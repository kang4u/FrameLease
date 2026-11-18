"""The R-1 metrics metrics_v4 lacks (framelease_v4/analysis/extra_metrics.py; PROTOCOL Secs. 6.1-6.4, 7.6). CPU only;
every log is synthetic and every expected value is computed by hand in the test. A step that fails on a malformed
record (extra_metrics(errors=...), guarded) leaves only its own columns out.

  cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/analysis/tests/test_extra_metrics.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ['CUDA_VISIBLE_DEVICES'] = ''
sys.dont_write_bytecode = True

from framelease_v4.analysis import extra_metrics as XM  # noqa: E402


def commit_ev(job, depth, capture, commit, deadline, lease, obs=None, **kw):
    return {'kind': 'commit', 'job_id': job, 'obs_id': job if obs is None else obs, 'depth': depth,
            'capture_s': capture, 'commit_s': commit, 'sim_s': commit, 'deadline_s': deadline, 'lease_s': lease,
            'release_s': commit - 0.005, 'budget': None, **kw}


class Driving(unittest.TestCase):
    def test_infractions_per_km_excludes_min_speed_and_route_ending(self):
        row = {'valid_record': 1, 'km_driven': 0.5, 'inf_collisions_vehicle': 2, 'inf_red_light': 1,
               'inf_outside_route_lanes': 1, 'inf_scenario_timeouts': 1, 'inf_min_speed_infractions': 7,
               'inf_route_dev': 1, 'inf_vehicle_blocked': 1, 'inf_route_timeout': 0}
        got = XM.infraction_metrics(row)
        self.assertEqual(got['infractions_penalized'], 5)
        self.assertAlmostEqual(got['infractions_per_km'], 10.0)
        self.assertEqual(got['route_ending_events'], 2)
        self.assertAlmostEqual(XM.infraction_metrics({**row, 'km_driven': 0.0})['infractions_per_km'], 5 / 0.001)
        self.assertIsNone(XM.infraction_metrics({'valid_record': 0})['infractions_per_km'])

    def test_dmr_from_first_commit_and_cuda_seconds(self):
        ticks = [{'sim_s': 0.05 * (k + 1), 'mode': 'fallback', 'fallback_reason': 'no_plan'} for k in range(4)]
        ticks += [{'sim_s': 0.25, 'mode': 'track'}, {'sim_s': 0.30, 'mode': 'fallback', 'fallback_reason': 'expired'},
                  {'sim_s': 0.35, 'mode': 'fallback', 'fallback_reason': 'reanchor_nonfinite'},
                  {'sim_s': 0.40, 'mode': 'track'}]
        got = XM.dmr_metrics(ticks, [commit_ev(1, 1, 0.0, 0.25, 1.0, 1.0)], gpu_usage=0.9, kappa=1.5)
        self.assertEqual(got['dmr_ticks'], 4)
        self.assertAlmostEqual(got['dmr'], 0.5)
        self.assertAlmostEqual(got['expired_ratio_after_first_commit'], 0.25)
        self.assertAlmostEqual(got['cuda_s_per_s'], 0.6)
        none = XM.dmr_metrics(ticks, [], None, 1.0)
        self.assertEqual((none['dmr'], none['cuda_s_per_s']), (None, None))


class LeaseValidity(unittest.TestCase):
    def test_utilization_and_premature_expiry_by_hand(self):
        rz = {'available': True, 't_pred_s': 3.0, 't_c_s': 0.5, 'candidates': {
            '1:1': {'status': 'ok', 'conflict': True, 'V_suf': 1.0, 'lease_s': 0.5, 'log_censored': False},
            '2:1': {'status': 'ok', 'conflict': False, 'V_suf': None, 'lease_s': 2.5, 'log_censored': False},
            '3:1': {'status': 'ok', 'conflict': False, 'V_suf': None, 'lease_s': 1.0, 'log_censored': True},
            '4:1': {'status': 'ok', 'conflict': True, 'V_suf': 1.0, 'lease_s': 0.2, 'log_censored': False},
            '5:1': {'status': 'ok', 'conflict': True, 'V_suf': 0.0, 'lease_s': 0.3, 'log_censored': False},
            '6:1': {'status': 'no_pose_or_plan'}}}
        events = [commit_ev(1, 1, 0.0, 0.45, 0.5, 0.5), commit_ev(2, 1, 1.0, 1.2, 3.5, 2.5),
                  commit_ev(3, 1, 1.8, 2.0, 2.8, 1.0), commit_ev(4, 1, 2.5, 2.6, 2.7, 0.2),
                  commit_ev(5, 1, 4.0, 4.1, 4.3, 0.3), {'kind': 'reject', 'job_id': 9}]
        got = XM.lease_validity_metrics(rz, XM.accepted_commits(events), end_s=5.0)
        # evaluated: 1, 2, 4, 5 (3 log-censored, 6 without pose); utilization over V_suf > 0: 0.5/1, 2.5/2.5, 0.2/1
        self.assertEqual(got['lease_plans_evaluated'], 4)
        self.assertAlmostEqual(got['lease_utilization'], (0.5 + 1.0 + 0.2) / 3)
        # premature: plan 1 (D 0.5 < next commit 1.2, valid until 1.0) and plan 4 (D 2.7 < 4.1, valid until 3.5)
        self.assertEqual(got['premature_expiry_plans'], 2)
        self.assertAlmostEqual(got['premature_expiry_ratio'], 0.5)
        self.assertAlmostEqual(got['premature_expiry_lost_s'], (1.0 - 0.5) + (3.5 - 2.7))

    def test_last_plan_uses_the_run_end_and_unavailable_log(self):
        rz = {'available': True, 't_pred_s': 3.0, 't_c_s': 0.5,
              'candidates': {'1:1': {'status': 'ok', 'conflict': True, 'V_suf': 2.0, 'lease_s': 1.0,
                                     'log_censored': False}}}
        got = XM.lease_validity_metrics(rz, XM.accepted_commits([commit_ev(1, 1, 0.0, 0.4, 1.0, 1.0)]), end_s=1.5)
        self.assertEqual(got['premature_expiry_plans'], 1)
        self.assertAlmostEqual(got['premature_expiry_lost_s'], 0.5)
        early = XM.lease_validity_metrics(rz, XM.accepted_commits([commit_ev(1, 1, 0.0, 0.4, 1.0, 1.0)]), end_s=0.9)
        self.assertEqual(early['premature_expiry_plans'], 0)
        self.assertIsNone(XM.lease_validity_metrics({'available': False}, [], 1.0)['lease_utilization'])
        self.assertIsNone(XM.lease_validity_metrics(None, [], 1.0)['premature_expiry_plans'])


class Scheduler(unittest.TestCase):
    def decisions(self, qnet=True):
        rows = [({'depth': 3, 'v4_bypass': None, 'v4_qnet_s': 1e-5}, True, 'REFINE'),
                ({'depth': 4, 'v4_bypass': None, 'v4_qnet_s': 3e-5}, True, 'REFINE'),
                ({'depth': 2, 'v4_bypass': 'slack', 'v4_qnet_s': None}, True, 'REFINE'),
                ({'depth': 5, 'v4_bypass': None, 'v4_qnet_s': 2e-5}, False, 'REFRESH')]
        out = []
        for i, (f, both, a) in enumerate(rows, 1):
            if not qnet:
                f = {'depth': f['depth']}
            out.append({'epoch': i, 'p_both': both, 'action': a, 'depth': f['depth'], 'features': f,
                        'decision_wall_s': 1e-4 * i})
        return out

    def events(self):
        return [commit_ev(1, 1, 0.0, 0.4, 1.0, 0.4, budget={'overrun': False}), commit_ev(1, 2, 0.0, 0.5, 1.0, 0.8),
                {'kind': 'reject', 'reason': 'invalid:shape_or_nonfinite', 'budget': {'overrun': True}},
                {'kind': 'reject', 'reason': 'expired_before_commit', 'budget': None},
                {'kind': 'shield_violation', 'sim_s': 2.0}]

    def test_deviation_bypass_budget_rejects(self):
        got = XM.scheduler_metrics(self.decisions(), self.events(), d_star=4)
        self.assertEqual((got['choice_epochs'], got['deviation_epochs']), (3, 1))     # depth 4 REFINE vs a_det^4
        self.assertAlmostEqual(got['deviation_rate'], 1 / 3)
        self.assertEqual((got['bypass_epochs'], json.loads(got['bypass_by_reason'])), (1, {'slack': 1}))
        self.assertAlmostEqual(got['bypass_rate'], 1 / 3)
        self.assertEqual((got['committed_plans'], got['budget_checked'], got['budget_overruns']), (2, 2, 1))
        self.assertAlmostEqual(got['lease_committed_p50_s'], 0.6)
        self.assertEqual(got['shield_violations'], 1)
        self.assertEqual(json.loads(got['gate_rejects_by_reason']), {'expired_before_commit': 1, 'invalid': 1})

    def test_without_qnet_or_d_star(self):
        got = XM.scheduler_metrics(self.decisions(qnet=False), self.events(), d_star=None)
        self.assertEqual((got['bypass_rate'], got['bypass_by_reason'], got['deviation_rate']), (None, None, None))
        self.assertEqual(XM.scheduler_metrics(self.decisions(qnet=False), [], d_star=10)['deviation_epochs'], 0)

    def test_utility_depth(self):
        self.assertEqual([XM.utility_depth(n) for n in ('heuristic', 'v4_adet_d4', 'v4_eps0.300_seed7_d6',
                                                        'v4_eps0.300_seed7', 'v4_qnet_0123456789ab', None)],
                         [10, 4, 6, 10, None, None])


class Timing(unittest.TestCase):
    def test_switching_cancelled_validation_quanta(self):
        jobs = [{'job_id': 1, 'start_s': 0.0, 'end_s': 0.62, 'prefix': {'timeline_cost_s': 0.4}, 'prefix_end_s': 0.4,
                 'committed_depths': [1],
                 'steps': [{'depth': 1, 'timeline_cost_s': 0.1, 'release_s': 0.5, 'validity': {'lease_wall_s': 1e-3}},
                           {'depth': 2, 'timeline_cost_s': 0.1, 'release_s': 0.61,
                            'validity': {'lease_wall_s': 3e-3}}]},
                {'job_id': 2, 'start_s': 0.62, 'end_s': 1.15, 'prefix': {'timeline_cost_s': 0.4}, 'prefix_end_s': 1.03,
                 'committed_depths': [], 'steps': [{'depth': 1, 'timeline_cost_s': 0.1, 'release_s': 1.13}]}]
        events = [{'kind': 'job_start', 'job_id': 1, 'sim_s': 0.0, 'overhead_s': 0.0, 'prefix_timeline_s': 0.4,
                   'prefix_cost_s': 0.4},
                  {'kind': 'job_start', 'job_id': 2, 'sim_s': 0.62, 'overhead_s': 0.01, 'prefix_timeline_s': 0.4,
                   'prefix_cost_s': 0.4},
                  {'kind': 'job_start', 'job_id': 3, 'sim_s': 1.30, 'overhead_s': 0.01, 'prefix_timeline_s': 0.5,
                   'prefix_cost_s': 0.5},
                  {'kind': 'commit', 'job_id': 1, 'depth': 1, 'commit_s': 0.505, 'release_s': 0.5},
                  {'kind': 'reject', 'job_id': 1, 'depth': 2, 'commit_s': None, 'release_s': 0.61,
                   'details': {'commit_s': 0.613}}]
        self.assertEqual(len(XM.switching_latencies(jobs, events)), 1)               # job 3 waited for a frame
        self.assertAlmostEqual(XM.switching_latencies(jobs, events)[0], (0.62 - 0.61) + 0.01)
        cancelled, total = XM.cancelled_gpu_work(jobs)
        self.assertAlmostEqual(cancelled, 0.1 + 0.5)
        self.assertAlmostEqual(total, 1.1)
        got = XM.timing_metrics(jobs, events, [{'decision_wall_s': 2e-4, 'features': {'v4_qnet_s': 5e-5}}])
        self.assertAlmostEqual(got['cancelled_gpu_share'], 0.6 / 1.1)
        self.assertEqual(got['validation_s_n'], 2)
        self.assertAlmostEqual(got['validation_s_p50'], 0.004)
        self.assertAlmostEqual(got['prefix_quantum_s_p50'], 0.4)
        self.assertEqual((got['prefix_quantum_s_n'], got['step_quantum_s_n'], got['lease_wall_s_n']), (3, 3, 2))
        self.assertAlmostEqual(got['lease_wall_s_p50'], 2e-3)
        self.assertAlmostEqual(got['qnet_s_p50'], 5e-5)
        self.assertAlmostEqual(got['decision_wall_s_p99'], 2e-4)


class OneRun(unittest.TestCase):
    def test_extra_metrics_on_a_run_directory_and_summary_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / 'run'
            fl = run / 'raw' / 'agent' / 'framelease'
            fl.mkdir(parents=True)
            (run / 'metrics').mkdir()
            (run / 'config.json').write_text(json.dumps({'kind': 'shield', 'kappa': 2.0, 'v4': {
                'agent': {'policy_params': {'utility': 'v4_adet_d4'}}}}))
            summary = {'v3': {'budget_checked': 0, 'budget_overruns': 0, 'shield_violations': 0,
                              'commit_gate': {'accepted': 1}},
                       'v4': {'deadline_miss_ratio_after_first_commit': 0.5}}
            (fl / 'summary.json').write_text(json.dumps(summary))
            (fl / 'ticks.jsonl').write_text(''.join(json.dumps(t) + '\n' for t in (
                {'sim_s': 0.05, 'mode': 'fallback', 'fallback_reason': 'no_plan'}, {'sim_s': 0.10, 'mode': 'track'},
                {'sim_s': 0.15, 'mode': 'fallback', 'fallback_reason': 'expired'})))
            (fl / 'events.jsonl').write_text(json.dumps(commit_ev(1, 1, 0.0, 0.1, 0.12, 0.12)) + '\n')
            for n in ('jobs.jsonl', 'decisions.jsonl'):
                (fl / n).write_text('')
            got = XM.extra_metrics(run, {'valid_record': 0, 'gpu_usage': 0.8, 'kappa': 2.0})
            self.assertEqual((got['arm_kind'], got['d_star_used'], got['d_star_source']),
                             ('shield', 4, 'utility of the run'))
            self.assertAlmostEqual(got['dmr'], 0.5)
            self.assertAlmostEqual(got['cuda_s_per_s'], 0.4)
            self.assertIsNone(got['lease_utilization'])                              # no actor log
            self.assertEqual(json.loads(got['agg_checks']),
                             {'dmr_abs_diff': 0.0, 'budget_checked_equal': True, 'budget_overruns_equal': True,
                              'shield_violations_equal': True, 'gate_rejects_equal': True})
            self.assertEqual(XM.extra_metrics(run, {}, d_star=6)['d_star_source'], 'freeze')
            # a malformed commit event (no depth): only the lease-validity step fails, its columns are left out
            (fl / 'events.jsonl').write_text(json.dumps({k: v for k, v in commit_ev(1, 1, 0.0, 0.1, 0.12, 0.12).items()
                                                         if k != 'depth'}) + '\n')
            with self.assertRaises(KeyError):                            # without errors an exception propagates
                XM.extra_metrics(run, {'valid_record': 0, 'gpu_usage': 0.8, 'kappa': 2.0})
            errors = []
            got = XM.extra_metrics(run, {'valid_record': 0, 'gpu_usage': 0.8, 'kappa': 2.0}, errors=errors)
            self.assertEqual([n for n, _ in errors], ['lease_validity_metrics'])
            self.assertIn('KeyError', errors[0][1])
            self.assertNotIn('lease_utilization', got)
            self.assertAlmostEqual(got['dmr'], 0.5)
            self.assertIn('agg_checks', got)
            self.assertIn('validation_s_p50', got)

    def test_guarded(self):
        errors = []
        self.assertEqual(XM.guarded(errors, 'ok', dict, a=1), {'a': 1})
        self.assertIsNone(XM.guarded(errors, 'bad', lambda: {}['x']))
        self.assertEqual(XM.guarded(errors, 'kw', lambda errors: errors, errors='mine'), 'mine')   # kw named errors
        self.assertEqual(errors, [('bad', "KeyError: 'x'")])
        with self.assertRaises(KeyError):
            XM.guarded(None, 'bad', lambda: {}['x'])
        with self.assertRaises(RuntimeError):                            # not a malformed record: propagates
            XM.guarded([], 'boom', lambda: (_ for _ in ()).throw(RuntimeError('x')))


if __name__ == '__main__':
    unittest.main()
