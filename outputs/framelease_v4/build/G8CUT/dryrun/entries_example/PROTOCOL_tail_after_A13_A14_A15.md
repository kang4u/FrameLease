**Amendment A13, 2026-11-16 00:25 (Beijing time): the analysis freeze (Sec. 9.12) under the cut of Amendment A12,
carried out by the coordinating session with the registered tools in place of gate G8 of the phase driver; no run, job
line, criterion or analysis rule changes.**
* Freeze. Every job that Amendment A12 keeps in tiers 3-6 was final and the runner of `outputs/framelease_v4/queue_p4`
  had exited (last runner exit 2026-11-16T07:30:00Z). `aggregate_v4.py --queue outputs/framelease_v4/queue_p4 --specs
  outputs/framelease_v4/test_jobs/FULL --rl-freeze outputs/framelease_v4/rl_freeze/rl_freeze.json --tuning-freeze
  outputs/framelease_v4/tuning/selection.json --write-freeze-record
  outputs/framelease_v4/analysis/final_20261116T002530/analysis_freeze.json --cut-amendment A12` wrote
  `outputs/framelease_v4/analysis/final_20261116T002530/analysis_freeze.json` (sha256
  `e9c25c744bc2b11479f15c698671ec3bd8bd0cbb682dc454fbd6e964031e5fd9`; trigger cut, cut amendment A12, frozen
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
  `e3bb27afdafad46afb9c059c0c4d0bd4b0dbc1d5a4f2e2a7ce45b0d3638bd9bb`);
  `outputs/framelease_v4/analysis/final_20261116T002530/required_job_files.json` (sha256
  `f58321692f998d7e33f713aee2f212f54f8e7699babc0f13310bcfdb71521d6d`) lists the six queue copies at their G6 sha256 (the
  --required-job-files of the analysis).
* Validity. The record is valid from this entry on (its sha256 in Sec. 13 of the sealed PROTOCOL.md,
  `interim_guard.load_freeze`). The confirmatory analysis (Amendments A3 and A10) writes its outputs into directories
  inside `outputs/framelease_v4/analysis/final_20261116T002530`, each with its sha256 manifest. The phase driver stays
  stopped (`outputs/framelease_v4/phase_driver/STOP`, Amendment A12): this entry takes the place of its G8 entry.
* Manifest and seal after this entry: `MANIFEST.sha256`, 221 files, sha256
  `0fdb720ea103b891218cf538960a8fb93f9f8d46dcef59c421716c0c6137dca3`, sealed with this entry.

**Amendment A14, 2026-11-16 00:27 (Beijing time): result of the independent verification of H1 and of the Table I
columns DS, SR, RC, collisions/km and infractions/km (Sec. 9.12; Amendment A10, use rule 4); no run, job line, criterion
or analysis rule changes.**
* Run. An independent session ran `framelease_v4/analysis/verify_independent.py` (sha256
  `4935152684abcfdaef547438772bb041f323344dcbfe636d41b2a161ff149bff`) after the analysis freeze, with the record, the
  released aggregation, the analysis and `--queue outputs/framelease_v4/queue_p4`, into
  `outputs/framelease_v4/verification/final_20261116T002530`.
* Result. `outputs/framelease_v4/verification/final_20261116T002530/verification.json` (sha256
  `49cd2b856f19aded6dd1ab9831a67640247ae7c88b1cd7675d76ac3cd64eb89b`): status final, verdict AGREE, differences 0;
  `SHA256SUMS` sha256 `dd443b60be0cbb71218941983e3d493870d9dbe176c68049b95af11e4243bb3b`. AGREE releases H1 and its
  findings and the verified Table I columns (use rule 4).
* Manifest and seal after this entry: `MANIFEST.sha256`, 221 files, sha256
  `0fdb720ea103b891218cf538960a8fb93f9f8d46dcef59c421716c0c6137dca3`, sealed with this entry.

**Amendment A15, 2026-11-16 00:27 (Beijing time): result of the independent recomputation of the Table I columns GPU
usage, DMR, action age, fallback ratio, EIR and P_both and of the closed-loop R_cond (Sec. 9.12; Amendment A11, use
rules 1-3); no run, job line, criterion or analysis rule changes.**
* Run. An independent session ran `framelease_v4/analysis/verify_table1_extra.py` (sha256
  `f77b2dcf34484d2537a4c22d804912f0c155c3e3c26a576f433b9f4f73d83c27`) after the analysis freeze, with the record,
  `--queue outputs/framelease_v4/queue_p4`, the released aggregation and the analysis, into
  `outputs/framelease_v4/verification/final_20261116T002530_table1_extra`, and the class report
  `outputs/framelease_v4/build/AMEND2/a10r7b/f1/f1_class_report.py` (sha256
  `5fa8fa171e1677e87b4b0d48155402ca794104f19b6aeacfedf17de3a84e33ac`) on that directory.
* Result. `outputs/framelease_v4/verification/final_20261116T002530_table1_extra/table1_extra.json` (sha256
  `190a0e4bd91c229fa9943111fbcf1842baf1eba3b643d5fafa7915bfb32d97ca`): status final, verdict DIFFER; `SHA256SUMS` sha256
  `b54e95353f8590223d5e1d4c89c0ae059089faee122b81be5a1a57292a576730`; class report
  `outputs/framelease_v4/verification/final_20261116T002530_table1_extra_f1_class.json` (sha256
  `b975dcfac8995d4eaa962b5155428f60fdec6244ea8c265b90c1bb80eb3a2a6f`): outcome verification failure, release
  verification failure; differences per class: none.
* Use (Amendment A11, use rule 2): AGREE, or every difference in a pre-specified class, releases these columns with the
  registered values, and the paper states each class, its cause and its size; any other difference is resolved and its
  cause entered in Sec. 13 before any of these numbers enters the paper.
* Manifest and seal after this entry: `MANIFEST.sha256`, 221 files, sha256
  `0fdb720ea103b891218cf538960a8fb93f9f8d46dcef59c421716c0c6137dca3`, sealed with this entry.

