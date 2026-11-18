# Item F1A11: progress (append-only)

Item: write the reporting rule of finding F1 (decision of the coordinating session: the registered `realized.py`
stays unchanged; the registered values are the values of Tables I and II and of the paper; the R7B run after the
analysis freeze reports every difference with cause F1 as a separate class) into the A11 draft, with the P1
development evidence of F1, the executions of the R7B re-review in "Development data", the R7B pins and test counts
(make_a11_spec.py, A11_spec.json), check_a11.py, a line and parser check on a scratch copy (/tmp/A10A11/f1/) with A10
then A11 inserted, f1/F1_RULE.md and RUNBOOK.md Sec. 3. Nothing is applied. Files of this item:
a10r7b/{A11_entry.md, A11_spec.json, make_a11_spec.py, check_a11.py, RUNBOOK.md} and a10r7b/f1/.

- 2026-11-15T14:05:56+0800 START: no earlier f1/PROGRESS.md (directory absent: fresh start). Wrapper
  /tmp/A10A11/f1/p.sh (taskset -c 12-15, nice 19, ionice -c 3, one BLAS thread, CUDA_VISIBLE_DEVICES='', ulimit -v
  1.5 GiB; affinity mask f000 checked). registration.py --verify (4.2 s, 18 MB): seal framelease_v4/PROTOCOL.md OK,
  seal MANIFEST.sha256 OK; manifest: 2 files differ, exactly the two unregistered R7B files
  (verify_table1_extra.py a8bf57b7 -> f77b2dcf, tests/test_verify_table1_extra.py c3bf160c -> f0e74336; RUNBOOK
  Sec. 3, precondition 5). PROTOCOL.md ca54d359 (06:43:14), MANIFEST 4bfe7451, SEAL b8d516d1, REGISTRATION c0ee0217,
  PIPELINE_STATE 73add832, phase baseline cfe58aa1, P1 baseline df4435e1: equal to the end values of fix pass 2
  (11:01): no driver re-seal since. Phase driver pid 256142 alive. Slip: the first inspection commands of this item
  (ls, date, ps, free, nproc, cat, head, sed of the a10r7b and R7B files, 14:04-14:05) ran without the prefix;
  from here on every process runs through p.sh.
- 2026-11-15T14:13:30+0800 READ (all read only): A11_entry.md, A11_spec.json, make_a11_spec.py, check_a11.py,
  RUNBOOK.md (Secs. 0, 3-6), a10r7b/PROGRESS.md, final/A10_entry.md, apply_entry_stream.py (registered set, newly cited
  count), sim_tree.py (options), R7B/A11_input_round1.txt (the A11 text changes of round 1), R7B/rereview/REVIEW.md
  (round 2, Verdict GO, e1220a89 = REVIEW_round2.md; REVIEW_round1.md f7eb872f), the tails of R7B/PROGRESS.md and
  rereview/PROGRESS.md, PROTOCOL Secs. 6.3, 7.2, 9.11-9.13, verify_table1_extra.py docstring and output fields,
  geometry.GTTrack._bracket (inside up to t_last + 1e-9 s), realized.py log_censored rule. R7B files on disk:
  verify_table1_extra.py f77b2dcf (13:15:33), test_verify_table1_extra.py f0e74336 (12:59:21), review/test_review_r7b.py
  63c4359d, rereview/test_rereview_r7b.py b378a152, test_rereview_r7b_round2.py 16473afe. check_a11.py before any change
  (0.13 s, 31 MB): exit 1 (must_equal of both R7B files; newly cited count 0 against the sealed manifest);
  make_a11_spec.py --check: STOP (MUST_EQUAL). Deviation search (find build -name 'PROGRESS*.md' -newermt
  '2026-11-15 01:13' + grep): executions of verify_table1_extra.py on real data only in R7B/PROGRESS.md (attempt 6)
  and rereview/PROGRESS.md (rounds 1 and 2); the other logs cite the files only.
- 2026-11-15T14:13:30+0800 CHECK of the F1 numbers (14:06-14:13, read only; P1 training routes only, no P2 data):
  build/R7B/dev/verify_p1_snap_2203_d/ (sha256sum -c OK): 136 differences, cause F1 26 (runs.csv 25 in 19 runs:
  realized_log_censored_plans 19, realized_conflict_plans 2, realized_misses 2, realized_invalid_ticks 1,
  realized_invalid_tick_ratio 1 in scope 'analysis'; arm_summary.csv fast_only realized_invalid_tick_ratio 1),
  unclassified 110. The analysis-read value: v4p1_fast_only_k1.0_s11_r1792 EIR 0.22815533980582525 (94/412)
  recomputed, 0.20631067961165048 (85/412) in runs.csv: the stated 0.2282 / 0.2063, fast_only route 1792, 19 of the
  180 run directories: CONFIRMED. Per arm (agg_snap_2203/runs.csv protocol_arm): event_triggered 6, fast_only 5,
  fixed_deep 4, fl_heuristic 4, all 19 with analysis_use. cause_plans.csv: F1 40 plans in 19 run dirs (38
  clear/log_censored, 2 conflict/log_censored with a miss here), F3 1; /tmp/A10A11/r7bfix/verify_p1_rundirs (272 dirs):
  F1 47 plans in 26 run dirs, F3 2. Offsets: sample time - last-row time of the F1 plans 1.39e-7 to 1.18e-6 s
  (snapshot), 1.39e-7 to 1.99e-6 s (all 271); capture_s above the 0.05 s grid over all plans.csv rows (56,892 and
  68,977 plans): 7.45e-10 to 2.97e-6 s, median 5.9e-7 s, 98% above 1e-9 s (the re-review's time_offsets.py:
  up to 2.98e-6 s, float32 clock drift 1.49e-8 s per s). FINDING: the stated "3e-7 to 1.1e-6 s" (R7B review S3, a
  sample of capture times) is narrower than the measured range; the A11 text states the measured one.
- 2026-11-15T14:13:30+0800 WRITTEN f1/f1_class_report.py (reference computation of class F1 from one output
  directory of verify_table1_extra.py: counts by cause cross-checked with table1_extra.json, runs per arm from
  runs_recomputed.csv, largest abs_diff per (target, metric, their_field), F1 plans, other causes, release; standard
  library; writes only --out). pyflakes clean, lines <= 120. RUN 14:13:07 (0.03 s, 19 MB) on
  build/R7B/dev/verify_p1_snap_2203_d -> f1/f1_class_dev.json: class F1 26 (analysis 1), 19 runs {event_triggered
  6, fast_only 5, fixed_deep 4, fl_heuristic 4}, largest: runs.csv realized_log_censored_plans 10,
  realized_invalid_ticks 9, realized_conflict_plans 1, realized_misses 1, realized_invalid_tick_ratio 0.021845
  (r1792, scope analysis), arm_summary.csv realized_invalid_tick_ratio 0.000993; other causes: unclassified 110;
  release 'verification failure' (the 110 cross-check and timed-out-run cells). On /tmp/A10A11/r7bfix/verify_p1_rundirs
  -> f1/f1_class_p1_rundirs.json: AGREE, 5,523 comparisons, F1 plans 47 in 26 run dirs.
  Slip: the heredoc append of the three entries above (cat >>, 14:13:40) ran without the prefix; from here on
  PROGRESS.md is appended with the editor (no process).
- 2026-11-15T14:14:12+0800 BACKUPS f1/orig/*.before_f1.* of A11_entry.md (11b4ac48), A11_spec.json (5fc36c01),
  make_a11_spec.py (cbaf546a), check_a11.py (63a420f4), RUNBOOK.md (125a2883): equal to RUNBOOK Sec. 6 (unchanged
  since item a10r7b).
- 2026-11-15T14:15:00+0800 EDIT A11_entry.md (template; written 14:14, 5 follow-up edits): title names the reporting
  rule of F1 and Sec. 6.3; the R7B text changes of build/R7B/A11_input_round1.txt applied (blocks [1]-[11]; [6] with
  "the version under review" for round 1 and 13:21 as the end of the second check_vlin/reconcile run, [9] replaced by
  the F1 rule) and the A11 notes of rereview/REVIEW.md (round-2 Development data sentence; review cells and evidence
  with REVIEW_round1.md and both re-review test files; F3 bullet with the candidate radius and "by more than 1 ms for
  914 of the 7,078 conflict plans" (realized.py measured by the second review; 915 was the emulation's count); F2
  restricted to in-flight commits, decimated logs give differences without a cause; new bullet "Gaps inside a log").
  New: F1 bullet with the measured offsets; bullet "Reporting rule for finding F1 (fixed by this entry)"; bullet
  "Known limitations accepted" (second review S1, S2 not applied); class F1 of the development comparison (per arm,
  largest differences); Development data: "the values were used to check the code and to find F1 and F3, never to
  choose a definition or a tolerance; the reporting rule of F1 was fixed with its P1 size known"; use rule 2 (class
  F1 releases with the registered values; any other difference is a verification failure under A10 use rule 4) and
  use rule 3 (sha256 of the class F1 report and its numbers in the Sec. 13 entry); Scope sentence; Evidence with the
  _d outputs, check_vlin JSONs, mutate_round1.log and f1/{f1_class_report.py, f1_class_dev.json, F1_RULE.md}; "At
  drafting" 87 / 80 and 14 / 2 (f1/logs/). Other content kept.
- 2026-11-15T14:15:24+0800 EDIT make_a11_spec.py: MUST_EQUAL verify_table1_extra.py f77b2dcf...,
  tests/test_verify_table1_extra.py f0e74336... (review/test_review_r7b.py 63c4359d unchanged); docstring (attempt 6,
  the second review of the fixes; the registered set and count of apply_entry_stream.py). pyflakes clean, lines <=
  120. RUN: A11_spec.json written (30dfb776...; diff against the backup: the two must_equal lines only); --check
  "equal to the generated spec", exit 0.
- 2026-11-15T14:16:11+0800 TEST RUN (the spec's two pytest commands as apply_entry_stream.py --tests runs them, logs
  in f1/logs/ instead of amendment_a11/, which this item does not write): test_verify_table1_extra.py 14:15:59-14:16:06
  exit 0, 87 passed, 80 subtests (6.4 s, 68 MB; the 14 P1-0 smoke run directories of route 18305); test_review_r7b.py
  14:16:06-14:16:11 exit 0, 14 passed, 2 subtests (4.9 s, 94 MB; three P1 run directories and agg_snap_2203/runs.csv,
  read only). No new __pycache__ (3 directories, as before) and no new empty file under framelease_v4/.
- 2026-11-15T14:19:21+0800 EDIT check_a11.py (both parts by a python replace script through p.sh, every old text
  found once): the newly cited count mirrors apply_entry_stream.py after --write-manifest (registered at A11 = both
  baselines + sealed-manifest files cited by PROTOCOL.md after A10 + P1 job files; manifest view = sealed sha256 for
  registered files, the disk sha256 for the others; count over the composed PROTOCOL.md after A11), note of the files
  whose sha256 --write-manifest changes; TODO lines rejected (exit 1); RULE_PHRASES (the F1 rule sentences must be in
  the template); evidence pins f1/evidence_a11_sha256.txt (--write-evidence); an application test log older than a
  must_equal file is an open precondition and the fill uses the newest valid copy (application, f1/logs/, logs/);
  --write-sim also under /tmp/A10A11/; docstring. RUNBOOK Sec. 5 item 6 (P1 job files) is resolved by this.
  pyflakes clean, lines <= 120 (one 121-column line fixed at 14:18).
- 2026-11-15T14:19:21+0800 WRITTEN f1/F1_RULE.md (the rule in 7 points, the mechanism with the code references, the
  development evidence, the other causes, the class report after the freeze, the files). A11_entry.md: F1 bullet
  ("a conflict first found there is lost and a clear plan whose horizon ends at that row counts as log-censored";
  "2 conflict plans here, both misses, log-censored there"), Interim looks (route ids in any integral form; bullet
  rewrapped greedily at 120, backtick spans kept whole, 9 -> 8 lines, words unchanged otherwise).
- 2026-11-15T14:19:21+0800 CHECK check_a11.py --write-evidence (0.13 s, 31 MB): f1/evidence_a11_sha256.txt written (19
  files, 2654111c...); checks passed; count 2 (the two R7B files); 3 open: A10 not entered; the two application test
  logs of amendment_a11/ (10:55, 71 passed / 67 subtests on a8bf57b7) older than the R7B files; exit 2.
- 2026-11-15T14:20:46+0800 SIMULATION sim_tree.py --out /tmp/A10A11/f1/sim_tree --cases A (14:19:54-14:20:46, 51.5 s,
  33 MB; tree removed at the end): A0 "tree seal" FAIL only because the tree's copy of the sealed manifest holds
  a8bf57b7 / c3bf160c for the two unregistered R7B files ("manifest: 2 files differ", both seals OK: the project state
  of RUNBOOK Sec. 3, precondition 5; sim_tree.py, not a file of this item, expects "manifest: OK"); A1-A9 PASS: A10
  check and --apply (newly cited the 8 A10 files; new manifest 0fdb720e..., 221 files, with the current R7B sha256),
  seal OK ("manifest: OK"), parsers (analyze_v4.py first cited by A10, G8 no wait); A11 with the real
  rereview/REVIEW.md (linked): check passed, --apply sealed, newly cited exactly the two R7B files, manifest unchanged
  (0fdb720e...), seal OK, parsers (owners A10 / A11 / A11, G8 no wait), diff 550 lines. The tree's A11 shows
  "71 passed, 67 subtests" from the copied stale application logs: the reason for the open precondition above.
- 2026-11-15T14:22:13+0800 WRITTEN f1/line_check.py (added lines of a composed PROTOCOL.md: widths, driver forms,
  headings, titles, TODO / placeholders; anchor and Sec. 13.2 heading once; both parsers, entries unchanged, every
  amendment still read, a later gate entry read); pyflakes clean after removing an unused import (sed through p.sh,
  then the blank line removed with the editor). CHECK on scratch copies: /tmp/A10A11/f1/PROTOCOL.sealed.md (= project
  ca54d359); check_a11.py --protocol that copy --write-sim /tmp/A10A11/f1/sim: checks passed, 3 open, exit 2;
  line_check.py: tree after A10 + A11 and in-memory after A11: 531 added or changed lines, 24 table rows, 13 lines over
  120 columns, all table rows, titles A10 and A11, phase driver amendments A1-A11, later gate entry read, P1 entries
  10: all checks passed; in-memory after A10: 279 lines, 9 over 120 (table rows), title A10: all checks passed. (The
  after-gate text holds check_a11's own gate entry; line_check inserts the same gate again, so that output was
  discarded.) Evidence copied to f1/sim_output/ (17 files, incl. the simulated PROTOCOL as .md.txt).
- 2026-11-15T14:25:01+0800 WRITTEN f1/test_f1_class_report.py (7 cases on synthetic verification outputs in /tmp:
  mixed causes with runs per arm, columns with metric, F1 plans, other causes and release; class F1 only with abs_diff
  formed from the values; AGREE; counts not equal to table1_extra.json -> exit 2; a missing input -> exit 2; --out and
  the refusal under framelease_v4/ (nothing created); an unmapped job). TEST RUN 14:25:00-14:25:01: 7 passed (0.3 s,
  37 MB; f1/logs/pytest_f1_class_report.log); pyflakes clean on the three f1 scripts, lines <= 120; no __pycache__.
  A11_entry.md Evidence: the tests of the class report cited by sha256 (27 placeholders). F1_RULE.md: the clock-offset
  measurement attributed to the review of the fixes (time_offsets.py, 12:05; it read "the second review"), one
  bullet rewrapped (a 160-column line), F3 bullet "no difference in the development comparison", files list (tests,
  line_check.py, sim_output/).
- 2026-11-15T14:25:28+0800 CHECK check_a11.py --write-evidence: f1/evidence_a11_sha256.txt (20 files); check_a11.py:
  checks passed, count 2, 3 open (A10; the two stale application logs), exit 2; sha256sum -c of the evidence list OK;
  make_a11_spec.py --check equal.
- 2026-11-15T14:26:31+0800 SIMULATION rerun with the final template: sim_tree.py --cases A (14:25:41-14:26:30, 49.2 s,
  33 MB): as at 14:20 (A0 FAIL on the two unregistered R7B files only; A1-A9 PASS; A10 newly cited 8, A11 newly cited
  exactly the two R7B files; seals OK; owners A10 / A11 / A11; G8 no wait; diff 552 lines). The scratch copy of
  PROTOCOL.md still equal to the project's; check_a11.py --protocol <copy> --write-sim /tmp/A10A11/f1/sim: checks
  passed, 3 open, exit 2. line_check.py: tree after A10 + A11 and in-memory after A11: 533 added or changed lines (24
  table rows, 13 over 120 columns, all table rows), titles A10, A11: all checks passed; in-memory after A10: 279
  lines: all checks passed. f1/sim_output/ refreshed (18 files).
- 2026-11-15T14:28:00+0800 EDIT RUNBOOK.md (python replace script through p.sh, each old text found once; the
  paragraph texts written to /tmp/A10A11/f1/runbook_sec3.md first): Sec. 3 replaced (pins f77b2dcf / f0e74336; the
  F1 rule and its P1 size; precondition 2 done, with the procedure for a further R7B change; precondition 3 to 14:13
  and the search from 14:30; precondition 4 with 87 / 80 and 14 / 2, the required --tests run, the open and problem
  lists of check_a11.py and f1/evidence_a11_sha256.txt; precondition 5: "manifest: OK" after A10; after G8 the class
  report command and the release reading; the dry run of this item); header (item F1A11; state: review GO, F1 rule);
  Sec. 4 last paragraph; Sec. 5 items 1, 2 (F1 decided; open: F3 / F1+F3 as verification failures, the cross-check
  columns, the offset range) and 6 (resolved); Sec. 6 header and the rows of the four changed files, 10 rows of f1/
  files; the backups paragraph rewritten and rewrapped. Sec. 1 (A10, precondition 2): a note that sha256sum -c of
  evidence_sha256.txt (item a10r7b, not a file of this item) reports exactly the two R7B files FAILED since R7B
  attempt 6 (lines 29-38 are the A11 evidence of attempt 5), expected; any other FAILED line is a problem. Prose
  widths <= 120 (only the copied python one-liner of line 123 and table rows exceed).
- 2026-11-15T14:28:27+0800 FINAL CHECKS (read only): check_a11.py exit 2 (open: A10 not entered; the two application
  test logs of 10:55 older than the R7B files; no problem); make_a11_spec.py --check equal; sha256sum -c
  f1/evidence_a11_sha256.txt OK; sha256sum -c a10r7b/evidence_sha256.txt: exactly verify_table1_extra.py and its test
  FAILED (attempt-5 pins; RUNBOOK Sec. 1 note); apply_entry_stream.py check mode on the project: A11 STOP "in-place
  text found 0 times" (A10 not entered; 6.3 s, 19 MB), A10 "check: pre-checks passed" (6.4 s, 19 MB);
  check_drafts.py "all checks passed", exit 0; pyflakes clean on f1/*.py, make_a11_spec.py, check_a11.py.
- 2026-11-15T14:29:42+0800 END: registration.py --verify (14:29:25, 3.2 s, 18 MB): seal framelease_v4/PROTOCOL.md OK,
  seal MANIFEST.sha256 OK; manifest: 2 files differ, exactly the two unregistered R7B files (as at the start).
  PROTOCOL.md ca54d359 (06:43:14), MANIFEST 4bfe7451, SEAL b8d516d1 (06:43:14), REGISTRATION c0ee0217,
  PIPELINE_STATE 73add832, phase baseline cfe58aa1, P1 baseline df4435e1: equal to the start; no driver re-seal
  during the item. Newer than the start reference outside f1/: only A11_entry.md, A11_spec.json, make_a11_spec.py,
  check_a11.py, RUNBOOK.md (this item) and phase_driver/state.json (the driver). No ALERT, protocol_txn, STOP or
  PAUSE file of either driver; no .PROTOCOL.md.entrytmp; no new __pycache__ or empty file under framelease_v4/; phase
  driver pid 256142 alive. Final sha256: A11_entry.md 9fc737ac..., A11_spec.json 30dfb776..., make_a11_spec.py
  3776e06d..., check_a11.py 6f5029ee..., RUNBOOK.md 62bac8c2... (before the last RUNBOOK edit of 14:28 the RUNBOOK
  table row values were taken; RUNBOOK.md is in no table), F1_RULE.md 067532ac..., evidence_a11_sha256.txt 8fe5bf48....
  Not written: PROTOCOL.md, registration/, the seal, PIPELINE_STATE.md, every registered file, the drivers'
  directories and queues, amendment_a10/ and amendment_a11/, evidence_sha256.txt, sim_tree.py and the other files
  of item a10r7b outside the five of this item. The protocol lock, the drivers, CARLA and the GPU were not touched;
  every python, pytest, sha256sum, find, cp and simulation process ran through p.sh (taskset 12-15, nice 19, ionice
  3, one BLAS thread, CUDA hidden, ulimit -v 1.5 GiB), one at a time; max RSS 94 MB (review tests). Slips: the first
  inspection commands (14:04-14:05) and one heredoc append (14:13:40) without the prefix. Scratch: /tmp/A10A11/f1/
  (1.6 MB: p.sh, logs of the dry runs, the sealed copy, the in-memory texts; trees removed).
- 2026-11-15T14:30:30+0800 CORRECTION of the parenthesis on RUNBOOK.md in the END entry: RUNBOOK.md is in no sha256
  table; its Sec. 6 rows were all checked after the last edit: the 34 rows parsed from Sec. 6, sha256sum -c, all OK.
- 2026-11-15T14:31:32+0800 PROBE of the new checks of check_a11.py in memory (module loaded from its path; texts
  altered in memory only, the probe list under /tmp removed): a TODO line -> "line 202 holds a TODO"; one F1 rule
  sentence altered -> "the template lacks the F1 rule text"; evidence list missing -> reported; a changed sha256 and
  an extra file -> both reported; a cited file not listed -> reported; the fill takes the f1/logs/ copies (the
  application logs are stale); open items: A10 and the two stale logs. FINDING of the probe: the evidence messages used
  Path.relative_to(ROOT) and raised for a list outside the root; EDIT check_a11.py: helper shown() (relative where
  possible). pyflakes clean, lines <= 120. check_a11.py: exit 2, the same 3 open items, no problem. check_a11.py
  sha256 1e157544... (was 6f5029ee... at the END entry); RUNBOOK Sec. 6 row updated (sed through p.sh), 34 rows
  sha256sum -c OK; RUNBOOK.md a1ecba8b....
- 2026-11-15T14:37:51+0800 END (final): registration.py --verify: seal framelease_v4/PROTOCOL.md OK, seal
  MANIFEST.sha256 OK, manifest: 2 files differ (exactly the two unregistered R7B files, as at the start); PROTOCOL.md
  ca54d359 (06:43:14), MANIFEST 4bfe7451, SEAL b8d516d1: no driver re-seal during the item. Nothing under
  framelease_v4/, registration/, amendment_a10/ or amendment_a11/ newer than the start; no new __pycache__ or empty
  file; no ALERT or protocol_txn file of either driver.

## Fix pass 1 (review f1/REVIEW.md, 9e2f2eab..., Verdict GO_WITH_FIXES: must-fix M1-M3, should-fix S1-S7)

- 2026-11-15T15:08:55+0800 START of fix pass 1: this PROGRESS.md read first (item ended 14:37:51, complete).
  Wrapper /tmp/A10A11/f1fix1/p.sh, called under `taskset -c 12-15 nice -n 19 ionice -c 3` (one BLAS thread, CUDA
  hidden, ulimit -v 1.5 GiB, refuses unless the affinity mask is f000). registration.py --verify (3.2 s, 18 MB): seal
  framelease_v4/PROTOCOL.md OK, seal MANIFEST.sha256 OK, manifest: 2 files differ, exactly the two unregistered R7B
  files (a8bf57b7 -> f77b2dcf, c3bf160c -> f0e74336). PROTOCOL.md ca54d359 (06:43:14), MANIFEST 4bfe7451, SEAL
  b8d516d1, REGISTRATION c0ee0217, PIPELINE_STATE 73add832, phase baseline cfe58aa1, P1 baseline df4435e1: equal to
  the item's end; no driver re-seal. Phase driver pid 256142 alive; no ALERT, protocol_txn, STOP, PAUSE or entrytmp
  file. The item files equal the reviewed versions (A11_entry 9fc737ac, A11_spec 30dfb776, make_a11_spec 3776e06d,
  check_a11 1e157544, RUNBOOK a1ecba8b, F1_RULE 067532ac, f1_class_report 3ef60e91, its test 6e5f4fe1, f1_class_dev
  741a035c, evidence 8fe5bf48; REVIEW.md 9e2f2eab). Slip: the first reads of this pass (ls, cat of the PROGRESS,
  REVIEW, review files and the five item files, 15:06-15:08) ran without the prefix; from here on every process runs
  through the wrapper.
- 2026-11-15T15:10:30+0800 READ (read only, the reviewed code and texts): apply_entry_stream.py (--tests mode: pytest
  -q -p no:cacheprovider -rA from the root; pre-check: every test log of the spec exists and passes; must_equal),
  sim_tree.py (the tree copies amendment_a11/ from the project), verify_table1_extra.py (SHA256SUMS over the four
  data files and plans.csv, written last; comparisons.differences, differences_by_cause, agree_within_bounds_by_cause;
  verdict AGREE exactly without a difference; status 'final' or 'development'; runs_recomputed.csv
  gpu_inflight_boundaries), build/R7B/PROGRESS.md 13:12:40 and rereview/REVIEW.md (route 2086: the misses, R_cond and
  R_cond without V = 0 agree within the bounds that plan 209:9 in the 1e-3 s band gives and equal the F3 values;
  EIR by F2). BACKUPS f1/orig/*.before_fix1.* of the eleven files this pass changes (the five a10r7b files and
  F1_RULE.md, f1_class_report.py, test_f1_class_report.py, f1_class_dev.json, f1_class_p1_rundirs.json,
  evidence_a11_sha256.txt), equal to the reviewed sha256 (slip: one `ls f1/orig/` before them without the prefix).
- 2026-11-15T15:15:32+0800 EDIT f1/f1_class_report.py (S2, S3; 3ef60e91 -> bfa88965, schema f1_class/2): the four
  inputs must be listed in the directory's SHA256SUMS at their sha256 (exit 2 otherwise; SHA256SUMS missing: exit 2);
  table1_extra.json comparisons.differences must equal the rows and its verdict be AGREE exactly without a row;
  per column rows_without_abs_diff (class F1 rows with a side empty or not a number) and class_F1
  differences_without_abs_diff; agree_within_bounds_by_cause copied and class_F1 agree_within_bounds (its F1
  count); 'outcome' (AGREE / class F1 only / verification failure) always, 'release' = outcome for status 'final',
  else 'not final'; --out refused inside VERIFY_OUT, under framelease_v4/ or on a directory. EDIT
  f1/test_f1_class_report.py (6e5f4fe1 -> dea097a8): SHA256SUMS written by the fixture; new cases (release only for
  'final', one side empty counted, counts and verdict against differences.csv, inputs against SHA256SUMS, --out
  refusals with the directory unchanged) and class OnVerifierOutput (the outputs verify_table1_extra.py f77b2dcf
  writes for a synthetic F1 case built with its own test fixtures: counts, runs per arm, analysis columns by metric,
  per_scenario.csv r_cond with one side empty: abs_diff null and rows_without_abs_diff 1, an altered copy refused).
  TEST RUNS (pyflakes clean, lines <= 120): 15:14:51 1 failed, 14 passed (--out equal to VERIFY_OUT: the report
  wrote VERIFY_OUT.tmp next to it and os.replace failed; the file /tmp/f1_class_test_l9xu_cfp.tmp removed): fixed
  (inside() includes the directory itself; a directory as --out refused); 15:15:13 14 passed, 10 subtests; 15:15:26
  with the metric case: 15 passed, 10 subtests (0.6 s, 62 MB); no leftovers under /tmp.
- 2026-11-15T15:17:30+0800 Slip: the append of the two entries above (cat >> with a heredoc, 15:15:40) ran without
  the prefix; from here on PROGRESS.md is appended through the wrapper (tee -a).
- 2026-11-15T15:17:30+0800 WRITTEN f1/fix1_numbers.py (recount of the numbers that the review corrected; standard
  library; checks each input against the directory's SHA256SUMS; writes only --out). REAL DATA (read only; P1
  training routes, development outputs; no test route, no P2 data): 15:16:25-15:16:26 fix1_numbers.py (0.75 s, 21 MB)
  on build/R7B/dev/verify_p1_snap_2203_d/ (differences.csv, runs_recomputed.csv, plans.csv) and
  /tmp/A10A11/r7bfix/verify_p1_rundirs/ (runs_recomputed.csv, plans.csv) -> f1/fix1_numbers.json. CONFIRMED (M1):
  110 differences without a cause = the timed-out job v4p1_fl_heuristic_B0_d10_k1.0_s11_r23659 with 39 runs.csv
  cells and 2 runner result fields (41) + the cross-check columns gpu_usage_recomputed 31, gpu_busy_recomputed_s 31,
  commits 7 (69 cells) in 31 runs (31 jobs), each with in-flight GPU boundaries, and 31 of the 180 runs have such
  boundaries; 7 of the 69 on three other route-23659 jobs (fixed_deep 2, event_triggered_v2_hb2.0 3, hb1.0 2).
  CONFIRMED (S4): capture offsets above the grid median 5.91e-7 s (snapshot, 56,892 plans) and 5.70e-7 s (272 run
  directories, 68,977 plans); min 7.45e-10, max 2.97e-6, none below the grid. S5: runs with unevaluable plans 8 on the
  snapshot (all 8 with log-censored bounds wider than a point, e.g. route 23659 [6, 13]) and 14 of the 272 (13 with
  such bounds). 15:16:44 f1_class_report.py (new version bfa88965; 0.04 s, 19 MB) on both outputs -> f1/f1_class_dev.json
  and f1/f1_class_p1_rundirs.json: every class F1 number equal to the version before (26 differences, 1 analysis, 19
  runs: event_triggered 6, fast_only 5, fixed_deep 4, fl_heuristic 4; largest differences 10, 9, 1, 1, 0.021845,
  0.000993; plans 40 in 19 run dirs), rows without an absolute difference 0, agree_within_bounds_by_cause {F3: 3}
  (route 2086), class F1 agreements within bounds 0, sha256sums OK; outcome 'verification failure', release 'not
  final' (status development); the 272 directories: AGREE, release 'not final'.

## Fix pass 2 (review f1/REVIEW.md 9e2f2eab: M1-M3, S1 as decided by the coordinating session, S2-S7)

- 2026-11-15T23:33:17+0800 START of fix pass 2: this PROGRESS.md and f1/REVIEW.md read first. Fix pass 1 ended
  without an END entry: its last entry is 15:17:30, and A11_entry.md changed at 15:18 (21b817f2, reviewed 9fc737ac)
  without an entry: the M3 sentence (and a sentence on the reads of fix pass 1, 15:16), S2 in the rule bullet
  ("the number of its differences without one", "after checking its inputs against the directory's SHA256SUMS"; one
  line of 126 columns), S5 ("no P1 value is changed by them"), "each of the 26 has an absolute difference". Done in
  fix pass 1 (entries above): S2 and S3 in f1_class_report.py (bfa88965) and its test (dea097a8), fix1_numbers.py /
  .json, f1_class_dev.json 6576fd9f, f1_class_p1_rundirs.json 85fade8a. Not done: M1, M2, S1, S4, S6, S7, the
  F1_RULE.md and RUNBOOK edits, --write-evidence. Wrapper /tmp/A10A11/f1fix/p.sh (called under `taskset -c 12-15
  nice -n 19 ionice -c 3`; one BLAS thread, CUDA hidden, PYTHONDONTWRITEBYTECODE, ulimit -v 1.5 GiB, refuses unless
  the affinity mask is f000). registration.py --verify (23:33:17, 3.4 s, 18 MB): "manifest: OK", seal
  framelease_v4/PROTOCOL.md OK, seal MANIFEST.sha256 OK, exit 0. PROTOCOL.md 3fa337c1 (23:30:57; holds A10 at line
  2990, 20:15, and A12 at line 3251, 23:30), MANIFEST 0fdb720e (221 files), SEAL 577f1c6a, REGISTRATION 6d309f94,
  PIPELINE_STATE 43d6cbe5. amendment_a10/ holds the A10 application (apply.out, attempt_20261115T201534_601055);
  amendment_a11/ only the two test logs of 10:55. phase_driver/STOP present, no driver process; no ALERT,
  protocol_txn or .PROTOCOL.md.entrytmp file. Slip: the first two commands of this pass (ls and wc of the item
  files, 23:32) ran without the prefix; from here on every process runs through the wrapper.
- 2026-11-15T23:41:10+0800 READ (read only): f1/REVIEW.md, f1/review/{PROGRESS.md, test_review_f1_class_report.py},
  fix1_numbers.json, the five item files, F1_RULE.md, f1_class_report.py and its test; PROTOCOL.md (A10 use rule 4 and
  deviation 9; A12 entry: Table I on 14 of the 44 test routes, 98 of 308 Table I jobs, 127 of 632 P4-P6 jobs; one
  b11_ti_main job timed out twice, v4p4_fl_original_k1.0_s11_r23658); verify_table1_extra.py (docstring, _gpu_intervals,
  recompute_run GPU bounds, validity_run plan status 'no_plan_logged', RUNS_CSV_MAP, compare_run, the cause test
  _classify / value_agrees); metrics_v4.py (gpu_usage from summary.json gpu_busy_ratio, else gpu_usage_recomputed;
  gpu_busy_recomputed_s / gpu_usage_recomputed from jobs.jsonl and job_start events without the steps of a job still
  running; commits from the committed_depths of jobs.jsonl); analyze_v4.py (Metric table: gpu_usage reads runs.csv
  gpu_usage; commits read only by no_log_run, H5, for commit-audit status NO_LOG = neither jobs.jsonl nor events.jsonl);
  figures_tables.py (no runs.csv read; "accepted commits" from the commit-audit document). No analysis file reads
  gpu_usage_recomputed or gpu_busy_recomputed_s. BACKUPS f1/orig/*.before_fix2.* of the eleven files this pass changes
  (A11_entry 21b817f2, A11_spec 30dfb776, make_a11_spec 3776e06d, check_a11 1e157544, RUNBOOK a1ecba8b, F1_RULE
  067532ac, f1_class_report bfa88965, its test dea097a8, f1_class_dev 6576fd9f, f1_class_p1_rundirs 85fade8a,
  evidence 8fe5bf48).
- 2026-11-15T23:41:10+0800 REAL DATA (read only; P1 training-route development outputs, no test route, no P2 data):
  23:36:43 sha256sum -c of build/R7B/dev/verify_p1_snap_2203_d/SHA256SUMS and /tmp/A10A11/r7bfix/verify_p1_rundirs/
  SHA256SUMS (5 OK each); 23:37 scratch probe /tmp/A10A11/f1fix/inflight_probe.py and one python -c read of
  differences.csv and runs_recomputed.csv of the snapshot (console): the 69 cross-check cells lie in the 31 runs with
  in-flight GPU boundaries; every GPU cell has the registered value below the recomputed lower bound; each of the 7
  commits cells differs by exactly plans_by_status 'no_plan_logged' (checks empty); the 41 cells of the timed-out job
  (scope 'record', theirs empty, analysis_use false).
- 2026-11-15T23:41:10+0800 EDIT f1/f1_class_report.py (S1; bfa88965 -> cf3074f6, schema f1_class/3): every row of
  differences.csv is assigned to class F1 (cause 'F1'), class F3 (cause 'F3' or 'F1+F3'), class in_flight (no cause,
  runs.csv, scope 'record', column gpu_usage_recomputed / gpu_busy_recomputed_s / commits of a run that ended with a
  job in flight: GPU: in-flight boundaries >= 1, registered below the recomputed lower bound, no difference in that
  key's runs.csv gpu_usage and gpu_busy_in_span_s; commits: recomputed minus registered equal to the commits of jobs
  without a jobs.jsonl row, >= 1) or unexplained; per class the counts (all, analysis), runs per arm and the largest
  absolute difference per column; outcome 'AGREE' / 'pre-specified classes only' / 'verification failure'. pyflakes
  clean, lines <= 120. RUN 23:39:46 (0.05 s, 19 MB each) into /tmp/A10A11/f1fix/{dev,rundirs}.json: snapshot F1 26,
  F3 0, in_flight 69 (31 runs: event_triggered 8, fast_only 2, fixed_deep 11, fl_heuristic 9, fl_original 1; 0 in
  scope 'analysis'), unexplained 41 (the timed-out job); runs ending with a job in flight 31 of 180; the 272 run
  directories: AGREE, 36 of 272 runs ending with a job in flight. Every class F1 number unchanged.
- 2026-11-15T23:41:10+0800 EDIT f1/test_f1_class_report.py (dea097a8 -> 45d29581): the synthetic runs_recomputed.csv
  carries the in-flight fields; the mixed case expects class F3 1 and unexplained 1; 'pre-specified classes only'.
  The tests of the new classes follow. (The session was interrupted once by an API error after this edit; the work
  continues from the saved files.)
- 2026-11-15T23:42:20+0800 EDIT f1/test_f1_class_report.py (45d29581 -> e05af6fd): new cases class F3 (causes F3 and
  F1+F3, by cause, agreements within bounds, plans), InFlightClass (the three columns of a run ending with a job in
  flight; 12 subtests, one per condition that leaves a row unexplained: no job in flight, registered within the lower
  bound, registered above, the analysis-read gpu_usage differs, the runtime busy time differs, scope 'analysis', a
  cause, commits off by more than the in-flight commits, a logged job's commit without its step, one side empty,
  another column, an unmapped job) and OnVerifierOutputInFlight (the verifier's own fixture run ending with job 3 in
  flight plus one commit of job 3, runs.csv with the aggregator's values: class in_flight 3 rows, 'pre-specified
  classes only'; with runs.csv gpu_usage at the cross-check value: gpu_usage (scope 'analysis') and the two GPU
  cross-check rows unexplained, commits in_flight, 'verification failure'). TEST RUNS 23:41:57 21 passed, 22 subtests
  (one line of 121 columns fixed); 23:42:06 21 passed, 22 subtests (0.7 s, 64 MB); pyflakes clean, lines <= 120; no
  /tmp/f1_class_* left, no new __pycache__ or empty file under framelease_v4/.
- 2026-11-15T23:42:20+0800 REAL DATA (read only; P1 training-route development outputs): f1_class_report.py cf3074f6
  on build/R7B/dev/verify_p1_snap_2203_d/ -> f1/f1_class_dev.json (79f8e945; class_F1 identical to the version before)
  and on /tmp/A10A11/r7bfix/verify_p1_rundirs/ -> f1/f1_class_p1_rundirs.json (99948cdc). Expected rates (python -c,
  no data read): F1 26/271 = 9.6% -> 9.4 of the 98 Table I runs of the A12 cut, a condition mean over 14 routes holds
  an F1 route with probability 0.756 (0.988 over 44); jobs in flight 31/180 = 17.2% and 36/272 = 13.2% -> 16.9 / 13.0
  of 98 (21.9 / 16.8 of the 127 queue_p4 runs); F3 outside the 1e-3 s band 1/271 -> 0.36 plans in 98 runs (at least
  one with probability 0.30), 0.47 in 127; a timed-out run without aggregator values 1/180 -> 0.54 in 98 (A12 already
  records one timeout).
- 2026-11-15T23:45:00+0800 READ (read only, P1 development aggregation): one python -c read of the runs.csv row of job
  v4p1_fl_heuristic_B0_d10_k1.0_s11_r23659 in build/R7B/dev/agg_snap_2203/ (23:43:22: outcome 'sim_failure',
  missing_reason 'sim_failure', selected_run set, run_dir and every metric empty) and aggregate_v4.py job_row: a row
  whose outcome is not 'ok' returns before run_fields, so it carries no metric. FINDING: a timed-out or crashed job
  of the final aggregation gives differences without a cause whenever its runner record names a run directory (P1:
  41, scope 'record'); A12 records one such Table I job (v4p4_fl_original_k1.0_s11_r23658, timeout twice). No class
  covers it (open for the coordinating session).
- 2026-11-15T23:45:00+0800 WRITTEN f1/F1_RULE.md (067532ac -> new; S1, M1, S2, S3, S4): the rule in 8 points with the
  three classes by mechanism (F1; F3 = 'F3' or 'F1+F3'; in-flight with its conditions), the report numbers per class,
  failure for any difference without a class; Sec. 2 the mechanisms (F1 with the medians 5.9e-7 / 5.7e-7 s and the
  1 ms row match as the recomputation's own convention; F3; jobs in flight with what analyze_v4.py and
  figures_tables.py read); Sec. 3 the development numbers per class and the M1 split (31 / 31 / 7 in 31 runs; 39 + 2
  of the timed-out run); Sec. 4 the expected rates under A12; Sec. 5 the differences without a class (candidate
  radius, F2 / gaps, a job whose outcome is not 'ok', with the A12 timeout); Sec. 6 the class-report command with the
  sha256 check first; Sec. 7 files. Prose lines <= 120 (table rows excepted); no TODO, no hedging word.
- 2026-11-15T23:46:40+0800 EDIT A11_entry.md (python replace script through the wrapper, each old text found once):
  title "the reporting rule of its differences"; Cause bullet; "Development data": the classes fixed with their P1
  sizes known, the reads of fix pass 2 (23:36-23:47) after those of 15:16, the broken line "The definitions" rejoined
  (M3 sentence of fix pass 1 kept); "Development comparison": the split of the 110 (69 in 31 runs; 41 of the timed-out
  run, outcome 'sim_failure', its runs.csv row without metric) and the classes of the comparison with the rates for
  the final run (F1_RULE.md Sec. 4); Findings closing sentence; the bullet "Reporting rule for the differences" with
  the classes F1, F3 ('F3' or 'F1+F3') and in-flight by mechanism (with what the analysis reads) and failure for a
  difference that no class explains (the 126-column line of fix pass 1 gone); use rules 2 and 3 (three classes, the
  class report at its cited sha256); Scope; Evidence (the tests of the class report: the third test); Tests: third
  bullet pytest_f1_class_report.log, "At drafting" 21 passed and 22 subtests. One template line of 126 columns
  rewrapped with the editor. Prose lines <= 120 (template).
- 2026-11-15T23:46:40+0800 EDIT make_a11_spec.py (S6): third test (amendment_a11/pytest_f1_class_report.log, argv
  f1/test_f1_class_report.py), MUST_EQUAL f1_class_report.py cf3074f6 and test_f1_class_report.py e05af6fd, docstring.
  pyflakes clean, lines <= 120. RUN 23:45:21: A11_spec.json written (f9ade8e1; diff against the backup: the third test
  and the two must_equal lines); --check equal, exit 0.
- 2026-11-15T23:46:40+0800 EDIT check_a11.py: RULE_PHRASES of the new bullet (11 sentences); the simulated later gate
  entry is the first phase-driver gate not entered yet (G3 was entered at 20:13, so the fixed G3 line raised "two Sec.
  13.2 entries for G3"; now G8 'Analysis freeze'); FAKE_DATETIME 2026-11-16 01:00 (after A12); docstring. RUN
  23:45:35 exit 1 (four evidence pins, the G3 alert); 23:46:17 exit 1 (only the four evidence pins of the files this
  pass changed: --write-evidence pending); one docstring line of 149 columns rewrapped. pyflakes clean.
- 2026-11-15T23:47:40+0800 READ (read only): amendment_a10/{console.txt, verify.out, apply.out}: A10 applied 20:15:34-
  20:15:50, apply_locked exit 0; pre-verify "manifest: OK"; manifest difference "new [] / left [] / changed []"; newly
  cited the eight A10 files; the attempt copy of MANIFEST.sha256 is 0fdb720e and holds the R7B files at f77b2dcf /
  f0e74336: the G3 entry (20:13) sealed that manifest, so A10 never met the "2 files differ" state the review
  expected (M2). SEARCH (precondition 3) 23:47:22: find build -name 'PROGRESS*.md' -newermt '2026-11-15 14:13': only
  f1/review/PROGRESS.md and f1/PROGRESS.md (both in "Development data"). CHECK 23:47:30 post_check.py A10 (3.6 s, 30
  MB): "post-check A10: passed", exit 0 (refresh done; G8 analysis_registration without wait).
- 2026-11-15T23:50:00+0800 EDIT RUNBOOK.md (python replace scripts through the wrapper, each old text found once):
  header (fix passes 1 and 2; the state at 23:47: A10 applied 20:15, A12 23:30, PROTOCOL 3fa337c1, MANIFEST
  0fdb720e, "manifest: OK", phase driver stopped); Sec. 1 (M2): applied-status paragraph, precondition 1 comment
  'both "seal ...: OK" lines and "manifest: OK"' with a note on the "2 files differ" period 13:15-20:13 (the G3 seal
  recorded the R7B files; never clear it with a seal outside a transaction), expected manifest difference ('changed'
  exactly the two R7B files while they differ, else empty; empty at 20:15); Sec. 3: intro (name A11 kept, in-place
  text found 1x), the rule with the three classes, P1 sizes and expected rates, precondition 1 done (post_check A10
  passed 23:47), precondition 2 (a change of the class report or its test), precondition 3 (S6: the reads up to fix
  pass 2, the search of 23:47:22, -newermt '2026-11-15 23:47'), precondition 4 (three tests; S7: --tests right before
  the application, the applier accepts stale passing logs), precondition 5 (the CURRENT expected verify output and
  what A11's pre-check sees), precondition 6 (check mode after --tests; the STOP before it), deadline (driver stopped
  by A12), "After G8" (S6: sha256 of the class report first; outcomes 'AGREE' / 'pre-specified classes only' /
  'verification failure'; the expected failure of a job whose outcome is not 'ok'); Sec. 4 (simulated gate G8); Sec.
  5 item 2 (M1: 69 of the 110 in 31 runs; open (a) F1+F3 in class F3, (b) the timed-out job of A12) and item 6
  (resolved). Prose lines <= 120 (the copied python one-liner of Sec. 1 excepted).
- 2026-11-15T23:50:00+0800 EDIT f1/line_check.py (29e03516 -> new; backup f1/orig/line_check.before_fix2.py): the
  simulated later gate entry is the first phase-driver gate not entered yet (the fixed G3 line would raise "two Sec.
  13.2 entries for G3" since 20:13). pyflakes clean, lines <= 120.
- 2026-11-15T23:50:00+0800 CHECK check_a11.py --write-evidence (23:49:11): f1/evidence_a11_sha256.txt written (20
  files, 252fb6d9; changed rows: F1_RULE.md f89f3b5c, f1_class_dev.json 79f8e945, f1_class_report.py cf3074f6,
  test_f1_class_report.py e05af6fd); checks passed; count 2 (the two R7B files); --write-manifest changes no sealed
  sha256; later gate entry G8 simulated; 3 open: the two application logs of 10:55 older than a must_equal file, the
  third log (pytest_f1_class_report.log) missing; exit 2.
- 2026-11-15T23:50:00+0800 TEST RUNS (pytest -q -p no:cacheprovider -rA from the root, as apply_entry_stream.py --tests
  runs them; logs in f1/logs/, amendment_a11/ not written): test_verify_table1_extra.py 23:49:19-23:49:25 exit 0, 87
  passed, 80 subtests (6.6 s, 68 MB); test_review_r7b.py 23:49:25-23:49:30 exit 0, 14 passed, 2 subtests (5.2 s, 94
  MB); f1/test_f1_class_report.py 23:49:30-23:49:31 exit 0, 21 passed, 22 subtests (0.8 s, 65 MB). The tests of the
  review, f1/review/test_review_f1_class_report.py (23:49:31-23:49:32, log /tmp/A10A11/f1fix/
  pytest_review_f1_class_report.log): 4 passed, 3 failed, exactly the expected three: test_pinned_versions (the
  report pinned at 3ef60e91, now cf3074f6), test_sha256sums_not_checked_gap (the report now stops: "the inputs do not
  match SHA256SUMS ... differences.csv differs ... table1_extra.json differs"; S3), test_release_ignores_status_gap
  (release 'not final' for status 'development'; S3); the four tests of behaviour (counts, runs per arm, columns by
  metric, the one-side-empty column with abs_diff null) pass. No /tmp test directory left, no new __pycache__ or empty
  file under framelease_v4/.
- 2026-11-15T23:51:00+0800 SCRATCH CHECKS (/tmp/A10A11/f1fix/; with A10 and A12 in the sealed PROTOCOL.md):
  PROTOCOL.sealed.md = project 3fa337c1; 23:50:02 check_a11.py --protocol that copy --write-sim /tmp/A10A11/f1fix/sim:
  checks passed, in-place text 1x, newly cited exactly the two R7B files, --write-manifest changes no sealed sha256,
  G8 entry simulated and read, 3 open (the stale and the missing application logs), exit 2; line_check.py copy
  sim/PROTOCOL.after_A11.md --expect A11: 293 added or changed lines, 4 over 120 columns, all table rows (8), title
  A11 once, 6 phase-driver entries and 10 P1 entries unchanged, amendments A1-A12 read, later gate entry read: "all
  checks passed", exit 0. CHECK MODE apply_entry_stream.py A11_spec.json (23:50:12, 6.1 s, 19 MB): seal verified,
  then "STOP: test log outputs/framelease_v4/amendment_a11/pytest_f1_class_report.log: ''" (exit 1; the third log is
  written by the --tests run before the application); every pre-check before it passed. Scratch spec and template
  with the three logs pointed at the fresh f1/logs/ copies (/tmp/A10A11/f1fix/A11_spec.scratch.json, 23:50:30):
  "check: pre-checks passed", exit 0. make_a11_spec.py --check equal; sha256sum -c f1/evidence_a11_sha256.txt OK.
- 2026-11-15T23:51:00+0800 EDIT RUNBOOK.md: Sec. 3 precondition 6 (the check-mode results above) and the paragraph
  "Checks of fix pass 2"; Sec. 6 header as a sentence, 18 rows updated (the files of this pass, f1/logs/, the four
  amendment_a10/ logs as the A10 application wrote them) and 2 rows added (fix1_numbers.py / .json); backups
  paragraph (before_fix1, before_fix2). The 36 rows: sha256sum -c OK. Prose lines <= 120 (the python one-liner of
  Sec. 1 excepted); no hedging word.
- 2026-11-15T23:51:35+0800 END of fix pass 2: check_a11.py exit 2 (checks passed; open: the two application logs of
  10:55 older than a must_equal file, the third log missing); pyflakes clean on check_a11.py, make_a11_spec.py,
  f1_class_report.py, its test and line_check.py; evidence OK; spec equal. registration.py --verify (23:51:35, 3.5 s,
  18 MB): "manifest: OK", seal framelease_v4/PROTOCOL.md OK, seal MANIFEST.sha256 OK, exit 0; PROTOCOL.md 3fa337c1,
  MANIFEST 0fdb720e, SEAL 577f1c6a, REGISTRATION 6d309f94, PIPELINE_STATE 43d6cbe5 (23:32:57, before the start of
  this pass): equal to the start. Nothing under framelease_v4/ (other than PIPELINE_STATE.md, written before the
  start), registration/, amendment_a10/, amendment_a11/ or p1_driver/ newer than the start; no new __pycache__ or
  empty file under framelease_v4/; no ALERT, protocol_txn or .PROTOCOL.md.entrytmp file; no /tmp test directory
  left. Final sha256: A11_entry.md 02f041d5, A11_spec.json f9ade8e1, make_a11_spec.py 8888fbee, check_a11.py
  b0e55879, RUNBOOK.md 9c94b2aa, F1_RULE.md f89f3b5c, f1_class_report.py cf3074f6, test_f1_class_report.py
  e05af6fd, f1_class_dev.json 79f8e945, f1_class_p1_rundirs.json 99948cdc, evidence_a11_sha256.txt 252fb6d9,
  line_check.py 565c2674. Not written: PROTOCOL.md, registration/, the seal, PIPELINE_STATE.md, every registered
  file, the drivers' directories and queues, amendment_a10/, amendment_a11/, the review files in f1/review/. The
  protocol lock, the drivers, CARLA and the GPU were not touched; every process after the first two ran through the
  wrapper (taskset 12-15, nice 19, ionice 3, one BLAS thread, CUDA hidden, ulimit -v 1.5 GiB), one at a time; max
  RSS 94 MB (test_review_r7b.py). Scratch: /tmp/A10A11/f1fix/ (1.4 MB). Open for the coordinating session: (a)
  'F1+F3' in class F3 (confirm or remove before the application); (b) no class covers a job whose outcome is not
  'ok' (A12's timed-out Table I job gives a predictable verification failure); then apply_entry_stream.py
  A11_spec.json --tests right before the application, check_a11.py exit 0, check mode "pre-checks passed".

## Fix pass 2, part b (decisions of the coordinating session: class "not-ok record" added; 'F1+F3' in class F3 confirmed)

- 2026-11-15T23:56:00+0800 READ (read only): verify_table1_extra.py load_runner_records (job -> its last final 'end'
  record, else its last 'end' record), compare_all (runs.csv rows not used: note "row not used by the analysis
  (analysis_use false)", scope 'record'; runner result rows: note "runner outcome ..."), the 'inputs' of
  table1_extra.json (every status.jsonl of --queue and runs.csv / arm_summary.csv of --agg with their sha256; paths
  relative to the project root, else absolute), runs_csv_run_dir (run_dir, else selected_run); its test
  test_runner_records (status.jsonl format). The verifier's four outputs do not carry the runner outcome of a job:
  the class report reads the runner records and runs.csv that table1_extra.json 'inputs' names, each at its recorded
  sha256. 23:53:22 one python -c read of the keys of table1_extra.json of the snapshot output (P1 development).
  BACKUPS f1/orig/{f1_class_report,test_f1_class_report}.before_fix2b.py (cf3074f6, e05af6fd).
- 2026-11-15T23:56:10+0800 CORRECTION: the READ entry above is stamped 23:56:00; it was written at 23:54 (clock read
  wrong by hand). EDIT f1/f1_class_report.py (cf3074f6 -> 4c7f3af5; schema f1_class/3 kept): class not_ok_record = a
  row without a cause, scope 'record', target runs.csv or runner result, registered side empty, of a job whose final
  runner outcome (its last final 'end' record, else its last 'end' record, as load_runner_records) is not 'ok' and
  whose runs.csv row has analysis_use false; the runner records and runs.csv are read only when such a row exists,
  from table1_extra.json 'inputs' at the recorded sha256 (else exit 2), and their sha256 enter inputs_sha256; report
  per class as the others plus the jobs with their outcome and the sources; outcome 'pre-specified classes only'
  includes it. pyflakes clean, lines <= 120 (one comment of 121 columns shortened with sed). REAL DATA (read only,
  P1 development): 23:54:28 f1_class_report.py on the snapshot output (it read
  build/R7B/dev/p1_snap_2203/status.jsonl 3d8164ad and build/R7B/dev/agg_snap_2203/runs.csv 9ee8c078, both equal to
  the recorded sha256) and on the 272 directories, into /tmp/A10A11/f1fix/{dev2,rundirs2}.json: snapshot F1 26, F3 0,
  in_flight 69, not_ok_record 41 (job v4p1_fl_heuristic_B0_d10_k1.0_s11_r23659, outcome 'timeout', fl_heuristic, 40
  columns, all 41 without an absolute difference), unexplained 0, outcome 'pre-specified classes only'; 272: AGREE.
- 2026-11-15T23:56:10+0800 EDIT f1/test_f1_class_report.py (e05af6fd -> f26ffb38): NotOkRecordClass (3 rows of a
  timed-out job; the final-record rule; 7 subtests for each condition: final outcome ok, analysis_use true, a
  non-empty registered value, scope 'analysis', no runner record, another target, a cause; the recorded inputs: a
  sha256 that differs or a missing file -> exit 2, no inputs -> unexplained); OnVerifierOutputNotOk (the verifier's
  fixture run without summary.json, a final runner record 'timeout' without result values and a runs.csv row as
  job_row writes it: every difference in not_ok_record, 'pre-specified classes only'; final outcome 'ok' ->
  'verification failure'; runs.csv ticks 999 -> that row unexplained); the earlier class counts gain not_ok_record 0
  (5 asserts rewrapped). TEST RUNS 23:55:34 5 failed (the earlier asserts without the new key), 23:55:54 26 passed, 31
  subtests (0.6 s); no /tmp test directory left. REAL DATA 23:56:04: the report 4c7f3af5 on both P1 outputs into
  f1/f1_class_dev.json (f0344500) and f1/f1_class_p1_rundirs.json (750387ed); numbers as at 23:54:28.
- 2026-11-15T23:59:30+0800 EDIT f1/F1_RULE.md (f89f3b5c -> 4c7384d3; backup orig/F1_RULE.before_fix2b.md): four
  classes; rule 3 class not-ok record with its conditions and sources; rule 5 "one of the four classes"; new Sec. 2.4
  (the mechanism: job_row returns before run_fields for an outcome other than 'ok', the runner reports no result
  values, the verifier recomputes the run of the final runner record; analyze_v4.py uses a cell only through a row with
  analysis_use and valid_record 1, read in its docstring and cell code); Sec. 3 table (class not-ok record 41, without a
  class 0, outcome 'pre-specified classes only'); Sec. 4 row not-ok record (1 of 180; A12's timeout); Sec. 5 (a
  non-empty value, scope 'analysis' or analysis_use true stays without a class); Sec. 6 (the recorded inputs read);
  Sec. 7 (26 passed, 31 subtests). EDIT A11_entry.md (backup orig/A11_entry.before_fix2b.md): the class not-ok record
  bullet, "one of four classes", use rule 2 "one of the four classes", the class in the development comparison and
  the rates (A12's timed-out job), "At drafting" 26 passed and 31 subtests. EDIT check_a11.py: RULE_PHRASES (four
  classes; the two sentences of class not-ok record). EDIT make_a11_spec.py: MUST_EQUAL f1_class_report.py 4c7f3af5,
  test_f1_class_report.py f26ffb38. EDIT RUNBOOK.md (backup orig/RUNBOOK.before_fix2b.md): header, Sec. 3 rule
  paragraph and expected occurrences, precondition 4 counts, "After G8" (the recorded inputs read by the report), Sec.
  5 item 2 (both decisions recorded; the open items removed). Prose lines <= 120 in all (RUNBOOK one-liner excepted).
- 2026-11-16T00:00:28+0800 CORRECTION: the EDIT entry above stamped 23:59:30 was written at 23:57-23:58 (stamp written by hand); stamps
  from here on come from date.
- 2026-11-16T00:00:28+0800 RERUNS of fix pass 2, part b (logs in f1/logs/ and /tmp/A10A11/f1fix/): make_a11_spec.py 23:58:04 (A11_spec.json
  71323aad; diff: the two MUST_EQUAL sha256 of the class report and its test), --check equal; check_a11.py
  --write-evidence 23:58:04 (f1/evidence_a11_sha256.txt 6184bd8e, 20 files; checks passed, count 2, 3 open, exit 2),
  sha256sum -c OK. TESTS: test_verify_table1_extra.py 23:58:15-23:58:21 exit 0, 87 passed, 80 subtests (6.7 s, 68
  MB); test_review_r7b.py 23:58:21-23:58:27 exit 0, 14 passed, 2 subtests (5.1 s, 94 MB); f1/test_f1_class_report.py
  23:58:27 exit 0, 26 passed, 31 subtests (0.9 s, 66 MB); f1/review/test_review_f1_class_report.py 23:58:27: 4
  passed, 3 failed, the same expected three (the pin of the report, the two gaps that S3 closed). SCRATCH 23:58:35:
  check_a11.py --protocol PROTOCOL.sealed.md (= 3fa337c1) --write-sim: checks passed, exit 2 (3 open);
  line_check.py after A11: 302 lines, all checks passed. (A line_check run on sim/PROTOCOL.after_gate.md, 23:58:35,
  reported the simulated G8 line of check_a11 as an added driver entry and no further gate to simulate: that text
  already holds the simulated gate entry; not a check, discarded.) CHECK MODE 23:58:36 on A11_spec.json: STOP at the
  missing test log pytest_f1_class_report.log (exit 1, 6.7 s, 19 MB); 23:58:52 on the temporary spec (three logs
  pointed at f1/logs/): "check: pre-checks passed", exit 0.
- 2026-11-16T00:00:28+0800 EDIT A11_entry.md "Development data": the reads of fix pass 2 are 23:36-23:57 and include the runner records
  build/R7B/dev/p1_snap_2203/status.jsonl and build/R7B/dev/agg_snap_2203/runs.csv (read by f1_class_report.py) and
  table1_extra.json. SEARCH 23:59:08 (find -newermt '2026-11-15 23:47'): f1/PROGRESS.md and build/G8CUT/PROGRESS.md
  (no match of the search terms; content not read). RERUN after that edit: check_a11.py 23:59:18 exit 2 (checks
  passed; the 3 open items); scratch check_a11.py exit 2, 297 lines; line_check.py after A11: 303 added or changed
  lines, 4 over 120 columns (table rows), title A11 once, 6 phase-driver and 10 P1 entries unchanged, A1-A12 read,
  later gate entry read, "all checks passed"; check mode on A11_spec.json 23:59:18: the same STOP; on the temporary
  spec 23:59:25: "check: pre-checks passed"; make_a11_spec.py --check equal; evidence OK.
- 2026-11-16T00:00:28+0800 EDIT RUNBOOK.md: precondition 3 (reads to 23:57, searches 23:47:22 and 23:59:08, -newermt '2026-11-15 23:59'),
  precondition 6 and "Checks of fix pass 2" with the times and counts of these reruns; Sec. 6: 13 rows refreshed
  (A11_entry db3729c2, A11_spec 71323aad, make_a11_spec ee1603e2, check_a11 ed87abb7, F1_RULE 4c7384d3,
  f1_class_report 4c7f3af5, its test f26ffb38, f1_class_dev f0344500, f1_class_p1_rundirs 750387ed, evidence 6184bd8e,
  the three f1/logs), its header sentence rewrapped; 36 rows sha256sum -c OK. RUNBOOK.md 7c7a771f.
- 2026-11-16T00:00:28+0800 END of fix pass 2 (part b): registration.py --verify 00:00:13 (3.2 s, 18 MB): "manifest: OK", both seals OK, exit
  0; PROTOCOL.md 3fa337c1, MANIFEST 0fdb720e, SEAL 577f1c6a, REGISTRATION 6d309f94, PIPELINE_STATE 43d6cbe5: equal to
  the start of fix pass 2. Nothing under framelease_v4/, registration/, amendment_a10/, amendment_a11/ or p1_driver/
  newer than the start; no new __pycache__ or empty file under framelease_v4/; no ALERT, protocol_txn or
  .PROTOCOL.md.entrytmp file; no /tmp test directory left. The protocol lock, the drivers, CARLA and the GPU were not
  touched; one process at a time through the wrapper; max RSS 94 MB. Open before the application: the coordinating
  session runs apply_entry_stream.py A11_spec.json --tests right before it (87/80, 14/2, 26/31 expected), then
  check_a11.py exit 0 and check mode "pre-checks passed".

## Fix pass 3 (round-2 review f1/review/REVIEW_round2.md dd465845, GO_WITH_FIXES: must-fix M1, M2; should-fix S1-S5)

- 2026-11-16T00:20:17+0800 START: f1/review/REVIEW_round2.md and r2_test_adversarial.py read (read only). registration.py --verify
  (00:20:00): "manifest: OK", both seals OK, exit 0; PROTOCOL.md 3fa337c1, MANIFEST 0fdb720e, SEAL 577f1c6a,
  PIPELINE_STATE 43d6cbe5: equal to the end of fix pass 2. The item files equal the reviewed versions (A11_entry
  db3729c2, A11_spec 71323aad, make_a11_spec ee1603e2, check_a11 ed87abb7, RUNBOOK 7c7a771f, F1_RULE 4c7384d3,
  f1_class_report 4c7f3af5, its test f26ffb38, evidence 6184bd8e). READ framelease_v2/gpu_queue.py (grep: status events
  runner_start / start / end / invalid_line / runner_exit; the STOP file of a queue ends the runner after its current
  job and writes runner_exit; OK_OUTCOMES = ('ok', 'result_with_warnings')). BACKUPS f1/orig/*.before_fix3.* of the
  eleven files this pass changes.
- 2026-11-16T00:21:53+0800 EDIT f1/f1_class_report.py (4c7f3af5 -> f53e21f8). M1: class not_ok_record requires in addition the job's
  runs.csv outcome present and other than 'ok' (job_row returns before run_fields exactly then) and its final runner
  outcome present and not in RUNNER_OK = ('ok', 'result_with_warnings'); runs_csv_rows gives (analysis_use, outcome);
  the class reports per job runner_outcome and runs_csv_outcome. S1: class in_flight requires
  gpu_inflight_boundaries >= 1 for commits as well; the docstring states that for the GPU columns the class tests the
  boundaries and the direction, not the size. S3: release = outcome only when status 'final', script_sha256 equal to
  REGISTERED_VERIFIER (f77b2dcf, the verifier A11 registers) and options.runs_csv_values false; release_checks states
  each. pyflakes clean, lines <= 120. EDIT f1/test_f1_class_report.py (f26ffb38 -> 79c67568): the synthetic outputs
  carry script_sha256 and options; test_release_requires_the_registered_verifier (4 subtests); in-flight subtest
  'commits in a run without in-flight boundaries'; not-ok subtests: the review's two counter-examples inverted (runner
  'result_with_warnings' or a final record without an outcome, runs.csv outcome 'ok'), the same with runs.csv outcome
  'sim_failure', runner 'timeout' with runs.csv outcome 'ok' or empty: all unexplained; the jobs field with both
  outcomes; OnVerifierOutputNotOk.test_valid_run_dropped_by_a_failed_metric_step (runner 'result_with_warnings' or
  'ok', runs.csv outcome 'ok', run_dir set, missing_reason 'no_metrics', metrics empty: no row in not_ok_record,
  'verification failure'). TEST RUNS 00:21:23 28 passed, 44 subtests (one 122-column line rewrapped), 00:21:41 28
  passed, 44 subtests (0.6 s); no /tmp test directory left. REAL DATA (read only, P1 development) 00:20:48 into
  /tmp/A10A11/f1fix/{dev3,rundirs3}.json and 00:21:42 into f1/f1_class_dev.json (bedca68a) and
  f1/f1_class_p1_rundirs.json (61fe0cda): numbers unchanged (F1 26, F3 0, in_flight 69 in 31 runs, not_ok_record 41,
  job v4p1_fl_heuristic_B0_d10_k1.0_s11_r23659 runner 'timeout' / runs.csv 'sim_failure', unexplained 0; 272: AGREE);
  release_checks: status_final false (development), registered_verifier true, runs_csv_values_false true.
- 2026-11-16T00:24:44+0800 EDIT A11_entry.md: Cause bullet (S2: the review of the reporting rule and its second round with their verdicts
  and applied items; S5c: "and F2, inside the bounds"); "Development data" (M2: the sentence of the second review,
  verbatim, and one for the reruns of fix pass 3, 00:20-00:22); "P1 rates behind the expected sizes of the final run"
  (S5b); Findings closing sentence (S5a, as the review words it); class in-flight (S1: commits needs in-flight
  boundaries; the limitation of the GPU columns stated); class not-ok record (M1: failure outcome, not 'ok' or
  'result_with_warnings', runs.csv outcome other than 'ok'; a valid run whose metric step failed is outside); both
  class bullets rewrapped greedily at 120 (backtick spans whole); use rule 1 (S3: release only by the registered
  verifier without --runs-csv-values); Evidence (S2: f1/REVIEW.md and f1/review/REVIEW_round2.md by sha256); "At
  drafting (2026-11-16)": 28 passed and 44 subtests. EDIT check_a11.py RULE_PHRASES (the new not-ok sentence, the
  sentence on the metric-step failure, the in-flight limitation). EDIT f1/F1_RULE.md (-> 190a6761): rule 3 (in-flight
  commits with boundaries and the size limitation; not-ok record with both outcomes), Sec. 2.4 (OK outcomes of the
  runner; job_row returns exactly when the aggregator outcome is not 'ok'; the valid run with a failed metric step is
  outside the class), Sec. 5 (the metric-step case; the size limitation of class in-flight), Sec. 6 (release checks;
  the runner of each queue read has exited first), Sec. 7 (28 passed, 44 subtests); select_stage.py read (outcomes
  agent_crashed / sim_failure / pending, OK_OUTCOMES). SEARCH 00:24:06 (-newermt '2026-11-16 00:00'):
  f1/review/PROGRESS.md, f1/PROGRESS.md, build/G8CUT/PROGRESS.md; the one matching line of the last (00:03:43, step 2)
  read: a read of the command-line interfaces (verify_table1_extra among them), no execution; nothing else of that
  file read. EDIT RUNBOOK.md: header (fix pass 3); Sec. 3 rule paragraph (M1), precondition 2 (the fix-pass-3 change
  of the class report needs its review before the application; REGISTERED_VERIFIER changes with the verifier),
  precondition 3 (M2: the second review and fix pass 3; search from 2026-11-16 00:24), precondition 4 (28 / 44),
  "After G8" (S4: write queue_p4/STOP once every kept job is final and wait for the 'runner_exit' record before the
  verification; S3: release_checks), Sec. 5 item 2 (M1; the open review). EDIT make_a11_spec.py MUST_EQUAL:
  f1_class_report.py f53e21f8, test_f1_class_report.py 79c67568. pyflakes clean on check_a11.py, make_a11_spec.py.
- 2026-11-16T00:26:37+0800 RERUNS of fix pass 3: make_a11_spec.py 00:24:44 (A11_spec.json 3dc04684; the two MUST_EQUAL sha256 of the class
  report and its test), --check equal; check_a11.py --write-evidence 00:24:44 (f1/evidence_a11_sha256.txt 86602b3f, 22
  files: F1_RULE.md, f1_class_dev.json, f1_class_report.py, test_f1_class_report.py changed; f1/REVIEW.md 9e2f2eab and
  f1/review/REVIEW_round2.md dd465845 added; 315 lines, 31 placeholders; checks passed; 3 open; exit 2); sha256sum -c
  OK. TESTS (logs f1/logs/): test_verify_table1_extra.py 00:24:54-00:25:01 exit 0, 87 passed, 80 subtests (7.1 s, 69
  MB); test_review_r7b.py 00:25:01-00:25:06 exit 0, 14 passed, 2 subtests (5.3 s, 94 MB); f1/test_f1_class_report.py
  00:25:06-00:25:07 exit 0, 28 passed, 44 subtests (1.0 s, 66 MB). Review tests (logs /tmp/A10A11/f1fix/):
  f1/review/test_review_f1_class_report.py 00:25:07 4 passed, 3 failed (the pin, the two round-1 S3 gaps);
  f1/review/r2_test_adversarial.py 00:25:08 9 passed, 18 subtests, 4 failed: test_valid_run_dropped_by_a_failed_
  metric_step_gap and the two subtests of test_not_ok_record_with_an_ok_runner_outcome_gap (M1 closed: 0 rows in
  not_ok_record), and test_analysis_read_values_without_a_class_holds (outcome 'verification failure' as asserted;
  release 'not final' instead of 'verification failure' because its synthetic table1_extra.json names no verifier
  sha256: S3); the two S1 gap tests pass (the stated limitation). SCRATCH 00:25:29 (PROTOCOL.sealed.md = 3fa337c1):
  check_a11.py --protocol --write-sim: checks passed, 3 open, exit 2; line_check.py after A11: 321 added or changed
  lines, 4 over 120 columns (table rows), title A11 once, 6 phase-driver and 10 P1 entries unchanged, A1-A12 read, a
  later gate entry read, "all checks passed". CHECK MODE 00:25:30 on A11_spec.json: STOP at the missing
  pytest_f1_class_report.log (exit 1, 6.5 s, 19 MB; every pre-check before it passed); 00:25:36 on the temporary spec
  (logs pointed at f1/logs/): "check: pre-checks passed", exit 0. check_a11.py (project): checks passed, exit 2.
  EDIT RUNBOOK.md: precondition 6 times, the paragraph "Checks of fix pass 3" (with the review tests), Sec. 6: 13 rows
  refreshed, header "fix pass 3 (2026-11-16 00:26)"; 36 rows sha256sum -c OK; RUNBOOK.md 820c91a1.
- 2026-11-16T00:26:37+0800 END of fix pass 3: registration.py --verify 00:26:22: "manifest: OK", both seals OK, exit 0; PROTOCOL.md
  3fa337c1, MANIFEST 0fdb720e, SEAL 577f1c6a, REGISTRATION 6d309f94, PIPELINE_STATE 43d6cbe5: unchanged. Nothing under
  framelease_v4/, registration/, amendment_a10/, amendment_a11/ or p1_driver/ newer than the start; no new
  __pycache__ or empty file; no ALERT, protocol_txn or .PROTOCOL.md.entrytmp file; no /tmp test directory left. Final
  sha256: A11_entry.md a1db8524, A11_spec.json 3dc04684, make_a11_spec.py 3ec26961, check_a11.py e1db7a5f, RUNBOOK.md
  820c91a1, F1_RULE.md 190a6761, f1_class_report.py f53e21f8, test_f1_class_report.py 79c67568, f1_class_dev.json
  bedca68a, f1_class_p1_rundirs.json 61fe0cda, evidence_a11_sha256.txt 86602b3f. Open: a review (verdict GO) of the
  fix-pass-3 change of f1_class_report.py and its test (RUNBOOK Sec. 3, precondition 2); then --tests right before the
  application, check_a11.py exit 0, check mode "pre-checks passed".

## Fix pass 4 (round 3 GO, f1/review/REVIEW_round3.md 973d59ef; the fifth class decided after the G8 dry run)

- 2026-11-16T00:38:23+0800 START. READ (read only): f1/review/REVIEW_round3.md (Verdict GO; should-fix N1; housekeeping),
  build/G8CUT/DRYRUN.md (cc3ee4f6) and build/G8CUT/RUNBOOK.md (170894ea; Sec. 1 item 7 and Sec. 11 open point 1, the
  P_both pairing: 76 = 14 x 3 + 13 x 2 + 2 x 4 rows in the dry run), the registered code: verify_table1_extra.py
  (AGE_RULE_ARMS, LEASE_ARMS, SHIELD_ARMS = LEASE_ARMS without fl_original, p_both None outside SHIELD_ARMS,
  ANALYSIS_METRICS, compare_paired_differences: 'paired' / 'status' row with note "status '<analysis status>'", the
  values compared only when both sides are paired), analyze_v4.py (paired: drop reason '<column> missing: <conditions>'
  with value_a, value_b and difference None; ROUTE_COLUMNS). The dry-run outputs of the scratch tree (synthetic run
  directories, /tmp/G8CUT/root/; read: the 76 paired_differences.csv rows of differences.csv, the 'inputs' keys,
  status and options of table1_extra.json, two rows of the tree's analysis paired_differences.csv); the tree's
  queue_p4 and analysis are real directories of the tree, no link to the project. Slip: one stray "python3 -c 1"
  (system python, no -I) ran inside a read command at 00:36; it read nothing. registration.py --verify (00:38:07):
  "manifest: OK", both seals OK, exit 0. BACKUPS f1/orig/*.before_fix4.* of the eleven files this pass changes.
- 2026-11-16T00:39:54+0800 EDIT f1/f1_class_report.py: class undefined_metric_pairing (UNDEFINED_METRICS = {'p_both': column 'p_both',
  arms fixed_deep, fast_only, event_triggered, fl_original}, the arms outside the verifier's SHIELD_ARMS): a row
  without a cause, paired_differences.csv, field 'paired' / their_field 'status', ours 'True', theirs 'False', the note
  exactly "status '<column> missing: <conditions>'" with the metric's column, every condition an arm of the list, no
  value_a / value_b / difference row of the key in differences.csv, the analysis row (read from the
  paired_differences.csv that table1_extra.json 'inputs' records, at its sha256, only when a candidate exists) with
  that status and empty values, every recomputed run of each named arm (at least one) without the metric; reported by
  metric and arm and by contrast. N1: runner_outcomes stops (exit 2) when a job id has 'end' records in more than one
  recorded status.jsonl. recorded_files generalizes the recorded-input check. pyflakes clean, lines <= 120 (three
  long lines rewrapped). REAL DATA (read only, P1 development) 00:39:31: the report on both P1 outputs into
  /tmp/A10A11/f1fix/{dev4,rundirs4}.json: snapshot F1 26, F3 0, in_flight 69, not_ok_record 41,
  undefined_metric_pairing 0, unexplained 0; 272: AGREE. Neither P1 output holds a paired_differences.csv row (grep:
  0 and 0; those verification runs had no --analysis). DRY RUN (synthetic, the scratch tree of build/G8CUT/DRYRUN.md):
  a copy of the report with ROOT set to /tmp/G8CUT/root (the one changed line, diff checked) on
  /tmp/G8CUT/root/.../final_20261116T002530_table1_extra, 00:39:41: 116 differences = not_ok_record 40 (job
  v4p4_fl_original_k1.0_s11_r23658, runner 'timeout', runs.csv 'sim_failure') + undefined_metric_pairing 76 (p_both:
  event_triggered 14, fast_only 18, fixed_deep 18, fl_original 26; 9 secondary contrasts 14 / 14 / 14 / 13 / 13 / 2 /
  2 / 2 / 2), unexplained 0; outcome and release (status final in the tree, registered verifier) 'pre-specified
  classes only'.
- 2026-11-16T00:41:41+0800 EDIT f1/test_f1_class_report.py (79c67568 -> b2d3388c): runs_recomputed fields with p_both;
  UndefinedMetricPairingClass: test_arms_and_metric_from_the_registered_code (UNDEFINED_METRICS against the
  verifier's AGE_RULE_ARMS, LEASE_ARMS, SHIELD_ARMS and ANALYSIS_METRICS; recompute_run of the fixture run gives p_both
  None exactly for those arms), test_dry_run_case (the 76 rows of the dry run, 9 contrasts: all in the class, by arm
  14 / 18 / 18 / 26, 'pre-specified classes only'), test_each_condition_is_required (13 subtests: two conditions without
  a shield in the class; the metric defined for the arm, one of two conditions with a shield, a metric defined for
  every arm, a numeric value that differs, a value in the analysis row, the analysis row absent, another analysis
  status, a note with more text, a column other than the metric's, a condition that does not parse, the reversed
  pairing: unexplained; a cause: class F1), test_recomputed_runs_of_the_arm (a run of the arm with the metric, no run
  of the arm: unexplained), test_recorded_analysis_file (not recorded: unexplained; sha256 differs: exit 2);
  NotOkRecordClass.test_job_in_two_recorded_queues_stops (N1); the earlier class counts gain undefined_metric_pairing
  0 (long lines rewrapped). TEST RUNS 00:40:47 failed (the earlier counts without the new key), 00:41:19 34 passed, 59
  subtests (0.7 s); no /tmp test directory left. REAL DATA (read only, P1 development) 00:41:31: f1_class_report.py
  ac82d65a on both outputs into f1/f1_class_dev.json (22ceb51f) and f1/f1_class_p1_rundirs.json (60aeeece): classes
  F1, F3, in_flight, not_ok_record and unexplained equal to the version before (26 / 0 / 69 / 41 / 0), class
  undefined_metric_pairing 0; 272: AGREE.
- 2026-11-16T00:44:27+0800 EDIT A11_entry.md (backup orig/A11_entry.before_fix4.md): Cause bullet (round 3 GO, N1 applied, the fifth class
  by the decision of the coordinating session); "Development data" (fix-pass reads 00:20-00:22 and 00:39-00:42);
  "Development comparison" (class undefined-metric pairing none; the expected 76 at the A12 scale from the G8 dry run,
  14 x 3 + 13 x 2 + 2 x 4); the reporting rule "one of five classes" and the bullet of class undefined-metric pairing;
  use rule 2 "one of the five classes"; Evidence (REVIEW_round3.md by sha256; the three reviews listed as a series);
  "At drafting" 34 passed and 59 subtests. The bullets Cause, Development data and Development comparison rewrapped
  greedily at 120 with backtick spans whole (/tmp/A10A11/f1fix/rewrap.py): the two short lines of round 3 are gone;
  word-level diff against the backup checked (only the edits above). EDIT check_a11.py RULE_PHRASES (five classes;
  the first sentence and the closing sentence of the new bullet). EDIT make_a11_spec.py MUST_EQUAL f1_class_report.py
  ac82d65a, test_f1_class_report.py b2d3388c. EDIT f1/F1_RULE.md: title, rule 3 (five classes; the new class with its
  conditions), rule 5, Sec. 2.5 (the mechanism from the registered code), Sec. 3 (class undefined-metric pairing 0 on
  P1), Sec. 4 (about 76 at the A12 scale; the dry-run check of 00:39:41), Sec. 6 (the recorded analysis file; N1),
  Sec. 7 (34 / 59). EDIT RUNBOOK.md: header (round 3, fix pass 4), Sec. 3 rule paragraph and expected sizes,
  precondition 2 (fix pass 3 reviewed GO by round 3: closed; the fix-pass-4 change needs its review), precondition 4
  (34 / 59), Sec. 5 item 2 (the fifth class decided; the open review), rewrapped. Prose lines <= 120 in all
  (RUNBOOK one-liner excepted); pyflakes clean on check_a11.py and make_a11_spec.py.
- 2026-11-16T00:46:29+0800 RERUNS of fix pass 4: make_a11_spec.py 00:44:27 (A11_spec.json bba16198; the two MUST_EQUAL sha256), --check
  equal; check_a11.py --write-evidence 00:44:27 (f1/evidence_a11_sha256.txt ec80acac, 23 files: F1_RULE.md 5feda06a,
  f1_class_dev.json 22ceb51f, f1_class_report.py ac82d65a, test_f1_class_report.py b2d3388c, REVIEW_round3.md 973d59ef
  added; 331 lines, 32 placeholders; checks passed; 3 open; exit 2); sha256sum -c OK. TESTS (logs f1/logs/):
  test_verify_table1_extra.py 00:44:37-00:44:43 exit 0, 87 passed, 80 subtests (6.8 s, 69 MB); test_review_r7b.py
  00:44:43-00:44:48 exit 0, 14 passed, 2 subtests (5.0 s, 94 MB); f1/test_f1_class_report.py 00:44:49-00:44:50 exit 0,
  34 passed, 59 subtests (1.0 s, 67 MB). Review tests (logs /tmp/A10A11/f1fix/): round 1 4 passed, 3 failed (pin, two
  S3 gaps); r2_test_adversarial.py 8 passed, 16 subtests, 7 failed: the three round-2 M1 gap cases, the S3 holds case,
  and three dict comparisons that lack the new key undefined_metric_pairing (test_in_flight_run_where_the_analysis_
  value_differs_holds x 2, test_in_flight_cross_check_of_any_size_gap); with the key removed from the report output
  (/tmp/A10A11/f1fix/r2_without_new_key.py, 00:45:15, wraps R.report and asserts the removed value is 0): 11 tests, 4
  failures, exactly those of fix pass 3; r3_test_new.py 5 passed, 22 subtests, 1 failed:
  test_two_queues_read_in_another_order_gap (SystemExit "job ids with 'end' records in more than one recorded
  status.jsonl ... ['job1']": N1 closed). SCRATCH 00:45:28 (PROTOCOL.sealed.md = 3fa337c1): check_a11.py --protocol
  --write-sim: checks passed, 3 open, exit 2; line_check.py after A11: 337 added or changed lines, 4 over 120 columns
  (table rows), title A11 once, 6 phase-driver and 10 P1 entries unchanged, A1-A12 read, later gate entry read, "all
  checks passed". CHECK MODE 00:45:28 on A11_spec.json: STOP at the missing pytest_f1_class_report.log (exit 1, 6.4 s,
  19 MB); 00:45:34 on the temporary spec: "check: pre-checks passed", exit 0. check_a11.py (project) exit 2.
  EDIT RUNBOOK.md: precondition 6 times, the paragraph "Checks of fix pass 4" (with every review test and the dry-run
  class report), Sec. 6: 13 rows refreshed, header "fix pass 4 (2026-11-16 00:46)"; 36 rows sha256sum -c OK.
- 2026-11-16T00:46:29+0800 END of fix pass 4: registration.py --verify 00:46:04: "manifest: OK", both seals OK, exit 0; PROTOCOL.md
  3fa337c1, MANIFEST 0fdb720e, SEAL 577f1c6a, REGISTRATION 6d309f94 unchanged. PIPELINE_STATE.md is 31c502f2 (mtime
  00:35:47, before the start of this pass at 00:38; not written here). Nothing else under framelease_v4/,
  registration/, amendment_a10/, amendment_a11/ or p1_driver/ newer than the start; no new __pycache__ or empty file;
  no ALERT, protocol_txn or .PROTOCOL.md.entrytmp file; no /tmp test directory left. Final sha256: A11_entry.md
  df2f49b2, A11_spec.json bba16198, make_a11_spec.py a7c85333, check_a11.py 953fbb8a, RUNBOOK.md bf067f77, F1_RULE.md
  5feda06a, f1_class_report.py ac82d65a, test_f1_class_report.py b2d3388c, f1_class_dev.json 22ceb51f,
  f1_class_p1_rundirs.json 60aeeece, evidence_a11_sha256.txt ec80acac. Open: a review (verdict GO) of the fix-pass-4
  change of f1_class_report.py and its test (RUNBOOK Sec. 3, precondition 2); then --tests right before the
  application (87/80, 14/2, 34/59), check_a11.py exit 0, check mode "pre-checks passed".

## Fix pass 5 (round 4 GO, f1/review/REVIEW_round4.md 79b4e6b1; text only, no code change)

- 2026-11-16T00:58:07+0800 START 00:55:37 (REVIEW_round4.md read); registration.py --verify 00:56:01: "manifest: OK", both seals OK, exit 0.
  BACKUPS f1/orig/{A11_entry,RUNBOOK}.before_fix5.md, F1_RULE.before_fix5.md, evidence_a11_sha256.before_fix5.txt.
  EDIT A11_entry.md (df2f49b2 -> b2517571): Cause bullet (fourth round GO; its should-fix N2 not applied, Known
  limitations); S1 "13 x 2 for fl_heuristic and fl_full against fl_original"; S2 in the class bullet "differences.csv
  holds no value_a, value_b or difference row of that route" (for "no value of that route differs"); Known
  limitations: one sentence on N2; Evidence: REVIEW_round4.md by sha256; the Cause, Development comparison and Known
  limitations bullets and the class bullet rewrapped at 120 (word-level diff against the backup: only these edits).
  EDIT f1/F1_RULE.md (5feda06a -> e117ade3): S1 in the Sec. 4 row; Sec. 2.5 the N2 limitation. EDIT RUNBOOK.md: header
  (round 4, fix pass 5), precondition 2 (fix pass 4 reviewed GO by round 4: open item closed), Sec. 5 item 2 (closed;
  N2 recorded as a known limitation: analyze_v4.paired names only the contrast's own conditions, and a wrongly dropped
  pair also changes the contrast row's n, which stays unexplained), precondition 6 and the checks paragraph, Sec. 6
  (3 rows refreshed; 36 rows sha256sum -c OK). No code file changed (check_a11.py 953fbb8a, make_a11_spec.py
  a7c85333, f1_class_report.py ac82d65a, test_f1_class_report.py b2d3388c unchanged).
- 2026-11-16T00:58:07+0800 RERUNS: make_a11_spec.py 00:57:09 (A11_spec.json bba16198, unchanged), --check equal; check_a11.py
  --write-evidence (f1/evidence_a11_sha256.txt 273658ba, 24 files: F1_RULE.md e117ade3, REVIEW_round4.md 79b4e6b1
  added; 338 lines, 33 placeholders; checks passed, 3 open, exit 2); sha256sum -c OK. SCRATCH (PROTOCOL.sealed.md =
  3fa337c1): check_a11.py --protocol --write-sim exit 2, checks passed; line_check.py after A11: 344 added or changed
  lines, 4 over 120 (table rows), A11 once, A1-A12 read, driver entries unchanged, later gate entry read, "all checks
  passed". CHECK MODE 00:57:10 on A11_spec.json: STOP at the missing pytest_f1_class_report.log (exit 1); 00:57:22 on
  the temporary spec: "check: pre-checks passed", exit 0.
- 2026-11-16T00:58:07+0800 END: registration.py --verify 00:57:40: "manifest: OK", both seals OK, exit 0; PROTOCOL.md 3fa337c1, MANIFEST
  0fdb720e, SEAL 577f1c6a, PIPELINE_STATE 31c502f2 unchanged; nothing under framelease_v4/, registration/,
  amendment_a10/, amendment_a11/ or p1_driver/ newer than the start; no new __pycache__ or empty file. Final sha256:
  A11_entry.md b25175716c8a2dbdb0835a7f4f13ff611fc4dda0bf4db2335eb7f7dbf4435a84, A11_spec.json
  bba1619869d0963f3aa5cd8600e7d4cb541fd9d1a9797cb927d29b31863f6122, RUNBOOK.md 072148f3 (before this entry's
  append, no RUNBOOK change after it). Remaining before the application: --tests right before it, check_a11.py exit
  0, check mode "pre-checks passed" (RUNBOOK Sec. 3, preconditions 4-6).
