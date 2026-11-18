"""Class F1 of a run of verify_table1_extra.py (Amendment A11, reporting rule of finding F1): read only.

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/a10r7b/f1/f1_class_report.py VERIFY_OUT [--out FILE.json]

VERIFY_OUT is the output directory of one run of framelease_v4/analysis/verify_table1_extra.py. Read: SHA256SUMS,
differences.csv, runs_recomputed.csv, table1_extra.json and cause_plans.csv; nothing else. Each of the four data files
must be listed in SHA256SUMS at its sha256 (the list the verifier writes last); otherwise the report stops (exit 2).

Class F1 holds exactly the rows of differences.csv whose 'cause' is 'F1'. Reported:
* differences: the rows of class F1; analysis_differences: those with scope 'analysis';
* runs_per_arm: per arm, the run directories with at least one row of class F1 in a run-level comparison (target
  runs.csv, summary.json, runner or runner result; the key names the job, or the run directory for summary.json), and
  of them those with a row in scope 'analysis'. The job and the arm of a run come from runs_recomputed.csv ('jobs',
  'run_dir', 'arm');
* largest_abs_diff: per affected column the row of class F1 with the largest absolute difference, and the number of
  the column's rows of class F1 without an absolute difference (rows_without_abs_diff: a side empty or not a number).
  The column is the target, the metric (for a target other than runs.csv, arm_summary.csv, summary.json and the runner
  records: the component of the key, or else the field, that names a metric of the script) and their_field. The
  absolute difference is 'abs_diff', else |ours - theirs| when both are numbers; a column whose rows all lack one has
  abs_diff null;
* agree_within_bounds: the agreements within bounds whose other side equals the value under F1
  (comparisons.agree_within_bounds_by_cause of table1_extra.json, copied with every cause);
* plans: the rows of cause_plans.csv with cause F1 (plans and run directories);
* other_causes: every other row of differences.csv by cause ('F3', 'F1+F3', 'unclassified' for an empty cause).
  Under use rule 2 of Amendment A11 any such row is a verification failure handled by the rules of Amendment A10;
* outcome: 'AGREE' (no difference), 'class F1 only' (every difference in class F1) or 'verification failure' (a
  difference of another cause); release: the outcome when table1_extra.json has status 'final' (use rule 1: only
  such a result counts for the paper; 'class F1 only' releases the columns with the registered values and class F1 is
  reported), else 'not final'.
The counts by cause are formed again from differences.csv and must equal comparisons.differences_by_cause and
comparisons.analysis_differences_by_cause of table1_extra.json, its comparisons.differences the number of rows and its
verdict 'AGREE' exactly when there is none; otherwise the report stops (exit 2). --out must lie outside VERIFY_OUT (its
SHA256SUMS stays valid) and outside framelease_v4/.
Exit 0 report written (stdout, or --out), 2 input error.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys

SCHEMA = 'framelease_v4.f1_class/2'
CLASS = 'F1'
UNCLASSIFIED = 'unclassified'
RUN_TARGETS = ('runs.csv', 'summary.json', 'runner', 'runner result')
COLUMN_TARGETS = RUN_TARGETS + ('arm_summary.csv',)
METRICS = ('gpu_usage', 'dmr', 'action_age_p50_s', 'action_age_p95_s', 'fallback_ratio', 'p_both', 'eir', 'r_cond')
INPUTS = ('differences.csv', 'runs_recomputed.csv', 'table1_extra.json', 'cause_plans.csv')
SUMS = 'SHA256SUMS'
PROJECT_CODE = '/home/kang/Desktop/DAC/framelease_v4'


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def number(text):
    try:
        x = float(text)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def read_csv(path):
    with open(path, newline='', encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


def metric_of(row):
    if row['target'] in COLUMN_TARGETS:
        return ''
    for part in re.split(r'[:/]', row.get('key') or ''):
        if part in METRICS:
            return part
    return row['field'] if row.get('field') in METRICS else ''


def abs_diff(row):
    d = number(row.get('abs_diff'))
    if d is None:
        a, b = number(row.get('ours')), number(row.get('theirs'))
        d = abs(a - b) if a is not None and b is not None else None
    return d


def column_of(row):
    return row['target'], metric_of(row), row.get('their_field') or row.get('field') or ''


def runs_index(rows):
    """job -> (run_dir, arm) and run_dir -> arm from runs_recomputed.csv."""
    by_job, by_dir = {}, {}
    for r in rows:
        run_dir, arm = r.get('run_dir') or '', r.get('arm') or ''
        by_dir[run_dir] = arm
        try:
            jobs = json.loads(r.get('jobs') or '[]')
        except ValueError:
            jobs = []
        for j in jobs if isinstance(jobs, list) else []:
            by_job[str(j)] = (run_dir, arm)
    return by_job, by_dir


def checked_inputs(out_dir):
    """The paths of the four inputs after the check against SHA256SUMS; the sha256 of every file read."""
    paths = {n: os.path.join(out_dir, n) for n in INPUTS + (SUMS,)}
    missing = [n for n, p in paths.items() if not os.path.isfile(p)]
    if missing:
        raise SystemExit('input error: %s lacks %s' % (out_dir, missing))
    listed = {}
    with open(paths[SUMS], encoding='utf-8') as fh:
        for ln in fh:
            digest, sep, name = ln.rstrip('\n').partition('  ')
            if sep:
                listed[name] = digest
    shas = {n: sha256(p) for n, p in paths.items()}
    bad = ['%s %s' % (n, 'not listed' if n not in listed else 'differs (%s listed, %s now)'
                      % (listed[n][:12], shas[n][:12])) for n in INPUTS if listed.get(n) != shas[n]]
    if bad:
        raise SystemExit('input error: the inputs do not match %s of %s: %s' % (SUMS, out_dir, '; '.join(bad)))
    return paths, shas


def report(out_dir):
    paths, shas = checked_inputs(out_dir)
    diffs = read_csv(paths['differences.csv'])
    by_job, by_dir = runs_index(read_csv(paths['runs_recomputed.csv']))
    with open(paths['table1_extra.json'], encoding='utf-8') as fh:
        t1 = json.load(fh)
    plans = [p for p in read_csv(paths['cause_plans.csv']) if p.get('cause') == CLASS]

    by_cause, by_cause_analysis = {}, {}
    for r in diffs:
        cause = r.get('cause') or UNCLASSIFIED
        by_cause[cause] = by_cause.get(cause, 0) + 1
        if r.get('scope') == 'analysis':
            by_cause_analysis[cause] = by_cause_analysis.get(cause, 0) + 1
    comp = t1.get('comparisons') or {}
    if by_cause != (comp.get('differences_by_cause') or {}) or \
            by_cause_analysis != (comp.get('analysis_differences_by_cause') or {}):
        raise SystemExit('input error: the counts by cause of differences.csv (%s; analysis %s) differ from '
                         'table1_extra.json (%s; analysis %s)' % (by_cause, by_cause_analysis,
                                                                 comp.get('differences_by_cause'),
                                                                 comp.get('analysis_differences_by_cause')))
    want_verdict = 'AGREE' if not diffs else 'DIFFER'
    if comp.get('differences') != len(diffs) or t1.get('verdict') != want_verdict:
        raise SystemExit('input error: table1_extra.json states %r differences and verdict %r; differences.csv holds '
                         '%d rows' % (comp.get('differences'), t1.get('verdict'), len(diffs)))
    f1 = [r for r in diffs if r.get('cause') == CLASS]

    runs = {}
    for r in f1:
        if r['target'] not in RUN_TARGETS:
            continue
        key = r.get('key') or ''
        if r['target'] == 'summary.json':
            run_dir, arm = key, by_dir.get(key, '(unmapped)')
        else:
            run_dir, arm = by_job.get(key, (key, '(unmapped)'))
        e = runs.setdefault(run_dir, {'arm': arm, 'jobs': set(), 'analysis': False})
        if r['target'] != 'summary.json':
            e['jobs'].add(key)
        e['analysis'] |= r.get('scope') == 'analysis'
    per_arm = {}
    for e in runs.values():
        a = per_arm.setdefault(e['arm'], {'runs': 0, 'runs_with_analysis_difference': 0})
        a['runs'] += 1
        a['runs_with_analysis_difference'] += int(e['analysis'])

    largest = {}
    for r in f1:
        col = column_of(r)
        d = abs_diff(r)
        best = largest.get(col)
        if best is None or (d is not None and (best['abs_diff'] is None or d > best['abs_diff'])):
            largest[col] = {'target': col[0], 'metric': col[1], 'column': col[2], 'abs_diff': d, 'key': r.get('key'),
                            'ours': r.get('ours'), 'theirs': r.get('theirs'), 'scope': r.get('scope'), 'rows': 0,
                            'rows_without_abs_diff': 0}
    for r in f1:
        e = largest[column_of(r)]
        e['rows'] += 1
        e['rows_without_abs_diff'] += int(abs_diff(r) is None)

    within = dict(sorted((comp.get('agree_within_bounds_by_cause') or {}).items()))
    other = {c: n for c, n in by_cause.items() if c != CLASS}
    n_other = sum(other.values())
    outcome = 'AGREE' if not diffs else ('class F1 only' if n_other == 0 else 'verification failure')
    return {
        'schema': SCHEMA,
        'verification': out_dir,
        'inputs_sha256': dict(sorted(shas.items())),
        'sha256sums': 'OK: the four inputs equal %s' % SUMS,
        'status': t1.get('status'),
        'verdict': t1.get('verdict'),
        'comparisons': comp.get('compared', comp.get('comparisons')),
        'differences': len(diffs),
        'differences_by_cause': dict(sorted(by_cause.items())),
        'analysis_differences_by_cause': dict(sorted(by_cause_analysis.items())),
        'agree_within_bounds_by_cause': within,
        'class_F1': {
            'differences': len(f1),
            'analysis_differences': sum(r.get('scope') == 'analysis' for r in f1),
            'differences_without_abs_diff': sum(abs_diff(r) is None for r in f1),
            'agree_within_bounds': within.get(CLASS, 0),
            'runs': len(runs),
            'runs_per_arm': dict(sorted(per_arm.items())),
            'run_list': [{'run_dir': d, 'arm': e['arm'], 'jobs': sorted(e['jobs']), 'analysis': e['analysis']}
                         for d, e in sorted(runs.items())],
            'largest_abs_diff': [largest[k] for k in sorted(largest)],
            'plans': {'plans': len(plans), 'run_dirs': len({p.get('run_dir') for p in plans})},
        },
        'other_causes': {'differences': n_other, 'by_cause': dict(sorted(other.items())),
                         'analysis_differences': sum(n for c, n in by_cause_analysis.items() if c != CLASS)},
        'outcome': outcome,
        'release': outcome if t1.get('status') == 'final' else 'not final',
    }


def inside(path, directory):
    """path is directory or lies under it."""
    p, d = os.path.realpath(path), os.path.realpath(directory)
    return p == d or p.startswith(d + os.sep)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('verify_out')
    ap.add_argument('--out', default=None)
    a = ap.parse_args(argv)
    out_dir = os.path.normpath(a.verify_out)
    if a.out and (inside(a.out, PROJECT_CODE) or inside(a.out, out_dir) or os.path.isdir(a.out)):
        print('input error: --out %s is a directory or lies under framelease_v4/ or inside %s' % (a.out, out_dir),
              file=sys.stderr)
        return 2
    try:
        rep = report(out_dir)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 2
    text = json.dumps(rep, indent=1, sort_keys=False) + '\n'
    if a.out:
        tmp = a.out + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            fh.write(text)
        os.replace(tmp, a.out)
    else:
        sys.stdout.write(text)
    c = rep['class_F1']
    print('status %s, verdict %s: %d differences (%s); class F1 %d (analysis %d, without an absolute difference %d) in '
          '%d runs %s; outcome: %s; release: %s'
          % (rep['status'], rep['verdict'], rep['differences'], rep['differences_by_cause'], c['differences'],
             c['analysis_differences'], c['differences_without_abs_diff'], c['runs'],
             {k: v['runs'] for k, v in c['runs_per_arm'].items()}, rep['outcome'], rep['release']), file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
