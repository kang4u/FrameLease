"""Round-2 review of A11: adversarial cases for the class report f1/f1_class_report.py (4c7f3af5) of the reporting rule.

Synthetic verification outputs, and the outputs that framelease_v4/analysis/verify_table1_extra.py (f77b2dcf) writes
for the fixture runs of its own tests. Temporary directories under /tmp only; nothing of the project is written.

Tests named *_holds check that a class does not absorb the case (the row stays unexplained or the report stops).
Tests named *_gap document a case the current class report absorbs although the stated mechanism does not hold; they
assert the current behaviour, so they fail once the gap is closed (then invert them).

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      outputs/framelease_v4/build/AMEND2/a10r7b/f1/review/r2_test_adversarial.py
"""
import contextlib
import csv
import hashlib
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
F1 = ROOT + '/outputs/framelease_v4/build/AMEND2/a10r7b/f1'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = _load('r2_f1_class_report', F1 + '/f1_class_report.py')
DIFF_FIELDS = ('target', 'key', 'field', 'their_field', 'ours', 'theirs', 'abs_diff', 'tolerance', 'status', 'cause',
               'below_grid', 'scope', 'value_source', 'note')
RUN_FIELDS = ('jobs', 'run_dir', 'route_id', 'arm', 'gpu_inflight_boundaries', 'gpu_busy_s_bounds', 'gpu_usage_bounds',
              'plans_by_status', 'checks')


def sha(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def drow(target, key, field, their, ours, theirs, cause='', scope='record'):
    try:
        d = repr(abs(float(ours) - float(theirs)))
    except ValueError:
        d = ''
    return {'target': target, 'key': key, 'field': field, 'their_field': their, 'ours': ours, 'theirs': theirs,
            'abs_diff': d, 'tolerance': '0', 'status': 'differ', 'cause': cause, 'below_grid': '', 'scope': scope,
            'value_source': 'raw', 'note': ''}


RUNS = [dict(jobs=json.dumps(['job_a']), run_dir='runs/a', route_id='1', arm='fixed_deep', gpu_inflight_boundaries='3',
             gpu_busy_s_bounds='[10.0, 10.2]', gpu_usage_bounds='[0.9, 0.92]',
             plans_by_status=json.dumps({'clear': 5, 'no_plan_logged': 2}), checks='{}'),
        dict(jobs=json.dumps(['job_b']), run_dir='runs/b', route_id='2', arm='fixed_deep', gpu_inflight_boundaries='0',
             gpu_busy_s_bounds='[8.0, 8.0]', gpu_usage_bounds='[0.8, 0.8]', plans_by_status=json.dumps({'clear': 5}),
             checks='{}')]


def write(d, diffs, runs=RUNS, status='final', inputs=None):
    with open(os.path.join(d, 'differences.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, DIFF_FIELDS)
        w.writeheader()
        w.writerows(diffs)
    with open(os.path.join(d, 'runs_recomputed.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, RUN_FIELDS)
        w.writeheader()
        w.writerows(runs)
    with open(os.path.join(d, 'cause_plans.csv'), 'w', newline='', encoding='utf-8') as fh:
        fh.write('run_dir,commit_index,job_id,depth,capture_s,cause\n')
    by, by_a = {}, {}
    for r in diffs:
        c = r['cause'] or 'unclassified'
        by[c] = by.get(c, 0) + 1
        if r['scope'] == 'analysis':
            by_a[c] = by_a.get(c, 0) + 1
    t1 = {'status': status, 'verdict': 'DIFFER' if diffs else 'AGREE', 'inputs': inputs or {},
          'comparisons': {'compared': 50, 'differences': len(diffs), 'differences_by_cause': by,
                          'analysis_differences_by_cause': by_a, 'agree_within_bounds_by_cause': {}}}
    with open(os.path.join(d, 'table1_extra.json'), 'w', encoding='utf-8') as fh:
        json.dump(t1, fh)
    with open(os.path.join(d, 'SHA256SUMS'), 'w', encoding='utf-8') as fh:
        for name in sorted(R.INPUTS):
            fh.write('%s  %s\n' % (sha(os.path.join(d, name)), name))


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = R.main(argv)
    return code, out.getvalue(), err.getvalue()


class Synthetic(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='r2_f1_adv_', dir='/tmp')
        self.d = os.path.join(self.tmp, 'out')
        os.makedirs(self.d)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def report(self, diffs, runs=RUNS, status='final', inputs=None):
        write(self.d, diffs, runs, status, inputs)
        code, out, err = run([self.d])
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def records(self, recs, runs_rows):
        q = os.path.join(self.tmp, 'q', 'status.jsonl')
        agg = os.path.join(self.tmp, 'agg', 'runs.csv')
        os.makedirs(os.path.dirname(q), exist_ok=True)
        os.makedirs(os.path.dirname(agg), exist_ok=True)
        with open(q, 'w', encoding='utf-8') as fh:
            fh.writelines(json.dumps(r) + '\n' for r in recs)
        with open(agg, 'w', newline='', encoding='utf-8') as fh:
            w = csv.DictWriter(fh, ('job', 'outcome', 'analysis_use', 'missing_reason', 'dmr', 'ticks'))
            w.writeheader()
            w.writerows(runs_rows)
        return {q: sha(q), agg: sha(agg)}

    def test_analysis_read_values_without_a_class_holds(self):
        """A value the analysis reads that differs for a reason no convention explains stays unexplained, wherever it
        sits (runs.csv, conditions.csv, per_scenario.csv, secondary.csv), and so do an unknown cause, an absent column
        and an arm_summary.csv value without a cause."""
        diffs = [drow('runs.csv', 'job_b', 'eir', 'realized_invalid_tick_ratio', '0.25', '0.2', scope='analysis'),
                 drow('conditions.csv', 'fixed_deep_k1.0_s11/all/eir', 'mean', 'mean', '0.12', '0.11',
                      scope='analysis'),
                 drow('per_scenario.csv', 'fixed_deep_k1.0_s11/2', 'r_cond', 'r_cond', '0.5', '', scope='analysis'),
                 drow('secondary.csv', 'a_minus_b/dmr', 'mean_a', 'mean_a', '0.3', '0.2', scope='analysis'),
                 drow('runs.csv', 'job_b', 'misses', 'realized_misses', '3', '2', cause='F2'),
                 dict(drow('runs.csv', '*', None, 'gpu_usage_recomputed', '', ''), status='absent'),
                 drow('arm_summary.csv', 'fixed_deep/x', 'realized_invalid_tick_ratio', 'realized_invalid_tick_ratio',
                      '0.12', '0.11')]
        rep = self.report(diffs)
        self.assertEqual(rep['differences_by_class'],
                         {'F1': 0, 'F3': 0, 'in_flight': 0, 'not_ok_record': 0, 'unexplained': 7})
        self.assertEqual(rep['unexplained']['analysis_differences'], 4)
        self.assertEqual((rep['outcome'], rep['release']), ('verification failure', 'verification failure'))

    def test_in_flight_run_where_the_analysis_value_differs_holds(self):
        """In a run that ended with a job in flight: gpu_usage (analysis) below the recomputed lower bound like the
        cross-check, or above the upper bound, makes the GPU cross-check rows unexplained too; commits in scope
        'analysis' with exactly the in-flight commits stays unexplained; commits in scope 'record' is in_flight."""
        for ga in ('0.85', '0.95'):
            with self.subTest(gpu_usage=ga):
                diffs = [drow('runs.csv', 'job_a', 'gpu_usage', 'gpu_usage', '0.91', ga, scope='analysis'),
                         drow('runs.csv', 'job_a', 'gpu_usage', 'gpu_usage_recomputed', '0.91', '0.85'),
                         drow('runs.csv', 'job_a', 'gpu_busy_s', 'gpu_busy_recomputed_s', '10.1', '9.4'),
                         drow('runs.csv', 'job_a', 'commits', 'commits', '40', '38', scope='analysis'),
                         drow('runs.csv', 'job_a', 'commits', 'commits', '40', '38')]
                rep = self.report(diffs)
                self.assertEqual(rep['differences_by_class'],
                                 {'F1': 0, 'F3': 0, 'in_flight': 1, 'not_ok_record': 0, 'unexplained': 4})
                self.assertEqual(rep['outcome'], 'verification failure')

    def test_in_flight_gpu_difference_of_any_size_gap(self):
        """GAP (should-fix S1): for the GPU cross-check columns the class checks the direction (registered below the
        recomputed lower bound) and the run's in-flight state, not the size: a registered gpu_busy_recomputed_s of 0
        (10.1 s recomputed) or gpu_usage_recomputed of 0 is in_flight. Neither column is read by the analysis."""
        diffs = [drow('runs.csv', 'job_a', 'gpu_busy_s', 'gpu_busy_recomputed_s', '10.1', '0'),
                 drow('runs.csv', 'job_a', 'gpu_usage', 'gpu_usage_recomputed', '0.91', '0')]
        rep = self.report(diffs)
        self.assertEqual(rep['differences_by_class']['in_flight'], 2)
        self.assertEqual(rep['outcome'], 'pre-specified classes only')
        big = {x['column']: x['abs_diff'] for x in rep['class_in_flight']['largest_abs_diff']}
        self.assertAlmostEqual(big['gpu_busy_recomputed_s'], 10.1)       # the size is visible in the report

    def test_not_ok_job_whose_row_is_used_holds(self):
        timeout = [{'event': 'end', 'id': 'job_a', 'final': True, 'outcome': 'timeout'}]
        diffs = [drow('runs.csv', 'job_a', 'dmr', 'dmr', '0.25', ''), drow('runs.csv', 'job_a', 'ticks', 'ticks',
                                                                              '3256', '')]
        for use in ('True', 'true', '1'):
            with self.subTest(analysis_use=use):
                inputs = self.records(timeout, [{'job': 'job_a', 'outcome': 'sim_failure', 'analysis_use': use,
                                                 'missing_reason': '', 'dmr': '', 'ticks': ''}])
                rep = self.report(diffs, inputs=inputs)
                self.assertEqual(rep['differences_by_class']['unexplained'], 2)

    def test_not_ok_record_with_an_ok_runner_outcome_gap(self):
        """GAP (must-fix M1): the runner's 'result_with_warnings' is an OK outcome (framelease_v2/gpu_queue.py and
        select_stage.OK_OUTCOMES: a valid record), and aggregate_v4.job_row then runs run_fields (runs.csv outcome
        'ok'). Empty cells there come from a failed metric step (missing_reason 'no_metrics'), not from the early
        return of a job that is not ok; the class report still puts them in not_ok_record because it compares the
        runner outcome with the literal 'ok' and never reads the runs.csv outcome. A final record without an
        outcome is absorbed the same way."""
        diffs = [drow('runs.csv', 'job_a', 'dmr', 'dmr', '0.25', ''),
                 drow('runs.csv', 'job_a', 'ticks', 'ticks', '3256', '')]
        for name, rec in (('result_with_warnings', {'outcome': 'result_with_warnings'}), ('no outcome', {})):
            with self.subTest(case=name):
                inputs = self.records([dict({'event': 'end', 'id': 'job_a', 'final': True}, **rec)],
                                      [{'job': 'job_a', 'outcome': 'ok', 'analysis_use': 'False',
                                        'missing_reason': 'no_metrics', 'dmr': '', 'ticks': ''}])
                rep = self.report(diffs, inputs=inputs)
                self.assertEqual(rep['differences_by_class']['not_ok_record'], 2)
                self.assertEqual(rep['outcome'], 'pre-specified classes only')

    def test_missing_or_altered_inputs_holds(self):
        diffs = [drow('runs.csv', 'job_a', 'dmr', 'dmr', '0.25', '')]
        timeout = [{'event': 'end', 'id': 'job_a', 'final': True, 'outcome': 'timeout'}]
        row = {'job': 'job_a', 'outcome': 'sim_failure', 'analysis_use': 'False', 'missing_reason': 'sim_failure',
               'dmr': '', 'ticks': ''}
        for name in R.INPUTS + ('SHA256SUMS',):
            with self.subTest(missing=name):
                write(self.d, diffs, inputs=self.records(timeout, [row]))
                os.remove(os.path.join(self.d, name))
                self.assertEqual(run([self.d])[0], 2)
        for name in R.INPUTS:
            with self.subTest(altered=name):
                write(self.d, diffs, inputs=self.records(timeout, [row]))
                with open(os.path.join(self.d, name), 'a', encoding='utf-8') as fh:
                    fh.write('\n')
                self.assertEqual(run([self.d])[0], 2)
        inputs = self.records(timeout, [row])
        for name, mutate in (('status.jsonl changed', 'q'), ('runs.csv changed', 'agg'), ('status.jsonl gone', 'rm')):
            with self.subTest(recorded=name):
                write(self.d, diffs, inputs=inputs)
                q, agg = list(inputs)
                if mutate == 'q':
                    with open(q, 'a', encoding='utf-8') as fh:
                        fh.write(json.dumps({'event': 'start', 'id': 'job_x'}) + '\n')
                elif mutate == 'agg':
                    with open(agg, 'a', encoding='utf-8') as fh:
                        fh.write('job_x,ok,True,,,\n')
                else:
                    os.remove(q)
                code, out, err = run([self.d])
                self.assertEqual((code, out), (2, ''), err)
                inputs = self.records(timeout, [row])
        with self.subTest(recorded='runs.csv not recorded'):
            q = [p for p in inputs if p.endswith('status.jsonl')][0]
            rep = self.report(diffs, inputs={q: inputs[q]})
            self.assertEqual(rep['differences_by_class']['unexplained'], 1)


class OnVerifierOutput(unittest.TestCase):
    """End to end: the verifier's own outputs for its fixture run (it ends with job 3 in flight)."""

    @classmethod
    def setUpClass(cls):
        cls.vt = _load('r2_vt', ROOT + '/framelease_v4/analysis/verify_table1_extra.py')
        cls.fx = _load('r2_vt_fixtures', ROOT + '/framelease_v4/analysis/tests/test_verify_table1_extra.py')
        cls.tmp = tempfile.mkdtemp(prefix='r2_f1_adv_vt_', dir='/tmp')
        cls.run_dir = cls.fx.make_run(cls.tmp, 'run')
        cls.r = cls.vt.recompute_run(cls.run_dir)
        with open(os.path.join(cls.run_dir, 'raw', 'agent', 'framelease', 'summary.json'), 'w') as fh:
            json.dump(cls.fx.summary_from(dict(cls.r)), fh)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def verify(self, name, row, outcome=None):
        q = os.path.join(self.tmp, 'q_' + name)
        agg = os.path.join(self.tmp, 'agg_' + name)
        os.makedirs(agg)
        argv = ['--agg', agg, '--out', os.path.join(self.tmp, 'out_' + name)]
        if outcome is not None:
            os.makedirs(q)
            self.fx.write_jsonl(os.path.join(q, 'status.jsonl'), [
                {'event': 'end', 'id': 'job1', 'final': True, 'run_dir': self.run_dir, 'outcome': outcome,
                 'job': {'route_id': '990001'}, 'result': {'action_age_p50_s': None, 'fallback_tick_ratio': None}}])
            argv = ['--queue', q] + argv
        self.fx.write_csv(os.path.join(agg, 'runs.csv'), [row])
        code = self.vt.main(argv)
        self.assertEqual(code, self.vt.EXIT_DIFFER)
        return R.report(argv[-1])

    def test_fixture_ends_in_flight(self):
        self.assertGreaterEqual(self.r['gpu_inflight_boundaries'], 1)

    def test_in_flight_cross_check_of_any_size_gap(self):
        """GAP (should-fix S1) on the verifier's output: runs.csv gpu_busy_recomputed_s 0.01 s and
        gpu_usage_recomputed 0.01 (an aggregator defect, far below the in-flight work) are class in_flight."""
        row = self.fx.runs_row('job1', self.run_dir, self.r, gpu_busy_recomputed_s=0.01, gpu_usage_recomputed=0.01)
        rep = self.verify('size', row)
        self.assertEqual(rep['differences_by_class'],
                         {'F1': 0, 'F3': 0, 'in_flight': 2, 'not_ok_record': 0, 'unexplained': 0})

    def test_in_flight_run_with_gpu_usage_above_the_bounds_holds(self):
        row = self.fx.runs_row('job1', self.run_dir, self.r, gpu_usage=self.r['gpu_usage_bounds'][1] + 0.05,
                               gpu_busy_recomputed_s=self.r['gpu_busy_s_bounds'][0] - 0.1,
                               gpu_usage_recomputed=self.r['gpu_usage_bounds'][0] - 0.01)
        rep = self.verify('above', row)
        self.assertEqual(rep['differences_by_class']['in_flight'], 0)
        self.assertEqual(rep['unexplained']['analysis_differences'], 1)
        self.assertEqual(rep['outcome'], 'verification failure')

    def _empty_row(self, **over):
        full = self.fx.runs_row('job1', self.run_dir, self.r)
        ids = ('job', 'route_id', 'protocol_arm', 'candidate', 'kappa', 'seed', 'phase', 'block', 'test_route')
        row = {k: (v if k in ids else None) for k, v in full.items()}
        row.update(over)
        return row

    def test_not_ok_runner_with_used_row_holds(self):
        row = self._empty_row(run_dir=None, selected_run=self.run_dir, outcome='sim_failure', analysis_use='True',
                              missing_reason='')
        rep = self.verify('used', row, outcome='timeout')
        self.assertEqual(rep['differences_by_class']['not_ok_record'], 0)
        self.assertGreater(rep['unexplained']['analysis_differences'], 0)
        self.assertEqual(rep['outcome'], 'verification failure')

    def test_valid_run_dropped_by_a_failed_metric_step_gap(self):
        """GAP (must-fix M1) on the verifier's output: the runner reports 'result_with_warnings' (a valid record);
        aggregate_v4.py selects the run (outcome 'ok', run_dir set) but its metric step failed: analysis_use False,
        missing_reason 'no_metrics', every metric empty, so the route leaves Table I. Every difference lands in class
        not_ok_record and the report releases the columns."""
        row = self._empty_row(run_dir=self.run_dir, selected_run=self.run_dir, outcome='ok', analysis_use='False',
                              missing_reason='no_metrics')
        rep = self.verify('rww', row, outcome='result_with_warnings')
        self.assertGreater(rep['differences_by_class']['not_ok_record'], 30)
        self.assertEqual(rep['differences_by_class']['unexplained'], 0)
        self.assertEqual(rep['outcome'], 'pre-specified classes only')
        rep_ok = self.verify('ok', row, outcome='ok')                  # the same row with runner outcome 'ok'
        self.assertEqual(rep_ok['outcome'], 'verification failure')


if __name__ == '__main__':
    unittest.main()
