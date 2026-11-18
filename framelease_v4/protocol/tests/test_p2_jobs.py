"""Phase-2 job file (framelease_v4/protocol/p2_jobs.py; PROTOCOL Secs. 2.6, 3.2-3.3, 4.9, 5.3, 8.2-8.4, 8.6). CPU only;
nothing is launched or enqueued. The tuning freeze, PROTOCOL.md and its seal are synthetic files in a temporary
directory, and every file is written to a temporary directory; the real envelopes, route split, collection plan and code
pins are only read.

  cd /home/kang/Desktop/DAC && OMP_NUM_THREADS=1 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      -m pytest -q -p no:cacheprovider framelease_v4/protocol/tests/test_p2_jobs.py
  # + the in-process launcher checks of every line and the --dry-run of the whole block (official stack variables):
  source linux/env.sh && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 nice -n 19 ionice -c 3 \
      .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/protocol/tests/test_p2_jobs.py

What is shown:
  * the freeze gate: a selection.json whose sha256 PROTOCOL Sec. 13.2 does not cite (not at all, only outside Sec.
    13.2, or a file changed after its entry) is refused, so is an unsealed PROTOCOL.md, a TRIMMED freeze, an L* that is
    not the exported envelope, a d* outside the registered grid; the CLI refuses with exit code 2 and writes nothing;
  * the block: 132 lines = the 44 training routes x kappa {1.0, 1.5, 2.0}, the collection plan's launcher arguments
    with the port recomputed, ids v4p2_fl_behaviour_<L*>_eps0.300_d<d*>_k<kappa>_s11_r<route>, output directories
    rl_data/k<kappa>, tier 2, wall cap 1500 s, the behaviour seed rule (with and without the _d<d*> suffix);
  * the order: Random(20261110 + 10) route shuffle, the 3 kappas of a route back to back rotated by one per route,
    every prefix balanced over kappa, ports 2600 + 10 (i mod 4); an unbalanced order is a static problem;
  * the pins equal jobs_v4.code_pins([L*]);
  * test routes are refused (in the plan: PermissionError; in a line: a static problem);
  * determinism: the same inputs give byte-identical job files and stage specs;
  * the write guards: existing runs (also with --force), a queue path, an existing file with other content;
  * with the official stack: every line passes the kappa-aware in-process launcher check (p1_jobs.check_in_process
    flags kappa 1.5 / 2.0), and the CLI --check --write runs the --dry-run of all 132 lines with 2 workers.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ['CUDA_VISIBLE_DEVICES'] = ''
sys.dont_write_bytecode = True

from framelease_v4.arms import jobs_v4 as J  # noqa: E402
from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402
from framelease_v4.protocol import p2_jobs as P2  # noqa: E402
from framelease_v4.protocol import select_stage as SS  # noqa: E402
from framelease_v4.rl import behaviour as B  # noqa: E402
from framelease_v4.rl import collection_plan as CP  # noqa: E402

STACK = bool(os.environ.get('CHECKPOINT')) and Path(os.environ.get('CHECKPOINT', '/nonexistent')).is_file()


def freeze_doc(label='E5', d=10, variant='FULL'):
    """A synthetic tuning freeze in the select_stage.freeze() format (only the fields P2 reads are meaningful)."""
    e = PJ.envelopes()[label]
    u = PJ.heur_utility(d)
    return {'schema': SS.FREEZE_SCHEMA, 'variant': variant, 'written': '2026-11-12T09:00:00+0800',
            'L_star': {'label': label, 'envelope_path': e['path'], 'envelope_sha256': e['sha256'],
                       'config': e['config'], 'validity': 'std'},
            'd_star': {'d': d, 'utility': u}, 'A_star': {'age_lease_s': 2.0},
            'event_star': {'candidate': 'v2_hb2.0', 'policy_params': {**PJ.THETA['v2'], 'heartbeat_s': 2.0}},
            'arms': {'fl_heuristic': {'envelope': e['path'], 'policy_params': {'utility': u}},
                     'fl_full': {'envelope': e['path'], 'a_det_depth': d},
                     'fl_behaviour': {'envelope': e['path'], 'base_depth': d},
                     'age_only': {'policy_params': {'age_lease_s': 2.0, 'utility': u}},
                     'event_triggered': {'policy_params': {**PJ.THETA['v2'], 'heartbeat_s': 2.0}}},
            'fl_risk': None, 'stages': {}, 'tables': {}, 'flags': {}, 'script_sha256': {}}


def protocol_text(in_13_2='', in_13_1='', in_14=''):
    """A PROTOCOL.md skeleton around Sec. 13.2, with the P1 driver's subsection and anchor paragraph."""
    return '\n'.join([
        '# FrameLease v4 method-paper experiments: pre-registration protocol (synthetic)', '',
        '## 13. Registration and amendments', '', '### 13.1 Registration checklist', '',
        f'Registration entry. {in_13_1}', '', '### 13.2 Amendments', '',
        '**Smoke report 2, 2026-11-11 12:28 (Beijing time): PASS.** P1 may start (Sec. 8.1).', '',
        '**Stage selections (P1, FULL).**', in_13_2, '',
        'Each amendment gets the date and time, the reason, and what changes for which runs.', '',
        '## 14. TRIMMED plan (reduced budget; not registered: the user chose FULL)', '', f'{in_14}', ''])


def freeze_entry(sha):
    """The P1 driver's freeze entry (p1_driver.freeze_entry, wrapped at 120 columns)."""
    return (f'* **Tuning freeze**, 2026-11-12 09:05 (Beijing time). `outputs/framelease_v4/tuning/selection.json`\n'
            f'  (sha256 `{sha}`), written 2026-11-12T09:00:00+0800 by `select_stage.py --variant FULL --freeze\n'
            '  --write` from the eight stage selections above (Sec. 4.9).')


class Env:
    """A synthetic freeze, PROTOCOL.md and SEAL.sha256 in a temporary directory."""

    def __init__(self, tmp, label='E5', d=10, cite=True, sealed=True, doc=None):
        self.tmp = Path(tmp)
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.sel = self.tmp / 'selection.json'
        self.protocol = self.tmp / 'PROTOCOL.md'
        self.seal = self.tmp / 'SEAL.sha256'
        self.jobs = self.tmp / 'jobs'
        self.root = self.tmp / 'root'
        self.sel.write_text(json.dumps(doc or freeze_doc(label, d), indent=1, sort_keys=True) + '\n')
        self.sha = PJ.sha256_file(self.sel)
        self.write_protocol(protocol_text(freeze_entry(self.sha) if cite else ''), sealed)

    def write_protocol(self, text, sealed=True):
        self.protocol.write_text(text)
        psha = PJ.sha256_file(self.protocol) if sealed else '0' * 64
        self.seal.write_text(f'{psha}  {self.protocol}\n{"1" * 64}  {self.tmp / "MANIFEST.sha256"}\n')

    def freeze(self, seal=True):
        return P2.load_freeze(self.sel, self.protocol, self.seal if seal else None)

    def main(self, *extra):
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            rc = P2.main(['--selection', str(self.sel), '--protocol', str(self.protocol), '--seal', str(self.seal),
                          '--jobs-dir', str(self.jobs)] + list(extra))
        return rc, out.getvalue(), err.getvalue()


def opts(cmd):
    return {cmd[k]: cmd[k + 1] for k in range(len(cmd) - 1) if cmd[k].startswith('--')}


def without_port(cmd):
    i = cmd.index('--port')
    return cmd[:i] + cmd[i + 2:]


class FreezeGateTest(unittest.TestCase):
    def test_the_freeze_must_be_cited_in_sec_13_2_and_sealed(self):
        with tempfile.TemporaryDirectory() as tmp:
            E = Env(tmp)
            fr = E.freeze()
            self.assertEqual(fr['sha256'], E.sha)
            lines = E.protocol.read_text().split('\n')
            self.assertEqual(len(fr['cited_lines']), 1)
            self.assertIn(E.sha, lines[fr['cited_lines'][0] - 1])
            self.assertTrue(fr['protocol']['seal']['sealed'])
            # not cited at all
            E.write_protocol(protocol_text(''))
            with self.assertRaises(PermissionError):
                E.freeze()
            # cited only outside Sec. 13.2 (registration checklist, Sec. 14)
            E.write_protocol(protocol_text('', in_13_1=f'sha256 `{E.sha}`', in_14=f'sha256 `{E.sha}`'))
            with self.assertRaises(PermissionError):
                E.freeze()
            # recorded, but selection.json changed afterwards: its sha256 is no longer the cited one
            E.write_protocol(protocol_text(freeze_entry(E.sha)))
            E.freeze()
            E.sel.write_text(E.sel.read_text() + ' ')
            with self.assertRaises(PermissionError):
                E.freeze()

    def test_an_unsealed_protocol_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            E = Env(tmp, sealed=False)
            with self.assertRaises(PermissionError):
                E.freeze()
            self.assertIsNone(E.freeze(seal=False)['protocol']['seal'])     # tests only: no seal check
            E.write_protocol(E.protocol.read_text(), sealed=True)
            self.assertTrue(E.freeze()['protocol']['seal']['sealed'])

    def test_freeze_contents(self):
        cases = []
        doc = freeze_doc('E10', 4)
        cases.append(('variant', {**doc, 'variant': 'TRIMMED'}))
        bad = json.loads(json.dumps(doc))
        bad['L_star']['envelope_sha256'] = '0' * 64
        cases.append(('envelope sha256', bad))
        bad = json.loads(json.dumps(doc))
        bad['L_star']['label'] = 'E7'
        cases.append(('label', bad))
        bad = json.loads(json.dumps(doc))
        bad['L_star']['validity'] = 'ra'
        cases.append(('validity', bad))
        bad = json.loads(json.dumps(doc))
        bad['d_star'] = {'d': 7, 'utility': 'v4_adet_d7'}
        cases.append(('d*', bad))
        bad = json.loads(json.dumps(doc))
        bad['d_star']['utility'] = 'heuristic'
        cases.append(('d* utility', bad))
        bad = json.loads(json.dumps(doc))
        bad['arms']['fl_behaviour']['base_depth'] = 10
        cases.append(('behaviour base depth', bad))
        cases.append(('schema', {**doc, 'schema': 'framelease_v4.p1_selection/1'}))
        for what, d in cases:
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError, msg=what):
                    Env(tmp, doc=d).freeze()

    def test_cli_refuses_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            E = Env(tmp, cite=False)
            rc, out, err = E.main()
            self.assertEqual(rc, 2)
            self.assertIn('not cited in PROTOCOL.md Sec. 13.2', err)
            self.assertNotIn('Traceback', err)
            E.sel.unlink()
            rc, out, err = E.main()
            self.assertEqual(rc, 2)
            self.assertIn('no tuning freeze yet', err)
            self.assertFalse(E.jobs.exists())
            for bad in (['--write'], ['--check', '--write', '--no-dry-run'], ['--workers', '3'], ['--workers', '0']):
                with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(io.StringIO()):
                    E.main(*bad)
                self.assertEqual(cm.exception.code, 2, bad)
            # cited: the block is printed (nothing checked, nothing written)
            E2 = Env(Path(tmp) / 'ok')
            rc, out, err = E2.main()
            self.assertEqual(rc, 0, err)
            self.assertIn('132 job lines', out)
            self.assertFalse(E2.jobs.exists())


class BlockTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.E = Env(Path(cls._tmp.name) / 'a', 'E10', 4)
        cls.fr = cls.E.freeze()
        cls.lines, cls.spec = P2.build_block(cls.fr)
        cls.E10 = Env(Path(cls._tmp.name) / 'b', 'B0', 10)
        cls.fr10 = cls.E10.freeze()
        cls.lines10, cls.spec10 = P2.build_block(cls.fr10)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_routes_kappas_and_lines(self):
        train = PJ.training_routes()
        test = {r['route_id'] for r in PJ.route_split()['test']}
        for fr, lines in ((self.fr, self.lines), (self.fr10, self.lines10)):
            self.assertEqual(len(lines), 132)
            cells = [(j['route_id'], j['kappa']) for j in lines]
            self.assertEqual(len(set(cells)), 132)
            self.assertEqual(sorted({r for r, _ in cells}, key=int), PJ.route_set('RL'))
            self.assertEqual(sorted(train, key=int), PJ.route_set('RL'))
            self.assertFalse({r for r, _ in cells} & test)
            self.assertEqual({k: sum(1 for j in lines if j['kappa'] == k) for k in (1.0, 1.5, 2.0)},
                             {1.0: 44, 1.5: 44, 2.0: 44})
            self.assertEqual(P2.static_problems(lines, fr), [])
            L = fr['L']
            for j in lines:
                o = opts(j['cmd'])
                k, r = j['kappa'], j['route_id']
                self.assertEqual(j['id'], f'v4p2_fl_behaviour_{L["label"]}_eps0.300_d{fr["d"]}_k{k:.1f}_s11_r{r}')
                self.assertEqual(j['cmd'][:3], [PJ.PYTHON, '-B', 'framelease_v4/arms/run_closed_loop_v4.py'])
                self.assertEqual((o['--arm'], o['--fast-prefix'], o['--kappa'], o['--seed'], o['--timeout-s'],
                                  o['--lock-wait-s'], o['--envelope'], o['--route-id']),
                                 ('fl_behaviour', 'sdpa,gpu_preproc,lora_merged', f'{k:.1f}', '11', '1410', '600',
                                  L['path'], r))
                self.assertEqual((j['tier'], j['wall_cap_s'], j['phase'], j['block'], j['block_no']),
                                 (2, 1500, 'P2', 'rl_data', 10))
                self.assertEqual(j['output_dir'], f'outputs/framelease_v4/rl_data/k{k:.1f}')
                self.assertEqual(o['--output-dir'], j['output_dir'])
                self.assertEqual(j['envelope'], L)
                self.assertEqual(j['tuning_freeze'], {'path': fr['path'], 'sha256': fr['sha256']})
                seed = CP.behaviour_seed(r, k, 0)
                name = json.loads(o['--policy-params'])['utility']
                self.assertEqual(j['policy_params'], {'utility': name})
                self.assertEqual(B.parse_behaviour(name), (0.3, seed, fr['d']))
                self.assertEqual(name, f'v4_eps0.300_seed{seed}' + ('' if fr['d'] == 10 else f'_d{fr["d"]}'))
                self.assertEqual(j['behaviour']['seed'], seed)

    def test_lines_are_the_collection_plan_with_ports_recomputed(self):
        plan = CP.plan(eps=0.3, kappas=(1.0, 1.5, 2.0), d_det=4, envelope=self.fr['L']['path'], variant='FULL')
        by = {(r['route_id'], r['kappa']): r for r in plan['runs']}
        for j in self.lines:
            run = by[(j['route_id'], j['kappa'])]
            self.assertEqual(without_port(j['cmd'][2:]), without_port(run['argv']))
        self.assertEqual(self.spec['collection_plan']['n_runs'], 132)
        self.assertEqual([x['id'] for x in self.spec['jobs']], [j['id'] for j in self.lines])

    def test_order_kappa_balance_and_ports(self):
        for lines, spec in ((self.lines, self.spec), (self.lines10, self.spec10)):
            routes = sorted(spec['routes'], key=int)
            random.Random(20261110 + 10).shuffle(routes)
            self.assertEqual(spec['route_order'], routes)
            for pos, r in enumerate(routes):
                chunk = lines[3 * pos:3 * pos + 3]
                self.assertEqual({j['route_id'] for j in chunk}, {r})                     # back to back
                ks = [1.0, 1.5, 2.0]
                self.assertEqual([j['kappa'] for j in chunk], ks[pos % 3:] + ks[:pos % 3])   # rotated by one
            counts = {1.0: 0, 1.5: 0, 2.0: 0}
            for n, j in enumerate(lines, 1):                                              # every prefix
                counts[j['kappa']] += 1
                self.assertLessEqual(max(counts.values()) - min(counts.values()), 1, n)
                self.assertEqual(sum(counts.values()), n)
            self.assertEqual(P2.kappa_spread(lines), 1)
            for i, j in enumerate(lines):
                self.assertEqual(j['port'], 2600 + 10 * (i % 4))
                self.assertEqual(opts(j['cmd'])['--port'], str(j['port']))
        # an unbalanced order (all kappa 1.0 first) breaks the prefix balance and the ports
        bad = sorted(self.lines, key=lambda j: (j['kappa'], int(j['route_id'])))
        probs = P2.static_problems(bad, self.fr)
        self.assertTrue(any('unbalanced over kappa' in p for p in probs), probs[-3:])
        self.assertTrue(any('port' in p for p in probs))

    def test_pins_equal_jobs_v4_code_pins(self):
        for fr, lines in ((self.fr, self.lines), (self.fr10, self.lines10)):
            want = J.code_pins([fr['L']['path']])
            self.assertEqual(len(want), 50)
            self.assertEqual(want[fr['L']['path']], fr['L']['sha256'])
            self.assertEqual({k: v for k, v in want.items() if k != fr['L']['path']}, J.code_pins())
            self.assertEqual(len(J.code_pins()), 49)
            for j in lines:
                self.assertEqual(j['require_sha256'], want)
        changed = json.loads(json.dumps(self.lines))
        changed[5]['require_sha256'].pop('framelease_v4/rl/qnet.py')
        self.assertTrue(any('code_pins' in p for p in P2.static_problems(changed, self.fr)))

    def test_test_routes_are_refused(self):
        test = PJ.route_split()['test'][0]['route_id']
        plan = P2.behaviour_plan(self.fr)
        bad = json.loads(json.dumps(plan))
        bad['runs'][7]['route_id'] = test
        with self.assertRaises(PermissionError):
            P2.build_block(self.fr, bad)
        lines = json.loads(json.dumps(self.lines))
        lines[4]['route_id'] = test
        lines[4]['cmd'][lines[4]['cmd'].index('--route-id') + 1] = test
        probs = P2.static_problems(lines, self.fr)
        self.assertTrue(any(f'route {test} is not a training route' in p for p in probs), probs)
        # the seed rule and L* are checked per line as well
        lines = json.loads(json.dumps(self.lines))
        other = B.behaviour_name(0.3, 12345, 4)
        lines[2]['policy_params'] = {'utility': other}
        lines[2]['cmd'][lines[2]['cmd'].index('--policy-params') + 1] = json.dumps({'utility': other})
        lines[9]['cmd'][lines[9]['cmd'].index('--envelope') + 1] = 'outputs/framelease_v4/envelopes/E5.json'
        probs = P2.static_problems(lines, self.fr)
        self.assertTrue(any(lines[2]['id'] in p and 'seed rule' in p for p in probs), probs)
        self.assertTrue(any(lines[9]['id'] in p and 'L*' in p for p in probs), probs)

    def test_determinism(self):
        lines2, spec2 = P2.build_block(self.E.freeze())
        self.assertEqual(P2.jsonl(lines2), P2.jsonl(self.lines))
        self.assertEqual(json.dumps(spec2, sort_keys=True), json.dumps(self.spec, sort_keys=True))
        with tempfile.TemporaryDirectory() as tmp:
            a = P2.block_paths(Path(tmp) / 'a')
            b = P2.block_paths(Path(tmp) / 'b')
            ia = P2.write_block(a, self.lines, self.spec, [], [], root=Path(tmp) / 'root')
            ib = P2.write_block(b, lines2, spec2, [], [], root=Path(tmp) / 'root')
            self.assertEqual(a[0].read_bytes(), b[0].read_bytes())
            self.assertEqual(ia['sha256'], ib['sha256'])
            sa, sb = json.loads(a[1].read_text()), json.loads(b[1].read_text())
            self.assertEqual(sa['job_file_sha256'], PJ.sha256_file(a[0]))
            sa.pop('job_file'), sb.pop('job_file')
            self.assertEqual(sa, sb)
            self.assertEqual([json.loads(x) for x in a[0].read_text().splitlines()], self.lines)

    def test_write_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root = tmp / 'root'
            paths = P2.block_paths(tmp / 'p2_jobs')
            self.assertEqual([p.name for p in paths], ['b10_rl_data.jsonl', 'b10_rl_data.stage.json',
                                                       'b10_rl_data.check.json'])
            self.assertEqual(paths[0].parent.name, 'FULL')
            P2.write_block(paths, self.lines, self.spec, [], [], root=root)
            P2.write_block(paths, self.lines, self.spec, [], [], root=root)          # identical: idempotent
            with self.assertRaises(FileExistsError):                                # other lines: refused
                P2.write_block(paths, self.lines10, self.spec10, [], [], root=root)
            P2.write_block(paths, self.lines10, self.spec10, [], [], force=True, root=root)
            self.assertEqual(json.loads(paths[0].read_text().splitlines()[0])['envelope']['label'], 'B0')
            # existing runs: refused, also with force
            run = root / 'outputs/framelease_v4/rl_data/k1.5/runs/20261113T010203_abcdef01'
            run.mkdir(parents=True)
            self.assertEqual(P2.runs_present(self.lines, root),
                             [str(root / 'outputs/framelease_v4/rl_data/k1.5/runs')])
            before = paths[0].read_bytes()
            for force in (False, True):
                with self.assertRaises(PermissionError):
                    P2.write_block(paths, self.lines, self.spec, [], [], force=force, root=root)
            self.assertEqual(paths[0].read_bytes(), before)
            # inside a queue: refused
            for qdir in (tmp / 'queue_p2' / 'jobs.d', tmp / 'queue_p2', tmp / 'q'):
                if qdir.name == 'q':
                    qdir.mkdir(parents=True)
                    (qdir / 'status.jsonl').write_text('')
                with self.assertRaises(PermissionError, msg=str(qdir)):
                    P2.write_block(P2.block_paths(qdir), self.lines, self.spec, [], [], root=tmp / 'empty')
            self.assertFalse((tmp / 'queue_p2').exists())
            self.assertFalse(any((tmp / 'q').rglob('b10_*')))


@unittest.skipUnless(STACK, 'official stack variables not set (source linux/env.sh)')
class LauncherTest(unittest.TestCase):
    """The launcher's own parsing, configuration build and preflight for every line (kappa-aware), and the CLI
    --check --write with the --dry-run of every line (2 workers), into a temporary directory."""

    def test_every_line_in_process_and_sample_dry_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            E = Env(tmp, 'E5', 1)
            fr = E.freeze()
            lines, _ = P2.build_block(fr)
            results, problems = P2.check_lines(lines, fr, dry_run=False)
            self.assertEqual(problems, [])
            self.assertEqual([r['kappa'] for r in results], [j['kappa'] for j in lines])
            self.assertEqual([r['utility'] for r in results], [j['policy_params']['utility'] for j in lines])
            first = {k: next(j for j in lines if j['kappa'] == k) for k in P2.KAPPAS}
            for k, j in first.items():
                r = P2.check_line(j, dry_run=True)
                self.assertTrue(r['ok'], r['problems'])
                self.assertEqual(r['dry_run']['ports'], [j['port'], j['port'] + 1, j['port'] + 2, j['port'] + 6000])
                p1 = PJ.check_in_process(j)                       # the P1 check asserts kappa 1.0
                self.assertEqual(p1['problems'] == [], k == 1.0, p1['problems'])
            # a command whose --kappa differs from the job's kappa is caught in process
            j = json.loads(json.dumps(first[1.5]))
            j['cmd'][j['cmd'].index('--kappa') + 1] = '2.0'
            self.assertTrue(any('kappa / seed' in p for p in P2.check_in_process(j)['problems']))

    def test_cli_check_write_with_every_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            E = Env(tmp, 'E10', 10)
            lines, _ = P2.build_block(E.freeze())
            if P2.runs_present(lines):
                self.skipTest('P2 runs exist in the project outputs: the CLI refuses to write (by design)')
            rc, out, err = E.main('--check', '--write', '--workers', '2')
            self.assertEqual(rc, 0, err[-2000:])
            job, spec, check = P2.block_paths(E.jobs)
            self.assertEqual(len(job.read_text().splitlines()), 132)
            c = json.loads(check.read_text())
            self.assertEqual((c['problems'], c['all_dry_runs_ok'], c['n_lines']), ([], True, 132))
            self.assertEqual(c['job_file_sha256'], PJ.sha256_file(job))
            s = json.loads(spec.read_text())
            self.assertEqual((s['job_file_sha256'], s['tuning_freeze']['sha256']), (PJ.sha256_file(job), E.sha))
            self.assertEqual(len(c['lines']), 132)
            self.assertTrue(all(r['ok'] and r['dry_run']['status'] == 'NOT_STARTED' for r in c['lines']))
            self.assertEqual(sorted({r['kappa'] for r in c['lines']}), [1.0, 1.5, 2.0])
            for d in ('k1.0', 'k1.5', 'k2.0'):                    # the dry runs created no run directory
                self.assertFalse((ROOT / 'outputs/framelease_v4/rl_data' / d / 'runs').exists())


if __name__ == '__main__':
    unittest.main()
