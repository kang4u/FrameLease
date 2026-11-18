"""Residual envelopes for the outline's suffix-aligned validity lease (framelease_v3, Gate 2 offline).

Ground truth is used ONLY here (calibration) and only on clips other than the evaluated one; the lease itself
reads only the model's own detections and plans. framelease_v2 modules are imported read-only.

Calibration samples
-------------------
Matching is framelease_v2.calibration's: per processed frame k after the detector warm-up (run_step >= 5) the model's
confident detections (score >= 0.3, groups vehicle / pedestrian) are placed in the world frame with lidar2global and
matched one-to-one to ground-truth actors of the same group within 75 m by the Hungarian algorithm on centre distance
(gate 2.0 m). Pairs whose actor is farther than 50 m from the LiDAR are dropped (calibration.py error_range_m).
For every matched pair and every tau on the 0.05 s grid in [0, T_pred] at which the actor exists in the recording:

  iso(tau)   Hausdorff distance between the detection box translated with its own velocity (constant-velocity,
             CV, extrapolation) and the ground-truth box at t_k + tau. This is calibration.py's CV footprint error,
             evaluated on the fine grid (E0).
  lon(tau)   max(0, max_i |(p_i - c_cv(tau)) . u| - hl_det)   p_i: ground-truth footprint corners at t_k + tau;
  lat(tau)   max(0, max_i |(p_i - c_cv(tau)) . n| - hw_det)   c_cv: CV centre; u, n: detection heading and normal.
             (lon, lat) is the smallest inflation of the CV box along / across the DETECTED heading whose rectangle
             Minkowski sum contains the true footprint (E1/E2). It contains the GT centre deviation from the CV
             extrapolation plus the size and orientation error of the detection; at tau = 0 it is the detection
             error itself.
  fp0        tau = 0 Hausdorff error (E0 sigma), vel_err = |v_det - v_gt| (E0 vbar), both as calibration.py.
  speed      detected speed |v_det| (E2 motion-state bin; available online).

Envelopes
---------
  E0 (iso)    B_c(tau) = vbar_c tau + 0.5 abar_c tau^2 + sigma_c (calibration.py's functional form): sigma_c, vbar_c
              = q-quantiles of fp0 and vel_err; abar_c = smallest value with B_c(D) >= q-quantile of iso(D) at every D
              of the envelope grid (0.5 ... 3.0 s, i.e. the old grid 0.5 ... 2.0 s extended to T_pred = 3 s).
  E1 (aniso)  per class c and tau on the 0.05 s grid: (B_lon, B_lat) = (Q_lon(q'), Q_lat(q')) with the smallest
              q' >= q such that the JOINT empirical containment coverage P(lon <= B_lon and lat <= B_lat) >= q (so q95
              means 95% of matched (pair, tau) samples are contained, the same coverage notion as E0's Hausdorff q95);
              then made non-decreasing in tau (running maximum).
  E2          E1 per (class, motion bin), bins from the detected speed: static < 0.5 m/s <= moving. A (class, bin, tau)
              cell with fewer than min_n samples uses the class-level (E1) value.
"""
from __future__ import annotations

import math
import sys

sys.dont_write_bytecode = True

from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v2.calibration import MATCH_GROUPS, RANGE_BINS, dets_world, gt_frame, hungarian_match  # noqa: E402
from framelease_v2.geometry import box_corners, hausdorff_convex  # noqa: E402

GROUPS = ('vehicle', 'pedestrian')
GROUP_ID = {'vehicle': 0, 'pedestrian': 1}
STATIC_SPEED_MPS = 0.5
BIN_NAMES = ('static', 'moving')
E0_D_GRID_S = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0)
OLD_E0_D_GRID_S = (0.5, 1.0, 1.5, 2.0)
DEFAULT_SIGMA = {'vehicle': 1.0, 'pedestrian': 0.6}
DEFAULT_VBAR = {'vehicle': 2.0, 'pedestrian': 1.0}
DEFAULT_ABAR = {'vehicle': 4.0, 'pedestrian': 2.0}


def speed_bin(speed):
    """0 = static (detected speed < 0.5 m/s), 1 = moving."""
    return (np.asarray(speed, dtype=float) >= STATIC_SPEED_MPS).astype(np.int8)


def containment_residual(gt_corners, cv_center, det_yaw, det_hl, det_hw):
    """(lon, lat) inflation of the CV box needed to contain the GT footprint, in the detection heading frame.

    gt_corners (..., 4, 2), cv_center (..., 2), det_yaw / det_hl / det_hw broadcastable to (...)."""
    rel = np.asarray(gt_corners, dtype=float) - np.asarray(cv_center, dtype=float)[..., None, :]
    yaw = np.asarray(det_yaw, dtype=float)
    c, s = np.cos(yaw)[..., None], np.sin(yaw)[..., None]
    x = np.abs(rel[..., 0] * c + rel[..., 1] * s).max(-1)
    y = np.abs(-rel[..., 0] * s + rel[..., 1] * c).max(-1)
    return np.maximum(0.0, x - det_hl), np.maximum(0.0, y - det_hw)


def clip_samples(clip, tau, gate_m=2.0, error_range_m=50.0, score_threshold=0.3, warmup_steps=5):
    """Calibration samples of one clip (see module docstring). Returns a dict of arrays (P pairs, M taus)."""
    tau = np.asarray(tau, dtype=float)
    M = len(tau)
    v_gt, v_ok = clip.gt.frame_velocities()
    acc = {k: [] for k in ('group', 'speed', 'fp0', 'vel_err', 'range', 'score', 'frame_idx', 'iso', 'lon', 'lat')}
    n_frames = 0
    for k in range(len(clip)):
        if clip.run_step[k] < warmup_steps:
            continue
        n_frames += 1
        gt = gt_frame(clip, k, v_gt, v_ok)
        dw = dets_world(clip, k)
        rel = np.isin(dw['group'], MATCH_GROUPS)
        conf = rel & (dw['score'] >= score_threshold)
        within = gt['range'] < RANGE_BINS[-2]
        gidx = np.flatnonzero(within)
        pairs = hungarian_match(gt['xy'][within], gt['group'][within], dw['xy'][conf], dw['group'][conf], gate_m)
        if not pairs:
            continue
        ci = np.flatnonzero(conf)
        a_idx = np.array([gidx[a] for a, _, _ in pairs], dtype=int)
        d_idx = np.array([ci[b] for _, b, _ in pairs], dtype=int)
        rng = gt['range'][a_idx]
        keep = rng <= error_range_m
        if not keep.any():
            continue
        a_idx, d_idx, rng = a_idx[keep], d_idx[keep], rng[keep]
        cols = gt['col'][a_idx]
        fxy, fyaw, fhl, fhw, fvalid = clip.gt.actors_at(clip.t[k] + tau)        # (M, A, ...)
        gxy = np.transpose(fxy[:, cols], (1, 0, 2))                              # (P, M, 2)
        gbox = box_corners(gxy, fyaw[:, cols].T, fhl[:, cols].T, fhw[:, cols].T)  # (P, M, 4, 2)
        valid = fvalid[:, cols].T                                                # (P, M)
        c, yaw, v = dw['xy'][d_idx], dw['yaw'][d_idx], dw['v'][d_idx]
        hl, hw = dw['hl'][d_idx], dw['hw'][d_idx]
        pc = c[:, None, :] + tau[None, :, None] * v[:, None, :]                  # (P, M, 2)
        pbox = box_corners(pc, yaw[:, None], hl[:, None], hw[:, None])           # (P, M, 4, 2)
        iso = hausdorff_convex(pbox, gbox)
        lon, lat = containment_residual(gbox, pc, yaw[:, None], hl[:, None], hw[:, None])
        for arr in (iso, lon, lat):
            arr[~valid] = np.nan
        # tau = 0 errors exactly as calibration.py (GT box of the capture frame row; GT velocity of that row).
        dbox0 = box_corners(c, yaw, hl, hw)
        gbox0 = box_corners(gt['xy'][a_idx], gt['yaw'][a_idx], gt['hl'][a_idx], gt['hw'][a_idx])
        fp0 = np.asarray(hausdorff_convex(dbox0, gbox0), dtype=float).reshape(-1)
        vg = np.where(gt['v_ok'][a_idx][:, None], gt['v'][a_idx], np.nan)
        acc['group'].append(np.array([GROUP_ID[g] for g in gt['group'][a_idx]], dtype=np.int8))
        acc['speed'].append(np.linalg.norm(v, axis=-1))
        acc['fp0'].append(fp0)
        acc['vel_err'].append(np.linalg.norm(v - vg, axis=-1))
        acc['range'].append(rng)
        acc['score'].append(dw['score'][d_idx])
        acc['frame_idx'].append(np.full(len(a_idx), int(clip.frame_idx[k])))
        acc['iso'].append(iso.astype(float))
        acc['lon'].append(lon.astype(float))
        acc['lat'].append(lat.astype(float))
    out = {}
    for key, parts in acc.items():
        if parts:
            out[key] = np.concatenate(parts, axis=0)
        else:
            out[key] = np.zeros((0, M) if key in ('iso', 'lon', 'lat') else (0,), dtype=float)
    out['n_frames'] = n_frames
    return out


def pool_samples(per_clip, names):
    """Concatenate the samples of the named clips."""
    keys = ('group', 'speed', 'fp0', 'vel_err', 'range', 'score', 'iso', 'lon', 'lat')
    return {k: np.concatenate([per_clip[n][k] for n in names], axis=0) for k in keys}


# ----------------------------------------------------------------------------- E0: isotropic quadratic form

def _q(x, q):
    return float(np.quantile(np.asarray(x, dtype=float), q))


def fit_iso(S, q, tau, d_grid_s=E0_D_GRID_S, min_n=20):
    """calibration.py's envelope parameters (sigma, vbar, abar_env) at quantile q from pooled samples S."""
    sig, vb, notes = {}, {}, []
    for g, gid in GROUP_ID.items():
        sel = S['group'] == gid
        fp0 = S['fp0'][sel]
        if len(fp0) >= min_n:
            sig[g] = _q(fp0, q)
            ve = S['vel_err'][sel]
            ve = ve[np.isfinite(ve)]
            vb[g] = _q(ve, q) if len(ve) >= min_n else None
        else:
            sig[g] = vb[g] = None
            notes.append(f'{g}: only {len(fp0)} matched pairs (< {min_n}); bound borrowed')
    for d, default in ((sig, DEFAULT_SIGMA), (vb, DEFAULT_VBAR)):
        have = [v for v in d.values() if v is not None]
        for g in GROUPS:
            if d[g] is None:
                d[g] = max(have) if have else default[g]
    ab = {}
    need_by_d = {}
    for g, gid in GROUP_ID.items():
        sel = S['group'] == gid
        need = []
        for D in d_grid_s:
            m = int(round(D / (tau[1] - tau[0])))
            e = S['iso'][sel, m]
            e = e[np.isfinite(e)].astype(float)
            if len(e) >= min_n:
                need.append(max(0.0, 2.0 * (_q(e, q) - sig[g] - vb[g] * D) / (D * D)))
        need_by_d[g] = need
        ab[g] = max(need) if need else None
        if ab[g] is None:
            notes.append(f'{g}: too few prediction-error samples; abar borrowed')
    have = [v for v in ab.values() if v is not None]
    for g in GROUPS:
        if ab[g] is None:
            ab[g] = max(have) if have else DEFAULT_ABAR[g]
    return {'kind': 'iso', 'q': q, 'sigma_m': sig, 'vbar_mps': vb, 'abar_mps2': ab, 'd_grid_s': list(d_grid_s),
            'n_pairs': {g: int((S['group'] == gid).sum()) for g, gid in GROUP_ID.items()}, 'notes': notes}


def iso_bound(env, group, tau):
    tau = np.asarray(tau, dtype=float)
    return env['vbar_mps'][group] * tau + 0.5 * env['abar_mps2'][group] * tau * tau + env['sigma_m'][group]


# ----------------------------------------------------------------------------- E1 / E2: anisotropic grid envelopes

def _sorted_quantile(xs, qq):
    """numpy 'linear' quantile of a sorted 1-D array."""
    n = len(xs)
    h = (n - 1) * qq
    lo = int(math.floor(h))
    hi = min(lo + 1, n - 1)
    return float(xs[lo] + (h - lo) * (xs[hi] - xs[lo]))


def joint_quantile(a, b, q, iters=40):
    """Smallest per-component level q' >= q with empirical P(a <= Q_a(q') and b <= Q_b(q')) >= q.

    Returns (B_a, B_b, q', coverage). Coverage is monotone in q' and equals 1 at q' = 1, so bisection applies."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    sa, sb = np.sort(a), np.sort(b)

    def cov(qq):
        Ba, Bb = _sorted_quantile(sa, qq), _sorted_quantile(sb, qq)
        return float(np.mean((a <= Ba) & (b <= Bb))), Ba, Bb

    c, Ba, Bb = cov(q)
    if c >= q:
        return Ba, Bb, q, c
    lo, hi = q, 1.0
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if cov(mid)[0] >= q:
            hi = mid
        else:
            lo = mid
    c, Ba, Bb = cov(hi)
    return Ba, Bb, hi, c


def _fit_cells(lon, lat, q, min_n):
    """Per-tau joint quantile for one sample subset. Returns B (M, 2) with NaN where n < min_n, n (M,), q' (M,)."""
    M = lon.shape[1]
    B = np.full((M, 2), np.nan)
    n = np.zeros(M, dtype=int)
    qq = np.full(M, np.nan)
    for m in range(M):
        ok = np.isfinite(lon[:, m]) & np.isfinite(lat[:, m])
        n[m] = int(ok.sum())
        if n[m] < min_n:
            continue
        Ba, Bb, qm, _ = joint_quantile(lon[ok, m], lat[ok, m], q)
        B[m] = (Ba, Bb)
        qq[m] = qm
    return B, n, qq


def _fill_monotone(B):
    """Forward-fill NaN along tau (axis 0), then running maximum (non-decreasing envelope)."""
    B = B.copy()
    for j in range(B.shape[1]):
        col = B[:, j]
        last = np.nan
        for m in range(len(col)):
            if np.isfinite(col[m]):
                last = col[m]
            else:
                col[m] = last
        if np.isnan(col).all():
            continue
        first = np.flatnonzero(np.isfinite(col))[0]
        col[:first] = col[first]
        B[:, j] = np.maximum.accumulate(col)
    return B


def fit_aniso(S, q, tau, motion_bins=False, min_n=20):
    """E1 (motion_bins=False) or E2 (True). table[g, b, m, :] = (B_lon, B_lat) at tau_m for class g, motion bin b."""
    M = len(tau)
    G, NB = len(GROUPS), len(BIN_NAMES)
    cls_B = np.full((G, M, 2), np.nan)
    diag = {'n': {}, 'q_used': {}, 'fallback_cells': {}}
    for g, gid in GROUP_ID.items():
        sel = S['group'] == gid
        B, n, qq = _fit_cells(S['lon'][sel].astype(float), S['lat'][sel].astype(float), q, min_n)
        cls_B[gid] = B
        diag['n'][g] = n.tolist()
        diag['q_used'][g] = qq.tolist()
    # classes without enough samples at some tau borrow the maximum over classes (calibration.py's rule)
    mx = np.nanmax(np.where(np.isfinite(cls_B), cls_B, -np.inf), axis=0)
    mx = np.where(np.isfinite(mx), mx, np.nan)
    for gid in range(G):
        bad = ~np.isfinite(cls_B[gid])
        cls_B[gid][bad] = mx[bad]
        cls_B[gid] = _fill_monotone(cls_B[gid])
    table = np.repeat(cls_B[:, None], NB, axis=1)                                   # (G, NB, M, 2)
    if motion_bins:
        for g, gid in GROUP_ID.items():
            for b in range(NB):
                sel = (S['group'] == gid) & (speed_bin(S['speed']) == b)
                B, n, qq = _fit_cells(S['lon'][sel].astype(float), S['lat'][sel].astype(float), q, min_n)
                bad = ~np.isfinite(B)
                diag['fallback_cells'][f'{g}/{BIN_NAMES[b]}'] = int(bad[:, 0].sum())
                diag['n'][f'{g}/{BIN_NAMES[b]}'] = n.tolist()
                diag['q_used'][f'{g}/{BIN_NAMES[b]}'] = qq.tolist()
                B[bad] = cls_B[gid][bad]
                table[gid, b] = _fill_monotone(B)
    return {'kind': 'aniso', 'q': q, 'motion_bins': bool(motion_bins), 'table': table, 'diag': diag,
            'n_pairs': {g: int((S['group'] == gid).sum()) for g, gid in GROUP_ID.items()}}


def aniso_inside(env, S):
    """Containment indicator of an anisotropic envelope on samples S: (inside (P, M), valid (P, M), group (P,))."""
    gid = S['group'].astype(int)
    b = speed_bin(S['speed']) if env['motion_bins'] else np.zeros(len(gid), dtype=int)
    B = env['table'][gid, b]                                                        # (P, M, 2)
    ok = np.isfinite(S['lon']) & np.isfinite(S['lat'])
    inside = (S['lon'] <= B[..., 0] + 1e-9) & (S['lat'] <= B[..., 1] + 1e-9)
    return inside, ok, gid


def iso_inside(env, S, tau):
    """Coverage indicator of an isotropic envelope (Hausdorff CV error <= B_c(tau)) on samples S."""
    gid = S['group'].astype(int)
    Bt = np.stack([iso_bound(env, g, tau) for g in GROUPS])                         # (G, M)
    ok = np.isfinite(S['iso'])
    inside = S['iso'] <= Bt[gid] + 1e-9
    return inside, ok, gid


def coverage_summary(inside, ok, gid, tau):
    """Per-tau coverage at 0, 0.5, ..., 3 s, sample coverage over all tau, and whole-path coverage per class."""
    out = {}
    marks = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    dt = tau[1] - tau[0]
    for g, k in GROUP_ID.items():
        sel = gid == k
        if not sel.any():
            out[g] = None
            continue
        ins, okk = inside[sel], ok[sel]
        per_tau = {}
        for t in marks:
            m = int(round(t / dt))
            v = okk[:, m]
            per_tau[f'{t:g}'] = {'n': int(v.sum()), 'coverage': float(ins[v, m].mean()) if v.any() else None}
        whole = okk.any(1)
        path = (ins | ~okk).all(1)
        m25 = int(round(2.5 / dt)) + 1
        path25 = (ins[:, :m25] | ~okk[:, :m25]).all(1)
        out[g] = {'per_tau': per_tau, 'n_pairs': int(whole.sum()),
                  'path_coverage_0_3s': float(path[whole].mean()) if whole.any() else None,
                  'path_coverage_0_2.5s': float(path25[whole].mean()) if whole.any() else None,
                  'sample_coverage_all_tau': float(ins[okk].mean()) if okk.any() else None}
    return out


def env_to_json(env, tau):
    """JSON-friendly copy of an envelope."""
    if env['kind'] == 'iso':
        return {k: env[k] for k in ('kind', 'q', 'sigma_m', 'vbar_mps', 'abar_mps2', 'd_grid_s', 'n_pairs', 'notes')}
    t = env['table']
    out = {'kind': 'aniso', 'q': env['q'], 'motion_bins': env['motion_bins'], 'tau_s': [round(float(x), 4) for x in tau],
           'n_pairs': env['n_pairs'], 'B_lon_m': {}, 'B_lat_m': {}}
    for g, gid in GROUP_ID.items():
        bins = BIN_NAMES if env['motion_bins'] else ('all',)
        for bi, bn in enumerate(bins):
            key = g if bn == 'all' else f'{g}/{bn}'
            out['B_lon_m'][key] = [round(float(x), 4) for x in t[gid, bi, :, 0]]
            out['B_lat_m'][key] = [round(float(x), 4) for x in t[gid, bi, :, 1]]
    out['min_samples_per_tau'] = {k: int(np.min(v)) for k, v in env['diag']['n'].items()}
    out['fallback_cells'] = env['diag']['fallback_cells']
    return out
