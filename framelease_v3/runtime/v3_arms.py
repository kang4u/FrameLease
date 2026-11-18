"""Arms of the v3 closed-loop matrix (one launcher for all of them: run_closed_loop_v3.py).

fl_v3_heuristic   FrameLease + Heuristic (v3): suffix lease, shield, a_det, versioned commit, watchdog
fast_only         v2 arm fast_only_k1.0_s11 (Fast Only, 1 flow step, expiry at 3.0 s observation age)
fixed_deep        v2 arm fixed_deep_k1.0_s11 (Fixed Deep, 10 flow steps, expiry 3.0 s)
fixed_deep_age2.0 v2 arm fixed_deep_age2.0_k1.0_s11 (Age-Only: Fixed Deep with a fixed 2.0 s age expiry)
fl_global         v2 arm framelease_q95env_k1.0_s11 (FrameLease-Global: v2 global-margin lease gate, q95 bounds,
                  reserve 0.2 m, H_max 2.0 s = runtime max_age_s, v2 refresh-time reservation rule)

Baseline arms are executed by the UNCHANGED framelease_v2 launcher (framelease_v2/run_closed_loop.py main(), called
in-process with exactly the argument list framelease_v2/closed_loop_matrix.py generates for the named v2 arm), so the
agent process runs only unchanged framelease_v2 code with a byte-identical agent configuration.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

LEASE_PARAMS_REL = 'outputs/framelease_v2/c2_calibration/full_20261107T045343Z/lease_params_q95_envelope.json'
ROUTES_XML_REL = 'third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/data/bench2drive220.xml'
V3_MODE = 'fl_v3_heuristic'
V3_RUNTIME_PARAMS = {'max_age_s': 2.5, 'profile_quantile': 0.99}


@dataclass(frozen=True)
class ArmSpec:
    name: str
    policy: str
    runtime_params: Optional[dict] = None
    lease_params: Optional[str] = None
    v2_arm: Optional[str] = None
    title: str = ''
    description: str = ''
    v3_policy_params: dict = field(default_factory=dict)

    @property
    def is_v3(self):
        return self.policy == V3_MODE

    @property
    def expected_max_age_s(self):
        if self.runtime_params and 'max_age_s' in self.runtime_params:
            return float(self.runtime_params['max_age_s'])
        return 2.0 if self.policy == 'framelease' else None   # v2 launcher default: max_age_s = lease h_max_s


ARMS = {a.name: a for a in (
    ArmSpec('fl_v3_heuristic', V3_MODE, dict(V3_RUNTIME_PARAMS), LEASE_PARAMS_REL, None, 'FrameLease + Heuristic',
            'suffix lease (T_pred 3.0, T_c 0.5, d_safe 0.5, delta 0.2; envelope pluggable, default = the isotropic q95 '
            'sigma/vbar/abar of lease_params_q95_envelope.json), shield (latency-profile p99 bounds, eps 0.05 s, '
            'R_REFINE = L_REFRESH + L_commit, R_REFRESH = 0), a_det = refine while feasible and depth < 10 else '
            'refresh, none feasible -> keep the active plan until D* (watchdog fallback after it) + recovery refresh, '
            'versioned commit (Eq. 9); runtime max_age_s 2.5 = H_bar (unused by the v3 validity), '
            'profile_quantile 0.99'),
    ArmSpec('fast_only', 'fast_only', {'max_age_s': 3.0}, None, 'fast_only_k1.0_s11', 'Fast Only',
            'Fast Only (1 flow step), plans expire at 3.0 s (v2 arm, unchanged v2 launcher and agent)'),
    ArmSpec('fixed_deep', 'fixed_deep', {'max_age_s': 3.0}, None, 'fixed_deep_k1.0_s11', 'Fixed Deep',
            'Fixed Deep (10 flow steps), plans expire at 3.0 s (v2 arm, unchanged v2 launcher and agent)'),
    ArmSpec('fixed_deep_age2.0', 'fixed_deep', {'max_age_s': 2.0}, None, 'fixed_deep_age2.0_k1.0_s11', 'Age-Only',
            'Fixed Deep with a fixed 2.0 s observation-age expiry (v2 cap-ablation arm, unchanged v2 code)'),
    ArmSpec('fl_global', 'framelease', None, LEASE_PARAMS_REL, 'framelease_q95env_k1.0_s11', 'FrameLease-Global',
            'v2 FrameLease: global-margin lease gate with lease_params_q95_envelope.json (reserve 0.2 m, H_max 2.0 s, '
            'runtime max_age_s = H_max), v2 refresh-time reservation rule (v2 arm, unchanged v2 code)'),
)}
BASELINE_ARMS = tuple(a for a in ARMS if not ARMS[a].is_v3)


def arm_id(arm, kappa, seed):
    return f'{arm}_k{float(kappa):.1f}_s{int(seed)}'


def v2_policy_args(arm: ArmSpec, kappa, seed):
    """framelease_v2/closed_loop_matrix.py arm_args() for the v2 arm this baseline reproduces (same order)."""
    if arm.is_v3:
        raise ValueError(f'{arm.name} is not a v2 arm')
    args = ['--policy', arm.policy, '--kappa', f'{float(kappa):.1f}', '--seed', str(int(seed))]
    if arm.runtime_params:
        args += ['--runtime-params', json.dumps(arm.runtime_params, sort_keys=True)]
    if arm.lease_params:
        args += ['--lease-params', arm.lease_params]
    return args


def v2_launcher_argv(arm: ArmSpec, kappa, seed, routes, route_id, port, output_dir, timeout_s=None, lock_wait_s=None,
                     evaluator_timeout=None, checkpoint=None, carla_root=None, dry_run=False):
    """The complete framelease_v2/run_closed_loop.py argument list of a baseline run (closed_loop_matrix.job_for
    order; optional launcher-only flags appended)."""
    argv = [*v2_policy_args(arm, kappa, seed), '--routes', str(routes), '--route-id', str(route_id),
            '--port', str(int(port)), '--output-dir', str(output_dir)]
    if timeout_s is not None:
        argv += ['--timeout-s', str(timeout_s)]
    if lock_wait_s is not None:
        argv += ['--lock-wait-s', str(lock_wait_s)]
    if evaluator_timeout is not None:
        argv += ['--evaluator-timeout', str(evaluator_timeout)]
    if checkpoint is not None:
        argv += ['--checkpoint', str(checkpoint)]
    if carla_root is not None:
        argv += ['--carla-root', str(carla_root)]
    if dry_run:
        argv += ['--dry-run']
    return argv


__all__ = ['LEASE_PARAMS_REL', 'ROUTES_XML_REL', 'V3_MODE', 'V3_RUNTIME_PARAMS', 'ArmSpec', 'ARMS', 'BASELINE_ARMS',
           'arm_id', 'v2_policy_args', 'v2_launcher_argv']
