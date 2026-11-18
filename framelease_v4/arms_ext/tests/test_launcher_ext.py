"""CPU tests of the extension launcher framelease_v4/arms_ext/run_closed_loop_ext.py and of its job lines (PROTOCOL
Secs. 4.1, 7.4, 8.2-8.3; GAP_AUDIT Sec. 2). Every launcher call is a --dry-run, in a fresh `python -I -B` interpreter
or in process: nothing is started (no CARLA, no GPU, no queue) and nothing is written outside temporary directories.
The launcher's preflight checks the files of CHECKPOINT and CARLA_ROOT (linux/env.sh); without them the tests skip.

  cd /home/kang/Desktop/DAC && source linux/env.sh && export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 && \
      nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/arms_ext/tests/test_launcher_ext.py

What is shown:
  * additive only: for each of the 8 arms_v4 arms, the extension launcher's --dry-run output is byte-identical to the
    pinned launcher's for the same arguments (no field differs by construction: the dry run prints a placeholder run
    directory, no time stamp); in process, the extension's parse_args returns the pinned parser's namespace, and the
    pinned launcher refuses fl_global_shield (it is not an arms_v4 arm);
  * fl_global_shield against the pinned launcher's fl_heuristic with the same arguments: the dry runs differ only in
    the arm labels (arm, v4_arm, title; the configuration's arm, title and description; the fast-prefix block's arm
    labels), the evaluator's agent entry (framelease_v4_arms_ext_agent_entry.py) and the 'extension' blocks; the
    route, working directory, the rest of the evaluator command, its environment, ports and the agent / v3 / utility /
    actor-log blocks are equal;
  * a dry run writes nothing; invalid configurations are refused before anything starts;
  * the copied run(): with run_closed_loop_fast.execute replaced in this process by a stub that starts nothing (and a
    dummy checkpoint file), the extension launcher writes the pinned launcher's run layout (the pinned run() of
    fl_heuristic with the same stub and arguments) plus exactly the extension's entry and frozen sources: the same
    v3 / fast-prefix source freezes, the v4 source freeze plus the 5 extension files, configurations that differ only
    in the labels and the extension block, the same evaluator command and environment apart from the entry and the run
    directory, and a StageRun ledger whose code identity names the extension sources and the pinned launcher;
  * the job line of the new arm: its pins are exactly the pins of a registered P1 fl_heuristic line (the 49 common
    paths with the same sha256, and E*) plus the 5 extension sources; its command is the P1 command with the extension
    launcher and arm; it passes gpu_queue's contract, the launcher's in-process preparation and the dry run of its
    exact command (run with -I), with the same configuration; a changed pin is reported;
  * fixed lease constants (PROTOCOL Secs. 2.4, 7.4): the launcher refuses --lease-overrides for fl_global_shield, a
    job line that carries them is reported, and check_job_line itself reports a configuration with lease overrides or
    a cap other than 2.5 s (preparation replaced in this process by one that does not refuse them).
"""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import helpers_ext as H

from framelease_common import file_hash
from framelease_v4.arms import arms_v4 as AV

GS_ARM = 'fl_global_shield'


def swap_arm(argv, arm):
    out = list(argv)
    out[out.index('--arm') + 1] = arm
    return out


@unittest.skipUnless(H.stack_ready(), 'CHECKPOINT / CARLA_ROOT not set (source linux/env.sh)')
class LauncherTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from framelease_v4.arms import run_closed_loop_v4 as RV4
        from framelease_v4.arms_ext import agent_ext as AGX
        from framelease_v4.arms_ext import arms_ext as X
        from framelease_v4.arms_ext import run_closed_loop_ext as RX
        cls.RV4, cls.RX, cls.X, cls.AGX = RV4, RX, X, AGX

    def test_arms_v4_dry_runs_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            for arm in AV.ALL_ARMS:
                argv = H.launcher_argv(arm, out)
                a = H.dry_run(H.EXT_LAUNCHER_REL, argv)
                b = H.dry_run(H.PINNED_LAUNCHER_REL, argv)
                self.assertEqual((a.returncode, b.returncode), (0, 0), (arm, a.stderr[-1500:], b.stderr[-1500:]))
                self.assertEqual(a.stdout, b.stdout, arm)
                d = json.loads(a.stdout)
                self.assertEqual((d['status'], d['v4_arm']), ('NOT_STARTED', arm))
                self.assertNotIn('extension', d)
            self.assertFalse(out.exists())                                    # a dry run writes nothing

    def test_parsing_is_the_pinned_parser(self):
        RV4, RX = self.RV4, self.RX
        for arm in AV.ALL_ARMS:
            argv = H.launcher_argv(arm, '/tmp/unused_arms_ext')
            self.assertEqual(vars(RX.parse_args(argv)), vars(RV4.parse_args(argv)), arm)
        argv = H.launcher_argv(GS_ARM, '/tmp/unused_arms_ext')
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            RV4.parse_args(argv)                                              # not an arms_v4 arm
        for form in (argv, [a if a != '--arm' else '--arm=' + GS_ARM for a in argv if a != GS_ARM]):
            got = vars(RX.parse_args(form))
            want = vars(RV4.parse_args(swap_arm(argv, 'fl_heuristic')))
            self.assertEqual(got.pop('arm'), GS_ARM)
            want.pop('arm')
            self.assertEqual(got, want)
        self.assertEqual(RX.requested_arm(['--route-id', '1', '--arm', 'fixed_deep', '--arm', GS_ARM]), GS_ARM)
        self.assertIsNone(RX.requested_arm(['--route-id', '1']))

    def test_global_shield_dry_run_differs_from_fl_heuristic_only_by_labels(self):
        X, AGX = self.X, self.AGX
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            argv = H.launcher_argv(GS_ARM, out)
            a = H.dry_run(H.EXT_LAUNCHER_REL, argv)
            b = H.dry_run(H.PINNED_LAUNCHER_REL, swap_arm(argv, 'fl_heuristic'))
            self.assertEqual((a.returncode, b.returncode), (0, 0), (a.stderr[-1500:], b.stderr[-1500:]))
            da, db = json.loads(a.stdout), json.loads(b.stdout)
            ext = da.pop('extension')
            self.assertEqual(sorted(k for k in set(da) | set(db) if da.get(k) != db.get(k)),
                             ['agent_runtime_config', 'arm', 'command', 'title', 'v4_arm'])
            self.assertEqual((da['arm'], da['v4_arm'], db['arm'], db['v4_arm']),
                             ('fl_global_shield_fp', GS_ARM, 'fl_heuristic_fp', 'fl_heuristic'))
            ca, cb = da['command'], db['command']
            i = ca.index('--agent')
            self.assertEqual((Path(ca[i + 1]).name, Path(cb[i + 1]).name),
                             (AGX.ENTRY_NAME, 'framelease_v4_arms_agent_entry.py'))
            self.assertEqual(ca[:i + 1] + ca[i + 2:], cb[:i + 1] + cb[i + 2:])
            ra, rb = da['agent_runtime_config'], db['agent_runtime_config']
            self.assertEqual(sorted(k for k in set(ra) | set(rb) if ra.get(k) != rb.get(k)),
                             ['arm', 'description', 'extension', 'fast_prefix', 'title'])
            fa, fb = ra['fast_prefix'], rb['fast_prefix']
            self.assertEqual(sorted(k for k in fa if fa[k] != fb[k]), ['arm', 'base_arm'])
            self.assertEqual((fa['arm'], fa['base_arm']), ('fl_global_shield_fp', GS_ARM))
            for k in ('agent', 'v3', 'utility', 'actor_log', 'kind', 'schema'):
                self.assertEqual(ra[k], rb[k], k)
            self.assertEqual(ext['global_lease'], ra['extension']['global_lease'])
            self.assertEqual((ext['arm'], ext['base_arm'], ext['entry'], ext['launcher']),
                             (GS_ARM, 'fl_heuristic', AGX.ENTRY_NAME, H.EXT_LAUNCHER_REL))
            self.assertEqual(ext['sources_sha256'], {rel: file_hash(H.ROOT / rel) for rel in X.EXT_CODE})
            self.assertEqual(ra['utility']['name'], 'v4_adet_d4')
            self.assertFalse(out.exists())

    def test_invalid_configurations_are_refused(self):
        RX = self.RX
        e5 = str(H.ENVELOPES['E5'])
        base = ['--arm', GS_ARM, '--route-id', '2086', '--output-dir', '/tmp/unused_arms_ext']
        with tempfile.TemporaryDirectory() as tmp:
            table = Path(tmp) / 'iso_table.json'
            table.write_text(json.dumps({'kind': 'iso_table', 'tau_s': [0.0, 3.0],
                                         'B_m': {'vehicle': [0.1, 0.4], 'pedestrian': [0.1, 0.3]}}))
            bad = [base,
                   base + ['--envelope', str(table)],
                   base + ['--envelope', str(Path(tmp) / 'missing.json')],
                   base + ['--envelope', e5, '--policy-params', '{"utility": "v4_eps0.300_seed1"}'],
                   base + ['--envelope', e5, '--policy-params', '{"max_depth": 4}'],
                   base + ['--envelope', e5, '--runtime-params', '{"max_depth": 4}'],
                   base + ['--envelope', e5, '--utility-env', f'FRAMELEASE_V4_QNET={H.QNET_FILE}'],
                   base + ['--envelope', e5, '--lease-overrides', '{"t_c_s": 1.0}'],
                   base + ['--envelope', e5, '--lease-overrides', '{"t_c_s": 0.5}'],
                   base[:2] + ['--route-id', '999999'] + base[4:] + ['--envelope', e5]]
            for argv in bad:                    # (a missing E* raises the pinned v3_configs' FileNotFoundError)
                with self.assertRaises((SystemExit, ValueError, OSError), msg=argv), \
                        contextlib.redirect_stderr(io.StringIO()), H.Env(FRAMELEASE_V4_QNET=None):
                    RX.prepare(RX.parse_args(argv))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                rc = RX.main(base + ['--envelope', e5, '--dry-run'])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(buf.getvalue())['agent_runtime_config']['agent']['policy_params'], {})
            self.assertFalse(Path('/tmp/unused_arms_ext').exists())


def diff_keys(a, b):
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


@unittest.skipUnless(H.stack_ready(), 'CHECKPOINT / CARLA_ROOT not set (source linux/env.sh)')
class RunPathTest(unittest.TestCase):
    """The copied run() of the extension launcher against the pinned run(), both with a stub execute (no evaluator,
    no GPU lock, no port check: nothing starts)."""

    def run_launcher(self, main, argv):
        from framelease_v3.fastprefix import run_closed_loop_fast as F
        real, calls = F.execute, []

        def stub(srun, run_dir, cmd, env, ports, timeout_s, lock_wait_s):
            calls.append({'run_dir': Path(run_dir), 'cmd': list(cmd), 'env': dict(env), 'ports': list(ports)})
            return None, {}, 'test stub: nothing was started', False, [], time.monotonic()
        F.execute = stub                                 # test process only; restored below
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                rc = main(argv)
        finally:
            F.execute = real
        return rc, calls

    def test_copied_run_writes_the_pinned_layout_plus_the_extension(self):
        from framelease_v4.arms import run_closed_loop_v4 as RV4
        from framelease_v4.arms_ext import agent_ext as AGX
        from framelease_v4.arms_ext import arms_ext as X
        from framelease_v4.arms_ext import run_closed_loop_ext as RX
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / 'dummy_checkpoint.pt'
            ckpt.write_bytes(b'not a checkpoint: the stub starts nothing')
            runs = {}
            for tag, main, arm in (('pinned', RV4.main, 'fl_heuristic'), ('ext', RX.main, GS_ARM)):
                out = Path(tmp) / tag
                argv = swap_arm(H.launcher_argv(GS_ARM, out), arm) + ['--checkpoint', str(ckpt)]
                rc, calls = self.run_launcher(main, argv)
                self.assertEqual((rc, len(calls)), (1, 1), tag)              # FAILED: no route record, as expected
                run_dirs = list((out / 'runs').iterdir())
                self.assertEqual(len(run_dirs), 1, tag)
                rd = run_dirs[0]
                self.assertEqual(calls[0]['run_dir'], rd.resolve())
                files = {str(p.relative_to(rd)) for p in rd.rglob('*') if p.is_file()}
                runs[tag] = (rd, {f for f in files if not f.startswith('source/')}, calls[0])
            (rp, fp_, cp), (rx, fx, cx) = runs['pinned'], runs['ext']
            self.assertEqual(fp_ - fx, {'raw/framelease_v4_arms_agent_entry.py'})
            self.assertEqual(fx - fp_, {f'raw/{AGX.ENTRY_NAME}'} | {f'raw/source_v4/{rel}' for rel in X.EXT_CODE})
            self.assertEqual((rx / 'raw' / AGX.ENTRY_NAME).read_text(encoding='utf-8'), AGX.ENTRY_SOURCE)
            for rel in X.EXT_CODE:
                self.assertEqual(file_hash(rx / 'raw/source_v4' / rel), file_hash(H.ROOT / rel), rel)
            for name in ('raw/source_v3/hashes.json', 'raw/source_fastprefix/hashes.json'):
                self.assertEqual(load(rx / name), load(rp / name), name)
            hx, hp = load(rx / 'raw/source_v4/hashes.json'), load(rp / 'raw/source_v4/hashes.json')
            self.assertEqual(hx, {**hp, **{rel: file_hash(H.ROOT / rel) for rel in X.EXT_CODE}})
            self.assertEqual(len(hx), len(hp) + 5)
            ax, ap = load(rx / 'raw/agent_runtime_config.json'), load(rp / 'raw/agent_runtime_config.json')
            self.assertEqual(diff_keys(ax, ap), ['arm', 'description', 'extension', 'fast_prefix', 'title'])
            self.assertEqual(X.base_config(ax), {**ap, 'fast_prefix': ax['fast_prefix']})
            fx_, fp2 = load(rx / 'raw/fast_prefix_config.json'), load(rp / 'raw/fast_prefix_config.json')
            self.assertEqual(diff_keys(fx_, fp2), ['arm', 'base_arm'])
            # evaluator command and environment: the entry and the run directory differ, nothing else
            norm = lambda x, rd: json.loads(json.dumps(x).replace(str(rd.resolve()), '<RUN>'))  # noqa: E731
            cmd_x, cmd_p = norm(cx['cmd'], rx), norm(cp['cmd'], rp)
            i = cmd_x.index('--agent')
            self.assertEqual((cmd_x[i + 1], cmd_p[i + 1]),
                             (f'<RUN>/raw/{AGX.ENTRY_NAME}', '<RUN>/raw/framelease_v4_arms_agent_entry.py'))
            self.assertEqual(cmd_x[:i + 1] + cmd_x[i + 2:], cmd_p[:i + 1] + cmd_p[i + 2:])
            self.assertEqual(norm(cx['env'], rx), norm(cp['env'], rp))
            self.assertEqual(cx['ports'], cp['ports'])
            kx, kp = load(rx / 'raw/command.json'), load(rp / 'raw/command.json')
            self.assertEqual(norm(kx['environment_overrides'], rx), norm(kp['environment_overrides'], rp))
            self.assertEqual(kx['patched_evaluator_sha256'], kp['patched_evaluator_sha256'])
            # the StageRun ledger
            cfx, cfp = load(rx / 'config.json'), load(rp / 'config.json')
            self.assertEqual(diff_keys(cfx, cfp), ['arm', 'entry', 'extension', 'fast_prefix', 'title', 'v4', 'v4_arm'])
            self.assertEqual((cfx['entry'], cfx['extension']['global_lease']),
                             (AGX.ENTRY_NAME, ax['extension']['global_lease']))
            self.assertEqual(cfx['agent_config'], cfp['agent_config'])
            mx, mp = load(rx / 'manifest.json'), load(rp / 'manifest.json')
            self.assertEqual((mx['stage'], mp['stage']), (RX.STAGE, RV4.STAGE))
            self.assertEqual((mx['status'], mp['status']), ('FAILED', 'FAILED'))
            code_x = {str(Path(k).resolve().relative_to(H.ROOT)) for k in mx['identity']['code']
                      if Path(k).resolve().is_relative_to(H.ROOT)}
            code_p = {str(Path(k).resolve().relative_to(H.ROOT)) for k in mp['identity']['code']
                      if Path(k).resolve().is_relative_to(H.ROOT)}
            self.assertEqual(code_x - code_p, set(X.EXT_CODE))
            self.assertEqual(code_p - code_x, set())
            self.assertIn(H.PINNED_LAUNCHER_REL, code_x)
            rx_res = load(rx / 'metrics/result.json')
            self.assertIn('test stub', rx_res['error'])


@unittest.skipUnless(H.stack_ready(), 'CHECKPOINT / CARLA_ROOT not set (source linux/env.sh)')
class JobLineTest(unittest.TestCase):
    def test_job_line_pins_command_and_dry_run(self):
        from framelease_v4.arms_ext import agent_ext as AGX
        from framelease_v4.arms_ext import arms_ext as X
        from framelease_v4.arms_ext import run_closed_loop_ext as RX
        p1 = H.p1_shield_line()
        if p1 is None:
            self.skipTest('registered P1 job files not available')
        env_rel = p1['envelope']['path']
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = str(Path(tmp) / 'ablation' / GS_ARM)
            job = RX.job_line('2086', 3300, out_dir, env_rel, p1['envelope']['label'], utility='v4_adet_d4',
                              envelope_config=p1['envelope']['config'], phase='test', block='dry_run')
            pins, p1_pins = job['require_sha256'], dict(p1['require_sha256'])
            self.assertEqual(len(p1_pins), 50)                                # PROTOCOL Sec. 8.3: 49 files + E*
            self.assertIn(env_rel, p1_pins)
            self.assertEqual(set(pins), set(p1_pins) | set(X.EXT_CODE))
            self.assertEqual(len(pins), 55)
            for rel, sha in p1_pins.items():
                self.assertEqual(pins[rel], sha, rel)                          # the code P1 runs, unchanged
            for rel in X.EXT_CODE:
                self.assertEqual(pins[rel], file_hash(H.ROOT / rel), rel)
            self.assertEqual(job['envelope'], {**p1['envelope']})
            cmd, p1_cmd = job['cmd'], p1['cmd']
            self.assertEqual(cmd[:3], [p1_cmd[0], '-B', H.EXT_LAUNCHER_REL])
            self.assertEqual(p1_cmd[:3], [p1_cmd[0], '-B', H.PINNED_LAUNCHER_REL])
            opts = [a for a in cmd[3:] if a.startswith('--')]
            self.assertEqual(opts, [a for a in p1_cmd[3:] if a.startswith('--')])
            same = {'--fast-prefix', '--kappa', '--seed', '--routes', '--timeout-s', '--lock-wait-s', '--envelope'}
            for o in same:
                self.assertEqual(cmd[cmd.index(o) + 1], p1_cmd[p1_cmd.index(o) + 1], o)
            self.assertEqual(cmd[cmd.index('--arm') + 1], GS_ARM)
            self.assertEqual(json.loads(cmd[cmd.index('--policy-params') + 1]), {'utility': 'v4_adet_d4'})
            self.assertEqual((job['arm_name'], job['protocol_arm'], job['wall_cap_s'], job['kind']),
                             (GS_ARM, GS_ARM, p1['wall_cap_s'], 'closed_loop'))
            res = RX.check_job_line(job, dry_run=True, isolated=True)
            self.assertTrue(res['ok'], res['problems'])
            self.assertEqual(res['dry_run']['entry'], AGX.ENTRY_NAME)
            self.assertEqual(res['dry_run']['agent_runtime_config_sha256'], res['agent_runtime_config_sha256'])
            self.assertFalse(Path(out_dir).exists())
            bad = json.loads(json.dumps(job))
            bad['require_sha256'][X.EXT_CODE[1]] = '0' * 64
            res = RX.check_job_line(bad, dry_run=False)
            self.assertFalse(res['ok'])
            self.assertTrue(any('differ from the tree' in p for p in res['problems']), res['problems'])
            bad = json.loads(json.dumps(job))
            del bad['require_sha256'][X.EXT_CODE[0]]
            self.assertFalse(RX.check_job_line(bad, dry_run=False)['ok'])

    def test_check_job_line_requires_the_fixed_lease_constants(self):
        from framelease_v4.arms_ext import run_closed_loop_ext as RX
        p1 = H.p1_shield_line()
        if p1 is None:
            self.skipTest('registered P1 job files not available')
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = str(Path(tmp) / 'ablation' / GS_ARM)
            job = RX.job_line('2086', 3300, out_dir, p1['envelope']['path'], p1['envelope']['label'],
                              utility='v4_adet_d4', envelope_config=p1['envelope']['config'])
            self.assertTrue(RX.check_job_line(job, dry_run=False)['ok'])
            # a line that carries lease overrides: the launcher refuses them
            bad = json.loads(json.dumps(job))
            bad['cmd'] += ['--lease-overrides', '{"t_c_s": 1.0}']
            res = RX.check_job_line(bad, dry_run=False)
            self.assertFalse(res['ok'])
            self.assertTrue(any('lease-overrides are refused' in p for p in res['problems']), res['problems'])
            # check_job_line's own check, independent of the launcher's refusal
            real = RX.prepare

            def lenient(args, lease=None, h_bar=None):
                prep = real(args)
                if lease is not None:
                    prep['cfg']['v3']['lease'] = lease
                if h_bar is not None:
                    prep['cfg']['extension']['global_lease']['h_bar_s'] = h_bar
                return prep
            for lease, h_bar, want in (({'t_c_s': 1.0}, 2.0, ('lease overrides', 'h_bar_s')),
                                       ({'t_c_s': 1.0}, None, ('lease overrides',)),
                                       (None, 2.0, ('h_bar_s',))):
                with mock.patch.object(RX, 'prepare', lambda a, lo=lease, hb=h_bar: lenient(a, lo, hb)):
                    res = RX.check_job_line(job, dry_run=False)
                self.assertFalse(res['ok'], (lease, h_bar))
                for w in want:
                    self.assertTrue(any(w in p for p in res['problems']), (w, res['problems']))
                self.assertEqual(len(res['problems']), len(want), res['problems'])
            self.assertTrue(RX.check_job_line(job, dry_run=False)['ok'])
            self.assertFalse(Path(out_dir).exists())


if __name__ == '__main__':
    unittest.main()
