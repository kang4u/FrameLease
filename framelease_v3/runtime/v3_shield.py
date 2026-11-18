"""Action-specific feasibility shield (outline Eq. 5) and the shielded decision rule (Eq. 8 with the fixes).

At a decision epoch t (a refinement-quantum boundary of the running job, depth d >= 1) with the active committed
candidate's deadline D* (-inf without an active candidate) and the deadline D_c of the running job's newest
candidate:

    A_feas = { a in {REFINE, REFRESH} : C_a = 1  and  t + L_pi + L_a + L_commit + R_a + eps < D* }

    REFINE   L_a = L_step^bnd(d + 1), R_a = L_REFRESH^bnd + L_commit^bnd (the refresh recovery path stays reserved)
             C_a: d < d_max and t + L_pi + L_step^bnd + L_commit^bnd + eps < D_c (the refined result of the current
             observation can still be committed before the current candidate's own deadline)
    REFRESH  L_a = L_REFRESH^bnd (preprocess + prefix + first step + two scheduler boundaries), R_a = 0
             C_a: a frame newer than the running job's observation exists at t (an observation is never processed
             twice; otherwise the only compute action is WAIT)

No GPU-budget term: kappa is fixed and identical across arms. Strict inequality: exactly at the deadline is
infeasible. Bounds are measured (p99 of the runtime's own latency profile, kappa-scaled), so the shield is soft
real-time admission, not a hard guarantee.

Decision (a_det = the deterministic heuristic; a learned utility may replace it only when |A_feas| = 2):
    |A_feas| = 2          -> utility choice; heuristic: REFINE (refine while feasible and d < d_max, else refresh)
    A_feas = {REFINE}     -> REFINE
    A_feas = {REFRESH}    -> REFRESH
    A_feas = {}           -> control mode FALLBACK (the controller keeps the active candidate until D*, the watchdog
                             then brakes) and the compute side starts a RECOVERY_REFRESH immediately, or WAITs for
                             the next frame if none newer exists.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

REFINE, REFRESH, RECOVERY_REFRESH, WAIT = 'REFINE', 'REFRESH', 'RECOVERY_REFRESH', 'WAIT'
ACTIONS = (REFINE, REFRESH)
COMPUTE_ACTIONS = (REFINE, REFRESH, RECOVERY_REFRESH, WAIT)


@dataclass(frozen=True)
class ShieldBounds:
    L_pi: float          # scheduler time at a boundary (lease of the released candidate, commit, decision)
    L_refine: float      # next flow step, kappa-scaled
    L_refresh: float     # new observation: preprocess + prefix + first step + 2 boundaries, kappa-scaled
    L_commit: float      # validation of a released candidate (lease + commit check)
    eps: float           # timing guard

    @property
    def R_refine(self):
        return self.L_refresh + self.L_commit

    R_refresh = 0.0

    def as_dict(self):
        return {'L_pi': self.L_pi, 'L_refine': self.L_refine, 'L_refresh': self.L_refresh, 'L_commit': self.L_commit,
                'R_refine': self.R_refine, 'R_refresh': self.R_refresh, 'eps': self.eps}


@dataclass(frozen=True)
class ShieldResult:
    t: float
    D_star: float
    D_cand: float
    depth: int
    newer_frame: bool
    refine_ok: bool
    refresh_ok: bool
    refine_lhs: float
    refresh_lhs: float
    refine_cand_lhs: float
    refine_why: str      # 'ok' | 'max_depth' | 'candidate_deadline' | 'shield'
    refresh_why: str     # 'ok' | 'no_newer_frame' | 'shield'

    @property
    def feasible(self):
        return tuple(a for a, ok in ((REFINE, self.refine_ok), (REFRESH, self.refresh_ok)) if ok)

    @property
    def both(self):
        return self.refine_ok and self.refresh_ok

    def as_dict(self):
        def f(x):
            return x if math.isfinite(x) else None
        return {'t': self.t, 'D_star': f(self.D_star), 'D_cand': f(self.D_cand), 'depth': self.depth,
                'newer_frame': self.newer_frame, 'refine_ok': self.refine_ok, 'refresh_ok': self.refresh_ok,
                'refine_lhs': self.refine_lhs, 'refresh_lhs': self.refresh_lhs, 'refine_cand_lhs': self.refine_cand_lhs,
                'refine_why': self.refine_why, 'refresh_why': self.refresh_why,
                'refine_margin_s': f(self.D_star - self.refine_lhs), 'refresh_margin_s': f(self.D_star - self.refresh_lhs)}


def _num(x, default=-math.inf):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(v) else v


def shield(t, D_star, D_cand, depth, max_depth, newer_frame, b: ShieldBounds) -> ShieldResult:
    """Eq. 5 for REFINE and REFRESH. Missing or NaN deadlines count as -inf (infeasible)."""
    t = float(t)
    D_star, D_cand = _num(D_star), _num(D_cand)
    refresh_lhs = t + b.L_pi + b.L_refresh + b.L_commit + b.R_refresh + b.eps
    refine_lhs = t + b.L_pi + b.L_refine + b.L_commit + b.R_refine + b.eps
    cand_lhs = t + b.L_pi + b.L_refine + b.L_commit + b.eps
    if not int(depth) < int(max_depth):
        refine_ok, refine_why = False, 'max_depth'
    elif not cand_lhs < D_cand:
        refine_ok, refine_why = False, 'candidate_deadline'
    elif not refine_lhs < D_star:
        refine_ok, refine_why = False, 'shield'
    else:
        refine_ok, refine_why = True, 'ok'
    if not newer_frame:
        refresh_ok, refresh_why = False, 'no_newer_frame'
    elif not refresh_lhs < D_star:
        refresh_ok, refresh_why = False, 'shield'
    else:
        refresh_ok, refresh_why = True, 'ok'
    return ShieldResult(t, D_star, D_cand, int(depth), bool(newer_frame), refine_ok, refresh_ok, refine_lhs,
                        refresh_lhs, cand_lhs, refine_why, refresh_why)


class HeuristicUtility:
    """a_det on |A_feas| = 2: keep refining (REFINE while feasible and depth < d_max).

    A learned utility (outline Eq. 6, argmax_a Q(s, a) over A_feas) plugs in as another object with the same
    select(features, feasible) -> action interface; decide() never lets it leave A_feas.
    """
    name = 'heuristic'

    def select(self, features, feasible):
        return REFINE if REFINE in feasible else feasible[0]


UTILITIES = {'heuristic': HeuristicUtility}


def make_utility(name):
    if name not in UTILITIES:
        raise ValueError(f'unknown utility {name!r}; implemented: {sorted(UTILITIES)}')
    return UTILITIES[name]()


def decide(sr: ShieldResult, utility=None, features=None):
    """(action, reason) of Eq. 8. The action is one of COMPUTE_ACTIONS; FALLBACK is a control mode (watchdog)."""
    feasible = sr.feasible
    if len(feasible) == 2:
        u = utility or HeuristicUtility()
        a = u.select(features, feasible)
        if a not in feasible:  # a learned utility can never leave the feasible set
            a = HeuristicUtility().select(features, feasible)
        return a, f'both_feasible:{u.name}'
    if feasible == (REFINE,):
        return REFINE, f'only_refine_feasible:refresh_{sr.refresh_why}'
    if feasible == (REFRESH,):
        return REFRESH, f'only_refresh_feasible:refine_{sr.refine_why}'
    if sr.newer_frame:
        return RECOVERY_REFRESH, f'none_feasible:refine_{sr.refine_why}:refresh_{sr.refresh_why}'
    return WAIT, f'none_feasible:refine_{sr.refine_why}:no_newer_frame'


__all__ = ['REFINE', 'REFRESH', 'RECOVERY_REFRESH', 'WAIT', 'ACTIONS', 'COMPUTE_ACTIONS', 'ShieldBounds',
           'ShieldResult', 'shield', 'HeuristicUtility', 'UTILITIES', 'make_utility', 'decide']
