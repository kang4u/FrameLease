#!/usr/bin/env python3
"""Table II-B stress tests S1-S3 (framelease_v4/PROTOCOL.md Sec. 7.6; GAP_AUDIT Sec. 3.4 rows S-1 to S-4).

CPU only: no CARLA, no GPU, no queue. Decision logs are read, never written; the only output is one JSON report.

  cd /home/kang/Desktop/DAC
  PY=".conda-unidrive-linux/bin/python -I -B"
  $PY framelease_v4/protocol/stress_bench.py s3 [--n-sequences 100000] [--targets gate,runtime] [--seed N] \
      [--out FILE] [--registered]
  $PY framelease_v4/protocol/stress_bench.py s2 --qnet NET.json [--qnet ...] [--states synthetic|recorded] \
      [--runs-root DIR ...] [--n-states 2000] [--grid registered|relative] [--out FILE] [--registered]
  $PY framelease_v4/protocol/stress_bench.py s1 --qnet NET.json [--qnet ...] [--loads 0,4,8,15] [--dry-run] \
      [--states synthetic|recorded] [--scenes c1_sweep|synthetic] [--envelope L*.json] [--out FILE] [--registered] \
      [--cpu-sample-s 2] [--accept-foreign-cpu]

While any runner is active, prefix every command with "nice -n 19 ionice -c 3" and keep OMP_NUM_THREADS=1
(GAP_AUDIT Sec. 1.4). s1 refuses to start while a runner, CARLA, the P1 driver or an RL job is alive: it needs an
exclusive CPU (end of P3). It also samples the CPU use of every other process (/proc) before the plan and each load
level; a registered s1 refuses while a foreign process uses CPU, unless --accept-foreign-cpu (recorded). s1 --dry-run
prints the plan and starts nothing. Without --registered every report is labelled "development run, not the registered
S<k>". Reports are written, by whitelist, only under outputs/framelease_v4/stress/ (the default) or
outputs/framelease_v4/build/, or outside the project, and never onto a file of the registration manifest; --force
overwrites only an earlier stress_bench report.

Decision states (GAP_AUDIT S-1). One format, two sources:
  synthetic  random states over the operating range of the shield arms (synthetic_states: kappa 1.0 / 1.5 / 2.0,
             depth 1-10, p99 bounds around the measured fast-prefix profile, D* - t in [-0.3, 2.5] s);
  recorded   the shield rows of raw/agent/framelease/decisions.jsonl of FINISHED runs under --runs-root (found by
             rl.dataset.discover_runs; entry_status 'Finished' and exactly one valid official route record, Sec. 8.4;
             aborted, still running or retried attempts are skipped and listed): the P1 shield runs
             (outputs/framelease_v4/tuning) and later the P2 behaviour runs (outputs/framelease_v4/rl_data). Held-out
             test routes, and runs without a route id, are refused (Sec. 9.11) unless --allow-test-routes (Phase 7,
             after the analysis freeze; a missing route id is always refused).
A state is replayed through ReplayPolicy: the deployed framelease_v3 ShieldedHeuristicPolicy.decide (shield Eq. 5,
the 32 features, Eq. 8 with the utility, bookkeeping) on rebuilt runtime objects (job, active candidate, newest
frame, context). Only the shield budgets come from the state (its recorded p99 bounds and L_commit) instead of the
live latency profile. For recorded states the unmoved replay is checked against the log ('replay_fidelity': feasible
set, the 32 features, and the action at forced epochs and heuristic-utility choice epochs).

S3, cancellation and regression (Sec. 7.6; Eq. 9 of Sec. 2.4). At least 1e5 random event sequences, each run against
  gate     framelease_v3.runtime.v3_commit.CommitGate, and
  runtime  the V4Runtime commit path (framelease_v4/arms/runtime_v4.py, inherited from V3Runtime): the release
           section of LatencyRuntime._complete_op (ShieldedHeuristicPolicy.validity -> D = t_k + H), then
           V3Runtime._try_commit (kinematic check, policy.margin_check = M(t_commit - t_k) > delta from the lease
           result, CommitGate), job closing through V3Runtime._end_job, and the watchdog
           (V3Runtime.control_reference) at random query times. The lease of every candidate is scripted
           (ScriptedLeasePolicy.compute_lease) with analytic margin functions; everything else is deployed code.
  A sequence has 1-5 jobs (observations; 5% reuse the previous observation), 1-10 candidates per job, and the fault
  classes of Sec. 7.6: completions delivered late (1/3 delayed by up to 1.5 s) and out of order (half the sequences
  shuffled), REFRESH closes before the next job's releases (70%) plus random closes and single-candidate
  cancellations, late completions of closed jobs, duplicate releases, older observations completing after a newer
  commit, expired candidates (H = 0, short and NaN leases, delays), stale commit clocks (20%), invalid plans (5%:
  non-finite, speed limit, acceleration limit), over-long leases whose margin fails before D (10%; runtime target),
  failing margin flags (5%; gate target) and commits exactly at the deadline (2%: t_commit = D). An independent
  oracle decides every offer in the order of Sec. 2.4 and counts violations per invariant (INVARIANTS): commit of a
  cancelled candidate, of an invalid plan, of a version that is not newer, at or after the deadline, with
  M <= delta; committed versions not strictly increasing; spurious
  rejections; wrong rejection reasons; and for the runtime target gate/runtime desynchronisation, a deadline that is
  not t_k + H (Eq. 3), a step record that disagrees with the commit, and the watchdog tracking a plan at or after its
  deadline, or not the latest commit, or falling back while the latest commit is valid. The oracle's M(Delta) is
  computed analytically from the margin functions (linear, and V-shaped with the minimum on a grid point), not by
  LeaseResult.margin; |M - delta| <= 1e-9 is counted as ambiguous and judged neither way. Violations must be 0; the
  report also lists the coverage of each fault class (coverage_ok: each >= n_sequences / 100; deadline_tie counts the
  exact ties decided by the deadline check).

S2, near deadline (Sec. 7.6). Every state with an active candidate is replayed with D* moved to t + s for s in
  [-0.1, 0.6] s in 10 ms steps (71 values); when the running job's candidate is the active one (D_cand = D* in the
  state) D_cand moves with D*. Per deployed network (Full FrameLease utility, loaded by name through
  behaviour.register_utility_name and $FRAMELEASE_V4_QNET exactly as the agent does; a fresh policy per slack value)
  and slack value: the share of admitted actions, P_both, feasible sets, actions, the Q-network calls and bypasses by
  reason (slack < B_pi, disabled, overrun, non-finite) and the bypass rate, also split into its near-deadline part
  (slack) and its CPU-timing part (overrun, disabled: machine load, S1's subject). Checked for every admitted
  action, from the state's bounds (the Eq. 5 sums of Sec. 2.4): bound = t + L_pi + L_a + L_commit + R_a + eps < D*
  (the number with bound >= D* must be 0), the predicted commit time t + L_pi + L_a + L_commit < D* and equal to the
  runtime's expectation, REFINE below depth 10 and inside the candidate deadline, REFRESH only with a newer frame; no
  feasible action left unused; the network consulted exactly at the |A_feas| = 2 epochs (Sec. 5.7). Per kappa, the
  report gives the Eq. 5 slack floors of the states (slack_floor) and per network the admitted actions checked, the
  grid values that admit nothing and the first admitting slack (by_kappa). The lease values of a moved state stay as
  logged (only the network's input sees them; NOTES).

Supplementary S2 (Amendment A7; s2 --grid relative, default --grid registered). The same sweep and checks on a grid
  relative to each state's own Eq. 5 slack floor f(state) (slack_floor(state)['any'], the first-admissible slack):
  D* = t + f(state) + delta for delta in [-0.1, 0.6] s in 10 ms steps (71 offsets), D_cand moving with D* as above.
  A state that admits no action at any slack has no floor and is counted (no_floor), not swept. Reported per offset
  and per kappa: the share admitted, the admitted actions whose bound >= D* (must be 0) and the bypass rate with its
  near-deadline and CPU-timing parts; the report records grid 'relative_to_floor', the offsets and f(state) per state,
  and checks every feasible set against the per-action floors (floor_check). It is labelled "supplementary: S2
  relative to the slack floor" ('supplementary': true), also when --registered, and never replaces the registered
  grid, whose report is unchanged by this option.

S1, CPU contention (Sec. 7.6). Under 0 / 4 / 8 / 15 background busy processes (Python spin loops at the caller's
  priority, started and killed by BusyLoad; each also ends by itself when the bench process is gone or after
  --busy-max-s, and the CLI turns SIGTERM into a clean exit): the Q-network call (QUtility's timed region:
  featurize + forward + two reads) per network, with the overrun rate against B_pi and the call at which QUtility's
  5%-of-256 rule would disable the network; shield + decision (ShieldedHeuristicPolicy.decide's own
  decision_wall_s, the Panel B quantity) with the heuristic and with each network, over all epochs and over choice
  epochs; the lease (ShieldedHeuristicPolicy.validity's own lease_wall_s: suffix lease Eq. 1-3 against the
  observation's prepared agents, L* envelope) and the commit check (V3Runtime._try_commit, timed around the call).
  decisions.jsonl does not log detections, so the lease and the commit check run on scenes: the C1-sweep frames
  (real model detections and candidate plans, framelease_v3 helpers_v3.sweep_frames) or synthetic scenes.
  p50 / p99 / max / mean in us. Before each level the CPU use of every foreign process is sampled from /proc
  (foreign_cpu_before).

Deviations from GAP_AUDIT Sec. 3.4 (recorded in the reports): S1's shield + decision replays the recorded shield
budgets (the closed loop reads them from the memoized latency profile); S1's lease and commit check use C1-sweep or
synthetic scenes, not the decision states.
"""
from __future__ import annotations

import os

for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ.setdefault(_v, '1')
os.environ['CUDA_VISIBLE_DEVICES'] = ''

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import platform  # noqa: E402
import random  # noqa: E402
import signal  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from collections import Counter  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

import numpy as np  # noqa: E402

from framelease_v2 import latency_agent as la  # noqa: E402
from framelease_v3.runtime import v3_commit as VC  # noqa: E402
from framelease_v3.runtime import v3_lease as VL  # noqa: E402
from framelease_v3.runtime import v3_scheduler as S  # noqa: E402
from framelease_v3.runtime import v3_shield as VS  # noqa: E402
from framelease_v4.arms import arms_v4 as AV  # noqa: E402
from framelease_v4.arms import metrics_v4 as MV  # noqa: E402
from framelease_v4.arms import runtime_v4 as RV  # noqa: E402
from framelease_v4.protocol import registration as REG  # noqa: E402
from framelease_v4.rl import behaviour as BH  # noqa: E402
from framelease_v4.rl import common as C  # noqa: E402
from framelease_v4.rl import prefix_score as PS  # noqa: E402
from framelease_v4.rl import qnet as Q  # noqa: E402

SCHEMA = 'framelease_v4.stress_bench/1'
OUT_DIR = ROOT / 'outputs/framelease_v4/stress'
LEASE_PARAMS = ROOT / AV.LEASE_PARAMS_REL
DEFAULT_ENVELOPE = ROOT / 'outputs/framelease_v4/envelopes/E5.json'
RECORDED_ROOTS = (ROOT / 'outputs/framelease_v4/tuning', ROOT / 'outputs/framelease_v4/rl_data')
DEV_QNETS = tuple(ROOT / f'outputs/framelease_v4/rl_dev/smoke_20261110/qnet_{f}.json'
                  for f in ('fqi', 'bandit', 'fqi_nolease'))
OUT_ALLOWED = ('outputs/framelease_v4/stress', 'outputs/framelease_v4/build')     # inside the project: only here
CODE_FILES = ('framelease_v4/protocol/stress_bench.py', 'framelease_v3/runtime/v3_commit.py',
              'framelease_v3/runtime/v3_scheduler.py', 'framelease_v3/runtime/v3_shield.py',
              'framelease_v3/runtime/v3_lease.py', 'framelease_v2/latency_agent.py', 'framelease_v4/arms/runtime_v4.py',
              'framelease_v4/rl/qnet.py', 'framelease_v4/rl/features.py', 'framelease_v4/rl/behaviour.py')

SLACK_GRID_MS = tuple(range(-100, 601, 10))          # [-0.1, 0.6] s in 10 ms steps (Sec. 7.6, S2)
RELATIVE_OFFSETS_MS = tuple(range(-100, 601, 10))    # delta = D* - t - f(state): [-0.1, 0.6] s in 10 ms (Amendment A7)
S2_GRIDS = ('registered', 'relative')                # s2 --grid; the registered grid is the default
SUPPLEMENTARY_LABEL = 'supplementary: S2 relative to the slack floor'
FLOOR_TOL = 1e-9                                     # |s - floor_a| <= FLOOR_TOL: the Eq. 5 boundary, not judged
LOADS = (0, 4, 8, 15)                                # background busy processes (Sec. 7.6, S1)
S3_MIN_SEQUENCES = 100_000                           # Sec. 7.6, S3
S3_SEED = 20261111
SYNTH_SEED = 20261111
MAX_DEPTH = 10                                       # shield depth limit of every shield arm (Sec. 2.4)
EYE4 = np.eye(4)
BOUND_KEYS = ('L_pi', 'L_refine', 'L_refresh', 'L_commit', 'eps')
COUPLE_TOL = 1e-9
MARGIN_TOL = 1e-9


def label_for(test, registered):
    return f'registered {test} run (PROTOCOL Sec. 7.6)' if registered else f'development run, not the registered {test}'


def relative_label(registered):
    """Label of an S2 report on the grid relative to the slack floor (Amendment A7): always supplementary, never the
    registered S2 grid."""
    if registered:
        return f'{SUPPLEMENTARY_LABEL} (registered run, PROTOCOL Sec. 7.6, Amendment A7; never in place of the S2 grid)'
    return f'{SUPPLEMENTARY_LABEL}; {label_for("S2", False)}'


def rel(path):
    p = Path(path).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def provenance():
    from framelease_v4.rl import bench_qnet as BQ
    return {'utc': C.utc_stamp(), 'argv': list(sys.argv), 'python': platform.python_version(), 'numpy': np.__version__,
            'cpu': BQ.cpu_model(), 'nproc': os.cpu_count(), 'loadavg': list(os.getloadavg()), 'niceness': os.nice(0),
            'threads': {v: os.environ.get(v) for v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')},
            'cuda_visible_devices': os.environ.get('CUDA_VISIBLE_DEVICES'),
            'code_sha256': {f: C.sha256_file(ROOT / f) for f in CODE_FILES}}


def _stats(seconds):
    a = np.asarray(seconds, dtype=np.float64) * 1e6
    if a.size == 0:
        return {'n': 0, 'p50_us': None, 'p99_us': None, 'max_us': None, 'mean_us': None}
    return {'n': int(a.size), 'p50_us': float(np.percentile(a, 50)), 'p99_us': float(np.percentile(a, 99)),
            'max_us': float(a.max()), 'mean_us': float(a.mean())}


def manifest_files(manifest=REG.MANIFEST):
    """Resolved paths of every file of the registration manifest (registration.read_manifest), wherever they lie."""
    return {(Path(f) if Path(f).is_absolute() else ROOT / f).resolve() for f in REG.read_manifest(manifest)}


def check_out_path(path, force=False, manifest=REG.MANIFEST):
    """A report path (symlinks resolved), by whitelist: inside the project only under OUT_ALLOWED
    (outputs/framelease_v4/stress/ and outputs/framelease_v4/build/), otherwise outside it; never a file of the
    registration manifest. An existing file is overwritten only with force and only if it is a stress_bench report
    (JSON 'schema' SCHEMA)."""
    p = Path(path).resolve()
    try:
        r = p.relative_to(ROOT).as_posix()
    except ValueError:
        r = None
    if r is not None and not any(r.startswith(a + '/') for a in OUT_ALLOWED):
        raise PermissionError(f'stress_bench writes inside the project only under {", ".join(OUT_ALLOWED)}: {r}')
    if p in manifest_files(manifest):
        raise PermissionError(f'{p} is a registered file (registration manifest); stress_bench never writes it')
    if p.exists():
        if not force:
            raise FileExistsError(f'{p} exists (use --force to overwrite a stress_bench report)')
        try:
            schema = C.read_json(p).get('schema') if p.is_file() else None
        except (OSError, ValueError, AttributeError):
            schema = None
        if schema != SCHEMA:
            raise PermissionError(f'{p} is not a stress_bench report (schema {SCHEMA}); --force never overwrites it')
    return p


def write_report(path, report, force=False):
    p = check_out_path(path, force)
    return C.atomic_json(p, report)


def lease_env(envelope=None):
    """LeaseEnv of the shield arms: the registered v2 q95 lease-parameter file (ego shape, constants T_pred 3.0,
    T_c 0.5, d_safe 0.5, delta 0.2, H_bar 2.5) and optionally an envelope file (E5 / E10 / B0 = L*)."""
    return VL.build_lease_env(str(LEASE_PARAMS), str(envelope) if envelope else None)


_CFG = {}


def runtime_config(kappa=1.0):
    """RuntimeConfig of the shield arms (arms_v4.SHIELD_RUNTIME: max_age_s 2.5, profile_quantile 0.99) at kappa."""
    k = float(kappa)
    cfg = _CFG.get(k)
    if cfg is None:
        cfg = _CFG[k] = la.RuntimeConfig(**{**AV.SHIELD_RUNTIME, 'kappa': k}).validate()
    return cfg


# ============================================================================================ decision states (S-1)

class ReplayPolicy(S.ShieldedHeuristicPolicy):
    """The deployed shielded policy replayed on a decision state: decide() is ShieldedHeuristicPolicy.decide unchanged
    (shield, features, Eq. 8 with the utility, bookkeeping, decision_wall_s); bounds() returns the state's own shield
    budgets (set in state_bounds before each call) instead of reading the live latency profile."""

    def __init__(self, env, utility='heuristic'):
        super().__init__(env=env, utility=utility)
        self.state_bounds = None

    def bounds(self, job, ctx):
        return self.state_bounds


def _deadline(x):
    """A logged deadline as v3_shield reads it: None / NaN is -inf (no active candidate)."""
    if x is None:
        return -math.inf
    v = float(x)
    return -math.inf if v != v else v


def _nan(x):
    return math.nan if x is None else float(x)


LAST_VALIDITY_KEYS = (('lease_s', 'cand_lease_s'), ('n_relevant', 'n_relevant'), ('n_confident', 'n_confident'),
                      ('n_computed', 'n_computed'), ('margin0_m', 'margin0_m'), ('g0_m', 'g0_m'),
                      ('min_g_m', 'min_g_m'), ('tau_star_s', 'tau_star_s'))


def state_from_row(row, source=None):
    """The replay state of one logged shield decision row (v3 schema, decisions.jsonl)."""
    f = row['features']
    sh = row['shield']
    b = row['bounds']
    t = float(row['sim_s'])
    a = row.get('active')
    age = f.get('active_age_s')
    newest_age = f.get('newest_frame_age_s')
    ep = f.get('episode_time_s')
    return {
        't': t, 'job_id': int(row['job_id']), 'obs_id': int(row['obs_id']), 'capture_s': float(row['capture_s']),
        'depth': int(row['depth']), 'at_max_depth': bool(row.get('at_max_depth')),
        'D_star': sh.get('D_star'), 'D_cand': sh.get('D_cand'),
        'last_validity': {k: f.get(src) for k, src in LAST_VALIDITY_KEYS},
        'last_step_cost_s': f.get('last_step_cost_s'), 'last_prefix_cost_s': f.get('last_prefix_cost_s'),
        'plan_delta_m': f.get('plan_delta_m'), 'ego_speed_mps': f.get('ego_speed_mps'),
        'active': None if a is None else {
            'job_id': int(a['job_id']), 'obs_id': int(a['obs_id']), 'depth': int(a['depth']),
            'capture_s': (t - float(age)) if age is not None else t, 'lease_s': f.get('active_lease_s')},
        'newest': None if newest_age is None else {
            'obs_id': int(row['obs_id']) + int(f.get('newer_frames') or 0), 'capture_s': t - float(newest_age),
            'speed_mps': f.get('newest_speed_mps')},
        'kappa': float(f['kappa']) if f.get('kappa') is not None else 1.0,
        'episode_start_s': (t - float(ep)) if ep is not None else 0.0,
        'bounds': {k: float(b[k]) for k in BOUND_KEYS},
        'source': source, 'row': row}


def make_job_ctx(st, D_star, D_cand):
    """(job, ctx): the v2 / v3 runtime objects ShieldedHeuristicPolicy.decide reads, rebuilt from a state."""
    t = st['t']
    obs = la.Observation(st['obs_id'], st['capture_s'], EYE4, _nan(st['ego_speed_mps']), 0.0, 4)
    step_cost = st['last_step_cost_s']
    if st['plan_delta_m'] is not None:
        p1, p2 = np.zeros((6, 2)), np.zeros((6, 2))
        p2[0, 0] = float(st['plan_delta_m'])
        steps = [{'plan': p1, 'timeline_cost_s': step_cost}, {'plan': p2, 'timeline_cost_s': step_cost}]
    else:
        steps = [{'plan': None, 'timeline_cost_s': step_cost}]
    job = la.Job(job_id=st['job_id'], obs=obs, start_s=st['capture_s'], phase='step', depth=st['depth'],
                 prefix={'timeline_cost_s': st['last_prefix_cost_s']}, steps=steps, last_deadline_s=D_cand,
                 last_validity=dict(st['last_validity']))
    a = st['active']
    inc = None
    if a is not None:
        inc = la.Candidate(job_id=a['job_id'], obs=la.Observation(a['obs_id'], a['capture_s'], EYE4, math.nan, 0.0, 4),
                           depth=a['depth'], plan_xy=None, release_s=t, dets=None, deadline_s=D_star,
                           validity={'lease_s': a['lease_s']})
    n = st['newest']
    newest = None if n is None else la.Observation(n['obs_id'], n['capture_s'], EYE4, _nan(n['speed_mps']), 0.0, 4)
    ctx = la.PolicyContext(now_s=t, newest_obs=newest, incumbent=inc, job=job, last_job=None, idle_since_s=t,
                           profile=None, config=runtime_config(st['kappa']), latest_dets=None, prev_dets=None,
                           episode_start_s=st['episode_start_s'])
    return job, ctx


def is_coupled(st):
    """D_cand = D* in the state: the running job's newest candidate is the active one (S2 moves D_cand with D*)."""
    D_star, D_cand = _deadline(st['D_star']), _deadline(st['D_cand'])
    return math.isfinite(D_star) and math.isfinite(D_cand) and abs(D_cand - D_star) <= COUPLE_TOL


def replay(policy, st, slack_s=None):
    """One decide() on the state, with D* moved to t + slack_s if given (D_cand with it if it equals D*).

    Returns (decision row, coupled, D*, D_cand)."""
    t = st['t']
    D_star, D_cand = _deadline(st['D_star']), _deadline(st['D_cand'])
    coupled = False
    if slack_s is not None:
        coupled = is_coupled(st)
        D_star = t + float(slack_s)
        if coupled:
            D_cand = D_star
    job, ctx = make_job_ctx(st, D_star, D_cand)
    policy.state_bounds = VS.ShieldBounds(**st['bounds'])
    policy.decide(job, ctx, at_max_depth=st['at_max_depth'])
    row = policy.pending_rows[-1]
    policy.pending_rows.clear()
    return row, coupled, D_star, D_cand


def synthetic_states(n, seed=SYNTH_SEED):
    """n random decision states (replay format) over the shield arms' operating range."""
    rng = random.Random(seed)
    out = []
    for i in range(int(n)):
        kappa = rng.choice((1.0, 1.5, 2.0))
        t = rng.uniform(1.0, 200.0)
        depth = rng.randint(1, MAX_DEPTH)
        L_pi = rng.uniform(0.0008, 0.004)
        L_refine = kappa * rng.uniform(0.012, 0.03)
        L_refresh = kappa * rng.uniform(0.38, 1.0) + L_refine + 2.0 * L_pi
        L_commit = rng.uniform(0.002, 0.01)
        prefix_cost = kappa * rng.uniform(0.38, 0.95)
        step_cost = L_refine * rng.uniform(0.6, 1.0)
        capture = t - (prefix_cost + depth * step_cost + rng.uniform(0.0, 0.08))
        obs_id = 20 * i + 1000
        active = None
        D_star = None
        if rng.random() < 0.97:
            D_star = t + rng.uniform(-0.3, 2.5)
            same = rng.random() < 0.5
            a_capture = capture if same else capture - rng.uniform(0.05, 2.0)
            active = {'job_id': i + 1 if same else i, 'obs_id': obs_id if same else obs_id - rng.randint(1, 40),
                      'depth': rng.randint(1, depth) if same else rng.randint(1, MAX_DEPTH), 'capture_s': a_capture,
                      'lease_s': max(0.0, D_star - a_capture)}
        coupled = D_star is not None and rng.random() < 0.5
        D_cand = D_star if coupled else capture + rng.uniform(0.0, 2.5)
        newer = 0 if rng.random() < 0.1 else rng.randint(1, 24)
        n_rel = rng.randint(0, 30)
        speed = rng.uniform(0.0, 15.0)
        out.append({
            't': t, 'job_id': i + 1, 'obs_id': obs_id, 'capture_s': capture, 'depth': depth,
            'at_max_depth': depth == MAX_DEPTH, 'D_star': D_star, 'D_cand': D_cand,
            'last_validity': {'lease_s': max(0.0, D_cand - capture), 'n_relevant': n_rel,
                              'n_confident': rng.randint(0, n_rel), 'n_computed': rng.randint(0, n_rel),
                              'margin0_m': None if n_rel == 0 else rng.uniform(-0.5, 20.0),
                              'g0_m': None if n_rel == 0 else rng.uniform(-1.0, 15.0),
                              'min_g_m': None if n_rel == 0 else rng.uniform(-1.0, 10.0),
                              'tau_star_s': None if n_rel == 0 or rng.random() < 0.5 else rng.uniform(0.0, 3.0)},
            'last_step_cost_s': step_cost, 'last_prefix_cost_s': prefix_cost,
            'plan_delta_m': None if depth == 1 else rng.uniform(0.0, 1.5), 'ego_speed_mps': speed,
            'active': active,
            'newest': {'obs_id': obs_id + newer, 'capture_s': t - rng.uniform(0.0, 0.05) if newer else capture,
                       'speed_mps': speed + rng.uniform(-0.5, 0.5)},
            'kappa': kappa, 'episode_start_s': rng.uniform(0.0, max(capture, 0.0)),
            'bounds': {'L_pi': L_pi, 'L_refine': L_refine, 'L_refresh': L_refresh, 'L_commit': L_commit, 'eps': 0.05},
            'source': f'synthetic:{seed}:{i}', 'row': None})
    meta = {'source': 'synthetic', 'seed': int(seed), 'n': len(out),
            'generator': 'stress_bench.synthetic_states (kappa 1.0/1.5/2.0, depth 1-10, D* - t in [-0.3, 2.5] s, '
                         'active candidate in 97%, D_cand = D* in half, newer frames 0-24)'}
    return out, meta


def unfinished_reason(run_dir):
    """None for a finished run with a valid official route record (PROTOCOL Sec. 8.4: exactly one record,
    prefix_score.official_record; entry_status 'Finished'; no execution-failure status, metrics_v4), else why the run
    is not taken (an aborted or still running attempt, or one that the retry rule repeats)."""
    try:
        rec = PS.official_record(run_dir)
        entry = C.read_json(Path(run_dir) / 'raw' / 'official_results.json').get('entry_status')
    except (OSError, ValueError, AttributeError) as e:
        return f'no single official route record ({type(e).__name__}: {e})'
    if entry != 'Finished':
        return f'entry_status {entry!r}'
    status = str(rec.get('status'))
    if any(m in status for m in MV.EXECUTION_FAILURE_STATUS):
        return f'no valid record: route status {status!r}'
    return None


def recorded_states(roots=RECORDED_ROOTS, allow_test_routes=False, max_states=None, seed=SYNTH_SEED):
    """Shield decision states of the finished runs under roots (read-only). Refuses held-out test routes and runs
    whose route cannot be identified (fail closed, Sec. 9.11); skips unfinished runs (unfinished_reason) and
    unreadable decision logs, both listed in the metadata."""
    from framelease_v4.rl import dataset as DS
    test_routes = C.test_route_ids()
    states, runs, skipped, unreadable = [], [], [], []
    for rd in DS.discover_runs([r for r in roots if Path(r).exists()]):
        cfg = C.read_json(rd / 'config.json')
        route_id = (cfg.get('route') or {}).get('route_id')
        if route_id is None or str(route_id).strip() in ('', 'None'):
            raise PermissionError(f'{rd}: config.json names no route id; the held-out-route guard (PROTOCOL Sec. '
                                  f'9.11) cannot be applied; refusing')
        route = str(route_id)
        if route in test_routes and not allow_test_routes:
            raise PermissionError(f'{rd}: route {route} is a held-out test route (PROTOCOL Sec. 9.11); refusing')
        why = unfinished_reason(rd)
        if why is not None:
            skipped.append({'run_dir': rel(rd), 'reason': why})
            continue
        path = rd / 'raw' / 'agent' / 'framelease' / 'decisions.jsonl'
        if not path.is_file():
            continue
        try:
            logged = C.read_jsonl(path)
        except (OSError, ValueError) as e:
            unreadable.append({'run_dir': rel(rd), 'reason': f'{type(e).__name__}: {e}'})
            continue
        rows = [r for r in logged if r.get('kind') == 'decision' and isinstance(r.get('shield'), dict)
                and isinstance(r.get('bounds'), dict) and isinstance(r.get('features'), dict)]
        v4 = cfg.get('v4') or {}
        agent = cfg.get('agent_config') or v4.get('agent') or {}
        runs.append({'run_dir': rel(rd), 'arm': cfg.get('v4_arm') or v4.get('arm') or cfg.get('arm'),
                     'kind': cfg.get('kind') or v4.get('kind'), 'route_id': route, 'kappa': cfg.get('kappa'),
                     'utility': (agent.get('policy_params') or {}).get('utility'),
                     'shield_rows': len(rows), 'decisions_sha256': C.sha256_file(path)})
        states.extend(state_from_row(r, f'{rel(rd)}#{r.get("epoch")}') for r in rows)
    n_all = len(states)
    if max_states is not None and n_all > int(max_states):
        keep = sorted(random.Random(seed).sample(range(n_all), int(max_states)))
        states = [states[i] for i in keep]
    meta = {'source': 'recorded', 'roots': [rel(r) for r in roots], 'runs': runs, 'n_available': n_all,
            'n': len(states), 'sample_seed': int(seed) if max_states is not None and n_all > int(max_states) else None,
            'allow_test_routes': bool(allow_test_routes), 'skipped_unfinished': skipped,
            'skipped_unreadable': unreadable}
    return states, meta


def replay_fidelity(states, env, tol=1e-9):
    """Unmoved replay of recorded states vs their logged rows (feasible set, Eq. 5 sums, 32 features, action)."""
    pol = ReplayPolicy(env, 'heuristic')
    n = feas_bad = lhs_bad = act_n = act_bad = 0
    feat_bad, feat_max = Counter(), {}
    for st in states:
        row0 = st.get('row')
        if row0 is None:
            continue
        row = replay(pol, st)[0]
        n += 1
        feas_bad += int(list(row['feasible']) != list(row0['feasible']))
        sh0, sh = row0['shield'], row['shield']
        lhs_bad += int(any(abs(float(sh[k]) - float(sh0[k])) > tol
                           for k in ('refine_lhs', 'refresh_lhs', 'refine_cand_lhs')))
        if len(row0['feasible']) < 2 or str(row0.get('reason')) == 'both_feasible:heuristic':
            act_n += 1
            act_bad += int(row['action'] != row0['action'])
        for k in S.FEATURE_NAMES:
            x, y = row['features'].get(k), row0['features'].get(k)
            if (x is None) != (y is None):
                feat_bad[k] += 1
                continue
            if x is None:
                continue
            d = abs(float(x) - float(y))
            feat_max[k] = max(feat_max.get(k, 0.0), d)
            if d > tol * max(1.0, abs(float(y))):
                feat_bad[k] += 1
    return {'n': n, 'feasible_mismatch': feas_bad, 'shield_sum_mismatch': lhs_bad, 'action_compared': act_n,
            'action_mismatch': act_bad, 'feature_mismatch': dict(feat_bad), 'feature_max_abs_diff': feat_max,
            'tolerance': tol, 'ok': n == 0 or (feas_bad == 0 and lhs_bad == 0 and act_bad == 0 and not feat_bad)}


def load_states(kind, n_states, roots=None, allow_test_routes=False, seed=SYNTH_SEED):
    if kind == 'synthetic':
        return synthetic_states(n_states, seed)
    return recorded_states(roots or RECORDED_ROOTS, allow_test_routes, n_states, seed)


# ============================================================================================ Q-networks

def describe_qnet(path):
    """Spec (verified: schema, weights sha256, name) and identity of a deployed network file."""
    spec = Q.load_spec(path)
    return {'path': rel(path), 'abs_path': str(Path(path).resolve()), 'file_sha256': C.sha256_file(path),
            'name': spec['name'], 'weights_sha256': spec['weights_sha256'],
            'family': (spec.get('candidate') or {}).get('family'), 'n_inputs': len(spec['feature_columns']),
            'feature_columns': list(spec['feature_columns']), 'a_det_depth': int(spec['a_det']['depth']),
            'supported': list(spec['supported']), 'budget_s': float(spec.get('policy_budget_s', 1e-4)),
            'layers': [[len(L['W']), len(L['W'][0])] for L in spec['layers']], 'spec': spec}


def qnet_policy(net, env):
    """A ReplayPolicy whose utility is the network, built through the agent's path: the name registered by
    behaviour.register_utility_name, the file found through $FRAMELEASE_V4_QNET (sha256-checked by QUtility)."""
    os.environ[Q.ENV_QNET] = net['abs_path']
    BH.register_utility_name(net['name'])
    return ReplayPolicy(env, utility=net['name'])


def _public(net):
    return {k: v for k, v in net.items() if k not in ('spec', 'abs_path')}


# ============================================================================================ S2

S2_VIOLATIONS = ('admitted_bound_ge_Dstar', 'admitted_commit_bound_ge_Dstar', 'expectation_bound_mismatch',
                 'admitted_refine_cand_bound_ge_Dcand', 'admitted_refine_at_max_depth',
                 'admitted_refresh_without_newer_frame', 'feasible_action_not_taken',
                 'utility_calls_not_equal_choice_epochs', 'utility_called_outside_choice_epochs')


def s2_check(row, st, D_star, D_cand, policy, c, v):
    """Counts of one replayed decision and the independent Eq. 5 checks of an admitted action."""
    feasible = tuple(row['feasible'])
    action = row['action']
    admitted = bool(row['admitted'])
    c['epochs'] += 1
    c['admitted'] += int(admitted)
    c['both'] += int(len(feasible) == 2)
    c['feasible:' + ('+'.join(feasible) or 'none')] += 1
    c['action:' + action] += 1
    t, b = st['t'], st['bounds']
    if admitted:
        if action == VS.REFINE:
            bound = t + b['L_pi'] + b['L_refine'] + b['L_commit'] + (b['L_refresh'] + b['L_commit']) + b['eps']
            commit_bound = t + b['L_pi'] + b['L_refine'] + b['L_commit']
            cand_bound = t + b['L_pi'] + b['L_refine'] + b['L_commit'] + b['eps']
            v['admitted_refine_cand_bound_ge_Dcand'] += int(not cand_bound < D_cand)
            v['admitted_refine_at_max_depth'] += int(not st['depth'] < MAX_DEPTH)
        else:
            bound = t + b['L_pi'] + b['L_refresh'] + b['L_commit'] + 0.0 + b['eps']
            commit_bound = t + b['L_pi'] + b['L_refresh'] + b['L_commit']
            newer = st['newest'] is not None and st['newest']['obs_id'] > st['obs_id']
            v['admitted_refresh_without_newer_frame'] += int(not newer)
        v['admitted_bound_ge_Dstar'] += int(not bound < D_star)
        v['admitted_commit_bound_ge_Dstar'] += int(not commit_bound < D_star)
        exp = policy.expectation
        v['expectation_bound_mismatch'] += int(exp is None or abs(float(exp['bound_s']) - commit_bound) > 1e-12)
    elif feasible:
        v['feasible_action_not_taken'] += 1


def _bypass_rates(bypass, n_select):
    """Q-network bypass rate over the choice epochs: every reason, the near-deadline part (a shield margin below
    B_pi; deterministic) and the CPU-timing part (overrun, disabled; depends on the machine load, see S1)."""
    if not n_select:
        return {'bypass_rate': None, 'bypass_rate_slack': None, 'bypass_rate_timing': None}
    return {'bypass_rate': sum(bypass.values()) / n_select, 'bypass_rate_slack': bypass.get('slack', 0) / n_select,
            'bypass_rate_timing': (bypass.get('overrun', 0) + bypass.get('disabled', 0)) / n_select}


def slack_floor(st):
    """Eq. 5 floors of the slack s = D* - t of a state (the deployed ShieldBounds sums of Sec. 2.4): action a can be
    admitted only at s > floor_a. None: at no slack (REFRESH without a newer frame; REFINE at the depth limit, or with
    a D_cand that does not move with D* and that the candidate bound already misses)."""
    b = VS.ShieldBounds(**st['bounds'])
    newer = st['newest'] is not None and st['newest']['obs_id'] > st['obs_id']
    refresh = b.L_pi + b.L_refresh + b.L_commit + b.R_refresh + b.eps if newer else None
    refine = None
    if st['depth'] < MAX_DEPTH:
        refine = b.L_pi + b.L_refine + b.L_commit + b.R_refine + b.eps
        if not is_coupled(st) and not st['t'] + b.L_pi + b.L_refine + b.L_commit + b.eps < _deadline(st['D_cand']):
            refine = None
    finite = [x for x in (refine, refresh) if x is not None]
    return {'REFINE': refine, 'REFRESH': refresh, 'any': min(finite) if finite else None}


def _spread(xs):
    a = np.asarray(xs, dtype=np.float64)
    if a.size == 0:
        return None
    return {'min': float(a.min()), 'p50': float(np.percentile(a, 50)), 'max': float(a.max())}


def _kappa_key(st):
    return str(float(st['kappa']))


def slack_floor_summary(states, slack_ms=SLACK_GRID_MS):
    """Per kappa: the spread of the swept states' slack floors (slack_floor) and the number of grid values at or below
    every state's floor, where no action can be admitted for any state of that kappa."""
    grid = [ms / 1000.0 for ms in slack_ms]
    by = {}
    for st in states:
        by.setdefault(_kappa_key(st), []).append(slack_floor(st))
    out = {}
    for k, fl in sorted(by.items()):
        any_f = [f['any'] for f in fl if f['any'] is not None]
        lowest = min(any_f) if any_f else math.inf
        out[k] = {'n_states': len(fl), 'never_admissible': len(fl) - len(any_f), 'floor_any_s': _spread(any_f),
                  'floor_refresh_s': _spread([f['REFRESH'] for f in fl if f['REFRESH'] is not None]),
                  'floor_refine_s': _spread([f['REFINE'] for f in fl if f['REFINE'] is not None]),
                  'grid_values_at_or_below_every_floor': sum(1 for s in grid if not s > lowest)}
    return out


def _by_kappa(rows):
    """Per kappa over the slack grid of one network: epochs, admitted actions (each checked against Eq. 5), the share
    admitted, the grid values that admit nothing, and the first grid value that admits an action."""
    out = {}
    for k in sorted({k for r in rows for k in r['epochs_by_kappa']}):
        ep = sum(r['epochs_by_kappa'].get(k, 0) for r in rows)
        ad = sum(r['admitted_by_kappa'].get(k, 0) for r in rows)
        hits = [r['slack_s'] for r in rows if r['admitted_by_kappa'].get(k, 0) > 0]
        out[k] = {'epochs': ep, 'admitted': ad, 'share_admitted': ad / ep if ep else None,
                  'grid_values_admitting_nothing': len(rows) - len(hits),
                  'first_admitting_slack_s': min(hits) if hits else None}
    return out


def run_s2(states, nets, env, slack_ms=SLACK_GRID_MS, progress=None):
    usable = [st for st in states if st['active'] is not None and math.isfinite(_deadline(st['D_star']))]
    coupled = sum(1 for st in usable if is_coupled(st))
    out = {'n_states': len(states), 'n_swept': len(usable),
           'skipped_without_active_candidate': len(states) - len(usable), 'coupled_states': coupled,
           'slack_grid_s': [ms / 1000.0 for ms in slack_ms], 'slack_floor': slack_floor_summary(usable, slack_ms),
           'networks': {}}
    total_v = 0
    for net in nets:
        rows, tot, tv, byp = [], Counter(), Counter({k: 0 for k in S2_VIOLATIONS}), Counter()
        t0 = time.perf_counter()
        for ms in slack_ms:
            s = ms / 1000.0
            pol = qnet_policy(net, env)
            c, v, ck = Counter(), Counter({k: 0 for k in S2_VIOLATIONS}), Counter()
            for st in usable:
                row, _, D_star, D_cand = replay(pol, st, s)
                s2_check(row, st, D_star, D_cand, pol, c, v)
                ck[('epochs', _kappa_key(st))] += 1
                ck[('admitted', _kappa_key(st))] += int(bool(row['admitted']))
            u = pol.utility
            v['utility_calls_not_equal_choice_epochs'] += int(u.n_select != c['both'])
            v['utility_called_outside_choice_epochs'] += int(u.n_not_both)
            bypass = dict(u.bypass)
            nb = sum(bypass.values())
            rows.append({'slack_s': s, 'epochs': c['epochs'], 'admitted': c['admitted'],
                         'share_admitted': c['admitted'] / c['epochs'] if c['epochs'] else None,
                         'p_both': c['both'] / c['epochs'] if c['epochs'] else None,
                         'feasible': {k.split(':', 1)[1]: n for k, n in c.items() if k.startswith('feasible:')},
                         'actions': {k.split(':', 1)[1]: n for k, n in c.items() if k.startswith('action:')},
                         'epochs_by_kappa': {k: n for (w, k), n in sorted(ck.items()) if w == 'epochs'},
                         'admitted_by_kappa': {k: n for (w, k), n in sorted(ck.items()) if w == 'admitted'},
                         'select_calls': u.n_select, 'network_calls': u.n_calls, 'bypass': bypass,
                         **_bypass_rates(bypass, u.n_select), 'network_disabled': u.disabled,
                         'violations': dict(v)})
            tot.update({'epochs': c['epochs'], 'admitted': c['admitted'], 'both': c['both'],
                        'select_calls': u.n_select, 'network_calls': u.n_calls})
            byp.update(bypass)
            tv.update(v)
            if progress:
                progress(f's2 {net["name"]} slack {s:+.2f} s: share admitted '
                         f'{rows[-1]["share_admitted"]}, bypass {nb}/{u.n_select}, violations {sum(v.values())}')
        nv = int(sum(tv.values()))
        total_v += nv
        out['networks'][net['name']] = {
            **_public(net), 'per_slack': rows, 'epochs': tot['epochs'], 'admitted': tot['admitted'],
            'share_admitted': tot['admitted'] / tot['epochs'] if tot['epochs'] else None, 'by_kappa': _by_kappa(rows),
            'select_calls': tot['select_calls'], 'network_calls': tot['network_calls'], 'bypass': dict(byp),
            **_bypass_rates(byp, tot['select_calls']),
            'admitted_bound_ge_Dstar': tv['admitted_bound_ge_Dstar'], 'violations': dict(tv), 'violations_total': nv,
            'wall_s': time.perf_counter() - t0}
    out['violations_total'] = total_v
    out['pass'] = total_v == 0
    return out


# ============================================================================================ S2, supplementary grid

def predicted_feasible(floor, slack, tol=FLOOR_TOL):
    """A_feas that the Eq. 5 floors of a state (slack_floor) predict at slack s: every action a with floor_a < s, in
    the shield's order. None where s lies within tol of a floor: the boundary, where the strict Eq. 5 comparison of
    t + s with the shield's own sum is decided by floating-point rounding."""
    out = []
    for a in (VS.REFINE, VS.REFRESH):
        f = floor[a]
        if f is None:
            continue
        if abs(slack - f) <= tol:
            return None
        if slack > f:
            out.append(a)
    return out


def _kappa_part(c, v, sel, bypass):
    """One kappa's counts at one offset (or summed over the offsets) of run_s2_relative."""
    return {'epochs': c['epochs'], 'admitted': c['admitted'],
            'share_admitted': c['admitted'] / c['epochs'] if c['epochs'] else None,
            'admitted_bound_ge_Dstar': v['admitted_bound_ge_Dstar'], 'select_calls': sel, 'bypass': dict(bypass),
            **_bypass_rates(bypass, sel), 'violations': dict(v)}


def _relative_by_kappa(rows):
    """Per kappa over the offsets of one network: the counts summed over the offsets, the offsets that admit nothing,
    the first admitting offset and the first offset from which every swept state of the kappa admits an action at
    every larger offset."""
    out = {}
    for k in sorted({k for r in rows for k in r['by_kappa']}):
        parts = [(r['delta_s'], r['by_kappa'][k]) for r in rows if k in r['by_kappa']]
        c = Counter(epochs=sum(p['epochs'] for _, p in parts), admitted=sum(p['admitted'] for _, p in parts))
        v, byp = Counter(), Counter()
        for _, p in parts:
            v.update(p['violations'])
            byp.update(p['bypass'])
        all_from = None
        for d, p in reversed(parts):
            if p['epochs'] == 0 or p['admitted'] < p['epochs']:
                break
            all_from = d
        hits = [d for d, p in parts if p['admitted'] > 0]
        out[k] = {**_kappa_part(c, v, sum(p['select_calls'] for _, p in parts), byp),
                  'offsets_admitting_nothing': len(parts) - len(hits),
                  'first_admitting_offset_s': min(hits) if hits else None,
                  'every_state_admits_from_offset_s': all_from}
    return out


def run_s2_relative(states, nets, env, offsets_ms=RELATIVE_OFFSETS_MS, progress=None):
    """Supplementary S2 (Amendment A7): the sweep and checks of run_s2 on a grid relative to each state's own Eq. 5
    slack floor f(state) = slack_floor(state)['any'] (the first-admissible slack): D* = t + f(state) + delta for every
    offset delta, D_cand moving with D* exactly as in the registered sweep (replay). States without an active
    candidate are skipped as in run_s2; a state that admits no action at any slack has no floor and is counted
    (no_floor), not swept. Per network and offset, and per kappa: the share admitted, the admitted actions whose bound
    >= D* (must be 0), the Q-network bypass rate and its near-deadline and CPU-timing parts. floor_check compares the
    feasible set of every replay with the one the per-action floors predict (predicted_feasible)."""
    usable = [st for st in states if st['active'] is not None and math.isfinite(_deadline(st['D_star']))]
    floors = [slack_floor(st) for st in usable]
    swept = [(st, fl, _kappa_key(st)) for st, fl in zip(usable, floors) if fl['any'] is not None]
    kappas = sorted({k for _, _, k in swept})
    out = {'grid': 'relative_to_floor', 'n_states': len(states), 'n_swept': len(swept),
           'skipped_without_active_candidate': len(states) - len(usable), 'no_floor': len(usable) - len(swept),
           'coupled_states': sum(1 for st, _, _ in swept if is_coupled(st)),
           'offsets_s': [ms / 1000.0 for ms in offsets_ms], 'slack_floor': slack_floor_summary(usable),
           'state_floors': [{'source': st['source'], 'kappa': _kappa_key(st), 'f_s': fl['any'],
                             'refine_s': fl['REFINE'], 'refresh_s': fl['REFRESH']} for st, fl in zip(usable, floors)],
           'networks': {}}
    total_v, floor_ok = 0, True
    for net in nets:
        rows, tot, tv, byp, fc = [], Counter(), Counter({k: 0 for k in S2_VIOLATIONS}), Counter(), Counter()
        t0 = time.perf_counter()
        for ms in offsets_ms:
            d = ms / 1000.0
            pol = qnet_policy(net, env)
            u = pol.utility
            cb = {k: Counter() for k in kappas}
            vb = {k: Counter({x: 0 for x in S2_VIOLATIONS}) for k in kappas}
            sb, bb = Counter(), {k: Counter({r: 0 for r in u.bypass}) for k in kappas}
            n_mis = 0
            for st, fl, k in swept:
                sel0, byp0 = u.n_select, dict(u.bypass)
                s = fl['any'] + d
                row, _, D_star, D_cand = replay(pol, st, s)
                s2_check(row, st, D_star, D_cand, pol, cb[k], vb[k])
                sb[k] += u.n_select - sel0
                bb[k].update({r: n - byp0[r] for r, n in u.bypass.items()})
                pred = predicted_feasible(fl, s)
                if pred is None:
                    fc['boundary'] += 1
                else:
                    fc['judged'] += 1
                    n_mis += int(list(row['feasible']) != pred)
            c, v = Counter(), Counter({k: 0 for k in S2_VIOLATIONS})
            for k in kappas:
                c.update(cb[k])
                v.update(vb[k])
            v['utility_calls_not_equal_choice_epochs'] += int(u.n_select != c['both'])
            v['utility_called_outside_choice_epochs'] += int(u.n_not_both)
            fc['mismatch'] += n_mis
            bypass = dict(u.bypass)
            rows.append({'delta_s': d, 'epochs': c['epochs'], 'admitted': c['admitted'],
                         'share_admitted': c['admitted'] / c['epochs'] if c['epochs'] else None,
                         'p_both': c['both'] / c['epochs'] if c['epochs'] else None,
                         'feasible': {x.split(':', 1)[1]: n for x, n in c.items() if x.startswith('feasible:')},
                         'actions': {x.split(':', 1)[1]: n for x, n in c.items() if x.startswith('action:')},
                         'select_calls': u.n_select, 'network_calls': u.n_calls, 'bypass': bypass,
                         **_bypass_rates(bypass, u.n_select), 'network_disabled': u.disabled,
                         'admitted_bound_ge_Dstar': v['admitted_bound_ge_Dstar'], 'floor_mismatch': n_mis,
                         'violations': dict(v),
                         'by_kappa': {k: _kappa_part(cb[k], vb[k], sb[k], bb[k]) for k in kappas}})
            tot.update({'epochs': c['epochs'], 'admitted': c['admitted'], 'both': c['both'],
                        'select_calls': u.n_select, 'network_calls': u.n_calls})
            byp.update(bypass)
            tv.update(v)
            if progress:
                progress(f's2 relative {net["name"]} offset {d:+.2f} s: share admitted {rows[-1]["share_admitted"]}, '
                         f'bypass {sum(bypass.values())}/{u.n_select}, violations {sum(v.values())}, '
                         f'floor mismatches {n_mis}')
        nv = int(sum(tv.values()))
        total_v += nv
        floor_ok = floor_ok and fc['mismatch'] == 0
        out['networks'][net['name']] = {
            **_public(net), 'per_offset': rows, 'epochs': tot['epochs'], 'admitted': tot['admitted'],
            'share_admitted': tot['admitted'] / tot['epochs'] if tot['epochs'] else None,
            'by_kappa': _relative_by_kappa(rows), 'select_calls': tot['select_calls'],
            'network_calls': tot['network_calls'], 'bypass': dict(byp), **_bypass_rates(byp, tot['select_calls']),
            'admitted_bound_ge_Dstar': tv['admitted_bound_ge_Dstar'], 'violations': dict(tv), 'violations_total': nv,
            'floor_check': {'judged': fc['judged'], 'boundary': fc['boundary'], 'mismatch': fc['mismatch'],
                            'tolerance_s': FLOOR_TOL, 'ok': fc['mismatch'] == 0},
            'wall_s': time.perf_counter() - t0}
    out['violations_total'] = total_v
    out['floor_check_ok'] = floor_ok
    out['pass'] = total_v == 0 and floor_ok
    return out


# ============================================================================================ S3

INVARIANTS = {
    'commit_of_cancelled_candidate': 'Eq. 9 (1): a candidate of a closed job (REFRESH / end of job) or an explicitly '
                                     'cancelled candidate is committed (late completion of a cancelled job)',
    'commit_of_invalid_plan': 'Eq. 9 (2): a non-finite or kinematically implausible plan is committed',
    'commit_of_non_newer_version': 'Eq. 9 (3): the committed version is not newer than the latest commit (older '
                                   'observation, or same observation not deeper; duplicate release)',
    'commit_at_or_after_deadline': 'Eq. 9 (4): t_commit >= D, or D is NaN (expired candidate)',
    'commit_with_margin_at_or_below_delta': 'Eq. 9 (5): M(t_commit - t_k) <= delta at commit',
    'committed_versions_not_increasing': 'committed versions of a sequence do not strictly increase',
    'spurious_rejection': 'an admissible candidate (all five checks pass) is rejected',
    'wrong_rejection_reason': 'the logged reason is not the first failing check in the order of Sec. 2.4',
    'accepted_with_wrong_reason': 'an accepted candidate carries a reason other than accepted',
    'gate_runtime_out_of_sync': 'runtime target: the runtime\'s latest commit and the gate\'s latest version differ',
    'deadline_not_eq3': 'runtime target: the released candidate\'s deadline is not t_k + H of its lease (Eq. 3)',
    'commit_record_mismatch': 'runtime target: the step record\'s commit block disagrees with the commit decision',
    'tracked_at_or_after_deadline': 'runtime target: the watchdog lets the controller track a plan at t >= D',
    'tracked_not_latest_commit': 'runtime target: the tracked plan is not the latest commit',
    'fallback_with_valid_commit': 'runtime target: full-brake fallback while the latest commit is still valid'}
GATE_INVARIANTS = tuple(list(INVARIANTS)[:9])
RUNTIME_INVARIANTS = tuple(INVARIANTS)
INVALID_PLAN_KINDS = ('shape_or_nonfinite', 'speed_limit', 'accel_limit')
P_SAME_OBS, P_DELAYED, P_STALE_CLOCK, P_PLAN_INVALID, P_MARGIN_FLAG_FAIL = 0.05, 1.0 / 3.0, 0.2, 0.05, 0.05
P_LEASE_NAN, P_LEASE_OVERLONG, P_LEASE_SHORT, P_QUERY = 0.005, 0.10, 0.05, 0.25
P_DEADLINE_TIE = 0.02                                # offers committed exactly at t_commit = D (Eq. 9 (4) boundary)
COVERAGE_KEYS = {
    'gate': ('accepted', 'late_completion_of_closed_job', 'explicitly_cancelled_candidate',
             'older_observation_after_newer_commit', 'not_deeper_version', 'duplicate_release', 'expired',
             'deadline_tie', 'nan_deadline', 'invalid_plan', 'margin_failure', 'out_of_order_commit_time'),
    'runtime': ('accepted', 'late_completion_of_closed_job', 'older_observation_after_newer_commit',
                'not_deeper_version', 'duplicate_release', 'expired', 'deadline_tie', 'nan_deadline', 'invalid_plan',
                'margin_failure', 'overlong_lease', 'out_of_order_commit_time', 'watchdog_queries', 'watchdog_track')}


@dataclass
class SynthCandidate:
    """One released candidate (job, depth) of a random sequence."""
    job: int
    obs_id: int
    depth: int
    capture_s: float
    release_s: float
    deliver_s: float
    lease_true_s: float      # exact lease of the margin functions (Eq. 2 closed form)
    lease_s: float           # reported lease H (exact, over-long, short or NaN)
    lease_kind: str
    tau_star_s: float
    plan_kind: str           # ok | shape_or_nonfinite | speed_limit | accel_limit
    plan_speed: float
    margin_ok: bool          # gate target: the commit-time margin flag
    agents: tuple            # runtime target: margin functions ('lin', c, s) or ('vee', m, a, tau0)

    @property
    def deadline_s(self):
        return self.capture_s + self.lease_s           # Eq. 3; LeaseResult.as_validity computes the same sum


def _agents(rng, tau_star, tau, delta):
    """Margin functions g_j(tau) whose first delta-crossing is exactly tau_star (inf: none crosses on the grid)."""
    out = []
    finite = math.isfinite(tau_star)
    if finite:
        if rng.random() < 0.5:
            s = rng.uniform(0.5, 6.0)
            out.append(('lin', delta + s * tau_star, s))                   # g = delta + s (tau* - tau)
        else:
            t0 = float(tau[min(int(np.searchsorted(tau, tau_star)), len(tau) - 1)])
            a = rng.uniform(0.5, 5.0)
            out.append(('vee', delta - a * (t0 - tau_star), a, t0))        # minimum on a grid point, crosses at tau*
    for _ in range(rng.randint(0, 2)):
        r = rng.random()
        if r < 0.4:                                                        # crosses later (or beyond the grid)
            later = (tau_star if finite else float(tau[-1])) + rng.uniform(0.05, 3.0)
            s = rng.uniform(0.2, 4.0)
            out.append(('lin', delta + s * later, s))
        elif r < 0.7:                                                      # passes by above delta
            out.append(('vee', delta + rng.uniform(0.01, 3.0), rng.uniform(0.5, 5.0),
                        float(tau[rng.randrange(len(tau))])))
        else:                                                              # moving away
            out.append(('lin', delta + rng.uniform(0.01, 5.0), -rng.uniform(0.0, 2.0)))
    rng.shuffle(out)
    return tuple(out)


def g_matrix(agents, tau):
    if not agents:
        return np.zeros((0, len(tau)))
    return np.vstack([ag[1] - ag[2] * tau if ag[0] == 'lin' else ag[1] + ag[2] * np.abs(tau - ag[3]) for ag in agents])


def margin_oracle(agents, age_s, t_c, t_last):
    """M(Delta) of Eq. 1 from the analytic margin functions (piecewise linear: the minimum over [Delta, Delta + T_c]
    is at an end or at a V's apex), with LeaseResult.margin's conventions outside the grid (independent code)."""
    a, b = max(float(age_s), 0.0), float(age_s) + float(t_c)
    if b > t_last + 1e-9:
        return -math.inf
    if not agents:
        return math.inf
    b = min(b, t_last)
    m = math.inf
    for ag in agents:
        if ag[0] == 'lin':
            v = min(ag[1] - ag[2] * a, ag[1] - ag[2] * b)
        else:
            mm, sl, t0 = ag[1], ag[2], ag[3]
            v = mm if a <= t0 <= b else min(mm + sl * abs(a - t0), mm + sl * abs(b - t0))
        m = min(m, v)
    return m


def synth_plan(kind, speed):
    """6 x 2 plan along +y: constant speed (ok / speed_limit), a 15 m/s speed jump (accel_limit), or a NaN entry."""
    v = np.array([speed] * 3 + [speed + 15.0] * 3) if kind == 'accel_limit' else np.full(6, float(speed))
    p = np.stack([np.zeros(6), np.cumsum(v * la.PLAN_DT_S)], -1).astype(np.float32)
    if kind == 'shape_or_nonfinite':
        p[3, 1] = np.nan
    return p


def lease_result(c, env):
    """The scripted LeaseResult of a candidate: reported lease H, its margin functions sampled on the tau grid."""
    cfg = env.cfg
    h = c.lease_s
    reason = 'synthetic_nan' if h != h else ('horizon_cap' if h >= cfg.h_bar_s else
                                             ('immediate_failure' if h <= 0.0 else 'first_failure'))
    return VL.LeaseResult(h, c.tau_star_s, reason, {'n_relevant': len(c.agents), 'lease_kind': c.lease_kind},
                          env.tau, g_matrix(c.agents, env.tau), None, None, cfg.t_pred_s)


def generate_sequence(rng, env):
    """(candidates, events) of one random sequence. Events: (kind, payload, t_commit, duplicate, out_of_order,
    t_query) with kind offer (payload SynthCandidate), close (job) or cancel ((job, depth))."""
    cfg, tau = env.cfg, env.tau
    t_c, h_bar, delta = cfg.t_c_s, cfg.h_bar_s, cfg.delta_m
    n_jobs = rng.randint(1, 5)
    cands = []
    t = 0.0
    obs_id = rng.randint(0, 3)
    capture = 0.0
    for j in range(1, n_jobs + 1):
        start = t + rng.uniform(0.0, 0.3)
        same = j > 1 and rng.random() < P_SAME_OBS
        if not same:
            obs_id += rng.randint(1, 4) if j > 1 else 0
            capture = start - rng.uniform(0.0, 0.05)
        prefix, step = rng.uniform(0.35, 1.0), rng.uniform(0.012, 0.03)
        for d in range(1, rng.randint(1, MAX_DEPTH) + 1):
            release = start + prefix + step * d
            deliver = release + (rng.uniform(0.0, 1.5) if rng.random() < P_DELAYED else 0.0)
            r = rng.random()
            h_true = 0.0 if r < 0.1 else (h_bar if r < 0.3 else rng.uniform(0.0, h_bar))
            if h_true >= h_bar:
                tau_star = math.inf
            elif h_true <= 0.0:
                tau_star = rng.uniform(0.0, t_c)
            else:
                tau_star = h_true + t_c
            agents = _agents(rng, tau_star, tau, delta) if (math.isfinite(tau_star) or rng.random() < 0.7) else ()
            r = rng.random()
            if r < P_LEASE_NAN:
                lease, kind = math.nan, 'nan'
            elif r < P_LEASE_NAN + P_LEASE_OVERLONG and h_true < h_bar:
                lease, kind = min(h_bar, h_true + rng.uniform(0.02, 1.0)), 'overlong'
            elif r < P_LEASE_NAN + P_LEASE_OVERLONG + P_LEASE_SHORT and h_true > 0.0:
                lease, kind = h_true * rng.random(), 'short'
            else:
                lease, kind = h_true, 'exact'
            pk = rng.choice(INVALID_PLAN_KINDS) if rng.random() < P_PLAN_INVALID else 'ok'
            speed = rng.uniform(45.0, 80.0) if pk == 'speed_limit' else rng.uniform(0.0, 20.0)
            cands.append(SynthCandidate(j, obs_id, d, capture, release, deliver, h_true, lease, kind, tau_star, pk,
                                        speed, rng.random() >= P_MARGIN_FLAG_FAIL, agents))
        t = start + rng.uniform(0.0, 1.2)
    ev = [['offer', c, c.deliver_s, False] for c in cands]
    if rng.random() < 0.5:
        rng.shuffle(ev)                                                   # out-of-order delivery ...
    else:
        ev.sort(key=lambda e: e[2])                                       # ... or in delivery-time order
    for j in range(1, n_jobs):                                            # REFRESH ends job j before job j + 1 releases
        if rng.random() < 0.7:
            pos = next((i for i, e in enumerate(ev) if e[0] == 'offer' and e[1].job == j + 1), len(ev))
            ev.insert(pos, ['close', j, None, False])
    for _ in range(rng.randint(0, 2)):
        ev.insert(rng.randrange(len(ev) + 1), ['close', rng.randint(1, n_jobs), None, False])
    for _ in range(rng.randint(0, 2)):
        ev.insert(rng.randrange(len(ev) + 1), ['cancel', (rng.randint(1, n_jobs), rng.randint(1, MAX_DEPTH)), None,
                                               False])
    if rng.random() < 0.3:                                                # duplicate releases, later
        for _ in range(rng.randint(1, 2)):
            i = rng.choice([k for k, e in enumerate(ev) if e[0] == 'offer'])
            c = ev[i][1]
            ev.insert(rng.randint(i + 1, len(ev)), ['offer', c, c.deliver_s + rng.uniform(0.0, 1.0), True])
    closes = [k for k, e in enumerate(ev) if e[0] == 'close']
    if closes and rng.random() < 0.3:                                     # late completion right after a close
        i = rng.choice(closes)
        c = rng.choice([x for x in cands if x.job == ev[i][1]])
        ev.insert(i + 1, ['offer', c, c.deliver_s + rng.uniform(0.0, 1.0), True])
    clock, events = 0.0, []
    for kind, x, deliver, dup in ev:
        if kind == 'offer':
            t_commit = deliver if rng.random() < P_STALE_CLOCK else max(deliver, clock)    # stale clocks, as in v3
            if rng.random() < P_DEADLINE_TIE and x.deadline_s == x.deadline_s:
                t_commit = x.deadline_s                                                 # exactly at the deadline
            events.append(['offer', x, t_commit, dup, t_commit < clock])
            clock = max(clock, t_commit)
        else:
            events.append([kind, x, None, False, False])
        events[-1].append(clock + rng.uniform(0.0, 0.5) if rng.random() < P_QUERY else None)
    return cands, [tuple(e) for e in events]


class S3Tally:
    """Coverage and violation counts of one target over all sequences."""

    def __init__(self, target):
        self.target = target
        names = GATE_INVARIANTS if target == 'gate' else RUNTIME_INVARIANTS
        self.viol = Counter({k: 0 for k in names})
        self.cov = Counter()
        self.reasons = Counter()
        self.expected = Counter()
        self.wall_s = 0.0

    def judge(self, c, t_commit, ok, reason, closed, cancelled, last, margin_state, dup, ooo):
        """One offer: the oracle's Eq. 9 decision in the order of Sec. 2.4 vs the target's (ok, reason).

        last: (obs_id, depth) of the target's latest commit; margin_state True / False / None (ambiguous)."""
        cov, viol = self.cov, self.viol
        closed_job = c.job in closed
        is_cancelled = closed_job or (c.job, c.depth) in cancelled
        invalid = c.plan_kind != 'ok'
        older = last is not None and c.obs_id < last[0]
        not_deeper = last is not None and c.obs_id == last[0] and c.depth <= last[1]
        D = c.deadline_s
        expired = D != D or not t_commit < D
        if is_cancelled:
            exp = 'cancelled'
        elif invalid:
            exp = 'invalid:' + c.plan_kind
        elif older:
            exp = 'stale_version:older_observation'
        elif not_deeper:
            exp = 'stale_version:not_deeper'
        elif expired:
            exp = 'expired_before_commit'
        elif margin_state is None:
            exp = None
        elif not margin_state:
            exp = 'margin_violated_at_commit'
        else:
            exp = 'accepted'
        cov['offers'] += 1
        cov['duplicate_release'] += int(dup)
        cov['late_completion_of_closed_job'] += int(closed_job)
        cov['explicitly_cancelled_candidate'] += int(not closed_job and is_cancelled)
        cov['older_observation_after_newer_commit'] += int(exp == 'stale_version:older_observation')
        cov['not_deeper_version'] += int(exp == 'stale_version:not_deeper')
        cov['expired'] += int(exp == 'expired_before_commit')
        cov['deadline_tie'] += int(exp == 'expired_before_commit' and t_commit == D)
        cov['nan_deadline'] += int(D != D)
        cov['invalid_plan'] += int(invalid)
        cov['margin_failure'] += int(exp == 'margin_violated_at_commit')
        cov['overlong_lease'] += int(c.lease_kind == 'overlong')
        cov['out_of_order_commit_time'] += int(ooo)
        cov['ambiguous_margin'] += int(exp is None)
        self.expected[exp or 'ambiguous'] += 1
        self.reasons[reason] += 1
        if ok:
            cov['accepted'] += 1
            viol['commit_of_cancelled_candidate'] += int(is_cancelled)
            viol['commit_of_invalid_plan'] += int(invalid)
            viol['commit_of_non_newer_version'] += int(older or not_deeper)
            viol['commit_at_or_after_deadline'] += int(expired)
            viol['commit_with_margin_at_or_below_delta'] += int(margin_state is False)
            viol['accepted_with_wrong_reason'] += int(reason != 'accepted')
        elif exp == 'accepted':
            viol['spurious_rejection'] += 1
        elif reason != (exp or 'margin_violated_at_commit'):
            viol['wrong_rejection_reason'] += 1

    def check_versions(self, versions):
        for a, b in zip(versions, versions[1:]):
            self.viol['committed_versions_not_increasing'] += int(not (b[0] > a[0] or (b[0] == a[0] and b[1] > a[1])))

    def report(self, n_sequences):
        need = max(1, int(n_sequences) // 100)
        keys = COVERAGE_KEYS[self.target]
        nv = int(sum(self.viol.values()))
        return {'sequences': int(n_sequences), 'offers': self.cov['offers'], 'accepted': self.cov['accepted'],
                'rejections_by_reason': {k: n for k, n in sorted(self.reasons.items()) if k != 'accepted'},
                'expected_by_reason': dict(sorted(self.expected.items())), 'coverage': dict(sorted(self.cov.items())),
                'coverage_min': need, 'coverage_ok': all(self.cov[k] >= need for k in keys),
                'coverage_keys': list(keys), 'violations': dict(self.viol), 'violations_total': nv,
                'wall_s': self.wall_s}


def run_gate_sequence(events, tally, gate_factory=VC.CommitGate):
    """S3 target 'gate': the events against a fresh CommitGate."""
    gate = gate_factory()
    closed, cancelled = set(), set()
    last, versions = None, []
    for kind, x, t_commit, dup, ooo, _query in events:
        if kind == 'close':
            gate.close_job(x)
            closed.add(x)
            continue
        if kind == 'cancel':
            gate.cancel(*x)
            cancelled.add(x)
            continue
        c = x
        valid = c.plan_kind == 'ok'
        ok, reason = gate.offer(c.job, VC.Version(c.obs_id, c.depth), c.deadline_s, t_commit,
                                (valid, 'ok' if valid else c.plan_kind), c.margin_ok)
        tally.judge(c, t_commit, ok, reason, closed, cancelled, last, c.margin_ok, dup, ooo)
        if ok:
            last = (c.obs_id, c.depth)
            versions.append(last)
    tally.check_versions(versions)


class ScriptedLeasePolicy(S.ShieldedHeuristicPolicy):
    """The shield arms' v3 policy with each candidate's lease scripted: compute_lease returns the sequence's
    LeaseResult; validity(), margin_check() and every other method are the deployed code."""

    def __init__(self, env):
        super().__init__(env=env)
        self.scripted = {}

    def compute_lease(self, cand):
        return self.scripted[(cand.job_id, cand.depth)]


class NullBackend:
    """Model backend of the commit-path runs: nothing runs on a GPU; release() is a no-op."""

    def release(self, state):
        return None


class NullLogger(la.MemoryLogger):
    """Logger that keeps nothing (1e5 sequences)."""

    def write(self, stream, row):
        return None


def run_runtime_sequence(cands, events, policy, env, tally, runtime_cls=RV.V4Runtime):
    """S3 target 'runtime': the events through the V4Runtime commit path (a fresh runtime per sequence)."""
    rt = runtime_cls(NullBackend(), policy, runtime_config(1.0), NullLogger())
    t_c, delta, t_last = env.cfg.t_c_s, env.cfg.delta_m, float(env.tau[-1])
    jobs = {}
    for c in cands:
        if c.job not in jobs:
            jobs[c.job] = la.Job(job_id=c.job, obs=la.Observation(c.obs_id, c.capture_s, EYE4, 0.0, 0.0, 4),
                                 start_s=c.capture_s, phase='step')
    closed, last, last_cand, versions = set(), None, None, []
    viol, cov = tally.viol, tally.cov
    clock = 0.0
    for kind, x, t_commit, dup, ooo, t_query in events:
        if kind == 'close':
            rt._end_job(jobs[x], clock, 'stress_close')
            closed.add(x)
        elif kind == 'cancel':
            cov['cancel_events_not_applicable'] += 1           # the runtime cancels whole jobs only
        else:
            c = x
            clock = max(clock, t_commit)
            job = jobs[c.job]
            cand = la.Candidate(job_id=c.job, obs=job.obs, depth=c.depth, plan_xy=synth_plan(c.plan_kind, c.plan_speed),
                                release_s=c.release_s, dets=None)
            policy.scripted[(c.job, c.depth)] = lease_result(c, env)
            # release section of LatencyRuntime._complete_op: validity of the released candidate, then the commit
            validity = dict(policy.validity(cand, rt._ctx(c.release_s, job)))
            cand.deadline_s = float(validity['deadline_s'])
            cand.validity = validity
            job.last_deadline_s = cand.deadline_s
            job.last_validity = validity
            rec = {'depth': c.depth}
            try:
                kind_, _, data = rt._try_commit(job, cand, t_commit, rec)
            except RuntimeError:
                viol['gate_runtime_out_of_sync'] += 1
                break
            ok = kind_ == 'commit'
            reason = 'accepted' if ok else data['reason']
            viol['commit_record_mismatch'] += int(rec['commit']['accepted'] != ok or rec['commit']['reason'] != reason)
            D = c.deadline_s
            same_deadline = cand.deadline_s == D or (D != D and cand.deadline_s != cand.deadline_s)
            viol['deadline_not_eq3'] += int(not same_deadline)
            M = margin_oracle(c.agents, float(t_commit) - float(c.capture_s), t_c, t_last)
            margin_state = None if abs(M - delta) <= MARGIN_TOL else bool(M > delta)
            tally.judge(c, t_commit, ok, reason, closed, (), last, margin_state, dup, ooo)
            if ok:
                last, last_cand = (c.obs_id, c.depth), cand
                versions.append(last)
                viol['gate_runtime_out_of_sync'] += int(rt.latest_committed() is not cand)
            viol['gate_runtime_out_of_sync'] += int(rt.gate.latest != (None if last is None else VC.Version(*last)))
        if t_query is not None:
            ref = rt.control_reference(t_query, la.Observation(10 ** 9, t_query, EYE4, 0.0, 0.0, 4))
            cov['watchdog_queries'] += 1
            valid_now = last_cand is not None and t_query + la.EPS_S < float(last_cand.deadline_s)
            if ref['mode'] == 'track':
                cov['watchdog_track'] += 1
                inc = ref['incumbent']
                viol['tracked_at_or_after_deadline'] += int(not t_query + la.EPS_S < float(inc.deadline_s))
                viol['tracked_not_latest_commit'] += int(inc is not last_cand)
            else:
                viol['fallback_with_valid_commit'] += int(valid_now)
    tally.check_versions(versions)


def run_s3(n_sequences=S3_MIN_SEQUENCES, seed=S3_SEED, targets=('gate', 'runtime'), progress=None,
           gate_factory=VC.CommitGate, runtime_cls=RV.V4Runtime, policy_cls=ScriptedLeasePolicy):
    """S3 on n random sequences; every sequence is run against each target."""
    env = lease_env()
    rng = random.Random(seed)
    tallies = {t: S3Tally(t) for t in targets}
    policy = policy_cls(env) if 'runtime' in targets else None
    pc = time.perf_counter
    t_start = pc()
    for i in range(int(n_sequences)):
        cands, events = generate_sequence(rng, env)
        for t in targets:
            t0 = pc()
            if t == 'gate':
                run_gate_sequence(events, tallies[t], gate_factory)
            else:
                run_runtime_sequence(cands, events, policy, env, tallies[t], runtime_cls)
            tallies[t].wall_s += pc() - t0
        if progress and (i + 1) % 10000 == 0:
            progress(f's3 {i + 1}/{n_sequences} sequences, {pc() - t_start:.0f} s, violations ' +
                     ', '.join(f'{t}={sum(tallies[t].viol.values())}' for t in targets))
    reports = {t: tallies[t].report(n_sequences) for t in targets}
    total = sum(r['violations_total'] for r in reports.values())
    return {'targets': reports, 'violations_total': int(total), 'pass': total == 0,
            'coverage_ok': all(r['coverage_ok'] for r in reports.values()), 'wall_s': pc() - t_start,
            'lease_constants': {'t_c_s': env.cfg.t_c_s, 'delta_m': env.cfg.delta_m, 'h_bar_s': env.cfg.h_bar_s,
                                't_pred_s': env.cfg.t_pred_s},
            'generator': {'seed': int(seed), 'p_same_observation': P_SAME_OBS, 'p_delayed': P_DELAYED,
                          'p_stale_clock': P_STALE_CLOCK, 'p_plan_invalid': P_PLAN_INVALID,
                          'p_margin_flag_fail': P_MARGIN_FLAG_FAIL, 'p_lease_nan': P_LEASE_NAN,
                          'p_lease_overlong': P_LEASE_OVERLONG, 'p_lease_short': P_LEASE_SHORT,
                          'p_watchdog_query': P_QUERY, 'p_deadline_tie': P_DEADLINE_TIE,
                          'margin_ambiguity_tol': MARGIN_TOL}}


# ============================================================================================ S1

# A busy process spins and ends by itself when its parent (the bench) is gone or after argv[1] seconds, so an
# interrupted bench never leaves spinning processes behind (they run in their own session).
BUSY_CODE = ('import os, sys, time\n'
             'parent, end = os.getppid(), time.monotonic() + float(sys.argv[1])\n'
             'while os.getppid() == parent and time.monotonic() < end:\n'
             '    for _ in range(20000):\n'
             '        pass\n')
BUSY_MAX_S = 3600.0
BLOCKING_MARKERS = ('gpu_queue', 'CarlaUE4', 'leaderboard_evaluator', 'run_closed_loop', 'p1_driver', 'launch_queue',
                    'disk_watchdog', 'autoresume', 'framelease_v4/rl/', 'p3_rl')


def blocking_processes(markers=BLOCKING_MARKERS, proc_root='/proc'):
    """Processes whose command line names a runner, the simulator, a stage driver or an RL job (S1 needs the CPU)."""
    me = os.getpid()
    out = []
    for d in Path(proc_root).iterdir():
        if not d.name.isdigit() or int(d.name) == me:
            continue
        try:
            cmd = (d / 'cmdline').read_bytes().replace(b'\0', b' ').decode('utf-8', 'replace').strip()
        except OSError:
            continue
        hits = [m for m in markers if m in cmd]
        if hits:
            out.append({'pid': int(d.name), 'markers': hits, 'cmdline': cmd[:240]})
    return sorted(out, key=lambda r: r['pid'])


CPU_SAMPLE_S = 2.0                                   # /proc sampling window of the foreign-CPU check
FOREIGN_CPU_MIN_SHARE = 0.05                         # a foreign process using >= 5% of one core is listed


def _cpu_ticks(proc_root='/proc'):
    """{pid: (utime + stime clock ticks, ppid, comm)} of every process (/proc/<pid>/stat)."""
    out = {}
    for d in Path(proc_root).iterdir():
        if not d.name.isdigit():
            continue
        try:
            s = (d / 'stat').read_text(encoding='utf-8', errors='replace')
            i = s.rindex(')')
            f = s[i + 2:].split()
            out[int(d.name)] = (int(f[11]) + int(f[12]), int(f[1]), s[s.index('(') + 1:i])
        except (OSError, ValueError, IndexError):
            continue
    return out


def foreign_cpu(sample_s=CPU_SAMPLE_S, min_share=FOREIGN_CPU_MIN_SHARE, exclude=(), proc_root='/proc',
                sleep=time.sleep):
    """Processes other than this bench, its children (the busy processes) and exclude that used >= min_share of one
    core over sample_s seconds (/proc/<pid>/stat utime + stime): CPU load from outside the bench, e.g. another
    project on the machine, which blocking_processes does not see. None if sample_s <= 0 (not sampled)."""
    if sample_s <= 0:
        return None
    me, skip = os.getpid(), {int(p) for p in exclude}
    hz = float(os.sysconf('SC_CLK_TCK'))
    t0 = time.monotonic()
    a = _cpu_ticks(proc_root)
    sleep(sample_s)
    b = _cpu_ticks(proc_root)
    dt = max(time.monotonic() - t0, float(sample_s))
    out = []
    for pid, (ticks, ppid, comm) in b.items():
        if pid == me or ppid == me or pid in skip or pid not in a:
            continue
        share = (ticks - a[pid][0]) / hz / dt
        if share >= min_share:
            try:
                cmd = (Path(proc_root) / str(pid) / 'cmdline').read_bytes().replace(b'\0', b' ')
                cmd = cmd.decode('utf-8', 'replace').strip() or f'[{comm}]'
            except OSError:
                cmd = f'[{comm}]'
            out.append({'pid': pid, 'cpu_share': round(share, 4), 'comm': comm, 'cmdline': cmd[:240]})
    return sorted(out, key=lambda r: -r['cpu_share'])


def foreign_cpu_record(sample_s=CPU_SAMPLE_S, exclude=(), min_share=FOREIGN_CPU_MIN_SHARE):
    procs = foreign_cpu(sample_s, min_share, exclude)
    return {'sample_s': float(sample_s), 'min_share_of_one_core': min_share, 'processes': procs,
            'total_cpu_share': None if procs is None else round(sum(p['cpu_share'] for p in procs), 4)}


class BusyLoad:
    """n background busy processes (Python spin loops at the caller's priority) for the duration of a with-block;
    killed on exit, also on an exception, KeyboardInterrupt or (through cmd_s1's handler) SIGTERM. Each one also ends
    by itself when the bench process is gone or after max_s seconds."""

    def __init__(self, n, settle_s=2.0, python=sys.executable, max_s=BUSY_MAX_S):
        self.n, self.settle_s, self.python, self.max_s = int(n), float(settle_s), python, float(max_s)
        self.procs = []

    def command(self):
        return [self.python, '-I', '-B', '-c', BUSY_CODE, repr(self.max_s)]

    def pids(self):
        return [p.pid for p in self.procs]

    def __enter__(self):
        if self.n <= 0:
            return self
        env = dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
                   OPENBLAS_NUM_THREADS='1')
        try:
            for _ in range(self.n):
                self.procs.append(subprocess.Popen(self.command(), env=env, stdin=subprocess.DEVNULL,
                                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                                   start_new_session=True))
            time.sleep(self.settle_s)
            dead = [p.pid for p in self.procs if p.poll() is not None]
            if dead:
                raise RuntimeError(f'busy processes exited early: {dead}')
        except BaseException:
            self.stop()
            raise
        return self

    def stop(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
        for p in self.procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        self.procs = []

    def __exit__(self, *exc):
        self.stop()
        return False


def disable_index(walls, budget, window=Q.QUtility.WINDOW, min_calls=Q.QUtility.MIN_CALLS_TO_DISABLE,
                  rate=Q.QUtility.MAX_OVERRUN_RATE):
    """0-based call at which QUtility's rule (> 5% of the last 256 calls over B_pi, after >= 64 calls) would disable
    the network for the run, or None."""
    ring = [0] * window
    n_over = 0
    for i, w in enumerate(walls):
        k = i % window
        over = 1 if w > budget else 0
        n_over += over - ring[k]
        ring[k] = over
        if over and i + 1 >= min_calls and n_over > rate * min(i + 1, window):
            return i
    return None


def c1_scenes(max_clips=20, every=9):
    """Real scenes for the lease: model detections and the 10 candidate plans of C1-sweep frames."""
    from framelease_v3.runtime.tests import helpers_v3 as H3
    frames = H3.sweep_frames(max_clips=max_clips, every=every)
    scenes = [{'boxes': det, 'scores': score, 'labels': label, 'plans': [cands[d] for d in range(MAX_DEPTH)]}
              for det, score, label, cands, _p, _s in frames]
    return scenes, {'source': 'c1_sweep', 'dir': rel(H3.SWEEP_CLIPS), 'max_clips': max_clips, 'every': every,
                    'n': len(scenes)}


def synthetic_scenes(n=200, seed=SYNTH_SEED):
    """Synthetic scenes: framelease_v3 helpers_v3.random_scene detections (half near the ego) and random plans."""
    from framelease_v3.runtime.tests import helpers_v3 as H3
    rng = np.random.default_rng(seed)
    scenes = []
    for i in range(int(n)):
        boxes, scores, labels = H3.random_scene(rng, near=bool(i % 2))
        scenes.append({'boxes': boxes, 'scores': scores, 'labels': labels,
                       'plans': [H3.random_plan(rng) for _ in range(MAX_DEPTH)]})
    return scenes, {'source': 'synthetic', 'seed': int(seed), 'n': len(scenes)}


def lease_and_commit(scenes, env_lease, n, warm=200):
    """n lease computations (validity's own lease_wall_s) and commit checks (around V3Runtime._try_commit), one
    observation per scene, depths 1-10 released in order as in the closed loop."""
    policy = S.ShieldedHeuristicPolicy(env=env_lease)
    pc = time.perf_counter
    lease_w, commit_w, reasons = [], [], Counter()
    total = int(n) + int(warm)
    rt, i = None, 0
    while len(lease_w) < total:
        sc = scenes[i % len(scenes)]
        i += 1
        if rt is None or i % 200 == 0:
            rt = RV.V4Runtime(NullBackend(), policy, runtime_config(1.0), NullLogger())
        t = 0.5 * i
        obs = la.Observation(i, t, EYE4, 5.0, 0.0, 4)
        dets = la.DetectionSet(np.asarray(sc['boxes'], float), np.asarray(sc['scores'], float),
                               np.asarray(sc['labels']), None, True, i, t, EYE4)
        job = la.Job(job_id=i, obs=obs, start_s=t, dets=dets, phase='step')
        ctx = rt._ctx(t, job)
        policy.after_prefix(job, ctx)                    # agent preparation of the observation (not in lease_wall_s)
        for d in range(1, MAX_DEPTH + 1):
            release = t + 0.45 + 0.02 * d
            cand = la.Candidate(job_id=i, obs=obs, depth=d, plan_xy=np.asarray(sc['plans'][d - 1], np.float32),
                                release_s=release, dets=dets)
            validity = dict(policy.validity(cand, ctx))
            cand.deadline_s = float(validity['deadline_s'])
            cand.validity = validity
            job.last_deadline_s = cand.deadline_s
            job.last_validity = validity
            lease_w.append(policy.lease_wall_s[-1])
            rec = {'depth': d}
            t0 = pc()
            kind, _, data = rt._try_commit(job, cand, release + 0.003, rec)
            commit_w.append(pc() - t0)
            reasons['accepted' if kind == 'commit' else data['reason']] += 1
            if len(lease_w) >= total:
                break
    return lease_w[warm:], commit_w[warm:], dict(reasons)


def s1_feature_dicts(states, env):
    """The 32-feature dicts of the states (heuristic replay); choice-epoch states first (where the network runs)."""
    pol = ReplayPolicy(env, 'heuristic')
    both, other = [], []
    for st in states:
        row = replay(pol, st)[0]
        f = {k: row['features'][k] for k in S.FEATURE_NAMES}
        (both if row['p_both'] else other).append(f)
    return both or other


def s1_measure(nets, states, feats, scenes, env, env_lease, n_calls, n_lease, warm=1000):
    """One load level: the four components (see the module docstring)."""
    pc = time.perf_counter
    out = {'qnet_call': {}, 'shield_decision': {}}
    k = len(feats)
    for net in nets:
        qn = Q.QNetwork(net['spec'])
        for i in range(warm):
            qn.q_from_features(feats[i % k])
        walls = np.empty(int(n_calls))
        for i in range(int(n_calls)):
            f = feats[i % k]
            t0 = pc()
            q = qn.q_from_features(f)
            float(q[0])
            float(q[1])
            walls[i] = pc() - t0
        b = net['budget_s']
        out['qnet_call'][net['name']] = {**_stats(walls), 'budget_s': b, 'overruns': int((walls > b).sum()),
                                         'overrun_rate': float((walls > b).mean()),
                                         'would_disable_at_call': disable_index(walls, b)}
    ks = len(states)
    for label, mk in [('heuristic', lambda: ReplayPolicy(env, 'heuristic'))] + \
            [(net['name'], (lambda net=net: qnet_policy(net, env))) for net in nets]:
        pol = mk()
        for i in range(min(warm, int(n_calls))):
            replay(pol, states[i % ks])
        u = pol.utility
        byp0 = dict(getattr(u, 'bypass', {}) or {})
        pol.decision_wall_s.clear()
        both = np.zeros(int(n_calls), dtype=bool)
        for i in range(int(n_calls)):
            both[i] = bool(replay(pol, states[i % ks])[0]['p_both'])
        walls = np.asarray(pol.decision_wall_s, dtype=np.float64)
        byp = getattr(u, 'bypass', None)
        out['shield_decision'][label] = {
            'all': _stats(walls), 'choice_epochs': _stats(walls[both]), 'utility': u.name,
            'bypass': None if byp is None else {r: byp[r] - byp0.get(r, 0) for r in byp},
            'network_disabled': getattr(u, 'disabled', None)}
    lw, cw, reasons = lease_and_commit(scenes, env_lease, n_lease)
    out['lease'] = _stats(lw)
    out['commit_check'] = {**_stats(cw), 'outcomes': reasons}
    return out


def s1_plan(nets, states_meta, scenes_meta, loads, n_calls, n_lease, settle_s, env_lease_path, out_path,
            busy_max_s=BUSY_MAX_S, cpu_sample_s=CPU_SAMPLE_S):
    n_dec = (len(nets) + 1) * int(n_calls)
    est = settle_s + cpu_sample_s + len(nets) * n_calls * 15e-6 + n_dec * 120e-6 + n_lease * 1.5e-3
    blockers = blocking_processes()
    foreign = foreign_cpu_record(cpu_sample_s)
    return {'test': 'S1', 'loads': list(loads), 'busy_command': BusyLoad(0, max_s=busy_max_s).command(),
            'busy_max_s': float(busy_max_s), 'settle_s': settle_s,
            'components': {
                'qnet_call': f'{n_calls} calls per network (QUtility timed region), overrun rate vs B_pi',
                'shield_decision': f'{n_calls} ShieldedHeuristicPolicy.decide per utility (heuristic + '
                                   f'{len(nets)} networks), decision_wall_s',
                'lease': f'{n_lease} ShieldedHeuristicPolicy.validity (lease_wall_s), envelope {rel(env_lease_path)}',
                'commit_check': f'{n_lease} V3Runtime._try_commit on the same candidates'},
            'networks': [_public(n) for n in nets], 'states': states_meta, 'scenes': scenes_meta,
            'estimated_wall_s_without_contention': est * len(loads), 'blocking_processes': blockers,
            'would_refuse_busy_loads': bool(blockers), 'foreign_cpu': foreign,
            'cpu_affinity': sorted(os.sched_getaffinity(0)), 'out': str(out_path)}


def run_s1(nets, states, scenes, env, env_lease, loads=LOADS, n_calls=20000, n_lease=5000, settle_s=2.0,
           guard=True, warm=1000, progress=None, busy_max_s=BUSY_MAX_S, cpu_sample_s=CPU_SAMPLE_S,
           refuse_foreign=False):
    """S1 at each load level. Before each level the foreign CPU consumers are sampled (foreign_cpu, recorded as
    foreign_cpu_before); with refuse_foreign a level does not start while one uses CPU (RuntimeError)."""
    if refuse_foreign and cpu_sample_s <= 0:
        raise ValueError('refuse_foreign needs cpu_sample_s > 0')
    if guard:
        blockers = blocking_processes()
        if blockers:
            raise RuntimeError('S1 needs an exclusive CPU; running: ' +
                               '; '.join(f'{b["pid"]} {b["cmdline"][:80]}' for b in blockers))
    if int(n_calls) > 200000:
        raise ValueError('n_calls <= 200000 (decision_wall_s keeps the last 200000 calls)')
    feats = s1_feature_dicts(states, env)
    results = []
    for load in loads:
        if progress:
            progress(f's1 load {load}: starting')
        foreign = foreign_cpu_record(cpu_sample_s)
        if refuse_foreign and foreign['processes']:
            raise RuntimeError(f'S1 load {load}: foreign CPU consumers alive (S1 needs an exclusive CPU): ' +
                               '; '.join(f'{p["pid"]} {p["cpu_share"]:.2f} core {p["cmdline"][:80]}'
                                         for p in foreign['processes']))
        with BusyLoad(load, settle_s, max_s=busy_max_s) as busy:
            la0 = list(os.getloadavg())
            t0 = time.perf_counter()
            res = s1_measure(nets, states, feats, scenes, env, env_lease, n_calls, n_lease, warm)
            res.update(load=int(load), busy_pids=busy.pids(), loadavg_start=la0, loadavg_end=list(os.getloadavg()),
                       wall_s=time.perf_counter() - t0, foreign_cpu_before=foreign)
        results.append(res)
    return {'per_load': results, 'n_feature_dicts': len(feats)}


# ============================================================================================ CLI

def _log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', file=sys.stderr, flush=True)


def _default_out(test, registered, variant=None):
    """Default report path; variant 'relative' (S2 on the supplementary grid) names the file s2_relative_..."""
    stamp = C.utc_stamp()
    base = test.lower() + (f'_{variant}' if variant else '')
    name = f'{base}_registered_{stamp}.json' if registered else f'dev/{base}_dev_{stamp}.json'
    return OUT_DIR / name


NOTES = {
    'S3': ['Every sequence is run against both targets; the generator and its probabilities are in "generator".',
           'runtime target: V4Runtime has no single-candidate cancellation (REFRESH or the end of a job closes the '
           'whole job, V3Runtime._end_job); cancel events are counted as cancel_events_not_applicable and only closed '
           'jobs are cancelled there.',
           'runtime target: the lease of every candidate is scripted (ScriptedLeasePolicy.compute_lease); validity, '
           'D = t_k + H, the kinematic check, the margin check, the gate, job closing and the watchdog are deployed '
           'code.',
           'margin oracle: |M - delta| <= 1e-9 is ambiguous and judged neither way; coverage.ambiguous_margin counts '
           'the offers whose decision the margin alone would make (an earlier failing check decides the others).',
           'A share p_deadline_tie of the offers with a finite D is committed exactly at t_commit = D, the Eq. 9 (4) '
           'boundary; coverage.deadline_tie counts those that the deadline check decides (a gate accepting t_commit '
           '<= D fails commit_at_or_after_deadline).'],
    'S2': ['D* is moved to t + s; D_cand moves with it when D_cand = D* in the state (the active candidate is the '
           'running job\'s newest one: coupled_states), otherwise it keeps its value.',
           'States without an active candidate (before the first commit) have no D* and are skipped.',
           'A fresh policy, hence a fresh Q-network utility and overrun window, per network and slack value.',
           'share_admitted = decision epochs whose action lies in A_feas / decision epochs; it does not depend on the '
           'utility. The bound of an admitted action is the Eq. 5 sum t + L_pi + L_a + L_commit + R_a + eps.',
           'bypass_rate counts every reason over the choice epochs; bypass_rate_slack is the near-deadline part (a '
           'shield margin below B_pi, deterministic), bypass_rate_timing the CPU-timing part (overrun, disabled), '
           'which depends on the machine load (S1) and is not a near-deadline effect.',
           'Only D* (and a coupled D_cand) moves. The lease values of the state stay as logged: active_lease_s, '
           'cand_lease_s and tau_star_s (network inputs), so D = t_k + H (Eq. 3) does not hold in a moved state. The '
           'shield (Eq. 5), A_feas, share_admitted and every Eq. 5 check depend on D*, D_cand and the bounds only; '
           'the network\'s input, hence its choice inside A_feas, sees the logged lease values.',
           'slack_floor: per kappa, the Eq. 5 floors of the slack (an action is admitted only at s > L_pi + L_a + '
           'L_commit + R_a + eps) and the grid values at or below every state\'s floor; per network, by_kappa lists '
           'the admitted actions checked per kappa, the grid values that admit nothing and the first admitting slack. '
           'Where the floor lies above most of the registered grid, its lower values admit nothing and check no '
           'admitted action.'],
    'S2_relative': [
        'Supplementary (Amendment A7): the grid is relative to each state\'s own Eq. 5 slack floor f(state) = '
        'slack_floor(state)[\'any\'], the first-admissible slack (L_pi + L_a + L_commit + R_a + eps minimised over the '
        'actions the state can admit at some slack): D* = t + f(state) + delta for delta in offsets_s; D_cand moves '
        'with D* exactly as in the registered sweep. Reported as supplementary, never in place of the registered S2 '
        'grid (slack_grid_s, a separate run).',
        'A state with an active candidate that admits no action at any slack (no newer frame, and REFINE at the depth '
        'limit or its candidate bound already missing a fixed D_cand) has no floor: counted in no_floor, not swept. '
        'state_floors lists f(state) and the per-action floors of every state with an active candidate.',
        'per_offset and by_kappa give, per offset and per kappa, the share admitted, the admitted actions whose bound '
        '>= D* (must be 0), the Q-network bypass rate and its near-deadline (bypass_rate_slack) and CPU-timing '
        '(bypass_rate_timing) parts; every other S2 check of run_s2 applies unchanged (violations).',
        'floor_check: the feasible set of every replay equals the one the per-action floors predict (a in A_feas iff '
        'floor_a < f(state) + delta); replays within tolerance_s of a floor, among them every state at delta = 0, are '
        'the Eq. 5 boundary, decided by floating-point rounding of t + f(state) against the shield\'s own sum, and '
        'are counted as boundary, not judged. pass requires 0 violations and floor_check ok.',
        'slack_floor is the summary of the registered report (its grid_values_at_or_below_every_floor refers to the '
        'registered grid), given here for comparison.'],
    'S1': ['Deviation (GAP_AUDIT S-4): shield + decision replays ShieldedHeuristicPolicy.decide with the state\'s '
           'recorded shield budgets (the closed loop reads them from the memoized latency profile).',
           'Deviation (GAP_AUDIT S-4): decisions.jsonl logs no detections, so the lease and the commit check run on '
           'C1-sweep scenes (real model detections and candidate plans) or synthetic scenes.',
           'qnet_call is QUtility\'s timed region (featurize + forward + two reads) on choice-epoch feature dicts; '
           'would_disable_at_call applies QUtility\'s 5%-of-256 rule to the measured series.',
           'commit_check.outcomes include the 200 warm-up calls.',
           'blocking_processes sees only FrameLease runners, the simulator and RL jobs; foreign_cpu (plan) and '
           'foreign_cpu_before (each load level) list every other process that used >= min_share_of_one_core over '
           'sample_s (/proc utime + stime). A registered run refuses while one exists unless --accept-foreign-cpu '
           '(foreign_cpu_accepted).']}


def _header(test, registered):
    """Report header; the provenance (code sha256, load) is taken when the run starts."""
    return {'schema': SCHEMA, 'test': test, 'label': label_for(test, registered), 'registered': bool(registered),
            'protocol': 'framelease_v4/PROTOCOL.md Sec. 7.6 (Table II-B stress tests); Eq. 5 / Eq. 8 / Eq. 9 of '
                        'Sec. 2.4; Sec. 5.7 (budgeted CPU policy execution); Sec. 6.4',
            'notes': list(NOTES[test]), 'provenance': provenance()}


def _finish(head):
    head['provenance'].update(finished_utc=C.utc_stamp(), loadavg_end=list(os.getloadavg()))
    return head


def cmd_s3(args):
    targets = tuple(t for t in args.targets.split(',') if t)
    if not set(targets) <= {'gate', 'runtime'} or not targets:
        raise SystemExit('--targets: gate and / or runtime')
    if args.registered and (args.n_sequences < S3_MIN_SEQUENCES or set(targets) != {'gate', 'runtime'}):
        raise SystemExit(f'registered S3 needs >= {S3_MIN_SEQUENCES} sequences on both targets')
    out = check_out_path(args.out or _default_out('S3', args.registered), args.force)
    head = _header('S3', args.registered)
    res = run_s3(args.n_sequences, args.seed, targets, progress=_log)
    report = {**_finish(head), 'invariants': {k: INVARIANTS[k] for k in RUNTIME_INVARIANTS},
              'n_sequences': int(args.n_sequences), **res}
    path = write_report(out, report, args.force)
    print(json.dumps({'out': str(path), 'pass': report['pass'], 'coverage_ok': report['coverage_ok'],
                      'violations_total': report['violations_total'],
                      **{t: report['targets'][t]['violations'] for t in targets}}, indent=1))
    return 0 if report['pass'] else 1


def cmd_s2(args):
    """S2 on the registered grid (default), or with --grid relative on the supplementary grid relative to each
    state's slack floor (Amendment A7: label SUPPLEMENTARY_LABEL, 'supplementary': true, NOTES['S2_relative'])."""
    relative = args.grid == 'relative'
    nets = [describe_qnet(p) for p in args.qnet]
    out = check_out_path(args.out or _default_out('S2', args.registered, 'relative' if relative else None), args.force)
    states, meta = load_states(args.states, args.n_states, args.runs_root, args.allow_test_routes, args.seed)
    if not states:
        raise SystemExit(f'no {args.states} decision states found')
    head = _header('S2', args.registered)
    if relative:
        head.update(label=relative_label(args.registered), supplementary=True,
                    notes=head['notes'] + NOTES['S2_relative'])
    env = lease_env()
    fidelity = replay_fidelity(states, env) if args.states == 'recorded' else None
    res = (run_s2_relative if relative else run_s2)(states, nets, env, progress=_log)
    report = {**_finish(head), 'states': meta, 'replay_fidelity': fidelity, **res}
    if fidelity is not None and not fidelity['ok']:
        report['pass'] = False
    path = write_report(out, report, args.force)
    extra = {'grid': report['grid'], 'floor_check_ok': report['floor_check_ok']} if relative else {}
    print(json.dumps({'out': str(path), 'pass': report['pass'], 'violations_total': report['violations_total'],
                      'n_swept': report['n_swept'], **extra,
                      **{n: {'share_admitted': r['share_admitted'], 'bypass_rate': r['bypass_rate'],
                             'bypass_rate_slack': r['bypass_rate_slack'],
                             'bypass_rate_timing': r['bypass_rate_timing'],
                             'admitted_bound_ge_Dstar': r['admitted_bound_ge_Dstar']}
                         for n, r in report['networks'].items()}}, indent=1))
    return 0 if report['pass'] else 1


def _sigterm_exit(signum, frame):
    raise SystemExit(f'stress_bench: terminated by signal {signum}')


def cmd_s1(args):
    loads = tuple(int(x) for x in args.loads.split(',') if x != '')
    if not loads or any(not 0 <= n < (os.cpu_count() or 1) for n in loads):
        raise SystemExit(f'--loads: integers in [0, {(os.cpu_count() or 1) - 1}]')
    if args.registered and loads != LOADS:
        raise SystemExit(f'registered S1 runs the loads {LOADS}')
    if args.registered and not args.cpu_sample_s > 0:
        raise SystemExit('registered S1 samples the foreign CPU load: --cpu-sample-s > 0')
    nets = [describe_qnet(p) for p in args.qnet]
    out = Path(args.out or _default_out('S1', args.registered))
    states, smeta = load_states(args.states, args.n_states, args.runs_root, args.allow_test_routes, args.seed)
    scenes, cmeta = c1_scenes() if args.scenes == 'c1_sweep' else synthetic_scenes(seed=args.seed)
    if not states or not scenes:
        raise SystemExit('no decision states or no scenes')
    plan = s1_plan(nets, smeta, cmeta, loads, args.n_calls, args.n_lease, args.settle_s, args.envelope, out,
                   args.busy_max_s, args.cpu_sample_s)
    if args.dry_run:
        print(json.dumps(C.jsonable(plan), indent=1))
        return 0
    blockers = plan['blocking_processes']
    if blockers and (any(n > 0 for n in loads) or not args.allow_shared_cpu or args.registered):
        raise SystemExit('s1: refusing to run while these processes are alive (S1 needs an exclusive CPU; only a '
                         'development run at load 0 may share it, with --allow-shared-cpu):\n' +
                         '\n'.join(f'  {b["pid"]} {b["cmdline"][:120]}' for b in blockers))
    foreign = plan['foreign_cpu']['processes']
    refuse_foreign = args.registered and not args.accept_foreign_cpu
    if refuse_foreign and foreign:
        raise SystemExit('s1: refusing a registered run while these processes use CPU (S1 needs an exclusive CPU; '
                         '--accept-foreign-cpu runs anyway and records it in the report):\n' +
                         '\n'.join(f'  {p["pid"]} {p["cpu_share"]:.2f} core {p["cmdline"][:120]}' for p in foreign))
    check_out_path(out, args.force)
    head = _header('S1', args.registered)
    env, env_lease = lease_env(), lease_env(args.envelope)
    old_handler = signal.signal(signal.SIGTERM, _sigterm_exit)     # BusyLoad.__exit__ then kills the busy processes
    try:
        res = run_s1(nets, states, scenes, env, env_lease, loads, args.n_calls, args.n_lease, args.settle_s,
                     guard=False, progress=_log, busy_max_s=args.busy_max_s, cpu_sample_s=args.cpu_sample_s,
                     refuse_foreign=refuse_foreign)
    finally:
        signal.signal(signal.SIGTERM, old_handler)
    report = {**_finish(head), 'plan': plan, 'shared_cpu': bool(blockers),
              'foreign_cpu_accepted': bool(args.accept_foreign_cpu),
              'envelope': {'path': rel(args.envelope), 'sha256': C.sha256_file(args.envelope)}, **res}
    path = write_report(out, report, args.force)
    print(json.dumps({'out': str(path), 'loads': list(loads)}, indent=1))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = p.add_subparsers(dest='cmd', required=True)

    def common(q, test):
        q.add_argument('--out', type=Path, default=None, help='report path (default outputs/framelease_v4/stress/...)')
        q.add_argument('--force', action='store_true', help='overwrite an existing report')
        q.add_argument('--registered', action='store_true', help=f'label the report as the registered {test} run')
        q.add_argument('--seed', type=int, default=S3_SEED if test == 'S3' else SYNTH_SEED)

    def states_args(q):
        q.add_argument('--qnet', type=Path, action='append', required=True, help='deployed network file (repeat)')
        q.add_argument('--states', choices=('synthetic', 'recorded'), default='synthetic')
        q.add_argument('--runs-root', type=Path, action='append', default=None,
                       help='roots of finished runs for --states recorded (default: tuning and rl_data)')
        q.add_argument('--n-states', type=int, default=2000, help='synthetic states, or the cap on recorded states')
        q.add_argument('--allow-test-routes', action='store_true',
                       help='Phase 7 only, after the analysis freeze (PROTOCOL Sec. 9.11)')

    q3 = sub.add_parser('s3', help='S3: random event sequences against the commit gate and the V4Runtime commit path')
    q3.add_argument('--n-sequences', type=int, default=S3_MIN_SEQUENCES)
    q3.add_argument('--targets', default='gate,runtime')
    common(q3, 'S3')
    q2 = sub.add_parser('s2', help='S2: slack sweep [-0.1, 0.6] s in 10 ms steps per deployed network')
    states_args(q2)
    q2.add_argument('--grid', choices=S2_GRIDS, default='registered',
                    help='registered: D* = t + s (Sec. 7.6); relative: D* = t + f(state) + delta, the supplementary '
                         'grid relative to each state\'s Eq. 5 slack floor (Amendment A7, labelled supplementary)')
    common(q2, 'S2')
    q1 = sub.add_parser('s1', help='S1: CPU contention (exclusive CPU only; --dry-run prints the plan)')
    states_args(q1)
    q1.add_argument('--loads', default=','.join(str(n) for n in LOADS))
    q1.add_argument('--scenes', choices=('c1_sweep', 'synthetic'), default='c1_sweep')
    q1.add_argument('--envelope', type=Path, default=DEFAULT_ENVELOPE, help='L* envelope for the lease timing')
    q1.add_argument('--n-calls', type=int, default=20000)
    q1.add_argument('--n-lease', type=int, default=5000)
    q1.add_argument('--settle-s', type=float, default=2.0)
    q1.add_argument('--busy-max-s', type=float, default=BUSY_MAX_S,
                    help='lifetime cap of every busy process (they also end when the bench is gone)')
    q1.add_argument('--dry-run', action='store_true')
    q1.add_argument('--allow-shared-cpu', action='store_true',
                    help='development run at load 0 only while other processes are alive')
    q1.add_argument('--cpu-sample-s', type=float, default=CPU_SAMPLE_S,
                    help='/proc sampling window of the foreign-CPU check before the plan and each load level')
    q1.add_argument('--accept-foreign-cpu', action='store_true',
                    help='registered run although foreign processes use CPU (recorded in the report)')
    common(q1, 'S1')
    args = p.parse_args(argv)
    return {'s3': cmd_s3, 's2': cmd_s2, 's1': cmd_s1}[args.cmd](args)


if __name__ == '__main__':
    raise SystemExit(main())
