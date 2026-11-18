"""Table I policies that are new or adapted in v4 (framelease_v4/arms). framelease_v2 / framelease_v3 are imported
read-only; every class here is a subclass, nothing upstream is edited.

AgeLeasePolicy ('age_only', Age-Only)
    The v3 shielded scheduler (framelease_v3.runtime.v3_scheduler.ShieldedHeuristicPolicy: shield Eq. 5, decision
    rule Eq. 8 with a_det, versioned commit Eq. 9, watchdog) with the action-conditioned lease replaced by a constant
    observation-age lease

        H = clip(A, 0, H_bar),   D = t_k + H                      (A = age_lease_s, the threshold; H_bar = 2.5 s)

    for every finite plan (a non-finite plan gets H = 0, as in v3). The lease never looks at the plan geometry or at
    perception, so the scheduler refines while the age budget still leaves room for a refresh and refreshes (or
    recovers) when it does not: refresh is triggered by observation age only. The commit-time margin check of Eq. 9
    uses a synthetic margin g(tau) = delta + (A + T_c - tau) that crosses delta exactly at tau* = A + T_c, so
    M(t_commit - t_k) > delta  <=>  t_commit - t_k < A, i.e. it agrees with t_commit < D (tested). The detections are
    not prepared (no lease geometry), so the per-boundary CPU time charged to the timeline is the Age-Only rule's own.

EventTriggeredV4 ('event_triggered', Event-Triggered)
    framelease_v2.policies.EventTriggered with its rules unchanged: inference is triggered by ego-state events (speed,
    heading, route command from the agent's own sensors) and by a change of the model's own detection set between the
    two most recent prefixes; a running job is preempted at the next quantum boundary on an ego event; without events
    the next job starts when the incumbent reaches the heartbeat age minus the refresh reservation. One parameter is
    added: heartbeat_s (None = the runtime max_age_s, i.e. exactly v2; tested). The trigger of every job start is
    recorded in job.policy_state, and v3-schema decision rows are written (DecisionRowsMixin).

DecisionRowsMixin
    v3-schema decision rows (decisions.jsonl) and summary counters for any v2 (non-shield) policy, so that every arm
    of the matrix logs its boundary decisions in one schema. The v2 rules are not changed; there is no shield, so
    'feasible', 'p_both', 'admitted' and 'shield' are None. Used for Event-Triggered and for the v2 baselines
    (logged_v2_class: Fixed Deep, Fast Only, Original FrameLease).
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np

from framelease_v2 import policies as P
from framelease_v3.runtime import v3_lease as VL
from framelease_v3.runtime import v3_scheduler as S

SCHEMA = 'framelease_v4.arms.policies/1'
END = 'END'                       # decision of a v2 rule that ends the job (no shield, no REFRESH/WAIT distinction yet)
REFINE = 'REFINE'


# ============================================================================================ Age-Only

@dataclass
class AgeLeaseResult(VL.LeaseResult):
    """LeaseResult of the constant-age lease: validity source 'age_lease', no geometric crossing time."""

    def as_validity(self, capture_s):
        out = super().as_validity(capture_s)
        out['source'] = 'age_lease'
        out['tau_star_s'] = None
        return out


def age_lease_result(env: VL.LeaseEnv, age_s, plan_xy):
    """Eq. 1-3 with the constant-age lease H = clip(A, 0, H_bar) (synthetic margin, see the module docstring)."""
    cfg, tau = env.cfg, env.tau
    h_bar, t_c, delta = cfg.h_bar_s, cfg.t_c_s, cfg.delta_m
    info = {'lease_kind': 'age', 'age_lease_s': float(age_s), 'n_relevant': None, 'n_confident': None,
            'n_low_confidence': None, 'n_computed': None, 'margin0_m': None, 'g0_m': None, 'min_g_m': None,
            'binding_index': None, 'binding_group': None, 'binding_moving': None, 'envelope': None}
    plan = np.asarray(plan_xy, dtype=float)
    if plan.shape != (6, 2) or not np.isfinite(plan).all():
        return AgeLeaseResult(0.0, 0.0, 'invalid_plan', info, t_pred_s=cfg.t_pred_s)
    a = float(age_s)
    h = min(max(a, 0.0), h_bar)
    if h >= h_bar:
        g = np.full((1, len(tau)), delta + 10.0)
        return AgeLeaseResult(h_bar, math.inf, 'age_cap', info, tau, g, t_pred_s=cfg.t_pred_s)
    ts = h + t_c
    g = (delta + (ts - tau))[None, :]                         # crosses delta exactly at tau* = H + T_c
    return AgeLeaseResult(h, ts, 'age_lease' if h > 0 else 'age_zero', info, tau, g, t_pred_s=cfg.t_pred_s)


class AgeLeasePolicy(S.ShieldedHeuristicPolicy):
    """Age-Only: v3 shield + a_det with the constant observation-age lease D = t_k + clip(A, 0, H_bar)."""
    name = 'age_only'
    PARAMS = {**S.ShieldedHeuristicPolicy.PARAMS, 'age_lease_s': 2.0}

    def _check(self):
        super()._check()
        a = float(self.params['age_lease_s'])
        if not (math.isfinite(a) and a >= 0):
            raise ValueError('age_only: age_lease_s must be finite and >= 0')

    def describe(self):
        return {**super().describe(), 'title': 'Age-Only', 'validity': 'constant observation-age lease',
                'age_lease_s': float(self.params['age_lease_s']),
                'effective_lease_s': min(max(float(self.params['age_lease_s']), 0.0), self.env.cfg.h_bar_s),
                'v4_schema': SCHEMA}

    def after_prefix(self, job, ctx):
        """The age lease uses neither perception nor plan geometry: nothing to prepare."""
        self._agents = {}
        self._leases = {}

    def compute_lease(self, cand):
        return age_lease_result(self.env, self.params['age_lease_s'], cand.plan_xy)


# ============================================================================================ decision rows for v2 rules

class DecisionRowsMixin:
    """v3-schema decision rows and summary counters for a v2 (non-shield) policy; the v2 rules are unchanged.

    A row is written at every refinement-quantum boundary at which the v2 rule is asked (depth >= min depth and
    < max depth) and, through V4Runtime._end_job, at the max-depth boundary where the runtime ends the job without
    asking the rule. action = REFINE (the rule continued) or END (the job ends). How the next job starts is recorded
    at that start in job.policy_state: start_action BOOTSTRAP | REFRESH (at once, at the previous job's end) |
    REFRESH_AFTER_WAIT (later: the policy idled, or no newer frame existed), start_trigger (the reason the policy's
    idle_start_time gave: 'gpu_free' for work-conserving rules) and start_delay_s. The features are the 32 v3 names
    computed by the v3 function; the shield-only ones (refine / refresh margin, L_commit) are None, the deadline-based
    ones use the policy's own validity (for the non-lease baselines the global max-age deadline).
    Rows are built at the boundary, so their CPU time is charged to the timeline like the v3 policy's features.
    """

    def __init__(self, env=None, **params):
        super().__init__(env, **params)
        self.pending_rows = []
        self.n_decisions = 0
        self.counts = {'actions': Counter(), 'reasons': Counter(), 'start_labels': Counter(),
                       'start_triggers': Counter()}
        self.last_decision = None          # no shield: no expiry is ever "protected" (V3Runtime accounting)
        self.expectation = None            # no shield bound to check against the realized commit time
        self._trigger_reason = None
        self._last_trigger = None

    def describe(self):
        return {**super().describe(), 'decision_rows': 'framelease_v4 DecisionRowsMixin (v3 schema, no shield)'}

    # -- rows
    def _bounds(self, job, ctx):
        prof = ctx.profile
        nxt = min(int(job.depth) + 1, P.MAX_DEPTH)
        return SimpleNamespace(L_pi=float(prof.overhead_bound_s), L_refine=float(prof.step_bound_s(nxt)),
                               L_refresh=float(prof.refresh_bound_s), L_commit=None)

    def _row(self, job, ctx, cont, reason, at_max_depth):
        t = float(ctx.now_s)
        inc = ctx.incumbent
        b = self._bounds(job, ctx)
        sr = SimpleNamespace(D_star=float(inc.deadline_s) if inc is not None else -math.inf,
                             D_cand=float(job.last_deadline_s), refine_lhs=math.nan, refresh_lhs=math.nan)
        feats = S.ShieldedHeuristicPolicy.features(self, job, ctx, sr, b)
        action = REFINE if cont else END
        self.n_decisions += 1
        self.counts['actions'][action] += 1
        self.counts['reasons'][str(reason)] += 1
        self.pending_rows.append({
            'kind': 'decision', 'epoch': self.n_decisions, 'sim_s': t, 'job_id': job.job_id,
            'obs_id': job.obs.obs_id, 'capture_s': job.obs.capture_s, 'depth': job.depth,
            'at_max_depth': bool(at_max_depth),
            'active': None if inc is None else {'job_id': inc.job_id, 'obs_id': inc.obs_id, 'depth': inc.depth},
            'feasible': None, 'p_both': None, 'action': action, 'reason': str(reason), 'admitted': None,
            'shield': None, 'bounds': {'L_pi': b.L_pi, 'L_refine': b.L_refine, 'L_refresh': b.L_refresh},
            'features': feats, 'policy': self.name, 'v4_rows': SCHEMA})

    def continue_refinement(self, job, ctx):
        cont, reason = super().continue_refinement(job, ctx)
        self._row(job, ctx, cont, reason, at_max_depth=False)
        return cont, reason

    def log_end_boundary(self, job, ctx):
        """Max-depth boundary (the runtime ends the job without asking the rule); called by V4Runtime._end_job."""
        self._row(job, ctx, False, 'max_depth', at_max_depth=True)

    # -- job starts
    def idle_start_time(self, ctx):
        self._trigger_reason = None
        start = super().idle_start_time(ctx)
        reason = self._trigger_reason
        if reason is None:
            reason = 'bootstrap' if ctx.last_job is None else ('gpu_free' if self.work_conserving else 'policy_rule')
        self._last_trigger = {'reason': reason, 'query_s': float(ctx.now_s),
                              'start_s': None if start is None else float(start)}
        return start

    def on_job_start(self, job, ctx):
        super().on_job_start(job, ctx)
        last = ctx.last_job
        if last is None:
            label, delay = 'BOOTSTRAP', None
        else:
            delay = float(job.start_s) - float(last.end_s)
            label = 'REFRESH' if delay <= 1e-9 else 'REFRESH_AFTER_WAIT'
        trig = (self._last_trigger or {}).get('reason') or ('bootstrap' if last is None else 'unknown')
        job.policy_state['start_action'] = label
        job.policy_state['start_trigger'] = trig
        job.policy_state['start_delay_s'] = delay
        self.counts['start_labels'][label] += 1
        self.counts['start_triggers'][trig] += 1


# ============================================================================================ Event-Triggered

class EventRules(P.EventTriggered):
    """framelease_v2 EventTriggered with an optional heartbeat (None = runtime max_age_s = v2 exactly)."""
    name = 'event_triggered'
    PARAMS = {**P.EventTriggered.PARAMS, 'heartbeat_s': None}

    def _check(self):
        super()._check()
        h = self.params['heartbeat_s']
        if h is not None and not (math.isfinite(float(h)) and float(h) > 0):
            raise ValueError('event_triggered: heartbeat_s must be None or a positive number')

    def heartbeat_s(self, ctx):
        h = self.params['heartbeat_s']
        return float(ctx.config.max_age_s) if h is None else float(h)

    def describe(self):
        return {**super().describe(), 'title': 'Event-Triggered', 'v4_schema': SCHEMA,
                'heartbeat': 'runtime max_age_s' if self.params['heartbeat_s'] is None else self.params['heartbeat_s']}

    def continue_refinement(self, job, ctx):
        """v2: stop on an ego event; stop when a heartbeat refresh started at the next boundary would be late."""
        reasons = self._ego_event(job.obs, ctx.newest_obs)
        if reasons:
            return False, 'event:' + '+'.join(reasons)
        if self.params['max_age_reservation'] and \
                P.reservation_slack(job.obs.capture_s + self.heartbeat_s(ctx), ctx, job.depth) < 0:
            return False, 'max_age_reservation'
        return True, 'no_event'

    def idle_start_time(self, ctx):
        """v2: start at once after a detection change or on an ego event, else at the heartbeat minus reservation."""
        last = ctx.last_job
        if last is None:
            self._trigger_reason = 'bootstrap'
            return ctx.idle_since_s
        if last.policy_state.get('det_event'):
            self._trigger_reason = 'det_event'
            return ctx.idle_since_s
        reasons = self._ego_event(last.obs, ctx.newest_obs)
        if reasons:
            self._trigger_reason = 'ego_event:' + '+'.join(reasons)
            return ctx.now_s
        base = ctx.incumbent.capture_s if ctx.incumbent is not None else last.obs.capture_s
        cap = base + self.heartbeat_s(ctx) - (ctx.profile.refresh_bound_s + ctx.config.guard_s)
        self._trigger_reason = 'heartbeat'
        return max(ctx.idle_since_s, cap)


class EventTriggeredV4(DecisionRowsMixin, EventRules):
    """Event-Triggered of Table I: v2 rules (+ heartbeat) with v3-schema decision rows and start triggers."""
    name = 'event_triggered'


# ============================================================================================ logged v2 baselines

_LOGGED = {}


def logged_v2_class(name):
    """The v2 policy class `name` with DecisionRowsMixin (rules unchanged, decision rows added)."""
    if name not in P.POLICY_CLASSES:
        raise ValueError(f'unknown v2 policy {name!r}')
    if name not in _LOGGED:
        base = P.POLICY_CLASSES[name]
        _LOGGED[name] = type(f'Logged{base.__name__}', (DecisionRowsMixin, base),
                             {'__module__': __name__,
                              '__doc__': f'framelease_v2 {base.__name__} (rules unchanged) + v3-schema decision rows'})
    return _LOGGED[name]


V4_POLICY_CLASSES = {'age_only': AgeLeasePolicy, 'event_triggered': EventTriggeredV4}

__all__ = ['SCHEMA', 'END', 'REFINE', 'AgeLeaseResult', 'age_lease_result', 'AgeLeasePolicy', 'DecisionRowsMixin',
           'EventRules', 'EventTriggeredV4', 'logged_v2_class', 'V4_POLICY_CLASSES']
