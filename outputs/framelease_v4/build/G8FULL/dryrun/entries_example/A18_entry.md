**Amendment A18, {{datetime}} (Beijing time): the second analysis freeze (Sec. 9.12) under Amendment A17, all
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
  `{{sha256:outputs/framelease_v4/analysis/final_20261117T161912/analysis_freeze.json}}`; trigger all_final, no cut, frozen
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
  `{{sha256:outputs/framelease_v4/analysis/final_20261117T161912/SHA256SUMS}}`);
  `outputs/framelease_v4/analysis/final_20261117T161912/required_job_files.json` (sha256
  `{{sha256:outputs/framelease_v4/analysis/final_20261117T161912/required_job_files.json}}`) lists the six queue copies at their G6 sha256 (the
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
* Manifest and seal after this entry: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.
