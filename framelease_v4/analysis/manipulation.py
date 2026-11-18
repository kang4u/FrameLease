"""Manipulation checks of the P7 aggregator (R-3; framelease_v4/PROTOCOL.md Sec. 9.7, reported, not tested; GAP_AUDIT
Sec. 3.7 'R-3') and the background-load check. CPU only; reads run directories; nothing here excludes a run.

Per run (every run with a selected record, test routes included: these are job health, timing and configuration,
which Sec. 9.11 allows before the analysis freeze):
  fast_prefix_check     framelease_v4/protocol/check_smoke.c_fast_prefix (final stage, validated, every option active,
                        SDPA calls > 0)
  charged_prefix_check  the run's charged prefix p50 / kappa within [0.35, 0.60] s: PASS, else FLAG
  bg_load_status        the background-load check: the charged prefix p50 against the idle band kappa x [0.416,
                        0.426] s, the pilot range that framelease_v4/PROTOCOL.md Sec. 9.7 registers ("Charged prefix.
                        The p50 of every run lies within kappa x [0.35, 0.60] s; the pilot measured 0.416-0.426 s at
                        kappa 1.0. Deviations are flagged."; IDLE_BAND_SOURCE). The band was registered before P1;
                        the P1 ref runs of 12:29-13:22 Beijing time on 2026-11-11, measured with no background load
                        (p50 0.416-0.422 s; outputs/framelease_v4/validity_notes/background_load_20261111.md), lie
                        inside it. Status 'within', 'above' (CPU load inflates the measured CUDA time of the prefix) or
                        'below', edges included in 'within';
                        bg_load_excess_s = p50 - the band edge it passes (0 within). Reported per run and per arm; it
                        does not exclude a run (Sec. 9.7 reports manipulation checks, it does not test them)
  config_check          the configuration the run recorded equals the registered one: check_smoke.c_config (launcher
                        arm, route, kappa, seed, policy parameters incl. the utility name, envelope sha256, fast-prefix
                        options, pinned sha256), the shield depth limit 10 (arms with a lease; recorded at least once),
                        and for runs after the tuning (phases other than P1-0 / P1) the frozen values: L* (or the
                        fl_risk point) envelope, the utility of d*, A*, theta* and A_hb*, the Q-network family (label)
                        and the RL freeze's d*. PASS, FAIL, or UNCHECKED (a post-tuning run read without the tuning
                        freeze). Reported, never an exclusion (Sec. 9.7 'reported, not tested'): the exclusions are the
                        Sec. 9.1 ones the aggregator applies separately, a run that does not match its own job line
                        and pins (check_smoke.c_config: code_mismatch) and a run without a protocol arm (label_problem:
                        a run that cannot be attributed to an arm cannot enter any contrast). A frozen value that
                        differs from the freeze while the run matches its job line is a job-file defect of the whole
                        arm, which this check reports for the analysis to judge
  job_release_by_depth  {final depth: median over finished jobs of (release of the last step - job start)} (the job
                        durations of the kappa-scaling check); withheld in the health-only rows of the arms with a lease
                        (Sec. 9.11: their final depths are the utility's choices, an outcome)
Per run, outcome-dependent (withheld for health-only rows, Sec. 9.11):
  predicted_expiry_fallback  v2 rule max(0, 2L + 0.05 - H) / L for Fixed Deep, Fast Only and Age-Only: L = mean job
                        release time (release of the last step - job start; the fast-prefix release time), H = the
                        validity horizon (max_age_s; Age-Only: min(A, H_bar)); observed = expired ticks from the first
                        commit on / those ticks; expiry_fallback_flag when |observed - predicted| > 0.05.
                        v4 interpretation: L is the mean over every finished job with at least one step, whereas the
                        v2 rule (framelease_v2/closed_loop_timing.py) uses complete jobs only (final depth = target
                        depth); an a_det^d job (Age-Only with the utility of d*) stops below the target depth by
                        design, so the v2 restriction would drop all of its jobs
Across runs (manipulation_summary):
  per protocol arm and kappa: fast prefix, charged prefix, background load and configuration counts, the prefix p50 /
  kappa range; predicted vs observed expiry fallback; kappa scaling (job_release_by_depth at kappa k against k x the
  kappa-1.0 run of the same arm, route and seed, on common depths: ratio median, share outside 1 +- 0.10, flag when
  the median is outside); P_both of fl_full and fl_heuristic on their common routes (Sec. 5.8, descriptive). The
  outcome-dependent parts use non-health-only rows only.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v4.analysis import extra_metrics as XM  # noqa: E402
from framelease_v4.arms import metrics_v4 as MV  # noqa: E402
from framelease_v4.protocol import check_smoke as CS  # noqa: E402

CHARGED_PREFIX_BAND_S = (0.35, 0.60)       # PROTOCOL Sec. 9.7, x kappa
IDLE_PREFIX_BAND_S = (0.416, 0.426)        # background-load check, x kappa: the pilot range of PROTOCOL Sec. 9.7
IDLE_BAND_SOURCE = ('framelease_v4/PROTOCOL.md Sec. 9.7, "Charged prefix. The p50 of every run lies within kappa x '
                    '[0.35, 0.60] s; the pilot measured 0.416-0.426 s at kappa 1.0. Deviations are flagged." '
                    '(registered before P1; the P1 ref runs of 12:29-13:22 Beijing time, 2026-11-11, no background '
                    'load, prefix p50 0.416-0.422 s, lie inside it: '
                    'outputs/framelease_v4/validity_notes/background_load_20261111.md)')
EXPIRY_RULE_ARMS = ('fixed_deep', 'fast_only', 'age_only')
EXPIRY_FLAG = 0.05                         # 5 percentage points (Sec. 9.7)
FRAME_S = 0.05                             # the v2 rule's one-frame term
KAPPA_TOL = 0.10                           # Sec. 9.7 kappa scaling +-10%
TUNING_PHASES = ('P1-0', 'P1')             # runs before the tuning freeze: no frozen values to compare


# ============================================================================================ per run

def prefix_checks(prefix_p50_s, kappa):
    """Charged-prefix band (Sec. 9.7) and background-load check of one run's charged prefix p50 (module docstring)."""
    out = {'prefix_p50_per_kappa_s': None, 'charged_prefix_check': None, 'bg_load_status': None,
           'bg_load_excess_s': None}
    if prefix_p50_s is None or not kappa:
        return out
    per = float(prefix_p50_s) / float(kappa)
    lo, hi = CHARGED_PREFIX_BAND_S
    blo, bhi = IDLE_PREFIX_BAND_S
    status = 'above' if per > bhi else 'below' if per < blo else 'within'
    edge = {'above': bhi, 'below': blo, 'within': per}[status]
    out.update(prefix_p50_per_kappa_s=per, charged_prefix_check='PASS' if lo <= per <= hi else 'FLAG',
               bg_load_status=status, bg_load_excess_s=float(kappa) * (per - edge))
    return out


def depth_limit_problems(cfg):
    """The shield depth limit 10 (arms with a lease; framelease_v4/arms/arms_v4.SHIELD_MAX_DEPTH) in every place the
    configuration records a depth limit, and recorded in at least one of them (a configuration without any is a
    problem: the limit is unverifiable)."""
    from framelease_v4.arms import arms_v4 as AV
    if XM.arm_kind(cfg) not in XM.LEASE_KINDS:
        return []
    v4 = cfg.get('v4') or {}
    where = {'v4.v3.resolved.policy_params': ((v4.get('v3') or {}).get('resolved') or {}).get('policy_params'),
             'v4.agent.policy_params': (v4.get('agent') or {}).get('policy_params'),
             'v4.agent.runtime': (v4.get('agent') or {}).get('runtime'),
             'agent_config.runtime': (cfg.get('agent_config') or {}).get('runtime')}
    found = {k: d['max_depth'] for k, d in where.items() if isinstance(d, dict) and 'max_depth' in d}
    if not found:
        return [f'no depth limit recorded (max_depth {AV.SHIELD_MAX_DEPTH} expected in one of {sorted(where)})']
    return [f'{k}.max_depth = {v!r} != {AV.SHIELD_MAX_DEPTH}' for k, v in found.items() if v != AV.SHIELD_MAX_DEPTH]


def freeze_problems(protocol_arm, cfg, tuning, rl=None):
    """The frozen values a post-tuning run must carry (module docstring). tuning: aggregate_v4.load_tuning_freeze
    (L_star_sha256, risk_sha256, d_star, utility, A_star, event_params); rl: load_rl_freeze or None."""
    v4 = cfg.get('v4') or {}
    pp = dict((v4.get('agent') or {}).get('policy_params') or {})
    env, util = cfg.get('envelope_sha256'), XM.run_utility(cfg)
    out = []

    def envelope(sha, what):
        if env != sha:
            out.append(f'envelope sha256 {env} != {what} {sha}')

    def params(want, what):
        out.extend(f'policy parameter {k} {pp.get(k)!r} != {what} {v!r}' for k, v in (want or {}).items()
                   if pp.get(k) != v)

    if protocol_arm in ('fl_heuristic', 'fl_global_shield', 'fl_risk'):
        if protocol_arm == 'fl_risk':
            envelope(tuning.get('risk_sha256'), 'the fl_risk point')
        else:
            envelope(tuning.get('L_star_sha256'), 'L*')
        if util != tuning.get('utility'):
            out.append(f'utility {util!r} != the utility of d* {tuning.get("utility")!r}')
    elif protocol_arm in ('fl_full', 'fl_bandit', 'fl_fqi_nolease'):
        envelope(tuning.get('L_star_sha256'), 'L*')
        if rl is not None and rl.get('d_star') is not None and tuning.get('d_star') is not None \
                and int(rl['d_star']) != int(tuning['d_star']):
            out.append(f'RL freeze d* {rl["d_star"]} != tuning freeze d* {tuning["d_star"]}')
    elif protocol_arm == 'fl_behaviour':
        envelope(tuning.get('L_star_sha256'), 'L*')
        if XM.utility_depth(util) != tuning.get('d_star'):
            out.append(f'behaviour base depth {XM.utility_depth(util)} != d* {tuning.get("d_star")}')
    elif protocol_arm == 'age_only':
        params(tuning.get('A_star'), 'A* / d*')
    elif protocol_arm == 'event_triggered':
        params(tuning.get('event_params'), 'theta* / A_hb*')
    return out


def config_result(job, run, cfg, protocol_arm, refs=None):
    """(status, detail) of the configuration check (module docstring)."""
    refs = refs or {}
    c = CS.c_config(job, Path(run))
    problems = [] if c['status'] == CS.PASS else [c['detail']]
    problems += depth_limit_problems(cfg)
    unchecked = False
    if job.get('phase') not in TUNING_PHASES:
        if refs.get('tuning') is None:
            unchecked = True
        else:
            problems += freeze_problems(protocol_arm, cfg, refs['tuning'], refs.get('rl'))
    if problems:
        return 'FAIL', '; '.join(problems)
    if unchecked:
        return 'UNCHECKED', f'phase {job.get("phase")!r} run read without the tuning freeze: frozen values unchecked'
    return 'PASS', c['detail']


def job_release_times(jobs):
    """[(final depth, release of the last step - job start)] of the finished jobs with at least one step."""
    out = []
    for j in jobs:
        steps = j.get('steps') or []
        rel, start = (MV.num(steps[-1].get('release_s')) if steps else None), MV.num(j.get('start_s'))
        if rel is not None and start is not None:
            out.append((int(steps[-1]['depth']), rel - start))
    return out


def job_release_by_depth(jobs):
    """{final depth: median job release time} (the job durations of the kappa-scaling check)."""
    by = {}
    for d, t in job_release_times(jobs):
        by.setdefault(d, []).append(t)
    return {str(d): statistics.median(v) for d, v in sorted(by.items())}


def expiry_check(cfg, jobs, observed):
    """(predicted, observed, deviation, flag) of the v2 predicted-expiry rule (module docstring); Nones for an arm the
    rule does not cover or a run without a finished job."""
    none = {'predicted_expiry_fallback': None, 'observed_expiry_fallback': None, 'expiry_fallback_dev': None,
            'expiry_fallback_flag': None}
    if cfg.get('v4_arm') not in EXPIRY_RULE_ARMS:
        return none
    times = [t for _, t in job_release_times(jobs)]
    if not times:
        return none
    L = sum(times) / len(times)
    if XM.arm_kind(cfg) == 'age':
        lease = (((cfg.get('v4') or {}).get('v3') or {}).get('resolved') or {}).get('lease') or {}
        a = MV.num((((cfg.get('v4') or {}).get('agent') or {}).get('policy_params') or {}).get('age_lease_s'))
        h = None if a is None else min(a, MV.num(lease.get('h_bar_s')) or a)
    else:
        h = MV.num(((cfg.get('agent_config') or {}).get('runtime') or {}).get('max_age_s'))
    if h is None:
        return none
    pred = max(0.0, 2.0 * L + FRAME_S - h) / L if L > 0 else None
    if pred is None or observed is None:
        return {**none, 'predicted_expiry_fallback': pred}
    dev = float(observed) - pred
    return {'predicted_expiry_fallback': pred, 'observed_expiry_fallback': float(observed), 'expiry_fallback_dev': dev,
            'expiry_fallback_flag': abs(dev) > EXPIRY_FLAG}


def run_checks(job, run, logs, prefix_p50_s, observed_expiry, protocol_arm, refs=None, health_only=False):
    """The per-run checks of the module docstring. logs: extra_metrics.load_logs(run); prefix_p50_s: the charged prefix
    p50 (extra_metrics.timing_metrics prefix_quantum_s_p50); observed_expiry: expired ticks from the first commit on /
    those ticks (extra_metrics.dmr_metrics); health_only: the outcome-dependent expiry rule, and the job release times
    by final depth of an arm with a lease, are withheld (Sec. 9.11)."""
    cfg = logs['cfg']
    fp = CS.c_fast_prefix(Path(run))
    out = {'fast_prefix_check': fp['status'], 'fast_prefix_detail': fp['detail']}
    out.update(prefix_checks(prefix_p50_s, MV.num(cfg.get('kappa'))))
    out['config_check'], out['config_detail'] = config_result(job, run, cfg, protocol_arm, refs)
    if not (health_only and XM.arm_kind(cfg) in XM.LEASE_KINDS):
        out['job_release_by_depth'] = json.dumps(job_release_by_depth(logs['jobs']), sort_keys=True)
    if not health_only:
        out.update(expiry_check(cfg, logs['jobs'], observed_expiry))
    return out


# ============================================================================================ across runs

def _median(v):
    return statistics.median(v) if v else None


def _count(rows, key, value):
    return sum(1 for r in rows if r.get(key) == value)


def per_arm_health(rows):
    """{'<protocol arm> k<kappa>': counts and the prefix p50 / kappa range} over the given rows (module docstring)."""
    by = {}
    for r in rows:
        by.setdefault(f'{r.get("protocol_arm")} k{r.get("kappa")}', []).append(r)
    out = {}
    for name, rs in sorted(by.items()):
        per = [r['prefix_p50_per_kappa_s'] for r in rs if r.get('prefix_p50_per_kappa_s') is not None]
        out[name] = {'runs': len(rs), 'fast_prefix_not_pass': sum(1 for r in rs if r.get('fast_prefix_check') != CS.PASS),
                     'charged_prefix_flag': _count(rs, 'charged_prefix_check', 'FLAG'),
                     'bg_load': {s: _count(rs, 'bg_load_status', s) for s in ('within', 'above', 'below')},
                     'prefix_p50_per_kappa_s': {'min': min(per) if per else None, 'median': _median(per),
                                                'max': max(per) if per else None},
                     'config': {s: _count(rs, 'config_check', s) for s in ('PASS', 'FAIL', 'UNCHECKED')}}
    return out


def run_flags(rows):
    """[{job, protocol_arm, kappa, check, value}] of every per-run check that is not clean (reported, not tested)."""
    out = []
    for r in rows:
        base = {'job': r.get('job'), 'protocol_arm': r.get('protocol_arm'), 'kappa': r.get('kappa'),
                'run_created_utc': r.get('run_created_utc')}
        if r.get('fast_prefix_check') not in (None, CS.PASS):
            out.append({**base, 'check': 'fast_prefix', 'value': r.get('fast_prefix_detail')})
        if r.get('charged_prefix_check') == 'FLAG':
            out.append({**base, 'check': 'charged_prefix', 'value': r.get('prefix_p50_per_kappa_s')})
        if r.get('bg_load_status') not in (None, 'within'):
            out.append({**base, 'check': f'bg_load_{r["bg_load_status"]}', 'value': r.get('prefix_p50_per_kappa_s')})
        if r.get('config_check') in ('FAIL', 'UNCHECKED'):
            out.append({**base, 'check': f'config_{r["config_check"]}', 'value': r.get('config_detail')})
        if r.get('expiry_fallback_flag') is True:
            out.append({**base, 'check': 'predicted_expiry_fallback', 'value': r.get('expiry_fallback_dev')})
    return out


def expiry_summary(rows):
    """Per protocol arm: runs, mean predicted and observed expiry fallback, flagged runs (rows with a prediction)."""
    by = {}
    for r in rows:
        if r.get('predicted_expiry_fallback') is not None and r.get('observed_expiry_fallback') is not None:
            by.setdefault(f'{r.get("protocol_arm")} k{r.get("kappa")}', []).append(r)
    return {name: {'runs': len(rs),
                   'predicted_mean': sum(r['predicted_expiry_fallback'] for r in rs) / len(rs),
                   'observed_mean': sum(r['observed_expiry_fallback'] for r in rs) / len(rs),
                   'flagged_runs': [r['job'] for r in rs if r.get('expiry_fallback_flag')]}
            for name, rs in sorted(by.items())}


def kappa_scaling(rows):
    """Per protocol arm and kappa != 1.0: job_release_by_depth against kappa x the kappa-1.0 run of the same arm,
    route and seed, on common depths (module docstring)."""
    base = {(r.get('protocol_arm'), r.get('route_id'), r.get('seed')): r for r in rows
            if r.get('kappa') is not None and float(r['kappa']) == 1.0 and r.get('job_release_by_depth')}
    ratios = {}
    for r in rows:
        if r.get('kappa') is None or float(r['kappa']) == 1.0 or not r.get('job_release_by_depth'):
            continue
        b = base.get((r.get('protocol_arm'), r.get('route_id'), r.get('seed')))
        if b is None:
            continue
        k = float(r['kappa'])
        dk, d1 = json.loads(r['job_release_by_depth']), json.loads(b['job_release_by_depth'])
        got = [dk[d] / (k * d1[d]) for d in dk if d in d1 and d1[d] > 0]
        if got:
            ratios.setdefault(f'{r.get("protocol_arm")} k{k}', []).append((r.get('route_id'), got))
    out = {}
    for name, per in sorted(ratios.items()):
        flat = [x for _, v in per for x in v]
        med = _median(flat)
        out[name] = {'routes': len(per), 'pairs': len(flat), 'ratio_median': med, 'ratio_min': min(flat),
                     'ratio_max': max(flat),
                     'share_outside_tol': sum(1 for x in flat if abs(x - 1.0) > KAPPA_TOL) / len(flat),
                     'flag': abs(med - 1.0) > KAPPA_TOL}
    return out


def p_both_summary(rows, arms=('fl_full', 'fl_heuristic')):
    """P_both of the two arms that share the shield on their common (route, seed) per kappa (Sec. 9.7, descriptive):
    route means, pooled over shield epochs, mean paired difference arms[0] - arms[1]."""
    by = {}
    for r in rows:
        if r.get('protocol_arm') in arms and r.get('p_both') is not None and r.get('analysis_use'):
            by.setdefault(float(r['kappa']), {}).setdefault(r['protocol_arm'], {})[(r['route_id'], r['seed'])] = r
    out = {}
    for k, per in sorted(by.items()):
        if len(per) < 2:
            continue
        common = sorted(set(per[arms[0]]) & set(per[arms[1]]))
        if not common:
            continue
        res = {'routes': len(common)}
        for a in arms:
            rs = [per[a][c] for c in common]
            se = sum(int(r.get('shield_epochs') or 0) for r in rs)
            res[a] = {'mean': sum(float(r['p_both']) for r in rs) / len(rs),
                      'pooled': (sum(float(r['p_both']) * int(r.get('shield_epochs') or 0) for r in rs) / se)
                      if se else None}
        res['mean_difference'] = res[arms[0]]['mean'] - res[arms[1]]['mean']
        out[f'k{k}'] = res
    return out


def manipulation_summary(rows):
    """The across-run part of R-3 (module docstring) over the rows with a selected run; the outcome-dependent parts
    use the rows that are not health-only."""
    ok = [r for r in rows if r.get('outcome') == 'ok' and r.get('selected_run')]
    guarded = [r for r in ok if not r.get('health_only')]
    return {'status': 'reported (PROTOCOL Sec. 9.7: not tested, no run excluded)',
            'charged_prefix_band_s_per_kappa': list(CHARGED_PREFIX_BAND_S),
            'idle_prefix_band_s_per_kappa': list(IDLE_PREFIX_BAND_S), 'idle_band_source': IDLE_BAND_SOURCE,
            'runs': len(ok), 'per_arm': per_arm_health(ok), 'flags': run_flags(ok),
            'predicted_expiry': expiry_summary(guarded), 'kappa_scaling': kappa_scaling(guarded),
            'p_both_shared_shield': p_both_summary(guarded),
            'withheld_health_only_runs': len(ok) - len(guarded)}


__all__ = ['CHARGED_PREFIX_BAND_S', 'IDLE_PREFIX_BAND_S', 'IDLE_BAND_SOURCE', 'prefix_checks', 'depth_limit_problems',
           'freeze_problems', 'config_result', 'job_release_by_depth', 'expiry_check', 'run_checks', 'per_arm_health',
           'run_flags', 'expiry_summary', 'kappa_scaling', 'p_both_summary', 'manipulation_summary']
