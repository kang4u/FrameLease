"""Cause classes of a run of verify_table1_extra.py (Amendment A11, reporting rule of the differences): read only.

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/a10r7b/f1/f1_class_report.py VERIFY_OUT [--out FILE.json]

VERIFY_OUT is the output directory of one run of framelease_v4/analysis/verify_table1_extra.py. Read: SHA256SUMS,
differences.csv, runs_recomputed.csv, table1_extra.json and cause_plans.csv; each of the four data files must be listed
in SHA256SUMS at its sha256 (the list the verifier writes last); otherwise the report stops (exit 2). Only when a row
can belong to class not_ok_record (below) the report also reads the runner records (every status.jsonl) and the
runs.csv that table1_extra.json 'inputs' names, each at the sha256 recorded there (else exit 2); nothing else.

Every row of differences.csv is assigned to one class, defined by its mechanism (A11, reporting rule):
* class F1: the cause 'F1' (finding F1: a plan sample on the last actor-log row lies outside the log);
* class F3: the cause 'F3', or 'F1+F3' for a value that agrees only under both conventions (finding F3: V by
  interpolation of the clearance). The verifier gives a cause only when the other side agrees with the value under
  that convention at its tolerances or within the bounds under it;
* class in_flight: a row without a cause, target runs.csv, scope 'record', compared column gpu_usage_recomputed,
  gpu_busy_recomputed_s or commits, of a run (the job of the key, mapped through runs_recomputed.csv 'jobs') that ended
  with a job still running. The aggregator (metrics_v4.py) forms these columns from jobs.jsonl, which lacks that job:
  the GPU columns without its step quanta, commits without its commits; the verifier includes them. Required, for the
  GPU columns: gpu_inflight_boundaries >= 1 in runs_recomputed.csv, both sides numbers, the registered value below the
  lower bound of the recomputed one (gpu_usage_bounds, gpu_busy_s_bounds), and no difference row of the same key in
  the runs.csv columns gpu_usage (the value the analysis reads) and gpu_busy_in_span_s (the runtime's busy time,
  which includes that job); for commits: gpu_inflight_boundaries >= 1, both sides integers and the recomputed count
  minus the registered one equal to the commits of jobs without a jobs.jsonl row (plans_by_status 'no_plan_logged'
  minus the check 'commit_without_job_step'), at least 1. For the GPU columns the class tests the in-flight boundaries
  of the run and the direction of the difference, not its size against the omitted step quanta, which the verifier's
  outputs do not hold; largest_abs_diff states the largest difference;
* class not_ok_record: a row without a cause, scope 'record', target runs.csv or runner result, whose registered side
  is empty, of a job whose final runner outcome is a failure (present and neither 'ok' nor 'result_with_warnings',
  the OK outcomes of framelease_v2/gpu_queue.py: timeout, crash, simulator failure; the job's last final 'end' record
  of the runner records, else its last 'end' record, as the verifier reads them), whose runs.csv row carries an
  outcome other than 'ok' (the condition under which aggregate_v4.py job_row records no metric: 'sim_failure',
  'agent_crashed', 'pending') and analysis_use false. For such a job job_row records no metric and the runner no
  result values, while the verifier recomputes the run that the runner's record names. A non-empty registered value, a
  row in scope 'analysis', a job without a runner record or runs.csv row, a runner outcome that is absent, 'ok' or
  'result_with_warnings', a runs.csv outcome that is empty or 'ok' (a valid run whose metric step failed:
  missing_reason 'no_metrics'), or analysis_use true stays unexplained;
* unexplained: every other row. Under use rule 2 of Amendment A11 any such row is a verification failure handled by
  the rules of Amendment A10 (use rule 4; Sec. 9.12).
Reported per class: differences (all) and analysis_differences (scope 'analysis'); differences_without_abs_diff;
runs_per_arm: per arm, the run directories with at least one row of the class in a run-level comparison (target
runs.csv, summary.json, runner or runner result; the key names the job, or the run directory for summary.json), and of
them those with a row in scope 'analysis' (the job and the arm of a run from runs_recomputed.csv 'jobs', 'run_dir',
'arm'); largest_abs_diff: per affected column the row with the largest absolute difference and the number of the
column's rows without one (rows_without_abs_diff: a side empty or not a number). The column is the target, the metric
(for a target other than runs.csv, arm_summary.csv, summary.json and the runner records: the component of the key, or
else the field, that names a metric of the script) and their_field. The absolute difference is 'abs_diff', else
|ours - theirs| when both are numbers; a column whose rows all lack one has abs_diff null. Further: class F1 and F3
their plans (cause_plans.csv) and agree_within_bounds (comparisons.agree_within_bounds_by_cause of table1_extra.json,
copied with every cause), class F3 its rows by cause, class in_flight runs_ending_with_job_in_flight (the runs of
runs_recomputed.csv with in-flight GPU boundaries or commits of a job without a jobs.jsonl row), class not_ok_record
its jobs with their final runner outcome and runs.csv outcome, unexplained its rows by (target, column, scope) and
by cause.
outcome: 'AGREE' (no difference), 'pre-specified classes only' (every difference in class F1, F3, in_flight or
not_ok_record) or 'verification failure' (an unexplained difference); release: the outcome when table1_extra.json has
status 'final', script_sha256 equal to the sha256 of verify_table1_extra.py that Amendment A11 registers
(REGISTERED_VERIFIER) and options.runs_csv_values false (use rule 1: only such a result counts for the paper;
'pre-specified classes only' releases the columns with the registered values and every class is reported), else
'not final' (release_checks states each condition).
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

SCHEMA = 'framelease_v4.f1_class/3'
CLASS = 'F1'
UNCLASSIFIED = 'unclassified'
# The classes and the causes of differences.csv they hold; class in_flight holds rows without a cause (below).
CLASS_CAUSES = {'F1': ('F1',), 'F3': ('F3', 'F1+F3')}
IN_FLIGHT = 'in_flight'
NOT_OK = 'not_ok_record'
UNEXPLAINED = 'unexplained'
# runs.csv cross-check columns that the aggregator forms from jobs.jsonl (without a job still running at the end) and
# the runs_recomputed.csv bounds of the recomputed value they are compared with.
IN_FLIGHT_GPU = {'gpu_usage_recomputed': 'gpu_usage_bounds', 'gpu_busy_recomputed_s': 'gpu_busy_s_bounds'}
IN_FLIGHT_COMMITS = 'commits'
# runs.csv columns of the runtime's busy time (they include the work of a job still running at the end).
RUNTIME_GPU = ('gpu_usage', 'gpu_busy_in_span_s')
RUN_TARGETS = ('runs.csv', 'summary.json', 'runner', 'runner result')
NOT_OK_TARGETS = ('runs.csv', 'runner result')
RUNNER_OK = ('ok', 'result_with_warnings')                       # framelease_v2/gpu_queue.py OK_OUTCOMES
# The verifier that Amendment A11 registers (its sha256 in table1_extra.json 'script_sha256'); a change of it is an
# amendment, and this pin changes with it (RUNBOOK Sec. 3, precondition 2).
REGISTERED_VERIFIER = 'f77b2dcf34484d2537a4c22d804912f0c155c3e3c26a576f433b9f4f73d83c27'
COLUMN_TARGETS = RUN_TARGETS + ('arm_summary.csv',)
METRICS = ('gpu_usage', 'dmr', 'action_age_p50_s', 'action_age_p95_s', 'fallback_ratio', 'p_both', 'eir', 'r_cond')
INPUTS = ('differences.csv', 'runs_recomputed.csv', 'table1_extra.json', 'cause_plans.csv')
SUMS = 'SHA256SUMS'
ROOT = '/home/kang/Desktop/DAC'                                  # the verifier's root (table1_extra.json 'inputs')
PROJECT_CODE = ROOT + '/framelease_v4'


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


def integer(text):
    x = number(text)
    return int(x) if x is not None and x == int(x) else None


def as_json(text, default):
    try:
        x = json.loads(text) if text not in (None, '') else default
    except ValueError:
        return default
    return x if isinstance(x, type(default)) else default


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
    """job -> (run_dir, arm), run_dir -> arm and job -> runs_recomputed.csv row."""
    by_job, by_dir, row_of = {}, {}, {}
    for r in rows:
        run_dir, arm = r.get('run_dir') or '', r.get('arm') or ''
        by_dir[run_dir] = arm
        jobs = as_json(r.get('jobs'), [])
        for j in jobs:
            by_job[str(j)] = (run_dir, arm)
            row_of[str(j)] = r
    return by_job, by_dir, row_of


def in_flight_commits(run):
    """Commits of jobs without a jobs.jsonl row (still running at the end): plans 'no_plan_logged' less the commits of
    a logged job without that step."""
    pbs = as_json(run.get('plans_by_status'), {})
    chk = as_json(run.get('checks'), {})
    return (integer(pbs.get('no_plan_logged')) or 0) - (integer(chk.get('commit_without_job_step')) or 0)


def ended_in_flight(run):
    return (integer(run.get('gpu_inflight_boundaries')) or 0) >= 1 or in_flight_commits(run) >= 1


def is_in_flight(row, row_of, runtime_gpu_differs):
    """Class in_flight (module docstring)."""
    col = row.get('their_field') or ''
    if row.get('cause') or row['target'] != 'runs.csv' or row.get('scope') != 'record':
        return False
    run = row_of.get(row.get('key') or '')
    if run is None or col not in tuple(IN_FLIGHT_GPU) + (IN_FLIGHT_COMMITS,):
        return False
    ours, theirs = number(row.get('ours')), number(row.get('theirs'))
    if ours is None or theirs is None or not theirs < ours:
        return False
    if col == IN_FLIGHT_COMMITS:
        n = in_flight_commits(run)
        return (integer(run.get('gpu_inflight_boundaries')) or 0) >= 1 and integer(row.get('ours')) is not None \
            and integer(row.get('theirs')) is not None and n >= 1 \
            and integer(row.get('ours')) - integer(row.get('theirs')) == n
    bounds = as_json(run.get(IN_FLIGHT_GPU[col]), [])
    lower = number(bounds[0]) if len(bounds) == 2 else None
    return (integer(run.get('gpu_inflight_boundaries')) or 0) >= 1 and lower is not None and theirs < lower \
        and row.get('key') not in runtime_gpu_differs


def not_ok_candidate(row):
    """A row that class not_ok_record can hold, before its job is looked up."""
    return not row.get('cause') and row.get('scope') == 'record' and row['target'] in NOT_OK_TARGETS \
        and not (row.get('theirs') or '').strip()


def recorded_inputs(t1):
    """(status.jsonl paths, runs.csv path or None) of table1_extra.json 'inputs', each checked against the sha256
    recorded there (SystemExit otherwise)."""
    inputs = t1.get('inputs') or {}
    queues, runs_csv, bad = [], None, []
    for name, want in inputs.items():
        base = os.path.basename(name)
        if base not in ('status.jsonl', 'runs.csv'):
            continue
        path = name if os.path.isabs(name) else os.path.join(ROOT, name)
        if not os.path.isfile(path) or sha256(path) != want:
            bad.append('%s %s' % (name, 'missing' if not os.path.isfile(path) else 'differs from the recorded sha256'))
            continue
        if base == 'status.jsonl':
            queues.append(path)
        else:
            runs_csv = path
    if bad:
        raise SystemExit('input error: the runner records or runs.csv named in table1_extra.json inputs: %s'
                         % '; '.join(bad))
    return queues, runs_csv


def runner_outcomes(queues):
    """job -> outcome of its last final 'end' record of the runner, else of its last 'end' record (the rule of the
    verifier's load_runner_records), over the status.jsonl files in the order of table1_extra.json 'inputs'."""
    out = {}
    for path in queues:
        with open(path, encoding='utf-8') as fh:
            for ln in fh:
                try:
                    r = json.loads(ln) if ln.strip() else None
                except ValueError:
                    raise SystemExit('input error: %s holds a line that is not JSON' % path)
                if not isinstance(r, dict) or r.get('event') != 'end' or not r.get('id'):
                    continue
                prev = out.get(r['id'])
                if prev is None or bool(r.get('final')) or not prev[1]:
                    out[r['id']] = (r.get('outcome'), bool(r.get('final')))
    return {j: o for j, (o, _) in out.items()}


def runs_csv_rows(runs_csv):
    """job -> (analysis_use True / False, outcome) of runs.csv."""
    if runs_csv is None:
        return {}
    return {r.get('job'): (str(r.get('analysis_use')).strip().lower() in ('1', 'true', 'yes'),
                           (r.get('outcome') or '').strip()) for r in read_csv(runs_csv)}


def not_ok_job(job, outcomes, rows):
    """The job's final runner outcome is a failure and its runs.csv row has an outcome other than 'ok' and
    analysis_use false (class not_ok_record)."""
    runner = (outcomes.get(job) or '').strip() if isinstance(outcomes.get(job), str) else ''
    use, agg = rows.get(job, (None, ''))
    return bool(runner) and runner not in RUNNER_OK and bool(agg) and agg != 'ok' and use is False


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


def summarize(rows, by_job, by_dir):
    """Counts, runs per arm and the largest absolute difference per column of the rows of one class."""
    runs = {}
    for r in rows:
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
    for r in rows:
        col = column_of(r)
        d = abs_diff(r)
        best = largest.get(col)
        if best is None or (d is not None and (best['abs_diff'] is None or d > best['abs_diff'])):
            largest[col] = {'target': col[0], 'metric': col[1], 'column': col[2], 'abs_diff': d, 'key': r.get('key'),
                            'ours': r.get('ours'), 'theirs': r.get('theirs'), 'scope': r.get('scope'), 'rows': 0,
                            'rows_without_abs_diff': 0}
    for r in rows:
        e = largest[column_of(r)]
        e['rows'] += 1
        e['rows_without_abs_diff'] += int(abs_diff(r) is None)
    return {
        'differences': len(rows),
        'analysis_differences': sum(r.get('scope') == 'analysis' for r in rows),
        'differences_without_abs_diff': sum(abs_diff(r) is None for r in rows),
        'runs': len(runs),
        'runs_per_arm': dict(sorted(per_arm.items())),
        'run_list': [{'run_dir': d, 'arm': e['arm'], 'jobs': sorted(e['jobs']), 'analysis': e['analysis']}
                     for d, e in sorted(runs.items())],
        'largest_abs_diff': [largest[k] for k in sorted(largest)],
    }


def count(items):
    out = {}
    for k in items:
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


def report(out_dir):
    paths, shas = checked_inputs(out_dir)
    diffs = read_csv(paths['differences.csv'])
    runs_rows = read_csv(paths['runs_recomputed.csv'])
    by_job, by_dir, row_of = runs_index(runs_rows)
    with open(paths['table1_extra.json'], encoding='utf-8') as fh:
        t1 = json.load(fh)
    plans = read_csv(paths['cause_plans.csv'])

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

    runtime_gpu_differs = {r.get('key') for r in diffs if r['target'] == 'runs.csv' and
                           (r.get('their_field') or r.get('field')) in RUNTIME_GPU}
    outcomes, rows, sources = {}, {}, {'runner_records': [], 'runs_csv': None}
    if any(not_ok_candidate(r) for r in diffs):
        queues, runs_csv = recorded_inputs(t1)
        outcomes, rows = runner_outcomes(queues), runs_csv_rows(runs_csv)
        sources = {'runner_records': queues, 'runs_csv': runs_csv}
        shas.update({p: sha256(p) for p in queues + ([runs_csv] if runs_csv else [])})
    classes = {CLASS: [], 'F3': [], IN_FLIGHT: [], NOT_OK: [], UNEXPLAINED: []}
    for r in diffs:
        cause = r.get('cause') or ''
        name = next((c for c, causes in CLASS_CAUSES.items() if cause in causes), None)
        if name is None and is_in_flight(r, row_of, runtime_gpu_differs):
            name = IN_FLIGHT
        if name is None and not_ok_candidate(r):
            if not_ok_job(r.get('key') or '', outcomes, rows):
                name = NOT_OK
        classes[name or UNEXPLAINED].append(r)

    within = dict(sorted((comp.get('agree_within_bounds_by_cause') or {}).items()))
    c_f1 = summarize(classes[CLASS], by_job, by_dir)
    c_f1['agree_within_bounds'] = within.get(CLASS, 0)
    f1_plans = [p for p in plans if p.get('cause') == CLASS]
    c_f1['plans'] = {'plans': len(f1_plans), 'run_dirs': len({p.get('run_dir') for p in f1_plans})}
    c_f3 = summarize(classes['F3'], by_job, by_dir)
    c_f3['by_cause'] = count(r.get('cause') for r in classes['F3'])
    c_f3['agree_within_bounds'] = sum(within.get(c, 0) for c in CLASS_CAUSES['F3'])
    f3_plans = [p for p in plans if p.get('cause') == 'F3']
    c_f3['plans'] = {'plans': len(f3_plans), 'run_dirs': len({p.get('run_dir') for p in f3_plans})}
    c_fl = summarize(classes[IN_FLIGHT], by_job, by_dir)
    c_fl['runs_ending_with_job_in_flight'] = sum(ended_in_flight(r) for r in runs_rows)
    c_fl['runs_recomputed'] = len(runs_rows)
    c_no = summarize(classes[NOT_OK], by_job, by_dir)
    c_no['jobs'] = {j: {'runner_outcome': outcomes[j], 'runs_csv_outcome': rows[j][1]}
                    for j in sorted({r.get('key') for r in classes[NOT_OK]})}
    c_no['sources'] = sources
    c_un = summarize(classes[UNEXPLAINED], by_job, by_dir)
    c_un['by_cause'] = count(r.get('cause') or UNCLASSIFIED for r in classes[UNEXPLAINED])
    c_un['by_column'] = count('%s|%s|%s' % (r['target'], r.get('their_field') or r.get('field') or '', r.get('scope'))
                              for r in classes[UNEXPLAINED])

    checks = {'status_final': t1.get('status') == 'final',
              'registered_verifier': t1.get('script_sha256') == REGISTERED_VERIFIER,
              'runs_csv_values_false': (t1.get('options') or {}).get('runs_csv_values') is False}
    outcome = 'AGREE' if not diffs else ('pre-specified classes only' if not classes[UNEXPLAINED]
                                         else 'verification failure')
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
        'differences_by_class': {k: len(v) for k, v in classes.items()},
        'class_F1': c_f1,
        'class_F3': c_f3,
        'class_in_flight': c_fl,
        'class_not_ok_record': c_no,
        'unexplained': c_un,
        'outcome': outcome,
        'release_checks': checks,
        'release': outcome if all(checks.values()) else 'not final',
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
    print('status %s, verdict %s: %d differences (by cause %s; by class %s); runs per arm: F1 %s, F3 %s, in_flight %s, '
          'not_ok_record %s, unexplained %s; outcome: %s; release: %s'
          % (rep['status'], rep['verdict'], rep['differences'], rep['differences_by_cause'],
             rep['differences_by_class'],
             *[{k: v['runs'] for k, v in rep[c]['runs_per_arm'].items()}
               for c in ('class_F1', 'class_F3', 'class_in_flight', 'class_not_ok_record', 'unexplained')],
             rep['outcome'], rep['release']), file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
