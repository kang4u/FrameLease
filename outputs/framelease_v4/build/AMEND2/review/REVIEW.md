# Review of item AMEND2: PROTOCOL Sec. 13.2 drafts (operational addition "phase driver", Amendment A10) and APPLY_PLAN2

Reviewed files. This review left all of them unchanged.

| file | sha256 |
|---|---|
| `final/OP_phase_driver_entry.md` | `148b7f5717e8c7b61fd0e570dc281f5e3ba4a75efbb312ac50c791234d7f3f5f` |
| `final/A10_entry.md` | `3fb819735446f2bf4ffd0cde2e384bc9ff5ccc4277ae7624d40d7654fb310194` |
| `final/OP_spec.json` | `8594385079e7a746fe588513d68a26de8de97a510855a7e08742dbef96d066c5` |
| `final/A10_spec.json` | `329509ef32f297d47a1a04ce3758cd5f58b780f4db4e3465bbb74087c955d6da` |
| `AMENDMENTS2_DRAFT.md` | `be63194aff3392b0215274f5bbcce86b62666e872c87f296a16c1e3841660f9c` |
| `APPLY_PLAN2.md` | `2fb801724659601272397e10f6b9afeda9fafdf6bab9187152b9ef1996b2ed55` |
| `check_drafts.py` | `3cf18166608c0399db5946f9badae6926963f309a4ba7c000b940d2cf9d95e9e` |
| `fill_entry.py` | `64ed5d8491bdcb4221a5729b575c215533c26feb87d655258adf592173551b77` |
| `sha256_at_drafting.txt` | `ddfcd0110cf2a5dbfbc2d802fc5c770e00079a3b420e5481941dd4eb33df1035` |

Sources checked against:
* the code: `phase_driver.py`, `start_phase_driver.sh`, `apply_entry.py`, `p1_driver.py` (helpers), `commit_audit.py`,
  `v3_lease.py`, `v3_scheduler.py`, `analyze_v4.py`, `prop1_coverage.py`, `figures_tables.py`, `verify_independent.py`,
  and `framelease_v2/analyze_closed_loop.py` (`dp_grid`, `sign_flip_test`);
* the build and review reports: `build/{R4,R5,R6,R7,PHASE,AMEND,AGG}` PROGRESS and REVIEW, and the development outputs
  under `build/{AGG,R4,R7}`;
* PROTOCOL Secs. 4.1, 4.8, 7.1, 7.2, 9.4, 9.5, 9.11-9.13, 11.1 and 13.2 (the existing entries and the closing
  paragraph), GAP_AUDIT Secs. 3.6-3.7 and the AMEND drafts A3, A4, A7b and A9.

Registration. `registration.py --verify` at the start (13:18) and at the end: manifest OK, and both seal lines are
OK. `p1_driver/registered_baseline.json` has 153 files, and none differs. Nothing was created or changed under
`framelease_v4/`.

## Verdict: GO_WITH_FIXES

Most statements in the two entries match the code, the reviews and the development outputs (see "Verified"). The
constraints that the drivers' parsers place on the text hold, both alone and in the full remaining order (own
simulation below). Four defects must be fixed before application:
* three statements would be false when sealed (M1, M2, M3);
* the apply plan treats a registered result as optional (M4).

## Must fix

**M1. Amendment A9, entered in step 3 of this plan, will be false when it is sealed.**
* Evidence. The A9 draft (`build/AMEND/AMENDMENTS_DRAFT.md` lines 657-673) has two statements that will no longer
  hold:
  * the list header "What was run (every execution on real data, 2026-11-11)";
  * the rule "Rule from this entry on. `analyze_v4.py` (R-4) is written and tested on synthetic CSVs only, as Sec. 9.12
    states."
* APPLY_PLAN2 Sec. 3 step 3.2 fills A9 "by the rules of `build/AMEND/AMENDMENTS_DRAFT.md`", with no change, and seals
  it after P1. By then, more executions on real data exist:
  * `aggregate_v4.py` ran on real P1 data on 2026-11-14: the aggregation `build/R7/dev/agg_p1` (11:46-11:50), and two
    `--write-freeze-record` probes on copies of the smoke job lines (`/tmp/R7/fq`, `/tmp/R7/fq2`). Source: R7 PROGRESS
    steps 2, 32 and 43.
  * `analyze_v4.py` ran five times on `build/AGG/smoke_D` (see M3).
* A10 records these runs "in addition to those of Amendment A9", but only at step 6. From step 3 to step 6, Sec. 13.2
  therefore holds:
  * a false claim that the list of executions is complete;
  * a "rule" that runs already made contradict.
* Fix. In APPLY_PLAN2 Sec. 2 step 3 (precondition) and Sec. 3 step 3.2, edit the A9 draft before it is filled:
  * List header: "What was run (every execution on real data up to the drafting of this entry, 2026-11-11; the
    read-only executions of 2026-11-14 are recorded in Amendment A10)". Alternatively, list those executions in A9
    with their times.
  * Rule: "`analyze_v4.py` runs during development on synthetic CSVs and, read-only, on training-route aggregations
    only (its runs of 2026-11-14 on `build/AGG/smoke_D`: Amendment A10)".
  * Keep the A10 wording "in addition to those of Amendment A9" consistent with whichever version A9 takes.

**M2. Step 0 changes the commit-audit rule, but the texts that describe the rule are not updated.**
* Evidence, the plan. APPLY_PLAN2 Sec. 2 step 0 and Sec. 5 item 1 settle the rule for null margins of `horizon_cap`
  leases in `commit_audit.py`, before A3.
* Evidence, the texts that state the old rule:
  * The A3 draft (`build/AMEND/AMENDMENTS_DRAFT.md` line 132, item 6) states: "A null commit margin passes only where
    the validity record names no relevant agent".
  * A10 finding 1 (`final/A10_entry.md` lines 142-144) states, in the present tense: "`commit_audit.py` accepts a
    null margin only when the record names no relevant agent (n_relevant 0 or reason `no_relevant_agents`). The rule
    for this case is settled in `commit_audit.py` before the analysis freeze".
* Effect. After step 0, both sentences describe a version that is no longer current:
  * A3 would register the new file with a false description;
  * A10 would be entered with a false present-tense statement, and without the rule that was settled.
* Nothing in the plan updates them:
  * step 0 says nothing about the texts;
  * Sec. 4 step 1 only checks "step 0 is done (A10's finding 1 states the rule as settled before the analysis
    freeze)".
* The A3 sha256 list (`build/AMEND/a3_sha256_at_drafting.txt`) also changes: `commit_audit.py` (now `96dd22c4...`)
  and `tests/test_commit_audit.py` (now `8e4cb39d...`).
* Fix, step 0 row. Add: "with the change, update the A3 draft, its sha256 list and its review." In the A3 draft,
  item 6 states the settled rule. For example: "a null margin also passes when the validity record has reason
  `horizon_cap` and n_computed 0 (the prefilter showed g > delta for every relevant agent, so M = +inf)".
* Fix, A10 finding 1. Rewrite it before step 6, and add that rewrite to APPLY_PLAN2 Sec. 4 step 1:
  * "the version used on `build/R7/dev/agg_p1` (sha256 `96dd22c4...`) accepted a null margin only when ...";
  * "step 0 settled the rule: <rule> (`commit_audit.py`, Amendment A3)".

**M3. A10 deviation 1 understates the development runs of `analyze_v4.py`.**
* Evidence. `final/A10_entry.md` lines 47-50 state "one read-only run on the development aggregation of P1
  training-route runs `outputs/framelease_v4/build/AGG/smoke_D` ..., output `.../build/R4/smoke_train_D/`".
* `build/R4/PROGRESS.md` records five command-line runs on `smoke_D`:

  | time | R4 step | output |
  |---|---|---|
  | 07:40 | 22 | `/tmp/R4/smoke_train` |
  | 07:47 | 36 | `/tmp/R4/smoke_train2` |
  | 08:05 | 53 | `/tmp/R4/smoke_train3` |
  | 08:14 | 68 | `build/R4/smoke_train_D` |
  | 08:42 | 93 | `build/R4/smoke_train_D`, `--force`, final code `10d7ea4f...` |

* It also records a `load_aggregation` check on `smoke_D` at 07:35 (step 6).
* A9 lists every execution on real data with its time, and A10 records the same kind of deviation from Sec. 9.12. A10
  must therefore give the full list too.
* Fix. Replace the sentence with: "five read-only command-line runs on the development aggregation
  `outputs/framelease_v4/build/AGG/smoke_D` of Amendment A9 on 2026-11-14 (07:40, 07:47 and 08:05 into scratch
  directories under /tmp; 08:14 and 08:42, the last with the final code and `--force`, into
  `outputs/framelease_v4/build/R4/smoke_train_D/`) and a load check (07:35): no test-route row, every family with
  n 0".

**M4. APPLY_PLAN2 makes the independent recomputation of seven Table I columns optional.**
* Evidence, the plan:
  * APPLY_PLAN2 Sec. 2 step 7 says "... if those columns are to enter the paper";
  * Sec. 5 item 3 says "Without it, these columns stay out of the paper's numbers."
* Evidence, PROTOCOL:
  * Sec. 7.2 lists GPU usage, DMR, action age p50 / p95, fallback ratio, EIR and P_both as Table I columns, and RC
    and closed-loop R_cond as table notes;
  * Sec. 9.13 says: "Every registered result appears in the paper or its supplement."
* A10 deviation 9 (and its Sec. 9.12 in-place text) admits these columns only after an independent recomputation is
  entered in Sec. 13. Taken together, the recomputation is required, not optional. Without it, registered results
  are left out.
* Fix. Make step 7 (and Sec. 5 item 3) required, and name its own item:
  * build it with an independent session, from the run directories (Secs. 6.2-6.4, including the actor-box realized
    validity behind EIR, R_cond and P_both);
  * build it during P4-P6, on training-route runs and synthetic data;
  * have it reviewed, and register it by its own amendment before the analysis freeze;
  * run it after G8, next to `verify_independent.py`;
  * enter its result before the paper is written.
* Delete "if those columns are to enter the paper" and the sentence "Without it, ...".

## Should fix

1. **Finding 1 counts.** "12,958 'margin' violations in 38 runs, all `fl_heuristic` runs of the stages `lease_s1` and
   `lease_s2`" reads as if these 38 were all such runs. `agg_p1` audited 48 of them (B0 18, E5 18, E10 12), and 38
   violate. Write "in 38 of the 48 audited `fl_heuristic` runs of the stages `lease_s1` and `lease_s2` (violations:
   B0 8,179, E10 2,625, E5 2,154)".
2. **Deviation 11 cites the wrong source.** It cites GAP_AUDIT R-6, but PROTOCOL Sec. 7.1 itself defines the two
   panels:
   * panel (a), offline: error against observation age, and the Fast@Fresh - Deep@Old contrast against kappa;
   * panel (b), closed loop: per scenario type and per ability.

   The layout departs from Sec. 7.1, and the PROTOCOL governs, so cite Sec. 7.1. The phrase "placed as Fig. 1(d) or
   in the supplement" also leaves the placement open. Fix one; Sec. 9.13 is met either way.
3. **Reused code of the coverage is not registered.** The registered coverage depends on code outside the
   registration:
   * `framelease_v3/envelopes.py` and `framelease_v2/calibration.py` are in `prop1_coverage.CODE_FILES`, but not in
     `MANIFEST.sha256` and not cited in PROTOCOL;
   * `framelease_v3/suffix_lease_eval.py` is in neither.

   Cite their sha256 in A10 (Files or Evidence). R5 review Sec. 3 found them equal to gate2's `config.json`.
4. **Manual transaction (APPLY_PLAN2 Sec. 3 step 3): no post-manifest check before insertion.** The check that every
   registered file entered the new manifest at its sealed sha256, and that none vanished, runs only after the seal
   (step 4). The other paths all run it before:
   * `apply_entry.py` ("After write-manifest");
   * both drivers;
   * PHASE review M3 asks for it.

   Departure 3 of the operational addition states this property in the sealed text. Run the one-liner right after
   `--write-manifest` (step 3.1), and stop before inserting anything if it fails.
5. **Priority of the application commands.** In APPLY_PLAN2 Sec. 4, steps 3 and 4 run `apply_entry.py` (check mode
   and `--apply`) without `taskset -c 12-15 nice -n 19 ionice -c 3` and the one-thread BLAS environment. A10 may be
   applied during P2, while closed-loop jobs run. The priority rule of the operational addition (Secs. 2.3 and 11.2,
   A8) puts every tool on the E-cores at nice 19 then. Add the prefix, and write it out in the flock command of Sec. 3
   step 3 as well.
6. **Plan details.**
   * APPLY_PLAN2 Sec. 4 step 2 lists `build/AMEND/AMENDMENTS_DRAFT.md` (read by `test_phase_driver`) among the
     development inputs of the A10 tests. `test_phase_driver` is an OP test, so move it to Sec. 3 step 2.
   * Sec. 5 item 1 cites `/tmp/AMEND2/r2_margin_null.py`. /tmp is not durable; keep the script in the item directory.
7. **A3's analysis test log now includes the A10 tests.** A3 runs the whole directory `framelease_v4/analysis/tests`
   into `amendment_a3/pytest_analysis.log`. It now also runs the four A10 test files: 196 tests in R6's run of
   2026-11-14 11:26, against 76 in AGG step 159 (2026-11-14 04:00), before the R4-R7 test files existed. Either run A3's log on A3's five test files, or state in A3 that its count includes the A10
   tests (APPLY_PLAN2 Sec. 3 step 2).
8. **Test-only options in the operational addition's launch.** The OP "Launch" bullet says the script and the driver
   refuse a niced or CPU-pinned start. That holds only without `--allow-nice-launch`. Also, `--normal-priority` runs
   the tools without nice, ionice or taskset. Both are test options, and the driver accepts them in the project tree.
   State that the start passes neither; APPLY_PLAN2 step 5 passes none.
9. **Wording (no mention of who wrote anything).**
   * A10 use rule 4: "A session that wrote neither the aggregator nor the analysis runs it" becomes "An independent
     session (Sec. 9.12) runs it".
   * "The reviewer's tests" (A10 known limitations; OP Tests) becomes "The review tests".
10. **The fifth in-place clause occurs twice.** After step 3 the clause stands twice in the flattened text (simulated
    below): in Sec. 4.1, and in A3's own quotation of its in-place text. `apply_entry.py` stops when the count is not
    1, so the step fails safe. APPLY_PLAN2 Sec. 4 already asks for the exact Sec. 4.1 line breaks. Add that the
    indented A3 quotation differs and must not be the one matched.
11. **Wrong step number in the OP preface.** The preface in `AMENDMENTS2_DRAFT.md` says "before the phase driver starts
    (`APPLY_PLAN2.md` Sec. 2, step 4)". The entry is step 3, and the start is step 5.
12. **Sec. 9.12 after A9 and A10 (simulated).** The **Code.** paragraph still says of `analyze_v4.py` "Both are written
    and tested on synthetic CSVs only". A10's new paragraph, a few lines below, says otherwise. Point the Code
    paragraph to A10. For example, A10's in-place text could append "(the analysis code: Amendment A10)" there.

## Verified

* **Hashes and tests.**
  * All 25 files of the appendix (`sha256_at_drafting.txt`) are at their drafting sha256 now. Both `must_equal` lists
    equal the tree.
  * The drafting test logs equal my reruns (see the last section).
* **Insertion mechanics** (`apply_entry.py`, the drivers' parsers):
  * The insertion goes before the anchor. Titles: the A10 title is read as Amendment A10, and the OP has no amendment
    title.
  * The OP does not match `A7B_RE`. No line reads as a driver entry or heading. The anchor phrase does not occur.
    Filled prose lines are at most 120 columns.
  * `check_drafts.py` (rerun, read-only): all checks passed.
  * `max_new_registered` 8 (A10): `MANIFEST.sha256` holds no `outputs/framelease_v4/build` file, so the REVIEW and
    `SHA256SUMS` citations register nothing. OP: `--tests` only, and `--check` / `--apply` stop at the template check.
  * The four existing A10 in-place texts occur once each, now and after step 3. The fifth exists only after A3, as
    stated.
* **Full remaining order, simulated in memory** (`/tmp/AMEND2_REVIEW/sim_full_order.py`). The order is: A3, A9, A7b,
  A4 and OP with the A3 and A9 in-place texts; then the phase heading with G1; then A10; then a G2 entry. Results:
  * `p1_driver.protocol_view` and `phase_driver.phase_view` raise no ALERT;
  * the P1 entries are unchanged, and A3, A4, A7 and A9 are read (G0);
  * A7 is read as A7b;
  * the G2 entry lands inside the phase block, above A10;
  * the first line citing `analyze_v4.py` is attributed to A10 (`citing_amendment`, G8).
* **Operational addition, against the code.** These match the `phase_driver.py` docstring and code:
  * G0-G8 as tabled, and `REQUIRED_AMENDMENTS` A3, A4, A7, A9;
  * D1 file and checks, `DECISION_GRACE_S` 120 s;
  * runner command and rules, `EMPTY_EXIT_LIMIT` 2, disk 7.3 / 11.9 GiB;
  * priorities: nice 10 / best-effort 7, E-cores 12-15 at nice 19, P3 and stress on all cores;
  * `insert_entry` placement, `refresh_baseline` (seal pair, citation rule), `analysis_registration`, and G7 health
    only (`p4_progress` holds counts only).

  The `start_phase_driver.sh` scope (`OOMPolicy=continue`), `driver.lock` and the refusals also match.
* **Operational addition, against the records.**
  * The delegation quote matches `DELEGATION` and PIPELINE_STATE line 27 (2026-11-14 04:00). Sec. 4.8 is quoted
    exactly.
  * Departure 2: the A4 row of `APPLY_PLAN.md` is row 9, "during P2 or P3". Departure 3: the baseline one-liner
    prints OK now.
  * Review: GO_WITH_FIXES. M1-M4 and S1-S8 were applied (S7 through M2). The chaos runs after the fixes: seeds 10-21
    12/12 and seeds 30-35 6/6 (PHASE PROGRESS lines 150-152), on the final `phase_driver.py` `2bf4147c...`.
* **A10 file table, against the reviews.**
  * Verdicts: R4 GO_WITH_FIXES (must-fix 1-2 and should-fix 1-5 applied); R5 GO (S1-S6 dispositions as stated); R6
    GO_WITH_FIXES (must-fix 1-4 applied; compact variants and supplement tables not done); R7 GO_WITH_FIXES (must-fix
    1-3 and step 1 of 4 applied; `numbers.json` comparison not done).
  * `verify_independent.py` imports only the standard library and numpy.
  * No job line pins the A10 files, and no agent, rl or v2/v3 module imports them.
* **A10 deviations, against code and outputs.**
  * Deviation 2: `h4_offline.csv` has 12 rows from `paired.csv`, all 'inconclusive'.
  * Deviation 4: pooled collisions/km.
  * Deviation 5: `dp_grid` coarsening above `MAX_DP_BINS` = 2^23 (1-2-5 steps); `analyze_v4` reports `dp_grid` and
    `dp_grid_registered`.
  * Deviation 6: `per_clip_check` compared 30 rows, max difference 4.97e-6. 7 of the 11 secondary rows combine two or
    more variations; recounted, and R4's "6" was wrong.
  * Deviations 7 and 8: the H5 and NO_LOG rules, and panel B, as in the `analyze_v4` docstring.
  * Deviations 9 and 10: the scope and statistics of `verify_independent`, as in its docstring. The Table I column
    list is complete against Sec. 7.2.
* **Findings, recounted independently** (`/tmp/AMEND2_REVIEW/null_margin_check.py`, read-only):
  * 38 violating runs and 12,958 flagged commits. Every one is an accepted commit with a null margin, a validity
    record with n_relevant > 0 and n_computed 0, reason `horizon_cap`, and `min_g_m` null. No finite margin is at or
    below delta.
  * The `v3_lease.py` prefilter (lines 619-630) and the `LeaseResult.margin` docstring are quoted correctly.
    `margin_check` logs a non-finite margin as null.
  * `smoke_B`, `smoke_C` and `smoke_D` are PASS with 4,109 accepted commits each. The PIPELINE_STATE Batch 8 phrase
    matches.
  * Findings 2 and 3 match R7 PROGRESS steps 43 and 61.
* **Wording.**
  * No hedging words appear in either entry.
  * The form matches the existing Sec. 13.2 entries: title line, bullets, and "Manifest and seal after this
    amendment/addition".
  * The scope lines are present and correct: no job line pins these files, and G8 waits for A10.

## Checks run (E-cores 12-15, nice 19, idle I/O, one BLAS thread, one at a time)

| check | result | time / memory |
|---|---|---|
| `check_drafts.py` | all checks passed | 0.15 s / 30 MB |
| `/tmp/AMEND2_REVIEW/null_margin_check.py` | 38 runs; 12,958 commits, all `horizon_cap`, n_computed 0 | 0.7 s / 12 MB |
| `/tmp/AMEND2_REVIEW/sim_full_order.py` | see "Verified" | 0.13 s / 30 MB |
| `test_analyze_v4.py` | 48 passed, 107 subtests | 16.0 s / 218 MB |
| `test_prop1_coverage.py` | 22 passed | 20.6 s / 129 MB |
| `test_figures_tables.py` | 50 passed | 24.8 s / 225 MB |
| `test_verify_independent.py` | 28 passed, 20 subtests | 14.5 s / 73 MB |

* The test logs are in `/tmp/AMEND2_REVIEW/`.
* `test_phase_driver.py` (163 s) and `test_review_phase.py` (67 s) were not rerun. `apply_entry.py --tests` reruns
  them at application. The drafting logs show 24 passed and 6 passed.
