**Amendment A14, {{datetime}} (Beijing time): result of the independent verification of H1 and of the Table I
columns DS, SR, RC, collisions/km and infractions/km (Sec. 9.12; Amendment A10, use rule 4); no run, job line, criterion
or analysis rule changes.**
* Run. An independent session ran `framelease_v4/analysis/verify_independent.py` (sha256
  `4935152684abcfdaef547438772bb041f323344dcbfe636d41b2a161ff149bff`) after the analysis freeze, with the record, the
  released aggregation, the analysis and `--queue outputs/framelease_v4/queue_p4`, into
  `outputs/framelease_v4/verification/final_20261116T002530`.
* Result. `outputs/framelease_v4/verification/final_20261116T002530/verification.json` (sha256
  `{{sha256:outputs/framelease_v4/verification/final_20261116T002530/verification.json}}`): status final, verdict AGREE, differences 0;
  `SHA256SUMS` sha256 `{{sha256:outputs/framelease_v4/verification/final_20261116T002530/SHA256SUMS}}`. AGREE releases H1 and its
  findings and the verified Table I columns (use rule 4).
* Manifest and seal after this entry: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.
