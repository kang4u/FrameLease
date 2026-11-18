"""CPU-only fakes shared by the framelease_v4/arms tests (no GPU, no CARLA, no model).

Same contract as framelease_v2/tests/test_runtime.py and framelease_v3/runtime/tests/helpers_v3.py: a fake backend
with known CUDA costs, a fake scheduler clock and the agent's control loop (observation -> advance -> control ->
record), so every policy runs on exactly the v2 timeline machinery.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ['CUDA_VISIBLE_DEVICES'] = ''          # never touch the GPU from tests
sys.dont_write_bytecode = True                   # never leave __pycache__ in the read-only v2 / v3 trees

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v2 import latency_agent as la  # noqa: E402
from framelease_v2 import policies as P  # noqa: E402
from framelease_v3.runtime import v3_lease as VL  # noqa: E402

DT = 0.05
TOL = 1e-9
LEASE_PARAMS = ROOT / 'outputs/framelease_v2/c2_calibration/full_20261107T045343Z/lease_params_q95_envelope.json'


def straight_plan(obs, depth, speed=5.0):
    """Plan along LiDAR +y; a small depth-dependent lateral offset makes every depth a different plan."""
    y = speed * la.PLAN_DT_S * np.arange(1, 7)
    return np.stack([np.full(6, 0.01 * depth), y], -1).astype(np.float32)


class FakeBackend:
    """Fake model with known CUDA costs; records the order of real computations."""

    def __init__(self, prefix_s=0.45, step_s=0.015, plan_fn=straight_plan, dets_fn=None, use_payload=None):
        self.prefix_s = prefix_s
        self.step_s = step_s
        self.plan_fn = plan_fn
        self.dets_fn = dets_fn or (lambda obs: la.DetectionSet.empty(obs))
        self.calls = []
        self.released = []
        self.use_payload = use_payload
        self.warmups = 0

    def step_cost(self, depth):
        return float(self.step_s[depth - 1]) if np.ndim(self.step_s) else float(self.step_s)

    def prefix(self, obs):
        self.calls.append(('prefix', obs.obs_id))
        if self.use_payload is not None:
            self.use_payload(obs.payload)
            obs.payload = None
        cost = self.prefix_s(obs) if callable(self.prefix_s) else float(self.prefix_s)
        return la.PrefixResult(state={'obs': obs, 'done': 0}, cost_s=float(cost), wall_s=0.0,
                               dets=self.dets_fn(obs), preprocess_wall_s=0.0)

    def step(self, state, depth):
        assert state['done'] == depth - 1, 'steps must be computed one at a time in order'
        state['done'] = depth
        self.calls.append(('step', state['obs'].obs_id, depth))
        return la.StepResult(plan_xy=self.plan_fn(state['obs'], depth), cost_s=self.step_cost(depth), wall_s=0.0)

    def release(self, state):
        self.released.append(state['obs'].obs_id)

    def warmup(self, obs):
        self.warmups += 1
        return {'prefix_cost_s': 0.0, 'step_costs_s': [], 'preprocess_wall_s': 0.0}


class SteppingTimer:
    """Fake scheduler clock: every read advances by delta seconds."""

    def __init__(self, delta):
        self.delta = delta
        self.t = 0.0

    def __call__(self):
        self.t += self.delta
        return self.t


def make_obs(k, speed=5.0, yaw=math.pi / 2, command=4, moving=False):
    t = k * DT
    y = speed * t if moving else 0.0
    return la.Observation(obs_id=k, capture_s=t, lidar2global=la.planar_lidar2global(0.0, y, yaw),
                          speed_mps=speed, yaw_rad=yaw, command=command)


def dets_with(obs, boxes, scores=None, labels=None):
    boxes = np.asarray(boxes, dtype=float).reshape(-1, 7)
    n = len(boxes)
    return la.DetectionSet(boxes, np.asarray(scores if scores is not None else [0.9] * n, dtype=float),
                           np.asarray(labels if labels is not None else [0] * n), np.zeros((n, 10)), True,
                           obs.obs_id, obs.capture_s, obs.lidar2global)


def config(**kw):
    base = dict(kappa=1.0, overhead_scale=0.0, prior_prefix_s=0.45, prior_step_s=0.015, prior_overhead_s=0.0,
                guard_s=0.05, max_age_s=3.0, profile_quantile=0.99)
    base.update(kw)
    return la.RuntimeConfig(**base)


def group_fn(labels):
    names = {0: 'vehicle', 7: 'pedestrian'}
    return np.array([names.get(int(x), 'other') for x in np.asarray(labels).reshape(-1)], dtype=object)


def stub_env(lease_s=2.0):
    """v2 PolicyEnv with a scripted lease (Interface 2 signature), as framelease_v2/tests/test_runtime.py."""
    ego = SimpleNamespace(half_length_m=2.4462, half_width_m=0.9184, center_offset_xy=(0.0, 0.3837),
                          forward_yaw_rad=math.pi / 2)
    params = SimpleNamespace(h_max_s=2.0, score_threshold=0.3, relevant_groups=('vehicle', 'pedestrian'))

    def lease_fn(plan_xy, dets, scores, labels, ego_, params_):
        value = lease_s(plan_xy) if callable(lease_s) else lease_s
        return {'lease_s': value, 'margin_m': 3.0, 'binding_index': None, 'reason': 'stub'}

    def ttc_fn(speed, dets, scores, labels, ego_, params_):
        return math.inf
    return P.PolicyEnv(ego=ego, lease_params=params, lease_fn=lease_fn, ttc_fn=ttc_fn, group_fn=group_fn,
                       lease_params_source='stub')


def lease_env(**overrides):
    return VL.build_lease_env(str(LEASE_PARAMS), lease_overrides=overrides or None)


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


def job_projection(row):
    """Everything the timeline decides for one job (no wall-clock fields, no policy_state)."""
    steps = [(s.get('depth'), round(s.get('launch_s'), 9), round(s.get('release_s'), 9),
              (s.get('commit') or {}).get('accepted'), (s.get('commit') or {}).get('reason'),
              round((s.get('commit') or {}).get('commit_s') or -1.0, 9), (s.get('decision') or {}).get('reason'))
             for s in row.get('steps') or []]
    return (row['job_id'], row['obs_id'], round(row['start_s'], 9), round(row['prefix_end_s'], 9),
            round(row['end_s'], 9), row['final_depth'], row['stop_reason'], tuple(row['committed_depths']),
            tuple(steps))


def tick_projection(row):
    inc = row.get('incumbent') or {}
    return (round(row['sim_s'], 9), row['mode'], row['fallback_reason'], inc.get('job_id'), inc.get('depth'))


# ============================================================================================ fake CARLA world

class Vec:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class Rot:
    def __init__(self, yaw=0.0, pitch=0.0, roll=0.0):
        self.yaw, self.pitch, self.roll = float(yaw), float(pitch), float(roll)


class Tr:
    def __init__(self, x, y, yaw):
        self.location = Vec(x, y, 0.0)
        self.rotation = Rot(yaw)


class BBox:
    def __init__(self, hx, hy, hz=0.8, ox=0.0, oy=0.0):
        self.extent = Vec(hx, hy, hz)
        self.location = Vec(ox, oy, hz)


class FakeActor:
    """A CARLA actor: id, type_id, attributes, bounding_box; its state lives in the FakeWorld."""

    def __init__(self, world, aid, type_id, bbox, role=''):
        self.world, self.id, self.type_id, self.bounding_box = world, aid, type_id, bbox
        self.attributes = {'role_name': role} if role else {}

    def get_transform(self):
        x, y, yaw, _, _ = self.world.state[self.id]
        return Tr(x, y, yaw)

    def get_velocity(self):
        _, _, _, vx, vy = self.world.state[self.id]
        return Vec(vx, vy, 0.0)


class FakeActorSnapshot:
    def __init__(self, aid, st):
        self.id = aid
        self._st = st

    def get_transform(self):
        x, y, yaw, _, _ = self._st
        return Tr(x, y, yaw)

    def get_velocity(self):
        return Vec(self._st[3], self._st[4], 0.0)


class FakeSnapshot:
    def __init__(self, state):
        self._s = {aid: FakeActorSnapshot(aid, st) for aid, st in state.items()}

    def __len__(self):
        return len(self._s)

    def __iter__(self):
        return iter(list(self._s.values()))

    def find(self, aid):
        return self._s.get(aid)


class FakeWorld:
    """Actors with constant velocities in CARLA's frame (state: x, y, yaw_deg, vx, vy); step(dt) moves them."""

    def __init__(self):
        self.actors = {}
        self.state = {}
        self.lookups = 0

    def add(self, aid, type_id, x, y, yaw=0.0, vx=0.0, vy=0.0, bbox=None, role=''):
        self.actors[aid] = FakeActor(self, aid, type_id, bbox or BBox(2.3, 1.0), role)
        self.state[aid] = (float(x), float(y), float(yaw), float(vx), float(vy))
        return self.actors[aid]

    def remove(self, aid):
        self.actors.pop(aid, None)
        self.state.pop(aid, None)

    def step(self, dt):
        self.state = {a: (x + vx * dt, y + vy * dt, yaw, vx, vy) for a, (x, y, yaw, vx, vy) in self.state.items()}

    def get_snapshot(self):
        return FakeSnapshot(self.state)

    def get_actors(self, ids=None):
        self.lookups += 1
        if ids is None:
            return list(self.actors.values())
        return [self.actors[i] for i in ids if i in self.actors]

    def get_actor(self, aid):
        return self.actors.get(aid)


def busy_world(rng, n_vehicles=40, n_walkers=10, n_other=200, hero_speed=8.0):
    """Hero driving +x at hero_speed among vehicles / walkers; n_other irrelevant actors (signs, sensors)."""
    w = FakeWorld()
    hero = w.add(1, 'vehicle.lincoln.mkz_2020', 0.0, 0.0, 0.0, hero_speed, 0.0, BBox(2.45, 1.06), role='hero')
    for i in range(n_vehicles):
        w.add(100 + i, 'vehicle.tesla.model3', rng.uniform(-60, 140), rng.choice([-3.5, 0.0, 3.5, 7.0]),
              rng.uniform(-180, 180), rng.uniform(-10, 10), rng.uniform(-1, 1), BBox(2.4, 1.05, ox=0.1))
    for i in range(n_walkers):
        w.add(500 + i, 'walker.pedestrian.0001', rng.uniform(-30, 120), rng.uniform(-10, 10), rng.uniform(-180, 180),
              rng.uniform(-1.5, 1.5), rng.uniform(-1.5, 1.5), BBox(0.3, 0.3))
    for i in range(n_other):
        w.add(1000 + i, 'traffic.speed_limit.30' if i % 2 else 'sensor.camera.rgb', rng.uniform(-500, 500),
              rng.uniform(-500, 500))
    w.add(900, 'static.prop.trafficcone01', 30.0, 2.0, 0.0, bbox=BBox(0.2, 0.2))
    return w, hero
