#!/usr/bin/env python3
"""NEGATIVE tests of the resolution rule (g8f_lib.py resolution) in the G8FULL dry run: a copy of the scratch tree's
second verify_table1_extra.py output with one change, its SHA256SUMS and table1_extra.json counts made consistent, so
that f1_class_report.py accepts it. Writes only under /tmp/G8FULL/neg/. Run from /tmp/G8FULL/root.

  variant A  one more difference row without a cause outside R_cond (runs.csv dmr of a used run, scope analysis)
  variant B  a value_a row for the key of an R_cond pairing-status row (a numeric difference on that pair)
  variant C  runs_recomputed.csv: the first run that an R_cond pairing-status row names as missing gets R_cond 0.5 from
             2 conflict plans (R_cond defined on the recomputed side)
  python ... tamper_verify.py VARIANT VERIFY_DIR   (prints the copy's directory)
"""
import csv
import hashlib
import io
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path('/tmp/G8FULL/root')
if Path.cwd().resolve() != ROOT:
    sys.exit(f'run from {ROOT}')
variant, src = sys.argv[1], Path(sys.argv[2])
dst = Path('/tmp/G8FULL/neg') / f'vx_{variant}'
shutil.rmtree(dst, ignore_errors=True)
shutil.copytree(src, dst)


def rows(p):
    with open(p, newline='', encoding='utf-8') as fh:
        r = csv.DictReader(fh)
        return r.fieldnames, list(r)


def write(p, fields, data):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator='\n')
    w.writeheader()
    w.writerows(data)
    p.write_text(buf.getvalue(), encoding='utf-8')


fields, diffs = rows(dst / 'differences.csv')
t1 = json.loads((dst / 'table1_extra.json').read_text())
note_re = re.compile(r"^status 'realized_r_cond missing: (?P<conds>[^']+)'$")
rc_rows = [r for r in diffs if r['target'] == 'paired_differences.csv' and '/r_cond/' in r['key']
           and note_re.match(r.get('note') or '')]
if variant in ('A', 'B'):
    if variant == 'A':
        rf, runs = rows(dst / 'runs_recomputed.csv')
        job = json.loads(next(r['jobs'] for r in runs if r.get('dmr')))[0]
        new = dict.fromkeys(fields, '')
        new.update(target='runs.csv', key=job, field='dmr', their_field='dmr', ours='0.5', theirs='0.4',
                   abs_diff='0.1', tolerance='1e-06', status='differ', scope='analysis', value_source='raw')
    else:
        new = dict.fromkeys(fields, '')
        new.update(target='paired_differences.csv', key=rc_rows[0]['key'], field='value_a', their_field='value_a',
                   ours='0.5', theirs='', status='differ', scope='analysis', value_source='raw')
    diffs.append(new)
    write(dst / 'differences.csv', fields, diffs)
    comp = t1['comparisons']
    comp['differences'] += 1
    for k in ('differences_by_cause', 'analysis_differences_by_cause'):
        comp[k]['unclassified'] = comp[k].get('unclassified', 0) + 1
    (dst / 'table1_extra.json').write_text(json.dumps(t1, indent=1) + '\n')
elif variant == 'C':
    conds = [c.strip() for c in note_re.match(rc_rows[0]['note']).group('conds').split(',')]
    route = rc_rows[0]['key'].rsplit('/', 1)[1]
    arm = re.match(r'^(.+)_k[0-9.]+_s[0-9]+$', conds[0]).group(1)
    cells_path = next(Path(p) for p in t1['inputs'] if p.endswith('/cells.csv'))
    _, cells = rows(ROOT / cells_path)
    job = next(json.loads(c['jobs'])[0] for c in cells if c['condition'] == conds[0] and c['route_id'] == route)
    rf, runs = rows(dst / 'runs_recomputed.csv')
    hit = [r for r in runs if job in json.loads(r['jobs'])]
    hit[0].update(r_cond='0.5', conflict_plans='2')
    write(dst / 'runs_recomputed.csv', rf, runs)
    print(f'variant C: {job} ({arm}, route {route}) now R_cond 0.5 from 2 conflict plans', file=sys.stderr)
else:
    sys.exit(f'unknown variant {variant}')
sums = []
for ln in (dst / 'SHA256SUMS').read_text().splitlines():
    h, _, n = ln.partition('  ')
    sums.append(f'{hashlib.sha256((dst / n).read_bytes()).hexdigest()}  {n}')
(dst / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')
print(dst)
