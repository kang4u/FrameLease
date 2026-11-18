# RUNBOOK: second analysis freeze and analysis under Amendment A17 (all registered jobs final)

For the coordinating session (and, for step e, the independent session of Sec. 9.12). Nothing of this item is applied:
PROTOCOL.md, the registration files, the queues, the drivers' directories, every registered file, the first analysis
`analysis/final_20261116T091445/`, `verification/` and the G8CUT files are unchanged by it. The sequence was dry-run end
to end on a scratch copy of the project with synthetic run directories and the first freeze already entered
(`DRYRUN.md`); timings are those of the dry run unless marked "real data".

## 0. Conventions

Every command runs from `/home/kang/Desktop/DAC`, one at a time, after

```
cd /home/kang/Desktop/DAC
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
G=outputs/framelease_v4/build/G8FULL
```

The scripts of `$G` source `g8f_common.sh`: it pins the script's own shell (and so every child) with `taskset -cp 12-15`,
`renice 19`, `ionice -c 3`, and runs every tool as `taskset -c 12-15 nice -n 19 ionice -c 3 /usr/bin/time ...
.conda-unidrive-linux/bin/python -I -B`. Each tool's full output goes to `$G/logs/<label>.<time>.log`, one line per
tool (exit code, wall time, max RSS) to `$G/logs/steps.log`. Every script can be run again after an interruption
(Sec. 13). `PROGRESS.md` is the build log of this item.

| script | step | writes |
|---|---|---|
| `g8f_check.sh [final\|stopped]` | a: completion check (job health only) | `$G/logs/` only |
| `g8f_stop.sh` | b: `queue_p4/STOP`, `test_freeze.py --verify` | `queue_p4/STOP` |
| `g8f_freeze.sh` | c1: second freeze record, record checks, entry files, simulation, applier check | new `analysis/final_<stamp>/`, `$G/entries/` |
| `g8f_apply.sh NAME [F]` | c2, e2: one dated Sec. 13.2 entry through the registered appliers, post-check | PROTOCOL.md (sealed), `amendment_<name>/` |
| `g8f_analysis.sh A18` | d: released aggregations, analysis, coverage, figures, `ANALYSIS_OUTPUTS.sha256` | inside the new `final_<stamp>/` |
| `g8f_verify.sh A18` | e1: both verifiers, class report, entries A19, A20 and (rule) A21 | `verification/`, `$G/entries/` |
| `g8f_figs.sh A18` | f: Fig. 3 copies of the Desktop scripts on the new analysis, end-state check | `$G/fig3_full_<stamp>/` |
| `g8f_lib.py` | checks and entry texts (its docstring); imports the pure helpers of `G8CUT/g8_lib.py` | as above |
| `fig3/make_fig3_panels_full.py`, `fig3/make_fig3ab_table1_full.py` | parameterized copies of the Desktop scripts | `--out` only |
| `dryrun/` | scratch tree, synthetic runs, negative tests, `run_dryrun.sh` | `/tmp/G8FULL/` only |

`F` below is the new `outputs/framelease_v4/analysis/final_<stamp>/` (`g8f_lib.py new-dir` prints it: the one
`final_*` directory besides `final_20261116T091445`).

Entry ids. The freeze entry is the next free amendment id after A17, i.e. **A18**; the verification results follow as
**A19** (`verify_independent.py`) and **A20** (`verify_table1_extra.py` with the class report), and the resolution
entry as **A21** when the rule of Sec. 8 holds (`g8f_lib.py next-name`; the verify step computes N1, N1+1, N1+2 from
the sealed PROTOCOL.md). The appliers accept only titles `**Amendment <id>, <date> (Beijing time): ...**`; each title
states that no run, job line, criterion or analysis rule changes.

## 1. What differs from the first freeze (G8CUT) and how the scripts handle it

1. **No swap and no cut.** The six registered job files are in `queue_p4/jobs.d` at their G6 sha256 since Amendment
   A13 (Amendment A17 runs them in place). The freeze aggregation is the phase driver's `aggregate_cmd` without
   `--cut-amendment`: trigger `all_final`, every one of the 632 jobs final (`interim_guard.freeze_record` raises while
   one is not, aggregator exit 2). The record is checked with `interim_guard.record_problems` (required job files) and
   the criteria of `phase_driver.analysis_record_problems` (trigger `all_final`, no cut amendment, job files = the six
   copies, every job line once with a final outcome of its own file, the five aggregator modules on disk).
2. **Two `final_*` directories.** `G8CUT/g8_common.sh final_dir` and `phase_driver.analysis_target` refuse more than
   one `final_*` directory. `g8f_lib.py new-dir` addresses the new directory as the one besides
   `final_20261116T091445`; a second new one is a PROBLEM (dry run `NEG_two_new_dirs`). The new stamp is the time of
   the freeze; the scripts refuse to write into `final_20261116T091445`.
3. **Both records are valid after A18.** `interim_guard.load_freeze` accepts any record whose sha256 Sec. 13 cites. The
   first record holds the 505 jobs of A17 as `cut` (released only as `pending` without a run), so it releases none of
   their runs: dry run `NEG_first_record_new_runs`, an aggregation of the final queue with the first record releases its
   127 rows and withholds all 505 new ones. Every analysis command of this runbook names the second record explicitly
   (`--analysis-freeze $F/analysis_freeze.json`, `--required-job-files $F/required_job_files.json`).
4. **The 127 jobs of the first freeze must not have run again.** `check` compares the final runner record of each job
   that the first record holds as final with the recorded run directory and refuses a start record after the first
   freeze; `record` compares outcome and run directory of each such job in the two records (dry run: 126 ok and 1
   sim_failure identical).
5. **The first freeze stays unchanged.** `g8f_lib.py first` (part of every check and of the end-state check): the
   first record at `fdda3480...` (cited by A13 and A17) and accepted by `load_freeze` (trigger cut, A12, registered);
   every file of the first analysis and its verifications that A13-A16 cite by sha256 at that sha256 (the record,
   `SHA256SUMS`, `required_job_files.json`; `agg_p4/runs.csv`, `analysis/paired_differences.csv`, the files of
   `verification/final_20261116T091445*`); every `SHA256SUMS` below those directories holds; every line of its
   `ANALYSIS_OUTPUTS.sha256` holds except the temporary-file line of A16 correction 2 (61 lines).
6. **`ANALYSIS_OUTPUTS.sha256` (A16 correction 2).** G8CUT `g8_analysis.sh` lines 49-50 redirected `find` into
   `$F/.ANALYSIS_OUTPUTS.tmp`, so the list named its own temporary file. `g8f_lib.py manifest` lists every file below
   `F` except the list, writes the temporary file in `$G/logs/` and renames it into `F`, then checks every line, that
   the list equals the files on disk and that it names no temporary file (dry run: 61 files, no temporary line). A
   resumed run with every step skipped only checks the list (`manifest-check`).
7. **Verifier inputs (A16 "Aggregation path").** Both verifiers take `--agg $F/agg_p4` (the released aggregation with
   `arm_summary.csv`), not `F` (health-only rows).
8. **Class report and the R_cond rows (A16, A17).** `f1_class_report.py` runs only at the sha256 that A11 and A15 cite
   (`ac82d65a...`, `g8f_lib.py f1-ok`). It has no class for R_cond: a route whose R_cond is undefined (0/0) on one
   side is dropped by `analyze_v4.paired` (status `realized_r_cond missing: <conditions>`) and paired by the verifier,
   so each such row stays `unexplained` and the outcome reads "verification failure". `g8f_lib.py resolution` applies
   the rule of A16 (Sec. 8) and writes the resolution entry A21 automatically only when every unexplained row
   satisfies it.
9. **H5.** `agg_p1` holds the log-less attempt of the 2026-11-11 pause, so H5 reads 'contradicted' with 0 violations
   (G8CUT open point 2; the dry run reproduces it). The 2026-11-17 pause interrupted one queue_p4 attempt
   (`fl_original` r1956, not counted); its run directory is audited when it holds `jobs.jsonl` / `events.jsonl` (dry
   run) and counts as one more unaudited run otherwise. The label stays 'contradicted' either way.
10. **Fig. 3 scripts.** The Desktop scripts hard-code `FINAL = .../final_20261116T091445`, write the PNGs onto the
    Desktop under fixed names and `make_fig3ab_table1.py` writes "n = 14 routes" into its titles. The copies in `fig3/`
    take `--root --final --out`, write PNG and PDF only into `--out` (refused on the Desktop outside the project and
    inside `F`), refuse `final_20261116T091445`, and state n from the data ("n = 44 routes", or "n = <min>-<max>
    routes"). Drawing code and the checks against `figures/numbers.json` are the originals'.

## 2. Preconditions (read only)

1. Amendments A10-A17 entered once each; `registration.py --verify` reads "manifest: OK" and both seals OK.
2. The runner of `queue_p4` (ETA about 2026-11-19 10:00) has exited after the last job: `status.jsonl` ends with a
   `runner_exit` record after the last `runner_start`; no process holds `queue_p4/runner.lock`.
3. `phase_driver/STOP` present, no phase-driver process, no `ALERT.txt` / `protocol_txn.json` of either driver, no
   `framelease_v4/.PROTOCOL.md.entrytmp`.
4. Disk: the freeze, the analysis and the verifications write about 40-60 MB (first freeze: 11 MB for 127 runs).
5. Memory: every tool below 1.5 GB (dry run at most 213 MB; real-data estimates in Sec. 10).

## 3. Step a: completion check (`g8f_check.sh`)

```
bash $G/g8f_check.sh            # before queue_p4/STOP
```

Checks (`g8f_lib.py check`, job health only, Sec. 9.11; module docstring): the six job files in `jobs.d` at their G6
sha256, each cited by the G6 entry and by A17; 632 job lines, each with a final runner record; no runner (lock pid,
flock) and a runner exit after the last start; the 127 jobs of the first freeze unchanged (item 4 of Sec. 1); phase
driver stopped; no driver or applier transaction file; A10-A17 once each; the analysis code and the verifiers cited at
their sha256 on disk; `f1_class_report.py` at the A11 sha256; the first freeze valid and unchanged (`first`); at most
one new `final_*` directory.

Expected: `CHECK: READY (final)`, exit 0 (dry run 3.5 s with `registration.py --verify`; the tool 0.3 s, 45 MB). On
the project at 2026-11-17 16:26 (read only): exit 3 NOT FINAL, 301 of 632 job lines final, runner 14451 alive and
holding the lock, no problem (the first freeze valid and unchanged: 12 cited files, every `SHA256SUMS`, 61 lines of
its `ANALYSIS_OUTPUTS.sha256`; the 127 jobs of the first record not run again).
* Exit 3 `NOT FINAL (wait)`: `waits` names the cause (job lines without a final record, a live runner, no runner exit
  record). Run again later.
* Exit 2 `PROBLEM`: `problems` names it. A job file not at its sha256, a job of the first freeze run again, a changed
  file of the first freeze, a driver file, two new `final_*` directories: stop and resolve (a new amendment decides a
  changed registered file). A job that stays non-final because the runner stopped by a signal: relaunch the runner as
  A17 states (`systemd-run --user --scope ... launch_queue.sh outputs/framelease_v4/queue_p4`, after moving
  `queue_p4/STOP` aside if one exists), never the phase driver.
* `registration.py --verify` not OK: stop.

## 4. Step b: `queue_p4/STOP` (`g8f_stop.sh`)

```
bash $G/g8f_stop.sh
```

Refuses unless step a is READY. Writes `queue_p4/STOP` (temporary file and rename; text: "G8 under Amendment A17: every
job of the six registered job files is final and the runner has exited; the second analysis-freeze record follows. No
runner starts in this queue. Do not remove."), runs `check --expect stopped` and the phase driver's G6 verification
`test_freeze.py --verify --jobs-dir outputs/framelease_v4/test_jobs --rl-freeze ... --selection ... --stress-dir ...
--out-dir outputs/framelease_v4/test_freeze --queue-dir outputs/framelease_v4/queue_p4/jobs.d`.

Expected: `STOP: outputs/framelease_v4/queue_p4/STOP written`, `CHECK: READY (stopped)`, `test freeze OK: ...`, exit 0
(dry run 3.9 s). Run again: `STOP: ... exists already; nothing to do`, exit 0. From here on `queue_p4/STOP` stays and
no runner is launched into `queue_p4` (`launch_queue.sh` refuses while it exists; the runner starts no job).
* Exit 3 / 2: as step a. `test_freeze.py --verify` exit 2: its log names the job file (restore it from
  `test_jobs/FULL/`).

## 5. Step c1: the second analysis-freeze record (`g8f_freeze.sh`)

```
bash $G/g8f_freeze.sh
```

Runs `check --expect stopped` (READY required; without the STOP file: exit 2, dry run `NEG_freeze_before_stop`),
`test_freeze.py --verify`, then, into a new `outputs/framelease_v4/analysis/final_<stamp>/`:

```
aggregate_v4.py --queue outputs/framelease_v4/queue_p4 --specs outputs/framelease_v4/test_jobs/FULL \
    --rl-freeze outputs/framelease_v4/rl_freeze/rl_freeze.json --tuning-freeze outputs/framelease_v4/tuning/selection.json \
    --write-freeze-record outputs/framelease_v4/analysis/final_<stamp>/analysis_freeze.json \
    --out outputs/framelease_v4/analysis/final_<stamp>
```

(the phase driver's `aggregate_cmd`; never `--cut-amendment`, `--arm-summary` or `--analysis-freeze`), then `g8f_lib.py
required` (`F/required_job_files.json`: the six queue copies at their G6 sha256), `record`, `entry --name A18`,
`simulate` and the applier in check mode.

`record` checks (module docstring): `record_problems` with the required job files; trigger `all_final`, no cut
amendment; 632 jobs = the job lines of the six files, each final (`ok`, `agent_crashed`, `sim_failure`) and of its own
file; `analysis_code` = the five modules on disk, each cited; route split; `SHA256SUMS` holds; the aggregation guarded
(`pre_freeze`, no summary, no `arm_summary.csv`, queues `[queue_p4]`); no collision with the first freeze (another
directory and sha256, cited by no entry but its own (A18), frozen after `2026-11-16T09:15:07+0800`); the 127 jobs of the first record with
the same outcome and run directory, the 505 cut ones final. `simulate` composes PROTOCOL.md with the filled entry as
the applier does, reads it with both drivers' parsers (no Alert, A18 read once, other titles and driver entries
unchanged, the new record first cited by A18, the first record still first cited by A13), seals a copy under
`/tmp/G8FULL_sim/` and calls `load_freeze` on it for both records (accepted, `registered False` on the copy), while the
sealed PROTOCOL.md still refuses the new record.

Expected (dry run 32.5 s; aggregator 21.3 s, 75 MB on 632 synthetic runs; real data about 2-3 min, 200-400 MB):

```
outcomes: {'ok': <n>, 'sim_failure': <m>, ...}               (632 jobs, none pending)
interim guard (Sec. 9.11): pre_freeze, 632 guarded rows (632 test-route), 0 released, 632 health-only, ...
analysis-freeze record outputs/framelease_v4/analysis/final_<stamp>/analysis_freeze.json: sha256 <hex>, 632 jobs,
    trigger all_final. Not valid until ...
RECORD: OK
outputs/framelease_v4/build/G8FULL/entries/A18_entry.md (<n> lines), ..._spec.json; line problems: []
SIMULATE: OK
check: pre-checks passed
READY TO APPLY: bash outputs/framelease_v4/build/G8FULL/g8f_apply.sh A18 outputs/framelease_v4/analysis/final_<stamp>
```

Failures:
* Aggregator exit 2 "no analysis-freeze record: N job lines are not final": a job without a final record (step a
  missed it: read the list); nothing but the guard log is written; run `g8f_freeze.sh` again once resolved (it redoes
  the directory with `--force` while no record exists). Exit 4: a guard refusal (route split): stop. Exit 1: outputs
  exist (resume, Sec. 13).
* `RECORD: PROBLEM`: the list names it; the record is never rewritten (the aggregator refuses an existing record).
  Move `F` aside to `analysis/rejected_<stamp>/` after reading the problem, fix the cause, run again.
* `SIMULATE: PROBLEM` or the applier check stops (`STOP: ...`): nothing is written to PROTOCOL.md; the line names the
  cause (a width, a driver form, a file of `must_equal`).

## 6. Step c2: the dated entry A18 (`g8f_apply.sh A18 F`)

Wording: G8CUT's A13 (`g8_lib.freeze_entry`) adapted to Amendment A17.

| A13 (cut) | A18 (`g8f_lib.freeze_entry`) |
|---|---|
| title "... the analysis freeze (Sec. 9.12) under the cut of Amendment A12, carried out by the coordinating session ..." | "... the second analysis freeze (Sec. 9.12) under Amendment A17, all registered jobs final, carried out by the coordinating session with the registered tools in place of gate G8 of the phase driver; no run, job line, criterion or analysis rule changes." |
| "Freeze. Every job that Amendment A12 keeps ... `--cut-amendment A12` wrote ... trigger cut, cut amendment A12" | "Freeze. Every job of the six registered job files ... was final and the runner ... had exited (last runner exit <utc>); `queue_p4/STOP` was written before the freeze and `test_freeze.py --verify` passed ... trigger all_final, no cut, frozen ..." |
| "Job status: 632 jobs ...; outcomes ok, agent_crashed, sim_failure, cut 505 ..." | "Job status: 632 jobs ... (each file: tier, lines, sha256); outcomes ok, agent_crashed, sim_failure; no job cut. The 127 jobs that the record of A13 holds as final carry the same outcomes and run directories here (...); the 505 jobs that A12 cut and A17 runs are final (...)." |
| "Job files." (reduced files, swap) | (none: no swap) |
| "Analysis code frozen by the record: ...; `analyze_v4.py` by A10, `verify_table1_extra.py` by A11" | the same, plus `verify_independent.py` by A10 |
| "Interim looks (Sec. 9.11). ..." | the same, for `F` |
| (none) | "First analysis freeze. The record of A13 (sha256 `fdda...`) stays valid and unchanged, as do its outputs ...; it holds the 505 jobs of A17 as cut and releases none of their runs. Every result in the paper names the analysis it comes from (A17)." |
| "Validity. ..." | the same for `F`, plus: the verifications read `F/agg_p4` (A16 "Aggregation path"); phase driver stopped (A12, A17) |
| manifest clause | the same |

`entries/A18_spec.json`: no tests, no in-place text, `max_new_registered` 0, `must_equal` = the new record, its
`SHA256SUMS`, `required_job_files.json`, `test_freeze.json`, `analyze_v4.py`, `verify_independent.py`,
`verify_table1_extra.py`, the five modules, the six queue copies and the first record. Worked example (synthetic
counts): `dryrun/entries_example/`.

```
bash $G/g8f_apply.sh A18 outputs/framelease_v4/analysis/final_<stamp>
```

It runs `setsid nohup taskset ... bash outputs/framelease_v4/build/AMEND2/a10r7b/apply_locked.sh $G/entries/A18_spec.json
outputs/framelease_v4/amendment_a18 > .../console.txt` detached (a10r7b RUNBOOK Sec. 1: the wrapper takes
`framelease_v4/.protocol.lock`), waits for `apply_locked: exit`, prints the applier's lines, then `registration.py
--verify` and `g8f_lib.py post`.

Expected (dry run 19.5 s): `wrapper exit 0`; `manifest difference: new [] / left [] / changed []`; `newly cited manifest
files: []`; `POST: OK` with `owner A18`, the second record `trigger all_final, registered true` and the first record
`trigger cut, cut_amendment A12, registered true`.
* Wrapper exit 94: completed by the wrapper; continue. Exits 92, 93, 95-98, or no exit line: a10r7b RUNBOOK Sec. 1
  (`g8f_apply.sh` stops after 1500 s without a wrapper process with exit 91: hand recovery there).
* `POST: PROBLEM`: the record is not valid for the analysis until it passes.
* Running `g8f_freeze.sh` after the application prints "the record is entered already" and exits 0.

From the seal of A18 on, every test-route row of the second record may be examined.

## 7. Step d: the registered analysis (`g8f_analysis.sh A18`)

```
bash $G/g8f_analysis.sh A18
```

Refuses (exit 4) unless `post` passes. Then exactly the G8CUT step d commands, on `F`:

```
aggregate_v4.py --queue outputs/framelease_v4/queue_p4 --specs outputs/framelease_v4/test_jobs/FULL \
    --rl-freeze outputs/framelease_v4/rl_freeze/rl_freeze.json --tuning-freeze outputs/framelease_v4/tuning/selection.json \
    --analysis-freeze $F/analysis_freeze.json --required-job-files $F/required_job_files.json --arm-summary test \
    --out $F/agg_p4
aggregate_v4.py --queue outputs/framelease_v4/queue_p1 --specs outputs/framelease_v4/p1_jobs/FULL --out $F/agg_p1
aggregate_v4.py --queue outputs/framelease_v4/queue_p2 --specs outputs/framelease_v4/p2_jobs/FULL --out $F/agg_p2
analyze_v4.py --agg $F/agg_p4 --agg $F/agg_p1 --agg $F/agg_p2 --analysis-freeze $F/analysis_freeze.json \
    --required-job-files $F/required_job_files.json --rl-freeze outputs/framelease_v4/rl_freeze/rl_freeze.json \
    --offline outputs/framelease_v4/offline_ablation \
    --s3 outputs/framelease_v4/stress/s3_registered_20261115T122819Z.json --out $F/analysis
prop1_coverage.py --tuning-freeze outputs/framelease_v4/tuning/selection.json --out $F/coverage
figures_tables.py --out $F/figures --analysis $F/analysis --offline outputs/framelease_v4/offline_ablation \
    --coverage $F/coverage --s1 outputs/framelease_v4/stress/s1_registered_20261115T124141Z.json \
    --s2 outputs/framelease_v4/stress/s2_registered_20261115T123104Z.json \
    --s2-relative outputs/framelease_v4/stress/s2_relative_registered_20261115T123118Z.json \
    --s3 outputs/framelease_v4/stress/s3_registered_20261115T122819Z.json \
    --d1 outputs/framelease_v4/tuning/d1/FULL_d1_summary.json --rl-freeze outputs/framelease_v4/rl_freeze/rl_freeze.json \
    --require-registered
g8f_lib.py manifest --dir $F          # $F/ANALYSIS_OUTPUTS.sha256, temporary file outside F (Sec. 1 item 6)
```

Expected (dry run 99 s: agg_p4 29.7 s / 83 MB, agg_p1 9.9 s, agg_p2 23.3 s, analyze_v4.py 10.9 s / 213 MB,
coverage 17.5 s, figures 4.5 s / 165 MB; real data in Sec. 10): `agg_p4` (released: 632 guarded rows, 632 released), `agg_p1`,
`agg_p2`; `analysis status registered | H5 contradicted | development reasons []`; coverage; `figures status
registered | reasons [] | numbers <n>` (7 items); `F/ANALYSIS_OUTPUTS.sha256: <n> files, problems []`; `ANALYSIS DONE:
F (<n> files in ANALYSIS_OUTPUTS.sha256)`. With every job final, the contrasts use up to 44 (Table I, H1-H3), 22
(subset E: Fig. 3, Table II-A panels, F3, H4-cl, RL-abl, fl_risk) and 15 (seed-12 replicates) routes; the routes of
the two `sim_failure` jobs drop from their contrasts (Sec. 9.8; dry run: the timed-out `fl_original` r23658 and one
synthetic `fl_full` kappa-2.0 job).

Failures: a step exits 2 or 4 with its log tail printed. `analysis status development`: `development_reasons` names it;
`figures_tables.py --require-registered` then exits 4 and writes nothing. Fix the source, remove the failed
subdirectory only if it holds no `SHA256SUMS`, run again (finished steps are skipped; with every step skipped the list
is only checked). Never remove or rewrite a subdirectory with `SHA256SUMS`.

## 8. Step e: the independent verifications and their entries (`g8f_verify.sh A18`, independent session)

```
bash $G/g8f_verify.sh A18
```

It runs (each skipped when its output holds `SHA256SUMS`, the class report when its file exists):

```
verify_independent.py --queue outputs/framelease_v4/queue_p4 --analysis-freeze $F/analysis_freeze.json \
    --agg $F/agg_p4 --analysis $F/analysis --out outputs/framelease_v4/verification/final_<stamp>
verify_table1_extra.py --analysis-freeze $F --queue outputs/framelease_v4/queue_p4 --agg $F/agg_p4 \
    --analysis $F/analysis --out outputs/framelease_v4/verification/final_<stamp>_table1_extra
f1_class_report.py outputs/framelease_v4/verification/final_<stamp>_table1_extra \
    --out outputs/framelease_v4/verification/final_<stamp>_table1_extra_f1_class.json      # only at the A11 sha256
```

then the entry files: `entries/A19_*` (`result-entry --kind verify`: `verification.json` and `SHA256SUMS` by sha256,
status, verdict, differences; A10 use rule 4), `entries/A20_*` (`--kind extra`: `table1_extra.json`, `SHA256SUMS` and
the class report by sha256, status, verdict, outcome, release, differences per class; A11 use rules 1-3) and, by the
rule below, `entries/A21_*` plus `entries/A21_rows.json` (every resolved row with its conditions, jobs and the
registered and recomputed R_cond and conflict plans). Each spec passes the applier in check mode.

**Resolution rule (A16, A17; `g8f_lib.py resolution`).** The unexplained rows are formed again with the functions of
`f1_class_report.py` (same order as its `report`), and the class sizes must equal the report's. The entry is written
when, and only when, the report reads "verification failure" and EVERY unexplained row
* is a pairing-status row: no cause, target `paired_differences.csv`, field `paired` against `status`, `True` /
  `False`, metric `r_cond`, note exactly `status 'realized_r_cond missing: <conditions>'`;
* has its analysis row with that status and no value, no `value_a` / `value_b` / `difference` row of its key and no
  contrast-level row (`n`, means, median, min, max) of its contrast and metric in `differences.csv`, and no runs.csv
  comparison of R_cond, conflict plans or misses for the jobs of the pair (no numeric difference);
* has, for every condition the status names, the cell's run with R_cond undefined by 0/0 on both sides: registered
  `agg_p4/runs.csv` `realized_r_cond` empty and `realized_conflict_plans` 0, recomputed `runs_recomputed.csv` `r_cond`
  empty and `conflict_plans` 0 (a recomputed interval from unevaluated plans, as A16's Event-Triggered cell, is noted
  in the entry).
Otherwise it writes no resolution entry, prints every failing row with its reasons and the script exits 3; the rows are
then resolved by hand and their cause entered in Sec. 13 before any R7B column enters the paper (A10 use rule 4; A11
use rule 2). No unexplained row: "RESOLUTION: not needed", no A21.

The A21 wording follows A16 ("Differences", "Resolution"), with the counts per contrast, the evidence files by sha256
(`differences.csv`, `runs_recomputed.csv`, `agg_p4/runs.csv`, `analysis/paired_differences.csv`, the class report) and
the size of every class (F1, F3, in-flight with their analysis-scope counts, not-ok record with its jobs,
undefined-metric pairing, the resolved rows).

Expected (dry run 57 s): `verify_independent: final AGREE` (4.5 s, 100 MB); `verify_table1_extra: final DIFFER` (29 s,
149 MB); `class report: verification failure | ... {'F1': 0, 'F3': 0, 'in_flight': 0, 'not_ok_record': 81,
'undefined_metric_pairing': 304, 'unexplained': 121}`; `RESOLUTION: entry written (121 unexplained rows, all R_cond
0/0 pairing-status rows ...)`; three `check: pre-checks passed`; `ENTRIES (apply in this order, after reading the
results): ... A19; ... A20; ... A21`. Negative tests (dry run): an extra non-R_cond row, a value row on an R_cond pair,
and R_cond defined on the recomputed side each give `RESOLUTION: STOP` with the failing rows and exit 3, no entry.

Then, after reading the results:

```
bash $G/g8f_apply.sh A19
bash $G/g8f_apply.sh A20
bash $G/g8f_apply.sh A21          # only when entries/A21_spec.json exists
```

(dry run 19.2 s each). Running `g8f_verify.sh` after A19 is entered prints "the results are entered already" and writes
no entry file.

Failures:
* `verify_independent.py` exit 1 (DIFFER): A19 records the result as it is; every row of its `differences.csv` is
  resolved and entered in Sec. 13 before H1 or the five columns enter the paper (A10 use rule 4).
* Exit 2 of a verifier (input or guard error) or of the class report (`queue_p4/status.jsonl` or `agg_p4/runs.csv`
  changed after the verifier ran; nothing writes them after the STOP): read the log; never run a verifier with
  `--force` over an output with `SHA256SUMS`.
* `RESOLUTION: STOP` (exit 3): A19 and A20 are ready; apply them; resolve the listed rows by hand.
* "the classes formed again ... differ from the class report": a changed input; stop.

## 9. Step f: Fig. 3 on the new analysis and the end-state check (`g8f_figs.sh A18`)

```
bash $G/g8f_figs.sh A18
```

Runs `fig3/make_fig3_panels_full.py --root /home/kang/Desktop/DAC --final $F --out $G/fig3_full_<stamp>` and
`fig3/make_fig3ab_table1_full.py` with the same arguments (the Desktop originals stay as they are, read only), writes
`$G/fig3_full_<stamp>/SHA256SUMS`, then `g8f_lib.py final-check --dir $F`: the first freeze unchanged (`first`), every
`SHA256SUMS` of `F` and of `verification/final_<stamp>*` holds, `F/ANALYSIS_OUTPUTS.sha256` holds, one new `final_*`.

Expected (dry run 4.1 s; each script 2 s, 132 MB): `240 values equal to the registered numbers.json of final_<stamp>`; three panels
(`Fig3a_DS_vs_action_age_p50`, `Fig3b_DS_vs_action_age_p95`, `Fig3c_EIR_GPU_usage`); `means equal to the registered
numbers.json`; two Table-I panels (`Fig3a_TableI_methods_DS_vs_age_p50`, `..._p95`) with "(n = 44 routes)"; `FINAL
CHECK: OK`; `FIGURES: ... (10 files)`. The PNG / PDF go to the paper only by an explicit copy of the paper session.
* A value that differs from `numbers.json` stops the script before drawing (exit 1): the analysis outputs changed;
  stop. `FINAL CHECK: PROBLEM`: read the list.

## 10. Order and timing

| # | step | needs | dry run | real data (estimate) |
|---:|---|---|---:|---:|
| 1 | `g8f_check.sh` until READY | runner exited (ETA 2026-11-19 about 10:00) | 3.5 s | 4 s |
| 2 | `g8f_stop.sh` | 1 | 3.9 s | 4 s |
| 3 | `g8f_freeze.sh` | 2 | 32.5 s | 3-4 min (aggregator 2-3 min) |
| 4 | `g8f_apply.sh A18 F` | 3, entry read | 19.5 s | 20 s |
| 5 | `g8f_analysis.sh A18` | 4 | 99 s | 20-25 min (agg_p4 9-12 min, agg_p1 6 min, agg_p2 2.5 min) |
| 6 | `g8f_verify.sh A18` (independent session) | 5 | 57 s | 4-5 min (verify_table1_extra about 3 min) |
| 7 | `g8f_apply.sh A19`, `A20` (`A21`) | 6, results read | 3 x 19.2 s | 1 min |
| 8 | `g8f_figs.sh A18` | 5 (after 7 for the paper) | 4.1 s | 10 s |
| 9 | paper fill from `F/figures/numbers.json` and the entries | 7, 8 | - | - |

Real-data estimates scale the logs of the first freeze (127 runs, `G8CUT/logs/steps.log`) to 632 runs: freeze
aggregation 22.5 s, agg_p4 117 s / 297 MB, agg_p1 336 s / 312 MB, agg_p2 151 s / 206 MB, analysis 1.9 s, coverage 17 s,
figures 5 s, verify_independent 1.5 s, verify_table1_extra 34 s / 148 MB, appliers 16 s. Memory: every tool is
expected below 1 GB; the dry run's largest resident set was 213 MB (analyze_v4.py on 632 runs).

## 11. Expected outputs

* `outputs/framelease_v4/queue_p4/STOP` (step b).
* `F = outputs/framelease_v4/analysis/final_<stamp>/` (steps c1, d; 62 files in the dry run):
  `analysis_freeze.json` (the record), `runs.csv`, `aggregate.json`, `interim_guard.jsonl`, `SHA256SUMS` (the
  health-only freeze aggregation), `required_job_files.json`, `ANALYSIS_OUTPUTS.sha256` (61 lines);
  `agg_p4/` (`runs.csv`, `aggregate.json`, `arm_summary.csv`, `interim_guard.jsonl`, `SHA256SUMS`), `agg_p1/`, `agg_p2/`
  (the same without `arm_summary.csv`); `analysis/` (`analysis.json`, `cells.csv`, `conditions.csv`, `descriptive.csv`,
  `family_{F3,H1,H2,H3,H4-cl,RL-abl,S-coll,S-dmr}.csv`, `h4_offline.csv`, `paired_differences.csv`, `per_ability.csv`,
  `per_scenario.csv`, `secondary.csv`, `interim_guard.jsonl`, `SHA256SUMS`); `coverage/` (`coverage.csv`,
  `coverage.json`, `per_clip.csv`, `per_tau.csv`, `interim_guard.jsonl`, `SHA256SUMS`); `figures/` (`numbers.json`,
  `figures.json`, `fig1`, `fig1_scenarios`, `fig3` as PDF, PNG and caption, `table1.tex`, `table2a.tex`, `table2b.tex`,
  `table_train.tex`, `interim_guard.jsonl`, `SHA256SUMS`).
* `outputs/framelease_v4/verification/final_<stamp>/` (`verification.json`, `comparisons.csv`, `contrasts.csv`,
  `differences.csv`, `paired.csv`, `runs.csv`, `table_i.csv`, `guard_log.jsonl`, `SHA256SUMS`),
  `.../final_<stamp>_table1_extra/` (`table1_extra.json`, `differences.csv`, `runs_recomputed.csv`, `cause_plans.csv`,
  `guard_log.jsonl`, `SHA256SUMS`), `.../final_<stamp>_table1_extra_f1_class.json` (step e).
* `outputs/framelease_v4/amendment_a18/` ... `amendment_a21/` (`apply.out`, `verify.out`, `console.txt`, `attempt_*/`);
  PROTOCOL.md with A18-A21, `MANIFEST.sha256` (221 files, unchanged), `SEAL.sha256`, `REGISTRATION.json` re-sealed.
* `$G/entries/A18_*`, `A19_*`, `A20_*`, `A21_*` (+ `A21_rows.json`); `$G/logs/`; `$G/fig3_full_<stamp>/` (5 PNG, 5 PDF,
  `SHA256SUMS`).
* Unchanged: `analysis/final_20261116T091445/`, `verification/final_20261116T091445*`, the Desktop figure scripts and
  figures, every registered file.

## 12. Failure actions (summary)

| symptom | action |
|---|---|
| `registration.py --verify` not OK | stop; a registered file changed: a new amendment decides |
| check exit 3 | wait; run again |
| check exit 2: job file, first freeze, rerun job, driver file, two new `final_*` | stop; resolve the named cause; never edit the first freeze |
| runner stopped by a signal with jobs pending | relaunch the runner as A17 states (scope with OOMPolicy=continue), never the phase driver |
| aggregator exit 2 at the freeze | a job not final: back to step a |
| `RECORD: PROBLEM` / `SIMULATE: PROBLEM` / applier `STOP:` | read the list; move a rejected `F` aside to `analysis/rejected_<stamp>/`; nothing is entered |
| wrapper exit 92, 93, 95-98, 91 | a10r7b RUNBOOK Sec. 1 |
| `POST: PROBLEM` | no analysis on the record until it passes |
| analysis `development` / figures exit 4 | read `development_reasons`; fix; rerun (finished steps skipped) |
| verifier DIFFER (A19) | enter as is; resolve every difference before H1 enters the paper |
| `RESOLUTION: STOP` (exit 3) | apply A19, A20; resolve the listed rows by hand in their own entry |
| Fig. 3 copy stops on a value | the analysis outputs changed; stop |
| `FINAL CHECK: PROBLEM` | read the list; a changed output is a finding to enter |

## 13. Resume after an interruption

* `g8f_check.sh`, `g8f_stop.sh`: idempotent.
* `g8f_freeze.sh`: with no new `final_*` it starts one; with one without a record it redoes the aggregation there with
  `--force`; with a record it checks it again (never rewrites it) and regenerates the entry files; with the record
  entered it prints so and exits 0. Two new `final_*`: stop.
* `g8f_apply.sh NAME`: a wrapper that ended with exit 0 is not run again (`apply.out` holds `apply_locked: exit 0`);
  an interrupted wrapper: a10r7b RUNBOOK Sec. 1.
* `g8f_analysis.sh`, `g8f_verify.sh`: each step is skipped when its output directory holds `SHA256SUMS` (the class
  report when its file exists); a failed step leaves no `SHA256SUMS` and runs again. `g8f_figs.sh` redraws.
* `$G/logs/steps.log` holds every tool run with its exit code; `PROGRESS.md` the build of this item.

## 14. Open points

1. **Real R_cond rows outside the dry run.** The rule reproduces A16's mechanism on synthetic runs (121 rows) and stops
   on the three negative variants; it was not run on the real rows of A16 (that would read the first verification and
   `queue_p4/status.jsonl`, which has changed since its recorded sha256). A cell whose registered
   `realized_conflict_plans` is empty instead of 0 (e.g. no usable actor log) makes the rule stop: correct by design,
   then by hand.
2. **H5** stays 'contradicted' with 0 violations (Sec. 1 item 9; G8CUT open point 2): the paper reports the label with
   its cause (`analysis.json` h5 `unaudited_runs`, `no_log_runs`).
3. **Timing.** The queue ETA (2026-11-19 about 10:00) plus about 35 min of tools puts the entered A18-A21 and the
   figures near 10:40 on 2026-11-19, after the full-paper deadline recorded for DAC 2027 (2026-11-19 09:00 Beijing).
4. **Fig. 3 copies** write into `$G/fig3_full_<stamp>/`; moving them into the paper (and the caption "n = 44 routes")
   is a paper-side step.
5. **Entry ids** A18-A21 assume no other amendment is entered before the freeze; the scripts take the next free id
   from the sealed PROTOCOL.md at each step, and `entry` refuses an id below A18.
