# Review of item Step3 (APPLY_PLAN2 Sec. 3: A3 + A9 + A7b + A4 + operational addition, one manifest, one seal)

Reviewer: independent, adversarial. Date 2026-11-15 (Beijing time). Nothing of the builder was edited; everything
this review wrote lies in `outputs/framelease_v4/build/AMEND2/step3/review/` and under `/tmp/AMEND3_review/`.
Every process ran as `taskset -c 12-15 nice -n 19 ionice -c 3`, `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
OPENBLAS_NUM_THREADS=1`, `CUDA_VISIBLE_DEVICES=''`, one at a time, largest 0.9 GB (one stray `python3 -c` of a
JSON key list ran without the prefix, logged in `PROGRESS.md`).

**Verdict: GO_WITH_FIXES.** One must-fix (M1). The transaction is correct on every normal path and on every
injected failure the builder tested; it is not all-or-nothing when SIGTERM or SIGHUP reaches the whole process group
of `amend_step3.sh` during the locked part, which is what stopping a background task of the coordinating session's
tool, a `kill` of the group or a scope stop sends. Of the should-fix items, S1, S2, S3 and S6 are small code changes
best made together with M1; only S4 changes entry text (one path in A7b).

## 1. Must-fix

### M1. A signal to the process group during the locked part leaves the tree half-applied, without a STOP line

Evidence (`sim/case_b7_groupkill.sh`, `sim/case_b7b_groupkill.sh`; logs in `logs/sim/B7*` and the journals in
`logs/sim/journal_B7a`, `journal_B7c`; the scratch tree after the fake P1 end, an unregistered file changed so that
the new manifest differs, as in the builder's cases 04-06):

| case | signal to the group of `amend_step3.sh` | at journal step | result |
|---|---|---|---|
| B7a | SIGTERM | `post_manifest_check` | journal ends at `failed`; no restore; `MANIFEST.sha256` is the new manifest; `seal .../MANIFEST.sha256: CHANGED`; no PASS/STOP line |
| B7c | SIGTERM | `protocol` | PROTOCOL.md holds the five entries, unsealed; both seal lines CHANGED; no PASS/STOP line |
| B7d | SIGHUP | `post_manifest_check` | as B7a |
| B7b | SIGINT | `post_manifest_check` | restored, exit 1, STOP line (tee and bash survive SIGINT) |

`step3_txn.py restore --work <txn>` brings the sealed state back in every case (both seal lines OK).

Cause. `amend_step3.sh` pipes all output through `exec > >(tee -a ...)`. A SIGTERM or SIGHUP to the group ends
`tee` and `bash` at once. Python's handler raises `Stop` as designed, the `except Stop` branch writes the journal
step `failed` and then calls `say(...)`, whose `print` to the dead pipe raises `BrokenPipeError` before `restore()`
runs; the process ends with the tree half-applied. The builder's case 06b sends SIGTERM to the Python process only
(`os.kill(os.getpid(), ...)`), so it never exercised this path. RUNBOOK deviation 3 ("a signal (SIGTERM, SIGINT,
SIGHUP) before the seal is such a failure", i.e. restored) is therefore false for SIGTERM and SIGHUP, and the
RUNBOOK's exit-code table never triggers because `bash` itself is gone. The coordinating session reaches this path:
`sim/signal_probe.sh` (a `bash` parent and a Python child that log the signals they receive) shows that the Bash
tool moves a command past its time-out into the background, and that stopping a background task (as happens when a
session turn ends with the task still running) sends SIGTERM to the whole process group, parent and child at once
(`/tmp/AMEND3_review/signal_probe.log`).

Fix (all four parts):
1. `step3_txn.py`: `say()` never raises (catch `OSError`; after the first failure redirect fd 1 and 2 to
   `/dev/null` and append every later message to `<work>/step3_txn.log`, which Python writes itself). In both
   failure branches of `locked()` run `restore()` before any message (journal step, then `restore`, then the
   messages), so that no output error can skip it.
2. `amend_step3.sh`: start the log process immune to the group signals,
   `exec > >(trap '' INT TERM HUP; exec tee -a "$WORK/amend_step3.log") 2>&1`, and `trap '' INT TERM HUP` in
   `bash` from the lock on, so that `bash` waits for the helper, prints PASS/STOP and releases the lock.
3. Simulation: add the four group-signal cases above (`setsid`, `os.killpg` after `post_manifest_check` and after
   `protocol`); each must end restored (exit 1, both seals OK) with a STOP line.
4. RUNBOOK step 3: start the transaction detached in its own session, so that no task stop or end of a session
   turn can signal it (`setsid nohup taskset -c 12-15 nice -n 19 ionice -c 3 bash $S/amend_step3.sh > $S/step3.out
   2>&1 < /dev/null &`), then wait for the PASS/STOP line of `$S/step3.out` (the lock wait alone may last 600 s, the
   tool's longest time-out); add the row "no PASS/STOP line (interrupted)": read `txn_<time>/journal.json`; before
   `sealed`: the `restore` command (under the lock, S6); `sealed` or later: the `postcheck` command.

## 2. Should-fix

S1. **The locked part re-checks no input, and nothing lies between the post-manifest check and the seal.**
   `must_equal`, the OP `must_equal` and the 38 reviewed A3 values are checked in the pre-check only; the verdict
   is stale by the pre-check's duration (12 s) plus up to 600 s of lock wait. Evidence (`sim/case_b2_regfile.sh`,
   `sim/case_b5_b6.sh`):
   * B2a: `framelease_v4/protocol/p1_driver.py` (P1 baseline) changed after `post_manifest_check`: the transaction
     seals the five entries and ends with exit 3 ("sealed, but a registered file does not verify");
   * B2b: `framelease_v4/analysis/commit_audit.py` (one of the 40) changed after `filled`: sealed, exit 3;
   * B2c: the same file changed between `post_manifest_check` and the fill: STOP and restored (the count of newly
     registered files drops to 39), as designed;
   * B5: `locked` run alone with an altered test log: the altered log is cited and sealed.
   Fix: call `check_inputs()` at the start of `locked` (under the lock), and directly before `--seal` hash every file
   of the registered baseline, the P1 job files and the 40 newly registered files against the new manifest, and
   every `must_equal` file against the spec; any difference raises `Stop` and restores. Exit 3 then covers only a
   change inside the instant between that check and the seal.

S2. **P1 job files are not checked.** Both drivers treat every file under `outputs/framelease_v4/p1_jobs/` as
   registered (`p1_driver.is_strict`; phase driver "Registered files"), and the P1 entries cite their sha256. The
   pre-check checks only the seal lines and the 153 baseline files; the manifest files outside the baseline and the
   40 are 10 A10 / R7B development files and 15 P1 job files (`b04`-`b08` `.jsonl`, `.stage.json`, `.check.json`; `b09`
   follows), and APPLY_PLAN.md Sec. 3 step 1 admits only development files among the differing manifest files.
   Evidence (`sim/case_s_extra.sh`, X1; the scratch `p1_jobs/` made a real copy): `b08_age_s1.jsonl`, whose sha256
   `1cb6404a...` the age_s1 entry cites, changed after the fake P1 end. The pre-check reports no problem, the
   transaction PASSes, the new manifest seals the file at `66c8eb2b...`, `registration.py --verify` reads OK and
   `phase_driver.py --dry-run` passes G0: the change becomes the sealed state and no later check can see it. Fix:
   in the pre-check and again after `--write-manifest` (the step-3.2 check), compare every manifest file under
   `outputs/framelease_v4/p1_jobs/` with the sealed manifest as well (the drivers' `is_strict` rule); a difference
   stops the transaction.

S3. **The time stamp is not validated.** `--datetime` is checked for its format only (`\d{4}-\d{2}-\d{2}
   \d{2}:\d{2}`). Evidence (`sim/case_b4_time.sh`): B4a `--datetime '2026-11-14 00:00'`, earlier than the P1
   driver's "D1 summary" entry (2026-11-15 04:59 in the scratch), and B4b `'2026-13-45 99:99'` both seal (exit 0)
   and `phase_driver.py --dry-run` passes G0. Sec. 13.2 holds its entries in the order of application, each with its
   date and time; a wrong stamp in a sealed entry needs another amendment to correct. The default (the time the lock
   is taken) is correct; the RUNBOOK offers `--datetime` without a constraint. Fix: parse with
   `time.strptime(when, '%Y-%m-%d %H:%M')`, and refuse a stamp earlier than the latest `YYYY-MM-DD HH:MM` stamp of
   Sec. 13.2 or later than the current time.

S4. **The A7 entry does not name the directory of its test log.** The filled A7b entry reads "34 passed in
   30.38s (`pytest_stress_bench.log`, `4ca00fbd...`)"; `outputs/framelease_v4/amendment_a7/` appears nowhere in it
   (A3 names `outputs/framelease_v4/amendment_a3/` in its Tests bullet; A7b has no such clause). Fix: in the A7b
   draft, write `outputs/framelease_v4/amendment_a7/pytest_stress_bench.log` (log it in `build/AMEND/PROGRESS.md`),
   then `make_step3_spec.py` and the pre-check.

S5. **G1 wording.** `write_d1_decision.py` writes `"by": "coordinating session"` by default; the phase driver then
   enters "... decided 2026-11-15T05:07:32+0800 by coordinating session, on the D1 summary ..." (R13 dry run). The
   driver's own wording without the key is "by the coordinating session". Fix: default `--by` to
   `the coordinating session` (or omit the key), and the RUNBOOK step 5 commands accordingly.

S6. **`restore` is unguarded and runs without the lock.** `step3_txn.py restore` refuses only when the journal of
   the directory it is given says `sealed` or later. Evidence (`sim/case_s_extra.sh`, X2): after a later
   transaction had sealed, `restore --work <the directory of B1b, an earlier transaction that had been restored>`
   copied the older PROTOCOL.md, MANIFEST.sha256, SEAL.sha256 and REGISTRATION.json back, exited 0 with both seals
   OK, and left no amendment in PROTOCOL.md: one wrong directory name silently undoes a sealed transaction. The
   RUNBOOK's restore commands (exit 2, exit 137) also run without `framelease_v4/.protocol.lock`. Fix: `restore`
   proceeds only when the current PROTOCOL.md is the journal's `copied` or `composed`/`protocol` value and the
   current manifest is the journal's `copied` value or the one its `manifest` step wrote (else STOP, naming the
   files); `restore` takes the protocol lock itself (or the RUNBOOK prefixes it with `flock -w 600
   framelease_v4/.protocol.lock`).

S7. **Decision before step 3 (builder's open issue, endorsed).** AGG0 review should-fix 2 (check lease_s = H_bar
   for a `horizon_cap` null margin) and 4 (exclude `VL.INVALID_REASONS` from the n_relevant-0 case) are optional
   hardenings of `commit_audit.py`. Once step 3 registers the file, either one is an amendment that installs the file
   under the lock. The coordinating session decides before running step 3; if made, E3 and A10 finding 1 state the
   added condition, and the A3 review record gains a row.

## 3. Requirements checked (what holds)

* (a) Step 0 bookkeeping.
  * `commit_audit.null_margin_explained` (7439a4ea): `no_relevant_agents` first (n_relevant 0, else reason
    `no_relevant_agents`), then reason `horizon_cap` and n_computed not None and 0; `audit_records` flags a null margin
    only when the rule returns False; a commit event (no record) gives None (margin_unrecorded). This is APPLY_PLAN2
    Sec. 5 item 1, the E3 text and A10 finding 1 word for word.
  * The A3 draft carries the review record (F3 in the Cause, F4 in the appendix): the step 1/5/6/7 values equal the
    `CHANGED` pins of `review_prereq/test_review_prereq.py` and the AGG0 values equal the chain of the AGG0 review
    (Sec. 6 item 1); both reviews say GO. `review/check_spec.py`: the 38 A3 files equal their last reviewed value.
  * `test_review_prereq.py`: the pin change keeps the step 1/6 values in comments, adds `AGG0_A3_LINES`, admits the
    km floor in the scope test, and is logged in `build/AMEND/PROGRESS.md` with its reason. Rerun: 19 passed, 26
    subtests (18.8 s, 133 MB; `review/logs/pytest_review_prereq.log`).
* (b) E1-E4 in `build/AMEND/AMENDMENTS_DRAFT.md` equal the APPLY_PLAN2 texts (diff against
  `step3/orig/AMENDMENTS_DRAFT.before_step3.md`). F1: the cited report holds 1000 states at kappa 1.0, three
  networks, share admitted 1.0 from delta 0.01 on, 0 admitted actions with bound >= D*, `floor_check` mismatch 0
  (read from the JSON). F2 restates `stress_bench.NOTES['S2_relative']`. F5 and the F3 line break change no word.
  `check_drafts.py` on the project: exit 0, "all checks passed" (`review/logs/check_drafts_real.txt`). The step-3
  pre-check on the project (read only, `--precheck-only --work /tmp/AMEND3_review/real_precheck`): both seal lines
  and the manifest OK, the 153 baseline files unchanged, `check_drafts.py` exit 0, dry composition 40 files; exactly
  four problems, all of them the end of P1 (P1_DONE.json absent, `p1_driver.py` pid 27145 alive, `driver.lock` live,
  no "Tuning freeze" / "D1 summary" entry; `review/logs/real_precheck.out`).
* (c) Test logs: the six logs end with no failure and are newer than the code they cover; OP `must_equal` 4 of 4,
  step-3 `must_equal` 66 of 66 (`review/check_spec.py`). The E4 file set collects 34 + 15 + 10 + 11 + 11 + 2 = 83
  tests; the whole directory would add the A10 and R7B files (48 + 50 + 22 + 28 + 71). Rerun on the project tree,
  read only, with the plan's commands (`review/sim/run_tests_real.sh`, logs in `review/logs/`):

  | log | builder | rerun |
  |---|---|---|
  | analysis (E4 file set) | 83 passed, 103 subtests | 83 passed, 103 subtests (1.3 s, 61 MB) |
  | arms_ext | 38 passed | 38 passed (135 s, 781 MB) |
  | protocol tools | 194 passed, 21 warnings | 194 passed, 21 third-party deprecation warnings (288.5 s, 892 MB) |
  | phase driver | 24 passed | 24 passed (164 s, 51 MB) |
  | review phase | 6 passed | 6 passed (68 s, 50 MB) |

  A first rerun from a scratch copy is void: in that layout `interim_guard` resolves `route_split.json` through the
  `outputs/` symlink to the project path, which the scratch manifest does not hold (26 failures of
  `test_aggregate_v4.py`, all from `GuardRefused ... manifest entry None`: 24 raised, 2 as the CLI's exit 4); the
  project tree is the place these logs are defined for.
* (d) The transaction implements steps 1, 3 and 4: the pre-check list, the copies, `--write-manifest --force`, the
  step-3.2 check with restore, one time stamp, the fill by `fill_entry.py`, the rewrap (words unchanged), the parser
  checks of both drivers, the seven in-place texts in order, the insertion order A3, A9, A7, A4, OP before the anchor,
  the 40 newly registered files, the atomic write, seal and verify, and the post-checks. The six documented
  deviations are sound, except the claim of deviation 3 for SIGTERM and SIGHUP to the group (M1); deviation 1 (A4's
  in-place texts with A3, A9 and A7b) is required by the A4 entry and APPLY_PLAN.md Sec. 4. The in-place texts the
  builder composed where the drafts describe them in prose (Sec. 8.6 layout, the S2 "Supplementary" paragraph) state
  exactly the layout of A3's "Details" and the A7b wording.
* (e) Simulation rerun on `/tmp/AMEND3_review/tree` (own scripts `review/sim/`): R10, the whole transaction, PASS
  in 19.6 s (7 s under the lock), 42 MB. `review/sim/verify_result.py` on its result: six in-place hunks and one
  insertion directly before the anchor; 521 added lines, none of them a non-table line over 120 columns; no
  placeholder left; the five titles carry the one stamp; the five manifest clauses cite the sealed manifest (221
  files); 60 path / sha256 pairs of the entries equal the files; exactly the 40 expected files become registered and
  no other manifest file is cited. Post-checks: step 3.2 OK, both seals OK, G0 passed, G1 waiting for
  `D1_DECISION.json`, G5 plan `['s3', 's2', 's2_relative', 's1']` with `--grid relative`, `check_drafts.py` exit 0.
  R11: a second run stops at the pre-check (7 problems: the five entries exist).
* (f) `write_d1_decision.py` (R12): refuses a rationale that names its writer, an empty one, 4001 characters, a
  decision other than continue / stop, a missing P1_DONE.json and a second decision; `--dry-run` writes nothing;
  the write is a temporary file plus rename in `phase_driver/`; the JSON has the APPLY_PLAN2 schema and the D1
  summary sha256 that the "D1 summary" entry cites. R13: `phase_driver.py --dry-run` then shows G0 passed and G1
  "dry" with the G1 entry text, and writes nothing.
* (g) RUNBOOK: complete for the normal path and for the exit codes of a surviving `bash`; the gaps are M1 part 4,
  S5 and S6.

## 4. Break attempts (scratch tree, `/tmp/AMEND3_review/`)

| case | attempt | result |
|---|---|---|
| B1 | an in-place "old" text twice (the Sec. 8.3 lead sentence duplicated, scratch re-sealed) | pre-check STOP "found 2 times"; `locked` alone STOP, restored, both seals OK |
| B2a-c | a registered file changed between the manifest and the seal | see S1 |
| B3 | a partial write (`ulimit -f 200`: `PROTOCOL.new.md` cut at 204,800 bytes) | `OSError: File too large`, STOP, manifest restored, PROTOCOL.md untouched |
| B4a-b | a time stamp before the D1 summary entry; an impossible date | sealed: see S3 |
| B5 | a filled line over 120 columns (longer pytest summary) | the bullet rewrapped, words unchanged, no line over 120 |
| B6a | a line in A9 that `p1_driver.ENTRY_RE` reads as the `heur_s1` entry | STOP "A9: line 19 reads as a driver entry", restored |
| B6b | a line in A4 that `phase_driver.AMEND_RE` reads as Amendment A12 | STOP "reads as an amendment title", restored |
| B6c | a line in A3 that `phase_driver.ENTRY_RE` reads as the G1 entry | STOP "reads as a driver entry", restored |
| B7a-d | a signal to the process group in the locked part | see M1 |
| X1 | a P1 job file changed after P1 | see S2 |
| X2 | `restore` with the directory of an earlier transaction | see S6 |
| R10-R11 | the whole transaction, then a second run | PASS (section 3 (e)); the second run STOPs at the pre-check |

## 5. Notes (no action required for step 3)

* RUNBOOK step 6 is exact: `review/sim/env_compare.py` finds that this tool's shell carries the 138 variable names
  of the running P1 stage driver (pid 27145) with equal `PATH`, `HOME`, `LANG` and `LC_*`; the only differences are
  the four names exported for the one-thread runs, which `env -u` removes. The running closed-loop job adds only
  names from `linux/env.sh` and the runner.
* The exit-1 STOP text ("PROTOCOL.md and MANIFEST.sha256 are restored and both seals verify") is printed also when
  `locked` stops before taking its copies (for example a PROTOCOL.md that is no longer sealed); nothing changed then,
  but the seals need not verify. Word the message from the journal's last step.
* `fill_entry.py` and `apply_entry.py` read any summary that contains "failed" (also "xfailed") as a failure:
  conservative; no current log has an expected failure.
* RUNBOOK row "sha256 ... != ... (prepared / OP_spec.json)": for one of the four OP files, `final/OP_spec.json`
  "must_equal" is updated after the review of the change before `make_step3_spec.py` (which refuses until then).
* `sim_output/a10_inplace5_suggestion.json` uses the "new" wording of `final/A10_spec.json` ("the figure and table
  generator and the independent verification script are registered by Amendment A10"), not the paraphrase of
  APPLY_PLAN2 Sec. 4 step 1; the A10 spec governs (A10 item).
* review_prereq should-fix 1 (PIPELINE_STATE line 47, idle band 0.425) and 6 (supplementary S2 report on the
  test-freeze checklist) stay with the coordinating session.

## 6. Constraint checks

* Start (04:45): `registration.py --verify` manifest OK, both seal lines OK; `registered_baseline.json` 153 files,
  none differs (`review/check_baseline.py`).
* End (05:25, `review/logs/final_checks.out`): manifest OK, both seal lines OK; 153 baseline files, none differs;
  PROTOCOL.md `a848a349...`, MANIFEST `4e424763...`, SEAL `10f07459...`, REGISTRATION `13b19e7d...` unchanged during
  the review (the P1 stage driver did not re-seal; it last sealed at 04:21 with its age_s1 entry, before the review).
* Nothing under `framelease_v4/` changed during the review; under `outputs/framelease_v4/` only the P1 stage driver's
  `driver.log`, `pipeline_state.json` and the `tuning/age_s2` runs; no `__pycache__`, `.pyc` or `.pytest_cache`;
  the only empty files under `framelease_v4/` are the pre-existing `.protocol.lock` and `offline/__init__.py`; no
  `phase_driver/` directory. The runner, the P1 driver, their queues, CARLA and the GPU were not touched (the
  environment comparison read `/proc/<pid>/environ` only).
* No test-route data was read (Sec. 9.11): the scratch runs used the fake P1 end and synthetic decisions; the test
  reruns are the plan's own suites.

## 7. Files of this review

* `REVIEW.md` (this file), `PROGRESS.md`.
* `check_baseline.py` (registered baseline against the tree), `check_spec.py` (specs, `must_equal`, the six logs).
* `sim/`: `make_scratch_review.sh`, `fake_p1_end_review.py` (the builder's, guard moved to `/tmp/AMEND3_review/`),
  `common.sh`, `case_00_setup.sh`, `case_b1_twice.sh`, `case_b2_regfile.sh`, `case_b3_partial.sh`,
  `case_b4_time.sh`, `case_b5_b6.sh`, `case_b7_groupkill.sh`, `case_b7b_groupkill.sh`, `case_r10_full.sh`,
  `case_r12_d1.sh`, `case_s_extra.sh`, `watch_and_act.py`, `wait_pgroup.py`, `verify_result.py`, `signal_probe.sh`,
  `env_compare.py`, `run_tests_real.sh`, `run_tests_scratch.sh` (the void scratch rerun), `final_checks.sh`.
* `logs/`: the test reruns, `check_drafts_real.txt`, `real_precheck.out`, `final_checks.out`, `signal_probe.log`,
  `sim/` (every case log and four journals).
