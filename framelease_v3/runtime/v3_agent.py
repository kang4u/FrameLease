"""Evaluator agent of the v3 arm (fl_v3_heuristic): framelease_v2's latency agent with a v3 setup().

Everything the agent does per tick (official sensing and preprocessing, the lazy prefix / flow-step backend, the
re-anchored PID tracking, the logged full-brake fallback, metric_info, summary.json) is inherited unchanged from
framelease_v2.latency_agent's FrameLeaseLatencyAgent; only setup() differs: it builds V3Runtime +
ShieldedHeuristicPolicy from $FRAMELEASE_V3_RUNTIME_CONFIG instead of the v2 runtime and a v2 policy. Baseline arms
never use this module: run_closed_loop_v3.py runs them through the unchanged v2 launcher and agent entry.
"""
from __future__ import annotations

import json
import os
from dataclasses import fields
from pathlib import Path

from framelease_v2 import latency_agent as la

ENV_V3_CONFIG = 'FRAMELEASE_V3_RUNTIME_CONFIG'


def load_v3_config(path=None):
    path = path or os.environ.get(ENV_V3_CONFIG)
    if not path:
        raise RuntimeError(f'{ENV_V3_CONFIG} is not set; run through framelease_v3/runtime/run_closed_loop_v3.py')
    cfg = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(cfg, dict) or 'agent' not in cfg or 'v3' not in cfg:
        raise ValueError(f'{path}: expected {{"agent": ..., "v3": ...}}')
    return cfg


def agent_config_from(cfg):
    """v2 AgentConfig for a v3 mode (constructed directly: AgentConfig.from_dict accepts v2 modes only)."""
    from framelease_v3.runtime.v3_scheduler import V3_MODES
    agent = dict(cfg['agent'])
    if agent.get('mode') not in V3_MODES:
        raise ValueError(f'the v3 agent entry runs only {V3_MODES}; baseline arms use the unchanged v2 agent entry')
    names = {f.name for f in fields(la.AgentConfig)}
    unknown = sorted(set(agent) - names)
    if unknown:
        raise ValueError(f'unknown agent config keys {unknown}')
    out = la.AgentConfig(**agent)
    if out.temporal_mode not in ('latest', 'official') or out.precision not in ('bf16-autocast', 'official'):
        raise ValueError('bad temporal_mode / precision')
    la.RuntimeConfig.from_dict(out.runtime)
    v3_params = (cfg['v3'] or {}).get('policy_params') or {}
    if dict(out.policy_params or {}) != dict(v3_params):
        raise ValueError('agent.policy_params and v3.policy_params differ')
    return out


def setup_v3(agent, path_to_conf_file, official_setup, backend_factory=None):
    """The v3 counterpart of FrameLeaseLatencyAgent.setup: same order and attributes, v3 runtime and policy.

    official_setup: UniDriveVLAB2DAgent.setup (model, sensors, PID); backend_factory(agent, cfg) defaults to v2's
    UniDriveFlowBackend (injectable for the CPU tests only)."""
    from framelease_v3.runtime.v3_scheduler import V3Runtime, make_v3_policy
    full = load_v3_config()
    agent._fl_cfg = agent_config_from(full)
    official_setup(agent, path_to_conf_file)
    from stage02_real_vla import install_unidrive_command_prompt
    install_unidrive_command_prompt(agent.model.planning_head, agent._fl_cfg.prompt_command)
    agent._fl_dir = Path(os.environ['SAVE_PATH']) / agent._fl_cfg.log_subdir
    agent._fl_dir.mkdir(parents=True, exist_ok=True)
    agent._fl_logger = la.JsonlLogger(agent._fl_dir)
    agent._fl_metric_info = {}
    agent._fl_oracle_cuda = []
    agent._fl_oracle_ticks = 0
    agent._fl_warm = not agent._fl_cfg.warmup
    agent._fl_last_t = None
    agent._fl_runtime = None
    agent._fl_backend = None
    policy = make_v3_policy(full['v3'])
    agent._fl_backend = (backend_factory or la.UniDriveFlowBackend)(agent, agent._fl_cfg)
    agent._fl_runtime = V3Runtime(agent._fl_backend, policy, la.RuntimeConfig.from_dict(agent._fl_cfg.runtime),
                                  agent._fl_logger)
    row = {'agent_config': agent._fl_cfg.to_dict(), 'v3': full['v3'], 'save_name': getattr(agent, 'save_name', None),
           'evidence': 'CARLA_CLOSED_LOOP REAL_VLA REAL_GPU VIRTUAL_TIME_MEASURED_LATENCY FRAMELEASE_V3',
           'ground_truth_use': 'metric_info (hero state) is recorded for the official Bench2Drive metrics only; it '
                               'never feeds the model, the lease, the shield or the controller',
           'policy': policy.describe(), 'runtime': agent._fl_runtime.config.to_dict()}
    (agent._fl_dir / 'agent_config.json').write_text(json.dumps(la.jsonable(row), indent=1, sort_keys=True))


def build_v3_agent_class():
    """FrameLeaseV3Agent: the v2 FrameLeaseLatencyAgent class with setup() replaced (imports torch / carla)."""
    import team_code.unidrivevla_b2d_agent as official
    base = la._build_agent_class()

    class FrameLeaseV3Agent(base):
        """framelease_v2 latency agent; setup() builds the v3 runtime (fl_v3_heuristic)."""

        def setup(self, path_to_conf_file):
            setup_v3(self, path_to_conf_file, official.UniDriveVLAB2DAgent.setup)

    return FrameLeaseV3Agent


def get_entry_point():
    """Evaluator hook (the class is built only inside the evaluator process: torch / carla / mmcv imports)."""
    cls = build_v3_agent_class()
    globals()[cls.__name__] = cls
    return cls.__name__


__all__ = ['ENV_V3_CONFIG', 'load_v3_config', 'agent_config_from', 'setup_v3', 'build_v3_agent_class',
           'get_entry_point']
