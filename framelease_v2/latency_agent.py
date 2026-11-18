"""Latency-aware UniDriveVLA agent for the official Bench2Drive evaluator (virtual-time, measured latency).

CARLA runs synchronously at the evaluator's 20 Hz tick and is paused while the model computes. The agent keeps a
simulated single-GPU timeline in simulation seconds:

* A job processes one observation O_k (captured at t_k). When a policy starts it at simulated time s, the
  non-preemptible prefix (vision, language and perception) runs for real and its CUDA-event time c_P is measured.
* Flow steps are computed lazily, one at a time, exactly when the simulated timeline reaches their boundary, so
  a policy can stop, continue or preempt with only the information available at that simulated time.
* The candidate of depth d is released at  s + o_0 + kappa * (c_P + sum_{j<=d} c_j) + sum_{j<d} o_j,  where
  c_j are measured CUDA-event step times, kappa is the GPU contention scale and o_j the measured CPU time of the
  scheduler at each boundary (decision, lease, commit check; scaled by overhead_scale).
* Until a candidate is committed the vehicle tracks the incumbent plan: it is re-anchored from its capture-time
  LiDAR frame into the current LiDAR frame with the agent's own GNSS/IMU pose estimate (never simulator truth)
  and sampled at the elapsed time, then passed to the unchanged official PID controller.
* Versioned commit: a candidate replaces the incumbent only if its observation is newer (or the same observation
  at greater depth), it is not past its deadline at the commit instant, and it passes a finite / kinematic check.
  Otherwise it is rejected and logged. An incumbent strictly expires at its deadline; with nothing valid left a
  logged safety fallback (full brake) is applied.

Modes: one of policies.POLICY_NAMES, or 'oracle_sync' (the official zero-latency agent: full model every tick,
official temporal bank rotation and PID, BF16 autocast compatibility path) as an upper bound.

The runtime core (LatencyRuntime and helpers) depends on numpy only, so it is unit-tested with a fake model and
a fake clock (tests/test_runtime.py). torch / carla / the official agent are imported only inside the evaluator.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import time
import traceback
from collections import Counter, deque
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Callable, List, Optional

import numpy as np

from framelease_v2.policies import POLICY_NAMES, RUNTIME_MODES, default_policy_env, make_policy

SCHEMA_VERSION = 1
FRAME_DT_S = 0.05                 # Bench2Drive evaluator tick (20 Hz)
PLAN_DT_S = 0.5                   # UniDriveVLA waypoint spacing
PLAN_POINTS = 6                   # waypoints at 0.5 ... 3.0 s after capture (LiDAR origin at t = 0)
PLAN_KNOT_TIMES_S = np.arange(PLAN_POINTS + 1) * PLAN_DT_S
MAX_FLOW_DEPTH = 10
EPS_S = 1e-6
ENV_RUNTIME_CONFIG = 'FRAMELEASE_V2_RUNTIME_CONFIG'

# LIDAR2EGO of the official Bench2Drive UniDriveVLA agent (team_code/unidrivevla_b2d_agent.py).
OFFICIAL_LIDAR2EGO = np.array([[0., 1., 0., -0.39],
                               [-1., 0., 0., 0.],
                               [0., 0., 1., 1.84],
                               [0., 0., 0., 1.]])


# =============================================================================================== geometry

def planar_lidar2global(x, y, yaw, lidar2ego=OFFICIAL_LIDAR2EGO):
    """lidar2global of the official agent for an ego pose (x, y, yaw) in the right-handed model world."""
    c, s = math.cos(yaw), math.sin(yaw)
    ego2world = np.eye(4)
    ego2world[:2, :2] = [[c, -s], [s, c]]
    ego2world[:2, 3] = [x, y]
    return ego2world @ np.asarray(lidar2ego, dtype=float)


def plan_points_at(plan_xy, times_s, extrapolation='constant_velocity'):
    """Positions of a plan (capture LiDAR frame, origin at t = 0) at the given times after capture.

    Piecewise-linear between the knots t = 0, 0.5, ..., 3.0. Beyond 3.0 s either continue with the velocity of
    the last segment ('constant_velocity') or hold the last waypoint ('hold').
    """
    knots = np.vstack([np.zeros((1, 2)), np.asarray(plan_xy, dtype=float).reshape(PLAN_POINTS, 2)])
    t = np.asarray(times_s, dtype=float).reshape(-1)
    out = np.stack([np.interp(t, PLAN_KNOT_TIMES_S, knots[:, 0]), np.interp(t, PLAN_KNOT_TIMES_S, knots[:, 1])], -1)
    beyond = t > PLAN_KNOT_TIMES_S[-1]
    if extrapolation == 'constant_velocity':
        if beyond.any():
            vel = (knots[-1] - knots[-2]) / PLAN_DT_S
            out[beyond] = knots[-1] + (t[beyond] - PLAN_KNOT_TIMES_S[-1])[:, None] * vel
    elif extrapolation != 'hold':
        raise ValueError(f'unknown extrapolation {extrapolation!r}')
    return out


def transform_points(points_xy, src_lidar2global, dst_lidar2global):
    """Planar points from one LiDAR frame into another through the right-handed world."""
    T = np.linalg.inv(np.asarray(dst_lidar2global, dtype=float)) @ np.asarray(src_lidar2global, dtype=float)
    return np.asarray(points_xy, dtype=float) @ T[:2, :2].T + T[:2, 3]


def reanchor_plan(plan_xy, capture_lidar2global, now_lidar2global, elapsed_s, extrapolation='constant_velocity'):
    """PID reference at elapsed time e: plan positions at e + 0.5k (k = 1..6) in the current LiDAR frame.

    With e = 0 and an unchanged pose this is the plan itself (the official zero-latency input).
    """
    times = float(elapsed_s) + PLAN_DT_S * np.arange(1, PLAN_POINTS + 1)
    return transform_points(plan_points_at(plan_xy, times, extrapolation), capture_lidar2global, now_lidar2global)


def kinematic_check(plan_xy, max_speed_mps=40.0, max_accel_mps2=20.0):
    """Finite / kinematic screen of a 6 x 2 plan (not a safety or road check)."""
    p = np.asarray(plan_xy, dtype=float)
    if p.shape != (PLAN_POINTS, 2) or not np.isfinite(p).all():
        return False, 'shape_or_nonfinite', {}
    seg = np.diff(np.vstack([np.zeros((1, 2)), p]), axis=0)
    speed = np.linalg.norm(seg, axis=1) / PLAN_DT_S
    accel = np.diff(speed) / PLAN_DT_S
    stats = {'max_speed_mps': float(speed.max()), 'max_abs_accel_mps2': float(np.abs(accel).max())}
    if stats['max_speed_mps'] > max_speed_mps:
        return False, 'speed_limit', stats
    if stats['max_abs_accel_mps2'] > max_accel_mps2:
        return False, 'accel_limit', stats
    return True, 'ok', stats


# =============================================================================================== records

@dataclass
class Observation:
    """One control tick's sensor frame, as the agent itself perceives it."""
    obs_id: int                       # agent step (tick index) of capture
    capture_s: float                  # simulation time of capture
    lidar2global: np.ndarray          # 4x4 from the agent's GNSS / compass (official formula)
    speed_mps: float                  # speedometer
    yaw_rad: float                    # heading in the right-handed model world (compass)
    command: int                      # route command of the official route planner
    payload: Any = None               # opaque model input (dropped once a prefix consumed it)


@dataclass
class DetectionSet:
    """Model detections of one observation (top-K by score, capture LiDAR frame)."""
    boxes: np.ndarray                 # [N, 7] decode_boxes(): cx, cy, length, width, yaw, vx, vy
    scores: np.ndarray                # [N]
    labels: np.ndarray                # [N] UniDriveVLA label index
    raw: Optional[np.ndarray] = None  # [N, 10] boxes_3d
    valid: bool = True                # False if the perception output was missing
    obs_id: int = -1
    capture_s: float = math.nan
    lidar2global: Optional[np.ndarray] = None
    available_s: float = math.nan     # simulated time at which the prefix that produced them finished

    @classmethod
    def empty(cls, obs=None, valid=True):
        return cls(np.zeros((0, 7)), np.zeros(0), np.zeros(0, dtype=int), np.zeros((0, 10)), valid,
                   obs.obs_id if obs else -1, obs.capture_s if obs else math.nan,
                   obs.lidar2global if obs else None)


@dataclass
class Candidate:
    job_id: int
    obs: Observation
    depth: int
    plan_xy: np.ndarray
    release_s: float
    dets: Optional[DetectionSet]
    deadline_s: float = math.inf
    validity: dict = field(default_factory=dict)
    commit_s: Optional[float] = None

    @property
    def obs_id(self):
        return self.obs.obs_id

    @property
    def capture_s(self):
        return self.obs.capture_s

    def brief(self):
        return {'job_id': self.job_id, 'obs_id': self.obs_id, 'capture_s': self.capture_s, 'depth': self.depth,
                'release_s': self.release_s, 'commit_s': self.commit_s, 'deadline_s': self.deadline_s,
                'lease_s': self.validity.get('lease_s'), 'validity_source': self.validity.get('source')}


@dataclass
class PrefixResult:
    state: Any
    cost_s: float                      # CUDA-event elapsed time of the prefix (seconds)
    wall_s: float
    dets: DetectionSet
    preprocess_wall_s: float = 0.0     # CPU input preparation + host-to-device copy (not in the timeline by default)
    info: dict = field(default_factory=dict)


@dataclass
class StepResult:
    plan_xy: np.ndarray                # (6, 2) clean trajectory after this step; depth 10 = official final planning
    cost_s: float                      # CUDA-event elapsed time of the step (seconds)
    wall_s: float
    info: dict = field(default_factory=dict)


@dataclass
class Job:
    job_id: int
    obs: Observation
    start_s: float
    start_overhead_s: float = 0.0
    state: Any = None
    dets: Optional[DetectionSet] = None
    phase: str = 'prefix'              # prefix | step | done
    depth: int = 0
    busy_until_s: float = math.nan     # simulated end of the running GPU operation
    target_depth: int = MAX_FLOW_DEPTH
    pending_plan: Optional[np.ndarray] = None
    prefix: dict = field(default_factory=dict)
    prefix_end_s: float = math.nan
    steps: list = field(default_factory=list)
    last_deadline_s: float = -math.inf
    last_validity: dict = field(default_factory=dict)
    policy_state: dict = field(default_factory=dict)
    committed_depths: list = field(default_factory=list)
    stop_reason: Optional[str] = None
    end_s: float = math.nan

    def record(self):
        d = self.dets
        return {'job_id': self.job_id, 'obs_id': self.obs.obs_id, 'capture_s': self.obs.capture_s,
                'start_s': self.start_s, 'start_age_s': self.start_s - self.obs.capture_s,
                'start_overhead_s': self.start_overhead_s, 'prefix': self.prefix, 'prefix_end_s': self.prefix_end_s,
                'n_dets': int(len(d.scores)) if d is not None else 0, 'dets_valid': bool(d.valid) if d else False,
                'target_depth': self.target_depth, 'final_depth': self.depth, 'steps': self.steps,
                'committed_depths': self.committed_depths, 'stop_reason': self.stop_reason, 'end_s': self.end_s,
                'last_validity': self.last_validity, 'policy_state': self.policy_state}


# =============================================================================================== configuration

@dataclass
class RuntimeConfig:
    kappa: float = 1.0                 # GPU contention scale on measured CUDA times
    overhead_scale: float = 1.0        # scale on measured scheduler CPU time (0 removes it)
    cost_mode: str = 'measured'        # 'measured' or 'fixed' (fixed_prefix_s / fixed_step_s; measured still logged)
    fixed_prefix_s: float = 0.92
    fixed_step_s: float = 0.015
    count_preprocess: bool = False     # add measured CPU input preparation to the prefix release time
    min_depth: int = 1
    max_depth: int = MAX_FLOW_DEPTH
    max_age_s: float = 2.0             # global maximum observation age H_max (validity of non-lease policies)
    guard_s: float = 0.05              # G of the reservation rule (switching overhead, runtime fluctuation)
    versioned_commit: bool = True      # A3 ablation switch
    max_speed_mps: float = 40.0
    max_accel_mps2: float = 20.0
    extrapolation: str = 'constant_velocity'
    fallback_brake: float = 1.0
    fallback_steer: str = 'hold'       # 'hold' the last applied steer or 'zero'
    prior_prefix_s: float = 1.0        # latency profile before measurements exist
    prior_step_s: float = 0.02
    prior_overhead_s: float = 0.002
    profile_quantile: float = 0.95
    profile_window: int = 64
    profile_min_samples: int = 3
    obs_buffer: int = 4

    def validate(self):
        if not self.kappa >= 0 or not self.overhead_scale >= 0:
            raise ValueError('kappa and overhead_scale must be >= 0')
        if self.cost_mode not in ('measured', 'fixed'):
            raise ValueError('cost_mode must be measured or fixed')
        if not 1 <= self.min_depth <= self.max_depth <= MAX_FLOW_DEPTH:
            raise ValueError('need 1 <= min_depth <= max_depth <= 10')
        if not self.max_age_s > 0 or not self.guard_s >= 0:
            raise ValueError('max_age_s > 0 and guard_s >= 0 required')
        if self.extrapolation not in ('constant_velocity', 'hold') or self.fallback_steer not in ('hold', 'zero'):
            raise ValueError('bad extrapolation / fallback_steer')
        if not 0 < self.profile_quantile <= 1 or self.profile_window < 1 or self.obs_buffer < 2:
            raise ValueError('bad latency profile / buffer settings')
        return self

    @classmethod
    def from_dict(cls, d):
        names = {f.name for f in fields(cls)}
        unknown = sorted(set(d or {}) - names)
        if unknown:
            raise ValueError(f'unknown runtime config keys {unknown}')
        return cls(**(d or {})).validate()

    def to_dict(self):
        return {f.name: getattr(self, f.name) for f in fields(self)}


class LatencyProfile:
    """Measured latency profile: timeline costs and conservative bounds for the reservation rule."""

    def __init__(self, config: RuntimeConfig):
        self.cfg = config
        w = config.profile_window
        self.prefix = deque(maxlen=w)
        self.steps = {d: deque(maxlen=w) for d in range(1, MAX_FLOW_DEPTH + 1)}
        self.steps_all = deque(maxlen=4 * w)
        self.overhead = deque(maxlen=4 * w)
        self.preprocess = deque(maxlen=w)

    def _q(self, values, prior):
        if len(values) < self.cfg.profile_min_samples:
            return float(prior)
        return float(np.quantile(np.asarray(values, dtype=float), self.cfg.profile_quantile))

    def timeline_cost(self, kind, depth, measured_s):
        if self.cfg.cost_mode == 'fixed':
            base = self.cfg.fixed_prefix_s if kind == 'prefix' else self.cfg.fixed_step_s
        else:
            base = measured_s
        return self.cfg.kappa * float(base)

    def add_prefix(self, cost_s):
        self.prefix.append(float(cost_s))

    def add_step(self, depth, cost_s):
        self.steps[int(depth)].append(float(cost_s))
        self.steps_all.append(float(cost_s))

    def add_overhead(self, s):
        self.overhead.append(float(s))

    def add_preprocess(self, s):
        self.preprocess.append(float(s))

    @property
    def preprocess_bound_s(self):
        return self._q(self.preprocess, 0.0) if self.cfg.count_preprocess else 0.0

    @property
    def prefix_bound_s(self):
        if self.cfg.cost_mode == 'fixed':
            return self.cfg.kappa * self.cfg.fixed_prefix_s
        return self.cfg.kappa * self._q(self.prefix, self.cfg.prior_prefix_s)

    def step_bound_s(self, depth):
        if self.cfg.cost_mode == 'fixed':
            return self.cfg.kappa * self.cfg.fixed_step_s
        values = self.steps.get(int(depth), ())
        if len(values) < self.cfg.profile_min_samples:
            return self.cfg.kappa * self._q(self.steps_all, self.cfg.prior_step_s)
        return self.cfg.kappa * self._q(values, self.cfg.prior_step_s)

    @property
    def overhead_bound_s(self):
        return self._q(self.overhead, self.cfg.prior_overhead_s * self.cfg.overhead_scale)

    @property
    def refresh_bound_s(self):
        """L_refresh_bound: a fresh observation's prefix + first step + the scheduler time around them."""
        return self.preprocess_bound_s + self.prefix_bound_s + self.step_bound_s(1) + 2.0 * self.overhead_bound_s

    def next_step_bound_s(self, depth):
        return self.step_bound_s(depth) + self.overhead_bound_s

    def snapshot(self):
        return {'prefix_bound_s': self.prefix_bound_s, 'step1_bound_s': self.step_bound_s(1),
                'preprocess_bound_s': self.preprocess_bound_s,
                'overhead_bound_s': self.overhead_bound_s, 'refresh_bound_s': self.refresh_bound_s,
                'n_prefix': len(self.prefix), 'n_steps': len(self.steps_all)}


@dataclass
class PolicyContext:
    now_s: float
    newest_obs: Optional[Observation]
    incumbent: Optional[Candidate]
    job: Optional[Job]
    last_job: Optional[Job]
    idle_since_s: float
    profile: LatencyProfile
    config: RuntimeConfig
    latest_dets: Optional[DetectionSet]
    prev_dets: Optional[DetectionSet]
    episode_start_s: float


# =============================================================================================== commit

def versioned_commit_check(cand: Candidate, latest: Optional[Candidate], commit_s: float, config: RuntimeConfig):
    """(accept, reason, details). Order: validity, version, deadline (all reasons are logged)."""
    ok, why, stats = kinematic_check(cand.plan_xy, config.max_speed_mps, config.max_accel_mps2)
    details = {'kinematic': stats, 'commit_s': commit_s, 'deadline_s': cand.deadline_s}
    if not ok:
        return False, 'invalid:' + why, details
    if latest is not None:
        if cand.obs_id < latest.obs_id:
            return False, 'stale_version:older_observation', details
        if cand.obs_id == latest.obs_id and cand.depth <= latest.depth:
            return False, 'stale_version:not_deeper', details
    if math.isnan(cand.deadline_s) or not commit_s < cand.deadline_s:
        return False, 'expired_before_commit', details
    return True, 'accepted', details


# =============================================================================================== logging

def jsonable(x):
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, np.ndarray):
        return jsonable(x.tolist())
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        v = float(x)
        return v if math.isfinite(v) else ('nan' if math.isnan(v) else ('inf' if v > 0 else '-inf'))
    if x is None or isinstance(x, (str, int)):
        return x
    return repr(x)


class MemoryLogger:
    """Collects rows in memory (tests) with the same interface as JsonlLogger."""

    def __init__(self):
        self.rows = {'ticks': [], 'jobs': [], 'events': []}

    def write(self, stream, row):
        self.rows.setdefault(stream, []).append(jsonable(row))

    def event(self, kind, sim_s, **data):
        self.write('events', {'kind': kind, 'sim_s': sim_s, **data})

    def close(self):
        pass


class JsonlLogger(MemoryLogger):
    """Append-only JSONL streams ticks.jsonl / jobs.jsonl / events.jsonl in one run directory."""

    def __init__(self, directory):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._files = {}

    def write(self, stream, row):
        f = self._files.get(stream)
        if f is None:
            f = self._files[stream] = (self.dir / f'{stream}.jsonl').open('a', encoding='utf-8', buffering=1)
        f.write(json.dumps(jsonable(row), sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n')

    def close(self):
        for f in self._files.values():
            f.close()
        self._files = {}


def _quantiles(values, qs=(0.5, 0.95, 0.99)):
    if not values:
        return {f'p{int(q * 100)}': None for q in qs} | {'max': None, 'mean': None, 'n': 0}
    a = np.asarray(values, dtype=float)
    out = {f'p{int(q * 100)}': float(np.quantile(a, q)) for q in qs}
    out.update(max=float(a.max()), mean=float(a.mean()), n=int(a.size))
    return out


# =============================================================================================== runtime

class LatencyRuntime:
    """Simulated single-GPU timeline with lazy flow steps, versioned commit and strict expiry.

    backend.prefix(obs) -> PrefixResult, backend.step(state, depth) -> StepResult, backend.release(state)
    are executed for real at the moment the simulated timeline needs them.
    """
    MAX_EVENTS_PER_TICK = 10000

    def __init__(self, backend, policy, config: RuntimeConfig, logger=None, timer: Callable[[], float] = time.perf_counter):
        self.backend = backend
        self.policy = policy
        self.config = config.validate()
        self.logger = logger if logger is not None else MemoryLogger()
        self.timer = timer
        self.profile = LatencyProfile(self.config)
        self._obs = deque(maxlen=self.config.obs_buffer)
        self._commits: List[Candidate] = []
        self.job: Optional[Job] = None
        self.last_job: Optional[Job] = None
        self.gpu_free_s = math.nan
        self._idle_query_s = -math.inf
        self._declined_s = -math.inf
        self._last_job_obs_id: Optional[int] = None
        self.latest_dets: Optional[DetectionSet] = None
        self.prev_dets: Optional[DetectionSet] = None
        self.episode_start_s = math.nan
        self.now_s = -math.inf
        self._job_counter = 0
        self.stats = {'ticks': 0, 'track_ticks': 0, 'fallback': Counter(), 'ages': [], 'jobs': 0,
                      'stop_reasons': Counter(), 'commits': 0, 'rejects': Counter(), 'withheld': 0,
                      'committed_depths': Counter(), 'final_depths': Counter(), 'prefix_costs': [],
                      'step_costs': [], 'overheads': [], 'start_overheads': [], 'lease_s': [], 'lease_wall_s': [],
                      'gpu_busy_s': 0.0, 'busy_intervals': [], 'unversioned_overrides': Counter(), 'fallback_episodes': 0,
                      'validity_reasons': Counter(),
                      'first_tick_s': None, 'last_tick_s': None, 'preprocess_wall_s': []}
        self._in_fallback = False

    # ------------------------------------------------------------------ observations and time
    def add_observation(self, obs: Observation):
        if self._obs and obs.capture_s < self._obs[-1].capture_s - EPS_S:
            raise ValueError('observations must arrive in capture order')
        if self._obs and obs.obs_id <= self._obs[-1].obs_id:
            raise ValueError('observation ids must increase')
        evicted = self._obs[0] if len(self._obs) == self._obs.maxlen else None
        self._obs.append(obs)
        if evicted is not None and evicted is not getattr(self.job, 'obs', None):
            evicted.payload = None
        if math.isnan(self.episode_start_s):
            self.episode_start_s = obs.capture_s
            self.gpu_free_s = obs.capture_s

    def _newest_obs_at(self, t):
        for obs in reversed(self._obs):
            if obs.capture_s <= t + EPS_S:
                return obs
        return None

    def _first_obs_after(self, obs_id, t):
        for obs in self._obs:
            if (obs_id is None or obs.obs_id > obs_id) and obs.capture_s <= t + EPS_S:
                return obs
        return None

    def latest_committed(self):
        return self._commits[-1] if self._commits else None

    def incumbent_at(self, t):
        for cand in reversed(self._commits):
            if cand.commit_s <= t + EPS_S:
                return cand
        return None

    def _ctx(self, t, job=None):
        return PolicyContext(now_s=t, newest_obs=self._newest_obs_at(t), incumbent=self.latest_committed(),
                             job=job, last_job=self.last_job, idle_since_s=self.gpu_free_s, profile=self.profile,
                             config=self.config, latest_dets=self.latest_dets, prev_dets=self.prev_dets,
                             episode_start_s=self.episode_start_s)

    def _overhead(self, t0):
        return max(0.0, float(self.timer() - t0)) * self.config.overhead_scale

    # ------------------------------------------------------------------ event loop
    def advance(self, now_s):
        """Process every simulated GPU / scheduler event with time <= now_s, in time order."""
        if now_s < self.now_s - EPS_S:
            raise ValueError('simulation time went backwards')
        self.now_s = now_s
        for _ in range(self.MAX_EVENTS_PER_TICK):
            if self.job is not None:
                if self.job.busy_until_s > now_s + EPS_S:
                    return
                self._complete_op(self.job)
            elif not self._try_start(now_s):
                return
        raise RuntimeError('scheduler did not converge within one tick')

    def _try_start(self, now):
        g = self.gpu_free_s
        queries = []
        if self._idle_query_s < g - EPS_S:
            queries.append(g)
        if now > max(g, self._idle_query_s) + EPS_S:
            queries.append(now)
        for q in queries:
            t0 = self.timer()
            ctx = self._ctx(q)
            start = self.policy.idle_start_time(ctx)
            self._idle_query_s = q
            if start is not None:
                s = max(float(start), g, self._declined_s)
                if s <= now + EPS_S:
                    obs = self._newest_obs_at(s)
                    if obs is None or (self._last_job_obs_id is not None and obs.obs_id <= self._last_job_obs_id):
                        nxt = self._first_obs_after(self._last_job_obs_id, now)
                        if nxt is None:
                            self._declined_s = q
                            return False  # latest-frame rule: wait for a new frame
                        s = max(s, nxt.capture_s)
                        obs = self._newest_obs_at(s)
                    self._start_job(obs, s, t0)
                    return True
            self._declined_s = q
        return False

    def _start_job(self, obs, s, t0):
        self._job_counter += 1
        job = Job(job_id=self._job_counter, obs=obs, start_s=s)
        self.policy.on_job_start(job, self._ctx(s, job))
        overhead = self._overhead(t0)
        pre = self.backend.prefix(obs)
        cost = self.profile.timeline_cost('prefix', 0, pre.cost_s)
        self.profile.add_prefix(pre.cost_s)
        self.profile.add_preprocess(pre.preprocess_wall_s)
        extra = float(pre.preprocess_wall_s) if self.config.count_preprocess else 0.0
        job.start_overhead_s = overhead
        job.state = pre.state
        job.dets = pre.dets if pre.dets is not None else DetectionSet.empty(obs, valid=False)
        job.busy_until_s = s + overhead + extra + cost
        self.stats['busy_intervals'].append((job.busy_until_s - cost, job.busy_until_s))
        job.prefix = {'cost_s': pre.cost_s, 'timeline_cost_s': cost, 'wall_s': pre.wall_s,
                      'preprocess_wall_s': pre.preprocess_wall_s, 'counted_preprocess_s': extra,
                      'launch_s': s + overhead, **pre.info}
        self.job = job
        self._last_job_obs_id = obs.obs_id
        self.stats['gpu_busy_s'] += cost
        self.stats['prefix_costs'].append(pre.cost_s)
        self.stats['start_overheads'].append(overhead)
        self.stats['preprocess_wall_s'].append(pre.preprocess_wall_s)
        self.logger.event('job_start', s, job_id=job.job_id, obs_id=obs.obs_id, capture_s=obs.capture_s,
                          age_at_start_s=s - obs.capture_s, overhead_s=overhead, prefix_cost_s=pre.cost_s,
                          prefix_timeline_s=cost, prefix_end_s=job.busy_until_s, target_depth=job.target_depth,
                          profile=self.profile.snapshot())

    def _complete_op(self, job):
        """A GPU operation of `job` ended at b: release / commit, then decide the next operation at b + o."""
        b = job.busy_until_s
        t0 = self.timer()
        pending_logs = []  # written after the overhead is measured: log I/O is not scheduler time
        if job.phase == 'prefix':
            job.prefix_end_s = b
            job.dets.available_s = b
            self.prev_dets, self.latest_dets = self.latest_dets, job.dets
            self.policy.after_prefix(job, self._ctx(b, job))
            pending_logs.append(('prefix_done', b, {'job_id': job.job_id, 'obs_id': job.obs.obs_id,
                                                    'n_dets': int(len(job.dets.scores)),
                                                    'dets_valid': bool(job.dets.valid),
                                                    'target_depth': job.target_depth,
                                                    'policy_state': dict(job.policy_state)}))
        else:
            rec = job.steps[-1]
            rec['release_s'] = b
            cand = Candidate(job_id=job.job_id, obs=job.obs, depth=job.depth, plan_xy=job.pending_plan,
                             release_s=b, dets=job.dets)
            if self.policy.offers(job, job.depth):
                validity = dict(self.policy.validity(cand, self._ctx(b, job)))
                cand.deadline_s = float(validity['deadline_s'])
                cand.validity = validity
                job.last_deadline_s = cand.deadline_s
                job.last_validity = validity
                rec['validity'] = validity
                if 'lease_wall_s' in validity:
                    self.stats['lease_wall_s'].append(validity['lease_wall_s'])
                    self.stats['lease_s'].append(validity['lease_s'])
                self.stats['validity_reasons'][str(validity.get('reason', validity.get('source')))] += 1
                pending_logs.append(self._try_commit(job, cand, b + self._overhead(t0), rec))
            else:
                rec['offered'] = False
                self.stats['withheld'] += 1
        ctx = self._ctx(b, job)
        if job.depth < self.config.min_depth:
            cont, reason = True, 'min_depth'
        elif job.depth >= self.config.max_depth:
            cont, reason = False, 'max_depth'
        else:
            cont, reason = self.policy.continue_refinement(job, ctx)
        overhead = self._overhead(t0)
        self.profile.add_overhead(overhead)
        self.stats['overheads'].append(overhead)
        decision = {'at_depth': job.depth, 'boundary_s': b, 'continue': bool(cont), 'reason': reason,
                    'overhead_s': overhead, 'refresh_bound_s': ctx.profile.refresh_bound_s,
                    'next_step_bound_s': ctx.profile.next_step_bound_s(job.depth + 1)}
        if job.phase == 'prefix':
            job.prefix['decision'] = decision
        else:
            job.steps[-1]['decision'] = decision
        for kind, sim_s, data in pending_logs:
            self.logger.event(kind, sim_s, **data)
        if cont:
            self._launch_step(job, b + overhead, reason)
        else:
            self._end_job(job, b + overhead, reason)

    def _launch_step(self, job, t_launch, reason):
        depth = job.depth + 1
        res = self.backend.step(job.state, depth)
        cost = self.profile.timeline_cost('step', depth, res.cost_s)
        self.profile.add_step(depth, res.cost_s)
        job.depth = depth
        job.phase = 'step'
        job.pending_plan = np.asarray(res.plan_xy, dtype=np.float32).reshape(PLAN_POINTS, 2)
        job.busy_until_s = t_launch + cost
        self.stats['busy_intervals'].append((t_launch, t_launch + cost))
        job.steps.append({'depth': depth, 'launch_s': t_launch, 'cost_s': res.cost_s, 'timeline_cost_s': cost,
                          'wall_s': res.wall_s, 'launch_reason': reason, 'plan': job.pending_plan, **res.info})
        self.stats['gpu_busy_s'] += cost
        self.stats['step_costs'].append(res.cost_s)

    def _end_job(self, job, t_end, reason):
        job.end_s = t_end
        job.stop_reason = reason
        job.phase = 'done'
        try:
            self.backend.release(job.state)
        finally:
            job.state = None
            job.obs.payload = None
        self.gpu_free_s = t_end
        self._idle_query_s = -math.inf
        self._declined_s = -math.inf
        self.last_job = job
        self.job = None
        self.stats['jobs'] += 1
        self.stats['stop_reasons'][reason] += 1
        self.stats['final_depths'][job.depth] += 1
        self.logger.write('jobs', job.record())
        self.logger.event('job_end', t_end, job_id=job.job_id, obs_id=job.obs.obs_id, depth=job.depth,
                          reason=reason, committed_depths=job.committed_depths)

    def _try_commit(self, job, cand, commit_s, rec):
        """Versioned commit at commit_s; returns the (kind, sim_s, data) log entry to write later."""
        latest = self.latest_committed()
        ok, reason, details = versioned_commit_check(cand, latest, commit_s, self.config)
        overridden = False
        if not ok and not self.config.versioned_commit and not reason.startswith('invalid:shape_or_nonfinite'):
            # A3 ablation: everything except a non-finite plan reaches the controller; the would-be reason is kept.
            overridden, ok = True, True
            self.stats['unversioned_overrides'][reason] += 1
        rec['commit'] = {'accepted': ok, 'reason': reason, 'commit_s': commit_s, 'overridden': overridden}
        if ok:
            cand.commit_s = commit_s
            self._commits.append(cand)
            del self._commits[:-8]
            job.committed_depths.append(cand.depth)
            self.stats['commits'] += 1
            self.stats['committed_depths'][cand.depth] += 1
            return ('commit', commit_s, {**cand.brief(), 'replaced': latest.brief() if latest else None,
                                         'would_reject': reason if overridden else None})
        self.stats['rejects'][reason] += 1
        return ('reject', commit_s, {**cand.brief(), 'reason': reason, 'details': details,
                                     'incumbent': latest.brief() if latest else None})

    # ------------------------------------------------------------------ control
    def control_reference(self, now_s, obs_now: Observation):
        """{'mode': 'track'|'fallback', ...} for the control tick at now_s (strict expiry)."""
        inc = self.incumbent_at(now_s)
        if inc is None:
            return {'mode': 'fallback', 'reason': 'no_plan', 'incumbent': None}
        if now_s + EPS_S >= inc.deadline_s:
            return {'mode': 'fallback', 'reason': 'expired', 'incumbent': inc}
        elapsed = now_s - inc.capture_s
        ref = reanchor_plan(inc.plan_xy, inc.obs.lidar2global, obs_now.lidar2global, elapsed,
                            self.config.extrapolation)
        if not np.isfinite(ref).all():
            return {'mode': 'fallback', 'reason': 'reanchor_nonfinite', 'incumbent': inc}
        return {'mode': 'track', 'reason': None, 'incumbent': inc, 'reference': ref, 'elapsed_s': elapsed}

    def record_tick(self, now_s, ref, control=None, extra=None):
        """Per-tick log row and statistics."""
        inc = ref.get('incumbent')
        self.stats['ticks'] += 1
        if self.stats['first_tick_s'] is None:
            self.stats['first_tick_s'] = now_s
        self.stats['last_tick_s'] = now_s
        if ref['mode'] == 'track':
            self.stats['track_ticks'] += 1
            self.stats['ages'].append(now_s - inc.capture_s)
            if self._in_fallback:
                self.logger.event('fallback_end', now_s)
            self._in_fallback = False
        else:
            self.stats['fallback'][ref['reason']] += 1
            if not self._in_fallback:
                self.stats['fallback_episodes'] += 1
                self.logger.event('fallback_start', now_s, reason=ref['reason'],
                                  incumbent=inc.brief() if inc else None)
            self._in_fallback = True
        job = self.job
        row = {'sim_s': now_s, 'mode': ref['mode'], 'fallback_reason': ref['reason'],
               'incumbent': None if inc is None else {**inc.brief(), 'age_s': now_s - inc.capture_s},
               'gpu': None if job is None else {'job_id': job.job_id, 'obs_id': job.obs.obs_id, 'phase': job.phase,
                                                'depth': job.depth, 'busy_until_s': job.busy_until_s},
               'gpu_idle_since_s': self.gpu_free_s if job is None else None,
               'control': control, 'reference': ref.get('reference'),
               'ref_min_forward_m': float(np.min(ref['reference'][:, 1])) if ref.get('reference') is not None else None}
        if extra:
            row.update(extra)
        self.logger.write('ticks', row)
        return row

    def gpu_busy_within(self, t0, t1):
        """Simulated GPU busy time inside [t0, t1] (work scheduled past the last tick is not counted)."""
        return float(sum(max(0.0, min(b, t1) - max(a, t0)) for a, b in self.stats['busy_intervals']))

    def summary(self):
        s = self.stats
        span = (s['last_tick_s'] - s['first_tick_s'] + FRAME_DT_S) if s['ticks'] else 0.0
        busy = self.gpu_busy_within(s['first_tick_s'], s['last_tick_s'] + FRAME_DT_S) if s['ticks'] else 0.0
        ages = s['ages']
        exceed = {}
        for thr in (0.5, 1.0, 1.5, 2.0):
            late = sum(1 for a in ages if a > thr) + sum(s['fallback'].values())
            exceed[f'gt_{thr:.1f}s'] = late / s['ticks'] if s['ticks'] else None
        return {'schema': SCHEMA_VERSION, 'policy': self.policy.describe(), 'runtime': self.config.to_dict(),
                'ticks': s['ticks'], 'sim_span_s': span, 'track_ticks': s['track_ticks'],
                'fallback_ticks': dict(s['fallback']), 'fallback_episodes': s['fallback_episodes'],
                'fallback_tick_ratio': (sum(s['fallback'].values()) / s['ticks']) if s['ticks'] else None,
                'expired_tick_ratio': (s['fallback'].get('expired', 0) / s['ticks']) if s['ticks'] else None,
                'action_age_s': _quantiles(ages), 'age_or_fallback_exceed_ratio': exceed,
                'jobs': s['jobs'], 'stop_reasons': dict(s['stop_reasons']), 'final_depths': dict(s['final_depths']),
                'commits': s['commits'], 'rejects': dict(s['rejects']), 'withheld_candidates': s['withheld'],
                'committed_depths': dict(s['committed_depths']), 'validity_reasons': dict(s['validity_reasons']),
                'unversioned_overrides': dict(s['unversioned_overrides']),
                'gpu_busy_scheduled_s': s['gpu_busy_s'], 'gpu_busy_in_span_s': busy,
                'gpu_busy_ratio': (busy / span) if span else None,
                'prefix_cost_s': _quantiles(s['prefix_costs']), 'step_cost_s': _quantiles(s['step_costs']),
                'scheduler_overhead_s': _quantiles(s['overheads']),
                'start_overhead_s': _quantiles(s['start_overheads']),
                'preprocess_wall_s': _quantiles(s['preprocess_wall_s']),
                'lease_s': _quantiles(s['lease_s']), 'lease_wall_s': _quantiles(s['lease_wall_s']),
                'profile': self.profile.snapshot()}


# =============================================================================================== agent config

@dataclass
class AgentConfig:
    mode: str                                   # policy name or 'oracle_sync'
    policy_params: dict = field(default_factory=dict)
    runtime: dict = field(default_factory=dict)
    seed: int = 11
    temporal_mode: str = 'latest'               # 'latest' (one bank, newest memory) | 'official' (10-bank rotation)
    precision: str = 'bf16-autocast'            # 'bf16-autocast' (required compatibility path) | 'official'
    prompt_command: str = 'official'
    lease_params_path: Optional[str] = None
    warmup: bool = True
    record_metric_info: bool = True
    det_topk: int = 100
    log_subdir: str = 'framelease'

    @classmethod
    def from_dict(cls, d):
        names = {f.name for f in fields(cls)}
        unknown = sorted(set(d) - names)
        if unknown:
            raise ValueError(f'unknown agent config keys {unknown}')
        cfg = cls(**d)
        if cfg.mode not in RUNTIME_MODES:
            raise ValueError(f'mode must be one of {RUNTIME_MODES}')
        if cfg.temporal_mode not in ('latest', 'official') or cfg.precision not in ('bf16-autocast', 'official'):
            raise ValueError('bad temporal_mode / precision')
        RuntimeConfig.from_dict(cfg.runtime)
        return cfg

    def to_dict(self):
        return {f.name: getattr(self, f.name) for f in fields(self)}


def load_agent_config(path=None):
    path = path or os.environ.get(ENV_RUNTIME_CONFIG)
    if not path:
        raise RuntimeError(f'{ENV_RUNTIME_CONFIG} is not set; run through framelease_v2/run_closed_loop.py')
    return AgentConfig.from_dict(json.loads(Path(path).read_text(encoding='utf-8')))


def job_seed(seed, obs_id):
    """Per-observation model seed: identical flow noise for the same observation tick across policies."""
    return int(hashlib.sha256(f'framelease_v2_job:{int(seed)}:{int(obs_id)}'.encode()).hexdigest()[:8], 16) % (2 ** 31)


# =============================================================================================== real backend

class _PrefixCaptured(Exception):
    pass


class UniDriveFlowBackend:
    """Prefix + single flow steps of the pinned official UniDriveVLA head (stage02 extraction), CUDA-timed."""

    def __init__(self, agent, cfg: AgentConfig):
        import torch
        from stage02_real_vla import build_unidrive_flow_prepare, restore_unidrive_temporal, unidrive_flow_advance
        from framelease_v2.unidrive_boxes import decode_boxes
        self.torch = torch
        self.agent = agent
        self.head = agent.model.planning_head
        if int(self.head.num_sample_steps) != MAX_FLOW_DEPTH:
            raise ValueError('pinned 10-step flow protocol / model mismatch')
        self.prepare, _, self.prefix_source = build_unidrive_flow_prepare(self.head)
        self.advance = unidrive_flow_advance
        self.restore_temporal = restore_unidrive_temporal
        self.decode_boxes = decode_boxes
        self.decoder = self.head.unified_decoder
        self.cfg = cfg

    def _autocast(self):
        if self.cfg.precision == 'bf16-autocast':
            return self.torch.autocast(device_type='cuda', dtype=self.torch.bfloat16)
        return contextlib.nullcontext()

    def _timed(self, fn):
        torch = self.torch
        torch.cuda.synchronize()
        a, b = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
        w0 = time.perf_counter()
        a.record()
        out = fn()
        b.record()
        torch.cuda.synchronize()
        return out, a.elapsed_time(b) / 1000.0, time.perf_counter() - w0

    def _run_prefix(self, inputs):
        captured = {}

        def only_prepare(*a, **kw):
            captured['state'] = self.prepare(*a, **kw)
            raise _PrefixCaptured()

        def call():
            original = self.head.forward_test
            self.head.forward_test = only_prepare
            try:
                with self.torch.no_grad(), self._autocast():
                    self.agent.model(img=inputs['img'], img_metas=inputs['img_metas'],
                                     projection_mat=inputs['projection_mat'], ego_status=inputs.get('ego_status'),
                                     gt_ego_fut_cmd=inputs['gt_ego_fut_cmd'], image_wh=inputs['image_wh'],
                                     timestamp=inputs['timestamp'], rescale=True, return_loss=False)
            except _PrefixCaptured:
                pass
            finally:
                self.head.forward_test = original
            if 'state' not in captured:
                raise RuntimeError('native detector did not reach the planning head')
            return captured.pop('state')
        return self._timed(call)

    def _dets(self, state, obs):
        det = state.get('det')
        if not det:
            return DetectionSet.empty(obs, valid=False)
        d0 = det[0]
        raw = d0['boxes_3d'].detach().float().cpu().numpy().astype(np.float64)
        scores = d0['scores_3d'].detach().float().cpu().numpy().astype(np.float64)
        labels = d0['labels_3d'].detach().cpu().numpy().astype(np.int64)
        order = np.argsort(-scores, kind='stable')[:self.cfg.det_topk]
        raw, scores, labels = raw[order], scores[order], labels[order]
        return DetectionSet(self.decode_boxes(raw), scores, labels, raw, bool(np.isfinite(raw).all()), obs.obs_id,
                            obs.capture_s, obs.lidar2global)

    def prefix(self, obs, keep_payload=False):
        torch = self.torch
        w0 = time.perf_counter()
        inputs = self.agent._fl_model_inputs(obs.payload)
        torch.cuda.synchronize()
        preprocess = time.perf_counter() - w0
        if not keep_payload:
            obs.payload = None
        if self.cfg.temporal_mode == 'latest':
            self.decoder.run_step = 0  # single bank: the newest perception memory, time interval from timestamps
        torch.manual_seed(job_seed(self.cfg.seed, obs.obs_id))
        state, cost, wall = self._run_prefix(inputs)
        del inputs
        dets = self._dets(state, obs)
        return PrefixResult(state=state, cost_s=cost, wall_s=wall, dets=dets, preprocess_wall_s=preprocess,
                            info={'temporal_run_step': int(self.decoder.run_step), 'seed': job_seed(self.cfg.seed, obs.obs_id)})

    def step(self, state, depth):
        torch = self.torch
        if int(state['completed_steps']) != depth - 1:
            raise RuntimeError('flow state and requested depth disagree')

        def call():
            with torch.no_grad(), self._autocast():
                cand = self.advance(self.head, state)
                if state['completed_steps'] == state['num_steps']:
                    cand = torch.cumsum(self.head.denorm_delta(state['x_t']), dim=1)  # official final planning
            return cand
        cand, cost, wall = self._timed(call)
        plan = cand[0].detach().float().cpu().numpy().astype(np.float32)
        return StepResult(plan_xy=plan, cost_s=cost, wall_s=wall, info={'completed_steps': int(state['completed_steps'])})

    def release(self, state):
        if isinstance(state, dict):
            state.clear()

    def reset_temporal(self):
        self.restore_temporal(self.head, None, None)

    def warmup(self, obs):
        """One discarded prefix + 10 steps on the first frame (kernel JIT/autotune), then a clean temporal state."""
        pre = self.prefix(obs, keep_payload=True)
        costs = []
        for d in range(1, MAX_FLOW_DEPTH + 1):
            costs.append(self.step(pre.state, d).cost_s)
        self.release(pre.state)
        self.reset_temporal()
        return {'prefix_cost_s': pre.cost_s, 'step_costs_s': costs, 'preprocess_wall_s': pre.preprocess_wall_s}


# =============================================================================================== evaluator agent

def _build_agent_class():
    import cv2
    import carla
    import torch
    from pyquaternion import Quaternion
    import team_code.unidrivevla_b2d_agent as official
    from team_code.unidrivevla_b2d_agent import CAMERA, UniDriveVLAB2DAgent

    class FrameLeaseLatencyAgent(UniDriveVLAB2DAgent):
        """Official sensors, preprocessing, model and PID; virtual-time scheduling in between."""

        def setup(self, path_to_conf_file):
            self._fl_cfg = load_agent_config()
            super().setup(path_to_conf_file)
            from stage02_real_vla import install_unidrive_command_prompt
            install_unidrive_command_prompt(self.model.planning_head, self._fl_cfg.prompt_command)
            self._fl_dir = Path(os.environ['SAVE_PATH']) / self._fl_cfg.log_subdir
            self._fl_dir.mkdir(parents=True, exist_ok=True)
            self._fl_logger = JsonlLogger(self._fl_dir)
            self._fl_metric_info = {}
            self._fl_oracle_cuda = []
            self._fl_oracle_ticks = 0
            self._fl_warm = not self._fl_cfg.warmup
            self._fl_last_t = None
            self._fl_runtime = None
            self._fl_backend = None
            clock = ('OFFICIAL_ZERO_LATENCY_UPPER_BOUND' if self._fl_cfg.mode == 'oracle_sync'
                     else 'VIRTUAL_TIME_MEASURED_LATENCY')
            config_row = {'agent_config': self._fl_cfg.to_dict(), 'save_name': self.save_name,
                          'evidence': 'CARLA_CLOSED_LOOP REAL_VLA REAL_GPU ' + clock,
                          'ground_truth_use': 'metric_info (hero state) is recorded for the official Bench2Drive '
                                              'metrics only; it never feeds the model, the lease or the controller'}
            if self._fl_cfg.mode != 'oracle_sync':
                env = default_policy_env(self._fl_cfg.lease_params_path)
                policy = make_policy(self._fl_cfg.mode, self._fl_cfg.policy_params, env)
                self._fl_backend = UniDriveFlowBackend(self, self._fl_cfg)
                self._fl_runtime = LatencyRuntime(self._fl_backend, policy,
                                                  RuntimeConfig.from_dict(self._fl_cfg.runtime), self._fl_logger)
                config_row.update(policy=policy.describe(), policy_env=env.describe(),
                                  runtime=self._fl_runtime.config.to_dict())
            (self._fl_dir / 'agent_config.json').write_text(json.dumps(jsonable(config_row), indent=1, sort_keys=True))

        # ---------------------------------------------------------- sensing (official tick() without images)
        def _fl_sense(self, input_data):
            self.step += 1
            gps = input_data['GPS'][1][:2]
            speed = input_data['SPEED'][1]['speed']
            compass = input_data['IMU'][1][-1]
            acceleration = input_data['IMU'][1][:3]
            angular_velocity = input_data['IMU'][1][3:6]
            pos = self.gps_to_location(gps)
            near_node, near_command = self._route_planner.run_step(pos)
            if math.isnan(compass):
                compass = 0.0
                acceleration = np.zeros(3)
                angular_velocity = np.zeros(3)
            ego_theta = -compass + np.pi / 2
            ego2world = np.eye(4)
            ego2world[0:3, 0:3] = Quaternion(axis=[0, 0, 1], radians=ego_theta).rotation_matrix
            ego2world[0:2, 3] = [pos[0], -pos[1]]
            lidar2global = ego2world @ self.lidar2ego
            return {'raw_images': {cam: input_data[cam][1] for cam in CAMERA}, 'gps': gps, 'pos': pos,
                    'speed': speed, 'compass': compass, 'acceleration': acceleration,
                    'angular_velocity': angular_velocity, 'target_xy': near_node, 'command': near_command,
                    'command_next': near_command, 'step': self.step, 'ego_theta': ego_theta,
                    'lidar2global': lidar2global,
                    'steer': self.pid_metadata['steer'] if hasattr(self, 'pid_metadata') else 0}

        @staticmethod
        def _fl_images(raw_images):
            """Exactly the official tick() image path (BGR->RGB, JPEG quality 20 round trip)."""
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 20]
            imgs = {}
            for cam in CAMERA:
                img = cv2.cvtColor(raw_images[cam][:, :, :3], cv2.COLOR_BGR2RGB)
                _, img = cv2.imencode('.jpg', img, encode_param)
                imgs[cam] = cv2.imdecode(img, cv2.IMREAD_COLOR)
            return imgs

        def _fl_model_inputs(self, tick_data):
            """Exactly the official run_step() input construction for one sensed frame."""
            imgs = self._fl_images(tick_data['raw_images'])
            inputs = {'img': [], 'folder': '', 'scene_token': '', 'lidar2img': [], 'lidar2cam': [], 'frame_idx': 0,
                      'timestamp': tick_data['step'] / self.frame_rate}
            for cam in CAMERA:
                inputs['lidar2img'].append(self.lidar2img[cam])
                inputs['lidar2cam'].append(self.lidar2cam[cam])
                img = imgs[cam]
                if self.use_bgr_img:
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                inputs['img'].append(img)
            inputs['lidar2img'] = np.stack(inputs['lidar2img'], axis=0)
            inputs['lidar2cam'] = np.stack(inputs['lidar2cam'], axis=0)
            inputs['aug_config'] = self.get_augmentation()
            ego_speed = tick_data['speed']
            acceleration = tick_data['acceleration']
            ego_accel = [acceleration[0], -acceleration[1], acceleration[2]]
            angular_velocity = -tick_data['angular_velocity']
            ego_status = np.zeros(6)
            ego_status[0] = ego_speed
            ego_status[1:3] = ego_accel[:2]
            ego_status[3:5] = angular_velocity[:2]
            ego_status[5] = tick_data['steer']
            inputs['ego_status'] = np.array(ego_status, np.float32)
            command = tick_data['command']
            if command < 0:
                command = 4
            command -= 1
            command_onehot = np.zeros(6, np.float32)
            command_onehot[command] = 1
            inputs['command'] = command
            inputs['gt_ego_fut_cmd'] = command_onehot
            lidar2global = tick_data['lidar2global']
            inputs['l2g_r_mat'] = lidar2global[0:3, 0:3]
            inputs['l2g_t'] = lidar2global[0:3, 3]
            inputs['lidar2global'] = lidar2global
            image_h, image_w = self.data_aug_conf['final_dim']
            inputs['image_wh'] = np.array([[image_w, image_h] for _ in CAMERA], dtype=np.float32)
            inputs = self.inference_only_pipeline(inputs)
            inputs = official.mm_collate_to_batch_form([inputs], samples_per_gpu=1)
            for key, value in inputs.items():
                if isinstance(value, official.DataContainer):
                    inputs[key] = value.data[0]
                elif isinstance(value[0], official.DataContainer):
                    inputs[key] = value[0].data
                else:
                    inputs[key] = value
                if isinstance(inputs[key], torch.Tensor):
                    inputs[key] = inputs[key].to(self.device)
            return inputs

        # ---------------------------------------------------------- control
        def _fl_track(self, reference, speed):
            """Official PID on the re-anchored reference (same post-processing as the official run_step)."""
            pred = np.asarray(reference, dtype=np.float32)
            steer, throttle, brake, meta = self.pidcontroller.control_pid(pred, speed, pred[-1])
            if brake < 0.05:
                brake = 0.0
            if throttle > brake:
                brake = 0.0
            control = carla.VehicleControl()
            control.steer = np.clip(float(steer), -1, 1)
            control.throttle = np.clip(float(throttle), 0, 0.75)
            control.brake = np.clip(float(brake), 0, 1)
            return control, {'desired_speed': meta['desired_speed'], 'aim': meta['aim'], 'angle': meta['angle']}

        def _fl_fallback(self):
            rc = self._fl_runtime.config
            control = carla.VehicleControl()
            last = float(self.pid_metadata.get('steer', 0.0)) if hasattr(self, 'pid_metadata') else 0.0
            control.steer = last if rc.fallback_steer == 'hold' else 0.0
            control.throttle = 0.0
            control.brake = float(rc.fallback_brake)
            return control

        def _fl_record_metric_info(self):
            if not self._fl_cfg.record_metric_info:
                return
            self._fl_metric_info[self.step] = self.get_metric_info()  # evaluation only, never control
            if self.step % 100 == 0:
                self._fl_dump_metric_info()

        def _fl_dump_metric_info(self):
            if self._fl_cfg.record_metric_info:
                with open(self.save_path / 'metric_info.json', 'w') as f:
                    json.dump(self._fl_metric_info, f, indent=1)

        # ---------------------------------------------------------- step
        @torch.no_grad()
        def run_step(self, input_data, timestamp):
            try:
                if self._fl_cfg.mode == 'oracle_sync':
                    return self._fl_oracle_step(input_data, timestamp)
                return self._fl_latency_step(input_data, timestamp)
            except Exception:
                self._fl_logger.event('agent_exception', float(timestamp), traceback=traceback.format_exc())
                raise

        def _fl_oracle_step(self, input_data, timestamp):
            """The official run_step unchanged (zero latency: the world is paused for the full model)."""
            w0 = time.perf_counter()
            cuda = torch.cuda.is_available()
            if cuda:
                torch.cuda.synchronize()
                a, b = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
                a.record()
            if self._fl_cfg.precision == 'bf16-autocast':
                with torch.autocast(device_type='cuda', dtype=torch.bfloat16):
                    control = super().run_step(input_data, timestamp)
            else:
                control = super().run_step(input_data, timestamp)
            if cuda:
                b.record()
                torch.cuda.synchronize()
            row = {'sim_s': float(timestamp), 'tick': self.step, 'mode': 'oracle_sync', 'fallback_reason': None,
                   'incumbent': {'obs_id': self.step, 'capture_s': float(timestamp), 'depth': MAX_FLOW_DEPTH,
                                 'age_s': 0.0},
                   'control': {'steer': float(control.steer), 'throttle': float(control.throttle),
                               'brake': float(control.brake)},
                   'reference': self.pid_metadata.get('plan_temp'), 'speed_mps': float(input_data['SPEED'][1]['speed']),
                   'desired_speed': self.pid_metadata.get('desired_speed'),
                   'model_and_control_cuda_s': a.elapsed_time(b) / 1000.0 if cuda else None,
                   'wall_s': time.perf_counter() - w0}
            self._fl_logger.write('ticks', row)
            if cuda:
                self._fl_oracle_cuda.append(row['model_and_control_cuda_s'])
            self._fl_oracle_ticks += 1
            return control

        def _fl_latency_step(self, input_data, timestamp):
            w0 = time.perf_counter()
            if not self.initialized:
                self.init()
            now = float(timestamp)
            if self._fl_last_t is not None and abs(now - self._fl_last_t - FRAME_DT_S) > 1e-3:
                self._fl_logger.event('tick_interval_anomaly', now, previous_s=self._fl_last_t)
            self._fl_last_t = now
            sensed = self._fl_sense(input_data)
            obs = Observation(obs_id=self.step, capture_s=now, lidar2global=sensed['lidar2global'],
                              speed_mps=float(sensed['speed']), yaw_rad=float(sensed['ego_theta']),
                              command=int(sensed['command']), payload=sensed)
            if not self._fl_warm:
                info = self._fl_backend.warmup(obs)
                self._fl_logger.event('warmup', now, **info, note='discarded; not on the simulated timeline')
                self._fl_warm = True
            rt = self._fl_runtime
            rt.add_observation(obs)
            rt.advance(now)
            ref = rt.control_reference(now, obs)
            if ref['mode'] == 'track':
                control, pid = self._fl_track(ref['reference'], sensed['speed'])
            else:
                control, pid = self._fl_fallback(), None
            self.pid_metadata = {'steer': float(control.steer), 'throttle': float(control.throttle),
                                 'brake': float(control.brake), 'agent': 'framelease_v2_latency'}
            rt.record_tick(now, ref, {'steer': float(control.steer), 'throttle': float(control.throttle),
                                      'brake': float(control.brake)},
                           {'tick': self.step, 'speed_mps': float(sensed['speed']), 'command': int(sensed['command']),
                            'pid': pid, 'wall_s': time.perf_counter() - w0})
            self._fl_record_metric_info()
            return control

        def destroy(self):
            # The evaluator calls destroy() even when setup() failed part-way: touch only what exists.
            try:
                runtime = getattr(self, '_fl_runtime', None)
                if getattr(self, '_fl_dir', None) is not None and getattr(self, '_fl_cfg', None) is not None:
                    if runtime is not None:
                        summary = runtime.summary()
                    else:
                        n = getattr(self, '_fl_oracle_ticks', 0)
                        summary = {'schema': SCHEMA_VERSION, 'policy': {'name': self._fl_cfg.mode}, 'ticks': n,
                                   'action_age_s': _quantiles([0.0] * n),
                                   'model_and_control_cuda_s': _quantiles(getattr(self, '_fl_oracle_cuda', [])),
                                   'note': 'official zero-latency agent: full model every tick, world paused'}
                    (self._fl_dir / 'summary.json').write_text(json.dumps(jsonable(summary), indent=1, sort_keys=True))
                    if runtime is not None:  # oracle_sync: the official run_step owns metric_info.json
                        self._fl_dump_metric_info()
                if getattr(self, '_fl_logger', None) is not None:
                    self._fl_logger.close()
            finally:
                self._fl_backend = None
                self._fl_runtime = None
                if hasattr(self, 'model'):
                    super().destroy()

    return FrameLeaseLatencyAgent


def get_entry_point():
    """Evaluator hook: the class is built only inside the evaluator process (torch / carla / mmcv imports)."""
    cls = _build_agent_class()
    globals()[cls.__name__] = cls
    return cls.__name__


__all__ = ['LatencyRuntime', 'RuntimeConfig', 'LatencyProfile', 'Observation', 'DetectionSet', 'Candidate', 'Job',
           'PrefixResult', 'StepResult', 'PolicyContext', 'AgentConfig', 'versioned_commit_check', 'reanchor_plan',
           'plan_points_at', 'transform_points', 'planar_lidar2global', 'kinematic_check', 'JsonlLogger',
           'MemoryLogger', 'jsonable', 'load_agent_config', 'job_seed', 'get_entry_point', 'POLICY_NAMES']
