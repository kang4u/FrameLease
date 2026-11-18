**Amendment A16, {{datetime}} (Beijing time): resolution of the 28 differences outside the classes of Amendment A11
in the recomputation of Amendment A15, and two corrections of record; no run, job line, criterion or analysis rule
changes.**
* Differences. The class report of Amendment A15
  (`outputs/framelease_v4/verification/final_20261116T091445_table1_extra_f1_class.json`, sha256
  `{{sha256:outputs/framelease_v4/verification/final_20261116T091445_table1_extra_f1_class.json}}`) reads
  "verification failure" with 28 differences outside the five classes of Amendment A11. All 28 are status rows of the
  paired differences of the secondary metric closed-loop R_cond: the analysis records the route as missing for that
  metric ("realized_r_cond missing: <conditions>"), the recomputation records it as paired. No row holds a value, a
  difference or a different n on either side. In every row R_cond is undefined (no conflict plan, 0/0) for at least
  one condition of the pair, both in the registered aggregation
  (`outputs/framelease_v4/analysis/final_20261116T091445/agg_p4/runs.csv`, sha256
  `{{sha256:outputs/framelease_v4/analysis/final_20261116T091445/agg_p4/runs.csv}}`) and in the recomputation
  (`outputs/framelease_v4/verification/final_20261116T091445_table1_extra/runs_recomputed.csv`, sha256
  `{{sha256:outputs/framelease_v4/verification/final_20261116T091445_table1_extra/runs_recomputed.csv}}`). The
  analysis drops such a route from the contrast (Sec. 9.8); the recomputation pairs it with empty values. One row,
  `fl_full_minus_event_triggered_k1.0_s11_all` on route 2390, rests on an Event-Triggered cell whose point value is
  undefined (no conflict plan) and whose recomputed interval is [0, 1], from plans left unevaluated by a job in flight
  at the end of the run; its registered value is undefined as well. The rows: Full FrameLease against Fixed Deep 3,
  Fast Only 3, Age-Only 2, Event-Triggered 3 and FrameLease + Heuristic 3; FrameLease + Heuristic and Full FrameLease
  against Original FrameLease 6 each; Full FrameLease against Fixed Deep and Fast Only at kappa 1.5 on route 2390, 1
  each. Evidence: `outputs/framelease_v4/verification/final_20261116T091445_table1_extra/differences.csv` (sha256
  `{{sha256:outputs/framelease_v4/verification/final_20261116T091445_table1_extra/differences.csv}}`) and
  `outputs/framelease_v4/analysis/final_20261116T091445/analysis/paired_differences.csv` (sha256
  `{{sha256:outputs/framelease_v4/analysis/final_20261116T091445/analysis/paired_differences.csv}}`).
* Resolution (Amendment A10, use rule 4; Amendment A11, use rule 2). The 28 differences have the cause above and no
  numeric value disagrees. Their mechanism is the one of the class "undefined-metric pairing" of Amendment A11, for a
  metric that the data leave undefined (a zero denominator) instead of an arm's definition, a case A11 does not cover.
  The class report stays as computed and is reported as "verification failure" with this cause. With the cause entered
  here, the columns of Table I that Amendment A11 covers (GPU usage, DMR, action age p50 and p95, fallback ratio, EIR,
  P_both) and the closed-loop R_cond enter the paper with their registered values, stated together with the size of
  every class: F1 105 differences (92 in the analysis scope, all from one plan of Full FrameLease on route 17563, EIR
  of that run 0.0727 registered against 0.1061 recomputed), F3 0, in-flight 46 (none in the analysis scope), not-ok
  record 40 (the timed-out job `v4p4_fl_original_k1.0_s11_r23658`), undefined-metric pairing 76, and the 28 above.
* Correction 1, entry "G4 RL freeze". The decision text that the entry quotes from
  `outputs/framelease_v4/phase_driver/P3_OPEN_CASES.json` calls the FQE interval [28.9, 56.9] of
  `fqi_K128_leaf40_beta0_d1` a 95% route-bootstrap interval. The RL freeze records it as the 90% interval (ci90,
  coverage 0.9, 2000 resamples over the 44 training routes; `outputs/framelease_v4/rl_freeze/rl_freeze.json`, sha256
  `{{sha256:outputs/framelease_v4/rl_freeze/rl_freeze.json}}`), the interval of the FQE selection (Secs. 5.5 and
  5.6). The interval is a 90% interval; nothing else in that entry changes.
* Correction 2, outputs list of the analysis. `ANALYSIS_OUTPUTS.sha256` of
  `outputs/framelease_v4/analysis/final_20261116T091445/`, a list that no entry cites, holds one line for its own
  temporary file `.ANALYSIS_OUTPUTS.tmp`, because the list was computed while that file was written; the other 61
  lines match the files on disk, and every `SHA256SUMS` of the analysis directories, which Amendments A13-A15 cite,
  verifies. The list stays as written.
* Aggregation path. The verifications of Amendments A14 and A15 read the released aggregation of the test phase,
  `outputs/framelease_v4/analysis/final_20261116T091445/agg_p4`. The analysis keeps the aggregations of the phases in
  subdirectories of `final_<stamp>/` (`agg_p4`, `agg_p1`, `agg_p2`) because H5 audits every phase; `agg_p4` is the
  aggregation that use rule 1 of Amendment A10 and of Amendment A11 names as `final_<stamp>/`.
* Manifest and seal after this amendment: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.
