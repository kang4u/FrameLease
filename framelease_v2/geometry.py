"""Planar geometry for the FrameLease Action-Validity Lease (AVL) and its offline evaluation.

Conventions (coordinate contract shared with c1_depth_sweep.py / SWEEP_SCHEMA.md)
-------------------------------------------------------------------------------
* Every 2-D frame used here is RIGHT-handed. Yaw is counter-clockwise from +x, in radians.
* LiDAR frame of UniDriveVLA / Bench2Drive (converted infos): x to the right, y forward, z up.
  The ego forward axis therefore has yaw pi/2 in the LiDAR frame; `forward_yaw_from_lidar2ego`
  derives it from lidar2ego instead of assuming it.
* World frame: the right-handed frame reached by lidar2global = inv(world2lidar) of the B2D infos.
  Raw CARLA annotations (anno/*.json.gz) are LEFT-handed and must be converted (y -> -y, yaw -> -yaw)
  before they are compared with anything in this module.
* A plan is 6 waypoints (x, y) of the LiDAR origin at tau = 0.5, 1.0, ..., 3.0 s after capture, in the
  capture-time LiDAR frame. The LiDAR origin is (0, 0) at tau = 0.
* An oriented box is (center_xy, yaw, half_length, half_width); its length axis is (cos yaw, sin yaw).
  `box_corners` returns corners counter-clockwise: front-left, rear-left, rear-right, front-right.
* 3-D poses are reduced to SE(2) by taking the translation x, y and yaw = atan2(R[1,0], R[0,0]).
  For the near-planar CARLA poses the error of this projection is O(pitch^2) and is ignored.

Only numpy is needed here. shapely is used by the tests as an independent reference implementation.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

PLAN_DT_S = 0.5          # spacing of the UniDriveVLA planning waypoints
PLAN_STEPS = 6           # waypoints per plan (tau = 0.5 ... 3.0 s)
FRAME_DT_S = 0.1         # Bench2Drive recording period (10 Hz), timestamp = frame_idx / 10
GT_CLASSES = ('vehicle', 'walker')
GT_TO_GROUP = {'vehicle': 'vehicle', 'walker': 'pedestrian'}


# ----------------------------------------------------------------------------- angles and SE(2)

def wrap_angle(a):
    """Wrap angles to [-pi, pi). Scalars come back as float, arrays as arrays."""
    w = np.mod(np.asarray(a, dtype=float) + np.pi, 2.0 * np.pi) - np.pi
    return float(w) if np.ndim(w) == 0 else w


def rotate(xy, yaw):
    """Rotate 2-D vectors xy (..., 2) by yaw (broadcastable to xy[..., 0])."""
    xy = np.asarray(xy, dtype=float)
    c, s = np.cos(yaw), np.sin(yaw)
    return np.stack([c * xy[..., 0] - s * xy[..., 1], s * xy[..., 0] + c * xy[..., 1]], axis=-1)


def se2_from_matrix(T):
    """(x, y, yaw) of a 3x3 or 4x4 homogeneous rigid transform (planar projection)."""
    T = np.asarray(T, dtype=float)
    if T.shape == (4, 4):
        tx, ty = T[0, 3], T[1, 3]
    elif T.shape == (3, 3):
        tx, ty = T[0, 2], T[1, 2]
    else:
        raise ValueError(f'expected a 3x3 or 4x4 transform, got {T.shape}')
    if not np.isfinite(T).all():
        raise ValueError('non-finite transform')
    return float(tx), float(ty), float(math.atan2(T[1, 0], T[0, 0]))


def se2_apply(pose, xy):
    """Map points xy (..., 2) through pose = (x, y, yaw)."""
    x, y, yaw = pose
    return rotate(xy, yaw) + np.array([x, y], dtype=float)


def se2_inverse(pose):
    x, y, yaw = pose
    t = -rotate(np.array([x, y], dtype=float), -yaw)
    return float(t[0]), float(t[1]), float(-yaw)


def se2_compose(a, b):
    """Pose a o b (apply b first, then a)."""
    t = se2_apply(a, np.array([b[0], b[1]], dtype=float))
    return float(t[0]), float(t[1]), float(wrap_angle(a[2] + b[2]))


def transform_states(pose, center_xy, yaw, velocity_xy=None):
    """Express boxes given in a source frame in the target frame of pose (source -> target)."""
    center = se2_apply(pose, center_xy)
    heading = wrap_angle(np.asarray(yaw, dtype=float) + pose[2])
    vel = None if velocity_xy is None else rotate(velocity_xy, pose[2])
    return center, heading, vel


def forward_yaw_from_lidar2ego(lidar2ego):
    """Yaw, in the LiDAR frame, of the ego forward (+x) axis. lidar2ego maps LiDAR to ego coordinates."""
    R = np.asarray(lidar2ego, dtype=float)[:3, :3]
    f = R.T @ np.array([1.0, 0.0, 0.0])
    return float(math.atan2(f[1], f[0]))


def ego_origin_in_lidar(lidar2ego):
    """(x, y) of the ego-frame origin expressed in the LiDAR frame."""
    return np.linalg.inv(np.asarray(lidar2ego, dtype=float))[:2, 3].copy()


# ----------------------------------------------------------------------------- plans

def time_grid(horizon_s, dt_s):
    """Uniform grid 0, dt, ..., horizon (horizon must be an integer multiple of dt)."""
    n = int(round(horizon_s / dt_s))
    if n < 1 or abs(n * dt_s - horizon_s) > 1e-6:
        raise ValueError(f'horizon {horizon_s} is not a positive multiple of dt {dt_s}')
    return np.linspace(0.0, n * dt_s, n + 1)


def plan_knots(plan_xy, plan_dt_s=PLAN_DT_S):
    """Knot times and positions of a plan, including the LiDAR origin (0, 0) at tau = 0."""
    plan = np.asarray(plan_xy, dtype=float)
    if plan.ndim != 2 or plan.shape[1] != 2 or len(plan) < 1:
        raise ValueError(f'plan must be (K, 2), got {plan.shape}')
    t = np.arange(len(plan) + 1, dtype=float) * plan_dt_s
    return t, np.vstack([np.zeros((1, 2)), plan])


def path_headings(tau, xy, initial_yaw, min_speed_mps=0.5):
    """Heading of a vehicle following a sampled path, from central finite differences.

    tau = 0 keeps initial_yaw (the vehicle's current forward axis). Where the finite-difference speed is
    below min_speed_mps the previous heading is held (a stationary vehicle does not rotate). Motion that
    points backwards relative to the held heading is treated as reversing (heading = travel direction + pi).
    """
    tau = np.asarray(tau, dtype=float)
    xy = np.asarray(xy, dtype=float)
    M = len(tau)
    yaw = np.empty(M)
    prev = float(initial_yaw)
    yaw[0] = prev
    for m in range(1, M):
        lo, hi = m - 1, min(m + 1, M - 1)
        dx, dy = xy[hi] - xy[lo]
        span = tau[hi] - tau[lo]
        if span > 0 and math.hypot(dx, dy) >= min_speed_mps * span:
            h = math.atan2(dy, dx)
            if math.cos(h - prev) < 0.0:
                h = wrap_angle(h + math.pi)
            prev = h
        yaw[m] = prev
    return yaw


def interpolate_plan(plan_xy, dt_s=0.05, horizon_s=3.0, initial_yaw=math.pi / 2, min_speed_mps=0.5,
                     plan_dt_s=PLAN_DT_S):
    """Piecewise-linear interpolation of a plan on a dt grid. Returns tau (M,), xy (M, 2), yaw (M,)."""
    kt, kxy = plan_knots(plan_xy, plan_dt_s)
    if not np.isfinite(kxy).all():
        raise ValueError('non-finite plan')
    if horizon_s > kt[-1] + 1e-9:
        raise ValueError(f'plan covers {kt[-1]} s < horizon {horizon_s} s')
    tau = time_grid(horizon_s, dt_s)
    xy = np.stack([np.interp(tau, kt, kxy[:, 0]), np.interp(tau, kt, kxy[:, 1])], axis=-1)
    return tau, xy, path_headings(tau, xy, initial_yaw, min_speed_mps)


def constant_velocity_path(speed_mps, forward_yaw, n=PLAN_STEPS, plan_dt_s=PLAN_DT_S):
    """Plan-agnostic ego path: straight line along the current forward axis at constant speed (n, 2)."""
    t = np.arange(1, n + 1, dtype=float) * plan_dt_s
    d = np.array([math.cos(forward_yaw), math.sin(forward_yaw)])
    return (max(float(speed_mps), 0.0) * t)[:, None] * d[None, :]


# ----------------------------------------------------------------------------- oriented boxes

def box_corners(center_xy, yaw, half_length, half_width):
    """Corners (..., 4, 2) of oriented boxes, counter-clockwise (FL, RL, RR, FR)."""
    c = np.asarray(center_xy, dtype=float)
    yaw = np.asarray(yaw, dtype=float)
    hl = np.asarray(half_length, dtype=float)
    hw = np.asarray(half_width, dtype=float)
    ca, sa = np.cos(yaw), np.sin(yaw)
    f = np.stack([ca * hl, sa * hl], axis=-1)
    lft = np.stack([-sa * hw, ca * hw], axis=-1)
    return np.stack([c + f + lft, c - f + lft, c - f - lft, c + f - lft], axis=-2)


def ego_footprint(xy, yaw, half_length, half_width, center_offset_xy, forward_yaw):
    """Ego box corners (M, 4, 2) when its LiDAR origin is at xy (M, 2) with heading yaw (M,).

    center_offset_xy is the box center relative to the LiDAR origin at capture (heading forward_yaw); it
    rotates rigidly with the vehicle.
    """
    yaw = np.asarray(yaw, dtype=float)
    off = rotate(np.asarray(center_offset_xy, dtype=float), yaw - forward_yaw)
    return box_corners(np.asarray(xy, dtype=float) + off, yaw, half_length, half_width)


def _segment_distance(p, a, b):
    """Distance from points p to segments [a, b] (all broadcastable (..., 2))."""
    ab = b - a
    ap = p - a
    den = (ab * ab).sum(-1)
    t = np.divide((ap * ab).sum(-1), den, out=np.zeros(np.broadcast_shapes(den.shape, ap.shape[:-1])), where=den > 0)
    t = np.clip(t, 0.0, 1.0)
    d = ap - ab * t[..., None]
    return np.sqrt((d * d).sum(-1))


def _broadcast_polys(A, B):
    A = np.asarray(A, dtype=float)
    B = np.asarray(B, dtype=float)
    lead = np.broadcast_shapes(A.shape[:-2], B.shape[:-2])
    return np.broadcast_to(A, lead + A.shape[-2:]), np.broadcast_to(B, lead + B.shape[-2:])


def _edges(x, y):
    return np.roll(x, -1, axis=-1) - x, np.roll(y, -1, axis=-1) - y


def _sat_separated(ax, ay, bx, by):
    """True where some edge normal of either polygon separates them (component arrays (..., n))."""
    sep = None
    for px, py in ((ax, ay), (bx, by)):
        ex, ey = _edges(px, py)
        nx, ny = -ey[..., :, None], ex[..., :, None]                     # (..., n_axes, 1)
        pa = ax[..., None, :] * nx + ay[..., None, :] * ny               # (..., n_axes, nA)
        pb = bx[..., None, :] * nx + by[..., None, :] * ny
        s = ((pa.max(-1) < pb.min(-1)) | (pb.max(-1) < pa.min(-1))).any(-1)
        sep = s if sep is None else (sep | s)
    return sep


def _vertex_edge_d2(px, py, qx, qy):
    """Min squared distance from the vertices of P to the edges of Q (component arrays (..., n))."""
    ex, ey = _edges(qx, qy)
    L2 = ex * ex + ey * ey
    inv = np.divide(1.0, L2, out=np.zeros_like(L2), where=L2 > 0)[..., None, :]
    ex, ey = ex[..., None, :], ey[..., None, :]
    rx = px[..., :, None] - qx[..., None, :]                             # (..., nP, nQ)
    ry = py[..., :, None] - qy[..., None, :]
    t = np.clip((rx * ex + ry * ey) * inv, 0.0, 1.0)
    dx = rx - t * ex
    dy = ry - t * ey
    return (dx * dx + dy * dy).min(axis=(-1, -2))


def convex_overlap(A, B):
    """Separating-axis test for convex polygons A (..., nA, 2), B (..., nB, 2). Touching counts as overlap."""
    A, B = _broadcast_polys(A, B)
    return ~_sat_separated(A[..., 0], A[..., 1], B[..., 0], B[..., 1])


def convex_distance(A, B):
    """Exact Euclidean distance between convex polygons (0 when they overlap or touch).

    For disjoint convex polygons the distance is attained between a vertex of one and an edge of the
    other, so the minimum over all vertex-edge pairs (both ways) is exact.
    """
    A, B = _broadcast_polys(A, B)
    ax, ay, bx, by = A[..., 0], A[..., 1], B[..., 0], B[..., 1]
    d2 = np.minimum(_vertex_edge_d2(ax, ay, bx, by), _vertex_edge_d2(bx, by, ax, ay))
    return np.where(_sat_separated(ax, ay, bx, by), np.sqrt(d2), 0.0)


def point_convex_distance(P, poly):
    """Distance from points P (..., 2) to the filled convex polygon poly (..., n, 2); 0 inside."""
    P = np.asarray(P, dtype=float)
    poly = np.asarray(poly, dtype=float)
    poly1 = np.roll(poly, -1, axis=-2)
    e = poly1 - poly
    rel = P[..., None, :] - poly
    cross = e[..., 0] * rel[..., 1] - e[..., 1] * rel[..., 0]
    inside = (cross >= 0).all(-1) | (cross <= 0).all(-1)
    d = _segment_distance(P[..., None, :], poly, poly1).min(-1)
    return np.where(inside, 0.0, d)


def hausdorff_convex(A, B):
    """Exact Hausdorff distance between filled convex polygons (attained at vertices)."""
    A, B = _broadcast_polys(A, B)
    dA = point_convex_distance(A, B[..., None, :, :]).max(-1)
    dB = point_convex_distance(B, A[..., None, :, :]).max(-1)
    return np.maximum(dA, dB)


def first_crossing_time(tau, slack, level=0.0):
    """First tau at which slack (..., M) drops to <= level, linearly interpolated between grid points.

    Returns 0 where slack[..., 0] <= level and +inf where it never drops (callers cap or censor).
    """
    tau = np.asarray(tau, dtype=float)
    s = np.asarray(slack, dtype=float) - level
    bad = s <= 0
    hit = bad.any(-1)
    m = np.argmax(bad, axis=-1)
    out = np.full(s.shape[:-1], np.inf)
    out = np.where(hit & (m == 0), 0.0, out)
    inner = hit & (m > 0)
    if np.any(inner):
        mm = np.where(inner, m, 1)
        s0 = np.take_along_axis(s, (mm - 1)[..., None], -1)[..., 0]
        s1 = np.take_along_axis(s, mm[..., None], -1)[..., 0]
        ok = np.isfinite(s0) & np.isfinite(s1) & (s0 - s1 > 0)
        frac = np.where(ok, s0 / np.where(ok, s0 - s1, 1.0), 1.0)
        t = tau[mm - 1] + np.clip(frac, 0.0, 1.0) * (tau[mm] - tau[mm - 1])
        out = np.where(inner, t, out)
    return float(out) if np.ndim(out) == 0 else out


# ----------------------------------------------------------------------------- ground-truth tracks

class GTTrack:
    """Ground-truth actors of one clip, indexed by actor id. OFFLINE scoring and calibration only.

    Rows follow gt/<clip>.jsonl: {frame_idx, ego: {center_xy, yaw, half_length, half_width},
    actors: [{id, class, center_xy, yaw, half_length, half_width, speed}]} in right-handed world
    coordinates. Interpolation between frames is by actor id: linear in position, shortest arc in yaw.
    An actor present in only one of the two neighbouring frames is held at that frame's pose for the
    half interval nearest to it (appearing/vanishing actors are never silently dropped).
    """

    def __init__(self, rows, max_gap_s=0.25, frame_dt_s=FRAME_DT_S):
        rows = sorted(rows, key=lambda r: int(r['frame_idx']))
        frames = [int(r['frame_idx']) for r in rows]
        if not frames:
            raise ValueError('empty ground truth')
        if len(set(frames)) != len(frames):
            raise ValueError('duplicate ground-truth frame')
        self.frame_idx = np.asarray(frames, dtype=int)
        self.t = self.frame_idx * float(frame_dt_s)
        self.max_gap_s = float(max_gap_s)
        ids = sorted({str(a['id']) for r in rows for a in r['actors']})
        self.ids = ids
        index = {a: i for i, a in enumerate(ids)}
        F, A = len(rows), len(ids)
        self.xy = np.zeros((F, A, 2))
        self.yaw = np.zeros((F, A))
        self.hl = np.zeros((F, A))
        self.hw = np.zeros((F, A))
        self.speed = np.full((F, A), np.nan)
        self.vel_given = np.zeros((F, A, 2))
        self.vel_given_ok = np.zeros((F, A), dtype=bool)
        self.present = np.zeros((F, A), dtype=bool)
        cls = [''] * A
        self.ego_xy = np.zeros((F, 2))
        self.ego_yaw = np.zeros(F)
        self.ego_hl = np.zeros(F)
        self.ego_hw = np.zeros(F)
        for f, r in enumerate(rows):
            e = r['ego']
            self.ego_xy[f] = np.asarray(e['center_xy'], dtype=float)[:2]
            self.ego_yaw[f] = float(e['yaw'])
            self.ego_hl[f] = float(e['half_length'])
            self.ego_hw[f] = float(e['half_width'])
            for a in r['actors']:
                j = index[str(a['id'])]
                if self.present[f, j]:
                    raise ValueError(f'duplicate actor {a["id"]} in frame {frames[f]}')
                c = str(a['class'])
                if c not in GT_CLASSES:
                    raise ValueError(f'unexpected ground-truth class {c!r}')
                if cls[j] and cls[j] != c:
                    raise ValueError(f'actor {a["id"]} changes class')
                cls[j] = c
                self.xy[f, j] = np.asarray(a['center_xy'], dtype=float)[:2]
                self.yaw[f, j] = float(a['yaw'])
                self.hl[f, j] = float(a['half_length'])
                self.hw[f, j] = float(a['half_width'])
                if a.get('speed') is not None:
                    self.speed[f, j] = float(a['speed'])
                v = a.get('velocity_xy')
                if v is not None and len(v) >= 2 and np.isfinite(np.asarray(v[:2], dtype=float)).all():
                    self.vel_given[f, j] = np.asarray(v[:2], dtype=float)   # writer's own world-frame estimate
                    self.vel_given_ok[f, j] = True
                self.present[f, j] = True
        self.cls = np.asarray(cls, dtype=object)
        self.group = np.asarray([GT_TO_GROUP[c] for c in cls], dtype=object)
        for name in ('xy', 'yaw', 'hl', 'hw', 'ego_xy', 'ego_yaw', 'ego_hl', 'ego_hw'):
            if not np.isfinite(getattr(self, name)).all():
                raise ValueError(f'non-finite ground truth in {name}')

    @classmethod
    def from_jsonl(cls, path, **kw):
        rows = []
        with open(path, encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return cls(rows, **kw)

    def frame_position(self, frame_idx):
        """Row index of a frame, or None."""
        i = int(np.searchsorted(self.frame_idx, int(frame_idx)))
        return i if i < len(self.frame_idx) and self.frame_idx[i] == int(frame_idx) else None

    def _bracket(self, ts):
        ts = np.atleast_1d(np.asarray(ts, dtype=float))
        F = len(self.t)
        inside = (ts >= self.t[0] - 1e-9) & (ts <= self.t[-1] + 1e-9)
        if F == 1:
            i = np.zeros(len(ts), dtype=int)
            return ts, i, i, np.zeros(len(ts)), inside & (np.abs(ts - self.t[0]) < 1e-9), np.ones(len(ts), bool)
        i = np.clip(np.searchsorted(self.t, ts, side='right') - 1, 0, F - 2)
        gap = self.t[i + 1] - self.t[i]
        u = np.clip((ts - self.t[i]) / gap, 0.0, 1.0)
        return ts, i, i + 1, u, inside, gap <= self.max_gap_s + 1e-9

    def actors_at(self, ts):
        """Actor states at absolute times ts (M,): xy (M,A,2), yaw, hl, hw (M,A), valid (M,A)."""
        ts, i0, i1, u, inside, ok_gap = self._bracket(ts)
        p0, p1 = self.present[i0], self.present[i1]
        at0 = (u < 1e-9)[:, None]
        at1 = (u > 1 - 1e-9)[:, None]
        g = ok_gap[:, None]
        both = p0 & p1 & g
        hold0 = p0 & ~p1 & (((u <= 0.5)[:, None] & g) | at0)
        hold1 = p1 & ~p0 & (((u >= 0.5)[:, None] & g) | at1)
        exact0 = p0 & at0
        exact1 = p1 & at1
        valid = (both | hold0 | hold1 | exact0 | exact1) & inside[:, None]
        w = np.where(both, u[:, None], np.where(hold1 | (exact1 & ~exact0), 1.0, 0.0))
        xy = self.xy[i0] + (self.xy[i1] - self.xy[i0]) * w[..., None]
        yaw = wrap_angle(self.yaw[i0] + wrap_angle(self.yaw[i1] - self.yaw[i0]) * w)
        hl = np.where(w >= 0.5, self.hl[i1], self.hl[i0])
        hw = np.where(w >= 0.5, self.hw[i1], self.hw[i0])
        return xy, yaw, hl, hw, valid

    def ego_at(self, ts):
        """Recorded ego box at absolute times ts: xy (M,2), yaw (M,), valid (M,)."""
        ts, i0, i1, u, inside, ok_gap = self._bracket(ts)
        xy = self.ego_xy[i0] + (self.ego_xy[i1] - self.ego_xy[i0]) * u[:, None]
        yaw = wrap_angle(self.ego_yaw[i0] + wrap_angle(self.ego_yaw[i1] - self.ego_yaw[i0]) * u)
        return xy, yaw, inside & (ok_gap | (u < 1e-9) | (u > 1 - 1e-9))

    def frame_velocities(self, prefer_given=True):
        """World velocity (F, A, 2) per frame and actor. Returns (v, ok).

        A 'velocity_xy' written with the ground truth (the sweep writer differentiates the full 10 Hz recording)
        is preferred. Otherwise finite differences of the stored positions, central where possible; frames
        separated by more than max_gap_s are not differenced; with no neighbour, vehicles fall back to
        speed * heading (CARLA reports vehicle speed exactly).
        """
        F, A = self.present.shape
        v = np.zeros((F, A, 2))
        ok = np.zeros((F, A), dtype=bool)
        if F >= 2:
            dt = np.diff(self.t)
            link = (dt <= self.max_gap_s + 1e-9)[:, None] & self.present[:-1] & self.present[1:]
            d = (self.xy[1:] - self.xy[:-1]) / dt[:, None, None]
            back = np.zeros((F, A), dtype=bool)
            fwd = np.zeros((F, A), dtype=bool)
            back[1:] = link
            fwd[:-1] = link
            vb = np.zeros((F, A, 2))
            vf = np.zeros((F, A, 2))
            vb[1:] = d
            vf[:-1] = d
            both = back & fwd
            span = np.zeros(F)
            span[1:-1] = self.t[2:] - self.t[:-2]
            central = np.zeros((F, A, 2))
            if F >= 3:
                central[1:-1] = (self.xy[2:] - self.xy[:-2]) / span[1:-1, None, None]
            v = np.where(both[..., None], central, np.where(back[..., None], vb, vf))
            ok = back | fwd
        fallback = ~ok & self.present & np.isfinite(self.speed) & (self.cls == 'vehicle')[None, :]
        if fallback.any():
            sp = np.where(fallback, self.speed, 0.0)
            v = np.where(fallback[..., None], sp[..., None] * np.stack([np.cos(self.yaw), np.sin(self.yaw)], -1), v)
            ok = ok | fallback
        if prefer_given and self.vel_given_ok.any():
            v = np.where(self.vel_given_ok[..., None], self.vel_given, v)
            ok = ok | self.vel_given_ok
        return v, ok

    def frame_accelerations(self, half_span_frames=2):
        """World acceleration (F, A, 2) from a centred second difference over +-half_span_frames frames."""
        F, A = self.present.shape
        h = int(half_span_frames)
        a = np.zeros((F, A, 2))
        ok = np.zeros((F, A), dtype=bool)
        if F < 2 * h + 1:
            return a, ok
        t0, t1, t2 = self.t[:-2 * h], self.t[h:-h], self.t[2 * h:]
        uniform = (np.abs((t1 - t0) - (t2 - t1)) < 1e-6) & ((t2 - t0) <= 2 * h * FRAME_DT_S + 1e-6)
        pres = self.present[:-2 * h] & self.present[h:-h] & self.present[2 * h:] & uniform[:, None]
        step = (t1 - t0)[:, None, None]
        acc = (self.xy[2 * h:] - 2 * self.xy[h:-h] + self.xy[:-2 * h]) / np.where(step > 0, step, 1.0) ** 2
        a[h:-h] = np.where(pres[..., None], acc, 0.0)
        ok[h:-h] = pres
        return a, ok


def load_gt(path, **kw):
    return GTTrack.from_jsonl(Path(path), **kw)
