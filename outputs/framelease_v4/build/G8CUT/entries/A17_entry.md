**Amendment A17, {{datetime}} (Beijing time): the 505 test jobs cut by Amendment A12 run now, by the user's
decision; their analysis gets its own freeze; the cut analysis of Amendments A13-A16 stays as frozen; no job line,
criterion or analysis rule changes.**
* Decision. On 2026-11-16 at about 15:35 the user asked to run the experiments that the cut of Amendment A12 left out.
  Amendment A12 ("Later runs") keeps the cut lines in the registered job files and states that running them is a new
  amendment with its own freeze and analysis. This is that amendment.
* Jobs. The six registered job files of the test freeze are in `outputs/framelease_v4/queue_p4/jobs.d` at their G6
  sha256 since the analysis freeze of Amendment A13: `b11_ti_main.jsonl`
  (`{{sha256:outputs/framelease_v4/queue_p4/jobs.d/b11_ti_main.jsonl}}`), `b12_f3_k.jsonl`
  (`{{sha256:outputs/framelease_v4/queue_p4/jobs.d/b12_f3_k.jsonl}}`), `b13_a_lease.jsonl`
  (`{{sha256:outputs/framelease_v4/queue_p4/jobs.d/b13_a_lease.jsonl}}`), `b14_a_rl.jsonl`
  (`{{sha256:outputs/framelease_v4/queue_p4/jobs.d/b14_a_rl.jsonl}}`), `b15_s_seed12.jsonl`
  (`{{sha256:outputs/framelease_v4/queue_p4/jobs.d/b15_s_seed12.jsonl}}`) and `b16_s_risk.jsonl`
  (`{{sha256:outputs/framelease_v4/queue_p4/jobs.d/b16_s_risk.jsonl}}`). The runner of `outputs/framelease_v4/queue_p4`
  is launched again on them (`launch_queue.sh` in its own user scope with OOMPolicy=continue, as Amendment A12
  states); it skips every job with a final record, so the 127 jobs kept by Amendment A12 do not run again (126 ok and
  the timeout of `v4p4_fl_original_k1.0_s11_r23658`, final after its registered retry), and the 505 cut jobs run in
  the registered order of the files: Table I 210, Fig. 3 160, Table II-A lease panel 19 and RL panel 40, seed-12
  replicates 56, `fl_risk` 20. The `STOP` file that the analysis freeze wrote into the queue is moved aside for this
  launch. The phase driver stays stopped (`phase_driver/STOP`); its gates G7 and G8 are carried out by the coordinating
  session with the registered tools, as under Amendment A12.
* Interim looks. The results on the 14 routes of Amendment A12 are frozen, verified and known (Amendments A13-A16).
  For the runs of this amendment, Sec. 9.11 applies anew: before their analysis freeze only job health, timing and disk
  are examined, and no result of a new run is summarized across arms.
* Freeze and analysis. When every job of the six files is final and the runner has exited, a second analysis-freeze
  record is written by `aggregate_v4.py --write-freeze-record` (trigger all_final, no cut) into a new
  `outputs/framelease_v4/analysis/final_<stamp>/`, entered by its sha256 in a dated Sec. 13 entry; the registered
  analysis (Amendments A3, A10) and the independent verifications (Amendment A10 use rule 4, Amendment A11 with the
  resolution rule of Amendment A16) follow, each result in its own dated entry. The cut analysis
  (`outputs/framelease_v4/analysis/final_20261116T091445/analysis_freeze.json`,
  `{{sha256:outputs/framelease_v4/analysis/final_20261116T091445/analysis_freeze.json}}`) and its outputs stay
  unchanged; the paper states which analysis every result comes from.
* Manifest and seal after this amendment: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.
