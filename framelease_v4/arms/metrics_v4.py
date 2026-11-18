#!/usr/bin/env python3
"""Per-run and per-arm metrics of closed-loop runs (framelease_v4/arms; read-only on every run directory).

  python framelease_v4/arms/metrics_v4.py --runs-root outputs/framelease_v4/<matrix> [--out runs.csv]
      [--arm-summary arms.csv] [--realized] [--json runs.json]

A run is a directory with metrics/result.json (written by run_closed_loop_v4.py, and by the v2 / v3 / fast-prefix
launchers). Definitions (identical for every arm; the runtime quantities are recomputed from the run's own logs and
cross-checked against summary.json):

Bench2Drive (official record, raw/official_results.json via metrics/result.json)
  driving_score        score_composed;  route_completion  score_route;  infraction_penalty  score_penalty
  success              Bench2Drive definition (bench2drive/tools/statistic_route_json.is_success): status
                       'Completed' or 'Perfect' and no infraction of any type except min_speed_infractions
  collisions_per_km    (pedestrian + vehicle + layout collisions) / max(route length x completion, 0.001 km)
Runtime (ticks.jsonl, jobs.jsonl, events.jsonl, decisions.jsonl; simulated time of the cost-model timeline)
  gpu_usage            GPU-busy simulated seconds / simulated seconds of the run: summary.json's exact busy
                       intervals (prefix and flow-step costs, kappa-scaled) inside [first tick, last tick + 0.05 s];
                       gpu_usage_recomputed from jobs.jsonl + job_start events (the steps of a job still running at
                       the end are not in jobs.jsonl, so it can be lower by at most that job's steps)
  deadline_miss_ratio  control ticks without a valid committed action (mode fallback: no plan yet, plan expired,
                       re-anchoring failed) / control ticks; *_after_first_commit over the ticks from the first commit
  expired_ratio        ticks in fallback because the committed action's deadline passed / control ticks
  fallback_episodes    entries into fallback (maximal runs of consecutive fallback ticks)
  action_age_*         age (tick time - capture time of the tracked action's observation) over tracked ticks
  p_both               shield decision epochs with |A_feas| = 2 / shield decision epochs (decisions.jsonl rows with a
                       non-null p_both; None for the arms without a shield)
  realized_*           (--realized) realized validity from the evaluation-only actor log (realized.py)
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FRAME_DT_S = 0.05
EXECUTION_FAILURE_STATUS = ('Simulation crashed', "Agent's sensors were invalid", "Agent couldn't be set up",
                            'Agent crashed')
INFRACTION_TYPES = ('collisions_pedestrian', 'collisions_vehicle', 'collisions_layout', 'red_light', 'stop_infraction',
                    'outside_route_lanes', 'route_dev', 'route_timeout', 'vehicle_blocked',
                    'yield_emergency_vehicle_infractions', 'scenario_timeouts', 'min_speed_infractions')
COLLISION_TYPES = ('collisions_pedestrian', 'collisions_vehicle', 'collisions_layout')
SUCCESS_STATUS = ('Completed', 'Perfect')


# ============================================================================================ readers

def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def read_jsonl(path):
    out = []
    p = Path(path)
    if not p.is_file():
        return out
    with p.open(encoding='utf-8') as f:
        for line in f:
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    break                              # a line cut by a crash ends the stream
    return out


def num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def quantiles(values, qs=(0.5, 0.95)):
    a = np.asarray([v for v in values if v is not None and math.isfinite(v)], dtype=float)
    out = {f'p{int(q * 100)}': (float(np.quantile(a, q)) if a.size else None) for q in qs}
    out['mean'] = float(a.mean()) if a.size else None
    out['n'] = int(a.size)
    return out


# ============================================================================================ Bench2Drive

def b2d_success(status, infractions):
    """Bench2Drive success: status Completed / Perfect and no infraction except min_speed_infractions."""
    if status not in SUCCESS_STATUS:
        return False
    for k, v in (infractions or {}).items():
        if k != 'min_speed_infractions' and len(v or []) > 0:
            return False
    return True


def outside_lanes_m(messages):
    try:
        return float(messages[0].split(' ')[8]) if messages else 0.0
    except (IndexError, ValueError):
        return None


def b2d_metrics(result):
    status = result.get('route_status')
    records = result.get('route_records') or 0
    valid = bool(records) and not any(m in str(status) for m in EXECUTION_FAILURE_STATUS)
    out = {'route_status': status, 'valid_record': int(valid)}
    if not valid:
        return out
    scores = result.get('scores') or {}
    inf = result.get('infractions') or {}
    meta = result.get('meta') or {}
    counts = {t: len(inf.get(t) or []) for t in INFRACTION_TYPES}
    rc = num(scores.get('score_route'))
    length = num(meta.get('route_length'))
    out.update(driving_score=num(scores.get('score_composed')), route_completion=rc,
               infraction_penalty=num(scores.get('score_penalty')), success=int(b2d_success(status, inf)),
               infractions_total=sum(counts.values()), collisions_total=sum(counts[t] for t in COLLISION_TYPES),
               outside_route_lanes_m=outside_lanes_m(inf.get('outside_route_lanes') or []),
               route_length_m=length, sim_duration_s=num(meta.get('duration_game')))
    out.update({f'inf_{t}': counts[t] for t in INFRACTION_TYPES})
    if length is not None and rc is not None:
        km = length / 1000.0 * rc / 100.0
        out['km_driven'] = km
        out['collisions_per_km'] = out['collisions_total'] / max(km, 0.001)
    return out


# ============================================================================================ runtime

def busy_intervals(jobs, events):
    """GPU-busy intervals of the cost-model timeline from jobs.jsonl (+ job_start events of unfinished jobs)."""
    iv, seen = [], set()
    for j in jobs:
        seen.add(int(j['job_id']))
        pre = j.get('prefix') or {}
        end, cost = num(j.get('prefix_end_s')), num(pre.get('timeline_cost_s'))
        if end is not None and cost is not None:
            iv.append((end - cost, end))
        for s in j.get('steps') or []:
            a, c = num(s.get('launch_s')), num(s.get('timeline_cost_s'))
            if a is not None and c is not None:
                iv.append((a, a + c))
    for e in events:
        if e.get('kind') == 'job_start' and int(e.get('job_id', -1)) not in seen:
            end, cost = num(e.get('prefix_end_s')), num(e.get('prefix_timeline_s'))
            if end is not None and cost is not None:
                iv.append((end - cost, end))
    return iv


def busy_within(intervals, t0, t1):
    return float(sum(max(0.0, min(b, t1) - max(a, t0)) for a, b in intervals))


def tick_metrics(ticks, first_commit_s=None):
    n = len(ticks)
    out = {'ticks': n}
    if not n:
        return out
    t = [float(r['sim_s']) for r in ticks]
    modes = [r.get('mode') for r in ticks]
    reasons = Counter(r.get('fallback_reason') for r in ticks if r.get('mode') != 'track')
    fb = [m != 'track' for m in modes]
    episodes = sum(1 for i, x in enumerate(fb) if x and (i == 0 or not fb[i - 1]))
    ages = [float(r['sim_s']) - float(r['incumbent']['capture_s']) for r in ticks
            if r.get('mode') == 'track' and r.get('incumbent')]
    out.update(first_tick_s=t[0], last_tick_s=t[-1], sim_span_s=t[-1] - t[0] + FRAME_DT_S,
               track_ticks=n - sum(fb), fallback_ticks=sum(fb), fallback_by_reason=dict(reasons),
               deadline_miss_ratio=sum(fb) / n, expired_ratio=reasons.get('expired', 0) / n,
               fallback_episodes=episodes)
    if first_commit_s is not None:
        after = [x for x, ti in zip(fb, t) if ti + 1e-6 >= first_commit_s]
        out['ticks_after_first_commit'] = len(after)
        out['deadline_miss_ratio_after_first_commit'] = (sum(after) / len(after)) if after else None
    age = quantiles(ages)
    out.update(action_age_p50_s=age['p50'], action_age_p95_s=age['p95'], action_age_mean_s=age['mean'])
    return out


def decision_metrics(decisions):
    shield = [d for d in decisions if d.get('p_both') is not None]
    acts = Counter(d.get('action') for d in decisions)
    out = {'decision_epochs': len(decisions), 'shield_epochs': len(shield),
           'p_both': (sum(1 for d in shield if d['p_both']) / len(shield)) if shield else None,
           'actions': dict(acts)}
    if shield:
        out['admitted_ratio'] = sum(1 for d in shield if d.get('admitted')) / len(shield)
    return out


def job_metrics(jobs, span_s):
    committed = [d for j in jobs for d in (j.get('committed_depths') or [])]
    final = [int(j.get('final_depth') or 0) for j in jobs]
    starts = Counter((j.get('policy_state') or {}).get('start_action') for j in jobs)
    triggers = Counter((j.get('policy_state') or {}).get('start_trigger') for j in jobs)
    return {'jobs': len(jobs), 'commits': len(committed),
            'committed_depth_mean': float(np.mean(committed)) if committed else None,
            'final_depth_mean': float(np.mean(final)) if final else None,
            'refresh_rate_hz': (len(jobs) / span_s) if span_s else None,
            'start_actions': {str(k): v for k, v in starts.items() if k is not None},
            'start_triggers': {str(k): v for k, v in triggers.items() if k is not None}}


def derived_arm(cfg):
    """Arm label of a run without an 'arm' key (v2 / v3 launchers): framelease_v2's naming rule."""
    if not cfg:
        return None
    try:
        from framelease_v2.aggregate_closed_loop import derive_arm
        return derive_arm(cfg)
    except Exception:  # noqa: BLE001
        return cfg.get('policy')


# ============================================================================================ one run

def run_metrics(run_dir, realized=False):
    """One row of metrics for a finished run directory (None if it has no metrics/result.json)."""
    run_dir = Path(run_dir)
    result = read_json(run_dir / 'metrics/result.json')
    if result is None:
        return None
    cfg = read_json(run_dir / 'config.json') or {}
    man = read_json(run_dir / 'manifest.json') or {}
    fl = run_dir / 'raw' / 'agent' / 'framelease'
    summary = result.get('agent_summary') or read_json(fl / 'summary.json') or {}
    route = cfg.get('route') or {}
    agent_cfg = cfg.get('agent_config') or {}
    fp = cfg.get('fast_prefix') or {}
    row = {'run_dir': str(run_dir), 'run_created_utc': man.get('created'), 'run_status': man.get('status'),
           'arm': cfg.get('arm') or derived_arm(cfg), 'v4_arm': cfg.get('v4_arm'), 'kind': cfg.get('kind'), 'policy': cfg.get('policy'),
           'title': cfg.get('title'), 'route_id': str(route.get('route_id', '')), 'town': route.get('town'),
           'scenario_type': ','.join(route.get('scenarios') or []), 'seed': cfg.get('seed'),
           'kappa': num(cfg.get('kappa')), 'max_age_s': num((agent_cfg.get('runtime') or {}).get('max_age_s')),
           'fast_prefix': ','.join(fp.get('options') or []) if fp else None,
           'timed_out': result.get('timed_out'), 'wall_s': num(result.get('wall_s'))}
    row.update(b2d_metrics(result))
    ticks = read_jsonl(fl / 'ticks.jsonl')
    jobs = read_jsonl(fl / 'jobs.jsonl')
    events = read_jsonl(fl / 'events.jsonl')
    decisions = read_jsonl(fl / 'decisions.jsonl')
    commits = [e for e in events if e.get('kind') == 'commit']
    first_commit = min((float(e['commit_s']) for e in commits if e.get('commit_s') is not None), default=None)
    tm = tick_metrics(ticks, first_commit)
    row.update({k: v for k, v in tm.items() if k != 'fallback_by_reason'})
    row['fallback_by_reason'] = json.dumps(tm.get('fallback_by_reason') or {}, sort_keys=True)
    row['first_commit_s'] = first_commit
    if ticks:
        t0, t1 = tm['first_tick_s'], tm['last_tick_s'] + FRAME_DT_S
        busy = busy_within(busy_intervals(jobs, events), t0, t1)
        row['gpu_busy_recomputed_s'] = busy
        row['gpu_usage_recomputed'] = busy / tm['sim_span_s'] if tm['sim_span_s'] else None
    row['gpu_usage'] = num(summary.get('gpu_busy_ratio'))
    row['gpu_busy_in_span_s'] = num(summary.get('gpu_busy_in_span_s'))
    if row['gpu_usage'] is None:
        row['gpu_usage'] = row.get('gpu_usage_recomputed')
    dm = decision_metrics(decisions)
    row.update({k: v for k, v in dm.items() if k != 'actions'})
    row['decision_actions'] = json.dumps(dm['actions'], sort_keys=True)
    jm = job_metrics(jobs, tm.get('sim_span_s'))
    row.update({k: v for k, v in jm.items() if k not in ('start_actions', 'start_triggers')})
    row['start_actions'] = json.dumps(jm['start_actions'], sort_keys=True)
    row['start_triggers'] = json.dumps(jm['start_triggers'], sort_keys=True)
    v3 = summary.get('v3') or {}
    lease = v3.get('lease_s') or summary.get('lease_s') or {}
    row['lease_p50_s'] = num(lease.get('p50'))
    row['actor_log_bytes'] = (fl / 'actors.jsonl.gz').stat().st_size if (fl / 'actors.jsonl.gz').is_file() else None
    al = summary.get('actor_log') or {}
    row['actor_log_ticks'] = al.get('ticks_logged')
    row['actor_log_errors'] = al.get('errors')
    # cross-checks against the runtime's own summary (recomputed from the logs above)
    checks = {}
    if summary.get('fallback_tick_ratio') is not None and tm.get('deadline_miss_ratio') is not None:
        checks['deadline_miss_vs_summary'] = abs(float(summary['fallback_tick_ratio']) - tm['deadline_miss_ratio'])
    if row.get('gpu_usage_recomputed') is not None and num(summary.get('gpu_busy_ratio')) is not None:
        checks['gpu_usage_summary_minus_recomputed'] = float(summary['gpu_busy_ratio']) - row['gpu_usage_recomputed']
    if v3.get('p_both') is not None and dm['p_both'] is not None:
        checks['p_both_vs_summary'] = abs(float(v3['p_both']) - dm['p_both'])
    row['checks'] = json.dumps(checks, sort_keys=True)
    if realized:
        from framelease_v4.arms import realized as RZ
        lp = agent_cfg.get('lease_params_path')
        try:
            rz = RZ.realized_validity(run_dir, lease_params_path=lp if lp and Path(lp).is_file() else None)
        except Exception as e:  # noqa: BLE001  analysis must not stop on one broken run
            rz = {'available': False, 'reason': f'{type(e).__name__}: {e}'}
        for k in ('available', 'conflict_plans', 'misses', 'r_cond', 'v0_plans', 'r_cond_excl_v0',
                  'realized_invalid_ticks', 'realized_invalid_tick_ratio', 'log_censored_plans'):
            # keys that realized.py already prefixes keep their name (amendment A2: they were prefixed twice, so
            # arm_summary and d1_summary read None for the executed-invalid tick ratio)
            row[k if k.startswith('realized_') else f'realized_{k}'] = rz.get(k)
    return row


# ============================================================================================ per arm

def arm_summary(rows):
    """Per arm (valid official records only): means over routes; pooled ratios where a pooled count exists."""
    by = {}
    for r in rows:
        if r.get('valid_record'):
            by.setdefault(r.get('arm') or '?', []).append(r)
    out = []
    for arm, rs in sorted(by.items()):
        def mean(key):
            v = [r[key] for r in rs if r.get(key) is not None]
            return float(np.mean(v)) if v else None
        km = sum(r.get('km_driven') or 0.0 for r in rs)
        coll = sum(r.get('collisions_total') or 0 for r in rs)
        ticks = sum(r.get('ticks') or 0 for r in rs)
        miss = sum(r.get('fallback_ticks') or 0 for r in rs)
        se = sum(r.get('shield_epochs') or 0 for r in rs)
        both = sum((r.get('p_both') or 0.0) * (r.get('shield_epochs') or 0) for r in rs)
        out.append({'arm': arm, 'routes': len(rs), 'driving_score': mean('driving_score'),
                    'route_completion': mean('route_completion'), 'success_rate': mean('success'),
                    'infraction_penalty': mean('infraction_penalty'),
                    'collisions_per_km_pooled': coll / max(km, 0.001) if rs else None,
                    'gpu_usage': mean('gpu_usage'), 'deadline_miss_ratio': mean('deadline_miss_ratio'),
                    'deadline_miss_ratio_pooled': (miss / ticks) if ticks else None,
                    'deadline_miss_ratio_after_first_commit': mean('deadline_miss_ratio_after_first_commit'),
                    'fallback_episodes': mean('fallback_episodes'), 'action_age_p50_s': mean('action_age_p50_s'),
                    'action_age_mean_s': mean('action_age_mean_s'), 'p_both_pooled': (both / se) if se else None,
                    'refresh_rate_hz': mean('refresh_rate_hz'), 'committed_depth_mean': mean('committed_depth_mean'),
                    'realized_invalid_tick_ratio': mean('realized_invalid_tick_ratio')})
    return out


def find_runs(root):
    return sorted({p.parent.parent for p in Path(root).rglob('metrics/result.json')})


def write_csv(path, rows):
    if not rows:
        return
    cols = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: ('' if r.get(k) is None else r.get(k)) for k in cols})


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--runs-root', type=Path, required=True)
    p.add_argument('--out', type=Path, help='per-run CSV')
    p.add_argument('--arm-summary', type=Path, help='per-arm CSV')
    p.add_argument('--json', type=Path, help='per-run + per-arm JSON')
    p.add_argument('--realized', action='store_true', help='realized validity from the actor log (slower)')
    args = p.parse_args(argv)
    rows = [r for r in (run_metrics(d, args.realized) for d in find_runs(args.runs_root)) if r is not None]
    arms = arm_summary(rows)
    if args.out:
        write_csv(args.out, rows)
    if args.arm_summary:
        write_csv(args.arm_summary, arms)
    if args.json:
        Path(args.json).write_text(json.dumps({'runs': rows, 'arms': arms}, indent=1, sort_keys=True, default=str))
    hdr = f'{"arm":<26} {"n":>3} {"DS":>6} {"RC":>6} {"SR":>5} {"GPU":>5} {"DMR":>5} {"age50":>6} {"Pboth":>6}'
    print(hdr)

    def f(v, d=1, scale=1.0):
        return '-' if v is None else f'{v * scale:.{d}f}'
    for a in arms:
        print(f'{a["arm"]:<26} {a["routes"]:>3} {f(a["driving_score"]):>6} {f(a["route_completion"]):>6} '
              f'{f(a["success_rate"], 2):>5} {f(a["gpu_usage"], 2):>5} {f(a["deadline_miss_ratio"], 2):>5} '
              f'{f(a["action_age_p50_s"], 2):>6} {f(a["p_both_pooled"], 2):>6}')
    print(f'{len(rows)} runs')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
