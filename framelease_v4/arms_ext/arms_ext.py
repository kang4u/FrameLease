"""Additive arm registry of framelease_v4/arms_ext: the Table II-A arm fl_global_shield on top of the pinned v4 arms.

PROTOCOL Secs. 4.1 (fl_global_shield: "as fl_heuristic, with the suffix lease replaced by the global-margin lease"),
7.4 (Table II-A lease panel, closed loop) and 8.3 (pins). CPU only.

  from framelease_v4.arms_ext import arms_ext as X
  X.register()                       # idempotent: X.ARMS = arms_v4.ARMS + the extension arms, X.ALL_ARMS likewise
  cfg, lease_params, envelope = X.build_config('fl_global_shield', envelope='outputs/framelease_v4/envelopes/E5.json',
                                               policy_params={'utility': 'v4_adet_d4'})
  policy = X.build_policy(cfg)       # GlobalMarginShieldPolicy (global_shield.py)

Nothing pinned is modified. The P1 jobs pin framelease_v4/arms/*.py and framelease_v3/runtime/*.py, so this module never
rebinds an attribute of a pinned module and never mutates a pinned object (arms_v4.ARMS, ALL_ARMS, build_policy,
agent_v4.ENTRY_*, run_closed_loop_v4.V4_CODE stay what they are; tested). Instead:
  * register() builds the extension's own registry ARMS = {**arms_v4.ARMS, 'fl_global_shield': ...} (the arms_v4 arm
    objects themselves, plus the new one) and ALL_ARMS = arms_v4.ALL_ARMS + ('fl_global_shield',);
  * build_config / agent_config_from / validate_config / build_policy below delegate every arms_v4 arm to the
    arms_v4 function of the same name, unchanged (the same call, the same result);
  * an extension arm runs through the same arms_v4 functions as its BASE ARM (fl_heuristic), on a relabelled view of
    its configuration (base_config: arm, title and description of the base arm, without the 'extension' block). This
    is exact because the new arm equals its base arm in every field those functions read (kind 'shield', policy
    'fl_v3_heuristic', runtime, lease parameter file, v3 arm, utility kinds 'heuristic' / 'adet', no required
    utility; register() checks it). So the shield runtime (max_age_s 2.5, profile_quantile 0.99, max_depth 10), the
    utility rules (heuristic = a_det^10 or v4_adet_d<d>; check_shield_depth), the v3 block (lease and envelope files
    with their sha256, SuffixLeaseConfig, policy parameters), the fast-prefix block, the actor log and the agent
    configuration are exactly fl_heuristic's;
  * the only differences: cfg['arm'] / 'title' / 'description' name the new arm, cfg['extension'] records the base arm
    and the global lease (global_shield.global_lease_spec: P, H_bar, delta, envelope sha256), and build_policy returns
    GlobalMarginShieldPolicy built on the LeaseEnv of the base arm's policy. That LeaseEnv comes from
    arms_v4.build_policy of the base view, i.e. after its utility registration and file checks, the lease-parameter
    sha256 check and v3_scheduler.make_v3_policy's envelope sha256 check (the agent refuses a changed E*); the
    recorded global lease must equal the rebuilt one.

The new arm needs an explicit --envelope (E*, PROTOCOL Sec. 4.3: every shield-arm job passes it and pins its sha256)
and accepts exactly fl_heuristic's utilities (a_det^{d*}: 'heuristic' or 'v4_adet_d<d>', Sec. 4.4; the shield depth
limit stays 10, Sec. 2.4). It is not tuned (Sec. 4.1: the shield, E* and d* of fl_heuristic). Unlike fl_heuristic it
refuses --lease-overrides: PROTOCOL Secs. 2.4 and 7.4 fix the lease constants (T_pred 3.0 s, T_c 0.5 s, d_safe 0.5 m,
delta 0.2 m, the 0.05 s grid, the detection rules) and the cap H_bar = 2.5 s of the global lease. build_config refuses
the overrides, and check_extension (launcher, agent_config_from and build_policy in the agent process) refuses a
configuration whose v3 block carries lease overrides or whose global lease has another cap (fixed_lease_problems;
run_closed_loop_ext.check_job_line checks the same on every job line).
"""
from __future__ import annotations

import contextlib
import json

from framelease_v3.runtime import v3_arms as A3
from framelease_v4.arms import arms_v4 as AV
from framelease_v4.arms_ext import global_shield as GS

SCHEMA = 'framelease_v4.arms_ext/1'
ROOT = AV.ROOT
PKG_REL = 'framelease_v4/arms_ext'
EXT_FILES = ('__init__.py', 'global_shield.py', 'arms_ext.py', 'agent_ext.py', 'run_closed_loop_ext.py')
EXT_CODE = tuple(f'{PKG_REL}/{f}' for f in EXT_FILES)        # every extension source a run imports (frozen, pinned)
GLOBAL_SHIELD = GS.NAME                                       # 'fl_global_shield'
BASE_ARMS = {GLOBAL_SHIELD: 'fl_heuristic'}                   # extension arm -> the arms_v4 arm it runs as
EXTENSION_KEY = 'extension'
# the ArmV4 fields the arms_v4 functions read; an extension arm must equal its base arm in all of them
DELEGATED_FIELDS = ('kind', 'policy', 'params', 'runtime', 'lease_params', 'v3_arm', 'requires_utility', 'utilities')

EXT_ARMS = {GLOBAL_SHIELD: AV.ArmV4(
    GLOBAL_SHIELD, 'Global-Margin lease (Table II-A)', 'shield', A3.V3_MODE, {}, dict(AV.SHIELD_RUNTIME),
    AV.LEASE_PARAMS_REL, 'fl_v3_heuristic', tunable={},
    description='fl_heuristic with the suffix lease replaced by the v2 global-margin lease (margin_mode global: per '
                'agent the minimum clearance over the whole plan [0, T_pred], E* as the staleness-indexed B(D), '
                'reserve delta 0.2 m, d_safe 0.5 m, cap H_bar 2.5 s); synthetic commit-time margin crossing delta at '
                'H; shield Eq. 5, a_det^{d*}, versioned commit Eq. 9, watchdog; not tuned (E*, d* of fl_heuristic)',
    utilities=AV.HEURISTIC_UTILITIES)}

ARMS = {}
ALL_ARMS = ()


def register():
    """Build (idempotent) and return the extension registry ARMS = arms_v4.ARMS + EXT_ARMS; ALL_ARMS likewise.

    Additive only: the arms_v4 entries are the arms_v4 objects, in arms_v4 order; arms_v4 itself is not touched. Raises
    if an extension arm clashes with an arms_v4 arm or differs from its base arm in a delegated field."""
    global ARMS, ALL_ARMS
    for name, arm in EXT_ARMS.items():
        if name in AV.ARMS:
            raise ValueError(f'extension arm {name!r} clashes with an arms_v4 arm')
        base = AV.ARMS[BASE_ARMS[name]]
        diff = [f for f in DELEGATED_FIELDS if getattr(arm, f) != getattr(base, f)]
        if diff:
            raise ValueError(f'extension arm {name!r} differs from its base arm {base.name!r} in {diff}')
    reg = dict(AV.ARMS)
    reg.update(EXT_ARMS)
    ARMS = reg
    ALL_ARMS = tuple(AV.ALL_ARMS) + tuple(EXT_ARMS)
    return ARMS


def is_extension(name):
    return name in EXT_ARMS


def base_arm(name):
    """The arms_v4 arm an arm runs as (itself for an arms_v4 arm)."""
    if name in AV.ARMS:
        return name
    if name in EXT_ARMS:
        return BASE_ARMS[name]
    raise ValueError(f'unknown arm {name!r}')


def base_config(cfg):
    """The view of an extension arm's configuration that the arms_v4 functions accept: arm, title and description of
    the base arm, without the extension block (every other key unchanged)."""
    name = cfg.get('arm')
    if not is_extension(name):
        return cfg
    base = AV.ARMS[BASE_ARMS[name]]
    out = {k: v for k, v in cfg.items() if k != EXTENSION_KEY}
    out.update(arm=base.name, title=base.title, description=base.description)
    return out


def _jsonable(x):
    return json.loads(json.dumps(x))


@contextlib.contextmanager
def _as_base(name):
    """ValueErrors of the arms_v4 functions name the base arm; prefix them with the extension arm."""
    try:
        yield
    except ValueError as e:
        raise ValueError(f'{name} (checked as its base arm {BASE_ARMS[name]}): {e}') from e


def extension_block(name, policy):
    return _jsonable({'schema': SCHEMA, 'arm': name, 'base_arm': BASE_ARMS[name], 'lease': 'global_margin',
                      'global_lease': policy.global_lease_spec()})


def fixed_lease_problems(cfg):
    """Departures of an extension arm's configuration from the fixed lease constants (PROTOCOL Secs. 2.4, 7.4); empty
    if none: the v3 block carries no lease overrides (cfg['v3']['lease'] == {}, so the LeaseEnv constants are the
    SuffixLeaseConfig defaults) and the global lease's cap is GS.H_BAR_S = 2.5 s."""
    problems = []
    lease = (cfg.get('v3') or {}).get('lease')
    if lease != {}:
        problems.append(f"lease overrides {lease!r} in the v3 block (cfg['v3']['lease'] must be {{}}: PROTOCOL Secs. "
                        '2.4, 7.4 fix the lease constants)')
    h_bar = ((cfg.get(EXTENSION_KEY) or {}).get('global_lease') or {}).get('h_bar_s')
    if h_bar != GS.H_BAR_S:
        problems.append(f'global lease cap h_bar_s {h_bar!r} != {GS.H_BAR_S} s (PROTOCOL Secs. 2.4, 7.4)')
    return problems


def check_extension(cfg):
    """Raise unless cfg is an extension arm's configuration with a consistent extension block, an explicit E* and the
    fixed lease constants (fixed_lease_problems)."""
    name = cfg.get('arm')
    if not is_extension(name):
        raise ValueError(f'{name!r} is not an extension arm')
    if cfg.get('schema') != AV.SCHEMA:
        raise ValueError(f'configuration schema {cfg.get("schema")!r} != {AV.SCHEMA!r}')
    if cfg.get('kind') != EXT_ARMS[name].kind:
        raise ValueError('arm kind mismatch')
    ext = cfg.get(EXTENSION_KEY)
    if not isinstance(ext, dict) or ext.get('schema') != SCHEMA or ext.get('arm') != name \
            or ext.get('base_arm') != BASE_ARMS[name] or not isinstance(ext.get('global_lease'), dict):
        raise ValueError(f'{name}: missing or inconsistent {EXTENSION_KEY!r} block')
    v3 = cfg.get('v3') or {}
    if not v3.get('envelope_path') or not v3.get('envelope_sha256'):
        raise ValueError(f'{name}: the global-margin lease needs an explicit envelope E* (--envelope)')
    if ext['global_lease'].get('envelope_sha256') != v3['envelope_sha256']:
        raise ValueError(f'{name}: the global lease and the v3 block name different envelopes')
    bad = fixed_lease_problems(cfg)
    if bad:
        raise ValueError(f'{name}: ' + '; '.join(bad))
    return ext


# ============================================================================================ arms_v4 API, extended

def build_config(arm_name, **kw):
    """arms_v4.build_config for every arms_v4 arm (unchanged); for an extension arm: the base arm's configuration
    (all of arms_v4's checks), relabelled, with the extension block, validated by building the new policy. An
    extension arm refuses lease overrides (the lease constants are fixed, PROTOCOL Secs. 2.4, 7.4)."""
    if not is_extension(arm_name):
        return AV.build_config(arm_name, **kw)
    if kw.get('envelope') is None:
        raise ValueError(f'{arm_name}: the global-margin lease needs an explicit envelope E* (--envelope)')
    if kw.get('lease_overrides'):
        raise ValueError(f'{arm_name}: --lease-overrides are refused: PROTOCOL Secs. 2.4 and 7.4 fix the lease '
                         f'constants (T_pred 3.0 s, T_c 0.5 s, d_safe 0.5 m, delta 0.2 m, H_bar {GS.H_BAR_S} s); got '
                         f'{kw["lease_overrides"]!r}')
    with _as_base(arm_name):
        cfg, lease_path, env_path = AV.build_config(BASE_ARMS[arm_name], **kw)
    arm = EXT_ARMS[arm_name]
    cfg = dict(cfg)
    cfg.update(arm=arm.name, title=arm.title, description=arm.description)
    with _as_base(arm_name):
        base_policy = AV.build_policy(_jsonable(base_config(cfg)))
    cfg[EXTENSION_KEY] = extension_block(arm_name, GS.GlobalMarginShieldPolicy(
        env=base_policy.env, **dict((cfg['v3'] or {}).get('policy_params') or {})))
    validate_config(cfg)
    return cfg, lease_path, env_path


def agent_config_from(cfg):
    """arms_v4.agent_config_from; an extension arm is checked exactly as its base arm (plus its extension block)."""
    if not is_extension(cfg.get('arm')):
        return AV.agent_config_from(cfg)
    check_extension(cfg)
    with _as_base(cfg['arm']):
        return AV.agent_config_from(base_config(cfg))


def build_policy(cfg):
    """arms_v4.build_policy; for an extension arm the new policy class only, built on the LeaseEnv that
    arms_v4.build_policy builds for the base view (utility registration and checks, lease-parameter sha256,
    make_v3_policy's envelope sha256 check)."""
    name = cfg.get('arm')
    if not is_extension(name):
        return AV.build_policy(cfg)
    ext = check_extension(cfg)
    with _as_base(name):
        base = AV.build_policy(base_config(cfg))
    policy = GS.GlobalMarginShieldPolicy(env=base.env, **dict((cfg['v3'] or {}).get('policy_params') or {}))
    if _jsonable(policy.global_lease_spec()) != ext['global_lease']:
        raise ValueError(f'{name}: the global-lease parameters differ from the configured ones (envelope or lease '
                         'constants changed since the run was configured)')
    return policy


def validate_config(cfg):
    """arms_v4.validate_config; for an extension arm: every arms_v4 check on the base view (schema, keys, agent
    configuration, fast prefix, base policy), the extension block, then the new policy is built and returned."""
    name = cfg.get('arm')
    if not is_extension(name):
        return AV.validate_config(cfg)
    allowed = {'schema', 'arm', 'title', 'kind', 'description', 'agent', 'v2', 'v3', 'utility', 'fast_prefix',
               'actor_log', EXTENSION_KEY}
    unknown = sorted(set(cfg) - allowed)
    if unknown:
        raise ValueError(f'unknown configuration keys {unknown}')
    check_extension(cfg)
    with _as_base(name):
        AV.validate_config(_jsonable(base_config(cfg)))
    agent_config_from(cfg)
    return build_policy(_jsonable(cfg))


register()

__all__ = ['SCHEMA', 'PKG_REL', 'EXT_FILES', 'EXT_CODE', 'GLOBAL_SHIELD', 'BASE_ARMS', 'EXT_ARMS', 'ARMS', 'ALL_ARMS',
           'DELEGATED_FIELDS', 'register', 'is_extension', 'base_arm', 'base_config', 'extension_block',
           'fixed_lease_problems', 'check_extension', 'build_config', 'agent_config_from', 'build_policy',
           'validate_config']
