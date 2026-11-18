# The reporting rule of Amendment A11 (findings F1 and F3, jobs in flight, jobs not ok) and its evidence

`build/` stands for `outputs/framelease_v4/build/`. The rule is fixed by Amendment A11
(`build/AMEND2/a10r7b/A11_entry.md`, bullets "Reporting rule for the differences" and "Use of the registered files",
rules 2 and 3); this file states it with its evidence. Data read: P1 training-route outputs only (no test route, no
P2 data).

## 1. The rule

1. `framelease_v4/arms/realized.py` stays as registered: F1 and F3 are not corrected, and `actor_log.py`,
   `framelease_v2/geometry.py`, `framelease_v2/c2_eval.py` and the aggregator (`aggregate_v4.py`, `metrics_v4.py`)
   stay as registered as well.
2. The registered values, those of the aggregator and the analysis (`analyze_v4.py`) through `realized.py`, are the
   values of Tables I and II and of the paper. The recomputation changes none of them.
3. The run of `verify_table1_extra.py` after the analysis freeze (A11 use rule 1) assigns every difference of its
   `differences.csv` to one of four classes. Each class is defined by its mechanism and fixed before any test-route
   data exist; `f1/f1_class_report.py` assigns the rows from the verifier's own output and, for the fourth class, from
   the runner records and the `runs.csv` that the verifier recorded with their sha256:
   * class F1: the cause 'F1' (Sec. 2.1);
   * class F3: the cause 'F3', or 'F1+F3' for a value that agrees only under both conventions, such as a route mean
     over one route with an F1 plan and one with an F3 plan (Sec. 2.2). The verifier gives a cause only when the other
     side agrees with the value under that convention at its tolerances or within the bounds formed under it;
   * class in-flight: a difference without a cause in the `runs.csv` cross-check columns `gpu_usage_recomputed`,
     `gpu_busy_recomputed_s` and `commits`, scope 'record', of a run that ended with a job still running (Sec. 2.3).
     Required for the two GPU columns: in-flight GPU boundaries in the run's `runs_recomputed.csv` row, the registered
     value below the lower bound of the recomputed one, and no difference in the same row's `runs.csv` columns
     `gpu_usage` (the value the analysis reads) and `gpu_busy_in_span_s` (the runtime's busy time, which includes the
     job in flight); for `commits`: in-flight GPU boundaries and the recomputed count minus the registered one equal
     to the commits of jobs without a `jobs.jsonl` row (`plans_by_status` 'no_plan_logged' less the check
     'commit_without_job_step'), at least 1. For the GPU columns the class tests the in-flight boundaries of the run
     and the direction of the difference, not its size against the omitted step quanta, which the verifier's outputs
     do not hold; the class report states the largest difference;
   * class not-ok record: a difference without a cause, scope 'record', target `runs.csv` or the runner's result
     fields, whose registered value is empty, of a job whose final runner outcome is a failure (present and not 'ok'
     or 'result_with_warnings', the OK outcomes of `framelease_v2/gpu_queue.py`: timeout, crash, simulator failure),
     whose `runs.csv` row carries an outcome other than 'ok' ('sim_failure', 'agent_crashed', 'pending': the condition
     under which `aggregate_v4.py` `job_row` records no metric) and analysis_use false (Sec. 2.4). The final runner
     outcome is that of the job's last final 'end' record of the runner records, else of its last 'end' record (the
     verifier's rule); the runner records and `runs.csv` are those that `table1_extra.json` 'inputs' names, each at the
     sha256 recorded there. A non-empty registered value in such a run, a row in scope 'analysis', a job without a
     runner record or `runs.csv` row, a runner outcome that is absent, 'ok' or 'result_with_warnings', a `runs.csv`
     outcome that is empty or 'ok' (a valid run whose metric step failed: missing_reason 'no_metrics'), or a row with
     analysis_use true stays outside the class.
4. Each class is reported with its cause: the number of its differences, all and in scope 'analysis'; per arm, the
   number of runs with such a difference (the run directories of its `runs.csv`, `summary.json` and runner
   comparisons, with the arm of `runs_recomputed.csv`), and of them those with a difference in scope 'analysis'; per
   affected column the largest absolute difference (`abs_diff`, else |ours - theirs|) and the number of its differences
   without one (a side empty or not a number; a column whose differences all have one side empty states their number
   and no largest difference). The column is the target, the metric (in an analysis output, the component of the key
   or the field that names a metric) and the compared column (`their_field`) of `differences.csv`.
   `f1/f1_class_report.py` forms these numbers after checking its four inputs against the `SHA256SUMS` of the
   verification directory; its sha256 is cited under "Evidence" of A11, so the computation is fixed with the entry.
5. AGREE releases the columns. On DIFFER with every difference in one of the four classes, the columns GPU usage,
   DMR, action age p50 and p95, fallback ratio, EIR, P_both and the closed-loop R_cond are released with the
   registered values, and each class is reported.
6. The paper states each class, its cause and its size (rule 4) next to the verification result.
7. A difference that no class explains, in particular one in a value the analysis reads, is a verification failure
   handled by the rules of Amendment A10 (use rule 4; Sec. 9.12): it is resolved and its cause entered in Sec. 13
   before any of these numbers enters the paper.
8. The sha256 of `table1_extra.json`, of the `SHA256SUMS` of the verification directory and of the class report, with
   the numbers of each class, are entered in their own dated Sec. 13 entry before the paper is written (A11 use
   rule 3).

The classes were fixed with their P1 sizes known (Sec. 3); no test-route value was read, and no class depends on a
value of the final run other than the verifier's own output for that run and the inputs it recorded.

## 2. The mechanisms

### 2.1 F1

* `framelease_v4/arms/actor_log.py` places a row of the actor-box log at its frame time, a multiple of 0.05 s; the
  rows of the log carry these times exactly (`build/R7B/rereview/PROGRESS.md`, 12:05, `time_offsets.py`).
* `realized.py` evaluates a plan with `GTTrack` of `framelease_v2/geometry.py`. `GTTrack._bracket` takes a time as
  inside the log only up to the last row time + 1e-9 s; `realized.py` counts a clear plan as log-censored when
  `capture_s + 3.0 > t_end + 1e-9`.
* The plan sample times `capture_s + tau` lie above the 0.05 s grid by the runtime's clock offset: a drift of 1.49e-8
  s per s of simulated time, up to 2.98e-6 s at 200 s (the measurement of the review of the fixes on the 180 run
  directories of the snapshot, `time_offsets.py`, 12:05). On all plans of the P1 run directories (`plans.csv` of the
  verification outputs below): 7.45e-10 to 2.97e-6 s, none below the grid, median 5.9e-7 s on the snapshot and
  5.7e-7 s on the 272 run directories, more than 1e-9 s for 98% of the plans (55,875 of 56,892 on the snapshot;
  67,860 of 68,977 on the 272 run directories). At the plans that F1 changes, the sample lies 1.39e-7 to 1.18e-6 s
  (snapshot) and 1.39e-7 to 1.99e-6 s (272 run directories) after the last row.
* So a sample that lands on the last row has no actors: a conflict first found there is lost, and a clear plan whose
  last sample (tau 3.0) lands there is log-censored. The recomputation places a sample on a row within 1 ms (its
  documented convention; Sec. 6.3 states no row tolerance) and counts these plans; it forms the registered convention
  as the view 'F1' and gives a difference cause F1 when the registered value agrees with the value under that view.
* The range "3e-7 to 1.1e-6 s" of the R7B review (should-fix S3, a sample of capture times) is narrower than the
  measured range above; A11 states the measured one.

### 2.2 F3

`realized.py` takes V by linear interpolation of the clearance between the samples j - 1 and j
(`framelease_v2/c2_eval.py` `observed_validity`, `geometry.py` `first_crossing_time`), over the vehicles and walkers
within the candidate radius d_safe + 5 m, where Sec. 6.3 defines V as the first time the footprint comes within d_safe.
On the 271 P1 run directories with an actor log it differs from the first crossing by up to 31.7 ms, by more than 1 ms
for 914 of the 7,078 conflict plans whose first conflicting sample lies after tau 0, and decides the miss of 2 plans
differently: route 2086 plan 240:2 outside the 1e-3 s band of the miss rule, one more within it. The verifier forms
the values under F3 (V_lin) with the bounds of that band, and under F1+F3.

### 2.3 Jobs in flight

* The aggregator (`framelease_v4/arms/metrics_v4.py`, `run_metrics`) forms `gpu_busy_recomputed_s` and
  `gpu_usage_recomputed` from the intervals of `jobs.jsonl` and the prefixes of the `job_start` events: a job still
  running at the end of the run has no `jobs.jsonl` row, so its step quanta are omitted (its docstring: "it can be
  lower by at most that job's steps"). It forms `commits` from the `committed_depths` of the `jobs.jsonl` rows, so the
  commits of that job are omitted.
* The verifier (`_gpu_intervals`) adds the step quanta of that job shown in the ticks' `gpu` field, with bounds for
  the scheduler boundaries inside them, and counts every accepted `commit` event.
* What the analysis reads. `analyze_v4.py` reads the `runs.csv` column `gpu_usage` for GPU usage (its Metric table);
  `metrics_v4.py` fills it from the runtime's `summary.json` (`gpu_busy_ratio`, the exact busy intervals including the
  job in flight) and falls back to `gpu_usage_recomputed` only when that field is absent. In that case the value the
  analysis reads is affected: the verifier reports a `gpu_usage` difference, and class in-flight excludes the GPU
  columns of that run, so the case stays a verification failure. `analyze_v4.py` reads `commits` only in
  `no_log_run` (H5, Sec. 9.5) for a run whose commit-audit status is NO_LOG (neither `jobs.jsonl` nor
  `events.jsonl`); the verifier recomputes a run only with both files, so such a run never carries a class-in-flight
  difference. `figures_tables.py` reads no `runs.csv` (its "accepted commits" come from the commit-audit document).
  No analysis file reads `gpu_usage_recomputed` or `gpu_busy_recomputed_s`.

### 2.4 Jobs whose outcome is not 'ok'

* The runner ends a job with an outcome. 'ok' and 'result_with_warnings' are its OK outcomes (a valid record;
  `framelease_v2/gpu_queue.py` OK_OUTCOMES, `select_stage.py`); a timeout, a crash of the agent or a failure of the
  simulator is a failure, and its END-line result fields are empty. For a failure `select_stage.job_outcome` gives the
  aggregator outcome 'sim_failure' or 'agent_crashed' ('pending' for a job without a final outcome), and
  `aggregate_v4.py` `job_row` returns before `run_fields` exactly when that outcome is not 'ok': its `runs.csv` row
  holds the selection fields, the outcome, analysis_use false and missing_reason (Sec. 9.8: nothing is imputed; the
  analysis drops the row), and no metric.
* A valid run can leave the analysis another way: outcome 'ok', `run_fields` runs, its metric step fails, and the row
  gets analysis_use false, missing_reason 'no_metrics' and empty metric cells (`aggregate_v4.py`). That is an
  aggregator failure, not the mechanism of the class: the class requires the `runs.csv` outcome other than 'ok' and a
  failed runner outcome, so these differences stay without a class (review round 2, M1).
* The verifier recomputes the run directory that the job's final runner record names (when its logs parse) and
  compares it with the empty `runs.csv` cells and the empty runner result fields: every recomputed value differs, in
  scope 'record' (the row is not used), without a cause and without an absolute difference.
* The analysis reads no value of such a row: `analyze_v4.py` uses a cell only through a row with analysis_use and
  valid_record 1; a cell without one is 'missing' with the aggregator's missing_reason (Secs. 9.1, 9.8).

## 3. Development evidence (P1 training routes)

Development comparison of the registered version (`build/R7B/dev/verify_p1_snap_2203_d/`, `sha256sum -c` OK;
`verify_table1_extra.py` f77b2dcf against `build/R7B/dev/agg_snap_2203/`, the aggregator of Amendment A3), classes
by `f1_class_report.py` (`f1/f1_class_dev.json`):

| quantity | value |
|---|---|
| run directories recomputed | 180 (179 `runs.csv` rows with analysis_use) |
| comparisons / differences | 12,259 / 136 |
| differences by cause | F1 26, without a cause 110 |
| differences by class | F1 26, F3 0, in-flight 69, not-ok record 41, without a class 0 |
| class F1 in scope 'analysis' | 1: `fast_only`, route 1792, EIR 94/412 = 0.2282 recomputed, 85/412 = 0.2063 registered |
| runs with a class-F1 difference | 19 of 180: `event_triggered` 6, `fast_only` 5, `fixed_deep` 4, `fl_heuristic` 4 (all with analysis_use) |
| largest absolute difference, class F1, `runs.csv` | realized_log_censored_plans 10, realized_invalid_ticks 9, realized_conflict_plans 1, realized_misses 1, realized_invalid_tick_ratio 0.0218 (route 1792, the value the analysis reads) |
| largest absolute difference, class F1, `arm_summary.csv` | realized_invalid_tick_ratio 0.0010 (`fast_only` mean EIR: 0.1102 recomputed, 0.1092 registered) |
| plans that F1 changes | 40 in 19 run directories: 38 clear here and log-censored there, 2 conflicts (misses) here and log-censored there |
| class F1 differences without an absolute difference | 0 |
| class in-flight | 69 differences, 0 in scope 'analysis': `gpu_usage_recomputed` 31, `gpu_busy_recomputed_s` 31, `commits` 7 |
| runs with a class-in-flight difference | 31 of 180: `event_triggered` 8, `fast_only` 2, `fixed_deep` 11, `fl_heuristic` 9, `fl_original` 1 |
| largest absolute difference, class in-flight | `gpu_usage_recomputed` 0.0136 (`fixed_deep`, route 23659: 0.9944 recomputed, 0.9809 registered), `gpu_busy_recomputed_s` 0.212 s (`fixed_deep`, route 3514), `commits` 7 (`fl_heuristic`, route 2215: 990 / 983) |
| class F3 | 0 differences; 3 agreements within bounds at the value under F3 (route 2086) |
| class not-ok record | 41, 0 in scope 'analysis', all without an absolute difference: the timed-out unused run `v4p1_fl_heuristic_B0_d10_k1.0_s11_r23659` (`fl_heuristic`; 39 `runs.csv` cells in 38 columns, 2 runner result fields; runner outcome 'timeout', aggregator outcome 'sim_failure', analysis_use false) |
| outcome of the class report | 'pre-specified classes only' (status 'development', release 'not final') |

The 110 differences without a cause on the snapshot: the cross-check columns `gpu_usage_recomputed` (31),
`gpu_busy_recomputed_s` (31) and `commits` (7) of `runs.csv` in the 31 runs with a job still running at the end,
which omit the work of that job, and the timed-out unused run `v4p1_fl_heuristic_B0_d10_k1.0_s11_r23659` (39
`runs.csv` cells, 2 runner result fields). The 31 runs are exactly the runs of the snapshot that end with a job in
flight; in each, the registered GPU value lies below the recomputed lower bound, the `commits` difference equals the
commits of the job without a `jobs.jsonl` row, and the `gpu_usage` that the analysis reads agrees within the
in-flight bounds. Every one of the 69 meets the conditions of class in-flight, and every one of the 41 those of
class not-ok record (runner records `build/R7B/dev/p1_snap_2203/status.jsonl` and `build/R7B/dev/agg_snap_2203/runs.csv`
at the sha256 that `table1_extra.json` records).

On all 272 P1 run directories under `outputs/framelease_v4/tuning/` (`/tmp/A10A11/r7bfix/verify_p1_rundirs/`, item
R7B, 13:19-13:21; `f1/f1_class_p1_rundirs.json`): AGREE on `summary.json` (5,523 comparisons; no `runs.csv` in that
run), F1 changes 47 plans in 26 run directories (3 conflicts, 44 clear), F3 2 plans in 2; 36 of the 272 runs end with
a job in flight. The second review of the fixes ran the registered `realized.py` on the 271 run directories with an
actor log (`build/R7B/rereview/REVIEW.md`): for each of its 68,946 plans the conflict status, the miss, V = 0 and the
log-censoring equal the recomputation's view under F1+F3, and every registered per-run count, R_cond and R_cond
without V = 0 equals that view; EIR in 266 runs (the other 5 differ by the F2 denominator and lie inside the bounds).

## 4. Expected rates in the final run

Rates of the P1 evidence applied to the plan after Amendment A12 (Table I: 98 runs on 14 test routes; `queue_p4`: 127
runs), as the review of the rule computed them for the registered 308 Table I runs:

| class | P1 rate | expected in 98 Table I runs (127 runs) | registered plan (308) |
|---|---|---|---|
| F1 | 26 of 271 run directories (9.6%) | 9.4 runs (12.2); a condition mean over 14 routes holds an F1 route with probability 0.76 | 29.5 runs; probability 0.988 over 44 routes |
| in-flight | 31 of 180 runs (17.2%); 36 of 272 (13.2%) | 13.0 to 16.9 runs (16.8 to 21.9) | 40.8 to 53.0 runs |
| F3 outside the 1e-3 s band | 1 plan in 271 run directories | 0.36 plans (0.47); at least one with probability 0.30 | 1.1 plans |
| not-ok record | 1 of 180 runs (41 differences) | 0.54 runs at the P1 rate; A12 records one Table I job that timed out after two attempts (`v4p4_fl_original_k1.0_s11_r23658`) | 1.7 runs |

A plan of F3 in a run whose condition also holds an F1 route (probability 0.73 for the other 13 routes) gives cause
'F1+F3' at the analysis level; class F3 holds it.

## 5. Differences without a class (rule 7)

* The cause F3 omits the candidate radius (second review of the fixes, should-fix S1, not applied): an actor that
  enters the log next to the footprint at the conflicting sample, with every actor at sample j - 1 beyond the radius,
  gives a difference without a cause (V_lin up to 4.5 ms before the registered tau_j). No P1 plan has it.
* F2 with a decimated log and gaps inside a log give differences without a cause; no P1 log is decimated (largest
  425 kB), has rows more than 0.05 s apart or a row without actors.
* In a job whose outcome is not 'ok': a non-empty registered value that differs, or a difference in scope
  'analysis', stays without a class (rule 3, class not-ok record); so does a job whose runs.csv row has analysis_use
  true, and a valid run whose metric step failed (`runs.csv` outcome 'ok', missing_reason 'no_metrics').
* Class in-flight does not bound the size of a GPU cross-check difference (rule 3): an aggregator defect of another
  cause in `gpu_usage_recomputed` or `gpu_busy_recomputed_s` of a run that ends with a job in flight joins the class.
  Neither column is read by the analysis, and `gpu_usage` of that run must agree; the class report states the largest
  difference of each column (review round 2, S1).

## 6. Running the class report after the freeze

```
cd /home/kang/Desktop/DAC
taskset -c 12-15 nice -n 19 ionice -c 3 sha256sum outputs/framelease_v4/build/AMEND2/a10r7b/f1/f1_class_report.py
taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
    outputs/framelease_v4/build/AMEND2/a10r7b/f1/f1_class_report.py \
    outputs/framelease_v4/verification/final_<stamp>_table1_extra \
    --out outputs/framelease_v4/verification/final_<stamp>_table1_extra_f1_class.json
```

The sha256 of the script equals the one A11 cites under "Evidence"; a different sha256 stops the procedure. The report
reads `SHA256SUMS`, `differences.csv`, `runs_recomputed.csv`, `table1_extra.json` and `cause_plans.csv` of that
directory, and, when a row can belong to class not-ok record, the runner records and the `runs.csv` that
`table1_extra.json` 'inputs' names. It stops (exit 2) when an input differs from `SHA256SUMS` or from the sha256 that
`table1_extra.json` records, or the counts by cause differ from `table1_extra.json`, and states per class the numbers
of rule 4, `outcome` ('AGREE', 'pre-specified classes only' or 'verification failure') and `release`: the outcome
when `table1_extra.json` has status 'final', `script_sha256` equal to the sha256 of the registered
`verify_table1_extra.py` (`f77b2dcf...`) and `options.runs_csv_values` false, else 'not final' (`release_checks`
states each condition). `--out` lies next to the verification directory, never inside it (refused there and under
`framelease_v4/`), so its `SHA256SUMS` stays valid. The runner of each queue the verification reads has exited (its
`runner_exit` record written) before the verification runs, so its `status.jsonl` keeps the sha256 that
`table1_extra.json` records.
Standard library only; 0.05 s and 19 MB on the snapshot.

## 7. Files

* `f1/f1_class_report.py`: the class report (rules 3 and 4); `f1/test_f1_class_report.py`: its tests on synthetic
  verification outputs and on outputs of the verifier for its own fixture runs (28 passed, 44 subtests;
  `f1/logs/pytest_f1_class_report.log`; the third test of `A11_spec.json`).
* `f1/f1_class_dev.json`: its output on the development comparison (`build/R7B/dev/verify_p1_snap_2203_d/`).
* `f1/f1_class_p1_rundirs.json`: its output on the 272 P1 run directories (`/tmp/A10A11/r7bfix/verify_p1_rundirs/`;
  the input sha256 are recorded in the file).
* `f1/fix1_numbers.py`, `f1/fix1_numbers.json`: the recount of the split of the 110 differences without a cause, the
  capture offsets and the runs with unevaluable plans.
* `f1/evidence_a11_sha256.txt`: the files A11 cites by sha256 under "Evidence" and "Files", at drafting
  (`check_a11.py` compares them; `--write-evidence` rewrites the list).
* `f1/logs/`: the drafting logs of the A11 tests.
* `f1/line_check.py`: the line and parser check of a composed PROTOCOL.md against the sealed one.
* `f1/sim_output/`: the dry run of A10 then A11 on a scratch tree (`sim_tree.py --cases A`) and the line checks of
  item F1A11; the simulated PROTOCOL.md is kept as `.md.txt` and is never a source for the drivers.
* `f1/orig/`: the five files of item a10r7b before item F1A11 (`*.before_f1.*`), the files before fix pass 1
  (`*.before_fix1.*`) and before fix pass 2 (`*.before_fix2.*`).
* `f1/PROGRESS.md`: the log of the item and of its fix passes.
