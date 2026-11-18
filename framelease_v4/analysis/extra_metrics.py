"""Per-run metrics of the P7 aggregator that framelease_v4/arms/metrics_v4.py does not compute (framelease_v4/PROTOCOL.md
Secs. 6.1-6.4, 7.4, 7.6; GAP_AUDIT Sec. 3.7 'R-1, metrics'). Read-only on the run directory; CPU only.

Definitions (every value is recomputed from the run's own logs; summary.json is used only for cross-checks; a step that
fails on a malformed record leaves only its own columns empty, extra_metrics(errors=...)):

Driving (Sec. 6.1; metrics_v4 counts per infraction type and km driven)
  infractions_penalized   collisions (pedestrian, vehicle, layout), red light, stop, outside-route-lanes events,
                          scenario timeouts, yield to emergency vehicle (min-speed records excluded: Bench2Drive appends
                          one at every 5% of progress with no penalty)
  infractions_per_km      infractions_penalized / max(route length x RC / 100, 0.001 km)
  route_ending_events     deviation, blocked, route timeout (reported separately, not in infractions_per_km)
Compute and timing (Sec. 6.2)
  dmr                     ticks from the first commit on without a valid committed action (fallback: expired,
                          re-anchoring failed, none) / those ticks; the arm's own validity rule is the deadline of its
                          committed action (lease, or capture + max_age_s)
  expired_ratio_after_first_commit   the expired-only variant (the all-ticks DMR is metrics_v4 deadline_miss_ratio)
  cuda_s_per_s            gpu_usage / kappa
Validity (Sec. 6.3; framelease_v4/arms/realized.py realized_validity(with_candidates=True); runs with a lease only)
  V_suf                   clip(V - T_c, 0, H_bar); a plan without a realized conflict has V = T_pred, so V_suf = H_bar;
                          plans whose window passes the end of the actor log (log-censored) and plans without a pose
                          are excluded
  lease_utilization       mean over committed plans with V_suf > 0 of min(H, V_suf) / V_suf (H = deadline - t_k)
  premature_expiry_plans  committed plans whose deadline D passed before the next accepted commit (the end of the run
                          for the last one) while the plan was still valid there (V_suf > H, i.e. t_k + V_suf > D);
                          premature_expiry_ratio = / evaluated plans; premature_expiry_lost_s = the sum of
                          min(next commit, t_k + V_suf) - D over them
Scheduler (Sec. 6.4; decisions.jsonl and the commit / reject / shield_violation events)
  choice_epochs           shield decision epochs with |A_feas| = 2 (the epochs where the utility chooses)
  deviation_rate          choice epochs whose action differs from a_det^{d*}(depth) / choice epochs
  bypass_rate             choice epochs with a Q-network bypass (features v4_bypass: slack, disabled, overrun,
                          nonfinite) / choice epochs (None for a utility without a Q-network)
  lease_committed_p50_s   median lease H of the accepted commits
  budget_overruns         offers whose commit came later than the bound the last admitted decision promised
                          (commit / reject events, budget.overrun), of budget_checked
  shield_violations       shield_violation events: an expiry the last admitted decision promised to avoid
  gate_rejects_by_reason  commit-gate rejects by reason ('invalid:<why>' counted as 'invalid', as CommitGate does)
Table II-B timings (Sec. 7.6), p50 / p99
  qnet_s                  Q-network wall time of the network calls (features v4_qnet_s)
  decision_wall_s         shield + decision CPU time (decision rows); lease_wall_s: lease CPU time per candidate
  prefix_quantum_s        charged prefix duration (job_start events: kappa x measured CUDA time); prefix_measured_s
                          its measured CUDA time; step_quantum_s: charged flow-step duration (jobs.jsonl steps)
  switching_latency_s     charged CPU time between the last boundary of a job and the prefix launch of the next job,
                          for the jobs that start at the end of the previous one (REFRESH / end of job; a wait for a
                          new frame is not switching): (end_s - last release) + the next job's start overhead
  cancelled_gpu_share     GPU-busy time of the finished jobs that leads to no committed candidate (the prefix and
                          steps of a job without a commit, the steps after a job's deepest commit) / their GPU-busy time.
                          v4 interpretation: every step up to a job's deepest commit counts as used, including the
                          shallower steps whose own candidate was rejected or never offered (they are the prefix of
                          the committed one)
  validation_s            release-to-commit time of every offered candidate (commit and reject events)
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v4.arms import metrics_v4 as MV  # noqa: E402

PENALIZED_TYPES = ('collisions_pedestrian', 'collisions_vehicle', 'collisions_layout', 'red_light', 'stop_infraction',
                   'outside_route_lanes', 'scenario_timeouts', 'yield_emergency_vehicle_infractions')
ROUTE_ENDING_TYPES = ('route_dev', 'vehicle_blocked', 'route_timeout')
EXCLUDED_TYPES = ('min_speed_infractions',)
LEASE_KINDS = ('shield', 'age')            # arm kinds with a lease deadline, the shield and the commit-time margin
QS = (0.5, 0.99)
EPS = 1e-9
MIN_KM = 0.001                             # leaderboard floor of km driven (Sec. 6.1)
FIRST_COMMIT_EPS_S = 1e-6                  # metrics_v4.tick_metrics' tolerance for the first-commit tick
STEP_ERRORS = (KeyError, TypeError, ValueError, ZeroDivisionError, IndexError, AttributeError)   # a malformed record


def load_logs(run_dir):
    """{'cfg', 'summary', 'ticks', 'jobs', 'events', 'decisions'} of one run directory (missing files: empty)."""
    run_dir = Path(run_dir)
    fl = run_dir / 'raw' / 'agent' / 'framelease'
    result = MV.read_json(run_dir / 'metrics' / 'result.json') or {}
    return {'cfg': MV.read_json(run_dir / 'config.json') or {},
            'summary': result.get('agent_summary') or MV.read_json(fl / 'summary.json') or {},
            'ticks': MV.read_jsonl(fl / 'ticks.jsonl'), 'jobs': MV.read_jsonl(fl / 'jobs.jsonl'),
            'events': MV.read_jsonl(fl / 'events.jsonl'), 'decisions': MV.read_jsonl(fl / 'decisions.jsonl')}


def arm_kind(cfg):
    """The arm kind a run recorded (config.json kind / v4.kind: v2_rule, event, age, shield)."""
    return cfg.get('kind') or (cfg.get('v4') or {}).get('kind')


def qstats(values, name):
    """{name_p50, name_p99} (numpy linear quantiles, metrics_v4.quantiles) and name_n."""
    q = MV.quantiles(values, QS)
    return {f'{name}_p50': q['p50'], f'{name}_p99': q['p99'], f'{name}_n': q['n']}


def guarded(errors, name, fn, /, *args, **kw):
    """fn(*args, **kw) (kw may itself name 'errors'). With errors (a list), an exception of STEP_ERRORS (a malformed
    log record) is appended to it as (name, 'Type: message') and None is returned, so a failed step leaves only its own
    columns empty (Sec. 9.8: nothing is imputed, and no other metric of the run is lost); errors None lets it
    propagate."""
    if errors is None:
        return fn(*args, **kw)
    try:
        return fn(*args, **kw)
    except STEP_ERRORS as e:
        errors.append((name, f'{type(e).__name__}: {e}'))
        return None


# ============================================================================================ Sec. 6.1, 6.2

def infraction_metrics(row):
    """infractions_penalized, infractions_per_km and route_ending_events from a metrics_v4 row (its inf_<type> counts
    and km_driven); None without a valid official record."""
    if not row or not row.get('valid_record'):
        return {'infractions_penalized': None, 'infractions_per_km': None, 'route_ending_events': None}
    pen = sum(int(row.get(f'inf_{t}') or 0) for t in PENALIZED_TYPES)
    km = row.get('km_driven')
    return {'infractions_penalized': pen,
            'infractions_per_km': None if km is None else pen / max(float(km), MIN_KM),
            'route_ending_events': sum(int(row.get(f'inf_{t}') or 0) for t in ROUTE_ENDING_TYPES)}


def first_commit_s(events):
    """Commit time of the first accepted commit (commit events), None without one (metrics_v4's rule)."""
    return min((float(e['commit_s']) for e in events if e.get('kind') == 'commit' and e.get('commit_s') is not None),
               default=None)


def dmr_metrics(ticks, events, gpu_usage=None, kappa=None):
    """dmr (from the first commit on), expired_ratio_after_first_commit and cuda_s_per_s (Sec. 6.2)."""
    fc = first_commit_s(events)
    after = [t for t in ticks if fc is not None and float(t['sim_s']) + FIRST_COMMIT_EPS_S >= fc]
    n = len(after)
    miss = sum(1 for t in after if t.get('mode') != 'track')
    expired = sum(1 for t in after if t.get('mode') != 'track' and t.get('fallback_reason') == 'expired')
    return {'dmr': miss / n if n else None, 'dmr_ticks': n,
            'expired_ratio_after_first_commit': expired / n if n else None,
            'cuda_s_per_s': (float(gpu_usage) / float(kappa)) if gpu_usage is not None and kappa else None}


# ============================================================================================ Sec. 6.3

def run_end_s(ticks):
    """End of the run's control timeline: the last tick + one frame (metrics_v4's span), None without ticks."""
    return (float(ticks[-1]['sim_s']) + MV.FRAME_DT_S) if ticks else None


def accepted_commits(events):
    """Accepted commits (commit events) in commit order: [{'key': (job_id, depth), 'capture_s', 'commit_s',
    'deadline_s', 'lease_s'}] (the commits of a job still running at the end are in events.jsonl only)."""
    out = []
    for i, e in enumerate(events):
        if e.get('kind') != 'commit' or e.get('commit_s') is None:
            continue
        out.append({'key': (int(e['job_id']), int(e['depth'])), 'order': i, 'capture_s': MV.num(e.get('capture_s')),
                    'commit_s': float(e['commit_s']), 'deadline_s': MV.num(e.get('deadline_s')),
                    'lease_s': MV.num(e.get('lease_s'))})
    return sorted(out, key=lambda c: (c['commit_s'], c['order']))


def lease_validity_metrics(rz, commits, end_s):
    """lease_utilization and premature expiry (Sec. 6.3; module docstring) from realized_validity(...,
    with_candidates=True) and the accepted commits in commit order (accepted_commits)."""
    out = {'lease_plans_evaluated': None, 'lease_utilization': None, 'premature_expiry_plans': None,
           'premature_expiry_ratio': None, 'premature_expiry_lost_s': None}
    if not rz or not rz.get('available') or 'candidates' not in rz:
        return out
    h_bar = max(0.0, float(rz['t_pred_s']) - float(rz['t_c_s']))
    cands = rz['candidates']
    util, evaluated, premature, lost = [], 0, 0, 0.0
    for i, c in enumerate(commits):
        r = cands.get(f'{c["key"][0]}:{c["key"][1]}')
        if r is None or r.get('status') != 'ok' or r.get('log_censored'):
            continue
        v_suf = float(r['V_suf']) if r.get('conflict') else h_bar
        h = MV.num(r.get('lease_s'))
        if h is None:
            continue
        evaluated += 1
        if v_suf > 0:
            util.append(min(h, v_suf) / v_suf)
        succ = commits[i + 1]['commit_s'] if i + 1 < len(commits) else end_s
        dl = c['deadline_s'] if c['deadline_s'] is not None else c['capture_s'] + h
        valid_until = c['capture_s'] + v_suf
        if succ is not None and dl < succ - EPS and valid_until > dl + EPS:
            premature += 1
            lost += min(succ, valid_until) - dl
    out.update(lease_plans_evaluated=evaluated, lease_utilization=(sum(util) / len(util)) if util else None,
               premature_expiry_plans=premature, premature_expiry_ratio=(premature / evaluated) if evaluated else None,
               premature_expiry_lost_s=lost)
    return out


# ============================================================================================ Sec. 6.4

def utility_depth(name):
    """The a_det depth a utility name implies: 'heuristic' -> 10, v4_adet_d<d> -> d, a behaviour name -> its base
    depth; None otherwise (a Q-network name does not carry it)."""
    from framelease_v4.rl import behaviour as B
    if name in (None, ''):
        return None
    if name == 'heuristic':
        return B.MAX_DEPTH
    m = B.ADET_RE.match(str(name))
    if m:
        return int(m.group('d'))
    beh = B.parse_behaviour(name)
    return beh[2] if beh else None


def gate_reason(reason):
    """CommitGate's counting key of a reject reason ('invalid:<why>' -> 'invalid')."""
    reason = str(reason)
    return 'invalid' if reason.startswith('invalid') else reason


def scheduler_metrics(decisions, events, d_star=None):
    """The Sec. 6.4 scheduler outcomes (module docstring). d_star: the frozen a_det depth (None: deviation not
    computed)."""
    from framelease_v4.rl import behaviour as B
    choice = [d for d in decisions if d.get('p_both') is True]
    dev = None
    if d_star is not None:
        dev = sum(1 for d in choice
                  if d.get('action') != B.a_det_action((d.get('features') or {}).get('depth', d.get('depth')), d_star))
    qnet = any('v4_bypass' in (d.get('features') or {}) for d in decisions)
    bypass = Counter(str((d.get('features') or {}).get('v4_bypass')) for d in choice
                     if (d.get('features') or {}).get('v4_bypass') is not None)
    offers = [e for e in events if e.get('kind') in ('commit', 'reject')]
    budget = [e['budget'] for e in offers if isinstance(e.get('budget'), dict)]
    rejects = Counter(gate_reason(e.get('reason')) for e in events if e.get('kind') == 'reject')
    leases = [MV.num(e.get('lease_s')) for e in events if e.get('kind') == 'commit']
    n = len(choice)
    return {'choice_epochs': n, 'd_star_used': d_star, 'deviation_epochs': dev,
            'deviation_rate': (dev / n) if dev is not None and n else None,
            'bypass_epochs': sum(bypass.values()) if qnet else None,
            'bypass_rate': (sum(bypass.values()) / n) if qnet and n else None,
            'bypass_by_reason': json.dumps(dict(sorted(bypass.items()))) if qnet else None,
            'committed_plans': len(leases), 'lease_committed_p50_s': MV.quantiles(leases)['p50'],
            'budget_checked': len(budget), 'budget_overruns': sum(1 for b in budget if b.get('overrun')),
            'budget_overrun_ratio': (sum(1 for b in budget if b.get('overrun')) / len(budget)) if budget else None,
            'shield_violations': sum(1 for e in events if e.get('kind') == 'shield_violation'),
            'gate_rejects': sum(rejects.values()), 'gate_rejects_by_reason': json.dumps(dict(sorted(rejects.items())))}


# ============================================================================================ Table II-B

def switching_latencies(jobs, events):
    """Charged CPU time between the last boundary of a finished job and the prefix launch of the next job, for the
    jobs that start exactly when the previous one ended (module docstring)."""
    starts = {int(e['job_id']): e for e in events if e.get('kind') == 'job_start' and e.get('job_id') is not None}
    out = []
    for j in jobs:
        nxt = starts.get(int(j['job_id']) + 1)
        end = MV.num(j.get('end_s'))
        if nxt is None or end is None or abs(float(nxt['sim_s']) - end) > EPS:
            continue
        steps = j.get('steps') or []
        last = MV.num(steps[-1].get('release_s')) if steps else MV.num(j.get('prefix_end_s'))
        if last is not None:
            out.append(end - last + float(nxt.get('overhead_s') or 0.0))
    return out


def cancelled_gpu_work(jobs):
    """(cancelled GPU-busy s, GPU-busy s) of the finished jobs: the work that leads to no committed candidate."""
    total = cancelled = 0.0
    for j in jobs:
        pre = MV.num((j.get('prefix') or {}).get('timeline_cost_s')) or 0.0
        steps = [(int(s['depth']), MV.num(s.get('timeline_cost_s')) or 0.0) for s in j.get('steps') or []]
        work = pre + sum(c for _, c in steps)
        deepest = max((int(d) for d in j.get('committed_depths') or []), default=None)
        used = 0.0 if deepest is None else pre + sum(c for d, c in steps if d <= deepest)
        total += work
        cancelled += work - used
    return cancelled, total


def validation_times(events):
    """Release-to-commit time of every offered candidate (commit events; reject events carry details.commit_s)."""
    out = []
    for e in events:
        if e.get('kind') == 'commit':
            t = MV.num(e.get('commit_s'))
        elif e.get('kind') == 'reject':
            t = MV.num((e.get('details') or {}).get('commit_s'))
        else:
            continue
        rel = MV.num(e.get('release_s'))
        if t is not None and rel is not None:
            out.append(t - rel)
    return out


def timing_metrics(jobs, events, decisions):
    """The Table II-B timings (module docstring)."""
    feats = [d.get('features') or {} for d in decisions]
    steps = [s for j in jobs for s in j.get('steps') or []]
    starts = [e for e in events if e.get('kind') == 'job_start']
    out = {}
    out.update(qstats([MV.num(f.get('v4_qnet_s')) for f in feats if f.get('v4_qnet_s') is not None], 'qnet_s'))
    out.update(qstats([MV.num(d.get('decision_wall_s')) for d in decisions if d.get('decision_wall_s') is not None],
                      'decision_wall_s'))
    out.update(qstats([MV.num((s.get('validity') or {}).get('lease_wall_s')) for s in steps
                       if (s.get('validity') or {}).get('lease_wall_s') is not None], 'lease_wall_s'))
    out.update(qstats([MV.num(e.get('prefix_timeline_s')) for e in starts], 'prefix_quantum_s'))
    out['prefix_measured_s_p50'] = MV.quantiles([MV.num(e.get('prefix_cost_s')) for e in starts])['p50']
    out.update(qstats([MV.num(s.get('timeline_cost_s')) for s in steps], 'step_quantum_s'))
    out.update(qstats(switching_latencies(jobs, events), 'switching_latency_s'))
    cancelled, total = cancelled_gpu_work(jobs)
    out.update(cancelled_gpu_s=cancelled, cancelled_gpu_share=(cancelled / total) if total > 0 else None)
    out.update(qstats(validation_times(events), 'validation_s'))
    return out


# ============================================================================================ one run

def run_utility(cfg):
    """The utility name a run recorded (v4.agent.policy_params.utility, else v4.utility.name)."""
    v4 = cfg.get('v4') or {}
    pp = (v4.get('agent') or {}).get('policy_params') or {}
    return pp.get('utility') or (v4.get('utility') or {}).get('name')


def realized_candidates(run_dir, cfg):
    """realized_validity(with_candidates=True) with the run's lease parameter file (metrics_v4.run_metrics' call);
    an exception is returned as {'available': False, 'reason'} (one broken run never stops the aggregation)."""
    from framelease_v4.arms import realized as RZ
    lp = (cfg.get('agent_config') or {}).get('lease_params_path')
    try:
        return RZ.realized_validity(run_dir, lease_params_path=lp if lp and Path(lp).is_file() else None,
                                    with_candidates=True)
    except Exception as e:  # noqa: BLE001
        return {'available': False, 'reason': f'{type(e).__name__}: {e}'}


def summary_checks(x, summary):
    """{check: |recomputed - summary.json|} (numbers) or recomputed == summary (counts) for the values the runtime
    summary also reports; absent entries are skipped."""
    v3, v4 = summary.get('v3') or {}, summary.get('v4') or {}
    out = {}
    for mine, theirs in (('dmr', v4.get('deadline_miss_ratio_after_first_commit')),
                         ('expired_ratio_after_first_commit', v4.get('expired_ratio_after_first_commit')),
                         ('validation_s_p50', (v3.get('validation_s') or {}).get('p50')),
                         ('decision_wall_s_p50', (v3.get('decision_wall_s') or {}).get('p50')),
                         ('prefix_measured_s_p50', (summary.get('prefix_cost_s') or {}).get('p50'))):
        if x.get(mine) is not None and MV.num(theirs) is not None:
            out[f'{mine}_abs_diff'] = abs(float(x[mine]) - float(theirs))
    for mine, key in (('budget_checked', 'budget_checked'), ('budget_overruns', 'budget_overruns'),
                      ('shield_violations', 'shield_violations')):
        if v3.get(key) is not None:
            out[f'{mine}_equal'] = int(x.get(mine) or 0) == int(v3[key])
    if isinstance(v3.get('commit_gate'), dict):
        gate = {k: int(v) for k, v in v3['commit_gate'].items() if k != 'accepted'}
        out['gate_rejects_equal'] = gate == json.loads(x.get('gate_rejects_by_reason') or '{}')
    return out


def extra_metrics(run_dir, row, d_star=None, realized=True, logs=None, errors=None):
    """The metrics of the module docstring for one run directory. row: its metrics_v4.run_metrics row (counts, km,
    gpu_usage, kappa); d_star: the frozen a_det depth (None: the depth the run's own utility implies); realized: run
    the realized-validity pass with candidates (lease arms only); logs: load_logs(run_dir) if already read; errors: a
    list that collects the steps that failed on a malformed record (guarded: infraction_metrics, dmr_metrics,
    lease_validity_metrics, scheduler_metrics, timing_metrics, summary_checks), whose columns are then left out (None:
    an exception propagates)."""
    logs = load_logs(run_dir) if logs is None else logs
    cfg, row = logs['cfg'], row or {}
    kind = arm_kind(cfg)
    out = {'arm_kind': kind}

    def step(name, fn, *args, **kw):
        out.update(guarded(errors, name, fn, *args, **kw) or {})

    step('infraction_metrics', infraction_metrics, row)
    step('dmr_metrics', dmr_metrics, logs['ticks'], logs['events'], row.get('gpu_usage'), row.get('kappa'))
    rz = realized_candidates(run_dir, cfg) if realized and kind in LEASE_KINDS else None
    step('lease_validity_metrics', lambda: lease_validity_metrics(rz, accepted_commits(logs['events']),
                                                                  run_end_s(logs['ticks'])))
    if d_star is None:
        d_star, src = utility_depth(run_utility(cfg)), 'utility of the run'
    else:
        src = 'freeze'
    step('scheduler_metrics', scheduler_metrics, logs['decisions'], logs['events'],
         d_star if kind in LEASE_KINDS else None)
    out['d_star_source'] = src if kind in LEASE_KINDS and d_star is not None else None
    step('timing_metrics', timing_metrics, logs['jobs'], logs['events'], logs['decisions'])
    step('summary_checks', lambda: {'agg_checks': json.dumps(summary_checks(out, logs['summary']), sort_keys=True)})
    return out


__all__ = ['PENALIZED_TYPES', 'ROUTE_ENDING_TYPES', 'LEASE_KINDS', 'STEP_ERRORS', 'load_logs', 'arm_kind', 'guarded',
           'infraction_metrics', 'dmr_metrics', 'accepted_commits', 'lease_validity_metrics', 'scheduler_metrics',
           'timing_metrics', 'extra_metrics']
