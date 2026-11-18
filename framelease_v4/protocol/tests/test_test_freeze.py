"""The test freeze (framelease_v4/protocol/test_freeze.py; PROTOCOL Secs. 3.3 rule 4, 5.9, 7.6, 8.1, 8.3, 9.11, 13.2;
GAP_AUDIT Sec. 3.5 G-2 and G-3). CPU only; nothing is launched or enqueued. Every input is synthetic and lives in a
temporary directory: the tuning freeze with two stage selections, PROTOCOL.md and its seal, the production RL freeze
made from copies of the development networks outputs/framelease_v4/rl_dev/smoke_20261110/qnet_*.json (absolute paths)
with a P2 data manifest stand-in (test_test_jobs.Env), the P4-P6 job files written by test_jobs.write_all (the
launcher layers of the check replaced by clean NOT_STARTED results: test_test_jobs.LauncherTest runs the real ones),
and registered-looking S1-S3 reports made by the stress_bench code of the tree. The real envelopes, route split,
budget, code pins and code are only read.

  cd /home/kang/Desktop/DAC && OMP_NUM_THREADS=1 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      -m pytest -q -p no:cacheprovider framelease_v4/protocol/tests/test_test_freeze.py

What is shown:
  * the record (G-2): the tuning freeze with A*, theta* / A_hb*, the fl_risk point and its cited stage selections; the
    RL freeze with the networks per protocol arm by FILE sha256, its files, deviations and notes; every P4-P6 job file,
    block spec and check with its sha256 (632 lines = Sec. 10.1; with L* = E5 610 and s_risk without a file); every
    pin (59) at the tree; the S1-S3 reports; the code of the freeze; the route split, routes.json, the envelope
    manifest and the registered code at their sealed registration sha256; and the sha256 manifest over all of them
    (G-3, 100 files);
  * the flow: --write writes the record and its manifest and prints the Sec. 13.2 entry; an equal record is kept;
    --entry prints the same entry; --verify passes only after the entry cites the record and the manifest in a sealed
    PROTOCOL.md, and fails once a file of the manifest changes or a copy in queue_p4/jobs.d/ is not a frozen job file
    at its sha256; a cited record is never rewritten;
  * the refusals (exit 2): a test-route run (a runs/ entry under the P4-P6 roots, a queue_p4 status record), an
    uncited or unsealed tuning freeze, an uncited or changed stage selection, an RL development record, no job files,
    no or two registered reports of a test, a queue path, a changed file without --force, a recorded file with --force,
    a registered input or code file off the sealed registration manifest;
  * the checks (exit 1): every mutation of a job file, block spec, check or index; a check made by other code; a pin
    that differs from the tree or from the registered P1 pins; S1-S3 reports that are not registered, made by other
    code, run on other networks or another envelope, or with violations (Sec. 7.6: "must be 0").
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ['CUDA_VISIBLE_DEVICES'] = ''
sys.dont_write_bytecode = True

from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402
from framelease_v4.protocol import p2_jobs as P2J  # noqa: E402
from framelease_v4.protocol import registration as REG  # noqa: E402
from framelease_v4.protocol import test_freeze as F  # noqa: E402
from framelease_v4.protocol import test_jobs as TJ  # noqa: E402
from framelease_v4.protocol.tests import test_p2_jobs as T2J  # noqa: E402  (the PROTOCOL.md skeleton)
from framelease_v4.protocol.tests import test_test_jobs as TTJ  # noqa: E402  (the synthetic freezes)

STAGES = ('lease_s1', 'age_s2')


def stress_docs(tuning, rl):
    """Registered-looking S1-S3 reports (the stress_bench.py report layout that test_freeze.stress_check reads): made by
    the stress_bench code of the tree, on the deployed networks of the RL freeze and, for S1, the L* envelope."""
    from framelease_v4.protocol import stress_bench as SB
    code = {f: PJ.sha256_file(ROOT / f) for f in SB.CODE_FILES}
    nets = {n['name']: n for n in rl['networks'].values()}

    def head(test):
        return {'schema': SB.SCHEMA, 'test': test, 'label': SB.label_for(test, True), 'registered': True,
                'provenance': {'code_sha256': dict(code)}}

    s3 = {**head('S3'), 'n_sequences': SB.S3_MIN_SEQUENCES, 'targets': {'gate': {}, 'runtime': {}}, 'pass': True,
          'violations_total': 0, 'coverage_ok': True}
    s2 = {**head('S2'), 'n_states': 5000, 'n_swept': 4850, 'states': {'source': 'synthetic'},
          'slack_grid_s': [ms / 1000 for ms in SB.SLACK_GRID_MS], 'replay_fidelity': None, 'pass': True,
          'violations_total': 0,
          'networks': {n: {'file_sha256': v['sha256'], 'family': v['family'], 'admitted_bound_ge_Dstar': 0,
                           'violations_total': 0, 'share_admitted': 0.9, 'bypass_rate': 0.01,
                           'bypass_rate_slack': 0.01, 'bypass_rate_timing': 0.0} for n, v in nets.items()}}
    s1 = {**head('S1'), 'plan': {'loads': list(SB.LOADS),
                                 'networks': [{'name': n, 'file_sha256': v['sha256']} for n, v in nets.items()],
                                 'states': {'source': 'synthetic'}, 'scenes': {'source': 'synthetic'}},
          'per_load': [{'load': x} for x in SB.LOADS], 'shared_cpu': False, 'foreign_cpu_accepted': False,
          'envelope': {'path': tuning['L']['path'], 'sha256': tuning['L']['sha256']}}
    return {'S1': s1, 'S2': s2, 'S3': s3}


def write_stress(d, docs, stamp='20261112T000000Z'):
    """{test: path} of the reports written as stress_bench.py --registered names them."""
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    out = {}
    for test, doc in docs.items():
        out[test] = d / f'{test.lower()}_registered_{stamp}.json'
        TTJ.dump(out[test], doc)
    return out


class FreezeEnv(TTJ.Env):
    """test_test_jobs.Env plus two stage selections named by the tuning freeze and cited in Sec. 13.2, the P4-P6 job
    files of the two freezes (test_jobs.write_all), the S1-S3 reports in stress/, the run root root/ (empty) and the
    output directory freeze/."""

    def __init__(self, tmp, label='B0', **kw):
        super().__init__(tmp, label, **kw)
        self.stress, self.out, self.queue = self.tmp / 'stress', self.tmp / 'freeze', self.tmp / 'queue_p4' / 'jobs.d'
        self.root.mkdir()
        stages = {}
        for s in STAGES:
            p = self.tmp / 'stages' / f'{s}.json'
            p.parent.mkdir(exist_ok=True)
            TTJ.dump(p, {'stage': s, 'synthetic': True})
            stages[s] = {'path': PJ.rel(p), 'sha256': PJ.sha256_file(p)}
            self.extra.append(f'* Stage selection {s} `{p.name}` (sha256 `{stages[s]["sha256"]}`).')
        self.write_selection(TTJ.freeze_doc(label, stages=stages))
        self.refresh()

    def refresh(self):
        """The job files and the stress reports made again from the current freezes (after the RL freeze changed)."""
        self.tuning_, self.rl_, self.built = self.build()
        shutil.rmtree(self.jobs, ignore_errors=True)
        shutil.rmtree(self.stress, ignore_errors=True)
        self.write_jobs(self.built)
        self.docs = stress_docs(self.tuning_, self.rl_)
        self.reports = write_stress(self.stress, self.docs)

    def write_jobs(self, built, jobs_dir=None):
        return TJ.write_all(built, TTJ.fake_checked(built), TJ.cross_block_problems(built), jobs_dir or self.jobs,
                            self.protocol, root=self.root)

    def freeze(self, **kw):
        """test_freeze.build_freeze on the synthetic inputs (keyword arguments replace them)."""
        args = dict(selection=self.sel, rl_freeze=self.rl_path, jobs_dir=self.jobs, stress=(), stress_dir=self.stress,
                    protocol=self.protocol, seal=self.seal, root=self.root)
        args.update(kw)
        return F.build_freeze(**args)

    def cli(self, *extra):
        """(rc, stdout, stderr) of test_freeze.main on the synthetic inputs, the run guard on root/, the queue copies
        of --verify in queue_p4/jobs.d/ of the temporary directory."""
        argv = ['--selection', str(self.sel), '--rl-freeze', str(self.rl_path), '--jobs-dir', str(self.jobs),
                '--stress-dir', str(self.stress), '--protocol', str(self.protocol), '--seal', str(self.seal),
                '--out-dir', str(self.out), '--queue-dir', str(self.queue), *extra]
        err, out = io.StringIO(), io.StringIO()
        with TTJ.isolated_root(self.root), contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            rc = F.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def enter(self, entry):
        """The coordinating session's step: the entry appended to Sec. 13.2, PROTOCOL.md sealed again."""
        self.extra.append(entry)
        self.write_protocol()


@contextlib.contextmanager
def changed(path, mutate):
    """path changed by mutate(path) for the block, restored byte for byte afterwards."""
    path = Path(path)
    orig = path.read_bytes() if path.exists() else None
    try:
        mutate(path)
        yield path
    finally:
        if orig is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(orig)


def edit_json(fn):
    def mutate(path):
        doc = json.loads(path.read_text())
        fn(doc)
        TTJ.dump(path, doc)
    return mutate


def edit_line(k, fn):
    def mutate(path):
        lines = path.read_text().splitlines()
        j = json.loads(lines[k])
        fn(j)
        lines[k] = json.dumps(j, sort_keys=True)
        path.write_text('\n'.join(lines) + '\n')
    return mutate


def flat(text):
    """The text with its line breaks and indentation collapsed (the entry is wrapped at 120 columns)."""
    return ' '.join(text.split())


class RecordTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.E = FreezeEnv(Path(cls._tmp.name) / 'b0')
        cls.rec, cls.files, cls.problems = cls.E.freeze()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_the_record(self):
        from framelease_v4.protocol import p3_rl as P3
        E, rec = self.E, self.rec
        self.assertEqual(self.problems, [])
        self.assertEqual((rec['schema'], rec['variant'], rec['script']), (F.SCHEMA, 'FULL', F.THIS_REL))
        tf = rec['tuning_freeze']
        self.assertEqual((tf['path'], tf['sha256'], len(tf['cited_lines'])), (PJ.rel(E.sel), PJ.sha256_file(E.sel), 1))
        self.assertEqual((tf['L_star']['label'], tf['d_star'], tf['d_utility'], tf['A_star'],
                          tf['event_star']['candidate'], tf['fl_risk']['lease_point']),
                         ('B0', 10, 'heuristic', 1.5, 's_hb1.0', 'E10'))
        self.assertEqual([(s['stage'], len(s['cited_lines'])) for s in tf['stage_selections']],
                         [(s, 1) for s in sorted(STAGES)])
        rl = rec['rl_freeze']
        self.assertEqual((rl['path'], rl['sha256'], rl['p_both_label']),
                         (PJ.rel(E.rl_path), PJ.sha256_file(E.rl_path), 'testable'))
        self.assertEqual({a: (n['family'], n['sha256']) for a, n in rl['networks'].items()},
                         {a: (f, PJ.sha256_file(E.tmp / 'nets' / f'qnet_{f}.json')) for a, f in TJ.QNET_FAMILY.items()})
        self.assertEqual(rl['p2_manifest'], {'path': PJ.rel(E.p2), 'sha256': PJ.sha256_file(E.p2), 'cited_lines': []})
        self.assertEqual((rl['n_files'], rl['deviations'], rl['sec13_notes']), (4, [], list(P3.SEC13_NOTES)))
        jf = rec['job_files']
        self.assertEqual((jf['n_lines'], jf['expected_runs_sec_10_1'], jf['queue']), (632, 632, TJ.QUEUE_REL))
        self.assertEqual([(b['block'], b['n_lines']) for b in jf['blocks']],
                         [('ti_main', 308), ('f3_k', 176), ('a_lease', 22), ('a_rl', 44), ('s_seed12', 60),
                          ('s_risk', 22)])
        for b, blk in zip(jf['blocks'], TJ.BLOCKS):
            self.assertEqual((b['job_file_sha256'], b['stage_spec_sha256'], b['check_sha256']),
                             tuple(PJ.sha256_file(p) for p in TJ.block_paths(blk, E.jobs)))
        self.assertEqual(jf['generator'], {'path': 'framelease_v4/protocol/test_jobs.py',
                                           'sha256': PJ.sha256_file(ROOT / 'framelease_v4/protocol/test_jobs.py')})
        self.assertEqual({a: s['n'] for a, s in jf['pin_sets'].items()},
                         {'fixed_deep': 49, 'fast_only': 49, 'fl_original': 49, 'age_only': 49, 'event_triggered': 49,
                          'fl_heuristic': 50, 'fl_risk': 50, 'fl_full': 51, 'fl_bandit': 51, 'fl_fqi_nolease': 51,
                          'fl_global_shield': 55})
        self.assertEqual(rec['pins']['n'], 59)
        self.assertEqual({f: PJ.sha256_file(F._abs(f)) for f in rec['pins']['files']}, rec['pins']['files'])
        self.assertEqual({t: (s['path'], s['sha256'], s['registered']) for t, s in rec['stress'].items()},
                         {t: (PJ.rel(p), PJ.sha256_file(p), True) for t, p in E.reports.items()})
        self.assertEqual(rec['code_sha256'], {f: PJ.sha256_file(ROOT / f) for f in F.CODE_FILES})
        self.assertEqual(rec['test_route_runs']['existing'], [])
        self.assertEqual(rec['deviations'], list(F.DEVIATIONS))

    def test_the_manifest_covers_every_input(self):
        E, rec, files = self.E, self.rec, self.files
        stages = [s['path'] for s in rec['tuning_freeze']['stage_selections']]
        want = {PJ.rel(E.sel), PJ.rel(E.rl_path), PJ.rel(E.p2), *stages,
                *(n['path'] for n in rec['rl_freeze']['networks'].values()), PJ.rel(E.jobs / 'FULL' / TJ.INDEX_NAME),
                *(PJ.rel(p) for blk in TJ.BLOCKS for p in TJ.block_paths(blk, E.jobs)), *rec['pins']['files'],
                *(PJ.rel(p) for p in E.reports.values()), *F.CODE_FILES,
                *(PJ.rel(p) for p in TJ.REGISTERED_INPUTS), *F.REGISTERED_CODE}
        self.assertEqual(set(files), want)
        self.assertEqual(len(files), 100)       # + route split, routes.json, envelope manifest, make_protocol_tables.py
        self.assertEqual(rec['registered_inputs'], {f: files[f] for f in (*(PJ.rel(p) for p in TJ.REGISTERED_INPUTS),
                                                                           *F.REGISTERED_CODE)})
        self.assertEqual({f: PJ.sha256_file(F._abs(f)) for f in files}, files)
        text = F.manifest_text(files)
        self.assertEqual(text, ''.join(f'{files[f]}  {f}\n' for f in sorted(files)))      # sha256sum -c format
        with self.assertRaises(ValueError):                                 # one path, two sha256
            F.merge_files(dict(files), {PJ.rel(E.sel): '0' * 64}, 'test')

    def test_the_entry_cites_every_input(self):
        E = self.E
        with tempfile.TemporaryDirectory() as tmp:
            info = F.write_freeze(self.rec, self.files, tmp, E.protocol)
            rec, rsha, probs = F.read_written(tmp)
            self.assertEqual((probs, rsha, info['record_kept']), ([], info['record_sha256'], False))
            self.assertEqual(rec['manifest'], {'path': PJ.rel(Path(tmp) / F.MANIFEST_NAME),
                                               'sha256': info['manifest_sha256'], 'n_files': len(self.files)})
            lines = F.entry_lines(rec, rsha, when='2026-11-20 09:00 (Beijing time)')
        text = '\n'.join(lines)
        self.assertTrue(lines[0].startswith('**Test freeze, 2026-11-20 09:00 (Beijing time): P4-P6 job files'))
        self.assertEqual([x for x in lines if len(x) > 120], [])
        shas = [rsha, info['manifest_sha256'], PJ.sha256_file(E.sel), PJ.sha256_file(E.rl_path), PJ.sha256_file(E.p2),
                rec['job_files']['index']['sha256'], *(b['job_file_sha256'] for b in rec['job_files']['blocks']),
                *(n['sha256'] for n in rec['rl_freeze']['networks'].values()),
                *(PJ.sha256_file(p) for p in E.reports.values()), rec['tuning_freeze']['L_star']['sha256']]
        self.assertEqual([s for s in shas if s not in text], [])
        for arm in TJ.QNET_FAMILY:
            self.assertIn(f'`{arm}`', text)
        self.assertIn('P4 starts once this entry is sealed', flat(text))
        self.assertIn(f'(sha256 `{PJ.sha256_file(E.p2)}`, entered by this entry)', flat(text))   # P2 manifest
        self.assertIn('No test-route run existed at the freeze: no runs/ entry', flat(text))
        self.assertIn('each such arm is the pair (launcher arm, network file sha256 or envelope sha256)', flat(text))
        protocol = T2J.protocol_text(text)                                  # entered in Sec. 13.2: both cited
        self.assertTrue(P2J.citations(rsha, protocol) and P2J.citations(info['manifest_sha256'], protocol))

    def test_shared_network_names_and_a_p2_manifest_entered_earlier(self):
        with tempfile.TemporaryDirectory() as tmp:
            E = FreezeEnv(Path(tmp) / 'shared')
            ref = TTJ.share_core(E)                                         # fl_full and fl_bandit: one name
            E.refresh()
            E.extra.append(f'* P2 data manifest `{E.p2.name}` (sha256 `{PJ.sha256_file(E.p2)}`).')
            E.write_protocol()
            self.assertEqual(len(E.docs['S2']['networks']), 2)              # one report entry per name
            rec, files, problems = E.freeze()
            self.assertEqual(problems, [])
            rl = rec['rl_freeze']
            self.assertEqual(rl['shared_names'], {ref['name']: ['fl_full', 'fl_bandit']})
            self.assertEqual(rl['networks']['fl_bandit']['sha256'], ref['file_sha256'])
            self.assertEqual(len(rl['p2_manifest']['cited_lines']), 1)
            info = F.write_freeze(rec, files, E.out, E.protocol)
            text = flat('\n'.join(F.entry_lines(*F.read_written(E.out)[:2])))
            self.assertIn(f'Arms `fl_full`, `fl_bandit` share the name `{ref["name"]}` (identical decision cores).',
                          text)
            self.assertIn(f'(sha256 `{PJ.sha256_file(E.p2)}`, entered above in line(s) ', text)
            self.assertIn(info['record_sha256'], text)
            full = E.rl_['networks']['fl_full']['sha256']                   # the reports name fl_bandit's file
            for test in ('S1', 'S2'):                                       # a name stands for the files that share it
                docs = copy.deepcopy(E.docs)
                entries = ([(n['name'], n) for n in docs['S1']['plan']['networks']] if test == 'S1'
                           else list(docs['S2']['networks'].items()))
                self.assertEqual([n['file_sha256'] for name, n in entries if name == ref['name']], [ref['file_sha256']])
                for name, n in entries:
                    if name == ref['name']:
                        n['file_sha256'] = full
                self.assertEqual(F.stress_check(test, write_stress(E.tmp / 'alt', docs)[test], E.tuning_, E.rl_)[1],
                                 [])

    def test_l_star_e5_has_no_s_risk_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            E = FreezeEnv(Path(tmp) / 'e5', 'E5')
            rec, files, problems = E.freeze()
            self.assertEqual(problems, [])
            jf = rec['job_files']
            self.assertEqual((jf['n_lines'], jf['expected_runs_sec_10_1']), (610, 610))
            self.assertEqual((jf['blocks'][5]['n_lines'], jf['blocks'][5].get('job_file')), (0, None))
            self.assertIn('E5 is not B0', jf['blocks'][5]['skipped'])
            self.assertNotIn('fl_risk', jf['pin_sets'])
            self.assertFalse(any('s_risk' in f for f in files))
            self.assertEqual(rec['pins']['n'], 58)                         # no E10
            rc, out, err = E.cli('--write')
            self.assertEqual(rc, 0, err)
            self.assertIn('s_risk: no job file (L* = E5 is not B0: fl_risk is not run', flat(out))


def first_json(text):
    """The first JSON object printed by the CLI (write_freeze's or verify_freeze's summary)."""
    start = text.index('{\n')
    return json.loads(text[start:text.index('\n}\n', start) + 2])


def printed_entry(out):
    """The Sec. 13.2 entry that --write prints after its heading line."""
    return out.split('---- PROTOCOL Sec. 13.2 entry', 1)[1].split('\n', 2)[2].strip()


class FlowTest(unittest.TestCase):
    """--write, the kept record, --entry, the coordinating session's entry and seal, --verify (G-2, G-3)."""

    def test_write_keep_entry_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            E = FreezeEnv(Path(tmp) / 'b0')
            rc, out, err = E.cli()                                          # checked and printed, nothing written
            self.assertEqual(rc, 0, err)
            self.assertIn('test freeze: 100 files (NOT written unless --write)', out)
            self.assertFalse(E.out.exists())
            rc, out, err = E.cli('--write')
            self.assertEqual(rc, 0, err)
            info, entry = first_json(out), printed_entry(out)
            rpath, mpath = E.out / F.RECORD_NAME, E.out / F.MANIFEST_NAME
            self.assertEqual((info['record_sha256'], info['manifest_sha256'], info['n_files'], info['record_kept']),
                             (PJ.sha256_file(rpath), PJ.sha256_file(mpath), 100, False))
            rc, out, err = E.cli('--write')                                 # equal up to 'written': kept
            self.assertEqual(rc, 0, err)
            self.assertEqual((first_json(out)['record_kept'], PJ.sha256_file(rpath)), (True, info['record_sha256']))
            rc, out, err = E.cli('--entry')                                 # the same entry (its time: now)
            self.assertEqual(rc, 0, err)
            self.assertEqual(out.strip().split('\n')[1:], entry.split('\n')[1:])
            rc, out, err = E.cli('--verify')                                # not entered yet
            self.assertEqual(rc, 2)
            self.assertIn('does not cite the test freeze yet', err)
            E.enter(entry)                                                  # appended to Sec. 13.2 and sealed
            rc, out, err = E.cli('--verify')
            self.assertEqual(rc, 0, err)
            self.assertIn('test freeze OK', out)
            cited = first_json(out)['cited_lines']
            self.assertEqual((len(cited['record']), len(cited['manifest'])), (1, 1))
            self.assertEqual(first_json(out)['queue_copies'], [])          # nothing copied yet (review S-6)
            E.queue.mkdir(parents=True)
            names = []
            for blk in TJ.BLOCKS:                                           # the copy step, in name order
                src = TJ.block_paths(blk, E.jobs)[0]
                if src.is_file():
                    shutil.copyfile(src, E.queue / src.name)
                    names.append(src.name)
                    rc, out, err = E.cli('--verify')
                    self.assertEqual((rc, first_json(out)['queue_copies']), (0, names), err)
            self.assertEqual(len(names), 6)
            with changed(E.queue / names[2], edit_line(0, lambda j: j.update(port=2611))):
                rc, out, err = E.cli('--verify')                            # a copy that differs
                self.assertEqual(rc, 1)
                self.assertIn(f'{names[2]}: sha256', err)
            with changed(E.queue / 'b17_other.jsonl', lambda p: p.write_text('{}\n')):
                rc, out, err = E.cli('--verify')                            # a job file the freeze does not hold
                self.assertEqual(rc, 1)
                self.assertIn('b17_other.jsonl: not a job file of the test freeze', err)
            shutil.rmtree(E.queue.parent)
            for force in ((), ('--force',)):                                # a cited record is never rewritten
                rc, out, err = E.cli('--write', *force)
                self.assertEqual(rc, 2)
                self.assertIn('its sha256 is recorded in PROTOCOL Sec. 13.2', err)
            self.assertEqual(PJ.sha256_file(rpath), info['record_sha256'])
            for path in (E.reports['S3'], TJ.block_paths(TJ.BLOCKS[2], E.jobs)[1], E.p2, E.tmp / 'stages/age_s2.json'):
                with changed(path, lambda p: p.write_bytes(p.read_bytes() + b' ')):
                    for flag in ('--verify', '--entry'):
                        rc, out, err = E.cli(flag)
                        self.assertEqual(rc, 1, (path, flag))
                        self.assertIn(f'TEST FREEZE CHANGED\n  {PJ.rel(path)}: sha256', err)
            self.assertEqual(E.cli('--verify')[0], 0)                       # restored
            with changed(E.protocol, lambda p: p.write_text(p.read_text() + '\nedited after the seal\n')):
                rc, out, err = E.cli('--verify')
                self.assertEqual(rc, 2)
                self.assertIn('is not the sealed version', err)
            with changed(rpath, edit_json(lambda d: d.update(note='edited'))):
                self.assertEqual(E.cli('--verify')[0], 2)                   # its sha256 is no longer the cited one
            with changed(mpath, lambda p: p.write_text(''.join(p.read_text().splitlines(True)[1:]))):
                rc, out, err = E.cli('--verify')                            # the record names another manifest
                self.assertEqual(rc, 1)
                self.assertIn('names the manifest', err)
            for bad in (('--write', '--verify'), ('--entry', '--write'), ('--entry', '--verify')):
                with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(io.StringIO()):
                    F.main(list(bad))
                self.assertEqual(cm.exception.code, 2)

    def test_write_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            E = FreezeEnv(Path(tmp) / 'b0')
            rec, files, problems = E.freeze()
            self.assertEqual(problems, [])
            for q in (E.tmp / 'queue_p4' / 'freeze', E.tmp / 'x' / 'jobs.d'):
                with self.assertRaises(PermissionError):
                    F.write_freeze(rec, files, q, E.protocol)
                self.assertFalse(q.exists())
            first = F.write_freeze(rec, files, E.out, E.protocol)
            snap = {p: p.read_bytes() for p in E.out.iterdir()}
            self.assertEqual(sorted(p.name for p in snap), [F.MANIFEST_NAME, F.RECORD_NAME])
            again = F.write_freeze(rec, files, E.out, E.protocol)
            self.assertEqual((again['record_kept'], again['record_sha256']), (True, first['record_sha256']))
            for other_rec, other_files in (({**rec, 'note': 'other'}, files),
                                           (rec, dict(list(files.items())[1:]))):
                with self.assertRaises(FileExistsError):
                    F.write_freeze(other_rec, other_files, E.out, E.protocol)
                self.assertEqual({p: p.read_bytes() for p in snap}, snap)  # nothing written
            prot = E.tmp / 'PROTOCOL_cited.md'
            prot.write_text(T2J.protocol_text(f'* Test freeze record (sha256 `{first["record_sha256"]}`).'))
            with self.assertRaises(PermissionError):
                F.write_freeze({**rec, 'note': 'other'}, files, E.out, prot, force=True)
            self.assertEqual({p: p.read_bytes() for p in snap}, snap)
            forced = F.write_freeze({**rec, 'note': 'other'}, files, E.out, E.protocol, force=True)
            self.assertNotEqual(forced['record_sha256'], first['record_sha256'])
            with self.assertRaises(FileNotFoundError):
                F.read_written(E.tmp / 'nothing')
            with changed(E.out / F.RECORD_NAME, edit_json(lambda d: d.update(schema='x'))), \
                    self.assertRaises(ValueError):
                F.read_written(E.out)


class Shared(unittest.TestCase):
    """One FreezeEnv per class; every test restores what it changes."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.E = FreezeEnv(Path(cls._tmp.name) / 'b0')

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self.assertEqual(self.E.freeze()[2], [])


class RefusalTest(Shared):
    def test_a_test_route_run_refuses_the_freeze(self):
        E = self.E
        for rel in ('matrix/fixed_deep', 'fig3/fl_full_k2.0', 'ablation/fl_bandit', 'ablation/another_arm',
                    'replicates/fast_only'):
            run = E.root / 'outputs/framelease_v4' / rel / 'runs' / 'r1'
            run.mkdir(parents=True)
            try:
                with self.assertRaisesRegex(PermissionError, 'refusing the test freeze: .* exists'):
                    E.freeze()
                rc, out, err = E.cli('--write')
                self.assertEqual((rc, 'REFUSED: refusing the test freeze' in err), (2, True))
                self.assertFalse(E.out.exists())
            finally:
                shutil.rmtree(E.root / 'outputs')
            self.assertFalse(run.exists())
        status = E.root / TJ.QUEUE_REL / 'status.jsonl'
        status.parent.mkdir(parents=True)
        status.write_text('{"id": "v4p4_fixed_deep_k1.0_s11_r1711", "state": "running"}\n')
        try:
            with self.assertRaisesRegex(PermissionError, 'queue_p4/status.jsonl exists'):
                E.freeze()
        finally:
            shutil.rmtree(E.root / 'outputs')

    def test_uncited_or_unsealed_inputs(self):
        E = self.E
        try:
            E.cite = False                                                  # the tuning freeze not in Sec. 13.2
            E.write_protocol()
            with self.assertRaisesRegex(PermissionError, 'not cited in PROTOCOL.md Sec. 13.2'):
                E.freeze()
            self.assertEqual(E.cli()[0], 2)
            E.cite = True
            E.write_protocol(sealed=False)                                  # PROTOCOL.md not the sealed version
            with self.assertRaisesRegex(PermissionError, 'not the sealed version'):
                E.freeze()
            stage_line = E.extra.pop(0)                                     # a stage selection not in Sec. 13.2
            E.write_protocol()
            with self.assertRaisesRegex(PermissionError, 'stage selection lease_s1 .* is not cited'):
                E.freeze()
            E.extra.insert(0, stage_line)
            E.write_protocol()
            with changed(E.tmp / 'stages/lease_s1.json', lambda p: p.write_text('{}\n')):   # changed after its entry
                with self.assertRaisesRegex(ValueError, 'stage selection lease_s1'):
                    E.freeze()
            with changed(E.rl_path, lambda p: TTJ.dump(p, {**json.loads(p.read_text()), 'mode': 'development',
                                                           'frozen': False})):
                with self.assertRaisesRegex(PermissionError, 'never a freeze'):
                    E.freeze()
        finally:
            E.cite = True
            E.write_protocol()

    def test_missing_or_ambiguous_inputs(self):
        E = self.E
        with self.assertRaisesRegex(FileNotFoundError, 'no P4-P6 job files yet'):
            E.freeze(jobs_dir=E.tmp / 'nothing')
        with self.assertRaisesRegex(FileNotFoundError, 'no registered S1 report'):
            E.freeze(stress_dir=E.tmp / 'nothing')
        with tempfile.TemporaryDirectory() as tmp:
            write_stress(tmp, E.docs)
            write_stress(tmp, {'S1': E.docs['S1']}, stamp='20261112T010000Z')
            with self.assertRaisesRegex(ValueError, '2 registered S1 reports'):
                E.freeze(stress_dir=tmp)
            named = [f'{t}={p}' for t, p in E.reports.items()]
            self.assertEqual(E.freeze(stress_dir=tmp, stress=named)[2], [])       # --stress names them
            self.assertEqual(E.freeze(stress_dir=tmp, stress=named[:1])[2], [])   # S1 named, S2 / S3 found
            for bad in (['S4=x'], ['S1'], [named[0], named[0]]):
                with self.assertRaises(ValueError):
                    E.freeze(stress_dir=tmp, stress=bad)
            p = Path(tmp) / 'not_a_report.json'
            TTJ.dump(p, {'schema': 'other'})
            with self.assertRaisesRegex(ValueError, 'is not a S2 report'):
                E.freeze(stress=[f'S2={p}'])
        index = E.jobs / 'FULL' / TJ.INDEX_NAME
        with changed(index, edit_json(lambda d: d['blocks'].reverse())):
            with self.assertRaisesRegex(ValueError, 'is not a framelease_v4.test_jobs_index/1 index of the blocks'):
                E.freeze()

    def test_a_registered_input_off_the_sealed_registration_refuses_the_freeze(self):
        """Review S-1 / S-3: the route split, routes.json, the envelope manifest and the registered code the freeze runs
        must be at their entries of the sealed registration manifest (a copy with one entry changed stands for a file
        changed after registration); otherwise exit 2 and nothing written."""
        E = self.E
        rels = [PJ.rel(p) for p in TJ.REGISTERED_INPUTS] + list(F.REGISTERED_CODE)
        self.assertEqual(len(rels), 8)
        with tempfile.TemporaryDirectory() as tmp:
            for i, rel in enumerate(rels):
                sub = Path(tmp) / str(i)
                sub.mkdir()
                man, seal = TTJ.registration_copy(sub, {rel: '0' * 64})
                with mock.patch.object(REG, 'MANIFEST', man), mock.patch.object(REG, 'SEAL', seal):
                    with self.assertRaisesRegex(ValueError, 'differs from its registration manifest entry'):
                        E.freeze()
                    rc, out, err = E.cli('--write')
                self.assertEqual(rc, 2, rel)
                self.assertIn(f'REFUSED: {rel} (sha256 ', err)
                self.assertFalse(E.out.exists())
            man, seal = TTJ.registration_copy(tmp, sealed=False)
            with mock.patch.object(REG, 'MANIFEST', man), mock.patch.object(REG, 'SEAL', seal), \
                    self.assertRaisesRegex(ValueError, 'not the sealed registration manifest'):
                E.freeze()


def swap_lines(a, b):
    def mutate(path):
        lines = path.read_text().splitlines(True)
        lines[a], lines[b] = lines[b], lines[a]
        path.write_text(''.join(lines))
    return mutate


class ProblemsTest(Shared):
    """The checks of the freeze (exit 1): every input as test_jobs.py wrote and checked it, every pin at the tree, the
    registered S1-S3 reports."""

    def assert_problems(self, what, probs, wants):
        for w in wants:
            self.assertTrue(any(w in p for p in probs), (what, w, probs[:6]))

    def test_every_change_of_a_job_file_spec_check_or_index_is_caught(self):
        E = self.E
        J, index = E.jobs / 'FULL', E.jobs / 'FULL' / TJ.INDEX_NAME
        stale = {'framelease_v4/protocol/p3_rl.py': '4' * 64}
        cases = [
            ('a line\'s kappa', J / 'b14_a_rl.jsonl', edit_line(3, lambda j: j.update(kappa=2.0)),
             ['a_rl: the files differ from index.json', 'is not the job file test_jobs.py generates', 'kappa 2.0']),
            ('a route outside E', J / 'b13_a_lease.jsonl',
             edit_line(0, lambda j: TTJ.set_opt(j, '--route-id', TTJ.SUBSET_R[1])),
             ['is not a test route of subset E']),
            ('a dropped pin', J / 'b11_ti_main.jsonl',
             edit_line(5, lambda j: j['require_sha256'].pop(sorted(j['require_sha256'])[0])),
             ['require_sha256 is not the pin set']),
            ('an added lease override', J / 'b13_a_lease.jsonl',
             edit_line(2, lambda j: j['cmd'].extend(['--lease-overrides', '{"T_pred": 2.0}'])),
             ['the command is not the generated one']),
            ('two lines swapped', J / 'b15_s_seed12.jsonl', swap_lines(0, 1),
             ['s_seed12: ', 'is not the job file test_jobs.py generates', 'port']),
            ('a dry run failed', J / 'b13_a_lease.check.json',
             edit_json(lambda d: d['lines'][0].update(dry_run={'status': 'FAILED'})),
             ['a_lease: not every line passed its checks and its --dry-run']),
            ('a line not ok', J / 'b13_a_lease.check.json', edit_json(lambda d: d['lines'][1].update(ok=False)),
             ['a_lease: not every line passed its checks and its --dry-run']),
            ('check problems', J / 'b14_a_rl.check.json', edit_json(lambda d: d.update(problems=['x'])),
             ['a_rl: the check lists problems']),
            ('check of another job file', J / 'b14_a_rl.check.json',
             edit_json(lambda d: d.update(job_file_sha256='0' * 64)), ['a_rl: the check names another job file']),
            ('check ids out of order', J / 'b14_a_rl.check.json', edit_json(lambda d: d['lines'].reverse()),
             ['a_rl: the check\'s lines are not the job ids of the file, in order']),
            ('check by another module', J / 'b12_f3_k.check.json',
             edit_json(lambda d: d['reused_sha256'].update(stale)), ['f3_k: the check was made by other code']),
            ('check by another generator', J / 'b12_f3_k.check.json',
             edit_json(lambda d: d.update(script_sha256='4' * 64)), ['f3_k: the check was made by other code']),
            ('check schema', J / 'b12_f3_k.check.json', edit_json(lambda d: d.update(schema='x')),
             ['f3_k: the check is not a framelease_v4.test_check/1 record']),
            ('spec changed', J / 'b15_s_seed12.stage.json', edit_json(lambda d: d['jobs'][0].update(kappa=1.5)),
             ['s_seed12: ', 'is not the block spec of the job file']),
            ('index: a block\'s line count', index, edit_json(lambda d: d['blocks'][4].update(n_lines=59)),
             ['s_seed12: the files differ from index.json']),
            ('index: the total', index, edit_json(lambda d: d.update(n_lines=600)), ['n_lines 600 != the 632 lines']),
            ('index: other freezes', index, edit_json(lambda d: d['rl_freeze'].update(sha256='0' * 64)),
             ['was made from other freezes']),
            ('index: cross-block problems', index, edit_json(lambda d: d.update(cross_block_problems=['x'])),
             ['cross-block problems or another test_jobs.py']),
            ('index: another generator', index, edit_json(lambda d: d.update(script_sha256='5' * 64)),
             ['cross-block problems or another test_jobs.py']),
            ('index: s_risk skipped', index, edit_json(lambda d: d['blocks'][5].update(n_lines=0, skipped='x')),
             ['s_risk: the files differ from index.json']),
            ('a block file missing', J / 'b16_s_risk.check.json', lambda p: p.unlink(),
             ['s_risk: [', 'b16_s_risk.check.json\'] missing']),
        ]
        for what, path, mutate, wants in cases:
            with changed(path, mutate):
                self.assert_problems(what, E.freeze()[2], wants)
        # a block spec that differs only in the PROTOCOL.md state at generation: only the index sha256 differs
        with changed(J / 'b15_s_seed12.stage.json', edit_json(lambda d: d.update(tuning_freeze_cited_lines=[99]))):
            self.assertEqual(E.freeze()[2],
                             ['s_seed12: the files differ from index.json (sha256, paths or line count)'])
        with changed(J / 'b14_a_rl.jsonl', edit_line(3, lambda j: j.update(kappa=2.0))):
            rc, out, err = E.cli('--write')
            self.assertEqual(rc, 1)
            self.assertIn('CHECK FAILED', err)
            self.assertFalse(E.out.exists())

    def test_s_risk_files_while_s_risk_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            E = FreezeEnv(Path(tmp) / 'e5', 'E5')
            jf = TJ.block_paths(TJ.BLOCKS[5], E.jobs)[0]
            with changed(jf, lambda p: p.write_text('')):
                self.assert_problems('s_risk file', E.freeze()[2], ['s_risk: skipped now (L* = E5 is not B0'])

    def test_every_stress_report_problem_is_caught(self):
        E = self.E
        net = sorted(E.docs['S2']['networks'])[0]
        stale = {'framelease_v4/protocol/stress_bench.py': '2' * 64}
        cases = [
            ('S3', lambda d: d.update(violations_total=1, **{'pass': False}), 'S3: 1 commits violate Eq. 9'),
            ('S3', lambda d: d.update(n_sequences=1000), 'S3: 1000 sequences'),
            ('S3', lambda d: d.update(targets={'gate': {}}), 'S3: 100000 sequences on [\'gate\']'),
            ('S3', lambda d: d.update(coverage_ok=False), 'a fault class is not covered'),
            ('S3', lambda d: d['provenance']['code_sha256'].update(stale), 'S3: '),
            ('S3', lambda d: d['provenance'].update(code_sha256={}), 'no code_sha256'),
            ('S2', lambda d: d['networks'][net].update(admitted_bound_ge_Dstar=2), 'S2: admitted actions with bound'),
            ('S2', lambda d: d.update(violations_total=1, **{'pass': False}), 'violations 1'),
            ('S2', lambda d: d.update(registered=False, label='development run, not the registered S2'),
             'is not a registered run'),
            ('S2', lambda d: d['networks'][net].update(file_sha256='0' * 64), 'are not the deployed networks'),
            ('S2', lambda d: d['networks'].pop(net), 'are not the deployed networks'),
            ('S2', lambda d: d['slack_grid_s'].pop(), 'S2: 70 slack values'),
            ('S2', lambda d: d.update(replay_fidelity={'ok': False}), 'do not replay faithfully'),
            ('S1', lambda d: d.update(envelope={'path': 'outputs/framelease_v4/envelopes/E5.json', 'sha256': '1' * 64}),
             'S1: the lease ran on'),
            ('S1', lambda d: d.update(per_load=[{'load': 0}]), 'S1: loads [0]'),
            ('S1', lambda d: d.update(shared_cpu=True), 'S1: not run on an exclusive CPU'),
            ('S1', lambda d: d['plan']['networks'][0].update(file_sha256='0' * 64), 'are not the deployed networks'),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for test, mutate, want in cases:
                docs = copy.deepcopy(E.docs)
                mutate(docs[test])
                shutil.rmtree(tmp)
                write_stress(tmp, docs)
                probs = E.freeze(stress_dir=tmp)[2]
                self.assertTrue(probs and all(p.startswith(f'{test}: ') for p in probs), (test, want, probs))
                self.assert_problems(test, probs, [want])
            rc, out, err = E.cli('--stress-dir', tmp)
            self.assertEqual((rc, 'CHECK FAILED' in err), (1, True))

    def test_the_pins(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'pinned.py'
            f.write_text('a = 1\n')
            j1, j2 = Path(tmp) / 'a.jsonl', Path(tmp) / 'b.jsonl'
            j1.write_text(json.dumps({'require_sha256': {str(f): PJ.sha256_file(f)}}) + '\n')
            j2.write_text(json.dumps({'require_sha256': {str(f): '0' * 64}}) + '\n')
            self.assertEqual(F.pins_record([str(j1)]), {'n': 1, 'files': {str(f): PJ.sha256_file(f)},
                                                         'mismatches': []})
            with self.assertRaisesRegex(ValueError, 'pinned with two different sha256'):
                F.pins_record([str(j1), str(j2)])
            f.write_text('a = 2\n')
            self.assertEqual([m['file'] for m in F.pins_record([str(j1)])['mismatches']], [str(f)])
        real = F.pins_record
        bad = {'file': 'framelease_v4/arms/arms_v4.py', 'expected': '0' * 64, 'found': '1' * 64}
        with mock.patch.object(F, 'pins_record', lambda files: {**real(files), 'mismatches': [bad]}):
            self.assertEqual(self.E.freeze()[2], [f'pin {bad["file"]}: sha256 {"1" * 64} != pinned {"0" * 64}'])
        # review S-2: the envelope L* registered at another sha256 than the job files pin it (and the tree holds it)
        L, real_pins = self.E.tuning_['L']['path'], REG.job_pins

        def registered_elsewhere(files=REG.REGISTERED_JOB_FILES):     # pins_record's union of the P4-P6 pins: real
            pins = real_pins(files)
            return {**pins, L: '0' * 64} if tuple(files) == tuple(REG.REGISTERED_JOB_FILES) else pins

        with mock.patch.object(REG, 'job_pins', registered_elsewhere):
            problems = self.E.freeze()[2]
            rc, out, err = self.E.cli()
        on_l = [j['id'] for _, ls, _ in self.E.built for j in ls if (j.get('envelope') or {}).get('path') == L]
        self.assertEqual(len(on_l), 88 + 88 + 22 + 44 + 30)  # FL+H, Full FL in ti_main, f3_k, s_seed12; a_lease, a_rl
        self.assertEqual([p.split(':')[0] for p in problems], on_l)
        self.assertTrue(all('registered P1 lines' in p and L in p for p in problems))
        self.assertEqual(rc, 1)
        self.assertIn('CHECK FAILED', err)
