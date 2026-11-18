"""V4Runtime: the ONE runtime class every Table I arm runs on (framelease_v4/arms).

V4Runtime = framelease_v3.runtime.v3_scheduler.V3Runtime (itself framelease_v2's measured-latency LatencyRuntime + the
v3 versioned-commit gate (Eq. 9), job cancellation, watchdog / deadline-miss / shield-violation accounting and decision
logging), extended only where V3Runtime assumes a shield policy:

* summary(): V3Runtime.summary() for shield policies (FrameLease + Heuristic, Full FrameLease, Age-Only); for the v2
  rules (Fixed Deep, Fast Only, Event-Triggered, Original FrameLease) the LatencyRuntime summary plus the same 'v3'
  accounting block without the shield-only entries (p_both None). Every arm gets the same 'v4' block (below).
* _end_job(): the max-depth boundary of a v2 rule (the runtime ends the job without asking the rule) is written as a
  decision row by DecisionRowsMixin.log_end_boundary; nothing is charged to the timeline (the v2 rule takes no
  decision there). Shield policies keep V3Runtime's own at-max-depth decision epoch.
* record_tick(): also counts the ticks without a valid committed action after the first commit.

Nothing else changes: time charging (prefix / flow steps at kappa x measured CUDA time, measured scheduler CPU time at
every boundary), the latest-frame rule, commit, strict expiry and the logged full-brake fallback are v2 / v3 code. For
a v2 rule the gate decides exactly like v2's versioned_commit_check (nothing is ever cancelled at a release: the job
is still open), so a v2 policy produces the same timeline on V4Runtime as on LatencyRuntime (tested).

The 'v4' summary block (identical definitions for every arm; metrics_v4.py recomputes them from the logs):
  gpu_usage                  GPU-busy simulated seconds / simulated seconds of the run (busy = the cost-model
                             intervals of prefixes and flow steps inside [first tick, last tick + 0.05 s])
  deadline_miss_ratio        ticks without a valid committed action (fallback: no plan yet, expired, re-anchoring
                             failed) / all control ticks
  deadline_miss_ratio_after_first_commit   the same over the ticks from the first commit on
  expired_ratio_after_first_commit         expired ticks only (v3's deadline_miss_tick_ratio)
  action_age_s               age of the tracked action (now - capture of its observation) over the tracked ticks
  fallback_episodes          number of fallback triggers (entries into fallback)
  p_both                     share of shield decision epochs with |A_feas| = 2 (None for the v2 rules)
"""
from __future__ import annotations

import time

from framelease_v2 import latency_agent as la
from framelease_v3.runtime import v3_scheduler as S

SCHEMA = 'framelease_v4.arms.runtime/1'


def is_shield_policy(policy):
    return isinstance(policy, S.ShieldedHeuristicPolicy)


def _ratio(num, den):
    return (float(num) / float(den)) if den else None


class V4Runtime(S.V3Runtime):
    """V3Runtime for every policy kind (shield or v2 rule) with a uniform summary."""

    def __init__(self, backend, policy, config, logger=None, timer=time.perf_counter):
        super().__init__(backend, policy, config, logger, timer)
        self.v4 = {'fallback_ticks_after_first_commit': 0, 'end_boundary_rows': 0}

    # ------------------------------------------------------------------ events
    def _end_job(self, job, t_end, reason):
        if (reason == 'max_depth' and job.phase == 'step' and not hasattr(self.policy, 'decide')
                and hasattr(self.policy, 'log_end_boundary')):
            b = job.steps[-1].get('release_s', job.busy_until_s)
            self.policy.log_end_boundary(job, self._ctx(b, job))
            self.v4['end_boundary_rows'] += 1
        super()._end_job(job, t_end, reason)

    def record_tick(self, now_s, ref, control=None, extra=None):
        fc = self.v3['first_commit_s']
        if fc is not None and now_s + la.EPS_S >= fc and ref['mode'] != 'track':
            self.v4['fallback_ticks_after_first_commit'] += 1
        return super().record_tick(now_s, ref, control, extra)

    # ------------------------------------------------------------------ summary
    def _common_v3_block(self, s):
        """V3Runtime's accounting block for a v2 rule (no shield: p_both, feasible sets and lease stats are None)."""
        p = self.policy
        v = self.v3
        counts = getattr(p, 'counts', None) or {}
        cand = v['candidates']
        expired = s['rejects'].get('expired_before_commit', 0)
        return {
            'schema': S.SCHEMA, 'policy_kind': 'v2_rule', 'decisions': getattr(p, 'n_decisions', None),
            'p_both': None, 'actions': dict(counts.get('actions', {})), 'reasons': dict(counts.get('reasons', {})),
            'feasible_sets': None, 'start_labels': dict(counts.get('start_labels', {})),
            'start_triggers': dict(counts.get('start_triggers', {})),
            'validation_s': S._quantiles(v['validation_s']), 'candidates': cand,
            'candidate_expired_ratio': _ratio(expired, cand), 'commit_gate': dict(self.gate.counts),
            'cancelled_offers': v['cancelled_offers'], 'margin_rejects': v['margin_rejects'],
            'budget_checked': v['budget_checked'], 'budget_overruns': v['budget_overruns'],
            'budget_overrun_ratio': _ratio(v['budget_overruns'], v['budget_checked']),
            'overrun_s': S._quantiles(v['overrun_s']), 'expiry_episodes': v['expiry_episodes'],
            'shield_violations': v['shield_violations'], 'unprotected_expiries': v['unprotected_expiries'],
            'first_commit_s': v['first_commit_s'], 'ticks_after_first_commit': v['ticks_after_first_commit'],
            'deadline_miss_tick_ratio': _ratio(v['expired_ticks_after_first_commit'], v['ticks_after_first_commit'])}

    def _v4_block(self, s):
        v3 = s['v3']
        ticks = s['ticks']
        fallback = sum(int(x) for x in (s.get('fallback_ticks') or {}).values())
        return {
            'schema': SCHEMA, 'runtime_class': type(self).__name__,
            'policy_kind': 'shield' if is_shield_policy(self.policy) else 'v2_rule',
            'policy_name': getattr(self.policy, 'name', None),
            'gpu_usage': s.get('gpu_busy_ratio'), 'gpu_busy_in_span_s': s.get('gpu_busy_in_span_s'),
            'sim_span_s': s.get('sim_span_s'), 'ticks': ticks, 'fallback_ticks_total': fallback,
            'deadline_miss_ratio': _ratio(fallback, ticks),
            'deadline_miss_ratio_after_first_commit': _ratio(self.v4['fallback_ticks_after_first_commit'],
                                                             self.v3['ticks_after_first_commit']),
            'expired_ratio_after_first_commit': v3.get('deadline_miss_tick_ratio'),
            'fallback_episodes': s.get('fallback_episodes'), 'fallback_ticks': s.get('fallback_ticks'),
            'action_age_s': s.get('action_age_s'), 'p_both': v3.get('p_both'), 'decisions': v3.get('decisions'),
            'end_boundary_rows': self.v4['end_boundary_rows'],
            'definitions': {
                'gpu_usage': 'GPU-busy simulated s (prefix + flow-step cost-model intervals) / simulated s',
                'deadline_miss_ratio': 'ticks without a valid committed action / ticks',
                'action_age_s': 'now - capture time of the tracked action, tracked ticks only',
                'p_both': 'shield decision epochs with |A_feas| = 2 / shield decision epochs'}}

    def summary(self):
        if is_shield_policy(self.policy):
            s = super().summary()
        else:
            s = la.LatencyRuntime.summary(self)
            s['v3'] = self._common_v3_block(s)
        s['v4'] = self._v4_block(s)
        return s


__all__ = ['SCHEMA', 'V4Runtime', 'is_shield_policy']
