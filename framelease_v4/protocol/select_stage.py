#!/usr/bin/env python3
"""Deterministic stage selection of the Phase-1 tuning (framelease_v4/PROTOCOL.md Sec. 4.2; CPU only, reads only
training-route run directories, writes only under outputs/framelease_v4/tuning/).

  cd /home/kang/Desktop/DAC
  .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/select_stage.py --variant FULL --stage lease_s1 \
      --queue outputs/framelease_v4/queue_p1 [--write]
  .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/select_stage.py --variant FULL --freeze [--write]

Input: the stage spec that framelease_v4/protocol/p1_jobs.py wrote next to the stage's job file (candidates in the
registered order, the job id and output directory of every candidate x route, runs reused from an earlier block),
the run directories of those jobs (config.json, metrics/result.json) and, with --queue, the runner's status.jsonl
(framelease_v2/gpu_queue.py; its own Runner.job_states decides which attempts counted and which record is final).

Per candidate x route (the outcome of a job):
  ok             the first valid official record (a route record whose status is not an execution failure): its DS
                 (score_composed). A valid record is final whatever the driving outcome.
  agent_crashed  no valid record after the retry, last attempt 'Agent crashed': DS = 0 for that candidate (the agent
                 code is part of the candidate).
  sim_failure    no valid record after the retry, any other cause (Simulation crashed, sensors invalid, agent set-up,
                 CARLA / wall-clock timeout, launch error, no record): the route is dropped from the stage for EVERY
                 candidate.
  pending        no final outcome yet: the stage is incomplete and no selection is written (--provisional writes
                 <stage>.provisional.json, which p1_jobs.py never reads).
When is a job final?
  with --queue   (the protocol's mode) a matching valid run directory, or the runner's final 'end' record. Attempts the
                 runner did not count (shared GPU lock busy, runner interrupted) never make a job final; a job that
                 the runner is re-trying after a final record (--retry-failed) is pending again. A runner record that
                 says 'ok' / 'result_with_warnings' but names no matching valid run directory of the candidate is an
                 ERROR (exit 2): the selection never turns it into a dropped route.
  without        inferred from the run directories alone: a valid record, or MAX_ATTEMPTS failed attempts with a
                 result, not counting attempts that only met a busy shared GPU lock (attempts that left no result are
                 not counted either, so such a job stays pending until --queue is given).
Flags: a candidate with REPEATED_SETUP_FAILURES or more attempts ending in "Agent couldn't be set up" in the stage is
flagged ('flags' in the output, printed as FLAG lines): the registered rule still drops those routes for every
candidate, but a configuration that cannot set up the agent is an implementation defect to investigate (and report at
D1) before the next block is generated.
Rules: mean DS over the stage's kept routes; ranking by mean DS, ties (difference < 1e-9) to the earlier candidate in
the registered order. A non-final stage keeps the top ceil(K/2) (ties at the cut to the earlier candidate). The final
stage selects the best mean DS: FULL over all routes of T22 the survivor ran (stage-1 kept routes + stage-2 kept
routes; the d = 10 heuristic candidate's runs are the lease grid's runs at L*), TRIMMED over the T22a kept routes.
The reference block ('ref') is reported, not selected (framelease_v4/protocol/d1_summary.py tabulates it).
--freeze combines the final selections into outputs/framelease_v4/tuning/selection.json (Sec. 4.9): L* (envelope file
and sha256, validity std), d*, A*, theta* and A_hb*, the fl_risk lease point (FULL, if L* = B0: the better of E5 / E10
on lease_s1), every stage table and the sha256 of this script and of p1_jobs.py.
Exit codes: 0 selected / frozen, 2 error (unknown or reference stage, missing files, inconsistent runner records),
3 not selected (jobs without a final outcome).
"""
from __future__ import annotations

import argparse
import functools
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402

EXECUTION_FAILURES = ('Simulation crashed', "Agent's sensors were invalid", "Agent couldn't be set up",
                      'Agent crashed')            # framelease_v2.gpu_queue.EXECUTION_FAILURE_STATUS
AGENT_CRASH = 'Agent crashed'
SETUP_FAILURE = "Agent couldn't be set up"
LOCK_HELD_MARKER = 'shared GPU lock is held'     # framelease_v2.gpu_queue.LOCK_HELD_MARKER (attempt not counted)
OK_OUTCOMES = ('ok', 'result_with_warnings')     # framelease_v2.gpu_queue.OK_OUTCOMES
MAX_ATTEMPTS = 2                                  # one infrastructure retry (PROTOCOL Sec. 8.4)
REPEATED_SETUP_FAILURES = 2
TIE_EPS = 1e-9
FREEZE_PATH = ROOT / 'outputs/framelease_v4/tuning/selection.json'
FREEZE_SCHEMA = 'framelease_v4.tuning_selection/1'


class SelectionError(RuntimeError):
    """Inconsistent inputs (e.g. a runner 'ok' without a matching run directory): never silently selected."""


class StageIncomplete(RuntimeError):
    """Jobs without a final outcome: no selection is written."""


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def _abs(p, root=ROOT):
    p = Path(p)
    return p if p.is_absolute() else Path(root) / p


def _same_path(a, b, root=ROOT):
    try:
        return _abs(a, root).resolve() == _abs(b, root).resolve()
    except (OSError, RuntimeError, TypeError):
        return False


def read_run(run_dir):
    """The fields of one launcher run directory the selection needs (None without a config)."""
    run_dir = Path(run_dir)
    cfg = _read_json(run_dir / 'config.json')
    if not isinstance(cfg, dict):
        return None
    res = _read_json(run_dir / 'metrics' / 'result.json')
    man = _read_json(run_dir / 'manifest.json') or {}
    v4 = cfg.get('v4') or {}
    scores = (res or {}).get('scores') or {}
    status = (res or {}).get('route_status')
    error = str((res or {}).get('error') or '') + ' ' + ' '.join(map(str, man.get('blockers') or []))
    rec = {'run_dir': PJ.rel(run_dir), 'path': str(run_dir.resolve()), 'name': run_dir.name,
           'route_id': str((cfg.get('route') or {}).get('route_id')),
           'v4_arm': cfg.get('v4_arm'), 'kappa': cfg.get('kappa'), 'seed': cfg.get('seed'),
           'policy_params': dict(((v4.get('agent') or {}).get('policy_params')) or {}),
           'envelope_sha256': cfg.get('envelope_sha256'), 'has_result': res is not None,
           'route_records': int((res or {}).get('route_records') or 0), 'route_status': status,
           'ds': scores.get('score_composed'), 'rc': scores.get('score_route'),
           'timed_out': (res or {}).get('timed_out'), 'manifest_status': man.get('status'),
           'lock_busy': LOCK_HELD_MARKER in error, 'setup_failure': SETUP_FAILURE in str(status)}
    rec['valid'] = bool(rec['has_result'] and rec['route_records'] > 0 and rec['ds'] is not None
                        and not any(m in str(status) for m in EXECUTION_FAILURES))
    return rec


def matches(rec, route, c):
    try:
        same = (rec['route_id'] == str(route) and rec['v4_arm'] == c['arm'] and float(rec['kappa']) == PJ.KAPPA
                and int(rec['seed']) == PJ.SEED)
    except (TypeError, ValueError):
        return False
    if not same or any(rec['policy_params'].get(k) != v for k, v in (c['policy_params'] or {}).items()):
        return False
    return c.get('envelope') is None or rec['envelope_sha256'] == c['envelope']['sha256']


def queue_states(queue_dir):
    """{job id: state} from a gpu_queue directory's status.jsonl, None without --queue. The state is the runner's own
    Runner.job_states entry (attempts, counted, final, open, ends) plus 'after_final': a start / end record of the job
    after its last final record (a new attempt budget from --retry-failed)."""
    if not queue_dir:
        return None
    path = Path(queue_dir) / 'status.jsonl'
    if not path.is_file():
        raise FileNotFoundError(f'{path} not found (is {queue_dir} the queue directory the runner used?)')
    from framelease_v2 import gpu_queue as Q
    records = []
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    states = Q.Runner.job_states(records)
    last_final, after = {}, {}
    for i, r in enumerate(records):
        if r.get('event') in ('start', 'end') and 'id' in r:
            if r['event'] == 'end' and r.get('final'):
                last_final[r['id']] = i
                after[r['id']] = False
            elif r['id'] in last_final:
                after[r['id']] = True
    for jid, s in states.items():
        s['after_final'] = bool(after.get(jid))
    return states


def queue_finals(queue_dir):
    """{job id: last final 'end' record} of a gpu_queue directory (status.jsonl)."""
    return {jid: s['final'] for jid, s in (queue_states(queue_dir) or {}).items() if s.get('final') is not None}


def _job_runs(job, route, c, root):
    runs = Path(root) / job['output_dir'] / 'runs'
    recs = []
    if runs.is_dir():
        for d in sorted(runs.iterdir()):
            r = read_run(d) if d.is_dir() else None
            if r is not None and matches(r, route, c):
                recs.append(r)
    return recs


def _failed_final(base, status, run_dir, cause):
    if AGENT_CRASH in str(status):
        return {**base, 'outcome': 'agent_crashed', 'ds': 0.0, 'run_dir': run_dir, 'status': status}
    return {**base, 'outcome': 'sim_failure', 'ds': None, 'run_dir': run_dir, 'cause': cause}


def job_outcome(job, route, c, root=ROOT, states=None):
    """Outcome dict of one candidate x route job (see the module docstring). states: queue_states() or None."""
    recs = _job_runs(job, route, c, root)
    valid = [r for r in recs if r['valid']]
    base = {'job': job['id'], 'attempts_found': len(recs),
            'setup_failures': sum(1 for r in recs if r['setup_failure'])}
    if states is not None:
        s = states.get(job['id']) or {}
        fin = s.get('final')
        ends = s.get('ends') or []
        base['queue'] = {'attempts': int(s.get('attempts') or 0),
                         'counted': sum(1 for e in ends if e.get('counted')),
                         'final_outcome': None if fin is None else fin.get('outcome')}
        seen = {r['path'] for r in recs}
        for e in ends:                    # set-up failures the runner saw in attempts without a matching directory
            st = str((e.get('result') or {}).get('route_status'))
            rd = e.get('run_dir')
            if SETUP_FAILURE in st and not (rd and any(_same_path(rd, p, root) for p in seen)):
                base['setup_failures'] += 1
        if fin is not None and s.get('after_final'):
            return {**base, 'outcome': 'pending', 'cause': 'the runner is re-trying the job after its final record '
                                                           '(--retry-failed)'}
        if fin is not None and fin.get('outcome') in OK_OUTCOMES:
            rd = fin.get('run_dir')
            match = next((r for r in recs if rd and _same_path(rd, r['path'], root)), None)
            if match is None or not match['valid']:
                raise SelectionError(
                    f'{job["id"]}: the runner\'s final record says {fin.get("outcome")!r} but its run directory '
                    f'{rd!r} is not a matching valid run of candidate {c.get("name", c["arm"])} '
                    f'(matching run directories: {[r["run_dir"] for r in recs]}); fix or explain this before selecting')
            out = {**base, 'outcome': 'ok', 'ds': float(match['ds']), 'run_dir': match['run_dir'],
                   'status': match['route_status']}
            if valid and valid[0] is not match:
                out['warning'] = f'{len(valid)} valid records; the runner\'s final one is used'
            return out
        if valid:
            r = valid[0]
            out = {**base, 'outcome': 'ok', 'ds': float(r['ds']), 'run_dir': r['run_dir'], 'status': r['route_status']}
            if fin is not None:
                out['warning'] = f'the runner\'s final outcome is {fin.get("outcome")!r} but a valid record exists'
            elif len(valid) > 1:
                out['warning'] = f'{len(valid)} valid records; the first is the final one'
            return out
        if fin is None:
            return {**base, 'outcome': 'pending',
                    'cause': f'no runner final record yet ({base["queue"]["counted"]} counted of '
                             f'{base["queue"]["attempts"]} attempts; {len(recs)} run directories)'}
        res = fin.get('result') or {}
        status = res.get('route_status')
        rd = fin.get('run_dir')
        match = next((r for r in recs if rd and _same_path(rd, r['path'], root)), None)
        if status is None and match is not None:
            status = match['route_status']
        return _failed_final(base, status, match['run_dir'] if match else rd,
                             f'queue: {fin.get("outcome")} ({status})')
    # ------------------------------------------------------------ no queue: infer from the run directories
    if valid:
        r = valid[0]
        out = {**base, 'outcome': 'ok', 'ds': float(r['ds']), 'run_dir': r['run_dir'], 'status': r['route_status']}
        if len(valid) > 1:
            out['warning'] = f'{len(valid)} valid records; the first is the final one'
        return out
    counted = [r for r in recs if r['has_result'] and not r['lock_busy']]
    if not counted:
        return {**base, 'outcome': 'pending', 'cause': 'no run yet' if not recs else
                'attempts without a counted result (run the selection with --queue)'}
    last = counted[-1]
    status = last['route_status']
    if len(counted) < MAX_ATTEMPTS:
        return {**base, 'outcome': 'pending', 'cause': f'failed attempt ({status}) awaiting its retry',
                'run_dir': last['run_dir']}
    cause = str(status) if last['route_records'] else f'no official route record ({status})'
    return _failed_final(base, status, last['run_dir'], cause)


def check_training(spec):
    train = PJ.training_routes()
    test = {r['route_id'] for r in PJ.route_split()['test']}
    for r in spec['routes']:
        if r not in train or r in test:
            raise PermissionError(f'route {r} is not a training route: the selection reads training routes only')
    for c in spec['candidates']:
        for r, job in c['jobs'].items():
            if not str(job['output_dir']).startswith(PJ.TUNING_REL + '/'):
                raise PermissionError(f'{job["id"]}: output directory outside {PJ.TUNING_REL}')


def setup_flags(per):
    """Candidates with REPEATED_SETUP_FAILURES or more "Agent couldn't be set up" attempts in the stage."""
    flags = []
    for name, rows in per.items():
        n = sum(int(o.get('setup_failures') or 0) for o in rows.values())
        if n >= REPEATED_SETUP_FAILURES:
            flags.append({'candidate': name, 'setup_failures': n,
                          'routes': sorted((r for r, o in rows.items() if o.get('setup_failures')), key=int),
                          'flag': "repeated agent set-up failures (Agent couldn't be set up): the registered rule "
                                  'drops these routes for every candidate; a candidate-specific configuration defect '
                                  'is likely and is investigated (and reported at D1) before the next block'})
    return flags


def stage_table(spec, root=ROOT, states=None):
    """Per candidate x route outcomes, dropped routes, flags and mean DS over the kept routes."""
    check_training(spec)
    routes = list(spec['routes'])
    per = {}
    for c in spec['candidates']:
        per[c['name']] = {r: job_outcome(c['jobs'][r], r, c, root, states) for r in routes}
    pending = [f'{n} x {r}: {o["cause"]}' for n, rows in per.items() for r, o in rows.items() if o['outcome'] == 'pending']
    dropped = {}
    for n, rows in per.items():
        for r, o in rows.items():
            if o['outcome'] == 'sim_failure':
                dropped.setdefault(r, []).append(f'{n}: {o["cause"]}')
    kept = [r for r in routes if r not in dropped]
    table = []
    for c in spec['candidates']:
        vals = [per[c['name']][r]['ds'] for r in kept if per[c['name']][r]['outcome'] in ('ok', 'agent_crashed')]
        counts = {}
        for r in routes:
            o = per[c['name']][r]['outcome']
            counts[o] = counts.get(o, 0) + 1
        table.append({'candidate': c['name'], 'order': c['order'], 'arm': c['arm'], 'tag': c['tag'],
                      'policy_params': c['policy_params'], 'envelope': c.get('envelope'),
                      'reused_from': c.get('reused_from'), 'n': len(vals),
                      'mean_ds': (sum(vals) / len(vals)) if vals else None,
                      'outcomes': counts, 'per_route': per[c['name']]})
    return {'routes': routes, 'kept_routes': kept, 'dropped_routes': dropped, 'pending': pending, 'table': table,
            'flags': setup_flags(per)}


def rank(names_orders_means):
    """Names by mean DS (descending); |difference| < 1e-9 counts as a tie, which goes to the earlier candidate."""
    def cmp(a, b):
        if a[2] > b[2] + TIE_EPS:
            return -1
        if b[2] > a[2] + TIE_EPS:
            return 1
        return -1 if a[1] < b[1] else (1 if a[1] > b[1] else 0)
    return [x[0] for x in sorted(names_orders_means, key=functools.cmp_to_key(cmp))]


def check_stage_name(variant, stage):
    """Clean errors for a stage name that cannot be selected (unknown block, or the reference block)."""
    blocks = PJ.BLOCKS[variant]
    if stage not in blocks:
        raise ValueError(f'{variant} has no stage {stage!r}; stages: '
                         f'{", ".join(b for b, v in blocks.items() if v[1] != "ref")}')
    if blocks[stage][1] == 'ref':
        raise ValueError(f'{variant} {stage!r} is the reference block (Fixed Deep, Fast Only x T22): it is reported, '
                         'not selected (PROTOCOL Sec. 4.8); tabulate it with framelease_v4/protocol/d1_summary.py')


def select(variant, stage, root=ROOT, jobs_dir=None, sel_dir=None, queue_dir=None, provisional=False):
    check_stage_name(variant, stage)
    spec, spec_path = PJ.load_stage_spec(variant, stage, jobs_dir)
    if spec.get('grid') == 'ref':
        raise ValueError('the reference block is reported, not selected')
    states = queue_states(queue_dir)
    t = stage_table(spec, root, states)
    complete = not t['pending']
    if not complete and not provisional:
        raise StageIncomplete(f'{variant} {stage}: {len(t["pending"])} jobs have no final outcome yet, e.g. '
                              f'{t["pending"][:3]}' + ('' if queue_dir else ' (give --queue: the runner decides which '
                                                                            'attempts are final)')
                              + ' (--provisional writes a provisional table)')
    if not t['kept_routes']:
        raise StageIncomplete(f'{variant} {stage}: every route was dropped')
    out = {'schema': PJ.SELECTION_SCHEMA, 'variant': variant, 'stage': stage, 'grid': spec['grid'],
           'stage_no': spec['stage'], 'final': bool(spec['final_stage']), 'complete': complete,
           'provisional': not complete, 'stage_spec': PJ.rel(spec_path), 'stage_spec_sha256': PJ.sha256_file(spec_path),
           'job_file': spec.get('job_file'), 'job_file_sha256': spec.get('job_file_sha256'),
           'queue': PJ.rel(queue_dir) if queue_dir else None,
           'finality': 'runner records (--queue)' if queue_dir else 'run directories only (no --queue)',
           'routes': t['routes'], 'kept_routes': t['kept_routes'],
           'dropped_routes': t['dropped_routes'], 'pending': t['pending'], 'table': t['table'], 'flags': t['flags'],
           'candidates': [{k: c[k] for k in ('name', 'arm', 'policy_params', 'tag', 'envelope', 'order')}
                          for c in spec['candidates']],
           'warnings': [f'{row["candidate"]} x {r}: {o["warning"]}' for row in t['table']
                        for r, o in row['per_route'].items() if o.get('warning')],
           'script_sha256': PJ.sha256_file(Path(__file__)), 'written': time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    stage_means = [(row['candidate'], row['order'], row['mean_ds'] if row['mean_ds'] is not None else -math.inf)
                   for row in t['table']]
    out['ranking'] = rank(stage_means)
    if not spec['final_stage']:
        k = int(spec['survive'])
        keep = set(out['ranking'][:k])
        out['survivors'] = [c['name'] for c in sorted(spec['candidates'], key=lambda c: c['order']) if c['name'] in keep]
        out['rule'] = f'stage 1 of successive halving: top ceil({len(spec["candidates"])}/2) = {k} by mean DS on ' \
                      f'{spec["route_set"]} kept routes; ties to the earlier candidate'
        return out
    if spec['stage'] == 2:                     # FULL: mean over the T22 routes the survivor ran
        prev, _, _ = PJ.load_selection(variant, spec['previous_stage'], sel_dir, jobs_dir)
        prev_rows = {row['candidate']: row for row in prev['table']}
        means = []
        for row in t['table']:
            p = prev_rows.get(row['candidate'])
            if p is None:
                raise ValueError(f'{stage}: candidate {row["candidate"]} has no stage-1 row')
            vals = [p['per_route'][r]['ds'] for r in prev['kept_routes']]
            vals += [row['per_route'][r]['ds'] for r in t['kept_routes']]
            if any(v is None for v in vals):
                raise ValueError(f'{stage}: missing DS for {row["candidate"]}')
            row['n_T22'] = len(vals)
            row['mean_ds_T22'] = sum(vals) / len(vals)
            means.append((row['candidate'], row['order'], row['mean_ds_T22']))
        out['previous_selection_sha256'] = PJ.sha256_file(PJ.selection_path(variant, spec['previous_stage'], sel_dir))
        out['ranking_T22'] = rank(means)
        out['selected'] = out['ranking_T22'][0]
        out['rule'] = 'final stage of successive halving: best mean DS over the T22 routes (stage-1 kept + stage-2 ' \
                      'kept); ties to the earlier candidate'
    else:                                      # TRIMMED: one stage
        out['selected'] = out['ranking'][0]
        out['rule'] = f'one stage: best mean DS over the {spec["route_set"]} kept routes; ties to the earlier candidate'
    out['selected_candidate'] = next(c for c in out['candidates'] if c['name'] == out['selected'])
    return out


def write_selection(sel, sel_dir=None, force=False):
    path = PJ.selection_path(sel['variant'], sel['stage'], sel_dir)
    if sel.get('provisional'):
        path = path.with_name(path.stem + '.provisional.json')
    if path.exists() and not force and not sel.get('provisional'):
        old = _read_json(path) or {}
        if {k: v for k, v in old.items() if k != 'written'} != {k: v for k, v in sel.items() if k != 'written'}:
            raise SelectionError(f'refusing to overwrite {path} with a different selection (use --force)')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sel, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return path


def freeze(variant, jobs_dir=None, sel_dir=None):
    """The tuning freeze (PROTOCOL Sec. 4.9) from the final selections of the four grids."""
    finals, stages = {}, {}
    for grid, stage in PJ.FINAL_STAGE[variant].items():
        sel, sha, path = PJ.load_selection(variant, stage, sel_dir, jobs_dir)
        finals[grid] = sel
        stages[stage] = {'path': PJ.rel(path), 'sha256': sha}
    for block, (no, grid, st, rset, dep) in PJ.BLOCKS[variant].items():
        if grid == 'ref' or block in stages:
            continue
        sel, sha, path = PJ.load_selection(variant, block, sel_dir, jobs_dir)
        stages[block] = {'path': PJ.rel(path), 'sha256': sha}
    lease = finals['lease']['selected_candidate']
    heur = finals['heur']['selected_candidate']
    age = finals['age']['selected_candidate']
    event = finals['event']['selected_candidate']
    d_star = int(heur['tag'].rsplit('_d', 1)[1])
    if heur['envelope']['label'] != lease['envelope']['label']:
        raise ValueError('the heuristic grid ran at another lease point than L*')
    if int(age['tag'].rsplit('_d', 1)[1]) != d_star:
        raise ValueError('the Age-Only grid ran with another depth than d*')
    risk = None
    lease_s1, _, _ = PJ.load_selection(variant, 'lease_s1', sel_dir, jobs_dir)
    if variant == 'FULL' and lease['envelope']['label'] == 'B0':
        rows = [(row['candidate'], row['order'], row['mean_ds'] if row['mean_ds'] is not None else -math.inf)
                for row in lease_s1['table'] if row['candidate'] in ('E5', 'E10')]
        risk = {'lease_point': rank(rows)[0] if rows else None,
                'rule': 'L* = B0: fl_risk runs the better of E5 / E10 by mean DS on lease_s1 (T22a), ties earlier'}
    utility = PJ.heur_utility(d_star)
    all_sel = {s: (_read_json(_abs(v['path'])) or {}) for s, v in stages.items()}
    doc = {'schema': FREEZE_SCHEMA, 'variant': variant, 'written': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
           'L_star': {'label': lease['envelope']['label'], 'envelope_path': lease['envelope']['path'],
                      'envelope_sha256': lease['envelope']['sha256'], 'config': lease['envelope'].get('config'),
                      'validity': 'std'},
           'd_star': {'d': d_star, 'utility': utility},
           'A_star': {'age_lease_s': age['policy_params']['age_lease_s']},
           'event_star': {'candidate': event['name'], 'policy_params': event['policy_params']},
           'arms': {'fl_heuristic': {'envelope': lease['envelope']['path'], 'policy_params': {'utility': utility}},
                    'fl_full': {'envelope': lease['envelope']['path'], 'a_det_depth': d_star},
                    'fl_behaviour': {'envelope': lease['envelope']['path'], 'base_depth': d_star},
                    'age_only': {'policy_params': age['policy_params']},
                    'event_triggered': {'policy_params': event['policy_params']}},
           'fl_risk': risk if variant == 'FULL' else 'not part of the TRIMMED plan',
           'configurations_selected_from': {'FrameLease': len(lease_s1['candidates'])
                                            + len(PJ.GRIDS[variant]['heur']) - 1,
                                            'Age-Only': len(PJ.GRIDS[variant]['age']),
                                            'Event-Triggered': len(PJ.GRIDS[variant]['event'])},
           'stages': stages, 'tables': {s: sel.get('table') for s, sel in all_sel.items()},
           'flags': {s: sel.get('flags') for s, sel in all_sel.items() if sel.get('flags')},
           'script_sha256': {'framelease_v4/protocol/select_stage.py': PJ.sha256_file(Path(__file__)),
                             'framelease_v4/protocol/p1_jobs.py': PJ.sha256_file(Path(PJ.__file__))}}
    return doc


def summary_lines(sel):
    L = [f'{sel["variant"]} {sel["stage"]} ({"complete" if sel["complete"] else "PROVISIONAL"}; finality: '
         f'{sel.get("finality")}): {len(sel["kept_routes"])}/{len(sel["routes"])} routes kept'
         + (f', dropped {sorted(sel["dropped_routes"])}' if sel['dropped_routes'] else '')]
    for row in sorted(sel['table'], key=lambda r: r['order']):
        m = row['mean_ds']
        L.append(f'  {row["candidate"]:<12} mean DS {m if m is None else round(m, 3)!s:>8}  n {row["n"]:>2}  '
                 f'{row["outcomes"]}' + (f'  T22 {row["mean_ds_T22"]:.3f}' if 'mean_ds_T22' in row else ''))
    if 'survivors' in sel:
        L.append(f'  survivors: {sel["survivors"]}')
    if 'selected' in sel:
        L.append(f'  selected: {sel["selected"]}')
    for f in sel.get('flags') or []:
        L.append(f'  FLAG {f["candidate"]}: {f["setup_failures"]} set-up failures on routes {f["routes"]}: {f["flag"]}')
    for w in sel.get('warnings') or []:
        L.append(f'  warning: {w}')
    return L


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--variant', choices=PJ.VARIANTS, required=True)
    ap.add_argument('--stage', default=None, help='block name of the stage (p1_jobs.py --list)')
    ap.add_argument('--freeze', action='store_true')
    ap.add_argument('--queue', type=Path, default=None, help='gpu_queue directory (status.jsonl)')
    ap.add_argument('--provisional', action='store_true', help='allow pending jobs (written as *.provisional.json)')
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--jobs-dir', type=Path, default=PJ.JOBS_DIR)
    ap.add_argument('--selection-dir', type=Path, default=PJ.SELECTION_DIR)
    ap.add_argument('--freeze-path', type=Path, default=FREEZE_PATH)
    a = ap.parse_args(argv)
    if not a.freeze and not a.stage:
        ap.error('give --stage or --freeze')
    try:
        if a.freeze:
            doc = freeze(a.variant, a.jobs_dir, a.selection_dir)
            print(json.dumps({k: doc[k] for k in ('variant', 'L_star', 'd_star', 'A_star', 'event_star', 'fl_risk',
                                                  'flags')}, indent=1))
            if a.write:
                path = Path(a.freeze_path)
                if path.exists() and not a.force:
                    raise SelectionError(f'refusing to overwrite {path} (use --force)')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n', encoding='utf-8')
                print(f'wrote {path}  sha256 {PJ.sha256_file(path)}')
            return 0
        sel = select(a.variant, a.stage, ROOT, a.jobs_dir, a.selection_dir, a.queue, a.provisional)
        print('\n'.join(summary_lines(sel)))
        if a.write:
            path = write_selection(sel, a.selection_dir, a.force)
            print(f'wrote {path}  sha256 {PJ.sha256_file(path)}')
        return 0
    except StageIncomplete as e:
        print(f'NOT SELECTED: {e}', file=sys.stderr)
        return 3
    except (SelectionError, FileNotFoundError, ValueError, KeyError, PermissionError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
