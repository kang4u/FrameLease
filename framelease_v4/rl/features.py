"""The RL state: 16 scalars picked from the 32 decision features the v3 runtime logs (outline Sec. III-B, "about 16
scalars; key features lease slack, observation age, refinement progress, GPU budget, runtime latency").

Every feature is read from the `features` dict of a `decisions.jsonl` row (framelease_v3.runtime.v3_scheduler
FEATURE_NAMES) by name. Missing values (None / NaN: no active candidate, no relevant agent, depth 1 has no plan delta)
get a fixed, documented value and every value is clipped to a fixed range, so the vector is finite and bounded. The
same spec is used offline (dataset) and online (qnet.QUtility), and is frozen into every exported model.

Lease-derived features (6) are the ones the "FQI without lease features" ablation removes (outline Table II-A,
"Full RL without Lease-Slack Features"): everything computed from the lease deadline D* / the candidate's own lease,
the shield's lease-relative margins and the lease's clearance terms. The shield itself is unchanged in the ablation.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Feature:
    name: str            # key in the logged 32-feature dict
    lease_derived: bool
    missing: float       # value used when the logged value is None / NaN
    lo: float            # clip range
    hi: float
    meaning: str


FEATURES = (
    Feature('lease_slack_s', True, -3.0, -3.0, 3.0,
            's_lease = D* - t: slack of the active (committed) candidate; missing = no active candidate'),
    Feature('cand_slack_s', True, -3.0, -3.0, 3.0, 'D_cand - t: slack of the running job\'s newest candidate'),
    Feature('refine_margin_s', True, -3.0, -3.0, 3.0, 'D* - lhs_REFINE of Eq. 5 (shield margin of REFINE)'),
    Feature('refresh_margin_s', True, -3.0, -3.0, 3.0, 'D* - lhs_REFRESH of Eq. 5 (shield margin of REFRESH)'),
    Feature('min_g_m', True, 10.0, -5.0, 10.0,
            'min over the suffix grid of the conservative margin g (lease envelope); missing = no relevant agent'),
    Feature('tau_star_s', True, 3.0, 0.0, 3.0, 'first-failure time tau* of the lease; missing = no crossing (T_pred)'),
    Feature('obs_age_s', False, 3.0, 0.0, 3.0, 'age of the running job\'s observation, t - t_k (refinement keeps t_k)'),
    Feature('depth', False, 1.0, 1.0, 10.0, 'refinement progress: flow steps completed by the running job'),
    Feature('plan_delta_m', False, 0.0, 0.0, 5.0, 'refinement progress: max plan change of the last step (0 at depth 1)'),
    Feature('active_age_s', False, 3.0, 0.0, 3.0, 'age of the active candidate\'s observation; missing = none'),
    Feature('newer_frames', False, 0.0, 0.0, 60.0, 'frames captured since the running job\'s observation'),
    Feature('L_refine_s', False, 0.02, 0.0, 0.5, 'runtime latency bound of one refinement quantum (p99, kappa-scaled)'),
    Feature('L_refresh_s', False, 1.0, 0.0, 3.0, 'runtime latency bound of a refresh (prefix + step 1 + boundaries)'),
    Feature('kappa', False, 1.0, 0.5, 4.0, 'GPU budget: contention scale of the simulated GPU (cost = kappa x CUDA)'),
    Feature('ego_speed_mps', False, 0.0, 0.0, 30.0, 'ego speed at the running job\'s observation'),
    Feature('n_relevant', False, 0.0, 0.0, 50.0, 'relevant detected agents (vehicles / pedestrians) of the candidate'),
)
NAMES = tuple(f.name for f in FEATURES)
N_FEATURES = len(FEATURES)
LEASE_DERIVED = tuple(f.name for f in FEATURES if f.lease_derived)
NO_LEASE_COLUMNS = tuple(i for i, f in enumerate(FEATURES) if not f.lease_derived)
ALL_COLUMNS = tuple(range(N_FEATURES))

assert N_FEATURES == 16 and len(LEASE_DERIVED) == 6


def check_against_v3():
    """Every feature is one of the 32 the v3 runtime logs (raises otherwise)."""
    from framelease_v3.runtime.v3_scheduler import FEATURE_NAMES
    missing = [n for n in NAMES if n not in FEATURE_NAMES]
    if missing:
        raise ValueError(f'features not logged by the v3 runtime: {missing}')
    return True


def _value(raw, f):
    if raw is None or isinstance(raw, (str, bytes)):
        return f.missing
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return f.missing
    if math.isnan(v):
        return f.missing
    if v < f.lo:
        return f.lo
    if v > f.hi:
        return f.hi
    return v


def vector(feats, columns=ALL_COLUMNS, out=None):
    """Feature vector (float64) from a logged features dict. Deterministic, finite, clipped."""
    if out is None:
        out = np.empty(len(columns), dtype=np.float64)
    get = feats.get
    for j, i in enumerate(columns):
        f = FEATURES[i]
        out[j] = _value(get(f.name), f)
    return out


def matrix(rows, columns=ALL_COLUMNS):
    X = np.empty((len(rows), len(columns)), dtype=np.float64)
    for k, r in enumerate(rows):
        vector(r, columns, X[k])
    return X


class FastVectorizer:
    """Allocation-free featurizer for the online policy: fixed column list, preallocated output buffer.

    fill(feats) writes into self.buf and returns it (the same array every call)."""

    __slots__ = ('spec', 'buf')

    def __init__(self, columns=ALL_COLUMNS, spec=None):
        spec = spec or [(f.name, f.missing, f.lo, f.hi) for f in FEATURES]
        self.spec = tuple(spec[i] for i in columns)
        self.buf = np.zeros(len(self.spec), dtype=np.float64)

    def fill(self, feats):
        buf = self.buf
        get = feats.get
        i = 0
        for name, miss, lo, hi in self.spec:
            v = get(name)
            if v is None or v.__class__ is str:
                v = miss
            else:
                v = float(v)
                if v != v:
                    v = miss
                elif v < lo:
                    v = lo
                elif v > hi:
                    v = hi
            buf[i] = v
            i += 1
        return buf


def spec_dict(columns=ALL_COLUMNS):
    return [{'index': i, 'name': FEATURES[i].name, 'lease_derived': FEATURES[i].lease_derived,
             'missing': FEATURES[i].missing, 'lo': FEATURES[i].lo, 'hi': FEATURES[i].hi,
             'meaning': FEATURES[i].meaning} for i in columns]


__all__ = ['Feature', 'FEATURES', 'NAMES', 'N_FEATURES', 'LEASE_DERIVED', 'NO_LEASE_COLUMNS', 'ALL_COLUMNS',
           'check_against_v3', 'vector', 'matrix', 'FastVectorizer', 'spec_dict']
