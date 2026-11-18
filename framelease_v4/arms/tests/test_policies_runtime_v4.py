"""CPU tests of the v4 policies and the common runtime (fake model, fake clock; no GPU, no CARLA).

    cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
        framelease_v4/arms/tests

What is shown:
  * Age-Only: the constant-age lease and its commit-time margin agree (M(Delta) > delta <=> Delta < A); the shield
    (Eq. 5) and a_det decide from the age lease exactly as recomputed from the logged bounds; refine-to-10 for a long
    age budget, refresh at depth 1 for a short one, expiry + recovery below the release latency; no perception used.
  * Event-Triggered: with heartbeat None the v4 rules equal framelease_v2's EventTriggered bit for bit (every log
    stream, several event scenarios); the heartbeat moves the no-event refresh; job-start triggers are recorded.
  * DecisionRowsMixin leaves every v2 rule's timeline unchanged and writes v3-schema rows.
  * V4Runtime reproduces framelease_v2's LatencyRuntime for every v2 rule (jobs, ticks, commits, rejects), also with
    a stepping scheduler clock (charged CPU time), and its summary has the same accounting for every policy kind.
  * Timing accounting: GPU usage, deadline-miss ratio and action age of the summary equal values recomputed from the
    log streams and, in a constructed timeline, the analytic values.
"""
from __future__ import annotations

import math
import unittest

import numpy as np

from helpers_v4 import (DT, TOL, FakeBackend, SteppingTimer, config, dets_with, events, job_projection, lease_env,
                        make_obs, rows, simulate, straight_plan, stub_env, tick_projection)

from framelease_v2 import latency_agent as la
from framelease_v2 import policies as P
from framelease_v3.runtime import v3_scheduler as S
from framelease_v3.runtime import v3_shield as VS
from framelease_v4.arms import metrics_v4 as MV
from framelease_v4.arms import policies_v4 as PV
from framelease_v4.arms import runtime_v4 as RV


def v4rt(policy, backend=None, cfg=None, timer=None):
    return RV.V4Runtime(backend or FakeBackend(), policy, cfg or config(), la.MemoryLogger(),
                        timer=timer or (lambda: 0.0))


def v2rt(policy, backend=None, cfg=None, timer=None):
    return la.LatencyRuntime(backend or FakeBackend(), policy, cfg or config(), la.MemoryLogger(),
                             timer=timer or (lambda: 0.0))


def age_policy(A, **kw):
    return PV.AgeLeasePolicy(env=lease_env(), age_lease_s=A, **kw)


class AgeLeaseTest(unittest.TestCase):
    def test_lease_value_and_margin_agree(self):
        env = lease_env()
        plan = straight_plan(None, 1)
        rng = np.random.default_rng(0)
        for A in list(rng.uniform(0.0, 3.5, 40)) + [0.0, 0.5, 2.5, 3.0]:
            res = PV.age_lease_result(env, A, plan)
            H = min(max(A, 0.0), env.cfg.h_bar_s)
            self.assertAlmostEqual(res.lease_s, H, delta=1e-12)
            v = res.as_validity(10.0)
            self.assertEqual((v['source'], v['tau_star_s']), ('age_lease', None))
            self.assertAlmostEqual(v['deadline_s'], 10.0 + H, delta=1e-12)
            for age in rng.uniform(0.0, 2.6, 30):
                if age + env.cfg.t_c_s > env.cfg.t_pred_s:
                    continue
                m = res.margin(age, env.cfg.t_c_s)
                self.assertEqual(m > env.cfg.delta_m, age < H - 1e-9 or (H >= env.cfg.h_bar_s and age < H),
                                 (A, age, m))
        bad = PV.age_lease_result(env, 2.0, np.full((6, 2), np.nan))
        self.assertEqual((bad.lease_s, bad.reason), (0.0, 'invalid_plan'))
        self.assertEqual(bad.margin(0.0, 0.5), -math.inf)

    def test_parameters(self):
        with self.assertRaises(ValueError):
            age_policy(-1.0)
        with self.assertRaises(ValueError):
            age_policy(float('nan'))
        p = age_policy(1.5)
        d = p.describe()
        self.assertEqual((d['name'], d['title'], d['age_lease_s']), ('age_only', 'Age-Only', 1.5))
        self.assertIsInstance(p, S.ShieldedHeuristicPolicy)

    def test_long_budget_refines_to_10_then_refreshes(self):
        rt = v4rt(age_policy(2.5), cfg=config(max_age_s=2.5))
        simulate(rt, 80)
        j1 = rows(rt, 'jobs')[0]
        self.assertEqual((j1['final_depth'], j1['stop_reason']), (10, 'max_depth'))
        self.assertEqual(j1['committed_depths'], list(range(1, 11)))
        d = [r for r in rows(rt, 'decisions') if r['job_id'] == 1]
        self.assertEqual([r['action'] for r in d], [VS.REFINE] * 9 + [VS.REFRESH])
        commit = events(rt, 'commit')[0]
        self.assertEqual(commit['validity_source'], 'age_lease')
        self.assertAlmostEqual(commit['deadline_s'] - commit['capture_s'], 2.5, delta=TOL)

    def test_shield_recomputed_from_logged_bounds(self):
        for A in (2.0, 1.2, 1.0, 0.7):
            rt = v4rt(age_policy(A), cfg=config(max_age_s=2.5))
            simulate(rt, 90)
            for r in rows(rt, 'decisions'):
                b, sh, t = r['bounds'], r['shield'], r['sim_s']
                refine_lhs = t + b['L_pi'] + b['L_refine'] + b['L_commit'] + (b['L_refresh'] + b['L_commit']) + b['eps']
                refresh_lhs = t + b['L_pi'] + b['L_refresh'] + b['L_commit'] + b['eps']
                D = sh['D_star'] if sh['D_star'] is not None else -math.inf
                refine_ok = r['depth'] < 10 and refine_lhs < D and sh['refine_cand_lhs'] < sh['D_cand']
                refresh_ok = sh['newer_frame'] and refresh_lhs < D
                want = VS.REFINE if refine_ok else (VS.REFRESH if refresh_ok else (
                    VS.RECOVERY_REFRESH if sh['newer_frame'] else VS.WAIT))
                self.assertEqual(r['action'], want, (A, r['sim_s']))
                if sh['D_cand'] is not None:              # the candidate deadline is capture + A (capped)
                    self.assertAlmostEqual(sh['D_cand'] - r['capture_s'], min(A, 2.5), delta=TOL)

    def test_short_budget_refreshes_and_expiry_falls_back(self):
        rt = v4rt(age_policy(1.0), cfg=config(max_age_s=2.5))
        simulate(rt, 120)
        depths = [j['final_depth'] for j in rows(rt, 'jobs')]
        self.assertTrue(all(d <= 2 for d in depths))
        self.assertEqual(rt.summary()['v4']['deadline_miss_ratio_after_first_commit'], 0.0)
        rt = v4rt(age_policy(0.4), cfg=config(max_age_s=2.5))        # A < release latency 0.465 s: never valid
        simulate(rt, 60)
        self.assertEqual(rt.stats['commits'], 0)
        self.assertTrue(all(t['fallback_reason'] == 'no_plan' for t in rows(rt, 'ticks')))
        rt = v4rt(age_policy(0.6), cfg=config(max_age_s=2.5))        # valid 0.6 s, refreshed every ~0.47 s
        simulate(rt, 120)
        s = rt.summary()['v4']
        self.assertGreater(s['deadline_miss_ratio_after_first_commit'], 0.5)
        ages = [t['sim_s'] - t['incumbent']['capture_s'] for t in rows(rt, 'ticks') if t['mode'] == 'track']
        self.assertTrue(ages and max(ages) < 0.6 + 1e-9)               # strict expiry at age A

    def test_no_perception_is_prepared(self):
        calls = []

        def dets_fn(obs):
            calls.append(obs.obs_id)
            return dets_with(obs, [[0.0, 3.0, 4.5, 1.9, math.pi / 2, 0.0, 0.0]])
        pol = age_policy(2.0)
        rt = v4rt(pol, FakeBackend(dets_fn=dets_fn), cfg=config(max_age_s=2.5))
        simulate(rt, 40)
        self.assertTrue(calls)                                          # the model still produced detections
        self.assertEqual(pol._agents, {})                               # ... the age lease never used them
        lease = {e['lease_s'] for e in events(rt, 'commit')}
        self.assertEqual(lease, {2.0})                                  # a car 3 m ahead does not shorten it


class EventTriggeredTest(unittest.TestCase):
    SCENARIOS = {
        'idle': (lambda k: make_obs(k), None),
        'ego_idle': (lambda k: make_obs(k, speed=5.0 if k < 30 else 7.0), None),
        'ego_preempt': (lambda k: make_obs(k, speed=5.0 if k < 19 else 7.0), None),
        'yaw': (lambda k: make_obs(k, yaw=math.pi / 2 + (0.0 if k < 45 else 0.3)), None),
        'command': (lambda k: make_obs(k, command=4 if k < 55 else 2), None),
        'det_change': (lambda k: make_obs(k), lambda obs: dets_with(obs, [[0.0, 20.0, 4.5, 1.9, math.pi / 2, 0, 0]]
                                                                   if obs.obs_id < 30 else
                                                                   [[3.5, 10.0, 4.5, 1.9, 0.0, 0.0, 0.0]])),
        'moving_dets': (lambda k: make_obs(k, moving=True),
                        lambda obs: dets_with(obs, [[0.0, 15.0 - 0.1 * obs.obs_id, 4.5, 1.9, math.pi / 2, 0, 0]])),
    }

    def run_pair(self, scenario, n=140, timer=None):
        obs_fn, dets_fn = self.SCENARIOS[scenario]
        cfg = config(max_age_s=3.0)
        ref = v2rt(P.EventTriggered(env=stub_env()), FakeBackend(dets_fn=dets_fn), cfg,
                   timer=timer() if timer else None)
        simulate(ref, n, obs_fn=obs_fn)
        new = v2rt(PV.EventRules(env=stub_env()), FakeBackend(dets_fn=dets_fn), cfg, timer=timer() if timer else None)
        simulate(new, n, obs_fn=obs_fn)
        return ref, new

    def test_rules_equal_v2_bit_for_bit(self):
        for sc in self.SCENARIOS:
            ref, new = self.run_pair(sc)
            for stream in ('ticks', 'jobs', 'events'):
                self.assertEqual(rows(ref, stream), rows(new, stream), (sc, stream))
            self.assertGreaterEqual(len(rows(ref, 'jobs')), 2, sc)

    def test_v4_policy_on_v4_runtime_equals_v2(self):
        for sc in self.SCENARIOS:
            obs_fn, dets_fn = self.SCENARIOS[sc]
            for timer in (None, lambda: SteppingTimer(1e-4)):
                cfg = config(max_age_s=3.0, overhead_scale=1.0 if timer else 0.0)
                ref = v2rt(P.EventTriggered(env=stub_env()), FakeBackend(dets_fn=dets_fn), cfg,
                           timer=timer() if timer else None)
                simulate(ref, 140, obs_fn=obs_fn)
                new = v4rt(PV.EventTriggeredV4(env=stub_env()), FakeBackend(dets_fn=dets_fn), cfg,
                           timer=timer() if timer else None)
                simulate(new, 140, obs_fn=obs_fn)
                self.assertEqual([job_projection(j) for j in rows(ref, 'jobs')],
                                 [job_projection(j) for j in rows(new, 'jobs')], sc)
                self.assertEqual([tick_projection(t) for t in rows(ref, 'ticks')],
                                 [tick_projection(t) for t in rows(new, 'ticks')], sc)

    def test_heartbeat_moves_the_no_event_refresh(self):
        for hb, want in ((None, 3.0 - 0.515), (1.5, 1.5 - 0.515)):
            rt = v4rt(PV.EventTriggeredV4(env=stub_env(), heartbeat_s=hb), cfg=config(max_age_s=3.0))
            simulate(rt, 80)
            jobs = rows(rt, 'jobs')
            self.assertAlmostEqual(jobs[1]['start_s'], want, delta=1e-6)
            self.assertEqual(jobs[1]['policy_state']['start_trigger'], 'heartbeat')
            self.assertEqual(jobs[1]['policy_state']['start_action'], 'REFRESH_AFTER_WAIT')
        with self.assertRaises(ValueError):
            PV.EventTriggeredV4(env=stub_env(), heartbeat_s=0.0)

    def test_start_triggers(self):
        obs_fn, dets_fn = self.SCENARIOS['det_change']
        rt = v4rt(PV.EventTriggeredV4(env=stub_env()), FakeBackend(dets_fn=dets_fn), config(max_age_s=3.0))
        simulate(rt, 120, obs_fn=obs_fn)
        trig = [j['policy_state']['start_trigger'] for j in rows(rt, 'jobs')]
        self.assertEqual(trig[0], 'bootstrap')
        self.assertIn('det_event', trig)
        obs_fn, _ = self.SCENARIOS['ego_idle']
        rt = v4rt(PV.EventTriggeredV4(env=stub_env()), cfg=config(max_age_s=3.0))
        simulate(rt, 60, obs_fn=obs_fn)
        self.assertEqual(rows(rt, 'jobs')[1]['policy_state']['start_trigger'], 'ego_event:speed')
        self.assertAlmostEqual(rows(rt, 'jobs')[1]['start_s'], 1.5, delta=TOL)
        s = rt.summary()
        self.assertEqual(s['v3']['start_triggers'].get('ego_event:speed'), 1)

    def test_decision_rows_schema(self):
        rt = v4rt(PV.EventTriggeredV4(env=stub_env()), cfg=config(max_age_s=3.0))
        simulate(rt, 80)
        d = rows(rt, 'decisions')
        self.assertTrue(d)
        for r in d:
            self.assertEqual(set(r['features']), set(S.FEATURE_NAMES))
            self.assertIsNone(r['p_both'])
            self.assertIn(r['action'], (PV.REFINE, PV.END))
        self.assertIsNone(rt.summary()['v4']['p_both'])


class LoggedBaselineTest(unittest.TestCase):
    CASES = (('fixed_deep', {}, None), ('fast_only', {}, None), ('framelease', {}, 1.6),
             ('framelease', {}, lambda plan: 0.7), ('framelease', {'reservation': False}, 1.2))

    def make(self, name, params, lease, logged):
        cls = PV.logged_v2_class(name) if logged else P.POLICY_CLASSES[name]
        env = stub_env(lease) if lease is not None else None
        return cls(env=env, **params)

    def test_mixin_and_v4_runtime_keep_every_v2_timeline(self):
        for name, params, lease in self.CASES:
            for timer in (None, lambda: SteppingTimer(2e-4)):
                cfg = config(max_age_s=2.0 if name == 'framelease' else 3.0, overhead_scale=1.0 if timer else 0.0)
                ref = v2rt(self.make(name, params, lease, False), cfg=cfg, timer=timer() if timer else None)
                simulate(ref, 120, obs_fn=lambda k: make_obs(k, moving=True))
                new = v4rt(self.make(name, params, lease, True), cfg=cfg, timer=timer() if timer else None)
                simulate(new, 120, obs_fn=lambda k: make_obs(k, moving=True))
                key = (name, str(params), str(lease), bool(timer))
                self.assertEqual([job_projection(j) for j in rows(ref, 'jobs')],
                                 [job_projection(j) for j in rows(new, 'jobs')], key)
                self.assertEqual([tick_projection(t) for t in rows(ref, 'ticks')],
                                 [tick_projection(t) for t in rows(new, 'ticks')], key)
                for kind in ('commit', 'reject'):
                    strip = lambda e: {k: v for k, v in e.items() if k not in ('details', 'budget', 'margin_at_commit_m')}
                    self.assertEqual([strip(e) for e in events(ref, kind)], [strip(e) for e in events(new, kind)], key)
                self.assertEqual(ref.summary()['fallback_ticks'], new.summary()['fallback_ticks'], key)

    def test_rows_per_boundary(self):
        rt = v4rt(PV.logged_v2_class('fixed_deep')(env=None))
        simulate(rt, 100)
        d = rows(rt, 'decisions')
        done = [j['job_id'] for j in rows(rt, 'jobs')]
        for jid in done:
            acts = [r['action'] for r in d if r['job_id'] == jid]
            self.assertEqual(acts, [PV.REFINE] * 9 + [PV.END])
            self.assertTrue([r for r in d if r['job_id'] == jid][-1]['at_max_depth'])
        rt = v4rt(PV.logged_v2_class('fast_only')(env=None))
        simulate(rt, 100)
        d = rows(rt, 'decisions')
        self.assertTrue(all(r['action'] == PV.END and r['reason'] == 'target_depth' for r in d))
        self.assertEqual(rt.summary()['v3']['start_labels'].get('REFRESH'), len(rows(rt, 'jobs')) - 1 +
                         (1 if rt.job is not None else 0))


class RuntimeAccountingTest(unittest.TestCase):
    def check_against_logs(self, rt):
        s = rt.summary()
        ticks, jobs, evs = rows(rt, 'ticks'), rows(rt, 'jobs'), rows(rt, 'events')
        tm = MV.tick_metrics(ticks, s['v3']['first_commit_s'])
        self.assertAlmostEqual(s['v4']['deadline_miss_ratio'], tm['deadline_miss_ratio'], delta=1e-12)
        if tm.get('deadline_miss_ratio_after_first_commit') is not None:
            self.assertAlmostEqual(s['v4']['deadline_miss_ratio_after_first_commit'],
                                   tm['deadline_miss_ratio_after_first_commit'], delta=1e-12)
        self.assertEqual(s['v4']['fallback_episodes'], tm['fallback_episodes'])
        self.assertAlmostEqual(s['action_age_s']['p50'] or 0.0, tm['action_age_p50_s'] or 0.0, delta=1e-12)
        busy = MV.busy_within(MV.busy_intervals(jobs, evs), tm['first_tick_s'], tm['last_tick_s'] + DT)
        self.assertLessEqual(busy, s['gpu_busy_in_span_s'] + 1e-9)
        self.assertLessEqual(s['gpu_busy_in_span_s'] - busy, 10 * 0.015 + 1e-9)   # only the running job's steps
        self.assertAlmostEqual(s['v4']['gpu_usage'], s['gpu_busy_in_span_s'] / s['sim_span_s'], delta=1e-12)
        return s

    def test_every_policy_kind(self):
        pols = [PV.logged_v2_class('fixed_deep')(env=None), PV.logged_v2_class('fast_only')(env=None),
                PV.logged_v2_class('framelease')(env=stub_env(1.6)), PV.EventTriggeredV4(env=stub_env()),
                age_policy(1.5), S.ShieldedHeuristicPolicy(env=lease_env())]
        for pol in pols:
            rt = v4rt(pol, cfg=config(max_age_s=2.5))
            simulate(rt, 150, obs_fn=lambda k: make_obs(k, moving=True))
            s = self.check_against_logs(rt)
            kind = s['v4']['policy_kind']
            self.assertEqual(kind, 'shield' if isinstance(pol, S.ShieldedHeuristicPolicy) else 'v2_rule')
            if kind == 'shield':
                d = rows(rt, 'decisions')
                self.assertAlmostEqual(s['v4']['p_both'], sum(r['p_both'] for r in d) / len(d), delta=1e-12)
            else:
                self.assertIsNone(s['v4']['p_both'])

    def test_gpu_usage_analytic(self):
        """Event-Triggered without events: jobs at 0, 2.485 (obs 49) and 4.935 (obs 98), 0.45 + 10 x 0.015 s each."""
        rt = v4rt(PV.EventTriggeredV4(env=stub_env()), cfg=config(max_age_s=3.0))
        simulate(rt, 120)
        starts = [round(e['sim_s'], 9) for e in events(rt, 'job_start')]
        self.assertEqual(starts, [0.0, 2.485, 4.935])
        s = self.check_against_logs(rt)
        self.assertAlmostEqual(s['v4']['gpu_usage'], 3 * (0.45 + 10 * 0.015) / 6.0, delta=1e-9)
        rt = v4rt(PV.logged_v2_class('fast_only')(env=None))
        simulate(rt, 120)
        self.assertAlmostEqual(rt.summary()['v4']['gpu_usage'], 1.0, delta=1e-9)   # work-conserving: always busy

    def test_deadline_miss_analytic(self):
        """Fast Only with plans valid 0.5 s: released 0.465 s after capture, the next 0.465 s later -> each plan is
        tracked for 0.035 s of every 0.465 s cycle at most; ticks at 0.05 s see it in fallback in between."""
        rt = v4rt(PV.logged_v2_class('fast_only')(env=None), cfg=config(max_age_s=0.5))
        simulate(rt, 200)
        s = self.check_against_logs(rt)
        ticks = rows(rt, 'ticks')
        track = [t for t in ticks if t['mode'] == 'track']
        self.assertTrue(all(t['sim_s'] - t['incumbent']['capture_s'] < 0.5 for t in track))
        self.assertGreater(s['v4']['deadline_miss_ratio_after_first_commit'], 0.8)
        self.assertEqual(s['v4']['fallback_ticks_total'], sum(1 for t in ticks if t['mode'] != 'track'))


if __name__ == '__main__':
    unittest.main()
