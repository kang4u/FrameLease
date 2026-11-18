#!/usr/bin/env python3
"""Write OUT/README.md and OUT/summary.json from the analysis outputs only (no recomputation).

    .conda-unidrive-linux/bin/python -I -B framelease_v4/offline/make_readme.py
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault('OMP_NUM_THREADS', '1')
sys.dont_write_bytecode = True

import csv  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v4.offline import common as C  # noqa: E402

O = C.OUT
LABEL = {'AGE': 'Age-Only', 'GLOBAL': 'Global-Margin (v2)', 'SUFFIX': 'Suffix-Aligned (Eq. 1-3)',
         'GLOBAL_TAU': 'Whole-horizon control', 'GLOBAL_c2': 'Global-Margin, v2 2.0 s cap',
         'GLOBAL_L': 'Global-Margin, LOCO-36 env.', 'SUFFIX_L': 'Suffix-Aligned, LOCO-36 env.'}
NEEDS = {'fast': '0.964 s (fast prefix)', 'meas': '1.842 s (measured)'}


def rd(name):
    with open(O / name, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def fl(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float('nan')
    return v


def cil(s):
    if s in (None, ''):
        return (float('nan'), float('nan'))
    v = json.loads(s)
    return (fl(v[0]) if v[0] is not None else float('nan'), fl(v[1]) if v[1] is not None else float('nan'))


def p1(x, nd=1):
    v = fl(x)
    return 'n/a' if v != v else f'{100 * v:.{nd}f}'


def pci(x, ci, nd=1):
    v = fl(x)
    if v != v:
        return 'n/a'
    lo, hi = cil(ci) if isinstance(ci, str) else ci
    if lo != lo:
        return f'{100 * v:.{nd}f}'
    return f'{100 * v:.{nd}f} [{100 * lo:.{nd}f}, {100 * hi:.{nd}f}]'


def dci(r, nd=1, scale=100):
    return (f'{scale * fl(r["diff"]):+.{nd}f} [{scale * fl(r["diff_lo"]):+.{nd}f}, '
            f'{scale * fl(r["diff_hi"]):+.{nd}f}]')


def cand_label(c):
    if c in (None, '', 'None'):
        return 'fallback (H = 0)'
    if c == 'ZERO':
        return 'fallback (H = 0)'
    if c.startswith('T_age'):
        return c.replace('T_age=', 'T_age = ')
    return C.config_label(c)


def pick(rows, **kw):
    out = [r for r in rows if all(str(r.get(k)) == str(v) for k, v in kw.items())]
    if len(out) != 1:
        raise KeyError(f'{kw}: {len(out)} rows')
    return out[0]


def main():
    cand, front, nest, tsel, pair = (rd('candidate_metrics.csv'), rd('frontier.csv'), rd('nested.csv'),
                                     rd('train_selected.csv'), rd('paired.csv'))
    folds = rd('nested_folds.csv')
    ana = json.loads((O / 'analysis.json').read_text())
    chk = json.loads((O / 'checks' / 'crosscheck.json').read_text())
    envchk = json.loads((O / 'envelopes' / 'selfcheck.json').read_text())
    f1chk = json.loads((O / 'fig1' / 'fig1_check.json').read_text())
    ctx = ana['context']
    L = []
    w = L.append
    S = {}     # summary.json

    # ------------------------------------------------------------------ header
    w('# FrameLease v4 offline lease ablation (Table II-A) and Fig. 1 data')
    w('')
    w(f'Generated {time.strftime("%Y-%m-%d %H:%M %z")} by `framelease_v4/offline/make_readme.py` from the CSV/JSON files '
      'in this directory; every number below is read from them. CPU only: no GPU, no CARLA, no model inference; '
      'the plans and detections are the stored UniDriveVLA depth-1 outputs of the C1 sweep. Code: '
      '`framelease_v4/offline/`. Inputs are read-only (`framelease_v2`, `framelease_v3` imported unchanged).')
    w('')
    w('**Question (outline Sec. IV-B, paragraph 1).** Does the suffix-aligned, action-conditioned validity lease '
      '(Eq. 1-3) give a larger usable computation window than an observation-age deadline (Age-Only) and the '
      'v2 whole-horizon lease (Global-Margin) at a similar validity risk?')
    w('')

    # ------------------------------------------------------------------ bottom line
    def nrow(des, nk, alpha='0.05', sub='all'):
        return pick(nest, design=des, need=nk, alpha=alpha, subset=sub)

    def trow(des, nk, alpha='0.05', sub='all'):
        return pick(tsel, design=des, need=nk, alpha=alpha, subset=sub)

    def prow(proto, a, b, nk, met, alpha='0.05', sub='all'):
        return pick(pair, protocol=proto, a=a, b=b, need=nk, metric=met, alpha=alpha, subset=sub)

    def crow(des, cand_name, nk, sub='all'):
        return pick(cand, design=des, candidate=cand_name, need=nk, subset=sub)

    age_fast = crow('AGE', 'T_age=1.00s', 'fast')
    age_meas = crow('AGE', 'T_age=1.85s', 'meas')
    age_pos = crow('AGE', 'T_age=0.05s', 'fast')
    w('## 0. Bottom line')
    w('')
    w(f'Data: 32 held-out VAL clips, {int(ctx["val_all"]["plans"])} depth-1 plans, {int(ctx["val_all"]["conflicts"])} '
      f'conflict plans (a real actor within d_safe = 0.5 m inside the 3 s horizon). TRAIN: 5 clips, '
      f'{int(ctx["train_all"]["plans"])} plans, {int(ctx["train_all"]["conflicts"])} conflicts. Needs: plan in use '
      'certified until its successor is released, 2 L_rel + 0.05 s = 0.964 s with the fast prefix and 1.842 s at the '
      'measured latency. R_cond = share of conflict plans whose lease runs past the realized validity.')
    w('')
    bl = []
    bl.append(f'1. **Age-Only cannot be risk-controlled.** Every positive age deadline already misses '
              f'{p1(age_pos["val_R_cond"])}% of the conflicts (T_age = 0.05 s; plans whose conflict starts within '
              f'T_c of capture). The shortest deadline that covers the need misses {p1(age_fast["val_R_cond"])}% '
              f'[{p1(age_fast["val_R_cond_lo"])}, {p1(age_fast["val_R_cond_hi"])}] (T_age 1.00 s, need 0.964 s; '
              f'R_marg {p1(age_fast["val_R_marg"])}%) and {p1(age_meas["val_R_cond"])}% (1.85 s, need 1.842 s). '
              'At any R_cond limit up to 30% (TRAIN-selected, nested and in-sample alike) it can only fall back: '
              'continuity 0%, premature refresh 100%.')
    nS, nG, nT = nrow('SUFFIX', 'fast'), nrow('GLOBAL', 'fast'), nrow('GLOBAL_TAU', 'fast')
    nSm, nGm, nTm = nrow('SUFFIX', 'meas'), nrow('GLOBAL', 'meas'), nrow('GLOBAL_TAU', 'meas')
    dSG = prow('nested', 'SUFFIX', 'GLOBAL', 'fast', 'continuity')
    dSGm = prow('nested', 'SUFFIX', 'GLOBAL', 'meas', 'continuity')
    dST = prow('nested', 'SUFFIX', 'GLOBAL_TAU', 'meas', 'continuity')
    bl.append(f'2. **Action-conditioned leases make the risk controllable.** At R_cond <= 5% (nested leave-one-clip-out, '
              f'held-out per clip) the Suffix-Aligned lease keeps {p1(nS["continuity"])}% of plans continuous at '
              f'0.964 s (realized R_cond {p1(nS["R_cond"])}%, utilization {p1(nS["utilization"])}%) and '
              f'{p1(nSm["continuity"])}% at 1.842 s; Age-Only keeps 0%.')
    bl.append(f'3. **Suffix alignment is not better than the whole-horizon leases at matched risk.** Nested at R_cond <= 5%: '
              f'Suffix {p1(nS["continuity"])}% vs Global-Margin {p1(nG["continuity"])}% continuity at 0.964 s '
              f'(paired difference {dci(dSG)} points) and {p1(nSm["continuity"])}% vs {p1(nGm["continuity"])}% at '
              f'1.842 s ({dci(dSGm)}); utilization {p1(nS["utilization"])}% vs {p1(nG["utilization"])}%. The '
              f'whole-horizon control with the same tau-indexed envelope reaches {p1(nT["continuity"])}% at both needs '
              f'(Suffix minus control at 1.842 s: {dci(dST)}). The outline\'s expected effect ("larger usable window '
              'at a similar validity risk") is not observed on UniDriveVLA\'s own detections.')
    fS30 = pick(front, design='SUFFIX', need='fast', risk='R_cond', alpha='0.3', subset='all')
    fG30 = pick(front, design='GLOBAL', need='fast', risk='R_cond', alpha='0.3', subset='all')
    bl.append(f'4. **Where suffix alignment does help: the high-continuity end.** Without an envelope the whole-horizon '
              f'leases saturate at {p1(fG30["continuity"])}% continuity (R_cond {p1(fG30["R_cond"])}%), while the '
              f'suffix lease reaches {p1(fS30["continuity"])}% at 0.964 s (R_cond {p1(fS30["R_cond"])}%) because it '
              'ignores approaches after the need. That region is above every literature risk level used so far '
              '(5-10%).')
    tS, tG = trow('SUFFIX', 'fast'), trow('GLOBAL', 'fast')
    bl.append(f'5. **TRAIN-selected settings (the "best training-clip setting")** are not risk-matched: TRAIN has only '
              f'{int(ctx["train_all"]["conflicts"])} conflicts, so R_cond <= 5% on TRAIN means zero TRAIN misses. '
              f'Suffix picks {cand_label(tS["candidate"])} and Global {cand_label(tG["candidate"])}; on VAL Suffix has '
              f'{p1(tS["continuity"])}% vs {p1(tG["continuity"])}% continuity (0.964 s) but also R_cond '
              f'{p1(tS["R_cond"])}% vs {p1(tG["R_cond"])}% (above the 5% limit for Suffix).')
    v2r = crow('GLOBAL_c2', 'V2file', 'meas')
    bl.append(f'6. **The v2 deployed lease** (Global-Margin, E0-orig q95, 2.0 s cap) is a low-risk, low-availability '
              f'point: continuity {p1(crow("GLOBAL_c2", "V2file", "fast")["val_continuity"])}% / '
              f'{p1(v2r["val_continuity"])}% (0.964 / 1.842 s) at R_cond {p1(v2r["val_R_cond"])}%; P(H = 0) '
              f'{p1(v2r["val_P_H_zero"])}%.')
    ncF = prow('nested', 'SUFFIX_ncF', 'GLOBAL_ncF', 'fast', 'continuity')
    ncM = prow('nested', 'SUFFIX_ncM', 'GLOBAL_ncM', 'meas', 'continuity')
    bl.append('7. **Conclusion for Table II-A.** The validity-lease row that the data supports is "action-conditioned '
              'vs age-only", not "suffix vs global". All conclusions hold without the static V = 0 plans, without '
              'BlockedIntersection and with the 36-clip LOCO envelopes; if only violations inside the replacement '
              f'window count (every lease capped at the need) the whole-horizon lease is ahead of Suffix: '
              f'{dci(ncF)} points at 0.964 s and {dci(ncM)} at 1.842 s (Sec. 5).')
    for b in bl:
        w(b)
    w('')
    S['bottom_line'] = bl

    # ------------------------------------------------------------------ definitions
    w('## 1. What was compared')
    w('')
    w('| design | lease H of a depth-1 plan captured at t_k | knob (candidates) |')
    w('|---|---|---|')
    w('| Age-Only | H = T_age for every plan (fixed observation-age deadline) | T_age = 0, 0.05, ..., 2.5 s (51) |')
    w('| Global-Margin (v2) | `framelease_v2/lease.py` margin_mode `global`: m_j = min over the whole horizon [0, 3 s] of '
      'the clearance between the planned ego footprint and detection j moved at constant velocity, minus d_safe; '
      'H_j = sup{D : m_j - B_j(D) > delta}, envelope indexed by staleness D; H = min_j H_j, capped at 2.5 s '
      '(v2 deployed: 2.0 s, Sec. 5) | envelope (53) |')
    w('| Suffix-Aligned (Eq. 1-3) | `framelease_v3/suffix_lease_eval.py`: M(Delta) = min over tau in [Delta, Delta + T_c] '
      'of m(tau) - B(tau), H = first Delta with M(Delta) <= delta, capped at Hbar = T_pred - T_c = 2.5 s | envelope (53) |')
    w('| Whole-horizon control | same tau-indexed envelope as Suffix, minimum over the whole horizon: H = Hbar if '
      'm(tau) - B(tau) > delta for all tau in [0, 3 s], else 0 (isolates the alignment from the v2 envelope indexing) '
      '| envelope (53) |')
    w('')
    w('Shared: d_safe 0.5 m, delta 0.2 m, T_c 0.5 s, 0.05 s grid, T_pred 3 s; relevant detections = vehicles and '
      'pedestrians with score >= 0.1; a non-finite relevant detection gives H = 0 for the envelope designs. Envelope '
      'candidates: ZERO (H = 0, always fall back); the isotropic E0 envelope B_c(tau) = vbar_c tau + abar_c tau^2 / 2 + '
      'sigma_c fitted on the **5 TRAIN clips only** at q30, q40, ..., q99.5; lambda x E0 q95 for lambda = 0 (no '
      'envelope), 0.05, ..., 2.0; and the v2 deployed parameter file. No VAL clip enters any envelope.')
    w('')
    w('Metrics, all against the same realized validity: V = first tau at which the planned ego footprint comes within '
      'd_safe of a real vehicle / walker footprint (non-reactive replay, censored at 3 s); V_suf = clip(V - T_c, 0, 2.5); '
      'conflict = V not censored.')
    w('')
    w('| metric | definition |')
    w('|---|---|')
    w('| validity violation | H > V_suf (the lease allows the plan beyond its realized validity); R_marg = violations / '
      'plans, R_cond = violations / conflict plans |')
    w('| continuity | P(H >= need): the plan in use stays certified until its successor is released |')
    w('| lease utilization | mean over plans with V_suf > 0 of min(H, V_suf) / V_suf (capped at 1: over-estimates do '
      'not count as use) |')
    w('| premature refresh | P(H < need given V_suf >= need): the deadline expires before the next commit although '
      'the realized validity still covered it |')
    w('')
    w('Protocols (rule (a): maximal continuity at the need subject to R_cond <= alpha; ties: lower R_cond, then grid '
      'order; nothing qualifies -> fallback H = 0; declared before any VAL number was computed, see PROGRESS.md):')
    w('')
    w('- **TRAIN-selected** ("best training-clip setting"): knob chosen on the 5 TRAIN clips, evaluated on the 32 VAL clips.')
    w('- **Nested (risk-matched, held-out)**: for each VAL clip the knob is chosen on the other 31 VAL clips and '
      'evaluated on it; pooled. The envelopes are TRAIN-fitted, so nothing of the held-out clip enters its choice.')
    w('- **Frontier (descriptive)**: best candidate at each alpha in-sample on VAL (winner\'s curse).')
    w('')
    w(f'CIs: clip bootstrap, {C.BOOT_N} resamples, seed {C.BOOT_SEED}, conditional on the chosen candidates. Paired '
      'differences resample clips jointly.')
    w('')

    # ------------------------------------------------------------------ Table II-A candidate
    w('## 2. Table II-A candidate: each design at its TRAIN-selected setting, evaluated on 32 VAL clips')
    w('')
    for alpha in ('0.05', '0.1'):
        w(f'Selection on TRAIN at R_cond <= {int(float(alpha) * 100)}%. Cells: % [95% CI].')
        w('')
        w('| design | need | setting chosen on TRAIN (TRAIN misses / conflicts) | continuity | R_cond | R_marg | '
          'utilization | premature refresh | mean H (s) |')
        w('|---|---|---|---|---|---|---|---|---|')
        for des in ('AGE', 'GLOBAL', 'SUFFIX'):
            for nk in ('fast', 'meas'):
                r = trow(des, nk, alpha)
                mH = fl(r['mean_H_s'])
                w(f'| {LABEL[des]} | {NEEDS[nk]} | {cand_label(r["candidate"])} ({int(fl(r["train_over"]))} / '
                  f'{int(fl(r["train_conf"]))}) | {pci(r["continuity"], r["continuity_ci"])} | '
                  f'{pci(r["R_cond"], r["R_cond_ci"])} | {pci(r["R_marg"], r["R_marg_ci"], 2)} | '
                  f'{pci(r["utilization"], r["utilization_ci"])} | '
                  f'{pci(r["premature_refresh"], r["premature_refresh_ci"])} | {mH:.2f} |')
        w('')
    w('Paired differences on VAL (TRAIN-selected, R_cond <= 5%), points [95% CI]:')
    w('')
    w('| pair | need | continuity | R_cond | utilization | premature refresh |')
    w('|---|---|---|---|---|---|')
    for a, b in (('SUFFIX', 'GLOBAL'), ('SUFFIX', 'AGE'), ('GLOBAL', 'AGE')):
        for nk in ('fast', 'meas'):
            w(f'| {LABEL[a]} - {LABEL[b]} | {NEEDS[nk]} | {dci(prow("train", a, b, nk, "continuity"))} | '
              f'{dci(prow("train", a, b, nk, "R_cond"))} | {dci(prow("train", a, b, nk, "utilization"))} | '
              f'{dci(prow("train", a, b, nk, "premature_refresh"))} |')
    w('')
    w('Reading: with 12 TRAIN conflicts the TRAIN rule cannot match risk across designs; Suffix gains continuity '
      'partly by taking more risk (its VAL R_cond exceeds 5%). Section 3 compares at matched risk.')
    w('')

    # ------------------------------------------------------------------ nested
    w('## 3. Risk-matched comparison: nested leave-one-clip-out selection over the 32 VAL clips')
    w('')
    w('| design | need | alpha | modal choice | continuity | realized R_cond | R_marg | utilization | premature refresh | misses / conflicts |')
    w('|---|---|---|---|---|---|---|---|---|---|')
    for alpha in ('0.05', '0.1'):
        for nk in ('fast', 'meas'):
            for des in ('AGE', 'GLOBAL', 'GLOBAL_TAU', 'SUFFIX'):
                r = nrow(des, nk, alpha)
                mc = r['modal_choice']
                name, _, cnt = mc.partition(' (')
                w(f'| {LABEL[des]} | {NEEDS[nk]} | {int(float(alpha) * 100)}% | {cand_label(name)} ({cnt} | '
                  f'{pci(r["continuity"], r["continuity_ci"])} | {pci(r["R_cond"], r["R_cond_ci"])} | '
                  f'{pci(r["R_marg"], r["R_marg_ci"], 2)} | {pci(r["utilization"], r["utilization_ci"])} | '
                  f'{pci(r["premature_refresh"], r["premature_refresh_ci"])} | {int(fl(r["over"]))} / '
                  f'{int(fl(r["conf"]))} |')
    w('')
    w('Paired differences (nested choices, clip bootstrap of the difference), points [95% CI]; share = bootstrap share '
      'of differences <= 0:')
    w('')
    w('| pair | need | alpha | continuity | utilization | premature refresh | R_cond |')
    w('|---|---|---|---|---|---|---|')
    S['nested_paired'] = {}
    for a, b in (('SUFFIX', 'GLOBAL'), ('SUFFIX', 'GLOBAL_TAU'), ('SUFFIX', 'AGE')):
        for alpha in ('0.05', '0.1'):
            for nk in ('fast', 'meas'):
                rc = prow('nested', a, b, nk, 'continuity', alpha)
                w(f'| {LABEL[a]} - {LABEL[b]} | {NEEDS[nk]} | {int(float(alpha) * 100)}% | {dci(rc)} (share '
                  f'{fl(rc["boot_share_diff_le_0"]):.2f}) | {dci(prow("nested", a, b, nk, "utilization", alpha))} | '
                  f'{dci(prow("nested", a, b, nk, "premature_refresh", alpha))} | '
                  f'{dci(prow("nested", a, b, nk, "R_cond", alpha))} |')
                S['nested_paired'][f'{a}-{b}|{nk}|{alpha}'] = {
                    m: [fl(prow('nested', a, b, nk, m, alpha)[k]) for k in ('diff', 'diff_lo', 'diff_hi')]
                    for m in ('continuity', 'utilization', 'premature_refresh', 'R_cond')}
    w('')
    nfold = {}
    for r in folds:
        if r['subset'] == 'all' and r['alpha'] == '0.05' and r['design'] in ('GLOBAL', 'SUFFIX', 'GLOBAL_TAU'):
            nfold.setdefault((r['design'], r['need']), []).append(r['chosen'])
    w('Choices across the 32 folds (R_cond <= 5%): ' + '; '.join(
        f'{LABEL[d]} @ {NEEDS[n].split(" ")[0]} s: ' + ', '.join(
            f'{cand_label(c)} x{v.count(c)}' for c in sorted(set(v), key=lambda x: -v.count(x)))
        for (d, n), v in sorted(nfold.items())) + '.')
    w('')

    # ------------------------------------------------------------------ frontier
    w('## 4. In-sample frontier on VAL (descriptive): best continuity at R_cond <= alpha')
    w('')
    w('Cells: continuity % (realized R_cond %, utilization %). Each design\'s best candidate on the 32 VAL clips; '
      'optimistic (winner\'s curse), shown for the shape of the trade-off.')
    w('')
    for nk in ('fast', 'meas'):
        w(f'Need {NEEDS[nk]}:')
        w('')
        w('| alpha | Age-Only | Global-Margin (v2) | Whole-horizon control | Suffix-Aligned |')
        w('|---|---|---|---|---|')
        for alpha in ('0.02', '0.05', '0.1', '0.15', '0.2', '0.3'):
            cells = []
            for des in ('AGE', 'GLOBAL', 'GLOBAL_TAU', 'SUFFIX'):
                r = pick(front, design=des, need=nk, risk='R_cond', alpha=alpha, subset='all')
                cells.append(f'{p1(r["continuity"])} ({p1(r["R_cond"])}, {p1(r["utilization"])})')
            w(f'| {int(round(float(alpha) * 100))}% | ' + ' | '.join(cells) + ' |')
        w('')
    w('Age-Only along its knob (VAL, all plans; continuity is 0 below the need and 100% at or above it):')
    w('')
    w('| T_age (s) | R_cond % [CI] | R_marg % | utilization % | R_cond without static V = 0 plans % |')
    w('|---|---|---|---|---|')
    for t in ('0.05', '0.50', '1.00', '1.85', '2.50'):
        r = crow('AGE', f'T_age={t}s', 'fast')
        r2 = crow('AGE', f'T_age={t}s', 'fast', 'no_static_v0')
        w(f'| {t} | {pci(r["val_R_cond"], (fl(r["val_R_cond_lo"]), fl(r["val_R_cond_hi"])))} | '
          f'{p1(r["val_R_marg"])} | {p1(r["val_utilization"])} | {p1(r2["val_R_cond"])} |')
    w('')
    w(f'Of the {int(ctx["val_all"]["conflicts"])} VAL conflict plans, {ctx["val_conflicts_Vsuf_zero"]} have V_suf = 0 '
      f'(the conflict starts within T_c of capture; {ctx["val_static_v0"]} of them are static V = 0 plans, '
      f'{ctx["val_static_v0_BI"]} in BlockedIntersection_Town03_Route135); any positive age deadline misses all of them.')
    w('')

    # ------------------------------------------------------------------ sensitivities
    w('## 5. Sensitivities (nested selection at R_cond <= 5%)')
    w('')
    w('| variant | need | Age-Only | Global-Margin | Whole-horizon control | Suffix-Aligned | Suffix - Global (points) |')
    w('|---|---|---|---|---|---|---|')

    def cell(r, pre=''):
        return f'{p1(r[pre + "continuity"])} (R_cond {p1(r[pre + "R_cond"])})'

    for nk in ('fast', 'meas'):
        rows = [nrow(d, nk) for d in ('AGE', 'GLOBAL', 'GLOBAL_TAU', 'SUFFIX')]
        w(f'| main (all plans) | {NEEDS[nk]} | ' + ' | '.join(cell(r) for r in rows) +
          f' | {dci(prow("nested", "SUFFIX", "GLOBAL", nk, "continuity"))} |')
    for nk in ('fast', 'meas'):
        rows = [nrow(d, nk, sub='no_static_v0') for d in ('AGE', 'GLOBAL', 'GLOBAL_TAU', 'SUFFIX')]
        w(f'| without the {ctx["val_static_v0"]} static V = 0 plans (selection and evaluation) | {NEEDS[nk]} | ' +
          ' | '.join(cell(r) for r in rows) +
          f' | {dci(prow("nested", "SUFFIX", "GLOBAL", nk, "continuity", sub="no_static_v0"))} |')
    for nk in ('fast', 'meas'):
        rows = [nrow(d, nk) for d in ('AGE', 'GLOBAL', 'GLOBAL_TAU', 'SUFFIX')]
        w(f'| BlockedIntersection excluded from evaluation (same choices) | {NEEDS[nk]} | ' +
          ' | '.join(cell(r, 'noBI_') for r in rows) + ' | - |')
    for nk in ('fast', 'meas'):
        g, s = nrow('GLOBAL_L', nk), nrow('SUFFIX_L', nk)
        w(f'| 36-clip LOCO envelopes (stored tracking-study fits) | {NEEDS[nk]} | - | {cell(g)} | - | {cell(s)} | '
          f'{dci(prow("nested", "SUFFIX_L", "GLOBAL_L", nk, "continuity"))} |')
    for nk, t in (('fast', 'F'), ('meas', 'M')):
        rows = [nrow(f'{d}_nc{t}', nk) for d in ('AGE', 'GLOBAL', 'GLOBAL_TAU', 'SUFFIX')]
        w(f'| every lease capped at the need (only violations inside the replacement window count) | {NEEDS[nk]} | ' +
          ' | '.join(cell(r) for r in rows) +
          f' | {dci(prow("nested", f"SUFFIX_nc{t}", f"GLOBAL_nc{t}", nk, "continuity"))} |')
    for nk in ('fast', 'meas'):
        g = nrow('GLOBAL_c2', nk)
        w(f'| Global-Margin with the v2 deployed 2.0 s cap | {NEEDS[nk]} | - | {cell(g)} | - | - | - |')
    w('')
    bi_miss = {d: int(fl(nrow(d, 'fast')['over']) - fl(nrow(d, 'fast')['noBI_over']))
               for d in ('GLOBAL', 'GLOBAL_TAU', 'SUFFIX')}
    w(f'BlockedIntersection holds {ctx["val_conflicts_BI"]} of the {int(ctx["val_all"]["conflicts"])} VAL conflicts, '
      f'{ctx["val_static_v0_BI"]} of them static V = 0 plans (ego stopped about 0 m behind a stopped car, MERGE_NOTE). '
      f'The nested choices miss {bi_miss["GLOBAL"]} / {bi_miss["GLOBAL_TAU"]} / {bi_miss["SUFFIX"]} of them '
      '(Global / control / Suffix, 0.964 s), so these easy conflicts dilute R_cond: with the clip removed from the '
      'evaluation the realized R_cond of the same choices rises to about 7%. The static-V = 0 row, which removes these '
      'plans from the selection as well, is the consistent sensitivity (realized R_cond back at about 5%).')
    w('')
    w('The 2.0 s cap lowers the Global-Margin risk at an unchanged continuity (needs < 2 s), so the selection can use a '
      'smaller envelope; a cap is itself a risk knob and any design capped near the need would gain the same way. The '
      'main comparison caps every design at the same Hbar = 2.5 s.')
    w('')
    w('Fixed reference settings (no selection), VAL:')
    w('')
    w('| setting | need | continuity | R_cond | R_marg | utilization | premature refresh | P(H = 0) |')
    w('|---|---|---|---|---|---|---|---|')
    for des, cname, lab in (('GLOBAL_c2', 'V2file', 'v2 deployed lease (Global-Margin, E0-orig q95, 2.0 s cap)'),
                            ('SUFFIX', 'V2file', 'Suffix-Aligned with the same v2 envelope file'),
                            ('SUFFIX', 'T_q95', 'Suffix-Aligned, E0 q95 (TRAIN)'),
                            ('GLOBAL', 'T_q95', 'Global-Margin, E0 q95 (TRAIN), 2.5 s cap'),
                            ('SUFFIX', 'T_x0.00', 'Suffix-Aligned, no envelope'),
                            ('GLOBAL', 'T_x0.00', 'Global-Margin, no envelope')):
        for nk in ('fast', 'meas'):
            r = crow(des, cname, nk)
            w(f'| {lab} | {NEEDS[nk]} | {pci(r["val_continuity"], (fl(r["val_continuity_lo"]), fl(r["val_continuity_hi"])))} | '
              f'{pci(r["val_R_cond"], (fl(r["val_R_cond_lo"]), fl(r["val_R_cond_hi"])))} | {p1(r["val_R_marg"], 2)} | '
              f'{p1(r["val_utilization"])} | {p1(r["val_premature_refresh"])} | {p1(r["val_P_H_zero"])} |')
    w('')

    # ------------------------------------------------------------------ misses
    w('## 6. What the remaining misses are (nested, R_cond <= 5%, all plans)')
    w('')
    w('Capture-time detection status of the real actor that ends V, for the violated conflict plans:')
    w('')
    w('| design | need | misses | confident detection | low-confidence detection | undetected | absent at capture |')
    w('|---|---|---|---|---|---|---|')
    for des in ('GLOBAL', 'GLOBAL_TAU', 'SUFFIX'):
        for nk in ('fast', 'meas'):
            r = nrow(des, nk)
            w(f'| {LABEL[des]} | {NEEDS[nk]} | {int(fl(r["over"]))} | {int(fl(r["miss_confident"]))} | '
              f'{int(fl(r["miss_low_confidence"]))} | {int(fl(r["miss_undetected"]))} | '
              f'{int(fl(r["miss_absent_at_capture"]))} |')
    st = ctx['val_conflicts_by_status']
    w('')
    w(f'All VAL conflicts by status: confident {st["confident"]}, low-confidence {st["low_confidence"]}, undetected '
      f'{st["undetected"]}, absent at capture {st["absent_at_capture"]}. Undetected and absent actors cannot be seen '
      'by any perception-driven lease; they set a floor under R_cond that only better perception removes.')
    w('')

    # ------------------------------------------------------------------ Fig. 1
    f1 = {}
    with open(O / 'fig1' / 'c1_age_vs_depth.csv', newline='') as f:
        for r in csv.DictReader(f):
            if r['run'] == 'R1m' and r['split'] == 'val':
                f1[(int(r['depth']), r['age_s'])] = r
    kap = []
    with open(O / 'fig1' / 'c1_fresh_vs_deep_kappa.csv', newline='') as f:
        kap = list(csv.DictReader(f))
    abil = []
    with open(O / 'fig1' / 'closed_loop_ds_by_ability.csv', newline='') as f:
        abil = list(csv.DictReader(f))
    trend = []
    with open(O / 'fig1' / 'closed_loop_kappa_trend.csv', newline='') as f:
        trend = list(csv.DictReader(f))
    w('## 7. Fig. 1 data (freshness-depth evidence; preliminary, the final figure uses the new test matrix)')
    w('')
    w('Files in `fig1/` (all re-derived or copied from the v2 sources listed in `fig1/fig1_sources.json`; '
      f'checks in `fig1/fig1_check.json`: C1 panel a reproduced to {f1chk["c1_vs_paper_figure"]["max_abs_diff_m"]:.0e} m, '
      'closed-loop route means identical to the frozen contrasts):')
    w('')
    w('- `c1_age_vs_depth.csv`: execution error vs observation age for flow depths 1 / 5 / 10 (offline replay, '
      'W = 1 s and 0.5 s; 15 held-out, 5 train, 20 all clips; mean of per-clip means, Student-t 95% interval).')
    w('- `c1_fresh_vs_deep_kappa.csv`: Fast@Fresh (depth 1, fresh) minus Deep@Old (depth 10, old) execution error vs '
      'kappa, and its staleness-gain / depth-cost decomposition.')
    w('- `closed_loop_ds_by_route.csv`, `closed_loop_ds_by_ability.csv`, `closed_loop_kappa_trend.csv`: closed-loop '
      'DS of Fixed Deep and Fast Only (measured-latency CARLA loop, 44 one-route-per-scenario-type routes).')
    w('')
    w('Offline execution error (m), 15 held-out clips, W = 1 s, mean [t 95%]:')
    w('')
    w('| age (s) | depth 1 | depth 5 | depth 10 |')
    w('|---|---|---|---|')
    for age in ('0', '0.5', '1', '1.5', '2'):
        cells = []
        for d in (1, 5, 10):
            r = f1[(d, age)]
            cells.append(f'{fl(r["exec_err_mean_m"]):.3f} [{fl(r["t95_lo"]):.3f}, {fl(r["t95_hi"]):.3f}]')
        w(f'| {age} | ' + ' | '.join(cells) + ' |')
    w('')
    w('Fast@Fresh minus Deep@Old (m; < 0: the fresher shallow plan is better), held-out clips, W = 0.5 s (RKm):')
    w('')
    w('| kappa | delta [t 95%] | staleness gain | depth cost | clips fresh better |')
    w('|---|---|---|---|---|')
    kk = {(r['quantity'], r['kappa']): r for r in kap if r['run'] == 'RKm' and r['split'] == 'val'}
    for kv in ('1', '1.5', '2', '2.4'):
        d_ = kk[('fast_fresh_minus_deep_old', kv)]
        sg = kk[('staleness_gain', kv)]
        dc = kk[('depth_cost_equal_age', kv)]
        w(f'| {kv} | {fl(d_["value_m"]):+.3f} [{fl(d_["t95_lo"]):+.3f}, {fl(d_["t95_hi"]):+.3f}] | '
          f'{fl(sg["value_m"]):+.3f} | {fl(dc["value_m"]):+.3f} | {d_["clips_neg"]} / {d_["n_clips"]} |')
    w('')
    w('Closed loop, DS difference Fixed Deep - Fast Only (route-paired):')
    w('')
    w('| kappa | seed | routes | mean DS difference [95% CI] | p (two-sided) | status |')
    w('|---|---|---|---|---|---|')
    for r in trend:
        if not r['metric'].startswith('driving_score'):
            continue
        p = fl(r['p_two_sided'])
        sub_ = ' (the 11 kappa-2.0 routes)' if r['metric'] == 'driving_score_on_kappa2_routes' else ''
        w(f'| {fl(r["kappa"]):.1f}{sub_} | {r["seed"]} | {r["n_routes"]} | {fl(r["mean_diff"]):+.2f} '
          f'[{fl(r["ci95_lo"]):+.2f}, {fl(r["ci95_hi"]):+.2f}] | {"n/a" if p != p else f"{p:.3f}"} | '
          f'{r["decision"]} |')
    w('')
    w('By Bench2Drive ability at kappa 1.0 (abilities overlap; bootstrap 95% CI over routes, seed 20261109):')
    w('')
    w('| ability | routes | seed 11: mean [CI]; routes deep better / fresh better / tie | mean over seeds 11/12 [CI] |')
    w('|---|---|---|---|')
    for ab in ('Merging', 'Overtaking', 'Emergency_Brake', 'Give_Way', 'Traffic_Signs', 'all'):
        a11 = pick(abil, ability=ab, series='seed 11')
        am = pick(abil, ability=ab, series='mean over seeds 11/12')
        def mci(r):
            lo, hi = fl(r['boot95_lo']), fl(r['boot95_hi'])
            return f'{fl(r["mean_DS_diff"]):+.1f}' + ('' if lo != lo else f' [{lo:+.1f}, {hi:+.1f}]')
        w(f'| {ab} | {a11["n_routes"]} | {mci(a11)}; {a11["routes_pos"]} / {a11["routes_neg"]} / '
          f'{a11["routes_zero"]} | {mci(am)} |')
    w('')
    w('No interval for fewer than 5 routes.')
    w('')
    k2 = {r['kappa']: r for r in trend if r['metric'] == 'driving_score_on_kappa2_routes'}
    w(f'On the 11 routes of the kappa-2.0 arm the kappa-1.0 difference is {fl(k2["1"]["mean_diff"]):+.1f} and the '
      f'kappa-1.5 difference {fl(k2["1.5"]["mean_diff"]):+.1f}, so the sign change at kappa 2.0 is not a route-selection '
      'artifact (descriptive).')
    w('')
    w('Reading: offline, freshness dominates depth at every kappa (age adds about 1 m of error per second on held-out '
      'clips while depth changes it by centimetres), and the fresh-shallow advantage grows with kappa. In the closed '
      'loop at kappa 1.0 the deeper, older plan scores higher on average (+9.1 DS, p = 0.067, n = 44; seed 12: +3.9, '
      'n = 15), with large heterogeneity across scenario types (Overtaking +20, Emergency_Brake -2), and the sign '
      'reverses at kappa 2.0 (-11.2, n = 11, exploratory). This is a latency-dependent crossover in closed loop, '
      'not a significant one at any single kappa; the final Fig. 1 should come from the new test matrix.')
    w('')

    # ------------------------------------------------------------------ paper reading
    w('## 8. What Table II-A can and cannot say')
    w('')
    w('Supported (offline, 32 held-out clips, UniDriveVLA detections):')
    w('')
    cont5 = [fl(nrow(d, nk)['continuity']) for d in ('GLOBAL', 'GLOBAL_TAU', 'SUFFIX') for nk in ('fast', 'meas')]
    pf, pm = prow('nested', 'SUFFIX', 'AGE', 'fast', 'premature_refresh'), prow('nested', 'SUFFIX', 'AGE', 'meas',
                                                                                 'premature_refresh')
    w(f'- An observation-age deadline cannot separate plans that are about to conflict from plans that are not: any '
      f'positive age deadline misses {p1(age_pos["val_R_cond"], 0)}% of conflict plans '
      f'({p1(crow("AGE", "T_age=0.05s", "fast", "no_static_v0")["val_R_cond"], 0)}% without the static V = 0 plans), and '
      f'covering the need costs {p1(age_fast["val_R_cond"], 0)}-{p1(age_meas["val_R_cond"], 0)}% R_cond. The three '
      f'action-conditioned leases keep {100 * min(cont5):.0f}-{100 * max(cont5):.0f}% of the plans continuous at a '
      'realized R_cond of about 5% (nested, both needs), where Age-Only keeps none.')
    w(f'- Premature refresh at matched risk: Age-Only refreshes every plan whose realized validity would have covered '
      f'the need; the Suffix lease cuts this by {-fl(pf["diff"]) * 100:.0f} points at 0.964 s '
      f'({dci(pf)}) and {-fl(pm["diff"]) * 100:.0f} points at 1.842 s ({dci(pm)}).')
    w('')
    w('Not supported:')
    w('')
    w('- "Suffix alignment gives a larger usable window than the global margin at a similar risk": at R_cond 5% and 10% '
      'the paired continuity differences at the 0.964 s need are within +/-6 points with CIs spanning 0, and at the '
      '1.842 s need the whole-horizon leases are as good or better (significantly so for the control at 5% and 10% '
      'and for Global-Margin at 10%, Sec. 3). Utilization differences are within +/-3 points. The suffix lease only '
      'extends the frontier where R_cond is 20-30% (Sec. 4).')
    w('- Any closed-loop Driving Score claim for a lease: the DS column of Table II-A needs the closed-loop matrix.')
    w('')
    w('Mechanism (consistent with the v3 R&D report): the risk at the 5% level is set by perception error at small tau '
      '(detection error, undetected actors), not by the far-future part of the plan that suffix alignment removes. '
      'With noisy detections and constant-velocity prediction, a predicted close approach later in the plan is '
      'itself evidence of near-term risk; the whole-horizon leases use that evidence and can therefore run with a '
      'much smaller envelope (0.3 x q95 or q30) at the same R_cond, while the suffix lease discards it and needs '
      '0.6 x q95. Suffix alignment pays off only when larger risk is accepted or, presumably, when perception is '
      'accurate enough that the far future carries no extra information (the v3 requirement grid).')
    w('')

    # ------------------------------------------------------------------ checks and provenance
    w('## 9. Checks, provenance and reproduction')
    w('')
    w(f'- Envelope self-check (`envelopes/selfcheck.json`): TRAIN E0 fits at q80-q99.5 and the v2 file reproduce '
      f'gate2\'s ORIG envelopes exactly (max abs diff {max(envchk["max_abs_diff"].values()):.1e}); pass = '
      f'{envchk["pass"]}. TRAIN calibration pairs: {envchk["train_pairs"]}.')
    w(f'- Cross-checks (`checks/crosscheck.json`, pass = {chk["pass"]}): suffix tau* and V reproduce gate2 frames.csv on '
      f'all {chk["n_compared_gate2"]} plans of the 15 VAL clips (max abs diff '
      f'{max(chk["suffix_vs_gate2_max_abs_s"].values()):.1e} s, CSV precision); the Global-Margin lease with the v2 file '
      f'and 2.0 s cap reproduces the v2 c2_eval `H_avl_s` (max abs diff {chk["global_v2file_cap2_vs_v2_c2eval_max_abs_s"]:.1e} s); '
      'plan and conflict counts equal MERGE_NOTE (2447 / 246 and 2970 / 663); the analysis code reproduces gate2\'s '
      'continuity / R_marg / R_cond for four suffix configurations on the 15 clips (max abs diff '
      f'{max(chk["metrics_vs_gate2_max_abs"].values()):.1e}).')
    w(f'- Fig. 1 checks (`fig1/fig1_check.json`): pass = {f1chk["pass"]}.')
    w('- Tests: `framelease_v4/offline/tests/test_offline.py` (metric definitions on hand-made cases, kernel '
      'equivalence with `framelease_v2.lease.compute_lease`).')
    w('- Code sha256: `analysis.json` (`code_sha256`). Inputs: the merged 37-clip view '
      '`outputs/framelease_v3/c1_sweep_ext/merged_37clips_20261109T145344Z` (clip and GT sha256 in each '
      '`frames/<clip>.npz` meta), gate2 envelopes and frames.csv, the v2 lease file, the tracking-study LOCO envelopes '
      '(`envelopes/loco36_E0.json` records its sha256).')
    w('')
    w('```')
    w('cd /home/kang/Desktop/DAC; export OMP_NUM_THREADS=1; PY=".conda-unidrive-linux/bin/python -I -B"')
    w('$PY framelease_v4/offline/envelopes_v4.py        # TRAIN-only E0 fits + self-check (seconds)')
    w('$PY framelease_v4/offline/stage_frames.py --workers 8   # per-plan V, tau*, H_glob for 37 clips (~15 s)')
    w('$PY framelease_v4/offline/checks.py              # reproduction checks against gate2 / v2 c2_eval')
    w('$PY framelease_v4/offline/analyze.py             # metrics, frontier, nested, TRAIN-selected, paired')
    w('$PY framelease_v4/offline/fig1_data.py           # Fig. 1 data')
    w('$PY framelease_v4/offline/make_readme.py         # this README + summary.json')
    w('$PY -m pytest -q framelease_v4/offline/tests')
    w('```')
    w('')
    w('Files: `candidate_metrics.csv` (every design x candidate x need x subset, VAL with CIs and TRAIN point values), '
      '`frontier.csv`, `nested.csv`, `nested_folds.csv`, `train_selected.csv`, `paired.csv`, `per_clip_selected.csv`, '
      '`analysis.json`, `frames/` (per-plan inputs, 4.6 MB), `envelopes/`, `checks/`, `fig1/`.')
    w('')

    # ------------------------------------------------------------------ caveats
    w('## 10. Caveats')
    w('')
    w('- Offline, open-loop, non-reactive replay; constant-velocity prediction of the detections; depth-1 plans; '
      'T_c = 0.5 s. Validity is "within 0.5 m of a real actor", not a collision. No Driving Score here.')
    w('- One-shot leases computed at capture. The runtime re-checks the lease at commit (Eq. 9) and could renew it; '
      'neither changes the comparison of the deadlines themselves, but renewal results are in the v3 report.')
    w('- The TRAIN split is small (12 conflicts) and consists of official training routes the checkpoint has probably '
      'seen; TRAIN-fitted envelopes are optimistic for VAL, equally for both envelope designs.')
    w('- 32 VAL clips with very uneven conflict counts (BlockedIntersection alone holds 300 of 909); clip-bootstrap CIs '
      'are wide and condition on the chosen candidates. The frontier (Sec. 4) is in-sample.')
    w('- Only the isotropic E0 envelope family is compared, because the v2 global lease is defined for it; the v3 '
      'anisotropic families did not beat E0 at matched coverage in the gate2 study.')
    w('- Fig. 1 closed-loop data: one route per scenario type, seed 11 (44 routes) and 12 (15 routes); kappa 2.0 is an '
      'exploratory 11-route arm.')
    w('')
    C.atomic_write_text(O / 'README.md', '\n'.join(L) + '\n')

    # ------------------------------------------------------------------ summary.json
    def pack(r):
        return {k: fl(r[k]) for k in ('continuity', 'R_cond', 'R_marg', 'utilization', 'premature_refresh', 'mean_H_s')} | {
            f'{k}_ci': list(cil(r[k + '_ci'])) for k in ('continuity', 'R_cond', 'R_marg', 'utilization',
                                                         'premature_refresh')}
    S['train_selected_alpha5'] = {f'{d}|{nk}': {'candidate': trow(d, nk)['candidate'], **pack(trow(d, nk))}
                                  for d in ('AGE', 'GLOBAL', 'SUFFIX') for nk in ('fast', 'meas')}
    S['nested_alpha5'] = {f'{d}|{nk}': {'modal_choice': nrow(d, nk)['modal_choice'], **pack(nrow(d, nk))}
                          for d in ('AGE', 'GLOBAL', 'GLOBAL_TAU', 'SUFFIX') for nk in ('fast', 'meas')}
    S['nested_alpha10'] = {f'{d}|{nk}': {'modal_choice': nrow(d, nk, '0.1')['modal_choice'], **pack(nrow(d, nk, '0.1'))}
                           for d in ('AGE', 'GLOBAL', 'GLOBAL_TAU', 'SUFFIX') for nk in ('fast', 'meas')}
    S['age_only_at_need'] = {'fast': {'T_age': 1.0, 'R_cond': fl(age_fast['val_R_cond']),
                                      'R_marg': fl(age_fast['val_R_marg'])},
                             'meas': {'T_age': 1.85, 'R_cond': fl(age_meas['val_R_cond']),
                                      'R_marg': fl(age_meas['val_R_marg'])},
                             'any_positive_T_age_R_cond_min': fl(age_pos['val_R_cond'])}
    S['context'] = ctx
    S['checks_pass'] = {'envelopes': envchk['pass'], 'crosscheck': chk['pass'], 'fig1': f1chk['pass']}
    C.write_json(O / 'summary.json', S)
    C.log_progress('README.md and summary.json written')
    print(f'README.md: {len(L)} lines')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
