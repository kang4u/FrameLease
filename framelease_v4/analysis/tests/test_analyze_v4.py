"""The registered analysis (framelease_v4/analysis/analyze_v4.py; PROTOCOL Secs. 7.2-7.6, 9.1-9.13; GAP_AUDIT Sec. 3.7
row R-4). CPU only. Every run row is synthetic and lives in a temporary directory; the synthetic route ids
(910000-910043, and 920000-920043 with the registered scenario types) are outside the registered split. The
registered route split, manifest, PROTOCOL.md, its seal, the v2 module, the offline lease-ablation outputs (computed
before registration, Sec. 11.1 item 5) and a development S3 report are only read.

  cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/analysis/tests/test_analyze_v4.py

What is shown: the v2 functions are the registered ones and are called with the registered settings (one contrast
with the registered 10,000 resamples and 200,000 sign vectors; the other tests use small counts); the families,
metrics, grids and route subsets are those of Secs. 3.1, 9.2 and 9.3; contrasts use pairwise-complete routes and drop a
route only from the metrics it lacks; Holm keeps the registered family size; the labels follow the registered rule in
both directions; the H1 findings and the H2 / P_both rule; the uncorrected secondary rows; the Sec. 9.11 guard refuses
test-route input without a valid analysis-freeze record, from a bare CSV, from an aggregation of another record, when
this script is not cited, or when a row was not released, and lets released rows through a development record built
by interim_guard; the command line writes the tables, analysis.json and SHA256SUMS, logs every request and refuses
protected or occupied output directories and changed aggregations.

Known answers (Part B): a planted effect gives 'improves' with the exact p 2^-43 and no effect gives p 1 and no label;
Holm order and adjusted p by hand; the exact DP equals a brute-force enumeration at small n; the bootstrap is
deterministic with the registered seed; the noise floor, the seed-12 contrasts and the RL gain by kappa, seed and
ability (ability lists read by hand from the official map) on planted values; per-scenario rows and per-condition
means with their intervals; the registered MDE table from written-out z values; the H4 offline rule on every edge
case, its orientation, the per_clip_selected.csv fallback against an independent bootstrap and the registered offline
outputs (inconclusive); the H5 rule (supported, contradicted with every violation listed, undetermined); the
manipulation, overhead and missing-data reports; and no Part B table holds a test-route value for a training-route
input.

Review fixes (outputs/framelease_v4/build/R4/review/REVIEW.md): the Python API cannot narrow the guard (test_routes and
registered only add routes; a hand-made freeze dictionary is refused); the Sec. 6.1 pooled collisions/km with its
route-cluster interval by hand; NO_LOG runs in H5; every gap of a 'registered' run is a development reason, with the
Sec. 9.12 output location; the Sec. 7.6 panel B quantities; an aggregation directory is never written as --out.
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ['CUDA_VISIBLE_DEVICES'] = ''
sys.dont_write_bytecode = True

from framelease_v2 import analyze_closed_loop as V2  # noqa: E402
from framelease_v4.analysis import aggregate_v4 as AGG  # noqa: E402
from framelease_v4.analysis import analyze_v4 as AN  # noqa: E402
from framelease_v4.analysis import interim_guard as G  # noqa: E402

SYN = [{'index': i, 'route_id': str(910000 + i), 'scenario_type': f'Type{i % 11}', 'town': 'Town12'}
       for i in range(44)]
TABLE = AN.make_table(SYN, 'synthetic test routes')
ROUTES, E = TABLE['routes'], TABLE['subsets']['E']
FAST = AN.Settings(n_boot=200, mc_flips=2000)
BASE = {'driving_score': 40.0, 'collisions_per_km': 5.0, 'dmr': 0.10, 'success': 0.0, 'route_completion': 70.0,
        'infractions_per_km': 8.0, 'gpu_usage': 0.8, 'action_age_p50_s': 0.7, 'action_age_p95_s': 1.2,
        'deadline_miss_ratio': 0.12, 'realized_invalid_tick_ratio': 0.02, 'realized_r_cond': 0.05, 'p_both': 0.3,
        'lease_utilization': 0.6, 'premature_expiry_ratio': 0.1, 'deviation_rate': 0.2, 'bypass_rate': 0.01}
TABLE_I = ('fixed_deep', 'fast_only', 'age_only', 'event_triggered', 'fl_original', 'fl_heuristic', 'fl_full')
REGISTERED_TEST = sorted(G.registered_split()['test'])
# synthetic route ids (920000-920043) with the scenario types of the registered test routes, index for index
SYN_B2D = [{'index': e['index'], 'route_id': str(920000 + e['index']), 'scenario_type': e['scenario_type'],
            'town': e['town']} for e in json.loads((ROOT / G.PJ.ROUTE_SPLIT).read_text(encoding='utf-8'))['test']]
TABLE_B2D = AN.make_table(SYN_B2D, 'synthetic routes with the registered scenario types')
ROUTES_B, E_B, R_B = TABLE_B2D['routes'], TABLE_B2D['subsets']['E'], TABLE_B2D['subsets']['R']
# the route indices of each Bench2Drive ability for the 44 registered scenario types, read by hand from the official
# multi-label map (Bench2Drive ability_benchmark.py 'Ability'; a route counts in each of its abilities)
ABILITY_INDEX = {'Merging': (5, 6, 8, 9, 13, 15, 16, 25, 32, 35, 37, 38, 39, 40, 42, 43),
                 'Overtaking': (1, 2, 3, 4, 20, 21, 22, 28, 29),
                 'Emergency_Brake': (0, 7, 10, 11, 12, 14, 23, 26, 30, 31, 33, 36),
                 'Give_Way': (24, 27),
                 'Traffic_Signs': (6, 7, 8, 9, 10, 11, 12, 13, 14, 17, 18, 19, 25, 32, 33, 34, 41, 42, 43)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_row(arm, route, kappa=1.0, seed=11, values=None, **over):
    """One runs.csv row of a used run (BASE values, then values, then the field overrides)."""
    row = {'job': f'syn_{arm}_k{kappa}_s{seed}_r{route}', 'job_file': 'synthetic.jsonl', 'phase': 'P4',
           'block': 'ti_main', 'route_id': route, 'kappa': kappa, 'seed': seed, 'launcher_arm': arm,
           'protocol_arm': arm, 'outcome': 'ok', 'selected_run': f'runs/{arm}_{route}', 'code_check': 'PASS',
           'analysis_use': True, 'missing_reason': None, 'health_only': False, 'test_route': False,
           'guard_note': None, 'valid_record': 1, **BASE, **(values or {})}
    row.update(over)
    return row


def matrix(ds, arms=TABLE_I, kappa=1.0, seed=11, routes=ROUTES, extra=None):
    """Rows of every arm on every route: DS = ds[arm][i] (a callable of the route index or a constant); extra:
    {arm: {column: value or callable}}."""
    rows = []
    for i, rid in enumerate(routes):
        for arm in arms:
            vals = {}
            for col, v in {'driving_score': ds.get(arm, 40.0), **(extra or {}).get(arm, {})}.items():
                vals[col] = v(i) if callable(v) else v
            rows.append(run_row(arm, rid, kappa, seed, vals))
    return rows


def noisy(shift=0.0, seed=1, sd=25.0):
    """DS per route index: 40 + shift + N(0, sd), clipped to [0, 100], rounded to 0.01 (fixed generator)."""
    v = np.clip(40.0 + shift + np.random.default_rng(seed).normal(0.0, sd, 44), 0.0, 100.0).round(2)
    return lambda i: float(v[i])


def write_csv(path, rows):
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: '' if r.get(k) is None else r[k] for k in cols})
    return path


def write_agg(d, rows, freeze_sha=None, extra=None):
    """An aggregation directory as aggregate_v4.write_outputs leaves it: runs.csv, aggregate.json (schema, the runs.csv
    sha256, the guard state, plus extra: e.g. commit_audit, manipulation_checks, missing_reasons) and SHA256SUMS."""
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    write_csv(d / 'runs.csv', rows)
    guard = {'status': 'pre_freeze' if freeze_sha is None else 'frozen_development',
             'freeze': None if freeze_sha is None else {'sha256': freeze_sha}}
    doc = {'schema': AGG.SCHEMA, 'outputs': {'runs.csv': sha(d / 'runs.csv')}, 'interim_guard': guard, **(extra or {})}
    (d / 'aggregate.json').write_text(json.dumps(doc), encoding='utf-8')
    (d / 'SHA256SUMS').write_text(''.join(f'{sha(d / n)}  {n}\n' for n in ('aggregate.json', 'runs.csv')))
    return d


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def source(self, rows, name='runs.csv'):
        return AN.load_csv_source(write_csv(self.tmp / name, rows))

    def run_analysis(self, rows, **kw):
        kw.setdefault('table', TABLE)
        kw.setdefault('settings', FAST)
        return AN.analyze([self.source(rows)], **kw)

    @staticmethod
    def family(doc, name):
        return {r['b_arm'] if name != 'F3' else (r['b_arm'], r['kappa']): r
                for r in next(f for f in doc['families'] if f['name'] == name)['rows']}


# ============================================================================================ registered settings

class Registered(Base):
    def test_v2_functions_are_the_registered_ones(self):
        self.assertEqual(AN.check_v2(), AN.V2_SHA256)
        text = (ROOT / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
        self.assertIn(f'| {AN.V2_SHA256} | framelease_v2/analyze_closed_loop.py', text)       # Sec. 12.2
        for name in ('sign_flip_test', 'bootstrap_ci', 'holm', 'label_directional'):
            self.assertIs(getattr(AN, name), getattr(V2, name))
        self.assertEqual((AN.N_BOOT, AN.BOOT_SEED, AN.MC_FLIPS, AN.ALPHA, AN.ENUM_MAX_N),
                         (10_000, 20261110, 200_000, 0.05, V2.ENUM_MAX_N))
        self.assertTrue(AN.REGISTERED.registered)
        self.assertFalse(FAST.registered)
        with self.assertRaises(AN.AnalysisError):
            AN.check_v2(write_csv(self.tmp / 'other.py', [{'x': 1}]))

    def test_families_as_registered(self):
        """Secs. 9.2 and 9.3: names, metrics, contrasts (A - B), kappa, seed, subsets and family sizes."""
        want = {
            'H1': ('primary', 'driving_score', [('fl_full', b, 1.0, 'all') for b in AN.H1_OTHERS]),
            'S-coll': ('secondary', 'collisions_per_km', [('fl_full', b, 1.0, 'all') for b in AN.H1_OTHERS]),
            'S-dmr': ('secondary', 'dmr', [('fl_full', b, 1.0, 'all') for b in AN.H1_OTHERS]),
            'H2': ('secondary', 'driving_score', [('fl_full', 'fl_heuristic', 1.0, 'all')]),
            'H3': ('secondary', 'driving_score', [('fl_heuristic', 'fl_original', 1.0, 'all'),
                                                  ('fl_full', 'fl_original', 1.0, 'all')]),
            'F3': ('secondary', 'driving_score', [('fl_full', b, k, 'E') for k in (1.5, 2.0)
                                                  for b in ('fixed_deep', 'fast_only')]),
            'H4-cl': ('secondary', 'driving_score', [('fl_heuristic', 'fl_global_shield', 1.0, 'E'),
                                                     ('fl_heuristic', 'age_only', 1.0, 'E')]),
            'RL-abl': ('secondary', 'driving_score', [('fl_full', 'fl_bandit', 1.0, 'E'),
                                                      ('fl_full', 'fl_fqi_nolease', 1.0, 'E')]),
        }
        self.assertEqual([f.name for f in AN.FAMILIES], list(want))
        self.assertEqual(AN.H1_OTHERS, ('fixed_deep', 'fast_only', 'age_only', 'event_triggered'))
        for f in AN.FAMILIES:
            role, metric, contrasts = want[f.name]
            with self.subTest(family=f.name):
                self.assertEqual((f.role, f.metric), (role, metric))
                self.assertEqual([(c.a.arm, c.b.arm, c.a.kappa, c.subset) for c in f.contrasts], contrasts)
                self.assertTrue(all(c.a.kappa == c.b.kappa and c.a.seed == c.b.seed == 11 for c in f.contrasts))
        self.assertEqual(AN.METRICS['collisions_per_km'].better, 'lower')
        self.assertEqual(AN.METRICS['dmr'].better, 'lower')
        self.assertEqual(AN.METRICS['driving_score'].better, 'higher')
        self.assertEqual(AN.METRICS['dmr'].column, 'dmr')                  # Sec. 6.2: from the first commit

    def test_metric_grids(self):
        """Sec. 9.1: 0.01 for DS, RC and collisions/km; 1e-4 for fractions; 1 ms for ages."""
        grids = {k: m.grid for k, m in AN.METRICS.items()}
        for k in ('driving_score', 'route_completion', 'collisions_per_km', 'infractions_per_km'):
            self.assertEqual(grids.pop(k), 0.01, k)
        for k in ('action_age_p50_s', 'action_age_p95_s'):
            self.assertEqual(grids.pop(k), 1e-3, k)
        self.assertEqual(set(grids.values()), {1e-4}, grids)

    def test_route_table_is_sec_3_1(self):
        table = AN.route_table()
        self.assertTrue(table['registered'])
        self.assertEqual(table['subset_sizes'], {'all': 44, 'E': 22, 'C': 11, 'R': 15})
        self.assertEqual(sorted(table['routes']), REGISTERED_TEST)
        text = (ROOT / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
        for s in ('E', 'C', 'R'):
            line = next(x for x in text.splitlines() if x.startswith(f'| {s} | index %'))
            listed = [r.strip() for r in line.split('|')[4].split(',')]
            self.assertEqual(table['subsets'][s], listed, s)
        with self.assertRaises(AN.AnalysisError):              # an entry flag that contradicts the index rule
            AN.make_table([{'index': 0, 'route_id': '1', 'subsets': {'E': False}}], 'bad')

    def test_labels(self):
        self.assertEqual(AN.LABELS, {'supported': 'improves', 'contradicted': 'worse', 'inconclusive': 'inconclusive',
                                     'no data': 'no data'})
        cases = [(5.0, 0.01, 'higher', 'improves'), (-5.0, 0.01, 'higher', 'worse'), (5.0, 0.01, 'lower', 'worse'),
                 (-5.0, 0.01, 'lower', 'improves'), (5.0, 0.05, 'higher', 'inconclusive'),
                 (0.0, 0.001, 'higher', 'inconclusive'), (None, 0.01, 'lower', 'no data'),
                 (5.0, None, 'higher', 'no data')]
        for mean, p, better, want in cases:
            with self.subTest(mean=mean, p=p, better=better):
                self.assertEqual(AN.directional_label(mean, p, better), want)
        with self.assertRaises(ValueError):
            AN.directional_label(1.0, 0.01, None)


# ============================================================================================ statistics

class Statistics(Base):
    def test_rows_equal_the_v2_functions(self):
        """n = 44 (exact DP) and n = 22 (complete enumeration): the row's p, CIs and Holm equal direct calls of the v2
        functions with the given settings."""
        rows = matrix({'fl_full': noisy(10, 1), 'fixed_deep': noisy(0, 2), 'fast_only': noisy(0, 3),
                       'age_only': noisy(0, 4), 'event_triggered': noisy(0, 5)}, arms=('fl_full',) + AN.H1_OTHERS)
        rows += matrix({'fl_full': noisy(5, 6), 'fixed_deep': noisy(0, 7), 'fast_only': noisy(0, 8)},
                       arms=('fl_full', 'fixed_deep', 'fast_only'), kappa=1.5)
        doc, tables = self.run_analysis(rows)
        h1, f3 = self.family(doc, 'H1'), self.family(doc, 'F3')
        ps = []
        for b in AN.H1_OTHERS:
            d = np.array([noisy(10, 1)(i) - noisy(0, 2 + AN.H1_OTHERS.index(b))(i) for i in range(44)])
            sf = V2.sign_flip_test(d, 0.01, FAST.mc_flips, AN.MC_SEED)
            ci = V2.bootstrap_ci(d, FAST.n_boot, AN.BOOT_SEED)
            with self.subTest(contrast=b):
                r = h1[b]
                self.assertEqual((r['n'], r['n_expected'], r['p_method'], r['dp_grid']), (44, 44, 'exact_dp_rounded',
                                                                                          0.01))
                self.assertAlmostEqual(r['mean'], float(d.mean()), places=10)
                self.assertEqual(r['p_two_sided'], sf['p_two_sided'])
                self.assertEqual(r['p_mc'], sf['p_mc'])
                self.assertEqual((r['ci95'], r['ci90']), (ci['ci95'], ci['ci90']))
            ps.append(sf['p_two_sided'])
        self.assertEqual([h1[b]['p_adjusted'] for b in AN.H1_OTHERS], V2.holm(ps))
        r = f3[('fixed_deep', 1.5)]
        d = np.array([noisy(5, 6)(i) - noisy(0, 7)(i) for i in range(0, 44, 2)])
        self.assertEqual((r['n'], r['n_expected'], r['p_method']), (22, 22, 'exact_enumeration'))
        self.assertEqual(r['p_two_sided'], V2.sign_flip_test(d)['p_two_sided'])
        self.assertEqual(r['ci95'], V2.bootstrap_ci(d, FAST.n_boot, AN.BOOT_SEED)['ci95'])
        self.assertEqual(f3[('fixed_deep', 2.0)]['n'], 0)                     # no kappa-2.0 rows: no data, p None
        self.assertEqual(f3[('fixed_deep', 2.0)]['label'], 'no data')

    def test_exact_p_against_independent_counts(self):
        """The exact p at n = 44 (DP) against an independent dictionary count of the 2^44 sign sums of integer
        differences, and at n = 12 (enumeration) against itertools over the 4096 sign vectors."""
        rng = np.random.default_rng(5)
        d44 = rng.integers(-30, 31, 44).astype(float) + 3.0
        counts = {0: 1}
        for x in d44.astype(int):
            nxt = {}
            for s, c in counts.items():
                nxt[s + x] = nxt.get(s + x, 0) + c
                nxt[s - x] = nxt.get(s - x, 0) + c
            counts = nxt
        t = abs(int(d44.sum()))
        want = sum(c for s, c in counts.items() if abs(s) >= t) / 2 ** 44
        ds = {'fl_full': lambda i: 50.0 + d44[i], 'fixed_deep': 50.0}
        doc, _ = self.run_analysis(matrix(ds, arms=('fl_full', 'fixed_deep')))
        r = self.family(doc, 'H1')['fixed_deep']
        self.assertEqual(r['p_method'], 'exact_dp_rounded')
        self.assertAlmostEqual(r['p_two_sided'], want, delta=1e-15)
        d12 = rng.normal(2.0, 5.0, 12).round(2)
        rows = matrix({'fl_full': lambda i: 50.0 + d12[i], 'fixed_deep': 50.0}, arms=('fl_full', 'fixed_deep'),
                      kappa=1.5, routes=E[:12])
        doc, _ = self.run_analysis(rows)
        r = self.family(doc, 'F3')[('fixed_deep', 1.5)]
        diffs = [50.0 + d12[i] - 50.0 for i in range(12)]
        t = abs(sum(diffs))
        hits = sum(1 for s in itertools.product((1, -1), repeat=12)
                   if abs(sum(a * b for a, b in zip(s, diffs))) >= t - 1e-9 * max(1.0, sum(map(abs, diffs))))
        self.assertEqual((r['n'], r['n_expected'], r['p_method']), (12, 22, 'exact_enumeration'))
        self.assertAlmostEqual(r['p_two_sided'], hits / 4096, places=12)
        self.assertEqual(len(r['dropped']), 10)

    def test_registered_counts_once(self):
        """One contrast with the registered settings: 10,000 resamples from a fresh default_rng(20261110), the exact
        DP at n = 44 on the 0.01 grid and 200,000 Monte Carlo sign vectors."""
        rows = matrix({'fl_full': noisy(8, 11), 'fixed_deep': noisy(0, 12)}, arms=('fl_full', 'fixed_deep'))
        src = self.source(rows)
        cells = AN.build_cells(src['rows'], src['rows'], TABLE)
        row, routes = AN.evaluate(AN.H1_CONTRASTS[0], AN.METRICS['driving_score'], cells, TABLE, AN.REGISTERED)
        d = np.array([x['difference'] for x in routes])
        rng = np.random.default_rng(20261110)
        means = d[rng.integers(0, 44, size=(10_000, 44))].mean(axis=1)
        lv = 0.95                                                       # v2 bootstrap_ci's quantile levels
        self.assertEqual(row['ci95'], [float(q) for q in np.quantile(means, [(1 - lv) / 2, 1 - (1 - lv) / 2])])
        self.assertEqual((row['p_method'], row['dp_grid'], row['mc_flips'], row['mc_seed']),
                         ('exact_dp_rounded', 0.01, 200_000, 20261110))
        self.assertLess(abs(row['p_mc'] - row['p_two_sided']), 5 * row['mc_se'] + 1e-4)
        self.assertEqual([x['route_id'] for x in routes], ROUTES)

    def test_grid_per_metric(self):
        rows = matrix({'fl_full': 50.0, 'fixed_deep': 40.0}, arms=('fl_full', 'fixed_deep'),
                      extra={'fl_full': {'dmr': lambda i: 0.05 + 0.001 * i,
                                         'action_age_p50_s': lambda i: 0.6 + 0.01 * i}})
        doc, _ = self.run_analysis(rows)
        self.assertEqual(self.family(doc, 'S-dmr')['fixed_deep']['dp_grid_registered'], 1e-4)
        sec = {(r['b_arm'], r['metric']): r for r in doc['secondary'] if 'H1' in r['families']}
        self.assertEqual(sec[('fixed_deep', 'action_age_p50_s')]['dp_grid_registered'], 1e-3)
        self.assertEqual(sec[('fixed_deep', 'route_completion')]['dp_grid_registered'], 0.01)


# ============================================================================================ families and decisions

class Families(Base):
    def test_h1_labels_holm_and_findings(self):
        """fl_full = Fixed Deep + 25 and Fast Only + 25 on every route (improves), equal to Age-Only (inconclusive),
        Event-Triggered + 25 (improves): finding 1 may be stated, finding 2 is mixed."""
        base = noisy(0, 21)
        ds = {'fl_full': lambda i: base(i) + 25.0, 'fixed_deep': base, 'fast_only': base,
              'age_only': lambda i: base(i) + 25.0, 'event_triggered': base}
        doc, _ = self.run_analysis(matrix(ds, arms=('fl_full',) + AN.H1_OTHERS))
        h1 = self.family(doc, 'H1')
        self.assertEqual({b: h1[b]['label'] for b in AN.H1_OTHERS},
                         {'fixed_deep': 'improves', 'fast_only': 'improves', 'age_only': 'inconclusive',
                          'event_triggered': 'improves'})
        self.assertEqual(h1['age_only']['p_two_sided'], 1.0)
        self.assertEqual([h1[b]['p_adjusted'] for b in AN.H1_OTHERS],
                         V2.holm([h1[b]['p_two_sided'] for b in AN.H1_OTHERS]))
        self.assertTrue(all(r['family_size'] == 4 and r['correction'] == 'Holm over 4' for r in h1.values()))
        dec = doc['decisions']['H1']
        self.assertEqual(dec['finding_1']['statement'], 'may be stated')
        self.assertTrue(dec['finding_2']['statement'].startswith('mixed'))
        self.assertEqual([g['metric'] for g in dec['finding_2']['gpu_usage_descriptive']], ['gpu_usage'] * 2)
        self.assertEqual(doc['decisions']['labels']['H1']['fl_full_minus_fixed_deep_k1.0_s11_all'], 'improves')

    def test_worse_and_not_stated(self):
        base = noisy(0, 22)
        ds = {'fl_full': base, **{b: (lambda i: base(i) + 20.0) for b in AN.H1_OTHERS}}
        doc, _ = self.run_analysis(matrix(ds, arms=('fl_full',) + AN.H1_OTHERS))
        self.assertEqual({r['label'] for r in self.family(doc, 'H1').values()}, {'worse'})
        self.assertEqual(doc['decisions']['H1']['finding_1']['statement'], 'not stated: both worse')

    def test_lower_is_better(self):
        """S-coll and S-dmr: fewer collisions / a lower DMR for fl_full is 'improves', more is 'worse'."""
        extra = {'fl_full': {'collisions_per_km': 1.0, 'dmr': 0.30},
                 'fixed_deep': {'collisions_per_km': lambda i: 4.0 + 0.1 * i, 'dmr': lambda i: 0.1 + 0.001 * i},
                 'fast_only': {'collisions_per_km': 1.0, 'dmr': 0.30}}
        doc, _ = self.run_analysis(matrix({}, arms=('fl_full', 'fixed_deep', 'fast_only'), extra=extra))
        coll, dmr = self.family(doc, 'S-coll'), self.family(doc, 'S-dmr')
        self.assertLess(coll['fixed_deep']['mean'], 0)
        self.assertEqual(coll['fixed_deep']['label'], 'improves')
        self.assertEqual(dmr['fixed_deep']['label'], 'worse')
        self.assertEqual((coll['fast_only']['label'], coll['fast_only']['p_two_sided']), ('inconclusive', 1.0))
        self.assertEqual(coll['age_only']['label'], 'no data')

    def test_missing_p_counts_as_one(self):
        """Event-Triggered has no row: its p is None, label 'no data', and Holm still runs over 4."""
        base = noisy(0, 23)
        ds = {'fl_full': lambda i: base(i) + 15.0, 'fixed_deep': base, 'fast_only': noisy(0, 24),
              'age_only': noisy(5, 25)}
        doc, _ = self.run_analysis(matrix(ds, arms=('fl_full', 'fixed_deep', 'fast_only', 'age_only')))
        h1 = self.family(doc, 'H1')
        ps = [h1[b]['p_two_sided'] for b in AN.H1_OTHERS]
        self.assertIsNone(ps[3])
        self.assertEqual([h1[b]['p_adjusted'] for b in AN.H1_OTHERS], V2.holm(ps))
        self.assertEqual(h1['event_triggered']['label'], 'no data')
        self.assertEqual(h1['event_triggered']['n'], 0)
        self.assertNotEqual(V2.holm(ps[:3]), V2.holm(ps)[:3])        # the family size stays 4
        reasons = {x['reason'] for x in h1['event_triggered']['dropped']}
        self.assertEqual(reasons, {'cell not used: B event_triggered_k1.0_s11: no_row'})

    def test_pairwise_complete_and_missing_metric(self):
        """Fixed Deep crashed on 3 routes (missing), fl_full lacks collisions/km on one more: H1 drops 3 routes, S-coll
        4, and every other contrast keeps 44."""
        rows = matrix({'fl_full': noisy(10, 31), 'fixed_deep': noisy(0, 32), 'fast_only': noisy(0, 33)},
                      arms=('fl_full', 'fixed_deep', 'fast_only'))
        crashed, no_coll = set(ROUTES[:3]), ROUTES[5]
        for r in rows:
            if r['protocol_arm'] == 'fixed_deep' and r['route_id'] in crashed:
                r.update(analysis_use=False, missing_reason='agent_crashed', outcome='agent_crashed',
                         driving_score=None)
            if r['protocol_arm'] == 'fl_full' and r['route_id'] == no_coll:
                r['collisions_per_km'] = None
        doc, tables = self.run_analysis(rows)
        h1, coll = self.family(doc, 'H1'), self.family(doc, 'S-coll')
        self.assertEqual((h1['fixed_deep']['n'], h1['fixed_deep']['n_complete']), (41, 41))
        self.assertEqual((coll['fixed_deep']['n'], coll['fixed_deep']['n_complete']), (40, 41))
        self.assertEqual((h1['fast_only']['n'], coll['fast_only']['n']), (44, 43))
        drop = {x['route_id']: x['reason'] for x in coll['fixed_deep']['dropped']}
        self.assertEqual(set(drop), crashed | {no_coll})
        self.assertIn('missing (agent_crashed)', drop[ROUTES[0]])
        self.assertEqual(drop[no_coll], 'collisions_per_km missing: fl_full_k1.0_s11')
        d = [x for x in tables['paired_differences.csv'] if x['table'] == 'family_H1'
             and x['contrast'] == 'fl_full_minus_fixed_deep_k1.0_s11_all']
        self.assertEqual(len(d), 44)
        self.assertEqual(sum(1 for x in d if x['status'] == 'paired'), 41)
        cells = {(c['arm'], c['route_id']): c for c in tables['cells.csv'] if (c['kappa'], c['seed']) == (1.0, 11)}
        self.assertEqual(cells[('fixed_deep', ROUTES[0])]['status'], 'missing')
        self.assertEqual(cells[('fixed_deep', ROUTES[0])]['reasons'], ['agent_crashed'])

    def test_duplicate_and_inconsistent_cells(self):
        rows = matrix({'fl_full': 50.0, 'fixed_deep': 40.0}, arms=('fl_full', 'fixed_deep'))
        rows.append(run_row('fixed_deep', ROUTES[0], values={'driving_score': 10.0}, job='dup'))
        rows[2]['valid_record'] = 0                                    # fl_full on ROUTES[1]
        doc, tables = self.run_analysis(rows)
        cells = {(c['arm'], c['route_id']): c['status'] for c in tables['cells.csv']
                 if (c['kappa'], c['seed']) == (1.0, 11)}
        self.assertEqual(cells[('fixed_deep', ROUTES[0])], 'duplicate')
        self.assertEqual(cells[('fl_full', ROUTES[1])], 'inconsistent')
        self.assertEqual(self.family(doc, 'H1')['fixed_deep']['n'], 42)
        with self.assertRaises(AN.AnalysisError):                       # one row per job id across the inputs
            AN.analyze([self.source(rows[:3], 'a.csv'), self.source(rows[:1], 'b.csv')], table=TABLE,
                       settings=FAST)

    def test_e_families_use_e_and_their_kappa(self):
        rows = []
        for k in (1.0, 1.5, 2.0):
            rows += matrix({'fl_full': 60.0, 'fixed_deep': noisy(0, 41), 'fast_only': noisy(0, 42)},
                           arms=('fl_full', 'fixed_deep', 'fast_only'), kappa=k)
        rows += matrix({'fl_heuristic': 50.0, 'fl_global_shield': noisy(0, 43), 'age_only': 50.0,
                        'fl_bandit': noisy(0, 44), 'fl_fqi_nolease': 60.0}, arms=('fl_heuristic', 'fl_global_shield',
                                                                                     'age_only', 'fl_bandit',
                                                                                     'fl_fqi_nolease'))
        doc, tables = self.run_analysis(rows)
        for name in ('F3', 'H4-cl', 'RL-abl'):
            for r in self.family(doc, name).values():
                with self.subTest(family=name, contrast=r['contrast']):
                    self.assertEqual((r['n'], r['n_expected'], r['subset'], r['p_method']),
                                     (22, 22, 'E', 'exact_enumeration'))
                    self.assertEqual(r['family_size'], 2 if name != 'F3' else 4)
        self.assertEqual(self.family(doc, 'H4-cl')['age_only']['label'], 'inconclusive')
        self.assertEqual(self.family(doc, 'RL-abl')['fl_fqi_nolease']['p_two_sided'], 1.0)
        f3_routes = {x['route_id'] for x in tables['paired_differences.csv'] if x['table'] == 'family_F3'}
        self.assertEqual(f3_routes, set(E))
        self.assertEqual(self.family(doc, 'H1')['fixed_deep']['n'], 44)

    def test_h2_and_the_p_both_rule(self):
        base = noisy(0, 51)
        rows = matrix({'fl_full': lambda i: base(i) + 20.0, 'fl_heuristic': base}, arms=('fl_full', 'fl_heuristic'))
        doc, _ = self.run_analysis(rows)
        h2 = self.family(doc, 'H2')['fl_heuristic']
        self.assertEqual((h2['label'], h2['correction'], h2['family_size']), ('improves', 'single test', 1))
        self.assertEqual(h2['p_adjusted'], h2['p_two_sided'])
        fams, sec = doc['families'], doc['secondary']
        self.assertTrue(AN.decide(fams, sec)['H2']['rl_benefit'].startswith('undetermined'))
        self.assertEqual(AN.decide(fams, sec, {'label': 'testable'})['H2']['rl_benefit'], 'claimed')
        self.assertEqual(AN.decide(fams, sec, {'label': AN.P_BOTH_NOT_TESTABLE})['H2']['rl_benefit'],
                         'not testable at this operating point')
        doc, _ = self.run_analysis(matrix({'fl_full': base, 'fl_heuristic': base}, arms=('fl_full', 'fl_heuristic')))
        self.assertEqual(AN.decide(doc['families'], doc['secondary'], {'label': 'testable'})['H2']['rl_benefit'],
                         'not claimed (H2 inconclusive)')
        # the RL freeze: schema, frozen, the Sec. 5.8 entry; consistent with the aggregation's RL freeze
        rl = self.tmp / 'rl_freeze.json'
        rl.write_text(json.dumps({'schema': AN.RL_FREEZE_SCHEMA, 'frozen': True,
                                  'p_both': {'p_both': 0.02, 'label': AN.P_BOTH_NOT_TESTABLE, 'kappa': 1.0}}))
        pb = AN.load_p_both(rl)
        self.assertEqual((pb['p_both'], pb['label'], pb['sha256']), (0.02, AN.P_BOTH_NOT_TESTABLE, sha(rl)))
        doc, _ = self.run_analysis(rows, p_both=pb)
        self.assertEqual(doc['decisions']['H2']['rl_benefit'], AN.P_BOTH_NOT_TESTABLE)
        h2 = self.family(doc, 'H2')['fl_heuristic']                    # H2 is still reported, with the label
        self.assertEqual((h2['label'], h2['note']), ('improves', f'P_both label (Sec. 5.8): {AN.P_BOTH_NOT_TESTABLE}'))
        self.assertNotIn('note', self.family(doc, 'H3')['fl_original'])
        self.assertEqual(doc['inputs'][pb['path']], pb['sha256'])
        rl.write_text(json.dumps({'schema': AN.RL_FREEZE_SCHEMA, 'frozen': False, 'p_both': {'label': 'testable'}}))
        with self.assertRaises(AN.AnalysisError):
            AN.load_p_both(rl)
        self.assertEqual(AN.load_p_both(rl, allow_dev=True)['label'], 'testable')
        src = self.source(rows)
        src['rl_sha256'] = 'e' * 64
        with self.assertRaises(AN.AnalysisError):
            AN.analyze([src], table=TABLE, settings=FAST, p_both=pb)

    def test_secondary_rows(self):
        """Sec. 9.3: every family contrast on every other quantity, uncorrected; a metric without a direction is
        descriptive; H4-cl adds the lease metrics, RL-abl the scheduler rates; no family row is repeated."""
        rows = matrix({'fl_full': noisy(10, 61), 'fixed_deep': noisy(0, 62)}, arms=('fl_full', 'fixed_deep'),
                      extra={'fl_full': {'success': lambda i: float(i % 2), 'route_completion': 90.0},
                             'fixed_deep': {'p_both': None}})
        doc, tables = self.run_analysis(rows)
        sec = doc['secondary']
        self.assertTrue(all(r['p_adjusted'] == r['p_two_sided'] and r['correction'] == 'none (uncorrected)'
                            for r in sec))
        by = {}
        for r in sec:
            by.setdefault(r['contrast'], []).append(r['metric'])
        h1c = 'fl_full_minus_fixed_deep_k1.0_s11_all'
        self.assertEqual(by[h1c], ['success', 'route_completion', 'infractions_per_km', 'gpu_usage', 'action_age_p50_s',
                                   'action_age_p95_s', 'fallback_ratio', 'eir', 'r_cond', 'p_both'])
        self.assertEqual(by['fl_full_minus_fl_heuristic_k1.0_s11_all'][:5],
                         ['success', 'route_completion', 'collisions_per_km', 'infractions_per_km', 'dmr'])
        self.assertEqual(by['fl_heuristic_minus_fl_global_shield_k1.0_s11_E'][-2:],
                         ['lease_utilization', 'premature_expiry_ratio'])
        self.assertEqual(by['fl_full_minus_fl_bandit_k1.0_s11_E'][-2:], ['deviation_rate', 'bypass_rate'])
        self.assertEqual(len(by), 15)
        row = {r['metric']: r for r in sec if r['contrast'] == h1c}
        self.assertEqual((row['success']['n'], row['success']['label'], row['success']['role']),
                         (44, 'improves', 'secondary'))                # 22 routes 1 - 0, 22 routes 0 - 0
        self.assertEqual((row['route_completion']['label'], row['gpu_usage']['label'], row['gpu_usage']['role']),
                         ('improves', 'descriptive', 'descriptive'))
        self.assertEqual((row['p_both']['n'], row['p_both']['label']), (0, 'descriptive'))
        self.assertEqual(row['fallback_ratio']['column'], 'deadline_miss_ratio')
        self.assertEqual(row['eir']['column'], 'realized_invalid_tick_ratio')
        self.assertEqual(row['r_cond']['column'], 'realized_r_cond')
        self.assertEqual(len(tables['secondary.csv']), len(sec))


# ============================================================================================ the interim-look guard

class Guard(Base):
    def rows(self, routes=ROUTES[:4], **over):
        return [run_row(a, r, **over) for r in routes for a in ('fl_full', 'fixed_deep')]

    def test_test_route_rows_are_refused_before_the_freeze(self):
        """A row on a registered test route (however flagged), a flagged row on a synthetic route, or a guarded row:
        refused without a record, even when no outcome column is filled (health-only)."""
        cases = {'registered route': self.rows(routes=REGISTERED_TEST[:1]),
                 'registered route, health-only': self.rows(routes=REGISTERED_TEST[:1], analysis_use=False,
                                                            health_only=True, missing_reason='health_only',
                                                            driving_score=None),
                 'flagged test_route': self.rows(test_route=True),
                 'guard note': self.rows(guard_note='pre_freeze: no valid analysis-freeze record (Sec. 9.11)')}
        for name, rows in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(AN.GuardRefused) as e:
                    self.run_analysis(rows)
                self.assertIn('no valid analysis-freeze record', str(e.exception))
        doc, _ = self.run_analysis(self.rows())                         # synthetic routes, not flagged
        self.assertEqual((doc['interim_guard']['status'], doc['interim_guard']['test_input_rows']), ('pre_freeze', 0))

    def frozen(self, registered=False):
        return {'path': 'rec.json', 'sha256': 'f' * 64, 'frozen': 'now', 'trigger': 'all_final', 'protocol': 'P.md',
                'protocol_sha256': 'a' * 64, 'registered': registered}

    def test_conditions_after_the_freeze(self):
        fz, cited = self.frozen(), {'path': AN.THIS_REL, 'sha256': 'x', 'cited': True}
        released = f'{G.RELEASED}: by the analysis-freeze record ffffffffffff (DEVELOPMENT record)'
        rows = self.rows(test_route=True, guard_note=released)
        agg = AN.load_aggregation(write_agg(self.tmp / 'agg', rows, 'f' * 64))
        tr = set(ROUTES) | set(REGISTERED_TEST)
        use, doc = AN.guard_rows([agg], fz, tr, code=cited)
        self.assertEqual((len(use), doc['released_rows'], doc['status']), (8, 8, 'frozen_development'))
        refusals = {
            'not cited': ([agg], {**cited, 'cited': False}, 'not cited in Sec. 13'),
            'bare CSV': ([self.source(rows)], cited, 'a bare CSV'),
            'another record': ([AN.load_aggregation(write_agg(self.tmp / 'agg2', rows, 'e' * 64))], cited,
                               'made with the analysis-freeze record'),
            'not released': ([AN.load_aggregation(write_agg(
                self.tmp / 'agg3', self.rows(test_route=True, guard_note='withheld: x'), 'f' * 64))], cited,
                'not released'),
            'registered route, development record': ([AN.load_aggregation(write_agg(
                self.tmp / 'agg4', self.rows(routes=REGISTERED_TEST[:2], test_route=True, guard_note=released),
                'f' * 64))], cited, 'development analysis-freeze record'),
        }
        for name, (sources, code, text) in refusals.items():
            with self.subTest(case=name):
                with self.assertRaises(AN.GuardRefused) as e:
                    AN.guard_rows(sources, fz, tr, code=code)
                self.assertIn(text, str(e.exception))

    def test_a_development_record_end_to_end(self):
        """A record written by interim_guard.freeze_record, cited (with this script's sha256) in Sec. 13 of a
        development PROTOCOL.md copy and its seal, loaded by interim_guard.load_freeze: the released rows of extra
        (synthetic) routes are analysed; the same copy without this script's sha256 is refused."""
        rows = matrix({'fl_full': noisy(10, 71), 'fixed_deep': noisy(0, 72)}, arms=('fl_full', 'fixed_deep'))
        recs = [{'job': r['job'], 'job_file': 'synthetic.jsonl', 'outcome': 'ok', 'selected_run': r['selected_run']}
                for r in rows]
        record = G.freeze_record(recs, {'synthetic.jsonl': 'b' * 64}, created='2026-11-14T00:00:00+0800')
        rec = self.tmp / 'analysis_freeze.json'
        rec.write_text(json.dumps(record, sort_keys=True))
        prot, seal = self.tmp / 'PROTOCOL.md', self.tmp / 'SEAL.sha256'

        def load(cite_code):
            text = f'# P\n\n## 13. Registration and amendments\nrecord {sha(rec)}\n'
            text += f'analysis code {sha(ROOT / AN.THIS_REL)}\n' if cite_code else ''
            prot.write_text(text + '\n## 14. TRIMMED\n')
            seal.write_text(f'{sha(prot)}  {prot}\n')
            return G.load_freeze(rec, protocol=prot, seal=seal)

        fz = load(True)
        self.assertFalse(fz['registered'])
        note = f'{G.RELEASED}: by the analysis-freeze record {fz["sha256"][:12]} (DEVELOPMENT record)'
        for r in rows:
            r.update(test_route=True, guard_note=note)
        agg = AN.load_aggregation(write_agg(self.tmp / 'agg', rows, fz['sha256']))
        tr, _ = G.test_routes(extra=ROUTES)
        doc, _ = AN.analyze([agg], table=TABLE, settings=FAST, freeze=fz, test_routes=tr)
        self.assertEqual(self.family(doc, 'H1')['fixed_deep']['n'], 44)
        self.assertEqual(doc['interim_guard']['status'], 'frozen_development')
        self.assertTrue(doc['interim_guard']['code']['cited'])
        self.assertIn('a development analysis-freeze record (cited by a development copy of PROTOCOL.md)',
                      doc['development'])
        self.assertEqual(doc['scope'], 'test routes, released by the analysis-freeze record')
        self.assertEqual((doc['inputs'][fz['path']], doc['inputs'][fz['seal']]), (sha(rec), sha(seal)))
        fz = load(False)
        with self.assertRaises(AN.GuardRefused):
            AN.analyze([agg], table=TABLE, settings=FAST, freeze=fz, test_routes=tr)


# ================================================================================== inputs and the command line

class CommandLine(Base):
    def test_end_to_end(self):
        base = noisy(0, 82)
        rows = matrix({'fl_full': lambda i: base(i) + 25.0, 'fixed_deep': base, 'fast_only': noisy(0, 83)},
                      arms=('fl_full', 'fixed_deep', 'fast_only'))
        agg, out = write_agg(self.tmp / 'agg', rows), self.tmp / 'out'
        self.assertEqual(AN.main(['--agg', str(agg), '--out', str(out)], settings=FAST, table=TABLE), 0)
        sums = AN.read_sums(out / 'SHA256SUMS')
        self.assertEqual(sorted(sums), sorted(n for n in AN.OUTPUT_FILES if n != 'SHA256SUMS'))
        self.assertTrue(all(sha(out / n) == s for n, s in sums.items()))
        doc = json.loads((out / 'analysis.json').read_text(), parse_constant=lambda c: self.fail(c))
        self.assertEqual((doc['schema'], doc['status']), (AN.SCHEMA, 'development'))
        # synthetic route table, small settings, no record, no RL freeze, no S3, H5 undetermined, not final_<stamp>
        self.assertEqual(len(doc['development']), 7, doc['development'])
        self.assertTrue(doc['development'][-1].startswith(f'output directory {AN.PJ.rel(out)} is not inside'))
        self.assertEqual(doc['inputs'][AN.V2_REL], AN.V2_SHA256)
        self.assertEqual(doc['outputs'], {n: sums[n] for n in AN.TABLE_COLUMNS})
        with open(out / 'family_H1.csv', newline='') as f:
            h1 = list(csv.DictReader(f))
        self.assertEqual(list(h1[0]), list(AN.ROW_COLUMNS))
        self.assertEqual([r['label'] for r in h1], ['improves', 'improves', 'no data', 'no data'])
        self.assertEqual(h1[0]['n'], '44')
        log = [json.loads(x) for x in (out / G.LOG_NAME).read_text().splitlines()]
        self.assertEqual([(x['request'], x['decision']) for x in log], [('analysis', 'granted')])
        # occupied without --force (logged), then replaced with it
        self.assertEqual(AN.main(['--agg', str(agg), '--out', str(out)], settings=FAST, table=TABLE), 1)
        self.assertEqual(AN.main(['--agg', str(agg), '--out', str(out), '--force'], settings=FAST, table=TABLE), 0)
        log = [json.loads(x)['decision'] for x in (out / G.LOG_NAME).read_text().splitlines()]
        self.assertEqual(log, ['granted', 'refused', 'granted'])
        # a changed aggregation (runs.csv after SHA256SUMS) is an input error
        with open(agg / 'runs.csv', 'a') as f:
            f.write('\n')
        self.assertEqual(AN.main(['--agg', str(agg), '--out', str(self.tmp / 'o2')], settings=FAST, table=TABLE), 2)
        self.assertFalse((self.tmp / 'o2' / 'analysis.json').exists())

    def test_end_to_end_part_b(self):
        """--offline and --s3: the five Part B tables are written and listed in SHA256SUMS, the offline files and the S3
        report enter the inputs with their sha256, the decisions carry H4 offline and H5; a missing offline file or an
        S3 report of another schema is an input error (exit 2)."""
        rows = matrix({'fl_full': noisy(10, 84), 'fixed_deep': noisy(0, 85)}, arms=('fl_full', 'fixed_deep'))
        rows += [run_row('fl_full', rid, seed=12, values={'driving_score': 50.0}) for rid in TABLE['subsets']['R']]
        agg = write_agg(self.tmp / 'agg', rows, extra={'commit_audit': audit_doc([run_audit(0)])})
        off = write_offline(self.tmp / 'off', [prow('continuity', 0.01, 0.05), prow('R_cond', -0.01, 0.01)])
        s3, out = s3_report(self.tmp / 's3.json'), self.tmp / 'out'
        argv = ['--agg', str(agg), '--offline', str(off), '--s3', str(s3), '--out', str(out)]
        self.assertEqual(AN.main(argv, settings=FAST, table=TABLE), 0)
        sums = AN.read_sums(out / 'SHA256SUMS')
        self.assertEqual(len(sums), len(AN.TABLE_COLUMNS) + 1)
        for name in ('descriptive.csv', 'per_ability.csv', 'per_scenario.csv', 'conditions.csv', 'h4_offline.csv'):
            with self.subTest(table=name):
                self.assertEqual(sha(out / name), sums[name])
                with open(out / name, newline='') as f:
                    self.assertEqual(next(csv.reader(f)), list(AN.TABLE_COLUMNS[name]))
        doc = json.loads((out / 'analysis.json').read_text())
        self.assertEqual(doc['decisions']['H4_offline']['label'], 'supported')
        self.assertEqual(doc['decisions']['H5']['label'], 'undetermined')          # one phase (P4) in the input
        self.assertEqual(doc['inputs'][AN.PJ.rel(s3)], sha(s3))
        self.assertEqual(doc['inputs'][AN.PJ.rel(off / 'paired.csv')], sha(off / 'paired.csv'))
        self.assertIn(f'offline outputs from {AN.PJ.rel(off)}, not {AN.OFFLINE_REL}', doc['development'])
        self.assertEqual(doc['replicates']['noise_floor_ds']['fl_full']['n'], 15)
        (off / 'per_clip_selected.csv').unlink()
        self.assertEqual(AN.main([*argv[:-1], str(self.tmp / 'o2')], settings=FAST, table=TABLE), 2)
        self.assertEqual(AN.main(['--agg', str(agg), '--s3', str(s3_report(self.tmp / 'x.json', schema='y')), '--out',
                                  str(self.tmp / 'o3')], settings=FAST, table=TABLE), 2)
        self.assertFalse((self.tmp / 'o3' / 'analysis.json').exists())

    def test_refusals(self):
        """Test-route rows before the freeze: exit 4, logged, nothing else written; a protected output directory:
        exit 1 and nothing written at all."""
        bad = write_csv(self.tmp / 'test_routes.csv', [run_row('fl_full', REGISTERED_TEST[0])])
        out = self.tmp / 'out'
        self.assertEqual(AN.main(['--runs', str(bad), '--out', str(out)], settings=FAST, table=TABLE), 4)
        self.assertEqual(sorted(p.name for p in out.iterdir()), [G.LOG_NAME])
        entry = json.loads((out / G.LOG_NAME).read_text())
        self.assertEqual((entry['decision'], entry['request']), ('refused', 'analysis'))
        self.assertIn('no valid analysis-freeze record', entry['reason'])
        protected = ROOT / 'framelease_v4/analysis/_analyze_v4_test_never_created'
        ok = write_csv(self.tmp / 'ok.csv', [run_row('fl_full', ROUTES[0])])
        self.assertEqual(AN.main(['--runs', str(ok), '--out', str(protected)], settings=FAST, table=TABLE), 1)
        self.assertFalse(protected.exists())

    def test_inputs(self):
        rows = [run_row('fl_full', ROUTES[0])]
        with self.assertRaises(AN.AnalysisError):                        # a required column is missing
            AN.read_runs(write_csv(self.tmp / 'a.csv', [{k: v for k, v in rows[0].items() if k != 'dmr'}]))
        with self.assertRaises(AN.AnalysisError):                        # not a boolean
            AN.read_runs(write_csv(self.tmp / 'b.csv', [{**rows[0], 'analysis_use': 'maybe'}]))
        r, absent = AN.read_runs(write_csv(self.tmp / 'c.csv', [{k: v for k, v in rows[0].items()
                                                                 if k != 'bypass_rate'}]))
        self.assertEqual((absent, r[0]['analysis_use'], r[0]['kappa'], r[0]['seed']), (['bypass_rate'], True, 1.0, 11))
        agg = write_agg(self.tmp / 'agg', rows)
        doc = json.loads((agg / 'aggregate.json').read_text())
        doc['schema'] = 'other'
        (agg / 'aggregate.json').write_text(json.dumps(doc))
        with self.assertRaises(AN.AnalysisError):                        # SHA256SUMS no longer matches
            AN.load_aggregation(agg)
        (agg / 'SHA256SUMS').write_text(''.join(f'{sha(agg / n)}  {n}\n' for n in ('aggregate.json', 'runs.csv')))
        with self.assertRaises(AN.AnalysisError):                        # not the aggregator's schema
            AN.load_aggregation(agg)

    def test_training_route_aggregation(self):
        """An aggregation of training routes (the registered pool, P1-like rows): no test-route row, no record needed;
        the registered route table finds no cell, every family is 'no data'."""
        training = [str(r['route_id']) for r in json.loads((ROOT / G.PJ.ROUTE_SPLIT).read_text())['training'][:4]]
        rows = [run_row(a, r, phase='P1', block='ref', training_route=True) for r in training
                for a in ('fixed_deep', 'fast_only')]
        doc, _ = AN.analyze([self.source(rows)], settings=FAST)
        self.assertTrue(doc['route_table']['registered'])
        self.assertEqual(doc['outside_rows']['off_route_table'], {'P1/ref': 8})
        self.assertEqual({r['label'] for f in doc['families'] for r in f['rows']}, {'no data'})
        self.assertEqual(doc['interim_guard']['test_input_rows'], 0)
        doc, tables = AN.analyze([self.source(rows)], settings=FAST, offline=AN.load_offline())
        self.assertEqual({r['n'] for r in doc['descriptive']} | {r['n'] for r in tables['conditions.csv']}
                         | {r['n'] for r in tables['per_ability.csv']}, {0})            # no test-route value anywhere
        self.assertEqual({r['status'] for r in tables['per_scenario.csv']}, {'no_row'})
        self.assertEqual((doc['manipulation']['analysed_runs']['runs'], doc['overhead']), (0, {}))
        self.assertEqual(doc['h4_offline']['label'], 'inconclusive')                   # offline, not test routes


# ============================================================================== known answers (Secs. 9.1, 9.2, 9.3)

def ints(i):
    """An integer DS per route index (30-69), so that sums and differences are exact."""
    return float(30 + (i * 7) % 40)


class KnownAnswers(Base):
    def test_planted_effect_null_and_holm_by_hand(self):
        """H1 with a planted +30 against Fixed Deep and Age-Only, none against Fast Only (identical arms), and no
        Event-Triggered row. Hand-checked: a constant difference on 44 routes reaches |sum| only with the two constant
        sign vectors, p = 2 / 2^44 = 2^-43; identical arms give p = 1; Holm over 4 with the missing p as 1: the two
        tied smallest p get 4 x 2^-43 (rank 1: 4 p; rank 2: 3 p, raised to the running maximum), the p of 1 stays 1,
        the missing one stays missing. Labels: improves, inconclusive (no label), improves, no data."""
        ds = {'fl_full': lambda i: ints(i) + 30.0, 'fixed_deep': ints, 'fast_only': lambda i: ints(i) + 30.0,
              'age_only': ints}
        doc, _ = self.run_analysis(matrix(ds, arms=('fl_full', 'fixed_deep', 'fast_only', 'age_only')))
        h1 = self.family(doc, 'H1')
        self.assertEqual([h1[b]['p_two_sided'] for b in AN.H1_OTHERS], [2.0 ** -43, 1.0, 2.0 ** -43, None])
        self.assertEqual([h1[b]['p_adjusted'] for b in AN.H1_OTHERS], [4 * 2.0 ** -43, 1.0, 4 * 2.0 ** -43, None])
        self.assertEqual([h1[b]['label'] for b in AN.H1_OTHERS], ['improves', 'inconclusive', 'improves', 'no data'])
        self.assertEqual([h1[b]['mean'] for b in AN.H1_OTHERS], [30.0, 0.0, 30.0, None])
        self.assertEqual(doc['decisions']['H1']['finding_1']['statement'],
                         'mixed (not stated): fixed_deep improves, fast_only inconclusive')

    def test_holm_by_hand(self):
        """p = (0.01, 0.04, 0.03, 0.005): ordered 0.005 x 4 = 0.02, 0.01 x 3 = 0.03, 0.03 x 2 = 0.06, 0.04 x 1 = 0.04
        raised to 0.06; a missing p counts as 1 and keeps the family size."""
        for got, want in ((AN.holm([0.01, 0.04, 0.03, 0.005]), [0.03, 0.06, 0.06, 0.02]),
                          (AN.holm([0.01, None, 0.03, 0.005]), [0.03, None, 0.06, 0.02]),
                          (AN.holm([0.2, 0.01]), [0.2, 0.02])):
            for g, w in zip(got, want):
                if w is None:
                    self.assertIsNone(g)
                else:
                    self.assertAlmostEqual(g, w, places=12)
        self.assertEqual(AN.directional_label(5.0, 0.06, 'higher'), 'inconclusive')   # 0.06 after Holm: no label

    def test_dp_equals_enumeration_small_n(self):
        """The exact DP of sign_flip_test (forced with enum_max_n 0) equals a brute-force count over all 2^n sign
        vectors of the differences on the 0.01 grid (integers, ties exact), and so does the complete enumeration."""
        rng = np.random.default_rng(13)
        vectors = [rng.integers(-500, 501, n) / 100.0 for n in (6, 9, 12)]
        vectors.append(np.array([1.0, 1.0, 2.0, 2.0, -3.0, 0.0, 4.0, -1.0]))       # ties and a zero
        for d in vectors:
            k = [int(round(x * 100)) for x in d]
            t = abs(sum(k))
            hits = sum(1 for s in itertools.product((1, -1), repeat=len(k))
                       if abs(sum(a * b for a, b in zip(s, k))) >= t)
            with self.subTest(n=len(d)):
                dp = AN.sign_flip_test(d, 0.01, 100, AN.MC_SEED, 0)
                self.assertEqual(dp['p_method'], 'exact_dp_rounded')
                self.assertEqual(dp['p_two_sided'], hits / 2 ** len(k))
                self.assertEqual(AN.sign_flip_test(d, 0.01, 100, AN.MC_SEED, 22)['p_two_sided'], hits / 2 ** len(k))

    def test_bootstrap_determinism(self):
        """The same input gives identical tables (a fresh default_rng(20261110) for every contrast and metric, ability
        group and condition); the interval equals the quantiles of the means drawn here from default_rng(20261110);
        another seed gives another interval."""
        rows = matrix({'fl_full': noisy(8, 97), 'fixed_deep': noisy(0, 98)}, arms=('fl_full', 'fixed_deep'))
        doc1, t1 = self.run_analysis(rows)
        doc2, t2 = self.run_analysis(rows)
        self.assertEqual(t1, t2)
        self.assertEqual(doc1['families'], doc2['families'])
        d = np.array([noisy(8, 97)(i) - noisy(0, 98)(i) for i in range(44)])
        means = d[np.random.default_rng(20261110).integers(0, 44, size=(FAST.n_boot, 44))].mean(axis=1)
        want = [float(q) for q in np.quantile(means, [0.025, 0.975])]
        self.assertEqual(self.family(doc1, 'H1')['fixed_deep']['ci95'], want)
        doc3, _ = self.run_analysis(rows, settings=AN.Settings(n_boot=FAST.n_boot, boot_seed=1, mc_flips=2000))
        self.assertNotEqual(self.family(doc3, 'H1')['fixed_deep']['ci95'], want)


# ======================================================== descriptive contrasts (Secs. 7.5, 9.6, 9.9, 9.10)

class DescriptiveParts(Base):
    def test_definitions(self):
        """Sec. 9.6: four replicated arms on R at kappa 1.0; Sec. 7.5: the RL gain by kappa on E; every descriptive row
        is labelled 'descriptive' and never corrected."""
        self.assertEqual(AN.REPLICATE_ARMS, ('fixed_deep', 'fast_only', 'fl_heuristic', 'fl_full'))
        groups = {}
        for d in AN.DESCRIPTIVE_CONTRASTS:
            groups.setdefault(d.group, []).append((d.contrast.a.name, d.contrast.b.name, d.contrast.subset))
        self.assertEqual(groups['noise_floor'], [(f'{a}_k1.0_s11', f'{a}_k1.0_s12', 'R') for a in AN.REPLICATE_ARMS])
        self.assertEqual(groups['rl_gain_kappa'], [(f'fl_full_k{k}_s11', f'fl_heuristic_k{k}_s11', 'E')
                                                   for k in ('1.0', '1.5', '2.0')])
        self.assertEqual(groups['f3_kappa_1.0'], [('fl_full_k1.0_s11', f'{b}_k1.0_s11', 'E')
                                                  for b in ('fixed_deep', 'fast_only')])
        self.assertEqual(len(AN.DESCRIPTIVE_CONTRASTS), 19)
        self.assertEqual(AN.DESCRIPTIVE, 'descriptive')

    def test_noise_floor_and_seed12_known(self):
        """Seed 12 on R: Fixed Deep and fl_full at seed 12 = seed 11 + 10 on the 8 routes of even position in R and
        - 10 on the other 7, so |d| = 10 everywhere (mean, median, max 10; interval [10, 10]) and the mean s11 - s12 is
        (-80 + 70) / 15; fl_full = Fixed Deep + 20 at both seeds: both contrasts on R have mean 20, the same sign, and
        the seed-12 interval [20, 20] contains the seed-11 mean."""
        rows = matrix({'fl_full': lambda i: ints(i) + 20.0, 'fixed_deep': ints}, arms=('fl_full', 'fixed_deep'))
        s12 = {rid: ints(ROUTES.index(rid)) + (10.0 if k % 2 == 0 else -10.0) for k, rid in enumerate(TABLE['subsets']
                                                                                                        ['R'])}
        rows += [run_row('fixed_deep', rid, seed=12, values={'driving_score': v}) for rid, v in s12.items()]
        rows += [run_row('fl_full', rid, seed=12, values={'driving_score': v + 20.0}) for rid, v in s12.items()]
        doc, tables = self.run_analysis(rows)
        nf = doc['replicates']['noise_floor_ds']
        for arm in ('fixed_deep', 'fl_full'):
            with self.subTest(arm=arm):
                self.assertEqual((nf[arm]['n'], nf[arm]['n_expected']), (15, 15))
                self.assertEqual((nf[arm]['mean_abs_diff'], nf[arm]['median_abs_diff'], nf[arm]['max_abs_diff']),
                                 (10.0, 10.0, 10.0))
                self.assertEqual(nf[arm]['mean_abs_diff_ci95'], [10.0, 10.0])
                self.assertAlmostEqual(nf[arm]['mean'], -10.0 / 15, places=12)
        self.assertEqual((nf['fast_only']['n'], nf['fast_only']['mean_abs_diff']), (0, None))
        pair = {p['contrast']: p for p in doc['replicates']['seed12_contrasts']}['fl_full - fixed_deep']
        self.assertEqual((pair['seed12_on_R']['mean'], pair['seed11_on_R']['mean']), (20.0, 20.0))
        self.assertEqual((pair['same_sign_of_mean'], pair['seed12_ci95_contains_seed11_mean']), (True, True))
        self.assertEqual(pair['seed12_on_R']['n'], 15)
        rows_d = {r['contrast']: r for r in tables['descriptive.csv']}
        nfr = rows_d['fixed_deep_minus_fixed_deep_k1.0_s11-12_R']
        self.assertEqual((nfr['mean_abs_diff'], nfr['mean_abs_diff_ci95_lo'], nfr['mean_abs_diff_ci95_hi'],
                          nfr['label'], nfr['role'], nfr['group']), (10.0, 10.0, 10.0, 'descriptive', 'descriptive',
                                                                     'noise_floor'))
        self.assertTrue(all(r['p_adjusted'] is None and r['label'] == 'descriptive' for r in doc['descriptive']))

    def test_rl_gain_breakdown_known(self):
        """fl_full = fl_heuristic + d with d = 5 + (index % 3 - 1) at kappa 1.0 (44 routes), + 10 at kappa 1.5 and
        + 20 at 2.0 (E), + 7 at seed 12 (R): by kappa the means are mean(d on E) / 10 / 20, by seed mean(d on R) / 7;
        by ability n and mean follow the hand-read index lists, the interval equals bootstrap_ci on the ability's
        routes (fresh default_rng(20261110)), and there is none below 5 routes (Give_Way)."""
        d = {i: 5.0 + (i % 3 - 1) for i in range(44)}
        rows = matrix({'fl_full': lambda i: ints(i) + d[i], 'fl_heuristic': ints}, arms=('fl_full', 'fl_heuristic'),
                      routes=ROUTES_B)
        for k, add in ((1.5, 10.0), (2.0, 20.0)):
            rows += [run_row(a, rid, k, values={'driving_score': ints(ROUTES_B.index(rid)) + (add if a == 'fl_full'
                                                                                          else 0.0)})
                     for rid in E_B for a in ('fl_full', 'fl_heuristic')]
        rows += [run_row(a, rid, seed=12, values={'driving_score': 50.0 + (7.0 if a == 'fl_full' else 0.0)})
                 for rid in R_B for a in ('fl_full', 'fl_heuristic')]
        doc, tables = self.run_analysis(rows, table=TABLE_B2D)
        g = doc['rl_gain']
        self.assertEqual((g['all_44_routes']['n'], g['all_44_routes']['mean']), (44, float(np.mean(list(d.values())))))
        self.assertAlmostEqual(g['by_kappa_on_E']['1.0']['mean'], float(np.mean([d[i] for i in range(0, 44, 2)])))
        self.assertEqual([g['by_kappa_on_E'][k]['mean'] for k in ('1.5', '2.0')], [10.0, 20.0])
        self.assertEqual([g['by_kappa_on_E'][k]['n'] for k in ('1.0', '1.5', '2.0')], [22, 22, 22])
        self.assertAlmostEqual(g['by_seed_on_R']['11']['mean'], float(np.mean([d[i] for i in range(0, 44, 3)])))
        self.assertEqual((g['by_seed_on_R']['12']['mean'], g['by_seed_on_R']['12']['n']), (7.0, 15))
        ab = {x['ability']: x for x in g['by_ability']}
        self.assertEqual(list(ab), list(AN.ABILITIES) + ['all'])
        for name, idx in list(ABILITY_INDEX.items()) + [('all', tuple(range(44)))]:
            v = np.array([d[i] for i in idx])
            with self.subTest(ability=name):
                self.assertEqual((ab[name]['n'], ab[name]['n_routes']), (len(idx), len(idx)))
                self.assertAlmostEqual(ab[name]['mean'], float(v.mean()), places=12)
                want = V2.bootstrap_ci(v, FAST.n_boot, AN.BOOT_SEED, levels=(0.95,))['ci95'] if len(idx) >= 5 else None
                self.assertEqual(ab[name]['ci95'], want)
        self.assertIsNone(ab['Give_Way']['ci95'])
        h2_rows = [r for r in tables['per_ability.csv'] if r['contrast'] == AN.RL_GAIN.cid]
        self.assertEqual([r['ability'] for r in h2_rows], list(AN.ABILITIES) + ['all'])
        self.assertEqual(h2_rows[3]['routes'], '|'.join(ROUTES_B[i] for i in ABILITY_INDEX['Give_Way']))

    def test_per_scenario_and_conditions(self):
        """conditions.csv: fl_full DS = 40 + index, so the mean is 61.5 on the 44 routes and 61 on E, with the interval
        of bootstrap_ci on those values; a constant arm has [30, 30]; an arm without rows has n 0. per_scenario.csv:
        one row per cell of cells.csv, sorted by scenario type, with the abilities of the hand-read map."""
        rows = matrix({'fl_full': lambda i: 40.0 + i, 'fixed_deep': 30.0}, arms=('fl_full', 'fixed_deep'),
                      routes=ROUTES_B)
        doc, tables = self.run_analysis(rows, table=TABLE_B2D)
        cond = {(r['condition'], r['subset'], r['metric']): r for r in tables['conditions.csv']}
        c = cond[('fl_full_k1.0_s11', 'all', 'driving_score')]
        want = V2.bootstrap_ci(np.arange(40.0, 84.0), FAST.n_boot, AN.BOOT_SEED, levels=(0.95,))['ci95']
        self.assertEqual((c['n'], c['n_used'], c['n_routes'], c['mean'], [c['ci95_lo'], c['ci95_hi']]),
                         (44, 44, 44, 61.5, want))
        self.assertEqual(cond[('fl_full_k1.0_s11', 'E', 'driving_score')]['mean'], 61.0)
        fd = cond[('fixed_deep_k1.0_s11', 'all', 'driving_score')]
        self.assertEqual((fd['mean'], fd['ci95_lo'], fd['ci95_hi']), (30.0, 30.0, 30.0))
        self.assertEqual((cond[('fl_original_k1.0_s11', 'all', 'driving_score')]['n'],
                          cond[('fl_original_k1.0_s11', 'all', 'driving_score')]['mean']), (0, None))
        self.assertEqual({k[1] for k in cond if k[0] == 'fl_full_k1.0_s11'}, {'all', 'E', 'R'})
        scen = tables['per_scenario.csv']
        self.assertEqual(len(scen), len(tables['cells.csv']))
        self.assertEqual([r['scenario_type'] for r in scen], sorted(r['scenario_type'] for r in scen))
        by = {(r['route_id'], r['condition']): r for r in scen}
        r6 = by[(ROUTES_B[6], 'fl_full_k1.0_s11')]
        self.assertEqual((r6['driving_score'], r6['status'], r6['abilities'], r6['subsets']),
                         (46.0, 'used', 'Merging|Traffic_Signs', 'E|R'))          # index 6: E and R
        self.assertEqual(by[(ROUTES_B[0], 'fl_full_k1.0_s12')]['status'], 'no_row')
        self.assertIsNone(by[(ROUTES_B[0], 'fl_full_k1.0_s12')]['driving_score'])

    def test_sensitivity(self):
        """Sec. 9.10: the registered MDE table from SD 31 with z values written out (z_0.99375 = 2.4977054744,
        z_0.9875 = 2.2414027276, z_0.975 = 1.9599639845, z_0.80 = 0.8416212336); per family row the observed MDE at
        the first and last Holm step, and the statement only for a row that is neither improves nor worse."""
        z = {0.0125: 2.4977054744, 0.025: 2.2414027276, 0.05: 1.9599639845}
        for setting, n, alpha, registered in AN.MDE_REGISTERED:
            hand = (z[alpha] + 0.8416212336) * 31.0 / math.sqrt(n)
            with self.subTest(setting=setting, alpha=alpha):
                self.assertAlmostEqual(AN.mde(31.0, n, alpha), hand, places=8)
                self.assertLess(abs(hand - registered), 0.5)          # 15.6, 13.1, 'about 20', 18.5
                if registered != 20.0:
                    self.assertEqual(round(hand, 1), registered)
        base = noisy(0, 120)
        rows = matrix({'fl_full': lambda i: base(i) + 25.0, 'fixed_deep': base, 'fast_only': noisy(25, 121)},
                      arms=('fl_full', 'fixed_deep', 'fast_only'))
        doc, _ = self.run_analysis(rows)
        h1 = self.family(doc, 'H1')
        self.assertEqual((h1['fixed_deep']['label'], h1['fast_only']['label']), ('improves', 'inconclusive'))
        sens = {(r['family'], r['contrast']): r for r in doc['sensitivity']['contrasts']}
        fo = sens[('H1', h1['fast_only']['contrast'])]
        sd = h1['fast_only']['sd']
        self.assertAlmostEqual(fo['mde_observed_first_step'], (z[0.0125] + 0.8416212336) * sd / math.sqrt(44), 6)
        self.assertAlmostEqual(fo['mde_observed_last_step'], (z[0.05] + 0.8416212336) * sd / math.sqrt(44), 6)
        self.assertAlmostEqual(fo['mde_planned_first_step'], 15.606, places=2)
        self.assertIn('no difference larger than about', fo['statement'])
        self.assertIn('not evidence of no effect', fo['statement'])
        self.assertIsNone(sens[('H1', h1['fixed_deep']['contrast'])]['statement'])
        self.assertIsNone(sens[('S-coll', h1['fast_only']['contrast'])]['mde_planned_first_step'])
        h2 = [r for r in doc['sensitivity']['contrasts'] if r['family'] == 'H2'][0]
        self.assertEqual((h2['alpha_first_step'], h2['alpha_last_step']), (0.05, 0.05))


# ============================================================================================ H4 offline (Sec. 9.4)

PAIRED_COLS = ('protocol', 'a', 'b', 'subset', 'need', 'alpha', 'metric', 'a_value', 'b_value', 'diff', 'diff_lo',
               'diff_hi', 'boot_share_diff_le_0')
PER_CLIP_COLS = ('design', 'need', 'clip', 'candidate', 'continuity', 'R_marg', 'R_cond', 'utilization',
                 'premature_refresh', 'mean_H_s', 'oracle_continuity', 'n', 'conf', 'over', 'overc')


def prow(metric, lo, hi, a='SUFFIX', b='GLOBAL', alpha=0.05, protocol='nested', need='fast'):
    """One paired.csv row (offline/analyze.py columns) with the interval [lo, hi] and its midpoint as the estimate."""
    return {'protocol': protocol, 'a': a, 'b': b, 'subset': 'all', 'need': need, 'alpha': alpha, 'metric': metric,
            'a_value': 0.5, 'b_value': 0.5, 'diff': (lo + hi) / 2, 'diff_lo': lo, 'diff_hi': hi,
            'boot_share_diff_le_0': 0.5}


def write_offline(d, paired_rows, per_clip_rows=()):
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    for name, cols, rows in (('paired.csv', PAIRED_COLS, paired_rows), ('per_clip_selected.csv', PER_CLIP_COLS,
                                                                        per_clip_rows)):
        with open(d / name, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(cols))
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, '') for k in cols})
    return d


class H4Offline(Base):
    def test_rule_known_cases(self):
        """Sec. 9.4 on the primary row: (continuity CI, realized-R_cond CI) -> label, edges included: an interval
        touching 0 does not lie above (or below) 0, an R_cond interval with its lower bound at 0 contains 0."""
        cases = [((0.01, 0.05), (-0.01, 0.02), 'supported'), ((0.01, 0.05), (-0.03, -0.01), 'supported'),
                 ((0.01, 0.05), (0.0, 0.02), 'supported'), ((0.01, 0.05), (0.001, 0.02), 'inconclusive'),
                 ((0.0, 0.05), (-0.01, 0.02), 'inconclusive'), ((-0.05, -0.01), (-0.01, 0.02), 'contradicted'),
                 ((-0.05, -0.01), (0.01, 0.02), 'contradicted'), ((-0.05, 0.0), (-0.01, 0.02), 'inconclusive'),
                 ((-0.02, 0.03), (-0.01, 0.02), 'inconclusive')]
        for k, (cont, risk, want) in enumerate(cases):
            off = AN.load_offline(write_offline(self.tmp / f'o{k}', [prow('continuity', *cont), prow('R_cond', *risk)]))
            doc, rows = AN.h4_offline(off)
            with self.subTest(continuity=cont, r_cond=risk):
                self.assertEqual((doc['label'], doc['primary']['label']), (want, want))
                self.assertEqual((doc['primary']['lo'], doc['primary']['hi'], doc['primary']['r_cond_lo']),
                                 (cont[0], cont[1], risk[0]))
        self.assertEqual(len(rows), 12)
        self.assertEqual([r['role'] for r in rows].count('primary'), 1)
        sec = {(r['a'], r['b'], r['alpha'], r['metric']): r for r in rows}
        miss = sec[('SUFFIX', 'AGE', 0.1, 'utilization')]                      # not in this paired.csv
        self.assertEqual((miss['label'], miss['source']), ('no data', None))
        self.assertIn('train-selected', miss['missing'])

    def test_secondary_orientation(self):
        """Premature refresh is a loss: a negative SUFFIX - GLOBAL interval is 'supported' (with the R_cond condition),
        a positive one 'contradicted'; utilization and continuity at 10% follow the primary rule."""
        rows = [prow('continuity', -0.02, 0.03), prow('R_cond', -0.01, 0.02),
                prow('premature_refresh', -0.05, -0.01), prow('utilization', 0.02, 0.04),
                prow('continuity', 0.02, 0.06, alpha=0.1), prow('R_cond', 0.01, 0.03, alpha=0.1),
                prow('premature_refresh', 0.01, 0.05, alpha=0.1),
                prow('continuity', 0.3, 0.5, b='AGE'), prow('R_cond', -0.02, 0.1, b='AGE')]
        doc, out = AN.h4_offline(AN.load_offline(write_offline(self.tmp / 'o', rows)))
        lab = {(r['b'], r['alpha'], r['metric']): r['label'] for r in out}
        self.assertEqual(lab[('GLOBAL', 0.05, 'continuity')], 'inconclusive')
        self.assertEqual(lab[('GLOBAL', 0.05, 'premature_refresh')], 'supported')
        self.assertEqual(lab[('GLOBAL', 0.05, 'utilization')], 'supported')
        self.assertEqual(lab[('GLOBAL', 0.1, 'continuity')], 'inconclusive')          # R_cond CI above 0
        self.assertEqual(lab[('GLOBAL', 0.1, 'premature_refresh')], 'contradicted')
        self.assertEqual(lab[('AGE', 0.05, 'continuity')], 'supported')
        self.assertEqual(doc['label'], 'inconclusive')                              # the primary row
        self.assertEqual(AN.h4_label({'lo': 0.1, 'hi': 0.2}, None, 'higher'), 'no data')

    def test_per_clip_fallback_known(self):
        """A TRAIN-selected quantity missing from paired.csv is recomputed from per_clip_selected.csv: 4 clips with
        continuity counts SUFFIX 3, 1, 0, 2 and GLOBAL 1, 1, 0, 1 of n 4, 2, 2, 4 give pooled 6 / 12 - 3 / 12 = 0.25;
        the interval equals an independent implementation of the offline bootstrap (the point estimate and 2000
        multinomial clip weights from default_rng(20261109), 2.5% / 97.5% quantiles of the finite values); R_cond pools
        overc / conf. A nested quantity cannot come from that file."""
        n, conf = [4, 2, 2, 4], [2, 1, 0, 2]
        cont = {'SUFFIX': [3, 1, 0, 2], 'GLOBAL': [1, 1, 0, 1]}
        overc = {'SUFFIX': [1, 0, 0, 1], 'GLOBAL': [0, 0, 0, 1]}
        per_clip = [{'design': des, 'need': 'fast', 'clip': f'clip{j}', 'candidate': 'x',
                     'continuity': cont[des][j] / n[j], 'oracle_continuity': 1.0, 'premature_refresh': 0.0,
                     'mean_H_s': 1.0, 'n': n[j], 'conf': conf[j], 'over': overc[des][j], 'overc': overc[des][j]}
                    for des in ('SUFFIX', 'GLOBAL') for j in range(4)]
        off = AN.load_offline(write_offline(self.tmp / 'o', [prow('continuity', -0.1, 0.1)], per_clip))
        w = np.vstack([np.ones(4), np.random.default_rng(20261109).multinomial(4, np.full(4, 0.25), size=2000)])
        for metric, num, den, point in (('continuity', cont, {k: n for k in cont}, 0.25),
                                        ('R_cond', overc, {k: conf for k in cont}, 0.2)):
            with np.errstate(invalid='ignore', divide='ignore'):
                dl = (w @ num['SUFFIX']) / (w @ den['SUFFIX']) - (w @ num['GLOBAL']) / (w @ den['GLOBAL'])
            fin = dl[1:][np.isfinite(dl[1:])]
            q, why = AN.offline_quantity(off, 'train', 'SUFFIX', 'GLOBAL', 0.05, metric)
            with self.subTest(metric=metric):
                self.assertIsNone(why)
                self.assertTrue(q['source'].startswith('per_clip_selected.csv'))
                self.assertAlmostEqual(q['diff'], point, places=12)
                self.assertEqual([q['lo'], q['hi']], [float(x) for x in np.quantile(fin, [0.025, 0.975])])
        q, why = AN.offline_quantity(off, 'nested', 'SUFFIX', 'GLOBAL', 0.05, 'utilization')
        self.assertIsNone(q)
        self.assertIn('train-selected', why)
        self.assertEqual(AN.offline_quantity(off, 'train', 'SUFFIX', 'GLOBAL', 0.05, 'utilization')[0], None)

    def test_real_offline_outputs(self):
        """The registered offline outputs (read only; executed before registration, Sec. 11.1 item 5): the primary
        row is the nested SUFFIX - GLOBAL continuity row of paired.csv at R_cond <= 5%, need fast, all plans, and its
        interval contains 0, so H4 offline is 'inconclusive'; every TRAIN row of paired.csv in the scope of
        per_clip_selected.csv is reproduced by the fallback (the same bootstrap)."""
        off = AN.load_offline()
        with open(ROOT / AN.OFFLINE_REL / 'paired.csv', newline='', encoding='utf-8') as f:
            ref = next(r for r in csv.DictReader(f) if (r['protocol'], r['a'], r['b'], r['subset'], r['need'],
                                                        r['alpha'], r['metric']) == ('nested', 'SUFFIX', 'GLOBAL',
                                                                                     'all', 'fast', '0.05',
                                                                                     'continuity'))
        doc, rows = AN.h4_offline(off)
        p = doc['primary']
        self.assertEqual((p['diff'], p['lo'], p['hi']), (float(ref['diff']), float(ref['diff_lo']),
                                                         float(ref['diff_hi'])))
        self.assertTrue(p['lo'] < 0 < p['hi'])
        self.assertEqual(doc['label'], 'inconclusive')
        self.assertIn('executed before registration', doc['status'])
        self.assertTrue(off['registered_location'])
        self.assertEqual((doc['per_clip_check']['compared'], doc['per_clip_check']['agree']), (30, True))
        self.assertTrue(all(r['source'] == 'paired.csv' for r in rows))


# ================================================== H5, overhead, manipulation checks, missing data (Secs. 9.5-9.8)

CA_CHECKS = ('deadline', 'margin', 'version', 'cancelled', 'not_gate_accepted')      # commit_audit.CHECKS


def run_audit(k, status='PASS', n=0, check='deadline'):
    """One run entry of the aggregator's commit audit (commit_audit.audit_run plus run_dir and jobs)."""
    if status == 'WITHHELD':
        return {'run_dir': f'runs/r{k}', 'jobs': [f'j{k}'], 'status': status, 'guard_note': 'withheld: x'}
    return {'run_dir': f'runs/r{k}', 'jobs': [f'j{k}'], 'status': status, 'n_violations': n, 'offers': 10,
            'accepted': 5, 'violations': {c: (n if c == check else 0) for c in CA_CHECKS},
            'examples': [{'check': check}] * min(n, 1), **({'error': 'log mismatch'} if status == 'ERROR' else {})}


def audit_doc(runs):
    """aggregate.json 'commit_audit' as aggregate_v4.commit_audit writes it."""
    audits = [a for a in runs if a['status'] != 'WITHHELD']
    totals = {c: sum(a['violations'][c] for a in audits) for c in CA_CHECKS}
    errors = sum(1 for a in audits if a['status'] == 'ERROR')
    withheld = len(runs) - len(audits)
    status = 'FAIL' if any(totals.values()) else 'ERROR' if errors else 'INCOMPLETE' if withheld else 'PASS'
    return {'status': status, 'runs_audited': len(audits), 'runs_withheld': withheld, 'runs_error': errors,
            'runs_matching_no_job': 0, 'runs_without_log': 0, 'offers': 10 * len(audits), 'accepted': 5 * len(audits),
            'events_only_commits': 0, 'margin_unrecorded': 0, 'log_mismatches': 0, 'violations': totals, 'runs': runs}


def s3_report(path, registered=True, n=100_000, violations=0, schema=AN.S3_SCHEMA):
    """A stress_bench S3 report (the fields analyze_v4.load_s3 reads)."""
    targets = {t: {'violations_total': violations if t == 'gate' else 0,
                   'violations': {'commit_at_or_after_deadline': violations if t == 'gate' else 0}}
               for t in AN.S3_TARGETS}
    Path(path).write_text(json.dumps({'schema': schema, 'test': 'S3', 'registered': registered,
                                      'label': 'registered S3 run' if registered else 'development run',
                                      'n_sequences': n, 'targets': targets, 'violations_total': violations,
                                      'pass': violations == 0, 'coverage_ok': True}), encoding='utf-8')
    return path


class H5AndChecks(Base):
    def phase_rows(self, phases=AN.H5_PHASES):
        return [run_row('fixed_deep', ROUTES[i], phase=p, job=f'syn_{p}') for i, p in enumerate(phases)]

    def test_h5_labels(self):
        """Sec. 9.5: supported only with a clean audit of every phase and the registered S3 at 0; any violation
        (audit or S3) contradicts, with the run listed; an unauditable run (ERROR) leaves condition 1 unmet
        (contradicted); withheld runs, a missing phase, a development or missing S3 report: undetermined."""
        ok, s3_ok = [run_audit(k) for k in range(3)], s3_report(self.tmp / 's3.json')
        cases = {
            'supported': ([*ok], self.phase_rows(), s3_ok, 'supported'),
            'violation': ([*ok, run_audit(9, 'FAIL', 2, 'margin')], self.phase_rows(), s3_ok, 'contradicted'),
            's3 violation': ([*ok], self.phase_rows(), s3_report(self.tmp / 's3v.json', violations=3),
                             'contradicted'),
            'unaudited': ([*ok, run_audit(9, 'ERROR')], self.phase_rows(), s3_ok, 'contradicted'),
            'withheld': ([*ok, run_audit(9, 'WITHHELD')], self.phase_rows(), s3_ok, 'undetermined'),
            'phase missing': ([*ok], self.phase_rows([p for p in AN.H5_PHASES if p != 'P2']), s3_ok,
                              'undetermined'),
            'development S3': ([*ok], self.phase_rows(), s3_report(self.tmp / 's3d.json', registered=False),
                               'undetermined'),
            'too few S3 sequences': ([*ok], self.phase_rows(), s3_report(self.tmp / 's3n.json', n=99_999),
                                     'undetermined'),
            'no S3': ([*ok], self.phase_rows(), None, 'undetermined'),
            'development S3 with violations': ([*ok], self.phase_rows(), s3_report(self.tmp / 's3dv.json',
                                                                                    registered=False, violations=2),
                                               'undetermined'),
            'violation without S3': ([*ok, run_audit(9, 'FAIL', 1)], self.phase_rows(), None, 'contradicted'),
        }
        for k, (runs, rows, s3, want) in enumerate(cases.values()):
            name = list(cases)[k]
            agg = AN.load_aggregation(write_agg(self.tmp / f'agg{k}', rows, extra={'commit_audit': audit_doc(runs)}))
            h = AN.h5([agg], None if s3 is None else AN.load_s3(s3))
            with self.subTest(case=name):
                self.assertEqual(h['label'], want)
                if name == 'violation':
                    self.assertEqual([(r['run_dir'], r['violations']['margin']) for r in h['violating_runs']],
                                     [('runs/r9', 2)])
                    self.assertEqual(h['commit_audit_violations'], 2)
                if name == 's3 violation':
                    self.assertEqual((h['s3_violations'], h['s3']['violations']['gate']),
                                     (3, {'commit_at_or_after_deadline': 3}))
                if name == 'unaudited':
                    self.assertEqual([(r['run_dir'], r['status']) for r in h['unaudited_runs']], [('runs/r9', 'ERROR')])
                if name == 'phase missing':
                    self.assertEqual(h['phases_missing'], ['P2'])
                if name == 'development S3 with violations':                      # reported, not counted
                    self.assertEqual((h['s3_violations'], h['s3']['violations_total']), (0, 2))
                if name == 'supported':
                    self.assertEqual((h['phases_missing'], h['undetermined_because']), ([], []))
        h = AN.h5([self.source(self.phase_rows())], AN.load_s3(s3_ok))
        self.assertEqual(h['label'], 'undetermined')
        self.assertIn('a bare CSV has no commit audit', h['undetermined_because'][0])
        with self.assertRaises(AN.AnalysisError):
            AN.load_s3(s3_report(self.tmp / 'bad.json', schema='other'))

    def test_real_development_s3_report(self):
        """The development S3 report of the stress bench (read only) is read, has 0 violations and is not the
        registered S3."""
        path = ROOT / 'outputs/framelease_v4/build/STRESS/s3_dev_report_v2.json'
        if not path.is_file():
            self.skipTest('no development S3 report')
        s3 = AN.load_s3(path)
        self.assertEqual((s3['registered'], s3['violations_total'], s3['n_sequences'], s3['targets']),
                         (False, 0, 100_000, ['gate', 'runtime']))

    def test_manipulation_overhead_and_missing(self):
        """Per condition: background load above the idle band on 3 runs, 1 charged-prefix flag, 1 configuration
        FAIL, 2 predicted-expiry flags, Q-network p99 above B_pi on 2 runs, one run with 3 budget overruns; Fixed Deep
        crashed on 3 routes: missing data lists those 3 routes for every contrast with Fixed Deep; the aggregator's
        documents are passed through."""
        manip = {'fast_prefix_check': 'PASS', 'charged_prefix_check': lambda i: 'FLAG' if i == 0 else 'PASS',
                 'bg_load_status': lambda i: 'above' if i < 3 else 'within',
                 'config_check': lambda i: 'FAIL' if i == 5 else 'PASS',
                 'prefix_p50_per_kappa_s': lambda i: 0.47 if i < 3 else 0.42,
                 'expiry_fallback_flag': lambda i: i in (7, 8), 'predicted_expiry_fallback': 0.0,
                 'observed_expiry_fallback': lambda i: 0.1 if i in (7, 8) else 0.0,
                 'qnet_s_p99': lambda i: 2e-4 if i in (1, 2) else 5e-5, 'decision_wall_s_p99': 1e-3,
                 'budget_overruns': lambda i: 3 if i == 4 else 0, 'shield_violations': 0, 'dmr': 0.1,
                 'shield_epochs': 10, 'outcome': 'ok'}
        rows = matrix({'fl_full': noisy(10, 95), 'fixed_deep': noisy(0, 96)}, arms=('fl_full', 'fixed_deep'),
                      extra={'fl_full': manip})
        for r in rows:
            if r['protocol_arm'] == 'fixed_deep' and r['route_id'] in ROUTES[:3]:
                r.update(analysis_use=False, missing_reason='agent_crashed', driving_score=None)
        extra = {'manipulation_checks': {'status': 'aggregator', 'marker': 1}, 'missing_reasons': {'agent_crashed': 3}}
        agg = AN.load_aggregation(write_agg(self.tmp / 'agg', rows, extra=extra))
        doc, _ = AN.analyze([agg], table=TABLE, settings=FAST)
        m = doc['manipulation']['by_condition']['fl_full_k1.0_s11']
        self.assertEqual((m['runs'], m['bg_load'], m['config'], m['charged_prefix_flag'], m['expiry_fallback_flags'],
                          m['fast_prefix_not_pass']),
                         (44, {'within': 41, 'above': 3, 'below': 0}, {'PASS': 43, 'FAIL': 1, 'UNCHECKED': 0}, 1, 2, 0))
        self.assertEqual(m['prefix_p50_per_kappa_s'], {'min': 0.42, 'median': 0.42, 'max': 0.47})
        self.assertEqual(doc['manipulation']['aggregations'][agg['path']], {'status': 'aggregator', 'marker': 1})
        ar = doc['manipulation']['analysed_runs']
        self.assertEqual(ar['runs'], 44 + 41)
        flags = [(f['job'], f['check']) for f in ar['flags'] if f['protocol_arm'] == 'fl_full']
        self.assertEqual(sorted(c for _, c in flags), sorted(['bg_load_above'] * 3 + ['charged_prefix', 'config_FAIL']
                                                             + ['predicted_expiry_fallback'] * 2))
        o = doc['overhead']['fl_full_k1.0_s11']
        self.assertEqual((o['qnet_s_p99']['runs'], o['qnet_s_p99']['runs_above_b_pi'], o['qnet_s_p99']['max']),
                         (44, 2, 2e-4))
        self.assertEqual((o['budget_overruns'], o['dmr']['median'], o['runs']), ({'total': 3, 'runs_with_any': 1},
                                                                                 0.1, 44))
        self.assertEqual(doc['overhead']['fixed_deep_k1.0_s11']['runs'], 41)
        md = {(x['table'], x['contrast'], x['metric']): x for x in doc['missing_data']['rows_incomplete']}
        h1 = md[('family_H1', 'fl_full_minus_fixed_deep_k1.0_s11_all', 'driving_score')]
        self.assertEqual((h1['n_expected'], h1['n_complete'], h1['n'], h1['n_dropped']), (44, 41, 41, 3))
        self.assertEqual(h1['reasons'], {'cell not used: B fixed_deep_k1.0_s11: missing (agent_crashed)': 3})
        self.assertEqual(doc['missing_data']['aggregations'][agg['path']], {'agent_crashed': 3})
        self.assertNotIn(('family_H1', 'fl_full_minus_fixed_deep_k1.0_s11_all', 'success'), md)


# ======================================================================= review fixes (build/R4/review/REVIEW.md)

class ReviewFixes(Base):
    def dev_freeze(self, rows):
        """A development analysis-freeze record of rows (interim_guard.freeze_record), cited with this script's sha256
        in Sec. 13 of a development PROTOCOL.md copy and its seal (interim_guard.load_freeze)."""
        recs = [{'job': r['job'], 'job_file': 'synthetic.jsonl', 'outcome': 'ok', 'selected_run': r['selected_run']}
                for r in rows]
        rec = self.tmp / 'analysis_freeze.json'
        rec.write_text(json.dumps(G.freeze_record(recs, {'synthetic.jsonl': 'b' * 64},
                                                  created='2026-11-14T00:00:00+0800'), sort_keys=True))
        prot, seal = self.tmp / 'PROTOCOL.md', self.tmp / 'SEAL.sha256'
        prot.write_text(f'# P\n\n## 13. Registration and amendments\nrecord {sha(rec)}\nanalysis code '
                        f'{sha(ROOT / AN.THIS_REL)}\n\n## 14. TRIMMED\n')
        seal.write_text(f'{sha(prot)}  {prot}\n')
        return G.load_freeze(rec, protocol=prot, seal=seal)

    def test_api_cannot_narrow_the_guard(self):
        """Must fix 1: analyze(test_routes=...) and analyze(registered=...) only ADD routes to the registered split
        (interim_guard.test_routes: 'a caller may add routes, never remove one'): rows on registered test routes are
        refused without a record whatever test_routes / registered say; under a development record registered=set()
        does not let a registered test route through summary_rows; a hand-made freeze dictionary is refused
        (aggregate_v4.checked_freeze); a caller's extra routes are still guarded."""
        reg = REGISTERED_TEST[:44]
        rows = matrix({'fl_full': 60.0, 'fixed_deep': 50.0}, arms=('fl_full', 'fixed_deep'), routes=reg)
        src = self.source(rows)
        for kw in ({}, {'test_routes': set()}, {'test_routes': set(), 'registered': set()},
                   {'test_routes': {'930000'}}, {'registered': {'930000'}}):
            with self.subTest(kw=kw):
                with self.assertRaises(AN.GuardRefused) as e:
                    AN.analyze([src], settings=FAST, offline=None, **kw)
                self.assertIn('no valid analysis-freeze record', str(e.exception))
        # an extra (synthetic) route a caller adds is guarded too
        with self.assertRaises(AN.GuardRefused):
            AN.analyze([self.source(matrix({'fl_full': 1.0}, arms=('fl_full',)), 's.csv')], table=TABLE,
                       settings=FAST, test_routes={ROUTES[0]})
        # a development record never summarizes a registered test route, even with registered=set()
        fz = self.dev_freeze(rows)
        note = f'{G.RELEASED}: by the analysis-freeze record {fz["sha256"][:12]} (DEVELOPMENT record)'
        released = [{**r, 'test_route': True, 'guard_note': note} for r in rows]
        agg = AN.load_aggregation(write_agg(self.tmp / 'agg', released, fz['sha256']))
        for kw in ({}, {'registered': set()}, {'registered': set(), 'test_routes': set()}):
            with self.subTest(development_record=kw):
                with self.assertRaises(AN.GuardRefused) as e:
                    AN.analyze([agg], settings=FAST, freeze=fz, **kw)
                self.assertIn('development analysis-freeze record over rows of the registered test routes',
                              str(e.exception))
        # a hand-made freeze dictionary is not a record
        forged = {'path': 'rec.json', 'sha256': fz['sha256'], 'frozen': 'now', 'trigger': 'all_final',
                  'protocol': 'P.md', 'protocol_sha256': 'a' * 64, 'seal': 'S.sha256', 'registered': True}
        with self.assertRaises(AN.GuardRefused):
            AN.analyze([agg], settings=FAST, freeze=forged)
        with self.assertRaises(TypeError):                              # the code citation is never the caller's
            AN.analyze([agg], settings=FAST, freeze=fz, code={'cited': True})
        # synthetic routes pass with test_routes=set(); the registered split is still the guard's set
        doc, _ = self.run_analysis(matrix({'fl_full': 1.0}, arms=('fl_full',)), test_routes=set())
        self.assertEqual((doc['interim_guard']['test_routes']['n_registered'],
                          doc['interim_guard']['test_routes']['n_extra'], doc['interim_guard']['test_input_rows']),
                         (44, 0, 0))

    def test_pooled_collisions_per_km_known(self):
        """Must fix 2 (Sec. 6.1): conditions.csv has, right after the route mean of collisions/km, the arm-level
        value sum of collisions / sum of km (0.001 km floor per route; a route without km is left out) with the
        route-cluster percentile bootstrap interval (routes resampled, ratio of sums; default_rng(20261110)); the
        review's example: 1 collision in 0.001 km and 0 in 1 km on 43 routes is 22.73 /km as a route mean and
        1 / 43.001 pooled."""
        coll = [1] + [0] * 43
        km = [0.001] + [1.0] * 43
        rows = [run_row('fl_full', rid, values={'collisions_total': c, 'km_driven': k,
                                                'collisions_per_km': c / max(k, 0.001)})
                for rid, c, k in zip(ROUTES, coll, km)]
        doc, tables = self.run_analysis(rows)
        cr = [r for r in tables['conditions.csv'] if r['condition'] == 'fl_full_k1.0_s11' and r['subset'] == 'all']
        i = next(j for j, r in enumerate(cr) if r['metric'] == 'collisions_per_km')
        mean_row, pooled = cr[i], cr[i + 1]
        self.assertEqual((mean_row['statistic'], pooled['metric'], pooled['statistic']),
                         ('route_mean', 'collisions_per_km_pooled', 'pooled_ratio'))
        self.assertAlmostEqual(mean_row['mean'], 1000 / 44, places=9)
        self.assertAlmostEqual(pooled['mean'], 1 / 43.001, places=12)
        self.assertEqual((pooled['n'], pooled['numerator_sum']), (44, 1.0))
        self.assertAlmostEqual(pooled['denominator_sum'], 43.001, places=12)
        self.assertEqual({r['statistic'] for r in tables['conditions.csv']}, {'route_mean', 'pooled_ratio'})
        # the interval by hand: resample routes, ratio of sums, 2.5% and 97.5% quantiles
        rng = np.random.default_rng(AN.BOOT_SEED)
        idx = rng.integers(0, 44, size=(FAST.n_boot, 44))
        c, k = np.array(coll, float), np.array(km, float)
        ratios = [c[ix].sum() / k[ix].sum() for ix in idx]
        self.assertEqual([pooled['ci95_lo'], pooled['ci95_hi']], [float(x) for x in np.quantile(ratios, [0.025,
                                                                                                         0.975])])
        j = [x for x in doc['collisions_per_km_pooled'] if (x['condition'], x['subset']) == ('fl_full_k1.0_s11', 'all')]
        self.assertEqual((j[0]['mean'], j[0]['ci95']), (pooled['mean'], [pooled['ci95_lo'], pooled['ci95_hi']]))
        # the km floor per route, a route without km left out, and an arm without rows
        rows[1].update(km_driven=0.0, collisions_total=2)
        rows[2].update(km_driven=None)
        _, tables = self.run_analysis(rows)
        p = next(r for r in tables['conditions.csv'] if (r['condition'], r['subset'], r['metric'])
                 == ('fl_full_k1.0_s11', 'all', 'collisions_per_km_pooled'))
        self.assertEqual((p['n'], p['numerator_sum']), (43, 3.0))
        self.assertAlmostEqual(p['denominator_sum'], 0.001 + 0.001 + 41.0, places=12)
        self.assertAlmostEqual(p['mean'], 3.0 / 41.002, places=12)
        e = next(r for r in tables['conditions.csv'] if (r['condition'], r['subset'], r['metric'])
                 == ('fixed_deep_k1.0_s11', 'all', 'collisions_per_km_pooled'))
        self.assertEqual((e['n'], e['mean'], e['ci95_lo'], e['numerator_sum']), (0, None, None, None))
        # the registered resample count, once, against the same procedure written out
        val, ci = AN.pooled_ratio(c, k)
        idx = np.random.default_rng(20261110).integers(0, 44, size=(10_000, 44))
        want = np.quantile(c[idx].sum(axis=1) / k[idx].sum(axis=1), [0.025, 0.975])
        self.assertEqual((val, ci), (c.sum() / k.sum(), [float(want[0]), float(want[1])]))
        with self.assertRaises(ValueError):
            AN.pooled_ratio([1.0], [0.0])

    def test_h5_no_log_runs(self):
        """Should fix 1 (Sec. 9.5: 'in every run of every phase'): a NO_LOG run (neither jobs.jsonl nor events.jsonl)
        is listed; it is unaudited (condition 1 not shown: contradicted) when the row that selects it records commits,
        records no commit count, or no row selects it; with 0 recorded commits it had nothing to audit."""
        rows = [run_row('fixed_deep', ROUTES[i], phase=p, job=f'syn_{p}', commits=5) for i, p in
                enumerate(AN.H5_PHASES)]
        s3 = AN.load_s3(s3_report(self.tmp / 's3.json'))
        sel = rows[0]['selected_run']
        cases = {'0 commits': (0, sel, 'supported', False), 'commits': (7, sel, 'contradicted', True),
                 'no commit count': (None, sel, 'contradicted', True),
                 'no selecting row': (0, 'runs/earlier_attempt', 'contradicted', True)}
        for k, (name, (commits, run_dir, want, unaudited)) in enumerate(cases.items()):
            rs = [dict(r) for r in rows]
            rs[0]['commits'] = commits
            runs = [run_audit(1), {**run_audit(2), 'run_dir': run_dir, 'status': 'NO_LOG', 'accepted': 0,
                                   'offers': 0}]
            agg = AN.load_aggregation(write_agg(self.tmp / f'agg{k}', rs, extra={'commit_audit': audit_doc(runs)}))
            h = AN.h5([agg], s3)
            with self.subTest(case=name):
                self.assertEqual(h['label'], want)
                self.assertEqual([(x['run_dir'], x['unaudited']) for x in h['no_log_runs']], [(run_dir, unaudited)])
                self.assertEqual([x['run_dir'] for x in h['unaudited_runs']], [run_dir] if unaudited else [])
                self.assertEqual(h['no_log_runs'][0]['selected_by'], None if run_dir != sel else 'syn_P1-0')
        families = self.run_analysis(matrix({'fl_full': 1.0}, arms=('fl_full',)))[0]['families']
        self.assertEqual(AN.decide(families, [], None, None, h)['H5']['no_log_runs'], 1)

    def test_development_reasons_and_location(self):
        """Should fix 3: 'registered' needs every registered input; each gap is a development reason: a record not
        checked against the job files of the test freeze, no or a development RL freeze, an undetermined RL benefit,
        H5 'undetermined', an output outside outputs/framelease_v4/analysis/final_<stamp>/ (out_location)."""
        base = ROOT / AN.ANALYSIS_REL
        for out, ok in ((base / 'final_20261120T000000', True), (base / 'final_20261120T000000' / 'analysis', True),
                        (base, False), (base / 'final_', False), (base / 'other' / 'final_x', False),
                        (self.tmp / 'final_x', False), (None, False)):
            with self.subTest(out=out):
                self.assertEqual(AN.out_location(out) is None, ok)
        full = {'sources': [{'kind': 'aggregation', 'path': 'agg'}], 'table': {'registered': True, 'source': 'split'},
                'settings': AN.REGISTERED, 'freeze': {'registered': True, 'required_job_files': {'p4.jsonl': 'a' * 64}},
                'p_both': {'path': 'rl.json', 'frozen': True, 'label': 'testable'},
                'offline': {'registered_location': True, 'path': AN.OFFLINE_REL},
                's3': {'registered': True, 'path': 's3.json'},
                'decisions': {'H2': {'rl_benefit': 'claimed'}, 'H5': {'label': 'supported'}},
                'out': base / 'final_20261120T000000' / 'analysis'}
        self.assertEqual(AN.development_reasons(**full), [])
        gaps = {'--required-job-files': {'freeze': {'registered': True, 'required_job_files': None}},
                'no RL freeze': {'p_both': None, 'decisions': {'H2': {'rl_benefit': 'undetermined: no RL freeze'},
                                                                'H5': {'label': 'supported'}}},
                'a development RL record': {'p_both': {'path': 'rl.json', 'frozen': False, 'label': 'testable'}},
                'H2 RL benefit undetermined': {'decisions': {'H2': {'rl_benefit': "undetermined: P_both label 'x'"},
                                                             'H5': {'label': 'supported'}}},
                "H5 'undetermined'": {'decisions': {'H2': {'rl_benefit': 'claimed'},
                                                    'H5': {'label': 'undetermined',
                                                           'undetermined_because': ['phase P2 missing']}}},
                'is not inside outputs/framelease_v4/analysis/final_<stamp>/': {'out': self.tmp / 'x'}}
        for text, change in gaps.items():
            with self.subTest(gap=text):
                dev = AN.development_reasons(**{**full, **change})
                self.assertEqual(len(dev), 1, dev)
                self.assertIn(text, dev[0])

    def test_overhead_panel_b(self):
        """Should fix 4 (Sec. 7.6 panel B): per condition the distribution of the per-run p50 / p99 values and the
        totals with their reasons."""
        vals = {'qnet_s_p50': lambda i: 1e-5 * (i + 1), 'decision_wall_s_p50': 2e-4, 'lease_wall_s_p50': 3e-4,
                'prefix_quantum_s_p50': 0.42, 'prefix_quantum_s_p99': 0.45, 'step_quantum_s_p50': 0.015,
                'step_quantum_s_p99': 0.02, 'switching_latency_s_p50': 1e-3, 'switching_latency_s_p99': 2e-3,
                'cancelled_gpu_share': lambda i: 0.1 if i < 22 else 0.3, 'cancelled_gpu_s': 1.5,
                'validation_s_p50': 1e-4, 'validation_s_p99': 5e-4, 'bypass_epochs': lambda i: 2 if i == 0 else 0,
                'bypass_by_reason': lambda i: json.dumps({'budget': 2}) if i == 0 else '{}',
                'gate_rejects': 3, 'gate_rejects_by_reason': json.dumps({'expired_before_commit': 2, 'version': 1}),
                'fallback_episodes': lambda i: 1 if i % 2 else 0}
        doc, _ = self.run_analysis(matrix({'fl_full': 50.0}, arms=('fl_full',), extra={'fl_full': vals}))
        o = doc['overhead']['fl_full_k1.0_s11']
        self.assertEqual(set(AN.OVERHEAD_DIST) - set(o), set())
        self.assertEqual((o['qnet_s_p50']['runs'], o['qnet_s_p50']['max']), (44, 44e-5))
        self.assertAlmostEqual(o['cancelled_gpu_share']['mean'], 0.2, places=12)
        self.assertEqual((o['prefix_quantum_s_p99']['median'], o['switching_latency_s_p99']['max']), (0.45, 2e-3))
        self.assertEqual(o['bypass_epochs'], {'total': 2, 'runs_with_any': 1, 'by_reason': {'budget': 2}})
        self.assertEqual(o['gate_rejects'], {'total': 132, 'runs_with_any': 44,
                                             'by_reason': {'expired_before_commit': 88, 'version': 44}})
        self.assertEqual(o['fallback_episodes'], {'total': 22, 'runs_with_any': 22})
        self.assertAlmostEqual(o['cancelled_gpu_s']['total'], 66.0, places=9)

    def test_out_dir_holding_an_aggregation_is_refused(self):
        """The aggregation of the analysis freeze occupies final_<stamp>/: an --out holding aggregate.json is refused
        (exit 1, even with --force), nothing is written there, not even a guard-log entry."""
        agg = write_agg(self.tmp / 'final_x', matrix({'fl_full': 1.0}, arms=('fl_full',)))
        before = {p.name: sha(p) for p in agg.iterdir()}
        for extra in ([], ['--force']):
            with self.subTest(extra=extra):
                rc = AN.main(['--agg', str(agg), '--out', str(agg), *extra], settings=FAST, table=TABLE)
                self.assertEqual(rc, 1)
                self.assertEqual({p.name: sha(p) for p in agg.iterdir()}, before)
        sub = agg / 'analysis'
        self.assertEqual(AN.main(['--agg', str(agg), '--out', str(sub)], settings=FAST, table=TABLE), 0)
        self.assertEqual({p.name: sha(p) for p in agg.iterdir() if p.is_file()}, before)
        with self.assertRaises(FileExistsError):
            AN.write_outputs(agg, {}, {n: [] for n in AN.TABLE_COLUMNS}, force=True)


if __name__ == '__main__':
    unittest.main()
