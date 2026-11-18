"""CPU-only fakes shared by the framelease_v3 runtime tests (no GPU, no CARLA, no model).

The fakes follow framelease_v2/tests/test_runtime.py (FakeBackend with known CUDA costs, fake scheduler clock), so
the v3 runtime is exercised on exactly the v2 timeline machinery.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

os.environ['CUDA_VISIBLE_DEVICES'] = ''  # never touch the GPU from tests

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v2 import latency_agent as la  # noqa: E402
from framelease_v3.runtime import v3_lease as VL  # noqa: E402
from framelease_v3.runtime import v3_scheduler as S  # noqa: E402

DT = 0.05
LEASE_PARAMS = ROOT / 'outputs/framelease_v2/c2_calibration/full_20261107T045343Z/lease_params_q95_envelope.json'
SWEEP_CLIPS = ROOT / 'outputs/framelease_v2/c1_sweep/merged_20clips_20261108T0052/clips'


def straight_plan(obs, depth, speed=5.0):
    """Plan along LiDAR +y; a small depth-dependent lateral offset makes every depth a different plan."""
    y = speed * la.PLAN_DT_S * np.arange(1, 7)
    return np.stack([np.full(6, 0.01 * depth), y], -1).astype(np.float32)


class FakeBackend:
    """Fake model with known CUDA costs; records the order of real computations."""

    def __init__(self, prefix_s=0.9, step_s=0.015, plan_fn=straight_plan, dets_fn=None, use_payload=None):
        self.prefix_s = prefix_s
        self.step_s = step_s
        self.plan_fn = plan_fn
        self.dets_fn = dets_fn or (lambda obs: la.DetectionSet.empty(obs))
        self.calls = []
        self.released = []
        self.use_payload = use_payload

    def step_cost(self, depth):
        return float(self.step_s[depth - 1]) if np.ndim(self.step_s) else float(self.step_s)

    def prefix(self, obs):
        self.calls.append(('prefix', obs.obs_id))
        if self.use_payload is not None:
            self.use_payload(obs.payload)
            obs.payload = None  # like UniDriveFlowBackend: images are dropped once the prefix consumed them
        return la.PrefixResult(state={'obs': obs, 'done': 0}, cost_s=float(self.prefix_s), wall_s=0.0,
                               dets=self.dets_fn(obs), preprocess_wall_s=0.0)

    def step(self, state, depth):
        assert state['done'] == depth - 1, 'steps must be computed one at a time in order'
        state['done'] = depth
        self.calls.append(('step', state['obs'].obs_id, depth))
        return la.StepResult(plan_xy=self.plan_fn(state['obs'], depth), cost_s=self.step_cost(depth), wall_s=0.0)

    def release(self, state):
        self.released.append(state['obs'].obs_id)

    def warmup(self, obs):
        return {'prefix_cost_s': 0.0, 'step_costs_s': [], 'preprocess_wall_s': 0.0}


class SteppingTimer:
    """Fake scheduler clock: every read advances by delta seconds."""

    def __init__(self, delta):
        self.delta = delta
        self.t = 0.0

    def __call__(self):
        self.t += self.delta
        return self.t


def make_obs(k, speed=5.0, yaw=math.pi / 2, command=4):
    return la.Observation(obs_id=k, capture_s=k * DT, lidar2global=la.planar_lidar2global(0.0, 0.0, yaw),
                          speed_mps=speed, yaw_rad=yaw, command=command)


def config(**kw):
    base = dict(kappa=1.0, overhead_scale=0.0, prior_prefix_s=0.9, prior_step_s=0.015, prior_overhead_s=0.0,
                guard_s=0.05, max_age_s=2.5, profile_quantile=0.99)
    base.update(kw)
    return la.RuntimeConfig(**base)


def lease_env(**overrides):
    return VL.build_lease_env(str(LEASE_PARAMS), lease_overrides=overrides or None)


def stub_result(env, lease_s, t_c=None):
    """A LeaseResult whose single synthetic agent margin crosses delta exactly at tau* = H + T_c (H < H_bar), so the
    commit-time margin check of Eq. 9 agrees with the deadline (H = H_bar: no crossing)."""
    cfg = env.cfg
    t_c = cfg.t_c_s if t_c is None else t_c
    tau = env.tau
    h = float(lease_s)
    if h >= cfg.h_bar_s:
        g = np.full((1, len(tau)), cfg.delta_m + 10.0)
        return VL.LeaseResult(cfg.h_bar_s, math.inf, 'horizon_cap', {'n_relevant': 1}, tau, g, t_pred_s=cfg.t_pred_s)
    ts = h + t_c
    g = (cfg.delta_m + (ts - tau))[None, :]                     # linear, crosses delta at ts exactly
    return VL.LeaseResult(max(h, 0.0), ts, 'first_failure' if h > 0 else 'immediate_failure', {'n_relevant': 1},
                          tau, g, t_pred_s=cfg.t_pred_s)


class StubLeasePolicy(S.ShieldedHeuristicPolicy):
    """The v3 policy with the lease value scripted per candidate: lease_fn(cand) -> H (seconds)."""

    def __init__(self, lease_fn, **params):
        super().__init__(env=lease_env(), **params)
        self.lease_fn = lease_fn

    def compute_lease(self, cand):
        return stub_result(self.env, float(self.lease_fn(cand)))


def make_v3_runtime(lease_fn, backend=None, cfg=None, timer=None, logger=None, **params):
    policy = StubLeasePolicy(lease_fn, **params)
    return S.V3Runtime(backend or FakeBackend(), policy, cfg or config(), logger or la.MemoryLogger(),
                       timer=timer or (lambda: 0.0))


def simulate(rt, n_ticks, obs_fn=make_obs, frame_every=1):
    """Control loop of the agent: a new observation every frame_every ticks, advance, control, record."""
    refs = []
    last = None
    for k in range(n_ticks):
        now = k * DT
        if k % frame_every == 0:
            last = obs_fn(k)
            rt.add_observation(last)
        rt.advance(now)
        ref = rt.control_reference(now, last)
        rt.record_tick(now, ref)
        refs.append(ref)
    return refs


def rows(rt, stream):
    return rt.logger.rows.get(stream, [])


def events(rt, kind):
    return [e for e in rt.logger.rows['events'] if e['kind'] == kind]


def random_scene(rng, n=None, near=False):
    """Random detections [cx, cy, length, width, yaw, vx, vy] (LiDAR frame), scores and labels."""
    n = int(rng.integers(0, 30)) if n is None else n
    boxes = np.zeros((n, 7))
    boxes[:, 0] = rng.uniform(-6, 6, n) if near else rng.uniform(-20, 20, n)
    boxes[:, 1] = rng.uniform(-5, 30, n) if near else rng.uniform(-15, 50, n)
    boxes[:, 2] = rng.uniform(0.6, 5.5, n)
    boxes[:, 3] = rng.uniform(0.5, 2.3, n)
    boxes[:, 4] = rng.uniform(-np.pi, np.pi, n)
    boxes[:, 5:7] = rng.normal(0, 2.5, (n, 2)) * (rng.uniform(size=(n, 1)) < 0.6)
    scores = rng.uniform(0.02, 1.0, n)
    labels = rng.choice([0, 1, 2, 3, 7, 4, 5, 8], n)
    return boxes, scores, labels


def random_plan(rng):
    t = np.arange(1, 7) * 0.5
    v = rng.uniform(0.0, 14.0)
    curv = rng.uniform(-0.6, 0.6)
    return np.stack([curv * t ** 2, v * t], -1)


def sweep_frames(max_clips=20, every=9):
    """(det, score, label, candidates[10,6,2]) of real C1-sweep frames (skips when the sweep is unavailable)."""
    out = []
    if not SWEEP_CLIPS.is_dir():
        return out
    for path in sorted(SWEEP_CLIPS.glob('*.npz'))[:max_clips]:
        z = np.load(path, allow_pickle=False)
        for k in range(0, len(z['frame_idx']), every):
            keep = z['det_label'][k] >= 0
            out.append((z['det'][k][keep].astype(float), z['det_score'][k][keep].astype(float),
                        z['det_label'][k][keep], z['candidates'][k].astype(float), float(z['prefix_ms'][k]),
                        z['step_ms'][k].astype(float)))
    return out
