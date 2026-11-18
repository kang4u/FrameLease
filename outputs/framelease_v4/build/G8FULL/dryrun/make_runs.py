#!/usr/bin/env python3
"""SYNTHETIC queues and run directories of the G8FULL dry run, inside the scratch tree /tmp/G8FULL/root only (built by
build_tree.py). No project run directory is read: the job lines come from the registered job files (job files, not
results), the kept / cut split and the run-directory names of the first freeze from the tree's copy of its record (job
status only), and every run directory, runner record and log is generated here. Adapted from
outputs/framelease_v4/build/G8CUT/dryrun/make_runs.py (its run and log generators, unchanged there).

  cd /tmp/G8FULL/root
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' \
      taskset -c 12-15 nice -n 19 ionice -c 3 /home/kang/Desktop/DAC/.conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/G8FULL/dryrun/make_runs.py --stage cut|a17_pending|a17_final
  (the script lives in the project; it refuses any root but /tmp/G8FULL/root)

Stages (the timeline of the project, Amendments A12, A13, A17):
  cut          queue_p4 as after the swap of the first freeze: jobs.d = byte copies of the six registered job files
               (G6 sha256), queue_p4/STOP present; one synthetic run for each of the 127 jobs that the first record
               holds as final, in the run directory that record names (126 ok; v4p4_fl_original_k1.0_s11_r23658 with two
               'timeout' attempts, the second in the recorded directory); runner start 2026-11-15T15:30:10Z, exit
               2026-11-16T01:12:24Z; the 505 cut lines have no record. queue_p1 (P1-0 and P1, with the interrupted
               log-less attempt of v4p1_fixed_deep_k1.0_s11_r28093) and queue_p2 as in the G8CUT dry run.
  a17_pending  the relaunch of Amendment A17: queue_p4/STOP moved aside (STOP.<stamp>.a17_resume.resolved.txt), runner
               start 2026-11-16T07:54:23Z, the 505 cut lines in the registered order; after 169 of them the pause of
               2026-11-17 (the next job interrupted, not counted, its run directory with logs and no result; runner exit
               by signal), runner start 2026-11-17T07:06:29Z; one more job ('timeout' twice) ends as sim_failure; the
               last 3 lines stay open (the first of them started, no end), no runner exit.
  a17_final    the 3 open lines end ok and the runner exits ('queue empty').
Synthetic values: DS, RC and infractions are deterministic pseudo-random functions of (arm, route, kappa, seed); in
about 12% of the runs (a deterministic choice of route, arm, kappa and seed) the scenario vehicle stands 665 m ahead,
so that no committed plan is a conflict plan and the closed-loop R_cond is undefined (0/0).
"""
import argparse
import hashlib
import importlib.util
import json
import random
import shutil
import sys
from pathlib import Path

SRC = Path('/home/kang/Desktop/DAC')
ROOT = Path('/tmp/G8FULL/root')
V4 = ROOT / 'outputs/framelease_v4'
TESTS = ROOT / 'framelease_v4/analysis/tests'
FIRST_RECORD = V4 / 'analysis/final_20261116T091445/analysis_freeze.json'
if Path.cwd().resolve() != ROOT:
    sys.exit(f'run from {ROOT}')
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TESTS))
sys.dont_write_bytecode = True


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TVI = load('tvi', TESTS / 'test_verify_independent.py')
T7X = load('t7x', TESTS / 'test_verify_table1_extra.py')
TAG = load('tag', TESTS / 'test_aggregate_v4.py')
from framelease_v2 import gpu_queue as Q  # noqa: E402
from framelease_v4.protocol import check_smoke as CS  # noqa: E402

KIND = {'fixed_deep': 'v2_rule', 'fast_only': 'v2_rule', 'fl_original': 'v2_rule', 'event_triggered': 'event',
        'age_only': 'age'}
BASE_DS = {'fixed_deep': 46, 'fast_only': 72, 'age_only': 63, 'event_triggered': 61, 'fl_original': 55,
           'fl_heuristic': 65, 'fl_full': 69, 'fl_global_shield': 60, 'fl_bandit': 64, 'fl_fqi_nolease': 62,
           'fl_risk': 58, 'fl_behaviour': 60}
DT = 0.05
N_TICKS = 60
LEASE_H = {'age': 1.0, 'shield': 1.2, 'v2_rule': 2.0}
MAX_AGE = 3.0
TIMEOUT_JOB = 'v4p4_fl_original_k1.0_s11_r23658'
NO_LOG_JOB = 'v4p1_fixed_deep_k1.0_s11_r28093'
NO_CONFLICT_SHARE = 0.12
PAUSE_AFTER = 169           # new jobs final at the pause of 2026-11-17 10:37 (296 final = 127 + 169)
TIMEOUT_NEW = 300           # index of the new job that times out twice
OPEN = 3                    # new jobs still open in stage a17_pending
STAMP = {'cut': '20261115', 'a17_pending': '20261116', 'a17_final': '20261119'}


def rnd(*key):
    return random.Random(int(hashlib.sha256(json.dumps(key).encode()).hexdigest()[:12], 16))


def no_conflict(job):
    arm = job.get('protocol_arm') or job['arm_name']
    return rnd('noconf', job['route_id'], arm, job['kappa'], job['seed']).random() < NO_CONFLICT_SHARE


def outcome_values(job):
    arm = job.get('protocol_arm') or job['arm_name']
    r = rnd(arm, job['route_id'], job['kappa'], job['seed'], job.get('candidate'))
    route_eff = rnd('route', job['route_id']).uniform(-15, 15)
    ds = BASE_DS.get(arm, 60) + route_eff - 6 * (float(job['kappa']) - 1.0) + r.uniform(-12, 12)
    ds = round(min(100.0, max(0.0, ds)), 6)
    pen = r.uniform(0.55, 1.0)
    rc = round(min(100.0, ds / pen), 6) if pen else 100.0
    pen = ds / rc if rc else 1.0
    inf = {}
    if r.random() < 0.4:
        inf['collisions_vehicle'] = ['Agent collided against object with type=vehicle.tesla.model3'] * r.randint(1, 2)
    if r.random() < 0.2:
        inf['red_light'] = ['Agent ran a red light']
    if r.random() < 0.15:
        inf['min_speed_infractions'] = ['Average speed 40% of the surrounding traffic']
    status = 'Completed' if rc >= 99.999 else 'Failed - Agent got blocked'
    if status != 'Completed':
        inf['vehicle_blocked'] = ['Agent got blocked']
    return ds, rc, pen, inf, status, 300.0 + 200.0 * rnd('len', job['route_id']).random()


def logs(job, run_dir):
    """ticks / jobs / events / decisions / actors of one run (the VT helpers' shapes plus the R-2 fields)."""
    launcher = job['arm_name']
    kind = KIND.get(launcher, 'shield')
    k = float(job['kappa'])
    p, s = 0.42 * k, 0.0146 * k
    h = LEASE_H.get(kind, 1.2)
    src = 'global_lease' if launcher == 'fl_global_shield' else ('suffix_lease' if kind == 'shield' else
                                                                 'age_lease' if kind == 'age' else 'v2_rule')
    c1 = 0.05
    commit_a = round(c1 + p + 2 * s + 0.005, 6)
    c2 = round(commit_a + 0.4, 6)
    commit_b = round(c2 + p + s + 0.005, 6)
    if kind in ('v2_rule', 'event') and launcher != 'fl_original':
        dl_a, dl_b = c1 + MAX_AGE, c2 + MAX_AGE
    else:
        dl_a, dl_b = round(c1 + max(h, commit_a - c1 + 0.2), 6), round(c2 + max(h, commit_b - c2 + 0.2), 6)
    commits = [{'job_id': 1, 'obs_id': 1, 'depth': 2, 'commit_s': commit_a, 'capture_s': c1, 'deadline_s': dl_a},
               {'job_id': 2, 'obs_id': 2, 'depth': 1, 'commit_s': commit_b, 'capture_s': c2, 'deadline_s': dl_b}]
    fl = Path(run_dir) / 'raw' / 'agent' / 'framelease'
    fl.mkdir(parents=True, exist_ok=True)
    ticks = []
    for i in range(1, N_TICKS + 1):
        t = round(i * DT, 6)
        inc = None
        for c in commits:
            if c['commit_s'] <= t + 1e-9:
                inc = c
        if inc is None:
            ok = False
        elif launcher in T7X.VT.AGE_RULE_ARMS:
            ok = t - inc['capture_s'] < MAX_AGE
        else:
            ok = t < inc['deadline_s']
        ticks.append({'tick': i - 1, 'sim_s': t, 'mode': 'track' if ok else 'fallback',
                      'fallback_reason': None if ok else ('no_plan' if inc is None else 'expired'),
                      'incumbent': dict(inc) if inc else None, 'control': {'brake': 0.0 if ok else 1.0},
                      'action_age_s': (t - inc['capture_s']) if inc else None, 'gpu': None})
    T7X.write_jsonl(fl / 'ticks.jsonl', ticks)
    validity = (lambda dl, cap: {'source': src, 'deadline_s': dl, 'lease_s': round(dl - cap, 6), 'n_relevant': 0,
                                 'reason': 'no_relevant_agents', 'n_computed': 0})
    rows, events = [], []
    for jid, cap, depth_c, commit, dl, n_steps in ((1, c1, 2, commits[0], dl_a, 2), (2, c2, 1, commits[1], dl_b, 1)):
        steps = []
        for d in range(1, n_steps + 1):
            launch = round(cap + p + (d - 1) * s, 6)
            st = {'depth': d, 'launch_s': launch, 'release_s': round(launch + s, 6), 'timeline_cost_s': s,
                  'decision': {'overhead_s': 0.001}, 'plan': T7X.PLANS.get((jid, d)), 'validity': validity(dl, cap)}
            if d == depth_c:
                st['commit'] = {'accepted': True, 'reason': 'accepted', 'commit_s': commit['commit_s'],
                                'margin_at_commit_m': None, 'overridden': False}
            steps.append(st)
        end_s = round(commit['commit_s'] + 0.001, 6)
        rows.append({'job_id': jid, 'obs_id': jid, 'capture_s': cap, 'start_s': cap, 'end_s': end_s,
                     'prefix': {'launch_s': cap, 'timeline_cost_s': p, 'decision': {'overhead_s': 0.001}},
                     'prefix_end_s': round(cap + p, 6), 'committed_depths': [depth_c], 'final_depth': n_steps,
                     'steps': steps})
        events.append({'kind': 'job_start', 'job_id': jid, 'sim_s': cap, 'overhead_s': 0.0,
                       'prefix_end_s': round(cap + p, 6), 'prefix_timeline_s': p, 'prefix_cost_s': 0.42})
        events.append({'kind': 'commit', 'job_id': jid, 'obs_id': jid, 'depth': depth_c, 'capture_s': cap,
                       'release_s': round(cap + p + depth_c * s, 6), 'commit_s': commit['commit_s'], 'deadline_s': dl,
                       'lease_s': round(dl - cap, 6), 'margin_at_commit_m': None, 'would_reject': None})
        events.append({'kind': 'job_end', 'job_id': jid, 'sim_s': end_s})
    T7X.write_jsonl(fl / 'jobs.jsonl', rows)
    T7X.write_jsonl(fl / 'events.jsonl', events)
    decisions = []
    if kind in ('shield', 'age'):
        for d in T7X.DECISIONS:
            if d.get('depth') == 0:         # the runtime logs no shield epoch at depth 0 (Sec. 5.1 decision epochs)
                continue
            decisions.append(dict(d, action='REFINE' if d.get('depth') else 'REFRESH',
                                  admitted=bool(d.get('feasible'))))
    T7X.write_jsonl(fl / 'decisions.jsonl', decisions)
    (fl / 'summary.json').write_text('{}')
    (fl / 'fast_prefix.json').write_text(json.dumps(
        {'stage': 'final', 'fast_prefix': {'validation': {'ok': True}, 'active': {o: True for o in
                                                                                    CS.FAST_PREFIX_OPTIONS},
                                           'stats': {'sdpa': {'sdpa_calls': 120}}}}))
    actors = ((7, 66500, 0, 0),) if no_conflict(job) else ((7, 665, 0, 0),)
    T7X.write_actor_log(fl, [T7X.actor_row(i, i * DT, actors=actors) for i in range(1, N_TICKS + 1)])


def config(job):
    launcher = job['arm_name']
    kind = KIND.get(launcher, 'shield')
    v4 = {'arm': launcher, 'kind': kind, 'agent': {'policy_params': dict(job.get('policy_params') or {})}}
    if launcher == 'fl_full':
        net = job.get('network') or {}
        v4['utility'] = {'name': (job.get('policy_params') or {}).get('utility'),
                         'env_files_sha256': {'FRAMELEASE_V4_QNET': net.get('sha256')}}
    if launcher == 'fl_global_shield':
        v4['extension'] = {'global_lease': {'design': 'GLOBAL', 'T_c_s': 0.5, 'd_safe_m': 0.5, 'delta_m': 0.2}}
    return {'v4_arm': launcher, 'kind': kind, 'kappa': job['kappa'], 'seed': job['seed'],
            'route': {'route_id': str(job['route_id']), 'town': job.get('town'),
                      'scenarios': [job['scenario_type']] if job.get('scenario_type') else []},
            'v4': v4, 'envelope_sha256': (job.get('envelope') or {}).get('sha256'),
            'fast_prefix': {'options': list(CS.FAST_PREFIX_OPTIONS)},
            'agent_config': {'runtime': {'max_age_s': MAX_AGE, 'fallback_brake': 1.0, 'kappa': job['kappa']}}}


class Gen:
    def __init__(self, stage):
        self.world = TVI.World(Path('/tmp/G8FULL/world_scratch'))
        self.n = 0
        self.date = STAMP[stage]

    def run(self, job, finished=True, with_logs=True, name=None):
        line = dict(job, output_dir=str(ROOT / job['output_dir']))
        ds, rc, pen, inf, status, length = outcome_values(job)
        rec = dict(job['require_sha256'])
        run_dir = self.world.run(line, ds=ds, rc=rc, status=status, infractions=inf, length=length, recorded=rec)
        self.n += 1
        tag = hashlib.sha256(job['id'].encode()).hexdigest()[:8]
        new = run_dir.parent / (name or f'{self.date}T{self.n:06d}_{tag}')
        if new.exists():
            sys.exit(f'{new} exists')
        run_dir.rename(new)
        run_dir = new
        (run_dir / 'config.json').write_text(json.dumps(config(job)))
        (run_dir / 'manifest.json').write_text(json.dumps(
            {'status': 'COMPLETED' if finished else 'RUNNING', 'created': '2026-11-16T00:00:00Z',
             'identity': {'code': {str(ROOT / k): v for k, v in job['require_sha256'].items()}}}))
        res = json.loads((run_dir / 'metrics/result.json').read_text())
        res.update(infractions=inf, meta={'route_length': length, 'duration_game': 60.0, 'duration_system': 320.0},
                   wall_s=320.0)
        res['scores']['score_penalty'] = pen
        (run_dir / 'metrics/result.json').write_text(json.dumps(res))
        if not finished:
            (run_dir / 'metrics/result.json').unlink()
            (run_dir / 'raw/official_results.json').unlink()
        if with_logs:
            logs(job, run_dir)
            fl = run_dir / 'raw/agent/framelease'
            if finished:
                exp = T7X.VT.recompute_run(str(run_dir))
                summ = T7X.summary_from(exp)
                summ.update(gpu_busy_ratio=exp['gpu_usage'], gpu_busy_in_span_s=exp['gpu_busy_s'],
                            action_age_s=summ['v4']['action_age_s'],
                            actor_log={'ticks_logged': exp['ticks'], 'errors': 0})
                (fl / 'summary.json').write_text(json.dumps(summ))
                res = json.loads((run_dir / 'metrics/result.json').read_text())
                res['agent_summary'] = summ
                (run_dir / 'metrics/result.json').write_text(json.dumps(res))
            else:
                (fl / 'summary.json').unlink()
        return run_dir


def end_record(jid, attempt, outcome, run_dir, final, counted=True):
    r = TAG.end(jid, attempt=attempt, outcome=outcome, run=run_dir, final=final)
    r.update(counted=counted, result=Q.Runner.closed_loop_result(run_dir) if run_dir else None, wall_s=320.0,
             kind='closed_loop')
    return r


def read_jobs(files):
    jobs = []
    for f in files:
        jobs += [json.loads(ln) for ln in Path(f).read_text().splitlines() if ln.strip()]
    return jobs


def write_simple_queue(qdir, job_files, gen, special=None):
    """P1 / P2 queues: jobs.d = byte copies of job_files; one run per line; runner start / exit."""
    if qdir.exists():
        shutil.rmtree(qdir)
    (qdir / 'jobs.d').mkdir(parents=True)
    for f in job_files:
        shutil.copy2(f, qdir / 'jobs.d' / Path(f).name)
    recs = [{'event': 'runner_start', 'utc': '2026-11-14T00:00:00Z', 'pid': 1}]
    jobs = read_jobs(job_files)
    for job in jobs:
        jid = job['id']
        if special and jid in special:
            recs += special[jid](job, gen)
            continue
        run = gen.run(job)
        recs += [TAG.start(jid), end_record(jid, 1, 'ok', run, True)]
    recs.append({'event': 'runner_exit', 'utc': '2026-11-15T06:30:00Z', 'pid': 1, 'reason': 'queue empty',
                 'exit_code': 0})
    TAG.write_status(qdir, recs)
    return jobs


def interrupted_then_ok(job, gen):
    gen.run(job, finished=False, with_logs=False)                 # no jobs.jsonl / events.jsonl: NO_LOG
    run2 = gen.run(job)
    return [TAG.start(job['id'], attempt=1),
            {'event': 'end', 'id': job['id'], 'attempt': 1, 'outcome': 'interrupted', 'counted': False, 'final': False,
             'run_dir': None, 'note': 'runner stopped during this attempt'},
            TAG.start(job['id'], attempt=2), end_record(job['id'], 2, 'ok', run2, True)]


def timeout_twice(job, gen, last_name=None):
    out = []
    for att in (1, 2):
        run = gen.run(job, finished=False, name=last_name if att == 2 else None)
        out += [TAG.start(job['id'], attempt=att), end_record(job['id'], att, 'timeout', run, att == 2)]
    return out


def stage_cut(gen):
    for d in ('matrix', 'fig3', 'ablation', 'replicates', 'smoke_p1_0'):
        p = V4 / d
        if p.is_symlink():
            sys.exit(f'{p} is a link')
        shutil.rmtree(p, ignore_errors=True)
    for p in (V4 / 'tuning').iterdir():
        if p.is_dir() and p.name not in ('selection', 'd1'):
            shutil.rmtree(p)
    for p in (V4 / 'rl_data').iterdir():
        if p.is_dir():
            shutil.rmtree(p)
    rec = json.loads(FIRST_RECORD.read_text())
    q4 = V4 / 'queue_p4'
    if q4.exists():
        shutil.rmtree(q4)
    (q4 / 'jobs.d').mkdir(parents=True)
    copies = sorted(rec['job_files'])
    for c in copies:                      # the registered copies (cut_*/jobs_registered = test_jobs/FULL, G6 sha256)
        src = V4 / 'cut_20261115T231415/jobs_registered' / Path(c).name
        shutil.copy2(src, ROOT / c)
        if hashlib.sha256((ROOT / c).read_bytes()).hexdigest() != rec['job_files'][c]:
            sys.exit(f'{c}: not at the sha256 of the first record')
    jobs = read_jobs(ROOT / c for c in copies)
    recs = [{'event': 'runner_start', 'utc': '2026-11-15T15:30:10Z', 'pid': 665278}]
    kept = 0
    for job in jobs:
        r = rec['jobs'][job['id']]
        if r['outcome'] == 'cut':
            continue
        want = Path(r['run_dir'])
        if str(want.parent) != f'{job["output_dir"]}/runs':
            sys.exit(f'{job["id"]}: recorded run {want} is not under {job["output_dir"]}/runs')
        kept += 1
        if job['id'] == TIMEOUT_JOB:
            recs += timeout_twice(job, gen, last_name=want.name)
            continue
        run = gen.run(job, name=want.name)
        recs += [TAG.start(job['id']), end_record(job['id'], 1, 'ok', run, True)]
    recs.append({'event': 'runner_exit', 'utc': '2026-11-16T01:12:24Z', 'pid': 665278, 'reason': 'queue empty',
                 'exit_code': 0})
    TAG.write_status(q4, recs)
    (q4 / 'STOP').write_text('2026-11-16T09:14:29+0800 G8 under Amendment A12: the registered job files are back in '
                             'jobs.d for the analysis-freeze record; their 505 cut lines never start. Do not remove.\n')
    p1 = write_simple_queue(V4 / 'queue_p1', sorted((SRC / 'outputs/framelease_v4/queue_p1/jobs.d').glob('*.jsonl')),
                            gen, {NO_LOG_JOB: interrupted_then_ok})
    p2 = write_simple_queue(V4 / 'queue_p2', sorted((SRC / 'outputs/framelease_v4/queue_p2/jobs.d').glob('*.jsonl')),
                            gen)
    print(f'stage cut: queue_p4 {len(jobs)} lines, {kept} final as the first record holds, '
          f'{len(jobs) - kept} cut lines without a record; STOP present; queue_p1 {len(p1)}, queue_p2 {len(p2)}; '
          f'{gen.n} run directories')


def new_jobs():
    rec = json.loads(FIRST_RECORD.read_text())
    jobs = read_jobs(ROOT / c for c in sorted(rec['job_files']))
    return [j for j in jobs if rec['jobs'][j['id']]['outcome'] == 'cut']


def stage_a17_pending(gen):
    q4 = V4 / 'queue_p4'
    recs = [json.loads(ln) for ln in (q4 / 'status.jsonl').read_text().splitlines() if ln.strip()]
    if sum(r.get('event') == 'runner_start' for r in recs) != 1:
        sys.exit('stage a17_pending needs the queue of stage cut')
    (q4 / 'STOP').rename(q4 / 'STOP.20261116T155423.a17_resume.resolved.txt')
    new = new_jobs()
    recs.append({'event': 'runner_start', 'utc': '2026-11-16T07:54:23Z', 'pid': 15838})
    n_final = len(new) - OPEN
    for i, job in enumerate(new[:n_final]):
        jid = job['id']
        if i == PAUSE_AFTER:
            run = gen.run(job, finished=False)
            recs += [TAG.start(jid, attempt=1),
                     {'event': 'end', 'id': jid, 'attempt': 1, 'outcome': 'interrupted', 'counted': False,
                      'final': False, 'run_dir': str(run), 'note': 'runner stopped by SIGTERM during this attempt'},
                     {'event': 'runner_exit', 'utc': '2026-11-17T02:37:10Z', 'pid': 15838, 'reason': 'signal 15',
                      'exit_code': 143},
                     {'event': 'runner_start', 'utc': '2026-11-17T07:06:29Z', 'pid': 14451}]
            run2 = gen.run(job)
            recs += [TAG.start(jid, attempt=2), end_record(jid, 2, 'ok', run2, True)]
            continue
        if i == TIMEOUT_NEW:
            recs += timeout_twice(job, gen)
            continue
        run = gen.run(job)
        recs += [TAG.start(jid), end_record(jid, 1, 'ok', run, True)]
    recs.append(TAG.start(new[n_final]['id'], attempt=1))      # running now: no end record, no runner exit
    TAG.write_status(q4, recs)
    print(f'stage a17_pending: {n_final} of {len(new)} new jobs final (pause after {PAUSE_AFTER}: one attempt '
          f'interrupted; {new[TIMEOUT_NEW]["id"]} timed out twice); {OPEN} open, the first started; {gen.n} run '
          'directories')


def stage_a17_final(gen):
    q4 = V4 / 'queue_p4'
    recs = [json.loads(ln) for ln in (q4 / 'status.jsonl').read_text().splitlines() if ln.strip()]
    new = new_jobs()
    open_ = new[len(new) - OPEN:]
    if recs[-1] != TAG.start(open_[0]['id'], attempt=1):
        sys.exit('stage a17_final needs the queue of stage a17_pending')
    for i, job in enumerate(open_):
        run = gen.run(job)
        recs += ([] if i == 0 else [TAG.start(job['id'])]) + [end_record(job['id'], 1, 'ok', run, True)]
    recs.append({'event': 'runner_exit', 'utc': '2026-11-19T01:55:00Z', 'pid': 14451, 'reason': 'queue empty',
                 'exit_code': 0})
    TAG.write_status(q4, recs)
    print(f'stage a17_final: the {OPEN} open jobs ended ok; runner exit; {gen.n} run directories')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', choices=tuple(STAMP), required=True)
    a = ap.parse_args()
    shutil.rmtree('/tmp/G8FULL/world_scratch', ignore_errors=True)
    gen = Gen(a.stage)
    {'cut': stage_cut, 'a17_pending': stage_a17_pending, 'a17_final': stage_a17_final}[a.stage](gen)
    shutil.rmtree('/tmp/G8FULL/world_scratch', ignore_errors=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
