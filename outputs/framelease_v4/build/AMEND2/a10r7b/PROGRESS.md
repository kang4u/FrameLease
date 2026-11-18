# AMEND2 a10r7b: progress (append-only)

Item: make the two later Sec. 13.2 entries ready: (a) Amendment A10 (APPLY_PLAN2 Sec. 4: everything that does not
need the A3 seal) and (b) the amendment that registers the R7B recomputation (APPLY_PLAN2 step 7, Sec. 5 item 3);
(c) RUNBOOK.md. Nothing is applied: PROTOCOL.md, the registration files, the seal and every registered file stay
untouched; simulations run on scratch copies under /tmp/AMEND3/a10r7b/ only.

- 2026-11-15T06:31:45+08:00 start: no earlier PROGRESS.md (directory absent: fresh start). registration.py --verify
  (3.1 s, 18 MB): manifest OK, seal framelease_v4/PROTOCOL.md OK, seal MANIFEST.sha256 OK. baseline_check.py (6.5 s,
  17 MB): registered_baseline.json 153 files, none differs from the tree or the sealed manifest; manifest 218 files, none
  differs from the tree; PROTOCOL.md a848a349..., MANIFEST 4e424763..., SEAL 10f07459..., REGISTRATION 13b19e7d...
  Reference stamp /tmp/AMEND3/a10r7b/start_ref (06:31:00+08:00). Slip: the heredoc that wrote /tmp/AMEND3/a10r7b/p.sh
  and its chmod ran without the prefix (trivial); every later process runs through p.sh (taskset -c 12-15 nice -n 19
  ionice -c 3, one BLAS thread, CUDA_VISIBLE_DEVICES=''). Step-3 item (build/AMEND2/step3) ended 06:29:54; its
  scratch /tmp/AMEND3/{tree,work,...} is read only here.
- 2026-11-15T06:50:00+08:00 read: APPLY_PLAN2 (all), A10_entry.md, A10_spec.json, OP_spec.json, apply_entry.py,
  check_drafts.py, AMENDMENTS2_DRAFT.md (front matter, appendix), AMEND2 / step3 PROGRESS, AGG PROGRESS 165-179, AGG0
  review, R4 / R5 / R6 / R7 / R7B / FILL0 PROGRESS, R4-R7 / R7B / FILL0 reviews. All 28 files of the AMENDMENTS2_DRAFT
  appendix (incl. the 8 A10 files and the 3 reused coverage files) are at their drafting sha256 (sha256sum -c OK): A10
  must_equal unchanged, step 1 of APPLY_PLAN2 was not done (A10 "Known limitations" stands as written).
- 2026-11-15T06:50:00+08:00 STATE CHANGE observed (read only): P1_DONE.json 06:38:47; the coordinating session applied
  step 3 at 06:40 (step3/step3_20261115T064024.out: PASS, A3, A9, A7 (A7b), A4 and the operational addition entered
  06:40, one manifest, one seal); D1_DECISION.json 06:42:15; the phase driver runs (pid 256142, started 06:42:42) and
  entered G1 (06:42) and G2 (06:43); queue_p2 runner alive. registration.py --verify now: manifest OK, both seals OK;
  PROTOCOL.md ca54d359..., MANIFEST 4bfe7451... (221 files). phase_driver/registered_baseline.json: 199 files. So A10
  is applicable now (APPLY_PLAN2 step 6) and its fifth in-place text can be derived from the real post-A3 PROTOCOL.md
  (Sec. 4.1 lines 483-486, read only). A11 is a free amendment name (PROTOCOL.md and the drafts use no A11). Slip:
  one stray `python3 -c "print('x')"` (system python, through p.sh, printed only) at 06:47.
- 2026-11-15T06:58:30+08:00 backups orig/A10_entry.before_a10r7b.md (c51566ea...), orig/A10_spec.before_a10r7b.json
  (e92a5dce...), orig/AMENDMENTS2_DRAFT.before_a10r7b.md (f022b942...). final/A10_entry.md edited: deviation 1
  rewritten as the complete list of executions on real data from 2026-11-14 on (sources: R4 PROGRESS steps 6, 22,
  36, 43, 53, 68, 70, 93 and console logs smoke_train*.log: six analyze_v4 CLI runs on smoke_D, the 08:16 run of step 70
  was missing from the draft; R5 PROGRESS 08:54-09:02 + R5 review; R6 PROGRESS 09:25-11:25; R7 PROGRESS steps 2, 31-33,
  43, 45, 47, 61, 62 + probe records frozen 11:33:30 / 11:57:47 + R7 review; AGG PROGRESS 171-173; R7B PROGRESS 14:50,
  22:04-22:08 + console logs; FILL0 and its review ran figures_tables on synthetic inputs only: not listed); finding
  1: the rule in the words of E3 (A3 departure 6, as sealed at 06:40) plus the re-audit result (0 violations, 47 PASS,
  1 NO_LOG) and agg_now / agg_snap_2203 PASS (read from their aggregate.json); finding 2: the km floor now in
  aggregate_v4.py (agg_p1 0.0, agg_snap_2203 0.001 for v4p1smoke_fl_heuristic_E5_d10_k1.0_s11_r18305, read from
  runs.csv); Evidence: + SHA256SUMS of build/AGG/step0_reaudit, build/R7B/dev/agg_now, agg_snap_2203 (all three and
  the five earlier dev manifests verify with sha256sum -c).
- 2026-11-15T07:00:57+08:00 TEST RUN apply_entry.py final/A10_spec.json --tests (06:59:42-07:00:57, 75.1 s, max RSS
  230 MB): pytest_analyze_v4.log 48 passed, 107 subtests (16.1 s); pytest_prop1_coverage.log 22 passed (20.3 s);
  pytest_figures_tables.log 50 passed, 422 warnings (23.5 s); pytest_verify_independent.log 28 passed, 20 subtests
  (13.7 s); all exit 0; the counts of the drafting logs. Logs in outputs/framelease_v4/amendment_a10/ (new directory).
- 2026-11-15T07:02:00+08:00 written derive_inplace5.py (the fifth A10 in-place text from a PROTOCOL.md that holds A3:
  OLD/NEW clause from the template bullet, the one Sec. 4.1 paragraph that starts "Status (Amendment A3):", old = the
  paragraph as it stands, new = clause replaced and rewrapped at 120 columns, checks: old once in PROTOCOL.md, words,
  widths, list/heading/driver-entry/amendment-title lines, outside Sec. 13.2; --spec compare (exit 3 when it differs),
  --write). pyflakes clean. Tests (read only): simulated post-step-3 /tmp/AMEND3/tree/framelease_v4/PROTOCOL.md exit 0;
  real PROTOCOL.md (ca54d359) exit 0, lines 483-486, max new line 119; both derivations equal each other and
  step3/sim_output/a10_inplace5_suggestion.json; negatives on scratch copies (/tmp/AMEND3/a10r7b/derive_tests/):
  paragraph twice -> FAIL, clause already replaced -> FAIL, paragraph text also elsewhere -> FAIL (old 2x),
  pre-step-3 PROTOCOL.md (/tmp/AMEND3/rv/snap/p1end) -> FAIL (0 paragraphs), clause rewrapped -> derived correctly.
- 2026-11-15T07:03:00+08:00 final/A10_spec.json: in-place text 5 written by derive_inplace5.py --write from the real
  sealed PROTOCOL.md (A3 sealed 06:40): old = the Sec. 4.1 status paragraph, new = rewrapped; nothing else changed
  (diff of the JSON: lines 48-49 only); spec sha256 b1de9f6a... (was e92a5dce...). final/A10_entry.md: deviation 1
  lead sentence ("from 2026-11-14 to the application of this entry read its inputs only"), the aggregator bullet end.
  edit_draft.py written and run: AMENDMENTS2_DRAFT.md holds the edited template verbatim, A10 preface states the
  second and fifth in-place texts after step 3, appendix + the 3 added Evidence sha256 (draft 6d9a0ced...; template
  72b6d1d9...). check_drafts.py: 5 in-place texts found 1x, all checks passed, exit 0 (0.2 s, 31 MB).
- 2026-11-15T07:04:00+08:00 apply_entry.py final/A10_spec.json (check mode, read only): "check: pre-checks passed"
  (10.7 s). SLIP / FINDING: its max RSS was 5.8 GB (above the 1.5 GB limit): apply_entry.sha() hashes with
  Path.read_bytes(), and the pre-check hashes every registered file of the sealed manifest, among them the 5.9 GB
  checkpoint checkpoints/UniDriveVLA/.../UniDriveVLA_Stage3_Bench2drive_2B.pt. No OOM followed (free -g: 11 GB
  available at 07:05; the P2 job that ended 07:02:34 exit 0, the next one started and runs). apply_entry.py is not
  run again by this item; --check and --apply of the coordinating session take the same 5.8 GB unless the hash
  streams (RUNBOOK: streaming variant, memory precondition).
- 2026-11-15T07:08:00+08:00 written apply_entry_stream.py = paper_tools/apply_entry.py (2ddc1c8c...) with only sha()
  changed to 1 MiB streaming (diff: lines 36-41; pyflakes clean; 31e9bab3...). Check mode on A10_spec.json (read
  only): "check: pre-checks passed", 8.3 s, max RSS 18 MB (the original: 5.8 GB).
- 2026-11-15T07:07:00+08:00 written make_a11_spec.py (A11_spec.json from the A10 spec: in-place = the A10
  Verification "new" with the clause "a second script, ... recomputes the other Table I columns," replaced by
  "Amendment A11: `framelease_v4/analysis/verify_table1_extra.py` recomputes GPU usage, DMR, action age p50 and p95,
  fallback ratio, EIR, P_both and the closed-loop R_cond," rewrapped at 120 (line widths 120, 118, 115, 118, 34);
  tests: builder tests + R7B review tests, logs in outputs/framelease_v4/amendment_a11/; must_equal: the two R7B
  files (a8bf57b7..., c3bf160c...) and review/test_review_r7b.py (63c4359d...); max_new_registered 2). pyflakes
  clean, lines <= 120. Run: A11_spec.json 5fc36c01... (the template A11_entry.md follows).
- 2026-11-15T07:07:16+08:00 TEST RUN apply_entry.py a10r7b/A11_spec.json --tests (07:07:06-07:07:16, 9.9 s, max RSS
  93 MB): pytest_verify_table1_extra.log 71 passed, 67 subtests (5.1 s; RealSmokeRuns ran on the 14 P1-0 smoke
  run directories); pytest_review_r7b.log 14 passed, 2 subtests (4.1 s); both exit 0, no skip; together the 85
  passed / 69 subtests of R7B attempt 5. Logs 7b3b4d9d..., 1cad9377... (new directory amendment_a11/).
- 2026-11-15T07:13:00+08:00 written A11_entry.md (Amendment A11: cause, file table, what it computes and from which
  logs, not recomputed, independence, tolerances, interim looks, development data, development comparison of the
  registered version, findings F1 / F2 on registered files, use rules 1-3, in-place text (Sec. 9.12 Verification as
  A10 leaves it), scope, files, evidence, tests with "At drafting" counts, manifest line); copies of the drafting
  logs in logs/ (A11) and logs/a10_20261115/ (A10). check_a11.py written (placeholders, filled widths and parser
  collisions, spec, the apply_entry.py count of newly cited manifest files, simulation after a simulated A10 with
  a later gate entry, open preconditions). Run 1: one filled line of 126 columns (mutate.log evidence line), the
  re-review placeholder reported as a problem: line rewrapped; the review of the R7B fixes
  (build/R7B/rereview/REVIEW.md) made an open precondition. Run 2 (0.11 s, 31 MB): checks passed, apply_entry count
  2 (the two R7B files), simulation without problem (P1 and phase entries unchanged, A10 and A11 read once,
  analyze_v4.py cited first by A10, the R7B files by A11, G8 analysis_registration without wait, a later G3 entry
  read), 2 open preconditions (A10 not yet entered; re-review missing), exit 2; simulated texts in
  /tmp/AMEND3/a10r7b/sim_mem/ (Sec. 4.1 and Sec. 9.12 Verification after A10 + A11 inspected).
- 2026-11-15T07:16:00+08:00 written sim_tree.py (scratch-tree dry run with apply_entry_stream.py, ROOT = tree, one
  line changed and checked; cases A: A10 check/apply/seal/parsers, A11 with a stand-in re-review check/apply/
  seal/parsers + later gate; B: A11 before A10 stops; C: A11 without the review file fails in the fill after
  write-manifest; safety stop unless every written path resolves inside the tree; the stand-in only when the real
  re-review is absent and its directory lies in the tree). pyflakes clean, lines <= 120.
- 2026-11-15T07:16:47+08:00 SIMULATION sim_tree.py (07:14:40-07:16:47, 126.8 s, max RSS 31 MB; trees under
  /tmp/AMEND3/a10r7b/sim_tree/): ALL EXPECTED. A0 tree seal OK; A1 A10 check passed; A2 A10 --apply (flock on the
  tree lock): sealed, newly cited manifest files 8 (the A10 files), manifest 221 files unchanged (4bfe7451...); A3
  seal OK; A4 parsers: analyze_v4.py first cited by A10, G8 analysis_registration without wait; A4b stand-in of
  the R7B re-review written in the tree; A5 A11 check passed; A6 A11 --apply sealed, newly cited exactly
  test_verify_table1_extra.py and verify_table1_extra.py; A7 seal OK; A8 parsers: A10 and A11 read once, the R7B
  files first cited by A11, a later G3 entry read; A9 diff against the project PROTOCOL.md: hunks Sec. 4.1, 9.4,
  9.12 Code/Freeze/Verification and the two entries after G2, 0 added prose lines over 120. B: A11 before A10 stops
  at the pre-check (in-place text found 0 times), PROTOCOL.md unchanged. C: A11 without the review file: exit 1,
  FileNotFoundError in the fill after write-manifest, PROTOCOL.md unchanged, rewritten manifest identical, seal OK.
  Evidence copied to sim_output/ (logs, parse JSON, diff, summary, the filled A11 of check_a11).
- 2026-11-15T07:21:00+08:00 A11_entry.md: Tolerances paragraph states when the tolerances were fixed (each part before
  its first comparison; the time resolution of V with must-fix M1), rewrapped by hand ("|H - V_suf|" kept on one
  line; words otherwise unchanged); check_a11.py: checks passed, 2 open (A10 not entered; re-review missing), exit 2.
  post_check.py written (registration verify, parsers, amendment read once, citing lines, G8 analysis_registration,
  in-place texts applied, phase_driver ALERT / txn absent, baseline refresh pending -> exit 3; --root for a scratch
  tree); tests: treeA A11 -> exit 3 (all checks pass, refresh pending), treeC (A10 only) A10 -> exit 3, treeA A10 ->
  FAIL in-place 4 (A11 replaced it: post_check A10 runs before A11), project now A10 -> FAIL (not applied yet), as
  expected. evidence_sha256.txt: the 36 files the two templates cite by sha256 (except manifest, test logs,
  re-review), sha256sum -c OK.
- 2026-11-15T07:21:52+08:00 written apply_locked.sh (one hold of framelease_v4/.protocol.lock: backup of the sealed
  manifest, apply_entry_stream.py --apply, restore of the sealed manifest when the applier failed after
  --write-manifest and before --seal and the rewritten manifest differs, registration --verify; APPLY_ROOT /
  APPLIER for the scratch tree only); bash -n ok. sim_tree.py: case D added (the wrapper: A10 sealed through it; a
  new file in the tree's manifest scope, then A11 without the review file: restore). pyflakes clean, lines <= 120.
- 2026-11-15T07:23:55+08:00 SIMULATION rerun with the final texts (07:22:03-07:23:55, 111.8 s, max RSS 31 MB): ALL
  EXPECTED: A0-A9 as before (A10 newly cited 8, A11 newly cited the 2 R7B files, seals OK, parsers OK, 0 added prose
  lines over 120), B STOP before any change, C crash in the fill with an identical rewritten manifest (seal OK), D1
  apply_locked.sh A10 exit 0, D2 apply_locked.sh: write-manifest 222 files (the probe), FileNotFoundError, "RESTORED
  the sealed manifest", both seals OK, PROTOCOL.md unchanged. Evidence refreshed in sim_output/ (19 files).
- 2026-11-15T07:25:00+08:00 RUNBOOK.md written (conventions with the memory and manifest-backup rules and the applier
  diff; A10 preconditions 1-5, application through apply_locked.sh, STOP handling, post-check; what changed in A10
  and the fifth in-place procedure with its differences from APPLY_PLAN2; A11 preconditions incl. the re-review,
  application, deadline, the later R7B run; the dry run; open issues; file sha256 table). Prose lines <= 120 (one
  command line copied from APPLY_PLAN2 longer).
- 2026-11-15T07:25:30+08:00 final checks (read only): check_drafts.py exit 0 "all checks passed" (5 in-place texts 1x);
  derive_inplace5.py --spec: equals, exit 0; check_a11.py exit 2 (open: A10 not entered; re-review missing; no
  problem); make_a11_spec.py --check equal; evidence_sha256.txt sha256sum -c exit 0; edit_draft.py --check: the
  draft holds the template verbatim.
- 2026-11-15T07:27:00+08:00 END: registration.py --verify: manifest OK, seal framelease_v4/PROTOCOL.md OK, seal
  MANIFEST.sha256 OK. P1 registered_baseline.json 153 files: none differs from the tree or the sealed manifest;
  phase_driver/registered_baseline.json 199 files, all equal the sealed manifest; manifest 221 files, none differs
  from the tree. PROTOCOL.md ca54d359... (06:43), MANIFEST 4bfe7451..., SEAL b8d516d1..., REGISTRATION c0ee0217...:
  changed since the start (a848a349 / 4e424763 / 10f07459 / 13b19e7d) by the coordinating session's step-3
  transaction (06:40) and the phase driver's G1 / G2 entries (06:42-06:43), not by this item. Under framelease_v4/
  since 06:31 only PROTOCOL.md (06:43) and PIPELINE_STATE.md (06:44, coordinating session) changed; the __pycache__
  directories under framelease_v4/, arms/ and rl/ date from 2026-11-10 (pre-existing); the only empty files are the
  pre-existing .protocol.lock and offline/__init__.py; no phase_driver/ALERT.txt or protocol_txn.json. This item wrote
  only under build/AMEND2/ (a10r7b/, final/A10_entry.md, final/A10_spec.json, AMENDMENTS2_DRAFT.md),
  outputs/framelease_v4/amendment_a10/ and amendment_a11/ (test logs) and /tmp/AMEND3/a10r7b/. The protocol lock,
  the drivers, queues, CARLA and the GPU were not touched. Slips: the heredoc/chmod of p.sh (06:31), one stray system
  python3 print (06:47), one `free -g` (07:14) without the prefix; apply_entry.py check mode at ~07:04 reached 5.8 GB
  RSS for about 10 s (no OOM; see 07:04).
- 2026-11-15T07:29:36+08:00 A11_entry.md: Cause states Sec. 7.2 as written (R_cond "in the table notes or the text";
  bullet rewrapped, words otherwise unchanged) and use rule 2 "(table notes or text)"; check_a11.py: checks passed, 2
  open, exit 2. SIMULATION final rerun with these texts (07:27:43-07:29:36, 113.0 s, 31 MB): ALL EXPECTED (A0-A9, B,
  C, D as at 07:23; 0 added prose lines over 120); sim_output/ refreshed (20 files, + the simulated PROTOCOL.md as
  .md.txt). RUNBOOK: dry-run time and the A11_entry.md sha256 (6a8bb75e...) updated.
- 2026-11-15T07:31:00+08:00 END (final, after the last simulation): registration.py --verify: manifest OK, seal
  framelease_v4/PROTOCOL.md OK, seal MANIFEST.sha256 OK; P1 baseline 153 files none differs; phase baseline 199 files
  equal the sealed manifest; PROTOCOL.md still ca54d359 (06:43); under framelease_v4/ since 06:31 only PROTOCOL.md and
  PIPELINE_STATE.md (not this item).

## Fix pass after review/REVIEW.md (GO_WITH_FIXES: must-fix M1; should-fix S1-S9)

- 2026-11-15T08:20:00+08:00 FIX START: PROGRESS.md read (last line 07:31 END; no file under build/AMEND2/ newer than
  review/REVIEW.md: no earlier fix attempt). registration.py --verify (5.2 s, 18 MB): manifest OK, seal
  framelease_v4/PROTOCOL.md OK, seal MANIFEST.sha256 OK. review/end_check.py --since 08:19 (7.4 s, 18 MB): P1
  baseline 153 and phase-driver baseline 199 files equal the tree and the sealed manifest; PROTOCOL.md ca54d359...,
  MANIFEST 4bfe7451..., SEAL b8d516d1..., REGISTRATION c0ee0217..., PIPELINE_STATE a670cacb..., P1 baseline
  df4435e1..., phase baseline cfe58aa1... (all as at the review's end). Reference stamp /tmp/AMEND3/a10r7b/fix_start_ref.
- 2026-11-15T08:27:00+08:00 read: review/REVIEW.md, review/PROGRESS.md, proposed_apply_locked.sh,
  proposed_apply_entry_stream.diff, review_sim.py (FIX_REPLACEMENTS, VANISH_REPLACEMENTS, cases), FILL0 and FILL0
  review PROGRESS (first FILL0 run 01:24 /tmp/FILL0/syn, last 03:33; helpers_fill.producer_pipeline runs AN.main and
  FT.main without --offline: both default to outputs/framelease_v4/offline_ablation), AGG steps 171-173 (re-audit ran
  the earlier commit_audit 96dd22c4 as /tmp/AGG0 copy with --before-module and the current 7439a4ea), R7B review
  PROGRESS (23:22-00:20; variants/injection on build/R7B/dev/p1_snap_2203 + agg_snap_2203; /tmp/review_R7B,
  build/R7B/review/logs/), phase_driver.refresh_baseline (registered = old baseline + manifest files whose sha256
  PROTOCOL.md cites), registration.py (scope; --verify lines). Read-only checks before any edit: check_drafts exit 0,
  check_a11 exit 2 (A10 not entered; re-review missing), derive_inplace5 --spec equal, evidence sha256sum -c OK,
  make_a11_spec --check equal, edit_draft --check verbatim. No PROGRESS.md under build/ changed since 06:31 except
  step3 (06:39), the review and this file; no build/R7B/rereview/ yet. Backups of the 11 files to be edited:
  orig/*.before_fix.* (sha256 = the reviewed versions). Slip: one `free -m` (08:23) ran without the prefix.
- 2026-11-15T08:41:00+08:00 M1 + S2-S6 applied. apply_entry_stream.py (0f0cfda6...): registered = files of
  p1_driver/ and phase_driver/registered_baseline.json (both required) + every sealed-manifest file whose sha256
  PROTOCOL.md cites (phase_driver.refresh_baseline's rule; closes the window between a seal and the driver's refresh);
  pre-check STOP when a registered file is absent from the sealed manifest, differs on disk or is missing (M1 items 1-2);
  after --write-manifest STOP when a registered file changed or left the new manifest (M1 item 3); template and filled
  entry refused on lines read as P1 / phase entries, amendment titles after the title, driver headings, the anchor
  phrase anywhere (S4); every placeholder must have a value before --write-manifest: known kind, {{sha256:}} file
  exists (manifest excepted), {{pytest:}} log is a spec test log (S4); %z must be +0800 (S3); STOP while
  framelease_v4/.PROTOCOL.md.entrytmp exists, temporary file removed on an exception (S5); protocol_txn.json /
  ALERT.txt of both drivers (S6). Regex/heading/anchor constants equal p1_driver / phase_driver (checked). pyflakes
  clean, lines <= 120. apply_locked.sh (9c86ca20...): TZ=Asia/Shanghai; in-lock refusal exit 96 for both drivers'
  txn/ALERT files and the leftover temporary file (S5, S6); PROTOCOL.md copied with the manifest; after a failure the
  manifest is restored only while PROTOCOL.md equals its copy (and a temporary file left by the applier is removed),
  otherwise kept with "seal it now" (S1); applier run with python -u (S1); exit 95 when the applier sealed but the
  verification does not read manifest OK + both seals OK (S2). bash -n ok, lines <= 120. apply_entry_stream.diff
  (737a3e5c..., diff -u against paper_tools/apply_entry.py 2ddc1c8c). Check mode on the project (read only): A10
  "check: pre-checks passed" (8.2 s, 18 MB); A11 STOP "in-place text found 0 times" (6.6 s, 18 MB; A10 not entered).
- 2026-11-15T08:50:00+08:00 S7 applied in final/A10_entry.md (3922f78c...): deviation 1 lead sentence "(2026-11-14
  unless a date is given)" instead of "(all on 2026-11-14)"; new bullet: analyze_v4.py and figures_tables.py on
  2026-11-15, 01:24 to 03:33, item FILL0 and its review on synthetic aggregations through the harness of
  tests/test_figures_tables.py into /tmp/FILL0/, /tmp/review_FILL0/ and test temporary directories, with the default
  --offline reading the offline outputs written before registration (S7a); the re-audit item now names "the earlier
  commit_audit.py (sha256 96dd22c4...bff279, a copy under /tmp) and the current one (the rule of finding 1)" (S7b).
  Filled widths <= 120 (table rows excepted). edit_draft.py (12a0a4ee...) made idempotent (a step whose new text the
  draft holds is skipped; the embedded template may be the pre-item or the 07:03 version); run: draft (b64d0599...)
  changed only in the template (diff: line 227, +5 lines after 246, lines 257-260 rewrapped); rerun: nothing to
  change; --check: verbatim. check_drafts.py: 5 in-place texts 1x, "all checks passed", exit 0.
- 2026-11-15T08:57:00+08:00 S8 (entry part) applied in A11_entry.md (11b4ac48...): "Development data" names the R7B
  review's runs: the reviewed version (injected runs.csv values, guard probes), monkeypatched variants and the
  plan-by-plan comparison with realized.py on the 180 run directories of build/R7B/dev/p1_snap_2203/, 2026-11-14
  23:22 to 2026-11-15 00:20, into /tmp/review_R7B/ and build/R7B/review/logs/ (build/R7B/review/PROGRESS.md); last
  sentence rewrapped (no orphan line). Widths <= 120 (table rows excepted). check_a11.py (63a420f4...): the newly-cited
  count mirrors the fixed applier (registered = both baselines + files PROTOCOL.md cites), docstring and messages
  name apply_entry_stream.py; pyflakes clean, lines <= 120; run: checks passed, count 2 (the R7B files), 2 open (A10
  not entered; re-review missing), exit 2. Slip: one sed (08:55, edit of check_a11.py) and the read-only inspection
  commands of this pass (cat, grep, sed -n, ls, find, date) ran without the taskset/nice/ionice prefix; every python,
  pytest, sha256sum, diff and simulation process runs through p.sh.
- 2026-11-15T08:54:54+0800 CORRECTION of the stamps of the three entries above stamped 08:41, 08:50 and 08:57: those stamps were
  estimates, not clock readings. Real times from the file mtimes: apply_entry_stream.py written 08:28:04,
  apply_locked.sh 08:41:55, apply_entry_stream.diff and the check-mode runs 08:44; A10_entry.md 08:45:53, draft
  08:46:35, edit_draft.py 08:46:45 (S7 entry written about 08:47); A11_entry.md 08:47:26, check_a11.py 08:48:03 (S8
  entry written about 08:49). From here on every stamp is read from the clock (date). Since then: sim_tree.py
  rewritten (08:49:48; cases A-G), rerun_review_sim.py written (08:51:11; the review's harness on the fixed files,
  expectations per case), post_check.py (08:51:48: a note when phase_driver/STOP exists and only the refresh is
  pending, S9), RUNBOOK.md rewritten (08:54:33; results still to be filled). SIMULATION sim_tree.py started about
  08:50 in the background (runs alone; no other process started meanwhile except one pyflakes/awk pass at about 08:52
  and the date/stat of this line).
- 2026-11-15T08:55:37+0800 SIMULATION sim_tree.py (08:49:59-08:54:58, 299 s, max RSS 31 MB; trees /tmp/AMEND3/a10r7b/sim_tree/): ALL
  EXPECTED (37 steps). A: A10 check/apply (newly cited the 8 A10 files, manifest 221 unchanged), seal OK, parsers
  (analyze_v4.py first cited by A10, G8 no wait); A11 right after A10 with the phase baseline NOT refreshed (the cited
  rule): check passed, sealed, newly cited the 2 R7B files, parsers OK, later G3 entry read; diff 457 lines. B: A11
  first STOP in-place 0x. C: A11 without the review file now STOPs at the pre-check (placeholder without a value)
  before --write-manifest, state unchanged, seal OK. D: wrapper A10 exit 0; A11 killed after --write-manifest (new
  file in scope): exit 137, RESTORED, state unchanged, seal OK; A11 again sealed. E (M1): commit_audit.py and p3_rl.py
  appended, arms_ext/tests/test_drift_guard.py and rl/RL_PROTOCOL.md removed: check exit 1 and wrapper exit 1 STOP
  before --write-manifest, state unchanged, each; restored: A10 sealed. F1 (S1): killed before --seal with a new file
  in scope: exit 137, PROTOCOL.md holds A10, manifest kept = the one the entry names (1ea365bc..., was 4bfe7451...),
  "seal it now"; hand seal under the tree lock: verify OK with that manifest. F2 (S2): manipulation.py appended after
  --write-manifest: exit 95. G: TZ=UTC applier STOP (S3); entrytmp and both drivers' txn/ALERT files: wrapper exit 96 +
  check STOP, unchanged (S5, S6); caller TZ=UTC through the wrapper: title 08:54 Beijing time (S3); template lines G3
  entry / A12 title / phase heading / anchor phrase: check STOP (S4); restored template passes. Added PROTOCOL lines
  (A9 diff): 438, prose > 120: none (13 table rows, as in A3), no driver-entry / heading / title / list-start line.
  Evidence: old sim_output/ renamed sim_output_before_fix/; new sim_output/ (53 files incl. sim_tree_run.out and the
  simulated PROTOCOL.md as .md.txt).
- 2026-11-15T08:57:25+0800 TEST RUN apply_entry_stream.py final/A10_spec.json --tests (08:55:44-08:57:00, 75.7 s, max RSS 230 MB):
  pytest_analyze_v4.log 48 passed, 107 subtests (15.8 s); pytest_prop1_coverage.log 22 passed (20.1 s);
  pytest_figures_tables.log 50 passed, 422 warnings (23.9 s); pytest_verify_independent.log 28 passed, 20 subtests
  (14.2 s); all exit 0 (logs f5f11f8a..., 5283125b..., 7ccb719f..., cf768b09...). TEST RUN A11_spec.json --tests
  (08:57:08-08:57:17, 9.6 s, 93 MB): pytest_verify_table1_extra.log 71 passed, 67 subtests (4.9 s; RealSmokeRuns on
  the 14 P1-0 smoke run directories); pytest_review_r7b.log 14 passed, 2 subtests (4.1 s); exit 0 (cd8d75ad...,
  0a6d4014...). Counts equal "At drafting" of both entries.
- 2026-11-15T09:07:32+0800 REVIEWER'S HARNESS rerun_review_sim.py (08:57:33-09:07:04, 570 s, max RSS 229 MB; trees
  /tmp/AMEND3/a10r7b/rsim/, removed afterwards; logs and summaries in review_rerun/logs/, 66 files): review_sim.py loaded
  unchanged, locations moved (BASE /tmp/AMEND3/a10r7b/rsim, LOGS review_rerun/logs, INJECT prefixes), fix hooks =
  the fixed applier/wrapper, VANISH_REPLACEMENTS = (); ALL EXPECTED, 46 expectations PASS: tests (A10 48/107, prop1
  21 + 1 failed = the tree artifact the review names, Reproducible::test_reproduces_development_run, 50, 28/20; A11
  71/67, 14/2; no protected path or __pycache__ in the tree), A (A10 newly 8, refresh +8, A11 newly 2, refresh +2,
  verify OK, parsers clean, 0 prose lines > 120, post_check A11 0, post_check A10 after A11 fails on in-place 4 only),
  B, C (no overlap; old twice STOP; derive exit 1), D (commit_audit.py changed: STOP, was sealed; control STOP), E
  (both labels: exit 95, was 0), F (F1/F2: entry kept, rewritten manifest kept, hand seal consistent, was a wrong
  restore in F2; F3 STOP), G (caller TZ=UTC: Beijing stamp), H (G3-entry template line: STOP, was sealed), fix (A 8/2,
  D STOP, E 95, F2 consistent, G applier UTC STOP + wrapper Beijing, H STOP), V (removed registered files: STOP, was
  sealed), T (leftover temporary file: exit 96, was sealed into the manifest), D3 (p3_rl.py changed: STOP, was
  sealed), fixAV (A10, refresh, A11: 8 and 2 files, verify OK, owners A10/A11, G8 no wait). The review directory was
  not written (REVIEW pointed to a scratch path; the review's logs and proposals unchanged). One ls/date (09:05) ran
  during the harness. A10_entry.md: FILL0 bullet wording "the temporary directories of the FILL0 tests" / "as their
  own tests do" (09:03, during the harness; trees built later used it; widths checked by hand: 116/115 columns).
- 2026-11-15T09:08:35+0800 edit_draft.py (67c6955c...) step 1 now replaces the embedded A10 template by its boundaries (the A10 title line,
  once in the draft, to the end of the first manifest line after it), whatever version the draft holds (the first
  fix-pass version stopped on the intermediate 08:46 draft: "old texts occur [0, 0] times", nothing written);
  pyflakes clean (lines over 120 only in the verbatim draft constants, as before). Run: template replaced, preface and
  appendix held; rerun: nothing to change; --check verbatim. Draft (03bfb7f4...) differs from orig/
  AMENDMENTS2_DRAFT.before_fix.md only in the template (line 227, +5 lines after 246, 257-260 rewrapped). A10_entry.md
  final (9790c164...). check_drafts.py: "all checks passed", exit 0. Filled widths of both templates <= 120 (table rows
  excepted).
- 2026-11-15T09:14:44+0800 SIMULATION sim_tree.py final rerun with the final texts (09:08:44-09:13:44, 299 s, max RSS 32 MB): ALL
  EXPECTED, 37 steps, the same results as at 08:54 (A10 newly 8, A11 newly 2 before the refresh; B; C STOP at the
  pre-check; D restore after a kill after --write-manifest; E 4x STOP; F1 kept + consistent hand seal, F2 exit 95; G
  TZ, entrytmp, 4 driver files, Beijing stamp 09:13, 4 template patterns). sim_output/ refreshed (53 files + the
  filled A11 of check_a11.py --write-sim as A11_filled_check_a11.md); added PROTOCOL lines 438, prose > 120 none, 13
  table rows, no pattern line; the simulated PROTOCOL.md holds the final FILL0 bullet and the R7B review sentence.
  post_check.py A11 --root treeA: exit 3 (refresh pending); with a STOP file written into the scratch tree's
  phase_driver/ only: exit 3 and the S9 note; STOP removed (the project's phase_driver/ unchanged). Checks:
  check_a11.py --write-sim: checks passed, 2 open (A10 not entered; re-review missing), exit 2; derive_inplace5 --spec
  equal; evidence sha256sum -c OK; make_a11_spec --check equal; edit_draft --check verbatim; check_drafts "all checks
  passed"; pyflakes clean on the 9 scripts; bash -n ok; lines <= 120 in the scripts; RUNBOOK only the copied python
  one-liner (285). Slip: the STOP probe write/rm in the scratch tree and two ls ran without the prefix.
- 2026-11-15T09:16:29+0800 RUNBOOK.md (75cb4c07...) final: Sec. 0 states the applier changes (M1, S3-S6; diff apply_entry_stream.diff)
  and the wrapper (S1, S2, S5, S6; exit codes 95-98); Sec. 1 precondition 1 + the temporary file, precondition 3 with
  the FILL0 runs and -newermt '2026-11-15 09:15', tests through apply_entry_stream.py (08:57 logs), the failure
  handling rewritten (S1: PROTOCOL.md unchanged -> restored or equal; entry written -> kept manifest, hand seal;
  exit 95, 96, 97; interrupted wrapper); Sec. 2 the S7 changes; Sec. 3 precondition 1 accepts exit 3 with only the
  refresh pending while phase_driver/STOP holds the driver (S9), new precondition 3 (Development data complete, the
  re-review's runs included, S8), precondition 5 (the two R7B files may differ before A11); Sec. 4 both dry runs;
  Sec. 5 open issues (paper_tools/apply_entry.py keeps the defects); Sec. 6 sha256 table of 23 files (sha256sum -c of
  the table as parsed from the RUNBOOK: OK). Widths: only the copied python one-liner exceeds 120.
- 2026-11-15T09:16:29+0800 END (fix pass): registration.py --verify (09:15:40): manifest OK, seal framelease_v4/PROTOCOL.md OK, seal
  MANIFEST.sha256 OK. review/end_check.py --since 08:19: P1 baseline 153 and phase-driver baseline 199 files equal the
  tree and the sealed manifest; framelease_v4/ entries changed since 08:19: none; new __pycache__ under framelease_v4:
  none; empty files only the pre-existing .protocol.lock and offline/__init__.py. baseline_check.py: manifest 221
  files, none differs. PROTOCOL.md ca54d359..., MANIFEST 4bfe7451..., SEAL b8d516d1..., REGISTRATION c0ee0217...,
  PIPELINE_STATE a670cacb..., P1 baseline df4435e1..., phase baseline cfe58aa1...: all equal the start values (no
  driver re-seal happened during this pass). No ALERT / protocol_txn / STOP / PAUSE file in either driver directory;
  no framelease_v4/.PROTOCOL.md.entrytmp. Written by this pass: build/AMEND2/a10r7b/ (scripts, texts, RUNBOOK,
  PROGRESS, orig/*.before_fix.*, sim_output/ + sim_output_before_fix/, review_rerun/logs/), final/A10_entry.md,
  AMENDMENTS2_DRAFT.md, the six test logs in outputs/framelease_v4/amendment_a10/ and amendment_a11/, and scratch under
  /tmp/AMEND3/a10r7b/ (rsim/ removed; sim_tree/ kept, 68 MB). review/ untouched (newest file 08:18:43, the review's).
  Outside these, only the phase driver's state.json and the P2 runner's files changed (driver/runner activity). The
  protocol lock, the drivers, queues, CARLA and the GPU were not touched; every python/pytest/sha256sum/diff process
  ran through p.sh (taskset 12-15, nice 19, ionice 3, one BLAS thread, CUDA hidden), max RSS 230 MB; slips recorded
  above (free -m, sed, read-only inspection commands, STOP probe write/rm in the scratch tree, ls/date during runs).
- 2026-11-15T10:16:21+0800 START (fix pass 2, review2/REVIEW.md GO_WITH_FIXES: M1 wrapper releases the lock unsealed,
  M2 P1 job files; S1-S8). registration.py --verify (10:09:49): manifest OK, seal framelease_v4/PROTOCOL.md OK, seal
  MANIFEST.sha256 OK. Backups of the reviewed versions in orig/*.before_fix2.* (sha256 equal to the review's table:
  apply_entry_stream.py 0f0cfda6, .diff 737a3e5c, apply_locked.sh 9c86ca20, post_check.py f2038c1f, RUNBOOK 75cb4c07,
  sim_tree.py 211a714b, A10_entry 9790c164, A10_spec b1de9f6a, AMENDMENTS2_DRAFT 03bfb7f4). Scratch: /tmp/A10A11/fix2/.
  Probe (/tmp/A10A11/fix2/probe): pgrep -f matches the bash -c processes whose script text holds the pattern (a
  literal pattern in the script would match the wrapper itself); pgrep -g 0 works (procps-ng 4.0.4); flock's command
  runs in the caller's process group.
- 2026-11-15T10:23:30+0800 EDIT apply_entry_stream.py (review2 proposal adopted with changes): M2 P1 job files of the
  sealed manifest registered (p1_driver.is_strict); S1 --apply needs the lock descriptor inherited from flock(1); S2
  newly registered = the unregistered manifest files whose sha256 the composed PROTOCOL.md cites, must equal the ones
  the template cites with {{sha256:...}} (refresh_baseline's rule); S3 SEC_START in the line check + both drivers'
  parsers on the composed text (entry read once, other titles and driver entries unchanged, new files first cited by the
  entry); S4 time not earlier than the last Sec. 13.2 stamp (pre-check and fill; a missing/doubled "### 13.2" heading
  STOPs cleanly instead of a traceback); S5 width 120 on the filled entry + check-mode preview; S6 cited files hashed
  once after --write-manifest, STOP when one differs from the new manifest; S8 sequential in-place counts, fsync,
  manifest difference printed right after --write-manifest. Own additions: changed lines of the in-place "new" texts
  at most 120 columns (A10 max 118, A11 max 120: pass); one clock reading per fill; the line "composed PROTOCOL.md
  sha256 <hex>" before the write (the wrapper seals after a failure only that text). pyflakes clean, widths <= 120.
  Check mode on the project, A10 (10:22): "check: pre-checks passed", 6.8 s, 18.6 MB.
- 2026-11-15T10:23:30+0800 EDIT apply_locked.sh (review2 M1/S7 proposal adopted with changes): trap '' INT TERM HUP;
  seal check before the copies (exit 96); one attempt_<time>_<pid>/ per attempt (mkdir, never reused) holding
  PROTOCOL.md, MANIFEST, SEAL, REGISTRATION.json and both baselines (post_check reads the phase baseline), apply.out and
  verify.out copied at the end; wait for registration.py children: pgrep -g 0 (this process group) and a python
  command line (the probe showed that a pattern in the script text matches the wrapper's own bash processes);
  failure: PROTOCOL.md unchanged -> manifest restored by temp file + rename; PROTOCOL.md = the composed text -> seal
  matches: 94; else --seal: 94; seal fails: roll back all four files by temp file + rename: 93; PROTOCOL.md neither ->
  kept as PROTOCOL.unexpected.md, rolled back (93) or, when sealed, left alone (92); roll-back fails: 92; final
  invariant: SEAL.sha256 not matching -> 92. bash -n ok; no quote inside the bash -c body; widths <= 120.
- 2026-11-15T10:23:30+0800 EDIT post_check.py: P1 driver ALERT/protocol_txn too (S8); refresh additions (S2): the
  sealed-manifest files outside the phase baseline before the amendment (attempt copy, else the current baseline while
  its refresh is pending) whose sha256 PROTOCOL.md cites must equal FILES[name] (A11: plus the A10 files pending at
  A11); after the refresh the baseline gained exactly these. pyflakes clean.
- 2026-11-15T10:23:30+0800 EDIT sim_tree.py: scratch base /tmp/A10A11/ (default --out /tmp/A10A11/fix2/sim_tree), one
  tree at a time (/tmp is tmpfs), trees removed at the end (--keep); D1 copies in attempt_*/; F1 now exit 94 sealed by
  the wrapper (no hand seal); new case H (H1 seal impossible -> 93, H2 foreign edit -> 93 + PROTOCOL.unexpected.md, H3
  roll-back impossible -> 92, H4 attempt dirs + post_check 3 -> refresh +8 -> 0 + gate_g1, H5 before-fix2 applier
  seals an empty file -> post_check fails); drv.py (refresh, g1) like review2's; D1_DECISION.json copied into the tree.
- 2026-11-15T10:30:10+0800 SIMULATION sim_tree.py run 1 (10:23:13-10:29:50, 397 s, max RSS 33 MB, /tmp/A10A11/fix2/
  sim_tree): ALL EXPECTED, 42 steps. A (A10 8 / A11 2 newly cited, parsers, G8 no wait), B, C, D (copies in
  attempt_*/), E 4x STOP + A10 sealed, F1 exit 94 sealed with the manifest the entry names (1ea365bc..., before
  4bfe7451...) and verification OK, F2 exit 95, G (TZ, 5 refusals, Beijing stamp 10:27, 4 template lines), H1 seal
  impossible -> 93 rolled back (state, REGISTRATION.json equal), H2 foreign edit -> 93 + PROTOCOL.unexpected.md, H3
  roll-back impossible -> 92, H4 94 then STOP; two attempt dirs with all copies; post_check 3 -> refresh +8 -> 0, g1
  done, H5 before-fix2 applier seals an empty file -> post_check exit 1. Finding of this run: in H3 the first roll-back
  step (PROTOCOL.md) succeeded and the manifest kept its bytes, so the seal matched again although the message read
  "PROTOCOL.md is not sealed" -> message split (next entry). Slip: python/awk edits of RUNBOOK.md, rerun_review2_sim.py
  and two free/du/ls ran while the simulation ran (no CPU or memory load of note).
- 2026-11-15T10:36:00+0800 EDIT apply_locked.sh: roll-back failure reported by the seal state after it ("ROLL BACK
  INCOMPLETE": a copy failed part-way, the seal matches again; "ROLL BACK FAILED": unsealed), exit 92 both; header
  rewrapped. sim_tree.py: H3 split into H3a (registration/ not writable: the roll-back stops at the manifest ->
  INCOMPLETE, seal matching) and H3b (framelease_v4/ not writable as well: stops at PROTOCOL.md -> FAILED, unsealed);
  inject mode lock_all_then_kill. bash -n ok, pyflakes clean, widths <= 120. RUNBOOK.md (in progress): header and state,
  Sec. 0 (registered files with the P1 job files; lines, widths, time, temporary file, lock, composed text, output;
  the wrapper steps 1-7, exit codes 92-98, the attention line), Sec. 1 (detached application, exit 92/93/94/98, the
  SIGKILL case with the driver's ALERT recovery, post-check), Sec. 3 (detached), Sec. 5 item 3.
- 2026-11-15T10:39:30+0800 SIMULATION sim_tree.py run 2, final files (10:31:35-10:38:37, 414.5 s, max RSS 33 MB):
  ALL EXPECTED, 43 steps (A 11, B 1, C 2, D 3, E 5, F 2, G 12, H 7): as run 1, and H3a "ROLL BACK INCOMPLETE" exit 92
  with the seal matching, H3b "ROLL BACK FAILED" exit 92 unsealed. Evidence: old sim_output/ renamed sim_output_fix1/;
  new sim_output/ (68 files: logs, summary.txt, sim_tree_run.out, drv.py, inject.py, the simulated PROTOCOL.md as
  PROTOCOL.after_A10_A11.simulated.md.txt; run-1 leftovers H3_* and the scratch applier copies not copied). Correction:
  the PROGRESS entry stamped 10:36:00 was written at 10:31 (stamp estimated, not read from the clock).
- 2026-11-15T10:54:30+0800 REVIEWER'S HARNESS rerun_review2_sim.py (10:39:21-10:53:47, 866 s, max RSS 34 MB; trees
  under /tmp/A10A11/applier/, one at a time, removed at the end; logs in review_rerun/review2_logs/, 133 files incl.
  expectations.txt, results.txt, rerun_review2_run.out): review2/review2_sim.py loaded unchanged; ALL EXPECTED, 74
  expectations PASS, 0 FAIL; every step id of the review's last run of each case present (R and K4b replaced by R2
  and K4R). The 14 steps that reproduced a defect now fail the review's defect check and pass positive log checks:
  P2 (P1 job file: check + wrapper STOP, the driver's pre-check still names it), K3 (exit 94, sealed, g1 done), K4
  race (no unsealed window), O1 (waited 3 s for the orphan, RESTORED, g1 done), L3 (--apply without the lock: STOP),
  T2 (06:30 STOP before --write-manifest), T3 + T4.7-4.9 (preview STOP in check mode and in the wrapper), T4.10
  (template STOP), T5 (empty file: STOP, RESTORED), S1 (SIGINT ignored, exit 0, g1 done), Y1 (cited file changed:
  STOP, manifest equal). X1-X14 on the files of this directory: all EXPECTED. R2: 94 then STOP, two attempt dirs with
  their own copies; K4R: a driver cycle during the recovery: done, next cycle done. Times: check 6.3-6.6 s / 18 MB,
  wrapper 15.7-20.1 s / 32 MB, post_check 3.4 s / 30 MB; lock held in one interval (0.0-15.7 s of a 15.7 s run).
- 2026-11-15T10:55:53+0800 TEST RUN apply_entry_stream.py final/A10_spec.json --tests (10:54:20-10:55:36, 76.4 s, max
  RSS 229 MB): pytest_analyze_v4.log 48 passed, 107 subtests (15.7 s); pytest_prop1_coverage.log 22 passed (20.0 s);
  pytest_figures_tables.log 50 passed, 422 warnings (25.2 s); pytest_verify_independent.log 28 passed, 20 subtests
  (13.8 s); all exit 0 (logs 9259c16e..., 7ecd626f..., 61c9b99b..., 786d01bc...). A11_spec.json --tests
  (10:55:44-10:55:53, 9.5 s, 93 MB): pytest_verify_table1_extra.log 71 passed, 67 subtests; pytest_review_r7b.log 14
  passed, 2 subtests; exit 0 (8c6be5f9..., 6524a120...). Counts equal "At drafting" of both entries.
- 2026-11-15T10:58:00+0800 CHECKS apply_entry_stream.diff regenerated (diff -u paper_tools/apply_entry.py, 2ddc1c8c...
  unchanged; 371 lines, 8e87f0c2...); check_drafts.py exit 0 "all checks passed", 5x "found 1x now";
  derive_inplace5.py --spec exit 0 "in-place text 5 equals the derived text"; evidence sha256sum -c exit 0;
  make_a11_spec --check equal; edit_draft --check verbatim; check_a11.py exit 2 (open: A10 not entered, re-review
  missing); pyflakes clean on the 10 scripts; bash -n ok; widths <= 120 in the changed scripts. Deviation 1 search
  (find -newermt '2026-11-15 09:15'): only review2/PROGRESS.md and this PROGRESS.md; neither records an execution of
  the aggregator or of the four A10 files on real data (review 2: file references only; this pass: scratch trees,
  parsers, the --tests runs). A10_entry.md, A10_spec.json and AMENDMENTS2_DRAFT.md unchanged (no review item asks for
  a text change; the draft holds the template verbatim).
- 2026-11-15T10:59:54+0800 EDIT RUNBOOK.md (125a2883...): header (review 2), state, Sec. 0 (applier changes incl. the
  P1 job files, lock, preview, widths, time order, composed text, output; wrapper steps 1-7; exit codes 92-98; the
  attention line), Sec. 1 (precondition 3 search -newermt '2026-11-15 11:05' with the statement on review 2 and this
  pass; tests 10:54-10:55; check mode 7 s / 19 MB; detached application; failure handling for exits 1, 92-98 and the
  SIGKILL case with the ALERT recovery; post-check with the refresh additions), Sec. 3 (detached; the pending A10
  refresh), Sec. 4 (fix pass 2 dry runs), Sec. 5 (items 3, 5, 6), Sec. 6 (sha256 of 24 files), backups. Widths: only
  the copied python one-liner (line 121) and table rows exceed 120.
- 2026-11-15T11:00:30+0800 FINAL CHECK check mode A10 on the project (11:00:11, 9.5 s, 18.7 MB): "check: pre-checks
  passed". review/end_check.py --since '2026-11-15 10:16': registration --verify OK; P1 baseline 153 and phase
  baseline 199 files equal the tree and the sealed manifest; framelease_v4 entries changed since 10:16: none; new
  __pycache__: none (3 dirs, 8 files, as before); empty files only .protocol.lock and offline/__init__.py. PROTOCOL.md
  ca54d359, MANIFEST 4bfe7451, SEAL b8d516d1, REGISTRATION c0ee0217, PIPELINE_STATE 73add832, P1 baseline df4435e1,
  phase baseline cfe58aa1: equal at start and end (no driver re-seal). No ALERT, protocol_txn, STOP or PAUSE file of
  either driver (only the resolved STOP.*.resolved.txt of earlier days); no .PROTOCOL.md.entrytmp; phase driver pid
  256142, driver.log unchanged since 06:48. Scratch /tmp/A10A11/fix2 removed (run-1 log kept as
  sim_output/sim_tree_run1.out); /tmp/A10A11/applier removed by the harness.
- 2026-11-15T11:01:17+0800 END (fix pass 2): registration.py --verify (11:01): manifest OK, seal
  framelease_v4/PROTOCOL.md OK, seal MANIFEST.sha256 OK; no driver re-seal during the pass. Written by this pass:
  a10r7b/apply_entry_stream.py (7d86e576), apply_entry_stream.diff (8e87f0c2), apply_locked.sh (1de9b701),
  post_check.py (7b08460b), sim_tree.py (59b7a83c), rerun_review2_sim.py (fdb0e3a1, new), RUNBOOK.md, PROGRESS.md,
  orig/*.before_fix2.* (backups),
  sim_output/ (new; the earlier one renamed sim_output_fix1/), review_rerun/review2_logs/, and the six test logs in
  outputs/framelease_v4/amendment_a10/ and amendment_a11/. Not changed: final/A10_entry.md, final/A10_spec.json,
  AMENDMENTS2_DRAFT.md, A11_entry.md, A11_spec.json, review2/ (the review's files), every registered file, PROTOCOL.md,
  the registration files, PIPELINE_STATE.md, the drivers' directories and queues. The protocol lock, the drivers,
  CARLA and the GPU were not touched; every python/pytest/sha256sum/diff/find process ran with taskset 12-15, nice 19,
  ionice 3 (registration --verify at start and end as constraint 4 states it), one BLAS thread, CUDA hidden; max RSS
  229 MB (the A10 tests), 34 MB in the simulations. Slips: python/awk edits and free/du/ls ran while sim_tree run 1
  ran, and one no-op shell call while the harness ran; read-only inspection commands (ls, cat, grep, awk, sed, stat,
  date, bash -n) and the file copies, moves and the scratch removal ran without the prefix; one PROGRESS stamp
  (10:36:00) was estimated (corrected above). Open: check_a11.py (not in this pass's files) describes the applier's
  registered set without the P1 job files (its result is unaffected; RUNBOOK Sec. 5 item 6).
