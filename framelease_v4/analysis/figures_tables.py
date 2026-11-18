#!/usr/bin/env python3
"""Figures and tables of the v4 method paper (framelease_v4/PROTOCOL.md Secs. 7.1-7.6, 9.9, 9.13 and 4.8; GAP_AUDIT
Sec. 3.7 row R-6). CPU only (matplotlib, Agg backend); reads only the outputs of the analysis pipeline, writes only
under --out.

  cd /home/kang/Desktop/DAC
  CUDA_VISIBLE_DEVICES= .conda-unidrive-linux/bin/python -I -B framelease_v4/analysis/figures_tables.py --out DIR \
      [--analysis outputs/framelease_v4/analysis/final_<stamp>/analysis] \
      [--offline outputs/framelease_v4/offline_ablation] [--coverage PROP1_DIR] [--rl-freeze RL_FREEZE.json] \
      [--s1 S1.json] [--s2 S2.json] [--s2-relative S2_RELATIVE.json] [--s3 S3.json] [--d1 FULL_d1_summary.json] \
      [--only fig1 fig1_scenarios fig3 table1 table2a table2b table_train] [--fig3-layout double|single] \
      [--require-registered] [--force]

Sources. Every number a figure or table shows comes from one of these files and is written to numbers.json with its
source file, field and row selectors (Numbers); nothing is recomputed from run directories:
  --analysis   an output directory of analyze_v4.py: analysis.json (schema framelease_v4.analyze/1), SHA256SUMS and
               the tables (conditions.csv, per_ability.csv, paired_differences.csv, family_H1.csv, family_H2.csv,
               family_H3.csv, family_S-coll.csv, family_S-dmr.csv, family_F3.csv, family_H4-cl.csv,
               family_RL-abl.csv, h4_offline.csv, cells.csv). Every file read must equal its SHA256SUMS entry and its
               analysis.json 'outputs' entry.
  --offline    the offline ablation outputs (framelease_v4/offline, before registration): fig1/*.csv, panel (a) of
               Fig. 1 and the v2 closed-loop series of panel (b), fig1/fig1_check.json must pass; nested.csv and
               nested_folds.csv (Table II-A panel a); its paired.csv must be the one the analysis judged H4 with. Every
               file read must equal its OFFLINE_SHA256 entry (the outputs written before registration; the
               registration manifest does not list them), otherwise the run is development
  RND          framelease_v3/RND_REPORT_20261110.md, Table 3 (the cited RA rows of Table II-A): the file must equal its
               registration-manifest sha256 and every cited cell must be the one PROTOCOL Sec. 7.4 quotes
  --coverage   an output directory of prop1_coverage.py (coverage.json, coverage.csv, SHA256SUMS; no failed check)
  --rl-freeze  the RL freeze of p3_rl.py (rl_freeze.json; a production record is re-checked by p3_rl.load_rl_freeze
               with its Sec. 13.2 citation; rl_freeze_dev.json is development data); it must be the RL freeze the
               analysis read (rl_link: analysis.json decisions.H2.p_both, the rl_sha256 of its aggregations;
               exit 2 otherwise); given with an analysis that read none, it adds a development reason
  --s1, --s2, --s2-relative, --s3   reports of stress_bench.py (schema framelease_v4.stress_bench/1): S1, S2 on the
               registered grid, S2 on the supplementary grid relative to the slack floor (Amendment A7; refused in the
               --s2 slot and vice versa), S3 (must be the report the analysis judged H5 with, when it used one)
  --d1         the D1 training-route summary of d1_summary.py (schema framelease_v4.d1_summary/1, FULL, training
               routes only)
JSON sources are recorded with their key path (row {'json_path': [...]}). The outputs of aggregate_v4.py enter through
analyze_v4.py (conditions, contrasts, overhead, manipulation checks).

Interim looks (PROTOCOL Sec. 9.11: no test-route result is examined before the analysis freeze). Before any table of
an analysis is read, analysis_permission checks the analysis independently of its own records: the routes of its used
cells (cells.csv) are intersected with the registered test split (interim_guard.registered_split, its sha256 checked
against the registration manifest). An analysis with a result on a registered test route, or with test-route rows in
its guard document, is used only when its guard status is 'frozen' with a registered analysis-freeze record and that
record is still valid (interim_guard.load_freeze: cited in Sec. 13 of the sealed PROTOCOL.md); otherwise the request is
refused (exit 4). Every request, granted or refused, is logged in <out>/interim_guard.jsonl (interim_guard.log_request).
Synthetic analyses (synthetic route ids) and training-route analyses carry no test-route result and need no record.
The other sources are checked as well (source_permission): the RL dataset and the D1 summary are training data by
design and are refused when they hold a registered test route; a stress report on recorded decision states of a
registered test route (or run with --allow-test-routes) and a coverage run over guarded clips are used only together
with an analysis whose registered analysis-freeze record was verified.

Status. A run is 'registered' only when every source its items use is registered: the analysis (analysis.json
'status', analyze_v4.development_reasons), the offline outputs at their registered location, the coverage of the cited
tuning freeze on the 32 VAL clips with the registered bootstrap, the cited RL freeze, stress reports labelled
registered (S1 on an exclusive CPU) and the D1 summary at its registered path cited in Sec. 13; every other source, and
every optional source not given (its panel is left out), adds a development reason. The status and the reasons go into
numbers.json and figures.json. A figure of a development run carries the stamp DEV_STAMP across the plot, and a table
or a figure caption a LaTeX comment and the stamp in its caption; --require-registered refuses anything but registered
sources (exit 4). The figures and tables of the paper are made from registered sources only.

Style (IEEE two-column, IEEEtran): figure widths 3.5 in (column) and 7.16 in (text width), 8 pt Times-like type
(Times New Roman or its metric twin Liberation Serif; STIX mathematics), TrueType fonts embedded (pdf.fonttype 42),
vector PDF plus a 300 dpi PNG; no frame on top or right, a recessive grid, a panel letter with a short panel title
above each panel and no other text in the plot beyond labels and legends. One categorical palette (PALETTE, fixed
slot order, never cycled) serves every figure: an arm keeps its colour and marker in every figure (ARM_STYLE); the two
fixed-depth arms lend their colours to depth 1 (Fast Only) and depth 10 (Fixed Deep) in Fig. 1 and to the two poles of
the diverging scale of the scenario-type companion (Fixed Deep better / Fast Only better, neutral midpoint). Slots 1-3
and INK separate pairwise by at least 9 OKLab Delta E (x 100) under simulated protan, deutan and tritan vision and by
at least 24 in normal vision (tests/test_figures_tables.py); every series also has its own marker shape, so identity
never rests on colour alone. Outputs are byte-deterministic (no time stamps in PDF or PNG).

Fig. 1 (Sec. 7.1; descriptive, no test; double column):
  (a)  offline: execution error (m) against observation age for depths 1, 5 and 10 (C1 sweep R1m, W = 1 s, the 15
       held-out clips, Student-t 95% bands over clips; c1_age_vs_depth.csv), with markers at the release ages of
       Sec. 7.1 (unmodified prefix: depth 1 at 0.896 s, depth 10 at 1.027 s; fast prefix: depth 1 at 0.457 s, depth 10
       at 0.457 + 9 x 0.0146 s); the error at a release age is the linear interpolation between the two neighbouring
       ages of the curve (numbers.json records both rows)
  (b)  offline: Fast@Fresh - Deep@Old against kappa (c1_fresh_vs_deep_kappa.csv, held-out clips; the kappa sweep RKm,
       W = 0.5 s, with its t band, and the W = 1 s points of R1m)
  (c)  closed loop: the paired DS difference Fixed Deep - Fast Only by Bench2Drive ability (the official multi-label
       map) and over all routes: this work at kappa 1.0 (Table I runs, 44 routes) and kappa 1.5 / 2.0 (Fig. 3 runs, E),
       from the analysis (per_ability.csv, group 'depth'; 95% route-bootstrap intervals for at least 5 routes), next to
       the v2 matrix (unmodified prefix; closed_loop_ds_by_ability.csv at kappa 1.0 and 1.5 on 44 routes and
       closed_loop_kappa_trend.csv over all routes; at kappa 2.0, 11 exploratory routes, the per-ability means come
       from closed_loop_ds_by_route.csv, without interval), labelled as the earlier measurement ('earlier
       (unmodified prefix)'); a light rule separates the ability groups
  fig1_scenarios (companion of panel (c), single column): the same difference per scenario type (one route per type):
       this work from paired_differences.csv (the 'depth' contrasts), the earlier measurement from
       closed_loop_ds_by_route.csv; a cell without a paired route is hatched (explained in the caption). The colour
       bar spans the figure width in its own subfigure, its end labels under its ends. Forty-four named rows at 8 pt
       do not fit a panel of Fig. 1; the companion is placed as Fig. 1(d) or in the supplement.
Fig. 3 (Sec. 7.3; descriptive): mean DS against the mean per-route action-age p50 (a) and p95 (b) for Fixed Deep, Fast
  Only, FrameLease + Heuristic and Full FrameLease at kappa 1.0, 1.5 and 2.0 on subset E (the kappa-1.0 points are the
  Table I runs on E), one line per method through its three budgets, 95% route-bootstrap intervals on both axes
  (conditions.csv, statistic route_mean, subset E); every point is annotated with its EIR and GPU usage in panel (c)
  (FrameLease does not minimize action age: lower age is not read as better without the validity and budget columns).
  The background-load flag counts of every point's condition (Amendment A8; analysis.json manipulation) and the
  secondary F3 family (family_F3.csv: Full FrameLease - Fixed Deep and - Fast Only at kappa 1.5 and 2.0 on E, Holm over
  4; numbers fig3.f3.*) are in the caption. --fig3-layout single stacks (a), (b) and (c) in one column.
Captions: every figure has its caption as <stem>_caption.tex (the LaTeX caption and the label fig:<figure>, every
  number in numbers.json), to be input in the figure environment.
Table I (Sec. 7.2; table*, booktabs, caption above): one row per arm in the order of Sec. 4.1, 44 test routes, kappa
  1.0, seed 11 (conditions.csv subset all): DS with its 95% route-bootstrap interval, SR, collisions/km (arm-level
  pooled ratio with the route-cluster interval of Sec. 6.1), infractions/km, GPU usage, DMR, action age p50 / p95,
  fallback ratio, EIR and P_both (route means); arrows mark the registered directions only. The notes carry the
  collisions/km intervals, RC and closed-loop R_cond (Sec. 7.2), the four H1 contrasts (primary) with their
  Holm-adjusted p and label (family_H1.csv), the secondary families of Table I labelled secondary (Sec. 7.2
  'Contrasts. As in Sec. 9.': H3, Holm over 2; S-coll and S-dmr, Holm over 4), the n of every contrast and its dropped
  routes (Sec. 9.8), the background-load flag counts (Amendment A8) and a dagger for an arm with fewer than 44 routes.
  LaTeX cells are escaped (latex_escape), negative numbers are set with a typographic minus (tex_minus), a positive
  rate below the shown resolution as '< 0.01' (fmt_num floor); the table compiles with IEEEtran and booktabs alone.
Table II-A (Secs. 7.4, 7.5, 9.13; table*, panels stacked under one caption, numbered TABLE II-A; Table II-B, input
  right after it, is numbered TABLE II-B):
  (a)  offline lease ablation: Age-Only, Global-Margin and Suffix-Aligned at their nested leave-one-clip-out choice
       under rule (a) at R_cond <= 5% over all plans (nested.csv): R_cond with its 95% clip-bootstrap interval, R_marg,
       utilization, premature refresh and continuity at the needs 0.964 s and 1.842 s (each need its own nested
       choice); the plan, conflict and clip counts; the H4 offline primary row of the analysis in the notes, labelled
       'pre-specified in code, executed before registration'; below a rule the four cited RND rows (RA and standard
       validity, model detections and oracle boxes: continuity and realized R_cond with their intervals), each marked
       (section mark) as another setting and, for RA, a definition change, never compared statistically with the rows
       above
  (b)  Proposition 1: per deployed envelope (L* and the fl_risk point after the tuning freeze, every kept candidate
       before it, with its role) and class (vehicle, pedestrian) the per-tau coverage at 0, 1, 2 and 3 s and the
       whole-path coverage on [0, 3 s] with its 95% clip-bootstrap interval and pair count (coverage.csv); stated as
       an empirical coverage, not a guarantee (Sec. 9.13)
  (c)  closed-loop lease panel: Age-Only, Global-Margin and Suffix-Aligned leases on E at kappa 1.0, seed 11 (the same
       shield and utility): DS with its interval, fallback ratio, DMR, lease utilization, premature expiry, EIR,
       closed-loop R_cond and P_both (conditions.csv, subset E); the H4-cl contrasts (family_H4-cl.csv) in the notes
  (d)  RL panel: Shield + Heuristic, Contextual Bandit, FQI (Full FrameLease) and FQI without lease features on E: DS,
       P_both, deviation and bypass rates (conditions.csv), the Q-network p50 / p99 of the condition (analysis.json
       overhead: median over its runs of the per-run quantiles) and the FQE estimate with its 90% route-cluster
       interval of each family's selected candidate (the RL freeze; 'ref.' for the heuristic, the reference of the
       estimate; a double dagger for a family that is not trainable); in the notes the RL-abl and H2 contrasts, the
       H2 RL-benefit statement and the P_both of the RL dataset with its Sec. 5.8 label as the analysis read them
       (analysis.json decisions.H2), and the breakdown of the RL gain (Sec. 7.5: Full FrameLease - FrameLease +
       Heuristic by ability on the 44 routes, by kappa on E, by seed on R; analysis.json rl_gain; tab2a.rl_gain.*)
  A dagger after a closed-loop value marks fewer routes than the subset. Without --coverage panel (b) is left out;
  without --rl-freeze the FQE column is empty; the dataset P_both is absent when the analysis read no RL freeze.
Table II-B (Sec. 7.6; table*, panels):
  (a)  from the logs (analysis.json overhead): the shield arms of Table I at kappa 1.0 and the Fig. 3 runs at kappa 2.0
       (GPU contention, S4): runs, CPU Q-network p50 / p99 and the runs whose p99 exceeds B_pi, bypass epochs and rate,
       shield decision and lease p50 / p99, the GPU quanta (charged prefix, flow step) p50 / p99, switching latency,
       cancelled GPU work, release-to-commit validation p50 / p99, commit-gate rejects (reasons in the notes), DMR,
       fallback episodes, shield violations and budget overruns; per-run quantiles are never pooled across runs (the
       median over the runs is shown); the commit audit (Eq. 9) and the H5 label in the notes
  (b)  S1 per load level (0, 4, 8, 15 busy processes): p50 / p99 / max of the Q-network call (the FQI network) with its
       overrun rate against B_pi, shield + decision with that network, the lease and the commit check
  (c)  S2 per deployed network: share admitted, admitted actions with bound >= D* (must be 0), bypass rate and its
       near-deadline and CPU-timing parts, violations, on the registered grid and, labelled 'Supplementary (A7)', on
       the grid relative to each state's slack floor (with its floor check); never in place of the registered grid
  (d)  S3 per target (commit gate, V4Runtime commit path): sequences, offers, accepted commits, Eq. 9 violations (must
       be 0) and the fault-class coverage
  A stress panel without its report is left out (development).
Training-route operating-point table (Secs. 4.2-4.8, 9.13; table*, supplement): every candidate of every Phase-1
  block of the D1 summary, block by block (grid, stage, route set, kept / all routes, pending jobs, set-up flags): the
  selection statistic (mean DS over the kept routes), DS, RC, SR, fallback ratio, DMR and EIR over valid runs, pooled
  closed-loop R_cond and P_both, with the stage selection marked (selected, survivor); the notes list the run outcomes
  other than ok, the dropped routes with their reasons, the set-up failure flags (Sec. 4.8) and the tuning freeze; it
  discloses the DS-risk position of the selected lease point. Training routes only.

numbers.json (schema NUMBERS_SCHEMA): {'status', 'development', 'sources': {path: sha256}, 'numbers': {key: {'value',
'shown' (the text as printed, None for a plotted position), 'source', 'field', 'row' (the selectors of the source row),
'derivation' (only for a number computed here: an interpolation or a mean over named rows)}}}. A key is never written
twice with different values.

Outputs (under --out): <figure>.pdf, <figure>.png and <figure>_caption.tex per figure, <table>.tex per table (table1,
table2a, table2b, table_train), numbers.json, figures.json (schema SCHEMA: arguments, status, the source paths, every
figure and table with its sources and number count, the sha256 of every input, of every output and of this script)
and SHA256SUMS (all of these); interim_guard.jsonl (append-only, not in SHA256SUMS). Nothing is written before every
number is computed (build, then render).

Exit codes: 0 written, 1 refused (outputs exist without --force, protected directory, an input directory itself),
2 inconsistent inputs (nothing written), 4 refused by the interim-look guard or by --require-registered (logged).
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('MPLBACKEND', 'Agg')
sys.dont_write_bytecode = True

import argparse  # noqa: E402
import csv  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import re  # noqa: E402
from pathlib import Path  # noqa: E402

import matplotlib  # noqa: E402

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, Normalize  # noqa: E402
from matplotlib.legend_handler import HandlerTuple  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.transforms import offset_copy  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v4.analysis import analyze_v4 as AN  # noqa: E402
from framelease_v4.analysis import interim_guard as G  # noqa: E402
from framelease_v4.offline import fig1_data as F1  # noqa: E402
from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402

SCHEMA = 'framelease_v4.figures_tables/1'
NUMBERS_SCHEMA = 'framelease_v4.figures_tables_numbers/1'
THIS_REL = 'framelease_v4/analysis/figures_tables.py'
OFFLINE_REL = 'outputs/framelease_v4/offline_ablation'
FIG1_REL = 'fig1'
ANALYSIS_TABLES = ('conditions.csv', 'per_ability.csv', 'paired_differences.csv', 'family_H1.csv', 'family_H2.csv',
                   'family_H3.csv', 'family_S-coll.csv', 'family_S-dmr.csv', 'family_F3.csv', 'family_H4-cl.csv',
                   'family_RL-abl.csv', 'h4_offline.csv', 'cells.csv')
# the offline outputs this script reads, as written on 2026-11-10 before registration (framelease_v4/offline; no
# manifest of their own: the registration manifest lists frontier.csv and envelopes/train_E0.json only); a file that
# differs makes the run development. paired.csv is in addition the file the analysis judged H4 offline with.
OFFLINE_SHA256 = {
    'nested.csv': 'b6e922ffda3afc9deb8a99448899f920d9ad43643907ecb988e37d77f8931b9f',
    'nested_folds.csv': '57e11eb5b4100d7180da988115c61cc65c0d7c5e315ab96fd048e1a7736742aa',
    'paired.csv': '357c7fcd9c3e0d29eb297d08a8b38a08a089d5d2a6a680e89e200fd8ee664b77',
    'fig1/c1_age_vs_depth.csv': 'e181a85821ecc01769cdbf62a89d2d758ab3faa8cb004981101368c48bd5eac2',
    'fig1/c1_fresh_vs_deep_kappa.csv': '62b089a78510cb30b5b3e81db116203a6e7603930d0f30599d38d353883c0794',
    'fig1/closed_loop_ds_by_ability.csv': '76073a44974e742e77c004377333c68f4afa22826311f0b67cf3551a1b1da119',
    'fig1/closed_loop_ds_by_route.csv': '69ff9a63a82cd7c10c314d5247cf5c0e9042b138d142dd0dd3b55c10d7f28784',
    'fig1/closed_loop_kappa_trend.csv': 'a6dcc4529aa8a6c0231c7314f3b680575d3f20d41beca4af849c8deda05f9f2d',
    'fig1/fig1_check.json': 'a6e3aa97ee7f0c91abb651a6e1ce999dedd5663a61d9236e6bbb43a4fa6f96da',
}
REGISTERED, DEVELOPMENT = 'registered', 'development'
DEV_STAMP = 'DEVELOPMENT DATA - not for the paper'

# ---------------------------------------------------------------------------------------------- IEEE geometry, type
COL_W_IN, DCOL_W_IN = 3.5, 7.16          # IEEEtran \columnwidth and \textwidth
FONT_PT = 8
PNG_DPI = 300
LINE_W, ERR_W, AX_W = 1.0, 0.6, 0.5      # data lines, error bars, axes (pt)
MARKER_PT = 4.0

# ---------------------------------------------------------------------------------------------- palette (all figures)
PALETTE = ('#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948')
INK, INK_2, MUTED = '#0b0b0b', '#52514e', '#898781'      # primary text / hero series, secondary text, muted
GRID_C, AXIS_C, NEUTRAL = '#e1e0d9', '#898781', '#f0efec'
DEV_C = '#e34948'
# an arm keeps its colour and marker in every figure (Fig. 3 plots these four; Table I has no colour)
ARM_STYLE = {
    'fixed_deep': (PALETTE[0], 's'),
    'fast_only': (PALETTE[1], 'o'),
    'fl_heuristic': (PALETTE[2], '^'),
    'fl_full': (INK, 'D'),
}
ARM_LABEL = {
    'fixed_deep': 'Fixed Deep', 'fast_only': 'Fast Only', 'age_only': 'Age-Only', 'event_triggered': 'Event-Triggered',
    'fl_original': 'Original FrameLease', 'fl_heuristic': 'FrameLease + Heuristic', 'fl_full': 'Full FrameLease',
    'fl_global_shield': 'Global-Margin lease', 'fl_bandit': 'Contextual Bandit',
    'fl_fqi_nolease': 'FQI w/o lease features', 'fl_risk': 'FrameLease + Heuristic (risk point)',
}
# Fig. 1: depth 1 is the Fast Only prefix depth, depth 10 the Fixed Deep depth; depth 5 is neutral
DEPTH_STYLE = {1: (PALETTE[1], 'o', '-'), 5: (MUTED, None, ':'), 10: (PALETTE[0], 's', '-')}
# kappa (GPU share 1 / kappa): marker shape in Fig. 1(c), marker fill in Fig. 3
KAPPAS = (1.0, 1.5, 2.0)
KAPPA_SHARE = {1.0: '100%', 1.5: '67%', 2.0: '50%'}
KAPPA_MARKER = {1.0: 'o', 1.5: 's', 2.0: '^'}
KAPPA_FILL = {1.0: 'full', 1.5: 'left', 2.0: 'none'}
# diverging scale of DS differences Fixed Deep - Fast Only: Fast Only better (orange) ... Fixed Deep better (blue)
DIVERGING = ('#a9441b', PALETTE[1], NEUTRAL, PALETTE[0], '#184f95')
MISSING_C = '#ffffff'

# ---------------------------------------------------------------------------------------------- Fig. 1 (Sec. 7.1)
FIG1_AGE_RUN = {'run': 'R1m', 'window_s': '1', 'split': 'val'}           # C1 sweep, W = 1 s, 15 held-out clips
FIG1_KAPPA_RUNS = ({'run': 'RKm', 'window_s': '0.5', 'split': 'val'},    # the kappa sweep (line and band)
                   {'run': 'R1m', 'window_s': '1', 'split': 'val'})      # W = 1 s at kappa 1.0 and 1.5 (points)
FIG1_KAPPA_QUANTITY = 'fast_fresh_minus_deep_old'
FAST_STEP_S = 0.0146
# release ages (Sec. 7.1): (prefix, depth, age in s, how the protocol states it)
RELEASE_AGES = (('unmodified', 1, 0.896, 'PROTOCOL Sec. 7.1: unmodified prefix, depth 1 at 0.896 s'),
                ('unmodified', 10, 1.027, 'PROTOCOL Sec. 7.1: unmodified prefix, depth 10 at 1.027 s'),
                ('fast', 1, 0.457, 'PROTOCOL Sec. 7.1: fast prefix, depth 1 at 0.457 s'),
                ('fast', 10, round(0.457 + 9 * FAST_STEP_S, 4),
                 'PROTOCOL Sec. 7.1: fast prefix, depth 10 at about 0.59 s (0.457 + 9 x 0.0146 s)'))
ABILITY_ROWS = F1.ABILITIES + ('all',)
ABILITY_LABEL = {'Merging': 'Merging', 'Overtaking': 'Overtaking', 'Emergency_Brake': 'Emergency brake',
                 'Give_Way': 'Give way', 'Traffic_Signs': 'Traffic signs', 'all': 'All routes'}
# this work: the 'depth' contrasts of analyze_v4 (Table I runs at kappa 1.0, the Fig. 3 runs on E at 1.5 and 2.0)
DEPTH_CONTRASTS = {d.contrast.a.kappa: d.contrast for d in AN.DESCRIPTIVE_CONTRASTS if d.group == 'depth'}
# v2: the series of closed_loop_ds_by_ability.csv and the columns of closed_loop_ds_by_route.csv
V2_ABILITY_SERIES = {1.0: 'seed 11', 1.5: 'kappa 1.5, seed 11'}
V2_ROUTE_COLUMN = {1.0: 'DS_diff_k1.0_s11', 1.5: 'DS_diff_k1.5_s11', 2.0: 'DS_diff_k2.0_s11'}
V2_TREND_K2 = {'kappa': '2', 'seed': '11', 'metric': 'driving_score'}     # the kappa-2.0 row over all 11 routes

# ---------------------------------------------------------------------------------------------- Fig. 3 (Sec. 7.3)
FIG3_ARMS = ('fixed_deep', 'fast_only', 'fl_heuristic', 'fl_full')
FIG3_SUBSET, FIG3_SEED = 'E', 11
FIG3_X = {'p50': 'action_age_p50_s', 'p95': 'action_age_p95_s'}
FIG3_Y = 'driving_score'
FIG3_NOTES = ('eir', 'gpu_usage')

# never an output directory: the code tree, the registered and other phases' outputs, and this tool's inputs
PROTECTED = AN.A.PROTECTED + ('outputs/framelease_v2', 'outputs/framelease_v3', OFFLINE_REL,
                              'outputs/framelease_v4/phase_driver')
PROTECTED_PREFIXES = AN.A.PROTECTED_PREFIXES
OUTPUT_META = ('numbers.json', 'figures.json', 'SHA256SUMS')

GuardRefused = G.GuardRefused        # a request the Sec. 9.11 guard refuses (interim_guard.py): exit 4, logged


class FigureError(RuntimeError):
    """Inconsistent inputs (files that differ from their manifests, missing rows, schema): nothing is written."""


# ============================================================================================ numbers.json registry

def _num(x):
    """A float from a CSV / JSON field; None for '', None, 'nan' or a non-finite value."""
    if x is None or x == '':
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


class Numbers:
    """The numbers.json registry: every number a figure or table shows, key -> {'value', 'shown', 'source', 'field',
    'row', 'derivation'}, plus the sha256 of every source file (sources). add() refuses a key written twice with
    different contents (ValueError)."""

    def __init__(self):
        self.items = {}
        self.sources = {}

    def source(self, path):
        """Register a source file; returns its repository-relative path."""
        rel = PJ.rel(Path(path))
        if rel not in self.sources:
            self.sources[rel] = PJ.sha256_file(Path(path))
        return rel

    def add(self, key, value, source, field, row=None, shown=None, derivation=None):
        """Record key; value is a JSON number, string or None (a missing value). Returns value."""
        if isinstance(value, float) and not math.isfinite(value):
            value = None
        path = None if source is None else Path(source) if Path(source).is_absolute() else ROOT / source
        src = None if path is None else self.source(path) if path.is_file() else str(source)
        entry = {'value': value, 'shown': shown, 'source': src, 'field': field,
                 'row': dict(row) if row else {}}
        if derivation:
            entry['derivation'] = derivation
        old = self.items.get(key)
        if old is not None and old != entry:
            raise ValueError(f'numbers.json key {key!r} written twice with different contents: {old} != {entry}')
        self.items[key] = entry
        return value

    def doc(self, status, development):
        return {'schema': NUMBERS_SCHEMA, 'status': status, 'development': list(development),
                'sources': dict(sorted(self.sources.items())), 'numbers': dict(sorted(self.items.items()))}


# ============================================================================================ inputs

def read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def select(rows, **where):
    """The rows whose fields equal where (string comparison)."""
    return [r for r in rows if all(r.get(k) == str(v) for k, v in where.items())]


def select_one(rows, what, **where):
    """The one row matching where; FigureError when there is none or more than one."""
    hit = select(rows, **where)
    if len(hit) != 1:
        raise FigureError(f'{what}: {len(hit)} rows match {where} (expected 1)')
    return hit[0]


def load_analysis(path):
    """An analyze_v4.py output directory: {'path', 'dir', 'doc' (analysis.json), 'sums' (SHA256SUMS)}. analysis.json
    and SHA256SUMS must exist, every SHA256SUMS entry must equal its file, analysis.json must carry the schema of
    analyze_v4.py and its 'outputs' must agree with SHA256SUMS; FigureError otherwise. No table is read here."""
    d = Path(path)
    absent = [n for n in ('analysis.json', 'SHA256SUMS') if not (d / n).is_file()]
    if absent:
        raise FigureError(f'{PJ.rel(d)}: not an analysis directory (no {absent})')
    try:
        sums = AN.read_sums(d / 'SHA256SUMS')
    except AN.AnalysisError as e:
        raise FigureError(str(e)) from None
    bad = [n for n, sha in sums.items() if not (d / n).is_file() or PJ.sha256_file(d / n) != sha]
    if bad or 'analysis.json' not in sums:
        raise FigureError(f'{PJ.rel(d)}: SHA256SUMS entries {bad or ["analysis.json missing"]} do not match the files '
                          '(changed after the analysis)')
    try:
        doc = json.loads((d / 'analysis.json').read_text(encoding='utf-8'))
    except ValueError as e:
        raise FigureError(f'{PJ.rel(d)}/analysis.json: not JSON ({e})') from None
    if not isinstance(doc, dict) or doc.get('schema') != AN.SCHEMA:
        raise FigureError(f'{PJ.rel(d)}/analysis.json: not an analysis (schema {AN.SCHEMA})')
    outs = doc.get('outputs') if isinstance(doc.get('outputs'), dict) else {}
    differ = sorted(n for n, sha in outs.items() if sums.get(n) != sha)
    if differ:
        raise FigureError(f'{PJ.rel(d)}: analysis.json outputs {differ} differ from SHA256SUMS')
    return {'path': PJ.rel(d), 'dir': d, 'doc': doc, 'sums': sums}


def analysis_table(src, name, nums=None):
    """The rows of one table of a loaded analysis (ANALYSIS_TABLES), after checking that the file still equals its
    SHA256SUMS and analysis.json 'outputs' entries; registers it as a numbers.json source."""
    if name not in ANALYSIS_TABLES:
        raise ValueError(f'{name} is not a table this script reads ({ANALYSIS_TABLES})')
    path = src['dir'] / name
    sha = PJ.sha256_file(path) if path.is_file() else None
    want = (src['sums'].get(name), (src['doc'].get('outputs') or {}).get(name))
    if sha is None or want != (sha, sha):
        raise FigureError(f'{PJ.rel(path)}: sha256 {sha} does not equal SHA256SUMS / analysis.json outputs {want}')
    if nums is not None:
        nums.source(path)
    return read_csv(path)


def used_routes(src):
    """The route ids of the cells a loaded analysis used (cells.csv status 'used')."""
    return {r['route_id'] for r in analysis_table(src, 'cells.csv') if r.get('status') == 'used'}


def _verify_freeze(fz):
    """interim_guard.load_freeze on the record an analysis's guard document names (its PROTOCOL.md, seal and required
    job files); GuardRefused when the record is no longer valid or its sha256 changed."""
    p = lambda x: Path(x) if Path(x).is_absolute() else ROOT / x  # noqa: E731
    rec = G.load_freeze(p(fz['path']), protocol=p(fz['protocol']), seal=p(fz['seal']),
                        required_job_files=fz.get('required_job_files'))
    if rec['sha256'] != fz.get('sha256'):
        raise GuardRefused(f'analysis-freeze record {rec["path"]}: sha256 {rec["sha256"]} is not the '
                           f'{fz.get("sha256")} the analysis was made with ({G.RULE})')
    return rec


def analysis_permission(src, registered=None, require_registered=False):
    """(status, development reasons, scope) of a loaded analysis for figures and tables (PROTOCOL Sec. 9.11), or
    GuardRefused. Results on registered test routes are present when a used cell lies on a route of the registered
    split (registered: its test route ids, default interim_guard.registered_split()); they are used only when the
    analysis's guard status is 'frozen' and its record, read again from its files (interim_guard.load_freeze), is
    valid, has the same sha256 and is cited by the registered PROTOCOL.md. Test-route rows of a development record
    (extra routes outside the registered split, guard status 'frozen_development') need a valid record as well.
    require_registered: GuardRefused for a development analysis (the paper's figures). FigureError when the status is
    neither 'registered' nor 'development' or contradicts the development reasons."""
    doc = src['doc']
    guard = doc.get('interim_guard') if isinstance(doc.get('interim_guard'), dict) else {}
    reg = G.registered_split()['test'] if registered is None else {str(r) for r in registered}
    hit = sorted(used_routes(src) & reg)
    test_rows = int(guard.get('test_input_rows') or 0) + int(guard.get('released_rows') or 0)
    fz = guard.get('freeze') if isinstance(guard.get('freeze'), dict) else None
    scope = {'registered_test_routes_used': len(hit), 'guard_status': guard.get('status'),
             'guard_test_input_rows': guard.get('test_input_rows'), 'guard_released_rows': guard.get('released_rows'),
             'analysis_scope': doc.get('scope'), 'freeze': None}
    if hit or test_rows:
        what = (f'{src["path"]}: results on test routes ({len(hit)} registered test routes used, e.g. {hit[:3]}; '
                f'{test_rows} test-route rows in the guard document)')
        if hit and (guard.get('status') != 'frozen' or not fz or not fz.get('registered')):
            raise GuardRefused(f'{what} without a registered analysis-freeze record (guard status '
                               f'{guard.get("status")!r}) ({G.RULE})')
        if not fz or guard.get('status') not in ('frozen', 'frozen_development'):
            raise GuardRefused(f'{what} without an analysis-freeze record (guard status {guard.get("status")!r}) '
                               f'({G.RULE})')
        rec = _verify_freeze(fz)
        if hit and not rec['registered']:
            raise GuardRefused(f'{what}: the record is cited by a development copy of PROTOCOL.md ({G.RULE})')
        scope['freeze'] = {'path': rec['path'], 'sha256': rec['sha256'], 'frozen': rec['frozen'],
                           'registered': rec['registered']}
    status = doc.get('status')
    dev = [str(x) for x in (doc.get('development') or [])]
    if status not in (REGISTERED, DEVELOPMENT) or (status == REGISTERED) == bool(dev):
        raise FigureError(f'{src["path"]}/analysis.json: status {status!r} with {len(dev)} development reasons')
    if require_registered and status != REGISTERED:
        more = ' ...' if len(dev) > 2 else ''
        raise GuardRefused(f'{src["path"]}: a development analysis ({"; ".join(dev[:2])}{more}); '
                           '--require-registered accepts only the registered analysis')
    return status, dev, scope


FIG1_FILES = ('c1_age_vs_depth.csv', 'c1_fresh_vs_deep_kappa.csv', 'closed_loop_ds_by_ability.csv',
              'closed_loop_ds_by_route.csv', 'closed_loop_kappa_trend.csv')


def load_offline(path=None, nums=None):
    """The Fig. 1 files of the offline ablation (<path>/fig1/, FIG1_FILES): {'dir', 'tables': {name: rows}}.
    fig1/fig1_check.json (fig1_data.py's reproduction checks) must report pass = true; FigureError otherwise. Every
    file read is registered as a numbers.json source."""
    d = (Path(path) if path is not None else ROOT / OFFLINE_REL) / FIG1_REL
    check = d / 'fig1_check.json'
    try:
        ok = json.loads(check.read_text(encoding='utf-8')).get('pass') is True
    except (OSError, ValueError, AttributeError):
        ok = False
    if not ok:
        raise FigureError(f'{PJ.rel(check)}: missing or not passed (fig1_data.py checks)')
    absent = [n for n in FIG1_FILES if not (d / n).is_file()]
    if absent:
        raise FigureError(f'{PJ.rel(d)}: missing {absent}')
    if nums is not None:
        nums.source(check)
        for n in FIG1_FILES:
            nums.source(d / n)
    return {'dir': d, 'tables': {n: read_csv(d / n) for n in FIG1_FILES}}


# the offline files each item reads (relative to the offline directory)
OFFLINE_ITEM_FILES = {'fig1': tuple(f'{FIG1_REL}/{n}' for n in FIG1_FILES + ('fig1_check.json',)),
                      'table2a': ('nested.csv', 'nested_folds.csv', 'paired.csv')}
OFFLINE_ITEM_FILES['fig1_scenarios'] = OFFLINE_ITEM_FILES['fig1']


def offline_development(path, figures):
    """The development reasons of the offline outputs the items read: a directory other than the registered one, and
    every file that is absent or differs from OFFLINE_SHA256 (the outputs of 2026-11-10)."""
    d = Path(path) if path is not None else ROOT / OFFLINE_REL
    dev = []
    if d.resolve() != (ROOT / OFFLINE_REL).resolve():
        dev.append(f'offline outputs from {PJ.rel(d)}, not the registered {OFFLINE_REL}')
    names = sorted({n for f in figures for n in OFFLINE_ITEM_FILES.get(f, ())})
    for n in names:
        sha = PJ.sha256_file(d / n) if (d / n).is_file() else None
        if sha != OFFLINE_SHA256[n]:
            dev.append(f'{PJ.rel(d / n)}: sha256 {sha} is not the {OFFLINE_SHA256[n][:12]} of the offline outputs '
                       'written before registration (OFFLINE_SHA256)')
    return dev


# ============================================================================================ style and saving

def rc_params():
    """matplotlib settings of every figure: IEEE type (8 pt Times-like serif, TrueType embedded), thin recessive axes,
    the fixed palette order."""
    return {
        'font.family': 'serif', 'font.serif': ['Times New Roman', 'Liberation Serif', 'STIXGeneral', 'DejaVu Serif'],
        'mathtext.fontset': 'stix', 'font.size': FONT_PT, 'axes.titlesize': FONT_PT, 'axes.labelsize': FONT_PT,
        'xtick.labelsize': FONT_PT, 'ytick.labelsize': FONT_PT, 'legend.fontsize': FONT_PT,
        'legend.title_fontsize': FONT_PT, 'figure.titlesize': FONT_PT,
        'text.color': INK, 'axes.labelcolor': INK, 'axes.edgecolor': AXIS_C, 'axes.linewidth': AX_W,
        'axes.spines.top': False, 'axes.spines.right': False, 'axes.titlelocation': 'left', 'axes.titlepad': 3.0,
        'axes.prop_cycle': matplotlib.cycler(color=list(PALETTE)), 'axes.axisbelow': True,
        'axes.grid': False, 'grid.color': GRID_C, 'grid.linewidth': 0.4,
        'xtick.color': AXIS_C, 'ytick.color': AXIS_C, 'xtick.labelcolor': INK_2, 'ytick.labelcolor': INK_2,
        'xtick.major.width': AX_W, 'ytick.major.width': AX_W, 'xtick.major.size': 2.5, 'ytick.major.size': 2.5,
        'xtick.major.pad': 2.0, 'ytick.major.pad': 2.0, 'axes.labelpad': 2.0,
        'lines.linewidth': LINE_W, 'lines.markersize': MARKER_PT, 'lines.markeredgewidth': 0.6,
        'errorbar.capsize': 0, 'hatch.linewidth': 0.4, 'hatch.color': MUTED,
        'legend.frameon': False, 'legend.handlelength': 1.6, 'legend.handletextpad': 0.4, 'legend.borderpad': 0.2,
        'legend.labelspacing': 0.25, 'legend.columnspacing': 0.8, 'legend.borderaxespad': 0.2,
        'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none', 'figure.dpi': 100, 'savefig.dpi': PNG_DPI,
        'savefig.bbox': None, 'savefig.pad_inches': 0.0, 'savefig.facecolor': 'white', 'figure.facecolor': 'white',
    }


def dev_stamp(fig):
    """The development stamp across a figure that is not made from the registered analysis; in a figure with
    subfigures (drawn after the figure's own artists) it belongs to the last subfigure, placed in figure coordinates,
    so that it stays on top."""
    size = min(2.0 * FONT_PT, 1.5 * 72.0 * fig.get_figwidth() / len(DEV_STAMP))
    owner = fig.subfigs[-1] if getattr(fig, 'subfigs', None) else fig
    owner.text(0.5, 0.5, DEV_STAMP, transform=fig.transFigure, ha='center', va='center', rotation=12,
               fontsize=size, color=DEV_C, alpha=0.35, zorder=1000)


def save_figure(fig, out, name, status):
    """<name>.pdf (vector) and <name>.png (PNG_DPI) under out, byte-deterministic (no creation date, no software
    tag), with the development stamp unless status is 'registered'; the figure is closed. Returns the file names."""
    if status != REGISTERED:
        dev_stamp(fig)
    names = []
    for ext, kw in (('pdf', {'metadata': {'CreationDate': None, 'ModDate': None, 'Creator': THIS_REL}}),
                    ('png', {'metadata': {'Software': None}, 'dpi': PNG_DPI})):
        path = Path(out) / f'{name}.{ext}'
        tmp = Path(str(path) + '.tmp')
        fig.savefig(tmp, format=ext, **kw)
        tmp.replace(path)
        names.append(path.name)
    plt.close(fig)
    return names


def _ax_style(ax, grid_axis='y'):
    """Recessive grid on one axis, ticks outward."""
    if grid_axis:
        ax.grid(True, axis=grid_axis, color=GRID_C, linewidth=0.4)
    ax.tick_params(direction='out')


def _zero_line(ax, orientation='h'):
    (ax.axhline if orientation == 'h' else ax.axvline)(0.0, color=MUTED, linewidth=AX_W, zorder=1)


# ============================================================================================ Fig. 1 data (Sec. 7.1)

def fig1_age_curves(offline, nums):
    """{depth: {'age', 'mean', 'lo', 'hi' (lists, by age), 'n_clips'}} of the C1 sweep FIG1_AGE_RUN
    (c1_age_vs_depth.csv), every point recorded in nums (fig1.a.depth<d>.age<a>.mean / lo / hi)."""
    src = offline['dir'] / 'c1_age_vs_depth.csv'
    rows = select(offline['tables']['c1_age_vs_depth.csv'], **FIG1_AGE_RUN)
    out = {}
    for depth in F1.DEPTHS:
        rs = sorted(select(rows, depth=depth), key=lambda r: float(r['age_s']))
        if not rs:
            raise FigureError(f'{PJ.rel(src)}: no rows for {FIG1_AGE_RUN} depth {depth}')
        c = {'age': [], 'mean': [], 'lo': [], 'hi': [], 'n_clips': sorted({int(r['n_clips']) for r in rs})}
        for r in rs:
            where = {**FIG1_AGE_RUN, 'depth': depth, 'age_s': r['age_s']}
            c['age'].append(float(r['age_s']))
            for k, field in (('mean', 'exec_err_mean_m'), ('lo', 't95_lo'), ('hi', 't95_hi')):
                c[k].append(nums.add(f'fig1.a.depth{depth}.age{r["age_s"]}.{k}', _num(r[field]), src, field, where))
        nums.add(f'fig1.a.depth{depth}.n_clips', c['n_clips'][0] if len(c['n_clips']) == 1 else None, src, 'n_clips',
                 {**FIG1_AGE_RUN, 'depth': depth}, shown=str(c['n_clips'][0]) if len(c['n_clips']) == 1 else None,
                 derivation=f'the one n_clips value of the {len(rs)} rows of the curve (None if they differ)')
        out[depth] = c
    return out


def interpolate(xs, ys, x):
    """(y, x0, x1): linear interpolation of the curve (xs ascending) at x; ValueError outside the curve."""
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            w = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + w * (ys[i + 1] - ys[i]), xs[i], xs[i + 1]
    raise ValueError(f'{x} outside [{xs[0]}, {xs[-1]}]')


def fig1_release_points(curves, nums, offline):
    """[{'prefix', 'depth', 'age', 'error'}] of RELEASE_AGES: the age from PROTOCOL Sec. 7.1, the error interpolated
    on the depth's mean curve (recorded with both neighbouring rows as the derivation)."""
    src = offline['dir'] / 'c1_age_vs_depth.csv'
    out = []
    for prefix, depth, age, cite in RELEASE_AGES:
        c = curves[depth]
        err, a0, a1 = interpolate(c['age'], c['mean'], age)
        base = f'fig1.a.release.{prefix}.depth{depth}'
        nums.add(f'{base}.age_s', age, 'framelease_v4/PROTOCOL.md', 'Sec. 7.1', {'text': cite})
        nums.add(f'{base}.error_m', err, src, 'exec_err_mean_m', {**FIG1_AGE_RUN, 'depth': depth, 'age_s': [a0, a1]},
                 derivation=f'linear interpolation at age {age} s between the rows at {a0:g} s and {a1:g} s')
        out.append({'prefix': prefix, 'depth': depth, 'age': age, 'error': err})
    return out


def fig1_kappa_contrast(offline, nums):
    """[{'where', 'kappa', 'value', 'lo', 'hi', 'n_clips', 'clips_neg'} lists per FIG1_KAPPA_RUNS] of Fast@Fresh -
    Deep@Old against kappa (c1_fresh_vs_deep_kappa.csv, quantity FIG1_KAPPA_QUANTITY), recorded in nums
    (fig1.b.<run>.kappa<k>.value / lo / hi / clips_fresh_better)."""
    src = offline['dir'] / 'c1_fresh_vs_deep_kappa.csv'
    out = []
    for run in FIG1_KAPPA_RUNS:
        rs = sorted(select(offline['tables']['c1_fresh_vs_deep_kappa.csv'], quantity=FIG1_KAPPA_QUANTITY, **run),
                    key=lambda r: float(r['kappa']))
        if not rs:
            raise FigureError(f'{PJ.rel(src)}: no {FIG1_KAPPA_QUANTITY} rows for {run}')
        s = {'where': run, 'kappa': [], 'value': [], 'lo': [], 'hi': [], 'n_clips': [], 'clips_neg': []}
        for r in rs:
            where = {**run, 'quantity': FIG1_KAPPA_QUANTITY, 'kappa': r['kappa']}
            base = f'fig1.b.{run["run"]}.kappa{r["kappa"]}'
            s['kappa'].append(float(r['kappa']))
            for k, field in (('value', 'value_m'), ('lo', 't95_lo'), ('hi', 't95_hi')):
                s[k].append(nums.add(f'{base}.{k}', _num(r[field]), src, field, where))
            s['n_clips'].append(nums.add(f'{base}.n_clips', int(r['n_clips']), src, 'n_clips', where))
            s['clips_neg'].append(nums.add(f'{base}.clips_fresh_better', int(r['clips_neg']), src, 'clips_neg', where))
        out.append(s)
    return out


def _cell(mean, lo, hi, n, pos=None, neg=None, zero=None):
    return {'mean': mean, 'lo': lo, 'hi': hi, 'n': n, 'pos': pos, 'neg': neg, 'zero': zero}


def _add_cell(nums, base, cell, src, fields, where, derivation=None):
    """Record the numbers of one difference cell (mean, interval, n, sign counts) under base."""
    for k in ('mean', 'lo', 'hi', 'n', 'pos', 'neg', 'zero'):
        if fields.get(k) is not None:
            name = {'pos': 'n_deep_better', 'neg': 'n_fast_better', 'zero': 'n_tie'}.get(k, k)
            nums.add(f'{base}.{name}', cell[k], src, fields[k], where, derivation=derivation)
    return cell


def fig1_v4_by_ability(src, nums):
    """{kappa: {ability: cell}} of this work: the 'depth' rows of per_ability.csv (Fixed Deep - Fast Only DS; kappa
    1.0 on all routes, 1.5 and 2.0 on E), recorded as fig1.c.v4.kappa<k>.<ability>.*; a missing row is a cell with
    n 0."""
    rows = analysis_table(src, 'per_ability.csv', nums)
    path = src['dir'] / 'per_ability.csv'
    fields = {'mean': 'mean', 'lo': 'ci95_lo', 'hi': 'ci95_hi', 'n': 'n', 'pos': 'n_positive', 'neg': 'n_negative',
              'zero': 'n_zero'}
    out = {}
    for k, con in sorted(DEPTH_CONTRASTS.items()):
        out[k] = {}
        for ab in ABILITY_ROWS:
            where = {'group': 'depth', 'contrast': con.cid, 'metric': 'driving_score', 'ability': ab}
            hit = select(rows, **where)
            if len(hit) > 1:
                raise FigureError(f'{PJ.rel(path)}: {len(hit)} rows for {where}')
            r = hit[0] if hit else {}
            cell = _cell(_num(r.get('mean')), _num(r.get('ci95_lo')), _num(r.get('ci95_hi')), int(r.get('n') or 0),
                         *(int(r[f]) if r.get(f) not in (None, '') else None
                           for f in ('n_positive', 'n_negative', 'n_zero')))
            out[k][ab] = _add_cell(nums, f'fig1.c.v4.kappa{k:.1f}.{ab}', cell, path, fields, where)
    return out


def _route_abilities(r):
    return [a for a in (r.get('abilities') or '').split('|') if a]


def fig1_v2_by_ability(offline, nums):
    """{kappa: {ability: cell}} of the v2 matrix (the earlier measurement, unmodified prefix): kappa 1.0 and 1.5 from
    closed_loop_ds_by_ability.csv (V2_ABILITY_SERIES, 44 routes); kappa 2.0 (11 exploratory routes) per ability as
    the mean of closed_loop_ds_by_route.csv DS_diff_k2.0_s11 over the routes of the ability (no interval), and over all
    routes from closed_loop_kappa_trend.csv with its interval. Recorded as fig1.c.v2.kappa<k>.<ability>.*."""
    d = offline['dir']
    rows = offline['tables']['closed_loop_ds_by_ability.csv']
    fields = {'mean': 'mean_DS_diff', 'lo': 'boot95_lo', 'hi': 'boot95_hi', 'n': 'n_routes', 'pos': 'routes_pos',
              'neg': 'routes_neg', 'zero': 'routes_zero'}
    out = {}
    for k, series in sorted(V2_ABILITY_SERIES.items()):
        out[k] = {}
        for ab in ABILITY_ROWS:
            where = {'ability': ab, 'series': series}
            r = select_one(rows, 'closed_loop_ds_by_ability.csv', **where)
            cell = _cell(_num(r['mean_DS_diff']), _num(r['boot95_lo']), _num(r['boot95_hi']), int(r['n_routes']),
                         int(r['routes_pos']), int(r['routes_neg']), int(r['routes_zero']))
            out[k][ab] = _add_cell(nums, f'fig1.c.v2.kappa{k:.1f}.{ab}', cell, d / 'closed_loop_ds_by_ability.csv',
                                   fields, where)
    col = V2_ROUTE_COLUMN[2.0]
    routes = [r for r in offline['tables']['closed_loop_ds_by_route.csv'] if _num(r.get(col)) is not None]
    out[2.0] = {}
    for ab in F1.ABILITIES:
        rs = [r for r in routes if ab in _route_abilities(r)]
        v = [_num(r[col]) for r in rs]
        cell = _cell(sum(v) / len(v) if v else None, None, None, len(v), sum(x > 0 for x in v), sum(x < 0 for x in v),
                     sum(x == 0 for x in v))
        where = {'column': col, 'ability': ab, 'route_id': [r['route_id'] for r in rs]}
        out[2.0][ab] = _add_cell(
            nums, f'fig1.c.v2.kappa2.0.{ab}', cell, d / 'closed_loop_ds_by_route.csv',
            {'mean': col, 'n': col, 'pos': col, 'neg': col, 'zero': col}, where,
            derivation=f'over the {len(v)} routes of the ability with a kappa-2.0 value: mean, count and sign counts')
    where = dict(V2_TREND_K2)
    r = select_one(offline['tables']['closed_loop_kappa_trend.csv'], 'closed_loop_kappa_trend.csv', **where)
    out[2.0]['all'] = _add_cell(
        nums, 'fig1.c.v2.kappa2.0.all',
        _cell(_num(r['mean_diff']), _num(r['ci95_lo']), _num(r['ci95_hi']), int(r['n_routes'])),
        d / 'closed_loop_kappa_trend.csv', {'mean': 'mean_diff', 'lo': 'ci95_lo', 'hi': 'ci95_hi', 'n': 'n_routes'},
        where)
    return out


def fig1_by_scenario(src, offline, nums):
    """{'types': [{'scenario_type', 'abilities', 'v2_route_id'}], 'v4': {kappa: {type: value or None}}, 'v2': {...},
    'v4_status': {kappa: {type: status}}}: Fixed Deep - Fast Only DS per scenario type (one route per type). This
    work from paired_differences.csv (table 'descriptive', the 'depth' contrasts; a route without a pair has its drop
    reason as status), v2 from closed_loop_ds_by_route.csv. Recorded as fig1.d.<series>.kappa<k>.<scenario type>."""
    v2rows = offline['tables']['closed_loop_ds_by_route.csv']
    v2path = offline['dir'] / 'closed_loop_ds_by_route.csv'
    types = [{'scenario_type': r['scenario_type'], 'abilities': _route_abilities(r), 'v2_route_id': r['route_id']}
             for r in v2rows]
    if len({t['scenario_type'] for t in types}) != len(types):
        raise FigureError(f'{PJ.rel(v2path)}: a scenario type occurs on more than one route')
    out = {'types': types, 'v4': {}, 'v2': {}, 'v4_status': {}}
    for k, col in sorted(V2_ROUTE_COLUMN.items()):
        out['v2'][k] = {}
        for r in v2rows:
            out['v2'][k][r['scenario_type']] = nums.add(
                f'fig1.d.v2.kappa{k:.1f}.{r["scenario_type"]}', _num(r[col]), v2path, col,
                {'route_id': r['route_id'], 'scenario_type': r['scenario_type']})
    if src is None:
        return out
    rows = analysis_table(src, 'paired_differences.csv', nums)
    path = src['dir'] / 'paired_differences.csv'
    for k, con in sorted(DEPTH_CONTRASTS.items()):
        out['v4'][k], out['v4_status'][k] = {}, {}
        for t in types:
            where = {'table': 'descriptive', 'contrast': con.cid, 'metric': 'driving_score',
                     'scenario_type': t['scenario_type']}
            hit = select(rows, **where)
            if len(hit) > 1:
                raise FigureError(f'{PJ.rel(path)}: {len(hit)} rows for {where}')
            r = hit[0] if hit else {}
            status = r.get('status') or 'not in the subset'
            val = _num(r.get('difference')) if status == 'paired' else None
            out['v4'][k][t['scenario_type']] = nums.add(
                f'fig1.d.v4.kappa{k:.1f}.{t["scenario_type"]}', val, path, 'difference',
                {**where, 'route_id': r.get('route_id'), 'status': status})
            out['v4_status'][k][t['scenario_type']] = status
    return out


# ============================================================================================ Fig. 1 drawing

MINUS = '−'
FIG1_H_IN = 2.2
FIG1_SCEN_H_IN = 6.6
FIG1_SCEN_BAR = 0.075            # share of the companion's height given to the colour bar (its own subfigure)
# the two closed-loop series of Fig. 1 (Sec. 7.1: the v2 matrix is labelled as the earlier measurement)
V4_LABEL, V2_LABEL = 'this work (fast prefix)', 'earlier (unmodified prefix)'
V4_SHORT, V2_SHORT = 'this work', 'earlier'
FIG1C_LEGEND = {'v4': 'this work\n(fast prefix)', 'v2': 'earlier\n(unmodified\nprefix)'}   # the two labels, wrapped


def draw_fig1_age(ax, curves, release):
    """Panel (a): execution error against observation age per depth (mean; the t band of depth 1 filled, that of
    depth 10 outlined, the curves nearly coincide) with the release markers in the depth's marker (filled: fast
    prefix, open: unmodified prefix); the legend shows every depth with its marker."""
    for depth in (10, 5, 1):
        c = curves[depth]
        color, _, ls = DEPTH_STYLE[depth]
        if depth == 1:
            ax.fill_between(c['age'], c['lo'], c['hi'], color=color, alpha=0.13, linewidth=0, zorder=1)
        elif depth == 10:
            for edge in ('lo', 'hi'):
                ax.plot(c['age'], c[edge], color=color, linewidth=0.4, linestyle=(0, (3, 2)), zorder=2)
        ax.plot(c['age'], c['mean'], color=color, linestyle=ls, linewidth=LINE_W, zorder=3)
    for p in release:
        color, marker, _ = DEPTH_STYLE[p['depth']]
        ax.plot([p['age']], [p['error']], linestyle='none', marker=marker, markersize=MARKER_PT + 0.5,
                markeredgecolor=color, markerfacecolor=color if p['prefix'] == 'fast' else 'white', zorder=5)
    ax.set_xlim(0.0, max(curves[1]['age']))
    ax.set_ylim(bottom=0.0)
    ax.set_xlabel('Observation age (s)')
    ax.set_ylabel('Execution error (m)')
    _ax_style(ax, 'y')
    handles = [Line2D([], [], color=DEPTH_STYLE[d][0], linestyle=DEPTH_STYLE[d][2], marker=DEPTH_STYLE[d][1],
                      markersize=MARKER_PT, markerfacecolor=DEPTH_STYLE[d][0]) for d in (1, 5, 10)]
    labels = [f'depth {d}' for d in (1, 5, 10)]
    for prefix, label in (('fast', 'release, fast prefix'), ('unmodified', 'release, unmodified')):
        handles.append(tuple(Line2D([], [], linestyle='none', marker=DEPTH_STYLE[d][1], markersize=MARKER_PT,
                                    markeredgecolor=DEPTH_STYLE[d][0],
                                    markerfacecolor=DEPTH_STYLE[d][0] if prefix == 'fast' else 'white')
                             for d in (1, 10)))
        labels.append(label)
    ax.legend(handles, labels, loc='upper left', handler_map={tuple: HandlerTuple(ndivide=None, pad=0.2)})


def draw_fig1_kappa(ax, series):
    """Panel (b): Fast@Fresh - Deep@Old against kappa (< 0: the fresh shallow plan has the smaller error); the
    kappa sweep as line and t band, the W = 1 s points as open markers."""
    line, points = series[0], series[1]
    ax.fill_between(line['kappa'], line['lo'], line['hi'], color=MUTED, alpha=0.22, linewidth=0, zorder=1)
    ax.plot(line['kappa'], line['value'], color=INK, linewidth=LINE_W, zorder=3,
            label=f'W = {line["where"]["window_s"]} s')
    ax.errorbar(points['kappa'], points['value'],
                yerr=[[v - lo for v, lo in zip(points['value'], points['lo'])],
                      [hi - v for v, hi in zip(points['value'], points['hi'])]],
                linestyle='none', marker='o', markersize=MARKER_PT, markerfacecolor='white', markeredgecolor=INK_2,
                ecolor=INK_2, elinewidth=ERR_W, zorder=4, label=f'W = {points["where"]["window_s"]} s')
    _zero_line(ax, 'h')
    ax.set_xlabel(r'GPU slowdown $\kappa$')
    ax.set_ylabel(f'Fast@Fresh {MINUS} Deep@Old (m)')
    ax.set_xlim(min(line['kappa']) - 0.05, max(line['kappa']) + 0.05)
    _ax_style(ax, 'y')
    ax.legend(loc='lower left')


FIG1_SERIES = tuple(('v4', k) for k in KAPPAS) + tuple(('v2', k) for k in KAPPAS)


def draw_fig1_ability(ax, v4, v2):
    """Panel (c): Fixed Deep - Fast Only DS by ability and over all routes; marker shape = kappa, filled = this work,
    open = the earlier measurement (v2); whiskers = 95% intervals where the source has one; a light rule between
    ability groups, a darker one above 'All routes'."""
    step = 0.12
    for i, ab in enumerate(ABILITY_ROWS):
        y0 = -i - (0.35 if ab == 'all' else 0.0)
        for j, (series, k) in enumerate(FIG1_SERIES):
            cell = (v4 if series == 'v4' else v2).get(k, {}).get(ab)
            if not cell or cell['mean'] is None:
                continue
            y = y0 + (2.5 - j) * step
            filled = series == 'v4'
            col = INK if filled else INK_2
            if cell['lo'] is not None and cell['hi'] is not None:
                ax.plot([cell['lo'], cell['hi']], [y, y], color=col, linewidth=ERR_W, zorder=2)
            ax.plot([cell['mean']], [y], linestyle='none', marker=KAPPA_MARKER[k], markersize=MARKER_PT - 0.5,
                    markeredgecolor=col, markerfacecolor=col if filled else 'white', zorder=3)
    for i in range(len(F1.ABILITIES) - 1):
        ax.axhline(-i - 0.5, color=GRID_C, linewidth=0.4, zorder=0)
    ax.axhline(-len(F1.ABILITIES) + 1 - 0.675, color=MUTED, linewidth=AX_W, zorder=0)
    _zero_line(ax, 'v')
    ax.set_yticks([-i - (0.35 if ab == 'all' else 0.0) for i, ab in enumerate(ABILITY_ROWS)])
    ax.set_yticklabels([ABILITY_LABEL[ab] for ab in ABILITY_ROWS])
    ax.set_ylim(-len(ABILITY_ROWS) + 0.2, 0.55)
    ax.tick_params(axis='y', length=0)
    ax.set_xlabel(f'DS, Fixed Deep {MINUS} Fast Only')
    _ax_style(ax, 'x')
    handles = [Line2D([], [], linestyle='none', marker=KAPPA_MARKER[k], markeredgecolor=INK_2, markerfacecolor=INK_2,
                      label=rf'$\kappa$ {k:.1f}') for k in KAPPAS]
    handles += [Line2D([], [], linestyle='none', marker='o', markeredgecolor=INK, markerfacecolor=INK,
                       label=FIG1C_LEGEND['v4']),
                Line2D([], [], linestyle='none', marker='o', markeredgecolor=INK_2, markerfacecolor='white',
                       label=FIG1C_LEGEND['v2'])]
    return handles


def fig1_data(src, offline, nums):
    """Everything Fig. 1 and its companion show (recorded in nums): the age curves, the release points, the kappa
    contrast, the by-ability cells of this work (empty without an analysis) and of v2, and the scenario-type cells."""
    curves = fig1_age_curves(offline, nums)
    return {'curves': curves, 'release': fig1_release_points(curves, nums, offline),
            'kappa': fig1_kappa_contrast(offline, nums),
            'v4': fig1_v4_by_ability(src, nums) if src is not None else {},
            'v2': fig1_v2_by_ability(offline, nums), 'scenarios': fig1_by_scenario(src, offline, nums)}


def figure_1(data, status, out):
    """Fig. 1 (double column): (a) error against age, (b) Fast@Fresh - Deep@Old against kappa, (c) Fixed Deep - Fast
    Only DS by ability. Returns the file names."""
    with plt.rc_context(rc_params()):
        fig = plt.figure(figsize=(DCOL_W_IN, FIG1_H_IN), constrained_layout=True)
        fig.set_constrained_layout_pads(w_pad=0.02, h_pad=0.02, wspace=0.04, hspace=0.0)
        gs = fig.add_gridspec(1, 3, width_ratios=(1.0, 0.82, 1.18))
        ax_a, ax_b, ax_c = (fig.add_subplot(gs[0, i]) for i in range(3))
        draw_fig1_age(ax_a, data['curves'], data['release'])
        ax_a.set_title('(a) Offline: error vs. observation age')
        draw_fig1_kappa(ax_b, data['kappa'])
        ax_b.set_title(f'(b) Offline: Fast@Fresh {MINUS} Deep@Old')
        handles = draw_fig1_ability(ax_c, data['v4'], data['v2'])
        ax_c.set_title('(c) Closed loop, by ability')
        ax_c.legend(handles=handles, loc='upper left', bbox_to_anchor=(1.0, 1.0), handletextpad=0.2)
        return save_figure(fig, out, 'fig1', status)


def figure_1_scenarios(data, status, out):
    """The companion of Fig. 1(c) (single column): Fixed Deep - Fast Only DS per scenario type, this work and the
    earlier measurement at kappa 1.0, 1.5 and 2.0, on the diverging scale (blue: Fixed Deep better, orange: Fast Only
    better); a cell without a paired route is hatched (explained in the caption). Rows sorted by this work's kappa-1.0
    difference (then by the earlier measurement's, then by name). The colour bar spans the figure width in its own
    subfigure, with the end labels under its ends. Returns the file names."""
    sc = data['scenarios']
    names = [t['scenario_type'] for t in sc['types']]

    def key(n):
        v4, v2 = sc['v4'].get(1.0, {}).get(n), sc['v2'][1.0].get(n)
        return (-(v4 if v4 is not None else -1e9), -(v2 if v2 is not None else -1e9), n)
    names.sort(key=key)
    cols = [(s, k) for s, k in FIG1_SERIES]
    vals = [[(sc[s].get(k) or {}).get(n) for s, k in cols] for n in names]
    finite = [abs(v) for row in vals for v in row if v is not None]
    lim = max(25.0, 25.0 * math.ceil(max(finite, default=25.0) / 25.0))
    cmap = LinearSegmentedColormap.from_list('fixed_deep_vs_fast_only', DIVERGING)
    norm = Normalize(-lim, lim)
    gap = 0.3
    with plt.rc_context(rc_params()):
        fig = plt.figure(figsize=(COL_W_IN, FIG1_SCEN_H_IN), constrained_layout=True)
        fig.set_constrained_layout_pads(w_pad=0.02, h_pad=0.02, wspace=0.0, hspace=0.0)
        # transparent subfigures: the development stamp of the parent figure stays visible
        top, bottom = fig.subfigures(2, 1, height_ratios=(1.0 - FIG1_SCEN_BAR, FIG1_SCEN_BAR), facecolor='none')
        ax, cax = top.add_subplot(1, 1, 1), bottom.add_subplot(1, 1, 1)
        for i, row in enumerate(vals):
            for j, v in enumerate(row):
                x = j + (gap if j >= len(KAPPAS) else 0.0)
                if v is None:
                    ax.add_patch(plt.Rectangle((x, i), 1, 1, facecolor=MISSING_C, edgecolor=GRID_C, hatch='////',
                                               linewidth=0.3))
                else:
                    ax.add_patch(plt.Rectangle((x, i), 1, 1, facecolor=cmap(norm(v)), edgecolor='white',
                                               linewidth=0.6))
        ax.set_xlim(0, len(cols) + gap)
        ax.set_ylim(len(names), 0)
        ax.set_yticks([i + 0.5 for i in range(len(names))])
        ax.set_yticklabels(names)
        ax.set_xticks([j + 0.5 + (gap if j >= len(KAPPAS) else 0.0) for j in range(len(cols))])
        ax.set_xticklabels([f'{k:.1f}' for _, k in cols])
        ax.xaxis.tick_top()
        ax.tick_params(length=0, pad=1.5)
        for side in ('left', 'bottom', 'top', 'right'):
            ax.spines[side].set_visible(False)
        for x, label in ((len(KAPPAS) / 2, V4_SHORT), (len(KAPPAS) * 1.5 + gap, V2_SHORT)):
            ax.text(x, 0, label, transform=offset_copy(ax.transData, fig=fig, y=12.0, units='points'), ha='center',
                    va='bottom', clip_on=False)
        ax.text(len(cols) + gap + 0.05, 0, r'$\kappa$', ha='left', va='bottom', clip_on=False,
                transform=offset_copy(ax.transData, fig=fig, y=1.5, units='points'))
        cb = bottom.colorbar(matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation='horizontal')
        cb.outline.set_linewidth(AX_W)
        cb.outline.set_edgecolor(AXIS_C)
        cb.ax.tick_params(length=2, width=AX_W, color=AXIS_C)
        cb.set_label(f'DS, Fixed Deep {MINUS} Fast Only', labelpad=2.0)
        cax.xaxis.set_label_position('top')
        for x, ha, text in ((0.0, 'left', 'Fast Only better'), (1.0, 'right', 'Fixed Deep better')):
            cax.text(x, 0.0, text, transform=offset_copy(cax.transAxes, fig=fig, y=-(FONT_PT + 4.5), units='points'),
                     ha=ha, va='top', color=INK_2, clip_on=False)
        return save_figure(fig, out, 'fig1_scenarios', status)


# ============================================================================================ Fig. 3 (Sec. 7.3)

def fmt_pct(v, nd=1):
    return '–' if v is None else f'{100.0 * v:.{nd}f}%'


FIG3_SHOWN = {'eir': lambda v: fmt_pct(v, 1), 'gpu_usage': lambda v: fmt_pct(v, 0)}


def fig3_points(src, nums):
    """{arm: {kappa: {metric: {'mean', 'lo', 'hi', 'n', 'n_routes'}, 'bg_load': {...}}}} of Fig. 3: the route means
    and 95% route-bootstrap intervals of conditions.csv (subset E, seed 11, statistic route_mean) for DS, action-age
    p50 / p95, EIR and GPU usage, and the background-load counts of the condition (analysis.json manipulation
    by_condition, Amendment A8; with the runs of the condition). Recorded as fig3.<arm>.kappa<k>.<metric>.<mean | lo |
    hi | n>, fig3.<arm>.kappa<k>.bg_load.<above | below | within> and fig3.<arm>.kappa<k>.runs; a condition without a
    row is a point with n 0."""
    rows = analysis_table(src, 'conditions.csv', nums)
    path = src['dir'] / 'conditions.csv'
    by_cond = ((src['doc'].get('manipulation') or {}).get('by_condition') or {})
    out = {}
    for arm in FIG3_ARMS:
        out[arm] = {}
        for k in KAPPAS:
            cond = AN.Cond(arm, k, FIG3_SEED).name
            pt = {}
            for metric in (FIG3_Y, *FIG3_X.values(), *FIG3_NOTES):
                where = {'condition': cond, 'subset': FIG3_SUBSET, 'metric': metric, 'statistic': 'route_mean'}
                hit = select(rows, **where)
                if len(hit) > 1:
                    raise FigureError(f'{PJ.rel(path)}: {len(hit)} rows for {where}')
                r = hit[0] if hit else {}
                base = f'fig3.{arm}.kappa{k:.1f}.{metric}'
                shown = FIG3_SHOWN.get(metric)
                m = _num(r.get('mean'))
                pt[metric] = {
                    'mean': nums.add(f'{base}.mean', m, path, 'mean', where, shown=shown(m) if shown else None),
                    'lo': nums.add(f'{base}.lo', _num(r.get('ci95_lo')), path, 'ci95_lo', where),
                    'hi': nums.add(f'{base}.hi', _num(r.get('ci95_hi')), path, 'ci95_hi', where),
                    'n': nums.add(f'{base}.n', int(r.get('n') or 0), path, 'n', where),
                    'n_routes': int(r.get('n_routes') or 0)}
            bg = (by_cond.get(cond) or {}).get('bg_load') or {}
            pt['bg_load'] = {s: nums.add(f'fig3.{arm}.kappa{k:.1f}.bg_load.{s}', bg.get(s),
                                         src['dir'] / 'analysis.json', f'manipulation.by_condition.{cond}.bg_load.{s}',
                                         {'condition': cond}, shown=None if bg.get(s) is None else str(bg.get(s)))
                             for s in ('above', 'below', 'within')}
            runs = (by_cond.get(cond) or {}).get('runs')
            pt['bg_load']['runs'] = nums.add(f'fig3.{arm}.kappa{k:.1f}.runs', runs, src['dir'] / 'analysis.json',
                                             f'manipulation.by_condition.{cond}.runs', {'condition': cond},
                                             shown=None if runs is None else str(runs))
            out[arm][k] = pt
    return out


def _fig3_ok(pt, xkey):
    return all(pt[m]['mean'] is not None for m in (FIG3_Y, xkey))


def draw_fig3_panel(ax, points, xkey, xlabel):
    """One Fig. 3 panel: mean DS against the mean action age xkey per arm through its three budgets; both axes carry
    the 95% route-bootstrap intervals; marker fill = kappa (KAPPA_FILL)."""
    for arm in FIG3_ARMS:
        color, marker = ARM_STYLE[arm]
        pts = [(k, points[arm][k]) for k in KAPPAS if _fig3_ok(points[arm][k], xkey)]
        ax.plot([p[xkey]['mean'] for _, p in pts], [p[FIG3_Y]['mean'] for _, p in pts], color=color,
                linewidth=LINE_W, zorder=2)
        for k, p in pts:
            x, y = p[xkey], p[FIG3_Y]
            if None not in (x['lo'], x['hi']):
                ax.plot([x['lo'], x['hi']], [y['mean']] * 2, color=color, linewidth=ERR_W, alpha=0.8, zorder=1)
            if None not in (y['lo'], y['hi']):
                ax.plot([x['mean']] * 2, [y['lo'], y['hi']], color=color, linewidth=ERR_W, alpha=0.8, zorder=1)
            ax.plot([x['mean']], [y['mean']], linestyle='none', marker=marker, markersize=MARKER_PT + 1.0,
                    fillstyle=KAPPA_FILL[k], markerfacecolor=color, markerfacecoloralt='white', markeredgecolor=color,
                    markeredgewidth=0.8, zorder=3)
    ax.set_xlabel(xlabel)
    ax.set_ylabel('Driving score (mean)')
    _ax_style(ax, 'both')


FIG3_SIZE_IN = {'double': (DCOL_W_IN, 2.3), 'single': (COL_W_IN, 6.0)}
FIG3_SHORT = {'fixed_deep': 'Fixed Deep', 'fast_only': 'Fast Only', 'fl_heuristic': 'FrameLease + Heuristic',
              'fl_full': 'Full FrameLease'}


def draw_fig3_notes(ax, points):
    """Panel (c): the annotation of every Fig. 3 point: EIR (upper line) and GPU usage (lower line) per arm and kappa
    (column header: the kappa and its marker fill), a dagger where a point has fewer routes than its subset."""
    ax.axis('off')
    cols = {k: 0.665 + 0.14 * j for j, k in enumerate(KAPPAS)}
    t = dict(transform=ax.transAxes, va='center')
    for k, x in cols.items():
        ax.text(x, 0.97, rf'$\kappa$ {k:.1f}', ha='center', **t)
        ax.plot([x], [0.885], transform=ax.transAxes, linestyle='none', marker='o', markersize=MARKER_PT + 1.0,
                fillstyle=KAPPA_FILL[k], markerfacecolor=INK_2, markerfacecoloralt='white', markeredgecolor=INK_2,
                clip_on=False)
    ax.plot([0.0, 1.0], [0.83, 0.83], transform=ax.transAxes, color=AXIS_C, linewidth=AX_W, clip_on=False)
    short = False
    for i, arm in enumerate(FIG3_ARMS):
        y = 0.73 - 0.17 * i
        color, marker = ARM_STYLE[arm]
        ax.plot([0.025], [y], transform=ax.transAxes, linestyle='none', marker=marker, markersize=MARKER_PT + 1.0,
                markerfacecolor=color, markeredgecolor=color, clip_on=False)
        ax.text(0.065, y, FIG3_SHORT[arm], ha='left', **t)
        for k, x in cols.items():
            p = points[arm][k]
            lacks = any(p[m]['n'] < p[m]['n_routes'] for m in (FIG3_Y, *FIG3_X.values(), *FIG3_NOTES)
                        if p[m]['mean'] is not None)
            short = short or lacks
            text = f'{FIG3_SHOWN["eir"](p["eir"]["mean"])}\n{FIG3_SHOWN["gpu_usage"](p["gpu_usage"]["mean"])}'
            ax.text(x, y, text + ('$^\\dagger$' if lacks else ''), ha='center', linespacing=1.05, color=INK_2, **t)
    ax.plot([0.0, 1.0], [0.08, 0.08], transform=ax.transAxes, color=AXIS_C, linewidth=AX_W, clip_on=False)
    note = 'Upper line: EIR; lower line: GPU usage.' + (r' $^\dagger$ Fewer routes than E.' if short else '')
    ax.text(0.0, 0.0, note, ha='left', **t)


def figure_3(points, status, out, layout='double'):
    """Fig. 3: (a) DS against action-age p50, (b) against p95, (c) the EIR / GPU-usage annotation of every point;
    layout 'double' (one row, text width) or 'single' (stacked, column width). Returns the file names."""
    if layout not in FIG3_SIZE_IN:
        raise ValueError(f'layout {layout!r} not in {sorted(FIG3_SIZE_IN)}')
    with plt.rc_context(rc_params()):
        fig = plt.figure(figsize=FIG3_SIZE_IN[layout], constrained_layout=True)
        fig.set_constrained_layout_pads(w_pad=0.02, h_pad=0.02, wspace=0.04, hspace=0.04)
        if layout == 'double':
            gs = fig.add_gridspec(1, 3, width_ratios=(1.0, 1.0, 1.02))
            ax_a = fig.add_subplot(gs[0, 0])
            ax_b, ax_c = fig.add_subplot(gs[0, 1], sharey=ax_a), fig.add_subplot(gs[0, 2])
        else:
            gs = fig.add_gridspec(3, 1, height_ratios=(1.0, 1.0, 0.95))
            ax_a = fig.add_subplot(gs[0, 0])
            ax_b, ax_c = fig.add_subplot(gs[1, 0], sharey=ax_a), fig.add_subplot(gs[2, 0])
        draw_fig3_panel(ax_a, points, FIG3_X['p50'], 'Action age p50 (s), mean over routes')
        draw_fig3_panel(ax_b, points, FIG3_X['p95'], 'Action age p95 (s), mean over routes')
        if layout == 'double':
            ax_b.set_ylabel('')
            ax_b.tick_params(labelleft=False)
        ax_a.set_title('(a) DS vs. action age p50')
        ax_b.set_title('(b) DS vs. action age p95')
        draw_fig3_notes(ax_c, points)
        ax_c.set_title('(c) Annotation of every point')
        return save_figure(fig, out, 'fig3' if layout == 'double' else 'fig3_single', status)


# ============================================================================================ figure captions

def write_caption(out, stem, label, text, status):
    r"""<stem>_caption.tex: the caption of a figure as LaTeX (\caption{text} and \label{fig:<label>}, to be input in its
    figure environment), with the development comment and caption prefix of a figure that is not made from registered
    sources; a typographic minus is set by tex_minus; every line ends with '%' (no space after the graphic). Returns the
    file name."""
    dev = status != REGISTERED
    lines = [f'% {THIS_REL}: generated caption of {stem}.pdf; every number is listed in numbers.json']
    if dev:
        lines.append(f'% {DEV_STAMP}')
    lines += ['\\caption{' + (r'\textbf{[' + latex_escape(DEV_STAMP) + r']} ' if dev else '') + tex_minus(text) + '}%',
              f'\\label{{fig:{label}}}%']
    name = f'{stem}_caption.tex'
    _write_text(Path(out) / name, '\n'.join(lines) + '\n')
    return name


def fig1_caption(data):
    """The caption of Fig. 1 (LaTeX): the panels, the release ages (numbers.json fig1.a.release.*) and the two
    closed-loop series, the v2 matrix labelled as the earlier measurement (Sec. 7.1)."""
    rel = {(p['prefix'], p['depth']): p['age'] for p in data['release']}
    n = data['curves'][1]['n_clips']
    clips = f'{n[0]} held-out clips' if len(n) == 1 else 'held-out clips'
    return ('Freshness--depth trade-off. (a) Offline: execution error against observation age for depths 1, 5 and 10 '
            f'(C1 sweep, $W$ = 1 s, {clips}, Student-t 95\\% bands); markers at the release ages in the marker of '
            f'the depth, filled for the fast prefix (depth 1 at {rel[("fast", 1)]:.3f} s, depth 10 at '
            f'{rel[("fast", 10)]:.3f} s) and open for the unmodified prefix ({rel[("unmodified", 1)]:.3f} s and '
            f'{rel[("unmodified", 10)]:.3f} s). (b) Offline: Fast@Fresh $-$ Deep@Old against $\\kappa$ ($W$ = 0.5 s '
            'with its t band, $W$ = 1 s points); below 0 the fresh shallow plan has the smaller execution error. '
            '(c) Closed loop: paired DS difference Fixed Deep $-$ Fast Only by Bench2Drive ability (official '
            'multi-label map) and over all routes; filled: this work (fast prefix; $\\kappa$ = 1.0 on the 44 test '
            'routes, $\\kappa$ = 1.5 and 2.0 on subset E); open: the earlier measurement (unmodified prefix; '
            '$\\kappa$ = 1.0 and 1.5 on 44 routes, $\\kappa$ = 2.0 on 11 routes as per-ability means without '
            'interval); whiskers: 95\\% route-bootstrap intervals where the source gives one. Descriptive; no test.')


def fig1_scenarios_caption(data):
    """The caption of the scenario-type companion of Fig. 1(c) (LaTeX): the series, the colour scale and the
    hatching."""
    return ('Paired DS difference Fixed Deep $-$ Fast Only per scenario type (one route per type) at $\\kappa$ = 1.0, '
            '1.5 and 2.0: this work (fast prefix; 44 test routes at $\\kappa$ = 1.0, subset E at 1.5 and 2.0) and the '
            'earlier measurement (unmodified prefix; 44 routes at $\\kappa$ = 1.0 and 1.5, 11 routes at 2.0). Blue: '
            'Fixed Deep better; orange: Fast Only better; hatched: no paired run (route outside the subset, not run '
            'or dropped). Rows sorted by the difference of this work at $\\kappa$ = 1.0. Descriptive; no test.')


def fig3_caption(points, f3):
    """The caption of Fig. 3 (LaTeX): the plot, the reading rule of Sec. 7.3, the secondary F3 contrasts (Holm over 4)
    and the background-load flag counts per condition (Amendment A8)."""
    count = lambda v: '--' if v is None else str(v)  # noqa: E731
    bg = '; '.join(latex_escape(FIG3_SHORT[a]) + ' ' + ', '.join(
        f'{count(points[a][k]["bg_load"]["above"])}/{count(points[a][k]["bg_load"]["runs"])}' for k in KAPPAS)
        for a in FIG3_ARMS)
    name = lambda h: f'$\\kappa$ {h["kappa"]:.1f} {latex_escape(ARM_LABEL[h["b"]])}'  # noqa: E731
    return ('Driving score against action age under constrained GPU budgets on subset E (22 test routes): mean DS '
            'against the mean per-route action-age p50 (a) and p95 (b) at $\\kappa$ = 1.0, 1.5 and 2.0 (GPU share '
            '100\\%, 67\\% and 50\\%; marker fill full, half, open), one line per method through its budgets, 95\\% '
            'route-bootstrap intervals on both axes; (c) EIR and GPU usage of every point. FrameLease does not '
            'minimize action age: a lower age is not better without the validity and budget columns. F3 (secondary; '
            'Full FrameLease $-$ each on E, DS, Holm over 4): ' + fmt_contrasts(f3, name=name) + '. Runs with the '
            'charged prefix above the idle band (background load; flagged, never excluded), per condition at $\\kappa$ '
            '= 1.0, 1.5, 2.0: ' + bg + '.')


# ============================================================================================ LaTeX tables (booktabs)

LATEX_SPECIALS = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_', '{': r'\{',
                  '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}', '<': r'\textless{}',
                  '>': r'\textgreater{}', '|': r'\textbar{}'}


# table marks: a value with fewer routes than its subset (dagger), a family that is not trainable (double dagger), a
# row cited from another study (section mark)
DAGGER, DDAGGER, CITED = '$^\\dagger$', '$^\\ddagger$', '$^\\S$'


def latex_escape(text):
    """Plain text for LaTeX (the specials of LATEX_SPECIALS escaped)."""
    return ''.join(LATEX_SPECIALS.get(ch, ch) for ch in str(text))


TEXT_SYMBOLS = (('P\\_both', '$P_\\mathrm{both}$'), ('R\\_cond', '$R_\\mathrm{cond}$'))


def tex_text(text):
    """latex_escape for a statement of the analysis, with the symbols P_both and R_cond set in math."""
    out = latex_escape(text)
    for plain, math_ in TEXT_SYMBOLS:
        out = out.replace(plain, math_)
    return out


def fmt_num(v, nd=1, scale=1.0, unit='', floor=False):
    """A number as printed (fixed decimals after scaling; '--' for a missing value); unit is appended verbatim. floor
    (a rate or share, never negative): a positive value below the printed resolution is printed as '< 0.01' (at two
    decimals), never as 0."""
    if v is None:
        return '--'
    text = f'{scale * v:.{nd}f}'
    if floor and scale * v > 0 and float(text) == 0.0:
        return f'< {10.0 ** -nd:.{nd}f}{unit}'
    return text + unit


def fmt_ci(mean, lo, hi, nd=1, scale=1.0):
    """'mean [lo, hi]' as printed; the interval is left out when it is missing."""
    if mean is None:
        return '--'
    if lo is None or hi is None:
        return fmt_num(mean, nd, scale)
    return f'{fmt_num(mean, nd, scale)} [{fmt_num(lo, nd, scale)}, {fmt_num(hi, nd, scale)}]'


def booktabs(colspec, header, body, caption, label, notes=(), wide=True, status=REGISTERED):
    """A complete IEEE table environment (table* when wide) with one booktabs tabular: header and body are lists of
    rows of LaTeX cells (already escaped; a body entry that is a string, e.g. '\\midrule', is written as it is); notes
    are LaTeX paragraphs set below the rule in \\footnotesize. A table that is not made from the registered analysis
    carries a LaTeX comment and a bold caption prefix."""
    return booktabs_panels([{'title': None, 'colspec': colspec, 'header': header, 'body': body}], caption, label,
                           notes, wide, status)


MINUS_RE = re.compile(r'(^|[\s\[(,/])-(?=\d)')
MATH_SPLIT = re.compile(r'(?<!\\)\$')


def tex_minus(text):
    """A typographic minus ($-$) for every negative number of a printed cell or note outside math ('-4.8' at the
    start or after a space, bracket, parenthesis, comma or slash) and a math '<' for a bare '<' outside math (fmt_num
    with floor; OT1 text has no '<'); math, ranges such as '0--3' and dates are left alone."""
    parts = MATH_SPLIT.split(text)
    return '$'.join(p if i % 2 else MINUS_RE.sub(lambda m: m.group(1) + '$-$', p).replace('<', '$<$')
                    for i, p in enumerate(parts))


def n_columns(colspec):
    """The number of columns of a tabular column specification (l, c, r, p{..}, m{..}, b{..}; @{..} and |
    do not count)."""
    return sum(ch in 'lcrpmb' for ch in re.sub(r'\{[^{}]*\}', '', colspec))


def booktabs_panels(panels, caption, label, notes=(), wide=True, status=REGISTERED, tabcolsep=3.2, part=None):
    """booktabs with several panels under one caption (Table II: 'two panels under one table number'): every panel
    {'title', 'colspec', 'header', 'body'} is its own tabular, stacked with a small gap; a titled panel opens with a
    row spanning its columns (title, then a rule). part ('A', 'B', ...): the table is a part of one table number,
    numbered '<number>-<part>' (TABLE II-A, TABLE II-B); a part other than 'A' takes the number of the table before
    it (its file is input right after that part's)."""
    env = 'table*' if wide else 'table'
    dev = status != REGISTERED
    lines = [f'% {THIS_REL}: generated; every number is listed in numbers.json']
    if dev:
        lines.append(f'% {DEV_STAMP}')
    lines += [f'\\begin{{{env}}}[t]', '\\centering']
    if part is not None:
        if part != 'A':
            lines.append('\\addtocounter{table}{-1}')
        lines.append(f'\\renewcommand{{\\thetable}}{{\\Roman{{table}}-{part}}}')
    lines += ['\\caption{' + (r'\textbf{[' + latex_escape(DEV_STAMP) + r']} ' if dev else '') + caption + '}',
              f'\\label{{{label}}}', '\\footnotesize', f'\\setlength{{\\tabcolsep}}{{{tabcolsep}pt}}']
    for i, p in enumerate(panels):
        if i:
            lines.append('\\par\\medskip')
        lines += [f'\\begin{{tabular}}{{{p["colspec"]}}}', '\\toprule']
        if p.get('title'):
            lines += [f'\\multicolumn{{{n_columns(p["colspec"])}}}{{@{{}}l}}{{{p["title"]}}} \\\\', '\\midrule']
        lines += [(' & '.join(r) + r' \\') if isinstance(r, (list, tuple)) else r for r in p['header']]
        lines.append('\\midrule')
        lines += [(' & '.join(tex_minus(c) for c in r) + r' \\') if isinstance(r, (list, tuple)) else r
                  for r in p['body']]
        lines += ['\\bottomrule', '\\end{tabular}']
    if notes:
        width = '\\textwidth' if wide else '\\columnwidth'
        lines += ['\\par\\smallskip', f'\\parbox{{{width}}}{{\\footnotesize']
        lines += [tex_minus(n) + ('' if i == len(notes) - 1 else ' ') for i, n in enumerate(notes)]
        lines.append('}')
    lines.append(f'\\end{{{env}}}')
    return '\n'.join(lines) + '\n'


# ============================================================================================ Table I (Sec. 7.2)

TABLE1_ARMS = ('fixed_deep', 'fast_only', 'age_only', 'event_triggered', 'fl_original', 'fl_heuristic', 'fl_full')
TABLE1_SUBSET, TABLE1_KAPPA, TABLE1_SEED = 'all', 1.0, 11


def hdr(*lines):
    """A header cell of stacked lines (bottom-aligned; '\\\\{}' so that a line may start with '[')."""
    return '\\begin{tabular}[b]{@{}c@{}}' + ' \\\\{} '.join(lines) + '\\end{tabular}'


# column: (header, conditions.csv metric, statistic, decimals, scale, unit); the arrow marks a registered direction
TABLE1_COLUMNS = (
    (hdr('DS $\\uparrow$', '[95\\% CI]'), 'driving_score', 'route_mean', 1, 1.0, ''),
    (hdr('SR', '(\\%) $\\uparrow$'), 'success', 'route_mean', 1, 100.0, ''),
    (hdr('Coll./', 'km $\\downarrow$'), 'collisions_per_km_pooled', 'pooled_ratio', 2, 1.0, ''),
    (hdr('Infr./', 'km $\\downarrow$'), 'infractions_per_km', 'route_mean', 2, 1.0, ''),
    (hdr('GPU', '(\\%)'), 'gpu_usage', 'route_mean', 0, 100.0, ''),
    (hdr('DMR', '(\\%) $\\downarrow$'), 'dmr', 'route_mean', 1, 100.0, ''),
    (hdr('Age', 'p50 (s)'), 'action_age_p50_s', 'route_mean', 2, 1.0, ''),
    (hdr('Age', 'p95 (s)'), 'action_age_p95_s', 'route_mean', 2, 1.0, ''),
    (hdr('Fallback', '(\\%) $\\downarrow$'), 'fallback_ratio', 'route_mean', 1, 100.0, ''),
    (hdr('EIR', '(\\%) $\\downarrow$'), 'eir', 'route_mean', 2, 100.0, ''),
    (hdr('$P_\\mathrm{both}$', '(\\%)'), 'p_both', 'route_mean', 1, 100.0, ''),
)
TABLE1_NOTE_COLUMNS = (('RC', 'route_completion', 1, 1.0), ('Closed-loop $R_\\mathrm{cond}$ (\\%)', 'r_cond', 1, 100.0))
# conditions.csv metrics that are rates or shares (never negative): a positive value below the shown resolution is
# printed as '< 0.01' (fmt_num floor)
RATE_METRICS = frozenset(('success', 'gpu_usage', 'dmr', 'fallback_ratio', 'eir', 'p_both', 'r_cond',
                          'lease_utilization', 'premature_expiry_ratio', 'deviation_rate', 'bypass_rate'))


def _condition_value(rows, path, nums, key, cond, metric, statistic, nd, scale, subset=TABLE1_SUBSET):
    """mean, interval and n of one conditions.csv row, recorded as <key>.mean / lo / hi / n (shown: the printed
    value, with floor for RATE_METRICS); a missing row gives n 0 and no value."""
    where = {'condition': cond, 'subset': subset, 'metric': metric, 'statistic': statistic}
    hit = select(rows, **where)
    if len(hit) > 1:
        raise FigureError(f'{PJ.rel(path)}: {len(hit)} rows for {where}')
    r = hit[0] if hit else {}
    m, fl = _num(r.get('mean')), metric in RATE_METRICS
    return {'mean': nums.add(f'{key}.mean', m, path, 'mean', where, shown=fmt_num(m, nd, scale, floor=fl)),
            'lo': nums.add(f'{key}.lo', _num(r.get('ci95_lo')), path, 'ci95_lo', where,
                           shown=fmt_num(_num(r.get('ci95_lo')), nd, scale, floor=fl)),
            'hi': nums.add(f'{key}.hi', _num(r.get('ci95_hi')), path, 'ci95_hi', where,
                           shown=fmt_num(_num(r.get('ci95_hi')), nd, scale, floor=fl)),
            'n': nums.add(f'{key}.n', int(r.get('n') or 0), path, 'n', where),
            'n_routes': int(r.get('n_routes') or 0)}


def table1_data(src, nums):
    """Everything Table I shows (recorded as tab1.*): per arm the TABLE1_COLUMNS (collisions/km with its route-cluster
    interval) and the note columns from conditions.csv (44 routes, kappa 1.0, seed 11), the primary H1 contrasts
    (family_H1.csv) and the secondary families of Table I (Sec. 7.2 'Contrasts. As in Sec. 9.'): H3 (family_H3.csv),
    S-coll and S-dmr (family_S-coll.csv, family_S-dmr.csv), each with mean, interval, Holm-adjusted p, n and label,
    and the background-load counts of analysis.json (Amendment A8)."""
    rows = analysis_table(src, 'conditions.csv', nums)
    path = src['dir'] / 'conditions.csv'
    by_cond = ((src['doc'].get('manipulation') or {}).get('by_condition') or {})
    arms = {}
    for arm in TABLE1_ARMS:
        cond = AN.Cond(arm, TABLE1_KAPPA, TABLE1_SEED).name
        cells = {}
        for _, metric, stat, nd, scale, _ in TABLE1_COLUMNS:
            cells[metric] = _condition_value(rows, path, nums, f'tab1.{arm}.{metric}', cond, metric, stat, nd, scale)
        for _, metric, nd, scale in TABLE1_NOTE_COLUMNS:
            cells[metric] = _condition_value(rows, path, nums, f'tab1.{arm}.{metric}', cond, metric, 'route_mean',
                                             nd, scale)
        bg = (by_cond.get(cond) or {}).get('bg_load') or {}
        cells['bg_load_above'] = nums.add(f'tab1.{arm}.bg_load.above', bg.get('above'), src['dir'] / 'analysis.json',
                                          f'manipulation.by_condition.{cond}.bg_load.above', {'condition': cond},
                                          shown=None if bg.get('above') is None else str(bg.get('above')))
        cells['runs'] = (by_cond.get(cond) or {}).get('runs')
        arms[arm] = cells
    return {'arms': arms, 'h1': family_rows(src, nums, 'H1', 'tab1.h1'), 'h3': family_rows(src, nums, 'H3', 'tab1.h3'),
            'scoll': family_rows(src, nums, 'S-coll', 'tab1.scoll'),
            'sdmr': family_rows(src, nums, 'S-dmr', 'tab1.sdmr')}


# the printed scale of a family's mean difference: (decimals, scale); DS families in DS points (1 decimal), S-coll in
# collisions per km (route-level), S-dmr in percentage points
FAMILY_FMT = {'S-coll': (2, 1.0), 'S-dmr': (1, 100.0)}


def family_rows(src, nums, family, base):
    """The contrasts of one family of the analysis (family_<family>.csv, in the order of analyze_v4.FAMILIES):
    [{'a', 'b', 'kappa', 'subset', 'mean', 'lo', 'hi', 'p_adjusted', 'n', 'n_expected', 'dropped', 'label', 'nd',
    'scale'}], recorded as <base>.<key>.* with key the b arm, or <a>_minus_<b>_k<kappa> in a family whose b arms repeat
    (H3, F3); shown: the printed text (mean and interval at FAMILY_FMT, p as fmt_p). dropped: the dropped routes with
    their reasons (Sec. 9.8; None when the contrast is complete). FigureError when a contrast has no row."""
    name = f'family_{family}.csv'
    fam = analysis_table(src, name, nums)
    fpath = src['dir'] / name
    spec = AN.FAMILY_BY_NAME[family]
    nd, scale = FAMILY_FMT.get(family, (1, 1.0))
    unique = len({c.b.arm for c in spec.contrasts}) == len(spec.contrasts)
    out = []
    for con in spec.contrasts:
        where = {'family': family, 'contrast': con.cid, 'metric': spec.metric}
        r = select_one(fam, PJ.rel(fpath), **where)
        key = f'{base}.{con.b.arm}' if unique else f'{base}.{con.a.arm}_minus_{con.b.arm}_k{con.a.kappa:.1f}'
        m, lo, hi, p = (_num(r[f]) for f in ('mean', 'ci95_lo', 'ci95_hi', 'p_adjusted'))
        n, n_exp, dropped = int(r['n'] or 0), int(r.get('n_expected') or 0), r.get('dropped_routes') or None
        out.append({'a': con.a.arm, 'b': con.b.arm, 'kappa': con.a.kappa, 'subset': con.subset, 'nd': nd,
                    'scale': scale,
                    'mean': nums.add(f'{key}.mean', m, fpath, 'mean', where, shown=fmt_num(m, nd, scale)),
                    'lo': nums.add(f'{key}.lo', lo, fpath, 'ci95_lo', where, shown=fmt_num(lo, nd, scale)),
                    'hi': nums.add(f'{key}.hi', hi, fpath, 'ci95_hi', where, shown=fmt_num(hi, nd, scale)),
                    'p_adjusted': nums.add(f'{key}.p_adjusted', p, fpath, 'p_adjusted', where, shown=fmt_p(p)),
                    'n': nums.add(f'{key}.n', n, fpath, 'n', where, shown=str(n)),
                    'n_expected': nums.add(f'{key}.n_expected', n_exp, fpath, 'n_expected', where, shown=str(n_exp)),
                    'dropped': nums.add(f'{key}.dropped_routes', dropped, fpath, 'dropped_routes', where,
                                        shown=dropped),
                    'label': nums.add(f'{key}.label', r['label'], fpath, 'label', where, shown=r['label'])})
    return out


def fmt_contrasts(rows, labels=None, name=None):
    """The LaTeX text of family_rows: '<name> mean [lo, hi], p_Holm p, label' joined by '; ' ('p' for a family of one
    contrast), then the n of the contrasts (PROTOCOL Sec. 9.8): 'n = <n> routes (each)' when every contrast is
    complete, otherwise 'n <n> of <expected>' with the dropped routes and their reasons after each incomplete
    contrast. name(row) is the LaTeX name of a contrast (default: the label of its b arm, labels or ARM_LABEL)."""
    labels = labels or ARM_LABEL
    name = name or (lambda h: latex_escape(labels[h['b']]))
    ptag = '$p$' if len(rows) == 1 else '$p_\\mathrm{Holm}$'
    parts = []
    for h in rows:
        f = lambda v: fmt_num(v, h['nd'], h['scale'])  # noqa: E731
        text = (f'{name(h)} {f(h["mean"])} [{f(h["lo"])}, {f(h["hi"])}], {ptag} {latex_escape(fmt_p(h["p_adjusted"]))}'
                f', {latex_escape(h["label"])}')
        if h['n'] != h['n_expected']:
            text += f', n {h["n"]} of {h["n_expected"]}'
            if h['dropped']:
                text += f' (dropped: {latex_escape(h["dropped"])})'
        parts.append(text)
    text = '; '.join(parts)
    if rows and all(h['n'] == h['n_expected'] for h in rows):
        text += f'; n = {rows[0]["n"]} routes' + (' each' if len(rows) > 1 else '')
    return text


def fmt_p(p):
    """A p value as printed: three decimals, '< 0.001' below 0.001."""
    if p is None:
        return '--'
    return '< 0.001' if p < 0.001 else f'{p:.3f}'


def table_1(data, status, out):
    """Table I (table*, booktabs) as table1.tex: one row per arm in the Sec. 4.1 order; DS with its 95% route-bootstrap
    interval; the notes carry the collisions/km route-cluster intervals, RC, closed-loop R_cond, the H1 contrasts
    (primary), the secondary H3, S-coll and S-dmr contrasts (labelled secondary), each with its n (Sec. 9.8), and the
    background-load flag counts. Returns the file names."""
    header = [['Method'] + [h for h, *_ in TABLE1_COLUMNS]]
    body, short = [], []
    for arm in TABLE1_ARMS:
        c = data['arms'][arm]
        row = [latex_escape(ARM_LABEL[arm])]
        for _, metric, _, nd, scale, _ in TABLE1_COLUMNS:
            v = c[metric]
            text = fmt_ci(v['mean'], v['lo'], v['hi'], nd, scale) if metric == 'driving_score' else \
                fmt_num(v['mean'], nd, scale, floor=metric in RATE_METRICS)
            if v['mean'] is not None and v['n'] < v['n_routes']:
                text += DAGGER
                short.append(arm)
            row.append(text)
        if arm == 'fl_full':
            body.append('\\midrule')
        body.append(row)
    notes = ['Mean over the 44 test routes at $\\kappa$ = 1.0, seed 11; DS with its 95\\% route-bootstrap interval.'
             ' Coll./km pooled over routes (sum of collisions / sum of km); the other columns are means over routes.'
             ' GPU: GPU-busy time per second; EIR: executed-invalid tick rate (standard validity); $P_\\mathrm{both}$:'
             ' share of shield decision epochs with both actions feasible. --: no value.']
    coll = 'collisions_per_km_pooled'
    notes.append('Coll./km, 95\\% route-cluster bootstrap interval: ' + '; '.join(
        f'{latex_escape(ARM_LABEL[a])} [{fmt_num(data["arms"][a][coll]["lo"], 2)}, '
        f'{fmt_num(data["arms"][a][coll]["hi"], 2)}]' for a in TABLE1_ARMS) + '.')
    for label, metric, nd, scale in TABLE1_NOTE_COLUMNS:
        fl = metric in RATE_METRICS
        notes.append(label + ': ' + '; '.join(
            f'{latex_escape(ARM_LABEL[a])} {fmt_num(data["arms"][a][metric]["mean"], nd, scale, floor=fl)}'
            for a in TABLE1_ARMS) + '.')
    notes.append('H1 (primary; Full FrameLease $-$ each, DS, Holm over 4): ' + fmt_contrasts(data['h1']) + '.')
    notes.append('Secondary (labelled secondary, Sec. 9.3 of the protocol). H3 (each $-$ Original FrameLease, DS, Holm '
                 'over 2): ' + fmt_contrasts(data['h3'], name=lambda h: latex_escape(ARM_LABEL[h['a']]))
                 + '. S-coll (Full FrameLease $-$ each, collisions/km per route, lower is better, Holm over 4): '
                 + fmt_contrasts(data['scoll']) + '. S-dmr (Full FrameLease $-$ each, DMR in percentage points, lower '
                 'is better, Holm over 4): ' + fmt_contrasts(data['sdmr']) + '.')
    count = lambda v: '--' if v is None else str(v)  # noqa: E731
    notes.append('Charged prefix above the idle band (background load, flagged and never excluded): ' + '; '.join(
        f'{latex_escape(ARM_LABEL[a])} {count(data["arms"][a]["bg_load_above"])}/{count(data["arms"][a]["runs"])}'
        for a in TABLE1_ARMS) + ' runs.')
    if short:
        notes.append(f'{DAGGER} Fewer than 44 routes (pairwise-complete contrasts; Sec. 9.8 of the protocol).')
    tex = booktabs('l' + 'c' * len(TABLE1_COLUMNS), header, body,
                   'End-to-end driving performance under matched compute budgets', 'tab:table1', notes, True, status)
    _write_text(Path(out) / 'table1.tex', tex)
    return ['table1.tex']


# ============================================================================================ sources of Tables II-A,
# II-B and the training-route table (each read once, checked, then only its recorded rows are used)

def _jget(doc, path):
    """The value at path (a list of keys and list indices) in a JSON document, None where it is absent."""
    cur = doc
    for k in path:
        if isinstance(cur, dict):
            cur = cur.get(k)
        elif isinstance(cur, list) and isinstance(k, int) and -len(cur) <= k < len(cur):
            cur = cur[k]
        else:
            return None
    return cur


def json_add(nums, key, doc, path, source, shown=None):
    """Record the value at path of a JSON source (row {'json_path': path}; the field is the dotted path) and return
    it; shown(value) gives the printed text."""
    v = _jget(doc, path)
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        v = v if isinstance(v, bool) or v is None else None
    return nums.add(key, v, source, '.'.join(str(k) for k in path), {'json_path': list(path)},
                    shown=None if shown is None else shown(v))


def _read_json(path, what):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        raise FigureError(f'{PJ.rel(Path(path))}: cannot read the {what} ({e})') from None


RND_REL = 'framelease_v3/RND_REPORT_20261110.md'
RND_TABLE = '**Table 3.**'
RND_ROWS = (('std', 'shared GPU, pass aligned with the release'),
            ('ra', 'RA validity (definition change), shared aligned'))
RND_COLS = (('model', 'model detections'), ('oracle', 'oracle ground-truth boxes'))
RND_CELL = re.compile(r'(\d+(?:\.\d+)?) \[(\d+(?:\.\d+)?), (\d+(?:\.\d+)?)\] at (\d+(?:\.\d+)?) '
                      r'\[(\d+(?:\.\d+)?), (\d+(?:\.\d+)?)\]')
RND_FIELDS = ('continuity', 'continuity_lo', 'continuity_hi', 'r_cond', 'r_cond_lo', 'r_cond_hi')


def protocol_section(text, number):
    """The text of section <number> of PROTOCOL.md (its '### <number> ' heading to the next heading of level 2 or 3);
    '' when there is no such section."""
    i = text.find(f'\n### {number} ')
    if i < 0:
        return ''
    ends = [k for k in (text.find('\n### ', i + 1), text.find('\n## ', i + 1)) if k >= 0]
    return text[i:min(ends, default=len(text))]


def load_rnd(path=None, protocol=None, manifest=None):
    """The cells of RND Table 3 that PROTOCOL Sec. 7.4 cites (the RA rows of Table II-A: RA validity and standard
    validity, shared GPU with the pass aligned with the release, model detections and oracle boxes): {'path',
    'sha256', 'cells': {(row, column): {RND_FIELDS (percent), 'row', 'column', 'text'}}}. The report must equal its
    registration-manifest sha256, and every cell must be the one Sec. 7.4 quotes ('<continuity>% [lo, hi]' and
    '<R_cond>% [lo, hi]'); FigureError otherwise."""
    p = Path(path) if path is not None else ROOT / RND_REL
    sha = PJ.sha256_file(p) if p.is_file() else None
    want = G.REG.read_manifest(manifest or G.REG.MANIFEST).get(RND_REL)
    if sha is None or sha != want:
        raise FigureError(f'{PJ.rel(p)}: sha256 {sha} is not the registered {want} of {RND_REL}')
    lines = p.read_text(encoding='utf-8').splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.startswith(RND_TABLE)), None)
    table = []
    for ln in lines[(start + 1) if start is not None else len(lines):]:
        if ln.startswith('|'):
            table.append([c.strip().replace('**', '') for c in ln.strip().strip('|').split('|')])
        elif table:
            break
    if len(table) < 3:
        raise FigureError(f'{PJ.rel(p)}: no {RND_TABLE} table')
    head, body = table[0], table[2:]
    sec74 = protocol_section(Path(protocol or G.REG.PROTOCOL).read_text(encoding='utf-8'), '7.4')
    cells = {}
    for rk, rname in RND_ROWS:
        row = next((r for r in body if r and r[0] == rname), None)
        for ck, cname in RND_COLS:
            m = RND_CELL.search(row[head.index(cname)]) if row is not None and cname in head else None
            if m is None:
                raise FigureError(f'{PJ.rel(p)} {RND_TABLE}: no cell "{rname}" x "{cname}"')
            g = m.groups()
            quoted = [f'{g[0]}% [{g[1]}, {g[2]}]', f'{g[3]}% [{g[4]}, {g[5]}]']
            absent = [q for q in quoted if q not in sec74]
            if absent:
                raise FigureError(f'{PJ.rel(p)} {RND_TABLE} "{rname}" x "{cname}": {absent} not quoted in PROTOCOL '
                                  'Sec. 7.4')
            cells[(rk, ck)] = {**dict(zip(RND_FIELDS, (float(x) for x in g))), 'row': rname, 'column': cname,
                               'text': m.group(0)}
    return {'path': PJ.rel(p), 'file': p, 'sha256': sha, 'cells': cells}


COVERAGE_SCHEMA = 'framelease_v4.prop1_coverage/1'
COVERAGE_BOOT = {'n_boot': 2000, 'seed': 20261109}      # Sec. 7.4: clip bootstrap, 2000 resamples, seed 20261109
N_VAL_CLIPS = 32


def _check_sums(d, required, what):
    """SHA256SUMS of an output directory: every entry equals its file and the required files are listed; returns
    {name: sha256}. FigureError otherwise."""
    d = Path(d)
    if not (d / 'SHA256SUMS').is_file():
        raise FigureError(f'{PJ.rel(d)}: not a {what} directory (no SHA256SUMS)')
    try:
        sums = AN.read_sums(d / 'SHA256SUMS')
    except AN.AnalysisError as e:
        raise FigureError(str(e)) from None
    bad = sorted(n for n, s in sums.items() if not (d / n).is_file() or PJ.sha256_file(d / n) != s)
    absent = sorted(set(required) - set(sums))
    if bad or absent:
        raise FigureError(f'{PJ.rel(d)}: SHA256SUMS entries {bad} differ from the files, {absent} not listed')
    return sums


def load_coverage(path):
    """An output directory of prop1_coverage.py (Proposition-1 coverage of the deployed E*, Sec. 7.4): {'path', 'dir',
    'doc' (coverage.json), 'rows' (coverage.csv), 'development': [reasons], 'clips': guarded and released clips}.
    SHA256SUMS must match its files and coverage.json 'outputs', the schema must be prop1_coverage's and no check may
    have failed (FigureError). It counts as registered only for the cited tuning freeze (deployed status
    'tuning_freeze', no warning), all 32 VAL clips and the registered clip bootstrap."""
    d = Path(path)
    sums = _check_sums(d, ('coverage.json', 'coverage.csv'), 'prop1_coverage')
    doc = _read_json(d / 'coverage.json', 'coverage document')
    if not isinstance(doc, dict) or doc.get('schema') != COVERAGE_SCHEMA:
        raise FigureError(f'{PJ.rel(d)}/coverage.json: not a prop1_coverage document (schema {COVERAGE_SCHEMA})')
    differ = sorted(n for n, s in (doc.get('outputs') or {}).items() if sums.get(n) != s)
    failed = sorted(k for k, v in (doc.get('checks') or {}).items() if isinstance(v, dict) and v.get('pass') is False)
    if differ or failed:
        raise FigureError(f'{PJ.rel(d)}: coverage.json outputs {differ} differ from SHA256SUMS; failed checks {failed}')
    dep, split, args = doc.get('deployed') or {}, doc.get('split') or {}, doc.get('arguments') or {}
    dev = []
    if dep.get('status') != 'tuning_freeze' or dep.get('warnings'):
        warn = f' ({"; ".join(dep["warnings"])})' if dep.get('warnings') else ''
        dev.append(f'{PJ.rel(d)}: deployed status {dep.get("status")!r}{warn}: E* is not fixed by a cited tuning '
                   'freeze, every kept envelope is reported as a deployed candidate')
    if not doc.get('complete') or split.get('evaluated') != 'VAL' or split.get('n_clips') != N_VAL_CLIPS:
        dev.append(f'{PJ.rel(d)}: not the {N_VAL_CLIPS} VAL clips (complete {doc.get("complete")}, '
                   f'{split.get("n_clips")} clips)')
    if {k: args.get(k) for k in COVERAGE_BOOT} != COVERAGE_BOOT:
        dev.append(f'{PJ.rel(d)}: bootstrap {({k: args.get(k) for k in COVERAGE_BOOT})}, not {COVERAGE_BOOT}')
    guard = doc.get('interim_guard') or {}
    return {'path': PJ.rel(d), 'dir': d, 'doc': doc, 'rows': read_csv(d / 'coverage.csv'), 'development': dev,
            'clips': sorted(set(guard.get('guarded_clips') or []) | set(guard.get('released_clips') or []))}


RL_SCHEMA = 'framelease_v4.rl_freeze/1'
RL_FAMILIES = (('fqi', 'fl_full'), ('bandit', 'fl_bandit'), ('fqi_nolease', 'fl_fqi_nolease'))   # trainers.FAMILIES


def load_rl_freeze(path):
    """The RL freeze of p3_rl.py (Sec. 5.9; the FQE estimates of Table II-A and the P_both label): {'path', 'file',
    'sha256', 'doc', 'routes' (the route ids of its episodes), 'development': [reasons]}. A production record counts
    only when p3_rl.load_rl_freeze accepts it with its Sec. 13.2 citation (every named file re-hashed); a development
    record (rl_freeze_dev.json) is development data. FigureError for another schema, a record without the three
    families, or a production record whose files changed."""
    p = Path(path)
    doc = _read_json(p, 'RL freeze')
    if not isinstance(doc, dict) or doc.get('schema') != RL_SCHEMA:
        raise FigureError(f'{PJ.rel(p)}: not an RL freeze (schema {RL_SCHEMA})')
    absent = [f for f, _ in RL_FAMILIES if not isinstance((doc.get('families') or {}).get(f), dict)]
    if absent:
        raise FigureError(f'{PJ.rel(p)}: no families {absent}')
    dev = []
    if doc.get('mode') == 'production' and doc.get('frozen') is True:
        from framelease_v4.protocol import p3_rl as P3
        try:
            P3.load_rl_freeze(p, require_cited=True)
        except PermissionError as e:
            dev.append(f'{PJ.rel(p)}: {e}')
        except (ValueError, OSError, KeyError) as e:
            raise FigureError(f'{PJ.rel(p)}: {e}') from None
    else:
        dev.append(f'{PJ.rel(p)}: a {doc.get("mode")} RL record (frozen {doc.get("frozen")}), not the RL freeze')
    eps = (doc.get('dataset') or {}).get('episodes') or []
    return {'path': PJ.rel(p), 'file': p, 'sha256': PJ.sha256_file(p), 'doc': doc, 'development': dev,
            'routes': sorted({str(e.get('route_id')) for e in eps if e.get('route_id') is not None})}


STRESS_SCHEMA = 'framelease_v4.stress_bench/1'
STRESS_SLOTS = {'s1': ('S1', False), 's2': ('S2', False), 's2_relative': ('S2', True), 's3': ('S3', False)}


def load_stress(path, slot):
    """A stress_bench.py report for one slot of Table II-B (STRESS_SLOTS: S1, S2 on the registered grid, S2 on the
    supplementary grid relative to the slack floor (Amendment A7), S3): {'path', 'file', 'sha256', 'doc', 'slot',
    'routes' (route ids of its recorded decision states), 'allow_test_routes', 'development': [reasons]}. FigureError
    for another schema or test, or an S2 report in the other grid's slot. A report counts as registered only when it
    is labelled so ('registered': true) and, for S1, did not share the CPU."""
    p = Path(path)
    test, relative = STRESS_SLOTS[slot]
    doc = _read_json(p, f'{test} report')
    if not isinstance(doc, dict) or doc.get('schema') != STRESS_SCHEMA or doc.get('test') != test:
        raise FigureError(f'{PJ.rel(p)}: not a {test} report of stress_bench.py (schema {STRESS_SCHEMA})')
    if test == 'S2' and (doc.get('supplementary') is True) != relative \
            or relative and doc.get('grid') != 'relative_to_floor':
        mine = 'supplementary' if doc.get('supplementary') else 'registered'
        raise FigureError(f'{PJ.rel(p)}: an S2 report on the {mine} grid given for the '
                          f'{"supplementary" if relative else "registered"} grid')
    states = doc.get('states') or (doc.get('plan') or {}).get('states') or {}
    dev = []
    if doc.get('registered') is not True:
        dev.append(f'{PJ.rel(p)}: {doc.get("label")}')
    if test == 'S1' and doc.get('shared_cpu'):
        dev.append(f'{PJ.rel(p)}: S1 shared the CPU with other processes (S1 needs an exclusive CPU)')
    return {'path': PJ.rel(p), 'file': p, 'sha256': PJ.sha256_file(p), 'doc': doc, 'slot': slot, 'development': dev,
            'routes': sorted({str(r.get('route_id')) for r in states.get('runs') or [] if r.get('route_id')}),
            'allow_test_routes': bool(states.get('allow_test_routes'))}


D1_SCHEMA = 'framelease_v4.d1_summary/1'
D1_REL = 'outputs/framelease_v4/tuning/d1/FULL_d1_summary.json'


def load_d1(path, protocol=None):
    """The D1 training-route summary of d1_summary.py (Sec. 4.8; the training-route operating-point table): {'path',
    'file', 'sha256', 'doc', 'routes', 'development': [reasons]}. FigureError for another schema or variant or a
    summary that is not 'training_routes_only'. It counts as registered only at D1_REL with its sha256 cited in Sec.
    13 of PROTOCOL.md (the D1 record)."""
    p = Path(path)
    doc = _read_json(p, 'D1 summary')
    if not isinstance(doc, dict) or doc.get('schema') != D1_SCHEMA:
        raise FigureError(f'{PJ.rel(p)}: not a D1 summary (schema {D1_SCHEMA})')
    if doc.get('variant') != 'FULL' or doc.get('training_routes_only') is not True:
        raise FigureError(f'{PJ.rel(p)}: variant {doc.get("variant")!r}, training_routes_only '
                          f'{doc.get("training_routes_only")!r} (FULL, training routes only)')
    sha = PJ.sha256_file(p)
    text = Path(protocol or G.REG.PROTOCOL).read_text(encoding='utf-8')
    dev = []
    if PJ.rel(p) != D1_REL or sha not in G.protocol_sec13(text):
        dev.append(f'{PJ.rel(p)}: not the D1 summary {D1_REL} cited in Sec. 13 of PROTOCOL.md (sha256 {sha[:12]})')
    routes = {str(r) for b in doc.get('blocks') or [] for r in (b.get('routes') or [])}
    return {'path': PJ.rel(p), 'file': p, 'sha256': sha, 'doc': doc, 'routes': sorted(routes), 'development': dev}


def source_permission(sources, scope, registered=None):
    """The Sec. 9.11 check of the sources of Tables II-A / II-B and the training-route table (GuardRefused):
    the RL dataset and the D1 summary are training data by design (Secs. 3.3, 4.8) and never hold a registered test
    route; a stress report on recorded decision states of a registered test route (or one run with
    --allow-test-routes) and a coverage run over guarded clips are used only together with an analysis whose
    registered analysis-freeze record was verified (scope['freeze'] of analysis_permission)."""
    reg = G.registered_split()['test'] if registered is None else {str(r) for r in registered}
    frozen = bool(((scope or {}).get('freeze') or {}).get('registered'))
    for kind in ('rl_freeze', 'd1'):
        s = sources.get(kind)
        hit = sorted(set(s['routes']) & reg) if s else []
        if hit:
            raise GuardRefused(f'{s["path"]}: training data holding registered test routes {hit[:3]} ({G.RULE})')
    for slot in STRESS_SLOTS:
        s = sources.get(slot)
        hit = sorted(set(s['routes']) & reg) if s else []
        if s and (hit or s['allow_test_routes']) and not frozen:
            raise GuardRefused(f'{s["path"]}: decision states of registered test routes ({hit[:3]}; '
                               f'allow_test_routes {s["allow_test_routes"]}) without a registered analysis-freeze '
                               f'record ({G.RULE})')
    cov = sources.get('coverage')
    if cov and cov['clips'] and not frozen:
        raise GuardRefused(f'{cov["path"]}: guarded clips {cov["clips"][:3]} without a registered analysis-freeze '
                           f'record ({G.RULE})')


# ============================================================================================ Table II-A (Secs. 7.4,
# 7.5, 9.13)

def arrow(better):
    """The registered direction of a column as a header arrow ('' for a descriptive column)."""
    return {'higher': ' $\\uparrow$', 'lower': ' $\\downarrow$'}.get(better, '')


OFFLINE_DESIGNS = (('AGE', 'Age-Only'), ('GLOBAL', 'Global-Margin'), ('SUFFIX', 'Suffix-Aligned'))
OFFLINE_WHERE = {'subset': 'all', 'alpha': '0.05', 'risk': 'R_cond'}     # primary: nested, R_cond <= 5%, all plans
OFFLINE_NEEDS = {'fast': 0.964, 'meas': 1.842}                           # 2 L_rel + 0.05 s: fast prefix, measured
# nested.csv metric: (decimals of the percentage, the better direction of Sec. 7.4)
OFFLINE_METRICS = {'R_cond': (1, 'lower'), 'R_marg': (2, 'lower'), 'utilization': (1, 'higher'),
                   'premature_refresh': (1, 'lower'), 'continuity': (1, 'higher')}
CITED_ORDER = (('ra', 'model'), ('std', 'model'), ('ra', 'oracle'), ('std', 'oracle'))
CITED_LABEL = {('ra', 'model'): 'RA validity, model detections', ('std', 'model'): 'Standard validity, same setting',
               ('ra', 'oracle'): 'RA validity, oracle boxes', ('std', 'oracle'): 'Standard validity, oracle boxes'}


def _ci_pair(text):
    """(lo, hi) of a nested.csv interval cell '[lo, hi]'; (None, None) when it is empty or not an interval."""
    try:
        v = json.loads(text) if text else None
    except ValueError:
        v = None
    return (_num(v[0]), _num(v[1])) if isinstance(v, list) and len(v) == 2 else (None, None)


def offline_panel_data(offline, src, rnd, nums):
    """Panel (a) of Table II-A (Sec. 7.4, offline): per design (AGE, GLOBAL, SUFFIX) and need (0.964 s, 1.842 s) the
    nested leave-one-clip-out row of nested.csv at R_cond <= 5% over all plans (value and 95% clip-bootstrap interval
    of R_cond, R_marg, utilization, premature refresh and continuity), the plan, conflict and clip counts, the H4
    offline primary row of the analysis (h4_offline.csv; its SUFFIX and GLOBAL continuities must equal nested.csv and
    its paired.csv must be this directory's) and the cited RND cells (load_rnd). Recorded as tab2a.offline.*."""
    d = Path(offline) if offline is not None else ROOT / OFFLINE_REL
    path, folds = d / 'nested.csv', d / 'nested_folds.csv'
    if not path.is_file() or not folds.is_file():
        raise FigureError(f'{PJ.rel(d)}: no nested.csv / nested_folds.csv (offline lease ablation)')
    rows = read_csv(path)
    out = {'designs': {}, 'cited': {}, 'h4': None}
    for design, _ in OFFLINE_DESIGNS:
        for need in OFFLINE_NEEDS:
            where = {'design': design, **OFFLINE_WHERE, 'need': need}
            r = select_one(rows, PJ.rel(path), **where)
            cell = {}
            for m, (nd, _) in OFFLINE_METRICS.items():
                base = f'tab2a.offline.{design}.{need}.{m}'
                v, (lo, hi) = _num(r.get(m)), _ci_pair(r.get(f'{m}_ci'))
                cell[m] = {'value': nums.add(f'{base}.value', v, path, m, where, shown=fmt_num(v, nd, 100.0)),
                           'lo': nums.add(f'{base}.lo', lo, path, f'{m}_ci', where, shown=fmt_num(lo, nd, 100.0)),
                           'hi': nums.add(f'{base}.hi', hi, path, f'{m}_ci', where, shown=fmt_num(hi, nd, 100.0))}
            out['designs'][(design, need)] = cell
    where = {'design': 'SUFFIX', **OFFLINE_WHERE, 'need': 'fast'}
    r = select_one(rows, PJ.rel(path), **where)
    out['n_plans'] = nums.add('tab2a.offline.n_plans', int(r['n']), path, 'n', where, shown=r['n'])
    out['n_conflicts'] = nums.add('tab2a.offline.n_conflicts', int(r['conf']), path, 'conf', where, shown=r['conf'])
    fw = {'design': 'SUFFIX', 'subset': 'all', 'need': 'fast', 'alpha': '0.05'}
    clips = sorted({x['held_out_clip'] for x in select(read_csv(folds), **fw)})
    out['n_clips'] = nums.add('tab2a.offline.n_clips', len(clips), folds, 'held_out_clip', fw, shown=str(len(clips)),
                              derivation='count of the distinct held-out clips of the nested folds')
    for rk, ck in CITED_ORDER:
        c = rnd['cells'][(rk, ck)]
        where = {'table': RND_TABLE.strip('*. '), 'candidate set': c['row'], 'column': c['column']}
        out['cited'][(rk, ck)] = {f: nums.add(f'tab2a.offline.cited.{rk}.{ck}.{f}', c[f], rnd['file'], f'{f} (%)',
                                              where, shown=f'{c[f]:.1f}') for f in RND_FIELDS}
    if src is not None:
        out['h4'] = h4_offline_row(src, d, out, nums)
    return out


def h4_offline_row(src, offline_dir, panel, nums):
    """The H4 offline primary row of the analysis (h4_offline.csv, role primary; Sec. 9.4), recorded as
    tab2a.offline.h4.*. FigureError when the analysis read another paired.csv or its continuities differ from
    nested.csv (OFFLINE_TOL)."""
    rows = analysis_table(src, 'h4_offline.csv', nums)
    hpath = src['dir'] / 'h4_offline.csv'
    r = select_one(rows, PJ.rel(hpath), role='primary')
    files = (src['doc'].get('h4_offline') or {}).get('files') or {}
    paired = Path(offline_dir) / 'paired.csv'
    used = [s for k, s in files.items() if k.endswith('/paired.csv')]
    mine = PJ.sha256_file(paired) if paired.is_file() else None
    if mine is None or used != [mine]:
        raise FigureError(f'{PJ.rel(paired)}: sha256 {mine} is not that of the paired.csv the analysis read {used}')
    for col, design in (('a_value', r['a']), ('b_value', r['b'])):
        mine = panel['designs'].get((design, r['need']), {}).get(r['metric'], {}).get('value')
        if mine is None or _num(r[col]) is None or abs(mine - _num(r[col])) > AN.OFFLINE_TOL:
            raise FigureError(f'{PJ.rel(hpath)}: {col} {r[col]} of {design} differs from nested.csv ({mine})')
    where = {'role': 'primary'}
    out = {f: nums.add(f'tab2a.offline.h4.{f}', _num(r[f]), hpath, f, where, shown=fmt_num(_num(r[f]), 1, 100.0))
           for f in ('diff', 'lo', 'hi', 'r_cond_diff', 'r_cond_lo', 'r_cond_hi')}
    out['label'] = nums.add('tab2a.offline.h4.label', r['label'], hpath, 'label', where, shown=r['label'])
    out['a'], out['b'], out['need_s'] = r['a'], r['b'], r['need_s']
    return out


COVERAGE_TAUS = ('0.0', '1.0', '2.0', '3.0')
COVERAGE_PATH = 'path_coverage_0_3s'
COVERAGE_CLASSES = ('vehicle', 'pedestrian')


def coverage_panel_data(cov, nums):
    """Panel (b) of Table II-A (Proposition 1 reporting, Secs. 7.4, 9.13): per deployed envelope (prop1_coverage
    'deployed', in its order, with its role) and class the per-tau coverage at COVERAGE_TAUS and the whole-path
    coverage on [0, 3 s] with its 95% clip-bootstrap interval and pair count (coverage.csv). Recorded as
    tab2a.coverage.<envelope>.<class>.*."""
    path = cov['dir'] / 'coverage.csv'
    dep = cov['doc'].get('deployed') or {}
    out = []
    for env in dep.get('deployed') or []:
        for cls in COVERAGE_CLASSES:
            base = f'tab2a.coverage.{env}.{cls}'
            cell = {'envelope': env, 'role': (dep.get('roles') or {}).get(env), 'class': cls, 'tau': {}}
            for tau in COVERAGE_TAUS:
                where = {'envelope': env, 'class': cls, 'metric': 'per_tau', 'tau_s': tau}
                r = select_one(cov['rows'], PJ.rel(path), **where)
                v = _num(r['coverage'])
                cell['tau'][tau] = nums.add(f'{base}.tau{tau}', v, path, 'coverage', where, shown=fmt_num(v, 1, 100.0))
            where = {'envelope': env, 'class': cls, 'metric': COVERAGE_PATH}
            r = select_one(cov['rows'], PJ.rel(path), **where)
            for k, f in (('path', 'coverage'), ('lo', 'ci_lo'), ('hi', 'ci_hi')):
                cell[k] = nums.add(f'{base}.{COVERAGE_PATH}.{k}', _num(r[f]), path, f, where,
                                   shown=fmt_num(_num(r[f]), 1, 100.0))
            cell['n'] = nums.add(f'{base}.{COVERAGE_PATH}.n', int(r['n']), path, 'n', where, shown=r['n'])
            out.append(cell)
    return out


T2A_SUBSET, T2A_KAPPA, T2A_SEED = 'E', 1.0, 11
T2A_LEASE = (('age_only', 'Age-Only lease'), ('fl_global_shield', 'Global-Margin lease'),
             ('fl_heuristic', 'Suffix-Aligned lease'))
# (conditions.csv metric, decimals, scale, header lines)
PCT = '(\\%)'
T2A_LEASE_COLUMNS = (('driving_score', 1, 1.0, ('DS', '[95\\% CI]')), ('fallback_ratio', 1, 100.0, ('Fallback', PCT)),
                     ('dmr', 1, 100.0, ('DMR', PCT)), ('lease_utilization', 1, 100.0, ('Util.', PCT)),
                     ('premature_expiry_ratio', 1, 100.0, ('Prem.', 'expiry (\\%)')), ('eir', 2, 100.0, ('EIR', PCT)),
                     ('r_cond', 1, 100.0, ('$R_\\mathrm{cond}$', PCT)),
                     ('p_both', 1, 100.0, ('$P_\\mathrm{both}$', PCT)))
T2A_RL = (('fl_heuristic', 'Shield + Heuristic', None), ('fl_bandit', 'Shield + Contextual Bandit', 'bandit'),
          ('fl_full', 'Shield + FQI (Full FrameLease)', 'fqi'),
          ('fl_fqi_nolease', 'FQI w/o lease features', 'fqi_nolease'))
T2A_RL_COLUMNS = (('driving_score', 1, 1.0, ('DS', '[95\\% CI]')), ('p_both', 1, 100.0, ('$P_\\mathrm{both}$', PCT)),
                  ('deviation_rate', 1, 100.0, ('Deviation', '(\\%)')), ('bypass_rate', 2, 100.0, ('Bypass', '(\\%)')))
QNET_KEYS = ('qnet_s_p50', 'qnet_s_p99')


def _subset_cells(rows, path, nums, base, arm, columns, subset=T2A_SUBSET):
    cond = AN.Cond(arm, T2A_KAPPA, T2A_SEED).name
    return {m: _condition_value(rows, path, nums, f'{base}.{arm}.{m}', cond, m, 'route_mean', nd, scale, subset=subset)
            for m, nd, scale, _ in columns}


def closed_lease_panel_data(src, nums):
    """Panel (c) of Table II-A (Sec. 7.4, closed loop): the three leases with the same shield and utility on E at
    kappa 1.0, seed 11 (conditions.csv, route means and 95% route-bootstrap intervals) and the H4-cl contrasts with
    their Holm-adjusted p and labels (family_H4-cl.csv). Recorded as tab2a.lease.*."""
    rows = analysis_table(src, 'conditions.csv', nums)
    path = src['dir'] / 'conditions.csv'
    return {'arms': {arm: _subset_cells(rows, path, nums, 'tab2a.lease', arm, T2A_LEASE_COLUMNS)
                     for arm, _ in T2A_LEASE},
            'h4cl': family_rows(src, nums, 'H4-cl', 'tab2a.lease.h4cl')}


def rl_link(src, rl):
    """The RL freeze of Table II-A against the analysis (Secs. 5.8, 9.13). The analysis decided the H2 RL-benefit
    statement with the P_both label of the RL freeze it read (analysis.json decisions.H2.p_both) and its aggregations
    name the RL freeze of their runs (analysis.json sources, rl_sha256). A given RL freeze (the FQE column) must be
    that freeze; FigureError otherwise, and when the analysis names two. The dataset P_both of Table II-A is always the
    analysis's (rl_panel_data). Returns the development reasons: an RL freeze given with an analysis that names none
    (its dataset P_both is then left out; the RL-benefit statement is the analysis's)."""
    doc = src['doc']
    pb = _jget(doc, ['decisions', 'H2', 'p_both'])
    named = {pb.get('sha256')} if isinstance(pb, dict) else set()
    named |= {x.get('rl_sha256') for x in doc.get('sources') or [] if isinstance(x, dict)}
    named.discard(None)
    if len(named) > 1:
        raise FigureError(f'{src["path"]}/analysis.json: names {len(named)} RL freezes '
                          f'{sorted(n[:12] for n in named)} (decisions.H2.p_both, sources rl_sha256)')
    if rl is None:
        return []
    if named and rl['sha256'] not in named:
        where = pb.get('path') if isinstance(pb, dict) else 'the RL freeze of its aggregations'
        raise FigureError(f'{rl["path"]}: sha256 {rl["sha256"][:12]} is not the RL freeze the analysis read ({where}, '
                          f'{next(iter(named))[:12]}): Table II-A would print the H2 RL-benefit statement of one RL '
                          'freeze next to the FQE estimates of another')
    if not named:
        return [f'{rl["path"]}: the analysis used no RL freeze (H2 RL benefit '
                f'{_jget(doc, ["decisions", "H2", "rl_benefit"])!r}); Table II-A shows the FQE estimates of this '
                'record and leaves out its dataset P_both']
    return []


def rl_gain_data(src, nums):
    """The breakdown of the RL gain (Sec. 7.5; descriptive; analysis.json 'rl_gain'): Full FrameLease - FrameLease +
    Heuristic DS by Bench2Drive ability (44 routes), by kappa on E and by seed on R: {'ability': [(ability, cell)],
    'kappa': [(kappa, cell)], 'seed': [(seed, cell)]} with cell {'mean', 'lo', 'hi', 'n'} (the 95% route-bootstrap
    interval, None below 5 routes), recorded as tab2a.rl_gain.<ability.<ability> | kappa<k> | seed<s>>.*. FigureError
    when the analysis has no breakdown."""
    doc, apath = src['doc'], src['dir'] / 'analysis.json'
    gain = doc.get('rl_gain')
    if not isinstance(gain, dict):
        raise FigureError(f'{src["path"]}/analysis.json: no rl_gain (the Sec. 7.5 breakdown of the RL gain)')
    one = lambda v: fmt_num(_num(v), 1)  # noqa: E731

    def cell(key, path):
        return {'mean': json_add(nums, f'{key}.mean', doc, path + ['mean'], apath, shown=one),
                'lo': json_add(nums, f'{key}.lo', doc, path + ['ci95', 0], apath, shown=one),
                'hi': json_add(nums, f'{key}.hi', doc, path + ['ci95', 1], apath, shown=one),
                'n': json_add(nums, f'{key}.n', doc, path + ['n'], apath, shown=_yes)}
    out = {'ability': [(r.get('ability'), cell(f'tab2a.rl_gain.ability.{r.get("ability")}',
                                               ['rl_gain', 'by_ability', i]))
                       for i, r in enumerate(gain.get('by_ability') or [])],
           'kappa': [(k, cell(f'tab2a.rl_gain.kappa{k}', ['rl_gain', 'by_kappa_on_E', k]))
                     for k in sorted(gain.get('by_kappa_on_E') or {}, key=float)],
           'seed': [(x, cell(f'tab2a.rl_gain.seed{x}', ['rl_gain', 'by_seed_on_R', x]))
                    for x in sorted(gain.get('by_seed_on_R') or {}, key=int)]}
    return out


def rl_panel_data(src, rl, nums):
    """Panel (d) of Table II-A (Sec. 7.5): the four utilities on E at kappa 1.0 (conditions.csv: DS, P_both, deviation
    and bypass rates), the Q-network p50 / p99 of each condition (analysis.json overhead: the median over its runs of
    the per-run quantiles), the FQE estimate and 90% interval of each family's selected candidate (the RL freeze, which
    rl_link checked against the analysis), the RL-abl and H2 contrasts (family_RL-abl.csv, family_H2.csv), the H2
    RL-benefit statement and the P_both of the RL dataset with its Sec. 5.8 label as the analysis read them
    (analysis.json decisions.H2; None when the analysis used no RL freeze), and the breakdown of the RL gain
    (rl_gain_data). Recorded as tab2a.rl.* and tab2a.rl_gain.*. FigureError (rl_link) for an RL freeze other than the
    analysis's."""
    rl_link(src, rl)
    rows = analysis_table(src, 'conditions.csv', nums)
    path, apath = src['dir'] / 'conditions.csv', src['dir'] / 'analysis.json'
    arms = {}
    for arm, _, fam in T2A_RL:
        cells = _subset_cells(rows, path, nums, 'tab2a.rl', arm, T2A_RL_COLUMNS)
        cond = AN.Cond(arm, T2A_KAPPA, T2A_SEED).name
        for q in QNET_KEYS:
            cells[q] = json_add(nums, f'tab2a.rl.{arm}.{q}.median', src['doc'], ['overhead', cond, q, 'median'], apath,
                                shown=lambda v: fmt_num(_num(v), 1, 1e6))
        if fam is not None and rl is not None:
            est = ['families', fam, 'estimate']
            cells['fqe'] = {
                'mean': json_add(nums, f'tab2a.rl.{arm}.fqe.mean_delta', rl['doc'], est + ['mean_delta'], rl['file'],
                                 shown=lambda v: fmt_num(_num(v), 2)),
                'lo': json_add(nums, f'tab2a.rl.{arm}.fqe.ci90_lo', rl['doc'], est + ['ci90', 0], rl['file'],
                               shown=lambda v: fmt_num(_num(v), 2)),
                'hi': json_add(nums, f'tab2a.rl.{arm}.fqe.ci90_hi', rl['doc'], est + ['ci90', 1], rl['file'],
                               shown=lambda v: fmt_num(_num(v), 2)),
                'not_trainable': json_add(nums, f'tab2a.rl.{arm}.fqe.not_trainable', rl['doc'],
                                          ['families', fam, 'not_trainable'], rl['file'])}
        arms[arm] = cells
    out = {'arms': arms, 'rlabl': family_rows(src, nums, 'RL-abl', 'tab2a.rl.rlabl'),
           'h2': family_rows(src, nums, 'H2', 'tab2a.rl.h2'),
           'rl_benefit': json_add(nums, 'tab2a.rl.h2.rl_benefit', src['doc'], ['decisions', 'H2', 'rl_benefit'], apath,
                                  shown=lambda v: v),
           'p_both': None, 'gain': rl_gain_data(src, nums)}
    if isinstance(_jget(src['doc'], ['decisions', 'H2', 'p_both']), dict):
        pb = ['decisions', 'H2', 'p_both']
        out['p_both'] = {k: json_add(nums, f'tab2a.rl.dataset.p_both.{k}', src['doc'], pb + [k], apath, shown=sh)
                         for k, sh in (('p_both', lambda v: fmt_num(_num(v), 1, 100.0)), ('label', lambda v: v),
                                       ('threshold', lambda v: fmt_num(_num(v), 0, 100.0)),
                                       ('kappa', lambda v: fmt_num(_num(v), 1)))}
    return out


def table2a_data(src, offline, rnd, cov, rl, nums):
    """Everything Table II-A shows: panels (a) offline lease, (b) Proposition-1 coverage (None without
    --coverage), (c) closed-loop lease and (d) RL (FQE columns empty without --rl-freeze)."""
    return {'offline': offline_panel_data(offline, src, rnd, nums),
            'coverage': None if cov is None else coverage_panel_data(cov, nums),
            'lease': closed_lease_panel_data(src, nums), 'rl': rl_panel_data(src, rl, nums)}


def _pct_ci(c, nd, ci=True):
    """'value [lo, hi]' in percent of an offline cell (value, lo, hi as fractions)."""
    return fmt_ci(c['value'], c['lo'] if ci else None, c['hi'] if ci else None, nd, 100.0)


def _arm_cells(cells, columns, short):
    """The LaTeX cells of one closed-loop row (DS with its interval, the rest as means); a dagger where the condition
    has fewer routes than its subset (short collects them)."""
    row = []
    for m, nd, scale, _ in columns:
        v = cells[m]
        text = fmt_ci(v['mean'], v['lo'], v['hi'], nd, scale) if m == 'driving_score' else \
            fmt_num(v['mean'], nd, scale, floor=m in RATE_METRICS)
        if v['mean'] is not None and v['n'] < v['n_routes']:
            text += DAGGER
            short.append(m)
        row.append(text)
    return row


def table_2a(data, status, out):
    """Table II-A (table*, booktabs, four panels under one caption) as table2a.tex: (a) the offline lease ablation with
    the cited RA rows, (b) the Proposition-1 envelope coverage, (c) the closed-loop lease panel, (d) the RL panel.
    Returns the file names."""
    off, cov, lease, rl = data['offline'], data['coverage'], data['lease'], data['rl']
    head_a = ['Lease'] + [hdr(f'$R_\\mathrm{{cond}}${arrow("lower")}', '(\\%) [95\\% CI]'),
                          hdr(f'$R_\\mathrm{{marg}}${arrow("lower")}', '(\\%)'),
                          hdr(f'Util.{arrow("higher")}', '(\\%)'), hdr(f'Prem. refresh{arrow("lower")}', '(\\%)'),
                          hdr(f'Continuity{arrow("higher")}', '0.964 s (\\%) [95\\% CI]'),
                          hdr('Continuity', '1.842 s (\\%) [95\\% CI]')]
    body_a = []
    for design, label in OFFLINE_DESIGNS:
        f, m = off['designs'][(design, 'fast')], off['designs'][(design, 'meas')]
        body_a.append([latex_escape(label), _pct_ci(f['R_cond'], 1), _pct_ci(f['R_marg'], 2, False),
                       _pct_ci(f['utilization'], 1, False), _pct_ci(f['premature_refresh'], 1, False),
                       _pct_ci(f['continuity'], 1), _pct_ci(m['continuity'], 1)])
    body_a.append('\\midrule')
    for key in CITED_ORDER:
        c = off['cited'][key]
        body_a.append([latex_escape(CITED_LABEL[key]) + CITED,
                       f'{c["r_cond"]:.1f} [{c["r_cond_lo"]:.1f}, {c["r_cond_hi"]:.1f}]', '--', '--', '--', '--',
                       f'{c["continuity"]:.1f} [{c["continuity_lo"]:.1f}, {c["continuity_hi"]:.1f}]'])
    title_a = (f'\\textbf{{(a)}} Offline lease ablation: {off["n_clips"]} VAL clips, {off["n_plans"]} depth-1 plans, '
               f'{off["n_conflicts"]} conflict plans; nested leave-one-clip-out selection at $R_\\mathrm{{cond}} '
               f'\\le$ 5\\%')
    panels = [{'title': title_a, 'colspec': 'l' + 'c' * 6, 'header': [head_a], 'body': body_a}]
    if cov is not None:
        head_b = (['Envelope', 'Class', 'Pairs']
                  + [hdr('Per $\\tau$', f'{float(t):.0f} s (\\%)') for t in COVERAGE_TAUS]
                  + [hdr('Whole path', '0--3 s (\\%) [95\\% CI]')])
        body_b = [[latex_escape(f'{c["envelope"]} ({c["role"]})'), c['class'], str(c['n'])]
                  + [fmt_num(c['tau'][t], 1, 100.0) for t in COVERAGE_TAUS]
                  + [fmt_ci(c['path'], c['lo'], c['hi'], 1, 100.0)] for c in cov]
        panels.append({'title': '\\textbf{(b)} Proposition 1: envelope coverage of the deployed lease envelope on the '
                                f'{off["n_clips"]} VAL clips',
                       'colspec': 'llr' + 'c' * (len(COVERAGE_TAUS) + 1), 'header': [head_b], 'body': body_b})
    short = []
    head_c = ['Lease'] + [hdr(h[0] + arrow(AN.METRICS[m].better), h[1]) for m, _, _, h in T2A_LEASE_COLUMNS]
    body_c = [[latex_escape(label)] + _arm_cells(lease['arms'][arm], T2A_LEASE_COLUMNS, short)
              for arm, label in T2A_LEASE]
    letter = 'c' if cov is not None else 'b'
    panels.append({'title': f'\\textbf{{({letter})}} Closed-loop lease ablation: subset E, $\\kappa$ = 1.0, seed 11, '
                            'same shield and utility $a_\\mathrm{det}^{d^*}$',
                   'colspec': 'l' + 'c' * len(T2A_LEASE_COLUMNS), 'header': [head_c], 'body': body_c})
    head_d = ['Utility'] + [hdr(h[0] + arrow(AN.METRICS[m].better), h[1]) for m, _, _, h in T2A_RL_COLUMNS] + [
        hdr('Q-net', 'p50 ($\\mu$s)'), hdr('Q-net', 'p99 ($\\mu$s)'), hdr('FQE $\\Delta$', '[90\\% CI]')]
    body_d = []
    for arm, label, fam in T2A_RL:
        c = rl['arms'][arm]
        q = [fmt_num(_num(c[k]), 1, 1e6) for k in QNET_KEYS]
        fq = c.get('fqe')
        if fam is None:
            fqe = 'ref.'
        elif fq is None:
            fqe = '--'
        else:
            fqe = fmt_ci(_num(fq['mean']), _num(fq['lo']), _num(fq['hi']), 2) + (DDAGGER if fq['not_trainable'] else '')
        body_d.append([latex_escape(label)] + _arm_cells(c, T2A_RL_COLUMNS, short) + q + [fqe])
    letter = chr(ord(letter) + 1)
    panels.append({'title': f'\\textbf{{({letter})}} RL contribution: subset E, $\\kappa$ = 1.0, seed 11, same shield '
                            'and lease',
                   'colspec': 'l' + 'c' * (len(T2A_RL_COLUMNS) + 3), 'header': [head_d], 'body': body_d})
    notes = _table2a_notes(data, short)
    tex = booktabs_panels(panels, 'Mechanism ablations: validity lease and RL contribution', 'tab:table2a', notes,
                          True, status, part='A')
    _write_text(Path(out) / 'table2a.tex', tex)
    return ['table2a.tex']


def _rl_gain_note(gain):
    """The note of the breakdown of the RL gain (rl_gain_data): mean [95% CI] (n) per ability, kappa and seed."""
    def cell(label, c):
        f = lambda v: fmt_num(_num(v), 1)  # noqa: E731
        ci = '' if c['lo'] is None or c['hi'] is None else f' [{f(c["lo"])}, {f(c["hi"])}]'
        return f'{label}: {f(c["mean"])}{ci} (n {_yes(c["n"])})'
    return ('RL gain (Full FrameLease $-$ FrameLease + Heuristic, DS; descriptive, Sec. 7.5 of the protocol): by '
            'ability on the 44 routes, ' + '; '.join(cell(latex_escape(ABILITY_LABEL.get(a, a)), c)
                                                     for a, c in gain['ability'])
            + '; by GPU budget on E, ' + '; '.join(cell(f'$\\kappa$ {_num(k):.1f}', c) for k, c in gain['kappa'])
            + '; by seed on R, ' + '; '.join(cell(f'seed {latex_escape(x)}', c) for x, c in gain['seed'])
            + '; 95\\% route-bootstrap intervals (none below 5 routes).')


def _table2a_notes(data, short):
    off, rl = data['offline'], data['rl']
    meas = '; '.join(f'{latex_escape(label)} {fmt_num(off["designs"][(d, "meas")]["R_cond"]["value"], 1, 100.0)}'
                     for d, label in OFFLINE_DESIGNS)
    notes = [f'(a) Realized validity of every plan; each lease at its nested leave-one-clip-out choice under rule (a) '
             f'at $R_\\mathrm{{cond}} \\le$ 5\\% for the need 0.964 s; the 1.842 s column is its own nested choice '
             f'(realized $R_\\mathrm{{cond}}$, \\%: {meas}); 95\\% clip-bootstrap intervals (2000 resamples).']
    h4 = off.get('h4')
    if h4:
        pts = lambda k: fmt_num(h4[k], 1, 100.0)  # noqa: E731
        notes.append(f'H4 offline ({latex_escape(h4["a"])} $-$ {latex_escape(h4["b"])}, continuity at '
                     f'{latex_escape(h4["need_s"])} s): {pts("diff")} [{pts("lo")}, {pts("hi")}] points at an '
                     f'$R_\\mathrm{{cond}}$ difference of {pts("r_cond_diff")} [{pts("r_cond_lo")}, '
                     f'{pts("r_cond_hi")}] points: {latex_escape(h4["label"])} (pre-specified in code, executed '
                     'before registration).')
    notes.append(f'{CITED} Cited from the renewal study (another setting: lease renewal on a shared GPU with the '
                 'perception pass aligned with the release, 15 VAL clips, the unmodified prefix with need 1.842 s; '
                 'continuity and realized $R_\\mathrm{cond}$). RA changes the validity definition '
                 '(responsibility-aware validity); these rows are not compared statistically with the rows above and '
                 'are not standard-validity safety evidence.')
    if data['coverage'] is not None:
        notes.append('(b) Proposition 1 holds under its envelope assumption; per-$\\tau$ coverage '
                     '$P(\\mathrm{iso}(\\tau) \\le B_c(\\tau))$ of matched detections and whole-path coverage on '
                     '[0, 3 s], 95\\% clip-bootstrap interval: empirical coverage, not a guarantee.'
                     + (' Before the tuning freeze every kept envelope is listed as a candidate.'
                        if any(c['role'] == 'candidate' for c in data['coverage']) else ''))
    notes.append('Closed loop: route means over subset E (22 test routes); DS with its 95\\% route-bootstrap '
                 'interval. H4-cl (Suffix-Aligned $-$ each, Holm over 2): '
                 + fmt_contrasts(data['lease']['h4cl'], {**ARM_LABEL, 'fl_global_shield': 'Global-Margin',
                                                         'age_only': 'Age-Only'}) + '.')
    rl_text = ('RL: Q-net p50 / p99 are the per-run quantiles of the network wall time, median over the runs of the '
               'condition; FQE $\\Delta$: cross-fitted FQE estimate of the selected candidate relative to '
               '$a_\\mathrm{det}^{d^*}$ (DS points per episode) with its 90\\% route-cluster bootstrap interval. '
               'RL-abl (Full FrameLease $-$ each, Holm over 2): ' + fmt_contrasts(rl['rlabl']) + '. H2 (key secondary, '
               'single test, 44 routes): ' + fmt_contrasts(rl['h2'])
               + f'; RL benefit: {tex_text(rl["rl_benefit"] or "--")}.')
    pb = rl.get('p_both')
    if pb:
        rl_text += (f' $P_\\mathrm{{both}}$ of the RL dataset ($\\kappa$ = {fmt_num(_num(pb["kappa"]), 1)} episodes): '
                    f'{fmt_num(_num(pb["p_both"]), 1, 100.0)}\\% ({latex_escape(pb["label"] or "--")}; threshold '
                    f'{fmt_num(_num(pb["threshold"]), 0, 100.0)}\\%).')
    notes.append(rl_text)
    notes.append(_rl_gain_note(rl['gain']))
    if any((c.get('fqe') or {}).get('not_trainable') for c in rl['arms'].values()):
        notes.append(f'{DDAGGER} Family not trainable: the deployed network is the '
                     '$a_\\mathrm{det}^{d^*}$-equivalent network.')
    if short:
        notes.append(f'{DAGGER} after a closed-loop value: fewer routes than the subset (pairwise-complete; Sec. 9.8 '
                     'of the protocol). --: no value.')
    else:
        notes.append('--: no value.')
    return notes


# ============================================================================================ Table II-B (Sec. 7.6)

# panel (a): the kappa-1.0 Table I runs of every shield arm of Table I and the kappa-2.0 Fig. 3 runs (GPU contention,
# S4), from analysis.json 'overhead' (per condition: per-run values, distribution over the runs)
T2B_CONDS = (('age_only', 1.0), ('fl_heuristic', 1.0), ('fl_full', 1.0), ('fl_heuristic', 2.0), ('fl_full', 2.0))
T2B_SHORT = {'age_only': 'Age-Only', 'fl_heuristic': 'FL + Heuristic', 'fl_full': 'Full FrameLease'}
# (row label, kind, overhead keys, scale, decimals); kind: 'q' p50 / p99 (median over runs of the per-run quantiles),
# 'mean' (mean over runs, percent), 'count' (total over runs), 'above' (runs with a per-run p99 above B_pi), 'bypass'
# (bypass epochs and the mean per-run bypass rate), 'runs'
T2B_ROWS = (
    ('Runs', 'runs', (), 1.0, 0),
    ('CPU Q-network inference p50 / p99 ($\\mu$s)', 'q', ('qnet_s_p50', 'qnet_s_p99'), 1e6, 1),
    ('Runs with Q-network p99 $> B_\\pi$', 'above', ('qnet_s_p99',), 1.0, 0),
    ('Policy bypass: epochs (mean rate, \\%)', 'bypass', ('bypass_epochs', 'bypass_rate'), 100.0, 2),
    ('Shield decision p50 / p99 ($\\mu$s)', 'q', ('decision_wall_s_p50', 'decision_wall_s_p99'), 1e6, 1),
    ('Lease computation p50 / p99 (ms)', 'q', ('lease_wall_s_p50', 'lease_wall_s_p99'), 1e3, 2),
    ('GPU quantum: charged prefix p50 / p99 (ms)', 'q', ('prefix_quantum_s_p50', 'prefix_quantum_s_p99'), 1e3, 0),
    ('GPU quantum: flow step p50 / p99 (ms)', 'q', ('step_quantum_s_p50', 'step_quantum_s_p99'), 1e3, 1),
    ('Switching latency p50 / p99 (ms)', 'q', ('switching_latency_s_p50', 'switching_latency_s_p99'), 1e3, 2),
    ('Cancelled GPU work (\\% of GPU-busy time)', 'mean', ('cancelled_gpu_share',), 100.0, 1),
    ('Versioned commit: validation p50 / p99 ($\\mu$s)', 'q', ('validation_s_p50', 'validation_s_p99'), 1e6, 0),
    ('Commit-gate rejects', 'count', ('gate_rejects',), 1.0, 0),
    ('DMR (\\%)', 'mean', ('dmr',), 100.0, 2),
    ('Fallback episodes', 'count', ('fallback_episodes',), 1.0, 0),
    ('Shield violations', 'count', ('shield_violations',), 1.0, 0),
    ('Budget overruns', 'count', ('budget_overruns',), 1.0, 0),
)
T2B_RATE_KINDS = ('mean', 'bypass')        # rows whose (second) value is a rate or share (fmt_num floor)
S1_COMPONENTS = (('qnet_call', 1), ('shield_decision', 1), ('lease', 0), ('commit_check', 1))   # (component, decimals)
S1_STATS = ('p50_us', 'p99_us', 'max_us')
S2_FIELDS = (('share_admitted', 100.0, 1), ('admitted_bound_ge_Dstar', 1.0, 0), ('bypass_rate', 100.0, 2),
             ('bypass_rate_slack', 100.0, 2), ('bypass_rate_timing', 100.0, 2), ('violations_total', 1.0, 0))
S3_FIELDS = ('sequences', 'offers', 'accepted', 'violations_total', 'coverage_ok')
NET_LABEL = {'fqi': 'Full FrameLease (FQI)', 'bandit': 'Contextual Bandit', 'fqi_nolease': 'FQI w/o lease features'}


def _cond_name(arm, kappa):
    return AN.Cond(arm, kappa, 11).name


def logs_panel_data(src, nums):
    """Panel (a) of Table II-B (Sec. 7.6, from the logs): per condition of T2B_CONDS every T2B_ROWS quantity of
    analysis.json 'overhead' (the per-run p50 / p99 are not pooled across runs: the median over the runs is shown),
    the commit-gate reject reasons summed over the conditions, and the commit audit of the analysis (H5). Recorded as
    tab2b.logs.<condition>.<key>.*."""
    apath, doc = src['dir'] / 'analysis.json', src['doc']
    out = {'cells': {}, 'reasons': {}}
    show = {}
    for arm, kappa in T2B_CONDS:
        cond = _cond_name(arm, kappa)
        base, root = f'tab2b.logs.{cond}', ['overhead', cond]
        cells = {}
        for label, kind, keys, scale, nd in T2B_ROWS:
            f = (lambda v, s=scale, n=nd, fl=kind in T2B_RATE_KINDS: fmt_num(_num(v), n, s, floor=fl))
            if kind == 'runs':
                cells[label] = (json_add(nums, f'{base}.runs', doc, root + ['runs'], apath, shown=f),)
            elif kind == 'q':
                cells[label] = tuple(json_add(nums, f'{base}.{k}.median', doc, root + [k, 'median'], apath, shown=f)
                                     for k in keys)
            elif kind == 'mean':
                cells[label] = (json_add(nums, f'{base}.{keys[0]}.mean', doc, root + [keys[0], 'mean'], apath,
                                         shown=f),)
            elif kind == 'count':
                cells[label] = (json_add(nums, f'{base}.{keys[0]}.total', doc, root + [keys[0], 'total'], apath,
                                         shown=f),)
            elif kind == 'above':
                cells[label] = (json_add(nums, f'{base}.qnet_s_p99.runs_above_b_pi', doc,
                                         root + ['qnet_s_p99', 'runs_above_b_pi'], apath, shown=f),
                                json_add(nums, f'{base}.qnet_s_p99.runs', doc, root + ['qnet_s_p99', 'runs'], apath,
                                         shown=f))
            elif kind == 'bypass':
                cells[label] = (json_add(nums, f'{base}.bypass_epochs.total', doc, root + ['bypass_epochs', 'total'],
                                         apath, shown=lambda v: fmt_num(_num(v), 0)),
                                json_add(nums, f'{base}.bypass_rate.mean', doc, root + ['bypass_rate', 'mean'], apath,
                                         shown=f))
            show[label] = (kind, scale, nd)
        for r, n in ((_jget(doc, root + ['gate_rejects', 'by_reason']) or {})).items():
            out['reasons'][r] = out['reasons'].get(r, 0) + (int(n) if isinstance(n, (int, float)) else 0)
        out['cells'][cond] = cells
    if out['reasons']:
        nums.add('tab2b.logs.gate_rejects_by_reason', dict(sorted(out['reasons'].items())), apath,
                 'overhead.<condition>.gate_rejects.by_reason', {'conditions': [_cond_name(*c) for c in T2B_CONDS]},
                 derivation='sum over the conditions of panel (a)')
    out['audit'] = {k: json_add(nums, f'tab2b.h5.{k}', doc, p, apath, shown=sh)
                    for k, p, sh in (('commit_audit_violations', ['h5', 'commit_audit_violations'], str),
                                     ('label', ['decisions', 'H5', 'label'], lambda v: v),
                                     ('s3_violations', ['h5', 's3_violations'], str))}
    h5 = doc.get('h5') or {}
    audits = h5.get('audits') or []
    for f in ('runs_audited', 'accepted'):
        total = sum(int(a.get(f) or 0) for a in audits) if audits else None
        out['audit'][f] = nums.add(f'tab2b.h5.{f}', total, apath, f'h5.audits.{f}', {'json_path': ['h5', 'audits']},
                                   shown=None if total is None else str(total),
                                   derivation=f'sum of {f} over the {len(audits)} commit audits of the analysis')
    phases = ', '.join(h5.get('phases_covered') or []) or None
    out['audit']['phases'] = nums.add('tab2b.h5.phases_covered', phases, apath, 'h5.phases_covered',
                                      {'json_path': ['h5', 'phases_covered']}, shown=phases,
                                      derivation='the covered phases joined by commas')
    out['show'] = show
    return out


def _s1_network(doc):
    """The network of the S1 report whose rows Table II-B shows: the FQI family's (Full FrameLease), else the
    first; (name, family)."""
    nets = (doc.get('plan') or {}).get('networks') or []
    pick = next((n for n in nets if n.get('family') == 'fqi'), nets[0] if nets else {})
    return pick.get('name'), pick.get('family')


def s1_panel_data(s1, nums):
    """Panel (b) of Table II-B (S1, CPU contention): per load level p50 / p99 / max (us) of the Q-network call and its
    overrun rate against B_pi, shield + decision with that network (all epochs), the lease and the commit check
    (stress_bench s1 report); the title names the network by its family (NET_LABEL). Recorded as tab2b.s1.load<L>.*."""
    doc, (name, family) = s1['doc'], _s1_network(s1['doc'])
    nums.add('tab2b.s1.network', name, s1['file'], 'plan.networks.name', {'family': family}, shown=name)
    rows = []
    for i, lv in enumerate(doc.get('per_load') or []):
        load = lv.get('load')
        base, root = f'tab2b.s1.load{load}', ['per_load', i]
        paths = {'qnet_call': root + ['qnet_call', name], 'shield_decision': root + ['shield_decision', name, 'all'],
                 'lease': root + ['lease'], 'commit_check': root + ['commit_check']}
        row = {'load': json_add(nums, f'{base}.load', doc, root + ['load'], s1['file'], shown=str)}
        for comp, nd in S1_COMPONENTS:
            for st in S1_STATS:
                row[(comp, st)] = json_add(nums, f'{base}.{comp}.{st}', doc, paths[comp] + [st], s1['file'],
                                           shown=lambda v, n=nd: fmt_num(_num(v), n))
        row[('qnet_call', 'overrun_rate')] = json_add(nums, f'{base}.qnet_call.overrun_rate', doc,
                                                      paths['qnet_call'] + ['overrun_rate'], s1['file'],
                                                      shown=lambda v: fmt_num(_num(v), 2, 100.0, floor=True))
        rows.append(row)
    plan = doc.get('plan') or {}
    return {'network': name, 'family': family, 'rows': rows, 'states': (plan.get('states') or {}).get('source'),
            'scenes': (plan.get('scenes') or {}).get('source')}


def _s2_order(doc):
    """The networks of an S2 report in the order of RL_FAMILIES (then by name)."""
    order = {f: i for i, (f, _) in enumerate(RL_FAMILIES)}
    nets = doc.get('networks') or {}
    return sorted(nets, key=lambda n: (order.get(nets[n].get('family'), 99), n))


def s2_panel_data(s2, s2r, nums):
    """Panel (c) of Table II-B (S2, near deadline): per grid (the registered grid D* = t + s; the supplementary grid
    relative to each state's slack floor, Amendment A7) and deployed network the share of admitted actions, the
    admitted actions with bound >= D* (must be 0), the bypass rate with its near-deadline and CPU-timing parts and
    the violations; the states swept, pass and (relative grid) the floor check. Recorded as tab2b.s2.<grid>.*."""
    out = []
    for grid, s in (('registered', s2), ('relative', s2r)):
        if s is None:
            continue
        doc, base = s['doc'], f'tab2b.s2.{grid}'
        head = {'grid': grid, 'n_swept': json_add(nums, f'{base}.n_swept', doc, ['n_swept'], s['file'], shown=str),
                'pass': json_add(nums, f'{base}.pass', doc, ['pass'], s['file'], shown=str), 'nets': [],
                'states': (doc.get('states') or {}).get('source')}
        if grid == 'registered':
            head['floor_p50'] = {k: json_add(nums, f'{base}.slack_floor.kappa{k}.p50', doc,
                                             ['slack_floor', k, 'floor_any_s', 'p50'], s['file'],
                                             shown=lambda v: fmt_num(_num(v), 3))
                                 for k in sorted(doc.get('slack_floor') or {})}
        for name in _s2_order(doc):
            fam = (doc['networks'][name] or {}).get('family')
            row = {'name': name, 'family': fam}
            for f, scale, nd in S2_FIELDS:
                row[f] = json_add(nums, f'{base}.{fam}.{f}', doc, ['networks', name, f], s['file'],
                                  shown=lambda v, sc=scale, n=nd: fmt_num(_num(v), n, sc, floor=sc == 100.0))
            if grid == 'relative':
                row['floor_check_ok'] = json_add(nums, f'{base}.{fam}.floor_check_ok', doc,
                                                 ['networks', name, 'floor_check', 'ok'], s['file'], shown=str)
            head['nets'].append(row)
        out.append(head)
    return out


def s3_panel_data(s3, src, nums):
    """Panel (d) of Table II-B (S3, cancellation and regression): per target (commit gate, V4Runtime commit path) the
    sequences, offers, accepted commits, violations of Eq. 9 (must be 0) and the fault-class coverage. The report must
    be the one the analysis judged H5 with, when it used one. Recorded as tab2b.s3.*."""
    used = (src['doc'].get('h5') or {}).get('s3') if src is not None else None
    if isinstance(used, dict) and used.get('sha256') and used['sha256'] != s3['sha256']:
        raise FigureError(f'{s3["path"]}: not the S3 report the analysis judged H5 with ({used.get("path")}, '
                          f'{used["sha256"][:12]})')
    doc = s3['doc']
    out = {'n_sequences': json_add(nums, 'tab2b.s3.n_sequences', doc, ['n_sequences'], s3['file'], shown=str),
           'pass': json_add(nums, 'tab2b.s3.pass', doc, ['pass'], s3['file'], shown=str), 'targets': []}
    for t in sorted(doc.get('targets') or {}):
        out['targets'].append({'target': t, **{f: json_add(nums, f'tab2b.s3.{t}.{f}', doc, ['targets', t, f],
                                                           s3['file'], shown=str) for f in S3_FIELDS}})
    return out


def table2b_data(src, stress, nums):
    """Everything Table II-B shows: (a) the log quantities (analysis), (b) S1, (c) S2 on both grids, (d) S3; a stress
    panel without its report is None."""
    return {'logs': logs_panel_data(src, nums),
            's1': None if stress.get('s1') is None else s1_panel_data(stress['s1'], nums),
            's2': s2_panel_data(stress.get('s2'), stress.get('s2_relative'), nums)
            if stress.get('s2') or stress.get('s2_relative') else None,
            's3': None if stress.get('s3') is None else s3_panel_data(stress['s3'], src, nums)}


def _logs_cell(kind, vals, scale, nd):
    f = lambda v: fmt_num(_num(v), nd, scale, floor=kind in T2B_RATE_KINDS)  # noqa: E731
    if kind == 'q':
        return f'{f(vals[0])} / {f(vals[1])}'
    if kind == 'above':
        return '--' if not vals[1] else f'{fmt_num(_num(vals[0]), 0)}/{fmt_num(_num(vals[1]), 0)}'
    if kind == 'bypass':
        return f'{fmt_num(_num(vals[0]), 0)} ({f(vals[1])})'
    return f(vals[0])


def _yes(v):
    return '--' if v is None else 'yes' if v is True else 'no' if v is False else str(v)


def table_2b(data, status, out):
    """Table II-B (table*, booktabs) as table2b.tex: (a) runtime overhead from the logs at kappa 1.0 and under GPU
    contention at kappa 2.0 (S4), (b) S1 CPU contention, (c) S2 near deadline on the registered grid and on the
    supplementary grid of Amendment A7 (labelled), (d) S3 cancellation and regression. Returns the file names."""
    logs, s1, s2, s3 = data['logs'], data['s1'], data['s2'], data['s3']
    k1 = sum(1 for _, k in T2B_CONDS if k == 1.0)
    head_a = [['', f'\\multicolumn{{{k1}}}{{c}}{{$\\kappa$ = 1.0 (Table I runs)}}',
               f'\\multicolumn{{{len(T2B_CONDS) - k1}}}{{c}}{{$\\kappa$ = 2.0 (GPU contention, S4)}}'],
              f'\\cmidrule(lr){{2-{k1 + 1}}}\\cmidrule(lr){{{k1 + 2}-{len(T2B_CONDS) + 1}}}',
              ['Quantity'] + [latex_escape(T2B_SHORT[a]) for a, _ in T2B_CONDS]]
    body_a = [[label] + [_logs_cell(kind, logs['cells'][_cond_name(a, k)][label], scale, nd) for a, k in T2B_CONDS]
              for label, kind, _, scale, nd in T2B_ROWS]
    panels = [{'title': '\\textbf{(a)} Runtime overhead from the run logs (per-run p50 / p99, median over runs)',
               'colspec': 'l' + 'c' * len(T2B_CONDS), 'header': head_a, 'body': body_a}]
    letters = iter('bcd')
    if s1 is not None:
        groups = (('Q-network call', 4), ('Shield + decision', 3), ('Lease', 3), ('Commit check', 3))
        cols, rules = 2, []
        for _, n in groups:
            rules.append(f'\\cmidrule(lr){{{cols}-{cols + n - 1}}}')
            cols += n
        head_b = [['Busy'] + [f'\\multicolumn{{{n}}}{{c}}{{{g} ($\\mu$s)}}' for g, n in groups], ''.join(rules),
                  ['proc.', 'p50', 'p99', 'max', '$> B_\\pi$ (\\%)'] + ['p50', 'p99', 'max'] * 3]
        body_b = []
        for r in s1['rows']:
            row = [fmt_num(_num(r['load']), 0)]
            for comp, nd in S1_COMPONENTS:
                row += [fmt_num(_num(r[(comp, st)]), nd) for st in S1_STATS]
                if comp == 'qnet_call':
                    row.append(fmt_num(_num(r[('qnet_call', 'overrun_rate')]), 2, 100.0, floor=True))
            body_b.append(row)
        panels.append({'title': f'\\textbf{{({next(letters)})}} S1, CPU contention: background busy processes on '
                                f'16 cores; network {latex_escape(NET_LABEL.get(s1["family"], s1["network"] or "--"))}',
                       'colspec': 'r' + 'c' * 13, 'header': head_b, 'body': body_b})
    if s2 is not None:
        head_c = [['Grid', 'Network', 'States', hdr('Admitted', '(\\%)'), hdr('Bound', '$\\ge D^*$'),
                   hdr('Bypass', '(\\%)'), hdr('Near', 'deadline (\\%)'), hdr('CPU', 'timing (\\%)'),
                   'Violations', hdr('Floor', 'check')]]
        body_c = []
        for g in s2:
            for i, n in enumerate(g['nets']):
                grid = ('Registered' if g['grid'] == 'registered' else 'Supplementary (A7)') if i == 0 else ''
                body_c.append([grid, latex_escape(NET_LABEL.get(n['family'], n['name'])),
                               fmt_num(_num(g['n_swept']), 0) if i == 0 else '']
                              + [fmt_num(_num(n[f]), nd, scale, floor=scale == 100.0) for f, scale, nd in S2_FIELDS]
                              + [_yes(n.get('floor_check_ok')) if g['grid'] == 'relative' else '--'])
        src_states = '/'.join(sorted({g['states'] or '--' for g in s2}))
        panels.append({'title': f'\\textbf{{({next(letters)})}} S2, near deadline: {latex_escape(src_states)} decision '
                                'states, slack swept in 10 ms steps',
                       'colspec': 'll' + 'c' * 8, 'header': head_c, 'body': body_c})
    if s3 is not None:
        head_d = [['Target', 'Sequences', 'Offers', hdr('Accepted', 'commits'), hdr('Eq. 9', 'violations'),
                   hdr('Fault-class', 'coverage')]]
        target = {'gate': 'Commit gate', 'runtime': 'V4Runtime commit path'}
        body_d = [[target.get(t['target'], latex_escape(t['target']))]
                  + [fmt_num(_num(t[f]), 0) for f in ('sequences', 'offers', 'accepted', 'violations_total')]
                  + [_yes(t['coverage_ok'])] for t in s3['targets']]
        panels.append({'title': f'\\textbf{{({next(letters)})}} S3, cancellation and regression: random event '
                                'sequences against the commit gate',
                       'colspec': 'l' + 'c' * 5, 'header': head_d, 'body': body_d})
    tex = booktabs_panels(panels, 'Runtime overhead and stress tests', 'tab:table2b', _table2b_notes(data), True,
                          status, part='B')
    _write_text(Path(out) / 'table2b.tex', tex)
    return ['table2b.tex']


def _table2b_notes(data):
    logs = data['logs']
    a = logs['audit']
    audit = ('no commit audit in the analysis' if a['runs_audited'] is None else
             f'{a["runs_audited"]} runs ({latex_escape(a["phases"] or "--")}), {a["accepted"]} accepted commits, '
             f'{_yes(a["commit_audit_violations"])} violating')
    notes = ['(a) Shield arms of Table I at $\\kappa$ = 1.0 (44 test routes) and the Fig. 3 runs at $\\kappa$ = 2.0 '
             '(subset E) as GPU contention (S4); per-run quantiles of the logged wall times, median over the runs of '
             f'the condition; $B_\\pi$ = 100 $\\mu$s. Commit audit (Eq. 9): {audit}; S3: '
             f'{_yes(a["s3_violations"])} violations; H5: {latex_escape(a["label"] or "--")}.']
    if logs['reasons']:
        notes.append('Commit-gate rejects by reason (all conditions of (a)): ' + '; '.join(
            f'{latex_escape(r)} {n}' for r, n in sorted(logs['reasons'].items())) + '.')
    if data['s1'] is not None:
        s1 = data['s1']
        notes.append('S1: Q-network call = featurize, forward and read (QUtility timed region); shield + decision = '
                     f'ShieldedHeuristicPolicy.decide with the network on {latex_escape(s1["states"] or "--")} '
                     f'decision states; lease and commit check on {latex_escape(s1["scenes"] or "--")} scenes.')
    else:
        notes.append('S1: no report.')
    if data['s2'] is not None:
        floors = next((g.get('floor_p50') for g in data['s2'] if g['grid'] == 'registered'), None) or {}
        notes.append('S2: registered grid $D^* = t + s$, $s \\in [-0.1, 0.6]$ s (Sec. 7.6); supplementary grid '
                     '$D^* = t + f(\\mathrm{state}) + \\delta$ relative to each state\'s Eq. 5 slack floor (Amendment '
                     'A7), reported in addition to the registered grid, never in its place. An admitted action whose '
                     'bound reaches $D^*$ is a violation (must be 0); bypass = near-deadline part + CPU-timing part.'
                     + (' Median slack floor: ' + '; '.join(f'$\\kappa$ {latex_escape(k)} {fmt_num(_num(v), 3)} s'
                                                            for k, v in floors.items()) + '.' if floors else ''))
    else:
        notes.append('S2: no report.')
    if data['s3'] is not None:
        notes.append(f'S3: {fmt_num(_num(data["s3"]["n_sequences"]), 0)} sequences per target with late, '
                     'out-of-order and cancelled completions, duplicate releases, older observations after a newer '
                     'commit and expired candidates; an independent oracle counts every Eq. 9 violation (must be 0).')
    else:
        notes.append('S3: no report.')
    notes.append('--: no value.')
    return notes


# ============================================================================================ training-route
# operating-point table (Secs. 4.2-4.8, 9.13; D1)

TRAIN_GRID = {'ref': 'references (untuned, Table I settings)', 'lease': 'lease operating point (FrameLease + '
              'Heuristic, d = 10)', 'event': 'Event-Triggered (theta, A_hb)', 'heur': 'heuristic depth d at L*',
              'age': 'Age-Only threshold A at d*'}
# (D1 column, decimals, scale, header lines)
TRAIN_COLUMNS = (('mean_ds_kept', 1, 1.0, ('DS', '(kept)')), ('ds', 1, 1.0, ('DS', '(valid)')),
                 ('rc', 1, 1.0, ('RC', '')), ('sr', 1, 100.0, ('SR', PCT)),
                 ('fallback_ratio', 1, 100.0, ('Fallback', PCT)),
                 ('dmr', 1, 100.0, ('DMR', PCT)), ('eir', 2, 100.0, ('EIR', PCT)),
                 ('r_cond', 1, 100.0, ('$R_\\mathrm{cond}$', PCT)), ('p_both', 1, 100.0, ('$P_\\mathrm{both}$', PCT)))
TRAIN_ARM = {'fixed_deep': 'Fixed Deep', 'fast_only': 'Fast Only', 'fl_heuristic': 'FL + Heuristic',
             'event_triggered': 'Event-Triggered', 'age_only': 'Age-Only'}


def _count(nums, key, doc, path, source):
    """Record the number of entries of the list at path (derivation) and return it."""
    v = _jget(doc, path)
    n = len(v) if isinstance(v, (list, dict)) else None
    return nums.add(key, n, source, '.'.join(str(k) for k in path), {'json_path': list(path)},
                    shown=None if n is None else str(n), derivation='number of entries')


def _json_text(v):
    return None if v is None else json.dumps(v, sort_keys=True)


def train_table_data(d1, nums):
    """Everything the training-route operating-point table shows (D1 summary, Sec. 4.8): per block in the order of
    the summary its grid, stage and route set, the kept / all routes and pending jobs, the dropped routes with their
    reasons and the set-up failure flags (candidate, failures, routes), and per candidate the D1 columns
    (TRAIN_COLUMNS: the selection statistic, then means over valid runs, pooled R_cond and P_both), the valid runs, the
    outcome counts and its selection mark (selected / survivor of the stage selection); the tuning freeze when the
    summary has one. Recorded as tabtrain.<block>.* (JSON entries as their JSON text, with a derivation)."""
    doc, f = d1['doc'], d1['file']
    out = {'blocks': [], 'freeze': None}
    as_text = 'the JSON text of the entry'

    def text(key, path):
        v = _json_text(_jget(doc, path))
        return nums.add(key, v, f, '.'.join(str(k) for k in path), {'json_path': list(path)}, shown=v,
                        derivation=as_text)
    for bi, b in enumerate(doc.get('blocks') or []):
        base, root = f'tabtrain.{b["block"]}', ['blocks', bi]
        sel = b.get('selection') or {}
        flags = []
        for fi, fl in enumerate(b.get('flags') or []):
            flags.append({'candidate': fl.get('candidate'),
                          'setup_failures': json_add(nums, f'{base}.flag{fi}.setup_failures', doc,
                                                     root + ['flags', fi, 'setup_failures'], f, shown=_yes),
                          'routes': text(f'{base}.flag{fi}.routes', root + ['flags', fi, 'routes']),
                          'route_ids': [str(r) for r in fl.get('routes') or []]})
        blk = {'block': b['block'], 'grid': b.get('grid'), 'stage': b.get('stage'), 'route_set': b.get('route_set'),
               'kept': _count(nums, f'{base}.kept_routes', doc, root + ['kept_routes'], f),
               'routes': _count(nums, f'{base}.routes', doc, root + ['routes'], f),
               'pending': json_add(nums, f'{base}.pending', doc, root + ['pending'], f, shown=str),
               'dropped': {str(r): why for r, why in sorted((b.get('dropped_routes') or {}).items())},
               'flags': flags, 'candidates': []}
        if blk['dropped']:
            text(f'{base}.dropped_routes', root + ['dropped_routes'])
        for ci, c in enumerate(b.get('candidates') or []):
            cbase, croot = f'{base}.{c["candidate"]}', root + ['candidates', ci]
            mark = 'selected' if sel.get('selected') == c['candidate'] else \
                'survivor' if c['candidate'] in (sel.get('survivors') or []) else ''
            row = {'candidate': c['candidate'], 'arm': c.get('arm'), 'tag': c.get('tag'), 'mark': mark,
                   'valid_runs': json_add(nums, f'{cbase}.valid_runs', doc, croot + ['valid_runs'], f, shown=str),
                   'n_kept': json_add(nums, f'{cbase}.n_kept', doc, croot + ['n_kept'], f, shown=str),
                   'outcomes': c.get('outcomes') if isinstance(c.get('outcomes'), dict) else {}}
            if c.get('outcomes') is not None:
                text(f'{cbase}.outcomes', croot + ['outcomes'])
            for col, nd, scale, _ in TRAIN_COLUMNS:
                row[col] = json_add(nums, f'{cbase}.{col}', doc, croot + [col], f,
                                    shown=lambda v, n=nd, s=scale: fmt_num(_num(v), n, s, floor=s == 100.0))
            blk['candidates'].append(row)
        out['blocks'].append(blk)
    fz = doc.get('tuning_freeze')
    if isinstance(fz, dict):
        out['freeze'] = {k: text(f'tabtrain.tuning_freeze.{k}', ['tuning_freeze', k])
                         for k in ('L_star', 'd_star', 'A_star', 'event_star', 'fl_risk', 'sha256') if k in fz}
    return out


def table_train(data, status, out):
    """The training-route operating-point table (table*, booktabs; supplement) as table_train.tex: every candidate of
    every Phase-1 block of the D1 summary with its training-route DS (the selection statistic over the kept routes,
    and over valid runs), RC, SR, fallback ratio, DMR, EIR, pooled closed-loop R_cond and P_both, so that the DS-risk
    position of the selected lease point is disclosed (Sec. 9.13); the notes list the outcomes other than ok, the
    dropped routes and the set-up failure flags (Sec. 4.8). Returns the file names."""
    ncol = 4 + len(TRAIN_COLUMNS)
    header = [['Candidate', 'Arm', hdr('Valid', 'runs'), hdr('Kept', 'routes')]
              + [hdr(*h) if h[1] else h[0] for _, _, _, h in TRAIN_COLUMNS]]
    body = []
    for i, b in enumerate(data['blocks']):
        if i:
            body.append('\\midrule')
        what = TRAIN_GRID.get(b['grid'], b['grid'] or '')
        body.append(f'\\multicolumn{{{ncol}}}{{@{{}}l}}{{\\textit{{{latex_escape(b["block"])}: '
                    f'{latex_escape(what)}, stage {b["stage"]}, {latex_escape(b["route_set"] or "")}; '
                    f'{_yes(b["kept"])}/{_yes(b["routes"])} routes kept, {_yes(b["pending"])} jobs pending'
                    + (f', {len(b["flags"])} set-up flags' if b['flags'] else '') + '}} \\\\')
        for c in b['candidates']:
            mark = {'selected': '$^\\ast$', 'survivor': '$^+$'}.get(c['mark'], '')
            body.append([latex_escape(c['tag'] or c['candidate']) + mark,
                         latex_escape(TRAIN_ARM.get(c['arm'], c['arm'] or '')), _yes(c['valid_runs']),
                         _yes(c['n_kept'])]
                        + [fmt_num(_num(c[col]), nd, scale, floor=scale == 100.0)
                           for col, nd, scale, _ in TRAIN_COLUMNS])
    notes = ['Training routes only (T22 = T22a + T22b; no test route). DS (kept): the selection statistic, mean DS '
             'over the routes the stage kept (an agent crash counts 0); the other columns are means over the valid '
             'runs, $R_\\mathrm{cond}$ pooled over runs (misses / conflict plans) and $P_\\mathrm{both}$ pooled over '
             'shield decision epochs. $^\\ast$ selected; $^+$ survivor of the stage selection. --: no value.']
    odd = [f'{latex_escape(b["block"])} {latex_escape(c["tag"] or c["candidate"])}: '
           + ', '.join(f'{latex_escape(k)} {v}' for k, v in sorted(c['outcomes'].items()) if k != 'ok')
           for b in data['blocks'] for c in b['candidates'] if any(k != 'ok' for k in c['outcomes'])]
    notes.append('Run outcomes other than ok: ' + ('; '.join(odd) if odd else 'none') + '.')
    why = lambda w: latex_escape('; '.join(map(str, w)) if isinstance(w, list) else w)  # noqa: E731
    dropped = [f'{latex_escape(b["block"])} route {latex_escape(r)} ({why(w)})'
               for b in data['blocks'] for r, w in b['dropped'].items()]
    notes.append('Dropped routes: ' + ('; '.join(dropped) if dropped else 'none') + '.')
    flags = [f'{latex_escape(b["block"])} {latex_escape(fl["candidate"] or "--")}: {_yes(fl["setup_failures"])} set-up '
             f'failures (routes {latex_escape(", ".join(fl["route_ids"]) or "--")})'
             for b in data['blocks'] for fl in b['flags']]
    notes.append('Set-up failure flags (the registered rule still drops those routes for every candidate): '
                 + ('; '.join(flags) if flags else 'none') + '.')
    if data['freeze']:
        notes.append('Tuning freeze: ' + '; '.join(f'{latex_escape(k)} {latex_escape(v)}'
                                                   for k, v in data['freeze'].items()) + '.')
    tex = booktabs_panels([{'title': None, 'colspec': 'llcc' + 'c' * len(TRAIN_COLUMNS), 'header': header,
                            'body': body}], 'Training-route operating points of the tuned arms and the references',
                          'tab:train_operating_points', notes, True, status)
    _write_text(Path(out) / 'table_train.tex', tex)
    return ['table_train.tex']


# ============================================================================================ outputs and CLI

FIGURES = {
    'fig1': 'Fig. 1 (Sec. 7.1): (a) execution error vs. observation age, (b) Fast@Fresh - Deep@Old vs. kappa, (c) '
            'Fixed Deep - Fast Only DS by ability, this work and v2',
    'fig1_scenarios': 'companion of Fig. 1(c): Fixed Deep - Fast Only DS per scenario type, this work and v2',
    'fig3': 'Fig. 3 (Sec. 7.3): DS vs. action age p50 / p95 on E at kappa 1.0, 1.5, 2.0 with EIR / GPU usage',
    'table1': 'Table I (Sec. 7.2): end-to-end performance of the 7 arms, 44 test routes, kappa 1.0, with the H1 notes',
    'table2a': 'Table II-A (Secs. 7.4, 7.5): offline lease ablation with the cited RA rows, Proposition-1 envelope '
               'coverage, closed-loop lease panel and RL panel with the FQE estimates and P_both',
    'table2b': 'Table II-B (Sec. 7.6): runtime overhead from the logs (kappa 1.0; kappa 2.0 = S4) and the stress tests '
               'S1, S2 (registered grid and the supplementary grid of Amendment A7) and S3',
    'table_train': 'training-route operating points of the tuned arms and the references (D1 summary, Sec. 4.8)',
}
TABLES = ('table1', 'table2a', 'table2b', 'table_train')
FIGURE_SOURCES = {'fig1': ('offline', 'analysis'), 'fig1_scenarios': ('offline', 'analysis'), 'fig3': ('analysis',),
                  'table1': ('analysis',), 'table2a': ('analysis', 'offline', 'rnd', 'coverage', 'rl_freeze'),
                  'table2b': ('analysis', 's1', 's2', 's2_relative', 's3'), 'table_train': ('d1',)}
FIGURE_KEYS = {'fig1': ('fig1.a.', 'fig1.b.', 'fig1.c.'), 'fig1_scenarios': ('fig1.d.',), 'fig3': ('fig3.',),
               'table1': ('tab1.',), 'table2a': ('tab2a.',), 'table2b': ('tab2b.',), 'table_train': ('tabtrain.',)}
NEEDS_ANALYSIS = ('fig3', 'table1', 'table2a', 'table2b')
# the optional sources of the tables: {kind: (CLI option, loader)}; a missing one leaves its panel out (development)
SOURCE_OPTIONS = {'coverage': '--coverage', 'rl_freeze': '--rl-freeze', 's1': '--s1', 's2': '--s2',
                  's2_relative': '--s2-relative', 's3': '--s3', 'd1': '--d1'}
NO_ANALYSIS = 'no analysis given (--analysis): the closed-loop series of this work are absent'


def default_items(sources=None):
    """The items of a run without --only: every item, the training-route table only with a D1 summary (--d1)."""
    return [f for f in FIGURES if f != 'table_train' or (sources or {}).get('d1')]


def load_source(kind, path):
    """One optional source by kind (SOURCE_OPTIONS)."""
    if kind == 'coverage':
        return load_coverage(path)
    if kind == 'rl_freeze':
        return load_rl_freeze(path)
    if kind == 'd1':
        return load_d1(path)
    return load_stress(path, kind)


def check_out_dir(out, inputs=()):
    """PermissionError for an output directory inside the code tree, another phase's directories or the offline
    inputs (PROTECTED), and for an input directory itself (its SHA256SUMS is never touched)."""
    res = Path(out).resolve()
    rel = PJ.rel(res)
    if not Path(rel).is_absolute() and (
            rel in ('.', 'outputs', 'outputs/framelease_v4') or rel in PROTECTED
            or any(rel.startswith(p + '/') for p in PROTECTED) or rel.startswith(PROTECTED_PREFIXES)):
        raise PermissionError(f'{rel}: figures_tables never writes there (PROTECTED)')
    for d in inputs:
        if d is not None and res == Path(d).resolve():
            raise PermissionError(f'{rel}: an input directory; figures_tables writes into its own directory')


def output_names(figures, layout='double'):
    """The files a run writes: per figure its pdf, png and caption (<stem>_caption.tex), per table its tex, plus
    OUTPUT_META."""
    names = []
    for f in figures:
        stem = 'fig3_single' if f == 'fig3' and layout == 'single' else f
        names += [f'{f}.tex'] if f in TABLES else [f'{stem}.pdf', f'{stem}.png', f'{stem}_caption.tex']
    return names + list(OUTPUT_META)


def _write_text(path, text):
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    tmp.replace(path)


def build(figures, analysis=None, offline=None, require_registered=False, registered=None, layout='double',
          sources=None):
    """Everything a run shows, before anything is written: {'status', 'development', 'scope', 'nums', 'data',
    'analysis', 'sources'}. analysis: an analyze_v4.py output directory (None: only the offline, v2 and training
    parts); offline: the offline ablation directory (default the registered one); sources: {kind: path} of the
    optional sources of SOURCE_OPTIONS (and 'rnd', default the registered RND report). The status is 'registered'
    only when every source an item uses is registered (the analysis, the offline outputs at their registered location,
    and every optional source); a missing optional source leaves its panel out and makes the run development.
    GuardRefused (Sec. 9.11, --require-registered), FigureError (inconsistent inputs)."""
    unknown = sorted(set(figures) - set(FIGURES))
    if unknown or not figures:
        raise FigureError(f'unknown or no figures {unknown or figures}; known: {sorted(FIGURES)}')
    sources = {k: v for k, v in (sources or {}).items() if v is not None}
    needed = {k for f in figures for k in FIGURE_SOURCES[f]}
    nums = Numbers()
    src, scope, dev = None, None, []
    if analysis is not None:
        src = load_analysis(analysis)
        _, adev, scope = analysis_permission(src, registered=registered, require_registered=require_registered)
        nums.source(src['dir'] / 'analysis.json')
        nums.source(src['dir'] / 'cells.csv')
        if 'analysis' in needed:
            dev += adev
    elif require_registered and 'analysis' in needed:
        raise GuardRefused(f'{NO_ANALYSIS}; --require-registered accepts only the registered analysis')
    elif 'analysis' in needed:
        dev.append(NO_ANALYSIS)
    for f in NEEDS_ANALYSIS:
        if f in figures and src is None:
            raise FigureError(f'{f}: {NO_ANALYSIS}')
    if 'table_train' in figures and not sources.get('d1'):
        raise FigureError('table_train: no D1 summary given (--d1)')
    if 'offline' in needed:
        dev += offline_development(offline, figures)
    loaded = {}
    for kind in SOURCE_OPTIONS:
        if kind not in needed:
            continue
        if sources.get(kind):
            loaded[kind] = load_source(kind, sources[kind])
            dev += loaded[kind]['development']
        else:
            dev.append(f'no {SOURCE_OPTIONS[kind]} given: its panel is absent')
    source_permission(loaded, scope, registered=registered)
    if 'table2a' in figures:
        dev += rl_link(src, loaded.get('rl_freeze'))
    if require_registered and dev:
        more = f' (+{len(dev) - 2} more)' if len(dev) > 2 else ''
        raise GuardRefused('--require-registered accepts only registered sources: ' + '; '.join(dev[:2]) + more)
    data = {}
    if {'fig1', 'fig1_scenarios'} & set(figures):
        data['fig1'] = fig1_data(src, load_offline(offline, nums), nums)
    if 'fig3' in figures:
        data['fig3'] = {'points': fig3_points(src, nums), 'f3': family_rows(src, nums, 'F3', 'fig3.f3')}
    if 'table1' in figures:
        data['table1'] = table1_data(src, nums)
    if 'table2a' in figures:
        rnd = load_rnd(sources.get('rnd'))
        data['table2a'] = table2a_data(src, offline, rnd, loaded.get('coverage'), loaded.get('rl_freeze'), nums)
    if 'table2b' in figures:
        data['table2b'] = table2b_data(src, {k: loaded.get(k) for k in STRESS_SLOTS}, nums)
    if 'table_train' in figures:
        data['table_train'] = train_table_data(loaded['d1'], nums)
    paths = {k: v['path'] for k, v in loaded.items()}
    return {'status': DEVELOPMENT if dev else REGISTERED, 'development': dev, 'scope': scope, 'nums': nums,
            'data': data, 'analysis': None if src is None else src['path'], 'sources': paths}


def render(built, figures, out, layout='double'):
    """The figures (with their captions) and tables of a build under out; {item: [file names]}."""
    out = Path(out)
    files = {}
    stem3 = 'fig3_single' if layout == 'single' else 'fig3'
    draw = {'fig1': lambda d, s: figure_1(d['fig1'], s, out)
            + [write_caption(out, 'fig1', 'fig1', fig1_caption(d['fig1']), s)],
            'fig1_scenarios': lambda d, s: figure_1_scenarios(d['fig1'], s, out)
            + [write_caption(out, 'fig1_scenarios', 'fig1_scenarios', fig1_scenarios_caption(d['fig1']), s)],
            'fig3': lambda d, s: figure_3(d['fig3']['points'], s, out, layout=layout)
            + [write_caption(out, stem3, 'fig3', fig3_caption(d['fig3']['points'], d['fig3']['f3']), s)],
            'table1': lambda d, s: table_1(d['table1'], s, out), 'table2a': lambda d, s: table_2a(d['table2a'], s, out),
            'table2b': lambda d, s: table_2b(d['table2b'], s, out),
            'table_train': lambda d, s: table_train(d['table_train'], s, out)}
    for f in figures:
        files[f] = draw[f](built['data'], built['status'])
    return files


def write_meta(out, built, files, argv):
    """numbers.json, figures.json and SHA256SUMS (every figure file and both JSON files) under out; returns
    figures.json as written. Byte-deterministic for equal inputs (no time stamp)."""
    out = Path(out)
    ndoc = built['nums'].doc(built['status'], built['development'])
    _write_text(out / 'numbers.json', json.dumps(ndoc, indent=1, sort_keys=True) + '\n')
    doc = {'schema': SCHEMA, 'script': THIS_REL, 'script_sha256': PJ.sha256_file(Path(__file__)),
           'arguments': list(argv), 'status': built['status'], 'development': built['development'],
           'analysis': built['analysis'], 'sources': built.get('sources') or {}, 'scope': built['scope'],
           'rule': 'PROTOCOL Sec. 9.11; figures and tables only from analysis outputs whose status allows it',
           'figures': {f: {'description': FIGURES[f], 'files': files[f], 'sources': list(FIGURE_SOURCES[f]),
                           'numbers': sum(1 for k in ndoc['numbers'] if k.startswith(FIGURE_KEYS[f]))}
                       for f in files},
           'inputs': ndoc['sources'],
           'outputs': {n: PJ.sha256_file(out / n) for fs in files.values() for n in fs} | {
               'numbers.json': PJ.sha256_file(out / 'numbers.json')}}
    _write_text(out / 'figures.json', json.dumps(doc, indent=1, sort_keys=True) + '\n')
    names = sorted([n for fs in files.values() for n in fs] + ['numbers.json', 'figures.json'])
    _write_text(out / 'SHA256SUMS', ''.join(f'{PJ.sha256_file(out / n)}  {n}\n' for n in names))
    return doc


def summary_lines(doc, out):
    lines = [f'figures_tables: {doc["status"]} -> {PJ.rel(Path(out))}']
    if doc['status'] != REGISTERED:
        lines.append(f'  development ({DEV_STAMP}): ' + '; '.join(doc['development']))
    for f, d in doc['figures'].items():
        lines.append(f'  {f}: {", ".join(d["files"])} ({d["numbers"]} numbers)')
    lines.append(f'  numbers.json, figures.json, SHA256SUMS; guard log {G.LOG_NAME}')
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description='Figures and tables of the v4 method paper (PROTOCOL Secs. 7.1-7.6; '
                                             'GAP_AUDIT R-6).')
    ap.add_argument('--out', required=True, help='output directory')
    ap.add_argument('--analysis', help='an analyze_v4.py output directory (analysis.json, SHA256SUMS, tables)')
    ap.add_argument('--offline', default=str(ROOT / OFFLINE_REL),
                    help='the offline ablation outputs (fig1/, nested.csv, nested_folds.csv, paired.csv)')
    ap.add_argument('--coverage', help='a prop1_coverage.py output directory (Table II-A panel b)')
    ap.add_argument('--rl-freeze', help='the RL freeze of p3_rl.py (Table II-A: FQE estimates, P_both label)')
    for opt, test in (('--s1', 'S1'), ('--s2', 'S2 (registered grid)'),
                      ('--s2-relative', 'S2 on the supplementary grid of Amendment A7'), ('--s3', 'S3')):
        ap.add_argument(opt, help=f'the {test} report of stress_bench.py (Table II-B)')
    ap.add_argument('--d1', help='the D1 training-route summary of d1_summary.py (training-route table)')
    ap.add_argument('--only', nargs='+', choices=sorted(FIGURES), default=None,
                    help='items to make (default: every item; table_train only with --d1)')
    ap.add_argument('--fig3-layout', choices=sorted(FIG3_SIZE_IN), default='double')
    ap.add_argument('--require-registered', action='store_true',
                    help='refuse anything but registered sources (the paper build)')
    ap.add_argument('--force', action='store_true', help='replace earlier outputs')
    a = ap.parse_args(argv)
    argv = list(sys.argv) if argv is None else ['figures_tables.py', *argv]
    out = Path(a.out)
    sources = {k: getattr(a, k) for k in SOURCE_OPTIONS}
    figures = list(dict.fromkeys(a.only if a.only else default_items(sources)))
    try:
        check_out_dir(out, inputs=(a.analysis, a.offline, a.coverage))
    except PermissionError as e:
        print(f'figures_tables: refused: {e}', file=sys.stderr)
        return 1
    log = out / G.LOG_NAME
    extra = {'analysis': a.analysis, 'offline': a.offline, 'sources': {k: v for k, v in sources.items() if v},
             'figures': figures, 'out': str(out), 'require_registered': a.require_registered}
    present = [n for n in output_names(figures, a.fig3_layout) if (out / n).exists()]
    if present and not a.force:
        G.log_request(log, 'figures_tables', 'refused', reason=f'outputs exist (no --force): {present}', argv=argv,
                      **extra)
        print(f'figures_tables: refused: {PJ.rel(out)} holds {present} (use --force)', file=sys.stderr)
        return 1
    try:
        built = build(figures, a.analysis, a.offline, a.require_registered, layout=a.fig3_layout, sources=sources)
    except GuardRefused as e:
        G.log_request(log, 'figures_tables', 'refused', reason=str(e), argv=argv, **extra)
        print(f'figures_tables: refused (PROTOCOL Sec. 9.11 / status): {e}', file=sys.stderr)
        return 4
    except (FigureError, OSError, ValueError, KeyError) as e:
        print(f'figures_tables: inconsistent inputs, nothing written: {e}', file=sys.stderr)
        return 2
    G.log_request(log, 'figures_tables', 'granted', argv=argv, freeze=(built['scope'] or {}).get('freeze'),
                  status=built['status'], **extra)
    out.mkdir(parents=True, exist_ok=True)
    doc = write_meta(out, built, render(built, figures, out, a.fig3_layout), argv)
    print('\n'.join(summary_lines(doc, out)))
    return 0


__all__ = ['SCHEMA', 'NUMBERS_SCHEMA', 'PALETTE', 'ARM_STYLE', 'FIGURES', 'TABLES', 'DEV_STAMP', 'FigureError',
           'GuardRefused', 'Numbers', 'load_analysis', 'analysis_table', 'analysis_permission', 'load_offline',
           'offline_development', 'load_rnd', 'load_coverage', 'load_rl_freeze', 'load_stress', 'load_d1',
           'source_permission', 'rl_link', 'rc_params', 'save_figure', 'fig1_data', 'figure_1', 'figure_1_scenarios',
           'fig3_points', 'figure_3', 'write_caption', 'fig1_caption', 'fig1_scenarios_caption', 'fig3_caption',
           'family_rows', 'fmt_contrasts', 'table1_data', 'table_1', 'rl_gain_data', 'table2a_data', 'table_2a',
           'table2b_data', 'table_2b', 'train_table_data', 'table_train', 'booktabs', 'booktabs_panels', 'build',
           'render', 'write_meta', 'check_out_dir', 'main']


if __name__ == '__main__':
    sys.exit(main())
