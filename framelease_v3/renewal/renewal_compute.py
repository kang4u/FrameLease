#!/usr/bin/env python3
"""Offline lease-renewal study, stage A (CPU only; no model, no GPU, no CARLA).

    cd /home/kang/Desktop/DAC
    OMP_NUM_THREADS=1 .conda-unidrive-linux/bin/python -I -B framelease_v3/renewal/renewal_compute.py \
        --out-dir outputs/framelease_v3/renewal_offline/run_20261110

For every evaluated plan (VAL clip frame k after the detector warm-up with 3 s of future ground truth, depths 1 and
10; the frame set of gate2_20261109) this stage computes, once, everything the renewal simulation (stage B,
renewal_analyze.py) needs:

* lease crossings tau*_{k,o} for o = 0 ... 29: the gate2 suffix lease of plan k evaluated with the perception of frame
  j = k + o (o = 0: the plan's own frame, i.e. exactly gate2's tau*). Frame j's boxes are moved into plan k's capture
  LiDAR frame with the two lidar2global poses (SE(2)), propagated with constant velocity from t_j and inflated by the
  envelope B(tau) with tau measured from t_j; the plan footprint is the suffix of plan k from t_j to t_k + 3 s.
  tau* is the first tau with min_agents margin <= delta (exact gate2 kernels: agent_leases' quadratic crossing for the
  isotropic forms, linear interpolation of the exact anisotropic margins), capped at T_rem = 3 s - (t_j - t_k).
  Perception sources: 'model' = the sweep's decoded detections (score >= 0.1, low-confidence rows count as real,
  vehicle / pedestrian), 'oracle' = ground-truth boxes of every vehicle / walker present at t_j with the recorded
  finite-difference velocity (upper bound; envelopes calibrated LOCO on ground-truth constant-velocity residuals).
  Validity variants: 'std' (gate2) and 'ra' (responsibility-aware definition change, see RA_RULE).
* envelope configurations: B0 (none) and E0 / E1 / E2 at q50, q60, q70, q80, q90, q95, q99, q99.5. Model source: the
  stored LOCO fold envelopes (gate2_20261109/envelopes/*_LOCO.json for q80-q99.5, risk_frontier_20261109/
  envelopes_new_quantiles.json for q50-q70). Oracle source: fitted here with framelease_v3.envelopes on ground-truth
  constant-velocity residuals, LOCO (each held-out VAL clip calibrated on the other 19 clips).
* the realized clearance series of plan k against the ground truth (c2_eval.observed_validity machinery: exact
  polygon distances, non-reactive replay), standard and responsibility-aware, with the binding actor per grid point;
* the detection status of every ground-truth actor in every frame (absent / undetected / low-confidence / confident,
  c2_eval.detection_status), and a binding code of the agent that ends each lease.

Outputs (resumable; one file per clip, written atomically): <out>/stageA/<clip>.npz, <out>/oracle_envelopes.json,
<out>/stageA_config.json. framelease_v2 and the other framelease_v3 modules are imported read-only.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault('OMP_NUM_THREADS', '1')
sys.dont_write_bytecode = True

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import platform  # noqa: E402
import time  # noqa: E402
from collections import Counter  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from multiprocessing import get_context  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v2.c2_eval import detection_status  # noqa: E402
from framelease_v2.calibration import SweepClip, clean_json, gt_frame, sha256_file, write_json  # noqa: E402
from framelease_v2.geometry import (box_corners, convex_distance, first_crossing_time, hausdorff_convex,  # noqa: E402
                                    se2_apply, se2_compose, se2_inverse, time_grid, transform_states)
from framelease_v2.lease import ego_corners_along_plan, load_ego_shape, resolve_groups  # noqa: E402
from framelease_v3 import envelopes as envmod  # noqa: E402
from framelease_v3 import suffix_lease_eval as sle  # noqa: E402

GATE2 = ROOT / 'outputs/framelease_v3/gate2_offline/gate2_20261109'
RF = ROOT / 'outputs/framelease_v3/gate2_offline/risk_frontier_20261109'
T_PRED, DT, D_SAFE, DELTA = sle.T_PRED, sle.DT, sle.D_SAFE, sle.DELTA
FRAME_DT = 0.1
STEP = int(round(FRAME_DT / DT))          # plan grid steps per recorded frame (2)
N_OFF = 30                                # renewal frame offsets o = 0 ... 29 (t_j - t_k = 0 ... 2.9 s)
TAU = time_grid(T_PRED, DT)               # 61 points
M_FULL = len(TAU)
DEPTHS = (1, 10)
QS = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 0.995)
OLD_Q = (0.8, 0.9, 0.95, 0.99, 0.995)
FAMS = ('E0', 'E1', 'E2')
CONFIGS = ['B0'] + [f'{f}_q{sle.qtag(q)}' for f in FAMS for q in QS]
N_ISO = 1 + len(QS)                       # B0 + E0 (isotropic kernels) come first, then E1 and E2 (tables)
VARIANTS = ('std', 'ra')
SOURCES = ('model', 'oracle')
GROUP_ID = envmod.GROUP_ID
RA_COS = 0.5                              # heading axes within 60 degrees
PRUNE_PAD = 1.0                           # agents whose centre lower bound minus the largest envelope exceeds
                                          # d_safe + delta + PRUNE_PAD at every tau cannot bind (exact pruning)
VAL_PAD = 5.0                             # c2_eval.observed_validity's pad_m
SCHEMA = 'framelease_v3.renewal.stageA/1'
RA_RULE = ('responsibility-aware validity (definition change, RSS-motivated): a CONTACT INTERVAL of a vehicle agent is '
           'ignored when the agent approaches from behind. A contact interval is a maximal run of grid times at which '
           'the agent is within the conflict distance of the planned ego box (lease: envelope-inflated margin <= delta '
           'on top of d_safe, per envelope configuration; realized conflict: ground-truth clearance <= d_safe). It is '
           'ignored iff at its first grid time (i) the agent box centre lies behind the rear edge line of the planned '
           'ego box, (c_agent - c_ego) . u_ego < -half_length_ego, and (ii) the agent heading axis is within 60 deg '
           'of the ego heading axis, |cos(yaw_agent - yaw_ego)| >= 0.5. The whole interval is ignored (a constant-'
           'velocity follower otherwise "drives through" the ego and would count again once its centre passes the '
           'rear edge); a later interval that starts alongside or ahead counts. Applied to the lease (detected / '
           'oracle boxes at their constant-velocity positions, detected heading) and to the realized conflict '
           '(ground-truth boxes and headings). Pedestrians are never ignored.')
# binding code of the agent that ends a lease: 0 = none (no crossing before the plan end), 127 = invalid perception
# (non-finite relevant detection), else 1 + pos * 8 + moving * 4 + pedestrian * 2 + gt_within_2m with pos 0 ahead,
# 1 alongside, 2 behind of the planned ego box at t_j (box centre along the ego heading).
POS_NAMES = ('ahead', 'alongside', 'behind')
STATUS_NAMES = ('absent', 'undetected', 'low_confidence', 'confident')

_SPEC = {}
_CLIP = {}
_SAMPLES = {}


def decode_bind(code):
    code = int(code)
    if code == 0:
        return 'none'
    if code == 127:
        return 'invalid'
    c = code - 1
    pos, rest = divmod(c, 8)
    mov, rest = divmod(rest, 4)
    ped, tp = divmod(rest, 2)
    return f'{POS_NAMES[pos]}/{"moving" if mov else "static"}/{"pedestrian" if ped else "vehicle"}/{"gt" if tp else "nogt"}'


# ----------------------------------------------------------------------------- envelopes

def iso_pack(e):
    return {'kind': 'iso', 'sig': np.array([float(e['sigma_m'][g]) for g in envmod.GROUPS]),
            'vb': np.array([float(e['vbar_mps'][g]) for g in envmod.GROUPS]),
            'ab': np.array([float(e['abar_mps2'][g]) for g in envmod.GROUPS])}


def zero_pack():
    return {'kind': 'iso', 'sig': np.zeros(2), 'vb': np.zeros(2), 'ab': np.zeros(2)}


def aniso_from_json(e, fam):
    T = np.zeros((len(envmod.GROUPS), len(envmod.BIN_NAMES), M_FULL, 2))
    for g, gi in GROUP_ID.items():
        for b, bn in enumerate(envmod.BIN_NAMES):
            key = g if fam == 'E1' else f'{g}/{bn}'
            T[gi, b, :, 0] = np.asarray(e['B_lon_m'][key], dtype=float)
            T[gi, b, :, 1] = np.asarray(e['B_lat_m'][key], dtype=float)
    return {'kind': 'aniso', 'table': T}


def load_model_envelopes(val):
    """Stored LOCO fold envelopes (gate2 q80-q99.5, risk_frontier q50-q70): {clip: {config: pack}}."""
    out = {h: {'B0': zero_pack()} for h in val}
    nq = json.loads((RF / 'envelopes_new_quantiles.json').read_text(encoding='utf-8'))['envelopes']
    for fam in FAMS:
        for q in QS:
            key = f'{fam}_q{sle.qtag(q)}'
            if q in OLD_Q:
                payload = json.loads((GATE2 / 'envelopes' / f'{key}_LOCO.json').read_text(encoding='utf-8'))
                for h in val:
                    e = payload['folds'][h]['envelope']
                    out[h][key] = iso_pack(e) if fam == 'E0' else aniso_from_json(e, fam)
            else:
                src = nq[f'{fam}|{q}']
                for h in val:
                    e = src[h]
                    out[h][key] = iso_pack(e) if fam == 'E0' else {'kind': 'aniso',
                                                                    'table': np.asarray(e['table'], dtype=float)}
    return out


def oracle_clip_samples(clip, tau, error_range_m=50.0, warmup_steps=sle.WARMUP_STEPS):
    """Ground-truth constant-velocity residual samples (envelopes.clip_samples with GT boxes as 'detections').

    Every ground-truth vehicle / walker present at frame k within error_range_m of the LiDAR with a velocity estimate
    (the recorded finite-difference velocity_xy) is moved with that velocity and compared with its own ground-truth box
    at t_k + tau. tau = 0 errors are zero by construction (fp0 = vel_err = 0)."""
    tau = np.asarray(tau, dtype=float)
    M = len(tau)
    v_gt, v_ok = clip.gt.frame_velocities()
    acc = {k: [] for k in ('group', 'speed', 'fp0', 'vel_err', 'range', 'score', 'iso', 'lon', 'lat')}
    for k in range(len(clip)):
        if clip.run_step[k] < warmup_steps:
            continue
        gt = gt_frame(clip, k, v_gt, v_ok)
        sel = (gt['range'] <= error_range_m) & gt['v_ok']
        if not sel.any():
            continue
        cols = gt['col'][sel]
        fxy, fyaw, fhl, fhw, fvalid = clip.gt.actors_at(clip.t[k] + tau)
        gxy = np.transpose(fxy[:, cols], (1, 0, 2))
        gbox = box_corners(gxy, fyaw[:, cols].T, fhl[:, cols].T, fhw[:, cols].T)
        valid = fvalid[:, cols].T
        c, yaw, v = gt['xy'][sel], gt['yaw'][sel], gt['v'][sel]
        hl, hw = gt['hl'][sel], gt['hw'][sel]
        pc = c[:, None, :] + tau[None, :, None] * v[:, None, :]
        pbox = box_corners(pc, yaw[:, None], hl[:, None], hw[:, None])
        iso = np.asarray(hausdorff_convex(pbox, gbox), dtype=float)
        lon, lat = envmod.containment_residual(gbox, pc, yaw[:, None], hl[:, None], hw[:, None])
        lon, lat = np.array(lon, dtype=float), np.array(lat, dtype=float)
        for arr in (iso, lon, lat):
            arr[~valid] = np.nan
        P = len(cols)
        acc['group'].append(np.array([GROUP_ID[g] for g in gt['group'][sel]], dtype=np.int8))
        acc['speed'].append(np.linalg.norm(v, axis=-1))
        acc['fp0'].append(np.zeros(P))
        acc['vel_err'].append(np.zeros(P))
        acc['range'].append(gt['range'][sel])
        acc['score'].append(np.ones(P))
        acc['iso'].append(iso)
        acc['lon'].append(lon)
        acc['lat'].append(lat)
    out = {}
    for key, parts in acc.items():
        out[key] = (np.concatenate(parts, axis=0) if parts else
                    np.zeros((0, M) if key in ('iso', 'lon', 'lat') else (0,), dtype=float))
    return out


def oracle_samples_job(name):
    clip = SweepClip(sle.SWEEP, name)
    return name, oracle_clip_samples(clip, TAU)


def oracle_fit_job(task):
    h, names = task
    S = envmod.pool_samples(_SAMPLES, names)
    out = {}
    for q in QS:
        out[f'E0_q{sle.qtag(q)}'] = envmod.fit_iso(S, q, TAU)
        out[f'E1_q{sle.qtag(q)}'] = envmod.fit_aniso(S, q, TAU, motion_bins=False)
        out[f'E2_q{sle.qtag(q)}'] = envmod.fit_aniso(S, q, TAU, motion_bins=True)
    return h, out


def oracle_env_to_json(env):
    if env['kind'] == 'iso':
        return {k: env[k] for k in ('kind', 'q', 'sigma_m', 'vbar_mps', 'abar_mps2', 'd_grid_s', 'n_pairs', 'notes')}
    return {'kind': 'aniso', 'q': env['q'], 'motion_bins': env['motion_bins'], 'n_pairs': env['n_pairs'],
            'table': env['table'].tolist()}


def oracle_pack(e):
    if e['kind'] == 'iso':
        return iso_pack(e)
    return {'kind': 'aniso', 'table': np.asarray(e['table'], dtype=float)}


def stack_packs(packs):
    """{config: pack} in CONFIGS order -> arrays for the kernels."""
    iso = [packs[c] for c in CONFIGS[:N_ISO]]
    an = [packs[c] for c in CONFIGS[N_ISO:]]
    assert all(p['kind'] == 'iso' for p in iso) and all(p['kind'] == 'aniso' for p in an)
    SIG = np.stack([p['sig'] for p in iso])
    VB = np.stack([p['vb'] for p in iso])
    AB = np.stack([p['ab'] for p in iso])
    TAB = np.stack([p['table'] for p in an])                                       # (C_an, G, NB, M, 2)
    # largest envelope radius per group and tau over all configurations (exact agent pruning)
    Biso = VB[:, :, None] * TAU[None, None, :] + 0.5 * AB[:, :, None] * TAU[None, None, :] ** 2 + SIG[:, :, None]
    Ban = np.hypot(TAB[..., 0], TAB[..., 1]).max(axis=2)                            # (C_an, G, M)
    BMAX = np.maximum(Biso.max(axis=0), Ban.max(axis=0))                            # (G, M)
    return {'SIG': SIG, 'VB': VB, 'AB': AB, 'TAB': TAB, 'BMAX': BMAX}


# ----------------------------------------------------------------------------- kernels

def contact_starts(bad, behind):
    """First points of contact intervals (runs of bad along the last axis) whose start is not 'behind'."""
    prev = np.zeros_like(bad)
    prev[..., 1:] = bad[..., :-1]
    return bad & ~prev & ~behind


def iso_cross_multi(clear, gid, SIG, VB, AB, tau, h_max, behind=None):
    """framelease_v2.lease.agent_leases ('time_resolved', reserve delta) for C isotropic envelopes at once.

    clear (N, M) = dist - d_safe; returns per-agent crossings (C, N) capped at h_max. Same operations in the same
    order as agent_leases, so each row equals agent_leases with that envelope bit for bit. behind (N, M): the
    responsibility-aware variant, the crossing is the start of the first contact interval not starting behind."""
    sig, vb, ab = SIG[:, gid], VB[:, gid], AB[:, gid]                               # (C, N)
    keep = tau < h_max + DT - 1e-9
    tau = tau[keep]
    c = clear[:, keep]
    B = vb[..., None] * tau[None, None, :] + 0.5 * ab[..., None] * tau[None, None, :] ** 2 + sig[..., None]
    g = c[None] - B - DELTA                                                         # (C, N, M)
    bad = g <= 0
    if behind is not None:
        bad = contact_starts(bad, behind[None, :, keep])
    hit = bad.any(-1)
    m = np.argmax(bad, axis=-1)
    out = np.where(hit, 0.0, np.inf)
    inner = hit & (m > 0)
    if inner.any():
        mm = np.where(inner, m, 1)
        idx = (mm - 1)[..., None]
        cb = np.broadcast_to(c, g.shape)
        c0 = np.take_along_axis(cb, idx, -1)[..., 0]
        c1 = np.take_along_axis(cb, mm[..., None], -1)[..., 0]
        t0, t1 = tau[mm - 1], tau[mm]
        k = (c1 - c0) / (t1 - t0)
        g0 = np.take_along_axis(g, idx, -1)[..., 0]
        a2 = 0.5 * ab
        b1 = ab * t0 + vb - k
        den = b1 + np.sqrt(np.maximum(b1 * b1 + 4.0 * a2 * g0, 0.0))
        u = np.where(den > 0, 2.0 * g0 / np.where(den > 0, den, 1.0), t1 - t0)
        out = np.where(inner, t0 + np.clip(u, 0.0, t1 - t0), out)
    return np.minimum(out, h_max)


def first_crossing_masked(tau, slack, behind):
    """first_crossing_time(tau, slack) restricted to contact intervals that do not start behind (RA variant).
    slack (..., M) <= 0 marks contact; the crossing is linearly interpolated before the first admissible start."""
    bad = np.asarray(slack) <= 0
    st = contact_starts(bad, np.broadcast_to(behind, bad.shape))
    hit = st.any(-1)
    m = np.argmax(st, axis=-1)
    out = np.full(st.shape[:-1], np.inf)
    out = np.where(hit & (m == 0), 0.0, out)
    inner = hit & (m > 0)
    if np.any(inner):
        mm = np.where(inner, m, 1)
        s0 = np.take_along_axis(slack, (mm - 1)[..., None], -1)[..., 0]
        s1 = np.take_along_axis(slack, mm[..., None], -1)[..., 0]
        ok = np.isfinite(s0) & np.isfinite(s1) & (s0 - s1 > 0)
        frac = np.where(ok, s0 / np.where(ok, s0 - s1, 1.0), 1.0)
        t = tau[mm - 1] + np.clip(frac, 0.0, 1.0) * (tau[mm] - tau[mm - 1])
        out = np.where(inner, t, out)
    return out


def suffix_kernel(E_suf, C_E, U_E, yaw_E, det7, score, groups, tp, pk, T_rem, hl_E, r_E):
    """Lease crossings of one plan suffix against one perception frame, for every configuration and variant.

    E_suf (M, 4, 2), C_E (M, 2), U_E (M, 2), yaw_E (M,): planned ego box from t_j on, in plan k's capture LiDAR
    frame; det7 (K, 7) boxes of frame j in the same frame (columns as decode_boxes); score (K,), groups (K,) group
    names, tp (K,) bool. Returns ts (C, 2) = tau* relative to t_j (capped at T_rem) and bind (C, 2) int8 codes."""
    C = len(CONFIGS)
    M = len(E_suf)
    tau_s = TAU[:M]
    ts = np.full((C, 2), T_rem)
    bind = np.zeros((C, 2), dtype=np.int8)
    if len(det7) == 0:
        return ts, bind
    relevant = np.isin(groups, ['vehicle', 'pedestrian']) & (np.nan_to_num(score, nan=1.0) >= sle.LOW_SCORE_FLOOR)
    finite = np.isfinite(det7).all(1) & np.isfinite(score)
    if (relevant & ~finite).any():
        ts[:] = 0.0
        bind[:] = 127
        return ts, bind
    idx = np.flatnonzero(relevant)
    if not len(idx):
        return ts, bind
    d = det7[idx]
    gid = np.array([GROUP_ID[g] for g in groups[idx]], dtype=int)
    cen = d[:, None, 0:2] + tau_s[None, :, None] * d[:, None, 5:7]                  # (N, M, 2)
    r_i = np.hypot(0.5 * np.abs(d[:, 2]), 0.5 * np.abs(d[:, 3]))
    lb = np.linalg.norm(cen - C_E[None], axis=-1) - r_E - r_i[:, None]
    keep = ((lb - pk['BMAX'][gid, :M]) <= D_SAFE + DELTA + PRUNE_PAD).any(axis=1)
    if not keep.any():
        return ts, bind
    idx, d, gid, cen = idx[keep], d[keep], gid[keep], cen[keep]
    R0 = box_corners(d[:, 0:2], d[:, 4], 0.5 * np.abs(d[:, 2]), 0.5 * np.abs(d[:, 3]))
    R = R0[:, None, :, :] + (tau_s[None, :, None, None] * d[:, None, None, 5:7])
    clear = convex_distance(E_suf[None], R) - D_SAFE                                 # (N, M) lease_geometry
    lon = ((cen - C_E[None]) * U_E[None]).sum(-1)                                   # (N, M)
    aligned = np.abs(np.cos(d[:, 4][:, None] - yaw_E[None, :])) >= RA_COS
    behind = (gid == 0)[:, None] & (lon < -hl_E) & aligned
    cross = np.empty((C, 2, len(idx)))
    cross[:N_ISO, 0] = iso_cross_multi(clear, gid, pk['SIG'], pk['VB'], pk['AB'], tau_s, T_rem)
    cross[:N_ISO, 1] = (iso_cross_multi(clear, gid, pk['SIG'], pk['VB'], pk['AB'], tau_s, T_rem, behind)
                        if behind.any() else cross[:N_ISO, 0])
    geom = SimpleNamespace(index=idx, group=groups[idx], ego_corners=E_suf)
    cm = sle.aniso_margins(geom, det7, pk['TAB'][:, :, :, :M, :], tau_s)           # (C_an, N, M)
    cross[N_ISO:, 0] = np.minimum(first_crossing_time(tau_s, cm - DELTA), T_rem)
    if behind.any():
        cross[N_ISO:, 1] = np.minimum(first_crossing_masked(tau_s, cm - DELTA, behind[None]), T_rem)
    else:
        cross[N_ISO:, 1] = cross[N_ISO:, 0]
    jmin = np.argmin(cross, axis=-1)                                                # (C, 2)
    ts = np.minimum(np.take_along_axis(cross, jmin[..., None], -1)[..., 0], T_rem)
    lon0 = lon[:, 0]
    pos = np.where(lon0 > hl_E, 0, np.where(lon0 < -hl_E, 2, 1))
    mov = (np.hypot(d[:, 5], d[:, 6]) >= envmod.STATIC_SPEED_MPS).astype(int)
    code_a = (1 + pos * 8 + mov * 4 + gid * 2 + tp[idx].astype(int)).astype(np.int8)
    bind = np.where(ts < T_rem - 1e-12, code_a[jmin], 0).astype(np.int8)
    return ts, bind


def gt_series(E_w, yaw_w, gt_state, gt_is_veh, ego_radius, hl_E):
    """Realized clearance (2, M) [std, ra] of the plan footprint E_w (M, 4, 2) to the ground truth, and the binding
    actor column per grid point (-1 if none): c2_eval.observed_validity's machinery, plus the RA mask."""
    xy, yaw, hl, hw, valid = gt_state
    ego_c = E_w.mean(axis=-2)
    r_a = np.hypot(hl, hw)
    lb = np.linalg.norm(xy - ego_c[:, None, :], axis=-1) - ego_radius - r_a
    cand = valid & (lb <= D_SAFE + VAL_PAD)
    dist = np.full(valid.shape, np.inf)
    if cand.any():
        mi, ai = np.nonzero(cand)
        dist[mi, ai] = convex_distance(E_w[mi], box_corners(xy[mi, ai], yaw[mi, ai], hl[mi, ai], hw[mi, ai]))
    u = np.stack([np.cos(yaw_w), np.sin(yaw_w)], axis=-1)
    lon = ((xy - ego_c[:, None, :]) * u[:, None, :]).sum(-1)
    aligned = np.abs(np.cos(yaw - yaw_w[:, None])) >= RA_COS
    behind = gt_is_veh[None, :] & (lon < -hl_E) & aligned
    # RA: ignore whole contact intervals (runs of dist <= d_safe per actor) that start behind
    bad = dist <= D_SAFE
    prev = np.zeros_like(bad)
    prev[1:] = bad[:-1]
    start = bad & ~prev
    ign = np.zeros_like(bad)
    if (start & behind).any():
        run = np.cumsum(start, axis=0)                                              # run id per (time, actor)
        for a in np.flatnonzero((start & behind).any(axis=0)):
            for rid in run[start[:, a] & behind[:, a], a]:
                ign[:, a] |= bad[:, a] & (run[:, a] == rid)
    clear = np.empty((2, len(E_w)))
    bindc = np.full((2, len(E_w)), -1, dtype=np.int16)
    for v, D in enumerate((dist, np.where(ign, np.inf, dist))):
        mn = D.min(axis=1) if D.shape[1] else np.full(len(E_w), np.inf)
        clear[v] = mn - D_SAFE
        if D.shape[1]:
            bindc[v] = np.where(np.isfinite(mn), np.argmin(D, axis=1), -1)
    return clear, bindc


# ----------------------------------------------------------------------------- workers

def _clip(name):
    if name not in _CLIP:
        _CLIP.clear()
        c = SweepClip(sle.SWEEP, name)
        c._v_gt = c.gt.frame_velocities()
        _CLIP[name] = c
    return _CLIP[name]


def status_job(name):
    """Detection status (F, A) int8 of every GT actor in every frame: 0 absent, 1 undetected, 2 low-conf, 3 conf."""
    clip = SweepClip(sle.SWEEP, name)
    bp = sle.base_params()
    F, A = len(clip), len(clip.gt.ids)
    S = np.zeros((F, A), dtype=np.int8)
    for j in range(F):
        S[j, clip.gt.present[int(clip.gt_row[j])]] = 1
        for col, s in detection_status(clip, j, bp, sle.GATE_M).items():
            S[j, col] = 3 if s == 'confident' else 2
    return name, S, clip.sha256, clip.gt_sha256, np.array([g == 'vehicle' for g in clip.gt.group], dtype=bool)


def eval_task(task):
    name, ks = task
    t0 = time.perf_counter()
    spec = _SPEC[name]
    clip = _clip(name)
    ego = spec['ego']
    bp = sle.base_params()
    hl_E = float(ego.half_length_m)
    r_E = float(np.hypot(ego.half_length_m, ego.half_width_m))
    v_gt, v_ok = clip._v_gt
    gt_is_veh = np.array([g == 'vehicle' for g in clip.gt.group], dtype=bool)
    F = len(clip)
    mcache, ocache = {}, {}
    rows, skipped = [], Counter()
    for k in ks:
        if clip.run_step[k] < sle.WARMUP_STEPS:
            skipped['warmup'] += 1
            continue
        t_k = float(clip.t[k])
        if t_k + T_PRED > clip.gt.t[-1] + 1e-9:
            skipped['insufficient_future_gt'] += 1
            continue
        gt_state = clip.gt.actors_at(t_k + TAU)
        pose_k = clip.poses[k]
        inv_k = se2_inverse(pose_k)
        for d in DEPTHS:
            plan = clip.cand[k, d - 1]
            if not np.isfinite(plan).all():
                skipped[f'nonfinite_plan_depth{d}'] += 1
                continue
            _, _, yaw_E, E = ego_corners_along_plan(plan, ego, bp)
            C_E = E.mean(axis=1)
            U_E = np.stack([np.cos(yaw_E), np.sin(yaw_E)], axis=-1)
            E_w = se2_apply(pose_k, E)
            gclear, gbind = gt_series(E_w, yaw_E + pose_k[2], gt_state, gt_is_veh, r_E, hl_E)
            ts = np.full((2, len(CONFIGS), 2, N_OFF), np.nan)
            bd = np.full((2, len(CONFIGS), 2, N_OFF), -1, dtype=np.int8)
            for o in range(N_OFF):
                j = k + o
                if j >= F or abs(float(clip.t[j]) - t_k - o * FRAME_DT) > 1e-6:
                    continue
                M = M_FULL - STEP * o
                T_rem = float(TAU[M - 1])
                sl = slice(STEP * o, None)
                # ---- model detections of frame j, in plan k's capture LiDAR frame
                if j not in mcache:
                    det7_j, score_j, label_j = clip.dets(j)
                    groups_j = resolve_groups(label_j) if len(label_j) else np.zeros(0, dtype=object)
                    mcache[j] = (det7_j, score_j, groups_j, sle.det_gt_flags(clip, j))
                det7_j, score_j, groups_j, tp_j = mcache[j]
                if o == 0:
                    det_kj = det7_j
                else:
                    rel = se2_compose(inv_k, clip.poses[j])
                    c, yw, v = transform_states(rel, det7_j[:, 0:2], det7_j[:, 4], det7_j[:, 5:7])
                    det_kj = np.column_stack([np.asarray(c).reshape(-1, 2), det7_j[:, 2:4],
                                              np.asarray(yw).reshape(-1), np.asarray(v).reshape(-1, 2)])
                ts[0, :, :, o], bd[0, :, :, o] = suffix_kernel(E[sl], C_E[sl], U_E[sl], yaw_E[sl], det_kj, score_j,
                                                               groups_j, tp_j, spec['model'], T_rem, hl_E, r_E)
                # ---- oracle: ground-truth boxes present at frame j (recorded finite-difference velocity)
                if j not in ocache:
                    g = int(clip.gt_row[j])
                    cols = np.flatnonzero(clip.gt.present[g])
                    vel = np.where(v_ok[g, cols][:, None], v_gt[g, cols], 0.0)
                    ocache[j] = (clip.gt.xy[g, cols], clip.gt.yaw[g, cols], clip.gt.hl[g, cols],
                                 clip.gt.hw[g, cols], vel, clip.gt.group[cols])
                xy_w, yaw_w, ghl, ghw, vel, ggrp = ocache[j]
                c, yw, v = transform_states(inv_k, xy_w.reshape(-1, 2), yaw_w, vel.reshape(-1, 2))
                det_o = np.column_stack([np.asarray(c).reshape(-1, 2), 2.0 * ghl, 2.0 * ghw,
                                         np.asarray(yw).reshape(-1), np.asarray(v).reshape(-1, 2)])
                ones = np.ones(len(det_o))
                ts[1, :, :, o], bd[1, :, :, o] = suffix_kernel(E[sl], C_E[sl], U_E[sl], yaw_E[sl], det_o, ones,
                                                               np.asarray(ggrp, dtype=object), ones.astype(bool),
                                                               spec['oracle'], T_rem, hl_E, r_E)
            rows.append((k, int(clip.frame_idx[k]), d, t_k, gclear, gbind, ts, bd))
    return name, rows, dict(skipped), time.perf_counter() - t0


# ----------------------------------------------------------------------------- main

def file_sha(paths):
    return {str(p): sha256_file(p) for p in paths}


def code_hash():
    h = hashlib.sha256()
    for p in (Path(__file__), Path(sle.__file__), Path(envmod.__file__)):
        h.update(Path(p).read_bytes())
    return h.hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out-dir', default=str(ROOT / 'outputs/framelease_v3/renewal_offline/run_20261110'))
    ap.add_argument('--workers', type=int, default=max(1, min(14, (os.cpu_count() or 2) - 2)))
    ap.add_argument('--chunk', type=int, default=8, help='plan frames per task')
    ap.add_argument('--clips', default='', help='comma list of VAL clips (default: the 15 of gate2)')
    ap.add_argument('--max-frames', type=int, default=0, help='smoke test: first N eligible frames per clip')
    args = ap.parse_args(argv)
    out = Path(args.out_dir)
    if not out.is_absolute():
        out = ROOT / out
    (out / 'stageA').mkdir(parents=True, exist_ok=True)
    log_f = open(out / 'stageA.log', 'a', encoding='utf-8')
    t_start = time.time()

    def log(*a):
        msg = time.strftime('%H:%M:%S ') + ' '.join(str(x) for x in a)
        print(msg, flush=True)
        log_f.write(msg + '\n')
        log_f.flush()

    g2cfg = json.loads((GATE2 / 'config.json').read_text(encoding='utf-8'))
    VAL = list(g2cfg['val_clips'])
    TRAIN = list(g2cfg['train_clips'])
    ALL = sorted(set(VAL) | set(TRAIN))
    run_clips = [c for c in args.clips.split(',') if c] or VAL
    ego = load_ego_shape(sle.OLD_PARAMS)
    if ego.to_dict() != g2cfg['ego_shape']:
        raise SystemExit('ego shape differs from gate2 config')
    chash = code_hash()
    log(f'[A] out {out}; clips {len(run_clips)}; workers {args.workers}; code {chash[:12]}; max_frames {args.max_frames}')
    ctx = get_context('fork')

    # ---------------------------------------------------------------- oracle envelopes (LOCO on GT CV residuals)
    oe_path = out / 'oracle_envelopes.json'
    if oe_path.exists():
        oe = json.loads(oe_path.read_text(encoding='utf-8'))
        if oe.get('code_sha256') != chash:
            log('[A] note: oracle_envelopes.json was written by a different code version; reusing it (fits only '
                'depend on envelopes.py and the sample definition, recorded in the file)')
        log(f'[A] oracle envelopes loaded from {oe_path}')
    else:
        t0 = time.time()
        with ProcessPoolExecutor(max_workers=args.workers, mp_context=ctx) as ex:
            for n, S in ex.map(oracle_samples_job, ALL):
                _SAMPLES[n] = S
        n_pairs = {n: int(len(S['group'])) for n, S in _SAMPLES.items()}
        log(f'[A] oracle samples: {sum(n_pairs.values())} GT pairs over {len(ALL)} clips in {time.time() - t0:.0f}s')
        t0 = time.time()
        folds = {}
        with ProcessPoolExecutor(max_workers=args.workers, mp_context=ctx) as ex:
            for h, envs in ex.map(oracle_fit_job, [(h, [c for c in ALL if c != h]) for h in VAL]):
                folds[h] = {k: oracle_env_to_json(e) for k, e in envs.items()}
        oe = {'note': 'oracle envelopes: framelease_v3.envelopes fits on ground-truth constant-velocity residuals '
                      '(GT box moved with the recorded finite-difference velocity vs the GT box at t_k + tau; all GT '
                      'vehicles / walkers within 50 m with a velocity; frames after the detector warm-up); LOCO: '
                      'fold h calibrated on the other 19 clips. Tables: [group (vehicle, pedestrian), motion bin '
                      '(static, moving), tau, (B_lon, B_lat)].',
              'code_sha256': chash, 'tau_s': TAU.tolist(), 'n_pairs_per_clip': n_pairs, 'folds': folds}
        tmp = oe_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(clean_json(oe)), encoding='utf-8')
        os.replace(tmp, oe_path)
        log(f'[A] oracle envelopes: {len(folds)} folds x {len(folds[VAL[0]])} fitted in {time.time() - t0:.0f}s')
    model_env = load_model_envelopes(VAL)
    for h in run_clips:
        _SPEC[h] = {'ego': ego, 'model': stack_packs(model_env[h]),
                    'oracle': stack_packs({'B0': zero_pack(), **{k: oracle_pack(e) for k, e in oe['folds'][h].items()}})}

    # ---------------------------------------------------------------- per-clip evaluation (resumable)
    todo = []
    for c in run_clips:
        p = out / 'stageA' / f'{c}.npz'
        if p.exists():
            try:
                with np.load(p, allow_pickle=False) as z:
                    meta = json.loads(str(z['meta']))
                if meta.get('code_sha256') == chash and meta.get('max_frames') == args.max_frames:
                    log(f'[A] {c}: done earlier ({meta["n_cases"]} cases), skipped')
                    continue
                log(f'[A] {c}: existing file from another code version / setting, recomputing')
            except Exception as e:  # noqa: BLE001
                log(f'[A] {c}: unreadable existing file ({e}), recomputing')
        todo.append(c)
    if todo:
        t0 = time.time()
        with ProcessPoolExecutor(max_workers=args.workers, mp_context=ctx) as ex:
            status = {n: (S, h, hg, veh) for n, S, h, hg, veh in ex.map(status_job, todo)}
        log(f'[A] detection status of {len(todo)} clips in {time.time() - t0:.0f}s')
        tasks = []
        for c in todo:
            nF = len(status[c][0])
            ks = list(range(nF))
            if args.max_frames:
                clip_ = SweepClip(sle.SWEEP, c)
                ks = [k for k in ks if clip_.run_step[k] >= sle.WARMUP_STEPS][:args.max_frames]
            for i in range(0, len(ks), args.chunk):
                tasks.append((c, ks[i:i + args.chunk]))
        left = Counter(t[0] for t in tasks)
        acc = {c: [] for c in todo}
        skipped = {c: Counter() for c in todo}
        cpu = Counter()
        t0 = time.time()
        with ProcessPoolExecutor(max_workers=args.workers, mp_context=ctx) as ex:
            for i, (name, rows, sk, sec) in enumerate(ex.map(eval_task, tasks)):
                acc[name].extend(rows)
                skipped[name].update(sk)
                cpu[name] += sec
                left[name] -= 1
                if left[name] == 0:
                    rows_c = sorted(acc[name], key=lambda r: (r[0], r[2]))
                    S, hsh, hgt, veh = status[name]
                    meta = {'schema': SCHEMA, 'clip': name, 'code_sha256': chash, 'max_frames': args.max_frames,
                            'n_cases': len(rows_c), 'configs': CONFIGS, 'variants': list(VARIANTS),
                            'sources': list(SOURCES), 'n_off': N_OFF, 'skipped': dict(skipped[name]),
                            'cpu_s': cpu[name], 'npz_sha256': hsh, 'gt_sha256': hgt, 'ra_rule': RA_RULE}
                    arrays = {
                        'meta': np.array(json.dumps(meta)),
                        'k': np.array([r[0] for r in rows_c], dtype=np.int64),
                        'frame_idx': np.array([r[1] for r in rows_c], dtype=np.int64),
                        'depth': np.array([r[2] for r in rows_c], dtype=np.int64),
                        't_k': np.array([r[3] for r in rows_c], dtype=float),
                        'gt_clear': np.stack([r[4] for r in rows_c]),          # (n, 2, 61)
                        'gt_bind': np.stack([r[5] for r in rows_c]),           # (n, 2, 61)
                        'ts': np.stack([r[6] for r in rows_c]),                # (n, 2 sources, C, 2 variants, 30)
                        'bind': np.stack([r[7] for r in rows_c]),              # (n, 2, C, 2, 30)
                        'status': S, 'gt_is_vehicle': veh}
                    p = out / 'stageA' / f'{name}.npz'
                    tmp = out / 'stageA' / f'{name}.tmp.npz'
                    np.savez_compressed(tmp, **arrays)
                    os.replace(tmp, p)
                    acc[name] = []
                    log(f'[A] {name}: {len(rows_c)} cases written ({cpu[name]:.0f} CPU-s); '
                        f'{i + 1}/{len(tasks)} tasks, {time.time() - t0:.0f}s wall')
    cfg = {'schema': SCHEMA, 'argv': sys.argv if argv is None else ['renewal_compute.py', *argv],
           'finished': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'wall_s_this_invocation': time.time() - t_start,
           'python': sys.version, 'numpy': np.__version__, 'platform': platform.platform(),
           'code_sha256_combined': chash,
           'script_sha256': file_sha([Path(__file__).resolve(), Path(sle.__file__).resolve(),
                                      Path(envmod.__file__).resolve(), ROOT / 'framelease_v3/__init__.py']),
           'framelease_v2_sha256': file_sha([ROOT / f'framelease_v2/{m}' for m in
                                             ('lease.py', 'geometry.py', 'calibration.py', 'c2_eval.py',
                                              'unidrive_boxes.py', '__init__.py')]),
           'input_sha256': file_sha([GATE2 / 'config.json', GATE2 / 'frames.csv', RF / 'envelopes_new_quantiles.json',
                                     RF / 'frames_tau_star_new.csv', sle.OLD_PARAMS, sle.SWEEP / 'MERGE_NOTE.json']
                                    + sorted((GATE2 / 'envelopes').glob('*_LOCO.json'))),
           'clip_npz_sha256': g2cfg['clip_npz_sha256'], 'clip_gt_sha256': g2cfg['clip_gt_sha256'],
           'settings': {'T_pred_s': T_PRED, 'dt_s': DT, 'frame_dt_s': FRAME_DT, 'n_offsets': N_OFF,
                        'd_safe_m': D_SAFE, 'delta_m': DELTA, 'score_floor': sle.LOW_SCORE_FLOOR,
                        'score_threshold': sle.SCORE_THRESHOLD, 'warmup_steps': sle.WARMUP_STEPS,
                        'configs': CONFIGS, 'quantiles': list(QS), 'prune_pad_m': PRUNE_PAD, 'val_pad_m': VAL_PAD,
                        'ra_rule': RA_RULE, 'ra_cos': RA_COS},
           'val_clips': VAL, 'train_clips': TRAIN, 'ego_shape': ego.to_dict()}
    write_json(out / 'stageA_config.json', cfg)
    log(f'[A] done in {time.time() - t_start:.0f}s')
    log_f.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
