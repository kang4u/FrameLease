"""Tests of framelease_v4/analysis/verify_independent.py on synthetic run directories with known answers (PROTOCOL
Secs. 6.1, 8.4, 9.1, 9.2, 9.8, 9.11, 9.12; GAP_AUDIT Sec. 3.7 row R-7). CPU only; writes only under a temporary
directory; reads the registered route split and PROTOCOL.md (never modified).

  cd /home/kang/Desktop/DAC
  OMP_NUM_THREADS=1 nice -n 19 .conda-unidrive-linux/bin/python -I -B -m pytest -p no:cacheprovider -q \
      framelease_v4/analysis/tests/test_verify_independent.py
"""
import csv
import hashlib
import itertools
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v4.analysis import verify_independent as V  # noqa: E402

REGISTERED_TEST = [e['route_id'] for e in json.loads((ROOT / V.ROUTE_SPLIT_REL).read_text())['test']]
SYN_ROUTES = [str(940000 + i) for i in range(44)]
PIN = 'framelease_v4/__init__.py'
PIN_SHA = 'a' * 64
FAST = ['--n-boot', '2000', '--mc-flips', '2000']


def brute_p(d, tol=1e-9):
    t, n = abs(sum(d)), len(d)
    hits = sum(1 for s in itertools.product((1, -1), repeat=n)
               if abs(sum(a * b for a, b in zip(s, d))) >= t - tol * (1 + sum(abs(x) for x in d)))
    return hits / 2 ** n


def binom_p(k, n):
    """Two-sided sign-flip p of k differences +1 and n - k differences -1."""
    return sum(math.comb(n, j) for j in range(n + 1) if abs(2 * j - n) >= abs(2 * k - n)) / 2 ** n


class World:
    """A synthetic queue (jobs.d/, status.jsonl) and run directories under a temporary directory."""

    def __init__(self, base):
        self.base = Path(base)
        self.queue = self.base / 'queue'
        (self.queue / 'jobs.d').mkdir(parents=True)
        self.lines, self.status = [], []
        self.n = 0

    def job(self, arm, route, kappa=1.0, seed=11, phase='P4', block='ti_main', candidate=None, protocol_arm=None):
        out = self.base / 'runs_root' / arm
        jid = 'v4%s_%s_k%.1f_s%d_r%s' % (phase.lower().replace('-', ''), arm, kappa, seed, route)
        cmd = ['python', '-B', 'framelease_v4/arms/run_closed_loop_v4.py', '--arm', arm, '--kappa', str(kappa),
               '--seed', str(seed), '--route-id', str(route), '--output-dir', str(out)]
        line = {'id': jid, 'kind': 'closed_loop', 'tier': 3, 'cmd': cmd, 'wall_cap_s': 1500, 'arm_name': arm,
                'phase': phase, 'block': block, 'candidate': candidate or arm, 'kappa': kappa, 'seed': seed,
                'route_id': str(route), 'output_dir': str(out), 'require_sha256': {PIN: PIN_SHA}, 'envelope': None}
        if phase not in V.TRAINING_PHASES:
            line['protocol_arm'] = protocol_arm or arm
        self.lines.append(line)
        return line

    def run(self, line, ds=50.0, rc=100.0, status='Completed', infractions=None, length=200.0, recorded=None,
            config=None, outside=False):
        self.n += 1
        root = Path(line['output_dir']) if not outside else self.base / 'elsewhere'
        run_dir = root / 'runs' / ('run%05d' % self.n)
        (run_dir / 'metrics').mkdir(parents=True)
        (run_dir / 'raw' / 'source_v4').mkdir(parents=True)
        inf = {k: [] for k in ('collisions_layout', 'collisions_pedestrian', 'collisions_vehicle', 'red_light',
                               'stop_infraction', 'outside_route_lanes', 'min_speed_infractions',
                               'yield_emergency_vehicle_infractions', 'scenario_timeouts', 'route_dev',
                               'vehicle_blocked', 'route_timeout')}
        inf.update(infractions or {})
        km = max(length / 1000.0 * rc / 100.0, 0.001)
        rates = {k: round(len(v) / km, 3) for k, v in inf.items()}
        record = {'index': 0, 'route_id': 'RouteScenario_%s_rep0' % line['route_id'], 'status': status,
                  'infractions': inf, 'scores': {'score_route': rc, 'score_penalty': ds / rc if rc else 1.0,
                                                 'score_composed': ds},
                  'meta': {'route_length': length, 'duration_game': 10.0, 'duration_system': 20.0}}
        official = {'_checkpoint': {'global_record': {'infractions': rates}, 'progress': [1, 1], 'records': [record]},
                    'entry_status': 'Finished'}
        (run_dir / 'raw' / 'official_results.json').write_text(json.dumps(official))
        (run_dir / 'metrics' / 'result.json').write_text(json.dumps(
            {'route_records': 1, 'route_status': status, 'scores': record['scores'], 'timed_out': False}))
        conf = {'route': {'route_id': line['route_id']}, 'kappa': line['kappa'], 'seed': line['seed'],
                'v4_arm': line['arm_name'], 'envelope_sha256': None}
        conf.update(config or {})
        (run_dir / 'config.json').write_text(json.dumps(conf))
        rec = {PIN: PIN_SHA} if recorded is None else recorded
        (run_dir / 'raw' / 'source_v4' / 'hashes.json').write_text(json.dumps(rec))
        (run_dir / 'manifest.json').write_text(json.dumps({'identity': {'code': {}}, 'status': 'COMPLETED'}))
        return run_dir

    def end(self, line, run_dir, outcome='ok', final=True, attempt=1, counted=True):
        self.status.append({'event': 'start', 'id': line['id'], 'attempt': attempt})
        self.status.append({'event': 'end', 'id': line['id'], 'attempt': attempt, 'outcome': outcome, 'final': final,
                            'counted': counted, 'run_dir': None if run_dir is None else str(run_dir)})

    def full(self, line, **kw):
        self.end(line, self.run(line, **kw))

    def write(self, name='b11_ti_main.jsonl'):
        (self.queue / 'jobs.d' / name).write_text(''.join(json.dumps(x) + '\n' for x in self.lines))
        (self.queue / 'status.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in self.status))
        return self.queue


def syn_table(base, routes=SYN_ROUTES):
    path = Path(base) / 'route_table.json'
    path.write_text(json.dumps({'test': [{'route_id': r, 'index': i, 'length_m': 200.0}
                                         for i, r in enumerate(routes)]}))
    return path


def run_main(argv):
    return V.main([str(a) for a in argv])


def read_csv(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


class Statistics(unittest.TestCase):
    def test_enumeration_and_dp_equal_brute_force(self):
        import random
        rng = random.Random(7)
        for _ in range(20):
            n = rng.randint(1, 11)
            d = [round(rng.uniform(-40, 40), 3) for _ in range(n)]
            self.assertAlmostEqual(V.enumeration_sign_flip_p(d), brute_p(d), places=15)
            units = [rng.randint(-25, 25) for _ in range(n)]
            self.assertAlmostEqual(V.dp_sign_flip_p(units), brute_p(units, 0.0), places=15)

    def test_dp_known_answers_n44(self):
        self.assertEqual(V.dp_sign_flip_p([1] * 44), 2.0 / 2 ** 44)
        self.assertAlmostEqual(V.dp_sign_flip_p([1] * 30 + [-1] * 14), binom_p(30, 44), places=15)
        self.assertEqual(V.dp_sign_flip_p([0] * 44), 1.0)
        p, method, ties = V.sign_flip_p([0.25] * 44, 0.01)
        self.assertEqual((p, method, ties), (2.0 / 2 ** 44, 'exact_dp_rounded', 0))
        self.assertEqual(V.sign_flip_p([0.3] * 22, 0.01)[1], 'exact_enumeration')

    def test_grid_rounding_ties(self):
        d = [0.005, -0.005, 0.015, 10.005, 0.0149, 0.025, -0.025, 0.035]
        # judged: numpy.rint of the binary quotient (registered sign_flip_test): 0.5 -> 0, 2.5 -> 2,
        # 1000.5000000000001 -> 1001, 3.5000000000000004 -> 4
        self.assertEqual(V.grid_units(d, 0.01), ([0, 0, 2, 1001, 1, 2, -2, 4], 7))
        self.assertEqual(V.grid_units(d, 0.01, 'half_away')[0], [1, -1, 2, 1001, 1, 3, -3, 4])
        self.assertEqual(V.grid_units(d, 0.01, 'half_even')[0], [0, 0, 2, 1000, 1, 2, -2, 4])
        self.assertEqual(V.sign_flip_p([0.025] * 23, 0.01), (2.0 / 2 ** 23, 'exact_dp_rounded', 23))

    def test_dp_cap_marks_only_that_contrast(self):
        cap = V.DP_MAX_STATES
        try:
            V.DP_MAX_STATES = 1001
            p, method, _ = V.sign_flip_p([1.0] * 30, 0.01)      # 2 x 3000 + 1 states
            self.assertIsNone(p)
            self.assertTrue(method.startswith('not computable'))
            self.assertEqual(V.sign_flip_p([0.01] * 30, 0.01)[0], 2.0 / 2 ** 30)
        finally:
            V.DP_MAX_STATES = cap
        self.assertEqual(V.decision_label(1.0, None, 'higher', 30), 'not computable')

    def test_holm_and_labels(self):
        self.assertEqual(V.holm([0.01, 0.04, 0.03, None]), [0.04, 0.09, 0.09, None])   # counts as 1, no adjusted p
        self.assertEqual(V.holm([0.2, 0.01, 0.03, 0.04]), [0.2, 0.04, 0.09, 0.09])
        self.assertEqual(V.decision_label(1.0, 0.01, 'higher', 44), 'improves')
        self.assertEqual(V.decision_label(-1.0, 0.01, 'higher', 44), 'worse')
        self.assertEqual(V.decision_label(-1.0, 0.01, 'lower', 44), 'improves')
        self.assertEqual(V.decision_label(1.0, 0.05, 'higher', 44), 'inconclusive')
        self.assertEqual(V.decision_label(None, None, 'higher', 0), 'no data')

    def test_bootstrap_and_windows(self):
        reps = V.bootstrap_replicates([1.0] * 10, 500, 1)
        self.assertEqual(V.percentile_ci(reps), [1.0, 1.0])
        reps = V.bootstrap_replicates(list(range(44)), 10000, V.BOOT_SEED)
        lo, hi = V.percentile_ci(reps)
        win = V.quantile_window(reps, 0.025)
        self.assertLess(win[0], lo)
        self.assertGreater(win[1], lo)
        self.assertLess(lo, hi)
        pooled = V.bootstrap_replicates([1, 0, 2], 1000, 3, denominators=[0.5, 1.0, 0.5])
        self.assertTrue(((pooled >= 0) & (pooled <= 4)).all())
        p = 0.02
        self.assertAlmostEqual(V.mc_tolerance(p, 200000), 5 * math.sqrt(p * (1 - p) / 200000) + 2 / 200001)

    def test_window_width(self):
        reps = (V.np.arange(10000) + 0.5) / 10000.0             # uniform replicates: q(p) = p
        delta = 5 * math.sqrt(2 * 0.025 * 0.975 / 10000)
        lo, hi = V.quantile_window(reps, 0.025)
        self.assertAlmostEqual(lo, 0.025 - delta, places=4)
        self.assertAlmostEqual(hi, 0.025 + delta, places=4)
        comp = V.Comparisons()
        comp.window('t', 'k', 'f', 0.025, 0.025 + 0.5 * delta, reps, 0.025, 10000)
        comp.window('t', 'k', 'f', 0.025, 0.025 + 1.5 * delta, reps, 0.025, 10000)
        comp.window('t', 'k', 'f', None, None, None, 0.025, 10000)
        self.assertEqual([r['ok'] for r in comp.rows], [True, False, True])

    def test_mc_close_to_exact(self):
        d = [((i * 37) % 23 - 9) * 0.73 for i in range(44)]
        p_exact = V.sign_flip_p(d, 0.01)[0]
        p_mc = V.mc_sign_flip_p(d, 50000)
        self.assertLessEqual(abs(p_mc - p_exact), V.mc_tolerance(p_exact, 50000))


class RawRuns(unittest.TestCase):
    """Per-run values, run selection, code and configuration checks from synthetic run directories."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = World(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self):
        q = V.load_queue(self.w.write())
        self.assertEqual(q['problems'], [])
        return {r['id']: r for r in (V.read_run(j) for j in q['jobs'])}

    def test_values_known_answers(self):
        w = self.w
        a = w.job('fixed_deep', '940000')
        w.full(a, ds=60.0, rc=50.0, status='Failed - Agent got blocked', length=400.0,
               infractions={'collisions_vehicle': ['x'], 'collisions_layout': ['y', 'z'], 'red_light': ['r']})
        b = w.job('fast_only', '940000')
        w.full(b, ds=100.0, rc=100.0, status='Completed', infractions={'min_speed_infractions': ['m1', 'm2']})
        c = w.job('age_only', '940000')
        w.full(c, ds=80.0, rc=100.0, status='Perfect', infractions={'collisions_pedestrian': ['p'], 'route_dev': ['rd'],
                                                                       'vehicle_blocked': ['vb']})
        d = w.job('event_triggered', '940000')
        w.full(d, ds=0.0, rc=0.0, status='Failed - TickRuntime', length=150.0,
               infractions={'collisions_layout': ['k']})
        e = w.job('fl_original', '940000')
        w.full(e, infractions={'stop_infraction': ['s'], 'scenario_timeouts': ['t'], 'some_new_list': ['n']})
        rows = self.rows()
        ra = rows[a['id']]
        self.assertTrue(ra['usable'], ra['reason'])
        self.assertEqual((ra['driving_score'], ra['route_completion'], ra['success'], ra['collisions']),
                         (60.0, 50.0, 0.0, 3))
        self.assertAlmostEqual(ra['km_driven'], 0.2)
        self.assertAlmostEqual(ra['collisions_per_km'], 15.0)
        self.assertEqual((ra['infractions_penalized'], ra['route_ending_events']), (4, 0))   # 3 collisions + red light
        self.assertAlmostEqual(ra['infractions_per_km'], 20.0)
        rb = rows[b['id']]
        self.assertEqual(rb['success'], 1.0)                     # min-speed records do not count
        self.assertEqual((rb['infractions_penalized'], rb['infractions_per_km']), (0, 0.0))  # nor as infractions
        rc = rows[c['id']]
        self.assertEqual(rc['success'], 0.0)                     # a collision on a Perfect status
        self.assertEqual((rc['infractions_penalized'], rc['route_ending_events']), (1, 2))   # route-ending: separate
        self.assertAlmostEqual(rc['infractions_per_km'], 5.0)
        rd = rows[d['id']]
        self.assertEqual(rd['km_driven'], 0.001)                 # leaderboard floor
        self.assertAlmostEqual(rd['collisions_per_km'], 1000.0)
        self.assertAlmostEqual(rd['infractions_per_km'], 1000.0)
        re_ = rows[e['id']]
        self.assertEqual(re_['infractions_penalized'], 2)        # an unknown list is not counted, but noted
        self.assertEqual(re_['notes'], ['infraction lists outside Sec. 6.1 (not counted): some_new_list'])
        for r in rows.values():
            self.assertEqual((r['outcome_class'], r['valid_record']), ('ok', True))
            if r['id'] != e['id']:
                self.assertEqual(r['notes'], [])

    def test_final_record_selection(self):
        w = self.w
        retry = w.job('fixed_deep', '940001')
        first = w.run(retry, ds=1.0)
        w.end(retry, first, outcome='timeout', final=False, attempt=1)
        w.end(retry, None, outcome='interrupted', final=False, attempt=2, counted=False)
        second = w.run(retry, ds=42.0)
        w.end(retry, second, outcome='ok', final=True, attempt=3)
        lost = w.job('fast_only', '940001')
        w.end(lost, w.run(lost), outcome='timeout', final=False, attempt=1)
        w.end(lost, None, outcome='timeout', final=True, attempt=2)
        regen = w.job('fl_heuristic', '940001')                # --retry-failed: a later final record wins
        w.end(regen, None, outcome='timeout', final=True, attempt=2)
        regen_run = w.run(regen, ds=33.0)
        w.end(regen, regen_run, outcome='ok', final=True, attempt=3)
        pending = w.job('age_only', '940001')
        w.status.append({'event': 'start', 'id': pending['id'], 'attempt': 1})
        again = w.job('event_triggered', '940001')
        w.full(again)
        w.status.append({'event': 'start', 'id': again['id'], 'attempt': 2})
        crashed = w.job('fl_original', '940001')
        w.full(crashed, status='Failed - Simulation crashed')
        rows = self.rows()
        self.assertTrue(rows[retry['id']]['usable'])
        self.assertEqual(rows[retry['id']]['driving_score'], 42.0)
        self.assertEqual(rows[retry['id']]['run_dir'], V.rel(second))
        self.assertTrue(rows[lost['id']]['reason'].startswith('no_valid_record'))
        self.assertEqual((rows[regen['id']]['usable'], rows[regen['id']]['driving_score']), (True, 33.0))
        self.assertEqual(rows[pending['id']]['reason'], 'pending')
        self.assertTrue(rows[again['id']]['reason'].startswith('pending'))
        self.assertIn('execution failure', rows[crashed['id']]['reason'])
        classes = {k: (r['outcome_class'], r['final_run_dir']) for k, r in rows.items()}
        self.assertEqual(classes[retry['id']], ('ok', V.rel(second)))
        self.assertEqual(classes[lost['id']], ('not ok', None))
        self.assertEqual(classes[pending['id']], ('none', None))
        self.assertEqual(classes[again['id']], ('none', None))   # a new attempt after the final record
        self.assertEqual(classes[crashed['id']][0], 'not ok')    # runner ok, official execution failure
        self.assertEqual([V.outcome_class(x) for x in ('ok', 'result_with_warnings', 'timeout', 'infra_failure',
                                                       'launch_error', 'sim_failure', 'agent_crashed', 'cut',
                                                       'pending', None)],
                         ['ok', 'ok', 'not ok', 'not ok', 'not ok', 'not ok', 'not ok', 'none', 'none', 'none'])
        self.assertEqual(V.outcome_class('ok', '0'), 'not ok')

    def test_code_and_config_checks(self):
        w = self.w
        bad_pin = w.job('fixed_deep', '940002')
        w.full(bad_pin, recorded={PIN: 'b' * 64})
        unrecorded = w.job('fast_only', '940002')
        w.full(unrecorded, recorded={})
        bad_kappa = w.job('age_only', '940002')
        w.full(bad_kappa, config={'kappa': 1.5})
        outside = w.job('event_triggered', '940002')
        w.full(outside, outside=True)
        wrong_route = w.job('fl_original', '940002')
        w.full(wrong_route, config={'route': {'route_id': '940003'}})
        rows = self.rows()
        self.assertIn('code: framelease_v4/__init__.py: run bbbbbbbbbbbb', rows[bad_pin['id']]['reason'])
        self.assertIn('pinned but not recorded', rows[unrecorded['id']]['reason'])
        self.assertIn('config: kappa 1.5', rows[bad_kappa['id']]['reason'])
        self.assertIn('outside', rows[outside['id']]['reason'])
        self.assertIn('config: route 940003', rows[wrong_route['id']]['reason'])
        self.assertFalse(any(r['usable'] for r in rows.values()))

    def test_unreadable_files_are_reasons(self):
        w = self.w
        line = w.job('fixed_deep', '940005')
        run_dir = w.run(line)
        (run_dir / 'raw' / 'official_results.json').write_text('{truncated')
        w.end(line, run_dir)
        other = w.job('fast_only', '940005')
        run_dir = w.run(other)
        (run_dir / 'config.json').write_text('[1, 2')
        w.end(other, run_dir)
        rows = self.rows()
        self.assertFalse(rows[line['id']]['usable'])
        self.assertIn('unreadable official_results.json', rows[line['id']]['reason'])
        self.assertIn('unreadable config.json', rows[other['id']]['reason'])

    def test_consistency_notes(self):
        w = self.w
        line = w.job('fixed_deep', '940004')
        run_dir = w.run(line, ds=50.0, rc=100.0)
        res = json.loads((run_dir / 'metrics' / 'result.json').read_text())
        res['scores']['score_composed'] = 51.0
        (run_dir / 'metrics' / 'result.json').write_text(json.dumps(res))
        w.end(line, run_dir)
        row = self.rows()[line['id']]
        self.assertTrue(row['usable'])
        self.assertEqual(row['driving_score'], 50.0)            # the official record is the source
        self.assertTrue(any('score_composed 51.0' in n for n in row['notes']))


class H1Matrix(unittest.TestCase):
    """H1, S-coll, SR / RC rows and Table I on a synthetic 44-route matrix with known answers."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        w = World(base)
        for i, r in enumerate(SYN_ROUTES):
            ds = {'fixed_deep': 40.0, 'fl_full': 41.0, 'age_only': 41.0, 'event_triggered': 42.0,
                  'fast_only': 40.0 if i < 30 else 42.0, 'fl_original': 10.0, 'fl_heuristic': 20.0}
            for arm in V.TABLE_I_ARMS:
                if arm == 'fl_full' and i == 43:
                    continue                                   # pairwise-complete: n 43 for every contrast
                coll = {'collisions_vehicle': ['v']} if (arm == 'fixed_deep' and i % 2 == 0) else {}
                status = 'Completed' if (arm == 'fl_full' and i % 4 == 0) else 'Failed - Agent got blocked'
                w.full(w.job(arm, r), ds=ds[arm], rc=100.0 if status == 'Completed' else 80.0, status=status,
                       infractions=coll)
        cls.queue = w.write()
        cls.table = syn_table(base)
        cls.out = base / 'out'
        cls.code = run_main(['--queue', cls.queue, '--route-table', cls.table, '--out', cls.out])
        cls.doc = json.loads((cls.out / 'verification.json').read_text())
        cls.h1 = {c['other']: c for c in cls.doc['h1']['contrasts']}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_exit_and_status(self):
        self.assertEqual(self.code, 0)
        self.assertEqual(self.doc['verdict'], 'NOT_COMPARED')
        self.assertEqual(self.doc['status'], 'development')
        self.assertTrue(self.doc['settings']['registered'])
        self.assertEqual(self.doc['runs']['by_status'], {'usable': 307})

    def test_h1_known_answers(self):
        h = self.h1
        n = 43
        self.assertEqual({k: c['n'] for k, c in h.items()}, dict.fromkeys(V.H1_OTHERS, n))
        self.assertEqual(sorted(h['fixed_deep']['dropped_routes']), ['940043'])
        p_fd = 2.0 / 2 ** n                                     # +1.00 on every route
        p_fo = binom_p(30, n)                                   # +1 on 30 routes, -1 on 13
        self.assertEqual(h['fixed_deep']['p_two_sided'], p_fd)
        self.assertAlmostEqual(h['fast_only']['p_two_sided'], p_fo, places=15)
        self.assertEqual(h['age_only']['p_two_sided'], 1.0)    # no difference
        self.assertEqual(h['event_triggered']['p_two_sided'], p_fd)
        adj = V.holm([p_fd, p_fo, 1.0, p_fd])
        self.assertEqual([h[k]['p_adjusted'] for k in V.H1_OTHERS], adj)
        self.assertEqual(adj[1], 2 * p_fo)
        self.assertEqual([h[k]['label'] for k in V.H1_OTHERS], ['improves', 'improves', 'inconclusive', 'worse'])
        self.assertEqual(self.doc['h1']['findings'], {'finding_1': True, 'finding_2': False})
        self.assertAlmostEqual(h['fixed_deep']['mean'], 1.0)
        self.assertEqual(h['fixed_deep']['ci95'], [1.0, 1.0])
        self.assertAlmostEqual(h['fast_only']['mean'], (30 - 13) / 43)

    def test_s_coll_and_secondary(self):
        s = {c['other']: c for c in self.doc['s_coll']}
        # fixed_deep: 1 collision on even routes (km 0.16) -> 6.25 /km; fl_full 0
        self.assertAlmostEqual(s['fixed_deep']['mean'], -6.25 * 22 / 43)
        self.assertEqual(s['fixed_deep']['label'], 'improves')  # lower is better
        self.assertEqual(s['fast_only']['n'], 43)
        sec = {(c['metric'], c['other']): c for c in self.doc['secondary']}
        # fl_full succeeds on the 11 routes i % 4 == 0 (i <= 40), the others never
        self.assertAlmostEqual(sec[('success', 'fixed_deep')]['mean'], 11 / 43)
        self.assertAlmostEqual(sec[('success', 'fixed_deep')]['p_two_sided'], 2.0 / 2 ** 11, places=15)
        self.assertEqual(sec[('success', 'fixed_deep')]['p_adjusted'], sec[('success', 'fixed_deep')]['p_two_sided'])
        self.assertAlmostEqual(sec[('route_completion', 'fixed_deep')]['mean'], 20 * 11 / 43)
        # infractions/km = collisions/km here (no other infraction), lower is better, uncorrected
        inf = sec[('infractions_per_km', 'fixed_deep')]
        self.assertAlmostEqual(inf['mean'], -6.25 * 22 / 43)
        self.assertEqual((inf['p_two_sided'], inf['p_adjusted'], inf['label']),
                         (s['fixed_deep']['p_two_sided'], s['fixed_deep']['p_two_sided'], 'improves'))

    def test_table_i_cells(self):
        t = self.doc['table_i']
        self.assertEqual(sorted(t), sorted(V.cell_name(a, 1.0, 11) for a in V.TABLE_I_ARMS))
        fd = t['fixed_deep_k1.0_s11']['metrics']
        self.assertEqual(fd['driving_score']['n'], 44)
        self.assertEqual(fd['driving_score']['mean'], 40.0)
        self.assertEqual(fd['driving_score']['ci95'], [40.0, 40.0])
        self.assertEqual(fd['success']['mean'], 0.0)
        self.assertEqual(fd['route_completion']['mean'], 80.0)
        pooled = fd['collisions_per_km_pooled']
        self.assertEqual((pooled['numerator_sum'], pooled['n']), (22.0, 44))
        self.assertAlmostEqual(pooled['denominator_sum'], 44 * 0.16)
        self.assertAlmostEqual(pooled['mean'], 22 / (44 * 0.16))
        self.assertAlmostEqual(fd['infractions_per_km']['mean'], 6.25 * 22 / 44)
        ff = t['fl_full_k1.0_s11']
        self.assertEqual(ff['metrics']['driving_score']['n'], 43)
        self.assertEqual(ff['metrics']['infractions_per_km']['mean'], 0.0)
        self.assertEqual(self.doc['scope']['not_verified'], list(V.NOT_VERIFIED_COLUMNS))
        self.assertAlmostEqual(ff['metrics']['success']['mean'], 11 / 43)

    def test_outputs(self):
        sums = (self.out / 'SHA256SUMS').read_text().split('\n')
        for line in filter(None, sums):
            digest, name = line.split('  ')
            self.assertEqual(hashlib.sha256((self.out / name).read_bytes()).hexdigest(), digest)
        self.assertEqual(len(read_csv(self.out / 'runs.csv')), 307)
        self.assertEqual(len(read_csv(self.out / 'contrasts.csv')), 20)
        self.assertEqual(len(read_csv(self.out / 'differences.csv')), 0)
        log = [json.loads(x) for x in (self.out / V.GUARD_LOG).read_text().splitlines()]
        self.assertEqual([x['decision'] for x in log], ['granted'])
        self.assertEqual(run_main(['--queue', self.queue, '--route-table', self.table, '--out', self.out]), 2)

    def test_comparisons_round_trip_and_perturbation(self):
        """An analysis output built from this script's own numbers agrees; one perturbed number differs."""
        base = Path(self.tmp.name) / 'cmp'
        adir = base / 'analysis'
        adir.mkdir(parents=True)
        mine = read_csv(self.out / 'contrasts.csv')
        cols = ['family', 'role', 'contrast', 'metric', 'n_expected', 'n', 'mean', 'mean_a', 'mean_b', 'n_positive',
                'n_negative', 'n_zero', 'p_two_sided', 'p_method', 'p_adjusted', 'label', 'ci95_lo', 'ci95_hi',
                'ci90_lo', 'ci90_hi', 'p_mc', 'mc_flips', 'dropped_routes']

        def write(name, rows):
            with open(adir / name, 'w', newline='') as f:
                wr = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore', lineterminator='\n')
                wr.writeheader()
                for r in rows:
                    wr.writerow(dict(r, role='secondary' if r['family'] == 'secondary' else 'primary',
                                     mc_flips=200000))

        def build(perturb=None):
            rows = [dict(r) for r in mine]
            if perturb:
                perturb(rows)
            write('family_H1.csv', [r for r in rows if r['family'] == 'H1'])
            write('family_S-coll.csv', [r for r in rows if r['family'] == 'S-coll'])
            write('secondary.csv', [r for r in rows if r['family'] == 'secondary'])
            cond = []
            for r in read_csv(self.out / 'table_i.csv'):
                if r['table_i'] != 'True':
                    continue
                stat = 'pooled_ratio' if r['metric'] == 'collisions_per_km_pooled' else 'route_mean'
                cond.append(dict(r, condition=r['cell'], subset='all', statistic=stat,
                                 n_used=self.doc['table_i'][r['cell']]['metrics']['driving_score']['n']))
            ccols = ['condition', 'subset', 'metric', 'statistic', 'n_routes', 'n_used', 'n', 'mean', 'median', 'min',
                     'max', 'ci95_lo', 'ci95_hi', 'numerator_sum', 'denominator_sum']
            with open(adir / 'conditions.csv', 'w', newline='') as f:
                wr = csv.DictWriter(f, fieldnames=ccols, extrasaction='ignore', lineterminator='\n')
                wr.writeheader()
                wr.writerows(cond)
            h1 = [r for r in rows if r['family'] == 'H1']
            doc = {'schema': 'framelease_v4.analyze/1', 'status': 'development',
                   'settings': {'n_boot': 10000, 'boot_seed': 20261110},
                   'interim_guard': {'test_input_rows': 0}, 'route_table': {'registered': False},
                   'decisions': {'H1': {
                       'contrasts': [{'contrast': r['contrast'], 'n': int(r['n']), 'n_expected': int(r['n_expected']),
                                      'mean': float(r['mean']), 'p_two_sided': float(r['p_two_sided']),
                                      'p_adjusted': float(r['p_adjusted']), 'label': r['label'],
                                      'ci95': [float(r['ci95_lo']), float(r['ci95_hi'])]} for r in h1],
                       'finding_1': {'statement': 'may be stated'}, 'finding_2': {'statement': 'not stated'}}}}
            (adir / 'analysis.json').write_text(json.dumps(doc))
            pd = [{'table': 'family_' + c['family'], 'contrast': c['contrast'], 'metric': c['metric'],
                   'route_id': r['route_id'], 'value_a': r['value_a'], 'value_b': r['value_b'],
                   'difference': r['difference'], 'status': 'paired'}
                  for c in [{'family': x['family'], 'contrast': x['contrast'], 'metric': x['metric']} for x in mine]
                  for r in read_csv(self.out / 'paired.csv')
                  if r['contrast'] == c['contrast'] and r['metric'] == c['metric'] and c['family'] in ('H1', 'S-coll')]
            with open(adir / 'paired_differences.csv', 'w', newline='') as f:
                wr = csv.DictWriter(f, fieldnames=list(pd[0]), lineterminator='\n')
                wr.writeheader()
                wr.writerows(pd)

        build()
        out = base / 'v1'
        code = run_main(['--queue', self.queue, '--route-table', self.table, '--analysis', adir, '--out', out])
        diffs = read_csv(out / 'differences.csv')
        self.assertEqual((code, diffs), (0, []))
        doc = json.loads((out / 'verification.json').read_text())
        self.assertEqual(doc['verdict'], 'AGREE')
        self.assertGreater(doc['comparisons']['n'], 900)

        def nudge(rows):
            for r in rows:
                if r['family'] == 'H1' and r['contrast'].startswith('fl_full_minus_fast_only'):
                    r['p_two_sided'] = repr(float(r['p_two_sided']) + 1e-8)
                    r['ci95_hi'] = repr(float(r['ci95_hi']) + 0.5)
                    r['ci90_lo'] = repr(float(r['ci90_lo']) + 1e-6)     # inside the window: exact rule only
                    r['dropped_routes'] = ''

        build(nudge)
        out = base / 'v2'
        code = run_main(['--queue', self.queue, '--route-table', self.table, '--analysis', adir, '--out', out])
        diffs = {(r['target'], r['field']) for r in read_csv(out / 'differences.csv')}
        self.assertEqual(code, 1)
        self.assertEqual(diffs, {('analysis:family_H1.csv', 'p_two_sided'), ('analysis:family_H1.csv', 'ci95_hi'),
                                 ('analysis:family_H1.csv', 'ci90_lo'), ('analysis:family_H1.csv', 'dropped_routes'),
                                 ('analysis:analysis.json decisions.H1', 'p_two_sided'),
                                 ('analysis:analysis.json decisions.H1', 'ci95[1]')})
        rules = {r['rule'] for r in read_csv(out / 'comparisons.csv') if r['field'].startswith('ci')}
        self.assertEqual(rules, {'bootstrap_exact'})

        # without the registered seed on their side the window rule judges (here the bootstrap distributions are
        # discrete, so the windows are single atoms and the same endpoints differ)
        doc = json.loads((adir / 'analysis.json').read_text())
        doc['settings'] = {'n_boot': 10000}
        (adir / 'analysis.json').write_text(json.dumps(doc))
        out = base / 'v3'
        run_main(['--queue', self.queue, '--route-table', self.table, '--analysis', adir, '--out', out])
        rules = {r['rule'] for r in read_csv(out / 'comparisons.csv') if r['field'].startswith('ci')}
        self.assertEqual(rules, {'bootstrap_window'})
        diffs = {(r['target'], r['field']) for r in read_csv(out / 'differences.csv')}
        self.assertIn(('analysis:family_H1.csv', 'ci95_hi'), diffs)

        def drop(name, columns):
            rows = read_csv(adir / name)
            keep = [c for c in rows[0] if c not in columns]
            with open(adir / name, 'w', newline='') as f:
                wr = csv.DictWriter(f, fieldnames=keep, extrasaction='ignore', lineterminator='\n')
                wr.writeheader()
                wr.writerows(rows)

        # an absent column or file is a listed difference, never a vacuous AGREE
        for i, (name, columns, want) in enumerate((
                ('conditions.csv', ['mean'], ('analysis:conditions.csv', 'mean', 'column absent')),
                ('conditions.csv', ['median', 'numerator_sum'], ('analysis:conditions.csv', 'median', 'column absent')),
                ('family_H1.csv', ['ci95_lo', 'ci95_hi', 'ci90_lo', 'ci90_hi'],
                 ('analysis:family_H1.csv', 'ci90_hi', 'column absent')),
                ('family_S-coll.csv', ['dropped_routes'], ('analysis:family_S-coll.csv', 'dropped_routes',
                                                           'column absent')),
                ('secondary.csv', ['p_mc'], ('analysis:secondary.csv', 'p_mc', 'column absent')),
                ('paired_differences.csv', None, ('analysis:paired_differences.csv', 'file', 'file absent')))):
            with self.subTest(name=name, columns=columns):
                build()
                if columns is None:
                    (adir / name).unlink()
                else:
                    drop(name, columns)
                out = base / ('absent%d' % i)
                code = run_main(['--queue', self.queue, '--route-table', self.table, '--analysis', adir, '--out', out])
                diffs = read_csv(out / 'differences.csv')
                self.assertEqual(code, 1)
                self.assertIn(want, {(d['target'], d['field'], d['note']) for d in diffs})
                self.assertEqual({d['note'] for d in diffs}, {want[2]})

    def test_agg_round_trip(self):
        base = Path(self.tmp.name) / 'agg'
        base.mkdir()
        mine = read_csv(self.out / 'runs.csv')
        fields = {'driving_score': 'driving_score', 'route_completion': 'route_completion',
                  'infraction_penalty': 'infraction_penalty', 'success': 'success', 'collisions_total': 'collisions',
                  'infractions_penalized': 'infractions_penalized', 'route_ending_events': 'route_ending_events',
                  'km_driven': 'km_driven', 'collisions_per_km': 'collisions_per_km',
                  'infractions_per_km': 'infractions_per_km', 'route_length_m': 'route_length_m'}
        cols = ['job', 'outcome', 'valid_record', 'analysis_use', 'selected_run', 'route_id',
                'test_route'] + list(fields)

        def write(rows, columns=cols):
            with open(base / 'runs.csv', 'w', newline='') as f:
                wr = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore', lineterminator='\n')
                wr.writeheader()
                for r in rows:
                    wr.writerow(dict({'job': r['id'], 'outcome': r['final_outcome'], 'valid_record': 1,
                                      'analysis_use': r['usable'], 'selected_run': r['run_dir'],
                                      'route_id': r['route_id'], 'test_route': False},
                                     **{k: r[v] for k, v in fields.items()}))

        def summary(drop=()):
            with open(base / 'arm_summary.csv', 'w', newline='') as f:
                wr = csv.DictWriter(f, fieldnames=[c for c in ('protocol_arm', 'kappa', 'seed', 'phase', 'routes',
                                                               'driving_score', 'route_completion', 'success_rate',
                                                               'collisions_per_km_pooled') if c not in drop],
                                    extrasaction='ignore', lineterminator='\n')
                wr.writeheader()
                for arm in V.TABLE_I_ARMS:
                    m = self.doc['table_i'][V.cell_name(arm, 1.0, 11)]['metrics']
                    wr.writerow({'protocol_arm': arm, 'kappa': 1.0, 'seed': 11, 'phase': 'P4',
                                 'routes': m['driving_score']['n'], 'driving_score': m['driving_score']['mean'],
                                 'route_completion': m['route_completion']['mean'],
                                 'success_rate': m['success']['mean'],
                                 'collisions_per_km_pooled': m['collisions_per_km_pooled']['mean']})

        def run(name):
            code = run_main(['--queue', self.queue, '--route-table', self.table, '--agg', base, '--out', base / name]
                            + FAST)
            return code, [(d['key'], d['field'], d['note']) for d in read_csv(base / name / 'differences.csv')]

        write(mine)
        summary()
        self.assertEqual(run('v1'), (0, []))
        changed = [dict(r) for r in mine]
        changed[5]['driving_score'] = repr(float(changed[5]['driving_score']) + 1e-6)
        changed[6]['infractions_per_km'] = repr(float(changed[6]['infractions_per_km']) + 0.01)
        write(changed)
        code, diffs = run('v2')
        self.assertEqual(code, 1)
        self.assertEqual([d[:2] for d in diffs], [(mine[5]['id'], 'driving_score'),
                                                  (mine[6]['id'], 'infractions_per_km')])
        # outcome words are compared by class: aggregator 'sim_failure' for a run this script reads as ok differs
        changed = [dict(r) for r in mine]
        changed[7]['final_outcome'] = 'sim_failure'
        write(changed)
        code, diffs = run('v3')
        self.assertEqual((code, [d[:2] for d in diffs]), (1, [(mine[7]['id'], 'outcome class')]))
        # a missing arm_summary.csv, a missing column: listed; a runs.csv without a job column: input error
        write(mine, [c for c in cols if c != 'infractions_per_km'])
        summary(drop=('success_rate',))
        code, diffs = run('v4')
        self.assertEqual((code, diffs), (1, [('runs.csv', 'infractions_per_km', 'column absent'),
                                             ('arm_summary.csv', 'success_rate', 'column absent')]))
        write(mine)
        (base / 'arm_summary.csv').unlink()
        code, diffs = run('v5')
        self.assertEqual((code, diffs), (1, [('arm_summary.csv', 'file', 'file absent')]))
        write(mine, [c for c in cols if c != 'job'])
        self.assertEqual(run_main(['--queue', self.queue, '--route-table', self.table, '--agg', base, '--out',
                                   base / 'v6'] + FAST), 2)


class Guard(unittest.TestCase):
    """Sec. 9.11: test-route input needs a valid analysis-freeze record; nothing is read or written before. The grant
    path runs on synthetic test routes (--route-table) under the test options --protocol / --seal, which never
    release a registered test route."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.table = syn_table(self.base)
        self.split_sha = hashlib.sha256(self.table.read_bytes()).hexdigest()
        self.route = SYN_ROUTES[0]
        self.queue, self.line, self.run_dir = self.world(self.base / 'w', self.route)
        self.job_file = self.queue / 'jobs.d' / 'b11_ti_main.jsonl'

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def world(base, route, outcome='ok', with_run=True, runner_run=True):
        w = World(base)
        line = w.job('fl_full', route)
        run_dir = w.run(line, ds=70.0) if with_run else None
        w.end(line, run_dir if runner_run else None, outcome=outcome)
        return w.write(), line, run_dir

    def record(self, job_file=None, line=None, run_dir=None, outcome='ok', **changes):
        job_file, line = job_file or self.job_file, line or self.line
        run_dir = self.run_dir if run_dir is None else run_dir
        rec = {'schema': V.FREEZE_SCHEMA, 'frozen': '2026-12-01T00:00:00+0800', 'trigger': 'all_final',
               'cut_amendment': None, 'route_split_sha256': self.split_sha, 'analysis_code': {},
               'job_files': {str(job_file): hashlib.sha256(job_file.read_bytes()).hexdigest()},
               'jobs': {line['id']: {'job_file': str(job_file), 'outcome': outcome, 'run_dir': str(run_dir)}}}
        rec.update(changes)
        return self.save(rec)

    def save(self, rec, name='freeze.json'):
        path = self.base / name
        path.write_text(json.dumps(rec, sort_keys=True))
        return path

    def protocol(self, cite=None, seal_ok=True):
        """A PROTOCOL.md copy with the record's sha256 cited in Sec. 13 (before '## 14.') and its seal."""
        text = (ROOT / V.PROTOCOL_REL).read_text(encoding='utf-8')
        if cite:
            text = text.replace('\n## 14.', '\n**Analysis freeze (test).** `freeze.json` (sha256 `%s`).\n\n## 14.'
                                % cite, 1)
        proto = self.base / 'PROTOCOL.md'
        proto.write_text(text, encoding='utf-8')
        digest = hashlib.sha256(proto.read_bytes()).hexdigest()
        seal = self.base / 'SEAL.sha256'
        seal.write_text('%s  framelease_v4/PROTOCOL.md\n' % (digest if seal_ok else '0' * 64))
        return proto, seal

    def cited(self, rec):
        proto, seal = self.protocol(cite=hashlib.sha256(rec.read_bytes()).hexdigest())
        return ['--analysis-freeze', rec, '--protocol', proto, '--seal', seal]

    def run_cli(self, *extra, out='out', queue=None):
        return run_main(['--queue', queue or self.queue, '--route-table', self.table, '--out', self.base / out]
                        + FAST + [str(x) for x in extra])

    def log(self, out='out'):
        return [json.loads(x) for x in (self.base / out / V.GUARD_LOG).read_text().splitlines()]

    def test_refused_without_record_and_before_reading(self):
        for p in self.run_dir.rglob('*'):                     # results unreadable: the refusal must not need them
            if p.is_file():
                p.write_text('not json')
        proto, seal = self.protocol()
        self.assertEqual(self.run_cli('--protocol', proto, '--seal', seal), 4)
        self.assertFalse((self.base / 'out' / 'verification.json').exists())
        entry = self.log()[-1]
        self.assertEqual(entry['decision'], 'refused')
        self.assertIn('no analysis-freeze record', entry['reason'])
        # a registered test route with the registered PROTOCOL.md: refused the same way
        queue, _, _ = self.world(self.base / 'reg', REGISTERED_TEST[0])
        self.assertEqual(run_main(['--queue', queue, '--out', self.base / 'o_reg'] + FAST), 4)
        self.assertIn('no analysis-freeze record', self.log('o_reg')[-1]['reason'])
        # without the test options the synthetic routes are development data (not guarded)
        self.assertEqual(self.run_cli(out='o_dev'), 0)

    def test_valid_record_grants(self):
        code = self.run_cli(*self.cited(self.record()))
        self.assertEqual(code, 0)
        doc = json.loads((self.base / 'out' / 'verification.json').read_text())
        self.assertEqual(doc['interim_guard']['decision'], 'granted (valid analysis-freeze record)')
        self.assertEqual(doc['runs']['by_status'], {'usable': 1})
        self.assertEqual(self.log()[-1]['decision'], 'granted')
        self.assertEqual(doc['status'], 'development')
        self.assertTrue(any('test options --protocol / --seal' in r for r in doc['development_reasons']))
        rows = read_csv(self.base / 'out' / 'comparisons.csv')
        self.assertEqual([(r['target'], r['field'], r['ok']) for r in rows],
                         [('freeze record', 'run_dir', 'True'), ('freeze record', 'outcome class', 'True')])

    def test_registered_test_route_never_released_under_test_options(self):
        queue, line, run_dir = self.world(self.base / 'reg', REGISTERED_TEST[0])
        job_file = queue / 'jobs.d' / 'b11_ti_main.jsonl'
        registered_sha = hashlib.sha256((ROOT / V.ROUTE_SPLIT_REL).read_bytes()).hexdigest()
        rec = self.record(job_file=job_file, line=line, run_dir=run_dir, route_split_sha256=registered_sha)
        for i, table in enumerate(([], ['--route-table', self.table])):
            out = self.base / ('forged%d' % i)
            code = run_main(['--queue', queue, '--out', out] + table + self.cited(rec))
            self.assertEqual(code, 4)
            self.assertIn('never released', self.log(out)[-1]['reason'])
            self.assertEqual(sorted(p.name for p in out.iterdir()), [V.GUARD_LOG])

    def test_invalid_records_refused(self):
        other = self.base / 'other'
        cases = {
            'not cited': ({}, False, True),
            'unsealed protocol': ({}, True, False),
            'schema': ({'schema': 'framelease_v4.aggregate/1'}, True, True),
            'route split': ({'route_split_sha256': 'f' * 64}, True, True),
            'trigger': ({'trigger': 'cut'}, True, True),
            'job missing': ({'jobs': {}}, True, True),
            'run dir': ({'run_dir': other}, True, True),
            'job file sha': ({'job_files': {str(self.job_file): '0' * 64}}, True, True),
        }
        for i, (name, (changes, cite, seal_ok)) in enumerate(cases.items()):
            with self.subTest(name):
                rec = self.record(**changes)
                proto, seal = self.protocol(cite=hashlib.sha256(rec.read_bytes()).hexdigest() if cite else None,
                                            seal_ok=seal_ok)
                out = 'out%d' % i
                code = self.run_cli('--analysis-freeze', rec, '--protocol', proto, '--seal', seal, out=out)
                self.assertEqual(code, 4)
                self.assertEqual(self.log(out)[-1]['decision'], 'refused')
                self.assertFalse((self.base / out / 'verification.json').exists())

    def test_record_run_without_runner_record_is_a_difference(self):
        w = World(self.base / 'w2')
        line = w.job('fl_full', self.route)
        run_dir = w.run(line, ds=70.0)                          # a run without any runner record
        queue = w.write()
        job_file = queue / 'jobs.d' / 'b11_ti_main.jsonl'
        rec = self.record(job_file=job_file, line=line, run_dir=run_dir)
        code = self.run_cli(*self.cited(rec), out='o5', queue=queue)
        self.assertEqual(code, 1)
        diffs = read_csv(self.base / 'o5' / 'differences.csv')
        self.assertEqual([(d['target'], d['field']) for d in diffs],
                         [('freeze record', 'run_dir'), ('freeze record', 'outcome class')])
        self.assertTrue(all('no final record' in d['note'] for d in diffs))
        rows = read_csv(self.base / 'o5' / 'runs.csv')
        self.assertEqual((rows[0]['usable'], rows[0]['reason']), ('False', 'pending'))

    def test_freeze_record_vocabulary(self):
        """Records written by interim_guard.freeze_record (the aggregator's select-stage words) for runner outcomes
        result_with_warnings, timeout and infra_failure: granted; outcome classes agree; a class disagreement on a
        released run is a listed difference, not a refusal."""
        from framelease_v4.analysis import interim_guard as IG     # the record writer (black box)
        # (runner outcome, a run exists, the runner names it, record word, record names the run, exit, status)
        cases = (('result_with_warnings', True, True, 'ok', True, 0, 'usable'),
                 ('timeout', True, True, 'sim_failure', True, 0, 'no_valid_record'),
                 ('infra_failure', False, False, 'sim_failure', True, 0, 'no_valid_record'),
                 ('infra_failure', True, False, 'sim_failure', True, 1, 'no_valid_record'),
                 ('timeout', True, True, 'sim_failure', False, 1, 'no_valid_record'),    # unread run: listed
                 ('ok', True, True, 'sim_failure', True, 1, 'usable'))
        for i, (runner, with_run, runner_run, word, named, want, status) in enumerate(cases):
            with self.subTest(runner=runner, record=word, runner_run=runner_run, named=named):
                queue, line, run_dir = self.world(self.base / ('v%d' % i), self.route, runner, with_run, runner_run)
                jf = queue / 'jobs.d' / 'b11_ti_main.jsonl'
                rows = [{'job': line['id'], 'job_file': str(jf), 'outcome': word,
                         'selected_run': str(run_dir) if run_dir and named else None, 'missing_reason': None}]
                rec = self.save(IG.freeze_record(rows, {str(jf): hashlib.sha256(jf.read_bytes()).hexdigest()},
                                                 created='2026-12-01T00:00:00+0800', split_sha256=self.split_sha),
                                'freeze_%d.json' % i)
                out = 'voc%d' % i
                code = self.run_cli(*self.cited(rec), out=out, queue=queue)
                self.assertEqual(code, want)
                self.assertEqual(self.log(out)[-1]['decision'], 'granted')
                doc = json.loads((self.base / out / 'verification.json').read_text())
                self.assertEqual(list(doc['runs']['by_status']), [status])
                diffs = read_csv(self.base / out / 'differences.csv')
                if want:
                    self.assertEqual({d['target'] for d in diffs}, {'freeze record'})
                else:
                    self.assertEqual(diffs, [])

    def test_csv_and_analysis_inputs_guarded(self):
        runs = self.base / 'runs.csv'
        runs.write_text('job,route_id,test_route,outcome,valid_record,code_check,driving_score\n'
                        'x,%s,False,ok,1,PASS,1.0\n' % REGISTERED_TEST[0])
        self.assertEqual(run_main(['--runs', runs, '--out', self.base / 'o1'] + FAST), 4)
        runs.write_text('job,route_id,test_route,outcome,valid_record,code_check,driving_score\n'
                        'x,940000,True,ok,1,PASS,1.0\n')
        self.assertEqual(run_main(['--runs', runs, '--out', self.base / 'o2'] + FAST), 4)
        runs.write_text('job,route_id,test_route,outcome,valid_record,code_check,driving_score\n'
                        'x,940000,False,ok,1,PASS,1.0\n')
        adir = self.base / 'analysis'
        adir.mkdir()
        (adir / 'analysis.json').write_text(json.dumps({'status': 'final', 'interim_guard': {'test_input_rows': 3}}))
        self.assertEqual(run_main(['--runs', runs, '--analysis', adir, '--out', self.base / 'o3'] + FAST), 4)
        self.assertEqual(run_main(['--runs', runs, '--out', self.base / 'o4'] + FAST), 0)
        proto, seal = self.protocol()                            # synthetic test route under the test options
        self.assertEqual(run_main(['--runs', runs, '--route-table', self.table, '--protocol', proto, '--seal', seal,
                                   '--out', self.base / 'o5'] + FAST), 4)
        runs.write_text('job,test_route,outcome\nx,False,ok\n')  # no route_id column: cannot be guarded
        self.assertEqual(run_main(['--runs', runs, '--out', self.base / 'o6'] + FAST), 2)
        # an unexpected failure (here a missing file) exits 2, never the DIFFER code 1
        self.assertEqual(run_main(['--runs', self.base / 'missing.csv', '--out', self.base / 'o7'] + FAST), 2)

    def test_protected_out_dir(self):
        target = ROOT / 'outputs/framelease_v4/queue_p1/r7_should_not_exist'
        self.assertEqual(run_main(['--queue', self.queue, '--out', target] + FAST), 2)
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
