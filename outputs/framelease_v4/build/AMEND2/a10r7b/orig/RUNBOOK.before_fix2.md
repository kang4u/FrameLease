# RUNBOOK: Amendment A10 (analysis code) and Amendment A11 (R7B recomputation of the other Table I columns)

For the coordinating session. Item a10r7b prepared both entries; nothing is applied by it. PROTOCOL.md, the
registration files, the seal, every registered file and the drivers' directories are unchanged by this item. This
version includes the fixes of the review `review/REVIEW.md` (GO_WITH_FIXES: must-fix M1, should-fix S1-S9).

State at the end of this item (2026-11-15, Beijing time): step 3 of `APPLY_PLAN2.md` is sealed (06:40: A3, A9, A7b, A4
and the operational addition); `D1_DECISION.json` 06:42; the phase driver runs since 06:42:42 (G1 06:42, G2 06:43,
G3 running: 132 P2 jobs in `queue_p2`, 14 final at 08:48). A10 is applicable now (APPLY_PLAN2 Sec. 2, step 6: after
step 3, recommended before the test freeze G6, required before the analysis freeze G8). A11 follows A10 and needs the
review of the fixed R7B Part B first (Sec. 3 below); it is required before the analysis freeze (APPLY_PLAN2 step 7).

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
* Registered files (review M1). `apply_entry.py` protects only the 153 files of `p1_driver/registered_baseline.json`
  and skips a registered file that is missing. Here the registered files are those of
  `p1_driver/registered_baseline.json` and of `phase_driver/registered_baseline.json` (both must exist; 199 files
  together now) and every sealed-manifest file whose sha256 PROTOCOL.md cites (the rule of
  `phase_driver.refresh_baseline`, so the files of A10 count as registered before the driver's next refresh). The
  pre-check stops when a registered file is absent from the sealed manifest, missing on disk or different from it;
  after `--write-manifest` the applier stops when a registered file changed or left the new manifest.
* Lines (review S4). The template and the filled entry hold no line after the title that a driver reads as an entry
  (`p1_driver.ENTRY_RE`, `phase_driver.ENTRY_RE`), an amendment title (`phase_driver.AMEND_RE`) or a driver heading,
  and the anchor phrase nowhere (the expressions equal the drivers' own).
* Placeholders (review S4). Before `--write-manifest`, every placeholder has a value: a known kind, an existing
  `{{sha256:...}}` file (the manifest excepted, written later) and a `{{pytest:...}}` log that a test of the spec
  writes.
* Time zone (review S3). The applier stops unless the local time zone is Beijing time (+0800); the entry states it.
* Temporary file (review S5). The applier stops while `framelease_v4/.PROTOCOL.md.entrytmp` (inside the manifest
  scope) exists, and removes its temporary file when an exception interrupts it.
* Driver files (review S6). It stops while a `protocol_txn.json` or `ALERT.txt` of the P1 stage driver or of the phase
  driver exists.

The wrapper. Each application runs through `$A/a10r7b/apply_locked.sh SPEC OUTDIR`. Inside one hold of
`framelease_v4/.protocol.lock` (600 s wait; the drivers lock the same file with `fcntl.flock`) it
1. refuses (exit 96, nothing done) while a `protocol_txn.json` or `ALERT.txt` of either driver or the temporary file
   `framelease_v4/.PROTOCOL.md.entrytmp` exists (S5, S6);
2. copies the sealed `MANIFEST.sha256` and `PROTOCOL.md` to `OUTDIR/MANIFEST.sealed.before_apply` and
   `OUTDIR/PROTOCOL.sealed.before_apply`;
3. runs the applier with `--apply`, unbuffered (`python -u`), with `TZ=Asia/Shanghai`, into `OUTDIR/apply.out` (S1, S3);
4. after a failure of the applier: while PROTOCOL.md equals its copy (the entry is not written) it puts the sealed
   manifest back when the rewritten one differs and removes a temporary file the applier left; when PROTOCOL.md holds
   the entry it keeps the rewritten manifest (the one the entry names) and writes "seal it now" (S1);
5. runs `registration.py --verify` into `OUTDIR/verify.out` and appends it to `apply.out`.

Exit codes: the applier's (0 sealed, 1 STOP or a traceback, 137 killed); 95 sealed, but the verification does not
read "manifest: OK" and both seals OK (S2); 96 refused at step 1; 97 the lock was not obtained in 600 s; 98 a copy
failed.

## 1. Amendment A10 (`$A/final/A10_entry.md`, `$A/final/A10_spec.json`)

Preconditions, in this order (all read only):

1. Seal and drivers (the wrapper checks the driver files and the temporary file again under the lock).
   ```
   $P framelease_v4/protocol/registration.py --verify      # "manifest: OK" and both "seal ...: OK" lines
   ls outputs/framelease_v4/phase_driver/{ALERT.txt,protocol_txn.json}  # both: "No such file or directory"
   ls outputs/framelease_v4/p1_driver/{ALERT.txt,protocol_txn.json}     # both: "No such file or directory"
   ls framelease_v4/.PROTOCOL.md.entrytmp                               # "No such file or directory"
   $P -c "import json; b=json.load(open('outputs/framelease_v4/phase_driver/registered_baseline.json'))['files']; m=dict(reversed(l.rstrip('\n').split('  ',1)) for l in open('outputs/framelease_v4/registration/MANIFEST.sha256')); print([k for k,v in b.items() if m.get(k)!=v] or 'OK')"
                                                             # OK
   ```
2. The entry and its inputs.
   ```
   $P $A/check_drafts.py                                     # exit 0, "all checks passed", 5 x "found 1x now"
   $P $A/a10r7b/derive_inplace5.py --spec $A/final/A10_spec.json | tail -1
                                                             # "... in-place text 5 equals the derived text", exit 0
   $X sha256sum -c --quiet $A/a10r7b/evidence_sha256.txt     # no output, exit 0
   ```
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
   by the sentences on the tests. List the PROGRESS files changed after this item and search them:
   ```
   find outputs/framelease_v4/build -name 'PROGRESS*.md' -newermt '2026-11-15 09:15'
   grep -n -E 'aggregate_v4|commit_audit|analyze_v4|prop1_coverage|figures_tables|verify_independent' <each file>
   ```
   A further execution on real data (outside a test run): add it to deviation 1 with its time (with its date when it
   is not 2026-11-14) and output directory, copy the template into `$A/AMENDMENTS2_DRAFT.md` (`$P
   $A/a10r7b/edit_draft.py` replaces the embedded template block, from the A10 title line to its manifest line), and
   rerun `check_drafts.py`.
4. Tests (no lock; 76 s, 230 MB; the logs of 2026-11-15 08:57 pass: rerun when an A10 file or a module it imports
   changed):
   ```
   $P $A/a10r7b/apply_entry_stream.py $A/final/A10_spec.json --tests
   ```
   Expected: `pytest_analyze_v4.log` 48 passed, 107 subtests; `pytest_prop1_coverage.log` 22 passed;
   `pytest_figures_tables.log` 50 passed, 422 warnings; `pytest_verify_independent.log` 28 passed, 20 subtests; every
   line "exit 0". Keep `build/STRESS/s3_dev_report_v2.json` and `build/R5/dev_run/` (two tests read them).
5. Check mode (no lock; 8 s, 18 MB):
   ```
   $P $A/a10r7b/apply_entry_stream.py $A/final/A10_spec.json      # "check: pre-checks passed"
   ```

Application (the phase driver waits up to 300 s for the lock and retries at its next cycle):

```
bash $A/a10r7b/apply_locked.sh $A/final/A10_spec.json outputs/framelease_v4/amendment_a10
```

Expected: `apply_locked: exit 0`; `outputs/framelease_v4/amendment_a10/apply.out` shows `registration --write-manifest
--force -> 0`, `--seal -> 0`, `--verify -> 0`, the line `PROTOCOL <sha256> MANIFEST <sha256> <n> files; newly cited
manifest files: [...]` with exactly the eight A10 files (`analyze_v4.py`, `figures_tables.py`, `prop1_coverage.py`,
`verify_independent.py` and their four tests), the filled entry, and the appended verification (`verify.out`:
"manifest: OK" and both seals OK).

Any other result; `apply.out` names the cause:
* `exit 1` with a `STOP:` line before `registration --write-manifest` (temporary file, driver files, seal, registered
  files, must_equal, test log, entry exists, in-place text count, anchor, template, placeholders, time zone): nothing
  changed; resolve the named cause and run the wrapper again.
* `exit 1` with a `STOP:` line after `registration --write-manifest` (`registered files changed or left the new
  manifest`, `unfilled placeholder`, `filled entry problem`, `the entry cites the sha256 of unregistered manifest
  files`, `PROTOCOL.md changed during the transaction`), a traceback, or `exit 137` (killed) before PROTOCOL.md was
  written: PROTOCOL.md equals `OUTDIR/PROTOCOL.sealed.before_apply`, and `apply.out` ends with "PROTOCOL.md unchanged;
  RESTORED the sealed manifest" or "PROTOCOL.md unchanged; the manifest equals the sealed one" (and "removed the
  temporary file" when the applier left one) and the verification with both seals OK. Resolve the cause and run the
  wrapper again.
* "PROTOCOL.md holds the entry but is not sealed" (`seal failed`, or a kill after PROTOCOL.md was written): the
  wrapper kept the rewritten manifest, the one the entry names. Seal at once and verify:
  `flock -w 600 framelease_v4/.protocol.lock $P framelease_v4/protocol/registration.py --seal`, then
  `$P framelease_v4/protocol/registration.py --verify` ("manifest: OK" and both seals OK), then the post-check. When
  the verification names a file, that file changed after `--write-manifest`: resolve it before anything else (a
  registered file changes only by an amendment that installs it).
* `exit 95`: sealed, but a file of the manifest changed between `--write-manifest` and `--seal` (the verification in
  `apply.out` names it), so the tree no longer matches the seal. Resolve it before anything else.
* `exit 96`: a `protocol_txn.json` or `ALERT.txt` of a driver, or `framelease_v4/.PROTOCOL.md.entrytmp`, exists
  (named in `apply.out`); nothing was done. A driver file: let the driver finish its transaction, or resolve its ALERT,
  first. The temporary file is left by an interrupted application: when `registration.py --verify` reads both seals
  OK, PROTOCOL.md is the sealed one; remove the file under the lock (`flock -w 600 framelease_v4/.protocol.lock rm
  framelease_v4/.PROTOCOL.md.entrytmp`) and run the wrapper again.
* `exit 97`: the lock was busy for 600 s (a driver transaction); run the wrapper again.
* No line `apply_locked: exit` on the console (the wrapper itself was interrupted): under the lock, compare
  PROTOCOL.md with `OUTDIR/PROTOCOL.sealed.before_apply`. Equal: put `OUTDIR/MANIFEST.sealed.before_apply` back as
  `MANIFEST.sha256` when they differ, and remove `framelease_v4/.PROTOCOL.md.entrytmp` if it exists. Different (the
  entry is written): seal as above. Then `registration.py --verify`.

Post-check:

```
$P $A/a10r7b/post_check.py A10
```

Exit 3 right after the application (the phase driver adds the eight files to `phase_driver/registered_baseline.json`
at its next cycle), exit 0 after that cycle; then `tail outputs/framelease_v4/phase_driver/driver.log` shows no ALERT.
`post_check.py A10` checks: seal, parsers without ALERT, A10 read once, the first Sec. 13.2 line citing `analyze_v4.py`
belongs to A10, `phase_driver.analysis_registration` has no wait reason (gate G8 sees the analysis code registered),
the five in-place texts applied, no ALERT or transaction file. Run it before A11 (A11 rewrites the text of A10's fourth
in-place text). Update `framelease_v4/PIPELINE_STATE.md`. From then on `check_drafts.py` does not apply (its
simulation would insert A10 a second time).

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

A11 registers `framelease_v4/analysis/verify_table1_extra.py` (`a8bf57b7...`) and
`framelease_v4/analysis/tests/test_verify_table1_extra.py` (`c3bf160c...`); the name A11 is the next free one
(PROTOCOL.md and the drafts use none). Its in-place text is the Sec. 9.12 "**Verification.**" paragraph as A10 leaves
it, so A11 is applied after A10 (before A10 its pre-check stops: "in-place text found 0 times").

Preconditions:

1. `$P $A/a10r7b/post_check.py A10` exits 0. While the phase driver is stopped by `phase_driver/STOP` (the deadline
   rule below), exit 3 with only the baseline refresh pending is accepted (`post_check.py` says so): every other check
   has passed, and the applier counts the files that A10 cites as registered without the refresh (review S9).
2. The review of the fixed R7B Part B (R7B review: "the fixed Part B needs a re-review of its changes before the R7B
   amendment"): continuous V, lease footprint, decoder, guard (`build/R7B/PROGRESS.md`, attempt 5). The template names
   it `outputs/framelease_v4/build/R7B/rereview/REVIEW.md` with verdict GO (file table and Evidence).
   * Written elsewhere: replace that path in `A11_entry.md` (two places) and `REREVIEW` in `check_a11.py`.
   * Verdict GO_WITH_FIXES: the fixes are applied and reviewed; set the new sha256 in `make_a11_spec.py` (MUST_EQUAL)
     and rerun it; rerun the P1 development comparison when the recomputation changed and update the "Development
     comparison" bullet; update the review cell, the counts "At drafting" and the evidence list.
3. "Development data" is complete (review S8). The bullet names every execution of `verify_table1_extra.py` on real
   data from 2026-11-14 to the application, outside a test run, with time and directory: item R7B from 2026-11-14
   14:39 to 2026-11-15 01:13 and its review from 23:22 to 00:20 at drafting. The re-review and any later run of the
   item add to it:
   ```
   find outputs/framelease_v4/build -name 'PROGRESS*.md' -newermt '2026-11-15 01:13'
   grep -n -E 'verify_table1_extra|variant|p1_snap|p1_snapshot|agg_snap|agg_now' <each file>
   ```
   A run of the re-review on real data (run directories, `runs.csv`): one sentence like the review's ("The review of
   the fixes ran ... on ... from ... to ..., into ... (`build/R7B/rereview/PROGRESS.md`)"); a further run of the item:
   extend "to 2026-11-15 01:13" and name its directory. Then `check_a11.py` again.
4. Spec, tests, checks:
   ```
   $P $A/a10r7b/make_a11_spec.py --check                            # "equal to the generated spec", exit 0
   $P $A/a10r7b/apply_entry_stream.py $A/a10r7b/A11_spec.json --tests
                                                                     # 71 passed, 67 subtests; 14 passed, 2 subtests
   $P $A/a10r7b/check_a11.py                                        # exit 0, "all checks passed"
   $X sha256sum -c --quiet $A/a10r7b/evidence_sha256.txt            # no output, exit 0
   ```
   `check_a11.py` exit 2 lists what is open (A10 not entered, the review file missing or not GO, a test log missing or
   failing); exit 1 lists problems (placeholders, widths, parser collisions, spec, the count of newly cited manifest
   files, the simulation). Never apply A11 on exit 1 or 2 (the applier also stops before `--write-manifest` on a
   placeholder without a value: dry-run case C).
5. Seal and drivers as in Sec. 1, precondition 1. After the re-review changed the two R7B files (unregistered),
   `registration.py --verify` reads "manifest: 2 files differ" naming exactly these two; that is expected (the A11
   transaction writes them into the manifest); any other file named is a problem. The applier compares every
   registered file with the sealed manifest itself.
6. Check mode: `$P $A/a10r7b/apply_entry_stream.py $A/a10r7b/A11_spec.json` -> "check: pre-checks passed".

Application and post-check:

```
bash $A/a10r7b/apply_locked.sh $A/a10r7b/A11_spec.json outputs/framelease_v4/amendment_a11
$P $A/a10r7b/post_check.py A11                     # exit 3, then 0 after the phase driver's next cycle
```

Expected: `apply_locked: exit 0`; `apply.out` shows `newly cited manifest files:
['framelease_v4/analysis/tests/test_verify_table1_extra.py', 'framelease_v4/analysis/verify_table1_extra.py']`
(`max_new_registered` 2) and `verify.out` "manifest: OK" and both seals OK. Any other result: as in Sec. 1. Update
`framelease_v4/PIPELINE_STATE.md`.

Deadline. G8 waits for A10 only (APPLY_PLAN2 Sec. 5, item 3): when A11 is not entered while the last tier-6 jobs run,
write `outputs/framelease_v4/phase_driver/STOP` (the driver stops at its next cycle; the runner continues) and restart
the driver after A11, with `STOP` moved aside.

After G8 (use rules 1-3 of A11; APPLY_PLAN2 step 8): an independent session runs, next to `verify_independent.py`,
```
$P framelease_v4/analysis/verify_table1_extra.py --analysis-freeze outputs/framelease_v4/analysis/final_<stamp> \
    --queue outputs/framelease_v4/queue_p4 [--queue <every other queue the aggregation covers>] \
    --agg outputs/framelease_v4/analysis/final_<stamp> \
    --analysis outputs/framelease_v4/analysis/final_<stamp>/analysis \
    --out outputs/framelease_v4/verification/final_<stamp>_table1_extra
```
(status 'final' required; never `--runs-csv-values` or a test option; development run on 180 P1 runs: 95 s, 158 MB),
and the sha256 of `table1_extra.json` and `SHA256SUMS` go into their own dated Sec. 13 entry before the paper is
written.

## 4. Dry runs (2026-11-15, fix pass; evidence in `sim_output/` and `review_rerun/logs/`)

`sim_tree.py` (09:08:44-09:13:44, final texts, 299 s, 32 MB; "ALL EXPECTED", 37 steps; `sim_output/summary.txt`):
scratch trees under `/tmp/AMEND3/a10r7b/sim_tree/` (real copies of `framelease_v4/`, `registration/`, `p1_driver/`,
`amendment_a10/`, `amendment_a11/`, `phase_driver/registered_baseline.json`, `build/AMEND2/` without `step3/`, a real
`build/R7B/` of links; links for the rest; no queue, no `pipeline_state.json`; every written path checked to resolve
inside the tree), the applier with `ROOT` set to the tree (one line changed, checked), the wrapper with `APPLY_ROOT` /
`APPLIER`, and a fault injector:
* A: A10 check passed; A10 `--apply` sealed, newly cited manifest files = the eight A10 files, manifest unchanged
  (221 files); parsers without ALERT, `analyze_v4.py` first cited by A10, G8 `analysis_registration` without wait;
  A11 right after A10 (the phase baseline not refreshed; a stand-in review file in the tree): check passed, sealed,
  newly cited = the two R7B files; parsers: A10 and A11 read once, the R7B files first cited by A11, a later G3 entry
  of the phase driver read; the diff against the project PROTOCOL.md: Secs. 4.1, 9.4, 9.12 (Code, Freeze,
  Verification) and the two entries after G2; 438 added lines, no prose line over 120 columns (13 table rows, as in
  A3), none read as a driver entry, heading, second amendment title or column-0 list start.
* B: A11 before A10 stops at the pre-check (in-place text found 0 times); PROTOCOL.md unchanged.
* C: A11 without the review file stops at the pre-check (a placeholder without a value), before `--write-manifest`;
  nothing changed, the seal verifies.
* D: A10 through the wrapper (exit 0); a new file in the manifest scope and A11 killed right after
  `--write-manifest`: exit 137, the wrapper restored the sealed manifest, PROTOCOL.md unchanged, both seals verify;
  A11 again: sealed.
* E (M1): `commit_audit.py` (phase baseline only) and `p3_rl.py` (the G4 tool) changed, `arms_ext/tests/
  test_drift_guard.py` (phase baseline only) and `rl/RL_PROTOCOL.md` (P1 baseline) removed: each stops in check mode
  and in the wrapper before `--write-manifest`, nothing changed; with every file restored, A10 is sealed.
* F: F1 (S1) a new file in the manifest scope and A10 killed before `--seal`: exit 137, PROTOCOL.md holds A10, the
  wrapper kept the rewritten manifest (the one the entry names) and wrote "seal it now"; the hand seal under the lock
  verifies with the manifest the entry names. F2 (S2) a registered file changed after `--write-manifest`: exit 95.
* G: TZ=UTC: the applier alone stops; the wrapper called with TZ=UTC stamps Beijing time (S3); the temporary file and
  each driver's `protocol_txn.json` and `ALERT.txt`: wrapper exit 96 and check-mode STOP, nothing changed (S5, S6);
  template lines read as a G3 entry, an amendment title, a driver heading or holding the anchor phrase: check-mode
  STOP (S4); the restored template passes.

`rerun_review_sim.py` (08:57:33-09:07:04, 570 s, 229 MB): the review's harness `review/review_sim.py`, unchanged, on
the fixed applier and wrapper (its locations moved to `/tmp/AMEND3/a10r7b/rsim/` and `review_rerun/logs/`; its "fix"
hooks pointed at these files), with the expected result of each case after the fix checked: "ALL EXPECTED", 46
expectations (`review_rerun/logs/expectations.txt`). The cases that sealed a changed or removed registered file (D,
D3, V), a leftover temporary file (T) or a template line read as a G3 entry (H) now stop before `--write-manifest`;
G stamps Beijing time; E exits 95; F2 keeps the rewritten manifest and the hand seal is consistent; A, fix and fixAV
seal A10 with the eight files and A11 with the two R7B files; the test tree reproduces the counts (prop1 with the
tree artifact the review names, `Reproducible::test_reproduces_development_run`; 22 passed in the project).

`check_a11.py` simulates in memory on the current PROTOCOL.md (A10 first, then A11, then a later gate entry) with the
same results; `post_check.py` passed on the scratch trees (exit 3 where the scratch baseline is not refreshed).

## 5. Open issues for the coordinating session

1. A11 needs the review of the fixed R7B Part B (Sec. 3, precondition 2); the template states verdict GO. Its runs on
   real data enter "Development data" (Sec. 3, precondition 3).
2. Finding F1 (A11): `realized.py` (`GTTrack._bracket`, 1e-9 s) drops a plan sample that lands on the last row of the
   actor-box log (`actor_log.gt_rows` places rows at their frame times; the sample times carry the runtime's 3e-7 to
   1.1e-6 s offsets): 19 of 180 P1 runs differ in Sec. 6.3 counts, one in an EIR value the analysis reads
   (`fast_only`, route 1792). The final recomputation reports every such value as a difference. Decide before the
   analysis freeze: an amendment that corrects `realized.py` (registered, pinned by no job line; `actor_log.py` is
   pinned by every job line and stays), or a reporting rule for the affected values with this cause. F2 concerns
   decimated logs and in-flight commits only (no P1 log was decimated; the recomputation bounds the in-flight case).
3. `outputs/framelease_v4/paper_tools/apply_entry.py` (the generic applier, not edited here) keeps the defects that
   the review found here: whole-file reads (5.8 GB RSS), the P1 baseline only and no missing-file check (M1), no
   driver-form check of the template (S4), local time (S3), no temporary-file and phase-driver checks (S5, S6), and no
   copy of the sealed manifest. Apply A10 and A11 only through `apply_locked.sh` with `apply_entry_stream.py`; a later
   entry of the same form (APPLY_PLAN2 step 8) can use them with its own spec.
4. A10 deviation 1 must stay complete up to the application (Sec. 1, precondition 3), and A11 "Development data" up to
   its application (Sec. 3, precondition 3).

## 6. Files (sha256 at the end of item a10r7b, fix pass, 2026-11-15)

| sha256 | file |
|---|---|
| `9790c164405f432a813df39986b84853bd18ac078b5d4afff0ea51915ea324ca` | `outputs/framelease_v4/build/AMEND2/final/A10_entry.md` |
| `b1de9f6a976da98dc0da9da48fff5a1e2ec55512dfaac581ad7eb73a64335b0e` | `outputs/framelease_v4/build/AMEND2/final/A10_spec.json` |
| `03bfb7f44e89cbc4d88ac12ca96f7366c05188cfae22de58fccc8b9357861eac` | `outputs/framelease_v4/build/AMEND2/AMENDMENTS2_DRAFT.md` |
| `11b4ac48b23a3940c291bb24d0fcc4b441d88615e91f46c7b15a08b4a72b913e` | `outputs/framelease_v4/build/AMEND2/a10r7b/A11_entry.md` |
| `5fc36c01ba7e9bc4a91cca5bc881151f606a0fd19fac5ef5a94aa77ce6a7a682` | `outputs/framelease_v4/build/AMEND2/a10r7b/A11_spec.json` |
| `0f0cfda6d51f4924e82799631f1ac5a0a00f0f44d02c48b61c9fa07a9f0ac923` | `outputs/framelease_v4/build/AMEND2/a10r7b/apply_entry_stream.py` |
| `737a3e5c9a90cc95521863a72fa8cf929e91232a3768d06bbc7f836a7f40806b` | `outputs/framelease_v4/build/AMEND2/a10r7b/apply_entry_stream.diff` |
| `9c86ca20f259e0df6a0547e0b954a1d554eecd96d67a6aa9cd49a2bd2b00ddf8` | `outputs/framelease_v4/build/AMEND2/a10r7b/apply_locked.sh` |
| `4d0fff50e6484862bd2040ba2c54ea81d652834c761e48dcb3ac69d30fbaf106` | `outputs/framelease_v4/build/AMEND2/a10r7b/derive_inplace5.py` |
| `cbaf546ac65b92e5b8fa2bed861047b1b559ee408277544ad79e1c820a5ca05a` | `outputs/framelease_v4/build/AMEND2/a10r7b/make_a11_spec.py` |
| `63a420f4a8ba4da6d3ca2b8b71907b6a1aaa2ecdb947e03bc9ffaa125a336804` | `outputs/framelease_v4/build/AMEND2/a10r7b/check_a11.py` |
| `f2038c1f33c642e9cfb199ccdd029bbd1a1f613c01cc4afd5bba9f1036ba6213` | `outputs/framelease_v4/build/AMEND2/a10r7b/post_check.py` |
| `211a714b88f65963b2ee71a6e4ea3e762e43f0229768fbb6377fb211b9bcf606` | `outputs/framelease_v4/build/AMEND2/a10r7b/sim_tree.py` |
| `f3c08af4d34aee3e31c19c04621459bd6d872e532318441722b624dcb11ba44a` | `outputs/framelease_v4/build/AMEND2/a10r7b/rerun_review_sim.py` |
| `67c6955cefae786fa532afa17bc351fd565d82a3a8c8fa1408dad80f0815ac98` | `outputs/framelease_v4/build/AMEND2/a10r7b/edit_draft.py` |
| `78058f6e38a53f950771c90a2dae5232c03e4e49b6a8e3cc3b84eed24c9e50c5` | `outputs/framelease_v4/build/AMEND2/a10r7b/baseline_check.py` |
| `c72ed83ffd79b180968b824159e3ae4242d0803d19bdeb125bf114d4623ea22b` | `outputs/framelease_v4/build/AMEND2/a10r7b/evidence_sha256.txt` |
| `f5f11f8a3805df55d382fe3baff22928a494515a692ea4fd2bbd32eb1db812fa` | `outputs/framelease_v4/amendment_a10/pytest_analyze_v4.log` |
| `7ccb719fe1f603cc75385ce8b9495b57da9ad7cc1455d81a89df6b140fd77176` | `outputs/framelease_v4/amendment_a10/pytest_figures_tables.log` |
| `5283125b70b52b289e9817cb657095c6347f43b4347ba2184abf1c2bad1fb76a` | `outputs/framelease_v4/amendment_a10/pytest_prop1_coverage.log` |
| `cf768b093163bfca3def6ac61e834457b72a5c4e3e23a77d37133c236e4f8bab` | `outputs/framelease_v4/amendment_a10/pytest_verify_independent.log` |
| `0a6d4014f31a74c558436d22e94150874e8640f361105662b663cf0cb9c38965` | `outputs/framelease_v4/amendment_a11/pytest_review_r7b.log` |
| `cd8d75adc82840df9edec591cf38c8c598f42836f6ee6d88d123f25584959802` | `outputs/framelease_v4/amendment_a11/pytest_verify_table1_extra.log` |

Backups: `orig/` (before this item: A10_entry c51566ea..., A10_spec e92a5dce..., AMENDMENTS2_DRAFT f022b942...;
before the fix pass, `*.before_fix.*`, the reviewed versions). Drafting copies of the test logs: `logs/`. Dry-run
evidence: `sim_output/` (with the simulated PROTOCOL.md after A10 and A11 as `PROTOCOL.after_A10_A11.simulated.md.txt`;
never a source for the drivers) and `review_rerun/logs/`.
