"""Action-Validity Lease (AVL): for how long a plan derived from one observation stays valid.

Interface 2 (used by latency_agent.py / policies.py)
----------------------------------------------------
    EgoShape(half_length_m, half_width_m, center_offset_xy, forward_yaw_rad=pi/2)
    LeaseParams(d_safe_m=0.5, reserve_m=0.2, h_max_s=2.0, score_threshold=0.3, horizon_s=3.0, dt_s=0.05,
                sigma_m, vbar_mps, abar_mps2, <extensions with defaults>)
    compute_lease(plan_xy[6,2], dets[N,7], scores[N], labels[N], ego, params)
        -> dict(lease_s, margin_m, binding_index, reason, <extra diagnostic keys>)

All inputs are in the capture-time LiDAR frame (x right, y forward; see geometry.py). dets rows are
decode_boxes() output [cx, cy, length, width, yaw, vx, vy]; labels are UniDriveVLA detection label indices
(mapped to 'vehicle' / 'pedestrian' / 'other' by unidrive_boxes.CLASS_GROUP) or group names.
`forward_yaw_rad` is an extension of EgoShape: the yaw of the ego forward axis in the LiDAR frame
(pi/2 for Bench2Drive/UniDriveVLA; see geometry.forward_yaw_from_lidar2ego).

Method (FrameLease blueprint, Sec. 4)
-------------------------------------
* Ego footprint E(pi, tau): the plan is interpolated every dt_s from the LiDAR origin (0, 0) at tau = 0;
  heading from finite differences along the path; the oriented ego box rides rigidly on it.
* Agent footprint R_j(tau): detected oriented box translated with its estimated velocity (constant velocity).
* Margin of agent j: m_j = min_{tau in [0, horizon]} [ dist(E(pi, tau), R_j(tau)) - d_safe ] (exact polygon
  distance). Reported margin_m = m_k = min_j m_j over confident relevant agents.
* Degradation over staleness D: B_c(D) = vbar_c D + 0.5 abar_c D^2 + sigma_c for class group c.
* Lease: H_k = sup{ D in [0, H_max] : m_j - B_c(j)(D) > reserve for every relevant agent j } = min_j H_j,
  H_j = 2 s / (vbar + sqrt(vbar^2 + 2 abar s)) with slack s = m_j - sigma_c - reserve (the stable form of the
  quadratic root); H_j = 0 when s <= 0 (the margin check already fails). With a single class this is exactly
  the blueprint's H_k = sup{D : m_k - B_k(D) > reserve}; with class-dependent bounds the condition is
  imposed per agent, which is the exact supremum (using only the binding agent's class would not be).
  Soundness: if every agent's footprint error at staleness tau is <= B_c(tau) and the ego tracks the plan, the
  true clearance at every tau <= H_k is >= m_j - B_c(tau) > reserve, i.e. the blindly executed plan keeps
  d_safe + reserve until H_k. margin_mode='time_resolved' (extension, not the default) applies the same
  bound pointwise in tau, which is equally sound and never shorter.

Conservative handling (blueprint Sec. 4.4)
------------------------------------------
* Relevant agents: class groups in params.relevant_groups (default vehicle, pedestrian; the 'other' group,
  i.e. signs, lights, cones, is excluded because validity is defined against vehicles and walkers).
* Detections with score < score_threshold are ignored for the margin. Low-confidence detections with
  low_score_floor <= score < score_threshold must not lengthen the lease: with low_conf_mode='cap' (default)
  each of them caps the lease at the lease it would produce if it were real (same formula, own class bounds).
  This binds exactly when the detection is near the planned path (a far one yields H_max), so a low score
  can only shorten the lease; it never extends it. Below low_score_floor detections are treated as clutter.
* Non-finite plan or a non-finite relevant detection: lease 0 (perception or planning state not trustworthy).
* No relevant agent: the lease is H_max, never unbounded.
* Possibly undetected agents (missed, occluded, beyond range): the lease cannot see them. They are covered
  only by the H_max cap, which must not exceed the time an unseen agent needs to reach the swept ego path
  from outside the reliably detected range; calibration.py reports that admissible bound from measured
  recall versus range, and c2_eval.py attributes residual over-estimates to detected versus undetected agents.
  The lease is not a collision probability and passing the check is not a safety certificate.
"""
from __future__ import annotations

import dataclasses
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from framelease_v2.geometry import (box_corners, constant_velocity_path, convex_distance, ego_footprint,
                                    first_crossing_time, interpolate_plan, rotate, time_grid)

GROUPS = ('vehicle', 'pedestrian', 'other')

# UniDriveVLA det_class_names = [car, van, truck, bicycle, traffic_sign, traffic_cone, traffic_light,
# pedestrian, others]. Used only if framelease_v2.unidrive_boxes cannot be imported.
FALLBACK_CLASS_GROUP = {0: 'vehicle', 1: 'vehicle', 2: 'vehicle', 3: 'vehicle', 4: 'other', 5: 'other',
                        6: 'other', 7: 'pedestrian', 8: 'other'}

# Placeholder bounds before calibration (calibration.py replaces them with measured quantiles).
DEFAULT_SIGMA_M = {'vehicle': 1.0, 'pedestrian': 0.6, 'other': 1.0}
DEFAULT_VBAR_MPS = {'vehicle': 2.0, 'pedestrian': 1.0, 'other': 2.0}
DEFAULT_ABAR_MPS2 = {'vehicle': 4.0, 'pedestrian': 2.0, 'other': 4.0}


@dataclass
class EgoShape:
    half_length_m: float
    half_width_m: float
    center_offset_xy: tuple  # vehicle box center relative to the LiDAR origin, LiDAR frame
    forward_yaw_rad: float = math.pi / 2  # extension: yaw of the ego forward axis in the LiDAR frame

    def to_dict(self):
        return {'half_length_m': float(self.half_length_m), 'half_width_m': float(self.half_width_m),
                'center_offset_xy': [float(v) for v in self.center_offset_xy],
                'forward_yaw_rad': float(self.forward_yaw_rad)}

    @classmethod
    def from_dict(cls, d):
        return cls(float(d['half_length_m']), float(d['half_width_m']), tuple(float(v) for v in d['center_offset_xy']),
                   float(d.get('forward_yaw_rad', math.pi / 2)))


# Bench2Drive hero vehicle (Lincoln MKZ 2020): recorded box extent 2.446 x 0.918 m (half sizes); the box
# center is 0.006 m behind the ego origin and the LiDAR is 0.39 m behind the ego origin, so the box center is
# (0, 0.384) in the LiDAR frame (x right, y forward). Vehicle constants, not perception.
B2D_EGO = EgoShape(2.4462, 0.9184, (0.0, 0.3837), math.pi / 2)


def ego_shape_from_lidar2ego(lidar2ego, half_length_m, half_width_m, box_center_in_ego_xy=(0.0, 0.0)):
    """EgoShape from the LiDAR mounting (lidar2ego maps LiDAR to right-handed ego coordinates, x forward)."""
    inv = np.linalg.inv(np.asarray(lidar2ego, dtype=float))
    c = inv @ np.array([box_center_in_ego_xy[0], box_center_in_ego_xy[1], 0.0, 1.0])
    f = inv[:3, :3] @ np.array([1.0, 0.0, 0.0])
    return EgoShape(float(half_length_m), float(half_width_m), (float(c[0]), float(c[1])), float(math.atan2(f[1], f[0])))


@dataclass
class LeaseParams:
    d_safe_m: float = 0.5
    reserve_m: float = 0.2
    h_max_s: float = 2.0
    score_threshold: float = 0.3
    horizon_s: float = 3.0
    dt_s: float = 0.05
    sigma_m: dict = field(default_factory=lambda: dict(DEFAULT_SIGMA_M))
    vbar_mps: dict = field(default_factory=lambda: dict(DEFAULT_VBAR_MPS))
    abar_mps2: dict = field(default_factory=lambda: dict(DEFAULT_ABAR_MPS2))
    # ---- extensions (defaults implement the documented conservative rules)
    low_score_floor: float = 0.1
    low_conf_mode: str = 'cap'            # 'cap' | 'ignore'
    relevant_groups: tuple = ('vehicle', 'pedestrian')
    margin_mode: str = 'global'           # 'global' (blueprint) | 'time_resolved'
    min_speed_mps: float = 0.5            # heading hold threshold along the plan

    def validate(self):
        if not (self.d_safe_m >= 0 and self.h_max_s > 0 and self.dt_s > 0 and self.horizon_s > 0):
            raise ValueError('d_safe_m >= 0, h_max_s > 0, dt_s > 0, horizon_s > 0 required')
        if self.h_max_s > self.horizon_s + 1e-9:
            raise ValueError('h_max_s must not exceed horizon_s')
        n = round(self.horizon_s / self.dt_s)
        if abs(n * self.dt_s - self.horizon_s) > 1e-6:
            raise ValueError('horizon_s must be a multiple of dt_s')
        if not 0 <= self.low_score_floor <= self.score_threshold:
            raise ValueError('need 0 <= low_score_floor <= score_threshold')
        if self.low_conf_mode not in ('cap', 'ignore'):
            raise ValueError('low_conf_mode must be cap or ignore')
        if self.margin_mode not in ('global', 'time_resolved'):
            raise ValueError('margin_mode must be global or time_resolved')
        for g in self.relevant_groups:
            if g not in GROUPS:
                raise ValueError(f'unknown group {g}')
            for name in ('sigma_m', 'vbar_mps', 'abar_mps2'):
                v = getattr(self, name).get(g)
                if v is None or not np.isfinite(v) or v < 0:
                    raise ValueError(f'{name}[{g}] must be a finite non-negative number')
        return self

    def bound(self, group, delta):
        """B_c(delta) for class group c."""
        d = np.asarray(delta, dtype=float)
        return self.vbar_mps[group] * d + 0.5 * self.abar_mps2[group] * d * d + self.sigma_m[group]

    def to_dict(self):
        d = dataclasses.asdict(self)
        d['relevant_groups'] = list(self.relevant_groups)
        for k in ('sigma_m', 'vbar_mps', 'abar_mps2'):
            d[k] = {g: float(v) for g, v in d[k].items()}
        return d

    @classmethod
    def from_dict(cls, d):
        names = {f.name for f in dataclasses.fields(cls)}
        clean = {}
        for k, v in d.items():
            if k.startswith('_'):
                continue
            if k not in names:
                raise ValueError(f'unknown LeaseParams field {k!r}')
            clean[k] = v
        if 'relevant_groups' in clean:
            clean['relevant_groups'] = tuple(clean['relevant_groups'])
        for k in ('sigma_m', 'vbar_mps', 'abar_mps2'):
            if k in clean:
                clean[k] = {str(g): float(v) for g, v in clean[k].items()}
        return cls(**clean).validate()


def save_lease_params(path, params, ego=None, meta=None):
    d = params.to_dict()
    if ego is not None:
        d['_ego_shape'] = ego.to_dict()
    if meta is not None:
        d['_meta'] = meta
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(d, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')


def load_lease_params(path):
    return LeaseParams.from_dict(json.loads(Path(path).read_text(encoding='utf-8')))


def load_ego_shape(path, default=None):
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    if '_ego_shape' in d:
        return EgoShape.from_dict(d['_ego_shape'])
    if default is None:
        raise KeyError(f'{path} has no _ego_shape')
    return default


# ----------------------------------------------------------------------------- class groups

_CLASS_GROUP = None
_CLASS_GROUP_SOURCE = None


def class_group_map():
    """(mapping label -> group, source). Prefers unidrive_boxes.CLASS_GROUP (Interface 1)."""
    global _CLASS_GROUP, _CLASS_GROUP_SOURCE
    if _CLASS_GROUP is None:
        try:
            from framelease_v2.unidrive_boxes import CLASS_GROUP as cg
            _CLASS_GROUP = {int(k): str(v) for k, v in cg.items()}
            _CLASS_GROUP_SOURCE = 'framelease_v2.unidrive_boxes.CLASS_GROUP'
        except Exception as e:  # unidrive_boxes is owned by another worker; keep the lease usable
            _CLASS_GROUP = dict(FALLBACK_CLASS_GROUP)
            _CLASS_GROUP_SOURCE = f'FALLBACK_CLASS_GROUP ({type(e).__name__}: {e})'
        bad = sorted({g for g in _CLASS_GROUP.values() if g not in GROUPS})
        if bad:
            raise ValueError(f'CLASS_GROUP has unknown groups {bad}')
    return _CLASS_GROUP, _CLASS_GROUP_SOURCE


def set_class_group(mapping, source='override'):
    """Override the label -> group map (tests, or a caller with its own decoder)."""
    global _CLASS_GROUP, _CLASS_GROUP_SOURCE
    _CLASS_GROUP = {int(k): str(v) for k, v in mapping.items()}
    _CLASS_GROUP_SOURCE = source


def resolve_groups(labels):
    labels = np.asarray(labels)
    if labels.dtype.kind in ('U', 'S', 'O'):
        out = np.asarray([str(x) for x in labels.reshape(-1)], dtype=object)
        bad = sorted({g for g in out if g not in GROUPS})
        if bad:
            raise ValueError(f'unknown group names {bad}')
        return out
    cg, _ = class_group_map()
    return np.asarray([cg.get(int(x), 'other') for x in labels.reshape(-1)], dtype=object)


# ----------------------------------------------------------------------------- geometry of one decision

@dataclass
class LeaseGeometry:
    """Everything the lease needs for one (plan, detection set); cheap to re-evaluate for other bounds."""
    tau: np.ndarray            # (M,) plan times 0 .. horizon
    clearance: np.ndarray      # (N, M) footprint distance minus d_safe, relevant agents with score >= floor
    index: np.ndarray          # (N,) row of each agent in the caller's arrays
    group: np.ndarray          # (N,) class group
    confident: np.ndarray      # (N,) score >= score_threshold
    status: str = 'ok'         # 'ok' | 'invalid_plan' | 'invalid_detection'
    invalid_index: object = None
    ego_corners: np.ndarray = None  # (M, 4, 2) ego footprint along the plan


def _empty_geometry(tau, status='ok', invalid_index=None, ego_corners=None):
    return LeaseGeometry(tau, np.zeros((0, len(tau))), np.zeros(0, dtype=int), np.zeros(0, dtype=object),
                         np.zeros(0, dtype=bool), status, invalid_index, ego_corners)


def ego_corners_along_plan(plan_xy, ego, params):
    tau, xy, yaw = interpolate_plan(plan_xy, params.dt_s, params.horizon_s, ego.forward_yaw_rad, params.min_speed_mps)
    return tau, xy, yaw, ego_footprint(xy, yaw, ego.half_length_m, ego.half_width_m, ego.center_offset_xy,
                                       ego.forward_yaw_rad)


def lease_geometry(plan_xy, dets, scores, labels, ego, params):
    tau = time_grid(params.horizon_s, params.dt_s)
    plan = np.asarray(plan_xy, dtype=float)
    if plan.ndim != 2 or plan.shape[1] != 2:
        return _empty_geometry(tau, 'invalid_plan')
    if not np.isfinite(plan).all():
        return _empty_geometry(tau, 'invalid_plan')
    try:
        tau, _, _, E = ego_corners_along_plan(plan, ego, params)
    except ValueError:
        return _empty_geometry(tau, 'invalid_plan')
    dets = np.asarray(dets, dtype=float).reshape(-1, 7)
    scores = np.asarray(scores, dtype=float).reshape(-1)
    if len(scores) != len(dets):
        raise ValueError('dets and scores differ in length')
    groups = resolve_groups(labels) if len(dets) else np.zeros(0, dtype=object)
    if len(groups) != len(dets):
        raise ValueError('dets and labels differ in length')
    relevant = np.isin(groups, list(params.relevant_groups)) & (np.nan_to_num(scores, nan=1.0) >= params.low_score_floor)
    finite = np.isfinite(dets).all(1) & np.isfinite(scores)
    broken = relevant & ~finite
    if broken.any():
        return _empty_geometry(tau, 'invalid_detection', int(np.flatnonzero(broken)[0]), E)
    idx = np.flatnonzero(relevant)
    if len(idx) == 0:
        return _empty_geometry(tau, 'ok', None, E)
    d = dets[idx]
    R0 = box_corners(d[:, 0:2], d[:, 4], 0.5 * np.abs(d[:, 2]), 0.5 * np.abs(d[:, 3]))       # (N, 4, 2)
    R = R0[:, None, :, :] + (tau[None, :, None, None] * d[:, None, None, 5:7])                # (N, M, 4, 2)
    dist = convex_distance(E[None], R)                                                       # (N, M)
    return LeaseGeometry(tau, dist - params.d_safe_m, idx, groups[idx], scores[idx] >= params.score_threshold,
                         'ok', None, E)


# ----------------------------------------------------------------------------- lease from geometry

def lease_root(slack, vbar, abar, h_max):
    """sup{D in [0, h_max]: vbar D + 0.5 abar D^2 < slack} (closed form, vectorised); 0 when slack <= 0."""
    s = np.asarray(slack, dtype=float)
    vbar = np.asarray(vbar, dtype=float)
    abar = np.asarray(abar, dtype=float)
    pos = s > 0
    s_pos = np.where(pos, s, 0.0)
    den = vbar + np.sqrt(vbar * vbar + 2.0 * abar * s_pos)
    with np.errstate(divide='ignore', invalid='ignore'):
        root = np.where(den > 0, 2.0 * s_pos / np.where(den > 0, den, 1.0), np.inf)
    out = np.where(pos, np.minimum(root, h_max), 0.0)
    return float(out) if np.ndim(out) == 0 else out


def _group_params(geom, params):
    sig = np.array([params.sigma_m[g] for g in geom.group], dtype=float)
    vb = np.array([params.vbar_mps[g] for g in geom.group], dtype=float)
    ab = np.array([params.abar_mps2[g] for g in geom.group], dtype=float)
    return sig, vb, ab


def agent_leases(geom, params, reserves, margin_mode=None):
    """Per-agent lease H_j for each reserve: array (R, N)."""
    mode = margin_mode or params.margin_mode
    reserves = np.atleast_1d(np.asarray(reserves, dtype=float))
    N = len(geom.index)
    if N == 0:
        return np.zeros((len(reserves), 0))
    sig, vb, ab = _group_params(geom, params)
    if mode == 'global':
        m = geom.clearance.min(axis=1)                                                       # (N,)
        slack = m[None, :] - sig[None, :] - reserves[:, None]
        return lease_root(slack, vb[None, :], ab[None, :], params.h_max_s)
    keep = geom.tau < params.h_max_s + params.dt_s - 1e-9   # grid up to the first point >= H_max
    tau = geom.tau[keep]
    c = geom.clearance[:, keep]                                                              # (N, Mh)
    B = vb[:, None] * tau[None, :] + 0.5 * ab[:, None] * tau[None, :] ** 2 + sig[:, None]
    g = c[None] - B[None] - reserves[:, None, None]                                          # (R, N, Mh)
    bad = g <= 0
    hit = bad.any(-1)
    m = np.argmax(bad, axis=-1)                                                              # (R, N)
    out = np.where(hit, 0.0, np.inf)
    inner = hit & (m > 0)
    if inner.any():
        # Clearance is linear between grid points and B is quadratic, so the crossing inside
        # [tau0, tau0 + dt] is the positive root of a convex quadratic in u = tau - tau0 (exact).
        mm = np.where(inner, m, 1)
        idx = (mm - 1)[..., None]
        c0 = np.take_along_axis(np.broadcast_to(c, g.shape), idx, -1)[..., 0]
        c1 = np.take_along_axis(np.broadcast_to(c, g.shape), mm[..., None], -1)[..., 0]
        t0, t1 = tau[mm - 1], tau[mm]
        k = (c1 - c0) / (t1 - t0)
        g0 = np.take_along_axis(g, idx, -1)[..., 0]                                         # > 0
        a2 = 0.5 * ab[None, :]
        b1 = ab[None, :] * t0 + vb[None, :] - k
        den = b1 + np.sqrt(np.maximum(b1 * b1 + 4.0 * a2 * g0, 0.0))
        u = np.where(den > 0, 2.0 * g0 / np.where(den > 0, den, 1.0), t1 - t0)
        out = np.where(inner, t0 + np.clip(u, 0.0, t1 - t0), out)
    return np.minimum(out, params.h_max_s)


def lease_sweep(geom, params, reserves, include_low_conf=None, margin_mode=None):
    """Lease for each reserve value (R,), identical to lease_from_geometry for that reserve."""
    reserves = np.atleast_1d(np.asarray(reserves, dtype=float))
    if geom.status != 'ok':
        return np.zeros(len(reserves))
    use_low = (params.low_conf_mode == 'cap') if include_low_conf is None else bool(include_low_conf)
    sel = geom.confident | (use_low & ~geom.confident)
    H = agent_leases(geom, params, reserves, margin_mode)
    if H.shape[1] == 0 or not sel.any():
        return np.full(len(reserves), float(params.h_max_s))
    return np.minimum(H[:, sel].min(axis=1), params.h_max_s)


def lease_from_geometry(geom, params, reserve_m=None, margin_mode=None):
    reserve = params.reserve_m if reserve_m is None else float(reserve_m)
    mode = margin_mode or params.margin_mode
    base = {'lease_s': 0.0, 'margin_m': float('inf'), 'binding_index': None, 'reason': '',
            'binding_group': None, 'binding_tau_s': None, 'closest_index': None, 'n_confident': int(geom.confident.sum()),
            'n_low_confidence': int((~geom.confident).sum()), 'lease_confident_only_s': None, 'margin_mode': mode}
    if geom.status == 'invalid_plan':
        base.update(reason='invalid_plan', margin_m=float('nan'))
        return base
    if geom.status == 'invalid_detection':
        base.update(reason='invalid_detection', binding_index=geom.invalid_index, margin_m=float('nan'))
        return base
    h_max = float(params.h_max_s)
    conf = geom.confident
    if conf.any():
        m_conf = geom.clearance[conf].min(axis=1)
        j = int(np.argmin(m_conf))
        base['margin_m'] = float(m_conf[j])
        base['closest_index'] = int(geom.index[conf][j])
    use_low = params.low_conf_mode == 'cap'
    sel = conf | (use_low & ~conf)
    if not sel.any():
        base.update(lease_s=h_max, reason='no_relevant_agents', lease_confident_only_s=h_max)
        return base
    H = agent_leases(geom, params, [reserve], mode)[0]                                       # (N,)
    Hc = H[conf]
    base['lease_confident_only_s'] = float(min(Hc.min(), h_max)) if len(Hc) else h_max
    cand = np.flatnonzero(sel)
    k = cand[np.lexsort((geom.clearance[cand].min(axis=1), H[cand]))[0]]
    lease = float(min(H[k], h_max))
    base['lease_s'] = lease
    if lease >= h_max - 1e-12:
        base['reason'] = 'h_max_cap'
        return base
    base.update(binding_index=int(geom.index[k]), binding_group=str(geom.group[k]),
                binding_tau_s=float(geom.tau[int(np.argmin(geom.clearance[k]))]))
    low = not conf[k]
    if lease <= 0.0:
        base['reason'] = 'low_confidence_margin_violated' if low else 'margin_violated'
    else:
        base['reason'] = 'low_confidence_cap' if low else 'bound_crossing'
    return base


def compute_lease(plan_xy, dets, scores, labels, ego, params):
    """Interface 2. See the module docstring for the definition and the conservative rules."""
    return lease_from_geometry(lease_geometry(plan_xy, dets, scores, labels, ego, params), params)


# ----------------------------------------------------------------------------- baselines (same inputs, no plan)

def plan_agnostic_lease(speed_mps, dets, scores, labels, ego, params):
    """Same lease formula with the ego path replaced by a straight constant-velocity extrapolation."""
    return compute_lease(constant_velocity_path(speed_mps, ego.forward_yaw_rad), dets, scores, labels, ego, params)


def ttc_from_geometry(geom):
    """Time until the predicted clearance to any confident relevant agent first drops to <= 0 (inf if never).

    No uncertainty bounds; with the plan-agnostic (constant-velocity) geometry this is a footprint TTC to
    d_safe, i.e. the classic time-to-collision measured against the same safety distance as validity.
    """
    if geom.status != 'ok':
        return 0.0
    if not geom.confident.any():
        return float('inf')
    return float(first_crossing_time(geom.tau, geom.clearance[geom.confident].min(axis=0)))


def ttc_seconds(speed_mps, dets, scores, labels, ego, params):
    plan = constant_velocity_path(speed_mps, ego.forward_yaw_rad)
    return ttc_from_geometry(lease_geometry(plan, dets, scores, labels, ego, params))


def ttc_lease(ttc_s, threshold_s, h_max_s):
    """TTC-threshold refresh as a lease: valid until the remaining TTC falls below threshold_s."""
    return np.clip(np.asarray(ttc_s, dtype=float) - threshold_s, 0.0, h_max_s)


def speed_deadline_lease(speed_mps, distance_m, h_max_s, min_speed_mps=0.1):
    """Refresh after the ego has travelled distance_m at its current speed."""
    v = np.maximum(np.asarray(speed_mps, dtype=float), min_speed_mps)
    return np.clip(distance_m / v, 0.0, h_max_s)


def fixed_ttl_lease(ttl_s, h_max_s):
    """Constant lease; identical to an observation-age (AoI) threshold rule."""
    return float(np.clip(ttl_s, 0.0, h_max_s))


__all__ = ['EgoShape', 'LeaseParams', 'compute_lease', 'B2D_EGO', 'ego_shape_from_lidar2ego', 'lease_geometry',
           'lease_from_geometry', 'lease_sweep', 'agent_leases', 'lease_root', 'plan_agnostic_lease', 'ttc_seconds',
           'ttc_from_geometry', 'ttc_lease', 'speed_deadline_lease', 'fixed_ttl_lease', 'class_group_map',
           'set_class_group', 'resolve_groups', 'save_lease_params', 'load_lease_params', 'load_ego_shape',
           'LeaseGeometry', 'GROUPS', 'rotate']
