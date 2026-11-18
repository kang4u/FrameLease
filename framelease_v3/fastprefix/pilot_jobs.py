#!/usr/bin/env python3
"""Day-3 closed-loop pilot job file for the fast prefix (framelease_v2/gpu_queue.py format). Writes nothing unless --write.

  python framelease_v3/fastprefix/pilot_jobs.py            # print the plan
  python framelease_v3/fastprefix/pilot_jobs.py --check    # + validate every job command (CPU only, no CARLA / GPU)
  python framelease_v3/fastprefix/pilot_jobs.py --write    # + write pilot/matrix.json and pilot_queue/jobs.d/*.jsonl

Routes: the 4 pilot routes of the v3 pilot (framelease_v3/runtime/v3_matrix.pilot_routes: 2086, 18305, 2554, 1792; none
is a test route), checked against outputs/framelease_v3/closed_loop/pilot/matrix.json.
Arms (seed 11, kappa 1.0; same wall cap 1500 s, launcher --timeout-s 1410 and --lock-wait-s 600 as the v3 pilot):
  fast_only           baseline: the unchanged v3 launcher (framelease_v3/runtime/run_closed_loop_v3.py --arm fast_only,
                      which delegates to the unchanged framelease_v2 launcher and agent)
  fast_only_fp        framelease_v3/fastprefix/run_closed_loop_fast.py --fast-prefix sdpa,gpu_preproc,lora_merged
                      --arm fast_only (agent configuration identical to fast_only; entry + fast prefix)
  fl_v3_heuristic_fp  framelease_v3/fastprefix/run_closed_loop_fast.py --fast-prefix ... --arm fl_v3_heuristic
                      (agent configuration identical to the v3 pilot's fl_v3_heuristic; entry + fast prefix)
Order: per route the three arms back to back, rotated by one position per route (each arm once in every position over
the first three routes). Ports: job i uses 2900 + 5 i (+1, +2 and +6000 also; 2900-2955 / 8900-8955; the v2 matrix
used 2500-2530, the v3 main 2700-2730, the v3 pilot 2800-2830). Output: one directory per arm under
outputs/framelease_v3/fastprefix/run_20261110/pilot/<arm>/runs/, queue outputs/framelease_v3/fastprefix/run_20261110/
pilot_queue/. Pins (require_sha256): the 26 files of the v3 pilot jobs, the fast-prefix sources, the upstream files the
fast path replaces or replicates, the Qwen3-VL image processor configuration and the team_code copies the evaluator
imports, for every job (a change blocks all three arms alike).
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v3.runtime import v3_arms as A  # noqa: E402
from framelease_v3.runtime import v3_matrix as M  # noqa: E402

PYTHON = M.PYTHON
OUT_REL = 'outputs/framelease_v3/fastprefix/run_20261110'
PILOT_OUT_REL = OUT_REL + '/pilot'
QUEUE_REL = OUT_REL + '/pilot_queue'
JOB_FILE = '10_pilot_fastprefix.jsonl'
FAST_LAUNCHER_REL = 'framelease_v3/fastprefix/run_closed_loop_fast.py'
V3_LAUNCHER_REL = M.LAUNCHER_REL
FAST_PREFIX = 'sdpa,gpu_preproc,lora_merged'
PORT_BASE = 2900
PORT_STEP = 5
SEED, KAPPA = M.SEED, M.KAPPA
WALL_CAP_S, LAUNCHER_MARGIN_S, LOCK_WAIT_S = M.WALL_CAP_S, M.LAUNCHER_MARGIN_S, M.LOCK_WAIT_S
EXISTING_PILOT_MATRIX = 'outputs/framelease_v3/closed_loop/pilot/matrix.json'
VLM_PREPROCESSOR = 'checkpoints/Qwen3-VL-2B-Instruct/89644892e4d85e24eaac8bacfd4f463576704203/preprocessor_config.json'
FP_PINNED = ('framelease_v3/fastprefix/__init__.py', 'framelease_v3/fastprefix/fast_path.py',
             'framelease_v3/fastprefix/agent_entry.py', FAST_LAUNCHER_REL,
             'third_party/transformers-linux/src/transformers/models/qwen3_vl/modeling_qwen3_vl.py',
             'third_party/UniDriveVLA-linux/Bench2Drive/projects/mmdet3d_plugin/models/vla/unidrivevla_vlm_qwenvl3.py',
             'third_party/UniDriveVLA-linux/Bench2Drive/projects/mmdet3d_plugin/models/vla/qwenvl3_vla_planning_head.py',
             VLM_PREPROCESSOR,
             # the copies the evaluator process actually imports as team_code.* (PYTHONPATH order of linux/env.sh);
             # byte-identical to the UniDriveVLA-linux copies the v2 / v3 jobs pin
             'third_party/bench2drive-linux/leaderboard/team_code/unidrivevla_b2d_agent.py',
             'third_party/bench2drive-linux/leaderboard/team_code/pid_controller.py',
             'third_party/bench2drive-linux/leaderboard/team_code/planner.py')
# (job arm name, base arm, fast prefix?)
ARMS = (('fast_only', 'fast_only', False), ('fast_only_fp', 'fast_only', True),
        ('fl_v3_heuristic_fp', 'fl_v3_heuristic', True))
TITLES = {'fast_only': 'Fast Only (baseline, unmodified prefix)', 'fast_only_fp': 'Fast Only + fast prefix',
          'fl_v3_heuristic_fp': 'FrameLease + Heuristic + fast prefix'}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def code_pins():
    rels = tuple(M.V2_PINNED) + tuple(M.V3_PINNED) + FP_PINNED
    return {rel: sha256(ROOT / rel) for rel in rels}


def routes():
    """The v3 pilot routes, recomputed with v3_matrix's rule and checked against the registered pilot matrix."""
    tests = M.test_routes()
    pilots = M.pilot_routes(tests)
    reg = json.loads((ROOT / EXISTING_PILOT_MATRIX).read_text(encoding='utf-8'))
    if [r['route_id'] for r in pilots] != [r['route_id'] for r in reg['routes']]:
        raise ValueError('pilot routes differ from the registered v3 pilot matrix')
    return pilots


def job_for(i, name, base_arm, fast, route, pins):
    arm = A.ARMS[base_arm]
    port = PORT_BASE + PORT_STEP * i
    out = f'{PILOT_OUT_REL}/{name}'
    common = ['--arm', base_arm, '--kappa', f'{KAPPA:.1f}', '--seed', str(SEED), '--routes', A.ROUTES_XML_REL,
              '--route-id', route['route_id'], '--port', str(port), '--output-dir', out,
              '--timeout-s', str(WALL_CAP_S - LAUNCHER_MARGIN_S), '--lock-wait-s', str(LOCK_WAIT_S)]
    if fast:
        cmd = [PYTHON, FAST_LAUNCHER_REL, '--fast-prefix', FAST_PREFIX] + common
    else:
        cmd = [PYTHON, V3_LAUNCHER_REL] + common
    return {'id': f'fpp_{A.arm_id(name, KAPPA, SEED)}_r{route["route_id"]}', 'kind': 'closed_loop', 'tier': 0,
            'cmd': cmd, 'wall_cap_s': WALL_CAP_S, 'matrix': 'fastprefix_pilot', 'arm': A.arm_id(name, KAPPA, SEED),
            'arm_name': name, 'base_arm': base_arm, 'title': TITLES[name], 'v2_arm': arm.v2_arm, 'policy': arm.policy,
            'kappa': KAPPA, 'seed': SEED, 'max_age_s': arm.expected_max_age_s, 'lease_params': arm.lease_params,
            'envelope': None, 'fast_prefix': FAST_PREFIX.split(',') if fast else None, 'exploratory': True,
            'route_id': route['route_id'], 'route_index': None, 'pilot_index': route['pilot_index'],
            'scenario_type': route['scenario_type'], 'town': route['town'], 'port': port, 'output_dir': out,
            'require_sha256': pins}


def build(rts, pins):
    jobs = []
    for r in rts:
        k = r['pilot_index'] % len(ARMS)
        for name, base_arm, fast in ARMS[k:] + ARMS[:k]:
            jobs.append(job_for(len(jobs), name, base_arm, fast, r, pins))
    return {JOB_FILE: jobs}


def manifest(rts, files, pins):
    return {'schema': 'framelease_v3.fastprefix_pilot/1', 'matrix': 'fastprefix_pilot', 'seed': SEED, 'kappa': KAPPA,
            'routes_xml': A.ROUTES_XML_REL, 'routes_xml_sha256': sha256(ROOT / A.ROUTES_XML_REL),
            'v3_pilot_matrix': EXISTING_PILOT_MATRIX, 'port_base': PORT_BASE, 'port_step': PORT_STEP,
            'output_dir': PILOT_OUT_REL, 'queue_dir': QUEUE_REL, 'wall_cap_s': WALL_CAP_S,
            'launchers': {'fast_only': V3_LAUNCHER_REL, 'fast_only_fp': FAST_LAUNCHER_REL,
                          'fl_v3_heuristic_fp': FAST_LAUNCHER_REL},
            'fast_prefix': FAST_PREFIX.split(','),
            'arms': {n: {'base_arm': b, 'fast_prefix': f, 'title': TITLES[n], 'policy': A.ARMS[b].policy,
                         'runtime_params': A.ARMS[b].runtime_params, 'lease_params': A.ARMS[b].lease_params,
                         'expected_max_age_s': A.ARMS[b].expected_max_age_s, 'output_dir': f'{PILOT_OUT_REL}/{n}'}
                     for n, b, f in ARMS},
            'files': {f: len(j) for f, j in files.items()},
            'job_order': {f: [j['id'] for j in jobs] for f, jobs in files.items()},
            'code_pins': pins, 'routes': rts,
            'launch': ('cd /home/kang/Desktop/DAC && source linux/env.sh && export PYTHONDONTWRITEBYTECODE=1 && nohup '
                       '.conda-unidrive-linux/bin/python framelease_v2/gpu_queue.py --queue-dir ' + QUEUE_REL +
                       ' --exit-when-empty --min-free-gib 8.5 > ' + QUEUE_REL + '/runner.nohup.log 2>&1 &')}


# ============================================================================================ checks (CPU only)

def check_jobs(files, pins):
    from framelease_v2 import gpu_queue as Q
    from framelease_v2 import run_closed_loop as R2
    from framelease_v3.fastprefix import run_closed_loop_fast as F
    from framelease_v3.runtime import run_closed_loop_v3 as L
    problems, configs = [], {}
    ports, outs = set(), {}
    for fname, jobs in files.items():
        for job in jobs:
            jid = job['id']
            try:
                bad = Q.validate_job(job)
                if bad:
                    problems.append(f'{jid}: gpu_queue rejects the job: {bad}')
                if Q.pin_mismatches(job['require_sha256']):
                    problems.append(f'{jid}: pinned files differ from the current tree')
                port = int(job['cmd'][job['cmd'].index('--port') + 1])
                for p in (port, port + 1, port + 2, port + 6000):
                    if p in ports:
                        problems.append(f'{jid}: port {p} used twice')
                    ports.add(p)
                outs.setdefault(job['arm_name'], set()).add(job['cmd'][job['cmd'].index('--output-dir') + 1])
                with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                    if job['cmd'][1] == V3_LAUNCHER_REL:
                        args = L.parse_args(job['cmd'][2:])
                        a2 = R2.parse_args(L.v2_argv(args))
                        agent = R2.agent_config(a2)
                        info = R2.preflight(a2)
                    else:
                        own, base = F.parse_args(job['cmd'][2:])
                        prep = F.prepare(own, base)
                        info = prep['route']
                        agent = prep['agent_runtime_config']
                        if prep['fp']['options'] != job['fast_prefix'] or prep['fp']['arm'] != job['arm_name']:
                            problems.append(f'{jid}: fast-prefix configuration {prep["fp"]["options"]} / '
                                            f'{prep["fp"]["arm"]} does not match the job')
                configs[(job['arm_name'], job['route_id'])] = agent
                if (info['route_id'], info['town'], info['scenarios']) != (job['route_id'], job['town'],
                                                                           [job['scenario_type']]):
                    problems.append(f'{jid}: route {info} does not match the job')
            except BaseException as e:  # noqa: BLE001 (SystemExit from preflight included)
                problems.append(f'{jid}: {type(e).__name__}: {e}')
    # the fast arms must run exactly the base arm's agent configuration
    reg = {}
    for line in (ROOT / 'outputs/framelease_v3/closed_loop/pilot_queue/jobs.d/10_pilot.jsonl').read_text().splitlines():
        if line.strip():
            j = json.loads(line)
            reg[(j['arm_name'], j['route_id'])] = j
    for (name, rid), agent in configs.items():
        if name == 'fast_only_fp':
            if agent != configs.get(('fast_only', rid)):
                problems.append(f'fast_only_fp r{rid}: agent configuration differs from the fast_only baseline job')
        if name == 'fl_v3_heuristic_fp':
            ref = reg.get(('fl_v3_heuristic', rid))
            if ref is None:
                problems.append(f'fl_v3_heuristic_fp r{rid}: no registered v3 pilot job to compare with')
                continue
            with contextlib.redirect_stderr(io.StringIO()):
                ref_cfg, _, _ = L.v3_configs(L.parse_args(ref['cmd'][2:]))
            if ref_cfg != agent:
                problems.append(f'fl_v3_heuristic_fp r{rid}: v3 agent configuration differs from the registered '
                                'v3 pilot job')
        if name == 'fast_only':
            ref = reg.get(('fast_only', rid))
            if ref is not None:
                a_ref = R2.agent_config(R2.parse_args(L.v2_argv(L.parse_args(ref['cmd'][2:]))))
                if a_ref != agent:
                    problems.append(f'fast_only r{rid}: agent configuration differs from the registered v3 pilot job')
    for name, dirs in outs.items():
        if len(dirs) != 1:
            problems.append(f'{name}: more than one output directory {sorted(dirs)}')
    all_dirs = [d for ds in outs.values() for d in ds]
    if len(set(all_dirs)) != len(all_dirs):
        problems.append('two arms share an output directory')
    for d in all_dirs:
        if not d.startswith(PILOT_OUT_REL + '/'):
            problems.append(f'output directory outside {PILOT_OUT_REL}: {d}')
    return problems


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--check', action='store_true')
    p.add_argument('--write', action='store_true')
    p.add_argument('--force', action='store_true', help='overwrite the job file (never after a run exists)')
    args = p.parse_args(argv)
    rts = routes()
    pins = code_pins()
    files = build(rts, pins)
    for fname, jobs in files.items():
        print(f'{QUEUE_REL}/jobs.d/{fname}: {len(jobs)} jobs, {len(pins)} pinned files, wall-cap sum '
              f'{sum(j["wall_cap_s"] for j in jobs) / 3600:.1f} h')
        for j in jobs:
            print(f'  {j["id"]:<48} port {j["port"]}  {j["cmd"][1]}  -> {j["output_dir"]}')
    if args.check or args.write:
        problems = check_jobs(files, pins)
        if problems:
            print('JOB CHECK FAILED:\n  ' + '\n  '.join(problems[:60]), file=sys.stderr)
            return 1
        print('job check: every command passes its launcher\'s parsing, configuration and preflight; gpu_queue accepts '
              'every job; pins match; ports and output directories are distinct; fast_only_fp = fast_only and '
              'fl_v3_heuristic_fp = the registered v3 pilot fl_v3_heuristic agent configuration')
    if not args.write:
        return 0
    out_dir, jobs_dir = ROOT / PILOT_OUT_REL, ROOT / QUEUE_REL / 'jobs.d'
    for name, _, _ in ARMS:
        runs = out_dir / name / 'runs'
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
    (out_dir / 'matrix.json').write_text(json.dumps(manifest(rts, files, pins), indent=1) + '\n', encoding='utf-8')
    for fname, jobs in files.items():
        (jobs_dir / fname).write_text(''.join(json.dumps(j, sort_keys=True) + '\n' for j in jobs), encoding='utf-8')
    for t in targets:
        print(f'wrote {t}  sha256 {sha256(t)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
