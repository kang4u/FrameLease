"""Realized validity of committed plans in a closed-loop run, from the evaluation-only actor log (framelease_v4/arms).

The closed-loop analogue of the offline V of framelease_v2/c2_eval.py and the v3 studies:

* For every committed candidate c (jobs.jsonl: job, depth, plan in the capture LiDAR frame, capture time t_k,
  commit time, lease H = deadline - t_k) the plan is placed in the world with the capture pose (default: the TRUE
  LiDAR pose = hero transform at the capture tick + the official lidar2ego, i.e. the frame the model's plan and
  detections are expressed in; option 'estimate': the agent's own GNSS + compass lidar2global, as logged).
* The ego footprint rides along the plan (framelease_v2.lease.ego_corners_along_plan, the lease's ego shape) and
  V_c is the first tau in [0, T_pred] at which it comes within d_safe of a REAL logged vehicle / walker box at the
  same absolute time t_k + tau (framelease_v2.c2_eval.observed_validity on a framelease_v2.geometry.GTTrack built
  from the log; the identical function the offline studies use). V_c = T_pred and censored when it never does.
* V_suf = clip(V - T_c, 0, H_bar); conflict = V not censored.

Closed-loop quantities (per run):
  realized_invalid_ticks   tracked control ticks whose action, at age Delta = now - t_k, has a conflict with
                           Delta >= V_suf (its executed suffix [Delta, Delta + T_c] reaches the first realized failure)
  misses                   committed conflict plans with H > V_suf (the validity used at runtime over-estimated it;
                           for the non-lease arms H is the max-age validity)
  r_cond                   misses / committed conflict plans (the per-demand risk measure of the v3 studies)
  v0_plans                 conflict plans with V = 0 (already within d_safe at capture; not attributable to the plan)
Caveats: actors react to the ego in closed loop (the offline replay is non-reactive); a plan whose window passes the
end of the log is censored there (log_censored); undecimated logs give 0.05 s resolution of the actor tracks.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from framelease_v4.arms import actor_log as AL

D_SAFE_M = 0.5
T_C_S = 0.5
T_PRED_S = 3.0
DT_S = 0.05


def _jsonl(path):
    out = []
    p = Path(path)
    if not p.is_file():
        return out
    with p.open(encoding='utf-8') as f:
        for line in f:
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    break                                   # a line cut by a crash ends the stream
    return out


def committed_candidates(jobs):
    """{(job_id, depth): candidate} of every committed candidate in jobs.jsonl rows."""
    out = {}
    for j in jobs:
        for s in j.get('steps') or []:
            c = s.get('commit') or {}
            if not c.get('accepted'):
                continue
            v = s.get('validity') or {}
            deadline = v.get('deadline_s')
            out[(int(j['job_id']), int(s['depth']))] = {
                'job_id': int(j['job_id']), 'obs_id': int(j['obs_id']), 'capture_s': float(j['capture_s']),
                'depth': int(s['depth']), 'plan': np.asarray(s.get('plan'), dtype=float),
                'commit_s': float(c.get('commit_s')), 'deadline_s': None if deadline is None else float(deadline),
                'lease_s': None if v.get('lease_s') is None else float(v.get('lease_s')),
                'validity_source': v.get('source')}
    return out


def plan_validity(cand, pose, gt, ego, d_safe=D_SAFE_M, t_pred=T_PRED_S, dt=DT_S):
    """observed_validity of one committed plan placed with pose (x, y, yaw) of its capture LiDAR frame."""
    from framelease_v2.c2_eval import observed_validity
    from framelease_v2.geometry import se2_apply
    from framelease_v2.lease import ego_corners_along_plan
    ns = SimpleNamespace(dt_s=dt, horizon_s=t_pred, min_speed_mps=0.5)
    tau, _, _, E = ego_corners_along_plan(cand['plan'], ego, ns)
    E_world = se2_apply(tuple(float(v) for v in pose), E)
    gt_state = gt.actors_at(cand['capture_s'] + tau)
    ego_radius = float(math.hypot(ego.half_length_m, ego.half_width_m))
    return observed_validity(E_world, tau, gt_state, d_safe, ego_radius)


def realized_validity(run_dir, ego=None, d_safe=D_SAFE_M, t_c=T_C_S, t_pred=T_PRED_S, dt=DT_S, pose='true',
                      lease_params_path=None, with_candidates=False):
    """Realized validity of every committed plan of a run (see the module docstring). Returns a dict."""
    from framelease_v2 import lease as L2
    run_dir = Path(run_dir)
    fl = run_dir / 'raw' / 'agent' / 'framelease' if (run_dir / 'raw').is_dir() else run_dir
    log_path = fl / AL.FILE_NAME
    if not log_path.is_file():
        return {'available': False, 'reason': f'no {AL.FILE_NAME}'}
    if ego is None:
        ego = L2.load_ego_shape(lease_params_path, default=L2.B2D_EGO) if lease_params_path else L2.B2D_EGO
    log = AL.read_actor_log(log_path)
    if log.n_ticks == 0:
        return {'available': False, 'reason': 'empty actor log'}
    gt = log.gt_track()
    poses = log.lidar_pose_true() if pose == 'true' else log.lidar_pose_estimate()
    est, true = log.lidar_pose_estimate(), log.lidar_pose_true()
    offset = np.hypot(est[:, 0] - true[:, 0], est[:, 1] - true[:, 1])
    t_end = float(log.sim_s[-1])
    h_bar = max(0.0, t_pred - t_c)
    cands = committed_candidates(_jsonl(fl / 'jobs.jsonl'))
    res = {}
    for key, c in cands.items():
        i = log.index_of_step.get(c['obs_id'])
        if i is None or not np.isfinite(poses[i]).all() or c['plan'].shape != (6, 2) or \
                not np.isfinite(c['plan']).all():
            res[key] = {'status': 'no_pose_or_plan'}
            continue
        val = plan_validity(c, poses[i], gt, ego, d_safe, t_pred, dt)
        conflict = not val['censored']
        v_suf = min(max(val['V'] - t_c, 0.0), h_bar) if conflict else None
        lease = c['lease_s'] if c['lease_s'] is not None else (
            (c['deadline_s'] - c['capture_s']) if c['deadline_s'] is not None else None)
        res[key] = {'status': 'ok', 'V': float(val['V']), 'conflict': conflict, 'v0': bool(val['v0']),
                    'V_suf': v_suf, 'lease_s': lease, 'miss': bool(conflict and lease is not None and lease > v_suf),
                    'log_censored': bool(c['capture_s'] + t_pred > t_end + 1e-9 and not conflict),
                    'min_clearance_m': val['min_clearance']}
    tracked = invalid = 0
    for t in _jsonl(fl / 'ticks.jsonl'):
        if t.get('mode') != 'track' or not t.get('incumbent'):
            continue
        inc = t['incumbent']
        r = res.get((int(inc['job_id']), int(inc['depth'])))
        if r is None or r.get('status') != 'ok':
            continue
        tracked += 1
        age = float(t['sim_s']) - float(inc['capture_s'])
        if r['conflict'] and age + 1e-9 >= r['V_suf']:
            invalid += 1
    ok = [r for r in res.values() if r.get('status') == 'ok']
    conflicts = [r for r in ok if r['conflict']]
    misses = [r for r in conflicts if r['miss']]
    out = {'available': True, 'pose': pose, 'd_safe_m': d_safe, 't_c_s': t_c, 't_pred_s': t_pred,
           'log_ticks': log.n_ticks, 'log_truncated': log.truncated, 'log_stride_s': log.stride_s(),
           'committed_plans': len(cands), 'evaluated_plans': len(ok), 'conflict_plans': len(conflicts),
           'v0_plans': sum(1 for r in conflicts if r['v0']), 'misses': len(misses),
           'r_cond': (len(misses) / len(conflicts)) if conflicts else None,
           'misses_excl_v0': sum(1 for r in misses if not r['v0']),
           'conflicts_excl_v0': sum(1 for r in conflicts if not r['v0']),
           'log_censored_plans': sum(1 for r in ok if r['log_censored']),
           'tracked_ticks': tracked, 'realized_invalid_ticks': invalid,
           'realized_invalid_tick_ratio': (invalid / tracked) if tracked else None,
           'est_vs_true_lidar_offset_m': {'p50': float(np.nanmedian(offset)) if np.isfinite(offset).any() else None,
                                          'max': float(np.nanmax(offset)) if np.isfinite(offset).any() else None}}
    out['r_cond_excl_v0'] = (out['misses_excl_v0'] / out['conflicts_excl_v0']) if out['conflicts_excl_v0'] else None
    if with_candidates:
        out['candidates'] = {f'{k[0]}:{k[1]}': v for k, v in res.items()}
    return out


__all__ = ['committed_candidates', 'plan_validity', 'realized_validity']
