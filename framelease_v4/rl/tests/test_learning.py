"""Trainers (FQI, bandit, FQI without lease features), distillation, export, and OPE on toy SMDPs with known optima.

    cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
        framelease_v4/rl/tests/test_learning.py
"""
from __future__ import annotations

import json
import unittest

import helpers_rl as H

import numpy as np

from framelease_v4.rl import ope as O
from framelease_v4.rl import qnet as Q
from framelease_v4.rl import trainers as TR

KW = dict(min_samples_leaf=5, n_estimators=40, min_support=5)


def agreement(ds, cand, test):
    q, info = TR.fit_candidate(ds, list(range(len(ds.episodes))), cand)
    pi = TR.policy_fn(q, cand)(test.X)
    opt = H.optimal_actions(test.X)
    return float(np.mean(pi == opt)), float(np.mean(pi[opt == 1] == 1)), q, info


class TrainerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = H.toy_dataset(n_episodes=60, steps=12, eps=0.5, seed=0)
        cls.test = H.toy_dataset(n_episodes=30, steps=12, eps=0.5, seed=1)

    def test_fqi_learns_the_delayed_credit_and_the_bandit_does_not(self):
        a_fqi, r_fqi, _, info = agreement(self.ds, TR.Candidate('fqi', horizon=3, **KW), self.test)
        a_bandit, r_bandit, _, _ = agreement(self.ds, TR.Candidate('bandit', window='step', **KW), self.test)
        self.assertGreaterEqual(a_fqi, 0.95)
        self.assertGreaterEqual(r_fqi, 0.95)
        self.assertLessEqual(r_bandit, 0.5)            # myopic: the +1 of its own REFRESH arrives one step later
        self.assertEqual(len(info['iterations']), 3)
        self.assertEqual(info['supported'], [True, True])

    def test_no_lease_ablation_cannot_see_the_lease_signal(self):
        a_full, _, _, _ = agreement(self.ds, TR.Candidate('fqi', horizon=3, **KW), self.test)
        a_nl, _, _, _ = agreement(self.ds, TR.Candidate('fqi_nolease', horizon=3, **KW), self.test)
        self.assertGreaterEqual(a_full - a_nl, 0.3)
        self.assertEqual(len(TR.Candidate('fqi_nolease').columns), 10)
        self.assertNotIn(0, TR.Candidate('fqi_nolease').columns)       # lease_slack_s is column 0

    def test_without_refresh_support_every_family_is_a_det(self):
        ds = H.toy_dataset(n_episodes=20, steps=10, eps=0.0, seed=2)  # heuristic-only data: REFRESH never logged
        for fam in TR.FAMILIES:
            cand = TR.Candidate(fam, horizon=2, **KW)
            q, info = TR.fit_candidate(ds, list(range(20)), cand)
            self.assertEqual(info['supported'], [True, False])
            self.assertTrue(np.all(TR.policy_fn(q, cand)(self.test.X) == 0))

    def test_pessimism_only_reduces_deviations(self):
        base = TR.Candidate('fqi', horizon=3, **KW)
        pess = TR.Candidate('fqi', horizon=3, beta=3.0, **KW)
        q0, _ = TR.fit_candidate(self.ds, list(range(60)), base)
        q1, _ = TR.fit_candidate(self.ds, list(range(60)), pess)
        p0 = TR.policy_fn(q0, base)(self.test.X)
        p1 = TR.policy_fn(q1, pess)(self.test.X)
        self.assertTrue(np.all(p1 <= p0))                               # REFRESH only where the plain policy has it
        self.assertLess(np.mean(p1), np.mean(p0) + 1e-12)

    def test_depth_limited_default_action(self):
        d1 = TR.Candidate('fqi', horizon=3, d_det=1, **KW)                  # default REFRESH everywhere (depth >= 1)
        self.assertEqual(d1.label, 'fqi_K3_leaf5_beta0_d1')
        self.assertTrue(np.all(TR.heuristic_policy_fn(1)(self.test.X) == 1))
        self.assertTrue(np.all(TR.heuristic_policy_fn(10)(self.test.X) == 0))
        a1, r1, _, _ = agreement(self.ds, d1, self.test)
        self.assertGreaterEqual(a1, 0.95)                                    # deviates to REFINE where c = 0
        X = self.test.X.copy()
        X[:, TR.DEPTH_COL] = np.where(np.arange(len(X)) % 2 == 0, 3.0, 7.0)
        dflt = TR.default_actions(X, 5)
        np.testing.assert_array_equal(dflt, (X[:, TR.DEPTH_COL] >= 5).astype(np.int8))
        Q = np.zeros((len(X), 2))
        np.testing.assert_array_equal(TR.greedy(Q, [True, True], 0.0, dflt), dflt)   # ties keep the default
        np.testing.assert_array_equal(TR.greedy(Q + [[0, 1]], [True, False], 0.0, dflt), dflt)  # unsupported

    def test_refuses_test_episodes_and_bad_candidates(self):
        ds = H.toy_dataset(n_episodes=4, steps=5, seed=3)
        ds.episodes[1]['split'] = 'test'
        with self.assertRaises(PermissionError):
            TR.fit_candidate(ds, [0, 1], TR.Candidate('fqi', horizon=1, **KW))
        with self.assertRaises(ValueError):
            TR.Candidate('dqn')
        self.assertEqual(len(TR.grid('fqi')), 12)
        self.assertEqual(len(TR.grid('bandit')), 12)
        self.assertEqual(len(TR.grid('fqi_nolease')), 12)

    def test_distill_export_and_load(self):
        cand = TR.Candidate('fqi', horizon=3, **KW)
        q, _ = TR.fit_candidate(self.ds, list(range(60)), cand)
        states = np.concatenate([self.ds.X, self.ds.XN[~self.ds.DONE]])
        mlp, fid = TR.distill(q, cand, states, epochs=300, seed=0)
        self.assertTrue(fid['ok'], fid)
        self.assertGreaterEqual(fid['final']['agreement'], 0.98)
        spec = json.loads(json.dumps(TR.export_qnet(mlp, cand, q.supported, provenance={'test': True})))
        self.assertEqual(Q.verify_spec(spec), spec['weights_sha256'])
        net = Q.QNetwork(spec)
        for x in self.test.X[:50]:
            np.testing.assert_allclose(net.forward(x.copy()), TR.mlp_forward(mlp['W'], mlp['b'], x[None])[0][0],
                                       rtol=1e-12, atol=1e-12)
        bad = json.loads(json.dumps(spec))
        bad['layers'][0]['b'][0] += 1e-3
        with self.assertRaises(ValueError):
            Q.verify_spec(bad)

    def test_masked_mlp_fits_supported_heads_only(self):
        rng = np.random.default_rng(0)
        X = rng.uniform(-1, 1, (600, 4))
        T = np.stack([X[:, 0] * 2 + X[:, 1], np.full(600, np.nan)], 1)
        mlp = TR.train_mlp(X, T, [True, False], hidden=(16, 16), epochs=300, seed=1)
        out, _ = TR.mlp_forward(mlp['W'], mlp['b'], X)
        self.assertLess(np.sqrt(np.mean((out[:, 0] - T[:, 0]) ** 2)), 0.1)


class OPETest(unittest.TestCase):
    def test_on_policy_fqe_with_exact_regressor_reproduces_the_returns(self):
        ds = H.toy_dataset(n_episodes=12, steps=8, eps=0.0, seed=5)          # behaviour = a_det
        ids = list(range(12))
        res = O.fqe(ds, ids, TR.heuristic_policy, O.FQEConfig(n_estimators=5, min_samples_leaf=1, min_support=1))
        self.assertEqual(res['iterations'], 2)                                # on-policy: no bootstrap point
        self.assertTrue(res['converged'])
        one = O.fqe(ds, ids, TR.heuristic_policy, O.FQEConfig(n_estimators=5, min_samples_leaf=1, min_support=1,
                                                               trace='one_step'))
        self.assertEqual(one['iterations'], 9)                                # longest episode 8 choice steps + 1
        for i in ids:
            self.assertAlmostEqual(one['V'][i], ds.episodes[i]['ds'], places=9)
        for i in ids:
            self.assertAlmostEqual(res['V'][i], ds.episodes[i]['ds'], places=9)
        diag = O.importance_diagnostics(ds, ids, TR.heuristic_policy)
        self.assertAlmostEqual(diag['wpdis'], np.mean([e['ds'] for e in ds.episodes]), places=9)
        self.assertAlmostEqual(diag['ess_final'], 12.0, places=9)

    def test_off_policy_fqe_matches_the_true_value_of_a_new_policy(self):
        ds = H.toy_dataset(n_episodes=120, steps=12, eps=0.5, seed=10)
        ids = list(range(120))
        opt = lambda X: H.optimal_actions(X)                                  # noqa: E731
        truth_opt = H.toy_policy_value(opt)
        truth_det = H.toy_policy_value(TR.heuristic_policy)
        self.assertGreater(truth_opt, 1.0)
        self.assertAlmostEqual(truth_det, 0.0, places=12)
        cfg = O.FQEConfig(n_estimators=30, min_samples_leaf=3, min_support=3)
        v_opt = np.mean(list(O.fqe(ds, ids, opt, cfg)['V'].values()))
        v_det = np.mean(list(O.fqe(ds, ids, TR.heuristic_policy, cfg)['V'].values()))
        self.assertLess(abs(v_opt - truth_opt), 0.25 * truth_opt)
        self.assertLess(abs(v_det - truth_det), 0.5)
        self.assertGreater(v_opt - v_det, 0.5 * (truth_opt - truth_det))

    def test_behaviour_calibration_is_exact_with_an_exact_regressor(self):
        ds = H.toy_dataset(n_episodes=10, steps=6, eps=0.0, seed=9)
        cal = O.behaviour_calibration(ds, list(range(10)), O.FQEConfig(n_estimators=5, min_samples_leaf=1,
                                                                        min_support=1))
        self.assertAlmostEqual(cal['bias'], 0.0, places=9)
        self.assertAlmostEqual(cal['mc_mean'], np.mean([e['ds'] for e in ds.episodes]), places=12)

    def test_unsupported_policy_is_flagged(self):
        ds = H.toy_dataset(n_episodes=6, steps=6, eps=0.0, seed=6)
        res = O.fqe(ds, list(range(6)), lambda X: np.ones(len(X), dtype=np.int8))
        self.assertGreater(res['unsupported_frac'], 0)
        self.assertTrue(all(np.isnan(v) for v in res['V'].values()))

    def test_route_folds_and_cluster_bootstrap(self):
        ds = H.toy_dataset(n_episodes=30, steps=4, seed=7)                    # 10 routes x 3 episodes
        folds = O.route_folds(ds, list(range(30)), 5)
        self.assertEqual(len(folds), 5)
        self.assertEqual(sorted(i for f in folds for i in f), list(range(30)))
        for f in folds:
            routes = {ds.episodes[i]['route_id'] for i in f}
            others = {ds.episodes[i]['route_id'] for g in folds if g is not f for i in g}
            self.assertFalse(routes & others)
        b = O.cluster_bootstrap({i: 1.0 for i in range(30)}, {i: ds.episodes[i]['route_id'] for i in range(30)})
        self.assertEqual((b['mean'], b['lo'], b['hi'], b['n_routes']), (1.0, 1.0, 1.0, 10))

    def test_selection_prefers_the_lookahead_candidate(self):
        ds = H.toy_dataset(n_episodes=40, steps=10, eps=0.5, seed=8)
        cands = [TR.Candidate('fqi', horizon=1, **KW), TR.Candidate('fqi', horizon=3, **KW)]
        rep = O.select(ds, cands, list(range(40)), n_folds=4,
                       fqe_cfg=O.FQEConfig(n_estimators=20, min_samples_leaf=3, min_support=3), n_boot=200)
        self.assertEqual(rep['selected'], 'fqi_K3_leaf5_beta0')
        rows = {r['label']: r for r in rep['candidates']}
        self.assertGreater(rows['fqi_K3_leaf5_beta0']['mean_delta'], rows['fqi_K1_leaf5_beta0']['mean_delta'])
        self.assertGreater(rows['fqi_K3_leaf5_beta0']['mean_delta'], 0.0)    # better than a_det on held-out routes
        self.assertEqual(rep['n_folds'], 4)


if __name__ == '__main__':
    unittest.main()
