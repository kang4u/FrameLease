#!/usr/bin/env python3
"""Independent recomputation of the Table I columns beyond verify_independent.py (PROTOCOL Secs. 6.2-6.4, 7.2,
9.12, 9.13).

Scope. GPU usage (and CUDA-seconds per second), the deadline miss rate DMR (from the first commit on, Sec. 6.2; the
all-ticks and expired-only variants), action age p50 / p95, the fallback ratio (and fallback episodes), P_both
(Secs. 5.8, 6.4), the executed-invalid tick rate EIR and the closed-loop R_cond (Sec. 6.3, standard validity, from the
actor-box log; R_cond also without the V = 0 plans).

Independence. Standard library and numpy only. Nothing of `framelease_v4/analysis`, `framelease_v4/arms/metrics_v4.py`,
`framelease_v4/arms/realized.py`, `framelease_v4/arms/actor_log.py` or `framelease_v2` is imported, and no code of them
is used; the definitions below follow the PROTOCOL text and the documented conventions of the lease footprint of the
standard validity definition, and only data formats are taken from elsewhere: the outputs of `aggregate_v4.py`
(runs.csv, arm_summary.csv) and `analyze_v4.py` (conditions.csv, cells.csv, secondary.csv, family_S-dmr.csv,
paired_differences.csv, analysis.json), the actor-box log (the `actor_log.py` docstring; its gzip members are decoded
here from RFC 1952), the `_ego_shape` of a lease parameter file and the analysis-freeze record of the P7 interim guard.

Inputs.
* Runner records (`--queue DIR`, repeatable): `status.jsonl` of a queue directory (or a copy of it); the last final
  'end' record of a job names its run directory.
* Run directories (`--run-dir DIR`, repeatable; also every run directory named by the runner records or by runs.csv):
  `config.json` and `raw/agent/framelease/{ticks,jobs,events,decisions}.jsonl`; `summary.json` when present; the
  actor-box log `raw/agent/framelease/actors.jsonl.gz` and the lease parameter file the config names
  (`agent_config.lease_params_path`) for EIR and R_cond (a run without a usable log or ego box keeps every other
  column; validity_problems names the reason).
* Aggregator output (`--agg DIR`): runs.csv and, when present, arm_summary.csv.
* Analysis output (`--analysis DIR`): conditions.csv, cells.csv, secondary.csv, family_S-dmr.csv, descriptive.csv,
  paired_differences.csv, per_scenario.csv, per_ability.csv and analysis.json.

Definitions (per run; the route is the unit; arm-level values are means over routes).
* Ticks are the rows of ticks.jsonl; t is the row's `sim_s`; dt is the median tick spacing (20 Hz control). A tick
  commands the control period [t, t + dt), so the run spans [t_first, t_last + dt] simulated seconds.
* GPU usage = |union of the cost-model intervals of prefixes and flow steps| within the span / span. A prefix occupies
  [launch_s, launch_s + timeline_cost_s] and a flow step [launch_s, launch_s + timeline_cost_s] (jobs.jsonl). A job
  still running at the end has no jobs.jsonl row: its prefix is [prefix_end_s - prefix_timeline_s, prefix_end_s] of
  its 'job_start' event, and each later step quantum shown in the ticks' 'gpu' field (phase 'step') occupies
  [end of the job's previous quantum, busy_until_s]. CUDA-seconds per second = GPU usage / kappa.
* The committed action at tick t is the last accepted commit ('commit' event) with commit_s <= t (time comparisons at
  1e-6 s: a commit logged up to 1 microsecond after the tick time is the tick's, as the runtime applies it). The first
  commit is the earliest such commit_s.
* DMR = ticks with t >= first commit at which the committed action is not valid / those ticks. Valid: t < deadline_s
  for the lease arms (shield arms and Original FrameLease); t - capture_s < max_age_s (config runtime) for Fixed Deep,
  Fast Only and Event-Triggered. A committed action without a finite deadline or capture time is invalid; before the
  first commit there is none. The all-ticks variant divides the ticks without a valid committed action by all ticks;
  the expired-only variants count the ticks whose committed action exists and has expired.
* Fallback ratio = ticks in control mode 'fallback' (full-brake fallback) / all ticks, before the first plan included.
  Fallback episodes = maximal runs of consecutive fallback ticks.
* Action age = t - capture_s of the committed action, over tracked ticks (control mode 'track'); p50 / p95 by linear
  interpolation (numpy.percentile default); also the mean.
* P_both = decision rows (kind 'decision', depth >= 1, shield evaluated: 'shield' present) with |feasible| = 2 / those
  rows (Sec. 5.1 decision epochs); None for an arm without a shield. The run value enters the route mean; the pooled
  value (sum of choice epochs / sum of shield epochs) is reported next to it.
* Committed plans (Sec. 6.3) are the accepted commits. The plan of a commit (job_id, depth) is the 'plan' of the
  jobs.jsonl step of that job at that depth: 6 waypoints at tau = 0.5, 1.0, ..., 3.0 s in the capture LiDAR frame
  (x right, y forward), the LiDAR origin (0, 0) at tau = 0. A commit of a job without a jobs.jsonl row (still running
  at the end of the run) has no logged plan.
* True capture pose: the hero transform of the actor-log row at capture_s (within 1 ms; else linear between the
  bracketing rows at most 0.2 s apart), right-handed (y -> -y, yaw -> -yaw). The capture LiDAR lies 0.39 m behind
  the hero origin (official LIDAR2EGO: LiDAR x = ego right, y = ego forward).
* Ego footprint: the lease footprint of the standard validity definition (Eqs. 1-3). The plan is sampled every 0.05 s,
  tau_j = 0.05 j, j = 0..60, from the LiDAR origin (0, 0) at tau = 0 (linear between the waypoints). The body heading
  at sample j is the direction of p(tau_{j+1}) - p(tau_{j-1}) (at the last sample p(tau_60) - p(tau_59)); a
  displacement slower than 0.5 m/s over its span keeps the previous sample's heading, one pointing backward of it
  reverses (heading = travel + pi); at tau = 0 the heading is the capture heading. The ego box rides rigidly on the
  LiDAR: the `_ego_shape` of the run's lease parameter file (config.json `agent_config.lease_params_path`: half length,
  half width, centre offset in the LiDAR frame; forward_yaw_rad, the direction of the length axis, pi / 2 when absent),
  else the documented Bench2Drive hero box (half sizes 2.4462 x 0.9184 m, centre 0.3837 m ahead of the LiDAR). A named
  lease parameter file that cannot be read, or whose forward_yaw_rad is not pi / 2 (length axis along LiDAR +y, the
  only reading implemented here), leaves the run without Sec. 6.3 values.
* Actor boxes at t_k + tau (t_k = capture_s): the vehicle and walker boxes (catalog ext and off; the row's location
  and yaw) of the actor-log row of that time (within 1 ms), else linear between the bracketing rows at most 0.2 s
  apart (yaw along the shorter arc); an actor present in only one of the two rows is held at its logged pose over the
  half interval nearer to that row. A sample without such rows, or whose row lists no actors (ego-only row after full
  decimation), is unknown.
* V. The first sample j at which the footprint comes within d_safe = 0.5 m of an actor box (box-to-box distance
  <= d_safe; 0 when they overlap) brackets the first crossing in (tau_{j-1}, tau_j]. V is the first crossing time in
  that bracket: the footprint pose moves linearly between the two samples (heading along the shorter arc) and the
  actor boxes linearly between their states at the two samples (with the same hold rule); a 5 ms scan locates the
  crossing and bisection refines it to 1e-4 s (V is the conflicting end of the final bracket, V_lo its clear end).
  V = 0 when sample 0 conflicts. An unknown sample before the first conflicting sample censors the plan
  ('log-censored'); a plan without a conflicting sample among 61 known samples is clear. A conflict plan has an
  uncensored V. V_suf = clip(V - T_c, 0, H_bar), T_c = 0.5 s, H_bar = 2.5 s.
* EIR = tracked ticks whose committed action is a conflict plan at age t - capture_s >= V_suf, divided by the tracked
  ticks (mode 'track'). Closed-loop R_cond = conflict plans with H > V_suf / conflict plans, H = deadline_s -
  capture_s of the commit (the lease, or the age cap of the age-rule arms); None without conflict plans. Plans with
  V = 0 are counted on their own, and R_cond is also given without them. Age and tick times are compared at 1e-6 s.
  Tracked ages are multiples of the 0.05 s tick (to microseconds), so EIR depends on the bracketing sample of V only.
* Bounds of these values. A plan that cannot be evaluated (no logged plan, no capture pose, a non-finite plan, no
  deadline) or whose first unknown sample lies before the last tick may hide a conflict (u such plans). A conflict plan
  with |H - V_suf| < 1e-3 s lies on the miss rule within the time resolution of V: r_- of them count as misses, r_+ do
  not. The 1e-3 s band covers the bisection resolution of V (1e-4 s) only; the clearance interpolation of the
  registered implementation is convention F3 below, not a bound. The counts of conflict plans lie in [c, c + u], of
  misses in [m - r_-, m + r_+ + u], and R_cond in [(m - r_-) / (c + u), (m + r_+ + u) / (c + u)] (c conflict plans,
  m misses; likewise without the V = 0 plans). The upper bound of EIR also counts as invalid the tracked ticks on
  unevaluable plans, on a bounded log-censored plan those at an age of at least clip(tau_unknown - T_c, 0, H_bar), and
  the ticks whose age lies between the V_suf of the clear and of the conflicting bracket end.
* Conventions of the registered implementation (causes of differences; Sec. 6.3 findings about registered files). Two
  conventions of the registered implementation give Sec. 6.3 values other than these definitions. The values under
  each (F1, F3, and both: F1+F3) are formed here from the same plans, with bounds formed in the same way, so that a
  difference can carry its cause; the values of this script stay those defined above.
  * F1: a plan sample t_k + tau_j that lands on the last actor-log row (within 1 ms) later than the row's time by more
    than 1e-9 s lies outside the log. A conflict plan whose first conflicting sample is that sample, and a clear plan
    whose last sample (tau 3.0) is that sample, count as log-censored there: no conflict, no miss, none of its tracked
    ticks invalid, no bound.
  * F3: V is tau_{j-1} + 0.05 c_{j-1} / (c_{j-1} - c_j) from the minimum clearances c (least box distance to a vehicle
    or walker minus d_safe) at the bracketing samples j - 1 and j; V = tau_j when sample j - 1 has no such actor or
    c_{j-1} <= c_j (V_lin). The miss rule and EIR follow with V_lin; the 1e-3 s band applies around its V_suf.

Comparisons (every difference is listed in differences.csv; counts are exact, other values are judged at the
tolerances of TOLERANCES; a difference below the registered metric grid of Sec. 9.1 (1e-4 for fractions, 1 ms for ages)
is flagged 'below_grid').
* run: runs.csv columns (among them committed_plans and the realized_* columns of Sec. 6.3), summary.json (runtime)
  fields and the runner's END-line result fields of the same run.
* runner: the final run directory of every job against runs.csv.
* arm_summary.csv: the per-candidate means and pooled ratios recomputed over the runs.csv rows with analysis_use
  (realized_invalid_tick_ratio: the mean EIR).
* analysis: conditions.csv route means (n, mean, median, min, max); the n / mean_a / mean_b / mean / median / min / max
  of the contrasts of secondary.csv, family_S-dmr.csv, descriptive.csv and of the analysis.json lists secondary and
  families; the per-route values of paired_differences.csv; the per-cell values, status and job of per_scenario.csv;
  the rows of per_ability.csv and analysis.json per_ability (n, means and signs over the listed routes, each of which
  must be paired; the ability membership itself is not checked); analysis.json overhead (per condition: used runs,
  DMR mean / median / max, fallback episodes runs_with_any / total), decisions.H1.finding_2.gpu_usage_descriptive
  (Sec. 9.2: the two GPU-usage contrasts, n, mean, label 'descriptive') and
  manipulation.analysed_runs.p_both_shared_shield (Sec. 9.7, per kappa: the (route, seed) cells where fl_full and
  fl_heuristic are both used and have a P_both, each arm's mean and pooled P_both over them, the mean difference).
  EIR ('eir') and R_cond ('r_cond') are compared wherever the analysis outputs carry them (conditions.csv, the
  contrast rows of secondary.csv, descriptive.csv and analysis.json secondary / descriptive, paired_differences.csv,
  per_scenario.csv, per_ability.csv and analysis.json per_ability). Every value is computed from the recomputed
  per-run values of the jobs that cells.csv lists as used; a value with bounds (in-flight GPU quanta; Sec. 6.3:
  unevaluable plans and the time resolution of V) agrees when the other side lies within its bounds, and these
  agreements are counted by kind.
Every difference carries a cause (differences.csv 'cause'): F1, F3 or F1+F3 (the first of these in this order) when
the other side agrees, at the same tolerances, with the value this script forms from the per-run values under that
convention (counts exactly, other values at TOLERANCES or within the bounds under that convention); empty otherwise.
Such a row remains a difference. table1_extra.json counts the differences by cause (comparisons.differences_by_cause;
analysis_differences_by_cause for scope 'analysis') and the agreements within bounds whose other side equals the point
value under a convention (agree_within_bounds_by_cause). cause_plans.csv, written on every run, lists every plan that
a convention changes (run directory, commit, job, depth, sample j, sample time, time of the last actor-log row,
capture time, V, V_lin, H and the outcomes here and under the convention); runs_recomputed.csv carries the per-run
values under each convention (<field>_f1, <field>_f3, <field>_f1f3) and the plans each changes (f1_plans, f3_plans).
Every comparison carries a scope: 'analysis' for a value the analysis reads for a Table I column (the runs.csv column
that conditions.csv names, on a row with analysis_use, and every analysis output), 'record' for all others. The
verdict counts every difference; the differences in scope 'analysis' are also counted on their own. A used runs.csv
row without recomputable raw logs enters the analysis comparisons with its runs.csv value and is listed in
table1_extra.json (runs.used_rows_without_raw_logs); a used row naming a run directory that does not exist is a
difference. The development option `--runs-csv-values` (synthetic matrices without raw logs) skips the run
directories runs.csv names and takes the per-run values of the analysis comparisons from runs.csv.
Raw-data checks (counts in runs_recomputed.csv 'checks'): among others, fallback ticks with a valid committed action
and non-fallback ticks without one. The analysis reads the fallback ratio from the all-tick DMR column; the two are
equal exactly when both counts are zero.

Interim looks (Sec. 9.11). Before reading any log, every input that names a route is classified with the registered
route split: runner records, runs.csv rows, run directories (config.json), cells.csv jobs, and every route list of the
analysis outputs (the route_id, route, routes and dropped_routes columns of the CSV files; in analysis.json the lists of
route_table.subsets and cells and every route_id, route, routes and route_ids entry at any depth). A route id that reads
as an integral number in any form (1711, ' 1711 ', '1711.0', 1711.0) is that integer, here and in the split. Fail
closed: an input whose route is unknown (a run directory whose config names no route, a runs.csv row or runner record
with neither a route id nor a test-route flag, an analysis route entry without a route id, an analysis directory that
carries values but names no route) is judged as a registered test route. A test route is released only with
`--analysis-freeze RECORD`: a valid analysis-freeze record (schema framelease_v4.analysis_freeze/1, the format the P7
interim guard writes; G8 writes it as analysis_freeze.json in the final_<stamp> directory, which may be given instead)
that covers the input. Valid: the fields have the documented form (a job with outcome ok names its run directory; a
failed job, agent_crashed or sim_failure, names one or null; a cut job needs trigger cut), Sec. 13 of PROTOCOL.md cites
the sha256 of the record, PROTOCOL.md equals the sha256 of its seal (SEAL.sha256), the recorded route split and analysis
code are the files on disk. Covered: every job of such an input is in the record and every run directory it names is the
recorded run of its job (a job recorded as cut or without a run directory admits none). Otherwise the run is refused
(exit 4) and only guard_log.jsonl is written. A release under the registered record (status 'final') recomputes every
run directory: `--runs-csv-values` is refused there. The test options `--route-split` (synthetic test routes),
`--protocol` and `--seal` (development copies that judge the record) apply to the synthetic test routes only; a
registered test route and an input without a route are always judged with the registered split, PROTOCOL.md and seal.

Exit codes: 0 AGREE, 1 DIFFER, 2 input error or unexpected failure, 4 refused by the interim guard.
"""

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import time
import zlib

import numpy as np

SCHEMA = 'framelease_v4.verify_table1_extra/1'
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REGISTERED_SPLIT = 'outputs/framelease_v4/protocol/route_split.json'

EXIT_AGREE, EXIT_DIFFER, EXIT_ERROR, EXIT_REFUSED = 0, 1, 2, 4

# Sec. 4.1: validity rule of each arm (Sec. 6.2 "Valid follows the arm's own validity rule").
AGE_RULE_ARMS = ('fixed_deep', 'fast_only', 'event_triggered')
LEASE_ARMS = ('age_only', 'fl_original', 'fl_heuristic', 'fl_full', 'fl_global_shield', 'fl_bandit',
              'fl_fqi_nolease', 'fl_risk', 'fl_behaviour')
# Arms with the shield of Eq. 5 + Eq. 8 (P_both defined, Secs. 5.8, 6.4).
SHIELD_ARMS = tuple(a for a in LEASE_ARMS if a != 'fl_original')
TABLE1_ARMS = ('fixed_deep', 'fast_only', 'age_only', 'event_triggered', 'fl_original', 'fl_heuristic', 'fl_full')
H1_CONTRASTS = tuple('fl_full_minus_%s' % b for b in ('fixed_deep', 'fast_only', 'age_only', 'event_triggered'))

# Analysis metric name -> recomputed per-run field (Table I columns of this script).
ANALYSIS_METRICS = {
    'gpu_usage': 'gpu_usage',
    'dmr': 'dmr',
    'action_age_p50_s': 'action_age_p50_s',
    'action_age_p95_s': 'action_age_p95_s',
    'fallback_ratio': 'fallback_ratio',
    'p_both': 'p_both',
    'eir': 'eir',
    'r_cond': 'r_cond',
}

# Kind of every compared field: 'count' (exact), 'fraction', 'seconds', 'ratio' (CUDA-s per s), 'json' (exact).
FIELD_KIND = {
    'ticks': 'count', 'ticks_after_first_commit': 'count', 'missed_ticks_after_first_commit': 'count',
    'fallback_ticks': 'count', 'fallback_episodes': 'count', 'track_ticks': 'count', 'action_age_n': 'count',
    'decision_rows': 'count', 'shield_epochs': 'count', 'choice_epochs': 'count', 'routes': 'count', 'n': 'count',
    'gpu_usage': 'fraction', 'cuda_s_per_s': 'ratio', 'dmr': 'fraction', 'dmr_all_ticks': 'fraction',
    'expired_ratio_after_first_commit': 'fraction', 'expired_ratio_all_ticks': 'fraction',
    'fallback_ratio': 'fraction', 'p_both': 'fraction', 'p_both_pooled': 'fraction', 'dmr_all_ticks_pooled': 'fraction',
    'gpu_busy_s': 'seconds', 'sim_span_s': 'seconds', 'first_tick_s': 'seconds', 'last_tick_s': 'seconds',
    'first_commit_s': 'seconds', 'action_age_p50_s': 'seconds', 'action_age_p95_s': 'seconds',
    'action_age_mean_s': 'seconds', 'fallback_episodes_mean': 'fraction_free', 'max_age_s': 'seconds',
    'commits': 'count',
    'kappa': 'ratio', 'fallback_by_reason': 'json',
    'committed_plans': 'count', 'conflict_plans': 'count', 'misses': 'count', 'v0_plans': 'count',
    'log_censored_plans': 'count', 'eir_invalid_ticks': 'count', 'eir': 'fraction', 'r_cond': 'fraction',
    'r_cond_excl_v0': 'fraction', 'validity_available': 'json_text', 'realized_invalid_tick_ratio': 'fraction',
}
# Fields and metrics of Sec. 6.3: their bounds come from plans that cannot be evaluated (validity_run).
VALIDITY_FIELDS = ('eir', 'r_cond', 'r_cond_excl_v0', 'conflict_plans', 'misses', 'v0_plans', 'log_censored_plans',
                   'eir_invalid_ticks', 'realized_invalid_tick_ratio')
# Judged tolerances (absolute). A recomputation from the same logs agrees to rounding. GPU busy time, GPU usage and
# CUDA-s per s of a run carry bounds for the in-flight step quanta of its last job (see _gpu_intervals): the other
# side agrees when it lies within the bounds widened by the tolerance.
TOLERANCES = {'fraction': 1e-6, 'ratio': 1e-6, 'seconds': 1e-6, 'fraction_free': 1e-9}
# Registered metric grid (Sec. 9.1): a difference below it cannot change a value at the registered resolution.
GRID = {'fraction': 1e-4, 'ratio': 1e-4, 'seconds': 1e-3, 'fraction_free': 1e-4}
# Conventions of the registered implementation (module docstring, 'Conventions of the registered implementation'):
# the causes in the order a difference is tested against them, the suffix of their per-run fields in
# runs_recomputed.csv and the per-run fields written there.
CAUSES = ('F1', 'F3', 'F1+F3')
CAUSE_SUFFIX = {'F1': '_f1', 'F3': '_f3', 'F1+F3': '_f1f3'}
CAUSE_FIELDS = ('conflict_plans', 'misses', 'v0_plans', 'log_censored_plans', 'eir_invalid_ticks', 'eir', 'r_cond',
                'r_cond_excl_v0')
CAUSE_TEXT = {
    'F1': 'a plan sample on the last actor-log row later than its time by more than 1e-9 s lies outside the log: a '
          'conflict first found there and a clear plan ending there count as log-censored',
    'F3': 'V by linear interpolation of the minimum clearance (box distance - d_safe) between the bracketing samples '
          'j - 1 and j (V_lin; tau_j when sample j - 1 has no actor or c_{j-1} <= c_j)',
    'F1+F3': 'both conventions F1 and F3',
}


# ----------------------------------------------------------------------------------------------------------------
# Small utilities
# ----------------------------------------------------------------------------------------------------------------

class InputError(Exception):
    """An input the script cannot use (exit 2)."""


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def rel(path):
    """Path relative to the project root when inside it, else the absolute path."""
    ap = os.path.abspath(path)
    try:
        r = os.path.relpath(ap, ROOT)
    except ValueError:
        return ap
    return ap if r.startswith('..') else r


def resolve(path):
    """Absolute path; a relative path is taken relative to the project root."""
    if path is None or path == '':
        return None
    return os.path.abspath(path if os.path.isabs(path) else os.path.join(ROOT, path))


def iter_jsonl(path):
    """Yield the JSON objects of a JSONL file; a line that does not parse raises InputError."""
    with open(path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError as e:
                raise InputError('%s line %d: %s' % (path, i, e))


def fnum(x):
    """Float of a CSV / JSON value; None for empty, None, NaN-free text that does not parse."""
    if x is None:
        return None
    if isinstance(x, bool):
        return float(x)
    if isinstance(x, (int, float)):
        v = float(x)
        return v if math.isfinite(v) else None
    s = str(x).strip()
    if s == '' or s.lower() in ('none', 'null', 'nan', 'na'):
        return None
    if s.lower() == 'true':
        return 1.0
    if s.lower() == 'false':
        return 0.0
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def truthy(x):
    return str(x).strip().lower() in ('1', 'true', 'yes')


def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def percentile(values, q):
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=float), q))


def mean(values):
    vals = [v for v in values if v is not None]
    return float(np.mean(np.asarray(vals, dtype=float))) if vals else None


def read_csv(path):
    with open(path, 'r', encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    return rows


def write_csv(path, rows, fields):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore', lineterminator='\n')
        w.writeheader()
        for r in rows:
            w.writerow({k: _csv_cell(r.get(k)) for k in fields})


def _csv_cell(v):
    if v is None:
        return ''
    if isinstance(v, (dict, list)):
        return json.dumps(v, sort_keys=True)
    if isinstance(v, float):
        return repr(v)
    return v


def dump_json(path, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=1, sort_keys=True, default=_json_default)
        f.write('\n')


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    raise TypeError(type(o).__name__)


# ----------------------------------------------------------------------------------------------------------------
# Per-run recomputation from the raw run directory
# ----------------------------------------------------------------------------------------------------------------

LOG_DIR = os.path.join('raw', 'agent', 'framelease')
LOG_FILES = ('ticks.jsonl', 'jobs.jsonl', 'events.jsonl', 'decisions.jsonl')  # summary.json: compared when present

RUN_FIELDS = (
    'run_dir', 'route_id', 'arm', 'arm_kind', 'kappa', 'seed', 'max_age_s', 'validity_rule',
    'ticks', 'tick_dt_s', 'first_tick_s', 'last_tick_s', 'sim_span_s',
    'gpu_busy_s', 'gpu_busy_s_bounds', 'gpu_usage', 'gpu_usage_bounds', 'cuda_s_per_s', 'cuda_s_per_s_bounds',
    'gpu_quanta', 'gpu_inflight_boundaries',
    'commits', 'first_commit_s', 'ticks_after_first_commit', 'missed_ticks_after_first_commit', 'dmr',
    'missed_ticks_all', 'dmr_all_ticks', 'expired_ticks_after_first_commit', 'expired_ratio_after_first_commit',
    'expired_ticks_all', 'expired_ratio_all_ticks', 'invalid_ticks',
    'fallback_ticks', 'fallback_ratio', 'fallback_episodes', 'fallback_by_reason',
    'track_ticks', 'action_age_n', 'action_age_p50_s', 'action_age_p95_s', 'action_age_mean_s',
    'decision_rows', 'shield_epochs', 'choice_epochs', 'p_both',
    'validity_available', 'ego_box', 'committed_plans', 'plans_by_status', 'conflict_plans', 'conflict_plans_bounds',
    'misses', 'misses_bounds', 'miss_resolution_plans', 'r_cond', 'r_cond_bounds', 'v0_plans', 'v0_plans_bounds',
    'v0_misses', 'r_cond_excl_v0', 'r_cond_excl_v0_bounds', 'log_censored_plans', 'log_censored_plans_bounds',
    'plans_unevaluable', 'eir_invalid_ticks', 'eir_invalid_ticks_bounds', 'eir_unevaluable_ticks',
    'eir_resolution_ticks', 'eir', 'eir_bounds', 'f1_plans', 'f3_plans',
) + tuple(f + CAUSE_SUFFIX[c] for c in CAUSES for f in CAUSE_FIELDS) + ('validity_problems', 'checks', 'problems')


def load_run_meta(run_dir):
    """Arm, route, kappa, seed and the runtime constants of a run (config.json)."""
    path = os.path.join(run_dir, 'config.json')
    with open(path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    agent = cfg.get('agent_config') or (cfg.get('v4') or {}).get('agent') or {}
    runtime = agent.get('runtime') or {}
    arm = cfg.get('v4_arm') or (cfg.get('v4') or {}).get('arm')
    route = (cfg.get('route') or {}).get('route_id')
    kappa = fnum(cfg.get('kappa'))
    if kappa is None:
        kappa = fnum(runtime.get('kappa'))
    if arm in AGE_RULE_ARMS:
        rule = 'age'
    elif arm in LEASE_ARMS:
        rule = 'deadline'
    else:
        rule = None
    return {
        'run_dir': os.path.abspath(run_dir), 'route_id': None if route is None else str(route), 'arm': arm,
        'arm_kind': cfg.get('kind'), 'kappa': kappa, 'seed': cfg.get('seed', agent.get('seed')),
        'max_age_s': fnum(runtime.get('max_age_s')), 'fallback_brake': fnum(runtime.get('fallback_brake')),
        'validity_rule': rule, 'lease_params_path': agent.get('lease_params_path') or None,
    }


def _union_within(intervals, lo, hi):
    """Length of the union of [s, e] intervals clipped to [lo, hi], and the overlapped length (sum - union)."""
    clipped = sorted((max(s, lo), min(e, hi)) for s, e in intervals if min(e, hi) > max(s, lo))
    total = 0.0
    raw = 0.0
    cur_s = cur_e = None
    for s, e in clipped:
        raw += e - s
        if cur_e is not None and s <= cur_e:
            cur_e = max(cur_e, e)
            continue
        if cur_e is not None:
            total += cur_e - cur_s
        cur_s, cur_e = s, e
    if cur_e is not None:
        total += cur_e - cur_s
    return total, raw - total


def _gpu_intervals(jobs_path, starts, tick_gpu):
    """Cost-model intervals of every prefix and flow step.

    Completed jobs: the prefix and step intervals of their jobs.jsonl rows. A job still running at the end of the run
    has no row: its prefix comes from its 'job_start' event and its later step quanta from the ticks' 'gpu' field
    (phase 'step', the running quantum and its end). Quanta that ran between two ticks are not shown there, so the
    in-flight steps are taken as one interval from the prefix end to the last end shown; it contains one CPU boundary
    (charged scheduler overhead, GPU idle) before each step: the prefix decision before step 1 and a step decision
    before each later step, i.e. 'depth' of the last shown quantum boundaries.

    Returns (intervals, inflight, overheads, jobs_rows, checks): inflight = {'prefix': n, 'step': n} boundaries inside
    the in-flight interval; overheads = {'prefix': [...], 'step': [...]} charged boundary overheads of the completed
    jobs (prefix decisions and step decisions)."""
    intervals = []
    overheads = {'prefix': [], 'step': []}
    done = set()
    checks = {}
    rows = 0
    for row in iter_jsonl(jobs_path):
        rows += 1
        jid = row.get('job_id')
        done.add(jid)
        p = row.get('prefix') or {}
        ls, c = fnum(p.get('launch_s')), fnum(p.get('timeline_cost_s'))
        if ls is not None and c is not None:
            intervals.append((ls, ls + c))
        elif p:
            checks['prefix_without_interval'] = checks.get('prefix_without_interval', 0) + 1
        o = fnum((p.get('decision') or {}).get('overhead_s'))
        if o is not None:
            overheads['prefix'].append(o)
        for st in row.get('steps') or []:
            ls, c = fnum(st.get('launch_s')), fnum(st.get('timeline_cost_s'))
            if ls is not None and c is not None:
                intervals.append((ls, ls + c))
            else:
                checks['step_without_interval'] = checks.get('step_without_interval', 0) + 1
            o = fnum((st.get('decision') or {}).get('overhead_s'))
            if o is not None:
                overheads['step'].append(o)
    inflight = {'prefix': 0, 'step': 0}
    for jid, ev in starts.items():
        if jid in done:
            continue
        pe, pc = fnum(ev.get('prefix_end_s')), fnum(ev.get('prefix_timeline_s'))
        if pe is None or pc is None:
            checks['inflight_prefix_unknown'] = checks.get('inflight_prefix_unknown', 0) + 1
            continue
        intervals.append((pe - pc, pe))
        shown = [(end, depth) for end, depth in tick_gpu.get(jid, []) if end > pe]
        if shown:
            last_end = max(end for end, _ in shown)
            last_depth = max(int(depth) for _, depth in shown if depth is not None) if any(
                depth is not None for _, depth in shown) else len(shown)
            intervals.append((pe, last_end))
            if last_depth >= 1:
                inflight['prefix'] += 1
                inflight['step'] += last_depth - 1
    return intervals, inflight, overheads, rows, checks


def recompute_run(run_dir):
    """Every Table I column of this script for one run directory (definitions in the module docstring)."""
    out = {k: None for k in RUN_FIELDS}
    out.update(load_run_meta(run_dir))
    checks = {}
    problems = []
    log_dir = os.path.join(run_dir, LOG_DIR)
    for name in LOG_FILES:
        if not os.path.isfile(os.path.join(log_dir, name)):
            problems.append('missing %s' % os.path.join(LOG_DIR, name))
    if out['validity_rule'] is None:
        problems.append('unknown arm %r (no validity rule)' % (out['arm'],))
    if problems:
        out['checks'], out['problems'] = checks, problems
        return out

    def bump(key, n=1):
        checks[key] = checks.get(key, 0) + n

    # Events: accepted commits, job starts and ends.
    commits = []
    starts = {}
    job_end_events = 0
    for ev in iter_jsonl(os.path.join(log_dir, 'events.jsonl')):
        kind = ev.get('kind')
        if kind == 'commit':
            cs = fnum(ev.get('commit_s'))
            if cs is None:
                bump('commit_without_time')
                continue
            commits.append((cs, ev))
        elif kind == 'job_start':
            starts[ev.get('job_id')] = ev
        elif kind == 'job_end':
            job_end_events += 1
    commits.sort(key=lambda x: x[0])
    out['commits'] = len(commits)
    first_commit = commits[0][0] if commits else None
    out['first_commit_s'] = first_commit
    max_age = out['max_age_s']
    for cs, ev in commits:
        cap, dl = fnum(ev.get('capture_s')), fnum(ev.get('deadline_s'))
        if out['validity_rule'] == 'deadline' and cap is not None and dl is not None and max_age is not None:
            if dl > cap + max_age + 1e-6:
                bump('deadline_beyond_max_age')

    # Ticks: one pass, validity of the committed action rebuilt from the commit events.
    rule = out['validity_rule']
    n = after = missed_after = missed_all = exp_after = exp_all = invalid = 0
    fb_ticks = episodes = track = 0
    fb_reason = {}
    ages = []
    tracked = []
    times = []
    tick_gpu = {}
    prev_fb = False
    ci = -1
    brake = out['fallback_brake']
    for r in iter_jsonl(os.path.join(log_dir, 'ticks.jsonl')):
        t = fnum(r.get('sim_s'))
        if t is None:
            bump('tick_without_time')
            continue
        if times and t <= times[-1]:
            bump('ticks_not_increasing')
        times.append(t)
        n += 1
        while ci + 1 < len(commits) and commits[ci + 1][0] <= t + TIME_TOL_S:
            ci += 1
        inc = commits[ci][1] if ci >= 0 else None
        state = 'none'
        if inc is not None:
            if rule == 'age':
                cap = fnum(inc.get('capture_s'))
                if cap is None or max_age is None:
                    state = 'invalid'
                else:
                    state = 'valid' if t - cap < max_age else 'expired'
            else:
                dl = fnum(inc.get('deadline_s'))
                if dl is None:
                    state = 'invalid'
                else:
                    state = 'valid' if t < dl else 'expired'
        is_after = first_commit is not None and t >= first_commit - TIME_TOL_S
        if is_after:
            after += 1
        if state != 'valid':
            missed_all += 1
            if is_after:
                missed_after += 1
        if state == 'expired':
            exp_all += 1
            if is_after:
                exp_after += 1
        if state == 'invalid':
            invalid += 1
        tick_inc = r.get('incumbent') or None
        tick_job = tick_inc.get('job_id') if isinstance(tick_inc, dict) else None
        if tick_job != (inc.get('job_id') if inc is not None else None):
            bump('incumbent_mismatch_ticks')
        elif inc is not None and tick_inc.get('depth') != inc.get('depth'):
            bump('incumbent_depth_mismatch_ticks')
        mode = r.get('mode')
        reason = r.get('fallback_reason')
        fb = mode == 'fallback'
        if mode not in ('track', 'fallback'):
            bump('mode_other')
        if fb != (reason is not None):
            bump('fallback_flag_mismatch')
        # The analysis reads the fallback ratio from the all-tick DMR column (conditions.csv 'column'); the two are
        # equal exactly when the fallback applies at the ticks without a valid committed action and only there.
        if fb and state == 'valid':
            bump('fallback_with_valid_action')
        elif not fb and state != 'valid':
            bump('no_fallback_without_valid_action')
        if fb:
            fb_ticks += 1
            key = str(reason)
            fb_reason[key] = fb_reason.get(key, 0) + 1
            if not prev_fb:
                episodes += 1
            b = fnum((r.get('control') or {}).get('brake'))
            if brake is not None and b != brake:
                bump('fallback_not_full_brake')
        prev_fb = fb
        if mode == 'track':
            track += 1
            cap = fnum(inc.get('capture_s')) if inc is not None else None
            if cap is None:
                bump('track_without_commit')
            else:
                ages.append(t - cap)
            if inc is not None:
                tracked.append((t, ci))
        g = r.get('gpu')
        if isinstance(g, dict) and g.get('phase') == 'step':
            end = fnum(g.get('busy_until_s'))
            if end is not None:
                tick_gpu.setdefault(g.get('job_id'), []).append((end, fnum(g.get('depth'))))
    if n == 0:
        problems.append('no ticks')
        out['checks'], out['problems'] = checks, problems
        return out
    diffs = np.diff(np.asarray(times, dtype=float)) if n > 1 else np.asarray([0.05])
    dt = float(np.median(diffs))
    if n > 1 and bool(np.any(np.abs(diffs - dt) > 1e-6)):
        bump('tick_spacing_irregular', int(np.sum(np.abs(diffs - dt) > 1e-6)))
    out['ticks'] = n
    out['tick_dt_s'] = dt
    out['first_tick_s'] = times[0]
    out['last_tick_s'] = times[-1]
    lo, hi = times[0], times[-1] + dt
    out['sim_span_s'] = hi - lo
    out['ticks_after_first_commit'] = after
    out['missed_ticks_after_first_commit'] = missed_after
    out['dmr'] = missed_after / after if after else None
    out['missed_ticks_all'] = missed_all
    out['dmr_all_ticks'] = missed_all / n
    out['expired_ticks_after_first_commit'] = exp_after
    out['expired_ratio_after_first_commit'] = exp_after / after if after else None
    out['expired_ticks_all'] = exp_all
    out['expired_ratio_all_ticks'] = exp_all / n
    out['invalid_ticks'] = invalid
    out['fallback_ticks'] = fb_ticks
    out['fallback_ratio'] = fb_ticks / n
    out['fallback_episodes'] = episodes
    out['fallback_by_reason'] = fb_reason
    out['track_ticks'] = track
    out['action_age_n'] = len(ages)
    out['action_age_p50_s'] = percentile(ages, 50)
    out['action_age_p95_s'] = percentile(ages, 95)
    out['action_age_mean_s'] = mean(ages)

    # GPU usage. The point value removes, at each in-flight boundary, the run's median charged overhead of that
    # boundary kind (prefix or step decision); the bounds remove none (upper) or the largest (lower).
    intervals, inflight, overheads, jobs_rows, gchecks = _gpu_intervals(
        os.path.join(log_dir, 'jobs.jsonl'), starts, tick_gpu)
    for k, v in gchecks.items():
        bump(k, v)
    if jobs_rows != job_end_events:
        checks['jobs_rows_minus_job_end_events'] = jobs_rows - job_end_events
    upper, overlap = _union_within(intervals, lo, hi)
    if overlap > 1e-9:
        checks['gpu_overlap_s'] = overlap
    busy = lower = upper
    for kind in ('prefix', 'step'):
        if not inflight[kind]:
            continue
        sample = overheads[kind] or overheads['prefix'] + overheads['step']
        if not sample:
            bump('inflight_boundaries_without_overhead_sample', inflight[kind])
            continue
        busy -= inflight[kind] * float(np.median(sample))
        lower -= inflight[kind] * float(np.max(sample))
    span = hi - lo
    out['gpu_quanta'] = len(intervals)
    out['gpu_inflight_boundaries'] = inflight['prefix'] + inflight['step']
    out['gpu_busy_s'] = busy
    out['gpu_busy_s_bounds'] = [lower, upper]
    if span > 0:
        out['gpu_usage'] = busy / span
        out['gpu_usage_bounds'] = [lower / span, upper / span]
        if out['kappa']:
            out['cuda_s_per_s'] = out['gpu_usage'] / out['kappa']
            out['cuda_s_per_s_bounds'] = [lower / span / out['kappa'], upper / span / out['kappa']]

    # P_both over the shield decision epochs (Sec. 5.1).
    rows = epochs = choice = 0
    for d in iter_jsonl(os.path.join(log_dir, 'decisions.jsonl')):
        if d.get('kind', 'decision') != 'decision':
            continue
        rows += 1
        shield = d.get('shield')
        if not isinstance(shield, dict):
            continue
        depth = fnum(d.get('depth'))
        if depth is None or depth < 1:
            bump('shield_row_depth_below_1')
            continue
        feas = d.get('feasible')
        if not isinstance(feas, list):
            bump('shield_row_without_feasible_set')
            continue
        epochs += 1
        both = len(set(feas)) == 2
        if len(feas) != len(set(feas)):
            bump('feasible_set_duplicates')
        choice += int(both)
        flag = d.get('p_both')
        if isinstance(flag, bool) and flag != both:
            bump('p_both_flag_mismatch')
    out['decision_rows'] = rows
    if out['arm'] in SHIELD_ARMS:
        out['shield_epochs'] = epochs
        out['choice_epochs'] = choice
        out['p_both'] = choice / epochs if epochs else None
    else:
        out['shield_epochs'] = epochs
        out['choice_epochs'] = choice
        if epochs:
            bump('shield_rows_in_arm_without_shield', epochs)

    # EIR and the closed-loop R_cond (Sec. 6.3) from the actor-box log, with the ego box of the run's lease; a run
    # without a usable log or ego box keeps every other column (validity_problems names the reason).
    box, box_source, box_problem = lease_ego_box(out.get('lease_params_path'))
    if box is not None:
        out['ego_box'] = {'source': box_source, 'half_m': list(box[0]), 'centre_from_hero_origin_m': list(box[1]),
                          'axis_yaw_rad': box[2]}
    val, vchecks = validity_run(log_dir, commits, tracked, track, times[-1], box=box, box_problem=box_problem)
    for k, v in vchecks.items():
        bump(k, v)
    # Every plan (run() writes them to plans.csv and drops them) and the plans a convention changes (cause_plans.csv).
    out['_plans'] = val.pop('plans', None)
    out['_cause_plans'] = val.pop('cause_plans', [])
    out.update(val)
    out['checks'] = checks
    out['problems'] = problems
    return out


def summary_values(run_dir):
    """The runtime's own values (summary.json) under the names of RUN_FIELDS; a missing field is absent."""
    path = os.path.join(run_dir, LOG_DIR, 'summary.json')
    with open(path, 'r', encoding='utf-8') as f:
        s = json.load(f)
    v4 = s.get('v4') or {}
    v3 = s.get('v3') or {}
    age = v4.get('action_age_s') or {}
    vals = {}

    def put(field, container, key):
        if isinstance(container, dict) and key in container:
            vals[field] = container[key]
    put('gpu_usage', v4, 'gpu_usage')
    put('gpu_busy_s', v4, 'gpu_busy_in_span_s')
    put('sim_span_s', v4, 'sim_span_s')
    put('ticks', v4, 'ticks')
    put('dmr', v4, 'deadline_miss_ratio_after_first_commit')
    put('dmr_all_ticks', v4, 'deadline_miss_ratio')
    put('expired_ratio_after_first_commit', v4, 'expired_ratio_after_first_commit')
    put('expired_ratio_all_ticks', s, 'expired_tick_ratio')
    put('ticks_after_first_commit', v3, 'ticks_after_first_commit')
    put('first_commit_s', v3, 'first_commit_s')
    put('fallback_ratio', s, 'fallback_tick_ratio')
    put('fallback_ticks', v4, 'fallback_ticks_total')
    put('fallback_episodes', v4, 'fallback_episodes')
    put('fallback_by_reason', v4, 'fallback_ticks')
    put('action_age_p50_s', age, 'p50')
    put('action_age_p95_s', age, 'p95')
    put('action_age_mean_s', age, 'mean')
    put('action_age_n', age, 'n')
    put('track_ticks', s, 'track_ticks')
    put('p_both', v4, 'p_both')
    put('commits', s, 'commits')
    return vals


# ----------------------------------------------------------------------------------------------------------------
# Validity outcomes (Sec. 6.3): EIR and the closed-loop R_cond from the actor-box log
# ----------------------------------------------------------------------------------------------------------------

ACTOR_LOG = 'actors.jsonl.gz'
ACTOR_SCHEMA = 'framelease_v4.actor_log/1'
# Sec. 2.4: T_pred 3.0 s (6 waypoints x 0.5 s), T_c 0.5 s, d_safe 0.5 m, time grid 0.05 s, H_bar 2.5 s.
TAU_STEP_S = 0.05
TAU_N = 61                       # samples j = 0..60, tau = 0.05 j in [0, T_pred]
KNOT_SAMPLES = 10                # waypoint i (i = 1..6) at tau = 0.5 i = sample 10 i; the LiDAR origin at sample 0
T_C_S = 0.5
H_BAR_S = 2.5
TC_SAMPLES = 10                  # T_c in samples (EIR bound of a log-censored plan)
HBAR_SAMPLES = 50                # H_bar in samples
D_SAFE_M = 0.5
HOLD_SPEED_MPS = 0.5             # a displacement slower than this keeps the previous heading (lease convention)
LIDAR_BEHIND_EGO_M = 0.39        # official LIDAR2EGO: LiDAR x = ego right, y = ego forward, origin 0.39 m behind
# Ego box of the standard validity definition when the run names no lease parameter file (or the file carries no
# _ego_shape): the documented Bench2Drive hero box, half sizes 2.4462 x 0.9184 m, centre 0.3837 m ahead of the LiDAR.
EGO_HALF_M = (2.4462, 0.9184)
EGO_CENTRE_AHEAD_OF_LIDAR_M = 0.3837
DOCUMENTED_EGO_BOX = (EGO_HALF_M, (EGO_CENTRE_AHEAD_OF_LIDAR_M - LIDAR_BEHIND_EGO_M, 0.0), 0.0)
ROW_MATCH_S = 1e-3               # an actor-log row within 1 ms of a sample time is the row of that time
MAX_BRACKET_S = 0.2              # interpolation only between bracketing rows at most 0.2 s (4 ticks) apart
TIME_TOL_S = 1e-6                # time comparisons of tick, commit and age values (Delta >= V_suf)
V_SCAN = 10                      # the first crossing is located on a 5 ms scan of its sample interval ...
V_RESOLUTION_S = 1e-4            # ... and refined by bisection to 0.1 ms
MISS_RESOLUTION_S = 1e-3         # |H - V_suf| below this: the miss rule lies within the bisection resolution (bounds)
F1_GAP_S = 1e-9                  # F1: a sample later than the last actor-log row by more than this is outside the log
ACTOR_CLASSES = ('vehicle', 'walker')
UNEVALUABLE = ('no_plan_logged', 'no_capture_pose', 'plan_not_finite', 'no_deadline')
PLAN_FIELDS = ('run_dir', 'commit_index', 'job_id', 'depth', 'capture_s', 'commit_s', 'status', 'j', 'V_lo', 'V',
               'V_suf', 'H', 'miss', 'resolution', 'j_unknown', 't_unknown', 'bound', 'tracked_ticks', 'invalid_ticks',
               'V_lin', 'miss_lin', 'invalid_ticks_lin', 'j_last_row', 'f1')
CAUSE_PLAN_FIELDS = ('run_dir', 'commit_index', 'job_id', 'depth', 'capture_s', 'cause', 'status', 'status_registered',
                     'j', 'j_last_row', 't_sample', 't_last_row', 'V', 'V_lin', 'H', 'miss', 'miss_registered',
                     'tracked_ticks', 'invalid_ticks', 'invalid_ticks_registered')
# Sec. 6.3 values with bounds (field + '_bounds'), formed by validity_values for this script and for each convention.
VALIDITY_BOUNDED = ('conflict_plans', 'v0_plans', 'log_censored_plans', 'misses', 'r_cond', 'r_cond_excl_v0',
                    'eir_invalid_ticks', 'eir')

# gzip members (RFC 1952): ID bytes, compression method deflate, header flags.
GZIP_ID = b'\x1f\x8b'
GZIP_DEFLATE = 8
GZIP_FHCRC, GZIP_FEXTRA, GZIP_FNAME, GZIP_FCOMMENT = 0x02, 0x04, 0x08, 0x10
INFLATE_CHUNK = 1 << 16


def gzip_members(raw):
    """(payloads, stop) of the bytes raw read as consecutive gzip members (RFC 1952). Each member: a 10-byte header (ID
    1f 8b, CM 8, FLG, MTIME, XFL, OS) with the optional FEXTRA, FNAME, FCOMMENT and FHCRC fields, raw deflate data and
    an 8-byte trailer (CRC-32 and length mod 2^32 of the payload, both checked here). payloads: the payloads of the
    complete members in file order. stop: None when every byte belongs to a complete member; 'truncated' when the data
    end inside a member; 'invalid' when a header, the deflate data or a trailer does not check. Nothing from the member
    where the scan stops, or after it, is used."""
    payloads = []
    view = memoryview(raw)
    size = len(raw)
    start = 0
    lead = GZIP_ID + bytes([GZIP_DEFLATE])
    while start < size:
        if raw[start:start + 3] != lead[:min(3, size - start)]:
            return payloads, 'invalid'
        if size - start < 10:
            return payloads, 'truncated'
        flg = raw[start + 3]
        at = start + 10
        if flg & GZIP_FEXTRA:
            if size - at < 2:
                return payloads, 'truncated'
            at += 2 + int.from_bytes(raw[at:at + 2], 'little')
        for field in (GZIP_FNAME, GZIP_FCOMMENT):
            if flg & field:
                nul = raw.find(b'\0', at)
                if nul < 0:
                    return payloads, 'truncated'
                at = nul + 1
        if flg & GZIP_FHCRC:
            at += 2
        inflater = zlib.decompressobj(-zlib.MAX_WBITS)
        pieces = []
        try:
            while at < size and not inflater.eof:
                block = view[at:at + INFLATE_CHUNK]
                pieces.append(inflater.decompress(block))
                at += len(block)
        except zlib.error:
            return payloads, 'invalid'
        if not inflater.eof:
            return payloads, 'truncated'
        at -= len(inflater.unused_data)
        if size - at < 8:
            return payloads, 'truncated'
        data = b''.join(pieces)
        crc_ok = int.from_bytes(raw[at:at + 4], 'little') == zlib.crc32(data)
        if not crc_ok or int.from_bytes(raw[at + 4:at + 8], 'little') != len(data) % (1 << 32):
            return payloads, 'invalid'
        payloads.append(data)
        start = at + 8
    return payloads, None


def read_actor_log(path):
    """(header, catalog {id: line}, tick rows, stop, unrecognized) of an actor-box log (format of the `actor_log.py`
    docstring): the JSON lines of its complete gzip members, joined in file order (gzip_members; stop says why the scan
    ended early, else None). The header line carries 'h', a catalog line 'c', a tick row 's' and the ego list 'e'
    (x, y, yaw at least); every other line is counted in unrecognized. A line that is not JSON raises ValueError."""
    with open(path, 'rb') as f:
        payloads, stop = gzip_members(f.read())
    header, catalog, rows, unrecognized = None, {}, [], 0
    for chunk in b''.join(payloads).split(b'\n'):
        if not chunk.strip():
            continue
        item = json.loads(chunk.decode('utf-8'))
        kind = None
        if isinstance(item, dict):
            ego = item.get('e')
            kind = ('header' if 'h' in item else 'catalog' if 'c' in item
                    else 'row' if 's' in item and isinstance(ego, list) and len(ego) >= 3 else None)
        if kind == 'header':
            header = item
        elif kind == 'catalog':
            catalog[int(item['c'])] = item
        elif kind == 'row':
            rows.append(item)
        else:
            unrecognized += 1
    return header, catalog, rows, stop, unrecognized


def carla_boxes(x, y, yaw_deg, ox, oy):
    """Right-handed centre (cx, cy) and heading of CARLA boxes: actor location (x, y) m and yaw (degrees) in CARLA's
    left-handed world, bounding-box centre offset (ox, oy) m in the actor frame (x forward, y right)."""
    psi = np.radians(yaw_deg)
    c, s = np.cos(psi), np.sin(psi)
    cx = x + c * ox - s * oy
    cy = y + s * ox + c * oy
    return cx, -cy, -psi


def _wrap(a):
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def blend_states(s0, s1, w):
    """Actor states {id: (x, y, yaw deg, half length, half width, ox, oy)} at the fraction w of the interval between the
    states s0 (w = 0) and s1 (w = 1): an actor present in both moves linearly (yaw along the shorter arc); an actor
    present in only one of them is held at that pose over the half of the interval nearer to it (w < 0.5 for s0,
    w >= 0.5 for s1)."""
    out = {}
    for aid, a in s0.items():
        b = s1.get(aid)
        if b is None:
            if w < 0.5:
                out[aid] = a
            continue
        turn = math.degrees(_wrap(math.radians(b[2] - a[2])))
        out[aid] = (a[0] + w * (b[0] - a[0]), a[1] + w * (b[1] - a[1]), a[2] + w * turn) + tuple(a[3:])
    if w >= 0.5:
        for aid, b in s1.items():
            if aid not in s0:
                out[aid] = b
    return out


def states_to_boxes(vals):
    """Right-handed boxes (cx, cy, heading, half length, half width) of a list of actor states."""
    if not vals:
        z = np.zeros(0)
        return z, z, z, z, z
    arr = np.asarray(vals, dtype=float)
    cx, cy, h = carla_boxes(arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 5], arr[:, 6])
    return cx, cy, h, arr[:, 3], arr[:, 4]


class ActorTrack(object):
    """Hero poses and vehicle / walker states of an actor-box log (CARLA frame, metres and degrees); poses and boxes are
    returned right-handed (y -> -y, yaw -> -yaw)."""

    def __init__(self, header, catalog, rows, checks):
        self.hero_id = ((header or {}).get('hero') or {}).get('id')
        self.catalog = catalog
        order = sorted(range(len(rows)), key=lambda i: float(rows[i]['s']))
        if order != list(range(len(rows))):
            checks['actor_rows_not_in_time_order'] = checks.get('actor_rows_not_in_time_order', 0) + 1
        self.rows = [rows[i] for i in order]
        self.times = np.asarray([float(r['s']) for r in self.rows], dtype=float)
        if len(self.times) > 1 and bool(np.any(np.diff(self.times) <= 0)):
            checks['actor_rows_repeated_time'] = int(np.sum(np.diff(self.times) <= 0))
        self.checks = checks
        self._row_states = {}
        self._row_boxes = {}

    def ego_pose(self, t):
        """Right-handed hero pose (x, y, heading) at time t: the row within ROW_MATCH_S, else linear between the
        bracketing rows at most MAX_BRACKET_S apart (heading along the shorter arc); None otherwise."""
        hit = self._row_at(t)
        if hit is not None:
            e = self.rows[hit]['e']
            return float(e[0]) / 100.0, -float(e[1]) / 100.0, -math.radians(float(e[2]) / 100.0)
        br = self._bracket(t)
        if br is None:
            return None
        i0, i1, w = br
        e0, e1 = self.rows[i0]['e'], self.rows[i1]['e']
        x = (float(e0[0]) + w * (float(e1[0]) - float(e0[0]))) / 100.0
        y = (float(e0[1]) + w * (float(e1[1]) - float(e0[1]))) / 100.0
        a0 = math.radians(float(e0[2]) / 100.0)
        a1 = a0 + _wrap(math.radians(float(e1[2]) / 100.0) - a0)
        return x, -y, -(a0 + w * (a1 - a0))

    def _row_at(self, t):
        i = int(np.searchsorted(self.times, t - ROW_MATCH_S))
        if i < len(self.times) and abs(self.times[i] - t) <= ROW_MATCH_S:
            return i
        return None

    def _bracket(self, t):
        i1 = int(np.searchsorted(self.times, t))
        i0 = i1 - 1
        if i0 < 0 or i1 >= len(self.times) or self.times[i1] - self.times[i0] > MAX_BRACKET_S + TIME_TOL_S:
            return None
        return i0, i1, (t - self.times[i0]) / (self.times[i1] - self.times[i0])

    def row_states(self, i):
        """{id: (x m, y m, yaw deg, half length, half width, ox, oy)} of the vehicles and walkers of row i (CARLA
        frame); None for an ego-only row."""
        if i in self._row_states:
            return self._row_states[i]
        r = self.rows[i]
        a = r.get('a')
        if a is None:
            self._row_states[i] = None
            return None
        ex, ey = r['e'][0], r['e'][1]
        out = {}
        for item in a:
            if not isinstance(item, list) or len(item) < 4:
                self.checks['actor_items_malformed'] = self.checks.get('actor_items_malformed', 0) + 1
                continue
            aid = int(item[0])
            meta = self.catalog.get(aid)
            if aid == self.hero_id:
                self.checks['hero_in_actor_rows'] = self.checks.get('hero_in_actor_rows', 0) + 1
                continue
            if meta is None:
                self.checks['actor_without_catalog'] = self.checks.get('actor_without_catalog', 0) + 1
                continue
            if meta.get('k') not in ACTOR_CLASSES:
                continue
            ext = meta.get('ext') or [0, 0, 0]
            off = meta.get('off') or [0, 0]
            out[aid] = ((float(ex) + float(item[1])) / 100.0, (float(ey) + float(item[2])) / 100.0,
                        float(item[3]) / 100.0, float(ext[0]) / 100.0, float(ext[1]) / 100.0,
                        float(off[0]) / 100.0, float(off[1]) / 100.0)
        self._row_states[i] = out
        return out

    def states_at(self, t):
        """Vehicle and walker states at time t: those of the row within ROW_MATCH_S, else blend_states of the
        bracketing rows at most MAX_BRACKET_S apart; None when t is unknown (no such row or rows, or an ego-only
        row)."""
        hit = self._row_at(t)
        if hit is not None:
            return self.row_states(hit)
        br = self._bracket(t)
        if br is None:
            return None
        i0, i1, w = br
        s0, s1 = self.row_states(i0), self.row_states(i1)
        if s0 is None or s1 is None:
            return None
        return blend_states(s0, s1, w)

    def boxes_at(self, t):
        """Right-handed vehicle and walker boxes at time t as arrays (cx, cy, heading, half length, half width), or
        None when t is unknown (states_at)."""
        hit = self._row_at(t)
        if hit is None:
            states = self.states_at(t)
            return None if states is None else states_to_boxes([states[k] for k in sorted(states)])
        if hit not in self._row_boxes:
            states = self.row_states(hit)
            self._row_boxes[hit] = None if states is None else states_to_boxes([states[k] for k in sorted(states)])
        return self._row_boxes[hit]


def lease_ego_box(path):
    """(box, source, problem): the ego box of the standard validity definition for a run whose lease parameter file is
    path (None: no file named). box = ((half length, half width) m, centre (forward, left) m from the hero origin, yaw
    of the box axis from the body heading, 0 here). The file's _ego_shape gives half_length_m, half_width_m,
    center_offset_xy (LiDAR frame: x right, y forward) and forward_yaw_rad (direction of the box's length axis in that
    frame, pi / 2 when absent); without a file, or a file without _ego_shape, the documented hero box
    (DOCUMENTED_EGO_BOX). A named file that cannot be read, an _ego_shape without these values, or a forward_yaw_rad
    other than pi / 2 (another reading of the lease footprint, not implemented here) gives no box and the problem."""
    if not path:
        return DOCUMENTED_EGO_BOX, 'documented Bench2Drive hero box (no lease parameter file)', None
    fp = resolve(path)
    try:
        with open(fp, 'r', encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        return None, None, 'lease parameter file %s not readable (%s): ego box unknown' % (path, type(e).__name__)
    shape = doc.get('_ego_shape') if isinstance(doc, dict) else None
    if shape is None:
        return DOCUMENTED_EGO_BOX, 'documented Bench2Drive hero box (%s has no _ego_shape)' % rel(fp), None
    try:
        half = (float(shape['half_length_m']), float(shape['half_width_m']))
        right, ahead = (float(v) for v in shape['center_offset_xy'])
        axis = float(shape.get('forward_yaw_rad', math.pi / 2.0))
    except (KeyError, TypeError, ValueError, AttributeError):
        return None, None, 'lease parameter file %s: _ego_shape without its sizes and centre offset' % rel(fp)
    if not all(math.isfinite(v) for v in half + (right, ahead, axis)) or min(half) <= 0:
        return None, None, 'lease parameter file %s: _ego_shape not finite and positive' % rel(fp)
    if abs(axis - math.pi / 2.0) > 1e-9:
        return None, None, ('lease parameter file %s: _ego_shape forward_yaw_rad %.9g is not pi / 2 (only the length '
                            'axis along LiDAR +y is implemented): ego box unknown' % (rel(fp), axis))
    return (half, (ahead - LIDAR_BEHIND_EGO_M, -right), 0.0), '_ego_shape of %s' % rel(fp), None


def plan_samples(plan):
    """LiDAR-frame positions (61, 2) of the samples tau_j = 0.05 j of a plan: (0, 0) at tau = 0, linear between the
    waypoints (waypoint i at tau = 0.5 i)."""
    knots = np.vstack([np.zeros((1, 2)), np.asarray(plan, dtype=float)])
    j = np.arange(TAU_N)
    seg = np.minimum(j // KNOT_SAMPLES, 5)
    frac = (j - KNOT_SAMPLES * seg) / float(KNOT_SAMPLES)
    return knots[seg] + frac[:, None] * (knots[seg + 1] - knots[seg])


def sample_headings(p):
    """LiDAR-frame body heading at every sample of p (lease convention of the standard validity definition): the capture
    heading (+y) at tau = 0; at sample j the direction of p[j + 1] - p[j - 1] (at the last sample p[60] - p[59]); a
    displacement slower than HOLD_SPEED_MPS over its span keeps the previous sample's heading, one pointing backward of
    it reverses (travel + pi)."""
    heads = np.empty(TAU_N)
    prev = heads[0] = math.pi / 2.0
    for j in range(1, TAU_N):
        a, b = j - 1, min(j + 1, TAU_N - 1)
        dx, dy = float(p[b, 0] - p[a, 0]), float(p[b, 1] - p[a, 1])
        if math.hypot(dx, dy) >= HOLD_SPEED_MPS * TAU_STEP_S * (b - a):
            travel = math.atan2(dy, dx)
            if math.cos(travel - prev) < 0.0:                             # backward motion: reversing
                travel += math.pi
            prev = travel
        heads[j] = prev
    return heads


def lidar_poses(plan, pose):
    """World LiDAR positions (x, y) and body headings at the samples of a plan placed with the true capture pose (hero
    x, y, heading; right-handed): the capture LiDAR lies LIDAR_BEHIND_EGO_M behind the hero origin; LiDAR x = right,
    y = forward."""
    p = plan_samples(plan)
    hl = sample_headings(p)
    x0, y0, th = pose
    c, s = math.cos(th), math.sin(th)
    lx = x0 - LIDAR_BEHIND_EGO_M * c + p[:, 0] * s + p[:, 1] * c
    ly = y0 - LIDAR_BEHIND_EGO_M * s - p[:, 0] * c + p[:, 1] * s
    return lx, ly, th + (hl - math.pi / 2.0)


def ego_boxes(lx, ly, head, half, off, yaw=0.0):
    """Ego boxes (cx, cy, heading, half length, half width) riding rigidly on the LiDAR poses (lx, ly, head): half sizes
    half; centre off = (forward, left) from the hero origin, i.e. LIDAR_BEHIND_EGO_M + off[0] ahead of the LiDAR; box
    axis turned by yaw from the body heading."""
    fx, fy = LIDAR_BEHIND_EGO_M + off[0], off[1]
    c, s = np.cos(head), np.sin(head)
    n = len(lx)
    return (lx + c * fx - s * fy, ly + s * fx + c * fy, head + yaw, np.full(n, float(half[0])),
            np.full(n, float(half[1])))


def plan_footprint(plan, pose, hero_half, hero_off, yaw=0.0):
    """Right-handed ego boxes (cx, cy, heading, half length, half width) at the samples j = 0..60 of a plan placed with
    the true capture pose (module docstring, 'Definitions'); hero_half, hero_off, yaw as in ego_boxes."""
    lx, ly, head = lidar_poses(plan, pose)
    return ego_boxes(lx, ly, head, hero_half, hero_off, yaw)


def _corners(cx, cy, h, hl, hw):
    c, s = np.cos(h)[:, None], np.sin(h)[:, None]
    dx = np.stack([hl, hl, -hl, -hl], axis=-1)
    dy = np.stack([hw, -hw, -hw, hw], axis=-1)
    return cx[:, None] + c * dx - s * dy, cy[:, None] + s * dx + c * dy


def _point_edges(px, py, qx, qy):
    """(N,) minimum distance from the 4 corners (px, py) to the 4 edges of the polygons (qx, qy), all (N, 4)."""
    sx, sy = qx[:, None, :], qy[:, None, :]
    ex, ey = np.roll(qx, -1, axis=1)[:, None, :] - sx, np.roll(qy, -1, axis=1)[:, None, :] - sy
    vx, vy = px[:, :, None] - sx, py[:, :, None] - sy
    den = ex * ex + ey * ey
    t = np.where(den > 0, np.clip((vx * ex + vy * ey) / np.where(den > 0, den, 1.0), 0.0, 1.0), 0.0)
    d = np.hypot(vx - t * ex, vy - t * ey)
    return d.reshape(len(px), -1).min(axis=1)


def box_distance(a, b):
    """(N,) distance between oriented rectangles a[k] and b[k] (tuples of arrays cx, cy, heading, half length, half
    width): 0 when they overlap (separating-axis test), else the least corner-to-edge distance."""
    ax, ay = _corners(*a)
    bx, by = _corners(*b)
    overlap = np.ones(len(ax), dtype=bool)
    for h in (a[2], a[2] + math.pi / 2.0, b[2], b[2] + math.pi / 2.0):
        ux, uy = np.cos(h)[:, None], np.sin(h)[:, None]
        pa, pb = ax * ux + ay * uy, bx * ux + by * uy
        overlap &= (pa.max(axis=1) >= pb.min(axis=1)) & (pb.max(axis=1) >= pa.min(axis=1))
    d = np.minimum(_point_edges(ax, ay, bx, by), _point_edges(bx, by, ax, ay))
    d[overlap] = 0.0
    return d


def distances_between(poses, box, s0, s1, j, fractions):
    """Least distance between the ego footprint and the actor boxes at the fractions f of the sample interval
    (tau_{j-1}, tau_j]: the footprint pose linear between the two samples (heading along the shorter arc), the actors
    blend_states of their states s0, s1 at the two samples. poses: (lx, ly, head) of the samples; box as in
    ego_boxes."""
    lx, ly, head = poses
    f = np.asarray(fractions, dtype=float)
    x = lx[j - 1] + f * (lx[j] - lx[j - 1])
    y = ly[j - 1] + f * (ly[j] - ly[j - 1])
    h = head[j - 1] + f * _wrap(float(head[j] - head[j - 1]))
    ego = ego_boxes(x, y, h, *box)
    owner, vals = [], []
    for k, w in enumerate(f):
        states = blend_states(s0, s1, float(w))
        for aid in sorted(states):
            owner.append(k)
            vals.append(states[aid])
    least = np.full(len(f), np.inf)
    if vals:
        idx = np.asarray(owner)
        d = box_distance(tuple(e[idx] for e in ego), states_to_boxes(vals))
        np.minimum.at(least, idx, d)
    return least


def first_crossing(track, capture_s, poses, box, j):
    """(V_lo, V): the first crossing of d_safe in (tau_{j-1}, tau_j] lies in (V_lo, V], for a plan whose sample j - 1 is
    clear and whose sample j conflicts: located on a scan of TAU_STEP_S / V_SCAN, then bisection to V_RESOLUTION_S."""
    base = TAU_STEP_S * (j - 1)
    s0 = track.states_at(capture_s + base)
    s1 = track.states_at(capture_s + TAU_STEP_S * j)
    if s0 is None or s1 is None:
        return base, TAU_STEP_S * j
    scan = np.arange(1, V_SCAN + 1) / float(V_SCAN)
    hit = np.nonzero(distances_between(poses, box, s0, s1, j, scan) <= D_SAFE_M)[0]
    k = int(hit[0]) if hit.size else V_SCAN - 1
    lo, hi = (float(scan[k - 1]) if k else 0.0), float(scan[k])
    while (hi - lo) * TAU_STEP_S > V_RESOLUTION_S:
        mid = 0.5 * (lo + hi)
        if distances_between(poses, box, s0, s1, j, [mid])[0] <= D_SAFE_M:
            hi = mid
        else:
            lo = mid
    return base + TAU_STEP_S * lo, base + TAU_STEP_S * hi


def min_clearance(track, capture_s, ego, j):
    """Minimum clearance at sample j of a plan (convention F3): the least box distance between the footprint ego
    (plan_footprint arrays) and a vehicle or walker box at capture_s + tau_j, minus d_safe; inf without such an actor
    (or without a known sample)."""
    boxes = track.boxes_at(capture_s + TAU_STEP_S * j)
    if boxes is None or not len(boxes[0]):
        return math.inf
    n = len(boxes[0])
    return float(np.min(box_distance(tuple(np.full(n, float(x[j])) for x in ego), boxes))) - D_SAFE_M


def clearance_interpolated_v(c0, c1, j):
    """V under convention F3 for a plan whose first conflicting sample is j >= 1: tau_{j-1} + 0.05 c0 / (c0 - c1) from
    the minimum clearances c0 at sample j - 1 and c1 at sample j; tau_j when c0 is infinite or c0 <= c1."""
    if not math.isfinite(c0) or c0 <= c1:
        return TAU_STEP_S * j
    return TAU_STEP_S * (j - 1) + TAU_STEP_S * c0 / (c0 - c1)


def last_row_sample(capture_s, t_last_row):
    """Convention F1: the index j of the plan sample capture_s + tau_j that lands on the last actor-log row (within
    ROW_MATCH_S, the row of that sample here) later than the row's time by more than F1_GAP_S; None otherwise."""
    j = int(round((t_last_row - capture_s) / TAU_STEP_S))
    if 0 <= j < TAU_N and t_last_row + F1_GAP_S < capture_s + TAU_STEP_S * j <= t_last_row + ROW_MATCH_S:
        return j
    return None


def plan_validity(track, plan, capture_s, box=DOCUMENTED_EGO_BOX):
    """Validity of one committed plan (module docstring, 'Definitions'): {'status': 'conflict' with 'j' (the first
    conflicting sample), 'V_lo', 'V' (the first crossing lies in (V_lo, V]; 0 and 0 when sample 0 conflicts) and 'V_lin'
    (V under convention F3; 0 when sample 0 conflicts); 'clear'; 'log_censored' with 'j_unknown', 't_unknown' (the
    first unknown sample); or 'no_capture_pose'}. box: the run's ego box (lease_ego_box)."""
    pose = track.ego_pose(capture_s)
    if pose is None:
        return {'status': 'no_capture_pose'}
    poses = lidar_poses(plan, pose)
    ego = ego_boxes(*(poses + box))
    owner, parts = [], []
    j_unknown = None
    for j in range(TAU_N):
        boxes = track.boxes_at(capture_s + TAU_STEP_S * j)
        if boxes is None:
            j_unknown = j
            break
        n = len(boxes[0])
        if n:
            owner.append(np.full(n, j))
            parts.append(boxes)
    if parts:
        jj = np.concatenate(owner)
        b = tuple(np.concatenate([p[k] for p in parts]) for k in range(5))
        a = tuple(x[jj] for x in ego)
        # Only pairs whose centres lie within both circumradii + d_safe can come within d_safe.
        near = np.hypot(a[0] - b[0], a[1] - b[1]) <= np.hypot(a[3], a[4]) + np.hypot(b[3], b[4]) + D_SAFE_M
        if near.any():
            hit = jj[near][box_distance(tuple(x[near] for x in a), tuple(x[near] for x in b)) <= D_SAFE_M]
            if hit.size:
                j = int(hit.min())
                if j == 0:
                    return {'status': 'conflict', 'j': 0, 'V_lo': 0.0, 'V': 0.0, 'V_lin': 0.0}
                v_lo, v = first_crossing(track, capture_s, poses, box, j)
                v_lin = clearance_interpolated_v(min_clearance(track, capture_s, ego, j - 1),
                                                 min_clearance(track, capture_s, ego, j), j)
                return {'status': 'conflict', 'j': j, 'V_lo': v_lo, 'V': v, 'V_lin': v_lin}
    if j_unknown is not None:
        return {'status': 'log_censored', 'j_unknown': j_unknown, 't_unknown': capture_s + TAU_STEP_S * j_unknown}
    return {'status': 'clear'}


def load_plans(jobs_path, checks):
    """((job_id, depth) -> the step plan of jobs.jsonl, None for a step without a list of 6 finite waypoints; the job
    ids with a jobs.jsonl row)."""
    plans, logged = {}, set()
    for row in iter_jsonl(jobs_path):
        jid = row.get('job_id')
        logged.add(jid)
        for st in row.get('steps') or []:
            key = (jid, st.get('depth'))
            if key in plans:
                checks['job_steps_repeated_depth'] = checks.get('job_steps_repeated_depth', 0) + 1
            p = st.get('plan')
            ok = isinstance(p, list) and len(p) == 6 and all(
                isinstance(w, list) and len(w) == 2 and all(finite(v) for v in w) for w in p)
            plans[key] = [[float(v) for v in w] for w in p] if ok else None
    return plans, logged


def _suffix(v):
    """V_suf = clip(V - T_c, 0, H_bar)."""
    return min(max(v - T_C_S, 0.0), H_BAR_S)


def plan_view(v, cause=None):
    """(status, V_lo, V, bound, j_unknown) of the plan v (validity_run) under a convention of the registered
    implementation (cause one of CAUSES; None: the values of this script). F1 turns the plans it changes (v['f1']) into
    log-censored plans without bound; F3 takes V_lin as the conflict time of every conflict plan."""
    if cause in ('F1', 'F1+F3') and v.get('f1'):
        return 'log_censored', None, None, False, v['j_last_row']
    if cause in ('F3', 'F1+F3') and v['status'] == 'conflict':
        return 'conflict', v['V_lin'], v['V_lin'], v['bound'], None
    return v['status'], v.get('V_lo'), v.get('V'), v['bound'], v.get('j_unknown')


def validity_values(status, commits, tracked, n_tracked, cause=None):
    """Counts, ratios and bounds of Sec. 6.3 (module docstring) over the plans status of validity_run, each plan as
    plan_view(plan, cause) gives it. Returns (values, by_status, miss, invalid, tracked_per_plan): values holds the
    counts, R_cond, EIR and every <field>_bounds of VALIDITY_BOUNDED (None without bounds); miss (None for a plan that
    is not a conflict), invalid and tracked_per_plan are per plan."""
    views = [plan_view(v, cause) for v in status]
    c = m = v0 = v0m = lc = u = u_v0 = unev = 0
    res = {'down': 0, 'up': 0, 'down_x': 0, 'up_x': 0}     # misses (and non-misses) within the time resolution
    by_status = {}
    miss = [None] * len(status)
    for i, (v, (st, _, vv, bound, j_unknown)) in enumerate(zip(status, views)):
        by_status[st] = by_status.get(st, 0) + 1
        lc += st == 'log_censored'
        unev += st in UNEVALUABLE
        if bound:
            u += 1
            u_v0 += int(st in UNEVALUABLE or j_unknown == 0)
        if st != 'conflict':
            continue
        v_suf = _suffix(vv)
        miss[i] = v['H'] > v_suf
        band = abs(v['H'] - v_suf) < MISS_RESOLUTION_S
        c += 1
        m += int(miss[i])
        if band:
            res['down' if miss[i] else 'up'] += 1
        if v['j'] == 0:
            v0 += 1
            v0m += int(miss[i])
        elif band:
            res['down_x' if miss[i] else 'up_x'] += 1
    inv = unk = amb = 0
    invalid = [0] * len(status)
    tracked_per_plan = [0] * len(status)
    for t, ci in tracked:
        st, v_lo, vv, bound, j_unknown = views[ci]
        tracked_per_plan[ci] += 1
        if st == 'conflict':
            age = t - fnum(commits[ci][1].get('capture_s'))
            if age >= _suffix(vv) - TIME_TOL_S:
                inv += 1
                invalid[ci] += 1
            elif age >= _suffix(v_lo) - TIME_TOL_S:
                amb += 1                       # between the V_suf of the clear and of the conflicting bracket end
        elif st in UNEVALUABLE:
            unk += 1
        elif bound:
            least = TAU_STEP_S * max(0, min(j_unknown - TC_SAMPLES, HBAR_SAMPLES))
            if t - fnum(commits[ci][1].get('capture_s')) >= least - TIME_TOL_S:
                unk += 1
    n = n_tracked
    values = {
        'conflict_plans': c, 'misses': m, 'v0_plans': v0, 'v0_misses': v0m, 'log_censored_plans': lc,
        'plans_unevaluable': u, 'miss_resolution_plans': res['down'] + res['up'],
        'r_cond': m / c if c else None, 'r_cond_excl_v0': (m - v0m) / (c - v0) if c - v0 else None,
        'eir_invalid_ticks': inv, 'eir_unevaluable_ticks': unk, 'eir_resolution_ticks': amb,
        'eir': inv / n if n else None,
    }
    values.update({f + '_bounds': None for f in VALIDITY_BOUNDED})
    if u:
        values['conflict_plans_bounds'] = [c, c + u]
        values['v0_plans_bounds'] = [v0, v0 + u_v0]
        values['log_censored_plans_bounds'] = [lc, lc + unev]
    if u or res['down'] or res['up']:
        values['misses_bounds'] = [m - res['down'], m + res['up'] + u]
        if c + u:
            values['r_cond_bounds'] = [(m - res['down']) / (c + u), (m + res['up'] + u) / (c + u)]
    if (u or res['down_x'] or res['up_x']) and c - v0 + u:
        values['r_cond_excl_v0_bounds'] = [(m - v0m - res['down_x']) / (c - v0 + u),
                                           (m - v0m + res['up_x'] + u) / (c - v0 + u)]
    if unk or amb:
        values['eir_invalid_ticks_bounds'] = [inv, inv + unk + amb]
        values['eir_bounds'] = [inv / n, (inv + unk + amb) / n]
    return values, by_status, miss, invalid, tracked_per_plan


def cause_plan(v, i, cause, t_last_row):
    """Row of cause_plans.csv: plan v (commit index i) and its outcome here and under convention cause."""
    row = {k: v.get(k) for k in ('job_id', 'depth', 'capture_s', 'status', 'j', 'V', 'V_lin', 'H', 'miss',
                                 'tracked_ticks', 'invalid_ticks', 'j_last_row')}
    row.update(commit_index=i, cause=cause, t_last_row=t_last_row)
    if cause == 'F1':
        row.update(status_registered='log_censored', miss_registered=None, invalid_ticks_registered=0,
                   t_sample=v['capture_s'] + TAU_STEP_S * v['j_last_row'])
    else:
        row.update(status_registered='conflict', miss_registered=v['miss_lin'],
                   invalid_ticks_registered=v['invalid_ticks_lin'])
    return row


def validity_run(log_dir, commits, tracked, n_tracked, last_tick_s, box=DOCUMENTED_EGO_BOX, box_problem=None):
    """EIR, closed-loop R_cond and their counts and bounds for one run (module docstring, 'Definitions'), and the same
    values under each convention of the registered implementation (registered_views; <field>_f1, _f3, _f1f3) with the
    plans the conventions change (cause_plans). commits: the accepted commit events sorted by commit_s; tracked: (t,
    index into commits) of the tracked ticks with a committed action; n_tracked: all tracked ticks; last_tick_s: the
    time of the last tick; box: the run's ego box (lease_ego_box) and box_problem the reason it is unknown."""
    out = {'validity_available': False, 'validity_problems': [], 'committed_plans': len(commits)}
    checks = {}
    if box_problem:
        out['validity_problems'].append(box_problem)
        return out, checks
    path = os.path.join(log_dir, ACTOR_LOG)
    if not os.path.isfile(path):
        out['validity_problems'].append('no %s' % os.path.join(LOG_DIR, ACTOR_LOG))
        return out, checks
    try:
        header, catalog, rows, stop, other = read_actor_log(path)
    except (ValueError, OSError) as e:
        out['validity_problems'].append('actor log does not decode: %s: %s' % (type(e).__name__, str(e)[:200]))
        return out, checks
    if stop:
        checks['actor_log_truncated' if stop == 'truncated' else 'actor_log_invalid_member'] = 1
    if other:
        checks['actor_log_unrecognized_rows'] = other
    if header is None or header.get('h') != ACTOR_SCHEMA:
        out['validity_problems'].append('actor log header absent or not %s' % ACTOR_SCHEMA)
    elif (header.get('hero') or {}).get('id') is None:
        out['validity_problems'].append('actor log header without the hero id')
    if not rows:
        out['validity_problems'].append('actor log without tick rows')
    if out['validity_problems']:
        return out, checks
    track = ActorTrack(header, catalog, rows, checks)
    t_last_row = float(track.times[-1])
    ego_only = sum(1 for r in rows if r.get('a') is None)
    if ego_only:
        checks['actor_rows_ego_only'] = ego_only
    plans, jobs_logged = load_plans(os.path.join(log_dir, 'jobs.jsonl'), checks)

    status = []
    for cs, ev in commits:
        jid, depth = ev.get('job_id'), ev.get('depth')
        cap, dl = fnum(ev.get('capture_s')), fnum(ev.get('deadline_s'))
        ident = {'job_id': jid, 'depth': depth, 'capture_s': cap, 'commit_s': cs}
        if cap is None or dl is None:
            status.append(dict(ident, status='no_deadline'))
            continue
        if (jid, depth) not in plans:
            status.append(dict(ident, status='no_plan_logged'))
            if jid in jobs_logged:
                checks['commit_without_job_step'] = checks.get('commit_without_job_step', 0) + 1
            continue
        if plans[(jid, depth)] is None:
            status.append(dict(ident, status='plan_not_finite'))
            continue
        v = dict(ident, **plan_validity(track, plans[(jid, depth)], cap, box))
        v['H'] = dl - cap
        v['j_last_row'] = last_row_sample(cap, t_last_row)
        lease = fnum(ev.get('lease_s'))
        if lease is not None and abs(lease - v['H']) > TIME_TOL_S:
            checks['lease_s_differs_from_deadline_minus_capture'] = checks.get(
                'lease_s_differs_from_deadline_minus_capture', 0) + 1
        status.append(v)
    for v in status:
        # A plan whose first unknown sample lies within the run (log tail lost, gap, ego-only rows) may hide a conflict.
        v['bound'] = v['status'] in UNEVALUABLE or (
            v['status'] == 'log_censored' and v['t_unknown'] <= last_tick_s + TIME_TOL_S)
        # Convention F1 changes a conflict first found on the last row and a clear plan whose last sample is there.
        v['f1'] = v.get('j_last_row') is not None and (
            (v['status'] == 'conflict' and v['j'] == v['j_last_row'])
            or (v['status'] == 'clear' and v['j_last_row'] == TAU_N - 1))
    values, by_status, miss, invalid, tracked_per_plan = validity_values(status, commits, tracked, n_tracked)
    for i, v in enumerate(status):
        v['tracked_ticks'], v['invalid_ticks'] = tracked_per_plan[i], invalid[i]
        if v['status'] == 'conflict':
            v['V_suf'], v['V_suf_lo'] = _suffix(v['V']), _suffix(v['V_lo'])
            v['miss'] = miss[i]
            v['resolution'] = abs(v['H'] - v['V_suf']) < MISS_RESOLUTION_S
    out.update(values)
    out.update({'validity_available': True, 'committed_plans': len(commits), 'plans_by_status': by_status})
    views = {}
    for cause in CAUSES:
        views[cause], _, miss_c, invalid_c, _ = validity_values(status, commits, tracked, n_tracked, cause)
        out.update({f + CAUSE_SUFFIX[cause]: views[cause][f] for f in CAUSE_FIELDS})
        if cause == 'F3':
            for i, v in enumerate(status):
                if v['status'] == 'conflict':
                    v['miss_lin'], v['invalid_ticks_lin'] = miss_c[i], invalid_c[i]
    out['registered_views'] = views
    f1 = [(i, v) for i, v in enumerate(status) if v['f1']]
    f3 = [(i, v) for i, v in enumerate(status) if v['status'] == 'conflict' and (
        v['miss_lin'] != v['miss'] or v['invalid_ticks_lin'] != v['invalid_ticks'])]
    out['f1_plans'], out['f3_plans'] = len(f1), len(f3)
    out['cause_plans'] = ([cause_plan(v, i, 'F1', t_last_row) for i, v in f1]
                          + [cause_plan(v, i, 'F3', t_last_row) for i, v in f3])
    out['plans'] = status
    return out, checks


# ----------------------------------------------------------------------------------------------------------------
# Inputs: runner records, runs.csv, analysis outputs
# ----------------------------------------------------------------------------------------------------------------

def load_runner_records(queue_dirs):
    """Job id -> the job's last final 'end' record of the runner (else its last 'end' record), over the queues."""
    out = {}
    for q in queue_dirs:
        path = os.path.join(q, 'status.jsonl')
        if not os.path.isfile(path):
            raise InputError('no status.jsonl in runner record directory %s' % q)
        for r in iter_jsonl(path):
            if r.get('event') != 'end' or not r.get('id'):
                continue
            jid = r['id']
            job = r.get('job') or {}
            rec = {
                'job': jid, 'queue': rel(q), 'run_dir': resolve(r.get('run_dir')), 'outcome': r.get('outcome'),
                'final': bool(r.get('final')), 'result': r.get('result') or {},
                'route_id': None if job.get('route_id') is None else str(job.get('route_id')),
                'arm': job.get('arm_name'), 'training_route': job.get('training_route'),
            }
            prev = out.get(jid)
            if prev is None or rec['final'] or not prev['final']:
                out[jid] = rec
    return out


def load_runs_csv(agg_dir):
    path = os.path.join(agg_dir, 'runs.csv')
    if not os.path.isfile(path):
        raise InputError('no runs.csv in %s' % agg_dir)
    rows = read_csv(path)
    if rows and 'job' not in rows[0]:
        raise InputError('%s has no job column' % path)
    cols = set(rows[0].keys()) if rows else set()
    return rows, cols


def runs_csv_run_dir(row):
    """The run directory a runs.csv row names (run_dir, else selected_run)."""
    for key in ('run_dir', 'selected_run'):
        v = (row.get(key) or '').strip()
        if v:
            return resolve(v)
    return None


ANALYSIS_FILES = ('conditions.csv', 'cells.csv', 'secondary.csv', 'family_S-dmr.csv', 'descriptive.csv',
                  'paired_differences.csv', 'per_scenario.csv', 'per_ability.csv', 'analysis.json')


def load_analysis(analysis_dir):
    """The analysis outputs this script compares; a missing file is recorded (and listed as a difference)."""
    out = {'dir': analysis_dir, 'missing': []}
    for name in ANALYSIS_FILES:
        path = os.path.join(analysis_dir, name)
        if not os.path.isfile(path):
            out['missing'].append(name)
            out[name] = None
            continue
        if name.endswith('.json'):
            with open(path, 'r', encoding='utf-8') as f:
                out[name] = json.load(f)
        else:
            out[name] = read_csv(path)
    if out['cells.csv'] is None and out['conditions.csv'] is not None:
        raise InputError('%s: conditions.csv without cells.csv (the routes of a condition are unknown)' % analysis_dir)
    return out


# ----------------------------------------------------------------------------------------------------------------
# Comparisons
# ----------------------------------------------------------------------------------------------------------------

DIFF_FIELDS = ('target', 'key', 'field', 'their_field', 'ours', 'theirs', 'abs_diff', 'tolerance', 'status', 'cause',
               'below_grid', 'scope', 'value_source', 'note')
# Scope of a comparison: 'analysis' for a value the analysis reads for a Table I column (the runs.csv column of
# conditions.csv 'column' on a row with analysis_use, and the analysis outputs); 'record' for every other value
# (runtime summary, runner record, the aggregator's other columns and arm_summary.csv).
SCOPES = ('analysis', 'record')
UNCLASSIFIED = 'unclassified'    # key of the differences without a cause in the counts by cause


def comparison_id(target, key, field, their_field=None):
    """Identity of a comparison: the passes over the values under the conventions (Recorder) and the comparisons
    (Comparisons) make the same calls in the same order, so the n-th comparison of an identity matches across them."""
    return (str(target), str(key), str(field), str(their_field or field))


def _bounds_hold(bounds, b, tol):
    return (bounds is not None and bounds[0] is not None and bounds[1] is not None and b is not None
            and bounds[0] - tol <= b <= bounds[1] + tol)


def value_agrees(kind, ours, theirs, bounds=None):
    """True when the other side's value theirs agrees with ours under the rules of Comparisons.compare: text equal for
    'json_text'; counts exactly, other numeric kinds at TOLERANCES, or theirs within bounds widened by the tolerance
    (also when ours is None). The causes are judged with it; kind 'json' carries no cause."""
    if kind == 'json':
        return False
    if kind == 'json_text':
        return (ours is None) == (theirs is None) and (ours is None or str(ours) == str(theirs))
    a, b = fnum(ours), fnum(theirs)
    tol = 0 if kind == 'count' else TOLERANCES.get(kind, 1e-6)
    if a is None or b is None:
        return (a is None and b is None) or (a is None and _bounds_hold(bounds, b, tol))
    return abs(a - b) <= tol or _bounds_hold(bounds, b, tol)


class Recorder(object):
    """Stands in for Comparisons in a pass over the per-run values under a convention of the registered implementation
    (CAUSES): records, per comparison identity and in call order, the value this side would compare and its bounds."""

    def __init__(self):
        self.values = {}

    def absent(self, *args, **kw):
        return None

    def compare(self, target, key, field, ours, theirs, their_field=None, kind=None, bounds=None, **kw):
        self.values.setdefault(comparison_id(target, key, field, their_field), []).append((ours, bounds))
        return None


class Comparisons(object):
    """Every comparison made; the differences are those with a status other than 'agree'. variants: cause -> the
    values a Recorder pass recorded under that convention (the cause of a difference)."""

    def __init__(self, variants=None):
        self.rows = []
        self.counts = {}
        self._absent = set()
        self.variants = variants or {}
        self._seen = {}

    def _add(self, rec):
        c = self.counts.setdefault(rec['target'], {'compared': 0, 'differences': 0, 'analysis_differences': 0,
                                                   'agree_within_inflight_bounds': 0,
                                                   'agree_within_validity_bounds': 0, 'differences_by_cause': {},
                                                   'analysis_differences_by_cause': {},
                                                   'agree_within_bounds_by_cause': {}})
        c['compared'] += 1
        within = rec.pop('within_bounds', None)
        at_cause = rec.pop('within_bounds_cause', None)
        if rec['status'] == 'agree' and within:
            c['agree_within_%s_bounds' % within] += 1
            if at_cause:
                c['agree_within_bounds_by_cause'][at_cause] = c['agree_within_bounds_by_cause'].get(at_cause, 0) + 1
        if rec['status'] != 'agree':
            cause = rec.get('cause') or UNCLASSIFIED
            c['differences'] += 1
            c['differences_by_cause'][cause] = c['differences_by_cause'].get(cause, 0) + 1
            if rec.get('scope') == 'analysis':
                c['analysis_differences'] += 1
                c['analysis_differences_by_cause'][cause] = c['analysis_differences_by_cause'].get(cause, 0) + 1
            self.rows.append(rec)

    def _variant(self, cause, cid, occurrence):
        vals = self.variants.get(cause, {}).get(cid)
        return vals[occurrence] if vals and occurrence < len(vals) else None

    def _classify(self, rec, cid, occurrence, kind, theirs):
        """The cause of a difference (the first convention whose value the other side agrees with, bounds included),
        or for an agreement within bounds the first convention whose point value the other side equals."""
        for cause in CAUSES:
            got = self._variant(cause, cid, occurrence)
            if got is None:
                continue
            value, bounds = got
            if rec['status'] != 'agree' and value_agrees(kind, value, theirs, bounds):
                rec['cause'] = cause
                rec['note'] = (rec['note'] + '; ' if rec['note'] else '') + 'equal to the value %s under %s' % (
                    _show(value), cause)
                return
            if rec['status'] == 'agree' and rec.get('within_bounds') and value_agrees(kind, value, theirs) \
                    and not value_agrees(kind, rec['ours'], theirs):
                rec['within_bounds_cause'] = cause
                return

    def absent(self, target, what, note='', scope='record'):
        """An expected column / field / file the other side lacks: one difference per target and name."""
        if (target, what) in self._absent:
            return
        self._absent.add((target, what))
        self._add({'target': target, 'key': '*', 'field': None, 'their_field': what, 'ours': None, 'theirs': None,
                   'abs_diff': None, 'tolerance': None, 'status': 'absent', 'cause': '', 'below_grid': None,
                   'scope': scope, 'value_source': None,
                   'note': note or 'expected by this script, absent on the other side'})

    def compare(self, target, key, field, ours, theirs, their_field=None, kind=None, bounds=None,
                value_source='raw', note='', scope='record'):
        kind = kind or FIELD_KIND.get(field, 'fraction')
        cid = comparison_id(target, key, field, their_field)
        occurrence = self._seen.get(cid, 0)
        self._seen[cid] = occurrence + 1
        rec = self._judge(target, key, field, ours, theirs, their_field, kind, bounds, value_source, note, scope)
        if self.variants and (rec['status'] != 'agree' or rec.get('within_bounds')):
            self._classify(rec, cid, occurrence, kind, theirs)
        self._add(rec)
        return rec

    def _judge(self, target, key, field, ours, theirs, their_field, kind, bounds, value_source, note, scope):
        rec = {'target': target, 'key': key, 'field': field, 'their_field': their_field or field, 'ours': ours,
               'theirs': theirs, 'abs_diff': None, 'tolerance': None, 'status': 'agree', 'cause': '',
               'below_grid': None, 'scope': scope, 'value_source': value_source, 'note': note}
        if kind == 'json_text':
            if (ours is None) != (theirs is None) or (ours is not None and str(ours) != str(theirs)):
                rec['status'] = 'differ'
            return rec
        if kind == 'json':
            a = ours if ours is not None else {}
            b = theirs
            if isinstance(b, str):
                b = b.strip()
                try:
                    b = json.loads(b) if b else {}
                except ValueError:
                    b = None
            if b is None:
                b = {}
            a = {str(k): int(v) for k, v in a.items()}
            try:
                b = {str(k): int(v) for k, v in b.items()}
            except (AttributeError, TypeError, ValueError):
                b = None
            if a != b:
                rec['status'] = 'differ'
                rec['note'] = (note + '; ' if note else '') + 'mapping differs'
            return rec
        a, b = fnum(ours), fnum(theirs)
        tol = 0 if kind == 'count' else TOLERANCES.get(kind, 1e-6)
        bk = bounds_kind(field, key)

        def within():
            if _bounds_hold(bounds, b, tol):
                rec['note'] = (note + '; ' if note else '') + 'within the %s bounds [%.9g, %.9g]' % (
                    BOUNDS_LABEL[bk], bounds[0], bounds[1])
                rec['within_bounds'] = bk
                return True
            return False
        if a is None and b is None:
            return rec
        if a is None or b is None:
            if not (a is None and within()):
                rec['status'] = 'differ'
                rec['note'] = (note + '; ' if note else '') + ('ours empty' if a is None else 'theirs empty')
            return rec
        d = abs(a - b)
        rec['abs_diff'] = d
        rec['tolerance'] = tol
        if d > tol and not within():
            rec['status'] = 'differ'
            if kind != 'count':
                rec['below_grid'] = d < GRID.get(kind, 0.0)
        return rec

    def summary(self):
        def merged(name):
            out = {}
            for c in self.counts.values():
                for k, v in c[name].items():
                    out[k] = out.get(k, 0) + v
            return out
        return {'compared': sum(c['compared'] for c in self.counts.values()),
                'differences': sum(c['differences'] for c in self.counts.values()),
                'analysis_differences': sum(c['analysis_differences'] for c in self.counts.values()),
                'differences_by_cause': merged('differences_by_cause'),
                'analysis_differences_by_cause': merged('analysis_differences_by_cause'),
                'agree_within_inflight_bounds': sum(c['agree_within_inflight_bounds'] for c in self.counts.values()),
                'agree_within_validity_bounds': sum(c['agree_within_validity_bounds'] for c in self.counts.values()),
                'agree_within_bounds_by_cause': merged('agree_within_bounds_by_cause'),
                'by_target': self.counts}


def _show(x):
    return '%.9g' % x if isinstance(x, float) else str(x)


BOUNDS_LABEL = {'inflight': 'in-flight GPU', 'validity': 'Sec. 6.3 (unevaluable plans, V resolution)'}


def bounds_kind(field, key):
    """'validity' for a field or metric of Sec. 6.3 (named by the field or by a part of the key), else
    'inflight'."""
    tokens = set(re.split(r'[/:]', str(key))) | {str(field)}
    return 'validity' if tokens & set(VALIDITY_FIELDS) else 'inflight'


# runs.csv column of each recomputed field (several columns may carry one field).
RUNS_CSV_MAP = (
    ('gpu_usage', 'gpu_usage'), ('gpu_usage', 'gpu_usage_recomputed'), ('gpu_busy_s', 'gpu_busy_recomputed_s'),
    ('gpu_busy_s', 'gpu_busy_in_span_s'), ('cuda_s_per_s', 'cuda_s_per_s'), ('sim_span_s', 'sim_span_s'),
    ('ticks', 'ticks'), ('first_tick_s', 'first_tick_s'), ('last_tick_s', 'last_tick_s'),
    ('dmr', 'dmr'), ('dmr', 'deadline_miss_ratio_after_first_commit'),
    ('ticks_after_first_commit', 'ticks_after_first_commit'), ('ticks_after_first_commit', 'dmr_ticks'),
    ('dmr_all_ticks', 'deadline_miss_ratio'), ('expired_ratio_after_first_commit', 'expired_ratio_after_first_commit'),
    ('expired_ratio_all_ticks', 'expired_ratio'), ('first_commit_s', 'first_commit_s'),
    ('fallback_ticks', 'fallback_ticks'), ('fallback_episodes', 'fallback_episodes'),
    ('fallback_by_reason', 'fallback_by_reason'), ('track_ticks', 'track_ticks'),
    ('action_age_p50_s', 'action_age_p50_s'), ('action_age_p95_s', 'action_age_p95_s'),
    ('action_age_mean_s', 'action_age_mean_s'), ('p_both', 'p_both'), ('shield_epochs', 'shield_epochs'),
    ('choice_epochs', 'choice_epochs'), ('decision_rows', 'decision_epochs'), ('commits', 'commits'),
    ('kappa', 'kappa'), ('max_age_s', 'max_age_s'),
    ('committed_plans', 'committed_plans'), ('conflict_plans', 'realized_conflict_plans'),
    ('misses', 'realized_misses'), ('r_cond', 'realized_r_cond'), ('v0_plans', 'realized_v0_plans'),
    ('r_cond_excl_v0', 'realized_r_cond_excl_v0'), ('eir_invalid_ticks', 'realized_invalid_ticks'),
    ('eir', 'realized_invalid_tick_ratio'), ('log_censored_plans', 'realized_log_censored_plans'),
    ('validity_available', 'realized_available'),
)
# runs.csv column the analysis reads for each Table I metric (conditions.csv 'column'); the default is replaced by
# the analysis' own 'column' entries when an analysis directory is given.
DEFAULT_ANALYSIS_COLUMNS = {
    'gpu_usage': 'gpu_usage', 'dmr': 'dmr', 'action_age_p50_s': 'action_age_p50_s',
    'action_age_p95_s': 'action_age_p95_s', 'fallback_ratio': 'deadline_miss_ratio', 'p_both': 'p_both',
    'eir': 'realized_invalid_tick_ratio', 'r_cond': 'realized_r_cond',
}
# Fields with bounds (field + '_bounds'): GPU in-flight step quanta (Sec. 6.2); unevaluable plans and the time
# resolution of V (Sec. 6.3).
BOUNDED = ('gpu_usage', 'gpu_busy_s', 'cuda_s_per_s', 'eir', 'r_cond', 'r_cond_excl_v0', 'conflict_plans', 'misses',
           'v0_plans', 'log_censored_plans', 'eir_invalid_ticks')
# Per-run counts that analysis outputs aggregate besides the Table I metrics (analysis.json overhead fallback episodes,
# the pooled P_both of the shared-shield check): recomputed field -> runs.csv column of the same quantity.
EXTRA_CELL_FIELDS = {'fallback_episodes': 'fallback_episodes', 'choice_epochs': 'choice_epochs',
                     'shield_epochs': 'shield_epochs'}
CONDITION_RE = re.compile(r'^(?P<arm>.+)_k(?P<kappa>[0-9]+(?:\.[0-9]+)?)_s(?P<seed>[0-9]+)$')
SIGN_ZERO = 1e-12  # |difference| at or below it counts as zero in the sign counts (floating-point noise only)


def metric_kind(metric):
    """Comparison kind of an analysis metric of this script."""
    return 'seconds' if metric.startswith('action_age') else 'fraction'


def condition_parts(cond, cell=None):
    """(arm, kappa, seed) of a condition: the cells.csv columns when present, else parsed from the name
    <arm>_k<kappa>_s<seed>."""
    cell = cell or {}
    m = CONDITION_RE.match(cond or '')
    arm = (cell.get('arm') or '').strip() or (m.group('arm') if m else None)
    kappa = fnum(cell.get('kappa'))
    if kappa is None and m:
        kappa = float(m.group('kappa'))
    seed = (str(cell.get('seed') or '')).strip() or (m.group('seed') if m else '')
    return arm, kappa, seed


def compare_run(cmp, key, ours, theirs_row, cols, target='runs.csv', analysis_columns=None, note='', used=False):
    """One recomputed run against one runs.csv row: the RUNS_CSV_MAP columns and the analysis columns. On a row
    the analysis uses (used), the (field, column) pairs the analysis reads have scope 'analysis'."""
    columns = analysis_columns or DEFAULT_ANALYSIS_COLUMNS
    read = set((ANALYSIS_METRICS[m], c) for m, c in columns.items())
    for field, col in RUNS_CSV_MAP:
        scope = 'analysis' if used and (field, col) in read else 'record'
        if col not in cols:
            cmp.absent(target, col, scope=scope)
            continue
        cmp.compare(target, key, field, ours.get(field), theirs_row.get(col), their_field=col,
                    bounds=ours.get(field + '_bounds') if field in BOUNDED else None, note=note, scope=scope)
    for metric, col in sorted(columns.items()):
        field = ANALYSIS_METRICS[metric]
        if (field, col) in RUNS_CSV_MAP:
            continue
        scope = 'analysis' if used else 'record'
        if col not in cols:
            cmp.absent(target, col, note='column the analysis reads as %s, absent in runs.csv' % metric, scope=scope)
            continue
        cmp.compare(target, key, field, ours.get(field), theirs_row.get(col), their_field=col, scope=scope,
                    note=(note + '; ' if note else '') + 'column the analysis reads as %s' % metric)


def compare_summary(cmp, key, ours, run_dir):
    vals = summary_values(run_dir)
    for field in ('gpu_usage', 'gpu_busy_s', 'sim_span_s', 'ticks', 'dmr', 'dmr_all_ticks',
                  'expired_ratio_after_first_commit', 'expired_ratio_all_ticks', 'ticks_after_first_commit',
                  'first_commit_s', 'fallback_ratio', 'fallback_ticks', 'fallback_episodes', 'fallback_by_reason',
                  'action_age_p50_s', 'action_age_p95_s', 'action_age_mean_s', 'action_age_n', 'track_ticks',
                  'p_both', 'commits'):
        if field not in vals:
            cmp.absent('summary.json', field)
            continue
        cmp.compare('summary.json', key, field, ours.get(field), vals[field],
                    bounds=ours.get(field + '_bounds') if field in BOUNDED else None)


def compare_runner_result(cmp, key, ours, rec):
    res = rec.get('result') or {}
    outcome = rec.get('outcome')
    note = '' if outcome == 'ok' else 'runner outcome %r' % (outcome,)
    for field, col in (('action_age_p50_s', 'action_age_p50_s'), ('fallback_ratio', 'fallback_tick_ratio')):
        if col not in res:
            continue
        cmp.compare('runner result', key, field, ours.get(field), res.get(col), their_field='result.' + col,
                    note=note)


ARM_SUMMARY_KEY = ('protocol_arm', 'candidate', 'kappa', 'seed', 'phase', 'block')


def _key_of(row, names):
    out = []
    for n in names:
        v = (row.get(n) or '').strip()
        f = fnum(v) if n in ('kappa', 'seed') else None
        out.append(repr(f) if f is not None else v)
    return tuple(out)


def compare_arm_summary(cmp, arm_rows, runs_rows, per_job):
    """arm_summary.csv against the means / pooled ratios of the recomputed runs of the runs.csv rows with
    analysis_use (grouped by protocol arm, candidate, kappa, seed, phase and block)."""
    groups = {}
    for r in runs_rows:
        if not truthy(r.get('analysis_use')):
            continue
        groups.setdefault(_key_of(r, ARM_SUMMARY_KEY), []).append(r['job'])
    target = 'arm_summary.csv'
    cols = set(arm_rows[0].keys()) if arm_rows else set()
    for row in arm_rows:
        key = _key_of(row, ARM_SUMMARY_KEY)
        jobs = groups.get(key, [])
        vals = [per_job.get(j) for j in jobs]
        known = [v for v in vals if v is not None and not v.get('problems')]
        label = '/'.join(key)
        cmp.compare(target, label, 'routes', len(jobs), row.get('routes'), kind='count')
        source = 'raw' if len(known) == len(jobs) else 'incomplete (%d of %d runs recomputed)' % (len(known), len(jobs))

        def col_mean(field):
            return mean([v.get(field) for v in known])

        def col_mean_bounds(field):
            bs = [v.get(field + '_bounds') or (v.get(field), v.get(field)) for v in known if v.get(field) is not None]
            if not bs:
                return None
            return _bounds_or_none((mean([b[0] for b in bs]), mean([b[1] for b in bs])))

        def pooled(num, den):
            n = sum(v.get(num) or 0 for v in known)
            d = sum(v.get(den) or 0 for v in known)
            return n / d if d else None
        for col, ours in (('gpu_usage', col_mean('gpu_usage')),
                          ('deadline_miss_ratio', col_mean('dmr_all_ticks')),
                          ('deadline_miss_ratio_pooled', pooled('missed_ticks_all', 'ticks')),
                          ('deadline_miss_ratio_after_first_commit', col_mean('dmr')),
                          ('fallback_episodes', col_mean('fallback_episodes')),
                          ('action_age_p50_s', col_mean('action_age_p50_s')),
                          ('action_age_mean_s', col_mean('action_age_mean_s')),
                          ('p_both_pooled', pooled('choice_epochs', 'shield_epochs')),
                          ('realized_invalid_tick_ratio', col_mean('eir'))):
            if col not in cols:
                cmp.absent(target, col)
                continue
            kind = 'fraction_free' if col == 'fallback_episodes' else FIELD_KIND.get(col, None)
            if col in ('deadline_miss_ratio', 'deadline_miss_ratio_pooled', 'deadline_miss_ratio_after_first_commit',
                       'p_both_pooled'):
                kind = 'fraction'
            cmp.compare(target, label, col, ours, row.get(col), their_field=col, kind=kind, value_source=source,
                        bounds=col_mean_bounds({'gpu_usage': 'gpu_usage',
                                                'realized_invalid_tick_ratio': 'eir'}.get(col, col))
                        if col in ('gpu_usage', 'realized_invalid_tick_ratio') else None)


def _subset_routes(analysis_json, subset):
    """Route ids of an analysis subset (analysis.json route_table.subsets), None when unknown."""
    rt = (analysis_json or {}).get('route_table') or {}
    subs = rt.get('subsets') or {}
    lst = subs.get(subset)
    if isinstance(lst, list):
        return set(str(x.get('route_id') if isinstance(x, dict) else x) for x in lst)
    return None


def condition_values(analysis, per_job, runs_by_job, analysis_columns):
    """(condition, route_id) -> {'job', 'arm', 'kappa', 'seed', 'vals': {metric: (value, source, lower, upper)},
    'extra': {field: value}} for the cells.csv rows with status 'used'. The value is the recomputed per-run value of
    the cell's job ('raw'; GPU usage with its in-flight bounds); without a recomputed run, the runs.csv value of the
    column the analysis reads ('runs.csv'); without either, None ('none'). 'extra' holds the EXTRA_CELL_FIELDS counts
    from the same source."""
    out = {}
    problems = []
    for c in analysis.get('cells.csv') or []:
        if c.get('status') != 'used':
            continue
        try:
            jobs = json.loads(c.get('jobs') or '[]')
        except ValueError:
            jobs = []
        if len(jobs) != 1:
            problems.append('cell %s route %s: %d jobs for a used cell' % (c.get('condition'), c.get('route_id'),
                                                                         len(jobs)))
            continue
        job = jobs[0]
        ours = per_job.get(job)
        row = runs_by_job.get(job)
        raw = ours is not None and not ours.get('problems')
        vals = {}
        for metric, field in ANALYSIS_METRICS.items():
            if raw:
                x = ours.get(field)
                b = ours.get(field + '_bounds') if field in BOUNDED else None
                vals[metric] = (x, 'raw', b[0] if b else x, b[1] if b else x)
            elif row is not None and analysis_columns.get(metric) in row:
                x = fnum(row.get(analysis_columns[metric]))
                vals[metric] = (x, 'runs.csv', x, x)
            else:
                vals[metric] = (None, 'none', None, None)
        extra = {}
        for field, col in EXTRA_CELL_FIELDS.items():
            if raw:
                extra[field] = ours.get(field)
            else:
                extra[field] = fnum(row.get(col)) if row is not None else None
        arm, kappa, seed = condition_parts(c.get('condition'), c)
        out[(c.get('condition'), str(c.get('route_id')))] = {'job': job, 'vals': vals, 'extra': extra, 'arm': arm,
                                                             'kappa': kappa, 'seed': seed}
    return out, problems


def _stats(values):
    arr = np.asarray(values, dtype=float)
    return {'n': int(arr.size), 'mean': float(np.mean(arr)) if arr.size else None,
            'median': float(np.median(arr)) if arr.size else None,
            'min': float(np.min(arr)) if arr.size else None, 'max': float(np.max(arr)) if arr.size else None}


def _stats_bounded(triples):
    """Statistics of (value, lower, upper) triples, each with its bounds (mean, median, min and max are monotone)."""
    st = _stats([x for x, _, _ in triples])
    lo = _stats([x for _, x, _ in triples])
    hi = _stats([x for _, _, x in triples])
    bounds = {k: (lo[k], hi[k]) for k in ('mean', 'median', 'min', 'max')}
    return st, bounds


def _count_by(rows, key):
    out = {}
    for r in rows:
        out[r[key]] = out.get(r[key], 0) + 1
    return out


def _source_label(sources):
    s = sorted(set(sources))
    return s[0] if len(s) == 1 else '+'.join(s) if s else 'none'


def _bounds_or_none(b):
    return None if b is None or b[0] is None or b[0] == b[1] else b


CONTRAST_RE = re.compile(r'^(?P<a>.+)_minus_(?P<b>.+)_k(?P<kappa>[0-9]+(?:\.[0-9]+)?)_s(?P<seed>[0-9]+)_'
                         r'(?P<subset>[A-Za-z0-9]+)$')


def parse_contrast(name):
    """(a, b, subset) of a contrast named <arm a>_minus_<arm b>_k<kappa>_s<seed>_<subset>; None otherwise."""
    m = CONTRAST_RE.match(name or '')
    if not m:
        return None
    suffix = '_k%s_s%s' % (m.group('kappa'), m.group('seed'))
    return m.group('a') + suffix, m.group('b') + suffix, m.group('subset')


def paired_triples(by_cond, a, b, metric, keep=None, routes=None):
    """The routes where the cells of conditions a and b are both used and both carry a value of metric (within keep
    and routes when given): (value, lower, upper) triples of a, of b and of the difference a - b, the value sources
    and the routes."""
    a_routes = by_cond.get(a, {})
    b_routes = by_cond.get(b, {})
    common = set(a_routes) & set(b_routes)
    if routes is not None:
        common &= set(routes)
    ta, tb, td, srcs, used = [], [], [], [], []
    for r in sorted(x for x in common if keep is None or x in keep):
        xa, sa, la, ha = a_routes[r]['vals'][metric]
        xb, sb, lb, hb = b_routes[r]['vals'][metric]
        if xa is None or xb is None:
            continue
        ta.append((xa, la, ha))
        tb.append((xb, lb, hb))
        td.append((xa - xb, la - hb, ha - lb))
        srcs += [sa, sb]
        used.append(r)
    return ta, tb, td, srcs, used


def compare_contrast_rows(put, target, rows, by_cond, aj, contrasts):
    """n, mean_a, mean_b, mean, median, min and max of the contrast rows (secondary, family or descriptive rows, CSV or
    analysis.json) of the metrics of this script, over the paired routes of the row's subset; records the (a, b,
    subset) of each contrast in contrasts."""
    for row in rows or []:
        metric = row.get('metric')
        if metric not in ANALYSIS_METRICS:
            continue
        subset = row.get('subset') or 'all'
        contrasts.setdefault(row.get('contrast'), (row.get('a'), row.get('b'), subset))
        ta, tb, td, srcs, _ = paired_triples(by_cond, row.get('a'), row.get('b'), metric, _subset_routes(aj, subset))
        src = _source_label(srcs)
        key = '%s:%s/%s' % (target, row.get('contrast'), metric)
        kind = metric_kind(metric)
        sa_, ba = _stats_bounded(ta)
        sb_, bb = _stats_bounded(tb)
        sd, bd = _stats_bounded(td)
        put(target, key, 'n', sd['n'], row.get('n'), kind='count', value_source=src)
        put(target, key, 'mean_a', sa_['mean'], row.get('mean_a'), kind=kind, value_source=src,
            bounds=_bounds_or_none(ba['mean']))
        put(target, key, 'mean_b', sb_['mean'], row.get('mean_b'), kind=kind, value_source=src,
            bounds=_bounds_or_none(bb['mean']))
        for stat in ('mean', 'median', 'min', 'max'):
            put(target, key, stat, sd[stat], row.get(stat), kind=kind, value_source=src,
                bounds=_bounds_or_none(bd[stat]))


def compare_sdmr_structure(put, target, rows):
    """The S-dmr family (Sec. 9.3): the four H1 contrasts at kappa 1.0, seed 11, all 44 routes, Holm over 4."""
    names = sorted(str(r.get('contrast')) for r in rows)
    want = sorted('%s_k1.0_s11_all' % c for c in H1_CONTRASTS)
    put(target, 'structure', 'contrasts', json.dumps(want), json.dumps(names), kind='json_text')
    for r in rows:
        put(target, 'structure:%s' % r.get('contrast'), 'family_size', 4, r.get('family_size'), kind='count')


def compare_paired_differences(put, rows, by_cond, contrasts):
    """paired_differences.csv: the pairing status of every route row of the metrics of this script and, on a paired
    route, value_a, value_b and the difference."""
    target = 'paired_differences.csv'
    for row in rows or []:
        metric = row.get('metric')
        if metric not in ANALYSIS_METRICS:
            continue
        abs_ = contrasts.get(row.get('contrast'))
        key = '%s:%s/%s/%s' % (row.get('table'), row.get('contrast'), metric, row.get('route_id'))
        if abs_ is None:
            put(target, key, 'contrast', None, row.get('contrast'), kind='json_text',
                note='contrast not found in the contrast rows (secondary, families, descriptive)')
            continue
        a, b, _ = abs_
        route = str(row.get('route_id'))
        none = (None, 'none', None, None)
        ca = (by_cond.get(a, {}).get(route) or {}).get('vals', {}).get(metric, none)
        cb = (by_cond.get(b, {}).get(route) or {}).get('vals', {}).get(metric, none)
        kind = metric_kind(metric)
        src = _source_label([ca[1], cb[1]])
        # A route is paired when both cells are used (cells.csv); an unpaired row carries no values.
        ours_paired = route in by_cond.get(a, {}) and route in by_cond.get(b, {})
        theirs_paired = (row.get('status') or '') == 'paired'
        put(target, key, 'paired', str(ours_paired), str(theirs_paired), their_field='status', kind='json_text',
            value_source=src, note='' if ours_paired == theirs_paired else 'status %r' % row.get('status'))
        if not (ours_paired and theirs_paired):
            continue
        put(target, key, 'value_a', ca[0], row.get('value_a'), kind=kind, value_source=src,
            bounds=_bounds_or_none((ca[2], ca[3])))
        put(target, key, 'value_b', cb[0], row.get('value_b'), kind=kind, value_source=src,
            bounds=_bounds_or_none((cb[2], cb[3])))
        both = ca[0] is not None and cb[0] is not None
        put(target, key, 'difference', ca[0] - cb[0] if both else None, row.get('difference'), kind=kind,
            value_source=src, bounds=_bounds_or_none((ca[2] - cb[3], ca[3] - cb[2])) if both else None)


def compare_per_scenario(cmp, put, rows, cells_all, by_cond):
    """per_scenario.csv (Sec. 9.9): every row's status against cells.csv; on a used cell the job and the per-run
    values of the metrics of this script; an unused cell carries no value; every used cell has a row."""
    target = 'per_scenario.csv'
    cols = set(rows[0].keys()) if rows else set()
    for metric in ANALYSIS_METRICS:
        if rows and metric not in cols:
            cmp.absent(target, metric, 'column absent', scope='analysis')
    seen = set()
    for row in rows:
        cond, route = row.get('condition'), str(row.get('route_id'))
        seen.add((cond, route))
        key = '%s/%s' % (cond, route)
        cell = by_cond.get(cond, {}).get(route)
        ours_status = 'used' if cell is not None else cells_all.get((cond, route), 'no cells.csv row')
        put(target, key, 'status', ours_status, (row.get('status') or '').strip(), kind='json_text',
            note='status of the cell in cells.csv')
        if cell is not None:
            put(target, key, 'job', cell['job'], (row.get('job') or '').strip() or None, kind='json_text')
        for metric in ANALYSIS_METRICS:
            if metric not in cols:
                continue
            if cell is None:
                put(target, key, metric, None, row.get(metric), kind=metric_kind(metric),
                    note='cell not used: no value expected')
                continue
            x, src, lo, hi = cell['vals'][metric]
            put(target, key, metric, x, row.get(metric), kind=metric_kind(metric), value_source=src,
                bounds=_bounds_or_none((lo, hi)))
    for cond, routes in sorted(by_cond.items()):
        for route in sorted(routes):
            if (cond, route) not in seen:
                put(target, '%s/%s' % (cond, route), 'row', 'used', None, kind='json_text',
                    note='used cell without a per_scenario.csv row')


def compare_per_ability(put, target, rows, by_cond):
    """per_ability rows (CSV or analysis.json) of the metrics of this script: the listed routes are exactly the paired
    ones among them; n, mean_a, mean_b, mean and the sign counts of the differences over them. The ability membership
    of a route (the official mapping) is not checked."""
    for row in rows or []:
        metric = row.get('metric')
        if metric not in ANALYSIS_METRICS:
            continue
        routes = row.get('routes')
        if isinstance(routes, str):
            routes = routes.split('|')
        routes = sorted(set(str(r).strip() for r in (routes or []) if str(r).strip()))
        key = '%s:%s/%s/%s' % (target, row.get('contrast'), metric, row.get('ability'))
        ta, tb, td, srcs, used = paired_triples(by_cond, row.get('a'), row.get('b'), metric, routes=routes)
        src = _source_label(srcs)
        kind = metric_kind(metric)
        put(target, key, 'routes', json.dumps(used), json.dumps(routes), kind='json_text', value_source=src,
            note='' if used == routes else 'listed routes without a paired value: %s'
            % ', '.join(sorted(set(routes) - set(used))))
        sa_, ba = _stats_bounded(ta)
        sb_, bb = _stats_bounded(tb)
        sd, bd = _stats_bounded(td)
        put(target, key, 'n', sd['n'], row.get('n'), kind='count', value_source=src)
        put(target, key, 'mean_a', sa_['mean'], row.get('mean_a'), kind=kind, value_source=src,
            bounds=_bounds_or_none(ba['mean']))
        put(target, key, 'mean_b', sb_['mean'], row.get('mean_b'), kind=kind, value_source=src,
            bounds=_bounds_or_none(bb['mean']))
        put(target, key, 'mean', sd['mean'], row.get('mean'), kind=kind, value_source=src,
            bounds=_bounds_or_none(bd['mean']))
        diffs = [x for x, _, _ in td]
        pos = sum(1 for x in diffs if x > SIGN_ZERO)
        neg = sum(1 for x in diffs if x < -SIGN_ZERO)
        for field, v in (('n_positive', pos), ('n_negative', neg), ('n_zero', len(diffs) - pos - neg)):
            put(target, key, field, v, row.get(field), kind='count', value_source=src)


def _section(obj, *path):
    """The value at a path of nested dicts; None when a level is missing."""
    for p in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(p)
    return obj


def compare_overhead(put, aj, by_cond):
    """analysis.json overhead (Secs. 7.6, 9.5: DMR reported as measured): per condition, the used runs, the DMR runs /
    mean / median / max over them and the fallback episodes (runs with any, total)."""
    target = 'analysis.json'
    ov = _section(aj, 'overhead')
    if not isinstance(ov, dict):
        put(target, 'overhead', 'section', 'present', None, their_field='overhead', kind='json_text',
            note='section absent')
        return
    for cond in sorted(set(ov) | set(by_cond)):
        o = ov.get(cond)
        cells = by_cond.get(cond, {})
        key = 'overhead:%s' % cond
        if not isinstance(o, dict):
            put(target, key, 'runs', len(cells), None, their_field='overhead.%s' % cond, kind='count',
                note='condition absent in overhead')
            continue
        put(target, key, 'runs', len(cells), o.get('runs'), their_field='overhead.runs', kind='count')
        dmr = [v['vals']['dmr'] for _, v in sorted(cells.items()) if v['vals']['dmr'][0] is not None]
        st, bounds = _stats_bounded([(x, lo, hi) for x, _, lo, hi in dmr])
        src = _source_label(s for _, s, _, _ in dmr)
        d = _section(o, 'dmr') if isinstance(_section(o, 'dmr'), dict) else {}
        put(target, key, 'dmr_runs', st['n'], d.get('runs'), their_field='overhead.dmr.runs', kind='count',
            value_source=src)
        for stat in ('mean', 'median', 'max'):
            put(target, key, 'dmr_' + stat, st[stat], d.get(stat), their_field='overhead.dmr.' + stat,
                kind='fraction', value_source=src, bounds=_bounds_or_none(bounds[stat]))
        fe = [v['extra']['fallback_episodes'] for v in cells.values()]
        known = [x for x in fe if x is not None]
        note = '' if len(known) == len(fe) else '%d of %d used runs without a fallback-episode count' % (
            len(fe) - len(known), len(fe))
        f = _section(o, 'fallback_episodes') if isinstance(_section(o, 'fallback_episodes'), dict) else {}
        put(target, key, 'fallback_episodes_runs_with_any', sum(1 for x in known if x > 0), f.get('runs_with_any'),
            their_field='overhead.fallback_episodes.runs_with_any', kind='count', note=note)
        put(target, key, 'fallback_episodes_total', sum(known), f.get('total'),
            their_field='overhead.fallback_episodes.total', kind='count', note=note)


FINDING2_GPU_CONTRASTS = tuple('fl_full_minus_%s_k1.0_s11_all' % b for b in ('age_only', 'event_triggered'))


def compare_gpu_descriptive(put, aj, by_cond, contrasts):
    """analysis.json decisions.H1.finding_2.gpu_usage_descriptive (Sec. 9.2: finding 2 is shown next to the GPU-usage
    contrasts, which are descriptive): the contrasts Full FrameLease - Age-Only and Full FrameLease - Event-Triggered
    (kappa 1.0, seed 11, all routes), each with metric gpu_usage, label 'descriptive', n and mean."""
    target = 'analysis.json'
    path = 'decisions.H1.finding_2.gpu_usage_descriptive'
    rows = _section(aj, 'decisions', 'H1', 'finding_2', 'gpu_usage_descriptive')
    if not isinstance(rows, list):
        put(target, 'finding_2', 'section', 'present', None, their_field=path, kind='json_text',
            note='section absent')
        return
    put(target, 'finding_2:structure', 'contrasts', json.dumps(sorted(FINDING2_GPU_CONTRASTS)),
        json.dumps(sorted(str(r.get('contrast')) for r in rows)), their_field=path, kind='json_text')
    for r in rows:
        name = r.get('contrast')
        key = 'finding_2:%s' % name
        abs_ = contrasts.get(name) or parse_contrast(name)
        if abs_ is None:
            put(target, key, 'contrast', None, name, their_field=path, kind='json_text',
                note='contrast not found in the contrast rows and not of the form a_minus_b_k<kappa>_s<seed>_<subset>')
            continue
        a, b, subset = abs_
        _, _, td, srcs, _ = paired_triples(by_cond, a, b, 'gpu_usage', _subset_routes(aj, subset))
        sd, bd = _stats_bounded(td)
        src = _source_label(srcs)
        put(target, key, 'metric', 'gpu_usage', r.get('metric'), their_field=path + '.metric', kind='json_text')
        put(target, key, 'label', 'descriptive', r.get('label'), their_field=path + '.label', kind='json_text')
        put(target, key, 'n', sd['n'], r.get('n'), their_field=path + '.n', kind='count', value_source=src)
        put(target, key, 'mean', sd['mean'], r.get('mean'), their_field=path + '.mean', kind='fraction',
            value_source=src, bounds=_bounds_or_none(bd['mean']))


SHARED_SHIELD_ARMS = ('fl_full', 'fl_heuristic')


def compare_p_both_shared_shield(put, aj, cond_vals):
    """analysis.json manipulation.analysed_runs.p_both_shared_shield (Sec. 9.7 'Shared shield', descriptive): per
    kappa, the (route, seed) cells where fl_full and fl_heuristic are both used and both have a P_both; 'routes' is
    their number; each arm's mean P_both and pooled P_both (sum of choice epochs / sum of shield epochs; None unless
    every one of these runs has both counts) over them; the mean difference fl_full - fl_heuristic. A kappa without
    such a cell on this side and without an entry on the other is not compared."""
    target = 'analysis.json'
    path = 'manipulation.analysed_runs.p_both_shared_shield'
    ps = _section(aj, 'manipulation', 'analysed_runs', 'p_both_shared_shield')
    if not isinstance(ps, dict):
        put(target, 'p_both_shared_shield', 'section', 'present', None, their_field=path, kind='json_text',
            note='section absent')
        return
    groups = {}
    for (cond, route), v in cond_vals.items():
        if v.get('arm') in SHARED_SHIELD_ARMS and v.get('kappa') is not None:
            groups.setdefault('k%.1f' % v['kappa'], {}).setdefault(v['arm'], {})[(route, v.get('seed'))] = v
    for k in sorted(set(groups) | set(ps)):
        arms = groups.get(k, {})
        full, heur = arms.get('fl_full', {}), arms.get('fl_heuristic', {})
        keys = sorted(x for x in set(full) & set(heur)
                      if full[x]['vals']['p_both'][0] is not None and heur[x]['vals']['p_both'][0] is not None)
        if not keys and k not in ps:
            continue  # no pair at this kappa on either side
        theirs = ps.get(k) if isinstance(ps.get(k), dict) else {}
        key = 'p_both_shared_shield:%s' % k
        base = '%s.%s.' % (path, k)
        src = _source_label(c[x]['vals']['p_both'][1] for c in (full, heur) for x in keys)
        put(target, key, 'routes', len(keys), theirs.get('routes'), their_field=base + 'routes', kind='count',
            value_source=src)
        for arm, cells in (('fl_full', full), ('fl_heuristic', heur)):
            th = theirs.get(arm) if isinstance(theirs.get(arm), dict) else {}
            put(target, key, arm + '_mean', mean([cells[x]['vals']['p_both'][0] for x in keys]), th.get('mean'),
                their_field=base + arm + '.mean', kind='fraction', value_source=src)
            num = [cells[x]['extra']['choice_epochs'] for x in keys]
            den = [cells[x]['extra']['shield_epochs'] for x in keys]
            pooled = None
            if keys and all(n_ is not None for n_ in num + den) and sum(den) > 0:
                pooled = sum(num) / sum(den)
            put(target, key, arm + '_pooled', pooled, th.get('pooled'), their_field=base + arm + '.pooled',
                kind='fraction', value_source=src)
        diff = mean([full[x]['vals']['p_both'][0] - heur[x]['vals']['p_both'][0] for x in keys])
        put(target, key, 'mean_difference', diff, theirs.get('mean_difference'),
            their_field=base + 'mean_difference', kind='fraction', value_source=src)


def compare_analysis(cmp, analysis, cond_vals):
    """Every analysis output value of the Table I metrics of this script (module docstring, 'analysis'): conditions.csv
    route means; the contrast rows of secondary.csv, family_S-dmr.csv, descriptive.csv and analysis.json (secondary,
    families) with the S-dmr structure; paired_differences.csv; per_scenario.csv; per_ability.csv and analysis.json
    per_ability; analysis.json overhead, decisions.H1.finding_2.gpu_usage_descriptive and
    manipulation.analysed_runs.p_both_shared_shield."""

    def put(*args, **kw):
        kw.setdefault('scope', 'analysis')
        return cmp.compare(*args, **kw)

    for name in analysis['missing']:
        cmp.absent('analysis', name, 'file absent', scope='analysis')
    aj = analysis.get('analysis.json')
    by_cond = {}
    for (cond, route), v in cond_vals.items():
        by_cond.setdefault(cond, {})[route] = v
    cells_all = {(c.get('condition'), str(c.get('route_id'))): (c.get('status') or '').strip()
                 for c in analysis.get('cells.csv') or []}
    # conditions.csv
    for row in analysis.get('conditions.csv') or []:
        metric = row.get('metric')
        if metric not in ANALYSIS_METRICS or row.get('statistic') != 'route_mean':
            continue
        cond, subset = row.get('condition'), row.get('subset') or 'all'
        routes = by_cond.get(cond, {})
        keep = _subset_routes(aj, subset)
        cells = [v['vals'][metric] for r, v in routes.items() if keep is None or r in keep]
        triples = [(x, lo, hi) for x, _, lo, hi in cells if x is not None]
        src = _source_label(s for x, s, _, _ in cells if x is not None)
        st, bounds = _stats_bounded(triples)
        key = '%s/%s/%s' % (cond, subset, metric)
        kind = 'seconds' if metric.startswith('action_age') else 'fraction'
        note = '' if keep is not None or subset == 'all' else 'subset %s unknown: all used routes' % subset
        put('conditions.csv', key, 'n', st['n'], row.get('n'), kind='count', value_source=src, note=note)
        for stat in ('mean', 'median', 'min', 'max'):
            put('conditions.csv', key, stat, st[stat], row.get(stat), kind=kind, value_source=src, note=note,
                        bounds=_bounds_or_none(bounds[stat]))
    # Contrast rows: secondary.csv, family_S-dmr.csv, descriptive.csv and the analysis.json lists.
    contrasts = {}
    for name in ('secondary.csv', 'family_S-dmr.csv', 'descriptive.csv'):
        compare_contrast_rows(put, name, analysis.get(name), by_cond, aj, contrasts)
    if analysis.get('family_S-dmr.csv') is not None:
        compare_sdmr_structure(put, 'family_S-dmr.csv', analysis['family_S-dmr.csv'])
    if isinstance(aj, dict):
        for section in ('secondary', 'families', 'per_ability', 'descriptive'):
            if not isinstance(aj.get(section), list):
                cmp.absent('analysis.json', section, 'list absent', scope='analysis')
        compare_contrast_rows(put, 'analysis.json:secondary', _list(aj.get('secondary')), by_cond, aj, contrasts)
        compare_contrast_rows(put, 'analysis.json:descriptive', _list(aj.get('descriptive')), by_cond, aj, contrasts)
        families = [f for f in _list(aj.get('families')) if isinstance(f, dict)]
        for fam in families:
            compare_contrast_rows(put, 'analysis.json:families/%s' % fam.get('name'), _list(fam.get('rows')),
                                  by_cond, aj, contrasts)
        sdmr = [f for f in families if f.get('name') == 'S-dmr']
        if len(sdmr) == 1:
            compare_sdmr_structure(put, 'analysis.json:families/S-dmr', _list(sdmr[0].get('rows')))
        elif isinstance(aj.get('families'), list):
            put('analysis.json:families/S-dmr', 'structure', 'families_named_S-dmr', 1, len(sdmr), kind='count')
    # Per-route rows.
    compare_paired_differences(put, analysis.get('paired_differences.csv'), by_cond, contrasts)
    if analysis.get('per_scenario.csv') is not None:
        compare_per_scenario(cmp, put, analysis['per_scenario.csv'], cells_all, by_cond)
    compare_per_ability(put, 'per_ability.csv', analysis.get('per_ability.csv'), by_cond)
    # analysis.json sections.
    if isinstance(aj, dict):
        compare_per_ability(put, 'analysis.json:per_ability', _list(aj.get('per_ability')), by_cond)
        compare_overhead(put, aj, by_cond)
        compare_gpu_descriptive(put, aj, by_cond, contrasts)
        compare_p_both_shared_shield(put, aj, cond_vals)


def _list(x):
    return x if isinstance(x, list) else []


# ----------------------------------------------------------------------------------------------------------------
# Interim guard (Sec. 9.11)
# ----------------------------------------------------------------------------------------------------------------

PROTECTED_OUT = ('framelease_v4', 'outputs/framelease_v4/queue_', 'outputs/framelease_v4/p1_driver',
                 'outputs/framelease_v4/p1_jobs', 'outputs/framelease_v4/tuning',
                 'outputs/framelease_v4/registration', 'outputs/framelease_v4/rl_dev',
                 'outputs/framelease_v4/amendment_', 'outputs/framelease_v4/phase_driver',
                 'outputs/framelease_v4/analysis/final_')


def protected_out(path):
    """True when an output directory lies in a directory this script never writes."""
    r = os.path.relpath(os.path.realpath(path), os.path.realpath(ROOT))
    if r.startswith('..'):
        return False
    r = r.replace(os.sep, '/')
    for p in PROTECTED_OUT:
        if p.endswith('_'):
            if r.startswith(p):
                return True
        elif r == p or r.startswith(p + '/'):
            return True
    return False


def load_test_routes(path):
    """Test route ids (route_text) of a route split (registered format: 'test' list of objects with 'route_id')."""
    with open(path, 'r', encoding='utf-8') as f:
        d = json.load(f)
    test = d.get('test')
    if not isinstance(test, list) or not test:
        raise InputError('%s: no test route list' % path)
    routes = set(route_text(x.get('route_id') if isinstance(x, dict) else x) for x in test)
    if None in routes:
        raise InputError('%s: a test route without a route id' % path)
    return routes


FREEZE_SCHEMA = 'framelease_v4.analysis_freeze/1'
FREEZE_RECORD_NAME = 'analysis_freeze.json'       # name of the record in its final_<stamp> directory (G8 layout)
FREEZE_TRIGGERS = ('all_final', 'cut')
FREEZE_OUTCOMES = ('ok', 'agent_crashed', 'sim_failure', 'cut')
REGISTERED_PROTOCOL = 'framelease_v4/PROTOCOL.md'
REGISTERED_SEAL = 'outputs/framelease_v4/registration/SEAL.sha256'
HEX64 = re.compile(r'^[0-9a-f]{64}$')


def sec13_text(text):
    """Sec. 13 of a protocol text: from its level-2 heading '## 13.' to the next level-2 heading."""
    m = re.search(r'^## 13\.', text, flags=re.M)
    if not m:
        return ''
    n = re.search(r'^## ', text[m.end():], flags=re.M)
    return text[m.start():m.end() + n.start()] if n else text[m.start():]


def seal_entry(seal, path):
    """The sha256 a seal file ('sha256  path' per line, paths relative to the project root) records for path."""
    if not os.path.isfile(seal):
        return None
    want = os.path.realpath(path)
    with open(seal, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.rstrip('\n').split('  ', 1)
            if len(parts) == 2 and os.path.realpath(resolve(parts[1].strip())) == want:
                return parts[0].strip().lower()
    return None


def _recorded_run_dir(entry):
    """The run directory a job entry of the record names, None when it names none (null or empty)."""
    rd = entry.get('run_dir') if isinstance(entry, dict) else None
    return rd if isinstance(rd, str) and rd.strip() else None


def _job_entry_ok(entry, files):
    """A job entry of the record: its job file is recorded, its outcome is final; outcome ok names its run directory,
    a failure (agent_crashed, sim_failure) names one or null (a final failure whose runner record names no run), a cut
    job may name none."""
    if not isinstance(entry, dict) or entry.get('job_file') not in files or entry.get('outcome') not in FREEZE_OUTCOMES:
        return False
    rd = entry.get('run_dir')
    if entry['outcome'] == 'ok':
        return _recorded_run_dir(entry) is not None
    return rd is None or _recorded_run_dir(entry) is not None


def check_freeze(path, protocol, seal, split):
    """(problems, summary, record) of an analysis-freeze record (Sec. 9.12; schema framelease_v4.analysis_freeze/1).
    path: the record, or a final_<stamp> directory holding analysis_freeze.json. Valid when the fields have the
    documented form (frozen; trigger all_final, or cut with its amendment; job_files {file: sha256}; jobs {job:
    {job_file, outcome, run_dir}}; analysis_code {path: sha256}; route_split_sha256), Sec. 13 of the protocol cites
    the record's sha256, the protocol equals the sha256 its seal records, the route split is the split file on disk
    and every analysis code file is on disk at its sha256."""
    if not path:
        return ['no --analysis-freeze given'], None, None
    if os.path.isdir(path):
        path = os.path.join(path, FREEZE_RECORD_NAME)
    if not os.path.isfile(path):
        return ['analysis-freeze record %s does not exist' % rel(path)], {'path': rel(path)}, None
    sha = sha256_file(path)
    summary = {'path': rel(path), 'sha256': sha, 'protocol': rel(protocol), 'seal': rel(seal), 'split': rel(split)}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            doc = json.load(f)
    except ValueError:
        return ['the record does not parse'], summary, None
    if not isinstance(doc, dict):
        return ['the record is not a JSON object'], summary, None
    problems = []
    if doc.get('schema') != FREEZE_SCHEMA:
        problems.append('schema %r is not %r' % (doc.get('schema'), FREEZE_SCHEMA))
    if not (isinstance(doc.get('frozen'), str) and doc['frozen'].strip()):
        problems.append('no freeze time (frozen)')
    if doc.get('trigger') not in FREEZE_TRIGGERS:
        problems.append('trigger %r is not one of %s' % (doc.get('trigger'), list(FREEZE_TRIGGERS)))
    elif doc['trigger'] == 'cut' and not (isinstance(doc.get('cut_amendment'), str) and doc['cut_amendment'].strip()):
        problems.append('trigger cut without its amendment (cut_amendment)')
    files = doc.get('job_files')
    if not (isinstance(files, dict) and files and all(isinstance(v, str) and HEX64.match(v) for v in files.values())):
        problems.append('job_files is not a non-empty {job file: sha256} mapping')
        files = {}
    jobs = doc.get('jobs')
    if not (isinstance(jobs, dict) and jobs):
        problems.append('jobs is not a non-empty mapping')
        jobs = {}
    bad = [j for j, v in jobs.items() if not _job_entry_ok(v, files)]
    if bad:
        problems.append('%d job entries without a recorded job file, a final outcome or (outcome ok) a run directory: '
                        '%s' % (len(bad), bad[:5]))
    if any(v.get('outcome') == 'cut' for v in jobs.values() if isinstance(v, dict)) and doc.get('trigger') != 'cut':
        problems.append('jobs with outcome cut under trigger %r' % doc.get('trigger'))
    code = doc.get('analysis_code')
    if not (isinstance(code, dict) and code):
        problems.append('analysis_code is not a non-empty {path: sha256} mapping')
        code = {}
    for cp, h in sorted(code.items()):
        fp = resolve(cp)
        if not (isinstance(h, str) and os.path.isfile(fp) and sha256_file(fp) == h):
            problems.append('analysis code %s is not on disk at the recorded sha256' % cp)
    if not os.path.isfile(split) or doc.get('route_split_sha256') != sha256_file(split):
        problems.append('route_split_sha256 is not the sha256 of %s' % rel(split))
    text = ''
    if os.path.isfile(protocol):
        with open(protocol, 'r', encoding='utf-8') as f:
            text = f.read()
    if sha not in sec13_text(text):
        problems.append('Sec. 13 of %s does not cite the record sha256 %s' % (rel(protocol), sha))
    sealed = seal_entry(seal, protocol)
    if sealed is None or not os.path.isfile(protocol) or sealed != sha256_file(protocol):
        problems.append('%s does not equal the sha256 its seal %s records' % (rel(protocol), rel(seal)))
    summary.update({'frozen': doc.get('frozen'), 'trigger': doc.get('trigger'), 'jobs': len(jobs)})
    return problems, summary, doc


def freeze_coverage(items, doc):
    """Problems of guarded inputs the record does not cover: a job outside the record, a job recorded as cut or without
    a run directory for which the input names one, and a run directory that is not the recorded run directory of its
    job (of any recorded job, for a run directory given without a job)."""
    jobs = doc.get('jobs') or {}
    recorded = {}
    for j, v in jobs.items():
        if _recorded_run_dir(v):
            recorded[os.path.realpath(resolve(_recorded_run_dir(v)))] = j
    problems = []
    for it in items:
        job, run_dir = it.get('job'), it.get('run_dir')
        where = '%s route %s' % (it['source'], it['route'])
        if job is not None:
            v = jobs.get(job)
            if not isinstance(v, dict):
                problems.append('%s: job %s is not in the record' % (where, job))
                continue
            if v.get('outcome') == 'cut':
                if run_dir:
                    problems.append('%s: job %s is recorded as cut but names a run directory' % (where, job))
                continue
            if _recorded_run_dir(v) is None:
                if run_dir:
                    problems.append('%s: job %s is recorded (%s) without a run directory but names one'
                                    % (where, job, v.get('outcome')))
                continue
            if run_dir and os.path.realpath(run_dir) != os.path.realpath(resolve(_recorded_run_dir(v))):
                problems.append('%s: run directory %s is not the recorded run of job %s' % (where, rel(run_dir), job))
        elif run_dir and os.path.realpath(run_dir) not in recorded:
            problems.append('%s: run directory %s is not a recorded run' % (where, rel(run_dir)))
    return problems


def route_flag(x):
    """A boolean flag of an input (test_route, training_route): True, False, or None when the input carries none."""
    s = '' if x is None or isinstance(x, (dict, list)) else str(x).strip().lower()
    if s in ('1', 'true', 'yes'):
        return True
    if s in ('0', 'false', 'no'):
        return False
    return None


def route_text(x):
    """A route id as text: a value that reads as an integral number in any form (1711, ' 1711 ', '1711.0', 1711.0) as
    that integer, any other text stripped; None for no id (None, empty, a container or a boolean)."""
    if x is None or isinstance(x, (bool, dict, list)):
        return None
    s = str(x).strip()
    if not s:
        return None
    try:
        return str(int(s))
    except ValueError:
        pass
    try:
        f = float(s)
    except ValueError:
        return s
    return str(int(f)) if math.isfinite(f) and f.is_integer() else s


def dropped_route_ids(text):
    """Route ids (route_text) of a dropped_routes cell ('route: reason | route: reason ...')."""
    return [r for r in (route_text(p.split(':', 1)[0]) for p in str(text or '').split('|')) if r is not None]


ROUTE_ID_KEYS = ('route_id', 'route')           # a route id
ROUTE_LIST_KEYS = ('routes', 'route_ids')       # a list of route ids or of objects with one (a number is a count)


def json_route_names(obj, found):
    """Append to found every route an analysis.json value names at any depth: the value of a ROUTE_ID_KEYS key (None for
    an entry without an id), the elements of a ROUTE_LIST_KEYS list (objects are searched in turn) and the ids of a
    dropped_routes text."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ROUTE_ID_KEYS and not isinstance(v, (dict, list)):
                found.append(route_text(v))
            elif k in ROUTE_LIST_KEYS and isinstance(v, list):
                found.extend(route_text(x) for x in v if not isinstance(x, dict))
            elif k == 'dropped_routes' and isinstance(v, str):
                found.extend(dropped_route_ids(v))
            json_route_names(v, found)
    elif isinstance(obj, list):
        for x in obj:
            json_route_names(x, found)


ANALYSIS_JSON_VALUE_SECTIONS = ('secondary', 'descriptive', 'families', 'per_ability', 'overhead', 'decisions',
                                'manipulation')


def analysis_route_names(analysis):
    """(source, route) of every route the analysis outputs other than cells.csv name (route None: an entry without an
    id): the route_id / route, routes ('|'-separated) and dropped_routes columns of the CSV files; in analysis.json the
    lists of route_table.subsets and of every cells condition, and json_route_names over the whole document."""
    found = []
    for name in ANALYSIS_FILES:
        rows = analysis.get(name)
        if not name.endswith('.csv') or name == 'cells.csv' or not rows:
            continue
        for r in rows:
            for col in ROUTE_ID_KEYS:
                if col in r:
                    found.append((name, route_text(r.get(col))))
            for x in str(r.get('routes') or '').split('|'):
                if x.strip():
                    found.append((name, route_text(x)))
            found.extend((name, x) for x in dropped_route_ids(r.get('dropped_routes')))
    aj = analysis.get('analysis.json')
    if isinstance(aj, dict):
        names = []
        subsets = (aj.get('route_table') or {}).get('subsets') if isinstance(aj.get('route_table'), dict) else None
        for lst in (subsets.values() if isinstance(subsets, dict) else []):
            names.extend(route_text(x.get('route_id')) if isinstance(x, dict) else route_text(x) for x in _list(lst))
        for cond in (aj.get('cells').values() if isinstance(aj.get('cells'), dict) else []):
            for lst in (cond.values() if isinstance(cond, dict) else []):
                names.extend(route_text(x) for x in _list(lst) if not isinstance(x, dict))
        json_route_names(aj, names)
        found.extend(('analysis.json', x) for x in names)
    return found


def analysis_has_values(analysis):
    """True when the analysis outputs carry a value row: a row of a CSV file other than cells.csv, or a non-empty
    compared section of analysis.json."""
    if any(analysis.get(n) for n in ANALYSIS_FILES if n.endswith('.csv') and n != 'cells.csv'):
        return True
    aj = analysis.get('analysis.json')
    return isinstance(aj, dict) and any(aj.get(k) for k in ANALYSIS_JSON_VALUE_SECTIONS)


def collect_routes(runner, runs_rows, run_dirs, analysis):
    """Every input that names a route, read from metadata only (no metric value): dicts with source, route (None when
    the input names none), flag (the input's own test-route flag: True, False or None), job and run_dir where the input
    names them. An analysis directory that carries values but names no route is one input without a route."""
    out = []

    def add(source, route, flag=None, job=None, run_dir=None):
        out.append({'source': source, 'route': route, 'flag': flag, 'job': job, 'run_dir': run_dir})
    for jid, rec in runner.items():
        training = route_flag(rec.get('training_route'))
        add('runner', route_text(rec.get('route_id')), None if training is None else not training, jid,
            rec.get('run_dir') if rec.get('final') else None)
    for r in runs_rows:
        add('runs.csv', route_text(r.get('route_id')), route_flag(r.get('test_route')), r.get('job'),
            runs_csv_run_dir(r))
    for d in run_dirs:
        try:
            meta = load_run_meta(d)
        except (OSError, ValueError):
            meta = {'route_id': None}
        add('run_dir', route_text(meta.get('route_id')), None, None, d)
    if analysis is not None:
        named = 0
        for r in analysis.get('cells.csv') or []:
            try:
                jobs = json.loads(r.get('jobs') or '[]')
            except ValueError:
                jobs = []
            route = route_text(r.get('route_id'))
            named += route is not None
            for j in (jobs if isinstance(jobs, list) and jobs else [None]):
                add('cells.csv', route, job=j)
        for source, route in analysis_route_names(analysis):
            named += route is not None
            add(source, route)
        if not named and analysis_has_values(analysis):
            add('analysis outputs', None)
    return out


def guard(items, registered_test, synthetic_test, freeze_path, dev):
    """Decision of the interim guard: (granted, status, record). Inputs naming a test route, and inputs without a route
    (route and flag None: fail closed), need a valid analysis-freeze record that covers them: a registered test route
    and an input without a route the registered PROTOCOL.md, seal and route split judge; a synthetic test route (test
    options) those of dev ('protocol', 'seal', 'split')."""
    reg = [i for i in items if i['route'] is not None and (
        i['route'] in registered_test or (i['flag'] is True and i['route'] not in synthetic_test))]
    unknown = [i for i in items if i['route'] is None and i['flag'] is not False]
    syn = [i for i in items if i['route'] is not None and i['route'] not in registered_test
           and i['route'] in synthetic_test]
    record = {'inputs_naming_a_route': len(items), 'registered_test_route_inputs': len(reg),
              'inputs_without_a_route': len(unknown), 'synthetic_test_route_inputs': len(syn), 'freeze': None,
              'problems': []}
    if not reg and not unknown and not syn:
        record['decision'] = 'granted'
        return True, 'development', record
    registered = (resolve(REGISTERED_PROTOCOL), resolve(REGISTERED_SEAL), resolve(REGISTERED_SPLIT))
    problems = []
    for label, group, (protocol, seal, split) in (
            ('registered test routes', reg, registered),
            ('inputs without a route', unknown, registered),
            ('synthetic test routes', syn, (dev.get('protocol') or registered[0], dev.get('seal') or registered[1],
                                            dev.get('split')))):
        if not group:
            continue
        p, summary, doc = check_freeze(freeze_path, protocol, seal, split)
        if doc is not None and not p:
            p = freeze_coverage(group, doc)
        problems += ['%s: %s' % (label, x) for x in p]
        record['freeze'] = record['freeze'] or summary
    record['problems'] = problems
    record['decision'] = 'refused' if problems else 'granted'
    if problems:
        return False, None, record
    return True, ('final' if reg or unknown else 'development'), record


def append_guard_log(out_dir, record):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'guard_log.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, sort_keys=True, default=_json_default) + '\n')


# ----------------------------------------------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------------------------------------------

def cause_view(run, cause):
    """The per-run values of run (recompute_run) with its Sec. 6.3 values under convention cause (registered_views);
    run itself when it has none."""
    views = run.get('registered_views')
    return dict(run, **views[cause]) if views else run


def compare_all(cmp, ctx, per_dir, per_job, variant=False):
    """Step 3 of run(): the comparisons with summary.json, runs.csv, the runner records, arm_summary.csv and the
    analysis outputs. cmp: a Comparisons, or with variant True a Recorder in a pass over the per-run values under a
    convention (the summary.json and runner comparisons, which no convention changes, are left out). Returns
    (unverified, cond_vals, cond_problems)."""
    runs_rows, runs_cols, runner = ctx['runs_rows'], ctx['runs_cols'], ctx['runner']
    runs_by_job, analysis, analysis_columns = ctx['runs_by_job'], ctx['analysis'], ctx['analysis_columns']
    used_dirs = ctx['used_dirs']
    if not variant:
        for d, ours in sorted(per_dir.items()):
            key = rel(d)
            if ours.get('problems'):
                if d in used_dirs:
                    cmp.compare('run logs', key, 'problems', json.dumps([]), json.dumps(ours['problems']),
                                kind='json_text', scope='analysis',
                                note='run directory of a row with analysis_use not recomputable')
                continue
            if os.path.isfile(os.path.join(d, LOG_DIR, 'summary.json')):
                compare_summary(cmp, key, ours, d)
            elif d in used_dirs:
                cmp.absent('summary.json', key, 'summary.json absent in the run directory of a row with analysis_use')
    unverified = []
    for r in runs_rows:
        job = r['job']
        ours = per_job.get(job)
        d = runs_csv_run_dir(r)
        used = truthy(r.get('analysis_use'))
        if used and (ours is None or ours.get('problems')):
            # A used row without recomputed raw logs: its values enter the analysis comparisons from runs.csv.
            if ctx['runs_csv_values']:
                unverified.append({'job': job, 'reason': 'runs.csv values (--runs-csv-values)'})
            elif d is None:
                unverified.append({'job': job, 'reason': 'no run directory named'})
            elif not os.path.isdir(d):
                unverified.append({'job': job, 'reason': 'run directory absent'})
                cmp.compare('run logs', job, 'run_dir', None, rel(d), kind='json_text', scope='analysis',
                            note='row with analysis_use names a run directory that does not exist')
            else:
                unverified.append({'job': job, 'reason': 'run directory not recomputable'})
        if ours is None or ours.get('problems'):
            continue
        note = '' if used else 'row not used by the analysis (analysis_use false)'
        compare_run(cmp, job, ours, r, runs_cols, analysis_columns=analysis_columns, note=note, used=used)
        cmp.compare('runs.csv', job, 'route_id', ours.get('route_id'), (r.get('route_id') or '').strip() or None,
                    their_field='route_id', kind='json_text', note=note, scope='analysis' if used else 'record')
    if not variant:
        for jid, rec in sorted(runner.items()):
            if not rec.get('final'):
                continue
            ours = per_job.get(jid)
            row = runs_by_job.get(jid)
            if row is not None or ctx['agg_dir']:
                a = os.path.realpath(rec['run_dir']) if rec.get('run_dir') else None
                b = runs_csv_run_dir(row) if row is not None else None
                b = os.path.realpath(b) if b else None
                cmp.compare('runner', jid, 'run_dir', a and rel(a), b and rel(b), their_field='runs.csv run_dir',
                            kind='json_text', note='' if row is not None else 'job absent in runs.csv')
            if ours is not None and not ours.get('problems') and rec.get('run_dir') \
                    and os.path.realpath(rec['run_dir']) == os.path.realpath(ours['run_dir']):
                compare_runner_result(cmp, jid, ours, rec)
    if ctx['arm_rows'] is not None:
        compare_arm_summary(cmp, ctx['arm_rows'], runs_rows, per_job)
    cond_vals, cond_problems = {}, []
    if analysis is not None:
        cond_vals, cond_problems = condition_values(analysis, per_job, runs_by_job, analysis_columns)
        for p in cond_problems:
            cmp.compare('cells.csv', p, 'jobs', 1, None, kind='json_text', note=p, scope='analysis')
        compare_analysis(cmp, analysis, cond_vals)
    return unverified, cond_vals, cond_problems


def parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--queue', action='append', default=[], help='runner record directory (status.jsonl); repeatable')
    ap.add_argument('--run-dir', action='append', default=[], help='run directory to recompute; repeatable')
    ap.add_argument('--agg', help='aggregator output directory (runs.csv, arm_summary.csv)')
    ap.add_argument('--analysis', help='analysis output directory (conditions.csv, cells.csv, ...)')
    ap.add_argument('--out', required=True, help='output directory')
    ap.add_argument('--analysis-freeze', help='analysis-freeze record (Sec. 9.12), or the final_<stamp> directory that '
                                              'holds it as analysis_freeze.json')
    ap.add_argument('--route-split', help='test option: synthetic route split whose test routes are guarded')
    ap.add_argument('--protocol',
                    help='test option: protocol copy that judges the record for the synthetic test routes')
    ap.add_argument('--seal', help='test option: seal file of that protocol copy')
    ap.add_argument('--write-plans', action='store_true',
                    help='development option: also write plans.csv (every committed plan: status, V, V_suf, H, miss)')
    ap.add_argument('--runs-csv-values', action='store_true',
                    help='development option (synthetic matrices without raw logs): the run directories runs.csv '
                         'names are not read; the analysis comparisons use the runs.csv values (refused under the '
                         'registered analysis-freeze record)')
    return ap.parse_args(argv)


def run(args):
    t_start = time.time()
    out_dir = resolve(args.out)
    if protected_out(out_dir):
        raise InputError('refusing to write into %s (a directory this script never writes)' % rel(out_dir))
    queues = [resolve(q) for q in args.queue]
    agg_dir = resolve(args.agg)
    analysis_dir = resolve(args.analysis)
    extra_dirs = [resolve(d) for d in args.run_dir]

    # 1. Metadata only: runner records, runs.csv rows, run directories, analysis cells; then the guard.
    runner = load_runner_records(queues)
    runs_rows, runs_cols = load_runs_csv(agg_dir) if agg_dir else ([], set())
    analysis = load_analysis(analysis_dir) if analysis_dir else None
    run_dirs = []
    named = [] if args.runs_csv_values else [runs_csv_run_dir(r) for r in runs_rows]
    for d in [rec['run_dir'] for rec in runner.values() if rec.get('final') and rec.get('run_dir')] + named + \
            extra_dirs:
        if d and os.path.isdir(d) and os.path.realpath(d) not in [os.path.realpath(x) for x in run_dirs]:
            run_dirs.append(d)
    for d in extra_dirs:
        if not os.path.isdir(d):
            raise InputError('run directory %s does not exist' % d)
    registered_test = load_test_routes(os.path.join(ROOT, REGISTERED_SPLIT))
    synthetic_test = load_test_routes(resolve(args.route_split)) if args.route_split else set()
    dev = {'protocol': resolve(args.protocol), 'seal': resolve(args.seal), 'split': resolve(args.route_split)}
    routes = collect_routes(runner, runs_rows, run_dirs, analysis)
    granted, status, grec = guard(routes, registered_test, synthetic_test, resolve(args.analysis_freeze), dev)
    if granted and status == 'final' and args.runs_csv_values:
        # A release under the registered record is the final verification: it recomputes every run directory.
        granted, status = False, None
        grec['decision'] = 'refused'
        grec['problems'].append('--runs-csv-values is a development option; the final verification (status final) '
                                'recomputes every run directory')
    grec.update({'schema': SCHEMA + '/guard', 'time': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'argv': sys.argv,
                 'test_options': {'route_split': args.route_split, 'protocol': args.protocol, 'seal': args.seal},
                 'runs_csv_values': bool(args.runs_csv_values)})
    append_guard_log(out_dir, grec)
    if not granted:
        print('verify_table1_extra REFUSED (Sec. 9.11): %d registered test-route inputs, %d inputs without a route and '
              '%d synthetic test-route inputs; nothing read; guard_log.jsonl in %s'
              % (grec['registered_test_route_inputs'], grec['inputs_without_a_route'],
                 grec['synthetic_test_route_inputs'], rel(out_dir)))
        for p in grec['problems']:
            print('  ' + p)
        return EXIT_REFUSED

    # 2. Recompute every run directory (in the order of their real paths). The plans of a run go to plans.csv
    # (--write-plans) as soon as it is recomputed and are not kept; the plans a convention changes are kept.
    plan_file = plan_writer = None
    if args.write_plans:
        plan_file = open(os.path.join(out_dir, 'plans.csv'), 'w', encoding='utf-8', newline='')
        plan_writer = csv.DictWriter(plan_file, fieldnames=PLAN_FIELDS, lineterminator='\n')
        plan_writer.writeheader()
    per_dir = {}
    cause_rows = []
    try:
        for d in sorted(run_dirs, key=os.path.realpath):
            real = os.path.realpath(d)
            try:
                r = recompute_run(d)
            except InputError as e:
                r = {k: None for k in RUN_FIELDS}
                r.update({'run_dir': d, 'checks': {}, 'problems': ['log does not parse: %s' % e]})
            plans = r.pop('_plans', None) or []
            cause_rows += [dict(v, run_dir=rel(real)) for v in r.pop('_cause_plans', None) or []]
            if plan_writer is not None:
                for k, v in enumerate(plans):
                    row = dict(v, run_dir=rel(real), commit_index=k)
                    plan_writer.writerow({f: _csv_cell(row.get(f)) for f in PLAN_FIELDS})
            per_dir[real] = r
    finally:
        if plan_file is not None:
            plan_file.close()
    runs_by_job = {r['job']: r for r in runs_rows}
    per_job = {}
    for r in runs_rows:
        d = runs_csv_run_dir(r)
        if d and os.path.realpath(d) in per_dir:
            per_job[r['job']] = per_dir[os.path.realpath(d)]
    for jid, rec in runner.items():
        if jid not in per_job and rec.get('final') and rec.get('run_dir') \
                and os.path.realpath(rec['run_dir']) in per_dir:
            per_job[jid] = per_dir[os.path.realpath(rec['run_dir'])]

    # 3. Comparisons: a pass over the per-run values under each convention of the registered implementation records
    # what each comparison would compare there (the causes); then the comparisons themselves.
    analysis_columns = dict(DEFAULT_ANALYSIS_COLUMNS)
    if analysis is not None:
        for row in analysis.get('conditions.csv') or []:
            if row.get('metric') in ANALYSIS_METRICS and row.get('statistic') == 'route_mean' and row.get('column'):
                analysis_columns[row['metric']] = row['column']
    used_dirs = set()
    for r in runs_rows:
        d = runs_csv_run_dir(r)
        if d and truthy(r.get('analysis_use')):
            used_dirs.add(os.path.realpath(d))
    arm_path = os.path.join(agg_dir, 'arm_summary.csv') if agg_dir else None
    ctx = {'runs_rows': runs_rows, 'runs_cols': runs_cols, 'runner': runner, 'runs_by_job': runs_by_job,
           'agg_dir': agg_dir, 'arm_rows': read_csv(arm_path) if arm_path and os.path.isfile(arm_path) else None,
           'analysis': analysis, 'analysis_columns': analysis_columns, 'used_dirs': used_dirs,
           'runs_csv_values': bool(args.runs_csv_values)}
    variants = {}
    for cause in CAUSES:
        view = {id(v): cause_view(v, cause) for v in per_dir.values()}
        recorder = Recorder()
        compare_all(recorder, ctx, {d: view[id(v)] for d, v in per_dir.items()},
                    {j: view[id(v)] for j, v in per_job.items()}, variant=True)
        variants[cause] = recorder.values
    cmp = Comparisons(variants)
    unverified, cond_vals, cond_problems = compare_all(cmp, ctx, per_dir, per_job)

    # 4. Outputs.
    summ = cmp.summary()
    verdict = 'AGREE' if summ['differences'] == 0 else 'DIFFER'
    os.makedirs(out_dir, exist_ok=True)
    runs_out = []
    for d, ours in sorted(per_dir.items()):
        row = dict(ours)
        row['run_dir'] = rel(d)
        row['jobs'] = sorted(j for j, v in per_job.items() if v is ours)
        runs_out.append(row)
    write_csv(os.path.join(out_dir, 'runs_recomputed.csv'), runs_out, ('jobs',) + RUN_FIELDS)
    write_csv(os.path.join(out_dir, 'differences.csv'), cmp.rows, DIFF_FIELDS)
    write_csv(os.path.join(out_dir, 'cause_plans.csv'), cause_rows, CAUSE_PLAN_FIELDS)
    out_files = ['cause_plans.csv', 'differences.csv', 'runs_recomputed.csv', 'table1_extra.json']
    if args.write_plans:
        out_files.append('plans.csv')
    sources = {}
    for v in cond_vals.values():
        for metric, (x, src, _, _) in v['vals'].items():
            sources[src] = sources.get(src, 0) + 1
    inputs = {}
    for q in queues:
        inputs[rel(os.path.join(q, 'status.jsonl'))] = sha256_file(os.path.join(q, 'status.jsonl'))
    if agg_dir:
        for name in ('runs.csv', 'arm_summary.csv'):
            p = os.path.join(agg_dir, name)
            if os.path.isfile(p):
                inputs[rel(p)] = sha256_file(p)
    if analysis_dir:
        for name in ANALYSIS_FILES:
            p = os.path.join(analysis_dir, name)
            if os.path.isfile(p):
                inputs[rel(p)] = sha256_file(p)
    checks_total = {}
    for ours in per_dir.values():
        for k, v in (ours.get('checks') or {}).items():
            checks_total[k] = checks_total.get(k, 0) + (v if isinstance(v, int) else 1)
    report = {
        'schema': SCHEMA, 'script': rel(os.path.abspath(__file__)), 'script_sha256': sha256_file(__file__),
        'created': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'status': status, 'verdict': verdict,
        'guard': grec, 'inputs': inputs, 'analysis_columns': analysis_columns,
        'options': {'runs_csv_values': bool(args.runs_csv_values), 'write_plans': bool(args.write_plans)},
        'runs': {'run_dirs': len(per_dir), 'recomputed': sum(1 for v in per_dir.values() if not v.get('problems')),
                 'not_recomputable': sorted(rel(d) for d, v in per_dir.items() if v.get('problems')),
                 'runner_jobs': len(runner), 'runs_csv_rows': len(runs_rows), 'jobs_matched': len(per_job),
                 'used_rows': sum(1 for r in runs_rows if truthy(r.get('analysis_use'))),
                 'used_rows_without_raw_logs': len(unverified),
                 'used_rows_without_raw_logs_by_reason': _count_by(unverified, 'reason'),
                 'used_rows_without_raw_logs_jobs': [u['job'] for u in unverified][:200],
                 'raw_data_checks': checks_total,
                 'f1_plans': sum(v.get('f1_plans') or 0 for v in per_dir.values()),
                 'runs_with_f1_plans': sum(1 for v in per_dir.values() if v.get('f1_plans')),
                 'f3_plans': sum(v.get('f3_plans') or 0 for v in per_dir.values()),
                 'runs_with_f3_plans': sum(1 for v in per_dir.values() if v.get('f3_plans'))},
        'analysis_cells': {'used_cells': len(cond_vals), 'value_sources': sources, 'problems': cond_problems},
        'comparisons': summ, 'tolerances': TOLERANCES, 'registered_grid': GRID,
        'causes': {'order': list(CAUSES), 'conventions': CAUSE_TEXT,
                   'rule': 'a difference whose other side agrees with the value formed under a convention of the '
                           'registered implementation (the first in this order; the same tolerances, bounds under '
                           'that convention) carries it as its cause and remains a difference'},
        'scope': {'verified': ['GPU usage', 'CUDA-s per s', 'DMR (from the first commit on; all-ticks and '
                               'expired-only variants)', 'action age p50 / p95', 'fallback ratio and episodes',
                               'P_both', 'EIR (executed-invalid tick rate, Sec. 6.3)',
                               'closed-loop R_cond (and without the V = 0 plans)',
                               'conflict plans, misses, V = 0 plans, log-censored plans, invalid ticks',
                               'the same Sec. 6.3 values under the conventions F1 and F3 of the registered '
                               'implementation (the cause of a difference)'],
                  'analysis_outputs_compared': [
                      'conditions.csv', 'secondary.csv', 'family_S-dmr.csv', 'descriptive.csv',
                      'paired_differences.csv', 'per_scenario.csv', 'per_ability.csv', 'analysis.json secondary',
                      'analysis.json descriptive', 'analysis.json families', 'analysis.json per_ability',
                      'analysis.json overhead',
                      'analysis.json decisions.H1.finding_2.gpu_usage_descriptive',
                      'analysis.json manipulation.analysed_runs.p_both_shared_shield'],
                  'not_verified_here': ['CIs and p-values of the contrasts of these metrics (S-dmr and the '
                                        'secondary rows)',
                                        'the ability membership of the per_ability rows (official mapping)',
                                        'closed-loop lease utilization and premature expiry (Sec. 6.3; not Table I '
                                        'columns)']},
        'definitions': __doc__.split('Definitions')[1].split('Comparisons (')[0].strip(),
        'elapsed_s': round(time.time() - t_start, 3),
    }
    dump_json(os.path.join(out_dir, 'table1_extra.json'), report)
    with open(os.path.join(out_dir, 'SHA256SUMS'), 'w', encoding='utf-8') as f:
        for name in sorted(out_files):
            f.write('%s  %s\n' % (sha256_file(os.path.join(out_dir, name)), name))
    print('verify_table1_extra %s (%s): %d run dirs (%d recomputed), %d runs.csv rows (%d used, %d of them without '
          'raw logs), %d used analysis cells; comparisons %d, differences %d (%d in values the analysis reads)%s'
          % (verdict, status, len(per_dir), report['runs']['recomputed'], len(runs_rows), report['runs']['used_rows'],
             len(unverified), len(cond_vals), summ['compared'], summ['differences'], summ['analysis_differences'],
             '; per-run values from runs.csv (--runs-csv-values)' if args.runs_csv_values else ''))
    for target, c in sorted(summ['by_target'].items()):
        print('  %-24s compared %6d  differences %5d  (analysis-read %d; agree within in-flight GPU bounds %d, '
              'within Sec. 6.3 bounds %d)'
              % (target, c['compared'], c['differences'], c['analysis_differences'],
                 c['agree_within_inflight_bounds'], c['agree_within_validity_bounds']))

    def by_cause(counts):
        return ', '.join('%s %d' % (k, counts[k]) for k in list(CAUSES) + [UNCLASSIFIED] if counts.get(k)) or 'none'
    print('  differences by cause: %s; in values the analysis reads: %s; agreements within bounds at the value under '
          'a convention: %s; plans changed by F1: %d in %d run directories, by F3: %d in %d run directories'
          % (by_cause(summ['differences_by_cause']), by_cause(summ['analysis_differences_by_cause']),
             by_cause(summ['agree_within_bounds_by_cause']), report['runs']['f1_plans'],
             report['runs']['runs_with_f1_plans'], report['runs']['f3_plans'], report['runs']['runs_with_f3_plans']))
    print('outputs: %s' % rel(out_dir))
    return EXIT_AGREE if verdict == 'AGREE' else EXIT_DIFFER


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return run(args)
    except InputError as e:
        print('verify_table1_extra: input error: %s' % e, file=sys.stderr)
        return EXIT_ERROR
    except Exception as e:  # any other failure is an error, never the DIFFER code
        print('verify_table1_extra: unexpected failure: %s: %s' % (type(e).__name__, e), file=sys.stderr)
        return EXIT_ERROR


if __name__ == '__main__':
    sys.exit(main())
