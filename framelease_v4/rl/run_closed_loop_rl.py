#!/usr/bin/env python3
"""Run one Bench2Drive route with the v3 runtime + fast prefix and a framelease_v4 utility (behaviour policy for
data collection, or a learned Q-network), e.g.

  cd /home/kang/Desktop/DAC && source linux/env.sh && .conda-unidrive-linux/bin/python -B \
      framelease_v4/rl/run_closed_loop_rl.py --utility v4_eps0.300_seed12345 \
      --arm fl_v3_heuristic --route-id 18305 --kappa 1.0 --seed 11 --port 2905 \
      --output-dir outputs/framelease_v4/rl_dev/adhoc --dry-run
  ... --utility v4_qnet_<sha12> --qnet path/to/qnet.json ...

Everything is the UNCHANGED fast-prefix launcher (framelease_v3/fastprefix/run_closed_loop_fast.py, which reuses the
v3 and v2 launchers): its run() executes with these in-process substitutions only (module attributes of that
launcher, restored afterwards; no file is edited):
  * v3.policy_params.utility = the v4 utility name (registered in v3_shield.UTILITIES in this process before the v3
    configuration is validated, and in the evaluator by the agent entry);
  * the evaluator loads raw/framelease_v4_rl_agent_entry.py (framelease_v4.rl.agent_entry: registers the utility,
    then the unchanged fast-prefix v3 agent runs);
  * v4 RL sources are frozen under raw/source_v4/ (with the Q-network JSON, whose path the evaluator gets as
    $FRAMELEASE_V4_QNET) and added to the run's code dependencies; the arm label is fl_v4_<utility>_fp.
Only the fl_v3_heuristic arm is accepted (the utility is a v3-shield component). --dry-run validates everything on
the CPU and prints the evaluator command; it starts nothing. This tool never enqueues jobs.
"""
from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v4.rl import agent_entry as AE  # noqa: E402
from framelease_v4.rl import behaviour as B  # noqa: E402
from framelease_v4.rl import common as C  # noqa: E402
from framelease_v4.rl import qnet as Q  # noqa: E402

STAGE = 'framelease_v4/rl/run_closed_loop_rl'
V4_CODE = ('framelease_v4/__init__.py', 'framelease_v4/rl/__init__.py', 'framelease_v4/rl/common.py',
           'framelease_v4/rl/features.py', 'framelease_v4/rl/behaviour.py', 'framelease_v4/rl/qnet.py',
           'framelease_v4/rl/agent_entry.py', 'framelease_v4/rl/run_closed_loop_rl.py')
QNET_FROZEN = 'qnet.json'


def utility_tag(name):
    if B.parse_behaviour_name(name):
        eps, _ = B.parse_behaviour_name(name)
        return f'eps{eps:.3f}'
    return name[len('v4_'):]


def parse_args(argv=None):
    from framelease_v3.fastprefix import run_closed_loop_fast as FL
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], allow_abbrev=False)
    p.add_argument('--utility', required=True, help='v4 utility name: v4_eps<eps>_seed<seed> or v4_qnet_<sha12>')
    p.add_argument('--qnet', type=Path, default=None, help='Q-network JSON (required for v4_qnet_* utilities)')
    mine, rest = p.parse_known_args(argv)
    if not str(mine.utility).startswith(B.PREFIX):
        p.error('--utility must be a framelease_v4 utility name')
    if B.QNET_RE.match(mine.utility):
        if mine.qnet is None:
            p.error('--qnet is required for a v4_qnet_* utility')
        spec = Q.load_spec(mine.qnet)
        if spec['name'] != mine.utility:
            p.error(f'--qnet holds {spec["name"]}, not {mine.utility}')
        mine.qnet = mine.qnet.resolve()
    elif mine.qnet is not None:
        p.error('--qnet only applies to v4_qnet_* utilities')
    if '--policy-params' in rest:
        p.error('--policy-params is set by this launcher (utility); other policy parameters are not supported')
    own, base = FL.parse_args(rest)
    if base.arm != 'fl_v3_heuristic':
        p.error('only --arm fl_v3_heuristic takes a v4 utility')
    base.policy_params = {**(base.policy_params or {}), 'utility': mine.utility}
    return mine, own, base


@contextlib.contextmanager
def v4_substitutions(mine):
    """Patch the fast-prefix launcher's module attributes for one run() call; always restored."""
    from framelease_v3.fastprefix import run_closed_loop_fast as FL
    saved = {k: getattr(FL, k) for k in ('STAGE', 'ENTRY_NAME', 'ENTRY_SOURCE', 'arm_label', 'evaluator_env',
                                         'code_dependencies', 'freeze_fastprefix_sources')}
    tag = utility_tag(mine.utility)

    def arm_label(arm, options):
        return f'fl_v4_{tag}_fp' if options else f'fl_v4_{tag}_fpnone'

    def evaluator_env(prep, run_dir):
        env, overrides = saved['evaluator_env'](prep, run_dir)
        if mine.qnet is not None:
            env[Q.ENV_QNET] = overrides[Q.ENV_QNET] = str(Path(run_dir) / 'raw' / 'source_v4' / QNET_FROZEN)
        return env, overrides

    def code_dependencies(prep):
        deps = saved['code_dependencies'](prep)
        deps += [ROOT / d for d in V4_CODE if (ROOT / d).is_file()]
        if mine.qnet is not None:
            deps.append(Path(mine.qnet))
        return deps

    def freeze_fastprefix_sources(raw):
        out = saved['freeze_fastprefix_sources'](raw)
        frozen = {}
        for rel in V4_CODE:
            src = ROOT / rel
            if src.is_file():
                dst = Path(raw) / 'source_v4' / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
                frozen[rel] = C.sha256_file(dst)
        if mine.qnet is not None:
            dst = Path(raw) / 'source_v4' / QNET_FROZEN
            shutil.copyfile(mine.qnet, dst)
            Q.load_spec(dst)
            frozen[QNET_FROZEN] = C.sha256_file(dst)
        C.atomic_json(Path(raw) / 'source_v4' / 'hashes.json', {'utility': mine.utility, 'files': frozen})
        return out

    FL.STAGE = STAGE
    FL.ENTRY_NAME = AE.ENTRY_NAME
    FL.ENTRY_SOURCE = AE.ENTRY_SOURCE
    FL.arm_label = arm_label
    FL.evaluator_env = evaluator_env
    FL.code_dependencies = code_dependencies
    FL.freeze_fastprefix_sources = freeze_fastprefix_sources
    try:
        yield FL
    finally:
        for k, v in saved.items():
            setattr(FL, k, v)


def main(argv=None):
    mine, own, base = parse_args(argv)
    if mine.qnet is not None:
        os.environ[Q.ENV_QNET] = str(mine.qnet)          # this process validates the v3 policy with the network
    B.register_utility_name(mine.utility)
    out_dir = Path(base.output_dir).resolve()
    C._check_writable(out_dir)
    with v4_substitutions(mine) as FL:
        return FL.run(own, base)


if __name__ == '__main__':
    raise SystemExit(main())
