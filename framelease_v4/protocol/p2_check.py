#!/usr/bin/env python3
"""Phase-2 completion check and data manifest of framelease_v4/PROTOCOL.md (Secs. 5.3, 5.9, 8.1, 8.4, 9.8; Sec. 8.1:
P2 "ends with: data manifest"). CPU only; reads the P2 job file and its stage spec (framelease_v4/protocol/p2_jobs.py),
the runner's status.jsonl of the P2 queue and the run directories its records name; writes only the report and the data
manifest (--write).

  cd /home/kang/Desktop/DAC
  OMP_NUM_THREADS=1 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/p2_check.py \
      --queue outputs/framelease_v4/queue_p2 [--write]

Which run is the episode of a job: the run directory of the runner's FINAL record of the job in status.jsonl
(framelease_v2/gpu_queue.py Runner.job_states, through select_stage.queue_states), never a directory listing: a listing
such as framelease_v4/rl/dataset.discover_runs over rl_data/ also returns the failed attempts of the Sec. 8.4 retry and
attempts the runner did not count (shared GPU lock busy, interrupted). Those are listed as excluded runs, never used.
Per job:
  episode  the final record is 'ok' or 'result_with_warnings': its run directory must lie in the job's output
           directory, hold a valid official record (select_stage.read_run) and match the job (route, arm fl_behaviour,
           kappa, seed 11, behaviour utility, envelope sha256; kappa-aware, select_stage.matches assumes kappa 1.0);
           otherwise the job is an ERROR, never silently dropped
  missing  the final record has no valid official record after the single infrastructure retry (Sec. 8.4: launch
           error, wall-cap timeout, Simulation crashed, Agent crashed, sensors invalid, set-up failure, no record):
           listed with its cause; nothing is imputed or re-run beyond the registered retry (Secs. 8.4, 9.8)
  pending  no final record yet, or a new attempt after it (--retry-failed): the check is INCOMPLETE
Criteria per episode (the check_smoke.py criteria are imported; PROTOCOL Sec. 8.1):
  record       a valid official route record (status not an execution failure) and raw/official_results.json; the
               launcher's wall time and timeout are reported, not judged (a valid record is final, Sec. 8.4)
  config       check_smoke.c_config: the job's configuration (arm, route, kappa, seed, utility, envelope sha256, fast
               prefix options), and every pinned file the run recorded has the job's sha256
  summary_v4   check_smoke.c_summary: the V4Runtime block, >= 1 tick, the fast_prefix and actor_log blocks
  fast_prefix  check_smoke.c_fast_prefix: stage final, validated, the three options active, SDPA calls > 0
  decisions    check_smoke.c_decisions: complete decision rows (epochs 1..N = the summary's count, the 32 v3 features)
  behaviour    the behaviour branch of check_smoke.c_utility: the agent reports the behaviour utility, and every choice
               epoch has reason both_feasible:<utility> and logs v4_mu = (1 - eps) 1[a = base] + eps / 2, v4_explore,
               v4_base_action = a_det^{d*}(depth) and v4_draw = 0, 1, 2, ...; an episode without a choice epoch logs
               nothing (N/A, flagged no_choice_epoch)
  source_logs  the dataset inputs exist (config.json, metrics/result.json, raw/official_results.json, decisions.jsonl,
               a non-empty ticks.jsonl, summary.json, fast_prefix.json); the sha256 of every source log, the optional
               ones when present (no metric_info.json: the reward is terminal-only, flagged, Sec. 5.2)
Verdict: PASS (every job final and every episode passes every criterion; missing episodes are listed), FAIL (an ERROR, a
failed criterion, or a queue copy of the job file that differs from it), INCOMPLETE (a job without a final outcome).
Exit codes: 0 PASS, 1 FAIL, 2 error (missing inputs, a test route, a stage spec of another job file), 3 INCOMPLETE.
Outputs (--write; an existing file with other content is never overwritten without --force, an equal one is kept):
  outputs/framelease_v4/rl_data/p2_check.json       the report: every job, its attempts and criteria, excluded runs
  outputs/framelease_v4/rl_data/data_manifest.json  on PASS only: the offline-RL dataset of Sec. 5.3 is exactly the
      listed episodes (run directory, route, kappa, behaviour seed, DS, decision and choice counts, flags, the sha256
      of every source log), plus the missing episodes with their causes and the excluded run directories (Sec. 5.9:
      "the dataset manifest: episode list, and the sha256 of every source log"). P3 builds the dataset from these
      run directories (framelease_v4/rl/dataset.build_dataset); the path and sha256 go into PROTOCOL Sec. 13.2.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from framelease_v4.protocol import check_smoke as CS  # noqa: E402
from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402
from framelease_v4.protocol import p2_jobs as P2  # noqa: E402
from framelease_v4.protocol import select_stage as SS  # noqa: E402

SCHEMA = 'framelease_v4.p2_completion_check/1'
MANIFEST_SCHEMA = 'framelease_v4.p2_data_manifest/1'
THIS_REL = 'framelease_v4/protocol/p2_check.py'
JOB_FILE = P2.block_paths()[0]
QUEUE = ROOT / P2.QUEUE_REL
REPORT_PATH = ROOT / P2.RL_DATA_REL / 'p2_check.json'
MANIFEST_PATH = ROOT / P2.RL_DATA_REL / 'data_manifest.json'
CRITERIA = ('record', 'config', 'summary_v4', 'fast_prefix', 'decisions', 'behaviour', 'source_logs')
FL = 'raw/agent/framelease/'
METRIC_INFO = 'raw/agent/metric_info.json'
# (path in the run directory, required): what framelease_v4/rl/dataset.py and prefix_score.py read, and the logs of
# the run's timeline and evaluation (Sec. 2.5)
SOURCE_LOGS = (('config.json', True), ('manifest.json', False), ('metrics/result.json', True),
               ('raw/official_results.json', True), (METRIC_INFO, False), (FL + 'decisions.jsonl', True),
               (FL + 'ticks.jsonl', True), (FL + 'summary.json', True), (FL + 'fast_prefix.json', True),
               (FL + 'jobs.jsonl', False), (FL + 'events.jsonl', False), (FL + 'actors.jsonl.gz', False),
               (FL + 'actor_log.json', False))
NON_EMPTY = (FL + 'decisions.jsonl', FL + 'ticks.jsonl')
STATUSES = ('episode', 'missing', 'pending', 'error', 'failed_criteria')
PASS, FAIL, NA = CS.PASS, CS.FAIL, CS.NA


# ============================================================================================ the block

def load_block(job_file=JOB_FILE):
    """(jobs, stage spec, job file sha256, stage spec path) of the P2 block. A job on a test route or with an output
    directory outside rl_data/ is refused (PermissionError); a stage spec written for another job file is an error."""
    job_file = Path(job_file)
    if not job_file.is_file() or not job_file.name.endswith('.jsonl'):
        raise FileNotFoundError(f'{PJ.rel(job_file)} not found (framelease_v4/protocol/p2_jobs.py --check --write)')
    jobs = [json.loads(x) for x in job_file.read_text(encoding='utf-8').splitlines() if x.strip()]
    sha = PJ.sha256_file(job_file)
    spec_path = job_file.with_name(job_file.name[:-len('.jsonl')] + '.stage.json')
    spec = CS._read_json(spec_path)
    if not isinstance(spec, dict) or spec.get('schema') != P2.STAGE_SCHEMA:
        raise FileNotFoundError(f'{PJ.rel(spec_path)}: no P2 stage spec ({P2.STAGE_SCHEMA}) next to the job file')
    if spec.get('job_file_sha256') != sha:
        raise ValueError(f'{PJ.rel(spec_path)} was written for another job file (job_file_sha256 differs from '
                         f'{PJ.rel(job_file)})')
    if [x.get('id') for x in spec.get('jobs') or []] != [j.get('id') for j in jobs]:
        raise ValueError(f'{PJ.rel(spec_path)} lists other jobs than {PJ.rel(job_file)}')
    train, test = P2.training_and_test()
    for j in jobs:
        if (j.get('phase'), j.get('block'), j.get('arm_name')) != (P2.PHASE, P2.BLOCK, P2.ARM):
            raise ValueError(f'{j.get("id")}: not a P2 behaviour job')
        r = str(j.get('route_id'))
        if r not in train or r in test:
            raise PermissionError(f'{j.get("id")}: route {r} is not a training route; test routes are never RL data '
                                  '(PROTOCOL Sec. 3.3)')
        if not str(j.get('output_dir')).startswith(P2.RL_DATA_REL + '/'):
            raise PermissionError(f'{j.get("id")}: output directory {j.get("output_dir")} outside {P2.RL_DATA_REL}')
    return jobs, spec, sha, spec_path


# ============================================================================================ the final run of a job

def run_matches(rec, job):
    """Is a run (select_stage.read_run) the job's configuration? Kappa-aware (select_stage.matches uses kappa 1.0)."""
    try:
        same = (rec['route_id'] == str(job['route_id']) and rec['v4_arm'] == job['arm_name']
                and float(rec['kappa']) == float(job['kappa']) and int(rec['seed']) == int(job['seed']))
    except (KeyError, TypeError, ValueError):
        return False
    if not same or any(rec['policy_params'].get(k) != v for k, v in (job.get('policy_params') or {}).items()):
        return False
    return rec.get('envelope_sha256') == (job.get('envelope') or {}).get('sha256')


def _attempt(e):
    res = e.get('result') or {}
    return {'attempt': e.get('attempt'), 'outcome': e.get('outcome'), 'counted': e.get('counted'),
            'final': e.get('final'), 'run_dir': PJ.rel(e['run_dir']) if e.get('run_dir') else None,
            'route_status': res.get('route_status'), 'end_utc': e.get('end_utc'), 'wall_s': e.get('wall_s')}


def job_final(job, state, root=ROOT):
    """The job's outcome from the runner's records (select_stage.queue_states entry or None):
    {'status': 'episode' | 'missing' | 'pending' | 'error', 'attempts', ...}; an episode also carries 'run' (Path)
    and 'record' (select_stage.read_run)."""
    state = state or {}
    ends = state.get('ends') or []
    out = {'job': job['id'], 'attempts': [_attempt(e) for e in ends]}
    fin = state.get('final')
    if fin is None:
        if not state:
            cause = 'no runner record yet'
        elif state.get('open'):
            cause = f'attempt {state["open"].get("attempt")} started, no end record'
        else:
            cause = f'no final record yet ({sum(1 for e in ends if e.get("counted"))} counted of {len(ends)} attempts)'
        return {**out, 'status': 'pending', 'cause': cause}
    if state.get('after_final'):
        return {**out, 'status': 'pending',
                'cause': 'the runner is re-trying the job after its final record (--retry-failed)'}
    out['final'] = _attempt(fin)
    res = fin.get('result') or {}
    if fin.get('outcome') not in SS.OK_OUTCOMES:
        cause = str(fin.get('outcome')) + (f' ({res.get("route_status")})' if res.get('route_status') else '')
        return {**out, 'status': 'missing', 'cause': cause}
    rd = fin.get('run_dir')
    problems = []
    run = SS._abs(rd, root) if rd else None
    if run is None:
        problems.append('it names no run directory')
    else:
        rec = SS.read_run(run) if run.is_dir() else None
        if not SS._same_path(run.parent, Path(root) / job['output_dir'] / 'runs', root):
            problems.append(f'{rd} is not in {job["output_dir"]}/runs')
        if rec is None:
            problems.append(f'{rd} is not a run directory (no config.json)')
        elif not rec['valid']:
            problems.append(f'{rd} holds no valid official record ({rec["route_status"]})')
        elif not run_matches(rec, job):
            problems.append(f'{rd} is another configuration (route {rec["route_id"]}, arm {rec["v4_arm"]}, kappa '
                            f'{rec["kappa"]}, seed {rec["seed"]}, utility {rec["policy_params"].get("utility")})')
    if problems:
        return {**out, 'status': 'error',
                'cause': f'the runner\'s final record says {fin.get("outcome")!r} but ' + '; '.join(problems)}
    return {**out, 'status': 'episode', 'run_dir': PJ.rel(run), 'run': run, 'record': rec}


# ============================================================================================ criteria (one episode)

def c_record(run, rec):
    res = CS._read_json(run / 'metrics' / 'result.json') or {}
    vals = {'route_status': rec['route_status'], 'route_records': rec['route_records'], 'ds': rec['ds'],
            'timed_out': res.get('timed_out'), 'wall_s': res.get('wall_s')}
    if not rec['valid']:
        return CS._res(FAIL, f'no valid official record ({rec["route_status"]})', **vals)
    if not (run / 'raw' / 'official_results.json').is_file():
        return CS._res(FAIL, 'raw/official_results.json missing', **vals)
    return CS._res(PASS, str(rec['route_status']), **vals)


def c_behaviour(job, run, summary, rows):
    """The behaviour branch of check_smoke.c_utility; no choice epoch: N/A (nothing was logged)."""
    from framelease_v4.rl import behaviour as B
    name = (job.get('policy_params') or {}).get('utility')
    if B.parse_behaviour(name) is None:
        return CS._res(FAIL, f'{name!r} is not a behaviour utility')
    res = CS.c_utility(job, run, summary, rows)
    if res['status'] == CS.DEFERRED:
        return CS._res(NA, 'no choice epoch (|A_feas| = 2 never held): nothing to log, no SMDP transition',
                       **(res.get('values') or {}))
    return res


def c_source_logs(run):
    files, missing, empty = {}, [], []
    for rel, required in SOURCE_LOGS:
        p = run / rel
        if p.is_file():
            files[rel] = PJ.sha256_file(p)
            if rel in NON_EMPTY and p.stat().st_size == 0:
                empty.append(rel)
        elif required:
            missing.append(rel)
    problems = ([f'missing {missing}'] if missing else []) + ([f'empty {empty}'] if empty else [])
    absent = [rel for rel, required in SOURCE_LOGS if not required and rel not in files]
    return CS._res(FAIL if problems else PASS, '; '.join(problems) or f'{len(files)} source logs hashed',
                   files=files, optional_absent=absent)


def check_episode(job, run, rec):
    """({criterion: result}, decision rows) of one episode; a malformed artefact fails its criterion, not the
    check."""
    fl = run / 'raw' / 'agent' / 'framelease'
    summary = CS._read_json(fl / 'summary.json')
    rows, problem = CS.strict_jsonl(fl / 'decisions.jsonl') if (fl / 'decisions.jsonl').is_file() else (None, None)
    steps = (('record', lambda: c_record(run, rec)), ('config', lambda: CS.c_config(job, run)),
             ('summary_v4', lambda: CS.c_summary(summary)), ('fast_prefix', lambda: CS.c_fast_prefix(run)),
             ('decisions', lambda: CS.c_decisions(run, summary, rows, problem)),
             ('behaviour', lambda: c_behaviour(job, run, summary, rows)), ('source_logs', lambda: c_source_logs(run)))
    out = {}
    for name, fn in steps:
        try:
            out[name] = fn()
        except Exception as e:  # noqa: BLE001  a malformed artefact fails its criterion
            out[name] = CS._res(FAIL, f'check raised {type(e).__name__}: {e}')
    return out, rows or []


def episode_entry(job, fin, crit, rows):
    rec = fin['record']
    files = ((crit.get('source_logs') or {}).get('values') or {}).get('files') or {}
    choice = [r for r in rows if r.get('p_both') is True]
    flags = []
    if METRIC_INFO not in files:
        flags.append('terminal_only_reward')                       # PROTOCOL Sec. 5.2
    if not choice:
        flags.append('no_choice_epoch')
    if fin['final']['outcome'] != 'ok':
        flags.append(fin['final']['outcome'])
    if sum(1 for a in fin['attempts'] if a.get('counted')) > 1:
        flags.append('retried')
    if ((crit.get('record') or {}).get('values') or {}).get('timed_out'):
        flags.append('launcher_timed_out')
    return {'job': job['id'], 'route_id': job['route_id'], 'scenario_type': job.get('scenario_type'),
            'town': job.get('town'), 'kappa': job['kappa'], 'seed': job['seed'],
            'behaviour_seed': (job.get('behaviour') or {}).get('seed'), 'utility': job['policy_params']['utility'],
            'run_dir': fin['run_dir'], 'route_status': rec['route_status'], 'ds': rec['ds'], 'rc': rec['rc'],
            'n_decisions': len(rows), 'n_choice': len(choice),
            'n_explored': sum(int((r.get('features') or {}).get('v4_explore') or 0) for r in choice),
            'final_record': fin['final'], 'attempts': fin['attempts'], 'source_logs_sha256': files, 'flags': flags}


# ============================================================================================ the block check

def excluded_runs(jobs, states, episode_dirs, root=ROOT):
    """Run directories under the block's output directories that are not episodes: attempts named by the runner's
    records (not counted, failed and retried, final without a valid record) and directories no record names."""
    named = {}
    for j in jobs:
        for e in (states.get(j['id']) or {}).get('ends') or []:
            for rd in [e.get('run_dir')] + list(e.get('other_new_run_dirs') or []):
                if rd:
                    named.setdefault(str(SS._abs(rd, root).resolve()), (j['id'], e))
    out = []
    for d in sorted({j['output_dir'] for j in jobs}):
        runs = Path(root) / d / 'runs'
        for run in (sorted(p for p in runs.iterdir() if p.is_dir()) if runs.is_dir() else []):
            key = str(run.resolve())
            if key in episode_dirs:
                continue
            if key not in named:
                out.append({'run_dir': PJ.rel(run), 'job': None, 'reason': 'no runner record names this directory'})
                continue
            jid, e = named[key]
            if not e.get('counted'):
                why = f'attempt not counted by the runner ({e.get("outcome")})'
            elif e.get('outcome') in SS.OK_OUTCOMES:
                why = 'final run of a job that is not an episode (error or failed criterion)'
            elif not e.get('final'):
                why = 'failed attempt, retried (PROTOCOL Sec. 8.4)'
            else:
                why = 'final attempt without a valid official record (missing episode)'
            out.append({'run_dir': PJ.rel(run), 'job': jid, 'attempt': e.get('attempt'), 'outcome': e.get('outcome'),
                        'counted': e.get('counted'), 'final': e.get('final'), 'reason': why})
    return out


def check(job_file=JOB_FILE, queue_dir=QUEUE, root=ROOT):
    """(report, data manifest or None) of the P2 block; the manifest only on PASS."""
    jobs, spec, job_sha, spec_path = load_block(job_file)
    if queue_dir is None:
        raise ValueError('the runner\'s records decide which run is final: give --queue')
    states = SS.queue_states(queue_dir)
    problems, warnings = [], []
    copy = Path(queue_dir) / 'jobs.d' / Path(job_file).name
    if copy.is_file():
        if PJ.sha256_file(copy) != job_sha:
            problems.append(f'{PJ.rel(copy)} differs from {PJ.rel(job_file)}: the queue ran another job file')
    else:
        warnings.append(f'{PJ.rel(copy)} not found: the queue copy of the job file was not compared')
    rows, episodes, missing, pending, errors, episode_dirs = [], [], [], [], [], set()
    for j in jobs:
        fin = job_final(j, states.get(j['id']), root)
        row = {'job': j['id'], 'route_id': j['route_id'], 'kappa': j['kappa'], 'status': fin['status'],
               'cause': fin.get('cause'), 'run_dir': fin.get('run_dir'), 'final': fin.get('final'),
               'attempts': fin['attempts']}
        if fin['status'] == 'episode':
            crit, drows = check_episode(j, fin['run'], fin['record'])
            row['criteria'] = crit
            failed = [k for k, c in crit.items() if c['status'] == FAIL]
            if failed:
                row.update(status='failed_criteria', failed=failed)
            else:
                episodes.append(episode_entry(j, fin, crit, drows))
                episode_dirs.add(str(fin['run'].resolve()))
        elif fin['status'] == 'missing':
            missing.append({'job': j['id'], 'route_id': j['route_id'], 'kappa': j['kappa'],
                            'scenario_type': j.get('scenario_type'), 'cause': fin['cause'],
                            'attempts': fin['attempts']})
        elif fin['status'] == 'pending':
            pending.append(f'{j["id"]}: {fin["cause"]}')
        else:
            errors.append(f'{j["id"]}: {fin["cause"]}')
        rows.append(row)
    excluded = excluded_runs(jobs, states, episode_dirs, root)
    unnamed = [x['run_dir'] for x in excluded if x['job'] is None]
    if unnamed:
        warnings.append(f'{len(unnamed)} run directories under {P2.RL_DATA_REL} are named by no runner record '
                        f'(excluded, never episodes): {unnamed[:5]}')
    failed_jobs = [r['job'] for r in rows if r['status'] == 'failed_criteria']
    verdict = 'FAIL' if (errors or failed_jobs or problems) else ('INCOMPLETE' if pending else 'PASS')
    counts = {s: sum(1 for r in rows if r['status'] == s) for s in STATUSES}
    per_kappa = {f'{k:.1f}': sum(1 for e in episodes if e['kappa'] == k) for k in P2.KAPPAS}
    now = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    status_path = Path(queue_dir) / 'status.jsonl'
    common = {'variant': spec.get('variant'), 'phase': P2.PHASE, 'job_file': PJ.rel(job_file),
              'job_file_sha256': job_sha,
              'stage_spec': PJ.rel(spec_path), 'stage_spec_sha256': PJ.sha256_file(spec_path),
              'tuning_freeze': spec.get('tuning_freeze'), 'L_star': spec.get('L_star'), 'd_star': spec.get('d_star'),
              'eps': spec.get('eps'), 'kappas': spec.get('kappas'), 'queue': PJ.rel(queue_dir),
              'status_jsonl_sha256': PJ.sha256_file(status_path), 'n_jobs': len(jobs), 'episodes_per_kappa': per_kappa}
    rep = {'schema': SCHEMA, 'verdict': verdict, **common,
           'gate': 'P2 ends with the data manifest (PROTOCOL Sec. 8.1); its path and sha256 go into PROTOCOL Sec. 13.2 '
                   'and the RL freeze (Sec. 5.9)',
           'counts': counts, 'missing': missing, 'pending': pending, 'errors': errors, 'failed_criteria': failed_jobs,
           'problems': problems, 'warnings': warnings, 'excluded_runs': excluded, 'criteria': list(CRITERIA),
           'jobs': rows, 'script': THIS_REL, 'script_sha256': PJ.sha256_file(Path(__file__)), 'written': now}
    manifest = None
    if verdict == 'PASS':
        manifest = {'schema': MANIFEST_SCHEMA, **common,
                    'dataset': 'the offline-RL dataset of PROTOCOL Sec. 5.3 is exactly the episodes below; P3 builds '
                               'it from their run directories (framelease_v4/rl/dataset.build_dataset; Sec. 5.9)',
                    'n_episodes': len(episodes), 'n_missing': len(missing),
                    'episodes': sorted(episodes, key=lambda e: (e['kappa'], int(e['route_id']))),
                    'missing': missing,
                    'missing_rule': 'a job without a valid official record after the single infrastructure retry '
                                    '(Sec. 8.4) is listed; nothing is imputed or re-run (Sec. 9.8)',
                    'excluded_runs': excluded, 'source_logs': [rel for rel, _ in SOURCE_LOGS],
                    'check': {'schema': SCHEMA, 'script': THIS_REL, 'script_sha256': rep['script_sha256']},
                    'written': now}
    return rep, manifest


# ============================================================================================ output

def write_json(doc, path, force=False):
    """(path, written): an existing file that differs only in 'written' is kept (its sha256 may be cited); one with
    other content is refused without force."""
    path = Path(path)
    if path.exists():
        old = CS._read_json(path) or {}
        if {k: v for k, v in old.items() if k != 'written'} == {k: v for k, v in doc.items() if k != 'written'}:
            return path, False
        if not force:
            raise FileExistsError(f'refusing to overwrite {PJ.rel(path)} with a different document (use --force)')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return path, True


def summary_lines(rep):
    c = rep['counts']
    out = [f'P2 check: {rep["verdict"]}  ({rep["n_jobs"]} jobs: {c["episode"]} episodes, {c["missing"]} missing, '
           f'{c["pending"]} pending, {c["error"]} errors, {c["failed_criteria"]} failing a criterion; episodes per '
           f'kappa {rep["episodes_per_kappa"]})']
    out += [f'  PROBLEM {p}' for p in rep['problems']]
    out += [f'  ERROR {e}' for e in rep['errors']]
    for r in rep['jobs']:
        if r['status'] == 'failed_criteria':
            out.append(f'  FAIL {r["job"]}: ' + ' | '.join(f'{k}: {r["criteria"][k]["detail"]}' for k in r['failed']))
    out += [f'  missing episode {m["job"]}: {m["cause"]}' for m in rep['missing']]
    out += [f'  pending {p}' for p in rep['pending'][:10]]
    if len(rep['pending']) > 10:
        out.append(f'  ... {len(rep["pending"]) - 10} more pending')
    if rep['excluded_runs']:
        out.append(f'  {len(rep["excluded_runs"])} run directories are not episodes (failed or uncounted attempts, '
                   'unnamed directories): listed under excluded_runs')
    out += [f'  warning: {w}' for w in rep['warnings']]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--queue', type=Path, default=QUEUE, help='the P2 gpu_queue directory (its status.jsonl)')
    ap.add_argument('--job-file', type=Path, default=JOB_FILE)
    ap.add_argument('--write', action='store_true', help='write the report, and the data manifest on PASS')
    ap.add_argument('--report', type=Path, default=REPORT_PATH)
    ap.add_argument('--manifest', type=Path, default=MANIFEST_PATH)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--root', type=Path, default=ROOT, help='root of the jobs\' relative output directories')
    a = ap.parse_args(argv)
    try:
        rep, man = check(a.job_file, a.queue, a.root)
        print('\n'.join(summary_lines(rep)))
        if a.write:
            for doc, path in ((rep, a.report), (man, a.manifest)):
                if doc is None:
                    print(f'no data manifest written (verdict {rep["verdict"]})')
                    continue
                p, written = write_json(doc, path, a.force)
                print(f'{"wrote" if written else "unchanged"} {p}  sha256 {PJ.sha256_file(p)}')
    except (SS.SelectionError, FileNotFoundError, FileExistsError, ValueError, KeyError, PermissionError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2
    return {'PASS': 0, 'FAIL': 1, 'INCOMPLETE': 3}[rep['verdict']]


if __name__ == '__main__':
    raise SystemExit(main())
