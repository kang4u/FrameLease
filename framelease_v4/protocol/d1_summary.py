#!/usr/bin/env python3
"""Training-route summary for decision point D1 (framelease_v4/PROTOCOL.md Sec. 4.8). CPU only; reads only the
Phase-1 stage specs, the training-route run directories under outputs/framelease_v4/tuning/ and the stage selections;
writes only under outputs/framelease_v4/tuning/d1/ (--write).

  cd /home/kang/Desktop/DAC
  .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/d1_summary.py --variant FULL \
      --queue outputs/framelease_v4/queue_p1 [--no-realized] [--write]

Content: every block of the variant whose job file exists (the two references and every candidate of every grid), per
candidate over the block's routes:
  outcomes        ok / agent_crashed / sim_failure / pending counts (select_stage.job_outcome, --queue as there)
  mean_ds_kept    the selection statistic: mean DS over the stage's kept routes ('Agent crashed' = 0)
  ds / rc / sr    mean DS, route completion and Bench2Drive success over the candidate's valid runs
  fallback_ratio  share of all control ticks in the full-brake fallback (metrics_v4 deadline_miss_ratio), mean
  dmr             deadline miss rate from the first commit on (deadline_miss_ratio_after_first_commit), mean
  eir             executed-invalid tick rate from the actor log (realized_invalid_tick_ratio), mean
  r_cond          closed-loop R_cond, pooled: realized misses / conflict plans over the candidate's runs
  p_both          P_both pooled over the shield decision epochs (None for arms without a shield)
plus each block's kept / dropped routes, pending jobs, set-up failure flags, and the stage selection if it exists
(survivors or the selected candidate; T22 means of the final FULL stages). Metrics come from
framelease_v4/arms/metrics_v4.run_metrics (realized validity with --realized, the default). Test routes are refused.
D1 is the user's decision; this script only tabulates.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402
from framelease_v4.protocol import select_stage as SS  # noqa: E402

SCHEMA = 'framelease_v4.d1_summary/1'
OUT_DIR = ROOT / 'outputs/framelease_v4/tuning/d1'
COLUMNS = ('outcomes', 'mean_ds_kept', 'ds', 'rc', 'sr', 'fallback_ratio', 'dmr', 'eir', 'r_cond', 'p_both')


def _mean(values):
    v = [float(x) for x in values if x is not None]
    return (sum(v) / len(v)) if v else None


def candidate_summary(row, root=ROOT, realized=True, metrics_fn=None):
    """D1 columns of one stage-table row (select_stage.stage_table)."""
    from framelease_v4.arms import metrics_v4 as MV
    metrics_fn = metrics_fn or MV.run_metrics
    runs = []
    for r, o in sorted(row['per_route'].items(), key=lambda kv: int(kv[0])):
        if o['outcome'] == 'ok' and o.get('run_dir'):
            m = metrics_fn(SS._abs(o['run_dir'], root), realized)
            if m is not None:
                runs.append(m)
    conflicts = sum(int(m.get('realized_conflict_plans') or 0) for m in runs)
    misses = sum(int(m.get('realized_misses') or 0) for m in runs)
    epochs = sum(int(m.get('shield_epochs') or 0) for m in runs)
    both = sum(float(m.get('p_both') or 0.0) * int(m.get('shield_epochs') or 0) for m in runs)
    return {'candidate': row['candidate'], 'arm': row['arm'], 'tag': row['tag'], 'policy_params': row['policy_params'],
            'envelope': (row.get('envelope') or {}).get('label'), 'reused_from': row.get('reused_from'),
            'outcomes': row['outcomes'], 'n_kept': row['n'], 'mean_ds_kept': row['mean_ds'], 'valid_runs': len(runs),
            'ds': _mean(m.get('driving_score') for m in runs), 'rc': _mean(m.get('route_completion') for m in runs),
            'sr': _mean(m.get('success') for m in runs),
            'fallback_ratio': _mean(m.get('deadline_miss_ratio') for m in runs),
            'dmr': _mean(m.get('deadline_miss_ratio_after_first_commit') for m in runs),
            'eir': _mean(m.get('realized_invalid_tick_ratio') for m in runs) if realized else None,
            'r_cond': (misses / conflicts) if (realized and conflicts) else None,
            'realized_conflicts': conflicts if realized else None, 'realized_misses': misses if realized else None,
            'p_both': (both / epochs) if epochs else None, 'shield_epochs': epochs}


def block_summary(variant, block, root=ROOT, jobs_dir=None, sel_dir=None, states=None, realized=True,
                  metrics_fn=None):
    spec, spec_path = PJ.load_stage_spec(variant, block, jobs_dir)
    t = SS.stage_table(spec, root, states)              # refuses test routes and output directories outside tuning/
    sel = None
    if spec['grid'] != 'ref':
        try:
            s, sha, path = PJ.load_selection(variant, block, sel_dir, jobs_dir)
            sel = {'path': PJ.rel(path), 'sha256': sha, 'survivors': s.get('survivors'), 'selected': s.get('selected'),
                   'mean_ds_T22': {r['candidate']: r.get('mean_ds_T22') for r in s['table'] if 'mean_ds_T22' in r}
                   or None}
        except (FileNotFoundError, ValueError):
            sel = None
    return {'block': block, 'block_no': spec['block_no'], 'grid': spec['grid'], 'stage': spec['stage'],
            'route_set': spec['route_set'], 'routes': t['routes'], 'kept_routes': t['kept_routes'],
            'dropped_routes': t['dropped_routes'], 'pending': len(t['pending']), 'flags': t['flags'],
            'stage_spec': PJ.rel(spec_path), 'stage_spec_sha256': PJ.sha256_file(spec_path), 'selection': sel,
            'candidates': [candidate_summary(row, root, realized, metrics_fn)
                           for row in sorted(t['table'], key=lambda r: r['order'])]}


def summarize(variant, root=ROOT, jobs_dir=None, sel_dir=None, queue_dir=None, realized=True, metrics_fn=None,
              freeze_path=SS.FREEZE_PATH):
    states = SS.queue_states(queue_dir)
    blocks = []
    for block, (no, grid, stage, rset, dep) in sorted(PJ.BLOCKS[variant].items(), key=lambda kv: kv[1][0]):
        _, spec_path, _ = PJ.stage_paths(variant, block, jobs_dir)
        if spec_path.is_file():
            blocks.append(block_summary(variant, block, root, jobs_dir, sel_dir, states, realized, metrics_fn))
    freeze = None
    if freeze_path is not None and Path(freeze_path).is_file():
        doc = json.loads(Path(freeze_path).read_text(encoding='utf-8'))
        if doc.get('variant') == variant:
            freeze = {k: doc.get(k) for k in ('L_star', 'd_star', 'A_star', 'event_star', 'fl_risk')}
            freeze['sha256'] = PJ.sha256_file(freeze_path)
    return {'schema': SCHEMA, 'variant': variant, 'training_routes_only': True, 'realized': bool(realized),
            'queue': PJ.rel(queue_dir) if queue_dir else None, 'blocks': blocks, 'tuning_freeze': freeze,
            'columns': {'mean_ds_kept': 'selection statistic: mean DS over the kept routes (agent crash = 0)',
                        'ds': 'mean DS over valid runs', 'rc': 'mean route completion', 'sr': 'Bench2Drive success rate',
                        'fallback_ratio': 'mean share of control ticks in fallback (all ticks)',
                        'dmr': 'mean deadline miss rate from the first commit on',
                        'eir': 'mean executed-invalid tick rate (actor log, standard validity)',
                        'r_cond': 'closed-loop R_cond pooled over runs (misses / conflict plans)',
                        'p_both': 'P_both pooled over shield decision epochs'},
            'script_sha256': PJ.sha256_file(Path(__file__)), 'written': time.strftime('%Y-%m-%dT%H:%M:%S%z')}


def _f(v, d=1, pct=False):
    if v is None:
        return '-'
    return f'{100 * v:.{d}f}' if pct else f'{v:.{d}f}'


def markdown(doc):
    L = [f'# D1 training-route summary, variant {doc["variant"]} (framelease_v4/protocol/d1_summary.py)', '',
         f'Written {doc["written"]}; training routes only; realized validity {"on" if doc["realized"] else "off"}. '
         'Percentages: SR, fallback ratio, DMR, EIR, R_cond, P_both.', '']
    for b in doc['blocks']:
        sel = b['selection'] or {}
        L.append(f'## {b["block"]} (grid {b["grid"]}, stage {b["stage"]}, {b["route_set"]}): '
                 f'{len(b["kept_routes"])}/{len(b["routes"])} routes kept, {b["pending"]} jobs pending')
        if b['dropped_routes']:
            L.append(f'Dropped routes: {json.dumps(b["dropped_routes"], sort_keys=True)}')
        for f in b['flags']:
            L.append(f'FLAG {f["candidate"]}: {f["setup_failures"]} set-up failures ({f["routes"]})')
        if sel:
            L.append(f'Selection {sel["path"]}: ' + (f'survivors {sel["survivors"]}' if sel.get('survivors') else
                                                     f'selected {sel["selected"]}'))
        L += ['', '| candidate | outcomes | mean DS (kept) | DS | RC | SR | fallback | DMR | EIR | R_cond | P_both |',
              '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        for c in b['candidates']:
            mark = ''
            if sel.get('selected') == c['candidate']:
                mark = ' (selected)'
            elif c['candidate'] in (sel.get('survivors') or []):
                mark = ' (survivor)'
            L.append(f'| {c["candidate"]}{mark} | {json.dumps(c["outcomes"], sort_keys=True)} | '
                     f'{_f(c["mean_ds_kept"])} | {_f(c["ds"])} | {_f(c["rc"])} | {_f(c["sr"], 0, True)} | '
                     f'{_f(c["fallback_ratio"], 1, True)} | {_f(c["dmr"], 1, True)} | {_f(c["eir"], 2, True)} | '
                     f'{_f(c["r_cond"], 1, True)} | {_f(c["p_both"], 1, True)} |')
        L.append('')
    if doc.get('tuning_freeze'):
        L.append(f'Tuning freeze: {json.dumps(doc["tuning_freeze"], sort_keys=True)}')
    return '\n'.join(L) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--variant', choices=PJ.VARIANTS, required=True)
    ap.add_argument('--queue', type=Path, default=None, help='gpu_queue directory (status.jsonl)')
    ap.add_argument('--no-realized', action='store_true', help='skip the actor-log realized validity (faster)')
    ap.add_argument('--write', action='store_true', help=f'write {PJ.rel(OUT_DIR)}/<VARIANT>_d1_summary.{{json,md}}')
    ap.add_argument('--jobs-dir', type=Path, default=PJ.JOBS_DIR)
    ap.add_argument('--selection-dir', type=Path, default=PJ.SELECTION_DIR)
    a = ap.parse_args(argv)
    try:
        doc = summarize(a.variant, ROOT, a.jobs_dir, a.selection_dir, a.queue, not a.no_realized)
    except (SS.SelectionError, FileNotFoundError, ValueError, KeyError, PermissionError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2
    md = markdown(doc)
    print(md)
    if a.write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        for ext, text in (('json', json.dumps(doc, indent=1, sort_keys=True) + '\n'), ('md', md)):
            path = OUT_DIR / f'{a.variant}_d1_summary.{ext}'
            path.write_text(text, encoding='utf-8')
            print(f'wrote {path}  sha256 {PJ.sha256_file(path)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
