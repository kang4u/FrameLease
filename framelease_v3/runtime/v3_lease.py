"""Suffix-aligned, first-failure action-validity lease (outline Eq. 1-3) with a pluggable residual envelope.

Definitions (capture-time LiDAR frame of the candidate's own observation, x right, y forward)
---------------------------------------------------------------------------------------------
* tau in [0, T_pred] is plan time after capture t_k; grid tau_m = m * dt (dt = 0.05 s, T_pred = 3.0 s, 61 points).
* E(tau): ego footprint along the plan (framelease_v2.lease.ego_corners_along_plan: the plan interpolated from the
  LiDAR origin at tau = 0, heading from finite differences, the ego box riding rigidly on it).
* R_j(tau): relevant detection j of the model's OWN perception output (never simulator state), its decoded box moved
  with its own velocity estimate (constant velocity).
* S_j(tau): residual envelope of agent j (class group c_j, motion state from the detected speed):
      isotropic    S = disc of radius B(tau)        dist(E, R (+) S) = max(0, dist(E, R) - B)
      anisotropic  S = [-B_lon, B_lon] x [-B_lat, B_lat] in the DETECTED heading frame of the agent, i.e.
                   R (+) S = the detected box with half extents (hl + B_lon(tau), hw + B_lat(tau))
* Pointwise margin of agent j: g_j(tau) = dist(E(tau), R_j(tau) (+) S_j(tau)) - d_safe;  g = min_j g_j.

Eq. 1-3 and the closed form (exact)
-----------------------------------
    M(Delta) = min_{tau in [Delta, Delta + T_c]} g(tau)                                    (Eq. 1)
    H = inf({Delta in [0, H_bar] : M(Delta) <= delta} U {H_bar}),  H_bar = max(0, T_pred - T_c)   (Eq. 2)
    D = t_k + H                                                                            (Eq. 3)
With tau* = the first tau at which g(tau) <= delta (0 if g(0) <= delta; none -> H = H_bar) and g continuous,
M(Delta) <= delta  <=>  Delta + T_c >= tau*, hence  H = clip(tau* - T_c, 0, H_bar).  Refinement never changes t_k.
tau* = min_j tau*_j, the first crossing of each agent's own margin.

Interpolation between grid points (the conventions of the offline Gate-2 study, framelease_v3/suffix_lease_eval.py):
* isotropic quadratic envelope B = sigma + vbar tau + 0.5 abar tau^2 (default; v2 LeaseParams form): clearance
  dist(E, R) - d_safe linear between grid points, B exact; the per-agent crossing is framelease_v2.lease.agent_leases
  in 'time_resolved' mode (exact quadratic root), i.e. the identical function the offline study uses for E0;
* table envelopes (isotropic or anisotropic B(tau) tables): g_j evaluated exactly at grid points (exact polygon
  distance to the inflated box), linear in between (framelease_v2.geometry.first_crossing_time per agent).
In both cases g_j is concave or linear between grid points, so an agent whose lower bound on g_j exceeds delta at
every grid point never crosses: the bounding-circle prefilter (skip such agents) is exact (tested).

The commit-time check of Eq. 9, M(t_commit - t_k) > delta, is evaluated literally from the stored per-agent margins
(LeaseResult.margin) with the same interpolants, independently of tau*.

Relevant agents and conservative rules are framelease_v2.lease's: groups vehicle / pedestrian; with
low_conf_mode = 'cap' detections with score >= low_score_floor count (a low-confidence detection can only shorten the
lease), else score >= score_threshold; a non-finite plan or relevant detection, or missing perception, gives lease 0;
no relevant agent gives H_bar. The envelope covers detected agents only; undetected agents are not covered.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field, fields
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import numpy as np

from framelease_v2 import lease as L2
from framelease_v2.geometry import box_corners, convex_distance, ego_footprint, first_crossing_time, time_grid

SCHEMA = 'framelease_v3.runtime.lease/2'
GROUPS = ('vehicle', 'pedestrian')
BIN_NAMES = ('static', 'moving')
DEFAULT_STATIC_SPEED_MPS = 0.5      # framelease_v3/envelopes.py STATIC_SPEED_MPS (static < 0.5 m/s <= moving)


# ============================================================================================ configuration

@dataclass
class SuffixLeaseConfig:
    """Lease constants (decided values) and the detection-selection rules shared with framelease_v2.lease."""
    t_pred_s: float = 3.0           # prediction coverage T_pred (6 waypoints x 0.5 s)
    t_c_s: float = 0.5              # control execution horizon T_c a committed action must cover
    d_safe_m: float = 0.5           # safety distance inside the pointwise margin
    delta_m: float = 0.2            # required margin threshold delta
    dt_s: float = 0.05              # tau grid
    score_threshold: float = 0.3    # confident detections
    low_score_floor: float = 0.1    # low-confidence detections still cap the lease (low_conf_mode = 'cap')
    low_conf_mode: str = 'cap'      # 'cap' | 'ignore'
    relevant_groups: tuple = GROUPS
    min_speed_mps: float = 0.5      # heading hold threshold along the plan (v2 interpolate_plan)
    prefilter: bool = True          # exact bounding-circle prefilter (bit-identical lease, tested)

    @property
    def h_bar_s(self):
        return max(0.0, float(self.t_pred_s) - float(self.t_c_s))

    def validate(self):
        if not (self.t_pred_s > 0 and self.t_c_s >= 0 and self.dt_s > 0 and self.d_safe_m >= 0):
            raise ValueError('need t_pred_s > 0, t_c_s >= 0, dt_s > 0, d_safe_m >= 0')
        if self.t_pred_s > 3.0 + 1e-9:
            raise ValueError('t_pred_s cannot exceed the 3.0 s plan coverage')
        if not self.delta_m > -self.d_safe_m:
            raise ValueError('delta_m must exceed -d_safe_m')
        time_grid(self.t_pred_s, self.dt_s)
        if not 0 <= self.low_score_floor <= self.score_threshold:
            raise ValueError('need 0 <= low_score_floor <= score_threshold')
        if self.low_conf_mode not in ('cap', 'ignore'):
            raise ValueError('low_conf_mode must be cap or ignore')
        for g in self.relevant_groups:
            if g not in L2.GROUPS:
                raise ValueError(f'unknown group {g}')
        return self

    def to_dict(self):
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        d['relevant_groups'] = list(self.relevant_groups)
        d['h_bar_s'] = self.h_bar_s
        return d

    @classmethod
    def from_dict(cls, d):
        d = dict(d or {})
        d.pop('h_bar_s', None)
        names = {f.name for f in fields(cls)}
        unknown = sorted(set(d) - names)
        if unknown:
            raise ValueError(f'unknown lease config keys {unknown}')
        if 'relevant_groups' in d:
            d['relevant_groups'] = tuple(d['relevant_groups'])
        return cls(**d).validate()


# ============================================================================================ envelopes

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def _key_candidates(group, moving, motion_bins):
    if motion_bins:
        return (f'{group}/{BIN_NAMES[int(bool(moving))]}', str(group))
    return (str(group),)


class Envelope:
    """Residual envelope B(tau) per agent (class group, motion state). Subclasses:

    IsoQuadraticEnvelope  'iso'        B = sigma + vbar tau + 0.5 abar tau^2 per key (v2 LeaseParams / Gate-2 E0)
    IsoTableEnvelope      'iso_table'  B(tau) table per key, linear in tau
    AnisoTableEnvelope    'aniso'      (B_lon(tau), B_lat(tau)) tables per key along / across the detected heading
                                       (Gate-2 E1; E2 with motion_bins)
    A key is a class group ('vehicle') or, with motion_bins, 'group/static' | 'group/moving' (falling back to the
    plain group key). The motion state is the DETECTED speed: moving iff |v_det| >= static_speed_mps.
    """
    kind = 'base'

    def __init__(self, source='inline', sha256=None, meta=None, motion_bins=False,
                 static_speed_mps=DEFAULT_STATIC_SPEED_MPS):
        self.source = source
        self.sha256 = sha256
        self.meta = meta or {}
        self.motion_bins = bool(motion_bins)
        self.static_speed_mps = float(DEFAULT_STATIC_SPEED_MPS if static_speed_mps is None else static_speed_mps)
        if not self.static_speed_mps >= 0:
            raise ValueError('static_speed_mps must be >= 0')

    def keys_needed(self, groups):
        return [(g, mv) for g in groups for mv in ((False, True) if self.motion_bins else (False,))]

    def describe(self):
        return {'kind': self.kind, 'source': self.source, 'sha256': self.sha256, 'motion_bins': self.motion_bins,
                'static_speed_mps': self.static_speed_mps, 'meta': self.meta}


class IsoQuadraticEnvelope(Envelope):
    kind = 'iso'

    def __init__(self, sigma_m, vbar_mps, abar_mps2, **kw):
        super().__init__(**kw)
        self.sigma = {str(k): float(v) for k, v in sigma_m.items()}
        self.vbar = {str(k): float(v) for k, v in vbar_mps.items()}
        self.abar = {str(k): float(v) for k, v in abar_mps2.items()}

    def _lookup(self, table, group, moving):
        for k in _key_candidates(group, moving, self.motion_bins):
            if k in table:
                return table[k]
        raise KeyError(f'envelope has no entry for group {group!r} (keys {sorted(table)})')

    def params(self, groups, moving):
        """(sigma, vbar, abar) arrays (N,) for the agents."""
        mv = np.zeros(len(groups), dtype=bool) if moving is None else np.asarray(moving, dtype=bool)
        out = [np.array([self._lookup(t, g, m) for g, m in zip(groups, mv)], dtype=float)
               for t in (self.sigma, self.vbar, self.abar)]
        return tuple(out)

    def check(self, groups, tau):
        for g, mv in self.keys_needed(groups):
            s, v, a = (x[0] for x in self.params([g], [mv]))
            if not all(math.isfinite(x) and x >= 0 for x in (s, v, a)):
                raise ValueError(f'envelope gives a non-finite or negative parameter for {g}')
        return self

    def describe(self):
        return {**super().describe(), 'sigma_m': self.sigma, 'vbar_mps': self.vbar, 'abar_mps2': self.abar}


class _TableEnvelope(Envelope):
    """Values per key on the table's own tau grid, linearly interpolated onto the lease grid (must cover it)."""

    def __init__(self, tau_s, **kw):
        super().__init__(**kw)
        self.tau_s = np.asarray(tau_s, dtype=float)
        if self.tau_s.ndim != 1 or len(self.tau_s) < 2 or np.any(np.diff(self.tau_s) <= 0):
            raise ValueError('envelope tau_s must be a strictly increasing 1-D grid')
        self._cache = {}

    def _row(self, table, group, moving, tau):
        key = None
        for k in _key_candidates(group, moving, self.motion_bins):
            if k in table:
                key = k
                break
        if key is None:
            raise KeyError(f'envelope has no entry for group {group!r} (keys {sorted(table)})')
        ck = (id(table), key, len(tau), float(tau[0]), float(tau[-1]))
        hit = self._cache.get(ck)
        if hit is None:
            vals = np.asarray(table[key], dtype=float)
            if vals.shape != self.tau_s.shape:
                raise ValueError(f'envelope entry {key!r} has {vals.shape} values for {self.tau_s.shape} taus')
            if tau[0] < self.tau_s[0] - 1e-9 or tau[-1] > self.tau_s[-1] + 1e-9:
                raise ValueError(f'envelope covers tau in [{self.tau_s[0]}, {self.tau_s[-1]}], '
                                 f'the lease needs [{tau[0]}, {tau[-1]}]')
            hit = np.interp(tau, self.tau_s, vals)
            hit.setflags(write=False)
            self._cache[ck] = hit
        return hit

    def rows(self, table, groups, moving, tau):
        tau = np.asarray(tau, dtype=float)
        mv = np.zeros(len(groups), dtype=bool) if moving is None else np.asarray(moving, dtype=bool)
        if len(groups) == 0:
            return np.zeros((0, len(tau)))
        return np.stack([self._row(table, g, m, tau) for g, m in zip(groups, mv)])

    def _check_tables(self, tables, groups, tau):
        for g, mv in self.keys_needed(groups):
            for t in tables:
                r = self._row(t, g, mv, np.asarray(tau, dtype=float))
                if not np.isfinite(r).all() or (r < 0).any():
                    raise ValueError(f'envelope gives a non-finite or negative bound for {g}')
        return self


class IsoTableEnvelope(_TableEnvelope):
    kind = 'iso_table'

    def __init__(self, tau_s, B_m, **kw):
        super().__init__(tau_s, **kw)
        self.table = {str(k): list(v) for k, v in B_m.items()}

    def check(self, groups, tau):
        return self._check_tables((self.table,), groups, tau)

    def describe(self):
        return {**super().describe(), 'tau_s_range': [float(self.tau_s[0]), float(self.tau_s[-1])],
                'n_tau': int(len(self.tau_s)), 'keys': sorted(self.table)}


class AnisoTableEnvelope(_TableEnvelope):
    kind = 'aniso'

    def __init__(self, tau_s, B_lon_m, B_lat_m, **kw):
        super().__init__(tau_s, **kw)
        self.lon = {str(k): list(v) for k, v in B_lon_m.items()}
        self.lat = {str(k): list(v) for k, v in B_lat_m.items()}

    def check(self, groups, tau):
        return self._check_tables((self.lon, self.lat), groups, tau)

    def describe(self):
        return {**super().describe(), 'tau_s_range': [float(self.tau_s[0]), float(self.tau_s[-1])],
                'n_tau': int(len(self.tau_s)), 'keys': sorted(self.lon)}


ENVELOPE_META_KEYS = ('q', 'n_pairs', 'notes', '_meta', 'protocol', 'calibration_clips', 'd_grid_s')


def envelope_from_dict(d, source='inline', sha256=None, outer=None):
    """Envelope from one of the accepted JSON forms (README.md, 'Envelope files'):

    * a framelease_v2 LeaseParams file (top-level sigma_m / vbar_mps / abar_mps2; the default q95 file);
    * {'kind': 'iso', 'sigma_m', 'vbar_mps', 'abar_mps2'}                         (Gate-2 E0)
    * {'kind': 'iso_table', 'tau_s', 'B_m', ['motion_bins', 'static_speed_mps']}
    * {'kind': 'aniso', 'tau_s', 'B_lon_m', 'B_lat_m', ['motion_bins', 'static_speed_mps']}   (Gate-2 E1 / E2)
    each optionally nested under 'envelope' (Gate-2 envelope files). Gate-2 LOCO fold files are offline-only.
    """
    if not isinstance(d, dict):
        raise ValueError('envelope spec must be a JSON object')
    if 'envelope' in d and isinstance(d['envelope'], dict):
        return envelope_from_dict(d['envelope'], source, sha256, outer=d)
    if 'folds' in d:
        raise ValueError('LOCO fold files hold one envelope per held-out clip (offline evaluation only); '
                         'use an envelope calibrated on all calibration clips (e.g. a Gate-2 *_ORIG file)')
    meta = {k: d[k] for k in ENVELOPE_META_KEYS if k in d}
    for k in ENVELOPE_META_KEYS:
        if outer and k in outer:
            meta.setdefault(k, outer[k])
    kind = d.get('kind')
    common = dict(source=source, sha256=sha256, meta=meta, motion_bins=bool(d.get('motion_bins') or False),
                  static_speed_mps=d.get('static_speed_mps'))
    if kind == 'iso' or (kind is None and {'sigma_m', 'vbar_mps', 'abar_mps2'} <= set(d)):
        return IsoQuadraticEnvelope(d['sigma_m'], d['vbar_mps'], d['abar_mps2'], **common)
    if kind == 'iso_table':
        return IsoTableEnvelope(d['tau_s'], d['B_m'], **common)
    if kind == 'aniso':
        return AnisoTableEnvelope(d['tau_s'], d['B_lon_m'], d['B_lat_m'], **common)
    raise ValueError(f'unrecognized envelope spec (kind={kind!r}, keys={sorted(d)[:12]})')


def load_envelope(path):
    path = Path(path)
    return envelope_from_dict(json.loads(path.read_text(encoding='utf-8')), str(path.resolve()), sha256_file(path))


# ============================================================================================ environment

@dataclass
class LeaseEnv:
    """Everything the runtime lease needs: constants, envelope, ego shape and the tau grid."""
    cfg: SuffixLeaseConfig
    envelope: Envelope
    ego: object
    lease_params_path: Optional[str] = None
    lease_params_sha256: Optional[str] = None
    tau: np.ndarray = field(default=None)

    def __post_init__(self):
        self.cfg.validate()
        if self.tau is None:
            self.tau = time_grid(self.cfg.t_pred_s, self.cfg.dt_s)
        self._ns = SimpleNamespace(dt_s=self.cfg.dt_s, horizon_s=self.cfg.t_pred_s, min_speed_mps=self.cfg.min_speed_mps)
        self.ego_radius = float(math.hypot(self.ego.half_length_m, self.ego.half_width_m))
        self.envelope.check(self.cfg.relevant_groups, self.tau)

    @property
    def static_speed_mps(self):
        return self.envelope.static_speed_mps

    def ego_corners(self, plan_xy):
        return L2.ego_corners_along_plan(plan_xy, self.ego, self._ns)[3]

    def describe(self):
        return {'schema': SCHEMA, 'lease': self.cfg.to_dict(), 'envelope': self.envelope.describe(),
                'ego': self.ego.to_dict() if hasattr(self.ego, 'to_dict') else repr(self.ego),
                'lease_params_path': self.lease_params_path, 'lease_params_sha256': self.lease_params_sha256,
                'n_tau': int(len(self.tau))}


def build_lease_env(lease_params_path=None, envelope_path=None, lease_overrides=None, envelope_spec=None):
    """LeaseEnv from the base v2 lease-parameter file (ego shape; its sigma/vbar/abar are the default isotropic
    envelope) and an optional envelope file or inline spec that replaces the default envelope."""
    if lease_params_path:
        base = json.loads(Path(lease_params_path).read_text(encoding='utf-8'))
        ego = L2.load_ego_shape(lease_params_path, default=L2.B2D_EGO)
    else:
        base = None
        ego = L2.B2D_EGO
    cfg = SuffixLeaseConfig.from_dict(lease_overrides or {})
    if envelope_spec is not None:
        env = envelope_from_dict(envelope_spec, 'inline')
    elif envelope_path:
        env = load_envelope(envelope_path)
    elif base is not None:
        env = IsoQuadraticEnvelope(base['sigma_m'], base['vbar_mps'], base['abar_mps2'],
                                   source=str(Path(lease_params_path).resolve()), sha256=sha256_file(lease_params_path),
                                   meta={'from': 'lease_params file (v2 isotropic envelope)',
                                         'quantile': (base.get('_meta') or {}).get('quantile')})
    else:
        raise ValueError('need lease_params_path or an envelope')
    return LeaseEnv(cfg, env, ego, str(Path(lease_params_path).resolve()) if lease_params_path else None,
                    sha256_file(lease_params_path) if lease_params_path else None)


# ============================================================================================ agents (per observation)

@dataclass
class AgentSet:
    """Relevant detections of one observation, propagated on the tau grid (computed once per job: the detections
    and the ego footprint at tau = 0 are the same for every refinement depth of the observation)."""
    status: str                         # ok | invalid_detection | perception_unavailable
    idx: np.ndarray                     # (N,) row in the detection arrays
    group: np.ndarray                   # (N,) object
    confident: np.ndarray               # (N,) bool
    moving: np.ndarray                  # (N,) bool
    centers_t: np.ndarray               # (N, M, 2) constant-velocity centres
    polys: np.ndarray                   # (N, M, 4, 2) boxes the distance is taken to (aniso: inflated)
    r_poly: np.ndarray                  # (N, M) circumradius of polys about centers_t
    kind: str = 'iso'                   # envelope kind
    B: Optional[np.ndarray] = None      # (N, M) isotropic bound at the grid points (iso, iso_table)
    quad: Optional[tuple] = None        # (sigma, vbar, abar) (N,) for the quadratic envelope
    margin0_m: Optional[float] = None   # nominal margin min_j dist(E(0), R_j(0)) - d_safe (no envelope)
    g0_m: Optional[float] = None        # conservative margin g(0) (with envelope); g(0) <= delta <=> H = 0
    invalid_index: Optional[int] = None

    def __len__(self):
        return int(len(self.idx))


def empty_agents(M, status='ok', invalid_index=None, kind='iso'):
    return AgentSet(status, np.zeros(0, dtype=int), np.zeros(0, dtype=object), np.zeros(0, dtype=bool),
                    np.zeros(0, dtype=bool), np.zeros((0, M, 2)), np.zeros((0, M, 4, 2)), np.zeros((0, M)), kind,
                    np.zeros((0, M)), None, None, None, invalid_index)


def margin_from_distance(kind, dist, B, d_safe):
    """Pointwise margin g from the polygon distance: dist(E, R (+) S) - d_safe for the envelope kind."""
    if kind == 'iso':
        return dist - d_safe - B                          # v2 time-resolved convention (exact crossing; see doc)
    if kind == 'iso_table':
        return np.maximum(dist - B, 0.0) - d_safe         # distance to the disc-inflated box
    return dist - d_safe                                  # aniso: polys are already inflated


def ego_box_at_capture(env):
    """Ego footprint at tau = 0 (LiDAR origin, forward heading): the same for every plan."""
    e = env.ego
    fy = float(e.forward_yaw_rad)
    return ego_footprint(np.zeros((1, 2)), np.array([fy]), e.half_length_m, e.half_width_m, e.center_offset_xy, fy)[0]


def prepare_agents(boxes, scores, labels, env: LeaseEnv, valid=True):
    """Relevant detections of one observation, propagated (and, for anisotropic envelopes, inflated) on the grid."""
    cfg, tau = env.cfg, env.tau
    M = len(tau)
    kind = env.envelope.kind
    if not valid:
        return empty_agents(M, 'perception_unavailable', kind=kind)
    boxes = np.asarray(boxes, dtype=float).reshape(-1, 7)
    scores = np.asarray(scores, dtype=float).reshape(-1)
    if len(scores) != len(boxes):
        raise ValueError('boxes and scores differ in length')
    if len(boxes) == 0:
        return empty_agents(M, kind=kind)
    groups = L2.resolve_groups(labels)
    if len(groups) != len(boxes):
        raise ValueError('boxes and labels differ in length')
    floor = cfg.low_score_floor if cfg.low_conf_mode == 'cap' else cfg.score_threshold
    relevant = np.isin(groups, list(cfg.relevant_groups)) & (np.nan_to_num(scores, nan=1.0) >= floor)
    finite = np.isfinite(boxes).all(1) & np.isfinite(scores)
    broken = relevant & ~finite
    if broken.any():
        return empty_agents(M, 'invalid_detection', int(np.flatnonzero(broken)[0]), kind=kind)
    idx = np.flatnonzero(relevant)
    if len(idx) == 0:
        return empty_agents(M, kind=kind)
    d = boxes[idx]
    g = groups[idx]
    hl, hw = 0.5 * np.abs(d[:, 2]), 0.5 * np.abs(d[:, 3])
    moving = np.hypot(d[:, 5], d[:, 6]) >= env.static_speed_mps
    N = len(idx)
    centers_t = d[:, None, 0:2] + tau[None, :, None] * d[:, None, 5:7]                 # (N, M, 2)
    box0 = box_corners(d[:, 0:2], d[:, 4], hl, hw)                                      # (N, 4, 2)
    B = quad = None
    envelope = env.envelope
    if kind in ('iso', 'iso_table'):
        # exactly framelease_v2.lease.lease_geometry's agent footprints R_j(tau) (bit-identical clearances)
        polys = box0[:, None, :, :] + (tau[None, :, None, None] * d[:, None, None, 5:7])
        r_poly = np.broadcast_to(np.hypot(hl, hw)[:, None], (N, M))
        if kind == 'iso':
            quad = envelope.params(g, moving)
            s, v, a = quad
            B = v[:, None] * tau[None, :] + 0.5 * a[:, None] * tau[None, :] ** 2 + s[:, None]
        else:
            B = envelope.rows(envelope.table, g, moving, tau)
    elif kind == 'aniso':
        ext_hl = hl[:, None] + envelope.rows(envelope.lon, g, moving, tau)
        ext_hw = hw[:, None] + envelope.rows(envelope.lat, g, moving, tau)
        polys = box_corners(centers_t, d[:, None, 4], ext_hl, ext_hw)
        r_poly = np.hypot(ext_hl, ext_hw)
    else:
        raise ValueError(f'unsupported envelope kind {kind!r}')
    E0 = ego_box_at_capture(env)
    margin0 = float(np.min(convex_distance(E0[None], box0))) - cfg.d_safe_m
    dist0 = convex_distance(E0[None], polys[:, 0])
    g0 = float(np.min(margin_from_distance(kind, dist0, None if B is None else B[:, 0], cfg.d_safe_m)))
    return AgentSet('ok', idx, g, scores[idx] >= cfg.score_threshold, moving, centers_t, polys, r_poly, kind, B,
                    quad, margin0, g0)


# ============================================================================================ lease

def quad_first_crossing(tau, clear, sigma, vbar, abar, delta, t_pred):
    """Per-agent first tau with clear(tau) - B(tau) <= delta, clear linear between grid points, B quadratic exact.

    framelease_v2.lease.agent_leases('time_resolved', reserve = delta, h_max = t_pred) with per-agent bounds (the
    function the offline Gate-2 study uses for E0); no crossing on the grid gives t_pred (its cap).
    """
    K = len(clear)
    if K == 0:
        return np.zeros(0)
    labels = np.array([f'a{i}' for i in range(K)], dtype=object)
    params = SimpleNamespace(sigma_m=dict(zip(labels, sigma)), vbar_mps=dict(zip(labels, vbar)),
                             abar_mps2=dict(zip(labels, abar)), h_max_s=float(t_pred), dt_s=float(tau[1] - tau[0]),
                             margin_mode='time_resolved')
    geom = L2.LeaseGeometry(tau, clear, np.arange(K), labels, np.ones(K, dtype=bool))
    return np.asarray(L2.agent_leases(geom, params, [float(delta)], 'time_resolved')[0], dtype=float)


def agent_crossings(tau, g, delta, t_pred, clear=None, quad=None):
    """Per-agent first crossing tau*_j of g_j <= delta on the grid prefix tau (+inf if none there).

    Table envelopes: g linear between grid points (framelease_v2.geometry.first_crossing_time). Quadratic isotropic
    envelope (clear and quad given): clearance linear, B exact (quad_first_crossing). g must be the grid values of
    the same margin (clear - B for the quadratic envelope)."""
    g = np.asarray(g, dtype=float)
    if len(g) == 0:
        return np.zeros(0)
    crosses = (g <= delta).any(axis=1)
    if clear is not None:
        ts = quad_first_crossing(tau, clear, *quad, delta, t_pred)
    else:
        ts = np.asarray(first_crossing_time(tau, g, delta), dtype=float).reshape(-1)
    return np.where(crosses, ts, np.inf)


def lease_closed_form(tau_star, t_c, h_bar):
    """H = clip(tau* - T_c, 0, H_bar); tau* = +inf (no crossing) gives H_bar; NaN gives 0."""
    ts = float(tau_star)
    if math.isnan(ts):
        return 0.0
    if not math.isfinite(ts):
        return float(h_bar)
    return float(min(max(ts - float(t_c), 0.0), float(h_bar)))


INVALID_REASONS = ('invalid_plan', 'invalid_detection', 'perception_unavailable')


@dataclass
class LeaseResult:
    lease_s: float
    tau_star_s: float
    reason: str
    info: dict
    # per-agent margin data of the agents that can bind, on the computed grid prefix (for the commit-time check)
    tau: Optional[np.ndarray] = None
    g: Optional[np.ndarray] = None          # (K, Mc) margins at grid points (exact wherever they can be <= delta)
    clear: Optional[np.ndarray] = None      # (K, Mc) clearance dist - d_safe (iso quadratic: B exact in between)
    quad: Optional[tuple] = None            # (sigma, vbar, abar) (K,) (iso quadratic only)
    t_pred_s: float = 3.0

    def as_validity(self, capture_s):
        out = {'deadline_s': float(capture_s) + float(self.lease_s), 'lease_s': float(self.lease_s),
               'source': 'suffix_lease', 'reason': self.reason,
               'tau_star_s': self.tau_star_s if math.isfinite(self.tau_star_s) else None}
        out.update(self.info)
        return out

    def margin(self, age_s, t_c):
        """M(Delta) of Eq. 1 at Delta = age_s, evaluated literally with the lease's own interpolants.

        The decision M > delta is exact for every window that starts at or before tau* (in particular every
        window of a commit with t_commit < D); the value is the minimum over the agents that can bind (agents
        skipped by the prefilter have g > delta everywhere) with bounding-circle placeholders, provably > delta, at
        grid points that cannot cross, so above delta it may differ from the minimum over all agents. Windows past
        the computed grid prefix (it always contains tau*) and invalid leases give -inf; no agent able to bind +inf.
        """
        a, b = float(age_s), float(age_s) + float(t_c)
        if self.g is None or self.reason in INVALID_REASONS or math.isnan(a) or math.isnan(b):
            return -math.inf
        if len(self.g) == 0:
            return math.inf if b <= self.t_pred_s + 1e-9 else -math.inf
        tau = self.tau
        if b > tau[-1] + 1e-9:
            return -math.inf
        a = max(a, 0.0)
        b = min(b, float(tau[-1]))
        inner = (tau > a) & (tau < b)
        ends = np.array([a, b])
        if self.clear is not None:
            s, v, k = self.quad
            c_ends = np.stack([np.interp(ends, tau, row) for row in self.clear])            # (K, 2)
            vals = c_ends - (v[:, None] * ends[None, :] + 0.5 * k[:, None] * ends[None, :] ** 2 + s[:, None])
        else:
            vals = np.stack([np.interp(ends, tau, row) for row in self.g])
        m = float(vals.min())
        if inner.any():
            m = min(m, float(self.g[:, inner].min()))
        return m


CHUNK_POINTS = 10   # early termination granularity (0.5 s of the 0.05 s grid)


def suffix_lease(plan_xy, agents: AgentSet, env: LeaseEnv, prefilter=None, full=False):
    """Eq. 1-3 for one candidate plan against the prepared agents of its observation.

    prefilter: exact distances only at grid points whose bounding-circle lower bound on g_j is <= delta, plus their
               left neighbours (placeholders elsewhere are provably > delta); agents with no such point are skipped.
    full:      evaluate the whole grid; otherwise stop after the first 0.5 s chunk that contains a crossing
               (tau* cannot be later). Both are exact: the lease is bit-identical in all four modes (tested).
    """
    cfg, tau = env.cfg, env.tau
    M = len(tau)
    h_bar, delta, t_pred, d_safe = cfg.h_bar_s, cfg.delta_m, cfg.t_pred_s, cfg.d_safe_m
    prefilter = cfg.prefilter if prefilter is None else bool(prefilter)
    info = {'n_relevant': len(agents), 'n_confident': int(agents.confident.sum()),
            'n_low_confidence': int((~agents.confident).sum()), 'n_computed': 0, 'n_exact_points': 0,
            'grid_points': 0, 'margin0_m': agents.margin0_m, 'g0_m': agents.g0_m, 'min_g_m': None,
            'binding_index': None, 'binding_group': None, 'binding_moving': None, 'envelope': env.envelope.kind}
    plan = np.asarray(plan_xy, dtype=float)
    if plan.shape != (6, 2) or not np.isfinite(plan).all():
        return LeaseResult(0.0, 0.0, 'invalid_plan', info, t_pred_s=t_pred)
    try:
        E = env.ego_corners(plan)
    except ValueError:
        return LeaseResult(0.0, 0.0, 'invalid_plan', info, t_pred_s=t_pred)
    if agents.status != 'ok':
        info['invalid_index'] = agents.invalid_index
        if agents.status not in INVALID_REASONS:
            info['error'] = agents.status
        reason = agents.status if agents.status in INVALID_REASONS else 'perception_unavailable'
        return LeaseResult(0.0, 0.0, reason, info, t_pred_s=t_pred)
    N = len(agents)
    if N == 0:
        return LeaseResult(h_bar, math.inf, 'no_relevant_agents', info, tau, np.zeros((0, M)), t_pred_s=t_pred)
    kind = agents.kind
    if prefilter:
        ce = E.mean(axis=1)                                                              # (M, 2) ego box centres
        dlb = np.maximum(np.linalg.norm(agents.centers_t - ce[None], axis=-1) - env.ego_radius - agents.r_poly, 0.0)
        need = margin_from_distance(kind, dlb, agents.B, d_safe) <= delta + 1e-9        # (N, M)
        kidx = np.flatnonzero(need.any(axis=1))
    else:
        kidx = np.arange(N)
    info['n_computed'] = int(kidx.size)
    if kidx.size == 0:
        return LeaseResult(h_bar, math.inf, 'horizon_cap', info, tau, np.zeros((0, M)), t_pred_s=t_pred)
    K = int(kidx.size)
    polys = agents.polys[kidx]
    Bk = None if agents.B is None else agents.B[kidx]
    if prefilter:
        nk = need[kidx]
        exact = nk.copy()
        exact[:, :-1] |= nk[:, 1:]                       # the left neighbour of every point that may cross
        dist = dlb[kidx].copy()                          # placeholders (lower bounds) where not exact
    else:
        exact = np.ones((K, M), dtype=bool)
        dist = np.empty((K, M))
    m1 = M
    for m0 in range(0, M, M if full else CHUNK_POINTS):
        m1 = min(m0 + (M if full else CHUNK_POINTS), M)
        ki, mi = np.nonzero(exact[:, m0:m1])
        if ki.size:
            mi = mi + m0
            dist[ki, mi] = convex_distance(E[mi], polys[ki, mi])
            info['n_exact_points'] += int(ki.size)
        if not full and m1 < M:
            gc = margin_from_distance(kind, dist[:, m0:m1], None if Bk is None else Bk[:, m0:m1], d_safe)
            if (gc <= delta).any():
                break
    tau_c = tau[:m1]
    dist = dist[:, :m1]
    g = margin_from_distance(kind, dist, None if Bk is None else Bk[:, :m1], d_safe)
    g = np.where(np.isnan(g), -np.inf, g)
    clear = quad = None
    if kind == 'iso':
        clear = dist - d_safe
        quad = tuple(x[kidx] for x in agents.quad)
    ts_j = agent_crossings(tau_c, g, delta, t_pred, clear, quad)
    j = int(np.argmin(ts_j))
    ts = float(ts_j[j])
    H = lease_closed_form(ts, cfg.t_c_s, h_bar)
    info['grid_points'] = int(m1)
    exact_g = np.where(exact[:, :m1], g, np.inf)
    info['min_g_m'] = float(exact_g.min()) if np.isfinite(exact_g.min()) else None
    if math.isfinite(ts):
        k = int(kidx[j])
        info.update(binding_index=int(agents.idx[k]), binding_group=str(agents.group[k]),
                    binding_moving=bool(agents.moving[k]))
        reason = 'immediate_failure' if H <= 0.0 else ('horizon_cap' if H >= h_bar else 'first_failure')
    else:
        reason = 'horizon_cap'
    return LeaseResult(H, ts, reason, info, tau_c, g, clear, quad, t_pred)


def compute_suffix_lease(plan_xy, boxes, scores, labels, env: LeaseEnv, valid=True, prefilter=None):
    """Convenience: prepare the agents and compute the lease in one call (agents are normally cached per job)."""
    return suffix_lease(plan_xy, prepare_agents(boxes, scores, labels, env, valid), env, prefilter)


__all__ = ['SCHEMA', 'SuffixLeaseConfig', 'Envelope', 'IsoQuadraticEnvelope', 'IsoTableEnvelope', 'AnisoTableEnvelope',
           'envelope_from_dict', 'load_envelope', 'LeaseEnv', 'build_lease_env', 'AgentSet', 'empty_agents',
           'margin_from_distance', 'ego_box_at_capture', 'prepare_agents', 'quad_first_crossing', 'agent_crossings',
           'lease_closed_form',
           'LeaseResult', 'suffix_lease', 'compute_suffix_lease', 'sha256_file', 'INVALID_REASONS', 'CHUNK_POINTS']
