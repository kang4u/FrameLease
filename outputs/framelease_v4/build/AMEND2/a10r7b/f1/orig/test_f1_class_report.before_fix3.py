"""Tests of f1_class_report.py (item F1A11): synthetic verification outputs, and the outputs that
framelease_v4/analysis/verify_table1_extra.py itself writes for a synthetic case with a class F1 difference and for a
run that ends with a job in flight (its own test fixtures). Temporary directories under /tmp only; nothing of the
project is written.

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      outputs/framelease_v4/build/AMEND2/a10r7b/f1/test_f1_class_report.py
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
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/home/kang/Desktop/DAC'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = _load('f1_class_report', os.path.join(HERE, 'f1_class_report.py'))

DIFF_FIELDS = ('target', 'key', 'field', 'their_field', 'ours', 'theirs', 'abs_diff', 'tolerance', 'status', 'cause',
               'below_grid', 'scope', 'value_source', 'note')
RUN_FIELDS = ('jobs', 'run_dir', 'route_id', 'arm', 'gpu_inflight_boundaries', 'gpu_busy_s_bounds', 'gpu_usage_bounds',
              'plans_by_status', 'checks')
PLAN_FIELDS = ('run_dir', 'commit_index', 'job_id', 'depth', 'capture_s', 'cause')


def sha(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def row(target, key, field, their, ours, theirs, cause, scope='record', abs_diff=None):
    d = abs(float(ours) - float(theirs)) if abs_diff is None else abs_diff
    return {'target': target, 'key': key, 'field': field, 'their_field': their, 'ours': ours, 'theirs': theirs,
            'abs_diff': '' if d == '' else repr(d), 'tolerance': '0', 'status': 'differ', 'cause': cause,
            'below_grid': '', 'scope': scope, 'value_source': 'raw', 'note': ''}


RUNS = [{'jobs': json.dumps(['job_a1']), 'run_dir': 'runs/a1', 'route_id': '1', 'arm': 'fast_only'},
        {'jobs': json.dumps(['job_a2']), 'run_dir': 'runs/a2', 'route_id': '2', 'arm': 'fast_only'},
        {'jobs': json.dumps(['job_b1']), 'run_dir': 'runs/b1', 'route_id': '1', 'arm': 'fixed_deep'}]
MIXED = [
    row('runs.csv', 'job_a1', 'log_censored_plans', 'realized_log_censored_plans', '3', '5', 'F1'),
    row('runs.csv', 'job_a1', 'eir', 'realized_invalid_tick_ratio', '0.25', '0.2', 'F1', scope='analysis'),
    row('runs.csv', 'job_a2', 'log_censored_plans', 'realized_log_censored_plans', '1', '2', 'F1'),
    row('runs.csv', 'job_b1', 'log_censored_plans', 'realized_log_censored_plans', '4', '11', 'F1'),
    row('arm_summary.csv', 'fast_only/fast_only/1.0/11/P4/b', 'realized_invalid_tick_ratio',
        'realized_invalid_tick_ratio', '0.12', '0.11', 'F1'),
    row('conditions.csv', 'fast_only_k1.0_s11/all/eir', 'mean', 'mean', '0.12', '0.11', 'F1', scope='analysis'),
    row('conditions.csv', 'fast_only_k1.0_s11/all/eir', 'max', 'max', '0.25', '0.2', 'F1', scope='analysis'),
    row('per_scenario.csv', 'fast_only_k1.0_s11/1', 'eir', 'eir', '0.25', '0.2', 'F1', scope='analysis'),
    row('runs.csv', 'job_b1', 'misses', 'realized_misses', '2', '1', 'F3'),
    row('runs.csv', 'job_b1', 'gpu_usage', 'gpu_usage_recomputed', '0.99', '0.98', ''),
]


def write(d, diffs, runs=RUNS, plans=(), counts=None, status='final', within=None, sums=True, **t1_extra):
    """A verification output as verify_table1_extra.py writes it: the four data files, then SHA256SUMS over them."""
    with open(os.path.join(d, 'differences.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, DIFF_FIELDS)
        w.writeheader()
        w.writerows(diffs)
    with open(os.path.join(d, 'runs_recomputed.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, RUN_FIELDS)
        w.writeheader()
        w.writerows(runs)
    with open(os.path.join(d, 'cause_plans.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, PLAN_FIELDS)
        w.writeheader()
        w.writerows(plans)
    by, by_a = {}, {}
    for r in diffs:
        c = r['cause'] or 'unclassified'
        by[c] = by.get(c, 0) + 1
        if r['scope'] == 'analysis':
            by_a[c] = by_a.get(c, 0) + 1
    if counts is not None:
        by = counts
    t1 = {'status': status, 'verdict': 'DIFFER' if diffs else 'AGREE',
          'comparisons': {'compared': 100, 'differences': len(diffs), 'differences_by_cause': by,
                          'analysis_differences_by_cause': by_a, 'agree_within_bounds_by_cause': within or {}}}
    t1.update(t1_extra)
    with open(os.path.join(d, 'table1_extra.json'), 'w', encoding='utf-8') as fh:
        json.dump(t1, fh)
    if sums:
        with open(os.path.join(d, 'SHA256SUMS'), 'w', encoding='utf-8') as fh:
            for name in sorted(R.INPUTS):
                fh.write('%s  %s\n' % (sha(os.path.join(d, name)), name))


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = R.main(argv)
    return code, out.getvalue(), err.getvalue()


def columns(rep):
    return {(x['target'], x['metric'], x['column']): x for x in rep['class_F1']['largest_abs_diff']}


class ClassReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='f1_class_test_', dir='/tmp')
        self.d = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_mixed_causes(self):
        plans = [{'run_dir': 'runs/a1', 'commit_index': '3', 'job_id': '7', 'depth': '1', 'capture_s': '20.0',
                  'cause': 'F1'},
                 {'run_dir': 'runs/b1', 'commit_index': '9', 'job_id': '8', 'depth': '2', 'capture_s': '30.0',
                  'cause': 'F1'},
                 {'run_dir': 'runs/b1', 'commit_index': '4', 'job_id': '2', 'depth': '1', 'capture_s': '10.0',
                  'cause': 'F3'}]
        write(self.d, MIXED, plans=plans, within={'F1': 2, 'F3': 3})
        code, out, _ = run([self.d])
        self.assertEqual(code, 0)
        rep = json.loads(out)
        c = rep['class_F1']
        self.assertEqual(rep['status'], 'final')
        self.assertEqual(rep['differences'], 10)
        self.assertEqual(c['differences'], 8)
        self.assertEqual(c['analysis_differences'], 4)
        self.assertEqual(c['differences_without_abs_diff'], 0)
        self.assertEqual(c['runs'], 3)
        self.assertEqual(c['runs_per_arm'], {'fast_only': {'runs': 2, 'runs_with_analysis_difference': 1},
                                             'fixed_deep': {'runs': 1, 'runs_with_analysis_difference': 0}})
        cols = columns(rep)
        self.assertEqual(cols[('runs.csv', '', 'realized_log_censored_plans')]['abs_diff'], 7.0)
        self.assertEqual(cols[('runs.csv', '', 'realized_log_censored_plans')]['key'], 'job_b1')
        self.assertEqual(cols[('runs.csv', '', 'realized_log_censored_plans')]['rows'], 3)
        self.assertAlmostEqual(cols[('conditions.csv', 'eir', 'mean')]['abs_diff'], 0.01)
        self.assertAlmostEqual(cols[('conditions.csv', 'eir', 'max')]['abs_diff'], 0.05)
        self.assertAlmostEqual(cols[('per_scenario.csv', 'eir', 'eir')]['abs_diff'], 0.05)
        self.assertAlmostEqual(cols[('arm_summary.csv', '', 'realized_invalid_tick_ratio')]['abs_diff'], 0.01)
        self.assertEqual(len(cols), 6)
        self.assertEqual({x['rows_without_abs_diff'] for x in cols.values()}, {0})
        self.assertEqual(c['plans'], {'plans': 2, 'run_dirs': 2})
        self.assertEqual((c['agree_within_bounds'], rep['agree_within_bounds_by_cause']), (2, {'F1': 2, 'F3': 3}))
        self.assertEqual(rep['differences_by_class'],
                         {'F1': 8, 'F3': 1, 'in_flight': 0, 'not_ok_record': 0, 'unexplained': 1})
        f3 = rep['class_F3']
        self.assertEqual((f3['differences'], f3['by_cause'], f3['agree_within_bounds'], f3['plans']),
                         (1, {'F3': 1}, 3, {'plans': 1, 'run_dirs': 1}))
        self.assertEqual(f3['runs_per_arm'], {'fixed_deep': {'runs': 1, 'runs_with_analysis_difference': 0}})
        un = rep['unexplained']
        self.assertEqual((un['differences'], un['by_cause'], un['by_column']),
                         (1, {'unclassified': 1}, {'runs.csv|gpu_usage_recomputed|record': 1}))
        self.assertEqual((rep['outcome'], rep['release']), ('verification failure', 'verification failure'))
        self.assertEqual(set(rep['inputs_sha256']), set(R.INPUTS) | {'SHA256SUMS'})

    def test_class_f1_only_and_abs_from_values(self):
        diffs = [r for r in MIXED if r['cause'] == 'F1']
        diffs[0] = dict(diffs[0], abs_diff='')
        write(self.d, diffs)
        code, out, _ = run([self.d])
        rep = json.loads(out)
        self.assertEqual((code, rep['outcome'], rep['release']),
                         (0, 'pre-specified classes only', 'pre-specified classes only'))
        self.assertEqual(columns(rep)[('runs.csv', '', 'realized_log_censored_plans')]['abs_diff'], 7.0)

    def test_release_only_for_status_final(self):
        diffs = [r for r in MIXED if r['cause'] == 'F1']
        for status in ('development', None):
            with self.subTest(status=status):
                write(self.d, diffs, status=status)
                code, out, _ = run([self.d])
                rep = json.loads(out)
                self.assertEqual((code, rep['status'], rep['outcome'], rep['release']),
                                 (0, status, 'pre-specified classes only', 'not final'))

    def test_agree(self):
        write(self.d, [])
        code, out, _ = run([self.d])
        rep = json.loads(out)
        self.assertEqual((code, rep['release'], rep['class_F1']['differences']), (0, 'AGREE', 0))

    def test_one_side_empty_rows_counted(self):
        """A class F1 difference with a side empty (or not a number) has no absolute difference: the column states
        the number of such rows; a column with only such rows has abs_diff null."""
        diffs = [row('per_scenario.csv', 'fast_only_k1.0_s11/1', 'r_cond', 'r_cond', '0.5', '', 'F1',
                     scope='analysis', abs_diff=''),
                 row('per_scenario.csv', 'fast_only_k1.0_s11/2', 'r_cond', 'r_cond', '', '0.25', 'F1',
                     scope='analysis', abs_diff=''),
                 row('per_scenario.csv', 'fast_only_k1.0_s11/1', 'eir', 'eir', '0.25', '0.2', 'F1', scope='analysis'),
                 row('per_scenario.csv', 'fast_only_k1.0_s11/2', 'eir', 'eir', '0.25', '', 'F1', scope='analysis',
                     abs_diff=''),
                 row('paired_differences.csv', 'c/eir/1', 'paired', 'status', 'True', 'False', 'F1',
                     scope='analysis', abs_diff='')]
        write(self.d, diffs)
        code, out, _ = run([self.d])
        rep = json.loads(out)
        cols = columns(rep)
        self.assertEqual(code, 0)
        self.assertEqual((cols[('per_scenario.csv', 'r_cond', 'r_cond')]['abs_diff'],
                          cols[('per_scenario.csv', 'r_cond', 'r_cond')]['rows'],
                          cols[('per_scenario.csv', 'r_cond', 'r_cond')]['rows_without_abs_diff']), (None, 2, 2))
        self.assertAlmostEqual(cols[('per_scenario.csv', 'eir', 'eir')]['abs_diff'], 0.05)
        self.assertEqual((cols[('per_scenario.csv', 'eir', 'eir')]['rows'],
                          cols[('per_scenario.csv', 'eir', 'eir')]['rows_without_abs_diff']), (2, 1))
        self.assertEqual(cols[('paired_differences.csv', 'eir', 'status')]['rows_without_abs_diff'], 1)
        self.assertEqual(rep['class_F1']['differences_without_abs_diff'], 4)

    def test_counts_must_match_table1_extra(self):
        write(self.d, MIXED, counts={'F1': 7, 'F3': 1, 'unclassified': 1})
        code, out, err = run([self.d])
        self.assertEqual((code, out), (2, ''))
        self.assertIn('differ from table1_extra.json', err)

    def test_difference_count_and_verdict_must_match(self):
        cases = {'count': {'comparisons': {'compared': 100, 'differences': 9,
                                           'differences_by_cause': {'F1': 8, 'F3': 1, 'unclassified': 1},
                                           'analysis_differences_by_cause': {'F1': 4}}},
                 'verdict': {'verdict': 'AGREE'}}
        for name, extra in cases.items():
            with self.subTest(case=name):
                write(self.d, MIXED, **extra)
                code, out, err = run([self.d])
                self.assertEqual((code, out), (2, ''))
                self.assertIn('differences.csv holds 10 rows', err)

    def test_missing_input(self):
        for name in ('cause_plans.csv', 'SHA256SUMS'):
            with self.subTest(missing=name):
                write(self.d, MIXED)
                os.remove(os.path.join(self.d, name))
                code, _, err = run([self.d])
                self.assertEqual(code, 2)
                self.assertIn(name, err)

    def test_inputs_must_match_sha256sums(self):
        """An input changed after SHA256SUMS (rows removed and the counts adjusted to them), or not listed: exit 2."""
        sums = os.path.join(self.d, 'SHA256SUMS')
        keep = [r for r in MIXED if r['cause'] == 'F1']
        write(self.d, MIXED)
        write(self.d, keep, sums=False)
        code, out, err = run([self.d])
        self.assertEqual((code, out), (2, ''))
        self.assertIn('differences.csv differs', err)
        self.assertIn('table1_extra.json differs', err)
        write(self.d, keep)
        with open(sums, encoding='utf-8') as fh:
            lines = [ln for ln in fh if not ln.rstrip('\n').endswith('  cause_plans.csv')]
        with open(sums, 'w', encoding='utf-8') as fh:
            fh.writelines(lines)
        code, out, err = run([self.d])
        self.assertEqual((code, out), (2, ''))
        self.assertIn('cause_plans.csv not listed', err)
        self.assertNotIn('differs', err)

    def test_out_file_and_refusals(self):
        write(self.d, MIXED)
        before = sorted(os.listdir(self.d))
        with tempfile.TemporaryDirectory(prefix='f1_class_out_', dir='/tmp') as other:
            target = os.path.join(other, 'report.json')
            code, out, _ = run([self.d, '--out', target])
            self.assertEqual((code, out), (0, ''))
            with open(target, encoding='utf-8') as fh:
                self.assertEqual(json.load(fh)['class_F1']['differences'], 8)
        bad = '/home/kang/Desktop/DAC/framelease_v4/no_such_directory_f1/report.json'
        for target in (bad, os.path.join(self.d, 'report.json'), os.path.join(self.d, 'sub', 'r.json'), self.d):
            with self.subTest(out=target):
                code, out, err = run([self.d, '--out', target])
                self.assertEqual((code, out), (2, ''))
                self.assertIn('input error: --out', err)
        self.assertFalse(os.path.exists(os.path.dirname(bad)))
        self.assertEqual(sorted(os.listdir(self.d)), before)

    def test_unmapped_job_is_reported(self):
        write(self.d, [row('runs.csv', 'job_x', 'misses', 'realized_misses', '2', '1', 'F1')])
        code, out, _ = run([self.d])
        rep = json.loads(out)
        self.assertEqual(rep['class_F1']['runs_per_arm'], {'(unmapped)': {'runs': 1,
                                                                          'runs_with_analysis_difference': 0}})

    def test_class_f3_holds_f3_and_f1_f3(self):
        diffs = [row('runs.csv', 'job_b1', 'misses', 'realized_misses', '2', '1', 'F3'),
                 row('runs.csv', 'job_b1', 'r_cond', 'realized_r_cond', '0.5', '0.25', 'F3'),
                 row('conditions.csv', 'fixed_deep_k1.0_s11/all/r_cond', 'mean', 'mean', '0.4', '0.3', 'F1+F3',
                     scope='analysis'),
                 row('runs.csv', 'job_a1', 'log_censored_plans', 'realized_log_censored_plans', '3', '5', 'F1')]
        plans = [{'run_dir': 'runs/b1', 'commit_index': '4', 'job_id': '2', 'depth': '1', 'capture_s': '10.0',
                  'cause': 'F3'}]
        write(self.d, diffs, plans=plans, within={'F3': 1, 'F1+F3': 2})
        code, out, _ = run([self.d])
        rep = json.loads(out)
        f3 = rep['class_F3']
        self.assertEqual(rep['differences_by_class'],
                         {'F1': 1, 'F3': 3, 'in_flight': 0, 'not_ok_record': 0, 'unexplained': 0})
        self.assertEqual((f3['differences'], f3['analysis_differences'], f3['by_cause'], f3['agree_within_bounds']),
                         (3, 1, {'F1+F3': 1, 'F3': 2}, 3))
        self.assertEqual(f3['runs_per_arm'], {'fixed_deep': {'runs': 1, 'runs_with_analysis_difference': 0}})
        self.assertAlmostEqual(columns(dict(class_F1=f3))[('conditions.csv', 'r_cond', 'mean')]['abs_diff'], 0.1)
        self.assertEqual((code, rep['outcome']), (0, 'pre-specified classes only'))


def in_flight_runs(**over):
    """runs_recomputed.csv rows: job_a1 ended with a job in flight (3 in-flight GPU boundaries, 2 commits of a job
    without a jobs.jsonl row); job_b1 did not."""
    a1 = dict(RUNS[0], gpu_inflight_boundaries='3', gpu_busy_s_bounds='[10.0, 10.2]', gpu_usage_bounds='[0.9, 0.92]',
              plans_by_status=json.dumps({'clear': 5, 'no_plan_logged': 2}), checks='{}')
    a1.update(over)
    b1 = dict(RUNS[2], gpu_inflight_boundaries='0', gpu_busy_s_bounds='[8.0, 8.0]', gpu_usage_bounds='[0.8, 0.8]',
              plans_by_status=json.dumps({'clear': 5}), checks='{}')
    return [a1, dict(RUNS[1]), b1]


IN_FLIGHT_ROWS = [row('runs.csv', 'job_a1', 'gpu_usage', 'gpu_usage_recomputed', '0.91', '0.85', ''),
                  row('runs.csv', 'job_a1', 'gpu_busy_s', 'gpu_busy_recomputed_s', '10.1', '9.4', ''),
                  row('runs.csv', 'job_a1', 'commits', 'commits', '40', '38', '')]


class InFlightClass(unittest.TestCase):
    """Class in_flight: the runs.csv cross-check columns of a run that ended with a job in flight (module docstring of
    f1_class_report.py); every condition that fails leaves the row unexplained."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='f1_class_inflight_', dir='/tmp')
        self.d = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def classes(self, diffs, runs=None):
        write(self.d, diffs, runs=runs or in_flight_runs())
        code, out, _ = run([self.d])
        self.assertEqual(code, 0)
        return json.loads(out)

    def test_in_flight_rows(self):
        rep = self.classes(IN_FLIGHT_ROWS)
        fl = rep['class_in_flight']
        self.assertEqual(rep['differences_by_class'],
                         {'F1': 0, 'F3': 0, 'in_flight': 3, 'not_ok_record': 0, 'unexplained': 0})
        self.assertEqual((fl['runs'], fl['runs_per_arm'], fl['analysis_differences']),
                         (1, {'fast_only': {'runs': 1, 'runs_with_analysis_difference': 0}}, 0))
        self.assertEqual((fl['runs_ending_with_job_in_flight'], fl['runs_recomputed']), (1, 3))
        cols = columns(dict(class_F1=fl))
        self.assertEqual(cols[('runs.csv', '', 'commits')]['abs_diff'], 2.0)
        self.assertAlmostEqual(cols[('runs.csv', '', 'gpu_busy_recomputed_s')]['abs_diff'], 0.7)
        self.assertEqual(rep['outcome'], 'pre-specified classes only')

    def test_each_condition_is_required(self):
        a1 = IN_FLIGHT_ROWS
        cases = {
            'no job in flight': ([dict(r, key='job_b1') for r in a1[:2]], None, 2),
            'registered within the lower bound': ([dict(a1[0], theirs='0.905', abs_diff='0.005')], None, 1),
            'registered above the recomputed value': ([dict(a1[0], ours='0.85', theirs='0.91')], None, 1),
            'analysis-read gpu_usage differs': (
                a1[:2] + [row('runs.csv', 'job_a1', 'gpu_usage', 'gpu_usage', '0.91', '0.85', '', scope='analysis')],
                None, 3),
            'runtime busy time differs': (
                a1[:1] + [row('runs.csv', 'job_a1', 'gpu_busy_s', 'gpu_busy_in_span_s', '10.1', '9.4', '')], None, 2),
            'scope analysis': ([dict(a1[0], scope='analysis')], None, 1),
            'a cause': ([dict(a1[2], cause='F1')], None, 0),
            'commits differ by more than the in-flight commits': ([dict(a1[2], theirs='37', abs_diff='3')], None, 1),
            'commits of a logged job without its step': (
                a1[2:], in_flight_runs(checks=json.dumps({'commit_without_job_step': 1})), 1),
            'one side empty': ([dict(a1[1], theirs='', abs_diff='')], None, 1),
            'another column': ([row('runs.csv', 'job_a1', 'ticks', 'ticks', '40', '38', '')], None, 1),
            'unmapped job': ([dict(a1[2], key='job_x')], None, 1),
        }
        for name, (diffs, runs, unexplained) in cases.items():
            with self.subTest(case=name):
                rep = self.classes(diffs, runs)
                self.assertEqual(rep['differences_by_class']['unexplained'], unexplained, rep['differences_by_class'])
                self.assertEqual(rep['outcome'], 'verification failure' if unexplained else
                                 'pre-specified classes only')


def empty_row(target, key, field, their, ours, scope='record'):
    """A difference whose registered side is empty (no absolute difference)."""
    return row(target, key, field, their, ours, '', '', scope=scope, abs_diff='')


NOT_OK_ROWS = [empty_row('runs.csv', 'job_a1', 'dmr', 'dmr', '0.25'),
               empty_row('runs.csv', 'job_a1', 'ticks', 'ticks', '3256'),
               empty_row('runner result', 'job_a1', 'action_age_p50_s', 'result.action_age_p50_s', '0.8')]


class NotOkRecordClass(unittest.TestCase):
    """Class not_ok_record: rows with an empty registered side of a job whose final runner outcome is not 'ok' and
    whose runs.csv row has analysis_use false; the runner records and runs.csv come from table1_extra.json 'inputs'."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='f1_class_notok_', dir='/tmp')
        self.d = os.path.join(self.tmp.name, 'out')
        os.makedirs(self.d)
        self.q = os.path.join(self.tmp.name, 'queue', 'status.jsonl')
        self.runs = os.path.join(self.tmp.name, 'agg', 'runs.csv')
        os.makedirs(os.path.dirname(self.q))
        os.makedirs(os.path.dirname(self.runs))

    def tearDown(self):
        self.tmp.cleanup()

    def classes(self, diffs, records, use='False', inputs=None):
        with open(self.q, 'w', encoding='utf-8') as fh:
            fh.writelines(json.dumps(r) + '\n' for r in records)
        with open(self.runs, 'w', newline='', encoding='utf-8') as fh:
            w = csv.DictWriter(fh, ('job', 'outcome', 'analysis_use', 'dmr', 'ticks'))
            w.writeheader()
            w.writerow({'job': 'job_a1', 'outcome': 'sim_failure', 'analysis_use': use, 'dmr': '', 'ticks': ''})
        write(self.d, diffs, inputs=inputs if inputs is not None else {self.q: sha(self.q), self.runs: sha(self.runs)})
        return run([self.d])

    def test_not_ok_rows(self):
        recs = [{'event': 'end', 'id': 'job_a1', 'final': False, 'outcome': 'ok'},
                {'event': 'end', 'id': 'job_a1', 'final': True, 'outcome': 'timeout'},
                {'event': 'end', 'id': 'job_a1', 'final': False, 'outcome': 'ok'}]
        code, out, _ = self.classes(NOT_OK_ROWS, recs)
        rep = json.loads(out)
        no = rep['class_not_ok_record']
        self.assertEqual(code, 0)
        self.assertEqual(rep['differences_by_class'],
                         {'F1': 0, 'F3': 0, 'in_flight': 0, 'not_ok_record': 3, 'unexplained': 0})
        self.assertEqual((no['jobs'], no['analysis_differences'], no['differences_without_abs_diff']),
                         ({'job_a1': 'timeout'}, 0, 3))
        self.assertEqual(no['runs_per_arm'], {'fast_only': {'runs': 1, 'runs_with_analysis_difference': 0}})
        self.assertEqual({(x['column'], x['abs_diff'], x['rows_without_abs_diff']) for x in no['largest_abs_diff']},
                         {('dmr', None, 1), ('ticks', None, 1), ('result.action_age_p50_s', None, 1)})
        self.assertEqual(no['sources'], {'runner_records': [self.q], 'runs_csv': self.runs})
        self.assertEqual(rep['outcome'], 'pre-specified classes only')

    def test_each_condition_is_required(self):
        timeout = [{'event': 'end', 'id': 'job_a1', 'final': True, 'outcome': 'timeout'}]
        cases = {
            'final outcome ok': (NOT_OK_ROWS, [{'event': 'end', 'id': 'job_a1', 'final': True, 'outcome': 'ok'}],
                                 'False', 3),
            'analysis_use true': (NOT_OK_ROWS, timeout, 'True', 3),
            'registered value not empty': ([row('runs.csv', 'job_a1', 'dmr', 'dmr', '0.25', '0.2', '')], timeout,
                                           'False', 1),
            'scope analysis': ([empty_row('runs.csv', 'job_a1', 'dmr', 'dmr', '0.25', scope='analysis')], timeout,
                               'False', 1),
            'job without a runner record': ([empty_row('runs.csv', 'job_a2', 'dmr', 'dmr', '0.25')], timeout,
                                            'False', 1),
            'another target': ([empty_row('summary.json', 'runs/a1', 'dmr', 'dmr', '0.25')], timeout, 'False', 1),
            'a cause': ([dict(NOT_OK_ROWS[0], cause='F1')], timeout, 'False', 0),
        }
        for name, (diffs, recs, use, unexplained) in cases.items():
            with self.subTest(case=name):
                code, out, _ = self.classes(diffs, recs, use)
                rep = json.loads(out)
                self.assertEqual(code, 0)
                self.assertEqual(rep['differences_by_class']['unexplained'], unexplained, rep['differences_by_class'])

    def test_recorded_inputs_are_checked(self):
        timeout = [{'event': 'end', 'id': 'job_a1', 'final': True, 'outcome': 'timeout'}]
        gone = os.path.join(self.tmp.name, 'gone', 'status.jsonl')
        for name, inputs in (('sha256 differs', {self.q: 'f' * 64}), ('missing', {gone: 'f' * 64})):
            with self.subTest(case=name):
                code, out, err = self.classes(NOT_OK_ROWS, timeout, inputs=inputs)
                self.assertEqual((code, out), (2, ''))
                self.assertIn('runner records or runs.csv named in table1_extra.json inputs', err)
        code, out, _ = self.classes(NOT_OK_ROWS, timeout, inputs={})
        self.assertEqual((code, json.loads(out)['differences_by_class']['unexplained']), (0, 3))


class OnVerifierOutput(unittest.TestCase):
    """The class report on the outputs of verify_table1_extra.py for a synthetic case: route 990101 of fl_heuristic
    has a conflict plan whose first conflicting sample lies on the last actor-log row (F1); the registered values are
    those under F1. Its R_cond is a number here and empty under F1 (one side empty)."""
    OFF = 7e-7

    @classmethod
    def setUpClass(cls):
        cls.vt = _load('vt_f1_class_test', os.path.join(ROOT, 'framelease_v4/analysis/verify_table1_extra.py'))
        cls.fx = _load('vt_fixtures_f1_class_test',
                       os.path.join(ROOT, 'framelease_v4/analysis/tests/test_verify_table1_extra.py'))
        cls.tmp = tempfile.mkdtemp(prefix='f1_class_vt_', dir='/tmp')
        cls.code, cls.out = cls.build(cls.tmp)
        with open(os.path.join(cls.out, 'differences.csv'), newline='', encoding='utf-8') as fh:
            cls.diffs = list(csv.DictReader(fh))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def build(cls, tmp):
        vt, fx = cls.vt, cls.fx
        conds = {'fl_heuristic': 'fl_heuristic_k1.0_s11', 'fl_full': 'fl_full_k1.0_s11'}
        routes = ('990101', '990102')
        runs, cells, vals = [], [], {}
        for arm, cond in conds.items():
            for route in routes:
                job = 'job_%s_%s' % (arm, route)
                n_ticks = 31 if (arm, route) == ('fl_heuristic', '990101') else 61
                d = fx.one_commit_run(tmp, job, capture=0.05 + cls.OFF, n_ticks=n_ticks, route=route, arm=arm)
                r = vt.recompute_run(d)
                reg = r['registered_views']['F1']
                vals[(cond, route)] = reg
                rr = fx.runs_row(job, d, dict(r, validity_available=True), route=route, arm=arm,
                                 last_tick_s=r['last_tick_s'])
                rr.update({'realized_conflict_plans': reg['conflict_plans'], 'realized_misses': reg['misses'],
                           'realized_v0_plans': reg['v0_plans'],
                           'realized_log_censored_plans': reg['log_censored_plans'],
                           'realized_invalid_ticks': reg['eir_invalid_ticks'],
                           'realized_invalid_tick_ratio': reg['eir'],
                           'realized_r_cond': '' if reg['r_cond'] is None else reg['r_cond'],
                           'realized_r_cond_excl_v0': '' if reg['r_cond_excl_v0'] is None else reg['r_cond_excl_v0']})
                runs.append(rr)
                cells.append({'condition': cond, 'route_id': route, 'status': 'used', 'jobs': json.dumps([job]),
                              'arm': arm, 'kappa': '1.0', 'seed': '11'})
        agg, ana = os.path.join(tmp, 'agg'), os.path.join(tmp, 'analysis')
        os.makedirs(agg)
        os.makedirs(ana)
        fx.write_csv(os.path.join(agg, 'runs.csv'), runs)
        fx.write_csv(os.path.join(ana, 'cells.csv'), cells)
        fx.write_csv(os.path.join(ana, 'per_scenario.csv'), [
            {'condition': cond, 'route_id': route, 'status': 'used', 'job': 'job_%s_%s' % (arm, route),
             'eir': vals[(cond, route)]['eir'],
             'r_cond': '' if vals[(cond, route)]['r_cond'] is None else vals[(cond, route)]['r_cond']}
            for arm, cond in conds.items() for route in routes])
        a, b = conds['fl_heuristic'], conds['fl_full']
        contrast = 'fl_heuristic_minus_fl_full_k1.0_s11_all'
        ea = [vals[(a, x)]['eir'] for x in routes]
        eb = [vals[(b, x)]['eir'] for x in routes]
        dif = [x - y for x, y in zip(ea, eb)]
        st = vt._stats(dif)
        means = {'n': 2, 'mean_a': sum(ea) / 2, 'mean_b': sum(eb) / 2, 'mean': st['mean']}
        fx.write_csv(os.path.join(ana, 'secondary.csv'), [dict(
            means, contrast=contrast, metric='eir', a=a, b=b, subset='all', median=st['median'], min=st['min'],
            max=st['max'])])
        fx.write_csv(os.path.join(ana, 'paired_differences.csv'), [
            {'table': 'secondary', 'contrast': contrast, 'metric': 'eir', 'route_id': x, 'status': 'paired',
             'value_a': va, 'value_b': vb, 'difference': va - vb} for x, va, vb in zip(routes, ea, eb)])
        pos = sum(1 for x in dif if x > vt.SIGN_ZERO)
        neg = sum(1 for x in dif if x < -vt.SIGN_ZERO)
        fx.write_csv(os.path.join(ana, 'per_ability.csv'), [dict(
            means, contrast=contrast, metric='eir', ability='Merging', a=a, b=b, routes='|'.join(routes),
            n_positive=pos, n_negative=neg, n_zero=2 - pos - neg)])
        out = os.path.join(tmp, 'out')
        return vt.main(['--agg', agg, '--analysis', ana, '--out', out]), out

    def test_counts_equal_the_verifier_output(self):
        self.assertEqual(self.code, self.vt.EXIT_DIFFER)
        rep = R.report(self.out)
        f1 = [d for d in self.diffs if d['cause'] == 'F1']
        self.assertTrue(f1)
        self.assertEqual(rep['differences'], len(self.diffs))
        self.assertEqual(rep['class_F1']['differences'], len(f1))
        self.assertEqual(rep['class_F1']['analysis_differences'], sum(d['scope'] == 'analysis' for d in f1))
        self.assertEqual(rep['class_F1']['runs_per_arm'],
                         {'fl_heuristic': {'runs': 1, 'runs_with_analysis_difference': 1}})
        self.assertEqual((rep['status'], rep['release']), ('development', 'not final'))
        self.assertEqual(rep['sha256sums'], 'OK: the four inputs equal SHA256SUMS')

    def test_analysis_columns_have_their_metric(self):
        cols = columns(R.report(self.out))
        for col in (('per_scenario.csv', 'eir', 'eir'), ('per_scenario.csv', 'r_cond', 'r_cond'),
                    ('secondary.csv', 'eir', 'mean'), ('secondary.csv', 'eir', 'mean_a'),
                    ('paired_differences.csv', 'eir', 'difference'), ('paired_differences.csv', 'eir', 'value_a'),
                    ('per_ability.csv', 'eir', 'mean'), ('per_ability.csv', 'eir', 'n_negative')):
            self.assertIn(col, cols)
        self.assertFalse([c for c in cols if c[0] not in R.COLUMN_TARGETS and not c[1]], cols)

    def test_one_side_empty_column(self):
        rows = [d for d in self.diffs if d['target'] == 'per_scenario.csv' and d['field'] == 'r_cond']
        self.assertEqual([(d['cause'], d['theirs'], d['abs_diff']) for d in rows], [('F1', '', '')])
        col = columns(R.report(self.out))[('per_scenario.csv', 'r_cond', 'r_cond')]
        self.assertEqual((col['abs_diff'], col['rows'], col['rows_without_abs_diff']), (None, 1, 1))

    def test_altered_copy_is_refused(self):
        d = tempfile.mkdtemp(prefix='f1_class_vt_copy_', dir='/tmp')
        try:
            for n in os.listdir(self.out):
                shutil.copy(os.path.join(self.out, n), d)
            keep = [r for r in self.diffs if r['cause'] == 'F1']
            with open(os.path.join(d, 'differences.csv'), 'w', newline='', encoding='utf-8') as fh:
                w = csv.DictWriter(fh, list(self.diffs[0]))
                w.writeheader()
                w.writerows(keep)
            code, out, err = run([d])
            self.assertEqual((code, out), (2, ''))
            self.assertIn('differences.csv differs', err)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class OnVerifierOutputInFlight(unittest.TestCase):
    """The class report on the outputs of verify_table1_extra.py for the fixture run of its tests that ends with job 3
    in flight (prefix [0.70, 0.90], step quanta shown to 1.10), with one commit of job 3 added. runs.csv carries the
    aggregator's values (metrics_v4.py): gpu_usage from the runtime (the recomputed point value here), the cross-check
    GPU columns without the in-flight steps (0.54 - 0.15 = 0.39 s in the span [0.05, 1.05]) and commits from jobs.jsonl
    (without the commit of job 3)."""

    @classmethod
    def setUpClass(cls):
        cls.vt = _load('vt_f1_class_inflight', os.path.join(ROOT, 'framelease_v4/analysis/verify_table1_extra.py'))
        cls.fx = _load('vt_fixtures_f1_class_inflight',
                       os.path.join(ROOT, 'framelease_v4/analysis/tests/test_verify_table1_extra.py'))
        cls.tmp = tempfile.mkdtemp(prefix='f1_class_vt_inflight_', dir='/tmp')
        fx = cls.fx
        commits = fx.COMMITS + [{'job_id': 3, 'depth': 2, 'commit_s': 0.97, 'capture_s': 0.70, 'deadline_s': 1.40}]
        cls.run_dir = fx.make_run(cls.tmp, 'run', commits=commits)
        cls.r = cls.vt.recompute_run(cls.run_dir)
        exp = dict(cls.r)
        with open(os.path.join(cls.run_dir, 'raw', 'agent', 'framelease', 'summary.json'), 'w') as fh:
            json.dump(fx.summary_from(exp), fh)
        busy = fx.GPU_UPPER - 0.15
        cls.agg_values = {'gpu_busy_recomputed_s': busy, 'gpu_usage_recomputed': busy / exp['sim_span_s'],
                          'commits': exp['commits'] - 1}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def verify(self, name, **extra):
        agg = os.path.join(self.tmp, 'agg_' + name)
        os.makedirs(agg)
        self.fx.write_csv(os.path.join(agg, 'runs.csv'),
                          [self.fx.runs_row('job1', self.run_dir, self.r, **dict(self.agg_values, **extra))])
        out = os.path.join(self.tmp, 'out_' + name)
        return self.vt.main(['--agg', agg, '--out', out]), out

    def test_fixture(self):
        self.assertEqual((self.r['commits'], self.r['gpu_inflight_boundaries']), (3, 3))
        self.assertEqual(self.r['plans_by_status'].get('no_plan_logged'), 1)
        self.assertLess(self.agg_values['gpu_busy_recomputed_s'], self.r['gpu_busy_s_bounds'][0])

    def test_in_flight_class_only(self):
        code, out = self.verify('a')
        self.assertEqual(code, self.vt.EXIT_DIFFER)
        rep = R.report(out)
        cols = columns(dict(class_F1=rep['class_in_flight']))
        self.assertEqual(rep['differences_by_class'],
                         {'F1': 0, 'F3': 0, 'in_flight': 3, 'not_ok_record': 0, 'unexplained': 0})
        self.assertEqual(set(cols), {('runs.csv', '', 'gpu_usage_recomputed'),
                                     ('runs.csv', '', 'gpu_busy_recomputed_s'), ('runs.csv', '', 'commits')})
        self.assertAlmostEqual(cols[('runs.csv', '', 'gpu_busy_recomputed_s')]['abs_diff'], self.fx.GPU_POINT - 0.39)
        self.assertEqual(rep['class_in_flight']['runs_per_arm'],
                         {'fl_heuristic': {'runs': 1, 'runs_with_analysis_difference': 0}})
        self.assertEqual((rep['outcome'], rep['release']), ('pre-specified classes only', 'not final'))

    def test_analysis_value_affected_is_a_failure(self):
        """runs.csv gpu_usage equal to the cross-check value (metrics_v4.py falls back to it without the runtime's
        gpu_busy_ratio): the value the analysis reads differs, so neither it nor the GPU cross-check columns of the run
        belong to class in_flight; commits still does."""
        code, out = self.verify('b', gpu_usage=self.agg_values['gpu_usage_recomputed'])
        rep = R.report(out)
        self.assertEqual(rep['differences_by_class'],
                         {'F1': 0, 'F3': 0, 'in_flight': 1, 'not_ok_record': 0, 'unexplained': 3})
        self.assertEqual(rep['unexplained']['analysis_differences'], 1)
        self.assertIn('runs.csv|gpu_usage|analysis', rep['unexplained']['by_column'])
        self.assertEqual(rep['outcome'], 'verification failure')


class OnVerifierOutputNotOk(unittest.TestCase):
    """The class report on the outputs of verify_table1_extra.py for a job whose final runner record has outcome
    'timeout' (the runner reports no result values) and whose runs.csv row carries no metric (aggregate_v4.py job_row:
    outcome 'sim_failure', analysis_use False, selected_run set, run_dir empty), as for the P1 timed-out run; the run
    directory is the fixture run of the verifier's tests without summary.json."""

    @classmethod
    def setUpClass(cls):
        cls.vt = _load('vt_f1_class_notok', os.path.join(ROOT, 'framelease_v4/analysis/verify_table1_extra.py'))
        cls.fx = _load('vt_fixtures_f1_class_notok',
                       os.path.join(ROOT, 'framelease_v4/analysis/tests/test_verify_table1_extra.py'))
        cls.tmp = tempfile.mkdtemp(prefix='f1_class_vt_notok_', dir='/tmp')
        cls.run_dir = cls.fx.make_run(cls.tmp, 'run', drop=('summary.json',))
        cls.r = cls.vt.recompute_run(cls.run_dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def verify(self, name, outcome='timeout', use='False', values=None):
        fx = self.fx
        q = os.path.join(self.tmp, 'queue_' + name)
        agg = os.path.join(self.tmp, 'agg_' + name)
        os.makedirs(q)
        os.makedirs(agg)
        fx.write_jsonl(os.path.join(q, 'status.jsonl'), [
            {'event': 'end', 'id': 'job1', 'final': True, 'run_dir': self.run_dir, 'outcome': outcome,
             'job': {'route_id': '990001'}, 'result': {'action_age_p50_s': None, 'fallback_tick_ratio': None}}])
        full = fx.runs_row('job1', self.run_dir, self.r)
        ids = ('job', 'route_id', 'protocol_arm', 'candidate', 'kappa', 'seed', 'phase', 'block', 'test_route')
        row = {k: (v if k in ids else None) for k, v in full.items()}
        row.update(run_dir=None, selected_run=self.run_dir, outcome='sim_failure', analysis_use=use,
                   missing_reason='sim_failure', **(values or {}))
        fx.write_csv(os.path.join(agg, 'runs.csv'), [row])
        out = os.path.join(self.tmp, 'out_' + name)
        return self.vt.main(['--queue', q, '--agg', agg, '--out', out]), out

    def test_not_ok_record_class_only(self):
        code, out = self.verify('a')
        self.assertEqual(code, self.vt.EXIT_DIFFER)
        rep = R.report(out)
        no = rep['class_not_ok_record']
        self.assertGreater(no['differences'], 30)
        self.assertEqual(rep['differences_by_class'], {'F1': 0, 'F3': 0, 'in_flight': 0,
                                                       'not_ok_record': no['differences'], 'unexplained': 0})
        self.assertEqual((no['jobs'], no['analysis_differences']), ({'job1': 'timeout'}, 0))
        self.assertEqual(no['differences_without_abs_diff'], no['differences'])
        self.assertIn(('runner result', 'result.action_age_p50_s'),
                      {(x['target'], x['column']) for x in no['largest_abs_diff']})
        self.assertEqual(no['runs_per_arm'], {'fl_heuristic': {'runs': 1, 'runs_with_analysis_difference': 0}})
        self.assertEqual(rep['outcome'], 'pre-specified classes only')

    def test_conditions_on_verifier_output(self):
        """Final outcome 'ok', or a non-empty registered value in the run: those rows stay unexplained."""
        code, out = self.verify('ok', outcome='ok')
        rep = R.report(out)
        self.assertEqual((rep['differences_by_class']['not_ok_record'], rep['outcome']), (0, 'verification failure'))
        code, out = self.verify('value', values={'ticks': 999})
        rep = R.report(out)
        self.assertEqual(rep['differences_by_class']['unexplained'], 1)
        self.assertEqual(rep['unexplained']['by_column'], {'runs.csv|ticks|record': 1})
        self.assertEqual(rep['outcome'], 'verification failure')


if __name__ == '__main__':
    unittest.main()
