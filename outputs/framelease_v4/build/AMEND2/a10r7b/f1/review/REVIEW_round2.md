Verdict: GO_WITH_FIXES

Round-2 adversarial review of the draft of Amendment A11 after fix passes 1, 2 and 2b: `A11_entry.md`,
`A11_spec.json`, `make_a11_spec.py`, `check_a11.py`, RUNBOOK Secs. 3 and 5, `f1/F1_RULE.md`, `f1/f1_class_report.py`,
`f1/test_f1_class_report.py`, `f1/evidence_a11_sha256.txt`, and the registered R7B files
`framelease_v4/analysis/verify_table1_extra.py` and `framelease_v4/analysis/tests/test_verify_table1_extra.py`.
`$A` stands for `outputs/framelease_v4/build/AMEND2/a10r7b/`, `build/` for `outputs/framelease_v4/build/`.

Reviewed versions (unchanged from 00:02 to the end of this review, 2026-11-16; sha256 checked at start and end):
`A11_entry.md` db3729c2..., `A11_spec.json` 71323aad..., `make_a11_spec.py` ee1603e2..., `check_a11.py` ed87abb7...,
`RUNBOOK.md` 7c7a771f..., `apply_entry_stream.py` 7d86e576..., `f1/F1_RULE.md` 4c7384d3..., `f1/f1_class_report.py`
4c7f3af5..., `f1/test_f1_class_report.py` f26ffb38..., `f1/evidence_a11_sha256.txt` 6184bd8e..., `f1/f1_class_dev.json`
f0344500..., `f1/f1_class_p1_rundirs.json` 750387ed..., `verify_table1_extra.py` f77b2dcf..., its tests f0e74336....
Context read: `f1/REVIEW.md` (round 1), `f1/PROGRESS.md` (fix passes), `build/R7B/rereview/REVIEW.md` and PROGRESS.md,
PROTOCOL Secs. 9.8, 9.12, 9.13, the A10 entry (use rules, deviations 1 and 9) and the A12 entry. Spec of the review:
the three decisions of the coordinating session (registered `realized.py` and values stay; four mechanism-defined
classes F1, F3 with 'F1+F3', in-flight, not-ok record, each with counts all / analysis, runs per arm and the largest
absolute difference per column; any other difference in a value the analysis reads is a verification failure).
Every process ran as `taskset -c 12-15 nice -n 19 ionice -c 3` with one BLAS thread, `CUDA_VISIBLE_DEVICES=''`, an
address-space cap of 1.5 GiB, one at a time, at most 94 MB resident. Data read: P1 training-route development outputs
only; no test-route data, nothing under `matrix/`, `fig3/`, `ablation/`, `replicates/` or `queue_p4/`.

**Summary.** The four classes are implemented as the decisions state, computed from the verifier's outputs and, for
class not-ok record, from the runner records and `runs.csv` at the sha256 the verifier recorded. Every adversarial case
in a value the analysis reads stays unexplained: an analysis-scope value without a cause in `runs.csv`,
`conditions.csv`, `per_scenario.csv` or `secondary.csv`; `gpu_usage` that differs in an in-flight run (it also removes
the run's GPU cross-check rows from the class); `commits` in scope 'analysis'; a not-ok job whose row is used. Every
missing or altered input stops the report. The analysis code reads none of the in-flight columns (`analyze_v4.py`
reads `gpu_usage` and reads `commits` only for NO_LOG runs, which the verifier never recomputes; `figures_tables.py`
reads no `runs.csv`). Every P1 number of A11, F1_RULE.md and RUNBOOK Sec. 3 holds under an independent recount, the
expected sizes at the A12 scale are right, the three test files pass with the stated counts, and the entry inserts
cleanly after A12 in the current sealed PROTOCOL.md and reads correctly with both drivers' parsers; the applier's check
mode passes with the fix's logs. One defect needs a fix before application: class not-ok record keys on the runner's
literal outcome 'ok' and never reads the aggregator's outcome, so it absorbs the empty cells of a valid run that the
aggregator dropped through a failed metric step (M1). "Development data" must also list this review's reads (M2).

**Must fix.**

M1. Class not-ok record does not test its mechanism. The class is defined by `aggregate_v4.py` `job_row` returning
before `run_fields` (no metric) for a job whose outcome is not 'ok'. `f1_class_report.py` (lines 195-198, 224-240,
364-367) instead requires the runner's final outcome to differ from the string 'ok' and never reads the `runs.csv`
column `outcome`. The runner reports a valid record as 'ok' or 'result_with_warnings' (`framelease_v2/gpu_queue.py`
`classify`, line 721; `OK_OUTCOMES = ('ok', 'result_with_warnings')`, also `select_stage.py` line 71), and for such a
job `select_stage.job_outcome` gives outcome 'ok' (lines 217-229) and `job_row` runs `run_fields`; when its metric
step fails (`metrics` None), the row gets analysis_use false, missing_reason 'no_metrics' and empty metric cells
(`aggregate_v4.py` lines 578-600): a valid run leaves Table I through an aggregator failure. Counter-example on the
verifier's own output (`f1/review/r2_test_adversarial.py`, `test_valid_run_dropped_by_a_failed_metric_step_gap`): the
fixture run, runner final outcome 'result_with_warnings', `runs.csv` row outcome 'ok', analysis_use False,
missing_reason 'no_metrics', metrics empty: 43 differences, all in class not-ok record, outcome 'pre-specified classes
only', so the columns are released; the same row with runner outcome 'ok' gives 'verification failure'. A final runner
record without an outcome is absorbed the same way (`test_not_ok_record_with_an_ok_runner_outcome_gap`). Fix:
`f1_class_report.py` puts a row in class not-ok record only when, in addition, the job's `runs.csv` row has an
`outcome` other than 'ok' (the condition under which `job_row` records no metric: 'sim_failure', 'agent_crashed',
'pending') and its final runner outcome is present and not in ('ok', 'result_with_warnings'); report both outcomes per
job. Text, same change: A11 bullet "class not-ok record" ("... of a job whose final runner outcome is a failure (not
'ok' or 'result_with_warnings': timeout, crash, simulator failure), whose `runs.csv` row carries an outcome other than
'ok' and analysis_use false. For such a job `aggregate_v4.py` (`job_row`) records no metric ..."), F1_RULE.md rule 3
and Sec. 2.4, RUNBOOK Sec. 3 rule paragraph, `check_a11.py` RULE_PHRASES. Tests: both gap cases of
`r2_test_adversarial.py` become unexplained (invert them into `f1/test_f1_class_report.py`). Then the class reports
`f1/f1_class_dev.json` and `f1/f1_class_p1_rundirs.json` (P1 numbers unchanged: the timed-out job has `runs.csv`
outcome 'sim_failure' and runner outcome 'timeout'), the "At drafting" counts, MUST_EQUAL in `make_a11_spec.py` and
the spec, `check_a11.py --write-evidence`, RUNBOOK Sec. 6, and a review of the change (RUNBOOK Sec. 3, precondition
2).

M2. "Development data" (RUNBOOK Sec. 3, precondition 3; round-1 M3) lacks this review. After the sentence on the fixes
of the first review add: "The second review of the reporting rule read the same outputs,
`build/R7B/dev/agg_snap_2203/runs.csv` and `build/R7B/dev/p1_snap_2203/status.jsonl` (2026-11-16 00:05-00:12, its own
scripts, into `build/AMEND2/a10r7b/f1/review/` and /tmp/A11R2/; `build/AMEND2/a10r7b/f1/review/PROGRESS.md`)." and a
sentence for the reruns of the M1 fix; then the search of precondition 3 from 2026-11-16 00:00 and `check_a11.py`.

**Should fix.**

S1. Class in-flight tests the direction, not the size, of the GPU cross-check difference, and its `commits` condition
does not test the in-flight state of the run. A registered `gpu_busy_recomputed_s` of 0.01 s or `gpu_usage_recomputed`
of 0.01 in a run with in-flight boundaries is class in-flight (`r2_test_adversarial.py`,
`test_in_flight_cross_check_of_any_size_gap`, on the verifier's output; `test_in_flight_gpu_difference_of_any_size_gap`
with 0). Neither column is read by the analysis and `gpu_usage` must agree, so no analysis value is absorbed, but an
aggregator defect of another cause in these columns is. The verifier's outputs do not hold the in-flight step time,
so the size cannot be tested from them. Fix: state it in A11 (reporting rule or "Known limitations") and F1_RULE.md
Sec. 5: "for the GPU columns the class tests the in-flight boundaries of the run and the direction of the difference,
not its size against the omitted step quanta, which the verifier's outputs do not hold; the class report states the
largest difference". Optionally require `gpu_inflight_boundaries` >= 1 for `commits` as well (P1: the 7 `commits`
rows lie in runs with such boundaries; 8 of the 36 runs on the 272 directories), so a job missing from `jobs.jsonl` for
another reason stays unexplained.

S2. The reviews of the reporting rule are not cited. The Cause bullet names the verdicts of the three R7B reviews and
"Evidence" cites them by sha256; `f1_class_report.py`, whose sha256 A11 fixes, has its own reviews: `f1/REVIEW.md`
(9e2f2eab..., GO_WITH_FIXES, M1-M3 and S1-S7 applied, S1 as decided) and this review. Add both to the Cause bullet with
their verdicts and to "Evidence" by `{{sha256:...}}`; `check_a11.py --write-evidence`.

S3. `f1_class_report.py` forms `release` from `status` alone. Before 'AGREE' or 'pre-specified classes only' is
released, check `table1_extra.json` 'script_sha256' against the sha256 A11 registers for `verify_table1_extra.py`
(f77b2dcf...; both P1 outputs carry it) and 'options.runs_csv_values' false; otherwise 'not final'. A test.

S4. RUNBOOK "After G8": with A12's timed-out job a not-ok candidate is certain, so the class report re-reads
`queue_p4/status.jsonl` at the sha256 the verifier recorded; the runner appends `runner_start` / `runner_exit` records
(`gpu_queue.py`). Stop the runner of `queue_p4` (its `runner_exit` record written) before the verification, or a later
record stops the report (exit 2) and the verification has to be rerun.

S5. Precision of three sentences of A11. (a) Findings, closing sentence: "The recomputation reports every value that
F1 or F3 changes as a difference with that cause" is too wide (a changed value can agree within the standard bounds,
as the three F3 values of route 2086, or differ without a cause); write "A difference whose registered value equals
the value under F1, F3 or both, at the tolerances or within the bounds under that convention, carries that cause
(`differences.csv` 'cause')". (b) "Rates for the final run (...): an F1 plan in 26 of the 271 run directories, ..."
lists P1 rates; write "P1 rates behind the expected sizes of the final run (...)". (c) Cause bullet: "differ by the
conventions F1 and F3" omits F2 (the EIR denominator, absorbed by the bounds on P1); add "(and F2, inside the bounds)".

**Verified.**

* Classes against the decisions. F1 = cause 'F1'; F3 = 'F3' or 'F1+F3'; the verifier gives a cause only when the
  registered side agrees with the value under the convention at the tolerances or within the bounds under it
  (`value_agrees`, `Comparisons._classify`, first of F1, F3, F1+F3). In-flight: no cause, target `runs.csv`, scope
  'record', columns `gpu_usage_recomputed` / `gpu_busy_recomputed_s` (in-flight boundaries >= 1, registered below the
  recomputed lower bound, no `runs.csv` difference of the job in `gpu_usage` or `gpu_busy_in_span_s`) or `commits`
  (difference equal to `no_plan_logged` minus `commit_without_job_step`, >= 1). Not-ok record: no cause, scope 'record',
  `runs.csv` or runner result, registered side empty, runner final outcome not 'ok', `runs.csv` analysis_use false,
  both read from `table1_extra.json` 'inputs' at the recorded sha256. Report: counts all / analysis, runs per arm with
  those with an analysis difference, largest absolute difference and rows without one per (target, metric, column).
* Counter-examples that hold (`r2_test_adversarial.py`, 11 passed, 20 subtests): analysis-read values without a cause
  in `runs.csv`, `conditions.csv`, `per_scenario.csv`, `secondary.csv`, an unknown cause 'F2', an absent column, an
  `arm_summary.csv` value: unexplained, 'verification failure'. In-flight run: `gpu_usage` below or above the bounds
  makes it and both GPU cross-check rows unexplained (also end to end); `commits` in scope 'analysis' unexplained. A
  not-ok job whose row is used ('True', 'true', '1'; and end to end): unexplained. Missing `SHA256SUMS` or any of the
  four inputs, any input altered after `SHA256SUMS`, a recorded `status.jsonl` or `runs.csv` changed or missing: exit
  2; `runs.csv` not recorded: unexplained.
* What the analysis reads. `analyze_v4.py`: `runs.csv` columns through its Metric table (`gpu_usage` for GPU usage;
  no cross-check column) and `commits` only in `no_log_run` for commit-audit status NO_LOG (neither `jobs.jsonl` nor
  `events.jsonl`); `recompute_run` needs all four logs, so such a run has no comparison. `figures_tables.py` reads only
  analysis outputs checked against their `SHA256SUMS`; `prop1_coverage.py` reads no `runs.csv`. `metrics_v4.py` fills
  `gpu_usage` from `summary.json` `gpu_busy_ratio`, else from `gpu_usage_recomputed` (then `gpu_usage` differs and the
  class excludes the run); `arm_summary.csv` holds no cross-check column. The freeze record lists the aggregator
  modules only (`interim_guard.ANALYSIS_MODULES`), not the R7B files (A11 "Scope").
* P1 numbers (`f1/review/r2_numbers.py`, own class logic from the A11 text, standard library). Snapshot
  (`build/R7B/dev/verify_p1_snap_2203_d/`, `SHA256SUMS` 5 OK): 180 run directories, 179 used rows, 12,259
  comparisons, 136 differences, 1 analysis; F1 26 (25 `runs.csv` in 19 jobs, 1 `arm_summary.csv`), runs per arm 6 / 5
  / 4 / 4, all analysis_use True; maxima 10, 9, 1, 1, 0.021845 (route 1792, 94 / 412 vs 85 / 412), 0.000993; plans 40
  in 19 (38 clear, 2 conflict); in-flight 31 + 31 + 7 = 69 in 31 runs (8 / 2 / 11 / 9 / 1), the 31 runs with in-flight
  boundaries, maxima 0.013571 (fixed_deep route 23659), 0.21230 s (fixed_deep route 3514), 7 (fl_heuristic route
  2215, 990 / 983); not-ok 41 (39 cells in 38 `runs.csv` columns, 2 runner result fields; runner 'timeout' after two
  end records, `runs.csv` outcome 'sim_failure', analysis_use False); unexplained 0; F3 0, 3 agreements within bounds
  under F3; `summary.json` 3,759 / 0; Sec. 6.3 bounds agreements 5 `runs.csv` (routes 2086, 24211) and 1
  `arm_summary.csv`. 272 directories: AGREE, 5,523 / 0, 271 actor logs, 36 in flight, F1 47 plans in 26 (44 / 3), F3 2
  in 2; F1 offsets 1.39e-7 to 1.18e-6 s (snapshot), 1.39e-7 to 1.99e-6 s (272); first conflicting samples 18, 28, 39;
  largest actor log 424,832 bytes. Synthetic outputs AGREE with 25,746 / 25,746 / 20,242 comparisons. F3 914 of 7,078
  and 31.7 ms as in `build/R7B/rereview/PROGRESS.md` (13:47, 13:52). Expected sizes: F1 9.40 / 12.18 / 29.55 runs,
  P(an F1 route among 14) 0.756, among 44 0.988, among 13 0.731; in-flight 12.97-16.88 (98), 16.81-21.87 (127),
  40.76-53.04 (308); F3 0.362 / 0.469 / 1.137, P(at least one in 98) 0.304; not-ok 0.544 / 1.711. All equal to the text.
* Tests (logs `f1/review/logs/r2_pytest_*.log`): `test_verify_table1_extra.py` 87 passed, 80 subtests;
  `test_review_r7b.py` 14 passed, 2 subtests; `f1/test_f1_class_report.py` 26 passed, 31 subtests (RUNBOOK precondition
  4, A11 "At drafting"). Round-1 tests `f1/review/test_review_f1_class_report.py`: 4 passed, 3 failed, exactly the pin
  and the two gaps that round-1 S3 closed.
* Insertion (`/tmp/A11R2/PROTOCOL.sealed.md` = 3fa337c1..., A10 and A12 in it; `f1/review/r2_insert_check.py`, the
  applier's composition, stamp 2026-11-16 02:00, the fix's logs): in-place text once; Sec. 9.12 "Verification." reads
  as intended; 297 entry lines, prose at most 120 columns after filling (also with test summaries two characters
  longer), 4 table rows over 120; no line after the title read as a driver entry, amendment title, heading or Sec.
  13.2 start; no hedging word, no mention of an assistant. `p1_driver.protocol_view` and `phase_driver.phase_view`:
  A1-A12 once each, A11 at line 3303 after A12 and before the anchor, P1 entries (10) and phase entries (6) unchanged,
  both R7B files first cited by A11; a G8 entry inserted by `phase_driver.insert_entry` is read. `f1/line_check.py` on
  the same pair: all checks passed. `check_a11.py` (project and scratch): checks passed, exit 2 with the three open
  test-log items. `make_a11_spec.py --check`: equal. `sha256sum -c f1/evidence_a11_sha256.txt`: OK.
* Applier check mode: `apply_entry_stream.py` on `/tmp/A11R2/A11_spec.tmp.json` (template copy and three test logs
  pointed at `f1/logs/`, `f1/review/r2_make_tmp_spec.py`): "check: pre-checks passed", exit 0; on `A11_spec.json`: STOP
  at the missing `pytest_f1_class_report.log` (RUNBOOK precondition 6).

**Executions on real data** (this review; read only; P1 training-route development outputs; 2026-11-16).
* 00:05-00:08 header lines and `SHA256SUMS` of `build/R7B/dev/verify_p1_snap_2203_d/` and of
  `build/R7B/dev/agg_snap_2203/runs.csv`; 00:08:52 `f1/review/r2_numbers.py` on that directory,
  /tmp/A10A11/r7bfix/verify_p1_rundirs/, `agg_snap_2203/runs.csv` and `build/R7B/dev/p1_snap_2203/status.jsonl`, into
  `f1/review/r2_numbers.json`; 00:09 `table1_extra.json` of the three synthetic outputs, `reconcile_p1_d.json` keys and
  the snapshot console log; 00:11 `cause_plans.csv` of both outputs and the sizes of the 271 actor logs (stat only).
* Test runs 00:10:10-00:10:23 (the 14 P1-0 smoke run directories of route 18305; three P1 run directories and
  `agg_snap_2203/runs.csv`); 00:14:49 and 00:16:24 the review tests (synthetic only). Runs without run data: 00:12
  `check_a11.py`, `make_a11_spec.py --check`; 00:13 `r2_insert_check.py`, `line_check.py`, check mode.

**Files of this review.** `f1/review/`: REVIEW_round2.md, PROGRESS.md (section "ROUND 2"), r2_p.sh, r2_numbers.py,
r2_numbers.json, r2_insert_check.py, r2_make_tmp_spec.py, r2_test_adversarial.py, logs/r2_pytest_*.log. Scratch:
/tmp/A11R2/ (wrapper, sealed copy, composed texts, temporary spec and template, outputs of the checks).

Registration (`registration.py --verify`) at start (00:02) and end (00:18:43), equal output: "manifest: OK", seal
PROTOCOL.md OK, seal MANIFEST.sha256 OK, exit 0; PROTOCOL.md 3fa337c1..., MANIFEST 0fdb720e..., SEAL 577f1c6a...,
REGISTRATION 6d309f94..., PIPELINE_STATE.md 43d6cbe5... unchanged. At the end: the reviewed files unchanged; nothing
under `framelease_v4/`, `registration/`, `amendment_a10/`, `amendment_a11/`, `p1_driver/` or `phase_driver/` newer than
the start; no new `__pycache__` or empty file under `framelease_v4/`; no ALERT, protocol_txn or `.PROTOCOL.md.entrytmp`
file; no test directory left under /tmp. The protocol lock, the drivers, their queues, `build/G8CUT/`, CARLA and the
GPU were not touched.
