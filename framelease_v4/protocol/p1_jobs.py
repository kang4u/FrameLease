#!/usr/bin/env python3
"""Phase-1 job files of framelease_v4/PROTOCOL.md: tuning on training routes (Secs. 4.2-4.8) and the P1-0 real-CARLA
smoke block, in the framelease_v2/gpu_queue.py format. WRITTEN, NEVER LAUNCHED OR ENQUEUED: the files go to
outputs/framelease_v4/p1_jobs/<variant>/ (not a queue jobs.d/ directory, so no runner picks them up); this script never
starts a job, CARLA or the GPU.

  cd /home/kang/Desktop/DAC
  .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/p1_jobs.py --variant FULL --list
  source linux/env.sh && CUDA_VISIBLE_DEVICES= .conda-unidrive-linux/bin/python -B framelease_v4/protocol/p1_jobs.py \
      --variant FULL --block ref,lease_s1,event_s1 --check --write          # validate every line, then write
  ... --smoke --check --write                                                 # the P1-0 smoke block

Variants (--variant; PROTOCOL Sec. 4.2 and Sec. 14): FULL is the registered plan (successive halving with two stages
of 11 routes, T22a then T22b); TRIMMED is the reduced plan (one stage on the 11 T22a routes, reduced grids). A block
that depends on a selection is generated only from the stage selection JSON that framelease_v4/protocol/
select_stage.py wrote for the job file of the previous stage (its sha256 is checked and recorded).

  block (no.)    FULL                                         TRIMMED
  ref      (1)   Fixed Deep, Fast Only x T22 (44)             -
  lease_s1 (2)   FL+H d=10 at E5, E10, B0 x T22a (33)         the same (33)
  event_s1 (3)   4 settings x T22a (44)                       (theta_v2, 2.0 s), (theta_s, 1.0 s) x T22a (22)
  lease_s2 (4)   top 2 x T22b (22)                            -
  event_s2 (5)   top 2 x T22b (22)                            -
  heur_s1  (6)   d in {4, 1} at L* x T22a (22; d=10 reused)   d = 4 at L* x T22a (11; d=10 reused)
  heur_s2  (7)   survivors without T22b runs x T22b (<= 22)   -
  age_s1   (8)   A in {1.0, 1.5, 2.0, 2.5} with d* x T22a     A in {1.0, 1.5, 2.0} with d* x T22a (33)
  age_s2   (9)   top 2 x T22b (22)                            -
  smoke    (0)   P1-0: route 18305 (training, outside T22), 7 runs: fixed_deep, fast_only, age_only (A 2.0 s,
                 utility v4_adet_d4), event_triggered (theta_v2, 2.0 s), fl_original, fl_heuristic at E5 (utility
                 heuristic), fl_behaviour at E5 (identical for both variants; checked by check_smoke.py)

Every line (PROTOCOL Secs. 8.2-8.3): kappa 1.0, seed 11, the v4 launcher framelease_v4/arms/run_closed_loop_v4.py with
an explicit --fast-prefix sdpa,gpu_preproc,lora_merged, an explicit --envelope for the shield arms (the exported
outputs/framelease_v4/envelopes/<E5|E10|B0>.json), explicit --policy-params, --timeout-s 1410 (= 1500 s wall cap - 90 s),
--lock-wait-s 600, CARLA port 2600 + 10 (i mod 4) for line i of the file; routes of a block in the order of
random.Random(20261110 + block number).shuffle(id-sorted routes), all candidates of a route back to back in an order
rotated by one position per route; require_sha256 pins = the v2 matrix files, framelease_v2/__init__.py, the v3 runtime,
the fast-prefix sources, every framelease_v4 source the agent imports (arms + rl/{__init__,behaviour,features,qnet}.py)
and the envelope file. Job ids v4p1_<arm>[_<config>]_k1.0_s11_r<route> (smoke: v4p1smoke_...), output directories
outputs/framelease_v4/tuning/<block>/<arm>_<config>/ (smoke: outputs/framelease_v4/smoke_p1_0/<arm>/). Identical runs
have identical ids and directories in both variants, so a TRIMMED block can be extended to FULL without re-running.
--check validates every line: gpu_queue's contract, the pins against the current tree, the launcher's own parsing,
configuration build and preflight in this process, and the exact command with --dry-run in a subprocess (writes
nothing). Results go to <block>.check.json next to the job file.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import math
import os
import random
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

PYTHON = str(ROOT / '.conda-unidrive-linux/bin/python')
LAUNCHER_REL = 'framelease_v4/arms/run_closed_loop_v4.py'
ROUTES_XML_REL = 'third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/data/bench2drive220.xml'
FAST_PREFIX = 'sdpa,gpu_preproc,lora_merged'
SEED, KAPPA = 11, 1.0
WALL_CAP_S, LAUNCHER_MARGIN_S, LOCK_WAIT_S = 1500, 90, 600
TIMEOUT_S = WALL_CAP_S - LAUNCHER_MARGIN_S
PORT_BASE, PORT_STEP, PORT_CYCLE = 2600, 10, 4
ORDER_SEED = 20261110
ROUTE_SPLIT = ROOT / 'outputs/framelease_v4/protocol/route_split.json'
ENVELOPE_MANIFEST = ROOT / 'outputs/framelease_v4/envelopes/manifest.json'
JOBS_DIR = ROOT / 'outputs/framelease_v4/p1_jobs'
SELECTION_DIR = ROOT / 'outputs/framelease_v4/tuning/selection'
TUNING_REL = 'outputs/framelease_v4/tuning'
SMOKE_REL = 'outputs/framelease_v4/smoke_p1_0'
SMOKE_ROUTE = '18305'          # the first v3 pilot route outside T22 (training index 31, ParkingCutIn)
SMOKE_DIR = 'P1-0'
SMOKE_AGE_LEASE_S, SMOKE_AGE_DEPTH = 2.0, 4   # smoke age_only: A 2.0 s with a_det^4 (utility v4_adet_d4)
VARIANTS = ('FULL', 'TRIMMED')
STAGE_SCHEMA = 'framelease_v4.p1_stage/1'
SELECTION_SCHEMA = 'framelease_v4.p1_selection/1'
BEHAVIOUR_EPS = 0.3

# ---------------------------------------------------------------------------------------- grids (PROTOCOL Secs. 4.3-4.6)
THETA = {'v2': {'speed_delta_mps': 1.0, 'yaw_delta_rad': 0.10, 'det_shift_m': 2.0},       # the v2 defaults
         's': {'speed_delta_mps': 0.5, 'yaw_delta_rad': 0.05, 'det_shift_m': 1.0}}        # twice as sensitive
GRIDS = {
    'FULL': {'lease': ('E5', 'E10', 'B0'), 'event': (('v2', 2.0), ('v2', 1.0), ('s', 2.0), ('s', 1.0)),
             'heur': (10, 4, 1), 'age': (1.0, 1.5, 2.0, 2.5), 'ref': ('fixed_deep', 'fast_only')},
    'TRIMMED': {'lease': ('E5', 'E10', 'B0'), 'event': (('v2', 2.0), ('s', 1.0)), 'heur': (10, 4),
                'age': (1.0, 1.5, 2.0), 'ref': ()},
}
# block name -> (number, grid, stage, route set, dependency: the selection the block is generated from)
BLOCKS = {
    'FULL': {'ref': (1, 'ref', 0, 'T22', None), 'lease_s1': (2, 'lease', 1, 'T22a', None),
             'event_s1': (3, 'event', 1, 'T22a', None), 'lease_s2': (4, 'lease', 2, 'T22b', 'lease_s1'),
             'event_s2': (5, 'event', 2, 'T22b', 'event_s1'), 'heur_s1': (6, 'heur', 1, 'T22a', 'lease_s2'),
             'heur_s2': (7, 'heur', 2, 'T22b', 'heur_s1'), 'age_s1': (8, 'age', 1, 'T22a', 'heur_s2'),
             'age_s2': (9, 'age', 2, 'T22b', 'age_s1')},
    'TRIMMED': {'lease_s1': (2, 'lease', 1, 'T22a', None), 'event_s1': (3, 'event', 1, 'T22a', None),
                'heur_s1': (6, 'heur', 1, 'T22a', 'lease_s1'), 'age_s1': (8, 'age', 1, 'T22a', 'heur_s1')},
}
FINAL_STAGE = {'FULL': {'lease': 'lease_s2', 'event': 'event_s2', 'heur': 'heur_s2', 'age': 'age_s2'},
               'TRIMMED': {'lease': 'lease_s1', 'event': 'event_s1', 'heur': 'heur_s1', 'age': 'age_s1'}}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def rel(p):
    p = Path(p)
    p = p if p.is_absolute() else ROOT / p
    p = p.resolve()
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


# ---------------------------------------------------------------------------------------- routes and envelopes

def route_split():
    return json.loads(ROUTE_SPLIT.read_text(encoding='utf-8'))


def training_routes():
    """{route_id: training row} of the 44 training routes; raises if any is a test route."""
    split = route_split()
    test = {r['route_id'] for r in split['test']}
    train = {r['route_id']: r for r in split['training']}
    if set(train) & test:
        raise ValueError('a training route is a test route')
    return train


def route_set(name):
    split = route_split()
    ids = list(split['subsets'][name])
    train = training_routes()
    if any(r not in train for r in ids):
        raise ValueError(f'route set {name} holds a non-training route')
    return sorted(ids, key=int)


def envelopes():
    """{label: {'path': rel, 'sha256'}} of the exported lease operating points that survived pruning (manifest)."""
    man = json.loads(ENVELOPE_MANIFEST.read_text(encoding='utf-8'))
    out = {}
    for label in man['kept']:
        f = man['files'][label]
        if sha256_file(ROOT / f['path']) != f['sha256']:
            raise ValueError(f'envelope {label} ({f["path"]}) differs from its manifest sha256')
        out[label] = {'path': f['path'], 'sha256': f['sha256'], 'config': f['config']}
    if (man.get('verification') or {}).get('pass') is not True:
        raise ValueError('the envelope export was not verified (run framelease_v4/offline/export_envelopes.py)')
    return out


# ---------------------------------------------------------------------------------------- candidates

def heur_utility(d):
    """Utility name of a_det^d: d = 10 is the v3 heuristic ('heuristic'), else 'v4_adet_d<d>'."""
    from framelease_v4.rl import behaviour as B
    d = int(d)
    return 'heuristic' if d == B.MAX_DEPTH else B.adet_name(d)


def cand(name, arm, params, tag, envelope=None):
    return {'name': name, 'arm': arm, 'policy_params': dict(params), 'tag': tag, 'envelope': envelope}


def lease_cand(label, envs, d=10, name=None):
    """FrameLease + Heuristic at lease point `label` with a_det^d; named by the label in the lease grid and by d in the
    heuristic grid (the tag <label>_d<d> is the same, so the d = 10 runs of the lease grid are found and reused)."""
    if label not in envs:
        raise ValueError(f'lease operating point {label} is not an exported (kept) envelope')
    return cand(name or label, 'fl_heuristic', {'utility': heur_utility(d)}, f'{label}_d{d}',
                {'label': label, **envs[label]})


def event_cand(theta, hb):
    return cand(f'{theta}_hb{hb:.1f}', 'event_triggered', {**THETA[theta], 'heartbeat_s': float(hb)},
                f'{theta}_hb{hb:.1f}')


def age_cand(a, d):
    return cand(f'A{a:.1f}', 'age_only', {'age_lease_s': float(a), 'utility': heur_utility(d)}, f'A{a:.1f}_d{d}')


def ref_cand(arm):
    return cand(arm, arm, {}, '')


def job_id(c, route, prefix='v4p1'):
    mid = f'{c["arm"]}_{c["tag"]}' if c['tag'] else c['arm']
    return f'{prefix}_{mid}_k{KAPPA:.1f}_s{SEED}_r{route}'


def output_dir(block, c):
    return f'{TUNING_REL}/{block}/{c["arm"]}_{c["tag"]}' if c['tag'] else f'{TUNING_REL}/{block}/{c["arm"]}'


# ---------------------------------------------------------------------------------------- pins and lines

def code_pins(extra=()):
    """Full pins (PROTOCOL Sec. 8.3): v2 matrix files, v2/v3 package inits, v3 runtime, fast prefix, the v4 sources the
    agent imports (arms_v4 pins = run_closed_loop_v4.V4_CODE incl. the v4 utilities) and the extra files."""
    from framelease_v4.arms import jobs_v4 as J
    return J.code_pins(extra)


def ordered(block_no, routes, cands):
    """[(candidate, route)]: routes shuffled with Random(20261110 + block), candidates rotated by one per route."""
    rs = sorted(routes, key=int)
    random.Random(ORDER_SEED + int(block_no)).shuffle(rs)
    out = []
    for pos, r in enumerate(rs):
        k = pos % len(cands)
        for c in list(cands[k:]) + list(cands[:k]):
            out.append((c, r))
    return out, rs


def port_of(i):
    return PORT_BASE + PORT_STEP * (int(i) % PORT_CYCLE)


def command(c, route, port, out_dir):
    cmd = [PYTHON, '-B', LAUNCHER_REL, '--arm', c['arm'], '--fast-prefix', FAST_PREFIX, '--kappa', f'{KAPPA:.1f}',
           '--seed', str(SEED), '--routes', ROUTES_XML_REL, '--route-id', str(route), '--port', str(port),
           '--output-dir', out_dir, '--timeout-s', str(TIMEOUT_S), '--lock-wait-s', str(LOCK_WAIT_S)]
    if c['envelope']:
        cmd += ['--envelope', c['envelope']['path']]
    if c['policy_params']:
        cmd += ['--policy-params', json.dumps(c['policy_params'], sort_keys=True)]
    return cmd


def make_lines(block, block_no, grid, stage, routes, cands, tier=1, phase='P1', prefix='v4p1', out_fn=None):
    train = training_routes()
    pairs, order = ordered(block_no, routes, cands)
    lines = []
    for i, (c, r) in enumerate(pairs):
        port = port_of(i)
        out = (out_fn or output_dir)(block, c)
        extra = [c['envelope']['path']] if c['envelope'] else []
        row = train[r]
        job = {'id': job_id(c, r, prefix), 'kind': 'closed_loop', 'tier': int(tier), 'cmd': command(c, r, port, out),
               'wall_cap_s': WALL_CAP_S, 'matrix': 'framelease_v4_p1', 'phase': phase, 'block': block,
               'block_no': int(block_no), 'grid': grid, 'stage': int(stage), 'candidate': c['name'],
               'arm_name': c['arm'], 'config': c['tag'] or None, 'policy_params': c['policy_params'],
               'envelope': c['envelope'], 'kappa': KAPPA, 'seed': SEED, 'fast_prefix': FAST_PREFIX.split(','),
               'route_id': r, 'route_index': row['index'], 'scenario_type': row['scenario_type'],
               'town': row['town'], 'port': port, 'output_dir': out, 'training_route': True,
               'not_for_launch_before': 'registration (PROTOCOL Sec. 13.1) and the user\'s approval',
               'require_sha256': code_pins(extra)}
        lines.append(job)
    return lines, order


# ---------------------------------------------------------------------------------------- selections

def selection_path(variant, stage, sel_dir=None):
    return Path(sel_dir or SELECTION_DIR) / variant / f'{stage}.json'


def stage_paths(variant, block, jobs_dir=None):
    no = BLOCKS[variant][block][0]
    base = Path(jobs_dir or JOBS_DIR) / variant / f'b{no:02d}_{block}'
    return base.with_suffix('.jsonl'), Path(str(base) + '.stage.json'), Path(str(base) + '.check.json')


def load_stage_spec(variant, block, jobs_dir=None):
    _, spec_path, _ = stage_paths(variant, block, jobs_dir)
    if not spec_path.is_file():
        raise FileNotFoundError(f'{variant} {block}: stage spec {spec_path} not written yet')
    return json.loads(spec_path.read_text(encoding='utf-8')), spec_path


def load_selection(variant, stage, sel_dir=None, jobs_dir=None):
    """A complete stage selection written by select_stage.py for the CURRENT job file of that stage."""
    path = selection_path(variant, stage, sel_dir)
    if not path.is_file():
        raise FileNotFoundError(f'{variant} {stage}: selection {path} not written yet (run select_stage.py)')
    sel = json.loads(path.read_text(encoding='utf-8'))
    if sel.get('schema') != SELECTION_SCHEMA or sel.get('variant') != variant or sel.get('stage') != stage:
        raise ValueError(f'{path}: not the {variant} {stage} selection')
    if sel.get('complete') is not True or sel.get('provisional'):
        raise ValueError(f'{path}: the selection is not complete')
    _, spec_path = load_stage_spec(variant, stage, jobs_dir)
    if sel.get('stage_spec_sha256') != sha256_file(spec_path):
        raise ValueError(f'{path}: made for another job file of {stage} (stage spec sha256 differs)')
    return sel, sha256_file(path), path


# ---------------------------------------------------------------------------------------- blocks

def block_candidates(variant, block, sel_dir=None, jobs_dir=None):
    """(candidates with their new routes, reused candidates, inputs) of a block. A reused candidate carries the jobs of
    an earlier block (PROTOCOL Sec. 4.4: the d = 10 runs at L* come from the lease grid)."""
    no, grid, stage, rset, dep = BLOCKS[variant][block]
    g = GRIDS[variant]
    inputs, reused = {}, []
    if grid == 'ref':
        return [ref_cand(a) for a in g['ref']], reused, inputs
    if grid == 'lease':
        envs = envelopes()
        cands = [lease_cand(L, envs) for L in g['lease'] if L in envs]
    elif grid == 'event':
        cands = [event_cand(t, hb) for t, hb in g['event']]
    elif grid == 'heur':
        sel, sha, path = load_selection(variant, FINAL_STAGE[variant]['lease'] if stage == 1 else dep, sel_dir,
                                        jobs_dir)
        inputs[rel(path)] = sha
        if stage == 1:
            L = sel['selected']
            envs = envelopes()
            cands = [lease_cand(L, envs, d, name=f'd{d}') for d in g['heur']]
        else:
            cands = [c for c in sel['candidates'] if c['name'] in sel['survivors']]
    elif grid == 'age':
        if stage == 1:
            sel, sha, path = load_selection(variant, FINAL_STAGE[variant]['heur'], sel_dir, jobs_dir)
            inputs[rel(path)] = sha
            d = int(sel['selected_candidate']['tag'].rsplit('_d', 1)[1])
            cands = [age_cand(a, d) for a in g['age']]
        else:
            sel, sha, path = load_selection(variant, dep, sel_dir, jobs_dir)
            inputs[rel(path)] = sha
            cands = [c for c in sel['candidates'] if c['name'] in sel['survivors']]
    else:
        raise ValueError(grid)
    if grid in ('lease', 'event') and stage == 2:
        sel, sha, path = load_selection(variant, dep, sel_dir, jobs_dir)
        inputs[rel(path)] = sha
        cands = [c for c in sel['candidates'] if c['name'] in sel['survivors']]
    if grid == 'heur':
        # d = 10 at L* already ran in the lease grid on this stage's routes: reuse those jobs
        lease_block = 'lease_s1' if stage == 1 else 'lease_s2'           # the lease stage on the same routes
        lease_spec, lease_spec_path = load_stage_spec(variant, lease_block, jobs_dir)
        inputs[rel(lease_spec_path)] = sha256_file(lease_spec_path)
        keep = []
        for c in cands:
            if c['tag'].endswith('_d10'):
                src = next((x for x in lease_spec['candidates'] if x['tag'] == c['tag']), None)
                if src is None:
                    raise ValueError(f'{block}: the d = 10 runs at {c["tag"]} are not in {lease_block}')
                reused.append({**c, 'jobs': src['jobs'], 'reused_from': lease_block})
            else:
                keep.append(c)
        cands = keep
    return cands, reused, inputs


def build_block(variant, block, sel_dir=None, jobs_dir=None):
    """(job lines, stage spec) of one block (nothing written)."""
    if block not in BLOCKS[variant]:
        raise ValueError(f'{variant} has no block {block!r} (blocks: {", ".join(BLOCKS[variant])})')
    no, grid, stage, rset, dep = BLOCKS[variant][block]
    routes = route_set(rset)
    cands, reused, inputs = block_candidates(variant, block, sel_dir, jobs_dir)
    lines, order = make_lines(block, no, grid, stage, routes, cands) if cands else ([], [])
    jobs = {}
    for j in lines:
        jobs.setdefault(j['candidate'], {})[j['route_id']] = {'id': j['id'], 'output_dir': j['output_dir'],
                                                               'block': block}
    all_cands = []
    names_in_order = _grid_order(variant, grid, cands + reused)
    for c in sorted(cands + reused, key=lambda x: names_in_order.index(x['name'])):
        entry = {k: c[k] for k in ('name', 'arm', 'policy_params', 'tag', 'envelope')}
        entry['order'] = names_in_order.index(c['name'])
        entry['jobs'] = c.get('jobs') or jobs.get(c['name'], {})
        entry['reused_from'] = c.get('reused_from')
        if sorted(entry['jobs'], key=int) != routes:
            raise ValueError(f'{block}: candidate {c["name"]} lacks jobs on some routes')
        all_cands.append(entry)
    k = len(all_cands)
    final = FINAL_STAGE[variant].get(grid) == block
    spec = {'schema': STAGE_SCHEMA, 'variant': variant, 'block': block, 'block_no': no, 'grid': grid,
            'stage': stage, 'final_stage': bool(final), 'route_set': rset, 'routes': routes,
            'route_order': order, 'candidates': all_cands, 'n_candidates': k,
            'survive': (math.ceil(k / 2) if (grid != 'ref' and not final) else None),
            'previous_stage': (f'{grid}_s1' if stage == 2 else None),
            'inputs': inputs, 'n_lines': len(lines), 'rules': 'PROTOCOL Sec. 4.2 (select_stage.py)'}
    return lines, spec


def _grid_order(variant, grid, cands):
    """Candidate names in the registered candidate order of the grid (Secs. 4.3-4.6)."""
    g = GRIDS[variant]
    if grid == 'lease':
        names = [L for L in g['lease']]
    elif grid == 'event':
        names = [f'{t}_hb{hb:.1f}' for t, hb in g['event']]
    elif grid == 'heur':
        names = [f'd{d}' for d in g['heur']]
    elif grid == 'age':
        names = [f'A{a:.1f}' for a in g['age']]
    else:
        names = list(g['ref'])
    return names


def smoke_block():
    """P1-0: one training route outside every tuning set, 7 runs (both variants)."""
    from framelease_v4.rl import behaviour as B
    from framelease_v4.rl import collection_plan as CP
    train = training_routes()
    if SMOKE_ROUTE not in train or SMOKE_ROUTE in set(route_set('T22')):
        raise ValueError('the smoke route must be a training route outside T22')
    envs = envelopes()
    seed = CP.behaviour_seed(SMOKE_ROUTE, KAPPA, 0)
    beh = B.behaviour_name(BEHAVIOUR_EPS, seed)
    # age_only runs a_det^4 (utility v4_adet_d4), so the smoke exercises every utility kind of Phase 1 in the agent
    # process: 'heuristic' (fl_heuristic), 'v4_adet_d<d>' (age_only) and the behaviour utility (fl_behaviour)
    cands = [ref_cand('fixed_deep'), ref_cand('fast_only'),
             age_cand(SMOKE_AGE_LEASE_S, SMOKE_AGE_DEPTH),
             event_cand('v2', 2.0), ref_cand('fl_original'),
             lease_cand('E5', envs), cand('fl_behaviour', 'fl_behaviour', {'utility': beh}, f'E5_eps{BEHAVIOUR_EPS:.3f}',
                                         {'label': 'E5', **envs['E5']})]
    cands[2] = {**cands[2], 'name': 'age_only'}
    cands[3] = {**cands[3], 'name': 'event_triggered'}
    cands[5] = {**cands[5], 'name': 'fl_heuristic'}
    lines, order = make_lines('smoke', 0, 'smoke', 0, [SMOKE_ROUTE], cands, tier=0, phase='P1-0', prefix='v4p1smoke',
                              out_fn=lambda block, c: f'{SMOKE_REL}/{c["arm"]}')
    meta = {'schema': 'framelease_v4.p1_smoke/1', 'block': 'smoke', 'block_no': 0, 'route': SMOKE_ROUTE,
            'route_row': train[SMOKE_ROUTE], 'behaviour': {'utility': beh, 'eps': BEHAVIOUR_EPS, 'seed': seed,
                                                           'seed_rule': 'collection_plan.behaviour_seed(route, kappa, rep=0)'},
            'arms': [c['name'] for c in cands], 'n_lines': len(lines),
            'utilities': {c['name']: c['policy_params'].get('utility') for c in cands if c['policy_params'].get('utility')},
            'check': 'framelease_v4/protocol/check_smoke.py (the PROTOCOL Sec. 8.1 P1-0 criteria; registered before any '
                     'smoke run existed)',
            'purpose': 'first real-CARLA runs of the v4 agent (V4Runtime, fast prefix, actor-box log, decision rows, '
                       'utility registration in the agent process) for every arm kind before any tuning run; '
                       'infrastructure check only, never used for selection or RL data'}
    return lines, meta


# ---------------------------------------------------------------------------------------- checks (CPU only)

def static_problems(lines):
    """Problems found without the launcher: gpu_queue contract, pins, ids, ports, explicit options, training routes."""
    from framelease_v2 import gpu_queue as Q
    train = training_routes()
    test = {r['route_id'] for r in route_split()['test']}
    problems = []
    ids = [j['id'] for j in lines]
    if len(set(ids)) != len(ids):
        problems.append('duplicate job ids')
    dirs = {}
    for i, j in enumerate(lines):
        bad = Q.validate_job(j)
        if bad:
            problems.append(f'{j["id"]}: gpu_queue rejects the job: {bad}')
        mism = Q.pin_mismatches(j['require_sha256'])
        if mism:
            problems.append(f'{j["id"]}: pinned files differ from the tree: {[m["file"] for m in mism][:5]}')
        cmd = j['cmd']
        opt = {cmd[k]: cmd[k + 1] for k in range(len(cmd) - 1) if cmd[k].startswith('--')}
        if j['port'] != port_of(i) or opt.get('--port') != str(port_of(i)):
            problems.append(f'{j["id"]}: port {j["port"]} != 2600 + 10 ({i} mod 4)')
        if opt.get('--fast-prefix') != FAST_PREFIX:
            problems.append(f'{j["id"]}: --fast-prefix not explicit')
        if opt.get('--timeout-s') != str(TIMEOUT_S) or opt.get('--lock-wait-s') != str(LOCK_WAIT_S):
            problems.append(f'{j["id"]}: --timeout-s / --lock-wait-s')
        if (opt.get('--kappa'), opt.get('--seed')) != (f'{KAPPA:.1f}', str(SEED)):
            problems.append(f'{j["id"]}: kappa / seed')
        shield = j['arm_name'] in ('fl_heuristic', 'fl_full', 'fl_behaviour')
        if shield != ('--envelope' in opt):
            problems.append(f'{j["id"]}: --envelope must be explicit for the shield arms (and only there)')
        if shield and j['envelope']['path'] not in j['require_sha256']:
            problems.append(f'{j["id"]}: the envelope file is not pinned')
        if j['route_id'] not in train or j['route_id'] in test:
            problems.append(f'{j["id"]}: route {j["route_id"]} is not a training route')
        if json.loads(opt.get('--policy-params', '{}')) != j['policy_params']:
            problems.append(f'{j["id"]}: --policy-params differ from the job record')
        dirs.setdefault(j['output_dir'], set()).add(j['candidate'])
    for d, cs in dirs.items():
        if len(cs) != 1:
            problems.append(f'{d}: output directory shared by candidates {sorted(cs)}')
    return problems


def check_in_process(job):
    """{'id', 'problems', ...}: the launcher's own parsing, configuration build and preflight, in this process (not
    thread-safe: stdout / stderr are redirected and the environment is restored afterwards; call it sequentially)."""
    from framelease_v4.arms import run_closed_loop_v4 as RL
    out = {'id': job['id'], 'problems': []}
    cmd = job['cmd']
    if cmd[:3] != [PYTHON, '-B', LAUNCHER_REL]:
        out['problems'].append('not the v4 launcher command')
        return out
    saved = dict(os.environ)
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            args = RL.parse_args(cmd[3:])
            prep = RL.prepare(args)
        cfg = prep['cfg']
        info = prep['route']
        if (info['route_id'], info['town'], info['scenarios']) != (job['route_id'], job['town'], [job['scenario_type']]):
            out['problems'].append(f'route {info} does not match the job')
        if cfg['arm'] != job['arm_name'] or prep['fp']['options'] != job['fast_prefix']:
            out['problems'].append('arm / fast prefix differ from the job')
        if cfg['agent']['runtime']['kappa'] != KAPPA or cfg['agent']['seed'] != SEED:
            out['problems'].append('kappa / seed differ')
        pp = dict(cfg['agent']['policy_params'] or {})
        for k, v in job['policy_params'].items():
            if pp.get(k) != v:
                out['problems'].append(f'policy parameter {k}: {pp.get(k)!r} != {v!r}')
        if job['envelope']:
            if (cfg.get('v3') or {}).get('envelope_sha256') != job['envelope']['sha256']:
                out['problems'].append('envelope sha256 of the configuration differs from the exported file')
        if cfg['kind'] in ('age', 'shield') and cfg['agent']['runtime'].get('max_depth') != 10:
            out['problems'].append('shield depth limit is not 10')
        out['agent_runtime_config_sha256'] = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
        out['utility'] = (cfg.get('utility') or {}).get('name') or pp.get('utility')
    except SystemExit as e:
        out['problems'].append(f'SystemExit: {e}')
    except BaseException as e:  # noqa: BLE001
        out['problems'].append(f'{type(e).__name__}: {e}')
    finally:
        os.environ.clear()
        os.environ.update(saved)
    return out


def dry_run_line(job, env):
    """The exact command with --dry-run in a subprocess (thread-safe; env prepared by the caller). Returns
    (dry_run summary or None, agent_runtime_config sha256 or None, problems)."""
    problems = []
    p = subprocess.run(job['cmd'] + ['--dry-run'], cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        return None, None, [f'dry run exit {p.returncode}: {p.stderr[-400:]}']
    d = json.loads(p.stdout)
    entry = d['command'][d['command'].index('--agent') + 1]
    ok = (d.get('status') == 'NOT_STARTED' and d.get('v4_arm') == job['arm_name']
          and entry.endswith('framelease_v4_arms_agent_entry.py')
          and 'FRAMELEASE_V4_ARMS_CONFIG' in d['environment_overrides']
          and 'FRAMELEASE_V2_RUNTIME_CONFIG' not in d['environment_overrides']
          and d['ports'] == [job['port'], job['port'] + 1, job['port'] + 2, job['port'] + 6000])
    if not ok:
        problems.append('dry-run output does not match the job')
    dsha = hashlib.sha256(json.dumps(d['agent_runtime_config'], sort_keys=True).encode()).hexdigest()
    summary = {'status': d.get('status'), 'arm': d.get('arm'), 'ports': d.get('ports'), 'entry': entry.split('/')[-1]}
    return summary, dsha, problems


def _merge_dry_run(out, res):
    summary, dsha, problems = res
    out['problems'] += problems
    if summary is not None:
        out['dry_run'] = summary
        if dsha != out.get('agent_runtime_config_sha256'):
            out['problems'].append('the dry run built another configuration than the in-process check')


def _stack_ready():
    return bool(os.environ.get('CHECKPOINT')) and Path(os.environ['CHECKPOINT']).is_file()


def check_line(job, dry_run=True):
    """{'id', 'ok', 'problems', ...} of one line: check_in_process, then (if dry_run) its --dry-run subprocess."""
    out = check_in_process(job)
    if dry_run and not out['problems']:
        before = (ROOT / job['output_dir']).exists()
        _merge_dry_run(out, dry_run_line(job, dict(os.environ, PYTHONDONTWRITEBYTECODE='1', CUDA_VISIBLE_DEVICES='')))
        if not before and (ROOT / job['output_dir']).exists():
            out['problems'].append('the dry run created the output directory')
    out['ok'] = not out['problems']
    return out


def check_lines(lines, dry_run=True, workers=4):
    """Every line: static checks, the in-process launcher checks (sequential) and the --dry-run subprocesses
    (parallel threads, each with its own copy of the environment). Returns (per-line results, problems)."""
    problems = static_problems(lines)
    if dry_run and not _stack_ready():
        raise SystemExit('--check needs the official stack variables (source linux/env.sh): CHECKPOINT is not set')
    results = [check_in_process(j) for j in lines]
    if dry_run:
        dirs_before = {j['output_dir']: (ROOT / j['output_dir']).exists() for j in lines}
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', CUDA_VISIBLE_DEVICES='')
        todo = [(r, j) for r, j in zip(results, lines) if not r['problems']]
        with ThreadPoolExecutor(max_workers=max(1, int(workers))) as ex:
            outs = list(ex.map(lambda rj: dry_run_line(rj[1], dict(env)), todo))
        for (r, _), res in zip(todo, outs):
            _merge_dry_run(r, res)
        for d, existed in dirs_before.items():
            if not existed and (ROOT / d).exists():
                problems.append(f'{d}: created by a dry run')
    for r in results:
        r['ok'] = not r['problems']
    problems += [f'{r["id"]}: {p}' for r in results for p in r['problems']]
    return results, problems


# ---------------------------------------------------------------------------------------- writing

def _jsonl(lines):
    return ''.join(json.dumps(j, sort_keys=True) + '\n' for j in lines)


def write_block(paths, lines, spec, results, problems, force=False):
    job_path, spec_path, check_path = paths
    for j in lines:
        runs = ROOT / j['output_dir'] / 'runs'
        if runs.is_dir() and any(runs.iterdir()):
            raise SystemExit(f'refusing to write {job_path}: {runs} already holds runs')
    text = _jsonl(lines)
    if job_path.exists() and job_path.read_text(encoding='utf-8') != text and not force:
        raise SystemExit(f'refusing to overwrite {job_path} with other lines (use --force; no run may exist)')
    job_path.parent.mkdir(parents=True, exist_ok=True)
    job_path.write_text(text, encoding='utf-8')
    spec = {**spec, 'job_file': rel(job_path), 'job_file_sha256': sha256_file(job_path)}
    spec_path.write_text(json.dumps(spec, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    check = {'schema': 'framelease_v4.p1_check/1', 'job_file': rel(job_path), 'job_file_sha256': spec['job_file_sha256'],
             'n_lines': len(lines), 'problems': problems, 'all_dry_runs_ok': bool(results) and all(
                 r.get('ok') and r.get('dry_run', {}).get('status') == 'NOT_STARTED' for r in results),
             'lines': results, 'script_sha256': sha256_file(Path(__file__))}
    check_path.write_text(json.dumps(check, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return {'job_file': rel(job_path), 'sha256': spec['job_file_sha256'], 'lines': len(lines),
            'stage_spec': rel(spec_path), 'stage_spec_sha256': sha256_file(spec_path), 'check': rel(check_path)}


def block_status(variant, jobs_dir=None, sel_dir=None):
    out = []
    for block, (no, grid, stage, rset, dep) in BLOCKS[variant].items():
        job_path, spec_path, _ = stage_paths(variant, block, jobs_dir)
        sel = selection_path(variant, block, sel_dir)
        out.append({'block': block, 'no': no, 'grid': grid, 'stage': stage, 'routes': rset, 'depends_on': dep,
                    'job_file': rel(job_path) if job_path.is_file() else None,
                    'selection': rel(sel) if sel.is_file() else None})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--variant', choices=VARIANTS, default=None)
    ap.add_argument('--block', default=None, help='comma-separated block names (see --list)')
    ap.add_argument('--smoke', action='store_true', help='the P1-0 smoke block')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--check', action='store_true', help='validate every line (needs source linux/env.sh)')
    ap.add_argument('--no-dry-run', action='store_true', help='skip the subprocess --dry-run of each line')
    ap.add_argument('--write', action='store_true', help='write the job file, stage spec and check (requires --check)')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--jobs-dir', type=Path, default=JOBS_DIR)
    ap.add_argument('--selection-dir', type=Path, default=SELECTION_DIR)
    a = ap.parse_args(argv)
    if a.list:
        for v in ([a.variant] if a.variant else VARIANTS):
            print(json.dumps({v: block_status(v, a.jobs_dir, a.selection_dir)}, indent=1))
        return 0
    if a.write and not a.check:
        ap.error('--write requires --check (every line must pass before a file is written)')
    todo = []
    if a.smoke:
        lines, meta = smoke_block()
        base = Path(a.jobs_dir) / SMOKE_DIR / 'b00_smoke'
        todo.append(('smoke', lines, meta, (base.with_suffix('.jsonl'), Path(str(base) + '.meta.json'),
                                            Path(str(base) + '.check.json'))))
    if a.block:
        if not a.variant:
            ap.error('--block needs --variant')
        for block in a.block.split(','):
            try:
                lines, spec = build_block(a.variant, block.strip(), a.selection_dir, a.jobs_dir)
            except (FileNotFoundError, ValueError) as e:
                print(f'{a.variant} {block.strip()}: cannot be generated yet: {e}', file=sys.stderr)
                return 2
            todo.append((block.strip(), lines, spec, stage_paths(a.variant, block.strip(), a.jobs_dir)))
    if not todo:
        ap.error('nothing to do: give --smoke and / or --variant V --block B (or --list)')
    rc = 0
    for name, lines, spec, paths in todo:
        print(f'{name}: {len(lines)} job lines -> {rel(paths[0])} (NOT launched)')
        for j in lines[:3]:
            print(f'  {j["id"]:<58} port {j["port"]} -> {j["output_dir"]}')
        if len(lines) > 3:
            print(f'  ... {len(lines) - 3} more')
        if not a.check:
            continue
        results, problems = check_lines(lines, not a.no_dry_run, a.workers)
        if problems:
            print(f'{name}: CHECK FAILED\n  ' + '\n  '.join(problems[:40]), file=sys.stderr)
            rc = 1
            continue
        print(f'{name}: every line passes gpu_queue, the pins, the launcher (parse, configuration, preflight)'
              + ('' if a.no_dry_run else ' and its --dry-run'))
        if a.write:
            info = write_block(paths, lines, spec, results, problems, a.force)
            print(json.dumps(info, indent=1))
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
