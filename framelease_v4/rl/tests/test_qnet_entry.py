"""CPU Q-network utility (Eq. 6 / 8, budgeted call, bypass) and the v4 evaluator agent entry (no torch / CARLA).

    cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
        framelease_v4/rl/tests/test_qnet_entry.py
"""
from __future__ import annotations

import json
import os
import tempfile
import types
import unittest
from pathlib import Path

import helpers_rl as H

import numpy as np

from framelease_v3.runtime import v3_shield as VS
from framelease_v4.rl import agent_entry as AE
from framelease_v4.rl import behaviour as B
from framelease_v4.rl import features as F
from framelease_v4.rl import qnet as Q
from framelease_v4.rl import trainers as TR

BOUNDS = VS.ShieldBounds(L_pi=0.001, L_refine=0.02, L_refresh=0.47, L_commit=0.001, eps=0.05)
BOTH = VS.shield(10.0, 12.5, 12.5, 3, 10, True, BOUNDS)
ONLY_REFRESH = VS.shield(10.0, 10.53, 12.5, 3, 10, True, BOUNDS)


def spec_from(Ws, bs, supported=(True, True), family='fqi', margin=0.0, budget=1e-3, d_det=10):
    cand = TR.Candidate(family, margin=margin, d_det=d_det)
    return json.loads(json.dumps(TR.export_qnet({'W': Ws, 'b': bs}, cand, list(supported), policy_budget_s=budget)))


def linear_spec(w_refresh_minus_refine, supported=(True, True), budget=1e-3, d_det=10):
    """1 hidden layer with identity-like ReLU on lease_slack (>= 0 after shift): Q_REFRESH - Q_REFINE = w * relu(x0+3)."""
    W1 = np.zeros((F.N_FEATURES, 1))
    W1[0, 0] = 1.0
    b1 = np.array([3.0])                                              # lease slack clipped to [-3, 3] -> [0, 6]
    W2 = np.array([[0.0, w_refresh_minus_refine]])
    b2 = np.array([0.0, -3.0 * w_refresh_minus_refine])               # Q_REFRESH - Q_REFINE = w * slack
    return spec_from([W1, W2], [b1, b2], supported, budget=budget, d_det=d_det)


class FakeTimer:
    def __init__(self, dt):
        self.dt = dt
        self.t = 0.0

    def __call__(self):                                               # every read advances by dt
        self.t += self.dt
        return self.t


class QNetTest(unittest.TestCase):
    def tearDown(self):
        for k in [k for k in VS.UTILITIES if k.startswith('v4_')]:
            del VS.UTILITIES[k]
        os.environ.pop(Q.ENV_QNET, None)

    def test_argmax_inside_the_feasible_set(self):
        u = Q.QUtility(linear_spec(1.0))
        f = H.feature_row(lease_slack_s=1.0)
        self.assertEqual(VS.decide(BOTH, u, f)[0], VS.REFRESH)          # Q_REFRESH - Q_REFINE = +1
        self.assertAlmostEqual(f['v4_q_refresh'] - f['v4_q_refine'], 1.0, places=12)
        self.assertIsNone(f['v4_bypass'])
        self.assertEqual(f['v4_mu'], 1.0)
        f = H.feature_row(lease_slack_s=-1.0)
        self.assertEqual(VS.decide(BOTH, u, f)[0], VS.REFINE)
        f = H.feature_row(lease_slack_s=0.0)
        self.assertEqual(VS.decide(BOTH, u, f)[0], VS.REFINE)           # tie -> a_det

    def test_depth_limited_default_and_deviation_back_to_refine(self):
        u = Q.QUtility(linear_spec(1.0, d_det=4))
        self.assertEqual(u.d_det, 4)
        f = H.feature_row(lease_slack_s=-1.0, depth=6)                     # default REFRESH; Q prefers REFINE
        self.assertEqual(VS.decide(BOTH, u, f)[0], VS.REFINE)
        f = H.feature_row(lease_slack_s=1.0, depth=6)                      # default REFRESH; Q agrees
        self.assertEqual(VS.decide(BOTH, u, f)[0], VS.REFRESH)
        f = H.feature_row(lease_slack_s=0.0, depth=6)                      # tie keeps the default
        self.assertEqual(VS.decide(BOTH, u, f)[0], VS.REFRESH)
        byp = Q.QUtility(linear_spec(-5.0, d_det=4), budget_s=1e6)          # slack bypass -> a_det^4
        self.assertEqual(VS.decide(BOTH, byp, H.feature_row(depth=6))[0], VS.REFRESH)
        self.assertEqual(VS.decide(BOTH, byp, H.feature_row(depth=2))[0], VS.REFINE)
        bad = dict(linear_spec(1.0))
        bad['a_det'] = 'REFINE'
        with self.assertRaises(ValueError):
            Q.verify_spec(bad)

    def test_not_invoked_unless_both_feasible(self):
        u = Q.QUtility(linear_spec(1.0))
        f = H.feature_row(lease_slack_s=1.0)
        self.assertEqual(VS.decide(ONLY_REFRESH, u, f)[0], VS.REFRESH)
        self.assertEqual((u.n_select, u.n_calls), (0, 0))
        self.assertNotIn('v4_q_refine', f)
        self.assertEqual(u.select(f, (VS.REFINE,)), VS.REFINE)        # direct misuse: a_det, no network call
        self.assertEqual((u.n_not_both, u.n_calls), (1, 0))

    def test_unsupported_refresh_head_never_deviates(self):
        u = Q.QUtility(linear_spec(5.0, supported=(True, False)))
        for s in np.linspace(-3, 3, 13):
            f = H.feature_row(lease_slack_s=float(s))
            self.assertEqual(VS.decide(BOTH, u, f)[0], VS.REFINE)
            self.assertIsNone(f['v4_q_refresh'])

    def test_budget_bypass_and_overrun(self):
        u = Q.QUtility(linear_spec(1.0, budget=1e-3))
        f = H.feature_row(lease_slack_s=1.0, refine_margin_s=5e-4)          # margin below the policy budget
        self.assertEqual(VS.decide(BOTH, u, f)[0], VS.REFINE)
        self.assertEqual((f['v4_bypass'], u.n_calls, u.bypass['slack']), ('slack', 0, 1))
        slow = Q.QUtility(linear_spec(1.0, budget=1e-3), timer=FakeTimer(2e-3))   # every call takes 2 ms
        f = H.feature_row(lease_slack_s=1.0)
        self.assertEqual(VS.decide(BOTH, slow, f)[0], VS.REFINE)                 # late result discarded -> a_det
        self.assertEqual(f['v4_bypass'], 'overrun')
        for _ in range(Q.QUtility.MIN_CALLS_TO_DISABLE):
            VS.decide(BOTH, slow, H.feature_row(lease_slack_s=1.0))
        self.assertTrue(slow.disabled)
        n = slow.n_calls
        f = H.feature_row(lease_slack_s=1.0)
        self.assertEqual(VS.decide(BOTH, slow, f)[0], VS.REFINE)
        self.assertEqual((f['v4_bypass'], slow.n_calls), ('disabled', n))

    def test_fixed_weights_preallocated_buffers(self):
        rng = np.random.default_rng(0)
        Ws = [rng.normal(size=(16, 32)), rng.normal(size=(32, 32)), rng.normal(size=(32, 2))]
        bs = [rng.normal(size=32), rng.normal(size=32), rng.normal(size=2)]
        net = Q.QNetwork(spec_from(Ws, bs))
        for W, b in net.layers:
            self.assertFalse(W.flags.writeable or b.flags.writeable)
        out_ids = set()
        for _ in range(20):
            x = rng.normal(size=16)
            out = net.forward(x)
            out_ids.add(id(out))
            np.testing.assert_allclose(out, TR.mlp_forward(Ws, bs, x[None])[0][0], rtol=1e-12, atol=1e-12)
        self.assertEqual(len(out_ids), 1)
        with self.assertRaises(ValueError):
            net.layers[0][0][0, 0] = 1.0

    def test_registered_name_loads_the_pinned_file(self):
        spec = linear_spec(1.0)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'q.json'
            path.write_text(json.dumps(spec))
            os.environ[Q.ENV_QNET] = str(path)
            self.assertTrue(B.register_utility_name(spec['name']))
            u = VS.make_utility(spec['name'])
            self.assertIsInstance(u, Q.QUtility)
            self.assertEqual(VS.decide(BOTH, u, H.feature_row(lease_slack_s=2.0)),
                             (VS.REFRESH, f'both_feasible:{spec["name"]}'))
            other = linear_spec(2.0)
            path.write_text(json.dumps(other))                           # a different model behind the same name
            with self.assertRaises(ValueError):
                VS.make_utility(spec['name'])


class AgentEntryTest(unittest.TestCase):
    def tearDown(self):
        for k in [k for k in VS.UTILITIES if k.startswith('v4_')]:
            del VS.UTILITIES[k]
        for v in (AE.ENV_V3_CONFIG, AE.ENV_FASTPREFIX_CONFIG):
            os.environ.pop(v, None)

    def test_entry_registers_and_installs(self):
        name = B.behaviour_name(0.3, 42)
        with tempfile.TemporaryDirectory() as tmp:
            cfgp = Path(tmp) / 'agent_runtime_config.json'
            cfgp.write_text(json.dumps({'agent': {}, 'v3': {'policy_params': {'utility': name}}}))
            os.environ[AE.ENV_V3_CONFIG] = str(cfgp)
            self.assertEqual(AE.configured_utility(), name)
            calls = []

            class FakeBase:                                               # stands in for the v3 agent class
                def setup(self, conf):
                    calls.append(conf)
                    util = VS.make_utility(name)                          # what make_v3_policy does
                    self._fl_dir = tmp
                    self._fl_runtime = types.SimpleNamespace(policy=types.SimpleNamespace(utility=util),
                                                             summary=lambda: {'v3': {}})

            orig = AE._base_class
            AE._base_class = lambda: FakeBase
            try:
                cls_name = AE.get_entry_point()
                cls = getattr(AE, cls_name)
                agent = cls()
                agent.setup('conf.py')
            finally:
                AE._base_class = orig
            self.assertEqual(calls, ['conf.py'])
            self.assertIn(name, VS.UTILITIES)
            man = json.loads((Path(tmp) / AE.MANIFEST_NAME).read_text())
            self.assertEqual((man['utility'], man['stage']), (name, 'setup'))
            s = agent._fl_runtime.summary()
            self.assertEqual(s['v4_rl']['utility'], name)
            self.assertEqual(s['v4_rl']['stats']['eps'], 0.3)
            self.assertEqual(json.loads((Path(tmp) / AE.MANIFEST_NAME).read_text())['stage'], 'final')

    def test_entry_refuses_a_policy_without_the_configured_utility(self):
        name = B.behaviour_name(0.3, 43)
        B.register_utility_name(name)
        agent = types.SimpleNamespace(_fl_dir='/nonexistent', _fl_runtime=types.SimpleNamespace(
            policy=types.SimpleNamespace(utility=VS.HeuristicUtility()), summary=lambda: {}))
        with self.assertRaises(RuntimeError):
            AE.install_v4(agent, name)

    def test_entry_source_imports_only_the_v4_entry(self):
        self.assertIn('from framelease_v4.rl import agent_entry as _impl', AE.ENTRY_SOURCE)
        compile(AE.ENTRY_SOURCE, AE.ENTRY_NAME, 'exec')


if __name__ == '__main__':
    unittest.main()
