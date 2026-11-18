**Amendment A21, {{datetime}} (Beijing time): resolution of the 121 differences outside the classes of Amendment A11
in the recomputation of Amendment A20, by the resolution rule of Amendment A16 (Amendment A17); no run, job line,
criterion or analysis rule changes.**
* Differences. The class report of Amendment A20
  (`outputs/framelease_v4/verification/final_20261117T161912_table1_extra_f1_class.json`, sha256
  `{{sha256:outputs/framelease_v4/verification/final_20261117T161912_table1_extra_f1_class.json}}`) reads "verification failure" with 121 differences
  outside the five classes of Amendment A11 (121 in the analysis scope). All 121 are status rows of the paired
  differences of the secondary metric closed-loop R_cond: the analysis records the route as missing for that metric
  ("realized_r_cond missing: <conditions>"), the recomputation records it as paired. No row holds a value, a difference
  or a different n on either side, and no per-run comparison of R_cond, conflict plans or misses differs for the cells
  of these pairs. For every condition that the analysis names, R_cond is undefined (no conflict plan, 0/0) both in the
  registered aggregation (`outputs/framelease_v4/analysis/final_20261117T161912/agg_p4/runs.csv`, sha256
  `{{sha256:outputs/framelease_v4/analysis/final_20261117T161912/agg_p4/runs.csv}}`) and in the recomputation
  (`outputs/framelease_v4/verification/final_20261117T161912_table1_extra/runs_recomputed.csv`, sha256
  `{{sha256:outputs/framelease_v4/verification/final_20261117T161912_table1_extra/runs_recomputed.csv}}`). The analysis drops such a route from the contrast
  (Sec. 9.8); the recomputation pairs it with empty values. The rows per contrast: `fl_full_minus_age_only_k1.0_s11_all`
  13; `fl_full_minus_event_triggered_k1.0_s11_all` 12; `fl_full_minus_fast_only_k1.0_s11_all` 11;
  `fl_full_minus_fast_only_k1.5_s11_E` 5; `fl_full_minus_fast_only_k2.0_s11_E` 6;
  `fl_full_minus_fixed_deep_k1.0_s11_all` 10; `fl_full_minus_fixed_deep_k1.5_s11_E` 5;
  `fl_full_minus_fixed_deep_k2.0_s11_E` 7; `fl_full_minus_fl_bandit_k1.0_s11_E` 8;
  `fl_full_minus_fl_fqi_nolease_k1.0_s11_E` 6; `fl_full_minus_fl_heuristic_k1.0_s11_all` 9;
  `fl_full_minus_fl_original_k1.0_s11_all` 10; `fl_heuristic_minus_age_only_k1.0_s11_E` 4;
  `fl_heuristic_minus_fl_global_shield_k1.0_s11_E` 3; `fl_heuristic_minus_fl_original_k1.0_s11_all` 8;
  `fl_risk_minus_fl_heuristic_k1.0_s11_E` 4. Evidence:
  `outputs/framelease_v4/verification/final_20261117T161912_table1_extra/differences.csv` (sha256
  `{{sha256:outputs/framelease_v4/verification/final_20261117T161912_table1_extra/differences.csv}}`) and
  `outputs/framelease_v4/analysis/final_20261117T161912/analysis/paired_differences.csv` (sha256
  `{{sha256:outputs/framelease_v4/analysis/final_20261117T161912/analysis/paired_differences.csv}}`).
* Resolution (Amendment A10, use rule 4; Amendment A11, use rule 2; Amendment A16). The differences have the cause that
  Amendment A16 resolved for the cut analysis, and no numeric value disagrees. The class report stays as computed and is
  reported as "verification failure" with this cause. With the cause entered here, the columns of Table I that Amendment
  A11 covers (GPU usage, DMR, action age p50 and p95, fallback ratio, EIR, P_both) and the closed-loop R_cond of this
  analysis enter the paper with their registered values, stated together with the size of every class: F1 0 differences
  (0 in the analysis scope), F3 0 (0 in the analysis scope), in-flight 0 (0 in the analysis scope), not-ok record 81
  (jobs `v4p4_fl_original_k1.0_s11_r23658`, `v4p5_fl_full_B0_d1_v4_qnet_5d8ffd7cf7dd_k2.0_s11_r1711`), undefined-metric
  pairing 304, and the 121 above.
* Manifest and seal after this entry: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.
