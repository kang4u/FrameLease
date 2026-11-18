#!/usr/bin/env python3
"""C2: offline evaluation of the Action-Validity Lease against observed plan validity (VAL clips only).

    python -m framelease_v2.c2_eval --sweep outputs/framelease_v2/c1_sweep/<run_name> \
        --lease-params outputs/framelease_v2/c2_calibration/<run_name>/lease_params.json

Without --lease-params the bounds are calibrated in-process on the TRAIN clips of the same sweep
(calibration.run_calibration) and saved next to the results; VAL ground truth never enters the lease.

Protocol
--------
For every VAL frame k whose ground truth covers [t_k, t_k + horizon] and every depth d (default 10 and 1):
  H_k  lease from the model's own decoded detections of frame k and plan candidates[k, d-1]
       (lease.compute_lease with the calibrated LeaseParams; ego vehicle constants from calibration).
  V_k  observed validity: first tau in (0, horizon] at which the ego footprint following the plan comes within
       d_safe of the REALIZED ground-truth footprint of any vehicle or walker at the same absolute time
       t_k + tau (GT interpolated between 10 Hz frames by actor id). Non-reactive replay assumption: actors
       follow their recorded paths, which reacted to the expert, not to this plan. V_k = 0 when the plan already
       starts within d_safe; V_k = horizon (right-censored) when it never comes within d_safe. The crossing time
       is linearly interpolated between dt_s grid points.
  A lease over-estimates dangerously when H_k > V_k.

Families (identical inputs, frames and scoring; one swept parameter each; all capped at H_max):
  avl                AVL, blueprint global margin                          reserve delta (m)
  avl_time_resolved  AVL with the bound applied pointwise in tau           reserve (m)
  avl_no_lowconf     AVL ignoring low-confidence detections (ablation)     reserve (m)
  plan_agnostic      same formula, ego path = straight constant-velocity   reserve (m)
                     extrapolation of the current speed (no plan)
  ttc                TTC threshold: H = clip(TTC - theta, 0, H_max); TTC   theta (s)
                     = time until the constant-velocity ego footprint first comes within d_safe of a
                     confident detection propagated at its velocity (current detections, no plan)
  speed              speed-based deadline H = min(H_max, D / v)            D (m)
  fixed_ttl          constant lease c (identical to an observation-age     c (s)
                     threshold rule, so the age-only baseline is this family)
Ego speed v is the model's own ego_status[:, 0] input (CAN-bus speed) when the sweep records it, otherwise the
recorded pose history (backward difference of lidar2global, i.e. odometry); see calibration.SweepClip._ego_speed.

Metrics per family and parameter: dangerous over-estimation rate P(H > V), mean lease, mean excess
E[(H - V)+], and the rate among frames with a realized conflict (V < horizon); per clip and pooled over frames.
Comparisons use each family's achievable frontier (Pareto set of its sweep; linear interpolation between
frontier points is achievable by randomizing between two settings; the trivial lease 0 is always available):
  lease at matched risk   best mean lease with P(H > V) <= target
  risk at matched lease   lowest P(H > V) with mean lease >= target
Confidence intervals: clip-level bootstrap (clips resampled with replacement).
Outputs (outputs/framelease_v2/c2_eval/<run_name>/): config.json, summary.json, curves.csv, frames.csv,
per_clip.csv, comparisons.csv, c2_tradeoff.{png,pdf}, lease_params_used.json.
Ground truth is used only for scoring (V_k) and for attributing over-estimates to detected or undetected agents.
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v2.calibration import (DEFAULT_WARMUP_STEPS, MATCH_GROUPS, TRAIN_CLIPS, VAL_CLIPS,  # noqa: E402
                                       available_clips, clean_json, dets_world, git_commit, gt_frame, hungarian_match,
                                       is_synthetic, load_clips, missing_expected, run_calibration, sha256_file,
                                       sweep_config, write_csv, write_json)
from framelease_v2.geometry import (box_corners, constant_velocity_path, convex_distance, ego_footprint,  # noqa: E402
                                    first_crossing_time, se2_apply, time_grid, wrap_angle)
from framelease_v2.lease import (B2D_EGO, LeaseParams, class_group_map, lease_from_geometry, lease_geometry,  # noqa: E402
                                 lease_sweep, load_ego_shape, load_lease_params, save_lease_params,
                                 speed_deadline_lease, ttc_from_geometry)

FAMILY_ORDER = ('avl', 'avl_time_resolved', 'avl_no_lowconf', 'plan_agnostic', 'ttc', 'speed', 'fixed_ttl')
FAMILY_LABEL = {'avl': 'AVL (ours)', 'avl_time_resolved': 'AVL, time-resolved bound',
                'avl_no_lowconf': 'AVL, low-confidence ignored', 'plan_agnostic': 'Plan-agnostic margin',
                'ttc': 'TTC threshold', 'speed': 'Speed deadline', 'fixed_ttl': 'Fixed TTL / age threshold'}
FAMILY_PARAM = {'avl': 'reserve_m', 'avl_time_resolved': 'reserve_m', 'avl_no_lowconf': 'reserve_m',
                'plan_agnostic': 'reserve_m', 'ttc': 'ttc_threshold_s', 'speed': 'distance_m', 'fixed_ttl': 'ttl_s'}
# Figure: categorical slots in fixed order, one entity per slot (validated adjacent pairs, light surface).
PALETTE = ('#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300')
FIG_FAMILIES = ('avl', 'plan_agnostic', 'ttc', 'speed', 'fixed_ttl', 'avl_time_resolved')
FIG_MARKERS = {'avl': 'o', 'plan_agnostic': 's', 'ttc': '^', 'speed': 'D', 'fixed_ttl': 'v', 'avl_time_resolved': 'P'}
INK = {'primary': '#0b0b0b', 'secondary': '#52514e', 'muted': '#898781', 'grid': '#e1e0d9', 'axis': '#c3c2b7',
       'surface': '#fcfcfb'}
EPS = 1e-9


def reserve_floor(params):
    """Reserve at or below which every relevant agent's lease is H_max, in both margin modes.

    The footprint clearance is >= -d_safe (overlapping footprints), so m - B_c(D) > reserve for all D <= H_max
    as soon as reserve < -d_safe - max_c B_c(H_max)."""
    return -float(params.d_safe_m) - max(float(params.bound(g, params.h_max_s)) for g in params.relevant_groups)


def default_grids(h_max, reserve_min=None):
    # Every sweep must span leases from ~0 up to the common endpoint (H = H_max on every frame); a curve that stops
    # short of it understates that family's lease at matched risk. The reserve tail therefore reaches
    # reserve_floor(params) (B(H_max) is ~18 m for the q95 set and ~42 m for q99), and the TTC threshold goes
    # down to -H_max so that H = clip(TTC - theta, 0, H_max) = H_max even when TTC = 0.
    lo = -14.0 if reserve_min is None else min(-14.0, math.floor(reserve_min) - 1.0)
    reserve = np.round(np.r_[np.arange(lo, -3.0, 1.0), np.arange(-3.0, -1.0, 0.25), np.arange(-1.0, 3.0, 0.1),
                             np.arange(3.0, 10.001, 0.5)], 6)
    return {'avl': reserve, 'avl_time_resolved': reserve, 'avl_no_lowconf': reserve, 'plan_agnostic': reserve,
            'ttc': np.round(np.arange(-float(h_max), 3.0001, 0.05), 6),
            'speed': np.round(np.r_[np.arange(0.0, 10.0, 0.5), np.arange(10.0, 80.001, 2.5)], 6),
            'fixed_ttl': np.round(np.arange(0.0, h_max + 1e-9, 0.05), 6)}


# ----------------------------------------------------------------------------- scoring

def observed_validity(E_world, tau, gt_state, d_safe, ego_radius, pad_m=5.0):
    """V for one plan. E_world (M,4,2) ego footprint at t_k + tau; gt_state from GTTrack.actors_at(t_k + tau).

    Exact polygon distances are computed for every (time, actor) pair whose center-distance lower bound is
    below d_safe + pad_m, so clearances around a crossing are exact and the interpolated crossing time is too.
    Returns dict(V, censored, v0, binding_col, min_clearance).
    """
    xy, yaw, hl, hw, valid = gt_state
    M = len(tau)
    ego_c = E_world.mean(axis=-2)
    r_a = np.hypot(hl, hw)
    lb = np.linalg.norm(xy - ego_c[:, None, :], axis=-1) - ego_radius - r_a
    cand = valid & (lb <= d_safe + pad_m)
    dist = np.full(valid.shape, np.inf)
    if cand.any():
        mi, ai = np.nonzero(cand)
        dist[mi, ai] = convex_distance(E_world[mi], box_corners(xy[mi, ai], yaw[mi, ai], hl[mi, ai], hw[mi, ai]))
    clear = dist.min(axis=1) - d_safe
    out = {'min_clearance': float(np.min(clear)) if np.isfinite(clear).any() else math.inf}
    V = first_crossing_time(tau, clear)
    if V == 0.0:
        out.update(V=0.0, censored=False, v0=True, binding_col=int(np.argmin(dist[0])))
    elif math.isfinite(V):
        m = int(np.argmax(clear <= 0))
        out.update(V=float(V), censored=False, v0=False, binding_col=int(np.argmin(dist[m])))
    else:
        out.update(V=float(tau[-1]), censored=True, v0=False, binding_col=None)
    return out


def detection_status(clip, k, params, gate_m):
    """Ground-truth actor column -> 'confident' | 'low_confidence' for actors matched at capture time."""
    gt = gt_frame(clip, k)
    dw = dets_world(clip, k)
    rel = np.isin(dw['group'], [g for g in params.relevant_groups if g in MATCH_GROUPS])
    status = {}
    for name, thr in (('low_confidence', params.low_score_floor), ('confident', params.score_threshold)):
        sel = rel & (dw['score'] >= thr)
        for a, _, _ in hungarian_match(gt['xy'], gt['group'], dw['xy'][sel], dw['group'][sel], gate_m):
            status[int(gt['col'][a])] = name
    return status


def evaluate_clip(clip, params, ego, depths, grids, gate_m, log=print, warmup_steps=DEFAULT_WARMUP_STEPS,
                  extra_params=None):
    """Score one VAL clip. extra_params: {name: LeaseParams} evaluated at their own reserve (operating points)."""
    extra_params = extra_params or {}
    tau = time_grid(params.horizon_s, params.dt_s)
    h_max = float(params.h_max_s)
    ego_radius = float(np.hypot(ego.half_length_m, ego.half_width_m))
    res = {d: {'H': {f: [] for f in FAMILY_ORDER}, 'V': [], 'conflict': [], 'op': [], 'rows': [],
               'extra': {n: [] for n in extra_params}} for d in depths}
    skipped = Counter()
    nolc_params = LeaseParams.from_dict({**params.to_dict(), 'low_conf_mode': 'ignore'})
    E0 = ego_footprint(np.zeros((1, 2)), np.array([ego.forward_yaw_rad]), ego.half_length_m, ego.half_width_m,
                       ego.center_offset_xy, ego.forward_yaw_rad)[0]
    checks = {'ego_capture_center_err_m': [], 'ego_capture_yaw_err_rad': []}
    t0 = time.perf_counter()
    for k in range(len(clip)):
        t_k = float(clip.t[k])
        if clip.run_step[k] < warmup_steps:
            skipped['warmup'] += 1
            continue
        # Contract check (not used by the lease): the plan's ego footprint at tau = 0 is the recorded ego box.
        g_row = int(clip.gt_row[k])
        Ew = se2_apply(clip.poses[k], E0)
        checks['ego_capture_center_err_m'].append(float(np.linalg.norm(Ew.mean(0) - clip.gt.ego_xy[g_row])))
        checks['ego_capture_yaw_err_rad'].append(abs(float(wrap_angle(clip.poses[k][2] + ego.forward_yaw_rad
                                                                      - clip.gt.ego_yaw[g_row]))))
        if t_k + params.horizon_s > clip.gt.t[-1] + EPS:
            skipped['insufficient_future_gt'] += 1
            continue
        gt_state = clip.gt.actors_at(t_k + tau)
        det7, score, label = clip.dets(k)
        pose = clip.poses[k]
        speed = max(float(clip.speed[k]), 0.0)
        geom_cv = lease_geometry(constant_velocity_path(speed, ego.forward_yaw_rad), det7, score, label, ego, params)
        ttc = ttc_from_geometry(geom_cv)
        base = {'plan_agnostic': lease_sweep(geom_cv, params, grids['plan_agnostic']),
                'ttc': np.clip(ttc - grids['ttc'], 0.0, h_max),
                'speed': speed_deadline_lease(speed, grids['speed'], h_max),
                'fixed_ttl': np.clip(grids['fixed_ttl'], 0.0, h_max)}
        pa_op = lease_from_geometry(geom_cv, params)
        status = None
        for d in depths:
            plan = clip.cand[k, d - 1]
            if not np.isfinite(plan).all():
                skipped[f'nonfinite_plan_depth{d}'] += 1
                continue
            geom = lease_geometry(plan, det7, score, label, ego, params)
            op = lease_from_geometry(geom, params)
            val = observed_validity(se2_apply(pose, geom.ego_corners), tau, gt_state, params.d_safe_m, ego_radius)
            H = {'avl': lease_sweep(geom, params, grids['avl']),
                 'avl_time_resolved': lease_sweep(geom, params, grids['avl_time_resolved'], margin_mode='time_resolved'),
                 'avl_no_lowconf': lease_sweep(geom, params, grids['avl_no_lowconf'], include_low_conf=False), **base}
            r = res[d]
            for f in FAMILY_ORDER:
                r['H'][f].append(np.asarray(H[f], dtype=float))
            r['V'].append(val['V'])
            r['conflict'].append(not val['censored'])
            r['op'].append(op['lease_s'])
            for n, pq in extra_params.items():
                r['extra'][n].append(float(lease_sweep(geom, pq, [pq.reserve_m])[0]))
            b_col = val['binding_col']
            b_status = None
            if b_col is not None:
                if status is None:
                    status = detection_status(clip, k, params, gate_m)
                g_row = int(clip.gt_row[k])
                b_status = status.get(b_col, 'undetected' if clip.gt.present[g_row, b_col] else 'absent_at_capture')
            tr_op = lease_from_geometry(geom, params, margin_mode='time_resolved')['lease_s']
            r['rows'].append({
                'clip': clip.name, 'frame_idx': int(clip.frame_idx[k]), 'depth': d, 't_s': t_k,
                'V_s': val['V'], 'censored': int(val['censored']), 'v0': int(val['v0']),
                'binding_actor_id': None if b_col is None else str(clip.gt.ids[b_col]),
                'binding_actor_group': None if b_col is None else str(clip.gt.group[b_col]),
                'binding_detection_status': b_status, 'min_clearance_m': val['min_clearance'],
                'H_avl_s': op['lease_s'], 'avl_reason': op['reason'], 'margin_m': op['margin_m'],
                'avl_binding_det_index': op['binding_index'], 'avl_binding_group': op['binding_group'],
                'n_confident': op['n_confident'], 'n_low_confidence': op['n_low_confidence'],
                'H_avl_time_resolved_s': tr_op,
                'H_avl_no_lowconf_s': lease_from_geometry(geom, nolc_params)['lease_s'],
                'H_plan_agnostic_s': pa_op['lease_s'], 'ttc_s': ttc, 'ego_speed_mps': speed,
                'speed_noncausal': int(clip.speed_noncausal[k]), 'overestimate_avl': int(op['lease_s'] > val['V'] + EPS)})
    log(f'[c2_eval] {clip.name}: {sum(len(res[d]["V"]) for d in depths)} (frame, depth) cases in '
        f'{time.perf_counter() - t0:.1f}s; skipped {dict(skipped)}')
    for d in depths:
        r = res[d]
        for f in FAMILY_ORDER:
            r['H'][f] = np.asarray(r['H'][f], dtype=float).reshape(len(r['V']), len(grids[f]))
        r['V'] = np.asarray(r['V'], dtype=float)
        r['conflict'] = np.asarray(r['conflict'], dtype=bool)
        r['op'] = np.asarray(r['op'], dtype=float)
        r['extra'] = {n: np.asarray(v, dtype=float) for n, v in r['extra'].items()}
    res['checks'] = checks
    return res, skipped


# ----------------------------------------------------------------------------- statistics

def clip_sums(H, V, conflict):
    """Sufficient statistics of one clip for one family: H (n, P), V (n,)."""
    over = H > V[:, None] + EPS
    return {'n': float(len(V)), 'over': over.sum(0).astype(float), 'sumH': H.sum(0),
            'excess': np.maximum(H - V[:, None], 0.0).sum(0), 'n_conf': float(conflict.sum()),
            'over_conf': (over & conflict[:, None]).sum(0).astype(float)}


def pooled(sums, w):
    """Pooled metrics for clip weights w (C,) or (B, C). sums: list over clips of clip_sums dicts."""
    w = np.asarray(w, dtype=float)
    n = w @ np.array([s['n'] for s in sums])
    nc = w @ np.array([s['n_conf'] for s in sums])
    stack = {k: np.stack([s[k] for s in sums]) for k in ('over', 'sumH', 'excess', 'over_conf')}
    with np.errstate(invalid='ignore', divide='ignore'):
        nn = np.asarray(n)[..., None]
        out = {'n': n, 'rate': (w @ stack['over']) / nn, 'mean_lease': (w @ stack['sumH']) / nn,
               'mean_excess': (w @ stack['excess']) / nn, 'n_conflict': nc,
               'rate_conflict': (w @ stack['over_conf']) / np.asarray(nc)[..., None]}
    return out


def frontier(rate, lease):
    """Achievable frontier of a sweep: Pareto points (rate ascending, lease strictly increasing) incl. (0, 0)."""
    pts = [(float(r), float(m)) for r, m in zip(rate, lease) if np.isfinite(r) and np.isfinite(m)] + [(0.0, 0.0)]
    pts.sort(key=lambda p: (p[0], -p[1]))
    out, best = [], -math.inf
    for r, m in pts:
        if m > best + 1e-12:
            out.append((r, m))
            best = m
    return np.asarray(out)


def lease_at_risk(front, target):
    r, m = front[:, 0], front[:, 1]
    if target >= r[-1]:
        return float(m[-1])
    i = int(np.searchsorted(r, target, side='right')) - 1
    if i < 0:
        return 0.0
    return float(m[i] + (m[i + 1] - m[i]) * (target - r[i]) / (r[i + 1] - r[i]))


def risk_at_lease(front, target):
    r, m = front[:, 0], front[:, 1]
    if target > m[-1] + 1e-12:
        return math.nan  # unattainable by this family
    j = int(np.searchsorted(m, target - 1e-12, side='left'))
    if j == 0:
        return float(r[0])
    return float(r[j - 1] + (r[j] - r[j - 1]) * (target - m[j - 1]) / (m[j] - m[j - 1]))


def ci(values):
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)], dtype=float)
    if len(v) == 0:
        return [None, None]
    return [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))]


def summarize_depth(d, per_clip, clip_names, grids, n_boot, seed, risk_targets, lease_targets, horizon):
    """per_clip: list over clips of res[d]. Returns (summary dict, curve rows, comparison rows, per-clip rows)."""
    C = len(clip_names)
    sums = {f: [clip_sums(pc['H'][f], pc['V'], pc['conflict']) for pc in per_clip] for f in FAMILY_ORDER}
    op_sums = [clip_sums(pc['op'][:, None], pc['V'], pc['conflict']) for pc in per_clip]
    ones = np.ones(C)
    curves = []
    for f in FAMILY_ORDER:
        P = pooled(sums[f], ones)
        for i, val in enumerate(grids[f]):
            curves.append({'depth': d, 'family': f, 'param': FAMILY_PARAM[f], 'value': float(val), 'clip': 'ALL',
                           'n': int(P['n']), 'rate': P['rate'][i], 'mean_lease_s': P['mean_lease'][i],
                           'mean_excess_s': P['mean_excess'][i], 'n_conflict': int(P['n_conflict']),
                           'rate_conflict': P['rate_conflict'][i]})
        for c, name in enumerate(clip_names):
            w = np.eye(C)[c]
            Pc = pooled(sums[f], w)
            for i, val in enumerate(grids[f]):
                curves.append({'depth': d, 'family': f, 'param': FAMILY_PARAM[f], 'value': float(val), 'clip': name,
                               'n': int(Pc['n']), 'rate': Pc['rate'][i], 'mean_lease_s': Pc['mean_lease'][i],
                               'mean_excess_s': Pc['mean_excess'][i], 'n_conflict': int(Pc['n_conflict']),
                               'rate_conflict': Pc['rate_conflict'][i]})
    rng = np.random.default_rng(seed)
    W = np.vstack([ones, rng.multinomial(C, np.full(C, 1.0 / C), size=n_boot)]) if C else np.zeros((1, 0))
    pooled_all = {f: pooled(sums[f], W) for f in FAMILY_ORDER}
    op_all = pooled(op_sums, W)
    op_rate, op_lease = op_all['rate'][:, 0], op_all['mean_lease'][:, 0]
    comp = {}
    comp_rows = []
    risk_targets = [('avl_operating_rate', None)] + [(f'rate<={t:g}', t) for t in risk_targets]
    lease_targets = [('avl_operating_mean_lease', None)] + [(f'mean_lease>={t:g}s', t) for t in lease_targets]
    for kind, targets, fn in (('lease_at_matched_risk', risk_targets, lease_at_risk),
                              ('risk_at_matched_lease', lease_targets, risk_at_lease)):
        comp[kind] = {}
        for tname, tval in targets:
            vals = {f: np.full(len(W), np.nan) for f in FAMILY_ORDER}
            for b in range(len(W)):
                target = tval if tval is not None else (op_rate[b] if kind == 'lease_at_matched_risk' else op_lease[b])
                if not np.isfinite(target):
                    continue
                for f in FAMILY_ORDER:
                    front = frontier(pooled_all[f]['rate'][b], pooled_all[f]['mean_lease'][b])
                    vals[f][b] = fn(front, target)
            entry = {}
            for f in FAMILY_ORDER:
                diff = (vals['avl'] - vals[f]) if kind == 'lease_at_matched_risk' else (vals[f] - vals['avl'])
                entry[f] = {'estimate': vals[f][0], 'ci95': ci(vals[f][1:]), 'avl_advantage': diff[0],
                            'avl_advantage_ci95': ci(diff[1:]),
                            'avl_advantage_positive_fraction': float(np.mean(diff[1:][np.isfinite(diff[1:])] > 0))
                            if np.isfinite(diff[1:]).any() else None}
                comp_rows.append({'depth': d, 'comparison': kind, 'target': tname,
                                  'target_value': tval if tval is not None else (op_rate[0] if kind == 'lease_at_matched_risk' else op_lease[0]),
                                  'family': f, 'estimate': vals[f][0], 'ci95_low': entry[f]['ci95'][0],
                                  'ci95_high': entry[f]['ci95'][1], 'avl_advantage': diff[0],
                                  'avl_advantage_ci95_low': entry[f]['avl_advantage_ci95'][0],
                                  'avl_advantage_ci95_high': entry[f]['avl_advantage_ci95'][1]})
            comp[kind][tname] = entry
    per_clip_rows = []
    for c, name in enumerate(clip_names):
        pc = per_clip[c]
        w = np.eye(C)[c]
        o = pooled([op_sums[c]], np.ones(1))
        row = {'depth': d, 'clip': name, 'n': int(o['n']), 'avl_rate': float(o['rate'][0]),
               'avl_mean_lease_s': float(o['mean_lease'][0]), 'avl_mean_excess_s': float(o['mean_excess'][0]),
               'n_conflict': int(o['n_conflict']), 'avl_rate_conflict': float(o['rate_conflict'][0]),
               'v0_frames': int(np.sum(pc['V'] <= 0.0)), 'censored_fraction': float(np.mean(~pc['conflict'])) if len(pc['V']) else None}
        for f in FAMILY_ORDER:
            Pc = pooled(sums[f], w)
            front = frontier(Pc['rate'], Pc['mean_lease'])
            row[f'{f}_lease_at_avl_rate_s'] = lease_at_risk(front, row['avl_rate']) if np.isfinite(row['avl_rate']) else None
            row[f'{f}_risk_at_avl_lease'] = risk_at_lease(front, row['avl_mean_lease_s']) if np.isfinite(row['avl_mean_lease_s']) else None
        per_clip_rows.append(row)
    extra_points = {}
    for n in (per_clip[0]['extra'] if per_clip else {}):
        es = [clip_sums(pc['extra'][n][:, None], pc['V'], pc['conflict']) for pc in per_clip]
        ea = pooled(es, W)
        extra_points[n] = {'rate': ea['rate'][0, 0], 'rate_ci95': ci(ea['rate'][1:, 0]),
                           'mean_lease_s': ea['mean_lease'][0, 0], 'mean_lease_ci95': ci(ea['mean_lease'][1:, 0]),
                           'rate_conflict': ea['rate_conflict'][0, 0]}
    V_all = np.concatenate([pc['V'] for pc in per_clip]) if per_clip else np.zeros(0)
    summary = {
        'avl_calibration_quantile_points': extra_points,
        'depth': d, 'n_cases': int(len(V_all)), 'n_clips': C,
        'v0_fraction': float(np.mean(V_all <= 0)) if len(V_all) else None,
        'conflict_fraction': float(np.mean(V_all < horizon - EPS)) if len(V_all) else None,
        'V_quantiles_s': {f'q{q}': float(np.quantile(V_all, q / 100)) for q in (5, 10, 25, 50)} if len(V_all) else None,
        'avl_operating_point': {'rate': op_rate[0], 'rate_ci95': ci(op_rate[1:]), 'mean_lease_s': op_lease[0],
                                'mean_lease_ci95': ci(op_lease[1:]), 'mean_excess_s': op_all['mean_excess'][0, 0],
                                'rate_conflict': op_all['rate_conflict'][0, 0],
                                'rate_conflict_ci95': ci(op_all['rate_conflict'][1:, 0])},
        'comparisons': comp, 'bootstrap': {'n_boot': int(n_boot), 'seed': int(seed), 'unit': 'clip'},
    }
    return summary, curves, comp_rows, per_clip_rows


# ----------------------------------------------------------------------------- figure

def style_axes(ax):
    ax.set_facecolor(INK['surface'])
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    for side in ('left', 'bottom'):
        ax.spines[side].set_color(INK['axis'])
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=INK['secondary'], labelsize=8, width=0.6, length=3)
    ax.xaxis.label.set_color(INK['secondary'])
    ax.yaxis.label.set_color(INK['secondary'])
    ax.title.set_color(INK['primary'])
    ax.grid(True, color=INK['grid'], linewidth=0.5, linestyle='-')
    ax.set_axisbelow(True)


def tradeoff_figure(curves, summaries, depths, out_base, synthetic, h_max):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, len(depths), figsize=(4.6 * len(depths), 3.7), constrained_layout=True, squeeze=False)
    fig.patch.set_facecolor(INK['surface'])
    for ax, d in zip(axes[0], depths):
        for slot, f in enumerate(FIG_FAMILIES):
            rows = [r for r in curves if r['depth'] == d and r['family'] == f and r['clip'] == 'ALL'
                    and np.isfinite(r['rate']) and np.isfinite(r['mean_lease_s'])]
            if not rows:
                continue
            rows.sort(key=lambda r: (r['mean_lease_s'], r['rate']))
            x = [r['mean_lease_s'] for r in rows]
            y = [100.0 * r['rate'] for r in rows]
            ax.plot(x, y, color=PALETTE[slot], lw=2.2 if f == 'avl' else 1.5, solid_joinstyle='round',
                    solid_capstyle='round', marker=FIG_MARKERS[f], ms=4.5, markevery=max(1, len(x) // 8),
                    mec=INK['surface'], mew=0.8, label=FAMILY_LABEL[f], zorder=4 if f == 'avl' else 3)
        qpts = [qp for _, qp in sorted(summaries[d].get('avl_calibration_quantile_points', {}).items())
                if qp['rate'] is not None and np.isfinite(qp['rate'])]
        if qpts:  # values are in summary.json; identity via the legend, no per-point text
            ax.plot([q['mean_lease_s'] for q in qpts], [100.0 * q['rate'] for q in qpts], marker='o', ms=6,
                    mfc=INK['surface'], mec=PALETTE[0], mew=1.4, ls='none', zorder=5,
                    label='AVL at other calibration quantiles')
        op = summaries[d]['avl_operating_point']
        if op['rate'] is not None and np.isfinite(op['rate']):
            ax.plot([op['mean_lease_s']], [100.0 * op['rate']], marker='o', ms=9, color=PALETTE[0],
                    mec=INK['surface'], mew=1.5, zorder=6, ls='none', label='AVL operating point')
        ax.set_xlim(0, h_max * 1.02)
        ax.set_ylim(bottom=0)
        ax.set_xlabel('mean lease (s)')
        ax.set_ylabel('dangerous over-estimation  P(H > V)  (%)')
        ax.set_title(f'Plan depth {d}' + (' (official final plan)' if d == 10 else ''), fontsize=9.5, loc='left')
        style_axes(ax)
    leg = axes[0][0].legend(loc='upper left', frameon=False, fontsize=7.5, handlelength=2.2)
    for t in leg.get_texts():
        t.set_color(INK['primary'])
    if synthetic:
        fig.suptitle('SYNTHETIC DATA - pipeline test only, not a result', color='#d03b3b', fontsize=10)
    for ext in ('png', 'pdf'):
        fig.savefig(f'{out_base}.{ext}', dpi=220, facecolor=fig.get_facecolor())
    plt.close(fig)


# ----------------------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sweep', required=True, type=Path, help='outputs/framelease_v2/c1_sweep/<run_name>')
    ap.add_argument('--lease-params', type=Path, default=None,
                    help='LeaseParams JSON from calibration.py (default: calibrate on the TRAIN clips of --sweep)')
    ap.add_argument('--clips', default='', help='comma list of VAL clips (default: all VAL clips present)')
    ap.add_argument('--depths', default='10,1', help='flow depths d (1..10); index d-1 of candidates')
    ap.add_argument('--gate-m', type=float, default=2.0, help='matching gate for attribution (and calibration)')
    ap.add_argument('--n-boot', type=int, default=2000)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--warmup-steps', type=int, default=DEFAULT_WARMUP_STEPS,
                    help='exclude frames with run_step below this (temporal detector warm-up)')
    ap.add_argument('--gt-max-gap-s', type=float, default=0.25, help='max GT frame gap bridged by interpolation')
    ap.add_argument('--risk-targets', default='0.01,0.02,0.05')
    ap.add_argument('--lease-targets', default='0.5,1.0,1.5')
    ap.add_argument('--output-root', type=Path, default=ROOT / 'outputs/framelease_v2/c2_eval')
    ap.add_argument('--run-name', default='')
    ap.add_argument('--no-figure', action='store_true')
    args = ap.parse_args(argv)
    sweep = args.sweep.resolve()
    synthetic = is_synthetic(sweep)
    name = args.run_name or time.strftime('run_%Y%m%dT%H%M%S') + ('_SYNTHETIC' if synthetic else '')
    out = args.output_root / name
    out.mkdir(parents=True, exist_ok=False)
    started = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    depths = [int(x) for x in args.depths.split(',') if x]
    if any(d < 1 or d > 10 for d in depths):
        raise SystemExit('depths must be in 1..10')
    present = set(available_clips(sweep))
    missing = [] if args.clips else missing_expected(sweep, VAL_CLIPS)
    names = [c for c in args.clips.split(',') if c] or [c for c in VAL_CLIPS if c in present]
    if not names:
        raise SystemExit(f'no VAL clips under {sweep / "clips"}')
    calib_info = None
    if args.lease_params is not None:
        params = load_lease_params(args.lease_params)
        ego = load_ego_shape(args.lease_params, default=B2D_EGO)
        calib_info = {'source': str(args.lease_params.resolve()), 'sha256': sha256_file(args.lease_params)}
    else:
        train = [c for c in TRAIN_CLIPS if c in present]
        summary_cal, by_q, ego, _ = run_calibration(sweep, train, quantile=0.95, gate_m=args.gate_m,
                                                    max_gap_s=args.gt_max_gap_s, warmup_steps=args.warmup_steps)
        params = by_q[0.95]
        write_json(out / 'calibration_in_process.json', summary_cal)
        calib_info = {'source': 'in-process calibration on TRAIN clips', 'clips': train,
                      'contract_checks_all_pass': summary_cal['contract_checks_all_pass']}
    save_lease_params(out / 'lease_params_used.json', params, ego, {'calibration': calib_info})
    # Other calibration quantiles as extra AVL operating points (same geometry, different bounds).
    extra = {}
    if args.lease_params is not None:
        geo_keys = ('d_safe_m', 'h_max_s', 'score_threshold', 'horizon_s', 'dt_s', 'low_score_floor', 'low_conf_mode',
                    'relevant_groups', 'margin_mode', 'min_speed_mps')
        for qp in sorted(args.lease_params.resolve().parent.glob('lease_params_q*.json')):
            pq = load_lease_params(qp)
            if all(getattr(pq, k) == getattr(params, k) for k in geo_keys):
                extra[qp.stem.replace('lease_params_', '')] = pq
    elif calib_info is not None:
        extra = {f'q{int(round(q * 100))}': p for q, p in by_q.items()}
    grids = default_grids(params.h_max_s, reserve_floor(params))
    clips = load_clips(sweep, names, 'val', max_gap_s=args.gt_max_gap_s)
    per_clip_res = []
    skipped_all = {}
    frames_rows = []
    cap_err, cap_yaw = [], []
    for clip in clips:
        res, skipped = evaluate_clip(clip, params, ego, depths, grids, args.gate_m, warmup_steps=args.warmup_steps,
                                     extra_params=extra)
        chk = res.pop('checks')
        cap_err += chk['ego_capture_center_err_m']
        cap_yaw += chk['ego_capture_yaw_err_rad']
        per_clip_res.append(res)
        skipped_all[clip.name] = dict(skipped)
        for d in depths:
            frames_rows.extend(res[d]['rows'])
    summaries, curves, comps, per_clip_rows = {}, [], [], []
    for d in depths:
        s, cv, cp, pcr = summarize_depth(d, [r[d] for r in per_clip_res], [c.name for c in clips], grids, args.n_boot,
                                         args.seed, [float(x) for x in args.risk_targets.split(',') if x],
                                         [float(x) for x in args.lease_targets.split(',') if x], params.horizon_s)
        rows_d = [r for r in frames_rows if r['depth'] == d]
        over = [r for r in rows_d if r['overestimate_avl']]
        s['avl_reasons'] = dict(Counter(r['avl_reason'] for r in rows_d))
        s['avl_overestimate_attribution'] = {
            'n_overestimates': len(over),
            'binding_actor_detection_status': dict(Counter(str(r['binding_detection_status']) for r in over)),
            'binding_actor_group': dict(Counter(str(r['binding_actor_group']) for r in over)),
            'v0_cases': int(sum(r['v0'] for r in over))}
        summaries[d] = s
        curves.extend(cv)
        comps.extend(cp)
        per_clip_rows.extend(pcr)
    # Plan orientation check on VAL (planning output must point along the ego forward axis).
    fwd = []
    for clip in clips:
        p6 = clip.cand[:, 9, -1]
        f = clip.forward_yaw
        ok = np.isfinite(p6).all(1) & (np.hypot(p6[:, 0], p6[:, 1]) > 2.0)
        fwd.extend((p6[ok, 0] * np.cos(f[ok]) + p6[ok, 1] * np.sin(f[ok]) > 0).tolist())
    here = Path(__file__).resolve().parent
    config = {'argv': sys.argv if argv is None else ['c2_eval.py', *argv], 'started': started, 'git_commit': git_commit(),
              'script_sha256': {p: sha256_file(here / p) for p in ('c2_eval.py', 'calibration.py', 'lease.py', 'geometry.py')},
              'sweep': str(sweep), 'sweep_config': sweep_config(sweep), 'synthetic_sweep': synthetic,
              'clips': names, 'clip_sha256': {c.name: c.sha256 for c in clips},
              'gt_sha256': {c.name: c.gt_sha256 for c in clips}, 'depths': depths, 'lease_params': params.to_dict(),
              'ego_shape': ego.to_dict(), 'calibration': calib_info, 'class_group_source': class_group_map()[1],
              'grids': {f: grids[f].tolist() for f in FAMILY_ORDER}, 'reserve_floor_m': reserve_floor(params),
              'gate_m': args.gate_m, 'n_boot': args.n_boot,
              'warmup_steps': args.warmup_steps, 'gt_max_gap_s': args.gt_max_gap_s,
              'extra_operating_points': {n: p.to_dict() for n, p in extra.items()},
              'ego_speed_source': {c.name: c.speed_source for c in clips},
              'seed': args.seed,
              'scope': 'OFFLINE open-loop, non-reactive replay; VAL clips only; ground truth used only for scoring'}
    write_json(out / 'config.json', config)
    contract = {
        'ego_capture_center_err_m': {'median': float(np.median(cap_err)) if cap_err else None,
                                     'max': float(np.max(cap_err)) if cap_err else None, 'expected': '< 0.10',
                                     'pass': bool(cap_err) and float(np.max(cap_err)) < 0.10},
        'ego_capture_yaw_err_rad': {'median': float(np.median(cap_yaw)) if cap_yaw else None,
                                    'max': float(np.max(cap_yaw)) if cap_yaw else None, 'expected': '< 0.02',
                                    'pass': bool(cap_yaw) and float(np.max(cap_yaw)) < 0.02},
        'val_final_plan_forward_fraction': {'value': float(np.mean(fwd)) if fwd else None, 'expected': '> 0.9',
                                            'pass': bool(fwd) and float(np.mean(fwd)) > 0.9}}
    summary = {'synthetic_sweep': synthetic, 'clips': names, 'expected_val_clips_missing': missing,
               'contract_checks': contract, 'contract_checks_all_pass': all(v['pass'] for v in contract.values()),
               'skipped': skipped_all,
               'clip_issues': {c.name: c.issues for c in clips if c.issues},
               'val_final_plan_forward_fraction': float(np.mean(fwd)) if fwd else None,
               'families': {f: {'label': FAMILY_LABEL[f], 'param': FAMILY_PARAM[f]} for f in FAMILY_ORDER},
               'by_depth': {str(d): summaries[d] for d in depths}, 'finished': time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    write_json(out / 'summary.json', summary)
    write_csv(out / 'curves.csv', curves)
    write_csv(out / 'frames.csv', frames_rows)
    write_csv(out / 'per_clip.csv', per_clip_rows)
    write_csv(out / 'comparisons.csv', comps)
    if not args.no_figure:
        tradeoff_figure(curves, summaries, depths, out / 'c2_tradeoff', synthetic, params.h_max_s)
    brief = {'run_dir': str(out), 'synthetic_sweep': synthetic, 'clips': names}
    for d in depths:
        op = summaries[d]['avl_operating_point']
        brief[f'depth{d}'] = {'cases': summaries[d]['n_cases'], 'avl_rate': op['rate'], 'avl_mean_lease_s': op['mean_lease_s'],
                              'lease_at_avl_risk': {f: summaries[d]['comparisons']['lease_at_matched_risk']['avl_operating_rate'][f]['estimate']
                                                    for f in FAMILY_ORDER}}
    import json
    print(json.dumps(clean_json(brief), indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
