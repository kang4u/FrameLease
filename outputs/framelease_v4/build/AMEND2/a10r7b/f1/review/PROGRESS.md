# PROGRESS of the review of item F1A11 (output directory f1/review/, report f1/REVIEW.md)

- 2026-11-15 14:39 Beijing: start; wrapper /tmp/A10A11/f1rev/p.sh (CPUs 12-15, nice 19, ionice 3, one BLAS thread,
  CUDA hidden, ulimit -v 1.5 GiB). registration.py --verify at start: exit 1; seal PROTOCOL.md OK; seal MANIFEST OK;
  manifest differs on 2 files (verify_table1_extra.py a8bf57b7 -> f77b2dcf, test_verify_table1_extra.py
  c3bf160c -> f0e74336). PROTOCOL.md ca54d359 (06:43:14), MANIFEST 4bfe7451, SEAL b8d516d1.
- 14:39-14:46 READ (read only): f1/PROGRESS.md, A11_entry.md (and its diff against f1/orig), F1_RULE.md, RUNBOOK.md,
  check_a11.py, make_a11_spec.py, A11_spec.json, f1_class_report.py, test_f1_class_report.py, f1_class_dev.json,
  line_check.py, R7B/rereview/REVIEW.md, REVIEW_round1.md (executions), R7B/PROGRESS.md (attempt 6),
  R7B/A11_input_round1.txt, final/A10_entry.md (use rules, deviation 9), PROTOCOL Secs. 6.3, 7.2, 7.4, 9.12, 9.13,
  verify_table1_extra.py (Comparisons, compare_run/summary/runner, compare_analysis), geometry.GTTrack._bracket,
  realized.py log_censored, actor_log.py budget, apply_entry_stream.py (registered set, newly cited count).
- 14:42 WRITTEN f1/review/review_f1_numbers.py (independent recount, standard library; writes only --out).
- 14:43 RUN review_f1_numbers.py (0.9 s, 22 MB) -> f1/review/review_f1_numbers.json. Inputs (read only, P1 training
  routes): build/R7B/dev/verify_p1_snap_2203_d/{differences,runs_recomputed,cause_plans,plans}.csv,
  /tmp/A10A11/r7bfix/verify_p1_rundirs/ (same files), build/R7B/dev/agg_snap_2203/runs.csv. All stated F1 numbers
  confirmed (19 runs: event_triggered 6, fast_only 5, fixed_deep 4, fl_heuristic 4, all analysis_use; r1792 EIR
  94/412 vs 85/412; largest differences; 40 plans / 19 dirs; 47 / 26; offsets 1.39e-7..1.99e-6 s; capture offsets
  7.45e-10..2.97e-6 s). Median capture offset on the 272 dirs 5.7e-7 s (F1_RULE.md states 5.9e-7, the snapshot value).
- 14:44-14:45 READ cause_plans.csv of both outputs (F1 conflict plans j = j_last_row 18, 39, 28; none at sample 0).
- 14:47 RUN check_a11.py (project, read only): exit 2, 3 open (A10; two stale application logs), count 2.
  make_a11_spec.py --check: equal, exit 0. sha256sum -c f1/evidence_a11_sha256.txt: 20 OK. sha256sum -c
  evidence_sha256.txt: exactly the two R7B files FAILED (as RUNBOOK Sec. 1 states).
- 14:47 SCRATCH /tmp/A10A11/f1rev/PROTOCOL.sealed.md (= ca54d359); check_a11.py --protocol <copy> --write-sim
  /tmp/A10A11/f1rev/sim: exit 2, same 3 open; line_check.py after A10+A11: 533 lines, 13 over 120 (all table rows),
  all checks passed; after A10: 279 lines, all checks passed.
- 14:50 TESTS (logs f1/review/logs/): test_verify_table1_extra.py 87 passed, 80 subtests (6.4 s, 68 MB);
  test_review_r7b.py 14 passed, 2 subtests (4.8 s, 94 MB); test_f1_class_report.py 7 passed (0.3 s, 37 MB).
- 14:51 WRITTEN f1/review/test_review_f1_class_report.py (f1_class_report.py on outputs that verify_table1_extra.py
  writes for the synthetic AnalysisCauses case of the round-2 re-review tests; /tmp only). RUN 14:51:24: 7 passed
  (0.7 s, 62 MB; log f1/review/logs/pytest_review_f1_class_report.log). Shows: analysis columns separated by metric,
  runs per arm right; a class F1 difference with one side empty (per_scenario.csv r_cond) has a null largest
  difference; the report accepts inputs that disagree with SHA256SUMS; release ignores the status.
- 14:52:23-14:53:11 SIMULATION sim_tree.py --out /tmp/A10A11/f1rev/sim_tree --cases A (48.7 s, 33 MB): A0 FAIL only
  on "manifest: 2 files differ" (the two R7B files); A1-A9 PASS (A10 newly cited 8, manifest 0fdb720e; A11 newly
  cited the two R7B files; seals OK; owners A10 / A11 / A11; 552 diff lines). Tree removed by the script.
- 14:54 READ differences.csv of the snapshot again (breakdown of the 110 without a cause): the timed-out job
  v4p1_fl_heuristic_B0_d10_k1.0_s11_r23659 has 39 runs.csv cells + 2 runner result fields (41); the cross-check
  columns of the other runs: gpu_usage_recomputed 31, gpu_busy_recomputed_s 31, commits 7 (69 cells in 31 runs;
  7 of them on three other route-23659 jobs). F1_RULE.md (28/28/6, 46 + 2) and RUNBOOK Sec. 5 item 2(b) ("62 of
  the 110") are wrong; the round-2 re-review counted every key holding r23659 as the timed-out run.
- 14:55:40 RUN f1_class_report.py on both development outputs into /tmp/A10A11/f1rev/: byte-equal to
  f1/f1_class_dev.json and f1/f1_class_p1_rundirs.json.
- 14:55 RUNBOOK check: Sec. 6 table, 34 rows, sha256sum -c OK. Sec. 1 precondition 1 still expects
  "manifest: OK" before A10 (the project reads "manifest: 2 files differ" since R7B attempt 6).
- 14:56:56 EDIT + RUN review_f1_numbers.py (line width; exact split of the 110 without a cause; 0.8 s, 22 MB):
  timed-out job 39 runs.csv + 2 runner result; others 31 / 31 / 7 in 31 runs. pyflakes clean, lines <= 120.
- 14:57-15:01 READ (python -c, read only): runs_recomputed.csv of the snapshot (the 31 runs: every one has in-flight
  GPU boundaries; 31 of 180 runs have them), runs_recomputed.csv of both outputs (runs with unevaluable plans: 8 and
  14; log_censored bounds use them), differences.csv rows of four F1 runs; stat of the 271 actor logs of the 272 P1
  run directories (largest 424,832 bytes). R7B review files and pins hashed: as A11 and RUNBOOK state.
- 14:59 CORRECTION of the entry above: those reads ran 14:56-14:58 (not 14:57-15:01).
- 15:05 COMPLETION of the log: before the 14:43 recount, 14:40-14:42 read only: sha256sum -c of
  build/R7B/dev/verify_p1_snap_2203_d/SHA256SUMS (5 OK), ls of /tmp/A10A11/r7bfix/verify_p1_rundirs/, the header
  lines of differences.csv, runs_recomputed.csv, cause_plans.csv, plans.csv and the comparisons of table1_extra.json
  of the snapshot output, the jobs/arm columns of its runs_recomputed.csv, the header of agg_snap_2203/runs.csv.
- 15:05 WRITTEN f1/REVIEW.md (Verdict GO_WITH_FIXES: M1 split of the 110, M2 RUNBOOK Sec. 1 precondition 1, M3
  Development data; S1-S7).
- 15:02 CORRECTION: the two entries above were written at 15:01 (not 15:05).
- 15:03 EDIT f1/REVIEW.md (M1 wording, S1 numbers, S3 wording, S6 time, execution list from 14:40) and the docstring
  of test_sha256sums_not_checked_gap; CORRECTION: the cause_plans reads ran 14:44-14:46. RUN 15:03:46 the review
  test: 7 passed (0.6 s, 62 MB); pyflakes clean; every line of the review files <= 120 columns.
- 15:04:46 END: registration.py --verify output equal to the start (both seals OK; manifest: 2 files differ, the two
  R7B files); PROTOCOL.md ca54d359, MANIFEST 4bfe7451, SEAL b8d516d1 (06:43:14), REGISTRATION c0ee0217,
  PIPELINE_STATE 73add832: no driver re-seal. The 39 item files hashed at the start unchanged; no new __pycache__ or
  empty file under framelease_v4/; nothing newer than the start under framelease_v4/, registration/, p1_driver/,
  amendment_a10/, amendment_a11/; only phase_driver/state.json (the driver); no ALERT, protocol_txn, STOP, PAUSE or
  entrytmp file; phase driver pid 256142 alive. f1/REVIEW.md: end paragraph and date range (15:06).
- 15:06 EDIT f1/REVIEW.md: M3 fix names the RUNBOOK Sec. 6 row of A11_entry.md. Widths <= 120. Done: Verdict
  GO_WITH_FIXES (M1-M3, S1-S7).

# ROUND 2: adversarial review of the A11 draft after two fix passes (report f1/review/REVIEW_round2.md)

Files of this round carry the prefix r2_ (scripts, tests, logs under logs/r2_*); scratch under /tmp/A11R2/.
Wrapper: `taskset -c 12-15 nice -n 19 ionice -c 3 r2_p.sh <cmd>` (r2_p.sh: ulimit -v 1.5 GiB, one BLAS thread,
CUDA hidden, PYTHONDONTWRITEBYTECODE=1); Python .conda-unidrive-linux/bin/python -I -B; pytest -p no:cacheprovider.

- 2026-11-16 00:02 Beijing: start. registration.py --verify: exit 0 (manifest OK, seal PROTOCOL.md OK, seal MANIFEST
  OK). PROTOCOL.md sha256 3fa337c1 (2026-11-15 23:30:57), MANIFEST 0fdb720e (221 files), SEAL 577f1c6a,
  REGISTRATION.json 6d309f94 (sealed 2026-11-15T23:30:57+0800, variant FULL).
- 00:03-00:10 READ (read only): f1/REVIEW.md, f1/PROGRESS.md (fix passes 1, 2, 2b), A11_entry.md, F1_RULE.md,
  f1_class_report.py, RUNBOOK.md header, Sec. 3, Sec. 5. sha256 of the reviewed files at start in
  /tmp/A11R2/hash_start.txt (A11_entry db3729c2, A11_spec 71323aad, make_a11_spec ee1603e2, check_a11 ed87abb7,
  RUNBOOK 7c7a771f, F1_RULE 4c7384d3, f1_class_report 4c7f3af5, its test f26ffb38, evidence 6184bd8e, f1_class_dev
  f0344500, f1_class_p1_rundirs 750387ed; verify_table1_extra f77b2dcf, its test f0e74336; PIPELINE_STATE 43d6cbe5).
- 00:10-00:25 READ (read only): PROTOCOL.md Secs. 9.8, 9.12, 9.13, A10 use rules and deviation 9, A12 entry;
  verify_table1_extra.py (Comparisons, value_agrees, _classify, compare_run, compare_runner_result, RUNS_CSV_MAP,
  load_runner_records, run(): per_job, runs_recomputed 'jobs', inputs, SHA256SUMS; _gpu_intervals and the GPU bounds;
  validity_run plans_by_status and commit_without_job_step; recompute_run missing logs); aggregate_v4.py job_row,
  run_fields; select_stage.job_outcome, OK_OUTCOMES ('ok', 'result_with_warnings'); framelease_v2/gpu_queue.py
  classify (valid record -> 'ok' or 'result_with_warnings'); analyze_v4.py no_log_run / H5 and its Metric table;
  figures_tables.py csv reads; commit_audit.py NO_LOG; test_f1_class_report.py (fixtures, InFlightClass,
  NotOkRecordClass).
- Correction: the two entries above are stamped ahead of the clock (written 00:03-00:08); stamps from here on come from
  date.
- 00:09 WRITTEN r2_numbers.py (independent recount, standard library, own class logic from the A11 text).
  RUN 00:08:52 (0.21 s, 24 MB; P1 training-route development outputs, read only): build/R7B/dev/verify_p1_snap_2203_d/
  (SHA256SUMS: 5 OK), /tmp/A10A11/r7bfix/verify_p1_rundirs/ (5 OK), build/R7B/dev/agg_snap_2203/runs.csv (9ee8c078),
  build/R7B/dev/p1_snap_2203/status.jsonl (3d8164ad) -> r2_numbers.json. Confirmed: 180 / 179 / 12,259 / 136 / 1;
  F1 26 (1 analysis; 19 runs: event_triggered 6, fast_only 5, fixed_deep 4, fl_heuristic 4; all analysis_use True;
  maxima 10, 9, 1, 1, 0.021845, arm_summary 0.000993); in-flight 69 = 31 + 31 + 7 in 31 runs (8/2/11/9/1), maxima
  0.013571 (fixed_deep r23659), 0.21230 s (fixed_deep r3514), 7 (fl_heuristic r2215, 990/983); not-ok 41 (39 cells in
  38 runs.csv columns, 2 runner result fields; runner final 'timeout' after 2 end records, aggregator 'sim_failure',
  analysis_use False); unexplained 0; summary.json 3,759 / 0; agree_within_bounds_by_cause {F3: 3}; F1 plans 40 in
  19 (38 clear, 2 conflict). 272 directories: AGREE, 5,523 / 0, 271 with an actor log, 36 end in flight, F1 47 in 26
  (44 / 3), F3 2 in 2. Rates: 9.40 / 12.18 / 29.55 runs, p14 0.756, p44 0.988, p13 0.731; in-flight 12.97-16.88 (98),
  16.81-21.87 (127), 40.76-53.04 (308); F3 0.362 / 0.469 / 1.137, p98 0.304; not-ok 0.544 / 1.711. All equal to A11,
  F1_RULE.md Sec. 3-4 and RUNBOOK Sec. 3.
- 00:10 TESTS (pytest -q -p no:cacheprovider -rA from the root, as apply_entry_stream.py --tests runs them; logs
  f1/review/logs/r2_pytest_*.log): test_verify_table1_extra.py 00:10:10-00:10:17 exit 0, 87 passed, 80 subtests (7.0 s,
  68 MB); test_review_r7b.py 00:10:17-00:10:22 exit 0, 14 passed, 2 subtests (5.1 s, 94 MB); f1/test_f1_class_report.py
  00:10:22-00:10:23 exit 0, 26 passed, 31 subtests (0.8 s, 66 MB). Equal to RUNBOOK Sec. 3 precondition 4 and A11
  "At drafting". Also checked: synthetic outputs syn_r4_d / r6_dev_inputs_d / syn_varied_d AGREE with 25,746 /
  25,746 / 20,242 comparisons (SHA256SUMS OK); snapshot console: runs.csv within Sec. 6.3 bounds 5, arm_summary 1;
  F1 plan offsets 1.39e-7..1.18e-6 s (snapshot), 1.39e-7..1.99e-6 s (272); first conflicting samples 18, 28, 39; 271
  actor logs, largest 424,832 bytes; F3 914 / 7,078 and 31.7 ms from build/R7B/rereview/PROGRESS.md 13:47 / 13:52.
- 00:13 CHECKS (no run data): 00:12:10 check_a11.py on the project: exit 2, checks passed, 3 open (the two
  amendment_a11/ logs of 10:55 older than a must_equal file; pytest_f1_class_report.log missing); newly cited exactly
  the two R7B files; --write-manifest changes no sealed sha256; G8 simulated. Same on the scratch copy
  /tmp/A11R2/PROTOCOL.sealed.md (= 3fa337c1). make_a11_spec.py --check: equal. sha256sum -c evidence_a11_sha256.txt:
  OK. WRITTEN r2_insert_check.py; RUN 00:13:21 (stamp 2026-11-16 02:00, logs f1/logs/): 297 entry lines, prose at
  most 120 columns (also with test summaries 2 characters longer), 4 table rows over 120; no line after the title read
  as a driver entry, amendment title, heading or Sec. 13.2 start; no hedging word, no mention of an assistant;
  in-place text 1x; 289 added or changed lines, none prose over 120; p1_driver.protocol_view and
  phase_driver.phase_view: amendments A1-A12 once each with A11 at line 3303 after A12, before the anchor (3601); P1
  entries 10 and phase entries 6 unchanged; both R7B files first cited by A11; a G8 entry inserted by
  phase_driver.insert_entry is read and A11 stays once; Sec. 9.12 "Verification." reads as intended. WRITTEN
  r2_make_tmp_spec.py (/tmp/A11R2/A11_spec.tmp.json and A11_entry.tmp.md: the three logs -> f1/logs/). CHECK MODE
  00:13:31 apply_entry_stream.py on the temporary spec: "check: pre-checks passed", exit 0 (6.6 s, 19 MB); on
  A11_spec.json: STOP at the missing pytest_f1_class_report.log (exit 1), as RUNBOOK Sec. 3 precondition 6 states.
- 00:17 WRITTEN r2_test_adversarial.py (11 tests, 20 subtests; synthetic outputs and the verifier's own
  outputs for its fixture run; /tmp only). RUN 00:14:49-00:14:50 (1.7 s, 62 MB; log logs/r2_pytest_adversarial.log):
  11 passed. Holds: analysis-read values without a cause (runs.csv, conditions.csv, per_scenario.csv, secondary.csv),
  an unknown cause, an absent column and an arm_summary value stay unexplained; in an in-flight run a gpu_usage
  difference (below or above the bounds) makes the GPU cross-check rows unexplained; commits in scope 'analysis'
  stays unexplained; a not-ok job whose row is used stays unexplained (synthetic and end to end); every missing or
  altered input, SHA256SUMS included, and a changed or missing recorded status.jsonl / runs.csv stop the report (exit
  2); runs.csv not recorded leaves the rows unexplained. GAPS: (1) class not_ok_record absorbs the empty cells of a
  job whose runner outcome is 'result_with_warnings' (an OK outcome of gpu_queue / select_stage.OK_OUTCOMES) or has no
  outcome, with runs.csv outcome 'ok' and missing_reason 'no_metrics' (a valid run dropped by a failed metric step):
  end to end on the verifier's output 'pre-specified classes only' (43 rows), against 'verification failure' with
  runner outcome 'ok'; (2) class in_flight takes a GPU cross-check value of any size below the lower bound (0.01 or 0).
- 00:17 READ (code): analyze_v4.py reads runs.csv columns through its Metric table (gpu_usage, not the
  cross-check columns) and 'commits' only in no_log_run (status NO_LOG of commit_audit: neither jobs.jsonl nor
  events.jsonl); figures_tables.py reads only analysis outputs checked against SHA256SUMS; prop1_coverage.py none;
  interim_guard.freeze_record lists ANALYSIS_MODULES only (not the R7B files); metrics_v4 gpu_usage from summary.json
  gpu_busy_ratio, else gpu_usage_recomputed; arm_summary holds no cross-check column; gpu_queue appends
  runner_start / runner_exit to status.jsonl; the class report does not check table1_extra.json script_sha256
  (f77b2dcf on both P1 outputs). test_review_f1_class_report.py (round 1) 00:16:24: 4 passed, 3 failed (the pin and
  the two gaps S3 closed), as the fix log states. line_check.py on /tmp/A11R2 (sealed copy vs. composed): all checks
  passed (303 lines, 4 table rows over 120, A11 once, later gate read).
- 00:18 WRITTEN REVIEW_round2.md: GO_WITH_FIXES; must-fix M1 (class not-ok record keyed on the runner's
  literal 'ok', never on the runs.csv outcome: absorbs a valid run dropped by a failed metric step) and M2 (this
  review in "Development data"); should-fix S1-S5. END 00:18:43 registration.py --verify: "manifest: OK", both seals
  OK, exit 0; PROTOCOL.md 3fa337c1, MANIFEST 0fdb720e, SEAL 577f1c6a, REGISTRATION 6d309f94 unchanged; reviewed files
  unchanged (sha256sum -c /tmp/A11R2/hash_start.txt); no new __pycache__ or empty file under framelease_v4/; nothing
  under framelease_v4/, registration/, amendment_a10/, amendment_a11/, p1_driver/, phase_driver/ newer than the start;
  no /tmp test directory left. Not touched: the protocol lock, the drivers, queues, build/G8CUT/, CARLA, the GPU.

# ROUND 3: re-check of fix pass 3 (report f1/review/REVIEW_round3.md)

- 00:27 START. registration.py --verify 00:27:18: "manifest: OK", both seals OK, exit 0; PROTOCOL.md 3fa337c1,
  MANIFEST 0fdb720e, SEAL 577f1c6a, REGISTRATION 6d309f94, PIPELINE_STATE 43d6cbe5. Files at start
  (/tmp/A11R2/hash_r3_start.txt): A11_entry a1db8524, A11_spec 3dc04684, make_a11_spec 3ec26961, check_a11 e1db7a5f,
  RUNBOOK 820c91a1, F1_RULE 190a6761, f1_class_report f53e21f8, its test 79c67568, evidence 86602b3f, f1_class_dev
  bedca68a, f1_class_p1_rundirs 61fe0cda; R7B files f77b2dcf / f0e74336 unchanged.
- 00:32 READ (read only): f1/PROGRESS.md "Fix pass 3"; diffs against f1/orig/*.before_fix3.* of
  f1_class_report.py (4c7f3af5 -> f53e21f8), test_f1_class_report.py, A11_entry.md, F1_RULE.md, check_a11.py,
  make_a11_spec.py, A11_spec.json, RUNBOOK.md; verify_table1_extra.py dump_json (sort_keys: 'inputs' sorted), guard /
  freeze_coverage (no status.jsonl sha256 check), interim_guard.freeze_record; aggregate_v4 / analyze_v4 /
  verify_independent: status.jsonl sha256 only recorded, never re-checked; gpu_queue.py STOP -> runner_exit.
- 00:29:52-00:30:06 TESTS (logs logs/r3_pytest_*.log): test_verify_table1_extra.py 87 passed, 80 subtests;
  test_review_r7b.py 14 / 2; f1/test_f1_class_report.py 28 passed, 44 subtests (all exit 0); round-1
  test_review_f1_class_report.py 4 passed, 3 failed (pin, two round-1 S3 gaps); r2_test_adversarial.py 9 passed, 18
  subtests, 4 failed: test_not_ok_record_with_an_ok_runner_outcome_gap (2 subtests: not_ok_record 0 != 2) and
  test_valid_run_dropped_by_a_failed_metric_step_gap (0 not > 30): M1 closed; test_analysis_read_values_without_a_
  class_holds: outcome 'verification failure' as asserted, release 'not final' because its synthetic table1_extra.json
  names no verifier sha256 (S3). The two S1 gap tests pass (the stated limitation). Confirmed as the fixer states.
- 00:31:29 WRITTEN r3_test_new.py and RUN (log logs/r3_pytest_new.log): 6 passed, 22 subtests. Holds: the round-2
  M1 cases inverted with variants (runner 'result_with_warnings', no outcome, ' ok ', None x runs.csv 'ok', '', ' ok'):
  0 not_ok_record, 'verification failure' released; the P1 mechanism ('timeout' / 'sim_failure', 'agent_crash' /
  'agent_crashed') stays in the class; release checks (development status, another or upper-case sha256,
  runs_csv_values 'false' or 0 -> 'not final'); commits without in-flight boundaries unexplained; duplicate runs.csv
  rows with a differing used row unexplained in either order. NEW GAP (non-blocking): the same job with final records
  in two queues ('timeout' in q_z, 'ok' in q_a; verifier --queue q_z --queue q_a keeps 'ok'): the class report reads
  the queues in the sorted order of table1_extra.json 'inputs' (dump_json sort_keys), takes 'timeout' and absorbs every
  difference. OBSERVATION: an agreeing used row followed by an empty unused row of the same job is absorbed (the
  analysis value agrees).
- 00:32:02-00:32:15 CHECKS (no run data): P1 numbers from f1_class_dev.json / f1_class_p1_rundirs.json against their
  before_fix3 copies: only release_checks added and the jobs entry split into runner / runs.csv outcome
  ('timeout' / 'sim_failure'); by class 26 / 0 / 69 / 41 / 0 equal to round-2 r2_numbers.json, runs per arm and
  maxima equal; input sha256 equal to the snapshot SHA256SUMS. r2_insert_check.py on /tmp/A11R2/PROTOCOL.sealed.r3.md
  (= 3fa337c1): 315 entry lines, prose <= 120 (also +2), 4 table rows over 120, no driver line, A1-A12 once, A11 line
  3303 after A12, entries unchanged, R7B files first cited by A11, G8 read; line_check.py all checks passed (321);
  check_a11.py project / scratch exit 2 (3 open test logs); make_a11_spec.py --check equal; evidence 22 OK; check mode
  temporary spec "check: pre-checks passed", A11_spec.json STOP at the missing third log.
- 00:33 WRITTEN REVIEW_round3.md: Verdict GO (round-2 M1, M2, S1-S5 fixed; non-blocking N1: a job with
  final records in two queues; observation: duplicate runs.csv rows; bookkeeping: cite this round, rewrap two short
  lines). END 00:33:31 registration.py --verify: "manifest: OK", both seals OK, exit 0; PROTOCOL.md 3fa337c1, MANIFEST
  0fdb720e, SEAL 577f1c6a unchanged; the reviewed files unchanged since 00:27 (sha256sum -c /tmp/A11R2/hash_r3_start.txt);
  no new __pycache__ or empty file under framelease_v4/; nothing newer under framelease_v4/, registration/,
  amendment_a10/, amendment_a11/, p1_driver/, phase_driver/; no /tmp test directory left.

# ROUND 4: review of fix pass 4 (class "undefined-metric pairing", N1, round-3 housekeeping; REVIEW_round4.md)

- 00:47 START. registration.py --verify 00:47:25: "manifest: OK", both seals OK, exit 0; PROTOCOL.md 3fa337c1,
  MANIFEST 0fdb720e, SEAL 577f1c6a, REGISTRATION 6d309f94 unchanged; PIPELINE_STATE.md now 31c502f2 (was 43d6cbe5;
  not written by this review). Files at start in /tmp/A11R2/hash_r4_start.txt: A11_entry df2f49b2, A11_spec bba16198,
  make_a11_spec a7c85333, check_a11 953fbb8a, RUNBOOK bf067f77, F1_RULE 5feda06a, f1_class_report ac82d65a, its test
  b2d3388c, evidence ec80acac, f1_class_dev 22ceb51f, f1_class_p1_rundirs 60aeeece; R7B files and analyze_v4.py
  (10d7ea4f) as registered.
- 00:48-00:50 READ (read only): f1/PROGRESS.md "Fix pass 4"; diffs against f1/orig/*.before_fix4.* (f1_class_report.py,
  A11_entry.md word-level, F1_RULE.md, RUNBOOK.md); verify_table1_extra.py SHIELD_ARMS / p_both (line 748-751),
  paired_triples, compare_paired_differences (note 'status %r', values only when both sides pair); analyze_v4.py paired
  (drop reason '<column> missing: <all missing conditions>'), Cond.name, FAMILIES, run_secondary, DESCRIPTIVE_CONTRASTS
  (no p_both); metrics_v4.py p_both None without shield. build/G8CUT/ not read. Expected count derived from the code
  and the A12 table: secondary p_both contrasts against an arm without a shield: fl_full - fixed_deep / fast_only /
  event_triggered (14 used routes each), fl_heuristic - fl_original and fl_full - fl_original (13: route 23658 has no
  used fl_original cell, both sides unpaired), F3 fl_full - fixed_deep / fast_only at kappa 1.5 and 2.0 on E (2 used
  routes each): 42 + 26 + 8 = 76; other routes of the subsets are 'cell not used' on both sides.
- 00:50:38-00:50:53 TESTS (logs logs/r4_pytest_*.log): 87/80, 14/2, 34 passed / 59 subtests (exit 0 each); round 1
  4 passed, 3 failed (as before); r2_test_adversarial.py 8 passed, 16 subtests, 7 failed; r3_test_new.py 5 passed, 1
  failed (test_two_queues_read_in_another_order_gap: SystemExit of N1).
- 00:52 WRITTEN r4_test_pairing.py: 8 passed, 17 subtests (logs/r4_pytest_pairing.log). WRITTEN r4_without_new_key.py
  (round-2 and round-3 tests with differences_by_class['undefined_metric_pairing'] asserted 0 and removed): 17 tests,
  exactly 4 failures + 1 error: the three round-2 M1 gap cases (0 != 2, 0 not > 30), the S3 release of
  test_analysis_read_values_without_a_class_holds, and the N1 SystemExit; the other 3 failures of the plain run are the
  new key only. Fixer's explanation confirmed.
- 00:53:33-00:53:48 CHECKS: P1 class reports vs before_fix4: only the new class (all 0) and its key added; by class
  26/0/69/41/0/0. Scratch insertion (/tmp/A11R2/PROTOCOL.sealed.r4.md = 3fa337c1): 331 entry lines, prose <= 120 (+2),
  4 table rows over 120, no driver line, A1-A12 once, A11 line 3303, entries unchanged, R7B files first cited by A11,
  G8 read; line_check.py all checks passed (337); check_a11.py exit 2 (3 open logs); spec equal; evidence 23 OK; f1/logs
  34/59; check mode temporary spec "check: pre-checks passed", A11_spec.json STOP at the missing third log.
- 00:54 WRITTEN REVIEW_round4.md: Verdict GO (non-blocking: N2 named condition outside the contrast, caught
  by the contrast row's n; S1, S2 wording; observation on data-undefined metrics; bookkeeping). END 00:54:44
  registration.py --verify: "manifest: OK", both seals OK, exit 0; reviewed files unchanged
  (/tmp/A11R2/hash_r4_start.txt); no new __pycache__ or empty file; nothing newer under framelease_v4/, registration/,
  amendment_a10/, amendment_a11/, p1_driver/, phase_driver/; no /tmp test directory left.
