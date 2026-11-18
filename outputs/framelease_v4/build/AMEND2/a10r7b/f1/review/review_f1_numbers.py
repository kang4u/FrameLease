"""Review of item F1A11: independent recount of the F1 numbers that A11 and F1_RULE.md state (read only).

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/a10r7b/f1/review/review_f1_numbers.py [--out FILE.json]

Reads the outputs of verify_table1_extra.py (f77b2dcf) on the P1 snapshot (build/R7B/dev/verify_p1_snap_2203_d/) and on
the 272 P1 run directories (/tmp/A10A11/r7bfix/verify_p1_rundirs/), and build/R7B/dev/agg_snap_2203/runs.csv (the
development aggregation; analysis_use and protocol_arm). P1 training routes only. Written without f1_class_report.py:
the counts are formed here from the csv files directly. Writes only --out (default: stdout).
"""
import argparse
import collections
import csv
import json
import math
import os
import statistics
import sys

ROOT = '/home/kang/Desktop/DAC'
SNAP = os.path.join(ROOT, 'outputs/framelease_v4/build/R7B/dev/verify_p1_snap_2203_d')
ALL = '/tmp/A10A11/r7bfix/verify_p1_rundirs'
AGG = os.path.join(ROOT, 'outputs/framelease_v4/build/R7B/dev/agg_snap_2203/runs.csv')
GRID = 0.05
TIMED_OUT_JOB = 'v4p1_fl_heuristic_B0_d10_k1.0_s11_r23659'    # the timed-out unused run of the snapshot


def rows(path):
    with open(path, newline='', encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


def num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def grid_offset(t):
    return t - round(t / GRID) * GRID


def diffs_summary(d):
    diffs = rows(os.path.join(d, 'differences.csv'))
    rr = rows(os.path.join(d, 'runs_recomputed.csv'))
    job_arm = {}
    for r in rr:
        for j in json.loads(r['jobs'] or '[]'):
            job_arm[j] = (r['run_dir'], r['arm'])
    by_cause = collections.Counter(r['cause'] or '' for r in diffs)
    by_cause_scope = collections.Counter((r['cause'] or '', r['scope']) for r in diffs)
    f1 = [r for r in diffs if r['cause'] == 'F1']
    per_col = {}
    for r in f1:
        a, b = num(r['ours']), num(r['theirs'])
        dd = abs(a - b) if a is not None and b is not None else None
        k = '%s|%s|%s' % (r['target'], r['field'], r['their_field'])
        e = per_col.setdefault(k, {'rows': 0, 'max_abs': None, 'key': None, 'ours': None, 'theirs': None})
        e['rows'] += 1
        if dd is not None and (e['max_abs'] is None or dd > e['max_abs']):
            e.update(max_abs=dd, key=r['key'], ours=r['ours'], theirs=r['theirs'])
    run_jobs = sorted({r['key'] for r in f1 if r['target'] == 'runs.csv'})
    arms = collections.Counter(job_arm.get(j, ('?', '?'))[1] for j in run_jobs)
    unclassified = collections.Counter('%s|%s' % (r['target'], r['their_field']) for r in diffs if not r['cause'])
    unclassified_r23659 = sum(1 for r in diffs if not r['cause'] and 'r23659' in r['key'])
    timed_out = [r for r in diffs if not r['cause'] and r['key'] == TIMED_OUT_JOB]
    others = [r for r in diffs if not r['cause'] and r['key'] != TIMED_OUT_JOB]
    analysis_rows = [{k: r[k] for k in ('target', 'key', 'field', 'their_field', 'ours', 'theirs', 'cause')}
                     for r in diffs if r['scope'] == 'analysis']
    other_targets = collections.Counter(r['target'] for r in f1 if r['target'] not in ('runs.csv', 'arm_summary.csv'))
    return {'differences': len(diffs), 'by_cause': dict(by_cause),
            'by_cause_scope': {'%s|%s' % k: v for k, v in by_cause_scope.items()},
            'f1_rows': len(f1), 'f1_runs_csv_jobs': len(run_jobs), 'f1_runs_per_arm': dict(arms),
            'f1_jobs': run_jobs, 'f1_per_column': per_col, 'f1_other_targets': dict(other_targets),
            'unclassified_by_column': dict(unclassified), 'unclassified_r23659': unclassified_r23659,
            'unclassified_timed_out_job_by_target': dict(collections.Counter(r['target'] for r in timed_out)),
            'unclassified_other_by_column': dict(collections.Counter('%s|%s' % (r['target'], r['their_field'])
                                                                     for r in others)),
            'unclassified_other_runs': len({r['key'] for r in others}),
            'analysis_scope_rows': analysis_rows, 'job_arm': job_arm}


def plans_summary(d):
    cp = rows(os.path.join(d, 'cause_plans.csv'))
    f1 = [r for r in cp if r['cause'] == 'F1']
    trans = collections.Counter('%s->%s' % (r['status'], r['status_registered']) for r in f1)
    miss = collections.Counter('%s/%s' % (r['miss'], r['miss_registered']) for r in f1 if r['status'] == 'conflict')
    dt = [num(r['t_sample']) - num(r['t_last_row']) for r in f1]
    capoff = [grid_offset(num(r['capture_s'])) for r in f1]
    out = {'cause_plans_rows': len(cp), 'by_cause': dict(collections.Counter(r['cause'] for r in cp)),
           'f1_plans': len(f1), 'f1_run_dirs': len({r['run_dir'] for r in f1}), 'f1_status_transitions': dict(trans),
           'f1_conflict_miss_ours/registered': dict(miss),
           'f1_sample_minus_last_row_s': [min(dt), max(dt)] if dt else None,
           'f1_capture_grid_offset_s': [min(capoff), max(capoff)] if capoff else None,
           'f1_t_last_row_on_grid': all(abs(grid_offset(num(r['t_last_row']))) < 1e-9 for r in f1)}
    offs, n = [], 0
    with open(os.path.join(d, 'plans.csv'), newline='', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            c = num(r['capture_s'])
            if c is None:
                continue
            n += 1
            offs.append(grid_offset(c))
    above = sum(1 for o in offs if o > 1e-9)
    out.update(plans=n, capture_offset_min=min(offs), capture_offset_max=max(offs),
               capture_offset_median=statistics.median(offs), capture_offset_negative=sum(1 for o in offs if o < 0),
               capture_offset_above_1e9=above, capture_offset_above_1e9_frac=above / n)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default=None)
    a = ap.parse_args(argv)
    snap = diffs_summary(SNAP)
    agg = {r['job']: r for r in rows(AGG)}
    jobs = snap.pop('f1_jobs')
    job_arm = snap.pop('job_arm')
    snap['f1_jobs_analysis_use'] = dict(collections.Counter(agg[j]['analysis_use'] if j in agg else 'absent'
                                                            for j in jobs))
    snap['f1_jobs_protocol_arm'] = dict(collections.Counter(agg[j]['protocol_arm'] if j in agg else 'absent'
                                                            for j in jobs))
    snap['f1_jobs_arm_mismatch'] = [j for j in jobs if j in agg and agg[j]['protocol_arm'] != job_arm[j][1]]
    r1792 = [r for r in rows(os.path.join(SNAP, 'differences.csv')) if r['key'] == 'v4p1_fast_only_k1.0_s11_r1792']
    snap['r1792_rows'] = [{k: r[k] for k in ('field', 'their_field', 'ours', 'theirs', 'cause', 'scope')}
                          for r in r1792]
    rr = {json.loads(r['jobs'])[0]: r for r in rows(os.path.join(SNAP, 'runs_recomputed.csv')) if r['jobs'] != '[]'}
    x = rr.get('v4p1_fast_only_k1.0_s11_r1792')
    if x:
        snap['r1792_recomputed'] = {k: x[k] for k in ('eir_invalid_ticks', 'track_ticks', 'eir', 'eir_f1',
                                                       'eir_invalid_ticks_f1', 'f1_plans')}
    if 'v4p1_fast_only_k1.0_s11_r1792' in agg:
        g = agg['v4p1_fast_only_k1.0_s11_r1792']
        snap['r1792_registered'] = {k: g[k] for k in ('realized_invalid_ticks', 'realized_invalid_tick_ratio',
                                                       'analysis_use', 'route_id', 'protocol_arm')}
    res = {'snapshot': snap, 'snapshot_plans': plans_summary(SNAP)}
    if os.path.isdir(ALL):
        alls = diffs_summary(ALL)
        alls.pop('f1_jobs')
        alls.pop('job_arm')
        res['all_272'] = alls
        res['all_272_plans'] = plans_summary(ALL)
        rr_all = rows(os.path.join(ALL, 'runs_recomputed.csv'))
        res['all_272_runs'] = len(rr_all)
        res['all_272_f1_run_dirs_per_arm'] = dict(collections.Counter(
            r['arm'] for r in rr_all if (num(r.get('f1_plans')) or 0) > 0))
    text = json.dumps(res, indent=1, sort_keys=True) + '\n'
    if a.out:
        tmp = a.out + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            fh.write(text)
        os.replace(tmp, a.out)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
