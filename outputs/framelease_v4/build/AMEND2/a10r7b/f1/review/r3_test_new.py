"""Round-3 review of A11: the round-2 counter-examples inverted, and new counter-examples against the class report
f1/f1_class_report.py of fix pass 3 (f53e21f8). Synthetic verification outputs and the outputs that
framelease_v4/analysis/verify_table1_extra.py (f77b2dcf) writes for the fixture run of its own tests; /tmp only.

Tests named *_holds: the class report does not absorb the case. Tests named *_gap: a case it absorbs although the
rule as written does not cover it (asserting the current behaviour).

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      outputs/framelease_v4/build/AMEND2/a10r7b/f1/review/r3_test_new.py
"""
import contextlib
import csv
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = '/home/kang/Desktop/DAC'
HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = _load('r3_f1_class_report', ROOT + '/outputs/framelease_v4/build/AMEND2/a10r7b/f1/f1_class_report.py')
R2 = _load('r3_r2_helpers', os.path.join(HERE, 'r2_test_adversarial.py'))     # write(), drow(), RUNS of round 2


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = R.main(argv)
    return code, out.getvalue(), err.getvalue()


def finalize(d, **t1):
    """Set fields of table1_extra.json and rewrite SHA256SUMS (as the verifier writes it last)."""
    p = os.path.join(d, 'table1_extra.json')
    doc = json.load(open(p, encoding='utf-8'))
    doc.update(t1)
    json.dump(doc, open(p, 'w', encoding='utf-8'))
    with open(os.path.join(d, 'SHA256SUMS'), 'w', encoding='utf-8') as fh:
        for name in sorted(R.INPUTS):
            fh.write('%s  %s\n' % (R.sha256(os.path.join(d, name)), name))


REGISTERED = {'script_sha256': R.REGISTERED_VERIFIER, 'options': {'runs_csv_values': False}}


class Synthetic(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='r3_f1_new_', dir='/tmp')
        self.d = os.path.join(self.tmp, 'out')
        os.makedirs(self.d)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def records(self, recs, rows):
        q = os.path.join(self.tmp, 'q', 'status.jsonl')
        agg = os.path.join(self.tmp, 'agg', 'runs.csv')
        os.makedirs(os.path.dirname(q), exist_ok=True)
        os.makedirs(os.path.dirname(agg), exist_ok=True)
        with open(q, 'w', encoding='utf-8') as fh:
            fh.writelines(json.dumps(r) + '\n' for r in recs)
        with open(agg, 'w', newline='', encoding='utf-8') as fh:
            w = csv.DictWriter(fh, ('job', 'outcome', 'analysis_use', 'missing_reason', 'dmr', 'ticks'))
            w.writeheader()
            w.writerows(rows)
        return {q: R.sha256(q), agg: R.sha256(agg)}

    def report(self, diffs, inputs=None, **t1):
        R2.write(self.d, diffs, inputs=inputs)
        finalize(self.d, **dict(REGISTERED, **t1))
        code, out, err = run([self.d])
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def test_round2_m1_counter_examples_now_fail_holds(self):
        """Round-2 M1 inverted: runner 'result_with_warnings', ' ok ', 'OK' or no outcome with runs.csv outcome 'ok' or
        empty; every row unexplained and, from the registered verifier with status final, release 'verification
        failure'."""
        diffs = [R2.drow('runs.csv', 'job_a', 'dmr', 'dmr', '0.25', ''),
                 R2.drow('runner result', 'job_a', 'action_age_p50_s', 'result.action_age_p50_s', '0.8', '')]
        end = {'event': 'end', 'id': 'job_a', 'final': True}
        for runner in ({'outcome': 'result_with_warnings'}, {}, {'outcome': ' ok '}, {'outcome': None}):
            for agg in ('ok', '', ' ok'):
                with self.subTest(runner=runner, agg=agg):
                    inputs = self.records([dict(end, **runner)],
                                          [{'job': 'job_a', 'outcome': agg, 'analysis_use': 'False',
                                            'missing_reason': 'no_metrics', 'dmr': '', 'ticks': ''}])
                    rep = self.report(diffs, inputs=inputs)
                    self.assertEqual(rep['differences_by_class']['not_ok_record'], 0)
                    self.assertEqual((rep['outcome'], rep['release']), ('verification failure',) * 2)

    def test_not_ok_record_still_holds_its_mechanism(self):
        """The P1 case (runner 'timeout', runs.csv 'sim_failure', analysis_use False, cells empty) and 'agent_crashed'
        stay in the class and release 'pre-specified classes only' from the registered verifier."""
        diffs = [R2.drow('runs.csv', 'job_a', 'dmr', 'dmr', '0.25', ''),
                 R2.drow('runner result', 'job_a', 'action_age_p50_s', 'result.action_age_p50_s', '0.8', '')]
        for runner, agg in (('timeout', 'sim_failure'), ('agent_crash', 'agent_crashed')):
            with self.subTest(runner=runner):
                inputs = self.records([{'event': 'end', 'id': 'job_a', 'final': True, 'outcome': runner}],
                                      [{'job': 'job_a', 'outcome': agg, 'analysis_use': 'False',
                                        'missing_reason': agg, 'dmr': '', 'ticks': ''}])
                rep = self.report(diffs, inputs=inputs)
                self.assertEqual(rep['differences_by_class']['not_ok_record'], 2)
                self.assertEqual(rep['class_not_ok_record']['jobs'],
                                 {'job_a': {'runner_outcome': runner, 'runs_csv_outcome': agg}})
                self.assertEqual(rep['release'], 'pre-specified classes only')

    def test_release_checks_holds(self):
        diffs = [R2.drow('runs.csv', 'job_b', 'misses', 'realized_misses', '2', '1', cause='F1')]
        for name, t1, want in (('registered', {}, 'pre-specified classes only'),
                               ('development status', {'status': 'development'}, 'not final'),
                               ('other verifier', {'script_sha256': 'f77b2dcf'}, 'not final'),
                               ('upper-case sha256', {'script_sha256': R.REGISTERED_VERIFIER.upper()}, 'not final'),
                               ('runs_csv_values string', {'options': {'runs_csv_values': 'false'}}, 'not final'),
                               ('runs_csv_values 0', {'options': {'runs_csv_values': 0}}, 'not final')):
            with self.subTest(case=name):
                rep = self.report(diffs, **t1)
                self.assertEqual((rep['outcome'], rep['release']), ('pre-specified classes only', want))

    def test_commits_without_in_flight_boundaries_holds(self):
        runs = [dict(R2.RUNS[0], gpu_inflight_boundaries='0')] + R2.RUNS[1:]
        diffs = [R2.drow('runs.csv', 'job_a', 'commits', 'commits', '40', '38')]
        R2.write(self.d, diffs, runs=runs)
        finalize(self.d, **REGISTERED)
        rep = json.loads(run([self.d])[1])
        self.assertEqual(rep['differences_by_class']['unexplained'], 1)


class OnVerifierOutput(unittest.TestCase):
    """End to end on the verifier's outputs for its fixture run without summary.json (as a timed-out run)."""

    @classmethod
    def setUpClass(cls):
        cls.vt = _load('r3_vt', ROOT + '/framelease_v4/analysis/verify_table1_extra.py')
        cls.fx = _load('r3_vt_fixtures', ROOT + '/framelease_v4/analysis/tests/test_verify_table1_extra.py')
        cls.tmp = tempfile.mkdtemp(prefix='r3_f1_new_vt_', dir='/tmp')
        cls.run_dir = cls.fx.make_run(cls.tmp, 'run', drop=('summary.json',))
        cls.r = cls.vt.recompute_run(cls.run_dir)
        cls.run_s = cls.fx.make_run(cls.tmp, 'run_s', drop=('summary.json',))   # with summary.json (a used row)
        cls.r_s = cls.vt.recompute_run(cls.run_s)
        with open(os.path.join(cls.run_s, 'raw', 'agent', 'framelease', 'summary.json'), 'w') as fh:
            json.dump(cls.fx.summary_from(dict(cls.r_s)), fh)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def empty_row(self, run_dir=None, **over):
        run_dir = run_dir or self.run_dir
        full = self.fx.runs_row('job1', run_dir, self.r)
        ids = ('job', 'route_id', 'protocol_arm', 'candidate', 'kappa', 'seed', 'phase', 'block', 'test_route')
        row = {k: (v if k in ids else None) for k, v in full.items()}
        row.update(run_dir=None, selected_run=run_dir, outcome='sim_failure', analysis_use='False',
                   missing_reason='sim_failure')
        row.update(over)
        return row

    def queue(self, name, outcome, run_dir=None):
        q = os.path.join(self.tmp, name)
        os.makedirs(q, exist_ok=True)
        self.fx.write_jsonl(os.path.join(q, 'status.jsonl'), [
            {'event': 'end', 'id': 'job1', 'final': True, 'run_dir': run_dir or self.run_dir, 'outcome': outcome,
             'job': {'route_id': '990001'}, 'result': {'action_age_p50_s': None, 'fallback_tick_ratio': None}}])
        return q

    def verify(self, name, queues, rows):
        agg = os.path.join(self.tmp, 'agg_' + name)
        os.makedirs(agg)
        self.fx.write_csv(os.path.join(agg, 'runs.csv'), rows)
        out = os.path.join(self.tmp, 'out_' + name)
        argv = sum((['--queue', q] for q in queues), []) + ['--agg', agg, '--out', out]
        self.assertEqual(self.vt.main(argv), self.vt.EXIT_DIFFER)
        return R.report(out)

    def test_two_queues_read_in_another_order_gap(self):
        """NEW counter-example 1. The same job holds a final record in two queues: 'timeout' in q_z, 'ok' in q_a. The
        verifier, given --queue q_z --queue q_a, keeps the last final record ('ok', its load_runner_records), so the
        rule ("as the verifier reads them") gives a runner outcome 'ok' and no class. The class report reads the queues
        in the order of table1_extra.json 'inputs', which the verifier writes with sorted keys (dump_json), takes
        'timeout' from q_z and absorbs every difference."""
        qz, qa = self.queue('q_z', 'timeout'), self.queue('q_a', 'ok')
        rep = self.verify('order', [qz, qa], [self.empty_row()])
        self.assertEqual(rep['class_not_ok_record']['jobs'],
                         {'job1': {'runner_outcome': 'timeout', 'runs_csv_outcome': 'sim_failure'}})
        self.assertEqual(rep['differences_by_class']['unexplained'], 0)
        rep_one = self.verify('one', [qa], [self.empty_row()])              # the verifier's own view: failure
        self.assertEqual(rep_one['outcome'], 'verification failure')

    def test_duplicate_runs_csv_rows(self):
        """NEW counter-example 2. Two runs.csv rows for one job. A used row whose values differ stays unexplained in
        either order (holds). An agreeing used row followed by an empty unused row: the class report takes the last
        row (sim_failure, False) and absorbs the empty cells of the second row; the analysis reads the first row,
        which agrees, so no analysis value is hidden, but the duplicate row itself passes (observation)."""
        good = self.fx.runs_row('job1', self.run_s, self.r_s, outcome='ok', missing_reason='')
        bad = dict(good, dmr=0.987)
        empty = self.empty_row(self.run_s)
        q = self.queue('q_dup', 'timeout', self.run_s)
        for name, rows in (('bad first', [bad, empty]), ('bad last', [empty, bad])):
            with self.subTest(case=name):
                rep = self.verify('dup_' + name.replace(' ', '_'), [q], rows)
                self.assertGreaterEqual(rep['unexplained']['analysis_differences'], 1)
                self.assertEqual(rep['outcome'], 'verification failure')
        rep = self.verify('dup_good_first', [q], [good, empty])
        self.assertEqual(rep['differences_by_class']['unexplained'], 0)
        self.assertGreater(rep['differences_by_class']['not_ok_record'], 30)
        rep = self.verify('dup_good_last', [q], [empty, good])
        self.assertEqual(rep['differences_by_class']['not_ok_record'], 0)
        self.assertEqual(rep['outcome'], 'verification failure')


if __name__ == '__main__':
    unittest.main()
