#!/usr/bin/env python3
"""Collect every finished closed-loop run (framelease_v2/run_closed_loop.py) into one CSV. Safe to run at any time.

  python framelease_v2/aggregate_closed_loop.py
  python framelease_v2/aggregate_closed_loop.py --runs-root outputs/framelease_v2/closed_loop_smoke --out /tmp/x.csv

A run is finished when <run>/metrics/result.json exists (run_closed_loop writes it atomically at the end, also after
a failure or timeout). Runs still in progress are skipped and counted. Read-only on every run directory.

One row per finished run:
  identity   job_id, tier, attempt, analysis_use (1 = the result the pre-registered analysis uses: the final attempt
             of a queue job with a valid official route record), exclusion_reason, run_dir
  route      route_id, route_index (pre-registered list), scenario_type, town, route_length_m
  arm        arm (from the queue job, else derived from the run configuration with the same naming rule),
             policy, kappa, seed, max_age_s, lease_params, lease_params_sha256, temporal_mode
  outcome    run_status, route_status, valid_record (official record without an execution-failure status),
             driving_score, route_completion, infraction_penalty, infractions_total, inf_<type> counts for every
             official type, outside_route_lanes_m, collisions_total, km_driven (route_length x completion, the
             leaderboard's definition), collisions_per_km (with the leaderboard's 0.001 km floor)
  runtime    fallback_fraction (fallback ticks / control ticks; 0 for oracle_sync, which never falls back),
             expired_tick_ratio, action_age_{p50,p95,p99,mean}_s, commits, rejects (total) and rejects_by_reason,
             jobs, ticks, gpu_busy_ratio, sim_duration_s, system_duration_s, wall_s (launcher wall time),
             wall_per_sim_s, timed_out, returncode, failures
  integrity  code_matches_prereg / code_mismatch_files: the run's frozen code hashes (manifest identity) against the
             pre-registered pins in routes.json (code_pins); a mismatching run is not used by the analysis
A per-arm summary (analysis_use rows only; descriptive, no tests) goes to <out stem>_arm_summary.csv and stdout.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_ROOT = ROOT / 'outputs/framelease_v2/closed_loop_matrix'
DEFAULT_QUEUE = ROOT / 'outputs/framelease_v2/gpu_queue'
DEFAULT_OUT = DEFAULT_RUNS_ROOT / 'aggregate/closed_loop_runs.csv'
EXECUTION_FAILURE_STATUS = ('Simulation crashed', "Agent's sensors were invalid", "Agent couldn't be set up",
                            'Agent crashed')
INFRACTION_TYPES = ('collisions_pedestrian', 'collisions_vehicle', 'collisions_layout', 'red_light', 'stop_infraction',
                    'outside_route_lanes', 'route_dev', 'route_timeout', 'vehicle_blocked',
                    'yield_emergency_vehicle_infractions', 'scenario_timeouts', 'min_speed_infractions')
COLLISION_TYPES = ('collisions_pedestrian', 'collisions_vehicle', 'collisions_layout')
NON_LEASE_MAX_AGE_S = 3.0
OK_OUTCOMES = ('ok', 'result_with_warnings')

COLUMNS = (['job_id', 'tier', 'attempt', 'analysis_use', 'exclusion_reason', 'run_dir', 'run_created_utc',
            'route_id', 'route_index', 'scenario_type', 'town', 'route_length_m',
            'arm', 'arm_derived', 'policy', 'kappa', 'seed', 'max_age_s', 'lease_params', 'lease_params_sha256',
            'temporal_mode', 'code_matches_prereg', 'code_mismatch_files', 'run_status', 'route_status',
            'valid_record',
            'driving_score', 'route_completion', 'infraction_penalty', 'infractions_total']
           + [f'inf_{t}' for t in INFRACTION_TYPES]
           + ['outside_route_lanes_m', 'collisions_total', 'km_driven', 'collisions_per_km',
              'fallback_fraction', 'expired_tick_ratio', 'action_age_p50_s', 'action_age_p95_s', 'action_age_p99_s',
              'action_age_mean_s', 'commits', 'rejects', 'rejects_by_reason', 'jobs', 'ticks', 'gpu_busy_ratio',
              'sim_duration_s', 'system_duration_s', 'wall_s', 'wall_per_sim_s', 'timed_out', 'returncode',
              'failures'])


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def derive_arm(cfg):
    """Arm name from a run configuration (same rule as framelease_v2/closed_loop_matrix.py)."""
    policy, seed = cfg.get('policy'), cfg.get('seed')
    if policy == 'oracle_sync':
        return f'oracle_sync_s{seed}'
    agent = cfg.get('agent_config') or {}
    rt = agent.get('runtime') or {}
    kappa, max_age = float(rt.get('kappa', cfg.get('kappa', 1.0))), float(rt.get('max_age_s', float('nan')))
    name = policy
    if policy == 'framelease':
        lease = agent.get('lease_params_path')
        stem = Path(lease).stem.replace('lease_params_', '') if lease else 'uncalibrated'
        name += '_' + {'q95_envelope': 'q95env'}.get(stem, stem)
        h_max = cfg.get('lease_h_max_s')
        if h_max is not None and abs(max_age - float(h_max)) > 1e-9:
            name += f'_age{max_age:.1f}'
    elif not abs(max_age - NON_LEASE_MAX_AGE_S) < 1e-9:
        name += f'_age{max_age:.1f}'
    if agent.get('temporal_mode', 'latest') != 'latest':
        name += '_' + str(agent['temporal_mode'])
    return f'{name}_k{kappa:.1f}_s{seed}'


def queue_index(queue_dir):
    """run_dir -> {job_id, tier, attempt, final, outcome, arm}; job_id -> final run_dir."""
    by_run, final_run = {}, {}
    status = Path(queue_dir) / 'status.jsonl'
    if not status.is_file():
        return by_run, final_run
    for line in status.read_text(encoding='utf-8').splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get('event') != 'end' or not r.get('run_dir'):
            continue
        run_dir = str(Path(r['run_dir']).resolve())
        job = r.get('job') or {}
        by_run[run_dir] = {'job_id': r.get('id'), 'tier': r.get('tier'), 'attempt': r.get('attempt'),
                           'final': bool(r.get('final')), 'outcome': r.get('outcome'), 'arm': job.get('arm')}
        if r.get('final'):
            final_run[r.get('id')] = run_dir if r.get('outcome') in OK_OUTCOMES else None
    return by_run, final_run


def num(x):
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def outside_lanes_m(messages):
    """Metres outside the route lanes (leaderboard statistics_manager: 9th token of the message)."""
    try:
        return float(messages[0].split(' ')[8]) if messages else 0.0
    except (IndexError, ValueError):
        return None


def code_check(man, pins):
    """(matches, mismatching files) of a run's frozen code hashes against the pre-registered pins."""
    if not pins:
        return None, None
    code = (man.get('identity') or {}).get('code') or {}
    if not code:
        return None, None
    bad = [rel for rel, want in sorted(pins.items()) if str(ROOT / rel) in code and code[str(ROOT / rel)] != want]
    return int(not bad), ';'.join(bad) or None


def run_row(run_dir, routes, qinfo, final_run, pins=None):
    result = read_json(run_dir / 'metrics/result.json')
    if result is None:
        return None
    cfg = read_json(run_dir / 'config.json') or {}
    man = read_json(run_dir / 'manifest.json') or {}
    route = cfg.get('route') or {}
    rid = str(route.get('route_id', ''))
    meta_route = routes.get(rid, {})
    agent_cfg = cfg.get('agent_config') or {}
    rt = agent_cfg.get('runtime') or {}
    status = result.get('route_status')
    records = result.get('route_records') or 0
    valid = bool(records) and not any(m in str(status) for m in EXECUTION_FAILURE_STATUS)
    scores = result.get('scores') or {}
    infractions = result.get('infractions') or {}
    meta = result.get('meta') or {}
    agent = result.get('agent_summary') or {}
    q = qinfo.get(str(run_dir.resolve()), {})
    arm_derived = derive_arm(cfg) if cfg else None
    row = {k: None for k in COLUMNS}
    row.update(run_dir=str(run_dir), run_created_utc=man.get('created'), route_id=rid,
               route_index=meta_route.get('index'),
               scenario_type=meta_route.get('scenario_type') or ','.join(route.get('scenarios') or []),
               town=route.get('town') or meta_route.get('town'), route_length_m=num(meta.get('route_length')),
               arm=q.get('arm') or arm_derived, arm_derived=arm_derived, policy=cfg.get('policy'),
               kappa=num(cfg.get('kappa')), seed=cfg.get('seed'),
               max_age_s=None if cfg.get('policy') == 'oracle_sync' else num(rt.get('max_age_s')),
               lease_params=Path(agent_cfg['lease_params_path']).name if agent_cfg.get('lease_params_path') else None,
               lease_params_sha256=cfg.get('lease_params_sha256'), temporal_mode=agent_cfg.get('temporal_mode'),
               run_status=man.get('status'), route_status=status, valid_record=int(valid),
               timed_out=result.get('timed_out'), returncode=result.get('returncode'),
               failures='; '.join(map(str, man.get('blockers') or [])) or None,
               job_id=q.get('job_id'), tier=q.get('tier'), attempt=q.get('attempt'))
    if valid:
        rc = num(scores.get('score_route'))
        length = row['route_length_m']
        row.update(driving_score=num(scores.get('score_composed')), route_completion=rc,
                   infraction_penalty=num(scores.get('score_penalty')))
        counts = {t: len(infractions.get(t) or []) for t in INFRACTION_TYPES}
        for t in INFRACTION_TYPES:
            row[f'inf_{t}'] = counts[t]
        row['infractions_total'] = sum(counts.values())
        row['outside_route_lanes_m'] = outside_lanes_m(infractions.get('outside_route_lanes') or [])
        row['collisions_total'] = sum(counts[t] for t in COLLISION_TYPES)
        if length is not None and rc is not None:
            km = length / 1000.0 * rc / 100.0
            row['km_driven'] = km
            row['collisions_per_km'] = row['collisions_total'] / max(km, 0.001)
    row['sim_duration_s'] = num(meta.get('duration_game'))
    row['system_duration_s'] = num(meta.get('duration_system'))
    row['wall_s'] = num(result.get('wall_s'))
    if row['sim_duration_s'] and row['system_duration_s']:
        row['wall_per_sim_s'] = row['system_duration_s'] / row['sim_duration_s']
    if agent:
        age = agent.get('action_age_s') or {}
        row.update(action_age_p50_s=num(age.get('p50')), action_age_p95_s=num(age.get('p95')),
                   action_age_p99_s=num(age.get('p99')), action_age_mean_s=num(age.get('mean')),
                   ticks=agent.get('ticks'), gpu_busy_ratio=num(agent.get('gpu_busy_ratio')),
                   expired_tick_ratio=num(agent.get('expired_tick_ratio')), jobs=agent.get('jobs'),
                   commits=agent.get('commits'))
        if cfg.get('policy') == 'oracle_sync':
            row['fallback_fraction'] = 0.0
        else:
            row['fallback_fraction'] = num(agent.get('fallback_tick_ratio'))
            rejects = agent.get('rejects')
            if isinstance(rejects, dict):
                row['rejects'] = int(sum(v for v in rejects.values() if isinstance(v, (int, float))))
                row['rejects_by_reason'] = json.dumps(rejects, sort_keys=True) if rejects else None
            elif isinstance(rejects, (int, float)):
                row['rejects'] = int(rejects)
    # analysis_use: the final, valid attempt of a queue job
    reason = None
    if not q:
        reason = 'not a queue job'
    elif not valid:
        reason = 'no valid official route record'
    elif final_run.get(q['job_id']) is None:
        reason = 'job not final yet' if q['job_id'] not in final_run else 'job final without a valid record'
    elif final_run[q['job_id']] != str(run_dir.resolve()):
        reason = 'superseded attempt'
    if reason is None and q.get('arm') and arm_derived and q['arm'] != arm_derived:
        reason = f'arm mismatch (job {q["arm"]}, configuration {arm_derived})'
    row['code_matches_prereg'], row['code_mismatch_files'] = code_check(man, pins)
    if reason is None and row['code_matches_prereg'] == 0:
        reason = 'closed-loop code differs from the pre-registered sha256 pins'
    row['analysis_use'] = int(reason is None)
    row['exclusion_reason'] = reason
    return row


def fmt(v):
    if v is None:
        return ''
    if isinstance(v, float):
        return f'{v:.6g}'
    return v


def arm_summary(rows):
    groups = defaultdict(list)
    for r in rows:
        if r['analysis_use']:
            groups[r['arm']].append(r)
    out = []
    for arm in sorted(groups):
        g = groups[arm]

        def mean(key):
            vals = [r[key] for r in g if r[key] is not None]
            return sum(vals) / len(vals) if vals else None

        km = sum(r['km_driven'] or 0.0 for r in g)
        out.append({'arm': arm, 'n_routes': len({r['route_id'] for r in g}), 'n_runs': len(g),
                    'driving_score_mean': mean('driving_score'), 'route_completion_mean': mean('route_completion'),
                    'infraction_penalty_mean': mean('infraction_penalty'),
                    'collisions_per_km_pooled': (sum(r['collisions_total'] or 0 for r in g) / max(km, 0.001))
                    if g else None,
                    'completed_routes': sum(1 for r in g if (r['route_completion'] or 0) >= 100),
                    'fallback_fraction_mean': mean('fallback_fraction'), 'action_age_p50_s_mean': mean('action_age_p50_s'),
                    'action_age_p95_s_mean': mean('action_age_p95_s'), 'sim_duration_s_mean': mean('sim_duration_s'),
                    'wall_s_mean': mean('wall_s')})
    return out


def write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('.' + path.name + '.tmp')
    with tmp.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({k: fmt(r.get(k)) for k in columns})
    tmp.replace(path)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--runs-root', type=Path, action='append',
                   help=f'directory with runs/<run>/ (repeatable; default {DEFAULT_RUNS_ROOT.relative_to(ROOT)})')
    p.add_argument('--queue-dir', type=Path, default=DEFAULT_QUEUE, help='GPU queue (status.jsonl) for job ids')
    p.add_argument('--routes-json', type=Path, default=DEFAULT_RUNS_ROOT / 'routes.json')
    p.add_argument('--out', type=Path, default=DEFAULT_OUT)
    args = p.parse_args(argv)
    roots = args.runs_root or [DEFAULT_RUNS_ROOT]
    matrix = read_json(args.routes_json) or {}
    routes = {r['route_id']: r for r in matrix.get('routes', [])}
    pins = matrix.get('code_pins')
    qinfo, final_run = queue_index(args.queue_dir)
    rows, unfinished = [], []
    for root in roots:
        runs = root / 'runs'
        if not runs.is_dir():
            continue
        for run_dir in sorted(d for d in runs.iterdir() if d.is_dir()):
            row = run_row(run_dir, routes, qinfo, final_run, pins)
            if row is None:
                unfinished.append(str(run_dir))
            else:
                rows.append(row)
    rows.sort(key=lambda r: (str(r['arm']), r['route_index'] if r['route_index'] is not None else 1e9,
                             str(r['route_id']), str(r['run_dir'])))
    write_csv(args.out, rows, COLUMNS)
    summary = arm_summary(rows)
    summary_path = args.out.with_name(args.out.stem + '_arm_summary.csv')
    write_csv(summary_path, summary, list(summary[0].keys()) if summary else ['arm'])
    print(f'{len(rows)} finished runs ({sum(r["analysis_use"] for r in rows)} used by the analysis), '
          f'{len(unfinished)} unfinished/in progress -> {args.out}')
    if summary:
        print(f'{"arm":<30} {"routes":>6} {"DS":>6} {"RC":>6} {"coll/km":>8} {"done":>5} {"fallb":>6} {"age50":>6} {"age95":>6}')
        for s in summary:
            print(f'{s["arm"]:<30} {s["n_routes"]:>6} {fmt_num(s["driving_score_mean"])} '
                  f'{fmt_num(s["route_completion_mean"])} {fmt_num(s["collisions_per_km_pooled"], 8)} '
                  f'{s["completed_routes"]:>5} {fmt_num(s["fallback_fraction_mean"], 6, 3)} '
                  f'{fmt_num(s["action_age_p50_s_mean"], 6, 2)} {fmt_num(s["action_age_p95_s_mean"], 6, 2)}')
    return 0


def fmt_num(v, width=6, digits=1):
    return f'{v:>{width}.{digits}f}' if isinstance(v, (int, float)) else ' ' * (width - 2) + 'NA'


if __name__ == '__main__':
    sys.exit(main())
