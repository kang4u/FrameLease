# Review of item A10R7B: Amendment A10 and Amendment A11 made ready

Independent adversarial review, 2026-11-15 07:31-08:20 (Beijing time). Nothing was applied: the protocol lock,
PROTOCOL.md, the registration files, the seal, the registered files, the drivers, their queues, CARLA and the GPU were
not touched.
Every process ran as `taskset -c 12-15 nice -n 19 ionice -c 3` with one BLAS thread and `CUDA_VISIBLE_DEVICES=''`, one
at a time, at most 230 MB RSS (most at 18-33 MB). Scratch trees: `/tmp/AMEND3_review/a10r7b/` only. No test-route data
was read.

Reviewed files (sha256 at review time; unchanged by this review):

| file (under `outputs/framelease_v4/build/AMEND2/`) | sha256 |
|---|---|
| `final/A10_entry.md` | `72b6d1d915b6fedac491692b1ffc74d4fb5de13641dfe7ba5620b2308dad3790` |
| `final/A10_spec.json` | `b1de9f6a976da98dc0da9da48fff5a1e2ec55512dfaac581ad7eb73a64335b0e` |
| `AMENDMENTS2_DRAFT.md` | `6d9a0ced76c96c9f9731c665f13d7811c4c249bae8c1420cac51c8213a51fe81` |
| `a10r7b/A11_entry.md` | `6a8bb75ec65a2e37088ee5976a8cad0f9db8a8ce16af6cc917adbba2b9ce987f` |
| `a10r7b/A11_spec.json` | `5fc36c01ba7e9bc4a91cca5bc881151f606a0fd19fac5ef5a94aa77ce6a7a682` |
| `a10r7b/apply_entry_stream.py` | `31e9bab339c2f094913aabec675562ebd9e0a0060ab38a308ca5bcf79060744d` |
| `a10r7b/apply_locked.sh` | `73b49d8ece76e2935532c852b61dc98d8b1eaebc4dd2bb0e78ea8a683b2ebe2a` |
| `a10r7b/derive_inplace5.py` | `4d0fff50e6484862bd2040ba2c54ea81d652834c761e48dcb3ac69d30fbaf106` |
| `a10r7b/check_a11.py` | `e2da1e856cb1b246f65c14a38bfda7f6fd3c99fbf9a05b849f7b5a7f44587e95` |
| `a10r7b/post_check.py` | `c92bce2558c020400062436d44e63539327484c3f61f71510bf5309381167b60` |
| `a10r7b/RUNBOOK.md` | `9cc693edbc52aa5cc924fdf78d360032dc7f2675b1780085410c54b98ae1cc85` |

## Verdict: GO_WITH_FIXES

The entry texts are right and complete in substance: finding 1 states the rule of the sealed `commit_audit.py` in the
words of E3; deviation 1 lists every execution of the aggregator and the four A10 files on training-route data from
2026-11-14 on that the records show; all 14 must_equal sha256 of both specs equal the tree; the fifth in-place text is
derived correctly from the sealed PROTOCOL.md; A11 is the next free name and its numbers, tolerances, definitions,
CLI and independence claims match `verify_table1_extra.py` and the R7B records; both entries apply cleanly on my own
scratch tree, the P1 and phase-driver parsers read them without an ALERT, no added prose line exceeds 120 columns and
no added line reads as a driver entry, heading or second amendment title. The tests reproduce.

One defect must be fixed before A10 is applied: the applier that the RUNBOOK prescribes protects only the P1 stage
driver's 153 registered files and never a registered file that is missing, so a change or removal of any of the 46
files registered after P1 (or the removal of any registered file) is sealed silently by the A10 or A11 transaction and
adopted by the phase driver (M1). The should-fix items harden the wrapper's failure paths and tighten two texts.

## Must fix

**M1. `a10r7b/apply_entry_stream.py` (and `paper_tools/apply_entry.py`) checks only the P1 stage driver's baseline and
never a missing registered file.** `base` is `p1_driver/registered_baseline.json` (153 files). The pre-check compares
those files with the sealed manifest and skips a file that does not exist (`(ROOT / k).is_file() and sha(...) != v`);
the post-manifest check (`changed`) compares those files only and skips a file that left the new manifest. The phase
driver's baseline holds 199 files; the 46 outside the P1 baseline are the A3 aggregator modules and tools
(`aggregate_v4.py`, `commit_audit.py`, `p2_jobs.py`, `p2_check.py`, `p3_rl.py`, `stress_bench.py`, `test_jobs.py`,
`test_freeze.py`, `check_smoke_ext.py`, `arms_ext/`), `phase_driver.py`, `start_phase_driver.sh`, the P1 job files
b04-b09 and their tests.
* Evidence (scratch trees, `review_sim.py`; logs in `logs/`):
  * Case D: `framelease_v4/analysis/commit_audit.py` changed before the A10 apply. `registration.py --verify` reads
    "manifest: 1 files differ", both seals OK; check mode "pre-checks passed"; `apply_locked.sh` exit 0, sealed;
    afterwards `--verify` reads "manifest: OK" (the changed file is in the sealed manifest); `phase_driver.
    refresh_baseline` keeps the file at its new sha256 (no ALERT). Control: `framelease_v4/arms/realized.py` (P1
    baseline) changed: STOP before `--write-manifest`, nothing changed.
  * Case D3: `framelease_v4/protocol/p3_rl.py` (the G4 tool) changed: sealed, `--verify` OK, the refreshed baseline
    holds the new sha256, so `require_registered_code` finds nothing pending, while PROTOCOL.md cites the new sha256
    nowhere. G4 would run the changed tool with no ALERT and no wait.
  * Case V: `framelease_v4/rl/RL_PROTOCOL.md` (P1 baseline) or `framelease_v4/arms_ext/tests/test_drift_guard.py`
    removed: sealed, exit 0; the new manifest omits the file, `--verify` reads OK and the refresh drops the file from
    the registered baseline.
  * The phase driver checks laundered and vanished registered files only inside its own transactions (its review fixes
    F1 and M3) and verifies the tree against the sealed manifest only at G0, at its own entries, G6 and G8; after a
    seal by this applier every one of these checks passes. The RUNBOOK's "manifest: OK" precondition is a manual check
    minutes before the locked apply (tests and check mode lie between), and for A11 it cannot hold when the re-review
    changes the unregistered R7B files ("2 files differ" is then expected and must be judged by hand).
* Fix, in `a10r7b/apply_entry_stream.py` (RUNBOOK Secs. 0, 1 and 3 use it):
  1. `base` = the files of `p1_driver/registered_baseline.json` united with those of
     `phase_driver/registered_baseline.json` (both exist now);
  2. pre-check: `reg_differ = [k for k, v in sealed.items() if k in base and (not (ROOT / k).is_file() or
     sha(ROOT / k) != v)]`;
  3. after `--write-manifest`: `changed = [k for k in base if k in sealed and new_man.get(k) != sealed[k]]` (changed or
     vanished).
  Item 1 is in `review/proposed_apply_entry_stream.diff` (with S3 and S4), items 2-3 are `VANISH_REPLACEMENTS` of
  `review_sim.py`. Tested on scratch trees: cases fix-D and V-fix stop before `--write-manifest` and change nothing;
  case fixAV (every proposed applier change with `proposed_apply_locked.sh`) applies A10 (newly cited: exactly the 8
  A10 files), then, after the phase driver's refresh, A11 (exactly the 2 R7B files); both seals verify, the parsers
  read both entries once, G8 waits for nothing (`max_new_registered` 8 and 2 still hold: the files are in neither
  baseline when cited). Then state the change in RUNBOOK Sec. 0 (the diff against `apply_entry.py`) and rerun
  `sim_tree.py`.

## Should fix

* **S1. `apply_locked.sh` restores the sealed manifest although PROTOCOL.md already holds the entry.** The restore runs
  when the applier failed, `apply.out` shows `registration --write-manifest` and no `registration --seal`. A kill
  between `os.replace` of PROTOCOL.md and the end of the seal subprocess fits that test. Case F2 (applier ended with
  `os._exit(137)` before `--seal`, a new file in the manifest scope): the wrapper RESTORED the old manifest while the
  A10 entry names the rewritten one (`cec7d5ce...`, 222 files); the hand seal of the RUNBOOK then verifies (manifest
  OK, both seals OK), and the sealed record names a manifest that is not the sealed one (`4bfe7451...`). The same
  happens for A11 whenever the re-reviewed R7B files changed. The applier's output is also block-buffered into
  `apply.out`, so after a real SIGKILL the grep may find nothing. Fix (tested in case fix-F2: consistent seal):
  `review/proposed_apply_locked.sh`: copy PROTOCOL.md next to the sealed manifest inside the lock; after a failure
  restore the manifest only when PROTOCOL.md is byte-identical to that copy; otherwise keep the rewritten manifest and
  print "seal now"; run the applier with `python -u`. In RUNBOOK Sec. 1 ("STOP" handling) replace "PROTOCOL.md is
  unchanged" by the two cases.
* **S2. `apply_locked.sh` exits 0 when its final `registration.py --verify` fails.** Case E: a registered file
  (`manipulation.py` of A3, or `realized.py` of the P1 baseline) changed between `--write-manifest` and `--seal`: the
  applier seals and exits 0, the wrapper prints "exit 0" while the appended verification reads "manifest: 1 files
  differ" (`post_check.py` then fails, so the RUNBOOK catches it one step later). Fix: exit 95 unless the appended
  verification reads "manifest: OK" and both seals OK (in `proposed_apply_locked.sh`; tested: case fix-E exit 95).
* **S3. The entry time is the caller's local time, labelled "Beijing time".** Case G: with `TZ=UTC` the A10 entry is
  sealed as "2026-11-14 23:57 (Beijing time)", eight hours early, before G1 / G2 (2026-11-15 06:42 / 06:43) above it
  and before A3 (06:40), which it depends on; nothing stops it (the drivers' own stamps check `%z`, the applier does
  not). Fix: `export TZ=Asia/Shanghai` in the wrapper and stop in the applier unless `time.strftime('%z') == '+0800'`
  (tested: fix-G).
* **S4. The applier's template check does not know the phase driver.** It refuses only `## `, the anchor and the P1
  entry form. Case H: a template line `* **G3 P2 data manifest** (2026-11-15 12:00, Beijing time). ...` passes the
  check, is sealed, and `phase_view` reads it as the G3 entry inside A11. The real templates hold no such line
  (`check_drafts.py`, `check_a11.py` and case A confirm), so this is hardening: refuse lines that match
  `phase_driver.ENTRY_RE`, `phase_driver.AMEND_RE` (after the title) or a driver heading (in the proposed diff;
  tested: fix-H STOP). Likewise check before `--write-manifest` that every `{{sha256:...}}` file except the manifest
  exists (the builder's case C: a missing review file crashes the fill after `--write-manifest`).
* **S5. A temporary file of a killed applier is sealed into the manifest.** `apply_entry` writes
  `framelease_v4/.PROTOCOL.md.entrytmp`, inside the manifest scope. Case T: with that file left over, a repeated apply
  lists it in the new manifest, renames it away, and seals a manifest that names a missing file ("manifest: 1 files
  differ ... unreadable" until the next seal; wrapper exit 0). Fix: the applier (or the wrapper) stops while
  `framelease_v4/.PROTOCOL.md.entrytmp` exists; add it to RUNBOOK Sec. 1, precondition 1.
* **S6. Driver transaction files are checked outside the lock only.** RUNBOOK precondition 1 lists
  `phase_driver/{ALERT.txt,protocol_txn.json}` with `ls`; the applier checks only the P1 driver's. Check both drivers'
  files inside the lock before the apply (in `proposed_apply_locked.sh`: exit 96).
* **S7. A10 deviation 1, two precision gaps.** (a) Its lead sentence says every execution on real data is listed and
  "(all on 2026-11-14)". On 2026-11-15 (about 01:25-03:33) item FILL0 and its review ran `analyze_v4.py` and
  `figures_tables.py` on synthetic analyses through the harness of `test_figures_tables.py`
  (`FrameLease_Paper_v4/scripts/tests/helpers_fill.py`, `build/FILL0/make_key_coverage.py`, scratch directories under
  /tmp); `figures_tables.py` read the offline outputs written before registration there (its `--offline` default), the
  same real input the deviation already names for its tests. Add them in one sentence (or restrict the lead sentence
  to training-route data and say that test-like runs read the offline outputs) and drop "(all on 2026-11-14)". (b)
  The re-audit of 14:09 / 14:10 also ran the earlier module `commit_audit.py` 96dd22c4 on the same 48 runs as its
  cross-check (`step0_reaudit/reaudit.py --before-module`); say "the earlier and the current `commit_audit.py`".
* **S8. A11 "Development data" omits the review runs and has no completeness precondition.** The R7B review ran
  monkeypatched variants of the reviewed script on the full P1 snapshot, 180 run directories (2026-11-14 23:22 to
  2026-11-15 00:20; `/tmp/review_R7B`, `build/R7B/review/logs/var_*`; `build/R7B/review/PROGRESS.md`); the bullet
  names only `build/R7B/PROGRESS.md`, `build/R7B/dev/verify_p1*/` and /tmp. The re-review will add runs. Fix: name the
  review runs with their times and directories, and add to RUNBOOK Sec. 3 a precondition like A10's deviation-1 check:
  every execution of `verify_table1_extra.py` on real data up to the application (the re-review's included) is in the
  bullet, with the end time adjusted.
* **S9. RUNBOOK Sec. 3, precondition 1 conflicts with the deadline rule.** It requires `post_check.py A10` exit 0,
  which needs the phase driver's baseline refresh; while the driver is stopped by `STOP` (the deadline rule of the same
  section) it stays at exit 3. State that exit 3 with only the refresh pending is accepted while the driver is stopped.

## Verified (no change needed)

* Registration at start (07:31) and end (08:17): `registration.py --verify` manifest OK and both seal lines OK; P1
  baseline 153 and phase-driver baseline 199 files equal the tree and the sealed manifest (`end_check.py`);
  PROTOCOL.md `ca54d359...`, MANIFEST `4bfe7451...`, SEAL `b8d516d1...`, REGISTRATION `c0ee0217...` unchanged during
  the review (the step-3 transaction and G1 / G2 that the builder reports predate my start). Nothing under
  `framelease_v4/` changed; no new `__pycache__`; the only empty files are the pre-existing `.protocol.lock` and
  `offline/__init__.py`. Outside `review/`, only the phase driver's and the P2 runner's own files changed in the
  project during the review.
* Finding 1: the rule sentence equals E3 and the sealed A3 departure 6 (PROTOCOL.md lines 2370-2373) and
  `commit_audit.py` 7439a4ea (`null_margin_explained`; a commit event keeps margin_unrecorded). `agg_now` and
  `agg_snap_2203` ran `aggregate_v4.py` ee13c90b with `commit_audit.py` 7439a4ea: 184 and 194 audited runs, PASS.
  The re-audit numbers (0 violations, 47 PASS, 1 NO_LOG) equal `build/AGG/PROGRESS.md` step 173.
* Finding 2: `km_driven` of `v4p1smoke_fl_heuristic_E5_d10_k1.0_s11_r18305` is 0.0 in `agg_p1`, 0.001 in `agg_now`
  and `agg_snap_2203`.
* Deviation 1 against the records of R4 (steps 6, 22, 36, 53, 68, 70, 93: 07:35 load check; 07:40, 07:47, 08:05,
  08:14, 08:16, 08:42), R5 and its review (08:54-09:14), R6 (09:25 on; 09:45 `/tmp/R6/train_run`; 10:09 D1; 10:10;
  10:29; 11:25), R7 (probe records frozen 11:33:30 and 11:57:47; `agg_p1` 11:46-11:50; verify 11:50, 12:00, 12:31),
  AGG steps 171-173, R7B (14:50:41-14:55:39 on `build/R7/dev/p1_snapshot`; 22:03:57-22:08:13 on the 22:03 copy). The
  AGG0 recount, the R7B review scripts and `r2_margin_null.py` import no analysis module; the review test files of
  AGG, AGG0, R4-R7 read synthetic data or outputs only. Complete for training-route data except S7.
* must_equal: the 8 A10 files and the 3 reused coverage files (equal to gate2 `config.json`) and the 3 A11 files
  equal the tree. The R7B review test file differs from the reviewer's original only by the 8 removed
  `expectedFailure` marks and one docstring sentence.
* Fifth in-place text: `derive_inplace5.py --spec` equals the spec on the sealed PROTOCOL.md and on
  `/tmp/AMEND3/tree`; on a copy with the status paragraph twice it exits 1. No overlap among the 5 A10 in-place texts
  (no "old" inside another "new" or "old"). Using the whole paragraph and the entry's clause is consistent with the
  entry's In-place bullet; the RUNBOOK states both differences from APPLY_PLAN2.
* Case A (my own scratch tree, the builder's applier and wrapper): A10 check passed, sealed, manifest unchanged (221
  files), newly cited exactly the 8 files; parsers without ALERT, P1 and phase entries unchanged, A10 read once, every
  A10 file first cited by A10, `analysis_registration` without wait, a later G3 entry lands in the phase block above
  A10 and is read; refresh +8. A11 (stand-in review file in the tree): sealed, newly cited exactly the 2 R7B files,
  read once, first cited by A11, refresh +2. 0 added prose lines over 120 columns (table rows only, as in A3), no
  driver-entry, heading, amendment-title or column-0 list line. Case B: A11 first stops (in-place 0 times). Case C: an
  "old" text twice in a sealed PROTOCOL.md stops before `--write-manifest`. F3: a truncated PROTOCOL.md stops at the
  seal check. F1 (killed before the seal, nothing in scope changed): the hand seal gives a consistent state.
* Tests on my test tree (copies of the data the tests read or try to write): A10 48 passed / 107 subtests, 50 passed
  (422 warnings), 28 passed / 20 subtests; A11 71 passed / 67 subtests, 14 passed / 2 subtests; `test_prop1_coverage.py`
  22 passed in the project tree (in the tree one test compares a recorded relative input path that the
  `outputs/framelease_v3` link turns absolute). The counts equal the builder's logs and the "At drafting" texts.
* A11 content: Sec. 7.2 (R_cond "to the table notes or the text"), Secs. 9.12, 9.13 quoted correctly; tolerances
  (counts exact; 1e-6; episode mean 1e-9; grid 1e-4 / 1 ms; bounds |H - V_suf| < 1e-3 s), definitions (d_safe 0.5 m,
  0.05 s grid, bisection to 1e-4 s, V_suf = clip(V - 0.5, 0, 2.5), miss H > V_suf), guard (fail closed, exit 4,
  `--runs-csv-values` refused under 'final', test options), CLI options and the `status` field equal the docstring and
  code; imports are the standard library and numpy; `review/scripts/blocks.py` rerun: only import lists shared.
  Numbers equal the R7B outputs: 180 / 179 / 12,259 / 136 / 1 (fast_only r1792 EIR 0.2282 vs 0.2063), summary.json
  3,759 / 0, F1 19 runs (38 end-censored, 2 missed conflicts), 0 unexplained, AGREE 25,746 / 25,746 / 20,242,
  mutants 110 / 110, `build/R6/dev_inputs/analysis*` synthetic.
* `check_drafts.py` exit 0 (5 in-place texts once), `check_a11.py` exit 2 (A10 not entered; re-review missing),
  `make_a11_spec.py --check` equal, `edit_draft.py --check` verbatim, `evidence_sha256.txt` OK, the RUNBOOK sha256 table
  (21 files) OK. The phase driver locks with `fcntl.flock`, the same lock as `flock(1)` in the wrapper.

## Observations

* The builder's check-mode run of `paper_tools/apply_entry.py` at about 07:04 reached 5.8 GB RSS (whole-file read of
  the 5.9 GB registered checkpoint) while a P2 job ran; recorded by the builder, no OOM followed. The RUNBOOK now uses
  the streaming copy for check mode and `--apply`.
* After A10, the phase driver's later gate entries are inserted in its own block, above A10 and A11 in the text but
  later in time (case A). This is the drivers' block layout (as for the P1 block before A3), not a defect.
* F1 of A11 (the registered `realized.py` drops the last actor-log row) will make the final recomputation DIFFER on
  EIR values; RUNBOOK open issue 2 asks for the decision before the analysis freeze. That decision (an amendment of
  `realized.py` or a reporting rule) belongs before any test-route run is analysed.
* Reviewer slip: one `python3 -c "print(1)"` (system Python, no output) ran without the prefix at 07:43.

## Files of this review

`review/PROGRESS.md`, `review/REVIEW.md`; `review/review_sim.py` (scratch-tree harness, cases tests, A-H, V, T, D3,
fix, fixAV); `review/end_check.py` (start / end check); `review/proposed_apply_locked.sh` and
`review/proposed_apply_entry_stream.diff` (tested fixes of M1 item 1, S1, S2, S3, the template part of S4 and S6;
M1 items 2-3 are `VANISH_REPLACEMENTS` in `review_sim.py`; S5 and the placeholder check of S4 are not drafted);
`review/logs/` (every case's output and summary JSON, the test logs of the test tree,
`realtree_pytest_prop1_coverage.log`, `check_drafts.out`, `check_a11.out`, `blocks_now.log`, `end_check_*.log`, the
simulated PROTOCOL.md after A10 and A11 as `.md.txt`). Scratch: `/tmp/AMEND3_review/a10r7b/`.
