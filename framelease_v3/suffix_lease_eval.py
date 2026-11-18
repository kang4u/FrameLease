#!/usr/bin/env python3
"""Gate 2 (offline, CPU only): the outline's suffix-aligned validity lease on UniDriveVLA replay data.

    cd /home/kang/Desktop/DAC
    OMP_NUM_THREADS=1 .conda-unidrive-linux/bin/python -I -B framelease_v3/suffix_lease_eval.py --run-name <name>

No model, no GPU, no CARLA. Inputs are read-only: the merged 20-clip C1 depth sweep (model detections, scores, labels,
plan candidates; ground truth for calibration and scoring), the existing envelope parameters and the existing
c2_eval frames.csv (reproduction check only). framelease_v2 modules are imported read-only.

Lease (FrameLease 1109 outline, Sec. III-A)
-------------------------------------------
For VAL frame k (observation time t_k), depth d (plan = candidates[k, d-1], 6 waypoints at 0.5 ... 3.0 s, so
T_pred = 3.0 s) and every relevant detection j (vehicle / pedestrian, score >= 0.1; detections with
0.1 <= score < 0.3 count as real, i.e. lease.py's low_conf_mode='cap'), on the 0.05 s grid tau in [0, T_pred]:
  E(tau)     ego footprint following the plan (lease.py geometry);  R_j(tau) detected box moved at its own velocity;
  cm_j(tau)  conservative margin:  E0: dist(E, R_j) - d_safe - B_c(tau)                (disk inflation)
                                   E1/E2: dist(E, R_j (+) Rect(B_lon(tau), B_lat(tau))) - d_safe  (rectangle
                                   inflation in the detection's heading frame, exact polygon distance)
  M(Delta) = min_{tau in [Delta, Delta+T_c]} min_j cm_j(tau)                                 Eq. (1)
  H = inf({Delta in [0, Hbar] : M(Delta) <= delta} U {Hbar}),  Hbar = max(0, T_pred - T_c)    Eq. (2)
Because every envelope here depends only on tau (time since observation), H = clip(tau* - T_c, 0, Hbar) with
tau* = first tau at which min_j cm_j(tau) <= delta (T_pred if never). tau* is the exact first crossing of the
per-agent margins, linearly interpolated between grid points (E0: linear clearance minus the exact quadratic bound,
lease.py's time-resolved mode). Self-test (i) checks the closed form against the literal Eq. (1)-(2).
delta = 0.2 m on top of d_safe = 0.5 m. The only cap is Hbar (the old 2.0 s h_max is not applied).
Invalid plan or non-finite relevant detection: H = 0. No relevant detection: H = Hbar.

Realized validity (ground truth, scoring only)
----------------------------------------------
V = c2_eval.observed_validity: first tau in (0, T_pred] at which the plan's ego footprint comes within d_safe of the
REALIZED footprint of any GT vehicle / walker (non-reactive replay), censored at T_pred.
V_suf = clip(V - T_c, 0, Hbar) (censored V -> Hbar). Over-estimation: H > V_suf + 1e-6.
Continuous operation without fallback needs H >= need_d = 2 L_rel(d) + 0.05 s (L_rel = release latency p50:
0.896 s depth 1, 1.027 s depth 10).

Protocols: LOCO = for each held-out VAL clip the envelope is calibrated on the other 19 clips; ORIG = calibrated on
the 5 TRAIN clips. The evaluated clip never enters its own calibration.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import csv  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
import platform  # noqa: E402
import time  # noqa: E402
from collections import Counter, defaultdict  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from multiprocessing import get_context  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v2.c2_eval import detection_status, observed_validity  # noqa: E402
from framelease_v2.calibration import (EXTRA_VAL_CLIPS, TRAIN_CLIPS, VAL_CLIPS, SweepClip, clean_json,  # noqa: E402
                                       dets_world, gt_frame, sha256_file, write_csv, write_json)
from framelease_v2.geometry import (box_corners, convex_distance, first_crossing_time, se2_apply,  # noqa: E402
                                    time_grid)
from framelease_v2.lease import (EgoShape, LeaseParams, agent_leases, ego_corners_along_plan,  # noqa: E402
                                 lease_geometry, load_ego_shape, load_lease_params)
from framelease_v3 import envelopes as envmod  # noqa: E402
from framelease_v3.envelopes import (GROUP_ID, GROUPS, OLD_E0_D_GRID_S, aniso_inside, clip_samples,  # noqa: E402
                                     containment_residual, coverage_summary, env_to_json, fit_aniso, fit_iso,
                                     iso_bound, iso_inside, pool_samples, speed_bin)

SWEEP = ROOT / 'outputs/framelease_v2/c1_sweep/merged_20clips_20261108T0052'
OLD_PARAMS = ROOT / 'outputs/framelease_v2/c2_calibration/full_20261107T045343Z/lease_params_q95_envelope.json'
OLD_EVAL = ROOT / 'outputs/framelease_v2/c2_eval/merged20_q95_envelope'
OUT_ROOT = ROOT / 'outputs/framelease_v3/gate2_offline'
T_PRED = 3.0
DT = 0.05
D_SAFE = 0.5
DELTA = 0.2
SCORE_THRESHOLD = 0.3
LOW_SCORE_FLOOR = 0.1
WARMUP_STEPS = 5
GATE_M = 2.0
T_CS = (0.3, 0.5, 1.0)
DEPTHS = (1, 10)
L_REL = {1: 0.896, 10: 1.027}         # C1_RESULTS.md Sec. 1, release latency p50 (s)
OVERHEAD_S = 0.05
NEED = {d: 2.0 * L_REL[d] + OVERHEAD_S for d in DEPTHS}
REFINE_QUANTUM_S = 0.0146
QUANTILES = (0.80, 0.90, 0.95, 0.99, 0.995)
OLD_CAP_S = 2.0
OVER_EPS = 1e-6
PAD_M = 5.0                            # exact polygon distances where the centre lower bound is within d_safe+delta+PAD
KEY_CONFIGS = ('E0orig_q95_ORIG', 'E0_q95_LOCO', 'E1_q95_LOCO', 'E2_q95_LOCO', 'E0_q80_LOCO', 'E1_q80_LOCO',
               'E2_q80_LOCO', 'B0_q0_NONE')
SELFTEST_PER_MILLE = 90                # deterministic ~9% sample of (clip, frame, depth) cases for self-test (i)
GATE = {'protocol': 'LOCO', 'T_c': 0.5, 'depth': 1, 'pass_continuous': 0.85, 'marginal_continuous': 0.70,
        'max_over_rate': 0.02, 'max_over_upper95': 0.05}


def qtag(q):
    s = f'{q * 100:.1f}'.rstrip('0').rstrip('.')
    return s


def cfg_key(family, q, protocol):
    return f'{family}_q{qtag(q)}_{protocol}'


def parse_key(key):
    fam, q, prot = key.split('_')
    return fam, float(q[1:]) / 100.0, prot


def stable_pick(clip, frame_idx, depth, per_mille=SELFTEST_PER_MILLE):
    h = int(hashlib.md5(f'{clip}|{int(frame_idx)}|{int(depth)}'.encode()).hexdigest(), 16)
    return (h % 1000) < per_mille


def base_params():
    return LeaseParams(d_safe_m=D_SAFE, reserve_m=DELTA, h_max_s=T_PRED, score_threshold=SCORE_THRESHOLD,
                       horizon_s=T_PRED, dt_s=DT, low_score_floor=LOW_SCORE_FLOOR, low_conf_mode='cap',
                       relevant_groups=('vehicle', 'pedestrian'), margin_mode='time_resolved').validate()


def iso_params(env):
    d = base_params().to_dict()
    for name in ('sigma_m', 'vbar_mps', 'abar_mps2'):
        v = {g: float(env[name][g]) for g in GROUPS}
        v['other'] = max(v.values())
        d[name] = v
    return LeaseParams.from_dict(d)


# ----------------------------------------------------------------------------- lease kernels

def iso_agent_tau(geom, prm):
    """Per-agent first crossing tau*_j (capped at T_pred) for an isotropic quadratic envelope (lease.py math)."""
    return agent_leases(geom, prm, [DELTA], 'time_resolved')[0]


def aniso_margins(geom, det7, tables, tau, pad=PAD_M):
    """Conservative margins cm (C, N, M) = dist(E, inflated box) - d_safe for C stacked anisotropic tables.

    Exact polygon distances wherever a centre-distance lower bound is within d_safe + delta + pad; elsewhere the
    lower bound itself (it exceeds d_safe + delta + pad there, so it can never cause a crossing)."""
    idx = geom.index
    d = np.asarray(det7, dtype=float)[idx]
    gid = np.array([GROUP_ID[g] for g in geom.group], dtype=int)
    b = speed_bin(np.hypot(d[:, 5], d[:, 6]))
    B = tables[:, gid, b]                                                          # (C, N, M, 2)
    C, N, M = B.shape[0], len(idx), len(tau)
    cen = d[:, None, 0:2] + tau[None, :, None] * d[:, None, 5:7]                   # (N, M, 2)
    hl = 0.5 * np.abs(d[:, 2])[None, :, None] + B[..., 0]                          # (C, N, M)
    hw = 0.5 * np.abs(d[:, 3])[None, :, None] + B[..., 1]
    E = geom.ego_corners                                                           # (M, 4, 2)
    ego_c = E.mean(axis=1)                                                         # (M, 2)
    ego_r = np.max(np.linalg.norm(E - ego_c[:, None, :], axis=-1), axis=-1)        # (M,)
    cd = np.linalg.norm(cen - ego_c[None], axis=-1)                                # (N, M)
    lb = cd[None] - ego_r[None, None] - np.hypot(hl, hw)                           # (C, N, M)
    dist = np.maximum(lb, 0.0)
    near = lb <= D_SAFE + DELTA + pad
    if near.any():
        ci, ni, mi = np.nonzero(near)
        R = box_corners(cen[ni, mi], d[ni, 4], hl[ci, ni, mi], hw[ci, ni, mi])     # (K, 4, 2)
        dist[ci, ni, mi] = convex_distance(E[mi], R)
    return dist - D_SAFE


def tau_star_from_agents(per_agent, status, n_agents):
    """tau* (min over agents, capped at T_pred) and the binding agent position."""
    if status != 'ok':
        return 0.0, None
    if n_agents == 0:
        return T_PRED, None
    j = int(np.argmin(per_agent))
    return float(min(per_agent[j], T_PRED)), j


def lease_H(tau_star, T_c):
    hbar = max(0.0, T_PRED - T_c)
    return np.clip(np.asarray(tau_star, dtype=float) - T_c, 0.0, hbar)


def literal_H(cm_min, dt, T_c, T_pred=T_PRED):
    """Literal Eq. (1)-(2) on a uniform grid: returns the grid index of H (Delta = i*dt)."""
    n_c = int(round(T_c / dt))
    n_bar = max(0, int(round((T_pred - T_c) / dt)))
    win = np.lib.stride_tricks.sliding_window_view(cm_min, n_c + 1)[:n_bar + 1].min(axis=1)   # M(Delta_i)
    bad = win <= DELTA
    return int(np.argmax(bad)) if bad.any() else n_bar


def closed_H(cm_min, dt, T_c, T_pred=T_PRED):
    """Closed form on the same grid: clip(tau* - T_c, 0, Hbar) in grid units."""
    n_c = int(round(T_c / dt))
    n_bar = max(0, int(round((T_pred - T_c) / dt)))
    bad = cm_min <= DELTA
    m = int(np.argmax(bad)) if bad.any() else int(round(T_pred / dt))
    return int(min(max(m - n_c, 0), n_bar))


# ----------------------------------------------------------------------------- worker

_CLIP = {}


def _clip(name):
    if name not in _CLIP:
        _CLIP.clear()
        _CLIP[name] = SweepClip(SWEEP, name)
    return _CLIP[name]


def det_gt_flags(clip, k, gate_m=GATE_M):
    """Per detection of frame k: True if a GT actor of the same group lies within gate_m of its centre (diagnostic)."""
    dw = dets_world(clip, k)
    gt = gt_frame(clip, k)
    out = np.zeros(len(dw['score']), dtype=bool)
    for g in ('vehicle', 'pedestrian'):
        di = np.flatnonzero(dw['group'] == g)
        gi = np.flatnonzero(gt['group'] == g)
        if len(di) and len(gi):
            D = np.linalg.norm(dw['xy'][di][:, None] - gt['xy'][gi][None], axis=-1)
            out[di] = D.min(axis=1) <= gate_m
    return out


def eval_unit(task):
    name, ks, iso_cfgs, aniso_keys, aniso_tables, ego_dict = task
    t0 = time.perf_counter()
    clip = _clip(name)
    ego = EgoShape.from_dict(ego_dict)
    tau = time_grid(T_PRED, DT)
    bp = base_params()
    iso_prm = {key: iso_params(env) for key, env in iso_cfgs}
    iso_env = dict(iso_cfgs)
    tables = np.asarray(aniso_tables, dtype=float)
    ego_radius = float(np.hypot(ego.half_length_m, ego.half_width_m))
    tau_f = np.linspace(0.0, T_PRED, int(round(T_PRED / (DT / 20))) + 1)
    rows, skipped, st = [], Counter(), []
    for k in ks:
        if clip.run_step[k] < WARMUP_STEPS:
            skipped['warmup'] += 1
            continue
        t_k = float(clip.t[k])
        if t_k + T_PRED > clip.gt.t[-1] + 1e-9:
            skipped['insufficient_future_gt'] += 1
            continue
        gt_state = clip.gt.actors_at(t_k + tau)
        det7, score, label = clip.dets(k)
        pose = clip.poses[k]
        flags = det_gt_flags(clip, k)
        status = None
        for d in DEPTHS:
            plan = clip.cand[k, d - 1]
            if not np.isfinite(plan).all():
                skipped[f'nonfinite_plan_depth{d}'] += 1
                continue
            geom = lease_geometry(plan, det7, score, label, ego, bp)
            val = observed_validity(se2_apply(pose, geom.ego_corners), tau, gt_state, D_SAFE, ego_radius)
            row = {'clip': name, 'frame_idx': int(clip.frame_idx[k]), 'depth': d, 't_s': t_k, 'V_s': val['V'],
                   'censored': int(val['censored']), 'v0': int(val['v0']), 'lease_status': geom.status,
                   'n_relevant': int(len(geom.index)), 'n_confident': int(geom.confident.sum())}
            b_col = val['binding_col']
            if b_col is not None:
                if status is None:
                    status = detection_status(clip, k, bp, GATE_M)
                g_row = int(clip.gt_row[k])
                row['V_binding_group'] = str(clip.gt.group[b_col])
                row['V_binding_status'] = status.get(b_col, 'undetected' if clip.gt.present[g_row, b_col]
                                                     else 'absent_at_capture')
            else:
                row['V_binding_group'] = None
                row['V_binding_status'] = None
            N = len(geom.index)
            ok = geom.status == 'ok'
            per_agent = {}
            for key, prm in iso_prm.items():
                pa = iso_agent_tau(geom, prm) if (ok and N) else np.zeros(0)
                per_agent[key] = pa
            cm_a = aniso_margins(geom, det7, tables, tau) if (ok and N and len(aniso_keys)) else None
            if cm_a is not None:
                cross = np.minimum(first_crossing_time(tau, cm_a - DELTA), T_PRED)   # (C, N)
                for c, key in enumerate(aniso_keys):
                    per_agent[key] = cross[c]
            else:
                for key in aniso_keys:
                    per_agent[key] = np.zeros(0)
            for key, pa in per_agent.items():
                ts, j = tau_star_from_agents(pa, geom.status, N)
                row[f'tau_star__{key}'] = ts
                if key in KEY_CONFIGS:
                    row[f'bindxy__{key}'] = None
                    if j is None:
                        row[f'bind__{key}'] = 'none' if geom.status == 'ok' else geom.status
                    else:
                        row[f'bindxy__{key}'] = (float(det7[int(geom.index[j]), 0]), float(det7[int(geom.index[j]), 1]))
                        di = int(geom.index[j])
                        grp = str(geom.group[j])
                        sb = 'static' if np.hypot(det7[di, 5], det7[di, 6]) < envmod.STATIC_SPEED_MPS else 'moving'
                        conf = 'conf' if score[di] >= SCORE_THRESHOLD else 'lowconf'
                        tp = 'gt' if flags[di] else 'nogt'
                        row[f'bind__{key}'] = f'{grp}/{sb}/{conf}/{tp}'
            rows.append(row)
            # ---------------- self-test (i): closed form versus literal Eq. (1)-(2), on the grid and a 20x finer grid
            if ok and stable_pick(name, clip.frame_idx[k], d):
                rec = {'clip': name, 'frame_idx': int(clip.frame_idx[k]), 'depth': d, 'n_agents': N,
                       'grid_mismatch': 0, 'fine_mismatch': 0, 'checks': 0, 'max_eval_vs_fine_s': 0.0,
                       'min_eval_vs_fine_s': 0.0}
                if N == 0:
                    cms = {key: np.full((1, len(tau)), np.inf) for key in per_agent}
                    cmf = {key: np.full((1, len(tau_f)), np.inf) for key in per_agent}
                else:
                    cms, cmf = {}, {}
                    for key in iso_prm:
                        env = iso_env[key]
                        B = np.stack([iso_bound(env, g, tau) for g in geom.group])           # (N, M)
                        Bf = np.stack([iso_bound(env, g, tau_f) for g in geom.group])
                        cms[key] = geom.clearance - B
                        cf = np.stack([np.interp(tau_f, tau, c) for c in geom.clearance])
                        cmf[key] = cf - Bf
                    for c, key in enumerate(aniso_keys):
                        cms[key] = cm_a[c]
                        cmf[key] = np.stack([np.interp(tau_f, tau, x) for x in cm_a[c]])
                for key in per_agent:
                    g_min = cms[key].min(axis=0)
                    f_min = cmf[key].min(axis=0)
                    for T_c in T_CS:
                        rec['checks'] += 1
                        if literal_H(g_min, DT, T_c) != closed_H(g_min, DT, T_c):
                            rec['grid_mismatch'] += 1
                        lf = literal_H(f_min, DT / 20, T_c)
                        if lf != closed_H(f_min, DT / 20, T_c):
                            rec['fine_mismatch'] += 1
                        H_eval = float(lease_H(row[f'tau_star__{key}'], T_c))
                        diff = lf * (DT / 20) - H_eval
                        rec['max_eval_vs_fine_s'] = max(rec['max_eval_vs_fine_s'], diff)
                        rec['min_eval_vs_fine_s'] = min(rec['min_eval_vs_fine_s'], diff)
                st.append(rec)
    return {'clip': name, 'rows': rows, 'skipped': dict(skipped), 'selftest': st, 'seconds': time.perf_counter() - t0}


def samples_job(name):
    tau = time_grid(T_PRED, DT)
    clip = SweepClip(SWEEP, name)
    S = clip_samples(clip, tau, gate_m=GATE_M, score_threshold=SCORE_THRESHOLD, warmup_steps=WARMUP_STEPS)
    return name, S, clip.split, clip.sha256, clip.gt_sha256, len(clip)


# ----------------------------------------------------------------------------- statistics

def boot_weights(C, n_boot, seed):
    rng = np.random.default_rng(seed)
    return np.vstack([np.ones(C), rng.multinomial(C, np.full(C, 1.0 / C), size=n_boot)]).astype(float)


def ci95(v):
    v = np.asarray(v, dtype=float)
    v = v[np.isfinite(v)]
    if not len(v):
        return [None, None]
    return [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))]


def ratio(num_c, den_c, W):
    num = W @ num_c
    den = W @ den_c
    with np.errstate(invalid='ignore', divide='ignore'):
        r = num / den
    return float(r[0]) if np.isfinite(r[0]) else None, ci95(r[1:])


def weighted_lower_median(values, cid, W):
    order = np.argsort(values, kind='stable')
    v = values[order]
    w = W[:, cid[order]]
    cw = np.cumsum(w, axis=1)
    idx = np.argmax(cw >= 0.5 * cw[:, -1:], axis=1)
    return v[idx]


def metrics(H, Vsuf, conflict, cid, C, W, need):
    n_c = np.bincount(cid, minlength=C).astype(float)
    over = H > Vsuf + OVER_EPS
    nconf_c = np.bincount(cid, weights=conflict.astype(float), minlength=C)
    out = {}
    for name, x, den in (('continuous_fraction', H >= need - 1e-9, n_c),
                         ('overestimation_rate', over, n_c),
                         ('overestimation_rate_conflict', over & conflict, nconf_c),
                         ('mean_H_s', H, n_c),
                         ('P_H_zero', H <= 1e-9, n_c),
                         ('oracle_continuous_fraction', Vsuf >= need - 1e-9, n_c),
                         ('P_both_proxy', H >= need + REFINE_QUANTUM_S - 1e-9, n_c)):
        num = np.bincount(cid, weights=np.asarray(x, dtype=float), minlength=C)
        est, ci = ratio(num, den, W)
        out[name] = est
        out[name + '_ci95'] = ci
    med_b = weighted_lower_median(H, cid, W)
    out['median_H_s'] = float(np.median(H)) if len(H) else None
    out['median_H_s_ci95'] = ci95(med_b[1:])
    out['n_frames'] = int(len(H))
    out['n_conflict'] = int(conflict.sum())
    out['n_clips'] = int((n_c > 0).sum())
    return out


# ----------------------------------------------------------------------------- self-tests (iii) and helpers

def selftest_inflation(ego):
    """(iii) a static box displaced laterally / longitudinally gives the analytic distance after rectangle inflation."""
    tau = time_grid(T_PRED, DT)
    bp = base_params()
    plan = np.zeros((6, 2))
    _, _, _, E = ego_corners_along_plan(plan, ego, bp)
    ex = E[0, :, 0]
    ey = E[0, :, 1]
    ego_xmin, ego_xmax, ego_ymin, ego_ymax = ex.min(), ex.max(), ey.min(), ey.max()
    G, NB, M = len(GROUPS), len(envmod.BIN_NAMES), len(tau)
    B_lon, B_lat = 3.0, 0.5
    table = np.zeros((1, G, NB, M, 2))
    table[..., 0] = B_lon
    table[..., 1] = B_lat
    cases = []
    hl, hw = 2.3, 0.9
    for off in (2.0, 3.0, 4.0, 6.5, 10.0):
        # agent parallel to the ego (heading +y in the LiDAR frame), displaced to the right: lateral = x
        cases.append(('parallel_lateral', off, [off, ego.center_offset_xy[1], 2 * hl, 2 * hw, math.pi / 2, 0.0, 0.0],
                      max(0.0, (off - (hw + B_lat)) - ego_xmax)))
        # agent perpendicular (heading +x), displaced to the right: its longitudinal axis is x
        cases.append(('perpendicular_lateral', off + 6.0, [off + 6.0, ego.center_offset_xy[1], 2 * hl, 2 * hw, 0.0, 0.0, 0.0],
                      max(0.0, (off + 6.0 - (hl + B_lon)) - ego_xmax)))
        # agent ahead, same heading: longitudinal gap
        cases.append(('parallel_ahead', off + 6.0, [0.0, off + 6.0, 2 * hl, 2 * hw, math.pi / 2, 0.0, 0.0],
                      max(0.0, (off + 6.0 - (hl + B_lon)) - ego_ymax)))
    errs = []
    lb_ok = []
    detail = []
    for kind, off, det, expect in cases:
        geom = lease_geometry(plan, np.array([det]), np.array([0.9]), np.array([0]), ego, bp)
        cm = aniso_margins(geom, np.array([det]), table, tau, pad=1e9)[0, 0]      # exact everywhere
        got = float(cm[0] + D_SAFE)
        lbv = float(aniso_margins(geom, np.array([det]), table, tau)[0, 0][0] + D_SAFE)   # default pruning
        errs.append(abs(got - expect))
        lb_ok.append(lbv <= got + 1e-9 and (abs(lbv - got) < 1e-12 or lbv > D_SAFE + DELTA + PAD_M))
        detail.append({'case': kind, 'offset_m': off, 'expected_m': expect, 'got_m': got, 'pruned_value_m': lbv})
    # residual decomposition: a GT box displaced by (a, b) in the detection frame with the same size and yaw
    res_err = []
    for yaw in (0.0, 0.7, -2.1):
        for a, b in ((0.0, 0.8), (1.5, 0.0), (-2.0, -0.4)):
            u = np.array([math.cos(yaw), math.sin(yaw)])
            n = np.array([-math.sin(yaw), math.cos(yaw)])
            c0 = np.array([3.0, -1.0])
            gtc = c0 + a * u + b * n
            corners = box_corners(gtc, yaw, hl, hw)
            lon, lat = containment_residual(corners[None], c0[None], np.array([yaw]), np.array([hl]), np.array([hw]))
            res_err.append(abs(float(lon[0]) - abs(a)) + abs(float(lat[0]) - abs(b)))
    return {'n_cases': len(cases), 'max_abs_err_m': float(max(errs)), 'pass': bool(max(errs) < 1e-9 and all(lb_ok)),
            'pruned_values_are_valid_lower_bounds': bool(all(lb_ok)),
            'cases': detail, 'residual_decomposition_max_err_m': float(max(res_err)),
            'residual_decomposition_pass': bool(max(res_err) < 1e-9)}


def residual_tail(samples, names, tau, t_s=2.0):
    """Descriptive calibration-sample statistics of the vehicle CV residual at tau = t_s (all 20 clips pooled)."""
    S = pool_samples(samples, names)
    m = int(round(t_s / (tau[1] - tau[0])))
    veh = S['group'] == GROUP_ID['vehicle']
    ok = veh & np.isfinite(S['lon'][:, m])
    lon, lat, iso, ve = S['lon'][:, m], S['lat'][:, m], S['iso'][:, m], S['vel_err']
    tail = ok & (lon > 7.0)
    good = ok & (ve < 1.0)
    bad = ok & (ve >= 1.0)
    out = {'tau_s': t_s, 'n_vehicle_pairs': int(ok.sum()),
           'lon_q95_m': float(np.quantile(lon[ok], 0.95)), 'lat_q95_m': float(np.quantile(lat[ok], 0.95)),
           'iso_q95_m': float(np.quantile(iso[ok], 0.95)), 'frac_lon_gt_7m': float(tail.sum() / ok.sum()),
           'tail_lon_gt_7m_median_vel_err_mps': float(np.nanmedian(ve[tail])),
           'tail_lon_gt_7m_frac_detected_static': float(np.mean(S['speed'][tail] < envmod.STATIC_SPEED_MPS)),
           'lon_q95_m_if_vel_err_lt_1mps': float(np.quantile(lon[good], 0.95)), 'n_vel_err_lt_1mps': int(good.sum()),
           'lon_q95_m_if_vel_err_ge_1mps': float(np.quantile(lon[bad], 0.95)), 'n_vel_err_ge_1mps': int(bad.sum()),
           'by_motion_bin': {}, 'frac_lon_gt_7m_by_clip': {}}
    for b, bn in enumerate(envmod.BIN_NAMES):
        sel = ok & (speed_bin(S['speed']) == b)
        out['by_motion_bin'][bn] = {'n': int(sel.sum()), 'lon_q95_m': float(np.quantile(lon[sel], 0.95)),
                                    'lat_q95_m': float(np.quantile(lat[sel], 0.95))}
    for c in names:
        Sc = samples[c]
        okc = (Sc['group'] == GROUP_ID['vehicle']) & np.isfinite(Sc['lon'][:, m])
        if okc.any():
            out['frac_lon_gt_7m_by_clip'][c] = {'n': int(okc.sum()), 'frac': float(np.mean(Sc['lon'][okc, m] > 7.0))}
    return out


def rel_position(xy, ego):
    """'ahead' / 'behind' / 'alongside' of the capture-time ego footprint (LiDAR frame, y forward), by box centre."""
    if xy is None:
        return 'none'
    front = ego.center_offset_xy[1] + ego.half_length_m
    rear = ego.center_offset_xy[1] - ego.half_length_m
    return 'ahead' if xy[1] > front else ('behind' if xy[1] < rear else 'alongside')


def sha_of(paths):
    return {str(p): sha256_file(p) for p in paths}


def fmt_ci(est, ci, pct=True, nd=1):
    if est is None:
        return 'n/a'
    if pct:
        s = f'{100 * est:.{nd}f}%'
        if ci and ci[0] is not None:
            s += f' [{100 * ci[0]:.{nd}f}, {100 * ci[1]:.{nd}f}]'
        return s
    s = f'{est:.2f}'
    if ci and ci[0] is not None:
        s += f' [{ci[0]:.2f}, {ci[1]:.2f}]'
    return s


# ----------------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--run-name', default='')
    ap.add_argument('--workers', type=int, default=max(1, min(14, (os.cpu_count() or 2) - 2)))
    ap.add_argument('--n-boot', type=int, default=2000)
    ap.add_argument('--seed', type=int, default=20261109)
    ap.add_argument('--chunk', type=int, default=24, help='frames per work unit')
    ap.add_argument('--frame-stride', type=int, default=1, help='deterministic subsampling of VAL frames (1 = all)')
    ap.add_argument('--clips', default='', help='comma list of VAL clips to evaluate (default: the 15 of merged20)')
    ap.add_argument('--max-frames', type=int, default=0, help='smoke test: at most this many frames per clip')
    args = ap.parse_args(argv)
    t_start = time.time()
    started = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    run_name = args.run_name or time.strftime('run_%Y%m%dT%H%M%S')
    out = OUT_ROOT / run_name
    out.mkdir(parents=True, exist_ok=False)
    (out / 'envelopes').mkdir()
    log_f = open(out / 'run.log', 'w', encoding='utf-8')

    def log(*a):
        msg = ' '.join(str(x) for x in a)
        print(msg, flush=True)
        log_f.write(msg + '\n')
        log_f.flush()

    old_cfg = json.loads((OLD_EVAL / 'config.json').read_text(encoding='utf-8'))
    if Path(old_cfg['sweep']).resolve() != SWEEP.resolve():
        raise SystemExit(f'sweep mismatch: {old_cfg["sweep"]}')
    val_all = list(old_cfg['clips'])
    if sorted(val_all) != sorted(VAL_CLIPS + EXTRA_VAL_CLIPS):
        raise SystemExit('merged20 VAL clip list differs from VAL_CLIPS + EXTRA_VAL_CLIPS')
    val_clips = [c for c in args.clips.split(',') if c] or val_all
    train_clips = list(TRAIN_CLIPS)
    all_clips = sorted(set(val_all) | set(train_clips))
    if len(all_clips) != 20:
        raise SystemExit(f'expected 20 clips, got {len(all_clips)}')
    tau = time_grid(T_PRED, DT)
    ego = load_ego_shape(OLD_PARAMS)
    if ego.to_dict() != old_cfg['ego_shape']:
        log('[warn] ego shape differs from merged20 config')
    old_params = load_lease_params(OLD_PARAMS)
    log(f'[gate2] run {out}; VAL clips {len(val_clips)}; workers {args.workers}; need {NEED}')

    # ---------------------------------------------------------------- calibration samples (all 20 clips)
    ctx = get_context('fork')
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=ctx) as ex:
        res = list(ex.map(samples_job, all_clips))
    samples = {n: S for n, S, _, _, _, _ in res}
    clip_meta = {n: {'split': sp, 'npz_sha256': h, 'gt_sha256': hg, 'frames': F} for n, _, sp, h, hg, F in res}
    for n in all_clips:
        want = 'train' if n in train_clips else 'val'
        if clip_meta[n]['split'] != want:
            raise SystemExit(f'{n}: split {clip_meta[n]["split"]} != {want}')
    log(f'[gate2] calibration samples: {sum(len(S["group"]) for S in samples.values())} matched pairs from '
        f'{len(all_clips)} clips in {time.time() - t0:.1f}s')

    # ---------------------------------------------------------------- envelopes
    t0 = time.time()
    folds = {'ORIG': train_clips}
    for h in val_all:
        folds[f'LOCO:{h}'] = [c for c in all_clips if c != h]
    env = {}          # (family, q, fold) -> envelope
    for fold, names in folds.items():
        if fold.startswith('LOCO:') and fold[5:] not in val_clips:
            continue
        S = pool_samples(samples, names)
        for q in QUANTILES:
            env[('E0', q, fold)] = fit_iso(S, q, tau)
            env[('E1', q, fold)] = fit_aniso(S, q, tau, motion_bins=False)
            env[('E2', q, fold)] = fit_aniso(S, q, tau, motion_bins=True)
    e0orig = {'kind': 'iso', 'q': 0.95, 'sigma_m': {g: old_params.sigma_m[g] for g in GROUPS},
              'vbar_mps': {g: old_params.vbar_mps[g] for g in GROUPS},
              'abar_mps2': {g: old_params.abar_mps2[g] for g in GROUPS}, 'd_grid_s': list(OLD_E0_D_GRID_S),
              'n_pairs': None, 'notes': [f'existing parameter file as-is: {OLD_PARAMS}']}
    zero_env = {'kind': 'iso', 'q': 0.0, 'sigma_m': {g: 0.0 for g in GROUPS}, 'vbar_mps': {g: 0.0 for g in GROUPS},
                'abar_mps2': {g: 0.0 for g in GROUPS}, 'd_grid_s': [], 'n_pairs': None,
                'notes': ['exploratory reference: no envelope (B = 0); not a gate candidate']}
    log(f'[gate2] {len(env)} envelopes fitted in {time.time() - t0:.1f}s')

    # self-test (iv): E0 ORIG with the old D grid reproduces the existing parameter file
    S_orig = pool_samples(samples, train_clips)
    rep = fit_iso(S_orig, 0.95, tau, d_grid_s=OLD_E0_D_GRID_S)
    st_iv = {name: {g: {'refit': rep[name][g], 'file': getattr(old_params, name)[g],
                        'abs_diff': abs(rep[name][g] - getattr(old_params, name)[g])} for g in GROUPS}
             for name in ('sigma_m', 'vbar_mps', 'abar_mps2')}
    st_iv_max = max(v['abs_diff'] for d in st_iv.values() for v in d.values())
    log(f'[gate2] self-test (iv) E0 ORIG refit vs existing file: max abs diff {st_iv_max:.3g}')

    # configs
    families = ('E0', 'E1', 'E2')
    # B0_q0_NONE: exploratory reference with NO envelope (CV prediction taken as exact); it is not a pre-specified
    # variant, is never calibrated and is excluded from the gate. It bounds what any envelope can reach.
    config_keys = (['E0orig_q95_ORIG'] + [cfg_key(f, q, p) for f in families for q in QUANTILES for p in ('LOCO', 'ORIG')]
                   + ['B0_q0_NONE'])
    iso_keys = [k for k in config_keys if parse_key(k)[0] in ('E0orig', 'E0', 'B0')]
    aniso_keys = [k for k in config_keys if parse_key(k)[0] in ('E1', 'E2')]

    def env_for(key, clip_name):
        fam, q, prot = parse_key(key)
        if fam == 'E0orig':
            return e0orig
        if fam == 'B0':
            return zero_env
        fold = 'ORIG' if prot == 'ORIG' else f'LOCO:{clip_name}'
        return env[(fam, q, fold)]

    # envelope parameter files and out-of-sample containment coverage
    cov = {}
    for key in config_keys:
        fam, q, prot = parse_key(key)
        if fam == 'E0orig':
            payload = {'protocol': 'ORIG (existing file, TRAIN clips)', 'envelope': env_to_json(e0orig, tau)}
            ins = [iso_inside(e0orig, samples[c], tau) for c in val_clips]
        elif fam == 'B0':
            payload = {'protocol': 'NONE (exploratory, no envelope)', 'envelope': env_to_json(zero_env, tau)}
            ins = [iso_inside(zero_env, samples[c], tau) for c in val_clips]
        elif prot == 'ORIG':
            e = env[(fam, q, 'ORIG')]
            payload = {'protocol': 'ORIG', 'calibration_clips': train_clips, 'envelope': env_to_json(e, tau)}
            ins = [(iso_inside(e, samples[c], tau) if fam == 'E0' else aniso_inside(e, samples[c])) for c in val_clips]
        else:
            payload = {'protocol': 'LOCO', 'folds': {}}
            ins = []
            for c in val_clips:
                e = env[(fam, q, f'LOCO:{c}')]
                payload['folds'][c] = {'calibration_clips': folds[f'LOCO:{c}'], 'envelope': env_to_json(e, tau)}
                ins.append(iso_inside(e, samples[c], tau) if fam == 'E0' else aniso_inside(e, samples[c]))
        write_json(out / 'envelopes' / f'{key}.json', payload)
        inside = np.concatenate([i[0] for i in ins])
        ok = np.concatenate([i[1] for i in ins])
        gid = np.concatenate([i[2] for i in ins])
        cov[key] = coverage_summary(inside, ok, gid, tau)

    # ---------------------------------------------------------------- evaluation
    ego_d = ego.to_dict()
    tasks = []
    for c in val_clips:
        F = clip_meta[c]['frames']
        ks = list(range(0, F, args.frame_stride))
        if args.max_frames:
            ks = ks[:args.max_frames]
        iso_cfgs = [(k, env_for(k, c)) for k in iso_keys]
        tables = np.stack([env_for(k, c)['table'] for k in aniso_keys]) if aniso_keys else np.zeros((0,))
        for i in range(0, len(ks), args.chunk):
            tasks.append((c, ks[i:i + args.chunk], iso_cfgs, aniso_keys, tables, ego_d))
    # large clips first for load balance
    tasks.sort(key=lambda t: -len(samples[t[0]]['group']) / max(1, clip_meta[t[0]]['frames']))
    t0 = time.time()
    results = []
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=ctx) as ex:
        for i, r in enumerate(ex.map(eval_unit, tasks)):
            results.append(r)
            if (i + 1) % 10 == 0 or i + 1 == len(tasks):
                log(f'[gate2] eval {i + 1}/{len(tasks)} units, {time.time() - t0:.0f}s')
    rows = [row for r in results for row in r['rows']]
    rows.sort(key=lambda r: (val_clips.index(r['clip']), r['frame_idx'], r['depth']))
    skipped = defaultdict(Counter)
    for r in results:
        skipped[r['clip']].update(r['skipped'])
    selftest_recs = [x for r in results for x in r['selftest']]
    log(f'[gate2] evaluated {len(rows)} (frame, depth) cases in {time.time() - t0:.0f}s')

    # ---------------------------------------------------------------- reproduction check against merged20 frames.csv
    old_rows = {(r['clip'], int(r['frame_idx']), int(r['depth'])): r
                for r in csv.DictReader(open(OLD_EVAL / 'frames.csv', newline='', encoding='utf-8'))
                if r['clip'] in val_clips}
    new_keys = {(r['clip'], r['frame_idx'], r['depth']) for r in rows}
    old_keys = set(old_rows)
    if args.frame_stride == 1 and not args.max_frames:
        same_set = new_keys == old_keys
    else:
        same_set = new_keys <= old_keys
    dH, dV, dG = [], [], []
    for r in rows:
        o = old_rows.get((r['clip'], r['frame_idx'], r['depth']))
        if o is None:
            continue
        mine = min(r['tau_star__E0orig_q95_ORIG'], OLD_CAP_S)        # T_c = 0, old cap 2.0 s
        dH.append(abs(mine - float(o['H_avl_time_resolved_s'])))
        dV.append(abs(r['V_s'] - float(o['V_s'])))
    dH, dV = np.asarray(dH), np.asarray(dV)
    repro = {'frame_set_identical_to_merged20': bool(same_set), 'n_compared': int(len(dH)),
             'n_new': len(new_keys), 'n_old': len(old_keys),
             'H_time_resolved_within_1e-3': float(np.mean(dH <= 1e-3)) if len(dH) else None,
             'H_time_resolved_max_abs_diff_s': float(dH.max()) if len(dH) else None,
             'V_within_1e-3': float(np.mean(dV <= 1e-3)) if len(dV) else None,
             'V_max_abs_diff_s': float(dV.max()) if len(dV) else None,
             'note': 'E0-orig (existing parameter file), T_c = 0, cap 2.0 s, versus frames.csv H_avl_time_resolved_s; '
                     'frames.csv stores 6 significant digits'}
    log(f'[gate2] reproduction: {json.dumps(clean_json(repro))}')

    # ---------------------------------------------------------------- metrics
    clip_index = {c: i for i, c in enumerate(val_clips)}
    C = len(val_clips)
    W = boot_weights(C, args.n_boot, args.seed)
    results_tab = {}
    per_clip_rows = []
    for d in DEPTHS:
        R = [r for r in rows if r['depth'] == d]
        if not R:
            continue
        cid = np.array([clip_index[r['clip']] for r in R])
        V = np.array([r['V_s'] for r in R])
        cens = np.array([r['censored'] for r in R], dtype=bool)
        conflict = ~cens
        for T_c in T_CS:
            hbar = max(0.0, T_PRED - T_c)
            Vsuf = np.where(cens, hbar, np.clip(V - T_c, 0.0, hbar))
            for key in config_keys:
                ts = np.array([r[f'tau_star__{key}'] for r in R])
                H = lease_H(ts, T_c)
                m = metrics(H, Vsuf, conflict, cid, C, W, NEED[d])
                results_tab[(key, T_c, d)] = m
                for c in range(C):
                    sel = cid == c
                    if not sel.any():
                        continue
                    Hc, Vc = H[sel], Vsuf[sel]
                    over = Hc > Vc + OVER_EPS
                    per_clip_rows.append({
                        'config': key, 'variant': parse_key(key)[0], 'quantile': parse_key(key)[1],
                        'protocol': parse_key(key)[2], 'T_c': T_c, 'depth': d, 'clip': val_clips[c],
                        'n': int(sel.sum()), 'n_conflict': int(conflict[sel].sum()),
                        'continuous_fraction': float(np.mean(Hc >= NEED[d] - 1e-9)),
                        'oracle_continuous_fraction': float(np.mean(Vc >= NEED[d] - 1e-9)),
                        'overestimation_rate': float(np.mean(over)),
                        'overestimation_rate_conflict': float(np.mean(over[conflict[sel]])) if conflict[sel].any() else None,
                        'n_overestimates': int(over.sum()),
                        'mean_H_s': float(np.mean(Hc)), 'median_H_s': float(np.median(Hc)),
                        'P_H_zero': float(np.mean(Hc <= 1e-9)),
                        'P_both_proxy': float(np.mean(Hc >= NEED[d] + REFINE_QUANTUM_S - 1e-9))})
    # old-reference rows straight from merged20 frames.csv (cap 2.0 s, T_c = 0 semantics)
    old_ref = {}
    for d in DEPTHS:
        o = [r for r in old_rows.values() if int(r['depth']) == d]
        if not o:
            continue
        Ht = np.array([float(r['H_avl_time_resolved_s']) for r in o])
        Hg = np.array([float(r['H_avl_s']) for r in o])
        Vo = np.array([float(r['V_s']) for r in o])
        old_ref[d] = {'n': len(o), 'time_resolved_at_cap_2s': float(np.mean(Ht >= OLD_CAP_S - 1e-9)),
                      'global_median_s': float(np.median(Hg)), 'global_P_H0': float(np.mean(Hg <= 0)),
                      'oracle_P_V_ge_2.35s': float(np.mean(Vo >= 2.35 - 1e-9)),
                      'oracle_P_V_ge_need_plus_0.5s': float(np.mean(Vo >= NEED[d] + 0.5 - 1e-9))}

    # ---------------------------------------------------------------- gate
    def gate_eval(depth):
        cands = []
        for key in config_keys:
            fam, q, prot = parse_key(key)
            if prot != GATE['protocol']:
                continue
            m = results_tab.get((key, GATE['T_c'], depth))
            if m is None:
                continue
            up = m['overestimation_rate_ci95'][1]
            risk_ok = (m['overestimation_rate'] is not None and m['overestimation_rate'] <= GATE['max_over_rate']
                       and up is not None and up <= GATE['max_over_upper95'])
            cands.append({'config': key, 'continuous_fraction': m['continuous_fraction'],
                          'continuous_fraction_ci95': m['continuous_fraction_ci95'],
                          'overestimation_rate': m['overestimation_rate'],
                          'overestimation_rate_ci95': m['overestimation_rate_ci95'], 'risk_ok': bool(risk_ok)})
        ok = [c for c in cands if c['risk_ok']]
        best = max(ok, key=lambda c: c['continuous_fraction']) if ok else None
        if best and best['continuous_fraction'] >= GATE['pass_continuous']:
            verdict = 'PASS'
        elif best and best['continuous_fraction'] >= GATE['marginal_continuous']:
            verdict = 'MARGINAL'
        else:
            verdict = 'FAIL'
        best_any = max(cands, key=lambda c: c['continuous_fraction']) if cands else None
        return {'verdict': verdict, 'best_risk_ok': best, 'best_continuous_ignoring_risk': best_any,
                'candidates': cands}

    gate = {d: gate_eval(d) for d in DEPTHS}
    log(f'[gate2] G2\' depth 1: {gate[1]["verdict"]}  best {gate[1]["best_risk_ok"]}')
    log(f'[gate2] G2\' depth 10: {gate[10]["verdict"]}  best {gate[10]["best_risk_ok"]}')

    # ---------------------------------------------------------------- self-tests (i), (iii)
    st_i = {'n_cases': len(selftest_recs), 'n_checks': int(sum(r['checks'] for r in selftest_recs)),
            'grid_mismatches': int(sum(r['grid_mismatch'] for r in selftest_recs)),
            'fine_grid_mismatches': int(sum(r['fine_mismatch'] for r in selftest_recs)),
            'eval_minus_fine_literal_s_range': [float(min([r['min_eval_vs_fine_s'] for r in selftest_recs] or [0])) * -1,
                                                float(max([r['max_eval_vs_fine_s'] for r in selftest_recs] or [0]))],
            'cases_with_agents': int(sum(r['n_agents'] > 0 for r in selftest_recs)),
            'rule': f'(clip, frame_idx, depth) with md5 % 1000 < {SELFTEST_PER_MILLE}; every config x every T_c'}
    lo = -max([r['max_eval_vs_fine_s'] for r in selftest_recs] or [0.0])
    hi = -min([r['min_eval_vs_fine_s'] for r in selftest_recs] or [0.0])
    st_i['H_eval_minus_H_literal_fine_s'] = {'min': lo, 'max': hi, 'fine_dt_s': DT / 20}
    st_i.pop('eval_minus_fine_literal_s_range')
    st_i['pass'] = bool(st_i['n_cases'] >= 300 and st_i['grid_mismatches'] == 0 and st_i['fine_grid_mismatches'] == 0
                        and lo >= -DT / 20 - 1e-9 and hi <= 1e-9)
    st_iii = selftest_inflation(ego)
    log(f'[gate2] self-test (i): {json.dumps(clean_json(st_i))}')
    log(f'[gate2] self-test (iii): max err {st_iii["max_abs_err_m"]:.2e}, residual {st_iii["residual_decomposition_max_err_m"]:.2e}')

    # ---------------------------------------------------------------- binding / attribution diagnostics
    diag = {}
    for d in DEPTHS:
        R = [r for r in rows if r['depth'] == d]
        for key in KEY_CONFIGS:
            T_c = 0.5
            hbar = T_PRED - T_c
            short = [r for r in R if lease_H(r[f'tau_star__{key}'], T_c) < NEED[d] - 1e-9]
            over = []
            for r in R:
                vs = hbar if r['censored'] else min(max(r['V_s'] - T_c, 0.0), hbar)
                if lease_H(r[f'tau_star__{key}'], T_c) > vs + OVER_EPS:
                    over.append(r)
            pos = Counter(f"{rel_position(r[f'bindxy__{key}'], ego)}/{r[f'bind__{key}'].split('/')[1] if r[f'bind__{key}'].count('/') == 3 else r[f'bind__{key}']}"
                          for r in short)
            diag[f'{key}|depth{d}|Tc0.5'] = {
                'n_frames': len(R), 'n_not_continuous': len(short),
                'binding_position_of_not_continuous': dict(pos.most_common()),
                'binding_detection_of_not_continuous': dict(Counter(r[f'bind__{key}'] for r in short).most_common()),
                'n_overestimates': len(over),
                'overestimates_V_binding_status': dict(Counter(str(r['V_binding_status']) for r in over)),
                'overestimates_V_binding_group': dict(Counter(str(r['V_binding_group']) for r in over)),
                'overestimates_lease_binding_detection': dict(Counter(r[f'bind__{key}'] for r in over).most_common())}

    # ---------------------------------------------------------------- outputs
    frame_rows = []
    for r in rows:
        o = {k: v for k, v in r.items() if not k.startswith(('tau_star__', 'bind__', 'bindxy__'))}
        for T_c in T_CS:
            hbar = T_PRED - T_c
            o[f'V_suf_Tc{T_c:g}'] = hbar if r['censored'] else min(max(r['V_s'] - T_c, 0.0), hbar)
        for key in config_keys:
            o[f'tau_star__{key}'] = r[f'tau_star__{key}']
        for key in config_keys:
            for T_c in T_CS:
                o[f'H__{key}__Tc{T_c:g}'] = float(lease_H(r[f'tau_star__{key}'], T_c))
        for key in KEY_CONFIGS:
            o[f'bind__{key}'] = r[f'bind__{key}']
            xy = r[f'bindxy__{key}']
            o[f'bind_x__{key}'] = None if xy is None else xy[0]
            o[f'bind_y__{key}'] = None if xy is None else xy[1]
            o[f'bind_pos__{key}'] = rel_position(xy, ego)
        frame_rows.append(o)
    write_csv(out / 'frames.csv', frame_rows)
    write_csv(out / 'per_clip.csv', per_clip_rows)
    table_rows = []
    for (key, T_c, d), m in sorted(results_tab.items(), key=lambda x: (x[0][2], x[0][1], config_keys.index(x[0][0]))):
        fam, q, prot = parse_key(key)
        table_rows.append({'config': key, 'variant': fam, 'quantile': q, 'protocol': prot, 'T_c': T_c, 'depth': d,
                           'need_s': NEED[d], **{k: v for k, v in m.items() if not k.endswith('_ci95')},
                           **{f'{k}_lo': v[0] for k, v in m.items() if k.endswith('_ci95')},
                           **{f'{k}_hi': v[1] for k, v in m.items() if k.endswith('_ci95')}})
    write_csv(out / 'metrics.csv', table_rows)

    scripts = [Path(__file__).resolve(), Path(envmod.__file__).resolve(), ROOT / 'framelease_v3/__init__.py']
    v2_mods = [ROOT / f'framelease_v2/{m}' for m in ('lease.py', 'geometry.py', 'calibration.py', 'c2_eval.py',
                                                       'unidrive_boxes.py', '__init__.py')]
    inputs = [OLD_PARAMS, OLD_EVAL / 'frames.csv', OLD_EVAL / 'config.json', SWEEP / 'MERGE_NOTE.json']
    config = {
        'argv': sys.argv if argv is None else ['suffix_lease_eval.py', *argv], 'started': started,
        'finished': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'wall_s': time.time() - t_start,
        'python': sys.version, 'numpy': np.__version__, 'platform': platform.platform(),
        'script_sha256': sha_of(scripts), 'framelease_v2_sha256': sha_of(v2_mods),
        'input_sha256': sha_of(inputs),
        'clip_npz_sha256': {c: clip_meta[c]['npz_sha256'] for c in all_clips},
        'clip_gt_sha256': {c: clip_meta[c]['gt_sha256'] for c in all_clips},
        'sweep': str(SWEEP), 'val_clips': val_clips, 'train_clips': train_clips,
        'settings': {'T_pred_s': T_PRED, 'dt_s': DT, 'd_safe_m': D_SAFE, 'delta_m': DELTA, 'T_c_s': list(T_CS),
                     'depths': list(DEPTHS), 'L_rel_s': L_REL, 'overhead_s': OVERHEAD_S, 'need_s': NEED,
                     'refine_quantum_s': REFINE_QUANTUM_S, 'quantiles': list(QUANTILES),
                     'score_threshold': SCORE_THRESHOLD, 'low_score_floor': LOW_SCORE_FLOOR, 'low_conf_mode': 'cap',
                     'warmup_steps': WARMUP_STEPS, 'gate_m': GATE_M, 'static_speed_mps': envmod.STATIC_SPEED_MPS,
                     'E0_envelope_D_grid_s': list(envmod.E0_D_GRID_S), 'pad_m': PAD_M, 'n_boot': args.n_boot,
                     'seed': args.seed, 'bootstrap_unit': 'clip', 'frame_stride': args.frame_stride,
                     'max_frames': args.max_frames, 'over_eps': OVER_EPS},
        'gate_prespecified': GATE, 'ego_shape': ego.to_dict(),
        'scope': 'OFFLINE open-loop non-reactive replay; lease uses only model detections and plans; ground truth '
                 'used only for envelope calibration on clips other than the evaluated one and for scoring'}
    write_json(out / 'config.json', config)
    summary = {
        'run_dir': str(out), 'gate': {str(d): gate[d] for d in DEPTHS}, 'gate_prespecified': GATE,
        'need_s': {str(d): NEED[d] for d in DEPTHS},
        'metrics': {f'{key}|Tc{T_c:g}|depth{d}': m for (key, T_c, d), m in results_tab.items()},
        'reproduction': repro, 'old_reference_from_merged20_frames_csv': {str(d): v for d, v in old_ref.items()},
        'selftests': {'i_closed_form_vs_literal': st_i, 'iii_inflation': st_iii,
                      'iv_E0_ORIG_refit_vs_existing_file': {'max_abs_diff': st_iv_max, 'detail': st_iv}},
        'envelope_coverage_out_of_sample': cov, 'binding_diagnostics': diag,
        'skipped': {c: dict(v) for c, v in skipped.items()},
        'n_cases': {str(d): int(sum(1 for r in rows if r['depth'] == d)) for d in DEPTHS},
        'calibration_pairs_per_clip': {c: int(len(samples[c]['group'])) for c in all_clips},
        'residual_tail_vehicle_2s': residual_tail(samples, all_clips, tau),
        'wall_s': time.time() - t_start}
    write_json(out / 'summary.json', summary)
    log(f'[gate2] done in {time.time() - t_start:.0f}s -> {out}')
    log_f.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
