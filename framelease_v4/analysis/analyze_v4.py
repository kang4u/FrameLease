#!/usr/bin/env python3
"""Registered analysis of the v4 experiments (framelease_v4/PROTOCOL.md Secs. 7.2-7.6 and 9.1-9.13; GAP_AUDIT Sec. 3.7
row R-4; CPU only, reads the aggregator's and the offline ablation's outputs, writes only under --out).

  cd /home/kang/Desktop/DAC
  CUDA_VISIBLE_DEVICES= .conda-unidrive-linux/bin/python -I -B framelease_v4/analysis/analyze_v4.py \
      --agg DIR [--agg DIR ...] [--runs CSV ...] [--analysis-freeze RECORD [--required-job-files FILE]] \
      [--rl-freeze outputs/framelease_v4/rl_freeze/rl_freeze.json] [--offline outputs/framelease_v4/offline_ablation] \
      [--s3 outputs/framelease_v4/stress/<S3 report>.json] --out outputs/framelease_v4/analysis/final_<stamp> [--force]

Inputs:
  --agg DIR     an output directory of aggregate_v4.py: runs.csv (one row per job line: protocol_arm, kappa, seed,
                route_id, analysis_use, missing_reason, the Sec. 9.11 guard fields and the per-run metrics),
                aggregate.json (schema framelease_v4.aggregate/1: the sha256 of runs.csv and the interim-guard state)
                and SHA256SUMS; the three must agree
  --runs CSV    a bare per-run CSV with the runs.csv columns (synthetic development data, Sec. 9.12); never accepted
                with a test-route row
  --analysis-freeze  the analysis-freeze record (interim_guard.load_freeze: valid only when its sha256 is a dated Sec.
                13 entry of the sealed PROTOCOL.md); --required-job-files: {job file: sha256} of the registered tier 3-6
                job files the record must cover (as aggregate_v4.py)
  --rl-freeze   the RL freeze of p3_rl.py: the Sec. 5.8 P_both label that H2 carries (Sec. 9.13)
  --offline     the offline lease-ablation outputs (framelease_v4/offline/analyze.py; default the registered directory
                outputs/framelease_v4/offline_ablation): paired.csv and per_clip_selected.csv for H4 offline
  --s3          the S3 report of framelease_v4/protocol/stress_bench.py (schema framelease_v4.stress_bench/1) for H5

Interim looks (Sec. 9.11; GAP_AUDIT Sec. 1.5; interim_guard.py). A test-route row is a row on a route of the
registered split (route_split.json, its sha256 checked against the registration manifest), or a row the aggregator
flagged (test_route, or a guard_note). Any test-route row in the input is refused (exit 4, logged in
<out>/interim_guard.jsonl) unless all of these hold:
  * a VALID analysis-freeze record is given (interim_guard.load_freeze; a record cited only by a development copy of
    PROTOCOL.md never covers a route of the registered split: interim_guard.summary_rows refuses it);
  * the sha256 of this script is cited in Sec. 13 of the PROTOCOL.md that cites the record (Sec. 9.12: 'Their sha256
    is entered in Sec. 13 before the analysis freeze');
  * every input with a test-route row is an aggregation (not a bare CSV) made with that record (aggregate.json
    interim_guard.freeze.sha256);
  * every test-route row with analysis_use was released by the record (guard_note 'released: ...';
    interim_guard.summary_rows).
Without test-route rows (synthetic CSVs on synthetic route ids, training-route aggregations) no record is needed, and
the contrasts of the registered families simply find no test-route cell. The Python API (analyze) is no weaker: the
record is verified again from its files (aggregate_v4.checked_freeze), the code citation is always computed, and a
caller's test_routes / registered route sets only add routes to the registered split, never remove one.

Data used (Secs. 9.1, 9.8). A cell is (protocol arm, kappa, seed, route) on a route of the route table (default: the
44 registered test routes with the subsets of Sec. 3.1, E = index % 2 == 0, C = index % 4 == 0, R = index % 3 == 0).
A cell is used when exactly one row of it is in the guard's rows (interim_guard.summary_rows: the aggregator's
analysis_use, i.e. the final valid record whose code matches the pins, label agreed, not health-only) and that row
has valid_record = 1. Every other cell carries its status: no_row (no job line of the cell in the input), missing
(the aggregator's missing_reason), duplicate (more than one usable row), inconsistent (a usable row without a valid
record). Nothing is imputed.

Contrasts (Secs. 9.1, 9.8). A - B over the routes of the contrast's subset: d_r = m(A, r) - m(B, r) on the routes where
both cells are used (pairwise complete) and, per metric, where both values exist (the aggregator leaves only the
columns of a failed metric step empty, so a missing value drops the route from that metric only). The n of every row,
the routes dropped and why are reported.

Statistics (Sec. 9.1; sign_flip_test, bootstrap_ci, holm and label_directional of framelease_v2/analyze_closed_loop.py,
whose sha256 is checked against Sec. 12.2, imported unchanged):
  estimate     the mean paired difference A - B
  test         sign_flip_test: the exact two-sided sign-flip test; complete enumeration for n <= 22, for n > 22 (n = 44
               in the 44-route families) the exact distribution by dynamic programming over the differences rounded to
               the metric grid (0.01 for DS, RC, collisions/km and infractions/km; 1e-4 for fractions; 1 ms for ages),
               with the Monte Carlo cross-check of 200,000 sign vectors (seed 20261110: Sec. 9.1 names no seed for the
               cross-check, so the registered v4 seed is used; decisions use the exact p)
  intervals    bootstrap_ci: percentile bootstrap over routes, 10,000 resamples, a fresh numpy.random.default_rng(
               20261110) for every contrast and metric; 95% (90% also reported)
  Holm         holm within each family; a missing p counts as 1, so the family size is kept
  labels       label_directional(oriented mean, p) with p the family's Holm-adjusted p (the single test of H2: its p),
               the oriented mean A - B for a higher-is-better metric and B - A for a lower-is-better one; the v2 words
               map to the registered ones: supported -> 'improves', contradicted -> 'worse', inconclusive ->
               'inconclusive' (no difference was demonstrated, not evidence of equivalence), no data -> 'no data'

Families (Secs. 9.2, 9.3; FAMILIES):
  H1      primary    DS, fl_full - {fixed_deep, fast_only, age_only, event_triggered}, kappa 1.0, 44 routes, Holm over 4
  S-coll  secondary  collisions/km (lower is better), the four H1 contrasts, 44 routes, Holm over 4
  S-dmr   secondary  DMR from the first commit (Sec. 6.2; lower is better), the four H1 contrasts, Holm over 4
  H2      secondary  DS, fl_full - fl_heuristic, 44 routes, single test (key secondary)
  H3      secondary  DS, fl_heuristic - fl_original and fl_full - fl_original, 44 routes, Holm over 2 (key secondary)
  F3      secondary  DS, fl_full - fixed_deep and fl_full - fast_only at kappa 1.5 and 2.0, E (22), Holm over 4
  H4-cl   secondary  DS, fl_heuristic - fl_global_shield and fl_heuristic - age_only, kappa 1.0, E, Holm over 2
  RL-abl  secondary  DS, fl_full - fl_bandit and fl_full - fl_fqi_nolease, kappa 1.0, E, Holm over 2
  Every test at seed 11. Decisions: H1 finding 1 (contrasts 1 and 2) and finding 2 (contrasts 3 and 4, shown with the
  descriptive GPU-usage contrasts) may be stated only if both of their contrasts are 'improves'; differing labels are
  'mixed' (Sec. 9.2). The RL benefit is claimed only if H2 is 'improves'; with P_both < 0.05 in the kappa-1.0 episodes
  of the RL dataset (the RL freeze's Sec. 5.8 label) H2 carries the label 'not testable at this operating point'
  (Sec. 9.13).

Secondary rows (Sec. 9.3, 'every other paired quantity is secondary or descriptive, uncorrected and labelled'): for
every contrast of the families, every metric of SECONDARY_METRICS (plus the lease metrics for H4-cl and the scheduler
metrics for RL-abl) that is not a family metric of that contrast: SR (sign-flip test on the success indicator), RC,
infractions/km, GPU usage, action age p50 / p95, fallback ratio, EIR, closed-loop R_cond, P_both, and DS,
collisions/km and DMR where no family tests them. Uncorrected (p_adjusted = p). A metric with a better direction is
labelled with the uncorrected p (role 'secondary'); GPU usage, action ages, P_both and the scheduler rates have no
registered direction and are labelled 'descriptive' (FrameLease does not minimize action age, Sec. 7.3).

Descriptive contrasts (DESCRIPTIVE_CONTRASTS; the statistics of Sec. 9.1 with the uncorrected p for information,
never a decision label):
  noise floor   (Sec. 9.6) fixed_deep, fast_only, fl_heuristic, fl_full: seed 11 - seed 12 on R (15 routes); the mean
                |DS(s11) - DS(s12)| with its 95% bootstrap interval (bootstrap_ci on |d|), median, max, Pearson r
  seed 12       (Sec. 9.6) fl_full - fixed_deep, - fast_only, - fl_heuristic at seed 12 on R, next to the same
                contrasts at seed 11 on R (same sign of the mean; whether the seed-12 CI contains the seed-11 mean)
  RL gain       (Sec. 7.5) fl_full - fl_heuristic: the 44-route H2 row; by GPU budget, kappa 1.0, 1.5 and 2.0 on E; by
                seed, seed 11 and seed 12 on R; by Bench2Drive ability (below)
  F3 at 1.0     fl_full - fixed_deep and - fast_only at kappa 1.0 on E: the kappa-1.0 points of Fig. 3 (Sec. 7.3)
  depth         fixed_deep - fast_only at kappa 1.0 (44 routes) and 1.5 / 2.0 (E): Fig. 1 panel b (GAP_AUDIT R-6)
  fl_risk       fl_risk - fl_heuristic on E: DS, EIR, closed-loop R_cond (Secs. 4.3, 9.13; runs only if L* = B0)
Per scenario and per ability (Sec. 9.9; descriptive, no per-scenario test). Abilities: the official Bench2Drive
multi-label map (framelease_v4/offline/fig1_data.ability_map, sha256 pinned there); a route counts in each of its
abilities. per_ability.csv: every family row and every descriptive row grouped by ability and 'all' (n, mean, both
means, signs, the 95% bootstrap interval for at least 5 routes, as fig1_data). per_scenario.csv: one row per route
(one route per scenario type) and condition with the metric values. conditions.csv: per condition and subset the mean
of every Table I column and of the closed-loop Table II-A columns (lease utilization, premature expiry, deviation and
bypass rates) over routes with its 95% route-bootstrap interval (Table I, Fig. 3, Table II-A; statistic 'route_mean').
Collisions/km has two rows (Sec. 6.1): the route mean ('collisions_per_km', the route-level values the paired
contrasts use) and the arm-level value 'collisions_per_km_pooled' (statistic 'pooled_ratio'): sum of collisions_total
/ sum of km_driven with the 0.001 km floor per route, with its 95% route-cluster percentile bootstrap interval (routes
resampled, the ratio of sums per resample; 10,000 resamples, a fresh default_rng(20261110), the draws of bootstrap_ci)
and both sums; analysis.json lists the pooled rows under collisions_per_km_pooled.

Sensitivity (Sec. 9.10): the registered MDE table recomputed from SD 31 (two-sided normal approximation, 80% power),
and per family contrast the planned (SD 31, DS families) and observed (its SD of paired differences) MDE at the first
(alpha / m) and the last (alpha) Holm step; a contrast that is neither 'improves' nor 'worse' states that no
difference larger than its MDE was detected, which is not evidence of no effect.

H4 offline (Sec. 9.4; the offline code never applies the rule). Quantity: SUFFIX - GLOBAL under nested
leave-one-clip-out selection at R_cond <= 5%, need 0.964 s, all plans, paired by clip, 2000 clip-bootstrap resamples
(seed 20261109), read from paired.csv. 'supported' if the 95% CI of the continuity difference lies above 0 and the 95%
CI of the realized-R_cond difference contains 0 or lies below 0; 'contradicted' if the continuity CI lies below 0;
'inconclusive' otherwise. Secondary rows, same rule: R_cond <= 10%, SUFFIX - AGE, utilization and premature refresh
(oriented so that positive is better: B - A for premature refresh), 12 rows in all. A quantity paired.csv lacks is
recomputed from per_clip_selected.csv with the same bootstrap (offline/analyze.py boot_weights and ci) when it lies in
that file's scope: per_clip_selected.csv holds the TRAIN-selected candidates only (subset all, alpha 0.05, AGE /
GLOBAL / SUFFIX; utilization cannot be pooled from it), so a nested quantity can come only from paired.csv; every
in-scope paired.csv row is recomputed as a check (per_clip_check). The label carries the status 'pre-specified in
code, executed before registration' (Sec. 11.1 item 5).

H5 (Sec. 9.5). 'supported' if the commit audit (the aggregator's R-2 document of every aggregation) finds 0 commits
violating Eq. 9 in every run of every phase with closed-loop runs (P1-0, P1, P2, P4, P5, P6) and the registered S3
(--s3: a registered stress_bench report, >= 100,000 sequences, gate and runtime targets) finds 0 violations;
'contradicted' otherwise, with every violating run listed; a run the audit could not check leaves condition 1 unmet
(status ERROR; status NO_LOG, neither jobs.jsonl nor events.jsonl, when the runs.csv row that selects the run records
commits or no row tells its commits: an earlier attempt, a run matching no job; a NO_LOG run with 0 recorded commits
had nothing to audit). Every NO_LOG run is listed. 'undetermined' (not a registered label; a run with it is
'development') marks incomplete evidence: an input without the audit, runs withheld by the interim-look guard, a
phase not covered, no registered S3 report. The overhead quantities are reported as measured per condition: the
Q-network p99 against B_pi = 100 us and the log quantities of Sec. 7.6 panel B (Q-network p50, shield decision and
lease p50 / p99, bypass count and rate, prefix and flow-step quanta p50 / p99, switching latency p50 / p99,
cancelled-GPU share, validation p50 / p99, commit-gate rejects by reason, fallback episodes, budget overruns, shield
violations, DMR) as distributions of the per-run values; Table II-B itself, with S1-S4, is rendered by the figures and
tables script (GAP_AUDIT R-6).

Manipulation checks (Sec. 9.7, reported, not tested; Amendment A8): the aggregator's R-3 document of every aggregation,
manipulation.manipulation_summary over the runs this analysis uses, and per condition the fast-prefix,
charged-prefix, background-load and configuration counts and the predicted-expiry flags. No run is excluded.

Missing data (Sec. 9.8): every row reports n_expected, n_complete and n and lists its dropped routes with the reason;
analysis.json missing_data counts them per row, with the aggregator's missing-reason counts.

Outputs (--out; Sec. 9.12: outputs/framelease_v4/analysis/final_<stamp>/ with a sha256 manifest; the aggregation of the
analysis freeze occupies final_<stamp>/ itself with its own SHA256SUMS, so the analysis goes into a directory inside
it, e.g. final_<stamp>/analysis/; a directory holding an aggregation (aggregate.json) is refused, even with --force):
  analysis.json               everything below plus provenance (the sha256 of every input, of this script and of the
                              v2 module), settings, the guard state, the cells, the replicates, the RL gain, the
                              sensitivity, the pooled collisions/km, H4 offline, H5, the overhead, the manipulation
                              checks, the missing data and the decisions
  family_<name>.csv           one per family: its contrasts with n, mean, CIs, p, the Holm-adjusted p and the label
  secondary.csv               the uncorrected secondary and descriptive rows
  descriptive.csv             the descriptive contrasts (noise floor columns for the seed-to-seed rows)
  paired_differences.csv      one row per contrast x metric x route of the subset (values, difference or drop reason)
  cells.csv                   one row per (arm, kappa, seed, route) cell the contrasts need: status, job, reason
  per_ability.csv, per_scenario.csv, conditions.csv   Sec. 9.9 and the per-condition columns (above)
  h4_offline.csv              the 12 H4 offline rows with their labels
  SHA256SUMS                  the sha256 of every file above
  interim_guard.jsonl         the guard log (append-only; every request, granted or refused; not in SHA256SUMS)

Development data (Sec. 9.12: 'written and tested on synthetic CSVs only'): the unit tests use synthetic rows only, on
synthetic route ids (and on registered route ids only where they show that the guard refuses them or that training
routes find no test-route cell); the builder also ran it read-only on an aggregation of P1 training-route runs, which
has no test-route row (GAP_AUDIT Sec. 1.5). No test-route result was read. analysis.json is 'registered' only for a run
with the registered route table and settings, aggregations as the only inputs, a registered analysis-freeze record
checked against the registered tier 3-6 job files (--required-job-files), the RL freeze with a decisive P_both label
(the H2 RL benefit is determined), the registered offline outputs, the registered S3 run, a determined H5 label and
the Sec. 9.12 output location; every other run is 'development' and lists why (development_reasons).

Deviations from PROTOCOL.md, to be recorded in the Sec. 13 entry of this script (the PROTOCOL wins):
  * development data: besides synthetic CSVs, the builder ran the script read-only on an aggregation of P1
    training-route runs (outputs/framelease_v4/build/AGG/smoke_D), against Sec. 9.12's 'written and tested on
    synthetic CSVs only' (GAP_AUDIT Sec. 1.5 allows development on training-route runs); it has no test-route row;
  * the seed of the Monte Carlo cross-check of the sign-flip test: Sec. 9.1 names none, the registered v4 seed
    20261110 is used (decisions use the exact p);
  * the H5 label 'undetermined': Sec. 9.5 has only supported / contradicted; 'undetermined' marks incomplete evidence
    and makes the run 'development', never 'registered';
  * H4 offline secondary rows: Sec. 9.4 lists 'the same comparison at 10%; SUFFIX - AGE; utilization and premature
    refresh'; the script reports the full crossing (2 comparisons x 2 risk levels x 3 quantities: 1 primary and 11
    secondary rows), of which 7 combine two or more of these variations (SUFFIX - GLOBAL at 10% for utilization and
    premature refresh; SUFFIX - AGE at 5% for utilization and premature refresh; SUFFIX - AGE at 10% for continuity,
    utilization and premature refresh), rows the Sec. 9.4 list does not name explicitly; each is secondary and
    uses the same rule.

Exit codes: 0 written, 1 refused (out directory exists without --force, holds an aggregation, protected path), 2
inconsistent inputs, 4 refused by the interim-look guard (logged).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from framelease_v2 import analyze_closed_loop as V2  # noqa: E402
from framelease_v4.analysis import aggregate_v4 as A  # noqa: E402
from framelease_v4.analysis import interim_guard as G  # noqa: E402
from framelease_v4.analysis import manipulation as MC  # noqa: E402
from framelease_v4.offline import analyze as OA  # noqa: E402
from framelease_v4.offline import common as OC  # noqa: E402
from framelease_v4.offline import fig1_data as F1  # noqa: E402
from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402

SCHEMA = 'framelease_v4.analyze/1'
THIS_REL = 'framelease_v4/analysis/analyze_v4.py'
V2_REL = 'framelease_v2/analyze_closed_loop.py'
V2_SHA256 = '5478c9f9cfb327c87361bf3f7832d3b6315be622414345f40fba82bd8093cc84'   # PROTOCOL Secs. 9.1 and 12.2
RL_FREEZE_SCHEMA = A.RL_FREEZE_SCHEMA                                              # p3_rl.py FREEZE_SCHEMA
P_BOTH_NOT_TESTABLE = 'not testable at this operating point'                       # Sec. 5.8 (p3_rl.p_both_summary)

# the registered statistics (Sec. 9.1); the v2 functions are called with these values
sign_flip_test, bootstrap_ci = V2.sign_flip_test, V2.bootstrap_ci
holm, label_directional = V2.holm, V2.label_directional
ALPHA = 0.05
N_BOOT = 10_000
BOOT_SEED = 20261110
MC_FLIPS = 200_000
MC_SEED = 20261110            # the Monte Carlo cross-check (Sec. 9.1 names no seed; the registered v4 seed)
ENUM_MAX_N = 22               # complete enumeration up to n = 22, exact DP above (v2 ENUM_MAX_N)
# the v2 label words -> the registered v4 labels (Sec. 9.1)
LABELS = {'supported': 'improves', 'contradicted': 'worse', 'inconclusive': 'inconclusive', 'no data': 'no data'}
DESCRIPTIVE = 'descriptive'

# the metric grids of the exact DP (Sec. 9.1)
GRID_POINTS, GRID_FRACTION, GRID_SECONDS = 0.01, 1e-4, 1e-3
SUBSET_RULES = {'all': 'every test route (44)', 'E': 'index % 2 == 0 (22)', 'C': 'index % 4 == 0 (11)',
                'R': 'index % 3 == 0 (15)'}
SUBSET_TEST = {'all': lambda i: True, 'E': lambda i: i % 2 == 0, 'C': lambda i: i % 4 == 0, 'R': lambda i: i % 3 == 0}
N_TEST_ROUTES = 44


class AnalysisError(RuntimeError):
    """Inconsistent inputs (aggregation files, columns, route table, the v2 module, the RL freeze): nothing is
    written."""


GuardRefused = G.GuardRefused        # a request the Sec. 9.11 guard refuses (interim_guard.py): exit 4, logged


# ===================================================================================== metrics, contrasts, families

@dataclass(frozen=True)
class Metric:
    key: str            # the name in the outputs
    column: str         # the runs.csv column (aggregate_v4: metrics_v4.run_metrics + extra_metrics)
    label: str
    unit: str
    grid: float         # DP rounding grid for n > 22 (Sec. 9.1)
    better: str | None  # 'higher' / 'lower' (the hypothesized direction of A - B), None: descriptive (no direction)


METRICS = {m.key: m for m in (
    Metric('driving_score', 'driving_score', 'Driving score (DS)', 'points (0-100)', GRID_POINTS, 'higher'),
    Metric('collisions_per_km', 'collisions_per_km', 'Collisions per km', 'collisions/km', GRID_POINTS, 'lower'),
    Metric('dmr', 'dmr', 'Deadline miss rate from the first commit (DMR, Sec. 6.2)', 'fraction of ticks',
           GRID_FRACTION, 'lower'),
    Metric('success', 'success', 'Success (SR; Bench2Drive definition)', 'indicator (0/1)', GRID_FRACTION, 'higher'),
    Metric('route_completion', 'route_completion', 'Route completion (RC)', 'points (0-100)', GRID_POINTS, 'higher'),
    Metric('infractions_per_km', 'infractions_per_km', 'Infractions per km (Sec. 6.1)', 'infractions/km', GRID_POINTS,
           'lower'),
    Metric('gpu_usage', 'gpu_usage', 'GPU usage', 'GPU-busy s per s', GRID_FRACTION, None),
    Metric('action_age_p50_s', 'action_age_p50_s', 'Action age p50', 's', GRID_SECONDS, None),
    Metric('action_age_p95_s', 'action_age_p95_s', 'Action age p95', 's', GRID_SECONDS, None),
    Metric('fallback_ratio', 'deadline_miss_ratio', 'Fallback ratio (all control ticks; metrics_v4 '
           'deadline_miss_ratio)', 'fraction of ticks', GRID_FRACTION, 'lower'),
    Metric('eir', 'realized_invalid_tick_ratio', 'Executed-invalid tick rate (EIR, standard validity)',
           'fraction of tracked ticks', GRID_FRACTION, 'lower'),
    Metric('r_cond', 'realized_r_cond', 'Closed-loop R_cond (standard validity)', 'fraction of conflict plans',
           GRID_FRACTION, 'lower'),
    Metric('p_both', 'p_both', 'P_both', 'fraction of shield decision epochs', GRID_FRACTION, None),
    Metric('lease_utilization', 'lease_utilization', 'Closed-loop lease utilization (Sec. 6.3)', 'fraction',
           GRID_FRACTION, 'higher'),
    Metric('premature_expiry_ratio', 'premature_expiry_ratio', 'Premature expiry (Sec. 6.3)',
           'fraction of committed plans', GRID_FRACTION, 'lower'),
    Metric('deviation_rate', 'deviation_rate', 'Deviation rate from a_det^{d*} (Sec. 6.4)', 'fraction of choice epochs',
           GRID_FRACTION, None),
    Metric('bypass_rate', 'bypass_rate', 'Q-network bypass rate (Sec. 6.4)', 'fraction of choice epochs',
           GRID_FRACTION, None),
)}
# Sec. 9.3: the paired quantities of every Table I contrast (and of every other family contrast), uncorrected
SECONDARY_METRICS = ('driving_score', 'success', 'route_completion', 'collisions_per_km', 'infractions_per_km', 'dmr',
                     'gpu_usage', 'action_age_p50_s', 'action_age_p95_s', 'fallback_ratio', 'eir', 'r_cond', 'p_both')
# the further closed-loop columns of Table II-A (Sec. 7.4 lease panel; Sec. 7.5 RL panel)
FAMILY_EXTRA_METRICS = {'H4-cl': ('lease_utilization', 'premature_expiry_ratio'),
                        'RL-abl': ('deviation_rate', 'bypass_rate')}


@dataclass(frozen=True)
class Cond:
    arm: str            # protocol arm (aggregate_v4 protocol_arm)
    kappa: float
    seed: int = 11

    @property
    def name(self):
        return f'{self.arm}_k{self.kappa:.1f}_s{self.seed}'


@dataclass(frozen=True)
class Contrast:
    a: Cond
    b: Cond
    subset: str         # 'all' (44), 'E' (22), 'C' (11), 'R' (15)

    @property
    def cid(self):
        k = f'k{self.a.kappa:.1f}' if self.a.kappa == self.b.kappa else f'k{self.a.kappa:.1f}-{self.b.kappa:.1f}'
        s = f's{self.a.seed}' if self.a.seed == self.b.seed else f's{self.a.seed}-{self.b.seed}'
        return f'{self.a.arm}_minus_{self.b.arm}_{k}_{s}_{self.subset}'

    @property
    def label(self):
        return f'{self.a.arm} - {self.b.arm}'


@dataclass(frozen=True)
class Family:
    name: str
    role: str           # 'primary' (H1) or 'secondary' (Sec. 9.3: labelled secondary)
    metric: str         # METRICS key
    contrasts: tuple
    section: str
    question: str


def _c(a, b, kappa=1.0, subset='all'):
    return Contrast(Cond(a, kappa), Cond(b, kappa), subset)


H1_OTHERS = ('fixed_deep', 'fast_only', 'age_only', 'event_triggered')     # Sec. 9.2, contrasts 1-4 in this order
H1_CONTRASTS = tuple(_c('fl_full', b) for b in H1_OTHERS)
FAMILIES = (
    Family('H1', 'primary', 'driving_score', H1_CONTRASTS, '9.2',
           'Full FrameLease achieves a higher DS than each of Fixed Deep, Fast Only, Age-Only and Event-Triggered at '
           'kappa 1.0 on the 44 test routes (Holm over 4)'),
    Family('S-coll', 'secondary', 'collisions_per_km', H1_CONTRASTS, '9.3',
           'collisions/km for the four H1 contrasts, lower is better (Holm over 4)'),
    Family('S-dmr', 'secondary', 'dmr', H1_CONTRASTS, '9.3',
           'DMR for the four H1 contrasts, lower is better (Holm over 4)'),
    Family('H2', 'secondary', 'driving_score', (_c('fl_full', 'fl_heuristic'),), '9.3',
           'key secondary: Full FrameLease achieves a higher DS than FrameLease + Heuristic (single test)'),
    Family('H3', 'secondary', 'driving_score', (_c('fl_heuristic', 'fl_original'), _c('fl_full', 'fl_original')),
           '9.3', 'key secondary: FrameLease + Heuristic and Full FrameLease achieve a higher DS than Original '
                  'FrameLease (Holm over 2)'),
    Family('F3', 'secondary', 'driving_score',
           tuple(_c('fl_full', b, k, 'E') for k in (1.5, 2.0) for b in ('fixed_deep', 'fast_only')), '9.3',
           'DS, Full FrameLease - Fixed Deep and Full FrameLease - Fast Only at kappa 1.5 and 2.0 on E (Holm over 4)'),
    Family('H4-cl', 'secondary', 'driving_score',
           (_c('fl_heuristic', 'fl_global_shield', 1.0, 'E'), _c('fl_heuristic', 'age_only', 1.0, 'E')), '9.3',
           'DS, FrameLease + Heuristic - Global-Margin lease and - Age-Only on E (Holm over 2)'),
    Family('RL-abl', 'secondary', 'driving_score',
           (_c('fl_full', 'fl_bandit', 1.0, 'E'), _c('fl_full', 'fl_fqi_nolease', 1.0, 'E')), '9.3',
           'DS, Full FrameLease - Shield + Contextual Bandit and - FQI without lease features on E (Holm over 2)'),
)
FAMILY_BY_NAME = {f.name: f for f in FAMILIES}
PROTOCOL_ARMS = ('fixed_deep', 'fast_only', 'age_only', 'event_triggered', 'fl_original', 'fl_heuristic', 'fl_full',
                 'fl_global_shield', 'fl_bandit', 'fl_fqi_nolease', 'fl_risk')     # Sec. 4.1 (fl_behaviour: training)


@dataclass(frozen=True)
class Descriptive:
    group: str          # DESCRIPTIVE_GROUPS key
    contrast: Contrast
    metrics: tuple      # METRICS keys
    section: str


# the descriptive contrasts (uncorrected, never a decision label; Secs. 7.5, 9.4-9.9)
REPLICATE_ARMS = ('fixed_deep', 'fast_only', 'fl_heuristic', 'fl_full')     # Sec. 9.6: the seed-12 replicates on R
SEED12_OTHERS = ('fixed_deep', 'fast_only', 'fl_heuristic')                 # fl_full - each: the family contrasts
DESCRIPTIVE_GROUPS = {
    'noise_floor': 'one arm, seed 11 - seed 12 on R: the per-arm seed-to-seed |DS(s11) - DS(s12)| is the noise floor '
                   '(Sec. 9.6)',
    'seed12': 'a family contrast among the replicated arms at seed 12 on R (Sec. 9.6, descriptive)',
    'seed11_on_R': 'the same contrast at seed 11 restricted to R, the like-for-like counterpart of seed 12',
    'rl_gain_kappa': 'the RL gain fl_full - fl_heuristic on E at kappa 1.0, 1.5 and 2.0 (Sec. 7.5, by GPU budget)',
    'f3_kappa_1.0': 'the F3 contrasts at kappa 1.0 restricted to E: the kappa-1.0 points of Fig. 3 are the Table I '
                    'runs on E (Sec. 7.3; F3 tests kappa 1.5 and 2.0)',
    'depth': 'Fixed Deep - Fast Only (the depth contrast of Fig. 1 panel b, GAP_AUDIT R-6; Sec. 7.1)',
    'fl_risk': 'the fl_risk sensitivity against the selected lease point, on E (Secs. 4.3, 9.13; only if L* = B0)',
}


def _d(group, a, b, kappa=1.0, subset='all', seed=11, metrics=('driving_score',), section='9.6'):
    return Descriptive(group, Contrast(Cond(a, kappa, seed), Cond(b, kappa, seed), subset), tuple(metrics), section)


DESCRIPTIVE_CONTRASTS = (
    *(Descriptive('noise_floor', Contrast(Cond(arm, 1.0, 11), Cond(arm, 1.0, 12), 'R'), ('driving_score',), '9.6')
      for arm in REPLICATE_ARMS),
    *(_d('seed12', 'fl_full', b, subset='R', seed=12) for b in SEED12_OTHERS),
    *(_d('seed11_on_R', 'fl_full', b, subset='R') for b in SEED12_OTHERS),
    *(_d('rl_gain_kappa', 'fl_full', 'fl_heuristic', k, 'E', section='7.5') for k in (1.0, 1.5, 2.0)),
    *(_d('f3_kappa_1.0', 'fl_full', b, subset='E', section='7.3') for b in ('fixed_deep', 'fast_only')),
    _d('depth', 'fixed_deep', 'fast_only', section='7.1'),
    *(_d('depth', 'fixed_deep', 'fast_only', k, 'E', section='7.1') for k in (1.5, 2.0)),
    _d('fl_risk', 'fl_risk', 'fl_heuristic', subset='E', metrics=('driving_score', 'eir', 'r_cond'), section='4.3'),
)
RL_GAIN = _c('fl_full', 'fl_heuristic')            # the RL gain (Sec. 7.5) on the 44 routes: the H2 contrast
ABILITIES = F1.ABILITIES                           # Bench2Drive abilities (official multi-label map, Sec. 9.9)
ABILITY_MIN_CI_N = 5                               # no interval for fewer than 5 routes (as fig1_data.closed_loop)

# Sec. 9.4 (H4 offline): the outputs of framelease_v4/offline/analyze.py, which never applies the rule itself
OFFLINE_REL = 'outputs/framelease_v4/offline_ablation'
OFFLINE_FILES = ('paired.csv', 'per_clip_selected.csv')
H4_PROTOCOL, H4_SUBSET, H4_NEED, H4_RISK = 'nested', 'all', 'fast', 'R_cond'     # nested LOCO, all plans, 0.964 s
H4_PRIMARY = ('SUFFIX', 'GLOBAL', 0.05, 'continuity')
H4_COMPARISONS = (('SUFFIX', 'GLOBAL'), ('SUFFIX', 'AGE'))
H4_ALPHAS = (0.05, 0.10)
H4_QUANTITIES = {'continuity': 'higher', 'utilization': 'higher', 'premature_refresh': 'lower'}
H4_PRE_REGISTRATION = ('pre-specified in code, executed before registration (PROTOCOL Sec. 11.1 item 5: the offline '
                       'analysis ran on 2026-11-10, before the registration; the Sec. 9.4 rule is applied here)')
# per_clip_selected.csv holds the TRAIN-selected candidates (offline/analyze.py: subset all, PRIMARY_ALPHA, AGE /
# GLOBAL / SUFFIX); a pooled metric is rebuilt from its per-clip columns as (numerator, denominator) per clip
PER_CLIP_SCOPE = {'protocol': 'train', 'subset': 'all', 'alpha': OC.PRIMARY_ALPHA, 'designs': ('AGE', 'GLOBAL',
                                                                                                'SUFFIX')}
PER_CLIP_METRICS = ('continuity', 'R_cond', 'R_marg', 'premature_refresh', 'mean_H_s')   # utilization: no npos column
OFFLINE_TOL = 1e-5             # paired.csv and per_clip_selected.csv carry 6 significant digits (offline common._fmt)

# Sec. 9.5 (H5) and Sec. 7.6 (Table II-B overhead)
H5_PHASES = ('P1-0', 'P1', 'P2', 'P4', 'P5', 'P6')          # the phases with closed-loop runs (Sec. 10.1)
S3_SCHEMA = 'framelease_v4.stress_bench/1'                  # framelease_v4/protocol/stress_bench.py SCHEMA
S3_MIN_SEQUENCES = 100_000                                  # Sec. 7.6 S3 (stress_bench.S3_MIN_SEQUENCES)
S3_TARGETS = ('gate', 'runtime')
B_PI_S = 100e-6                                             # Sec. 5.7: the policy budget B_pi = 100 us

# Sec. 9.10 (minimum detectable effects, 80% power, two-sided, normal approximation)
MDE_POWER = 0.80
MDE_SD_DS = 31.0              # 'an SD of paired route differences of about 31 points' (v2 half-width 9.2 at n = 44)
MDE_REGISTERED = (('H1, first Holm step', 44, 0.0125, 15.6), ('H1, last Holm step', 44, 0.05, 13.1),
                  ('families on E', 22, 0.025, 20.0), ('families on E', 22, 0.05, 18.5))


@dataclass(frozen=True)
class Settings:
    n_boot: int = N_BOOT
    boot_seed: int = BOOT_SEED
    mc_flips: int = MC_FLIPS
    mc_seed: int = MC_SEED

    @property
    def registered(self):
        return self == REGISTERED


REGISTERED = Settings()


def family_contrasts():
    """The distinct contrasts of the families in FAMILIES order, each with the families (and metrics) that test it."""
    out = {}
    for f in FAMILIES:
        for c in f.contrasts:
            out.setdefault(c, []).append((f.name, f.metric))
    return out


# ============================================================================================ inputs

def check_v2(path=ROOT / V2_REL):
    """The sha256 of the v2 statistics module, which must be the one PROTOCOL Secs. 9.1 and 12.2 register (its functions
    are imported unchanged); AnalysisError otherwise."""
    sha = PJ.sha256_file(path)
    if sha != V2_SHA256:
        raise AnalysisError(f'{V2_REL} has sha256 {sha}, not the registered {V2_SHA256} (PROTOCOL Secs. 9.1, 12.2)')
    if Path(V2.__file__).resolve() != Path(path).resolve():
        raise AnalysisError(f'the imported v2 module {V2.__file__} is not {V2_REL}')
    return sha


def flag(x, column='flag'):
    """A runs.csv boolean (metrics_v4.write_csv writes True / False, empty for None) as bool; AnalysisError for any
    other value."""
    if isinstance(x, bool):
        return x
    s = '' if x is None else str(x).strip().lower()
    if s in ('true', '1', '1.0'):
        return True
    if s in ('', 'false', '0', '0.0', 'none'):
        return False
    raise AnalysisError(f'{column}: {x!r} is not a boolean')


ID_REQUIRED = ('job', 'route_id', 'kappa', 'seed', 'protocol_arm', 'analysis_use', 'missing_reason', 'test_route',
               'guard_note', 'valid_record')
METRIC_REQUIRED = tuple(dict.fromkeys(METRICS[f.metric].column for f in FAMILIES))


def parse_row(raw, source):
    """One runs.csv row with typed key fields (route_id, kappa, seed, analysis_use, test_route, health_only, guard_note,
    protocol_arm); every other column is kept as read (metrics are parsed when used, V2.fnum)."""
    row = dict(raw)
    where = f'{source} job {raw.get("job")!r}'
    kappa, seed = V2.fnum(raw.get('kappa')), V2.inum(raw.get('seed'))
    if not raw.get('job') or kappa is None or seed is None or not str(raw.get('route_id') or '').strip():
        raise AnalysisError(f'{where}: a row without job, route_id, kappa or seed')
    row.update(route_id=V2.norm_route(raw['route_id']), kappa=round(kappa, 4), seed=seed,
               protocol_arm=(str(raw.get('protocol_arm') or '').strip() or None),
               analysis_use=flag(raw.get('analysis_use'), f'{where} analysis_use'),
               test_route=flag(raw.get('test_route'), f'{where} test_route'),
               health_only=flag(raw.get('health_only'), f'{where} health_only'),
               guard_note=(str(raw.get('guard_note') or '').strip() or None),
               missing_reason=(str(raw.get('missing_reason') or '').strip() or None), source=source)
    return row


def read_runs(path):
    """(rows, absent metric columns) of a per-run CSV (aggregate_v4 runs.csv columns). The key columns of ID_REQUIRED
    and the family metric columns must be present; an absent secondary metric column leaves its rows without data and
    is reported."""
    path = Path(path)
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        cols = list(reader.fieldnames or [])
        missing = [c for c in ID_REQUIRED + METRIC_REQUIRED if c not in cols]
        if missing:
            raise AnalysisError(f'{PJ.rel(path)}: no column {missing}')
        rows = [parse_row(r, PJ.rel(path)) for r in reader]
    absent = sorted({m.column for m in METRICS.values()} - set(cols))
    return rows, absent


def read_sums(path):
    """{file name: sha256} of a SHA256SUMS file ('sha256  name' per line)."""
    out = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        sha, _, name = line.partition('  ')
        if line.strip():
            if len(sha) != 64 or not name:
                raise AnalysisError(f'{PJ.rel(path)}: malformed line {line!r}')
            out[name] = sha
    return out


def load_aggregation(path):
    """An aggregate_v4.py output directory as an input source: {'kind': 'aggregation', 'path', 'rows',
    'absent_columns', 'files': {path: sha256}, 'guard': aggregate.json interim_guard, 'freeze_sha256' (the record the
    aggregation was made with, None before the freeze), 'rl_sha256' (its RL freeze), 'created', 'script_sha256',
    'phases' (of its rows), and the aggregator's 'commit_audit' (R-2, H5), 'manipulation_checks' (R-3, Sec. 9.7) and
    'missing_reasons' (Sec. 9.8) documents}. runs.csv, aggregate.json and SHA256SUMS must exist; SHA256SUMS must list
    both with their current sha256, and aggregate.json must carry the aggregator's schema and the sha256 of this
    runs.csv; AnalysisError otherwise."""
    d = Path(path)
    names = ('runs.csv', 'aggregate.json', 'SHA256SUMS')
    absent = [n for n in names if not (d / n).is_file()]
    if absent:
        raise AnalysisError(f'{PJ.rel(d)}: not an aggregation (no {absent})')
    files = {n: PJ.sha256_file(d / n) for n in names}
    sums = read_sums(d / 'SHA256SUMS')
    bad = [n for n in names[:2] if sums.get(n) != files[n]]
    if bad:
        raise AnalysisError(f'{PJ.rel(d)}: {bad} differ from SHA256SUMS (changed after the aggregation)')
    bad = [n for n, sha in sums.items() if not (d / n).is_file() or PJ.sha256_file(d / n) != sha]
    if bad:
        raise AnalysisError(f'{PJ.rel(d)}: SHA256SUMS entries {bad} do not match the files')
    try:
        doc = json.loads((d / 'aggregate.json').read_text(encoding='utf-8'))
    except ValueError as e:
        raise AnalysisError(f'{PJ.rel(d)}/aggregate.json: not JSON ({e})') from None
    if not isinstance(doc, dict) or doc.get('schema') != A.SCHEMA:
        raise AnalysisError(f'{PJ.rel(d)}/aggregate.json: not an aggregation (schema {A.SCHEMA})')
    if (doc.get('outputs') or {}).get('runs.csv') != files['runs.csv']:
        raise AnalysisError(f'{PJ.rel(d)}: aggregate.json records another runs.csv '
                            f'({(doc.get("outputs") or {}).get("runs.csv")} != {files["runs.csv"]})')
    rows, absent_cols = read_runs(d / 'runs.csv')
    guard = doc.get('interim_guard') if isinstance(doc.get('interim_guard'), dict) else {}
    fz = guard.get('freeze') if isinstance(guard.get('freeze'), dict) else {}
    rl = (doc.get('references') or {}).get('rl') or {}
    part = {k: doc.get(k) if isinstance(doc.get(k), dict) else None
            for k in ('commit_audit', 'manipulation_checks', 'missing_reasons')}
    return {'kind': 'aggregation', 'path': PJ.rel(d), 'rows': rows, 'absent_columns': absent_cols,
            'files': {PJ.rel(d / n): sha for n, sha in files.items()}, 'guard': guard,
            'guard_status': guard.get('status'), 'freeze_sha256': fz.get('sha256'),
            'rl_sha256': rl.get('sha256') if isinstance(rl, dict) else None, 'created': doc.get('created'),
            'script_sha256': doc.get('script_sha256'), 'phases': sorted({r.get('phase') or '?' for r in rows}), **part}


def load_csv_source(path):
    """A bare per-run CSV as an input source (synthetic development data): {'kind': 'csv', 'path', 'rows',
    'absent_columns', 'files', 'guard': None, 'freeze_sha256': None, 'commit_audit': None, ...}. It can never carry a
    test-route row past the guard (guard_rows), and it has no commit audit or manipulation summary of the aggregator."""
    rows, absent_cols = read_runs(path)
    return {'kind': 'csv', 'path': PJ.rel(path), 'rows': rows, 'absent_columns': absent_cols,
            'files': {PJ.rel(path): PJ.sha256_file(path)}, 'guard': None, 'guard_status': None, 'freeze_sha256': None,
            'rl_sha256': None, 'created': None, 'script_sha256': None,
            'phases': sorted({r.get('phase') or '?' for r in rows}), 'commit_audit': None, 'manipulation_checks': None,
            'missing_reasons': None}


def check_sources(sources):
    """AnalysisError when a job id appears in more than one row of the inputs (one final run per job line)."""
    seen = {}
    for s in sources:
        for r in s['rows']:
            if r['job'] in seen:
                raise AnalysisError(f'job {r["job"]} is in {seen[r["job"]]} and in {s["path"]}')
            seen[r['job']] = s['path']


# ============================================================================================ routes

def make_table(entries, source, registered=False, extra=None):
    """The route table of the contrasts: {'routes': [route ids in index order], 'meta': {route: {'index',
    'scenario_type', 'town'}}, 'subsets': {'all', 'E', 'C', 'R': [route ids]}, 'source', 'registered', ...}.
    entries: [{'index', 'route_id', ...}] with distinct indices and routes; the subsets follow the index rules of Sec.
    3.1 and must agree with an entry's own 'subsets' flags where it has them."""
    ents = sorted(entries, key=lambda e: int(e['index']))
    ids = [V2.norm_route(e['route_id']) for e in ents]
    idx = [int(e['index']) for e in ents]
    if len(set(ids)) != len(ids) or len(set(idx)) != len(idx):
        raise AnalysisError(f'{source}: route ids or indices repeat')
    subsets = {s: [r for r, i in zip(ids, idx) if SUBSET_TEST[s](i)] for s in SUBSET_TEST}
    for e, r, i in zip(ents, ids, idx):
        for s, v in (e.get('subsets') or {}).items():
            if s in SUBSET_TEST and bool(v) != SUBSET_TEST[s](i):
                raise AnalysisError(f'{source}: route {r} (index {i}) has {s} = {v}, the Sec. 3.1 rule says otherwise')
    meta = {r: {'index': i, 'scenario_type': e.get('scenario_type'), 'town': e.get('town')}
            for e, r, i in zip(ents, ids, idx)}
    return {'routes': ids, 'meta': meta, 'subsets': subsets, 'source': source, 'registered': bool(registered),
            'subset_sizes': {s: len(v) for s, v in subsets.items()}, **(extra or {})}


def route_table():
    """The registered test routes (PROTOCOL Sec. 3.1): the 'test' list of route_split.json, whose sha256 must equal its
    registration manifest entry (interim_guard.registered_split); 44 routes, E 22, C 11, R 15, and the split's own
    subset lists must agree with the index rules."""
    reg = G.registered_split()
    path = ROOT / reg['path']
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != reg['sha256']:
        raise AnalysisError(f'{reg["path"]} changed while it was read')
    doc = json.loads(raw.decode('utf-8'))
    table = make_table(doc['test'], reg['path'], registered=True,
                       extra={'sha256': reg['sha256'], 'manifest': reg['manifest'],
                              'manifest_sha256': reg['manifest_sha256']})
    want = {'all': N_TEST_ROUTES, 'E': 22, 'C': 11, 'R': 15}
    if table['subset_sizes'] != want or set(table['routes']) != set(reg['test']):
        raise AnalysisError(f'{reg["path"]}: subsets {table["subset_sizes"]}, not the registered {want}')
    for s in ('E', 'C', 'R'):
        listed = [V2.norm_route(r) for r in (doc.get('subsets') or {}).get(s) or []]
        if listed and sorted(listed) != sorted(table['subsets'][s]):
            raise AnalysisError(f'{reg["path"]}: subset {s} differs from its index rule')
    return table


# ============================================================================================ the interim-look guard

def test_input_rows(rows, test_routes):
    """The test-route rows of the input: on a route of test_routes (the registered split plus any extra route), or
    flagged by the aggregator (test_route, or a guard_note: a guarded row)."""
    return [r for r in rows if r['route_id'] in test_routes or r.get('test_route') or r.get('guard_note')]


def code_citation(protocol, path=None):
    """{'path', 'sha256', 'cited'} of this script against Sec. 13 of a PROTOCOL.md (Sec. 9.12: the sha256 of the
    analysis code is entered in Sec. 13 before the analysis freeze)."""
    path = Path(__file__) if path is None else Path(path)
    sha = PJ.sha256_file(path)
    p = Path(protocol)
    p = p if p.is_absolute() else ROOT / p                 # interim_guard records it relative to the project root
    text = p.read_text(encoding='utf-8') if p.is_file() else ''
    return {'path': PJ.rel(path), 'sha256': sha, 'protocol': PJ.rel(p), 'cited': sha in G.protocol_sec13(text)}


def guard_rows(sources, freeze, test_routes, registered=None, code=None):
    """(rows, guard document) of the Sec. 9.11 guard: the rows the analysis may use (interim_guard.summary_rows:
    analysis_use rows; 'training' without a record, 'all' with one) and the guard's state. GuardRefused when the input
    has a test-route row (test_input_rows) and
      * no valid analysis-freeze record is given (freeze None; load_freeze has already refused an invalid one), or
      * the sha256 of this script is not cited in Sec. 13 of the record's PROTOCOL.md (code: code_citation, computed
        here unless given), or
      * an input holding a test-route row is a bare CSV, or an aggregation made without this record (aggregate.json
        interim_guard.freeze.sha256), or
      * a test-route row with analysis_use was not released by the record, or summary_rows refuses (a development
        record over a route of the registered split: registered, default the registered split's test routes).
    A building block of analyze, which verifies the record from its files, computes the code citation and passes the
    registered split plus any extra routes as test_routes and registered; callers use analyze."""
    rows = [r for s in sources for r in s['rows']]
    per_source = [(s, test_input_rows(s['rows'], test_routes)) for s in sources]
    tin = [r for _, t in per_source for r in t]
    doc = {'status': 'pre_freeze' if freeze is None else 'frozen' if freeze.get('registered') else
           'frozen_development', 'rule': G.RULE, 'test_input_rows': len(tin),
           'test_input_by_source': {s['path']: len(t) for s, t in per_source if t},
           'freeze': None if freeze is None else {k: freeze.get(k) for k in (
               'path', 'sha256', 'frozen', 'trigger', 'cut_amendment', 'protocol', 'protocol_sha256', 'seal',
               'registered', 'required_job_files')}, 'code': None}
    if tin:
        if freeze is None:
            raise GuardRefused(f'{len(tin)} test-route rows in the input (e.g. {tin[0]["job"]} on route '
                               f'{tin[0]["route_id"]}) and no valid analysis-freeze record ({G.RULE})')
        code = code_citation(freeze['protocol']) if code is None else code
        doc['code'] = code
        if not code['cited']:
            raise GuardRefused(f'{code["path"]} (sha256 {code["sha256"]}) is not cited in Sec. 13 of '
                               f'{freeze["protocol"]}: the analysis code must be registered before the analysis freeze '
                               '(Sec. 9.12)')
        for s, t in per_source:
            if not t:
                continue
            if s['kind'] != 'aggregation':
                raise GuardRefused(f'{s["path"]}: a bare CSV with {len(t)} test-route rows; '
                                   'test-route rows are read only from an aggregation made with the analysis-freeze '
                                   'record')
            if s.get('freeze_sha256') != freeze['sha256']:
                raise GuardRefused(f'{s["path"]}: the aggregation was made with the analysis-freeze record '
                                   f'{s.get("freeze_sha256")}, not {freeze["sha256"]}')
        unreleased = [r for r in tin if r['analysis_use'] and G.note_category(r.get('guard_note')) != G.RELEASED]
        if unreleased:
            r = unreleased[0]
            raise GuardRefused(f'{len(unreleased)} test-route rows with analysis_use were not released by the '
                               f'analysis-freeze record (e.g. {r["job"]}, route {r["route_id"]}, guard note '
                               f'{r.get("guard_note")!r})')
    use = G.summary_rows(rows, 'training' if freeze is None else 'all', freeze, registered)
    doc.update(rows=len(rows), usable_rows=len(use),
               released_rows=sum(1 for r in use if G.note_category(r.get('guard_note')) == G.RELEASED))
    return use, doc


# ============================================================================ cells (arm x kappa x seed x route)

CELL_STATUS = {
    'used': 'exactly one usable row (the final valid record whose code matches the pins), with valid_record = 1',
    'no_row': 'no job line of this cell in the input',
    'missing': 'a job line without a usable row: the aggregator\'s missing_reason (pending, not_launched, '
               'agent_crashed, sim_failure, no_metrics, code_mismatch, label_problem, health_only, ...)',
    'duplicate': 'more than one usable row for the cell (not attributable to one final run)',
    'inconsistent': 'a usable row without valid_record = 1',
}


def cell_key(arm, kappa, seed, route):
    return (str(arm), round(float(kappa), 4), int(seed), str(route))


def build_cells(rows, use, table):
    """{cell_key: cell} of every (protocol arm, kappa, seed, route) the input has a row for, on the routes of table;
    cell = {'status' (CELL_STATUS), 'row' (the used row, else None), 'jobs', 'reasons'}. use: the rows the guard lets
    the analysis use (guard_rows). Rows off the table's routes are not cells (counted by outside_rows)."""
    usable = {r['job'] for r in use}
    on = set(table['routes'])
    groups = {}
    for r in rows:
        if r['route_id'] in on and r.get('protocol_arm'):
            groups.setdefault(cell_key(r['protocol_arm'], r['kappa'], r['seed'], r['route_id']), []).append(r)
    cells = {}
    for key, rs in groups.items():
        used = [r for r in rs if r['job'] in usable]
        jobs = sorted(r['job'] for r in rs)
        if len(used) > 1:
            cells[key] = {'status': 'duplicate', 'row': None, 'jobs': jobs,
                          'reasons': [f'{len(used)} usable rows: {sorted(r["job"] for r in used)}']}
        elif used and V2.inum(used[0].get('valid_record')) != 1:
            cells[key] = {'status': 'inconsistent', 'row': None, 'jobs': jobs,
                          'reasons': [f'{used[0]["job"]}: analysis_use without valid_record = 1']}
        elif used:
            cells[key] = {'status': 'used', 'row': used[0], 'jobs': jobs, 'reasons': []}
        else:
            why = sorted({r.get('missing_reason') or ('not usable (guard)' if r['analysis_use'] else 'no reason given')
                          for r in rs})
            cells[key] = {'status': 'missing', 'row': None, 'jobs': jobs, 'reasons': why}
    return cells


def get_cell(cells, cond, route):
    """The cell of a condition on a route, or a 'no_row' cell."""
    return cells.get(cell_key(cond.arm, cond.kappa, cond.seed, route)) or {'status': 'no_row', 'row': None,
                                                                             'jobs': [], 'reasons': []}


def cell_text(cell):
    """'status' or 'status (reasons)'."""
    return cell['status'] + (f' ({"; ".join(cell["reasons"])})' if cell['reasons'] else '')


def outside_rows(rows, table):
    """Counts of the input rows that are not cells of the table: off its routes (by phase and block), or without a
    protocol arm."""
    on = set(table['routes'])
    off = {}
    for r in rows:
        if r['route_id'] not in on:
            k = f'{r.get("phase") or "?"}/{r.get("block") or "?"}'
            off[k] = off.get(k, 0) + 1
    return {'off_route_table': dict(sorted(off.items())),
            'no_protocol_arm': sum(1 for r in rows if r['route_id'] in on and not r.get('protocol_arm')),
            'unknown_protocol_arm': sorted({r['protocol_arm'] for r in rows if r['route_id'] in on
                                            and r.get('protocol_arm') and r['protocol_arm'] not in PROTOCOL_ARMS})}


# ============================================================================================ contrasts

STAT_KEYS = ('n', 'mean', 'mean_a', 'mean_b', 'sd', 'median', 'min', 'max', 'n_positive', 'n_negative', 'n_zero',
             'ci95', 'ci90', 'p_two_sided', 'p_method', 'n_extreme', 'n_patterns', 'n_nonzero', 'min_attainable_p',
             'dp_grid', 'dp_grid_registered', 'dp_max_statistic_change', 'p_mc', 'mc_flips', 'mc_seed', 'mc_hits',
             'mc_se')


def paired(contrast, metric, cells, table):
    """(pairs, n_complete, dropped) of one contrast and metric over the routes of its subset (Secs. 9.1, 9.8): pairs =
    [(route, value A, value B, A - B)] where both cells are used and both values exist; n_complete = the routes where
    both cells are used (pairwise complete); dropped = [{'route_id', 'reason'}] for every other route, in route
    order."""
    out, dropped, complete = [], [], 0
    for rid in table['subsets'][contrast.subset]:
        ca, cb = get_cell(cells, contrast.a, rid), get_cell(cells, contrast.b, rid)
        bad = [f'{side} {cond.name}: {cell_text(c)}' for side, cond, c in (('A', contrast.a, ca), ('B', contrast.b, cb))
               if c['status'] != 'used']
        if bad:
            dropped.append({'route_id': rid, 'reason': 'cell not used: ' + '; '.join(bad)})
            continue
        complete += 1
        va, vb = V2.fnum(ca['row'].get(metric.column)), V2.fnum(cb['row'].get(metric.column))
        if va is None or vb is None:
            miss = [n for n, v in ((contrast.a.name, va), (contrast.b.name, vb)) if v is None]
            dropped.append({'route_id': rid, 'reason': f'{metric.column} missing: {", ".join(miss)}'})
            continue
        out.append((rid, va, vb, va - vb))
    return out, complete, dropped


def paired_stats(pairs, metric, settings=REGISTERED):
    """The Sec. 9.1 statistics of the paired differences (every key of STAT_KEYS; None but n for n = 0): the mean,
    bootstrap_ci (settings.n_boot resamples, a fresh numpy.random.default_rng(settings.boot_seed)) and sign_flip_test
    (metric.grid; complete enumeration for n <= 22, exact DP above, with the Monte Carlo cross-check of
    settings.mc_flips sign vectors from default_rng(settings.mc_seed))."""
    res = dict.fromkeys(STAT_KEYS)
    n = res['n'] = len(pairs)
    if not n:
        return res
    d = np.array([p[3] for p in pairs], dtype=float)
    va = np.array([p[1] for p in pairs], dtype=float)
    vb = np.array([p[2] for p in pairs], dtype=float)
    res.update(mean=float(d.mean()), mean_a=float(va.mean()), mean_b=float(vb.mean()),
               sd=float(d.std(ddof=1)) if n > 1 else None, median=float(np.median(d)), min=float(d.min()),
               max=float(d.max()), n_positive=int(np.count_nonzero(d > 0)), n_negative=int(np.count_nonzero(d < 0)),
               n_zero=int(np.count_nonzero(d == 0)))
    res.update(bootstrap_ci(d, settings.n_boot, settings.boot_seed))
    sf = sign_flip_test(d, metric.grid, settings.mc_flips, settings.mc_seed, ENUM_MAX_N)
    res.update({k: v for k, v in sf.items() if k in STAT_KEYS and k != 'n'})
    return res


def directional_label(mean, p, better):
    """The registered label (Sec. 9.1) of a mean difference A - B with its (Holm-adjusted) p: label_directional on the
    mean oriented to the hypothesized direction (A - B for 'higher', B - A for 'lower'), in the v4 words (LABELS)."""
    if better not in ('higher', 'lower'):
        raise ValueError(f'no hypothesized direction ({better!r})')
    m = None if mean is None else (mean if better == 'higher' else -mean)
    return LABELS[label_directional(m, p, ALPHA)]


def evaluate(contrast, metric, cells, table, settings=REGISTERED):
    """(row, route rows) of one contrast and metric: the contrast's identity, the metric, n_expected (the routes of the
    subset), n_complete, the statistics (paired_stats) and the dropped routes; route rows: one per route of the subset
    (values, difference, or the reason it was dropped)."""
    prs, complete, dropped = paired(contrast, metric, cells, table)
    row = {'contrast': contrast.cid, 'a': contrast.a.name, 'b': contrast.b.name, 'a_arm': contrast.a.arm,
           'b_arm': contrast.b.arm, 'kappa': contrast.a.kappa if contrast.a.kappa == contrast.b.kappa else None,
           'seed': contrast.a.seed if contrast.a.seed == contrast.b.seed else None, 'subset': contrast.subset,
           'subset_rule': SUBSET_RULES[contrast.subset], 'metric': metric.key, 'column': metric.column,
           'metric_label': metric.label, 'unit': metric.unit, 'better': metric.better, 'grid': metric.grid,
           'n_expected': len(table['subsets'][contrast.subset]), 'n_complete': complete,
           **paired_stats(prs, metric, settings), 'dropped': dropped}
    by_route = {p[0]: p for p in prs}
    why = {x['route_id']: x['reason'] for x in dropped}
    routes = []
    for rid in table['subsets'][contrast.subset]:
        p = by_route.get(rid)
        routes.append({'contrast': contrast.cid, 'metric': metric.key, 'route_id': rid,
                       'route_index': table['meta'][rid]['index'], 'scenario_type': table['meta'][rid]['scenario_type'],
                       'value_a': p[1] if p else None, 'value_b': p[2] if p else None,
                       'difference': p[3] if p else None, 'status': 'paired' if p else why[rid]})
    return row, routes


def run_family(family, cells, table, settings=REGISTERED):
    """(family document, route rows) of one registered family (Secs. 9.2, 9.3): every contrast on the family's metric
    (evaluate), Holm over the family (holm: a missing p counts as 1, so the family size stays the registered one; H2,
    a single test, keeps its p) and the label of each contrast from its adjusted p (directional_label)."""
    metric = METRICS[family.metric]
    rows, routes = [], []
    for c in family.contrasts:
        row, rr = evaluate(c, metric, cells, table, settings)
        rows.append(row)
        routes += [{'table': f'family_{family.name}', **r} for r in rr]
    m = len(rows)
    adj = holm([r['p_two_sided'] for r in rows])
    for r, pa in zip(rows, adj):
        r.update(family=family.name, role=family.role, correction=f'Holm over {m}' if m > 1 else 'single test',
                 family_size=m, p_adjusted=pa, label=directional_label(r['mean'], pa, metric.better))
    doc = {'name': family.name, 'role': family.role, 'section': family.section, 'question': family.question,
           'metric': metric.key, 'metric_label': metric.label, 'better': metric.better, 'family_size': m,
           'correction': f'Holm over {m}' if m > 1 else 'single test',
           'subsets': sorted({c.subset for c in family.contrasts}), 'rows': rows}
    return doc, routes


def secondary_metrics(families):
    """The secondary metric keys of a contrast tested by the given families: SECONDARY_METRICS plus the families'
    FAMILY_EXTRA_METRICS, without the families' own metrics, in that order."""
    keys = list(SECONDARY_METRICS) + [k for f in families for k in FAMILY_EXTRA_METRICS.get(f, ())]
    own = {FAMILY_BY_NAME[f].metric for f in families}
    return [k for k in dict.fromkeys(keys) if k not in own]


def run_secondary(cells, table, settings=REGISTERED):
    """(rows, route rows) of the uncorrected secondary and descriptive quantities (Sec. 9.3: 'every other paired
    quantity is secondary or descriptive, uncorrected and labelled'): every distinct contrast of FAMILIES on every
    metric of secondary_metrics. p_adjusted = p (no correction); a metric with a direction is labelled from the
    uncorrected p (role 'secondary'), a metric without one is 'descriptive'."""
    rows, routes = [], []
    for contrast, fams in family_contrasts().items():
        names = [f for f, _ in fams]
        for key in secondary_metrics(names):
            metric = METRICS[key]
            row, rr = evaluate(contrast, metric, cells, table, settings)
            row.update(family=None, families=names, role='secondary' if metric.better else DESCRIPTIVE,
                       correction='none (uncorrected)', family_size=1, p_adjusted=row['p_two_sided'],
                       label=(directional_label(row['mean'], row['p_two_sided'], metric.better) if metric.better
                              else DESCRIPTIVE))
            rows.append(row)
            routes += [{'table': 'secondary', **r} for r in rr]
    return rows, routes


# ============================================================ descriptive contrasts (Secs. 7.5, 9.6, 9.9, 9.10)

def noise_floor(route_rows, settings=REGISTERED):
    """The noise-floor summary of a seed-to-seed contrast (Sec. 9.6; as the v2 noise-floor contrasts): the mean, median
    and max of |d| over the paired routes, the 95% bootstrap interval of the mean |d| (bootstrap_ci with abs_values,
    settings.n_boot resamples, a fresh default_rng(settings.boot_seed)) and the Pearson r of the two seeds' values."""
    prs = [x for x in route_rows if x['difference'] is not None]
    out = dict.fromkeys(('mean_abs_diff', 'mean_abs_diff_ci95', 'median_abs_diff', 'max_abs_diff', 'pearson_r_a_b'))
    if not prs:
        return out
    d = np.array([x['difference'] for x in prs], dtype=float)
    va = np.array([x['value_a'] for x in prs], dtype=float)
    vb = np.array([x['value_b'] for x in prs], dtype=float)
    out.update(mean_abs_diff=float(np.abs(d).mean()), median_abs_diff=float(np.median(np.abs(d))),
               max_abs_diff=float(np.abs(d).max()),
               mean_abs_diff_ci95=bootstrap_ci(d, settings.n_boot, settings.boot_seed, levels=(0.95,),
                                                abs_values=True)['ci95'],
               pearson_r_a_b=(float(np.corrcoef(va, vb)[0, 1]) if len(d) > 2 and va.std() > 0 and vb.std() > 0
                              else None))
    return out


def run_descriptive(cells, table, settings=REGISTERED):
    """(rows, route rows) of the descriptive contrasts (DESCRIPTIVE_CONTRASTS): every contrast on its metrics with the
    Sec. 9.1 statistics (evaluate: n, mean, CIs and the uncorrected p for information), role and label 'descriptive',
    no correction; the seed-to-seed rows carry the noise floor (noise_floor)."""
    rows, routes = [], []
    for dsc in DESCRIPTIVE_CONTRASTS:
        for key in dsc.metrics:
            row, rr = evaluate(dsc.contrast, METRICS[key], cells, table, settings)
            row.update(family=None, families=None, group=dsc.group, section=dsc.section, role=DESCRIPTIVE,
                       correction='none (descriptive)', family_size=1, p_adjusted=None, label=DESCRIPTIVE,
                       note=DESCRIPTIVE_GROUPS[dsc.group])
            if dsc.group == 'noise_floor':
                row.update(noise_floor(rr, settings))
            rows.append(row)
            routes += [{'table': 'descriptive', **r} for r in rr]
    return rows, routes


def analysis_conditions(table):
    """{condition: [route ids of the table, in table order]} of every condition the family and descriptive contrasts
    use, on the routes of the subsets it is used on (families first, then DESCRIPTIVE_CONTRASTS, in order)."""
    want = {}
    for c in list(family_contrasts()) + [d.contrast for d in DESCRIPTIVE_CONTRASTS]:
        for cond in (c.a, c.b):
            want.setdefault(cond, set()).update(table['subsets'][c.subset])
    return {cond: [r for r in table['routes'] if r in routes] for cond, routes in want.items()}


def route_abilities(table):
    """{route id: [Bench2Drive abilities]} of the table's routes from their scenario type: the official multi-label
    map (fig1_data.ability_map: Bench2Drive ability_benchmark.py, sha256 pinned there; abilities_of). A scenario type
    the map does not name has no ability (it counts in 'all' only)."""
    try:
        amap = F1.ability_map()
    except SystemExit as e:                               # fig1_data refuses a changed mapping file
        raise AnalysisError(f'ability map: {e}') from None
    return {r: F1.abilities_of(str(table['meta'][r].get('scenario_type') or ''), amap) for r in table['routes']}


def per_ability(rows, route_rows, ability_of, table, settings=REGISTERED):
    """Sec. 9.9 (descriptive, no per-scenario test): for every row (contrast x metric, first occurrence) the paired
    differences of its routes grouped by Bench2Drive ability (multi-label: a route counts in each of its abilities) and
    'all': n, the subset's routes with that ability, the mean difference and both arms' means, the signs, and the 95%
    percentile bootstrap interval (bootstrap_ci, settings, a fresh generator per group) for at least ABILITY_MIN_CI_N
    routes."""
    by = {}
    for x in route_rows:
        if x['difference'] is not None:
            by.setdefault((x['contrast'], x['metric']), {})[x['route_id']] = x
    out, seen = [], set()
    for r in rows:
        key = (r['contrast'], r['metric'])
        if key in seen:
            continue
        seen.add(key)
        prs = by.get(key, {})
        for ab in ABILITIES + ('all',):
            on = [rid for rid in table['subsets'][r['subset']] if ab == 'all' or ab in ability_of.get(rid, ())]
            sel = [prs[rid] for rid in on if rid in prs]
            d = np.array([x['difference'] for x in sel], dtype=float)
            n = len(sel)
            ci = (bootstrap_ci(d, settings.n_boot, settings.boot_seed, levels=(0.95,))['ci95']
                  if n >= ABILITY_MIN_CI_N else None)
            out.append({'contrast': r['contrast'], 'a': r['a'], 'b': r['b'], 'subset': r['subset'],
                        'metric': r['metric'], 'family': r.get('family'), 'group': r.get('group'), 'ability': ab,
                        'n_routes': len(on), 'n': n, 'mean': float(d.mean()) if n else None,
                        'mean_a': float(np.mean([x['value_a'] for x in sel])) if n else None,
                        'mean_b': float(np.mean([x['value_b'] for x in sel])) if n else None, 'ci95': ci,
                        'n_positive': int(np.count_nonzero(d > 0)), 'n_negative': int(np.count_nonzero(d < 0)),
                        'n_zero': int(np.count_nonzero(d == 0)), 'routes': [x['route_id'] for x in sel],
                        'scenario_types': sorted({str(x['scenario_type']) for x in sel})})
    return out


def _find(rows, cid, metric='driving_score'):
    return next((r for r in rows if r['contrast'] == cid and r['metric'] == metric), None)


def replicates(desc_rows):
    """Sec. 9.6: the per-arm noise floor (seed 11 - seed 12 on R: mean |d| with its interval, median, max, r), and
    each seed-12 contrast on R next to its seed-11 counterpart on R (same sign of the mean; whether the seed-12 95% CI
    contains the seed-11 mean); descriptive."""
    noise = {}
    for r in desc_rows:
        if r['group'] == 'noise_floor' and r['metric'] == 'driving_score':
            noise[r['a_arm']] = {k: r.get(k) for k in (
                'contrast', 'n', 'n_expected', 'mean', 'ci95', 'mean_abs_diff', 'mean_abs_diff_ci95', 'median_abs_diff',
                'max_abs_diff', 'pearson_r_a_b')}
    pairs = []
    for b in SEED12_OTHERS:
        s12 = _find(desc_rows, Contrast(Cond('fl_full', 1.0, 12), Cond(b, 1.0, 12), 'R').cid)
        s11 = _find(desc_rows, Contrast(Cond('fl_full', 1.0, 11), Cond(b, 1.0, 11), 'R').cid)
        m11, m12 = s11['mean'], s12['mean']
        pairs.append({'contrast': f'fl_full - {b}', 'seed11_on_R': _brief(s11), 'seed12_on_R': _brief(s12),
                      'same_sign_of_mean': None if m11 is None or m12 is None else bool(np.sign(m11) == np.sign(m12)),
                      'seed12_ci95_contains_seed11_mean': (None if m11 is None or s12['ci95'] is None else
                                                           bool(s12['ci95'][0] <= m11 <= s12['ci95'][1]))})
    return {'definition': 'seed-12 replicates of ' + ', '.join(REPLICATE_ARMS) + ' on R (15 routes), kappa 1.0 '
                          '(Sec. 9.6); the noise floor is the per-arm seed-to-seed |DS(s11) - DS(s12)|; the seed-12 '
                          'contrasts are descriptive', 'noise_floor_ds': noise, 'seed12_contrasts': pairs}


def rl_gain(families, desc_rows, ability_rows):
    """Sec. 7.5, the breakdown of the RL gain fl_full - fl_heuristic on DS (descriptive): the 44-route H2 row; by GPU
    budget (kappa 1.0, 1.5 and 2.0 on E); by seed (seed 11 and seed 12 on R); by Bench2Drive ability (the H2 contrast
    per ability, per_ability)."""
    h2 = next(f for f in families if f['name'] == 'H2')['rows'][0]
    by_kappa = [_brief(_find(desc_rows, Contrast(Cond('fl_full', k), Cond('fl_heuristic', k), 'E').cid))
                for k in (1.0, 1.5, 2.0)]
    by_seed = [_brief(_find(desc_rows, Contrast(Cond('fl_full', 1.0, s), Cond('fl_heuristic', 1.0, s), 'R').cid))
               for s in (11, 12)]
    abil = [{k: x[k] for k in ('ability', 'n_routes', 'n', 'mean', 'ci95', 'n_positive', 'n_negative', 'n_zero')}
            for x in ability_rows if x['contrast'] == RL_GAIN.cid and x['metric'] == 'driving_score']
    return {'definition': 'RL gain = Full FrameLease - FrameLease + Heuristic, DS (Sec. 7.5; descriptive)',
            'all_44_routes': _brief(h2), 'by_kappa_on_E': dict(zip(('1.0', '1.5', '2.0'), by_kappa)),
            'by_seed_on_R': dict(zip(('11', '12'), by_seed)), 'by_ability': abil}


def mde(sd, n, alpha, power=MDE_POWER):
    """The minimum detectable mean paired difference (Sec. 9.10): (z_{1 - alpha / 2} + z_power) x sd / sqrt(n), the
    two-sided normal approximation the registered table uses; None without sd or n."""
    if sd is None or not n:
        return None
    z = statistics.NormalDist()
    return (z.inv_cdf(1.0 - alpha / 2.0) + z.inv_cdf(power)) * sd / math.sqrt(n)


def sensitivity(families):
    """Sec. 9.10: the registered MDE table recomputed from its SD (MDE_SD_DS), and per family contrast the MDE at the
    first Holm step (alpha / m) and the last (alpha), planned (registered SD, DS families, the registered n) and
    observed (the contrast's SD of paired differences and n). A contrast that is not 'improves' or 'worse' carries the
    statement that no difference larger than its MDE was detected, which is not evidence of no effect."""
    reg = [{'setting': s, 'n': n, 'alpha': a, 'mde_registered': m, 'mde_computed': mde(MDE_SD_DS, n, a)}
           for s, n, a, m in MDE_REGISTERED]
    rows = []
    for f in families:
        m = f['family_size']
        for r in f['rows']:
            unit = METRICS[r['metric']].unit
            obs = (mde(r['sd'], r['n'], ALPHA / m), mde(r['sd'], r['n'], ALPHA))
            plan = ((mde(MDE_SD_DS, r['n_expected'], ALPHA / m), mde(MDE_SD_DS, r['n_expected'], ALPHA))
                    if r['metric'] == 'driving_score' else (None, None))
            stmt = None
            if r['label'] not in ('improves', 'worse') and obs[0]:          # an SD of 0 gives no statement
                rng = f'{obs[1]:.3g}' if m == 1 else f'{obs[1]:.3g} (last Holm step) to {obs[0]:.3g} (first step)'
                stmt = (f'no difference larger than about {rng} {unit} was detected (80% power, two-sided); this is '
                        'not evidence of no effect (Sec. 9.10)')
            rows.append({'family': f['name'], 'contrast': r['contrast'], 'metric': r['metric'], 'unit': unit,
                         'n': r['n'], 'n_expected': r['n_expected'], 'sd': r['sd'], 'family_size': m,
                         'alpha_first_step': ALPHA / m, 'alpha_last_step': ALPHA, 'mde_observed_first_step': obs[0],
                         'mde_observed_last_step': obs[1], 'mde_planned_first_step': plan[0],
                         'mde_planned_last_step': plan[1], 'label': r['label'], 'statement': stmt})
    return {'method': 'two-sided normal approximation, 80% power: (z_{1-alpha/2} + z_0.80) x SD / sqrt(n)',
            'sd_registered_ds': MDE_SD_DS, 'sd_implied_by_v2_half_width': 9.2 * math.sqrt(44) / 1.96,
            'registered_table': reg, 'contrasts': rows}


# ============================================================================================ H4 offline (Sec. 9.4)

OFFLINE_COLUMNS = {'paired.csv': ('protocol', 'a', 'b', 'subset', 'need', 'alpha', 'metric', 'a_value', 'b_value',
                                  'diff', 'diff_lo', 'diff_hi'),
                   'per_clip_selected.csv': ('design', 'need', 'clip', 'candidate', 'continuity', 'R_cond',
                                             'premature_refresh', 'mean_H_s', 'oracle_continuity', 'n', 'conf',
                                             'over', 'overc')}


def load_offline(directory=ROOT / OFFLINE_REL):
    """The offline lease-ablation outputs the H4 rule reads (OFFLINE_FILES of framelease_v4/offline/analyze.py):
    {'path', 'registered_location', 'files': {path: sha256}, 'paired': rows, 'per_clip': rows (file order, which is
    the clip order of the bootstrap weights)}. AnalysisError for a missing file or column."""
    d = Path(directory)
    out = {'path': PJ.rel(d), 'registered_location': d.resolve() == (ROOT / OFFLINE_REL).resolve(), 'files': {}}
    for name, key in zip(OFFLINE_FILES, ('paired', 'per_clip')):
        p = d / name
        if not p.is_file():
            raise AnalysisError(f'{PJ.rel(p)}: no offline output (Sec. 9.4)')
        with open(p, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            lack = [c for c in OFFLINE_COLUMNS[name] if c not in (reader.fieldnames or [])]
            if lack:
                raise AnalysisError(f'{PJ.rel(p)}: no column {lack}')
            out[key] = list(reader)
        out['files'][PJ.rel(p)] = PJ.sha256_file(p)
    return out


def per_clip_sums(per_clip, design, need):
    """(clips, {metric: (numerator, denominator) per clip}) of one design and need of per_clip_selected.csv: the
    pooled metrics of offline/analyze.py METRICS rebuilt from the per-clip rates and counts (continuity = cont / n,
    R_cond = overc / conf, R_marg = over / n, premature_refresh = prem / oracle with oracle = oracle_continuity x n,
    mean_H_s = sum_H / n); counts are rounded to integers (the file keeps 6 significant digits)."""
    rows = [r for r in per_clip if r['design'] == design and r['need'] == need]

    def col(name):
        vals = [V2.fnum(r.get(name)) for r in rows]
        return np.array([np.nan if v is None else v for v in vals], dtype=float)

    n, orc = col('n'), np.round(col('oracle_continuity') * col('n'))
    prem = np.where(orc > 0, np.round(np.nan_to_num(col('premature_refresh')) * orc), 0.0)
    sums = {'continuity': (np.round(col('continuity') * n), n), 'R_cond': (col('overc'), col('conf')),
            'R_marg': (col('over'), n), 'premature_refresh': (prem, orc), 'mean_H_s': (col('mean_H_s') * n, n)}
    return [r['clip'] for r in rows], sums


def per_clip_pair(per_clip, a, b, metric, need):
    """A - B of a pooled metric from per_clip_selected.csv with the offline bootstrap (offline/analyze.py boot_weights:
    the point estimate and 2000 clip resamples, multinomial weights from default_rng(20261109); ci: the 2.5% and 97.5%
    quantiles): {'a_value', 'b_value', 'diff', 'lo', 'hi', 'n_clips', 'source'}; None when either design has no
    rows, the clip lists differ or a value is missing."""
    ca, sa = per_clip_sums(per_clip, a, need)
    cb, sb = per_clip_sums(per_clip, b, need)
    if not ca or ca != cb or metric not in sa:
        return None
    if any(not np.all(np.isfinite(x)) for x in (*sa[metric], *sb[metric])):
        return None
    w = OA.boot_weights(len(ca))
    with np.errstate(invalid='ignore', divide='ignore'):
        va = (w @ sa[metric][0]) / (w @ sa[metric][1])
        vb = (w @ sb[metric][0]) / (w @ sb[metric][1])
    dlt = va - vb
    lo, hi = OA.ci(dlt[1:])
    fin = [None if not math.isfinite(x) else float(x) for x in (va[0], vb[0], dlt[0], lo, hi)]
    return {'a_value': fin[0], 'b_value': fin[1], 'diff': fin[2], 'lo': fin[3], 'hi': fin[4], 'n_clips': len(ca),
            'source': 'per_clip_selected.csv (offline bootstrap recomputed)'}


def _alpha_eq(x, alpha):
    v = V2.fnum(x)
    return v is not None and abs(v - alpha) < 1e-9


def offline_quantity(off, protocol, a, b, alpha, metric, subset=H4_SUBSET, need=H4_NEED):
    """(value, reason) of one paired offline quantity A - B: the paired.csv row ({'a_value', 'b_value', 'diff', 'lo',
    'hi', 'source'}); if paired.csv lacks it, the per_clip_selected.csv recomputation (Sec. 9.4) when the quantity is in
    that file's scope (PER_CLIP_SCOPE, PER_CLIP_METRICS); otherwise None and the reason."""
    for r in off['paired']:
        if (r['protocol'], r['a'], r['b'], r['subset'], r['need'], r['metric']) == (protocol, a, b, subset, need,
                                                                                   metric) and _alpha_eq(r['alpha'],
                                                                                                         alpha):
            v = {k: V2.fnum(r.get(c)) for k, c in (('a_value', 'a_value'), ('b_value', 'b_value'), ('diff', 'diff'),
                                                    ('lo', 'diff_lo'), ('hi', 'diff_hi'))}
            return {**v, 'source': 'paired.csv'}, None
    sc = PER_CLIP_SCOPE
    if (protocol, subset) != (sc['protocol'], sc['subset']) or abs(alpha - sc['alpha']) > 1e-9 \
            or a not in sc['designs'] or b not in sc['designs'] or metric not in PER_CLIP_METRICS:
        return None, (f'not in paired.csv, and per_clip_selected.csv holds only the {sc["protocol"]}-selected '
                      f'candidates (subset {sc["subset"]}, alpha {sc["alpha"]}, {"/".join(sc["designs"])}; metrics '
                      f'{", ".join(PER_CLIP_METRICS)})')
    v = per_clip_pair(off['per_clip'], a, b, metric, need)
    return (v, None) if v is not None else (None, 'not in paired.csv and not computable from per_clip_selected.csv')


def h4_label(q, risk, better):
    """The Sec. 9.4 rule on one quantity: 'supported' if the 95% CI of the oriented difference (A - B for a
    higher-is-better quantity, B - A for premature refresh) lies above 0 and the 95% CI of the realized-R_cond
    difference A - B contains 0 or lies below 0 (its lower bound <= 0); 'contradicted' if the oriented CI lies below
    0; otherwise 'inconclusive'; 'no data' without both intervals."""
    if q is None or risk is None or None in (q.get('lo'), q.get('hi'), risk.get('lo')):
        return 'no data'
    lo, hi = (q['lo'], q['hi']) if better == 'higher' else (-q['hi'], -q['lo'])
    if lo > 0 and risk['lo'] <= 0:
        return 'supported'
    if hi < 0:
        return 'contradicted'
    return 'inconclusive'


def per_clip_check(off):
    """Every paired.csv row in the scope of per_clip_selected.csv recomputed with the offline bootstrap: {'compared',
    'agree', 'max_abs_diff', 'disagree': [...]} (agreement within OFFLINE_TOL, the files' 6 significant digits). It
    checks the fallback of Sec. 9.4 on real quantities and that the two files belong together."""
    sc, compared, worst, bad = PER_CLIP_SCOPE, 0, 0.0, []
    for r in off['paired']:
        if (r['protocol'], r['subset']) != (sc['protocol'], sc['subset']) or not _alpha_eq(r['alpha'], sc['alpha']) \
                or r['a'] not in sc['designs'] or r['b'] not in sc['designs'] or r['metric'] not in PER_CLIP_METRICS:
            continue
        v = per_clip_pair(off['per_clip'], r['a'], r['b'], r['metric'], r['need'])
        compared += 1
        for k, c in (('diff', 'diff'), ('lo', 'diff_lo'), ('hi', 'diff_hi')):
            want, got = V2.fnum(r[c]), None if v is None else v[k]
            gap = math.inf if want is None or got is None else abs(got - want)
            worst = max(worst, gap)
            if gap > OFFLINE_TOL * max(1.0, abs(want or 0.0)):
                bad.append({'a': r['a'], 'b': r['b'], 'need': r['need'], 'metric': r['metric'], 'field': c,
                            'paired_csv': want, 'recomputed': got})
    return {'compared': compared, 'agree': compared > 0 and not bad, 'max_abs_diff': worst if compared else None,
            'tolerance': OFFLINE_TOL, 'disagree': bad}


def h4_offline(off):
    """(document, rows) of Sec. 9.4: the primary H4 row (SUFFIX - GLOBAL continuity, nested selection at R_cond <= 5%,
    need 0.964 s, all plans, 2000 clip-bootstrap resamples) and the secondary rows with the same rule (both comparisons
    x both risk levels x continuity, utilization and premature refresh), each with the realized-R_cond difference of the
    same selection; the label of every row (h4_label) and the per_clip_selected.csv check."""
    rows = []
    for a, b in H4_COMPARISONS:
        for alpha in H4_ALPHAS:
            risk, risk_why = offline_quantity(off, H4_PROTOCOL, a, b, alpha, H4_RISK)
            for metric, better in H4_QUANTITIES.items():
                q, why = offline_quantity(off, H4_PROTOCOL, a, b, alpha, metric)
                var = [x for x, on in ((f'{a} - {b}', b != H4_PRIMARY[1]),
                                       (f'R_cond <= {alpha:.0%}', alpha != H4_PRIMARY[2]),
                                       (metric, metric != H4_PRIMARY[3])) if on]
                rows.append({'role': 'primary' if (a, b, alpha, metric) == H4_PRIMARY else 'secondary',
                             'variation': '; '.join(var) or None, 'a': a, 'b': b, 'protocol': H4_PROTOCOL,
                             'subset': H4_SUBSET, 'need': H4_NEED, 'need_s': OC.NEEDS[H4_NEED], 'alpha': alpha,
                             'metric': metric, 'better': better,
                             **{f'{k}': (q or {}).get(k) for k in ('a_value', 'b_value', 'diff', 'lo', 'hi')},
                             'source': (q or {}).get('source'), 'missing': why,
                             **{f'r_cond_{k}': (risk or {}).get(k) for k in ('diff', 'lo', 'hi')},
                             'r_cond_missing': risk_why, 'label': h4_label(q, risk, better)})
    primary = next(r for r in rows if r['role'] == 'primary')
    doc = {'question': 'H4 offline: the suffix-aligned lease keeps more plans continuous than the Global-Margin lease '
                       'at a realized R_cond that is not higher (Sec. 9.4)',
           'rule': 'supported: the 95% CI of the continuity difference lies above 0 and the 95% CI of the '
                   'realized-R_cond difference contains 0 or lies below 0; contradicted: the continuity CI lies below '
                   '0; inconclusive otherwise. Secondary rows use the same rule, with the difference oriented so that '
                   'positive is better (premature refresh: B - A)',
           'label': primary['label'], 'primary': primary, 'status': H4_PRE_REGISTRATION,
           'bootstrap': {'n': OC.BOOT_N, 'seed': OC.BOOT_SEED, 'unit': 'clip'}, 'source': off['path'],
           'registered_location': off['registered_location'], 'files': off['files'],
           'per_clip_check': per_clip_check(off), 'rows': rows}
    return doc, rows


# ================================================ H5, overhead, manipulation checks, missing data (Secs. 9.5-9.8)

def load_s3(path):
    """The S3 report of framelease_v4/protocol/stress_bench.py (Sec. 7.6; schema S3_SCHEMA, test 'S3'): {'path',
    'sha256', 'label', 'registered' (the report is a registered run with at least S3_MIN_SEQUENCES sequences on both
    targets), 'n_sequences', 'targets', 'violations_total', 'violations': {target: {invariant: count}}, 'pass',
    'coverage_ok'}. AnalysisError for another schema or test, or a report without its violation counts."""
    path = Path(path)
    try:
        doc = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        raise AnalysisError(f'{PJ.rel(path)}: cannot read the S3 report ({e})') from None
    if not isinstance(doc, dict) or doc.get('schema') != S3_SCHEMA or doc.get('test') != 'S3':
        raise AnalysisError(f'{PJ.rel(path)}: not an S3 report of stress_bench.py (schema {S3_SCHEMA}, test S3)')
    targets = doc.get('targets')
    total = V2.inum(doc.get('violations_total'))
    if not isinstance(targets, dict) or not targets or total is None \
            or any(not isinstance(t, dict) or V2.inum(t.get('violations_total')) is None for t in targets.values()):
        raise AnalysisError(f'{PJ.rel(path)}: no violation counts')
    n = V2.inum(doc.get('n_sequences')) or 0
    registered = doc.get('registered') is True and n >= S3_MIN_SEQUENCES and set(targets) == set(S3_TARGETS)
    return {'path': PJ.rel(path), 'sha256': PJ.sha256_file(path), 'label': doc.get('label'), 'registered': registered,
            'n_sequences': n, 'targets': sorted(targets), 'violations_total': total,
            'violations': {t: {k: v for k, v in (r.get('violations') or {}).items() if v} for t, r in targets.items()},
            'pass': doc.get('pass') is True and total == 0, 'coverage_ok': doc.get('coverage_ok')}


def no_log_run(run, rows):
    """(entry, unaudited) of a commit-audit run with status NO_LOG (commit_audit.py: neither jobs.jsonl nor
    events.jsonl). rows: the source's runs.csv rows; the row whose selected_run is the run gives its commits. A run
    whose row records 0 commits had nothing to audit (listed only); a run whose row records commits, or whose commits
    are unknown (no row selects it: an earlier attempt, a run matching no job, or a row without the commits value), was
    not audited, so condition 1 of Sec. 9.5 is not shown for it (unaudited)."""
    rd = str(Path(str(run.get('run_dir') or '')))
    row = next((r for r in rows if r.get('selected_run') and str(Path(str(r['selected_run']))) == rd), None)
    commits = None if row is None else V2.inum(row.get('commits'))
    if row is None:
        why = 'no jobs.jsonl or events.jsonl, and no runs.csv row selects this run: its commits are unknown'
    elif commits is None:
        why = f'no jobs.jsonl or events.jsonl, and the row of job {row["job"]} records no commit count'
    elif commits > 0:
        why = f'no jobs.jsonl or events.jsonl, but the row of job {row["job"]} records {commits} commits'
    else:
        why = f'no jobs.jsonl or events.jsonl; the row of job {row["job"]} records 0 commits (nothing to audit)'
    entry = {'run_dir': run.get('run_dir'), 'jobs': run.get('jobs'), 'status': run.get('status'),
             'selected_by': None if row is None else row['job'], 'commits': commits, 'error': why}
    return entry, commits != 0


def h5(sources, s3=None):
    """Sec. 9.5 (H5): 'supported' if the commit audit (the aggregator's R-2 document of every aggregation) finds 0
    commits violating Eq. 9 in every run of every phase and the registered S3 finds 0 violations; 'contradicted'
    otherwise, with every violation listed. The audit must cover every phase with closed-loop runs (H5_PHASES) and every
    run: a run the audit could not check (status ERROR: a malformed or inconsistent log; status NO_LOG with commits
    recorded or unknown, no_log_run) leaves condition 1 unmet, so the label is 'contradicted' even without a violation
    (listed under 'unaudited'); every NO_LOG run is listed under 'no_log_runs'. 'undetermined' (not a registered label;
    a run with it is 'development', development_reasons) means the evidence is incomplete: an input without the audit,
    runs withheld by the interim-look guard before the analysis freeze, a phase not covered, or no registered S3
    report (the violations of a development S3 report are reported in 's3', not counted)."""
    audits, violating, unaudited, undetermined, no_log = [], [], [], [], []
    phases = set()
    for s in sources:
        if s['kind'] != 'aggregation':
            undetermined.append(f'{s["path"]}: a bare CSV has no commit audit')
            continue
        a = s.get('commit_audit')
        if not a:
            undetermined.append(f'{s["path"]}: aggregate.json has no commit audit')
            continue
        phases.update(s.get('phases') or ())
        runs = a.get('runs') or []
        audits.append({'source': s['path'], 'phases': s.get('phases'), 'violations': a.get('violations'), **{
            k: a.get(k) for k in ('status', 'runs_audited', 'runs_withheld', 'runs_error', 'runs_without_log',
                                  'runs_matching_no_job', 'offers', 'accepted', 'events_only_commits',
                                  'margin_unrecorded', 'log_mismatches')}})
        violating += [{'source': s['path'], **{k: r.get(k) for k in ('run_dir', 'jobs', 'status', 'n_violations',
                                                                      'violations', 'examples')}}
                      for r in runs if (V2.inum(r.get('n_violations')) or 0) > 0]
        unaudited += [{'source': s['path'], **{k: r.get(k) for k in ('run_dir', 'jobs', 'status', 'error')}}
                      for r in runs if r.get('status') == 'ERROR']
        for r in runs:
            if r.get('status') == 'NO_LOG':
                entry, counts = no_log_run(r, s.get('rows') or [])
                no_log.append({'source': s['path'], **entry, 'unaudited': counts})
                if counts:
                    unaudited.append({'source': s['path'], **{k: entry[k] for k in ('run_dir', 'jobs', 'status',
                                                                                     'error')}})
        if a.get('runs_withheld'):
            undetermined.append(f'{s["path"]}: {a["runs_withheld"]} runs withheld by the interim-look guard (Sec. '
                                '9.11: H5 is judged after the analysis freeze)')
    n_audit = sum(sum((V2.inum(v) or 0) for v in (x.get('violations') or {}).values()) for x in audits)
    missing = [p for p in H5_PHASES if p not in phases]
    if audits and missing:
        undetermined.append(f'phases without audited runs in the input: {missing}')
    if not audits and not undetermined:
        undetermined.append('no aggregation input (no commit audit)')
    if s3 is None:
        undetermined.append('no S3 report given (--s3)')
    elif not s3['registered']:
        undetermined.append(f'{s3["path"]}: not the registered S3 ({s3["label"]}; {s3["n_sequences"]} sequences, '
                            f'targets {s3["targets"]})')
    n_s3 = s3['violations_total'] if s3 is not None and s3['registered'] else 0    # a development S3 is reported only
    if n_audit or n_s3:
        label = 'contradicted'
    elif undetermined:
        label = 'undetermined'
    elif unaudited:
        label = 'contradicted'
    else:
        label = 'supported'
    return {'question': 'H5: no committed action violates Eq. 9 (commit audit of every run of every phase; S3)',
            'rule': 'supported if the commit audit finds 0 commits violating Eq. 9 in every run of every phase and '
                    'stress test S3 finds 0 violations; contradicted otherwise, with every violation listed (Sec. 9.5)',
            'label': label, 'commit_audit_violations': n_audit, 's3_violations': n_s3, 'violating_runs': violating,
            'unaudited_runs': unaudited, 'no_log_runs': no_log, 'undetermined_because': undetermined,
            'phases_required': list(H5_PHASES),
            'phases_covered': sorted(phases), 'phases_missing': missing, 'audits': audits, 's3': s3}


def _dist(values):
    v = [x for x in values if x is not None]
    return {'runs': len(v), 'mean': float(np.mean(v)) if v else None, 'median': float(np.median(v)) if v else None,
            'max': float(max(v)) if v else None}


def used_rows(cells, conds, cond):
    """The used rows of one condition on its routes (conds: analysis_conditions), in route order."""
    return [c['row'] for c in (get_cell(cells, cond, r) for r in conds[cond]) if c['status'] == 'used']


def _reasons(values):
    """The sum of per-run {reason: count} JSON objects (runs.csv gate_rejects_by_reason / bypass_by_reason); a value
    that is empty or not such an object is skipped."""
    out = {}
    for v in values:
        if isinstance(v, str) and v.strip():
            try:
                v = json.loads(v)
            except ValueError:
                continue
        if isinstance(v, dict):
            for k, n in v.items():
                out[str(k)] = out.get(str(k), 0) + (V2.inum(n) or 0)
    return dict(sorted(out.items()))


def _count(values):
    v = [x for x in values if x is not None]
    return {'total': int(sum(v)), 'runs_with_any': sum(1 for x in v if x)}


# Sec. 7.6 panel B, per-run distributions (runs.csv columns: the per-run p50 / p99 of the logs, aggregate_v4)
OVERHEAD_DIST = ('qnet_s_p50', 'decision_wall_s_p50', 'decision_wall_s_p99', 'lease_wall_s_p50', 'lease_wall_s_p99',
                 'prefix_quantum_s_p50', 'prefix_quantum_s_p99', 'step_quantum_s_p50', 'step_quantum_s_p99',
                 'switching_latency_s_p50', 'switching_latency_s_p99', 'cancelled_gpu_share', 'validation_s_p50',
                 'validation_s_p99', 'bypass_rate', 'budget_overrun_ratio', 'dmr')


def overhead(cells, conds):
    """Sec. 9.5 'reported as measured' and the log quantities of Sec. 7.6 panel B, per condition over its used runs
    (the kappa-1.0 Table I runs of every shield arm and the kappa-2.0 Fig. 3 runs are among the conditions): the
    per-run Q-network p99 against B_pi (runs above B_pi = 100 us) and the distribution over runs (runs, mean, median,
    max) of every per-run value of OVERHEAD_DIST (Q-network p50; shield decision and lease p50 / p99, decision_wall_s
    and lease_wall_s; charged prefix and flow-step quanta p50 / p99; switching latency p50 / p99; cancelled-GPU share;
    release-to-commit validation p50 / p99; bypass rate; budget-overrun ratio; DMR), and the totals with the runs that
    have any of: bypass epochs (with the reasons), commit-gate rejects (with the reasons), cancelled GPU seconds,
    fallback episodes, budget overruns and shield violations. A per-run p50 / p99 is not pooled across runs (the logs'
    samples are not in runs.csv). Conditions without a used run are left out. Table II-B itself, with the stress tests
    S1-S4, is rendered by the figures and tables script (GAP_AUDIT R-6)."""
    out = {}
    for cond in conds:
        rows = used_rows(cells, conds, cond)
        if not rows:
            continue

        def col(name):
            return [V2.fnum(r.get(name)) for r in rows]

        q99 = [v for v in col('qnet_s_p99') if v is not None]
        out[cond.name] = {
            'runs': len(rows),
            'qnet_s_p99': {**_dist(q99), 'b_pi_s': B_PI_S, 'runs_above_b_pi': sum(1 for v in q99 if v > B_PI_S)},
            **{k: _dist(col(k)) for k in OVERHEAD_DIST},
            'budget_overruns': _count(col('budget_overruns')), 'shield_violations': _count(col('shield_violations')),
            'fallback_episodes': _count(col('fallback_episodes')),
            'bypass_epochs': {**_count(col('bypass_epochs')), 'by_reason': _reasons(r.get('bypass_by_reason')
                                                                                     for r in rows)},
            'gate_rejects': {**_count(col('gate_rejects')), 'by_reason': _reasons(r.get('gate_rejects_by_reason')
                                                                                  for r in rows)},
            'cancelled_gpu_s': {'total': float(sum(v for v in col('cancelled_gpu_s') if v is not None)),
                                'runs_with_any': sum(1 for v in col('cancelled_gpu_s') if v)}}
    return out


MANIP_NUM = ('prefix_p50_per_kappa_s', 'predicted_expiry_fallback', 'observed_expiry_fallback', 'expiry_fallback_dev',
             'bg_load_excess_s', 'p_both')
MANIP_TEXT = ('job', 'protocol_arm', 'route_id', 'outcome', 'selected_run', 'run_created_utc', 'fast_prefix_check',
              'fast_prefix_detail', 'charged_prefix_check', 'bg_load_status', 'config_check', 'config_detail',
              'job_release_by_depth')


def manipulation_row(row):
    """A runs.csv row typed as manipulation.py reads the aggregator's rows: numbers (MANIP_NUM) as float or None,
    shield_epochs as int, expiry_fallback_flag as bool, text (MANIP_TEXT) with '' as None; kappa, seed, analysis_use
    and health_only as parse_row typed them."""
    out = {k: (str(row.get(k)).strip() or None) if row.get(k) is not None else None for k in MANIP_TEXT}
    out.update({k: V2.fnum(row.get(k)) for k in MANIP_NUM})
    out.update(kappa=row['kappa'], seed=row['seed'], analysis_use=row['analysis_use'], health_only=row['health_only'],
               shield_epochs=V2.inum(row.get('shield_epochs')),
               expiry_fallback_flag=flag(row.get('expiry_fallback_flag'), 'expiry_fallback_flag'))
    return out


def manipulation(sources, cells, conds):
    """Sec. 9.7 (reported, not tested; no run excluded) and Amendment A8: the aggregator's R-3 document of every
    aggregation (manipulation_checks: every run it read), the same summary (manipulation.manipulation_summary) over
    the runs this analysis uses, and per condition the fast-prefix, charged-prefix, background-load and configuration
    counts, the prefix p50 / kappa range and the predicted-expiry flags (manipulation.per_arm_health)."""
    seen, typed, by = set(), [], {}
    for cond in conds:
        rows = []
        for r in used_rows(cells, conds, cond):
            t = manipulation_row(r)
            rows.append(t)
            if r['job'] not in seen:
                seen.add(r['job'])
                typed.append(t)
        if rows:
            health = MC.per_arm_health(rows)
            by[cond.name] = {**next(iter(health.values())),
                             'expiry_fallback_flags': sum(1 for t in rows if t['expiry_fallback_flag'])}
    return {'status': 'reported (PROTOCOL Sec. 9.7: not tested, no run excluded; background-load flag: Amendment A8)',
            'analysed_runs': MC.manipulation_summary(typed), 'by_condition': by,
            'aggregations': {s['path']: s.get('manipulation_checks') for s in sources if s['kind'] == 'aggregation'}}


def missing_data(sources, tables):
    """Sec. 9.8: per row of every table (contrast x metric) n_expected, n_complete (both cells used), n (both values
    present) and the dropped routes counted by reason; the aggregator's missing-reason counts of every aggregation.
    Nothing is imputed."""
    rows = []
    for name, rs in tables.items():
        for r in rs:
            reasons = {}
            for x in r['dropped']:
                reasons[x['reason']] = reasons.get(x['reason'], 0) + 1
            rows.append({'table': name, 'contrast': r['contrast'], 'metric': r['metric'], 'n_expected': r['n_expected'],
                         'n_complete': r['n_complete'], 'n': r['n'], 'n_dropped': len(r['dropped']),
                         'reasons': reasons})
    return {'rule': 'pairwise-complete routes per contrast and metric; nothing is imputed; the n of every contrast and '
                    'the dropped routes are reported (Sec. 9.8)',
            'rows_complete': sum(1 for x in rows if not x['n_dropped']), 'rows_incomplete': [x for x in rows
                                                                                           if x['n_dropped']],
            'aggregations': {s['path']: s.get('missing_reasons') for s in sources if s['kind'] == 'aggregation'}}


# ====================================================================================== decisions (Secs. 9.2, 9.13)

def load_p_both(path, allow_dev=False):
    """The Sec. 5.8 P_both label of an RL freeze (p3_rl.py rl_freeze.json; read as JSON): {'path', 'sha256', 'p_both',
    'label', 'kappa', 'threshold', 'decision_epochs', 'choice_epochs', 'n_episodes', 'frozen'}. AnalysisError for
    another schema, a record without its p_both entry, or a development record (frozen not true) unless allow_dev."""
    path = Path(path)
    try:
        doc = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        raise AnalysisError(f'{PJ.rel(path)}: cannot read the RL freeze ({e})') from None
    if not isinstance(doc, dict) or doc.get('schema') != RL_FREEZE_SCHEMA:
        raise AnalysisError(f'{PJ.rel(path)}: not an RL freeze (schema {RL_FREEZE_SCHEMA})')
    if doc.get('frozen') is not True and not allow_dev:
        raise AnalysisError(f'{PJ.rel(path)}: a {doc.get("mode")} record (frozen {doc.get("frozen")}) is not a freeze')
    pb = doc.get('p_both')
    if not isinstance(pb, dict) or 'label' not in pb:
        raise AnalysisError(f'{PJ.rel(path)}: no P_both label (Sec. 5.8)')
    return {'path': PJ.rel(path), 'sha256': PJ.sha256_file(path), 'frozen': doc.get('frozen') is True,
            **{k: pb.get(k) for k in ('p_both', 'label', 'kappa', 'threshold', 'decision_epochs', 'choice_epochs',
                                      'n_episodes')}}


def _brief(row):
    keys = ('contrast', 'metric', 'n', 'n_expected', 'mean', 'ci95', 'p_two_sided', 'p_adjusted', 'label')
    return {k: row.get(k) for k in keys}


def finding(rows):
    """Sec. 9.2: a finding may be stated only if each of its contrasts is 'improves'; differing labels are 'mixed'."""
    labels = [r['label'] for r in rows]
    if all(x == 'improves' for x in labels):
        return 'may be stated'
    if len(set(labels)) > 1:
        return 'mixed (not stated): ' + ', '.join(f'{r["b_arm"]} {r["label"]}' for r in rows)
    return f'not stated: both {labels[0]}'


def mark_p_both(families, p_both):
    """Sec. 5.8: H2 is computed and reported with the P_both label of the RL freeze; its row carries the label in
    'note' (nothing when no RL freeze is given)."""
    if p_both is None:
        return
    for f in families:
        if f['name'] == 'H2':
            for r in f['rows']:
                r['note'] = f'P_both label (Sec. 5.8): {p_both.get("label")}'


def decide(families, secondary, p_both=None, h4=None, h5_doc=None):
    """The registered decisions: H1 (Sec. 9.2) with findings 1 and 2, finding 2 shown with the descriptive GPU-usage
    contrasts; H2 with the Sec. 5.8 P_both label and the RL-benefit rule of Sec. 9.13; every family's labels; the H4
    offline label (Sec. 9.4; h4: h4_offline's document, None when not computed) and the H5 label (Sec. 9.5; h5_doc)."""
    fam = {f['name']: f for f in families}
    h1 = {r['b_arm']: r for r in fam['H1']['rows']}
    gpu = [_brief(r) for r in secondary if r['metric'] == 'gpu_usage' and r['a_arm'] == 'fl_full'
           and r['b_arm'] in ('age_only', 'event_triggered') and 'H1' in r['families']]
    out = {'H1': {
        'question': FAMILY_BY_NAME['H1'].question,
        'contrasts': [_brief(h1[b]) for b in H1_OTHERS],
        'finding_1': {'text': 'improves over fixed-depth and fixed-refresh methods (outline IV-A finding 1)',
                      'contrasts': ['fixed_deep', 'fast_only'],
                      'statement': finding([h1['fixed_deep'], h1['fast_only']])},
        'finding_2': {'text': 'action-aware scheduling uses compute better than Age-Only and Event-Triggered '
                              '(outline IV-A finding 2)', 'contrasts': ['age_only', 'event_triggered'],
                      'statement': finding([h1['age_only'], h1['event_triggered']]),
                      'gpu_usage_descriptive': gpu},
        'rule': 'each contrast: improves if the mean DS difference is > 0 with Holm-adjusted p < 0.05 (Holm over 4), '
                'worse if < 0 with Holm-adjusted p < 0.05, otherwise inconclusive; finding 1 may be stated only if '
                'contrasts 1 and 2 are both improves, finding 2 only if contrasts 3 and 4 are both improves; mixed '
                'outcomes are reported as mixed (Sec. 9.2)'}}
    h2 = fam['H2']['rows'][0]
    pb_label = None if p_both is None else p_both.get('label')
    if pb_label is None:
        rl = 'undetermined: no RL freeze given (the Sec. 5.8 P_both label)'
    elif pb_label == P_BOTH_NOT_TESTABLE:
        rl = P_BOTH_NOT_TESTABLE
    elif pb_label != 'testable':
        rl = f'undetermined: P_both label {pb_label!r}'
    else:
        rl = 'claimed' if h2['label'] == 'improves' else f'not claimed (H2 {h2["label"]})'
    out['H2'] = {'question': FAMILY_BY_NAME['H2'].question, 'contrast': _brief(h2), 'p_both': p_both,
                 'p_both_label': pb_label, 'rl_benefit': rl,
                 'rule': 'the RL benefit is claimed only if H2 is improves; with P_both < 0.05 in the kappa-1.0 '
                         'episodes of the RL dataset the RL contribution is labelled "not testable at this operating '
                         'point" and H2 is reported with that label (Secs. 5.8, 9.13)'}
    out['labels'] = {f['name']: {r['contrast']: r['label'] for r in f['rows']} for f in families}
    out['H4_offline'] = ({'label': 'not computed', 'reason': 'no offline outputs given'} if h4 is None else
                         {'label': h4['label'], 'status': h4['status'], 'rule': h4['rule'],
                          'primary': {k: h4['primary'][k] for k in ('a', 'b', 'alpha', 'metric', 'diff', 'lo', 'hi',
                                                                    'r_cond_diff', 'r_cond_lo', 'r_cond_hi')},
                          'secondary': {f'{r["a"]} - {r["b"]}, R_cond <= {r["alpha"]:.0%}, {r["metric"]}': r['label']
                                        for r in h4['rows'] if r['role'] == 'secondary'}})
    if h5_doc is not None:
        out['H5'] = {k: h5_doc[k] for k in ('label', 'rule', 'commit_audit_violations', 's3_violations',
                                            'undetermined_because', 'phases_missing')} | {
            'unaudited_runs': len(h5_doc['unaudited_runs']), 'violating_runs': len(h5_doc['violating_runs']),
            'no_log_runs': len(h5_doc['no_log_runs'])}
    return out


# ============================================================================================ the analysis

def needed_cells(cells, table, conds=None):
    """The cell rows (cells.csv) of every condition the family and descriptive contrasts use (conds:
    analysis_conditions), on the routes of the subsets it is used on, in condition and route order."""
    conds = analysis_conditions(table) if conds is None else conds
    out = []
    for cond, routes in conds.items():
        for rid in routes:
            cell = get_cell(cells, cond, rid)
            row = cell['row'] or {}
            out.append({'condition': cond.name, 'arm': cond.arm, 'kappa': cond.kappa, 'seed': cond.seed,
                        'route_id': rid, 'route_index': table['meta'][rid]['index'],
                        'scenario_type': table['meta'][rid]['scenario_type'], 'status': cell['status'],
                        'jobs': cell['jobs'], 'reasons': cell['reasons'], 'phase': row.get('phase'),
                        'block': row.get('block'), 'guard': G.note_category(row.get('guard_note'))})
    return out


def cell_summary(cell_rows):
    """{condition: {'routes', 'status': {status: count}, 'not_used': [{'route_id', 'status', 'reasons'}]}}."""
    out = {}
    for r in cell_rows:
        s = out.setdefault(r['condition'], {'routes': 0, 'status': {}, 'not_used': []})
        s['routes'] += 1
        s['status'][r['status']] = s['status'].get(r['status'], 0) + 1
        if r['status'] != 'used':
            s['not_used'].append({'route_id': r['route_id'], 'status': r['status'], 'reasons': r['reasons']})
    return out


# the Table I columns (Sec. 7.2; RC and R_cond for the notes) and the closed-loop Table II-A columns (Secs. 7.4, 7.5)
SUMMARY_METRICS = SECONDARY_METRICS + ('lease_utilization', 'premature_expiry_ratio', 'deviation_rate', 'bypass_rate')


def per_scenario(cells, table, ability_of, conds):
    """Sec. 9.9 (descriptive, no per-scenario test): one row per route and condition (conds: analysis_conditions; a
    condition on the routes it is used on), sorted by scenario type and condition order; the cell status, the used
    job and the SUMMARY_METRICS values (one route per scenario type in the registered split)."""
    out = []
    order = {cond: i for i, cond in enumerate(conds)}
    for rid in sorted(table['routes'], key=lambda r: (str(table['meta'][r]['scenario_type']),
                                                      table['meta'][r]['index'])):
        meta = table['meta'][rid]
        for cond in sorted((c for c in conds if rid in conds[c]), key=order.get):
            cell = get_cell(cells, cond, rid)
            row = cell['row'] if cell['status'] == 'used' else {}
            out.append({'scenario_type': meta['scenario_type'], 'route_id': rid, 'route_index': meta['index'],
                        'town': meta.get('town'), 'abilities': '|'.join(ability_of.get(rid, ())),
                        'subsets': '|'.join(s for s in ('E', 'C', 'R') if rid in table['subsets'][s]),
                        'condition': cond.name, 'arm': cond.arm, 'kappa': cond.kappa, 'seed': cond.seed,
                        'status': cell['status'], 'job': row.get('job'),
                        **{k: V2.fnum(row.get(METRICS[k].column)) for k in SUMMARY_METRICS}})
    return out


def condition_subsets():
    """{condition: [subsets in 'all', 'E', 'C', 'R' order]} of the family and descriptive contrasts that use it."""
    want = {}
    for c in list(family_contrasts()) + [d.contrast for d in DESCRIPTIVE_CONTRASTS]:
        for cond in (c.a, c.b):
            want.setdefault(cond, set()).add(c.subset)
    return {cond: [s for s in SUBSET_TEST if s in subs] for cond, subs in want.items()}


POOLED_COLLISIONS = 'collisions_per_km_pooled'     # the Sec. 6.1 arm-level collisions/km (conditions.csv metric)
KM_FLOOR = 0.001                                    # Sec. 6.1: km driven has a floor of 0.001 km (leaderboard)
STAT_ROUTE_MEAN = 'route_mean'                      # conditions.csv 'statistic': the mean of route-level values
STAT_POOLED = 'pooled_ratio'                        # conditions.csv 'statistic': sum of numerators / sum of km


def pooled_ratio(num, den, settings=REGISTERED, level=0.95):
    """(sum(num) / sum(den), [lo, hi]) with the route-cluster percentile bootstrap of Sec. 6.1: the routes are resampled
    with replacement (settings.n_boot resamples of n route indices, rng.integers from a fresh
    numpy.random.default_rng(settings.boot_seed), the draws of bootstrap_ci), the ratio of sums is taken per resample,
    and the (1 - level) / 2 and 1 - (1 - level) / 2 quantiles bound it. (None, None) without routes; den must be > 0
    per route (the km floor)."""
    num, den = np.asarray(num, dtype=float).ravel(), np.asarray(den, dtype=float).ravel()
    if num.size == 0:
        return None, None
    if num.size != den.size or not np.all(den > 0):
        raise ValueError('pooled_ratio: one positive denominator per route is needed')
    rng = np.random.default_rng(settings.boot_seed)
    idx = rng.integers(0, num.size, size=(settings.n_boot, num.size))
    ratios = num[idx].sum(axis=1) / den[idx].sum(axis=1)
    lo, hi = np.quantile(ratios, [(1.0 - level) / 2.0, 1.0 - (1.0 - level) / 2.0])
    return float(num.sum() / den.sum()), [float(lo), float(hi)]


def pooled_collisions_row(rows, settings=REGISTERED):
    """The Sec. 6.1 arm-level collisions/km of the used rows of one condition and subset: sum of collisions_total /
    sum of km_driven with the floor of KM_FLOOR km per route, over the routes where both values exist, with its 95%
    route-cluster bootstrap interval (pooled_ratio). {'n', 'mean' (the pooled value), 'ci95', 'numerator_sum',
    'denominator_sum'}."""
    pairs = [(V2.fnum(r.get('collisions_total')), V2.fnum(r.get('km_driven'))) for r in rows]
    pairs = [(c, max(km, KM_FLOOR)) for c, km in pairs if c is not None and km is not None]
    value, ci = pooled_ratio([c for c, _ in pairs], [km for _, km in pairs], settings)
    return {'n': len(pairs), 'mean': value, 'ci95': ci,
            'numerator_sum': float(sum(c for c, _ in pairs)) if pairs else None,
            'denominator_sum': float(sum(km for _, km in pairs)) if pairs else None}


def condition_summary(cells, table, settings=REGISTERED):
    """The per-condition columns of Table I, Fig. 3 and Table II-A (descriptive): for every condition and every subset
    it is used on, and every SUMMARY_METRICS metric, the n of used runs with a value, the mean over routes with its 95%
    percentile bootstrap interval over routes (bootstrap_ci, settings, a fresh generator per condition, subset and
    metric), SD, median, min and max (statistic 'route_mean'). Collisions/km has a second row right after its route
    mean (Sec. 6.1: 'Route-level values are used for paired contrasts' and 'The arm-level value is pooled (sum of
    collisions / sum of km), with a route-cluster bootstrap CI'): metric 'collisions_per_km_pooled', statistic
    'pooled_ratio', the pooled value in 'mean' with its route-cluster interval (pooled_collisions_row) and the two
    sums."""
    out = []
    for cond, subsets in condition_subsets().items():
        for s in subsets:
            routes = table['subsets'][s]
            rows = [c['row'] for c in (get_cell(cells, cond, r) for r in routes) if c['status'] == 'used']
            head = {'condition': cond.name, 'arm': cond.arm, 'kappa': cond.kappa, 'seed': cond.seed, 'subset': s,
                    'n_routes': len(routes), 'n_used': len(rows)}
            for k in SUMMARY_METRICS:
                v = np.array([x for x in (V2.fnum(r.get(METRICS[k].column)) for r in rows) if x is not None], float)
                ci = bootstrap_ci(v, settings.n_boot, settings.boot_seed, levels=(0.95,))['ci95']
                out.append({**head, 'metric': k, 'statistic': STAT_ROUTE_MEAN, 'column': METRICS[k].column,
                            'n': len(v), 'mean': float(v.mean()) if len(v) else None,
                            'ci95': ci, 'sd': float(v.std(ddof=1)) if len(v) > 1 else None,
                            'median': float(np.median(v)) if len(v) else None,
                            'min': float(v.min()) if len(v) else None, 'max': float(v.max()) if len(v) else None})
                if k == 'collisions_per_km':
                    out.append({**head, 'metric': POOLED_COLLISIONS, 'statistic': STAT_POOLED,
                                'column': 'collisions_total / km_driven', **pooled_collisions_row(rows, settings)})
    return out


ANALYSIS_REL = 'outputs/framelease_v4/analysis'     # Sec. 9.12: outputs go to <ANALYSIS_REL>/final_<stamp>/


def out_location(out):
    """None when out (as written: relative to the working directory) is outputs/framelease_v4/analysis/final_<stamp>/
    or a directory inside it (Sec. 9.12; the aggregation of the analysis freeze occupies final_<stamp>/ itself, so the
    analysis goes into a directory inside it, e.g. final_<stamp>/analysis/); else the development reason."""
    if out is None:
        return f'no output directory given (the analysis was not written to {ANALYSIS_REL}/final_<stamp>/, Sec. 9.12)'
    p = Path(out).resolve()
    base = (ROOT / ANALYSIS_REL).resolve()
    parts = p.relative_to(base).parts if p.is_relative_to(base) else ()
    if parts and parts[0].startswith('final_') and len(parts[0]) > len('final_'):
        return None
    return f'output directory {PJ.rel(p)} is not inside {ANALYSIS_REL}/final_<stamp>/ (Sec. 9.12)'


def development_reasons(sources, table, settings, freeze, p_both, offline, s3, decisions, out):
    """[reasons] why a run is 'development' and not 'registered' (empty: registered). 'registered' needs the registered
    route table and settings, aggregations only, a registered analysis-freeze record checked against the registered
    tier 3-6 job files (--required-job-files, Sec. 8.1), a frozen RL freeze with a decisive P_both label (the H2 RL
    benefit, Secs. 5.8, 9.13), the registered offline outputs (H4, Sec. 9.4), the registered S3 run and a determined
    H5 (Sec. 9.5 has only supported / contradicted), and the Sec. 9.12 output location (out_location)."""
    dev = []
    if not table['registered']:
        dev.append(f'route table {table["source"]} is not the registered split')
    dev += [f'{s["path"]}: a bare CSV (synthetic development data)' for s in sources if s['kind'] != 'aggregation']
    if not settings.registered:
        dev.append(f'settings {settings} differ from the registered {REGISTERED}')
    if freeze is None:
        dev.append('no analysis-freeze record: a pre-freeze run, no test-route row was read (Sec. 9.11)')
    elif not freeze.get('registered'):
        dev.append('a development analysis-freeze record (cited by a development copy of PROTOCOL.md)')
    if freeze is not None and not freeze.get('required_job_files'):
        dev.append('the analysis-freeze record was not checked against the registered tier 3-6 job files of the test '
                   'freeze (--required-job-files, Sec. 8.1)')
    if p_both is None:
        dev.append('no RL freeze (--rl-freeze): no Sec. 5.8 P_both label, the H2 RL benefit is undetermined '
                   '(Sec. 9.13)')
    elif not p_both.get('frozen'):
        dev.append(f'{p_both["path"]}: a development RL record (frozen not true), not the RL freeze')
    rl = decisions['H2']['rl_benefit']
    if p_both is not None and rl.startswith('undetermined'):
        dev.append(f'H2 RL benefit {rl} (Secs. 5.8, 9.13)')
    if offline is None:
        dev.append('no offline outputs: H4 offline not computed (Sec. 9.4)')
    elif not offline['registered_location']:
        dev.append(f'offline outputs from {offline["path"]}, not {OFFLINE_REL}')
    if s3 is None:
        dev.append('no S3 report: H5 not judged (Sec. 9.5)')
    elif not s3['registered']:
        dev.append(f'{s3["path"]}: not the registered S3 run')
    h5d = decisions.get('H5') or {}
    if h5d.get('label') == 'undetermined':
        dev.append("H5 'undetermined', which is not a registered label (Sec. 9.5: supported / contradicted): "
                   + '; '.join(h5d.get('undetermined_because') or ()))
    where = out_location(out)
    if where:
        dev.append(where)
    return dev


def analyze(sources, table=None, settings=REGISTERED, freeze=None, test_routes=None, registered=None, p_both=None,
            offline=None, s3=None, out=None):
    """(analysis document, {file name: rows}) of the input sources (load_aggregation / load_csv_source): the v2 module
    check, the route table (default the registered one), the Sec. 9.11 guard (guard_rows), the cells, the families, the
    secondary rows, the descriptive contrasts (replicates and noise floor, RL gain, per ability and per scenario,
    condition summaries), the sensitivity, H4 offline (offline: load_offline), H5 (the aggregations' commit audits and
    s3: load_s3), the overhead, the manipulation checks, the missing data and the decisions. GuardRefused /
    AnalysisError as the steps raise them; nothing is written here (out: the directory main writes to, for the Sec.
    9.12 location check only, out_location).
    The guard is never narrower through this API than on the command line: freeze is verified again from its files
    (aggregate_v4.checked_freeze: a hand-made dictionary is refused), the code citation is always computed here,
    test_routes only ADDS routes to the registered split (interim_guard.test_routes: 'a caller may add routes, never
    remove one') and registered only adds routes to the registered test routes that interim_guard.summary_rows
    protects under a development record."""
    v2_sha = check_v2()
    check_sources(sources)
    table = route_table() if table is None else table
    freeze = A.checked_freeze(freeze)
    split = G.registered_split()
    test_routes, routes_info = G.test_routes(extra=test_routes or (), split=split)
    registered = set(split['test']) | {str(r) for r in (registered or ())}
    if p_both is not None:
        other = sorted({s['rl_sha256'] for s in sources if s.get('rl_sha256')} - {p_both['sha256']})
        if other:
            raise AnalysisError(f'the aggregations were made with the RL freeze {other}, not {p_both["path"]} '
                                f'({p_both["sha256"]})')
    use, guard = guard_rows(sources, freeze, test_routes, registered)
    guard['test_routes'] = routes_info
    rows = [r for s in sources for r in s['rows']]
    cells = build_cells(rows, use, table)
    families, route_rows = [], []
    for f in FAMILIES:
        fdoc, rr = run_family(f, cells, table, settings)
        families.append(fdoc)
        route_rows += rr
    mark_p_both(families, p_both)
    secondary, rr = run_secondary(cells, table, settings)
    route_rows += rr
    desc, rr = run_descriptive(cells, table, settings)
    route_rows += rr
    conds = analysis_conditions(table)
    cell_rows = needed_cells(cells, table, conds)
    ability_of = route_abilities(table)
    abil = per_ability([r for f in families for r in f['rows']] + desc, route_rows, ability_of, table, settings)
    h4_doc, h4_rows = h4_offline(offline) if offline is not None else (None, [])
    h5_doc = h5(sources, s3)
    decisions = decide(families, secondary, p_both, h4_doc, h5_doc)
    cond_rows = condition_summary(cells, table, settings)
    dev = development_reasons(sources, table, settings, freeze, p_both, offline, s3, decisions, out)
    inputs = {k: v for s in sources for k, v in s['files'].items()}
    inputs.update((offline or {}).get('files') or {})
    if s3 is not None:
        inputs[s3['path']] = s3['sha256']
    inputs[V2_REL] = v2_sha
    if table.get('sha256'):
        inputs[table['source']] = table['sha256']
        inputs[table['manifest']] = table['manifest_sha256']
    inputs[routes_info['path']] = routes_info['sha256']
    if freeze is not None:
        inputs.update({freeze['path']: freeze['sha256'], freeze['protocol']: freeze['protocol_sha256']})
        if freeze.get('seal'):
            inputs[freeze['seal']] = PJ.sha256_file(ROOT / freeze['seal'])
    if p_both is not None:
        inputs[p_both['path']] = p_both['sha256']
    doc = {'schema': SCHEMA, 'script': THIS_REL, 'script_sha256': PJ.sha256_file(Path(__file__)),
           'created': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
           'v2_module': {'path': V2_REL, 'sha256': v2_sha, 'registered_sha256': V2_SHA256,
                         'functions': ['sign_flip_test', 'bootstrap_ci', 'holm', 'label_directional']},
           'settings': {'n_boot': settings.n_boot, 'boot_seed': settings.boot_seed, 'mc_flips': settings.mc_flips,
                        'mc_seed': settings.mc_seed, 'enum_max_n': ENUM_MAX_N, 'alpha': ALPHA,
                        'registered': settings.registered, 'labels': LABELS},
           'development': dev, 'status': 'development' if dev else 'registered',
           'scope': ('test routes, released by the analysis-freeze record' if guard['test_input_rows'] else
                     'no test-route row (synthetic or training-route input)'),
           'sources': [{k: s.get(k) for k in ('kind', 'path', 'files', 'guard_status', 'freeze_sha256', 'rl_sha256',
                                              'created', 'script_sha256', 'absent_columns')} | {'rows': len(s['rows'])}
                       for s in sources],
           'route_table': {k: table.get(k) for k in ('source', 'registered', 'sha256', 'subset_sizes')} | {
               'subset_rules': SUBSET_RULES, 'subsets': table['subsets']},
           'interim_guard': guard, 'cell_status': CELL_STATUS, 'cells': cell_summary(cell_rows),
           'outside_rows': outside_rows(rows, table), 'families': families, 'secondary': secondary,
           'descriptive': desc, 'replicates': replicates(desc), 'rl_gain': rl_gain(families, desc, abil),
           'per_ability': abil, 'sensitivity': sensitivity(families),
           'collisions_per_km_pooled': [{k: r[k] for k in ('condition', 'subset', 'n', 'mean', 'ci95', 'numerator_sum',
                                                           'denominator_sum')}
                                        for r in cond_rows if r['metric'] == POOLED_COLLISIONS],
           'h4_offline': h4_doc or {'label': 'not computed', 'reason': 'no offline outputs given'}, 'h5': h5_doc,
           'overhead': overhead(cells, conds), 'manipulation': manipulation(sources, cells, conds),
           'missing_data': missing_data(sources, {**{f'family_{f["name"]}': f['rows'] for f in families},
                                                  'secondary': secondary, 'descriptive': desc}),
           'decisions': decisions, 'inputs': dict(sorted(inputs.items()))}
    tables = {f'family_{f["name"]}.csv': [csv_row(r) for r in f['rows']] for f in families}
    tables['secondary.csv'] = [csv_row(r) for r in secondary]
    tables['descriptive.csv'] = [csv_row(r, DESCRIPTIVE_COLUMNS) for r in desc]
    tables['paired_differences.csv'] = route_rows
    tables['cells.csv'] = cell_rows
    tables['per_ability.csv'] = [csv_row(r, ABILITY_COLUMNS) for r in abil]
    tables['per_scenario.csv'] = per_scenario(cells, table, ability_of, conds)
    tables['conditions.csv'] = [csv_row(r, CONDITION_COLUMNS) for r in cond_rows]
    tables['h4_offline.csv'] = h4_rows
    return doc, tables


# ============================================================================================ outputs

ROW_COLUMNS = ('family', 'families', 'role', 'contrast', 'a', 'b', 'kappa', 'seed', 'subset', 'metric', 'column',
               'better', 'n_expected', 'n_complete', 'n', 'mean', 'mean_a', 'mean_b', 'ci95_lo', 'ci95_hi', 'ci90_lo',
               'ci90_hi', 'p_two_sided', 'p_method', 'correction', 'family_size', 'p_adjusted', 'label', 'sd', 'median',
               'min', 'max', 'n_positive', 'n_negative', 'n_zero', 'n_nonzero', 'min_attainable_p', 'dp_grid',
               'dp_grid_registered', 'dp_max_statistic_change', 'p_mc', 'mc_flips', 'mc_seed', 'mc_se', 'note',
               'dropped_routes')
ROUTE_COLUMNS = ('table', 'contrast', 'metric', 'route_id', 'route_index', 'scenario_type', 'value_a', 'value_b',
                 'difference', 'status')
CELL_COLUMNS = ('condition', 'arm', 'kappa', 'seed', 'route_id', 'route_index', 'scenario_type', 'status', 'jobs',
                'reasons', 'phase', 'block', 'guard')
DESCRIPTIVE_COLUMNS = ('group', 'section', 'role', 'contrast', 'a', 'b', 'kappa', 'seed', 'subset', 'metric', 'column',
                       'better', 'n_expected', 'n_complete', 'n', 'mean', 'mean_a', 'mean_b', 'ci95_lo', 'ci95_hi',
                       'ci90_lo', 'ci90_hi', 'p_two_sided', 'p_method', 'correction', 'label', 'sd', 'median', 'min',
                       'max', 'n_positive', 'n_negative', 'n_zero', 'mean_abs_diff', 'mean_abs_diff_ci95_lo',
                       'mean_abs_diff_ci95_hi', 'median_abs_diff', 'max_abs_diff', 'pearson_r_a_b', 'note',
                       'dropped_routes')
ABILITY_COLUMNS = ('contrast', 'a', 'b', 'subset', 'metric', 'family', 'group', 'ability', 'n_routes', 'n', 'mean',
                   'mean_a', 'mean_b', 'ci95_lo', 'ci95_hi', 'n_positive', 'n_negative', 'n_zero', 'routes',
                   'scenario_types')
SCENARIO_COLUMNS = ('scenario_type', 'route_id', 'route_index', 'town', 'abilities', 'subsets', 'condition', 'arm',
                    'kappa', 'seed', 'status', 'job') + SUMMARY_METRICS
CONDITION_COLUMNS = ('condition', 'arm', 'kappa', 'seed', 'subset', 'n_routes', 'n_used', 'metric', 'statistic',
                     'column', 'n', 'mean', 'ci95_lo', 'ci95_hi', 'sd', 'median', 'min', 'max', 'numerator_sum',
                     'denominator_sum')
H4_COLUMNS = ('role', 'variation', 'a', 'b', 'protocol', 'subset', 'need', 'need_s', 'alpha', 'metric', 'better',
              'a_value', 'b_value', 'diff', 'lo', 'hi', 'source', 'missing', 'r_cond_diff', 'r_cond_lo', 'r_cond_hi',
              'r_cond_missing', 'label')


def csv_row(row, columns=ROW_COLUMNS):
    """A result row as a CSV row with the given columns (ROW_COLUMNS: family and secondary rows): every column pair
    '<key>_lo' / '<key>_hi' is split from the interval '<key>' when the row has it, a list of strings (routes, scenario
    types) is joined by '|', the families are joined, the dropped routes are 'route: reason' joined by ' | '."""
    out = {k: row.get(k) for k in columns}
    for c in columns:
        if isinstance(out[c], list) and all(isinstance(x, str) for x in out[c]):
            out[c] = '|'.join(out[c])
        base = c[:-3]
        if c.endswith('_lo') and f'{base}_hi' in columns and isinstance(row.get(base), (list, tuple)):
            out.update({c: row[base][0], f'{base}_hi': row[base][1]})
    if 'families' in columns:
        out['families'] = ','.join(row.get('families') or ()) or None
    if 'dropped_routes' in columns:
        out['dropped_routes'] = ' | '.join(f'{x["route_id"]}: {x["reason"]}' for x in row.get('dropped') or ()) or None
    return out


def _value(v):
    """A CSV cell: empty for None (and non-finite floats), JSON for lists and dicts, repr for floats."""
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return ''
    if isinstance(v, (list, tuple, dict)):
        return json.dumps(V2.jsonable(v), sort_keys=True)
    return repr(v) if isinstance(v, float) else v


def write_csv(path, rows, columns):
    """rows as a CSV file with exactly the given columns (a header only when there is no row), written through a
    temporary file."""
    tmp = Path(str(path) + '.tmp')
    with open(tmp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(columns), extrasaction='raise')
        w.writeheader()
        for r in rows:
            w.writerow({k: _value(r.get(k)) for k in columns})
    tmp.replace(path)


TABLE_COLUMNS = {'secondary.csv': ROW_COLUMNS, 'paired_differences.csv': ROUTE_COLUMNS, 'cells.csv': CELL_COLUMNS,
                 **{f'family_{f.name}.csv': ROW_COLUMNS for f in FAMILIES}, 'descriptive.csv': DESCRIPTIVE_COLUMNS,
                 'per_ability.csv': ABILITY_COLUMNS, 'per_scenario.csv': SCENARIO_COLUMNS,
                 'conditions.csv': CONDITION_COLUMNS, 'h4_offline.csv': H4_COLUMNS}
OUTPUT_FILES = tuple(TABLE_COLUMNS) + ('analysis.json', 'SHA256SUMS')      # the guard log is never replaced
AGG_MARKER = 'aggregate.json'          # an aggregation directory (its SHA256SUMS is the aggregator's): never written


def write_outputs(out, doc, tables, force=False):
    """The tables (TABLE_COLUMNS), analysis.json (doc plus the sha256 of every table) and SHA256SUMS (every file
    written) under out. PermissionError for a protected directory (aggregate_v4.check_out_dir); FileExistsError when
    out already holds an output and force is not given. The guard log is never touched here. Returns the written
    document."""
    out = Path(out)
    A.check_out_dir(out)
    if set(tables) != set(TABLE_COLUMNS):
        raise ValueError(f'tables {sorted(tables)} are not {sorted(TABLE_COLUMNS)}')
    if (out / AGG_MARKER).exists():
        raise FileExistsError(f'{PJ.rel(out)} holds an aggregation ({AGG_MARKER}); its SHA256SUMS is never replaced')
    present = [n for n in OUTPUT_FILES if (out / n).exists()]
    if present and not force:
        raise FileExistsError(f'{PJ.rel(out)} already holds {present} (use --force to replace them)')
    out.mkdir(parents=True, exist_ok=True)
    for name in TABLE_COLUMNS:
        write_csv(out / name, tables[name], TABLE_COLUMNS[name])
    doc = {**doc, 'outputs': {n: PJ.sha256_file(out / n) for n in TABLE_COLUMNS}}
    A._write_text(out / 'analysis.json', json.dumps(V2.jsonable(doc), indent=1, sort_keys=True, allow_nan=False)
                  + '\n')
    names = sorted(list(TABLE_COLUMNS) + ['analysis.json'])
    A._write_text(out / 'SHA256SUMS', ''.join(f'{PJ.sha256_file(out / n)}  {n}\n' for n in names))
    return doc


def summary_lines(doc, out):
    """The console report: inputs, guard state, each family's labels with n, the H1 findings, the RL benefit, H4
    offline, H5, the n of the descriptive contrasts and the rows with dropped routes."""
    g = doc['interim_guard']
    lines = [f'{doc["status"]} analysis -> {PJ.rel(out)}: {sum(s["rows"] for s in doc["sources"])} rows from '
             f'{len(doc["sources"])} inputs; scope: {doc["scope"]}',
             f'interim guard (Sec. 9.11): {g["status"]}, {g["test_input_rows"]} test-route rows, '
             f'{g["usable_rows"]} usable rows, {g["released_rows"]} released']
    lines += [f'DEVELOPMENT: {x}' for x in doc['development']]
    for f in doc['families']:
        lines.append(f'{f["name"]} ({f["role"]}, {f["metric"]}, {f["correction"]}): ' + '; '.join(
            f'{r["a_arm"]} - {r["b_arm"]} k{r["kappa"]} {r["subset"]} n {r["n"]}/{r["n_expected"]} {r["label"]}'
            for r in f['rows']))
    d = doc['decisions']
    lines.append(f'H1 finding 1: {d["H1"]["finding_1"]["statement"]}; finding 2: {d["H1"]["finding_2"]["statement"]}')
    lines.append(f'H2 RL benefit (Sec. 9.13): {d["H2"]["rl_benefit"]}')
    h4 = d['H4_offline']
    if h4['label'] == 'not computed':
        lines.append(f'H4 offline (Sec. 9.4): not computed ({h4["reason"]})')
    else:
        p = h4['primary']
        lines.append(f'H4 offline (Sec. 9.4; {h4["status"].split(" (")[0]}): {h4["label"]}; {p["a"]} - {p["b"]} '
                     f'{p["metric"]} {p["diff"]} [{p["lo"]}, {p["hi"]}], R_cond {p["r_cond_diff"]} '
                     f'[{p["r_cond_lo"]}, {p["r_cond_hi"]}]')
    h5d = d['H5']
    lines.append(f'H5 (Sec. 9.5): {h5d["label"]}; commit-audit violations {h5d["commit_audit_violations"]}, S3 '
                 f'violations {h5d["s3_violations"]}, unaudited runs {h5d["unaudited_runs"]}'
                 + ''.join(f'; {x}' for x in h5d['undetermined_because']))
    lines.append('descriptive (Secs. 7.5, 9.6): ' + '; '.join(
        f'{r["contrast"]} {r["metric"]} n {r["n"]}/{r["n_expected"]}' for r in doc['descriptive']
        if r['metric'] == 'driving_score'))
    m = doc['missing_data']
    lines.append(f'missing data (Sec. 9.8): {m["rows_complete"]} rows complete, {len(m["rows_incomplete"])} with '
                 'dropped routes (cells.csv, analysis.json missing_data)')
    return lines


def main(argv=None, settings=REGISTERED, table=None):
    """The command line (module docstring). settings and table (default: the registered statistics settings and the
    registered route table) are for the unit tests only (smaller resample counts, synthetic route ids; analysis.json
    records either as development); the command line has no option for them."""
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--agg', action='append', default=[],
                    help='an aggregate_v4.py output directory (runs.csv, aggregate.json, SHA256SUMS)')
    ap.add_argument('--runs', action='append', default=[],
                    help='a bare per-run CSV with the runs.csv columns (synthetic development data; a test-route row '
                         'is refused)')
    ap.add_argument('--analysis-freeze', help='a valid analysis-freeze record (interim_guard.py): needed for any '
                                              'test-route row (Sec. 9.11)')
    ap.add_argument('--required-job-files', metavar='FILE',
                    help='with --analysis-freeze: a JSON object {job file: sha256}, the registered tier 3-6 job files '
                         'of the test freeze (Sec. 8.1); a record that does not list each with that sha256 is refused')
    ap.add_argument('--rl-freeze', help='p3_rl.py rl_freeze.json: the Sec. 5.8 P_both label that H2 carries')
    ap.add_argument('--offline', default=str(ROOT / OFFLINE_REL),
                    help=f'the offline lease-ablation outputs of H4 offline (Sec. 9.4; default {OFFLINE_REL})')
    ap.add_argument('--s3', help='the S3 report of stress_bench.py (Sec. 7.6) for H5 (Sec. 9.5)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--force', action='store_true', help='replace earlier outputs in --out')
    a = ap.parse_args(argv)
    if not a.agg and not a.runs:
        ap.error('give --agg or --runs')
    if a.required_job_files and not a.analysis_freeze:
        ap.error('--required-job-files needs --analysis-freeze')
    argv = list(sys.argv if argv is None else [sys.argv[0], *argv])
    log = Path(a.out) / G.LOG_NAME
    params = {'agg': [PJ.rel(d) for d in a.agg], 'runs': [PJ.rel(f) for f in a.runs],
              'analysis_freeze': a.analysis_freeze, 'required_job_files': a.required_job_files,
              'rl_freeze': a.rl_freeze, 'offline': PJ.rel(a.offline), 's3': a.s3 and PJ.rel(a.s3),
              'out': PJ.rel(a.out)}

    def refuse(reason, code, freeze=None, logged=True):
        if logged:
            G.log_request(log, 'analysis', 'refused', reason, freeze, argv, **params)
        where = f', logged in {PJ.rel(log)}' if logged else ''
        print(f'REFUSED{" (interim-look guard" + where + ")" if code == 4 else ""}: {reason}', file=sys.stderr)
        return code

    try:
        A.check_out_dir(a.out)
    except PermissionError as e:                       # nothing is written into a protected directory, not even a log
        return refuse(str(e), 1, logged=False)
    if (Path(a.out) / AGG_MARKER).exists():           # nothing is written there, not even a log entry (its guard log
        return refuse(f'{a.out} holds an aggregation ({AGG_MARKER}), whose SHA256SUMS the analysis would replace: '
                      'write the analysis into a directory inside it (e.g. final_<stamp>/analysis)', 1,
                      logged=False)                    # is the aggregator's, recorded in its aggregate.json)
    if not a.force and any((Path(a.out) / n).exists() for n in OUTPUT_FILES):
        return refuse(f'{a.out} already holds outputs (use --force to replace them)', 1)
    freeze = None
    try:
        if a.analysis_freeze:
            required = None
            if a.required_job_files:
                required = A.MV.read_json(a.required_job_files)
                if not isinstance(required, dict) or not required:
                    raise GuardRefused(f'{a.required_job_files}: not a JSON object {{job file: sha256}}')
            freeze = G.load_freeze(a.analysis_freeze, required_job_files=required)
        sources = [load_aggregation(d) for d in a.agg] + [load_csv_source(f) for f in a.runs]
        p_both = load_p_both(a.rl_freeze) if a.rl_freeze else None
        offline = load_offline(a.offline)
        s3 = load_s3(a.s3) if a.s3 else None
        doc, tables = analyze(sources, table=table, settings=settings, freeze=freeze, p_both=p_both,
                              offline=offline, s3=s3, out=a.out)
    except GuardRefused as e:
        return refuse(str(e), 4, freeze)
    except (AnalysisError, OSError, ValueError, KeyError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2
    G.log_request(log, 'analysis', 'granted', None, freeze, argv, **params)
    if a.required_job_files:
        doc['inputs'] = dict(sorted({**doc['inputs'],
                                     PJ.rel(a.required_job_files): PJ.sha256_file(a.required_job_files)}.items()))
    doc['interim_guard']['log'] = G.log_state(log)
    doc = write_outputs(a.out, doc, tables, force=a.force)
    for line in summary_lines(doc, a.out):
        print(line)
    return 0


__all__ = ['SCHEMA', 'V2_SHA256', 'ALPHA', 'N_BOOT', 'BOOT_SEED', 'MC_FLIPS', 'MC_SEED', 'LABELS', 'DESCRIPTIVE',
           'METRICS', 'SECONDARY_METRICS', 'FAMILY_EXTRA_METRICS', 'FAMILIES', 'FAMILY_BY_NAME', 'H1_OTHERS',
           'PROTOCOL_ARMS', 'CELL_STATUS', 'STAT_KEYS', 'OUTPUT_FILES', 'TABLE_COLUMNS', 'REGISTERED', 'AnalysisError',
           'GuardRefused', 'Metric', 'Cond', 'Contrast', 'Family', 'Settings', 'sign_flip_test', 'bootstrap_ci', 'holm',
           'label_directional', 'family_contrasts', 'check_v2', 'flag', 'parse_row', 'read_runs', 'read_sums',
           'load_aggregation', 'load_csv_source', 'check_sources', 'make_table', 'route_table', 'test_input_rows',
           'code_citation', 'guard_rows', 'cell_key', 'build_cells', 'get_cell', 'outside_rows', 'paired',
           'paired_stats', 'directional_label', 'evaluate', 'run_family', 'secondary_metrics', 'run_secondary',
           'load_p_both', 'mark_p_both', 'finding', 'decide', 'needed_cells', 'cell_summary', 'analyze', 'csv_row',
           'write_csv', 'write_outputs', 'summary_lines', 'main', 'Descriptive', 'DESCRIPTIVE_CONTRASTS',
           'DESCRIPTIVE_GROUPS', 'REPLICATE_ARMS', 'SEED12_OTHERS', 'RL_GAIN', 'ABILITIES', 'H4_PRIMARY', 'H5_PHASES',
           'B_PI_S', 'MDE_REGISTERED', 'noise_floor', 'run_descriptive', 'analysis_conditions', 'route_abilities',
           'per_ability', 'replicates', 'rl_gain', 'mde', 'sensitivity', 'load_offline', 'per_clip_sums',
           'per_clip_pair', 'offline_quantity', 'h4_label', 'per_clip_check', 'h4_offline', 'load_s3', 'h5',
           'used_rows', 'overhead', 'manipulation_row', 'manipulation', 'missing_data', 'per_scenario',
           'condition_subsets', 'condition_summary', 'POOLED_COLLISIONS', 'KM_FLOOR', 'STAT_ROUTE_MEAN', 'STAT_POOLED',
           'pooled_ratio', 'pooled_collisions_row', 'ANALYSIS_REL', 'AGG_MARKER', 'out_location',
           'development_reasons', 'no_log_run', 'OVERHEAD_DIST']


if __name__ == '__main__':
    sys.exit(main())
