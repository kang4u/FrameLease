"""Phase-1 job files and stage selection (framelease_v4/protocol/p1_jobs.py, select_stage.py; PROTOCOL Secs. 4.2,
8.1-8.3, 10, 14). CPU only; nothing is launched or enqueued; every file is written to a temporary directory.

  cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/protocol/tests
  # + the launcher / --dry-run checks of the written and of future job lines (official stack variables):
  source linux/env.sh && CUDA_VISIBLE_DEVICES= .conda-unidrive-linux/bin/python -B -m pytest -q -p no:cacheprovider \
      framelease_v4/protocol/tests

What is shown:
  * blocks: the T22a / T22b / T22 route sets, the smoke route outside T22, line counts equal to the budget tables of
    both variants, the order rule (Random(20261110 + block) route shuffle, rotation by one per route, candidates of a
    route back to back), ports 2600 + 10 (i mod 4), explicit --fast-prefix / --envelope / --timeout-s 1410 /
    --lock-wait-s 600, full pins (v2 matrix, v3 runtime, fast prefix, v4 arms + rl utilities, envelope), training
    routes only, identical ids and directories for identical runs in both variants;
  * selection: successive halving (top ceil(K/2), ties to the earlier candidate, final over T22), a simulator failure
    drops the route for every candidate, 'Agent crashed' counts as DS 0, a pending job blocks the selection, runner
    final records without a run directory, test routes refused, the d = 10 heuristic runs reused from the lease grid,
    the dependent blocks generated only from complete selections of the current job files, the tuning freeze (FULL
    and TRIMMED);
  * with the official stack: every line of the written job files passed the launcher and its --dry-run (check.json),
    a sample is re-run now, and lines of the future blocks (from synthetic selections) pass the launcher too.
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ['CUDA_VISIBLE_DEVICES'] = ''
sys.dont_write_bytecode = True

from framelease_v4.protocol import make_protocol_tables as MPT  # noqa: E402
from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402
from framelease_v4.protocol import select_stage as SS  # noqa: E402

STACK = bool(os.environ.get('CHECKPOINT')) and Path(os.environ.get('CHECKPOINT', '/nonexistent')).is_file()


def budget_runs(variant):
    return {b: r for _, _, b, _, r in MPT.plan_blocks(variant)}


def opts(cmd):
    return {cmd[k]: cmd[k + 1] for k in range(len(cmd) - 1) if cmd[k].startswith('--')}


class BlocksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full = {b: PJ.build_block('FULL', b) for b in ('ref', 'lease_s1', 'event_s1')}
        cls.trim = {b: PJ.build_block('TRIMMED', b) for b in ('lease_s1', 'event_s1')}
        cls.smoke = PJ.smoke_block()

    def test_route_sets_and_smoke_route(self):
        a, b, t22 = PJ.route_set('T22a'), PJ.route_set('T22b'), PJ.route_set('T22')
        self.assertEqual((len(a), len(b), len(t22)), (11, 11, 22))
        self.assertFalse(set(a) & set(b))
        self.assertEqual(sorted(a + b, key=int), t22)
        test = {r['route_id'] for r in PJ.route_split()['test']}
        self.assertFalse(set(t22) & test)
        self.assertIn(PJ.SMOKE_ROUTE, PJ.training_routes())
        self.assertNotIn(PJ.SMOKE_ROUTE, t22)
        lines, meta = self.smoke
        self.assertEqual({j['route_id'] for j in lines}, {PJ.SMOKE_ROUTE})

    def test_counts_equal_the_budget_tables(self):
        fb, tb = budget_runs('FULL'), budget_runs('TRIMMED')
        self.assertEqual(len(self.full['ref'][0]), fb['T-ref'])
        self.assertEqual(len(self.full['lease_s1'][0]), fb['T-lease-s1'])
        self.assertEqual(len(self.full['event_s1'][0]), fb['T-event-s1'])
        self.assertEqual(len(self.trim['lease_s1'][0]), tb['T-lease'])
        self.assertEqual(len(self.trim['event_s1'][0]), tb['T-event'])
        self.assertEqual(len(self.smoke[0]), fb['smoke'])
        self.assertEqual(fb['smoke'], tb['smoke'])
        self.assertEqual(sum(budget_runs('TRIMMED').values()), 579)
        self.assertEqual(sum(budget_runs('FULL').values()), 1046)

    def test_order_rotation_and_ports(self):
        for variant, blocks in (('FULL', self.full), ('TRIMMED', self.trim)):
            for name, (lines, spec) in blocks.items():
                no = PJ.BLOCKS[variant][name][0]
                routes = sorted(spec['routes'], key=int)
                random.Random(20261110 + no).shuffle(routes)
                self.assertEqual(spec['route_order'], routes, name)
                k = len(spec['candidates'])
                names = [c['name'] for c in sorted(spec['candidates'], key=lambda c: c['order'])]
                for pos, r in enumerate(routes):
                    chunk = lines[pos * k:(pos + 1) * k]
                    self.assertEqual({j['route_id'] for j in chunk}, {r}, name)          # back to back
                    self.assertEqual([j['candidate'] for j in chunk], names[pos % k:] + names[:pos % k], name)
                for i, j in enumerate(lines):
                    self.assertEqual(j['port'], 2600 + 10 * (i % 4))

    def test_line_contract(self):
        every = [l for blocks in (self.full, self.trim) for lines, _ in blocks.values() for l in lines]
        every += self.smoke[0]
        for lines in [ls for blocks in (self.full, self.trim) for ls, _ in blocks.values()] + [self.smoke[0]]:
            self.assertEqual(PJ.static_problems(lines), [])
        for j in every:
            o = opts(j['cmd'])
            self.assertEqual(j['cmd'][:3], [PJ.PYTHON, '-B', 'framelease_v4/arms/run_closed_loop_v4.py'])
            self.assertEqual(o['--fast-prefix'], 'sdpa,gpu_preproc,lora_merged')
            self.assertEqual((o['--timeout-s'], o['--lock-wait-s'], o['--kappa'], o['--seed']),
                             ('1410', '600', '1.0', '11'))
            self.assertEqual(j['wall_cap_s'], 1500)
            pins = j['require_sha256']
            for rel in ('framelease_v2/run_closed_loop.py', 'framelease_v2/__init__.py', 'framelease_v3/__init__.py',
                        'framelease_v3/runtime/v3_lease.py', 'framelease_v3/fastprefix/fast_path.py',
                        'framelease_v4/arms/arms_v4.py', 'framelease_v4/arms/agent_v4.py',
                        'framelease_v4/arms/run_closed_loop_v4.py', 'framelease_v4/rl/__init__.py',
                        'framelease_v4/rl/behaviour.py', 'framelease_v4/rl/features.py', 'framelease_v4/rl/qnet.py',
                        'linux/env.sh', PJ.ROUTES_XML_REL):
                self.assertIn(rel, pins, (j['id'], rel))
            shield = j['arm_name'] in ('fl_heuristic', 'fl_behaviour')
            self.assertEqual('--envelope' in o, shield, j['id'])
            if shield:
                self.assertEqual(o['--envelope'], j['envelope']['path'])
                self.assertEqual(pins[j['envelope']['path']], j['envelope']['sha256'])
            self.assertEqual(json.loads(o.get('--policy-params', '{}')), j['policy_params'])
            self.assertTrue(j['output_dir'].startswith('outputs/framelease_v4/tuning/')
                            or j['output_dir'].startswith('outputs/framelease_v4/smoke_p1_0/'))
            self.assertNotIn('jobs.d', j['output_dir'])
        def no_port(cmd):
            i = cmd.index('--port')
            return tuple(cmd[:i] + cmd[i + 2:])
        same = {(j['id'], j['output_dir'], no_port(j['cmd'])) for j in every if j['phase'] == 'P1'}
        self.assertEqual(len({j['id'] for j in every if j['phase'] == 'P1'}), len(same))   # same id = same run

    def test_candidates(self):
        lease = {j['candidate']: j for j in self.full['lease_s1'][0]}
        self.assertEqual(sorted(lease), ['B0', 'E10', 'E5'])
        man = json.loads(PJ.ENVELOPE_MANIFEST.read_text())
        for label, j in lease.items():
            self.assertEqual(j['envelope']['sha256'], man['files'][label]['sha256'])
            self.assertEqual(j['policy_params'], {'utility': 'heuristic'})
        ev = {j['candidate']: j['policy_params'] for j in self.full['event_s1'][0]}
        self.assertEqual(ev['v2_hb2.0'], {'speed_delta_mps': 1.0, 'yaw_delta_rad': 0.1, 'det_shift_m': 2.0,
                                          'heartbeat_s': 2.0})
        self.assertEqual(ev['s_hb1.0'], {'speed_delta_mps': 0.5, 'yaw_delta_rad': 0.05, 'det_shift_m': 1.0,
                                         'heartbeat_s': 1.0})
        self.assertEqual(sorted({j['candidate'] for j in self.trim['event_s1'][0]}), ['s_hb1.0', 'v2_hb2.0'])
        # identical runs: identical ids and directories in both variants
        full_ids = {j['id']: (j['output_dir'], tuple(j['cmd'][3:11])) for j in self.full['event_s1'][0]}
        for j in self.trim['event_s1'][0]:
            self.assertEqual(full_ids[j['id']][0], j['output_dir'])
        self.assertEqual({j['id'] for j in self.trim['lease_s1'][0]}, {j['id'] for j in self.full['lease_s1'][0]})
        smoke = {j['arm_name']: j for j in self.smoke[0]}
        self.assertEqual(list(smoke), ['fixed_deep', 'fast_only', 'age_only', 'event_triggered', 'fl_original',
                                       'fl_heuristic', 'fl_behaviour'])
        self.assertEqual(smoke['fl_heuristic']['envelope']['label'], 'E5')
        self.assertEqual(smoke['age_only']['policy_params'], {'age_lease_s': 2.0, 'utility': 'v4_adet_d4'})
        self.assertEqual(smoke['fl_heuristic']['policy_params'], {'utility': 'heuristic'})
        self.assertEqual([j['candidate'] for j in self.smoke[0]], [j['arm_name'] for j in self.smoke[0]])
        self.assertEqual(smoke['fl_behaviour']['envelope']['label'], 'E5')
        from framelease_v4.rl import behaviour as B
        from framelease_v4.rl import collection_plan as CP
        self.assertEqual(B.parse_behaviour(smoke['fl_behaviour']['policy_params']['utility']),
                         (0.3, CP.behaviour_seed(PJ.SMOKE_ROUTE, 1.0, 0), 10))

    def test_dependent_blocks_need_a_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            for variant, block in (('FULL', 'lease_s2'), ('FULL', 'heur_s1'), ('TRIMMED', 'age_s1')):
                with self.assertRaises((FileNotFoundError, ValueError)):
                    PJ.build_block(variant, block, Path(tmp) / 'sel', Path(tmp) / 'jobs')


# ============================================================================================ synthetic selections

class Synthetic:
    """Temporary job / selection directories and fake run directories under a temporary root."""

    def __init__(self, tmp):
        self.tmp = Path(tmp)
        self.jobs, self.sel, self.root = self.tmp / 'jobs', self.tmp / 'sel', self.tmp / 'root'
        self.n = 0

    def block(self, variant, name):
        lines, spec = PJ.build_block(variant, name, self.sel, self.jobs)
        PJ.write_block(PJ.stage_paths(variant, name, self.jobs), lines, spec, [], [])
        spec, _ = PJ.load_stage_spec(variant, name, self.jobs)
        return lines, spec

    def run(self, job, cand, route, status, ds, error=None, envelope_sha=None):
        self.n += 1
        d = self.root / job['output_dir'] / 'runs' / f'20261111T{self.n:06d}_x'
        (d / 'metrics').mkdir(parents=True)
        cfg = {'route': {'route_id': route}, 'v4_arm': cand['arm'], 'kappa': 1.0, 'seed': 11,
               'v4': {'agent': {'policy_params': cand['policy_params']}},
               'envelope_sha256': envelope_sha or (cand['envelope']['sha256'] if cand.get('envelope') else None)}
        (d / 'config.json').write_text(json.dumps(cfg))
        if status is not None:
            rec = 0 if status in ('NO_RECORD', 'LOCK_BUSY') else 1
            (d / 'metrics' / 'result.json').write_text(json.dumps(
                {'route_records': rec, 'route_status': None if not rec else status, 'error': error or (
                    'RuntimeError: shared GPU lock is held by pid 1' if status == 'LOCK_BUSY' else None),
                 'scores': {'score_composed': ds, 'score_route': ds, 'score_penalty': 1.0}}))
        return d

    def runs_for(self, spec, fn):
        """fn(candidate name, route) -> list of (status, ds) attempts; reused candidates are skipped."""
        for c in spec['candidates']:
            if c.get('reused_from'):
                continue
            for r, job in c['jobs'].items():
                for status, ds in fn(c['name'], r):
                    self.run(job, c, r, status, ds)

    def select(self, variant, stage, queue=None, provisional=False):
        sel = SS.select(variant, stage, self.root, self.jobs, self.sel, queue, provisional)
        SS.write_selection(sel, self.sel)
        return sel


OK = 'Completed'


class SelectionTest(unittest.TestCase):
    def test_rank_ties_go_to_the_earlier_candidate(self):
        self.assertEqual(SS.rank([('a', 0, 1.0), ('b', 1, 1.0 + 1e-12), ('c', 2, 2.0)]), ['c', 'a', 'b'])
        self.assertEqual(SS.rank([('a', 1, 5.0), ('b', 0, 5.0)]), ['b', 'a'])
        self.assertEqual(SS.rank([('a', 0, 1.0), ('b', 1, 1.0 + 1e-6)]), ['b', 'a'])

    def test_full_successive_halving_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Synthetic(tmp)
            _, s1 = S.block('FULL', 'lease_s1')
            a = s1['routes']
            crash_route, sim_route = a[0], a[1]

            def lease1(name, r):
                if name == 'E5' and r == crash_route:
                    return [('Failed - Agent crashed', 0.0), ('Failed - Agent crashed', 0.0)]
                if name == 'B0' and r == sim_route:
                    return [('Failed - Simulation crashed', 0.0), ('Failed - Simulation crashed', 0.0)]
                return [(OK, {'E5': 50.0, 'E10': 60.0, 'B0': 60.0}[name])]
            S.runs_for(s1, lease1)
            sel1 = S.select('FULL', 'lease_s1')
            self.assertEqual(sel1['dropped_routes'], {sim_route: ['B0: Failed - Simulation crashed']})
            rows = {r['candidate']: r for r in sel1['table']}
            self.assertEqual(rows['E5']['per_route'][crash_route]['outcome'], 'agent_crashed')
            self.assertAlmostEqual(rows['E5']['mean_ds'], 50.0 * 9 / 10)            # 9 x 50 + 1 x 0 over 10
            self.assertEqual(rows['E10']['n'], 10)
            self.assertEqual(sel1['ranking'], ['E10', 'B0', 'E5'])                 # E10 = B0: tie to the earlier
            self.assertEqual(sel1['survivors'], ['E10', 'B0'])
            self.assertFalse(sel1['final'])
            # the next block exists only for this selection and holds only the survivors, on T22b
            lines2, s2 = S.block('FULL', 'lease_s2')
            self.assertEqual(len(lines2), 22)
            self.assertEqual({c['name'] for c in s2['candidates']}, {'E10', 'B0'})
            self.assertEqual(s2['routes'], PJ.route_set('T22b'))
            S.runs_for(s2, lambda n, r: [(OK, {'E10': 40.0, 'B0': 70.0}[n])])
            sel2 = S.select('FULL', 'lease_s2')
            self.assertEqual(sel2['selected'], 'B0')
            t22 = {r['candidate']: r['mean_ds_T22'] for r in sel2['table']}
            self.assertAlmostEqual(t22['E10'], (60 * 10 + 40 * 11) / 21)
            self.assertAlmostEqual(t22['B0'], (60 * 10 + 70 * 11) / 21)
            # heuristic grid at L* = B0: d = 10 reused from the lease grid, d = 4 and d = 1 new on T22a
            lines_h1, h1 = S.block('FULL', 'heur_s1')
            self.assertEqual(len(lines_h1), 22)
            d10 = next(c for c in h1['candidates'] if c['name'] == 'd10')
            self.assertEqual(d10['reused_from'], 'lease_s1')
            self.assertEqual(d10['jobs'], next(c for c in s1['candidates'] if c['name'] == 'B0')['jobs'])
            self.assertEqual({j['policy_params']['utility'] for j in lines_h1}, {'v4_adet_d4', 'v4_adet_d1'})
            self.assertTrue(all(j['envelope']['label'] == 'B0' for j in lines_h1))
            S.runs_for(h1, lambda n, r: [(OK, {'d4': 70.0, 'd1': 10.0}[n])])
            selh1 = S.select('FULL', 'heur_s1')
            self.assertEqual(selh1['dropped_routes'], {sim_route: ['d10: Failed - Simulation crashed']})
            self.assertEqual(selh1['survivors'], ['d10', 'd4'])
            lines_h2, h2 = S.block('FULL', 'heur_s2')
            self.assertEqual(len(lines_h2), 11)                                    # only d4 runs; d10 reused
            self.assertEqual(next(c for c in h2['candidates'] if c['name'] == 'd10')['reused_from'], 'lease_s2')
            S.runs_for(h2, lambda n, r: [(OK, 75.0)])
            selh2 = S.select('FULL', 'heur_s2')
            self.assertEqual(selh2['selected'], 'd4')
            lines_a1, a1 = S.block('FULL', 'age_s1')
            self.assertEqual(len(lines_a1), 44)
            self.assertEqual({j['policy_params']['utility'] for j in lines_a1}, {'v4_adet_d4'})
            self.assertEqual(sorted({j['policy_params']['age_lease_s'] for j in lines_a1}), [1.0, 1.5, 2.0, 2.5])
            S.runs_for(a1, lambda n, r: [(OK, {'A1.0': 30.0, 'A1.5': 45.0, 'A2.0': 45.0, 'A2.5': 10.0}[n])])
            sela1 = S.select('FULL', 'age_s1')
            self.assertEqual(sela1['survivors'], ['A1.5', 'A2.0'])
            _, a2 = S.block('FULL', 'age_s2')
            S.runs_for(a2, lambda n, r: [(OK, {'A1.5': 40.0, 'A2.0': 41.0}[n])])
            self.assertEqual(S.select('FULL', 'age_s2')['selected'], 'A2.0')
            # event grid
            _, e1 = S.block('FULL', 'event_s1')
            S.runs_for(e1, lambda n, r: [(OK, {'v2_hb2.0': 20.0, 'v2_hb1.0': 22.0, 's_hb2.0': 25.0,
                                                's_hb1.0': 21.0}[n])])
            self.assertEqual(S.select('FULL', 'event_s1')['survivors'], ['v2_hb1.0', 's_hb2.0'])
            _, e2 = S.block('FULL', 'event_s2')
            S.runs_for(e2, lambda n, r: [(OK, 30.0)])
            self.assertEqual(S.select('FULL', 'event_s2')['selected'], 's_hb2.0')   # 25/22 on T22a, tie on T22b
            doc = SS.freeze('FULL', S.jobs, S.sel)
            self.assertEqual(doc['L_star']['label'], 'B0')
            self.assertEqual(doc['d_star'], {'d': 4, 'utility': 'v4_adet_d4'})
            self.assertEqual(doc['A_star'], {'age_lease_s': 2.0})
            self.assertEqual(doc['event_star']['policy_params']['heartbeat_s'], 2.0)
            self.assertEqual(doc['fl_risk']['lease_point'], 'E10')                 # L* = B0: better of E5 / E10
            self.assertEqual(doc['arms']['fl_heuristic'], {'envelope': 'outputs/framelease_v4/envelopes/B0.json',
                                                           'policy_params': {'utility': 'v4_adet_d4'}})
            self.assertEqual(doc['configurations_selected_from'], {'FrameLease': 5, 'Age-Only': 4,
                                                                   'Event-Triggered': 4})
            self.assertEqual(len(doc['stages']), 8)
            self.future_lines = {'lease_s2': lines2, 'heur_s1': lines_h1, 'heur_s2': lines_h2, 'age_s1': lines_a1}
            if STACK:
                for name, lines in self.future_lines.items():
                    for j in lines[:2]:
                        r = PJ.check_line(j, dry_run=True)
                        self.assertTrue(r['ok'], (name, r['problems']))

    def test_trimmed_one_stage_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Synthetic(tmp)
            _, s1 = S.block('TRIMMED', 'lease_s1')
            S.runs_for(s1, lambda n, r: [(OK, {'E5': 55.0, 'E10': 54.0, 'B0': 55.0}[n])])
            sel = S.select('TRIMMED', 'lease_s1')
            self.assertTrue(sel['final'])
            self.assertEqual(sel['selected'], 'E5')                               # tie with B0: earlier
            lines_h, h = S.block('TRIMMED', 'heur_s1')
            self.assertEqual(len(lines_h), 11)
            self.assertEqual({j['policy_params']['utility'] for j in lines_h}, {'v4_adet_d4'})
            S.runs_for(h, lambda n, r: [(OK, 50.0)])
            self.assertEqual(S.select('TRIMMED', 'heur_s1')['selected'], 'd10')
            lines_a, a = S.block('TRIMMED', 'age_s1')
            self.assertEqual(len(lines_a), 33)
            self.assertEqual({j['policy_params']['utility'] for j in lines_a}, {'heuristic'})
            S.runs_for(a, lambda n, r: [(OK, {'A1.0': 1.0, 'A1.5': 3.0, 'A2.0': 2.0}[n])])
            self.assertEqual(S.select('TRIMMED', 'age_s1')['selected'], 'A1.5')
            _, e = S.block('TRIMMED', 'event_s1')
            S.runs_for(e, lambda n, r: [(OK, {'v2_hb2.0': 5.0, 's_hb1.0': 6.0}[n])])
            self.assertEqual(S.select('TRIMMED', 'event_s1')['selected'], 's_hb1.0')
            doc = SS.freeze('TRIMMED', S.jobs, S.sel)
            self.assertEqual((doc['L_star']['label'], doc['d_star']['d'], doc['A_star']['age_lease_s']),
                             ('E5', 10, 1.5))
            self.assertEqual(doc['fl_risk'], 'not part of the TRIMMED plan')
            self.assertEqual(doc['configurations_selected_from'], {'FrameLease': 4, 'Age-Only': 3,
                                                                   'Event-Triggered': 2})
            if STACK:
                for j in lines_h[:2] + lines_a[:2]:
                    r = PJ.check_line(j, dry_run=True)
                    self.assertTrue(r['ok'], r['problems'])

    def test_pending_retries_and_queue_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Synthetic(tmp)
            _, s1 = S.block('TRIMMED', 'event_s1')
            r0, r1, r2 = s1['routes'][:3]
            plan = {}

            def fn(n, r):
                if n == 'v2_hb2.0' and r == r0:
                    return []                                                     # not run yet
                if n == 'v2_hb2.0' and r == r1:
                    return [('Failed - Simulation crashed', 0.0)]                 # one failed attempt
                if n == 's_hb1.0' and r == r2:
                    return [('Failed - Simulation crashed', 0.0), (OK, 80.0)]     # retry succeeded
                return [(OK, 10.0)]
            S.runs_for(s1, fn)
            with self.assertRaises(RuntimeError):
                SS.select('TRIMMED', 'event_s1', S.root, S.jobs, S.sel)
            prov = SS.select('TRIMMED', 'event_s1', S.root, S.jobs, S.sel, provisional=True)
            self.assertTrue(prov['provisional'])
            path = SS.write_selection(prov, S.sel)
            self.assertTrue(path.name.endswith('.provisional.json'))
            with self.assertRaises(FileNotFoundError):                            # never consumed
                PJ.load_selection('TRIMMED', 'event_s1', S.sel, S.jobs)
            # runner-final records: launch error without a run directory, and the retry rule
            cand = {c['name']: c for c in s1['candidates']}
            qdir = Path(tmp) / 'queue'
            qdir.mkdir()
            recs = [{'event': 'end', 'id': cand['v2_hb2.0']['jobs'][r0]['id'], 'final': True, 'outcome': 'launch_error',
                     'run_dir': None, 'result': None},
                    {'event': 'end', 'id': cand['v2_hb2.0']['jobs'][r1]['id'], 'final': True,
                     'outcome': 'infra_failure', 'run_dir': None, 'result': {'route_status': 'Failed - Simulation crashed'}}]
            (qdir / 'status.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in recs))
            sel = SS.select('TRIMMED', 'event_s1', S.root, S.jobs, S.sel, qdir)
            self.assertTrue(sel['complete'])
            self.assertEqual(sorted(sel['dropped_routes']), sorted([r0, r1]))
            row = {x['candidate']: x for x in sel['table']}['s_hb1.0']
            self.assertEqual(row['per_route'][r2]['ds'], 80.0)
            self.assertEqual(row['n'], 9)
            # without the queue a second failed attempt is final as well
            job = cand['v2_hb2.0']['jobs'][r1]
            S.run(job, cand['v2_hb2.0'], r1, 'Failed - Agent crashed', 0.0)
            out = SS.job_outcome(job, r1, cand['v2_hb2.0'], S.root, None)
            self.assertEqual((out['outcome'], out['ds']), ('agent_crashed', 0.0))
            # a run of another configuration in the same directory is ignored
            other = {**cand['v2_hb2.0'], 'policy_params': {**cand['v2_hb2.0']['policy_params'], 'heartbeat_s': 9.0}}
            job2 = cand['v2_hb2.0']['jobs'][r2]
            self.assertEqual(SS.job_outcome(job2, r2, other, S.root, None)['outcome'], 'pending')

    def test_test_routes_are_refused(self):
        lines, spec = PJ.build_block('TRIMMED', 'lease_s1')
        bad = json.loads(json.dumps(spec))
        bad['routes'][0] = PJ.route_split()['test'][0]['route_id']
        with self.assertRaises(PermissionError):
            SS.stage_table(bad, Path('/nonexistent'))
        bad = json.loads(json.dumps(spec))
        c = bad['candidates'][0]
        r = next(iter(c['jobs']))
        c['jobs'][r]['output_dir'] = 'outputs/framelease_v4/matrix/x'
        with self.assertRaises(PermissionError):
            SS.stage_table(bad, Path('/nonexistent'))

    def test_selection_for_another_job_file_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Synthetic(tmp)
            _, s1 = S.block('TRIMMED', 'lease_s1')
            S.runs_for(s1, lambda n, r: [(OK, 1.0)])
            S.select('TRIMMED', 'lease_s1')
            _, spec_path = PJ.load_stage_spec('TRIMMED', 'lease_s1', S.jobs)
            spec = json.loads(spec_path.read_text())
            spec['note'] = 'changed'
            spec_path.write_text(json.dumps(spec))
            with self.assertRaises(ValueError):
                PJ.build_block('TRIMMED', 'heur_s1', S.sel, S.jobs)


def q_records(*recs):
    return ''.join(json.dumps(r) + '\n' for r in recs)


class QueueRulesTest(unittest.TestCase):
    """--queue: only the runner's final record or a valid run makes a job final (PROTOCOL Sec. 4.2)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.S = Synthetic(self._tmp.name)
        _, self.spec = self.S.block('TRIMMED', 'event_s1')
        self.cand = {c['name']: c for c in self.spec['candidates']}
        self.c = self.cand['v2_hb2.0']
        self.r = self.spec['routes'][0]
        self.job = self.c['jobs'][self.r]
        self.q = Path(self._tmp.name) / 'queue'
        self.q.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def outcome(self, recs=None):
        if recs is None:
            return SS.job_outcome(self.job, self.r, self.c, self.S.root, None)
        (self.q / 'status.jsonl').write_text(q_records(*recs))
        return SS.job_outcome(self.job, self.r, self.c, self.S.root, SS.queue_states(self.q))

    def test_uncounted_attempts_never_make_a_job_final(self):
        jid = self.job['id']
        busy = self.S.run(self.job, self.c, self.r, 'LOCK_BUSY', 0.0)
        fail = self.S.run(self.job, self.c, self.r, 'Failed - Simulation crashed', 0.0)
        self.assertEqual(self.outcome()['outcome'], 'pending')        # no queue: the lock-busy attempt does not count
        recs = [{'event': 'start', 'id': jid, 'attempt': 1},
                {'event': 'end', 'id': jid, 'attempt': 1, 'outcome': 'gpu_lock_busy', 'counted': False, 'final': False,
                 'run_dir': str(busy)},
                {'event': 'start', 'id': jid, 'attempt': 2},
                {'event': 'end', 'id': jid, 'attempt': 2, 'outcome': 'infra_failure', 'counted': True, 'final': False,
                 'run_dir': str(fail), 'result': {'route_status': 'Failed - Simulation crashed'}}]
        o = self.outcome(recs)
        self.assertEqual(o['outcome'], 'pending')                     # the runner still retries
        self.assertEqual(o['queue']['counted'], 1)
        fail2 = self.S.run(self.job, self.c, self.r, 'Failed - Simulation crashed', 0.0)
        recs += [{'event': 'start', 'id': jid, 'attempt': 3},
                 {'event': 'end', 'id': jid, 'attempt': 3, 'outcome': 'infra_failure', 'counted': True, 'final': True,
                  'run_dir': str(fail2), 'result': {'route_status': 'Failed - Simulation crashed'}}]
        self.assertEqual(self.outcome(recs)['outcome'], 'sim_failure')
        # a new attempt budget after the final record (--retry-failed): pending again
        recs += [{'event': 'start', 'id': jid, 'attempt': 4}]
        self.assertEqual(self.outcome(recs)['outcome'], 'pending')
        # 'Agent crashed' as the final cause counts as DS 0
        crash = [{'event': 'end', 'id': jid, 'attempt': 2, 'outcome': 'infra_failure', 'counted': True, 'final': True,
                  'run_dir': None, 'result': {'route_status': 'Failed - Agent crashed'}}]
        self.assertEqual((self.outcome(crash)['outcome'], self.outcome(crash)['ds']), ('agent_crashed', 0.0))

    def test_runner_ok_without_a_matching_run_is_an_error(self):
        jid = self.job['id']
        ok = [{'event': 'end', 'id': jid, 'attempt': 1, 'outcome': 'ok', 'counted': True, 'final': True,
               'run_dir': str(self.S.root / 'nowhere')}]
        with self.assertRaises(SS.SelectionError):
            self.outcome(ok)
        other = self.S.run(self.job, {**self.c, 'policy_params': {**self.c['policy_params'], 'heartbeat_s': 9.0}},
                           self.r, 'Completed', 70.0)                 # another configuration in the same directory
        ok[0]['run_dir'] = str(other)
        with self.assertRaises(SS.SelectionError):
            self.outcome(ok)
        good = self.S.run(self.job, self.c, self.r, 'Completed', 55.0)
        ok[0]['run_dir'] = str(good)
        o = self.outcome(ok)
        self.assertEqual((o['outcome'], o['ds']), ('ok', 55.0))
        # the error reaches the stage selection and the CLI as an error, never as a dropped route
        others = [{'event': 'end', 'id': c['jobs'][r]['id'], 'attempt': 1, 'outcome': 'ok', 'counted': True,
                   'final': True, 'run_dir': str(self.S.run(c['jobs'][r], c, r, 'Completed', 10.0))}
                  for c in self.spec['candidates'] for r in self.spec['routes'] if (c['name'], r) != ('v2_hb2.0', self.r)]
        bad = [{**ok[0], 'run_dir': str(self.S.root / 'nowhere')}]
        (self.q / 'status.jsonl').write_text(q_records(*(others + bad)))
        with self.assertRaises(SS.SelectionError):
            SS.select('TRIMMED', 'event_s1', self.S.root, self.S.jobs, self.S.sel, self.q)
        (self.q / 'status.jsonl').write_text(q_records(*(others + ok)))
        sel = SS.select('TRIMMED', 'event_s1', self.S.root, self.S.jobs, self.S.sel, self.q)
        self.assertTrue(sel['complete'])
        self.assertEqual(sel['finality'], 'runner records (--queue)')

    def test_repeated_setup_failures_are_flagged(self):
        S, spec = self.S, self.spec
        setup = "Failed - Agent couldn't be set up"
        bad_routes = spec['routes'][:2]
        for c in spec['candidates']:
            for r, job in c['jobs'].items():
                if c['name'] == 's_hb1.0' and r in bad_routes:
                    S.run(job, c, r, setup, 0.0)
                    S.run(job, c, r, setup, 0.0)
                else:
                    S.run(job, c, r, OK, 20.0 if c['name'] == 'v2_hb2.0' else 30.0)
        sel = SS.select('TRIMMED', 'event_s1', S.root, S.jobs, S.sel)
        self.assertEqual(sorted(sel['dropped_routes']), sorted(bad_routes))      # the registered rule is unchanged
        self.assertEqual(sel['selected'], 's_hb1.0')
        self.assertEqual(len(sel['flags']), 1)
        self.assertEqual(sel['flags'][0]['candidate'], 's_hb1.0')
        self.assertEqual(sel['flags'][0]['setup_failures'], 4)
        self.assertTrue(any(line.lstrip().startswith('FLAG s_hb1.0') for line in SS.summary_lines(sel)))

    def test_cli_errors_are_clean(self):
        import contextlib
        import io
        for argv, rc, text in ((['--variant', 'FULL', '--stage', 'ref'], 2, 'reference block'),
                               (['--variant', 'FULL', '--stage', 'nope'], 2, 'has no stage'),
                               (['--variant', 'TRIMMED', '--stage', 'ref'], 2, 'has no stage'),
                               (['--variant', 'FULL', '--stage', 'heur_s1', '--jobs-dir', str(self.S.jobs)], 2,
                                'not written yet'),
                               (['--variant', 'TRIMMED', '--stage', 'event_s1', '--jobs-dir', str(self.S.jobs),
                                 '--selection-dir', str(self.S.sel), '--queue', str(self.q / 'missing')], 2, 'not found'),
                               (['--variant', 'FULL', '--freeze', '--jobs-dir', str(self.S.jobs),
                                 '--selection-dir', str(self.S.sel)], 2, 'not written yet')):
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(SS.main(argv), rc, argv)
            self.assertIn(text, err.getvalue(), argv)
            self.assertNotIn('Traceback', err.getvalue())


class BudgetTest(unittest.TestCase):
    """Every budget figure comes from its own run count (no sums of rounded values), in budget*.md and PROTOCOL.md."""

    def test_rows_from_run_counts(self):
        from decimal import ROUND_HALF_UP, Decimal
        from fractions import Fraction

        def r1(x):
            return float((Decimal(x.numerator) / Decimal(x.denominator)).quantize(Decimal('0.1'),
                                                                                  rounding=ROUND_HALF_UP))
        for v in MPT.VARIANTS:
            b = MPT.variant_budget(v)
            rows = b['blocks'] + list(b['phases'].values()) + [b['total'], b['without_smoke']]
            for row in rows:
                n = row['runs']
                self.assertEqual(row['gpu_h'], r1(Fraction(n * 450, 3600)), (v, row))
                self.assertEqual(row['gpu_h_worst'], r1(Fraction(n * 1500, 3600)), (v, row))
                self.assertEqual(row['disk_gb'], n / 100)
            self.assertEqual(b['total']['runs'], sum(x['runs'] for x in b['blocks']))
            self.assertEqual(sum(p['runs'] for p in b['phases'].values()), b['total']['runs'])
            first = next(iter(b['phases'].values()))
            need = Fraction(b['total']['runs'] * 10 ** 7, 2 ** 30) + 6
            self.assertEqual(first['disk_prereq_gib'], math.ceil(need * 10) / 10)
        self.assertEqual(MPT.variant_budget('FULL')['total']['gpu_h'], 130.8)        # 1046 x 7.5 min = 130.75 h
        self.assertEqual(MPT.variant_budget('TRIMMED')['total']['gpu_h'], 72.4)      # 579 x 7.5 min = 72.375 h

    def test_written_tables_and_protocol_agree(self):
        split, budget = MPT.build()
        files = MPT.render(split, budget)
        protocol = (ROOT / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
        for name in ('budget.md', 'budget_trimmed.md'):
            self.assertEqual((MPT.OUT / name).read_text(), files[name], name)       # make_protocol_tables --check
            tables = [ln for ln in files[name].splitlines() if ln.startswith('|')]
            for ln in tables:
                self.assertTrue(ln in protocol, f'{name} row missing in PROTOCOL.md: {ln}')



@unittest.skipUnless(STACK, 'official stack variables not set (source linux/env.sh)')
class WrittenJobFilesTest(unittest.TestCase):
    """The written job files: every line passed gpu_queue, the pins, the launcher and its --dry-run when it was
    written (check.json); a sample is re-checked now, against the current tree."""

    FILES = [('P1-0', 'b00_smoke'), ('FULL', 'b01_ref'), ('FULL', 'b02_lease_s1'), ('FULL', 'b03_event_s1'),
             ('TRIMMED', 'b02_lease_s1'), ('TRIMMED', 'b03_event_s1')]

    def test_written_files(self):
        for d, base in self.FILES:
            path = PJ.JOBS_DIR / d / f'{base}.jsonl'
            if not path.is_file():
                self.skipTest(f'{path} not written yet')
            lines = [json.loads(x) for x in path.read_text().splitlines()]
            check = json.loads((PJ.JOBS_DIR / d / f'{base}.check.json').read_text())
            self.assertEqual(check['job_file_sha256'], PJ.sha256_file(path))
            self.assertEqual(check['problems'], [])
            self.assertTrue(check['all_dry_runs_ok'])
            self.assertEqual(len(check['lines']), len(lines))
            self.assertEqual(PJ.static_problems(lines), [], base)
            for j in lines[:2] + lines[-1:]:
                r = PJ.check_line(j, dry_run=True)
                self.assertTrue(r['ok'], (base, r['problems']))


if __name__ == '__main__':
    unittest.main()
