**Amendment A15, {{datetime}} (Beijing time): result of the independent recomputation of the Table I columns GPU
usage, DMR, action age, fallback ratio, EIR and P_both and of the closed-loop R_cond (Sec. 9.12; Amendment A11, use
rules 1-3); no run, job line, criterion or analysis rule changes.**
* Run. An independent session ran `framelease_v4/analysis/verify_table1_extra.py` (sha256
  `f77b2dcf34484d2537a4c22d804912f0c155c3e3c26a576f433b9f4f73d83c27`) after the analysis freeze, with the record,
  `--queue outputs/framelease_v4/queue_p4`, the released aggregation and the analysis, into
  `outputs/framelease_v4/verification/final_20261116T002530_table1_extra`, and the class report
  `outputs/framelease_v4/build/AMEND2/a10r7b/f1/f1_class_report.py` (sha256
  `5fa8fa171e1677e87b4b0d48155402ca794104f19b6aeacfedf17de3a84e33ac`) on that directory.
* Result. `outputs/framelease_v4/verification/final_20261116T002530_table1_extra/table1_extra.json` (sha256
  `{{sha256:outputs/framelease_v4/verification/final_20261116T002530_table1_extra/table1_extra.json}}`): status final, verdict DIFFER; `SHA256SUMS` sha256
  `{{sha256:outputs/framelease_v4/verification/final_20261116T002530_table1_extra/SHA256SUMS}}`; class report
  `outputs/framelease_v4/verification/final_20261116T002530_table1_extra_f1_class.json` (sha256
  `{{sha256:outputs/framelease_v4/verification/final_20261116T002530_table1_extra_f1_class.json}}`): outcome verification failure, release
  verification failure; differences per class: none.
* Use (Amendment A11, use rule 2): AGREE, or every difference in a pre-specified class, releases these columns with the
  registered values, and the paper states each class, its cause and its size; any other difference is resolved and its
  cause entered in Sec. 13 before any of these numbers enters the paper.
* Manifest and seal after this entry: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.
