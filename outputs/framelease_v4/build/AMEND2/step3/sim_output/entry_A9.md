**Amendment A9, 2026-11-15 06:22 (Beijing time): the aggregator was developed with read-only runs on finished P1
training-route runs (Sec. 9.12; no test-route result examined; no effect on any run or criterion).**
* Cause. Sec. 9.12 states that `aggregate_v4.py` and `analyze_v4.py` "are written and tested on synthetic CSVs only".
  The aggregator (`framelease_v4/analysis/`, Amendment A3) was tested on synthetic run directories and, in addition,
  run read-only on the finished runs of `outputs/framelease_v4/queue_p1`: the P1-0 smoke runs and the P1 `ref` runs,
  all on training routes, which are examined by design (Sec. 9.11: "Training-route results are examined by design
  (Phase 1, D1, Phase 3)").
* What was run (every execution on real data up to the drafting of this entry, 2026-11-11; the read-only executions from
  2026-11-14 on are recorded in Amendment A10).
  * Seven development aggregations over the 128 jobs of `queue_p1` (42 final: the 7 P1-0 smoke jobs and 35 `ref`
    jobs) into four output directories: `outputs/framelease_v4/build/AGG/smoke_A` three times (18:57, then 18:58 and
    19:00 with `--force`), `smoke_B` once (19:18), `smoke_C` twice (19:35, then 19:38 with `--force`), all during the
    pause, and `smoke_D` once (23:39:44-23:40:06).
  * Probe executions of refused requests on the same data into `smoke_C` (19:35, `--force`, outputs unchanged):
    `--arm-summary test` and `all` and `--analysis-freeze` with an invalid record (exit 4), `--write-freeze-record`
    (exit 2: 86 jobs not final).
  * A guard check over 6 `ref` jobs, run twice (19:36 and 19:38; `smoke_C_guard`: the training route 17569 declared
    an extra test route to exercise the Sec. 9.11 guard on real logs).
  * Two determinism runs of the independent review (`build/AGG/review/det_1`, `det_2`, 19:48-19:50).
  * Their outputs were written only under `outputs/framelease_v4/build/AGG/`. No test-route run existed; none was
    read. The values were used to check the code (hand recomputation of DS, RC, infractions per km, DMR, EIR, R_cond,
    P_both, prefix p50, lease utilization and premature expiry from the raw logs of 5 runs, all equal), never to
    choose a metric, a rule or a parameter of the analysis.
* Rule from this entry on. `analyze_v4.py` (R-4) runs during development on synthetic CSVs and, read-only, on
  training-route aggregations only (its runs of 2026-11-14 on `outputs/framelease_v4/build/AGG/smoke_D`: Amendment A10).
  During development the aggregator runs on training-route runs (P1, P2) only; before the analysis freeze it shows
  test-route runs as job health only (the Sec. 9.11 guard, Amendment A3).
* In-place text, Sec. 9.12, after "Both are written and tested on synthetic CSVs only.": "The aggregator was also run
  read-only on finished P1 training-route runs during development (Amendment A9)."
* Scope. No run, job file, selection or criterion changes; the registered analysis is unchanged.
* Files. `framelease_v4/analysis/aggregate_v4.py` (`ee13c90b91bf44ad59d0a3c7e60bf93d65964785ed386d3e81c44fea0f5e4b96`)
  and `framelease_v4/analysis/interim_guard.py` (`5453a3573e7cca958cad1bc1c44d53995a11e034e251bba634fe09390efed9c7`),
  both Amendment A3, whose docstrings state this deviation; the output manifests of the development runs (each written
  by the last execution into its directory) `outputs/framelease_v4/build/AGG/smoke_A/SHA256SUMS`
  (`21f835a54a403d553ddae7b5334cf04e27c419313cd7464293a1aa017de0b397`), `smoke_B/SHA256SUMS`
  (`eb69c49d1c69ef2a1c1c7115d46b29e16488de19133a0391f48bf7f14928276e`), `smoke_C/SHA256SUMS`
  (`06751835016a6a001e1efcd38089e7ae09585bde52445e82b8b7155e3953a6a5`), `smoke_C_guard/SHA256SUMS`
  (`cbb0d53198b122d3cedc012f9a77bc383a8504de4a72c6582653b7c27d11a7e4`) and `smoke_D/SHA256SUMS`
  (`97f28abfa9da7f595f9344cf25e005a3f80197e73ae5cbf8efede789161bf312`).
* Tests. `framelease_v4/analysis/tests/test_interim_guard.py` (health-only rows before the freeze, a development
  record never releases a registered test route; Amendment A3 log `pytest_analysis.log`).
* Manifest and seal after this amendment: `MANIFEST.sha256`, 221 files, sha256
  `8c50b99209af9648f0ff35c95a8725a1c6585f221dbd26ea1d56545a2e60e0c9`, sealed with this entry.
