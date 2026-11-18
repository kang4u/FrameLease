"""Round-2 review of A11: independent recount of the P1 development numbers that A11, F1_RULE.md and RUNBOOK state.

Standard library only; no code of f1_class_report.py or verify_table1_extra.py is imported. Read only; writes --out.

  taskset -c 12-15 nice -n 19 ionice -c 3 <wrapper> python -I -B r2_numbers.py \
      --snap outputs/framelease_v4/build/R7B/dev/verify_p1_snap_2203_d \
      --rundirs /tmp/A10A11/r7bfix/verify_p1_rundirs \
      --runs-csv outputs/framelease_v4/build/R7B/dev/agg_snap_2203/runs.csv \
      --status outputs/framelease_v4/build/R7B/dev/p1_snap_2203/status.jsonl --out r2_numbers.json
"""
import argparse
import csv
import hashlib
import json
import math
import os
import sys


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def rows(p):
    with open(p, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def js(x, d):
    try:
        v = json.loads(x) if x else d
    except ValueError:
        return d
    return v


def sums_ok(d):
    out = {}
    with open(os.path.join(d, 'SHA256SUMS'), encoding='utf-8') as f:
        for ln in f:
            dig, _, name = ln.rstrip('\n').partition('  ')
            out[name] = (dig == sha(os.path.join(d, name)))
    return out


def outcomes(status):
    """job -> (outcome of the last final 'end' record, else of the last 'end' record, number of 'end' records)."""
    last, final, n = {}, {}, {}
    with open(status, encoding='utf-8') as f:
        for ln in f:
            if not ln.strip():
                continue
            r = json.loads(ln)
            if r.get('event') != 'end' or not r.get('id'):
                continue
            n[r['id']] = n.get(r['id'], 0) + 1
            last[r['id']] = r.get('outcome')
            if r.get('final'):
                final[r['id']] = r.get('outcome')
    return {j: (final.get(j, last[j]), n[j], j in final) for j in last}


def recount(d, runs_csv=None, status=None):
    t1 = json.load(open(os.path.join(d, 'table1_extra.json'), encoding='utf-8'))
    diffs = rows(os.path.join(d, 'differences.csv'))
    rr = rows(os.path.join(d, 'runs_recomputed.csv'))
    cp = rows(os.path.join(d, 'cause_plans.csv'))
    job_run = {}
    for r in rr:
        for j in js(r['jobs'], []):
            job_run[j] = r
    agg = {r['job']: r for r in rows(runs_csv)} if runs_csv else {}
    outc = outcomes(status) if status else {}

    def inflight_commits(r):
        pbs, chk = js(r.get('plans_by_status'), {}), js(r.get('checks'), {})
        return int(pbs.get('no_plan_logged', 0) or 0) - int(chk.get('commit_without_job_step', 0) or 0)

    runtime_diff = {x['key'] for x in diffs if x['target'] == 'runs.csv'
                    and x['their_field'] in ('gpu_usage', 'gpu_busy_in_span_s')}
    cls = {}
    for i, x in enumerate(diffs):
        c = x['cause']
        if c == 'F1':
            cls[i] = 'F1'
            continue
        if c in ('F3', 'F1+F3'):
            cls[i] = 'F3'
            continue
        if c:
            cls[i] = 'unexplained'
            continue
        r = job_run.get(x['key'])
        o, t = num(x['ours']), num(x['theirs'])
        if x['target'] == 'runs.csv' and x['scope'] == 'record' and r is not None and o is not None \
                and t is not None and t < o:
            if x['their_field'] in ('gpu_usage_recomputed', 'gpu_busy_recomputed_s'):
                b = js(r['gpu_usage_bounds' if x['their_field'] == 'gpu_usage_recomputed' else 'gpu_busy_s_bounds'],
                       [])
                if int(r['gpu_inflight_boundaries'] or 0) >= 1 and len(b) == 2 and t < b[0] \
                        and x['key'] not in runtime_diff:
                    cls[i] = 'in_flight'
                    continue
            if x['their_field'] == 'commits' and inflight_commits(r) >= 1 and o - t == inflight_commits(r):
                cls[i] = 'in_flight'
                continue
        if x['scope'] == 'record' and x['target'] in ('runs.csv', 'runner result') and not x['theirs'].strip():
            j = x['key']
            a = agg.get(j)
            if j in outc and outc[j][0] != 'ok' and a is not None and a['analysis_use'].strip().lower() in (
                    'false', '0', ''):
                cls[i] = 'not_ok_record'
                continue
        cls[i] = 'unexplained'

    def summary(name):
        sel = [x for i, x in enumerate(diffs) if cls[i] == name]
        runs, cols = {}, {}
        for x in sel:
            if x['target'] in ('runs.csv', 'runner', 'runner result'):
                r = job_run.get(x['key'])
                rd, arm = (r['run_dir'], r['arm']) if r else (x['key'], '?')
            elif x['target'] == 'summary.json':
                r = next((y for y in rr if y['run_dir'] == x['key']), None)
                rd, arm = x['key'], r['arm'] if r else '?'
            else:
                rd = None
            if rd is not None:
                runs.setdefault(rd, [arm, False])
                runs[rd][1] |= x['scope'] == 'analysis'
            col = (x['target'], x['their_field'])
            d = num(x['abs_diff'])
            if d is None and num(x['ours']) is not None and num(x['theirs']) is not None:
                d = abs(num(x['ours']) - num(x['theirs']))
            e = cols.setdefault('%s|%s' % col, {'n': 0, 'max': None, 'without': 0, 'at': None})
            e['n'] += 1
            if d is None:
                e['without'] += 1
            elif e['max'] is None or d > e['max']:
                e['max'], e['at'] = d, [x['key'], x['ours'], x['theirs'], x['scope']]
        per_arm = {}
        for rd, (arm, an) in runs.items():
            per_arm[arm] = per_arm.get(arm, 0) + 1
        return {'n': len(sel), 'analysis': sum(x['scope'] == 'analysis' for x in sel),
                'runs': len(runs), 'runs_per_arm': dict(sorted(per_arm.items())),
                'jobs': sorted({x['key'] for x in sel if x['target'] in ('runs.csv', 'runner result')}),
                'columns': dict(sorted(cols.items()))}

    ended = [r for r in rr if int(r['gpu_inflight_boundaries'] or 0) >= 1 or inflight_commits(r) >= 1]
    ended_gpu = [r for r in rr if int(r['gpu_inflight_boundaries'] or 0) >= 1]
    va = [r for r in rr if r['validity_available'] in ('True', 'true', '1')]
    f1_dirs = [r for r in rr if int(r['f1_plans'] or 0) > 0]
    f3_dirs = [r for r in rr if int(r['f3_plans'] or 0) > 0]
    comp = t1['comparisons']
    out = {
        'dir': d, 'sha256sums': sums_ok(d), 'status': t1.get('status'), 'verdict': t1.get('verdict'),
        'run_dirs': t1['runs'], 'compared': comp['compared'], 'differences': comp['differences'],
        'analysis_differences': comp['analysis_differences'], 'by_cause': comp['differences_by_cause'],
        'analysis_by_cause': comp['analysis_differences_by_cause'],
        'within_bounds_by_cause': comp.get('agree_within_bounds_by_cause'),
        'agree_within_validity_bounds': comp.get('agree_within_validity_bounds'),
        'agree_within_inflight_bounds': comp.get('agree_within_inflight_bounds'),
        'by_target': {k: {kk: v[kk] for kk in ('compared', 'differences')} for k, v in comp['by_target'].items()},
        'rows': len(diffs), 'runs_recomputed_rows': len(rr), 'validity_available': len(va),
        'runs_ending_in_flight': len(ended), 'runs_with_inflight_gpu_boundaries': len(ended_gpu),
        'runs_with_inflight_commits': sum(inflight_commits(r) >= 1 for r in rr),
        'f1_run_dirs': len(f1_dirs), 'f1_plans': sum(int(r['f1_plans'] or 0) for r in rr),
        'f3_run_dirs': len(f3_dirs), 'f3_plans': sum(int(r['f3_plans'] or 0) for r in rr),
        'cause_plans': {c: sum(p['cause'] == c for p in cp) for c in ('F1', 'F3')},
        'cause_plans_f1_status': {},
        'classes': {n: summary(n) for n in ('F1', 'F3', 'in_flight', 'not_ok_record', 'unexplained')},
    }
    for p in cp:
        if p['cause'] == 'F1':
            k = '%s->%s' % (p['status'], p['status_registered'])
            out['cause_plans_f1_status'][k] = out['cause_plans_f1_status'].get(k, 0) + 1
    if agg:
        out['runs_csv_rows'] = len(agg)
        out['runs_csv_analysis_use'] = sum(r['analysis_use'].strip().lower() in ('true', '1') for r in agg.values())
        f1_jobs = out['classes']['F1']['jobs']
        out['f1_jobs_analysis_use'] = {j: agg[j]['analysis_use'] for j in f1_jobs if j in agg}
        out['f1_jobs_arm_runs_csv'] = sorted({agg[j]['protocol_arm'] for j in f1_jobs if j in agg})
        no = out['classes']['not_ok_record']['jobs']
        out['not_ok_jobs'] = {j: {'runner': outc.get(j), 'outcome': agg[j]['outcome'],
                                  'missing_reason': agg[j]['missing_reason'], 'analysis_use': agg[j]['analysis_use'],
                                  'selected_run_set': bool(agg[j]['selected_run']), 'run_dir': agg[j]['run_dir']}
                              for j in no if j in agg}
        out['runner_not_ok_final'] = {j: v for j, v in outc.items() if v[0] != 'ok'}
    return out


def rates():
    def p_any(rate, n):
        return 1 - (1 - rate) ** n
    f1 = 26 / 271
    return {
        'F1': {'98': 98 * f1, '127': 127 * f1, '308': 308 * f1, 'p14': p_any(f1, 14), 'p44': p_any(f1, 44),
               'p13': p_any(f1, 13)},
        'in_flight': {'98': [98 * 36 / 272, 98 * 31 / 180], '127': [127 * 36 / 272, 127 * 31 / 180],
                      '308': [308 * 36 / 272, 308 * 31 / 180], 'pct': [31 / 180, 36 / 272]},
        'F3': {'98': 98 / 271, '127': 127 / 271, '308': 308 / 271, 'p98': p_any(1 / 271, 98)},
        'not_ok': {'98': 98 / 180, '308': 308 / 180},
        'F1_pct': f1,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--snap', required=True)
    ap.add_argument('--rundirs', required=True)
    ap.add_argument('--runs-csv', required=True)
    ap.add_argument('--status', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    rep = {'snapshot': recount(a.snap, a.runs_csv, a.status), 'rundirs_272': recount(a.rundirs), 'rates': rates(),
           'inputs_sha256': {p: sha(p) for p in (a.runs_csv, a.status)}}
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(rep, f, indent=1, sort_keys=True)
        f.write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
