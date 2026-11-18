#!/usr/bin/env python3
"""SYNTHETIC queues and run directories of the G8CUT dry run, inside the scratch tree /tmp/G8CUT/root only (built by
build_tree.py). No project run directory is read: the job lines come from the registered job files (job files, not
results) and every run directory, runner record and log is generated here.

  cd /tmp/G8CUT/root
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' \
      taskset -c 12-15 nice -n 19 ionice -c 3 /home/kang/Desktop/DAC/.conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/G8CUT/dryrun/make_runs.py --stage pending|final [--no-log-attempt]
  (the script lives in the project; it refuses any root but /tmp/G8CUT/root)

Builds with the existing test helpers of the tree's framelease_v4/analysis/tests:
  * test_verify_independent.World.run: the official leaderboard record (raw/official_results.json), metrics/result.json,
    raw/source_v4/hashes.json (the job's pins) and the run directory layout;
  * test_verify_table1_extra: write_jsonl, actor_row, write_actor_log, PLANS and the decision rows (the realized-validity
    actor log and the runtime logs), extended here so that the commit audit (R-2) and the realized validity both read
    them: every accepted commit is a steps[].commit of jobs.jsonl and a 'commit' event, with its validity record;
  * test_aggregate_v4.start / end: the runner's start / end records (completed here with gpu_queue's
    closed_loop_result of the run directory).
Queues:
  queue_p4  jobs.d = the A12 reduced job files (byte copies of cut_20261115T231415/jobs_reduced/); one synthetic run per
            kept job (127); job v4p4_fl_original_k1.0_s11_r23658 has two 'timeout' attempts without a result (as A12
            records); --stage pending leaves the last 3 kept jobs without a final record (one of them running);
  queue_p1  jobs.d = byte copies of the project's queue_p1/jobs.d (P1-0 smoke and the nine P1 blocks), one run each;
            --no-log-attempt adds, for v4p1_fixed_deep_k1.0_s11_r28093, an interrupted first attempt whose run
            directory holds no jobs.jsonl / events.jsonl (as the 2026-11-11 pause left one);
  queue_p2  jobs.d = byte copy of the project's queue_p2/jobs.d (P2, 132 lines), one run each.
DS, RC and infractions are deterministic pseudo-random functions of (arm, route, kappa, seed).
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
ROOT = Path('/tmp/G8CUT/root')
V4 = ROOT / 'outputs/framelease_v4'
TESTS = ROOT / 'framelease_v4/analysis/tests'
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


def rnd(*key):
    return random.Random(int(hashlib.sha256(json.dumps(key).encode()).hexdigest()[:12], 16))


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


def logs(job, run_dir, inflight=False):
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
    T7X.write_actor_log(fl, [T7X.actor_row(i, i * DT) for i in range(1, N_TICKS + 1)])


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
    def __init__(self):
        self.world = TVI.World(Path('/tmp/G8CUT/world_scratch'))
        self.n = 0

    def run(self, job, finished=True, with_logs=True):
        line = dict(job, output_dir=str(ROOT / job['output_dir']))
        ds, rc, pen, inf, status, length = outcome_values(job)
        rec = dict(job['require_sha256'])
        run_dir = self.world.run(line, ds=ds, rc=rc, status=status, infractions=inf, length=length, recorded=rec)
        self.n += 1
        new = run_dir.parent / f'20261116T{self.n:06d}_{hashlib.sha256(job["id"].encode()).hexdigest()[:8]}'
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
                # the runtime summary, consistent with the logs: the values of the test helper summary_from on the
                # recomputation of the logs, plus the keys metrics_v4 and the runner read
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


def write_queue(qdir, job_files, gen, special=None, pending=0):
    """jobs.d = byte copies of job_files; one run per line; status.jsonl with runner_start, start / end records,
    runner_exit (unless jobs stay pending)."""
    if qdir.exists():
        shutil.rmtree(qdir)
    (qdir / 'jobs.d').mkdir(parents=True)
    jobs = []
    for f in job_files:
        shutil.copy2(f, qdir / 'jobs.d' / Path(f).name)
        jobs += [json.loads(ln) for ln in Path(f).read_text().splitlines() if ln.strip()]
    recs = [{'event': 'runner_start', 'utc': '2026-11-16T00:00:00Z', 'pid': 1}]
    n_final = len(jobs) - pending
    for i, job in enumerate(jobs):
        jid = job['id']
        if special and jid in special:
            recs += special[jid](job, gen)
            continue
        if i >= n_final:
            if i == len(jobs) - 1:
                recs.append(TAG.start(jid, attempt=1))        # running now: no end record
            continue
        run = gen.run(job)
        recs += [TAG.start(jid), end_record(jid, 1, 'ok', run, True)]
    if not pending:
        recs.append({'event': 'runner_exit', 'utc': '2026-11-16T07:30:00Z', 'pid': 1, 'reason': 'queue empty',
                     'exit_code': 0})
    TAG.write_status(qdir, recs)
    return jobs


def timeout_twice(job, gen):
    out = []
    for att in (1, 2):
        run = gen.run(job, finished=False)
        out += [TAG.start(job['id'], attempt=att), end_record(job['id'], att, 'timeout', run, att == 2)]
    return out


def interrupted_then_ok(job, gen):
    gen.run(job, finished=False, with_logs=False)                 # no jobs.jsonl / events.jsonl: NO_LOG
    run2 = gen.run(job)
    return [TAG.start(job['id'], attempt=1),
            {'event': 'end', 'id': job['id'], 'attempt': 1, 'outcome': 'interrupted', 'counted': False, 'final': False,
             'run_dir': None, 'note': 'runner stopped during this attempt'},
            TAG.start(job['id'], attempt=2), end_record(job['id'], 2, 'ok', run2, True)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', choices=('pending', 'final'), required=True)
    ap.add_argument('--no-log-attempt', action='store_true')
    a = ap.parse_args()
    for d in ('matrix', 'fig3', 'ablation', 'replicates', 'smoke_p1_0', 'tuning/ref', 'rl_data/k1.0'):
        p = V4 / d
        if p.is_symlink():
            sys.exit(f'{p} is a link')
    for d in ('matrix', 'fig3', 'ablation', 'replicates', 'smoke_p1_0'):
        shutil.rmtree(V4 / d, ignore_errors=True)
    for p in (V4 / 'tuning').iterdir():
        if p.is_dir() and p.name not in ('selection', 'd1'):
            shutil.rmtree(p)
    for p in (V4 / 'rl_data').iterdir():
        if p.is_dir():
            shutil.rmtree(p)
    shutil.rmtree('/tmp/G8CUT/world_scratch', ignore_errors=True)
    gen = Gen()
    reduced = sorted((SRC / 'outputs/framelease_v4/cut_20261115T231415/jobs_reduced').glob('*.jsonl'))
    p4 = write_queue(V4 / 'queue_p4', reduced, gen, {TIMEOUT_JOB: timeout_twice},
                     pending=3 if a.stage == 'pending' else 0)
    p1 = write_queue(V4 / 'queue_p1', sorted((SRC / 'outputs/framelease_v4/queue_p1/jobs.d').glob('*.jsonl')), gen,
                     {NO_LOG_JOB: interrupted_then_ok} if a.no_log_attempt else None)
    p2 = write_queue(V4 / 'queue_p2', sorted((SRC / 'outputs/framelease_v4/queue_p2/jobs.d').glob('*.jsonl')), gen)
    shutil.rmtree('/tmp/G8CUT/world_scratch', ignore_errors=True)
    routes = {}
    for j in p4:
        routes.setdefault(j['block'], set()).add((j['route_id'], j.get('route_index'), j.get('route_set')))
    print(f'stage {a.stage}: queue_p4 {len(p4)} lines, queue_p1 {len(p1)}, queue_p2 {len(p2)}; {gen.n} run directories')
    for b, rs in sorted(routes.items()):
        print(f'  {b}: ' + ', '.join(f'{r} (index {i}, E {i % 2 == 0}, R {i % 3 == 0})' for r, i, _ in sorted(rs)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
