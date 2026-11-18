"""Global-Margin lease arm of Table II-A (fl_global_shield): the v3 shield and a_det with the v2 global-margin lease.

PROTOCOL Secs. 4.1 (arm fl_global_shield), 7.4 (Table II-A lease panel: the offline GLOBAL design, closed loop on
subset E) and 2.4 (lease, shield and commit constants). framelease_v2, framelease_v3 and the pinned framelease_v4
modules are imported read-only; nothing upstream is edited. The arm, its configuration and its launcher are in
arms_ext.py, agent_ext.py and run_closed_loop_ext.py (PROTOCOL Sec. 8.3 pins).

  from framelease_v4.arms_ext import global_shield as GS
  policy = GS.GlobalMarginShieldPolicy(env=lease_env, utility='heuristic')     # lease_env: v3 LeaseEnv with E*

GlobalMarginShieldPolicy = framelease_v3.runtime.v3_scheduler.ShieldedHeuristicPolicy (shield Eq. 5 with p99 bounds and
eps 0.05 s, decision rule Eq. 8 with a_det^d, versioned commit Eq. 9, watchdog; its parameters, utilities, feature
code and decision rows unchanged; the lease-derived feature values are described at the end) with the suffix lease
(Eqs. 1-3) replaced by the offline GLOBAL design of framelease_v4/offline (common.py; stage_frames.global_H):

    m_j = min_{tau in [0, T_pred]} [dist(E(tau), R_j(tau)) - d_safe]                 (the whole plan, past included)
    H_j = sup{D in [0, T_pred] : m_j - B_j(D) > delta},  B_j(D) = sigma_c + vbar_c D + abar_c D^2 / 2   (E* as B(D))
    H   = min(min_j H_j, H_bar),   D = t_k + H                                         (H_bar = T_pred - T_c = 2.5 s)

that is H = min(min_j framelease_v2.lease.agent_leases(geom, P, [delta], 'global'), H_bar) with P =
global_lease_params(env): the framelease_v2 LeaseParams of the offline iso_params (framelease_v3/suffix_lease_eval.py)
with the per-group sigma / vbar / abar of the exported envelope file E* (outputs/framelease_v4/envelopes/<E5|E10|B0>
.json), d_safe 0.5 m, reserve delta 0.2 m, T_pred 3.0 s on the 0.05 s grid, the per-agent cap T_pred and the v3
detection rules (vehicles and pedestrians; score >= 0.1 relevant, >= 0.3 confident; low_conf_mode 'cap': a
low-confidence detection counts like a real one, so it can only shorten the lease). All constants come from the v3
LeaseEnv (SuffixLeaseConfig defaults = PROTOCOL Sec. 2.4) and E*; nothing is tuned for this arm. The arm runs with
these defaults only: arms_ext refuses lease overrides for it and requires the cap H_BAR_S = 2.5 s (PROTOCOL Secs. 2.4,
7.4) in the launcher, the job-line check and the agent. A non-finite plan or invalid perception (missing, flagged
invalid, or a non-finite relevant detection) gives H = 0; no relevant agent gives H = H_bar.

Geometry, once per job and once per candidate. The inherited after_prefix prepares the observation's relevant agents
once per job (framelease_v3.runtime.v3_lease.prepare_agents: the relevant set, the per-agent envelope parameters and
the constant-velocity footprints R_j(tau) of framelease_v2.lease.lease_geometry, bit-identical). lease_geometry
itself cannot be built once per job: the ego footprint E(tau) depends on the plan of each released candidate (every
depth), so compute_lease adds E(tau) (lease_geometry's ego_corners_along_plan) and the clearances per candidate and
evaluates agent_leases on that framelease_v2 LeaseGeometry.

Exact prefilter (default). An agent can bind only if m_j < sigma_j + delta + vbar_j H_bar + abar_j H_bar^2 / 2
(otherwise H_j >= H_bar and the cap decides). The clearance is bounded below by the bounding circles of the ego box
and the agent box at every grid point; exact polygon distances are computed only where that bound is within 1e-6 m
of the agent's threshold, and agents with no such point are skipped (their H_j >= H_bar). H is bit-identical to the
plain computation (tested on every recorded offline frame and on random scenes); it keeps the per-candidate CPU time,
which the runtime charges to the simulated timeline (PROTOCOL Sec. 2.3), at the level of the v3 suffix lease (on the
recorded frames, in every measurement so far, about 0.85 times the CPU time of the suffix lease and a quarter of that of
the plain lease_geometry path, 0.5-0.7 ms per candidate depending on the machine load; tests/test_global_shield.py
prints the current numbers), so the lease panel compares lease definitions, not implementations. prefilter=False
evaluates every agent at every grid point.

Commit-time margin (Eq. 9, second line). The global lease has no time-resolved margin, so the check uses the synthetic
margin of framelease_v4.arms.policies_v4.age_lease_result(env, H, plan), as AgeLeasePolicy does: g(tau) = delta +
(H + T_c - tau) crosses delta exactly at tau* = H + T_c, hence M(t_commit - t_k) > delta <=> t_commit - t_k < H, the
deadline rule t_commit < D (H = H_bar: g = delta + 10 on the grid; invalid inputs: -inf). The result is relabelled as a
global lease: validity source 'global_lease', tau_star_s None, reasons 'global_lease' (0 < H < H_bar), 'global_zero'
(H = 0: some agent's slack m_j - sigma_j - delta <= 0), 'global_cap' (H = H_bar with relevant agents),
'no_relevant_agents', 'invalid_plan', 'invalid_detection', 'perception_unavailable'; an internal error gives H = 0 with
reason 'lease_error:<type>' and margin -inf (the v3 policy's conservative rule, kept under the global-lease label).

Validity diagnostics (logged with every candidate): binding agent (index, group, confidence, motion), its global
margin m_j and the plan time of its minimum clearance, the number of agents and grid points evaluated exactly. The 32
v3 decision features read five of these entries. n_relevant, n_confident, margin0_m and g0_m keep their v3 definitions
(computed by the inherited prepare_agents). n_computed does not: here it counts the agents that the global-lease
prefilter evaluates exactly (every relevant agent with prefilter=False; 0 when no agent can bind), not the agents of
the suffix-lease prefilter. min_g_m and tau_star_s are suffix-lease quantities and None here. These features are
logged only: the arm's utilities read none of them ('heuristic' reads no feature, a_det^d reads depth only).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from framelease_v2 import lease as L2
from framelease_v2.geometry import convex_distance
from framelease_v3.runtime import v3_lease as VL
from framelease_v3.runtime import v3_scheduler as S
from framelease_v4.arms import policies_v4 as PV

SCHEMA = 'framelease_v4.arms_ext.global_shield/1'
NAME = 'fl_global_shield'
TITLE = 'Global-Margin lease (shield + a_det)'
PREFILTER_TOL_M = 1e-6            # exact distances where the lower bound is within this of an agent's threshold
H_BAR_S = 2.5                     # the cap H_bar = T_pred - T_c, fixed (PROTOCOL Secs. 2.4, 7.4; checked by arms_ext)
REASONS = ('global_lease', 'global_zero', 'global_cap', 'no_relevant_agents') + VL.INVALID_REASONS
COMMIT_MARGIN = ('synthetic margin of framelease_v4.arms.policies_v4.age_lease_result(env, H, plan): g(tau) = delta + '
                 '(H + T_c - tau) crosses delta exactly at H + T_c, so M(t_commit - t_k) > delta <=> t_commit - t_k < H')
DEFINITION = ("H = min(min_j framelease_v2.lease.agent_leases(geom, P, [delta], 'global'), H_bar); m_j = min over the "
              'whole plan [0, T_pred] of the footprint clearance minus d_safe; B_j(D) = sigma + vbar D + abar D^2 / 2 '
              'of E*; H = 0 for a non-finite plan or invalid perception, H_bar without relevant agents')


# ============================================================================================ lease parameters

def global_lease_params(env: VL.LeaseEnv) -> L2.LeaseParams:
    """P of the global-margin lease: framelease_v2 LeaseParams from the v3 LeaseEnv (constants of SuffixLeaseConfig,
    per-group sigma / vbar / abar of its isotropic quadratic envelope E*), field by field the offline
    framelease_v3/suffix_lease_eval.iso_params (per-agent cap h_max_s = T_pred; 'other' = the largest value of each
    table, never read: only relevant groups have agents), with margin_mode 'global'."""
    cfg, env_b = env.cfg, env.envelope
    if env_b.kind != 'iso' or env_b.motion_bins:
        raise ValueError(f'{NAME}: the global-margin lease needs an isotropic quadratic envelope without motion bins '
                         f'(B(D) = sigma + vbar D + abar D^2 / 2 per class group); got kind {env_b.kind!r}, '
                         f'motion_bins {env_b.motion_bins}')
    groups = tuple(cfg.relevant_groups)
    tables = {}
    for name, idx in (('sigma_m', 0), ('vbar_mps', 1), ('abar_mps2', 2)):
        vals = {g: float(env_b.params([g], [False])[idx][0]) for g in groups}
        vals['other'] = max(vals.values())
        tables[name] = vals
    return L2.LeaseParams(d_safe_m=float(cfg.d_safe_m), reserve_m=float(cfg.delta_m), h_max_s=float(cfg.t_pred_s),
                          score_threshold=float(cfg.score_threshold), horizon_s=float(cfg.t_pred_s),
                          dt_s=float(cfg.dt_s), low_score_floor=float(cfg.low_score_floor),
                          low_conf_mode=str(cfg.low_conf_mode), relevant_groups=groups, margin_mode='global',
                          min_speed_mps=float(cfg.min_speed_mps), **tables).validate()


def global_lease_spec(env: VL.LeaseEnv, params: L2.LeaseParams = None, prefilter=True):
    """JSON-ready description of the lease (recorded in the arm's configuration and checked again by the agent)."""
    p = params or global_lease_params(env)
    return {'schema': SCHEMA, 'margin_mode': 'global', 'definition': DEFINITION, 'h_bar_s': float(env.cfg.h_bar_s),
            'reserve_m': float(env.cfg.delta_m), 'lease_params': p.to_dict(),
            'envelope_sha256': env.envelope.sha256, 'envelope_source': env.envelope.source,
            'prefilter': 'exact bounding-circle prefilter (bit-identical H)' if prefilter else 'none',
            'commit_margin': COMMIT_MARGIN}


# ============================================================================================ lease

@dataclass
class GlobalLeaseResult(VL.LeaseResult):
    """LeaseResult of the global-margin lease: H from the global margin, the commit-time margin is the synthetic one of
    policies_v4.age_lease_result (tau, g); validity source 'global_lease', no geometric crossing time."""

    def as_validity(self, capture_s):
        out = super().as_validity(capture_s)
        out['source'] = 'global_lease'
        out['tau_star_s'] = None
        return out


def _base_info(agents, prefilter):
    n = len(agents)
    return {'lease_kind': 'global', 'margin_mode': 'global', 'prefilter': bool(prefilter), 'n_relevant': n,
            'n_confident': int(agents.confident.sum()), 'n_low_confidence': int((~agents.confident).sum()),
            'n_computed': 0, 'n_exact_points': 0, 'margin0_m': agents.margin0_m, 'g0_m': agents.g0_m,
            'min_g_m': None, 'binding_index': None, 'binding_group': None, 'binding_moving': None,
            'binding_confident': None, 'binding_margin_m': None, 'binding_tau_s': None, 'envelope': agents.kind}


def global_margin_lease(plan_xy, agents: VL.AgentSet, env: VL.LeaseEnv, params: L2.LeaseParams, prefilter=True):
    """(H, reason, info) of the global-margin lease of one candidate plan against its observation's prepared agents.

    H = min(min_j agent_leases(geom, params, [delta], 'global'), H_bar) on the framelease_v2 LeaseGeometry of the plan
    (exact clearances wherever an agent can bind; see the module docstring)."""
    cfg = env.cfg
    h_bar, delta, d_safe = float(cfg.h_bar_s), float(cfg.delta_m), float(cfg.d_safe_m)
    info = _base_info(agents, prefilter)
    plan = np.asarray(plan_xy, dtype=float)
    if plan.shape != (6, 2) or not np.isfinite(plan).all():
        return 0.0, 'invalid_plan', info
    try:
        E = env.ego_corners(plan)                                            # (M, 4, 2), lease_geometry's E(tau)
    except ValueError:
        return 0.0, 'invalid_plan', info
    if agents.status != 'ok':
        info['invalid_index'] = agents.invalid_index
        if agents.status not in VL.INVALID_REASONS:
            info['error'] = agents.status
        return 0.0, (agents.status if agents.status in VL.INVALID_REASONS else 'perception_unavailable'), info
    N = len(agents)
    if N == 0:
        return h_bar, 'no_relevant_agents', info
    if agents.polys.shape[1] != len(env.tau):
        raise ValueError('prepared agents and lease grid differ')
    groups = agents.group
    sig = np.array([params.sigma_m[g] for g in groups], dtype=float)
    vb = np.array([params.vbar_mps[g] for g in groups], dtype=float)
    ab = np.array([params.abar_mps2[g] for g in groups], dtype=float)
    if prefilter:
        ce = E.mean(axis=1)                                                  # (M, 2) ego box centres
        lb = np.maximum(np.linalg.norm(agents.centers_t - ce[None], axis=-1) - env.ego_radius - agents.r_poly,
                        0.0) - d_safe                                        # (N, M) lower bound of the clearance
        need = sig + delta + vb * h_bar + 0.5 * ab * h_bar * h_bar + PREFILTER_TOL_M
        exact = lb <= need[:, None]
        kidx = np.flatnonzero(exact.any(axis=1))
        if kidx.size == 0:
            return h_bar, 'global_cap', info
        exact = exact[kidx]
        clear = lb[kidx].copy()                                              # placeholders where not exact (> need)
        ki, mi = np.nonzero(exact)
        clear[ki, mi] = convex_distance(E[mi], agents.polys[kidx[ki], mi]) - d_safe
        info['n_exact_points'] = int(ki.size)
    else:
        kidx = np.arange(N)
        clear = convex_distance(E[None], agents.polys) - d_safe             # (N, M), lease_geometry's clearance
        info['n_exact_points'] = int(clear.size)
    info['n_computed'] = int(kidx.size)
    geom = L2.LeaseGeometry(env.tau, clear, agents.idx[kidx], groups[kidx], agents.confident[kidx], 'ok', None, E)
    h_j = np.asarray(L2.agent_leases(geom, params, [delta], 'global')[0], dtype=float)
    H = float(min(float(np.min(h_j)), h_bar))
    if H >= h_bar:
        return h_bar, 'global_cap', info
    m = clear.min(axis=1)
    j = int(np.lexsort((m, h_j))[0])                                         # smallest H_j, ties: smallest margin
    k = int(kidx[j])
    info.update(binding_index=int(agents.idx[k]), binding_group=str(agents.group[k]),
                binding_moving=bool(agents.moving[k]), binding_confident=bool(agents.confident[k]),
                binding_margin_m=float(m[j]), binding_tau_s=float(env.tau[int(np.argmin(clear[j]))]))
    return H, ('global_zero' if H <= 0.0 else 'global_lease'), info


def global_lease_result(plan_xy, agents, env, params, prefilter=True) -> GlobalLeaseResult:
    """global_margin_lease with the synthetic commit-time margin of policies_v4.age_lease_result(env, H, plan)."""
    H, reason, info = global_margin_lease(plan_xy, agents, env, params, prefilter)
    syn = PV.age_lease_result(env, H, plan_xy)
    return GlobalLeaseResult(float(H), syn.tau_star_s, reason, info, syn.tau, syn.g, None, None, syn.t_pred_s)


# ============================================================================================ policy

class GlobalMarginShieldPolicy(S.ShieldedHeuristicPolicy):
    """fl_global_shield: v3 shield + a_det^d with the global-margin lease (E* as B(D), cap H_bar)."""
    name = NAME
    PARAMS = dict(S.ShieldedHeuristicPolicy.PARAMS)          # the same parameters and utilities as fl_heuristic
    PREFILTER = True

    def __init__(self, env=None, **params):
        super().__init__(env, **params)
        self.lease_params = global_lease_params(self.env)
        self.h_bar_s = float(self.env.cfg.h_bar_s)

    def global_lease_spec(self):
        return global_lease_spec(self.env, self.lease_params, self.PREFILTER)

    def describe(self):
        return {**super().describe(), 'title': TITLE,
                'validity': 'global-margin lease (framelease_v2 margin_mode global), E* as B(D), cap H_bar',
                'global_lease': self.global_lease_spec(), 'v4_ext_schema': SCHEMA}

    def compute_lease(self, cand):
        """The global-margin lease of a released candidate against its observation's agents (prepared once per job
        by the inherited after_prefix), with the synthetic commit-time margin. An error gives lease 0 and no margin,
        as the inherited validity() does for the suffix lease, under the global-lease label."""
        try:
            agents = self._agents.get(cand.job_id)
            if agents is None:
                agents = self._prepare(cand.dets)
                self._agents = {cand.job_id: agents}
            return global_lease_result(cand.plan_xy, agents, self.env, self.lease_params, self.PREFILTER)
        except Exception as e:  # noqa: BLE001  fail conservative: lease 0, margin -inf (the commit check fails too)
            return GlobalLeaseResult(0.0, 0.0, f'lease_error:{type(e).__name__}',
                                     {'lease_kind': 'global', 'margin_mode': 'global', 'error': str(e)[:300]},
                                     t_pred_s=float(self.env.cfg.t_pred_s))


__all__ = ['SCHEMA', 'NAME', 'TITLE', 'REASONS', 'PREFILTER_TOL_M', 'H_BAR_S', 'global_lease_params',
           'global_lease_spec', 'GlobalLeaseResult', 'global_margin_lease', 'global_lease_result',
           'GlobalMarginShieldPolicy']
