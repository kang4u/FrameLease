"""Item F1A11, fix pass 1: recount of the numbers that the review of the item corrected (read only; standard library).

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/a10r7b/f1/fix1_numbers.py SNAPSHOT_OUT RUNDIRS_OUT --out FILE.json

SNAPSHOT_OUT, RUNDIRS_OUT: output directories of verify_table1_extra.py (P1 training routes: the development
comparison build/R7B/dev/verify_p1_snap_2203_d/ and the 272 run directories /tmp/A10A11/r7bfix/verify_p1_rundirs/).
Each is checked against its SHA256SUMS first (exit 2 on a mismatch). Read: differences.csv and runs_recomputed.csv of
SNAPSHOT_OUT, runs_recomputed.csv and plans.csv of both. Counted:
* the differences without a cause of SNAPSHOT_OUT: those of the timed-out job TIMED_OUT by target; the others by
  compared column, their jobs and run directories, and whether these runs have in-flight GPU boundaries
  (runs_recomputed.csv gpu_inflight_boundaries > 0); the runs with such boundaries among all;
* the capture offsets above the 0.05 s grid of all plans of plans.csv (capture_s minus the nearest grid time): min,
  median, max, the number below the grid and above 1e-9 s;
* the runs with unevaluable plans (plans_unevaluable > 0) and among them those whose log-censored bounds are not a
  point (log_censored_plans_bounds).
"""
import argparse
import csv
import hashlib
import json
import os
import statistics
import sys

TIMED_OUT = 'v4p1_fl_heuristic_B0_d10_k1.0_s11_r23659'
GRID = 0.05


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def checked(out_dir, names):
    listed = {}
    with open(os.path.join(out_dir, 'SHA256SUMS'), encoding='utf-8') as fh:
        for ln in fh:
            digest, sep, name = ln.rstrip('\n').partition('  ')
            if sep:
                listed[name] = digest
    bad = [n for n in names if listed.get(n) != sha256(os.path.join(out_dir, n))]
    if bad:
        raise SystemExit('input error: %s differs from SHA256SUMS in %s' % (out_dir, bad))
    return {n: listed[n] for n in names}


def rows(path):
    with open(path, newline='', encoding='utf-8') as fh:
        yield from csv.DictReader(fh)


def number(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def runs_info(out_dir):
    by_job, inflight, unevaluable = {}, {}, {}
    for r in rows(os.path.join(out_dir, 'runs_recomputed.csv')):
        d = r['run_dir']
        inflight[d] = (number(r.get('gpu_inflight_boundaries')) or 0) > 0
        if (number(r.get('plans_unevaluable')) or 0) > 0:
            unevaluable[d] = {'plans_unevaluable': r.get('plans_unevaluable'),
                              'log_censored_plans': r.get('log_censored_plans'),
                              'log_censored_plans_bounds': r.get('log_censored_plans_bounds'),
                              'route_id': r.get('route_id')}
        for j in json.loads(r.get('jobs') or '[]'):
            by_job[j] = d
    return by_job, inflight, unevaluable


def offsets(out_dir):
    off = []
    for r in rows(os.path.join(out_dir, 'plans.csv')):
        c = number(r.get('capture_s'))
        if c is not None:
            off.append(c - round(c / GRID) * GRID)
    return {'plans': len(off), 'min': min(off), 'median': statistics.median(off), 'max': max(off),
            'below_grid': sum(x < 0 for x in off), 'above_1e-9': sum(x > 1e-9 for x in off),
            'above_1e-9_fraction': sum(x > 1e-9 for x in off) / len(off)}


def bound_values(text):
    """The numbers of a bounds cell ('[6, 13]', '(6, 13)' or empty)."""
    parts = (text or '').strip('[]() ').split(',')
    return {number(p) for p in parts if number(p) is not None}


def unevaluable_summary(unevaluable):
    widened = {d: v for d, v in unevaluable.items() if len(bound_values(v['log_censored_plans_bounds'])) > 1}
    return {'runs_with_unevaluable_plans': len(unevaluable), 'of_them_log_censored_bounds_not_a_point': len(widened),
            'examples': dict(sorted(widened.items())[:3])}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('snapshot_out')
    ap.add_argument('rundirs_out')
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    if os.path.realpath(a.out).startswith(os.path.realpath('/home/kang/Desktop/DAC/framelease_v4') + os.sep):
        print('--out under framelease_v4/ refused', file=sys.stderr)
        return 2
    try:
        sums = {'snapshot': checked(a.snapshot_out, ('differences.csv', 'runs_recomputed.csv', 'plans.csv')),
                'rundirs': checked(a.rundirs_out, ('runs_recomputed.csv', 'plans.csv'))}
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 2
    by_job, inflight, unev_snap = runs_info(a.snapshot_out)
    timed_out, other_cols, other_jobs, other_runs, r23659 = {}, {}, {}, set(), {}
    total = 0
    for r in rows(os.path.join(a.snapshot_out, 'differences.csv')):
        if r.get('cause'):
            continue
        total += 1
        key = r.get('key') or ''
        if key == TIMED_OUT:
            timed_out[r['target']] = timed_out.get(r['target'], 0) + 1
            continue
        col = '%s|%s' % (r['target'], r.get('their_field') or r.get('field'))
        other_cols[col] = other_cols.get(col, 0) + 1
        other_jobs[key] = other_jobs.get(key, 0) + 1
        other_runs.add(by_job.get(key, '(unmapped) ' + key))
        if 'r23659' in key:
            r23659[key] = r23659.get(key, 0) + 1
    _, inflight_all, unev_all = runs_info(a.rundirs_out)
    out = {
        'inputs_sha256': sums,
        'snapshot_without_cause': {
            'differences': total,
            'timed_out_job': {'job': TIMED_OUT, 'by_target': dict(sorted(timed_out.items())),
                              'cells': sum(timed_out.values())},
            'other': {'by_column': dict(sorted(other_cols.items())), 'cells': sum(other_cols.values()),
                      'jobs': len(other_jobs), 'runs': len(other_runs),
                      'runs_with_inflight_gpu_boundaries': sum(inflight.get(d, False) for d in other_runs),
                      'other_jobs_with_r23659': dict(sorted(r23659.items()))},
            'runs_recomputed': len(inflight),
            'runs_with_inflight_gpu_boundaries': sum(inflight.values()),
        },
        'capture_offsets': {'snapshot': offsets(a.snapshot_out), 'rundirs': offsets(a.rundirs_out)},
        'unevaluable': {'snapshot': unevaluable_summary(unev_snap), 'rundirs': unevaluable_summary(unev_all),
                        'rundirs_runs': len(inflight_all)},
    }
    tmp = a.out + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=1)
        fh.write('\n')
    os.replace(tmp, a.out)
    s = out['snapshot_without_cause']
    print('without a cause %d: timed-out job %s; other %s in %d runs (%d with in-flight GPU boundaries; %d of %d runs '
          'have them); capture offsets: median %.3g s (snapshot), %.3g s (run directories)'
          % (s['differences'], s['timed_out_job']['by_target'], s['other']['by_column'], s['other']['runs'],
             s['other']['runs_with_inflight_gpu_boundaries'], s['runs_with_inflight_gpu_boundaries'],
             s['runs_recomputed'], out['capture_offsets']['snapshot']['median'],
             out['capture_offsets']['rundirs']['median']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
