"""Utilities registered in the v3 shield by framelease_v4 (no v3 file is edited):

  * the depth-limited heuristic a_det^d (outline Eq. 8, "deterministic feasible choice"; PROTOCOL Sec. 4.4):
        a_det^d(s) = REFINE if depth(s) < d else REFRESH          (consulted only when |A_feas| = 2)
    d = 10 equals the v3 heuristic (refine while feasible: at a both-feasible state depth < 10 always);
  * the behaviour policy for offline-RL data collection: epsilon-random choice among the feasible actions around
    a_det^d, with the propensity of every choice logged;
  * the learned Q-network utility (qnet.QUtility), by name.

framelease_v3.runtime.v3_shield.decide calls a utility's select(features, feasible) ONLY when |A_feas| = 2 (Eq. 8);
a single feasible action is forced and an empty set triggers recovery, so exploration can never leave the shield's
admissible set (the v3 decide() additionally replaces any out-of-set answer by the v3 heuristic). With probability
1 - eps the behaviour utility returns the base selection a_det^d(s); with probability eps it draws uniformly among the
feasible actions. The propensity of the returned action is

    mu(a | s) = (1 - eps) * 1[a = a_det^d(s)] + eps / |A_feas(s)|        (|A_feas| = 2 here)

Logging without editing v3: ShieldedHeuristicPolicy.decide() passes its features dict to select() and then writes
that same dict object into the decisions.jsonl row. select() adds four scalar keys to it, which therefore appear in
the row's "features" (the 32 v3 features are untouched):
    v4_mu          propensity of the returned action
    v4_explore     1 if the uniform branch was taken
    v4_base_action a_det^d(s)
    v4_draw        0-based index of this behaviour draw in the run
The dataset builder reads v4_mu; the reason string is 'both_feasible:<utility name>'.

Names (they encode every parameter; register_utility_name(name) adds a zero-argument factory to
v3_shield.UTILITIES under that name, idempotently):
    v4_adet_d<d>                      a_det^d, d in 1..10
    v4_eps<eps>_seed<seed>            behaviour around the v3 heuristic (= a_det^10)
    v4_eps<eps>_seed<seed>_d<d>       behaviour around a_det^d (d < 10)
    v4_qnet_<sha12>                   Q-network ($FRAMELEASE_V4_QNET, sha256-pinned; its a_det^d is in the file)
Every process that builds the v3 policy (launcher validation, evaluator agent) registers the name first: the v4
launchers in-process, the evaluator through framelease_v4/rl/agent_entry.py (it reads the name from the v3 agent
configuration). Each behaviour instance owns a numpy Generator seeded from the name, so a run is reproducible and the
draws are exogenous (independent of the state).
"""
from __future__ import annotations

import functools
import re

import numpy as np

from framelease_v3.runtime import v3_shield as VS

PREFIX = 'v4_'
MAX_DEPTH = 10
BEHAVIOUR_RE = re.compile(r'^v4_eps(?P<eps>[01](?:\.\d{1,6})?)_seed(?P<seed>\d{1,19})(?:_d(?P<d>\d{1,2}))?$')
ADET_RE = re.compile(r'^v4_adet_d(?P<d>\d{1,2})$')
QNET_RE = re.compile(r'^v4_qnet_(?P<sha>[0-9a-f]{12})$')
LOG_KEYS = ('v4_mu', 'v4_explore', 'v4_base_action', 'v4_draw')


def _check_depth(d):
    d = int(d)
    if not 1 <= d <= MAX_DEPTH:
        raise ValueError(f'a_det depth must be in [1, {MAX_DEPTH}]')
    return d


def a_det_action(depth, d):
    """a_det^d at a both-feasible state: REFINE if depth < d else REFRESH (missing depth -> REFINE)."""
    if depth is None:
        return VS.REFINE
    try:
        v = float(depth)
    except (TypeError, ValueError):
        return VS.REFINE
    if v != v:
        return VS.REFINE
    return VS.REFINE if v < d else VS.REFRESH


class DepthHeuristicUtility:
    """a_det^d: refine while the running job's depth is below d, then refresh (only consulted if both feasible)."""

    def __init__(self, d=MAX_DEPTH, name=None):
        self.d = _check_depth(d)
        self.name = name or f'v4_adet_d{self.d}'

    def select(self, features, feasible):
        if len(feasible) != 2:
            return VS.REFINE if VS.REFINE in feasible else feasible[0]
        get = features.get if isinstance(features, dict) else (lambda k: None)
        return a_det_action(get('depth'), self.d)

    def stats(self):
        return {'name': self.name, 'd': self.d}


def adet_name(d):
    return f'v4_adet_d{_check_depth(d)}'


def behaviour_name(eps, seed, d=MAX_DEPTH):
    eps = float(eps)
    if not 0.0 <= eps <= 1.0:
        raise ValueError('eps must be in [0, 1]')
    seed = int(seed)
    if not 0 <= seed < 2 ** 63:
        raise ValueError('seed must be in [0, 2^63)')
    d = _check_depth(d)
    name = f'v4_eps{eps:.3f}_seed{seed}' + ('' if d == MAX_DEPTH else f'_d{d}')
    parsed = parse_behaviour_name(name)
    if parsed is None or abs(parsed[0] - eps) > 5e-4:
        raise ValueError(f'eps {eps} is not representable with 3 decimals')
    return name


def parse_behaviour(name):
    """(eps, seed, d) of a behaviour name, or None."""
    m = BEHAVIOUR_RE.match(str(name))
    if not m:
        return None
    eps = float(m.group('eps'))
    d = int(m.group('d')) if m.group('d') is not None else MAX_DEPTH
    if not 0.0 <= eps <= 1.0 or not 1 <= d <= MAX_DEPTH:
        return None
    if m.group('d') is not None and d == MAX_DEPTH:
        return None                                   # canonical form of d = 10 has no suffix
    return eps, int(m.group('seed')), d


def parse_behaviour_name(name):
    """(eps, seed) of a behaviour name, or None (see parse_behaviour for the base depth)."""
    p = parse_behaviour(name)
    return None if p is None else (p[0], p[1])


class EpsilonRandomUtility:
    """v3_shield utility: a_det^d with probability 1 - eps, uniform over A_feas with probability eps."""

    def __init__(self, eps, seed, name=None, base=None, d=MAX_DEPTH):
        self.eps = float(eps)
        if not 0.0 <= self.eps <= 1.0:
            raise ValueError('eps must be in [0, 1]')
        self.seed = int(seed)
        self.d = _check_depth(d)
        self.name = name or behaviour_name(self.eps, self.seed, self.d)
        if base is None:
            base = VS.HeuristicUtility() if self.d == MAX_DEPTH else DepthHeuristicUtility(self.d)
        self.base = base
        self.rng = np.random.default_rng(self.seed)
        self.n_draws = 0
        self.n_explore = 0
        self.n_not_both = 0
        self.actions = {VS.REFINE: 0, VS.REFRESH: 0}
        self.last = None

    def propensity(self, action, base_action, n_feasible):
        return (1.0 - self.eps) * float(action == base_action) + self.eps / float(n_feasible)

    def select(self, features, feasible):
        feasible = tuple(feasible)
        base_action = self.base.select(features, feasible)
        if len(feasible) != 2:                     # never reached through VS.decide (forced cases); stay forced
            self.n_not_both += 1
            return base_action
        u = float(self.rng.random())               # one uniform per choice decision
        explore = u < self.eps
        if explore:
            action = feasible[int(self.rng.integers(len(feasible)))]
        else:
            action = base_action
        mu = self.propensity(action, base_action, len(feasible))
        draw = self.n_draws
        self.n_draws += 1
        self.n_explore += int(explore)
        self.actions[action] = self.actions.get(action, 0) + 1
        self.last = {'v4_mu': mu, 'v4_explore': int(explore), 'v4_base_action': base_action, 'v4_draw': draw}
        if isinstance(features, dict):
            features.update(self.last)
        return action

    def stats(self):
        return {'name': self.name, 'eps': self.eps, 'seed': self.seed, 'base_depth': self.d, 'draws': self.n_draws,
                'explore': self.n_explore, 'not_both_calls': self.n_not_both, 'actions': dict(self.actions)}


def _qnet_factory(name):
    from framelease_v4.rl import qnet as Q
    return Q.QUtility.from_environment(expected_name=name)


def register_utility_name(name, utilities=None):
    """Register a v4 utility name in v3_shield.UTILITIES (idempotent). Returns True if the name is a v4 name.

    'heuristic' and other non-v4 names are left alone (False)."""
    utilities = VS.UTILITIES if utilities is None else utilities
    name = str(name)
    if not name.startswith(PREFIX):
        return False
    parsed = parse_behaviour(name)
    m_adet = ADET_RE.match(name)
    if parsed is not None:
        eps, seed, d = parsed
        factory = functools.partial(EpsilonRandomUtility, eps=eps, seed=seed, name=name, d=d)
    elif m_adet and 1 <= int(m_adet.group('d')) <= MAX_DEPTH and name == adet_name(int(m_adet.group('d'))):
        factory = functools.partial(DepthHeuristicUtility, d=int(m_adet.group('d')), name=name)
    elif QNET_RE.match(name):
        factory = functools.partial(_qnet_factory, name)
    else:
        raise ValueError(f'unknown framelease_v4 utility name {name!r}')
    existing = utilities.get(name)
    if existing is not None and getattr(existing, 'keywords', None) == getattr(factory, 'keywords', None) \
            and getattr(existing, 'args', None) == getattr(factory, 'args', None):
        return True
    utilities[name] = factory
    return True


def register_behaviour(eps, seed, d=MAX_DEPTH):
    name = behaviour_name(eps, seed, d)
    register_utility_name(name)
    return name


__all__ = ['PREFIX', 'MAX_DEPTH', 'LOG_KEYS', 'a_det_action', 'DepthHeuristicUtility', 'adet_name', 'behaviour_name',
           'parse_behaviour', 'parse_behaviour_name', 'EpsilonRandomUtility', 'register_utility_name',
           'register_behaviour']
