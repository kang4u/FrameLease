**Amendment A12, {{datetime}} (Beijing time): cut of the test blocks P4-P6 by the user's decision (Sec. 10.2): Table
I runs on 14 of the 44 test routes and every other block on its first routes among those 14; no criterion, arm, job
line or analysis rule changes.**
* Decision. On 2026-11-15 at about 23:05 the user asked to shorten the test phase so that the results and a complete
  paper exist in about 11 to 12 hours, by reducing every block rather than whole tiers, and chose 14 routes for
  Table I. The measured rate at the decision was 28 of the 308 Table I jobs final after 2 h 20 min (one of them a
  1500 s timeout twice), so the registered P4-P6 plan of 632 jobs needed about three days. The cut depends on run
  time only. No test-route outcome was examined: the runner's END lines were read for job health only and never
  summarized (Sec. 9.11).
* Departure from Sec. 10.2. Sec. 10.2 cuts tiers from the bottom and never cuts tier 3 (Table I). This cut reduces
  every tier, Table I included, by the user's decision. The registered analysis applies unchanged to the jobs that
  remain; the paper reports every result with its number of routes and labels the reduced blocks.
* Rule. S = the first 14 routes of the registered order of `outputs/framelease_v4/test_jobs/FULL/b11_ti_main.jsonl`:
  26458, 2790, 23658, 2390, 2084, 2204, 2115, 2050, 3248, 17563, 3464, 2509, 2286, 3561. Each other block keeps its
  first k routes, in its own registered order, among the routes of S. The kept job lines are byte-identical to the
  registered ones.

  | block | routes kept | jobs kept / registered |
  |---|---|---|
  | `b11_ti_main` (tier 3, Table I) | the 14 routes of S | 98 / 308 |
  | `b12_f3_k` (tier 4, Fig. 3, kappa 1.5 and 2.0) | 3248, 2390 | 16 / 176 |
  | `b13_a_lease` (tier 5, Table II-A lease panel) | 2050, 2204, 2286 | 3 / 22 |
  | `b14_a_rl` (tier 5, Table II-A RL panel) | 3248, 2509 | 4 / 44 |
  | `b15_s_seed12` (tier 6, seed-12 replicates) | 2050 | 4 / 60 |
  | `b16_s_risk` (tier 6, `fl_risk`) | 2286, 3248 | 2 / 22 |

  127 of the 632 registered jobs remain; the other 505 never start and carry the outcome "cut" in the analysis-freeze
  record. The plan with the kept routes per block: `outputs/framelease_v4/cut_20261115T231415/CUT_PLAN.json`
  (`{{sha256:outputs/framelease_v4/cut_20261115T231415/CUT_PLAN.json}}`).
* Job status at the cutoff. 29 jobs of `b11_ti_main` final (28 ok; `v4p4_fl_original_k1.0_s11_r23658` timeout after
  two attempts), the last of them `v4p4_fl_original_k1.0_s11_r2084`, which was running when the cut was decided; all
  of them on routes of S. No job of tiers 4-6 had started.
* Execution. The registered job files in `outputs/framelease_v4/test_jobs/FULL/` stay unchanged (their sha256 as the
  G6 entry cites). The runner of `outputs/framelease_v4/queue_p4` stopped after its running job and runs the reduced
  files, each a byte-identical subset of the registered file, kept in `outputs/framelease_v4/cut_20261115T231415/`:
  `jobs_reduced/b11_ti_main.jsonl` (`{{sha256:outputs/framelease_v4/cut_20261115T231415/jobs_reduced/b11_ti_main.jsonl}}`),
  `b12_f3_k.jsonl` (`{{sha256:outputs/framelease_v4/cut_20261115T231415/jobs_reduced/b12_f3_k.jsonl}}`),
  `b13_a_lease.jsonl` (`{{sha256:outputs/framelease_v4/cut_20261115T231415/jobs_reduced/b13_a_lease.jsonl}}`),
  `b14_a_rl.jsonl` (`{{sha256:outputs/framelease_v4/cut_20261115T231415/jobs_reduced/b14_a_rl.jsonl}}`),
  `b15_s_seed12.jsonl` (`{{sha256:outputs/framelease_v4/cut_20261115T231415/jobs_reduced/b15_s_seed12.jsonl}}`) and
  `b16_s_risk.jsonl` (`{{sha256:outputs/framelease_v4/cut_20261115T231415/jobs_reduced/b16_s_risk.jsonl}}`); the
  registered copies that `jobs.d` held are kept in `jobs_registered/`. The phase driver is stopped, because its G7
  requires the registered copies in `jobs.d`. When every kept job is final, the coordinating session carries out G8
  with the registered tools: `aggregate_v4.py --queue outputs/framelease_v4/queue_p4 --specs
  outputs/framelease_v4/test_jobs/FULL --write-freeze-record <record> --cut-amendment A12` (the job lines that never
  started are recorded as cut), the record entered by its sha256 as a dated Sec. 13 entry, then the registered
  analysis (Amendments A3 and A10).
* Later runs. The cut jobs keep their lines in the registered files. Running them later is a new amendment with its
  own freeze and analysis; the analysis under this cut stays as frozen.
* Manifest and seal after this amendment: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.
