#!/usr/bin/env python3
"""Dry-run job lines of the v4 Table I matrix: 2 routes x 7 arms (framelease_v2/gpu_queue.py format). WRITTEN, NEVER
LAUNCHED: the files go to outputs/framelease_v4/arms_dev/dryrun/ (not a queue jobs.d/ directory), so no runner picks
them up; this script never starts a job, CARLA or the GPU.

  python framelease_v4/arms/jobs_v4.py                 # print the plan
  python framelease_v4/arms/jobs_v4.py --check         # + validate every line (CPU only; needs `source linux/env.sh`)
  python framelease_v4/arms/jobs_v4.py --check --write # + write the job files, matrix.json and check.json
      [--fl-full-utility NAME --fl-full-env FRAMELEASE_V4_QNET=<weights.json>]

Routes: the first two v3 pilot routes (framelease_v3/runtime/v3_matrix.pilot_routes; never test routes): 2086
(NonSignalizedJunctionLeftTurn, the development route) and 18305 (ParkingCutIn). Arms (Table I order, seed 11,
kappa 1.0, fast prefix sdpa,gpu_preproc,lora_merged, actor log on, policy defaults = the documented priors of
arms_v4.py; hyperparameters still to be tuned on training routes): fixed_deep, fast_only, age_only, event_triggered,
fl_original, fl_heuristic, fl_full. Per route the seven arms run back to back, rotated by one position per route.
Ports: line i uses 3300 + 5 i (+1, +2, +6000; 3300-3365 / 9300-9365; the v2 matrix used 2500-2530, v3 2700-2830, the
fast-prefix pilot 2900-2955). Wall cap 1500 s, launcher --timeout-s 1410, --lock-wait-s 600 (as the v3 pilots).
fl_full needs a learned utility (framelease_v4/rl): without --fl-full-utility its two lines are written to
pending_fl_full.jsonl with "blocked" set and a placeholder utility, and the check confirms they are rejected.
Pins (require_sha256): the v2 / v3 / fast-prefix files the fast-prefix pilot pinned plus the v4 arms sources and the
v4 utility modules framelease_v4/rl/{__init__,behaviour,features,qnet}.py (and the Q-network weights for fl_full).
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v3.fastprefix import pilot_jobs as PJ  # noqa: E402
from framelease_v3.runtime import v3_matrix as M  # noqa: E402
from framelease_v4.arms import arms_v4 as AV  # noqa: E402

OUT_REL = 'outputs/framelease_v4/arms_dev/dryrun'
LAUNCHER_REL = 'framelease_v4/arms/run_closed_loop_v4.py'
JOB_FILE = 'jobs_2routes_x7arms.jsonl'
PENDING_FILE = 'pending_fl_full.jsonl'
PLACEHOLDER_UTILITY = '<PENDING_LEARNED_UTILITY>'
FAST_PREFIX = 'sdpa,gpu_preproc,lora_merged'
PORT_BASE, PORT_STEP = 3300, 5
SEED, KAPPA = 11, 1.0
WALL_CAP_S, LAUNCHER_MARGIN_S, LOCK_WAIT_S = M.WALL_CAP_S, M.LAUNCHER_MARGIN_S, M.LOCK_WAIT_S
N_ROUTES = 2
V4_UTILITY_PINNED = ('framelease_v4/rl/__init__.py', 'framelease_v4/rl/behaviour.py', 'framelease_v4/rl/features.py',
                     'framelease_v4/rl/qnet.py')            # = run_closed_loop_v4.V4_UTILITY_CODE (tested)
V4_PINNED = ('framelease_v4/__init__.py', 'framelease_v4/arms/__init__.py', 'framelease_v4/arms/policies_v4.py',
             'framelease_v4/arms/runtime_v4.py', 'framelease_v4/arms/arms_v4.py', 'framelease_v4/arms/actor_log.py',
             'framelease_v4/arms/agent_v4.py', LAUNCHER_REL) + V4_UTILITY_PINNED


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def code_pins(extra=()):
    rels = list(M.V2_PINNED) + list(M.V3_PINNED) + list(PJ.FP_PINNED) + list(V4_PINNED) + list(extra)
    out = {}
    for rel in rels:
        out[rel] = sha256(ROOT / rel)
    return out


def routes():
    tests = M.test_routes()
    pilots = M.pilot_routes(tests)[:N_ROUTES]
    test_ids = {r['route_id'] for r in tests}
    if any(r['route_id'] in test_ids for r in pilots):
        raise ValueError('a dry-run route is a test route')
    return pilots


def utility_pins(utility, env):
    """Repository-relative environment files of a learned utility (the Q-network weights); the default registrar's
    modules (framelease_v4/rl/{__init__,behaviour,features,qnet}.py) are pinned for every job (V4_PINNED)."""
    if not utility:
        return []
    rels = []
    for v in (env or {}).values():
        p = Path(v)
        p = p if p.is_absolute() else ROOT / p
        if p.is_file() and p.resolve().is_relative_to(ROOT):
            rels.append(str(p.resolve().relative_to(ROOT)))
    return rels


def job_for(i, arm_name, route, pins, utility=None, utility_env=None):
    arm = AV.ARMS[arm_name]
    port = PORT_BASE + PORT_STEP * i
    out = f'{OUT_REL}/{arm_name}_fp'
    cmd = [M.PYTHON, LAUNCHER_REL, '--arm', arm_name, '--fast-prefix', FAST_PREFIX, '--kappa', f'{KAPPA:.1f}',
           '--seed', str(SEED), '--routes', AV.ROUTES_XML_REL, '--route-id', route['route_id'], '--port', str(port),
           '--output-dir', out, '--timeout-s', str(WALL_CAP_S - LAUNCHER_MARGIN_S), '--lock-wait-s', str(LOCK_WAIT_S)]
    blocked = None
    if arm.requires_utility:
        cmd += ['--policy-params', json.dumps({'utility': utility or PLACEHOLDER_UTILITY}, sort_keys=True)]
        for k, v in sorted((utility_env or {}).items()):
            cmd += ['--utility-env', f'{k}={v}']
        if not utility:
            blocked = 'learned utility not available yet (framelease_v4/rl): pass --fl-full-utility'
    job = {'id': f'v4dev_{AV.arm_id(arm_name + "_fp", KAPPA, SEED)}_r{route["route_id"]}', 'kind': 'closed_loop',
           'tier': 0, 'cmd': cmd, 'wall_cap_s': WALL_CAP_S, 'matrix': 'framelease_v4_arms_dryrun',
           'arm': AV.arm_id(arm_name + '_fp', KAPPA, SEED), 'arm_name': arm_name, 'title': arm.title,
           'kind_v4': arm.kind, 'policy': arm.policy, 'kappa': KAPPA, 'seed': SEED,
           'fast_prefix': FAST_PREFIX.split(','), 'exploratory': True, 'not_for_launch': True,
           'route_id': route['route_id'], 'pilot_index': route['pilot_index'],
           'scenario_type': route['scenario_type'], 'town': route['town'], 'port': port, 'output_dir': out,
           'require_sha256': pins}
    if blocked:
        job['blocked'] = blocked
    return job


def build(rts, utility=None, utility_env=None):
    pins = code_pins(utility_pins(utility, utility_env))
    ready, pending = [], []
    order = list(AV.TABLE_I_ORDER)
    i = 0
    for r in rts:
        k = r['pilot_index'] % len(order)
        for arm_name in order[k:] + order[:k]:
            job = job_for(i, arm_name, r, pins, utility, utility_env)
            (pending if job.get('blocked') else ready).append(job)
            i += 1
    return ready, pending, pins


# ============================================================================================ checks (CPU only)

def check_job(job, subprocess_dry_run=True):
    """{'id', 'ok', 'problems', ...}: gpu_queue contract, pins, launcher parse + prepare, the exact command --dry-run."""
    from framelease_v2 import gpu_queue as Q
    from framelease_v4.arms import run_closed_loop_v4 as RL
    out = {'id': job['id'], 'problems': []}
    bad = Q.validate_job(job)
    if bad:
        out['problems'].append(f'gpu_queue rejects the job: {bad}')
    if Q.pin_mismatches(job['require_sha256']):
        out['problems'].append('pinned files differ from the current tree')
    saved = dict(os.environ)
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            args = RL.parse_args(job['cmd'][2:])
            prep = RL.prepare(args)
        info = prep['route']
        if (info['route_id'], info['town'], info['scenarios']) != (job['route_id'], job['town'], [job['scenario_type']]):
            out['problems'].append(f'route {info} does not match the job')
        if prep['cfg']['arm'] != job['arm_name'] or prep['fp']['options'] != job['fast_prefix']:
            out['problems'].append('arm / fast prefix of the prepared configuration differ from the job')
        out['agent_runtime_config_sha256'] = hashlib.sha256(
            json.dumps(prep['cfg'], sort_keys=True).encode()).hexdigest()
        out['policy'] = prep['cfg']['agent']['mode']
        out['policy_params'] = prep['cfg']['agent']['policy_params']
        out['runtime'] = {k: prep['cfg']['agent']['runtime'][k] for k in ('kappa', 'max_age_s', 'profile_quantile')}
        if job.get('blocked'):
            out['problems'].append('a blocked job passed preparation')
    except SystemExit as e:
        if job.get('blocked'):
            out['blocked_as_expected'] = str(e)[:300]
        else:
            out['problems'].append(f'SystemExit: {e}')
    except BaseException as e:  # noqa: BLE001
        out['problems'].append(f'{type(e).__name__}: {e}')
    finally:
        os.environ.clear()
        os.environ.update(saved)
    if subprocess_dry_run and not job.get('blocked') and not out['problems']:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', CUDA_VISIBLE_DEVICES='')
        p = subprocess.run(job['cmd'] + ['--dry-run'], cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            out['problems'].append(f'dry run exit {p.returncode}: {p.stderr[-400:]}')
        else:
            d = json.loads(p.stdout)
            ok = (d.get('status') == 'NOT_STARTED' and d.get('v4_arm') == job['arm_name']
                  and d['command'][d['command'].index('--agent') + 1].endswith('framelease_v4_arms_agent_entry.py')
                  and 'FRAMELEASE_V4_ARMS_CONFIG' in d['environment_overrides']
                  and 'FRAMELEASE_V2_RUNTIME_CONFIG' not in d['environment_overrides'])
            if not ok:
                out['problems'].append('dry-run output does not match the job')
            out['dry_run'] = {'status': d.get('status'), 'arm': d.get('arm'), 'ports': d.get('ports'),
                              'entry': d['command'][d['command'].index('--agent') + 1].split('/')[-1]}
    out['ok'] = not out['problems']
    return out


def check_all(ready, pending, subprocess_dry_run=True):
    results = [check_job(j, subprocess_dry_run) for j in ready + pending]
    problems = [f'{r["id"]}: {p}' for r in results for p in r['problems']]
    ports, outs = set(), {}
    for j in ready + pending:
        for p in (j['port'], j['port'] + 1, j['port'] + 2, j['port'] + 6000):
            if p in ports:
                problems.append(f'{j["id"]}: port {p} used twice')
            ports.add(p)
        outs.setdefault(j['arm_name'], set()).add(j['output_dir'])
    for name, dirs in outs.items():
        if len(dirs) != 1:
            problems.append(f'{name}: more than one output directory')
    if len({d for ds in outs.values() for d in ds}) != len(outs):
        problems.append('two arms share an output directory')
    ids = [j['id'] for j in ready + pending]
    if len(set(ids)) != len(ids):
        problems.append('duplicate job ids')
    return results, problems


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--check', action='store_true')
    p.add_argument('--write', action='store_true')
    p.add_argument('--no-subprocess', action='store_true', help='skip running each command with --dry-run')
    p.add_argument('--fl-full-utility', default=None)
    p.add_argument('--fl-full-env', action='append', default=[], help='KEY=VALUE for the learned utility')
    p.add_argument('--force', action='store_true', help='overwrite existing files (no run may exist)')
    args = p.parse_args(argv)
    env = dict(x.split('=', 1) for x in args.fl_full_env)
    rts = routes()
    ready, pending, pins = build(rts, args.fl_full_utility, env)
    print(f'{len(ready)} ready + {len(pending)} pending job lines, {len(pins)} pinned files, '
          f'wall-cap sum {sum(j["wall_cap_s"] for j in ready) / 3600:.1f} h (NOT launched)')
    for j in ready + pending:
        print(f'  {j["id"]:<46} port {j["port"]}  {"BLOCKED " if j.get("blocked") else ""}-> {j["output_dir"]}')
    results = problems = None
    if args.check or args.write:
        results, problems = check_all(ready, pending, not args.no_subprocess)
        if problems:
            print('JOB CHECK FAILED:\n  ' + '\n  '.join(problems[:60]), file=sys.stderr)
            if args.write:
                return 1
        else:
            print('job check: gpu_queue accepts every line, pins match, every ready command parses, prepares and '
                  'dry-runs through the v4 launcher, blocked lines are rejected, ports and output dirs distinct')
    if not args.write:
        return 0 if not problems else 1
    out_dir = ROOT / OUT_REL
    for j in ready + pending:
        runs = ROOT / j['output_dir'] / 'runs'
        if runs.is_dir() and any(runs.iterdir()):
            print(f'refusing to write: {runs} contains runs', file=sys.stderr)
            return 1
    targets = [out_dir / JOB_FILE, out_dir / PENDING_FILE, out_dir / 'matrix.json', out_dir / 'check.json']
    if any(t.exists() for t in targets) and not args.force:
        print('refusing to overwrite (use --force): ' + ', '.join(str(t) for t in targets if t.exists()),
              file=sys.stderr)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / JOB_FILE).write_text(''.join(json.dumps(j, sort_keys=True) + '\n' for j in ready), encoding='utf-8')
    (out_dir / PENDING_FILE).write_text(''.join(json.dumps(j, sort_keys=True) + '\n' for j in pending),
                                        encoding='utf-8')
    matrix = {'schema': 'framelease_v4.arms.dryrun_matrix/1', 'not_for_launch': True, 'seed': SEED, 'kappa': KAPPA,
              'fast_prefix': FAST_PREFIX.split(','), 'routes': rts, 'arms': {
                  n: {'title': AV.ARMS[n].title, 'kind': AV.ARMS[n].kind, 'policy': AV.ARMS[n].policy,
                      'default_params': AV.ARMS[n].params, 'runtime': AV.ARMS[n].runtime,
                      'lease_params': AV.ARMS[n].lease_params, 'tunable_on_training_routes': AV.ARMS[n].tunable,
                      'description': AV.ARMS[n].description} for n in AV.TABLE_I_ORDER},
              'files': {JOB_FILE: len(ready), PENDING_FILE: len(pending)},
              'job_order': [j['id'] for j in ready + pending], 'port_base': PORT_BASE, 'port_step': PORT_STEP,
              'wall_cap_s': WALL_CAP_S, 'code_pins': pins,
              'how_to_launch_later': 'copy the ready lines into <queue>/jobs.d/ of a NEW queue directory after the '
                                     'hyperparameters are tuned on training routes; never launch from this directory'}
    (out_dir / 'matrix.json').write_text(json.dumps(matrix, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    (out_dir / 'check.json').write_text(json.dumps({'problems': problems, 'jobs': results}, indent=1, sort_keys=True)
                                        + '\n', encoding='utf-8')
    for t in targets:
        print(f'wrote {t}  sha256 {sha256(t)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
