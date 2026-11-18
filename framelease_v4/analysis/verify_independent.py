#!/usr/bin/env python3
"""Independent verification of H1 and of the Table I columns DS / SR / RC / collisions per km / infractions per km
(framelease_v4/PROTOCOL.md Sec. 9.12: "before any number enters the paper, an independent session recomputes the H1
contrasts and the Table I columns from the raw run directories"; GAP_AUDIT Sec. 3.7 row R-7). CPU only; reads job
files, the runner's status records and the run directories they name; writes only under --out.

  cd /home/kang/Desktop/DAC
  OMP_NUM_THREADS=1 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      framelease_v4/analysis/verify_independent.py --queue outputs/framelease_v4/queue_p4 [--queue ...] \
      --analysis-freeze <record> --agg <aggregate_v4 output> --analysis <analyze_v4 output> --out <dir>

Procedure (P7; Sec. 9.12 "before any number enters the paper"), run by a session that wrote neither the aggregator nor
the analysis:
  1. registration.py --verify passes; the analysis-freeze record is cited in Sec. 13 and PROTOCOL.md is re-sealed;
  2. aggregate_v4.py and analyze_v4.py have written their outputs under the record (outputs/framelease_v4/analysis/
     final_<stamp>/);
  3. this script runs with --analysis-freeze, --agg and --analysis and with one --queue for every queue whose job lines
     the aggregator output covers (P4-P6; a job of a queue not given is listed as 'job absent from this
     verification'), into a new directory such as outputs/framelease_v4/verification/final_<stamp>/;
  4. AGREE: the H1 contrasts and findings and the verified Table I columns (DS with its CI, SR, collisions/km,
     infractions/km; RC in the notes) may enter the paper. DIFFER: every row of differences.csv is resolved and its
     cause recorded (Sec. 13) before any of these numbers enters the paper. The sha256 of verification.json is
     entered in its own dated Sec. 13 entry (the analysis-freeze record is cited before this script can run);
  5. scope: the other Table I columns (GPU usage, DMR, action age p50 / p95, fallback ratio, EIR, P_both) and the
     closed-loop R_cond of the notes are not recomputed by this script (verification.json 'scope'). They may not enter
     the paper on this verification; they need an independent recomputation from the run directories (Secs. 6.2-6.4)
     or a recorded decision on the scope of Sec. 9.12.

Independence. This script is written from the PROTOCOL text (Secs. 3, 6.1, 7.2, 8.2-8.4, 9.1, 9.2, 9.3, 9.8, 9.11,
9.12, 13), the runner's record format (framelease_v2/gpu_queue.py), the run-directory layout of the v4 launcher, the
official Bench2Drive success rule (tools/statistic_route_json.py is_success) and two documented conventions of the
registered functions that Sec. 9.1 names (the grid rounding numpy.rint(d / grid) of sign_flip_test; no Holm-adjusted p
for a missing p). It imports only the standard library and numpy. It neither imports nor reads framelease_v4/analysis/*,
framelease_v2/analyze_closed_loop.py or framelease_v4/arms/metrics_v4.py; it reads only the OUTPUT files of
aggregate_v4.py and analyze_v4.py, which it compares with its own numbers.

Inputs (one source of per-run values):
  --queue DIR    a gpu_queue directory (repeatable): jobs.d/*.jsonl and status.jsonl. The run of a job is the run
                 directory of the runner's FINAL 'end' record of the job id (the last record with final = true; a
                 start after it means a new attempt is under way: pending). Never a directory listing.
  --runs CSV     a per-run CSV in the aggregator's runs.csv format (job and route_id columns required): the statistics
                 layer is checked on given per-run values (synthetic development data, or the aggregator's own rows);
                 the result is development only.
Per run (raw source; Secs. 6.1, 8.4, 9.1):
  usable   the final record's outcome is ok / result_with_warnings; raw/official_results.json holds exactly one record
           of the job's route whose status is not an execution failure (Simulation crashed, Agent's sensors were
           invalid, Agent couldn't be set up, Agent crashed); metrics/result.json has >= 1 route record; the run
           directory lies under the job's --output-dir; the code matches the pins (every pinned file the run recorded,
           in manifest.json identity.code and raw/source_*/hashes.json, has the job's sha256, and every pinned
           framelease_v4 file is recorded); config.json names the job's route, kappa, seed, launcher arm and (shield
           arms) envelope sha256. Anything else is a missing cell with its reason; nothing is imputed (Sec. 9.8).
  outcome class  ok (a final ok / result_with_warnings record with a valid official record), not ok (any other final
           record: timeout, infra_failure, launch_error, an execution failure, ...), none (no final record). The
           runner and the aggregator's select stage (ok, agent_crashed, sim_failure, cut, pending) use different words
           for the same run; classes are compared, never words.
  DS = score_composed, RC = score_route of the official record; success = status Completed or Perfect and every
  infraction list other than min_speed_infractions empty; collisions = pedestrian + vehicle + layout collision
  events; km driven = route_length / 1000 x RC / 100, floored at 0.001 km; collisions/km = collisions / km driven;
  infractions/km = penalized infraction events (collisions, red light, stop, outside-route-lanes events, scenario
  timeouts, yield to emergency vehicle; min-speed records excluded) / km driven; the route-ending events (route
  deviation, vehicle blocked, route timeout) are counted separately (route_ending_events); an infraction list outside
  these three lists is noted and not counted.
  Consistency notes (reported, not used): metrics/result.json scores against the official record, and the official
  global record's per-km collision rates against collisions/km.
Labels: protocol arm = the job line's protocol_arm (P4-P6 lines); P1-0 / P1 / P2 lines carry none, and their launcher
arm (arm_name) is the protocol arm. Test routes are those of the registered route split (Sec. 3.1; its sha256 is
checked against the value cited in PROTOCOL.md); a cell is <protocol arm>_k<kappa>_s<seed> (+ _<candidate> on the
training phases P1-0 / P1 / P2, where several candidates share an arm).

Statistics (written from Secs. 9.1-9.3; not the v2 functions):
  H1           DS, Full FrameLease minus Fixed Deep, Fast Only, Age-Only, Event-Triggered; kappa 1.0, seed 11, the 44
               test routes, pairwise-complete routes; Holm over 4 (a missing p counts as 1 and has no adjusted p);
               label improves / worse (Holm-adjusted p < 0.05 with the mean difference > 0 / < 0), otherwise
               inconclusive; no data at n = 0; not computable without a p.
               Finding 1 may be stated only if contrasts 1 and 2 both improve, finding 2 only if 3 and 4 both improve.
  S-coll       the same four contrasts on route-level collisions/km (lower is better), Holm over 4.
  secondary    SR (success indicator), RC and infractions/km (lower is better) on the same four contrasts,
               uncorrected.
  test         exact two-sided sign-flip test of the mean paired difference: complete enumeration of the 2^n sign
               vectors on the raw differences for n <= 22 (meet in the middle); for n > 22 the exact distribution by
               dynamic programming over the differences rounded to the metric grid (DS, RC, collisions/km,
               infractions/km 0.01; fractions 1e-4) with numpy.rint of the binary quotient d / grid (the rounding of
               the registered sign_flip_test); p = P(|sum s_i k_i| >= |sum k_i|). A DP support above 40,000,001 states
               makes that contrast 'not computable' (p absent). At exact decimal half-grid ties the p under the two
               decimal readings of "rounded" (half away from zero; half to even) is reported as a diagnostic, never
               used; when the analysis reports a coarser DP grid (dp_grid), this script's p on that grid is reported
               as a diagnostic. Monte Carlo cross-check: 200,000 sign vectors, numpy.random.default_rng(20261110),
               p = (hits + 1) / (M + 1).
  CI           percentile bootstrap over routes, 10,000 resamples, a fresh numpy.random.default_rng(20261110) for every
               contrast and metric, 95% (and 90%); the pooled collisions/km of a cell (sum of collisions / sum of km)
               with the same route-cluster bootstrap.
  Table I      per cell <arm>_k1.0_s11 of the 7 Table I arms over the test routes: DS mean and 95% CI, SR, RC,
               collisions/km (route mean and pooled, with CIs), infractions/km (route mean).

Tolerances (fixed in advance; the exact rule for registered bootstrap endpoints was fixed on 2026-11-14, before any
test-route input):
  exact        counts, route sets, labels, statements, outcome classes: equality. Per-route values, means, sums,
               medians, minima, maxima, exact p-values and Holm-adjusted p-values: |difference| <= 1e-9.
  bootstrap    when both sides use the registered resamples and seed (this script's settings and the analysis'
               settings n_boot 10,000 and boot_seed 20261110): each CI endpoint |difference| <= 1e-9 (the bootstrap is
               deterministic). Otherwise an endpoint at level p (0.025 / 0.975 for the 95% CI, 0.05 / 0.95 for the 90%
               CI) agrees when it lies within [q(p - delta), q(p + delta)] (+-1e-9) of this script's own replicates,
               with delta = 5 sqrt(p (1 - p) (1 / B_mine + 1 / B_theirs)) (5 standard errors of the difference of two
               independent empirical quantile levels; distribution-free, valid for discrete bootstrap distributions);
               the window is reported as a diagnostic under the exact rule.
  Monte Carlo  a reported Monte Carlo p agrees when |p_mc - p_exact| <= 5 sqrt(p_exact (1 - p_exact) / M) + 2 / (M + 1)
               with M its number of sign vectors and p_exact this script's exact p; an empty Monte Carlo p at n > 22 is
               a difference.
  info         reported, never judged: the p method names, the DP grid, a Monte Carlo p this script has where the other
               side reports none (n <= 22), and the tie and grid diagnostics.
  Every expected file, column and field of the compared outputs is compared (a fixed list per target); an absent
  one is listed in differences.csv ('file absent', 'column absent', 'field absent', 'absent on one side'). Nothing is
  silently skipped.

Interim looks (Sec. 9.11). Before reading any run directory or result value, the script decides whether the input
touches a registered test route: a job line of a test route (--queue), a row of a test route or test_route = True
(--runs, --agg runs.csv), or an analysis output that read test-route rows (analysis.json interim_guard
test_input_rows > 0). Such input is refused (exit 4) unless --analysis-freeze names a valid analysis-freeze record:
  * the record parses and has schema framelease_v4.analysis_freeze/1 and a trigger (all_final, or a cut with its
    cut_amendment);
  * the sha256 of its bytes is cited in Sec. 13 of PROTOCOL.md, and PROTOCOL.md is the sealed version (its sha256 is
    the one in outputs/framelease_v4/registration/SEAL.sha256);
  * its route_split_sha256 is the sha256 of the registered route split, which is the value PROTOCOL.md cites;
  * it covers the input: every test-route job id is in its jobs, the job file of every such line is in its
    job_files with the file's current sha256, and every run this script reads (the run of an ok final runner record;
    the selected run of a --runs / --agg row) is the recorded run of the job.
  Every other disagreement with the record is not a refusal, since nothing unreleased is read: the run directory and
  the outcome class of every guarded job are compared with the record after the reading and listed as differences
  (target 'freeze record').
The test options --protocol / --seal (any path other than the registered PROTOCOL.md and SEAL.sha256) never release a
registered test route (exit 4) and make the status development; under them the test routes of a non-registered
--route-table are guarded instead (the record names that split), so that the grant path is tested on synthetic routes.
Every request is logged (granted or refused, with the reason) to <out>/guard_log.jsonl.

Outputs (--out; refused inside the queue, run, tuning, registration and job-file directories):
  verification.json  settings, tolerances, inputs with sha256, the guard decision, status (final / development and
                     why), run counts, H1, S-coll, the secondary rows, the Table I cells, every comparison, the scope
                     (verified and not verified Table I columns) and the verdict
  runs.csv           one row per job line: final record, outcome class, run directory, usable or the reason, DS, RC,
                     success, collisions, infractions, km driven, collisions/km, infractions/km
  contrasts.csv      the H1 / S-coll / secondary contrasts;  table_i.csv  the Table I cells (and every other cell)
  paired.csv         the per-route values of every contrast
  comparisons.csv    every comparison;  differences.csv  the comparisons outside their tolerance
  SHA256SUMS
Verdict: AGREE (every comparison within tolerance), DIFFER (at least one outside, or a listed freeze-record
difference), NOT_COMPARED (no --agg / --analysis and no difference).
Exit codes: 0 AGREE or NOT_COMPARED, 1 DIFFER, 2 input error (also any unexpected failure), 4 refused by the
interim-look rule (Sec. 9.11).
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
THIS_REL = 'framelease_v4/analysis/verify_independent.py'
SCHEMA = 'framelease_v4.verify_independent/1'
PROTOCOL_REL = 'framelease_v4/PROTOCOL.md'
SEAL_REL = 'outputs/framelease_v4/registration/SEAL.sha256'
ROUTE_SPLIT_REL = 'outputs/framelease_v4/protocol/route_split.json'
FREEZE_SCHEMA = 'framelease_v4.analysis_freeze/1'
GUARD_LOG = 'guard_log.jsonl'

# registered settings (PROTOCOL Sec. 9.1)
N_BOOT = 10000
BOOT_SEED = 20261110
MC_FLIPS = 200000
MC_SEED = 20261110
ENUM_MAX_N = 22
DP_MAX_STATES = 40_000_001     # 320 MB of int64 counts per array (two arrays live at a time)
ALPHA = 0.05
GRID = {'driving_score': 0.01, 'route_completion': 0.01, 'collisions_per_km': 0.01, 'infractions_per_km': 0.01,
        'success': 1e-4}

# tolerances (module docstring; fixed before any comparison)
TOL_EXACT = 1e-9
MC_SIGMAS = 5.0

# runner and leaderboard vocabulary (framelease_v2/gpu_queue.py; leaderboard FAILURE_MESSAGES)
OK_OUTCOMES = ('ok', 'result_with_warnings')
# words of the aggregator rows and the analysis-freeze record (select stage) for a job without a run
NO_RUN_OUTCOMES = ('pending', 'cut')
EXECUTION_FAILURE_STATUS = ('Simulation crashed', "Agent's sensors were invalid", "Agent couldn't be set up",
                            'Agent crashed')
SUCCESS_STATUS = ('Completed', 'Perfect')
COLLISION_KEYS = ('collisions_pedestrian', 'collisions_vehicle', 'collisions_layout')
# infractions per km (Sec. 6.1): counted, excluded and route-ending infraction lists of the official record
COUNTED_INFRACTIONS = COLLISION_KEYS + ('red_light', 'stop_infraction', 'outside_route_lanes', 'scenario_timeouts',
                                        'yield_emergency_vehicle_infractions')
EXCLUDED_INFRACTIONS = ('min_speed_infractions',)
ROUTE_ENDING_INFRACTIONS = ('route_dev', 'vehicle_blocked', 'route_timeout')
KM_FLOOR = 0.001
TRAINING_PHASES = ('P1-0', 'P1', 'P2')

# H1 and Table I (PROTOCOL Secs. 7.2, 9.2, 9.3)
FULL = 'fl_full'
H1_OTHERS = ('fixed_deep', 'fast_only', 'age_only', 'event_triggered')
TABLE_I_ARMS = ('fixed_deep', 'fast_only', 'age_only', 'event_triggered', 'fl_original', 'fl_heuristic', 'fl_full')
H_KAPPA = 1.0
H_SEED = 11
# (family, metric, better, correction): H1 is the primary family; S-coll and the SR / RC rows are the Table I
# collision, success and completion contrasts of the same four pairs (Sec. 9.3)
CONTRAST_SETS = (('H1', 'driving_score', 'higher', 'holm'),
                 ('S-coll', 'collisions_per_km', 'lower', 'holm'),
                 ('secondary', 'success', 'higher', 'none'),
                 ('secondary', 'route_completion', 'higher', 'none'),
                 ('secondary', 'infractions_per_km', 'lower', 'none'))
CELL_METRICS = ('driving_score', 'success', 'route_completion', 'collisions_per_km', 'infractions_per_km')
# scope of this verification (Secs. 7.2, 9.12): the Table I columns recomputed here, and those it does not recompute
VERIFIED_COLUMNS = ('DS (mean, 95% CI)', 'SR', 'RC (note)', 'collisions/km (pooled, route-cluster CI; route mean)',
                    'infractions/km (route mean)')
NOT_VERIFIED_COLUMNS = ('GPU usage', 'DMR', 'action age p50', 'action age p95', 'fallback ratio', 'EIR', 'P_both',
                        'closed-loop R_cond (note)')

# --out is refused inside these (PROTOCOL Sec. 8.6 run roots; the protected directories of the build)
PROTECTED_PREFIXES = ('outputs/framelease_v4/queue_', 'outputs/framelease_v4/p1_driver',
                      'outputs/framelease_v4/p1_jobs',
                      'outputs/framelease_v4/tuning', 'outputs/framelease_v4/registration',
                      'outputs/framelease_v4/rl_dev', 'outputs/framelease_v4/amendment_',
                      'outputs/framelease_v4/phase_driver', 'outputs/framelease_v4/matrix',
                      'outputs/framelease_v4/fig3', 'outputs/framelease_v4/ablation',
                      'outputs/framelease_v4/replicates', 'outputs/framelease_v4/rl_data',
                      'outputs/framelease_v4/smoke_p1_0', 'outputs/framelease_v4/test_jobs',
                      'outputs/framelease_v4/rl_freeze', 'outputs/framelease_v4/analysis')


class VerifyError(Exception):
    """An input problem (exit 2)."""


class GuardRefused(Exception):
    """Refused by the interim-look rule of PROTOCOL Sec. 9.11 (exit 4)."""


# ------------------------------------------------------------------------------------------------ small helpers
def now_iso():
    return _dt.datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S%z')


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def resolve(path, root=ROOT):
    """An absolute Path: a relative path is taken against the project root."""
    p = Path(path)
    return p if p.is_absolute() else Path(root) / p


def rel(path, root=ROOT):
    """The path relative to the project root when it lies inside it, else the absolute path (as a string)."""
    p = Path(os.path.normpath(str(resolve(path, root))))
    try:
        return p.relative_to(Path(os.path.normpath(str(root)))).as_posix()
    except ValueError:
        return p.as_posix()


def read_json(path):
    """A JSON file, or its losslessly compacted .gz sibling (PROTOCOL Sec. 8.5); None when neither exists."""
    path = Path(path)
    if path.is_file():
        return json.loads(path.read_text(encoding='utf-8'))
    gz = path.with_name(path.name + '.gz')
    if gz.is_file():
        import gzip
        with gzip.open(gz, 'rt', encoding='utf-8') as f:
            return json.load(f)
    return None


def as_float(value):
    """A finite float, or None (empty strings, None, NaN, non-numbers)."""
    if value is None or isinstance(value, bool):
        return None if value is None else float(value)
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def as_bool(value):
    """CSV and JSON booleans: True / False / 1 / 0 / 'true' / 'false'; None when empty."""
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ('true', '1', '1.0', 'yes'):
        return True
    if text in ('false', '0', '0.0', 'no'):
        return False
    return None


def kappa_text(kappa):
    return '%.1f' % float(kappa)


def route_order(route_id):
    """Sort key of route ids: numeric ids in numeric order, anything else after them."""
    text = str(route_id)
    return (0, int(text), '') if text.isdigit() else (1, 0, text)


def cell_name(arm, kappa, seed, candidate=None):
    base = '%s_k%s_s%d' % (arm, kappa_text(kappa), int(seed))
    return base if not candidate else '%s_%s_k%s_s%d' % (arm, candidate, kappa_text(kappa), int(seed))


# ------------------------------------------------------------------------------------------------ statistics (Sec. 9.1)
ROUNDING_RULES = ('rint', 'half_away', 'half_even')


def grid_units(diffs, grid, rule='rint'):
    """The differences in integer units of the metric grid, and the number of exact decimal half-grid ties.
    rint (judged): numpy.rint of the binary quotient d / grid as stored (half to even on the stored value), the
    rounding of the registered sign_flip_test (Sec. 9.1). half_away / half_even (diagnostics at ties only): the decimal
    value x = d / grid cleaned to 6 decimals, rounded half away from zero / half to even."""
    if rule not in ROUNDING_RULES:
        raise ValueError('rounding rule %r' % (rule,))
    units, ties = [], 0
    for d in diffs:
        q = float(d) / grid
        x = round(q, 6)
        frac = abs(x) - math.floor(abs(x))
        if abs(frac - 0.5) < 1e-9:
            ties += 1
        if rule == 'rint':
            k = int(np.rint(q))
        elif rule == 'half_even':
            k = int(round(x))
        else:
            k = int(math.floor(abs(x) + 0.5))
            k = k if x >= 0 else -k
        units.append(k)
    return units, ties


def dp_sign_flip_p(units):
    """Exact two-sided sign-flip p of integer differences by dynamic programming over the sum: the number of sign
    vectors s with |sum s_i |k_i|| >= |sum k_i|, divided by 2^n (exact integer counts; n <= 62)."""
    n = len(units)
    if n == 0:
        return None
    if n > 62:
        raise VerifyError('dynamic programming with exact int64 counts needs n <= 62 (n %d)' % n)
    mags = [abs(int(k)) for k in units]
    total = sum(mags)
    t_obs = abs(sum(int(k) for k in units))
    if t_obs == 0:
        return 1.0
    if 2 * total + 1 > DP_MAX_STATES:
        raise VerifyError('the DP support 2 x %d + 1 exceeds %d states (memory cap)' % (total, DP_MAX_STATES))
    counts = np.zeros(2 * total + 1, dtype=np.int64)
    counts[total] = 1
    for a in mags:
        if a == 0:
            counts *= 2
            continue
        new = np.zeros_like(counts)
        new[a:] += counts[:-a]
        new[:-a] += counts[a:]
        counts = new
    if int(counts.sum()) != 2 ** n:
        raise VerifyError('DP counts do not sum to 2^n')
    hits = int(counts[:total - t_obs + 1].sum()) + int(counts[total + t_obs:].sum())
    return hits / float(2 ** n)


def enumeration_sign_flip_p(diffs):
    """Exact two-sided sign-flip p by complete enumeration of the 2^n sign vectors of the raw differences (meet in the
    middle: the 2^(n/2) half sums of each half, sorted). |T| >= |T_obs| with a tolerance of 1e-9 (1 + sum |d|)."""
    d = np.asarray([float(x) for x in diffs], dtype=float)
    n = d.size
    if n == 0:
        return None
    t_obs = abs(float(d.sum()))
    tol = 1e-9 * (1.0 + float(np.abs(d).sum()))
    if t_obs <= tol:
        return 1.0

    def half_sums(part):
        sums = np.zeros(1)
        for x in part:
            sums = np.concatenate([sums + x, sums - x])
        return sums

    left, right = half_sums(d[:n // 2]), np.sort(half_sums(d[n // 2:]))
    upper = right.size - np.searchsorted(right, t_obs - tol - left, side='left')
    lower = np.searchsorted(right, -t_obs + tol - left, side='right')
    return float((upper + lower).sum()) / float(2 ** n)


def dp_states(units):
    """The number of DP states (2 sum |k| + 1) of integer differences."""
    return 2 * sum(abs(int(k)) for k in units) + 1


def sign_flip_p(diffs, grid, enum_max_n=ENUM_MAX_N, rule='rint'):
    """(p, method, ties): complete enumeration for n <= 22, else the exact DP over the grid-rounded differences. A DP
    support above the memory cap gives p None with the method 'not computable ...' (that contrast only)."""
    n = len(diffs)
    if n == 0:
        return None, 'no data', 0
    if n <= enum_max_n:
        return enumeration_sign_flip_p(diffs), 'exact_enumeration', 0
    units, ties = grid_units(diffs, grid, rule)
    states = dp_states(units)
    if states > DP_MAX_STATES and abs(sum(units)) > 0:
        return None, 'not computable (DP support %d states > %d)' % (states, DP_MAX_STATES), ties
    return dp_sign_flip_p(units), 'exact_dp_rounded', ties


def mc_sign_flip_p(diffs, flips=MC_FLIPS, seed=MC_SEED, chunk=20000):
    """Monte Carlo cross-check (Sec. 9.1): (hits + 1) / (M + 1) over M random sign vectors of the raw differences."""
    d = np.asarray([float(x) for x in diffs], dtype=float)
    if d.size == 0:
        return None
    rng = np.random.default_rng(seed)
    t_obs = abs(float(d.sum()))
    tol = 1e-9 * (1.0 + float(np.abs(d).sum()))
    hits, left = 0, int(flips)
    while left > 0:
        m = min(chunk, left)
        signs = rng.integers(0, 2, size=(m, d.size), dtype=np.int8) * 2 - 1
        hits += int((np.abs(signs @ d) >= t_obs - tol).sum())
        left -= m
    return (hits + 1) / (int(flips) + 1)


def holm(pvalues):
    """Holm step-down adjusted p-values in input order. A missing p counts as 1, so the family size is kept (Sec. 9.1);
    it has no adjusted p itself (None, as the registered holm)."""
    p = [1.0 if v is None else float(v) for v in pvalues]
    m = len(p)
    adjusted = [None] * m
    running = 0.0
    for rank, i in enumerate(sorted(range(m), key=lambda j: p[j])):
        running = max(running, min(1.0, (m - rank) * p[i]))
        adjusted[i] = None if pvalues[i] is None else running
    return adjusted


def decision_label(mean, p_adjusted, better, n, alpha=ALPHA):
    """improves / worse / inconclusive (Sec. 9.1); 'no data' at n = 0; 'not computable' without a p."""
    if not n or mean is None:
        return 'no data'
    if p_adjusted is None:
        return 'not computable'
    if p_adjusted < alpha and mean != 0:
        good = mean > 0 if better == 'higher' else mean < 0
        return 'improves' if good else 'worse'
    return 'inconclusive'


def bootstrap_replicates(values, n_boot=N_BOOT, seed=BOOT_SEED, denominators=None):
    """Bootstrap replicates over routes with a fresh default_rng(seed): the mean of the resampled values, or, with
    denominators, the pooled ratio sum(values) / sum(denominators) of the resampled routes (route-cluster bootstrap).
    A resample whose denominator sum is 0 gives NaN (reported, never dropped silently)."""
    v = np.asarray(values, dtype=float)
    n = v.size
    if n == 0:
        return None
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(int(n_boot), n))
    if denominators is None:
        return v[idx].mean(axis=1)
    den = np.asarray(denominators, dtype=float)[idx].sum(axis=1)
    num = v[idx].sum(axis=1)
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(den > 0, num / np.where(den > 0, den, 1.0), np.nan)


def percentile_ci(reps, level=0.95):
    """Percentile interval of the replicates (linear interpolation); None when absent or not finite."""
    if reps is None or not np.all(np.isfinite(reps)):
        return None
    lo = (1.0 - level) / 2.0
    return [float(np.quantile(reps, lo)), float(np.quantile(reps, 1.0 - lo))]


def quantile_window(reps, p, n_theirs=N_BOOT, sigmas=MC_SIGMAS):
    """[q(p - delta), q(p + delta)] of the replicates, delta = sigmas sqrt(p (1 - p) (1 / B_mine + 1 / B_theirs)) (=
    5 sqrt(2 p (1 - p) / 10000) at the registered B): the agreement window of an independent bootstrap endpoint at
    level p (module docstring)."""
    if reps is None or not np.all(np.isfinite(reps)):
        return None
    delta = sigmas * math.sqrt(p * (1.0 - p) * (1.0 / float(len(reps)) + 1.0 / float(n_theirs)))
    return [float(np.quantile(reps, max(0.0, p - delta))), float(np.quantile(reps, min(1.0, p + delta)))]


def mc_tolerance(p_exact, flips):
    """Agreement bound of a Monte Carlo p with M sign vectors around the exact p (module docstring)."""
    return MC_SIGMAS * math.sqrt(max(p_exact * (1.0 - p_exact), 0.0) / float(flips)) + 2.0 / (float(flips) + 1.0)


# -------------------------------------------------------------------------------------------- protocol, seal, routes
HEX64 = re.compile(r'\b[0-9a-f]{64}\b')


def protocol_section(text, number):
    """The text of '## <number>.' up to the next '## ' heading."""
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith('## '):
            inside = line.startswith('## %d.' % number)
            continue
        if inside:
            out.append(line)
    return '\n'.join(out)


def sealed_protocol(protocol, seal):
    """(PROTOCOL.md text, its sha256, problems): the protocol must be the sealed version of SEAL.sha256."""
    problems = []
    protocol, seal = Path(protocol), Path(seal)
    if not protocol.is_file():
        raise GuardRefused('PROTOCOL.md not found: %s' % protocol)
    data = protocol.read_bytes()
    digest = sha256_bytes(data)
    sealed = None
    if seal.is_file():
        for line in seal.read_text(encoding='utf-8').splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1].endswith('PROTOCOL.md'):
                sealed = parts[0]
    if sealed is None:
        problems.append('no PROTOCOL.md entry in the seal %s' % seal)
    elif sealed != digest:
        problems.append('PROTOCOL.md (sha256 %s) is not the sealed version (%s)' % (digest, sealed))
    return data.decode('utf-8'), digest, problems


def load_route_table(path=None, protocol_text=None, root=ROOT):
    """The test routes (id -> index, length) of a route split. registered: the registered file whose sha256 PROTOCOL.md
    cites (Sec. 12.2); any other table is development only. Test-route indices are the positions in the id-sorted list
    (Sec. 3.1) when the table carries none."""
    reg_path = resolve(ROUTE_SPLIT_REL, root)
    path = reg_path if path is None else resolve(path, root)
    doc = read_json(path)
    if not isinstance(doc, dict) or not isinstance(doc.get('test'), list):
        raise VerifyError('route table %s: no "test" list' % path)
    entries = []
    for e in doc['test']:
        e = {'route_id': str(e)} if not isinstance(e, dict) else dict(e, route_id=str(e.get('route_id')))
        entries.append(e)
    order = sorted(entries, key=lambda e: int(e['route_id']))
    test = {}
    for pos, e in enumerate(order):
        test[e['route_id']] = {'index': int(e['index']) if e.get('index') is not None else pos,
                               'length_m': as_float(e.get('length_m')), 'scenario_type': e.get('scenario_type')}
    if len(test) != len(entries):
        raise VerifyError('route table %s: repeated test route ids' % path)
    digest = sha256_file(path)
    cited = bool(protocol_text) and digest in set(HEX64.findall(protocol_text))
    training = [str(e.get('route_id')) for e in doc.get('training') or [] if isinstance(e, dict)]
    return {'path': rel(path, root), 'sha256': digest, 'test': test, 'training': set(training),
            'registered': os.path.normpath(str(path)) == os.path.normpath(str(reg_path)) and cited,
            'cited_in_protocol': cited}


# -------------------------------------------------------------------------------------------- interim looks (Sec. 9.11)
def official_paths(protocol, seal, root=ROOT):
    """True when the PROTOCOL.md and seal paths are the registered ones (framelease_v4/PROTOCOL.md and
    outputs/framelease_v4/registration/SEAL.sha256 of the project root, symbolic links resolved)."""
    return (os.path.realpath(str(resolve(protocol, root))) == os.path.realpath(str(resolve(PROTOCOL_REL, root)))
            and os.path.realpath(str(resolve(seal, root))) == os.path.realpath(str(resolve(SEAL_REL, root))))


def load_freeze_record(path, protocol, seal, route_table, root=ROOT, require_registered=True):
    """A valid analysis-freeze record (module docstring) -> (record, sha256); GuardRefused with every problem otherwise.
    route_table: the split the record must name (the registered one; with the test options --protocol / --seal the
    --route-table, require_registered False). Coverage of the input is checked separately (covers_jobs, covers_rows)."""
    path = resolve(path, root)
    if not path.is_file():
        raise GuardRefused('analysis-freeze record not found: %s' % path)
    data = path.read_bytes()
    digest = sha256_bytes(data)
    problems = []
    try:
        record = json.loads(data.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as exc:
        raise GuardRefused('analysis-freeze record %s does not parse: %s' % (path, exc))
    if not isinstance(record, dict) or record.get('schema') != FREEZE_SCHEMA:
        problems.append('not an analysis-freeze record (schema %s)' % FREEZE_SCHEMA)
        record = record if isinstance(record, dict) else {}
    text, _, seal_problems = sealed_protocol(protocol, seal)
    problems += seal_problems
    if digest not in set(HEX64.findall(protocol_section(text, 13))):
        problems.append('its sha256 %s is not cited in Sec. 13 of %s' % (digest, rel(protocol, root)))
    trigger = record.get('trigger')
    if trigger not in ('all_final', 'cut') or (trigger == 'cut' and not record.get('cut_amendment')):
        problems.append('trigger %r is neither all_final nor a cut with its cut_amendment' % (trigger,))
    if record.get('route_split_sha256') != route_table['sha256'] or (require_registered
                                                                       and not route_table['registered']):
        problems.append('route_split_sha256 %s is not the %s route split %s (%s)'
                        % (record.get('route_split_sha256'), 'registered' if require_registered else 'given',
                           route_table['path'], route_table['sha256']))
    if not isinstance(record.get('jobs'), dict) or not isinstance(record.get('job_files'), dict):
        problems.append('no jobs / job_files maps')
    if problems:
        raise GuardRefused('analysis-freeze record %s (sha256 %s) is not valid: %s' % (rel(path, root), digest,
                                                                                       '; '.join(problems)))
    return record, digest


def reads_run(job):
    """The run directory this script reads for a job line (read_run), or None: only the run of a final runner record
    with an ok outcome, without a new attempt after it and without job-line problems."""
    fin = job.get('final') or {}
    if not fin or job.get('pending_retry') or job.get('line_problems') or fin.get('outcome') not in OK_OUTCOMES:
        return None
    return fin.get('run_dir') or None


def covers_jobs(record, jobs, root=ROOT):
    """Problems of the record's coverage of test-route job lines (dicts from load_queue with their final record). Each
    problem refuses the input: a job file or job the record does not cover, a job file whose sha256 changed, or a run
    this script would read (reads_run) that is not the recorded run of the job (it was not released). Every other
    disagreement with the record (outcome class; the run of a job whose run this script does not read) is a listed
    difference after the reading (compare_freeze_record), not a refusal."""
    problems = []
    files = {rel(k, root): v for k, v in (record.get('job_files') or {}).items()}
    entries = record.get('jobs') or {}
    for job in jobs:
        jf = rel(job['job_file'], root)
        if jf not in files:
            problems.append('job file %s is not in the record' % jf)
        elif files[jf] != job['job_file_sha256']:
            problems.append('job file %s changed after the freeze (sha256 %s, record %s)'
                            % (jf, job['job_file_sha256'], files[jf]))
        entry = entries.get(job['id'])
        if not isinstance(entry, dict):
            problems.append('job %s is not in the record' % job['id'])
            continue
        if entry.get('job_file') is not None and rel(entry['job_file'], root) != jf:
            problems.append('job %s: job file %s, record %s' % (job['id'], jf, rel(entry['job_file'], root)))
        run = reads_run(job)
        rec_dir = rel(entry['run_dir'], root) if entry.get('run_dir') else None
        if run is not None and rel(run, root) != rec_dir:
            problems.append('job %s: the run of its final runner record (%s, %s) is not the recorded run (%s, %s)'
                            % (job['id'], job['final'].get('outcome'), rel(run, root), entry.get('outcome'), rec_dir))
    return sorted(set(problems))


def outcome_class(word, valid_record=None):
    """The outcome class of a runner, aggregator or analysis-freeze record word: 'ok' (ok / result_with_warnings, unless
    valid_record is false), 'none' (no word, pending, cut: no run) or 'not ok' (any other word: timeout,
    infra_failure, launch_error, sim_failure, agent_crashed, ...). The runner and the select stage of the aggregator
    use different words for the same run; classes are compared, not words."""
    if word in OK_OUTCOMES:
        return 'not ok' if as_bool(valid_record) is False else 'ok'
    if word in (None, '') or word in NO_RUN_OUTCOMES:
        return 'none'
    return 'not ok'


def compare_freeze_record(comp, record, rows, root=ROOT):
    """The record's run and outcome class of every guarded job line against this script's reading (listed
    differences, target 'freeze record'; refusals are decided before the reading by covers_jobs)."""
    entries = record.get('jobs') or {}
    for row in rows:
        entry = entries.get(row['id'])
        entry = entry if isinstance(entry, dict) else {}
        mine_run = row.get('final_run_dir')
        rec_run = rel(entry['run_dir'], root) if entry.get('run_dir') else None
        state = row.get('outcome_class')
        why = ('the runner has a new attempt after its final record' if row.get('pending_retry') else
               'the runner has no final record' if state == 'none' else None)
        comp.add('freeze record', row['id'], 'run_dir', mine_run, rec_run, 'equal', mine_run == rec_run,
                 note=None if mine_run == rec_run else why)
        theirs = outcome_class(entry.get('outcome'))
        comp.add('freeze record', row['id'], 'outcome class', state, theirs, 'equal', state == theirs,
                 note='runner %s, record %s%s' % (row.get('final_outcome'), entry.get('outcome'),
                                                  '' if why is None else '; ' + why))


def covers_rows(record, rows, root=ROOT):
    """Problems of the record's coverage of test-route per-run CSV rows (job id; selected run when the row names
    one)."""
    problems = []
    entries = record.get('jobs') or {}
    for row in rows:
        entry = entries.get(row.get('job'))
        if not isinstance(entry, dict):
            problems.append('job %s is not in the record' % row.get('job'))
            continue
        run = row.get('run_dir') or row.get('selected_run')
        if run and entry.get('run_dir') and rel(run, root) != rel(entry['run_dir'], root):
            problems.append('job %s: selected run %s is not the recorded one (%s)' % (row.get('job'), rel(run, root),
                                                                                    rel(entry['run_dir'], root)))
    return sorted(set(problems))


def log_request(out_dir, entry):
    """Append one guard decision to <out>/guard_log.jsonl (append-only)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / GUARD_LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, sort_keys=True) + '\n')
        f.flush()
        os.fsync(f.fileno())


# ------------------------------------------------------------------------------------------------ runner records
def cmd_value(cmd, option):
    """The value after an option in an argv list, or None."""
    if not isinstance(cmd, list):
        return None
    for i, arg in enumerate(cmd[:-1]):
        if arg == option:
            return cmd[i + 1]
    return None


def job_fields(spec):
    """The fields of a job line that this script uses, from the line's keys and its exact argv (they must agree)."""
    cmd = spec.get('cmd') or []
    problems = []

    def pick(key, option, cast=str):
        a, b = spec.get(key), cmd_value(cmd, option)
        if a is not None and b is not None and cast(a) != cast(b):
            problems.append('%s %r differs from argv %s %r' % (key, a, option, b))
        v = a if a is not None else b
        return None if v is None else cast(v)

    route = pick('route_id', '--route-id')
    kappa = pick('kappa', '--kappa', float)
    seed = pick('seed', '--seed', int)
    launcher_arm = pick('arm_name', '--arm')
    out_dir = pick('output_dir', '--output-dir', lambda v: rel(v))
    phase = spec.get('phase')
    protocol_arm = spec.get('protocol_arm')
    if protocol_arm is None and phase in TRAINING_PHASES:
        protocol_arm = launcher_arm
    envelope = spec.get('envelope')
    env_sha = envelope.get('sha256') if isinstance(envelope, dict) else None
    pins = spec.get('require_sha256') if isinstance(spec.get('require_sha256'), dict) else {}
    return {'id': spec.get('id'), 'route_id': route, 'kappa': kappa, 'seed': seed, 'launcher_arm': launcher_arm,
            'protocol_arm': protocol_arm, 'phase': phase, 'block': spec.get('block'),
            'candidate': spec.get('candidate'), 'output_dir': out_dir, 'envelope_sha256': env_sha, 'pins': pins,
            'line_problems': problems}


def load_status(path):
    """id -> {'final': the last end record with final = true, 'open_after_final': a start after it, 'attempts': [...]},
    plus the number of lines that do not parse (a last line may still be being written)."""
    states, bad = {}, 0
    if not Path(path).is_file():
        return states, bad
    for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if not isinstance(r, dict) or r.get('event') not in ('start', 'end') or 'id' not in r:
            continue
        s = states.setdefault(r['id'], {'final': None, 'open_after_final': False, 'attempts': []})
        if r['event'] == 'start':
            s['open_after_final'] = s['final'] is not None
            s['open'] = True
        else:
            s['open'] = False
            s['open_after_final'] = False
            s['attempts'].append({'attempt': r.get('attempt'), 'outcome': r.get('outcome'), 'final': r.get('final'),
                                  'counted': r.get('counted'), 'run_dir': r.get('run_dir')})
            if r.get('final'):
                s['final'] = {'outcome': r.get('outcome'), 'run_dir': r.get('run_dir'), 'attempt': r.get('attempt'),
                              'utc': r.get('utc')}
    return states, bad


def load_queue(queue_dir, root=ROOT):
    """The job lines of <queue>/jobs.d/*.jsonl (name order) with their job file, its sha256 and the job's final runner
    record. Invalid lines and repeated ids are input errors (the runner skips them, so they cannot be final)."""
    qdir = resolve(queue_dir, root)
    jobs_dir = qdir / 'jobs.d'
    if not jobs_dir.is_dir():
        raise VerifyError('no jobs.d/ in %s' % qdir)
    states, bad = load_status(qdir / 'status.jsonl')
    jobs, seen, problems = [], set(), []
    for jf in sorted(jobs_dir.glob('*.jsonl')):
        digest = sha256_file(jf)
        for no, line in enumerate(jf.read_text(encoding='utf-8').splitlines(), 1):
            if not line.strip():
                continue
            try:
                spec = json.loads(line)
            except ValueError:
                problems.append('%s line %d does not parse' % (rel(jf, root), no))
                continue
            f = job_fields(spec)
            if not f['id'] or f['id'] in seen:
                problems.append('%s line %d: missing or repeated id %r' % (rel(jf, root), no, f['id']))
                continue
            seen.add(f['id'])
            st = states.get(f['id']) or {}
            f.update(job_file=str(jf), job_file_sha256=digest, line=no, queue=rel(qdir, root),
                     final=st.get('final'), pending_retry=bool(st.get('open_after_final')),
                     attempts=st.get('attempts') or [])
            jobs.append(f)
    return {'queue': rel(qdir, root), 'jobs': jobs, 'problems': problems, 'unparsed_status_lines': bad,
            'status_sha256': sha256_file(qdir / 'status.jsonl') if (qdir / 'status.jsonl').is_file() else None}


# ------------------------------------------------------------------------------------------------ run directories
def official_record(official, route_id):
    """The one official route record of the route (route_id 'RouteScenario_<id>_rep<k>'), or (None, problem)."""
    checkpoint = (official or {}).get('_checkpoint') or {}
    records = checkpoint.get('records') if isinstance(checkpoint.get('records'), list) else []
    mine = [r for r in records if isinstance(r, dict)
            and re.fullmatch(r'RouteScenario_%s_rep\d+' % re.escape(str(route_id)), str(r.get('route_id')))]
    if len(mine) != 1:
        return None, '%d official records of route %s (%d records in total)' % (len(mine), route_id, len(records))
    return mine[0], None


def driving_values(record):
    """DS, RC, IP, success, collisions, penalized infractions, route-ending events, route length, km driven,
    collisions/km and infractions/km of one official record (Sec. 6.1). Infraction lists outside the counted, excluded
    and route-ending lists are returned as unknown_infractions (not counted; noted)."""
    scores = record.get('scores') or {}
    infractions = record.get('infractions') or {}
    meta = record.get('meta') or {}
    ds, rc = as_float(scores.get('score_composed')), as_float(scores.get('score_route'))
    status = record.get('status')
    success = status in SUCCESS_STATUS and all(not v for k, v in infractions.items() if k != 'min_speed_infractions')

    def events(keys):
        return sum(len(infractions.get(k) or []) for k in keys)

    collisions = events(COLLISION_KEYS)
    penalized = events(COUNTED_INFRACTIONS)
    known = set(COUNTED_INFRACTIONS) | set(EXCLUDED_INFRACTIONS) | set(ROUTE_ENDING_INFRACTIONS)
    length_m = as_float(meta.get('route_length'))
    km = None if length_m is None or rc is None else max(length_m / 1000.0 * rc / 100.0, KM_FLOOR)
    return {'route_status': status, 'driving_score': ds, 'route_completion': rc,
            'infraction_penalty': as_float(scores.get('score_penalty')), 'success': 1.0 if success else 0.0,
            'collisions': collisions, 'infractions_penalized': penalized,
            'route_ending_events': events(ROUTE_ENDING_INFRACTIONS), 'route_length_m': length_m, 'km_driven': km,
            'collisions_per_km': None if km is None else collisions / km,
            'infractions_per_km': None if km is None else penalized / km,
            'unknown_infractions': sorted(k for k, v in infractions.items() if k not in known and v)}


def recorded_hashes(run_dir, root=ROOT):
    """{project-relative path: sha256} the run recorded (manifest.json identity.code and raw/source_*/hashes.json),
    plus the paths recorded twice with different sha256."""
    run_dir = Path(run_dir)
    found, conflicts = {}, set()

    def add(path, digest):
        p = rel(path, root)
        if p in found and found[p] != digest:
            conflicts.add(p)
        found[p] = digest

    manifest = read_json(run_dir / 'manifest.json') or {}
    for path, digest in ((manifest.get('identity') or {}).get('code') or {}).items():
        add(path, digest)
    for hashes in sorted((run_dir / 'raw').glob('source_*/hashes.json')):
        for path, digest in (read_json(hashes) or {}).items():
            if '/' in path:            # envelope.json / lease_params.json are copies under another name
                add(path, digest)
    return found, sorted(conflicts)


def code_problems(job, run_dir, root=ROOT):
    """Sec. 9.1 "code matches the pins": every pinned file the run recorded has the pin, every pinned framelease_v4
    file is recorded, and no path is recorded twice with different sha256."""
    recorded, conflicts = recorded_hashes(run_dir, root)
    problems = ['%s recorded with two sha256' % p for p in conflicts]
    for path, digest in sorted(job['pins'].items()):
        p = rel(path, root)
        if p in recorded and recorded[p] != digest:
            problems.append('%s: run %s, pin %s' % (p, recorded[p][:12], digest[:12]))
        elif p not in recorded and p.startswith('framelease_v4/'):
            problems.append('%s pinned but not recorded' % p)
    if not job['pins']:
        problems.append('the job line pins no file')
    return problems


def config_problems(job, config):
    """config.json names the job's route, kappa, seed, launcher arm and (shield arms) envelope sha256."""
    if not isinstance(config, dict):
        return ['no config.json']
    problems = []
    route = str((config.get('route') or {}).get('route_id'))
    if route != str(job['route_id']):
        problems.append('route %s, job %s' % (route, job['route_id']))
    if as_float(config.get('kappa')) != job['kappa']:
        problems.append('kappa %s, job %s' % (config.get('kappa'), job['kappa']))
    if as_float(config.get('seed')) is None or as_float(config.get('seed')) != job['seed']:
        problems.append('seed %s, job %s' % (config.get('seed'), job['seed']))
    if config.get('v4_arm') != job['launcher_arm']:
        problems.append('arm %s, job %s' % (config.get('v4_arm'), job['launcher_arm']))
    if job['envelope_sha256'] and config.get('envelope_sha256') != job['envelope_sha256']:
        problems.append('envelope %s, job %s' % (config.get('envelope_sha256'), job['envelope_sha256']))
    return problems


def safe_json(path, problems):
    """read_json, with an unreadable file listed as a problem (the run is then not usable) instead of an exception."""
    try:
        return read_json(path)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        problems.append('unreadable %s (%s)' % (Path(path).name, type(exc).__name__))
        return None


def read_run(job, root=ROOT):
    """The per-run row of one job line: its final record, usability with the reason, the Sec. 6.1 values and
    consistency notes. Reads only the run directory of the runner's final record."""
    row = {k: job.get(k) for k in ('id', 'phase', 'block', 'protocol_arm', 'launcher_arm', 'candidate', 'route_id',
                                   'kappa', 'seed', 'queue')}
    row.update(job_file=rel(job['job_file'], root), final_outcome=None, run_dir=None, usable=False, reason=None,
               notes=[], final_run_dir=None, valid_record=False, outcome_class='none',
               pending_retry=bool(job.get('pending_retry')))
    fin = job.get('final')
    if fin:
        row['final_outcome'] = fin.get('outcome')
        if not job.get('pending_retry'):
            row['final_run_dir'] = rel(fin['run_dir'], root) if fin.get('run_dir') else None
            row['outcome_class'] = 'not ok'
    if job['line_problems']:
        row['reason'] = 'job_line: ' + '; '.join(job['line_problems'])
        return row
    if not fin:
        row['reason'] = 'pending'
        return row
    if job.get('pending_retry'):
        row['reason'] = 'pending (a new attempt after the final record)'
        return row
    if fin.get('outcome') not in OK_OUTCOMES:
        row['reason'] = 'no_valid_record (final outcome %s)' % fin.get('outcome')
        return row
    if not fin.get('run_dir'):
        row['reason'] = 'no run directory in the final record'
        return row
    run_dir = resolve(fin['run_dir'], root)
    row['run_dir'] = rel(run_dir, root)
    problems = []
    if job['output_dir'] and not row['run_dir'].startswith(job['output_dir'].rstrip('/') + '/runs/'):
        problems.append('run directory outside %s/runs/' % job['output_dir'])
    official = safe_json(run_dir / 'raw/official_results.json', problems)
    result = safe_json(run_dir / 'metrics/result.json', problems)
    official = official if isinstance(official, dict) else None
    record, why = official_record(official, job['route_id'])
    if official is None:
        problems.append('no readable raw/official_results.json')
    elif record is None:
        problems.append(why)
    elif any(m in str(record.get('status')) for m in EXECUTION_FAILURE_STATUS):
        problems.append('execution failure: %s' % record.get('status'))
    else:
        row.update(valid_record=True, outcome_class='ok')
    if not isinstance(result, dict) or not (result.get('route_records') or 0) >= 1:
        problems.append('metrics/result.json without a route record')
    try:
        code = code_problems(job, run_dir, root)
    except (OSError, ValueError, UnicodeDecodeError, AttributeError) as exc:
        code = ['unreadable recorded hashes (%s)' % type(exc).__name__]
    if code:
        problems.append('code: ' + '; '.join(code))
    conf = config_problems(job, safe_json(run_dir / 'config.json', problems))
    if conf:
        problems.append('config: ' + '; '.join(conf))
    if record is not None:
        row.update(driving_values(record))
        notes = row['notes']
        unknown = row.pop('unknown_infractions')
        if unknown:
            notes.append('infraction lists outside Sec. 6.1 (not counted): %s' % ', '.join(unknown))
        if isinstance(result, dict):
            for key, field in (('score_composed', 'driving_score'), ('score_route', 'route_completion'),
                               ('score_penalty', 'infraction_penalty')):
                theirs = as_float((result.get('scores') or {}).get(key))
                if theirs is None or row[field] is None or abs(theirs - row[field]) > TOL_EXACT:
                    notes.append('metrics/result.json %s %s, official %s' % (key, theirs, row[field]))
            if result.get('route_status') != record.get('status'):
                notes.append('metrics/result.json route_status %s, official %s' % (result.get('route_status'),
                                                                                     record.get('status')))
            if result.get('timed_out'):
                notes.append('the launcher reported a timeout')
        rates = ((official.get('_checkpoint') or {}).get('global_record') or {}).get('infractions') or {}
        if len(((official.get('_checkpoint') or {}).get('records')) or []) == 1 and all(k in rates for k in
                                                                                      COLLISION_KEYS):
            rate = sum(as_float(rates[k]) or 0.0 for k in COLLISION_KEYS)
            if row['collisions_per_km'] is None or abs(rate - row['collisions_per_km']) > 0.0015 + 1e-9:
                notes.append('official global collisions/km %.3f, recomputed %s' % (rate, row['collisions_per_km']))
    if problems:
        row['reason'] = '; '.join(problems)
        return row
    row['usable'] = True
    return row


# ------------------------------------------------------------------------------------------------ per-run CSV source
def read_csv_rows(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def csv_run_row(r):
    """A per-run row from a runs.csv row: usable = final outcome ok / result_with_warnings, valid_record, code_check
    PASS and not health-only (this script's rule; the aggregator's analysis_use is compared, not used). km driven
    below the 0.001 km floor of Sec. 6.1 is floored (noted); a collisions_per_km column that is not collisions_total /
    km driven is noted and used as given (route-level values, Sec. 6.1)."""
    def num(key):
        return as_float(r.get(key))

    usable = (r.get('outcome') in OK_OUTCOMES and as_bool(r.get('valid_record')) is True
              and r.get('code_check') == 'PASS' and as_bool(r.get('health_only')) is not True)
    collisions, km, per_km = num('collisions_total'), num('km_driven'), num('collisions_per_km')
    penalized, inf_per_km = num('infractions_penalized'), num('infractions_per_km')
    notes = []
    if km is not None and km < KM_FLOOR:
        notes.append('km_driven %r below the 0.001 km floor of Sec. 6.1: floored' % km)
        km = KM_FLOOR
    for name, count, given in (('collisions', collisions, per_km), ('infractions', penalized, inf_per_km)):
        if count is not None and km is not None and given is not None and abs(count / km - given) > 1e-6:
            notes.append('%s_per_km %r is not its count / km_driven (%r)' % (name, given, count / km))
    run = r.get('run_dir') or r.get('selected_run') or None
    return {'id': r.get('job'), 'phase': r.get('phase'), 'block': r.get('block'),
            'protocol_arm': r.get('protocol_arm') or None, 'launcher_arm': r.get('launcher_arm'),
            'candidate': r.get('candidate') or None, 'route_id': str(r.get('route_id')),
            'kappa': num('kappa'), 'seed': None if num('seed') is None else int(num('seed')),
            'job_file': r.get('job_file'), 'final_outcome': r.get('outcome'), 'run_dir': run,
            'final_run_dir': rel(run) if run else None, 'pending_retry': False,
            'valid_record': as_bool(r.get('valid_record')) is True,
            'outcome_class': outcome_class(r.get('outcome'), r.get('valid_record')), 'usable': usable,
            'reason': None if usable else 'csv_not_usable: outcome %s, valid_record %s, code_check %s, health_only %s'
            % (r.get('outcome'), r.get('valid_record'), r.get('code_check'), r.get('health_only')),
            'notes': notes, 'route_status': r.get('route_status'), 'driving_score': num('driving_score'),
            'route_completion': num('route_completion'), 'infraction_penalty': num('infraction_penalty'),
            'success': num('success'), 'collisions': collisions, 'infractions_penalized': penalized,
            'route_ending_events': num('route_ending_events'), 'route_length_m': num('route_length_m'),
            'km_driven': km, 'collisions_per_km': per_km, 'infractions_per_km': inf_per_km,
            'test_route_flag': as_bool(r.get('test_route'))}


# ------------------------------------------------------------------------------------------------ cells
def split_of(route_id, table, registered):
    if str(route_id) in table['test']:
        return 'test'
    if str(route_id) in registered['test']:
        return 'test (registered)'
    if str(route_id) in registered['training']:
        return 'training'
    return 'other'


def cell_key(row):
    """<arm>_k<kappa>_s<seed> on the test phases; <phase>/<block>/<arm>_<candidate>_k<kappa>_s<seed> on the training
    phases, where several candidates of an arm run on the same routes."""
    if row['protocol_arm'] is None or row['kappa'] is None or row['seed'] is None:
        return None
    if row.get('phase') in TRAINING_PHASES:
        cand = row.get('candidate') if row.get('candidate') not in (None, row['protocol_arm']) else None
        return '%s/%s/%s' % (row['phase'], row.get('block'), cell_name(row['protocol_arm'], row['kappa'], row['seed'],
                                                                        cand))
    return cell_name(row['protocol_arm'], row['kappa'], row['seed'])


def build_cells(rows):
    """cell -> {'routes': {route: row}, 'duplicates': {route: [ids]}, 'missing': {route: reason}}: usable rows only;
    two usable rows of one cell and route are a duplicate and the route is left out of the cell (reported)."""
    cells = {}
    for row in rows:
        key = cell_key(row)
        if key is None:
            continue
        c = cells.setdefault(key, {'routes': {}, 'duplicates': {}, 'missing': {}, 'ids': {}})
        r = str(row['route_id'])
        if not row['usable']:
            c['missing'].setdefault(r, row['reason'])
            continue
        c['ids'].setdefault(r, []).append(row['id'])
        if r in c['routes'] or r in c['duplicates']:
            c['duplicates'][r] = c['ids'][r]
            c['routes'].pop(r, None)
            continue
        c['routes'][r] = row
    for c in cells.values():
        for r in c['routes']:
            c['missing'].pop(r, None)
    return cells


# ------------------------------------------------------------------------------------------------ H1, S-coll, secondary
def paired_values(cells, a_cell, b_cell, routes, metric):
    """Pairwise-complete per-route values (route order of the table) and the dropped routes with their reason."""
    ca = cells.get(a_cell) or {'routes': {}, 'missing': {}, 'duplicates': {}}
    cb = cells.get(b_cell) or {'routes': {}, 'missing': {}, 'duplicates': {}}
    pairs, dropped = [], {}
    for r in routes:
        ra, rb = ca['routes'].get(r), cb['routes'].get(r)
        va = None if ra is None else ra.get(metric)
        vb = None if rb is None else rb.get(metric)
        if va is not None and vb is not None:
            pairs.append((r, float(va), float(vb)))
            continue
        why = []
        for name, c, row, v in (('a', ca, ra, va), ('b', cb, rb, vb)):
            if row is None:
                why.append('%s: %s' % (name, 'duplicate' if r in c['duplicates'] else c['missing'].get(r, 'no row')))
            elif v is None:
                why.append('%s: no %s' % (name, metric))
        dropped[r] = '; '.join(why)
    return pairs, dropped


def contrast(cells, a_cell, b_cell, routes, metric, better, settings):
    """One paired contrast A - B (Sec. 9.1): n, means, sign counts, exact p, Monte Carlo p, bootstrap CIs."""
    pairs, dropped = paired_values(cells, a_cell, b_cell, routes, metric)
    d = [va - vb for _, va, vb in pairs]
    out = {'a': a_cell, 'b': b_cell, 'metric': metric, 'better': better, 'n_expected': len(routes), 'n': len(d),
           'dropped_routes': dropped, 'pairs': pairs, 'grid': GRID[metric]}
    if not d:
        out.update(mean=None, mean_a=None, mean_b=None, p_two_sided=None, p_method='no data', p_mc=None,
                   ci95=None, ci90=None, n_positive=0, n_negative=0, n_zero=0, rounding_ties=0, reps=None)
        return out
    p, method, ties = sign_flip_p(d, GRID[metric], settings['enum_max_n'])
    reps = bootstrap_replicates(d, settings['n_boot'], settings['boot_seed'])
    out.update(mean=float(np.mean(d)), mean_a=float(np.mean([v for _, v, _ in pairs])),
               mean_b=float(np.mean([v for _, _, v in pairs])), p_two_sided=p, p_method=method,
               p_mc=mc_sign_flip_p(d, settings['mc_flips'], settings['mc_seed']) if settings['mc_flips'] else None,
               ci95=percentile_ci(reps, 0.95), ci90=percentile_ci(reps, 0.90),
               n_positive=sum(1 for x in d if x > 0), n_negative=sum(1 for x in d if x < 0),
               n_zero=sum(1 for x in d if x == 0), rounding_ties=ties, reps=reps)
    if ties and method == 'exact_dp_rounded':
        # diagnostics only (never used for a label): the decimal readings of "rounded to the metric grid" at exact ties
        for rule in ('half_away', 'half_even'):
            units = grid_units(d, GRID[metric], rule)[0]
            out['p_two_sided_' + rule] = dp_sign_flip_p(units) if dp_states(units) <= DP_MAX_STATES else None
    return out


def contrast_families(cells, table, settings):
    """H1 (Holm over 4), S-coll (Holm over 4) and the uncorrected SR / RC rows of the four H1 pairs, kappa 1.0, seed 11,
    over the table's test routes; the H1 findings (Sec. 9.2)."""
    routes = sorted(table['test'], key=lambda r: table['test'][r]['index'])
    a_cell = cell_name(FULL, H_KAPPA, H_SEED)
    rows = []
    for family, metric, better, correction in CONTRAST_SETS:
        group = []
        for other in H1_OTHERS:
            c = contrast(cells, a_cell, cell_name(other, H_KAPPA, H_SEED), routes, metric, better, settings)
            c.update(family=family, correction='Holm over %d' % len(H1_OTHERS) if correction == 'holm' else 'none',
                     contrast='%s_minus_%s_k%s_s%d_all' % (FULL, other, kappa_text(H_KAPPA), H_SEED), other=other)
            group.append(c)
        adjusted = holm([c['p_two_sided'] for c in group]) if correction == 'holm' else [c['p_two_sided']
                                                                                        for c in group]
        for c, adj in zip(group, adjusted):
            c['p_adjusted'] = adj
            c['label'] = decision_label(c['mean'], c['p_adjusted'], better, c['n'])
        rows += group
    h1 = {c['other']: c['label'] for c in rows if c['family'] == 'H1'}
    findings = {'finding_1': h1['fixed_deep'] == 'improves' and h1['fast_only'] == 'improves',
                'finding_2': h1['age_only'] == 'improves' and h1['event_triggered'] == 'improves'}
    return rows, findings


# ------------------------------------------------------------------------------------------------ cells (Table I)
def describe(values, settings):
    """n, mean, median, min, max and the 95% / 90% percentile bootstrap CIs of a route mean."""
    v = [float(x) for x in values]
    if not v:
        return {'n': 0, 'mean': None, 'median': None, 'min': None, 'max': None, 'ci95': None, 'ci90': None,
                'reps': None}
    reps = bootstrap_replicates(v, settings['n_boot'], settings['boot_seed'])
    return {'n': len(v), 'mean': float(np.mean(v)), 'median': float(np.median(v)), 'min': min(v), 'max': max(v),
            'ci95': percentile_ci(reps, 0.95), 'ci90': percentile_ci(reps, 0.90), 'reps': reps}


def cell_summary(cell, routes, settings):
    """The Table I columns of one cell over the given routes (all of the cell's routes when None): DS, SR, RC and
    collisions/km route means with CIs, and the pooled collisions/km (sum of collisions / sum of km driven) with its
    route-cluster bootstrap CI (Sec. 6.1)."""
    present = cell['routes']
    keep = [r for r in (routes if routes is not None else sorted(present, key=route_order)) if r in present]
    out = {'n_routes': len(routes) if routes is not None else len(present), 'routes_used': keep, 'metrics': {}}
    for metric in CELL_METRICS:
        out['metrics'][metric] = describe([present[r][metric] for r in keep if present[r].get(metric) is not None],
                                          settings)
    pooled = [(present[r]['collisions'], present[r]['km_driven']) for r in keep
              if present[r].get('collisions') is not None and present[r].get('km_driven') is not None]
    num, den = sum(c for c, _ in pooled), sum(k for _, k in pooled)
    reps = bootstrap_replicates([c for c, _ in pooled], settings['n_boot'], settings['boot_seed'],
                                denominators=[k for _, k in pooled]) if pooled else None
    out['metrics']['collisions_per_km_pooled'] = {
        'n': len(pooled), 'mean': (num / den) if den > 0 else None, 'numerator_sum': float(num),
        'denominator_sum': float(den), 'ci95': percentile_ci(reps, 0.95), 'ci90': percentile_ci(reps, 0.90),
        'reps': reps, 'nan_replicates': int(np.isnan(reps).sum()) if reps is not None else 0}
    return out


def table_i(cells, table, settings):
    """The 7 Table I cells <arm>_k1.0_s11 over the table's test routes (Sec. 7.2)."""
    routes = sorted(table['test'], key=lambda r: table['test'][r]['index'])
    empty = {'routes': {}, 'missing': {}, 'duplicates': {}}
    return {cell_name(arm, H_KAPPA, H_SEED): cell_summary(cells.get(cell_name(arm, H_KAPPA, H_SEED), empty), routes,
                                                           settings)
            for arm in TABLE_I_ARMS}


def other_cells(cells, settings, skip=()):
    """Every other cell over all of its routes (descriptive; the training cells of a development run)."""
    return {key: cell_summary(c, None, settings) for key, c in sorted(cells.items()) if key not in skip}


# ------------------------------------------------------------------------------------------------ comparisons
class Comparisons:
    """Every comparison with its rule and tolerance (module docstring); differences are those not ok."""

    def __init__(self):
        self.rows = []

    def add(self, target, key, field, mine, theirs, rule, ok, tolerance=None, note=None):
        diff = None
        if isinstance(mine, (int, float)) and isinstance(theirs, (int, float)) and not isinstance(mine, bool) \
                and not isinstance(theirs, bool):
            diff = abs(float(mine) - float(theirs))
        self.rows.append({'target': target, 'key': key, 'field': field, 'mine': mine, 'theirs': theirs,
                          'abs_diff': diff, 'rule': rule, 'tolerance': tolerance, 'ok': bool(ok), 'note': note})

    def number(self, target, key, field, mine, theirs, tol=TOL_EXACT):
        """|mine - theirs| <= tol; both absent agrees, one absent does not."""
        mine, theirs = as_float(mine), as_float(theirs)
        ok = (mine is None and theirs is None) or (mine is not None and theirs is not None
                                                   and abs(mine - theirs) <= tol)
        self.add(target, key, field, mine, theirs, 'exact', ok, tol,
                 None if ok or (mine is not None and theirs is not None) else 'absent on one side')

    def equal(self, target, key, field, mine, theirs):
        self.add(target, key, field, mine, theirs, 'equal', mine == theirs)

    def info(self, target, key, field, mine, theirs):
        self.add(target, key, field, mine, theirs, 'info', True, note='reported, not judged')

    def absent(self, target, key, field, what='column'):
        """An expected column, field or file the other side does not have: always a difference."""
        self.add(target, key, field, 'expected', None, 'equal', False, note='%s absent' % what)

    def window(self, target, key, field, mine_endpoint, theirs, reps, p, n_theirs, exact=False):
        """A bootstrap endpoint at level p. exact (both sides use the registered resamples and seed): |mine - theirs|
        <= 1e-9, with the window reported as a diagnostic; otherwise theirs within [q(p - delta), q(p + delta)] of
        this script's replicates."""
        theirs = as_float(theirs)
        win = quantile_window(reps, p, n_theirs)
        if win is None:
            ok = theirs is None and mine_endpoint is None
            self.add(target, key, field, mine_endpoint, theirs, 'bootstrap_exact' if exact else 'bootstrap_window',
                     ok, None, None if ok else 'no replicate window on this side')
            return
        inside = theirs is not None and win[0] - TOL_EXACT <= theirs <= win[1] + TOL_EXACT
        text = 'window [%.6g, %.6g] at level %.3f' % (win[0], win[1], p)
        if exact:
            ok = theirs is not None and mine_endpoint is not None and abs(theirs - mine_endpoint) <= TOL_EXACT
            self.add(target, key, field, mine_endpoint, theirs, 'bootstrap_exact', ok, TOL_EXACT,
                     'registered resamples and seed on both sides; %s (%s)' % (text, 'inside' if inside else
                                                                                 'outside'))
            return
        self.add(target, key, field, mine_endpoint, theirs, 'bootstrap_window', inside, win, text)

    def monte_carlo(self, target, key, field, p_exact, p_mc, flips):
        p_mc = as_float(p_mc)
        if p_exact is None or p_mc is None or not flips:
            ok = p_mc is None and p_exact is None
            self.add(target, key, field, p_exact, p_mc, 'monte_carlo', ok, None, None if ok else 'absent on one side')
            return
        tol = mc_tolerance(p_exact, flips)
        self.add(target, key, field, p_exact, p_mc, 'monte_carlo', abs(p_mc - p_exact) <= tol, tol,
                 'mine is the exact p; %d sign vectors' % int(flips))

    def differences(self):
        return [r for r in self.rows if not r['ok']]


def dropped_set(text):
    """Route ids of a ' | '-joined '<route>: <reason>' list (the analysis' dropped_routes column)."""
    out = set()
    for part in str(text or '').split(' | '):
        head = part.split(':', 1)[0].strip()
        if head:
            out.add(head)
    return out


CONTRAST_NUMBERS = ('n', 'n_expected', 'n_positive', 'n_negative', 'n_zero', 'mean', 'mean_a', 'mean_b', 'p_two_sided',
                    'p_adjusted')
CONTRAST_CI = ((0.95, ('ci95_lo', 'ci95_hi')), (0.90, ('ci90_lo', 'ci90_hi')))


def explain_p(comp, target, key, why):
    """Annotate the p differences of one contrast (still differences) with their explanation."""
    for r in comp.rows:
        if r['target'] == target and r['key'] == key and r['field'] in ('p_two_sided', 'p_adjusted') and not r['ok']:
            r['note'] = why


def compare_contrast_row(comp, target, mine, theirs, n_boot_theirs, exact_ci=False):
    """One contrast row of the analysis (family_*.csv, secondary.csv) against this script's contrast: a fixed list of
    fields; a column the row does not have is a listed difference."""
    key = '%s %s' % (mine['contrast'], mine['metric'])
    for field in CONTRAST_NUMBERS:
        if field not in theirs:
            comp.absent(target, key, field)
        else:
            comp.number(target, key, field, mine.get(field), theirs.get(field))
    for field in ('label', 'dropped_routes'):
        if field not in theirs:
            comp.absent(target, key, field)
    if 'label' in theirs:
        comp.equal(target, key, 'label', mine['label'], theirs.get('label'))
    if 'dropped_routes' in theirs:
        comp.equal(target, key, 'dropped_routes', sorted(mine['dropped_routes'], key=route_order),
                   sorted(dropped_set(theirs.get('dropped_routes')), key=route_order))
    comp.info(target, key, 'p_method', mine['p_method'], theirs.get('p_method'))
    comp.info(target, key, 'dp_grid', mine['grid'], as_float(theirs.get('dp_grid')))
    p_theirs = as_float(theirs.get('p_two_sided'))
    if mine.get('rounding_ties') and mine['p_method'] == 'exact_dp_rounded':
        for rule in ('half_away', 'half_even'):
            field = 'p_two_sided_' + rule
            comp.info(target, key, field, mine.get(field), p_theirs)
            if p_theirs is not None and mine.get(field) is not None and abs(mine[field] - p_theirs) <= TOL_EXACT \
                    and (mine['p_two_sided'] is None or abs(mine['p_two_sided'] - p_theirs) > TOL_EXACT):
                explain_p(comp, target, key, '%d exact half-grid ties: the p difference is explained by tie handling '
                          '(theirs equals %s)' % (mine['rounding_ties'], field))
    their_grid = as_float(theirs.get('dp_grid'))
    if their_grid and mine['n'] > ENUM_MAX_N and abs(their_grid - mine['grid']) > 1e-12 * mine['grid']:
        units = grid_units([va - vb for _, va, vb in mine['pairs']], their_grid)[0]
        p_grid = dp_sign_flip_p(units) if dp_states(units) <= DP_MAX_STATES else None
        comp.info(target, key, 'p_two_sided_on_their_dp_grid', p_grid, p_theirs)
        if p_grid is not None and p_theirs is not None and abs(p_grid - p_theirs) <= TOL_EXACT:
            explain_p(comp, target, key, 'the analysis used the DP grid %g instead of %g; this script\'s p on that '
                      'grid equals theirs' % (their_grid, mine['grid']))
    for level, lo_hi in CONTRAST_CI:
        ci = mine['ci95'] if level == 0.95 else mine['ci90']
        for i, field in enumerate(lo_hi):
            if field not in theirs:
                comp.absent(target, key, field)
                continue
            p = (1.0 - level) / 2.0 if i == 0 else 1.0 - (1.0 - level) / 2.0
            comp.window(target, key, field, None if ci is None else ci[i], theirs.get(field), mine['reps'], p,
                        n_boot_theirs, exact_ci)
    if 'p_mc' not in theirs:
        comp.absent(target, key, 'p_mc')
    elif as_float(theirs.get('p_mc')) is not None:
        comp.monte_carlo(target, key, 'p_mc', mine['p_two_sided'], theirs.get('p_mc'), as_float(theirs.get('mc_flips')))
    elif mine['n'] > ENUM_MAX_N:
        comp.add(target, key, 'p_mc', mine.get('p_mc'), None, 'monte_carlo', False,
                 note='absent on one side (n > %d: the Monte Carlo cross-check of Sec. 9.1)' % ENUM_MAX_N)
    else:
        comp.info(target, key, 'p_mc', mine.get('p_mc'), None)


CELL_NUMBERS = {'route_mean': ('n', 'mean', 'median', 'min', 'max'),
                'pooled_ratio': ('n', 'mean', 'numerator_sum', 'denominator_sum')}


def compare_cell_row(comp, target, cell, metric, mine, theirs, n_boot_theirs, exact_ci=False):
    """One conditions.csv row (route_mean or pooled_ratio) against this script's cell summary: a fixed list of fields;
    a column the row does not have is a listed difference."""
    key = '%s %s' % (cell, metric)
    statistic = 'pooled_ratio' if metric.endswith('_pooled') else 'route_mean'
    for field in CELL_NUMBERS[statistic]:
        if field not in theirs:
            comp.absent(target, key, field)
        else:
            comp.number(target, key, field, mine.get(field), theirs.get(field))
    for i, field in enumerate(('ci95_lo', 'ci95_hi')):
        if field not in theirs:
            comp.absent(target, key, field)
            continue
        comp.window(target, key, field, None if mine['ci95'] is None else mine['ci95'][i], theirs.get(field),
                    mine['reps'], 0.025 if i == 0 else 0.975, n_boot_theirs, exact_ci)


ANALYSIS_FILES = ('analysis.json', 'family_H1.csv', 'family_S-coll.csv', 'secondary.csv', 'conditions.csv',
                  'paired_differences.csv')


def analysis_meta(analysis_dir):
    """The analysis output's status and settings, and whether it holds test-route rows (Sec. 9.11)."""
    doc = read_json(Path(analysis_dir) / 'analysis.json')
    if not isinstance(doc, dict):
        raise VerifyError('no analysis.json in %s' % analysis_dir)
    guard = doc.get('interim_guard') or {}
    table = doc.get('route_table') or {}
    test_rows = int(as_float(guard.get('test_input_rows')) or 0)
    return {'doc': doc, 'status': doc.get('status'), 'schema': doc.get('schema'),
            'script_sha256': doc.get('script_sha256'), 'settings': doc.get('settings') or {},
            'guard_status': guard.get('status'), 'test_input_rows': test_rows,
            'freeze_hashes': sorted(set(HEX64.findall(json.dumps(guard.get('freeze'))))),
            'route_table_registered': bool(table.get('registered')),
            'touches_test_routes': test_rows > 0}


PAIRED_COLUMNS_THEIRS = ('contrast', 'metric', 'route_id', 'value_a', 'value_b', 'difference', 'status')
DECISION_FIELDS = ('n', 'n_expected', 'mean', 'p_two_sided', 'p_adjusted')


def exact_bootstrap(settings, meta):
    """True when both sides use the registered bootstrap (10,000 resamples, seed 20261110): CI endpoints are then
    judged exactly (module docstring)."""
    theirs = meta['settings']
    return (settings['n_boot'] == N_BOOT and settings['boot_seed'] == BOOT_SEED
            and as_float(theirs.get('n_boot')) == N_BOOT and as_float(theirs.get('boot_seed')) == BOOT_SEED)


def compare_analysis(comp, analysis_dir, contrasts, findings, cells_i, meta, settings):
    """This script's H1 / S-coll / secondary contrasts and Table I cells against an analyze_v4 output directory. Every
    expected file, column and field is compared; an absent one is a listed difference."""
    adir = Path(analysis_dir)
    n_boot = int(as_float(meta['settings'].get('n_boot')) or N_BOOT)
    exact_ci = exact_bootstrap(settings, meta)
    by_family = {'H1': 'family_H1.csv', 'S-coll': 'family_S-coll.csv', 'secondary': 'secondary.csv'}
    tables = {}
    for name in set(by_family.values()) | {'conditions.csv', 'paired_differences.csv'}:
        tables[name] = read_csv_rows(adir / name) if (adir / name).is_file() else None
        if tables[name] is None:
            comp.absent('analysis:' + name, name, 'file', 'file')
    for c in contrasts:
        target = 'analysis:' + by_family[c['family']]
        rows = tables[by_family[c['family']]]
        if rows is None:
            continue
        match = [r for r in rows if r.get('contrast') == c['contrast'] and r.get('metric') == c['metric']
                 and (c['family'] != 'secondary' or r.get('role') == 'secondary')]
        if len(match) != 1:
            comp.add(target, '%s %s' % (c['contrast'], c['metric']), 'rows', 1, len(match), 'equal', False,
                     note='expected exactly one row')
            continue
        compare_contrast_row(comp, target, c, match[0], n_boot, exact_ci)
    # analysis.json decisions of H1
    h1_doc = ((meta['doc'].get('decisions') or {}).get('H1')) or {}
    listed = {x.get('contrast'): x for x in h1_doc.get('contrasts') or [] if isinstance(x, dict)}
    for c in contrasts:
        if c['family'] != 'H1':
            continue
        x = listed.get(c['contrast'])
        target, key = 'analysis:analysis.json decisions.H1', c['contrast']
        if x is None:
            comp.add(target, key, 'contrast', 'present', None, 'equal', False, note='not listed')
            continue
        for field in DECISION_FIELDS:
            if field not in x:
                comp.absent(target, key, field, 'field')
            else:
                comp.number(target, key, field, c.get(field), x.get(field))
        if 'label' not in x:
            comp.absent(target, key, 'label', 'field')
        else:
            comp.equal(target, key, 'label', c['label'], x.get('label'))
        if not isinstance(x.get('ci95'), list) or len(x['ci95']) != 2:
            comp.absent(target, key, 'ci95', 'field [lo, hi]')
            continue
        for i, p in ((0, 0.025), (1, 0.975)):
            comp.window(target, key, 'ci95[%d]' % i, None if c['ci95'] is None else c['ci95'][i], x['ci95'][i],
                        c['reps'], p, n_boot, exact_ci)
    for name, mine in sorted(findings.items()):
        theirs = (h1_doc.get(name) or {}).get('statement')
        comp.equal('analysis:analysis.json decisions.H1', name, 'may be stated', mine,
                   None if theirs is None else theirs == 'may be stated')
    # per-route paired values
    pd_rows = tables['paired_differences.csv']
    if pd_rows is not None:
        header = set(pd_rows[0]) if pd_rows else set()
        for field in PAIRED_COLUMNS_THEIRS:
            if field not in header:
                comp.absent('analysis:paired_differences.csv', 'paired_differences.csv', field)
        index = {}
        for r in pd_rows:
            index.setdefault((r.get('contrast'), r.get('metric')), []).append(r)
        for c in contrasts:
            if c['family'] not in ('H1', 'S-coll'):
                continue
            target, key = 'analysis:paired_differences.csv', '%s %s' % (c['contrast'], c['metric'])
            theirs = [r for r in index.get((c['contrast'], c['metric']), [])
                      if r.get('table') in (None, '', 'family_' + c['family'])]
            paired = {r.get('route_id'): r for r in theirs if r.get('status') == 'paired'}
            comp.equal(target, key, 'paired routes', sorted((r for r, _, _ in c['pairs']), key=route_order),
                       sorted(paired, key=route_order))
            for route, va, vb in c['pairs']:
                r = paired.get(route)
                if r is None:
                    continue
                comp.number(target, '%s r%s' % (key, route), 'value_a', va, r.get('value_a'))
                comp.number(target, '%s r%s' % (key, route), 'value_b', vb, r.get('value_b'))
                comp.number(target, '%s r%s' % (key, route), 'difference', va - vb, r.get('difference'))
    # Table I cells
    cond = tables['conditions.csv']
    if cond is None:
        return
    for cell, summ in cells_i.items():
        for metric, mine in summ['metrics'].items():
            statistic = 'pooled_ratio' if metric.endswith('_pooled') else 'route_mean'
            match = [r for r in cond if r.get('condition') == cell and r.get('subset') == 'all'
                     and r.get('metric') == metric and r.get('statistic') == statistic]
            if len(match) != 1:
                comp.add('analysis:conditions.csv', '%s %s' % (cell, metric), 'rows', 1, len(match), 'equal', False,
                         note='expected exactly one row')
                continue
            compare_cell_row(comp, 'analysis:conditions.csv', cell, metric, mine, match[0], n_boot, exact_ci)
            if metric == 'driving_score':
                for field, value in (('n_routes', summ['n_routes']), ('n_used', len(summ['routes_used']))):
                    if field not in match[0]:
                        comp.absent('analysis:conditions.csv', '%s %s' % (cell, metric), field)
                    else:
                        comp.number('analysis:conditions.csv', '%s %s' % (cell, metric), field, value,
                                    match[0].get(field))


RUN_FIELDS = (('driving_score', 'driving_score'), ('route_completion', 'route_completion'),
              ('infraction_penalty', 'infraction_penalty'), ('success', 'success'),
              ('collisions', 'collisions_total'), ('infractions_penalized', 'infractions_penalized'),
              ('route_ending_events', 'route_ending_events'), ('km_driven', 'km_driven'),
              ('collisions_per_km', 'collisions_per_km'), ('infractions_per_km', 'infractions_per_km'),
              ('route_length_m', 'route_length_m'))
RUN_COLUMNS_THEIRS = ('job', 'outcome', 'analysis_use', 'selected_run') + tuple(t for _, t in RUN_FIELDS)
SUMMARY_FIELDS = (('driving_score', 'driving_score'), ('route_completion', 'route_completion'),
                  ('success', 'success_rate'), ('collisions_per_km_pooled', 'collisions_per_km_pooled'))
SUMMARY_COLUMNS_THEIRS = ('protocol_arm', 'kappa', 'seed', 'routes') + tuple(t for _, t in SUMMARY_FIELDS)


def agg_rows_touch_test(rows, registered):
    """The aggregator rows of a registered test route (route id or test_route flag)."""
    return [r for r in rows if str(r.get('route_id')) in registered['test'] or as_bool(r.get('test_route')) is True]


def compare_agg(comp, agg_dir, my_rows, summaries):
    """Per job: outcome class, usability, selected run and the Sec. 6.1 values against the aggregator's runs.csv; per
    cell: n, DS, RC, SR and pooled collisions/km against arm_summary.csv. Every expected file and column is compared;
    an absent one is a listed difference."""
    adir = Path(agg_dir)
    rows = read_csv_rows(adir / 'runs.csv')
    header = set(rows[0]) if rows else set()
    target = 'agg:runs.csv'
    for field in RUN_COLUMNS_THEIRS:
        if field not in header:
            comp.absent(target, 'runs.csv', field)
    if 'job' not in header:
        raise VerifyError('%s/runs.csv has no job column' % rel(adir))
    theirs = {r['job']: r for r in rows}
    for row in my_rows:
        t = theirs.get(row['id'])
        if t is None:
            comp.add(target, row['id'], 'row', 'present', None, 'equal', False, note='job absent from runs.csv')
            continue
        cls = outcome_class(t.get('outcome'), t.get('valid_record'))
        comp.add(target, row['id'], 'outcome class', row['outcome_class'], cls, 'equal', row['outcome_class'] == cls,
                 note='runner %s, aggregator %s (valid_record %s)' % (row['final_outcome'], t.get('outcome'),
                                                                      t.get('valid_record')))
        comp.equal(target, row['id'], 'usable / analysis_use', row['usable'], as_bool(t.get('analysis_use')))
        if not (row['usable'] or as_bool(t.get('analysis_use'))):
            continue
        run = t.get('selected_run') or t.get('run_dir')
        comp.equal(target, row['id'], 'run_dir', row['run_dir'], rel(run) if run else None)
        for mine_key, their_key in RUN_FIELDS:
            if their_key in header:
                comp.number(target, row['id'], their_key, row.get(mine_key), t.get(their_key))
    mine_ids = {r['id'] for r in my_rows}
    for job in sorted(set(theirs) - mine_ids):
        comp.add(target, job, 'row', None, 'present', 'equal', False, note='job absent from this verification')
    path = adir / 'arm_summary.csv'
    target = 'agg:arm_summary.csv'
    if not path.is_file():
        comp.absent(target, 'arm_summary.csv', 'file', 'file')
        return
    rows = read_csv_rows(path)
    header = set(rows[0]) if rows else set()
    for field in SUMMARY_COLUMNS_THEIRS:
        if field not in header:
            comp.absent(target, 'arm_summary.csv', field)
    for t in rows:
        arm, cand = t.get('protocol_arm'), t.get('candidate')
        kappa, seed = as_float(t.get('kappa')), as_float(t.get('seed'))
        if not arm or kappa is None or seed is None:
            comp.add(target, json.dumps(t, sort_keys=True)[:120], 'cell', None, 'present', 'equal', False,
                     note='row without protocol arm, kappa or seed')
            continue
        if t.get('phase') in TRAINING_PHASES:
            key = '%s/%s/%s' % (t.get('phase'), t.get('block'),
                                cell_name(arm, kappa, int(seed), cand if cand not in (None, '', arm) else None))
        else:
            key = cell_name(arm, kappa, int(seed))
        mine = summaries.get(key)
        if mine is None:
            comp.add(target, key, 'cell', None, 'present', 'equal', False, note='no usable run in this cell here')
            continue
        if 'routes' in header:
            comp.number(target, key, 'routes', len(mine['routes_used']), t.get('routes'))
        for mine_key, their_key in SUMMARY_FIELDS:
            if their_key in header:
                comp.number(target, key, their_key, mine['metrics'][mine_key]['mean'], t.get(their_key))


# ------------------------------------------------------------------------------------------------ outputs
OUTPUT_FILES = ('verification.json', 'runs.csv', 'contrasts.csv', 'table_i.csv', 'paired.csv', 'comparisons.csv',
                'differences.csv')
RUN_COLUMNS = ('id', 'queue', 'job_file', 'phase', 'block', 'protocol_arm', 'launcher_arm', 'candidate', 'route_id',
               'split', 'kappa', 'seed', 'cell', 'final_outcome', 'final_run_dir', 'outcome_class', 'valid_record',
               'run_dir', 'usable', 'reason', 'route_status', 'driving_score', 'route_completion',
               'infraction_penalty', 'success', 'collisions', 'infractions_penalized', 'route_ending_events',
               'route_length_m', 'km_driven', 'collisions_per_km', 'infractions_per_km', 'notes')
CONTRAST_COLUMNS = ('family', 'contrast', 'a', 'b', 'metric', 'better', 'n_expected', 'n', 'mean', 'mean_a', 'mean_b',
                    'n_positive', 'n_negative', 'n_zero', 'p_two_sided', 'p_method', 'grid', 'rounding_ties',
                    'p_two_sided_half_away', 'p_two_sided_half_even', 'p_mc', 'correction', 'p_adjusted', 'label',
                    'ci95_lo', 'ci95_hi', 'ci90_lo', 'ci90_hi', 'dropped_routes')
CELL_COLUMNS = ('cell', 'table_i', 'metric', 'n_routes', 'n', 'mean', 'median', 'min', 'max', 'ci95_lo', 'ci95_hi',
                'ci90_lo', 'ci90_hi', 'numerator_sum', 'denominator_sum')
PAIRED_COLUMNS = ('family', 'contrast', 'metric', 'route_id', 'value_a', 'value_b', 'difference')
COMPARISON_COLUMNS = ('target', 'key', 'field', 'mine', 'theirs', 'abs_diff', 'rule', 'tolerance', 'ok', 'note')


def check_out_dir(out, root=ROOT):
    p = rel(out, root)
    for prefix in PROTECTED_PREFIXES:
        if p == prefix.rstrip('/') or p.startswith(prefix):
            raise VerifyError('--out %s lies in a protected directory (%s)' % (p, prefix))
    return resolve(out, root)


def _cell(value):
    if value is None:
        return ''
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def write_csv(path, columns, rows):
    tmp = Path(str(path) + '.tmp')
    with open(tmp, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(columns)
        for r in rows:
            w.writerow([_cell(r.get(c)) for c in columns])
    os.replace(tmp, path)


def contrast_rows(contrasts):
    out = []
    for c in contrasts:
        r = {k: c.get(k) for k in CONTRAST_COLUMNS}
        for name in ('ci95', 'ci90'):
            ci = c.get(name)
            r[name + '_lo'], r[name + '_hi'] = (ci[0], ci[1]) if ci else (None, None)
        r['dropped_routes'] = ' | '.join('%s: %s' % (k, v) for k, v in sorted(c['dropped_routes'].items(),
                                                                          key=lambda kv: route_order(kv[0])))
        out.append(r)
    return out


def cell_rows(summaries, table_i_cells):
    out = []
    for cell, summ in summaries.items():
        for metric, m in summ['metrics'].items():
            r = {'cell': cell, 'table_i': cell in table_i_cells, 'metric': metric, 'n_routes': summ['n_routes']}
            r.update({k: m.get(k) for k in ('n', 'mean', 'median', 'min', 'max', 'numerator_sum', 'denominator_sum')})
            for name in ('ci95', 'ci90'):
                ci = m.get(name)
                r[name + '_lo'], r[name + '_hi'] = (ci[0], ci[1]) if ci else (None, None)
            out.append(r)
    return out


def public(contrast_or_cell):
    """A JSON-safe copy without the bootstrap replicates."""
    if isinstance(contrast_or_cell, dict):
        return {k: public(v) for k, v in contrast_or_cell.items() if k not in ('reps', 'pairs')}
    if isinstance(contrast_or_cell, list):
        return [public(v) for v in contrast_or_cell]
    if isinstance(contrast_or_cell, tuple):
        return [public(v) for v in contrast_or_cell]
    if isinstance(contrast_or_cell, (np.floating, np.integer)):
        return contrast_or_cell.item()
    return contrast_or_cell


def write_outputs(out_dir, doc, my_rows, contrasts, summaries, table_i_cells, comp, force=False):
    """The output files and SHA256SUMS; existing outputs are replaced only with --force (guard_log.jsonl is kept)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = [n for n in OUTPUT_FILES + ('SHA256SUMS',) if (out_dir / n).exists()]
    if existing and not force:
        raise VerifyError('%s already holds %s (use --force)' % (out_dir, ', '.join(existing)))
    write_csv(out_dir / 'runs.csv', RUN_COLUMNS, my_rows)
    write_csv(out_dir / 'contrasts.csv', CONTRAST_COLUMNS, contrast_rows(contrasts))
    write_csv(out_dir / 'table_i.csv', CELL_COLUMNS, cell_rows(summaries, table_i_cells))
    write_csv(out_dir / 'paired.csv', PAIRED_COLUMNS,
              [{'family': c['family'], 'contrast': c['contrast'], 'metric': c['metric'], 'route_id': r,
                'value_a': va, 'value_b': vb, 'difference': va - vb} for c in contrasts for r, va, vb in c['pairs']])
    write_csv(out_dir / 'comparisons.csv', COMPARISON_COLUMNS, comp.rows)
    write_csv(out_dir / 'differences.csv', COMPARISON_COLUMNS, comp.differences())
    doc['outputs'] = {n: sha256_file(out_dir / n) for n in OUTPUT_FILES if n != 'verification.json'}
    tmp = out_dir / 'verification.json.tmp'
    tmp.write_text(json.dumps(public(doc), indent=1, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(tmp, out_dir / 'verification.json')
    sums = ''.join('%s  %s\n' % (sha256_file(out_dir / n), n) for n in OUTPUT_FILES)
    (out_dir / 'SHA256SUMS').write_text(sums, encoding='utf-8')


# ------------------------------------------------------------------------------------------------ main
def guard(args, registered, table, jobs, csv_rows, agg_rows, meta, official, root=ROOT):
    """The Sec. 9.11 decision before any result is read: (decision document, freeze record or None, the guarded job
    ids). Guarded: the registered test routes; with the test options --protocol / --seal (official False) also the
    test routes of a --route-table that is not the registered split, so that the grant path can be exercised on
    synthetic routes. Registered test-route input is never released under the test options."""
    synthetic = set(table['test']) - set(registered['test']) if not official and not table['registered'] else set()

    def registered_row(r):
        return str(r.get('route_id')) in registered['test'] or as_bool(r.get('test_route')) is True

    reg_jobs = [j for j in jobs if str(j['route_id']) in registered['test']]
    syn_jobs = [j for j in jobs if str(j['route_id']) in synthetic]
    reg_rows = [r for r in csv_rows + agg_rows if registered_row(r)]
    syn_rows = [r for r in csv_rows + agg_rows if not registered_row(r) and str(r.get('route_id')) in synthetic]
    touches = {'job_lines': len(reg_jobs), 'runs_csv_rows': len([r for r in csv_rows if registered_row(r)]),
               'agg_rows': len(agg_rows_touch_test(agg_rows, registered)),
               'analysis_test_input_rows': meta['test_input_rows'] if meta else 0}
    doc = {'rule': 'PROTOCOL Sec. 9.11: no test-route result is examined before the analysis freeze',
           'mode': 'registered PROTOCOL.md and seal' if official else
           'test options --protocol / --seal (%s, %s): registered test routes are never released; the --route-table '
           'test routes are guarded' % (rel(args.protocol, root), rel(args.seal, root)),
           'test_route_input': touches, 'freeze_record': None, 'freeze_sha256': None}
    if not official:
        doc['route_table_test_route_input'] = len(syn_jobs) + len(syn_rows)
    if not any(touches.values()) and not syn_jobs and not syn_rows:
        doc['decision'] = 'granted (no test-route input)'
        return doc, None, []
    if any(touches.values()) and not official:
        raise GuardRefused('registered test-route input %s under the test options --protocol / --seal (%s, %s): '
                           'never released (Sec. 9.11; the registered PROTOCOL.md and SEAL.sha256 are needed)'
                           % (json.dumps(touches, sort_keys=True), rel(args.protocol, root), rel(args.seal, root)))
    if not args.analysis_freeze:
        raise GuardRefused('test-route input %s before the analysis freeze: no analysis-freeze record '
                           '(--analysis-freeze)' % json.dumps(dict(touches, route_table=len(syn_jobs) + len(syn_rows)),
                                                              sort_keys=True))
    record, digest = load_freeze_record(args.analysis_freeze, resolve(args.protocol, root), resolve(args.seal, root),
                                        registered if official else table, root, require_registered=official)
    test_jobs = reg_jobs + syn_jobs
    problems = covers_jobs(record, test_jobs, root)
    problems += covers_rows(record, reg_rows + syn_rows, root)
    if problems:
        raise GuardRefused('the analysis-freeze record does not cover the input: ' + '; '.join(problems[:20])
                           + ('' if len(problems) <= 20 else '; ... %d problems in total' % len(problems)))
    doc.update(decision='granted (valid analysis-freeze record)', freeze_record=rel(args.analysis_freeze, root),
               freeze_sha256=digest, frozen=record.get('frozen'), trigger=record.get('trigger'))
    return doc, record, [j['id'] for j in test_jobs]


def settings_of(args):
    s = {'n_boot': args.n_boot, 'boot_seed': BOOT_SEED, 'mc_flips': args.mc_flips, 'mc_seed': MC_SEED,
         'enum_max_n': ENUM_MAX_N, 'alpha': ALPHA, 'grids': GRID}
    s['registered'] = args.n_boot == N_BOOT and args.mc_flips == MC_FLIPS
    return s


def development_reasons(args, table, settings, meta, guard_doc, official=True):
    reasons = []
    if not official:
        reasons.append('PROTOCOL.md / seal from the test options --protocol / --seal (%s, %s), not the registered ones'
                       % (rel(args.protocol), rel(args.seal)))
    if not table['registered']:
        reasons.append('route table %s is not the registered split' % table['path'])
    if not settings['registered']:
        reasons.append('settings are not the registered ones (n_boot %d, mc_flips %d)' % (settings['n_boot'],
                                                                                           settings['mc_flips']))
    if args.runs:
        reasons.append('per-run values from a CSV (--runs), not from the run directories')
    if not guard_doc.get('freeze_sha256'):
        reasons.append('no analysis-freeze record: no test-route result was read (Sec. 9.11)')
    if meta and meta['status'] in (None, 'development'):
        reasons.append('the compared analysis output has status %r' % meta['status'])
    return reasons


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument('--queue', action='append', default=[], help='gpu_queue directory (jobs.d/, status.jsonl)')
    ap.add_argument('--runs', help='per-run CSV in the runs.csv format (statistics check; development)')
    ap.add_argument('--agg', help='aggregate_v4.py output directory to compare (runs.csv, arm_summary.csv)')
    ap.add_argument('--analysis', help='analyze_v4.py output directory to compare')
    ap.add_argument('--analysis-freeze', help='a valid analysis-freeze record (needed for any test-route input)')
    ap.add_argument('--route-table', help='route table (default: the registered route split; other: development)')
    ap.add_argument('--protocol', default=PROTOCOL_REL, help=argparse.SUPPRESS)
    ap.add_argument('--seal', default=SEAL_REL, help=argparse.SUPPRESS)
    ap.add_argument('--n-boot', type=int, default=N_BOOT, help=argparse.SUPPRESS)
    ap.add_argument('--mc-flips', type=int, default=MC_FLIPS, help=argparse.SUPPRESS)
    ap.add_argument('--out', required=True)
    ap.add_argument('--force', action='store_true', help='replace earlier outputs in --out')
    args = ap.parse_args(argv)
    if bool(args.queue) == bool(args.runs):
        ap.error('give either --queue (raw run directories) or --runs (a per-run CSV)')
    return args


TOLERANCES = {
    'exact': 'counts, route sets, labels, statements, outcome classes equal; per-route values, means, sums, medians, '
             'minima, maxima, exact and Holm-adjusted p-values within %g' % TOL_EXACT,
    'bootstrap_exact': 'both sides with the registered resamples and seed (n_boot %d, boot_seed %d): each CI endpoint '
                       'within %g (the bootstrap_window is reported in the note as a diagnostic)'
                       % (N_BOOT, BOOT_SEED, TOL_EXACT),
    'bootstrap_window': 'otherwise an endpoint at level p lies within [q(p - delta), q(p + delta)] (+-1e-9) of this '
                        'script\'s own replicates, delta = 5 sqrt(p (1 - p) (1 / B_mine + 1 / B_theirs)) (= 5 sqrt(2 p '
                        '(1 - p) / 10000) at the registered B)',
    'monte_carlo': '|p_mc - p_exact| <= 5 sqrt(p_exact (1 - p_exact) / M) + 2 / (M + 1); an empty p_mc at n > %d is a '
                   'difference' % ENUM_MAX_N,
    'absent': 'every expected file, column and field is compared; an absent one is a difference',
    'stated': 'in the module docstring before any comparison was run (bootstrap_exact fixed on 2026-11-14, before any '
              'test-route input)'}


def require_columns(path, columns):
    """The path of a CSV whose header has the given columns (an input error otherwise: a per-run CSV without a job
    or route id cannot be guarded or compared)."""
    with open(path, newline='', encoding='utf-8') as f:
        header = next(csv.reader(f), [])
    missing = [c for c in columns if c not in header]
    if missing:
        raise VerifyError('%s has no %s column' % (rel(path), ', '.join(missing)))
    return path


def verify(args, root=ROOT):
    """The whole verification; returns (document, exit code)."""
    out_dir = check_out_dir(args.out, root)
    official = official_paths(args.protocol, args.seal, root)
    protocol_path = resolve(args.protocol, root)
    protocol_text = protocol_path.read_text(encoding='utf-8')
    registered = load_route_table(None, protocol_text, root)
    if not registered['cited_in_protocol']:
        raise VerifyError('the registered route split %s (sha256 %s) is not the one PROTOCOL.md cites'
                          % (registered['path'], registered['sha256']))
    table = registered if not args.route_table else load_route_table(args.route_table, protocol_text, root)
    settings = settings_of(args)
    inputs = {rel(protocol_path, root): sha256_file(protocol_path), table['path']: table['sha256']}
    jobs, queues = [], []
    for q in args.queue:
        qd = load_queue(q, root)
        if qd['problems']:
            raise VerifyError('queue %s: %s' % (qd['queue'], '; '.join(qd['problems'][:10])))
        queues.append({k: qd[k] for k in ('queue', 'unparsed_status_lines', 'status_sha256')})
        inputs[qd['queue'] + '/status.jsonl'] = qd['status_sha256']
        for j in qd['jobs']:
            inputs[rel(j['job_file'], root)] = j['job_file_sha256']
        jobs += qd['jobs']
    if len({j['id'] for j in jobs}) != len(jobs):
        raise VerifyError('a job id appears in more than one queue')
    csv_rows = read_csv_rows(require_columns(resolve(args.runs, root), ('job', 'route_id'))) if args.runs else []
    if args.runs:
        inputs[rel(args.runs, root)] = sha256_file(resolve(args.runs, root))
    agg_rows = []
    if args.agg:
        agg_rows = read_csv_rows(require_columns(resolve(args.agg, root) / 'runs.csv', ('job', 'route_id')))
        for name in ('runs.csv', 'arm_summary.csv', 'aggregate.json', 'SHA256SUMS'):
            if (resolve(args.agg, root) / name).is_file():
                inputs[rel(resolve(args.agg, root) / name, root)] = sha256_file(resolve(args.agg, root) / name)
    meta = analysis_meta(resolve(args.analysis, root)) if args.analysis else None
    if args.analysis:
        adir = resolve(args.analysis, root)
        for name in ANALYSIS_FILES:
            if (adir / name).is_file():
                inputs[rel(adir / name, root)] = sha256_file(adir / name)
    entry = {'schema': 'framelease_v4.verify_independent_guard_log/1', 'time': now_iso(), 'request': 'verify',
             'argv': [THIS_REL] + list(getattr(args, 'argv', None) or sys.argv[1:]),
             'pid': os.getpid(), 'analysis_freeze': args.analysis_freeze}
    try:
        guard_doc, record, guarded = guard(args, registered, table, jobs, csv_rows, agg_rows, meta, official, root)
    except GuardRefused as exc:
        log_request(out_dir, dict(entry, decision='refused', reason=str(exc)))
        raise
    log_request(out_dir, dict(entry, decision='granted', reason=guard_doc['decision']))
    if args.analysis_freeze:
        inputs[rel(args.analysis_freeze, root)] = sha256_file(resolve(args.analysis_freeze, root))

    # results are read from here on
    my_rows = [read_run(j, root) for j in jobs] if args.queue else [csv_run_row(r) for r in csv_rows]
    for row in my_rows:
        row['split'] = split_of(row['route_id'], table, registered)
        row['cell'] = cell_key(row)
    cells = build_cells(my_rows)
    contrasts, findings = contrast_families(cells, table, settings)
    t1 = table_i(cells, table, settings)
    summaries = dict(t1)
    summaries.update(other_cells(cells, settings, skip=set(t1)))
    comp = Comparisons()
    if record is not None and args.queue:
        guarded = set(guarded)
        compare_freeze_record(comp, record, [r for r in my_rows if r['id'] in guarded], root)
    if args.agg:
        compare_agg(comp, resolve(args.agg, root), my_rows, summaries)
    if args.analysis:
        compare_analysis(comp, resolve(args.analysis, root), contrasts, findings, t1, meta, settings)
        if guard_doc.get('freeze_sha256') or meta['freeze_hashes']:
            comp.equal('analysis:analysis.json interim_guard', 'freeze', 'run under this analysis-freeze record',
                       guard_doc.get('freeze_sha256'), guard_doc.get('freeze_sha256')
                       if guard_doc.get('freeze_sha256') in meta['freeze_hashes'] else meta['freeze_hashes'] or None)
    diffs = comp.differences()
    verdict = 'DIFFER' if diffs else ('AGREE' if (args.agg or args.analysis) else 'NOT_COMPARED')
    reasons = development_reasons(args, table, settings, meta, guard_doc, official)
    counts = {}
    for row in my_rows:
        k = 'usable' if row['usable'] else (row['reason'] or '').split(' (')[0].split(':')[0]
        counts[k] = counts.get(k, 0) + 1
    by_target = {}
    for r in comp.rows:
        t = by_target.setdefault(r['target'], {'compared': 0, 'differences': 0})
        t['compared'] += 1
        t['differences'] += 0 if r['ok'] else 1
    doc = {'schema': SCHEMA, 'created': now_iso(), 'script': THIS_REL,
           'script_sha256': sha256_file(Path(__file__).resolve()),
           'independence': 'imports only the standard library and numpy; neither imports nor reads '
                           'framelease_v4/analysis/* or framelease_v4/arms/metrics_v4.py (only their outputs)',
           'source': 'run directories via the runner\'s final records' if args.queue else 'per-run CSV ' + args.runs,
           'inputs': inputs, 'queues': queues, 'settings': settings, 'tolerances': TOLERANCES,
           'interim_guard': guard_doc, 'status': 'development' if reasons else 'final',
           'development_reasons': reasons,
           'route_table': {k: table[k] for k in ('path', 'sha256', 'registered')} | {'n_test': len(table['test'])},
           'runs': {'job_lines': len(my_rows), 'by_status': counts,
                    'consistency_notes': [{'id': r['id'], 'notes': r['notes']} for r in my_rows if r.get('notes')]},
           'h1': {'contrasts': [c for c in contrasts if c['family'] == 'H1'], 'findings': findings},
           's_coll': [c for c in contrasts if c['family'] == 'S-coll'],
           'secondary': [c for c in contrasts if c['family'] == 'secondary'],
           'table_i': t1, 'other_cells': {k: v for k, v in summaries.items() if k not in t1},
           'compared_analysis': None if meta is None else {k: meta[k] for k in (
               'status', 'schema', 'script_sha256', 'settings', 'guard_status', 'test_input_rows',
               'route_table_registered')},
           'comparisons': {'n': len(comp.rows), 'differences': len(diffs), 'by_target': by_target},
           'scope': {'verified': list(VERIFIED_COLUMNS) + ['H1 contrasts and findings', 'S-coll',
                                                           'SR / RC / infractions/km contrasts (secondary)'],
                     'not_verified': list(NOT_VERIFIED_COLUMNS),
                     'rule': 'the not_verified Table I columns are not recomputed here and may not enter the paper '
                             'on this verification (Sec. 9.12)'},
           'verdict': verdict}
    write_outputs(out_dir, doc, my_rows, contrasts, summaries, set(t1), comp, force=args.force)
    return doc, (1 if verdict == 'DIFFER' else 0)


def summary_lines(doc):
    lines = ['verification %s (%s): %d job lines %s' % (doc['verdict'], doc['status'], doc['runs']['job_lines'],
                                                         json.dumps(doc['runs']['by_status'], sort_keys=True))]
    for c in doc['h1']['contrasts']:
        lines.append('H1 %s: n %d, mean %s, p %s (%s), Holm %s, %s' % (
            c['contrast'], c['n'], 'NA' if c['mean'] is None else '%.4f' % c['mean'],
            'NA' if c['p_two_sided'] is None else '%.6g' % c['p_two_sided'], c['p_method'],
            'NA' if c['p_adjusted'] is None else '%.6g' % c['p_adjusted'], c['label']))
    lines.append('findings: %s' % json.dumps(doc['h1']['findings'], sort_keys=True))
    lines.append('comparisons: %d, differences %d %s' % (doc['comparisons']['n'], doc['comparisons']['differences'],
                                                         json.dumps(doc['comparisons']['by_target'], sort_keys=True)))
    for reason in doc['development_reasons']:
        lines.append('development: ' + reason)
    return lines


def main(argv=None):
    args = parse_args(argv)
    args.argv = list(argv) if argv is not None else sys.argv[1:]
    try:
        doc, code = verify(args)
    except GuardRefused as exc:
        print('REFUSED (exit 4): %s' % exc, file=sys.stderr)
        return 4
    except VerifyError as exc:
        print('ERROR (exit 2): %s' % exc, file=sys.stderr)
        return 2
    except Exception as exc:                      # an unexpected failure is an input error, never DIFFER (exit 1)
        print('ERROR (exit 2): %s: %s' % (type(exc).__name__, exc), file=sys.stderr)
        return 2
    for line in summary_lines(doc):
        print(line)
    print('outputs: %s' % rel(args.out))
    return code


if __name__ == '__main__':
    sys.exit(main())
