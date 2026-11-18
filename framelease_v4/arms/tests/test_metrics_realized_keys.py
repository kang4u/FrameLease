"""Regression test of amendment A2 (PROTOCOL Sec. 13.2): the realized-validity keys of metrics_v4.run_metrics.

realized.realized_validity returns realized_invalid_ticks and realized_invalid_tick_ratio with their prefix already
in the name. run_metrics prefixed every key again, so these two became realized_realized_*, and the readers of
realized_invalid_tick_ratio (metrics_v4.arm_summary and the EIR column of protocol/d1_summary.py) always got None.
The keys without the prefix (conflict_plans, misses, r_cond, ...) were and stay realized_<key>.

  cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/arms/tests/test_metrics_realized_keys.py
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test_actor_log_metrics_v4 import parked_car_world, simulated_run

from framelease_v4.arms import metrics_v4 as MV
from framelease_v4.arms import policies_v4 as PV
from framelease_v4.arms import realized as RZ
from framelease_v4.protocol import d1_summary as D1


class RealizedKeysTest(unittest.TestCase):
    def test_single_prefix_and_eir(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / 'r0'
            d.mkdir()
            w, hero = parked_car_world()
            simulated_run(d, PV.logged_v2_class('fixed_deep')(env=None), w, hero, n=120)
            rz = RZ.realized_validity(d)
            row = MV.run_metrics(d, realized=True)
            self.assertFalse([k for k in row if k.startswith('realized_realized_')], sorted(row))
            self.assertTrue(row['realized_available'])
            self.assertGreater(rz['realized_invalid_ticks'], 0)              # the run has executed-invalid ticks
            self.assertEqual(row['realized_invalid_ticks'], rz['realized_invalid_ticks'])
            self.assertAlmostEqual(row['realized_invalid_tick_ratio'], rz['realized_invalid_tick_ratio'], places=15)
            for k in ('conflict_plans', 'misses', 'r_cond', 'v0_plans', 'r_cond_excl_v0', 'log_censored_plans'):
                self.assertEqual(row[f'realized_{k}'], rz[k], k)
            arm = MV.arm_summary([row])[0]
            self.assertAlmostEqual(arm['realized_invalid_tick_ratio'], rz['realized_invalid_tick_ratio'], places=15)
            cand = {'per_route': {'1': {'outcome': 'ok', 'run_dir': str(d)}}, 'candidate': 'c', 'arm': 'fixed_deep',
                    'tag': 'fixed_deep', 'policy_params': {}, 'envelope': None, 'reused_from': None,
                    'outcomes': {'ok': 1}, 'n': 1, 'mean_ds': 80.0}
            s = D1.candidate_summary(cand, realized=True)
            self.assertAlmostEqual(s['eir'], rz['realized_invalid_tick_ratio'], places=15)
            self.assertEqual((s['realized_conflicts'], s['realized_misses']), (rz['conflict_plans'], rz['misses']))
            self.assertIsNone(D1.candidate_summary(cand, realized=False)['eir'])

    def test_without_realized_no_realized_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / 'r0'
            d.mkdir()
            w, hero = parked_car_world()
            simulated_run(d, PV.logged_v2_class('fast_only')(env=None), w, hero, n=60)
            row = MV.run_metrics(d, realized=False)
            self.assertFalse([k for k in row if k.startswith('realized_')], sorted(row))


if __name__ == '__main__':
    unittest.main()
