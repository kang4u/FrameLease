#!/usr/bin/env python3
"""Mechanical check of runs of the configurations added after Phase 1 (GAP_AUDIT Sec. 3.5, item A-2): the Q-network
arm fl_full with an exported network (the protocol arms fl_full, fl_bandit and fl_fqi_nolease; PROTOCOL Secs. 4.1,
5.6-5.8, 6.4) and, through a documented hook, the global-lease arm fl_global_shield (Sec. 7.4). CPU only; reads a job
file in the framelease_v2/gpu_queue.py format, the run directories and, with --queue, the runner's status.jsonl; writes
only the report (--write --report PATH). It never starts a job, CARLA or the GPU.

  cd /home/kang/Desktop/DAC
  .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/check_smoke_ext.py --jobs-file JOBS.jsonl \
      [--queue outputs/framelease_v4/queue_X] [--extension MODULE:FUNCTION] [--write --report REPORT.json]

Reused unchanged: framelease_v4/protocol/check_smoke.py, the registered P1-0 criteria of Sec. 8.1. check_smoke.check_run
computes every criterion of every run (route_record, config, summary_v4, fast_prefix, decisions, utility, actor_log,
ego_found, pose_offset, tick_wall, run_size) with its thresholds; this module keeps every result as it is, except:
  * utility: check_smoke.c_utility cannot judge a Q-network utility (it parses 'v4_qnet_<sha12>' as an a_det name with
    int(name.rsplit('_d', 1)[1]), which raises) and check_smoke.arm_kind reads arms_v4.ARMS only. For a Q-network
    utility, or an arm that arms_v4.ARMS does not list (an extension arm), the entry is replaced by c_utility_ext:
    Q-network: the launcher arm takes Q-network utilities (arms_v4.ARMS[arm].utilities lists 'qnet': fl_full only; an
    extension arm is judged by its base arm, so fl_global_shield never does), the agent's policy reports the
    configured utility (registered in the agent process) and every choice epoch (|A_feas| = 2) has reason
    'both_feasible:<name>' (the actions are judged by the criterion qnet); any other utility of an extension arm:
    check_smoke.c_utility itself, applied as for the arm's declared base arm (e.g. fl_global_shield as fl_heuristic:
    'heuristic' -> REFINE, 'v4_adet_d<d>' -> REFINE iff depth < d).
Added: the criterion 'qnet' (N/A without a Q-network utility; PROTOCOL Sec. 5.7):
  * network identity: the configuration's utility block names the utility of policy_params, the default registrar
    (framelease_v4.rl.behaviour), FRAMELEASE_V4_QNET as an ABSOLUTE path (see qnet_line_problems) and its sha256; the
    network file (the run's frozen copy raw/source_v4/<rel>, else the path) has that sha256, which the job pins; the
    file passes qnet.verify_spec and its name is the utility; its feature spec is the pinned features.py spec of the
    16-input (fqi, bandit) or the 10-input (fqi_nolease, the non-lease columns) layout; the policy budget is
    B_pi = 100 us; a job's optional expectations hold: protocol_arm (fl_full / fl_bandit / fl_fqi_nolease -> the
    family fqi / bandit / fqi_nolease, its input count, launcher arm fl_full, and the fixed settings of Sec. 4.7:
    deviation margin 0, hidden layers 32 x 32 or the distillation retry 64 x 64; any other protocol arm on a
    Q-network line, fl_global_shield included, is a problem: only these three arms take a Q-network, Sec. 4.1),
    d_star (= the network's a_det depth) and network (path / sha256 / name / family / n_inputs);
  * decision rows, re-derived in epoch order exactly as qnet.QUtility.select decides: every choice epoch logs
    v4_q_refine, v4_q_refresh, v4_qnet_s, v4_bypass and v4_mu = 1; its action lies in A_feas and is admitted; the
    bypass reason follows the budget rule (disabled -> slack: a shield margin below B_pi -> a network call, overrun
    if v4_qnet_s > B_pi, else non-finite if a Q value is not finite). The disable rule of the pinned qnet.QUtility
    (l. 125-127, 219-232; QNET_THRESHOLDS['disable_rule']), exactly:
      - n counts the network calls of the run, from 1: the choice epochs that reached the timed forward pass (not the
        slack or disabled bypasses, not the forced epochs); a call overruns iff its wall time v4_qnet_s > B_pi;
      - at the n-th call, after recording it, let m = min(n, WINDOW = 256) and o = the overruns among the last m calls
        (this call included). The network is disabled iff this call overran AND n >= MIN_CALLS_TO_DISABLE = 64 AND
        o > MAX_OVERRUN_RATE x m = 0.05 x m, i.e. o >= floor(m / 20) + 1 (4 of the first 64 calls, 5 of the last 99,
        13 of the last 256);
      - the disabling call is itself an overrun bypass (its result discarded, a_det^{d*} taken); from the next choice
        epoch on, every choice epoch is a 'disabled' bypass (tested before the slack bypass) for the rest of the run
        (the QUtility instance of the agent process); nothing re-enables it, and a non-overrunning call never
        disables it.
    PROTOCOL Sec. 5.7 reads "more than 5% of the last 256 calls overran B_pi" (finding QNET-2; the checker replays the
    code): the network is never disabled before call 64 (13 overruns among the first 63 calls do not disable it), and
    for 64 <= n < 256 the denominator is n, not 256 (overruns at calls 95-99 disable it at call 99, 5 > 0.05 x 99 =
    4.95; overruns at calls 96-100 do not, 5 > 5.0 being false); over a full window 12 of the last 256 never disable
    it and 13 do, as the text says. Every bypassed epoch takes a_det^{d*}(depth) with d* the
    network's a_det depth; without bypass a head's Q value is logged iff the head is supported and the action is the
    other action than a_det^{d*} iff both heads are supported and Q[other] > Q[a_det] + margin; every logged Q value
    equals an independent re-computation from the logged features (the offline featurizer features.vector and a plain
    numpy forward pass of the exported layers, not qnet.QNetwork; |error| <= 1e-9 x max(1, |Q|) against a finite
    reference). The one exception: an overrunning call logs its discarded raw values, so where the re-computation is
    not finite the log may hold a non-finite value ('inf' / '-inf' / 'nan' after la.jsonable). No other decision row
    carries the network's keys (the utility is consulted only when |A_feas| = 2, Eq. 8). A run in which the network
    never decided is DEFERRED (its decision path, head support and margin, was not exercised): no choice epoch; no
    network call (every choice epoch bypassed by slack or disable); or every network call overran B_pi or gave
    non-finite Q values (values: network_decisions = 0).
  Reported: choice epochs, network calls and decisions, deviation rate from a_det^{d*} and bypass rate by reason
  (Sec. 6.4), the network wall time p50 / p99 / max (Table II-B), the a_det depth, input count, head support, margin.

Hook for the global-lease arm (framelease_v4/arms_ext, GAP_AUDIT Sec. 2 and A-1; built separately, NOT imported here):
register_extension_arm(name, kind, base_arm, criteria) declares a launcher arm that the pinned arms_v4.ARMS does not
list, the arm whose utility rules it shares and optional extra criteria {name: fn(job, run, summary, rows) -> result}
(a result is check_smoke._res(status, detail, **values): a dict with status PASS / FAIL / DEFERRED / N/A, a str
detail, optional dict values, JSON-serializable; a criterion that raises or returns anything else FAILS with the
reason). The extension's runs are then judged by every criterion above plus its own; other runs get N/A for them.
From the command line, --extension MODULE:FUNCTION imports MODULE and calls FUNCTION(this module), which registers the
arm (e.g. register_extension_arm('fl_global_shield', 'shield', 'fl_heuristic', {'global_lease': ...})). An extension
that keeps its own arm registry and leaves the pinned arms_v4.ARMS unchanged must declare its arm here; an arm that
arms_v4.ARMS itself lists needs no declaration for its utility (its extra criteria still come through the hook).

Job lines: the gpu_queue fields of the P1 lines (id, cmd, arm_name, route_id, kappa, seed, policy_params, envelope,
require_sha256, output_dir, candidate) plus, for the new configurations, optional protocol_arm (fl_full | fl_bandit |
fl_fqi_nolease | fl_global_shield | ...; GAP_AUDIT Sec. 2: the protocol arm is recorded on the job line; a Q-network
line may name only fl_full, fl_bandit or fl_fqi_nolease), d_star and network. arm_name is the LAUNCHER arm (fl_full
for the three Q-network protocol arms). Training routes only (Sec. 9.11: no tool summarizes test-route results; P4-P6
job health belongs to the stage driver, which may call check_run_ext per run). Run selection is check_smoke's
(select_stage.job_outcome), which matches kappa 1.0 and seed 11 only, so other kappa / seed values are refused here. A
Q-network line must pass qnet_line_problems: in particular its --utility-env FRAMELEASE_V4_QNET path must be absolute
(the evaluator runs with another working directory).
Verdict and exit codes as check_smoke: PASS (0; DEFERRED items allowed and listed), FAIL (1), error (2), INCOMPLETE (3);
an unexpected exception is an error (2, with its traceback on stderr), never the FAIL code.
Report path (report_path_problem): --write writes only to an explicit --report path, and refuses, even with --force, a
path inside a gpu_queue jobs.d directory, inside outputs/framelease_v4/{queue_*, registration, p1_driver, p1_jobs,
tuning} (the runner's, the P1 driver's, the job generator's, the tuning selection's and the registration's directories;
matched as the names outputs/framelease_v4/<dir> anywhere in the resolved path, so under this ROOT and in a copy of its
layout), inside the code trees of ROOT (framelease_v2/v3/v4, linux, third_party, checkpoints), a file listed in the
registration MANIFEST.sha256, and an existing directory or file that is not a report of this checker (only an earlier
report of this schema may be replaced, and only with --force if it differs).
"""
from __future__ import annotations

import argparse
import fnmatch
import importlib
import json
import math
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

import numpy as np  # noqa: E402

from framelease_v4.protocol import check_smoke as CS  # noqa: E402
from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402
from framelease_v4.protocol import select_stage as SS  # noqa: E402
from framelease_v4.rl import behaviour as B  # noqa: E402
from framelease_v4.rl import features as F  # noqa: E402
from framelease_v4.rl import qnet as Q  # noqa: E402

SCHEMA = 'framelease_v4.smoke_check_ext/1'
THIS_REL = 'framelease_v4/protocol/check_smoke_ext.py'
PASS, FAIL, DEFERRED, NA = CS.PASS, CS.FAIL, CS.DEFERRED, CS.NA
STATUSES = (PASS, FAIL, DEFERRED, NA)            # the statuses a criterion result may carry
QNET_CRITERION = 'qnet'
CRITERIA = tuple(CS.CRITERIA) + (QNET_CRITERION,)
QNET_LAUNCHER_ARM = 'fl_full'                    # the only arms_v4 arm that accepts a Q-network utility
POLICY_BUDGET_S = 1e-4                           # B_pi (PROTOCOL Sec. 5.7)
Q_LOG_KEYS = ('v4_q_refine', 'v4_q_refresh', 'v4_qnet_s', 'v4_bypass', 'v4_mu')
NETWORK_KEYS = Q_LOG_KEYS[:4]                    # keys only a network call (or its bypass) writes
BYPASS_REASONS = (None, 'slack', 'disabled', 'overrun', 'nonfinite')
Q_TOL = 1e-9
FAMILY_COLUMNS = {'fqi': tuple(F.ALL_COLUMNS), 'bandit': tuple(F.ALL_COLUMNS),
                  'fqi_nolease': tuple(F.NO_LEASE_COLUMNS)}            # = trainers.Candidate(family).columns
PROTOCOL_ARM_FAMILY = {'fl_full': 'fqi', 'fl_bandit': 'bandit', 'fl_fqi_nolease': 'fqi_nolease'}   # Secs. 4.1, 5.6
PROTOCOL_HIDDEN = ([32, 32], [64, 64])           # Sec. 4.7: ReLU MLP n -> 32 -> 32 -> 2; distill's one retry: 64 x 64
QNET_THRESHOLDS = {'policy_budget_s': POLICY_BUDGET_S, 'overrun_window': Q.QUtility.WINDOW,
                   'overrun_max_rate': Q.QUtility.MAX_OVERRUN_RATE,
                   'min_calls_to_disable': Q.QUtility.MIN_CALLS_TO_DISABLE, 'q_recompute_rel_tol': Q_TOL,
                   'disable_rule': 'at an overrunning network call n (network calls of the run counted from 1, '
                                   'bypassed epochs excluded): n >= min_calls_to_disable and overruns among the last '
                                   'min(n, overrun_window) calls (this one included) > overrun_max_rate x '
                                   'min(n, overrun_window); then every later choice epoch is a disabled bypass for '
                                   'the rest of the run (qnet.QUtility; finding QNET-2)',
                   'deferred_rule': 'no network decision in the run (no choice epoch, no network call, or every '
                                    'network call overran B_pi or gave non-finite Q values)',
                   'inputs': {'16': list(F.ALL_COLUMNS), '10': list(F.NO_LEASE_COLUMNS)}}
REQUIRED_JOB_KEYS = ('id', 'cmd', 'arm_name', 'route_id', 'kappa', 'seed', 'policy_params', 'require_sha256',
                     'output_dir', 'candidate')
KNOWN_EXTENSION_ARMS = {'fl_global_shield': 'the global-lease arm of framelease_v4/arms_ext (GAP_AUDIT Sec. 2, A-1)'}
MAX_PROBLEMS = 8
# --write refuses these (report_path_problem): directories of outputs/framelease_v4 owned by the gpu_queue runner, the
# P1 stage driver, the P1 job generator, the tuning selection and the registration, and the code trees of ROOT
PROTECTED_OUTPUT_DIRS = ('queue_*', 'registration', 'p1_driver', 'p1_jobs', 'tuning')
PROTECTED_TREES = ('framelease_v4', 'framelease_v2', 'framelease_v3', 'linux', 'third_party', 'checkpoints')

# launcher arm -> {'kind', 'base_arm', 'criteria': {name: fn}, 'source'}; filled only through register_extension_arm
EXTENSION_ARMS = {}


# ============================================================================================ hook: extension arms

def register_extension_arm(name, kind, base_arm, criteria=None, source=None):
    """Declare a launcher arm that the pinned arms_v4.ARMS does not list (fl_global_shield of framelease_v4/arms_ext).

    kind: an arms_v4 kind ('shield' for fl_global_shield); base_arm: the arms_v4 arm whose utility rules the arm shares
    (its runs' 'utility' criterion is check_smoke.c_utility applied as for base_arm; 'fl_heuristic' for
    fl_global_shield); criteria: {criterion name: fn(job, run, summary, rows) -> check_smoke._res(...)} judged on this
    arm's runs only (N/A elsewhere); a criterion that raises FAILS with the reason. Re-registering replaces."""
    from framelease_v4.arms import arms_v4 as AV
    name = str(name)
    if kind not in AV.KINDS:
        raise ValueError(f'{name}: kind {kind!r} is not an arms_v4 kind {AV.KINDS}')
    if base_arm not in AV.ARMS:
        raise ValueError(f'{name}: base arm {base_arm!r} is not an arms_v4 arm')
    if AV.ARMS[base_arm].kind != kind:
        raise ValueError(f'{name}: base arm {base_arm} is of kind {AV.ARMS[base_arm].kind!r}, not {kind!r}')
    criteria = dict(criteria or {})
    for c, fn in criteria.items():
        if c in CRITERIA or not callable(fn):
            raise ValueError(f'{name}: extension criterion {c!r} clashes with a built-in criterion or is not callable')
        for other, spec in EXTENSION_ARMS.items():
            if other != name and c in spec['criteria'] and spec['criteria'][c] is not fn:
                raise ValueError(f'{name}: criterion {c!r} is already registered by {other} with another function')
    EXTENSION_ARMS[name] = {'kind': kind, 'base_arm': base_arm, 'criteria': criteria, 'source': source}
    return EXTENSION_ARMS[name]


def unregister_extension_arm(name):
    EXTENSION_ARMS.pop(str(name), None)


def load_extension(spec):
    """--extension MODULE:FUNCTION: import MODULE and call FUNCTION(this checker module) (it registers its arms)."""
    if ':' not in str(spec):
        raise ValueError(f'--extension {spec!r}: expected MODULE:FUNCTION')
    mod, fn = str(spec).split(':', 1)
    me = sys.modules[__name__]
    sys.modules.setdefault('framelease_v4.protocol.check_smoke_ext', me)   # one registry when run as a script
    getattr(importlib.import_module(mod), fn)(me)
    return spec


def extension_criteria():
    """[criterion name] of every registered extension arm, in registration order (no duplicates)."""
    out = []
    for spec in EXTENSION_ARMS.values():
        out += [c for c in spec['criteria'] if c not in out]
    return out


def arm_kind_ext(arm):
    """check_smoke.arm_kind (arms_v4.ARMS) extended by the registered extension arms; KeyError with the hook's name."""
    from framelease_v4.arms import arms_v4 as AV
    if arm in AV.ARMS:
        return AV.ARMS[arm].kind
    if arm in EXTENSION_ARMS:
        return EXTENSION_ARMS[arm]['kind']
    hint = KNOWN_EXTENSION_ARMS.get(arm)
    raise KeyError(f'unknown launcher arm {arm!r}' + (f' ({hint}): declare it with register_extension_arm or '
                                                      f'--extension MODULE:FUNCTION' if hint else ''))


def base_arm_of(arm):
    """The arms_v4 arm whose utility rules apply (the arm itself if arms_v4.ARMS lists it)."""
    from framelease_v4.arms import arms_v4 as AV
    if arm in AV.ARMS:
        return arm
    arm_kind_ext(arm)                                   # raises for an undeclared arm
    return EXTENSION_ARMS[arm]['base_arm']


# ============================================================================================ Q-network helpers

def is_qnet_name(name):
    return name is not None and B.QNET_RE.match(str(name)) is not None


def utility_name(job):
    return (job.get('policy_params') or {}).get('utility')


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _close(a, b):
    """|a - b| <= Q_TOL x max(1, |b|) for a finite reference b (an infinite b would accept any finite a)."""
    return math.isfinite(float(b)) and abs(float(a) - float(b)) <= Q_TOL * max(1.0, abs(float(b)))


def _nonfinite(x):
    """A logged non-finite value: la.jsonable writes inf / -inf / nan as these strings; in-process rows keep floats."""
    return x in ('inf', '-inf', 'nan') or (isinstance(x, float) and not math.isfinite(x))


def _cap(problems):
    return problems[:MAX_PROBLEMS] + ([f'... {len(problems) - MAX_PROBLEMS} more'] if len(problems) > MAX_PROBLEMS
                                      else [])


def utility_env_args(cmd):
    """{KEY: VALUE} of the --utility-env options of a launcher command (a repeated key is a problem: ValueError)."""
    out = {}
    cmd = list(cmd or [])
    for i, tok in enumerate(cmd):
        if tok == '--utility-env' and i + 1 < len(cmd):
            k, sep, v = str(cmd[i + 1]).partition('=')
            if not sep:
                raise ValueError(f'--utility-env {cmd[i + 1]!r} is not KEY=VALUE')
            k = k.strip()
            if k in out:
                raise ValueError(f'--utility-env {k} given twice')
            out[k] = v
        elif tok.startswith('--utility-env='):
            raise ValueError('use "--utility-env KEY=VALUE" (two tokens), as the job generators do')
    return out


def network_family(spec):
    return (spec.get('candidate') or {}).get('family')


def spec_problems(spec):
    """Problems of an exported network against the pinned features.py layouts and the protocol budget (Sec. 5.7)."""
    problems = []
    cols = tuple(int(c) for c in spec.get('feature_columns') or ())
    if cols not in (tuple(F.ALL_COLUMNS), tuple(F.NO_LEASE_COLUMNS)):
        problems.append(f'feature columns {list(cols)} are neither the 16-input nor the 10-input (non-lease) layout')
    else:
        keys = ('index', 'name', 'lease_derived', 'missing', 'lo', 'hi')
        want = [{k: d[k] for k in keys} for d in F.spec_dict(cols)]
        got = [{k: (d or {}).get(k) for k in keys} for d in spec.get('feature_spec') or []]
        if got != want:
            problems.append('feature spec differs from framelease_v4/rl/features.py (names, missing values or clip '
                            'ranges): train / deploy skew')
    layers = spec.get('layers') or []
    if not layers or len(layers[0].get('W') or []) != len(cols):
        problems.append(f'first layer has {len((layers[0] if layers else {}).get("W") or [])} rows for {len(cols)} '
                        f'inputs')
    budget = spec.get('policy_budget_s', POLICY_BUDGET_S)
    if not (_num(budget) and abs(float(budget) - POLICY_BUDGET_S) <= 1e-12):
        problems.append(f'policy budget {budget!r} s != B_pi {POLICY_BUDGET_S} s (PROTOCOL Sec. 5.7)')
    fam = network_family(spec)
    if fam is not None and FAMILY_COLUMNS.get(fam) != cols:
        problems.append(f'family {fam!r} with {len(cols)} inputs (expected {len(FAMILY_COLUMNS.get(fam) or ())})')
    return problems


def expectation_problems(job, spec, file_sha=None, rel=None):
    """The job's optional expectations: protocol_arm (family, input count), d_star (a_det depth), network {...}."""
    problems = []
    cols = tuple(int(c) for c in spec.get('feature_columns') or ())
    fam = network_family(spec)
    parm = job.get('protocol_arm')
    if parm is not None and parm in PROTOCOL_ARM_FAMILY:
        want = PROTOCOL_ARM_FAMILY[parm]
        if fam != want:
            problems.append(f'protocol arm {parm} needs a {want} network, the file is family {fam!r}')
        if cols != FAMILY_COLUMNS[want]:
            problems.append(f'protocol arm {parm} needs {len(FAMILY_COLUMNS[want])} inputs, the network has '
                            f'{len(cols)}')
        if job.get('arm_name') != QNET_LAUNCHER_ARM:
            problems.append(f'protocol arm {parm} runs as launcher arm {QNET_LAUNCHER_ARM}, not {job.get("arm_name")}')
        if float(spec.get('deviation_margin', 0.0)) != 0.0:
            problems.append(f'deviation margin {spec.get("deviation_margin")} != 0 (PROTOCOL Sec. 4.7)')
        hidden = [len(L.get('b') or []) for L in (spec.get('layers') or [])[:-1]]
        if hidden not in PROTOCOL_HIDDEN:
            problems.append(f'hidden layers {hidden} not in {PROTOCOL_HIDDEN} (PROTOCOL Sec. 4.7; trainers.distill '
                            f'retries once at 64 x 64)')
    elif parm is not None:
        # PROTOCOL Sec. 4.1: only fl_full, fl_bandit and fl_fqi_nolease take a Q-network; every other arm, the
        # extension arm fl_global_shield included (it replaces only the lease), keeps a_det^{d*} of fl_heuristic
        problems.append(f'protocol arm {parm!r} does not take a Q-network utility (PROTOCOL Sec. 4.1: '
                        f'{", ".join(PROTOCOL_ARM_FAMILY)})')
    d_star = job.get('d_star')
    depth = int((spec.get('a_det') or {}).get('depth', 0))
    if d_star is not None and int(d_star) != depth:
        problems.append(f'the network\'s a_det depth {depth} != d* {d_star} of the job')
    net = job.get('network') or {}
    for key, got in (('name', spec.get('name')), ('family', fam), ('n_inputs', len(cols)), ('sha256', file_sha),
                     ('path', rel)):
        if key in net and got is not None and net[key] != got:
            problems.append(f'job network.{key} {net[key]!r} != {got!r}')
    return problems


def qnet_line_problems(job):
    """Problems of a Q-network job line found without running it ([] for a line without a Q-network utility).

    The --utility-env FRAMELEASE_V4_QNET path must be absolute: arms_v4.utility_block records it verbatim and
    run_closed_loop_v4.evaluator_env hands it to an evaluator that runs with cwd third_party/UniDriveVLA-linux/
    Bench2Drive (run_closed_loop_fast.execute), where arms_v4.build_policy cannot open a repository-relative path
    although the launcher's --dry-run (cwd = the project root) passes (finding QNET-1 of the QNET build report). The
    file must exist, be a valid exported network named policy_params.utility, be pinned (repository-relative path ->
    its sha256) and meet the job's expectations; the launcher arm must accept a Q-network (fl_full)."""
    name = utility_name(job)
    if not is_qnet_name(name):
        return []
    problems = []
    if job.get('arm_name') != QNET_LAUNCHER_ARM:
        problems.append(f'a Q-network utility runs on launcher arm {QNET_LAUNCHER_ARM}, not {job.get("arm_name")!r}')
    cmd = list(job.get('cmd') or [])
    opt = {cmd[i]: cmd[i + 1] for i in range(len(cmd) - 1) if str(cmd[i]).startswith('--')}
    if opt.get('--arm') != job.get('arm_name'):
        problems.append(f'command --arm {opt.get("--arm")!r} != the line\'s arm_name {job.get("arm_name")!r}')
    try:
        if json.loads(opt.get('--policy-params') or '{}') != job.get('policy_params'):
            problems.append('command --policy-params differ from the line\'s policy_params')
    except ValueError:
        problems.append('command --policy-params is not JSON')
    try:
        env = utility_env_args(cmd)
    except ValueError as e:
        return problems + [str(e)]
    extra = sorted(k for k in env if k != Q.ENV_QNET)
    if extra:
        problems.append(f'unexpected --utility-env keys {extra}')
    path = env.get(Q.ENV_QNET)
    if path is None:
        return problems + [f'no --utility-env {Q.ENV_QNET}=<network file>']
    if not Path(path).is_absolute():
        return problems + [f'--utility-env {Q.ENV_QNET}={path} is relative: the evaluator runs in '
                           'third_party/UniDriveVLA-linux/Bench2Drive, where the agent cannot open it; give the '
                           'absolute path']
    if not Path(path).is_file():
        return problems + [f'network file {path} not found']
    sha = PJ.sha256_file(path)
    rel = PJ.rel(path)
    if job.get('require_sha256', {}).get(rel) != sha:
        problems.append(f'the network file {rel} is not pinned with its sha256 {sha[:12]}...')
    try:
        spec = Q.load_spec(path)
    except (OSError, ValueError, KeyError, TypeError) as e:
        return problems + [f'network file {path}: {type(e).__name__}: {e}']
    if spec.get('name') != name:
        problems.append(f'network file {path} is {spec.get("name")}, the line names {name}')
    problems += spec_problems(spec)
    problems += expectation_problems(job, spec, sha, rel)
    if not (job.get('envelope') or {}).get('sha256'):
        problems.append('a shield arm line without its envelope (E*)')
    return problems


class IndependentQ:
    """Q values of an exported network re-computed from a logged feature dict without the pinned online path: the
    offline featurizer (features.vector, used by the dataset and the trainers) and a plain numpy forward pass of the
    exported layers (ReLU between layers, linear output), instead of qnet.QNetwork and its FastVectorizer."""

    def __init__(self, spec):
        self.columns = tuple(int(c) for c in spec['feature_columns'])
        self.layers = [(np.asarray(L['W'], dtype=np.float64), np.asarray(L['b'], dtype=np.float64))
                       for L in spec['layers']]

    def q(self, feats):
        h = F.vector(feats, self.columns)
        last = len(self.layers) - 1
        for i, (W, b) in enumerate(self.layers):
            h = h @ W + b
            if i < last:
                h = np.maximum(h, 0.0)
        return float(h[0]), float(h[1])


def qnet_rows_check(rows, spec, name=None):
    """(problems, values) of one run's decision rows (epoch order) against its network: the replay of
    qnet.QUtility.select described in the module docstring. name: the configured utility (reason check is in
    c_utility_ext; here only the network's own behaviour). Works on decisions.jsonl rows of a run and on the rows
    of an in-process agent run alike."""
    supported = (bool(spec['supported'][0]), bool(spec['supported'][1]))
    both = supported[0] and supported[1]
    margin = float(spec.get('deviation_margin', 0.0))
    d = int(spec['a_det']['depth'])
    budget = float(spec.get('policy_budget_s', POLICY_BUDGET_S))
    W, MINC, RATE = Q.QUtility.WINDOW, Q.QUtility.MIN_CALLS_TO_DISABLE, Q.QUtility.MAX_OVERRUN_RATE
    net = IndependentQ(spec)
    ring, n_calls, n_over, disabled, disabled_at = [0] * W, 0, 0, False, None
    n_choice, n_decisions, deviations, walls, max_err = 0, 0, 0, [], 0.0
    bypass = {'slack': 0, 'disabled': 0, 'overrun': 0, 'nonfinite': 0}
    actions = {'REFINE': 0, 'REFRESH': 0}
    problems = []

    def bad(r, msg):
        problems.append(f'epoch {r.get("epoch")}: {msg}')

    def compare(r, q0, q1, need0, need1, raw=False):
        """Logged Q values against the re-computation. raw: an overrunning call, whose discarded result QUtility logs
        as computed, so a non-finite logged value is right where the re-computation is not finite either."""
        nonlocal max_err
        try:
            r0, r1 = net.q(r['features'])
        except (TypeError, ValueError, KeyError) as e:
            bad(r, f'Q re-computation failed: {type(e).__name__}: {e}')
            return
        for label, got, ref, need in (('v4_q_refine', q0, r0, need0), ('v4_q_refresh', q1, r1, need1)):
            if not need:
                continue
            if raw and _nonfinite(got) and not math.isfinite(ref):
                continue
            if not _num(got):
                bad(r, f'{label} {got!r} is not a number' + ('' if math.isfinite(ref) else
                                                           f' (the network gives {ref!r} for the logged state)'))
            elif not _close(got, ref):
                bad(r, f'{label} {got!r} != the network\'s {ref!r} for the logged state')
            else:
                max_err = max(max_err, abs(float(got) - ref))

    for r in rows or []:
        f = r.get('features') if isinstance(r.get('features'), dict) else {}
        if r.get('p_both') is not True:
            leaked = [k for k in NETWORK_KEYS if k in f]
            if leaked:
                bad(r, f'{leaked} logged outside a choice epoch (the utility is consulted only when |A_feas| = 2)')
            continue
        n_choice += 1
        missing = [k for k in Q_LOG_KEYS if k not in f]
        if missing:
            bad(r, f'choice epoch without {missing}')
            continue
        a = r.get('action')
        feas = list(r.get('feasible') or [])
        if sorted(feas) != ['REFINE', 'REFRESH']:
            bad(r, f'choice epoch with A_feas {feas}')
        if a not in feas or r.get('admitted') is not True:
            bad(r, f'action {a!r} not admitted / not in A_feas {feas}')
        if a in actions:
            actions[a] += 1
        if f.get('v4_mu') != 1.0:
            bad(r, f'v4_mu {f.get("v4_mu")!r} != 1.0 (deterministic policy)')
        a_det = B.a_det_action(f.get('depth', r.get('depth')), d)
        byp, q0, q1, wall = f['v4_bypass'], f['v4_q_refine'], f['v4_q_refresh'], f['v4_qnet_s']
        if byp not in BYPASS_REASONS:
            bad(r, f'unknown bypass reason {byp!r}')
            continue
        if disabled or byp == 'disabled':
            if not disabled:
                bad(r, 'bypass "disabled" although at most 5 % of the recent calls overran (or too few calls)')
            elif byp != 'disabled':
                bad(r, f'bypass {byp!r} after the network was disabled at epoch {disabled_at}')
            if (q0, q1, wall) != (None, None, None):
                bad(r, 'a disabled network logged Q values or a wall time')
            if a != a_det:
                bad(r, f'action {a} != a_det^{d} {a_det} with the network disabled')
            bypass['disabled'] += 1
            continue
        slack = [k for k in ('refine_margin_s', 'refresh_margin_s') if _num(f.get(k)) and float(f[k]) < budget]
        if slack or byp == 'slack':
            if not slack:
                bad(r, f'bypass "slack" with both shield margins >= B_pi {budget} s')
            elif byp != 'slack':
                bad(r, f'shield margin {slack[0]} {f[slack[0]]!r} < B_pi {budget} s but bypass {byp!r}')
            if (q0, q1, wall) != (None, None, None):
                bad(r, 'a slack bypass logged Q values or a wall time (the network must not run)')
            if a != a_det:
                bad(r, f'action {a} != a_det^{d} {a_det} under the slack bypass')
            bypass['slack'] += 1
            continue
        # a network call (QUtility: timed, then overrun / non-finite / decision)
        if not (_num(wall) and float(wall) >= 0.0):
            bad(r, f'v4_qnet_s {wall!r} at a network call')
            continue
        over = 1 if float(wall) > budget else 0
        k = n_calls % W
        n_over += over - ring[k]
        ring[k] = over
        n_calls += 1
        walls.append(float(wall))
        if over and n_calls >= MINC and n_over > RATE * min(n_calls, W):
            disabled, disabled_at = True, r.get('epoch')
        if over or byp == 'overrun':
            if not over:
                bad(r, f'bypass "overrun" with v4_qnet_s {wall} <= B_pi {budget} s')
            elif byp != 'overrun':
                bad(r, f'v4_qnet_s {wall} > B_pi {budget} s but bypass {byp!r} (the late result must be discarded)')
            if a != a_det:
                bad(r, f'action {a} != a_det^{d} {a_det} after an overrun')
            compare(r, q0, q1, True, True, raw=True)
            bypass['overrun'] += 1
            continue
        if byp == 'nonfinite':
            try:
                r0, r1 = net.q(f)
            except (TypeError, ValueError, KeyError) as e:
                r0 = r1 = 0.0
                bad(r, f'Q re-computation failed: {type(e).__name__}: {e}')
            if math.isfinite(r0) and math.isfinite(r1):
                bad(r, 'bypass "nonfinite" but the network gives finite Q values for the logged state')
            if (q0, q1) != (None, None) or a != a_det:
                bad(r, f'non-finite bypass logged Q values or acted {a} != a_det^{d} {a_det}')
            bypass['nonfinite'] += 1
            continue
        n_decisions += 1                                  # the network's own decision (support and margin)
        for label, got, sup in (('v4_q_refine', q0, supported[0]), ('v4_q_refresh', q1, supported[1])):
            if (got is not None) != sup:
                bad(r, f'{label} {got!r} logged for a head with support {sup}')
        compare(r, q0, q1, supported[0], supported[1])
        want = a_det
        if both and _num(q0) and _num(q1):
            if a_det == 'REFINE' and float(q1) > float(q0) + margin:
                want = 'REFRESH'
            elif a_det == 'REFRESH' and float(q0) > float(q1) + margin:
                want = 'REFINE'
        if a != want:
            bad(r, f'action {a} != {want} (a_det^{d} {a_det}, Q {q0!r} / {q1!r}, margin {margin}, support '
                   f'{list(supported)})')
        if a != a_det:
            deviations += 1
    n_byp = sum(bypass.values())
    values = {'utility': name, 'a_det_depth': d, 'n_inputs': len(net.columns), 'supported': list(supported),
              'deviation_margin': margin, 'budget_s': budget, 'choice_epochs': n_choice, 'network_calls': n_calls,
              'network_decisions': n_decisions,
              'bypass': bypass, 'bypass_rate': (n_byp / n_choice) if n_choice else None, 'deviations': deviations,
              'deviation_rate': (deviations / n_choice) if n_choice else None, 'actions': actions,
              'disabled_at_epoch': disabled_at, 'max_abs_q_error': max_err,
              'qnet_s': {'p50': CS._q(walls, 0.5), 'p99': CS._q(walls, 0.99), 'max': max(walls) if walls else None}}
    return problems, values


def run_network(run, u):
    """(spec, path, file sha256, rel, problems) of the network a run recorded in its utility block."""
    from framelease_v4.arms import arms_v4 as AV
    problems = []
    if u.get('registrar') != AV.DEFAULT_UTILITY_REGISTRAR:
        problems.append(f'registrar {u.get("registrar")!r} is not the pinned default {AV.DEFAULT_UTILITY_REGISTRAR}')
    env = u.get('env') or {}
    path = env.get(Q.ENV_QNET)
    if not path:
        return None, None, None, None, problems + [f'the utility block sets no {Q.ENV_QNET}']
    if not Path(path).is_absolute():
        problems.append(f'{Q.ENV_QNET}={path} is relative (the agent process runs in another working directory)')
    recorded = (u.get('env_files_sha256') or {}).get(path)
    if recorded is None:
        problems.append('the utility block records no sha256 of the network file')
    rel = PJ.rel(path)
    frozen = Path(run) / 'raw' / 'source_v4' / rel
    src = frozen if (not Path(rel).is_absolute() and frozen.is_file()) else Path(path)
    if not src.is_file():
        return None, path, None, rel, problems + [f'network file not found (frozen copy or {path})']
    sha = PJ.sha256_file(src)
    if recorded is not None and sha != recorded:
        problems.append(f'network file {PJ.rel(src)} sha256 {sha[:12]}... != recorded {str(recorded)[:12]}...')
    try:
        spec = json.loads(src.read_text(encoding='utf-8'))
        Q.verify_spec(spec)
    except (OSError, ValueError, KeyError, TypeError) as e:
        return None, path, sha, rel, problems + [f'network file {PJ.rel(src)}: {type(e).__name__}: {e}']
    return spec, path, sha, rel, problems


# ============================================================================================ criteria (one run)

def c_utility_ext(job, run, summary, rows):
    """The 'utility' criterion for a Q-network utility or an extension arm (see the module docstring)."""
    from framelease_v4.arms import arms_v4 as AV
    name = utility_name(job)
    base = base_arm_of(job['arm_name'])
    if not is_qnet_name(name):
        return CS.c_utility({**job, 'arm_name': base}, run, summary, rows)
    if 'qnet' not in AV.ARMS[base].utilities:
        via = '' if base == job['arm_name'] else f' (judged as its base arm {base})'
        return CS._res(FAIL, f'launcher arm {job["arm_name"]}{via} does not take a Q-network utility: it accepts '
                             f'{", ".join(AV.ARMS[base].utilities) or "none"} (PROTOCOL Sec. 4.1: only '
                             f'{QNET_LAUNCHER_ARM} runs a Q-network)', arm=job['arm_name'], base_arm=base)
    got = ((summary or {}).get('policy') or {}).get('utility')
    if got != name:
        return CS._res(FAIL, f'the agent\'s policy reports utility {got!r}, configured {name!r}', utility=got)
    choice = [r for r in (rows or []) if r.get('p_both') is True]
    for r in choice:
        if r.get('reason') != f'both_feasible:{name}':
            return CS._res(FAIL, f'epoch {r.get("epoch")}: reason {r.get("reason")!r}', utility=got,
                           choice_epochs=len(choice))
    return CS._res(PASS, f'utility {got} registered in the agent; {len(choice)} choice epochs with reason '
                         f'both_feasible:{name} (actions: criterion {QNET_CRITERION})', utility=got,
                   choice_epochs=len(choice))


def c_qnet(job, run, summary, rows, problem=None):
    """The 'qnet' criterion (PROTOCOL Sec. 5.7; see the module docstring)."""
    name = utility_name(job)
    if not is_qnet_name(name):
        return CS._res(NA, 'no Q-network utility')
    cfg = CS._read_json(Path(run) / 'config.json') or {}
    u = (cfg.get('v4') or {}).get('utility') or {}
    problems = []
    if u.get('name') != name:
        problems.append(f'configuration utility block names {u.get("name")!r}, policy_params {name!r}')
    spec, path, sha, rel, p = run_network(run, u)
    problems += p
    if spec is None:
        return CS._res(FAIL, '; '.join(_cap(problems)), network=path)
    if spec.get('name') != name:
        problems.append(f'the network file is {spec.get("name")}, the utility is {name}')
    if sha is not None and (job.get('require_sha256') or {}).get(rel) != sha:
        problems.append(f'the job does not pin the network file {rel} with its sha256')
    problems += spec_problems(spec)
    problems += expectation_problems(job, spec, sha, rel)
    ident = {'network': rel, 'network_sha256': sha, 'family': network_family(spec),
             'protocol_arm': job.get('protocol_arm')}
    if rows is None or problem:
        problems.append(problem or 'decisions.jsonl missing')
        return CS._res(FAIL, '; '.join(_cap(problems)), **ident)
    rp, vals = qnet_rows_check(rows, spec, name)
    problems += rp
    vals.update(ident)
    if problems:
        return CS._res(FAIL, '; '.join(_cap(problems)), n_problems=len(problems), **vals)
    if vals['choice_epochs'] == 0:
        return CS._res(DEFERRED, 'no choice epoch: the network path was not exercised in this run', **vals)
    if vals['network_calls'] == 0:
        return CS._res(DEFERRED, f'{vals["choice_epochs"]} choice epochs, all bypassed: the network never ran', **vals)
    if vals['network_decisions'] == 0:
        return CS._res(DEFERRED, f'{vals["network_calls"]} network calls, every one overran B_pi or gave non-finite Q '
                                 f'values (bypass {vals["bypass"]}): no network decision in this run', **vals)
    return CS._res(PASS, f'{vals["choice_epochs"]} choice epochs consistent with {name} (a_det^{vals["a_det_depth"]}, '
                         f'{vals["n_inputs"]} inputs, {vals["network_calls"]} calls, {vals["deviations"]} deviations, '
                         f'{sum(vals["bypass"].values())} bypasses)', **vals)


def result_problem(res):
    """None if res is a criterion result (check_smoke._res: a dict {status, detail[, values]} with status PASS / FAIL /
    DEFERRED / N/A, a str detail, a dict of values, JSON-serializable as the report writes it), else the reason."""
    if not isinstance(res, dict):
        return f'returned {type(res).__name__}, not a check_smoke._res dict'
    extra = sorted(str(k) for k in res if k not in ('status', 'detail', 'values'))
    if extra:
        return f'result has unexpected keys {extra}'
    if res.get('status') not in STATUSES:
        return f'result status {res.get("status")!r} is not one of {list(STATUSES)}'
    if not isinstance(res.get('detail'), str):
        return f'result detail {res.get("detail")!r} is not a str'
    if 'values' in res and not isinstance(res['values'], dict):
        return f'result values are a {type(res["values"]).__name__}, not a dict'
    try:
        json.dumps(res, sort_keys=True)
    except (TypeError, ValueError) as e:
        return f'result is not JSON-serializable: {type(e).__name__}: {e}'
    return None


def _guarded(fn):
    """fn() if it is a criterion result; a FAIL with the reason if fn raises or returns anything else (a malformed
    artefact or a broken extension criterion fails its criterion, never the whole check)."""
    try:
        res = fn()
    except Exception as e:  # noqa: BLE001
        return CS._res(FAIL, f'check raised {type(e).__name__}: {e}')
    bad = result_problem(res)
    return res if bad is None else CS._res(FAIL, f'malformed criterion result: {bad}')


def check_run_ext(job, outcome, run):
    """{criterion: result} for one final run: check_smoke.check_run unchanged, 'utility' replaced only where it cannot
    judge (Q-network utility, extension arm), plus 'qnet' and the extension criteria."""
    from framelease_v4.arms import arms_v4 as AV
    run = Path(run)
    out = CS.check_run(job, outcome, run)
    fl = run / 'raw' / 'agent' / 'framelease'
    summary = CS._read_json(fl / 'summary.json')
    rows, problem = CS.strict_jsonl(fl / 'decisions.jsonl') if (fl / 'decisions.jsonl').is_file() else (None, None)
    if is_qnet_name(utility_name(job)) or job['arm_name'] not in AV.ARMS:
        out['utility'] = _guarded(lambda: c_utility_ext(job, run, summary, rows))
    out[QNET_CRITERION] = _guarded(lambda: c_qnet(job, run, summary, rows, problem))
    own = (EXTENSION_ARMS.get(job['arm_name']) or {}).get('criteria') or {}
    for name in extension_criteria():
        fn = own.get(name)
        out[name] = _guarded(lambda: fn(job, run, summary, rows)) if fn else CS._res(NA, f'not a criterion of '
                                                                                         f'{job["arm_name"]}')
    return out


# ============================================================================================ jobs and report

def load_jobs(path):
    """Job lines of the new configurations (see the module docstring); raises ValueError / PermissionError."""
    jobs = [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines() if x.strip()]
    if not jobs:
        raise ValueError(f'{path}: no job line')
    train = PJ.training_routes()
    test = {r['route_id'] for r in PJ.route_split()['test']}
    problems = []
    ids = [j.get('id') for j in jobs]
    if len(set(ids)) != len(ids):
        problems.append('duplicate job ids')
    for j in jobs:
        jid = j.get('id')
        missing = [k for k in REQUIRED_JOB_KEYS if k not in j]
        if missing:
            problems.append(f'{jid}: missing {missing}')
            continue
        if str(j['route_id']) in test or str(j['route_id']) not in train:
            raise PermissionError(f'{jid}: route {j["route_id"]} is not a training route (PROTOCOL Sec. 9.11: no '
                                  f'tool summarizes test-route runs; check P4-P6 job health per run instead)')
        try:
            arm_kind_ext(j['arm_name'])
        except KeyError as e:
            problems.append(f'{jid}: {e.args[0]}')
            continue
        if (float(j['kappa']), int(j['seed'])) != (PJ.KAPPA, PJ.SEED):
            problems.append(f'{jid}: kappa {j["kappa"]} / seed {j["seed"]}: select_stage.job_outcome matches '
                            f'kappa {PJ.KAPPA} and seed {PJ.SEED} only')
        problems += [f'{jid}: {p}' for p in qnet_line_problems(j)]
    if problems:
        raise ValueError(f'{path}: invalid job lines:\n  ' + '\n  '.join(problems))
    return jobs


def criteria_list():
    return list(CRITERIA) + extension_criteria()


def check(jobs, root=ROOT, queue_dir=None, job_file=None, registration=CS.REGISTRATION_MANIFEST):
    """The report over every job's final run (run selection and verdict exactly as check_smoke.check)."""
    states = SS.queue_states(queue_dir)
    per_job, deferred = [], []
    for j in jobs:
        cand = {'name': j['candidate'], 'arm': j['arm_name'], 'policy_params': j['policy_params'],
                'envelope': j.get('envelope')}
        outcome = SS.job_outcome(j, j['route_id'], cand, root, states)
        row = {'job': j['id'], 'candidate': j['candidate'], 'arm': j['arm_name'],
               'protocol_arm': j.get('protocol_arm'), 'utility': utility_name(j), 'outcome': outcome['outcome'],
               'run_dir': outcome.get('run_dir'), 'attempts_found': outcome.get('attempts_found'),
               'queue': outcome.get('queue')}
        if outcome['outcome'] == 'pending':
            row.update(status='INCOMPLETE', cause=outcome.get('cause'), criteria={})
        elif outcome.get('run_dir') is None:
            row.update(status=FAIL, criteria={'route_record': CS._res(FAIL, f'no run directory '
                                                                            f'({outcome.get("cause")})')})
        else:
            crit = check_run_ext(j, outcome, SS._abs(outcome['run_dir'], root))
            row['criteria'] = crit
            row['status'] = FAIL if any(c['status'] == FAIL for c in crit.values()) else PASS
            deferred += [f'{j["id"]}: {k}: {c["detail"]}' for k, c in crit.items() if c['status'] == DEFERRED]
        per_job.append(row)
    if any(r['status'] == FAIL for r in per_job):
        verdict = 'FAIL'
    elif any(r['status'] == 'INCOMPLETE' for r in per_job):
        verdict = 'INCOMPLETE'
    else:
        verdict = 'PASS'
    reg = CS.registered_hashes(registration)
    base_sha = PJ.sha256_file(Path(CS.__file__))
    this_sha = PJ.sha256_file(Path(__file__))
    rep = {'schema': SCHEMA, 'verdict': verdict, 'jobs': per_job, 'deferred': deferred, 'criteria': criteria_list(),
           'thresholds': CS.THRESHOLDS, 'qnet_thresholds': QNET_THRESHOLDS,
           'extensions': {k: {'kind': v['kind'], 'base_arm': v['base_arm'], 'criteria': list(v['criteria']),
                              'source': v['source']} for k, v in EXTENSION_ARMS.items()},
           'queue': PJ.rel(queue_dir) if queue_dir else None,
           'script': THIS_REL, 'script_sha256': this_sha, 'script_registered': reg.get(THIS_REL) == this_sha,
           'base_checker': CS.THIS_REL, 'base_checker_sha256': base_sha,
           'base_checker_registered': reg.get(CS.THIS_REL) == base_sha,
           'registration_manifest': PJ.rel(registration) if Path(registration).is_file() else None,
           'written': time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    if job_file is not None:
        rep['job_file'] = PJ.rel(job_file)
        rep['job_file_sha256'] = PJ.sha256_file(job_file)
        rep['job_file_registered'] = reg.get(rep['job_file']) == rep['job_file_sha256']
    return rep


def summary_lines(rep):
    L = [f'check of the new configurations: {rep["verdict"]}  (checker registered: {rep["script_registered"]}, '
         f'base checker registered: {rep["base_checker_registered"]})']
    for r in rep['jobs']:
        bad = [f'{k}: {c["detail"]}' for k, c in (r.get('criteria') or {}).items() if c['status'] in (FAIL, DEFERRED)]
        label = r['arm'] + (f' ({r["protocol_arm"]})' if r.get('protocol_arm') else '')
        L.append(f'  {r["status"]:<10} {r["job"]:<62} {label:<30} {r["outcome"]:<12}' +
                 ('' if not bad else '  ' + ' | '.join(bad)))
        if r['status'] == 'INCOMPLETE':
            L.append(f'             {r.get("cause")}')
        q = ((r.get('criteria') or {}).get(QNET_CRITERION) or {}).get('values') or {}
        if q.get('choice_epochs') is not None:
            L.append(f'             qnet {q.get("utility")}: a_det^{q.get("a_det_depth")}, {q.get("n_inputs")} inputs, '
                     f'{q.get("choice_epochs")} choice epochs, {q.get("network_calls")} calls, deviation rate '
                     f'{q.get("deviation_rate")}, bypass {q.get("bypass")}, qnet_s p99 {q["qnet_s"]["p99"]}')
    for d in rep['deferred']:
        L.append(f'  deferred: {d}')
    return L


def report_path_problem(path, root=ROOT, registration=CS.REGISTRATION_MANIFEST):
    """None if --write may write the report to path, else the reason (module docstring, 'Report path'): the path is
    resolved (symbolic links followed) and refused inside a jobs.d directory, inside outputs/framelease_v4/<d> for d
    in PROTECTED_OUTPUT_DIRS (matched as that sequence of names anywhere in the path, so also in a copy of the
    layout), inside a code tree of root, if the registration manifest lists it, and if it exists and is not a report
    of this checker (schema SCHEMA). Overwriting an earlier, different report still needs --force (check_smoke)."""
    if path is None:
        return '--write needs an explicit --report PATH'
    p = Path(path).expanduser().resolve()
    parts = p.parts
    if 'jobs.d' in parts:
        return f'{p} is inside a gpu_queue jobs.d directory'
    for i in range(len(parts) - 2):
        if parts[i:i + 2] == ('outputs', 'framelease_v4') and \
                any(fnmatch.fnmatchcase(parts[i + 2], g) for g in PROTECTED_OUTPUT_DIRS):
            return (f'{p} is inside outputs/framelease_v4/{parts[i + 2]} (a directory of the gpu_queue runner, the '
                    f'P1 driver, the P1 job generator, the tuning selection or the registration)')
    root = Path(root).resolve()
    for tree in PROTECTED_TREES:
        if p.is_relative_to(root / tree):
            return f'{p} is inside the code tree {tree}/ of {root}'
    for key in CS.registered_hashes(registration):
        k = Path(key)
        if (k if k.is_absolute() else root / k).resolve() == p:
            return f'{p} is listed in the registration manifest {registration}'
    if p.exists():
        if not p.is_file():
            return f'{p} exists and is not a file'
        old = CS._read_json(p)
        if not (isinstance(old, dict) and old.get('schema') == SCHEMA):
            return (f'{p} exists and is not a report of this checker (schema {SCHEMA}): only such a report may be '
                    f'replaced')
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--jobs-file', type=Path, required=True, help='job lines of the new configurations (gpu_queue)')
    ap.add_argument('--queue', type=Path, default=None, help='gpu_queue directory that ran them (status.jsonl)')
    ap.add_argument('--extension', action='append', default=[], help='MODULE:FUNCTION registering an extension arm')
    ap.add_argument('--write', action='store_true', help='write the report to --report')
    ap.add_argument('--report', type=Path, default=None, help='report path (needed with --write)')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args(argv)
    bad = report_path_problem(a.report) if a.write else None
    if bad:
        print(f'ERROR: --write: {bad}', file=sys.stderr)
        return 2
    try:
        for ext in a.extension:
            load_extension(ext)
        jobs = load_jobs(a.jobs_file)
        rep = check(jobs, ROOT, a.queue, a.jobs_file)
        print('\n'.join(summary_lines(rep)))
        if a.write:
            path = CS.write_report(rep, a.report, a.force)
            print(f'wrote {path}  sha256 {PJ.sha256_file(path)}')
    except (SS.SelectionError, FileNotFoundError, FileExistsError, ValueError, KeyError, PermissionError,
            ImportError, AttributeError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001  an error of the checker or an extension: exit 2, never the FAIL code 1
        traceback.print_exc()
        print(f'ERROR: unexpected {type(e).__name__}: {e} (an error of the check, not a FAIL verdict)', file=sys.stderr)
        return 2
    return {'PASS': 0, 'FAIL': 1, 'INCOMPLETE': 3}[rep['verdict']]


__all__ = ['SCHEMA', 'CRITERIA', 'QNET_CRITERION', 'POLICY_BUDGET_S', 'Q_LOG_KEYS', 'EXTENSION_ARMS',
           'register_extension_arm', 'unregister_extension_arm', 'load_extension', 'extension_criteria', 'arm_kind_ext',
           'base_arm_of', 'is_qnet_name', 'utility_env_args', 'spec_problems', 'expectation_problems',
           'qnet_line_problems', 'IndependentQ', 'qnet_rows_check', 'run_network', 'c_utility_ext', 'c_qnet',
           'result_problem', 'check_run_ext', 'load_jobs', 'criteria_list', 'check', 'summary_lines',
           'report_path_problem', 'main']


if __name__ == '__main__':
    raise SystemExit(main())
