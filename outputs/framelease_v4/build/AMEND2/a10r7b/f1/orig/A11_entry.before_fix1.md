**Amendment A11, {{datetime}} (Beijing time): registration of the independent recomputation of the Table I columns
GPU usage, DMR, action age, fallback ratio, EIR and P_both and of the closed-loop R_cond, and the reporting rule of
finding F1 (Secs. 6.3, 7.2, 9.12, 9.13; no effect on any run, job file, selection or criterion).**
* Cause. Sec. 7.2 lists GPU usage, DMR, action age p50 and p95, fallback ratio, EIR and P_both as columns of Table I and
  puts the closed-loop R_cond in the table notes or the text; Sec. 9.13 puts every registered result in the paper or its
  supplement; Sec. 9.12 requires an independent recomputation of the Table I columns from the raw run directories before
  any number enters the paper. Amendment A10 registers `verify_independent.py`, which recomputes DS, SR, RC,
  collisions/km and infractions/km, and leaves the other columns to a second independent script registered by its own
  amendment before the analysis freeze (Amendment A10, deviation 9). This entry registers that script and its tests.
  Item R7B built it from the PROTOCOL text and the data formats, independently of the aggregator, the analysis and the
  implementation of these metrics (Sec. 9.12; `outputs/framelease_v4/build/R7B/`). The review returned GO_WITH_FIXES;
  must-fix M1-M5 and should-fix S1-S5 are applied. The review of the fixes returned GO_WITH_FIXES; its must-fix M1 (the
  cause of a difference) and M2 (the clearance interpolation of V) and should-fix S1-S4 are applied. The second review
  of the fixes returned GO; its should-fix S1 and S2 are not applied (Known limitations). The recomputation and the
  registered `realized.py` differ by the conventions F1 and F3 (findings below); `realized.py` keeps them, and this
  entry fixes the reporting rule of F1. From this entry on, a change of either file is an amendment.
* Change: the files, their roles and the PROTOCOL sections they implement.

  | file | role | PROTOCOL | review |
  |---|---|---|---|
  | `framelease_v4/analysis/verify_table1_extra.py` | the recomputation, per run from the raw logs, of GPU usage (and CUDA-seconds per second), DMR (from the first commit on; the all-ticks and expired-only variants), action age p50 and p95, the fallback ratio and episodes, P_both, EIR and the closed-loop R_cond (also without the V = 0 plans), and its comparison with the aggregator's `runs.csv` and `arm_summary.csv`, the runtime's `summary.json`, the runner's END-line results and the analysis outputs, each difference with its cause where a convention of the registered implementation explains it; the Sec. 9.11 guard | 5.1, 5.8, 6.2-6.4, 7.2, 9.11-9.13 | `build/R7B/review/REVIEW.md`: GO_WITH_FIXES, must-fix M1-M5 and should-fix S1-S5 applied; `build/R7B/rereview/REVIEW_round1.md`: GO_WITH_FIXES, must-fix M1, M2 and should-fix S1-S4 applied; `build/R7B/rereview/REVIEW.md`: GO, should-fix S1 and S2 not applied |
  | `framelease_v4/analysis/tests/test_verify_table1_extra.py` | known answers on synthetic run directories, the run-level and analysis-level comparisons, the causes of differences, the Sec. 6.3 definitions, the actor-log decoder, the guard, the imports, and the P1-0 smoke runs against their `summary.json` | as above | as above |

* What it computes (its docstring fixes every definition; the route is the unit, arm-level values are means over
  routes).
  * Inputs: the runner's `status.jsonl` (the last final 'end' record of a job names its run directory) and, in each run
    directory, `config.json`, `raw/agent/framelease/{ticks,jobs,events,decisions}.jsonl`, `summary.json` where present,
    the actor-box log `raw/agent/framelease/actors.jsonl.gz` and the lease parameter file that the config names.
  * GPU usage: the union of the cost-model intervals of prefixes and flow steps (`jobs.jsonl`; for a job still running
    at the end, its `job_start` event and the step quanta in the ticks) over the span of the ticks.
  * DMR: the ticks from the first commit on whose committed action, rebuilt from the accepted commit events, is not
    valid by the arm's rule (before the deadline for the lease arms; below the age cap for Fixed Deep, Fast Only and
    Event-Triggered), over those ticks. Fallback ratio: the ticks in mode 'fallback' over all ticks. Action age: the
    tick time minus the capture time of the committed action over the tracked ticks, p50 and p95 by linear
    interpolation. P_both: the decision rows at depth >= 1 with the shield evaluated and two feasible actions, over
    those rows.
  * EIR and the closed-loop R_cond (Sec. 6.3, standard validity): every accepted commit is a committed plan, placed
    with the true capture pose of the actor-box log; the ego footprint is the lease footprint of Eqs. 1-3 (headings by
    central differences, the ego box of the lease parameter file); the actor boxes are those of the log at t_k + tau.
    V is the first time at which the footprint comes within d_safe = 0.5 m of an actor box (the first conflicting
    sample of the 0.05 s grid brackets it; bisection refines it to 1e-4 s) and V_suf = clip(V - T_c, 0, H_bar). A
    conflict plan is a miss when H > V_suf; EIR counts the tracked ticks whose committed plan is a conflict plan at an
    age of at least V_suf. Plans that cannot be evaluated and the bisection resolution of V (a band of 1e-3 s around
    the miss rule) give bounds.
  * Causes of differences. The script also forms the Sec. 6.3 values under the conventions F1 and F3 of the registered
    implementation (findings below; F1, F3 and both, F1+F3), from the same plans and with bounds formed in the same
    way. A difference whose other side agrees with one of them carries that convention as its cause (`differences.csv`
    'cause', the first of F1, F3, F1+F3) and remains a difference; `table1_extra.json` counts the differences by
    cause, and `cause_plans.csv` lists every plan a convention changes (run directory, job, depth, sample, sample
    time, time of the last actor-log row, capture time, V, V_lin, H, the outcomes on both sides).
  * Not recomputed: the CIs and p-values of the contrasts of these metrics (the S-dmr family and the secondary rows;
    their per-route values and means are compared), the ability membership of the per-ability rows, and the
    closed-loop lease utilization and premature expiry (Sec. 6.3; not columns of Table I).
* Independence. Standard library, `zlib` and numpy only. It imports nothing of `framelease_v4/analysis`,
  `framelease_v4/arms/metrics_v4.py`, `realized.py`, `actor_log.py` or `framelease_v2` and uses no code of them: the
  definitions follow the PROTOCOL text and the documented conventions of the lease footprint, its own RFC 1952 decoder
  reads the gzip members of the actor-box log, and only data formats are taken from elsewhere. The block comparison of
  the review (`build/R7B/review/scripts/blocks.py`) finds no shared block of four or more lines with these files other
  than import lists; must-fix M3 removed the one copied block. The second review of the fixes repeats the comparison
  on the registered version with the same result; the conventions F1 and F3 emulate the registered behaviour and reuse
  no code.
* Tolerances (in the docstring: stated before the first comparison of each part; the time resolution of V with must-fix
  M1). Counts are compared exactly; fractions, ratios and times at 1e-6 absolute (the mean episode count at 1e-9). A
  value with bounds (the in-flight step quanta of a job still running at the end; Sec. 6.3: the unevaluable plans and
  the plans with |H - V_suf| < 1e-3 s, a band that covers the bisection resolution of V only) agrees when the other
  side lies within the bounds widened by the tolerance; these agreements are counted by kind. A difference below the
  registered grid (1e-4 for fractions, 1 ms for ages) is flagged 'below_grid' and remains a difference. An expected
  column, field or file that is absent is a difference. Every comparison has a scope: 'analysis' for a value the
  analysis reads for a column of Table I, 'record' for every other value; the verdict counts every difference.
* Interim looks (Sec. 9.11). Before any log is read, every input that names a route is classified with the registered
  route split (runner records, `runs.csv` rows, run directories, the jobs of `cells.csv` and every route list of the
  analysis outputs; a route id in any integral form, such as '1711.0' or '+1711', is that integer); an input whose route
  is unknown counts as a registered test route. A test route is released only by a valid analysis-freeze record that
  covers the input (its sha256 cited in Sec. 13, PROTOCOL.md equal to its seal, the recorded route split and analysis
  code on disk); otherwise the run is refused (exit 4) and only `guard_log.jsonl` is written. Under the registered
  record (status 'final') every run directory is recomputed: the development option `--runs-csv-values` is refused
  there. The test options `--route-split`, `--protocol` and `--seal` apply to synthetic test routes only.
* Development data (Secs. 9.11, 9.12; `build/` stands for `outputs/framelease_v4/build/`). No test-route run existed or
  was read. The values were used to check the code and to find the conventions F1 and F3 of the registered
  implementation, never to choose a definition or a tolerance; the reporting rule of F1 was fixed with its P1 size
  known (development comparison below). Synthetic run directories with known answers (the tests); with
  `--runs-csv-values`, the synthetic analysis outputs `build/R7/dev/syn_r4/`, `build/R7/dev/syn_varied/` and
  `build/R6/dev_inputs/`; the 14 P1-0 smoke run directories of training route 18305 (the tests); and the P1
  training-route run directories named by two copies of the `queue_p1` runner records (`build/R7/dev/p1_snapshot/`,
  made on 2026-11-14 at 11:46; `build/R7B/dev/p1_snap_2203/`, made on 2026-11-14 at 22:03), compared with the
  development aggregations `build/R7/dev/agg_p1/`, `build/R7B/dev/agg_now/` and `build/R7B/dev/agg_snap_2203/`
  (Amendment A10, deviation 1), from 2026-11-14 14:39 to 2026-11-15 13:22, into `build/R7B/dev/verify_p1*/` and
  scratch directories under /tmp (`build/R7B/PROGRESS.md`). The review of item R7B ran the reviewed version (with
  injected `runs.csv` values and guard probes), monkeypatched variants of it and a plan-by-plan comparison with
  `realized.py` on the 180 run directories of `build/R7B/dev/p1_snap_2203/`, from 2026-11-14 23:22 to 2026-11-15
  00:20, into /tmp/review_R7B/ and `build/R7B/review/logs/` (`build/R7B/review/PROGRESS.md`). The review of the fixes
  ran the version under review on the P1 runs of `build/R7B/dev/p1_snap_2203/` against `build/R7B/dev/agg_snap_2203/`
  (2026-11-15 12:02-12:04) and on the 272 P1 run directories under `outputs/framelease_v4/tuning/` (12:17-12:19), its
  decoder on the 180 actor logs of that snapshot (12:17), its own scripts on these run directories (12:05-12:23) and
  `realized.py` on the run directory of route 2086 in stage lease_s2 (12:13), into /tmp/A10A11/r7b/
  (`build/R7B/rereview/PROGRESS.md`). Item R7B ran its fixed version on the same snapshot (2026-11-15 13:06-13:08 and
  13:17-13:19, into `build/R7B/dev/verify_p1_snap_2203_d/`) and on the 272 run directories (13:09-13:11 and
  13:19-13:21, into /tmp/A10A11/r7bfix/), and its development scripts `check_vlin.py` and `reconcile_p1.py` on these
  outputs (13:11-13:12 and 13:21, into `build/R7B/dev/`) (`build/R7B/PROGRESS.md`). The second review of the fixes
  ran the registered version on the P1 runs of `build/R7B/dev/p1_snap_2203/` against `build/R7B/dev/agg_snap_2203/`
  (2026-11-15 13:36-13:38) and on the 272 P1 run directories under `outputs/framelease_v4/tuning/` (13:39-13:41), with
  `--runs-csv-values` on the synthetic analysis outputs (13:57), and its own scripts and `realized.py` on these run
  directories (13:38-13:47 and 14:01), into /tmp/A10A11/r7b/round2/ (`build/R7B/rereview/PROGRESS.md`). Class F1 of
  the development comparison and the capture-time offsets were read from the outputs of the snapshot and of the 272
  run directories (2026-11-15 14:06-14:13, `f1_class_report.py`, into `build/AMEND2/a10r7b/f1/`). The definitions
  and tolerances were fixed in the docstring before the first comparison; the corrections of must-fix M1 and M2 of
  the review (the continuous V, the lease footprint) follow the text of Sec. 6.3, and the fixes of the review of the
  fixes change no value of the script (`build/R7B/rereview/REVIEW.md`).
* Development comparison of the registered version (2026-11-15, `build/R7B/dev/verify_p1_snap_2203_d/`). On the P1
  runs of `build/R7B/dev/p1_snap_2203/` against `build/R7B/dev/agg_snap_2203/` (the aggregator of Amendment A3): 180
  run directories recomputed, 179 `runs.csv` rows with analysis_use, 12,259 comparisons, 136 differences, 1 of them in
  a value the analysis reads. Every Sec. 6.3 difference other than the empty cells of an unused run carries cause F1:
  26 values (the Sec. 6.3 counts of 19 runs and the `fast_only` EIR mean of `arm_summary.csv`), among them the one
  value the analysis reads (`fast_only`, route 1792: EIR 94/412 = 0.2282 recomputed, 85/412 = 0.2063 in `runs.csv`).
  The 110 differences without a cause: the cross-check columns `gpu_usage_recomputed` and `gpu_busy_recomputed_s` and
  the commit count of `runs.csv` omit the work of a job still running at the end of a run (the `gpu_usage` that the
  analysis reads agrees within the in-flight bounds), and the timed-out run of job
  `v4p1_fl_heuristic_B0_d10_k1.0_s11_r23659` (not used; no `summary.json`) has empty cells there. Two runs agree only
  within the Sec. 6.3 bounds: route 24211 (EIR, finding F2) and route 2086 (EIR, finding F2; its misses, R_cond and
  R_cond without V = 0 equal the values under F3: plan 240:2, V 2.86375 s by the first crossing, 2.86985 s by the
  clearance interpolation, H 2.36612 s). `summary.json`: 3,759 comparisons, 0 differences. On all 272 P1 run
  directories under `outputs/framelease_v4/tuning/`: `summary.json` 5,523 comparisons, 0 differences; F1 changes 47
  plans in 26 run directories and F3 2 plans in 2. On the synthetic analysis outputs (`--runs-csv-values`;
  `build/R7B/dev/syn_r4_d/`, `r6_dev_inputs_d/`, `syn_varied_d/`): AGREE with 25,746, 25,746 and 20,242 comparisons.
  Class F1 of this comparison (reporting rule below; `build/AMEND2/a10r7b/f1/f1_class_dev.json`): 26 differences, 1
  of them in scope 'analysis'; runs per arm `event_triggered` 6, `fast_only` 5, `fixed_deep` 4, `fl_heuristic` 4 (19
  of the 180 runs, all with analysis_use); largest absolute difference per column: in `runs.csv`
  realized_log_censored_plans 10, realized_invalid_ticks 9, realized_conflict_plans 1, realized_misses 1 and
  realized_invalid_tick_ratio 0.0218 (`fast_only`, route 1792, the value the analysis reads), in `arm_summary.csv`
  realized_invalid_tick_ratio 0.0010.
* Findings about registered files (Sec. 6.3), carried to the analysis freeze; this entry changes no registered file.
  * F1. `framelease_v4/arms/actor_log.py` places a row of the actor-box log at its frame time, a multiple of 0.05 s,
    and `realized.py` (through `GTTrack._bracket` of `framelease_v2/geometry.py`) treats a time above the last row by
    more than 1e-9 s as outside the log, while the plan sample times `capture_s + tau` lie above the 0.05 s grid by the
    runtime's clock offset (a drift of 1.49e-8 s per s: up to 3.0e-6 s in 200 s; 1.4e-7 to 2.0e-6 s at the plans that
    F1 changes on P1): a sample that lands on the last row has no actors, so a conflict first found there is lost and
    a clear plan whose horizon ends at that row counts as log-censored. On the P1 runs above this changes the Sec. 6.3
    counts of 19 of the 180 runs (38 plans clear here and log-censored there; 2 conflict plans here, both misses,
    log-censored there) and one EIR value the analysis reads; 26 of the 271 recomputed P1 run directories carry such a
    plan (47 plans).
  * F2. `realized.py` places a plan only through the actor-log row of its capture step: a plan without that row (a
    decimated log) and the commits of a job still running at the end leave the counts and, with their tracked ticks,
    the EIR denominator, which Sec. 6.3 forms from all tracked ticks. The recomputation bounds the commits of a job
    still running at the end (no logged plan: unevaluable); it takes the capture pose of a plan without its row between
    the bracketing rows and evaluates the plan, so a decimated log gives differences without a cause. No P1 log was
    decimated: the largest of the 271 logs holds 425 kB, and decimation starts at half of the 2,000,000-byte budget.
  * F3. `realized.py` takes V by linear interpolation of the clearance between the grid samples j - 1 and j
    (`framelease_v2/c2_eval.py`, `observed_validity`; `geometry.py`, `first_crossing_time`): V = tau_{j-1} +
    0.05 c_{j-1} / (c_{j-1} - c_j), with c the least box distance minus d_safe over the vehicles and walkers whose
    centre-distance lower bound is at most d_safe + 5 m, and V = tau_j without such an actor at sample j - 1, where
    Sec. 6.3 defines V as the first time the footprint comes within d_safe. On the 271 recomputed P1 run directories
    the two differ by up to 31.7 ms, by more than 1 ms for 914 of the 7,078 conflict plans whose first conflicting
    sample lies after tau 0, and decide the miss of 2 plans differently (route 2086 plan 240:2, outside the 1e-3 s
    band; one more within it). The cause F3 of the recomputation omits the candidate radius d_safe + 5 m (Known
    limitations).
  * Gaps inside a log. A plan whose first unknown sample lies before the end of the log (rows more than 0.2 s apart,
    or rows without actors) is log-censored in the recomputation; `realized.py` interpolates across gaps up to 0.25 s,
    treats a row without actors as a row without conflict and counts a plan as log-censored only when its horizon
    passes the end of the log. Such a plan gives a difference without a cause. No P1 log has such a gap or row: the
    rows of all 271 logs lie 0.05 s apart, and every row lists at least one actor.
  The recomputation reports every value that F1 or F3 changes as a difference with that cause (`differences.csv`
  'cause'); class F1 follows the reporting rule below, and any other difference is a verification failure (use
  rule 2).
* Reporting rule for finding F1 (fixed by this entry). `framelease_v4/arms/realized.py` stays as registered: F1 is not
  corrected. The registered values, those of the aggregator and the analysis through `realized.py`, are the values of
  Tables I and II and of the paper; the recomputation changes none of them. The run of use rule 1 reports every
  difference whose cause in `differences.csv` is 'F1' as one class, class F1, with that cause: the number of its
  differences, all and in scope 'analysis'; per arm, the number of runs with such a difference (the run directories
  of its `runs.csv`, `summary.json` and runner comparisons, the arm from `runs_recomputed.csv`); and per affected
  column (the target, metric and compared column of `differences.csv`) the largest absolute difference.
  `build/AMEND2/a10r7b/f1/f1_class_report.py` forms these numbers from the output directory of that run (sha256
  under Evidence). The paper states class F1, its cause and its size next to the verification result. A difference
  of any other cause, 'F3', 'F1+F3' or none, is a verification failure handled by the rules of Amendment A10 (use
  rule 4; Sec. 9.12).
* Known limitations accepted (should-fix S1 and S2 of the second review of the fixes, not applied; no P1 value
  depends on them). The cause F3 omits the candidate radius of the registered clearance (finding F3): when a vehicle
  or walker enters the log next to the footprint at the conflicting sample and every actor at sample j - 1 lies
  beyond the radius, `realized.py` gives V = tau_j and the recomputation V_lin up to 4.5 ms earlier, a difference
  without a cause. Four branches have no test of their own (F1 at sample 0, an actor entering the log at the
  conflicting sample, a test entry of a route split without a route id, the upper bound of the log-censored plans
  with unevaluable plans); the second review of the fixes found each right on synthetic cases or a guard probe.
* Use of the registered files (fixed by this entry).
  1. After the analysis freeze is entered and `analyze_v4.py` has written `final_<stamp>/analysis/` (Amendment A10, use
     rule 1), an independent session (Sec. 9.12) runs `verify_table1_extra.py` next to `verify_independent.py`
     (Amendment A10, use rule 4): with `--analysis-freeze` (the record, or the `final_<stamp>/` directory that holds
     it), one `--queue` for every queue whose job lines the aggregation covers, `--agg final_<stamp>/`,
     `--analysis final_<stamp>/analysis/` and `--out` a new directory such as
     `outputs/framelease_v4/verification/final_<stamp>_table1_extra/`; never with `--runs-csv-values` or a test option.
     Only a result with status 'final' in `table1_extra.json` counts.
  2. AGREE releases the Table I columns GPU usage, DMR, action age p50 and p95, fallback ratio, EIR and P_both and the
     closed-loop R_cond (table notes or text). On DIFFER with every difference in class F1, these columns are released
     with the registered values and class F1 is reported (reporting rule above). Any other difference is a
     verification failure: it is resolved and its cause entered in Sec. 13 before any of these numbers enters the
     paper (Amendment A10, use rule 4; Sec. 9.12).
  3. The sha256 of `table1_extra.json`, of the `SHA256SUMS` of that directory and of the class F1 report
     (`f1_class_report.py` on that directory), with the numbers of class F1, are entered in their own dated Sec. 13
     entry before the paper is written.
* In-place text. Sec. 9.12, "**Verification.**" (as Amendment A10 leaves it): "a second script, registered by its own
  amendment before the analysis freeze, recomputes the other Table I columns," becomes "Amendment A11:
  `framelease_v4/analysis/verify_table1_extra.py` recomputes GPU usage, DMR, action age p50 and p95, fallback ratio,
  EIR, P_both and the closed-loop R_cond,".
* Scope. No run, job file, pin, stage selection, freeze or criterion changes. No job line pins these files, no agent
  process imports them, and neither the aggregator nor the analysis imports them; the analysis-freeze record does not
  list them. The reporting rule of F1 changes no registered file and no registered value. This entry precedes the
  analysis freeze; the phase driver's gate G8 waits for Amendment A10 only.
* Files (sha256).

  | file | sha256 |
  |---|---|
  | `framelease_v4/analysis/verify_table1_extra.py` | `{{sha256:framelease_v4/analysis/verify_table1_extra.py}}` |
  | `framelease_v4/analysis/tests/test_verify_table1_extra.py` | `{{sha256:framelease_v4/analysis/tests/test_verify_table1_extra.py}}` |

* Evidence (outside the manifest; fixed by these sha256). Reviews: `outputs/framelease_v4/build/R7B/review/REVIEW.md`
  (`{{sha256:outputs/framelease_v4/build/R7B/review/REVIEW.md}}`), the reviews of the fixes
  `build/R7B/rereview/REVIEW_round1.md` (`{{sha256:outputs/framelease_v4/build/R7B/rereview/REVIEW_round1.md}}`) and
  `build/R7B/rereview/REVIEW.md` (`{{sha256:outputs/framelease_v4/build/R7B/rereview/REVIEW.md}}`); the review tests
  `build/R7B/review/test_review_r7b.py` (`{{sha256:outputs/framelease_v4/build/R7B/review/test_review_r7b.py}}`),
  `build/R7B/rereview/test_rereview_r7b.py`
  (`{{sha256:outputs/framelease_v4/build/R7B/rereview/test_rereview_r7b.py}}`) and
  `build/R7B/rereview/test_rereview_r7b_round2.py`
  (`{{sha256:outputs/framelease_v4/build/R7B/rereview/test_rereview_r7b_round2.py}}`). Development comparison:
  `build/R7B/dev/verify_p1_snap_2203_d/SHA256SUMS`
  (`{{sha256:outputs/framelease_v4/build/R7B/dev/verify_p1_snap_2203_d/SHA256SUMS}}`),
  `build/R7B/dev/reconcile_p1_d.json` (`{{sha256:outputs/framelease_v4/build/R7B/dev/reconcile_p1_d.json}}`),
  `build/R7B/dev/check_vlin_snap_2203.json`
  (`{{sha256:outputs/framelease_v4/build/R7B/dev/check_vlin_snap_2203.json}}`), `build/R7B/dev/check_vlin_p1.json`
  (`{{sha256:outputs/framelease_v4/build/R7B/dev/check_vlin_p1.json}}`), `build/R7B/dev/syn_r4_d/SHA256SUMS`
  (`{{sha256:outputs/framelease_v4/build/R7B/dev/syn_r4_d/SHA256SUMS}}`), `build/R7B/dev/r6_dev_inputs_d/SHA256SUMS`
  (`{{sha256:outputs/framelease_v4/build/R7B/dev/r6_dev_inputs_d/SHA256SUMS}}`),
  `build/R7B/dev/syn_varied_d/SHA256SUMS` (`{{sha256:outputs/framelease_v4/build/R7B/dev/syn_varied_d/SHA256SUMS}}`).
  Mutation test of the tests: `build/R7B/logs/mutate_round1.log`
  (`{{sha256:outputs/framelease_v4/build/R7B/logs/mutate_round1.log}}`; 138 of 138 mutants killed). Reporting rule
  of F1: `build/AMEND2/a10r7b/f1/f1_class_report.py`
  (`{{sha256:outputs/framelease_v4/build/AMEND2/a10r7b/f1/f1_class_report.py}}`), its tests
  `build/AMEND2/a10r7b/f1/test_f1_class_report.py`
  (`{{sha256:outputs/framelease_v4/build/AMEND2/a10r7b/f1/test_f1_class_report.py}}`; 7 passed), its output on the
  development comparison `build/AMEND2/a10r7b/f1/f1_class_dev.json`
  (`{{sha256:outputs/framelease_v4/build/AMEND2/a10r7b/f1/f1_class_dev.json}}`) and the rule with its evidence
  `build/AMEND2/a10r7b/f1/F1_RULE.md` (`{{sha256:outputs/framelease_v4/build/AMEND2/a10r7b/f1/F1_RULE.md}}`).
* Tests (CPU; logs in `outputs/framelease_v4/amendment_a11/`):
  * `tests/test_verify_table1_extra.py`: {{pytest:outputs/framelease_v4/amendment_a11/pytest_verify_table1_extra.log}}
    (`pytest_verify_table1_extra.log`, `{{sha256:outputs/framelease_v4/amendment_a11/pytest_verify_table1_extra.log}}`);
  * the review tests `build/R7B/review/test_review_r7b.py`:
    {{pytest:outputs/framelease_v4/amendment_a11/pytest_review_r7b.log}}
    (`pytest_review_r7b.log`, `{{sha256:outputs/framelease_v4/amendment_a11/pytest_review_r7b.log}}`).

  At drafting (2026-11-15): 87 passed and 80 subtests; 14 passed and 2 subtests
  (`outputs/framelease_v4/build/AMEND2/a10r7b/f1/logs/`). Besides synthetic run directories, the tests read the 14 P1-0
  smoke run directories of training route 18305 and the review tests three P1 training-route run directories and
  `build/R7B/dev/agg_snap_2203/runs.csv`, all read only.
* Manifest and seal after this amendment: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.
