"""Off-policy evaluation for pre-specified model selection (PROTOCOL.md Sec. 5).

Primary estimator: fitted Q evaluation (FQE; Le et al. 2019) of a deterministic policy pi on held-out episodes,
undiscounted, on the choice-epoch SMDP of dataset.py, with lambda = 1 returns cut at the first disagreement (Watkins
Q(lambda) for a deterministic target; no importance weights are needed because a trajectory segment is used only
while the logged actions equal pi's):
    Y_i = R_i + (0 if done; Y_{i+1} if a_{i+1} = pi(s_{i+1}); else Q_{k-1}(s_{i+1}, pi(s_{i+1}))),  Q_k <- fit(Y),
    k = 1 .. B + 1 with B the largest number of bootstrap points along a held-out episode (finite horizon: every
    terminal reward reaches the first state; capped at iter_cap, flagged). On-policy (pi = behaviour) the target is
    the Monte Carlo return; plain one-step FQE (trace 'one_step') compounds the regression's shrinkage at every one
    of the ~10^2-10^3 choice steps of an episode. One
    ExtraTrees forest per action on the 16 features plus the evaluation-only covariates (route completion so far,
    penalty so far, elapsed time; they let the value model tell early from late states of an episode and are never
    a policy input). The evaluation model is the same for every candidate, whatever features the candidate uses;
    V_e(pi) = pre_choice_e + Q(s_e,first, pi(s_e,first))     (pre_choice = return before the first choice epoch).
The selection statistic of a candidate is the paired difference to the heuristic a_det^d (REFINE below depth d,
else REFRESH; d = 10 is the v3 heuristic) on the same held-out episodes, Delta_e = V_e(pi) - V_e(a_det^d), averaged
over all held-out episodes of the
route-grouped cross-fitting (every training episode is held out exactly once). If pi needs an action head that the
held-out data cannot fit (fewer than min_support samples of that action), the estimate is flagged unsupported.
The same holds for the training fold (PROTOCOL Amendment A6): when the fold's fit data cannot fit the candidate, i.e.
trainers.fit_candidate would raise ValueError because no action head has min_support samples or a head that a_det^d
needs is unsupported (trainers._check_default_support), the candidate is not fitted in that fold, its held-out
evaluation there is unsupported (fit_support; the fold record carries 'fit_unsupported'), it cannot be selected, and
the selection of the family continues with every other candidate and fold. Folds the fit data supports are evaluated
exactly as before, and the training-split guard of fit_candidate (PermissionError) applies to every fold, fitted or not.

Calibration (reported, not used for selection): FQE of the logged behaviour policy vs its own Monte Carlo returns on
the held-out episodes (the evaluation model's bias; a shared bias cancels in the paired deltas).
Diagnostics (not used for selection): weighted per-decision importance sampling (WPDIS) and weighted doubly robust
(WDR; Thomas & Brunskill 2016) with the logged behaviour propensities, and their effective sample sizes; the
deviation rate of pi (share of choice states where pi != a_det) and its agreement with the logged actions.
Uncertainty: route-clustered bootstrap (resample routes with replacement) of the mean Delta.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from framelease_v4.rl import trainers as TR

REFINE, REFRESH = 0, 1


@dataclass(frozen=True)
class FQEConfig:
    n_estimators: int = 50
    min_samples_leaf: int = 10
    min_support: int = 5
    iter_cap: int = 600          # iterations = min(longest held-out episode in choice steps + 1, iter_cap)
    seed: int = 1
    eval_covariates: bool = True  # value model also sees (RC so far, penalty so far, time); policies never do
    trace: str = 'watkins'        # 'watkins': lambda = 1 return cut at the first disagreement; 'one_step': plain FQE

    def as_dict(self):
        return asdict(self)


def _forests(X, A, Y, cfg):
    from sklearn.ensemble import ExtraTreesRegressor
    models = [None, None]
    for a in (REFINE, REFRESH):
        m = A == a
        if int(m.sum()) >= int(cfg.min_support):
            models[a] = ExtraTreesRegressor(n_estimators=int(cfg.n_estimators),
                                            min_samples_leaf=int(cfg.min_samples_leaf), max_features=1.0,
                                            random_state=int(cfg.seed) + 104729 * a, n_jobs=1).fit(X[m], Y[m])
    return models


def _q_at(models, X, actions):
    out = np.full(len(X), np.nan)
    for a in (REFINE, REFRESH):
        sel = actions == a
        if sel.any() and models[a] is not None:
            out[sel] = models[a].predict(X[sel])
    return out


def _lambda_returns(R, D, agree_next, boot):
    """Y_i = R_i + (0 if done_i; Y_{i+1} if the logged next action equals pi(s'); else boot_i), backwards."""
    Y = np.array(R, dtype=np.float64, copy=True)
    for i in range(len(Y) - 2, -1, -1):
        if not D[i]:
            Y[i] += Y[i + 1] if agree_next[i] else boot[i]
    if len(Y) and not D[-1]:
        Y[-1] += boot[-1]
    return Y


def fqe(ds, ep_ids, policy, cfg: FQEConfig = FQEConfig()):
    """Per-episode FQE values of `policy` (callable on (n, 16) states -> actions) on episodes ep_ids."""
    ep_ids = [int(i) for i in ep_ids]
    m = ds.episode_mask(ep_ids)
    X, XN, A, R, D, E, FIRST = ds.X[m], ds.XN[m], ds.A[m].astype(np.int8), ds.R[m], ds.DONE[m], ds.EP[m], ds.FIRST[m]
    if cfg.eval_covariates and 'XE' in ds.arrays:
        VX, VXN = np.hstack([X, ds.XE[m]]), np.hstack([XN, ds.XEN[m]])     # value-model inputs
    else:
        VX, VXN = X, XN
    pre = {i: float(ds.episodes[i]['pre_choice_return']) for i in ep_ids}
    no_choice = [i for i in ep_ids if ds.episodes[i]['n_choice'] == 0]
    live = ~D
    piN = np.zeros(len(X), dtype=np.int8)
    if live.any():
        piN[live] = policy(XN[live])
    first_idx = np.where(FIRST)[0]
    pi0 = policy(X[first_idx]) if len(first_idx) else np.zeros(0, dtype=np.int8)
    need = np.concatenate([piN[live], pi0])
    support = [int(np.sum(A == a)) >= int(cfg.min_support) for a in (REFINE, REFRESH)]
    unsupported = float(np.mean([not support[a] for a in need])) if len(need) else 0.0
    result = {'episodes': ep_ids, 'n': int(len(X)), 'support': support, 'unsupported_frac': unsupported,
              'refresh_rate_first': float(np.mean(pi0 == REFRESH)) if len(pi0) else None}
    if not len(X):
        result.update(V={i: ds.episodes[i]['ds'] for i in ep_ids}, iterations=0, converged=True)
        return result
    if unsupported > 0:
        result.update(V={i: float('nan') for i in ep_ids}, iterations=0, converged=False)
        for i in no_choice:
            result['V'][i] = float(ds.episodes[i]['ds'])
        return result
    # rows of an episode are contiguous and ordered, so for a live row i the next choice state is row i + 1
    agree_next = np.zeros(len(X), bool)
    if cfg.trace == 'watkins':
        agree_next[:-1] = live[:-1] & (A[1:] == piN[:-1])
    elif cfg.trace != 'one_step':
        raise ValueError("trace must be 'watkins' or 'one_step'")
    cuts = live & ~agree_next                                  # transitions that bootstrap Q(s', pi(s'))
    # finite horizon: after (max bootstraps along an episode) + 1 backups every terminal reward reaches the first state
    horizon = int(max(np.bincount(E - E.min(), weights=cuts.astype(float)).max(), 0)) + 1
    n_iter = min(horizon + 1, int(cfg.iter_cap))
    models, prev, last_change = None, None, None
    for k in range(1, n_iter + 1):
        boot = np.zeros(len(X))
        if models is not None and cuts.any():
            boot[cuts] = _q_at(models, VXN[cuts], piN[cuts])
        Y = _lambda_returns(R, D, agree_next, boot)
        models = _forests(VX, A, Y, cfg)
        vfirst = _q_at(models, VX[first_idx], pi0)
        if prev is not None:
            last_change = float(np.max(np.abs(vfirst - prev)))
        prev = vfirst
    vals = {int(E[j]): pre[int(E[j])] + float(v) for j, v in zip(first_idx, vfirst)}
    for i in no_choice:
        vals[i] = float(ds.episodes[i]['ds'])
    result.update(V=vals, iterations=n_iter, horizon=horizon, converged=bool(horizon + 1 <= int(cfg.iter_cap)),
                  last_change=last_change, models=models)
    return result


def behaviour_calibration(ds, ep_ids, cfg: FQEConfig = FQEConfig()):
    """Bias of the evaluation model on held-out data: its on-policy value of the logged (stochastic) behaviour policy
    against the Monte Carlo returns of the same episodes. On-policy, the lambda = 1 target of every transition is the
    logged return-to-go G = DS - S(t), so this is one regression of G on (state, logged action); the episode value is
    pre_choice + sum_a mu(a | s_first) Q(s_first, a). A shared bias cancels in the paired selection deltas."""
    ep_ids = [int(i) for i in ep_ids if ds.episodes[int(i)]['n_choice'] > 0]
    m = ds.episode_mask(ep_ids)
    if not m.any():
        return {'fqe_mean': None, 'mc_mean': None, 'bias': None, 'n_episodes': 0}
    X, A, E, FIRST, MU, G = ds.X[m], ds.A[m].astype(np.int8), ds.EP[m], ds.FIRST[m], ds.MU[m], ds.G[m]
    if not np.all(np.isfinite(MU)):
        return {'fqe_mean': None, 'mc_mean': None, 'bias': None, 'n_episodes': len(ep_ids), 'note': 'mu unknown'}
    VX = np.hstack([X, ds.XE[m]]) if cfg.eval_covariates and 'XE' in ds.arrays else X
    models = _forests(VX, A, G, cfg)
    first = np.where(FIRST)[0]
    p1 = np.where(A[first] == REFRESH, MU[first], 1.0 - MU[first])           # mu(REFRESH | s_first)
    q0 = _q_at(models, VX[first], np.zeros(len(first), np.int8))
    q1 = _q_at(models, VX[first], np.ones(len(first), np.int8)) if models[REFRESH] is not None else q0
    v = (1 - p1) * q0 + p1 * np.nan_to_num(q1)
    pre = np.asarray([ds.episodes[int(E[j])]['pre_choice_return'] for j in first])
    fqe_mean = float(np.mean(pre + v))
    mc_mean = float(np.mean([ds.episodes[i]['ds'] for i in ep_ids]))
    return {'fqe_mean': fqe_mean, 'mc_mean': mc_mean, 'bias': fqe_mean - mc_mean, 'n_episodes': len(ep_ids)}


def importance_diagnostics(ds, ep_ids, policy, q_models=None, q_models_cov=False):
    """WPDIS / WDR values and effective sample sizes for a deterministic policy (behaviour propensities MU)."""
    ep_ids = [int(i) for i in ep_ids if ds.episodes[int(i)]['n_choice'] > 0]
    if not ep_ids:
        return {'wpdis': None, 'wdr': None, 'ess_final': None, 'ess_min': None, 'mu_known': None}
    seqs = []
    for i in ep_ids:
        m = ds.EP == i
        X, A, R, MU = ds.X[m], ds.A[m].astype(np.int8), ds.R[m], ds.MU[m]
        pi = policy(X)
        ratio = (pi == A).astype(np.float64) / MU
        q_logged = v_pi = None
        if q_models is not None:
            VX = np.hstack([X, ds.XE[m]]) if q_models_cov else X
            q_logged = _q_at(q_models, VX, A)
            v_pi = _q_at(q_models, VX, pi)
        seqs.append((np.cumprod(ratio), R, q_logged, v_pi, float(ds.episodes[i]['pre_choice_return'])))
    if not all(np.all(np.isfinite(s[0])) for s in seqs):
        return {'wpdis': None, 'wdr': None, 'ess_final': None, 'ess_min': None, 'mu_known': False}
    H = max(len(s[1]) for s in seqs)
    W = np.zeros((len(seqs), H))
    Rm = np.zeros((len(seqs), H))
    Qm = np.zeros((len(seqs), H))
    Vm = np.zeros((len(seqs), H))
    for e, (w, r, ql, vp, _) in enumerate(seqs):
        n = len(r)
        W[e, :n] = w
        W[e, n:] = w[-1]
        Rm[e, :n] = r
        if ql is not None:
            Qm[e, :n] = np.nan_to_num(ql)
            Vm[e, :n] = np.nan_to_num(vp)
    sw = W.sum(0)
    with np.errstate(invalid='ignore', divide='ignore'):
        wn = np.where(sw > 0, W / sw, 0.0)
    pre = np.mean([s[4] for s in seqs])
    wpdis = pre + float(np.sum(wn * Rm))
    out = {'wpdis': wpdis, 'mu_known': True}
    ess = np.where(sw > 0, sw ** 2 / np.maximum((W ** 2).sum(0), 1e-300), 0.0)
    out['ess_final'] = float(ess[-1])
    out['ess_min'] = float(ess.min())
    out['n_episodes'] = len(seqs)
    if q_models is not None:
        wprev = np.concatenate([np.full((len(seqs), 1), 1.0 / len(seqs)), wn[:, :-1]], axis=1)
        out['wdr'] = pre + float(np.sum(wn * Rm) - np.sum(wn * Qm - wprev * Vm))
    else:
        out['wdr'] = None
    return out


def route_folds(ds, ep_ids, n_folds, seed=20261110):
    """Route-grouped folds (all episodes of a route in one fold); deterministic."""
    routes = sorted({ds.episodes[i]['route_id'] for i in ep_ids})
    rng = np.random.default_rng(seed)
    order = [routes[j] for j in rng.permutation(len(routes))]
    k = max(1, min(int(n_folds), len(routes)))
    fold_of = {r: j % k for j, r in enumerate(order)}
    folds = [[] for _ in range(k)]
    for i in ep_ids:
        folds[fold_of[ds.episodes[i]['route_id']]].append(int(i))
    return [sorted(f) for f in folds if f]


def cluster_bootstrap(delta_by_episode, routes_by_episode, n_boot=2000, seed=7, alpha=0.10):
    """Route-clustered bootstrap of the mean per-episode delta: (mean, lo, hi) with (1 - alpha) coverage."""
    eps_ = [e for e, v in delta_by_episode.items() if np.isfinite(v)]
    if not eps_:
        return {'mean': None, 'lo': None, 'hi': None, 'n_routes': 0, 'n_episodes': 0}
    by_route = {}
    for e in eps_:
        by_route.setdefault(routes_by_episode[e], []).append(delta_by_episode[e])
    keys = sorted(by_route)
    sums = np.asarray([np.sum(by_route[k]) for k in keys])
    cnts = np.asarray([len(by_route[k]) for k in keys])
    mean = float(sums.sum() / cnts.sum())
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(keys), size=(int(n_boot), len(keys)))
    boots = sums[idx].sum(1) / cnts[idx].sum(1)
    return {'mean': mean, 'lo': float(np.quantile(boots, alpha / 2)), 'hi': float(np.quantile(boots, 1 - alpha / 2)),
            'n_routes': len(keys), 'n_episodes': len(eps_), 'n_boot': int(n_boot), 'coverage': 1 - alpha}


def fit_support(ds, fit_ids, cand):
    """Support of one candidate on the fit episodes of a fold, with the conditions of trainers.fit_candidate:
    TreeQ.fit fits a head only with >= cand.min_support logged samples and raises ValueError when no head is supported;
    trainers._check_default_support raises ValueError when a_det^d (d = cand.d_det) needs an unsupported head on the
    states the fit evaluates it at (the choice states; the FQI families also the non-terminal next states).
    'ok' is False exactly when fit_candidate raises one of these two errors (Amendment A6)."""
    m = ds.episode_mask(fit_ids)
    A = ds.A[m].astype(np.int8)
    n = [int(np.sum(A == a)) for a in (REFINE, REFRESH)]
    supported = [k >= int(cand.min_support) for k in n]
    dflt = TR.default_actions(ds.X[m], cand.d_det)
    if cand.family != 'bandit':
        dflt = np.concatenate([dflt, TR.default_actions(ds.XN[m][~ds.DONE[m]], cand.d_det)])
    needs = [bool(np.any(dflt == a)) for a in (REFINE, REFRESH)]
    ok = any(supported) and not any(nd and not s for nd, s in zip(needs, supported))
    return {'n_samples': n, 'min_support': int(cand.min_support), 'supported': supported, 'a_det_needs': needs,
            'ok': bool(ok)}


def _unsupported_fold(ds, cand, fit_ids, eval_ids, heur, support):
    """The record of a fold whose fit data cannot fit the candidate (fit_support 'ok' False; PROTOCOL Secs. 5.5-5.6):
    nothing is fitted, the held-out evaluation is unsupported (unsupported_frac 1.0; V NaN for every episode with a
    choice epoch, the official DS for one without, as fqe does), so the candidate's mean delta is None and it is not
    selectable. The keys of a supported fold's record, plus 'fit_unsupported' (the fit_support result)."""
    V = {i: float(ds.episodes[i]['ds']) if ds.episodes[i]['n_choice'] == 0 else float('nan') for i in eval_ids}
    return {'candidate': cand.label, 'fit_episodes': fit_ids, 'eval_episodes': eval_ids,
            'V': V, 'delta': {i: V[i] - heur['V'][i] for i in eval_ids}, 'fqe_iterations': 0, 'fqe_converged': False,
            'unsupported_frac': 1.0, 'train_supported': list(support['supported']),
            'eval_deviation_rate': None, 'eval_agreement_with_logged': None, 'is_diagnostics': None,
            'fit_unsupported': support}


def _eval_fold(ds, cand, fit_ids, eval_ids, fqe_cfg, heur):
    # the split guard of trainers.fit_candidate (PROTOCOL Sec. 3.3), also for a fold that is not fitted (Amendment A6)
    bad = [i for i in fit_ids if ds.episodes[i]['split'] != 'train']
    if bad:
        raise PermissionError(f'episodes {bad} are not training episodes')
    support = fit_support(ds, fit_ids, cand)
    if not support['ok']:
        return _unsupported_fold(ds, cand, fit_ids, eval_ids, heur, support)
    q, info = TR.fit_candidate(ds, fit_ids, cand)
    pol = TR.policy_fn(q, cand)
    res = fqe(ds, eval_ids, pol, fqe_cfg)
    diag = importance_diagnostics(ds, eval_ids, pol, res.get('models'),
                                  q_models_cov=bool(fqe_cfg.eval_covariates and 'XE' in ds.arrays))
    delta = {i: res['V'][i] - heur['V'][i] for i in eval_ids}
    m = ds.episode_mask(eval_ids)
    acts = pol(ds.X[m]) if m.any() else np.zeros(0)
    dflt = TR.default_actions(ds.X[m], cand.d_det) if m.any() else np.zeros(0)
    return {'candidate': cand.label, 'fit_episodes': fit_ids, 'eval_episodes': eval_ids,
            'V': res['V'], 'delta': delta, 'fqe_iterations': res['iterations'], 'fqe_converged': res['converged'],
            'unsupported_frac': res['unsupported_frac'], 'train_supported': info['supported'],
            'eval_deviation_rate': float(np.mean(acts != dflt)) if len(acts) else None,
            'eval_agreement_with_logged': float(np.mean(acts == ds.A[m])) if len(acts) else None,
            'is_diagnostics': diag}


def select(ds, candidates, ep_ids=None, n_folds=5, fqe_cfg: FQEConfig = FQEConfig(), n_jobs=1, seed=20261110,
           n_boot=2000):
    """Route-grouped cross-fitted FQE selection within one family. Returns a JSON-able report with 'selected'."""
    ep_ids = ds.train_episode_ids() if ep_ids is None else [int(i) for i in ep_ids]
    d_dets = {int(c.d_det) for c in candidates}
    if len(d_dets) != 1:
        raise ValueError('all candidates of a selection must share the default a_det^d')
    d_det = d_dets.pop()
    folds = route_folds(ds, ep_ids, n_folds, seed)
    heur, calib = {}, {}
    for f, ev in enumerate(folds):
        heur[f] = fqe(ds, ev, TR.heuristic_policy_fn(d_det), fqe_cfg)
        calib[f] = behaviour_calibration(ds, ev, fqe_cfg)
    jobs = []
    for c in candidates:
        for f, ev in enumerate(folds):
            fit = sorted(set(ep_ids) - set(ev))
            jobs.append((c, f, fit, ev))
    if n_jobs and n_jobs != 1:
        from joblib import Parallel, delayed
        outs = Parallel(n_jobs=n_jobs)(delayed(_eval_fold)(ds, c, fit, ev, fqe_cfg, {'V': heur[f]['V']})
                                       for c, f, fit, ev in jobs)
    else:
        outs = [_eval_fold(ds, c, fit, ev, fqe_cfg, {'V': heur[f]['V']}) for c, f, fit, ev in jobs]
    routes = {i: ds.episodes[i]['route_id'] for i in ep_ids}
    rows = []
    for c in candidates:
        mine = [o for o in outs if o['candidate'] == c.label]
        delta = {}
        for o in mine:
            delta.update(o['delta'])
        finite = [v for v in delta.values() if np.isfinite(v)]
        boot = cluster_bootstrap(delta, routes, n_boot=n_boot)
        rows.append({'candidate': c.as_dict(), 'label': c.label, 'complexity': list(c.complexity),
                     'mean_delta': float(np.mean(finite)) if len(finite) == len(delta) and finite else None,
                     'bootstrap': boot, 'unsupported_folds': sum(o['unsupported_frac'] > 0 for o in mine),
                     'folds': [{k: v for k, v in o.items() if k not in ('V',)} for o in mine]})
    valid = [r for r in rows if r['mean_delta'] is not None]
    selected = None
    if valid:
        best = max(r['mean_delta'] for r in valid)
        tied = [r for r in valid if r['mean_delta'] >= best - 1e-6]
        selected = min(tied, key=lambda r: tuple(r['complexity']))['label']
    return {'family': candidates[0].family if candidates else None, 'a_det_depth': d_det, 'folds': folds,
            'n_folds': len(folds),
            'fqe': fqe_cfg.as_dict(), 'heuristic': {f: {k: v for k, v in h.items() if k != 'models'}
                                                     for f, h in heur.items()},
            'behaviour_calibration': calib, 'candidates': rows, 'selected': selected,
            'rule': 'argmax of the cross-fitted FQE mean paired delta vs a_det; ties (1e-6) -> simplest '
                    '(horizon/window, larger leaf, smaller beta); unsupported candidates are not selectable'}


__all__ = ['FQEConfig', 'fqe', 'behaviour_calibration', 'importance_diagnostics', 'route_folds', 'cluster_bootstrap',
           'fit_support', 'select']
