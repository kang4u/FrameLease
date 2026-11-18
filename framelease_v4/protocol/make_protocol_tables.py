#!/usr/bin/env python3
"""Deterministic tables of framelease_v4/PROTOCOL.md: route split, subsets, run budget (CPU only, stdlib only).

    cd /home/kang/Desktop/DAC
    .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/make_protocol_tables.py          # write
    .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/make_protocol_tables.py --check  # re-derive, compare

Inputs (read only): outputs/framelease_v2/closed_loop_matrix/routes.json (the 44 test routes), the Bench2Drive
bench2drive220.xml it names, the fast-prefix pilot queue status (measured wall time per closed-loop run) and the pilot
run directories (measured disk per run). Outputs (only): outputs/framelease_v4/protocol/{route_split.json,
budget.json, budget.md, MANIFEST.sha256}.

Rules implemented here (PROTOCOL.md Sec. 3 and Sec. 10):
* test = the 44 routes of routes.json (lowest route id of each of the 44 scenario types; 2086 excluded there).
* training pool = the second-lowest route id of each scenario type (numeric order), disjoint from test by construction.
* test subsets: E = index % 2 == 0 (22), C = index % 4 == 0 (11), R = index % 3 == 0 (15), as registered for v2.
* training subsets (index = position in the id-sorted training list): T22a = index % 4 == 0 (11),
  T22b = index % 4 == 2 (11), T22 = T22a + T22b (the tuning routes); RL = all 44 training routes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import xml.etree.ElementTree as ET
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTES_JSON = ROOT / 'outputs/framelease_v2/closed_loop_matrix/routes.json'
PILOT_STATUS = ROOT / 'outputs/framelease_v3/fastprefix/run_20261110/pilot_queue/status.jsonl'
PILOT_RUNS = ROOT / 'outputs/framelease_v3/fastprefix/run_20261110/pilot'
V2_STATUS = ROOT / 'outputs/framelease_v2/gpu_queue/status.jsonl'
OUT = ROOT / 'outputs/framelease_v4/protocol'
PROTECTED = [ROOT / p for p in ('framelease_v2', 'framelease_v3', 'outputs/framelease_v2', 'outputs/framelease_v3')]

DEV_ROUTE = '2086'
PILOT_ROUTES = ('2086', '18305', '2554', '1792')      # fast-prefix pilot (RND report Sec. 5), all training routes

# ------------------------------------------------------------------------------------------- run budget (Sec. 10)
PLAN_S_PER_RUN = 450.0       # planning figure: measured mean wall time of the 12 fast-prefix pilot jobs (450.5 s)
PLAN_MB_PER_RUN = 10.0       # planning figure: pilot runs 2.3-12 MB (mean about 6 MB) + actor-box log (<= 2 MB budget)
WALL_CAP_S = 1500.0          # per-job wall cap (25 min), the worst case of a single run
RUNNER_FLOOR_GIB = 6.0       # gpu_queue.py --min-free-gib of the v3 pilot (a disk watchdog places STOP at 5 GiB)

# (phase, tier, block id, description, runs, gpu?)  -- runs are derived from the subset sizes below
N = {'T22a': 11, 'T22b': 11, 'T22': 22, 'TR': 44, 'TEST': 44, 'E': 22, 'C': 11, 'R': 15}


VARIANTS = ('FULL', 'TRIMMED')     # FULL = the registered plan (default); TRIMMED = the reduced plan (PROTOCOL Sec. 14)
SMOKE = ('P1-0', 0, 'smoke', 'P1-0 real-CARLA smoke: fixed_deep, fast_only, age_only, event_triggered, fl_original, '
         'fl_heuristic at E5, behaviour policy at E5 x 1 training route outside T22 (18305)', 7)


def plan_blocks(variant='FULL'):
    """(phase, tier, block, description, runs) of a plan variant. The lease grid is {E5, E10, B0} with the standard
    validity definition (the RA rule is an offline sensitivity only; PROTOCOL Sec. 4.3)."""
    n = N
    if variant == 'FULL':
        return [
            SMOKE,
            # Phase 1: tuning on training routes (successive halving, Sec. 4.2)
            ('P1', 1, 'T-ref', 'references, untuned: Fixed Deep and Fast Only x T22', 2 * n['T22']),
            ('P1', 1, 'T-lease-s1', 'lease grid {E5, E10, B0} x T22a (FL+H, d = 10, std validity)', 3 * n['T22a']),
            ('P1', 1, 'T-event-s1', 'Event-Triggered grid, 4 candidates x T22a', 4 * n['T22a']),
            ('P1', 1, 'T-lease-s2', 'lease grid, top 2 x T22b', 2 * n['T22b']),
            ('P1', 1, 'T-event-s2', 'Event-Triggered grid, top 2 x T22b', 2 * n['T22b']),
            ('P1', 1, 'T-heur-s1', 'heuristic d in {4, 1} x T22a at L* (d = 10 reused from the lease grid)', 2 * n['T22a']),
            ('P1', 1, 'T-heur-s2', 'heuristic survivors without T22b runs x T22b (at most 2)', 2 * n['T22b']),
            ('P1', 1, 'T-age-s1', 'Age-Only grid, 4 candidates x T22a (utility a_det^{d*})', 4 * n['T22a']),
            ('P1', 1, 'T-age-s2', 'Age-Only grid, top 2 x T22b', 2 * n['T22b']),
            # Phase 2: offline-RL data on training routes (Sec. 5.3)
            ('P2', 2, 'RL-data', 'behaviour policy (eps 0.3) at L*, 44 training routes x kappa {1.0, 1.5, 2.0}',
             3 * n['TR']),
            # Phase 4: Table I (Sec. 7.2)
            ('P4', 3, 'TI-main', 'Table I: 7 arms x 44 test routes, kappa 1.0, seed 11', 7 * n['TEST']),
            # Phase 5: Fig. 3 (Sec. 7.3)
            ('P5', 4, 'F3-k', 'Fig. 3: 4 arms x kappa {1.5, 2.0} x subset E', 4 * 2 * n['E']),
            # Phase 6: ablations and replicates (Sec. 7.4-7.5, 9.6)
            ('P6', 5, 'A-lease', 'Table II-A closed loop: Global-Margin lease + shield + heuristic x E', 1 * n['E']),
            ('P6', 5, 'A-rl', 'Table II-A RL: Bandit and FQI w/o lease features x E', 2 * n['E']),
            ('P6', 6, 'S-seed12', 'seed-12 replicates: Fixed Deep, Fast Only, FL+H, Full FL x R', 4 * n['R']),
            ('P6', 6, 'S-risk', 'conditional (only if L* = B0): fl_risk at the better of E5 / E10 x E', n['E']),
        ]
    if variant == 'TRIMMED':
        return [
            SMOKE,
            # Phase 1: one stage on the 11 T22a routes, reduced grids (Sec. 14)
            ('P1', 1, 'T-lease', 'lease grid {E5, E10, B0} x T22a (FL+H, d = 10, std validity; one stage)',
             3 * n['T22a']),
            ('P1', 1, 'T-event', 'Event-Triggered (theta_v2, 2.0 s) and (theta_s, 1.0 s) x T22a', 2 * n['T22a']),
            ('P1', 1, 'T-heur', 'heuristic d = 4 x T22a at L* (d = 10 reused from the lease grid)', 1 * n['T22a']),
            ('P1', 1, 'T-age', 'Age-Only A in {1.0, 1.5, 2.0} s x T22a (utility a_det^{d*})', 3 * n['T22a']),
            # Phase 2: offline-RL data (Sec. 14)
            ('P2', 2, 'RL-data', 'behaviour policy (eps 0.3) at L*, the 22 training routes outside T22 x 2 behaviour '
             'seeds (rep 0 at kappa 1.0; rep 1 at kappa 1.5 / 2.0, alternating)', 2 * n['T22']),
            ('P4', 3, 'TI-main', 'Table I: 7 arms x 44 test routes, kappa 1.0, seed 11', 7 * n['TEST']),
            ('P5', 4, 'F3-k', 'Fig. 3: 4 arms x kappa {1.5, 2.0} x subset C', 4 * 2 * n['C']),
            ('P6', 5, 'A-lease', 'Table II-A closed loop: Global-Margin lease + shield + heuristic x C', 1 * n['C']),
            ('P6', 5, 'A-rl', 'Table II-A RL: Bandit and FQI w/o lease features x C', 2 * n['C']),
        ]
    raise ValueError(f'unknown plan variant {variant!r}')


def _round_half_up(value, places):
    """Decimal rounding (half up) of an exact Fraction, returned as float (display value only)."""
    q = Decimal(1).scaleb(-places)
    d = (Decimal(value.numerator) / Decimal(value.denominator)).quantize(q, rounding=ROUND_HALF_UP)
    return float(d)


def _ceil_to(value, places):
    """Smallest multiple of 10^-places >= the exact Fraction (prerequisites are rounded up)."""
    scale = 10 ** places
    return math.ceil(value * scale) / scale


def run_figures(runs):
    """Every budget figure of a run count, computed from the count itself (never from other rounded figures):
    GPU-h at PLAN_S_PER_RUN, worst case at WALL_CAP_S, disk at PLAN_MB_PER_RUN (exact Fractions, then rounded half up
    for display: GPU-h to 0.1, disk GB to 0.01)."""
    runs = int(runs)
    gpu = Fraction(runs) * Fraction(PLAN_S_PER_RUN).limit_denominator() / 3600
    worst = Fraction(runs) * Fraction(WALL_CAP_S).limit_denominator() / 3600
    disk = Fraction(runs) * Fraction(PLAN_MB_PER_RUN).limit_denominator() / 1000
    return {'runs': runs, 'gpu_h': _round_half_up(gpu, 1), 'gpu_h_worst': _round_half_up(worst, 1),
            'disk_gb': _round_half_up(disk, 2), 'gpu_h_exact': float(gpu), 'disk_gb_exact': float(disk)}


def disk_prereq_gib(remaining_runs):
    """Free disk (GiB) needed before a phase to finish the plan: the remaining runs' disk plus the runner's floor,
    rounded UP to 0.1 GiB."""
    need = Fraction(int(remaining_runs)) * Fraction(PLAN_MB_PER_RUN).limit_denominator() * 10 ** 6 / 2 ** 30 \
        + Fraction(RUNNER_FLOOR_GIB).limit_denominator()
    return _ceil_to(need, 1)


def variant_budget(variant):
    """Blocks, phases and total of a plan variant. Every row is computed from its own run count (run_figures), so no
    figure is a sum of rounded values; the disk prerequisite of a phase is computed from the runs that remain."""
    blocks = []
    for phase, tier, bid, desc, runs in plan_blocks(variant):
        blocks.append({'phase': phase, 'tier': tier, 'block': bid, 'description': desc, **run_figures(runs)})
    order = []
    for b in blocks:
        if b['phase'] not in order:
            order.append(b['phase'])
    total_runs = sum(b['runs'] for b in blocks)
    phases, done = {}, 0
    for ph in order:
        runs = sum(b['runs'] for b in blocks if b['phase'] == ph)
        phases[ph] = {**run_figures(runs), 'disk_prereq_gib': disk_prereq_gib(total_runs - done),
                      'disk_prereq_alone_gib': disk_prereq_gib(runs)}
        done += runs
    total = run_figures(total_runs)
    smoke = sum(b['runs'] for b in blocks if b['phase'] == 'P1-0')
    return {'variant': variant, 'blocks': blocks, 'phases': phases, 'total': total,
            'without_smoke': run_figures(total_runs - smoke),
            'rules': 'every figure from its own run count (exact, then rounded half up: GPU-h 0.1, GB 0.01); disk '
                     'prerequisite = remaining runs x PLAN_MB_PER_RUN + the runner floor, rounded up to 0.1 GiB'}


# ------------------------------------------------------------------------------------------------- helpers

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def guarded(path):
    p = Path(path).resolve()
    for prot in PROTECTED:
        if p == prot.resolve() or prot.resolve() in p.parents:
            raise PermissionError(f'refusing to write under {prot}: {p}')
    return p


def atomic_write(path, text):
    p = guarded(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + f'.{os.getpid()}.tmp')
    tmp.write_text(text, encoding='utf-8')
    os.replace(tmp, p)


def parse_routes_xml(path):
    """route id -> {town, scenario_types, n_waypoints, length_m (2D polyline through the XML waypoints)}."""
    out = {}
    for r in ET.parse(path).getroot().iter('route'):
        rid = r.get('id')
        pts = [(float(p.get('x')), float(p.get('y'))) for p in r.iter('position')]
        # the <waypoints> positions come first; scenario trigger points are nested under <scenarios>
        wp = r.find('waypoints')
        wpts = [(float(p.get('x')), float(p.get('y'))) for p in wp.iter('position')] if wp is not None else pts
        length = sum(math.dist(a, b) for a, b in zip(wpts, wpts[1:]))
        types = sorted({s.get('type') for s in r.iter('scenario') if s.get('type')})
        out[rid] = {'town': r.get('town'), 'scenario_types': types, 'n_waypoints': len(wpts),
                    'length_m': round(length, 1)}
    return out


def pilot_measurements():
    walls = []
    if PILOT_STATUS.is_file():
        for line in PILOT_STATUS.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get('event') == 'end' and r.get('exit_code') == 0 and r.get('wall_s') is not None:
                walls.append(float(r['wall_s']))
    sizes = []
    if PILOT_RUNS.is_dir():
        for run in sorted(PILOT_RUNS.glob('*/runs/*')):
            if run.is_dir():
                sizes.append(sum(f.stat().st_size for f in run.rglob('*') if f.is_file()) / 1e6)
    def q(v, p):
        v = sorted(v)
        if not v:
            return None
        k = (len(v) - 1) * p
        lo, hi = math.floor(k), math.ceil(k)
        return v[lo] + (v[hi] - v[lo]) * (k - lo)
    return {'pilot_jobs': len(walls),
            'pilot_wall_s': {'mean': round(sum(walls) / len(walls), 1) if walls else None,
                             'min': round(min(walls), 1) if walls else None,
                             'p50': round(q(walls, 0.5), 1) if walls else None,
                             'max': round(max(walls), 1) if walls else None},
            'pilot_runs_sized': len(sizes),
            'pilot_run_mb': {'mean': round(sum(sizes) / len(sizes), 2) if sizes else None,
                             'min': round(min(sizes), 2) if sizes else None,
                             'max': round(max(sizes), 2) if sizes else None}}


def v2_tier1_wall():
    """Mean wall time of the final v2 tier-1 jobs (unmodified prefix, the 44 test routes), for reference only."""
    if not V2_STATUS.is_file():
        return None
    walls = []
    for line in V2_STATUS.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get('event') == 'end' and str(r.get('file', '')).startswith('10_tier1') and r.get('exit_code') == 0 \
                and r.get('wall_s') is not None:
            walls.append(float(r['wall_s']))
    return {'jobs': len(walls), 'mean_s': round(sum(walls) / len(walls), 1) if walls else None}


# ------------------------------------------------------------------------------------------------- build

def build():
    rj = json.loads(ROUTES_JSON.read_text())
    xml_path = ROOT / rj['routes_xml']
    xml_sha = sha256_file(xml_path)
    if xml_sha != rj['routes_xml_sha256']:
        raise SystemExit(f'routes XML sha256 mismatch: {xml_sha} != {rj["routes_xml_sha256"]}')
    xml = parse_routes_xml(xml_path)
    if len(xml) != 220:
        raise SystemExit(f'expected 220 routes in the XML, found {len(xml)}')

    by_type = {}
    for rid, info in xml.items():
        if len(info['scenario_types']) != 1:
            raise SystemExit(f'route {rid}: expected exactly one scenario type, found {info["scenario_types"]}')
        by_type.setdefault(info['scenario_types'][0], []).append(rid)
    for t in by_type:
        by_type[t].sort(key=int)
    if len(by_type) != 44 or any(len(v) != 5 for v in by_type.values()):
        raise SystemExit('expected 44 scenario types with 5 routes each')

    test = []
    for r in rj['routes']:
        rid, typ = str(r['route_id']), r['scenario_type']
        if by_type[typ][0] != rid and not (by_type[typ][0] in rj.get('excluded_routes', {})):
            raise SystemExit(f'test route {rid} is not the lowest id of {typ}')
        if [str(x) for x in r['routes_of_type']] != by_type[typ]:
            raise SystemExit(f'routes_of_type of {rid} differs from the XML order')
        test.append({'index': int(r['index']), 'route_id': rid, 'scenario_type': typ, 'town': xml[rid]['town'],
                     'length_m': xml[rid]['length_m'], 'subsets': {'E': int(r['index']) % 2 == 0,
                                                                    'C': int(r['index']) % 4 == 0,
                                                                    'R': int(r['index']) % 3 == 0}})
    test.sort(key=lambda r: r['index'])
    test_ids = {r['route_id'] for r in test}
    if len(test_ids) != 44:
        raise SystemExit('expected 44 test routes')
    # consistency with the registered v2 subsets (per-route membership lists of routes.json)
    member = {str(r['route_id']): set(r.get('subsets') or []) for r in rj['routes']}
    for key, name in (('E', 'even'), ('C', 'core11'), ('R', 'rep15')):
        for r in test:
            if r['subsets'][key] != (name in member[r['route_id']]):
                raise SystemExit(f'subset {key} of route {r["route_id"]} differs from routes.json {name}')

    train = []
    for typ, ids in by_type.items():
        rid = ids[1]
        if rid in test_ids:
            raise SystemExit(f'training route {rid} is a test route')
        train.append({'route_id': rid, 'scenario_type': typ, 'town': xml[rid]['town'], 'length_m': xml[rid]['length_m'],
                      'test_route_of_type': ids[0] if ids[0] in test_ids else ids[1]})
    train.sort(key=lambda r: int(r['route_id']))
    for i, r in enumerate(train):
        r['index'] = i
        r['subsets'] = {'T22a': i % 4 == 0, 'T22b': i % 4 == 2, 'T22': i % 2 == 0, 'RL': True}
        r['dev_route'] = r['route_id'] == DEV_ROUTE
        r['pilot_route'] = r['route_id'] in PILOT_ROUTES
    train_ids = {r['route_id'] for r in train}
    assert not (train_ids & test_ids)
    assert DEV_ROUTE in train_ids and set(PILOT_ROUTES) <= train_ids
    # every scenario type exactly once in each pool
    assert sorted(r['scenario_type'] for r in train) == sorted(r['scenario_type'] for r in test)

    def ids(rows, key):
        return [r['route_id'] for r in rows if r['subsets'][key]]

    split = {
        'schema': 'framelease_v4.protocol.route_split/1',
        'routes_xml': rj['routes_xml'], 'routes_xml_sha256': xml_sha,
        'test_source': str(ROUTES_JSON.relative_to(ROOT)), 'test_source_sha256': sha256_file(ROUTES_JSON),
        'rules': {
            'test': 'the 44 routes of outputs/framelease_v2/closed_loop_matrix/routes.json (lowest route id of each '
                    'scenario type; dev route 2086 excluded there, which did not change the selection)',
            'training_pool': 'the second-lowest route id of each scenario type (numeric order); disjoint from test',
            'test_subsets': 'E = index % 2 == 0 (22), C = index % 4 == 0 (11), R = index % 3 == 0 (15) (v2 definitions)',
            'training_subsets': 'index = position in the id-sorted training list; T22a = index % 4 == 0 (11), '
                                'T22b = index % 4 == 2 (11), T22 = T22a + T22b (tuning), RL = all 44',
        },
        'test': test, 'training': train,
        'subsets': {'test_all': [r['route_id'] for r in test], 'E': ids(test, 'E'), 'C': ids(test, 'C'),
                    'R': ids(test, 'R'), 'train_all': [r['route_id'] for r in train], 'T22a': ids(train, 'T22a'),
                    'T22b': ids(train, 'T22b'), 'T22': ids(train, 'T22'), 'RL': ids(train, 'RL')},
        'totals': {'test_length_km': round(sum(r['length_m'] for r in test) / 1000, 2),
                   'train_length_km': round(sum(r['length_m'] for r in train) / 1000, 2),
                   'test_towns': _count(r['town'] for r in test), 'train_towns': _count(r['town'] for r in train)},
    }
    for key in ('E', 'C', 'R', 'T22a', 'T22b', 'T22'):
        assert len(split['subsets'][key]) == N[key], (key, len(split['subsets'][key]))

    meas = pilot_measurements()
    budget = {'schema': 'framelease_v4.protocol.budget/3',
              'planning': {'s_per_run': PLAN_S_PER_RUN, 'mb_per_run': PLAN_MB_PER_RUN, 'wall_cap_s': WALL_CAP_S,
                           'runner_floor_gib': RUNNER_FLOOR_GIB},
              'measured': {**meas, 'v2_tier1_wall_unmodified_prefix': v2_tier1_wall()},
              'default_variant': 'FULL', 'variants': {v: variant_budget(v) for v in VARIANTS}}
    return split, budget


def _count(it):
    out = {}
    for x in it:
        out[x] = out.get(x, 0) + 1
    return dict(sorted(out.items()))


def budget_md(split, budget, variant='FULL'):
    vb = budget['variants'][variant]
    title = {'FULL': 'FULL (the registered plan, default)', 'TRIMMED': 'TRIMMED (reduced plan, PROTOCOL Sec. 14)'}
    L = [f'# Run budget, variant {title[variant]} (generated by framelease_v4/protocol/make_protocol_tables.py)', '',
         f"Planning figures: {budget['planning']['s_per_run']:.0f} s (7.5 min) of GPU wall time and "
         f"{budget['planning']['mb_per_run']:.0f} MB of disk per closed-loop run; worst case = every run hits the "
         f"{budget['planning']['wall_cap_s']:.0f} s wall cap.", '']
    m = budget['measured']
    L.append(f"Measured: {m['pilot_jobs']} fast-prefix pilot jobs, wall time mean {m['pilot_wall_s']['mean']} s "
             f"(min {m['pilot_wall_s']['min']}, median {m['pilot_wall_s']['p50']}, max {m['pilot_wall_s']['max']}); "
             f"{m['pilot_runs_sized']} pilot run directories, {m['pilot_run_mb']['mean']} MB mean "
             f"({m['pilot_run_mb']['min']}-{m['pilot_run_mb']['max']} MB).")
    if m.get('v2_tier1_wall_unmodified_prefix'):
        v = m['v2_tier1_wall_unmodified_prefix']
        L.append(f"Reference: v2 tier-1 jobs (unmodified prefix, the 44 test routes): {v['jobs']} jobs, mean {v['mean_s']} s.")
    L += ['', '| phase | tier | block | content | runs | GPU-h | GPU-h worst | disk GB |', '|---|---:|---|---|---:|---:|---:|---:|']
    for b in vb['blocks']:
        L.append(f"| {b['phase']} | {b['tier']} | {b['block']} | {b['description']} | {b['runs']} | {b['gpu_h']} | "
                 f"{b['gpu_h_worst']} | {b['disk_gb']} |")
    L += ['', '| phase | runs | GPU-h | GPU-h worst | disk GB | free disk needed at phase start, rest of the plan (GiB) | '
          'free disk needed for this phase alone (GiB) |', '|---|---:|---:|---:|---:|---:|---:|']
    for ph, p in vb['phases'].items():
        L.append(f"| {ph} | {p['runs']} | {p['gpu_h']} | {p['gpu_h_worst']} | {p['disk_gb']} | {p['disk_prereq_gib']} | "
                 f"{p['disk_prereq_alone_gib']} |")
    t = vb['total']
    L.append(f"| total | {t['runs']} | {t['gpu_h']} | {t['gpu_h_worst']} | {t['disk_gb']} | | |")
    w = vb['without_smoke']
    L.append('')
    L.append(f"Without the P1-0 smoke block: {w['runs']} runs, {w['gpu_h']} GPU-h, {w['disk_gb']} GB.")
    L.append('')
    L.append('Every figure is computed from its own run count (exact, then rounded half up: GPU-h to 0.1, GB to 0.01); '
             'no figure is a sum of rounded values, so a column need not add up to its rounded total. The free-disk '
             'prerequisite of a phase is the disk of the runs that remain from that phase on plus the runner floor of '
             f"{budget['planning']['runner_floor_gib']:.0f} GiB, rounded up to 0.1 GiB.")
    L += ['', f"Route lengths (XML polyline): test {split['totals']['test_length_km']} km, training "
              f"{split['totals']['train_length_km']} km.", '']
    return '\n'.join(L) + '\n'


def render(split, budget):
    return {'route_split.json': json.dumps(split, indent=1, sort_keys=False) + '\n',
            'budget.json': json.dumps(budget, indent=1, sort_keys=False) + '\n',
            'budget.md': budget_md(split, budget, 'FULL'),
            'budget_trimmed.md': budget_md(split, budget, 'TRIMMED')}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true', help='re-derive and compare with the written files; write nothing')
    a = ap.parse_args(argv)
    split, budget = build()
    files = render(split, budget)
    if a.check:
        bad = [n for n, text in files.items() if not (OUT / n).is_file() or (OUT / n).read_text() != text]
        print('check:', 'OK' if not bad else f'DIFFERS {bad}')
        return 1 if bad else 0
    for name, text in files.items():
        atomic_write(OUT / name, text)
    manifest = ''.join(f'{sha256_file(OUT / n)}  {n}\n' for n in sorted(files))
    manifest += f'{sha256_file(Path(__file__))}  framelease_v4/protocol/{Path(__file__).name}\n'
    atomic_write(OUT / 'MANIFEST.sha256', manifest)
    print(json.dumps({'test': len(split['test']), 'training': len(split['training']), 'subsets':
                      {k: len(v) for k, v in split['subsets'].items()}, 'totals': split['totals'],
                      'budget_total': {v: b['total'] for v, b in budget['variants'].items()},
                      'phases': {v: b['phases'] for v, b in budget['variants'].items()},
                      'measured': budget['measured']}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
