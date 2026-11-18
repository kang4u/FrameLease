**Amendment A18, 2026-11-17 16:20 (Beijing time): the second analysis freeze (Sec. 9.12) under Amendment A17, all
registered jobs final, carried out by the coordinating session with the registered tools in place of gate G8 of the
phase driver; no run, job line, criterion or analysis rule changes.**
* Freeze. Every job of the six registered job files of the test freeze was final and the runner of
  `outputs/framelease_v4/queue_p4` had exited (last runner exit 2026-11-19T01:55:00Z);
  `outputs/framelease_v4/queue_p4/STOP` was written before the freeze and `test_freeze.py --verify` passed on the job
  files in `outputs/framelease_v4/queue_p4/jobs.d`. `aggregate_v4.py --queue outputs/framelease_v4/queue_p4 --specs
  outputs/framelease_v4/test_jobs/FULL --rl-freeze outputs/framelease_v4/rl_freeze/rl_freeze.json --tuning-freeze
  outputs/framelease_v4/tuning/selection.json --write-freeze-record
  outputs/framelease_v4/analysis/final_20261117T161912/analysis_freeze.json` wrote
  `outputs/framelease_v4/analysis/final_20261117T161912/analysis_freeze.json` (sha256
  `e0e17c5bce96d980d6ad88764bc2892b499117fa1833d8e127b6661c2bd8fa5c`; trigger all_final, no cut, frozen
  2026-11-17T16:19:33+0800).
* Job status: 632 jobs of the 6 job files of the test freeze (entry "G6 Test freeze", record
  `outputs/framelease_v4/test_freeze/test_freeze.json` sha256
  `e9e2d309fefd49209d1303356328049f8c0e89534f1b0cfaffffea82ed1ba633`):
  `outputs/framelease_v4/queue_p4/jobs.d/b11_ti_main.jsonl` (tier 3, 308 lines, sha256
  `54e551df44f30a02277e91849f1e40390cd77ffca7e59256edc98b3f5cd4a6df`);
  `outputs/framelease_v4/queue_p4/jobs.d/b12_f3_k.jsonl` (tier 4, 176 lines, sha256
  `8ba8a4e5f6874860f9fefae81d836ccbdd297ac6a801a67663d6a5322507311b`);
  `outputs/framelease_v4/queue_p4/jobs.d/b13_a_lease.jsonl` (tier 5, 22 lines, sha256
  `6b906bc220d74fdf8fb5bfce287465e608fd378b22869af6d188ec411d37bd2a`);
  `outputs/framelease_v4/queue_p4/jobs.d/b14_a_rl.jsonl` (tier 5, 44 lines, sha256
  `a73491e47ab5cb3fcba868a0e5e6bf7f34c5ad6a09ea3fde8cd11d18ef623e31`);
  `outputs/framelease_v4/queue_p4/jobs.d/b15_s_seed12.jsonl` (tier 6, 60 lines, sha256
  `bd77e5ed172bc834b63a4fa188cae97f92047f8072a45b92e738aad52cffd207`);
  `outputs/framelease_v4/queue_p4/jobs.d/b16_s_risk.jsonl` (tier 6, 22 lines, sha256
  `83fe874f000340d6ee15509c35c7829bd03a6612a75a181e82c0b26ab36a156b`); outcomes ok 630, agent_crashed 0, sim_failure 2;
  no job cut. The 127 jobs that the record of Amendment A13 holds as final carry the same outcomes and run directories
  here (ok 126, agent_crashed 0, sim_failure 1); the 505 jobs that Amendment A12 cut and Amendment A17 runs are final
  (ok 504, agent_crashed 0, sim_failure 1).
* Analysis code frozen by the record: `aggregate_v4.py` (sha256
  `ee13c90b91bf44ad59d0a3c7e60bf93d65964785ed386d3e81c44fea0f5e4b96`), `commit_audit.py` (sha256
  `7439a4eac0986cad6a25b7395975a0411b7483944a988d68dabb656bd2544ec7`), `extra_metrics.py` (sha256
  `53050f6bed5aa48054d5217832fb84ed4089b3ae80e8fdcf965769af2af79c4c`), `interim_guard.py` (sha256
  `5453a3573e7cca958cad1bc1c44d53995a11e034e251bba634fe09390efed9c7`), `manipulation.py` (sha256
  `78f18dacf323832ef16684b0b81a2ba03b2ffb00186259780d1bafe7e656cbd0`); the analysis script
  `framelease_v4/analysis/analyze_v4.py` (sha256 `10d7ea4f9516725cd94932a0618bbe5cc6a20bae60b49f4004013b3682cee54c`) and
  `framelease_v4/analysis/verify_independent.py` (sha256
  `4935152684abcfdaef547438772bb041f323344dcbfe636d41b2a161ff149bff`) are registered in Sec. 13.2 by Amendment A10,
  `framelease_v4/analysis/verify_table1_extra.py` (sha256
  `f77b2dcf34484d2537a4c22d804912f0c155c3e3c26a576f433b9f4f73d83c27`) by Amendment A11. Route split sha256
  `555f6869cb62d89082efc0fefc8f125ee133b16fd36a6fcf9f68bb1269fa527e`.
* Interim looks (Sec. 9.11). The aggregation that made the record ran without --arm-summary and without
  --analysis-freeze: every test-route row stayed health-only and no cross-arm summary was made. Its outputs and its
  guard log are in `outputs/framelease_v4/analysis/final_20261117T161912` (`SHA256SUMS` sha256
  `898b77802f77e0d26e71fa91617fb11bc855d3b134cf78e7b9a16e9b07b745e5`);
  `outputs/framelease_v4/analysis/final_20261117T161912/required_job_files.json` (sha256
  `f58321692f998d7e33f713aee2f212f54f8e7699babc0f13310bcfdb71521d6d`) lists the six queue copies at their G6 sha256 (the
  --required-job-files of the analysis).
* First analysis freeze. The record of Amendment A13
  (`outputs/framelease_v4/analysis/final_20261116T091445/analysis_freeze.json`, sha256
  `fdda348027092724f74bf10cf0b5e33ed3219ffbfe5cfe6a57ac8aa9e4bd7c05`) stays valid and unchanged, as do its outputs in
  `outputs/framelease_v4/analysis/final_20261116T091445` and `outputs/framelease_v4/verification/final_20261116T091445*`
  (every `SHA256SUMS` there verifies). It holds the 505 jobs of Amendment A17 as cut and releases none of their runs.
  Every result in the paper names the analysis it comes from (Amendment A17).
* Validity. The record is valid from this entry on (its sha256 in Sec. 13 of the sealed PROTOCOL.md,
  `interim_guard.load_freeze`). The confirmatory analysis (Amendments A3 and A10) writes its outputs into directories
  inside `outputs/framelease_v4/analysis/final_20261117T161912`, each with its sha256 manifest; the independent
  verifications (Amendment A10, use rule 4; Amendment A11 with the resolution rule of Amendment A16) read the released
  aggregation `outputs/framelease_v4/analysis/final_20261117T161912/agg_p4` (Amendment A16, "Aggregation path"). The
  phase driver stays stopped (`outputs/framelease_v4/phase_driver/STOP`, Amendments A12 and A17): this entry takes the
  place of its G8 entry.
* Manifest and seal after this entry: `MANIFEST.sha256`, 221 files, sha256
  `0fdb720ea103b891218cf538960a8fb93f9f8d46dcef59c421716c0c6137dca3`, sealed with this entry.

**Amendment A19, 2026-11-17 16:23 (Beijing time): result of the independent verification of H1 and of the Table I
columns DS, SR, RC, collisions/km and infractions/km on the second analysis freeze (Amendment A18; Sec. 9.12; Amendment
A10, use rule 4); no run, job line, criterion or analysis rule changes.**
* Run. An independent session ran `framelease_v4/analysis/verify_independent.py` (sha256
  `4935152684abcfdaef547438772bb041f323344dcbfe636d41b2a161ff149bff`) after the analysis freeze of Amendment A18, with
  the record `outputs/framelease_v4/analysis/final_20261117T161912/analysis_freeze.json`, the released aggregation
  `outputs/framelease_v4/analysis/final_20261117T161912/agg_p4`, the analysis
  `outputs/framelease_v4/analysis/final_20261117T161912/analysis` and `--queue outputs/framelease_v4/queue_p4`, into
  `outputs/framelease_v4/verification/final_20261117T161912`.
* Result. `outputs/framelease_v4/verification/final_20261117T161912/verification.json` (sha256
  `6857ed6f4690401c74f57025430e985bb8721d25d610999636b6af1959a6cbf9`): status final, verdict AGREE, differences 0;
  `SHA256SUMS` sha256 `7899238ed0571459fcb283a5c0528bf9b0e65bea830c2af2f4d7a61e6ae2fa2e`. AGREE releases H1 and its
  findings and the verified Table I columns of this analysis (use rule 4).
* Manifest and seal after this entry: `MANIFEST.sha256`, 221 files, sha256
  `0fdb720ea103b891218cf538960a8fb93f9f8d46dcef59c421716c0c6137dca3`, sealed with this entry.

**Amendment A20, 2026-11-17 16:23 (Beijing time): result of the independent recomputation of the Table I columns GPU
usage, DMR, action age, fallback ratio, EIR and P_both and of the closed-loop R_cond on the second analysis freeze
(Amendment A18; Sec. 9.12; Amendment A11, use rules 1-3); no run, job line, criterion or analysis rule changes.**
* Run. An independent session ran `framelease_v4/analysis/verify_table1_extra.py` (sha256
  `f77b2dcf34484d2537a4c22d804912f0c155c3e3c26a576f433b9f4f73d83c27`) after the analysis freeze of Amendment A18, with
  the record, `--queue outputs/framelease_v4/queue_p4`, the released aggregation
  `outputs/framelease_v4/analysis/final_20261117T161912/agg_p4` and the analysis
  `outputs/framelease_v4/analysis/final_20261117T161912/analysis`, into
  `outputs/framelease_v4/verification/final_20261117T161912_table1_extra`, and the class report
  `outputs/framelease_v4/build/AMEND2/a10r7b/f1/f1_class_report.py` (sha256
  `ac82d65a9f4507a779dce5632e166b79e9d4c8d83f6c2b014ca27561e29145b6`) on that directory.
* Result. `outputs/framelease_v4/verification/final_20261117T161912_table1_extra/table1_extra.json` (sha256
  `4b183daab079f3469f56bafd0ff0f53b35fdb1529eb06b693163a13b88d228f5`): status final, verdict DIFFER; `SHA256SUMS` sha256
  `e5bb585543574d421523710a39fcfa60e1273592963e590945c7d6c79f1f28d9`; class report
  `outputs/framelease_v4/verification/final_20261117T161912_table1_extra_f1_class.json` (sha256
  `429d9d541401c0f1c809e3068f029b94ffcb3808b6b6c9176800b2508fcacc26`): outcome verification failure, release
  verification failure; differences per class: F1 0, F3 0, in-flight 0, not-ok record 81, undefined-metric pairing 304,
  unexplained 121.
* Use. A difference without a pre-specified class is a verification failure: each such difference is resolved and its
  cause entered in Sec. 13 before any of these numbers enters the paper (use rule 2; Amendment A10, use rule 4); for
  pairing-status rows of the closed-loop R_cond the resolution rule of Amendment A16 applies (Amendment A17).
* Manifest and seal after this entry: `MANIFEST.sha256`, 221 files, sha256
  `0fdb720ea103b891218cf538960a8fb93f9f8d46dcef59c421716c0c6137dca3`, sealed with this entry.

**Amendment A21, 2026-11-17 16:23 (Beijing time): resolution of the 121 differences outside the classes of Amendment A11
in the recomputation of Amendment A20, by the resolution rule of Amendment A16 (Amendment A17); no run, job line,
criterion or analysis rule changes.**
* Differences. The class report of Amendment A20
  (`outputs/framelease_v4/verification/final_20261117T161912_table1_extra_f1_class.json`, sha256
  `429d9d541401c0f1c809e3068f029b94ffcb3808b6b6c9176800b2508fcacc26`) reads "verification failure" with 121 differences
  outside the five classes of Amendment A11 (121 in the analysis scope). All 121 are status rows of the paired
  differences of the secondary metric closed-loop R_cond: the analysis records the route as missing for that metric
  ("realized_r_cond missing: <conditions>"), the recomputation records it as paired. No row holds a value, a difference
  or a different n on either side, and no per-run comparison of R_cond, conflict plans or misses differs for the cells
  of these pairs. For every condition that the analysis names, R_cond is undefined (no conflict plan, 0/0) both in the
  registered aggregation (`outputs/framelease_v4/analysis/final_20261117T161912/agg_p4/runs.csv`, sha256
  `8d095d06dd6f9075876a04262eebda0e68bb6a251c31ca40eec893203831ed82`) and in the recomputation
  (`outputs/framelease_v4/verification/final_20261117T161912_table1_extra/runs_recomputed.csv`, sha256
  `cd658cf9cd14844f1942f3ee642961db889f34154a6e45b298f2eec3c81184f0`). The analysis drops such a route from the contrast
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
  `a371a37b2165c46f0a70681f9bbe3d9ce40406d291c7dad7679dad1703533f66`) and
  `outputs/framelease_v4/analysis/final_20261117T161912/analysis/paired_differences.csv` (sha256
  `0b788578736ee07af67f272ec9add704622eb15b741501753197e11eecae0ea8`).
* Resolution (Amendment A10, use rule 4; Amendment A11, use rule 2; Amendment A16). The differences have the cause that
  Amendment A16 resolved for the cut analysis, and no numeric value disagrees. The class report stays as computed and is
  reported as "verification failure" with this cause. With the cause entered here, the columns of Table I that Amendment
  A11 covers (GPU usage, DMR, action age p50 and p95, fallback ratio, EIR, P_both) and the closed-loop R_cond of this
  analysis enter the paper with their registered values, stated together with the size of every class: F1 0 differences
  (0 in the analysis scope), F3 0 (0 in the analysis scope), in-flight 0 (0 in the analysis scope), not-ok record 81
  (jobs `v4p4_fl_original_k1.0_s11_r23658`, `v4p5_fl_full_B0_d1_v4_qnet_5d8ffd7cf7dd_k2.0_s11_r1711`), undefined-metric
  pairing 304, and the 121 above.
* Manifest and seal after this entry: `MANIFEST.sha256`, 221 files, sha256
  `0fdb720ea103b891218cf538960a8fb93f9f8d46dcef59c421716c0c6137dca3`, sealed with this entry.

