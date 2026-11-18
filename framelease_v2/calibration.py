#!/usr/bin/env python3
"""Calibrate the Action-Validity Lease bounds from a C1 depth sweep, on TRAIN clips only.

    python -m framelease_v2.calibration --sweep outputs/framelease_v2/c1_sweep/<run_name> [--quantile 0.95]

Per train frame the model's own decoded detections (det, det_score, det_label of the sweep) are placed in the
right-handed world frame with lidar2global and matched to ground-truth actors of the same group
(vehicle <-> vehicle, pedestrian <-> walker) by the Hungarian algorithm on center distance within a gate.

Reported (calibration.json and CSV files):
  * recall versus range for confident detections (score >= score_threshold) and at the low-score floor;
  * precision versus score (greedy matching in descending score order);
  * 50/90/95/99th percentiles by class group of center, footprint (Hausdorff), velocity, speed, heading and
    orientation (mod pi) errors of matched confident detections;
  * ground-truth acceleration percentiles of actors near the ego (the motion bound abar);
  * constant-velocity footprint prediction error versus staleness D and the empirical coverage of
    B(D) = vbar D + 0.5 abar D^2 + sigma under the emitted parameters;
  * coordinate-contract checks (LiDAR orientation, ego mounting, yaw and velocity conventions);
  * the admissible H_max for agents outside the reliably detected range (rule for undetected agents).

Emitted lease parameters: lease_params.json for --quantile and lease_params_q{50,90,95,99}.json. Each is a
LeaseParams JSON (lease.load_lease_params) with the ego vehicle constants under _ego_shape and provenance under
_meta. sigma uses the footprint (Hausdorff) error by default because the margin is a footprint distance:
|dist(E, R_hat) - dist(E, R)| <= Hausdorff(R_hat, R).

Ground truth is used only here, offline. It never feeds the model or an online lease; the ego vehicle size and
LiDAR mounting taken from the recorded ego box are vehicle constants.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v2.geometry import (GT_TO_GROUP, GTTrack, box_corners, forward_yaw_from_lidar2ego,  # noqa: E402
                                    hausdorff_convex, se2_apply, se2_from_matrix, se2_inverse, transform_states,
                                    wrap_angle)
from framelease_v2.lease import (B2D_EGO, DEFAULT_ABAR_MPS2, DEFAULT_SIGMA_M, DEFAULT_VBAR_MPS, EgoShape,  # noqa: E402
                                 LeaseParams, class_group_map, resolve_groups, save_lease_params)

TRAIN_CLIPS = ('ControlLoss_Town11_Route401_Weather11', 'HardBreakRoute_Town11_Route50_Weather23',
               'ParkingCrossingPedestrian_Town12_Route953_Weather9', 'PedestrianCrossing_Town12_Route867_Weather9',
               'StaticCutIn_Town03_Route149_Weather19')
VAL_CLIPS = ('ControlLoss_Town10HD_Route378_Weather14', 'HardBreakRoute_Town01_Route32_Weather6',
             'ParkingCrossingPedestrian_Town13_Route545_Weather25', 'PedestrianCrossing_Town13_Route747_Weather19',
             'StaticCutIn_Town05_Route226_Weather18')
# Ten further official Bench2Drive *validation* clips (framelease_v2/heldout_extra.py: selection frozen before download;
# all ten are in audits/dac2027_data_semantics_20261106/discovery/bench2drive_base_train_val_split.json /val). Added
# 2026-11-08. They are accepted as held-out clips by load_clips(..., 'val') but are never a default: c2_eval and
# c2_viability score them only when they are listed explicitly (--clips / --val-clips), and calibration never sees them.
EXTRA_VAL_CLIPS = ('ControlLoss_Town04_Route170_Weather14', 'InvadingTurn_Town02_Route95_Weather9',
                   'LaneChange_Town06_Route307_Weather21', 'MergerIntoSlowTrafficV2_Town12_Route857_Weather25',
                   'NonSignalizedJunctionLeftTurnEnterFlow_Town12_Route949_Weather13',
                   'NonSignalizedJunctionLeftTurn_Town07_Route342_Weather3',
                   'OppositeVehicleRunningRedLight_Town04_Route180_Weather23', 'ParkingExit_Town12_Route922_Weather12',
                   'SignalizedJunctionRightTurn_Town03_Route118_Weather14',
                   'VanillaNonSignalizedTurnEncounterStopsign_Town12_Route979_Weather9')
QUANTILES = (0.5, 0.9, 0.95, 0.99)
RANGE_BINS = (0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 75.0, math.inf)
SCORE_BINS = (0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0001)
DELTAS_S = (0.0, 0.5, 1.0, 1.5, 2.0)
MATCH_GROUPS = ('vehicle', 'pedestrian')
REQUIRED_KEYS = ('frame_idx', 'timestamp_s', 'split', 'clip', 'lidar2global', 'lidar2ego', 'candidates', 'det',
                 'det_score', 'det_label', 'det_count')
OPTIONAL_KEYS = ('prefix_ms', 'step_ms', 'det_raw', 'run_step', 'ego_status')
DEFAULT_WARMUP_STEPS = 5   # UniDriveVLA's temporal instance bank: no confident detection before run_step 5


# ----------------------------------------------------------------------------- utilities

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def git_commit():
    try:
        return subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def clean_json(x):
    """Recursively replace non-finite floats with None and numpy scalars with Python scalars."""
    if isinstance(x, dict):
        return {str(k): clean_json(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean_json(v) for v in x]
    if isinstance(x, np.ndarray):
        return clean_json(x.tolist())
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        x = float(x)
        return x if math.isfinite(x) else None
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(clean_json(obj), indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def write_csv(path, rows):
    rows = list(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for r in rows for k in r)) if rows else ['empty']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: ('' if v is None else (f'{v:.6g}' if isinstance(v, float) else v)) for k, v in r.items()})


def quantiles(values, qs=QUANTILES):
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)], dtype=float)
    out = {'n': int(len(v))}
    for q in qs:
        out[f'q{int(round(q * 100))}'] = float(np.quantile(v, q)) if len(v) else None
    out['mean'] = float(v.mean()) if len(v) else None
    out['max'] = float(v.max()) if len(v) else None
    return out


def sweep_config(sweep):
    p = Path(sweep) / 'config.json'
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return {'unreadable': True}
    return {}


def is_synthetic(sweep):
    return bool(sweep_config(sweep).get('synthetic', False))


# ----------------------------------------------------------------------------- sweep reader

class SchemaError(ValueError):
    pass


class SweepClip:
    """One clip of a C1 sweep (clips/<clip>.npz + gt/<clip>.jsonl), validated against SWEEP_SCHEMA."""

    def __init__(self, sweep, name, max_gap_s=0.25):
        sweep = Path(sweep)
        self.name = name
        self.path = sweep / 'clips' / f'{name}.npz'
        self.gt_path = sweep / 'gt' / f'{name}.jsonl'
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        if not self.gt_path.is_file():
            raise FileNotFoundError(self.gt_path)
        self.sha256 = sha256_file(self.path)
        self.gt_sha256 = sha256_file(self.gt_path)
        self.issues = []
        with np.load(self.path, allow_pickle=False) as z:
            missing = [k for k in REQUIRED_KEYS if k not in z.files]
            if missing:
                raise SchemaError(f'{self.path}: missing arrays {missing}')
            a = {k: z[k] for k in REQUIRED_KEYS + OPTIONAL_KEYS if k in z.files}
            absent = [k for k in OPTIONAL_KEYS if k not in z.files]
            if absent:
                self.issues.append(f'optional arrays absent: {absent}')
        self.split = str(a['split'])
        if str(a['clip']) != name:
            raise SchemaError(f'{self.path}: clip field {str(a["clip"])!r} != file name')
        if self.split not in ('train', 'val'):
            raise SchemaError(f'{self.path}: split {self.split!r}')
        fi = np.asarray(a['frame_idx']).astype(int).reshape(-1)
        F = len(fi)
        if F == 0:
            raise SchemaError(f'{self.path}: no frames')
        order = np.argsort(fi, kind='stable')
        if np.any(order != np.arange(F)):
            self.issues.append('frames were not ordered by frame_idx; sorted on load')
        if len(np.unique(fi)) != F:
            raise SchemaError(f'{self.path}: duplicate frame_idx')

        def take(key, shape_tail, dtype=float):
            v = np.asarray(a[key])
            if v.shape[0] != F or (shape_tail is not None and tuple(v.shape[1:]) != tuple(shape_tail)):
                raise SchemaError(f'{self.path}: {key} has shape {v.shape}, expected ({F}, {shape_tail})')
            return v[order].astype(dtype)

        self.frame_idx = fi[order]
        self.t = take('timestamp_s', ())
        if np.max(np.abs(self.t - self.frame_idx / 10.0)) > 1e-3:
            self.issues.append('timestamp_s differs from frame_idx/10 by more than 1 ms')
        self.L = take('lidar2global', (4, 4))
        self.l2e = take('lidar2ego', (4, 4))
        self.cand = take('candidates', (10, 6, 2))
        self.prefix_ms = take('prefix_ms', ()) if 'prefix_ms' in a else None
        self.step_ms = take('step_ms', (10,)) if 'step_ms' in a else None
        # Position in the sequential run (temporal state warm-up); without the field, position in the clip.
        self.run_step = take('run_step', (), int) if 'run_step' in a else np.arange(F)
        self.ego_status = take('ego_status', None) if 'ego_status' in a else None
        K = np.asarray(a['det']).shape[1] if np.asarray(a['det']).ndim == 3 else -1
        self.det = take('det', (K, 7))
        if 'det_raw' in a:
            take('det_raw', (K, 10))
        self.det_score = take('det_score', (K,))
        self.det_label = take('det_label', (K,), int)
        self.det_count = take('det_count', (), int)
        if np.any(self.det_count < 0) or np.any(self.det_count > K):
            raise SchemaError(f'{self.path}: det_count outside [0, {K}]')
        if not np.isfinite(self.L).all():
            raise SchemaError(f'{self.path}: non-finite lidar2global')
        if not np.isfinite(self.cand).all():
            self.issues.append(f'{int((~np.isfinite(self.cand)).any(axis=(2, 3)).sum())} non-finite candidate plans')
        self.gt = GTTrack.from_jsonl(self.gt_path, max_gap_s=max_gap_s)
        rows = np.array([self.gt.frame_position(f) if self.gt.frame_position(f) is not None else -1
                         for f in self.frame_idx])
        if np.any(rows < 0):
            raise SchemaError(f'{self.gt_path}: ground truth missing for {int((rows < 0).sum())} processed frames')
        self.gt_row = rows
        self.poses = [se2_from_matrix(T) for T in self.L]
        self.forward_yaw = np.array([forward_yaw_from_lidar2ego(T) for T in self.l2e])
        self.speed, self.speed_noncausal = self._ego_speed()

    def __len__(self):
        return len(self.frame_idx)

    def dets(self, k):
        n = int(self.det_count[k])
        return self.det[k, :n].astype(float), self.det_score[k, :n].astype(float), self.det_label[k, :n]

    def _ego_speed(self, max_gap_s=0.6):
        """Current ego speed: the model's own input ego_status[:, 0] (CAN-bus speed) when recorded, otherwise
        the signed forward speed of the LiDAR origin from the pose history (odometry, causal backward difference)."""
        F = len(self)
        if self.ego_status is not None and self.ego_status.ndim == 2 and self.ego_status.shape[1] >= 1 \
                and np.isfinite(self.ego_status[:, 0]).all():
            self.speed_source = 'ego_status[:, 0] (model input, CAN-bus speed)'
            return self.ego_status[:, 0].astype(float).copy(), np.zeros(F, dtype=bool)
        self.speed_source = 'lidar2global backward difference (odometry)'
        xy = self.L[:, :2, 3]
        v = np.zeros(F)
        noncausal = np.zeros(F, dtype=bool)
        for k in range(F):
            j0, j1 = (k - 1, k) if k > 0 else (0, 1)
            if F < 2 or self.t[j1] - self.t[j0] > max_gap_s or self.t[j1] <= self.t[j0]:
                if k + 1 < F and 0 < self.t[k + 1] - self.t[k] <= max_gap_s:
                    j0, j1 = k, k + 1
                else:
                    noncausal[k] = True
                    continue
            if j0 == k:
                noncausal[k] = True
            d = xy[j1] - xy[j0]
            fwd = self.poses[k][2] + self.forward_yaw[k]
            sgn = 1.0 if d[0] * math.cos(fwd) + d[1] * math.sin(fwd) >= 0 else -1.0
            v[k] = sgn * float(np.hypot(*d)) / (self.t[j1] - self.t[j0])
        return v, noncausal


def available_clips(sweep):
    return sorted(p.stem for p in (Path(sweep) / 'clips').glob('*.npz'))


def missing_expected(sweep, expected):
    have = set(available_clips(sweep))
    miss = [c for c in expected if c not in have]
    if miss:
        print(f'[warning] {len(miss)} expected clips absent from {Path(sweep) / "clips"}: {miss}', file=sys.stderr)
    return miss


def load_clips(sweep, names, expect_split, max_gap_s=0.25):
    """Load clips and enforce the train/val separation (both the fixed lists and the split field)."""
    allowed = {'train': TRAIN_CLIPS, 'val': VAL_CLIPS + EXTRA_VAL_CLIPS}[expect_split]
    out = []
    for n in names:
        if n not in allowed:
            raise SchemaError(f'{n} is not a {expect_split} clip of the FrameLease protocol')
        c = SweepClip(sweep, n, max_gap_s)
        if c.split != expect_split:
            raise SchemaError(f'{n}: split field is {c.split!r}, expected {expect_split!r}')
        out.append(c)
    return out


# ----------------------------------------------------------------------------- matching

def hungarian_match(gt_xy, gt_group, det_xy, det_group, gate_m, groups=MATCH_GROUPS):
    """Optimal one-to-one matching per group on center distance; pairs farther than the gate are dropped."""
    from scipy.optimize import linear_sum_assignment
    pairs = []
    for g in groups:
        gi = np.flatnonzero(gt_group == g)
        di = np.flatnonzero(det_group == g)
        if len(gi) == 0 or len(di) == 0:
            continue
        gate = gate_m[g] if isinstance(gate_m, dict) else float(gate_m)
        D = np.linalg.norm(gt_xy[gi][:, None, :] - det_xy[di][None, :, :], axis=-1)
        r, c = linear_sum_assignment(np.where(D <= gate, D, 1e6))
        for a, b in zip(r, c):
            if D[a, b] <= gate:
                pairs.append((int(gi[a]), int(di[b]), float(D[a, b])))
    return pairs


def greedy_match_by_score(gt_xy, gt_group, det_xy, det_group, det_score, gate_m):
    """Detection-evaluation style matching: in descending score, each detection takes the nearest free GT."""
    matched = np.zeros(len(det_xy), dtype=bool)
    used = np.zeros(len(gt_xy), dtype=bool)
    for d in np.argsort(-det_score, kind='stable'):
        gate = gate_m[det_group[d]] if isinstance(gate_m, dict) else float(gate_m)
        cand = np.flatnonzero((gt_group == det_group[d]) & ~used)
        if len(cand) == 0:
            continue
        dist = np.linalg.norm(gt_xy[cand] - det_xy[d], axis=-1)
        j = int(np.argmin(dist))
        if dist[j] <= gate:
            used[cand[j]] = True
            matched[d] = True
    return matched


def dets_world(clip, k):
    """Detections of frame k in world coordinates: dict of arrays (all valid entries, all groups)."""
    det7, score, label = clip.dets(k)
    pose = clip.poses[k]
    c, yaw, v = transform_states(pose, det7[:, 0:2], det7[:, 4], det7[:, 5:7])
    return {'xy': c.reshape(-1, 2), 'yaw': np.asarray(yaw).reshape(-1), 'v': v.reshape(-1, 2),
            'hl': 0.5 * np.abs(det7[:, 2]), 'hw': 0.5 * np.abs(det7[:, 3]), 'score': score,
            'group': resolve_groups(label) if len(label) else np.zeros(0, dtype=object), 'label': label, 'lidar': det7}


def gt_frame(clip, k, v_gt=None, v_ok=None):
    """Ground-truth actors present at processed frame k (world): dict of arrays with actor column indices."""
    g = int(clip.gt_row[k])
    cols = np.flatnonzero(clip.gt.present[g])
    out = {'col': cols, 'xy': clip.gt.xy[g, cols], 'yaw': clip.gt.yaw[g, cols], 'hl': clip.gt.hl[g, cols],
           'hw': clip.gt.hw[g, cols], 'group': clip.gt.group[cols], 'id': np.asarray(clip.gt.ids, dtype=object)[cols]}
    if v_gt is not None:
        out['v'] = v_gt[g, cols]
        out['v_ok'] = v_ok[g, cols]
    out['range'] = np.linalg.norm(out['xy'] - np.array(clip.poses[k][:2]), axis=-1)
    return out


# ----------------------------------------------------------------------------- calibration

def _range_bin(r):
    for lo, hi in zip(RANGE_BINS[:-1], RANGE_BINS[1:]):
        if lo <= r < hi:
            return f'{lo:g}-{hi:g}'
    return 'nan'


def run_calibration(sweep, clip_names=None, quantile=0.95, quantiles_out=QUANTILES, gate_m=2.0, error_range_m=50.0,
                    accel_range_m=50.0, score_threshold=0.3, low_score_floor=0.1, sigma_source='footprint',
                    min_pairs=20, base_params=None, max_gap_s=0.25, warmup_steps=DEFAULT_WARMUP_STEPS, log=print):
    """Calibrate on TRAIN clips. Returns (summary dict, {q: LeaseParams}, EgoShape, tables dict).

    Frames with run_step < warmup_steps (temporal state not yet warm) are excluded from every detection
    statistic; ego constants and ground-truth motion statistics use all frames."""
    sweep = Path(sweep)
    missing = missing_expected(sweep, TRAIN_CLIPS) if not clip_names else []
    names = list(clip_names) if clip_names else [c for c in TRAIN_CLIPS if c in set(available_clips(sweep))]
    if not names:
        raise SchemaError(f'no train clips found under {sweep / "clips"}')
    clips = load_clips(sweep, names, 'train', max_gap_s)
    base = base_params or LeaseParams()
    base = LeaseParams.from_dict({**base.to_dict(), 'score_threshold': score_threshold,
                                  'low_score_floor': low_score_floor})
    match_rows, recall_rows, prec_rows, pred_rows = [], [], [], []
    accel = {g: [] for g in MATCH_GROUPS}
    gt_speed = {g: [] for g in MATCH_GROUPS}
    ego_off, ego_hl, ego_hw, ego_yaw_err, fwd_yaws = [], [], [], [], []
    plan_forward = []
    ego_speeds = []
    warm_skipped = {}
    for clip in clips:
        log(f'[calibration] {clip.name}: {len(clip)} frames, {len(clip.gt.ids)} GT actors')
        v_gt, v_ok = clip.gt.frame_velocities()
        a_gt, a_ok = clip.gt.frame_accelerations()
        # Motion bounds from ground truth near the ego, over every recorded GT frame of the clip.
        rng_all = np.linalg.norm(clip.gt.xy - clip.gt.ego_xy[:, None, :], axis=-1)
        for g in MATCH_GROUPS:
            col = clip.gt.group == g
            m = a_ok & col[None, :] & (rng_all <= accel_range_m)
            accel[g].extend(np.linalg.norm(a_gt[m], axis=-1).tolist())
            mv = v_ok & col[None, :] & (rng_all <= RANGE_BINS[-2])
            gt_speed[g].extend(np.linalg.norm(v_gt[mv], axis=-1).tolist())
        ego_speeds.extend(np.abs(clip.speed[~clip.speed_noncausal]).tolist())
        for k in range(len(clip)):
            pose = clip.poses[k]
            g_row = int(clip.gt_row[k])
            # Ego constants and contract checks (vehicle geometry, not perception).
            off = se2_apply(se2_inverse(pose), clip.gt.ego_xy[g_row])
            ego_off.append(off)
            ego_hl.append(clip.gt.ego_hl[g_row])
            ego_hw.append(clip.gt.ego_hw[g_row])
            fwd_yaws.append(clip.forward_yaw[k])
            ego_yaw_err.append(abs(wrap_angle(clip.gt.ego_yaw[g_row] - (pose[2] + clip.forward_yaw[k]))))
            p6 = clip.cand[k, 9, -1]
            if np.isfinite(p6).all() and np.hypot(*p6) > 2.0:
                f = clip.forward_yaw[k]
                plan_forward.append(float(p6[0] * math.cos(f) + p6[1] * math.sin(f) > 0))
            if clip.run_step[k] < warmup_steps:
                warm_skipped[clip.name] = warm_skipped.get(clip.name, 0) + 1
                continue
            gt = gt_frame(clip, k, v_gt, v_ok)
            dw = dets_world(clip, k)
            rel = np.isin(dw['group'], MATCH_GROUPS)
            conf = rel & (dw['score'] >= score_threshold)
            low = rel & (dw['score'] >= low_score_floor)
            within = gt['range'] < RANGE_BINS[-2]
            gxy, ggrp = gt['xy'][within], gt['group'][within]
            gidx = np.flatnonzero(within)
            pairs_conf = hungarian_match(gxy, ggrp, dw['xy'][conf], dw['group'][conf], gate_m)
            pairs_low = hungarian_match(gxy, ggrp, dw['xy'][low], dw['group'][low], gate_m)
            hit_conf = np.zeros(len(gidx), dtype=bool)
            hit_low = np.zeros(len(gidx), dtype=bool)
            for a, _, _ in pairs_conf:
                hit_conf[a] = True
            for a, _, _ in pairs_low:
                hit_low[a] = True
            for a in range(len(gidx)):
                recall_rows.append((ggrp[a], _range_bin(gt['range'][gidx[a]]), hit_conf[a], hit_low[a]))
            # Precision versus score (all relevant detections above the lowest score bin, within range).
            pr = rel & (dw['score'] >= SCORE_BINS[0]) & (np.linalg.norm(dw['xy'] - np.array(pose[:2]), axis=-1)
                                                          < RANGE_BINS[-2])
            if pr.any():
                tp = greedy_match_by_score(gxy, ggrp, dw['xy'][pr], dw['group'][pr], dw['score'][pr], gate_m)
                for s, grp, ok in zip(dw['score'][pr], dw['group'][pr], tp):
                    prec_rows.append((grp, float(s), bool(ok)))
            # Errors of matched confident detections and constant-velocity prediction error versus staleness.
            if not pairs_conf:
                continue
            ci = np.flatnonzero(conf)
            times = clip.t[k] + np.asarray(DELTAS_S)
            fxy, fyaw, fhl, fhw, fvalid = clip.gt.actors_at(times)
            for a, b, dist in pairs_conf:
                gi = gidx[a]
                di = ci[b]
                col = gt['col'][gi]
                grp = gt['group'][gi]
                rng_m = float(gt['range'][gi])
                dbox = box_corners(dw['xy'][di], dw['yaw'][di], dw['hl'][di], dw['hw'][di])
                gbox = box_corners(gt['xy'][gi], gt['yaw'][gi], gt['hl'][gi], gt['hw'][gi])
                head = abs(wrap_angle(dw['yaw'][di] - gt['yaw'][gi]))
                vg = gt['v'][gi] if gt['v_ok'][gi] else np.array([np.nan, np.nan])
                row = {'clip': clip.name, 'frame_idx': int(clip.frame_idx[k]), 'gt_id': str(gt['id'][gi]),
                       'group': grp, 'score': float(dw['score'][di]), 'label': int(dw['label'][di]), 'range_m': rng_m,
                       'center_err_m': dist, 'footprint_err_m': float(hausdorff_convex(dbox, gbox)),
                       'vel_err_mps': float(np.linalg.norm(dw['v'][di] - vg)),
                       'speed_err_mps': float(abs(np.linalg.norm(dw['v'][di]) - np.linalg.norm(vg))),
                       'gt_speed_mps': float(np.linalg.norm(vg)), 'heading_err_rad': float(head),
                       'orient_err_rad': float(min(head, math.pi - head)),
                       'length_err_m': float(2 * dw['hl'][di] - 2 * gt['hl'][gi]),
                       'width_err_m': float(2 * dw['hw'][di] - 2 * gt['hw'][gi]),
                       'vel_cos': float(np.dot(dw['v'][di], vg) / max(np.linalg.norm(dw['v'][di]) * np.linalg.norm(vg), 1e-9))}
                match_rows.append(row)
                if rng_m > error_range_m:
                    continue
                for ti, D in enumerate(DELTAS_S):
                    if not fvalid[ti, col]:
                        continue
                    pbox = box_corners(dw['xy'][di] + dw['v'][di] * D, dw['yaw'][di], dw['hl'][di], dw['hw'][di])
                    tbox = box_corners(fxy[ti, col], fyaw[ti, col], fhl[ti, col], fhw[ti, col])
                    pred_rows.append({'group': grp, 'delta_s': D, 'footprint_err_m': float(hausdorff_convex(pbox, tbox)),
                                      'center_err_m': float(np.linalg.norm(dw['xy'][di] + dw['v'][di] * D - fxy[ti, col]))})

    # ---------------------------------------------------------------- statistics
    err_keys = ('center_err_m', 'footprint_err_m', 'vel_err_mps', 'speed_err_mps', 'heading_err_rad', 'orient_err_rad',
                'length_err_m', 'width_err_m')
    errors = {}
    for g in MATCH_GROUPS:
        rows = [r for r in match_rows if r['group'] == g and r['range_m'] <= error_range_m]
        errors[g] = {key: quantiles([r[key] for r in rows]) for key in err_keys}
        errors[g]['n_pairs'] = len(rows)
    recall = []
    for g in MATCH_GROUPS:
        for lo, hi in zip(RANGE_BINS[:-1], RANGE_BINS[1:]):
            b = f'{lo:g}-{hi:g}'
            sel = [r for r in recall_rows if r[0] == g and r[1] == b]
            n = len(sel)
            recall.append({'group': g, 'range_bin_m': b, 'range_lo_m': lo, 'range_hi_m': hi, 'n_gt': n,
                           'recall_confident': (sum(r[2] for r in sel) / n) if n else None,
                           'recall_low_floor': (sum(r[3] for r in sel) / n) if n else None})
    precision = []
    for g in MATCH_GROUPS:
        for lo, hi in zip(SCORE_BINS[:-1], SCORE_BINS[1:]):
            sel = [r for r in prec_rows if r[0] == g and lo <= r[1] < hi]
            precision.append({'group': g, 'score_lo': lo, 'score_hi': min(hi, 1.0), 'n_det': len(sel),
                              'precision': (sum(r[2] for r in sel) / len(sel)) if sel else None})
    accel_q = {g: quantiles(accel[g]) for g in MATCH_GROUPS}
    speed_q = {g: quantiles(gt_speed[g]) for g in MATCH_GROUPS}

    # ---------------------------------------------------------------- ego constants and contract checks
    ego_off = np.asarray(ego_off)
    fwd = float(np.arctan2(np.median(np.sin(fwd_yaws)), np.median(np.cos(fwd_yaws))))
    ego = EgoShape(float(np.median(ego_hl)), float(np.median(ego_hw)),
                   (float(np.median(ego_off[:, 0])), float(np.median(ego_off[:, 1]))), fwd)
    spread = float(np.quantile(np.linalg.norm(ego_off - np.median(ego_off, axis=0), axis=-1), 0.95))
    veh = [r for r in match_rows if r['group'] == 'vehicle' and r['range_m'] <= error_range_m]
    moving = [r for r in veh if r['gt_speed_mps'] > 2.0]
    checks = {
        'ego_center_offset_lidar_xy': {'value': list(ego.center_offset_xy), 'expected': 'about (0, 0.38) for B2D',
                                       'pass': bool(abs(ego.center_offset_xy[0]) < 0.3 and 0.0 < ego.center_offset_xy[1] < 1.0)},
        'ego_center_offset_spread_q95_m': {'value': spread, 'expected': '< 0.10 (rigid mounting)', 'pass': spread < 0.10},
        'ego_forward_yaw_in_lidar_rad': {'value': fwd, 'expected': 'pi/2 (LiDAR +y forward)',
                                         'pass': abs(wrap_angle(fwd - math.pi / 2)) < 0.05},
        'gt_ego_yaw_vs_lidar_forward_median_abs_rad': {'value': float(np.median(ego_yaw_err)), 'expected': '< 0.05',
                                                       'pass': float(np.median(ego_yaw_err)) < 0.05},
        'final_plan_points_forward_fraction': {'value': float(np.mean(plan_forward)) if plan_forward else None,
                                               'n': len(plan_forward), 'expected': '> 0.9',
                                               'pass': bool(plan_forward) and float(np.mean(plan_forward)) > 0.9},
        'moving_vehicle_orientation_err_median_rad': {
            'value': float(np.median([r['orient_err_rad'] for r in moving])) if moving else None, 'n': len(moving),
            'expected': '< 0.17 (yaw convention)',
            'pass': bool(moving) and float(np.median([r['orient_err_rad'] for r in moving])) < 0.17},
        'moving_vehicle_velocity_cosine_median': {
            'value': float(np.median([r['vel_cos'] for r in moving])) if moving else None, 'n': len(moving),
            'expected': '> 0.8 (velocity frame)', 'pass': bool(moving) and float(np.median([r['vel_cos'] for r in moving])) > 0.8},
    }

    # ---------------------------------------------------------------- parameters per quantile
    params_by_q, param_meta, params_env, env_meta = {}, {}, {}, {}
    for q in sorted(set(list(quantiles_out) + [quantile])):
        sig, vb, ab, notes = {}, {}, {}, []
        for g in MATCH_GROUPS:
            rows = [r for r in match_rows if r['group'] == g and r['range_m'] <= error_range_m]
            src = 'footprint_err_m' if sigma_source == 'footprint' else 'center_err_m'
            if len(rows) >= min_pairs:
                sig[g] = float(np.quantile([r[src] for r in rows], q))
                vv = [r['vel_err_mps'] for r in rows if np.isfinite(r['vel_err_mps'])]
                vb[g] = float(np.quantile(vv, q)) if len(vv) >= min_pairs else None
            else:
                sig[g] = vb[g] = None
                notes.append(f'{g}: only {len(rows)} matched pairs (< {min_pairs}); bound borrowed')
            ab[g] = float(np.quantile(accel[g], q)) if len(accel[g]) >= min_pairs else None
            if ab[g] is None:
                notes.append(f'{g}: too few GT acceleration samples; bound borrowed')
        for name, d, default in (('sigma_m', sig, DEFAULT_SIGMA_M), ('vbar_mps', vb, DEFAULT_VBAR_MPS),
                                 ('abar_mps2', ab, DEFAULT_ABAR_MPS2)):
            have = [v for v in d.values() if v is not None]
            for g in MATCH_GROUPS:
                if d[g] is None:
                    d[g] = max(have) if have else default[g]
                    if not have:
                        notes.append(f'{name}[{g}]: UNCALIBRATED placeholder')
            d['other'] = max(d['vehicle'], d['pedestrian'])  # no ground-truth class: conservative maximum
        p = LeaseParams.from_dict({**base.to_dict(), 'sigma_m': sig, 'vbar_mps': vb, 'abar_mps2': ab})
        params_by_q[q] = p
        param_meta[q] = {'quantile': q, 'sigma_source': sigma_source, 'abar_source': 'gt_acceleration_quantile',
                         'notes': notes, 'other_group': 'max(vehicle, pedestrian); no ground-truth class to calibrate against'}
        # Envelope alternative: smallest abar with B(D) >= the measured q-quantile of the constant-velocity
        # footprint error at every calibrated staleness D (sigma and vbar unchanged).
        ab_env, env_notes = {}, []
        for g in MATCH_GROUPS:
            need = []
            for D in DELTAS_S[1:]:
                e = [r['footprint_err_m'] for r in pred_rows if r['group'] == g and r['delta_s'] == D]
                if len(e) >= min_pairs:
                    need.append(max(0.0, 2.0 * (float(np.quantile(e, q)) - sig[g] - vb[g] * D) / (D * D)))
            ab_env[g] = max(need) if need else None
            if ab_env[g] is None:
                env_notes.append(f'{g}: too few prediction-error samples; abar borrowed')
        have = [v for v in ab_env.values() if v is not None]
        for g in MATCH_GROUPS:
            if ab_env[g] is None:
                ab_env[g] = max(have) if have else ab[g]
        ab_env['other'] = max(ab_env['vehicle'], ab_env['pedestrian'])
        params_env[q] = LeaseParams.from_dict({**base.to_dict(), 'sigma_m': sig, 'vbar_mps': vb, 'abar_mps2': ab_env})
        env_meta[q] = {**param_meta[q], 'abar_source': 'envelope of measured CV footprint error quantile over D',
                       'notes': notes + env_notes}

    # ---------------------------------------------------------------- coverage of B(D) and the undetected-agent rule
    chosen = params_by_q[quantile]
    coverage = []
    for g in MATCH_GROUPS:
        for D in DELTAS_S:
            e = np.array([r['footprint_err_m'] for r in pred_rows if r['group'] == g and r['delta_s'] == D])
            ec = np.array([r['center_err_m'] for r in pred_rows if r['group'] == g and r['delta_s'] == D])
            bnd = float(chosen.bound(g, D))
            coverage.append({'group': g, 'delta_s': D, 'n': int(len(e)), 'bound_m': bnd,
                             'coverage_footprint': float(np.mean(e <= bnd)) if len(e) else None,
                             'coverage_center': float(np.mean(ec <= bnd)) if len(ec) else None,
                             **{f'footprint_err_q{int(round(q * 100))}_m': (float(np.quantile(e, q)) if len(e) else None)
                                for q in QUANTILES}})
    undetected = {}
    v_ego99 = float(np.quantile(ego_speeds, 0.99)) if ego_speeds else None
    for g in MATCH_GROUPS:
        reliable = 0.0
        for r in [x for x in recall if x['group'] == g]:
            if r['n_gt'] < 20 or r['recall_confident'] is None or r['recall_confident'] < 0.9 or not math.isfinite(r['range_hi_m']):
                break
            reliable = r['range_hi_m']
        v_agent99 = speed_q[g]['q99']
        v_close = (v_agent99 or 0.0) + (v_ego99 or 0.0)
        h = max(0.0, (reliable - ego.half_length_m - chosen.d_safe_m) / v_close) if v_close > 0 else None
        undetected[g] = {'reliable_range_m(recall>=0.9 in every bin from 0)': reliable, 'agent_speed_q99_mps': v_agent99,
                         'ego_speed_q99_mps': v_ego99, 'closing_speed_mps': v_close, 'admissible_h_max_s': h,
                         'h_max_s': chosen.h_max_s,
                         'h_max_covers_undetected': (h is not None and chosen.h_max_s <= h)}

    summary = {
        'sweep': str(sweep), 'synthetic_sweep': is_synthetic(sweep), 'clips': names, 'split': 'train',
        'clip_sha256': {c.name: c.sha256 for c in clips}, 'gt_sha256': {c.name: c.gt_sha256 for c in clips},
        'clip_issues': {c.name: c.issues for c in clips if c.issues},
        'frames': int(sum(len(c) for c in clips)), 'class_group_source': class_group_map()[1],
        'expected_train_clips_missing': missing, 'warmup_frames_excluded': warm_skipped,
        'ego_speed_source': {c.name: c.speed_source for c in clips},
        'settings': {'quantile': quantile, 'gate_m': gate_m, 'error_range_m': error_range_m,
                     'warmup_steps': warmup_steps, 'gt_max_gap_s': max_gap_s,
                     'accel_range_m': accel_range_m, 'score_threshold': score_threshold,
                     'low_score_floor': low_score_floor, 'sigma_source': sigma_source, 'min_pairs': min_pairs,
                     'deltas_s': list(DELTAS_S)},
        'errors_by_group': errors, 'gt_acceleration_mps2': accel_q, 'gt_speed_mps': speed_q,
        'recall_vs_range': recall, 'precision_vs_score': precision, 'bound_coverage': coverage,
        'undetected_agent_rule': undetected, 'contract_checks': checks,
        'contract_checks_all_pass': all(v['pass'] for v in checks.values()),
        'ego_shape': ego.to_dict(), 'ego_shape_reference_B2D_constant': B2D_EGO.to_dict(),
        'lease_params': {f'q{int(round(q * 100))}': p.to_dict() for q, p in params_by_q.items()},
        'lease_params_envelope': {f'q{int(round(q * 100))}': p.to_dict() for q, p in params_env.items()},
        'chosen_quantile': quantile,
        'scope': 'OFFLINE calibration on TRAIN clips; ground truth used only for matching and motion statistics',
    }
    for g in MATCH_GROUPS:   # coverage of the envelope alternative at the chosen quantile
        for row in coverage:
            if row['group'] == g:
                e = np.array([r['footprint_err_m'] for r in pred_rows if r['group'] == g and r['delta_s'] == row['delta_s']])
                row['bound_envelope_m'] = float(params_env[quantile].bound(g, row['delta_s']))
                row['coverage_footprint_envelope'] = float(np.mean(e <= row['bound_envelope_m'])) if len(e) else None
    tables = {'matches': match_rows, 'recall': recall, 'precision': precision, 'coverage': coverage,
              'param_meta': param_meta, 'params_envelope': params_env, 'envelope_meta': env_meta}
    return summary, params_by_q, ego, tables


# ----------------------------------------------------------------------------- figure

def calibration_figure(summary, out_base):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from framelease_v2.c2_eval import PALETTE, style_axes
    colors = {'vehicle': PALETTE[0], 'pedestrian': PALETTE[1]}
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.4), constrained_layout=True)
    ax = axes[0]
    for g in MATCH_GROUPS:
        rows = [r for r in summary['recall_vs_range'] if r['group'] == g and r['n_gt'] and math.isfinite(r['range_hi_m'])]
        if not rows:
            continue
        x = [0.5 * (r['range_lo_m'] + r['range_hi_m']) for r in rows]
        ax.plot(x, [r['recall_confident'] for r in rows], marker='o', ms=4, lw=2, color=colors[g], label=g)
        ax.plot(x, [r['recall_low_floor'] for r in rows], ls='--', lw=1.5, color=colors[g], alpha=0.7)
    ax.set_xlabel('range from LiDAR (m)')
    ax.set_ylabel('recall')
    ax.set_ylim(0, 1.02)
    ax.set_title('Detection recall (solid: score >= threshold; dashed: >= floor)', fontsize=9, loc='left')
    ax.legend(frameon=False, fontsize=8)
    style_axes(ax)
    ax = axes[1]
    q = summary['chosen_quantile']
    key = f'footprint_err_q{int(round(q * 100))}_m'
    for g in MATCH_GROUPS:
        rows = [r for r in summary['bound_coverage'] if r['group'] == g and r['n']]
        if not rows:
            continue
        D = [r['delta_s'] for r in rows]
        ax.plot(D, [r[key] for r in rows], marker='o', ms=4, lw=2, color=colors[g], label=f'{g}: measured q{int(round(q * 100))}')
        lp = summary['lease_params'][f'q{int(round(q * 100))}']
        Df = np.linspace(0.0, max(D), 101)
        Bf = lp['vbar_mps'][g] * Df + 0.5 * lp['abar_mps2'][g] * Df ** 2 + lp['sigma_m'][g]
        ax.plot(Df, Bf, ls='--', lw=1.5, color=colors[g], label=f'{g}: bound B(D)')
    ax.set_xlabel('staleness D (s)')
    ax.set_ylabel('CV footprint error (m)')
    ax.set_title('Constant-velocity prediction error vs bound', fontsize=9, loc='left')
    ax.legend(frameon=False, fontsize=8)
    style_axes(ax)
    if summary.get('synthetic_sweep'):
        fig.suptitle('SYNTHETIC DATA - pipeline test only', color='#b00020', fontsize=10)
    for ext in ('png', 'pdf'):
        fig.savefig(f'{out_base}.{ext}', dpi=200)
    plt.close(fig)


# ----------------------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sweep', required=True, type=Path, help='outputs/framelease_v2/c1_sweep/<run_name>')
    ap.add_argument('--clips', default='', help='comma list (default: all TRAIN clips present in the sweep)')
    ap.add_argument('--quantile', type=float, default=0.95)
    ap.add_argument('--gate-m', type=float, default=2.0, help='center-distance matching gate')
    ap.add_argument('--error-range-m', type=float, default=50.0, help='only matches within this range set bounds')
    ap.add_argument('--accel-range-m', type=float, default=50.0)
    ap.add_argument('--score-threshold', type=float, default=0.3)
    ap.add_argument('--low-score-floor', type=float, default=0.1)
    ap.add_argument('--sigma-source', choices=('footprint', 'center'), default='footprint')
    ap.add_argument('--min-pairs', type=int, default=20)
    ap.add_argument('--warmup-steps', type=int, default=DEFAULT_WARMUP_STEPS,
                    help='exclude frames with run_step below this (temporal detector warm-up)')
    ap.add_argument('--gt-max-gap-s', type=float, default=0.25, help='max GT frame gap bridged by interpolation')
    ap.add_argument('--output-root', type=Path, default=ROOT / 'outputs/framelease_v2/c2_calibration')
    ap.add_argument('--run-name', default='')
    ap.add_argument('--no-figure', action='store_true')
    args = ap.parse_args(argv)
    sweep = args.sweep.resolve()
    name = args.run_name or time.strftime('run_%Y%m%dT%H%M%S') + ('_SYNTHETIC' if is_synthetic(sweep) else '')
    out = args.output_root / name
    out.mkdir(parents=True, exist_ok=False)
    started = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    clips = [c for c in args.clips.split(',') if c] or None
    summary, params_by_q, ego, tables = run_calibration(
        sweep, clips, args.quantile, QUANTILES, args.gate_m, args.error_range_m, args.accel_range_m,
        args.score_threshold, args.low_score_floor, args.sigma_source, args.min_pairs,
        max_gap_s=args.gt_max_gap_s, warmup_steps=args.warmup_steps)
    here = Path(__file__).resolve().parent
    config = {'argv': sys.argv if argv is None else ['calibration.py', *argv], 'started': started,
              'finished': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'git_commit': git_commit(),
              'script_sha256': {p: sha256_file(here / p) for p in ('calibration.py', 'lease.py', 'geometry.py')},
              'sweep': str(sweep), 'sweep_config': sweep_config(sweep), 'synthetic_sweep': summary['synthetic_sweep'],
              'clips': summary['clips'], 'clip_sha256': summary['clip_sha256']}
    write_json(out / 'config.json', config)
    write_json(out / 'calibration.json', summary)
    write_csv(out / 'matches.csv', tables['matches'])
    write_csv(out / 'recall_vs_range.csv', tables['recall'])
    write_csv(out / 'precision_vs_score.csv', tables['precision'])
    write_csv(out / 'bound_coverage.csv', tables['coverage'])
    for q, p in params_by_q.items():
        meta = {**tables['param_meta'][q], 'sweep': str(sweep), 'clips': summary['clips'], 'run_dir': str(out),
                'synthetic_sweep': summary['synthetic_sweep'], 'created': started}
        save_lease_params(out / f'lease_params_q{int(round(q * 100))}.json', p, ego, meta)
        if abs(q - args.quantile) < 1e-12:
            save_lease_params(out / 'lease_params.json', p, ego, meta)
            emeta = {**tables['envelope_meta'][q], 'sweep': str(sweep), 'clips': summary['clips'], 'run_dir': str(out),
                     'synthetic_sweep': summary['synthetic_sweep'], 'created': started}
            save_lease_params(out / f'lease_params_q{int(round(q * 100))}_envelope.json', tables['params_envelope'][q],
                              ego, emeta)
    if not args.no_figure:
        calibration_figure(summary, out / 'calibration_figure')
    print(json.dumps(clean_json({'run_dir': str(out), 'frames': summary['frames'], 'clips': summary['clips'],
                                 'contract_checks_all_pass': summary['contract_checks_all_pass'],
                                 'lease_params': summary['lease_params'][f'q{int(round(args.quantile * 100))}']}), indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
