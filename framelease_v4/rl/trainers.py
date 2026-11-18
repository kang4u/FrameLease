"""Offline trainers for the utility selector of Eq. 6 / 8 (outline Sec. III-B and Table II-A).

Data: the SMDP over choice epochs of dataset.py (states where both REFINE and REFRESH are admissible; all other
epochs are forced by the shield and belong to the transition). Rewards are prefix-driving-score increments in DS
units, so an undiscounted episode return equals the official driving score.

Families (each gets the same pre-specified tuning budget, see PROTOCOL.md):
  fqi          finite-horizon undiscounted fitted Q-iteration on the 16 features:
                   Q_0 = 0,  Q_k(s, a) <- R + (1 - done) * V_{k-1}(s'),  k = 1..K   (K = horizon in SMDP steps)
                   V_{k-1}(s') = max_{a' in A_feas(s')} Q~_{k-1}(s', a')  (s' is a choice state: both admissible)
               terminal transitions carry no bootstrap term. Regressor: one ExtraTrees forest per action
               (Ernst et al. 2005), refit from scratch every iteration.
  bandit       contextual bandit, one step: Q(s, a) = E[target | s, a] without bootstrapping; target = R (the
               reward up to the next choice epoch) or the fixed-window gain S(t + W) - S(t) (W in seconds, equal
               duration for both actions).
  fqi_nolease  fqi on the 10 features that are not lease-derived (the shield is unchanged).

Default action: a_det^d(s) = REFINE if depth(s) < d else REFRESH (the deterministic feasible choice of Eq. 8;
d = Candidate.d_det, the tuned heuristic depth d*; d = 10 is the v3 heuristic, i.e. always REFINE at a choice state).
Action coverage / out-of-distribution actions (outline: "consider action coverage and OOD action values"):
  * support: an action head is fitted only with >= min_support logged samples; the learned policy may deviate from
    a_det^d(s) to the other action only if both heads are supported, otherwise it equals a_det^d. The backup uses the
    same rule. Without exploration data (e.g. the heuristic pilot) every family therefore reduces to a_det^d.
  * pessimism: the deviating action's value is Q~(s, a') = mean_trees Q - beta * std_trees Q (deviations from the
    default need a margin that grows where the forest disagrees, i.e. where data are sparse); the default action's
    value is the mean. beta is a tuned hyperparameter (0 = plain FQI).
Deployment model: the selected forest is distilled into a small ReLU MLP (16 -> 32 -> 32 -> 2, masked MSE on the
supported heads, normalisation folded into the weights) and exported for qnet.QUtility.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

from framelease_v4.rl import common as C
from framelease_v4.rl import features as F

FAMILIES = ('fqi', 'bandit', 'fqi_nolease')
REFINE, REFRESH = 0, 1
QNET_SCHEMA = 'framelease_v4.qnet/1'
MAX_DEPTH = 10
DEPTH_COL = F.NAMES.index('depth')


@dataclass(frozen=True)
class Candidate:
    family: str
    horizon: int = 16            # fqi / fqi_nolease: iterations K; bandit: ignored (1)
    window: str = 'step'         # bandit: 'step' or a window in seconds ('0.5', '1', '2')
    min_samples_leaf: int = 20
    beta: float = 0.0
    n_estimators: int = 100
    max_features: float = 1.0
    min_support: int = 30
    seed: int = 0
    margin: float = 0.0          # deviation margin in DS units (fixed 0 in the protocol)
    d_det: int = MAX_DEPTH       # depth of the default action a_det^d (the tuned heuristic depth d*)

    def __post_init__(self):
        if self.family not in FAMILIES:
            raise ValueError(f'family must be one of {FAMILIES}')
        if not 1 <= int(self.d_det) <= MAX_DEPTH:
            raise ValueError(f'd_det must be in [1, {MAX_DEPTH}]')
        if self.family != 'bandit' and int(self.horizon) < 1:
            raise ValueError('horizon >= 1')
        if self.family == 'bandit' and self.window != 'step' and float(self.window) <= 0:
            raise ValueError('window must be "step" or > 0 s')

    @property
    def columns(self):
        return F.NO_LEASE_COLUMNS if self.family == 'fqi_nolease' else F.ALL_COLUMNS

    @property
    def label(self):
        if self.family == 'bandit':
            core = f'bandit_w{self.window}'
        else:
            core = f'{self.family}_K{self.horizon}'
        tail = '' if int(self.d_det) == MAX_DEPTH else f'_d{int(self.d_det)}'
        return f'{core}_leaf{self.min_samples_leaf}_beta{self.beta:g}{tail}'

    @property
    def complexity(self):
        """Tie-break order (smaller = simpler): shorter horizon / window, larger leaves, no pessimism."""
        w = 0.0 if self.window == 'step' else float(self.window)
        return (int(self.horizon) if self.family != 'bandit' else 1, w, -int(self.min_samples_leaf), float(self.beta))

    def as_dict(self):
        return asdict(self)


def grid(family, smoke=False, d_det=MAX_DEPTH):
    """The pre-specified hyperparameter grid of a family (RL_PROTOCOL.md Sec. 4): 12 candidates each; d_det = d*."""
    if smoke:
        if family == 'bandit':
            return [Candidate('bandit', window=w, min_samples_leaf=5, n_estimators=20, min_support=5, d_det=d_det)
                    for w in ('step', '1')]
        return [Candidate(family, horizon=k, min_samples_leaf=5, n_estimators=20, min_support=5, d_det=d_det)
                for k in (2, 4)]
    out = []
    for leaf in (10, 40):
        for beta in (0.0, 1.0):
            if family == 'bandit':
                for w in ('step', '1', '2'):
                    out.append(Candidate('bandit', window=w, min_samples_leaf=leaf, beta=beta, d_det=d_det))
            else:
                for k in (8, 32, 128):
                    out.append(Candidate(family, horizon=k, min_samples_leaf=leaf, beta=beta, d_det=d_det))
    return out


def default_actions(X16, d_det=MAX_DEPTH):
    """a_det^d on full 16-column states: REFRESH where depth >= d, else REFINE."""
    X16 = np.asarray(X16, dtype=np.float64)
    if not len(X16):
        return np.zeros(0, dtype=np.int8)
    return (X16[:, DEPTH_COL] >= float(d_det)).astype(np.int8)


# ============================================================================================ forests

class TreeQ:
    """Per-action ExtraTrees Q-function with support mask and per-tree spread."""

    def __init__(self, cand: Candidate):
        self.cand = cand
        self.models = [None, None]
        self.supported = [False, False]
        self.n_samples = [0, 0]

    def fit(self, X, A, Y):
        from sklearn.ensemble import ExtraTreesRegressor
        c = self.cand
        for a in (REFINE, REFRESH):
            m = A == a
            self.n_samples[a] = int(m.sum())
            self.supported[a] = self.n_samples[a] >= int(c.min_support)
            if self.supported[a]:
                model = ExtraTreesRegressor(n_estimators=int(c.n_estimators), min_samples_leaf=int(c.min_samples_leaf),
                                            max_features=float(c.max_features), random_state=int(c.seed) + 7919 * a,
                                            n_jobs=1)
                self.models[a] = model.fit(X[m], Y[m])
            else:
                self.models[a] = None
        if not any(self.supported):
            raise ValueError(f'no action head has min_support {c.min_support} samples ({self.n_samples})')
        return self

    def predict(self, X):
        """Mean Q per action (n, 2); NaN for an unsupported head."""
        Q = np.full((len(X), 2), np.nan)
        for a in (REFINE, REFRESH):
            if self.models[a] is not None and len(X):
                Q[:, a] = self.models[a].predict(X)
        return Q

    def spread(self, X, a=REFRESH):
        if self.models[a] is None or not len(X):
            return np.zeros(len(X))
        P = np.stack([e.predict(X) for e in self.models[a].estimators_])
        return P.std(axis=0)

    def adjusted(self, X, default=None):
        """Q~: the head of the non-default action (the deviation) lowered by beta x per-tree std; the default
        action's head is the plain mean. default = a_det^d per row (None: REFINE everywhere)."""
        Q = self.predict(X)
        if self.cand.beta > 0 and len(X):
            default = np.zeros(len(X), dtype=np.int8) if default is None else np.asarray(default, dtype=np.int8)
            for a in (REFINE, REFRESH):
                rows = default != a                         # rows where action a would be a deviation
                if rows.any() and self.supported[a]:
                    Q[rows, a] -= float(self.cand.beta) * self.spread(X[rows], a)
        return Q


def greedy(Q, supported, margin=0.0, default=None):
    """Eq. 6 restricted by support: the other action than a_det^d(s) iff both heads are supported and
    Q~[other] > Q~[default] + margin; else a_det^d(s) (ties go to the default). default None = REFINE everywhere."""
    a = np.zeros(len(Q), dtype=np.int8) if default is None else np.array(default, dtype=np.int8, copy=True)
    if supported[REFINE] and supported[REFRESH] and len(Q):
        idx = np.arange(len(Q))
        other = 1 - a
        dev = Q[idx, other] > Q[idx, a] + float(margin)
        a[dev] = other[dev]
    return a


def _check_default_support(q, default):
    for a in (REFINE, REFRESH):
        if not q.supported[a] and np.any(default == a):
            raise ValueError(f'the default action a_det^d is {("REFINE", "REFRESH")[a]} at {int(np.sum(default == a))} '
                             f'states but that head has only {q.n_samples[a]} samples (< min_support)')


def value_of(Q, actions):
    return Q[np.arange(len(Q)), actions]


def _cols(X, cols):
    return X[:, list(cols)] if len(cols) != X.shape[1] else X


def fit_candidate(ds, ep_ids, cand: Candidate, log=None):
    """Fit one candidate on the transitions of episodes ep_ids (training routes only). Returns (TreeQ, info)."""
    bad = [i for i in ep_ids if ds.episodes[i]['split'] != 'train']
    if bad:
        raise PermissionError(f'episodes {bad} are not training episodes')
    m = ds.episode_mask(ep_ids)
    X, XN, A, R, D = (_cols(ds.X[m], cand.columns), _cols(ds.XN[m], cand.columns), ds.A[m].astype(np.int8),
                      ds.R[m], ds.DONE[m])
    dflt, dflt_n = default_actions(ds.X[m], cand.d_det), default_actions(ds.XN[m], cand.d_det)
    info = {'candidate': cand.as_dict(), 'label': cand.label, 'n': int(m.sum()), 'episodes': list(map(int, ep_ids)),
            'iterations': []}
    if cand.family == 'bandit':
        Y = R if cand.window == 'step' else ds.arrays[f'GW{float(cand.window):g}'][m]
        q = TreeQ(cand).fit(X, A, Y)
        _check_default_support(q, dflt)
        info['iterations'].append({'k': 1, 'target_mean': float(np.mean(Y)) if len(Y) else None})
    else:
        q = None
        for k in range(1, int(cand.horizon) + 1):
            if q is None:
                V = np.zeros(len(R))
            else:
                live = ~D
                V = np.zeros(len(R))
                if live.any():
                    Qn = q.adjusted(XN[live], dflt_n[live])
                    V[live] = value_of(Qn, greedy(Qn, q.supported, cand.margin, dflt_n[live]))
            Y = R + V
            prev = q
            q = TreeQ(cand).fit(X, A, Y)
            _check_default_support(q, np.concatenate([dflt, dflt_n[~D]]))
            row = {'k': k, 'target_mean': float(np.mean(Y)) if len(Y) else None}
            if prev is not None and len(X):
                Qp = prev.predict(X)
                row['bellman_residual_mae'] = float(np.mean(np.abs(Y - value_of(Qp, A))))
            info['iterations'].append(row)
            if log:
                log(k, row)
    info['supported'] = list(q.supported)
    info['n_samples'] = list(q.n_samples)
    if len(X):
        Qt = q.adjusted(X, dflt)
        pi = greedy(Qt, q.supported, cand.margin, dflt)
        info['train_deviation_rate'] = float(np.mean(pi != dflt))
        info['train_agreement_with_logged'] = float(np.mean(pi == A))
    return q, info


def policy_fn(q: TreeQ, cand: Candidate):
    """Deterministic policy on full 16-column state arrays (columns selected inside; default from 'depth')."""
    def act(X16):
        X16 = np.asarray(X16, dtype=np.float64)
        if not len(X16):
            return np.zeros(0, dtype=np.int8)
        X = _cols(X16, cand.columns)
        dflt = default_actions(X16, cand.d_det)
        return greedy(q.adjusted(X, dflt), q.supported, cand.margin, dflt)
    return act


def heuristic_policy_fn(d_det=MAX_DEPTH):
    """a_det^d at a choice state (d = 10: the v3 heuristic, REFINE)."""
    def act(X16):
        return default_actions(X16, d_det)
    return act


def heuristic_policy(X16):
    """a_det^10 = the v3 heuristic at a choice state: REFINE."""
    return np.zeros(len(X16), dtype=np.int8)


# ============================================================================================ small MLP (numpy)

def _init(sizes, rng):
    Ws, bs = [], []
    for i, o in zip(sizes[:-1], sizes[1:]):
        Ws.append(rng.normal(0.0, math.sqrt(2.0 / i), size=(i, o)))
        bs.append(np.zeros(o))
    return Ws, bs


def mlp_forward(Ws, bs, X):
    hs = [X]
    h = X
    for i, (W, b) in enumerate(zip(Ws, bs)):
        z = h @ W + b
        h = np.maximum(z, 0.0) if i < len(Ws) - 1 else z
        hs.append(h)
    return h, hs


def train_mlp(X, T, head_mask, hidden=(32, 32), epochs=400, batch=256, lr=3e-3, seed=0, val_frac=0.2,
              patience=40):
    """Masked-MSE regression of the supported Q heads. Inputs / targets are standardised inside; the returned
    weights act on RAW inputs and produce RAW Q values (normalisation folded in)."""
    X = np.asarray(X, dtype=np.float64)
    T = np.asarray(T, dtype=np.float64)
    mask = np.asarray(head_mask, dtype=bool)
    rng = np.random.default_rng(seed)
    xm, xs = X.mean(0), X.std(0)
    xs = np.where(xs < 1e-6, 1.0, xs)
    Tm = T[:, mask]
    ym = float(np.mean(Tm)) if Tm.size else 0.0
    ysd = float(np.std(Tm)) if Tm.size else 1.0
    ysd = ysd if ysd > 1e-9 else 1.0
    Xn = (X - xm) / xs
    Tn = np.where(mask[None, :], (np.nan_to_num(T) - ym) / ysd, 0.0)
    n = len(Xn)
    perm = rng.permutation(n)
    nv = int(round(val_frac * n)) if n >= 10 else 0
    va, tr = perm[:nv], perm[nv:]
    Ws, bs = _init([X.shape[1], *hidden, T.shape[1]], rng)
    mW = [np.zeros_like(w) for w in Ws]
    vW = [np.zeros_like(w) for w in Ws]
    mb = [np.zeros_like(b) for b in bs]
    vb = [np.zeros_like(b) for b in bs]
    b1, b2, eps = 0.9, 0.999, 1e-8
    step = 0
    mf = mask.astype(np.float64)[None, :]
    denom = max(1.0, float(mask.sum()))

    def loss(idx):
        if not len(idx):
            return float('nan')
        out, _ = mlp_forward(Ws, bs, Xn[idx])
        return float(np.mean(np.sum(((out - Tn[idx]) * mf) ** 2, axis=1) / denom))

    best = (math.inf, None, 0)
    hist = []
    for ep in range(int(epochs)):
        order = tr[rng.permutation(len(tr))]
        for s in range(0, len(order), int(batch)):
            idx = order[s:s + int(batch)]
            out, hs = mlp_forward(Ws, bs, Xn[idx])
            g = 2.0 * (out - Tn[idx]) * mf / (denom * len(idx))
            step += 1
            for i in range(len(Ws) - 1, -1, -1):
                gW = hs[i].T @ g
                gb = g.sum(0)
                if i > 0:
                    g = (g @ Ws[i].T) * (hs[i] > 0)
                for P, M, V, G in ((Ws, mW, vW, gW), (bs, mb, vb, gb)):
                    M[i] = b1 * M[i] + (1 - b1) * G
                    V[i] = b2 * V[i] + (1 - b2) * G * G
                    P[i] = P[i] - lr * (M[i] / (1 - b1 ** step)) / (np.sqrt(V[i] / (1 - b2 ** step)) + eps)
        lv = loss(va) if nv else loss(tr)
        hist.append(lv)
        if lv < best[0] - 1e-9:
            best = (lv, ([w.copy() for w in Ws], [b.copy() for b in bs]), ep)
        elif ep - best[2] >= int(patience):
            break
    Ws, bs = best[1]
    # fold the normalisation: raw x -> (x - xm) / xs ; raw q = ym + ysd * out
    W0 = Ws[0] / xs[:, None]
    b0 = bs[0] - (xm / xs) @ Ws[0]
    Ws = [W0] + Ws[1:]
    bs = [b0] + bs[1:]
    Ws[-1] = Ws[-1] * ysd
    bs[-1] = bs[-1] * ysd + ym
    return {'W': Ws, 'b': bs, 'val_loss': best[0], 'best_epoch': best[2], 'epochs_run': len(hist),
            'history': hist[::max(1, len(hist) // 50)]}


def distill(q: TreeQ, cand: Candidate, X16_states, hidden=(32, 32), seed=0, min_agreement=0.98, **kw):
    """Distil the forest's Q~ into a small MLP; retry once with (64, 64) if the greedy actions agree on less than
    min_agreement of the states. Returns (mlp dict, fidelity dict)."""
    X16 = np.asarray(X16_states, dtype=np.float64)
    X = _cols(X16, cand.columns)
    dflt = default_actions(X16, cand.d_det)
    T = q.adjusted(X, dflt)
    mask = np.asarray(q.supported, dtype=bool)
    tree_pi = greedy(T, q.supported, cand.margin, dflt)
    tries = []
    for h in (tuple(hidden), (64, 64)):
        mlp = train_mlp(X, T, mask, hidden=h, seed=seed, **kw)
        out, _ = mlp_forward(mlp['W'], mlp['b'], X)
        pi = greedy(out, q.supported, cand.margin, dflt)
        fid = {'hidden': list(h), 'agreement': float(np.mean(pi == tree_pi)) if len(X) else None,
               'rmse_refine': float(np.sqrt(np.mean((out[:, 0] - T[:, 0]) ** 2))) if len(X) and mask[REFINE] else None,
               'rmse_refresh': float(np.sqrt(np.mean((out[:, 1] - T[:, 1]) ** 2)))
               if len(X) and mask[REFRESH] else None,
               'tree_deviation_rate': float(np.mean(tree_pi != dflt)) if len(X) else None,
               'mlp_deviation_rate': float(np.mean(pi != dflt)) if len(X) else None, 'n_states': int(len(X)),
               'val_loss': mlp['val_loss'], 'best_epoch': mlp['best_epoch']}
        tries.append(fid)
        if fid['agreement'] is None or fid['agreement'] >= min_agreement:
            break
    return mlp, {'tries': tries, 'final': tries[-1], 'ok': bool(tries[-1]['agreement'] is None or
                                                                tries[-1]['agreement'] >= min_agreement)}


def export_qnet(mlp, cand: Candidate, supported, provenance=None, policy_budget_s=1e-4):
    """JSON-able Q-network spec for qnet.QUtility; the name pins the sha256 of the decision-relevant content."""
    import json
    cols = list(cand.columns)
    Ws = [np.array(W, dtype=np.float64) for W in mlp['W']]
    bs = [np.array(b, dtype=np.float64) for b in mlp['b']]
    for j, ok in enumerate(supported):           # an unsupported head is inert (never used by the policy)
        if not ok:
            Ws[-1][:, j] = 0.0
            bs[-1][j] = 0.0
    core = {'schema': QNET_SCHEMA, 'feature_columns': cols, 'feature_spec': F.spec_dict(cols),
            'layers': [{'W': W.tolist(), 'b': b.tolist()} for W, b in zip(Ws, bs)],
            'activation': 'relu', 'actions': ['REFINE', 'REFRESH'], 'supported': [bool(s) for s in supported],
            'deviation_margin': float(cand.margin),
            'a_det': {'rule': 'refine_below_depth', 'depth': int(cand.d_det)}}
    sha = C.sha256_bytes(json.dumps(core, sort_keys=True, separators=(',', ':')).encode())
    return {**core, 'weights_sha256': sha, 'name': f'v4_qnet_{sha[:12]}', 'policy_budget_s': float(policy_budget_s),
            'candidate': cand.as_dict(), 'provenance': provenance or {}}


__all__ = ['FAMILIES', 'MAX_DEPTH', 'Candidate', 'grid', 'default_actions', 'TreeQ', 'greedy', 'value_of',
           'fit_candidate', 'policy_fn', 'heuristic_policy_fn', 'heuristic_policy', 'mlp_forward', 'train_mlp', 'distill', 'export_qnet', 'QNET_SCHEMA']
