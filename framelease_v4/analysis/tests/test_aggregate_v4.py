"""The P7 aggregator (framelease_v4/analysis/aggregate_v4.py; PROTOCOL Secs. 9.1, 9.7, 9.8, 9.11; GAP_AUDIT Sec. 3.7
R-1, R-2, R-3). CPU only; every run directory, job file, runner record, block spec and freeze is synthetic and lives in a
temporary directory.

  cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/analysis/tests/test_aggregate_v4.py

What is shown: the final run of a job comes from the runner's final record (or the first valid record without a
queue), with the job's own kappa and seed (p1_jobs.KAPPA / SEED restored); a pin mismatch is a code mismatch; every
job without a selected run carries its Sec. 9.8 reason (not_launched, pending, agent_crashed, sim_failure,
selection_error); test-route rows are health-only; the protocol-arm labels of fl_full (RL freeze families by network
file sha256), fl_risk (tuning freeze) and fl_global_shield (configuration arm, validity source); block specs and
duplicate job ids are checked; the outputs carry the sha256 of every input and output and are never written into a
protected directory or over earlier outputs without --force; the Part B columns (extra metrics, per-run R-3 checks,
the commit audit of the selected run) are in the rows, a health-only row keeps only health, prefix timing and checks,
and the commit audit covers every attempt and the runs that match no job line.

Injected failures (one queue, one failure per job): a commit after its deadline, a stale version and a cancelled commit
(R-2 FAIL in that run only, reported, not excluded), a pin mismatch, a missing run, a job never launched, an
unfinished run (pending, its directory still audited), a network sha256 outside the RL freeze (label problem), the
background-load flag (reported per run and per arm, never excluded), a test route (health-only, its R-2 audit
WITHHELD); a malformed log is an ERROR of the audit and empties only the failed metric steps' columns (the route with a
valid official record stays in the analysis), never a crash or a pass.

Labels and summaries: the output directory (.../ablation/<arm>/) must name the label; the arm summary never pools
seeds, phases, blocks or candidates; code_sha256 covers the modules imported inside functions, inputs the
registration manifest.

Sec. 9.11 guard: before a valid analysis-freeze record a test-route row is health-only, its R-2 audit is withheld, a
cross-arm summary of test routes is refused (API and CLI, exit 4) and every CLI request is logged; test_routes cannot
remove a registered test route; a valid record cited by a development copy of PROTOCOL.md (frozen_development)
releases the rows it covers on extra routes (EXTRA_ROUTE) with their audits, never a registered test route; a rerun
or a changed job file after the freeze is withheld; invalid, forged or edited records are refused; a freeze record
waits for every job (or a cut); the route split must be the registered one; --required-job-files is checked.
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
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

from framelease_v4.analysis import aggregate_v4 as A  # noqa: E402
from framelease_v4.analysis import interim_guard as G  # noqa: E402
from framelease_v4.protocol import check_smoke as CS  # noqa: E402
from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402

TRAIN_ROUTE, TEST_ROUTE = '1792', '1711'      # 1711: a test route of the registered split
EXTRA_ROUTE = '2086'                          # a registered training route the tests add as an extra test route
PIN = {'framelease_v4/arms/arms_v4.py': 'a' * 64, 'framelease_common.py': 'b' * 64}
NET = {'fqi': 'f' * 64, 'bandit': 'e' * 64, 'fqi_nolease': 'd' * 64}


def job_line(jid, arm='fixed_deep', route=TRAIN_ROUTE, kappa=1.0, seed=11, training=True, **kw):
    job = {'id': jid, 'arm_name': arm, 'candidate': arm, 'route_id': route, 'kappa': kappa, 'seed': seed,
           'output_dir': f'out/{arm}_k{kappa}', 'policy_params': {}, 'envelope': None, 'require_sha256': dict(PIN),
           'training_route': training, 'phase': 'P1', 'block': 'ref'}
    job.update(kw)
    return job


DEFAULT_COMMITS = ((1, 0, 0.5, 3.0, 0.6),)      # (job id, obs id, commit_s, deadline_s, job end_s): one clean commit


def make_run(root, job, name=None, status='Completed', pins=None, sources=('suffix_lease',),
             v4_extra=None, commits=DEFAULT_COMMITS, prefix_s=0.42, finished=True):
    """A minimal run directory of a job (config, manifest pins, result, runtime logs): one job per commits entry, each
    with one accepted step commit (the first job has one step per validity source) and its job_start / commit events;
    prefix_s is the charged prefix / kappa; finished False leaves out metrics/result.json and summary.json (a run
    still going, or killed)."""
    run = Path(root) / job['output_dir'] / 'runs' / (name or f'20261111T010101_{job["id"]}')
    fl = run / 'raw' / 'agent' / 'framelease'
    fl.mkdir(parents=True)
    (run / 'metrics').mkdir()
    v4 = {'arm': job['arm_name'], 'agent': {'policy_params': dict(job['policy_params'])}, **(v4_extra or {})}
    cfg = {'v4_arm': job['arm_name'], 'route': {'route_id': job['route_id'], 'town': 'Town12'},
           'kappa': job['kappa'], 'seed': job['seed'], 'v4': v4,
           'fast_prefix': {'options': list(CS.FAST_PREFIX_OPTIONS)},
           'envelope_sha256': (job.get('envelope') or {}).get('sha256')}
    (run / 'config.json').write_text(json.dumps(cfg))
    pins = dict(job['require_sha256'], **(pins or {}))
    (run / 'manifest.json').write_text(json.dumps(
        {'status': 'COMPLETED' if finished else 'RUNNING',
         'identity': {'code': {str(ROOT / k): v for k, v in pins.items()}}}))
    if finished:
        (run / 'metrics' / 'result.json').write_text(json.dumps(
            {'route_records': 1, 'route_status': status, 'scores': {'score_composed': 40.0, 'score_route': 50.0,
                                                                     'score_penalty': 0.8},
             'meta': {'route_length': 400.0, 'duration_game': 60.0}, 'infractions': {}, 'timed_out': False,
             'wall_s': 320.0}))
        (run / 'raw' / 'official_results.json').write_text('{}')
        (fl / 'summary.json').write_text(json.dumps({'v4': {'ticks': 40}}))
    with open(fl / 'ticks.jsonl', 'w') as f:
        for k in range(40):
            f.write(json.dumps({'tick': k, 'sim_s': (k + 1) * 0.05, 'mode': 'track', 'action_age_s': 0.3}) + '\n')
    k = float(job['kappa'])
    rows, events = [], []
    for n, (jid, obs, t_c, dl, t_end) in enumerate(commits):
        t0 = 0.0 if n == 0 else commits[n - 1][4]
        commit = {'accepted': True, 'reason': 'accepted', 'commit_s': t_c, 'margin_at_commit_m': None,
                  'overridden': False}
        steps = [{'depth': i + 1, 'release_s': t_c - 0.01 + 0.02 * i, 'timeline_cost_s': 0.02 * k,
                  'validity': {'source': s, 'deadline_s': dl, 'lease_s': dl - t0},
                  **({'commit': commit} if i == 0 else {})}
                 for i, s in enumerate(sources if n == 0 else sources[:1])]
        rows.append({'job_id': jid, 'obs_id': obs, 'capture_s': t0, 'start_s': t0, 'end_s': t_end,
                     'prefix': {'timeline_cost_s': prefix_s * k}, 'committed_depths': [1], 'steps': steps})
        events += [{'kind': 'job_start', 'job_id': jid, 'sim_s': t0, 'overhead_s': 0.0,
                    'prefix_timeline_s': prefix_s * k, 'prefix_cost_s': prefix_s},
                   {'kind': 'commit', 'job_id': jid, 'obs_id': obs, 'depth': 1, 'capture_s': t0,
                    'release_s': t_c - 0.01, 'commit_s': t_c, 'deadline_s': dl, 'lease_s': dl - t0,
                    'margin_at_commit_m': None, 'would_reject': None}]
    (fl / 'jobs.jsonl').write_text(''.join(json.dumps(j) + '\n' for j in rows))
    (fl / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
    (fl / 'decisions.jsonl').write_text('')
    return run


def write_jobs(path, jobs):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(j, sort_keys=True) + '\n' for j in jobs))
    return path


def write_status(qdir, records):
    (Path(qdir) / 'status.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records))


def end(jid, attempt=1, outcome='ok', run=None, final=True, status=None):
    return {'event': 'end', 'id': jid, 'attempt': attempt, 'final': final, 'counted': True, 'outcome': outcome,
            'run_dir': None if run is None else str(run), 'result': {'route_status': status}}


def start(jid, attempt=1):
    return {'event': 'start', 'id': jid, 'attempt': attempt}


def by_job(rows):
    return {r['job']: r for r in rows}


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / 'root'
        self.queue = self.tmp / 'queue'

    def tearDown(self):
        self._tmp.cleanup()

    def run_agg(self, jobs, records, **kw):
        write_jobs(self.queue / 'jobs.d' / 'b01.jsonl', jobs)
        write_status(self.queue, records)
        return A.aggregate([self.queue], root=self.root, test_routes={TEST_ROUTE, EXTRA_ROUTE}, **kw)


# ============================================================================================ selection and rows

class Selection(Base):
    def test_final_record_row_and_metrics(self):
        job = job_line('j_ok')
        run = make_run(self.root, job)
        rows, doc = self.run_agg([job], [start('j_ok'), end('j_ok', run=run)])
        r = rows[0]
        self.assertEqual((r['outcome'], r['code_check'], r['analysis_use'], r['missing_reason']),
                         ('ok', CS.PASS, True, None))
        self.assertEqual((r['protocol_arm'], r['label_source']), ('fixed_deep', 'launcher arm'))
        self.assertEqual(r['driving_score'], 40.0)
        for k in ('realized_invalid_ticks', 'realized_invalid_tick_ratio', 'realized_available'):
            self.assertIn(k, r)                                  # Amendment A2 keys, single prefix
        self.assertFalse(any(k.startswith('realized_realized_') for k in r))
        self.assertEqual(doc['outcomes'], {'ok': 1})
        self.assertIn(PJ.rel(run / 'config.json'), doc['inputs'])
        self.assertIn(PJ.rel(self.queue / 'status.jsonl'), doc['inputs'])

    def test_km_driven_floor(self):
        """Sec. 6.1: km driven = route length x RC / 100 with a floor of 0.001 km; runs.csv carries the floored km,
        the per-km metrics divide by it, the pooled arm summary sums it; a record without a route length gives none
        (nothing imputed, Sec. 9.8)."""
        jobs = [job_line('j_rc0'), job_line('j_rc50', route='1833'), job_line('j_nolen', route='2129')]
        runs = {j['id']: make_run(self.root, j) for j in jobs}
        res = runs['j_rc0'] / 'metrics' / 'result.json'
        doc = json.loads(res.read_text())
        doc['scores']['score_route'] = 0.0                              # RC 0: 0.0 km before the floor
        doc['infractions'] = {'collisions_vehicle': ['hit'], 'red_light': ['ran']}
        res.write_text(json.dumps(doc))
        nolen = runs['j_nolen'] / 'metrics' / 'result.json'
        nolen.write_text(json.dumps({**json.loads(nolen.read_text()), 'meta': {'duration_game': 60.0}}))
        rows, doc = self.run_agg(jobs, [x for j in jobs for x in (start(j['id']), end(j['id'], run=runs[j['id']]))])
        r = by_job(rows)
        self.assertEqual((A.KM_FLOOR, r['j_rc0']['route_completion'], r['j_rc0']['km_driven']), (0.001, 0.0, 0.001))
        self.assertEqual((r['j_rc0']['collisions_total'], r['j_rc0']['collisions_per_km']), (1, 1 / 0.001))
        self.assertEqual((r['j_rc0']['infractions_penalized'], r['j_rc0']['infractions_per_km']), (2, 2 / 0.001))
        self.assertAlmostEqual(r['j_rc50']['km_driven'], 400.0 / 1000.0 * 50.0 / 100.0)     # above the floor: as is
        self.assertEqual((r['j_nolen']['valid_record'], r['j_nolen']['analysis_use'], r['j_nolen'].get('km_driven'),
                          r['j_nolen'].get('collisions_per_km'), r['j_nolen']['infractions_per_km']),
                         (1, True, None, None, None))
        A.write_outputs(self.tmp / 'out', rows, doc)
        with open(self.tmp / 'out' / 'runs.csv', newline='') as f:
            csv_km = {x['job']: x['km_driven'] for x in csv.DictReader(f)}
        self.assertEqual((float(csv_km['j_rc0']), csv_km['j_nolen']), (0.001, ''))
        summary = A.arm_summary(rows, 'training')                       # one group: same arm, kappa, seed, block
        self.assertEqual([(s['routes'], s['collisions_per_km_pooled']) for s in summary], [(3, 1 / (0.001 + 0.2))])
        self.assertEqual(A.floor_km({'km_driven': 0.0004}), {'km_driven': 0.001})
        self.assertEqual(A.floor_km({'km_driven': None, 'x': 1}), {'km_driven': None, 'x': 1})
        self.assertEqual(A.floor_km({}), {})

    def test_job_kappa_and_seed_and_restore(self):
        job = job_line('j_k15', kappa=1.5, seed=12)
        run = make_run(self.root, job)
        rows, _ = self.run_agg([job], [start('j_k15'), end('j_k15', run=run)])
        self.assertEqual((rows[0]['outcome'], rows[0]['analysis_use']), ('ok', True))
        self.assertEqual((PJ.KAPPA, PJ.SEED), (1.0, 11))

    def test_pin_mismatch_is_code_mismatch(self):
        job = job_line('j_pin')
        run = make_run(self.root, job, pins={'framelease_common.py': 'c' * 64})
        rows, doc = self.run_agg([job], [start('j_pin'), end('j_pin', run=run)])
        r = rows[0]
        self.assertEqual((r['code_check'], r['analysis_use'], r['missing_reason']), (CS.FAIL, False, 'code_mismatch'))
        self.assertEqual(doc['code_mismatches'][0]['job'], 'j_pin')

    def test_missing_reasons(self):
        jobs = [job_line(f'j_{n}', route=r) for n, r in
                (('none', '2215'), ('open', '2539'), ('crash', '2715'), ('sim', '2943'), ('err', '3184'))]
        crash = make_run(self.root, jobs[2], status='Agent crashed')
        sim = make_run(self.root, jobs[3], status='Simulation crashed')
        recs = [start('j_open'),
                start('j_crash'), end('j_crash', run=crash, outcome='failed', status='Agent crashed'),
                start('j_sim'), end('j_sim', run=sim, outcome='failed', status='Simulation crashed'),
                start('j_err'), end('j_err', run=self.root / 'nowhere')]
        rows = by_job(self.run_agg(jobs, recs)[0])
        want = {'j_none': 'not_launched', 'j_open': 'pending', 'j_crash': 'agent_crashed', 'j_sim': 'sim_failure',
                'j_err': 'selection_error'}
        self.assertEqual({j: r['missing_reason'] for j, r in rows.items()}, want)
        self.assertFalse(any(r['analysis_use'] for r in rows.values()))
        self.assertIsNone(rows['j_crash'].get('driving_score'))   # nothing imputed (Sec. 9.8)
        self.assertEqual({r['protocol_arm'] for r in rows.values()}, {'fixed_deep'})   # the arm of a dropped route

    def test_without_queue_first_valid_record(self):
        job = job_line('j_noq')
        make_run(self.root, job, name='20261111T010101_aaaaaaaa', status='Simulation crashed')
        make_run(self.root, job, name='20261111T020202_bbbbbbbb')
        f = write_jobs(self.tmp / 'jobs.jsonl', [job])
        rows, _ = A.aggregate(job_files=[f], root=self.root, test_routes={TEST_ROUTE})
        self.assertEqual(rows[0]['outcome'], 'ok')
        self.assertTrue(rows[0]['selected_run'].endswith('20261111T020202_bbbbbbbb'))

    def test_test_route_rows_are_health_only(self):
        jobs = [job_line('j_test', route=TEST_ROUTE, training=False), job_line('j_undeclared', route='2215')]
        del jobs[1]['training_route']
        runs = [make_run(self.root, j) for j in jobs]
        rows = by_job(self.run_agg(jobs, [x for j, r in zip(jobs, runs) for x in (start(j['id']),
                                                                                   end(j['id'], run=r))])[0])
        for r in rows.values():
            self.assertEqual((r['health_only'], r['analysis_use'], r['missing_reason']), (True, False, 'health_only'))
            self.assertNotIn('driving_score', r)
            self.assertEqual(r['wall_s'], 320.0)
        self.assertTrue(A.health_only(job_line('x', route=TEST_ROUTE, training=True), {TEST_ROUTE}))
        self.assertIn(TEST_ROUTE, A.test_route_ids())

    def test_duplicate_job_id_refused(self):
        job = job_line('j_dup')
        write_jobs(self.queue / 'jobs.d' / 'b01.jsonl', [job])
        write_status(self.queue, [])
        f = write_jobs(self.tmp / 'again.jsonl', [job])
        with self.assertRaises(A.AggregateError):
            A.collect_jobs([self.queue], [f])

    def test_malformed_job_line_refused(self):
        f = self.tmp / 'bad.jsonl'
        f.write_text(json.dumps(job_line('j1')) + '\n{"id": \n')
        with self.assertRaises(A.AggregateError):
            A.load_job_file(f)


# ============================================================================================ block specs

class Specs(Base):
    def spec(self, job_file, jobs, **over):
        doc = {'schema': 'framelease_v4.p1_stage/1', 'block': 'ref', 'job_file': 'x',
               'job_file_sha256': PJ.sha256_file(job_file),
               'candidates': [{'name': 'fixed_deep', 'arm': 'fixed_deep',
                               'jobs': {j['route_id']: {'id': j['id'], 'block': 'ref', 'output_dir': j['output_dir']}
                                        for j in jobs}}]}
        doc.update(over)
        p = self.tmp / 'specs' / 'b01.stage.json'
        p.parent.mkdir(exist_ok=True)
        p.write_text(json.dumps(doc))
        return p

    def test_spec_consistent_and_recorded(self):
        job = job_line('j_s')
        f = write_jobs(self.queue / 'jobs.d' / 'b01.jsonl', [job])
        p = self.spec(f, [job])
        write_status(self.queue, [])
        rows, doc = A.aggregate([self.queue], specs=[p.parent], root=self.root, test_routes={TEST_ROUTE})
        self.assertEqual(rows[0]['block_spec'], PJ.rel(p))
        self.assertIn(PJ.rel(p), doc['inputs'])

    def test_spec_schemas_of_the_three_writers(self):
        """load_specs reads the specs of p1_jobs.py, p2_jobs.py and test_jobs.py (APPLY_PLAN step 6, TESTJOBS review
        M-1: 'framelease_v4.test_stage/1', jobs[] as written) and refuses any other schema."""
        from framelease_v4.protocol import p2_jobs as P2
        from framelease_v4.protocol import test_jobs as TJ
        self.assertEqual(A.STAGE_SCHEMAS, (PJ.STAGE_SCHEMA, P2.STAGE_SCHEMA, TJ.STAGE_SCHEMA))
        job = job_line('j_t', block='s_main', protocol_arm='fixed_deep')
        f = write_jobs(self.queue / 'jobs.d' / 'b11.jsonl', [job])
        write_status(self.queue, [])
        entry = {'line': 1, 'id': 'j_t', 'block': 's_main', 'protocol_arm': 'fixed_deep', 'route_id': TRAIN_ROUTE,
                 'output_dir': job['output_dir']}
        p = self.tmp / 'test_specs' / 'b11.stage.json'
        p.parent.mkdir()

        def write(schema):
            p.write_text(json.dumps({'schema': schema, 'variant': 'FULL', 'block': 's_main', 'job_file': 'x',
                                     'job_file_sha256': PJ.sha256_file(f), 'jobs': [entry]}))
            return p
        write(TJ.STAGE_SCHEMA)
        self.assertEqual([(q, s['schema']) for q, s in A.load_specs([p.parent])], [(p, TJ.STAGE_SCHEMA)])
        self.assertEqual(A.spec_jobs(A.load_specs([p])[0][1]),
                         {'j_t': {'block': 's_main', 'output_dir': job['output_dir'], 'route_id': TRAIN_ROUTE,
                                  'protocol_arm': 'fixed_deep'}})
        rows, doc = A.aggregate([self.queue], specs=[p.parent], root=self.root, test_routes={TEST_ROUTE})
        self.assertEqual(rows[0]['block_spec'], PJ.rel(p))
        self.assertIn(PJ.rel(p), doc['inputs'])
        for bad in ('framelease_v4.test_check/1', 'framelease_v4.test_jobs_index/1', None):
            with self.subTest(schema=bad), self.assertRaises(A.AggregateError):
                A.load_specs([write(bad)])

    def test_spec_disagreement_refused(self):
        job = job_line('j_s')
        f = write_jobs(self.queue / 'jobs.d' / 'b01.jsonl', [job])
        write_status(self.queue, [])
        bad = dict(job, output_dir='out/elsewhere')
        for p in (self.spec(f, [bad]), self.spec(f, [job], job_file_sha256='0' * 64),
                  self.spec(f, [job, job_line('j_unknown', route='2215')])):
            with self.assertRaises(A.AggregateError):
                A.aggregate([self.queue], specs=[p], root=self.root, test_routes={TEST_ROUTE})


# ============================================================================================ labels

def rl_freeze(path, nets=NET, frozen=False):
    fams = {f: {'network': {'file_sha256': sha, 'arm': A.RL_ARM_OF[f], 'name': f'v4_qnet_{sha[:12]}'}}
            for f, sha in nets.items()}
    lines = {A.RL_ARM_OF[f]: {'qnet_file_sha256': sha} for f, sha in nets.items()}
    Path(path).write_text(json.dumps({'schema': A.RL_FREEZE_SCHEMA, 'mode': 'production' if frozen else 'development',
                                      'frozen': frozen, 'd_star': 10, 'families': fams, 'job_lines': lines}))
    return path


def qnet_cfg(sha):
    return {'v4_arm': 'fl_full', 'v4': {'arm': 'fl_full', 'utility': {'env_files_sha256': {'/abs/q.json': sha}}}}


class Labels(Base):
    def test_rl_families_by_network_sha256(self):
        rl = A.load_rl_freeze(rl_freeze(self.tmp / 'rl.json'), allow_dev=True)
        for fam, sha in NET.items():
            arm = A.RL_ARM_OF[fam]
            got = A.protocol_label(job_line('j', arm='fl_full', protocol_arm=arm), qnet_cfg(sha), {}, rl)
            self.assertEqual((got[0], got[2]), (arm, []))
        arm, _, probs = A.protocol_label(job_line('j', arm='fl_full', protocol_arm='fl_full'), qnet_cfg(NET['bandit']),
                                         {}, rl)
        self.assertEqual(arm, 'fl_bandit')
        self.assertTrue(any('protocol_arm' in p for p in probs))
        self.assertTrue(A.protocol_label(job_line('j', arm='fl_full'), qnet_cfg('0' * 64), {}, rl)[2])
        self.assertTrue(A.protocol_label(job_line('j', arm='fl_full'), qnet_cfg(NET['fqi']), {}, None)[2])

    def test_shared_network_needs_job_line(self):
        nets = dict(NET, fqi_nolease=NET['bandit'])
        rl = A.load_rl_freeze(rl_freeze(self.tmp / 'rl.json', nets), allow_dev=True)
        cfg = qnet_cfg(NET['bandit'])
        self.assertEqual(A.protocol_label(job_line('j', arm='fl_full', protocol_arm='fl_fqi_nolease'), cfg, {}, rl)[:1],
                         ('fl_fqi_nolease',))
        self.assertTrue(A.protocol_label(job_line('j', arm='fl_full'), cfg, {}, rl)[2])

    def test_dev_freeze_refused_by_default(self):
        with self.assertRaises(A.AggregateError):
            A.load_rl_freeze(rl_freeze(self.tmp / 'rl.json'))
        self.assertTrue(A.load_rl_freeze(rl_freeze(self.tmp / 'rl2.json', frozen=True))['frozen'])

    def test_fl_risk_from_tuning_freeze(self):
        sel = self.tmp / 'selection.json'
        sel.write_text(json.dumps({'schema': A.SS.FREEZE_SCHEMA, 'L_star': {'envelope_sha256': 'b0' * 32},
                                   'd_star': {'d': 10}, 'fl_risk': {'lease_point': 'E10'}}))
        tun = A.load_tuning_freeze(sel, envelopes={'E10': {'sha256': 'e1' * 32}})
        job = job_line('j', arm='fl_heuristic', protocol_arm='fl_risk')
        self.assertEqual(A.protocol_label(job, {'v4_arm': 'fl_heuristic', 'envelope_sha256': 'e1' * 32}, {}, None,
                                          tun)[::2], ('fl_risk', []))
        arm, _, probs = A.protocol_label(job, {'v4_arm': 'fl_heuristic', 'envelope_sha256': 'b0' * 32}, {}, None, tun)
        self.assertEqual(arm, 'fl_heuristic')
        self.assertTrue(probs)
        self.assertTrue(A.protocol_label(job, {'v4_arm': 'fl_heuristic'}, {}, None, None)[2])

    def test_global_shield_by_config_and_validity_source(self):
        job = job_line('j_gs', arm=A.GLOBAL_SHIELD)
        ext = {'extension': {'global_lease': {'h_bar_s': 2.5}}}
        good = make_run(self.root, job, sources=('global_lease',) * 3, v4_extra=ext)
        cfg = json.loads((good / 'config.json').read_text())
        self.assertEqual(A.protocol_label(job, cfg, A.validity_sources(good))[::2], (A.GLOBAL_SHIELD, []))
        self.assertTrue(A.protocol_label(job, cfg, {'global_lease': 2, 'suffix_lease': 1})[2])
        self.assertTrue(A.protocol_label(job, {'v4_arm': A.GLOBAL_SHIELD, 'v4': {}}, {'global_lease': 1})[2])

    def test_output_directory_label(self):
        """GAP_AUDIT Sec. 2: the protocol arm is also recorded in the output directory (.../ablation/<arm>/)."""
        rl = A.load_rl_freeze(rl_freeze(self.tmp / 'rl.json'), allow_dev=True)
        cfg = qnet_cfg(NET['bandit'])
        for out, ok in (('outputs/framelease_v4/p6/ablation/fl_bandit/k1.0', True),
                        ('outputs/framelease_v4/p6/ablation/fl_full/k1.0', False),
                        ('outputs/framelease_v4/p6/ablation', False), ('outputs/framelease_v4/offline_ablation/x', True),
                        ('out/fl_full_k1.0', True)):
            with self.subTest(out):
                job = job_line('j', arm='fl_full', protocol_arm='fl_bandit', output_dir=out)
                arm, _, probs = A.protocol_label(job, cfg, {}, rl)
                self.assertEqual((arm, not probs), ('fl_bandit', ok), probs)
        self.assertEqual([A.output_dir_arm(p) for p in ('a/ablation/x/y', 'a/ablation', 'a/b', None)],
                         ['x', '', None, None])
        job = job_line('j_lbl', output_dir='out/ablation/fast_only/k1.0')               # a run of fixed_deep
        rows, _ = self.run_agg([job], [start('j_lbl'), end('j_lbl', run=make_run(self.root, job))])
        self.assertEqual((rows[0]['missing_reason'], rows[0]['analysis_use']), ('label_problem', False))
        self.assertIn('output directory', rows[0]['label_problem'])


# ============================================================================================ Part B in the rows

class PartB(Base):
    def test_metric_and_check_columns_health_only_and_audit_of_every_attempt(self):
        train, test = job_line('j_tr'), job_line('j_te', route=TEST_ROUTE, training=False)
        crashed = make_run(self.root, train, name='20261111T010101_a', status='Simulation crashed')
        final = make_run(self.root, train, name='20261111T020202_b')
        tr = make_run(self.root, test, name='20261111T030303_c')
        make_run(self.root, job_line('other', seed=12), name='20261111T040404_d')       # matches no job line
        rows, doc = self.run_agg([train, test], [start('j_tr'), end('j_tr', outcome='sim_failure', final=False,
                                                                     run=crashed),
                                                 start('j_tr', 2), end('j_tr', 2, run=final),
                                                 start('j_te'), end('j_te', run=tr)])
        r = by_job(rows)
        a, h = r['j_tr'], r['j_te']
        self.assertTrue(a['analysis_use'])
        self.assertEqual((a['dmr'], a['cuda_s_per_s'], a['infractions_per_km']), (0.0, a['gpu_usage'] / 1.0, 0.0))
        self.assertEqual((a['prefix_quantum_s_p50'], a['charged_prefix_check'], a['bg_load_status']),
                         (0.42, 'PASS', 'within'))
        self.assertEqual((a['fast_prefix_check'], a['config_check']), (CS.FAIL, 'PASS'))   # no fast_prefix.json
        self.assertEqual((a['commit_audit_status'], a['commit_audit_accepted'], a['commit_audit_violations']),
                         ('PASS', 1, 0))
        self.assertIn('predicted_expiry_fallback', a)
        self.assertTrue(h['health_only'])
        self.assertEqual((h['bg_load_status'], h['prefix_quantum_s_p50']), ('within', 0.42))
        for k in ('driving_score', 'dmr', 'infractions_per_km', 'predicted_expiry_fallback', 'p_both',
                  'lease_utilization', 'realized_invalid_tick_ratio'):
            self.assertNotIn(k, h)
        # R-2 of the test-route run is withheld before the freeze (H5 is a registered outcome)
        self.assertEqual((h['commit_audit_status'], h['commit_audit_accepted'], h['commit_audit_violations']),
                         (A.WITHHELD, None, None))
        audit = doc['commit_audit']
        self.assertEqual((audit['status'], audit['runs_audited'], audit['runs_withheld'], audit['runs_matching_no_job']),
                         ('INCOMPLETE', 3, 1, 1))
        self.assertEqual(sorted(x['run_dir'].rsplit('/', 1)[1] for x in audit['runs'] if 'j_tr' in x['jobs']),
                         ['20261111T010101_a', '20261111T020202_b'])
        held = [x for x in audit['runs'] if x['status'] == A.WITHHELD]
        self.assertEqual([(x['jobs'], sorted(x)) for x in held], [(['j_te'], ['guard_note', 'jobs', 'run_dir',
                                                                               'status'])])
        self.assertEqual(doc['manipulation_checks']['withheld_health_only_runs'], 1)
        self.assertEqual(doc['manipulation_checks']['per_arm']['fixed_deep k1.0']['runs'], 2)


# ============================================================================================ injected failures

class InjectedFailures(Base):
    """One aggregation over a queue in which every job but one carries one injected failure: each failure shows up in
    its own row (and in the commit audit / R-3 / guard documents), and no other row is affected."""

    def test_each_failure_in_its_own_row(self):
        rl = rl_freeze(self.tmp / 'rl.json')
        jobs = {n: job_line(f'j_{n}', route=r) for n, r in (
            ('clean', '1792'), ('late', '2215'), ('stale', '2539'), ('cancel', '2715'), ('pin', '2943'),
            ('missing', '3184'), ('never', '14862'), ('unfinished', '17569'), ('bg', '1833'))}
        jobs['net'] = job_line('j_net', arm='fl_full', route='18305')
        jobs['test'] = job_line('j_test', route=TEST_ROUTE, training=False)
        runs = {'clean': make_run(self.root, jobs['clean']),
                'late': make_run(self.root, jobs['late'], commits=((1, 0, 0.5, 0.45, 0.6),)),        # t_commit >= D
                'stale': make_run(self.root, jobs['stale'], commits=((1, 5, 0.5, 3.0, 0.6), (2, 3, 1.1, 3.0, 1.2))),
                'cancel': make_run(self.root, jobs['cancel'], commits=((1, 0, 0.7, 3.0, 0.6),)),   # after the job end
                'pin': make_run(self.root, jobs['pin'], pins={'framelease_common.py': 'c' * 64}),
                'unfinished': make_run(self.root, jobs['unfinished'], finished=False),
                'bg': make_run(self.root, jobs['bg'], prefix_s=0.47),                       # background CPU load
                'net': make_run(self.root, jobs['net'], v4_extra={'utility': {'env_files_sha256': {
                    '/abs/q.json': '0' * 64}}}),                                            # a network not in the freeze
                'test': make_run(self.root, jobs['test'])}
        recs = []
        for n, job in jobs.items():
            if n == 'never':
                continue
            recs.append(start(job['id']))
            if n == 'missing':
                recs.append(end(job['id'], run=self.root / 'out' / 'gone'))      # final record, no run directory
            elif n != 'unfinished':
                recs.append(end(job['id'], run=runs[n]))
        rows, doc = self.run_agg(list(jobs.values()), recs, rl_freeze=rl, allow_dev_freeze=True)
        r = {k[2:]: v for k, v in by_job(rows).items()}
        want_reason = {'clean': None, 'late': None, 'stale': None, 'cancel': None, 'bg': None,
                       'pin': 'code_mismatch', 'missing': 'selection_error', 'never': 'not_launched',
                       'unfinished': 'pending', 'net': 'label_problem', 'test': 'health_only'}
        self.assertEqual({n: x['missing_reason'] for n, x in r.items()}, want_reason)
        self.assertEqual({n for n, x in r.items() if x['analysis_use']}, {'clean', 'late', 'stale', 'cancel', 'bg'})
        # R-2: each Eq. 9 violation alone, in its own run; the audit reports, it does not exclude (H5, Sec. 9.5)
        audit = {n: (x['commit_audit_status'], x['commit_audit_violations']) for n, x in r.items()}
        for n in ('clean', 'pin', 'bg', 'net'):
            self.assertEqual(audit[n], ('PASS', 0), n)
        for n in ('late', 'stale', 'cancel'):
            self.assertEqual(audit[n], ('FAIL', 1), n)
        self.assertEqual(audit['test'], (A.WITHHELD, None))           # Sec. 9.11: not audited before the freeze
        a = doc['commit_audit']
        self.assertEqual(a['status'], 'FAIL')
        self.assertEqual({k: v for k, v in a['violations'].items() if v},
                         {'deadline': 1, 'version': 1, 'cancelled': 1})
        by_run = {x['run_dir'].rsplit('/', 1)[1]: x for x in a['runs']}
        self.assertEqual(by_run['20261111T010101_j_late']['examples'][0]['violations'], ['deadline'])
        self.assertEqual(by_run['20261111T010101_j_stale']['examples'][0]['violations'], ['version'])
        self.assertEqual(by_run['20261111T010101_j_cancel']['examples'][0]['violations'], ['cancelled'])
        self.assertEqual(by_run['20261111T010101_j_unfinished']['status'], 'PASS')     # every attempt is audited
        self.assertEqual((a['runs_audited'], a['runs_withheld']), (8, 1))   # every job's run directory
        # code check, missing data, label
        self.assertIn('framelease_common.py', r['pin']['code_detail'])
        self.assertIn('gone', r['missing']['selection_note'])
        self.assertIsNone(r['unfinished']['selected_run'])
        self.assertEqual((r['net']['protocol_arm'], r['net']['code_check']), ('fl_full', CS.PASS))
        self.assertIn('not in the RL freeze', r['net']['label_problem'])
        self.assertEqual(doc['label_problems'], [{'job': 'j_net', 'problem': r['net']['label_problem']}])
        for n in ('missing', 'never', 'unfinished'):                   # no selected run: no audit columns
            self.assertIsNone(r[n]['commit_audit_status'])
        # R-3 background load: flagged and reported per run and per arm, never excluded
        self.assertEqual((r['bg']['bg_load_status'], r['bg']['charged_prefix_check'], r['bg']['analysis_use']),
                         ('above', 'PASS', True))
        self.assertAlmostEqual(r['bg']['bg_load_excess_s'], 0.47 - 0.426)               # kappa 1.0: upper edge 0.426
        self.assertEqual(r['clean']['bg_load_status'], 'within')
        m = doc['manipulation_checks']
        self.assertEqual(m['idle_prefix_band_s_per_kappa'], [0.416, 0.426])    # Sec. 9.7 pilot range at kappa 1.0
        self.assertIn('Sec. 9.7', m['idle_band_source'])
        self.assertEqual(m['per_arm']['fixed_deep k1.0']['bg_load'], {'within': 6, 'above': 1, 'below': 0})
        self.assertEqual([f['job'] for f in m['flags'] if f['check'] == 'bg_load_above'], ['j_bg'])
        # Sec. 9.11: the test-route row keeps health only
        self.assertEqual((r['test']['health_only'], r['test']['test_route'], r['test']['bg_load_status']),
                         (True, True, 'within'))
        self.assertTrue(r['test']['guard_note'].startswith('pre_freeze'))
        self.assertNotIn('driving_score', r['test'])
        self.assertEqual((doc['interim_guard']['status'], doc['interim_guard']['health_only_rows']), ('pre_freeze', 1))

    def test_unauditable_log_is_not_a_pass(self):
        job = job_line('j_bad')
        run = make_run(self.root, job)
        fl = run / 'raw' / 'agent' / 'framelease'
        bad = json.loads((fl / 'jobs.jsonl').read_text())
        del bad['steps'][0]['depth']                                   # a malformed commit record
        (fl / 'jobs.jsonl').write_text(json.dumps(bad) + '\n')
        rows, doc = self.run_agg([job], [start('j_bad'), end('j_bad', run=run)])
        r = rows[0]
        self.assertEqual((r['commit_audit_status'], doc['commit_audit']['status'],
                          doc['commit_audit']['runs_error']), ('ERROR', 'ERROR', 1))
        # the official record is valid: the route stays in the analysis, only the failed steps' columns are empty
        self.assertEqual((r['analysis_use'], r['missing_reason'], r['driving_score']), (True, None, 40.0))
        self.assertIn('run_checks: KeyError', r['extra_metrics_error'])
        self.assertEqual(set(r['metric_steps_failed'].split(',')), {'timing_metrics', 'run_checks'})
        for k in ('cancelled_gpu_share', 'prefix_quantum_s_p50', 'config_check', 'bg_load_status'):
            self.assertNotIn(k, r)
        self.assertEqual((r['dmr'], r['infractions_per_km']), (0.0, 0.0))       # the other steps are kept
        self.assertEqual({k: doc['metric_errors'][0][k] for k in ('job', 'analysis_use')},
                         {'job': 'j_bad', 'analysis_use': True})

    def test_metric_step_error_keeps_the_other_metrics(self):
        """A commit event without its depth breaks the lease-validity step only (Sec. 9.1, 9.8: the DS route stays)."""
        job = job_line('j_ev')
        run = make_run(self.root, job)
        ev = run / 'raw' / 'agent' / 'framelease' / 'events.jsonl'
        lines = [json.loads(x) for x in ev.read_text().splitlines()]
        for e in lines:
            if e.get('kind') == 'commit':
                e.pop('depth')
        ev.write_text(''.join(json.dumps(e) + '\n' for e in lines))
        rows, doc = self.run_agg([job], [start('j_ev'), end('j_ev', run=run)])
        r = rows[0]
        self.assertEqual((r['analysis_use'], r['missing_reason'], r['driving_score']), (True, None, 40.0))
        self.assertEqual(r['metric_steps_failed'], 'lease_validity_metrics')
        self.assertNotIn('lease_utilization', r)
        self.assertIsNotNone(r['prefix_quantum_s_p50'])
        self.assertEqual(doc['commit_audit']['status'], 'ERROR')         # the audit cannot read the commit either


# ============================================================================================ Sec. 9.11 guard

def dev_protocol(d, cited=(), outside=()):
    """A development copy of PROTOCOL.md whose Sec. 13 cites the given sha256 (outside: cited in Sec. 9 instead), and
    its seal."""
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    text = ('# protocol\n\n## 9. Statistical analysis plan\n' + ''.join(f'* {s}\n' for s in outside)
            + '\n## 13. Registration and amendments\n' + ''.join(f'* analysis freeze, `{s}`\n' for s in cited)
            + '\n## 14. TRIMMED plan\n')
    p = d / 'PROTOCOL.md'
    p.write_text(text)
    seal = d / 'SEAL.sha256'
    seal.write_text(f'{PJ.sha256_file(p)}  {p}\n')
    return p, seal


class Guard(Base):
    def final_queue(self, out_root=None, route=TEST_ROUTE):
        """One training-route and one test-route job (route: the registered test route, or EXTRA_ROUTE for a record
        cited by a development PROTOCOL.md copy, which never releases a registered one), both final (output
        directories under out_root if given)."""
        kw = {} if out_root is None else {'output_dir': str(Path(out_root) / 'out' / 'fixed_deep_k1.0')}
        jobs = [job_line('g_tr', **kw), job_line('g_te', route=route, training=False, **kw)]
        recs = []
        for j in jobs:
            recs += [start(j['id']), end(j['id'], run=make_run(self.root, j))]
        return jobs, recs

    def freeze(self, rows, doc, name='freeze.json', cite=True, edit=None, outside=(), **kw):
        """(record path, development PROTOCOL.md, seal) of an analysis-freeze record of this aggregation."""
        rec = G.freeze_record(rows, doc['job_files'], **kw)
        if edit:
            edit(rec)
        path = self.tmp / 'freeze' / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(rec))
        sha = PJ.sha256_file(path)
        protocol, seal = dev_protocol(self.tmp / f'proto_{name}', cited=[sha] if cite else [],
                                      outside=[sha] if outside else [])
        return path, protocol, seal

    def test_before_the_freeze(self):
        jobs, recs = self.final_queue()
        rows, doc = self.run_agg(jobs, recs)
        r = by_job(rows)
        self.assertEqual((r['g_tr']['guard_note'], r['g_tr']['health_only']), (None, False))
        self.assertEqual((r['g_te']['health_only'], r['g_te']['analysis_use']), (True, False))
        self.assertTrue(r['g_te']['guard_note'].startswith('pre_freeze'))
        g = doc['interim_guard']
        self.assertEqual((g['status'], g['guarded_rows'], g['released_rows'], g['notes']),
                         ('pre_freeze', 1, 0, {'pre_freeze': 1}))
        self.assertEqual(g['test_routes']['n_registered'], 44)
        s = A.arm_summary(rows, 'training')
        self.assertEqual([(x['protocol_arm'], x['split'], x['routes'], x['driving_score']) for x in s],
                         [('fixed_deep', 'training', 1, 40.0)])
        for split in ('test', 'all'):                          # a cross-arm test-route summary before the freeze
            with self.assertRaises(A.GuardRefused):
                A.arm_summary(rows, split)
        forged = [dict(r['g_te'], health_only=False, analysis_use=True, driving_score=40.0, valid_record=True)]
        for split in ('training', 'test'):                     # a row the guard did not release never enters
            with self.assertRaises(A.GuardRefused):
                G.summary_rows(forged, split, {'sha256': 'x'})
        rows2, _ = A.aggregate([self.queue], root=self.root, test_routes=set())   # cannot remove a test route
        self.assertTrue(by_job(rows2)['g_te']['health_only'])
        g = A.guard_fields(job_line('x'), {TEST_ROUTE}, None, TEST_ROUTE)     # a run that recorded a test route
        self.assertEqual((g['health_only'], g['test_route']), (True, True))
        self.assertIn('the run recorded the test route', g['guard_note'])
        run = ROOT / r['g_te']['selected_run'] if not Path(r['g_te']['selected_run']).is_absolute() \
            else Path(r['g_te']['selected_run'])
        with self.assertRaises(A.GuardRefused):                 # the per-run function itself fails closed
            A.run_fields(jobs[1], run, 'fixed_deep')
        self.assertNotIn('driving_score', A.run_fields(jobs[1], run, 'fixed_deep', health=True)[1])

    def test_cli_summary_requests_are_logged_and_refused(self):
        jobs, recs = self.final_queue(out_root=self.root)
        write_jobs(self.queue / 'jobs.d' / 'b01.jsonl', jobs)
        write_status(self.queue, recs)
        out = self.tmp / 'cli'
        base = ['--queue', str(self.queue), '--out', str(out)]
        for split in ('test', 'all'):
            self.assertEqual(A.main(base + ['--arm-summary', split]), 4)
            self.assertFalse((out / 'runs.csv').exists())
        rec = self.tmp / 'not_cited.json'
        rec.write_text(json.dumps({'schema': G.FREEZE_SCHEMA}))
        self.assertEqual(A.main(base + ['--analysis-freeze', str(rec)]), 4)    # not cited by the registered protocol
        self.assertEqual(A.main(base + ['--arm-summary', 'training']), 0)
        log = [json.loads(x) for x in (out / G.LOG_NAME).read_text().splitlines()]
        self.assertEqual([(e['decision'], e['arm_summary'], e['analysis_freeze'] is not None) for e in log],
                         [('refused', 'test', False), ('refused', 'all', False), ('refused', None, True),
                          ('granted', 'training', False)])
        self.assertTrue(all('Sec. 9.11' in e['reason'] for e in log[:2]))
        self.assertIn('not cited in Sec. 13', log[2]['reason'])
        agg = json.loads((out / 'aggregate.json').read_text())
        g = agg['interim_guard']
        self.assertEqual((g['status'], g['summary'], g['log']['entries'], g['log']['refused']),
                         ('pre_freeze', {'split': 'training', 'rows': 1}, 4, 3))
        with open(out / 'arm_summary.csv', newline='') as f:
            got = list(csv.DictReader(f))
        self.assertEqual([(x['protocol_arm'], x['split'], x['routes']) for x in got], [('fixed_deep', 'training', '1')])
        sums = {line.split('  ')[1] for line in (out / 'SHA256SUMS').read_text().splitlines()}
        self.assertEqual(sums, {'runs.csv', 'aggregate.json', 'arm_summary.csv'})
        self.assertEqual(A.main(base + ['--force']), 0)
        self.assertFalse((out / 'arm_summary.csv').exists())          # a stale summary never outlives its aggregate
        self.assertEqual(len((out / G.LOG_NAME).read_text().splitlines()), 5)   # the log is never replaced

    def test_summary_never_pools_seeds_phases_blocks_or_candidates(self):
        jobs = [job_line('s_ref'), job_line('s_smoke', phase='P1-0', block='smoke', route='2215'),
                job_line('s_seed12', seed=12), job_line('s_cand', candidate='fixed_deep_b', route='2539')]
        recs = []
        for j in jobs:
            recs += [start(j['id']), end(j['id'], run=make_run(self.root, j))]
        rows, _ = self.run_agg(jobs, recs)
        self.assertTrue(all(r['analysis_use'] for r in rows), [r['missing_reason'] for r in rows])
        got = [tuple(x[k] for k in A.SUMMARY_KEYS) + (x['routes'],) for x in A.arm_summary(rows, 'training')]
        self.assertEqual(sorted(got), sorted([('fixed_deep', 'fixed_deep', 1.0, 11, 'P1', 'ref', 'training', 1),
                                              ('fixed_deep', 'fixed_deep', 1.0, 11, 'P1-0', 'smoke', 'training', 1),
                                              ('fixed_deep', 'fixed_deep', 1.0, 12, 'P1', 'ref', 'training', 1),
                                              ('fixed_deep', 'fixed_deep_b', 1.0, 11, 'P1', 'ref', 'training', 1)]))

    def test_cli_required_job_files(self):
        jobs, recs = self.final_queue(out_root=self.root)
        write_jobs(self.queue / 'jobs.d' / 'b01.jsonl', jobs)
        write_status(self.queue, recs)
        out, bad = self.tmp / 'cli_req', self.tmp / 'required.json'
        bad.write_text('[1]')
        base = ['--queue', str(self.queue), '--out', str(out)]
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):                         # needs --analysis-freeze
                A.main(base + ['--required-job-files', str(bad)])
            self.assertEqual(A.main(base + ['--analysis-freeze', str(bad), '--required-job-files', str(bad)]), 4)
        log = [json.loads(x) for x in (out / G.LOG_NAME).read_text().splitlines()]
        self.assertEqual([(e['decision'], e['required_job_files']) for e in log], [('refused', str(bad))])
        self.assertIn('not a JSON object', log[0]['reason'])

    def test_valid_record_releases_the_covered_rows(self):
        jobs, recs = self.final_queue(route=EXTRA_ROUTE)
        rows, doc = self.run_agg(jobs, recs)
        self.assertEqual((by_job(rows)['g_te']['commit_audit_status'], doc['commit_audit']['status']),
                         (A.WITHHELD, 'INCOMPLETE'))
        path, protocol, seal = self.freeze(rows, doc)
        fz = G.load_freeze(path, protocol, seal)
        self.assertFalse(fz['registered'])
        rows2, doc2 = self.run_agg(jobs, recs, freeze=fz)
        r = by_job(rows2)['g_te']
        self.assertEqual((r['health_only'], r['analysis_use'], r['driving_score']), (False, True, 40.0))
        self.assertTrue(r['guard_note'].startswith('released') and 'DEVELOPMENT' in r['guard_note'])
        # the R-2 audit of the run is released together with its row
        self.assertEqual((r['commit_audit_status'], r['commit_audit_violations']), ('PASS', 0))
        self.assertEqual((doc2['commit_audit']['status'], doc2['commit_audit']['runs_withheld']), ('PASS', 0))
        g = doc2['interim_guard']
        self.assertEqual((g['status'], g['released_rows'], g['freeze']['sha256']),
                         ('frozen_development', 1, PJ.sha256_file(path)))
        for p in (path, protocol, seal):
            self.assertIn(PJ.rel(p), doc2['inputs'])
        self.assertEqual([x['split'] for x in A.arm_summary(rows2, 'test', fz)], ['test'])
        self.assertEqual(sorted(x['split'] for x in A.arm_summary(rows2, 'all', fz)), ['test', 'training'])
        self.assertEqual(doc2['manipulation_checks']['withheld_health_only_runs'], 0)
        self.assertTrue(any('WARNING' in x for x in A.summary_lines(doc2, self.tmp)))

    def test_development_record_never_releases_a_registered_test_route(self):
        jobs, recs = self.final_queue()                                       # g_te on the registered route 1711
        rows, doc = self.run_agg(jobs, recs)
        fz = G.load_freeze(*self.freeze(rows, doc))
        rows2, doc2 = self.run_agg(jobs, recs, freeze=fz)
        r = by_job(rows2)['g_te']
        self.assertEqual((r['health_only'], r['guard_note'], r['commit_audit_status']),
                         (True, G.DEV_WITHHELD, A.WITHHELD))
        self.assertNotIn('driving_score', r)
        self.assertEqual((doc2['interim_guard']['released_rows'], doc2['commit_audit']['runs_withheld']), (0, 1))
        for split in ('test', 'all'):
            with self.assertRaises(A.GuardRefused):
                A.arm_summary(rows2, split, fz)
        forged = [dict(r, health_only=False, analysis_use=True, guard_note='released: by hand', driving_score=1.0)]
        with self.assertRaisesRegex(A.GuardRefused, 'development'):     # summary_rows' own defence
            G.summary_rows(forged, 'test', fz)
        self.assertEqual([x['split'] for x in A.arm_summary(rows2, 'training', fz)], ['training'])

    def test_changes_after_the_freeze_are_withheld(self):
        jobs, recs = self.final_queue(route=EXTRA_ROUTE)
        rows, doc = self.run_agg(jobs, recs)
        fz = G.load_freeze(*self.freeze(rows, doc))
        rerun = make_run(self.root, jobs[1], name='20261112T010101_rerun')        # a later attempt of the test job
        _, d2 = self.run_agg(jobs, recs + [start('g_te', 2), end('g_te', 2, run=rerun)], freeze=fz)
        self.assertEqual(d2['interim_guard']['released_rows'], 0)
        self.assertIn('differs from the record', d2['interim_guard']['withheld'][0]['note'])
        more = jobs + [job_line('g_te2', route='1773', training=False)]           # the job file changed
        rows3, d3 = self.run_agg(more, recs, freeze=fz)
        notes = {r['job']: r['guard_note'] for r in rows3 if r['guard_note']}
        self.assertEqual(set(notes), {'g_te', 'g_te2'})
        self.assertTrue(all('changed since the freeze' in n for n in notes.values()))
        self.assertTrue(all(r['health_only'] for r in rows3 if r['guard_note']))

    def test_invalid_records_are_refused(self):
        jobs, recs = self.final_queue()
        rows, doc = self.run_agg(jobs, recs)
        code = 'framelease_v4/analysis/aggregate_v4.py'
        cases = {'not cited in Sec. 13': {'cite': False},
                 'cited outside Sec. 13': {'cite': False, 'outside': True},
                 'final outcome': {'edit': lambda r: r['jobs']['g_te'].update(outcome='pending')},
                 'analysis code differs': {'edit': lambda r: r['analysis_code'].update({code: '0' * 64})},
                 'without the amendment': {'edit': lambda r: r.update(trigger='cut')},
                 'route split sha256': {'edit': lambda r: r.update(route_split_sha256='0' * 64)},
                 'not an analysis-freeze record': {'edit': lambda r: r.update(schema='x')}}
        for i, (want, kw) in enumerate(cases.items()):
            with self.subTest(want):
                path, protocol, seal = self.freeze(rows, doc, name=f'f{i}.json', **kw)
                with self.assertRaises(A.GuardRefused) as cm:
                    G.load_freeze(path, protocol, seal)
                self.assertIn('cited' if 'cited' in want else want, str(cm.exception))
        path, protocol, seal = self.freeze(rows, doc, name='edited.json')
        with open(protocol, 'a') as f:
            f.write('edited after the seal\n')
        with self.assertRaisesRegex(A.GuardRefused, 'does not equal its seal'):
            G.load_freeze(path, protocol, seal)
        path, protocol, seal = self.freeze(rows, doc, name='good.json')
        fz = G.load_freeze(path, protocol, seal)
        for forged in ({**fz, 'sha256': '0' * 64}, {**fz, 'path': str(self.tmp / 'nowhere.json')},
                       {'sha256': fz['sha256'], 'registered': True}, 'frozen'):
            with self.assertRaises(A.GuardRefused):                    # a hand-made or stale record dictionary
                self.run_agg(jobs, recs, freeze=forged)
        path.write_text(path.read_text().replace('"ok"', '"agent_crashed"', 1))   # the record edited after citing
        with self.assertRaises(A.GuardRefused):
            self.run_agg(jobs, recs, freeze=fz)

    def test_freeze_record_waits_for_every_job(self):
        jobs = [job_line('w_tr'), job_line('w_open', route=TEST_ROUTE, training=False),
                job_line('w_never', route=EXTRA_ROUTE, training=False)]
        recs = [start('w_tr'), end('w_tr', run=make_run(self.root, jobs[0])), start('w_open')]
        rows, doc = self.run_agg(jobs, recs)
        for cut in (None, 'A9'):                                   # a running job is never cut
            with self.assertRaisesRegex(ValueError, 'w_open'):
                G.freeze_record(rows, doc['job_files'], cut)
        rows, doc = self.run_agg([jobs[0], jobs[2]], recs[:2])
        with self.assertRaisesRegex(ValueError, 'not final'):
            G.freeze_record(rows, doc['job_files'])
        path, protocol, seal = self.freeze(rows, doc, cut_amendment='A9')
        rec = json.loads(path.read_text())
        self.assertEqual((rec['trigger'], rec['cut_amendment'], rec['jobs']['w_never']['outcome']), ('cut', 'A9', 'cut'))
        rows2, _ = self.run_agg([jobs[0], jobs[2]], recs[:2], freeze=G.load_freeze(path, protocol, seal))
        self.assertEqual(by_job(rows2)['w_never']['missing_reason'], 'not_launched')   # released, still no data
        self.assertTrue(by_job(rows2)['w_never']['guard_note'].startswith(G.RELEASED))
        out = self.tmp / 'cli_rec'
        rows_jobs = [dict(j, output_dir=str(self.root / j['output_dir'])) for j in jobs]
        write_jobs(self.queue / 'jobs.d' / 'b01.jsonl', rows_jobs)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = A.main(['--queue', str(self.queue), '--out', str(out), '--write-freeze-record',
                           str(out / 'record.json')])
        self.assertEqual(code, 2)
        self.assertIn('not final', err.getvalue())
        self.assertFalse((out / 'record.json').exists() or (out / 'runs.csv').exists())
        log = [json.loads(x) for x in (out / G.LOG_NAME).read_text().splitlines()]
        self.assertEqual([(e['request'], e['decision']) for e in log],
                         [('aggregate', 'granted'), ('write_freeze_record', 'refused')])
        write_jobs(self.queue / 'jobs.d' / 'b01.jsonl', rows_jobs[:1])             # every job final: a record
        write_status(self.queue, recs[:2])
        out2, msg = self.tmp / 'cli_rec2', io.StringIO()
        args = ['--queue', str(self.queue), '--out', str(out2), '--write-freeze-record', str(out2 / 'record.json')]
        with contextlib.redirect_stdout(msg):
            self.assertEqual(A.main(args), 0)
        rec = json.loads((out2 / 'record.json').read_text())
        self.assertEqual((rec['trigger'], list(rec['jobs']), rec['jobs']['w_tr']['outcome']),
                         ('all_final', ['w_tr'], 'ok'))
        self.assertEqual(rec['analysis_code'], G.analysis_code())
        self.assertIn(PJ.sha256_file(out2 / 'record.json'), msg.getvalue())
        with self.assertRaisesRegex(A.GuardRefused, 'not cited'):              # valid only once entered in Sec. 13
            G.load_freeze(out2 / 'record.json')
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(A.main(args + ['--force']), 1)                     # a record is never replaced

    def test_route_split_must_be_the_registered_one(self):
        copy = self.tmp / 'route_split.json'
        copy.write_text(PJ.ROUTE_SPLIT.read_text())
        with self.assertRaisesRegex(A.GuardRefused, 'registration manifest'):
            G.registered_split(copy)
        self.assertEqual(len(G.registered_split()['test']), 44)


# ============================================================================================ outputs and CLI

class Outputs(Base):
    def test_outputs_hashes_and_refusals(self):
        job = job_line('j_o')
        run = make_run(self.root, job)
        rows, doc = self.run_agg([job], [start('j_o'), end('j_o', run=run)])
        out = self.tmp / 'agg'
        written = A.write_outputs(out, rows, doc)
        self.assertEqual(written['outputs']['runs.csv'], PJ.sha256_file(out / 'runs.csv'))
        sums = dict(reversed(line.split('  ')) for line in (out / 'SHA256SUMS').read_text().splitlines())
        self.assertEqual(sums, {n: PJ.sha256_file(out / n) for n in ('runs.csv', 'aggregate.json')})
        self.assertFalse((out / 'arm_summary.csv').exists())
        with open(out / 'runs.csv', newline='') as f:
            got = list(csv.DictReader(f))
        self.assertEqual(list(got[0])[:len(A.ID_COLUMNS)], list(A.ID_COLUMNS))
        agg = json.loads((out / 'aggregate.json').read_text())
        self.assertEqual(agg['stubs'], [])
        self.assertEqual((agg['interim_guard']['status'], agg['interim_guard']['freeze']), ('pre_freeze', None))
        self.assertIn('framelease_v4/analysis/interim_guard.py', agg['code_sha256'])
        for p in A.CODE_FILES:                                   # modules imported inside the row-making functions
            self.assertEqual(agg['code_sha256'][p], PJ.sha256_file(ROOT / p))
        self.assertIn(PJ.rel(PJ.ROUTE_SPLIT), agg['inputs'])
        self.assertEqual(agg['inputs'][PJ.rel(A.G.REG.MANIFEST)], PJ.sha256_file(A.G.REG.MANIFEST))
        self.assertEqual((agg['commit_audit']['status'], agg['commit_audit']['runs_audited']), ('PASS', 1))
        self.assertIn('fixed_deep k1.0', agg['manipulation_checks']['per_arm'])
        self.assertIn(PJ.rel(run / 'raw/agent/framelease/events.jsonl'), agg['inputs'])
        for k in ('xm', 'ca', 'mc'):
            mod = {'xm': 'extra_metrics', 'ca': 'commit_audit', 'mc': 'manipulation'}[k]
            self.assertIn(f'framelease_v4/analysis/{mod}.py', agg['code_sha256'])
        with self.assertRaises(FileExistsError):
            A.write_outputs(out, rows, doc)
        A.write_outputs(out, rows, doc, force=True)
        for bad in ('outputs/framelease_v4/queue_p1/agg', 'outputs/framelease_v4/tuning/x', 'framelease_v4/analysis',
                    'outputs/framelease_v4/amendment_a2/x', 'outputs/framelease_v4'):
            with self.assertRaises(PermissionError):
                A.check_out_dir(ROOT / bad)
        A.check_out_dir(ROOT / 'outputs/framelease_v4/build/AGG/x')

    def test_cli_exit_codes(self):
        out = self.tmp / 'cli'
        self.assertEqual(A.main(['--queue', str(self.tmp / 'missing'), '--out', str(out)]), 2)
        self.assertEqual(A.main(['--queue', str(self.queue), '--out', str(ROOT / 'outputs/framelease_v4/p1_driver')]),
                         1)
        out.mkdir(exist_ok=True)                                 # the guard log of the first request made it
        (out / 'runs.csv').write_text('x')
        self.assertEqual(A.main(['--queue', str(self.queue), '--out', str(out)]), 1)
        log = [json.loads(x) for x in (out / 'interim_guard.jsonl').read_text().splitlines()]
        self.assertEqual([e['decision'] for e in log], ['granted', 'refused'])
        self.assertFalse((ROOT / 'outputs/framelease_v4/p1_driver/interim_guard.jsonl').exists())


if __name__ == '__main__':
    unittest.main()
