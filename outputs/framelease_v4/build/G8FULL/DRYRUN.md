# DRYRUN: G8FULL sequence on a scratch tree with synthetic run directories and the first freeze entered

Run by `dryrun/run_dryrun.sh` (times below); every process pinned to cores 12-15 at nice 19 and idle IO priority (the
driving shell pins itself, every child inherits; the tools also run under `taskset -c 12-15 nice -n 19 ionice -c 3`),
one BLAS thread, no CUDA, one at a time. Step log: `dryrun/dryrun_steps.log`; per-tool log of the tree:
`dryrun/tree_steps.log`; entry texts: `dryrun/entries_example/`. No file under
`outputs/framelease_v4/{matrix,fig3,ablation,replicates}/` of the project was read, no aggregation ran on the project's
`queue_p4`, and nothing of the project was written outside `outputs/framelease_v4/build/G8FULL/`.

## 1. The scratch tree (`dryrun/build_tree.py`)

`/tmp/G8FULL/root` is its own project root (43 MB in tmpfs), built as the G8CUT tree (`G8CUT/dryrun/build_tree.py`,
unchanged there): real copies of `framelease_v2/`, `framelease_v3/`, `framelease_v4/` (no `__pycache__`),
`framelease_common.py`, every registration-manifest file below 50 MB and the registered inputs under
`outputs/framelease_v4/` (`registration/`, `protocol/`, `envelopes/`, `offline_ablation/`, `p1_jobs/`, `p2_jobs/`,
`rl_freeze/`, `stress/`, `test_jobs/`, `test_freeze/`, `cut_20261115T231415/`, `rl_dev/`, `readiness_fixes/`,
`paper_sources/`, the tuning freeze, the P2 data manifest and check, both drivers' `registered_baseline.json`,
`phase_driver/P4_QUEUED.json` and `STOP`). Everything else of the root and of `outputs/` outside
`outputs/framelease_v4` is a read-only link; nothing of `outputs/framelease_v4` is linked.

The first freeze is entered in the tree:
* PROTOCOL.md is the project's (Amendments A1-A17, A13-A17 included); `MANIFEST.sha256` and `SEAL.sha256` equal the
  project's; `registration.py --verify` in the tree: "manifest: OK", both seals OK.
* `analysis/final_20261116T091445/` holds byte copies of its six top-level files (`analysis_freeze.json` at `fdda3480...`,
  `required_job_files.json`, `SHA256SUMS` and the health-only freeze aggregation it lists, `runs.csv` and
  `aggregate.json`, and `interim_guard.jsonl`). They carry job status only: every test-route row of that aggregation
  is health-only (Sec. 9.11; Amendment A13), the record lists job files, outcomes and run-directory names.
* The synthetic stage `cut` creates the 127 runs of the first record in exactly the run directories it names, so that
  the copied record releases them in the tree; the first analysis (`agg_p4`, `agg_p1`, `agg_p2`, `analysis`,
  `coverage`, `figures`, `ANALYSIS_OUTPUTS.sha256` with its temporary-file line) is then made by the G8CUT script
  `g8_analysis.sh A13` itself, and the first verifications (`verification/final_20261116T091445*`) by the registered
  verifiers and the class report. These result files are synthetic stand-ins: their sha256 differ from the values
  A14-A16 cite.

Tree adjustments (each exists only because the tree lies at another path or holds synthetic data; none changes a
registered file of the tree):
* the appliers: `apply_entry_stream.py` with `ROOT` = the tree (the only changed line) and `apply_locked.sh` through
  `APPLY_ROOT` / `APPLIER` (the wrapper takes the tree's `framelease_v4/.protocol.lock`, never the project's);
* `f1_class_report.py` with its fixed `ROOT` line set to the tree (its inputs are recorded with relative paths);
  `g8f_lib.py` compares its sha256 with the project's line restored (`f1-ok`: "tree copy, ROOT line restored");
* `G8F_TREE_STANDIN=1`, honoured only outside the project root: `g8f_lib.py first` does not compare the A14-A16 result
  files of the first freeze with their cited sha256 (they are stand-ins) and still requires them present, every
  `SHA256SUMS` there to hold and the job-status files of A13 at their cited sha256;
* `G8_TREE_FIGURES_NO_RL=1`, honoured only outside the project root (as in the G8CUT dry run): the RL freeze names its
  networks by the project's absolute paths, so `figures_tables.py --rl-freeze` refuses it in the tree; the tree's
  figures run without `--rl-freeze` / `--require-registered` (status 'development', reason "no --rl-freeze"). On the
  project the RL freeze is accepted (G8CUT DRYRUN Sec. 1; the first freeze's figures ran with it, status registered);
* the P2 run directories named by the P2 data manifest are linked into the tree (`build_tree.py --link-p2-sources`,
  133 training-route directories, read by `p3_rl.load_rl_freeze` for their sha256 only).

## 2. Synthetic data (`dryrun/make_runs.py`)

The run generators of the G8CUT dry run (the test helpers `test_verify_independent.World.run`,
`test_verify_table1_extra` logs and actor-box log, `test_aggregate_v4` runner records, `gpu_queue.Runner
.closed_loop_result`), with the job lines of the six registered job files; DS, RC and infractions deterministic
pseudo-random per arm, route, kappa and seed. Stages, after the project's timeline:
* `cut`: `queue_p4` as after the first freeze (registered job files in `jobs.d`, `queue_p4/STOP`); the 127 jobs final
  in the first record with runs in the recorded directories (126 ok; `v4p4_fl_original_k1.0_s11_r23658` timed out
  twice, the second attempt in its recorded directory); runner start / exit as recorded (exit
  2026-11-16T01:12:24Z); the 505 cut lines without a record. `queue_p1` (P1-0 and P1, with the log-less interrupted
  attempt of `v4p1_fixed_deep_k1.0_s11_r28093`) and `queue_p2` as in the G8CUT dry run.
* `a17_pending`: `STOP` moved aside (`STOP.20261116T155423.a17_resume.resolved.txt`), runner start
  2026-11-16T07:54:23Z, the 505 lines in the registered order; after 169 of them the pause (the next attempt
  interrupted, not counted, its run directory with logs and no result; runner exit by signal 15), runner start
  2026-11-17T07:06:29Z; one new job (`v4p5_fl_full_B0_d1_v4_qnet_5d8ffd7cf7dd_k2.0_s11_r1711`) times out twice and
  ends as sim_failure; the last 3 lines open (the first started), no runner exit.
* `a17_final`: the 3 open jobs end ok; runner exit ("queue empty").
* In about 12% of the runs the scenario vehicle stands 665 m ahead: no committed plan is a conflict plan and the
  closed-loop R_cond is undefined (0/0), the mechanism of Amendment A16.

## 3. Steps and timings (dry run 3, 2026-11-17 16:16:56-16:24:05, 430 s)

| # | step | expected | exit | wall | result |
|---:|---|---:|---:|---:|---|
| 1 | build_tree | 0 | 0 | 0.6 s | tree built; PROTOCOL.md (A13-A17), seals and the first record's files equal the project's |
| 2 | synthetic_cut | 0 | 0 | 6.6 s | 127 runs in the recorded directories, 505 cut lines without record, STOP; P1, P2 queues |
| 3 | link_p2_sources | 0 | 0 | 0.0 s | 133 P2 training-route directories linked |
| 4 | first_analysis_standin (G8CUT `g8_analysis.sh A13`) | 0 | 0 | 68.5 s | POST OK on the copied first record; 62-line list with the `.tmp` line, as A16 correction 2 |
| 5 | first_verification_standin | 0 | 0 | 5.0 s | AGREE; DIFFER; class report: 21 unexplained R_cond rows |
| 6 | synthetic_a17_pending | 0 | 0 | 6.2 s | 502 of 505 new final, pause attempt, one double timeout, 3 open |
| 7 | `g8f_check.sh` | 3 | 3 | 3.5 s | NOT FINAL: 3 lines open, no runner exit after the last start |
| 8 | synthetic_a17_final | 0 | 0 | 0.3 s | 632 final, runner exit |
| 9 | `g8f_check.sh` | 0 | 0 | 3.5 s | READY (final) |
| 10 | NEGATIVE: `g8f_freeze.sh` before STOP | 2 | 2 | 3.5 s | "queue_p4/STOP is missing: run g8f_stop.sh first" |
| 11 | NEGATIVE: aggregation with the FIRST record | 0 | 0 | 23.3 s | released: the 127 jobs of the first record; withheld: all 505 new runs |
| 12 | `g8f_stop.sh` | 0 | 0 | 3.9 s | STOP written; READY (stopped); `test_freeze.py --verify` OK |
| 13 | `g8f_stop.sh` again | 0 | 0 | 3.7 s | "exists already; nothing to do" |
| 14 | NEGATIVE: two new `final_*` directories | 2 | 2 | 3.5 s | PROBLEM "analysis holds 2 new final_* directories" |
| 15 | NEGATIVE: one byte appended to the first record | 2 | 2 | 0.5 s | `first`: PROBLEM (record not at the cited sha256, its `ANALYSIS_OUTPUTS.sha256` line differs); restored, `first` OK |
| 16 | `g8f_freeze.sh` | 0 | 0 | 32.5 s | record all_final, 632 jobs = ok 630 + sim_failure 2; RECORD OK; A18 entry; SIMULATE OK; applier check passed |
| 17 | `g8f_freeze.sh` again | 0 | 0 | 10.8 s | resume: record checked again, not rewritten; entry regenerated |
| 18 | `g8f_apply.sh A18 F` | 0 | 0 | 19.5 s | wrapper exit 0; manifest unchanged (221 files); POST OK: owner A18, both records valid |
| 19 | `g8f_freeze.sh` after the entry | 0 | 0 | 3.9 s | "the record is entered already" |
| 20 | `g8f_analysis.sh A18` | 0 | 0 | 99.4 s | analysis registered, H5 contradicted; figures (tree: no RL freeze); 61 files listed, no temporary line |
| 21 | `g8f_analysis.sh A18` again | 0 | 0 | 3.6 s | every step skipped; list checked, not rewritten |
| 22 | `g8f_verify.sh A18` | 0 | 0 | 57.4 s | AGREE; DIFFER; class report 'verification failure'; A19, A20; resolution A21 written; 3 applier checks passed |
| 23 | NEGATIVE resolution A: one extra non-R_cond row | 3 | 3 | 0.5 s | STOP, 1 of 122 rows outside the rule, no entry |
| 24 | NEGATIVE resolution B: value row on an R_cond pair | 3 | 3 | 0.5 s | STOP, 2 of 122 rows, no entry |
| 25 | NEGATIVE resolution C: R_cond 0.5 recomputed for one run | 3 | 3 | 0.5 s | STOP, 8 of 121 rows "not 0/0 on both sides", no entry |
| 26 | `g8f_apply.sh A19` | 0 | 0 | 19.2 s | sealed |
| 27 | `g8f_apply.sh A20` | 0 | 0 | 19.2 s | sealed |
| 28 | `g8f_apply.sh A21` | 0 | 0 | 19.2 s | sealed |
| 29 | `g8f_verify.sh A18` after the entries | 0 | 0 | 3.6 s | "the results are entered already" |
| 30 | `g8f_figs.sh A18` | 0 | 0 | 4.1 s | 240 values equal numbers.json; 10 files; titles "n = 44 routes"; FINAL CHECK OK |
| 31 | `registration.py --verify` in the tree | 0 | 0 | 3.2 s | manifest OK, both seals OK |

Tools inside the steps (wall time, max RSS; `dryrun/tree_steps.log`): `g8f_lib.py check` 0.3 s, 45 MB; freeze
aggregation 21.3 s, 75 MB; `record` 0.27 s, 55 MB; `simulate` 0.2 s; applier check 6.3 s, 19 MB; applier 16 s;
`agg_p4` 29.7 s, 83 MB; `agg_p1` 9.9 s, 59 MB; `agg_p2` 23.3 s, 91 MB; `analyze_v4.py` 10.9 s, 213 MB;
`prop1_coverage.py` 17.5 s, 118 MB; `figures_tables.py` 4.5 s, 165 MB; `verify_independent.py` 4.5 s, 100 MB;
`verify_table1_extra.py` 29.3 s, 149 MB; `f1_class_report.py` 0.19 s, 38 MB; `resolution` 0.25 s, 47 MB; Fig. 3
copies 1.9 s and 1.6 s, 132 MB. Largest resident set of any process: 213 MB.

Earlier runs: dry run 1 (15:59-16:07, 436 s) stopped step 19 with exit 2: `record` counted the record's own A18
citation as a collision; `record_info` now accepts a citation by an entry after A17 only. Dry run 2 was stopped at
step 22 to rerun with the final `rel()` (text-only path relativization, so that no run directory named by a runner
record is touched on the project); dry run 3 is the run above.

## 4. Results that carry over to the real run

* The full queue needs no swap and no `--cut-amendment`: the record has trigger `all_final`, 632 final jobs, the six
  queue copies at their G6 sha256, and passes `record_problems` and the phase driver's `analysis_record_problems`
  criteria (steps 16-18).
* Two `final_*` directories coexist: the scripts address the new one (`new-dir`), refuse two new ones (step 14) and
  never write into `final_20261116T091445`; `first` verifies it unchanged before and after every step (steps 9, 12,
  16, 30).
* After A18 both records are valid (`post`: owner A18; first record trigger cut / A12, registered). The first record
  releases none of the new runs (step 11), so the second analysis names its record explicitly.
* The 127 jobs of the first record keep outcome and run directory in the second record (ok 126, sim_failure 1).
* `ANALYSIS_OUTPUTS.sha256` of the new directory lists 61 files and no temporary file; the stand-in first directory
  shows the old defect (62 lines, one `.ANALYSIS_OUTPUTS.tmp`).
* The class report reads 'verification failure' with unexplained R_cond pairing-status rows whenever an R_cond cell
  is 0/0 (121 rows here, 21 in the stand-in first verification), the A16 mechanism. The resolution generator writes
  A21 when every such row satisfies the rule and stops (exit 3, no entry) on each of the three violations.
* Other classes on synthetic data: not_ok_record 81 (two double timeouts: `fl_original` r23658 and one `fl_full`
  kappa-2.0 job), undefined_metric_pairing 304 (P_both, A11 class), F1, F3, in-flight 0.
* H5: 'contradicted' from the log-less P1 attempt (`agg_p1`), with 0 violations; the queue_p4 attempt interrupted at
  the pause (logs present) is audited.
* Fig. 3: both copies draw from the new analysis, check every value against its `numbers.json`, write only into
  `$G/fig3_full_<stamp>/` and state "n = 44 routes".
* Sealed text: A18-A21 compose, seal and parse; 145 lines, none over 120 columns
  (`entries_example/PROTOCOL_tail_after_A18_A21.md`).

## 5. Job-health check on the project (read only)

`bash outputs/framelease_v4/build/G8FULL/g8f_check.sh` at 2026-11-17 16:26: exit 3 NOT FINAL; 301 of 632 job lines
final, 331 pending, runner 14451 alive and holding the lock, no queue STOP; no problem: the six job files at their G6
sha256, the 127 jobs of the first record not run again, A10-A17 once each, the analysis code and
`f1_class_report.py` at their cited sha256, the first freeze valid and unchanged (12 cited files at their sha256, every
`SHA256SUMS` of the first analysis and verifications, 61 of 62 lines of its `ANALYSIS_OUTPUTS.sha256`, the temporary
line excepted). The check reads runner records (start, end, final flag, run-directory name, runner start / exit) and
sha256 values only; no outcome of a run was read.
