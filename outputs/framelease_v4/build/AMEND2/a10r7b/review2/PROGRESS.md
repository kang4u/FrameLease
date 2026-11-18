# review2 PROGRESS (adversarial review of the streaming applier, wrapper, post check, A10 entry)

- 2026-11-15 09:19 start; registration.py --verify: manifest OK, seal PROTOCOL.md OK, seal MANIFEST.sha256 OK.
- 09:20-09:40 read RUNBOOK, applier, diff (matches apply_entry.py -> stream: DIFF FILE MATCHES), wrapper, post_check,
  sim_tree, review/REVIEW.md, phase_driver (cycle, gate_g1, ensure_recorded, refresh_baseline, is_strict,
  analysis_registration, citing_amendment), p1_driver (protocol_view, ProtocolLock, precheck_tree), registration.py.
  sha256 of the reviewed files equal the RUNBOOK Sec. 6 table (RUNBOOK itself 75cb4c07).
- 09:40 read-only checks: check_drafts.py exit 0 "all checks passed" (5 x found 1x); derive_inplace5.py --spec exit 0
  "in-place text 5 equals the derived text" (lines 483-486); evidence sha256sum -c exit 0; RUNBOOK precondition-1
  baseline one-liner OK; no driver ALERT/txn file, no entrytmp. Deviation-1 search (-newermt 09:15 and since 00:00):
  no execution of the aggregator or the four A10 files on real data after FILL0 (03:33). Finding 1 = E3 = sealed A3
  departure 6 (PROTOCOL 2370-2373) = commit_audit 7439a4ea null_margin_explained; finding 2: km_driven 0.0 agg_p1,
  0.001 agg_now / agg_snap_2203 (aggregate_v4 ee13c90b, commit_audit 7439a4ea in code_sha256).
- 09:40 candidate findings from reading: (a) p1_jobs/ b04-b09 .stage/.check.json (12 manifest files) are strict for
  both drivers (is_strict prefix) but not registered for the applier; (b) the wrapper leaves an unsealed PROTOCOL.md
  when the lock is released (kill after the write, seal failed), and phase_driver gate_g1 -> ensure_recorded raises
  an ALERT on an unsealed edit at its next cycle; (c) orphan registration.py after a kill of the applier;
  (d) no lock check in --apply; (e) no stamp-order, width or SEC_START check; (f) cited_new uses the entry only.
  To be tested on scratch trees under /tmp/A10A11/applier/.
- 09:33 review2_sim.py written (scratch harness: cases A B P K O L T M); pyflakes clean; first run: case M (smoke, time
  and memory)
- 09:43 run 1 (A B P K O L T; 557 s, max RSS 35 MB): A all EXPECTED (A10 newly 8, A11 newly 2, lock held 0-19.8 s in one
  interval, parsers, G8 no wait, post_check 3 -> 0 after the driver refresh); B all EXPECTED (P1-baseline, phase-only,
  missing, absent-from-manifest, changed/removed before write-manifest, exit 95 after); FINDINGS: P (p1_jobs check.json
  sealed), K3/K4b (unsealed PROTOCOL.md after kill before seal -> driver gate_g1 ALERT), O (orphan registration.py
  rewrote the manifest after the wrapper's decision -> seal CHANGED -> ALERT), L3 (--apply without the lock seals), T2
  (06:30 stamp), T3 (154-col line), T4.10 (### 13.2 Amendments -> both parsers Alert), T5 (empty file registered by the
  driver, 9 vs 8); harness slips: T3 probe 137 cols in the template, T4.7-4.9 expectation too strict (the applier did
  STOP 'filled entry problem', manifest equal) -> fixed; rerun T R S
- 09:48 run 2 (T R S; 226 s, max RSS 33 MB): no UNEXPECTED. T1 EXPECTED (old twice STOP); T2 FINDING (06:30 stamp
  sealed); T3 FINDING (template 112 cols, filled 129, sealed); T4.1-4.6 EXPECTED (template STOP); T4.7-4.9 EXPECTED
  (filled-entry check STOP after write-manifest, manifest equal/restored); T4.10 FINDING (### 13.2 Amendments sealed,
  both parsers Alert); T5 FINDING (empty file: applier 8, driver 9, post_check 0); R FINDING (rerun on the unsealed
  state overwrites the sealed copies, says 'equals the sealed one'); S FINDING (SIGINT to the group before --seal: no
  exit line, unsealed, driver ALERT). Next: proposed wrapper and applier changes in review2/, tested on scratch trees.
- 09:50 proposals written: review2/proposed_apply_entry_stream.py (p1_jobs prefix, lock check, stamp order, widths +
  preview fill, SEC_START, sequential in-place counts, cited-vs-manifest check, cited_new over the composed text =
  template set, drivers' parsers on the composed text, fsync, manifest diff print) and review2/proposed_apply_locked.sh
  (trap '' INT TERM HUP, seal check before copies, per-attempt copies incl. SEAL/REGISTRATION, wait for leftover
  registration.py, re-seal or roll back before the lock is released, exit 93/94); pyflakes clean, bash -n ok; harness
  cases X (proposals) and Y (stale cite, original) added; running X Y
- 09:54 run 3 (Y X; 258 s): Y FINDING (stale cite: exit 95, driver registers 7, not analyze_v4.py); X: harness slip,
  wrapper() bound the original WRAPPER as a default argument, so X3/X4/X8 ran the original wrapper (UNEXPECTED); X1, X2,
  X5, X6, X9-X14 EXPECTED with the proposed applier; X7 (proposed wrapper) EXPECTED. Fixed (script read at call time);
  rerun X C D.
- 09:59 run 4 (C D X; 270 s, max RSS 36 MB): no UNEXPECTED. C EXPECTED (analyze_v4.py registered only by its A10
  citation, changed: A11 check and wrapper STOP); D1-D5 EXPECTED (entrytmp and the 4 driver files: exit 96 / STOP);
  X1-X14 EXPECTED with the proposed applier and wrapper (A10 8 + A11 2 with and without the refresh; p1_jobs STOP; kill
  before seal -> exit 94 sealed, g1 done; orphan -> waited 3 s, RESTORED, g1 done; kill after manifest / in replace ->
  RESTORED; SIGINT ignored -> exit 0; unsealed -> 96; no lock -> STOP; 06:30 -> STOP; long line and ### 13.2 -> check
  STOP; empty file -> STOP; stale cite -> STOP).
- 10:02 REVIEW.md written (verdict GO_WITH_FIXES: M1 unsealed release -> driver ALERT; M2 P1 job files); proposals
  wrapped to 120 columns (cosmetic), diffs regenerated; rerun X to confirm the final proposal files
- 10:07 Z1/Z2 on the unchanged scratch tree of case D (original applier, ROOT line aside): TZ=UTC check mode STOP
  "not Beijing time"; the wrapper called with TZ=UTC stamps 10:07 (Beijing time). Run 5 (X with the final proposal
  files, 236 s, max RSS 36 MB): X1-X14 EXPECTED, no UNEXPECTED step.
- 10:08 END: registration.py --verify "manifest: OK", both seals OK (also after removing /tmp/A10A11/applier, 370 MB of
  scratch, rm -rf --one-file-system, links not followed); PROTOCOL.md ca54d359, MANIFEST 4bfe7451, SEAL b8d516d1,
  REGISTRATION c0ee0217, PIPELINE_STATE 73add832 (mtime 09:19:06, before this review's first command), both
  baselines equal the start values; no driver re-seal; phase driver pid 256142 alive, driver.log unchanged since
  06:48; no ALERT/txn/STOP file; no entrytmp; __pycache__ under framelease_v4 unchanged (3 dirs, 8 files, Nov 10);
  empty files only .protocol.lock and offline/__init__.py. Written: review2/ (PROGRESS, REVIEW, review2_sim.py,
  proposed_apply_entry_stream.py/.diff, proposed_apply_locked.sh/.diff, logs/). Verdict GO_WITH_FIXES (M1, M2).
- 10:09 REVIEW.md final (results.txt note added); widths <= 120, no driver-form line; __pycache__ count under framelease_v4 still 8
- 2026-11-15 11:03 RE-CHECK ROUND 1 start (fix pass 2: apply_entry_stream.py 7d86e576, .diff 8e87f0c2 = diff -u of
  apply_entry.py, apply_locked.sh 1de9b701, post_check.py 7b08460b, sim_tree.py 59b7a83c, RUNBOOK 125a2883; A10_entry
  9790c164, A10_spec b1de9f6a, AMENDMENTS2_DRAFT 03bfb7f4 unchanged since review 2). registration.py --verify 11:03:
  manifest OK, both seals OK. Scratch: /tmp/A10A11/recheck1/.
- 11:13:53 sim_tree.py (59b7a83c, unchanged) started: --out /tmp/A10A11/recheck1/sim_tree, cases ABCDEFGH, one tree at a
  time; output sim_tree_run.out.
- 11:21:45 sim_tree.py ended (11:13:53-11:20:59, 6 min 52 s, max RSS 33 MB): ALL EXPECTED, 43 PASS (A 11, B 1, C 2, D 3,
  E 5, F 2, G 12, H 7), exit 0; the one 'FAIL' text is the expected post_check output inside H5. Simulated PROTOCOL.md
  after A10 and A11 against the project: 413 added lines, no prose line over 120 (max 120), 13 table rows, only the two
  titles read as driver forms, no non-ASCII character. Wrote /tmp/A10A11/recheck1/{inject2.py,holder2.py,recheck_sim.py}
  (own harness).
- 11:28:41 own harness recheck_sim.py (11:21:52-11:27:55, end from the time file, 6 min 3 s, max RSS 33 MB; trees under
  /tmp/A10A11/recheck1/own/, one at a time, removed): 34 PASS, 1 FAIL = finding WD7. E: A10 and A11 through the wrapper
  with a lock-wanting stand-in driver (holder2.py) running: exit 0 both, 26 + 36 lock acquisitions, 0 with a seal
  mismatch; post_check A10 3 -> refresh +8 -> 0, A11 3 -> +2 -> 0; gate_g1 done; analyze_v4.py first cited by A10, G8 no
  wait. KS SIGKILL after --seal: 94 'seal matches'. OS orphan late --seal: waited 3 s, 94. OM RUNBOOK detached form,
  orphan late --write-manifest: waited 7 s, RESTORED, 137. SG INT+TERM+HUP to the session's group: exit 0. KI inner
  shell SIGKILLed: outer prints exit 137 at once, the applier keeps the lock descriptor and seals (observation). CK
  clock 06:30 STOP (check, wrapper), set back at the fill STOP after --write-manifest, equal 06:43 sealed, later G3
  entry 2026-11-16 00:30 STOP. WD 120 ok, 121 STOP, table 150 ok, placeholder 104 -> 121 preview STOP (check and
  wrapper), in-place 121 STOP, 120 ok; WD7 FINDING: an in-place text that starts mid-line produces a 144-column line,
  check mode passes (fragment 56 columns measured). IP old twice STOP, sequential doubling STOP. TL six driver forms
  STOP. LK --apply with the lock held elsewhere STOP (with and without an own unlocked descriptor), under flock sealed.
  RF registered file changed before --write-manifest STOP + RESTORED; after it exit 95.
- 11:29:07 review 2's harness started through /tmp/A10A11/recheck1/rerun2.py: a10r7b/rerun_review2_sim.py (fdb0e3a1)
  loading review2/review2_sim.py (393d8102) unchanged, its LOGS and link directory moved to /tmp/A10A11/recheck1/ (the
  item's review_rerun/ logs untouched); trees under /tmp/A10A11/applier/.
- 11:45:06 review 2's harness ended (11:29:07-11:43:40, 14 min 33 s, max RSS 33 MB; /tmp/A10A11/applier/ removed by it):
  ALL EXPECTED, 74 expectations PASS, 0 FAIL (logs /tmp/A10A11/recheck1/review2_logs/, 132 files). The 14 steps that
  reproduced a defect of review 2 read UNEXPECTED and pass the positive log checks (P2, K3, K4, O1, L3, T2, T3,
  T4.7-4.10, T5, S1, Y1); X1-X14, R2 and K4R EXPECTED; check mode 6.4 s / 18 MB, wrapper 16.2 s / 32 MB, post_check 3.3
  s / 30 MB.
- 11:45:34 console.txt race probe (scratch /tmp/A10A11/recheck1/race/): the RUNBOOK block run in one shell with a
  console.txt of an earlier attempt: 0 of 40 first greps read the earlier exit line (the launched child truncates the
  file first); no finding. Next: the A10 and A11 test suites with logs in /tmp/A10A11/recheck1/tests/.
- 11:47:10 test suites (logs in /tmp/A10A11/recheck1/tests/; project logs untouched; 1 min 25 s, max RSS 230 MB): A10 48
  passed + 107 subtests, 22 passed, 50 passed (422 warnings), 28 passed + 20 subtests; A11 71 passed + 67 subtests, 14
  passed + 2 subtests; every exit 0; the counts equal the project's logs (10:54-10:55) that the entries cite. Next: the
  read-only final checks on the project.
- 11:51:03 final checks (11:47:10, read only, logs in round2/logs/final_checks.out): A10 check mode on the project
  'check: pre-checks passed' (6.4 s, 18.8 MB); check_drafts.py exit 0 'all checks passed' (5 x found 1x);
  derive_inplace5.py --spec exit 0 'in-place text 5 equals the derived text'; evidence sha256sum -c exit 0; RUNBOOK
  precondition 1: no driver ALERT/txn file, no entrytmp, phase baseline OK; precondition 3 search (-newermt 11:05): only
  review2/PROGRESS.md, whose lines after 11:03 record no execution of the aggregator or of the four A10 files on real
  data (scratch trees, drivers' parsers, the applier on scratch trees, test suites with logs in /tmp); the 9 reviewed
  files unchanged; PROTOCOL ca54d359, MANIFEST 4bfe7451, SEAL b8d516d1, REGISTRATION c0ee0217, PIPELINE_STATE 73add832,
  P1 baseline df4435e1, phase baseline cfe58aa1 as at the start; phase driver pid 256142 alive; no ALERT/txn/STOP/PAUSE;
  __pycache__ 3 dirs 8 files; empty files only .protocol.lock and offline/__init__.py; nothing under framelease_v4/
  newer than 11:03; registration --verify OK. Wrote review2/REVIEW_round2.md (verdict GO; should-fix S1 in-place width
  measured on fragments, S2 RUNBOOK exit line after a SIGKILL of the inner shell) and review2/round2/ (scripts, logs; 90
  files, no empty file).
- 11:52:02 END (re-check round 1): registration.py --verify 11:51:03 manifest OK, both seals OK; no driver re-seal,
  every registered and registration file as at the start; the 9 reviewed files unchanged; scratch /tmp/A10A11/recheck1/
  removed (4 MB; rm -rf --one-file-system), its scripts and logs kept in review2/round2/. Verdict GO (REVIEW_round2.md).
  Every python, pytest, sha256sum, find and shell process of this re-check ran with taskset 12-15, nice 19, ionice 3,
  one BLAS thread, CUDA hidden; one working process at a time (polling tail/sleep beside the background runs). Slip: the
  stamp of the 11:13:53 entry was first written as 11:20 (estimated) and corrected from the clock and the file times;
  the time span of the own harness was first approximate and corrected from its time file.
