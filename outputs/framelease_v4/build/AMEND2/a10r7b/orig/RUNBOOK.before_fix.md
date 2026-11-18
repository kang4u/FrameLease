# RUNBOOK: Amendment A10 (analysis code) and Amendment A11 (R7B recomputation of the other Table I columns)

For the coordinating session. Item a10r7b prepared both entries; nothing is applied by it. PROTOCOL.md, the
registration files, the seal, every registered file and the drivers' directories are unchanged by this item.

State at the end of this item (2026-11-15, Beijing time): step 3 of `APPLY_PLAN2.md` is sealed (06:40: A3, A9, A7b, A4
and the operational addition); `D1_DECISION.json` 06:42; the phase driver runs since 06:42:42 (G1 06:42, G2 06:43,
G3 running: 132 P2 jobs in `queue_p2`). A10 is applicable now (APPLY_PLAN2 Sec. 2, step 6: after step 3, recommended
before the test freeze G6, required before the analysis freeze G8). A11 follows A10 and needs the review of the fixed
R7B Part B first (Sec. 3 below); it is required before the analysis freeze (APPLY_PLAN2 step 7).

## 0. Conventions

Every command runs from `/home/kang/Desktop/DAC`, one at a time, after

```
cd /home/kang/Desktop/DAC
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
X="taskset -c 12-15 nice -n 19 ionice -c 3"
P="$X .conda-unidrive-linux/bin/python -I -B"
A=outputs/framelease_v4/build/AMEND2
```

Memory. `outputs/framelease_v4/paper_tools/apply_entry.py` hashes with `Path.read_bytes()`; its pre-check (check mode
and `--apply`) hashes every registered file of the sealed manifest, among them the 5.9 GB checkpoint
`checkpoints/UniDriveVLA/.../UniDriveVLA_Stage3_Bench2drive_2B.pt`: max RSS 5.8 GB (measured 2026-11-15 07:04). A P2-P6
job holds up to 23 GB of 30 GB. Check mode and `--apply` therefore use `$A/a10r7b/apply_entry_stream.py`, the same
script with only `sha()` streaming in 1 MiB blocks (diff below; max RSS 18 MB, same result). The `--tests` mode hashes
nothing and is the same in both scripts.

```
36,37c36,41 (apply_entry.py -> apply_entry_stream.py)
<     return hashlib.sha256(Path(p).read_bytes()).hexdigest()
>     h = hashlib.sha256()                    # streamed in 1 MiB blocks (a registered checkpoint has 5.9 GB)
>     with open(p, 'rb') as fh:
>         for block in iter(lambda: fh.read(1 << 20), b''):
>             h.update(block)
>     return h.hexdigest()
```

Manifest backup. `apply_entry.py` rewrites `MANIFEST.sha256` (`registration.py --write-manifest --force`) before it
fills and inserts the entry, and keeps no copy. A STOP after that step leaves the rewritten manifest; when a file of
the manifest scope changed since the last seal (for example a reviewed fix of `verify_table1_extra.py`), the seal no
longer verifies and the phase driver raises an ALERT at its next cycle. Each application below therefore runs through
`$A/a10r7b/apply_locked.sh SPEC OUTDIR`: inside one hold of `framelease_v4/.protocol.lock` (600 s wait) it copies the
sealed manifest to `OUTDIR/MANIFEST.sealed.before_apply`, runs `apply_entry_stream.py SPEC --apply` into
`OUTDIR/apply.out`, puts the sealed manifest back when the applier failed after `--write-manifest` and before `--seal`
and the rewritten manifest differs, and appends `registration.py --verify`. Its exit code is the applier's (0 sealed,
1 STOP; 97 lock not obtained, 98 backup failed).

## 1. Amendment A10 (`$A/final/A10_entry.md`, `$A/final/A10_spec.json`)

Preconditions, in this order (all read only):

1. Seal and drivers.
   ```
   $P framelease_v4/protocol/registration.py --verify      # "manifest: OK" and both "seal ...: OK" lines
   ls outputs/framelease_v4/phase_driver/{ALERT.txt,protocol_txn.json}  # both: "No such file or directory"
   ls outputs/framelease_v4/p1_driver/{ALERT.txt,protocol_txn.json}     # both: "No such file or directory"
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
   `verify_independent.py` on real data from 2026-11-14 to the application (all on 2026-11-14 at drafting). The test
   runs are covered by the sentences on the tests. List the PROGRESS files changed after this item and search them:
   ```
   find outputs/framelease_v4/build -name PROGRESS.md -newer $A/a10r7b/PROGRESS.md
   grep -n -E 'aggregate_v4|commit_audit|analyze_v4|prop1_coverage|figures_tables|verify_independent' <each file>
   ```
   A further execution on real data (outside a test run): add it to deviation 1 with its time and output directory
   (and change "(all on 2026-11-14)"), copy the template into `$A/AMENDMENTS2_DRAFT.md` (it must hold the template
   verbatim: replace the old block, or adapt `$A/a10r7b/edit_draft.py`), and rerun `check_drafts.py`.
4. Tests (no lock; 75 s, 230 MB; logs of 2026-11-15 07:00 exist and pass: rerun when an A10 file or a module it
   imports changed):
   ```
   $P outputs/framelease_v4/paper_tools/apply_entry.py $A/final/A10_spec.json --tests
   ```
   Expected: `pytest_analyze_v4.log` 48 passed, 107 subtests; `pytest_prop1_coverage.log` 22 passed;
   `pytest_figures_tables.log` 50 passed, 422 warnings; `pytest_verify_independent.log` 28 passed, 20 subtests; every
   line "exit 0". Keep `build/STRESS/s3_dev_report_v2.json` and `build/R5/dev_run/` (two tests read them).
5. Check mode (no lock):
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
`verify_independent.py` and their four tests), the filled entry, and the appended verification (both seals OK).

`apply_locked: exit 1` with a line `STOP: ...` in `apply.out`:
* before `registration --write-manifest` (seal, registered files, driver files, must_equal, test log, entry exists,
  in-place text count, anchor, template): nothing changed; resolve the named cause.
* after it (`registered files changed in the new manifest`, `unfilled placeholder`, `the entry cites the sha256 of
  unregistered manifest files`, `PROTOCOL.md changed during the transaction`) or a traceback: PROTOCOL.md is
  unchanged, and `apply.out` ends with "RESTORED the sealed manifest" or "the rewritten manifest equals the sealed
  one" and the verification (both seals OK); resolve the cause.
* `seal failed: PROTOCOL.md holds the entry but is not sealed` (the wrapper restores nothing then): seal by hand at
  once, `flock -w 600 framelease_v4/.protocol.lock $P framelease_v4/protocol/registration.py --seal`, then `--verify`.

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
  and console logs of R4, R5, R6, R7, AGG (AGG0) and R7B and the review records; the draft listed five `analyze_v4.py`
  command-line runs on `smoke_D`, there were six (08:16, R4 step 70, console `smoke_train_partB.log`). FILL0 and its
  review ran `figures_tables.py` on synthetic inputs only (not listed).
* Evidence: the output manifests of `build/AGG/step0_reaudit/`, `build/R7B/dev/agg_now/` and `agg_snap_2203/`.
* Spec: the fifth in-place text, derived from the sealed PROTOCOL.md (below); nothing else. must_equal is unchanged:
  the eight A10 files and the three reused coverage files are at their drafting sha256 (APPLY_PLAN2 step 1 was not
  done; "Known limitations" stands).
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

1. `$P $A/a10r7b/post_check.py A10` exits 0.
2. The review of the fixed R7B Part B (R7B review: "the fixed Part B needs a re-review of its changes before the R7B
   amendment"): continuous V, lease footprint, decoder, guard (`build/R7B/PROGRESS.md`, attempt 5). The template names
   it `outputs/framelease_v4/build/R7B/rereview/REVIEW.md` with verdict GO (file table and Evidence).
   * Written elsewhere: replace that path in `A11_entry.md` (two places) and `REREVIEW` in `check_a11.py`.
   * Verdict GO_WITH_FIXES: the fixes are applied and reviewed; set the new sha256 in `make_a11_spec.py` (MUST_EQUAL)
     and rerun it; rerun the P1 development comparison when the recomputation changed and update the "Development
     comparison" bullet; update the review cell, the counts "At drafting" and the evidence list.
3. Spec, tests, checks:
   ```
   $P $A/a10r7b/make_a11_spec.py --check                            # "equal to the generated spec", exit 0
   $P outputs/framelease_v4/paper_tools/apply_entry.py $A/a10r7b/A11_spec.json --tests
                                                                     # 71 passed, 67 subtests; 14 passed, 2 subtests
   $P $A/a10r7b/check_a11.py                                        # exit 0, "all checks passed"
   $X sha256sum -c --quiet $A/a10r7b/evidence_sha256.txt            # no output, exit 0
   ```
   `check_a11.py` exit 2 lists what is open (A10 not entered, the review file missing or not GO, a test log missing or
   failing); exit 1 lists problems (placeholders, widths, parser collisions, spec, the count of newly cited manifest
   files, the simulation). Never apply A11 on exit 1 or 2: a placeholder that names a missing file stops
   `apply_entry` after `--write-manifest` (dry-run case C).
4. Seal and drivers as in Sec. 1, precondition 1.
5. Check mode: `$P $A/a10r7b/apply_entry_stream.py $A/a10r7b/A11_spec.json` -> "check: pre-checks passed".

Application and post-check:

```
bash $A/a10r7b/apply_locked.sh $A/a10r7b/A11_spec.json outputs/framelease_v4/amendment_a11
$P $A/a10r7b/post_check.py A11                     # exit 3, then 0 after the phase driver's next cycle
```

Expected: `apply_locked: exit 0`; `apply.out` shows `newly cited manifest files:
['framelease_v4/analysis/tests/test_verify_table1_extra.py', 'framelease_v4/analysis/verify_table1_extra.py']`
(`max_new_registered` 2). A STOP: as in Sec. 1. Update `framelease_v4/PIPELINE_STATE.md`.

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

## 4. Dry run (sim_tree.py, 2026-11-15 07:27-07:30, final texts; evidence in `sim_output/`)

Scratch trees under `/tmp/AMEND3/a10r7b/sim_tree/` (real copies of `framelease_v4/`, `registration/`, `p1_driver/`,
`amendment_a10/`, `amendment_a11/`, `build/AMEND2/` without `step3/`, a real `build/R7B/` of links; links for the rest;
no queue, no `pipeline_state.json`, no `phase_driver/`; every written path checked to resolve inside the tree), the
applier `apply_entry_stream.py` with `ROOT` set to the tree (one line changed, checked):
* A: A10 check passed; A10 `--apply` sealed, newly cited manifest files = the eight A10 files, manifest unchanged
  (221 files); parsers without ALERT, `analyze_v4.py` first cited by A10, G8 `analysis_registration` without wait;
  A11 (with a stand-in review file in the tree) check passed, `--apply` sealed, newly cited = the two R7B files;
  parsers: A10 and A11 read once, the R7B files first cited by A11, a later G3 entry of the phase driver read; diff
  against the project PROTOCOL.md: Secs. 4.1, 9.4, 9.12 (Code, Freeze, Verification) and the two entries after G2,
  no added prose line over 120 columns.
* B: A11 before A10 stops at the pre-check (in-place text found 0 times); PROTOCOL.md unchanged.
* C: A11 without the review file: `FileNotFoundError` in the fill after `--write-manifest`; PROTOCOL.md unchanged; the
  rewritten manifest identical (no file of its scope changed), so the seal held. With a changed file it would not.
* D: `apply_locked.sh` (APPLY_ROOT and APPLIER set to the tree): A10 sealed through it; then a new file in the
  manifest scope and A11 without the review file: the applier failed after `--write-manifest` (222 files), the wrapper
  restored the sealed manifest, both seals verify, PROTOCOL.md unchanged.

`check_a11.py` simulates in memory on the current PROTOCOL.md (A10 first, then A11, then a later gate entry) with the
same results; `post_check.py` passed on the scratch trees (exit 3: the scratch baseline is the real one, not refreshed).

## 5. Open issues for the coordinating session

1. A11 needs the review of the fixed R7B Part B (Sec. 3, precondition 2); the template states verdict GO.
2. Finding F1 (A11): `realized.py` (`GTTrack._bracket`, 1e-9 s) drops a plan sample that lands on the last row of the
   actor-box log (`actor_log.gt_rows` places rows at their frame times; the sample times carry the runtime's 3e-7 to
   1.1e-6 s offsets): 19 of 180 P1 runs differ in Sec. 6.3 counts, one in an EIR value the analysis reads
   (`fast_only`, route 1792). The final recomputation reports every such value as a difference. Decide before the
   analysis freeze: an amendment that corrects `realized.py` (registered, pinned by no job line; `actor_log.py` is
   pinned by every job line and stays), or a reporting rule for the affected values with this cause. F2 concerns
   decimated logs and in-flight commits only (no P1 log was decimated; the recomputation bounds the in-flight case).
3. `apply_entry.py` reads the 5.9 GB checkpoint whole (5.8 GB RSS): use `apply_entry_stream.py` for check and apply
   while closed-loop jobs run.
4. `apply_entry.py` keeps no copy of the sealed manifest: apply through `apply_locked.sh` (Sec. 0).
5. A10 deviation 1 must stay complete up to the application (Sec. 1, precondition 3).

## 6. Files (sha256 at the end of item a10r7b, 2026-11-15 07:31)

| sha256 | file |
|---|---|
| `72b6d1d915b6fedac491692b1ffc74d4fb5de13641dfe7ba5620b2308dad3790` | `outputs/framelease_v4/build/AMEND2/final/A10_entry.md` |
| `b1de9f6a976da98dc0da9da48fff5a1e2ec55512dfaac581ad7eb73a64335b0e` | `outputs/framelease_v4/build/AMEND2/final/A10_spec.json` |
| `6d9a0ced76c96c9f9731c665f13d7811c4c249bae8c1420cac51c8213a51fe81` | `outputs/framelease_v4/build/AMEND2/AMENDMENTS2_DRAFT.md` |
| `6a8bb75ec65a2e37088ee5976a8cad0f9db8a8ce16af6cc917adbba2b9ce987f` | `outputs/framelease_v4/build/AMEND2/a10r7b/A11_entry.md` |
| `5fc36c01ba7e9bc4a91cca5bc881151f606a0fd19fac5ef5a94aa77ce6a7a682` | `outputs/framelease_v4/build/AMEND2/a10r7b/A11_spec.json` |
| `4d0fff50e6484862bd2040ba2c54ea81d652834c761e48dcb3ac69d30fbaf106` | `outputs/framelease_v4/build/AMEND2/a10r7b/derive_inplace5.py` |
| `cbaf546ac65b92e5b8fa2bed861047b1b559ee408277544ad79e1c820a5ca05a` | `outputs/framelease_v4/build/AMEND2/a10r7b/make_a11_spec.py` |
| `e2da1e856cb1b246f65c14a38bfda7f6fd3c99fbf9a05b849f7b5a7f44587e95` | `outputs/framelease_v4/build/AMEND2/a10r7b/check_a11.py` |
| `c92bce2558c020400062436d44e63539327484c3f61f71510bf5309381167b60` | `outputs/framelease_v4/build/AMEND2/a10r7b/post_check.py` |
| `31e9bab339c2f094913aabec675562ebd9e0a0060ab38a308ca5bcf79060744d` | `outputs/framelease_v4/build/AMEND2/a10r7b/apply_entry_stream.py` |
| `73b49d8ece76e2935532c852b61dc98d8b1eaebc4dd2bb0e78ea8a683b2ebe2a` | `outputs/framelease_v4/build/AMEND2/a10r7b/apply_locked.sh` |
| `3b8f1e3733e2effbe1010709679684c60984a8c89b33aa742d2b6012c3817a75` | `outputs/framelease_v4/build/AMEND2/a10r7b/sim_tree.py` |
| `3e88577bbd5b4dd3acbfdf1130d61ad8ca538568b671cc533fa62e17202f5045` | `outputs/framelease_v4/build/AMEND2/a10r7b/edit_draft.py` |
| `78058f6e38a53f950771c90a2dae5232c03e4e49b6a8e3cc3b84eed24c9e50c5` | `outputs/framelease_v4/build/AMEND2/a10r7b/baseline_check.py` |
| `c72ed83ffd79b180968b824159e3ae4242d0803d19bdeb125bf114d4623ea22b` | `outputs/framelease_v4/build/AMEND2/a10r7b/evidence_sha256.txt` |
| `5b3486abb90e45c35606d92b0e4549f0774d3ff08fe55cb7ae23d84f49d9f117` | `outputs/framelease_v4/amendment_a10/pytest_analyze_v4.log` |
| `49a6851dfe1f9c9042393569820d204f46885f2392927c7f651fc9975786daf6` | `outputs/framelease_v4/amendment_a10/pytest_figures_tables.log` |
| `02231b6d7dc4eac4c6692c623f899249cf48413d89ec9a859e50d8b5543baecd` | `outputs/framelease_v4/amendment_a10/pytest_prop1_coverage.log` |
| `f5613b647595d77f7f488f17f9080f9b91536967715844ff538cc7b15389f986` | `outputs/framelease_v4/amendment_a10/pytest_verify_independent.log` |
| `1cad937711cfdbdebc999e44800a45afcbe600b78568a293f510a957280b6225` | `outputs/framelease_v4/amendment_a11/pytest_review_r7b.log` |
| `7b3b4d9dd0f79bfa69e22da560626a12bcd04943a9eb0e87a98b50d75822e6f8` | `outputs/framelease_v4/amendment_a11/pytest_verify_table1_extra.log` |

Backups of the files before this item: `orig/` (A10_entry c51566ea..., A10_spec e92a5dce..., AMENDMENTS2_DRAFT
f022b942...). Drafting copies of the test logs: `logs/`. Dry-run evidence: `sim_output/` (with the simulated
PROTOCOL.md after A10 and A11 as `PROTOCOL.after_A10_A11.simulated.md.txt`; never a source for the drivers).
