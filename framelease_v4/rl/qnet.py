"""CPU Q-network utility for the shielded scheduler (outline Eq. 6 and Eq. 8; Sec. III-C "Budgeted CPU policy
execution": fixed network, preallocated buffers, bounded CPU call, deterministic fallback, final commit check
unchanged).

QNetwork: a fixed-weight ReLU MLP (exported by trainers.export_qnet; normalisation folded into the weights). All
arrays are float64, C-contiguous and read-only; every forward pass writes into buffers allocated once at load
(np.dot(..., out=...), in-place bias and ReLU), so a call allocates no arrays.

QUtility implements the v3_shield utility protocol select(features, feasible) -> action:
  * v3_shield.decide() calls it only when |A_feas| = 2 (Eq. 8, first branch); select() re-checks and, if not, returns
    the forced choice without touching the network ("only one action feasible -> no RL call");
  * policy budget (Eq. 8 "policy budget permits"): the call is bypassed (a_det) if the shield margin of either
    action is below the budget B_pi (spending B_pi could break that action's admission) or if the network has been
    disabled after too many overruns (> 5% of the last 256 calls over B_pi);
  * the network call is timed; if it took longer than B_pi its result is discarded and a_det is returned (overrun);
  * otherwise a = the other action than a_det^d(s) iff both heads are supported and Q[other] > Q[a_det^d] + margin,
    else a_det^d(s) (ties and unsupported deviations stay with the default). a_det^d(s) = REFINE if depth < d else
    REFRESH, d frozen in the model file (d = 10: the v3 heuristic). The answer is always in A_feas;
    v3_shield.decide() enforces this again and the versioned commit gate (Eq. 9) still checks every candidate.
Logged through the features dict (written into decisions.jsonl by the v3 policy): v4_q_refine, v4_q_refresh,
v4_qnet_s (network wall time), v4_bypass (None or reason), v4_mu = 1.0 (deterministic policy).
Registration: the name 'v4_qnet_<sha12>' (first 12 hex of the weights' sha256) is registered by
behaviour.register_utility_name; the instance loads $FRAMELEASE_V4_QNET and refuses a file with another hash.
"""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

import numpy as np

from framelease_v4.rl import features as F

SCHEMA = 'framelease_v4.qnet/1'
ENV_QNET = 'FRAMELEASE_V4_QNET'
REFINE, REFRESH = 'REFINE', 'REFRESH'


def _canonical_sha(spec):
    import hashlib
    core = {k: spec[k] for k in ('schema', 'feature_columns', 'feature_spec', 'layers', 'activation', 'actions',
                                 'supported', 'deviation_margin', 'a_det')}
    return hashlib.sha256(json.dumps(core, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def load_spec(path):
    spec = json.loads(Path(path).read_text(encoding='utf-8'))
    verify_spec(spec)
    return spec


def verify_spec(spec):
    if spec.get('schema') != SCHEMA:
        raise ValueError(f'Q-network schema {spec.get("schema")!r} != {SCHEMA!r}')
    sha = _canonical_sha(spec)
    if spec.get('weights_sha256') != sha:
        raise ValueError('Q-network weights do not match their sha256')
    if spec.get('name') != f'v4_qnet_{sha[:12]}':
        raise ValueError('Q-network name does not match its sha256')
    if spec.get('actions') != ['REFINE', 'REFRESH']:
        raise ValueError('unexpected action layout')
    a = spec.get('a_det')
    if not isinstance(a, dict) or a.get('rule') != 'refine_below_depth' or not 1 <= int(a.get('depth', 0)) <= 10:
        raise ValueError('a_det must be {"rule": "refine_below_depth", "depth": 1..10}')
    return sha


class QNetwork:
    """Fixed-weight ReLU MLP with preallocated buffers."""

    __slots__ = ('layers', 'bufs', 'vec', 'n_in', 'n_out')

    def __init__(self, spec):
        layers = []
        n_in = len(spec['feature_columns'])
        prev = n_in
        for L in spec['layers']:
            W = np.ascontiguousarray(np.asarray(L['W'], dtype=np.float64))
            b = np.ascontiguousarray(np.asarray(L['b'], dtype=np.float64))
            if W.ndim != 2 or W.shape[0] != prev or b.shape != (W.shape[1],):
                raise ValueError('inconsistent layer shapes')
            if not (np.all(np.isfinite(W)) and np.all(np.isfinite(b))):
                raise ValueError('non-finite weights')
            W.setflags(write=False)
            b.setflags(write=False)
            layers.append((W, b))
            prev = W.shape[1]
        if prev != 2:
            raise ValueError('the output layer must have 2 units (REFINE, REFRESH)')
        if spec.get('activation') != 'relu':
            raise ValueError('only relu is supported')
        self.layers = tuple(layers)
        self.bufs = tuple(np.zeros(W.shape[1], dtype=np.float64) for W, _ in layers)
        fs = spec['feature_spec']
        cols = list(spec['feature_columns'])
        local = [(d['name'], float(d['missing']), float(d['lo']), float(d['hi'])) for d in fs]
        if [d['index'] for d in fs] != cols:
            raise ValueError('feature spec and columns disagree')
        self.vec = F.FastVectorizer(columns=tuple(range(len(cols))), spec=local)
        self.n_in, self.n_out = n_in, 2

    def forward(self, x):
        """Q values (buffer of 2) for a raw feature vector x (n_in,). Allocation-free."""
        h = x
        last = len(self.layers) - 1
        for i, (W, b) in enumerate(self.layers):
            out = self.bufs[i]
            np.dot(h, W, out=out)
            np.add(out, b, out=out)
            if i < last:
                np.maximum(out, 0.0, out=out)
            h = out
        return h

    def q_from_features(self, feats):
        return self.forward(self.vec.fill(feats))


class QUtility:
    """v3_shield utility: argmax_{a in A_feas} Q(s, a) when both are feasible and the policy budget permits."""

    WINDOW = 256
    MIN_CALLS_TO_DISABLE = 64
    MAX_OVERRUN_RATE = 0.05

    def __init__(self, spec, budget_s=None, timer=time.perf_counter, log_to_features=True):
        verify_spec(spec)
        self.spec = spec
        self.name = spec['name']
        self.net = QNetwork(spec)
        self.supported = (bool(spec['supported'][0]), bool(spec['supported'][1]))
        self.both_supported = self.supported[0] and self.supported[1]
        self.d_det = int(spec['a_det']['depth'])
        self.margin = float(spec.get('deviation_margin', 0.0))
        self.budget_s = float(spec.get('policy_budget_s', 1e-4) if budget_s is None else budget_s)
        if not self.budget_s > 0:
            raise ValueError('policy budget must be > 0')
        self.timer = timer
        self.log_to_features = bool(log_to_features)
        self.ring = np.zeros(self.WINDOW, dtype=np.float64)
        self.ring_over = [0] * self.WINDOW
        self.n_over_window = 0         # overruns among the last WINDOW network calls
        self.n_calls = 0               # network calls
        self.n_select = 0              # select() calls
        self.n_not_both = 0
        self.counts = {'REFINE': 0, 'REFRESH': 0}
        self.bypass = {'slack': 0, 'disabled': 0, 'overrun': 0, 'nonfinite': 0}
        self.disabled = False
        self.warmup()

    def warmup(self, n=16):
        """Run the network n times at load (outside any decision epoch) so the first real call is not cold."""
        probe = {}
        for _ in range(int(n)):
            self.net.q_from_features(probe)

    # ------------------------------------------------------------------ construction
    @classmethod
    def from_file(cls, path, expected_name=None, **kw):
        spec = load_spec(path)
        if expected_name is not None and spec['name'] != expected_name:
            raise ValueError(f'{path}: model {spec["name"]} != expected {expected_name}')
        return cls(spec, **kw)

    @classmethod
    def from_environment(cls, expected_name=None, **kw):
        path = os.environ.get(ENV_QNET)
        if not path:
            raise RuntimeError(f'{ENV_QNET} is not set (path of the frozen Q-network JSON)')
        return cls.from_file(path, expected_name=expected_name, **kw)

    # ------------------------------------------------------------------ decision
    def _a_det(self, feasible, features=None):
        """a_det^d: REFINE below depth d, else REFRESH (only both-feasible states reach here; forced otherwise)."""
        if len(feasible) != 2:
            return REFINE if REFINE in feasible else feasible[0]
        depth = features.get('depth') if isinstance(features, dict) else None
        if depth is None or depth != depth:
            return REFINE
        return REFINE if depth < self.d_det else REFRESH

    def _log(self, features, q0, q1, wall, bypass):
        if self.log_to_features and isinstance(features, dict):
            features['v4_q_refine'] = q0
            features['v4_q_refresh'] = q1
            features['v4_qnet_s'] = wall
            features['v4_bypass'] = bypass
            features['v4_mu'] = 1.0

    def select(self, features, feasible):
        if not isinstance(features, dict):            # the v3 policy always passes its features dict
            features = {}
        self.n_select += 1
        if len(feasible) != 2:
            self.n_not_both += 1
            return self._a_det(feasible)
        a_det = self._a_det(feasible, features)
        if self.disabled:
            self.bypass['disabled'] += 1
            self._log(features, None, None, None, 'disabled')
            self.counts[a_det] += 1
            return a_det
        get = features.get
        for key in ('refine_margin_s', 'refresh_margin_s'):
            m = get(key)
            if m is not None and m < self.budget_s:
                self.bypass['slack'] += 1
                self._log(features, None, None, None, 'slack')
                self.counts[a_det] += 1
                return a_det
        t0 = self.timer()
        q = self.net.q_from_features(features)
        q0 = float(q[0])
        q1 = float(q[1])
        wall = self.timer() - t0
        k = self.n_calls % self.WINDOW
        self.ring[k] = wall
        over = 1 if wall > self.budget_s else 0
        self.n_over_window += over - self.ring_over[k]
        self.ring_over[k] = over
        self.n_calls += 1
        if over and self.n_calls >= self.MIN_CALLS_TO_DISABLE and \
                self.n_over_window > self.MAX_OVERRUN_RATE * min(self.n_calls, self.WINDOW):
            self.disabled = True
        if over:
            self.bypass['overrun'] += 1
            self._log(features, q0, q1, wall, 'overrun')
            self.counts[a_det] += 1
            return a_det
        if not (math.isfinite(q0) and math.isfinite(q1)):
            self.bypass['nonfinite'] += 1
            self._log(features, None, None, wall, 'nonfinite')
            self.counts[a_det] += 1
            return a_det
        a = a_det
        if self.both_supported:
            if a_det == REFINE and q1 > q0 + self.margin:
                a = REFRESH
            elif a_det == REFRESH and q0 > q1 + self.margin:
                a = REFINE
        self._log(features, q0 if self.supported[0] else None, q1 if self.supported[1] else None, wall, None)
        self.counts[a] += 1
        return a

    def stats(self):
        n = min(self.n_calls, self.WINDOW)
        w = np.sort(self.ring[:n]) if n else np.zeros(0)
        q = (lambda p: float(w[min(n - 1, int(math.ceil(p * n)) - 1)]) if n else None)
        return {'name': self.name, 'budget_s': self.budget_s, 'select_calls': self.n_select,
                'network_calls': self.n_calls, 'not_both_calls': self.n_not_both, 'actions': dict(self.counts),
                'bypass': dict(self.bypass), 'disabled': self.disabled,
                'recent_wall_s': {'n': n, 'p50': q(0.5), 'p99': q(0.99), 'max': float(w[-1]) if n else None}}


__all__ = ['SCHEMA', 'ENV_QNET', 'load_spec', 'verify_spec', 'QNetwork', 'QUtility']
