# RUNBOOK: analysis freeze (gate G8) and registered analysis under the cut of Amendment A12

For the coordinating session (Sec. 8: the independent session). Nothing of this item is applied: PROTOCOL.md, the
registration files, the queues, the drivers' directories and every registered file are unchanged by it. The sequence
was dry-run end to end on a scratch copy of the project with synthetic run directories (`DRYRUN.md`); the timings
quoted below are those of the dry run unless marked "real data".

## 0. Conventions

Every command runs from `/home/kang/Desktop/DAC`, one at a time, after

```
cd /home/kang/Desktop/DAC
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
X="taskset -c 12-15 nice -n 19 ionice -c 3"
P="$X .conda-unidrive-linux/bin/python -I -B"
G=outputs/framelease_v4/build/G8CUT
```

The scripts of `$G` source `g8_common.sh`, which sets the same environment and runs every tool as
`taskset -c 12-15 nice -n 19 ionice -c 3 /usr/bin/time ...`; each tool's full output goes to
`$G/logs/<step>.<time>.log` and one line per tool (exit code, wall time, max RSS) to `$G/logs/steps.log`. A step that
already produced its outputs is never redone: every script can be run again after an interruption (Sec. 10).

| script | step | writes |
|---|---|---|
| `g8_check.sh [reduced\|registered]` | a: completion check | `$G/logs/` only |
| `g8_swap.sh` | b1: `queue_p4/STOP`, registered job files back into `queue_p4/jobs.d` | the queue's `jobs.d/` and `STOP` |
| `g8_freeze.sh` | b2, c1: freeze record, record checks, entry files, simulation, applier check | `analysis/final_<stamp>/`, `$G/entries/` |
| `g8_apply.sh NAME [FINAL_DIR]` | c2, e3: one dated Sec. 13.2 entry through the registered appliers, post-check | PROTOCOL.md (sealed), `amendment_<name>/` |
| `g8_analysis.sh A13` | d: released aggregations, analysis, coverage, figures and tables | inside `analysis/final_<stamp>/` |
| `g8_verify.sh A13` | e: independent verification, R7B recomputation, class report, entry files | `verification/`, `$G/entries/` |
| `g8_lib.py` | the checks and entry texts behind the scripts (its docstring) | as above |

Entry ids: the freeze entry is the next free amendment id after A11 and A12, i.e. **A13**; the two verification results
follow as **A14** and **A15** (`g8_lib.py next-name`). The appliers accept only titles of the form
`**Amendment <id>, <date> (Beijing time): ...**` (`apply_entry_stream.py`: `title = '**Amendment ' + name + ','`), so
each dated entry of this runbook carries an amendment id; its title states that it records the analysis freeze or a
verification result and changes no run, job line, criterion or analysis rule.

## 1. What the cut changes in G8 (findings of the preparation and the dry run)

1. **The registered job files must be back in `queue_p4/jobs.d` before the freeze aggregation.** `queue_p4/jobs.d` now
   holds the six A12 reduced files. `aggregate_v4.py --queue queue_p4 --specs test_jobs/FULL ...` reads the job files of
   `jobs.d` and checks every block spec against them: with the reduced files it stops with exit 2 ("block specs
   disagree with the job lines": the specs' job-file sha256 are not among the files read and 505 spec jobs are not job
   lines; dry run `NEG_aggregate_reduced`). Without `--specs` it writes a record of 127 jobs whose job files are the
   reduced ones, which `interim_guard.record_problems(..., required_job_files=<G6 files>)` rejects ("6 job files differ
   from the test freeze's sha256"). With the registered copies in `jobs.d` (`cut_20261115T231415/jobs_registered/`, at
   their G6 sha256), the 505 never-started lines have no runner record and no run directory (`missing_reason
   not_launched`), and `--cut-amendment A12` records them as `cut`: trigger `cut`, 632 jobs, 127 final + 505 cut,
   `job_files` = the six queue copies at their G6 sha256. Amendment A12 already keeps the registered copies for this
   ("the phase driver ... requires the registered copies in `jobs.d`"). `g8_swap.sh` writes `queue_p4/STOP` first, so
   that no runner ever starts one of the 505 cut lines (`launch_queue.sh` refuses while `STOP` exists; the runner starts
   no job while it exists; a restarted phase driver never launches a runner while it exists).
2. **The phase driver stays stopped for good.** Its G8 refuses a record with trigger `cut` (`analysis_record_problems`:
   "the driver freezes when every job is final, without a cut"), and after the swap its G7 would see 505 pending jobs.
   `phase_driver/STOP` and `queue_p4/STOP` stay; the driver is never restarted; the A13 entry takes the place of its
   G8 entry and its `PHASES_DONE.json` is never written.
3. **The confirmatory analysis cannot read the freeze aggregation.** The aggregation that makes the record keeps every
   test-route row health-only (Sec. 9.11), so `analyze_v4.py --agg final_<stamp>` stops with exit 2 ("no column
   ['driving_score', 'collisions_per_km', 'dmr']"; dry run `NEG_analyze_freeze_agg`), and `analyze_v4.py` requires every
   input with a test-route row to be an aggregation made with the record. A10 use rule 1 ("runs on the aggregation of
   the freeze") is therefore carried out with a second aggregation of `queue_p4` made WITH `--analysis-freeze` and
   `--required-job-files`, written inside `final_<stamp>/` (`agg_p4/`); the freeze aggregation and its `SHA256SUMS`
   (cited by A13) stay untouched.
4. **H5 needs the commit audit of every phase.** `analyze_v4.h5` labels H5 'undetermined' (a development status, so
   `figures_tables.py --require-registered` refuses) unless the inputs cover P1-0, P1, P2, P4, P5 and P6. The analysis
   therefore also reads the aggregations of `queue_p1` (P1-0 smoke and P1; `--specs p1_jobs/FULL`) and of `queue_p2`
   (P2; `--specs p2_jobs/FULL`), both without `--rl-freeze` / `--tuning-freeze` (with the tuning freeze the P1 runs of
   `fl_heuristic` at E5 would be labelled `fl_risk`). `queue_p1_smoke2` repeats the job ids of `queue_p1`'s smoke block
   with the same output directories: its runs are audited through `queue_p1` and it is not aggregated separately.
5. **The verifiers compare `arm_summary.csv`.** `verify_independent.py` and `verify_table1_extra.py` compare the
   aggregator's `runs.csv` and `arm_summary.csv` of `--agg`; a missing `arm_summary.csv` is a difference. `agg_p4` is
   therefore written with `--arm-summary test` (allowed under the valid record), and the verifiers take
   `--agg final_<stamp>/agg_p4` (not `final_<stamp>`, which a10r7b RUNBOOK Sec. 3 names: its rows are health-only and it
   has no `arm_summary.csv`).
6. **H5 will read 'contradicted' without any Eq. 9 violation** when the P1 aggregation holds a run directory without
   `jobs.jsonl` and `events.jsonl` that no row selects: `analyze_v4.h5` counts such a NO_LOG run as unaudited, and an
   unaudited run makes the label 'contradicted' (Amendment A10, deviation 7). The development aggregations of the A10
   evidence hold two: `tuning/ref/fixed_deep/runs/20261111T153901_60968837` (job `v4p1_fixed_deep_k1.0_s11_r28093`,
   interrupted at the pause of 2026-11-11 15:36; `build/AGG/smoke_D`) and
   `tuning/lease_s1/fl_heuristic_E10_d10/runs/20261111T193852_ee1fc967` (job `v4p1_fl_heuristic_E10_d10_k1.0_s11_r3514`,
   the OOM stop of 2026-11-12 03:40; `build/R7B/dev/agg_snap_2203`). The dry run reproduces the mechanism (one
   interrupted synthetic attempt: H5 'contradicted', "commit-audit violations 0, S3 violations 0, unaudited runs 1").
   Open point 2 (Sec. 11).
7. **`verify_table1_extra.py` reports 'paired' status differences for P_both against arms without a shield.** Its
   `compare_paired_differences` pairs a route when both cells are used, while `analyze_v4.py` drops a route from a
   metric whose value is missing (`status 'p_both missing: fixed_deep_k1.0_s11'`). Every secondary P_both row of a
   shield arm against `fixed_deep`, `fast_only`, `event_triggered` or `fl_original` (H1 contrasts 1, 2, 4, H3, F3)
   gives one difference per paired route, without a cause, in scope 'analysis'; `f1_class_report.py` puts them in
   'unexplained' and the outcome is 'verification failure' (dry run: 76 = 14 x 3 + 13 x 2 + 2 x 4). No number differs:
   P_both of these arms is undefined (no shield) on both sides. Open point 1 (Sec. 11).
8. **Tree-only effects of the dry run** (absent in the project): the RL freeze names its networks by the project's
   absolute paths, so `figures_tables.py --rl-freeze` refuses it in a copy at another path; in the project
   `p3_rl.load_rl_freeze(require_cited=True)` and `figures_tables.load_rl_freeze` accept it with no development reason
   (checked read-only, 1.9 s, 111 MB). `DRYRUN.md` lists the other tree adjustments.

## 2. Preconditions (all read only)

1. Amendment A11 is entered and sealed (its RUNBOOK: `outputs/framelease_v4/build/AMEND2/a10r7b/RUNBOOK.md` Sec. 3,
   `post_check.py A11` passed). `g8_check.sh` waits for it ("Amendment A11 found 0 times"). A11 must precede the freeze
   (APPLY_PLAN2 step 7; Amendment A10, deviation 9).
2. Open point 1 decided (Sec. 11) before A11 is applied, when A11 is to carry the class for finding 7.
3. No ALERT.txt / protocol_txn.json of either driver, no `framelease_v4/.PROTOCOL.md.entrytmp`, `phase_driver/STOP`
   present, no phase-driver process.
4. Disk: the freeze and the analysis write less than 100 MB (dry run: 62 files; real-data aggregations of P1 runs wrote
   a few MB each).

## 3. Step a: completion check (`g8_check.sh`)

```
bash $G/g8_check.sh            # before the swap: jobs.d must hold the reduced files
```

Checks (job health only, Sec. 9.11; `g8_lib.py check`): `registration.py --verify` reads "manifest: OK" and both seals
OK; `queue_p4/jobs.d` holds exactly the six job files, all at their A12 reduced sha256 (`CUT_PLAN.json`, itself at its
A12 sha256); the reduced and registered copies in `cut_20261115T231415/` and `test_jobs/FULL/` at their sha256; 632
registered, 127 kept and 505 cut lines; every kept line has a final runner record; no runner holds the queue
(`runner.lock` pid with `gpu_queue.py`, flock) and the last runner record is an exit; no runner record of a cut line;
`phase_driver/STOP` present and no driver process; no driver ALERT / transaction file and no applier temporary file;
Sec. 13.2 holds A10, A11 and A12 once each and cites the cut plan, `analyze_v4.py`, the five aggregator modules and
`verify_table1_extra.py` at their sha256 on disk; no `analysis/final_*` directory yet.

Expected: `CHECK: READY (reduced)`, exit 0 (dry run 3.4 s; the tool 0.15 s, 33 MB).
* Exit 3 `NOT FINAL (wait)`: the `waits` list names the cause (kept jobs without a final record, a live runner, no
  runner exit record, A11 not entered). Run again later. On the project at 2026-11-16 00:30 it reads: 34 of 127 kept
  jobs final, runner 665278 alive, 0 cut lines with records, A11 not entered (exit 3).
* Exit 2 `PROBLEM`: the `problems` list names it. A job file not at its sha256, a cut line with a runner record (a cut
  job started: a new amendment decides), a driver file, a second `final_*` directory: resolve before going on. A kept
  job that stays non-final (e.g. the runner stopped by a signal with pending jobs): relaunch the runner as Amendment A12
  states (`systemd-run --user --scope ... launch_queue.sh outputs/framelease_v4/queue_p4`), never the phase driver.
* `registration.py --verify` not OK: stop; a registered file changed (a new amendment decides).

## 4. Step b1: registered job files back into `jobs.d` (`g8_swap.sh`)

```
bash $G/g8_swap.sh
```

Refuses unless step a is READY. Writes `queue_p4/STOP` (reason text), replaces each reduced file in `jobs.d` by its
registered copy (temporary file, rename), checks the G6 sha256 of all six, runs `g8_lib.py check --expect registered`
and then the phase driver's G6 verification `test_freeze.py --verify --jobs-dir outputs/framelease_v4/test_jobs
--rl-freeze ... --selection ... --stress-dir ... --out-dir outputs/framelease_v4/test_freeze --queue-dir
outputs/framelease_v4/queue_p4/jobs.d`.

Expected: `SWAP: done; ... STOP written; the six registered job files are in jobs.d at their G6 sha256`, `CHECK: READY
(registered)`, `test freeze OK: ...`, exit 0 (dry run 3.7 s). Run again: `SWAP: the registered copies are in jobs.d
already; nothing to do`, exit 0.
* Exit 3: step a is not READY. Exit 2: a copy not at its sha256 (disk; restore from `cut_20261115T231415/`), or
  `test_freeze.py --verify` fails (its log names the file).
* From here on `queue_p4/STOP` never goes away and no runner is launched into `queue_p4`.

## 5. Step b2: the analysis-freeze record (`g8_freeze.sh`)

```
bash $G/g8_freeze.sh
```

Runs, into a new `outputs/framelease_v4/analysis/final_<stamp>/` (one only):

```
$P framelease_v4/analysis/aggregate_v4.py --queue outputs/framelease_v4/queue_p4 \
    --specs outputs/framelease_v4/test_jobs/FULL --rl-freeze outputs/framelease_v4/rl_freeze/rl_freeze.json \
    --tuning-freeze outputs/framelease_v4/tuning/selection.json \
    --write-freeze-record outputs/framelease_v4/analysis/final_<stamp>/analysis_freeze.json \
    --cut-amendment A12 --out outputs/framelease_v4/analysis/final_<stamp>
```

(the phase driver's `aggregate_cmd` plus `--cut-amendment A12`; never `--arm-summary`, never `--analysis-freeze`), then
`g8_lib.py required` (`final_<stamp>/required_job_files.json`: the six queue copies at the G6 sha256, each sha256 cited
by the G6 entry), `g8_lib.py record`, `g8_lib.py entry --name A13`, `g8_lib.py simulate` and the applier in check mode.

`g8_lib.py record` checks, as `interim_guard.record_problems` / `load_freeze` and the driver's
`analysis_record_problems` would: schema and freeze time; trigger `cut` with `cut_amendment` `A12`; `job_files` =
`required_job_files.json` = the six queue copies at their G6 sha256 (`coverage_problems` with the required job files);
632 jobs, each a line of its own job file; the 127 kept jobs with a final outcome (`ok`, `agent_crashed`,
`sim_failure`) and the 505 cut jobs with `cut`; `analysis_code` = the five aggregator modules on disk, each sha256 cited
in PROTOCOL.md; the route-split sha256 of the registered split; `SHA256SUMS` of the directory holds
(`phase_driver.sha256sums_problems`); the aggregation guarded (`pre_freeze`, no summary, no `arm_summary.csv`, queues
`[queue_p4]`).

Expected (dry run, 17 s; aggregator 6.0 s, 63 MB on synthetic runs; real data: about 3-4 min and 300 MB, from the P1
development aggregation of 172 lines, 195 s, 307 MB):

```
outcomes: {'ok': <n>, 'pending': 505, 'sim_failure': <m>}          (pending = the cut lines before the record)
missing reasons: {'health_only': <n>, 'not_launched': 505, ...}
commit audit (R-2): INCOMPLETE, 0 run directories audited, <k> withheld (Sec. 9.11), ...
interim guard (Sec. 9.11): pre_freeze, 632 guarded rows (632 test-route), 0 released, 632 health-only, ...
analysis-freeze record outputs/framelease_v4/analysis/final_<stamp>/analysis_freeze.json: sha256 <hex>, 632 jobs,
    trigger cut. Not valid until ...
RECORD: OK
... entries/A13_entry.md (58 lines), entries/A13_spec.json; line problems: []
SIMULATE: OK
check: pre-checks passed
READY TO APPLY: bash outputs/framelease_v4/build/G8CUT/g8_apply.sh A13 outputs/framelease_v4/analysis/final_<stamp>
```

Failures:
* Aggregator exit 2 "block specs disagree with the job lines": `jobs.d` is not the registered set (step b1). Exit 2
  "no analysis-freeze record: N job lines are not final: [... (pending)]": a cut line with a run directory or a kept
  job without a final record; nothing is written but the guard log; resolve, then run `g8_freeze.sh` again (it reuses
  the directory with `--force` while no record exists). Exit 4: a guard refusal (the route split differs from the
  registration manifest): stop. Exit 1: outputs exist (resume logic of Sec. 10).
* `RECORD: PROBLEM`: the list names it; the record is never rewritten (`aggregate_v4.py` refuses an existing record).
  Move `final_<stamp>/` aside to `analysis/rejected_<stamp>/` after reading the problem, fix the cause, run again.
* `SIMULATE: PROBLEM` or the applier check stops (`STOP: ...`): nothing is written to PROTOCOL.md; the line names the
  cause (a width, a driver form, a changed file of `must_equal`).

## 6. Step c: the dated Sec. 13.2 entry A13 (`g8_apply.sh A13 FINAL_DIR`)

**Wording.** The entry follows the phase driver's G8 entry (`phase_driver.analysis_entry`, operational addition of
2026-11-15 06:40), adapted to the cut and to the coordinating session:

| phase driver G8 (`analysis_entry`) | A13 (`g8_lib.freeze_entry`) |
|---|---|
| head `* **G8 Analysis freeze** (<date>, Beijing time).` under "Phase gates" | title `**Amendment A13, <date> (Beijing time): the analysis freeze (Sec. 9.12) under the cut of Amendment A12, carried out by the coordinating session with the registered tools in place of gate G8 of the phase driver; no run, job line, criterion or analysis rule changes.**` |
| "every registered job of tiers 3-6 was final and the runner of `queue_p4` had exited; `aggregate_v4.py --write-freeze-record` wrote `<record>` (sha256; trigger, frozen)" | "Freeze. Every job that Amendment A12 keeps in tiers 3-6 was final and the runner ... had exited (last runner exit <utc>). `aggregate_v4.py <full command> --cut-amendment A12` wrote `<record>` (sha256; trigger cut, cut amendment A12, frozen)" |
| "Job status: N jobs of the 6 job files of the test freeze (entry "G6 Test freeze", record, sha256): <files>; outcomes ...; no job cut" | "Job status: 632 jobs ...: <each queue copy, tier, kept / registered lines, sha256>; outcomes ok, agent_crashed, sim_failure, cut 505. The 127 jobs kept ... are final (...); the 505 cut jobs have no runner record and no run directory and carry the outcome cut" |
| (none) | "Job files." the reduced files, the STOP file, the registered copies back in `jobs.d`, `test_freeze.py --verify` |
| "Analysis code frozen by the record: <modules>; the analysis script ... is registered in Sec. 13.2 by Amendment A10. Route split sha256" | the same, plus `verify_table1_extra.py` by Amendment A11 |
| "The aggregation that made the record ran without --arm-summary and without --analysis-freeze ... (Sec. 9.11). Its outputs and its guard log are in <dir> (`SHA256SUMS` sha256)" | the same, plus `required_job_files.json` (sha256) |
| "The record is valid from this entry on (... `interim_guard.load_freeze`); the confirmatory analysis writes its outputs into the same directory with a sha256 manifest. The phase driver stops after this entry" | "Validity." the same; the analysis writes into directories inside `final_<stamp>/`; "The phase driver stays stopped (`phase_driver/STOP`, Amendment A12): this entry takes the place of its G8 entry." |
| the manifest clause | "Manifest and seal after this entry: `MANIFEST.sha256`, N files, sha256 ..., sealed with this entry." |

The template `entries/A13_entry.md` holds the placeholders `{{datetime}}`, `{{sha256:<record>}}`,
`{{sha256:<SHA256SUMS>}}`, `{{sha256:<required_job_files.json>}}`, `{{manifest:files}}` and
`{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`; every other value is written in at generation.
`entries/A13_spec.json`: `name` A13, no tests, no in-place text, `max_new_registered` 0, `must_equal` = the record, its
`SHA256SUMS`, `required_job_files.json`, `CUT_PLAN.json`, `test_freeze.json`, `analyze_v4.py`,
`verify_table1_extra.py`, the five aggregator modules and the six queue copies at the sha256 the record was checked
with. Worked example from the dry run (synthetic counts): `dryrun/entries_example/A13_entry.md`, `A13_spec.json`, and
the sealed text `dryrun/entries_example/PROTOCOL_tail_after_A13_A14_A15.md` (every prose line at most 120 columns).

**Checks before the application (in `g8_freeze.sh`).** `g8_lib.py entry` checks the lines (no line after the title
read as a P1-driver or phase-driver entry, an amendment title, a driver heading or `### 13.2 Amendments`; the anchor
phrase absent; filled width at most 120). `g8_lib.py simulate` composes PROTOCOL.md + the filled entry exactly as the
applier does (before the anchor paragraph), reads it with `p1_driver.protocol_view` and `phase_driver.phase_view`
(no Alert, A13 read once, the other amendment titles and both drivers' entries unchanged, the record first cited by
A13), seals a copy under `/tmp/G8CUT_sim/` and calls `interim_guard.load_freeze` on it with the required job files:
accepted (`registered False` on the copy), while the registered PROTOCOL.md still refuses the record. Dry run: the
composed sha256 of the simulation equalled the sha256 the applier sealed.

**Application.**

```
bash $G/g8_apply.sh A13 outputs/framelease_v4/analysis/final_<stamp>
```

It runs `setsid nohup $X bash outputs/framelease_v4/build/AMEND2/a10r7b/apply_locked.sh $G/entries/A13_spec.json
outputs/framelease_v4/amendment_a13 > .../console.txt` detached (a10r7b RUNBOOK Sec. 1), waits for the line
`apply_locked: exit`, prints the applier's lines, then `registration.py --verify` and `g8_lib.py post`.

Expected (dry run 21.5 s): `wrapper exit 0`; `manifest difference: new [] / left [] / changed []`; `composed PROTOCOL.md
sha256 <hex>`; `--seal -> 0`; `--verify -> 0`; `newly cited manifest files: []`; then `POST: OK` with
`load_freeze: trigger cut, cut_amendment A12, registered true` and `owner A13`.
* Wrapper exit 94: completed by the wrapper; continue as after 0. Exits 92, 93, 95-98, or no exit line: a10r7b RUNBOOK
  Sec. 1 (`g8_apply.sh` stops after 1500 s without a wrapper process with exit 91: hand recovery there).
* `POST: PROBLEM`: read the list; the record is not valid for the analysis until it passes.

From the seal of A13 on, the record is valid: every test-route row may be examined.

## 7. Step d: the registered analysis (`g8_analysis.sh A13`)

```
bash $G/g8_analysis.sh A13
```

Refuses (exit 4) unless `g8_lib.py post` passes. Then, inside `F=outputs/framelease_v4/analysis/final_<stamp>`:

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
```

and `$F/ANALYSIS_OUTPUTS.sha256` (sha256 of every file below `$F`, `sha256sum -c` from the project root). The coverage
uses the 32 VAL clips, 2000 resamples, seed 20261109 (defaults) and the cited tuning freeze: the deployed envelopes are
L* = B0 and the `fl_risk` point E5 (role 'deployed'); E10 is computed with role 'not deployed'.

Expected (dry run; real-data estimates in brackets): `agg_p4` 7.4 s, 65 MB [3-4 min, 300 MB]; `agg_p1` 10.3 s [5-7
min, 300-400 MB]; `agg_p2` 7.9 s [3 min]; `analysis status registered | H5 <label> | development reasons []` (1.8 s,
128 MB); coverage 18.4 s, 117 MB (real VAL clips, same as the project); `figures status registered | reasons [] |
numbers <n>` (4.6 s, 164 MB; 7 items: fig1, fig1_scenarios, fig3, table1, table2a, table2b, table_train);
`ANALYSIS DONE: <F> (<n> files in ANALYSIS_OUTPUTS.sha256)`.

How each tool treats the cut (dry run on the 14 + 2 + 3 + 2 + 1 + 2 kept routes; no tool refused or crashed):
* `aggregate_v4.py`: the 505 cut lines are rows with `outcome pending`, `missing_reason not_launched`,
  `analysis_use False`; they enter no contrast and no arm summary.
* `analyze_v4.py`: every cell of a cut line has status `missing (not_launched)`; contrasts use the pairwise-complete
  routes (Sec. 9.8), each row reports `n` of `n_expected` and its dropped routes: H1, S-coll, S-dmr, H2 n 14 of 44 (13
  where `fl_original`'s timed-out route drops: H3); F3 n 2 of 22; H4-cl `fl_heuristic - fl_global_shield` n 3 of 22,
  `- age_only` n 8 of 22; RL-abl n 2 of 22; seed 12 and the noise floor n 1 of 15 (CI collapses to the single value,
  Pearson r empty); `fl_risk - fl_heuristic` n 2. The sign-flip test cannot reach p < 0.05 below n 6 (n 2: smallest
  p 0.5; n 3: 0.25; n 5: 0.0625): F3, H4-cl (global shield), RL-abl, seed 12 and fl_risk are 'inconclusive' by
  construction. Holm keeps the registered family sizes. Per ability: no interval below 5 routes.
* `prop1_coverage.py`: independent of the cut (offline VAL clips).
* `figures_tables.py`: renders every item. Table I: every value carries the dagger "Fewer than 44 routes"; the caption
  keeps "Mean over the 44 test routes" (fixed text of the generator); the notes list, per contrast, every dropped route
  with its reason (`table1.tex` holds 840 "not_launched" entries and a 40 KB note line in the dry run). Fig. 3: the
  kappa-1.0 points are the Table I runs on the E routes among the 14 (8 routes: 2050, 2084, 2204, 2286, 2390, 2509,
  2790, 3248), the kappa-1.5 / 2.0 points the 2 Fig. 3 routes (2390, 3248): each line joins means over different route
  sets; the caption keeps "on subset E (22 test routes)". Table II-A closed-loop panels: Age-Only and Suffix-Aligned on
  8 routes, Global-Margin on 3; Shield + Heuristic and FQI on 8, Bandit and FQI w/o lease on 2, each with the dagger.
  Fig. 1 (c): kappa 1.5 / 2.0 per ability from 2 routes, intervals only from 5 routes.
* What to do (paper side, Amendment A12 "the paper reports every result with its number of routes and labels the
  reduced blocks"): the numbers come from the registered outputs (`numbers.json`); the main-text captions and notes
  state n per row and per point and name the cut (Amendment A12) instead of the generated route lists and the
  "44 / 22 test routes" sentences; the generated dropped-route lists go to the supplement; for Fig. 3 and the
  closed-loop panels of Table II-A the paired contrasts (`family_F3.csv`, `family_H4-cl.csv`, `family_RL-abl.csv`, on the
  common routes) are the comparisons, the condition means are labelled with their own route counts. No registered file
  changes for this.

Failures: a step exits 2 or 4 with its log tail printed. `analysis status development`: `development_reasons` names it
(a missing phase for H5, a source not registered); `figures_tables.py --require-registered` then exits 4 and writes
nothing: fix the source, remove the failed subdirectory only if it holds no `SHA256SUMS`, run again (finished steps are
skipped).

## 8. Step e: the independent verification (`g8_verify.sh A13`, independent session)

Run by a session that wrote neither the aggregator nor the analysis (Sec. 9.12; Amendment A10, use rule 4; Amendment
A11, use rules 1-3):

```
bash $G/g8_verify.sh A13
```

It runs

```
verify_independent.py --queue outputs/framelease_v4/queue_p4 --analysis-freeze $F/analysis_freeze.json \
    --agg $F/agg_p4 --analysis $F/analysis --out outputs/framelease_v4/verification/final_<stamp>
verify_table1_extra.py --analysis-freeze $F --queue outputs/framelease_v4/queue_p4 --agg $F/agg_p4 \
    --analysis $F/analysis --out outputs/framelease_v4/verification/final_<stamp>_table1_extra
f1_class_report.py outputs/framelease_v4/verification/final_<stamp>_table1_extra \
    --out outputs/framelease_v4/verification/final_<stamp>_table1_extra_f1_class.json
```

(the class report only when `f1/f1_class_report.py` is at the sha256 that the A11 paragraph cites), then writes the
entry files of the two results: `entries/A14_*` (`verify_independent.py`: `verification.json` and `SHA256SUMS` by
sha256, status, verdict, differences) and `entries/A15_*` (`table1_extra.json`, `SHA256SUMS` and the class report by
sha256, status, verdict, outcome, release, differences per class), each "in its own dated Sec. 13 entry" (A10 use rule
4; A11 use rule 3; APPLY_PLAN2 step 8). Apply them in order, after reading the results:

```
bash $G/g8_apply.sh A14
bash $G/g8_apply.sh A15
```

Expected (dry run): `verify_independent: final AGREE` (1.5 s, 94 MB); `verify_table1_extra: final DIFFER` (3.5 s,
103 MB; real data: about 1-2 min, 110 MB, from the 180-run P1 development run, 102 s); `class report: <outcome>`;
A14 16 s, A15 18 s.
* `verify_independent.py` exit 1 (DIFFER): every row of `differences.csv` is resolved and its cause entered in Sec. 13
  before any of these numbers enters the paper (A10 use rule 4); A14 records the result as it is.
* Class report outcome 'verification failure': with the synthetic data it lists 40 rows in class `not_ok_record` (the
  timed-out `fl_original` job, as `v4p4_fl_original_k1.0_s11_r23658`) and 76 'unexplained' rows, all the P_both
  pairing mechanism of Sec. 1 item 7. With real data expect the same mechanism (about 14 x 3 + 13 x 2 + 2 x 4 = 76
  rows) unless A11 covers it (open point 1): then its resolution is entered in Sec. 13 before the columns GPU usage, DMR,
  action age, fallback ratio, EIR and P_both and the closed-loop R_cond enter the paper (A11 use rule 2).
* The class report stops with exit 2 when `queue_p4/status.jsonl` or `agg_p4/runs.csv` changed after the verifier ran
  (they are read at their recorded sha256): run it right after the verifier (nothing writes them after the swap).

## 9. Order and timing

| # | step | needs | dry run |
|---:|---|---|---:|
| 0 | A11 entered (parallel item), open point 1 decided | - | (stand-in: 17 s) |
| 1 | `g8_check.sh` until READY | every kept job final, runner exited | 3.4 s |
| 2 | `g8_swap.sh` | 1 | 3.7 s |
| 3 | `g8_freeze.sh` | 2 | 17.0 s |
| 4 | `g8_apply.sh A13 <F>` | 3 | 21.5 s |
| 5 | `g8_analysis.sh A13` | 4 | about 56 s (real data: about 15-20 min) |
| 6 | `g8_verify.sh A13` (independent session) | 5 | 9.0 s (real data: about 3 min) |
| 7 | `g8_apply.sh A14`, `g8_apply.sh A15` | 6, results read | 19 s + 21 s |

Job health at 2026-11-16 00:30 (step a on the project, job counts and wall times only): 34 of 127 kept jobs final; the
5 jobs that ended since the 23:30 relaunch took 220-1149 s of wall time each (mean about 690 s). At that pace the 93
pending jobs need about 18 h, i.e. the queue ends near 18:00 on 2026-11-16, not at 07:30.

## 10. Resume after an interruption

* `g8_check.sh`, `g8_swap.sh`: idempotent.
* `g8_freeze.sh`: with no `final_*` directory it starts one; with one directory without a record it redoes the
  aggregation there with `--force`; with a record it checks it again (never rewrites it) and regenerates the entry
  files. More than one `final_*`: stop (one analysis freeze).
* `g8_apply.sh NAME`: a wrapper that ended with exit 0 is not run again (`apply.out` holds `apply_locked: exit 0`); an
  interrupted wrapper: a10r7b RUNBOOK Sec. 1.
* `g8_analysis.sh`, `g8_verify.sh`: each step is skipped when its output directory holds `SHA256SUMS` (the class report
  when its file exists); a failed step leaves no `SHA256SUMS` and runs again.
* `$G/logs/steps.log` holds every tool run with its exit code.

## 11. Open points for the coordinating session

1. **P_both pairing in `verify_table1_extra.py` (Sec. 1 item 7).** With real data the R7B verification will report
   about 76 'paired' status differences without a cause in `paired_differences.csv` (P_both of shield arms against
   arms without a shield), and the class report will read 'verification failure'. A11 is not applied yet: the
   coordinating session decides whether A11 adds a pre-specified class for this mechanism (a `paired_differences.csv`
   'status' row whose analysis status reads `<metric> missing: <condition>` while the verifier's value of that metric
   on that condition is None, P_both of an arm without a shield), or whether the difference is resolved by its own
   Sec. 13 entry after the verification (A10 use rule 4). Either is decided before the R7B columns enter the paper.
2. **H5 and the log-less interrupted P1 attempts (Sec. 1 item 6).** Under the registered rule H5 reads 'contradicted'
   with 0 violations because of unaudited NO_LOG runs of interrupted P1 attempts. The paper reports the label with its
   cause (`analysis.json` h5: `unaudited_runs`, `no_log_runs`); a change of the rule is an amendment before the freeze.
3. **Queue timing.** At the observed pace the kept jobs end near 18:00 on 2026-11-16 (Sec. 9), after the paper target
   of about 11:00.
4. **Entry ids.** A13-A15 carry amendment titles because the appliers accept only those; the titles state that they
   record the freeze and the verification results.
5. **Paper-side handling of the cut** (Sec. 7): captions and notes state n and the cut; the generated route lists go to
   the supplement.
6. **Never restart the phase driver**; `phase_driver/STOP` and `queue_p4/STOP` stay (Sec. 1 item 2). Running the cut
   jobs later is a new amendment with its own freeze and analysis (Amendment A12, "Later runs").
