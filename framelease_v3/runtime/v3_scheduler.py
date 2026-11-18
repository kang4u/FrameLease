"""FrameLease v3 scheduler on the framelease_v2 measured-latency timeline.

Two thin layers over unchanged framelease_v2 code:

* ShieldedHeuristicPolicy (a framelease_v2.policies.Policy): suffix lease as the candidate validity (Eq. 1-3,
  v3_lease), the action-specific shield (Eq. 5, v3_shield) and the decision rule (Eq. 8, a_det) at every
  refinement-quantum boundary, plus per-epoch state features for later offline RL.
* V3Runtime (a framelease_v2.latency_agent.LatencyRuntime): versioned commit through CommitGate (Eq. 9, including the
  commit-time margin check), job cancellation on REFRESH, watchdog / deadline-miss / shield-violation / budget-overrun
  accounting, decision and tick logging.

Time charging is v2's, unchanged (LatencyRuntime._start_job / _complete_op / _launch_step / _end_job): a job's prefix
and every flow step run lazily when the simulated timeline reaches them and are charged kappa x their measured CUDA
time; every scheduler boundary is charged its measured CPU time (lease of the released candidate, commit check,
decision; overhead_scale = 1). REFINE = one more step of the running job (the next quantum is launched at
boundary + CPU time), REFRESH = end the job and start the next one at once on the newest frame (prefix + step 1, the
minimum depth), WAIT = the GPU idles until a frame newer than the last processed one exists (v2's latest-frame rule).
FALLBACK is a control mode: v2's control_reference tracks the active candidate while t < D* and applies the logged
full-brake fallback at t >= D* or without a commit (the watchdog). Decision rows are written after the boundary's CPU
time is measured (log I/O is not scheduler time, as in v2).

Baselines (fast_only, fixed_deep, fixed_deep_age2.0, fl_global) are NOT implemented here: build_runtime() returns the
unchanged v2 LatencyRuntime with the unchanged v2 policy objects, and the launcher runs them through the unchanged
v2 launcher and agent.
"""
from __future__ import annotations

import math
import time
from collections import Counter, deque
from typing import Optional

import numpy as np

from framelease_v2 import latency_agent as la
from framelease_v2 import lease as L2
from framelease_v2 import policies as P
from framelease_v3.runtime import v3_commit as VC
from framelease_v3.runtime import v3_lease as VL
from framelease_v3.runtime import v3_shield as VS

SCHEMA = 'framelease_v3.runtime/1'
V3_MODES = ('fl_v3_heuristic',)
FEATURE_NAMES = ('lease_slack_s', 'obs_age_s', 'depth', 'active_age_s', 'active_depth', 'active_lease_s',
                 'active_is_current_obs', 'cand_lease_s', 'cand_slack_s', 'refine_margin_s', 'refresh_margin_s',
                 'L_pi_s', 'L_refine_s', 'L_refresh_s', 'L_commit_s', 'last_step_cost_s', 'last_prefix_cost_s',
                 'ego_speed_mps', 'newest_speed_mps', 'n_relevant', 'n_confident', 'n_computed', 'margin0_m', 'g0_m',
                 'min_g_m', 'tau_star_s', 'newer_frames', 'newest_frame_age_s', 'plan_delta_m', 'in_fallback',
                 'kappa', 'episode_time_s')
START_LABELS = {VS.REFRESH: 'REFRESH', VS.RECOVERY_REFRESH: 'RECOVERY_REFRESH', VS.WAIT: 'REFRESH_AFTER_WAIT'}


def _f(x):
    """Finite float or None (JSON-friendly feature value)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _quantiles(values, qs=(0.5, 0.95, 0.99)):
    return la._quantiles(list(values), qs)


# ============================================================================================ latency profile

def quantile_linear(values, q):
    """numpy.quantile(values, q) (default 'linear' method, numpy 1.23 arithmetic), bit-identical, in pure Python:
    ~10x faster than np.quantile on the <= 256-sample latency windows read at every decision epoch (tested)."""
    xs = sorted(values)
    n = len(xs)
    v = (n - 1) * q
    if v >= n - 1:
        return float(xs[-1])
    if v < 0:
        return float(xs[0])
    p = math.floor(v)
    a, b = xs[p], xs[p + 1]
    g = v - p
    d = b - a
    return float(b - d * (1 - g)) if g >= 0.5 else float(a + d * g)


class CachedLatencyProfile(la.LatencyProfile):
    """framelease_v2's LatencyProfile with identical bounds, computed faster: the quantile is quantile_linear and the
    bound properties are memoized between samples (each add_* call invalidates the keys it affects)."""

    def __init__(self, config):
        super().__init__(config)
        self._memo = {}

    def _q(self, values, prior):
        if len(values) < self.cfg.profile_min_samples:
            return float(prior)
        return quantile_linear(values, self.cfg.profile_quantile)

    def _drop(self, *keys):
        m = self._memo
        for k in keys:
            m.pop(k, None)
        m.pop('refresh', None)

    def add_prefix(self, cost_s):
        super().add_prefix(cost_s)
        self._drop('prefix')

    def add_step(self, depth, cost_s):
        super().add_step(depth, cost_s)
        for k in [k for k in self._memo if isinstance(k, tuple)]:      # depths without own samples use steps_all
            del self._memo[k]
        self._drop()

    def add_overhead(self, s):
        super().add_overhead(s)
        self._drop('overhead')

    def add_preprocess(self, s):
        super().add_preprocess(s)
        self._drop('preprocess')

    def _cached(self, key, fn):
        v = self._memo.get(key)
        if v is None:
            v = self._memo[key] = fn()
        return v

    @property
    def preprocess_bound_s(self):
        return self._cached('preprocess', lambda: la.LatencyProfile.preprocess_bound_s.fget(self))

    @property
    def prefix_bound_s(self):
        return self._cached('prefix', lambda: la.LatencyProfile.prefix_bound_s.fget(self))

    def step_bound_s(self, depth):
        return self._cached(('step', int(depth)), lambda: la.LatencyProfile.step_bound_s(self, depth))

    @property
    def overhead_bound_s(self):
        return self._cached('overhead', lambda: la.LatencyProfile.overhead_bound_s.fget(self))

    @property
    def refresh_bound_s(self):
        return self._cached('refresh', lambda: la.LatencyProfile.refresh_bound_s.fget(self))


# ============================================================================================ policy

class ShieldedHeuristicPolicy(P.Policy):
    """Suffix lease + feasibility shield + a_det (refine while feasible and depth < 10, else refresh)."""
    name = 'fl_v3_heuristic'
    PARAMS = {'eps_s': 0.05, 'max_depth': P.MAX_DEPTH, 'commit_prior_s': 0.005, 'commit_quantile': 0.99,
              'commit_window': 256, 'commit_min_samples': 3, 'utility': 'heuristic'}

    def __init__(self, env: Optional[VL.LeaseEnv] = None, **params):
        super().__init__(env, **params)
        if env is None:
            raise ValueError('fl_v3_heuristic needs a LeaseEnv')
        self.utility = VS.make_utility(self.params['utility'])
        self._agents = {}                    # job_id -> AgentSet (current job only)
        self._leases = {}                    # (job_id, depth) -> LeaseResult (current job only)
        self._validation = deque(maxlen=int(self.params['commit_window']))
        self._commit_bound = None
        self.pending_rows = []
        self._next_start = 'BOOTSTRAP'
        self.last_decision = None
        self.expectation = None
        self.n_decisions = 0
        self.counts = {'actions': Counter(), 'reasons': Counter(), 'feasible': Counter(), 'both': 0,
                       'start_labels': Counter(), 'lease_reasons': Counter()}
        self.decision_wall_s = deque(maxlen=200000)
        self.lease_wall_s = deque(maxlen=200000)
        self.lease_values = deque(maxlen=200000)

    def _check(self):
        super()._check()
        p = self.params
        if not p['eps_s'] >= 0 or not p['commit_prior_s'] >= 0 or not 0 < p['commit_quantile'] <= 1:
            raise ValueError('fl_v3_heuristic: eps_s >= 0, commit_prior_s >= 0, 0 < commit_quantile <= 1')
        if int(p['commit_window']) < 1 or int(p['commit_min_samples']) < 1:
            raise ValueError('fl_v3_heuristic: commit_window >= 1 and commit_min_samples >= 1')
        VS.make_utility(p['utility'])

    @property
    def anytime(self):
        return True

    @property
    def work_conserving(self):
        return True

    def describe(self):
        return {**super().describe(), 'schema': SCHEMA, 'lease_env': self.env.describe(),
                'feature_names': list(FEATURE_NAMES), 'utility': self.utility.name}

    # ------------------------------------------------------------------ v2 hooks
    def on_job_start(self, job, ctx):
        job.target_depth = int(self.params['max_depth'])
        job.policy_state['start_action'] = self._next_start
        self.counts['start_labels'][self._next_start] += 1
        self._next_start = 'REFRESH'

    def _prepare(self, dets):
        try:
            if dets is None:
                return VL.empty_agents(len(self.env.tau), 'perception_unavailable', kind=self.env.envelope.kind)
            return VL.prepare_agents(dets.boxes, dets.scores, dets.labels, self.env, valid=bool(dets.valid))
        except Exception as e:  # noqa: BLE001  a failed preparation never extends validity (lease 0)
            return VL.empty_agents(len(self.env.tau), f'lease_error:{type(e).__name__}:{str(e)[:200]}',
                                   kind=self.env.envelope.kind)

    def after_prefix(self, job, ctx):
        """The observation's detections exist now: propagate / inflate them once for every depth of this job."""
        self._agents = {job.job_id: self._prepare(job.dets)}
        self._leases = {}

    def compute_lease(self, cand):
        """Eq. 1-3 for a released candidate against its observation's prepared agents (VL.LeaseResult)."""
        agents = self._agents.get(cand.job_id)
        if agents is None:
            agents = self._prepare(cand.dets)
            self._agents = {cand.job_id: agents}
        return VL.suffix_lease(cand.plan_xy, agents, self.env)

    def validity(self, cand, ctx):
        t0 = time.perf_counter()
        try:
            res = self.compute_lease(cand)
        except Exception as e:  # noqa: BLE001  fail conservative: lease 0, no margin (commit check fails too)
            res = VL.LeaseResult(0.0, 0.0, f'lease_error:{type(e).__name__}', {'error': str(e)[:300]})
        self._leases[(cand.job_id, cand.depth)] = res
        out = res.as_validity(cand.capture_s)
        if out.get('binding_index') is not None:
            brief = P.detection_brief(cand.dets, out['binding_index'], L2.resolve_groups)
            if brief is not None:
                out['binding_det'] = brief
        wall = time.perf_counter() - t0
        out['lease_wall_s'] = wall
        self.counts['lease_reasons'][res.reason] += 1
        self.lease_values.append(float(res.lease_s))
        self.lease_wall_s.append(wall)
        return out

    def offers(self, job, depth):
        return True

    def continue_refinement(self, job, ctx):
        action, reason = self.decide(job, ctx)
        return action == VS.REFINE, reason

    def idle_start_time(self, ctx):
        return ctx.idle_since_s

    # ------------------------------------------------------------------ commit support (called by V3Runtime)
    def margin_check(self, cand, commit_s):
        """Eq. 9 second line: (M(t_commit - t_k) > delta, M) from the candidate's own lease result."""
        res = self._leases.get((cand.job_id, cand.depth))
        if res is None:
            return False, None
        m = res.margin(float(commit_s) - float(cand.capture_s), self.env.cfg.t_c_s)
        return bool(m > self.env.cfg.delta_m), (m if math.isfinite(m) else None)

    def observe_validation(self, seconds):
        self._validation.append(max(0.0, float(seconds)))
        self._commit_bound = None

    def commit_bound_s(self, ctx):
        """L_commit^bnd: quantile of the measured validation time (release -> commit decision) of past candidates."""
        if len(self._validation) < int(self.params['commit_min_samples']):
            return float(self.params['commit_prior_s']) * float(ctx.config.overhead_scale)
        if self._commit_bound is None:
            self._commit_bound = quantile_linear(self._validation, float(self.params['commit_quantile']))
        return self._commit_bound

    def bounds(self, job, ctx):
        """Shield budgets from the runtime's measured latency profile (RuntimeConfig.profile_quantile, kappa-scaled)."""
        prof = ctx.profile
        nxt = min(int(job.depth) + 1, P.MAX_DEPTH)
        return VS.ShieldBounds(L_pi=float(prof.overhead_bound_s), L_refine=float(prof.step_bound_s(nxt)),
                               L_refresh=float(prof.refresh_bound_s), L_commit=self.commit_bound_s(ctx),
                               eps=float(self.params['eps_s']))

    # ------------------------------------------------------------------ decision epoch
    def features(self, job, ctx, sr, b):
        t = float(ctx.now_s)
        inc = ctx.incumbent
        v = job.last_validity or {}
        newest = ctx.newest_obs
        steps = job.steps
        plan_delta = None
        if len(steps) >= 2 and steps[-1].get('plan') is not None and steps[-2].get('plan') is not None:
            plan_delta = float(np.max(np.abs(np.asarray(steps[-1]['plan'], float) - np.asarray(steps[-2]['plan'], float))))
        last_step = steps[-1]['timeline_cost_s'] if steps else None
        in_fallback = inc is None or not t < float(inc.deadline_s)
        vals = {
            'lease_slack_s': _f(sr.D_star - t), 'obs_age_s': t - float(job.obs.capture_s), 'depth': int(job.depth),
            'active_age_s': _f(t - inc.capture_s) if inc is not None else None,
            'active_depth': int(inc.depth) if inc is not None else None,
            'active_lease_s': _f(inc.validity.get('lease_s')) if inc is not None else None,
            'active_is_current_obs': int(inc is not None and inc.obs_id == job.obs.obs_id),
            'cand_lease_s': _f(v.get('lease_s')), 'cand_slack_s': _f(sr.D_cand - t),
            'refine_margin_s': _f(sr.D_star - sr.refine_lhs), 'refresh_margin_s': _f(sr.D_star - sr.refresh_lhs),
            'L_pi_s': b.L_pi, 'L_refine_s': b.L_refine, 'L_refresh_s': b.L_refresh, 'L_commit_s': b.L_commit,
            'last_step_cost_s': _f(last_step), 'last_prefix_cost_s': _f(job.prefix.get('timeline_cost_s')),
            'ego_speed_mps': _f(job.obs.speed_mps), 'newest_speed_mps': _f(newest.speed_mps) if newest else None,
            'n_relevant': v.get('n_relevant'), 'n_confident': v.get('n_confident'), 'n_computed': v.get('n_computed'),
            'margin0_m': _f(v.get('margin0_m')), 'g0_m': _f(v.get('g0_m')), 'min_g_m': _f(v.get('min_g_m')),
            'tau_star_s': _f(v.get('tau_star_s')),
            'newer_frames': int(newest.obs_id - job.obs.obs_id) if newest is not None else 0,
            'newest_frame_age_s': _f(t - newest.capture_s) if newest is not None else None,
            'plan_delta_m': plan_delta, 'in_fallback': int(in_fallback), 'kappa': float(ctx.config.kappa),
            'episode_time_s': _f(t - ctx.episode_start_s)}
        return {k: vals[k] for k in FEATURE_NAMES}

    def decide(self, job, ctx, at_max_depth=False):
        """Shield + Eq. 8 at boundary ctx.now_s of `job` (depth >= 1). Returns (action, reason)."""
        t0 = time.perf_counter()
        t = float(ctx.now_s)
        inc = ctx.incumbent
        D_star = float(inc.deadline_s) if inc is not None else -math.inf
        newest = ctx.newest_obs
        newer = newest is not None and newest.obs_id > job.obs.obs_id
        b = self.bounds(job, ctx)
        d_max = min(int(self.params['max_depth']), int(ctx.config.max_depth))
        sr = VS.shield(t, D_star, job.last_deadline_s, job.depth, d_max, newer, b)
        feats = self.features(job, ctx, sr, b)
        action, reason = VS.decide(sr, self.utility, feats)
        wall = time.perf_counter() - t0
        admitted = action in sr.feasible
        if action != VS.REFINE:
            self._next_start = START_LABELS[action]
        if action == VS.REFINE:
            self.expectation = {'action': action, 'job_id': job.job_id, 'depth': job.depth + 1,
                                'bound_s': t + b.L_pi + b.L_refine + b.L_commit, 'decided_s': t}
        elif action in (VS.REFRESH, VS.RECOVERY_REFRESH):
            self.expectation = {'action': action, 'after_job': job.job_id, 'depth': 1,
                                'bound_s': t + b.L_pi + b.L_refresh + b.L_commit, 'decided_s': t}
        else:
            self.expectation = None
        self.n_decisions += 1
        self.counts['actions'][action] += 1
        self.counts['reasons'][reason] += 1
        self.counts['feasible']['+'.join(sr.feasible) or 'none'] += 1
        self.counts['both'] += int(sr.both)
        self.decision_wall_s.append(wall)
        self.last_decision = {'epoch': self.n_decisions, 't': t, 'action': action, 'admitted': admitted,
                              'D_star': D_star, 'active': None if inc is None else (inc.obs_id, inc.depth),
                              'job_id': job.job_id, 'depth': job.depth}
        self.pending_rows.append({
            'kind': 'decision', 'epoch': self.n_decisions, 'sim_s': t, 'job_id': job.job_id, 'obs_id': job.obs.obs_id,
            'capture_s': job.obs.capture_s, 'depth': job.depth, 'at_max_depth': bool(at_max_depth),
            'active': None if inc is None else {'job_id': inc.job_id, 'obs_id': inc.obs_id, 'depth': inc.depth},
            'feasible': list(sr.feasible), 'p_both': bool(sr.both), 'action': action, 'reason': reason,
            'admitted': admitted, 'shield': sr.as_dict(), 'bounds': b.as_dict(), 'features': feats,
            'decision_wall_s': wall})
        return action, reason


# ============================================================================================ runtime

class V3Runtime(la.LatencyRuntime):
    """v2 timeline + CommitGate (Eq. 9) + watchdog accounting + v3 logging."""

    def __init__(self, backend, policy, config, logger=None, timer=time.perf_counter):
        super().__init__(backend, policy, config, logger, timer)
        if not self.config.versioned_commit:
            raise ValueError('the v3 runtime always uses the versioned commit')
        self.profile = CachedLatencyProfile(self.config)
        self.gate = VC.CommitGate()
        self.v3 = {'candidates': 0, 'validation_s': [], 'budget_checked': 0, 'budget_overruns': 0, 'overrun_s': [],
                   'shield_violations': 0, 'unprotected_expiries': 0, 'expiry_episodes': 0, 'first_commit_s': None,
                   'ticks_after_first_commit': 0, 'expired_ticks_after_first_commit': 0, 'cancelled_offers': 0,
                   'margin_rejects': 0, 'decision_overhead_s': []}
        self._prev_reason = None

    # ------------------------------------------------------------------ events
    def _complete_op(self, job):
        try:
            super()._complete_op(job)
        finally:
            self._flush_decisions()

    def _flush_decisions(self):
        rows = getattr(self.policy, 'pending_rows', None)
        if rows:
            for r in rows:
                self.logger.write('decisions', r)
            rows.clear()

    def _end_job(self, job, t_end, reason):
        """Close the job: every later completion of it is cancelled. At depth 10 v2 ends the job without asking the
        policy; the v3 decision epoch (REFINE infeasible) is still evaluated and logged and its CPU time is charged."""
        if reason == 'max_depth' and job.phase == 'step' and hasattr(self.policy, 'decide'):
            t0 = self.timer()
            b = job.steps[-1].get('release_s', job.busy_until_s)
            self.policy.decide(job, self._ctx(b, job), at_max_depth=True)
            extra = self._overhead(t0)
            if isinstance(job.steps[-1].get('decision'), dict):
                job.steps[-1]['decision']['v3_decision_overhead_s'] = extra
            self.v3['decision_overhead_s'].append(extra)
            t_end = t_end + extra
        super()._end_job(job, t_end, reason)
        self.gate.close_job(job.job_id)

    def _expectation_check(self, job, cand, commit_s):
        exp = getattr(self.policy, 'expectation', None)
        if not exp:
            return None
        if exp['action'] == VS.REFINE:
            match = exp['job_id'] == job.job_id and exp['depth'] == cand.depth
        else:
            match = job.job_id > exp['after_job'] and cand.depth == 1
        if not match:
            return None
        self.policy.expectation = None
        over = float(commit_s) - float(exp['bound_s'])
        self.v3['budget_checked'] += 1
        if over > 1e-9:
            self.v3['budget_overruns'] += 1
            self.v3['overrun_s'].append(over)
        return {'action': exp['action'], 'bound_s': exp['bound_s'], 'over_s': over, 'overrun': over > 1e-9}

    def _try_commit(self, job, cand, commit_s, rec):
        """Eq. 9 at commit_s: not cancelled, valid plan, admissible version, t_commit < D, M(t_commit - t_k) > delta."""
        latest = self.latest_committed()
        want = None if latest is None else VC.Version(latest.obs_id, latest.depth)
        if self.gate.latest != want:
            raise RuntimeError(f'commit gate out of sync with the runtime ({self.gate.latest} != {want})')
        kin_ok, kin_why, kin_stats = la.kinematic_check(cand.plan_xy, self.config.max_speed_mps,
                                                        self.config.max_accel_mps2)
        if hasattr(self.policy, 'margin_check'):
            m_ok, m_val = self.policy.margin_check(cand, commit_s)
        else:
            m_ok, m_val = True, None
        ok, reason = self.gate.offer(job.job_id, VC.Version(cand.obs_id, cand.depth), cand.deadline_s, commit_s,
                                     (kin_ok, kin_why), m_ok)
        validation = float(commit_s) - float(cand.release_s)
        if hasattr(self.policy, 'observe_validation'):
            self.policy.observe_validation(validation)
        self.v3['candidates'] += 1
        self.v3['validation_s'].append(validation)
        self.v3['cancelled_offers'] += int(reason == 'cancelled')
        self.v3['margin_rejects'] += int(reason == 'margin_violated_at_commit')
        budget = self._expectation_check(job, cand, commit_s)
        details = {'kinematic': kin_stats, 'commit_s': commit_s, 'deadline_s': cand.deadline_s,
                   'margin_at_commit_m': m_val}
        rec['commit'] = {'accepted': ok, 'reason': reason, 'commit_s': commit_s, 'overridden': False,
                         'margin_at_commit_m': m_val, 'budget': budget}
        if ok:
            cand.commit_s = commit_s
            self._commits.append(cand)
            del self._commits[:-8]
            job.committed_depths.append(cand.depth)
            self.stats['commits'] += 1
            self.stats['committed_depths'][cand.depth] += 1
            if self.v3['first_commit_s'] is None:
                self.v3['first_commit_s'] = float(commit_s)
            return ('commit', commit_s, {**cand.brief(), 'replaced': latest.brief() if latest else None,
                                         'would_reject': None, 'margin_at_commit_m': m_val, 'budget': budget})
        self.stats['rejects'][reason] += 1
        return ('reject', commit_s, {**cand.brief(), 'reason': reason, 'details': details,
                                     'incumbent': latest.brief() if latest else None, 'budget': budget})

    # ------------------------------------------------------------------ control (watchdog)
    def control_reference(self, now_s, obs_now):
        """Watchdog: the active candidate (newest commit with commit_s <= now) is tracked while now < D*; at
        now >= D* (strict expiry) or without any commit the logged fallback (full brake) applies until a newer valid
        candidate is committed. This is v2's control_reference; v3 only annotates it."""
        ref = super().control_reference(now_s, obs_now)
        inc = ref.get('incumbent')
        ref['watchdog'] = {'D_star': float(inc.deadline_s) if inc is not None else None,
                           'fallback': ref['mode'] != 'track', 'reason': ref.get('reason')}
        return ref

    def record_tick(self, now_s, ref, control=None, extra=None):
        inc = ref.get('incumbent')
        fallback = ref['mode'] != 'track'
        reason = ref.get('reason') if fallback else None
        v = self.v3
        if v['first_commit_s'] is not None and now_s + la.EPS_S >= v['first_commit_s']:
            v['ticks_after_first_commit'] += 1
            v['expired_ticks_after_first_commit'] += int(reason == 'expired')
        if reason == 'expired' and self._prev_reason != 'expired':
            v['expiry_episodes'] += 1
            d = getattr(self.policy, 'last_decision', None)
            protected = bool(d and d['admitted'] and inc is not None and d['active'] == (inc.obs_id, inc.depth)
                             and abs(d['D_star'] - float(inc.deadline_s)) < 1e-9)
            if protected:
                v['shield_violations'] += 1
                self.logger.event('shield_violation', now_s, incumbent=inc.brief(), last_decision=d)
            else:
                v['unprotected_expiries'] += 1
        self._prev_reason = reason
        x = dict(extra or {})
        x['v3'] = {'active': None if inc is None else {'job_id': inc.job_id, 'obs_id': inc.obs_id, 'depth': inc.depth,
                                                       'capture_s': inc.capture_s},
                   'age_s': None if inc is None else now_s - inc.capture_s,
                   'D_star': None if inc is None else inc.deadline_s,
                   'slack_s': None if inc is None else inc.deadline_s - now_s,
                   'fallback': fallback, 'watchdog': reason}
        return super().record_tick(now_s, ref, control, x)

    # ------------------------------------------------------------------ summary
    def summary(self):
        s = super().summary()
        p = self.policy
        v = self.v3
        n = getattr(p, 'n_decisions', 0)
        cand = v['candidates']
        expired = s['rejects'].get('expired_before_commit', 0)
        s['v3'] = {
            'schema': SCHEMA, 'decisions': n, 'p_both': (p.counts['both'] / n) if n else None,
            'actions': dict(p.counts['actions']), 'reasons': dict(p.counts['reasons']),
            'feasible_sets': dict(p.counts['feasible']), 'start_labels': dict(p.counts['start_labels']),
            'lease_reasons': dict(p.counts['lease_reasons']), 'lease_s': _quantiles(p.lease_values),
            'lease_wall_s': _quantiles(p.lease_wall_s), 'decision_wall_s': _quantiles(p.decision_wall_s),
            'max_depth_decision_overhead_s': _quantiles(v['decision_overhead_s']),
            'validation_s': _quantiles(v['validation_s']), 'candidates': cand,
            'candidate_expired_ratio': (expired / cand) if cand else None, 'commit_gate': dict(self.gate.counts),
            'cancelled_offers': v['cancelled_offers'], 'margin_rejects': v['margin_rejects'],
            'budget_checked': v['budget_checked'], 'budget_overruns': v['budget_overruns'],
            'budget_overrun_ratio': (v['budget_overruns'] / v['budget_checked']) if v['budget_checked'] else None,
            'overrun_s': _quantiles(v['overrun_s']), 'expiry_episodes': v['expiry_episodes'],
            'shield_violations': v['shield_violations'], 'unprotected_expiries': v['unprotected_expiries'],
            'first_commit_s': v['first_commit_s'], 'ticks_after_first_commit': v['ticks_after_first_commit'],
            'deadline_miss_tick_ratio': (v['expired_ticks_after_first_commit'] / v['ticks_after_first_commit'])
            if v['ticks_after_first_commit'] else None}
        return s


# ============================================================================================ factories

def v3_block_defaults():
    return {'schema': SCHEMA, 'policy': 'fl_v3_heuristic', 'policy_params': {}, 'lease': {},
            'lease_params_path': None, 'envelope_path': None, 'envelope_sha256': None}


def make_v3_policy(v3: dict):
    """ShieldedHeuristicPolicy from the 'v3' block of the agent configuration."""
    v3 = {**v3_block_defaults(), **(v3 or {})}
    if v3['policy'] not in V3_MODES:
        raise ValueError(f'unknown v3 policy {v3["policy"]!r}')
    env = VL.build_lease_env(v3['lease_params_path'], v3.get('envelope_path'), v3.get('lease'),
                             envelope_spec=v3.get('envelope_spec'))
    want = v3.get('envelope_sha256')
    if want and env.envelope.sha256 != want:
        raise ValueError(f'envelope file changed: sha256 {env.envelope.sha256} != pinned {want}')
    return ShieldedHeuristicPolicy(env=env, **(v3.get('policy_params') or {}))


def build_runtime(mode, backend, runtime_config, logger=None, policy_params=None, lease_params_path=None, v3=None,
                  timer=time.perf_counter):
    """The runtime + policy an arm runs with. v2 modes: exactly the objects framelease_v2's agent setup() builds."""
    if mode in P.POLICY_NAMES:
        env = P.default_policy_env(lease_params_path)
        policy = P.make_policy(mode, policy_params, env)
        return la.LatencyRuntime(backend, policy, runtime_config, logger, timer=timer)
    if mode in V3_MODES:
        return V3Runtime(backend, make_v3_policy(v3), runtime_config, logger, timer=timer)
    raise ValueError(f'unknown mode {mode!r}')


__all__ = ['SCHEMA', 'V3_MODES', 'FEATURE_NAMES', 'quantile_linear', 'CachedLatencyProfile', 'ShieldedHeuristicPolicy', 'V3Runtime',
           'make_v3_policy', 'build_runtime', 'v3_block_defaults']
