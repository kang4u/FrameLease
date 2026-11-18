# Apply plan of the AMEND2 entries and the order of every remaining Sec. 13.2 entry

For the coordinating session. The entry texts are `final/OP_phase_driver_entry.md` (operational addition: the phase
driver) and `final/A10_entry.md` (Amendment A10: registration of the analysis code), copied verbatim into
`AMENDMENTS2_DRAFT.md`. Nothing of this item is applied: PROTOCOL.md, the registration manifest and the seal are
unchanged by it. `APPLY_PLAN.md` of item AMEND (the package A3-A9) stays valid except where this plan changes it (the
edits E1-E4 of Sec. 3, step 0, and the A3 analysis test log); this plan adds the two entries, updates the status of
that package and fixes the order of everything still to be entered. Revised after the review `review/REVIEW.md`
(GO_WITH_FIXES; must-fix M1-M4 and should-fix 1-12 applied).

Every command of this plan runs as `taskset -c 12-15 nice -n 19 ionice -c 3 <command>` with
`OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1` and `CUDA_VISIBLE_DEVICES=''` (after `source linux/env.sh`
where a tool needs it), one at a time, from `/home/kang/Desktop/DAC`. `$P` below stands for
`taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B`. The only exception is the start of
the phase driver (step 5).

## 1. State at drafting (2026-11-14, 13:10 Beijing time; revised 2026-11-14 after the review)

* Sec. 13.2 holds A1, A2, the operational additions of 2026-11-11, A6 (with the fix), A5, A8 and the P1 stage
  driver's selections `lease_s1`, `event_s1` and `lease_s2` (12:57; selected L* candidate `B0`). P1 runs.
* Decisions of the user (`framelease_v4/PIPELINE_STATE.md`, 2026-11-14 03:48): A6 with the fix (applied), A7 = A7b,
  A4 approved as drafted. 04:00: the instruction that delegates the phase gates, D1 included, to the coordinating
  session (quoted in translation by the operational addition and by the phase driver's G1 entry).
* `APPLY_PLAN.md` Sec. 2: steps 1 (idle band), 2 (A8), 3 (A5), 4 (A6), 5 (`p3_rl.py` adapted to A6), 6 (aggregator
  reads the P4-P6 block specs) and 7 (`stress_bench.py s2 --grid relative`, A7b;
  `outputs/framelease_v4/amendment_a7/pytest_stress_bench.log`) are done. Open: A3 + A9 + A7b, A4.
* The phase driver (`framelease_v4/protocol/phase_driver.py` 2bf4147c..., `start_phase_driver.sh` 5c70674f...,
  `tests/test_phase_driver.py` b4e5bc44...) and the four analysis files of A10 are at their reviewed and fixed versions
  (appendix of `AMENDMENTS2_DRAFT.md`; `sha256_at_drafting.txt`). None of them is registered: the P1 stage driver's
  seals list them in the manifest as unregistered files.
* `check_drafts.py` exits 2 at drafting: the checks pass, and five preconditions are open (step 0 and the edits E1-E4
  of Sec. 3, step 0). Application needs exit 0, "all checks passed".

## 2. Order and deadlines

| step | entry or work | preconditions | apply when | latest |
|---:|---|---|---|---|
| 0 | (no entry) the commit-audit rule for null margins of `horizon_cap` leases in `framelease_v4/analysis/commit_audit.py` and `tests/test_commit_audit.py` (AGG item, then review), the rule of Sec. 5, item 1; with the change: edit E3 of the A3 draft (Sec. 3, step 0), the two sha256 in `build/AMEND/a3_sha256_at_drafting.txt` and the review record of the change (`APPLY_PLAN.md` Sec. 4: a changed A3 file carries the review of its change); optionally the `km_driven` floor of `runs.csv` (Sec. 6.1) in `aggregate_v4.py` | none | now, while P1 runs (both files are unregistered) | before A3 (step 3) |
| 1 | (no entry, optional) R5 should-fix S1, S2, S5 in `prop1_coverage.py`; the comparison of the rendered Table I with `numbers.json` in `verify_independent.py` | none | now | before A10 (step 6); each change reviewed, then `final/A10_spec.json` "must_equal", the A10 "Known limitations" and the test counts updated |
| 2 | P1 ends | the P1 stage driver's "Tuning freeze" and "D1 summary" entries; `outputs/framelease_v4/p1_driver/P1_DONE.json`; the P1 stage driver has exited | by the P1 stage driver | - |
| 3 | one transaction: A3, A9, A7 (A7b), A4, the operational addition (in this order; one manifest, one seal) | step 0 done; the edits E1-E4 made (Sec. 3, step 0); every A3 file at its reviewed version (`build/AMEND/APPLY_PLAN.md` Sec. 4); the A3 and OP test logs (Sec. 3, step 2); `check_drafts.py` exit 0 | after step 2, before the D1 decision is written | before the phase driver starts (step 5) |
| 4 | (no Sec. 13.2 entry by the session) the D1 decision: `outputs/framelease_v4/phase_driver/D1_DECISION.json` | step 3; the D1 summary read | after step 3 | before G1 can pass; the driver records it as "G1 D1 decision" |
| 5 | (no entry) start the phase driver | steps 3-4; `phase_driver.py --dry-run` shows G0 passed | after step 4 (or after step 3: G1 then waits for the decision file) | - |
| 6 | A10 (`apply_entry.py final/A10_spec.json`) | A3 sealed; step 0 done; step 1 done or accepted as recorded; A10 finding 1 and deviation 1 checked, in-place texts 2 and 5 confirmed (Sec. 4, step 1) | after step 3; recommended before the test freeze (G6), so that the analysis code is registered before any test-route run exists | before the analysis freeze: G8 waits for it |
| 7 | item R7B (required): the independent recomputation of the Table I columns GPU usage, DMR, action age p50 / p95, fallback ratio, EIR and P_both and of the closed-loop R_cond of the notes (Secs. 7.2, 9.13; A10 deviation 9), registered by its own amendment | built by an independent session (Sec. 9.12) from the run directories (Secs. 6.2-6.4, including the realized validity of the actor boxes behind EIR, R_cond and P_both), during P4-P6, on training-route runs and synthetic data only (Sec. 9.11); reviewed | during P4-P6, after A10 | before the analysis freeze; the phase driver's G8 does not wait for this amendment (Sec. 5, item 3) |
| 8 | (later entries) the verification after G8: `verify_independent.py` (A10 use rule 4) and the R7B recomputation, each run by an independent session; the sha256 of `verification.json` and of the R7B result, each in its own dated entry | G8 passed (the analysis-freeze record entered) and the analysis run | after the analysis | before any of these numbers enters the paper; both before the paper is written |

Why the operational addition goes with A3 and after P1: once a file is registered, the P1 stage driver treats it as
registered (`p1_driver.refresh_baseline` adds a manifest file whose full sha256 PROTOCOL.md cites) and stops P1 with
an ALERT at any later change of it; registered after P1, the phase driver's files stay free to change until then.
G0 of the phase driver waits for A3, A4, A7 and A9, so all four and the operational addition go into the one
transaction that follows P1. If that transaction is split, the operational addition is entered right after A3 (and
A4), still before step 5. `APPLY_PLAN.md` (row 9) allows A4 "during P2 or P3"; the phase driver's G0 requires it
before P2, so A4 joins step 3 (its precondition, A3 applied, holds inside the same transaction).

Why A10 before the test freeze: the tools that the generator and the analysis read (the RL freeze, the stress reports,
the D1 summary) exist by then in their production form, and no test-route run exists yet. A change after A10 is an
amendment that installs the new file under the lock (the phase driver stops with an ALERT at a registered file that
changes outside a transaction); it remains possible until the analysis freeze.

Why R7B is required: Sec. 7.2 lists these columns in Table I and Sec. 9.13 puts every registered result in the paper
or its supplement; A10 (deviation 9 and the Sec. 9.12 in-place text) admits them only after an independent
recomputation entered in Sec. 13. `verify_independent.py` recomputes DS, SR, RC, collisions/km and infractions/km
only.

## 3. Transaction of step 3 (manual; `apply_entry.py` applies one "**Amendment <name>,**" entry)

0. Edits of the AMEND drafts, before the tests of step 2 (each logged in `build/AMEND/PROGRESS.md`; the drafts are
   files of item AMEND, not of this item). Old texts as they read in `build/AMEND/AMENDMENTS_DRAFT.md` (line breaks
   aside); `check_drafts.py` lists each one still present as OPEN.
   * E1, A9, the list header. Old: "What was run (every execution on real data, 2026-11-11)." New: "What was run
     (every execution on real data up to the drafting of this entry, 2026-11-11; the read-only executions from
     2026-11-14 on are recorded in Amendment A10)." A10 deviation 1 ("a development aggregation in addition to those
     of Amendment A9") matches this header.
   * E2, A9, the rule. Old: "`analyze_v4.py` (R-4) is written and tested on synthetic CSVs only, as Sec. 9.12
     states." New: "`analyze_v4.py` (R-4) runs during development on synthetic CSVs and, read-only, on training-route
     aggregations only (its runs of 2026-11-14 on `outputs/framelease_v4/build/AGG/smoke_D`: Amendment A10)."
   * E3, A3 item 6, made with the change of step 0. Old: "A null commit margin passes only where the validity record
     names no relevant agent;". New: "A null commit margin passes where the validity record names no relevant agent,
     or has reason `horizon_cap` and n_computed 0 (the lease prefilter showed g > delta for every relevant agent, so
     M = +inf); any other null margin with a relevant agent is a violation;". If step 0 settles a different rule,
     E3 and A10 finding 1 state that rule instead, in the same words.
   * E4, A3, the analysis test log (it no longer runs the whole directory `framelease_v4/analysis/tests`, which also
     holds the four A10 test files). Old: "* `framelease_v4/analysis/tests` and
     `framelease_v4/arms/tests/test_metrics_realized_keys.py`:". New: "* the aggregator tests
     `framelease_v4/analysis/tests/test_aggregate_v4.py`, `test_commit_audit.py`, `test_extra_metrics.py`,
     `test_interim_guard.py` and `test_manipulation.py`, and `framelease_v4/arms/tests/test_metrics_realized_keys.py`
     (the A10 test files have their own logs, Amendment A10):". The log command of step 2 follows it.

   The edited lines keep the constraints of `build/AMEND/AMENDMENTS_DRAFT.md` (filled prose lines at most 120
   columns; no line that a driver reads as an entry or a heading).
1. Pre-check (no lock).
   * `$P framelease_v4/protocol/registration.py --verify`: both seal lines OK.
   * `outputs/framelease_v4/p1_driver/P1_DONE.json` exists; no `p1_driver.py` process is alive; neither
     `p1_driver/protocol_txn.json` nor `p1_driver/ALERT.txt` exists.
   * The four files of `final/OP_spec.json` "must_equal" have those sha256 (else: the change carries its review, and
     the spec is updated).
   * `$P outputs/framelease_v4/build/AMEND2/check_drafts.py`: exit 0, "all checks passed" (exit 2 lists the open
     preconditions: step 0 and E1-E4).
2. Tests (no lock). The A3 logs as `build/AMEND/APPLY_PLAN.md` Sec. 4 lists them, except the analysis log, which runs
   the files of E4:
   ```
   PYT="taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider"
   $PYT framelease_v4/analysis/tests/test_{aggregate_v4,commit_audit,extra_metrics,interim_guard,manipulation}.py \
       framelease_v4/arms/tests/test_metrics_realized_keys.py \
       > outputs/framelease_v4/amendment_a3/pytest_analysis.log 2>&1
   ```
   For the operational addition:
   ```
   $P outputs/framelease_v4/paper_tools/apply_entry.py outputs/framelease_v4/build/AMEND2/final/OP_spec.json --tests
   ```
   It writes `outputs/framelease_v4/operational_phase_driver/pytest_phase_driver.log` (at drafting: 24 passed in
   163 s, 50 MB) and `pytest_review_phase.log` (6 passed in 67 s); both must end with no failure. `--check` and
   `--apply` of this spec stop at the template check by design. `test_phase_driver.py` reads the development input
   `build/AMEND/AMENDMENTS_DRAFT.md` (after E1-E4) and skips that test when the file is absent: keep it until the log
   is written.
3. Under the lock: `flock -w 600 framelease_v4/.protocol.lock taskset -c 12-15 nice -n 19 ionice -c 3 bash
   /tmp/amend_step3.sh`, the script exporting the one-thread BLAS environment and `CUDA_VISIBLE_DEVICES=''` and
   running the steps below with `$P`:
   1. Copy `outputs/framelease_v4/registration/MANIFEST.sha256` to a scratch file (the sealed manifest);
      `registration.py --write-manifest --force`; note the file count and the sha256.
   2. Post-manifest check, before anything is inserted (the property that departure 3 of the operational addition
      states; `apply_entry.py` and both drivers check it at this point): every file of
      `p1_driver/registered_baseline.json` entered the new manifest at its sealed sha256 and none vanished:
      ```
      $P -c "import json; b=json.load(open('outputs/framelease_v4/p1_driver/registered_baseline.json'))['files']; m=dict(reversed(l.rstrip('\n').split('  ',1)) for l in open('outputs/framelease_v4/registration/MANIFEST.sha256')); print([k for k,v in b.items() if m.get(k)!=v] or 'OK')"
      ```
      Anything but `OK`: stop. Insert nothing, restore the sealed manifest from the scratch copy (`--verify` OK
      again), and resolve the cause first.
   3. Fill each entry with one time stamp, e.g. for the operational addition
      ```
      $P outputs/framelease_v4/build/AMEND2/fill_entry.py \
          outputs/framelease_v4/build/AMEND2/final/OP_phase_driver_entry.md --datetime '<YYYY-MM-DD HH:MM>' > /tmp/op.md
      ```
      (exit 0; it refuses an unfilled placeholder, a failing test log and the anchor phrase, and lists the three
      `framelease_v4` files it cites). A3, A9, A7b and A4 are filled by the rules of `build/AMEND/AMENDMENTS_DRAFT.md`,
      A3 and A9 after the edits E1-E4.
   4. Insert the five entries, in the order of step 3, each as its own paragraph block with blank lines around it,
      directly before the paragraph that starts "Each amendment gets the date and time" (after the P1 stage driver's
      block); apply the in-place texts of A3, A9 and A7b (the operational addition has none).
   5. `registration.py --seal`; `registration.py --verify` (both seals OK, `manifest: OK`).
4. Post-check.
   * The command of step 3.2 again, on the sealed manifest: `OK`.
   * `$P framelease_v4/protocol/phase_driver.py --dry-run` (writes nothing): G0 passed (P1_DONE, "Tuning freeze",
     "D1 summary", A3, A4, A7, A9, seal OK); G1 waits for `D1_DECISION.json`; the G5 plan includes
     `s2 --grid relative` (A7b read from the A7 text).
   * `$P outputs/framelease_v4/build/AMEND2/check_drafts.py` on the new PROTOCOL.md: its simulation (operational
     addition already present: see Sec. 6) and the in-place counts of A10 (Sec. 4, step 1).
   * Update `framelease_v4/PIPELINE_STATE.md`.

Step 4, the D1 decision: write `outputs/framelease_v4/phase_driver/D1_DECISION.json` as a temporary file in the same
directory, then `mv` (the driver reads a partial file again for 120 s, then raises an ALERT):
`{"schema": "framelease_v4.d1_decision/1", "decision": "continue" | "stop", "rationale": "<the reasons, from the D1
summary>", "d1_summary_sha256": "<sha256 of outputs/framelease_v4/tuning/d1/FULL_d1_summary.json>", "decided":
"<ISO time>", "by": "coordinating session"}`. The sha256 must be the file's and the one the P1 driver's "D1 summary"
entry cites.

Step 5, the start: from a shell at nice 0 WITHOUT CPU pinning (the prefix of this plan does not apply here; the script
and the driver refuse a niced or pinned start because the runners inherit it):
`bash framelease_v4/protocol/start_phase_driver.sh`, with no option: never the test options `--allow-nice-launch` or
`--normal-priority` (the operational addition, "Launch in an isolated scope"). It prints the pid, the scope
`framelease-phase-driver-<ts>` and the log paths; `outputs/framelease_v4/phase_driver/driver.log` and `state.json`
follow every cycle.

## 4. Step 6, Amendment A10

1. Pre-check (no lock).
   * A3 is sealed (the five aggregator modules and `__init__.py` cited); step 0 is done.
   * A10 finding 1 states the rule that the A3-sealed `commit_audit.py` implements (its docstring and the
     `horizon_cap` test of `tests/test_commit_audit.py`), in the words of E3; otherwise rewrite the rule sentence of
     finding 1 to that rule before the check (and set its review).
   * A10 deviation 1 lists every execution of the aggregator and of the four A10 files on real data from 2026-11-14 on
     up to the application, with its time and output directory (from the PROGRESS files of the items that ran them,
     e.g. a re-audit of `build/R7/dev/agg_p1` at step 0); otherwise extend it. A9 (edit E1) refers to this list.
   * `final/A10_spec.json` "must_equal": the eight files at their drafting sha256, and the three files the coverage
     reuses outside the manifest (`framelease_v3/envelopes.py`, `framelease_v2/calibration.py`,
     `framelease_v3/suffix_lease_eval.py`, cited under "Evidence"; `check_drafts.py` compares them with gate2's
     `config.json`). A file changed by step 1 carries its review; then set its sha256 in the spec and update the entry
     text of A10 that the change affects ("Known limitations", deviation 9 or 12, the test counts "At drafting").
   * The second in-place text (Sec. 9.12, the end of "**Code.**" and the new paragraph before "**Freeze.**"): its
     "old" starts at the last word of the "**Code.**" paragraph, "freeze.", which A9's in-place sentence does not
     move; `check_drafts.py` on the PROTOCOL.md after A9 shows it once and no produced line over 120 columns (else set
     the line break of its "new" in the spec).
   * The fifth in-place text (Sec. 4.1, the status sentence that A3 inserts): open PROTOCOL.md after A3, copy the
     exact text of the clause "the analysis script, the Proposition-1 coverage and the figure and table generators
     remain required before the analysis freeze" with its line breaks and indentation into "old", and the same text
     with "remain required before the analysis freeze" replaced by "are registered by Amendment A10" (rewrapped at 120
     columns, same indentation) into "new". A3's own entry quotes the same clause in its "In-place text" bullet,
     wrapped and indented differently: "old" is the Sec. 4.1 text, never that quotation. `apply_entry.py` stops when
     an "old" text does not occur exactly once. The other three in-place texts (Sec. 9.4; Sec. 9.12 "**Freeze.**" and
     "**Verification.**") occur once in the current PROTOCOL.md and are not touched by A3, A9 or A7.
   * While the phase driver runs: no `outputs/framelease_v4/phase_driver/ALERT.txt` and no
     `phase_driver/protocol_txn.json`; every file of `phase_driver/registered_baseline.json` equals the sealed manifest
     (the command of Sec. 3, step 3.2, with that path). `apply_entry.py` checks the P1 stage driver's baseline only.
   * `$P outputs/framelease_v4/build/AMEND2/check_drafts.py`: exit 0, "all checks passed".
2. Tests (no lock; `apply_entry.py` runs each test file on the E-cores at nice 19):
   ```
   $P outputs/framelease_v4/paper_tools/apply_entry.py outputs/framelease_v4/build/AMEND2/final/A10_spec.json --tests
   ```
   Logs in `outputs/framelease_v4/amendment_a10/`. At drafting: `test_analyze_v4.py` 48 passed, 107 subtests (26 s);
   `test_prop1_coverage.py` 22 passed (20 s); `test_figures_tables.py` 50 passed (23 s); `test_verify_independent.py`
   28 passed, 20 subtests (14 s). Two tests read development outputs and are skipped when these are removed:
   `build/STRESS/s3_dev_report_v2.json` (test_analyze_v4) and `build/R5/dev_run/` (test_prop1_coverage); keep them
   until the logs are written.
3. Check mode: `$P outputs/framelease_v4/paper_tools/apply_entry.py
   outputs/framelease_v4/build/AMEND2/final/A10_spec.json`: "check: pre-checks passed".
4. Under the lock:
   ```
   OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' \
   flock -w 600 framelease_v4/.protocol.lock taskset -c 12-15 nice -n 19 ionice -c 3 \
       .conda-unidrive-linux/bin/python -I -B outputs/framelease_v4/paper_tools/apply_entry.py \
       outputs/framelease_v4/build/AMEND2/final/A10_spec.json --apply
   ```
   The phase driver waits for the lock up to 300 s and retries at its next cycle. `max_new_registered` is 8: the entry
   cites exactly the eight A10 files among the unregistered manifest files (it cites no A3 file by its full sha256;
   the three reused coverage files are outside the manifest).
5. Post-check: `registration.py --verify` (both seals OK); after the phase driver's next cycle, `driver.log` shows no
   ALERT and `phase_driver/registered_baseline.json` holds the eight files; `phase_driver.py --dry-run` shows the G8
   analysis-code registration satisfied (`analyze_v4.py` cited by Amendment A10). Update `PIPELINE_STATE.md`.

## 5. Open issues the entries depend on

1. Commit audit, null margins (A10 finding 1; blocks a decided H5). `build/R7/dev/agg_p1` (2026-11-14 11:50) reports
   12,958 'margin' violations in 38 of the 48 audited `fl_heuristic` runs of `lease_s1` / `lease_s2` (violations: B0
   8,179; E10 2,625; E5 2,154). Each flagged commit is accepted with a null margin, validity n_relevant > 0, n_computed
   0, reason `horizon_cap`, `min_g_m` null (all 12,958; `outputs/framelease_v4/build/AMEND2/r2_margin_null.py`, read
   only). In `framelease_v3/runtime/v3_lease.py` (lines 620-630) the prefilter keeps only agents whose distance lower
   bound can bring the margin to delta or below; with none kept the lease is the horizon cap, `LeaseResult.margin`
   returns +inf (no agent able to bind; its docstring: "agents skipped by the prefilter have g > delta everywhere"), and
   `margin_check` logs it as null. Eq. 9 (M > delta) holds for these commits; the current
   `commit_audit.no_relevant_agents` accepts a null margin only with n_relevant 0 or reason `no_relevant_agents`. With
   L* = B0 (lease_s2), the P4-P6 runs of `fl_heuristic` and `fl_full` produce such commits, so the rule decides H5. The
   rule step 0 implements (stated by A10 finding 1 and edit E3): an accepted commit with a null margin passes when its
   validity record names no relevant agent (n_relevant 0, else reason `no_relevant_agents`) or has reason `horizon_cap`
   and n_computed 0; any other accepted commit with a null margin and a relevant agent is a 'margin' violation; a commit
   event without a validity record keeps its current treatment. Tests: a `horizon_cap` record with n_computed 0 passes;
   a `horizon_cap` record with n_computed > 0 and a null margin fails. `commit_audit.py` is unregistered until A3 (a
   reviewed change needs no amendment); after A3 a change needs an amendment that installs the file under the lock.
   `framelease_v4/PIPELINE_STATE.md` (Batch 8) records "H5 dev 0 Eq. 9 violations in 4109 P1 commits": that is
   `build/AGG/smoke_D` (2026-11-11, P1-0 smoke and `ref` runs only).
2. `km_driven` 0.0 in `runs.csv` for an RC-0 run (A10 finding 2): the per-km values agree; the floor in `runs.csv`
   itself is an optional step-0 fix.
3. Table I columns beyond `verify_independent.py` (A10 deviation 9; step 7, required): GPU usage, DMR, action age
   p50 / p95, fallback ratio, EIR, P_both and the closed-loop R_cond are registered results (Secs. 7.2, 9.13) and enter
   the paper once the R7B recomputation is entered in Sec. 13. Item R7B: an independent session builds it from the run
   directories during P4-P6 (training-route runs and synthetic data only), standard library and numpy as
   `verify_independent.py`; it is reviewed and registered by its own amendment before the analysis freeze, runs after
   G8 next to `verify_independent.py`, and its result is entered before the paper is written. The phase driver's G8
   waits for A10 only: if the R7B amendment is not entered when the last tier-6 jobs run, the coordinating session
   writes `outputs/framelease_v4/phase_driver/STOP` (the driver stops at its next cycle; the runner continues) and
   restarts the driver after the amendment, with `STOP` moved aside.
4. Not rendered by `figures_tables.py` (A10 deviation 12): the Sec. 7.4 secondary offline protocols, `secondary.csv`,
   the replicates and noise floor, the manipulation checks beyond the background-load counts, and compact main-text
   variants of Tables II-A / II-B. A later item builds the supplement tables (with the scenario-type companion of
   Fig. 1, A10 deviation 11); registered by its own amendment if it changes a registered file.
5. R5 should-fix S1, S2, S5 (A10 "Known limitations"); S4 is the A10 reporting rule for Proposition 1; S3 is covered by
   `figures_tables.load_coverage`.

## 6. Checks of this item (all CPU, E-cores 12-15, nice 19, idle I/O, one BLAS thread)

* `check_drafts.py` (read only): placeholders; filled prose lines <= 120 columns; no anchor phrase, driver entry or
  heading line; the A10 title read as Amendment A10 and no other amendment title; the operational addition not read as
  A7b text; simulated application on PROTOCOL.md (current, with the lease_s2 entry): no ALERT of
  `p1_driver.protocol_view` / `phase_driver.phase_view`, P1 entries unchanged, the line citing `analyze_v4.py`
  attributed to A10 by `phase_driver.citing_amendment`, no line over 120 columns produced by an A10 in-place text;
  specs against templates and tree; the reused coverage code against gate2's `config.json`; the draft holds both
  templates verbatim; the open preconditions (step 0, E1-E4). Once PROTOCOL.md holds the operational addition (after
  step 3) and the phase driver's heading, the simulation inserts only A10 and requires the phase driver's entries
  unchanged by it. Result after the review fixes: the checks pass; 5 open preconditions (exit 2).
* `check_drafts_states.py` (read only; scratch file under /tmp/AMEND2): the simulation on the current PROTOCOL.md, after
  step 3 without and with the phase heading and a G1 entry (no problem), with the operational addition twice (a
  problem), and with A9's sentence in a Code paragraph rewrapped at 120 columns (in-place text 2 found once, no line
  over 120 columns). Result: exit 0.
* `check_plan_edits.py` (read only; scratch file under /tmp/AMEND2): the old texts of E1-E4 equal those that
  `check_drafts.py` looks for, each occurs once in `build/AMEND/AMENDMENTS_DRAFT.md`, and with E1-E4 applied to a copy
  only step 0 stays open. Result: exit 0.
* Tests at drafting (`logs/`): `pytest_phase_driver.log` 24 passed (163 s), `pytest_review_phase.log` 6 passed
  (67 s), `pytest_analyze_v4.log` 48 passed / 107 subtests, `pytest_prop1_coverage.log` 22 passed,
  `pytest_figures_tables.log` 50 passed, `pytest_verify_independent.log` 28 passed / 20 subtests.
* `fill_entry.py` on a copy of the operational-addition template that points to the drafting logs: complete fill, no
  prose line over 120 columns.
* `r2_margin_null.py` (read only, 0.7 s, 12 MB): the counts of Sec. 5, item 1.
