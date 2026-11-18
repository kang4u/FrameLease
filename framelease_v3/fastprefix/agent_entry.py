"""Evaluator agent of the fast-prefix arms (framelease_v3/fastprefix; R&D sprint 2026-11-10, not for DAC 2027).

The agent class is the UNCHANGED closed-loop agent of the base arm, subclassed only to apply the fast prefix at the
end of setup():
  base 'v2'  framelease_v2.latency_agent FrameLeaseLatencyAgent (v2 policies: fast_only, fixed_deep, framelease, ...),
             configured by $FRAMELEASE_V2_RUNTIME_CONFIG exactly as under framelease_v2/run_closed_loop.py;
  base 'v3'  framelease_v3.runtime.v3_agent FrameLeaseV3Agent (fl_v3_heuristic), configured by
             $FRAMELEASE_V3_RUNTIME_CONFIG exactly as under framelease_v3/runtime/run_closed_loop_v3.py.
$FRAMELEASE_FASTPREFIX_CONFIG names the fast-prefix configuration (framelease_v3/fastprefix/run_closed_loop_fast.py
writes it to raw/fast_prefix_config.json).

What install_fast_prefix() adds after the base setup (model loaded, backend and runtime built):
  * fast_path.apply_fast_prefix(agent.model.planning_head, options) -> SDPA dispatcher / exact GPU preprocessing /
    merged LoRA on the loaded model;
  * <SAVE_PATH>/framelease/fast_prefix.json: what is active, upstream source hashes, versions, later the validation and
    the call statistics (written at setup, after the warm-up and at destroy);
  * the backend's warm-up (one discarded prefix + 10 steps on the first frame, never on the simulated timeline) runs
    inside fast_path's validation window: GPU preprocessing bit-equal to the CPU processor on that frame, selected
    SDPA calls close to the original eager attention; a failure raises (default) or is only recorded;
  * summary.json gets a 'fast_prefix' block (active options, validation result, call statistics).
Nothing else changes: per tick, the unchanged v2 backend runs the (now faster) prefix and flow steps lazily, times them
with CUDA events, and the unchanged v2 / v3 runtime charges kappa x the measured cost to the simulated timeline.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ENV_FASTPREFIX_CONFIG = 'FRAMELEASE_FASTPREFIX_CONFIG'
CONFIG_SCHEMA = 'framelease_v3.fastprefix_config/1'
MANIFEST_SCHEMA = 'framelease_v3.fastprefix_agent/1'
MANIFEST_NAME = 'fast_prefix.json'
BASES = ('v2', 'v3')
ON_FAILURE = ('raise', 'record')


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def normalize_config(cfg):
    """Validated copy of a fast-prefix configuration dict (raises ValueError)."""
    from framelease_v3.fastprefix import fast_path as FP
    if not isinstance(cfg, dict):
        raise ValueError('fast-prefix configuration must be a JSON object')
    if cfg.get('schema') != CONFIG_SCHEMA:
        raise ValueError(f'fast-prefix configuration schema {cfg.get("schema")!r} != {CONFIG_SCHEMA!r}')
    allowed = {'schema', 'base', 'options', 'validate', 'on_validation_failure', 'strict_sources', 'fast_path_sha256',
               'expected_upstream_sha256', 'arm', 'base_arm'}
    unknown = sorted(set(cfg) - allowed)
    if unknown:
        raise ValueError(f'unknown fast-prefix configuration keys {unknown}')
    out = dict(cfg)
    if out.get('base') not in BASES:
        raise ValueError(f'base must be one of {BASES}')
    out['options'] = list(FP.parse_options(out.get('options', 'all')))
    out['validate'] = bool(out.get('validate', True))
    out['on_validation_failure'] = out.get('on_validation_failure', 'raise')
    if out['on_validation_failure'] not in ON_FAILURE:
        raise ValueError(f'on_validation_failure must be one of {ON_FAILURE}')
    out['strict_sources'] = bool(out.get('strict_sources', True))
    want = out.get('fast_path_sha256')
    if want is not None and want != _sha256(FP.__file__):
        raise ValueError('framelease_v3/fastprefix/fast_path.py changed since the run was configured')
    exp = out.get('expected_upstream_sha256')
    if exp is not None and exp != FP.UPSTREAM_SOURCE_SHA256:
        raise ValueError('the configured upstream source contract differs from fast_path.UPSTREAM_SOURCE_SHA256')
    return out


def load_fastprefix_config(path=None):
    path = path or os.environ.get(ENV_FASTPREFIX_CONFIG)
    if not path:
        raise RuntimeError(f'{ENV_FASTPREFIX_CONFIG} is not set; run through framelease_v3/fastprefix/'
                           'run_closed_loop_fast.py')
    return normalize_config(json.loads(Path(path).read_text(encoding='utf-8')))


def _jsonable(x):
    from framelease_v2.latency_agent import jsonable
    return jsonable(x)


def install_fast_prefix(agent, fp_cfg, apply_fn=None):
    """Apply the fast prefix to a set-up agent (end of setup()); returns the fast_path.FastPrefix handle."""
    from framelease_v3.fastprefix import fast_path as FP
    apply_fn = apply_fn or FP.apply_fast_prefix
    handle = apply_fn(agent.model.planning_head, tuple(fp_cfg['options']), strict_sources=fp_cfg['strict_sources'])
    agent._fl_fastprefix = handle
    out_dir = Path(agent._fl_dir)
    backend = getattr(agent, '_fl_backend', None)
    runtime = getattr(agent, '_fl_runtime', None)
    agent_cfg = getattr(agent, '_fl_cfg', None)
    state = {'stage': 'applied_at_setup', 'validation_note': None}

    def write_manifest():
        row = {'schema': MANIFEST_SCHEMA, 'stage': state['stage'], 'config': fp_cfg,
               'agent_class': type(agent).__name__,
               'base_agent_class': type(agent).__mro__[1].__name__ if len(type(agent).__mro__) > 1 else None,
               'validation_note': state['validation_note'], 'fast_prefix': handle.manifest(),
               'stats': handle.stats()}
        tmp = out_dir / (MANIFEST_NAME + '.tmp')
        tmp.write_text(json.dumps(_jsonable(row), indent=1, sort_keys=True), encoding='utf-8')
        os.replace(tmp, out_dir / MANIFEST_NAME)

    if not fp_cfg['validate']:
        state['validation_note'] = 'validation disabled by the configuration'
    elif backend is None:
        state['validation_note'] = 'no latency backend (oracle_sync): not validated'
    elif agent_cfg is not None and not agent_cfg.warmup:
        state['validation_note'] = ('agent warm-up disabled: not validated (the validation never runs on the simulated '
                                    'timeline)')
    else:
        original_warmup = backend.warmup

        def warmup(obs):
            with handle.validation_window():
                info = original_warmup(obs)
            info = dict(info)
            val = handle.validation or {}
            info['fast_prefix_validation_ok'] = bool(val.get('ok'))
            info['fast_prefix_validation_failures'] = list(val.get('failures') or [])
            state['stage'] = 'validated_in_warmup'
            write_manifest()
            if not val.get('ok') and fp_cfg['on_validation_failure'] == 'raise':
                handle.raise_if_invalid()
            return info
        backend.warmup = warmup                      # instance attribute; the class method is untouched
    if runtime is not None:
        original_summary = runtime.summary

        def summary():
            s = original_summary()
            val = handle.validation or {}
            s['fast_prefix'] = {'options': list(handle.options), 'active': handle.active,
                                'validated': handle.validation is not None, 'validation_ok': val.get('ok'),
                                'validation_failures': val.get('failures'), 'validation_note': state['validation_note'],
                                'stats': handle.stats(), 'manifest': MANIFEST_NAME}
            state['stage'] = 'final'
            write_manifest()
            return s
        runtime.summary = summary                    # instance attribute; adds a key, changes no value
    write_manifest()
    return handle


def build_agent_class(base):
    """The base arm's agent class with setup() extended by install_fast_prefix (imports torch / carla / mmcv)."""
    if base == 'v3':
        from framelease_v3.runtime import v3_agent
        Base = v3_agent.build_v3_agent_class()
        name = 'FrameLeaseFastPrefixV3Agent'
    elif base == 'v2':
        from framelease_v2 import latency_agent as la
        Base = la._build_agent_class()
        name = 'FrameLeaseFastPrefixV2Agent'
    else:
        raise ValueError(f'base must be one of {BASES}')

    def setup(self, path_to_conf_file):
        fp_cfg = load_fastprefix_config()
        if fp_cfg['base'] != base:
            raise ValueError(f'fast-prefix configuration is for base {fp_cfg["base"]!r}, agent class for {base!r}')
        Base.setup(self, path_to_conf_file)
        install_fast_prefix(self, fp_cfg)

    return type(name, (Base,), {'setup': setup, '__module__': __name__,
                                '__doc__': f'{Base.__name__} + fast prefix applied at the end of setup()'})


def get_entry_point():
    """Evaluator hook (the class is built only inside the evaluator process)."""
    cls = build_agent_class(load_fastprefix_config()['base'])
    globals()[cls.__name__] = cls
    return cls.__name__


__all__ = ['ENV_FASTPREFIX_CONFIG', 'CONFIG_SCHEMA', 'MANIFEST_NAME', 'normalize_config', 'load_fastprefix_config',
           'install_fast_prefix', 'build_agent_class', 'get_entry_point']
