"""The interim-look guard (framelease_v4/analysis/interim_guard.py; PROTOCOL Secs. 9.11, 9.12, 13). CPU only; the
records, protocol copies, seals and logs are synthetic and live in a temporary directory; the registered route split,
manifest, PROTOCOL.md and seal are only read.

  cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/analysis/tests/test_interim_guard.py

What is shown: only Sec. 13 of PROTOCOL.md counts as a citation; the seal is read for the protocol it names; the
registered PROTOCOL.md equals its seal; each release decision (no record, job file absent or changed, job absent,
outcome or run changed, cut job) and its note; a development record releases only extra routes (job-line route and
recorded run route outside the registered split), never a registered test route, and never summarizes one; the R-2
audit release of a run directory by its recorded route; the summary refusal by split; the guard log (append-only
entries, counts) and the record checks that need no aggregation, including the coverage of the test freeze's job
files.
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

from framelease_v4.analysis import interim_guard as G  # noqa: E402

JOB_FILE, SHA = 'outputs/framelease_v4/queue_p4/jobs.d/t3.jsonl', 'a' * 64


def freeze(registered=True, **jobs):
    """A loaded record (the shape load_freeze returns) with one job file and the given jobs."""
    doc = {'job_files': {JOB_FILE: SHA},
           'jobs': {j: {'job_file': JOB_FILE, 'outcome': o, 'run_dir': r} for j, (o, r) in jobs.items()}}
    return {'doc': doc, 'sha256': 'f' * 64, 'registered': registered}


class Protocol(unittest.TestCase):
    def test_only_sec13_counts(self):
        text = '# P\n\n## 9. Plan\nAAA\n\n## 13. Registration and amendments\n### 13.2\nBBB\n\n## 14. TRIMMED\nCCC\n'
        sec = G.protocol_sec13(text)
        self.assertIn('BBB', sec)
        self.assertNotIn('AAA', sec)
        self.assertNotIn('CCC', sec)
        self.assertEqual(G.protocol_sec13('# P\n## 9. x\n'), '')

    def test_seal_lookup(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'PROTOCOL.md'
            p.write_text('x')
            seal = Path(d) / 'SEAL.sha256'
            seal.write_text(f'{"1" * 64}  framelease_v4/PROTOCOL.md\n{"2" * 64}  {p}\n')
            self.assertEqual(G.sealed_sha256(seal, p), '2' * 64)
            self.assertEqual(G.sealed_sha256(seal, ROOT / 'framelease_v4/PROTOCOL.md'), '1' * 64)
            self.assertIsNone(G.sealed_sha256(Path(d) / 'missing', p))
        # the registered PROTOCOL.md equals its seal (read only)
        self.assertEqual(G.sealed_sha256(G.REG.SEAL, G.REG.PROTOCOL), G.PJ.sha256_file(G.REG.PROTOCOL))


class Release(unittest.TestCase):
    def test_each_decision(self):
        job = {'id': 't3_a'}
        ok = {'outcome': 'ok', 'run_dir': 'runs/x'}
        cases = [
            (None, JOB_FILE, SHA, ok, False, 'pre_freeze'),
            (freeze(t3_a=('ok', 'runs/x')), 'other.jsonl', SHA, ok, False, 'not in the analysis-freeze record'),
            (freeze(t3_a=('ok', 'runs/x')), JOB_FILE, 'b' * 64, ok, False, 'changed since the freeze'),
            (freeze(t3_b=('ok', 'runs/x')), JOB_FILE, SHA, ok, False, 'the job is not in'),
            (freeze(t3_a=('ok', 'runs/y')), JOB_FILE, SHA, ok, False, 'differs from the record'),
            (freeze(t3_a=('sim_failure', 'runs/x')), JOB_FILE, SHA, ok, False, 'differs from the record'),
            (freeze(t3_a=('ok', 'runs/x')), JOB_FILE, SHA, ok, True, 'released: by the analysis-freeze record ffff'),
            (freeze(t3_a=('cut', None)), JOB_FILE, SHA, {'outcome': 'pending'}, True, 'released'),
            (freeze(t3_a=('cut', None)), JOB_FILE, SHA, ok, False, 'differs from the record'),
        ]
        for fz, f, sha, outcome, want, text in cases:
            with self.subTest(text=text, want=want):
                got, note = G.release(fz, job, f, sha, outcome)
                self.assertEqual(got, want)
                self.assertIn(text, note)
                self.assertEqual(G.note_category(note), 'released' if want else note.split(':')[0])
        self.assertIsNone(G.note_category(None))

    def test_development_record_only_releases_extra_routes(self):
        """A record cited by a development PROTOCOL.md copy releases a row only when its job-line route and the route
        its run recorded are outside the registered split; a registered record releases registered routes."""
        reg = {'1711'}
        with tempfile.TemporaryDirectory() as d:
            def run(route):
                p = Path(d) / f'run_{route}'
                p.mkdir()
                (p / 'config.json').write_text(json.dumps({'route': {'route_id': route}}))
                return str(p)
            extra, on_test, nowhere = run('2086'), run('1711'), str(Path(d) / 'missing')
            cases = [('2086', extra, False, True), ('1711', extra, False, False), ('2086', on_test, False, False),
                     ('2086', nowhere, False, False), ('1711', on_test, True, True)]
            for route, run_dir, registered, want in cases:
                with self.subTest(route=route, run=Path(run_dir).name, registered=registered):
                    fz = freeze(registered, t3_a=('ok', run_dir))
                    got, note = G.release(fz, {'id': 't3_a', 'route_id': route}, JOB_FILE, SHA,
                                          {'outcome': 'ok', 'run_dir': run_dir}, reg)
                    self.assertEqual(got, want, note)
                    if not want:
                        self.assertEqual(note, G.DEV_WITHHELD)
                    elif not registered:
                        self.assertIn('DEVELOPMENT', note)
            cut = freeze(False, t3_a=('cut', None))                       # a cut job: no run, the job route decides
            self.assertTrue(G.release(cut, {'id': 't3_a', 'route_id': '2086'}, JOB_FILE, SHA, {'outcome': 'pending'},
                                      reg)[0])
            self.assertFalse(G.release(cut, {'id': 't3_a', 'route_id': '1711'}, JOB_FILE, SHA, {'outcome': 'pending'},
                                       reg)[0])
            self.assertEqual(G.recorded_route(extra), '2086')
            self.assertIsNone(G.recorded_route(nowhere))

    def test_release_run(self):
        tests, reg = {'1711', '2086'}, {'1711'}
        dev, registered = freeze(False), freeze(True)
        cases = [(None, '1792', True, None), (None, '1711', False, 'pre_freeze'), (None, None, False, 'pre_freeze'),
                 (registered, '1711', True, 'released'), (registered, None, True, 'released'),
                 (dev, '1711', False, 'withheld'), (dev, None, False, 'withheld'), (dev, '2086', True, 'released'),
                 (dev, '1792', True, None)]
        for fz, route, want, cat in cases:
            with self.subTest(freeze=None if fz is None else fz['registered'], route=route):
                got, note = G.release_run(fz, route, tests, reg)
                self.assertEqual((got, G.note_category(note)), (want, cat))


class Requests(unittest.TestCase):
    def test_summary_refusal_by_split(self):
        self.assertIsNone(G.summary_refusal('training', None))
        for split in ('test', 'all'):
            self.assertIn('Sec. 9.11', G.summary_refusal(split, None))
            self.assertIsNone(G.summary_refusal(split, freeze()))
        with self.assertRaises(ValueError):
            G.summary_refusal('everything', None)

    def test_development_record_never_summarizes_a_registered_test_route(self):
        rel = {'analysis_use': True, 'test_route': True, 'guard_note': 'released: by the analysis-freeze record x'}
        rows = [dict(rel, job='a', route_id='2086'), dict(rel, job='b', route_id='1711')]
        for split in ('test', 'all'):
            with self.assertRaisesRegex(G.GuardRefused, 'development'):
                G.summary_rows(rows, split, freeze(False), {'1711'})
        self.assertEqual([r['job'] for r in G.summary_rows(rows[:1], 'test', freeze(False), {'1711'})], ['a'])
        self.assertEqual([r['job'] for r in G.summary_rows(rows, 'test', freeze(True), {'1711'})], ['a', 'b'])

    def test_log_is_append_only_and_counted(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / 'sub' / G.LOG_NAME
            self.assertIsNone(G.log_state(log))
            G.log_request(log, 'aggregate', 'refused', 'r1', None, ['x'], arm_summary='test')
            e = G.log_request(log, 'aggregate', 'granted', None, {'path': 'p', 'sha256': 's', 'registered': True},
                              ['x'])
            lines = [json.loads(x) for x in log.read_text().splitlines()]
            self.assertEqual([x['decision'] for x in lines], ['refused', 'granted'])
            self.assertEqual((lines[0]['arm_summary'], lines[0]['schema'], e['freeze']['sha256']),
                             ('test', G.LOG_SCHEMA, 's'))
            for k in ('time', 'user', 'host', 'pid', 'argv'):
                self.assertIn(k, lines[1])
            st = G.log_state(log)
            self.assertEqual((st['entries'], st['refused'], st['sha256']), (2, 1, G.PJ.sha256_file(log)))


class Record(unittest.TestCase):
    def good(self):
        return {'schema': G.FREEZE_SCHEMA, 'frozen': '2027-01-01T00:00:00+0800', 'trigger': 'all_final',
                'cut_amendment': None, 'job_files': {JOB_FILE: SHA},
                'jobs': {'t3_a': {'job_file': JOB_FILE, 'outcome': 'ok', 'run_dir': 'runs/x'}},
                'analysis_code': {'a.py': '1' * 64}, 'route_split_sha256': 'r' * 64}

    def test_record_problems(self):
        code, split = {'a.py': '1' * 64}, 'r' * 64
        self.assertEqual(G.record_problems(self.good(), code, split), [])
        edits = {'no freeze time': lambda r: r.update(frozen=None),
                 'trigger': lambda r: r.update(trigger='early'),
                 'no jobs': lambda r: r.update(jobs={}),
                 'no job files': lambda r: r.update(job_files={}),
                 'job files the record does not list': lambda r: r['jobs']['t3_a'].update(job_file='x.jsonl'),
                 "final outcome in ('ok', 'agent_crashed', 'sim_failure')":
                     lambda r: r['jobs']['t3_a'].update(outcome='cut'),            # a cut job needs trigger cut
                 'frozen code': lambda r: r.update(analysis_code={}),
                 'route split': lambda r: r.update(route_split_sha256=None)}
        for want, edit in edits.items():
            with self.subTest(want):
                rec = self.good()
                edit(rec)
                self.assertTrue(any(want in p for p in G.record_problems(rec, code, split)),
                                G.record_problems(rec, code, split))
        cut = self.good()
        cut.update(trigger='cut', cut_amendment='A9')
        cut['jobs']['t3_a'].update(outcome='cut', run_dir=None)
        self.assertEqual(G.record_problems(cut, code, split), [])
        self.assertEqual(G.record_problems([], code, split), [f'not an analysis-freeze record (schema '
                                                              f'{G.FREEZE_SCHEMA})'])

    def test_coverage_of_the_test_freeze_job_files(self):
        code, split = {'a.py': '1' * 64}, 'r' * 64
        self.assertEqual(G.record_problems(self.good(), code, split, {JOB_FILE: SHA}), [])
        other = 'outputs/framelease_v4/queue_p4/jobs.d/t4.jsonl'
        cases = {'not in the record': {JOB_FILE: SHA, other: SHA}, 'differ from the test freeze': {JOB_FILE: 'b' * 64}}
        for want, required in cases.items():
            with self.subTest(want):
                probs = G.record_problems(self.good(), code, split, required)
                self.assertTrue(any(want in p for p in probs), probs)
        with tempfile.TemporaryDirectory() as d:                         # load_freeze refuses a non-dict list
            with self.assertRaisesRegex(G.GuardRefused, 'job file: sha256'):
                path = Path(d) / 'r.json'
                path.write_text(json.dumps(self.good()))
                G.load_freeze(path, required_job_files=[JOB_FILE])

    def test_analysis_code_covers_every_module(self):
        code = G.analysis_code()
        self.assertEqual(sorted(Path(p).name for p in code), sorted(G.ANALYSIS_MODULES))
        self.assertTrue(all(p.startswith('framelease_v4/analysis/') for p in code))


if __name__ == '__main__':
    unittest.main()
