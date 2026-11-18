"""Round-4 review of A11: adversarial cases for class undefined_metric_pairing and N1 of the class report
f1/f1_class_report.py of fix pass 4 (ac82d65a). Synthetic verification outputs, and the outputs that
framelease_v4/analysis/verify_table1_extra.py (f77b2dcf) writes for fixture runs of its own tests with synthetic
analysis outputs; /tmp only.

Tests named *_holds: the class report does not absorb the case. Tests named *_gap: a case it absorbs although the rule
as written does not cover it (asserting the current behaviour).

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      outputs/framelease_v4/build/AMEND2/a10r7b/f1/review/r4_test_pairing.py
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


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = _load('r4_f1_class_report', ROOT + '/outputs/framelease_v4/build/AMEND2/a10r7b/f1/f1_class_report.py')
DIFF_FIELDS = ('target', 'key', 'field', 'their_field', 'ours', 'theirs', 'abs_diff', 'tolerance', 'status', 'cause',
               'below_grid', 'scope', 'value_source', 'note')
RUN_FIELDS = ('jobs', 'run_dir', 'route_id', 'arm', 'gpu_inflight_boundaries', 'gpu_busy_s_bounds', 'gpu_usage_bounds',
              'plans_by_status', 'checks', 'p_both')
PAIR_FIELDS = ('table', 'contrast', 'metric', 'route_id', 'status', 'value_a', 'value_b', 'difference')
C_FD = 'fl_full_minus_fixed_deep_k1.0_s11_all'
C_FH = 'fl_full_minus_fl_heuristic_k1.0_s11_all'


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = R.main(argv)
    return code, out.getvalue(), err.getvalue()


def write_csv(path, rows, fields):
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fields)
        w.writeheader()
        w.writerows(rows)


def pair_diff(contrast, route, status, metric='p_both', **over):
    r = {'target': 'paired_differences.csv', 'key': 'secondary:%s/%s/%s' % (contrast, metric, route),
         'field': 'paired', 'their_field': 'status', 'ours': 'True', 'theirs': 'False', 'abs_diff': '',
         'tolerance': '', 'status': 'differ', 'cause': '', 'below_grid': '', 'scope': 'analysis', 'value_source': 'raw',
         'note': 'status %r' % status}
    r.update(over)
    return r


def pair_row(contrast, route, status, metric='p_both', **over):
    r = {'table': 'secondary', 'contrast': contrast, 'metric': metric, 'route_id': route, 'status': status,
         'value_a': '', 'value_b': '', 'difference': ''}
    r.update(over)
    return r


RUNS = [{'jobs': json.dumps(['j_ff_1']), 'run_dir': 'runs/ff1', 'route_id': '1', 'arm': 'fl_full', 'p_both': '0.5'},
        {'jobs': json.dumps(['j_fd_1']), 'run_dir': 'runs/fd1', 'route_id': '1', 'arm': 'fixed_deep', 'p_both': ''},
        {'jobs': json.dumps(['j_fh_1']), 'run_dir': 'runs/fh1', 'route_id': '1', 'arm': 'fl_heuristic',
         'p_both': '0.4'},
        {'jobs': json.dumps(['j_fo_1']), 'run_dir': 'runs/fo1', 'route_id': '1', 'arm': 'fl_original', 'p_both': ''}]


class Synthetic(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='r4_f1_pair_', dir='/tmp')
        self.d = os.path.join(self.tmp, 'out')
        self.ana = os.path.join(self.tmp, 'analysis', 'paired_differences.csv')
        os.makedirs(self.d)
        os.makedirs(os.path.dirname(self.ana))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, diffs, pairs, runs=RUNS, inputs=None, extra_inputs=None):
        write_csv(self.ana, pairs, PAIR_FIELDS)
        write_csv(os.path.join(self.d, 'differences.csv'), diffs, DIFF_FIELDS)
        write_csv(os.path.join(self.d, 'runs_recomputed.csv'), runs, RUN_FIELDS)
        write_csv(os.path.join(self.d, 'cause_plans.csv'), [], ('run_dir', 'commit_index', 'job_id', 'cause'))
        by, by_a = {}, {}
        for r in diffs:
            c = r['cause'] or 'unclassified'
            by[c] = by.get(c, 0) + 1
            if r['scope'] == 'analysis':
                by_a[c] = by_a.get(c, 0) + 1
        ins = {self.ana: R.sha256(self.ana)} if inputs is None else inputs
        ins.update(extra_inputs or {})
        t1 = {'status': 'final', 'verdict': 'DIFFER' if diffs else 'AGREE', 'inputs': ins,
              'script_sha256': R.REGISTERED_VERIFIER, 'options': {'runs_csv_values': False},
              'comparisons': {'compared': 50, 'differences': len(diffs), 'differences_by_cause': by,
                              'analysis_differences_by_cause': by_a, 'agree_within_bounds_by_cause': {}}}
        json.dump(t1, open(os.path.join(self.d, 'table1_extra.json'), 'w', encoding='utf-8'))
        with open(os.path.join(self.d, 'SHA256SUMS'), 'w', encoding='utf-8') as fh:
            for name in sorted(R.INPUTS):
                fh.write('%s  %s\n' % (R.sha256(os.path.join(self.d, name)), name))

    def classes(self, diffs, pairs, **kw):
        self.write(diffs, pairs, **kw)
        code, out, err = run([self.d])
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def test_genuine_rows_in_the_class(self):
        for status in ('p_both missing: fixed_deep_k1.0_s11',
                       'p_both missing: fixed_deep_k1.0_s11, fl_original_k1.0_s11'):
            with self.subTest(status=status):
                rep = self.classes([pair_diff(C_FD, '1', status)], [pair_row(C_FD, '1', status)])
                self.assertEqual(rep['differences_by_class']['undefined_metric_pairing'], 1)
                self.assertEqual(rep['release'], 'pre-specified classes only')

    def test_counter_examples_holds(self):
        st = 'p_both missing: fixed_deep_k1.0_s11'
        runs_fd_value = [dict(r, p_both='0.3') if r['arm'] == 'fixed_deep' else r for r in RUNS]
        cases = {
            'numeric value_b in the analysis row': ([pair_diff(C_FD, '1', st)],
                                                    [pair_row(C_FD, '1', st, value_b='0.2')], RUNS),
            'difference 0 in the analysis row': ([pair_diff(C_FD, '1', st)], [pair_row(C_FD, '1', st, difference='0')],
                                                 RUNS),
            'a value row of the key differs': ([pair_diff(C_FD, '1', st),
                                                pair_diff(C_FD, '1', st, field='value_a', their_field='value_a',
                                                          ours='0.5', theirs='0.4', note='')],
                                               [pair_row(C_FD, '1', st)], RUNS),
            'shield arm named (fl_heuristic)': ([pair_diff(C_FH, '1', 'p_both missing: fl_heuristic_k1.0_s11')],
                                                [pair_row(C_FH, '1', 'p_both missing: fl_heuristic_k1.0_s11')], RUNS),
            'shield arm named (age_only)': ([pair_diff(C_FD, '1', 'p_both missing: age_only_k1.0_s11')],
                                            [pair_row(C_FD, '1', 'p_both missing: age_only_k1.0_s11')], RUNS),
            'shield arm with a non-shield arm': (
                [pair_diff(C_FD, '1', 'p_both missing: fl_full_k1.0_s11, fixed_deep_k1.0_s11')],
                [pair_row(C_FD, '1', 'p_both missing: fl_full_k1.0_s11, fixed_deep_k1.0_s11')], RUNS),
            'note and analysis status differ': ([pair_diff(C_FD, '1', st)],
                                                [pair_row(C_FD, '1', 'p_both missing: fast_only_k1.0_s11')], RUNS),
            'metric defined for every arm (r_cond)': (
                [pair_diff(C_FD, '1', 'realized_r_cond missing: fixed_deep_k1.0_s11', metric='r_cond')],
                [pair_row(C_FD, '1', 'realized_r_cond missing: fixed_deep_k1.0_s11', metric='r_cond')], RUNS),
            'p_both key with another column in the note': (
                [pair_diff(C_FD, '1', 'p_both_pooled missing: fixed_deep_k1.0_s11')],
                [pair_row(C_FD, '1', 'p_both_pooled missing: fixed_deep_k1.0_s11')], RUNS),
            'cell not used': ([pair_diff(C_FD, '1', 'cell not used: B fixed_deep_k1.0_s11: missing')],
                              [pair_row(C_FD, '1', 'cell not used: B fixed_deep_k1.0_s11: missing')], RUNS),
            'arm with a suffix (fixed_deep_v2)': ([pair_diff(C_FD, '1', 'p_both missing: fixed_deep_v2_k1.0_s11')],
                                                  [pair_row(C_FD, '1', 'p_both missing: fixed_deep_v2_k1.0_s11')],
                                                  RUNS),
            'recomputed fixed_deep run with P_both': ([pair_diff(C_FD, '1', st)], [pair_row(C_FD, '1', st)],
                                                      runs_fd_value),
            'no recomputed fixed_deep run': ([pair_diff(C_FD, '1', st)], [pair_row(C_FD, '1', st)],
                                             [r for r in RUNS if r['arm'] != 'fixed_deep']),
            'analysis row of another route': ([pair_diff(C_FD, '1', st)], [pair_row(C_FD, '2', st)], RUNS),
            'paired here and there reversed': ([pair_diff(C_FD, '1', st, ours='False', theirs='True')],
                                               [pair_row(C_FD, '1', st)], RUNS),
        }
        for name, (diffs, pairs, runs) in cases.items():
            with self.subTest(case=name):
                rep = self.classes(diffs, pairs, runs=runs)
                self.assertEqual(rep['differences_by_class']['undefined_metric_pairing'], 0, name)
                self.assertEqual(rep['outcome'], 'verification failure')

    def test_analysis_file_integrity_holds(self):
        st = 'p_both missing: fixed_deep_k1.0_s11'
        self.write([pair_diff(C_FD, '1', st)], [pair_row(C_FD, '1', st)])
        with open(self.ana, 'a', encoding='utf-8') as fh:
            fh.write('secondary,%s,p_both,2,paired,0.5,0.4,0.1\n' % C_FH)
        code, out, err = run([self.d])
        self.assertEqual((code, out), (2, ''), err)
        self.assertIn('paired_differences.csv', err)
        self.write([pair_diff(C_FD, '1', st)], [pair_row(C_FD, '1', st)])
        os.remove(self.ana)
        self.assertEqual(run([self.d])[0], 2)
        rep = self.classes([pair_diff(C_FD, '1', st)], [pair_row(C_FD, '1', st)], inputs={})
        self.assertEqual(rep['differences_by_class']['unexplained'], 1)

    def test_condition_outside_the_contrast_gap(self):
        """NEW counter-example: the analysis row of a contrast of two shield arms (fl_full - fl_heuristic) carries the
        status 'p_both missing: fixed_deep_k1.0_s11', naming a condition that is not an arm of the contrast. The class
        does not check that the named conditions are the contrast's own, so the row is absorbed. analyze_v4.paired
        names only the contrast's conditions, and the dropped pair changes the contrast's n, which the verifier
        compares (OnVerifierOutput below), so the outcome stays a failure on a real output."""
        st = 'p_both missing: fixed_deep_k1.0_s11'
        rep = self.classes([pair_diff(C_FH, '1', st)], [pair_row(C_FH, '1', st)])
        self.assertEqual(rep['differences_by_class']['undefined_metric_pairing'], 1)

    def test_job_in_two_recorded_queues_stops_holds(self):
        """N1: a not-ok candidate makes the report read the runner records; a job id with 'end' records in two
        recorded status.jsonl stops it, whatever the outcomes."""
        qs = []
        for name, outcome in (('q_a', 'ok'), ('q_z', 'timeout')):
            q = os.path.join(self.tmp, name, 'status.jsonl')
            os.makedirs(os.path.dirname(q))
            with open(q, 'w', encoding='utf-8') as fh:
                fh.write(json.dumps({'event': 'end', 'id': 'j_fd_1', 'final': True, 'outcome': outcome}) + '\n')
            qs.append(q)
        agg = os.path.join(self.tmp, 'agg', 'runs.csv')
        os.makedirs(os.path.dirname(agg))
        write_csv(agg, [{'job': 'j_fd_1', 'outcome': 'sim_failure', 'analysis_use': 'False'}],
                  ('job', 'outcome', 'analysis_use'))
        diff = {'target': 'runs.csv', 'key': 'j_fd_1', 'field': 'dmr', 'their_field': 'dmr', 'ours': '0.2',
                'theirs': '', 'abs_diff': '', 'tolerance': '', 'status': 'differ', 'cause': '', 'below_grid': '', 'scope': 'record',
                'value_source': 'raw', 'note': ''}
        self.write([diff], [], inputs={q: R.sha256(q) for q in qs}, extra_inputs={agg: R.sha256(agg)})
        code, out, err = run([self.d])
        self.assertEqual((code, out), (2, ''))
        self.assertIn('more than one recorded status.jsonl', err)
        self.write([diff], [], inputs={qs[1]: R.sha256(qs[1])}, extra_inputs={agg: R.sha256(agg)})
        rep = json.loads(run([self.d])[1])
        self.assertEqual(rep['differences_by_class']['not_ok_record'], 1)


class OnVerifierOutput(unittest.TestCase):
    """The verifier's own outputs for fixture runs of fl_full, fl_heuristic and fixed_deep on two routes, with synthetic
    analysis outputs: the P_both pairing of fl_full - fixed_deep as analyze_v4.paired writes it, and fl_full -
    fl_heuristic either paired (as the analysis writes it) or with one route dropped under a status that names
    fixed_deep (a defect of the analysis output)."""

    @classmethod
    def setUpClass(cls):
        cls.vt = _load('r4_vt', ROOT + '/framelease_v4/analysis/verify_table1_extra.py')
        cls.fx = _load('r4_vt_fixtures', ROOT + '/framelease_v4/analysis/tests/test_verify_table1_extra.py')
        cls.tmp = tempfile.mkdtemp(prefix='r4_f1_pair_vt_', dir='/tmp')
        cls.runs, cls.cells, cls.vals = [], [], {}
        for arm in ('fl_full', 'fl_heuristic', 'fixed_deep'):
            for route in ('990101', '990102'):
                job = 'job_%s_%s' % (arm, route)
                d = cls.fx.make_run(cls.tmp, job, arm=arm, route=route, drop=('summary.json',))
                r = cls.vt.recompute_run(d)
                with open(os.path.join(d, 'raw', 'agent', 'framelease', 'summary.json'), 'w') as fh:
                    json.dump(cls.fx.summary_from(dict(r)), fh)
                cls.vals[(arm, route)] = r['p_both']
                cls.runs.append(cls.fx.runs_row(job, d, r, route=route, arm=arm, p_both='' if r['p_both'] is None
                                                 else r['p_both']))
                cls.cells.append({'condition': '%s_k1.0_s11' % arm, 'route_id': route, 'status': 'used',
                                  'jobs': json.dumps([job]), 'arm': arm, 'kappa': '1.0', 'seed': '11'})

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def verify(self, name, drop_fh_route=None):
        agg, ana = os.path.join(self.tmp, 'agg_' + name), os.path.join(self.tmp, 'ana_' + name)
        os.makedirs(agg)
        os.makedirs(ana)
        self.fx.write_csv(os.path.join(agg, 'runs.csv'), self.runs)
        self.fx.write_csv(os.path.join(ana, 'cells.csv'), self.cells)
        sec, pairs = [], []
        for contrast, b in ((C_FD, 'fixed_deep'), (C_FH, 'fl_heuristic')):
            used = []
            for route in ('990101', '990102'):
                va, vb = self.vals[('fl_full', route)], self.vals[(b, route)]
                if vb is None:
                    pairs.append(pair_row(contrast, route, 'p_both missing: %s_k1.0_s11' % b))
                elif route == drop_fh_route:
                    pairs.append(pair_row(contrast, route, 'p_both missing: fixed_deep_k1.0_s11'))
                else:
                    pairs.append(pair_row(contrast, route, 'paired', value_a=va, value_b=vb, difference=va - vb))
                    used.append(va - vb)
            n = len(used)
            st = self.vt._stats(used) if used else {'mean': None, 'median': None, 'min': None, 'max': None}
            sec.append({'contrast': contrast, 'metric': 'p_both', 'a': 'fl_full_k1.0_s11', 'b': '%s_k1.0_s11' % b,
                        'subset': 'all', 'n': n, 'mean_a': (sum(self.vals[('fl_full', x)] for x in ('990101', '990102'))
                                                            / 2) if n == 2 else (self.vals[('fl_full', '990101')]
                                                                                 if n else None),
                        'mean_b': None if not n else (sum(self.vals[(b, x)] for x in ('990101', '990102')) / 2
                                                      if n == 2 else self.vals[(b, '990101')]),
                        'mean': st['mean'], 'median': st['median'], 'min': st['min'], 'max': st['max']})
        self.fx.write_csv(os.path.join(ana, 'secondary.csv'), sec)
        self.fx.write_csv(os.path.join(ana, 'paired_differences.csv'), pairs)
        out = os.path.join(self.tmp, 'out_' + name)
        code = self.vt.main(['--agg', agg, '--analysis', ana, '--out', out])
        self.assertEqual(code, self.vt.EXIT_DIFFER)
        with open(os.path.join(out, 'differences.csv'), newline='', encoding='utf-8') as fh:
            diffs = list(csv.DictReader(fh))
        return R.report(out), diffs

    def test_fixture(self):
        self.assertIsNone(self.vals[('fixed_deep', '990101')])
        self.assertIsNotNone(self.vals[('fl_heuristic', '990101')])

    def test_genuine_pairing_rows_are_the_class(self):
        rep, diffs = self.verify('genuine')
        pd_rows = [d for d in diffs if d['target'] == 'paired_differences.csv']
        self.assertEqual(len(pd_rows), 2)
        self.assertEqual(rep['differences_by_class']['undefined_metric_pairing'], 2)
        self.assertEqual(rep['class_undefined_metric_pairing']['by_metric_and_arm'], {'p_both|fixed_deep': 2})
        others = [d for d in diffs if d['target'] in ('paired_differences.csv', 'secondary.csv')
                  and not (d['field'] == 'paired' and C_FD in d['key'])]
        self.assertEqual(others, [])

    def test_wrongly_dropped_pair_fails_through_the_contrast_row_holds(self):
        """The pairing row of the mis-attributed drop is absorbed by the class
        (test_condition_outside_the_contrast_gap), but the contrast row's n (and means) differ from the recomputation, so the outcome is a failure."""
        rep, diffs = self.verify('dropped', drop_fh_route='990102')
        sec = [d for d in diffs if d['target'] == 'secondary.csv' and C_FH in d['key']]
        self.assertIn('n', {d['field'] for d in sec})
        self.assertEqual(rep['differences_by_class']['undefined_metric_pairing'], 3)
        self.assertIn('secondary.csv|n|analysis', rep['unexplained']['by_column'])
        self.assertEqual(rep['outcome'], 'verification failure')


if __name__ == '__main__':
    unittest.main()
