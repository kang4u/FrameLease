# Review 2 of item a10r7b: the streaming applier, its wrapper and the post-check before Amendment A10

Independent adversarial review, 2026-11-15 09:19-10:10 (Beijing time). Nothing was applied: the protocol lock,
PROTOCOL.md, the registration files, the seal, PIPELINE_STATE.md, every registered file, both drivers, their queues,
CARLA and the GPU were not touched. Every process ran as `taskset -c 12-15 nice -n 19 ionice -c 3` with one BLAS thread
and `CUDA_VISIBLE_DEVICES=''`, one at a time; the largest resident set was 36 MB. Scratch trees: `/tmp/A10A11/applier/`
only, removed after the runs (the logs are in `review2/logs/`). No test-route data and no P2 outcome was read.

Reviewed files (sha256 at review time, equal to RUNBOOK Sec. 6; unchanged by this review):

| file (under `outputs/framelease_v4/build/AMEND2/`) | sha256 |
|---|---|
| `a10r7b/apply_entry_stream.py` | `0f0cfda6d51f4924e82799631f1ac5a0a00f0f44d02c48b61c9fa07a9f0ac923` |
| `a10r7b/apply_entry_stream.diff` | `737a3e5c9a90cc95521863a72fa8cf929e91232a3768d06bbc7f836a7f40806b` |
| `a10r7b/apply_locked.sh` | `9c86ca20f259e0df6a0547e0b954a1d554eecd96d67a6aa9cd49a2bd2b00ddf8` |
| `a10r7b/post_check.py` | `f2038c1f33c642e9cfb199ccdd029bbd1a1f613c01cc4afd5bba9f1036ba6213` |
| `a10r7b/sim_tree.py` | `211a714b88f65963b2ee71a6e4ea3e762e43f0229768fbb6377fb211b9bcf606` |
| `a10r7b/RUNBOOK.md` | `75cb4c0737054ea2c82e42a1e82f76e9081b9dfdf3b78b66b856e5e3cfb517ee` |
| `final/A10_entry.md` | `9790c164405f432a813df39986b84853bd18ac078b5d4afff0ea51915ea324ca` |
| `final/A10_spec.json` | `b1de9f6a976da98dc0da9da48fff5a1e2ec55512dfaac581ad7eb73a64335b0e` |
| `AMENDMENTS2_DRAFT.md` | `03bfb7f44e89cbc4d88ac12ca96f7366c05188cfae22de58fccc8b9357861eac` |

`apply_entry_stream.diff` equals `diff -u paper_tools/apply_entry.py a10r7b/apply_entry_stream.py` (headers aside).

## Verdict: GO_WITH_FIXES

The fixes of review 1 hold: M1 (both baselines, missing files, vanished files) and the three new hardenings stop every
class of registered-file change tested, before `--write-manifest` or right after it with the sealed manifest put back;
S1-S6 behave as the RUNBOOK states; S7-S9 are in the texts. The A10 entry is right: finding 1 is the rule of the sealed
`commit_audit.py` 7439a4ea in the words of E3, finding 2 states the AGG0 km floor, deviation 1 is complete up to now,
the fifth in-place text equals the one `derive_inplace5.py` derives from the current sealed PROTOCOL.md, and on the
simulated text `phase_driver.citing_amendment` gives A10 for the first Sec. 13.2 line citing `analyze_v4.py` and
`analysis_registration` has no wait reason. A10 and then A11 apply end to end on a scratch tree, the lock is held in one
interval for the whole transaction, and the applier stays at 18 MB.

Two defects must be fixed before A10 is applied while the phase driver runs. M1: the wrapper releases the protocol lock
while SEAL.sha256 does not match PROTOCOL.md (the "seal it now" branch, an orphaned `registration.py`, an interrupted
wrapper), and the running phase driver turns that state into an ALERT at its next cycle, before the RUNBOOK's hand seal
can run. M2: the registered set of the applier omits the P1 job files that both drivers treat as registered, so the
applier seals a changed one. Both fixes are drafted in `review2/` and pass every case on scratch trees (case X).

## Must fix

**M1. `apply_locked.sh` leaves an unsealed PROTOCOL.md when it releases the lock; the phase driver then raises an
ALERT.** The phase driver evaluates G1 at every cycle (`cycle`, `gate_g1` line 1646): `ensure_recorded` returns early
only while the seal matches (line 1077); otherwise it waits for running `registration.py` processes, takes the
protocol lock and raises `Alert('registration', 'Sec. 13.2 already cites G1 D1 decision ... but SEAL.sha256 does not
match PROTOCOL.md / MANIFEST.sha256 (an unsealed edit)')` (line 1106). The wrapper's failure branch for "PROTOCOL.md
holds the entry" keeps the rewritten manifest, prints "seal it now" and exits, which releases the lock in exactly that
state (`apply_locked.sh` lines 59-61); the RUNBOOK (Sec. 1, "PROTOCOL.md holds the entry but is not sealed" and "No
line `apply_locked: exit`") prescribes a hand seal afterwards, which races the driver's next cycle (at most 300 s).
* Evidence (`review2/logs/`):
  * K3: SIGKILL of the applier before `--seal`: exit 137, "seal it now", `verify.out` reads both seals CHANGED;
    `phase_driver.gate_g1` on the tree raises the ALERT above (`K3_driver_g1.log`). The RUNBOOK hand seal then gives a
    consistent state (K3b), but only when it runs before the driver's cycle.
  * K4: a driver cycle that starts while the wrapper verifies waits (its `tool_pids` counts the wrapper's `flock` and
    `bash` processes, whose command lines hold `python` and `framelease_v4/protocol/registration.py`); the next cycle
    after the wrapper exit raises the ALERT (`K4b_driver_g1_next_cycle.log`).
  * O: SIGKILL of the applier 1 s into `registration.py --write-manifest`: the child keeps running, the wrapper decides
    at once ("PROTOCOL.md unchanged; the manifest equals the sealed one"), the child then writes the new manifest,
    `verify.out` reads "seal ... MANIFEST.sha256: CHANGED", the wrapper exits 137 and the driver raises the ALERT
    (`O1_wrapper_kill9_during_manifest.log`, `O3_driver_g1.log`). The RUNBOOK has no instruction for this state.
  * S: SIGINT to the wrapper's process group before `--seal` (Ctrl-C, a closed terminal, a tool timeout): every
    process ends, no `apply_locked: exit` line, PROTOCOL.md holds A10 unsealed, the lock is free, the driver raises the
    ALERT (`S1_wrapper_sigint_group.log`, `S2_driver_g1.log`). Measured duration of the wrapper: 16-25 s.
* Fix (`review2/proposed_apply_locked.sh`, diff `review2/proposed_apply_locked.diff`):
  1. `trap '' INT TERM HUP` before `flock` (the applier and `registration.py` inherit the ignored signals);
  2. under the lock, refuse (exit 96) unless `sha256sum -c --status outputs/framelease_v4/registration/SEAL.sha256`
     passes, then copy PROTOCOL.md, MANIFEST.sha256, SEAL.sha256 and REGISTRATION.json into a new
     `OUTDIR/attempt_<time>/`;
  3. after the applier, wait while `pgrep -f "$ROOT/framelease_v4/protocol/registration.py"` finds a process (the
     applier calls it by its absolute path; the drivers use the relative one);
  4. after a failure with PROTOCOL.md different from its copy: when the seal matches, nothing (exit 94); else
     `registration.py --seal` with the manifest the entry names (exit 94); when that fails, roll PROTOCOL.md (temporary
     file and rename), the manifest, SEAL.sha256 and REGISTRATION.json back to the copies (exit 93). The lock is never
     released while the seal does not match.
  Tested (case X): kill before `--seal` exit 94, sealed, verification OK, `gate_g1` passes; orphan: waited 3 s,
  "RESTORED the sealed manifest", `gate_g1` passes; kill after `--write-manifest` and inside `os.replace`: restored;
  SIGINT to the group: ignored, exit 0, sealed; unsealed PROTOCOL.md before the run: exit 96, no copies.
  RUNBOOK Sec. 1: run the wrapper detached (`setsid nohup bash $A/a10r7b/apply_locked.sh SPEC OUTDIR >
  OUTDIR/console.txt 2>&1 < /dev/null &`) and wait for the line `apply_locked: exit` in `console.txt`; describe exit 93
  (rolled back, nothing applied: resolve the cause in `apply.out`, run again) and exit 94 (the entry sealed by the
  wrapper: `verify.out` must read "manifest: OK" and both seals OK, then the post-check); keep the hand seal only for
  "No line `apply_locked: exit`" and state that the phase driver raises an ALERT at its next cycle in that state
  (recovery: seal, verify, move `phase_driver/ALERT.txt` aside, restart the driver).

**M2. The registered set of `apply_entry_stream.py` omits the P1 job files.** Both drivers treat every file under
`outputs/framelease_v4/p1_jobs/` as registered (`p1_driver.is_strict`, line 737; phase driver docstring line 118:
"the P1 job files ... always count as registered"). Twelve of them are in the sealed manifest but in neither baseline
and cited by no sha256: the `.stage.json` and `.check.json` of b04-b09 (`outputs/framelease_v4/p1_jobs/FULL/`). The
applier's set (both baselines and the citations, line 128) leaves them out, so it seals a change of one, and the
drivers see nothing afterwards.
* Evidence (case P): `b04_lease_s2.check.json` changed by one byte. The phase driver's own pre-check refuses it
  (`P1_driver_precheck_before.log`: "1 registered file(s) differ from the sealed manifest"). The applier's check mode
  passes, the wrapper seals A10 (exit 0), `registration.py --verify` reads OK, the sealed manifest holds the changed
  sha256, and the driver's pre-check afterwards finds nothing (`P2_check.log`, `P3_wrapper.log`,
  `P4_driver_precheck_after.log`). The project tree holds no such change now (the start check: manifest OK).
* Fix: after line 128, `registered |= {k for k in sealed if k.startswith('outputs/framelease_v4/p1_jobs/')}`
  (p1_driver.is_strict); RUNBOOK Sec. 0 "Registered files": add the P1 job files. Tested (case X2): check and wrapper
  stop before `--write-manifest`, nothing changed; A10 and A11 still apply (X1, X1c).

## Should fix

All items are in `review2/proposed_apply_entry_stream.py` (diff `review2/proposed_apply_entry_stream.diff`) and pass
on scratch trees (case X); the original behaviour is reproduced by the cases named.

* **S1. `--apply` without the lock.** The applier never checks that it holds the protocol lock. Case L3: with another
  process holding the lock (the phase driver's record), `apply_entry_stream.py SPEC --apply` run directly seals A10
  (exit 0). Fix: in `--apply` mode require a descriptor of `framelease_v4/.protocol.lock` inherited from `flock(1)`
  (found in `/proc/self/fd`) on which `flock(LOCK_EX | LOCK_NB)` succeeds; X9: "STOP: --apply runs only under
  framelease_v4/.protocol.lock".
* **S2. Newly registered files are counted on the entry only.** `phase_driver.refresh_baseline` (line 950) registers
  every new manifest file whose sha256 any part of PROTOCOL.md cites; the applier counts the files the entry cites
  (line 194). Case T5: an empty file in the manifest scope (its sha256 `e3b0c442...` is cited in PROTOCOL.md): the
  applier reports the eight A10 files, the driver's refresh registers nine, `post_check.py A10` exits 0. Fix: count
  over the composed PROTOCOL.md and require the set to equal the unregistered manifest files the template cites with
  `{{sha256:...}}` (X13: STOP, manifest restored); `post_check.py`: require the refresh to add exactly `FILES[name]`.
* **S3. The composed PROTOCOL.md is not read by the drivers' parsers.** The line check copies the drivers' entry,
  title and heading forms but not `p1_driver.SEC_START`. Case T4.10: a template line holding only
  `### 13.2 Amendments` passes the check, is sealed, and both `p1_driver.protocol_view` and `phase_driver.phase_view`
  then raise "expected exactly one ... heading, found 2".
  Fix: add SEC_START to the line check, and before the write parse the composed text with both views (no Alert, the
  entry's title read once, the drivers' entries and the other titles unchanged, each newly registered file first cited
  by the entry per `citing_amendment`); X12: STOP.
* **S4. No order check of the stamp.** Case T2: with the clock at 06:30 (+0800) the entry is sealed as "2026-11-15
  06:30", before A3 (06:40) and G1 / G2 (06:42 / 06:43). Fix: stop when the time is earlier than the latest stamp of
  an entry head or amendment title in Sec. 13.2 (pre-check and again at the fill); X10: STOP before
  `--write-manifest`.
* **S5. No width check.** Case T3: a template prose line of 112 columns becomes 129 columns when filled; check mode
  passes and the wrapper seals it. Fix: prose lines (table rows excepted) at most 120 columns in the filled entry, and
  a check-mode preview of the fill (the current sha256 values, the time, the test summaries) so that check mode reports
  it; X11: check-mode STOP.
* **S6. A cited file that changes after `--write-manifest` is cited at a sha256 the manifest does not hold.** Case Y:
  `analyze_v4.py` changed between `--write-manifest` and the fill: the entry cites the new sha256, the sealed manifest
  the old one, exit 95, and the driver's refresh registers seven files, not `analyze_v4.py`. Fix: hash the cited files
  once after `--write-manifest`, stop when one differs from the new manifest, fill from these values; X14: STOP before
  PROTOCOL.md is written.
* **S7. The wrapper copies without a seal check and overwrites the copies of an earlier attempt.** Case R: after K3's
  state, the wrapper run again stops at the applier's seal check (exit 1), but `MANIFEST.sealed.before_apply` and
  `PROTOCOL.sealed.before_apply` now hold the unsealed files and `apply.out` reads "the manifest equals the sealed
  one". Fix: M1 items 2 (seal check, one directory per attempt); X8.
* **S8. Smaller hardenings.** Count each in-place "old" on the text as the earlier replacements leave it (the order the
  applier applies them; the A10 texts do not overlap now); fsync the temporary file before the rename, as
  `p1_driver.atomic_write` does; print the manifest difference (new, left, changed files) in `apply.out`;
  `post_check.py` also checks the P1 driver's ALERT and transaction files.

## Verified (no change needed)

* Registration at start (09:19) and end (10:08, after the scratch trees were removed): "manifest: OK" and both seal
  lines OK; PROTOCOL.md `ca54d359...`, MANIFEST `4bfe7451...`, SEAL `b8d516d1...`, REGISTRATION `c0ee0217...`, P1
  baseline `df4435e1...`, phase baseline `cfe58aa1...` and PIPELINE_STATE.md `73add832...` equal at start and end: no
  driver re-seal during the review. The phase driver ran throughout (pid 256142, G3 with P2 running; `driver.log`
  unchanged since 06:48, no ALERT). No `__pycache__` and no empty file was added under `framelease_v4/`.
* Review 1 M1 and the hardenings (cases B, C, D on scratch trees, original applier and wrapper): a P1-baseline file
  (`arms/realized.py`), a phase-baseline-only file (`analysis/commit_audit.py`) and a missing one
  (`protocol/stress_bench.py`) stop check mode and the wrapper before `--write-manifest`, nothing changed (B1-B3); a
  baseline entry absent from the sealed manifest stops ("registered files absent from the sealed manifest", B4); a
  registered file changed or removed between the pre-check and `--write-manifest` stops after it and the sealed
  manifest is restored (B5, B6); a registered file changed between `--write-manifest` and `--seal` gives exit 95 and
  the driver's pre-check reports it (B7); after A10 without the driver's refresh, `analyze_v4.py`, registered only by
  its citation, stops A11 when changed (C1); the temporary file and each driver's `protocol_txn.json` and `ALERT.txt`
  give exit 96 and a check-mode STOP (D1-D5); template lines in the P1 entry form, the phase entry form, an amendment
  title, either driver heading or holding the anchor phrase stop check mode (T4.1-T4.6); lines that take a driver
  form only when filled (`{{datetime}}` in an entry head, `A{{manifest:files}}` in a title) pass check mode and stop
  after `--write-manifest` with "filled entry problem", PROTOCOL.md unchanged (T4.7-T4.9); an in-place "old" twice
  stops before `--write-manifest` (T1).
* Review 1 S1-S6 (cases K, L): SIGKILL after `--write-manifest` and inside `os.replace`: exit 137, the sealed manifest
  restored, the temporary file removed, `gate_g1` passes (K1, K2); output unbuffered; exit 95 (B7); with `TZ=UTC`
  check mode stops ("not Beijing time") and the wrapper stamps Beijing time (Z1, Z2); a holder of the lock delays the
  wrapper, which then seals (L1, 35 s); a busy lock gives
  exit 97 and changes nothing (L2, the wrapper copy with a 5-s wait). S7-S9: deviation 1 lead sentence, FILL0 bullet
  and the two `commit_audit.py` versions; A11 "Development data" with the R7B review runs and RUNBOOK Sec. 3
  precondition 3; RUNBOOK Sec. 3 precondition 1 and the STOP note of `post_check.py`.
* End to end (case A, original applier and wrapper, real specs): A10 check 11 s, 18 MB; wrapper exit 0 in 20 s,
  18 MB, newly cited exactly the eight A10 files, manifest unchanged (221 files), verification OK; the lock held from
  0.0 to 19.8 s, one interval (a concurrent prober never obtained it); parsers without Alert, A10 read once, P1 and
  phase entries unchanged, every A10 file first cited by A10, `analysis_registration` without wait, a later G3 entry
  inserted by `phase_driver.insert_entry` is read and leaves `analyze_v4.py` attributed to A10; 279 added lines, no
  prose line over 120 columns (9 table rows), no driver-form line; `post_check.py A10` exit 3, the driver's
  `sealed_baseline` refresh adds exactly the eight files, then exit 0; `gate_g1` passes. A11 (stand-in review file):
  check passes, wrapper exit 0, newly cited exactly the two R7B files, `post_check.py A11` exit 3 then 0 after the
  refresh (two files added). The diff against the project PROTOCOL.md touches Secs. 4.1 (lines 484-486), 9.4 (1392),
  9.12 (1465-1472) and inserts the two entries after the G2 entry.
* A10 text against APPLY_PLAN2 Sec. 4: finding 1 states "a null commit margin passes where the validity record names
  no relevant agent, or has reason `horizon_cap` and n_computed 0 ...; any other null margin with a relevant agent is a
  violation", equal to E3, to the sealed A3 departure 6 (PROTOCOL.md lines 2370-2373) and to
  `commit_audit.null_margin_explained` of 7439a4ea (the file's sha256 now, cited by A3); finding 2: `km_driven` of the
  `fl_heuristic` smoke run on route 18305 (RC 0) is 0.0 in `build/R7/dev/agg_p1`, 0.001 in `build/R7B/dev/agg_now`
  and `agg_snap_2203`, whose `code_sha256` names `aggregate_v4.py` ee13c90b (cited by A3) and `commit_audit.py`
  7439a4ea; deviation 1: the RUNBOOK search (`-newermt '2026-11-15 09:15'`) finds only the PROGRESS files of item
  a10r7b and of this review, and the PROGRESS files changed since 2026-11-15 00:00 (AMEND, AMEND2/step3 and its
  review, a10r7b and its review, FILL0 and its review, R7B and its review) record no execution of the aggregator or of
  the four A10 files on real data after the FILL0 runs (01:24-03:33), which the deviation lists;
  `derive_inplace5.py --spec` exit 0, "in-place text 5 equals the derived text" (lines 483-486 of the sealed
  PROTOCOL.md); `check_drafts.py` exit 0, "all checks
  passed", every in-place text found once; `evidence_sha256.txt` verifies; `edit_draft.py --check`: the draft holds
  `final/A10_entry.md` verbatim; the test logs read 48 passed / 107 subtests, 22, 50 (422 warnings), 28 / 20.
* Memory and time: check mode 6-11 s and 18 MB; wrapper 16-25 s and 18 MB (32 MB with the proposed applier, which
  imports the drivers' parsers); `post_check.py` 4 s and 29 MB; the harness 36 MB.

## Observations

* During the transaction a phase-driver cycle that finds the seal mismatching logs the attention line
  "registration.py (pids ...) still running" and goes on at its next cycle (its `tool_pids` matches the wrapper's
  `flock` and `bash` command lines). This is harmless and expected; the RUNBOOK names it so that the post-check reader
  does not take it for a fault.
* When the manifest scope does not change, the G2 entry, A10 and A11 each name the manifest `4bfe7451...` "sealed with
  this entry"; this is correct, since a seal is the pair of PROTOCOL.md and manifest (phase driver review fix M1).
* The P1 driver's baseline is frozen since P1 ended. A later amendment that removes a registered file from the
  manifest makes this applier stop with "absent from the sealed manifest" until that baseline entry is resolved; A10
  and A11 remove none.
* Exit 97 leaves the `apply.out` of an earlier attempt in place; the console line names the exit code.
* `paper_tools/apply_entry.py` keeps every defect named in RUNBOOK Sec. 5 item 3 and those above; it is not used.

## Files of this review

`review2/PROGRESS.md`, `review2/REVIEW.md`; `review2/review2_sim.py` (scratch-tree harness, cases A, B, C, D, K, L, M,
O, P, R, S, T, X, Y; it writes `inject.py`, `drv.py`, `prober.py` and `holder.py` under `/tmp/A10A11/applier/`);
`review2/proposed_apply_entry_stream.py` and `review2/proposed_apply_locked.sh` with their diffs against the reviewed
files; `review2/logs/` (every case's output, `results.txt`, the scratch PROTOCOL.md after A10 and A11 as
`PROTOCOL.after_A10_A11.scratch.md.txt`, its diff `A10_protocol.diff`, the parser reports `A4_*.json` and
`A9_*.json`). `results.txt` holds the runs in order: the six UNEXPECTED lines of runs 1 and 3 come from two harness
errors (an expectation for T4.7-T4.9 that required "RESTORED" where the rewritten manifest equalled the sealed one;
case X calling the reviewed wrapper through a default argument), both corrected and rerun with no UNEXPECTED step
(runs 2, 4 and 5; `PROGRESS.md`).
