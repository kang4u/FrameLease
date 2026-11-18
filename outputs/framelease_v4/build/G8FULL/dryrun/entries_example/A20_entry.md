**Amendment A20, {{datetime}} (Beijing time): result of the independent recomputation of the Table I columns GPU
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
  `{{sha256:outputs/framelease_v4/verification/final_20261117T161912_table1_extra/table1_extra.json}}`): status final, verdict DIFFER; `SHA256SUMS` sha256
  `{{sha256:outputs/framelease_v4/verification/final_20261117T161912_table1_extra/SHA256SUMS}}`; class report
  `outputs/framelease_v4/verification/final_20261117T161912_table1_extra_f1_class.json` (sha256
  `{{sha256:outputs/framelease_v4/verification/final_20261117T161912_table1_extra_f1_class.json}}`): outcome verification failure, release
  verification failure; differences per class: F1 0, F3 0, in-flight 0, not-ok record 81, undefined-metric pairing 304,
  unexplained 121.
* Use. A difference without a pre-specified class is a verification failure: each such difference is resolved and its
  cause entered in Sec. 13 before any of these numbers enters the paper (use rule 2; Amendment A10, use rule 4); for
  pairing-status rows of the closed-loop R_cond the resolution rule of Amendment A16 applies (Amendment A17).
* Manifest and seal after this entry: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.
