#!/usr/bin/env python3
"""Confirmatory analysis of the pre-registered closed-loop matrix (framelease_v2/PREREGISTRATION.md, Sec. 7).

Input: the aggregate CSV of framelease_v2/aggregate_closed_loop.py (one row per finished run). The route table, arms,
subsets, contrasts, settings and decision rules are fixed in this file (sha256 recorded in PREREGISTRATION.md
Sec. 10). Written and tested on synthetic CSVs only, without access to matrix results.

Confirmatory run, after the analysis freeze is recorded in PREREGISTRATION.md Sec. 10 (CPU only):
  CUDA_VISIBLE_DEVICES= python framelease_v2/aggregate_closed_loop.py
  CUDA_VISIBLE_DEVICES= python framelease_v2/analyze_closed_loop.py \\
      --csv outputs/framelease_v2/closed_loop_matrix/aggregate/closed_loop_runs.csv \\
      --out-dir outputs/framelease_v2/closed_loop_matrix/analysis

Data used. A cell (arm, route) is used when it has exactly one CSV row with analysis_use = 1 (the final attempt of a
queue job with a valid official route record), code_matches_prereg = 1, and the registered configuration (policy,
seed, kappa, max_age_s, lease file). Every other cell is reported with a status (no finished run, pending, failed,
excluded and why) and is never imputed. Rows of unknown routes, unregistered arms or routes outside an arm's subset
are counted and listed.

Contrasts. Each contrast is A - B over the routes of its registered subset; d_r = m(A, r) - m(B, r) on routes where
every arm of the contrast has a used cell (pairwise complete); per metric, routes whose value is missing are dropped
and listed. Orientation follows Sec. 7 (positive = the effect each hypothesis predicts: oracle - latency arm,
kappa 1.0 - kappa 1.5, Fixed Deep - Fast Only, fixed-age expiry - FrameLease). Metrics: driving score, route
completion, collisions per km, fallback tick fraction, action age p50 / p95, plus infraction penalty and total
infractions (secondary).

Statistics (registered, Sec. 7):
  estimate      mean paired difference over routes
  test          exact two-sided sign-flip test, p = P(|sum s_r d_r| >= |sum d_r|) over all 2^n sign vectors:
                complete enumeration for n <= 22; for n > 22 the exact distribution of sum s_r k_r by dynamic
                programming, k_r = d_r rounded to the metric grid (0.01 points for DS and RC; changes the statistic by
                at most 0.005 n points). For n > 22 a Monte Carlo sign-flip p (200,000 random sign vectors,
                numpy.random.default_rng(20261107)) is reported next to it as a cross-check; decisions use the exact p
  intervals     percentile bootstrap over routes, 10,000 resamples, numpy.random.default_rng(20261107) (a fresh
                generator per contrast and metric); 95% and 90%
  multiplicity  Holm within H1's primary pair (DS) and within its fast_only pair (secondary); nothing else corrected
  decisions     H1 (Holm p < 0.05 and sign, per step), H2 (90% CI inside (-10, 10) / p < 0.05 and |mean| >= 10),
                H3 (p < 0.05 and sign) exactly as in Sec. 7; a hypothesis with unfinished arms is labelled incomplete
  descriptive   kappa-2.0 extension, cap ablation, seed-12 replicate agreement and noise floor, manipulation checks
                (fallback fractions against the registered predictions), arm summaries, per-scenario (per-route)
                tables; no per-scenario tests

Outputs (--out-dir):
  analysis.json               everything below plus provenance (script and input sha256), settings and decisions
  contrasts.csv               one row per contrast x metric
  paired_differences.csv      one row per contrast x metric x route of the subset (values, difference or drop reason)
  cells.csv                   one row per registered (arm, route) cell: status, rows, attempts, reasons
  arms.csv                    per-arm completeness and descriptive summary
  per_route_by_scenario.csv   descriptive per-route results grouped by scenario type
  dose_response.{pdf,png}     DS and RC versus latency condition (oracle, kappa 1.0 / 1.5 / 2.0; Fixed Deep)
  contrast_forest.{pdf,png}   mean paired differences of DS and RC with 95% bootstrap intervals
  <figure>_data.csv           every plotted value (table view of each figure)
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import hashlib
import json
import math
import platform
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SCHEMA = 'framelease_v2.analyze_closed_loop/1'

# ------------------------------------------------------------------------- registered settings (Sec. 7)
ALPHA = 0.05
N_BOOT = 10_000
BOOT_SEED = 20261107
CI_LEVELS = (0.95, 0.90)
ENUM_MAX_N = 22               # complete enumeration of the 2^n sign vectors up to this n; dynamic programming above
EQUIV_MARGIN = 10.0           # H2 equivalence margin (DS points; RC points for the RC secondary)
MC_FLIPS = 200_000            # Monte Carlo cross-check for n > 22 (at least 100,000)
MC_SEED = 20261107
MAX_DP_BINS = 1 << 23         # memory guard of the DP; beyond it the grid is coarsened (1-2-5 steps) and reported
TIE_RTOL = 1e-9               # |S| >= |T| - TIE_RTOL * max(1, sum |d|): float round-off never breaks an exact tie
FALLBACK_FLAG_PP = 5.0        # manipulation checks: a deviation above this is reported as a possible runtime problem

# ------------------------------------------------------------------------- design (Secs. 3 and 4)
# (index, route id, town, scenario type): the 44 registered routes sorted by route id (PREREGISTRATION.md Sec. 3).
ROUTES = (
    (0, '1711', 'Town12', 'ParkingCutIn'),
    (1, '1773', 'Town12', 'ParkedObstacle'),
    (2, '1790', 'Town12', 'HazardAtSideLane'),
    (3, '1825', 'Town12', 'ConstructionObstacleTwoWays'),
    (4, '1852', 'Town12', 'AccidentTwoWays'),
    (5, '1956', 'Town12', 'ParkingExit'),
    (6, '2050', 'Town12', 'SignalizedJunctionRightTurn'),
    (7, '2082', 'Town12', 'OppositeVehicleRunningRedLight'),
    (8, '2084', 'Town12', 'NonSignalizedJunctionLeftTurn'),
    (9, '2115', 'Town12', 'NonSignalizedJunctionRightTurn'),
    (10, '2127', 'Town12', 'OppositeVehicleTakingPriority'),
    (11, '2144', 'Town12', 'VehicleTurningRoute'),
    (12, '2164', 'Town12', 'VehicleTurningRoutePedestrian'),
    (13, '2201', 'Town12', 'EnterActorFlow'),
    (14, '2204', 'Town12', 'BlockedIntersection'),
    (15, '2273', 'Town12', 'MergerIntoSlowTraffic'),
    (16, '2286', 'Town12', 'HighwayCutIn'),
    (17, '2373', 'Town12', 'VanillaSignalizedTurnEncounterRedLight'),
    (18, '2390', 'Town12', 'VanillaNonSignalizedTurn'),
    (19, '2416', 'Town12', 'VanillaNonSignalizedTurnEncounterStopsign'),
    (20, '2509', 'Town12', 'ConstructionObstacle'),
    (21, '2534', 'Town12', 'Accident'),
    (22, '2664', 'Town12', 'ParkedObstacleTwoWays'),
    (23, '2709', 'Town12', 'StaticCutIn'),
    (24, '2790', 'Town12', 'InvadingTurn'),
    (25, '3086', 'Town12', 'CrossingBicycleFlow'),
    (26, '3248', 'Town13', 'ParkingCrossingPedestrian'),
    (27, '3364', 'Town13', 'YieldToEmergencyVehicle'),
    (28, '3436', 'Town13', 'HazardAtSideLaneTwoWays'),
    (29, '3464', 'Town13', 'VehicleOpensDoorTwoWays'),
    (30, '3540', 'Town13', 'HardBreakRoute'),
    (31, '3561', 'Town13', 'ControlLoss'),
    (32, '3936', 'Town12', 'SignalizedJunctionLeftTurn'),
    (33, '14194', 'Town12', 'PedestrianCrossing'),
    (34, '14842', 'Town12', 'VanillaSignalizedTurnEncounterGreenLight'),
    (35, '17563', 'Town12', 'SequentialLaneChange'),
    (36, '17752', 'Town12', 'DynamicObjectCrossing'),
    (37, '23658', 'Town12', 'HighwayExit'),
    (38, '23695', 'Town13', 'InterurbanAdvancedActorFlow'),
    (39, '23771', 'Town12', 'MergerIntoSlowTrafficV2'),
    (40, '23901', 'Town13', 'InterurbanActorFlow'),
    (41, '26458', 'Town07', 'T_Junction'),
    (42, '28087', 'Town04', 'NonSignalizedJunctionLeftTurnEnterFlow'),
    (43, '28099', 'Town04', 'SignalizedJunctionLeftTurnEnterFlow'),
)
SUBSETS = {'all': 'every route (44)', 'E': 'index % 2 == 0 (22; oracle_sync)',
           'C': 'index % 4 == 0 (11; core: kappa 2.0, FrameLease, cap ablation)',
           'R': 'index % 3 == 0 (15; seed-12 replicates)'}
_SUBSET_RULE = {'all': lambda i: True, 'E': lambda i: i % 2 == 0, 'C': lambda i: i % 4 == 0,
                'R': lambda i: i % 3 == 0}
ROUTE_BY_ID = {rid: {'index': i, 'route_id': rid, 'town': town, 'scenario_type': stype}
               for i, rid, town, stype in ROUTES}
SUBSET_ROUTES = {s: tuple(rid for i, rid, _, _ in ROUTES if _SUBSET_RULE[s](i)) for s in SUBSETS}


def in_subset(subset: str, index: int) -> bool:
    return bool(_SUBSET_RULE[subset](index))


def route_subsets(index: int):
    return [s for s in ('E', 'C', 'R') if in_subset(s, index)]


@dataclass(frozen=True)
class Arm:
    name: str
    policy: str
    kappa: float | None           # None: oracle_sync (synchronous, no latency; --kappa does not apply)
    seed: int
    max_age_s: float | None       # runtime expiry (None for oracle_sync)
    lease_params: str | None      # lease file name (FrameLease only)
    subset: str
    tier: int
    short: str                    # figure label
    predicted_fallback: float | None = None   # Sec. 7 manipulation checks (excluding the first ~1 s)


ARMS = {a.name: a for a in (
    Arm('fixed_deep_k1.0_s11', 'fixed_deep', 1.0, 11, 3.0, None, 'all', 1, 'FD κ1.0', 0.0),
    Arm('fast_only_k1.0_s11', 'fast_only', 1.0, 11, 3.0, None, 'all', 1, 'FO κ1.0', 0.0),
    Arm('oracle_sync_s11', 'oracle_sync', None, 11, None, None, 'E', 2, 'Oracle', 0.0),
    Arm('fixed_deep_k1.5_s11', 'fixed_deep', 1.5, 11, 3.0, None, 'all', 3, 'FD κ1.5', 0.13),
    Arm('fast_only_k1.5_s11', 'fast_only', 1.5, 11, 3.0, None, 'all', 3, 'FO κ1.5', 0.0),
    Arm('fixed_deep_k2.0_s11', 'fixed_deep', 2.0, 11, 3.0, None, 'C', 4, 'FD κ2.0', 0.60),
    Arm('framelease_q95env_k1.0_s11', 'framelease', 1.0, 11, 2.0, 'lease_params_q95_envelope.json', 'C', 4,
        'FrameLease', None),
    Arm('fixed_deep_k1.0_s12', 'fixed_deep', 1.0, 12, 3.0, None, 'R', 5, 'FD κ1.0 s12', 0.0),
    Arm('fast_only_k1.0_s12', 'fast_only', 1.0, 12, 3.0, None, 'R', 5, 'FO κ1.0 s12', 0.0),
    Arm('fixed_deep_age2.0_k1.0_s11', 'fixed_deep', 1.0, 11, 2.0, None, 'C', 5, 'FD κ1.0 2 s cap', 0.15),
)}
OR, FD10, FO10 = 'oracle_sync_s11', 'fixed_deep_k1.0_s11', 'fast_only_k1.0_s11'
FD15, FO15, FD20 = 'fixed_deep_k1.5_s11', 'fast_only_k1.5_s11', 'fixed_deep_k2.0_s11'
FL, FDA2 = 'framelease_q95env_k1.0_s11', 'fixed_deep_age2.0_k1.0_s11'
FD10_S12, FO10_S12 = 'fixed_deep_k1.0_s12', 'fast_only_k1.0_s12'


@dataclass(frozen=True)
class Metric:
    key: str          # aggregate CSV column
    label: str
    unit: str
    grid: float       # DP rounding grid for n > 22 (registered: 0.01 points for DS and RC)
    contrast_set: str  # 'required' (the six task metrics) or 'secondary'


METRICS = (
    Metric('driving_score', 'Driving score', 'points (0-100)', 0.01, 'required'),
    Metric('route_completion', 'Route completion', 'points (0-100)', 0.01, 'required'),
    Metric('collisions_per_km', 'Collisions per km', 'collisions/km', 0.01, 'required'),
    Metric('fallback_fraction', 'Fallback tick fraction', 'fraction of ticks', 1e-4, 'required'),
    Metric('action_age_p50_s', 'Action age p50', 's', 1e-3, 'required'),
    Metric('action_age_p95_s', 'Action age p95', 's', 1e-3, 'required'),
    Metric('infraction_penalty', 'Infraction penalty', 'multiplier (0-1)', 1e-4, 'secondary'),
    Metric('infractions_total', 'Infractions, all types', 'count', 1.0, 'secondary'),
)
METRIC_BY_KEY = {m.key: m for m in METRICS}
INFRACTION_TYPES = ('collisions_pedestrian', 'collisions_vehicle', 'collisions_layout', 'red_light',
                    'stop_infraction', 'outside_route_lanes', 'route_dev', 'route_timeout', 'vehicle_blocked',
                    'yield_emergency_vehicle_infractions', 'scenario_timeouts', 'min_speed_infractions')
REQUIRED_COLUMNS = ('job_id', 'attempt', 'analysis_use', 'exclusion_reason', 'run_dir', 'route_id', 'route_index',
                    'scenario_type', 'arm', 'policy', 'kappa', 'seed', 'max_age_s', 'lease_params',
                    'code_matches_prereg', 'route_status', 'valid_record', 'km_driven', 'collisions_total',
                    'expired_tick_ratio', 'action_age_p99_s', 'sim_duration_s', 'wall_s', 'commits', 'rejects',
                    'rejects_by_reason') + tuple(m.key for m in METRICS) + tuple(f'inf_{t}' for t in INFRACTION_TYPES)


@dataclass(frozen=True)
class Contrast:
    cid: str
    label: str                    # figure label (A - B)
    a: tuple                      # ((arm, weight), ...): term A
    b: tuple                      # term B
    subset: str
    hypothesis: str               # H1 | H2 | H3 | replicate | cap
    role: str                     # primary | key_secondary | secondary | descriptive
    primary_metric: str | None = None
    holm_family: str | None = None
    rule: str | None = None       # decision rule applied: directional | equivalence
    noise_floor: bool = False
    note: str = ''

    @property
    def arms(self):
        out = []
        for arm, _ in self.a + self.b:
            if arm not in out:
                out.append(arm)
        return out

    @property
    def simple(self):
        return len(self.a) == 1 and len(self.b) == 1 and self.a[0][1] == 1 and self.b[0][1] == 1


def _c(cid, label, a, b, subset, hypothesis, role, **kw):
    a = ((a, 1),) if isinstance(a, str) else a
    b = ((b, 1),) if isinstance(b, str) else b
    return Contrast(cid, label, a, b, subset, hypothesis, role, **kw)


CONTRASTS = (
    _c('H1a_oracle_minus_fixed_deep_k1.0', 'Oracle − FD κ1.0', OR, FD10, 'E', 'H1', 'primary',
       primary_metric='driving_score', holm_family='H1_primary', rule='directional',
       note='synchronous zero-latency evaluation (world paused) versus measured latency; not a pure latency dose'),
    _c('H1b_fixed_deep_k1.0_minus_k1.5', 'FD κ1.0 − FD κ1.5', FD10, FD15, 'all', 'H1', 'primary',
       primary_metric='driving_score', holm_family='H1_primary', rule='directional',
       note='combines plan age with periodic 3.0 s horizon expiry at kappa 1.5 (manipulation checks)'),
    _c('H1a_oracle_minus_fast_only_k1.0', 'Oracle − FO κ1.0', OR, FO10, 'E', 'H1', 'secondary',
       primary_metric='driving_score', holm_family='H1_secondary_fast_only', rule='directional'),
    _c('H1b_fast_only_k1.0_minus_k1.5', 'FO κ1.0 − FO κ1.5', FO10, FO15, 'all', 'H1', 'secondary',
       primary_metric='driving_score', holm_family='H1_secondary_fast_only', rule='directional',
       note='age only (Fast Only does not cross the 3.0 s cap at kappa 1.5)'),
    _c('H1ext_fixed_deep_k1.0_minus_k2.0', 'FD κ1.0 − FD κ2.0', FD10, FD20, 'C', 'H1', 'descriptive',
       note='kappa-2.0 extension on the core subset; descriptive, with CIs'),
    _c('H1ext_fixed_deep_k1.5_minus_k2.0', 'FD κ1.5 − FD κ2.0', FD15, FD20, 'C', 'H1', 'descriptive',
       note='kappa-2.0 extension on the core subset; descriptive, with CIs'),
    _c('H2_fixed_deep_minus_fast_only_k1.0', 'FD − FO at κ1.0', FD10, FO10, 'all', 'H2', 'primary',
       primary_metric='driving_score', rule='equivalence',
       note='DS primary (margin 10 points); RC secondary with margin 10 RC points'),
    _c('H2_fixed_deep_minus_fast_only_k1.5', 'FD − FO at κ1.5', FD15, FO15, 'all', 'H2', 'secondary',
       primary_metric='driving_score', rule='equivalence',
       note='not a pure depth contrast: Fixed Deep crosses the 3.0 s cap at kappa 1.5, Fast Only does not'),
    _c('H2_fixed_deep_minus_fast_only_k1.0_s12', 'FD − FO κ1.0, seed 12', FD10_S12, FO10_S12, 'R', 'H2',
       'secondary', primary_metric='driving_score', rule='equivalence', note='seed-12 replicate on R'),
    _c('H2_fixed_deep_minus_fast_only_k1.0_s11_on_R', 'FD − FO κ1.0, seed 11 (R)', FD10, FO10, 'R', 'H2',
       'secondary', primary_metric='driving_score', rule='equivalence',
       note='seed-11 contrast restricted to R: the like-for-like comparison for the seed-12 replicate'),
    _c('H2_replicate_seed11_minus_seed12', '(FD − FO) s11 − (FD − FO) s12', ((FD10, 1), (FO10, -1)),
       ((FD10_S12, 1), (FO10_S12, -1)), 'R', 'replicate', 'secondary',
       note='replicate agreement of the depth contrast: difference of the per-route depth effects between seeds'),
    _c('seed_fixed_deep_k1.0_s11_minus_s12', 'FD κ1.0: s11 − s12', FD10, FD10_S12, 'R', 'replicate', 'secondary',
       noise_floor=True, note='run-to-run noise floor: |d| summarizes the seed-to-seed difference'),
    _c('seed_fast_only_k1.0_s11_minus_s12', 'FO κ1.0: s11 − s12', FO10, FO10_S12, 'R', 'replicate', 'secondary',
       noise_floor=True, note='run-to-run noise floor: |d| summarizes the seed-to-seed difference'),
    _c('H3_fixed_deep_k1.0_minus_framelease', 'FD κ1.0 − FrameLease', FD10, FL, 'C', 'H3', 'primary',
       primary_metric='route_completion', rule='directional',
       note='fixed-age expiry (3.0 s) minus lease-gated expiry (H_max 2.0 s); 11 routes'),
    _c('H3_fixed_deep_age2.0_minus_framelease', 'FD 2 s cap − FrameLease', FDA2, FL, 'C', 'H3', 'key_secondary',
       primary_metric='route_completion', rule='directional',
       note='same 2.0 s cap: separates the lease from the shorter cap'),
    _c('cap_fixed_deep_age3.0_minus_age2.0', 'FD 3 s cap − FD 2 s cap', FD10, FDA2, 'C', 'cap', 'secondary',
       note='cap ablation (3.0 s versus 2.0 s expiry, Fixed Deep, kappa 1.0); not among the Sec. 7 tests; '
            'uncorrected'),
)
CONTRAST_BY_ID = {c.cid: c for c in CONTRASTS}

# Cell statuses. INCOMPLETE: the arm is not finished on that route at the cutoff (the hypothesis is labelled
# incomplete); every other non-used status is missing data of a finished job (pairwise deletion, reported).
CELL_STATUS = {
    'used': 'one final valid record with matching code and configuration',
    'no_finished_run': 'no finished run in the CSV (not started or still running)',
    'pending_not_final': 'a finished run exists but the queue job is not final yet',
    'failed_retry_pending': 'one attempt without a valid record; the registered infrastructure retry is pending',
    'failed_final': 'queue job final without a valid record (two attempts, or marked final by the queue)',
    'excluded_code_mismatch': 'closed-loop code differs from the pre-registered sha256 pins',
    'excluded_code_unverified': 'code match against the pins could not be verified (code_matches_prereg empty)',
    'excluded_config_mismatch': 'run configuration differs from the registered arm',
    'excluded_ambiguous_duplicate': 'more than one row with analysis_use = 1 for the same arm and route',
    'excluded_invalid_record': 'analysis_use = 1 but valid_record != 1 (inconsistent row)',
    'excluded_other': 'no usable row for another reason (see reasons)',
}
INCOMPLETE = frozenset({'no_finished_run', 'pending_not_final', 'failed_retry_pending'})


@dataclass
class Settings:
    n_boot: int = N_BOOT
    boot_seed: int = BOOT_SEED
    mc_flips: int = MC_FLIPS
    mc_seed: int = MC_SEED
    allow_unverified_code: bool = False


# ------------------------------------------------------------------------- parsing helpers
def fnum(x):
    """Float or None (empty, None, nan, inf, non-numeric)."""
    if x is None:
        return None
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        v = float(x)
    else:
        s = str(x).strip()
        if not s or s.lower() in ('none', 'nan', 'null', 'na'):
            return None
        try:
            v = float(s)
        except ValueError:
            return None
    return v if math.isfinite(v) else None


def inum(x):
    """Integer or None ('1', '1.0', 1, True -> 1)."""
    if isinstance(x, bool):
        return int(x)
    s = '' if x is None else str(x).strip().lower()
    if s in ('true', 'false'):
        return int(s == 'true')
    v = fnum(x)
    return int(v) if v is not None and v == int(v) else None


def norm_route(x) -> str:
    s = '' if x is None else str(x).strip()
    v = fnum(s)
    return str(int(v)) if v is not None and v == int(v) else s


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def jsonable(x):
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return float(x) if math.isfinite(float(x)) else None
    if isinstance(x, np.ndarray):
        return jsonable(x.tolist())
    if isinstance(x, Path):
        return str(x)
    return x


# ------------------------------------------------------------------------- statistics
def sign_flip_counts_enumeration(d):
    """Complete enumeration of all 2^n sign vectors: (count of s with |sum s_r d_r| >= |sum d_r|, 2^n).
    Ties are exact up to float round-off (relative tolerance TIE_RTOL of sum |d|)."""
    d = np.asarray(d, dtype=float).ravel()
    sums = np.zeros(1)
    for x in d:
        sums = np.concatenate((sums + x, sums - x))
    t = abs(math.fsum(d.tolist()))
    tol = TIE_RTOL * max(1.0, float(np.abs(d).sum()))
    return int(np.count_nonzero(np.abs(sums) >= t - tol)), 1 << int(d.size)


def sign_flip_counts_dp(k):
    """Exact distribution of sum s_r k_r over all 2^n sign vectors for integers k, by dynamic programming:
    (count of s with |sum s_r k_r| >= |sum k_r|, 2^n). Integer arithmetic: ties are exact."""
    k = np.asarray(k, dtype=np.int64).ravel()
    n = int(k.size)
    if n > 62:
        raise ValueError('more than 62 routes would overflow the int64 pattern counts')
    counts = np.ones(1, dtype=np.int64)          # index j <-> sum j - K (K = half width)
    for a in sorted(int(v) for v in np.abs(k)):
        if a == 0:
            counts = counts * 2
            continue
        new = np.zeros(counts.size + 2 * a, dtype=np.int64)
        new[:counts.size] += counts              # sum - a
        new[2 * a:] += counts                    # sum + a
        counts = new
    half = (counts.size - 1) // 2
    t = abs(int(k.sum()))
    s = np.arange(-half, half + 1)
    return int(counts[np.abs(s) >= t].sum()), 1 << n


def dp_grid(d, base: float, max_bins: int = MAX_DP_BINS) -> float:
    """The registered grid, or the smallest coarser 1-2-5 multiple whose DP array fits in max_bins."""
    d = np.abs(np.asarray(d, dtype=float))
    for e in range(0, 16):
        for m in (1, 2, 5):
            g = base * m * 10 ** e
            if 2 * int(np.rint(d / g).sum()) + 1 <= max_bins:
                return g
    raise ValueError('differences too large for the DP grid')


def sign_flip_mc(d, n_flips: int = MC_FLIPS, seed: int = MC_SEED, chunk: int = 25_000):
    """Monte Carlo sign-flip p (cross-check): (1 + #{|sum s d| >= |sum d|}) / (1 + n_flips), random sign vectors from
    numpy.random.default_rng(seed)."""
    d = np.asarray(d, dtype=float).ravel()
    rng = np.random.default_rng(seed)
    t = abs(math.fsum(d.tolist()))
    tol = TIE_RTOL * max(1.0, float(np.abs(d).sum()))
    hits = done = 0
    while done < n_flips:
        m = min(chunk, n_flips - done)
        s = rng.integers(0, 2, size=(m, d.size)) * 2.0 - 1.0
        hits += int(np.count_nonzero(np.abs(s @ d) >= t - tol))
        done += m
    p = (hits + 1) / (n_flips + 1)
    return {'p_mc': p, 'mc_flips': int(n_flips), 'mc_seed': int(seed), 'mc_hits': hits,
            'mc_se': math.sqrt(p * (1.0 - p) / n_flips)}


def sign_flip_test(d, grid: float = 0.01, mc_flips: int = MC_FLIPS, mc_seed: int = MC_SEED,
                   enum_max_n: int = ENUM_MAX_N):
    """Exact two-sided sign-flip test of the mean paired difference (Sec. 7). n <= enum_max_n: complete enumeration;
    n > enum_max_n: exact DP over d rounded to `grid` (coarsened only if the DP would not fit in memory), plus a
    Monte Carlo cross-check. None for n = 0."""
    d = np.asarray(d, dtype=float).ravel()
    n = int(d.size)
    if n == 0:
        return None
    out = {'n': n, 'sum': math.fsum(d.tolist())}
    if n <= enum_max_n:
        cnt, tot = sign_flip_counts_enumeration(d)
        nz = int(np.count_nonzero(d))
        out.update(p_method='exact_enumeration', dp_grid=None, dp_grid_registered=None, dp_max_statistic_change=0.0)
    else:
        g = dp_grid(d, grid)
        k = np.rint(d / g).astype(np.int64)
        cnt, tot = sign_flip_counts_dp(k)
        nz = int(np.count_nonzero(k))
        out.update(p_method='exact_dp_rounded', dp_grid=g, dp_grid_registered=grid,
                   dp_max_statistic_change=n * g / 2.0)
        out.update(sign_flip_mc(d, mc_flips, mc_seed))
    out.update(p_two_sided=cnt / tot, n_extreme=cnt, n_patterns=tot, n_nonzero=nz,
               min_attainable_p=min(1.0, 2.0 / 2 ** nz) if nz else 1.0)
    return out


def bootstrap_ci(x, n_boot: int = N_BOOT, seed: int = BOOT_SEED, levels=CI_LEVELS, abs_values: bool = False):
    """Percentile bootstrap of the mean over routes: {'ci95': [lo, hi], 'ci90': [lo, hi]} (None for n = 0).
    A fresh numpy.random.default_rng(seed) per call; resampled indices rng.integers(0, n, (n_boot, n))."""
    x = np.asarray(x, dtype=float).ravel()
    if abs_values:
        x = np.abs(x)
    keys = [f'ci{int(round(lv * 100))}' for lv in levels]
    if x.size == 0:
        return dict.fromkeys(keys)
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, x.size, size=(n_boot, x.size))].mean(axis=1)
    out = {}
    for key, lv in zip(keys, levels):
        lo, hi = np.quantile(means, [(1.0 - lv) / 2.0, 1.0 - (1.0 - lv) / 2.0])
        out[key] = [float(lo), float(hi)]
    return out


def holm(pvals):
    """Holm step-down adjusted p-values. A missing p (None) keeps its place in the family as p = 1 (conservative:
    the family size stays as registered) and its adjusted value stays None."""
    m = len(pvals)
    filled = [1.0 if p is None else float(p) for p in pvals]
    adj, running = [0.0] * m, 0.0
    for rank, i in enumerate(sorted(range(m), key=lambda j: filled[j])):
        running = max(running, min(1.0, (m - rank) * filled[i]))
        adj[i] = running
    return [None if pvals[i] is None else adj[i] for i in range(m)]


def label_directional(mean, p, alpha: float = ALPHA):
    """H1 (with Holm-adjusted p) and H3 rule: supported if mean > 0 and p < alpha; contradicted if mean < 0 and
    p < alpha; otherwise inconclusive."""
    if mean is None or p is None:
        return 'no data'
    if p < alpha and mean > 0:
        return 'supported'
    if p < alpha and mean < 0:
        return 'contradicted'
    return 'inconclusive'


def label_equivalence(mean, ci90, p, margin: float = EQUIV_MARGIN, alpha: float = ALPHA):
    """H2 rule: 'no meaningful difference' (supported) if the 90% bootstrap CI lies inside (-margin, +margin);
    'meaningful difference' (contradicted) if p < alpha and |mean| >= margin; otherwise inconclusive."""
    if mean is None:
        return 'no data'
    if ci90 is not None and ci90[0] is not None and -margin < ci90[0] and ci90[1] < margin:
        return 'supported: no meaningful difference'
    if p is not None and p < alpha and abs(mean) >= margin:
        return 'contradicted: meaningful difference'
    return 'inconclusive'


# ------------------------------------------------------------------------- cells (arm x route)
@dataclass
class Cell:
    arm: str
    route_id: str
    status: str
    row: dict | None
    rows: list
    detail: list

    @property
    def attempts(self):
        vals = [inum(r.get('attempt')) for r in self.rows]
        vals = [v for v in vals if v is not None]
        return max(vals) if vals else None


def config_problems(row: dict, arm: Arm):
    """Differences between a run's recorded configuration and the registered arm."""
    probs = []
    if (row.get('policy') or '').strip() != arm.policy:
        probs.append(f'policy {row.get("policy")!r} != {arm.policy!r}')
    if inum(row.get('seed')) != arm.seed:
        probs.append(f'seed {row.get("seed")!r} != {arm.seed}')
    if arm.policy != 'oracle_sync':
        kappa, age = fnum(row.get('kappa')), fnum(row.get('max_age_s'))
        if kappa is None or abs(kappa - arm.kappa) > 1e-6:
            probs.append(f'kappa {row.get("kappa")!r} != {arm.kappa}')
        if age is None or abs(age - arm.max_age_s) > 1e-6:
            probs.append(f'max_age_s {row.get("max_age_s")!r} != {arm.max_age_s}')
        lease = (row.get('lease_params') or '').strip() or None
        if lease != arm.lease_params:
            probs.append(f'lease_params {lease!r} != {arm.lease_params!r}')
    return probs


def classify_cell(arm: Arm, route_id: str, rows: list, allow_unverified_code: bool = False) -> Cell:
    """Status of one registered (arm, route) cell from all its CSV rows (any attempt)."""
    if not rows:
        return Cell(arm.name, route_id, 'no_finished_run', None, [], [])
    used = [r for r in rows if inum(r.get('analysis_use')) == 1]
    reasons = [(r.get('exclusion_reason') or '').strip() for r in rows if inum(r.get('analysis_use')) != 1]
    if len(used) > 1:
        return Cell(arm.name, route_id, 'excluded_ambiguous_duplicate', None, rows,
                    [f'{len(used)} rows with analysis_use = 1: ' + '; '.join(str(r.get('run_dir')) for r in used)])
    if len(used) == 1:
        r = used[0]
        if inum(r.get('valid_record')) != 1:
            return Cell(arm.name, route_id, 'excluded_invalid_record', None, rows,
                        [f'valid_record = {r.get("valid_record")!r}'])
        code = inum(r.get('code_matches_prereg'))
        if code == 0:
            return Cell(arm.name, route_id, 'excluded_code_mismatch', None, rows,
                        [f'code_mismatch_files = {r.get("code_mismatch_files")!r}'])
        if code is None and not allow_unverified_code:
            return Cell(arm.name, route_id, 'excluded_code_unverified', None, rows, ['code_matches_prereg empty'])
        probs = config_problems(r, arm)
        if probs:
            return Cell(arm.name, route_id, 'excluded_config_mismatch', None, rows, probs)
        detail = ['code match unverified; included by --allow-unverified-code'] if code is None else []
        return Cell(arm.name, route_id, 'used', r, rows, detail + [f'{x} (other attempt)' for x in reasons if x])
    if any(x == 'job not final yet' for x in reasons):
        status = 'pending_not_final'
    elif any(x.startswith('closed-loop code differs') for x in reasons):
        status = 'excluded_code_mismatch'
    elif any(x.startswith('arm mismatch') for x in reasons):
        status = 'excluded_config_mismatch'
    elif any(x == 'job final without a valid record' for x in reasons):
        status = 'failed_final'
    elif all(inum(r.get('valid_record')) != 1 for r in rows):
        attempts = max([inum(r.get('attempt')) or 0 for r in rows] + [len(rows)])
        status = 'failed_final' if attempts >= 2 else 'failed_retry_pending'
    else:
        status = 'excluded_other'
    return Cell(arm.name, route_id, status, None, rows, [x or '(no exclusion_reason)' for x in reasons])


def build_cells(rows, allow_unverified_code: bool = False):
    """{(arm, route_id): Cell} for every registered cell, plus the rows that belong to no registered cell."""
    groups = defaultdict(list)
    stray = {'not_queue_job': [], 'unknown_route': [], 'unregistered_arm': [], 'outside_arm_subset': []}
    for i, row in enumerate(rows):
        rid, arm = norm_route(row.get('route_id')), (row.get('arm') or '').strip()
        brief = {'data_row': i + 1, 'arm': arm, 'route_id': rid, 'analysis_use': inum(row.get('analysis_use')),
                 'exclusion_reason': row.get('exclusion_reason') or None, 'run_dir': row.get('run_dir') or None}
        if not (row.get('job_id') or '').strip() and inum(row.get('analysis_use')) != 1:
            stray['not_queue_job'].append(brief)   # e.g. smoke or manual runs: not part of the matrix
        elif rid not in ROUTE_BY_ID:
            stray['unknown_route'].append(brief)
        elif arm not in ARMS:
            stray['unregistered_arm'].append(brief)
        elif not in_subset(ARMS[arm].subset, ROUTE_BY_ID[rid]['index']):
            stray['outside_arm_subset'].append(brief)
        else:
            groups[(arm, rid)].append(row)
    cells = {(a.name, rid): classify_cell(a, rid, groups.get((a.name, rid), []), allow_unverified_code)
             for a in ARMS.values() for rid in SUBSET_ROUTES[a.subset]}
    return cells, stray


def cell_value(cell: Cell | None, key: str):
    if cell is None or cell.status != 'used':
        return None
    return fnum(cell.row.get(key))


def term_value(term, cells, route_id, key):
    total = 0.0
    for arm, w in term:
        v = cell_value(cells.get((arm, route_id)), key)
        if v is None:
            return None
        total += w * v
    return total


def term_name(term):
    """'arm' for a single arm, 'arm1 - arm2' for a linear combination."""
    parts = []
    for i, (arm, w) in enumerate(term):
        mag = arm if abs(w) == 1 else f'{abs(w):g}*{arm}'
        parts.append(('- ' if w < 0 else ('+ ' if i else '')) + mag)
    return ' '.join(parts)


# ------------------------------------------------------------------------- contrasts
def metric_stats(c: Contrast, metric: Metric, pairs, settings: Settings):
    """Statistics of one contrast and metric from [(route, value_a, value_b, d), ...]."""
    n = len(pairs)
    res = {'metric': metric.key, 'unit': metric.unit, 'n': n}
    if n == 0:
        res.update(mean=None, sd=None, median=None, min=None, max=None, mean_a=None, mean_b=None, ci95=None,
                   ci90=None, p_two_sided=None, p_method=None)
        return res
    d = np.array([p[3] for p in pairs], dtype=float)
    va = np.array([p[1] for p in pairs], dtype=float)
    vb = np.array([p[2] for p in pairs], dtype=float)
    res.update(mean=float(d.mean()), sd=float(d.std(ddof=1)) if n > 1 else None, median=float(np.median(d)),
               min=float(d.min()), max=float(d.max()), mean_a=float(va.mean()), mean_b=float(vb.mean()),
               n_positive=int(np.count_nonzero(d > 0)), n_negative=int(np.count_nonzero(d < 0)),
               n_zero=int(np.count_nonzero(d == 0)))
    res.update(bootstrap_ci(d, settings.n_boot, settings.boot_seed))
    sf = sign_flip_test(d, metric.grid, settings.mc_flips, settings.mc_seed)
    res.update({k: v for k, v in sf.items() if k not in ('n',)})
    if c.noise_floor:
        absd = np.abs(d)
        ci = bootstrap_ci(d, settings.n_boot, settings.boot_seed, levels=(0.95,), abs_values=True)
        r = float(np.corrcoef(va, vb)[0, 1]) if n > 2 and va.std() > 0 and vb.std() > 0 else None
        res['noise_floor'] = {'mean_abs_diff': float(absd.mean()), 'mean_abs_diff_ci95': ci['ci95'],
                              'median_abs_diff': float(np.median(absd)), 'max_abs_diff': float(absd.max()),
                              'pearson_r_a_b': r}
    return res


def evaluate_contrast(c: Contrast, cells, settings: Settings):
    routes = SUBSET_ROUTES[c.subset]
    paired, dropped = [], []
    for rid in routes:
        miss = [{'arm': a, 'status': cells[(a, rid)].status} for a in c.arms if cells[(a, rid)].status != 'used']
        (dropped if miss else paired).append({'route_id': rid, 'missing': miss} if miss else rid)
    incomplete = sorted({(m['arm'], m['status']) for x in dropped for m in x['missing'] if m['status'] in INCOMPLETE})
    out = {'contrast_id': c.cid, 'label': c.label, 'hypothesis': c.hypothesis, 'role': c.role,
           'a': term_name(c.a), 'b': term_name(c.b), 'arms': c.arms, 'subset': c.subset,
           'subset_rule': SUBSETS[c.subset], 'primary_metric': c.primary_metric, 'holm_family': c.holm_family,
           'decision_rule': c.rule, 'note': c.note, 'n_expected': len(routes), 'n_paired': len(paired),
           'paired_routes': paired, 'dropped_routes': dropped,
           'n_dropped_unfinished': sum(1 for x in dropped if any(m['status'] in INCOMPLETE for m in x['missing'])),
           'n_dropped_missing_data': sum(1 for x in dropped
                                         if not any(m['status'] in INCOMPLETE for m in x['missing'])),
           'arms_final': not incomplete, 'metrics': {}, 'route_rows': {}}
    for metric in METRICS:
        pairs, missing, audit = [], [], []
        for rid in routes:
            if rid not in paired:
                x = next(x for x in dropped if x['route_id'] == rid)
                audit.append((rid, None, None, None, 'dropped: ' + '; '.join(f'{m["arm"]} {m["status"]}'
                                                                            for m in x['missing'])))
                continue
            va, vb = term_value(c.a, cells, rid, metric.key), term_value(c.b, cells, rid, metric.key)
            if va is None or vb is None:
                arms = [a for a in c.arms if cell_value(cells[(a, rid)], metric.key) is None]
                missing.append({'route_id': rid, 'arms_missing_value': arms})
                audit.append((rid, va, vb, None, 'metric missing: ' + ', '.join(arms)))
                continue
            pairs.append((rid, va, vb, va - vb))
            audit.append((rid, va, vb, va - vb, 'paired'))
        res = metric_stats(c, metric, pairs, settings)
        res['dropped_missing_metric'] = missing
        if c.simple and pairs and metric.key == 'route_completion':
            res['completed_routes'] = {'n': len(pairs), 'a': sum(1 for p in pairs if p[1] >= 100 - 1e-9),
                                       'b': sum(1 for p in pairs if p[2] >= 100 - 1e-9)}
        if c.simple and pairs and metric.key == 'collisions_per_km':
            res['pooled'] = pooled_collisions(c, cells, [p[0] for p in pairs])
        out['metrics'][metric.key] = res
        out['route_rows'][metric.key] = audit
    if c.simple and paired:
        out['infractions_by_type'] = {
            side: {t: int(sum(inum(cells[(term[0][0], rid)].row.get(f'inf_{t}')) or 0 for rid in paired))
                   for t in INFRACTION_TYPES} for side, term in (('a', c.a), ('b', c.b))}
    return out


def pooled_collisions(c: Contrast, cells, routes):
    """Arm-level pooled collisions per km over the paired routes: sum of collisions / sum of km (floor 0.001 km)."""
    out = {}
    for side, term in (('a', c.a), ('b', c.b)):
        rows = [cells[(term[0][0], rid)].row for rid in routes]
        coll = [fnum(r.get('collisions_total')) for r in rows]
        km = [fnum(r.get('km_driven')) for r in rows]
        if any(v is None for v in coll + km):
            out[side] = None
            continue
        out[side] = {'collisions': float(sum(coll)), 'km': float(sum(km)),
                     'collisions_per_km': float(sum(coll) / max(sum(km), 0.001))}
    if out.get('a') and out.get('b'):
        out['difference_a_minus_b'] = out['a']['collisions_per_km'] - out['b']['collisions_per_km']
    return out


def apply_holm(results):
    families = defaultdict(list)
    for c in CONTRASTS:
        if c.holm_family:
            families[c.holm_family].append(c.cid)
    out = {}
    for fam, cids in families.items():
        ms = [results[cid]['metrics'][CONTRAST_BY_ID[cid].primary_metric] for cid in cids]
        adj = holm([m.get('p_two_sided') for m in ms])
        for cid, m, pa in zip(cids, ms, adj):
            m['p_holm'] = pa
            m['holm_family'] = fam
        out[fam] = {'contrasts': cids, 'metric': CONTRAST_BY_ID[cids[0]].primary_metric,
                    'p': [m.get('p_two_sided') for m in ms], 'p_holm': adj}
    return out


def _brief(r, metric):
    m = r['metrics'][metric]
    return {'contrast': r['contrast_id'], 'metric': metric, 'n': m['n'], 'n_expected': r['n_expected'],
            'arms_final': r['arms_final'], 'mean': m.get('mean'), 'ci95': m.get('ci95'), 'ci90': m.get('ci90'),
            'p_two_sided': m.get('p_two_sided'), 'p_method': m.get('p_method')}


def decide(results):
    """Sec. 7 decisions. Labels are computed on pairwise-complete routes; 'completeness' is 'incomplete' when an arm
    of a primary contrast is unfinished on a route of its subset."""
    R = results
    for r in R.values():
        c = CONTRAST_BY_ID[r['contrast_id']]
        for key in ('driving_score', 'route_completion'):
            m = r['metrics'][key]
            if c.rule == 'equivalence':
                m['decision'] = label_equivalence(m.get('mean'), m.get('ci90'), m.get('p_two_sided'))
            elif c.rule == 'directional' and key == c.primary_metric:
                p = m.get('p_holm') if c.holm_family else m.get('p_two_sided')
                m['decision'] = label_directional(m.get('mean'), p)

    def completeness(*cids):
        return 'complete' if all(R[c]['arms_final'] for c in cids) else 'incomplete'

    def step(cid, metric):
        b = _brief(R[cid], metric)
        b['p_holm'] = R[cid]['metrics'][metric].get('p_holm')
        b['label'] = R[cid]['metrics'][metric].get('decision')
        return b

    h1a, h1b = 'H1a_oracle_minus_fixed_deep_k1.0', 'H1b_fixed_deep_k1.0_minus_k1.5'
    steps = {'a_oracle_minus_k1.0': step(h1a, 'driving_score'), 'b_k1.0_minus_k1.5': step(h1b, 'driving_score')}
    labels = [s['label'] for s in steps.values()]
    h1 = {'question': 'latency degrades closed-loop driving (oracle > kappa 1.0 > kappa 1.5), DS, Fixed Deep',
          'completeness': completeness(h1a, h1b), 'steps': steps,
          'overall': 'supported' if all(x == 'supported' for x in labels) else 'not supported (see steps)',
          'contradicted_steps': [k for k, s in steps.items() if s['label'] == 'contradicted'],
          'secondary_fast_only': {'a_oracle_minus_k1.0': step('H1a_oracle_minus_fast_only_k1.0', 'driving_score'),
                                  'b_k1.0_minus_k1.5': step('H1b_fast_only_k1.0_minus_k1.5', 'driving_score')},
          'rule': 'supported if both mean DS differences > 0 with Holm-adjusted p < 0.05 (Holm over the two); '
                  'contradicted at a step if its mean < 0 with Holm-adjusted p < 0.05; otherwise inconclusive at '
                  'that step. Secondary: fast_only pair (Holm within the pair), RC, collisions/km, infractions; '
                  'kappa-2.0 extension descriptive.'}
    h2c = 'H2_fixed_deep_minus_fast_only_k1.0'

    def eq(cid, metric):
        b = _brief(R[cid], metric)
        b['label'] = R[cid]['metrics'][metric].get('decision')
        return b

    h2 = {'question': 'refinement depth makes no meaningful difference at equal kappa (Fixed Deep - Fast Only, DS)',
          'completeness': completeness(h2c), 'margin': EQUIV_MARGIN, 'primary': eq(h2c, 'driving_score'),
          'secondary': {'route_completion_k1.0': eq(h2c, 'route_completion'),
                        'driving_score_k1.5': eq('H2_fixed_deep_minus_fast_only_k1.5', 'driving_score'),
                        'route_completion_k1.5': eq('H2_fixed_deep_minus_fast_only_k1.5', 'route_completion'),
                        'driving_score_seed12_R': eq('H2_fixed_deep_minus_fast_only_k1.0_s12', 'driving_score'),
                        'route_completion_seed12_R': eq('H2_fixed_deep_minus_fast_only_k1.0_s12',
                                                        'route_completion'),
                        'driving_score_seed11_R': eq('H2_fixed_deep_minus_fast_only_k1.0_s11_on_R', 'driving_score'),
                        'route_completion_seed11_R': eq('H2_fixed_deep_minus_fast_only_k1.0_s11_on_R',
                                                        'route_completion')},
          'rule': 'supported (no meaningful difference) if the 90% bootstrap CI of the mean DS difference lies inside '
                  '(-10, +10); contradicted (meaningful difference) if the exact sign-flip p < 0.05 and |mean| >= 10; '
                  'otherwise inconclusive. Mean, 95% and 90% CIs reported in every case.'}
    h3c, h3k = 'H3_fixed_deep_k1.0_minus_framelease', 'H3_fixed_deep_age2.0_minus_framelease'
    h3 = {'question': 'lease-gated expiry reduces route completion relative to fixed-age expiry (RC)',
          'completeness': completeness(h3c), 'primary': step(h3c, 'route_completion'),
          'key_secondary': step(h3k, 'route_completion'),
          'descriptive': {k: {cid: _brief(R[cid], k) for cid in (h3c, h3k)}
                          for k in ('driving_score', 'fallback_fraction', 'action_age_p50_s', 'action_age_p95_s',
                                    'collisions_per_km')},
          'rule': 'supported if the mean RC difference > 0 with exact sign-flip p < 0.05; contradicted if < 0 with '
                  'p < 0.05; otherwise inconclusive. With 11 routes a non-significant result is not evidence of no '
                  'effect.'}
    return {'H1': h1, 'H2': h2, 'H3': h3}


def replicate_agreement(results):
    s11, s12 = (results['H2_fixed_deep_minus_fast_only_k1.0_s11_on_R'],
                results['H2_fixed_deep_minus_fast_only_k1.0_s12'])
    did = results['H2_replicate_seed11_minus_seed12']
    out = {'definition': 'depth contrast (Fixed Deep - Fast Only, kappa 1.0) at seed 11 and seed 12 on R; their '
                         'per-route difference (replicate disagreement) with test and CI; per-arm seed-to-seed '
                         '|d| noise floor', 'metrics': {}}
    for key in ('driving_score', 'route_completion'):
        a, b = s11['metrics'][key], s12['metrics'][key]
        same = (None if a.get('mean') is None or b.get('mean') is None
                else bool(np.sign(a['mean']) == np.sign(b['mean'])))
        out['metrics'][key] = {
            'seed11_on_R': _brief(s11, key), 'seed12_on_R': _brief(s12, key), 'difference_seed11_minus_seed12':
                _brief(did, key), 'same_sign_of_mean': same,
            'seed12_ci95_contains_seed11_mean': None if b.get('ci95') is None or a.get('mean') is None
            else bool(b['ci95'][0] <= a['mean'] <= b['ci95'][1])}
    out['noise_floor'] = {}
    for cid in ('seed_fixed_deep_k1.0_s11_minus_s12', 'seed_fast_only_k1.0_s11_minus_s12'):
        r = results[cid]
        out['noise_floor'][r['arms'][0]] = {
            key: {'n': r['metrics'][key]['n'], **(r['metrics'][key].get('noise_floor') or {}),
                  'mean_s11_minus_s12': r['metrics'][key].get('mean'), 'ci95': r['metrics'][key].get('ci95'),
                  'p_two_sided': r['metrics'][key].get('p_two_sided')}
            for key in (m.key for m in METRICS)}
    return out


# ------------------------------------------------------------------------- descriptive summaries
def arm_summary(cells):
    out = {}
    for arm in ARMS.values():
        cs = [cells[(arm.name, rid)] for rid in SUBSET_ROUTES[arm.subset]]
        used = [c for c in cs if c.status == 'used']

        def vals(key):
            return [v for v in (cell_value(c, key) for c in used) if v is not None]

        def mean(key):
            v = vals(key)
            return float(np.mean(v)) if v else None

        counts = Counter(c.status for c in cs)
        ck = [(cell_value(c, 'collisions_total'), cell_value(c, 'km_driven')) for c in used]
        ck = [p for p in ck if None not in p]
        rejects = Counter()
        for c in used:
            try:
                rejects.update(json.loads(c.row.get('rejects_by_reason') or '{}'))
            except (TypeError, ValueError):
                pass
        out[arm.name] = {
            'policy': arm.policy, 'kappa': arm.kappa, 'seed': arm.seed, 'max_age_s': arm.max_age_s,
            'lease_params': arm.lease_params, 'subset': arm.subset, 'tier': arm.tier,
            'n_expected': len(cs), 'n_used': len(used), 'status_counts': dict(sorted(counts.items())),
            'all_jobs_final': not any(c.status in INCOMPLETE for c in cs),
            'not_used_routes': [{'route_id': c.route_id, 'status': c.status, 'detail': c.detail}
                                for c in cs if c.status != 'used'],
            'driving_score_mean': mean('driving_score'), 'route_completion_mean': mean('route_completion'),
            'infraction_penalty_mean': mean('infraction_penalty'),
            'completed_routes': sum(1 for v in vals('route_completion') if v >= 100 - 1e-9),
            'collisions_total': float(sum(p[0] for p in ck)) if ck else None,
            'km_driven_total': float(sum(p[1] for p in ck)) if ck else None,
            'collisions_per_km_pooled': float(sum(p[0] for p in ck) / max(sum(p[1] for p in ck), 0.001))
            if ck else None, 'n_routes_pooled': len(ck),
            'infractions_by_type_total': {t: int(sum(vals(f'inf_{t}'))) for t in INFRACTION_TYPES},
            'fallback_fraction_mean': mean('fallback_fraction'), 'expired_tick_ratio_mean': mean('expired_tick_ratio'),
            'action_age_p50_s_mean': mean('action_age_p50_s'), 'action_age_p95_s_mean': mean('action_age_p95_s'),
            'action_age_p99_s_mean': mean('action_age_p99_s'), 'sim_duration_s_mean': mean('sim_duration_s'),
            'wall_s_mean': mean('wall_s'), 'commits_mean': mean('commits'),
            'rejects_total': int(sum(vals('rejects'))) if vals('rejects') else None,
            'rejects_by_reason_total': dict(sorted(rejects.items())),
            'route_status_counts': dict(sorted(Counter((c.row.get('route_status') or '').strip() or '(empty)'
                                                       for c in used).items())),
            'descriptive_only': True}
    return out


def manipulation_checks(cells, arms):
    """Observed fallback against the registered predictions (Sec. 7; reported, not tested)."""
    out = {'definition': 'mean over used routes of fallback_fraction (all fallback ticks, including the first ~1 s '
                         'before any plan exists) and expired_tick_ratio (expiry fallback only); predictions exclude '
                         f'the first ~1 s. |deviation| > {FALLBACK_FLAG_PP:g} percentage points is reported as a '
                         'possible runtime problem.', 'arms': {}}
    for arm in ARMS.values():
        s = arms[arm.name]
        ff = [v for v in (cell_value(cells[(arm.name, r)], 'fallback_fraction') for r in SUBSET_ROUTES[arm.subset])
              if v is not None]
        ent = {'n': len(ff), 'predicted_fallback_fraction': arm.predicted_fallback,
               'fallback_fraction_mean': s['fallback_fraction_mean'],
               'fallback_fraction_median': float(np.median(ff)) if ff else None,
               'fallback_fraction_range': [float(min(ff)), float(max(ff))] if ff else None,
               'expired_tick_ratio_mean': s['expired_tick_ratio_mean']}
        if arm.predicted_fallback is not None:
            for key in ('fallback_fraction_mean', 'expired_tick_ratio_mean'):
                v = ent[key]
                dev = None if v is None else 100.0 * (v - arm.predicted_fallback)
                ent[key.replace('_mean', '_deviation_pp')] = dev
                ent[key.replace('_mean', '_flag')] = None if dev is None else bool(abs(dev) > FALLBACK_FLAG_PP)
        if arm.name == OR:
            ent['note'] = '0 by construction (official synchronous agent never falls back)'
        if arm.seed == 12:
            ent['note'] = 'prediction of the identical seed-11 configuration (Sec. 7 lists seed 11)'
        if arm.name == FDA2:
            ent['note'] = 'Sec. 7: about 15% (smoke on 2086: 15.0% expired ticks)'
        if arm.name == FL:
            ent['note'] = ('prediction: at least the lease-free schedule allows (smoke on 2086: 87-98%); compared '
                           'descriptively with the Fixed Deep 2.0 s cap arm on the same routes')
            pairs = [(cell_value(cells[(FL, r)], 'fallback_fraction'), cell_value(cells[(FDA2, r)],
                                                                                   'fallback_fraction'))
                     for r in SUBSET_ROUTES['C']]
            pairs = [p for p in pairs if None not in p]
            ent['paired_with_fixed_deep_age2.0'] = {
                'n': len(pairs), 'framelease_mean': float(np.mean([p[0] for p in pairs])) if pairs else None,
                'fixed_deep_age2.0_mean': float(np.mean([p[1] for p in pairs])) if pairs else None,
                'flag_below_lease_free_by_more_than_5pp': bool(np.mean([p[0] - p[1] for p in pairs]) * 100
                                                               < -FALLBACK_FLAG_PP) if pairs else None}
        out['arms'][arm.name] = ent
    return out


PER_ROUTE_KEYS = ('driving_score', 'route_completion', 'infraction_penalty', 'collisions_per_km',
                  'fallback_fraction', 'action_age_p50_s', 'action_age_p95_s')


def per_scenario(cells):
    """Descriptive per-route table grouped by scenario type (one route per type in this matrix); no tests."""
    out = []
    for i, rid, town, stype in sorted(ROUTES, key=lambda r: (r[3], r[0])):
        arms = {}
        for arm in ARMS.values():
            if not in_subset(arm.subset, i):
                continue
            cell = cells[(arm.name, rid)]
            arms[arm.name] = {'status': cell.status,
                              'route_status': (cell.row.get('route_status') or None) if cell.row else None,
                              **{k: cell_value(cell, k) for k in PER_ROUTE_KEYS}}
        out.append({'scenario_type': stype, 'route_id': rid, 'route_index': i, 'town': town,
                    'subsets': route_subsets(i), 'arms': arms})
    return out


# ------------------------------------------------------------------------- figures
INK, INK2, MUTED, GRIDC, AXISC = '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#c3c2b7'
ROUTE_GREY = '#b4b3ab'
BAND_GREY = '#ecebe5'
# Categorical slots 1 and 2 of the dataviz reference palette (blue, orange); validated all-pairs on white:
# CVD dE 24.7, normal-vision dE 33.6, both >= 3:1 contrast. Marker shape is the secondary encoding.
METRIC_STYLE = {'driving_score': ('#2a78d6', 'o', 'DS'), 'route_completion': ('#eb6834', 's', 'RC')}
DOSE_LEVELS = ((OR, 'Oracle\n(sync)'), (FD10, 'κ 1.0'), (FD15, 'κ 1.5'), (FD20, 'κ 2.0'))
FOREST_GROUPS = (
    ('H1  Latency', ('H1a_oracle_minus_fixed_deep_k1.0', 'H1b_fixed_deep_k1.0_minus_k1.5',
                                   'H1a_oracle_minus_fast_only_k1.0', 'H1b_fast_only_k1.0_minus_k1.5',
                                   'H1ext_fixed_deep_k1.0_minus_k2.0', 'H1ext_fixed_deep_k1.5_minus_k2.0')),
    ('H2  Depth at equal κ', ('H2_fixed_deep_minus_fast_only_k1.0', 'H2_fixed_deep_minus_fast_only_k1.5',
                                           'H2_fixed_deep_minus_fast_only_k1.0_s12',
                                           'H2_fixed_deep_minus_fast_only_k1.0_s11_on_R')),
    ('H3  Lease and expiry cap', ('H3_fixed_deep_k1.0_minus_framelease',
                                                'H3_fixed_deep_age2.0_minus_framelease',
                                                'cap_fixed_deep_age3.0_minus_age2.0')),
    ('Seeds 11 − 12 (noise floor)', ('seed_fixed_deep_k1.0_s11_minus_s12',
                                                 'seed_fast_only_k1.0_s11_minus_s12')),
)


def _pyplot():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        'font.family': 'sans-serif', 'font.sans-serif': ['Liberation Sans', 'Arial', 'Helvetica', 'DejaVu Sans'],
        'font.size': 8, 'axes.labelsize': 8, 'axes.titlesize': 8, 'xtick.labelsize': 7.5, 'ytick.labelsize': 7.5,
        'legend.fontsize': 7.5, 'pdf.fonttype': 42, 'ps.fonttype': 42, 'axes.edgecolor': AXISC,
        'axes.linewidth': 0.6, 'axes.labelcolor': INK, 'text.color': INK, 'xtick.color': INK2,
        'ytick.color': INK2, 'xtick.major.width': 0.6, 'ytick.major.width': 0.6, 'xtick.major.size': 2.5,
        'ytick.major.size': 2.5, 'axes.unicode_minus': True, 'figure.facecolor': 'white',
        'axes.facecolor': 'white', 'savefig.facecolor': 'white'})
    return plt


def _style_axes(ax):
    ax.grid(color=GRIDC, lw=0.5)
    ax.set_axisbelow(True)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)


def dose_response_data(cells, settings: Settings):
    data = {}
    for key in ('driving_score', 'route_completion'):
        per_route = {rid: [cell_value(cells.get((arm, rid)), key) for arm, _ in DOSE_LEVELS]
                     for _, rid, _, _ in ROUTES}
        levels = []
        for j, (arm, _) in enumerate(DOSE_LEVELS):
            v = [per_route[rid][j] for rid in per_route if per_route[rid][j] is not None]
            ci = bootstrap_ci(v, settings.n_boot, settings.boot_seed, levels=(0.95,))['ci95']
            levels.append({'arm': arm, 'n': len(v), 'mean': float(np.mean(v)) if v else None, 'ci95': ci})
        data[key] = {'per_route': per_route, 'levels': levels}
    return data


def plot_dose_response(dose, out_dir: Path, png_dpi: int = 600, name: str = 'dose_response'):
    plt = _pyplot()
    from matplotlib.lines import Line2D
    W, H = 3.5, 4.3
    left, right, top, bottom, gap = 0.50, 0.10, 0.54, 0.66, 0.30
    ph = (H - top - bottom - gap) / 2.0
    fig = plt.figure(figsize=(W, H))
    x = np.arange(len(DOSE_LEVELS), dtype=float)
    rows, axes, titles = [], [], []
    for k, key in enumerate(('driving_score', 'route_completion')):
        color, marker, short = METRIC_STYLE[key]
        y0 = bottom + (1 - k) * (ph + gap)
        ax = fig.add_axes([left / W, y0 / H, (W - left - right) / W, ph / H])
        axes.append(ax)
        _style_axes(ax)
        for rid, vals in dose[key]['per_route'].items():
            y = np.array([np.nan if v is None else v for v in vals], dtype=float)
            if np.all(np.isnan(y)):
                continue
            ax.plot(x, y, color=ROUTE_GREY, lw=0.6, alpha=0.75, zorder=2, solid_capstyle='round')
            ax.plot(x, y, ls='none', marker='o', ms=1.6, color=ROUTE_GREY, alpha=0.9, zorder=2)
            for j, v in enumerate(vals):
                rows.append({'panel': short, 'series': 'route', 'route_id': rid, 'level': DOSE_LEVELS[j][0],
                             'x': j, 'y': v, 'ci95_lo': '', 'ci95_hi': '', 'n': ''})
        lv = dose[key]['levels']
        mx = [j for j, e in enumerate(lv) if e['mean'] is not None]
        for j0, j1 in zip(mx[:-1], mx[1:]):
            ax.plot([j0, j1], [lv[j0]['mean'], lv[j1]['mean']], color=color, lw=1.6, zorder=4,
                    ls=(0, (3.0, 1.6)) if j0 == 0 else '-', solid_capstyle='round', dash_capstyle='round')
        for j in mx:
            e = lv[j]
            ax.errorbar([j], [e['mean']], yerr=[[e['mean'] - e['ci95'][0]], [e['ci95'][1] - e['mean']]],
                        fmt='none', ecolor=color, elinewidth=1.0, capsize=0, zorder=5)
            ax.plot([j], [e['mean']], ls='none', marker=marker, ms=4.6, color=color, mec='white', mew=0.7, zorder=6)
        for j, e in enumerate(lv):
            rows.append({'panel': short, 'series': 'mean', 'route_id': '', 'level': e['arm'], 'x': j, 'y': e['mean'],
                         'ci95_lo': e['ci95'][0] if e['ci95'] else '', 'ci95_hi': e['ci95'][1] if e['ci95'] else '',
                         'n': e['n']})
        ax.set_xlim(-0.35, len(DOSE_LEVELS) - 0.65)
        ax.set_ylim(-4, 104)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.set_xticks(x)
        ax.set_ylabel('Driving score' if key == 'driving_score' else 'Route completion (%)')
        titles.append(ax.set_title(('(a) Driving score' if key == 'driving_score' else '(b) Route completion')
                                   + ', Fixed Deep', loc='left', pad=3, color=INK))
    n_ds = [e['n'] for e in dose['driving_score']['levels']]
    n_rc = [e['n'] for e in dose['route_completion']['levels']]
    axes[0].set_xticklabels([''] * len(DOSE_LEVELS))
    axes[1].set_xticklabels([f'{lab}\nn = {a}' if a == b else f'{lab}\nn = {a}/{b}'
                             for (_, lab), a, b in zip(DOSE_LEVELS, n_ds, n_rc)])
    axes[1].set_xlabel('Latency condition (κ: GPU contention scale)', labelpad=3)
    handles = [Line2D([], [], color=ROUTE_GREY, lw=0.9, marker='o', ms=2, label='Route'),
               Line2D([], [], color=METRIC_STYLE['driving_score'][0], lw=1.6, marker='o', ms=4.6, mec='white',
                      mew=0.7, label='Mean DS, 95% CI'),
               Line2D([], [], color=METRIC_STYLE['route_completion'][0], lw=1.6, marker='s', ms=4.4, mec='white',
                      mew=0.7, label='Mean RC, 95% CI')]
    leg = fig.legend(handles=handles, loc='upper left', bbox_to_anchor=(left / W - 0.02, 1.0), ncol=3,
                     frameon=False, handlelength=1.8, columnspacing=1.0, handletextpad=0.5, borderaxespad=0.3)
    note = fig.text(left / W, (H - 0.24) / H, 'dashed: synchronous oracle → measured latency (not a pure dose)',
                    fontsize=6.5, color=INK2, va='top', ha='left')
    outside = ([t for ax in axes for t in ax.get_yticklabels()] + list(axes[1].get_xticklabels()) + titles
               + [ax.yaxis.label for ax in axes] + [axes[1].xaxis.label, leg, note])
    return _save(fig, plt, out_dir, name, png_dpi, rows, axes, outside)


def plot_forest(results, out_dir: Path, png_dpi: int = 600, name: str = 'contrast_forest'):
    plt = _pyplot()
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from matplotlib.transforms import blended_transform_factory
    items = []
    for header, cids in FOREST_GROUPS:
        items.append(('header', header, None))
        items.extend(('contrast', cid, results[cid]) for cid in cids if cid in results)
    row_h = 0.172
    W, left, right, top, bottom = 3.5, 1.58, 0.10, 0.34, 0.62
    H = top + bottom + row_h * len(items)
    fig = plt.figure(figsize=(W, H))
    ax = fig.add_axes([left / W, bottom / H, (W - left - right) / W, (H - top - bottom) / H])
    _style_axes(ax)
    ax.grid(axis='y', visible=False)
    ax.set_ylim(len(items) - 0.5, -0.5)
    bounds, rows, ticks, labels, bold = [], [], [], [], []
    h2_rows, headers, inside = [], [], []
    for i, (kind, text, r) in enumerate(items):
        if kind == 'header':
            headers.append(ax.text(0.03, i, text, transform=blended_transform_factory(fig.transFigure, ax.transData),
                                   ha='left', va='center', fontsize=7.5, fontweight='bold', color=INK))
            continue
        c = CONTRAST_BY_ID[text]
        if c.hypothesis == 'H2':
            h2_rows.append(i)
        ticks.append(i)
        labels.append(f'{c.label} ({r["n_paired"]})')
        bold.append(c.role == 'primary')
        for key, off in (('driving_score', -0.18), ('route_completion', 0.18)):
            color, marker, short = METRIC_STYLE[key]
            m = r['metrics'][key]
            if m['n'] == 0 or m.get('mean') is None:
                rows.append({'contrast_id': c.cid, 'label': c.label, 'metric': short, 'n': 0, 'mean': '',
                             'ci95_lo': '', 'ci95_hi': '', 'p_two_sided': '', 'role': c.role})
                continue
            lo, hi = m['ci95']
            ax.plot([lo, hi], [i + off, i + off], color=color, lw=1.0, solid_capstyle='butt', zorder=3)
            ax.plot([m['mean']], [i + off], ls='none', marker=marker, ms=3.9 if marker == 'o' else 3.6,
                    color=color, mec='white', mew=0.5, zorder=4)
            bounds += [lo, hi, m['mean']]
            rows.append({'contrast_id': c.cid, 'label': c.label, 'metric': short, 'n': m['n'], 'mean': m['mean'],
                         'ci95_lo': lo, 'ci95_hi': hi, 'p_two_sided': m.get('p_two_sided'), 'role': c.role})
        if all(r['metrics'][k]['n'] == 0 for k in ('driving_score', 'route_completion')):
            inside.append(ax.text(0, i, 'no paired routes', ha='center', va='center', fontsize=6.5, color=MUTED))
    lim = max([EQUIV_MARGIN * 1.5] + [abs(b) * 1.04 for b in bounds])
    step = next(s for s in (5, 10, 20, 25, 50) if math.ceil(lim / s) <= 3)   # at most 7 ticks: no collisions
    tick_lim = min(100, step * math.ceil(lim / step))
    ax.set_xlim(-max(lim, tick_lim * 1.04), max(lim, tick_lim * 1.04))
    ax.set_xticks(np.arange(-tick_lim, tick_lim + 1e-9, step))
    if h2_rows:
        ax.fill_betweenx([min(h2_rows) - 0.5, max(h2_rows) + 0.5], -EQUIV_MARGIN, EQUIV_MARGIN, color=BAND_GREY,
                         lw=0, zorder=0)
    ax.axvline(0, color=INK2, lw=0.7, zorder=2)
    ax.set_yticks(ticks)
    ax.set_yticklabels(labels)
    ax.tick_params(axis='y', length=0, pad=3)
    for lab, b in zip(ax.get_yticklabels(), bold):
        lab.set_color(INK)
        if b:
            lab.set_fontweight('bold')
    ax.set_xlabel('A − B (points): mean, 95% bootstrap CI', labelpad=2)
    handles = [Line2D([], [], color=METRIC_STYLE['driving_score'][0], lw=1.0, marker='o', ms=3.9, mec='white',
                      mew=0.5, label='Driving score'),
               Line2D([], [], color=METRIC_STYLE['route_completion'][0], lw=1.0, marker='s', ms=3.6, mec='white',
                      mew=0.5, label='Route completion'),
               Patch(facecolor=BAND_GREY, edgecolor='none', label='H2 margin ±10')]
    leg = fig.legend(handles=handles, loc='upper left', bbox_to_anchor=(0.01, 1.0), ncol=3, frameon=False,
                     handlelength=1.6, columnspacing=1.1, handletextpad=0.5, borderaxespad=0.3)
    foot = fig.text(0.02, 0.012, 'FD Fixed Deep (10 steps), FO Fast Only (1 step); (n) paired routes;\n'
                                 'bold: pre-registered primary contrast (H1, H2: DS; H3: RC).',
                    fontsize=6.5, color=INK2, ha='left', va='bottom', linespacing=1.25)
    outside = list(ax.get_yticklabels()) + list(ax.get_xticklabels()) + headers + [ax.xaxis.label, leg, foot]
    return _save(fig, plt, out_dir, name, png_dpi, rows, [ax], outside, inside)


def layout_problems(fig, axes, outside, inside=()):
    """Rendered-layout check: text boxes (tick labels, titles, legends, notes) that overlap each other or leave
    the figure, and text placed outside the plot area that overlaps it."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    def boxes(items):
        out = []
        for t in items:
            text = t.get_text() if hasattr(t, 'get_text') else type(t).__name__
            if t.get_visible() and str(text).strip():
                out.append((str(text).replace('\n', ' ')[:48], t.get_window_extent(renderer)))
        return out

    out_b, in_b = boxes(outside), boxes(inside)
    every, fb, probs = out_b + in_b, fig.bbox, []
    for name, bb in every:
        if bb.x0 < fb.x0 - 0.5 or bb.y0 < fb.y0 - 0.5 or bb.x1 > fb.x1 + 0.5 or bb.y1 > fb.y1 + 0.5:
            probs.append(f'{name!r} leaves the figure')
    for i in range(len(every)):
        for j in range(i + 1, len(every)):
            if every[i][1].overlaps(every[j][1]):
                probs.append(f'{every[i][0]!r} overlaps {every[j][0]!r}')
    for name, bb in out_b:
        if any(bb.overlaps(ax.get_window_extent(renderer)) for ax in axes):
            probs.append(f'{name!r} overlaps the plot area')
    return probs


def _save(fig, plt, out_dir: Path, name: str, png_dpi: int, rows, axes, outside, inside=()):
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf, png, data = out_dir / f'{name}.pdf', out_dir / f'{name}.png', out_dir / f'{name}_data.csv'
    size = [round(float(v), 3) for v in fig.get_size_inches()]
    problems = layout_problems(fig, axes, outside, inside)
    if problems:
        print(f'LAYOUT WARNING ({name}): ' + '; '.join(problems), file=sys.stderr)
    fig.savefig(pdf)
    fig.savefig(png, dpi=png_dpi)
    plt.close(fig)
    write_csv(data, rows, list(rows[0].keys()) if rows else ['empty'])
    return {'pdf': str(pdf), 'png': str(png), 'data_csv': str(data), 'size_in': size, 'layout_problems': problems}


# ------------------------------------------------------------------------- output
def _fmt(v):
    if v is None:
        return ''
    if isinstance(v, float):
        return repr(v) if math.isfinite(v) else ''
    if isinstance(v, (list, dict)):
        return json.dumps(jsonable(v), sort_keys=True)
    return v


def write_csv(path: Path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('.' + path.name + '.tmp')
    with tmp.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({k: _fmt(r.get(k)) for k in columns})
    tmp.replace(path)


def contrast_rows(results):
    rows = []
    for c in CONTRASTS:
        r = results[c.cid]
        for metric in METRICS:
            m = r['metrics'][metric.key]
            rows.append({
                'contrast_id': c.cid, 'hypothesis': c.hypothesis, 'role': c.role, 'label': c.label, 'a': r['a'],
                'b': r['b'], 'subset': c.subset, 'metric': metric.key, 'metric_set': metric.contrast_set,
                'is_primary_metric': int(metric.key == c.primary_metric and c.role == 'primary'),
                'n_expected': r['n_expected'], 'n_paired': r['n_paired'], 'n': m['n'],
                'arms_final': int(r['arms_final']), 'mean': m.get('mean'), 'sd': m.get('sd'), 'median': m.get('median'),
                'mean_a': m.get('mean_a'), 'mean_b': m.get('mean_b'),
                'ci95_lo': (m.get('ci95') or [None, None])[0], 'ci95_hi': (m.get('ci95') or [None, None])[1],
                'ci90_lo': (m.get('ci90') or [None, None])[0], 'ci90_hi': (m.get('ci90') or [None, None])[1],
                'p_two_sided': m.get('p_two_sided'), 'p_method': m.get('p_method'), 'p_holm': m.get('p_holm'),
                'holm_family': m.get('holm_family'), 'decision': m.get('decision'), 'p_mc': m.get('p_mc'),
                'mc_se': m.get('mc_se'), 'dp_grid': m.get('dp_grid'), 'n_nonzero': m.get('n_nonzero'),
                'min_attainable_p': m.get('min_attainable_p'),
                'dropped_routes': ';'.join(x['route_id'] for x in r['dropped_routes']),
                'dropped_missing_metric': ';'.join(x['route_id'] for x in m['dropped_missing_metric'])})
    return rows


def paired_rows(results):
    rows = []
    for c in CONTRASTS:
        r = results[c.cid]
        for metric in METRICS:
            for rid, va, vb, d, status in r['route_rows'][metric.key]:
                rows.append({'contrast_id': c.cid, 'metric': metric.key, 'route_id': rid,
                             'route_index': ROUTE_BY_ID[rid]['index'],
                             'scenario_type': ROUTE_BY_ID[rid]['scenario_type'], 'a': r['a'], 'b': r['b'],
                             'value_a': va, 'value_b': vb, 'diff': d, 'status': status})
    return rows


def cell_rows(cells):
    rows = []
    for (arm, rid), c in cells.items():
        rows.append({'arm': arm, 'route_id': rid, 'route_index': ROUTE_BY_ID[rid]['index'],
                     'scenario_type': ROUTE_BY_ID[rid]['scenario_type'], 'status': c.status,
                     'counts_as_unfinished': int(c.status in INCOMPLETE), 'n_rows': len(c.rows),
                     'attempts': c.attempts, 'run_dir': c.row.get('run_dir') if c.row else None,
                     'route_status': c.row.get('route_status') if c.row else None, 'detail': ' | '.join(c.detail)})
    return rows


def arm_rows(arms):
    keys = ('policy', 'kappa', 'seed', 'max_age_s', 'subset', 'tier', 'n_expected', 'n_used', 'all_jobs_final',
            'status_counts', 'driving_score_mean', 'route_completion_mean', 'infraction_penalty_mean',
            'completed_routes', 'collisions_per_km_pooled', 'fallback_fraction_mean', 'expired_tick_ratio_mean',
            'action_age_p50_s_mean', 'action_age_p95_s_mean', 'action_age_p99_s_mean', 'sim_duration_s_mean',
            'wall_s_mean', 'commits_mean', 'rejects_total', 'rejects_by_reason_total', 'route_status_counts',
            'infractions_by_type_total')
    return [{'arm': a, **{k: s[k] for k in keys}} for a, s in arms.items()], ['arm', *keys]


def scenario_rows(table):
    rows = []
    for e in table:
        for arm, v in e['arms'].items():
            rows.append({'scenario_type': e['scenario_type'], 'route_id': e['route_id'],
                         'route_index': e['route_index'], 'town': e['town'], 'subsets': ','.join(e['subsets']),
                         'arm': arm, **v})
    cols = ['scenario_type', 'route_id', 'route_index', 'town', 'subsets', 'arm', 'status', 'route_status',
            *PER_ROUTE_KEYS]
    return rows, cols


def read_csv_rows(path: Path):
    with open(path, encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise SystemExit(f'{path}: missing columns {missing} (expected the aggregate_closed_loop.py CSV)')
    return rows, header


def rejects_summary(cells, arm: str, routes):
    """Plan rejects (total and by reason) of an arm over the used cells of the given routes (descriptive)."""
    used = [cells[(arm, r)] for r in routes if cells[(arm, r)].status == 'used']
    by_reason = Counter()
    for c in used:
        try:
            by_reason.update(json.loads(c.row.get('rejects_by_reason') or '{}'))
        except (TypeError, ValueError):
            pass
    totals = [v for v in (cell_value(c, 'rejects') for c in used) if v is not None]
    return {'n_routes': len(used), 'rejects_total': int(sum(totals)) if totals else None,
            'rejects_by_reason': dict(sorted(by_reason.items()))}


def analyze(rows, settings: Settings):
    cells, stray = build_cells(rows, settings.allow_unverified_code)
    results = {c.cid: evaluate_contrast(c, cells, settings) for c in CONTRASTS}
    holm_fams = apply_holm(results)
    hyp = decide(results)
    hyp['H3']['descriptive']['rejects_on_C'] = {a: rejects_summary(cells, a, SUBSET_ROUTES['C'])
                                                for a in (FD10, FDA2, FL)}
    arms = arm_summary(cells)
    status_totals = Counter(c.status for c in cells.values())
    data_status = {
        'rows_total': len(rows), 'rows_analysis_use': sum(1 for r in rows if inum(r.get('analysis_use')) == 1),
        'rows_by_exclusion_reason': dict(sorted(Counter((r.get('exclusion_reason') or '').strip() or '(none: used)'
                                                        for r in rows).items())),
        'cells_expected': len(cells), 'cells_used': status_totals.get('used', 0),
        'cell_status_counts': dict(sorted(status_totals.items())), 'cell_status_definitions': CELL_STATUS,
        'unfinished_statuses': sorted(INCOMPLETE),
        'stray_rows': {k: {'n': len(v), 'rows': v} for k, v in stray.items()},
        'route_metadata_mismatches': route_metadata_mismatches(cells)}
    return {'cells': cells, 'results': results, 'holm': holm_fams, 'hypotheses': hyp, 'arms': arms,
            'data_status': data_status, 'replicate_agreement': replicate_agreement(results),
            'manipulation_checks': manipulation_checks(cells, arms), 'per_scenario': per_scenario(cells)}


def route_metadata_mismatches(cells):
    """Used rows whose route_index or scenario_type disagree with the registered route table."""
    out = []
    for (arm, rid), c in cells.items():
        if c.status != 'used':
            continue
        idx, stype = inum(c.row.get('route_index')), (c.row.get('scenario_type') or '').strip()
        reg = ROUTE_BY_ID[rid]
        if (idx is not None and idx != reg['index']) or (stype and stype != reg['scenario_type']):
            out.append({'arm': arm, 'route_id': rid, 'csv_route_index': idx, 'csv_scenario_type': stype,
                        'registered_index': reg['index'], 'registered_scenario_type': reg['scenario_type']})
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument('--csv', type=Path, required=True, help='aggregate_closed_loop.py output CSV')
    p.add_argument('--out-dir', type=Path, required=True)
    p.add_argument('--n-boot', type=int, default=N_BOOT, help=f'bootstrap resamples (registered {N_BOOT})')
    p.add_argument('--boot-seed', type=int, default=BOOT_SEED, help=f'bootstrap seed (registered {BOOT_SEED})')
    p.add_argument('--mc-flips', type=int, default=MC_FLIPS, help='Monte Carlo sign-flip cross-check size (>= 100000)')
    p.add_argument('--mc-seed', type=int, default=MC_SEED)
    p.add_argument('--allow-unverified-code', action='store_true',
                   help='use runs whose code_matches_prereg is empty (recorded as a deviation)')
    p.add_argument('--no-figures', action='store_true')
    p.add_argument('--png-dpi', type=int, default=600)
    args = p.parse_args(argv)
    if args.mc_flips < 100_000:
        p.error('--mc-flips must be at least 100000')
    if args.n_boot < 1000:
        p.error('--n-boot must be at least 1000')
    settings = Settings(args.n_boot, args.boot_seed, args.mc_flips, args.mc_seed, args.allow_unverified_code)
    deviations = []
    if (args.n_boot, args.boot_seed) != (N_BOOT, BOOT_SEED):
        deviations.append(f'bootstrap {args.n_boot} resamples, seed {args.boot_seed} (registered {N_BOOT}, '
                          f'{BOOT_SEED})')
    if args.allow_unverified_code:
        deviations.append('runs whose code match could not be verified are included (--allow-unverified-code)')

    rows, header = read_csv_rows(args.csv)
    out = analyze(rows, settings)
    results = out['results']
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    figures = {}
    if not args.no_figures:
        dose = dose_response_data(out['cells'], settings)
        figures['dose_response'] = plot_dose_response(dose, out_dir, args.png_dpi)
        figures['dose_response']['levels'] = {k: v['levels'] for k, v in dose.items()}
        figures['dose_response']['caption'] = (
            'Driving score (a) and route completion (b) of Fixed Deep per route (grey lines, paired across the '
            'conditions each route has) and their mean with a 95% percentile bootstrap CI over routes (colour), '
            'versus latency condition: synchronous oracle (subset E), kappa 1.0 and 1.5 (all routes), kappa 2.0 '
            '(subset C). Means use the routes available at each level (n below each level). The dashed segment '
            'joins the synchronous oracle (world paused) to measured latency: not a pure latency dose.')
        figures['contrast_forest'] = plot_forest(results, out_dir, args.png_dpi)
        figures['contrast_forest']['caption'] = (
            'Mean paired per-route difference A - B of driving score and route completion with 95% percentile '
            f'bootstrap CIs over routes ({settings.n_boot:,} resamples). Grey band: H2 equivalence margin (+-10 '
            'points). Bold: pre-registered primary contrasts (primary metric DS for H1 and H2, RC for H3).')

    script = Path(__file__).resolve()
    doc = {
        'schema': SCHEMA,
        'provenance': {'script': str(script), 'script_sha256': sha256_file(script), 'input_csv': str(args.csv),
                       'input_csv_sha256': sha256_file(args.csv), 'input_columns': len(header),
                       'created_utc': _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                       'argv': sys.argv if argv is None else list(argv), 'python': platform.python_version(),
                       'numpy': np.__version__},
        'settings': {'alpha': ALPHA, 'n_boot': settings.n_boot, 'boot_seed': settings.boot_seed,
                     'ci_levels': CI_LEVELS, 'bootstrap': 'percentile bootstrap of the mean over routes; fresh '
                     'numpy.random.default_rng(seed) per contrast and metric; indices rng.integers(0, n, (B, n))',
                     'sign_flip': {'statistic': '|sum_r d_r| (two-sided)', 'enumeration_max_n': ENUM_MAX_N,
                                   'dp_grid_by_metric': {m.key: m.grid for m in METRICS},
                                   'dp_max_bins': MAX_DP_BINS, 'tie_rtol': TIE_RTOL,
                                   'mc_cross_check_flips': settings.mc_flips, 'mc_seed': settings.mc_seed},
                     'equivalence_margin': EQUIV_MARGIN, 'holm_families': out['holm'],
                     'fallback_flag_pp': FALLBACK_FLAG_PP, 'allow_unverified_code': settings.allow_unverified_code,
                     'deviations_from_registered_settings': deviations},
        'design': {'routes': [{'index': i, 'route_id': rid, 'town': t, 'scenario_type': s,
                               'subsets': route_subsets(i)} for i, rid, t, s in ROUTES],
                   'subsets': SUBSETS, 'arms': {a.name: a.__dict__ for a in ARMS.values()},
                   'metrics': {m.key: m.__dict__ for m in METRICS}},
        'data_status': out['data_status'],
        'arms': out['arms'],
        'hypotheses': out['hypotheses'],
        'contrasts': {cid: {k: v for k, v in r.items() if k != 'route_rows'} for cid, r in results.items()},
        'replicate_agreement': out['replicate_agreement'],
        'manipulation_checks': out['manipulation_checks'],
        'per_scenario': {'descriptive_only': True, 'note': 'one route per scenario type; no per-scenario tests',
                         'routes': out['per_scenario']},
        'figures': figures,
    }
    tmp = out_dir / '.analysis.json.tmp'
    tmp.write_text(json.dumps(jsonable(doc), indent=1, allow_nan=False) + '\n', encoding='utf-8')
    tmp.replace(out_dir / 'analysis.json')
    crow = contrast_rows(results)
    write_csv(out_dir / 'contrasts.csv', crow, list(crow[0].keys()))
    prow = paired_rows(results)
    write_csv(out_dir / 'paired_differences.csv', prow, list(prow[0].keys()))
    cr = cell_rows(out['cells'])
    write_csv(out_dir / 'cells.csv', cr, list(cr[0].keys()))
    ar, acols = arm_rows(out['arms'])
    write_csv(out_dir / 'arms.csv', ar, acols)
    sr, scols = scenario_rows(out['per_scenario'])
    write_csv(out_dir / 'per_route_by_scenario.csv', sr, scols)

    ds = out['data_status']
    print(f'{ds["rows_total"]} CSV rows, {ds["cells_used"]}/{ds["cells_expected"]} registered cells used; '
          f'cell statuses {ds["cell_status_counts"]}')
    for h, v in out['hypotheses'].items():
        if h == 'H1':
            brief = '; '.join(f'{k}: {s["label"]} (n={s["n"]}/{s["n_expected"]})' for k, s in v['steps'].items())
            print(f'H1 [{v["completeness"]}] {v["overall"]}; {brief}')
        else:
            s = v['primary']
            print(f'{h} [{v["completeness"]}] {s["label"]} (n={s["n"]}/{s["n_expected"]})')
    if deviations:
        print('DEVIATIONS FROM REGISTERED SETTINGS: ' + '; '.join(deviations))
    print(f'-> {out_dir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
