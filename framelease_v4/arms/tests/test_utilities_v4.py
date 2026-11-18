"""Utilities of the age and shield arms (PROTOCOL Secs. 2.4, 4.4, 5.3): the depth-limited heuristic a_det^d is a
UTILITY ('v4_adet_d<d>'), registered for the age and shield arm kinds in the launcher process (build_config) and in
the agent process (build_policy); fl_heuristic / age_only accept only 'heuristic' or 'v4_adet_d<d>'; the shield depth
limit (max_depth) stays 10 everywhere; the v4 utility modules are pinned and frozen with every job. CPU only, no
official stack needed (the agent-class and launcher dry-run counterparts are in test_agent_launcher_v4.py).

  cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/arms/tests/test_utilities_v4.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers_v4 import ROOT

from framelease_v3.runtime import v3_shield as VS
from framelease_v4.arms import arms_v4 as AV
from framelease_v4.rl import behaviour as B

PY = str(ROOT / '.conda-unidrive-linux/bin/python')


def _forget_v4_utilities():
    for k in [k for k in VS.UTILITIES if k.startswith('v4_')]:
        del VS.UTILITIES[k]


class UtilityKindTest(unittest.TestCase):
    def test_kinds(self):
        cases = {None: 'heuristic', 'heuristic': 'heuristic', 'v4_adet_d1': 'adet', 'v4_adet_d4': 'adet',
                 'v4_adet_d10': 'adet', 'v4_adet_d0': None, 'v4_adet_d11': None, 'v4_adet_d04': None,
                 'v4_eps0.300_seed7': 'behaviour', 'v4_eps0.300_seed7_d4': 'behaviour',
                 'v4_eps0.300_seed7_d10': None,                       # canonical d = 10 has no suffix
                 'v4_qnet_0123456789ab': 'qnet', 'v4_qnet_xyz': None, 'adet4': None, 'v4_other': None}
        for name, kind in cases.items():
            self.assertEqual(AV.utility_kind(name), kind, name)
        self.assertEqual(AV.adet_depth('heuristic'), 10)
        self.assertEqual(AV.adet_depth('v4_adet_d4'), 4)
        with self.assertRaises(ValueError):
            AV.adet_depth('v4_eps0.300_seed7')

    def test_arm_utility_sets(self):
        self.assertEqual(AV.ARMS['fl_heuristic'].utilities, ('heuristic', 'adet'))
        self.assertEqual(AV.ARMS['age_only'].utilities, ('heuristic', 'adet'))
        self.assertEqual(AV.ARMS['fl_full'].utilities, ('qnet',))
        self.assertEqual(AV.ARMS['fl_behaviour'].utilities, ('behaviour',))
        self.assertEqual(AV.TABLE_I_ORDER, tuple(AV.ALL_ARMS[:7]))
        self.assertNotIn('fl_behaviour', AV.TABLE_I_ORDER)


class BuildConfigTest(unittest.TestCase):
    def tearDown(self):
        _forget_v4_utilities()

    def test_depth_limited_heuristic_registered_for_age_and_shield(self):
        for arm in ('age_only', 'fl_heuristic'):
            for d in (1, 4, 10):
                _forget_v4_utilities()
                name = B.adet_name(d)
                cfg, _, _ = AV.build_config(arm, policy_params={'utility': name})
                self.assertIn(name, VS.UTILITIES, (arm, d))                    # registered in this process
                self.assertEqual(cfg['utility']['name'], name)
                self.assertEqual(cfg['utility']['registrar'], AV.DEFAULT_UTILITY_REGISTRAR)
                self.assertEqual(cfg['utility']['env'], {})
                self.assertEqual(cfg['agent']['policy_params']['utility'], name)
                self.assertEqual(cfg['agent']['runtime']['max_depth'], 10)
                pol = AV.build_policy(json.loads(json.dumps(cfg)))
                self.assertIsInstance(pol.utility, B.DepthHeuristicUtility)
                self.assertEqual((pol.utility.name, pol.utility.d, pol.params['max_depth']), (name, d, 10))

    def test_default_heuristic_has_no_utility_block(self):
        for arm in ('age_only', 'fl_heuristic'):
            for pp in ({}, {'utility': 'heuristic'}):
                cfg, _, _ = AV.build_config(arm, policy_params=pp)
                self.assertNotIn('utility', cfg)
                self.assertEqual(AV.build_policy(cfg).utility.name, 'heuristic')

    def test_behaviour_arm(self):
        name = B.behaviour_name(0.3, 123456789, 4)
        cfg, _, _ = AV.build_config('fl_behaviour', policy_params={'utility': name})
        pol = AV.build_policy(json.loads(json.dumps(cfg)))
        self.assertIsInstance(pol.utility, B.EpsilonRandomUtility)
        self.assertEqual((pol.utility.eps, pol.utility.seed, pol.utility.d), (0.3, 123456789, 4))

    def test_wrong_utilities_are_rejected(self):
        bad = [('fl_heuristic', {'utility': 'v4_eps0.300_seed1'}), ('fl_heuristic', {'utility': 'v4_qnet_0123456789ab'}),
               ('fl_heuristic', {'utility': 'v4_adet_d11'}), ('fl_heuristic', {'utility': 'mystery'}),
               ('age_only', {'utility': 'v4_eps0.300_seed1'}), ('age_only', {'utility': 'v4_qnet_0123456789ab'}),
               ('fl_full', {}), ('fl_full', {'utility': 'heuristic'}), ('fl_full', {'utility': 'v4_adet_d4'}),
               ('fl_full', {'utility': 'v4_eps0.300_seed1'}), ('fl_behaviour', {}),
               ('fl_behaviour', {'utility': 'v4_adet_d4'}), ('fast_only', {'utility': 'heuristic'}),
               ('event_triggered', {'utility': 'v4_adet_d4'})]
        for arm, pp in bad:
            with self.assertRaises(ValueError, msg=(arm, pp)):
                AV.build_config(arm, policy_params=pp)
        with self.assertRaises(ValueError):                                  # env only for the Q-network
            AV.build_config('fl_heuristic', policy_params={'utility': 'v4_adet_d4'},
                            utility_env={'FRAMELEASE_V4_QNET': '/nonexistent.json'})

    def test_depth_is_never_tuned_through_max_depth(self):
        for arm, pp in (('fl_heuristic', {}), ('age_only', {}), ('fl_behaviour', {'utility': 'v4_eps0.300_seed1'})):
            for d in (1, 4, 9):
                with self.assertRaises(ValueError, msg=(arm, d)):
                    AV.build_config(arm, policy_params={**pp, 'max_depth': d})
                with self.assertRaises(ValueError, msg=(arm, d)):
                    AV.build_config(arm, policy_params=pp, runtime_params={'max_depth': d})
            cfg, _, _ = AV.build_config(arm, policy_params={**pp, 'max_depth': 10})       # the shield's own limit
            self.assertEqual(AV.build_policy(cfg).params['max_depth'], 10)

    def test_agent_side_rechecks_the_configuration(self):
        cfg, _, _ = AV.build_config('fl_heuristic', policy_params={'utility': 'v4_adet_d4'})
        tampered = json.loads(json.dumps(cfg))
        del tampered['utility']
        with self.assertRaises(ValueError):
            AV.agent_config_from(tampered)
        tampered = json.loads(json.dumps(cfg))
        tampered['utility']['name'] = 'v4_adet_d1'
        with self.assertRaises(ValueError):
            AV.agent_config_from(tampered)
        tampered = json.loads(json.dumps(cfg))
        for blk in (tampered['agent'], tampered['v3']):
            blk['policy_params']['max_depth'] = 4
        with self.assertRaises(ValueError):
            AV.agent_config_from(tampered)
        cfg, _, _ = AV.build_config('age_only', policy_params={'utility': 'v4_adet_d4'})
        tampered = json.loads(json.dumps(cfg))
        tampered['agent']['runtime']['max_depth'] = 4
        with self.assertRaises(ValueError):
            AV.agent_config_from(tampered)


class AgentProcessRegistrationTest(unittest.TestCase):
    """A fresh interpreter (the evaluator's agent process): nothing is registered until build_policy runs."""

    def run_fresh(self, cfg):
        code = (
            'import json, sys\n'
            f'sys.path.insert(0, {str(ROOT)!r})\n'
            'from framelease_v3.runtime import v3_shield as VS\n'
            'from framelease_v4.arms import arms_v4 as AV\n'
            'cfg = json.load(open(sys.argv[1]))\n'
            'name = cfg["agent"]["policy_params"].get("utility")\n'
            'before = name in VS.UTILITIES\n'
            'AV.agent_config_from(cfg)\n'
            'pol = AV.build_policy(cfg)\n'
            'print(json.dumps({"before": before, "after": name in VS.UTILITIES, "utility": pol.utility.name,\n'
            '                  "cls": type(pol.utility).__name__, "d": getattr(pol.utility, "d", None),\n'
            '                  "policy": type(pol).__name__, "max_depth": pol.params["max_depth"]}))\n')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'cfg.json'
            path.write_text(json.dumps(cfg))
            p = subprocess.run([PY, '-I', '-B', '-c', code, str(path)], capture_output=True, text=True, timeout=300,
                               env={'CUDA_VISIBLE_DEVICES': '', 'PATH': '/usr/bin:/bin'})
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        return json.loads(p.stdout.strip().splitlines()[-1])

    def test_age_and_shield_register_in_a_fresh_process(self):
        cases = [('age_only', {'utility': 'v4_adet_d4', 'age_lease_s': 1.5}, 'AgeLeasePolicy', 'DepthHeuristicUtility', 4),
                 ('fl_heuristic', {'utility': 'v4_adet_d1'}, 'ShieldedHeuristicPolicy', 'DepthHeuristicUtility', 1),
                 ('fl_behaviour', {'utility': 'v4_eps0.300_seed42_d4'}, 'ShieldedHeuristicPolicy',
                  'EpsilonRandomUtility', 4)]
        for arm, pp, pol_cls, util_cls, d in cases:
            cfg, _, _ = AV.build_config(arm, policy_params=pp)
            out = self.run_fresh(json.loads(json.dumps(cfg)))
            self.assertEqual((out['before'], out['after']), (False, True), arm)
            self.assertEqual((out['policy'], out['cls'], out['d'], out['utility'], out['max_depth']),
                             (pol_cls, util_cls, d, pp['utility'], 10), arm)
        _forget_v4_utilities()


class PinsTest(unittest.TestCase):
    def test_v4_utility_modules_are_pinned_and_frozen(self):
        from framelease_v4.arms import jobs_v4 as J
        from framelease_v4.arms import run_closed_loop_v4 as RL
        want = {'framelease_v4/rl/__init__.py', 'framelease_v4/rl/behaviour.py', 'framelease_v4/rl/features.py',
                'framelease_v4/rl/qnet.py'}
        self.assertEqual(set(RL.V4_UTILITY_CODE), want)
        self.assertTrue(want <= set(RL.V4_CODE))
        self.assertEqual(set(J.V4_PINNED), set(RL.V4_CODE))
        pins = J.code_pins()
        self.assertTrue(want <= set(pins))
        for mod in ('behaviour', 'qnet', 'features'):                         # the agent imports only these
            src = (ROOT / f'framelease_v4/rl/{mod}.py').read_text()
            for line in src.splitlines():
                s = line.strip()
                if s.startswith('from framelease_v4') or s.startswith('import framelease_v4'):
                    target = s.split()[1].replace('.', '/')
                    imported = s.split()[3] if s.startswith('from') and len(s.split()) > 3 else None
                    rel = f'{target}/{imported}.py' if imported else f'{target}.py'
                    self.assertIn(rel, want | {'framelease_v4/__init__.py'}, (mod, s))


if __name__ == '__main__':
    unittest.main()
