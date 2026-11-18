# DRYRUN: G8CUT sequence on a scratch tree with synthetic run directories

Run 2026-11-16 00:24:38-00:28:02 (Beijing time) by `dryrun/run_dryrun.sh`; every process
`taskset -c 12-15 nice -n 19 ionice -c 3`, one BLAS thread, no CUDA, one at a time; the largest resident set of any
step 164 MB (figures_tables.py). Step log: `dryrun/dryrun_steps.log`; per-tool log of the tree: `dryrun/tree_steps.log`;
entry texts: `dryrun/entries_example/`. No file under `outputs/framelease_v4/{matrix,fig3,ablation,replicates}/` of the
project was read, and no aggregation ran on the project's `queue_p4`.

## 1. The scratch tree (`dryrun/build_tree.py`)

`/tmp/G8CUT/root` is its own project root (42 MB in tmpfs): real copies of `framelease_v2/`, `framelease_v3/`,
`framelease_v4/` (no `__pycache__`), `framelease_common.py`, every registration-manifest file below 50 MB, and under
`outputs/framelease_v4/` the registered inputs (`registration/`, `protocol/`, `envelopes/`, `offline_ablation/`,
`p1_jobs/`, `p2_jobs/`, `rl_freeze/`, `stress/`, `test_jobs/`, `test_freeze/`, `cut_20261115T231415/`, `rl_dev/`,
`readiness_fixes/`, `paper_sources/`, the tuning freeze with `selection/` and `d1/`, the P2 data manifest and check, both
drivers' `registered_baseline.json`, `phase_driver/P4_QUEUED.json` and `STOP`). Everything else of the root and of
`outputs/` outside `outputs/framelease_v4` is a read-only link; nothing of `outputs/framelease_v4` is linked. The
tree's PROTOCOL.md, `MANIFEST.sha256` and `SEAL.sha256` equal the project's at the build; `registration.py --verify` in
the tree: "manifest: OK", both seals OK.

Tree adjustments (each exists only because the tree lies at another path; none changes a registered file of the tree):
* the appliers: `apply_entry_stream.py` with `ROOT` = the tree (the only changed line) and `apply_locked.sh` through its
  `APPLY_ROOT` / `APPLIER` variables (as `a10r7b/sim_tree.py` does); `f1_class_report.py` with its fixed `ROOT` line
  set to the tree (the stand-in A11 cites this copy);
* `p1_jobs.rel` resolves symbolic links, so a linked registered input fails the route-split check (aggregator exit 4,
  first build); the final tree copies every input that a tool looks up by its relative path;
* Amendment A11 is a STAND-IN (`dryrun/A11_standin_entry.md`: the two R7B files and `f1_class_report.py` by sha256),
  applied with the registered applier copy; the real A11 is finished by its own item;
* the P2 run directories that the P2 data manifest names are linked into the tree after the P2 aggregation
  (`build_tree.py --link-p2-sources`, 133 directories): `p3_rl.load_rl_freeze` hashes their logs when
  `figures_tables.py` reads the RL freeze (training-route runs, read for their sha256 only);
* the RL freeze names its networks by the project's absolute paths: in the tree `figures_tables.py --rl-freeze` refuses
  it (exit 2, "network abs_path ... != /tmp/G8CUT/root/..."); the tree's figures therefore ran once more without
  `--rl-freeze` and without `--require-registered` (`G8_TREE_FIGURES_NO_RL=1`, honoured only outside the project root).
  On the project, `p3_rl.load_rl_freeze(..., require_cited=True)` and `figures_tables.load_rl_freeze` accept the RL
  freeze with no development reason (read only, 1.9 s, 111 MB).

## 2. Synthetic data (`dryrun/make_runs.py`, built with the test helpers)

* `queue_p4`: `jobs.d` = byte copies of the six A12 reduced files; one synthetic run per kept job (127), the job
  `v4p4_fl_original_k1.0_s11_r23658` with two 'timeout' attempts without a result (as A12 records); stage `pending`
  leaves 3 kept jobs without a final record (one running), stage `final` adds a runner exit.
* `queue_p1`: byte copies of the project's `queue_p1/jobs.d` (271 lines: P1-0 smoke and P1) with one run each, and for
  `v4p1_fixed_deep_k1.0_s11_r28093` an interrupted first attempt whose run directory has no `jobs.jsonl` /
  `events.jsonl` (the mechanism of the 2026-11-11 pause); `queue_p2`: byte copy of `queue_p2/jobs.d` (132 lines).
* Run directories (532): `test_verify_independent.World.run` (official record, `metrics/result.json`, pins), the logs
  and actor-box log of `test_verify_table1_extra` (`write_jsonl`, `actor_row`, `write_actor_log`, `PLANS`,
  `DECISIONS` without the depth-0 row), every accepted commit in `jobs.jsonl` and `events.jsonl` with its validity
  record (commit audit PASS), the runtime summary from `test_verify_table1_extra.summary_from` on the recomputed logs,
  the runner records of `test_aggregate_v4.start` / `end` with `gpu_queue.Runner.closed_loop_result`. DS, RC and
  infractions are deterministic pseudo-random values per arm, route, kappa and seed; the job lines, routes, arms,
  networks and envelopes are the registered ones.

## 3. Steps and timings

| # | step | expected | exit | wall | result |
|---:|---|---:|---:|---:|---|
| 1 | build_tree | 0 | 0 | 0.4 s | tree built, seals equal the project's |
| 2 | synthetic data, stage pending | 0 | 0 | 6.9 s | 529 run directories |
| 3 | `g8_check.sh` on the pending queue | 3 | 3 | 3.4 s | NOT FINAL: 3 kept jobs open, no runner exit, A11 absent |
| 4 | synthetic data, stage final | 0 | 0 | 7.0 s | 532 run directories |
| 5 | `g8_check.sh` without A11 | 3 | 3 | 3.4 s | NOT FINAL: A11 absent, `verify_table1_extra.py` not cited |
| 6 | stand-in A11 through `apply_locked.sh` | 0 | 0 | 17.1 s | sealed; newly registered the two R7B files |
| 7 | `g8_check.sh` | 0 | 0 | 3.4 s | READY (reduced): 127 kept final, 505 cut without record |
| 8 | NEGATIVE: freeze aggregation on the reduced `jobs.d` | 2 | 2 | 0.2 s | "block specs disagree with the job lines" |
| 9 | `g8_swap.sh` | 0 | 0 | 3.7 s | STOP written, registered copies in `jobs.d`, `test_freeze.py --verify` OK |
| 10 | `g8_swap.sh` again | 0 | 0 | 3.7 s | "nothing to do" |
| 11 | `g8_freeze.sh` | 0 | 0 | 17.0 s | record: trigger cut / A12, 632 jobs = ok 126 + sim_failure 1 + cut 505; RECORD OK; A13 entry 58 lines; SIMULATE OK; applier check passed |
| 12 | `g8_apply.sh A13 <F>` | 0 | 0 | 21.5 s | wrapper exit 0, composed sha256 = the simulated one; POST OK (load_freeze registered, owner A13) |
| 13 | NEGATIVE: `analyze_v4.py` on the freeze aggregation | 2 | 2 | 0.5 s | "no column ['driving_score', 'collisions_per_km', 'dmr']" |
| 14 | `g8_analysis.sh A13` (P2 logs not in the tree) | 2 | 2 | 50.7 s | aggregations, analysis (registered, H5 contradicted), coverage done; figures: RL freeze source logs absent |
| 15 | link the P2 run directories | 0 | 0 | 0.0 s | 133 linked |
| 16 | `g8_analysis.sh A13`, the registered figures command | 2 | 2 | 5.1 s | tree-only refusal of the RL freeze paths |
| 17 | `g8_analysis.sh A13` with `G8_TREE_FIGURES_NO_RL=1` | 0 | 0 | 8.2 s | 7 items, 2573 numbers, only reason "no --rl-freeze"; 62 files in `ANALYSIS_OUTPUTS.sha256` |
| 18 | `g8_verify.sh A13` | 0 | 0 | 9.0 s | verify_independent AGREE; verify_table1_extra DIFFER (116); class report 'verification failure'; A14, A15 entry files |
| 19 | `g8_apply.sh A14` | 0 | 0 | 19.3 s | sealed |
| 20 | `g8_apply.sh A15` | 0 | 0 | 21.4 s | sealed |
| 21 | `registration.py --verify` in the tree | 0 | 0 | 3.1 s | manifest OK, both seals OK |

Tools inside the steps (wall time, max RSS): `g8_lib.py check` 0.15 s, 33 MB; aggregator (freeze) 6.0 s, 63 MB;
`record` 0.26 s; `entry` 0.26 s; `simulate` 0.20 s; applier check 6.6 s, 19 MB; `agg_p4` 7.4 s, 65 MB; `agg_p1`
10.3 s, 59 MB; `agg_p2` 7.9 s, 52 MB; `analyze_v4.py` 1.8 s, 128 MB; `prop1_coverage.py` 18.4 s, 117 MB;
`figures_tables.py` 4.6 s, 164 MB; `verify_independent.py` 1.5 s, 94 MB; `verify_table1_extra.py` 3.5 s, 103 MB;
`f1_class_report.py` 0.06 s, 26 MB.

## 4. Results that carry over to the real run

* The A12 command needs the registered job files in `jobs.d` (steps 8, 9, 11; RUNBOOK Sec. 1 item 1).
* The A13 entry composes, seals and parses as simulated; `interim_guard.load_freeze` accepts the record only after
  the seal (step 11 also checks that the registered PROTOCOL.md refuses it before).
* The analysis cannot read the freeze aggregation (step 13); `agg_p4` under the record, plus `agg_p1` and `agg_p2`,
  give a 'registered' analysis (step 14).
* H5: 'contradicted' with 0 violations and 0 S3 violations, from 1 unaudited NO_LOG run (the interrupted attempt).
* With so few routes no tool refuses or crashes. Analysis: H1 / S-coll / S-dmr / H2 n 14 of 44, H3 n 13, F3 n 2 of 22,
  H4-cl n 3 and 8 of 22, RL-abl n 2 of 22, noise floor and seed 12 n 1 of 15 (CI equal to the single value, Pearson r
  empty), 224 rows with dropped routes. Figures: every item renders; Table I values carry the "fewer than 44 routes"
  dagger and the notes list every cut route per contrast (840 "not_launched" entries in `table1.tex`); Fig. 3 joins
  kappa-1.0 means on 8 E routes with kappa-1.5 / 2.0 means on 2 routes; Table II-A closed-loop rows mix 8-, 3- and
  2-route means; Fig. 1 (c) shows kappa 1.5 / 2.0 per ability from 2 routes. Panel (c) of Fig. 3 sets the three
  per-kappa percentages close together (they touch at "45.7%" widths).
* `verify_independent.py`: AGREE, 5215 comparisons over 10 targets, 0 differences, with the 632 job lines of the
  registered files in `jobs.d` (the 505 cut lines included).
* `verify_table1_extra.py`: 116 differences = 40 in class `not_ok_record` (the timed-out job) + 76 'unexplained' rows,
  all `paired_differences.csv` 'status' of P_both for shield arms against arms without a shield (RUNBOOK Sec. 1 item 7,
  open point 1). The A15 example in `entries_example/` was generated before the per-class text was fixed; the fixed
  `g8_lib.py result-entry` writes "differences per class: F1 0, F3 0, in_flight 0, not_ok_record 40, unexplained 76"
  and the verification-failure sentence (checked on the same outputs).

## 5. Job-health check on the project (read only)

`bash outputs/framelease_v4/build/G8CUT/g8_check.sh` on the project at 2026-11-16 00:30: exit 3 NOT FINAL; 34 of 127
kept jobs final, runner 665278 alive and holding the lock, `jobs.d` at the reduced sha256, 0 cut lines with a runner
record, A11 not entered; `registration.py --verify` manifest OK and both seals OK. No outcome was read: the check counts
final records and reads runner start / exit records; the timing note of RUNBOOK Sec. 9 uses the end times and wall
times of the runner records only.
