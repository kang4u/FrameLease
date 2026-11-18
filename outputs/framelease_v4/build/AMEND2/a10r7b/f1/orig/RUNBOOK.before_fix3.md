# RUNBOOK: Amendment A10 (analysis code) and Amendment A11 (R7B recomputation of the other Table I columns)

For the coordinating session. Item a10r7b prepared both entries; nothing is applied by it. PROTOCOL.md, the
registration files, the seal, every registered file and the drivers' directories are unchanged by this item. This
version includes the fixes of the review `review/REVIEW.md` (GO_WITH_FIXES: must-fix M1, should-fix S1-S9) and of
review 2 `review2/REVIEW.md` (GO_WITH_FIXES: must-fix M1 and M2, should-fix S1-S8; fix pass 2). Item F1A11
(2026-11-15, `f1/`) brought A11 to the R7B files of attempt 6 and the reporting rule of its differences (Sec. 3) and
updated `make_a11_spec.py`, `A11_spec.json` and `check_a11.py`; its fix passes 1 and 2 applied the review
`f1/REVIEW.md` (GO_WITH_FIXES: must-fix M1-M3, should-fix S1-S7; S1 as decided by the coordinating session: the
classes F1, F3, in-flight and not-ok record). It applied nothing either.

State (2026-11-15 23:47, Beijing time): Amendment A10 is applied (20:15, `outputs/framelease_v4/amendment_a10/`,
wrapper exit 0, `post_check.py A10` passed) and Amendment A12, the cut of the test blocks P4-P6, at 23:30. PROTOCOL.md
`3fa337c1...`, `MANIFEST.sha256` `0fdb720e...` (221 files); `registration.py --verify` reads "manifest: OK" and both
seals OK. The phase driver is stopped (`phase_driver/STOP`, A12); the runner of `queue_p4` runs the reduced job files.
A11 (Sec. 3) is the next amendment and is required before the analysis freeze (APPLY_PLAN2 step 7).

## 0. Conventions

Every command runs from `/home/kang/Desktop/DAC`, one at a time, after

```
cd /home/kang/Desktop/DAC
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
X="taskset -c 12-15 nice -n 19 ionice -c 3"
P="$X .conda-unidrive-linux/bin/python -I -B"
A=outputs/framelease_v4/build/AMEND2
```

The applier. Tests, check mode and `--apply` use `$A/a10r7b/apply_entry_stream.py`: the generic applier
`outputs/framelease_v4/paper_tools/apply_entry.py` (`2ddc1c8c...`) with the changes below (the full diff is
`$A/a10r7b/apply_entry_stream.diff`; the `--tests` mode is unchanged).
* sha256 streamed in 1 MiB blocks. `apply_entry.py` reads each file whole; its pre-check hashes the 5.9 GB registered
  checkpoint `checkpoints/UniDriveVLA/.../UniDriveVLA_Stage3_Bench2drive_2B.pt` and reached 5.8 GB RSS (2026-11-15
  07:04) while a P2-P6 job holds up to 23 GB of 30 GB; the streaming applier stays at 18 MB.
* Registered files (review M1, review 2 M2). `apply_entry.py` protects only the 153 files of
  `p1_driver/registered_baseline.json` and skips a registered file that is missing. Here the registered files are
  those of `p1_driver/registered_baseline.json` and of `phase_driver/registered_baseline.json` (both must exist; 199
  files together now), every sealed-manifest file whose sha256 PROTOCOL.md cites (the rule of
  `phase_driver.refresh_baseline`, so the files of A10 count as registered before the driver's next refresh) and every
  sealed-manifest file under `outputs/framelease_v4/p1_jobs/` (both drivers treat the P1 job files as registered,
  `p1_driver.is_strict`; twelve of them, the `.stage.json` and `.check.json` of b04-b09, are in neither baseline and
  cited by no sha256). The pre-check stops when a registered file is absent from the sealed manifest, missing on disk
  or different from it; after `--write-manifest` the applier stops when a registered file changed or left the new
  manifest.
* Lines (review S4, review 2 S3). The template, a preview of the filled entry and the filled entry hold no line after
  the title that a driver reads as an entry (`p1_driver.ENTRY_RE`, `phase_driver.ENTRY_RE`), an amendment title
  (`phase_driver.AMEND_RE`), a driver heading or the heading `### 13.2 Amendments`, and the anchor phrase nowhere (the
  expressions equal the drivers' own).
* Widths (review 2 S5). Prose lines of the filled entry (table rows excepted) and the changed lines of the in-place
  texts are at most 120 columns. Check mode fills a preview (the current sha256 values, the time, the test summaries)
  and applies the line and width checks to it, so a line that only the fill makes too long, or turns into a driver
  form, stops before `--write-manifest`.
* Placeholders (review S4). Before `--write-manifest`, every placeholder has a value: a known kind, an existing
  `{{sha256:...}}` file (the manifest excepted, written later) and a `{{pytest:...}}` log that a test of the spec
  writes.
* Time (review S3, review 2 S4). The applier stops unless the local time zone is Beijing time (+0800); the entry
  states it. It stops as well when the time is earlier than the latest stamp of an entry head or an amendment title in
  Sec. 13.2 (now the G2 entry, 2026-11-15 06:43): a wrong clock.
* Temporary file (review S5, review 2 S8). The applier stops while `framelease_v4/.PROTOCOL.md.entrytmp` (inside the
  manifest scope) exists, writes it with an fsync before the rename, and removes it when an exception interrupts it.
* Driver files (review S6). It stops while a `protocol_txn.json` or `ALERT.txt` of the P1 stage driver or of the phase
  driver exists.
* Lock (review 2 S1). `--apply` stops unless the process holds `framelease_v4/.protocol.lock` through a descriptor
  inherited from `flock(1)` (the wrapper; `flock(LOCK_EX | LOCK_NB)` on that descriptor succeeds only for the holder).
* The composed PROTOCOL.md (review 2 S2, S3, S6, S8). The files the template cites are hashed once after
  `--write-manifest`; one that differs from the new manifest stops the application before PROTOCOL.md is written, and
  the entry is filled from these values. The newly registered files are counted over the composed PROTOCOL.md (the
  manifest files outside the registered set whose sha256 any part of it cites: what the phase driver's refresh
  registers) and must equal the unregistered manifest files that the template cites with `{{sha256:...}}` (at most
  `max_new_registered`). The composed text is read with `p1_driver.protocol_view` and `phase_driver.phase_view`: no
  Alert, the entry's title read once, the other amendment titles and the drivers' entries unchanged, each newly
  registered file first cited in Sec. 13.2 by the entry (`phase_driver.citing_amendment`). The in-place texts are
  counted in the order the applier applies them.
* Output (review 2 S8). `apply.out` shows the manifest difference (new, left, changed files) right after
  `--write-manifest`, and the line `composed PROTOCOL.md sha256 <hex>` right before the write: after a failure the
  wrapper seals only a PROTOCOL.md with this sha256.

The wrapper (review S1, S2, S5, S6; review 2 M1, S7). Each application runs through `$A/a10r7b/apply_locked.sh SPEC
OUTDIR`, detached from the calling terminal or tool (Sec. 1). It ignores SIGINT, SIGTERM and SIGHUP from the start
(the applier and `registration.py` inherit this). Inside one hold of `framelease_v4/.protocol.lock` (600 s wait; the
drivers lock the same file with `fcntl.flock`) it
1. refuses (exit 96, nothing done) while a `protocol_txn.json` or `ALERT.txt` of either driver or the temporary file
   `framelease_v4/.PROTOCOL.md.entrytmp` exists, or while `SEAL.sha256` does not match PROTOCOL.md and
   `MANIFEST.sha256`;
2. copies PROTOCOL.md, `MANIFEST.sha256`, `SEAL.sha256`, `REGISTRATION.json` and both drivers'
   `registered_baseline.json` into a new directory `OUTDIR/attempt_<time>_<pid>/` (one per attempt, never reused);
3. runs the applier with `--apply`, unbuffered (`python -u`), with `TZ=Asia/Shanghai`, into `OUTDIR/apply.out`;
4. waits while a python process of its own process group runs this root's `registration.py` (a killed applier leaves
   its child, which may still rewrite the manifest);
5. after a failure of the applier: when PROTOCOL.md equals its copy, it puts the sealed manifest back when the
   rewritten one differs and removes a temporary file the applier left; when PROTOCOL.md is the text the applier
   composed, it seals it with the manifest the entry names unless the seal matches already (exit 94), and when that
   seal fails it rolls PROTOCOL.md, the manifest, `SEAL.sha256` and `REGISTRATION.json` back to the copies (exit 93);
   a PROTOCOL.md that is neither is kept as `attempt_.../PROTOCOL.unexpected.md` and rolled back (exit 93), or left
   alone when it is sealed (exit 92). Every restore writes a temporary file and renames it;
6. exits 92 whenever `SEAL.sha256` does not match PROTOCOL.md and `MANIFEST.sha256` at this point; in every other case
   the lock is released with a matching seal;
7. runs `registration.py --verify` into `OUTDIR/verify.out`, appends it to `apply.out` and copies both into the
   attempt directory.

Exit codes: the applier's (0 sealed, 1 STOP or a traceback, 137 killed); 92 the state of before not restored (a
roll-back step failed) or a sealed PROTOCOL.md that the applier did not compose: hand recovery at once (Sec. 1); 93
rolled back, nothing applied; 94 the wrapper completed the application (the entry is in PROTOCOL.md
and sealed); 95 sealed, but the verification does not read "manifest: OK" and both seals OK; 96 refused at step 1; 97
the lock was not obtained in 600 s; 98 a copy into the attempt directory failed (nothing applied).

During the transaction a phase-driver cycle that finds the seal not matching (from the write of PROTOCOL.md to the
seal, about one second) logs the attention line "registration.py (pids ...) still running ..." and goes on at its
next cycle: its `tool_pids` counts the wrapper's `flock` and `bash` processes, whose command lines name `python` and
`framelease_v4/protocol/registration.py`. The line is expected and harmless. A cycle that reaches the lock waits for it
and reads the seal again under it.

## 1. Amendment A10 (`$A/final/A10_entry.md`, `$A/final/A10_spec.json`)

Applied on 2026-11-15 at 20:15 (`outputs/framelease_v4/amendment_a10/`): `apply_locked: exit 0`; `apply.out` shows the
pre-check verification "manifest: OK", the manifest difference `new [] / left [] / changed []`, the newly cited
manifest files exactly the eight A10 files and the verification "manifest: OK" with both seals OK; `post_check.py A10`
passes (23:47). This section records the procedure as prepared; Sec. 3 refers to it for the wrapper, the exit codes
and the recovery.

Preconditions, in this order (all read only):

1. Seal and drivers (the wrapper checks the driver files and the temporary file again under the lock).
   ```
   $P framelease_v4/protocol/registration.py --verify      # both "seal ...: OK" lines and "manifest: OK"
   ls outputs/framelease_v4/phase_driver/{ALERT.txt,protocol_txn.json}  # both: "No such file or directory"
   ls outputs/framelease_v4/p1_driver/{ALERT.txt,protocol_txn.json}     # both: "No such file or directory"
   ls framelease_v4/.PROTOCOL.md.entrytmp                               # "No such file or directory"
   $P -c "import json; b=json.load(open('outputs/framelease_v4/phase_driver/registered_baseline.json'))['files']; m=dict(reversed(l.rstrip('\n').split('  ',1)) for l in open('outputs/framelease_v4/registration/MANIFEST.sha256')); print([k for k,v in b.items() if m.get(k)!=v] or 'OK')"
                                                             # OK
   ```
   * From R7B attempt 6 (2026-11-15 13:15) to the G3 entry (20:13) `--verify` read "manifest: 2 files differ", naming
     exactly the two unregistered R7B files `framelease_v4/analysis/verify_table1_extra.py` and
     `framelease_v4/analysis/tests/test_verify_table1_extra.py`. The seal of the G3 entry (manifest `0fdb720e...`)
     recorded their current sha256, and A10 met "manifest: OK". Such a difference is never cleared by a seal outside
     a transaction (the next `--write-manifest` of an entry records it); any other file named is a problem.
2. The entry and its inputs.
   ```
   $P $A/check_drafts.py                                     # exit 0, "all checks passed", 5 x "found 1x now"
   $P $A/a10r7b/derive_inplace5.py --spec $A/final/A10_spec.json | tail -1
                                                             # "... in-place text 5 equals the derived text", exit 0
   $X sha256sum -c --quiet $A/a10r7b/evidence_sha256.txt     # no output, exit 0
   ```
   * Since item R7B, attempt 6 (2026-11-15 13:15), `sha256sum -c` reports exactly two lines FAILED (exit 1):
     `framelease_v4/analysis/verify_table1_extra.py` and `tests/test_verify_table1_extra.py`, lines of the A11 evidence
     of attempt 5 (lines 29-38). That is expected and does not concern A10; the A11 evidence is
     `f1/evidence_a11_sha256.txt` (Sec. 3). Any other FAILED line is a problem.
   * `check_drafts.py` reports a must_equal file as changed: that file carries its review first; then set its sha256
     in `final/A10_spec.json` and update the A10 text the change affects ("Known limitations", deviations 9 or 12,
     the counts "At drafting").
   * `derive_inplace5.py` exits 3 (Sec. 4.1 changed since 2026-11-15 07:03): `$P $A/a10r7b/derive_inplace5.py --spec
     $A/final/A10_spec.json --write $A/final/A10_spec.json`, then `check_drafts.py` again. It exits 1: the Sec. 4.1
     status paragraph of A3 is missing, doubled or already changed; resolve before going on.
   * `sha256sum -c` names a file: an evidence file changed after 2026-11-15 07:20; check why before going on (the
     entry cites the file's sha256 at application, and deviation 1 describes its content).
3. Deviation 1 is complete. It lists every execution of the aggregator (`aggregate_v4.py` and the modules it imports,
   `commit_audit.py` included) and of `analyze_v4.py`, `prop1_coverage.py`, `figures_tables.py` and
   `verify_independent.py` on real data from 2026-11-14 to the application, with time and output directory (at
   drafting: 2026-11-14, and item FILL0 with its review on 2026-11-15 from 01:24 to 03:33). The test runs are covered
   by the sentences on the tests. Review 2 (09:19-10:10) and fix pass 2 (10:16-11:05) ran neither the aggregator nor
   the four A10 files on real data (scratch trees, the drivers' parsers, and the test suites through `--tests`). List
   the PROGRESS files changed after fix pass 2 and search them:
   ```
   find outputs/framelease_v4/build -name 'PROGRESS*.md' -newermt '2026-11-15 11:05'
   grep -n -E 'aggregate_v4|commit_audit|analyze_v4|prop1_coverage|figures_tables|verify_independent' <each file>
   ```
   A further execution on real data (outside a test run): add it to deviation 1 with its time (with its date when it
   is not 2026-11-14) and output directory, copy the template into `$A/AMENDMENTS2_DRAFT.md` (`$P
   $A/a10r7b/edit_draft.py` replaces the embedded template block, from the A10 title line to its manifest line), and
   rerun `check_drafts.py`.
4. Tests (no lock; 76 s, 230 MB; the logs of 2026-11-15 10:54-10:55 pass: rerun when an A10 file or a module it
   imports changed):
   ```
   $P $A/a10r7b/apply_entry_stream.py $A/final/A10_spec.json --tests
   ```
   Expected: `pytest_analyze_v4.log` 48 passed, 107 subtests; `pytest_prop1_coverage.log` 22 passed;
   `pytest_figures_tables.log` 50 passed, 422 warnings; `pytest_verify_independent.log` 28 passed, 20 subtests; every
   line "exit 0". Keep `build/STRESS/s3_dev_report_v2.json` and `build/R5/dev_run/` (two tests read them).
5. Check mode (no lock; 7 s, 19 MB):
   ```
   $P $A/a10r7b/apply_entry_stream.py $A/final/A10_spec.json      # "check: pre-checks passed"
   ```

Application (the phase driver waits up to 300 s for the lock and retries at its next cycle). Run the wrapper detached,
so that neither a closed terminal nor a tool timeout reaches it, and wait for its last line:

```
O=outputs/framelease_v4/amendment_a10
setsid nohup $X bash $A/a10r7b/apply_locked.sh $A/final/A10_spec.json $O > $O/console.txt 2>&1 < /dev/null &
grep 'apply_locked: exit' $O/console.txt     # repeat until it prints (20-40 s; up to 600 s more while a driver
                                              # holds the lock)
```

Expected: `apply_locked: exit 0`; `$O/apply.out` shows the copies in `attempt_<time>_<pid>/`, `registration
--write-manifest --force -> 0`, the manifest difference (`changed` exactly the two R7B files while they differ from the
sealed manifest, else `new [] / left [] / changed []`; at the application of 20:15: `new [] / left [] / changed []`),
`composed PROTOCOL.md sha256 <hex>`, `--seal -> 0`, `--verify -> 0`, the line
`PROTOCOL <sha256> MANIFEST <sha256> <n> files; newly cited manifest files: [...]` with exactly the eight A10 files
(`analyze_v4.py`, `figures_tables.py`, `prop1_coverage.py`, `verify_independent.py` and their four tests), the filled
entry, and the appended verification (`verify.out`: "manifest: OK" and both seals OK).

Any other result; `apply.out` names the cause:
* `exit 1` with a `STOP:` line before `registration --write-manifest` (lock, temporary file, driver files, seal,
  registered files, must_equal, test log, entry exists, in-place text count or width, anchor, template, placeholders,
  time zone, time earlier than the last stamp, filled entry preview): nothing changed; resolve the named cause and run
  the wrapper again.
* `exit 1` with a `STOP:` line after `registration --write-manifest` (`registered files changed or left the new
  manifest`, `cited files changed after --write-manifest`, `unfilled placeholder`, `filled entry problem`, `the
  composed PROTOCOL.md would register`, `the composed PROTOCOL.md as the drivers read it`, `PROTOCOL.md changed during
  the transaction`), a traceback, or `exit 137` (killed) before PROTOCOL.md was written: PROTOCOL.md equals the attempt
  copy, and `apply.out` ends with "PROTOCOL.md unchanged; RESTORED the sealed manifest" or "PROTOCOL.md unchanged; the
  manifest equals the sealed one" (after "waited <n> s for a registration.py the applier started" when the applier was
  killed during `--write-manifest`, and with "removed the temporary file" when it left one) and the verification with
  both seals OK. Resolve the cause and run the wrapper again.
* `exit 94`: the applier stopped after it wrote PROTOCOL.md (killed, or its seal failed) and the wrapper completed the
  application under the same lock hold ("SEALED it with the manifest the entry names", or "the seal matches" when the
  applier stopped after its own seal). The verification reads "manifest: OK" and both seals OK (else the exit is 95):
  go on with the post-check as after exit 0.
* `exit 93`: the seal could not be completed, or PROTOCOL.md was not the text the applier composed (kept as
  `attempt_.../PROTOCOL.unexpected.md`); the wrapper rolled PROTOCOL.md, `MANIFEST.sha256`, `SEAL.sha256` and
  `REGISTRATION.json` back to the attempt copies. Nothing is applied and both seals verify; resolve the cause named in
  `apply.out` and run the wrapper again.
* `exit 92`: the state of before could not be restored (a roll-back step failed: disk or permissions), or PROTOCOL.md
  is sealed but is not the text the applier composed. "ROLL BACK FAILED": the seal does not match, and the phase
  driver raises an ALERT at its next cycle (within 300 s): act at once. "ROLL BACK INCOMPLETE": the seal matches again;
  compare each of the four files with the attempt copies. Under the lock, restore the four files of the attempt
  directory, each through a temporary file and a rename, or, when PROTOCOL.md is the composed text (its sha256 in
  `apply.out`), seal it: `flock -w 600 framelease_v4/.protocol.lock $P framelease_v4/protocol/registration.py --seal`;
  then `$P framelease_v4/protocol/registration.py --verify`. When the driver raised the ALERT meanwhile: with the seal
  verified, move `outputs/framelease_v4/phase_driver/ALERT.txt` aside and restart the driver.
* `exit 95`: sealed, but a file of the manifest changed between `--write-manifest` and `--seal` (the verification in
  `apply.out` names it), so the tree no longer matches the seal. Resolve it before anything else (a registered file
  changes only by an amendment that installs it).
* `exit 96`: a `protocol_txn.json` or `ALERT.txt` of a driver, or `framelease_v4/.PROTOCOL.md.entrytmp`, exists, or
  `SEAL.sha256` does not match PROTOCOL.md and `MANIFEST.sha256` (named in `apply.out`); nothing was done. A driver
  file: let the driver finish its transaction, or resolve its ALERT, first. The temporary file is left by an
  interrupted application: when `registration.py --verify` reads both seals OK, PROTOCOL.md is the sealed one; remove
  the file under the lock (`flock -w 600 framelease_v4/.protocol.lock rm framelease_v4/.PROTOCOL.md.entrytmp`) and run
  the wrapper again.
* `exit 97`: the lock was busy for 600 s (a driver transaction); run the wrapper again.
* `exit 98`: a copy into the attempt directory failed (a full disk, a missing baseline); nothing was applied.
* No line `apply_locked: exit` in `console.txt` and no wrapper process left (`pgrep -f a10r7b/apply_locked.sh` prints
  nothing): the wrapper was killed by SIGKILL, or the machine stopped. With a seal that does not match, the phase
  driver raises an ALERT at its next cycle. Under the lock, compare PROTOCOL.md with the newest
  `$O/attempt_*/PROTOCOL.md`. Equal: put that directory's `MANIFEST.sha256` back when they differ and remove
  `framelease_v4/.PROTOCOL.md.entrytmp` if it exists. Different and equal to the composed text of `apply.out`: seal as
  for exit 92. Otherwise restore the four files of the attempt directory. Then `registration.py --verify`; after an
  ALERT of the driver: move `phase_driver/ALERT.txt` aside and restart the driver.

Post-check:

```
$P $A/a10r7b/post_check.py A10
```

Exit 3 right after the application (the phase driver adds the eight files to `phase_driver/registered_baseline.json`
at its next cycle), exit 0 after that cycle; then `tail outputs/framelease_v4/phase_driver/driver.log` shows no ALERT
(an ATTENTION line on `registration.py` from the time of the transaction is expected, Sec. 0). `post_check.py A10`
checks: seal, parsers without ALERT, A10 read once, the first Sec. 13.2 line citing `analyze_v4.py` belongs to A10,
`phase_driver.analysis_registration` has no wait reason (gate G8 sees the analysis code registered), the five in-place
texts applied, no ALERT or transaction file of either driver, and that the phase driver's refresh registers exactly the
eight A10 files (against the copy of its baseline in the attempt directory; after the refresh the baseline gained
exactly these). Run it before A11 (A11 rewrites the text of A10's fourth in-place text). Update
`framelease_v4/PIPELINE_STATE.md`. From then on `check_drafts.py` does not apply (its simulation would insert A10 a
second time).

## 2. What changed in A10 and its spec (item a10r7b)

* Finding 1 states the rule of the A3-sealed `commit_audit.py` (`7439a4ea...`) in the words of edit E3 (A3,
  departure 6), and the re-audit result (`build/AGG/step0_reaudit/`: 0 violations, 47 PASS, 1 NO_LOG) and the PASS of
  `build/R7B/dev/agg_now/` and `agg_snap_2203/` (184 and 194 audited runs).
* Finding 2: the km floor of `runs.csv`, settled in `aggregate_v4.py` (`ee13c90b...`) before A3 (`agg_p1` 0.0,
  `agg_snap_2203` 0.001 for `v4p1smoke_fl_heuristic_E5_d10_k1.0_s11_r18305`).
* Deviation 1: every execution on real data from 2026-11-14 on, with time and output directory, from the PROGRESS files
  and console logs of R4, R5, R6, R7, AGG (AGG0), R7B and FILL0 and the review records; the draft listed five
  `analyze_v4.py` command-line runs on `smoke_D`, there were six (08:16, R4 step 70, console `smoke_train_partB.log`).
  Fix pass (review S7): item FILL0 and its review ran `analyze_v4.py` and `figures_tables.py` on 2026-11-15 from 01:24
  to 03:33 on synthetic aggregations, and with the default `--offline` both read the offline outputs written before
  registration: listed in their own bullet; the lead sentence gives times on 2026-11-14 unless a date is given (it
  said "all on 2026-11-14"); the re-audit of 14:09 / 14:10 names the earlier `commit_audit.py` (`96dd22c4...`, a copy
  under /tmp, the `--before-module` cross-check) and the current one.
* Evidence: the output manifests of `build/AGG/step0_reaudit/`, `build/R7B/dev/agg_now/` and `agg_snap_2203/`.
* Spec: the fifth in-place text, derived from the sealed PROTOCOL.md (below); nothing else. must_equal is unchanged:
  the eight A10 files and the three reused coverage files are at their drafting sha256 (APPLY_PLAN2 step 1 was not
  done; "Known limitations" stands); the counts "At drafting" therefore stand.
* `AMENDMENTS2_DRAFT.md` holds the edited template verbatim (`edit_draft.py`), its A10 preface states the second and
  fifth in-place texts after step 3, and its appendix the sha256 of the three added evidence files.

The fifth in-place text (APPLY_PLAN2 Sec. 4, step 1). `derive_inplace5.py` reads the clause pair from the A10
template's in-place bullet ("the analysis script, the Proposition-1 coverage and the figure and table generators
remain required before the analysis freeze" -> "the analysis script, the Proposition-1 coverage, the figure and table
generator and the independent verification script are registered by Amendment A10"), takes as "old" the one Sec. 4.1
paragraph that starts "Status (Amendment A3):" exactly as it stands (lines 483-486 of the sealed PROTOCOL.md, with the
sentence A4 appended), and as "new" that paragraph with the clause replaced and rewrapped at 120 columns. It checks:
"old" once in PROTOCOL.md (A3's own quotation of the clause in Sec. 13.2 is indented differently and stays untouched),
the words, the widths (max 119), no list, heading, driver-entry or amendment-title line, outside Sec. 13.2. Difference
from APPLY_PLAN2 Sec. 4: "old" is the whole paragraph, not the clause (the replaced clause is longer and the paragraph
is rewrapped, so no line exceeds 120 columns), and the new clause is the one the A10 entry states (APPLY_PLAN2's
shorter "are registered by Amendment A10" would contradict the entry text). Tested on the simulated post-step-3
PROTOCOL.md of `/tmp/AMEND3/tree/` and on the sealed one (equal results, equal to
`step3/sim_output/a10_inplace5_suggestion.json`), and on four failing copies (paragraph twice, clause already replaced,
paragraph text also elsewhere, PROTOCOL.md before A3).

## 3. Amendment A11 (`$A/a10r7b/A11_entry.md`, `$A/a10r7b/A11_spec.json`)

A11 registers `framelease_v4/analysis/verify_table1_extra.py` (`f77b2dcf...`) and
`framelease_v4/analysis/tests/test_verify_table1_extra.py` (`f0e74336...`), the files of item R7B, attempt 6, that the
second review of the fixes (`build/R7B/rereview/REVIEW.md`, round 2) passed with GO, and fixes the reporting rule of
the differences (item F1A11, 2026-11-15; `$A/a10r7b/f1/F1_RULE.md`). The name A11 stays: A12 (the cut) was applied
first and uses its own name. Its in-place text is the Sec. 9.12 "**Verification.**" paragraph as A10 leaves it; A10 is
applied, so it occurs once in PROTOCOL.md now (`check_a11.py`: "found 1x").

The reporting rule (decision of the coordinating session; A11 bullets "Reporting rule for the differences" and "Use of
the registered files", rules 2 and 3; `f1/F1_RULE.md` Sec. 1): `realized.py` stays as registered; the registered values
(aggregator and analysis through `realized.py`) are the values of Tables I and II and of the paper; the run after the
analysis freeze assigns every difference to a class defined by its mechanism: class F1 (cause 'F1'), class F3 (cause
'F3' or 'F1+F3'), class in-flight (the cross-check columns `gpu_usage_recomputed`, `gpu_busy_recomputed_s` and
`commits`, scope 'record', of a run that ended with a job still running, under the conditions of A11) and class not-ok
record (an empty registered value, scope 'record', in `runs.csv` or the runner's result fields, of a job whose final
runner outcome is not 'ok' and whose `runs.csv` row has analysis_use false); each class is
reported with its counts (all and in scope 'analysis'), the runs per arm and the largest absolute difference per column
(`f1/f1_class_report.py`, cited by sha256); the paper states each class and its size next to the verification result;
a difference that no class explains, in particular one in a value the analysis reads, is a verification failure under
Amendment A10, use rule 4. P1 development sizes (A11 "Development comparison", `f1/f1_class_dev.json`): class F1 26
differences in 19 of the 180 runs, one in a value the analysis reads (`fast_only`, route 1792: EIR 0.2063 registered,
0.2282 recomputed); class in-flight 69 in 31 runs, none in scope 'analysis'; class F3 none; class not-ok record the
41 of the timed-out run; no difference without a class. Expected in the 98 Table I runs of the A12 cut
(`f1/F1_RULE.md` Sec. 4): F1 in 9.4 runs (a condition mean over 14 routes holds an F1 route with probability 0.76), a
job in flight at the end in 13 to 17 runs, 0.36 F3 plans outside the 1e-3 s band, and the job that A12 records as
timed out twice (`v4p4_fl_original_k1.0_s11_r23658`) in class not-ok record.

Preconditions:

1. `$P $A/a10r7b/post_check.py A10` exits 0: done (2026-11-15 23:47, "post-check A10: passed"; the phase driver's
   refresh added the eight A10 files before A12 stopped it). Exit 3 with only the baseline refresh pending would be
   accepted (`post_check.py` says so; the applier counts the files that A10 cites as registered without the refresh).
2. The review of the R7B fixes: done. `build/R7B/rereview/REVIEW.md` (`e1220a89...`, equal to `REVIEW_round2.md`)
   reads "Verdict: GO" for the two files of MUST_EQUAL; the first round (`REVIEW_round1.md`, GO_WITH_FIXES) is cited
   as well. Its should-fix S1 (the candidate radius of F3) and S2 (four untested branches) are not applied; A11 states
   them under "Known limitations accepted".
   * When item R7B changes either file again (for example for these two should-fix items), the change carries its own
     review with verdict GO first. Then: the new sha256 in `make_a11_spec.py` (MUST_EQUAL) and the spec rewritten; the
     development comparison rerun when the recomputation changed, with "Development comparison", the class F1 numbers
     (`f1/f1_class_report.py` on the new output into `f1/f1_class_dev.json`), the review cells, "Known limitations",
     "Development data", the counts "At drafting" and the evidence list updated; then
     `$P $A/a10r7b/check_a11.py --write-evidence`.
   * A change of `f1/f1_class_report.py` or `f1/test_f1_class_report.py` carries its own review first; then its tests
     (logs in `f1/logs/`), the class reports `f1/f1_class_dev.json` and `f1/f1_class_p1_rundirs.json`, the numbers of
     `f1/F1_RULE.md` and A11, MUST_EQUAL in `make_a11_spec.py` and the spec, and `check_a11.py --write-evidence`.
   * A review written elsewhere: replace its path in `A11_entry.md` and `REREVIEW` in `check_a11.py`.
3. "Development data" is complete. The bullet names every execution of `verify_table1_extra.py` on real data from
   2026-11-14 to the application, outside a test run, with time and directory: item R7B from 2026-11-14 14:39 to
   2026-11-15 13:22, its review from 23:22 to 00:20, the review of the fixes (12:02-12:23), the second review of the
   fixes (13:36-14:01), the reading of class F1 and of the time offsets (14:06-14:13), the review of the reporting rule
   (14:40-14:58) and its fix passes (15:16 and 23:36-23:57). The last complete searches ran at 23:47:22 and 23:59:08
   (fix pass 2): after 14:13 only `f1/review/PROGRESS.md`, `f1/PROGRESS.md` and `build/G8CUT/PROGRESS.md` changed, the
   last without a match of the search terms. A later run adds to it:
   ```
   find outputs/framelease_v4/build -name 'PROGRESS*.md' -newermt '2026-11-15 23:59'
   grep -n -E 'verify_table1_extra|variant|p1_snap|p1_snapshot|agg_snap|agg_now|realized' <each file>
   ```
   A run of the item or of a review on real data (run directories, `runs.csv`): one sentence like those of the bullet
   (the run, its inputs, its times, its output directory, its PROGRESS.md); then `check_a11.py`.
4. Spec, tests, checks:
   ```
   $P $A/a10r7b/make_a11_spec.py --check                            # "equal to the generated spec", exit 0
   $P $A/a10r7b/apply_entry_stream.py $A/a10r7b/A11_spec.json --tests
                    # 87 passed, 80 subtests; 14 passed, 2 subtests; 26 passed, 31 subtests (each "exit 0")
   $P $A/a10r7b/check_a11.py                                        # exit 0, "all checks passed"
   $X sha256sum -c --quiet $A/a10r7b/f1/evidence_a11_sha256.txt     # no output, exit 0
   ```
   Run `--tests` right before the application, after the last change of any must_equal file (review S7). The logs in
   `amendment_a11/` (10:55) ran on the attempt-5 files (71 passed, 67 subtests) and the third log
   (`pytest_f1_class_report.log`) does not exist yet. The applier accepts any passing log and fills the "Tests" bullet
   from it (review dry run, step A5: "71 passed, 67 subtests" in the entry), so only this run and `check_a11.py` keep
   a stale count out of the entry. `check_a11.py` exit 2 lists what is open (A10 not entered; the review file missing
   or not GO; a test log missing, failing or older than a file of must_equal); exit 1 lists problems (placeholders,
   filled widths, parser collisions, a TODO line, the sentences of the reporting rule, the evidence pins of
   `f1/evidence_a11_sha256.txt`, the spec, the count of newly cited manifest files after `--write-manifest`, the
   simulation). Never apply A11 on exit 1 or 2 (the applier also stops before `--write-manifest` on a placeholder
   without a value: dry-run case C). `evidence_sha256.txt` of item a10r7b still lists the A11 evidence of attempt 5;
   the A11 evidence of this version is `f1/evidence_a11_sha256.txt`.
5. Seal and drivers as in Sec. 1, precondition 1. Expected now (fix pass 2, 2026-11-15 23:33 and at its end):
   `registration.py --verify` reads "manifest: OK", "seal framelease_v4/PROTOCOL.md: OK" and "seal
   outputs/framelease_v4/registration/MANIFEST.sha256: OK" (exit 0). The seal of the G3 entry (20:13; manifest
   `0fdb720e...`, kept by A10 and A12) recorded the two R7B files at `f77b2dcf...` and `f0e74336...`. What the
   pre-check of A11 sees: both seals OK; the R7B files in the sealed manifest at these sha256 but cited by no sha256
   of PROTOCOL.md, so outside the registered set (no stop); every registered file equal to the sealed manifest;
   must_equal equal. After `--write-manifest`: the manifest difference `new [] / left [] / changed []` (`check_a11.py`:
   "--write-manifest changes the sealed sha256 of []") and the newly cited manifest files exactly the two R7B files.
   Any file named by `--verify`, an R7B file that differs from `0fdb720e...` (precondition 2 first) or a non-empty
   manifest difference is a problem.
6. Check mode: `$P $A/a10r7b/apply_entry_stream.py $A/a10r7b/A11_spec.json` -> "check: pre-checks passed" after the
   `--tests` run of precondition 4. Before it (fix pass 2, 23:59:18): STOP at the test log
   `pytest_f1_class_report.log`, which does not exist yet; every pre-check before it passed (driver files, seal,
   registered files, must_equal). With a scratch copy of the spec and the template whose three test logs are the
   fresh drafting logs of `f1/logs/` (`/tmp/A10A11/f1fix/A11_spec.scratch.json`, 23:59:25) check mode reads "check:
   pre-checks passed" (in-place text once, anchor, placeholders, time, the filled preview).

Application and post-check:

```
O=outputs/framelease_v4/amendment_a11
setsid nohup $X bash $A/a10r7b/apply_locked.sh $A/a10r7b/A11_spec.json $O > $O/console.txt 2>&1 < /dev/null &
grep 'apply_locked: exit' $O/console.txt     # repeat until it prints
$P $A/a10r7b/post_check.py A11                # exit 3, then 0 after the phase driver's next cycle
```

When A10's refresh is still pending at A11 (`phase_driver/STOP`), `post_check.py A11` counts the eight A10 files among
the expected refresh additions. Expected: `apply_locked: exit 0`; `apply.out` shows `newly cited manifest files:
['framelease_v4/analysis/tests/test_verify_table1_extra.py', 'framelease_v4/analysis/verify_table1_extra.py']`
(`max_new_registered` 2) and `verify.out` "manifest: OK" and both seals OK. Any other result: as in Sec. 1. Update
`framelease_v4/PIPELINE_STATE.md`.

Deadline. G8 waits for A10 only (APPLY_PLAN2 Sec. 5, item 3). The phase driver is stopped now (`phase_driver/STOP`,
A12: its G7 requires the registered copies in `jobs.d`); A11 is applied before the coordinating session carries out
G8 (A12, "Execution").

After G8 (use rules 1-3 of A11; APPLY_PLAN2 step 8): an independent session runs, next to `verify_independent.py`,
```
$P framelease_v4/analysis/verify_table1_extra.py --analysis-freeze outputs/framelease_v4/analysis/final_<stamp> \
    --queue outputs/framelease_v4/queue_p4 [--queue <every other queue the aggregation covers>] \
    --agg outputs/framelease_v4/analysis/final_<stamp> \
    --analysis outputs/framelease_v4/analysis/final_<stamp>/analysis \
    --out outputs/framelease_v4/verification/final_<stamp>_table1_extra
$P $A/a10r7b/f1/f1_class_report.py outputs/framelease_v4/verification/final_<stamp>_table1_extra \
    --out outputs/framelease_v4/verification/final_<stamp>_table1_extra_f1_class.json
```
(status 'final' required; never `--runs-csv-values` or a test option; development run on the 180 P1 runs: 102 s,
110 MB; the class report: 0.05 s, 19 MB). Before the class report runs, `$X sha256sum $A/a10r7b/f1/f1_class_report.py`
equals the sha256 that A11 cites under "Evidence" (review S6); a different sha256 stops the procedure. The report's
`release` reads 'AGREE' or 'pre-specified classes only' (the columns are released with the registered values and every
class is reported) or 'verification failure' (every difference without a class is resolved and its cause entered in
Sec. 13 under A10 use rule 4 before any of these numbers enters the paper). The sha256 of `table1_extra.json`, of
`SHA256SUMS` and of the class report, with the numbers of each class, go into their own dated Sec. 13 entry before the
paper is written; the paper states each class and its size next to the verification result. The class report reads
the runner records (`queue_p4/status.jsonl`) and `runs.csv` that `table1_extra.json` 'inputs' names at their recorded
sha256 when a row can belong to class not-ok record: run it before any of these files changes, or the report stops
(exit 2).

Dry run of item F1A11 (2026-11-15, evidence in `f1/sim_output/`): `sim_tree.py --out /tmp/A10A11/f1/sim_tree --cases
A` (14:25:41-14:26:30, 49 s, 33 MB) on the A10 spec and the A11 spec and template of this version: A0 "tree seal"
fails only on "manifest: 2 files differ" for the two R7B files (precondition 5; `sim_tree.py` expects "manifest: OK");
A1-A9 pass: A10 check, `--apply` (newly cited the eight A10 files; the new manifest `0fdb720e...` holds the current R7B
sha256), seal "manifest: OK", parsers; A11 with the real review file: check, `--apply` (newly cited exactly the two
R7B files, manifest unchanged), seal OK, parsers (`analyze_v4.py` first cited by A10, both R7B files by A11, G8 without
wait). In the tree the "Tests" bullet reads "71 passed, 67 subtests" from the copied stale logs (precondition 4).
`f1/line_check.py` on the tree's PROTOCOL.md and on the in-memory texts of `check_a11.py --write-sim` (both against a
copy of the sealed PROTOCOL.md, `ca54d359...`): 533 added or changed lines after A10 and A11, every line over 120
columns a table row (13 of 24), no line read as a driver entry, heading or Sec. 13.2 start, the titles of A10 and A11
once each, the drivers' entries unchanged, a later gate entry read: "all checks passed". `check_a11.py`: "checks
passed", 3 open (A10 not entered; the two stale application test logs), exit 2.

Checks of fix pass 2 (2026-11-15 23:58-23:59, scratch `/tmp/A10A11/f1fix/`), with A10 and A12 in the sealed
PROTOCOL.md (`3fa337c1...`): `check_a11.py --protocol` a copy of it `--write-sim /tmp/A10A11/f1fix/sim`: checks
passed, the A11 in-place text found once, A11 entered after A12 before the anchor, newly cited after `--write-manifest`
exactly the two R7B files, `--write-manifest` changes no sealed sha256, the entry of G8 (the first gate not entered)
read after A11, 3 open (the two application logs of 10:55 older than a must_equal file; the third log missing), exit 2.
`f1/line_check.py` on that copy and `sim/PROTOCOL.after_A11.md` (`--expect A11`): 303 added or changed lines, every line
over 120 columns a table row (4 of 8), the title of A11 once, no driver entry, heading or Sec. 13.2 start, the entries
of both drivers unchanged (6 phase-driver entries, 10 P1 entries), every amendment A1-A12 still read, a later gate
entry read: "all checks passed". `make_a11_spec.py --check`: equal; `sha256sum -c f1/evidence_a11_sha256.txt`: OK.

## 4. Dry runs (2026-11-15, fix pass 2; evidence in `sim_output/` and `review_rerun/review2_logs/`)

`sim_tree.py` (10:31:35-10:38:37, the final files, 415 s, 33 MB; "ALL EXPECTED", 43 steps; `sim_output/summary.txt`):
scratch trees under `/tmp/A10A11/fix2/sim_tree/`, one at a time and removed at the end (real copies of
`framelease_v4/`, `registration/`, `p1_driver/`, `amendment_a10/`, `amendment_a11/`,
`phase_driver/registered_baseline.json` and `D1_DECISION.json`, `build/AMEND2/` without `step3/`, a real `build/R7B/`
of links; links for the rest; no queue, no `pipeline_state.json`; every written path checked to resolve inside the
tree), the applier with `ROOT` set to the tree (one line changed, checked), the wrapper with `APPLY_ROOT` / `APPLIER`,
a fault injector, and `drv.py` (the phase driver's `sealed_baseline` and `gate_g1` on the tree):
* A: A10 check passed; A10 `--apply` under `flock` sealed, newly cited manifest files = the eight A10 files, manifest
  unchanged (221 files); parsers without ALERT, `analyze_v4.py` first cited by A10, G8 `analysis_registration`
  without wait; A11 right after A10 (the phase baseline not refreshed; a stand-in review file in the tree): check
  passed, sealed, newly cited = the two R7B files; parsers: A10 and A11 read once, the R7B files first cited by A11, a
  later G3 entry of the phase driver read. Against the project PROTOCOL.md: Secs. 4.1, 9.4, 9.12 (Code, Freeze,
  Verification) and the two entries after G2; 438 added lines, no prose line over 120 columns (13 table rows, as in
  A3), none read as a driver entry, heading or Sec. 13.2 start, two amendment titles (A10, A11).
* B: A11 before A10 stops at the pre-check (in-place text found 0 times); PROTOCOL.md unchanged.
* C: A11 without the review file stops at the pre-check (a placeholder without a value), before `--write-manifest`;
  nothing changed, the seal verifies.
* D: A10 through the wrapper (exit 0; the copies in one `attempt_*/`); a new file in the manifest scope and A11 killed
  right after `--write-manifest`: exit 137, the sealed manifest restored, PROTOCOL.md unchanged, both seals verify;
  A11 again: sealed.
* E (review M1): `commit_audit.py` (phase baseline only) and `p3_rl.py` (the G4 tool) changed,
  `arms_ext/tests/test_drift_guard.py` (phase baseline only) and `rl/RL_PROTOCOL.md` (P1 baseline) removed: each
  stops in check mode and in the wrapper before `--write-manifest`, nothing changed; with every file restored, A10 is
  sealed.
* F: F1 a new file in the manifest scope and A10 killed before `--seal`: exit 94, the wrapper sealed under the same
  lock hold with the manifest the entry names (`1ea365bc...`; before `4bfe7451...`), verification OK (review 2 M1).
  F2 a registered file changed after `--write-manifest`: exit 95.
* G: TZ=UTC: the applier alone stops; the wrapper called with TZ=UTC stamps Beijing time; the temporary file and each
  driver's `protocol_txn.json` and `ALERT.txt`: wrapper exit 96 and check-mode STOP, nothing changed; template lines
  read as a G3 entry, an amendment title, a driver heading or holding the anchor phrase: check-mode STOP; the restored
  template passes.
* H (review 2 M1, S2, S7): H1 after a kill before `--seal` the seal is impossible (the manifest changed): exit 93,
  the four files rolled back, PROTOCOL.md, manifest, seal and `REGISTRATION.json` equal to the state of before,
  verification OK; H2 PROTOCOL.md edited by another hand before the kill: kept as `PROTOCOL.unexpected.md`, rolled
  back, exit 93; H3a the seal impossible and the roll-back stopped at the manifest: "ROLL BACK INCOMPLETE" (the seal
  matches again), exit 92; H3b stopped at PROTOCOL.md: "ROLL BACK FAILED" (unsealed), exit 92; H4 exit 94, then the
  wrapper again: STOP (entry exists), two attempt directories, the first with the sealed files before A10, both
  baselines, `apply.out` and `verify.out`; `post_check.py A10` exit 3, the driver's refresh adds exactly the eight A10
  files, `post_check.py A10` exit 0, `gate_g1` passes; H5 an empty file in scope sealed by the applier of before this
  pass (`orig/apply_entry_stream.before_fix2.py`): `post_check.py A10` exit 1 (the driver registers nine files).

`rerun_review2_sim.py` (10:39:21-10:53:47, 866 s, 34 MB): the harness of review 2 (`review2/review2_sim.py`,
unchanged, loaded as a module; trees under `/tmp/A10A11/applier/`, one at a time, removed at the end; logs in
`review_rerun/review2_logs/`; its case X pointed at the files of this directory) on the fixed applier and wrapper:
"ALL EXPECTED", 74 expectations (`review_rerun/review2_logs/expectations.txt`). Every step of the review's cases A, B,
P, K, O, L, T, M, S, C, D, Y and X occurs. The 14 steps that reproduced a defect now fail the review's own defect
check and pass positive checks on their logs: P (a changed P1 job file: check and wrapper STOP, nothing changed, the
driver's pre-check still names it), K3 (kill before `--seal`: exit 94, sealed, `gate_g1` passes), the race of K (no
unsealed window), O (kill during `--write-manifest`: the wrapper waited 3 s for the orphan, restored the manifest,
`gate_g1` passes), L3 (`--apply` without the lock: STOP), T2 (clock 06:30: STOP before `--write-manifest`), T3 and
T4.7-T4.9 (the check-mode preview stops a line that only the fill makes too long or turns into a driver form), T4.10
(`### 13.2 Amendments` in the template: STOP), T5 (an empty file in scope: STOP, manifest restored), S (SIGINT to the
process group: ignored, exit 0, sealed), Y (a cited file changed after `--write-manifest`: STOP before PROTOCOL.md is
written). Case X (the cases of the review's proposals, X1-X14) passes on the fixed files. R2 and K4R replace case R
(it reads the copies of the earlier wrapper) and the race of case K (it waits for "seal it now"): R2 exit 94 then
STOP, two attempt directories with their own copies; K4R a driver cycle during the recovery: no ALERT, the next cycle
passes. Applier 6-7 s and 18 MB in check mode; wrapper 16-20 s and 32 MB; `post_check.py` 3 s and 30 MB.

Fix pass 1 (superseded): `sim_tree.py` 09:08-09:14 and `rerun_review_sim.py` (review 1's harness) 08:57-09:07 on the
files of fix pass 1 (`sim_output_fix1/`, `review_rerun/logs/`); the classes of review 1 (registered files, refusals,
TZ, template lines, kills) are cases B, C, D, E, G of `sim_tree.py` and B, C, D, K1, K2, T4.1-T4.6 of review 2's
harness above.

`check_a11.py` simulates in memory on the current PROTOCOL.md (A10 when it is absent, then A11, then the entry of the
first phase-driver gate not entered yet: G8 now) with the same results. The dry runs of item F1A11 are at the end of
Sec. 3.

## 5. Open issues for the coordinating session

1. A11: the review of the R7B fixes returned GO (Sec. 3, precondition 2). Its should-fix S1 and S2 are not applied
   (A11 "Known limitations accepted"); applying them changes the two R7B files and needs precondition 2 again. The
   runs on real data enter "Development data" (Sec. 3, precondition 3).
2. The reporting rule: decided (`realized.py` unchanged; the classes F1, F3, in-flight and not-ok record of A11, Sec.
   3). The cross-check columns `gpu_usage_recomputed`, `gpu_busy_recomputed_s` and `commits` of `runs.csv` (69 of the
   110 development differences, in 31 of the 180 runs; scope 'record'; the `gpu_usage` that the analysis reads agrees
   within the in-flight bounds) form class in-flight; the 41 of the timed-out run form class not-ok record. Decided by
   the coordinating session after the review: class F3 holds the cause 'F1+F3' as well as 'F3' (the same convention
   together with F1 in one value), and the fourth class not-ok record covers the empty registered values of a job
   whose final runner outcome is not 'ok' (A12 records one such Table I job, `v4p4_fl_original_k1.0_s11_r23658`). The
   earlier texts gave the offsets of F1 as 3e-7 to 1.1e-6 s; the measured range reaches 3.0e-6 s (A11,
   `f1/F1_RULE.md`).
3. `outputs/framelease_v4/paper_tools/apply_entry.py` (the generic applier, not edited here) keeps the defects that
   the reviews found here: whole-file reads (5.8 GB RSS), the P1 baseline only and no missing-file check (M1), no
   driver-form check of the template (S4), local time (S3), no temporary-file and phase-driver checks (S5, S6), no copy
   of the sealed manifest; and from review 2: the P1 job files not protected (M2), no lock check (S1), the newly
   registered files counted on the entry only (S2), no parser, stamp-order or width check (S3-S5), a cited file
   changed after `--write-manifest` cited at a sha256 the manifest does not hold (S6). It has no wrapper that seals or
   rolls back before the lock is released (review 2 M1). Apply A10 and A11 only through `apply_locked.sh` with
   `apply_entry_stream.py`; a later entry of the same form (APPLY_PLAN2 step 8) can use them with its own spec.
4. A10 deviation 1 must stay complete up to the application (Sec. 1, precondition 3), and A11 "Development data" up to
   its application (Sec. 3, precondition 3).
5. Run the wrapper detached (Sec. 1). Only a SIGKILL of the wrapper itself, or a machine stop, during the transaction
   leaves the hand recovery of Sec. 1 ("No line `apply_locked: exit`"), and the phase driver raises an ALERT at its
   next cycle when the seal does not match then.
6. Resolved: `check_a11.py` (item F1A11) uses the registered set of `apply_entry_stream.py` with the P1 job files and
   counts the newly cited files on the manifest that `--write-manifest` writes (2 now, the two R7B files).

## 6. Files

sha256 at the end of item a10r7b, fix pass 2 (2026-11-15); the rows of item F1A11 at the end of its fix pass 2
(2026-11-16 00:00); the `amendment_a10/` logs as the A10 application wrote them (2026-11-15 20:14-20:15).

| sha256 | file |
|---|---|
| `9790c164405f432a813df39986b84853bd18ac078b5d4afff0ea51915ea324ca` | `outputs/framelease_v4/build/AMEND2/final/A10_entry.md` |
| `b1de9f6a976da98dc0da9da48fff5a1e2ec55512dfaac581ad7eb73a64335b0e` | `outputs/framelease_v4/build/AMEND2/final/A10_spec.json` |
| `03bfb7f44e89cbc4d88ac12ca96f7366c05188cfae22de58fccc8b9357861eac` | `outputs/framelease_v4/build/AMEND2/AMENDMENTS2_DRAFT.md` |
| `db3729c26bb635f96027f78f229e0a8a033826e2ad70c2cb67f64f2a59e4036a` | `outputs/framelease_v4/build/AMEND2/a10r7b/A11_entry.md` |
| `71323aad67f5d4d7f5933fd670180d16de36b7d6fb82977fea8e97b804e1feaf` | `outputs/framelease_v4/build/AMEND2/a10r7b/A11_spec.json` |
| `7d86e576f2c8413f642c2c6ab7bba94212dcf573558d3be8e6d03eb19deb3884` | `outputs/framelease_v4/build/AMEND2/a10r7b/apply_entry_stream.py` |
| `8e87f0c20d05cc5e90bff569b09e7433171b26e0bdb1c6d44fe586d245707184` | `outputs/framelease_v4/build/AMEND2/a10r7b/apply_entry_stream.diff` |
| `1de9b701aabfc7ec607c840123a315df152393315b4ed9bd386961ebc4212310` | `outputs/framelease_v4/build/AMEND2/a10r7b/apply_locked.sh` |
| `4d0fff50e6484862bd2040ba2c54ea81d652834c761e48dcb3ac69d30fbaf106` | `outputs/framelease_v4/build/AMEND2/a10r7b/derive_inplace5.py` |
| `ee1603e2c3a84c1f934f60b8b1956d452f1306da1474b11126b52f83e0db6302` | `outputs/framelease_v4/build/AMEND2/a10r7b/make_a11_spec.py` |
| `ed87abb77ce4ae2d8aa2f4da8488c96ddeb7b79aca9666ce02be29f51255b443` | `outputs/framelease_v4/build/AMEND2/a10r7b/check_a11.py` |
| `7b08460b0fd96ec2cdfd9994677d59f6a378ec42dba23401db116ccfd61149ac` | `outputs/framelease_v4/build/AMEND2/a10r7b/post_check.py` |
| `59b7a83ce99b98f51b3dc8f17870cafec5920a0683af884caacce5cc00554c92` | `outputs/framelease_v4/build/AMEND2/a10r7b/sim_tree.py` |
| `fdb0e3a1b57abf1a6a225d8c859f52907b5974f04c0460ec74e23aaf9f256bd7` | `outputs/framelease_v4/build/AMEND2/a10r7b/rerun_review2_sim.py` |
| `f3c08af4d34aee3e31c19c04621459bd6d872e532318441722b624dcb11ba44a` | `outputs/framelease_v4/build/AMEND2/a10r7b/rerun_review_sim.py` |
| `67c6955cefae786fa532afa17bc351fd565d82a3a8c8fa1408dad80f0815ac98` | `outputs/framelease_v4/build/AMEND2/a10r7b/edit_draft.py` |
| `78058f6e38a53f950771c90a2dae5232c03e4e49b6a8e3cc3b84eed24c9e50c5` | `outputs/framelease_v4/build/AMEND2/a10r7b/baseline_check.py` |
| `c72ed83ffd79b180968b824159e3ae4242d0803d19bdeb125bf114d4623ea22b` | `outputs/framelease_v4/build/AMEND2/a10r7b/evidence_sha256.txt` |
| `3d6c4e3bd50d61cacec60d0bbbafc4531dcd5b3e0674c028f48f0f4f207c5e18` | `outputs/framelease_v4/amendment_a10/pytest_analyze_v4.log` |
| `7f27d7c271a0960e4af368c308550422d052b3e9eba990a9b080d6edbc97e3d0` | `outputs/framelease_v4/amendment_a10/pytest_figures_tables.log` |
| `19d26691f913722dada248000164eea1d9729028967268a6d4f75f3195a87152` | `outputs/framelease_v4/amendment_a10/pytest_prop1_coverage.log` |
| `527b6de39dc8039fca790d485d31f78ae36bdb2971189b3f36a25428a3cf5b36` | `outputs/framelease_v4/amendment_a10/pytest_verify_independent.log` |
| `6524a1202df9e35aee21b4f4529060e8456cb027f4ea3dd06e401831cfc7511a` | `outputs/framelease_v4/amendment_a11/pytest_review_r7b.log` |
| `8c6be5f95f57874c6fd05cf8f5ec54af3febffa31ca736c4e5050f39d5a60ded` | `outputs/framelease_v4/amendment_a11/pytest_verify_table1_extra.log` |
| `4c7384d3b5f8ead8f0f9258808b511b9401b8c3a7b0d23ea44016f09a0351eb8` | `outputs/framelease_v4/build/AMEND2/a10r7b/f1/F1_RULE.md` |
| `4c7f3af5981bf0328caa9897e6525f63ca891dc1e08f48cc9a29148b65cf30e7` | `outputs/framelease_v4/build/AMEND2/a10r7b/f1/f1_class_report.py` |
| `f26ffb38558420a83d35300ec5b8797f516e21fb1bfcff21a6094194272c2955` | `outputs/framelease_v4/build/AMEND2/a10r7b/f1/test_f1_class_report.py` |
| `f0344500ba82efdf8bccccd8ab50ca48f887ca27774a20592fe1ae569bd93d9b` | `outputs/framelease_v4/build/AMEND2/a10r7b/f1/f1_class_dev.json` |
| `750387ed2898c80a017ce3f363b31c28abb55152f4828bf373deb0b5ae8d415b` | `outputs/framelease_v4/build/AMEND2/a10r7b/f1/f1_class_p1_rundirs.json` |
| `6184bd8ed754d3d8f31088a6a974b03b0d6aad86c9370d378006b566560f5cb8` | `outputs/framelease_v4/build/AMEND2/a10r7b/f1/evidence_a11_sha256.txt` |
| `565c26743f54b4787a755431780fb8faf70fff74830ad6269dd7d666210a9318` | `outputs/framelease_v4/build/AMEND2/a10r7b/f1/line_check.py` |
| `24675e87448bf923bea358b7f2cc16cca8224ede74aa12646985800e21010028` | `outputs/framelease_v4/build/AMEND2/a10r7b/f1/logs/pytest_verify_table1_extra.log` |
| `8daa6c8d12a056c456744753589f3822ebcace108b834a9e13b837db0aab4ef0` | `outputs/framelease_v4/build/AMEND2/a10r7b/f1/logs/pytest_review_r7b.log` |
| `6861dfc2e3273a3e9cc8e69f3414e0473d30968e4e48ffee7f2d5179ae843633` | `outputs/framelease_v4/build/AMEND2/a10r7b/f1/logs/pytest_f1_class_report.log` |
| `6b3bf3958071de2a8dc1b5e41a36a946a82a24339f7d3665f38b04579d259ad1` | `outputs/framelease_v4/build/AMEND2/a10r7b/f1/fix1_numbers.py` |
| `bda65ff9b1284ad0f73431b0aacbbade41d9c9e5deea99be21f4d68b886fb76e` | `outputs/framelease_v4/build/AMEND2/a10r7b/f1/fix1_numbers.json` |

Backups: `f1/orig/*.before_f1.*` (the five files that item F1A11 changed, before it), `f1/orig/*.before_fix1.*` and
`f1/orig/*.before_fix2.*` (the files of its fix passes 1 and 2, before them); `orig/` (before item a10r7b:
A10_entry c51566ea..., A10_spec e92a5dce..., AMENDMENTS2_DRAFT f022b942...; before fix pass 1, `*.before_fix.*`, the
versions review 1 read; before fix pass 2, `*.before_fix2.*`, the versions review 2 read). Drafting copies of the test
logs: `logs/` (item a10r7b) and `f1/logs/` (item F1A11). Dry-run evidence: `f1/sim_output/` (item F1A11, case A of
`sim_tree.py` and the line checks), `sim_output/` (fix pass 2, with the simulated PROTOCOL.md after A10 and A11 as
`PROTOCOL.after_A10_A11.simulated.md.txt`; never a source for the drivers) and `review_rerun/review2_logs/` (review 2's
harness); earlier: `sim_output_fix1/`, `sim_output_before_fix/` and `review_rerun/logs/` (review 1's harness).
