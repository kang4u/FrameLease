Verdict: GO_WITH_FIXES

Review of item F1A11: the reporting rule of finding F1 in the draft of Amendment A11, its P1 development evidence,
"Development data" with both rounds of the review of the R7B fixes, the R7B pins and test counts (`make_a11_spec.py`,
`A11_spec.json`), `check_a11.py`, the line and parser checks of A10 then A11 on scratch copies, `f1/F1_RULE.md` and
RUNBOOK Sec. 3. `$A` stands for `outputs/framelease_v4/build/AMEND2/`, `build/` for `outputs/framelease_v4/build/`.

Reviewed versions (unchanged from 14:39 to the end of this review; sha256 checked at start and end):
`$A/a10r7b/A11_entry.md` 9fc737ac..., `A11_spec.json` 30dfb776..., `make_a11_spec.py` 3776e06d..., `check_a11.py`
1e157544..., `RUNBOOK.md` a1ecba8b..., `f1/F1_RULE.md` 067532ac..., `f1/f1_class_report.py` 3ef60e91...,
`f1/test_f1_class_report.py` 6e5f4fe1..., `f1/f1_class_dev.json` 741a035c..., `f1/f1_class_p1_rundirs.json`
47803fa2..., `f1/evidence_a11_sha256.txt` 8fe5bf48..., `f1/line_check.py` 29e03516...; the R7B files
`verify_table1_extra.py` f77b2dcf... and `tests/test_verify_table1_extra.py` f0e74336.... Spec of the review: the
decision on F1 (registered `realized.py` unchanged; registered values in Tables I and II and the paper; class F1 with
its cause, the affected runs per arm and the largest absolute difference per affected column; the paper states class
and size next to the verification result; any other cause is a verification failure under A10 and Sec. 9.12), PROTOCOL
Secs. 6.3, 7.2, 7.4, 9.11-9.13, `final/A10_entry.md`, `build/R7B/` (PROGRESS.md, A11_input_round1.txt, review/,
rereview/). Dates: 2026-11-15, 14:39-15:06 Beijing time. Every command ran as `taskset -c 12-15 nice -n 19 ionice -c 3`
with one BLAS thread, `CUDA_VISIBLE_DEVICES=''` and an address-space cap of 1.5 GiB, one at a time, at most 94 MB
resident. Read: P1 training-route development outputs and run-directory metadata only; no test-route data, no P2 data.

**Summary.** The A11 draft states the decided rule point by point and keeps the rest of the entry; the round-1 text
changes of `build/R7B/A11_input_round1.txt` and the A11 notes of the round-2 review are in, block [9] replaced by the
rule. Every P1 number of F1 holds under an independent recount (19 of 180 runs: `event_triggered` 6, `fast_only` 5,
`fixed_deep` 4, `fl_heuristic` 4, all with analysis_use; route 1792 EIR 85/412 = 0.2063 registered, 94/412 = 0.2282
recomputed; 40 plans in 19 run directories, 47 in 26 of 271). The measured offsets replace "3e-7 to 1.1e-6 s" with
the right numbers. "Development data" lists the executions of both review rounds and of R7B attempt 6 with their times.
Pins, spec and test counts hold; `check_a11.py` exits 2 with three open preconditions and no problem; A10 then A11
pass the line and parser checks in memory and on a scratch tree. Three defects need a fix before A11 is applied: the
split of the 110 differences without a cause in `f1/F1_RULE.md` (pinned by A11) and RUNBOOK Sec. 5 is wrong; RUNBOOK
Sec. 1 still expects "manifest: OK" before A10; "Development data" lacks the reads of this review.

**Must fix.**

M1. The split of the 110 development differences without a cause. `f1/F1_RULE.md` lines 84-87 (cited by sha256 under
"Evidence" of A11) state `gpu_usage_recomputed` 28, `gpu_busy_recomputed_s` 28 and `commits` 6, and 46 `runs.csv`
cells and 2 runner result fields of the timed-out run; RUNBOOK Sec. 5, item 2(b) states "62 of the 110".
`build/R7B/dev/verify_p1_snap_2203_d/differences.csv` (88102ad6..., `sha256sum -c` of the directory OK) holds: job
`v4p1_fl_heuristic_B0_d10_k1.0_s11_r23659`, 39 `runs.csv` cells and 2 runner result fields (41); the cross-check
columns of the other runs, `gpu_usage_recomputed` 31, `gpu_busy_recomputed_s` 31 and `commits` 7: 69 cells in 31
runs, exactly the 31 of the 180 runs whose `runs_recomputed.csv` row has in-flight GPU boundaries. The 7 cells that
the stated split gives to the timed-out run belong to three other jobs of route 23659
(`v4p1_fixed_deep_k1.0_s11_r23659` 2, `v4p1_event_triggered_v2_hb2.0_k1.0_s11_r23659` 3,
`v4p1_event_triggered_v2_hb1.0_k1.0_s11_r23659` 2): the stated numbers (from the round-2 review) are those of a count
that takes every key holding 'r23659' for the timed-out run. Evidence: `f1/review/review_f1_numbers.json` (snapshot:
unclassified_timed_out_job_by_target, unclassified_other_by_column, unclassified_other_runs). The total 110 and the
A11 text, which gives no split, are right. Fix: F1_RULE.md lines 84-87: "the cross-check columns
`gpu_usage_recomputed` (31), `gpu_busy_recomputed_s` (31) and `commits` (7) of `runs.csv` in the 31 runs with a job
still running at the end, which omit the work of that job, and the timed-out unused run
`v4p1_fl_heuristic_B0_d10_k1.0_s11_r23659` (39 `runs.csv` cells, 2 runner result fields)"; RUNBOOK Sec. 5, item
2(b): "(69 of the 110 development differences, in 31 of the 180 runs; scope 'record'; ...)"; then
`check_a11.py --write-evidence` and the RUNBOOK Sec. 6 rows of `f1/F1_RULE.md` and `f1/evidence_a11_sha256.txt`.

M2. RUNBOOK Sec. 1, precondition 1 (line 119) expects `registration.py --verify` to read "manifest: OK" before A10,
and the expected A10 output (lines 183-185) shows the manifest difference "new [] / left [] / changed []". Since R7B
attempt 6 the project reads "manifest: 2 files differ" naming exactly `framelease_v4/analysis/verify_table1_extra.py`
and `framelease_v4/analysis/tests/test_verify_table1_extra.py` (this review, start and end), and A10, applied first,
meets that state: the dry run (`/tmp/A10A11/f1rev/sim_tree`, step A2) prints "manifest difference: new [] / left [] /
changed ['framelease_v4/analysis/tests/test_verify_table1_extra.py', 'framelease_v4/analysis/verify_table1_extra.py']".
The item states this only in Sec. 3, precondition 5 (A11). Read in its order, Sec. 1 stops A10 at its first
precondition or invites a seal outside a transaction to clear the difference. Fix: line 119, comment: both "seal
...: OK" lines and "manifest: OK", or, until A10, "manifest: 2 files differ" naming exactly these two unregistered
R7B files (A10's `--write-manifest` records them; Sec. 3, precondition 5; never seal to clear it); any other file
named is a problem. Lines 183-185: "the manifest difference (`changed` exactly the two R7B files while A10 is the
first application after R7B attempt 6, else `new [] / left [] / changed []`)".

M3. "Development data" names the reading of class F1 and of the time offsets by item F1A11 (14:06-14:13) and no
later read. This review read the same development outputs and `build/R7B/dev/agg_snap_2203/runs.csv` from 14:40 to
14:58 (list below); RUNBOOK Sec. 3, precondition 3 counts such a read ("a run of the item or of a review on real data
(run directories, runs.csv)"). Fix: after the sentence that ends "into `build/AMEND2/a10r7b/f1/`).", add: "The review
of the reporting rule read the same outputs and `build/R7B/dev/agg_snap_2203/runs.csv` (2026-11-15 14:40-14:58, its
own scripts and `f1_class_report.py`, into `build/AMEND2/a10r7b/f1/review/` and /tmp/A10A11/f1rev/;
`build/AMEND2/a10r7b/f1/review/PROGRESS.md`)."; then `check_a11.py` (and `--write-evidence` with M1) and the
RUNBOOK Sec. 6 row of `A11_entry.md`.

**Should fix.**

S1. A verification failure in the final run is predictable (RUNBOOK Sec. 5, item 2 raises both causes; for the
decision before A11 is applied). (a) The in-flight cross-check columns: 31 of the 180 snapshot runs (17%) give
differences without a cause in `gpu_usage_recomputed`, `gpu_busy_recomputed_s` and `commits` (M1); at that rate the
308 Table I runs hold 53 such runs. (b) F3: one plan of the 271 P1 run directories changes its miss outside the
1e-3 s band (route 2086 plan 240:2); at that rate 308 runs hold 1.1 such plans, each a cause 'F3' in the misses and
R_cond of its run unless other bounds absorb it. F1 touches 26 of the 271 run directories (9.6%); at that incidence a
condition mean over 44 routes holds an F1 route with probability 0.988, and an F3 plan in such a condition gives
cause 'F1+F3' at the analysis level. Under the rule as decided each of these differences is a verification failure,
resolved and entered in Sec. 13 under A10 use rule 4 before any of the eight columns enters the paper, and the class
report reads 'verification failure'. Either pre-specify their classes in A11 now (the record-scope cross-check columns
of runs with in-flight GPU boundaries; F3 and F1+F3 as conventions of the registered `realized.py`), or keep the rule
and plan the Sec. 13 resolution entry for them.

S2. A class F1 difference with one side empty has no absolute difference. `verify_table1_extra.py` leaves `abs_diff`
empty when one side is empty; a run whose every conflict plan is changed by F1 has an empty registered R_cond, so its
`per_scenario.csv` r_cond row is class F1 with no number, and `f1_class_report.py` reports the largest absolute
difference of that column as null (`f1/review/test_review_f1_class_report.py`, test_one_side_empty_gap, on the
verifier's own output for the synthetic AnalysisCauses case). The rule gives no reading for it. Fix: the report counts
per column the class F1 rows without a numeric difference, and the rule adds "a column whose class F1 differences have
one side empty states their number"; a test; F1_RULE.md; `--write-evidence`.

S3. Integrity of the class report. `f1_class_report.py` reads the four inputs without checking them against the
`SHA256SUMS` of the verification directory (test_sha256sums_not_checked_gap: a copy with the rows without a cause
removed from `differences.csv` and from the counts reads 'class F1 only'); it forms `release` for any status
(test_release_ignores_status_gap); it accepts an `--out` inside VERIFY_OUT although F1_RULE.md Sec. 5 states "never
inside it"; it omits `agree_within_bounds_by_cause['F1']`, the F1 values that the bounds absorb. Fix: exit 2 when an
input differs from `SHA256SUMS`; `release` only for status 'final' (else 'not final'); refuse `--out` inside
VERIFY_OUT; copy the agreements within bounds at the F1 value. Then the tests, `f1_class_dev.json`, F1_RULE.md and
`--write-evidence`.

S4. `f1/F1_RULE.md`, further precision (pinned evidence; fix with M1). Sec. 2: "median 5.9e-7 s" is the snapshot
median; on the 272 run directories it is 5.7e-7 s. Sec. 2: "The recomputation follows Sec. 6.3 (the row within 1
ms)": Sec. 6.3 states no row tolerance; the 1 ms row match is the recomputation's documented convention. Sec. 4,
first bullet: the 3 values that F3 changes on route 2086 agree within the bounds of the 1e-3 s band (plan 209:9,
`build/R7B/PROGRESS.md` 13:12:40), not "(F2)"; F2 is the EIR denominator of that run.

S5. A11, "Known limitations accepted ... no P1 value depends on them": the untested branch "the upper bound of the
log-censored plans with unevaluable plans" forms the log-censored bounds of 8 snapshot runs (14 of the 271), e.g.
route 23659 [6, 13]; the exact claim is "no P1 value is changed by them".

S6. RUNBOOK Sec. 3. Precondition 3 searches from 14:30, the last complete search of the item ran at 14:13:30; no
PROGRESS file other than `f1/PROGRESS.md` changed between them (checked at 14:53-14:55), so nothing is missed; write
14:13. "After G8": compare the sha256 of `f1/f1_class_report.py` with the one A11 cites before running it. The class
report's tests ("7 passed" in A11 "Evidence") are not a test of the spec and do not run at application; adding them
as a third test of `A11_spec.json` records them with the entry.

S7. The third open item of `check_a11.py` (the 10:55 application logs ran on attempt 5) is right and blocks a stale
"Tests" bullet only through `check_a11.py` and the RUNBOOK: the applier accepts the stale logs (dry run step A5,
check passed, then the tree's entry reads "71 passed, 67 subtests"). Run `apply_entry_stream.py A11_spec.json --tests`
right before the application, as precondition 4 requires.

**Verified.**

* The rule against the decision. A11 bullet "Reporting rule for finding F1 (fixed by this entry)" and use rules 2-3:
  `realized.py` stays as registered; the registered values (aggregator and analysis through `realized.py`) are the
  values of Tables I and II and of the paper (Table II-A lists EIR and closed-loop R_cond, Sec. 7.4); class F1 =
  cause 'F1' of `differences.csv`, with its count (all and in scope 'analysis'), the runs per arm and the largest
  absolute difference per (target, metric, compared column); the paper states class, cause and size next to the
  verification result; 'F3', 'F1+F3' or no cause is a verification failure under A10 use rule 4 (its text: "on DIFFER
  every difference is resolved and its cause entered in Sec. 13") and Sec. 9.12. `check_a11.py` RULE_PHRASES pins the
  sentences. "Development data" discloses that the rule was fixed with its P1 size known.
* The mechanism. `framelease_v2/geometry.py` `GTTrack._bracket`: inside up to `t[-1] + 1e-9`; `realized.py`
  log_censored: `capture_s + t_pred > t_end + 1e-9` and no conflict. Recount (`f1/review/review_f1_numbers.py`,
  standard library, no code of the item): capture offsets above the 0.05 s grid 7.45e-10 to 2.97e-6 s, none below
  it, 98.2% (55,875 of 56,892) and 98.4% (67,860 of 68,977) above 1e-9 s; the last-row times of the F1 plans lie on
  the grid; sample minus last row 1.39e-7 to 1.18e-6 s (snapshot) and 1.39e-7 to 1.99e-6 s (272 directories). The
  first conflicting samples of the F1 conflict plans are 18, 39 and 28, never sample 0.
* The P1 numbers. Snapshot: 136 differences, F1 26 (25 `runs.csv` in 19 jobs, 1 `arm_summary.csv`), 1 in scope
  'analysis', 110 without a cause; jobs per arm as stated, protocol_arm of `agg_snap_2203/runs.csv` equal to the arm
  of `runs_recomputed.csv`, all analysis_use True; route 1792 rows conflict 17/16, misses 17/16, invalid ticks 94/85,
  EIR 0.22815533980582525 / 0.20631067961165048 (scope 'analysis'), log-censored 2/3; largest differences 10
  (log-censored, job `..._v2_hb2.0_..._r23659`), 9, 1, 1, 0.021845, `arm_summary.csv` 0.000993 (0.110207 / 0.109214);
  F1 plans 40 in 19 directories (38 clear and 2 conflict plans, misses here, log-censored there); 272 directories: 47
  plans in 26 (44 and 3; per arm `age_only` 6, `event_triggered` 6, `fast_only` 5, `fixed_deep` 4, `fl_heuristic` 5),
  F3 2; largest actor log 424,832 bytes (271 logs). `f1_class_report.py` rerun on both outputs: byte-equal to
  `f1/f1_class_dev.json` and `f1/f1_class_p1_rundirs.json`.
* "Development data". Round 1 of the review of the fixes 12:02-12:04, 12:05-12:23, 12:13, 12:17, 12:17-12:19
  (`rereview/REVIEW_round1.md`, executions); R7B attempt 6 13:06-13:08, 13:09-13:11, 13:11-13:12, 13:17-13:19,
  13:19-13:21, 13:21 (`build/R7B/PROGRESS.md`); round 2 13:36-13:38, 13:39-13:41, 13:38-13:47, 13:57, 14:01 (the
  sentence of `rereview/REVIEW.md`, verbatim); item R7B "to 2026-11-15 13:22". No TODO line. F3 "914 of the 7,078"
  is the count of `realized.py` (`rereview/PROGRESS.md` 13:47); the review's "915" is the recomputation's own.
* Pins and counts. `make_a11_spec.py --check`: equal; MUST_EQUAL f77b2dcf / f0e74336 / 63c4359d equal to the files;
  `A11_spec.json` differs from its backup in the two must_equal lines only. Tests rerun (logs in `f1/review/logs/`):
  item 87 passed, 80 subtests; review 14 passed, 2 subtests; `f1/test_f1_class_report.py` 7 passed. `rereview/REVIEW.md`
  e1220a89... = `REVIEW_round2.md`, "Verdict: GO"; `REVIEW_round1.md` f7eb872f...; `sha256sum -c` of
  `f1/evidence_a11_sha256.txt`: 20 OK; of `evidence_sha256.txt`: exactly the two R7B lines FAILED (RUNBOOK Sec. 1
  note); RUNBOOK Sec. 6: 34 rows, all OK.
* `check_a11.py` (read only): exit 2; checks passed; newly cited after `--write-manifest` exactly the two R7B files;
  open: A10 not entered, the two application logs of 10:55 older than the R7B files. Its registered set equals the
  one of `apply_entry_stream.py` (both baselines, the sealed-manifest files PROTOCOL.md cites, the P1 job files).
* Scratch checks. `/tmp/A10A11/f1rev/PROTOCOL.sealed.md` (= ca54d359...), `check_a11.py --protocol` that copy
  `--write-sim /tmp/A10A11/f1rev/sim`: exit 2, the same open items; `f1/line_check.py`: after A10 and A11 533 added or
  changed lines, 13 over 120 columns, all table rows, titles A10 and A11 once, no driver entry, heading or Sec. 13.2
  start, P1 entries 10 unchanged, a later gate entry read: all checks passed; after A10 alone: 279 lines, all checks
  passed. `sim_tree.py --cases A` (14:52:23-14:53:11): A0 fails only on "manifest: 2 files differ" (the two R7B files),
  A1-A9 pass, A11 newly cited exactly the two R7B files, owners A10 / A11 / A11, G8 without wait. No template line
  starts with `**` except the title; no hedging word and no mention of an author in A11 or F1_RULE.md.
* The class report on the verifier's own output (`f1/review/test_review_f1_class_report.py`, 7 passed, synthetic run
  directories, /tmp only): counts equal `differences.csv`; runs per arm `fl_heuristic` 1 from `runs_recomputed.csv`;
  the analysis columns are separated by metric (`secondary.csv`, `paired_differences.csv`, `per_scenario.csv`,
  `per_ability.csv`); the gaps of S2 and S3.

**Executions on real data** (this review; read only; P1 training-route development outputs; 2026-11-15).
* 14:40-14:42 `sha256sum -c` of `build/R7B/dev/verify_p1_snap_2203_d/SHA256SUMS`, the header lines of its csv files
  and of `build/R7B/dev/agg_snap_2203/runs.csv`, the jobs and arm columns of its `runs_recomputed.csv`.
* 14:43:05-14:43:06 and 14:56:56 `f1/review/review_f1_numbers.py` on `build/R7B/dev/verify_p1_snap_2203_d/` and
  `/tmp/A10A11/r7bfix/verify_p1_rundirs/` (differences.csv, runs_recomputed.csv, cause_plans.csv, plans.csv) and
  `build/R7B/dev/agg_snap_2203/runs.csv`, into `f1/review/review_f1_numbers.json`.
* 14:44-14:46, 14:53-14:55 and 14:56-14:58 one-line reads of cause_plans.csv, differences.csv and
  runs_recomputed.csv of both outputs (console); 14:58 the file sizes of the 271 actor logs (stat only).
* 14:55:40 `f1/f1_class_report.py` on both outputs, into /tmp/A10A11/f1rev/.
* Test runs: 14:50:10-14:50:22 the two test files of the spec and `f1/test_f1_class_report.py` (the 14 P1-0 smoke run
  directories of route 18305; three P1 run directories and `agg_snap_2203/runs.csv`); 14:51:24
  `f1/review/test_review_f1_class_report.py` (synthetic only). Scratch runs without run data: 14:47 `check_a11.py`,
  `line_check.py`; 14:52:23-14:53:11 `sim_tree.py --cases A`.

**Files of this review.** `f1/REVIEW.md`; `f1/review/`: PROGRESS.md, review_f1_numbers.py, review_f1_numbers.json,
test_review_f1_class_report.py, logs/ (four pytest logs). Scratch: /tmp/A10A11/f1rev/ (wrapper, sealed copy, in-memory
simulation texts, dry-run logs; the tree removed). Registration (`registration.py --verify`) at start (14:39) and end
(15:04:46), equal output: seal PROTOCOL.md OK, seal MANIFEST.sha256 OK, "manifest: 2 files differ" on exactly the two
R7B files; PROTOCOL.md ca54d359..., MANIFEST 4bfe7451..., SEAL b8d516d1... (06:43:14), REGISTRATION c0ee0217...,
PIPELINE_STATE.md 73add832... unchanged: no driver re-seal. At the end: the 39 files of item F1A11 hashed at the start
unchanged; nothing under `framelease_v4/`, `registration/`, `p1_driver/`, `amendment_a10/` or `amendment_a11/` newer
than the start; no new `__pycache__` or empty file under `framelease_v4/`; no ALERT, protocol_txn, STOP, PAUSE or
`.PROTOCOL.md.entrytmp` file; phase driver pid 256142 alive. The protocol lock, the drivers, their queues, CARLA and
the GPU were not touched.
