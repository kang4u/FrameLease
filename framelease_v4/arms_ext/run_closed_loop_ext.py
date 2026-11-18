#!/usr/bin/env python3
"""Run one Bench2Drive route under an arm of the v4 matrix or of the extension (framelease_v4/arms_ext), fast prefix on.

  cd /home/kang/Desktop/DAC && source linux/env.sh
  .conda-unidrive-linux/bin/python -B framelease_v4/arms_ext/run_closed_loop_ext.py --arm fl_global_shield \
      --route-id R --envelope outputs/framelease_v4/envelopes/<E*>.json --policy-params '{"utility": "<a_det^d*>"}' \
      [every option of framelease_v4/arms/run_closed_loop_v4.py] [--dry-run]

PROTOCOL Secs. 4.1 / 7.4 (fl_global_shield, Table II-A lease panel), 8.2-8.3 (job lines and code pins), 2.1-2.5 (the
common settings, unchanged).

ARM: every arms_v4 arm (fixed_deep, fast_only, age_only, event_triggered, fl_original, fl_heuristic, fl_full,
fl_behaviour) and the extension arm fl_global_shield (arms_ext.py). An arms_v4 arm is handed to the pinned launcher
untouched: main() calls framelease_v4/arms/run_closed_loop_v4.main(argv) with the same arguments, so its parsing,
configuration, agent entry, frozen sources and run directory are the pinned launcher's own (byte-identical --dry-run;
tested for all 8 arms). This launcher adds nothing to those runs.

fl_global_shield (no attribute of a pinned module is rebound; run_closed_loop_v4's own helpers are called):
* parsing: run_closed_loop_v4.parse_args on the arguments with the arm name replaced by its base arm (fl_heuristic),
  then the arm name restored: the same options, defaults and checks;
* configuration: arms_ext.build_config (the base arm's arms_v4 configuration, relabelled, with the 'extension' block;
  --envelope is required); run_closed_loop_v4.fast_prefix_config / namespace / evaluator_env / run_config /
  freeze_v4_sources / actor_log_outcome and the v2 / v3 / fast-prefix helpers they use, unchanged;
* run(): a copy of run_closed_loop_v4.run (the documented alternative of GAP_AUDIT Sec. 2, item 4, to rebinding module
  attributes) with four substitutions: the evaluator loads raw/framelease_v4_arms_ext_agent_entry.py
  (agent_ext.FrameLeaseV4ExtAgent = the pinned FrameLeaseV4Agent with the extension registry in setup()); the
  extension sources (arms_ext.EXT_CODE) are frozen under raw/source_v4/framelease_v4/arms_ext/ and listed in
  raw/source_v4/hashes.json next to the pinned v4 sources; they and the pinned launcher are code dependencies of the
  StageRun ledger (stage framelease_v4/arms_ext/run_closed_loop_ext); config.json names the extension entry and has an
  'extension' block. Everything else (StageRun, the stage05 crash-cleanup patch, the shared GPU lock, the port check,
  the wall-clock budget, owned-process cleanup, result.json, the fast-prefix and actor-log checks, the report) is the
  pinned code path.
Outputs: as run_closed_loop_v4 (<output-dir>/runs/<utc>_<id>/...). --dry-run validates everything and starts nothing.

Job lines (framelease_v2/gpu_queue.py format): job_line() builds one line of the new arm; its require_sha256 pins the
49 files of every P1 line (framelease_v4/arms/jobs_v4.code_pins), E* and the extension sources EXT_CODE (PROTOCOL Sec.
8.3); check_job_line() validates it (gpu_queue contract, pins, in-process preparation, the fixed lease constants of
PROTOCOL Secs. 2.4 / 7.4: no lease overrides and the cap H_bar 2.5 s, the exact command with --dry-run in a
subprocess). This module never enqueues or launches a job.

Drift guard: tests/test_drift_guard.py requires prepare() and run() to equal run_closed_loop_v4.prepare / run up to the
substitutions it lists (the pinned helpers called through RV4, arms_ext's registry and build_config, the extension
entry, the extension sources, the extension block).
"""
from __future__ import annotations

import argparse
import contextlib
import difflib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_common import StageRun, atomic_json, canonical, file_hash  # noqa: E402
from framelease_v2 import run_closed_loop as R2  # noqa: E402
from framelease_v3.fastprefix import run_closed_loop_fast as F  # noqa: E402
from framelease_v3.runtime import run_closed_loop_v3 as L  # noqa: E402
from framelease_v4.arms import arms_v4 as AV  # noqa: E402
from framelease_v4.arms import run_closed_loop_v4 as RV4  # noqa: E402
from framelease_v4.arms_ext import agent_ext as AGX  # noqa: E402
from framelease_v4.arms_ext import arms_ext as X  # noqa: E402

STAGE = 'framelease_v4/arms_ext/run_closed_loop_ext'
PINNED_LAUNCHER_REL = 'framelease_v4/arms/run_closed_loop_v4.py'
PYTHON = str(ROOT / '.conda-unidrive-linux/bin/python')
FAST_PREFIX = 'sdpa,gpu_preproc,lora_merged'


# ============================================================================================ arguments

def requested_arm(argv):
    """The --arm value the pinned parser would take (the last one), or None."""
    p = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    p.add_argument('--arm', default=None)
    try:
        known, _ = p.parse_known_args(list(argv))
    except SystemExit:
        return None
    return known.arm


def _swap_arm(argv, mapping):
    out, it = [], iter(range(len(argv)))
    argv = list(argv)
    for i in it:
        tok = argv[i]
        if tok == '--arm' and i + 1 < len(argv):
            out += [tok, mapping.get(argv[i + 1], argv[i + 1])]
            next(it, None)
        elif tok.startswith('--arm='):
            v = tok[len('--arm='):]
            out.append('--arm=' + mapping.get(v, v))
        else:
            out.append(tok)
    return out


def parse_args(argv=None):
    """run_closed_loop_v4.parse_args with an extension arm parsed as its base arm, then restored."""
    argv = list(sys.argv[1:] if argv is None else argv)
    arm = requested_arm(argv)
    if not X.is_extension(arm):
        return RV4.parse_args(argv)
    args = RV4.parse_args(_swap_arm(argv, X.BASE_ARMS))
    args.arm = arm
    return args


def base_args(args):
    """A copy of the arguments with the arm replaced by its arms_v4 base arm (for the pinned helpers' ARMS lookups)."""
    return SimpleNamespace(**{**vars(args), 'arm': X.base_arm(args.arm)})


# ============================================================================================ preparation

def prepare(args):
    """run_closed_loop_v4.prepare for an extension arm (CPU only); SystemExit on an invalid configuration."""
    args.output_dir = Path(args.output_dir).resolve()
    actor = dict(args.actor_log or {})
    if args.no_actor_log:
        actor['enabled'] = False
    try:
        fp = RV4.fast_prefix_config(args)
        cfg, lease_params, envelope = X.build_config(
            args.arm, kappa=args.kappa, seed=args.seed, policy_params=args.policy_params,
            runtime_params=args.runtime_params, lease_params=args.lease_params, envelope=args.envelope,
            lease_overrides=args.lease_overrides, utility_registrar=args.utility_registrar,
            utility_env=dict(args.utility_env) or None, fast_prefix=fp, actor_log=actor, routes=args.routes,
            route_id=args.route_id, port=args.port, output_dir=args.output_dir)
        ns = RV4.namespace(base_args(args), lease_params)
        if envelope and not Path(envelope).is_file():
            raise SystemExit(f'preflight failed:\n  envelope not found: {envelope}')
        info = R2.preflight(ns)
    except ValueError as e:
        raise SystemExit(f'invalid configuration: {e}')
    missing = [rel for rel in RV4.V4_CODE + X.EXT_CODE if not (ROOT / rel).is_file()]
    if missing:
        raise SystemExit('preflight failed:\n  v4 sources missing: ' + ', '.join(missing))
    return {'arm': X.ARMS[args.arm], 'cfg': json.loads(json.dumps(cfg)), 'ns': ns, 'route': info,
            'lease_params': lease_params, 'envelope': envelope, 'fp': fp}


def extension_sources():
    """{relative path: sha256} of the extension sources (arms_ext.EXT_CODE)."""
    return {rel: file_hash(ROOT / rel) for rel in X.EXT_CODE}


def extension_info(prep):
    return {'schema': X.SCHEMA, 'arm': prep['arm'].name, 'base_arm': X.base_arm(prep['arm'].name),
            'entry': AGX.ENTRY_NAME, 'launcher': STAGE + '.py', 'sources_sha256': extension_sources(),
            'global_lease': prep['cfg'][X.EXTENSION_KEY]['global_lease']}


def evaluator_command(prep, run_dir, checkpoint):
    cmd = RV4.evaluator_command(prep, run_dir, checkpoint)
    i = cmd.index('--agent')
    cmd[i + 1] = str(run_dir / 'raw' / AGX.ENTRY_NAME)
    return cmd


def code_dependencies(prep):
    """run_closed_loop_v4.code_dependencies + the pinned launcher (its helpers run here) + the extension sources
    (this launcher is the StageRun stage file itself)."""
    deps = list(RV4.code_dependencies(prep))
    deps += [ROOT / PINNED_LAUNCHER_REL]
    deps += [ROOT / rel for rel in X.EXT_CODE if rel != STAGE + '.py']
    seen, out = set(), []
    for d in deps:
        if str(d) not in seen:
            seen.add(str(d))
            out.append(d)
    return out


def freeze_ext_sources(raw):
    """Byte copies of the extension sources under raw/source_v4/<relative path>; {rel: sha256 of the copy}."""
    out = {}
    for rel in X.EXT_CODE:
        src = ROOT / rel
        dst = raw / 'source_v4' / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        out[rel] = file_hash(dst)
    return out


def run_config(prep, args, checkpoint, hash_cache):
    config = RV4.run_config(prep, args, checkpoint, hash_cache)
    config['entry'] = AGX.ENTRY_NAME
    config['extension'] = extension_info(prep)
    return config


# ============================================================================================ run (extension arms)

def run(args):
    """run_closed_loop_v4.run for an extension arm (the copy documented in the module docstring)."""
    prep = prepare(args)
    fp, cfg = prep['fp'], prep['cfg']
    if args.dry_run:
        placeholder = args.output_dir / 'runs' / '<UTC>_<ID>'
        env, overrides = RV4.evaluator_env(prep, placeholder)
        print(json.dumps({'status': 'NOT_STARTED', 'dry_run': True, 'arm': fp['arm'], 'v4_arm': args.arm,
                          'title': prep['arm'].title, 'kind': prep['arm'].kind, 'policy': prep['arm'].policy,
                          'route': prep['route'], 'agent_runtime_config': cfg, 'cwd': str(R2.B2D),
                          'command': evaluator_command(prep, placeholder, prep['ns'].checkpoint),
                          'environment_overrides': overrides,
                          'ports': [args.port, args.port + 1, args.port + 2, args.port + 6000],
                          'extension': extension_info(prep)}, indent=1, default=str))
        return 0
    from stage05_carla_closed_loop import native_evaluator_owned_cleanup
    checkpoint = Path(prep['ns'].checkpoint).resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    hash_cache = args.output_dir / '.file_hash_cache.json'
    config = run_config(prep, args, checkpoint, hash_cache)
    evidence = ['CARLA_CLOSED_LOOP', 'REAL_VLA', 'REAL_GPU', 'VIRTUAL_TIME_MEASURED_LATENCY', 'FAST_PREFIX',
                'FRAMELEASE_V4_ARMS']
    sns = SimpleNamespace(output_dir=args.output_dir, seed=args.seed, mode='closed-loop', resume=False)
    srun = StageRun(STAGE, sns, config, evidence, code_dependencies(prep))
    run_dir = srun.path.resolve()
    raw = run_dir / 'raw'
    (raw / 'agent').mkdir(parents=True, exist_ok=True)
    atomic_json(raw / 'source_v3' / 'hashes.json', L.freeze_v3_sources(raw, prep['lease_params'], prep['envelope']))
    atomic_json(raw / 'source_fastprefix' / 'hashes.json', F.freeze_fastprefix_sources(raw))
    v4_hashes = RV4.freeze_v4_sources(raw, prep)
    v4_hashes.update(freeze_ext_sources(raw))
    atomic_json(raw / 'source_v4' / 'hashes.json', v4_hashes)
    atomic_json(raw / RV4.CONFIG_NAME, cfg)
    atomic_json(raw / RV4.FP_CONFIG_NAME, fp)
    (raw / AGX.ENTRY_NAME).write_text(AGX.ENTRY_SOURCE, encoding='utf-8')
    original = R2.EVALUATOR.read_text()
    patched = native_evaluator_owned_cleanup(original)
    (raw / 'leaderboard_evaluator_owned.py').write_text(patched)
    (raw / 'evaluator_cleanup.patch').write_text(''.join(difflib.unified_diff(
        original.splitlines(True), patched.splitlines(True), fromfile=str(R2.EVALUATOR),
        tofile=str(raw / 'leaderboard_evaluator_owned.py'))))
    cmd = evaluator_command(prep, run_dir, checkpoint)
    env, overrides = RV4.evaluator_env(prep, run_dir)
    atomic_json(raw / 'command.json', {'argv': cmd, 'cwd': str(R2.B2D), 'environment_overrides': overrides,
                                       'patched_evaluator_sha256': file_hash(raw / 'leaderboard_evaluator_owned.py')})
    ports = [args.port, args.port + 1, args.port + 2, args.port + 6000]
    process, owned, error, timed_out, cleanup, started = F.execute(srun, run_dir, cmd, env, ports, args.timeout_s,
                                                                    args.lock_wait_s)
    result = R2.summarize(run_dir, process, timed_out, error, cleanup, owned, started)
    fp_manifest, fp_problems = F.fast_prefix_outcome(run_dir, fp) if fp['options'] else (None, [])
    al_manifest, al_problems = RV4.actor_log_outcome(run_dir, cfg)
    result['fast_prefix'] = {'config': fp, 'agent_manifest': fp_manifest, 'problems': fp_problems}
    result['actor_log'] = {'manifest': al_manifest, 'problems': al_problems}
    atomic_json(run_dir / 'metrics/result.json', result)
    failures = []
    if error:
        failures.append(error)
    if timed_out:
        failures.append('wall-clock budget exhausted')
    if cleanup:
        failures.append('owned process cleanup errors: ' + str(cleanup))
    if not result['route_records']:
        failures.append('no official route record')
    elif any(m in str(result['route_status']) for m in R2.EXECUTION_FAILURE_STATUS):
        failures.append('official route status: ' + str(result['route_status']))
    if process is not None and process.returncode not in (0, None) and not timed_out:
        failures.append('evaluator exit code ' + str(process.returncode))
    if result['agent_summary'] is None:
        failures.append('agent summary missing (agent did not reach destroy)')
    failures += fp_problems
    srun.record({'kind': 'framelease_v4_arms_closed_loop_route', 'arm': fp['arm'], 'v4_arm': args.arm,
                 'policy': prep['arm'].policy, 'route_id': str(args.route_id), 'seed': args.seed, 'kappa': args.kappa,
                 'fast_prefix': fp['options']}, result, 'FAILED' if failures else 'COMPLETED',
                '; '.join(failures) or None)
    agent = result['agent_summary'] or {}
    v4 = agent.get('v4') or {}
    report = canonical({'arm': fp['arm'], 'v4_arm': args.arm, 'policy': prep['arm'].policy, 'route': prep['route'],
                        'route_status': result['route_status'], 'scores': result['scores'],
                        'gpu_usage': v4.get('gpu_usage'), 'deadline_miss_ratio': v4.get('deadline_miss_ratio'),
                        'action_age_s': agent.get('action_age_s'), 'p_both': v4.get('p_both'),
                        'fallback_tick_ratio': agent.get('fallback_tick_ratio'), 'commits': agent.get('commits'),
                        'jobs': agent.get('jobs'), 'fast_prefix': agent.get('fast_prefix'),
                        'actor_log': agent.get('actor_log'), 'warnings': al_problems, 'failures': failures})
    return srun.finish('FAILED' if failures else 'COMPLETED', report, failures,
                       acceptance='PARTIAL' if not failures else 'FAILED')


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not X.is_extension(requested_arm(argv)):
        return RV4.main(argv)                       # every arms_v4 arm: the pinned launcher, unchanged
    return run(parse_args(argv))


# ============================================================================================ job lines

def job_pins(envelope):
    """require_sha256 of a line of the new arm: the pins of every P1 line (jobs_v4.code_pins: v2 matrix files, v2 / v3
    package inits, v3 runtime, fast prefix, the v4 sources the agent imports), E* and the extension sources."""
    from framelease_v4.arms import jobs_v4 as J
    env_rel = str(Path(envelope)) if not Path(envelope).is_absolute() else str(Path(envelope).resolve().relative_to(ROOT))
    return J.code_pins([env_rel] + list(X.EXT_CODE))


def job_command(route_id, port, output_dir, envelope, utility='heuristic', kappa=1.0, seed=11,
                timeout_s=1410, lock_wait_s=600):
    """The launcher argv of one fl_global_shield line (the option order of protocol/p1_jobs.command)."""
    cmd = [PYTHON, '-B', STAGE + '.py', '--arm', X.GLOBAL_SHIELD, '--fast-prefix', FAST_PREFIX,
           '--kappa', f'{float(kappa):.1f}', '--seed', str(int(seed)), '--routes', AV.ROUTES_XML_REL,
           '--route-id', str(route_id), '--port', str(int(port)), '--output-dir', str(output_dir),
           '--timeout-s', str(int(timeout_s)), '--lock-wait-s', str(int(lock_wait_s)), '--envelope', str(envelope)]
    cmd += ['--policy-params', json.dumps({'utility': utility}, sort_keys=True)]
    return cmd


def job_line(route_id, port, output_dir, envelope, envelope_label, utility='heuristic', job_id=None, kappa=1.0,
             seed=11, wall_cap_s=1500, tier=1, phase=None, block=None, envelope_config=None, **extra):
    """One gpu_queue line of fl_global_shield (protocol arm = launcher arm = fl_global_shield). WRITTEN, NEVER
    LAUNCHED here: the caller (a phase job generator) decides the route set, ports, output layout and queue.
    envelope: E* relative to the project root (as the P1 lines name it); envelope_config: its offline configuration
    (e.g. 'T_x0.60' for E5), recorded as the P1 lines record it."""
    env_rel = str(envelope)
    sha = file_hash(ROOT / env_rel if not Path(env_rel).is_absolute() else env_rel)
    env_block = {'label': envelope_label, 'path': env_rel, 'sha256': sha}
    if envelope_config is not None:
        env_block['config'] = envelope_config
    job = {'id': job_id or f'v4ext_{X.GLOBAL_SHIELD}_{envelope_label}_k{float(kappa):.1f}_s{int(seed)}_r{route_id}',
           'kind': 'closed_loop', 'tier': int(tier),
           'cmd': job_command(route_id, port, output_dir, env_rel, utility, kappa, seed, wall_cap_s - 90),
           'wall_cap_s': int(wall_cap_s), 'arm_name': X.GLOBAL_SHIELD, 'protocol_arm': X.GLOBAL_SHIELD,
           'launcher': STAGE + '.py', 'candidate': f'{envelope_label}_{utility}', 'policy_params': {'utility': utility},
           'envelope': env_block, 'kappa': float(kappa), 'seed': int(seed), 'fast_prefix': FAST_PREFIX.split(','),
           'route_id': str(route_id), 'port': int(port), 'output_dir': str(output_dir),
           'require_sha256': job_pins(env_rel)}
    if phase is not None:
        job['phase'] = phase
    if block is not None:
        job['block'] = block
    job.update(extra)
    return job


def check_job_line(job, dry_run=True, timeout_s=600, isolated=False):
    """{'id', 'ok', 'problems', ...}: gpu_queue's contract, the pins against the tree (P1 pins + E* + EXT_CODE), the
    launcher's parsing and preparation in this process, the fixed lease constants of the configuration (PROTOCOL Secs.
    2.4, 7.4: cfg['v3']['lease'] == {} and the global lease's h_bar_s == 2.5; arms_ext.fixed_lease_problems), and the
    exact command with --dry-run in a subprocess (isolated=True runs it as `python -I ...`: the launcher puts the
    project root on sys.path itself, and the dry run imports nothing from $PYTHONPATH). Run it from the project root,
    as gpu_queue runs the line."""
    from framelease_v2 import gpu_queue as Q
    out = {'id': job['id'], 'problems': []}
    bad = Q.validate_job(job)
    if bad:
        out['problems'].append(f'gpu_queue rejects the job: {bad}')
    mism = Q.pin_mismatches(job['require_sha256'])
    if mism:
        out['problems'].append(f'pinned files differ from the tree: {[m["file"] for m in mism][:5]}')
    want_pins = set(job_pins(job['envelope']['path']))
    if set(job['require_sha256']) != want_pins:
        out['problems'].append('the pins are not the P1 pins + E* + the extension sources')
    cmd = job['cmd']
    if cmd[:3] != [PYTHON, '-B', STAGE + '.py']:
        out['problems'].append('not the extension launcher command')
        out['ok'] = False
        return out
    saved = dict(os.environ)
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            args = parse_args(cmd[3:])
            prep = prepare(args)
        cfg = prep['cfg']
        if cfg['arm'] != job['arm_name'] or prep['fp']['options'] != job['fast_prefix']:
            out['problems'].append('arm / fast prefix differ from the job')
        if (cfg.get('v3') or {}).get('envelope_sha256') != job['envelope']['sha256']:
            out['problems'].append('envelope sha256 of the configuration differs from the job')
        if dict(cfg['agent']['policy_params'] or {}) != dict(job['policy_params']):
            out['problems'].append('policy parameters differ from the job')
        out['problems'] += [f'configuration: {p}' for p in X.fixed_lease_problems(cfg)]
        out['agent_runtime_config_sha256'] = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
    except SystemExit as e:
        out['problems'].append(f'SystemExit: {e}')
    except BaseException as e:  # noqa: BLE001
        out['problems'].append(f'{type(e).__name__}: {e}')
    finally:
        os.environ.clear()
        os.environ.update(saved)
    if dry_run and not out['problems']:
        before = (ROOT / job['output_dir']).exists()
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', CUDA_VISIBLE_DEVICES='')
        argv = job['cmd'][:1] + (['-I'] if isolated else []) + job['cmd'][1:] + ['--dry-run']
        p = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout_s)
        if p.returncode != 0:
            out['problems'].append(f'dry run exit {p.returncode}: {p.stderr[-600:]}')
        else:
            d = json.loads(p.stdout)
            entry = d['command'][d['command'].index('--agent') + 1]
            dsha = hashlib.sha256(json.dumps(d['agent_runtime_config'], sort_keys=True).encode()).hexdigest()
            ok = (d.get('status') == 'NOT_STARTED' and d.get('v4_arm') == job['arm_name']
                  and entry.endswith(AGX.ENTRY_NAME)
                  and 'FRAMELEASE_V4_ARMS_CONFIG' in d['environment_overrides']
                  and 'FRAMELEASE_V2_RUNTIME_CONFIG' not in d['environment_overrides']
                  and d['ports'] == [job['port'], job['port'] + 1, job['port'] + 2, job['port'] + 6000]
                  and d['extension']['sources_sha256'] == {r: job['require_sha256'][r] for r in X.EXT_CODE}
                  and not X.fixed_lease_problems(d['agent_runtime_config']))
            if not ok:
                out['problems'].append('dry-run output does not match the job')
            if dsha != out.get('agent_runtime_config_sha256'):
                out['problems'].append('the dry run built another configuration than the in-process check')
            out['dry_run'] = {'status': d.get('status'), 'arm': d.get('arm'), 'ports': d.get('ports'),
                              'entry': entry.split('/')[-1], 'agent_runtime_config_sha256': dsha}
        if not before and (ROOT / job['output_dir']).exists():
            out['problems'].append('the dry run created the output directory')
    out['ok'] = not out['problems']
    return out


if __name__ == '__main__':
    raise SystemExit(main())
