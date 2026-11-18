#!/usr/bin/env python3
"""Stage F (CPU): per-plan realized validity and Global-Margin / Suffix-Aligned leases for every envelope configuration.

    cd /home/kang/Desktop/DAC
    OMP_NUM_THREADS=1 .conda-unidrive-linux/bin/python -I -B framelease_v4/offline/stage_frames.py --workers 8

For every clip of the merged 37-clip view (5 TRAIN + 32 VAL) and every plan frame of the gate2 rule (run_step >= 5,
3 s of future ground truth, finite depth-1 plan), with the gate2 kernels (read-only imports):
  geometry   framelease_v2.lease.lease_geometry(plan, detections, ...) with suffix_lease_eval.base_params()
             (vehicles / pedestrians with score >= 0.1 count as real; d_safe 0.5 m; 0.05 s grid to T_pred = 3 s)
  V          framelease_v2.c2_eval.observed_validity: first tau at which the planned ego footprint comes within d_safe
             of a realized ground-truth vehicle / walker footprint (non-reactive replay), censored at 3 s
  suffix     tau* = min_j first crossing of clearance_j(tau) - B_j(tau) - delta (suffix_lease_eval.iso_agent_tau,
             exact quadratic crossing, per-agent cap 3 s); H = clip(tau* - T_c, 0, Hbar) is formed in the analysis
  global     H_glob = min_j lease_root(min_tau clearance_j - sigma_j - delta, vbar_j, abar_j, 3 s)
             (framelease_v2.lease.agent_leases(..., 'global')); the cap is applied in the analysis
Invalid perception (a non-finite relevant detection) gives tau* = 0 and H_glob = 0; no relevant detection gives 3 s.
Conflict frames also store the capture-time detection status of the ground-truth actor that ends V
(c2_eval.detection_status: confident / low-confidence detection, undetected, absent at capture).

Output: OUT/frames/<clip>.npz (resumable: an existing file with the same configuration hash is skipped),
OUT/frames/stage_meta.json.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault('OMP_NUM_THREADS', '1')
sys.dont_write_bytecode = True

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from concurrent.futures import ProcessPoolExecutor, as_completed  # noqa: E402
from multiprocessing import get_context  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v2.c2_eval import detection_status, observed_validity  # noqa: E402
from framelease_v2.calibration import SweepClip  # noqa: E402
from framelease_v2.geometry import se2_apply, time_grid  # noqa: E402
from framelease_v2.lease import agent_leases, lease_geometry, load_ego_shape  # noqa: E402
from framelease_v4.offline import common as C  # noqa: E402
from framelease_v4.offline import envelopes_v4 as EV  # noqa: E402

sle = C.sle
FRAMES_DIR = C.OUT / 'frames'


def config_hash(train_cfg, loco_cfg):
    blob = json.dumps({'train': train_cfg, 'loco': loco_cfg, 'T_PRED': C.T_PRED, 'DT': C.DT, 'D_SAFE': C.D_SAFE,
                       'DELTA': C.DELTA, 'depth': C.DEPTH, 'warmup': C.WARMUP_STEPS}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def global_H(geom, prm):
    """v2 Global-Margin lease at the per-agent cap of prm.h_max_s (3 s): min_j H_j (lease.py lease_from_geometry)."""
    if geom.status != 'ok':
        return 0.0
    if len(geom.index) == 0:
        return float(prm.h_max_s)
    H = agent_leases(geom, prm, [C.DELTA], 'global')[0]
    return float(min(np.min(H), prm.h_max_s))


def suffix_tau(geom, prm):
    N = len(geom.index)
    pa = sle.iso_agent_tau(geom, prm) if (geom.status == 'ok' and N) else np.zeros(0)
    ts, _ = sle.tau_star_from_agents(pa, geom.status, N)
    return float(ts)


def process_clip(task):
    name, train_cfg, loco_cfg, h = task
    t0 = time.perf_counter()
    out_path = FRAMES_DIR / f'{name}.npz'
    clip = SweepClip(C.VIEW, name)
    ego = load_ego_shape(C.V2_PARAMS)
    bp = sle.base_params()
    tau = time_grid(C.T_PRED, C.DT)
    ego_radius = float(np.hypot(ego.half_length_m, ego.half_width_m))
    tnames = list(train_cfg)
    lnames = list(loco_cfg) if loco_cfg else []
    prm_t = [sle.iso_params(train_cfg[n]) for n in tnames]
    prm_l = [sle.iso_params(loco_cfg[n]) for n in lnames]
    cols = {k: [] for k in ('frame_idx', 't_s', 'V', 'censored', 'v0', 'speed', 'lease_status', 'n_relevant',
                            'n_confident', 'bind_group', 'bind_status', 'min_clear')}
    tsT, hgT, tsL, hgL = [], [], [], []
    skipped = {'warmup': 0, 'insufficient_future_gt': 0, 'nonfinite_plan': 0}
    for k in range(len(clip)):
        if clip.run_step[k] < C.WARMUP_STEPS:
            skipped['warmup'] += 1
            continue
        t_k = float(clip.t[k])
        if t_k + C.T_PRED > clip.gt.t[-1] + 1e-9:
            skipped['insufficient_future_gt'] += 1
            continue
        plan = clip.cand[k, C.DEPTH - 1]
        if not np.isfinite(plan).all():
            skipped['nonfinite_plan'] += 1
            continue
        gt_state = clip.gt.actors_at(t_k + tau)
        det7, score, label = clip.dets(k)
        geom = lease_geometry(plan, det7, score, label, ego, bp)
        val = observed_validity(se2_apply(clip.poses[k], geom.ego_corners), tau, gt_state, C.D_SAFE, ego_radius)
        bgroup, bstat = 'none', 'none'
        if val['binding_col'] is not None:
            b_col = int(val['binding_col'])
            status = detection_status(clip, k, bp, C.GATE_M)
            g_row = int(clip.gt_row[k])
            bgroup = str(clip.gt.group[b_col])
            bstat = status.get(b_col, 'undetected' if clip.gt.present[g_row, b_col] else 'absent_at_capture')
        cols['frame_idx'].append(int(clip.frame_idx[k]))
        cols['t_s'].append(t_k)
        cols['V'].append(float(val['V']))
        cols['censored'].append(bool(val['censored']))
        cols['v0'].append(bool(val['v0']))
        cols['speed'].append(float(clip.speed[k]))
        cols['lease_status'].append(C.LEASE_STATUS_CODES[geom.status])
        cols['n_relevant'].append(int(len(geom.index)))
        cols['n_confident'].append(int(geom.confident.sum()))
        cols['bind_group'].append(C.GROUP_CODES.get(bgroup, 0))
        cols['bind_status'].append(C.STATUS_CODES[bstat])
        cols['min_clear'].append(float(geom.clearance.min()) if len(geom.index) else np.inf)
        tsT.append([suffix_tau(geom, p) for p in prm_t])
        hgT.append([global_H(geom, p) for p in prm_t])
        if prm_l:
            tsL.append([suffix_tau(geom, p) for p in prm_l])
            hgL.append([global_H(geom, p) for p in prm_l])
    F = len(cols['frame_idx'])
    arrays = {k: np.asarray(v, dtype=(float if k in ('t_s', 'V', 'speed', 'min_clear') else
                                      (bool if k in ('censored', 'v0') else np.int16))) for k, v in cols.items()}
    arrays.update(ts_T=np.asarray(tsT, dtype=float).reshape(F, len(tnames)),
                  hg_T=np.asarray(hgT, dtype=float).reshape(F, len(tnames)),
                  ts_L=np.asarray(tsL, dtype=float).reshape(F, len(lnames)),
                  hg_L=np.asarray(hgL, dtype=float).reshape(F, len(lnames)),
                  names_T=np.asarray(tnames), names_L=np.asarray(lnames, dtype='<U16'),
                  meta=np.asarray(json.dumps({'clip': name, 'split': clip.split, 'config_hash': h,
                                              'skipped': skipped, 'clip_sha256': clip.sha256,
                                              'gt_sha256': clip.gt_sha256, 'seconds': time.perf_counter() - t0})))
    C.atomic_savez(out_path, **arrays)
    return name, F, skipped, time.perf_counter() - t0


def load_clip(name):
    with np.load(FRAMES_DIR / f'{name}.npz', allow_pickle=False) as z:
        d = {k: z[k] for k in z.files}
    d['meta'] = json.loads(str(d['meta']))
    d['names_T'] = [str(x) for x in d['names_T']]
    d['names_L'] = [str(x) for x in d['names_L']]
    return d


def done_ok(name, h):
    p = FRAMES_DIR / f'{name}.npz'
    if not p.is_file():
        return False
    try:
        with np.load(p, allow_pickle=False) as z:
            return json.loads(str(z['meta'])).get('config_hash') == h
    except Exception:
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--clips', default=None, help='comma-separated subset (debug)')
    a = ap.parse_args(argv)
    C.check_disk()
    lists = C.load_lists()
    train_all = EV.load_train()
    train_cfg = {n: {p: train_all[n][p] for p in EV.PARAMS} for n in C.train_config_names()}
    loco_all = EV.load_loco()
    names = a.clips.split(',') if a.clips else lists['all']
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    tasks = []
    for n in names:
        loco_cfg = ({k: loco_all[n][k] for k in C.loco_config_names()} if n in loco_all else None)
        h = config_hash(train_cfg, loco_cfg)
        if done_ok(n, h):
            continue
        tasks.append((n, train_cfg, loco_cfg, h))
    # longest clips first
    tasks.sort(key=lambda t: -os.path.getsize(C.VIEW / 'clips' / f'{t[0]}.npz'))
    print(f'{len(names) - len(tasks)} clips already done, {len(tasks)} to run', flush=True)
    C.log_progress(f'stage_frames start: {len(tasks)} clips to run ({len(names) - len(tasks)} done)')
    t0 = time.time()
    res = []
    if tasks:
        with ProcessPoolExecutor(max_workers=a.workers, mp_context=get_context('fork')) as ex:
            futs = {ex.submit(process_clip, t): t[0] for t in tasks}
            for f in as_completed(futs):
                name, F, skipped, sec = f.result()
                res.append({'clip': name, 'frames': F, 'skipped': skipped, 'seconds': round(sec, 1)})
                print(f'[{time.time() - t0:7.1f}s] {name}: {F} frames ({sec:.1f}s)', flush=True)
    meta_path = FRAMES_DIR / 'stage_meta.json'
    old = json.loads(meta_path.read_text()) if meta_path.is_file() else {'runs': []}
    old['runs'].append({'finished': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'wall_s': round(time.time() - t0, 1),
                        'clips': res})
    C.write_json(meta_path, old)
    C.log_progress(f'stage_frames done: {len(res)} clips in {time.time() - t0:.0f}s')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
