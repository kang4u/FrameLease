"""Read-only recount behind A10 finding 1 (commit audit, null margins) on the R7 development aggregation
build/R7/dev/agg_p1 (P1 training-route runs only; it reads no test-route run):
  * the audited fl_heuristic runs of the stages lease_s1 / lease_s2 per stage and candidate, the runs with a violation
    and their 'margin' violations (aggregate.json, commit_audit.runs);
  * the accepted commits with a null margin and n_relevant > 0 in the violating runs, by (validity reason, n_computed,
    min_g_m is None), from each run's raw/agent/framelease/jobs.jsonl.

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/r2_margin_null.py
"""
import collections
import gzip
import json
import os
import re
import sys

ROOT = '/home/kang/Desktop/DAC'
AGG = os.path.join(ROOT, 'outputs/framelease_v4/build/R7/dev/agg_p1/aggregate.json')


def lease_stage_counts(runs):
    """{(stage, candidate): n} of the audited non-smoke fl_heuristic lease-stage runs, of those with a violation, and
    their 'margin' violations."""
    audited, violating, margin = collections.Counter(), collections.Counter(), collections.Counter()
    for r in runs:
        d = r['run_dir']
        stage, cand = re.search(r'/(lease_s[12])/', d), re.search(r'/fl_heuristic_(B0|E5|E10)_', d)
        if not (stage and cand):
            continue
        key = (stage.group(1), cand.group(1))
        audited[key] += 1
        if r['n_violations']:
            violating[key] += 1
            margin[key] += r['violations'].get('margin', 0)
    return audited, violating, margin


def null_margin_classes(runs):
    """Counter of (reason, n_computed, min_g_m is None) over the accepted null-margin commits with a relevant agent in
    the violating runs, and the number of violating runs."""
    c, n_runs = collections.Counter(), 0
    for r in runs:
        if not r['n_violations']:
            continue
        n_runs += 1
        p = os.path.join(ROOT, r['run_dir'], 'raw/agent/framelease/jobs.jsonl')
        op, fn = (open, p) if os.path.exists(p) else (gzip.open, p + '.gz')
        with op(fn, 'rt') as fh:
            for ln in fh:
                j = json.loads(ln)
                for s in j.get('steps') or []:
                    cm = s.get('commit') or {}
                    v = s.get('validity') or {}
                    if cm.get('accepted') and cm.get('margin_at_commit_m') is None and (v.get('n_relevant') or 0) > 0:
                        c[(v.get('reason'), v.get('n_computed'), v.get('min_g_m') is None)] += 1
    return c, n_runs


def main():
    runs = json.load(open(AGG))['commit_audit']['runs']
    audited, violating, margin = lease_stage_counts(runs)

    def by_cand(cnt):
        out = {}
        for (_, cand), n in cnt.items():
            out[cand] = out.get(cand, 0) + n
        return dict(sorted(out.items()))
    print('audited fl_heuristic lease-stage runs', sum(audited.values()), by_cand(audited))
    print('with a violation', sum(violating.values()), by_cand(violating))
    print('margin violations', sum(margin.values()), by_cand(margin))
    c, n_runs = null_margin_classes(runs)
    print('violating runs', n_runs, 'flagged null-margin commits', sum(c.values()))
    for k, n in c.most_common():
        print(' (reason, n_computed, min_g_m is None)', k, n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
