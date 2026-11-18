# A10R7B review progress (independent reviewer)

- 2026-11-15 07:31 CST: review started; review directory created; no earlier review attempt found.
- 2026-11-15 07:31 CST: registration.py --verify at start (3.2 s, 18 MB): manifest OK, seal PROTOCOL.md OK, seal
  MANIFEST.sha256 OK. Start hashes: PROTOCOL.md ca54d359..., MANIFEST 4bfe7451..., SEAL b8d516d1..., REGISTRATION
  c0ee0217..., P1 registered_baseline.json df4435e1..., PIPELINE_STATE a670cacb.... No new __pycache__ / empty file
  under framelease_v4/ (only the pre-existing ones of 2026-11-10/11).
- 2026-11-15 07:35-07:55 CST: read APPLY_PLAN2 (all), APPLY_PLAN, apply_entry.py, registration.py, the builder's
  PROGRESS / RUNBOOK / A10_entry / A10_spec / A11_entry / A11_spec / derive_inplace5 / check_a11 / post_check /
  apply_locked.sh / apply_entry_stream.py (diff vs apply_entry.py: sha() only), sim_tree.py; phase_driver phase_view /
  insert_entry / refresh_baseline / verify_registration / analysis_registration / citing_amendment; p1_driver
  protocol_view. Verified: finding 1 = E3 = sealed A3 departure 6 (PROTOCOL.md 2370-2373) = commit_audit 7439a4ea
  docstring; agg_now / agg_snap_2203 commit audit PASS with 184 / 194 audited runs (commit_audit 7439a4ea); km floor
  0.0 (agg_p1) / 0.001 (agg_now, agg_snap_2203); all 14 must_equal sha256 of both specs equal the tree; R7B numbers
  (12259 / 136 / 1, summary.json 3759 / 0, AGREE 25746 / 25746 / 20242, mutate 110/110, 85 passed / 69 subtests);
  review test file differs from the reviewer's original only by the 8 removed expectedFailure marks + 1 docstring line.
- 2026-11-15 07:44 CST: written review/review_sim.py (own scratch-tree harness: trees under /tmp/AMEND3_review/a10r7b/,
  safety checks, the builder's apply_entry_stream.py with only ROOT changed, the builder's apply_locked.sh through
  APPLY_ROOT / APPLIER, an in-process fault injector, cases tests, A-H). Slip: one `python3 -c "print(1)"` (system
  python, no output) ran without the prefix inside a grep command at 07:43.
- 2026-11-15 07:46 CST: TEST RUN case 'tests' on a scratch test tree (85 s, 229 MB): A10 48/107, 21+1F, 49+1F, 28/20;
  A11 71/67, 14/2. Both failures are tree artifacts (framelease_v3 symlinked: its envelopes.py puts the REAL root on
  sys.path, so framelease_v4 was imported from the project; prop1's protected-out test then wrote into the tree's
  envelopes COPY only; figures_tables compared a relative path). Project checked: nothing written outside the review
  directory (the real envelopes/ unchanged, mtime 2026-11-10).
- 2026-11-15 07:50 CST: TEST RUN rerun with framelease_v2/v3 and root *.py copied into the test tree (91 s, 230 MB):
  A10 48/107, 21+1F (Reproducible: recorded input path absolute through the outputs/framelease_v3 link, a tree
  artifact), 50 (422 warnings), 28/20; A11 71/67, 14/2. TEST RUN test_prop1_coverage.py in the project tree (20.5 s,
  131 MB; log review/logs/realtree_pytest_prop1_coverage.log): 22 passed; nothing created. Counts of the builder's
  logs reproduced.
- 2026-11-15 07:52 CST: SIMULATION case A (61 s, 32 MB; /tmp/AMEND3_review/a10r7b/treeA): A10 check passed; A10 through
  apply_locked.sh rc 0, sealed, newly cited = the 8 A10 files, manifest unchanged (221, 4bfe7451); verify OK; parsers
  without ALERT, P1 and phase entries unchanged, A10 read once, every A10 file first cited by A10, G8 waits none, a
  later G3 entry lands above A10 and is read; refresh_baseline (dry run) +8 files, none changed; 0 added prose lines
  > 120 (table rows only), no driver-entry / heading / title / column-0 list line. A11 (stand-in re-review in the
  tree) check passed, rc 0, newly cited = the 2 R7B files, verify OK, A11 read once, R7B files first cited by A11,
  refresh +2; 0 prose lines > 120. post_check A11 passed; post_check A10 after A11 fails on in-place 4 (expected).
- 2026-11-15 07:53 CST: SIMULATION cases B, C (26 s): B A11 first: STOP (in-place 0 times), nothing changed, seal OK.
  C: no overlap among the 5 A10 in-place texts; the Sec. 4.1 status paragraph twice in a (re)sealed PROTOCOL.md: STOP
  before write-manifest (found 2 times), nothing changed; derive_inplace5.py exit 1 on that copy.
- 2026-11-15 07:54 CST: SIMULATION case D (39 s): commit_audit.py (registered by A3; in phase_driver baseline, not in
  the P1 baseline; 46 such files) changed in the tree: registration --verify "manifest: 1 files differ", seals OK;
  apply_entry_stream check passed; apply_locked.sh A10 rc 0 SEALED; verify after: manifest OK (new sha256 sealed);
  phase_driver.refresh_baseline adopts the changed sha256 (no ALERT). Control (realized.py, P1 baseline): STOP before
  write-manifest, nothing changed. => FINDING (laundering of post-P1 registered files).
- 2026-11-15 07:55 CST: SIMULATION case E (45 s): a registered file appended to after --write-manifest (in-process
  injector): applier sealed, apply_locked.sh "exit 0" although its appended verify reads "manifest: 1 files differ"
  (manipulation.py of A3; realized.py of the P1 baseline alike); post_check.py exits 1 (catches it).
- 2026-11-15 07:57 CST: SIMULATION case F (47 s; after fixing my own regex, which first matched A2's manifest line): F1
  applier killed (os._exit 137) after PROTOCOL.md was written and before --seal, nothing of the manifest scope changed:
  PROTOCOL.md holds the entry unsealed (seal CHANGED); wrapper: "rewritten manifest equals the sealed one"; a hand seal
  gives a consistent state. F2 the same with a new file in the manifest scope: the wrapper RESTORES the old manifest
  although PROTOCOL.md holds the entry naming the new one (cec7d5ce..., 222 files); the hand seal of the RUNBOOK then
  verifies (manifest OK, both seals OK) while the A10 entry names a manifest that is not the sealed one (4bfe7451...).
  F3 truncated PROTOCOL.md: STOP "the seal does not verify", nothing changed.
- 2026-11-15 07:58 CST: SIMULATION cases G, H (57 s). G (TZ=UTC): A10 sealed as "2026-11-14 23:57 (Beijing time)",
  8 h early, earlier than G1/G2 (2026-11-15 06:42/06:43) above it and than A3 (06:40) it depends on; nothing stops it
  (the drivers' own stamps guard the zone, apply_entry does not). H: a template line "* **G3 P2 data manifest** (...)"
  passes apply_entry_stream's template check (P1 ENTRY_RE only), is sealed, and phase_view reads it as the G3 entry
  inside A11 (line 3183). The real templates hold no such line (case A; check_a11 / check_drafts check it).
- 2026-11-15 08:02 CST: written review/proposed_apply_locked.sh (wrapper with TZ, driver-file check, PROTOCOL-aware
  restore, python -u, exit 95 on a failed final verify) and case 'fix' in review_sim.py (patched applier copy:
  union of the P1 and phase-driver baselines, phase-driver entry / amendment-title / heading template check, +0800
  check; diff in review/proposed_apply_entry_stream.diff).
- 2026-11-15 08:04 CST: SIMULATION case 'fix' (123 s, 33 MB): A10 / A11 rc 0, newly 8 / 2, verify OK; D STOP before
  write-manifest (commit_audit.py), nothing changed; E wrapper exit 95; F2 no wrong restore, hand seal consistent
  (sealed manifest = the one the entry names); G applier alone under TZ=UTC STOPs, wrapper stamps Beijing time; H
  template STOP.
- 2026-11-15 08:05-08:09 CST: SIMULATION cases V, T, D3. V: a registered file removed before the apply
  (rl/RL_PROTOCOL.md of the P1 baseline; arms_ext/tests/test_drift_guard.py of the phase baseline): sealed rc 0, the
  new manifest omits it, verify OK, refresh drops it; with the vanish fix: STOP before write-manifest. T: a leftover
  framelease_v4/.PROTOCOL.md.entrytmp is sealed into the manifest and vanishes at the rename: verify "1 files differ"
  afterwards, wrapper exit 0. D3: p3_rl.py (gate G4 tool) changed before the apply: sealed, verify OK, refresh adopts,
  require_registered_code would see nothing pending, the new sha256 is cited nowhere.
- 2026-11-15 08:06 CST: blocks.py of the R7B review rerun on the current files (0.1 s): only import lists shared.
  verify_table1_extra imports stdlib + numpy only; tolerances / grid / CLI options / result fields equal the A11 text;
  reconcile_p1_c.json 19 F1 runs, 38 end-censored, 2 missed conflicts, 0 unexplained.
- 2026-11-15 08:09 CST: end_check.py (6.3 s, 18 MB; logs/end_check_0811.log): registration --verify manifest OK, both
  seals OK; P1 baseline 153 and phase-driver baseline 199 files equal the tree and the sealed manifest; nothing under
  framelease_v4/ changed since 07:31; no new __pycache__; only the two pre-existing empty files. Project outputs: only
  the phase driver's own state.json changed (driver activity); nothing written by this review outside review/.
- 2026-11-15 08:10 CST: RUNBOOK sha256 table (21 files) verified with sha256sum -c: all OK. Reproduced read-only:
  check_drafts.py exit 0 (5 in-place texts 1x), check_a11.py exit 2 (A10 not entered; re-review missing),
  make_a11_spec.py --check equal, edit_draft.py --check verbatim, evidence_sha256.txt OK, derive_inplace5.py --spec
  equal on the project PROTOCOL.md and on /tmp/AMEND3/tree (exit 0). A11 is the next free name.
- 2026-11-15 08:12-08:14 CST: two harness lines rewrapped to 120 columns (pyflakes clean); SIMULATION 'fix' and 'V'
  rerun with the final harness (same results; proposed_apply_entry_stream.diff regenerated).
- 2026-11-15 08:16 CST: SIMULATION case fixAV (35 s, 33 MB): every proposed applier change (union baseline, missing
  and vanished files, template patterns, +0800) with proposed_apply_locked.sh: A10 rc 0 (newly the 8 A10 files), the
  phase driver's refresh, A11 rc 0 (newly the 2 R7B files), verify OK, parsers without problem, owners A10 / A11, G8
  waits none. REVIEW.md written (GO_WITH_FIXES; M1; S1-S9). One harness line rewrapped (pyflakes clean).
- 2026-11-15 08:17 CST: END check. registration.py --verify: manifest OK, seal framelease_v4/PROTOCOL.md OK, seal
  MANIFEST.sha256 OK (exit 0). end_check.py (logs/end_check_end.log): P1 baseline 153 and phase-driver baseline 199
  files equal the tree and the sealed manifest; nothing under framelease_v4/ changed since 07:31; no new __pycache__;
  only the two pre-existing empty files. PROTOCOL.md ca54d359, MANIFEST 4bfe7451, SEAL b8d516d1, REGISTRATION c0ee0217,
  P1 registered_baseline df4435e1, PIPELINE_STATE a670cacb: all equal the start values. No ALERT / txn / STOP / PAUSE
  file in phase_driver/. The protocol lock, the drivers, queues, CARLA and the GPU were not touched; this review wrote
  only under build/AMEND2/a10r7b/review/ and /tmp/AMEND3_review/a10r7b/. For A10 deviation 1: this review executed the
  A10 / A11 files only as tests (scratch test tree; test_prop1_coverage.py once in the project tree) and the applier
  on scratch trees; no other execution on real data.
- 2026-11-15 08:20 CST: REVIEW.md final (verdict GO_WITH_FIXES; must-fix M1; should-fix S1-S9; verified list;
  observations). Review files: PROGRESS.md, REVIEW.md, review_sim.py, end_check.py, proposed_apply_locked.sh,
  proposed_apply_entry_stream.diff, logs/. END.
