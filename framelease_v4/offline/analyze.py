#!/usr/bin/env python3
"""Analysis of the v4 offline lease ablation (Table II-A): Age-Only vs Global-Margin vs Suffix-Aligned (CPU only).

    cd /home/kang/Desktop/DAC
    OMP_NUM_THREADS=1 .conda-unidrive-linux/bin/python -I -B framelease_v4/offline/analyze.py

Inputs: OUT/frames/<clip>.npz (stage_frames.py). Outputs: OUT/candidate_metrics.csv, frontier.csv, nested.csv,
nested_folds.csv, train_selected.csv, paired.csv, per_clip_selected.csv, analysis.json.

Definitions (T_c = 0.5 s, Hbar = 2.5 s, depth-1 plans)
------------------------------------------------------
V_suf = clip(V - T_c, 0, Hbar) (censored V -> Hbar): the latest plan age at which the next T_c of execution still
stays d_safe away from every real actor. Conflict = V not censored (a real approach within the 3 s horizon).
Every design is scored against this one yardstick; a lease is a deadline on the plan's age.
  validity violation   H > V_suf + 1e-6 (the lease allows the plan beyond its realized validity)
    R_marg             violations / plans;      R_cond   violations / conflict plans
  continuity           P(H >= need): the plan in use stays certified until its successor is released
  utilization          mean over plans with V_suf > 0 of min(H, V_suf) / V_suf (capped at 1; over-estimates do not
                       count as use); pooled variant sum min(H, V_suf) / sum V_suf
  premature refresh    H < need <= V_suf: the deadline expires before the next commit although the realized validity
                       still covered it; reported conditional on V_suf >= need (primary) and per plan
needs: fast-prefix 2 x 0.457 + 0.05 = 0.964 s and measured 2 x 0.896 + 0.05 = 1.842 s.

Designs and knobs
-----------------
AGE        H = T_age, T_age = 0, 0.05, ..., 2.5 s.
GLOBAL     v2 Global-Margin lease, cap 2.5 s (aligned with Hbar); GLOBAL_c2 = the v2 deployed 2.0 s cap.
SUFFIX     Eq. 1-3 suffix-aligned lease.
GLOBAL_TAU mechanism control: the whole-horizon minimum of Eq. 1's integrand with the SAME tau-indexed envelope as
           SUFFIX (H = Hbar if m(tau) - B(tau) > delta for every tau in [0, T_pred], else 0); isolates the alignment
           from the v2 lease's staleness-indexed envelope.
GLOBAL / SUFFIX share the envelope candidates: ZERO (H = 0, i.e. always fall back), E0 at q30 ... q99.5 fitted on
the 5 TRAIN clips, lambda x E0 q95 (TRAIN) for lambda = 0 ... 2 (0 = no envelope), and the v2 deployed file.
GLOBAL_L / SUFFIX_L (sensitivity, VAL only): ZERO plus the 36-clip LOCO E0 family (q50 ... q99.5, lambda x q95).

Protocols (rule (a): maximal continuity at the need subject to risk point estimate <= alpha; ties: lower risk, then
candidate order; if nothing qualifies, H = 0)
--------------------------------------------------------------------------------------------------------------------
train_selected  candidate chosen on the 5 TRAIN clips (envelopes also fitted on TRAIN only), evaluated on 32 VAL.
nested          leave-one-clip-out over the 32 VAL clips: chosen on the other 31, evaluated on the held-out clip,
                pooled (TRAIN-fitted envelopes, so nothing of the held-out clip enters).
frontier        in-sample on VAL (descriptive, winner's curse): the best candidate at each alpha.
CIs: clip-level percentile bootstrap, 2000 resamples, seed 20261109, conditional on the chosen candidates.
Subsets: all plans; no_static_v0 (plans with V = 0 and ego speed < 0.1 m/s removed from selection and evaluation).
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault('OMP_NUM_THREADS', '1')
sys.dont_write_bytecode = True

import argparse  # noqa: E402
import time  # noqa: E402
import warnings  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v4.offline import common as C  # noqa: E402
from framelease_v4.offline import stage_frames as S  # noqa: E402

BASE_DESIGNS = ('AGE', 'GLOBAL', 'SUFFIX', 'GLOBAL_c2', 'GLOBAL_TAU', 'GLOBAL_L', 'SUFFIX_L')
# need-capped sensitivity: H' = min(H, need), i.e. only violations inside the steady-state replacement window count;
# design X_ncF is capped at the fast-prefix need and evaluated only there, X_ncM at the measured need.
NC_BASES = ('AGE', 'GLOBAL', 'SUFFIX', 'GLOBAL_TAU')
NC_DESIGNS = tuple(f'{b}_nc{t}' for b in NC_BASES for t in ('F', 'M'))
DESIGNS = BASE_DESIGNS + NC_DESIGNS
NC_NEED = {'F': 'fast', 'M': 'meas'}
MAIN_DESIGNS = ('AGE', 'GLOBAL', 'SUFFIX')
DESIGN_LABEL = {'AGE': 'Age-Only', 'GLOBAL': 'Global-Margin (v2)', 'SUFFIX': 'Suffix-Aligned (Eq. 1-3)',
                'GLOBAL_c2': 'Global-Margin, v2 2.0 s cap',
                'GLOBAL_TAU': 'Whole-horizon minimum of Eq. 1 (same tau-indexed envelope as Suffix)',
                **{f'{b}_nc{t}': f'{b} capped at the {NC_NEED[t]} need' for b in NC_BASES for t in ('F', 'M')},
                'GLOBAL_L': 'Global-Margin, LOCO-36 envelopes',
                'SUFFIX_L': 'Suffix-Aligned, LOCO-36 envelopes'}
VAL_ONLY = ('GLOBAL_L', 'SUFFIX_L')
SUBSETS = ('all', 'no_static_v0')
NEED_KEYS = ('fast', 'meas')
RISKS = ('R_cond', 'R_marg')
STATUS_NAMES = {v: k for k, v in C.STATUS_CODES.items()}
BI = 'BlockedIntersection_Town03_Route135_Weather5'
# per-clip sufficient statistics: need-independent and need-dependent keys
KEYS0 = ('n', 'conf', 'over', 'overc', 'npos', 'sum_u', 'sum_min', 'sum_vsuf', 'sum_H', 'nzero',
         'miss_confident', 'miss_low_confidence', 'miss_undetected', 'miss_absent_at_capture')
KEYS1 = ('cont', 'oracle', 'prem', 'unsafe_cont')
# metric -> (numerator key, denominator key)
METRICS = {'continuity': ('cont', 'n'), 'R_marg': ('over', 'n'), 'R_cond': ('overc', 'conf'),
           'utilization': ('sum_u', 'npos'), 'utilization_pooled': ('sum_min', 'sum_vsuf'),
           'premature_refresh': ('prem', 'oracle'), 'premature_refresh_marg': ('prem', 'n'),
           'mean_H_s': ('sum_H', 'n'), 'P_H_zero': ('nzero', 'n'), 'oracle_continuity': ('oracle', 'n'),
           'unsafe_continuity': ('unsafe_cont', 'n')}
NOBI_KEYS = ('continuity', 'R_cond', 'R_marg', 'utilization', 'premature_refresh', 'conf', 'over')
CI_METRICS = ('continuity', 'R_marg', 'R_cond', 'utilization', 'utilization_pooled', 'premature_refresh',
              'premature_refresh_marg', 'mean_H_s', 'P_H_zero')


# ----------------------------------------------------------------------------- data

def design_needs(design):
    return (NC_NEED[design[-1]],) if design in NC_DESIGNS else NEED_KEYS


def candidates(design, d):
    """Candidate names, knob values and the (F, K) lease matrix of one clip."""
    if design in NC_DESIGNS:
        names, knobs, H = candidates(design[:-4], d)
        return names, knobs, (None if H is None else np.minimum(H, C.NEEDS[NC_NEED[design[-1]]]))
    F = len(d['V'])
    if design == 'AGE':
        names = [f'T_age={t:.2f}s' for t in C.T_AGE_GRID]
        H = np.broadcast_to(np.asarray(C.T_AGE_GRID, dtype=float), (F, len(C.T_AGE_GRID))).copy()
        return names, list(C.T_AGE_GRID), H
    zero = np.zeros((F, 1))
    if design in ('GLOBAL', 'GLOBAL_c2', 'SUFFIX', 'GLOBAL_TAU'):
        names = ['ZERO'] + list(d['names_T'])
        if design == 'SUFFIX':
            H = np.clip(d['ts_T'] - C.T_C, 0.0, C.HBAR)
        elif design == 'GLOBAL_TAU':
            # min over the WHOLE horizon [0, T_pred] of m(tau) - B(tau) > delta  <=>  no crossing before T_pred
            H = np.where(d['ts_T'] >= C.T_PRED - 1e-9, C.HBAR, 0.0)
        else:
            H = np.minimum(d['hg_T'], 2.0 if design == 'GLOBAL_c2' else 2.5)
    else:
        names = ['ZERO'] + list(d['names_L'])
        if not len(d['names_L']):
            return names, [None] * len(names), None
        H = np.clip(d['ts_L'] - C.T_C, 0.0, C.HBAR) if design == 'SUFFIX_L' else np.minimum(d['hg_L'], 2.5)
    return names, [None] * len(names), np.hstack([zero, H])


def clip_sums(H, d, mask):
    """Per-candidate sufficient statistics of one clip (dict of (K,) arrays and {need: (K,)})."""
    V = d['V']
    Vsuf = np.clip(V - C.T_C, 0.0, C.HBAR)
    conflict = ~d['censored']
    m = mask
    Hm, Vm, cm = H[m], Vsuf[m], conflict[m]
    over = Hm > Vm[:, None] + C.OVER_EPS
    pos = Vm > 0
    u = np.zeros_like(Hm)
    if pos.any():
        u[pos] = np.minimum(Hm[pos], Vm[pos, None]) / Vm[pos, None]
    st = d['bind_status'][m]
    out = {'n': np.full(H.shape[1], float(m.sum())), 'conf': np.full(H.shape[1], float(cm.sum())),
           'over': over.sum(0).astype(float), 'overc': (over & cm[:, None]).sum(0).astype(float),
           'npos': np.full(H.shape[1], float(pos.sum())), 'sum_u': u.sum(0),
           'sum_min': np.minimum(Hm, Vm[:, None]).sum(0), 'sum_vsuf': np.full(H.shape[1], float(Vm.sum())),
           'sum_H': Hm.sum(0), 'nzero': (Hm <= 1e-9).sum(0).astype(float)}
    for name, code in C.STATUS_CODES.items():
        if name == 'none':
            continue
        out[f'miss_{name}'] = (over & (st == code)[:, None]).sum(0).astype(float)
    for nk in NEED_KEYS:
        need = C.NEEDS[nk]
        ok_h = Hm >= need - 1e-9
        ok_v = Vm >= need - 1e-9
        out[('cont', nk)] = ok_h.sum(0).astype(float)
        out[('oracle', nk)] = np.full(H.shape[1], float(ok_v.sum()))
        out[('prem', nk)] = (~ok_h & ok_v[:, None]).sum(0).astype(float)
        out[('unsafe_cont', nk)] = (ok_h & ~ok_v[:, None]).sum(0).astype(float)
    return out


def build(lists):
    """sums[design][subset][key] -> (C, K) over all 37 clips (rows in lists['all'] order); names per design.
    VAL-only designs have NaN rows for the TRAIN clips."""
    clips = lists['all']
    data = {c: S.load_clip(c) for c in clips}
    sums, names, knobs = {}, {}, {}
    for des in DESIGNS:
        sums[des] = {}
        for sub in SUBSETS:
            rows = []
            for c in clips:
                d = data[c]
                nm, kn, H = candidates(des, d)
                if H is None:
                    rows.append(None)
                    continue
                if des in names and names[des] != nm:
                    raise SystemExit(f'candidate list of {des} differs between clips')
                names[des], knobs[des] = nm, kn
                mask = np.ones(len(d['V']), dtype=bool)
                if sub == 'no_static_v0':
                    mask &= ~(d['v0'] & (d['speed'] < C.STATIONARY_MPS))
                rows.append(clip_sums(H, d, mask))
            K = len(names[des])
            keys = list(KEYS0) + [(k, nk) for k in KEYS1 for nk in NEED_KEYS]
            sums[des][sub] = {key: np.stack([r[key] if r is not None else np.full(K, np.nan) for r in rows])
                              for key in keys}
    return data, sums, names, knobs


# ----------------------------------------------------------------------------- statistics

def boot_weights(n_clips, n_boot=C.BOOT_N, seed=C.BOOT_SEED):
    rng = np.random.default_rng(seed)
    return np.vstack([np.ones(n_clips), rng.multinomial(n_clips, np.full(n_clips, 1.0 / n_clips), size=n_boot)])


def mkey(key, nk):
    return (key, nk) if key in KEYS1 else key


def metric_values(S_, metric, nk, W):
    """(B+1, K) metric values from per-clip sums S_ (rows = clips of W)."""
    num_k, den_k = METRICS[metric]
    num = W @ S_[mkey(num_k, nk)]
    den = W @ S_[mkey(den_k, nk)]
    with np.errstate(invalid='ignore', divide='ignore'):
        return num / den


def ci(vals):
    v = np.asarray(vals, dtype=float)
    v = v[np.isfinite(v)]
    if not len(v):
        return (np.nan, np.nan)
    return (float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975)))


def choose(cont, est, alpha):
    ok = np.isfinite(est) & (est <= alpha + 1e-12)
    idx = np.flatnonzero(ok)
    if not len(idx):
        return None
    return int(min(idx, key=lambda i: (-cont[i], est[i], i)))


def sub_rows(S_, rows):
    return {k: v[rows] for k, v in S_.items()}


def chosen_sums(S_, rows, choice):
    """Per-clip sums (C, 1) of a per-clip choice vector; choice None -> index 0, which is H = 0 in every design
    (ZERO for the envelope designs, T_age = 0 for AGE), i.e. the controller only falls back."""
    out = {}
    for key, arr in S_.items():
        out[key] = np.array([arr[r, (0 if k is None else k)] for r, k in zip(rows, choice)], dtype=float)[:, None]
    return out


def summarize(S1, W, nk):
    """Point estimates and CIs of single-column sums S1 ((C, 1) arrays); need-dependent metrics at need nk."""
    out = {}
    for met in METRICS:
        v = metric_values(S1, met, nk, W)[:, 0]
        out[met] = float(v[0]) if np.isfinite(v[0]) else np.nan
        if met in CI_METRICS:
            out[met + '_ci'] = ci(v[1:])
    for key in ('n', 'conf', 'over', 'overc', 'miss_confident', 'miss_low_confidence', 'miss_undetected',
                'miss_absent_at_capture'):
        out[key] = float(W[0] @ S1[key][:, 0])
    return out


def is_need_metric(met):
    return METRICS[met][0] in KEYS1 or METRICS[met][1] in KEYS1


# ----------------------------------------------------------------------------- protocols

def run(lists, sums, names, knobs, t0):
    clips = lists['all']
    vrows = [clips.index(c) for c in lists['val']]
    trows = [clips.index(c) for c in lists['train']]
    Wv = boot_weights(len(vrows))
    Wv_noBI = Wv.copy()
    Wv_noBI[:, lists['val'].index(BI)] = 0.0
    Wt1 = np.ones((1, len(trows)))
    cand_rows, front_rows, nest_rows, fold_rows, tsel_rows, pair_rows, perclip_rows = [], [], [], [], [], [], []
    chosen = {}       # (protocol, design, subset, alpha, nk) -> per-VAL-clip choice list
    for des in DESIGNS:
        for sub in SUBSETS:
            S_ = sums[des][sub]
            Sv = sub_rows(S_, vrows)
            K = len(names[des])
            for nk in design_needs(des):
                # ---------------- candidate table
                vals = {met: metric_values(Sv, met, nk, Wv) for met in METRICS}
                tr = ({met: metric_values(sub_rows(S_, trows), met, nk, Wt1)[0] for met in METRICS}
                      if des not in VAL_ONLY else None)
                for k in range(K):
                    r = {'design': des, 'design_label': DESIGN_LABEL[des], 'candidate': names[des][k],
                         'candidate_label': ('fallback (H = 0)' if names[des][k] == 'ZERO' else
                                             (names[des][k] if des == 'AGE' else C.config_label(names[des][k]))),
                         'knob_T_age_s': knobs[des][k], 'subset': sub, 'need': nk, 'need_s': C.NEEDS[nk]}
                    for met in METRICS:
                        r[f'val_{met}'] = vals[met][0, k]
                        if met in CI_METRICS:
                            lo, hi = ci(vals[met][1:, k])
                            r[f'val_{met}_lo'], r[f'val_{met}_hi'] = lo, hi
                    for key in ('n', 'conf', 'over', 'miss_confident', 'miss_low_confidence', 'miss_undetected',
                                'miss_absent_at_capture'):
                        r[f'val_{key}'] = float(Sv[key][:, k].sum())
                    if tr is not None:
                        for met in ('continuity', 'R_marg', 'R_cond', 'utilization', 'premature_refresh'):
                            r[f'train_{met}'] = tr[met][k]
                        r['train_conf'] = float(sub_rows(S_, trows)['conf'][:, k].sum())
                        r['train_over'] = float(sub_rows(S_, trows)['over'][:, k].sum())
                    cand_rows.append(r)
                cont_v = vals['continuity'][0]
                # ---------------- frontier (in-sample VAL)
                for risk in RISKS:
                    for alpha in C.ALPHAS:
                        k = choose(cont_v, vals[risk][0], alpha)
                        row = {'design': des, 'subset': sub, 'need': nk, 'risk': risk, 'alpha': alpha,
                               'candidate': None if k is None else names[des][k]}
                        S1 = chosen_sums(Sv, range(len(vrows)), [k] * len(vrows))
                        row.update(summarize(S1, Wv, nk))
                        front_rows.append(row)
                # ---------------- nested leave-one-clip-out over VAL (risk R_cond)
                tot = {key: arr.sum(0) for key, arr in Sv.items()}
                for alpha in C.NESTED_ALPHAS:
                    choice = []
                    for i in range(len(vrows)):
                        loo = {key: (tot[key] - Sv[key][i])[None, :] for key in Sv}
                        c_ = metric_values(loo, 'continuity', nk, np.ones((1, 1)))[0]
                        e_ = metric_values(loo, 'R_cond', nk, np.ones((1, 1)))[0]
                        choice.append(choose(c_, e_, alpha))
                        fold_rows.append({'design': des, 'subset': sub, 'need': nk, 'alpha': alpha,
                                          'held_out_clip': lists['val'][i],
                                          'chosen': None if choice[-1] is None else names[des][choice[-1]]})
                    chosen[('nested', des, sub, alpha, nk)] = choice
                    S1 = chosen_sums(Sv, range(len(vrows)), choice)
                    row = {'design': des, 'subset': sub, 'need': nk, 'alpha': alpha, 'risk': 'R_cond',
                           'n_distinct_choices': len({c for c in choice}),
                           'modal_choice': _modal([None if c is None else names[des][c] for c in choice])}
                    row.update(summarize(S1, Wv, nk))
                    row.update({f'noBI_{k}': v for k, v in summarize(S1, Wv_noBI, nk).items()
                                if k.startswith(NOBI_KEYS)})
                    nest_rows.append(row)
                # ---------------- TRAIN-selected
                if des in VAL_ONLY:
                    continue
                Str = sub_rows(S_, trows)
                c_t = metric_values(Str, 'continuity', nk, Wt1)[0]
                for alpha in C.NESTED_ALPHAS:
                    e_t = metric_values(Str, 'R_cond', nk, Wt1)[0]
                    k = choose(c_t, e_t, alpha)
                    chosen[('train', des, sub, alpha, nk)] = [k] * len(vrows)
                    S1 = chosen_sums(Sv, range(len(vrows)), [k] * len(vrows))
                    row = {'design': des, 'subset': sub, 'need': nk, 'alpha': alpha, 'risk': 'R_cond',
                           'candidate': None if k is None else names[des][k],
                           'candidate_label': (None if k is None else (names[des][k] if des == 'AGE' else
                                               ('fallback (H = 0)' if names[des][k] == 'ZERO' else
                                                C.config_label(names[des][k])))),
                           'train_continuity': None if k is None else c_t[k],
                           'train_R_cond': None if k is None else e_t[k],
                           'train_conf': float(Str['conf'][:, 0].sum()),
                           'train_over': None if k is None else float(Str['over'][:, k].sum())}
                    row.update(summarize(S1, Wv, nk))
                    row.update({f'noBI_{kk}': v for kk, v in summarize(S1, Wv_noBI, nk).items()
                                if kk.startswith(NOBI_KEYS)})
                    tsel_rows.append(row)
                    if sub == 'all' and alpha == C.PRIMARY_ALPHA and des in MAIN_DESIGNS:
                        for i, c in enumerate(lists['val']):
                            S1c = {key: arr[i:i + 1] for key, arr in S1.items()}
                            pr = {'design': des, 'need': nk, 'clip': c, 'candidate': row['candidate']}
                            pr.update({kk: v for kk, v in summarize(S1c, np.ones((1, 1)), nk).items()
                                       if not kk.endswith('_ci')})
                            perclip_rows.append(pr)
        print(f'[{time.time() - t0:6.1f}s] {des} done', flush=True)
    # ---------------- paired differences (clip bootstrap of the difference)
    pairs = (('SUFFIX', 'GLOBAL'), ('SUFFIX', 'AGE'), ('GLOBAL', 'AGE'), ('SUFFIX', 'GLOBAL_TAU'),
             ('SUFFIX_L', 'GLOBAL_L'), ('GLOBAL', 'GLOBAL_c2'),
             ('SUFFIX_ncF', 'GLOBAL_ncF'), ('SUFFIX_ncM', 'GLOBAL_ncM'), ('SUFFIX_ncF', 'GLOBAL_TAU_ncF'),
             ('SUFFIX_ncM', 'GLOBAL_TAU_ncM'), ('SUFFIX_ncF', 'AGE_ncF'), ('SUFFIX_ncM', 'AGE_ncM'))
    for proto in ('train', 'nested'):
        for a, b in pairs:
            for sub in SUBSETS:
                for nk in NEED_KEYS:
                    for alpha in C.NESTED_ALPHAS:
                        ka, kb = chosen.get((proto, a, sub, alpha, nk)), chosen.get((proto, b, sub, alpha, nk))
                        if ka is None or kb is None:
                            continue
                        Sa = chosen_sums(sub_rows(sums[a][sub], vrows), range(len(vrows)), ka)
                        Sb = chosen_sums(sub_rows(sums[b][sub], vrows), range(len(vrows)), kb)
                        for met in ('continuity', 'R_cond', 'R_marg', 'utilization', 'premature_refresh', 'mean_H_s'):
                            va = metric_values(Sa, met, nk, Wv)[:, 0]
                            vb = metric_values(Sb, met, nk, Wv)[:, 0]
                            dlt = va - vb
                            lo, hi = ci(dlt[1:])
                            with warnings.catch_warnings():
                                warnings.simplefilter('ignore', RuntimeWarning)
                                p_le0 = float(np.mean(dlt[1:] <= 0)) if np.isfinite(dlt[1:]).any() else np.nan
                            pair_rows.append({'protocol': proto, 'a': a, 'b': b, 'subset': sub, 'need': nk,
                                              'alpha': alpha, 'metric': met, 'a_value': va[0], 'b_value': vb[0],
                                              'diff': dlt[0], 'diff_lo': lo, 'diff_hi': hi,
                                              'boot_share_diff_le_0': p_le0})
    return cand_rows, front_rows, nest_rows, fold_rows, tsel_rows, pair_rows, perclip_rows


def _modal(xs):
    from collections import Counter
    c = Counter(xs).most_common(1)
    return f'{c[0][0]} ({c[0][1]}/{len(xs)})' if c else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.parse_args(argv)
    t0 = time.time()
    C.check_disk()
    lists = C.load_lists()
    data, sums, names, knobs = build(lists)
    print(f'[{time.time() - t0:6.1f}s] sums built', flush=True)
    cand, front, nest, folds, tsel, pairs, perclip = run(lists, sums, names, knobs, t0)
    C.write_csv(C.OUT / 'candidate_metrics.csv', cand)
    C.write_csv(C.OUT / 'frontier.csv', front)
    C.write_csv(C.OUT / 'nested.csv', nest)
    C.write_csv(C.OUT / 'nested_folds.csv', folds)
    C.write_csv(C.OUT / 'train_selected.csv', tsel)
    C.write_csv(C.OUT / 'paired.csv', pairs)
    C.write_csv(C.OUT / 'per_clip_selected.csv', perclip)
    # context counts
    ctx = {}
    for sub in SUBSETS:
        S_ = sums['AGE'][sub]
        for split in ('val', 'train'):
            rows = [lists['all'].index(c) for c in lists[split]]
            ctx[f'{split}_{sub}'] = {'plans': float(S_['n'][rows, 0].sum()), 'conflicts': float(S_['conf'][rows, 0].sum()),
                                     'oracle_continuity_fast': float(S_[('oracle', 'fast')][rows, 0].sum() /
                                                                     S_['n'][rows, 0].sum()),
                                     'oracle_continuity_meas': float(S_[('oracle', 'meas')][rows, 0].sum() /
                                                                     S_['n'][rows, 0].sum())}
    vrows = [lists['all'].index(c) for c in lists['val']]
    Vs = np.concatenate([np.clip(data[c]['V'] - C.T_C, 0, C.HBAR)[~data[c]['censored']] for c in lists['val']])
    ctx['val_conflicts_Vsuf_zero'] = int((Vs <= 0).sum())
    ctx['val_conflicts_by_status'] = {name: int(sum(((data[c]['bind_status'] == code) & ~data[c]['censored']).sum()
                                                    for c in lists['val']))
                                      for name, code in C.STATUS_CODES.items() if name != 'none'}
    ctx['val_conflicts_BI'] = int((~data[BI]['censored']).sum())
    ctx['val_static_v0'] = int(sum((data[c]['v0'] & (data[c]['speed'] < C.STATIONARY_MPS)).sum() for c in lists['val']))
    ctx['val_static_v0_BI'] = int((data[BI]['v0'] & (data[BI]['speed'] < C.STATIONARY_MPS)).sum())
    ctx['invalid_detection_plans_val'] = int(sum((data[c]['lease_status'] == 2).sum() for c in lists['val']))
    C.write_json(C.OUT / 'analysis.json', {'context': ctx, 'needs': C.NEEDS, 'T_c': C.T_C, 'Hbar': C.HBAR,
                                           'alphas': C.ALPHAS, 'nested_alphas': C.NESTED_ALPHAS,
                                           'boot': {'n': C.BOOT_N, 'seed': C.BOOT_SEED},
                                           'designs': DESIGN_LABEL, 'n_candidates': {d: len(names[d]) for d in names},
                                           'code_sha256': C.code_sha256(), 'wall_s': time.time() - t0})
    C.log_progress(f'analyze done in {time.time() - t0:.0f}s: {len(cand)} candidate rows')
    print(f'done in {time.time() - t0:.1f}s')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
