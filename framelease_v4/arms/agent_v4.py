"""Evaluator agent of every v4 arm (framelease_v4/arms): ONE agent class for all seven Table I arms.

FrameLeaseV4Agent = framelease_v2.latency_agent FrameLeaseLatencyAgent (unchanged: official sensing and preprocessing,
lazy prefix / flow-step backend timed with CUDA events, re-anchored PID tracking, logged full-brake fallback,
metric_info, summary.json) with
  1. setup(): setup_v4 builds the arm's policy (arms_v4.build_policy) and the common runtime (runtime_v4.V4Runtime)
     from $FRAMELEASE_V4_ARMS_CONFIG, in the same order and with the same attributes as the v2 / v3 setups; then the
     fast prefix is applied to the loaded model exactly as framelease_v3/fastprefix does
     (agent_entry.install_fast_prefix, validation inside the discarded warm-up); then the evaluation-only actor log
     (actor_log.ActorBoxLogger) is attached;
  2. run_step(): the base run_step, then (after the control of the tick is computed) one actor-log row;
  3. destroy(): the last actor-log chunk is flushed before the base destroy writes summary.json (which then carries an
     'actor_log' block); the actor-log manifest is written after it.
The actor log never feeds anything back: the policy, the runtime and the controller hold no reference to it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from framelease_v2 import latency_agent as la

ENV_V4_CONFIG = 'FRAMELEASE_V4_ARMS_CONFIG'
FOREIGN_CONFIG_ENVS = ('FRAMELEASE_V2_RUNTIME_CONFIG', 'FRAMELEASE_V3_RUNTIME_CONFIG', 'FRAMELEASE_FASTPREFIX_CONFIG')


def load_v4_config(path=None):
    from framelease_v4.arms import arms_v4 as AV
    path = path or os.environ.get(ENV_V4_CONFIG)
    if not path:
        raise RuntimeError(f'{ENV_V4_CONFIG} is not set; run through framelease_v4/arms/run_closed_loop_v4.py')
    cfg = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(cfg, dict) or cfg.get('schema') != AV.SCHEMA:
        raise ValueError(f'{path}: not a {AV.SCHEMA} configuration')
    return cfg


def setup_v4(agent, path_to_conf_file, official_setup, backend_factory=None):
    """The v4 counterpart of FrameLeaseLatencyAgent.setup / v3 setup_v3: same order and attributes, any arm."""
    from framelease_v4.arms import arms_v4 as AV
    from framelease_v4.arms import runtime_v4 as RV
    full = load_v4_config()
    agent._fl_v4_cfg = full
    agent._fl_cfg = AV.agent_config_from(full)
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
    agent._fl_actor_log = None
    policy = AV.build_policy(full)
    agent._fl_backend = (backend_factory or la.UniDriveFlowBackend)(agent, agent._fl_cfg)
    agent._fl_runtime = RV.V4Runtime(agent._fl_backend, policy, la.RuntimeConfig.from_dict(agent._fl_cfg.runtime),
                                     agent._fl_logger)
    row = {'agent_config': agent._fl_cfg.to_dict(), 'v4': full, 'save_name': getattr(agent, 'save_name', None),
           'evidence': 'CARLA_CLOSED_LOOP REAL_VLA REAL_GPU VIRTUAL_TIME_MEASURED_LATENCY FRAMELEASE_V4_ARMS',
           'ground_truth_use': 'metric_info (hero state) and the actor log (actors near the hero) are recorded for '
                               'evaluation only; they never feed the model, the policy, the lease, the shield or the '
                               'controller',
           'policy': policy.describe(), 'runtime': agent._fl_runtime.config.to_dict(),
           'runtime_class': type(agent._fl_runtime).__name__}
    (agent._fl_dir / 'agent_config.json').write_text(json.dumps(la.jsonable(row), indent=1, sort_keys=True))
    return full


def install_actor_log(agent, params, world_fn=None):
    """Attach the evaluation-only actor log; summary.json gets an 'actor_log' block (runtime instance attribute)."""
    from framelease_v4.arms import actor_log as AL
    logger = AL.ActorBoxLogger(agent._fl_dir, params, world_fn=world_fn,
                               hero_fn=lambda: getattr(agent, 'hero_actor', None))
    agent._fl_actor_log = logger
    runtime = agent._fl_runtime
    original_summary = runtime.summary

    def summary():
        s = original_summary()
        s['actor_log'] = logger.status()
        return s
    runtime.summary = summary                       # instance attribute; adds a key, changes no value
    return logger


def build_agent_class(world_fn=None, backend_factory=None):
    """FrameLeaseV4Agent (imports torch / carla / the official agent; built only inside the evaluator process)."""
    import team_code.unidrivevla_b2d_agent as official
    from framelease_v3.fastprefix import agent_entry as AE
    Base = la._build_agent_class()

    class FrameLeaseV4Agent(Base):
        """framelease_v2 latency agent + v4 setup (any arm, V4Runtime) + fast prefix + evaluation-only actor log."""

        def setup(self, path_to_conf_file):
            from framelease_v4.arms import arms_v4 as AV
            full = setup_v4(self, path_to_conf_file, official.UniDriveVLAB2DAgent.setup, backend_factory)
            fp = full.get('fast_prefix')
            if fp is not None:                      # re-checked here: fast_path.py and upstream sources unchanged
                AE.install_fast_prefix(self, AV.normalize_fast_prefix(fp))
            install_actor_log(self, full.get('actor_log'), world_fn)

        def run_step(self, input_data, timestamp):
            control = Base.run_step(self, input_data, timestamp)
            log = getattr(self, '_fl_actor_log', None)
            if log is not None:                     # evaluation only, after the control of this tick exists
                rt = self._fl_runtime
                newest = rt._obs[-1] if rt is not None and rt._obs else None
                est = newest.lidar2global if newest is not None and newest.obs_id == self.step else None
                log.tick(self.step, float(timestamp), est)
            return control

        def destroy(self):
            log = getattr(self, '_fl_actor_log', None)
            try:
                if log is not None:
                    log.flush()                     # final numbers in summary.json['actor_log']
                Base.destroy(self)
            finally:
                if log is not None:
                    log.close()

    return FrameLeaseV4Agent


def get_entry_point():
    """Evaluator hook (the class is built only inside the evaluator process)."""
    cls = build_agent_class()
    globals()[cls.__name__] = cls
    return cls.__name__


ENTRY_NAME = 'framelease_v4_arms_agent_entry.py'
ENTRY_SOURCE = '''"""Evaluator agent entry generated by framelease_v4/arms/run_closed_loop_v4.py.

The evaluator puts this file's directory first on sys.path; keeping the entry outside the packages avoids shadowing.
"""
from framelease_v4.arms import agent_v4 as _impl


def get_entry_point():
    name = _impl.get_entry_point()
    globals()[name] = getattr(_impl, name)
    return name
'''

__all__ = ['ENV_V4_CONFIG', 'FOREIGN_CONFIG_ENVS', 'load_v4_config', 'setup_v4', 'install_actor_log',
           'build_agent_class', 'get_entry_point', 'ENTRY_NAME', 'ENTRY_SOURCE']
