"""v4 launcher (dry run only: nothing is started) and the training-route collection plan.

    cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
        framelease_v4/rl/tests/test_launcher_plan.py
    # the dry-run test needs the official stack variables (checkpoint path etc.):
    source linux/env.sh && CUDA_VISIBLE_DEVICES= .conda-unidrive-linux/bin/python -B -m pytest -q -p no:cacheprovider \
        framelease_v4/rl/tests/test_launcher_plan.py
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import unittest
from pathlib import Path

import helpers_rl as H  # noqa: F401

from framelease_v3.runtime import v3_shield as VS
from framelease_v4.rl import behaviour as B
from framelease_v4.rl import collection_plan as CP
from framelease_v4.rl import common as C

STACK = bool(os.environ.get('CHECKPOINT')) and Path(os.environ.get('CHECKPOINT', '/nonexistent')).is_file()


class PlanTest(unittest.TestCase):
    def test_plan_uses_training_routes_only_with_distinct_seeds(self):
        doc = CP.plan(eps=0.3)
        test = C.test_route_ids()
        self.assertEqual(doc['n_runs'], 132)                           # 44 training routes x kappa {1.0, 1.5, 2.0}
        self.assertEqual((doc['n_routes'], doc['n_types']), (44, 44))
        self.assertFalse({r['route_id'] for r in doc['runs']} & test)
        self.assertTrue({'2086', '18305', '2554', '1792'} <= {r['route_id'] for r in doc['runs']})
        self.assertEqual(len({r['behaviour_seed'] for r in doc['runs']}), 132)
        if doc['training_pool_check']['match'] is not None:
            self.assertTrue(doc['training_pool_check']['match'])
        for i, r in enumerate(doc['runs']):
            self.assertEqual(B.parse_behaviour(r['utility']), (0.3, r['behaviour_seed'], 10))
            self.assertEqual(r['behaviour_seed'], CP.behaviour_seed(r['route_id'], r['kappa'], r['rep']))
            argv = r['argv']
            self.assertEqual(argv[:3], ['framelease_v4/arms/run_closed_loop_v4.py', '--arm', 'fl_behaviour'])
            opt = {argv[k]: argv[k + 1] for k in range(1, len(argv) - 1) if argv[k].startswith('--')}
            self.assertEqual(opt['--fast-prefix'], 'sdpa,gpu_preproc,lora_merged')
            self.assertEqual(opt['--output-dir'], f'outputs/framelease_v4/rl_data/k{r["kappa"]:.1f}')
            self.assertEqual(opt['--port'], str(2600 + 10 * (i % 4)))
            self.assertEqual((opt['--timeout-s'], opt['--lock-wait-s']), ('1410', '600'))
            self.assertEqual(json.loads(opt['--policy-params']), {'utility': r['utility']})
        self.assertIn('not enqueued', doc['status'])
        d4 = CP.plan(eps=0.3, kappas=(1.0,), d_det=4, envelope='E.json')
        self.assertEqual(B.parse_behaviour(d4['runs'][0]['utility'])[2], 4)
        self.assertEqual(d4['runs'][0]['argv'][-2:], ['--envelope', 'E.json'])

    def test_trimmed_plan(self):
        doc = CP.plan(eps=0.3, variant='TRIMMED', envelope='E.json')
        self.assertEqual(doc['n_runs'], 44)
        self.assertEqual(doc['n_routes'], 22)
        self.assertEqual(doc['runs_per_kappa'], {'1.0': 22, '1.5': 11, '2.0': 11})
        split = json.loads(CP.ROUTE_SPLIT.read_text())
        idx = {r['route_id']: r['index'] for r in split['training']}
        self.assertTrue(all(idx[r['route_id']] % 2 == 1 for r in doc['runs']))       # outside T22
        self.assertFalse({r['route_id'] for r in doc['runs']} & set(split['subsets']['T22']))
        per_route = {}
        for r in doc['runs']:
            per_route.setdefault(r['route_id'], []).append((r['rep'], r['kappa']))
        self.assertTrue(all(sorted(v)[0] == (0, 1.0) and sorted(v)[1][0] == 1 for v in per_route.values()))
        self.assertEqual(len({r['behaviour_seed'] for r in doc['runs']}), 44)


@unittest.skipUnless(STACK, 'official stack variables not set (source linux/env.sh)')
class LauncherDryRunTest(unittest.TestCase):
    def tearDown(self):
        for k in [k for k in VS.UTILITIES if k.startswith('v4_')]:
            del VS.UTILITIES[k]

    def test_dry_run_command_and_restored_launcher(self):
        from framelease_v3.fastprefix import run_closed_loop_fast as FL
        from framelease_v4.rl import run_closed_loop_rl as RL
        before = (FL.STAGE, FL.ENTRY_NAME, FL.evaluator_env, FL.arm_label)
        name = B.behaviour_name(0.3, 5)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = RL.main(['--utility', name, '--arm', 'fl_v3_heuristic', '--route-id', '18305', '--port', '2905',
                          '--output-dir', str(C.OUT_ROOT / 'adhoc_test_never_created'), '--dry-run'])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        j = json.loads(out[out.index('{'):])
        self.assertEqual(j['status'], 'NOT_STARTED')
        self.assertEqual(j['arm'], 'fl_v4_eps0.300_fp')
        self.assertEqual(j['agent_runtime_config']['v3']['policy_params']['utility'], name)
        self.assertTrue(any(c.endswith('framelease_v4_rl_agent_entry.py') for c in j['command']))
        self.assertIn('FRAMELEASE_FASTPREFIX_CONFIG', j['environment_overrides'])
        self.assertEqual(before, (FL.STAGE, FL.ENTRY_NAME, FL.evaluator_env, FL.arm_label))   # restored
        self.assertFalse((C.OUT_ROOT / 'adhoc_test_never_created').exists())

    def test_plan_runs_dry_run_through_the_v4_launcher(self):
        """A collection-plan run is the v4 arm fl_behaviour (V4Runtime, actor log) and passes the v4 launcher."""
        import subprocess
        env_file = 'outputs/framelease_v4/envelopes/E5.json'
        if not (C.ROOT / env_file).is_file():
            self.skipTest('exported envelopes not available')
        doc = CP.plan(eps=0.3, variant='TRIMMED', envelope=env_file)
        for r in (doc['runs'][0], doc['runs'][-1]):
            cmd = [str(C.ROOT / '.conda-unidrive-linux/bin/python'), '-B'] + r['argv'] + ['--dry-run']
            p = subprocess.run(cmd, cwd=C.ROOT, capture_output=True, text=True, timeout=600,
                               env=dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1'))
            self.assertEqual(p.returncode, 0, p.stderr[-1500:])
            j = json.loads(p.stdout)
            self.assertEqual((j['status'], j['v4_arm']), ('NOT_STARTED', 'fl_behaviour'))
            self.assertEqual(j['agent_runtime_config']['utility']['name'], r['utility'])
            self.assertEqual(j['agent_runtime_config']['agent']['runtime']['kappa'], r['kappa'])
            self.assertTrue(any(c.endswith('framelease_v4_arms_agent_entry.py') for c in j['command']))
        self.assertFalse((C.ROOT / 'outputs/framelease_v4/rl_data').exists())

    def test_wrong_arm_is_refused(self):
        from framelease_v4.rl import run_closed_loop_rl as RL
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            RL.parse_args(['--utility', B.behaviour_name(0.3, 5), '--arm', 'fast_only', '--route-id', '18305',
                           '--dry-run'])


if __name__ == '__main__':
    unittest.main()
