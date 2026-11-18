**Amendment A13, {{datetime}} (Beijing time): the analysis freeze (Sec. 9.12) under the cut of Amendment A12,
carried out by the coordinating session with the registered tools in place of gate G8 of the phase driver; no run, job
line, criterion or analysis rule changes.**
* Freeze. Every job that Amendment A12 keeps in tiers 3-6 was final and the runner of `outputs/framelease_v4/queue_p4`
  had exited (last runner exit 2026-11-16T07:30:00Z). `aggregate_v4.py --queue outputs/framelease_v4/queue_p4 --specs
  outputs/framelease_v4/test_jobs/FULL --rl-freeze outputs/framelease_v4/rl_freeze/rl_freeze.json --tuning-freeze
  outputs/framelease_v4/tuning/selection.json --write-freeze-record
  outputs/framelease_v4/analysis/final_20261116T002530/analysis_freeze.json --cut-amendment A12` wrote
  `outputs/framelease_v4/analysis/final_20261116T002530/analysis_freeze.json` (sha256
  `{{sha256:outputs/framelease_v4/analysis/final_20261116T002530/analysis_freeze.json}}`; trigger cut, cut amendment A12, frozen
  2026-11-16T00:25:36+0800).
* Job status: 632 jobs of the 6 job files of the test freeze (entry "G6 Test freeze", record
  `outputs/framelease_v4/test_freeze/test_freeze.json` sha256
  `e9e2d309fefd49209d1303356328049f8c0e89534f1b0cfaffffea82ed1ba633`):
  `outputs/framelease_v4/queue_p4/jobs.d/b11_ti_main.jsonl` (tier 3, 98 of 308 lines kept, sha256
  `54e551df44f30a02277e91849f1e40390cd77ffca7e59256edc98b3f5cd4a6df`);
  `outputs/framelease_v4/queue_p4/jobs.d/b12_f3_k.jsonl` (tier 4, 16 of 176 lines kept, sha256
  `8ba8a4e5f6874860f9fefae81d836ccbdd297ac6a801a67663d6a5322507311b`);
  `outputs/framelease_v4/queue_p4/jobs.d/b13_a_lease.jsonl` (tier 5, 3 of 22 lines kept, sha256
  `6b906bc220d74fdf8fb5bfce287465e608fd378b22869af6d188ec411d37bd2a`);
  `outputs/framelease_v4/queue_p4/jobs.d/b14_a_rl.jsonl` (tier 5, 4 of 44 lines kept, sha256
  `a73491e47ab5cb3fcba868a0e5e6bf7f34c5ad6a09ea3fde8cd11d18ef623e31`);
  `outputs/framelease_v4/queue_p4/jobs.d/b15_s_seed12.jsonl` (tier 6, 4 of 60 lines kept, sha256
  `bd77e5ed172bc834b63a4fa188cae97f92047f8072a45b92e738aad52cffd207`);
  `outputs/framelease_v4/queue_p4/jobs.d/b16_s_risk.jsonl` (tier 6, 2 of 22 lines kept, sha256
  `83fe874f000340d6ee15509c35c7829bd03a6612a75a181e82c0b26ab36a156b`); outcomes ok 126, agent_crashed 0, sim_failure 1,
  cut 505. The 127 jobs kept by Amendment A12 are final (ok 126, agent_crashed 0, sim_failure 1); the 505 cut jobs have
  no runner record and no run directory and carry the outcome cut.
* Job files. The runner ran the kept jobs from the reduced job files of Amendment A12
  (`outputs/framelease_v4/cut_20261115T231415/jobs_reduced/`, byte-identical subsets). Once every kept job was final and
  the runner had exited, `outputs/framelease_v4/queue_p4/STOP` was written and the registered copies
  (`outputs/framelease_v4/cut_20261115T231415/jobs_registered/`) were put back into
  `outputs/framelease_v4/queue_p4/jobs.d`, so that the record covers the registered job files of the test freeze at
  their sha256 of the G6 entry; `test_freeze.py --verify` passed on them. The STOP file stays: no runner starts a cut
  job.
* Analysis code frozen by the record: `aggregate_v4.py` (sha256
  `ee13c90b91bf44ad59d0a3c7e60bf93d65964785ed386d3e81c44fea0f5e4b96`), `commit_audit.py` (sha256
  `7439a4eac0986cad6a25b7395975a0411b7483944a988d68dabb656bd2544ec7`), `extra_metrics.py` (sha256
  `53050f6bed5aa48054d5217832fb84ed4089b3ae80e8fdcf965769af2af79c4c`), `interim_guard.py` (sha256
  `5453a3573e7cca958cad1bc1c44d53995a11e034e251bba634fe09390efed9c7`), `manipulation.py` (sha256
  `78f18dacf323832ef16684b0b81a2ba03b2ffb00186259780d1bafe7e656cbd0`); the analysis script
  `framelease_v4/analysis/analyze_v4.py` (sha256 `10d7ea4f9516725cd94932a0618bbe5cc6a20bae60b49f4004013b3682cee54c`) is
  registered in Sec. 13.2 by Amendment A10 and `framelease_v4/analysis/verify_table1_extra.py` (sha256
  `f77b2dcf34484d2537a4c22d804912f0c155c3e3c26a576f433b9f4f73d83c27`) by Amendment A11. Route split sha256
  `555f6869cb62d89082efc0fefc8f125ee133b16fd36a6fcf9f68bb1269fa527e`.
* Interim looks (Sec. 9.11). The aggregation that made the record ran without --arm-summary and without
  --analysis-freeze: every test-route row stayed health-only and no cross-arm summary was made. Its outputs and its
  guard log are in `outputs/framelease_v4/analysis/final_20261116T002530` (`SHA256SUMS` sha256
  `{{sha256:outputs/framelease_v4/analysis/final_20261116T002530/SHA256SUMS}}`);
  `outputs/framelease_v4/analysis/final_20261116T002530/required_job_files.json` (sha256
  `{{sha256:outputs/framelease_v4/analysis/final_20261116T002530/required_job_files.json}}`) lists the six queue copies at their G6 sha256 (the
  --required-job-files of the analysis).
* Validity. The record is valid from this entry on (its sha256 in Sec. 13 of the sealed PROTOCOL.md,
  `interim_guard.load_freeze`). The confirmatory analysis (Amendments A3 and A10) writes its outputs into directories
  inside `outputs/framelease_v4/analysis/final_20261116T002530`, each with its sha256 manifest. The phase driver stays
  stopped (`outputs/framelease_v4/phase_driver/STOP`, Amendment A12): this entry takes the place of its G8 entry.
* Manifest and seal after this entry: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.
