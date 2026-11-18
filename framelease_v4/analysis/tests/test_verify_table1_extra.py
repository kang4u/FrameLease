"""Tests of framelease_v4/analysis/verify_table1_extra.py (synthetic run directories with known answers; the
read-only smoke run directories of P1-0, training route 18305, when present)."""

import ast
import csv
import glob
import gzip
import hashlib
import importlib.util
import json
import math
import os
import shutil
import tempfile
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SCRIPT = os.path.join(ROOT, 'framelease_v4', 'analysis', 'verify_table1_extra.py')

_spec = importlib.util.spec_from_file_location('verify_table1_extra_under_test', SCRIPT)
VT = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(VT)

DT = 0.05
SCRATCH = '/tmp/R7B' if os.path.isdir('/tmp/R7B') else None


def write_jsonl(path, rows):
    with open(path, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')


def write_csv(path, rows, fields=None):
    fields = fields or sorted(set(k for r in rows for k in r))
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        w.writeheader()
        for r in rows:
            w.writerow({k: ('' if r.get(k) is None else (json.dumps(r[k]) if isinstance(r.get(k), dict)
                                                       else repr(r[k]) if isinstance(r.get(k), float) else r[k]))
                        for k in fields})


# Two commits A (job 1 at depth 2: capture 0.05, commit 0.12, deadline 0.375) and B (job 2 at depth 1: capture 0.50,
# commit 0.62, deadline 0.775) on 20 ticks t = 0.05 k, k = 1..20 (lease arm): none at k 1-2, A valid at k 3-7,
# A expired at k 8-12, B valid at k 13-15, B expired at k 16-20.
COMMITS = [
    {'job_id': 1, 'depth': 2, 'commit_s': 0.12, 'capture_s': 0.05, 'deadline_s': 0.375},
    {'job_id': 2, 'depth': 1, 'commit_s': 0.62, 'capture_s': 0.50, 'deadline_s': 0.775},
]
# Completed jobs: (prefix launch, cost, prefix decision overhead), [(step launch, cost, decision overhead)].
JOBS = [
    {'job_id': 1, 'prefix': (0.05, 0.05, 0.001), 'steps': [(0.101, 0.010, 0.001), (0.112, 0.010, 0.001)]},
    {'job_id': 2, 'prefix': (0.45, 0.10, 0.002), 'steps': [(0.552, 0.020, 0.003)]},
]
# Job 3 runs at the end: prefix [0.70, 0.90]; ticks k 19 / 20 show step quanta (depth 2 until 0.96, depth 3 until 1.10).
INFLIGHT = {'job_id': 3, 'prefix_end_s': 0.90, 'prefix_timeline_s': 0.20}
GPU_TICKS = {19: {'job_id': 3, 'phase': 'step', 'depth': 2, 'busy_until_s': 0.96},
             20: {'job_id': 3, 'phase': 'step', 'depth': 3, 'busy_until_s': 1.10}}
# Union in [0.05, 1.05]: 0.07 + 0.12 + 0.20 + 0.15 = 0.54 (upper). Boundaries inside the in-flight interval: 1 prefix
# (median 0.0015, max 0.002) + 2 step (median 0.001, max 0.003): point 0.5365, lower 0.532.
GPU_UPPER, GPU_POINT, GPU_LOWER = 0.54, 0.5365, 0.532
# Shield decision rows: |A_feas| 2, 2, 1, 0 at depth >= 1 (P_both 0.5); one depth-0 shield row and one row without
# shield.
DECISIONS = [
    {'kind': 'decision', 'depth': 1, 'shield': {'t': 0.1}, 'feasible': ['REFINE', 'REFRESH'], 'p_both': True},
    {'kind': 'decision', 'depth': 2, 'shield': {'t': 0.2}, 'feasible': ['REFINE', 'REFRESH'], 'p_both': True},
    {'kind': 'decision', 'depth': 3, 'shield': {'t': 0.3}, 'feasible': ['REFRESH'], 'p_both': False},
    {'kind': 'decision', 'depth': 4, 'shield': {'t': 0.4}, 'feasible': [], 'p_both': False},
    {'kind': 'decision', 'depth': 0, 'shield': {'t': 0.0}, 'feasible': ['REFRESH'], 'p_both': False},
    {'kind': 'decision', 'depth': 1, 'shield': None, 'feasible': None, 'p_both': None},
]


def straight(v, lateral=0.0):
    """Plan waypoints (capture LiDAR frame: x right, y forward) at forward speed v m/s, drifting right to lateral m."""
    return [[lateral * i / 6.0, v * 0.5 * i] for i in range(1, 7)]


# Step plans (job_id, depth). The hero stands at the CARLA origin (yaw 0); vehicle 7 (half length 2.00 m) stands with
# its centre 6.65 m ahead. The ego box (the documented Bench2Drive hero box of the lease: half length 2.4462 m, centre
# 0.3837 m ahead of the LiDAR, which lies 0.39 m behind the hero origin, so its front is 2.4399 m ahead of the origin)
# travels 4 tau along plan A, so the gap is 6.65 - 2.00 - 2.4399 - 4 tau = 2.2101 - 4 tau: d_safe at V = 0.427525
# (first conflicting sample tau 0.45), V_suf = 0. Plan B moves 0.06 m: clear on its known samples, censored after the
# last row (t 1.05 > the last tick: no bound).
PLANS = {(1, 1): straight(2.0), (1, 2): straight(4.0), (2, 1): straight(0.02)}
HERO = {'id': 1, 'ty': 'vehicle.lincoln.mkz_2020', 'ext': [245, 92, 75], 'off': [0, 0]}
CAR = {'c': 7, 'k': 'vehicle', 'ty': 'vehicle.tesla.model3', 'ext': [200, 90, 75], 'off': [0, 0], 'role': 'scenario',
       't': 0}
WALKER = {'c': 8, 'k': 'walker', 'ty': 'walker.pedestrian.0001', 'ext': [20, 20, 90], 'off': [0, 0], 'role': '',
          't': 0}
PROP = {'c': 9, 'k': 'static', 'ty': 'static.prop.barrel', 'ext': [300, 300, 50], 'off': [0, 0], 'role': '', 't': 0,
        'p': [450, 0, 0]}


def actor_row(k, t, ego=(0, 0, 0), actors=((7, 665, 0, 0),)):
    """An actor-log tick row: hero CARLA pose ego (cm, cm, centi-degrees); actors (id, x cm, y cm, yaw centi-degrees)
    in absolute CARLA coordinates (written relative to the hero as the logger does); actors None = ego-only row."""
    row = {'t': k - 1, 's': round(t, 4), 'e': [ego[0], ego[1], ego[2], 0, 0], 'g': None}
    if actors is None:
        row.update(n=None, a=None)
    else:
        row.update(n=len(actors), a=[[aid, x - ego[0], y - ego[1], yaw, 0, 0] for aid, x, y, yaw in actors])
    return row


def write_actor_log(log_dir, rows, header=None, catalog=(CAR, WALKER, PROP), member=7, truncate=False):
    """actors.jsonl.gz as the logger writes it: one gzip member per member lines; truncate cuts the last member."""
    lines = [json.dumps({'h': VT.ACTOR_SCHEMA, 'frame': 'carla_world_left_handed', 'hero': header or HERO})]
    lines += [json.dumps(c) for c in catalog] + [json.dumps(r) for r in rows]
    with open(os.path.join(log_dir, VT.ACTOR_LOG), 'wb') as f:
        for i in range(0, len(lines), member):
            data = gzip.compress(('\n'.join(lines[i:i + member]) + '\n').encode('utf-8'))
            if truncate and i + member >= len(lines):
                data = data[:len(data) // 2]
            f.write(data)


# Known answers of the lease-arm run (fl_heuristic).
LEASE_EXPECTED = {
    'ticks': 20, 'first_commit_s': 0.12, 'ticks_after_first_commit': 18, 'missed_ticks_after_first_commit': 10,
    'dmr': 10 / 18, 'dmr_all_ticks': 12 / 20, 'expired_ratio_after_first_commit': 10 / 18,
    'expired_ratio_all_ticks': 10 / 20, 'fallback_ticks': 12, 'fallback_ratio': 0.6, 'fallback_episodes': 3,
    'fallback_by_reason': {'no_plan': 2, 'expired': 10}, 'track_ticks': 8, 'action_age_n': 8,
    'action_age_p50_s': 0.20, 'action_age_p95_s': 0.2825, 'action_age_mean_s': 0.20, 'decision_rows': 6,
    'shield_epochs': 4, 'choice_epochs': 2, 'p_both': 0.5, 'gpu_usage': GPU_POINT, 'gpu_busy_s': GPU_POINT,
    'cuda_s_per_s': GPU_POINT, 'sim_span_s': 1.0, 'commits': 2,
    # Sec. 6.3: A is a conflict plan (V 0.4275, V_suf 0, H 0.325: a miss) tracked at k 3-7; B is log-censored.
    'validity_available': True, 'committed_plans': 2, 'conflict_plans': 1, 'misses': 1, 'v0_plans': 0,
    'log_censored_plans': 1, 'plans_unevaluable': 0, 'r_cond': 1.0, 'r_cond_excl_v0': 1.0, 'eir_invalid_ticks': 5,
    'eir': 5 / 8, 'eir_unevaluable_ticks': 0,
}


def _valid(arm, inc, t, max_age):
    if inc is None:
        return False
    if arm in VT.AGE_RULE_ARMS:
        return t - inc['capture_s'] < max_age
    return t < inc['deadline_s']


def make_run(root, name, arm='fl_heuristic', route='990001', kappa=1.0, max_age=2.5, n_ticks=20, commits=COMMITS,
             jobs=JOBS, inflight=INFLIGHT, gpu_ticks=GPU_TICKS, decisions=DECISIONS, summary=None, drop=(),
             tick_patch=None, plans=PLANS, actor=actor_row, actor_log=None):
    """A synthetic run directory whose logs are consistent with the arm's validity rule. Step i (1-based) of a job
    has depth i and the plan plans[(job_id, i)]; actor(k, t) gives the actor-log row of tick k (None: no row; actor
    None: no actor log); actor_log holds keyword arguments of write_actor_log."""
    d = os.path.join(root, name)
    log = os.path.join(d, 'raw', 'agent', 'framelease')
    os.makedirs(log)
    with open(os.path.join(d, 'config.json'), 'w') as f:
        json.dump({'v4_arm': arm, 'kind': 'shield' if arm in VT.SHIELD_ARMS else 'v2_rule', 'kappa': kappa,
                   'seed': 11, 'route': {'route_id': route},
                   'agent_config': {'runtime': {'max_age_s': max_age, 'fallback_brake': 1.0, 'kappa': kappa}}}, f)
    ticks = []
    for k in range(1, n_ticks + 1):
        t = k * DT
        inc = None
        for c in commits:
            if c['commit_s'] <= t:
                inc = c
        ok = _valid(arm, inc, t, max_age)
        row = {'tick': k - 1, 'sim_s': t, 'mode': 'track' if ok else 'fallback',
               'fallback_reason': None if ok else ('no_plan' if inc is None else 'expired'),
               'incumbent': dict(inc) if inc else None, 'control': {'brake': 0.0 if ok else 1.0},
               'gpu': (gpu_ticks or {}).get(k)}
        if tick_patch:
            tick_patch(k, row)
        ticks.append(row)
    write_jsonl(os.path.join(log, 'ticks.jsonl'), ticks)
    job_rows, events = [], []
    for j in jobs:
        pl, pc, po = j['prefix']
        job_rows.append({'job_id': j['job_id'],
                         'prefix': {'launch_s': pl, 'timeline_cost_s': pc, 'decision': {'overhead_s': po}},
                         'steps': [{'launch_s': a, 'timeline_cost_s': c, 'decision': {'overhead_s': o},
                                    'depth': i + 1, 'plan': plans.get((j['job_id'], i + 1))}
                                   for i, (a, c, o) in enumerate(j['steps'])]})
        events.append({'kind': 'job_start', 'job_id': j['job_id'], 'sim_s': pl, 'prefix_end_s': pl + pc,
                       'prefix_timeline_s': pc})
        events.append({'kind': 'job_end', 'job_id': j['job_id']})
    if inflight:
        events.append(dict(inflight, kind='job_start', sim_s=inflight['prefix_end_s'] - inflight['prefix_timeline_s']))
    for c in commits:
        events.append(dict(c, kind='commit'))
    write_jsonl(os.path.join(log, 'jobs.jsonl'), job_rows)
    write_jsonl(os.path.join(log, 'events.jsonl'), events)
    write_jsonl(os.path.join(log, 'decisions.jsonl'), decisions)
    with open(os.path.join(log, 'summary.json'), 'w') as f:
        json.dump(summary if summary is not None else {}, f)
    if actor is not None:
        rows = [actor(k, k * DT) for k in range(1, n_ticks + 1)]
        write_actor_log(log, [r for r in rows if r is not None], **(actor_log or {}))
    for name_ in drop:
        os.remove(os.path.join(log, name_))
    return d


def summary_from(exp):
    """A summary.json carrying the expected values under the runtime's field names."""
    return {
        'v4': {'gpu_usage': exp['gpu_usage'], 'gpu_busy_in_span_s': exp['gpu_busy_s'], 'sim_span_s': exp['sim_span_s'],
               'ticks': exp['ticks'], 'deadline_miss_ratio_after_first_commit': exp['dmr'],
               'deadline_miss_ratio': exp['dmr_all_ticks'],
               'expired_ratio_after_first_commit': exp['expired_ratio_after_first_commit'],
               'fallback_ticks_total': exp['fallback_ticks'], 'fallback_episodes': exp['fallback_episodes'],
               'fallback_ticks': exp['fallback_by_reason'], 'p_both': exp['p_both'],
               'action_age_s': {'p50': exp['action_age_p50_s'], 'p95': exp['action_age_p95_s'],
                                'mean': exp['action_age_mean_s'], 'n': exp['action_age_n']}},
        'v3': {'ticks_after_first_commit': exp['ticks_after_first_commit'], 'first_commit_s': exp['first_commit_s']},
        'expired_tick_ratio': exp['expired_ratio_all_ticks'], 'fallback_tick_ratio': exp['fallback_ratio'],
        'track_ticks': exp['track_ticks'], 'commits': exp['commits'],
    }


def runs_row(job, run_dir, exp, route='990001', arm='fl_heuristic', **extra):
    """A runs.csv row carrying the expected values under the aggregator's column names."""
    row = {'job': job, 'run_dir': run_dir, 'route_id': route, 'analysis_use': 'True', 'protocol_arm': arm,
           'candidate': arm, 'kappa': 1.0, 'seed': 11, 'phase': 'P1', 'block': 'b', 'test_route': 'False',
           'max_age_s': extra.pop('max_age_s', 2.5),
           'ticks': exp['ticks'], 'first_tick_s': DT, 'last_tick_s': 20 * DT, 'sim_span_s': exp['sim_span_s'],
           'gpu_usage': exp['gpu_usage'], 'gpu_usage_recomputed': exp['gpu_usage'], 'gpu_busy_recomputed_s':
           exp['gpu_busy_s'], 'gpu_busy_in_span_s': exp['gpu_busy_s'], 'cuda_s_per_s': exp['cuda_s_per_s'],
           'dmr': exp['dmr'], 'deadline_miss_ratio_after_first_commit': exp['dmr'],
           'ticks_after_first_commit': exp['ticks_after_first_commit'], 'dmr_ticks': exp['ticks_after_first_commit'],
           'deadline_miss_ratio': exp['dmr_all_ticks'],
           'expired_ratio_after_first_commit': exp['expired_ratio_after_first_commit'],
           'expired_ratio': exp['expired_ratio_all_ticks'], 'first_commit_s': exp['first_commit_s'],
           'fallback_ticks': exp['fallback_ticks'], 'fallback_episodes': exp['fallback_episodes'],
           'fallback_by_reason': exp['fallback_by_reason'], 'track_ticks': exp['track_ticks'],
           'action_age_p50_s': exp['action_age_p50_s'], 'action_age_p95_s': exp['action_age_p95_s'],
           'action_age_mean_s': exp['action_age_mean_s'], 'p_both': exp['p_both'],
           'shield_epochs': exp['shield_epochs'], 'choice_epochs': exp['choice_epochs'],
           'decision_epochs': exp['decision_rows'], 'commits': exp['commits'],
           'committed_plans': exp['committed_plans'], 'realized_available': exp['validity_available'],
           'realized_conflict_plans': exp['conflict_plans'], 'realized_misses': exp['misses'],
           'realized_r_cond': exp['r_cond'], 'realized_v0_plans': exp['v0_plans'],
           'realized_r_cond_excl_v0': exp['r_cond_excl_v0'], 'realized_invalid_ticks': exp['eir_invalid_ticks'],
           'realized_invalid_tick_ratio': exp['eir'], 'realized_log_censored_plans': exp['log_censored_plans']}
    row.update(extra)
    return row


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='vt1x_', dir=SCRATCH)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def out(self, name='out'):
        return os.path.join(self.tmp, name)

    def diffs(self, out):
        with open(os.path.join(out, 'differences.csv')) as f:
            return list(csv.DictReader(f))

    def report(self, out):
        with open(os.path.join(out, 'table1_extra.json')) as f:
            return json.load(f)


class KnownAnswers(Base):
    def test_lease_arm_known_answers(self):
        d = make_run(self.tmp, 'lease')
        r = VT.recompute_run(d)
        self.assertEqual(r['problems'], [])
        for k, v in LEASE_EXPECTED.items():
            if isinstance(v, float):
                self.assertAlmostEqual(r[k], v, places=9, msg=k)
            else:
                self.assertEqual(r[k], v, k)
        lo, hi = r['gpu_usage_bounds']
        self.assertAlmostEqual(lo, GPU_LOWER, places=9)
        self.assertAlmostEqual(hi, GPU_UPPER, places=9)
        self.assertEqual(r['gpu_inflight_boundaries'], 3)
        self.assertEqual(r['checks'].get('shield_row_depth_below_1'), 1)
        self.assertNotIn('incumbent_mismatch_ticks', r['checks'])

    def test_age_rule_arm_uses_max_age_not_deadline(self):
        # Fixed Deep, max_age 0.275: A valid at k 3-6 (ages 0.10-0.25), expired k 7-12; B valid k 13-15, expired
        # k 16-20; the logged deadlines are ignored by the age rule.
        commits = [dict(c, deadline_s=9.0) for c in COMMITS]
        d = make_run(self.tmp, 'age', arm='fixed_deep', max_age=0.275, commits=commits, decisions=DECISIONS[-1:])
        r = VT.recompute_run(d)
        self.assertEqual(r['validity_rule'], 'age')
        self.assertEqual(r['missed_ticks_after_first_commit'], 11)
        self.assertAlmostEqual(r['dmr'], 11 / 18, places=12)
        self.assertAlmostEqual(r['dmr_all_ticks'], 13 / 20, places=12)
        self.assertEqual(r['fallback_ticks'], 13)
        self.assertEqual(r['fallback_episodes'], 3)
        self.assertIsNone(r['p_both'])
        self.assertEqual(r['shield_epochs'], 0)
        self.assertAlmostEqual(r['action_age_p50_s'], 0.20, places=9)
        self.assertEqual(r['track_ticks'], 7)

    def test_lease_arm_deadline_rule_and_shield_rows_in_rule_arm(self):
        d = make_run(self.tmp, 'orig', arm='fl_original', max_age=2.0)
        r = VT.recompute_run(d)
        self.assertEqual(r['validity_rule'], 'deadline')
        self.assertAlmostEqual(r['dmr'], 10 / 18, places=12)
        self.assertIsNone(r['p_both'])
        self.assertEqual(r['checks'].get('shield_rows_in_arm_without_shield'), 4)

    def test_raw_data_checks(self):
        def patch(k, row):
            if k == 5:
                row['incumbent'] = None          # tick incumbent disagrees with the commit events
            if k == 9:
                row['fallback_reason'] = None    # fallback without a reason
            if k == 10:
                row['control'] = {'brake': 0.5}  # fallback without the full brake
        d = make_run(self.tmp, 'chk', tick_patch=patch)
        r = VT.recompute_run(d)
        self.assertEqual(r['checks']['incumbent_mismatch_ticks'], 1)
        self.assertEqual(r['checks']['fallback_flag_mismatch'], 1)
        self.assertEqual(r['checks']['fallback_not_full_brake'], 1)
        self.assertAlmostEqual(r['dmr'], 10 / 18, places=12)
        self.assertEqual(r['fallback_ticks'], 12)
        self.assertEqual(r['action_age_n'], 8)

    def test_fallback_validity_identity_checks(self):
        # The analysis reads the fallback ratio from the all-tick DMR column: a fallback tick with a valid committed
        # action and a tracked tick without one are both counted.
        def patch(k, row):
            if k == 4:
                row.update(mode='fallback', fallback_reason='other', control={'brake': 1.0})
            if k == 10:
                row.update(mode='track', fallback_reason=None, control={'brake': 0.0})
        r = VT.recompute_run(make_run(self.tmp, 'ident', tick_patch=patch))
        self.assertEqual(r['checks'].get('fallback_with_valid_action'), 1)
        self.assertEqual(r['checks'].get('no_fallback_without_valid_action'), 1)
        self.assertEqual(r['fallback_ticks'], 12)
        self.assertEqual(r['fallback_episodes'], 5)  # k 1-2, 4, 8-9, 11-12, 16-20
        self.assertAlmostEqual(r['dmr_all_ticks'], 12 / 20, places=12)
        r = VT.recompute_run(make_run(self.tmp, 'ident_ok'))
        self.assertNotIn('fallback_with_valid_action', r['checks'])
        self.assertNotIn('no_fallback_without_valid_action', r['checks'])

    def test_commit_logged_just_after_the_tick(self):
        # B is logged 0.8 microseconds after tick k 13 (t 0.65), which the runtime already tracks on B: within the
        # 1e-6 s time tolerance the rebuilt committed action is B there too.
        commits = [COMMITS[0], dict(COMMITS[1], commit_s=0.65 + 8e-7)]

        def patch(k, row):
            if k == 13:
                row.update(mode='track', fallback_reason=None, incumbent=dict(commits[1]), control={'brake': 0.0})
        r = VT.recompute_run(make_run(self.tmp, 'late', commits=commits, tick_patch=patch))
        for key in ('incumbent_mismatch_ticks', 'no_fallback_without_valid_action', 'fallback_with_valid_action'):
            self.assertNotIn(key, r['checks'])
        self.assertEqual((r['track_ticks'], r['action_age_n']), (8, 8))   # A at k 3-7, B at k 13-15

    def test_unknown_arm_and_missing_log_are_problems(self):
        r = VT.recompute_run(make_run(self.tmp, 'unk', arm='mystery'))
        self.assertTrue(any('unknown arm' in p for p in r['problems']))
        r = VT.recompute_run(make_run(self.tmp, 'miss', drop=('decisions.jsonl',)))
        self.assertTrue(any('decisions.jsonl' in p for p in r['problems']))
        r = VT.recompute_run(make_run(self.tmp, 'nosum', drop=('summary.json',)))
        self.assertEqual(r['problems'], [])

    def test_no_inflight_job_is_exact(self):
        d = make_run(self.tmp, 'exact', inflight=None, gpu_ticks={})
        r = VT.recompute_run(d)
        self.assertAlmostEqual(r['gpu_busy_s'], 0.19, places=12)
        self.assertEqual(r['gpu_usage_bounds'][0], r['gpu_usage_bounds'][1])


class RunLevel(Base):
    def setUp(self):
        Base.setUp(self)
        self.run_dir = make_run(self.tmp, 'run', summary=summary_from(LEASE_EXPECTED))
        self.agg = os.path.join(self.tmp, 'agg')
        os.makedirs(self.agg)

    def write_runs(self, **extra):
        write_csv(os.path.join(self.agg, 'runs.csv'), [runs_row('job1', self.run_dir, LEASE_EXPECTED, **extra)])

    def test_agree(self):
        self.write_runs()
        code = VT.main(['--agg', self.agg, '--out', self.out()])
        self.assertEqual(code, VT.EXIT_AGREE, self.diffs(self.out()))
        rep = self.report(self.out())
        self.assertEqual(rep['verdict'], 'AGREE')
        self.assertEqual(rep['status'], 'development')
        self.assertGreater(rep['comparisons']['by_target']['runs.csv']['compared'], 30)
        self.assertGreater(rep['comparisons']['by_target']['summary.json']['compared'], 15)
        with open(os.path.join(self.out(), 'SHA256SUMS')) as f:
            for line in f:
                h, name = line.split()
                self.assertEqual(VT.sha256_file(os.path.join(self.out(), name)), h)

    def test_each_perturbation_is_listed(self):
        cases = {'dmr': LEASE_EXPECTED['dmr'] + 1e-3, 'action_age_p95_s': 0.30, 'p_both': 0.25,
                 'fallback_episodes': 4, 'deadline_miss_ratio': 0.5, 'fallback_by_reason': {'expired': 12},
                 'realized_invalid_tick_ratio': 0.5, 'realized_v0_plans': 1, 'realized_r_cond': 0.5,
                 'realized_log_censored_plans': 0, 'committed_plans': 3}
        for col, val in cases.items():
            with self.subTest(col=col):
                self.write_runs(**{col: val})
                out = self.out('o_' + col)
                self.assertEqual(VT.main(['--agg', self.agg, '--out', out]), VT.EXIT_DIFFER)
                cols = set(r['their_field'] for r in self.diffs(out))
                self.assertIn(col, cols)

    def test_numerical_noise_agrees_and_gpu_bounds(self):
        self.write_runs(dmr=LEASE_EXPECTED['dmr'] + 1e-9, gpu_usage=0.5381, gpu_usage_recomputed=GPU_LOWER)
        self.assertEqual(VT.main(['--agg', self.agg, '--out', self.out()]), VT.EXIT_AGREE)
        by = self.report(self.out())['comparisons']['by_target']
        self.assertEqual(by['runs.csv']['agree_within_inflight_bounds'], 2)
        self.assertEqual(by['summary.json']['agree_within_inflight_bounds'], 0)
        self.write_runs(gpu_usage=GPU_UPPER + 1e-4)
        self.assertEqual(VT.main(['--agg', self.agg, '--out', self.out('o2')]), VT.EXIT_DIFFER)
        d = self.diffs(self.out('o2'))
        self.assertEqual([(x['their_field'], x['below_grid']) for x in d], [('gpu_usage', 'False')])

    def test_absent_column_listed_once(self):
        row = runs_row('job1', self.run_dir, LEASE_EXPECTED)
        del row['dmr_ticks']
        write_csv(os.path.join(self.agg, 'runs.csv'), [row, dict(row, job='job2')])
        self.assertEqual(VT.main(['--agg', self.agg, '--out', self.out()]), VT.EXIT_DIFFER)
        d = self.diffs(self.out())
        self.assertEqual([(x['status'], x['their_field']) for x in d], [('absent', 'dmr_ticks')])

    def test_summary_json_difference(self):
        s = summary_from(LEASE_EXPECTED)
        s['v4']['action_age_s']['p50'] = 0.25
        with open(os.path.join(self.run_dir, VT.LOG_DIR, 'summary.json'), 'w') as f:
            json.dump(s, f)
        self.write_runs()
        self.assertEqual(VT.main(['--agg', self.agg, '--out', self.out()]), VT.EXIT_DIFFER)
        d = self.diffs(self.out())
        self.assertEqual([(x['target'], x['field']) for x in d], [('summary.json', 'action_age_p50_s')])

    def test_missing_summary_of_used_run_is_a_difference(self):
        os.remove(os.path.join(self.run_dir, VT.LOG_DIR, 'summary.json'))
        self.write_runs()
        self.assertEqual(VT.main(['--agg', self.agg, '--out', self.out()]), VT.EXIT_DIFFER)
        self.assertEqual([(x['target'], x['status']) for x in self.diffs(self.out())], [('summary.json', 'absent')])
        self.write_runs(analysis_use='False')
        self.assertEqual(VT.main(['--agg', self.agg, '--out', self.out('o2')]), VT.EXIT_AGREE)

    def test_unrecomputable_used_run_is_a_difference(self):
        os.remove(os.path.join(self.run_dir, VT.LOG_DIR, 'ticks.jsonl'))
        self.write_runs()
        self.assertEqual(VT.main(['--agg', self.agg, '--out', self.out()]), VT.EXIT_DIFFER)
        self.assertEqual([x['target'] for x in self.diffs(self.out())], ['run logs'])
        self.write_runs(analysis_use='False')
        self.assertEqual(VT.main(['--agg', self.agg, '--out', self.out('o2')]), VT.EXIT_AGREE)

    def test_scope_of_differences(self):
        # dmr is a column the analysis reads; gpu_usage_recomputed is not; deadline_miss_ratio is read as the
        # fallback ratio (scope analysis) and compared as the all-tick DMR (scope record).
        self.write_runs(dmr=0.9, gpu_usage_recomputed=0.9, deadline_miss_ratio=0.9)
        self.assertEqual(VT.main(['--agg', self.agg, '--out', self.out()]), VT.EXIT_DIFFER)
        got = sorted((x['field'], x['their_field'], x['scope']) for x in self.diffs(self.out()))
        self.assertEqual(got, [('dmr', 'dmr', 'analysis'), ('dmr_all_ticks', 'deadline_miss_ratio', 'record'),
                               ('fallback_ratio', 'deadline_miss_ratio', 'analysis'),
                               ('gpu_usage', 'gpu_usage_recomputed', 'record')])
        rep = self.report(self.out())
        self.assertEqual(rep['comparisons']['differences'], 4)
        self.assertEqual(rep['comparisons']['analysis_differences'], 2)
        self.assertEqual(rep['comparisons']['by_target']['runs.csv']['analysis_differences'], 2)
        # A row the analysis does not use: every difference has scope record.
        self.write_runs(dmr=0.9, analysis_use='False')
        self.assertEqual(VT.main(['--agg', self.agg, '--out', self.out('o2')]), VT.EXIT_DIFFER)
        self.assertEqual([x['scope'] for x in self.diffs(self.out('o2'))], ['record'])
        self.assertEqual(self.report(self.out('o2'))['comparisons']['analysis_differences'], 0)

    def test_used_rows_without_raw_logs(self):
        gone = os.path.join(self.tmp, 'gone')
        rows = [runs_row('job1', gone, LEASE_EXPECTED), runs_row('job2', '', LEASE_EXPECTED),
                runs_row('job3', gone, LEASE_EXPECTED, analysis_use='False')]
        write_csv(os.path.join(self.agg, 'runs.csv'), rows)
        self.assertEqual(VT.main(['--agg', self.agg, '--out', self.out()]), VT.EXIT_DIFFER)
        d = self.diffs(self.out())
        self.assertEqual([(x['target'], x['key'], x['scope']) for x in d], [('run logs', 'job1', 'analysis')])
        runs = self.report(self.out())['runs']
        self.assertEqual(runs['used_rows'], 2)
        self.assertEqual(runs['used_rows_without_raw_logs'], 2)
        self.assertEqual(runs['used_rows_without_raw_logs_by_reason'],
                         {'run directory absent': 1, 'no run directory named': 1})

    def test_runner_records(self):
        self.write_runs()
        q = os.path.join(self.tmp, 'queue')
        os.makedirs(q)
        other = make_run(self.tmp, 'other', summary=summary_from(LEASE_EXPECTED))
        recs = [
            {'event': 'end', 'id': 'job1', 'final': False, 'run_dir': other, 'outcome': 'timeout',
             'job': {'route_id': '990001'}},
            {'event': 'end', 'id': 'job1', 'final': True, 'run_dir': self.run_dir, 'outcome': 'ok',
             'job': {'route_id': '990001'}, 'result': {'action_age_p50_s': 0.20, 'fallback_tick_ratio': 0.6}},
        ]
        write_jsonl(os.path.join(q, 'status.jsonl'), recs)
        self.assertEqual(VT.main(['--queue', q, '--agg', self.agg, '--out', self.out()]), VT.EXIT_AGREE)
        rep = self.report(self.out())
        self.assertEqual(rep['comparisons']['by_target']['runner result']['compared'], 2)
        recs[1]['run_dir'] = other
        recs[1]['result']['fallback_tick_ratio'] = 0.55
        write_jsonl(os.path.join(q, 'status.jsonl'), recs)
        self.assertEqual(VT.main(['--queue', q, '--agg', self.agg, '--out', self.out('o2')]), VT.EXIT_DIFFER)
        self.assertEqual(sorted(x['target'] for x in self.diffs(self.out('o2'))), ['runner'])
        # A timed-out final attempt: the runner reports no values; the recomputed ones differ, with the outcome noted.
        recs[1].update(run_dir=self.run_dir, outcome='timeout',
                       result={'action_age_p50_s': None, 'fallback_tick_ratio': None})
        write_jsonl(os.path.join(q, 'status.jsonl'), recs)
        self.assertEqual(VT.main(['--queue', q, '--agg', self.agg, '--out', self.out('o3')]), VT.EXIT_DIFFER)
        d = self.diffs(self.out('o3'))
        self.assertEqual(sorted(x['their_field'] for x in d), ['result.action_age_p50_s', 'result.fallback_tick_ratio'])
        self.assertTrue(all("runner outcome 'timeout'" in x['note'] and 'theirs empty' in x['note'] for x in d))

    def test_arm_summary(self):
        self.write_runs()
        row = {'protocol_arm': 'fl_heuristic', 'candidate': 'fl_heuristic', 'kappa': '1.0', 'seed': '11',
               'phase': 'P1', 'block': 'b', 'routes': 1, 'gpu_usage': 0.537,
               'deadline_miss_ratio': LEASE_EXPECTED['dmr_all_ticks'], 'deadline_miss_ratio_pooled': 12 / 20,
               'deadline_miss_ratio_after_first_commit': LEASE_EXPECTED['dmr'], 'fallback_episodes': 3.0,
               'action_age_p50_s': 0.2, 'action_age_mean_s': 0.2, 'p_both_pooled': 0.5,
               'realized_invalid_tick_ratio': 0.625}
        write_csv(os.path.join(self.agg, 'arm_summary.csv'), [row])
        self.assertEqual(VT.main(['--agg', self.agg, '--out', self.out()]), VT.EXIT_AGREE, self.diffs(self.out()))
        write_csv(os.path.join(self.agg, 'arm_summary.csv'), [dict(row, p_both_pooled=0.4, routes=2,
                                                                   realized_invalid_tick_ratio=0.5)])
        self.assertEqual(VT.main(['--agg', self.agg, '--out', self.out('o2')]), VT.EXIT_DIFFER)
        self.assertEqual(sorted(x['field'] for x in self.diffs(self.out('o2'))),
                         ['p_both_pooled', 'realized_invalid_tick_ratio', 'routes'])


def _route_age_commits(shift):
    """Commits whose ages differ by route (shift in seconds)."""
    return [dict(c, capture_s=c['capture_s'] - shift) for c in COMMITS]


class AnalysisLevel(Base):
    """Two conditions x two synthetic routes: hand-made analysis outputs from the known per-run values."""

    def setUp(self):
        Base.setUp(self)
        self.agg = os.path.join(self.tmp, 'agg')
        self.ana = os.path.join(self.tmp, 'analysis')
        os.makedirs(self.agg)
        os.makedirs(self.ana)
        runs, self.vals = [], {}
        for arm, cond in (('fl_full', 'fl_full_k1.0_s11'), ('fixed_deep', 'fixed_deep_k1.0_s11')):
            for i, route in enumerate(('930000', '930001')):
                job = 'syn_%s_r%s' % (arm, route)
                # Fixed Deep: max_age 0.275 / 0.325 by route, so its DMR differs between the routes (11/18, 9/18).
                d = make_run(self.tmp, job, arm=arm, route=route,
                             max_age=2.5 if arm == 'fl_full' else (0.275, 0.325)[i],
                             commits=_route_age_commits(0.0 if i == 0 else 0.01) if arm == 'fl_full'
                             else [dict(c, deadline_s=9.0) for c in COMMITS])
                r = VT.recompute_run(d)
                with open(os.path.join(d, VT.LOG_DIR, 'summary.json'), 'w') as f:
                    json.dump(summary_from(r), f)
                self.vals[(cond, route)] = r
                runs.append(runs_row(job, d, r, route=route, arm=arm, max_age_s=r['max_age_s']))
        write_csv(os.path.join(self.agg, 'runs.csv'), runs)
        self.cells = []
        for (cond, route), r in sorted(self.vals.items()):
            self.cells.append({'condition': cond, 'route_id': route, 'status': 'used',
                               'jobs': json.dumps(['syn_%s_r%s' % (cond.split('_k')[0], route)])})
        # A cell without a job line in the input (no value anywhere).
        self.cells.append({'condition': 'age_only_k1.0_s11', 'route_id': '930000', 'status': 'no_row', 'jobs': '[]'})
        write_csv(os.path.join(self.ana, 'cells.csv'), self.cells)
        cols = dict(VT.DEFAULT_ANALYSIS_COLUMNS)
        self.cond_rows = []
        for cond in ('fl_full_k1.0_s11', 'fixed_deep_k1.0_s11'):
            for metric, field in VT.ANALYSIS_METRICS.items():
                xs = [self.vals[(cond, r)][field] for r in ('930000', '930001')]
                xs = [x for x in xs if x is not None]
                st = VT._stats(xs)
                self.cond_rows.append(dict(st, condition=cond, subset='all', metric=metric, statistic='route_mean',
                                           column=cols[metric]))
        write_csv(os.path.join(self.ana, 'conditions.csv'), self.cond_rows)
        self.sec_rows, self.pairs = [], []
        for metric, field in VT.ANALYSIS_METRICS.items():
            a = [self.vals[('fl_full_k1.0_s11', r)][field] for r in ('930000', '930001')]
            b = [self.vals[('fixed_deep_k1.0_s11', r)][field] for r in ('930000', '930001')]
            keep = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
            st = VT._stats([x - y for x, y in keep])
            row = dict(st, contrast='fl_full_minus_fixed_deep_k1.0_s11_all', a='fl_full_k1.0_s11',
                       b='fixed_deep_k1.0_s11', subset='all', metric=metric,
                       mean_a=VT.mean([x for x, _ in keep]), mean_b=VT.mean([y for _, y in keep]))
            self.sec_rows.append(row)
            for route, x, y in zip(('930000', '930001'), a, b):
                self.pairs.append({'table': 'secondary', 'contrast': row['contrast'], 'metric': metric,
                                   'route_id': route, 'value_a': x, 'value_b': y,
                                   'difference': None if x is None or y is None else x - y, 'status': 'paired'})
        write_csv(os.path.join(self.ana, 'secondary.csv'), self.sec_rows)
        write_csv(os.path.join(self.ana, 'paired_differences.csv'), self.pairs)
        sdmr = [dict(r, contrast='%s_k1.0_s11_all' % c, family_size=4) for c in VT.H1_CONTRASTS
                for r in self.sec_rows if r['metric'] == 'dmr']
        for r in sdmr[1:]:
            r['b'] = r['contrast'].split('_minus_')[1].replace('_all', '')
            r['n'] = 0
            for k in ('mean', 'median', 'min', 'max', 'mean_a', 'mean_b'):
                r[k] = None
        write_csv(os.path.join(self.ana, 'family_S-dmr.csv'), sdmr)
        # descriptive.csv: the GPU-usage contrast as a descriptive row.
        self.desc = [dict(r, role='descriptive') for r in self.sec_rows if r['metric'] == 'gpu_usage']
        write_csv(os.path.join(self.ana, 'descriptive.csv'), self.desc)
        # per_scenario.csv: every used cell with its values, and the cell without a row (no value).
        self.scen = []
        for (cond, route), r in sorted(self.vals.items()):
            row = {'scenario_type': 'Accident', 'route_id': route, 'condition': cond, 'arm': cond.split('_k')[0],
                   'kappa': '1.0', 'seed': '11', 'status': 'used', 'job': 'syn_%s_r%s' % (cond.split('_k')[0], route)}
            row.update({m: r[f] for m, f in VT.ANALYSIS_METRICS.items()})
            self.scen.append(row)
        self.scen.append({'scenario_type': 'Accident', 'route_id': '930000', 'condition': 'age_only_k1.0_s11',
                          'arm': 'age_only', 'kappa': '1.0', 'seed': '11', 'status': 'no_row', 'job': None})
        write_csv(os.path.join(self.ana, 'per_scenario.csv'), self.scen, fields=list(self.scen[0]))
        # per_ability.csv: one ability group with both routes, for DMR (S-dmr) and GPU usage.
        self.ability = []
        for metric in ('dmr', 'gpu_usage'):
            field = VT.ANALYSIS_METRICS[metric]
            a = [self.vals[('fl_full_k1.0_s11', r)][field] for r in ('930000', '930001')]
            b = [self.vals[('fixed_deep_k1.0_s11', r)][field] for r in ('930000', '930001')]
            d = [x - y for x, y in zip(a, b)]
            self.ability.append({
                'contrast': 'fl_full_minus_fixed_deep_k1.0_s11_all', 'a': 'fl_full_k1.0_s11',
                'b': 'fixed_deep_k1.0_s11', 'subset': 'all', 'metric': metric, 'ability': 'Merging', 'n_routes': 2,
                'n': 2, 'mean': VT.mean(d), 'mean_a': VT.mean(a), 'mean_b': VT.mean(b),
                'n_positive': sum(1 for x in d if x > 0), 'n_negative': sum(1 for x in d if x < 0),
                'n_zero': sum(1 for x in d if x == 0), 'routes': '930000|930001'})
        write_csv(os.path.join(self.ana, 'per_ability.csv'), self.ability)
        # analysis.json: route table, the lists and the sections of this script's metrics.
        overhead = {}
        for cond in ('fl_full_k1.0_s11', 'fixed_deep_k1.0_s11'):
            rs = [self.vals[(cond, r)] for r in ('930000', '930001')]
            st = VT._stats([x['dmr'] for x in rs])
            overhead[cond] = {'runs': 2, 'dmr': {'runs': 2, 'mean': st['mean'], 'median': st['median'],
                                                 'max': st['max']},
                              'fallback_episodes': {'runs_with_any': sum(1 for x in rs if x['fallback_episodes']),
                                                    'total': sum(x['fallback_episodes'] for x in rs)}}
        self.aj = {
            'status': 'development', 'route_table': {'subsets': {'all': ['930000', '930001']}},
            'secondary': [dict(r) for r in self.sec_rows],
            'descriptive': [dict(r) for r in self.desc],
            'families': [{'name': 'S-dmr', 'metric': 'dmr', 'rows': [dict(r) for r in sdmr]}],
            'per_ability': [dict(r, routes=r['routes'].split('|')) for r in self.ability],
            'overhead': overhead,
            'decisions': {'H1': {'finding_2': {'gpu_usage_descriptive': [
                {'contrast': c, 'metric': 'gpu_usage', 'label': 'descriptive', 'n': 0, 'mean': None}
                for c in VT.FINDING2_GPU_CONTRASTS]}}},
            'manipulation': {'analysed_runs': {'p_both_shared_shield': {}}},
        }
        self.write_aj()

    def write_aj(self):
        with open(os.path.join(self.ana, 'analysis.json'), 'w') as f:
            json.dump(self.aj, f)

    def run_vt(self, *extra, out='out'):
        return VT.main(['--agg', self.agg, '--analysis', self.ana, '--out', self.out(out)] + list(extra))

    def test_agree_from_raw(self):
        self.assertEqual(self.run_vt(), VT.EXIT_AGREE, self.diffs(self.out()))
        rep = self.report(self.out())
        self.assertEqual(rep['analysis_cells']['used_cells'], 4)
        self.assertEqual(set(rep['analysis_cells']['value_sources']), {'raw'})
        by = rep['comparisons']['by_target']
        for t in ('conditions.csv', 'secondary.csv', 'paired_differences.csv', 'family_S-dmr.csv'):
            self.assertGreater(by[t]['compared'], 0, t)
        self.assertNotEqual(self.vals[('fl_full_k1.0_s11', '930000')]['action_age_p50_s'],
                            self.vals[('fl_full_k1.0_s11', '930001')]['action_age_p50_s'])

    def test_condition_mean_difference(self):
        rows = [dict(r) for r in self.cond_rows]
        for r in rows:
            if r['condition'] == 'fl_full_k1.0_s11' and r['metric'] == 'action_age_p50_s':
                r['mean'] += 0.002
        write_csv(os.path.join(self.ana, 'conditions.csv'), rows)
        self.assertEqual(self.run_vt(), VT.EXIT_DIFFER)
        d = self.diffs(self.out())
        self.assertEqual([(x['target'], x['field'], x['below_grid']) for x in d],
                         [('conditions.csv', 'mean', 'False')])

    def test_fallback_column_substitution_is_judged(self):
        # The analysis reads its fallback ratio from a column; a per-run value there that is not the fallback
        # ratio is a difference at the condition level.
        rows = [dict(r) for r in self.cond_rows]
        for r in rows:
            if r['metric'] == 'fallback_ratio' and r['condition'] == 'fixed_deep_k1.0_s11':
                r['mean'] = 0.7
        write_csv(os.path.join(self.ana, 'conditions.csv'), rows)
        self.assertEqual(self.run_vt(), VT.EXIT_DIFFER)
        self.assertEqual(self.report(self.out())['analysis_columns']['fallback_ratio'], 'deadline_miss_ratio')

    def test_contrast_and_pair_differences(self):
        sec = [dict(r) for r in self.sec_rows]
        for r in sec:
            if r['metric'] == 'gpu_usage':
                r['mean_b'] += 1e-2
        write_csv(os.path.join(self.ana, 'secondary.csv'), sec)
        pairs = [dict(p) for p in self.pairs]
        pairs[0]['status'] = 'cell not used: A fl_full_k1.0_s11: no_row'
        write_csv(os.path.join(self.ana, 'paired_differences.csv'), pairs)
        self.assertEqual(self.run_vt(), VT.EXIT_DIFFER)
        got = sorted((x['target'], x['field']) for x in self.diffs(self.out()))
        self.assertEqual(got, [('paired_differences.csv', 'paired'), ('secondary.csv', 'mean_b')])

    def test_sdmr_structure_and_missing_file(self):
        with open(os.path.join(self.ana, 'family_S-dmr.csv')) as f:
            rows = list(csv.DictReader(f))
        write_csv(os.path.join(self.ana, 'family_S-dmr.csv'), rows[:3])
        os.remove(os.path.join(self.ana, 'paired_differences.csv'))
        self.assertEqual(self.run_vt(), VT.EXIT_DIFFER)
        got = sorted((x['target'], x['field'] or x['their_field']) for x in self.diffs(self.out()))
        self.assertEqual(got, [('analysis', 'paired_differences.csv'), ('family_S-dmr.csv', 'contrasts')])

    def test_unpaired_route_carries_no_value_comparison(self):
        # cells.csv no longer uses fixed_deep on route 930001 while paired_differences.csv still pairs it.
        cells = [dict(c) for c in self.cells]
        for c in cells:
            if c['condition'] == 'fixed_deep_k1.0_s11' and c['route_id'] == '930001':
                c['status'] = 'missing'
        write_csv(os.path.join(self.ana, 'cells.csv'), cells)
        self.assertEqual(self.run_vt(), VT.EXIT_DIFFER)
        pd = [x for x in self.diffs(self.out()) if x['target'] == 'paired_differences.csv']
        self.assertEqual(len(pd), len(VT.ANALYSIS_METRICS))
        self.assertEqual(set(x['field'] for x in pd), {'paired'})

    def test_analysis_column_named_by_conditions(self):
        # The runs.csv column the analysis reads is taken from conditions.csv 'column'.
        rows = []
        for (cond, route), r in sorted(self.vals.items()):
            rows.append({'job': 'syn_%s_r%s' % (cond.split('_k')[0], route), 'route_id': route,
                         'analysis_use': 'True', 'gpu_usage': r['gpu_usage'], 'dmr': r['dmr'],
                         'action_age_p50_s': r['action_age_p50_s'], 'action_age_p95_s': r['action_age_p95_s'],
                         'fallback_share': r['fallback_ratio'], 'deadline_miss_ratio': 0.99, 'p_both': r['p_both'],
                         'fallback_episodes': r['fallback_episodes'], 'realized_invalid_tick_ratio': r['eir'],
                         'realized_r_cond': r['r_cond']})
        write_csv(os.path.join(self.agg, 'runs.csv'), rows)
        cond = [dict(r, column='fallback_share') if r['metric'] == 'fallback_ratio' else dict(r)
                for r in self.cond_rows]
        write_csv(os.path.join(self.ana, 'conditions.csv'), cond)
        self.assertEqual(self.run_vt(), VT.EXIT_AGREE, self.diffs(self.out()))
        self.assertEqual(self.report(self.out())['analysis_columns']['fallback_ratio'], 'fallback_share')

    def test_per_scenario_differences(self):
        rows = [dict(r) for r in self.scen]
        rows[0]['dmr'] += 1e-3                                  # value of a used cell
        rows[1].update(job='other_job', status='duplicate')     # job and status of a used cell
        rows[-1]['p_both'] = 0.5                                # a cell without a row carries a value
        del rows[2]                                             # a used cell without a row
        write_csv(os.path.join(self.ana, 'per_scenario.csv'), rows, fields=list(self.scen[0]))
        self.assertEqual(self.run_vt(), VT.EXIT_DIFFER)
        got = sorted((x['target'], x['field']) for x in self.diffs(self.out()))
        self.assertEqual(got, [('per_scenario.csv', f) for f in ('dmr', 'job', 'p_both', 'row', 'status')])
        rep = self.report(self.out())
        self.assertEqual(rep['comparisons']['by_target']['per_scenario.csv']['analysis_differences'], 5)

    def test_per_ability_differences(self):
        rows = [dict(r) for r in self.ability]
        rows[0]['routes'] = '930000|930001|930002'   # a listed route without a paired value
        rows[1]['n_zero'] = 1
        write_csv(os.path.join(self.ana, 'per_ability.csv'), rows)
        self.aj['per_ability'][0]['mean_a'] += 0.01
        self.write_aj()
        self.assertEqual(self.run_vt(), VT.EXIT_DIFFER)
        got = sorted((x['target'], x['field']) for x in self.diffs(self.out()))
        self.assertEqual(got, [('analysis.json:per_ability', 'mean_a'), ('per_ability.csv', 'n_zero'),
                               ('per_ability.csv', 'routes')])

    def test_overhead_differences(self):
        ov = self.aj['overhead']
        ov['fl_full_k1.0_s11']['dmr']['median'] += 1e-3
        ov['fixed_deep_k1.0_s11']['fallback_episodes']['total'] += 1
        self.write_aj()
        self.assertEqual(self.run_vt(), VT.EXIT_DIFFER)
        got = sorted((x['key'], x['field']) for x in self.diffs(self.out()))
        self.assertEqual(got, [('overhead:fixed_deep_k1.0_s11', 'fallback_episodes_total'),
                               ('overhead:fl_full_k1.0_s11', 'dmr_median')])
        del ov['fixed_deep_k1.0_s11']
        ov['fl_full_k1.0_s11']['dmr']['median'] -= 1e-3
        self.write_aj()
        self.assertEqual(self.run_vt(out='o2'), VT.EXIT_DIFFER)
        self.assertEqual([(x['key'], x['field'], x['note']) for x in self.diffs(self.out('o2'))],
                         [('overhead:fixed_deep_k1.0_s11', 'runs', 'condition absent in overhead; theirs empty')])
        del self.aj['overhead']
        self.write_aj()
        self.assertEqual(self.run_vt(out='o3'), VT.EXIT_DIFFER)
        self.assertEqual([(x['key'], x['note']) for x in self.diffs(self.out('o3'))], [('overhead', 'section absent')])

    def test_contrast_lists_and_descriptive(self):
        for r in self.aj['secondary']:
            if r['metric'] == 'gpu_usage':
                r['mean_b'] += 1e-2
        self.aj['families'] = []
        self.write_aj()
        desc = [dict(r) for r in self.desc]
        desc[0]['mean'] += 1e-2
        write_csv(os.path.join(self.ana, 'descriptive.csv'), desc)
        self.assertEqual(self.run_vt(), VT.EXIT_DIFFER)
        got = sorted((x['target'], x['field']) for x in self.diffs(self.out()))
        self.assertEqual(got, [('analysis.json:families/S-dmr', 'families_named_S-dmr'),
                               ('analysis.json:secondary', 'mean_b'), ('descriptive.csv', 'mean')])

    def test_new_analysis_files_required(self):
        for name in ('per_scenario.csv', 'per_ability.csv', 'descriptive.csv'):
            os.remove(os.path.join(self.ana, name))
        del self.aj['per_ability']
        self.write_aj()
        self.assertEqual(self.run_vt(), VT.EXIT_DIFFER)
        got = sorted((x['target'], x['their_field'], x['status']) for x in self.diffs(self.out()))
        self.assertEqual(got, [('analysis', 'descriptive.csv', 'absent'), ('analysis', 'per_ability.csv', 'absent'),
                               ('analysis', 'per_scenario.csv', 'absent'),
                               ('analysis.json', 'per_ability', 'absent')])

    def test_validity_metrics_compared(self):
        self.assertIn('eir', [r['metric'] for r in self.cond_rows])
        rows = [dict(r) for r in self.cond_rows]
        for r in rows:
            if r['metric'] == 'eir' and r['condition'] == 'fixed_deep_k1.0_s11':
                r['mean'] += 1e-3
        write_csv(os.path.join(self.ana, 'conditions.csv'), rows)
        scen = [dict(r) for r in self.scen]
        scen[0]['r_cond'] = 0.123
        write_csv(os.path.join(self.ana, 'per_scenario.csv'), scen, fields=list(self.scen[0]))
        self.assertEqual(self.run_vt(), VT.EXIT_DIFFER)
        got = sorted((x['target'], x['key'].split('/')[-1] if x['target'] == 'conditions.csv' else x['field'],
                      x['scope']) for x in self.diffs(self.out()))
        self.assertEqual(got, [('conditions.csv', 'eir', 'analysis'), ('per_scenario.csv', 'r_cond', 'analysis')])
        self.assertEqual(self.report(self.out())['analysis_columns']['eir'], 'realized_invalid_tick_ratio')

    def test_runs_csv_values_without_raw(self):
        # Without run directories the analysis is compared with the runs.csv columns it reads ('runs.csv' source).
        rows = []
        for (cond, route), r in sorted(self.vals.items()):
            rows.append({'job': 'syn_%s_r%s' % (cond.split('_k')[0], route), 'route_id': route,
                         'analysis_use': 'True', 'gpu_usage': r['gpu_usage'], 'dmr': r['dmr'],
                         'action_age_p50_s': r['action_age_p50_s'], 'action_age_p95_s': r['action_age_p95_s'],
                         'deadline_miss_ratio': r['fallback_ratio'], 'p_both': r['p_both'],
                         'fallback_episodes': r['fallback_episodes'], 'realized_invalid_tick_ratio': r['eir'],
                         'realized_r_cond': r['r_cond']})
        write_csv(os.path.join(self.agg, 'runs.csv'), rows)
        self.assertEqual(self.run_vt(), VT.EXIT_AGREE, self.diffs(self.out()))
        self.assertEqual(set(self.report(self.out())['analysis_cells']['value_sources']), {'runs.csv'})
        # Rows naming run directories that do not exist: a difference each by default; with --runs-csv-values the
        # directories are not read and the rows are listed as used rows without raw logs.
        for r in rows:
            r['selected_run'] = 'runs/%s' % r['job']
        write_csv(os.path.join(self.agg, 'runs.csv'), rows)
        self.assertEqual(self.run_vt(out='o2'), VT.EXIT_DIFFER)
        self.assertEqual(set((x['target'], x['scope']) for x in self.diffs(self.out('o2'))), {('run logs', 'analysis')})
        self.assertEqual(len(self.diffs(self.out('o2'))), len(rows))
        self.assertEqual(self.run_vt('--runs-csv-values', out='o3'), VT.EXIT_AGREE)
        rep = self.report(self.out('o3'))
        self.assertTrue(rep['options']['runs_csv_values'])
        self.assertEqual(rep['runs']['used_rows_without_raw_logs_by_reason'],
                         {'runs.csv values (--runs-csv-values)': len(rows)})


class AnalysisJsonSections(unittest.TestCase):
    """analysis.json decisions.H1.finding_2.gpu_usage_descriptive and manipulation p_both_shared_shield."""

    @staticmethod
    def cell(arm, kappa, seed, p_both, gpu=None, choice=None, shield=None):
        vals = {m: (None, 'raw', None, None) for m in VT.ANALYSIS_METRICS}
        vals['p_both'] = (p_both, 'raw', p_both, p_both)
        if gpu is not None:
            vals['gpu_usage'] = (gpu, 'raw', gpu - 0.001, gpu + 0.001)
        return {'job': 'j_%s_%s_%s' % (arm, kappa, seed), 'arm': arm, 'kappa': kappa, 'seed': seed, 'vals': vals,
                'extra': {'fallback_episodes': 0, 'choice_epochs': choice, 'shield_epochs': shield}}

    @staticmethod
    def run_cmp(fn, *args):
        cmp = VT.Comparisons()

        def put(*a, **k):
            k.setdefault('scope', 'analysis')
            return cmp.compare(*a, **k)
        fn(put, *args)
        return cmp

    def test_p_both_shared_shield(self):
        cv = {}
        # kappa 1.0: (r1, s11), (r2, s11) and (r1, s12) paired; r3 has fl_full only. kappa 1.5: (r1, s11) paired, the
        # heuristic run without a choice-epoch count. kappa 2.0: fl_full only (no pair, no entry: not compared).
        # fl_full: mean 0.4, pooled 14 / 40 = 0.35; fl_heuristic: mean 0.3, pooled 9 / 30 = 0.3.
        for route, seed, pf, cf, sf, ph, ch in (('r1', '11', 0.4, 4, 10, 0.3, 3), ('r2', '11', 0.2, 4, 20, 0.2, 2),
                                                ('r1', '12', 0.6, 6, 10, 0.4, 4)):
            cv[('fl_full_k1.0_s' + seed, route)] = self.cell('fl_full', 1.0, seed, pf, choice=cf, shield=sf)
            cv[('fl_heuristic_k1.0_s' + seed, route)] = self.cell('fl_heuristic', 1.0, seed, ph, choice=ch, shield=10)
        cv[('fl_full_k1.0_s11', 'r3')] = self.cell('fl_full', 1.0, '11', 0.9, choice=9, shield=10)
        cv[('fl_full_k1.5_s11', 'r1')] = self.cell('fl_full', 1.5, '11', 0.5, choice=5, shield=10)
        cv[('fl_heuristic_k1.5_s11', 'r1')] = self.cell('fl_heuristic', 1.5, '11', 0.5, choice=None, shield=10)
        cv[('fl_full_k2.0_s11', 'r1')] = self.cell('fl_full', 2.0, '11', 0.5, choice=5, shield=10)
        cv[('fixed_deep_k1.0_s11', 'r1')] = self.cell('fixed_deep', 1.0, '11', None)
        theirs = {'k1.0': {'routes': 3, 'fl_full': {'mean': 0.4, 'pooled': 0.35},
                           'fl_heuristic': {'mean': 0.3, 'pooled': 9 / 30}, 'mean_difference': 0.1},
                  'k1.5': {'routes': 1, 'fl_full': {'mean': 0.5, 'pooled': 0.5},
                           'fl_heuristic': {'mean': 0.5, 'pooled': None}, 'mean_difference': 0.0}}
        aj = {'manipulation': {'analysed_runs': {'p_both_shared_shield': theirs}}}
        cmp = self.run_cmp(VT.compare_p_both_shared_shield, aj, cv)
        self.assertEqual(cmp.rows, [])
        self.assertEqual(cmp.summary()['compared'], 12)
        theirs['k1.0']['routes'] = 4             # r3 counted although fl_heuristic has no cell there
        theirs['k1.0']['fl_full']['mean'] = 0.475
        theirs['k1.5']['fl_heuristic']['pooled'] = 0.5
        cmp = self.run_cmp(VT.compare_p_both_shared_shield, aj, cv)
        self.assertEqual(sorted((x['key'], x['field']) for x in cmp.rows),
                         [('p_both_shared_shield:k1.0', 'fl_full_mean'), ('p_both_shared_shield:k1.0', 'routes'),
                          ('p_both_shared_shield:k1.5', 'fl_heuristic_pooled')])
        theirs['k2.0'] = {'routes': 0}
        del theirs['k1.0'], theirs['k1.5']
        cmp = self.run_cmp(VT.compare_p_both_shared_shield, aj, cv)
        # k1.0 and k1.5 absent on the other side: every value differs (the heuristic pooled P_both of k1.5 is None on
        # both sides); k2.0 has no pair here and 'routes' 0 there.
        self.assertEqual(sorted(x['key'] for x in cmp.rows), ['p_both_shared_shield:k1.0'] * 6
                         + ['p_both_shared_shield:k1.5'] * 5)

    def test_gpu_descriptive(self):
        by_cond = {}
        for route, full, age, ev in (('r1', 0.5, 0.6, 0.55), ('r2', 0.7, 0.6, None)):
            by_cond.setdefault('fl_full_k1.0_s11', {})[route] = self.cell('fl_full', 1.0, '11', 0.3, gpu=full)
            by_cond.setdefault('age_only_k1.0_s11', {})[route] = self.cell('age_only', 1.0, '11', 0.3, gpu=age)
            if ev is not None:
                by_cond.setdefault('event_triggered_k1.0_s11', {})[route] = self.cell('event_triggered', 1.0, '11',
                                                                                       None, gpu=ev)
        rows = [{'contrast': 'fl_full_minus_age_only_k1.0_s11_all', 'metric': 'gpu_usage', 'label': 'descriptive',
                 'n': 2, 'mean': 0.0},
                {'contrast': 'fl_full_minus_event_triggered_k1.0_s11_all', 'metric': 'gpu_usage',
                 'label': 'descriptive', 'n': 1, 'mean': -0.05}]
        aj = {'decisions': {'H1': {'finding_2': {'gpu_usage_descriptive': rows}}},
              'route_table': {'subsets': {'all': ['r1', 'r2']}}}
        cmp = self.run_cmp(VT.compare_gpu_descriptive, aj, by_cond, {})
        self.assertEqual(cmp.rows, [])
        self.assertEqual(cmp.summary()['compared'], 9)
        rows[0]['mean'] = 0.0015      # within the in-flight bounds of the mean difference (+-0.002)
        rows[1].update(label='improves', n=2)
        cmp = self.run_cmp(VT.compare_gpu_descriptive, aj, by_cond, {})
        self.assertEqual(sorted(x['field'] for x in cmp.rows), ['label', 'n'])
        self.assertEqual(cmp.summary()['agree_within_inflight_bounds'], 1)
        rows[0]['mean'] = 0.0025      # beyond them
        rows.pop()
        cmp = self.run_cmp(VT.compare_gpu_descriptive, aj, by_cond, {})
        self.assertEqual(sorted(x['field'] for x in cmp.rows), ['contrasts', 'mean'])
        del aj['decisions']
        cmp = self.run_cmp(VT.compare_gpu_descriptive, aj, by_cond, {})
        self.assertEqual([(x['field'], x['note']) for x in cmp.rows], [('section', 'section absent')])

    def test_parse_contrast_and_condition_parts(self):
        self.assertEqual(VT.parse_contrast('fl_full_minus_age_only_k1.0_s11_all'),
                         ('fl_full_k1.0_s11', 'age_only_k1.0_s11', 'all'))
        self.assertEqual(VT.parse_contrast('fl_full_minus_fixed_deep_k1.5_s11_E'),
                         ('fl_full_k1.5_s11', 'fixed_deep_k1.5_s11', 'E'))
        self.assertIsNone(VT.parse_contrast('fl_full_k1.0_s11'))
        self.assertEqual(VT.condition_parts('fl_heuristic_k2.0_s12'), ('fl_heuristic', 2.0, '12'))
        self.assertEqual(VT.condition_parts('x_k1.0_s11', {'arm': 'fl_full', 'kappa': '1.5', 'seed': '12'}),
                         ('fl_full', 1.5, '12'))


class Guard(Base):
    def registered_test_route(self):
        with open(os.path.join(ROOT, VT.REGISTERED_SPLIT)) as f:
            return str(json.load(f)['test'][0]['route_id'])

    def make_freeze(self, runs, split, cite=True, seal_ok=True, name='final_20261201T000000', **patch):
        """A record (in a final_<stamp> directory) of the jobs runs {job: run_dir} (patch replaces fields), a
        development protocol whose Sec. 13 cites it (cite) and its seal (seal_ok: the seal records the protocol's
        sha256); returns (record, protocol, seal)."""
        d = os.path.join(self.tmp, name)
        os.makedirs(d, exist_ok=True)
        code = os.path.join(self.tmp, 'code_aggregate.py')
        with open(code, 'w') as f:
            f.write('# analysis code\n')
        doc = {'schema': VT.FREEZE_SCHEMA, 'frozen': '2026-12-01T00:00:00+0800', 'trigger': 'all_final',
               'cut_amendment': None, 'job_files': {'test_jobs/b_test.jsonl': '1' * 64},
               'jobs': {j: {'job_file': 'test_jobs/b_test.jsonl', 'outcome': 'ok', 'run_dir': rd}
                        for j, rd in runs.items()},
               'analysis_code': {code: VT.sha256_file(code)}, 'route_split_sha256': VT.sha256_file(split)}
        doc.update(patch)
        rec = os.path.join(d, VT.FREEZE_RECORD_NAME)
        with open(rec, 'w') as f:
            json.dump(doc, f)
        sha = VT.sha256_file(rec)
        protocol = os.path.join(self.tmp, 'PROTOCOL_dev.md')
        with open(protocol, 'w') as f:
            f.write('# Protocol\n\n## 12. Provenance\n\nnot here\n\n## 13. Registration and amendments\n\n'
                    '**Analysis freeze.** record sha256 `%s`.\n\n## 14. Other\n' % (sha if cite else '0' * 64))
        seal = os.path.join(self.tmp, 'SEAL_dev.sha256')
        with open(seal, 'w') as f:
            f.write('%s  %s\n' % (VT.sha256_file(protocol) if seal_ok else '2' * 64, protocol))
        return rec, protocol, seal

    def assert_refused(self, code, out, needle=None):
        self.assertEqual(code, VT.EXIT_REFUSED)
        self.assertEqual(sorted(os.listdir(out)), ['guard_log.jsonl'])
        with open(os.path.join(out, 'guard_log.jsonl')) as f:
            last = json.loads(f.readlines()[-1])
        self.assertEqual(last['decision'], 'refused')
        if needle:
            self.assertTrue(any(needle in p for p in last['problems']), last['problems'])

    def test_registered_test_route_refused_without_freeze(self):
        d = make_run(self.tmp, 'reg', route=self.registered_test_route())
        self.assert_refused(VT.main(['--run-dir', d, '--out', self.out()]), self.out(), 'no --analysis-freeze')

    def test_registered_test_route_never_released_under_test_options(self):
        # A valid development record (cited by a development protocol copy) never releases a registered test route.
        d = make_run(self.tmp, 'reg', route=self.registered_test_route())
        split = os.path.join(self.tmp, 'split.json')
        with open(split, 'w') as f:
            json.dump({'test': [{'route_id': self.registered_test_route()}]}, f)
        rec, protocol, seal = self.make_freeze({'j': d}, split)
        code = VT.main(['--run-dir', d, '--out', self.out(), '--route-split', split, '--protocol', protocol,
                        '--seal', seal, '--analysis-freeze', rec])
        self.assert_refused(code, self.out(), 'does not cite the record')

    def test_synthetic_test_route_grant_and_refusals(self):
        d = make_run(self.tmp, 'syn', route='990001', summary=summary_from(LEASE_EXPECTED))
        split = os.path.join(self.tmp, 'split.json')
        with open(split, 'w') as f:
            json.dump({'test': [{'route_id': '990001'}]}, f)

        def run(out, rec=None, protocol=None, seal=None):
            argv = ['--run-dir', d, '--route-split', split, '--out', self.out(out)]
            for opt, v in (('--analysis-freeze', rec), ('--protocol', protocol), ('--seal', seal)):
                if v:
                    argv += [opt, v]
            return VT.main(argv)
        self.assert_refused(run('o0'), self.out('o0'), 'no --analysis-freeze')
        cases = [('o1', {'cite': False}, 'does not cite the record'),
                 ('o2', {'seal_ok': False}, 'does not equal the sha256 its seal'),
                 ('o3', {'schema': 'other/1'}, 'schema'),
                 ('o4', {'trigger': 'cut'}, 'without its amendment'),
                 ('o5', {'route_split_sha256': '3' * 64}, 'route_split_sha256'),
                 ('o6', {'analysis_code': {os.path.join(self.tmp, 'nofile.py'): '4' * 64}}, 'analysis code'),
                 ('o7', {'jobs': {'j': {'job_file': 'other.jsonl', 'outcome': 'ok', 'run_dir': d}}},
                  'without a recorded job file'),
                 ('o12', {'frozen': ' '}, 'no freeze time'),
                 ('o13', {'job_files': {'test_jobs/b_test.jsonl': 'b' * 63 + 'X'}}, 'job_files is not')]
        for out, patch, needle in cases:
            with self.subTest(case=out):
                rec, protocol, seal = self.make_freeze({'j': d}, split, name='final_' + out, **patch)
                self.assert_refused(run(out, rec, protocol, seal), self.out(out), needle)
        # A valid record that does not cover the run directory.
        rec, protocol, seal = self.make_freeze({'j': os.path.join(self.tmp, 'other_run')}, split, name='final_o8')
        self.assert_refused(run('o8', rec, protocol, seal), self.out('o8'), 'is not a recorded run')
        # A valid record that covers it: granted, by the record file and by its final_<stamp> directory.
        rec, protocol, seal = self.make_freeze({'j': d}, split, name='final_ok')
        self.assertEqual(run('o9', rec, protocol, seal), VT.EXIT_AGREE)
        rep = self.report(self.out('o9'))
        self.assertEqual(rep['guard']['decision'], 'granted')
        self.assertEqual(rep['guard']['freeze']['sha256'], VT.sha256_file(rec))
        self.assertEqual(rep['status'], 'development')
        self.assertEqual(run('o10', os.path.dirname(rec), protocol, seal), VT.EXIT_AGREE)
        # Without the test options the registered protocol judges the record: refused.
        self.assert_refused(run('o11', rec), self.out('o11'), 'does not cite the record')

    def test_record_covers_runner_and_runs_csv_jobs(self):
        d = make_run(self.tmp, 'syn', route='990001', summary=summary_from(LEASE_EXPECTED))
        split = os.path.join(self.tmp, 'split.json')
        with open(split, 'w') as f:
            json.dump({'test': [{'route_id': '990001'}]}, f)
        agg = os.path.join(self.tmp, 'agg')
        os.makedirs(agg)
        write_csv(os.path.join(agg, 'runs.csv'), [runs_row('job1', d, LEASE_EXPECTED)])
        base = ['--agg', agg, '--route-split', split]
        rec, protocol, seal = self.make_freeze({'job_other': d}, split, name='final_a')
        self.assert_refused(VT.main(base + ['--out', self.out('o1'), '--analysis-freeze', rec, '--protocol', protocol,
                                            '--seal', seal]), self.out('o1'), 'job job1 is not in the record')
        other = make_run(self.tmp, 'other', route='990001')
        rec, protocol, seal = self.make_freeze({'job1': other}, split, name='final_b')
        self.assert_refused(VT.main(base + ['--out', self.out('o2'), '--analysis-freeze', rec, '--protocol', protocol,
                                            '--seal', seal]), self.out('o2'), 'is not the recorded run of job job1')
        rec, protocol, seal = self.make_freeze({'job1': d}, split, name='final_c')
        self.assertEqual(VT.main(base + ['--out', self.out('o3'), '--analysis-freeze', rec, '--protocol', protocol,
                                         '--seal', seal]), VT.EXIT_AGREE, self.diffs(self.out('o3')))
        # A job recorded as cut that names no run passes (trigger cut with its amendment); one with a run does not.
        write_csv(os.path.join(agg, 'runs.csv'), [runs_row('job1', d, LEASE_EXPECTED),
                                                   {'job': 'job2', 'route_id': '990001', 'analysis_use': 'False'}])
        jobs = {'job1': {'job_file': 'test_jobs/b_test.jsonl', 'outcome': 'ok', 'run_dir': d},
                'job2': {'job_file': 'test_jobs/b_test.jsonl', 'outcome': 'cut', 'run_dir': None}}
        rec, protocol, seal = self.make_freeze({}, split, name='final_d', jobs=jobs, trigger='cut',
                                               cut_amendment='Amendment A99')
        self.assertEqual(VT.main(base + ['--out', self.out('o4'), '--analysis-freeze', rec, '--protocol', protocol,
                                         '--seal', seal]), VT.EXIT_AGREE, self.diffs(self.out('o4')))
        jobs['job1']['outcome'] = 'cut'
        rec, protocol, seal = self.make_freeze({}, split, name='final_e', jobs=jobs, trigger='cut',
                                               cut_amendment='Amendment A99')
        self.assert_refused(VT.main(base + ['--out', self.out('o5'), '--analysis-freeze', rec, '--protocol', protocol,
                                            '--seal', seal]), self.out('o5'), 'recorded as cut but names a run')

    def test_runner_run_directory_is_covered(self):
        # The final runner record of job jA names the run directory recorded for job jB: not covered.
        da = make_run(self.tmp, 'run_a', route='990001', summary=summary_from(LEASE_EXPECTED))
        db = make_run(self.tmp, 'run_b', route='990001', summary=summary_from(LEASE_EXPECTED))
        split = os.path.join(self.tmp, 'split.json')
        with open(split, 'w') as f:
            json.dump({'test': [{'route_id': '990001'}]}, f)
        q = os.path.join(self.tmp, 'queue')
        os.makedirs(q)
        rec, protocol, seal = self.make_freeze({'jA': da, 'jB': db}, split)
        opts = ['--queue', q, '--route-split', split, '--analysis-freeze', rec, '--protocol', protocol, '--seal', seal]
        for out, run_dir, refused in (('o1', db, True), ('o2', da, False)):
            with self.subTest(run_dir=os.path.basename(run_dir)):
                write_jsonl(os.path.join(q, 'status.jsonl'), [{'event': 'end', 'id': 'jA', 'final': True,
                                                               'outcome': 'ok', 'run_dir': run_dir,
                                                               'job': {'route_id': '990001'}}])
                code = VT.main(opts + ['--out', self.out(out)])
                if refused:
                    self.assert_refused(code, self.out(out), 'is not the recorded run of job jA')
                else:
                    self.assertEqual(code, VT.EXIT_AGREE, self.diffs(self.out(out)))

    def test_route_ids_in_decimal_text_are_guarded(self):
        # A registered test route written as decimal text, in runs.csv, a CSV route list, a dropped_routes text and a
        # runner record: refused; a synthetic split whose route ids are numbers guards the same routes.
        test_route = self.registered_test_route()
        self.assertEqual([VT.route_text(x) for x in (test_route + '.0', ' %s ' % test_route, float(test_route),
                                                     int(test_route), '%s.5' % test_route, 'r12', True, '')],
                         [test_route] * 4 + ['%s.5' % test_route, 'r12', None, None])
        agg = os.path.join(self.tmp, 'agg')
        os.makedirs(agg)
        write_csv(os.path.join(agg, 'runs.csv'), [{'job': 'j', 'route_id': test_route + '.0', 'analysis_use': 'False'}])
        self.assert_refused(VT.main(['--agg', agg, '--out', self.out('o1')]), self.out('o1'), 'registered test routes')
        ana = os.path.join(self.tmp, 'ana')
        os.makedirs(ana)
        write_csv(os.path.join(ana, 'per_ability.csv'), [{'metric': 'dmr', 'routes': '930000|%s.0' % test_route,
                                                          'dropped_routes': ''}])
        self.assert_refused(VT.main(['--analysis', ana, '--out', self.out('o2')]), self.out('o2'),
                            'registered test routes')
        write_csv(os.path.join(ana, 'per_ability.csv'), [{'metric': 'dmr', 'routes': '930000',
                                                          'dropped_routes': '%s.0: no_row' % test_route}])
        self.assert_refused(VT.main(['--analysis', ana, '--out', self.out('o3')]), self.out('o3'),
                            'registered test routes')
        q = os.path.join(self.tmp, 'queue')
        os.makedirs(q)
        write_jsonl(os.path.join(q, 'status.jsonl'), [{'event': 'end', 'id': 'j', 'final': False, 'outcome': 'ok',
                                                       'job': {'route_id': float(test_route)}}])
        self.assert_refused(VT.main(['--queue', q, '--out', self.out('o4')]), self.out('o4'), 'registered test routes')
        split = os.path.join(self.tmp, 'split.json')
        with open(split, 'w') as f:
            json.dump({'test': [{'route_id': 990001.0}, 990002]}, f)
        self.assertEqual(VT.load_test_routes(split), {'990001', '990002'})

    def test_cells_jobs_are_covered(self):
        # cells.csv names a job of a synthetic test route that the record does not hold: refused.
        split = os.path.join(self.tmp, 'split.json')
        with open(split, 'w') as f:
            json.dump({'test': [{'route_id': '990001'}]}, f)
        ana = os.path.join(self.tmp, 'ana')
        os.makedirs(ana)
        write_csv(os.path.join(ana, 'cells.csv'), [{'condition': 'fl_full_k1.0_s11', 'route_id': '990001',
                                                    'status': 'used', 'jobs': json.dumps(['job_x'])}])
        rec, protocol, seal = self.make_freeze({'job_y': os.path.join(self.tmp, 'r')}, split)
        argv = ['--analysis', ana, '--route-split', split, '--analysis-freeze', rec, '--protocol', protocol,
                '--seal', seal]
        self.assert_refused(VT.main(argv + ['--out', self.out('o1')]), self.out('o1'), 'job job_x is not in the record')

    def test_analysis_route_lists_are_guarded(self):
        # Refused as registered test routes (not only as values without a route).
        test_route = self.registered_test_route()
        for name, row in (('per_scenario.csv', {'condition': 'fl_full_k1.0_s11', 'route_id': test_route}),
                          ('paired_differences.csv', {'contrast': 'x', 'metric': 'dmr', 'route_id': test_route}),
                          ('per_ability.csv', {'metric': 'dmr', 'routes': '930000|%s' % test_route})):
            with self.subTest(name=name):
                ana = os.path.join(self.tmp, 'ana_' + name)
                os.makedirs(ana)
                write_csv(os.path.join(ana, name), [row])
                out = self.out('o_' + name)
                self.assert_refused(VT.main(['--analysis', ana, '--out', out]), out, 'registered test routes')
                with open(os.path.join(out, 'guard_log.jsonl')) as f:
                    self.assertEqual(json.loads(f.readlines()[-1])['inputs_without_a_route'], 0)

    def test_runs_csv_test_route_flag_is_guarded(self):
        agg = os.path.join(self.tmp, 'agg')
        os.makedirs(agg)
        write_csv(os.path.join(agg, 'runs.csv'), [{'job': 'j', 'route_id': '990777', 'test_route': 'True'}])
        self.assert_refused(VT.main(['--agg', agg, '--out', self.out()]), self.out())

    def test_input_errors_and_protected_output(self):
        agg = os.path.join(self.tmp, 'agg')
        os.makedirs(agg)
        write_csv(os.path.join(agg, 'runs.csv'), [{'run': 'x'}])
        self.assertEqual(VT.main(['--agg', agg, '--out', self.out()]), VT.EXIT_ERROR)
        self.assertEqual(VT.main(['--queue', os.path.join(self.tmp, 'noqueue'), '--out', self.out('o2')]),
                         VT.EXIT_ERROR)
        for p in ('outputs/framelease_v4/tuning/x', 'outputs/framelease_v4/queue_p1/x', 'framelease_v4/analysis/x',
                  'outputs/framelease_v4/analysis/final_x/y'):
            with self.subTest(p=p):
                self.assertEqual(VT.main(['--out', os.path.join(ROOT, p)]), VT.EXIT_ERROR)
                self.assertFalse(os.path.exists(os.path.join(ROOT, p)))

    def test_analysis_json_and_dropped_route_lists_are_guarded(self):
        # A registered test route named only by one route list of the analysis outputs: refused.
        test_route = self.registered_test_route()
        cases = {
            'route_table': {'route_table': {'subsets': {'all': ['930000', test_route]}}},
            'cells_used': {'cells': {'fl_full_k1.0_s11': {'used': [test_route], 'routes': 1}}},
            'cells_not_used': {'cells': {'fl_full_k1.0_s11': {'not_used': [{'route_id': test_route,
                                                                              'status': 'missing'}]}}},
            'dropped': {'secondary': [{'contrast': 'x', 'metric': 'dmr', 'dropped': [{'route_id': test_route}]}]},
            'nested': {'manipulation': {'analysed_runs': {'k1.0': {'route_ids': ['930000', test_route]}}}},
            'number': {'per_ability': [{'metric': 'dmr', 'routes': [930000, float(test_route)]}]},
            'dropped_text': {'descriptive': [{'contrast': 'x', 'dropped_routes': '930001: no_row | %s: no_row'
                                              % test_route}]},
        }
        for name, aj in cases.items():
            with self.subTest(case=name):
                ana = os.path.join(self.tmp, 'ana_' + name)
                os.makedirs(ana)
                with open(os.path.join(ana, 'analysis.json'), 'w') as f:
                    json.dump(aj, f)
                out = self.out('o_' + name)
                self.assert_refused(VT.main(['--analysis', ana, '--out', out]), out, 'registered test routes')
        ana = os.path.join(self.tmp, 'ana_csv')
        os.makedirs(ana)
        write_csv(os.path.join(ana, 'secondary.csv'), [{'contrast': 'x', 'metric': 'dmr', 'mean': 0.1,
                                                        'dropped_routes': '930001: cell not used | %s: no_row'
                                                        % test_route}])
        self.assert_refused(VT.main(['--analysis', ana, '--out', self.out('o_csv')]), self.out('o_csv'),
                            'registered test routes')

    def test_analysis_outputs_without_routes_fail_closed(self):
        # Contrast values that name no route, and a route entry without an id: judged as registered test routes.
        ana = os.path.join(self.tmp, 'ana_values')
        os.makedirs(ana)
        write_csv(os.path.join(ana, 'secondary.csv'), [{'contrast': 'fl_full_minus_fixed_deep_k1.0_s11_all',
                                                        'metric': 'gpu_usage', 'mean': 0.1, 'dropped_routes': ''}])
        self.assert_refused(VT.main(['--analysis', ana, '--out', self.out('o1')]), self.out('o1'),
                            'inputs without a route')
        ana = os.path.join(self.tmp, 'ana_noid')
        os.makedirs(ana)
        with open(os.path.join(ana, 'analysis.json'), 'w') as f:
            json.dump({'secondary': [{'contrast': 'x', 'dropped': [{'route_id': None}]}]}, f)
        self.assert_refused(VT.main(['--analysis', ana, '--out', self.out('o2')]), self.out('o2'),
                            'inputs without a route')
        # No value and no route: nothing to guard (the absent files are differences).
        ana = os.path.join(self.tmp, 'ana_empty')
        os.makedirs(ana)
        with open(os.path.join(ana, 'analysis.json'), 'w') as f:
            json.dump({'status': 'development'}, f)
        self.assertEqual(VT.main(['--analysis', ana, '--out', self.out('o3')]), VT.EXIT_DIFFER)
        self.assertEqual(self.report(self.out('o3'))['guard']['decision'], 'granted')

    def test_inputs_without_a_route_fail_closed(self):
        d = make_run(self.tmp, 'noroute', summary=summary_from(LEASE_EXPECTED))
        with open(os.path.join(d, 'config.json')) as f:
            cfg = json.load(f)
        del cfg['route']
        with open(os.path.join(d, 'config.json'), 'w') as f:
            json.dump(cfg, f)
        self.assert_refused(VT.main(['--run-dir', d, '--out', self.out('o1')]), self.out('o1'),
                            'inputs without a route')
        # A runs.csv row with neither a route id nor a test-route flag; with the flag False it is a training row.
        agg = os.path.join(self.tmp, 'agg')
        os.makedirs(agg)
        write_csv(os.path.join(agg, 'runs.csv'), [{'job': 'j', 'route_id': '', 'analysis_use': 'False'}])
        self.assert_refused(VT.main(['--agg', agg, '--out', self.out('o2')]), self.out('o2'), 'inputs without a route')
        write_csv(os.path.join(agg, 'runs.csv'), [{'job': 'j', 'route_id': '', 'test_route': 'False',
                                                   'analysis_use': 'False'}])
        self.assertEqual(VT.main(['--agg', agg, '--out', self.out('o3')]), VT.EXIT_AGREE)
        # A runner record with neither a route id nor a training flag.
        q = os.path.join(self.tmp, 'queue')
        os.makedirs(q)
        write_jsonl(os.path.join(q, 'status.jsonl'), [{'event': 'end', 'id': 'j', 'final': True, 'outcome': 'ok',
                                                       'job': {}}])
        self.assert_refused(VT.main(['--queue', q, '--out', self.out('o4')]), self.out('o4'), 'inputs without a route')

    def test_failed_final_job_without_run_directory(self):
        # The P7 guard records a final failure whose runner record names no run directory with run_dir null: a valid
        # record; an input that names a run directory for that job is not covered.
        d = make_run(self.tmp, 'syn', route='990001', summary=summary_from(LEASE_EXPECTED))
        split = os.path.join(self.tmp, 'split.json')
        with open(split, 'w') as f:
            json.dump({'test': [{'route_id': '990001'}]}, f)
        agg = os.path.join(self.tmp, 'agg')
        os.makedirs(agg)
        rows = [runs_row('job1', d, LEASE_EXPECTED), {'job': 'job2', 'route_id': '990001', 'analysis_use': 'False'}]
        write_csv(os.path.join(agg, 'runs.csv'), rows)
        jobs = {'job1': {'job_file': 'test_jobs/b_test.jsonl', 'outcome': 'ok', 'run_dir': d},
                'job2': {'job_file': 'test_jobs/b_test.jsonl', 'outcome': 'agent_crashed', 'run_dir': None}}
        base = ['--agg', agg, '--route-split', split]
        rec, protocol, seal = self.make_freeze({}, split, name='final_f1', jobs=jobs)
        opts = ['--analysis-freeze', rec, '--protocol', protocol, '--seal', seal]
        self.assertEqual(VT.main(base + opts + ['--out', self.out('o1')]), VT.EXIT_AGREE, self.diffs(self.out('o1')))
        rows[1]['run_dir'] = make_run(self.tmp, 'crashed', route='990001')
        write_csv(os.path.join(agg, 'runs.csv'), rows)
        self.assert_refused(VT.main(base + opts + ['--out', self.out('o2')]), self.out('o2'),
                            'without a run directory but names one')
        # Outcome ok without a run directory: the record is not valid.
        jobs['job1']['run_dir'] = None
        rec, protocol, seal = self.make_freeze({}, split, name='final_f3', jobs=jobs)
        self.assert_refused(VT.main(base + ['--analysis-freeze', rec, '--protocol', protocol, '--seal', seal,
                                            '--out', self.out('o3')]), self.out('o3'), '(outcome ok) a run directory')

    def test_runs_csv_values_refused_under_the_final_record(self):
        # A release with status 'final' (registered record) recomputes the run directories: --runs-csv-values is
        # refused there and accepted otherwise.
        d = make_run(self.tmp, 'run', summary=summary_from(LEASE_EXPECTED))
        agg = os.path.join(self.tmp, 'agg')
        os.makedirs(agg)
        write_csv(os.path.join(agg, 'runs.csv'), [runs_row('job1', d, LEASE_EXPECTED)])
        original = VT.guard

        def final_guard(*args, **kw):
            return True, 'final', {'decision': 'granted', 'problems': [], 'registered_test_route_inputs': 1,
                                   'inputs_without_a_route': 0, 'synthetic_test_route_inputs': 0, 'freeze': None}
        VT.guard = final_guard
        try:
            self.assert_refused(VT.main(['--agg', agg, '--runs-csv-values', '--out', self.out('o1')]), self.out('o1'),
                                '--runs-csv-values')
            self.assertEqual(VT.main(['--agg', agg, '--out', self.out('o2')]), VT.EXIT_AGREE)
            self.assertEqual(self.report(self.out('o2'))['status'], 'final')
        finally:
            VT.guard = original
        self.assertEqual(VT.main(['--agg', agg, '--runs-csv-values', '--out', self.out('o3')]), VT.EXIT_AGREE)


def one_commit_run(root, name, capture=0.05, deadline=1.25, plan=None, actor=None, n_ticks=40, commits=None,
                   jobs=None, plans=None, **kw):
    """A lease-arm run with one commit (job 1, depth 1, committed 0.01 s after capture) of plan (default straight
    2 m/s) on n_ticks ticks; the default actor log holds vehicle 7 standing 7.92 m ahead of the hero at the origin."""
    commits = commits or [{'job_id': 1, 'depth': 1, 'commit_s': capture + 0.01, 'capture_s': capture,
                           'deadline_s': deadline}]
    jobs = jobs or [{'job_id': 1, 'prefix': (0.0, 0.04, 0.001), 'steps': [(capture, 0.005, 0.001)]}]
    plans = plans or {(1, 1): plan or straight(2.0)}
    return make_run(root, name, commits=commits, jobs=jobs, plans=plans, inflight=None, gpu_ticks={},
                    decisions=DECISIONS[-1:], n_ticks=n_ticks,
                    actor=actor or (lambda k, t: actor_row(k, t, actors=((7, 792, 0, 0),))), **kw)


class Validity(Base):
    """Sec. 6.3 known answers: geometry, footprint conventions, censoring, bounds and their comparisons."""

    @staticmethod
    def box(cx, cy, h, hl, hw):
        return tuple(VT.np.asarray([v], dtype=float) for v in (cx, cy, h, hl, hw))

    def test_box_distance_known_answers(self):
        cases = [((0, 0, 0, 2, 1), (5, 0, 0, 2, 1), 1.0),                       # parallel, gap 1
                 ((0, 0, 0, 2, 1), (3, 0, 0, 2, 1), 0.0),                       # overlap
                 ((0, 0, 0, 2, 1), (4, 0, 0, 2, 1), 0.0),                       # touching
                 ((0, 0, 0, 2, 1), (0, 5, math.pi / 2, 2, 1), 2.0),             # rotated: spans y 3..7
                 ((0, 0, 0, 1, 1), (3, 3, 0, 1, 1), math.sqrt(2.0)),            # corner to corner
                 ((0, 0, 0, 1, 1), (1 + math.sqrt(2.0) + 0.3, 0, math.pi / 4, 1, 1), 0.3)]   # vertex to face
        for a, b, want in cases:
            with self.subTest(a=a, b=b):
                self.assertAlmostEqual(float(VT.box_distance(self.box(*a), self.box(*b))[0]), want, places=9)
                self.assertAlmostEqual(float(VT.box_distance(self.box(*b), self.box(*a))[0]), want, places=9)

    def test_footprint_placement_and_heading_conventions(self):
        half, off = (2.45, 0.92), (0.0, 0.0)
        cx, cy, h, hl, hw = VT.plan_footprint(straight(4.0), (0.0, 0.0, 0.0), half, off)
        self.assertAlmostEqual(cx[10], 2.0, places=12)       # box centre 0.39 m ahead of the LiDAR, which moves 4 tau
        self.assertAlmostEqual(cx[45], 9.0, places=12)
        self.assertTrue(VT.np.allclose(cy, 0.0) and VT.np.allclose(h, 0.0))
        self.assertEqual((hl[0], hw[0]), half)
        # Facing -y (right-handed): the plan moves along -y; the centre offset turns with the heading.
        cx, cy, h, _, _ = VT.plan_footprint(straight(4.0), (10.0, -5.0, -math.pi / 2), half, (-0.01, 0.0))
        self.assertAlmostEqual(cx[10], 10.0, places=12)
        self.assertAlmostEqual(cy[10], -5.0 - 2.0 + 0.01, places=12)
        # Slow first chords (0.2 m/s; the second points right) keep the capture heading; the knot sample 20 takes the
        # direction of p21 - p19 = (0.15, 0.15) - (0.09, 0.10) (central difference, 0.78 m/s); the chord 45 degrees to
        # the right turns the box after it; tau 0 is the capture pose even when the first chord turns.
        plan = [[0.0, 0.1], [0.1, 0.1], [0.6, 0.6], [1.1, 1.1], [1.6, 1.6], [2.1, 2.1]]
        _, _, h, _, _ = VT.plan_footprint(plan, (0.0, 0.0, 0.0), half, off)
        self.assertTrue(VT.np.allclose(h[:20], 0.0))
        self.assertAlmostEqual(h[20], math.atan2(0.05, 0.06) - math.pi / 2, places=12)
        self.assertTrue(VT.np.allclose(h[21:], -math.pi / 4))
        _, _, h, _, _ = VT.plan_footprint([[1.0, 1.0]] + straight(2.0)[1:], (0.0, 0.0, 0.0), half, off)
        self.assertAlmostEqual(h[0], 0.0, places=12)
        self.assertAlmostEqual(h[1], -math.pi / 4, places=12)
        # The knot between a straight chord and a 90-degree right turn: p11 - p9 = (0.4, 2.0) - (0, 1.8).
        _, _, h, _, _ = VT.plan_footprint([[0.0, 2.0], [4.0, 2.0], [8.0, 2.0], [12.0, 2.0], [16.0, 2.0], [20.0, 2.0]],
                                          (0.0, 0.0, 0.0), half, off)
        self.assertAlmostEqual(h[10], math.atan2(0.2, 0.4) - math.pi / 2, places=12)
        self.assertAlmostEqual(h[9], 0.0, places=12)
        self.assertAlmostEqual(h[11], -math.pi / 2, places=12)
        # The last sample takes the backward difference p60 - p59.
        plan = straight(2.0)[:5] + [[0.5, 6.0]]
        _, _, h, _, _ = VT.plan_footprint(plan, (0.0, 0.0, 0.0), half, off)
        self.assertAlmostEqual(h[60], math.atan2(0.1, 0.05) - math.pi / 2, places=12)
        self.assertAlmostEqual(h[59], math.atan2(0.1, 0.05) - math.pi / 2, places=12)
        self.assertAlmostEqual(h[49], 0.0, places=12)
        # Backward motion reverses: the heading stays forward while the box moves back.
        cx, _, h, _, _ = VT.plan_footprint(straight(-2.0), (0.0, 0.0, 0.0), half, off)
        self.assertTrue(VT.np.allclose(h, 0.0))
        self.assertAlmostEqual(cx[60], -6.0, places=12)

    def assert_v(self, plan, v_true, j):
        """The first crossing v_true lies in the bisection bracket (V_lo, V] of width <= 1e-4 s at sample j."""
        self.assertEqual((plan['status'], plan['j']), ('conflict', j))
        self.assertLess(plan['V_lo'], v_true + 1e-9)
        self.assertGreaterEqual(plan['V'], v_true - 1e-9)
        self.assertLessEqual(plan['V'] - plan['V_lo'], VT.V_RESOLUTION_S + 1e-12)
        self.assertAlmostEqual(plan['V_suf'], max(plan['V'] - 0.5, 0.0), places=12)

    def test_conflict_time_miss_and_eir(self):
        # Vehicle 7.92 m ahead (half length 2.00 m), plan 2 m/s; the documented ego box ends 2.4462 - 0.0063 = 2.4399 m
        # ahead of the hero origin: gap 7.92 - 2.00 - 2.4399 - 2 tau = 3.4801 - 2 tau reaches d_safe at
        # V = 1.49005 s (first conflicting sample j = 30, tau 1.5), V_suf = 0.99005. H = 1.2 > V_suf: a miss. Tracked
        # ticks k 2-24 (deadline 1.25), ages 0.05-1.15; ages >= V_suf (1.0-1.15, k 21-24) are invalid: EIR 4 / 23.
        r = VT.recompute_run(one_commit_run(self.tmp, 'miss'))
        self.assertEqual(r['problems'], [])
        self.assertEqual(r['plans_by_status'], {'conflict': 1})
        self.assert_v(r['_plans'][0], 1.49005, 30)
        self.assertEqual((r['conflict_plans'], r['misses'], r['v0_plans'], r['track_ticks']), (1, 1, 0, 23))
        self.assertEqual(r['eir_invalid_ticks'], 4)
        self.assertAlmostEqual(r['eir'], 4 / 23, places=12)
        self.assertEqual(r['r_cond'], 1.0)
        self.assertIsNone(r.get('eir_bounds'))
        self.assertIsNone(r.get('misses_bounds'))
        self.assertEqual((r['miss_resolution_plans'], r['eir_resolution_ticks']), (0, 0))
        # The same box with its location 1 m behind its centre (catalog off +1 m forward): the same V.
        car2 = dict(CAR, c=17, off=[100, 0])
        d = one_commit_run(self.tmp, 'offset', actor=lambda k, t: actor_row(k, t, actors=((17, 692, 0, 0),)),
                           actor_log={'catalog': (CAR, car2)})
        self.assert_v(VT.recompute_run(d)['_plans'][0], 1.49005, 30)
        # H = 0.9 < V_suf: no miss. H = 1.0 = V_suf of the grid sample tau 1.5 but above the V_suf of the first
        # crossing (Sec. 6.3): a miss. The deadline ends tracking before age V_suf in both.
        for name, h, miss in (('nomiss', 0.9, 0), ('gridtie', 1.0, 1)):
            with self.subTest(H=h):
                r = VT.recompute_run(one_commit_run(self.tmp, name, deadline=0.05 + h))
                self.assertEqual((r['conflict_plans'], r['misses'], r['eir_invalid_ticks']), (1, miss, 0))
                self.assertEqual(r['r_cond'], float(miss))
                self.assertIsNone(r.get('misses_bounds'))
        # H = 0.99 lies within 1e-3 s of V_suf (0.99005): the miss rule is within the time resolution. The point value
        # counts no miss; the bounds hold both outcomes.
        r = VT.recompute_run(one_commit_run(self.tmp, 'resolution', deadline=0.05 + 0.99))
        self.assertEqual((r['misses'], r['miss_resolution_plans'], r['misses_bounds']), (0, 1, [0, 1]))
        self.assertEqual((r['r_cond'], r['r_cond_bounds'], r['r_cond_excl_v0_bounds']), (0.0, [0.0, 1.0], [0.0, 1.0]))
        self.assertTrue(r['_plans'][0]['resolution'])
        r = VT.recompute_run(one_commit_run(self.tmp, 'resolution_miss', deadline=0.05 + 0.9905))
        self.assertEqual((r['misses'], r['misses_bounds'], r['r_cond_bounds']), (1, [0, 1], [0.0, 1.0]))

    def test_eir_ticks_within_the_resolution_of_v(self):
        # Vehicle 7.84 m ahead: gap 3.4001 - 2 tau reaches d_safe at tau 1.45005, 0.05 ms after the clear sample
        # tau 1.45. The bisection bracket is (1.45, 1.45008]: the tick at age 0.95 lies between the V_suf of the two
        # ends (0.95, 0.95008) and enters the EIR upper bound only; ages 1.0-1.15 are invalid.
        r = VT.recompute_run(one_commit_run(self.tmp, 'band', actor=lambda k, t: actor_row(
            k, t, actors=((7, 784, 0, 0),))))
        p = r['_plans'][0]
        self.assert_v(p, 1.45005, 30)
        self.assertAlmostEqual(p['V_lo'], 1.45, places=12)
        self.assertEqual((r['eir_invalid_ticks'], r['eir_resolution_ticks'], r['track_ticks']), (4, 1, 23))
        self.assertEqual(r['eir_bounds'], [4 / 23, 5 / 23])
        self.assertEqual(r['eir_invalid_ticks_bounds'], [4, 5])

    def lease_file(self, name, shape):
        path = os.path.join(self.tmp, name)
        with open(path, 'w') as f:
            json.dump({'d_safe_m': 0.5, 'dt_s': 0.05, '_ego_shape': shape} if shape is not None else {'d_safe_m': 0.5},
                      f)
        return path

    def with_lease_file(self, name, path, **kw):
        """one_commit_run whose config names the lease parameter file path."""
        d = one_commit_run(self.tmp, name, **kw)
        cfg_path = os.path.join(d, 'config.json')
        with open(cfg_path) as f:
            cfg = json.load(f)
        cfg['agent_config']['lease_params_path'] = path
        with open(cfg_path, 'w') as f:
            json.dump(cfg, f)
        return d

    def test_ego_box_of_the_lease_parameter_file(self):
        # _ego_shape: half length 2.0 m, centre on the LiDAR (0.39 m behind the hero origin): front 1.61 m ahead of the
        # origin; gap 7.92 - 2.00 - 1.61 - 2 tau = 4.31 - 2 tau -> V = 1.905 (j 39).
        own = self.lease_file('own.json', {'half_length_m': 2.0, 'half_width_m': 1.0, 'center_offset_xy': [0.0, 0.0],
                                           'forward_yaw_rad': math.pi / 2})
        r = VT.recompute_run(self.with_lease_file('own', own, deadline=3.05, n_ticks=80))
        self.assert_v(r['_plans'][0], 1.905, 39)
        self.assertEqual((r['ego_box']['half_m'], r['ego_box']['centre_from_hero_origin_m']),
                         ([2.0, 1.0], [-0.39, 0.0]))
        self.assertIn('_ego_shape of', r['ego_box']['source'])
        # The documented box without forward_yaw_rad (pi / 2 when absent): the same V as the default (1.49005).
        default_axis = self.lease_file('default_axis.json', {'half_length_m': 2.4462, 'half_width_m': 0.9184,
                                                             'center_offset_xy': [0.0, 0.3837]})
        r = VT.recompute_run(self.with_lease_file('default_axis', default_axis))
        self.assert_v(r['_plans'][0], 1.49005, 30)
        self.assertEqual(r['ego_box']['axis_yaw_rad'], 0.0)
        # A length axis other than LiDAR +y (forward_yaw_rad 0, sizes swapped) is another reading of the lease
        # footprint: no Sec. 6.3 values, the reason named.
        swapped = self.lease_file('swapped.json', {'half_length_m': 0.9184, 'half_width_m': 2.4462,
                                                   'center_offset_xy': [0.0, 0.3837], 'forward_yaw_rad': 0.0})
        r = VT.recompute_run(self.with_lease_file('swapped', swapped))
        self.assertEqual((r['problems'], r['validity_available'], r['eir']), ([], False, None))
        self.assertTrue(any('forward_yaw_rad' in x for x in r['validity_problems']), r['validity_problems'])
        # A file without _ego_shape: the documented box.
        bare = self.lease_file('bare.json', None)
        r = VT.recompute_run(self.with_lease_file('bare', bare))
        self.assert_v(r['_plans'][0], 1.49005, 30)
        self.assertIn('documented', r['ego_box']['source'])
        # A named file that does not exist, or an _ego_shape without sizes: no Sec. 6.3 values, the run kept.
        dmr = VT.recompute_run(one_commit_run(self.tmp, 'reference'))['dmr']
        for name, path in (('absent', os.path.join(self.tmp, 'absent.json')),
                           ('broken', self.lease_file('broken.json', {'half_length_m': 2.0}))):
            with self.subTest(case=name):
                r = VT.recompute_run(self.with_lease_file(name, path))
                self.assertEqual(r['problems'], [])
                self.assertFalse(r['validity_available'])
                self.assertTrue(any('lease parameter file' in x for x in r['validity_problems']),
                                r['validity_problems'])
                self.assertIsNone(r['eir'])
                self.assertEqual(r['dmr'], dmr)

    def test_lateral_centre_offset_of_the_lease_box(self):
        # center_offset_xy (LiDAR x right, y forward) [0.5, 0.3837]: the box centre lies 0.5 m right of the hero axis.
        # Its right side is 0.5 + 0.9184 = 1.4184 m right of the axis; a vehicle (half width 0.90) at CARLA y 2.6184 m
        # (right of a hero facing CARLA +x) is 0.3 m from it: V = 0 under the standing plan. The box's left side is
        # 0.4184 m left of the axis; the mirrored vehicle on the left (its side at 1.7184 m) is 1.3 m away: clear.
        path = self.lease_file('lateral.json', {'half_length_m': 2.4462, 'half_width_m': 0.9184,
                                                'center_offset_xy': [0.5, 0.3837], 'forward_yaw_rad': math.pi / 2})
        box, _, problem = VT.lease_ego_box(path)
        self.assertIsNone(problem)
        self.assertAlmostEqual(box[1][0], 0.3837 - 0.39, places=12)
        self.assertAlmostEqual(box[1][1], -0.5, places=12)                # (forward, left): 0.5 m right
        for name, y, want in (('right', 261.84, 'conflict'), ('left', -261.84, 'clear')):
            with self.subTest(side=name):
                d = self.with_lease_file('lat_' + name, path, plan=straight(0.0), deadline=3.05, n_ticks=80,
                                         actor=lambda k, t, y=y: actor_row(k, t, actors=((7, 0, y, 0),)))
                p = VT.recompute_run(d)['_plans'][0]
                self.assertEqual(p['status'], want)
                if want == 'conflict':
                    self.assertEqual((p['j'], p['V']), (0, 0.0))

    def test_heading_interpolation_across_pi_in_the_bracket(self):
        # A left turn whose LiDAR-frame heading passes -x between samples 30 (177.1 deg) and 31 (-174.3 deg) with the
        # first conflict in that bracket; the mirrored scene (right turn through +x, vehicle mirrored) has the same V.
        plan = [[0.0, 2.0], [-1.0, 3.0], [-3.0, 3.4], [-5.0, 3.2], [-7.0, 2.6], [-9.0, 1.8]]
        car = (246.463, -845.37, 26428.941)
        got = []
        for name, sign in (('left', 1.0), ('right', -1.0)):
            d = one_commit_run(self.tmp, 'turn_' + name, plan=[[sign * x, y] for x, y in plan], deadline=3.05,
                               n_ticks=80, actor=lambda k, t, s=sign: actor_row(
                                   k, t, actors=((7, car[0], s * car[1], s * car[2]),)))
            got.append(VT.recompute_run(d)['_plans'][0])
        self.assertEqual([(p['status'], p['j']) for p in got], [('conflict', 31)] * 2)
        self.assertAlmostEqual(got[0]['V'], got[1]['V'], delta=1e-9)
        self.assertAlmostEqual(got[0]['V_lin'], got[1]['V_lin'], delta=1e-9)
        self.assertLess(abs(got[0]['V'] - 1.51984), 2e-4)

    def test_lidar_offset_of_a_turning_plan(self):
        # A 90-degree right turn after the first chord: at tau 1.5 the LiDAR is at plan point (4, 2), i.e. world
        # (-0.39 + 2, -4) for the hero at the origin, heading -90 degrees; the documented box centre lies 0.3837 m
        # ahead of the LiDAR along that heading.
        plan = [[0.0, 2.0], [2.0, 2.0], [4.0, 2.0], [6.0, 2.0], [8.0, 2.0], [10.0, 2.0]]
        cx, cy, h, hl, hw = VT.plan_footprint(plan, (0.0, 0.0, 0.0), VT.EGO_HALF_M, VT.DOCUMENTED_EGO_BOX[1])
        self.assertAlmostEqual(h[30], -math.pi / 2, places=12)
        self.assertAlmostEqual(cx[30], 1.61, places=12)
        self.assertAlmostEqual(cy[30], -4.3837, places=12)
        # The same plan from hero pose (10, 5, +90 degrees): the LiDAR is 0.39 m behind (10, 5) along +y.
        cx, cy, h, _, _ = VT.plan_footprint(plan, (10.0, 5.0, math.pi / 2), VT.EGO_HALF_M, VT.DOCUMENTED_EGO_BOX[1])
        self.assertAlmostEqual(h[30], 0.0, places=12)
        self.assertAlmostEqual(cx[30], 10.0 + 4.0 + 0.3837, places=12)
        self.assertAlmostEqual(cy[30], 5.0 - 0.39 + 2.0, places=12)

    def test_heading_hold_threshold(self):
        # Sideways at 0.4 m/s (below the 0.5 m/s hold speed): the capture heading is kept at every sample; at 0.6 m/s
        # the body turns right.
        half, off = VT.EGO_HALF_M, VT.DOCUMENTED_EGO_BOX[1]
        _, _, h, _, _ = VT.plan_footprint(straight(0.0, lateral=1.2), (0.0, 0.0, 0.0), half, off)
        self.assertTrue(VT.np.allclose(h, 0.0))
        _, _, h, _, _ = VT.plan_footprint(straight(0.0, lateral=1.8), (0.0, 0.0, 0.0), half, off)
        self.assertAlmostEqual(h[0], 0.0, places=12)
        self.assertTrue(VT.np.allclose(h[1:], -math.pi / 2))

    def test_capture_offsets_and_the_last_actor_log_row(self):
        # Capture times carry the runtime's offset (here 7e-7 s) against the 4-decimal actor-log times. The conflict
        # sample tau 1.5 lands on the last row (t 1.55): a conflict, not an unknown sample.
        cap = 0.05 + 7e-7
        r = VT.recompute_run(one_commit_run(self.tmp, 'lastrow', capture=cap, n_ticks=31))
        self.assertEqual(r['plans_by_status'], {'conflict': 1})
        self.assert_v(r['_plans'][0], 1.49005, 30)
        # A clear plan whose last sample (tau 3.0) lands on the last row (t 3.05): clear, not log-censored.
        r = VT.recompute_run(one_commit_run(self.tmp, 'lastrow_clear', capture=cap, n_ticks=61, plan=straight(0.0)))
        self.assertEqual((r['plans_by_status'], r['log_censored_plans']), ({'clear': 1}, 0))

    def test_h_is_deadline_minus_capture(self):
        # Committed 0.30 s after capture: H = deadline - capture = 1.2 > V_suf (0.99005), a miss; the commit delay
        # does not shorten H (deadline - commit = 0.9 would not be).
        commits = [{'job_id': 1, 'depth': 1, 'commit_s': 0.35, 'capture_s': 0.05, 'deadline_s': 1.25}]
        r = VT.recompute_run(one_commit_run(self.tmp, 'late', commits=commits))
        self.assertAlmostEqual(r['_plans'][0]['H'], 1.2, places=12)
        self.assertEqual((r['conflict_plans'], r['misses']), (1, 1))

    def test_interpolated_poses_and_held_actors(self):
        # Rows 0.1 s apart: hero and vehicle 7 turn from yaw 0 to 20 degrees and advance 1 m; walker 8 is logged only
        # in the first row, vehicle 17 only in the second; the third row is ego-only.
        car2 = dict(CAR, c=17)
        rows = [{'t': 1, 's': 0.1, 'e': [0, 0, 0, 0, 0], 'a': [[7, 1000, 0, 0, 0, 0], [8, 0, 500, 0, 0, 0]]},
                {'t': 3, 's': 0.2, 'e': [100, 0, 2000, 0, 0], 'a': [[7, 1000, 0, 2000, 0, 0], [17, 0, -500, 0, 0, 0]]},
                {'t': 5, 's': 0.3, 'e': [200, 0, 2000, 0, 0], 'a': None}]
        checks = {}
        track = VT.ActorTrack({'h': VT.ACTOR_SCHEMA, 'hero': {'id': 1}}, {7: CAR, 8: WALKER, 17: car2}, rows, checks)
        x, y, h = track.ego_pose(0.14)
        self.assertAlmostEqual(x, 0.4, places=12)
        self.assertAlmostEqual(h, -math.radians(8.0), places=12)          # capture heading interpolated
        st = track.states_at(0.14)
        self.assertEqual(sorted(st), [7, 8])                               # 8 held over the nearer half interval
        self.assertAlmostEqual(st[7][0], 10.4, places=12)
        self.assertAlmostEqual(st[7][2], 8.0, places=12)                   # actor yaw interpolated
        cx, cy, hh, _, _ = track.boxes_at(0.14)
        self.assertAlmostEqual(float(hh[0]), -math.radians(8.0), places=12)
        self.assertEqual(sorted(track.states_at(0.16)), [7, 17])
        self.assertEqual(sorted(track.states_at(0.2 + 5e-4)), [7, 17])     # the row within 1 ms
        self.assertIsNone(track.boxes_at(0.25))                            # bracketing row ego-only: unknown
        self.assertIsNone(track.states_at(0.45))                           # after the last row
        # Yaw across +-180 degrees moves along the shorter arc.
        rows = [{'t': 1, 's': 0.1, 'e': [0, 0, 17900, 0, 0], 'a': [[7, 1000, 0, 17900, 0, 0]]},
                {'t': 3, 's': 0.2, 'e': [0, 0, -17900, 0, 0], 'a': [[7, 1000, 0, -17900, 0, 0]]}]
        track = VT.ActorTrack({'h': VT.ACTOR_SCHEMA, 'hero': {'id': 1}}, {7: CAR}, rows, {})
        self.assertAlmostEqual(math.cos(track.ego_pose(0.15)[2]), -1.0, places=12)
        self.assertAlmostEqual(math.cos(math.radians(track.states_at(0.15)[7][2])), -1.0, places=12)

    def test_moving_actor_and_handedness(self):
        # Head-on: vehicle at x = 20 - 4 t (yaw 180), plan 4 m/s from capture 0.05: gap 15.3601 - 8 tau: 0.5601 at
        # tau 1.85, 0.1601 at 1.90 (j 38) -> V = 1.8575125, V_suf = 1.3575125 (the actor moves linearly between rows).
        def head_on(k, t):
            return actor_row(k, t, actors=((7, int(round((20.0 - 4.0 * t) * 100)), 0, 18000),))
        d = one_commit_run(self.tmp, 'headon', plan=straight(4.0), actor=head_on, deadline=3.05)
        r = VT.recompute_run(d)
        self.assert_v(r['_plans'][0], 1.8575125, 38)
        self.assertLess(abs(r['_plans'][0]['V_suf'] - 1.3575125), VT.V_RESOLUTION_S)
        # Hero at CARLA (10, 5) m, yaw 90 deg (facing CARLA +y): the vehicle 6.65 m along CARLA +y conflicts at
        # V = 0.45 under the 4 m/s plan; mirrored along -y it is clear.
        for name, y, want in (('ahead', 500 + 665, 'conflict'), ('behind', 500 - 665, 'clear')):
            with self.subTest(case=name):
                d = one_commit_run(self.tmp, 'yaw90_' + name, plan=straight(4.0), deadline=3.05, n_ticks=80,
                                   actor=lambda k, t, y=y: actor_row(k, t, ego=(1000, 500, 9000),
                                                                     actors=((7, 1000, y, 9000),)))
                v = VT.recompute_run(d)['_plans'][0]
                self.assertEqual(v['status'], want)
                if want == 'conflict':
                    self.assertEqual(v['j'], 9)
        # LiDAR x is the ego's right: hero yaw 0 faces CARLA +x, whose right is CARLA +y. A plan drifting 6 m right
        # reaches a vehicle at CARLA (6, 6); the mirrored vehicle at (6, -6) stays clear.
        for name, y, want in (('right', 600, 'conflict'), ('left', -600, 'clear')):
            with self.subTest(case=name):
                d = one_commit_run(self.tmp, 'lat_' + name, plan=straight(2.0, lateral=6.0), deadline=3.05,
                                   n_ticks=80, actor=lambda k, t, y=y: actor_row(k, t, actors=((7, 600, y, 0),)))
                self.assertEqual(VT.recompute_run(d)['_plans'][0]['status'], want)

    def test_v0_walker_static_prop_and_hero(self):
        # A walker beside the hero (lateral gap 1.5 - 0.92 - 0.20 = 0.38 m): V = 0; R_cond without V = 0 plans is
        # None. The hero's own id and a static prop over the path are ignored.
        d = one_commit_run(self.tmp, 'walker', actor=lambda k, t: actor_row(k, t, actors=((8, 0, 150, 0),
                                                                                            (1, 0, 0, 0),
                                                                                            (9, 450, 0, 0))))
        r = VT.recompute_run(d)
        self.assertEqual((r['conflict_plans'], r['v0_plans'], r['misses']), (1, 1, 1))
        self.assertIsNone(r['r_cond_excl_v0'])
        self.assertGreater(r['checks']['hero_in_actor_rows'], 0)
        d = one_commit_run(self.tmp, 'walker_far', n_ticks=80,
                           actor=lambda k, t: actor_row(k, t, actors=((8, 0, 165, 0), (9, 450, 0, 0))))
        self.assertEqual(VT.recompute_run(d)['plans_by_status'], {'clear': 1})

    def test_interpolation_censoring_and_bounds(self):
        # Rows every 0.10 s (stride 2): odd samples are interpolated; same V as the full log (capture 0.10).
        d = one_commit_run(self.tmp, 'stride2', capture=0.10, deadline=1.30,
                           actor=lambda k, t: actor_row(k, t, actors=((7, 792, 0, 0),)) if k % 2 == 0 else None)
        r = VT.recompute_run(d)
        self.assertEqual((r['_plans'][0]['status'], r['_plans'][0]['j']), ('conflict', 30))
        # Rows 0.25 s apart: the sample at 0.15 s is unknown -> log-censored within the run, with bounds.
        d = one_commit_run(self.tmp, 'stride5', capture=0.10, deadline=1.30,
                           actor=lambda k, t: actor_row(k, t, actors=((7, 792, 0, 0),)) if k % 5 == 2 else None)
        r = VT.recompute_run(d)
        self.assertEqual(r['_plans'][0]['status'], 'log_censored')
        self.assertEqual(r['_plans'][0]['j_unknown'], 1)
        self.assertIsNone(r['r_cond'])
        self.assertEqual(r['r_cond_bounds'], [0.0, 1.0])
        self.assertEqual(r['conflict_plans_bounds'], [0, 1])
        # An ego-only row at t 1.05 (sample tau 1.0) before the conflict at 1.5: censored; the EIR upper bound counts
        # the tracked ticks at an age of at least clip(1.0 - 0.5, 0, 2.5): k 11-24, 14 of 23.
        d = one_commit_run(self.tmp, 'egoonly', actor=lambda k, t: actor_row(
            k, t, actors=None if k == 21 else ((7, 792, 0, 0),)))
        r = VT.recompute_run(d)
        self.assertEqual(r['_plans'][0]['status'], 'log_censored')
        self.assertEqual((r['eir_invalid_ticks'], r['eir_unevaluable_ticks'], r['track_ticks']), (0, 14, 23))
        self.assertEqual(r['eir_bounds'], [0.0, 14 / 23])
        self.assertEqual(r['checks']['actor_rows_ego_only'], 1)
        # The end of the log after the last tick: censored without bounds.
        d = one_commit_run(self.tmp, 'short', n_ticks=25)
        r = VT.recompute_run(d)
        self.assertEqual((r['_plans'][0]['status'], r['plans_unevaluable']), ('log_censored', 0))
        self.assertIsNone(r.get('eir_bounds'))

    def test_v0_bound_and_a_first_unknown_sample_at_the_last_tick(self):
        # The capture row (t 0.05) is ego-only: the pose is known, sample 0 is not: log-censored at j 0 within the run,
        # so the V = 0 count may hide one plan.
        d = one_commit_run(self.tmp, 'capture_egoonly', actor=lambda k, t: actor_row(
            k, t, actors=None if k == 1 else ((7, 792, 0, 0),)))
        r = VT.recompute_run(d)
        self.assertEqual((r['_plans'][0]['status'], r['_plans'][0]['j_unknown']), ('log_censored', 0))
        self.assertEqual((r['v0_plans'], r['v0_plans_bounds'], r['conflict_plans_bounds']), (0, [0, 1], [0, 1]))
        # A standing plan whose first unknown sample (j 39, t 2.0, an ego-only row) is the last tick: bounded.
        d = one_commit_run(self.tmp, 'last_tick_unknown', plan=straight(0.0), deadline=3.05,
                           actor=lambda k, t: actor_row(k, t, actors=None if k == 40 else ((7, 792, 0, 0),)))
        r = VT.recompute_run(d)
        self.assertEqual((r['_plans'][0]['status'], r['_plans'][0]['j_unknown']), ('log_censored', 39))
        self.assertEqual((r['plans_unevaluable'], r['conflict_plans_bounds']), (1, [0, 1]))
        # The same plan when the log ends at the last tick: censored after the run, no bound.
        r = VT.recompute_run(one_commit_run(self.tmp, 'log_end', plan=straight(0.0), deadline=3.05))
        self.assertEqual((r['_plans'][0]['j_unknown'], r['plans_unevaluable']), (40, 0))

    def test_lease_s_of_the_commit_is_checked(self):
        # lease_s logged with the commit equals deadline - capture (1.2 s); another value is a raw-data check.
        for name, lease, want in (('equal', 1.2, None), ('other', 1.0, 1)):
            with self.subTest(case=name):
                commits = [{'job_id': 1, 'depth': 1, 'commit_s': 0.06, 'capture_s': 0.05, 'deadline_s': 1.25,
                            'lease_s': lease}]
                r = VT.recompute_run(one_commit_run(self.tmp, 'lease_' + name, commits=commits))
                self.assertEqual(r['checks'].get('lease_s_differs_from_deadline_minus_capture'), want)

    def test_unlogged_plan_truncated_and_missing_log(self):
        # A commit of a job without a jobs.jsonl row (running at the end): no logged plan, bounds on every value.
        commits = [{'job_id': 1, 'depth': 1, 'commit_s': 0.06, 'capture_s': 0.05, 'deadline_s': 1.25},
                   {'job_id': 2, 'depth': 1, 'commit_s': 1.21, 'capture_s': 1.0, 'deadline_s': 1.6}]
        d = one_commit_run(self.tmp, 'unlogged', commits=commits)
        r = VT.recompute_run(d)
        self.assertEqual(r['plans_by_status'], {'conflict': 1, 'no_plan_logged': 1})
        self.assertEqual((r['conflict_plans'], r['misses'], r['plans_unevaluable']), (1, 1, 1))
        self.assertEqual(r['conflict_plans_bounds'], [1, 2])
        self.assertEqual(r['r_cond_bounds'], [0.5, 1.0])
        # Job 1 tracked k 2-24 (4 invalid), job 2 tracked k 25-31 (t < 1.6): 30 tracked ticks, 7 unevaluable.
        self.assertEqual((r['track_ticks'], r['eir_invalid_ticks'], r['eir_unevaluable_ticks']), (30, 4, 7))
        self.assertEqual(r['eir_bounds'], [4 / 30, 11 / 30])
        # Truncated last gzip member: the complete members are read and the truncation is reported.
        d = one_commit_run(self.tmp, 'trunc', actor_log={'truncate': True})
        r = VT.recompute_run(d)
        self.assertEqual(r['checks']['actor_log_truncated'], 1)
        self.assertTrue(r['validity_available'])
        # A line that does not parse inside a complete member: no Sec. 6.3 value, the reason named, the run kept.
        d = one_commit_run(self.tmp, 'badline')
        path = os.path.join(d, VT.LOG_DIR, VT.ACTOR_LOG)
        with open(path, 'ab') as f:
            f.write(gzip.compress(b'{"t": 99, "s": 9.0, \n'))
        r = VT.recompute_run(d)
        self.assertEqual(r['problems'], [])
        self.assertFalse(r['validity_available'])
        self.assertTrue(any('does not decode' in x for x in r['validity_problems']))
        # No actor log: every other column is computed; the Sec. 6.3 values are None with the reason.
        r = VT.recompute_run(make_run(self.tmp, 'nolog', actor=None))
        self.assertEqual(r['problems'], [])
        self.assertFalse(r['validity_available'])
        self.assertTrue(any('actors.jsonl.gz' in x for x in r['validity_problems']))
        self.assertIsNone(r['eir'])
        self.assertAlmostEqual(r['dmr'], LEASE_EXPECTED['dmr'], places=12)

    def test_runs_csv_comparison_with_bounds(self):
        commits = [{'job_id': 1, 'depth': 1, 'commit_s': 0.06, 'capture_s': 0.05, 'deadline_s': 1.25},
                   {'job_id': 2, 'depth': 1, 'commit_s': 1.21, 'capture_s': 1.0, 'deadline_s': 1.6}]
        d = one_commit_run(self.tmp, 'unlogged', commits=commits)
        r = VT.recompute_run(d)
        agg = os.path.join(self.tmp, 'agg')
        os.makedirs(agg)
        cols = ('committed_plans', 'realized_available', 'realized_conflict_plans', 'realized_misses',
                'realized_r_cond', 'realized_v0_plans', 'realized_r_cond_excl_v0', 'realized_invalid_ticks',
                'realized_invalid_tick_ratio', 'realized_log_censored_plans')

        def write(**over):
            row = {k: v for k, v in runs_row('job1', d, r).items() if k in cols + ('job', 'run_dir', 'route_id',
                                                                                 'analysis_use')}
            row.update(over)
            write_csv(os.path.join(agg, 'runs.csv'), [row])

        def diffs_of(out):
            return sorted(x['their_field'] for x in self.diffs(out) if x['their_field'] in cols)
        write()
        VT.main(['--agg', agg, '--out', self.out('o1')])
        self.assertEqual(diffs_of(self.out('o1')), [])
        # The other side evaluated the unlogged plan as a missed conflict on all its ticks: within the bounds.
        write(realized_conflict_plans=2, realized_misses=2, realized_r_cond=1.0, realized_invalid_ticks=11,
              realized_invalid_tick_ratio=11 / 30)
        VT.main(['--agg', agg, '--out', self.out('o2')])
        self.assertEqual(diffs_of(self.out('o2')), [])
        by = self.report(self.out('o2'))['comparisons']['by_target']['runs.csv']
        self.assertEqual(by['agree_within_validity_bounds'], 4)   # R_cond 1.0 equals the point value
        write(realized_conflict_plans=3, realized_invalid_tick_ratio=12 / 30)
        VT.main(['--agg', agg, '--out', self.out('o3')])
        self.assertEqual(diffs_of(self.out('o3')), ['realized_conflict_plans', 'realized_invalid_tick_ratio'])
        # A run without an actor log: empty realized cells agree, values differ ('ours empty').
        d2 = make_run(self.tmp, 'nolog', actor=None, summary=summary_from(LEASE_EXPECTED))
        row = runs_row('job1', d2, LEASE_EXPECTED)
        for c in cols[2:]:
            row[c] = None
        row['realized_available'] = 'False'
        write_csv(os.path.join(agg, 'runs.csv'), [row])
        self.assertEqual(VT.main(['--agg', agg, '--out', self.out('o4')]), VT.EXIT_AGREE, self.diffs(self.out('o4')))
        row['realized_invalid_tick_ratio'] = 0.625
        write_csv(os.path.join(agg, 'runs.csv'), [row])
        self.assertEqual(VT.main(['--agg', agg, '--out', self.out('o5')]), VT.EXIT_DIFFER)
        got = [(x['their_field'], x['scope'], 'ours empty' in x['note']) for x in self.diffs(self.out('o5'))]
        self.assertEqual(got,
                         [('realized_invalid_tick_ratio', 'analysis', True)])

    def test_plans_output(self):
        d = one_commit_run(self.tmp, 'plans')
        agg = os.path.join(self.tmp, 'agg')
        os.makedirs(agg)
        write_csv(os.path.join(agg, 'runs.csv'), [runs_row('job1', d, VT.recompute_run(d))])
        VT.main(['--agg', agg, '--out', self.out(), '--write-plans'])
        with open(os.path.join(self.out(), 'plans.csv')) as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([(x['status'], x['j'], x['miss'], x['job_id'], x['depth']) for x in rows],
                         [('conflict', '30', 'True', '1', '1')])
        with open(os.path.join(self.out(), 'SHA256SUMS')) as f:
            self.assertIn('plans.csv', f.read())


REALIZED_COLS = ('realized_conflict_plans', 'realized_misses', 'realized_v0_plans', 'realized_log_censored_plans',
                 'realized_invalid_ticks', 'realized_invalid_tick_ratio', 'realized_r_cond', 'realized_r_cond_excl_v0')
REALIZED_FIELDS = dict(zip(REALIZED_COLS, ('conflict_plans', 'misses', 'v0_plans', 'log_censored_plans',
                                           'eir_invalid_ticks', 'eir', 'r_cond', 'r_cond_excl_v0')))
CAPTURE_OFFSET = 7e-7      # the runtime's clock offset of sample times against the 4-decimal actor-log times
CAR17 = dict(CAR, c=17)


def corner_actor(k, t):
    """Vehicle 7 ahead-left of the hero (centre CARLA (14.54, -2.22) m): the ego front-left corner meets its rear-right
    corner under the 10 m/s plan; the clearances at tau 0.95 and 1.0 are 0.222082 and -0.086113 m, so
    V_lin = 0.95 + 0.05 * 0.222082 / 0.308195 = 0.986030 s while the first crossing is V = 0.980225 s."""
    return actor_row(k, t, actors=((7, 1454, -222, 0),))


def two_plan_run(root, name, cap_b, gap_b, h_b, n_ticks, h_a=0.483):
    """Plan A (job 1): the corner approach at 10 m/s from capture 0.05 with H h_a (0.483: a miss by V, not by V_lin).
    Plan B (job 2): reversing at 2 m/s from capture cap_b toward vehicle 17, whose front is gap_b m behind the ego
    box (V = (gap_b - 0.5) / 2), with H h_b."""
    x17 = -(2.4525 + 2.0 + gap_b) * 100
    commits = [{'job_id': 1, 'depth': 1, 'commit_s': 0.06, 'capture_s': 0.05, 'deadline_s': 0.05 + h_a},
               {'job_id': 2, 'depth': 1, 'commit_s': cap_b + 0.01, 'capture_s': cap_b, 'deadline_s': cap_b + h_b}]
    jobs = [{'job_id': 1, 'prefix': (0.0, 0.04, 0.001), 'steps': [(0.05, 0.005, 0.001)]},
            {'job_id': 2, 'prefix': (cap_b - 0.05, 0.04, 0.001), 'steps': [(cap_b, 0.005, 0.001)]}]
    plans = {(1, 1): straight(10.0), (2, 1): straight(-2.0)}
    return one_commit_run(root, name, commits=commits, jobs=jobs, plans=plans, n_ticks=n_ticks,
                          actor=lambda k, t: actor_row(k, t, actors=((7, 1454, -222, 0), (17, x17, 0, 0))),
                          actor_log={'catalog': (CAR, WALKER, PROP, CAR17)})


class Causes(Base):
    """The conventions F1 and F3 of the registered implementation: per-run values under each, the cause of a
    difference, the counts by cause and cause_plans.csv."""

    def agg_with(self, run_dir, ours, name='agg', **realized):
        """runs.csv of one used row equal to the recomputation except the given realized_* columns."""
        row = runs_row('job1', run_dir, dict(ours, validity_available=True), last_tick_s=ours['last_tick_s'])
        row.update({k: ('' if v is None else v) for k, v in realized.items()})
        agg = os.path.join(self.tmp, name)
        os.makedirs(agg)
        write_csv(os.path.join(agg, 'runs.csv'), [row])
        return agg

    def realized_rows(self, out):
        return [(x['their_field'], x['cause']) for x in self.diffs(out) if x['their_field'] in REALIZED_COLS]

    @staticmethod
    def recompute(d):
        """recompute_run of d after writing its summary.json from the recomputed values (no summary difference)."""
        r = VT.recompute_run(d)
        with open(os.path.join(d, VT.LOG_DIR, 'summary.json'), 'w') as f:
            json.dump(summary_from(r), f)
        return r

    def values_under(self, r, cause):
        return {col: r['registered_views'][cause][f] for col, f in REALIZED_FIELDS.items()}

    def test_f1_conflict_on_the_last_row(self):
        # The conflict sample tau 1.5 lands on the last row (t 1.55) 0.7 microseconds after its time: a conflict here
        # (V 1.49005, a miss, 4 invalid ticks); log-censored under F1.
        d = one_commit_run(self.tmp, 'lastrow', capture=0.05 + CAPTURE_OFFSET, n_ticks=31)
        r = self.recompute(d)
        p = r['_plans'][0]
        self.assertEqual((p['status'], p['j'], p['j_last_row'], p['f1']), ('conflict', 30, 30, True))
        self.assertEqual((r['conflict_plans'], r['misses'], r['eir_invalid_ticks'], r['f1_plans']), (1, 1, 4, 1))
        f1 = self.values_under(r, 'F1')
        self.assertEqual(f1, {'realized_conflict_plans': 0, 'realized_misses': 0, 'realized_v0_plans': 0,
                              'realized_log_censored_plans': 1, 'realized_invalid_ticks': 0,
                              'realized_invalid_tick_ratio': 0.0, 'realized_r_cond': None,
                              'realized_r_cond_excl_v0': None})
        self.assertEqual((r['misses_f1'], r['log_censored_plans_f1'], r['misses_f3'], r['misses_f1f3']), (0, 1, 1, 0))
        # F1 decides the plan (no bound): the values under F1 carry no bounds.
        self.assertEqual([k for k, v in r['registered_views']['F1'].items() if k.endswith('_bounds') and v], [])
        out = self.out()
        self.assertEqual(VT.main(['--agg', self.agg_with(d, r, **f1), '--out', out]), VT.EXIT_DIFFER)
        rows = self.realized_rows(out)
        self.assertEqual(sorted(rows), sorted((c, 'F1') for c in REALIZED_COLS if c != 'realized_v0_plans'))
        comp = self.report(out)['comparisons']
        self.assertEqual(comp['differences_by_cause'], {'F1': 7})
        self.assertEqual(comp['analysis_differences_by_cause'], {'F1': 2})     # EIR and R_cond of a used row
        self.assertEqual(comp['by_target']['runs.csv']['differences_by_cause'], {'F1': 7})
        with open(os.path.join(out, 'cause_plans.csv')) as f:
            plans = list(csv.DictReader(f))
        self.assertEqual([(x['cause'], x['job_id'], x['depth'], x['j'], x['j_last_row'], x['t_last_row'],
                           x['status'], x['status_registered'], x['invalid_ticks'], x['invalid_ticks_registered'])
                          for x in plans], [('F1', '1', '1', '30', '30', '1.55', 'conflict', 'log_censored', '4', '0')])
        self.assertAlmostEqual(float(plans[0]['t_sample']) - 1.55, CAPTURE_OFFSET, places=12)
        with open(os.path.join(out, 'SHA256SUMS')) as f:
            self.assertIn('cause_plans.csv', f.read())
        with open(os.path.join(out, 'runs_recomputed.csv')) as f:
            run = list(csv.DictReader(f))[0]
        self.assertEqual((run['f1_plans'], run['conflict_plans_f1'], run['eir_f1'], run['r_cond_f1']), ('1', '0',
                                                                                                    '0.0', ''))

    def test_f1_needs_the_offset_and_the_row(self):
        # The same plan captured exactly on the grid (no offset), 0.5 ns or 2 ns after it, and 2 ms after it (the
        # sample lies past the last row: unknown here too).
        for name, offset, f1, status in (('exact', 0.0, 0, 'conflict'), ('half_ns', 5e-10, 0, 'conflict'),
                                         ('two_ns', 2e-9, 1, 'conflict'), ('two_ms', 2e-3, 0, 'log_censored')):
            with self.subTest(case=name):
                r = VT.recompute_run(one_commit_run(self.tmp, 'off_' + name, capture=0.05 + offset, n_ticks=31))
                self.assertEqual((r['_plans'][0]['status'], r['f1_plans']), (status, f1))
        self.assertEqual(VT.last_row_sample(0.05 + CAPTURE_OFFSET, 1.55), 30)
        self.assertIsNone(VT.last_row_sample(0.05 - CAPTURE_OFFSET, 1.55))
        self.assertIsNone(VT.last_row_sample(0.05 + CAPTURE_OFFSET, 4.55))     # beyond tau 3.0

    def test_f1_clear_plan_ending_on_the_last_row(self):
        d = one_commit_run(self.tmp, 'lastrow_clear', capture=0.05 + CAPTURE_OFFSET, n_ticks=61, plan=straight(0.0))
        r = self.recompute(d)
        self.assertEqual((r['plans_by_status'], r['f1_plans'], r['log_censored_plans_f1']), ({'clear': 1}, 1, 1))
        out = self.out()
        VT.main(['--agg', self.agg_with(d, r, realized_log_censored_plans=1), '--out', out])
        self.assertEqual(self.realized_rows(out), [('realized_log_censored_plans', 'F1')])
        # A conflict before the last row is not changed by F1 (the sample on the last row is never reached).
        d = one_commit_run(self.tmp, 'early_conflict', capture=0.05 + CAPTURE_OFFSET, n_ticks=61)
        r = VT.recompute_run(d)
        self.assertEqual((r['plans_by_status'], r['f1_plans'], r['_plans'][0]['j_last_row']), ({'conflict': 1}, 0, 60))

    def test_f3_clearance_interpolation(self):
        d = one_commit_run(self.tmp, 'corner', plan=straight(10.0), deadline=0.05 + 0.483, actor=corner_actor)
        r = self.recompute(d)
        p = r['_plans'][0]
        self.assertEqual((p['status'], p['j']), ('conflict', 20))
        dx = math.sqrt(0.25 - 0.4016 ** 2)
        self.assertLess(p['V_lo'], (10.1001 - dx) / 10.0 + 1e-9)
        self.assertGreaterEqual(p['V'], (10.1001 - dx) / 10.0 - 1e-9)
        c0 = math.hypot(10.1001 - 9.5, 0.4016) - 0.5
        c1 = math.hypot(10.1001 - 10.0, 0.4016) - 0.5
        self.assertAlmostEqual(p['V_lin'], 0.95 + 0.05 * c0 / (c0 - c1), places=9)
        self.assertEqual((p['miss'], p['miss_lin'], p['resolution']), (True, False, False))
        self.assertEqual((r['misses'], r['misses_f3'], r['f3_plans'], r['miss_resolution_plans']), (1, 0, 1, 0))
        out = self.out()
        self.assertEqual(VT.main(['--agg', self.agg_with(d, r, realized_misses=0, realized_r_cond=0.0,
                                                        realized_r_cond_excl_v0=0.0), '--out', out,
                                  '--write-plans']), VT.EXIT_DIFFER)
        self.assertEqual(sorted(self.realized_rows(out)), [('realized_misses', 'F3'), ('realized_r_cond', 'F3'),
                                                           ('realized_r_cond_excl_v0', 'F3')])
        with open(os.path.join(out, 'plans.csv')) as f:
            row = list(csv.DictReader(f))[0]
        self.assertEqual((row['miss'], row['miss_lin']), ('True', 'False'))
        self.assertAlmostEqual(float(row['V_lin']), p['V_lin'], places=12)
        with open(os.path.join(out, 'cause_plans.csv')) as f:
            self.assertEqual([(x['cause'], x['miss'], x['miss_registered']) for x in csv.DictReader(f)],
                             [('F3', 'True', 'False')])
        # Without a vehicle or walker at sample j - 1 (the vehicle enters the log at the conflicting sample): tau_j.
        self.assertEqual(VT.clearance_interpolated_v(math.inf, -0.1, 20), VT.TAU_STEP_S * 20)
        self.assertEqual(VT.clearance_interpolated_v(0.1, 0.2, 20), VT.TAU_STEP_S * 20)
        self.assertAlmostEqual(VT.clearance_interpolated_v(0.3, -0.1, 20), 0.95 + 0.0375, places=12)

    def test_f1_and_f3_in_one_run(self):
        # A: the corner approach (a miss by V, not by V_lin). B: a conflict at tau 0.5 (V 0.475, a miss on all its 10
        # tracked ticks) found on the last row (t 2.0) 0.7 microseconds after its time. The other side under both
        # conventions: per column, the first convention whose value it equals.
        d = two_plan_run(self.tmp, 'f1f3', 1.5 + CAPTURE_OFFSET, 1.45, 1.0, 40)
        r = self.recompute(d)
        self.assertEqual([(p['status'], p['j'], p['f1'], p['miss'], p['miss_lin']) for p in r['_plans']],
                         [('conflict', 20, False, True, False), ('conflict', 10, True, True, True)])
        both = self.values_under(r, 'F1+F3')
        self.assertEqual((both['realized_conflict_plans'], both['realized_misses'], both['realized_r_cond']),
                         (1, 0, 0.0))
        out = self.out()
        VT.main(['--agg', self.agg_with(d, r, **both), '--out', out])
        self.assertEqual(sorted(self.realized_rows(out)), sorted([
            ('realized_conflict_plans', 'F1'), ('realized_misses', 'F1+F3'), ('realized_log_censored_plans', 'F1'),
            ('realized_invalid_ticks', 'F1'), ('realized_invalid_tick_ratio', 'F1'), ('realized_r_cond', 'F1+F3'),
            ('realized_r_cond_excl_v0', 'F1+F3')]))
        self.assertEqual(self.report(out)['comparisons']['differences_by_cause'], {'F1': 4, 'F1+F3': 3})
        with open(os.path.join(out, 'cause_plans.csv')) as f:
            self.assertEqual(sorted((x['cause'], x['job_id']) for x in csv.DictReader(f)), [('F1', '2'), ('F3', '1')])

    def test_difference_without_a_cause(self):
        # 3 conflict plans and 5 misses are neither the values here (1, 1) nor under a convention (F1: 0, 0).
        d = one_commit_run(self.tmp, 'lastrow', capture=0.05 + CAPTURE_OFFSET, n_ticks=31)
        r = self.recompute(d)
        out = self.out()
        VT.main(['--agg', self.agg_with(d, r, realized_conflict_plans=3, realized_misses=5), '--out', out])
        self.assertEqual(sorted(self.realized_rows(out)), [('realized_conflict_plans', ''), ('realized_misses', '')])
        self.assertEqual(self.report(out)['comparisons']['differences_by_cause'], {VT.UNCLASSIFIED: 2})

    def test_agreement_within_bounds_at_the_value_of_a_convention(self):
        # A: the corner approach (F3: no miss). B: a miss within the 1e-3 s band (V 1.495, H 0.9955). Here 2 misses in
        # [1, 2], R_cond 1.0 in [0.5, 1.0]; under F3 1 miss, R_cond 0.5: the other side agrees within the bounds and
        # equals the F3 values (counted apart; no difference).
        d = two_plan_run(self.tmp, 'band', 1.0, 3.49, 0.9955, 60)
        r = self.recompute(d)
        self.assertEqual((r['misses'], r['misses_bounds'], r['r_cond_bounds']), (2, [1, 2], [0.5, 1.0]))
        out = self.out()
        f3 = self.values_under(r, 'F3')
        self.assertEqual((f3['realized_misses'], f3['realized_r_cond']), (1, 0.5))
        code = VT.main(['--agg', self.agg_with(d, r, realized_misses=1, realized_r_cond=0.5,
                                               realized_r_cond_excl_v0=0.5), '--out', out])
        self.assertEqual(self.realized_rows(out), [])
        comp = self.report(out)['comparisons']
        self.assertEqual(comp['agree_within_bounds_by_cause'], {'F3': 3})
        self.assertEqual(comp['by_target']['runs.csv']['agree_within_validity_bounds'], 3)
        self.assertEqual(code, VT.EXIT_AGREE, self.diffs(out))

    def test_cause_rules(self):
        # The n-th comparison of an identity takes the n-th value a pass recorded under each convention; a difference
        # takes the first convention whose value (bounds included) the other side agrees with; kind 'json' takes none.
        cid = VT.comparison_id('runs.csv', 'job1', 'conflict_plans', 'realized_conflict_plans')
        mis = VT.comparison_id('runs.csv', 'job1', 'misses', 'realized_misses')
        txt = VT.comparison_id('per_ability.csv', 'k', 'routes')
        variants = {'F1': {cid: [(0, None), (2, [2, 4])], mis: [(None, [0, 1])], txt: [('["a"]', None)]},
                    'F3': {cid: [(1, None), (5, None)], mis: [(0, None)]}}
        cmp = VT.Comparisons(variants)
        put = cmp.compare
        got = [put('runs.csv', 'job1', 'conflict_plans', 3, 1, their_field='realized_conflict_plans')['cause'],
               put('runs.csv', 'job1', 'conflict_plans', 3, 4, their_field='realized_conflict_plans')['cause'],
               put('runs.csv', 'job1', 'misses', 3, 0, their_field='realized_misses')['cause'],
               put('per_ability.csv', 'k', 'routes', '["a", "b"]', '["a"]', kind='json_text')['cause'],
               put('runs.csv', 'job2', 'conflict_plans', 3, 0, their_field='realized_conflict_plans')['cause']]
        # 1: F3's point value; 4: within F1's bounds [2, 4] (second occurrence); 0: F1's bounds hold it although its
        # point value is None (first in order); the text equal under F1; job2: nothing recorded.
        self.assertEqual(got, ['F3', 'F1', 'F1', 'F1', ''])
        self.assertEqual(cmp.summary()['differences_by_cause'], {'F1': 3, 'F3': 1, VT.UNCLASSIFIED: 1})
        self.assertTrue(VT.value_agrees('count', None, 1, [0, 2]))
        self.assertFalse(VT.value_agrees('count', None, 1))
        self.assertTrue(VT.value_agrees('fraction', None, None))
        self.assertFalse(VT.value_agrees('json', {'a': 1}, {'a': 1}))
        self.assertFalse(VT.value_agrees('fraction', 0.5, 0.5 + 2e-6))
        rec = VT.Recorder()
        self.assertIsNone(rec.compare('t', 'k', 'f', 1, 2, bounds=[0, 1]))
        self.assertIsNone(rec.absent('t', 'f'))
        self.assertEqual(rec.values, {VT.comparison_id('t', 'k', 'f'): [(1, [0, 1])]})

    def test_plans_are_not_kept(self):
        # S4: run() writes the plans of a run (plans.csv) and drops them; only the plans a convention changes stay.
        d = one_commit_run(self.tmp, 'lastrow', capture=0.05 + CAPTURE_OFFSET, n_ticks=31)
        kept = []
        original = VT.recompute_run

        def spy(run_dir):
            r = original(run_dir)
            kept.append(r)
            return r
        VT.recompute_run = spy
        try:
            VT.main(['--run-dir', d, '--out', self.out(), '--write-plans'])
        finally:
            VT.recompute_run = original
        self.assertEqual(len(kept), 1)
        self.assertNotIn('_plans', kept[0])
        self.assertNotIn('_cause_plans', kept[0])
        with open(os.path.join(self.out(), 'plans.csv')) as f:
            self.assertEqual([(x['status'], x['f1'], x['j_last_row']) for x in csv.DictReader(f)],
                             [('conflict', 'True', '30')])
        with open(os.path.join(self.out(), 'cause_plans.csv')) as f:
            self.assertEqual([x['cause'] for x in csv.DictReader(f)], ['F1'])

    def test_analysis_and_arm_summary_values_under_f1(self):
        # Two routes of one condition: route 990101 with the F1 conflict, route 990102 with the same conflict before
        # the last row. The analysis' EIR and R_cond route means and the arm_summary EIR mean equal those formed
        # from the F1 per-run values: differences with cause F1 (R_cond of route 990101 is None under F1: n 1).
        runs, vals = [], {}
        for route, n_ticks in (('990101', 31), ('990102', 61)):
            d = one_commit_run(self.tmp, 'r' + route, capture=0.05 + CAPTURE_OFFSET, n_ticks=n_ticks, route=route)
            r = self.recompute(d)
            vals[route] = r
            runs.append(runs_row('job_' + route, d, dict(r, validity_available=True), route=route,
                                 last_tick_s=r['last_tick_s'], **self.values_under(r, 'F1')))
        self.assertEqual((vals['990101']['f1_plans'], vals['990102']['f1_plans']), (1, 0))
        agg = os.path.join(self.tmp, 'agg')
        ana = os.path.join(self.tmp, 'analysis')
        os.makedirs(agg)
        os.makedirs(ana)
        for row in runs:
            row.update({k: ('' if row[k] is None else row[k]) for k in REALIZED_COLS})
        write_csv(os.path.join(agg, 'runs.csv'), runs)
        eir_f1 = [vals[x]['registered_views']['F1']['eir'] for x in ('990101', '990102')]
        rc_f1 = [vals[y]['registered_views']['F1']['r_cond'] for y in ('990101', '990102')]
        rc_f1 = [x for x in rc_f1 if x is not None]
        write_csv(os.path.join(agg, 'arm_summary.csv'), [{
            'protocol_arm': 'fl_heuristic', 'candidate': 'fl_heuristic', 'kappa': '1.0', 'seed': '11', 'phase': 'P1',
            'block': 'b', 'routes': 2, 'gpu_usage': VT.mean([v['gpu_usage'] for v in vals.values()]),
            'deadline_miss_ratio': VT.mean([v['dmr_all_ticks'] for v in vals.values()]),
            'deadline_miss_ratio_pooled': sum(v['missed_ticks_all'] for v in vals.values()) / sum(
                v['ticks'] for v in vals.values()),
            'deadline_miss_ratio_after_first_commit': VT.mean([v['dmr'] for v in vals.values()]),
            'fallback_episodes': VT.mean([v['fallback_episodes'] for v in vals.values()]),
            'action_age_p50_s': VT.mean([v['action_age_p50_s'] for v in vals.values()]),
            'action_age_mean_s': VT.mean([v['action_age_mean_s'] for v in vals.values()]),
            'p_both_pooled': None, 'realized_invalid_tick_ratio': VT.mean(eir_f1)}])
        cond = 'fl_heuristic_k1.0_s11'
        write_csv(os.path.join(ana, 'cells.csv'), [{'condition': cond, 'route_id': x, 'status': 'used',
                                                    'jobs': json.dumps(['job_' + x])} for x in ('990101', '990102')])
        write_csv(os.path.join(ana, 'conditions.csv'), [
            dict(VT._stats(eir_f1), condition=cond, subset='all', metric='eir', statistic='route_mean',
                 column='realized_invalid_tick_ratio'),
            dict(VT._stats(rc_f1), condition=cond, subset='all', metric='r_cond', statistic='route_mean',
                 column='realized_r_cond')])
        out = self.out()
        self.assertEqual(VT.main(['--agg', agg, '--analysis', ana, '--out', out]), VT.EXIT_DIFFER)
        d = self.diffs(out)
        got = sorted((x['target'], x['key'].split('/')[-1], x['field'], x['cause']) for x in d
                     if x['target'] in ('conditions.csv', 'arm_summary.csv'))
        self.assertEqual(got, [('arm_summary.csv', 'b', 'realized_invalid_tick_ratio', 'F1')]
                         + [('conditions.csv', 'eir', s, 'F1') for s in ('mean', 'median', 'min')]
                         + [('conditions.csv', 'r_cond', 'n', 'F1')])
        self.assertTrue(all(x['cause'] == 'F1' for x in d if x['their_field'] in REALIZED_COLS))
        self.assertTrue(all(x['cause'] == '' for x in d if x['status'] == 'absent'))
        comp = self.report(out)['comparisons']
        self.assertEqual(comp['differences_by_cause']['F1'], 7 + 5)
        self.assertEqual(comp['by_target']['conditions.csv']['analysis_differences_by_cause'], {'F1': 4})


def gzip_member(data, name=None, extra=None, comment=None, hcrc=False):
    """One gzip member of data with the optional header fields FNAME, FEXTRA, FCOMMENT and FHCRC (RFC 1952)."""
    flg = (0x08 if name else 0) | (0x04 if extra else 0) | (0x10 if comment else 0) | (0x02 if hcrc else 0)
    head = b'\x1f\x8b\x08' + bytes([flg]) + b'\x00\x00\x00\x00\x00\xff'
    if extra:
        head += len(extra).to_bytes(2, 'little') + extra
    if name:
        head += name + b'\x00'
    if comment:
        head += comment + b'\x00'
    if hcrc:
        head += (zlib.crc32(head) & 0xffff).to_bytes(2, 'little')
    deflate = zlib.compressobj(6, zlib.DEFLATED, -zlib.MAX_WBITS)
    body = deflate.compress(data) + deflate.flush()
    return head + body + zlib.crc32(data).to_bytes(4, 'little') + (len(data) % (1 << 32)).to_bytes(4, 'little')


class Decoder(Base):
    """gzip_members (RFC 1952) against gzip.decompress; read_actor_log on a log whose last member is cut."""

    def members(self):
        noise = b''.join(hashlib.sha256(str(i).encode()).digest() for i in range(6000))   # 192 kB, incompressible
        return [gzip.compress(b'{"a": 1}\n{"b": 2}\n'), gzip_member(b'{"c": 3}\n', name=b'actors.jsonl'),
                gzip_member(noise, extra=b'xy', comment=b'chunk', hcrc=True), gzip.compress(b''),
                gzip.compress(b'{"d": 4}\n')]

    def test_complete_members_equal_gzip_decompress(self):
        members = self.members()
        raw = b''.join(members)
        payloads, stop = VT.gzip_members(raw)
        self.assertIsNone(stop)
        self.assertEqual(len(payloads), 5)
        self.assertEqual(b''.join(payloads), gzip.decompress(raw))

    def test_cut_and_invalid_members(self):
        members = self.members()
        raw = b''.join(members)
        cases = [('trailer cut', raw[:-3], 4, 'truncated'),
                 ('deflate cut', b''.join(members[:2]) + members[2][:len(members[2]) // 2], 2, 'truncated'),
                 ('header cut', b''.join(members[:3]) + members[3][:6], 3, 'truncated'),
                 ('crc flipped', b''.join(members[:2]) + members[2][:-8] + bytes([members[2][-8] ^ 1])
                  + members[2][-7:] + b''.join(members[3:]), 2, 'invalid'),
                 ('isize wrong', b''.join(members[:2]) + members[2][:-4] + bytes([members[2][-4] ^ 1])
                  + members[2][-3:] + b''.join(members[3:]), 2, 'invalid'),
                 ('trailing bytes', raw + b'not a gzip member', 5, 'invalid'),
                 ('short trailing bytes', raw + b'xy', 5, 'invalid'),
                 ('short member start', raw + b'\x1f\x8b\x08\x00', 5, 'truncated')]
        for name, data, n, stop_want in cases:
            with self.subTest(case=name):
                payloads, stop = VT.gzip_members(data)
                self.assertEqual((len(payloads), stop), (n, stop_want))
                self.assertEqual(b''.join(payloads), gzip.decompress(b''.join(members[:n])))
                with self.assertRaises((OSError, EOFError, zlib.error)):
                    gzip.decompress(data)

    def test_actor_log_with_a_cut_last_member(self):
        # The logger appends one member per flush (here 7 lines); a cut last member loses its own lines only.
        d = one_commit_run(self.tmp, 'cut', actor_log={'truncate': True})
        full = one_commit_run(self.tmp, 'full')
        with open(os.path.join(full, VT.LOG_DIR, VT.ACTOR_LOG), 'rb') as f:
            lines = [json.loads(x) for x in gzip.decompress(f.read()).decode().splitlines()]
        kept = lines[:7 * ((len(lines) - 1) // 7)]
        header, catalog, rows, stop, other = VT.read_actor_log(os.path.join(d, VT.LOG_DIR, VT.ACTOR_LOG))
        self.assertEqual(stop, 'truncated')
        self.assertEqual(rows, [x for x in kept if 's' in x])
        self.assertLess(len(rows), 40)
        self.assertEqual((header['h'], sorted(catalog), other), (VT.ACTOR_SCHEMA, [7, 8, 9], 0))


class Independence(unittest.TestCase):
    def test_imports_are_stdlib_and_numpy_only(self):
        with open(SCRIPT) as f:
            tree = ast.parse(f.read())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split('.')[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or '').split('.')[0])
        self.assertEqual(names - {'argparse', 'csv', 'hashlib', 'json', 'math', 'os', 're', 'sys', 'time', 'zlib'},
                         {'numpy'})

    def test_no_reference_to_the_checked_implementations(self):
        with open(SCRIPT) as f:
            src = f.read()
        for name in ('metrics_v4', 'realized', 'aggregate_v4', 'analyze_v4', 'interim_guard', 'verify_independent'):
            for line in src.splitlines():
                if name in line and not line.lstrip().startswith(('#', '*')) and '`' not in line:
                    self.assertNotRegex(line, r'(import|open\(|load|exec)', '%s: %s' % (name, line))


SMOKE_RUNS = sorted(glob.glob(os.path.join(ROOT, 'outputs/framelease_v4/smoke_p1_0/*/runs/*/')))


@unittest.skipUnless(SMOKE_RUNS, 'P1-0 smoke run directories absent')
class RealSmokeRuns(unittest.TestCase):
    """The recomputation agrees with the runtime's summary.json on the P1-0 smoke runs (training route 18305)."""

    def test_agree_with_summary(self):
        for d in SMOKE_RUNS:
            with self.subTest(run=os.path.relpath(d, ROOT)):
                ours = VT.recompute_run(d)
                self.assertEqual(ours['problems'], [])
                cmp = VT.Comparisons()
                VT.compare_summary(cmp, d, ours, d)
                self.assertEqual(cmp.rows, [])
                self.assertGreaterEqual(cmp.summary()['compared'], 15)


if __name__ == '__main__':
    unittest.main()
