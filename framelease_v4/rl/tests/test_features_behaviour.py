"""State features and the epsilon-random behaviour utility inside the v3 shield (no v3 file is edited).

    cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
        framelease_v4/rl/tests/test_features_behaviour.py
"""
from __future__ import annotations

import math
import unittest

import helpers_rl as H  # noqa: F401  (paths, CUDA hidden, no byte-code)

import numpy as np

from framelease_v3.runtime import v3_shield as VS
from framelease_v3.runtime.v3_scheduler import FEATURE_NAMES
from framelease_v4.rl import behaviour as B
from framelease_v4.rl import features as F

BOUNDS = VS.ShieldBounds(L_pi=0.001, L_refine=0.02, L_refresh=0.47, L_commit=0.001, eps=0.05)


def both():
    sr = VS.shield(10.0, 12.5, 12.5, 3, 10, True, BOUNDS)
    assert sr.both
    return sr


class FeatureTest(unittest.TestCase):
    def test_sixteen_features_six_lease_derived_all_logged_by_v3(self):
        self.assertEqual(F.N_FEATURES, 16)
        self.assertEqual(len(F.LEASE_DERIVED), 6)
        self.assertTrue(F.check_against_v3())
        self.assertTrue(set(F.NAMES) <= set(FEATURE_NAMES))
        for key in ('lease_slack_s', 'obs_age_s', 'depth', 'kappa', 'L_refine_s', 'L_refresh_s'):
            self.assertIn(key, F.NAMES)                            # outline: slack, age, progress, budget, latency
        self.assertEqual(len(F.NO_LEASE_COLUMNS), 10)
        self.assertTrue(all(not F.FEATURES[i].lease_derived for i in F.NO_LEASE_COLUMNS))

    def test_missing_values_and_clipping(self):
        row = H.feature_row(lease_slack_s=None, tau_star_s=None, min_g_m=float('nan'), depth=37, ego_speed_mps=-2.0,
                            plan_delta_m='x')
        v = F.vector(row)
        d = dict(zip(F.NAMES, v))
        self.assertEqual(d['lease_slack_s'], -3.0)
        self.assertEqual(d['tau_star_s'], 3.0)
        self.assertEqual(d['min_g_m'], 10.0)
        self.assertEqual(d['depth'], 10.0)
        self.assertEqual(d['ego_speed_mps'], 0.0)
        self.assertEqual(d['plan_delta_m'], 0.0)
        self.assertTrue(np.all(np.isfinite(v)))
        self.assertEqual(F.vector({}).tolist(), [f.missing for f in F.FEATURES])

    def test_fast_vectorizer_equals_vector_and_reuses_its_buffer(self):
        rng = np.random.default_rng(3)
        fv = F.FastVectorizer()
        buf_id = id(fv.buf)
        for _ in range(200):
            row = {n: (None if rng.uniform() < 0.1 else float(rng.normal(0, 5))) for n in FEATURE_NAMES}
            out = fv.fill(row)
            self.assertEqual(id(out), buf_id)
            np.testing.assert_array_equal(out, F.vector(row))
        sub = F.FastVectorizer(F.NO_LEASE_COLUMNS)
        row = H.feature_row()
        np.testing.assert_array_equal(sub.fill(row), F.vector(row, F.NO_LEASE_COLUMNS))


class BehaviourTest(unittest.TestCase):
    def tearDown(self):
        for k in [k for k in VS.UTILITIES if k.startswith('v4_')]:
            del VS.UTILITIES[k]

    def test_names_round_trip(self):
        n = B.behaviour_name(0.3, 1234)
        self.assertEqual(n, 'v4_eps0.300_seed1234')
        self.assertEqual(B.parse_behaviour_name(n), (0.3, 1234))
        self.assertIsNone(B.parse_behaviour_name('v4_eps1.500_seed1'))
        self.assertIsNone(B.parse_behaviour_name('heuristic'))
        with self.assertRaises(ValueError):
            B.behaviour_name(1.2, 1)
        with self.assertRaises(ValueError):
            B.register_utility_name('v4_unknown')
        self.assertFalse(B.register_utility_name('heuristic'))

    def test_depth_limited_heuristic_and_behaviour_names(self):
        self.assertEqual(B.adet_name(4), 'v4_adet_d4')
        self.assertTrue(B.register_utility_name('v4_adet_d4'))
        u = VS.make_utility('v4_adet_d4')
        self.assertIsInstance(u, B.DepthHeuristicUtility)
        sr = both()
        self.assertEqual(VS.decide(sr, u, H.feature_row(depth=3)), (VS.REFINE, 'both_feasible:v4_adet_d4'))
        self.assertEqual(VS.decide(sr, u, H.feature_row(depth=4))[0], VS.REFRESH)
        self.assertEqual(VS.decide(sr, B.DepthHeuristicUtility(10), H.feature_row(depth=9))[0], VS.REFINE)
        self.assertEqual(VS.decide(sr, B.DepthHeuristicUtility(1), H.feature_row(depth=1))[0], VS.REFRESH)
        with self.assertRaises(ValueError):
            B.register_utility_name('v4_adet_d11')
        n = B.behaviour_name(0.3, 9, d=4)
        self.assertEqual(n, 'v4_eps0.300_seed9_d4')
        self.assertEqual(B.parse_behaviour(n), (0.3, 9, 4))
        self.assertEqual(B.parse_behaviour_name(n), (0.3, 9))
        self.assertEqual(B.behaviour_name(0.3, 9, d=10), 'v4_eps0.300_seed9')
        self.assertIsNone(B.parse_behaviour('v4_eps0.300_seed9_d10'))        # canonical d = 10 has no suffix
        B.register_utility_name(n)
        ub = VS.make_utility(n)
        f = H.feature_row(depth=6)
        a, _ = VS.decide(sr, ub, f)
        self.assertEqual(f['v4_base_action'], VS.REFRESH)                      # a_det^4 at depth 6
        self.assertAlmostEqual(f['v4_mu'], 0.85 if a == VS.REFRESH else 0.15, places=12)

    def test_behaviour_around_a_det_d_propensities(self):
        sr = both()
        u = B.EpsilonRandomUtility(0.3, 21, d=4)
        for depth in (2, 7):
            base = VS.REFINE if depth < 4 else VS.REFRESH
            for _ in range(300):
                f = H.feature_row(depth=depth)
                a, _ = VS.decide(sr, u, f)
                self.assertEqual(f['v4_base_action'], base)
                self.assertAlmostEqual(f['v4_mu'], 0.85 if a == base else 0.15, places=12)

    def test_registration_in_the_v3_registry_without_editing_v3(self):
        name = B.register_behaviour(0.25, 7)
        self.assertIn(name, VS.UTILITIES)
        self.assertIn('heuristic', VS.UTILITIES)
        u = VS.make_utility(name)
        self.assertIsInstance(u, B.EpsilonRandomUtility)
        self.assertEqual((u.eps, u.seed, u.name), (0.25, 7, name))
        self.assertTrue(B.register_utility_name(name))          # idempotent

    def test_eps_zero_is_the_heuristic_and_eps_one_is_uniform(self):
        sr = both()
        u0 = B.EpsilonRandomUtility(0.0, 1)
        for _ in range(100):
            f = H.feature_row()
            self.assertEqual(VS.decide(sr, u0, f)[0], VS.REFINE)
            self.assertEqual(f['v4_mu'], 1.0)
            self.assertEqual(f['v4_explore'], 0)
        u1 = B.EpsilonRandomUtility(1.0, 2)
        n = 4000
        acts = [VS.decide(sr, u1, H.feature_row())[0] for _ in range(n)]
        k = sum(a == VS.REFRESH for a in acts)
        self.assertLess(abs(k / n - 0.5), 4 * math.sqrt(0.25 / n))
        self.assertEqual(u1.n_draws, n)
        self.assertEqual(u1.n_explore, n)

    def test_propensities_and_frequencies(self):
        eps = 0.3
        sr = both()
        u = B.EpsilonRandomUtility(eps, 11)
        n, ref = 6000, 0
        for i in range(n):
            f = H.feature_row()
            a, reason = VS.decide(sr, u, f)
            self.assertEqual(reason, f'both_feasible:{u.name}')
            want = (1 - eps) + eps / 2 if a == VS.REFINE else eps / 2
            self.assertAlmostEqual(f['v4_mu'], want, places=12)
            self.assertEqual(f['v4_base_action'], VS.REFINE)
            self.assertEqual(f['v4_draw'], i)
            ref += a == VS.REFRESH
        self.assertLess(abs(ref / n - eps / 2), 4 * math.sqrt(eps / 2 * (1 - eps / 2) / n))

    def test_never_called_or_leaving_the_set_when_forced(self):
        u = B.EpsilonRandomUtility(1.0, 5)
        only_refresh = VS.shield(10.0, 10.53, 12.5, 3, 10, True, BOUNDS)       # refine eats the recovery path
        self.assertEqual(only_refresh.feasible, (VS.REFRESH,))
        only_refine = VS.shield(10.0, 12.5, 12.5, 3, 10, False, BOUNDS)        # no newer frame
        self.assertEqual(only_refine.feasible, (VS.REFINE,))
        none = VS.shield(10.0, 10.1, 12.5, 3, 10, True, BOUNDS)
        self.assertEqual(none.feasible, ())
        for sr, want in ((only_refresh, VS.REFRESH), (only_refine, VS.REFINE), (none, VS.RECOVERY_REFRESH)):
            for _ in range(50):
                f = H.feature_row()
                self.assertEqual(VS.decide(sr, u, f)[0], want)
                self.assertNotIn('v4_mu', f)
        self.assertEqual(u.n_draws, 0)                               # Eq. 8: no utility call unless both feasible

    def test_same_seed_same_draws(self):
        sr = both()
        a = [VS.decide(sr, B.EpsilonRandomUtility(0.5, 99), H.feature_row())[0] for _ in range(1)]
        u1, u2 = B.EpsilonRandomUtility(0.5, 99), B.EpsilonRandomUtility(0.5, 99)
        s1 = [VS.decide(sr, u1, H.feature_row())[0] for _ in range(300)]
        s2 = [VS.decide(sr, u2, H.feature_row())[0] for _ in range(300)]
        self.assertEqual(s1, s2)
        self.assertEqual(a[0], s1[0])
        s3 = [VS.decide(sr, B.EpsilonRandomUtility(0.5, 100), H.feature_row())[0] for _ in range(1)]
        self.assertIn(s3[0], (VS.REFINE, VS.REFRESH))

    def test_inside_the_real_v3_runtime_timeline(self):
        """ShieldedHeuristicPolicy + V3Runtime (v2 timeline, fake backend, scripted lease) with the registered
        behaviour utility: draws happen exactly at the both-feasible epochs and every row logs its propensity."""
        import helpers_v3 as HV
        name = B.register_behaviour(1.0, 3)
        rt = HV.make_v3_runtime(lambda cand: 2.5, utility=name)
        HV.simulate(rt, 120)
        rows = HV.rows(rt, 'decisions')
        both_rows = [r for r in rows if r['p_both']]
        self.assertGreater(len(both_rows), 5)
        self.assertEqual(rt.policy.utility.n_draws, len(both_rows))
        self.assertTrue(all(r['reason'] == f'both_feasible:{name}' for r in both_rows))
        self.assertTrue(all(r['features']['v4_mu'] == 0.5 for r in both_rows))
        self.assertTrue(all(r['action'] in r['feasible'] for r in rows if r['feasible']))
        self.assertTrue(all('v4_mu' not in r['features'] for r in rows if not r['p_both']))
        acts = {r['action'] for r in both_rows}
        self.assertEqual(acts, {VS.REFINE, VS.REFRESH})
        self.assertEqual(rt.policy.describe()['utility'], name)


if __name__ == '__main__':
    unittest.main()
