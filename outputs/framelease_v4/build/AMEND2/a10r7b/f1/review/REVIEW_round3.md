Verdict: GO

Round-3 review of A11: re-check of fix pass 3 (`f1/PROGRESS.md`, section "Fix pass 3") against the round-2 review
`f1/review/REVIEW_round2.md` (dd465845..., GO_WITH_FIXES: must-fix M1, M2; should-fix S1-S5). `$A` stands for
`outputs/framelease_v4/build/AMEND2/a10r7b/`, `build/` for `outputs/framelease_v4/build/`.

Reviewed versions (unchanged from 00:27 to the end of this review, 2026-11-16; sha256 checked at start and end):
`A11_entry.md` a1db8524..., `A11_spec.json` 3dc04684..., `make_a11_spec.py` 3ec26961..., `check_a11.py` e1db7a5f...,
`RUNBOOK.md` 820c91a1..., `f1/F1_RULE.md` 190a6761..., `f1/f1_class_report.py` f53e21f8..., `f1/test_f1_class_report.py`
79c67568..., `f1/evidence_a11_sha256.txt` 86602b3f..., `f1/f1_class_dev.json` bedca68a..., `f1/f1_class_p1_rundirs.json`
61fe0cda...; the R7B files f77b2dcf... / f0e74336... unchanged. Each change was read as a diff against its backup
`f1/orig/*.before_fix3.*`. Every process ran as `taskset -c 12-15 nice -n 19 ionice -c 3` with one BLAS thread,
`CUDA_VISIBLE_DEVICES=''` and an address-space cap of 1.5 GiB, one at a time, at most 94 MB resident. This round read
no run directory, `runs.csv` or verification output of real data outside the test runs (the P1 numbers were checked on
the item's class reports, below), so "Development data" needs no sentence for it.

**Summary.** Every must-fix and should-fix of round 2 is fixed correctly. Class not-ok record now requires the
`runs.csv` outcome to be present and other than 'ok' (the condition of `job_row`'s early return) and the final runner
outcome to be present and outside ('ok', 'result_with_warnings'); the round-2 counter-examples and seven variants stay
unexplained and release 'verification failure', while the P1 mechanism stays in the class. The four failures of
`r2_test_adversarial.py` are exactly the expected ones. Two new counter-examples against the changed code find one
non-blocking gap (a job with final records in two queues) and one observation (duplicate `runs.csv` rows); neither
can occur with the registered job ids and the single queue of A12. The P1 numbers are unchanged, the tests pass, the
entry inserts cleanly after A12 in the current sealed PROTOCOL.md, and the check mode passes with a temporary spec.

**Round-2 items.**

* M1, fixed. `f1_class_report.py` `not_ok_job`: runner outcome a non-empty string (stripped) not in `RUNNER_OK =
  ('ok', 'result_with_warnings')`, `runs.csv` outcome non-empty and not 'ok', analysis_use false; the class reports
  both outcomes per job. A11 bullet "class not-ok record", F1_RULE.md rule 3 and Sec. 2.4, RUNBOOK Sec. 3 and
  `check_a11.py` RULE_PHRASES state it, including "A valid run whose metric step failed (`runs.csv` outcome 'ok',
  missing_reason 'no_metrics') is outside the class". New tests in `f1/test_f1_class_report.py` (six not-ok subtests and
  `test_valid_run_dropped_by_a_failed_metric_step` on the verifier's output) pass.
* M2, fixed. "Development data" holds the round-2 sentence verbatim and one for the reruns of fix pass 3 (00:20-00:22,
  matching `f1/PROGRESS.md` 00:20:48 and 00:21:42); RUNBOOK precondition 3 searches from 2026-11-16 00:24.
* S1, fixed. `commits` needs `gpu_inflight_boundaries` >= 1; the size limitation of the GPU columns is stated in the
  class bullet of A11, F1_RULE.md rule 3 and Sec. 5 and the docstring.
* S2, fixed. Cause bullet and "Evidence" cite `f1/REVIEW.md` (9e2f2eab...) and `f1/review/REVIEW_round2.md`
  (dd465845...) with their verdicts; `f1/evidence_a11_sha256.txt` lists 22 files, `sha256sum -c` OK.
* S3, fixed. `release` = outcome only when status 'final', `script_sha256` equal to `REGISTERED_VERIFIER`
  (f77b2dcf..., the file A11 registers) and `options.runs_csv_values` is False; `release_checks` states each. A11 use
  rule 1, F1_RULE.md Sec. 6 and RUNBOOK "After G8" state it; RUNBOOK precondition 2 ties `REGISTERED_VERIFIER` to a
  change of the verifier.
* S4, fixed. RUNBOOK "After G8": write `queue_p4/STOP` once every kept job is final and wait for the 'runner_exit'
  record before the verification (`gpu_queue.py`: STOP ends the runner after its current job, then `runner_exit`).
  Neither the guard (`freeze_coverage`) nor any analysis tool re-checks the `status.jsonl` sha256 that the aggregation
  records, so the later `runner_exit` record breaks nothing.
* S5, fixed. (a) the Findings closing sentence as proposed; (b) "P1 rates behind the expected sizes of the final run";
  (c) "(and F2, inside the bounds; ...)".

**The round-2 counter-examples** (`f1/review/r2_test_adversarial.py` rerun on f53e21f8, 00:30:05: 9 passed, 18
subtests, 4 failed). Each failure confirms the fix: `test_not_ok_record_with_an_ok_runner_outcome_gap`, subtests
'result_with_warnings' and 'no outcome' (not_ok_record 0 instead of 2) and
`test_valid_run_dropped_by_a_failed_metric_step_gap` (0 rows instead of more than 30): M1 closed;
`test_analysis_read_values_without_a_class_holds`: its outcome is still 'verification failure' as asserted, and its
release reads 'not final' only because the synthetic `table1_extra.json` names no verifier sha256 (S3). The two S1
gap tests pass, as the stated limitation implies. The fixer's statement is confirmed. `f1/review/r3_test_new.py`
asserts the inverted cases: all unexplained, release 'verification failure'.

**New counter-examples** (`f1/review/r3_test_new.py`, 6 passed, 22 subtests; synthetic outputs and the verifier's own
outputs for its fixture run).
* Holds: runner outcome 'result_with_warnings', missing, ' ok ' or null with `runs.csv` outcome 'ok', '' or ' ok':
  unexplained (12 subtests); runner 'timeout' / `runs.csv` 'sim_failure' and runner 'agent_crash' / 'agent_crashed':
  class not-ok record, release 'pre-specified classes only'; release 'not final' for status 'development', another
  or upper-case verifier sha256, `runs_csv_values` 'false' (a string) or 0; `commits` in a run without in-flight
  boundaries: unexplained; two `runs.csv` rows of one job with a differing used row: unexplained in either order.
* Gap, non-blocking (should-fix N1). The same job with final records in two queues, 'timeout' in `q_z` and 'ok' in
  `q_a`: the verifier given `--queue q_z --queue q_a` keeps the last final record ('ok', `load_runner_records`), so by
  the rule ("as the verifier reads them") no class applies; the class report reads the queues in the order of
  `table1_extra.json` 'inputs', which `dump_json` writes with sorted keys, takes 'timeout' and puts every difference in
  class not-ok record (`test_two_queues_read_in_another_order_gap`; with `q_a` alone: 'verification failure'). It
  cannot occur under A11 as registered: the job ids carry their phase (`v4p1_`, `v4p4_`) and A12's aggregation covers
  `queue_p4` only. Fix when convenient: the class report stops (exit 2) when a job id has 'end' records in more than one
  recorded `status.jsonl`; F1_RULE.md Sec. 6 states it.
* Observation (`test_duplicate_runs_csv_rows`): an agreeing used row followed by an empty unused row of the same job is
  absorbed (`runs_csv_rows` keeps the last row); the analysis reads the used row, which agrees, so no analysis value is
  hidden. The registered aggregator writes one row per job line.

**P1 numbers unchanged.** `f1/f1_class_dev.json` and `f1/f1_class_p1_rundirs.json` against their `before_fix3` copies:
only `release_checks` added (status_final false, registered_verifier true, runs_csv_values_false true) and the job
entry of class not-ok record split into runner 'timeout' / `runs.csv` 'sim_failure'; every count, run per arm and
largest difference equal. By class 26 / 0 / 69 / 41 / 0, runs per arm and maxima equal to the independent recount of
round 2 (`f1/review/r2_numbers.json`); the recorded input sha256 equal the snapshot `SHA256SUMS`,
`agg_snap_2203/runs.csv` 9ee8c078... and `p1_snap_2203/status.jsonl` 3d8164ad.... The added conditions hold on P1 by
the round-2 recount: the timed-out job has runner 'timeout' and `runs.csv` 'sim_failure', and the 7 `commits` rows lie
in runs with in-flight boundaries (31 runs with boundaries, 31 ending in flight).

**Tests** (logs `f1/review/logs/r3_pytest_*.log`, 00:29:52-00:31:29): `test_verify_table1_extra.py` 87 passed, 80
subtests; `test_review_r7b.py` 14 passed, 2 subtests; `f1/test_f1_class_report.py` 28 passed, 44 subtests (each exit 0,
the counts of A11 "At drafting" and RUNBOOK precondition 4; the drafting logs in `f1/logs/` read the same);
`test_review_f1_class_report.py` (round 1) 4 passed, 3 failed (its pin and the two gaps round-1 S3 closed).

**Insertion and check mode** (no run data). `/tmp/A11R2/PROTOCOL.sealed.r3.md` (= 3fa337c1..., A10 and A12 in it),
`f1/review/r2_insert_check.py` (the applier's composition, stamp 2026-11-16 02:00, the logs of `f1/logs/`): in-place
text once; 315 entry lines, prose at most 120 columns after filling (also with test summaries two characters longer),
4 table rows over 120; no line after the title read as a driver entry, amendment title, heading or Sec. 13.2 start;
no hedging word, no mention of an assistant; `p1_driver.protocol_view` and `phase_driver.phase_view`: A1-A12 once each,
A11 at line 3303 after A12 and before the anchor, P1 entries (10) and phase entries (6) unchanged, both R7B files
first cited by A11, a G8 entry inserted by `phase_driver.insert_entry` read. `f1/line_check.py`: all checks passed (321
added or changed lines). `check_a11.py` on the project and on the copy: checks passed, exit 2 with the three open
application test logs. `make_a11_spec.py --check`: equal. Check mode `apply_entry_stream.py` on
`/tmp/A11R2/A11_spec.tmp.json` (template and three logs pointed at `f1/logs/`): "check: pre-checks passed", exit 0; on
`A11_spec.json`: STOP at the missing `pytest_f1_class_report.log` (RUNBOOK precondition 6).

**Before the application** (bookkeeping, not defects). Cite this review in the Cause bullet ("Its third round
(`build/AMEND2/a10r7b/f1/review/REVIEW_round3.md`) returned GO") and under "Evidence" by `{{sha256:...}}`, then
`check_a11.py --write-evidence`; close the "Open" item of RUNBOOK Sec. 3 precondition 2 and Sec. 5 item 2 with it. Two
lines of A11 are left short by the inserted text ("The definitions and tolerances were fixed in the docstring before the
first" and "directories, a job in flight at"); Markdown joins them, the drivers ignore them; rewrap if the entry is
edited again. Then, as RUNBOOK Sec. 3 states: `apply_entry_stream.py A11_spec.json --tests` right before the
application, `check_a11.py` exit 0, check mode "pre-checks passed".

**Files of this round.** `f1/review/`: REVIEW_round3.md, r3_test_new.py, logs/r3_pytest_*.log, PROGRESS.md (section
"ROUND 3"); reused r2_insert_check.py, r2_make_tmp_spec.py, r2_test_adversarial.py. Scratch: /tmp/A11R2/
(PROTOCOL.sealed.r3.md, sim_r3/, the temporary spec and template, check outputs).

Registration (`registration.py --verify`) at start (00:27:18) and end (00:33:31), equal output: "manifest: OK", seal
PROTOCOL.md OK, seal MANIFEST.sha256 OK, exit 0; PROTOCOL.md 3fa337c1..., MANIFEST 0fdb720e..., SEAL 577f1c6a...,
REGISTRATION 6d309f94..., PIPELINE_STATE.md 43d6cbe5... unchanged. At the end: the reviewed files unchanged since the
start of this round; nothing under `framelease_v4/`, `registration/`, `amendment_a10/`, `amendment_a11/`, `p1_driver/`
or `phase_driver/` newer than the start; no new `__pycache__` or empty file under `framelease_v4/`; no test directory
left under /tmp. The protocol lock, the drivers, their queues, `build/G8CUT/`, CARLA and the GPU were not touched.
