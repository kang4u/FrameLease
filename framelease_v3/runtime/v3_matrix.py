#!/usr/bin/env python3
"""v3 closed-loop job files (pilot and main matrix) for framelease_v2/gpu_queue.py. Writes nothing unless --write.

  python framelease_v3/runtime/v3_matrix.py            # print routes, job counts and order; write nothing
  python framelease_v3/runtime/v3_matrix.py --check    # also validate every job command (CPU only, no CARLA / GPU)
  python framelease_v3/runtime/v3_matrix.py --write    # write <out>/matrix.json and <queue>/jobs.d/*.jsonl

Routes
* Test routes: the 44 routes of the v2 matrix (framelease_v2.closed_loop_matrix.select_routes(): one route per
  scenario type of bench2drive220.xml, the lowest id of the type, the development route 2086 excluded; checked
  against outputs/framelease_v2/closed_loop_matrix/routes.json).
* Pilot routes (never test routes): 2086 (the development route) and, for the first three scenario types in the
  routes.json order (sorted by route id), the second-lowest route id of the type.

Jobs (seed 11, kappa 1.0; the same queue contract, wall caps and launcher options as the v2 matrix)
* pilot: 4 routes x [fl_v3_heuristic, fast_only] = 8 jobs, one file; per route both arms back to back
  (fl_v3_heuristic first on even positions, fast_only first on odd ones).
* main: 44 routes x 5 arms = 220 jobs in two files so that fl_v3_heuristic and fast_only finish first:
  10_tier1_v3_fast.jsonl (fl_v3_heuristic, fast_only; 88) then 20_tier2_baselines.jsonl (fixed_deep,
  fixed_deep_age2.0, fl_global; 132). Within a file the route order is shuffled with random.Random(ORDER_SEED + tier)
  and all arms of a route run back to back in an order drawn from the same generator (as the v2 matrix).
Ports: line i of a file uses PORT_BASE + 10 (i mod 4) (pilot 2800, main 2700; +1, +2 and +6000 are also used); the
v2 matrix used 2500-2530 and the v2 launcher default is 2400. Output and queue directories are under
outputs/framelease_v3/closed_loop/ only.
Every job pins (require_sha256) the 16 files the v2 matrix pinned, framelease_v2/__init__.py and the v3 runtime
sources (framelease_v3/__init__.py and framelease_v3/runtime/*.py used by the launcher and the agent); gpu_queue.py
does not start a job while any of them differs.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v3.runtime import v3_arms as A  # noqa: E402

PYTHON = str(ROOT / '.conda-unidrive-linux/bin/python')
LAUNCHER_REL = 'framelease_v3/runtime/run_closed_loop_v3.py'
V2_ROUTES_JSON_REL = 'outputs/framelease_v2/closed_loop_matrix/routes.json'
OUT_ROOT_REL = 'outputs/framelease_v3/closed_loop'
MATRICES = {
    'pilot': {'out': OUT_ROOT_REL + '/pilot', 'queue': OUT_ROOT_REL + '/pilot_queue', 'port_base': 2800},
    'main': {'out': OUT_ROOT_REL + '/main', 'queue': OUT_ROOT_REL + '/main_queue', 'port_base': 2700},
}
PILOT_ARMS = ('fl_v3_heuristic', 'fast_only')
MAIN_TIERS = ((1, '10_tier1_v3_fast.jsonl', ('fl_v3_heuristic', 'fast_only')),
              (2, '20_tier2_baselines.jsonl', ('fixed_deep', 'fixed_deep_age2.0', 'fl_global')))
PILOT_FILE = '10_pilot.jsonl'
# OPTIONAL (not in jobs.d; the runner never sees it unless it is moved there): fl_v3_heuristic with two envelopes of the
# offline Gate-2 study on the pilot routes, in case the default isotropic q95 envelope leaves the arm in fallback.
GATE2_ENV_DIR = 'outputs/framelease_v3/gate2_offline/gate2_20261109/envelopes'
ENVELOPE_VARIANTS = (('E0q80', GATE2_ENV_DIR + '/E0_q80_ORIG.json'), ('B0', GATE2_ENV_DIR + '/B0_q0_NONE.json'))
OPTIONAL_DIR = 'optional'
OPTIONAL_FILE = '15_pilot_envelope_variants.jsonl'
DEV_ROUTE = '2086'
SEED = 11
KAPPA = 1.0
ORDER_SEED = 20261109
WALL_CAP_S = 25 * 60          # v2 LATENCY_WALL_CAP_S
LAUNCHER_MARGIN_S = 90        # v2: launcher --timeout-s = wall cap - margin
LOCK_WAIT_S = 600             # v2
V2_PINNED = ('framelease_v2/run_closed_loop.py', 'framelease_v2/latency_agent.py', 'framelease_v2/policies.py',
             'framelease_v2/lease.py', 'framelease_v2/geometry.py', 'framelease_v2/unidrive_boxes.py',
             'framelease_common.py', 'stage02_real_vla.py', 'stage05_carla_closed_loop.py', 'linux/env.sh',
             'third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/leaderboard/leaderboard_evaluator.py',
             'third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/team_code/unidrivevla_b2d_agent.py',
             'third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/team_code/pid_controller.py',
             'third_party/UniDriveVLA-linux/Bench2Drive/projects/configs/unidrivevla_b2d_stage2_unified_2b.py',
             A.ROUTES_XML_REL, A.LEASE_PARAMS_REL)
V3_PINNED = ('framelease_v2/__init__.py', 'framelease_v3/__init__.py', 'framelease_v3/runtime/__init__.py',
             'framelease_v3/runtime/v3_lease.py', 'framelease_v3/runtime/v3_shield.py',
             'framelease_v3/runtime/v3_commit.py', 'framelease_v3/runtime/v3_scheduler.py',
             'framelease_v3/runtime/v3_agent.py', 'framelease_v3/runtime/v3_arms.py', LAUNCHER_REL)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def code_pins():
    return {rel: sha256(ROOT / rel) for rel in V2_PINNED + V3_PINNED}


# ============================================================================================ routes

def test_routes():
    """The 44 v2 test routes (recomputed with v2's rule and checked against the registered routes.json)."""
    from framelease_v2 import closed_loop_matrix as M2
    routes = M2.select_routes()
    registered = json.loads((ROOT / V2_ROUTES_JSON_REL).read_text(encoding='utf-8'))['routes']
    if [r['route_id'] for r in routes] != [r['route_id'] for r in registered]:
        raise ValueError('recomputed test routes differ from the registered v2 routes.json')
    return routes


def pilot_routes(tests):
    """2086 + the second-lowest id of the first three scenario types (routes.json order); none is a test route."""
    test_ids = {r['route_id'] for r in tests}
    dev = [r for r in tests if DEV_ROUTE in r['routes_of_type']]
    if len(dev) != 1:
        raise ValueError('development route 2086 not found in exactly one scenario type')
    out = [{'route_id': DEV_ROUTE, 'scenario_type': dev[0]['scenario_type'], 'town': None,
            'rule': 'development route of the v2 smoke test (excluded from the 44 test routes)'}]
    for r in tests:
        if len(out) == 4:
            break
        if r['scenario_type'] in {x['scenario_type'] for x in out}:
            continue
        cands = [x for x in r['routes_of_type'] if x not in test_ids and x != DEV_ROUTE]
        second = r['routes_of_type'][1]
        if second in test_ids or second == DEV_ROUTE or not cands:
            raise ValueError(f'type {r["scenario_type"]}: second-lowest id {second} is not eligible')
        out.append({'route_id': second, 'scenario_type': r['scenario_type'], 'town': None,
                    'rule': f'second-lowest route id of type {r["scenario_type"]} (test route {r["route_id"]})'})
    import xml.etree.ElementTree as ET
    towns = {}
    for route in ET.parse(ROOT / A.ROUTES_XML_REL).iter('route'):
        towns[route.attrib['id']] = (route.attrib['town'], sorted({s.attrib['type'] for s in route.iter('scenario')}))
    for r in out:
        town, types = towns[r['route_id']]
        if types != [r['scenario_type']]:
            raise ValueError(f'route {r["route_id"]}: scenario types {types} != {r["scenario_type"]}')
        r['town'] = town
    if len({r['scenario_type'] for r in out}) != 4 or any(r['route_id'] in test_ids for r in out):
        raise ValueError('pilot routes must be 4 non-test routes of 4 different scenario types')
    for i, r in enumerate(out):
        r['index'] = None
        r['pilot_index'] = i
    return out


# ============================================================================================ jobs

def job_for(matrix, tier, arm_name, route, port, pins, variant=None):
    arm = A.ARMS[arm_name]
    m = MATRICES[matrix]
    cmd = [PYTHON, LAUNCHER_REL, '--arm', arm_name, '--kappa', f'{KAPPA:.1f}', '--seed', str(SEED),
           '--routes', A.ROUTES_XML_REL, '--route-id', route['route_id'], '--port', str(port),
           '--output-dir', m['out'], '--timeout-s', str(WALL_CAP_S - LAUNCHER_MARGIN_S), '--lock-wait-s', str(LOCK_WAIT_S)]
    envelope = None
    name = arm_name
    if variant is not None:
        tag, envelope = variant
        cmd += ['--envelope', envelope]
        name = f'{arm_name}_{tag}'
        pins = {**pins, envelope: sha256(ROOT / envelope)}
    prefix = 'v3p' if matrix == 'pilot' else f'v3m{tier}'
    return {'id': f'{prefix}_{A.arm_id(name, KAPPA, SEED)}_r{route["route_id"]}', 'kind': 'closed_loop',
            'tier': tier, 'cmd': cmd, 'wall_cap_s': WALL_CAP_S, 'matrix': matrix, 'arm': A.arm_id(name, KAPPA, SEED),
            'arm_name': arm_name, 'title': arm.title, 'v2_arm': arm.v2_arm, 'policy': arm.policy, 'kappa': KAPPA,
            'seed': SEED, 'max_age_s': arm.expected_max_age_s, 'lease_params': arm.lease_params, 'envelope': envelope,
            'exploratory': variant is not None,
            'route_id': route['route_id'], 'route_index': route.get('index'), 'pilot_index': route.get('pilot_index'),
            'scenario_type': route['scenario_type'], 'town': route['town'], 'require_sha256': pins}


def build_pilot(routes, pins):
    jobs = []
    for i, r in enumerate(routes):
        arms = PILOT_ARMS if i % 2 == 0 else tuple(reversed(PILOT_ARMS))
        for a in arms:
            jobs.append(job_for('pilot', 0, a, r, MATRICES['pilot']['port_base'] + 10 * (len(jobs) % 4), pins))
    return {PILOT_FILE: jobs}


def build_pilot_variants(routes, pins):
    """OPTIONAL envelope variants of fl_v3_heuristic on the pilot routes (written outside jobs.d)."""
    jobs = []
    for r in routes:
        for v in ENVELOPE_VARIANTS:
            if (ROOT / v[1]).is_file():
                jobs.append(job_for('pilot', 0, 'fl_v3_heuristic', r,
                                    MATRICES['pilot']['port_base'] + 10 * (len(jobs) % 4), pins, v))
    return {OPTIONAL_FILE: jobs} if jobs else {}


def build_main(routes, pins):
    out = {}
    for tier, fname, arms in MAIN_TIERS:
        rng = random.Random(ORDER_SEED + tier)
        order = list(routes)
        rng.shuffle(order)
        jobs = []
        for r in order:
            names = list(arms)
            rng.shuffle(names)
            for a in names:
                jobs.append(job_for('main', tier, a, r, MATRICES['main']['port_base'] + 10 * (len(jobs) % 4), pins))
        out[fname] = jobs
    return out


def check_jobs(files, v2_jobs=None):
    """Validate every command with the v3 launcher's own parsing, configuration and preflight (CPU only).

    Baseline jobs: the v2 agent configuration built from the delegated argument list must equal the one the
    registered v2 matrix job of the same v2 arm (any route) builds, with only the route substituted."""
    from framelease_v2 import run_closed_loop as R2
    from framelease_v3.runtime import run_closed_loop_v3 as L
    problems = []
    v2_by_arm = {}
    for j in (v2_jobs or []):
        v2_by_arm.setdefault(j['arm'], j)
    for fname, jobs in files.items():
        for job in jobs:
            try:
                if job['cmd'][0] != PYTHON or not Path(PYTHON).is_file() or job['cmd'][1] != LAUNCHER_REL:
                    problems.append(f'{job["id"]}: interpreter / launcher {job["cmd"][:2]}')
                args = L.parse_args(job['cmd'][2:])
                arm = A.ARMS[args.arm]
                with contextlib.redirect_stderr(io.StringIO()):
                    if arm.is_v3:
                        cfg, lease, envelope = L.v3_configs(args)
                        ns = L.v2_namespace(args, lease)
                        info = L.preflight_v3(ns, lease, envelope)
                        agent, rt = cfg['agent'], cfg['agent']['runtime']
                        lease_path = agent['lease_params_path']
                    else:
                        a2 = R2.parse_args(L.v2_argv(args))
                        agent = R2.agent_config(a2)
                        info = R2.preflight(a2)
                        rt = agent['runtime']
                        lease_path = agent['lease_params_path']
                        ref = v2_by_arm.get(arm.v2_arm)
                        if v2_jobs is not None:
                            if ref is None:
                                problems.append(f'{job["id"]}: no registered v2 job of arm {arm.v2_arm}')
                            else:
                                rcmd = list(ref['cmd'][2:])
                                rcmd[rcmd.index('--route-id') + 1] = job['route_id']
                                ref_cfg = R2.agent_config(R2.parse_args(rcmd))
                                if ref_cfg != agent:
                                    problems.append(f'{job["id"]}: agent configuration differs from v2 arm {arm.v2_arm}')
                want_lease = str((ROOT / job['lease_params']).resolve()) if job['lease_params'] else None
                if arm.is_v3:
                    want_env = str((ROOT / job['envelope']).resolve()) if job.get('envelope') else None
                    if cfg['v3']['envelope_path'] != want_env:
                        problems.append(f'{job["id"]}: envelope {cfg["v3"]["envelope_path"]!r} != {want_env!r}')
                checks = {'policy': (agent['mode'], job['policy']), 'seed': (agent['seed'], job['seed']),
                          'kappa': (rt['kappa'], job['kappa']), 'max_age_s': (rt['max_age_s'], job['max_age_s']),
                          'lease_params': (lease_path, want_lease), 'route': (info['route_id'], job['route_id']),
                          'scenario': (info['scenarios'], [job['scenario_type']]), 'town': (info['town'], job['town'])}
                for key, (got, want) in checks.items():
                    if got != want:
                        problems.append(f'{job["id"]}: {key} = {got!r}, expected {want!r}')
            except BaseException as e:  # noqa: BLE001  (SystemExit from preflight included)
                problems.append(f'{job["id"]}: {type(e).__name__}: {e}')
    return problems


def registered_v2_jobs():
    path = ROOT / 'outputs/framelease_v2/gpu_queue/jobs.d/10_tier1.jsonl'
    jobs = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    for extra in ('40_tier4.jsonl', '50_tier5.jsonl'):
        p = ROOT / 'outputs/framelease_v2/gpu_queue/jobs.d' / extra
        jobs += [json.loads(line) for line in p.read_text(encoding='utf-8').splitlines() if line.strip()]
    return jobs


def manifest(matrix, routes, files, pins):
    m = MATRICES[matrix]
    return {'schema': 'framelease_v3.closed_loop_matrix/1', 'matrix': matrix, 'routes_xml': A.ROUTES_XML_REL,
            'routes_xml_sha256': sha256(ROOT / A.ROUTES_XML_REL), 'v2_routes_json': V2_ROUTES_JSON_REL,
            'v2_routes_json_sha256': sha256(ROOT / V2_ROUTES_JSON_REL), 'seed': SEED, 'kappa': KAPPA,
            'order_seed': ORDER_SEED, 'port_base': m['port_base'], 'output_dir': m['out'], 'queue_dir': m['queue'],
            'wall_cap_s': WALL_CAP_S, 'launcher': LAUNCHER_REL,
            'arms': {a.name: {'policy': a.policy, 'title': a.title, 'v2_arm': a.v2_arm, 'runtime_params': a.runtime_params,
                              'lease_params': a.lease_params, 'expected_max_age_s': a.expected_max_age_s,
                              'description': a.description} for a in A.ARMS.values()},
            'files': {f: len(j) for f, j in files.items()},
            'job_order': {f: [j['id'] for j in jobs] for f, jobs in files.items()},
            'code_pins': pins, 'routes': routes}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--check', action='store_true', help='validate every job command (CPU only)')
    p.add_argument('--write', action='store_true', help='write matrix.json and the job files')
    p.add_argument('--root', type=Path, default=ROOT, help='write under this root instead of the project (tests)')
    p.add_argument('--force', action='store_true', help='overwrite job files (never after runs exist)')
    p.add_argument('--only', choices=('pilot', 'main'), help='restrict to one matrix')
    args = p.parse_args(argv)

    tests = test_routes()
    pilots = pilot_routes(tests)
    pins = code_pins()
    built = {'pilot': (pilots, build_pilot(pilots, pins)), 'main': (tests, build_main(tests, pins))}
    optional = build_pilot_variants(pilots, pins)
    if args.only:
        built = {args.only: built[args.only]}
        if args.only != 'pilot':
            optional = {}
    for matrix, (routes, files) in built.items():
        print(f'== {matrix}: {len(routes)} routes -> {MATRICES[matrix]["queue"]}/jobs.d/')
        if matrix == 'pilot':
            for r in routes:
                print(f'   {r["route_id"]:>6} {r["town"]:<8} {r["scenario_type"]:<36} {r["rule"]}')
        for fname, jobs in files.items():
            print(f'   {fname}: {len(jobs)} jobs, arms {sorted({j["arm_name"] for j in jobs})}, '
                  f'wall-cap sum {sum(j["wall_cap_s"] for j in jobs) / 3600:.1f} h; first: '
                  + ', '.join(j['id'] for j in jobs[:4]))
    for fname, jobs in optional.items():
        print(f'   OPTIONAL (not in jobs.d) {OPTIONAL_DIR}/{fname}: {len(jobs)} jobs, '
              f'envelopes {sorted({j["envelope"] for j in jobs})}')
    ids = [j['id'] for _, files in built.values() for jobs in files.values() for j in jobs]
    ids += [j['id'] for jobs in optional.values() for j in jobs]
    if len(ids) != len(set(ids)):
        print('duplicate job ids', file=sys.stderr)
        return 1
    if args.check or args.write:
        problems = []
        v2_jobs = registered_v2_jobs()
        for _, files in built.values():
            problems += check_jobs(files, v2_jobs)
        problems += check_jobs(optional, v2_jobs)
        if problems:
            print('JOB CHECK FAILED:\n  ' + '\n  '.join(problems[:50]), file=sys.stderr)
            return 1
        print(f'job check: all {len(ids)} commands pass the v3 launcher\'s parsing, configuration and preflight; '
              'baseline configurations equal the registered v2 arms')
    if not args.write:
        return 0
    root = args.root.resolve()
    for matrix, (routes, files) in built.items():
        m = MATRICES[matrix]
        out_dir, jobs_dir = root / m['out'], root / m['queue'] / 'jobs.d'
        runs = out_dir / 'runs'
        if runs.is_dir() and any(runs.iterdir()):
            print(f'refusing to write: {runs} already contains runs', file=sys.stderr)
            return 1
        targets = [out_dir / 'matrix.json'] + [jobs_dir / f for f in files]
        existing = [t for t in targets if t.exists()]
        if existing and not args.force:
            print('refusing to overwrite (use --force before any run exists): ' + ', '.join(map(str, existing)),
                  file=sys.stderr)
            return 1
        out_dir.mkdir(parents=True, exist_ok=True)
        jobs_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / 'matrix.json').write_text(json.dumps(manifest(matrix, routes, files, pins), indent=1) + '\n',
                                             encoding='utf-8')
        for fname, jobs in files.items():
            (jobs_dir / fname).write_text(''.join(json.dumps(j, sort_keys=True) + '\n' for j in jobs), encoding='utf-8')
        for t in targets:
            print(f'wrote {t}  sha256 {sha256(t)}')
        if matrix == 'pilot' and optional:
            opt_dir = root / m['queue'] / OPTIONAL_DIR
            opt_dir.mkdir(parents=True, exist_ok=True)
            for fname, jobs in optional.items():
                t = opt_dir / fname
                if t.exists() and not args.force:
                    print(f'refusing to overwrite {t}', file=sys.stderr)
                    return 1
                t.write_text(''.join(json.dumps(j, sort_keys=True) + '\n' for j in jobs), encoding='utf-8')
                print(f'wrote {t}  sha256 {sha256(t)}  (OPTIONAL: move into jobs.d to enable)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
