# Runbook: APPLY_PLAN2.md step 3 at the end of P1, the D1 decision and the start of the phase driver

For the coordinating session. Everything below is prepared and simulated end to end on a scratch copy
(`SIMULATION.md`: 45 cases, 45 PASS, and the reviewer's break cases rerun). The session executes the commands in
order and stops where a step prints STOP. Working directory `/home/kang/Desktop/DAC` throughout. Every command except
the start of the phase driver (step 6) runs with the prefix `taskset -c 12-15 nice -n 19 ionice -c 3` (the scripts set
`OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''` themselves). The commands below
use two shell variables, set once:
```
cd /home/kang/Desktop/DAC
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
P="taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B"
S=outputs/framelease_v4/build/AMEND2/step3
```
The exported variables are for steps 2-5 only; step 6 removes them (see there).

## Prepared inputs (sha256 at preparation, 2026-11-15)

| file | sha256 | role |
|---|---|---|
| `$S/amend_step3.sh` | `978c9bddfb90f9347374e33d9ed1bdf624176dad12c53fe83c16c86a2f2b4251` | the transaction: pre-check, lock, locked part, post-check, PASS/STOP |
| `$S/step3_txn.py` | `a778ad618c0a587a2a73fa8d3bae564bcac4945ec8f4ddbf3157b3b61fc703a0` | its logic (`precheck`, `locked`, `postcheck`, `restore`) |
| `$S/step3_spec.json` | `5ffa420793cb394fe6cd148663254c9d67a25dbf7ca016ae0c789ca48cba9142` | entries, in-place texts, `must_equal` (66 files), the 38 A3 files at their reviewed sha256, the 40 files the transaction registers |
| `$S/make_step3_spec.py` | `7f7e618a4b3d88523f0f5c6facbae1b160920eb99117220bcfddff0b537a4c49` | writes `step3_spec.json` from the tree |
| `$S/write_d1_decision.py` | `c0abb6e3d60ccad93904f323d48c2584c33c856fbe3bf42f6ccb8ff8354c297b` | the D1 decision file |
| `outputs/framelease_v4/build/AMEND/AMENDMENTS_DRAFT.md` | `81e5376eaad29c5918246ccfab421c482680ef004f47f14754f534de8de9802d` | A3, A9, A7b, A4 (after E1-E4, F1-F5 and S4, `build/AMEND/PROGRESS.md`) |

`amend_step3.sh` prints the sha256 of `step3_txn.py` and `step3_spec.json` on its second line; compare them with the
table. Test logs of step 2 (all end with no failure; the pre-check and the locked part check their sha256):

| log | summary | sha256 |
|---|---|---|
| `outputs/framelease_v4/amendment_a3/pytest_protocol_tools.log` | 194 passed, 21 warnings in 284.98s (0:04:44) | `c84a284e3dd4d433c6cc3313fd678857fe083fa37881a0bc86997e789c63f8a5` |
| `outputs/framelease_v4/amendment_a3/pytest_arms_ext.log` | 38 passed, 21 warnings in 133.66s (0:02:13) | `ffbd12d131a0f5691ac38c4b174c217b17f09cfdef2208a742dd3f56cf29f2ec` |
| `outputs/framelease_v4/amendment_a3/pytest_analysis.log` (E4 file set) | 83 passed, 103 subtests passed in 1.24s | `abf4a435e8c83a5e617281eca8b06c56e7f3f9164ecdcc6ce441fc3e2eac083a` |
| `outputs/framelease_v4/amendment_a7/pytest_stress_bench.log` | 34 passed in 30.38s | `4ca00fbd23e75887174e4bc878d6ebb37582661dfa388726a40dc65729390a7c` |
| `outputs/framelease_v4/operational_phase_driver/pytest_phase_driver.log` | 24 passed in 163.54s (0:02:43) | `42b12b9d6205dd7d6a8d7749f0f63e37c7e5345f5780849c3800e0b4cd2dd7e9` |
| `outputs/framelease_v4/operational_phase_driver/pytest_review_phase.log` | 6 passed in 66.11s (0:01:06) | `e5f2c98e88088eda4803c8f29f5ba9059921a707eb70a0b839c9938fdcc6b0c1` |

## 0. Before P1 ends: one decision (review of item Step3, should-fix S7)

The AGG0 review (`outputs/framelease_v4/build/AGG0/review/REVIEW.md`, verdict GO) lists two optional hardenings of
`framelease_v4/analysis/commit_audit.py`, neither of which blocks A3:
* should-fix 2: a `horizon_cap` null margin with n_computed 0 passes without a check that lease_s = H_bar; the
  hardening requires |lease_s - h_bar_s| <= 1e-9, h_bar_s from `config.json` `v4.v3.resolved.lease` (real runs cannot
  produce the unchecked case: all 12,958 real commits satisfy the premise);
* should-fix 4: an invalid v3 lease (`perception_unavailable`, `invalid_detection`) logs n_relevant 0, so its null
  margin passes the margin line (the deadline line flags the commit); the hardening excludes `VL.INVALID_REASONS` from
  the n_relevant-0 case.

Step 3 registers `commit_audit.py` (Amendment A3). Decide before step 3:
* not adopted: step 3 runs as prepared; a later change of the file is an amendment that installs it under the lock;
* adopted: a reviewed change of `commit_audit.py` and `tests/test_commit_audit.py` (item AGG, then its review); E3 in
  the A3 draft and A10 finding 1 (`final/A10_entry.md`, A10 item) state the added condition in the same words; the A3
  review record of the AMEND draft (appendix table) gains a row with the new sha256 and the review;
  `build/AMEND/a3_sha256_at_drafting.txt` and the pins of `build/AMEND/review_prereq/test_review_prereq.py` follow;
  the A3 analysis log is written again (step 2 commands); then `$P $S/make_step3_spec.py` and the pre-check (step 2).

## 1. Wait for the end of P1

P1 has ended when the P1 stage driver has entered "Tuning freeze" and "D1 summary" in Sec. 13.2, written
`outputs/framelease_v4/p1_driver/P1_DONE.json` and exited (its `driver.log` ends with "P1 DONE: ... the driver
stops"). Touch nothing of P1 before that. If the P1 stage driver stops with `p1_driver/ALERT.txt` instead, resolve
that first (its operational addition of 2026-11-11); step 3 never runs over an ALERT or an open
`p1_driver/protocol_txn.json`.

## 2. Pre-check (APPLY_PLAN2 Sec. 3 step 1; no lock, changes nothing)

```
taskset -c 12-15 nice -n 19 ionice -c 3 bash $S/amend_step3.sh --precheck-only
```
Last line: `PASS: pre-check passed (--precheck-only; nothing was changed)` (about 10 s). The log lies in
`$S/txn_<time>/amend_step3.log`. It checks: `registration.py --verify` (both seal lines OK; a manifest difference only
of unregistered files), the registered baseline (`p1_driver/registered_baseline.json`) in the sealed manifest and
unchanged in the tree, every P1 job file of the sealed manifest (`outputs/framelease_v4/p1_jobs/`, registered for both
drivers) unchanged in the tree, P1_DONE.json, no live `p1_driver.py` / `phase_driver.py`, no P1 or phase driver
ALERT / `protocol_txn.json`, no earlier step-3 transaction directory of `$S` left unresolved, the two P1 entries and
the D1 summary sha256 they cite, `final/OP_spec.json` "must_equal" and the spec's `must_equal`, the 38 A3 files at the
sha256 of their review record (appendix of the AMEND draft), no entry of A3, A4, A7, A9 or the operational addition
yet, every in-place "old" exactly once, `check_drafts.py` exit 0, `--datetime` when given, and a dry composition of
the whole new PROTOCOL.md (fill, rewrap, the drivers' parsers, 40 newly registered files).

At STOP the log lists every PROBLEM line. Action per problem:

| PROBLEM | action |
|---|---|
| `P1_DONE.json does not exist`, `p1_driver.py of this root is alive`, `driver.lock names a live p1_driver.py`, `no P1 driver entry` | P1 has not ended: wait (step 1). |
| `p1_driver/ALERT.txt exists` or `protocol_txn.json exists` | resolve the P1 driver's ALERT or interrupted record first. |
| `the two seal lines are not both OK`, `registered files differ`, `P1 job files ... differ from the sealed manifest` | an unsealed edit or a changed registered file (a P1 job file counts as registered): do not continue; find the cause (`registration.py --verify` lists the files). |
| `an interrupted step-3 transaction is not resolved: <dir>` | an earlier run of step 3 ended without its PASS/STOP line: resolve it as in step 3, row "no PASS/STOP line", then the pre-check again. |
| `<file>: sha256 ... != ... (prepared / OP_spec.json)` | the file changed after the preparation. Code or draft: the change must carry its review (APPLY_PLAN.md Sec. 4); an A3 file also gets its row in the review record of the AMEND draft; one of the four files of `final/OP_spec.json`: its "must_equal" is set to the reviewed sha256 first. Rerun the test log that covers it (commands below), then `$P $S/make_step3_spec.py` (it refuses while `final/OP_spec.json` differs from the tree) and the pre-check again. A test log rerun by itself: only `make_step3_spec.py` again. |
| `A3 file ... is not at the sha256 of its review record` | an A3 file changed without a recorded review: do not continue until the change is reviewed and recorded. |
| `check_drafts.py exit 1/2` | read its lines. A10 files changed after drafting (A10 `must_equal`): the A10 item updates `final/A10_spec.json` after the review of the change (APPLY_PLAN2 Sec. 4 step 1); then `make_step3_spec.py` (it records the spec's sha256) and the pre-check again. |
| `in-place text ... found N times` | Secs. 4.1, 7.6, 8.3, 8.6 or 9.12 of PROTOCOL.md changed since the preparation: do not continue; regenerate the in-place texts (`make_step3_spec.py` refuses an "old" that is not found once). |
| `--datetime ... is earlier than the latest time stamp` / `later than the current time` / `not a valid time` | give no `--datetime` (the default is the time the lock is taken) or a valid one. |
| `dry fill` / `dry composition` | an entry line or the composed text fails a check: fix the draft by line breaks only (log it in `build/AMEND/PROGRESS.md`), `make_step3_spec.py`, pre-check again. |
| `Amendment A3 is entered already` (A4, A7, A9, the operational addition) | step 3 was applied: never rerun; go to step 4. |

Rerun commands of the step-2 logs (only when a covered file changed):
```
source linux/env.sh && export CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PYT="taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider"
$PYT framelease_v4/protocol/tests/test_{p2_jobs,p2_check,p3_rl,stress_bench,check_smoke,check_smoke_ext}.py \
  framelease_v4/protocol/tests/test_{fl_full_qnet_agent,test_jobs,test_freeze}.py \
  > outputs/framelease_v4/amendment_a3/pytest_protocol_tools.log 2>&1
$PYT framelease_v4/arms_ext/tests > outputs/framelease_v4/amendment_a3/pytest_arms_ext.log 2>&1
$PYT framelease_v4/analysis/tests/test_{aggregate_v4,commit_audit,extra_metrics,interim_guard,manipulation}.py \
  framelease_v4/arms/tests/test_metrics_realized_keys.py > outputs/framelease_v4/amendment_a3/pytest_analysis.log 2>&1
$P outputs/framelease_v4/paper_tools/apply_entry.py outputs/framelease_v4/build/AMEND2/final/OP_spec.json --tests
```
A wall-time failure of `test_p3_rl.py` follows APPLY_PLAN.md Sec. 4 (attempt log kept, one rerun alone).
`apply_entry.py` and `fill_entry.py` read any summary that contains "failed" (also "xfailed") as a failure; no step-2
log has an expected failure.

## 3. The transaction (APPLY_PLAN2 Sec. 3 steps 1, 3 and 4)

Start it detached, in its own session, so that no stop of a background task, end of a session turn or time-out of
the calling shell can signal it; it ends by itself (about 1 min, plus up to 600 s of lock wait):
```
O=$S/step3_$(date +%Y%m%dT%H%M%S).out
setsid nohup taskset -c 12-15 nice -n 19 ionice -c 3 bash $S/amend_step3.sh > $O 2>&1 < /dev/null &
```
Then poll until the PASS or STOP line is there (from 5 s after the start, every 10-20 s; each poll returns at once).
The first line of `$O` names the pid of the script and the transaction directory:
```
PID=$(sed -n 's/^amend_step3.sh [^ ]* (pid \([0-9]*\)).*/\1/p' $O | head -n 1)
W=$(sed -n 's/.*transaction directory //p' $O | head -n 1); echo "pid $PID, transaction directory $W"
grep -E '^(PASS|STOP):' $O; kill -0 ${PID:-999999999} 2>/dev/null && echo running || echo ended
```
Leave the process alone while it runs: a SIGTERM before the seal only undoes the transaction (STOP), a SIGKILL leaves
work for `restore` (table below). It repeats the pre-check, takes `framelease_v4/.protocol.lock`
(`flock -w 600`; the file stays empty) for the locked part only, and runs the post-checks after releasing it. Under
the lock, before any change: the time stamp (default: the time the lock is taken; `--datetime 'YYYY-MM-DD HH:MM'`
sets it, refused when earlier than the latest stamp of Sec. 13.2 or later than now), none of the five entries in
PROTOCOL.md yet, the seal, the drivers' ALERT / `protocol_txn.json` files and the prepared inputs again (a failed
check: STOP, nothing changed). Then: copies of
PROTOCOL.md, MANIFEST.sha256, SEAL.sha256 and REGISTRATION.json into `$W` (their sha256 in the journal);
`registration.py --write-manifest --force`; the post-manifest check of step 3.2 (the registered baseline and the P1
job files); the five entries filled by `fill_entry.py` with ONE time stamp and rewrapped where a filled line exceeds
120 columns; the in-place texts; the entries inserted in the order A3, A9, A7, A4, operational addition, each its own
block, directly before "Each amendment gets the date and time"; the pre-seal check (the files on disk, every registered
file at its new-manifest sha256, every prepared input at its sha256); `registration.py --seal`; `registration.py
--verify`. From the lock on, the script and its log process ignore SIGINT, SIGTERM and SIGHUP; the helper turns such
a signal before the seal into a STOP with the sealed state restored, and ignores signals from the seal on. Post-checks:
the command of step 3.2 prints OK; the P1 job files; `--verify`; `phase_driver.py --dry-run` shows G0 passed and G1
waiting for `D1_DECISION.json`; the G5 plan holds `s2 --grid relative`; `check_drafts.py` exit 0 on the new
PROTOCOL.md; 40 files newly registered; the Sec. 4.1 status paragraph for A10. Duration in the simulation (case 08):
pre-check 7 s, locked part 10 s, post-check about 20 s.

Last line on success: `PASS: Amendments A3, A9, A7 (A7b), A4 and the operational addition entered at <time>, one
manifest, one seal;`. The transaction directory `$W` keeps `amend_step3.log`, `step3_txn.log` (every message, written
by the helper itself), `journal.json`, the sealed copies, the five filled entries (`entry_*.md`), `PROTOCOL.new.md`,
the dry-run output and `sec_4_1_status_paragraph.txt`.

STOP lines (the exit code in brackets; `$O` holds the same text as `$W/amend_step3.log`):

| STOP line | meaning | action |
|---|---|---|
| (1) `STOP: pre-check failed` | nothing changed | as in step 2. |
| (1) `STOP: the protocol lock was not free within 600 s` | nothing changed | another editor holds the lock; start the transaction again later. |
| (1) `STOP: the locked part stopped before it changed anything` | nothing changed (journal `refused`) | read the `STOPPED before any change` line of `$W/step3_txn.log`; an input changed since the pre-check, the time stamp or the seal: as in step 2. Then start again. |
| (1) `STOP: the transaction failed before the seal and was undone` | PROTOCOL.md and MANIFEST.sha256 restored, both seals verify: nothing applied (journal `restored`) | read the FAILURE line. Post-manifest check: a registered file or a P1 job file changed between the pre-check and the manifest; pre-seal check: one changed between the manifest and the seal; find it, never seal over it. Entry or composition problem: fix as in step 2. A signal: nothing to fix. Then start again (a new transaction directory). |
| (2) `STOP: ... the restore did not verify` | the restore needs a check | do not start again. Read `$W/journal.json`; run `$P $S/step3_txn.py restore --root /home/kang/Desktop/DAC --work $W` (it takes the protocol lock itself: never under `flock`); then `$P framelease_v4/protocol/registration.py --verify` must show both seals OK and PROTOCOL.md equal to `$W/PROTOCOL.sealed.md`. |
| (137 or another code) `STOP: step3_txn.py locked exited ... (killed?)` | the helper was killed | do not start again. The line names the journal step and the command: before `sealed`, the `restore` command above; `sealed` or later, the post-check alone: `$P $S/step3_txn.py postcheck --root /home/kang/Desktop/DAC --work $W`. |
| (3) `STOP: sealed (the entries are in PROTOCOL.md), but a seal line or a registered file does not verify` | sealed | do not start the phase driver; find the changed registered file (`registration.py --verify`) and treat it as an amendment matter. |
| (4) `STOP: post-check failed` | sealed; a post-check failed | read the PROBLEM line. G0 not passed or G1 not waiting: do not start the phase driver until the cause is clear (the dry-run output is in `$W`). `check_drafts.py` not exit 0: an A10 matter (step 7), not a blocker of steps 4-6. |
| no PASS/STOP line, and `kill -0` says ended | the run was cut off (a SIGKILL of the script, a reboot) | `$W` empty (no "transaction directory" line in `$O`) or no `$W/journal.json`: the run ended before the locked part; nothing changed; start again. Else read the journal step: `sed -n 's/^ "step": "\([a-z_]*\)",\{0,1\}$/\1/p' $W/journal.json`. `refused` or `restored`: nothing applied; start again. `sealed`, `verified` or `verify_not_clean`: sealed; run the post-check alone (command above; exit 0 = PASS; `verify_not_clean` is the case (3)). Any other step: not sealed; run the `restore` command above (it takes the lock itself), check both seals, then start again. |

## 4. Record the state

Append to `framelease_v4/PIPELINE_STATE.md` (P1 progress section): the time of step 3, the transaction directory,
the PROTOCOL.md and manifest sha256 printed by `--seal`, "A3, A9, A7 (A7b), A4 and the operational addition of the
phase driver entered in one transaction; 40 files registered", and the next steps 5-7 of this runbook.

## 5. The D1 decision (APPLY_PLAN2 Sec. 3 "Step 4")

1. Read `outputs/framelease_v4/tuning/d1/FULL_d1_summary.md` (and `.json`): the D1 table of PROTOCOL Sec. 4.8.
2. Write the rationale into `$S/d1_rationale.txt`: the reasons, taken from the D1 summary, in assertive sentences: the
   P1 blocks and their final jobs, dropped routes and set-up failure flags; the tuning freeze (L*, d*, A*, theta* and
   A_hb*, the `fl_risk` point); the training-route DS of the tuned arms next to the references; the decision and its
   consequence under Sec. 4.8 ("If the work continues, nothing registered here changes"). No hedging; no mention of
   who or what wrote the text; at most 4000 characters. The text enters Sec. 13.2 in the phase driver's "G1 D1
   decision" entry, which adds the user's instruction of 2026-11-14 (translated) and its reading itself.
3. Check, then write:
   ```
   $P $S/write_d1_decision.py --decision continue --rationale-file $S/d1_rationale.txt --dry-run
   $P $S/write_d1_decision.py --decision continue --rationale-file $S/d1_rationale.txt
   ```
   The second prints `wrote outputs/framelease_v4/phase_driver/D1_DECISION.json: decision continue, sha256 ...`. The
   file has the schema of APPLY_PLAN2 (`framelease_v4.d1_decision/1`, `decision`, `rationale`, `d1_summary_sha256`,
   `decided`, `by`: "the coordinating session", so that the G1 entry reads "by the coordinating session"); it is
   written as a temporary file in the same directory and renamed. The helper refuses (REFUSED lines, exit 1, nothing
   written) when the D1 summary is not the one the P1 driver's "D1 summary" entry and P1_DONE.json cite, when a G1
   entry or a decision file exists already, or when the rationale (or `--by`) is empty, too long, holds the anchor
   phrase or a placeholder brace, or names who or what wrote it.
4. `$P framelease_v4/protocol/phase_driver.py --dry-run`: G0 passed, G1 "dry" with the plan "record G1 D1 decision"
   and the entry text. A decision once written is never replaced; to change it before the driver records it, move the
   file aside (never after the G1 entry exists: the driver then raises an ALERT).

With `--decision stop` the driver records the decision, writes `phase_driver/P2_STOPPED.json` and ends; no later
phase starts (Sec. 4.8: the protocol and the training-route results are reported as they are).

## 6. Start the phase driver (APPLY_PLAN2 Sec. 3 "Step 5")

From a shell at nice 0 without CPU pinning, WITHOUT the prefix (the runners it launches inherit the driver's priority
and affinity; the script and the driver refuse a niced or pinned start), and without the one-thread / no-GPU
variables of steps 2-5: the driver hands its whole environment to `systemd-run` and so to the runner and every
closed-loop job (`p1_driver.run_cmd`), and the P1 stage driver and its jobs ran without `OMP_NUM_THREADS`,
`MKL_NUM_THREADS` and `OPENBLAS_NUM_THREADS` (checked on 2026-11-15 in `/proc/<pid>/environ` of the P1 stage
driver and of a running job; the jobs get `CUDA_VISIBLE_DEVICES=0` from `linux/env.sh` and the runner).
`start_phase_driver.sh` starts the driver with `setsid nohup systemd-run --user --scope` (its own session and scope,
`OOMPolicy=continue`), so no signal to the calling shell reaches it:
```
cd /home/kang/Desktop/DAC
nice                     # prints 0
taskset -pc $$           # lists 0-15
env -u OMP_NUM_THREADS -u MKL_NUM_THREADS -u OPENBLAS_NUM_THREADS -u CUDA_VISIBLE_DEVICES \
    bash framelease_v4/protocol/start_phase_driver.sh
tr '\0' '\n' < /proc/$(cat outputs/framelease_v4/phase_driver/driver.pid)/environ \
    | grep -E '^(OMP|MKL|OPENBLAS)_NUM_THREADS=|^CUDA_VISIBLE_DEVICES='    # prints nothing
```
No option: never `--allow-nice-launch` or `--normal-priority` (test sandboxes only). It prints the pid, the scope
`framelease-phase-driver-<ts>`, the log paths and the stop command. Its refusals: `phase_driver/ALERT.txt` or `STOP`
exists (resolve, move aside), the shell is niced or pinned (open a plain shell), another driver holds `driver.lock`.

After the first cycle (it runs at once; then every 300 s): `outputs/framelease_v4/phase_driver/driver.log` shows G0
passed and the G1 record; Sec. 13.2 holds the heading "**Phase gates (P2-P7, FULL).**" with the "G1 D1 decision"
entry after the five entries of step 3; `$P framelease_v4/protocol/registration.py --verify` shows both seals OK;
`state.json` names G2 (the P2 job file: generated, entered, copied into `queue_p2`, runner launched).

## 7. Next items (APPLY_PLAN2 Secs. 2 and 4)

* Amendment A10 (step 6), before the test freeze (G6). Its fifth in-place text takes the Sec. 4.1 status paragraph
  as step 3 leaves it (`$W/sec_4_1_status_paragraph.txt`); `sim_output/a10_inplace5_suggestion.json` gives an "old"
  (the whole paragraph, found once) and a "new" (rewrapped at 120 columns) for that text, in the wording of
  `final/A10_spec.json` (the A10 spec governs). A10 finding 2 (`km_driven` 0.0 in `runs.csv`) describes the state
  before item AGG0, which floors km at 0.001 (AGG0 review: "This closes A10 finding 2").
* The R7B amendment (step 7) before the analysis freeze; the phase driver's G8 waits for A10 only (APPLY_PLAN2 Sec. 5
  item 3: `phase_driver/STOP` if R7B is late).
* review_prereq should-fix 1 (PIPELINE_STATE line 47, idle band 0.425) and 6 (the supplementary S2 report on the
  test-freeze checklist) stay with the coordinating session.

## How this transaction differs from the text of APPLY_PLAN2 Sec. 3 (all intended)

1. The in-place texts of A4 are applied with those of A3, A9 and A7b: the A4 entry states them ("In-place text, Sec.
   8.3 (Amendment A4)" and the Sec. 4.1 sentence), and APPLY_PLAN.md Sec. 4 (A4: "In-place text: Sec. 8.3 ... and the
   Sec. 4.1 status sentence of A3 (item 1)") stays valid; step 3.4 of APPLY_PLAN2 names A3, A9 and A7b only because A4
   joined step 3 later.
2. The script takes the protocol lock itself, around the locked part only (steps 3.1-3.5); the pre-check and the
   post-check run without it, as steps 1 and 4 state. It is started detached (step 3 above), not in the foreground.
3. A failure before the seal restores SEAL.sha256 and REGISTRATION.json as well when `--seal` touched them. SIGINT,
   SIGTERM and SIGHUP, to the helper or to the whole process group, are such failures until the seal has returned
   (simulation cases 06b and 12a-d); the script and its log process ignore them from the lock on, so that the restore
   completes and the STOP line is written. Only SIGKILL interrupts the helper (case 06c); `restore` then brings the
   sealed state back (case 06d).
4. All five entries are filled by `fill_entry.py` (the rules of `apply_entry.py`, those of the AMEND drafts); a block
   with a filled line over 120 columns is rewrapped with its words unchanged.
5. After the seal, a manifest difference of an unregistered development file is reported and tolerated (named at the
   next seal, as both drivers and APPLY_PLAN.md Sec. 3 step 5 do); a registered one stops with exit 3.
6. The A7b placeholder "{{path and sha256 of the report}}" is resolved in the draft (edit F1, review_prereq should-fix
   5): `outputs/framelease_v4/build/STRESS/s2_dev_relative_recorded_smoke_a7.json` with its sha256. The A7b test log
   is named with its directory (`outputs/framelease_v4/amendment_a7/pytest_stress_bench.log`, edit of the step-3
   review should-fix S4).
7. Checks beyond the text of APPLY_PLAN2: the P1 job files in the pre-check, the post-manifest check and the
   post-check (both drivers treat them as registered); the prepared inputs again under the lock and, with every
   registered file, directly before the seal; the time stamp against Sec. 13.2 and the clock; no unresolved earlier
   transaction; none of the five entries in PROTOCOL.md yet, again under the lock. `restore` reads the journal under
   the protocol lock and refuses a journal that ended restored, refused or sealed, and files that this transaction did
   not write (a later edit or transaction).
8. `write_d1_decision.py` writes `"by": "the coordinating session"` (APPLY_PLAN2 shows "coordinating session"): the
   G1 entry then reads "by the coordinating session", the driver's own wording when the key is absent.
