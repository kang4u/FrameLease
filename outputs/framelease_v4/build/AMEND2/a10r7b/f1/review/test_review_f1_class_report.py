"""Review of item F1A11: f1_class_report.py on outputs that verify_table1_extra.py (f77b2dcf) itself writes, built from
synthetic run directories with the item's test fixtures (the AnalysisCauses case of
build/R7B/rereview/test_rereview_r7b_round2.py). Temporary directories under /tmp only; nothing of the project is
written.

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      outputs/framelease_v4/build/AMEND2/a10r7b/f1/review/test_review_f1_class_report.py

Pins: the class report separates the analysis-level columns of class F1 by metric; it maps the run of a runs.csv
difference to its arm. Shows (the tests named *_gap pass on the current version and state its behaviour): a class F1
difference with one side empty has no absolute difference, so "the largest absolute difference" of its column is
null; the report accepts inputs that disagree with the SHA256SUMS of the verification directory; the release field
ignores the status of table1_extra.json.
"""
import csv
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = '/home/kang/Desktop/DAC'
SCRIPT = os.path.join(ROOT, 'framelease_v4/analysis/verify_table1_extra.py')
TESTS = os.path.join(ROOT, 'framelease_v4/analysis/tests/test_verify_table1_extra.py')
REPORT = os.path.join(ROOT, 'outputs/framelease_v4/build/AMEND2/a10r7b/f1/f1_class_report.py')
PINNED = {SCRIPT: 'f77b2dcf34484d2537a4c22d804912f0c155c3e3c26a576f433b9f4f73d83c27',
          REPORT: '3ef60e91b792e6d11880822d3fe303c6b64709141feec81cec79b99d3344f0aa'}


def _sha(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


VT = _load('vt_review_f1a11', SCRIPT)
T = _load('vt_fixtures_review_f1a11', TESTS)
R = _load('f1_class_report_review_f1a11', REPORT)
OFF = 7e-7


def build_output(tmp):
    """The AnalysisCauses case: route 990101 of fl_heuristic carries an F1 conflict; registered values under F1."""
    a, b = 'fl_heuristic_k1.0_s11', 'fl_full_k1.0_s11'
    contrast = 'fl_heuristic_minus_fl_full_k1.0_s11_all'
    runs, vals, cells = [], {}, []
    for arm, cond in (('fl_heuristic', a), ('fl_full', b)):
        for route in ('990101', '990102'):
            n_ticks = 31 if (arm, route) == ('fl_heuristic', '990101') else 61
            job = 'job_%s_%s' % (arm, route)
            d = T.one_commit_run(tmp, job, capture=0.05 + OFF, n_ticks=n_ticks, route=route, arm=arm)
            r = VT.recompute_run(d)
            f1 = r['registered_views']['F1']
            vals[(cond, route)] = {'eir': f1['eir'], 'r_cond': f1['r_cond']}
            row = T.runs_row(job, d, dict(r, validity_available=True), route=route, arm=arm,
                             last_tick_s=r['last_tick_s'])
            row.update({'realized_conflict_plans': f1['conflict_plans'], 'realized_misses': f1['misses'],
                        'realized_v0_plans': f1['v0_plans'], 'realized_log_censored_plans': f1['log_censored_plans'],
                        'realized_invalid_ticks': f1['eir_invalid_ticks'], 'realized_invalid_tick_ratio': f1['eir'],
                        'realized_r_cond': '' if f1['r_cond'] is None else f1['r_cond'],
                        'realized_r_cond_excl_v0': '' if f1['r_cond_excl_v0'] is None else f1['r_cond_excl_v0']})
            runs.append(row)
            cells.append({'condition': cond, 'route_id': route, 'status': 'used', 'jobs': json.dumps([job]),
                          'arm': arm, 'kappa': '1.0', 'seed': '11'})
    agg, ana = os.path.join(tmp, 'agg'), os.path.join(tmp, 'analysis')
    os.makedirs(agg)
    os.makedirs(ana)
    T.write_csv(os.path.join(agg, 'runs.csv'), runs)
    T.write_csv(os.path.join(ana, 'cells.csv'), cells)
    ea = [vals[(a, x)]['eir'] for x in ('990101', '990102')]
    eb = [vals[(b, x)]['eir'] for x in ('990101', '990102')]
    dif = [x - y for x, y in zip(ea, eb)]
    sd = VT._stats(dif)
    T.write_csv(os.path.join(ana, 'secondary.csv'), [{
        'contrast': contrast, 'metric': 'eir', 'a': a, 'b': b, 'subset': 'all', 'n': 2, 'mean_a': sum(ea) / 2,
        'mean_b': sum(eb) / 2, 'mean': sd['mean'], 'median': sd['median'], 'min': sd['min'], 'max': sd['max']}])
    T.write_csv(os.path.join(ana, 'paired_differences.csv'), [
        {'table': 'secondary', 'contrast': contrast, 'metric': 'eir', 'route_id': x, 'status': 'paired',
         'value_a': va, 'value_b': vb, 'difference': va - vb} for x, va, vb in zip(('990101', '990102'), ea, eb)])
    T.write_csv(os.path.join(ana, 'per_scenario.csv'), [
        {'condition': c, 'route_id': x, 'status': 'used', 'job': 'job_%s_%s' % (c.split('_k')[0], x),
         'eir': vals[(c, x)]['eir'], 'r_cond': vals[(c, x)]['r_cond']} for c in (a, b) for x in ('990101', '990102')])
    pos = sum(1 for x in dif if x > VT.SIGN_ZERO)
    neg = sum(1 for x in dif if x < -VT.SIGN_ZERO)
    T.write_csv(os.path.join(ana, 'per_ability.csv'), [{
        'contrast': contrast, 'metric': 'eir', 'ability': 'Merging', 'a': a, 'b': b, 'routes': '990101|990102',
        'n': 2, 'mean_a': sum(ea) / 2, 'mean_b': sum(eb) / 2, 'mean': sd['mean'], 'n_positive': pos,
        'n_negative': neg, 'n_zero': 2 - pos - neg}])
    out = os.path.join(tmp, 'out')
    code = VT.main(['--agg', agg, '--analysis', ana, '--out', out])
    return code, out


class ClassReportOnVerifierOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='review_f1a11_', dir='/tmp')
        cls.code, cls.out = build_output(cls.tmp)
        with open(os.path.join(cls.out, 'differences.csv'), newline='', encoding='utf-8') as fh:
            cls.diffs = list(csv.DictReader(fh))
        cls.rep = R.report(cls.out)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_pinned_versions(self):
        for path, want in PINNED.items():
            self.assertEqual(_sha(path), want, path)

    def test_verifier_differs_and_counts_agree(self):
        self.assertEqual(self.code, VT.EXIT_DIFFER)
        f1 = [d for d in self.diffs if d['cause'] == 'F1']
        self.assertEqual(self.rep['class_F1']['differences'], len(f1))
        self.assertEqual(self.rep['class_F1']['analysis_differences'], sum(d['scope'] == 'analysis' for d in f1))
        self.assertEqual(self.rep['differences'], len(self.diffs))

    def test_runs_per_arm_from_runs_csv(self):
        self.assertEqual(self.rep['class_F1']['runs_per_arm'],
                         {'fl_heuristic': {'runs': 1, 'runs_with_analysis_difference': 1}})
        self.assertEqual([r['jobs'] for r in self.rep['class_F1']['run_list']], [['job_fl_heuristic_990101']])

    def test_analysis_columns_separated_by_metric(self):
        cols = {(c['target'], c['metric'], c['column']) for c in self.rep['class_F1']['largest_abs_diff']}
        for col in (('per_scenario.csv', 'eir', 'eir'), ('per_scenario.csv', 'r_cond', 'r_cond'),
                    ('secondary.csv', 'eir', 'mean'), ('secondary.csv', 'eir', 'mean_a'),
                    ('paired_differences.csv', 'eir', 'difference'), ('paired_differences.csv', 'eir', 'value_a'),
                    ('per_ability.csv', 'eir', 'mean'), ('per_ability.csv', 'eir', 'n_negative')):
            self.assertIn(col, cols)
        self.assertFalse([c for c in cols if c[0] not in R.COLUMN_TARGETS and not c[1]], cols)

    def test_one_side_empty_gap(self):
        """per_scenario.csv r_cond of route 990101: a number here, empty under F1 (no conflict plan left there). The
        difference belongs to class F1, and its column has no largest absolute difference (null)."""
        rows = [d for d in self.diffs if d['target'] == 'per_scenario.csv' and d['field'] == 'r_cond']
        self.assertEqual([(d['cause'], d['theirs'], d['abs_diff']) for d in rows], [('F1', '', '')])
        col = [c for c in self.rep['class_F1']['largest_abs_diff']
               if (c['target'], c['metric'], c['column']) == ('per_scenario.csv', 'r_cond', 'r_cond')]
        self.assertEqual(len(col), 1)
        self.assertIsNone(col[0]['abs_diff'])

    def test_sha256sums_not_checked_gap(self):
        """The rows without a cause removed from differences.csv and from the counts of table1_extra.json: the
        directory's SHA256SUMS no longer matches, the report reads 'class F1 only' all the same."""
        d = tempfile.mkdtemp(prefix='review_f1a11_tamper_', dir='/tmp')
        try:
            for n in os.listdir(self.out):
                shutil.copy(os.path.join(self.out, n), d)
            keep = [r for r in self.diffs if r['cause'] == 'F1']
            with open(os.path.join(d, 'differences.csv'), 'w', newline='', encoding='utf-8') as fh:
                w = csv.DictWriter(fh, list(self.diffs[0].keys()))
                w.writeheader()
                w.writerows(keep)
            with open(os.path.join(d, 'table1_extra.json'), encoding='utf-8') as fh:
                t1 = json.load(fh)
            t1['comparisons']['differences_by_cause'] = {'F1': len(keep)}
            t1['comparisons']['analysis_differences_by_cause'] = {
                'F1': sum(r['scope'] == 'analysis' for r in keep)}
            with open(os.path.join(d, 'table1_extra.json'), 'w', encoding='utf-8') as fh:
                json.dump(t1, fh)
            with open(os.path.join(d, 'SHA256SUMS'), encoding='utf-8') as fh:
                sums = dict(reversed(ln.rstrip('\n').split('  ', 1)) for ln in fh if '  ' in ln)
            self.assertNotEqual(sums['differences.csv'], _sha(os.path.join(d, 'differences.csv')))
            self.assertEqual(R.report(d)['release'], 'class F1 only')
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_release_ignores_status_gap(self):
        """table1_extra.json of this synthetic run has status 'development'; the release is formed all the same."""
        self.assertNotEqual(self.rep['status'], 'final')
        self.assertIn(self.rep['release'], ('AGREE', 'class F1 only', 'verification failure'))


if __name__ == '__main__':
    unittest.main()
