"""CPU helpers shared by the framelease_v4/arms_ext tests (no GPU, no CARLA server, no model).

Reuses the pinned fakes of framelease_v4/arms/tests/helpers_v4.py (fake backend with known CUDA costs, fake clock, the
agent's control loop, fake CARLA world) and adds: the exported lease operating points E5 / E10 / B0 with their offline
configurations, the recorded offline frames of the lease ablation (outputs/framelease_v4/offline_ablation/frames and
the C1 sweep view, as framelease_v4/offline/export_envelopes.verify reads them), fake candidates and scenes, the
build arguments of every arm, launcher subprocesses (`python -I -B`, no GPU, one BLAS thread), the official-stack import
path for `python -I` (isolated mode ignores $PYTHONPATH; linux/env.sh puts the official Bench2Drive / CARLA packages
there, so they are inserted into sys.path in the same order), and a snapshot of every attribute of the pinned modules
(main_pinned_state, run in a fresh interpreter by test_arms_ext.py).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ['CUDA_VISIBLE_DEVICES'] = ''          # never touch the GPU from tests
sys.dont_write_bytecode = True                   # never leave __pycache__ in the pinned trees

ROOT = Path(__file__).resolve().parents[3]
ARMS_TESTS = ROOT / 'framelease_v4' / 'arms' / 'tests'
EXT_TESTS = Path(__file__).resolve().parent
for _p in (str(ROOT), str(ARMS_TESTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402

import helpers_v4 as HV  # noqa: E402  (the pinned fakes)

from framelease_v2 import latency_agent as la  # noqa: E402
from framelease_v3.runtime import v3_lease as VL  # noqa: E402

LEASE_PARAMS = HV.LEASE_PARAMS
ENVELOPE_DIR = ROOT / 'outputs/framelease_v4/envelopes'
ENVELOPES = {label: ENVELOPE_DIR / f'{label}.json' for label in ('E5', 'E10', 'B0')}
OFFLINE_CONFIGS = {'E5': 'T_x0.60', 'E10': 'T_x0.30', 'B0': 'T_x0.00'}       # PROTOCOL Sec. 4.3
PYTHON = str(ROOT / '.conda-unidrive-linux/bin/python')
P1_JOBS_DIR = ROOT / 'outputs/framelease_v4/queue_p1/jobs.d'                    # registered P1 job files (read only)


def lease_env(label='E5', **overrides):
    """The v3 LeaseEnv of a shield arm with the exported envelope (as arms_v4.build_policy builds it)."""
    return VL.build_lease_env(str(LEASE_PARAMS), str(ENVELOPES[label]), overrides or None)


def stack_ready():
    """CHECKPOINT and CARLA_ROOT of linux/env.sh (the launcher's preflight needs them; nothing is started)."""
    ck, carla = os.environ.get('CHECKPOINT'), os.environ.get('CARLA_ROOT')
    return bool(ck) and Path(ck).is_file() and bool(carla) and (Path(carla) / 'CarlaUE4.sh').is_file()


def official_stack_paths():
    """The import path of linux/env.sh: its $PYTHONPATH entries when it was sourced, else the same list rebuilt."""
    if os.environ.get('PYTHONPATH'):
        return [Path(p) for p in os.environ['PYTHONPATH'].split(os.pathsep) if p]
    work = ROOT / 'third_party/UniDriveVLA-linux/Bench2Drive'
    bench = ROOT / 'third_party/bench2drive-linux'
    carla = Path(os.environ.get('CARLA_ROOT') or '/home/kang/opt/CARLA_0.9.15')
    return [work, bench, bench / 'leaderboard', bench / 'scenario_runner', carla / 'PythonAPI',
            carla / 'PythonAPI' / 'carla']


def add_official_stack_paths():
    """Insert the linux/env.sh import path after the project root, in its order and ahead of site-packages, as
    $PYTHONPATH would (python -I ignores the variable). Returns the entries added (for remove_paths)."""
    added = [str(p) for p in official_stack_paths() if p.is_dir() and str(p) not in sys.path]
    i = sys.path.index(str(ROOT)) + 1 if str(ROOT) in sys.path else 0
    sys.path[i:i] = added
    return added


def remove_paths(paths):
    for p in paths:
        if p in sys.path:
            sys.path.remove(p)


class Env:
    """Set (value) or remove (None) environment variables; restored on exit."""

    def __init__(self, **values):
        self.values = values
        self.saved = {}

    def __enter__(self):
        for k, v in self.values.items():
            self.saved[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = str(v)
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def drop_v4_utilities():
    """Remove the v4 utilities from framelease_v3.runtime.v3_shield.UTILITIES (a fresh agent process has none)."""
    from framelease_v3.runtime import v3_shield as VS
    for k in [k for k in VS.UTILITIES if str(k).startswith('v4_')]:
        del VS.UTILITIES[k]


def subprocess_env():
    """Environment of a launcher subprocess: the caller's (linux/env.sh), no GPU, no byte code, one BLAS thread."""
    return dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1',
                MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')


def run_python(args, timeout=600):
    """`python -I -B ARGS` in the project root with subprocess_env() (niceness and I/O class are inherited)."""
    import subprocess
    return subprocess.run([PYTHON, '-I', '-B'] + [str(a) for a in args], cwd=ROOT, env=subprocess_env(),
                          capture_output=True, text=True, timeout=timeout)


def offline_ready():
    from framelease_v4.offline import common as C
    return (C.OUT / 'frames').is_dir() and (C.VIEW / 'clips').is_dir()


def recorded_frames(every=1, clips=None):
    """Yield (clip, i, d, plan, det7, score, label) for the recorded frames of the offline lease ablation: d is the
    stage_frames record of the clip (hg_T / ts_T per TRAIN configuration), plan the depth-1 plan of frame i."""
    from framelease_v2.calibration import SweepClip
    from framelease_v4.offline import common as C
    from framelease_v4.offline import stage_frames as SF
    for name in clips or C.load_lists()['all']:
        d = SF.load_clip(name)
        sc = SweepClip(C.VIEW, name)
        kidx = {int(f): k for k, f in enumerate(sc.frame_idx)}
        for i in range(0, len(d['frame_idx']), every):
            k = kidx[int(d['frame_idx'][i])]
            det7, score, label = sc.dets(k)
            yield name, i, d, sc.cand[k, C.DEPTH - 1], det7, score, label


def plain_global_H(plan, det7, score, label, env, prm):
    """The offline GLOBAL design literally: framelease_v4/offline/stage_frames.global_H on
    framelease_v2.lease.lease_geometry, capped at H_bar (PROTOCOL Sec. 7.4)."""
    from framelease_v2 import lease as L2
    from framelease_v4.offline import stage_frames as SF
    geom = L2.lease_geometry(plan, det7, score, label, env.ego, prm)
    return float(min(SF.global_H(geom, prm), env.cfg.h_bar_s))


def dets_ns(boxes, scores, labels, valid=True):
    """A detection set as the policy reads it (boxes, scores, labels, valid)."""
    return SimpleNamespace(boxes=np.asarray(boxes, dtype=float).reshape(-1, 7), scores=np.asarray(scores, dtype=float),
                           labels=np.asarray(labels), valid=bool(valid))


def candidate(plan, dets, job_id=1, depth=1, capture_s=0.0):
    """A released candidate as V3Runtime hands it to the policy (only the fields the lease reads)."""
    obs = SimpleNamespace(obs_id=job_id, capture_s=float(capture_s), speed_mps=5.0)
    return SimpleNamespace(job_id=job_id, depth=depth, plan_xy=np.asarray(plan, dtype=float), dets=dets, obs=obs,
                           obs_id=job_id, capture_s=float(capture_s))


def vehicle(x, y, yaw=np.pi / 2, vx=0.0, vy=0.0, length=4.5, width=1.9):
    return [x, y, length, width, yaw, vx, vy]


SCENE_PHASES = ('no_relevant_agents', 'global_zero', 'global_lease', 'global_cap', 'global_lease')


def scene_boxes(obs_id):
    """(boxes, scores, labels) of the closed-loop test scene at observation obs_id (LiDAR frame; the fake plans run
    along +y at 5 m/s), in cycles of 100 observations (5 s), 20 observations per phase (SCENE_PHASES, the global lease
    with E5): no detection (H_bar); a stopped car on the path (H = 0); a car closing in the next lane (0 < H < H_bar);
    a far car only (H_bar by the cap); the far car and a low-confidence pedestrian beside the path (score 0.2: it
    counts in mode 'cap' and binds, 0 < H < H_bar). Labels: 0 car, 7 pedestrian."""
    phase = int(obs_id) % 100
    if phase < 20:
        return np.zeros((0, 7)), np.zeros(0), np.zeros(0, dtype=int)
    if phase < 40:
        return np.asarray([vehicle(0.0, 9.0)]), np.asarray([0.9]), np.asarray([0])
    if phase < 60:
        return (np.asarray([vehicle(4.0, 18.0 - 0.2 * (phase - 40), vy=-2.0)]), np.asarray([0.8]),
                np.asarray([0]))
    if phase < 80:
        return np.asarray([vehicle(30.0, 40.0)]), np.asarray([0.9]), np.asarray([0])
    return (np.asarray([vehicle(30.0, 40.0), [3.5, 8.0, 0.6, 0.6, 0.0, -0.3, 0.0]]), np.asarray([0.9, 0.2]),
            np.asarray([0, 7]))


def scene_dets(obs):
    """la.DetectionSet of scene_boxes for a fake or agent observation (helpers_v4.dets_with)."""
    boxes, scores, labels = scene_boxes(obs.obs_id)
    return HV.dets_with(obs, boxes, scores, labels)


# ============================================================================================ arms and launchers

QNET_FILE = ROOT / 'outputs/framelease_v4/rl_dev/smoke_20261110/qnet_fqi_nolease.json'     # v4_qnet_6479fc17e9ed
QNET_NAME = 'v4_qnet_6479fc17e9ed'
PINNED_LAUNCHER_REL = 'framelease_v4/arms/run_closed_loop_v4.py'
EXT_LAUNCHER_REL = 'framelease_v4/arms_ext/run_closed_loop_ext.py'
PINNED_MODULES = ('framelease_v2.latency_agent', 'framelease_v2.lease', 'framelease_v2.policies',
                  'framelease_v2.run_closed_loop', 'framelease_v3.runtime.v3_lease', 'framelease_v3.runtime.v3_shield',
                  'framelease_v3.runtime.v3_commit', 'framelease_v3.runtime.v3_scheduler', 'framelease_v3.runtime.v3_arms',
                  'framelease_v3.runtime.run_closed_loop_v3', 'framelease_v3.fastprefix.agent_entry',
                  'framelease_v3.fastprefix.run_closed_loop_fast', 'framelease_v4', 'framelease_v4.arms',
                  'framelease_v4.arms.arms_v4', 'framelease_v4.arms.agent_v4', 'framelease_v4.arms.policies_v4',
                  'framelease_v4.arms.runtime_v4', 'framelease_v4.arms.run_closed_loop_v4', 'framelease_v4.arms.actor_log',
                  'framelease_v4.rl', 'framelease_v4.rl.behaviour')


def arm_kwargs():
    """Build arguments of every arms_v4 arm and of fl_global_shield (the explicit E5 envelope where it applies)."""
    e5 = str(ENVELOPES['E5'])
    return {'fixed_deep': {}, 'fast_only': {}, 'age_only': {'policy_params': {'utility': 'v4_adet_d4'}},
            'event_triggered': {}, 'fl_original': {}, 'fl_heuristic': {'envelope': e5},
            'fl_full': {'envelope': e5, 'policy_params': {'utility': QNET_NAME},
                        'utility_env': {'FRAMELEASE_V4_QNET': str(QNET_FILE)}},
            'fl_behaviour': {'envelope': e5, 'policy_params': {'utility': 'v4_eps0.300_seed11'}},
            'fl_global_shield': {'envelope': e5, 'policy_params': {'utility': 'v4_adet_d4'}}}


def launcher_argv(arm, out_dir, route_id='2086', port=3300):
    """Launcher arguments of arm_kwargs() (route 2086, port 3300), for both launchers."""
    import json
    kw = arm_kwargs()[arm]
    argv = ['--arm', arm, '--route-id', str(route_id), '--port', str(port), '--output-dir', str(out_dir)]
    if 'envelope' in kw:
        argv += ['--envelope', kw['envelope']]
    if 'policy_params' in kw:
        argv += ['--policy-params', json.dumps(kw['policy_params'], sort_keys=True)]
    for k, v in (kw.get('utility_env') or {}).items():
        argv += ['--utility-env', f'{k}={v}']
    return argv


def dry_run(launcher_rel, argv, timeout=600):
    """A launcher's --dry-run in a fresh `python -I -B` interpreter (CompletedProcess)."""
    return run_python([launcher_rel] + list(argv) + ['--dry-run'], timeout=timeout)


def p1_shield_line():
    """The first fl_heuristic line of the registered P1 lease block (b02_lease_s1.jsonl; read only), or None."""
    import json
    path = P1_JOBS_DIR / 'b02_lease_s1.jsonl'
    if not path.is_file():
        return None
    for line in path.read_text(encoding='utf-8').splitlines():
        job = json.loads(line)
        if job.get('arm_name') == 'fl_heuristic':
            return job
    return None


# ============================================================================================ pinned-state snapshot

def _state_of(value):
    """Identity of a value and, for containers, of their items (detects rebinding and mutation)."""
    out = [id(value)]
    if isinstance(value, dict):
        out.append(sorted((repr(k), id(v)) for k, v in value.items()))
    elif isinstance(value, (list, tuple)):
        out.append([id(v) for v in value])
    elif isinstance(value, (set, frozenset)):
        out.append(sorted(id(v) for v in value))
    return out


def pinned_state(modules=PINNED_MODULES):
    """{name: state} of every attribute of the pinned modules and of the classes they define."""
    import importlib
    import inspect
    for name in modules:                             # import all first: the snapshot holds every submodule binding
        importlib.import_module(name)
    out = {}
    for name in modules:
        mod = importlib.import_module(name)
        for k, v in list(vars(mod).items()):
            if k == '__warningregistry__':
                continue
            out[f'{name}.{k}'] = _state_of(v)
            if inspect.isclass(v) and v.__module__ == name:
                for ck, cv in list(vars(v).items()):
                    out[f'{name}.{k}.{ck}'] = _state_of(cv)
    return out


def compare_states(before, after):
    """(changed, removed, added) attribute names."""
    changed = sorted(k for k in before if k in after and before[k] != after[k])
    removed = sorted(k for k in before if k not in after)
    added = sorted(k for k in after if k not in before)
    return changed, removed, added


def main_pinned_state(launcher=True, extension=True):
    """Fresh interpreter: snapshot the pinned modules, configure every arm, snapshot again, print a JSON report.

    extension=True: through framelease_v4/arms_ext (arms_ext.build_config / agent_config_from / validate_config /
    build_policy for the 8 arms_v4 arms and fl_global_shield; with launcher=True the --dry-run of both launchers,
    in process). extension=False (the control): the same with the arms_v4 functions and the pinned launcher only, so
    that the attributes the pinned code itself changes (utility registration, caches) are known."""
    import contextlib
    import importlib
    import io
    import json
    import tempfile
    import types
    from framelease_v3.runtime import v3_shield as VS
    before = pinned_state()
    utilities_before = sorted(VS.UTILITIES)
    from framelease_v4.arms import arms_v4 as AV
    if extension:
        from framelease_v4.arms_ext import arms_ext as X
        api = X
    else:
        api = AV
    used = []
    saved = dict(os.environ)
    for arm, kw in arm_kwargs().items():
        if not extension and arm not in AV.ARMS:
            continue
        cfg, _, _ = api.build_config(arm, **kw)
        api.agent_config_from(cfg)
        api.validate_config(cfg)
        api.build_policy(json.loads(json.dumps(cfg)))
        used.append(arm)
        os.environ.clear()
        os.environ.update(saved)
    dry = {}
    if launcher and stack_ready():
        from framelease_v4.arms import run_closed_loop_v4 as RV4
        mains = [('pinned', RV4.main)]
        if extension:
            from framelease_v4.arms_ext import run_closed_loop_ext as RX
            mains = [('ext', RX.main)] + mains
        with tempfile.TemporaryDirectory() as tmp:
            for arm in used:
                for tag, fn in mains:
                    if tag == 'pinned' and arm not in AV.ARMS:
                        continue
                    buf = io.StringIO()
                    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                        rc = fn(launcher_argv(arm, tmp) + ['--dry-run'])
                    dry[f'{tag}:{arm}'] = rc
                    os.environ.clear()
                    os.environ.update(saved)
    after = pinned_state()
    changed, removed, added = compare_states(before, after)
    added_modules = []
    for k in list(added):
        mod_name, attr = k.rsplit('.', 1)
        try:
            v = getattr(importlib.import_module(mod_name), attr)
        except (ImportError, AttributeError):
            continue
        if isinstance(v, types.ModuleType) and v.__name__ == f'{mod_name}.{attr}':
            added.remove(k)                        # the import system binds a new submodule in its package
            added_modules.append(k)
    print(json.dumps({'extension': bool(extension), 'arms_used': used, 'dry_runs': dry, 'n_attributes': len(before),
                      'changed': changed, 'removed': removed, 'added': added,
                      'added_submodule_bindings': added_modules,
                      'utilities_registered': sorted(set(VS.UTILITIES) - set(utilities_before))}))


__all__ = ['HV', 'la', 'ROOT', 'ARMS_TESTS', 'EXT_TESTS', 'LEASE_PARAMS', 'ENVELOPES', 'OFFLINE_CONFIGS', 'PYTHON',
           'P1_JOBS_DIR', 'lease_env', 'stack_ready', 'official_stack_paths', 'add_official_stack_paths',
           'remove_paths', 'Env', 'drop_v4_utilities', 'subprocess_env', 'run_python', 'offline_ready',
           'recorded_frames', 'plain_global_H', 'dets_ns', 'candidate', 'vehicle', 'SCENE_PHASES', 'scene_boxes',
           'scene_dets', 'QNET_FILE', 'QNET_NAME', 'PINNED_LAUNCHER_REL', 'EXT_LAUNCHER_REL', 'PINNED_MODULES',
           'arm_kwargs', 'launcher_argv', 'dry_run', 'p1_shield_line', 'pinned_state', 'compare_states',
           'main_pinned_state']
