"""The manipulation checks R-3 and the background-load check (framelease_v4/analysis/manipulation.py; PROTOCOL Sec. 9.7,
reported, not tested). CPU only; every configuration, log and row is synthetic.

  cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/analysis/tests/test_manipulation.py
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

from framelease_v4.analysis import manipulation as MC  # noqa: E402
from framelease_v4.protocol import check_smoke as CS  # noqa: E402

TUNING = {'L_star_sha256': 'L' * 64, 'risk_sha256': 'R' * 64, 'd_star': 4, 'utility': 'v4_adet_d4',
          'A_star': {'age_lease_s': 1.5, 'utility': 'v4_adet_d4'},
          'event_params': {'heartbeat_s': 2.0, 'speed_delta_mps': 1.0}}


def shield_cfg(env='L' * 64, utility='v4_adet_d4', kind='shield', depth=10, **pp):
    return {'kind': kind, 'envelope_sha256': env, 'agent_config': {'runtime': {'max_depth': depth}},
            'v4': {'agent': {'policy_params': {'utility': utility, **pp}, 'runtime': {'max_depth': depth}},
                   'v3': {'resolved': {'policy_params': {'max_depth': depth}, 'lease': {'h_bar_s': 2.5}}}}}


class PerRun(unittest.TestCase):
    def test_prefix_band_and_background_load(self):
        cases = [(0.420, 1.0, 'PASS', 'within', 0.0), (0.450, 1.0, 'PASS', 'above', 0.450 - 0.426),
                 (0.840, 2.0, 'PASS', 'within', 0.0), (0.700, 2.0, 'PASS', 'below', 2.0 * (0.35 - 0.416)),
                 (0.300, 1.0, 'FLAG', 'below', 0.300 - 0.416), (0.650, 1.0, 'FLAG', 'above', 0.650 - 0.426)]
        for p50, kappa, band, load, excess in cases:
            with self.subTest(p50=p50, kappa=kappa):
                got = MC.prefix_checks(p50, kappa)
                self.assertEqual((got['charged_prefix_check'], got['bg_load_status']), (band, load))
                self.assertAlmostEqual(got['bg_load_excess_s'], excess)
                self.assertAlmostEqual(got['prefix_p50_per_kappa_s'], p50 / kappa)
        self.assertIsNone(MC.prefix_checks(None, 1.0)['bg_load_status'])

    def test_idle_band_edges_are_the_sec_9_7_pilot_range(self):
        """The idle band is kappa x [0.416, 0.426] s, edges inside (APPLY_PLAN step 1: the upper edge was 0.425)."""
        self.assertEqual(MC.IDLE_PREFIX_BAND_S, (0.416, 0.426))
        cases = [(0.416, 1.0, 'within'), (0.426, 1.0, 'within'), (0.4255, 1.0, 'within'), (0.4261, 1.0, 'above'),
                 (0.4159, 1.0, 'below'), (0.852, 2.0, 'within'), (0.8530, 2.0, 'above'), (0.624, 1.5, 'within'),
                 (0.6230, 1.5, 'below')]
        for p50, kappa, load in cases:
            with self.subTest(p50=p50, kappa=kappa):
                got = MC.prefix_checks(p50, kappa)
                self.assertEqual(got['bg_load_status'], load)
                edge = {'within': p50 / kappa, 'above': 0.426, 'below': 0.416}[load]
                self.assertAlmostEqual(got['bg_load_excess_s'], kappa * (p50 / kappa - edge))

    def test_idle_band_source_quotes_sec_9_7(self):
        """IDLE_BAND_SOURCE quotes the 'Charged prefix' item of PROTOCOL Sec. 9.7 word for word (markdown emphasis and
        line breaks removed), and the quoted pilot range is IDLE_PREFIX_BAND_S."""
        text = (ROOT / 'framelease_v4' / 'PROTOCOL.md').read_text(encoding='utf-8')
        sec = text.split('### 9.7 ', 1)[1].split('\n### ', 1)[0]
        flat = ' '.join(sec.replace('**', '').split())
        quote = MC.IDLE_BAND_SOURCE.split('"')[1]
        self.assertIn('Sec. 9.7', MC.IDLE_BAND_SOURCE.split('"')[0])
        self.assertIn(quote, flat)
        lo, hi = MC.IDLE_PREFIX_BAND_S
        self.assertIn(f'the pilot measured {lo:.3f}-{hi:.3f} s at kappa 1.0', quote)
        self.assertIn(quote, ' '.join(MC.__doc__.split()))

    def test_depth_limit(self):
        self.assertEqual(MC.depth_limit_problems(shield_cfg()), [])
        cfg = shield_cfg()
        cfg['v4']['v3']['resolved']['policy_params']['max_depth'] = 8
        self.assertEqual(len(MC.depth_limit_problems(cfg)), 1)
        self.assertEqual(MC.depth_limit_problems(shield_cfg(kind='v2_rule', depth=1)), [])
        none = {'kind': 'shield', 'v4': {'agent': {'policy_params': {}}}}           # a lease arm without any limit
        self.assertIn('no depth limit recorded', MC.depth_limit_problems(none)[0])
        self.assertEqual(MC.depth_limit_problems({'kind': 'v2_rule'}), [])

    def test_health_only_rows_withhold_the_depths_of_lease_arms(self):
        jobs = [{'start_s': 0.0, 'steps': [{'depth': 3, 'release_s': 0.4}]}]
        logs = {'cfg': {}, 'jobs': jobs}
        job = {'arm_name': 'fl_heuristic', 'route_id': '1711', 'kappa': 1.0, 'seed': 11, 'phase': 'P4',
               'policy_params': {}, 'envelope': None, 'require_sha256': {}}
        with tempfile.TemporaryDirectory() as tmp:
            for cfg, health, shown in ((shield_cfg(), True, False), (shield_cfg(), False, True),
                                       ({'kind': 'v2_rule'}, True, True)):
                with self.subTest(kind=cfg['kind'], health=health):
                    got = MC.run_checks(job, tmp, {**logs, 'cfg': cfg}, 0.42, None, 'fl_heuristic', None, health)
                    self.assertEqual('job_release_by_depth' in got, shown)
                    self.assertEqual('predicted_expiry_fallback' in got, not health)

    def test_freeze_values_per_protocol_arm(self):
        ok = [('fl_heuristic', shield_cfg()), ('fl_global_shield', shield_cfg()),
              ('fl_risk', shield_cfg(env='R' * 64)), ('fl_full', shield_cfg(utility='v4_qnet_0123456789ab')),
              ('fl_behaviour', shield_cfg(utility='v4_eps0.300_seed7_d4')),
              ('age_only', shield_cfg(kind='age', age_lease_s=1.5)),
              ('event_triggered', shield_cfg(kind='event', heartbeat_s=2.0, speed_delta_mps=1.0)),
              ('fixed_deep', {'kind': 'v2_rule'})]
        for arm, cfg in ok:
            with self.subTest(arm):
                self.assertEqual(MC.freeze_problems(arm, cfg, TUNING, {'d_star': 4}), [])
        bad = [('fl_heuristic', shield_cfg(env='R' * 64)), ('fl_heuristic', shield_cfg(utility='heuristic')),
               ('fl_risk', shield_cfg()), ('fl_bandit', shield_cfg(env='x')),
               ('fl_behaviour', shield_cfg(utility='v4_eps0.300_seed7_d6')),
               ('age_only', shield_cfg(kind='age', age_lease_s=2.0)),
               ('event_triggered', shield_cfg(kind='event', heartbeat_s=3.0, speed_delta_mps=1.0))]
        for arm, cfg in bad:
            with self.subTest(arm):
                self.assertEqual(len(MC.freeze_problems(arm, cfg, TUNING, {'d_star': 4})), 1)
        self.assertEqual(len(MC.freeze_problems('fl_full', shield_cfg(), TUNING, {'d_star': 10})), 1)

    def test_expiry_rule(self):
        jobs = [{'start_s': 0.0, 'steps': [{'depth': 10, 'release_s': 0.62}]},
                {'start_s': 1.0, 'steps': [{'depth': 10, 'release_s': 1.64}]}]
        fixed = {'v4_arm': 'fixed_deep', 'kind': 'v2_rule', 'agent_config': {'runtime': {'max_age_s': 3.0}}}
        got = MC.expiry_check(fixed, jobs, 0.0)
        self.assertEqual((got['predicted_expiry_fallback'], got['expiry_fallback_flag']), (0.0, False))
        self.assertTrue(MC.expiry_check(fixed, jobs, 0.06)['expiry_fallback_flag'])
        age = {**shield_cfg(kind='age', age_lease_s=1.0), 'v4_arm': 'age_only'}
        half = [{'start_s': 0.0, 'steps': [{'depth': 4, 'release_s': 0.5}]}]
        got = MC.expiry_check(age, half, 0.12)                    # L 0.5, H 1.0: (2 x 0.5 + 0.05 - 1.0) / 0.5
        self.assertAlmostEqual(got['predicted_expiry_fallback'], 0.1)
        self.assertAlmostEqual(got['expiry_fallback_dev'], 0.02)
        self.assertFalse(got['expiry_fallback_flag'])
        self.assertIsNone(MC.expiry_check({**shield_cfg(), 'v4_arm': 'fl_heuristic'}, half, 0.5)[
            'predicted_expiry_fallback'])
        by = MC.job_release_by_depth(jobs + half + [{'start_s': 2.0, 'steps': []}])
        self.assertEqual(sorted(by), ['10', '4'])
        self.assertAlmostEqual(by['10'], 0.63)
        self.assertAlmostEqual(by['4'], 0.5)


class ConfigCheck(unittest.TestCase):
    def run_dir(self, tmp, job, cfg_extra=None):
        run = Path(tmp) / 'run'
        (run / 'raw').mkdir(parents=True)
        cfg = {'v4_arm': job['arm_name'], 'route': {'route_id': job['route_id']}, 'kappa': job['kappa'],
               'seed': job['seed'], 'fast_prefix': {'options': list(CS.FAST_PREFIX_OPTIONS)},
               **shield_cfg(), **(cfg_extra or {})}
        cfg['v4']['agent']['policy_params'] = dict(job['policy_params'])
        (run / 'config.json').write_text(json.dumps(cfg))
        (run / 'manifest.json').write_text(json.dumps({'identity': {'code': {}}}))
        return run, cfg

    def test_phases_and_freeze(self):
        job = {'arm_name': 'fl_heuristic', 'route_id': '1792', 'kappa': 1.0, 'seed': 11, 'phase': 'P1',
               'policy_params': {'utility': 'v4_adet_d4'}, 'envelope': None, 'require_sha256': {}}
        with tempfile.TemporaryDirectory() as tmp:
            run, cfg = self.run_dir(tmp, job)
            self.assertEqual(MC.config_result(job, run, cfg, 'fl_heuristic')[0], 'PASS')
            late = {**job, 'phase': 'P4'}
            self.assertEqual(MC.config_result(late, run, cfg, 'fl_heuristic')[0], 'UNCHECKED')
            self.assertEqual(MC.config_result(late, run, cfg, 'fl_heuristic', {'tuning': TUNING})[0], 'PASS')
            wrong = {**TUNING, 'L_star_sha256': 'B' * 64}
            status, detail = MC.config_result(late, run, cfg, 'fl_heuristic', {'tuning': wrong})
            self.assertEqual(status, 'FAIL')
            self.assertIn('L*', detail)
            cfg['v4']['agent']['runtime']['max_depth'] = 6
            self.assertEqual(MC.config_result(job, run, cfg, 'fl_heuristic')[0], 'FAIL')
            other = {**job, 'seed': 12}
            self.assertEqual(MC.config_result(other, run, shield_cfg(), 'fl_heuristic')[0], 'FAIL')


def row(arm, route, kappa, health=False, **kw):
    base = {'job': f'{arm}_{route}_k{kappa}', 'protocol_arm': arm, 'route_id': route, 'seed': 11, 'kappa': kappa,
            'outcome': 'ok', 'selected_run': f'runs/{arm}_{route}_{kappa}', 'health_only': health,
            'analysis_use': not health, 'fast_prefix_check': CS.PASS, 'config_check': 'PASS',
            **MC.prefix_checks(0.42 * kappa, kappa)}
    base.update(kw)
    return base


class AcrossRuns(unittest.TestCase):
    def test_kappa_scaling(self):
        rows = [row('fixed_deep', 'r1', 1.0, job_release_by_depth=json.dumps({'10': 0.62})),
                row('fixed_deep', 'r1', 2.0, job_release_by_depth=json.dumps({'10': 1.24})),
                row('fixed_deep', 'r2', 1.0, job_release_by_depth=json.dumps({'10': 0.60, '3': 0.5})),
                row('fixed_deep', 'r2', 2.0, job_release_by_depth=json.dumps({'10': 1.50})),
                row('fixed_deep', 'r3', 2.0, job_release_by_depth=json.dumps({'10': 9.0}))]     # no kappa-1.0 run
        got = MC.kappa_scaling(rows)['fixed_deep k2.0']
        self.assertEqual((got['routes'], got['pairs']), (2, 2))
        self.assertAlmostEqual(got['ratio_median'], 1.125)
        self.assertAlmostEqual(got['share_outside_tol'], 0.5)
        self.assertTrue(got['flag'])

    def test_p_both_on_common_routes(self):
        rows = [row('fl_full', 'r1', 1.0, p_both=0.2, shield_epochs=10),
                row('fl_full', 'r2', 1.0, p_both=0.4, shield_epochs=30),
                row('fl_heuristic', 'r1', 1.0, p_both=0.1, shield_epochs=10),
                row('fl_heuristic', 'r2', 1.0, p_both=0.3, shield_epochs=10),
                row('fl_heuristic', 'r3', 1.0, p_both=0.9, shield_epochs=10)]
        got = MC.p_both_summary(rows)['k1.0']
        self.assertEqual(got['routes'], 2)
        self.assertAlmostEqual(got['fl_full']['mean'], 0.3)
        self.assertAlmostEqual(got['fl_full']['pooled'], (0.2 * 10 + 0.4 * 30) / 40)
        self.assertAlmostEqual(got['fl_heuristic']['mean'], 0.2)
        self.assertAlmostEqual(got['mean_difference'], 0.1)

    def test_summary_withholds_outcome_parts_of_health_only_rows(self):
        rows = [row('fixed_deep', 'r1', 1.0, predicted_expiry_fallback=0.0, observed_expiry_fallback=0.0),
                row('fixed_deep', 't1', 1.0, health=True, **MC.prefix_checks(0.47, 1.0)),
                row('fl_full', 't1', 1.0, health=True, p_both=0.5, shield_epochs=4),
                row('fl_heuristic', 't1', 1.0, health=True, p_both=0.1, shield_epochs=4),
                {'job': 'pending', 'outcome': 'pending', 'health_only': False}]
        got = MC.manipulation_summary(rows)
        self.assertEqual((got['runs'], got['withheld_health_only_runs']), (4, 3))
        self.assertEqual(got['per_arm']['fixed_deep k1.0']['bg_load'], {'within': 1, 'above': 1, 'below': 0})
        self.assertEqual([f['check'] for f in got['flags']], ['bg_load_above'])
        self.assertEqual(got['predicted_expiry']['fixed_deep k1.0']['runs'], 1)
        self.assertEqual(got['p_both_shared_shield'], {})
        self.assertEqual(got['idle_prefix_band_s_per_kappa'], [0.416, 0.426])
        self.assertEqual(got['idle_band_source'], MC.IDLE_BAND_SOURCE)


if __name__ == '__main__':
    unittest.main()
