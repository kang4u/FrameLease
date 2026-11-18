#!/usr/bin/env python3
"""Pre-registered closed-loop experiment matrix: route set, arms, priority tiers -> GPU queue job files.

The matrix is fixed by framelease_v2/PREREGISTRATION.md. This script only materializes it:

  python framelease_v2/closed_loop_matrix.py              # print routes, subsets and job counts; write nothing
  python framelease_v2/closed_loop_matrix.py --check      # also validate every job command (CPU only, no CARLA)
  python framelease_v2/closed_loop_matrix.py --write      # write routes.json and jobs.d/{10,20,30,40,50}_tier*.jsonl

Route set: one Bench2Drive route per scenario type of bench2drive220.xml, the lowest route id of the type,
skipping the development route 2086 (the next-lowest id of its type would be used if 2086 were the lowest).
"The list" is these routes sorted by route id; index = position in that list.

Subsets (deterministic from the list index): all (44), even = index % 2 == 0 (22, oracle_sync),
core11 = index % 4 == 0 (11; kappa 2.0, FrameLease, max-age-2.0 cap ablation), rep15 = index % 3 == 0 (15; seed-12
replicates). Within a tier the route order is shuffled with random.Random(20261107 + tier); all arms of a route run
back to back, in an order drawn from the same generator (counterbalanced).

Job line (queue contract): {"id", "kind": "closed_loop", "tier", "cmd", "wall_cap_s"} plus descriptive keys
(arm, route_id, route_index, scenario_type, town, policy, kappa, seed, max_age_s, lease_params) that the runner
copies into its status records.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
ROUTES_XML_REL = 'third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/data/bench2drive220.xml'
EXCLUDED_ROUTES = {'2086': 'development route of the closed-loop smoke test (routes_debug.xml)'}
OUTPUT_DIR_REL = 'outputs/framelease_v2/closed_loop_matrix'
QUEUE_DIR_REL = 'outputs/framelease_v2/gpu_queue'
LEASE_PARAMS_REL = 'outputs/framelease_v2/c2_calibration/full_20261107T045343Z/lease_params_q95_envelope.json'
PYTHON = str(ROOT / '.conda-unidrive-linux/bin/python')
ORDER_SEED = 20261107
PORT_BASE = 2500          # job i of a tier file uses PORT_BASE + 10 * (i % 4); +1, +2 and +6000 are also used
LATENCY_WALL_CAP_S = 25 * 60
ORACLE_WALL_CAP_S = 110 * 60
LAUNCHER_MARGIN_S = 90    # run_closed_loop --timeout-s = wall cap - margin: its own graceful timeout fires first
LOCK_WAIT_S = 600         # the runner waits for the shared GPU lock first; this only covers a start-up race
NON_LEASE_MAX_AGE_S = 3.0  # plan horizon; non-lease latency arms expire plans at 3.0 s observation age
# Files that determine closed-loop behaviour (run_closed_loop.CODE_DEPENDENCIES + the official evaluator stack + the
# route file + the lease parameters). Every job pins their sha256 ("require_sha256"); gpu_queue.py does not start a
# job whose pinned files differ (another worker editing them mid-matrix would otherwise mix code versions).
PINNED_FILES = ('framelease_v2/run_closed_loop.py', 'framelease_v2/latency_agent.py', 'framelease_v2/policies.py',
                'framelease_v2/lease.py', 'framelease_v2/geometry.py', 'framelease_v2/unidrive_boxes.py',
                'framelease_common.py', 'stage02_real_vla.py', 'stage05_carla_closed_loop.py', 'linux/env.sh',
                'third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/leaderboard/leaderboard_evaluator.py',
                'third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/team_code/unidrivevla_b2d_agent.py',
                'third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/team_code/pid_controller.py',
                'third_party/UniDriveVLA-linux/Bench2Drive/projects/configs/unidrivevla_b2d_stage2_unified_2b.py',
                ROUTES_XML_REL, LEASE_PARAMS_REL)


@dataclass(frozen=True)
class Arm:
    name: str
    policy: str
    kappa: float = 1.0
    seed: int = 11
    runtime_params: Optional[dict] = None
    lease_params: Optional[str] = None
    expected_max_age_s: Optional[float] = None
    description: str = ''

    @property
    def wall_cap_s(self):
        return ORACLE_WALL_CAP_S if self.policy == 'oracle_sync' else LATENCY_WALL_CAP_S


def _latency(name, policy, kappa, seed=11, max_age=NON_LEASE_MAX_AGE_S, description=''):
    return Arm(name, policy, kappa, seed, {'max_age_s': max_age}, None, max_age, description)


ARMS = {a.name: a for a in (
    _latency('fixed_deep_k1.0_s11', 'fixed_deep', 1.0, description='Fixed Deep (10 flow steps), kappa 1.0'),
    _latency('fast_only_k1.0_s11', 'fast_only', 1.0, description='Fast Only (1 flow step), kappa 1.0'),
    Arm('oracle_sync_s11', 'oracle_sync', 1.0, 11, None, None, None,
        'official synchronous zero-latency agent (world paused for the full model every tick)'),
    _latency('fixed_deep_k1.5_s11', 'fixed_deep', 1.5, description='Fixed Deep, kappa 1.5'),
    _latency('fast_only_k1.5_s11', 'fast_only', 1.5, description='Fast Only, kappa 1.5'),
    _latency('fixed_deep_k2.0_s11', 'fixed_deep', 2.0, description='Fixed Deep, kappa 2.0'),
    Arm('framelease_q95env_k1.0_s11', 'framelease', 1.0, 11, None, LEASE_PARAMS_REL, 2.0,
        'FrameLease, pre-registered AVL bounds lease_params_q95_envelope.json (global margin, reserve 0.2 m, '
        'H_max 2.0 s; runtime max_age_s = H_max), kappa 1.0'),
    _latency('fixed_deep_k1.0_s12', 'fixed_deep', 1.0, seed=12, description='Fixed Deep, kappa 1.0, seed 12'),
    _latency('fast_only_k1.0_s12', 'fast_only', 1.0, seed=12, description='Fast Only, kappa 1.0, seed 12'),
    _latency('fixed_deep_age2.0_k1.0_s11', 'fixed_deep', 1.0, max_age=2.0,
             description='Fixed Deep, kappa 1.0, max_age_s 2.0 (cap ablation: the lease arm\'s H_max)'),
)}

SUBSETS = {
    'all': lambda i: True,
    'even': lambda i: i % 2 == 0,
    'core11': lambda i: i % 4 == 0,
    'rep15': lambda i: i % 3 == 0,
}

# (tier, file name, [(subset, [arms])])
TIERS = (
    (1, '10_tier1.jsonl', (('all', ('fixed_deep_k1.0_s11', 'fast_only_k1.0_s11')),)),
    (2, '20_tier2.jsonl', (('even', ('oracle_sync_s11',)),)),
    (3, '30_tier3.jsonl', (('all', ('fixed_deep_k1.5_s11', 'fast_only_k1.5_s11')),)),
    (4, '40_tier4.jsonl', (('core11', ('fixed_deep_k2.0_s11', 'framelease_q95env_k1.0_s11')),)),
    (5, '50_tier5.jsonl', (('rep15', ('fixed_deep_k1.0_s12', 'fast_only_k1.0_s12')),
                           ('core11', ('fixed_deep_age2.0_k1.0_s11',)))),
)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def select_routes(xml_path=ROOT / ROUTES_XML_REL, excluded=EXCLUDED_ROUTES):
    """One route per scenario type: the lowest route id of the type that is not excluded; sorted by id."""
    by_type = defaultdict(list)
    for route in ET.parse(xml_path).iter('route'):
        types = sorted({s.attrib['type'] for s in route.iter('scenario')})
        if len(types) != 1:
            raise ValueError(f'route {route.attrib.get("id")}: expected one scenario type, got {types}')
        by_type[types[0]].append((int(route.attrib['id']), route.attrib['town']))
    chosen = []
    for stype, routes in by_type.items():
        routes.sort()
        candidates = [r for r in routes if str(r[0]) not in excluded]
        if not candidates:
            raise ValueError(f'no eligible route of type {stype}')
        rid, town = candidates[0]
        chosen.append({'route_id': str(rid), 'scenario_type': stype, 'town': town,
                       'lowest_id_of_type': str(routes[0][0]),
                       'substituted_for_excluded': str(routes[0][0]) if str(routes[0][0]) in excluded else None,
                       'routes_of_type': [str(r[0]) for r in routes]})
    chosen.sort(key=lambda r: int(r['route_id']))
    for i, r in enumerate(chosen):
        r['index'] = i
        r['subsets'] = [name for name, keep in SUBSETS.items() if keep(i)]
    return chosen


def arm_args(arm):
    args = ['--policy', arm.policy]
    if arm.policy != 'oracle_sync':
        args += ['--kappa', f'{arm.kappa:.1f}']
    args += ['--seed', str(arm.seed)]
    if arm.runtime_params:
        args += ['--runtime-params', json.dumps(arm.runtime_params, sort_keys=True)]
    if arm.lease_params:
        args += ['--lease-params', arm.lease_params]
    return args


def code_pins():
    return {rel: sha256(ROOT / rel) for rel in PINNED_FILES}


def job_for(tier, arm, route, port, pins):
    cmd = [PYTHON, 'framelease_v2/run_closed_loop.py', *arm_args(arm), '--routes', ROUTES_XML_REL,
           '--route-id', route['route_id'], '--port', str(port), '--output-dir', OUTPUT_DIR_REL,
           '--timeout-s', str(arm.wall_cap_s - LAUNCHER_MARGIN_S), '--lock-wait-s', str(LOCK_WAIT_S)]
    return {'id': f't{tier}_{arm.name}_r{route["route_id"]}', 'kind': 'closed_loop', 'tier': tier, 'cmd': cmd,
            'wall_cap_s': arm.wall_cap_s, 'arm': arm.name, 'policy': arm.policy, 'kappa': arm.kappa,
            'seed': arm.seed, 'max_age_s': arm.expected_max_age_s, 'lease_params': arm.lease_params,
            'route_id': route['route_id'], 'route_index': route['index'],
            'scenario_type': route['scenario_type'], 'town': route['town'], 'require_sha256': pins}


def build_tiers(routes, pins=None):
    """{file name: [job, ...]} in execution order."""
    pins = code_pins() if pins is None else pins
    out = {}
    for tier, fname, groups in TIERS:
        per_route = defaultdict(list)
        for subset, arm_names in groups:
            for r in routes:
                if SUBSETS[subset](r['index']):
                    per_route[r['route_id']].extend(arm_names)
        rng = random.Random(ORDER_SEED + tier)
        order = [r for r in routes if r['route_id'] in per_route]
        rng.shuffle(order)
        jobs = []
        for r in order:
            arms = list(per_route[r['route_id']])
            rng.shuffle(arms)
            for name in arms:
                jobs.append(job_for(tier, ARMS[name], r, PORT_BASE + 10 * (len(jobs) % 4), pins))
        out[fname] = jobs
    ids = [j['id'] for jobs in out.values() for j in jobs]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate job ids')
    return out


def check_jobs(tiers):
    """Validate every command with run_closed_loop's own argument parsing, configuration and preflight checks."""
    sys.path.insert(0, str(ROOT))
    import contextlib
    import io
    from framelease_v2 import run_closed_loop as rcl
    problems = []
    for fname, jobs in tiers.items():
        for job in jobs:
            argv = job['cmd'][2:]
            try:
                args = rcl.parse_args(argv)
                with contextlib.redirect_stderr(io.StringIO()):
                    cfg = rcl.agent_config(args)
                info = rcl.preflight(args)
                rt = cfg['runtime']
                checks = {'policy': (cfg['mode'], job['policy']), 'seed': (cfg['seed'], job['seed']),
                          'route': (info['route_id'], job['route_id']),
                          'scenario': (info['scenarios'], [job['scenario_type']]), 'town': (info['town'], job['town'])}
                if job['policy'] != 'oracle_sync':
                    checks['kappa'] = (rt['kappa'], job['kappa'])
                    checks['max_age_s'] = (rt['max_age_s'], job['max_age_s'])
                    lease = cfg['lease_params_path']
                    want = str((ROOT / job['lease_params']).resolve()) if job['lease_params'] else None
                    checks['lease_params'] = (lease, want)
                for key, (got, want) in checks.items():
                    if got != want:
                        problems.append(f'{job["id"]}: {key} = {got!r}, expected {want!r}')
                if job['cmd'][0] != PYTHON or not Path(PYTHON).is_file():
                    problems.append(f'{job["id"]}: interpreter {job["cmd"][0]}')
            except BaseException as e:  # noqa: BLE001  (SystemExit from preflight included)
                problems.append(f'{job["id"]}: {type(e).__name__}: {e}')
    return problems


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--check', action='store_true', help='validate every job command (CPU only)')
    p.add_argument('--write', action='store_true', help='write routes.json and the tier job files')
    p.add_argument('--root', type=Path, default=ROOT, help='write under this root instead of the project (tests)')
    p.add_argument('--force', action='store_true', help='overwrite existing files (never after results exist)')
    args = p.parse_args(argv)

    routes = select_routes()
    tiers = build_tiers(routes)
    print(f'{len(routes)} routes (one per scenario type; excluded: {sorted(EXCLUDED_ROUTES)})')
    for r in routes:
        print(f'  [{r["index"]:2d}] {r["route_id"]:>6} {r["town"]:<9} {r["scenario_type"]:<42} {",".join(r["subsets"])}')
    for fname, jobs in tiers.items():
        caps = sum(j['wall_cap_s'] for j in jobs)
        print(f'{fname}: {len(jobs)} jobs, {len({j["route_id"] for j in jobs})} routes, '
              f'arms {sorted({j["arm"] for j in jobs})}, wall-cap sum {caps / 3600:.1f} h')
    print(f'total jobs: {sum(len(j) for j in tiers.values())}')

    if args.check or args.write:
        problems = check_jobs(tiers)
        if problems:
            print('JOB CHECK FAILED:\n  ' + '\n  '.join(problems), file=sys.stderr)
            return 1
        print(f'job check: all {sum(len(j) for j in tiers.values())} commands pass run_closed_loop parsing, '
              'configuration and preflight')
    if not args.write:
        return 0

    root = args.root.resolve()
    out_dir = root / OUTPUT_DIR_REL
    jobs_dir = root / QUEUE_DIR_REL / 'jobs.d'
    runs = out_dir / 'runs'
    if runs.is_dir() and any(runs.iterdir()):
        print(f'refusing to write: {runs} already contains runs (the matrix is pre-registered)', file=sys.stderr)
        return 1
    targets = [out_dir / 'routes.json'] + [jobs_dir / f for f in tiers]
    existing = [t for t in targets if t.exists()]
    if existing and not args.force:
        print('refusing to overwrite (use --force before any result exists): ' + ', '.join(map(str, existing)),
              file=sys.stderr)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs_dir.mkdir(parents=True, exist_ok=True)
    xml = ROOT / ROUTES_XML_REL
    manifest = {'schema': 'framelease_v2.closed_loop_matrix/1', 'routes_xml': ROUTES_XML_REL,
                'routes_xml_sha256': sha256(xml), 'excluded_routes': EXCLUDED_ROUTES,
                'selection_rule': 'one route per scenario type: lowest route id of the type, excluded ids skipped; '
                                  'list sorted by route id',
                'subsets': {'all': 'every route', 'even': 'index % 2 == 0', 'core11': 'index % 4 == 0',
                            'rep15': 'index % 3 == 0'},
                'order_seed': ORDER_SEED, 'port_base': PORT_BASE,
                'arms': {a.name: {'policy': a.policy, 'kappa': a.kappa, 'seed': a.seed,
                                  'runtime_params': a.runtime_params, 'lease_params': a.lease_params,
                                  'expected_max_age_s': a.expected_max_age_s, 'wall_cap_s': a.wall_cap_s,
                                  'description': a.description} for a in ARMS.values()},
                'tiers': [{'tier': t, 'file': f, 'groups': [{'subset': s, 'arms': list(a)} for s, a in g],
                           'jobs': len(tiers[f])} for t, f, g in TIERS],
                'code_pins': tiers[next(iter(tiers))][0]['require_sha256'],
                'routes': routes}
    (out_dir / 'routes.json').write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8')
    for fname, jobs in tiers.items():
        (jobs_dir / fname).write_text(''.join(json.dumps(j, sort_keys=True) + '\n' for j in jobs), encoding='utf-8')
    for t in targets:
        print(f'wrote {t}  sha256 {sha256(t)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
