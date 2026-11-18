# Finding F1: the reporting rule of Amendment A11 and its evidence

`build/` stands for `outputs/framelease_v4/build/`. The rule is fixed by Amendment A11
(`build/AMEND2/a10r7b/A11_entry.md`, bullets "Reporting rule for finding F1" and "Use of the registered files", rules
2 and 3); this file states it with its evidence. Data read: P1 training-route outputs only (no test route, no P2 data).

## 1. The rule

1. `framelease_v4/arms/realized.py` stays as registered: F1 is not corrected, and `actor_log.py` and
   `framelease_v2/geometry.py` stay as registered as well.
2. The registered values, those of the aggregator (`aggregate_v4.py`) and the analysis (`analyze_v4.py`) through
   `realized.py`, are the values of Tables I and II and of the paper. The recomputation changes none of them.
3. The run of `verify_table1_extra.py` after the analysis freeze (A11 use rule 1) reports every difference whose cause
   in `differences.csv` is 'F1' as one class, class F1, with that cause:
   * the number of its differences, all and in scope 'analysis';
   * per arm, the number of runs with such a difference: the run directories of its `runs.csv`, `summary.json` and
     runner comparisons, with the arm of `runs_recomputed.csv`, and of them those with a difference in scope
     'analysis';
   * per affected column the largest absolute difference (`abs_diff`, else |ours - theirs|): the column is the target,
     the metric (in an analysis output, the component of the key or the field that names a metric) and the compared
     column (`their_field`) of `differences.csv`.
   `f1/f1_class_report.py` forms these numbers from the output directory of that run; its sha256 is cited under
   "Evidence" of A11, so the computation is fixed with the entry.
4. AGREE releases the columns. On DIFFER with every difference in class F1, the columns GPU usage, DMR, action age p50
   and p95, fallback ratio, EIR, P_both and the closed-loop R_cond are released with the registered values, and class
   F1 is reported.
5. The paper states class F1, its cause and its size (rule 3) next to the verification result.
6. A difference of any other cause, 'F3', 'F1+F3' or none, is a verification failure handled by the rules of
   Amendment A10 (use rule 4; Sec. 9.12): it is resolved and its cause entered in Sec. 13 before any of these numbers
   enters the paper.
7. The sha256 of `table1_extra.json`, of the `SHA256SUMS` of the verification directory and of the class F1 report,
   with the numbers of class F1, are entered in their own dated Sec. 13 entry before the paper is written (A11 use
   rule 3).

Class F1 holds exactly the cause 'F1'. The verifier gives a difference the first of 'F1', 'F3', 'F1+F3' under which
the other side agrees; a value that agrees only when both conventions apply ('F1+F3'), for example a route mean over
one route with an F1 plan and one with an F3 plan, is outside the class.

## 2. The mechanism

* `framelease_v4/arms/actor_log.py` places a row of the actor-box log at its frame time, a multiple of 0.05 s; the
  rows of the log carry these times exactly (`build/R7B/rereview/PROGRESS.md`, 12:05, `time_offsets.py`).
* `realized.py` evaluates a plan with `GTTrack` of `framelease_v2/geometry.py`. `GTTrack._bracket` takes a time as
  inside the log only up to the last row time + 1e-9 s; `realized.py` counts a clear plan as log-censored when
  `capture_s + 3.0 > t_end + 1e-9`.
* The plan sample times `capture_s + tau` lie above the 0.05 s grid by the runtime's clock offset: a drift of 1.49e-8
  s per s of simulated time, up to 2.98e-6 s at 200 s (the measurement of the review of the fixes on the 180 run
  directories of the snapshot, `time_offsets.py`, 12:05). On all plans of the P1 run directories (`plans.csv` of the
  verification outputs below): 7.45e-10 to 2.97e-6 s, median 5.9e-7 s, more than 1e-9 s for 98% of the plans (55,875
  of 56,892 on the snapshot; 67,860 of 68,977 on the 272 run directories). At the plans that F1 changes, the sample
  lies 1.39e-7 to 1.18e-6 s (snapshot) and 1.39e-7 to 1.99e-6 s (272 run directories) after the last row.
* So a sample that lands on the last row has no actors: a conflict first found there is lost, and a clear plan whose
  last sample (tau 3.0) lands there is log-censored. The recomputation follows Sec. 6.3 (the row within 1 ms) and
  counts these plans; it forms the registered convention as the view 'F1' and gives a difference cause F1 when the
  registered value equals the value under that view.
* The range "3e-7 to 1.1e-6 s" of the R7B review (should-fix S3, a sample of capture times) is narrower than the
  measured range above; A11 states the measured one.

## 3. Development evidence (P1 training routes)

Development comparison of the registered version (`build/R7B/dev/verify_p1_snap_2203_d/`, `sha256sum -c` OK;
`verify_table1_extra.py` f77b2dcf against `build/R7B/dev/agg_snap_2203/`, the aggregator of Amendment A3), class F1
by `f1_class_report.py` (`f1/f1_class_dev.json`):

| quantity | value |
|---|---|
| run directories recomputed | 180 (179 `runs.csv` rows with analysis_use) |
| comparisons / differences | 12,259 / 136 |
| differences by cause | F1 26, without a cause 110 |
| class F1 in scope 'analysis' | 1: `fast_only`, route 1792, EIR 94/412 = 0.2282 recomputed, 85/412 = 0.2063 registered |
| runs with a class-F1 difference | 19 of 180: `event_triggered` 6, `fast_only` 5, `fixed_deep` 4, `fl_heuristic` 4 (all with analysis_use) |
| largest absolute difference, `runs.csv` | realized_log_censored_plans 10, realized_invalid_ticks 9, realized_conflict_plans 1, realized_misses 1, realized_invalid_tick_ratio 0.0218 (route 1792, the value the analysis reads) |
| largest absolute difference, `arm_summary.csv` | realized_invalid_tick_ratio 0.0010 (`fast_only` mean EIR: 0.1102 recomputed, 0.1092 registered) |
| plans that F1 changes | 40 in 19 run directories: 38 clear here and log-censored there, 2 conflicts (misses) here and log-censored there |

On all 272 P1 run directories under `outputs/framelease_v4/tuning/` (`/tmp/A10A11/r7bfix/verify_p1_rundirs/`, item
R7B, 13:19-13:21; `f1/f1_class_p1_rundirs.json`): AGREE on `summary.json` (5,523 comparisons; no `runs.csv` in that
run), F1 changes 47 plans in 26 run directories (3 conflicts, 44 clear). The second review of the fixes ran the
registered `realized.py` on the 271 run directories with an actor log (`build/R7B/rereview/REVIEW.md`): for each of
its 68,946 plans the conflict status, the miss, V = 0 and the log-censoring equal the recomputation's view under
F1+F3, and every registered per-run count, R_cond and R_cond without V = 0 equals that view; EIR in 266 runs (the
other 5 differ by the F2 denominator and lie inside the bounds).

The 110 differences without a cause on the snapshot: the cross-check columns `gpu_usage_recomputed` (28) and
`gpu_busy_recomputed_s` (28) and `commits` (6) of `runs.csv`, which omit the work of a job still running at the end
of a run, and the timed-out unused run `v4p1_fl_heuristic_B0_d10_k1.0_s11_r23659` (46 `runs.csv` cells, 2 runner
result fields). Under rule 6 such differences in the final run are verification failures, each resolved under
Amendment A10.

## 4. Other causes (rule 6)

* F3 (cause 'F3'): `realized.py` takes V by linear interpolation of the clearance between the samples j - 1 and j
  (`framelease_v2/c2_eval.py` `observed_validity`, `geometry.py` `first_crossing_time`), over the actors within the
  candidate radius d_safe + 5 m. On the 271 P1 run directories it differs from the first crossing by up to 31.7 ms and
  decides the miss of 2 plans differently; in the development comparison the 3 values it changes (route 2086) agree
  within the bounds (F2), so F3 gives no difference there. In the final run a difference with cause 'F3' or 'F1+F3'
  is a verification failure (rule 6).
* The cause F3 omits the candidate radius (second review of the fixes, should-fix S1, not applied): an actor that
  enters the log next to the footprint at the conflicting sample, with every actor at sample j - 1 beyond the radius,
  gives a difference without a cause (V_lin up to 4.5 ms before the registered tau_j). No P1 plan has it.
* F2 with a decimated log and gaps inside a log give differences without a cause; no P1 log is decimated (largest 425
  kB), has rows more than 0.05 s apart or a row without actors.

## 5. Running the class report after the freeze

```
cd /home/kang/Desktop/DAC
taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
    outputs/framelease_v4/build/AMEND2/a10r7b/f1/f1_class_report.py \
    outputs/framelease_v4/verification/final_<stamp>_table1_extra \
    --out outputs/framelease_v4/verification/final_<stamp>_table1_extra_f1_class.json
```

The report reads `differences.csv`, `runs_recomputed.csv`, `table1_extra.json` and `cause_plans.csv` of that
directory only, checks the counts by cause against `table1_extra.json` (exit 2 when they differ), copies the status
(only 'final' counts) and states `release`: 'AGREE', 'class F1 only' or 'verification failure'. The output lies next
to the verification directory, never inside it, so its `SHA256SUMS` stays valid. Standard library only; 0.03 s and
19 MB on the snapshot.

## 6. Files

* `f1/f1_class_report.py`: the class report (rule 3); `f1/test_f1_class_report.py`: its tests on synthetic
  verification outputs (7 passed, `f1/logs/pytest_f1_class_report.log`).
* `f1/f1_class_dev.json`: its output on the development comparison (`build/R7B/dev/verify_p1_snap_2203_d/`).
* `f1/f1_class_p1_rundirs.json`: its output on the 272 P1 run directories (`/tmp/A10A11/r7bfix/verify_p1_rundirs/`;
  the input sha256 are recorded in the file).
* `f1/evidence_a11_sha256.txt`: the files A11 cites by sha256 under "Evidence" and "Files", at drafting
  (`check_a11.py` compares them; `--write-evidence` rewrites the list).
* `f1/logs/`: the drafting logs of the A11 tests (87 passed, 80 subtests; 14 passed, 2 subtests).
* `f1/line_check.py`: the line and parser check of a composed PROTOCOL.md against the sealed one.
* `f1/sim_output/`: the dry run of A10 then A11 on a scratch tree (`sim_tree.py --cases A`) and the line checks
  (RUNBOOK Sec. 3); the simulated PROTOCOL.md is kept as `.md.txt` and is never a source for the drivers.
* `f1/orig/`: the five files of the item before it (`*.before_f1.*`).
* `f1/PROGRESS.md`: the log of the item.
