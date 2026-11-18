#!/usr/bin/env python3
"""Run one Bench2Drive route under one Table I arm of the v4 matrix, with the fast prefix (framelease_v4/arms).

  python framelease_v4/arms/run_closed_loop_v4.py --arm ARM --route-id R [--kappa 1.0] [--seed 11] [--port P] \
      [--output-dir DIR] [--fast-prefix all|none|sdpa,gpu_preproc,lora_merged] [--policy-params JSON] \
      [--runtime-params JSON] [--lease-params PATH] [--envelope PATH] [--lease-overrides JSON] \
      [--utility-env KEY=VALUE ...] [--actor-log JSON | --no-actor-log] [--dry-run]

ARM: fixed_deep, fast_only, age_only, event_triggered, fl_original, fl_heuristic, fl_full (Table I) and fl_behaviour
(offline-RL data; arms_v4.py). age_only and fl_heuristic take --policy-params '{"utility": "v4_adet_d<d>"}' for the
depth-limited heuristic a_det^d (default 'heuristic' = a_det^10; max_depth is never used for d); fl_full needs
'{"utility": "v4_qnet_<sha12>"}' and --utility-env FRAMELEASE_V4_QNET=<weights>; fl_behaviour needs
'{"utility": "v4_eps<eps>_seed<s>[_d<d>]"}'. The utility is registered in this process and in the agent process.

Composition (nothing upstream is modified; the helpers are imported and called):
* configuration: arms_v4.build_config. The v2-rule arms take exactly the agent configuration that
  framelease_v2/run_closed_loop.agent_config builds for the corresponding v3-matrix baseline arm (v3_arms); the shield
  arms take exactly framelease_v3/runtime/run_closed_loop_v3.v3_configs; Age-Only / Event-Triggered are built the same
  way with their own mode. The policy is constructed once here as the agent will (validation, CPU only).
* fast prefix: the framelease_v3/fastprefix configuration (agent_entry.normalize_config checks, base 'v4'), applied
  in the agent by agent_entry.install_fast_prefix; the run is checked afterwards with
  run_closed_loop_fast.fast_prefix_outcome (manifest, options active, validation passed).
* execution: framelease_v2/run_closed_loop's preflight / evaluator_command / evaluator_env / summarize, the stage05
  crash-cleanup patch of the official evaluator, and run_closed_loop_fast.execute (shared GPU lock, port check,
  wall-clock budget, owned-process cleanup), so framelease_v2/gpu_queue.py classifies these runs like v2 / v3 runs.
The only differences from the v3 / fast-prefix launchers: the evaluator loads raw/framelease_v4_arms_agent_entry.py
(agent_v4.FrameLeaseV4Agent, one class for every arm), configured by raw/agent_runtime_config.json through
$FRAMELEASE_V4_ARMS_CONFIG; the v4 sources are frozen under raw/source_v4/ (v3 and fast-prefix sources as before).
Outputs: <output-dir>/runs/<utc>_<id>/ with the v2 layout plus raw/agent/framelease/{decisions.jsonl,
actors.jsonl.gz, actor_log.json, fast_prefix.json}. --dry-run validates everything and starts nothing.
"""
from __future__ import annotations

import argparse
import difflib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_common import StageRun, atomic_json, canonical, file_hash  # noqa: E402
from framelease_v2 import run_closed_loop as R2  # noqa: E402
from framelease_v2.latency_agent import ENV_RUNTIME_CONFIG  # noqa: E402
from framelease_v3.fastprefix import agent_entry as AE  # noqa: E402
from framelease_v3.fastprefix import fast_path as FP  # noqa: E402
from framelease_v3.fastprefix import run_closed_loop_fast as F  # noqa: E402
from framelease_v3.runtime import run_closed_loop_v3 as L  # noqa: E402
from framelease_v4.arms import agent_v4 as AG  # noqa: E402
from framelease_v4.arms import arms_v4 as AV  # noqa: E402

STAGE = 'framelease_v4/arms/run_closed_loop_v4'
DEFAULT_OUTPUT = ROOT / 'outputs/framelease_v4/arms_dev/adhoc'
CONFIG_NAME = 'agent_runtime_config.json'
FP_CONFIG_NAME = 'fast_prefix_config.json'
# every framelease_v4 source the agent process may import: the arms package and the v4 utilities (a_det^d, behaviour,
# Q-network) that arms_v4.build_policy registers for the age / shield arms (framelease_v4/rl/__init__.py runs on import)
V4_UTILITY_CODE = ('framelease_v4/rl/__init__.py', 'framelease_v4/rl/behaviour.py', 'framelease_v4/rl/features.py',
                   'framelease_v4/rl/qnet.py')
V4_CODE = ('framelease_v4/__init__.py', 'framelease_v4/arms/__init__.py', 'framelease_v4/arms/policies_v4.py',
           'framelease_v4/arms/runtime_v4.py', 'framelease_v4/arms/arms_v4.py', 'framelease_v4/arms/actor_log.py',
           'framelease_v4/arms/agent_v4.py', 'framelease_v4/arms/run_closed_loop_v4.py') + V4_UTILITY_CODE


def _json_arg(text):
    if text is None:
        return {}
    if text.startswith('@'):
        text = Path(text[1:]).read_text(encoding='utf-8')
    value = json.loads(text)
    if not isinstance(value, dict):
        raise argparse.ArgumentTypeError('expected a JSON object')
    return value


def _env_arg(text):
    if '=' not in text:
        raise argparse.ArgumentTypeError('expected KEY=VALUE')
    k, v = text.split('=', 1)
    return k.strip(), v


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], allow_abbrev=False,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--arm', required=True, choices=list(AV.ALL_ARMS))
    p.add_argument('--routes', type=Path, default=ROOT / AV.ROUTES_XML_REL, help='Bench2Drive routes XML')
    p.add_argument('--route-id', required=True)
    p.add_argument('--kappa', type=float, default=1.0)
    p.add_argument('--seed', type=int, default=11)
    p.add_argument('--port', type=int, default=3300, help='CARLA RPC port; +1, +2 and +6000 (TM) must be free')
    p.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT)
    p.add_argument('--timeout-s', type=float, default=7200.0, help='wall-clock budget of the whole evaluation')
    p.add_argument('--evaluator-timeout', type=float, default=180.0, help="evaluator's --timeout (agent watchdog)")
    p.add_argument('--lock-wait-s', type=float, default=0.0, help='wait up to this long for the shared GPU lock')
    p.add_argument('--carla-root', type=Path, default=None, help='default: $CARLA_ROOT')
    p.add_argument('--checkpoint', type=Path, default=None, help='default: $CHECKPOINT')
    p.add_argument('--fast-prefix', default='all', help="'all' (= sdpa,gpu_preproc,lora_merged), 'none' or a list")
    p.add_argument('--no-validate', action='store_true', help='skip the fast-prefix warm-up validation window')
    p.add_argument('--on-validation-failure', choices=AE.ON_FAILURE, default='raise')
    p.add_argument('--policy-params', type=_json_arg, default={}, help='policy parameters (JSON or @file)')
    p.add_argument('--runtime-params', type=_json_arg, default={}, help='RuntimeConfig overrides (JSON or @file)')
    p.add_argument('--lease-params', type=Path, default=None, help="lease parameter file (default: the arm's)")
    p.add_argument('--envelope', type=Path, default=None, help='residual envelope JSON (shield arms)')
    p.add_argument('--lease-overrides', type=_json_arg, default={}, help='SuffixLeaseConfig fields (JSON or @file)')
    p.add_argument('--utility-registrar', default=AV.DEFAULT_UTILITY_REGISTRAR,
                   help='module:function that registers a v4 utility (policy_params.utility) in the v3 shield')
    p.add_argument('--utility-env', type=_env_arg, action='append', default=[],
                   help='Q-network utility: KEY=VALUE (repeatable), e.g. FRAMELEASE_V4_QNET=<file>')
    p.add_argument('--actor-log', type=_json_arg, default={}, help='actor-log parameters (JSON or @file)')
    p.add_argument('--no-actor-log', action='store_true', help='disable the evaluation-only actor log')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args(argv)
    try:
        args.fp_options = FP.parse_options(args.fast_prefix)
    except ValueError as e:
        p.error(str(e))
    return args


def arm_label(arm, options):
    return f'{arm}_fp' if options else f'{arm}_fpnone'


def fast_prefix_config(args):
    """framelease_v3/fastprefix configuration (all of agent_entry.normalize_config's checks) with base 'v4'."""
    cfg = {'schema': AE.CONFIG_SCHEMA, 'base': 'v4', 'options': list(args.fp_options), 'validate': not args.no_validate,
           'on_validation_failure': args.on_validation_failure, 'strict_sources': True,
           'fast_path_sha256': F.sha256(FP.__file__), 'expected_upstream_sha256': dict(FP.UPSTREAM_SOURCE_SHA256),
           'arm': arm_label(args.arm, args.fp_options), 'base_arm': args.arm}
    return AV.normalize_fast_prefix(cfg)


def namespace(args, lease_params):
    """The fields framelease_v2.run_closed_loop's preflight / evaluator_command / evaluator_env read."""
    carla_root = args.carla_root or Path(os.environ.get('CARLA_ROOT', '/home/kang/opt/CARLA_0.9.15'))
    checkpoint = args.checkpoint or (Path(os.environ['CHECKPOINT']) if os.environ.get('CHECKPOINT') else None)
    return SimpleNamespace(policy=AV.ARMS[args.arm].policy, routes=Path(args.routes), route_id=str(args.route_id),
                           kappa=args.kappa, seed=args.seed, port=args.port, output_dir=args.output_dir,
                           lease_params=Path(lease_params) if lease_params else None, carla_root=carla_root,
                           checkpoint=checkpoint, timeout_s=args.timeout_s, evaluator_timeout=args.evaluator_timeout,
                           lock_wait_s=args.lock_wait_s)


def prepare(args):
    """Everything the run needs (CPU only). Raises SystemExit on an invalid configuration."""
    args.output_dir = Path(args.output_dir).resolve()
    actor = dict(args.actor_log or {})
    if args.no_actor_log:
        actor['enabled'] = False
    try:
        fp = fast_prefix_config(args)
        cfg, lease_params, envelope = AV.build_config(
            args.arm, kappa=args.kappa, seed=args.seed, policy_params=args.policy_params,
            runtime_params=args.runtime_params, lease_params=args.lease_params, envelope=args.envelope,
            lease_overrides=args.lease_overrides, utility_registrar=args.utility_registrar,
            utility_env=dict(args.utility_env) or None, fast_prefix=fp, actor_log=actor, routes=args.routes,
            route_id=args.route_id, port=args.port, output_dir=args.output_dir)
        ns = namespace(args, lease_params)
        if envelope and not Path(envelope).is_file():
            raise SystemExit(f'preflight failed:\n  envelope not found: {envelope}')
        info = R2.preflight(ns)
    except ValueError as e:
        raise SystemExit(f'invalid configuration: {e}')
    missing = [rel for rel in V4_CODE if not (ROOT / rel).is_file()]
    if missing:
        raise SystemExit('preflight failed:\n  v4 sources missing: ' + ', '.join(missing))
    return {'arm': AV.ARMS[args.arm], 'cfg': json.loads(json.dumps(cfg)), 'ns': ns, 'route': info,
            'lease_params': lease_params, 'envelope': envelope, 'fp': fp}


def evaluator_command(prep, run_dir, checkpoint):
    cmd = R2.evaluator_command(prep['ns'], run_dir, checkpoint)
    i = cmd.index('--agent')
    cmd[i + 1] = str(run_dir / 'raw' / AG.ENTRY_NAME)
    return cmd


def evaluator_env(prep, run_dir):
    env, overrides = R2.evaluator_env(prep['ns'], run_dir)
    for k in (ENV_RUNTIME_CONFIG,) + AG.FOREIGN_CONFIG_ENVS:
        env.pop(k, None)
        overrides.pop(k, None)
    env[AG.ENV_V4_CONFIG] = overrides[AG.ENV_V4_CONFIG] = str(run_dir / 'raw' / CONFIG_NAME)
    for k, v in ((prep['cfg'].get('utility') or {}).get('env') or {}).items():
        env[k] = overrides[k] = v
    return env, overrides


def utility_files(prep):
    """Extra files of a configured v4 utility: its environment files (the Q-network weights) and, for a registrar
    other than the default (whose modules are in V4_CODE), the registrar package's sources."""
    u = prep['cfg'].get('utility') or {}
    out = []
    if u.get('registrar') and u['registrar'] != AV.DEFAULT_UTILITY_REGISTRAR:
        mod = u['registrar'].split(':', 1)[0]
        spec = importlib.util.find_spec(mod)
        if spec is not None and spec.origin:
            pkg = Path(spec.origin).parent
            out += sorted(p for p in pkg.glob('*.py') if p.is_file())
    out += [Path(p) for p in (u.get('env_files_sha256') or {})]
    return out


def code_dependencies(prep):
    ns = prep['ns']
    deps = [ROOT / d for d in R2.CODE_DEPENDENCIES if (ROOT / d).is_file()]
    deps += [ROOT / d for d in L.V3_CODE if (ROOT / d).is_file()]
    deps += [ROOT / d for d in F.FP_CODE if (ROOT / d).is_file()]
    deps += [ROOT / d for d in F.UPSTREAM_FILES if (ROOT / d).is_file()]
    deps += [ROOT / d for d in V4_CODE if (ROOT / d).is_file() and d != STAGE + '.py']
    deps += [R2.EVALUATOR, R2.OFFICIAL_AGENT, R2.OFFICIAL_AGENT.with_name('pid_controller.py'), R2.MODEL_CONFIG,
             Path(ns.routes).resolve()]
    for p in (prep['lease_params'], prep['envelope']):
        if p:
            deps.append(Path(p))
    deps += utility_files(prep)
    seen, out = set(), []
    for d in deps:
        if str(d) not in seen:
            seen.add(str(d))
            out.append(d)
    return out


def freeze_v4_sources(raw, prep):
    out = {}
    rels = list(V4_CODE) + [str(p.resolve().relative_to(ROOT)) for p in utility_files(prep)
                            if p.resolve().is_relative_to(ROOT)]
    for rel in rels:
        src = ROOT / rel
        if src.is_file():
            dst = raw / 'source_v4' / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            out[rel] = file_hash(dst)
    return out


def run_config(prep, args, checkpoint, hash_cache):
    from stage02_real_vla import UNIDRIVE_COMMIT
    arm, cfg, info, fp = prep['arm'], prep['cfg'], prep['route'], prep['fp']
    lp, ep = prep['lease_params'], prep['envelope']
    return {'mode': 'closed-loop', 'arm': fp['arm'], 'v4_arm': arm.name, 'title': arm.title + ' + fast prefix',
            'kind': arm.kind, 'policy': arm.policy, 'clock': 'VIRTUAL_TIME_MEASURED_LATENCY', 'route': info,
            'routes': str(Path(args.routes).resolve()), 'routes_sha256': file_hash(args.routes), 'kappa': args.kappa,
            'seed': args.seed, 'port': args.port, 'tm_port': args.port + 6000, 'agent_config': cfg['agent'],
            'v4': cfg, 'checkpoint': str(checkpoint), 'checkpoint_sha256': R2.cached_file_hash(checkpoint, hash_cache),
            'lease_params_sha256': file_hash(lp) if lp else None, 'envelope_sha256': file_hash(ep) if ep else None,
            'model_source_commit': UNIDRIVE_COMMIT, 'evaluator_sha256': file_hash(R2.EVALUATOR),
            'official_agent_sha256': file_hash(R2.OFFICIAL_AGENT), 'wall_timeout_s': args.timeout_s,
            'fast_prefix': fp, 'entry': AG.ENTRY_NAME, 'runtime_class': 'framelease_v4.arms.runtime_v4.V4Runtime',
            'ground_truth_contract': 'simulator state only in the official scorer and in evaluation-only metric_info '
                                     'and actor log; never in the model input, the policy, the lease, the shield or '
                                     'the controller'}


def actor_log_outcome(run_dir, cfg):
    """(manifest or None, problems) of the evaluation-only actor log."""
    from framelease_v4.arms import actor_log as AL
    if not (cfg.get('actor_log') or {}).get('enabled', True):
        return None, []
    path = run_dir / 'raw' / 'agent' / 'framelease' / AL.MANIFEST_NAME
    if not path.is_file():
        return None, ['actor-log manifest missing (agent did not reach destroy)']
    try:
        man = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        return None, [f'actor-log manifest unreadable: {e}']
    problems = []
    if man.get('errors'):
        problems.append(f'actor log: {man["errors"]} errors ({man.get("disabled_reason")})')
    return man, problems


def run(args):
    prep = prepare(args)
    fp, cfg = prep['fp'], prep['cfg']
    if args.dry_run:
        placeholder = args.output_dir / 'runs' / '<UTC>_<ID>'
        env, overrides = evaluator_env(prep, placeholder)
        print(json.dumps({'status': 'NOT_STARTED', 'dry_run': True, 'arm': fp['arm'], 'v4_arm': args.arm,
                          'title': prep['arm'].title, 'kind': prep['arm'].kind, 'policy': prep['arm'].policy,
                          'route': prep['route'], 'agent_runtime_config': cfg, 'cwd': str(R2.B2D),
                          'command': evaluator_command(prep, placeholder, prep['ns'].checkpoint),
                          'environment_overrides': overrides,
                          'ports': [args.port, args.port + 1, args.port + 2, args.port + 6000]}, indent=1, default=str))
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
    atomic_json(raw / 'source_v4' / 'hashes.json', freeze_v4_sources(raw, prep))
    atomic_json(raw / CONFIG_NAME, cfg)
    atomic_json(raw / FP_CONFIG_NAME, fp)
    (raw / AG.ENTRY_NAME).write_text(AG.ENTRY_SOURCE, encoding='utf-8')
    original = R2.EVALUATOR.read_text()
    patched = native_evaluator_owned_cleanup(original)
    (raw / 'leaderboard_evaluator_owned.py').write_text(patched)
    (raw / 'evaluator_cleanup.patch').write_text(''.join(difflib.unified_diff(
        original.splitlines(True), patched.splitlines(True), fromfile=str(R2.EVALUATOR),
        tofile=str(raw / 'leaderboard_evaluator_owned.py'))))
    cmd = evaluator_command(prep, run_dir, checkpoint)
    env, overrides = evaluator_env(prep, run_dir)
    atomic_json(raw / 'command.json', {'argv': cmd, 'cwd': str(R2.B2D), 'environment_overrides': overrides,
                                       'patched_evaluator_sha256': file_hash(raw / 'leaderboard_evaluator_owned.py')})
    ports = [args.port, args.port + 1, args.port + 2, args.port + 6000]
    process, owned, error, timed_out, cleanup, started = F.execute(srun, run_dir, cmd, env, ports, args.timeout_s,
                                                                    args.lock_wait_s)
    result = R2.summarize(run_dir, process, timed_out, error, cleanup, owned, started)
    fp_manifest, fp_problems = F.fast_prefix_outcome(run_dir, fp) if fp['options'] else (None, [])
    al_manifest, al_problems = actor_log_outcome(run_dir, cfg)
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
    return run(parse_args(argv))


if __name__ == '__main__':
    raise SystemExit(main())
