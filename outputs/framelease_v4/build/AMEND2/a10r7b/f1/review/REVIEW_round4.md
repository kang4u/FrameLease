Verdict: GO

Round-4 review of A11: fix pass 4 (`f1/PROGRESS.md`, section "Fix pass 4"): the fifth class "undefined-metric
pairing" (decided by the coordinating session after the G8 dry run), round-3 should-fix N1 and the round-3
housekeeping. `$A` stands for `outputs/framelease_v4/build/AMEND2/a10r7b/`, `build/` for `outputs/framelease_v4/build/`.

Reviewed versions (unchanged from 00:47 to the end of this review, 2026-11-16; sha256 checked at start and end):
`A11_entry.md` df2f49b2..., `A11_spec.json` bba16198..., `make_a11_spec.py` a7c85333..., `check_a11.py` 953fbb8a...,
`RUNBOOK.md` bf067f77..., `f1/F1_RULE.md` 5feda06a..., `f1/f1_class_report.py` ac82d65a..., `f1/test_f1_class_report.py`
b2d3388c..., `f1/evidence_a11_sha256.txt` ec80acac..., `f1/f1_class_dev.json` 22ceb51f..., `f1/f1_class_p1_rundirs.json`
60aeeece...; registered `verify_table1_extra.py` f77b2dcf..., its tests f0e74336..., `analyze_v4.py` 10d7ea4f.... Each
change was read as a diff against `f1/orig/*.before_fix4.*` (the entry word by word, since it was rewrapped). Every
process ran as `taskset -c 12-15 nice -n 19 ionice -c 3` with one BLAS thread, `CUDA_VISIBLE_DEVICES=''` and an
address-space cap of 1.5 GiB, one at a time, at most 94 MB resident. This round read no run directory, `runs.csv`,
verification output of real data or file under `build/G8CUT/`; the expected count was derived from the registered code.

**Summary.** The new class is defined by the mechanism of the registered code and implemented as stated: P_both is None
for exactly the arms outside the verifier's SHIELD_ARMS (`fixed_deep`, `fast_only`, `event_triggered`, `fl_original`);
`analyze_v4.paired` drops such a route with the status '<column> missing: <every missing condition>', while
`compare_paired_differences` pairs it on the used cells and compares no value unless both sides pair it, so the
difference is in the status only. Every requested counter-example stays unexplained or stops the report; N1 holds; the
expected 76 rows at the A12 scale follow from the analysis code and the A12 table; the P1 numbers are unchanged with 0
in the new class; the tests pass, the remaining reviewer-test failures are exactly the expected ones, and the
insertion and the check mode pass. One non-blocking gap (a named condition outside the contrast) is caught on a real
output by the contrast row; two sentences want more precise wording.

**The class against the registered code.**
* Arms: `verify_table1_extra.py` lines 195-199 and 748-751 (`p_both` only for SHIELD_ARMS = LEASE_ARMS without
  `fl_original`; a shield arm without shield epochs also gives None, but it is not in the class); `metrics_v4.py` gives
  None without a shield as well. UNDEFINED_METRICS = {p_both: column `p_both`, the four arms}: equal.
* Status and note: `analyze_v4.paired` writes `f'{metric.column} missing: {", ".join(miss)}'` with every missing
  condition (`Cond.name` = `<arm>_k<kappa:.1f>_s<seed>`); the verifier's note is `'status %r' % status`. The report's
  PAIRING_NOTE and CONDITION_RE parse exactly these forms.
* No numeric value differs: on such a route the analysis row carries no value and the verifier makes no value
  comparison; the contrast row of the same metric (n 0, means empty) agrees and is compared separately.

**Counter-examples** (`f1/review/r4_test_pairing.py`, 8 passed, 17 subtests; synthetic outputs and, end to end, the
verifier's own outputs for fixture runs of `fl_full`, `fl_heuristic` and `fixed_deep` with synthetic analysis files).
* Holds (unexplained, 'verification failure'): a numeric value_b or a difference 0 in the analysis row; a value row
  of the key in `differences.csv` (also the case of a duplicated analysis row, where the paired duplicate gives value
  rows); a shield arm named (`fl_heuristic`, `age_only`), alone or with `fixed_deep`; note and analysis status that
  differ; another metric (`r_cond` with 'realized_r_cond missing: ...'); another column in the note (`p_both_pooled`);
  'cell not used'; an arm with a suffix (`fixed_deep_v2`); a recomputed `fixed_deep` run with P_both; no recomputed run
  of the arm; the analysis row of another route; the reversed pairing. The analysis file: a sha256 that differs or a
  recorded file that is missing stops the report (exit 2); not recorded: unexplained.
* End to end: the genuine `fl_full - fixed_deep` rows (2) are the class (`p_both|fixed_deep` 2) and nothing else of
  `paired_differences.csv` or `secondary.csv` differs.
* Gap, non-blocking (should-fix N2): the class does not check that the named conditions are the contrast's own. An
  analysis row of `fl_full_minus_fl_heuristic_k1.0_s11_all` (P_both defined for both) dropped with the status 'p_both
  missing: fixed_deep_k1.0_s11' is absorbed (`test_condition_outside_the_contrast_gap`). The registered
  `analyze_v4.paired` names only the contrast's conditions, and on the verifier's output the wrongly dropped pair also
  changes the contrast row's n (`secondary.csv|n|analysis` unexplained), so the outcome stays 'verification failure'
  (`test_wrongly_dropped_pair_fails_through_the_contrast_row_holds`). Fix when convenient: require every named
  condition to be one of the two conditions of the contrast (parsed from its registered name
  `<a>_minus_<b>_k<kappa>_s<seed>_<subset>`).
* N1 holds: a not-ok candidate with the same job in two recorded `status.jsonl` stops the report (exit 2), whatever the
  outcomes; with one queue the class not-ok record holds the row.

**Expected count at the A12 scale.** The secondary contrasts (`run_secondary`: every contrast of FAMILIES on every
SECONDARY_METRICS key, P_both included; DESCRIPTIVE_CONTRASTS carry no P_both) against an arm without a shield:
`fl_full` - `fixed_deep`, `fast_only`, `event_triggered` (14 used routes each), `fl_heuristic` - `fl_original` and
`fl_full` - `fl_original` (13: route 23658 has no used `fl_original` cell, so both sides leave it unpaired), and F3,
`fl_full` - `fixed_deep` / `fast_only` at kappa 1.5 and 2.0 on E (2 used routes, 3248 and 2390): 42 + 26 + 8 = 76, the
other routes of each subset 'cell not used' on both sides. The count holds while every other kept job is used; each
further unused cell of these arms lowers it.

**Nothing else changed.** `f1/f1_class_dev.json` and `f1/f1_class_p1_rundirs.json` against their `before_fix4` copies:
only the new class (every number 0, source none) and its key in `differences_by_class` added; by class 26 / 0 / 69 /
41 / 0 / unexplained 0, release 'not final' (status development). The P1 verifications ran without `--analysis`, so
they hold no `paired_differences.csv` row. The round-2 and round-3 reviewer tests with the new key asserted 0 and
removed from every report (`f1/review/r4_without_new_key.py`): 17 tests, exactly 4 failures and 1 error, those of
fix pass 3 (the three round-2 M1 gap cases, the round-2 S3 release) and the N1 stop of
`test_two_queues_read_in_another_order_gap`. In the plain run (`r2_test_adversarial.py` 8 passed, 7 failed;
`r3_test_new.py` 5 passed, 1 failed) the three further failures are dict comparisons that lack only
`undefined_metric_pairing: 0`. The fixer's explanation is confirmed.

**Tests** (logs `f1/review/logs/r4_pytest_*.log`, 00:50:38-00:52): `test_verify_table1_extra.py` 87 passed, 80
subtests; `test_review_r7b.py` 14 passed, 2 subtests; `f1/test_f1_class_report.py` 34 passed, 59 subtests (each exit 0;
the counts of A11 "At drafting", RUNBOOK precondition 4 and the drafting logs in `f1/logs/`); round-1
`test_review_f1_class_report.py` 4 passed, 3 failed (its pin and the two gaps round-1 S3 closed).

**Insertion and check mode** (no run data). `/tmp/A11R2/PROTOCOL.sealed.r4.md` (= 3fa337c1..., A10 and A12 in it),
`f1/review/r2_insert_check.py` (the applier's composition, stamp 2026-11-16 02:00, the logs of `f1/logs/`): in-place
text once; 331 entry lines, prose at most 120 columns after filling (also with test summaries two characters longer),
4 table rows over 120; no line after the title read as a driver entry, amendment title, heading or Sec. 13.2 start;
no hedging word, no mention of an assistant; `p1_driver.protocol_view` and `phase_driver.phase_view`: A1-A12 once
each, A11 at line 3303 after A12 and before the anchor, P1 entries (10) and phase entries (6) unchanged, both R7B files
first cited by A11, a later G8 entry read. `f1/line_check.py`: all checks passed (337 added or changed lines).
`check_a11.py` on the project and the copy: checks passed, exit 2 with the three open application test logs.
`make_a11_spec.py --check`: equal. `sha256sum -c f1/evidence_a11_sha256.txt`: 23 OK. Check mode
`apply_entry_stream.py` on `/tmp/A11R2/A11_spec.tmp.json` (template and logs pointed at `f1/logs/`): "check:
pre-checks passed", exit 0; on `A11_spec.json`: STOP at the missing `pytest_f1_class_report.log` (precondition 6).

**Text** (non-blocking). (S1) A11 "Development comparison" and F1_RULE.md Sec. 4: "13 x 2 against `fl_original`"
reads as `fl_full` twice; write "13 x 2 for `fl_heuristic` and `fl_full` against `fl_original`". (S2) A11 class bullet:
"no value of that route differs" says more than the report tests; write as F1_RULE.md rule 3 does:
"`differences.csv` holds no value_a, value_b or difference row of that route". The Cause bullet (round 3 GO, N1
applied, the fifth class by decision), "Development data" (00:39-00:42), the five-class sentences and Evidence
(REVIEW_round3.md by sha256) are right; round-3 housekeeping is done (the two short lines are gone).

**Observation.** The class is limited to P_both by design. A status-only pairing difference of a metric that is
undefined by the data (R_cond of a run without conflict plans, P_both of a shield arm without shield epochs, an action
age without tracked ticks) stays unexplained and is a verification failure under A10 use rule 4; the G8 dry run
(synthetic) holds none.

**Before the application** (bookkeeping). Cite this review in the Cause bullet and under "Evidence"
(`{{sha256:...}}`), `check_a11.py --write-evidence`, close the open item of RUNBOOK Sec. 3 precondition 2 and Sec. 5
item 2; then `apply_entry_stream.py A11_spec.json --tests` right before the application, `check_a11.py` exit 0, check
mode "pre-checks passed".

**Files of this round.** `f1/review/`: REVIEW_round4.md, r4_test_pairing.py, r4_without_new_key.py,
logs/r4_pytest_*.log, logs/r4_without_new_key.log, PROGRESS.md (section "ROUND 4"); reused r2_insert_check.py,
r2_make_tmp_spec.py. Scratch: /tmp/A11R2/ (PROTOCOL.sealed.r4.md, sim_r4/, the temporary spec and template).

Registration (`registration.py --verify`) at start (00:47:25) and end (00:54:44), equal output: "manifest: OK", seal
PROTOCOL.md OK, seal MANIFEST.sha256 OK, exit 0; PROTOCOL.md 3fa337c1..., MANIFEST 0fdb720e..., SEAL 577f1c6a...,
REGISTRATION 6d309f94... unchanged; PIPELINE_STATE.md 31c502f2... (changed before this round, at 00:35:47; not written
here). At the end: the reviewed files unchanged; nothing under `framelease_v4/`, `registration/`, `amendment_a10/`,
`amendment_a11/`, `p1_driver/` or `phase_driver/` newer than the start; no new `__pycache__` or empty file under
`framelease_v4/`; no test directory left under /tmp. The protocol lock, the drivers, their queues, `build/G8CUT/`,
CARLA and the GPU were not touched.
