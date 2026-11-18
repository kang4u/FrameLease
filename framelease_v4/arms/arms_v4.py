"""The seven arms of Table I (outline 1109, Sec. IV-A) and their exact configuration (framelease_v4/arms).

Common to every arm (the fair-protocol contract): the same UniDriveVLA checkpoint and official Bench2Drive stack, the
fast prefix (SDPA + exact GPU preprocessing + merged LoRA, framelease_v3/fastprefix), seed, kappa (GPU contention
scale), the same runtime class (runtime_v4.V4Runtime: v2 measured-latency timeline, v3 commit gate and watchdog), the
same agent class (agent_v4.FrameLeaseV4Agent), the same evaluation-only actor log, the same temporal mode / precision /
prompt / warm-up. Arms differ only in the scheduling policy and its validity rule:

| arm             | Table I row          | kind    | policy (code)                                    | validity of a committed plan  |
|-----------------|----------------------|---------|--------------------------------------------------|-------------------------------|
| fixed_deep      | Fixed Deep           | v2_rule | framelease_v2 FixedDeep (10 flow steps)          | max age 3.0 s                 |
| fast_only       | Fast Only            | v2_rule | framelease_v2 FastOnly (1 flow step)             | max age 3.0 s                 |
| age_only        | Age-Only             | age     | policies_v4.AgeLeasePolicy (v3 shield + a_det,   | constant age lease A          |
|                 |                      |         | lease D = t_k + A)                               | (capped at H_bar 2.5 s)       |
| event_triggered | Event-Triggered      | event   | policies_v4.EventTriggeredV4 (v2 rules)          | max age 3.0 s                 |
| fl_original     | Original FrameLease  | v2_rule | framelease_v2 FrameLease (global-margin lease,    | v2 lease, capped at H_max 2 s |
|                 |                      |         | q95 file, refresh-time reservation, no shield)   |                               |
| fl_heuristic    | FrameLease+Heuristic | shield  | framelease_v3 ShieldedHeuristicPolicy (suffix    | suffix lease (Eq. 1-3),       |
|                 |                      |         | lease, shield Eq. 5, a_det, versioned commit)    | capped at H_bar 2.5 s         |
| fl_full         | Full FrameLease      | shield  | the same + a learned utility (Eq. 6/8) named by  | suffix lease                  |
|                 |                      |         | policy_params.utility, registered by its owner   |                               |
| fl_behaviour    | (RL data, not Tab. I)| shield  | the same + the epsilon-random behaviour utility  | suffix lease                  |

Utilities (policy_params.utility, Eq. 8 consults it only when |A_feas| = 2): age_only and fl_heuristic accept
'heuristic' (= a_det^10, the v3 heuristic) or 'v4_adet_d<d>' (a_det^d, PROTOCOL Sec. 4.4); fl_full a Q-network
'v4_qnet_<sha12>'; fl_behaviour a behaviour name 'v4_eps<eps>_seed<s>[_d<d>]'. Every v4 utility is registered in the
v3 shield by build_config (launcher process) and again by build_policy (the evaluator's agent process) through the
registrar recorded in the configuration. The heuristic depth d is a utility parameter: max_depth (policy or runtime)
must stay 10 in every age / shield arm, so d is never tuned through max_depth.

Original FrameLease vs Full FrameLease (the outline asks for the exact difference): Original = the v2 method (global
minimum margin over the whole plan with the q95 isotropic envelope, capped at 2.0 s; a refresh-time reservation rule
S = D - t - L_refresh - G >= next step; no feasibility shield, no learned selection; v2 commit / expiry). Full =
suffix-aligned first-failure lease (Eq. 1-3, H_bar 2.5 s), the action-specific shield (Eq. 5) with the decision rule
(Eq. 8), a learned utility among feasible actions only, versioned commit with the commit-time margin check (Eq. 9).

Defaults below are the documented priors. Hyperparameters marked tunable are to be selected on TRAINING routes only
(never on the 44 test routes); the tuning task passes the selected values through --policy-params / --envelope /
--lease-overrides, which every job line records.
"""
from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from framelease_v2 import latency_agent as la
from framelease_v2 import policies as P
from framelease_v3.runtime import v3_arms as A3
from framelease_v4.arms import policies_v4 as PV

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = 'framelease_v4.arms.agent_config/1'
LEASE_PARAMS_REL = A3.LEASE_PARAMS_REL
ROUTES_XML_REL = A3.ROUTES_XML_REL
NON_LEASE_MAX_AGE_S = 3.0
SHIELD_RUNTIME = dict(A3.V3_RUNTIME_PARAMS)          # max_age_s 2.5 (= H_bar, unused by lease validity), q 0.99
DEFAULT_UTILITY_REGISTRAR = 'framelease_v4.rl.behaviour:register_utility_name'
KINDS = ('v2_rule', 'event', 'age', 'shield')
AGENT_DEFAULTS = {'temporal_mode': 'latest', 'precision': 'bf16-autocast', 'prompt_command': 'official',
                  'warmup': True, 'record_metric_info': True}


@dataclass(frozen=True)
class ArmV4:
    name: str
    title: str
    kind: str
    policy: str
    params: dict = field(default_factory=dict)
    runtime: dict = field(default_factory=dict)
    lease_params: Optional[str] = None
    v3_arm: Optional[str] = None
    requires_utility: bool = False
    tunable: dict = field(default_factory=dict)
    description: str = ''
    utilities: tuple = ()          # utility kinds the arm accepts (age / shield arms), see utility_kind()


# Utility kinds (policy_params.utility of the 'age' and 'shield' arms; consulted by Eq. 8 only when |A_feas| = 2):
#   heuristic  'heuristic' or absent: the v3 heuristic = a_det^10 (refine while feasible)
#   adet       'v4_adet_d<d>', d in 1..10: the depth-limited heuristic a_det^d (PROTOCOL Sec. 4.4)
#   behaviour  'v4_eps<eps>_seed<seed>[_d<d>]': epsilon-random behaviour around a_det^d (offline-RL data, Sec. 5.3)
#   qnet       'v4_qnet_<sha12>': the CPU Q-network (Eqs. 6, 8; needs FRAMELEASE_V4_QNET)
# The heuristic depth d is a UTILITY parameter: the shield's C_REFINE depth limit (policy_params.max_depth and the
# runtime max_depth) stays 10 in every age / shield arm, so d is never tuned through max_depth (Sec. 2.4).
UTILITY_KINDS = ('heuristic', 'adet', 'behaviour', 'qnet')
SHIELD_MAX_DEPTH = 10
HEURISTIC_UTILITIES = ('heuristic', 'adet')

ARMS = {a.name: a for a in (
    ArmV4('fixed_deep', 'Fixed Deep', 'v2_rule', 'fixed_deep', {}, {'max_age_s': NON_LEASE_MAX_AGE_S}, None,
          'fixed_deep', description='all 10 flow steps per observation, only the final plan is committed, refresh '
                                    'whenever the GPU is free; plans expire at 3.0 s observation age'),
    ArmV4('fast_only', 'Fast Only', 'v2_rule', 'fast_only', {}, {'max_age_s': NON_LEASE_MAX_AGE_S}, None,
          'fast_only', description='1 flow step per observation, refresh whenever the GPU is free; expiry 3.0 s'),
    ArmV4('age_only', 'Age-Only', 'age', 'age_only', {'age_lease_s': 2.0}, dict(SHIELD_RUNTIME), LEASE_PARAMS_REL,
          None, tunable={'age_lease_s': [1.0, 1.5, 2.0, 2.5], 'utility': 'a_det^{d*} inherited (v4_adet_d<d*>)'},
          description='v3 shield + a_det^d with the constant observation-age lease D = t_k + A: refine while the age '
                      'budget leaves room for a refresh, refresh by age only; plans expire at age A',
          utilities=HEURISTIC_UTILITIES),
    ArmV4('event_triggered', 'Event-Triggered', 'event', 'event_triggered', {}, {'max_age_s': NON_LEASE_MAX_AGE_S},
          None, None, tunable={'(speed_delta_mps, yaw_delta_rad, det_shift_m)': [[1.0, 0.1, 2.0], [0.5, 0.05, 1.0]],
                               'heartbeat_s': [2.0, 1.0]},
          description='v2 EventTriggered: ego-state events (speed / heading / command) and detection-set changes '
                      'trigger inference, ego events preempt refinement, heartbeat refresh at the max age minus '
                      'the refresh reservation; expiry 3.0 s'),
    ArmV4('fl_original', 'Original FrameLease', 'v2_rule', 'framelease', {}, {}, LEASE_PARAMS_REL, 'fl_global',
          description='v2 FrameLease: global-margin lease (q95 isotropic envelope, reserve 0.2 m, H_max 2.0 s = '
                      'runtime max_age_s), refresh-time reservation, no shield, no learned selection'),
    ArmV4('fl_heuristic', 'FrameLease + Heuristic', 'shield', A3.V3_MODE, {}, dict(SHIELD_RUNTIME), LEASE_PARAMS_REL,
          'fl_v3_heuristic', tunable={'envelope': 'exported offline candidates E5 / E10 / B0 '
                                                  '(framelease_v4/offline/export_envelopes.py)',
                                      'utility': ['heuristic', 'v4_adet_d4', 'v4_adet_d1']},
          description='suffix lease (T_pred 3.0, T_c 0.5, d_safe 0.5, delta 0.2), shield Eq. 5 (p99 bounds, eps '
                      '0.05 s), a_det^d (heuristic = a_det^10, v4_adet_d<d>), versioned commit Eq. 9, watchdog',
          utilities=HEURISTIC_UTILITIES),
    ArmV4('fl_full', 'Full FrameLease', 'shield', A3.V3_MODE, {}, dict(SHIELD_RUNTIME), LEASE_PARAMS_REL,
          'fl_v3_heuristic', requires_utility=True,
          tunable={'envelope': 'as fl_heuristic', 'utility': 'v4_qnet_<sha12> learned on training routes '
                                                             '(framelease_v4/rl; its a_det^{d*} is in the file)'},
          description='fl_heuristic with the learned utility (Eq. 6) choosing among feasible actions only',
          utilities=('qnet',)),
    # ---- not a Table I arm: offline-RL data collection (PROTOCOL Sec. 5.3), training routes only
    ArmV4('fl_behaviour', 'FrameLease behaviour policy (RL data)', 'shield', A3.V3_MODE, {}, dict(SHIELD_RUNTIME),
          LEASE_PARAMS_REL, 'fl_v3_heuristic', requires_utility=True,
          tunable={'envelope': 'as fl_heuristic (L*)', 'utility': 'v4_eps0.300_seed<s>[_d<d*>] (rl/collection_plan)'},
          description='fl_heuristic with the epsilon-random behaviour utility around a_det^d (logged propensities); '
                      'offline-RL data on training routes only',
          utilities=('behaviour',)),
)}
TABLE_I_ORDER = ('fixed_deep', 'fast_only', 'age_only', 'event_triggered', 'fl_original', 'fl_heuristic', 'fl_full')
EXTRA_ARMS = ('fl_behaviour',)
ALL_ARMS = TABLE_I_ORDER + EXTRA_ARMS
assert tuple(ARMS) == ALL_ARMS


def arm_id(arm, kappa, seed):
    return f'{arm}_k{float(kappa):.1f}_s{int(seed)}'


def _resolve(path):
    if path is None:
        return None
    p = Path(path)
    return (p if p.is_absolute() else ROOT / p).resolve()


# ============================================================================================ utility registration

def register_utility(name, registrar=DEFAULT_UTILITY_REGISTRAR):
    """Make the learned utility `name` available in framelease_v3.runtime.v3_shield.UTILITIES (owner's registrar)."""
    from framelease_v3.runtime import v3_shield as VS
    if name in VS.UTILITIES:
        return name
    if not registrar or ':' not in registrar:
        raise ValueError(f'utility {name!r} is not registered and no registrar "module:function" was given')
    mod_name, fn_name = registrar.split(':', 1)
    try:
        fn = getattr(importlib.import_module(mod_name), fn_name)
    except (ImportError, AttributeError) as e:
        raise ValueError(f'utility registrar {registrar!r} unavailable: {type(e).__name__}: {e}') from e
    fn(name)
    if name not in VS.UTILITIES:
        raise ValueError(f'registrar {registrar!r} did not register utility {name!r}')
    return name


def utility_kind(name):
    """Kind of a policy_params.utility value ('heuristic' | 'adet' | 'behaviour' | 'qnet'), or None if unknown.

    The name patterns are framelease_v4.rl.behaviour's (the default registrar); only canonical names are accepted
    (v4_adet_d<d> with d in 1..10, behaviour names that behaviour.parse_behaviour accepts)."""
    if name is None or name == 'heuristic':
        return 'heuristic'
    from framelease_v4.rl import behaviour as B
    name = str(name)
    m = B.ADET_RE.match(name)
    if m:
        d = int(m.group('d'))
        return 'adet' if 1 <= d <= B.MAX_DEPTH and name == B.adet_name(d) else None
    if B.parse_behaviour(name) is not None:
        return 'behaviour'
    if B.QNET_RE.match(name):
        return 'qnet'
    return None


def adet_depth(name):
    """d of a heuristic utility name: 'heuristic' (or None) -> 10, 'v4_adet_d<d>' -> d; anything else raises."""
    kind = utility_kind(name)
    if kind == 'heuristic':
        return SHIELD_MAX_DEPTH
    if kind != 'adet':
        raise ValueError(f'{name!r} is not a heuristic utility (heuristic | v4_adet_d<d>)')
    return int(str(name).rsplit('_d', 1)[1])


def arm_utility(arm, policy_params, utility_env=None):
    """(name, kind) of the utility an arm is configured with; raises if the arm does not accept it.

    v2-rule and event arms take no utility. Age and shield arms accept the kinds in arm.utilities; the heuristic
    depth is chosen through the utility name (v4_adet_d<d>), never through max_depth (checked by
    check_shield_depth). A utility environment (--utility-env) belongs to the Q-network utility only."""
    params = dict(policy_params or {})
    if arm.kind not in ('age', 'shield'):
        if 'utility' in params or utility_env:
            raise ValueError(f'{arm.name}: a utility applies to the age and shield arms only')
        return None, None
    name = params.get('utility')
    kind = utility_kind(name)
    allowed = ', '.join(arm.utilities)
    if arm.requires_utility and kind == 'heuristic':
        examples = {'qnet': 'v4_qnet_<sha12>', 'behaviour': 'v4_eps0.300_seed<s>[_d<d>]', 'adet': 'v4_adet_d<d>'}
        raise ValueError(f'{arm.name} needs policy_params.utility = a v4 utility of kind {allowed} '
                         f'({", ".join(examples.get(k, k) for k in arm.utilities)})')
    if kind is None:
        raise ValueError(f'{arm.name}: unknown utility {name!r} (kinds accepted here: {allowed})')
    if kind not in arm.utilities:
        raise ValueError(f'{arm.name}: utility {name!r} is of kind {kind!r}; this arm accepts {allowed} only'
                         + (' (the heuristic arm: a learned utility belongs to fl_full)' if arm.name == 'fl_heuristic'
                            else ''))
    if utility_env and kind != 'qnet':
        raise ValueError(f'{arm.name}: --utility-env applies to the Q-network utility only')
    return (None if name is None else str(name)), kind


def check_shield_depth(arm, policy_params=None, runtime_params=None):
    """The shield's C_REFINE depth limit is 10 in every age / shield arm (PROTOCOL Sec. 2.4): the heuristic depth d
    is a utility parameter (v4_adet_d<d>), so max_depth may not be used to tune it."""
    if arm.kind not in ('age', 'shield'):
        return
    for where, params in (('policy_params', policy_params), ('runtime', runtime_params)):
        if params and 'max_depth' in params and params['max_depth'] != SHIELD_MAX_DEPTH:
            raise ValueError(f'{arm.name}: {where}.max_depth = {params["max_depth"]!r}; the shield depth limit is '
                             f'{SHIELD_MAX_DEPTH} in every shield arm. Choose the heuristic depth d through '
                             f'policy_params.utility = "v4_adet_d<d>" instead')


def utility_block(name, registrar=DEFAULT_UTILITY_REGISTRAR, env=None):
    """{'name', 'registrar', 'env', 'env_files_sha256'} of a learned utility; env (e.g. FRAMELEASE_V4_QNET = the
    weights file the utility loads) is applied to this process (validation) and to the evaluator environment."""
    import os
    from framelease_common import file_hash
    env = {str(k): str(v) for k, v in dict(env or {}).items()}
    shas = {}
    for k, v in env.items():
        cur = os.environ.get(k)
        if cur is not None and cur != v:
            raise ValueError(f'environment {k}={cur!r} differs from the configured {v!r}')
        os.environ[k] = v
        if Path(v).is_file():
            shas[v] = file_hash(v)
    return {'name': str(name), 'registrar': registrar, 'env': env, 'env_files_sha256': shas}


# ============================================================================================ configuration

def _runtime(arm, kappa, overrides):
    overrides = dict(overrides or {})
    if 'kappa' in overrides and float(overrides['kappa']) != float(kappa):
        raise ValueError('kappa given twice with different values (--kappa and --runtime-params)')
    return la.RuntimeConfig.from_dict({'kappa': float(kappa), **arm.runtime, **overrides}).to_dict()


def build_config(arm_name, kappa=1.0, seed=11, policy_params=None, runtime_params=None, lease_params=None,
                 envelope=None, lease_overrides=None, utility_registrar=DEFAULT_UTILITY_REGISTRAR, utility_env=None,
                 fast_prefix=None, actor_log=None, routes=None, route_id='0', port=2700, output_dir='/tmp/unused'):
    """The agent configuration of one arm ({'schema', 'arm', 'kind', 'agent', ...}); validated by building the policy
    exactly as the agent will (CPU only, no model). Returns (config, lease_params_path or None, envelope_path or None).
    """
    from framelease_v2 import run_closed_loop as R2
    from framelease_v3.runtime import run_closed_loop_v3 as L
    from framelease_v4.arms import actor_log as AL
    arm = ARMS[arm_name]
    policy_params = dict(policy_params or {})
    lease_path = _resolve(lease_params) or _resolve(arm.lease_params)
    env_path = _resolve(envelope)
    if arm.kind in ('v2_rule', 'event') and (envelope is not None or lease_overrides):
        raise ValueError(f'{arm_name}: --envelope / --lease-overrides apply to the shield and age arms only')
    if arm.kind == 'age' and envelope is not None:
        raise ValueError('age_only: the constant-age lease uses no envelope')
    if arm.kind in ('v2_rule', 'event') and lease_params is not None and arm.lease_params is None:
        raise ValueError(f'{arm_name}: this arm uses no lease parameters')
    utility, ukind = arm_utility(arm, policy_params, utility_env)
    check_shield_depth(arm, policy_params, runtime_params)
    cfg = {'schema': SCHEMA, 'arm': arm.name, 'title': arm.title, 'kind': arm.kind, 'description': arm.description}
    if ukind in ('adet', 'behaviour', 'qnet'):
        # any v4 utility of an age / shield arm is registered here (launcher process) and again by build_policy in
        # the evaluator's agent process (cfg['utility'] names the registrar), before the policy is built
        cfg['utility'] = utility_block(utility, utility_registrar, utility_env)
        register_utility(utility, utility_registrar)
    if arm.kind == 'v2_rule':
        a3 = A3.ARMS[arm.v3_arm]
        runtime = {**(a3.runtime_params or {}), **dict(runtime_params or {})}
        argv = ['--policy', arm.policy, '--kappa', f'{float(kappa):.1f}', '--seed', str(int(seed))]
        if runtime:
            argv += ['--runtime-params', json.dumps(runtime, sort_keys=True)]
        if lease_path is not None:
            argv += ['--lease-params', str(lease_path)]
        if policy_params:
            argv += ['--policy-params', json.dumps(policy_params, sort_keys=True)]
        argv += ['--routes', str(routes or (ROOT / ROUTES_XML_REL)), '--route-id', str(route_id), '--port',
                 str(int(port)), '--output-dir', str(output_dir)]
        a2 = R2.parse_args(argv)
        a2.kappa = float(kappa)
        cfg['agent'] = R2.agent_config(a2)
        cfg['v2'] = {'lease_params_path': str(lease_path) if lease_path else None,
                     'lease_params_sha256': R2.file_hash(lease_path) if lease_path else None,
                     'lease_h_max_s': R2.lease_h_max(lease_path) if arm.policy == 'framelease' else None,
                     'reproduces_v3_arm': arm.v3_arm}
    elif arm.kind == 'event':
        params = PV.EventTriggeredV4(env=None, **policy_params).params
        cfg['agent'] = la.AgentConfig(mode=arm.policy, policy_params=_jsonable(params),
                                      runtime=_runtime(arm, kappa, runtime_params), seed=int(seed),
                                      lease_params_path=None, **AGENT_DEFAULTS).to_dict()
    elif arm.kind == 'age':
        from framelease_v3.runtime import v3_lease as VL
        lenv = VL.build_lease_env(str(lease_path), None, lease_overrides or None)
        pol = PV.AgeLeasePolicy(env=lenv, **policy_params)
        cfg['agent'] = la.AgentConfig(mode=arm.policy, policy_params=_jsonable(policy_params),
                                      runtime=_runtime(arm, kappa, runtime_params), seed=int(seed),
                                      lease_params_path=str(lease_path), **AGENT_DEFAULTS).to_dict()
        cfg['v3'] = {'lease_params_path': str(lease_path), 'lease_params_sha256': VL.sha256_file(lease_path),
                     'lease': dict(lease_overrides or {}), 'envelope_path': None, 'envelope_sha256': None,
                     'resolved': {'lease': lenv.cfg.to_dict(), 'policy_params': _jsonable(pol.params),
                                  'ego': lenv.ego.to_dict()}}
    elif arm.kind == 'shield':
        ns = _ns(arm=arm.v3_arm, lease_params=lease_path, envelope=env_path, lease_overrides=dict(lease_overrides or {}),
                 policy_params=policy_params, runtime_params={k: v for k, v in dict(runtime_params or {}).items()},
                 kappa=float(kappa), seed=int(seed))
        full, lease_path, env_path = L.v3_configs(ns)
        cfg['agent'], cfg['v3'] = full['agent'], full['v3']
    else:
        raise ValueError(f'unknown arm kind {arm.kind!r}')
    if fast_prefix is not None:
        cfg['fast_prefix'] = fast_prefix
    cfg['actor_log'] = AL.normalize_params(actor_log)
    validate_config(cfg)
    return cfg, lease_path, env_path


def _ns(**kw):
    from types import SimpleNamespace
    return SimpleNamespace(**kw)


def _jsonable(x):
    return json.loads(json.dumps(la.jsonable(x)))


# ============================================================================================ agent side

def agent_config_from(cfg):
    """la.AgentConfig of a v4 configuration (constructed directly: AgentConfig.from_dict accepts v2 modes only)."""
    from dataclasses import fields
    agent = dict(cfg['agent'])
    names = {f.name for f in fields(la.AgentConfig)}
    unknown = sorted(set(agent) - names)
    if unknown:
        raise ValueError(f'unknown agent config keys {unknown}')
    out = la.AgentConfig(**agent)
    arm = ARMS[cfg['arm']]
    if out.mode != arm.policy:
        raise ValueError(f'agent mode {out.mode!r} != arm policy {arm.policy!r}')
    if out.mode == 'oracle_sync':
        raise ValueError('oracle_sync is not a v4 arm')
    if out.temporal_mode not in ('latest', 'official') or out.precision not in ('bf16-autocast', 'official'):
        raise ValueError('bad temporal_mode / precision')
    la.RuntimeConfig.from_dict(out.runtime)
    if arm.kind == 'shield' and dict(out.policy_params or {}) != dict((cfg['v3'] or {}).get('policy_params') or {}):
        raise ValueError('agent.policy_params and v3.policy_params differ')
    if arm.kind in ('age', 'shield'):                     # the same rules as build_config, re-checked by the agent
        name, kind = arm_utility(arm, out.policy_params, (cfg.get('utility') or {}).get('env'))
        check_shield_depth(arm, out.policy_params, out.runtime)
        u = cfg.get('utility')
        if kind in ('adet', 'behaviour', 'qnet') and (not u or u.get('name') != name):
            raise ValueError(f'utility block missing or names another utility than policy_params.utility {name!r}')
        if kind == 'heuristic' and u:
            raise ValueError('a utility block without a v4 utility in policy_params')
    elif cfg.get('utility'):
        raise ValueError(f'{arm.name}: a utility block applies to the age and shield arms only')
    return out


def build_policy(cfg):
    """The policy object of an arm (identical construction in the launcher's validation and in the agent)."""
    from framelease_v3.runtime import v3_lease as VL
    from framelease_v3.runtime import v3_scheduler as S
    arm = ARMS[cfg['arm']]
    agent = cfg['agent']
    params = dict(agent.get('policy_params') or {})
    if arm.kind == 'v2_rule':
        env = P.default_policy_env(agent.get('lease_params_path'))
        return PV.logged_v2_class(arm.policy)(env=env, **params)
    if arm.kind == 'event':
        return PV.EventTriggeredV4(env=P.default_policy_env(None), **params)
    if arm.kind in ('age', 'shield') and cfg.get('utility'):
        # register the v4 utility (a_det^d, behaviour or Q-network) in THIS process before the policy is built: the
        # launcher's validation and the evaluator's agent process (agent_v4.setup_v4) both come through here
        u = cfg['utility']
        import os
        from framelease_common import file_hash
        for k, v in (u.get('env') or {}).items():
            if os.environ.get(k, v) != v:
                raise ValueError(f'environment {k} differs from the configured utility environment')
            os.environ[k] = v
        for path, sha in (u.get('env_files_sha256') or {}).items():
            if file_hash(path) != sha:
                raise ValueError(f'utility file {path} changed since the run was configured')
        register_utility(u['name'], u.get('registrar'))
    if arm.kind == 'age':
        v3 = cfg['v3']
        want = v3.get('lease_params_sha256')
        if want and VL.sha256_file(v3['lease_params_path']) != want:
            raise ValueError('lease parameter file changed since the run was configured')
        return PV.AgeLeasePolicy(env=VL.build_lease_env(v3['lease_params_path'], None, v3.get('lease') or None),
                                 **params)
    if arm.kind == 'shield':
        v3 = cfg['v3']
        want = v3.get('lease_params_sha256')
        if want and VL.sha256_file(v3['lease_params_path']) != want:
            raise ValueError('lease parameter file changed since the run was configured')
        return S.make_v3_policy(v3)
    raise ValueError(f'unknown arm kind {arm.kind!r}')


def normalize_fast_prefix(fp):
    """framelease_v3/fastprefix configuration checks (schema, options, fast_path.py sha256, upstream source contract)
    for a v4 fast-prefix block (base 'v4'; agent_entry.normalize_config accepts the v2 / v3 bases only)."""
    from framelease_v3.fastprefix import agent_entry as AE
    if not isinstance(fp, dict) or fp.get('base') not in ('v4', 'v3'):
        raise ValueError('fast-prefix block must be a v4 fast-prefix configuration')
    out = AE.normalize_config({**json.loads(json.dumps(fp)), 'base': 'v3'})
    out['base'] = 'v4'
    return out


def validate_config(cfg):
    if cfg.get('schema') != SCHEMA:
        raise ValueError(f'configuration schema {cfg.get("schema")!r} != {SCHEMA!r}')
    if cfg.get('arm') not in ARMS:
        raise ValueError(f'unknown arm {cfg.get("arm")!r}')
    if cfg.get('kind') != ARMS[cfg['arm']].kind:
        raise ValueError('arm kind mismatch')
    allowed = {'schema', 'arm', 'title', 'kind', 'description', 'agent', 'v2', 'v3', 'utility', 'fast_prefix',
               'actor_log'}
    unknown = sorted(set(cfg) - allowed)
    if unknown:
        raise ValueError(f'unknown configuration keys {unknown}')
    agent_config_from(cfg)
    if cfg.get('fast_prefix') is not None:
        normalize_fast_prefix(cfg['fast_prefix'])
    policy = build_policy(json.loads(json.dumps(cfg)))
    return policy


__all__ = ['SCHEMA', 'ArmV4', 'ARMS', 'TABLE_I_ORDER', 'EXTRA_ARMS', 'ALL_ARMS', 'NON_LEASE_MAX_AGE_S',
           'SHIELD_RUNTIME', 'SHIELD_MAX_DEPTH', 'UTILITY_KINDS', 'HEURISTIC_UTILITIES', 'DEFAULT_UTILITY_REGISTRAR',
           'arm_id', 'utility_kind', 'adet_depth', 'arm_utility', 'check_shield_depth', 'register_utility',
           'utility_block', 'build_config',
           'agent_config_from', 'build_policy', 'normalize_fast_prefix', 'validate_config']
