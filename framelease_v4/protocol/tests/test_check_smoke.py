"""The mechanical P1-0 smoke check (framelease_v4/protocol/check_smoke.py; PROTOCOL Sec. 8.1). CPU only; every run
directory is synthetic and lives in a temporary directory; the actor log is written by the real ActorBoxLogger from a
fake CARLA world, with the agent's pose estimate placed like the GNSS (1.4 m behind the vehicle origin).

  cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/protocol/tests/test_check_smoke.py

What is shown: seven complete smoke runs (the registered smoke block) PASS; each criterion fails on its own defect
(route record, configuration / pins, summary, fast prefix, decisions, utility, actor log, ego, pose offset, per-tick
wall time, run size); a behaviour run without choice epochs is DEFERRED (verdict still PASS); a job without a final
run makes the check INCOMPLETE; with the runner's records a lock-busy attempt is not counted and a runner 'ok' without
a matching run directory is an error; the report records whether the checker and the job file are the registered ones.
"""
from __future__ import annotations

import copy
import gzip
import json
import math
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

import numpy as np  # noqa: E402

from framelease_v2.latency_agent import planar_lidar2global  # noqa: E402
from framelease_v3.runtime import v3_shield as VS  # noqa: E402
from framelease_v3.runtime.v3_scheduler import FEATURE_NAMES  # noqa: E402
from framelease_v4.arms import actor_log as AL  # noqa: E402
from framelease_v4.arms import agent_frame as AF  # noqa: E402
from framelease_v4.protocol import check_smoke as CS  # noqa: E402
from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402
from framelease_v4.protocol import select_stage as SS  # noqa: E402
from framelease_v4.rl import behaviour as B  # noqa: E402

GNSS_BEHIND_M = 1.4
ROUTES_XML = ROOT / 'third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/data/bench2drive220.xml'
_FRAMES = {}


def agent_frame_of(job):
    """The official agent's GNSS frame for the job's route (amendment A1); cached."""
    key = (job['town'], str(job['route_id']))
    if key not in _FRAMES:
        _FRAMES[key] = AF.AgentFrame(job['town'], ROUTES_XML, job['route_id'])
    return _FRAMES[key]


# ============================================================================================ a tiny CARLA-like world

class _V:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class _Tr:
    def __init__(self, x, y, yaw):
        self.location, self.rotation = _V(x, y), type('R', (), {'yaw': float(yaw)})()


class _BB:
    def __init__(self, hx, hy):
        self.extent, self.location = _V(hx, hy, 0.8), _V(0.0, 0.0, 0.8)


class _Actor:
    def __init__(self, world, aid, type_id, role=''):
        self.world, self.id, self.type_id, self.bounding_box = world, aid, type_id, _BB(2.4, 1.0)
        self.attributes = {'role_name': role} if role else {}

    def get_transform(self):
        x, y, yaw, _, _ = self.world.state[self.id]
        return _Tr(x, y, yaw)

    def get_velocity(self):
        return _V(*self.world.state[self.id][3:5])


class _Snap:
    def __init__(self, world):
        self._a = {aid: world.actors[aid] for aid in world.state}

    def __len__(self):
        return len(self._a)

    def __iter__(self):
        return iter(list(self._a.values()))

    def find(self, aid):
        return self._a.get(aid)


class _World:
    def __init__(self):
        self.actors, self.state = {}, {}

    def add(self, aid, type_id, x, y, yaw, vx, vy, role=''):
        self.actors[aid] = _Actor(self, aid, type_id, role)
        self.state[aid] = (x, y, yaw, vx, vy)
        return self.actors[aid]

    def step(self, dt):
        self.state = {a: (x + vx * dt, y + vy * dt, yaw, vx, vy) for a, (x, y, yaw, vx, vy) in self.state.items()}

    def get_snapshot(self):
        return _Snap(self)

    def get_actors(self, ids=None):
        return [self.actors[i] for i in (ids if ids is not None else self.actors) if i in self.actors]

    def get_actor(self, aid):
        return self.actors.get(aid)


def write_actor_log(fl, n_ticks=120, offset_m=GNSS_BEHIND_M, with_hero=True, params=None, rng_seed=0, frame=None):
    """The real logger over a fake drive; the estimate is the GNSS pose: offset_m behind the vehicle origin, in the
    official agent's route-anchored frame when `frame` is given (as in a real run), else in the world frame."""
    rng = np.random.default_rng(rng_seed)
    w = _World()
    hero = w.add(1, 'vehicle.lincoln.mkz_2020', 120.0, -40.0, 30.0, 6.0, 3.0, role='hero' if with_hero else '')
    for i in range(6):
        w.add(100 + i, 'vehicle.tesla.model3', 120.0 + rng.uniform(-30, 30), -40.0 + rng.uniform(-10, 10), 0.0,
              rng.uniform(-3, 3), 0.0)
    lg = AL.ActorBoxLogger(fl, params, world_fn=lambda: w, hero_fn=(lambda: hero) if with_hero else (lambda: None))
    for k in range(n_ticks):
        x, y, yaw_deg = w.state[1][:3]
        xr, yr, yawr = x, -y, -math.radians(yaw_deg)          # right-handed model world
        gx, gy = xr - offset_m * math.cos(yawr), yr - offset_m * math.sin(yawr)
        if frame is not None:
            gx, gy = frame.map_point(gx, gy)
        est = planar_lidar2global(gx, gy, yawr)
        lg.tick(k, (k + 1) * 0.05, est)
        w.step(0.05)
    lg.close()
    return lg


# ============================================================================================ synthetic smoke runs

def utility_of(job):
    return (job['policy_params'] or {}).get('utility')


def decision_rows(job, n=12, choice=True):
    """v3-schema rows; choice epochs follow the job's utility (a_det^d, heuristic or behaviour with logged keys)."""
    name = utility_of(job)
    shield = CS.arm_kind(job['arm_name']) in ('age', 'shield')
    beh = B.parse_behaviour(name) if name else None
    d = 10 if name in (None, 'heuristic') else (beh[2] if beh else int(name.rsplit('_d', 1)[1]))
    rows, draw = [], 0
    for e in range(1, n + 1):
        depth = 1 + (e % 9)
        feats = {k: 0.0 for k in FEATURE_NAMES}
        feats['depth'] = depth
        row = {'kind': 'decision', 'epoch': e, 'sim_s': 0.5 * e, 'depth': depth, 'features': feats}
        if shield and choice and e % 2 == 0:
            base = B.a_det_action(depth, d)
            if beh:
                eps = beh[0]
                explore = int(e % 4 == 0)
                action = (VS.REFRESH if base == VS.REFINE else VS.REFINE) if explore else base
                feats.update({'v4_mu': (1 - eps) * float(action == base) + eps / 2, 'v4_explore': explore,
                              'v4_base_action': base, 'v4_draw': draw})
                draw += 1
            else:
                action = base
            row.update(p_both=True, feasible=[VS.REFINE, VS.REFRESH], action=action,
                       reason=f'both_feasible:{name or "heuristic"}')
        elif shield:
            row.update(p_both=False, feasible=[VS.REFRESH], action=VS.REFRESH,
                       reason='only_refresh_feasible:refine_depth')
        else:
            row.update(p_both=None, feasible=None, action='REFINE', reason='rule')
        rows.append(row)
    return rows


def make_run(root, job, name='20261111T010101_aaaaaaaa', status='Completed', n_ticks=120, choice=True,
             tick_wall_s=0.06, offset_m=GNSS_BEHIND_M, with_hero=True, result=True, agent_frame=True, route_cfg=True):
    run = Path(root) / job['output_dir'] / 'runs' / name
    fl = run / 'raw' / 'agent' / 'framelease'
    (run / 'metrics').mkdir(parents=True)
    fl.mkdir(parents=True)
    pp = dict(job['policy_params'])
    shield = CS.arm_kind(job['arm_name']) in ('age', 'shield')
    route = {'route_id': job['route_id'], 'town': job['town']} if route_cfg else {'route_id': job['route_id']}
    cfg = {'v4_arm': job['arm_name'], 'route': route, 'routes': str(ROUTES_XML), 'kappa': 1.0, 'seed': 11,
           'v4': {'agent': {'policy_params': pp}}, 'fast_prefix': {'options': list(CS.FAST_PREFIX_OPTIONS)},
           'envelope_sha256': (job.get('envelope') or {}).get('sha256')}
    (run / 'config.json').write_text(json.dumps(cfg))
    code = {str(ROOT / rel): sha for rel, sha in job['require_sha256'].items()}
    (run / 'manifest.json').write_text(json.dumps({'status': 'COMPLETED', 'identity': {'code': code}}))
    (run / 'raw' / 'source_v4').mkdir(parents=True)
    (run / 'raw' / 'source_v4' / 'hashes.json').write_text(json.dumps(
        {rel: sha for rel, sha in job['require_sha256'].items() if rel.startswith('framelease_v4/')}))
    if not result:
        return run
    (run / 'metrics' / 'result.json').write_text(json.dumps(
        {'route_records': 1, 'route_status': status, 'scores': {'score_composed': 40.0, 'score_route': 50.0},
         'timed_out': False, 'wall_s': 320.0, 'error': None, 'fast_prefix': {'problems': []}}))
    (run / 'raw' / 'official_results.json').write_text('{}')
    rows = decision_rows(job, choice=choice)
    with open(fl / 'decisions.jsonl', 'w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    with open(fl / 'ticks.jsonl', 'w') as f:
        for k in range(n_ticks):
            f.write(json.dumps({'tick': k, 'sim_s': (k + 1) * 0.05, 'mode': 'track', 'wall_s': tick_wall_s}) + '\n')
    lg = write_actor_log(fl, n_ticks, offset_m, with_hero, frame=agent_frame_of(job) if agent_frame else None)
    summary = {'policy': ({'utility': utility_of(job) or 'heuristic'} if shield else {'name': job['arm_name']}),
               'v4': {'schema': CS.V4_RUNTIME_SCHEMA, 'runtime_class': 'V4Runtime', 'ticks': n_ticks,
                      'decisions': len(rows), 'p_both': None},
               'fast_prefix': {'validation_ok': True}, 'actor_log': lg.status()}
    (fl / 'summary.json').write_text(json.dumps(summary))
    (fl / 'fast_prefix.json').write_text(json.dumps(
        {'stage': 'final', 'fast_prefix': {'active': {o: True for o in CS.FAST_PREFIX_OPTIONS},
                                           'validation': {'ok': True, 'failures': []}},
         'stats': {'sdpa': {'sdpa_calls': 1234}}}))
    return run


class Smoke:
    def __init__(self, tmp):
        self.tmp = Path(tmp)
        self.root = self.tmp / 'root'
        self.lines, _ = PJ.smoke_block()
        self.job_file = self.tmp / 'b00_smoke.jsonl'
        self.job_file.write_text(''.join(json.dumps(j, sort_keys=True) + '\n' for j in self.lines))
        self.jobs = CS.load_jobs(self.job_file)
        self.by_arm = {j['arm_name']: j for j in self.jobs}

    def all_runs(self, **kw):
        return {j['arm_name']: make_run(self.root, j, **kw) for j in self.jobs}

    def check(self, queue=None, registration=None):
        return CS.check(self.jobs, self.root, queue, self.job_file, registration or self.tmp / 'no_manifest')


def crit(rep, arm, name):
    row = next(r for r in rep['jobs'] if r['arm'] == arm)
    return row['criteria'][name]


class SmokeCheckTest(unittest.TestCase):
    def test_complete_smoke_passes_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Smoke(tmp)
            self.assertEqual(len(S.jobs), 7)
            self.assertEqual(utility_of(S.by_arm['age_only']), 'v4_adet_d4')     # smoke covers a_det^4
            S.all_runs()
            rep = S.check()
            self.assertEqual(rep['verdict'], 'PASS', json.dumps([r for r in rep['jobs'] if r['status'] != 'PASS'],
                                                                indent=1)[:3000])
            self.assertEqual(rep['deferred_to_P2'], [])
            for r in rep['jobs']:
                self.assertEqual(set(r['criteria']), set(CS.CRITERIA))
            self.assertEqual(crit(rep, 'fixed_deep', 'utility')['status'], CS.NA)
            self.assertEqual(crit(rep, 'age_only', 'utility')['values']['utility'], 'v4_adet_d4')
            pose = crit(rep, 'fl_heuristic', 'pose_offset')['values']
            self.assertAlmostEqual(pose['offset_p50_m'], GNSS_BEHIND_M, delta=0.02)
            self.assertLess(pose['yaw_p50_deg'], 0.5)
            self.assertFalse(rep['script_registered'])
            # registered: a manifest that lists this checker and this job file
            man = Path(tmp) / 'MANIFEST.sha256'
            man.write_text(f'{PJ.sha256_file(CS.__file__)}  {CS.THIS_REL}\n'
                           f'{PJ.sha256_file(S.job_file)}  {PJ.rel(S.job_file)}\n')
            rep2 = S.check(registration=man)
            self.assertTrue(rep2['script_registered'])
            self.assertTrue(rep2['job_file_registered'])
            path = CS.write_report(rep2, Path(tmp) / 'report.json')
            self.assertEqual(json.loads(path.read_text())['verdict'], 'PASS')
            with self.assertRaises(FileExistsError):
                CS.write_report({**rep2, 'verdict': 'FAIL'}, path)

    def test_each_criterion_fails_on_its_defect(self):
        def broken(mutate, arm, criterion, expect=CS.FAIL):
            with tempfile.TemporaryDirectory() as tmp:
                S = Smoke(tmp)
                runs = S.all_runs()
                mutate(runs[arm], S.by_arm[arm])
                rep = S.check()
                c = crit(rep, arm, criterion)
                self.assertEqual(c['status'], expect, (criterion, c))
                self.assertEqual(rep['verdict'], 'FAIL' if expect == CS.FAIL else 'PASS', criterion)
                return c

        def fl(run):
            return run / 'raw' / 'agent' / 'framelease'

        def edit_json(path, fn):
            d = json.loads(path.read_text())
            fn(d)
            path.write_text(json.dumps(d))

        # route record: a timed-out launcher
        broken(lambda run, j: edit_json(run / 'metrics/result.json', lambda d: d.update(timed_out=True)),
               'fast_only', 'route_record')
        # configuration / pins: the run recorded another sha256 for a pinned v4 file
        def bad_pin(run, j):
            edit_json(run / 'raw/source_v4/hashes.json', lambda d: d.update({'framelease_v4/arms/arms_v4.py': 'f' * 64}))
            edit_json(run / 'manifest.json', lambda d: d['identity']['code'].update(
                {str(ROOT / 'framelease_v4/arms/arms_v4.py'): 'f' * 64}))
        broken(bad_pin, 'fl_original', 'config')
        # summary without the v4 block
        broken(lambda run, j: edit_json(fl(run) / 'summary.json', lambda d: d.pop('v4')), 'event_triggered',
               'summary_v4')
        # fast prefix: the agent never reached destroy (stage not final), or no SDPA call
        broken(lambda run, j: edit_json(fl(run) / 'fast_prefix.json', lambda d: d.update(stage='validated_in_warmup')),
               'fixed_deep', 'fast_prefix')
        broken(lambda run, j: edit_json(fl(run) / 'fast_prefix.json',
                                        lambda d: d['stats']['sdpa'].update(sdpa_calls=0)), 'fixed_deep', 'fast_prefix')
        # decisions: a cut last line, a missing epoch, a row without the v3 features
        def cut(run, j):
            p = fl(run) / 'decisions.jsonl'
            p.write_text(p.read_text()[:-40])
        broken(cut, 'fl_heuristic', 'decisions')

        def gap(run, j):
            p = fl(run) / 'decisions.jsonl'
            rows = [json.loads(x) for x in p.read_text().splitlines()]
            del rows[3]
            p.write_text(''.join(json.dumps(r) + '\n' for r in rows))
        broken(gap, 'fl_heuristic', 'decisions')

        def nofeat(run, j):
            p = fl(run) / 'decisions.jsonl'
            rows = [json.loads(x) for x in p.read_text().splitlines()]
            rows[0]['features'].pop('lease_slack_s')
            p.write_text(''.join(json.dumps(r) + '\n' for r in rows))
        broken(nofeat, 'fast_only', 'decisions')
        # utility: the agent built the policy with another utility than configured, or acted against a_det^4
        broken(lambda run, j: edit_json(fl(run) / 'summary.json', lambda d: d['policy'].update(utility='heuristic')),
               'age_only', 'utility')

        def wrong_action(run, j):
            p = fl(run) / 'decisions.jsonl'
            rows = [json.loads(x) for x in p.read_text().splitlines()]
            r = next(r for r in rows if r.get('p_both') and r['depth'] < 4)
            r['action'] = VS.REFRESH                                   # a_det^4 refines below depth 4
            p.write_text(''.join(json.dumps(r) + '\n' for r in rows))
        broken(wrong_action, 'age_only', 'utility')

        def bad_mu(run, j):
            p = fl(run) / 'decisions.jsonl'
            rows = [json.loads(x) for x in p.read_text().splitlines()]
            next(r for r in rows if r.get('p_both'))['features']['v4_mu'] = 0.42
            p.write_text(''.join(json.dumps(r) + '\n' for r in rows))
        broken(bad_mu, 'fl_behaviour', 'utility')
        # actor log: truncated gzip member; over budget
        def trunc(run, j):
            p = fl(run) / AL.FILE_NAME
            p.write_bytes(p.read_bytes()[:-30])
        broken(trunc, 'fl_original', 'actor_log')
        broken(lambda run, j: edit_json(fl(run) / AL.MANIFEST_NAME, lambda d: d.update(errors=3)), 'fl_original',
               'actor_log')
        # per-tick wall time: a slow agent
        def slow(run, j):
            p = fl(run) / 'ticks.jsonl'
            rows = [json.loads(x) for x in p.read_text().splitlines()]
            p.write_text(''.join(json.dumps({**r, 'wall_s': 0.3}) + '\n' for r in rows))
        broken(slow, 'fast_only', 'tick_wall')
        # run size above the limit (limit lowered for the test)
        saved = dict(CS.THRESHOLDS)
        try:
            CS.THRESHOLDS['run_dir_max_mb'] = 0.001
            broken(lambda run, j: None, 'fixed_deep', 'run_size')
        finally:
            CS.THRESHOLDS.clear()
            CS.THRESHOLDS.update(saved)

    def test_pose_and_ego_defects(self):
        for kw, criterion in (({'offset_m': 0.0}, 'pose_offset'), ({'offset_m': 6.0}, 'pose_offset'),
                              ({'with_hero': False}, 'ego_found')):
            with tempfile.TemporaryDirectory() as tmp:
                S = Smoke(tmp)
                for j in S.jobs:
                    make_run(S.root, j, **(kw if j['arm_name'] == 'fl_heuristic' else {}))
                rep = S.check()
                self.assertEqual(crit(rep, 'fl_heuristic', criterion)['status'], CS.FAIL, (kw, criterion))
                self.assertEqual(rep['verdict'], 'FAIL')

    def test_pose_amendment_a1_frame(self):
        """A1: an estimate left in the world frame (no route anchoring) fails by about |x_first|; a config without the
        route town fails with the reason; the real-run layout (agent frame) passes at the GNSS lever arm."""
        for kw, needle in (({'agent_frame': False}, 'offset p50'), ({'route_cfg': False}, 'agent frame unavailable')):
            with tempfile.TemporaryDirectory() as tmp:
                S = Smoke(tmp)
                for j in S.jobs:
                    make_run(S.root, j, **(kw if j['arm_name'] == 'fl_heuristic' else {}))
                rep = S.check()
                c = crit(rep, 'fl_heuristic', 'pose_offset')
                self.assertEqual(c['status'], CS.FAIL, kw)
                self.assertIn(needle, c['detail'], kw)
                self.assertEqual(rep['verdict'], 'FAIL')
        with tempfile.TemporaryDirectory() as tmp:
            S = Smoke(tmp)
            S.all_runs()
            vals = crit(S.check(), 'fast_only', 'pose_offset')['values']
            self.assertAlmostEqual(vals['offset_p50_m'], GNSS_BEHIND_M, delta=0.02)
            self.assertGreater(vals['raw_world_offset_p50_m'], 1000.0)      # Town12 route 18305: x_first = 1176.6 m
            self.assertAlmostEqual(vals['agent_frame']['translation_at_first_waypoint_m'][0], -1176.6, places=6)

    def test_behaviour_without_choice_epochs_is_deferred(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Smoke(tmp)
            for j in S.jobs:
                make_run(S.root, j, choice=j['arm_name'] != 'fl_behaviour')
            rep = S.check()
            self.assertEqual(crit(rep, 'fl_behaviour', 'utility')['status'], CS.DEFERRED)
            self.assertEqual(rep['verdict'], 'PASS')
            self.assertEqual(len(rep['deferred_to_P2']), 1)

    def test_execution_failures_and_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Smoke(tmp)
            for j in S.jobs:
                if j['arm_name'] != 'event_triggered':
                    make_run(S.root, j)
            rep = S.check()
            self.assertEqual(rep['verdict'], 'INCOMPLETE')
            j = S.by_arm['event_triggered']
            make_run(S.root, j, name='20261111T020000_bbbbbbbb', status='Failed - Simulation crashed')
            self.assertEqual(S.check()['verdict'], 'INCOMPLETE')                 # its retry is still to come
            make_run(S.root, j, name='20261111T030000_cccccccc', status='Failed - Agent crashed')
            rep = S.check()
            self.assertEqual(rep['verdict'], 'FAIL')                             # no valid record after the retry
            self.assertEqual(crit(rep, 'event_triggered', 'route_record')['status'], CS.FAIL)
            make_run(S.root, j, name='20261111T040000_dddddddd', status='Failed - Agent got blocked')
            self.assertEqual(S.check()['verdict'], 'PASS')                       # a driving failure is a valid record

    def test_runner_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Smoke(tmp)
            runs = S.all_runs()
            j = S.by_arm['fl_heuristic']
            q = Path(tmp) / 'queue'
            q.mkdir()
            recs = []
            for jj in S.jobs:
                if jj is j:
                    continue
                recs += [{'event': 'start', 'id': jj['id'], 'attempt': 1},
                         {'event': 'end', 'id': jj['id'], 'attempt': 1, 'outcome': 'ok', 'counted': True, 'final': True,
                          'run_dir': str(runs[jj['arm_name']])}]
            # fl_heuristic: the valid run exists, the runner has not written its record yet -> still final (valid run)
            (q / 'status.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in recs))
            self.assertEqual(S.check(q)['verdict'], 'PASS')
            # a runner 'ok' whose run directory is not a matching valid run is an error, never a silent pass / drop
            bad = recs + [{'event': 'start', 'id': j['id'], 'attempt': 1},
                          {'event': 'end', 'id': j['id'], 'attempt': 1, 'outcome': 'ok', 'counted': True, 'final': True,
                           'run_dir': str(Path(tmp) / 'elsewhere')}]
            (q / 'status.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in bad))
            with self.assertRaises(SS.SelectionError):
                S.check(q)

    def test_main_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Smoke(tmp)
            self.assertEqual(CS.main(['--jobs-file', str(Path(tmp) / 'missing.jsonl')]), 2)
            bad = Path(tmp) / 'notsmoke.jsonl'
            lines, _ = PJ.build_block('TRIMMED', 'event_s1')
            bad.write_text(json.dumps(lines[0]) + '\n')
            self.assertEqual(CS.main(['--jobs-file', str(bad)]), 2)              # not a smoke job
            self.assertTrue(S.job_file.is_file())


if __name__ == '__main__':
    unittest.main()
