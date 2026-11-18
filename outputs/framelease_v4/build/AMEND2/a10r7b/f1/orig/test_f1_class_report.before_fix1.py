"""Tests of f1_class_report.py on synthetic verification outputs (item F1A11; temporary directories under /tmp only).

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      outputs/framelease_v4/build/AMEND2/a10r7b/f1/test_f1_class_report.py
"""
import contextlib
import csv
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('f1_class_report', os.path.join(HERE, 'f1_class_report.py'))
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)

DIFF_FIELDS = ('target', 'key', 'field', 'their_field', 'ours', 'theirs', 'abs_diff', 'tolerance', 'status', 'cause',
               'below_grid', 'scope', 'value_source', 'note')
RUN_FIELDS = ('jobs', 'run_dir', 'route_id', 'arm')
PLAN_FIELDS = ('run_dir', 'commit_index', 'job_id', 'depth', 'capture_s', 'cause')


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


def write(d, diffs, runs=RUNS, plans=(), counts=None, status='final'):
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
                          'analysis_differences_by_cause': by_a}}
    with open(os.path.join(d, 'table1_extra.json'), 'w', encoding='utf-8') as fh:
        json.dump(t1, fh)


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = R.main(argv)
    return code, out.getvalue(), err.getvalue()


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
        write(self.d, MIXED, plans=plans)
        code, out, _ = run([self.d])
        self.assertEqual(code, 0)
        rep = json.loads(out)
        c = rep['class_F1']
        self.assertEqual(rep['status'], 'final')
        self.assertEqual(rep['differences'], 10)
        self.assertEqual(c['differences'], 8)
        self.assertEqual(c['analysis_differences'], 4)
        self.assertEqual(c['runs'], 3)
        self.assertEqual(c['runs_per_arm'], {'fast_only': {'runs': 2, 'runs_with_analysis_difference': 1},
                                             'fixed_deep': {'runs': 1, 'runs_with_analysis_difference': 0}})
        cols = {(x['target'], x['metric'], x['column']): x for x in c['largest_abs_diff']}
        self.assertEqual(cols[('runs.csv', '', 'realized_log_censored_plans')]['abs_diff'], 7.0)
        self.assertEqual(cols[('runs.csv', '', 'realized_log_censored_plans')]['key'], 'job_b1')
        self.assertEqual(cols[('runs.csv', '', 'realized_log_censored_plans')]['rows'], 3)
        self.assertAlmostEqual(cols[('conditions.csv', 'eir', 'mean')]['abs_diff'], 0.01)
        self.assertAlmostEqual(cols[('conditions.csv', 'eir', 'max')]['abs_diff'], 0.05)
        self.assertAlmostEqual(cols[('per_scenario.csv', 'eir', 'eir')]['abs_diff'], 0.05)
        self.assertAlmostEqual(cols[('arm_summary.csv', '', 'realized_invalid_tick_ratio')]['abs_diff'], 0.01)
        self.assertEqual(len(cols), 6)
        self.assertEqual(c['plans'], {'plans': 2, 'run_dirs': 2})
        self.assertEqual(rep['other_causes'], {'differences': 2, 'by_cause': {'F3': 1, 'unclassified': 1},
                                               'analysis_differences': 0})
        self.assertEqual(rep['release'], 'verification failure')

    def test_class_f1_only_and_abs_from_values(self):
        diffs = [r for r in MIXED if r['cause'] == 'F1']
        diffs[0] = dict(diffs[0], abs_diff='')
        write(self.d, diffs, status='development')
        code, out, _ = run([self.d])
        rep = json.loads(out)
        self.assertEqual((code, rep['release'], rep['status']), (0, 'class F1 only', 'development'))
        cols = {(x['target'], x['metric'], x['column']): x for x in rep['class_F1']['largest_abs_diff']}
        self.assertEqual(cols[('runs.csv', '', 'realized_log_censored_plans')]['abs_diff'], 7.0)

    def test_agree(self):
        write(self.d, [])
        code, out, _ = run([self.d])
        rep = json.loads(out)
        self.assertEqual((code, rep['release'], rep['class_F1']['differences']), (0, 'AGREE', 0))

    def test_counts_must_match_table1_extra(self):
        write(self.d, MIXED, counts={'F1': 7, 'F3': 1, 'unclassified': 1})
        code, out, err = run([self.d])
        self.assertEqual((code, out), (2, ''))
        self.assertIn('differ from table1_extra.json', err)

    def test_missing_input(self):
        write(self.d, MIXED)
        os.remove(os.path.join(self.d, 'cause_plans.csv'))
        code, _, err = run([self.d])
        self.assertEqual(code, 2)
        self.assertIn('cause_plans.csv', err)

    def test_out_file_and_refusal_under_framelease_v4(self):
        write(self.d, MIXED)
        target = os.path.join(self.d, 'report.json')
        code, out, _ = run([self.d, '--out', target])
        self.assertEqual((code, out), (0, ''))
        with open(target, encoding='utf-8') as fh:
            self.assertEqual(json.load(fh)['class_F1']['differences'], 8)
        bad = '/home/kang/Desktop/DAC/framelease_v4/no_such_directory_f1/report.json'
        code, _, err = run([self.d, '--out', bad])
        self.assertEqual(code, 2)
        self.assertFalse(os.path.exists(os.path.dirname(bad)))

    def test_unmapped_job_is_reported(self):
        write(self.d, [row('runs.csv', 'job_x', 'misses', 'realized_misses', '2', '1', 'F1')])
        code, out, _ = run([self.d])
        rep = json.loads(out)
        self.assertEqual(rep['class_F1']['runs_per_arm'], {'(unmapped)': {'runs': 1,
                                                                          'runs_with_analysis_difference': 0}})


if __name__ == '__main__':
    unittest.main()
