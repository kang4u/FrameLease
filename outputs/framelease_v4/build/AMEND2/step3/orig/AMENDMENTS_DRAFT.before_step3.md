# PROTOCOL Sec. 13.2 amendment package A3-A9: drafts

Status: DRAFTS. `framelease_v4/PROTOCOL.md` is not edited by this package. The coordinating session applies each entry
under `framelease_v4/.protocol.lock` in the order and with the steps of `APPLY_PLAN.md` (same directory). Each entry
follows the form of Amendments A1 and A2: dated title, cause, change, scope (what changes for which runs), files with
sha256, tests with log sha256, manifest-and-seal line. Where a PROTOCOL section must also change in place, the
replacement text is given under "In-place text" (the A1 pattern: the changed text names the amendment).

## Placeholders

* `{{datetime}}`: the time of application, `YYYY-MM-DD HH:MM` (Beijing time).
* `{{sha256:<path>}}`: the full 64-hex sha256 of `<path>` (project-relative) at application. Write it in full: the P1
  stage driver registers a file that is new in the manifest only when PROTOCOL.md cites its full sha256
  (`p1_driver.refresh_baseline`). For that reason the entries applied while P1 runs (A8, A5, A6) name the files that
  Amendment A3 registers without their sha256. `a3_sha256_at_drafting.txt` and the appendix list the values at
  drafting; a different value at application means the file changed after drafting, and its review status is
  re-checked first.
* `{{pytest:<log>}}`: the summary line of that pytest log (e.g. "37 passed in 64.2 s").
* `{{manifest:files}}` and `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`: the count and the sha256
  printed by `registration.py --write-manifest --force`.
* `{{...}}` elsewhere: a value named in the brackets, filled at application.

## Constraints on the inserted text (the P1 stage driver parses Sec. 13.2)

Each entry is inserted as its own paragraph block, with a blank line before and after, directly before the paragraph
that starts "Each amendment gets the date and time" (after the driver's "**Stage selections (P1, FULL).**" block if
that block exists). No line of an entry starts with `## `, with "Each amendment gets the date and time", with the
driver's heading, or with `* **<stage>**, <date>` (`p1_driver.ENTRY_RE`). The entry is the text from its bold title
line to its manifest-and-seal line; the `##` headings of this file are not inserted. Prose lines are wrapped at
120 columns; table rows stay single lines, as elsewhere in PROTOCOL.md.

---

## A3: registration of the Phase 2-7 tooling

**Amendment A3, {{datetime}} (Beijing time): registration of the Phase 2-7 tooling (no effect on any P1 run, P1 job
file, stage selection or criterion).**
* Cause. Secs. 4.1 ("Still required", items 1-4), 5.9, 7.6, 8.1, 8.6 and 9.12 require tools that did not exist at
  registration: the P2 job generator and completion check, the RL production driver and the RL freeze, the CPU stress
  bench, the arm `fl_global_shield`, a checker for Q-network and extension-arm runs, the P4-P6 job generator, the test
  freeze and the aggregator. Amendment A2 listed 21 of the 37 `framelease_v4` files below in its manifest without
  registering them; the other 16 were written later. `outputs/framelease_v4/p2_jobs/README.md` lies outside the
  manifest; the sealed PROTOCOL.md fixes it by its sha256. Each tool was built against
  `outputs/framelease_v4/p1_driver/GAP_AUDIT.md`, reviewed independently
  (`outputs/framelease_v4/build/<item>/review/REVIEW.md`; verdicts GO or GO_WITH_FIXES) and every must-fix item of
  every review is applied. This entry registers them. From this entry on, a change of any file below is an amendment.
* Change: the tools, their roles and the PROTOCOL sections they implement.

  | file | role | PROTOCOL | GAP_AUDIT |
  |---|---|---|---|
  | `framelease_v4/protocol/p2_jobs.py` | P2 job file: `fl_behaviour` at L* and d*, 44 training routes x kappa {1.0, 1.5, 2.0}, seed 11 (132 lines); input = the tuning freeze, accepted only when Sec. 13.2 cites its sha256 and PROTOCOL.md is sealed; pins `jobs_v4.code_pins([L*])` (the 49 common files + L*); in-process and `--dry-run` checks; writes outside every queue | 5.3, 8.1-8.4, 8.6 | P2-1 |
  | `framelease_v4/protocol/p2_check.py` | P2 completion check and data manifest: the final run of every job from the runner's records, the per-run criteria of `check_smoke.py` that apply to P2 (route record, config and pins, `summary_v4`, fast prefix, decisions, behaviour logging), the sha256 of every source log; writes `rl_data/p2_check.json` and, on PASS, `rl_data/data_manifest.json` | 5.3, 5.9 (dataset manifest), 8.1 ("ends with: data manifest") | P2-3 |
  | `outputs/framelease_v4/p2_jobs/README.md` | P2 procedure: checks, generation, Sec. 13.2 entry, `queue_p2`, launch, AUTORESUME line, `p2_check.py --write` | 8.1, 8.2 | P2-2 |
  | `framelease_v4/protocol/p3_rl.py` | P3 RL driver, resumable stages: dataset from the P2 manifest (reward identity per episode), P_both and the Sec. 5.8 label, `ope.select` per family with the registered grid, folds, FQE and bootstrap, refit on every training episode, distillation, export (B_pi 100 µs), deployment check, RL freeze `outputs/framelease_v4/rl_freeze/rl_freeze.json` | 4.7, 5.2-5.9 | P3-1, P3-2, P3-4, P3-5 |
  | `framelease_v4/protocol/stress_bench.py` | stress tests S1 (CPU contention), S2 (near deadline), S3 (cancellation and regression) on synthetic and recorded decision states; reports under `outputs/framelease_v4/stress/` | 7.6, 9.5 | S-1 to S-4 |
  | `framelease_v4/protocol/check_smoke_ext.py` | the `check_smoke.py` criteria for runs of `fl_full`, `fl_bandit`, `fl_fqi_nolease` and `fl_global_shield`: the `utility` criterion replaced for Q-network and extension arms, plus a `qnet` criterion (identity, absolute network path, bypass state machine, independent Q recomputation, support and margin) | 4.1, 5.7, 8.1 | A-2 |
  | `framelease_v4/arms_ext/` (`__init__.py`, `global_shield.py`, `arms_ext.py`, `agent_ext.py`, `run_closed_loop_ext.py`) | the arm `fl_global_shield`: the shield, a_det^{d*}, commit and watchdog of `fl_heuristic` with the global-margin lease (offline `GLOBAL` design) instead of the suffix lease; its own registry, agent entry and launcher; no pinned module is rebound or mutated | 4.1, 7.4 | A-1 |
  | `framelease_v4/analysis/` (`__init__.py`, `aggregate_v4.py`, `commit_audit.py`, `extra_metrics.py`, `interim_guard.py`, `manipulation.py`) | aggregator: run selection from the runner's records and the block specs, protocol-arm labels, per-run metrics (R-1), the Eq. 9 commit audit (R-2), the manipulation checks (R-3), and the Sec. 9.11 guard (test-route rows health-only before the analysis freeze) | 6, 7.6, 9.1, 9.5, 9.7, 9.8, 9.11, 9.12 | R-1, R-2, R-3 |
  | `framelease_v4/protocol/test_jobs.py` | P4-P6 job files (tiers 3-6), block specs and checks; inputs = the tuning freeze and the RL freeze only; written outside every queue | 7.2-7.5, 8.1-8.4, 8.6, 9.6, 10.1 | G-1 |
  | `framelease_v4/protocol/test_freeze.py` | test freeze: the tuning freeze, the RL freeze and every file it names, every P4-P6 job, spec and check file, every pin, the registered S1-S3 reports, the registered inputs and code, and its own sha256 manifest `outputs/framelease_v4/test_freeze/MANIFEST.sha256`; refuses while any test-route run exists | 3.3, 5.9, 7.6, 8.1, 8.3, 9.11 | G-2, G-3 |

* Details Sec. 8 leaves open, fixed by this entry.
  * P2: block number 10 (route order `random.Random(20261120)`, the 3 kappas of a route back to back, rotated by one
    per route); files `outputs/framelease_v4/p2_jobs/FULL/b10_rl_data.{jsonl,stage.json,check.json}`; queue
    `outputs/framelease_v4/queue_p2`; job ids `v4p2_fl_behaviour_<L*>_eps0.300_d<d*>_k<kappa>_s11_r<route>`. The P2
    lines keep the argument order of `rl/collection_plan.py` (`--policy-params` before `--envelope`); argparse does
    not depend on the order.
  * P4-P6: blocks `ti_main` 11 (tier 3), `f3_k` 12 (tier 4), `a_lease` 13 and `a_rl` 14 (tier 5), `s_seed12` 15 and
    `s_risk` 16 (tier 6); route order `random.Random(20261110 + block number)`; in `f3_k` the 8 arm x kappa cells
    arm-major; files `outputs/framelease_v4/test_jobs/FULL/b<NN>_<block>.{jsonl,stage.json,check.json}` and
    `index.json`; one queue `outputs/framelease_v4/queue_p4` holding the six files in name order, so a cut (Sec. 10.2)
    takes the bottom tiers first; job ids `v4<p4|p5|p6>_<protocol arm>[_<config>]_k<kappa>_s<seed>_r<route>`; every
    line carries `not_for_launch_before` = the test freeze.
  * Output layout (Sec. 8.6, "Planned for P4-P6"): `matrix/<arm>/`, `fig3/<arm>_k<kappa>/`, `ablation/<arm>/`,
    `replicates/<arm>/` under `outputs/framelease_v4/`; `rl_freeze/`, `stress/`, `test_jobs/FULL/`, `test_freeze/`.
* Departures from the GAP_AUDIT recommendations (PROTOCOL governs; none changes a run, a pin or a criterion).
  1. P2 tooling. The freeze gate accepts the tuning freeze only when its sha256 is cited in Sec. 13.2 and PROTOCOL.md
     is the sealed version (stricter than "entered in Sec. 13"). `p2_check.py` applies a superset of the GAP_AUDIT
     criteria (adds config and pins, `summary_v4`, source-log hashes); the smoke-only criteria (`actor_log`,
     `ego_found`, `pose_offset`, `tick_wall`, `run_size`) are not applied to P2, and the launcher wall time is
     reported, not judged (Sec. 8.4). Missing episodes are listed, not a failure of the check; whether P3 proceeds
     without them is open case (c) of `p3_rl.py` (default: stop). `p2_check.py` does not itself require all 132
     lines; `p3_rl.py` does (the registered P2 plan, job ids, output directories, and each run's `config.json`
     against its manifest entry), so an incomplete block cannot become the RL dataset unnoticed.
  2. `check_smoke_ext.py`. It judges Q-network runs by the code of `rl/qnet.py`, including the overrun-disable rule
     of Amendment A5, the one 64 x 64 retry of `trainers.distill` (Sec. 4.7) and the `nonfinite` bypass of `qnet.py`.
     It requires an absolute `FRAMELEASE_V4_QNET` path (Amendment A4) and accepts a Q-network utility only on the
     protocol arms `fl_full`, `fl_bandit` and `fl_fqi_nolease`. A run without any network decision (no call, or every
     call overran B_pi) is DEFERRED, not PASS. Its queue mode matches runs through `select_stage` (training routes,
     kappa 1.0, seed 11); P4-P6 runs are judged per run (`check_run_ext`).
  3. `arms_ext/` (the ten points of `outputs/framelease_v4/build/GSHIELD/DEPARTURES.md`). No pinned module is
     rebound or mutated: the extension keeps its own registry, the agent is a subclass of the pinned
     `FrameLeaseV4Agent` that overrides `setup()` only, and the launcher hands every arms_v4 arm to the pinned
     launcher unchanged (byte-identical `--dry-run` for all 8 arms) and runs `fl_global_shield` through copies of
     `prepare()` and `run()`; `tests/test_drift_guard.py` requires every copy to equal its pinned source up to the
     listed substitutions. The ego footprint is built per released candidate (it depends on each candidate's plan);
     an exact bounding-circle prefilter skips agents that cannot bind; H is bit-identical to the offline `GLOBAL`
     lease (`stage_frames.global_H`) on all 6421 recorded frames x {E5, E10, B0} (max difference 0.0), and the
     prefiltered lease costs 0.82 times the mean CPU time of the suffix lease (per candidate: 0.99 ms against 1.21 ms;
     per-frame ratio p50 0.94, p95 1.26; 4866 evaluations on every fourth recorded frame x 3 envelopes,
     `outputs/framelease_v4/build/GSHIELD/review/REVIEW.md`). The lease constants are fixed
     (`--lease-overrides` refused; T_c 0.5 s, d_safe 0.5 m, delta 0.2 m, H_bar 2.5 s); only isotropic envelopes
     without motion bins are accepted; the lease reasons are `global_*`, `min_g_m` and `tau_star_s` are None and
     `n_computed` counts the agents of the global-lease prefilter (logged only; the arm's utilities read `depth`
     only); importing the package sets `sys.dont_write_bytecode` in the agent process (import time only).
  4. `p3_rl.py`. The deployment check is a hard gate: the `featurize_forward` p99 of `rl/bench_qnet.py` must be at most
     B_pi = 100 µs (Sec. 5.7 defines B_pi as a run-time bypass only; the gate changes no network). The `calibrate`
     subcommand sets `--n-jobs` from CPU-time probes of every part of an `ope.select` task and a cost law, not from one
     timing of a full selection. The open cases of GAP_AUDIT Sec. 6 item 5 default to "stop" (exit 4): (a) a family
     without a selectable candidate, (b) a distillation agreement below 0.98 after the retry, (c) missing P2 episodes;
     the alternative (a: the a_det^{d*}-equivalent network, family "not trainable"; b: the best try; c: the valid
     episodes) is the user's decision and is entered in Sec. 13 when used. P_both is computed from the dataset and
     must equal `metrics_v4.decision_metrics` (the driver stops on a difference). The freeze hashes every file under
     `framelease_v4/rl` and the P2 gate modules. An arm is identified by its protocol arm and its network FILE sha256:
     two not-trainable families share one network name.
  5. `stress_bench.py`. Reports are written only under `outputs/framelease_v4/stress/` or
     `outputs/framelease_v4/build/` or outside the project, never onto a file of the registration manifest. Recorded
     states come from finished runs only (`entry_status` Finished and exactly one valid official record); aborted,
     running or retried attempts are skipped and listed; a run without a route id and, before the analysis freeze,
     every test-route run are refused. S3 adds 2% of offers at exactly t_commit = D. S1 refuses while a runner, CARLA,
     the P1 driver or an RL job runs, and a registered S1 refuses while a foreign process uses CPU unless
     `--accept-foreign-cpu` (recorded in the report). S2 moves D* (and D_cand when the running job's candidate is the
     active one); the lease values of the state stay as logged, so D = t_k + H (Eq. 3) does not hold in a moved state;
     the shield checks and the share admitted depend on D*, D_cand and the bounds only. S2 reports the per-kappa slack
     floors (Amendment A7).
  6. `analysis/`. Before the analysis freeze, the commit audit (R-2) of a test-route run is WITHHELD (no counts, out of
     the totals), like every other test-route outcome (Sec. 9.11); the registered H5 audit (Sec. 9.5) runs after the
     freeze over every run of every phase. A development freeze record never releases a registered test route. A
     failed secondary-metric step leaves only its own columns empty; it never removes a route with a valid DS from a
     contrast (Secs. 9.1, 9.8). The predicted expiry fallback takes L over every finished job with at least one step
     (the v2 rule uses complete jobs only; a_det^d jobs stop below the target depth by design), and cancelled GPU work
     counts the steps up to the deepest commit as used. A null commit margin passes only where the validity record
     names no relevant agent; a commit present in one log only is an ERROR. Arm summaries are keyed by protocol arm,
     candidate, kappa, seed, phase, block and split. The background-load flag is Amendment A8; the real-data
     development smokes are Amendment A9.
  7. `test_jobs.py` and `test_freeze.py`. The test freeze writes its own sha256 manifest, cited in its Sec. 13.2 entry
     and sealed with it (GAP_AUDIT G-3, recommended option); `registration.py` is not changed. The generator and the
     freeze compare `route_split.json`, `routes.json` and `envelopes/manifest.json` with the sealed registration
     manifest, and every pin except the network files and the extension sources with the registered P1 pins
     (`registration.job_pins`). The `framelease_v4/rl` sources enter the test freeze through the sha256 of
     `rl_freeze.json`, which lists them.
* Known limitations accepted by this entry (review should-fix items not applied; none affects a run or a criterion):
  the `p2_jobs.py` freeze gate accepts the freeze sha256 on any line of Sec. 13.2, not only in the driver's
  "Tuning freeze" entry; the `p2_check.py` manifest flag `terminal_only_reward` reflects a missing `metric_info.json`
  only (the authoritative flag is the dataset's); `p2_check.py` flags a job with more than 2 counted attempts as
  `retried` only.
* Not part of this entry: `framelease_v4/analysis/analyze_v4.py` (R-4), the Proposition-1 coverage (R-5), the figure
  and table generators (R-6) and a stage driver beyond P1 (E-2). Each is registered by its own entry before its first
  use; R-4 to R-6 before the analysis freeze (Sec. 9.12).
* Scope. No P1 run, P1 job file, stage selection, tuning freeze or criterion changes, and no file pinned by a job line
  changes. The agent of every arm except `fl_global_shield` imports none of these files. The P2 lines pin the 49
  common files and L*; the P4-P6 lines pin 49, 50, 51 or 55 files (Amendment A4); the 22 `fl_global_shield` runs of
  P6 (block `a_lease`) import and pin the five `arms_ext` sources.
* Files (sha256).

  | file | sha256 |
  |---|---|
  | `framelease_v4/protocol/p2_jobs.py` | `{{sha256:framelease_v4/protocol/p2_jobs.py}}` |
  | `framelease_v4/protocol/p2_check.py` | `{{sha256:framelease_v4/protocol/p2_check.py}}` |
  | `framelease_v4/protocol/p3_rl.py` | `{{sha256:framelease_v4/protocol/p3_rl.py}}` |
  | `framelease_v4/protocol/stress_bench.py` | `{{sha256:framelease_v4/protocol/stress_bench.py}}` |
  | `framelease_v4/protocol/check_smoke_ext.py` | `{{sha256:framelease_v4/protocol/check_smoke_ext.py}}` |
  | `framelease_v4/protocol/test_jobs.py` | `{{sha256:framelease_v4/protocol/test_jobs.py}}` |
  | `framelease_v4/protocol/test_freeze.py` | `{{sha256:framelease_v4/protocol/test_freeze.py}}` |
  | `framelease_v4/protocol/tests/test_p2_jobs.py` | `{{sha256:framelease_v4/protocol/tests/test_p2_jobs.py}}` |
  | `framelease_v4/protocol/tests/test_p2_check.py` | `{{sha256:framelease_v4/protocol/tests/test_p2_check.py}}` |
  | `framelease_v4/protocol/tests/test_p3_rl.py` | `{{sha256:framelease_v4/protocol/tests/test_p3_rl.py}}` |
  | `framelease_v4/protocol/tests/test_stress_bench.py` | `{{sha256:framelease_v4/protocol/tests/test_stress_bench.py}}` |
  | `framelease_v4/protocol/tests/test_check_smoke_ext.py` | `{{sha256:framelease_v4/protocol/tests/test_check_smoke_ext.py}}` |
  | `framelease_v4/protocol/tests/test_fl_full_qnet_agent.py` | `{{sha256:framelease_v4/protocol/tests/test_fl_full_qnet_agent.py}}` |
  | `framelease_v4/protocol/tests/test_test_jobs.py` | `{{sha256:framelease_v4/protocol/tests/test_test_jobs.py}}` |
  | `framelease_v4/protocol/tests/test_test_freeze.py` | `{{sha256:framelease_v4/protocol/tests/test_test_freeze.py}}` |
  | `framelease_v4/arms_ext/__init__.py` | `{{sha256:framelease_v4/arms_ext/__init__.py}}` |
  | `framelease_v4/arms_ext/global_shield.py` | `{{sha256:framelease_v4/arms_ext/global_shield.py}}` |
  | `framelease_v4/arms_ext/arms_ext.py` | `{{sha256:framelease_v4/arms_ext/arms_ext.py}}` |
  | `framelease_v4/arms_ext/agent_ext.py` | `{{sha256:framelease_v4/arms_ext/agent_ext.py}}` |
  | `framelease_v4/arms_ext/run_closed_loop_ext.py` | `{{sha256:framelease_v4/arms_ext/run_closed_loop_ext.py}}` |
  | `framelease_v4/arms_ext/tests/helpers_ext.py` | `{{sha256:framelease_v4/arms_ext/tests/helpers_ext.py}}` |
  | `framelease_v4/arms_ext/tests/test_agent_ext.py` | `{{sha256:framelease_v4/arms_ext/tests/test_agent_ext.py}}` |
  | `framelease_v4/arms_ext/tests/test_arms_ext.py` | `{{sha256:framelease_v4/arms_ext/tests/test_arms_ext.py}}` |
  | `framelease_v4/arms_ext/tests/test_drift_guard.py` | `{{sha256:framelease_v4/arms_ext/tests/test_drift_guard.py}}` |
  | `framelease_v4/arms_ext/tests/test_global_shield.py` | `{{sha256:framelease_v4/arms_ext/tests/test_global_shield.py}}` |
  | `framelease_v4/arms_ext/tests/test_launcher_ext.py` | `{{sha256:framelease_v4/arms_ext/tests/test_launcher_ext.py}}` |
  | `framelease_v4/analysis/__init__.py` | `{{sha256:framelease_v4/analysis/__init__.py}}` |
  | `framelease_v4/analysis/aggregate_v4.py` | `{{sha256:framelease_v4/analysis/aggregate_v4.py}}` |
  | `framelease_v4/analysis/commit_audit.py` | `{{sha256:framelease_v4/analysis/commit_audit.py}}` |
  | `framelease_v4/analysis/extra_metrics.py` | `{{sha256:framelease_v4/analysis/extra_metrics.py}}` |
  | `framelease_v4/analysis/interim_guard.py` | `{{sha256:framelease_v4/analysis/interim_guard.py}}` |
  | `framelease_v4/analysis/manipulation.py` | `{{sha256:framelease_v4/analysis/manipulation.py}}` |
  | `framelease_v4/analysis/tests/test_aggregate_v4.py` | `{{sha256:framelease_v4/analysis/tests/test_aggregate_v4.py}}` |
  | `framelease_v4/analysis/tests/test_commit_audit.py` | `{{sha256:framelease_v4/analysis/tests/test_commit_audit.py}}` |
  | `framelease_v4/analysis/tests/test_extra_metrics.py` | `{{sha256:framelease_v4/analysis/tests/test_extra_metrics.py}}` |
  | `framelease_v4/analysis/tests/test_interim_guard.py` | `{{sha256:framelease_v4/analysis/tests/test_interim_guard.py}}` |
  | `framelease_v4/analysis/tests/test_manipulation.py` | `{{sha256:framelease_v4/analysis/tests/test_manipulation.py}}` |
  | `outputs/framelease_v4/p2_jobs/README.md` | `{{sha256:outputs/framelease_v4/p2_jobs/README.md}}` |

* Tests (CPU, run at application with `source linux/env.sh` and then `CUDA_VISIBLE_DEVICES=''`; logs in
  `outputs/framelease_v4/amendment_a3/`):
  * `framelease_v4/protocol/tests/test_<tool>.py` for the tools `p2_jobs`, `p2_check`, `p3_rl`, `stress_bench`,
    `check_smoke`, `check_smoke_ext`, `fl_full_qnet_agent`, `test_jobs` and `test_freeze`:
    {{pytest:outputs/framelease_v4/amendment_a3/pytest_protocol_tools.log}}
    (`pytest_protocol_tools.log`, `{{sha256:outputs/framelease_v4/amendment_a3/pytest_protocol_tools.log}}`);
  * `framelease_v4/arms_ext/tests`: {{pytest:outputs/framelease_v4/amendment_a3/pytest_arms_ext.log}}
    (`pytest_arms_ext.log`, `{{sha256:outputs/framelease_v4/amendment_a3/pytest_arms_ext.log}}`);
  * `framelease_v4/analysis/tests` and `framelease_v4/arms/tests/test_metrics_realized_keys.py`:
    {{pytest:outputs/framelease_v4/amendment_a3/pytest_analysis.log}}
    (`pytest_analysis.log`, `{{sha256:outputs/framelease_v4/amendment_a3/pytest_analysis.log}}`).

  `test_test_jobs.py::LabelsTest::test_the_aggregator_loads_the_block_specs` passes: the aggregator reads the P4-P6
  block specs (schema `framelease_v4.test_stage/1`). The three logs above hold the test counts of the registered
  versions; the development runs of each tool are recorded in `outputs/framelease_v4/build/<item>/PROGRESS.md`.
* In-place text. Sec. 4.1, after item 4 of "Still required, not needed for Phase 1", the sentence: "Status
  (Amendment A3): the `fl_global_shield` lease of item 1, the aggregator of item 2 (with infractions per km), item 3
  and item 4 are implemented and registered; the analysis script, the Proposition-1 coverage and the figure and table
  generators remain required before the analysis freeze." (`fl_bandit` and `fl_fqi_nolease` of item 1: Amendment A4.)
  Sec. 8.6, "Planned for P4-P6 (generators not yet written)": replaced by the layout fixed above (Amendment A3).
* Manifest and seal after this amendment: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.

---

## A4: realisation of the ablation arms

**Amendment A4, {{datetime}} (Beijing time): realisation of the ablation arms `fl_bandit`, `fl_fqi_nolease`, `fl_risk`
and `fl_global_shield`, and the code pins of their job lines (Secs. 4.1, 7.4, 7.5, 8.3; no effect on any P1 or P2
run).**
* Cause. Sec. 4.1 defines the ablation arms by their difference from `fl_heuristic`, but the registered launcher
  `framelease_v4/arms/run_closed_loop_v4.py` accepts only the arms of `arms_v4.ALL_ARMS`, and the pinned agent accepts
  only their configurations. Three of the four ablation arms are configurations of registered launcher arms; the
  global-margin lease needs new code, which must not rebind or edit any file pinned by the P1 and P2 job lines. Two
  findings fix how the Q-network arms are identified: QNET-1 (the evaluator runs in another working directory, so a
  repository-relative `FRAMELEASE_V4_QNET` passes the launcher's `--dry-run` and then fails in every agent process
  with "Agent couldn't be set up") and `rl/qnet.py` `_canonical_sha` (the name `v4_qnet_<sha12>` hashes the network
  core without `policy_budget_s`, so it pins neither B_pi nor the provenance; two not-trainable families share one
  name).
* Change. Each protocol arm is defined as (launcher, launcher arm, configuration, identity):

  | protocol arm | launcher and launcher arm | configuration | identity checked |
  |---|---|---|---|
  | `fl_full` | `run_closed_loop_v4.py`, `fl_full` | envelope L*, utility = the network name of the `fqi` family, `--utility-env FRAMELEASE_V4_QNET=<absolute path>` | network FILE sha256 = `families.fqi.network.file_sha256` of the RL freeze |
  | `fl_bandit` | `run_closed_loop_v4.py`, `fl_full` | as `fl_full`, with the network of the `bandit` family (16 inputs) | network FILE sha256 = `families.bandit.network.file_sha256` |
  | `fl_fqi_nolease` | `run_closed_loop_v4.py`, `fl_full` | as `fl_full`, with the network of the `fqi_nolease` family (10 non-lease inputs; the pinned `QNetwork` reads its input list by feature name from the network file); the shield is unchanged | network FILE sha256 = `families.fqi_nolease.network.file_sha256` |
  | `fl_risk` | `run_closed_loop_v4.py`, `fl_heuristic` | envelope = the `fl_risk` lease point of `tuning/selection.json` (E5 or E10, Sec. 4.3), utility a_det^{d*} | envelope sha256 = the `fl_risk` point of the tuning freeze |
  | `fl_global_shield` | `arms_ext/run_closed_loop_ext.py`, `fl_global_shield` | envelope L*, utility a_det^{d*}, the fixed lease constants of Secs. 2.4 and 7.4 (no `--lease-overrides`; the configuration's v3 lease block is empty and the global lease's cap is 2.5 s) | the configuration's `extension` block (base arm `fl_heuristic`, global-lease parameters, envelope sha256) |

  * The protocol arm is recorded in three places: the job line (`protocol_arm`; `arm_name` = the launcher arm), the
    output directory (`ablation/<arm>/` for the ablation arms; `matrix/<arm>/`, `fig3/<arm>_k<kappa>/` and
    `replicates/<arm>/` for the others) and the block spec (`jobs[]`: protocol arm, route, kappa, seed,
    configuration, envelope or network sha256). The aggregator reads all three, cross-checks them, and identifies a
    Q-network run by its network FILE sha256 against the RL freeze and an `fl_risk` run by its envelope sha256 against
    the tuning freeze; a run it cannot attribute to one protocol arm enters no contrast.
  * `FRAMELEASE_V4_QNET` is an absolute path in every job line (QNET-1). `test_jobs.py` and
    `check_smoke_ext.qnet_line_problems` refuse a relative path, a network whose family or input count does not match
    the protocol arm, a network whose a_det depth is not d*, and a network file whose sha256 is not the one the RL
    freeze records.
  * The alternative of GAP_AUDIT Sec. 2 (named copies of `fl_full` registered by the extension) is not used: the
    Q-network arms run on the registered launcher path only.
* In-place text, Sec. 8.3 (Amendment A4).
  * The lead sentence reads: "Every job carries `require_sha256` for (49 files, plus the envelope, the Q-network file
    and the extension sources where they apply; Amendment A4):".
  * The last two bullets ("the envelope file, for the shield arms;" and "the Q-network file, for `fl_full`,
    `fl_bandit` and `fl_fqi_nolease`.") are replaced by:
    * the envelope file, for the arms with a lease (`fl_heuristic`, `fl_risk`, `fl_behaviour`, `fl_full`,
      `fl_bandit`, `fl_fqi_nolease`, `fl_global_shield`);
    * the Q-network FILE, at the sha256 the RL freeze records, for `fl_full`, `fl_bandit` and `fl_fqi_nolease` (the
      network name pins neither B_pi nor the provenance);
    * the five extension sources
      `framelease_v4/arms_ext/{__init__,global_shield,arms_ext,agent_ext,run_closed_loop_ext}.py`, for
      `fl_global_shield` (they are frozen into every run of the arm).
  * After the list: "Pins per job line: 49 for `fixed_deep`, `fast_only`, `fl_original`, `age_only` and
    `event_triggered`; 50 for `fl_heuristic`, `fl_risk` and `fl_behaviour`; 51 for `fl_full`, `fl_bandit` and
    `fl_fqi_nolease`; 55 for `fl_global_shield`. Every P4-P6 common pin equals the pin of the registered P1 lines
    (`registration.job_pins`)."
  * Sec. 4.1, the status sentence after "Still required" (Amendment A3), appended: "`fl_bandit` and `fl_fqi_nolease`
    of item 1 are configurations of launcher arm `fl_full` with the networks of their families (Amendment A4)."
* Scope. P4-P6 job lines (tiers 3-6): the 44 `fl_bandit` and `fl_fqi_nolease` runs and the 22 `fl_global_shield`
  runs of P6, the conditional 22 `fl_risk` runs (FULL, only if L* = B0), and the `fl_full` runs of P4-P6 (identity by
  file sha256). No P1 or P2 run, job file or pin changes; no registered or pinned file changes. The run counts of
  Sec. 10.1 are unchanged.
* Files (registered by Amendment A3; this entry fixes their behaviour as the realisation of the arms):
  `framelease_v4/protocol/test_jobs.py` (`{{sha256:framelease_v4/protocol/test_jobs.py}}`),
  `framelease_v4/arms_ext/run_closed_loop_ext.py` (`{{sha256:framelease_v4/arms_ext/run_closed_loop_ext.py}}`),
  `framelease_v4/arms_ext/arms_ext.py` (`{{sha256:framelease_v4/arms_ext/arms_ext.py}}`),
  `framelease_v4/protocol/check_smoke_ext.py` (`{{sha256:framelease_v4/protocol/check_smoke_ext.py}}`),
  `framelease_v4/protocol/p3_rl.py` (`{{sha256:framelease_v4/protocol/p3_rl.py}}`; `JOB_LINES_RULE`, the freeze's
  `job_lines`) and `framelease_v4/analysis/aggregate_v4.py` (`{{sha256:framelease_v4/analysis/aggregate_v4.py}}`).
* Tests (in the Amendment A3 logs): `test_test_jobs.py` (labels in the three places, pins 49 / 50 / 51 / 55, absolute
  network path, relabelled network caught, lease overrides refused, the aggregator reads the block specs);
  `test_launcher_ext.py` (the 55 pins, byte-identical dry runs of the 8 arms_v4 arms, fixed lease constants);
  `test_check_smoke_ext.py` (`qnet_line_problems`; QNET-1); `test_fl_full_qnet_agent.py` (16- and 10-input networks
  in the agent process of launcher arm `fl_full`); `test_aggregate_v4.py` (protocol labels, output-directory label,
  network-file and envelope identities). QNET-1 reproduction:
  `outputs/framelease_v4/build/QNET/review/repro_qnet1_review.out.json`
  (`{{sha256:outputs/framelease_v4/build/QNET/review/repro_qnet1_review.out.json}}`).
* Manifest and seal after this amendment: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.

---

## A5: Q-network disable rule, text versus code (QNET-2)

**Amendment A5, {{datetime}} (Beijing time): the overrun-disable rule of the Q-network utility, stated as the
registered code implements it (Sec. 5.7; no change of code, data, threshold or result).**
* Cause. Sec. 5.7 states the second bypass case as "more than 5% of the last 256 calls overran B_pi, which disables
  the network for the run". The registered and pinned `framelease_v4/rl/qnet.py` `QUtility` (`WINDOW = 256`,
  `MIN_CALLS_TO_DISABLE = 64`, `MAX_OVERRUN_RATE = 0.05`, lines 125-127; the rule in `select`, lines 219-232)
  disables the network only at an overrunning call, never before the 64th network call, and below 256 calls compares
  with the calls made so far, not with 256. The registered behaviour is the code's.
* Change: the registered rule.
  * n counts the network calls of the run from 1. A network call is a choice epoch (|A_feas| = 2) that reaches the
    timed forward pass; slack bypasses, disabled bypasses and forced epochs are not calls. A call overruns iff its
    wall time `v4_qnet_s` > B_pi = 100 µs.
  * At the n-th call, after recording it, let m = min(n, 256) and o = the number of overruns among the last m calls,
    this call included. The network is disabled iff all three hold: this call overran; n >= 64; o > 0.05 m, i.e.
    o >= floor(m / 20) + 1.
  * Required overruns: 4 among the first 64 calls, 5 among the first 99, 13 among the last 256 once n >= 256.
  * The disabling call is an overrun bypass: its result is discarded and a_det^{d*} is taken. From the next choice
    epoch on, every choice epoch is a `disabled` bypass for the rest of the run; that case is tested before the slack
    bypass. Nothing re-enables the network, and a call that does not overrun never disables it.
  * Consequences relative to the earlier text: the network is never disabled before call 64 (13 overruns among the
    first 63 calls, 20.6%, do not disable it); for 64 <= n < 256 the denominator is n (overruns at calls 95-99
    disable it at call 99, 5 > 4.95; overruns at calls 96-100 do not, 5 > 5.0 is false); for n >= 256 the text was
    exact (12 overruns among the last 256 calls never disable the network, 13 do).
  * Safety is unchanged: the third bypass case of Sec. 5.7 discards every overrunning result, whether or not the
    network is disabled; the rule only decides from which call on the network is no longer run. The commit check of
    Eq. 9 is unchanged.
* In-place text, Sec. 5.7, second bullet under "Bypass to a_det^{d*}", replaced by (Amendment A5): "the network has
  been disabled: at an overrunning call, once at least 64 network calls were made in the run, the network is disabled
  for the rest of the run if more than 5% of the last min(n, 256) calls overran B_pi (n = the network calls so far,
  this one included);".
* Scope. Every run whose utility is a Q-network (`fl_full`, `fl_bandit`, `fl_fqi_nolease`; P4-P6) and stress tests
  S1 and S2 (Sec. 7.6). No run, job file, pin or result changes: the runs execute the registered `qnet.py`, and
  `check_smoke_ext.py` and `stress_bench.py` already replay this rule (`QNET_THRESHOLDS['disable_rule']`,
  `stress_bench.disable_index`). Table II-B reports the bypass counts by reason under this rule.
* Files. `framelease_v4/rl/qnet.py`, unchanged: `{{sha256:framelease_v4/rl/qnet.py}}` (must equal the registered and
  pinned `53bbf8c69124519c6bb2133961695aa4f238c6d52e325f0d8e7de53008d23f3f`); the replaying checker
  `framelease_v4/protocol/check_smoke_ext.py` (registered by Amendment A3, which cites its sha256).
* Tests.
  `framelease_v4/protocol/tests/test_check_smoke_ext.py::ReviewFixesTest::test_sf4_disable_rule_is_replayed_exactly`
  (nine overrun patterns on rows of the pinned `QUtility`; the integer form floor(m / 20) + 1 for every m in
  64..256) and the three tests of `ProtocolTextTest` in `outputs/framelease_v4/build/QNET/review/test_review_qnet.py`
  (`{{sha256:outputs/framelease_v4/build/QNET/review/test_review_qnet.py}}`; no disable before call 64; 12 versus 13
  overruns of 256; the denominator below 256 calls): 4 passed
  (`outputs/framelease_v4/amendment_a5/pytest_disable_rule.log`,
  `{{sha256:outputs/framelease_v4/amendment_a5/pytest_disable_rule.log}}`; at drafting 4 passed in 0.66 s,
  `outputs/framelease_v4/build/AMEND/a5_disable_rule_tests.log`).
* Manifest and seal after this amendment: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.

---

## A6: `rl/ope.py`, a candidate whose a_det^{d*} head lacks support in a training fold

Needs the user's decision (APPLY_PLAN.md). The fix is staged in `outputs/framelease_v4/build/AMEND/staged/`; the
variant "A6 without the fix" follows the entry.

**Amendment A6, {{datetime}} (Beijing time): `framelease_v4/rl/ope.py`: a candidate whose training fold cannot fit it
is unsupported in that fold, and the selection of its family continues (Secs. 5.5-5.6; no effect on any P1, P2 or
P4-P6 run, job file or pin).**
* Cause. `ope.select` -> `_eval_fold` -> `trainers.fit_candidate` raises ValueError when the a_det^{d*} head has fewer
  than `min_support` logged samples in a training fold (`trainers._check_default_support`), or when no head has
  `min_support` samples (`TreeQ.fit`). The exception ends the selection of the whole family: no report is written and
  no other candidate or fold is evaluated. Secs. 5.5-5.6 define an unsupported candidate on the held-out data only
  (Sec. 5.5: an action head "the held-out data cannot fit"; Sec. 5.6 rule 3: an unsupported "held-out evaluation") and
  say nothing of a training fold. On the development dataset of the pilot runs (heuristic-policy data: no REFRESH
  logged at a choice epoch) at d* = 4, all three families stop with "the default action a_det^d is REFRESH at 214
  states but that head has only 0 samples" (`bandit`: 107 states). With eps 0.3 behaviour data the case arises when a
  training fold logs fewer than 30 actions of a head that a_det^{d*} needs; the P1-0 `fl_behaviour` smoke run logged
  4 choice epochs in 145 decision epochs.
* Change, `framelease_v4/rl/ope.py`.
  * New `fit_support(ds, fit_ids, cand)`: per head, the logged samples of the fold's fit episodes; the heads with at
    least `cand.min_support` samples; the heads a_det^{d*} needs on the states the fit evaluates it at (the choice
    states; for `fqi` and `fqi_nolease` also the non-terminal next states). `ok` is false exactly when
    `trainers.fit_candidate` raises one of the two support errors.
  * `_eval_fold` first applies the training-split guard of `trainers.fit_candidate` in every fold, fitted or not
    (PermissionError, with the message of `fit_candidate`, when a fit episode is not a training episode; Sec. 3.3),
    then checks `fit_support`. A fold whose fit data cannot fit the candidate is not fitted. Its record has the keys
    of a fitted fold plus `fit_unsupported` (the `fit_support` result): `unsupported_frac` 1.0, V NaN for every
    held-out episode with a choice epoch (the official DS for one without, as `fqe` does), `fqe_iterations` 0,
    `fqe_converged` false. The candidate's mean delta is None, so it cannot be selected (Sec. 5.6 rule 3). Every
    other candidate and fold is evaluated as before, and `select` returns the complete report, with `selected` None
    when no candidate is selectable.
  * Any other error of a fit still stops the selection. `trainers.py` is unchanged: `fit_candidate` still raises on
    such data, and `ope.select` no longer calls it there.
  * `framelease_v4/rl/RL_PROTOCOL.md` Secs. 5 and 6 state the rule.
  * Under the registered grid (Sec. 4.7) every candidate has `min_support` 30 and the same d*, and the `bandit` check
    (choice states) and the FQI check (also next states, which are choice states of the same episodes) need the same
    heads. A training-fold support failure therefore makes every candidate of every family unsupported in that fold:
    each family has no selectable candidate, P3 writes the three complete selection reports and stops at open case
    (a) of `p3_rl.py` (Amendment A3), whose resolution is the user's decision.
* `p3_rl.py` with the fixed `ope.py`. The driver's ValueError branch (`DEFAULT_HEAD_UNSUPPORTED`,
  `default_head_report`) is no longer reached: `select_<family>` records the family as not trainable with the reason
  of Sec. 5.6 rule 3 and `refit_<family>` stops at open case (a) (exit 4), as with the registered `ope.py`. Before
  Amendment A3 registers `p3_rl.py`, the driver changes accordingly: the branch is removed; the reason is derived from
  the fold records (`fit_unsupported` with the per-head sample counts, otherwise the held-out rule); folds without a
  fit are left out of `fqe_not_converged`; the third `SEC13_NOTES` item and the text of open case (a) state that an
  a_det^{d*} head without support in a training fold is a regular unsupported evaluation (Amendment A6);
  `OpenCasesTest.test_a_the_a_det_head_unsupported_in_a_training_fold` asserts the new report (it pins the ValueError
  path and is the only test of `test_p3_rl.py` that the fixed `ope.py` changes). The driver change is made and
  tested before Amendment A3 registers `p3_rl.py`; A3's log `pytest_protocol_tools.log` records it.
* Pins. No job line pins `rl/ope.py` or `rl/trainers.py`. Every P1 line pins `framelease_v4/arms/jobs_v4.code_pins`
  (the 49 common files; of `framelease_v4/rl` only `__init__`, `behaviour`, `features` and `qnet`) plus the envelope
  where it applies (at drafting: the 128 lines of `queue_p1/jobs.d` and the 6 registered P1 job files, 52 distinct
  paths); the P2 lines pin `jobs_v4.code_pins([L*])`, the same 49 common files and L*; the P4-P6 lines pin 49 to 55
  files (Amendment A4), none of them `ope.py` or `trainers.py`. No agent process imports either file (`behaviour` ->
  `qnet` -> `features`). Both are files of the registration manifest and of the P1 stage driver's registered
  baseline.
* Scope. The P3 selection (Secs. 5.5-5.6) only. Where every training fold supports every candidate, the selection
  reports are byte-identical to those of the registered `ope.py` (15 cases: toy SMDPs at d* 10 and 4 and the pilot
  dataset at d* 10, every family; each with the smoke grid `trainers.grid(smoke=True)` and 4 folds on the toy SMDPs, 2
  on the pilot dataset, not the registered grid with 5 folds). Where a training fold lacks support, the registered
  code ends the family with
  ValueError and the fixed code returns the complete report with the candidate unsupported in that fold. No P1, P2 or
  P4-P6 run, job line or pin changes. The RL freeze (Sec. 5.9) records the new sha256 with every `framelease_v4/rl`
  source.
* In-place text, Sec. 5.5, the last sentence of "Value of an episode": "A candidate that needs an action head the
  held-out data cannot fit is unsupported and cannot be selected; so is a candidate in a fold whose training data
  cannot fit it (Amendment A6)."
* Files. Changed: `framelease_v4/rl/ope.py` (`269e8e8392c308ba1ceb4adcd82bbca3736e98bc7ac5e62e5b86c570b316405e` ->
  `{{sha256:framelease_v4/rl/ope.py}}`), `framelease_v4/rl/RL_PROTOCOL.md`
  (`27f0ecebdcb0ec0431c84a0659f0a748b07544900e5f7547d0fcb5c53ec4e8a3` -> `{{sha256:framelease_v4/rl/RL_PROTOCOL.md}}`).
  New: `framelease_v4/rl/tests/test_ope_support.py` (`{{sha256:framelease_v4/rl/tests/test_ope_support.py}}`).
  The installed files equal the staged copies `outputs/framelease_v4/build/AMEND/staged/{ope.py,RL_PROTOCOL.md,
  test_ope_support.py}` (unified diffs `ope.patch`, `RL_PROTOCOL.patch`).
* Tests.
  * Regression test `test_ope_support.py` (8 tests, 189 subtests), run in an overlay copy of the tree (every
    project-root entry a symlink to the tree except a copied `framelease_v4/`; `outputs/` a directory of symlinks):
    with the registered `ope.py` 4 failed, 4 passed (`fit_support` missing, twice; the ValueError of
    `trainers._check_default_support`, twice; the split-guard test passes, as the registered guard is kept;
    `staged/logs/pytest_ope_support_registered.log`,
    `{{sha256:outputs/framelease_v4/build/AMEND/staged/logs/pytest_ope_support_registered.log}}`); with the fixed
    `ope.py` 8 passed (`staged/logs/pytest_ope_support_patched.log`,
    `{{sha256:outputs/framelease_v4/build/AMEND/staged/logs/pytest_ope_support_patched.log}}`). Its tests: the tree's
    own `ope.py` is tested; `fit_support` is false exactly when `fit_candidate` raises, on 180 random folds of the
    three families; the fold record; every family of the smoke grid at d* = 4 completes with each candidate
    unsupported in the fold that lacks REFRESH samples and fitted in every other fold; a family continues and selects
    the candidate whose `min_support` the fold meets; a non-training episode among the fit episodes raises the
    PermissionError of `fit_candidate` in every family although no fold is fitted; a supported selection keeps the
    registered fold records; any other ValueError of a fit still stops the selection.
  * Registered against fixed `select` (`staged/compare_supported.py`, output `staged/compare_supported.out.json`,
    `{{sha256:outputs/framelease_v4/build/AMEND/staged/compare_supported.out.json}}`): 18 cases, the 15 supported
    ones byte-identical, the 3 pilot cases at d* = 4 ValueError (registered) and complete reports with `selected` None
    (fixed).
  * At application (logs in `outputs/framelease_v4/amendment_a6/`): `framelease_v4/rl/tests`,
    {{pytest:outputs/framelease_v4/amendment_a6/pytest_rl.log}} (`pytest_rl.log`,
    `{{sha256:outputs/framelease_v4/amendment_a6/pytest_rl.log}}`; at staging 59 passed, 3 skipped without the
    official stack, 189 subtests).
  * The unchanged driver with the fixed `ope.py`, in the overlay copy: `test_p3_rl.py` gives 37 passed and 3 failed,
    namely the pinned ValueError path and two path checks that fail only in the overlay copy
    (`staged/logs/pytest_p3_rl_overlay_patched.log`,
    `{{sha256:outputs/framelease_v4/build/AMEND/staged/logs/pytest_p3_rl_overlay_patched.log}}`); the development
    run at d* = 4 stops at open case (a) with exit 4 (`staged/logs/p3_rl_dev_dstar4_overlay_patched.log`,
    `{{sha256:outputs/framelease_v4/build/AMEND/staged/logs/p3_rl_dev_dstar4_overlay_patched.log}}`).
* Manifest and seal after this amendment: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.

**Variant: A6 without the fix** (the user keeps the registered `ope.py`).

**Amendment A6, {{datetime}} (Beijing time): a candidate whose a_det^{d*} head lacks support in a training fold
(Secs. 5.5-5.6; no change of code; no effect on any run).**
* Cause. `ope.select` -> `_eval_fold` -> `trainers.fit_candidate` raises ValueError when the a_det^{d*} head has
  fewer than `min_support` logged samples in a training fold (`trainers._check_default_support`) or no head has
  `min_support` samples (`TreeQ.fit`); the exception ends the selection of the whole family. On the development
  dataset of the pilot runs at d* = 4 all three families stop this way.
* Rule. The registered behaviour stays. `p3_rl.py` (Amendment A3) catches exactly this ValueError
  (`DEFAULT_HEAD_UNSUPPORTED`), writes a selection report with every candidate unevaluated and the logged actions of
  each fold's fit episodes (`default_head_report`), records the family as not trainable with that reason, and stops
  at open case (a) (exit 4); any other ValueError stops the driver. Under the registered grid the failure is shared by
  every candidate of every family in that fold, so the outcome (no selectable candidate in any family) equals that of
  Sec. 5.6 rule 3; the selection reports of the affected families hold no per-fold evaluation.
* Scope, files and tests. P3 only; `framelease_v4/rl/ope.py` (`{{sha256:framelease_v4/rl/ope.py}}`, must equal the
  registered `269e8e8392c308ba1ceb4adcd82bbca3736e98bc7ac5e62e5b86c570b316405e`), `framelease_v4/protocol/p3_rl.py`
  (Amendment A3); `test_p3_rl.py::OpenCasesTest::test_a_the_a_det_head_unsupported_in_a_training_fold` (Amendment A3
  logs).
* Manifest and seal after this amendment: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.

---

## A7: Table II-B, the S2 grid (two alternatives; the user chooses one)

Common cause of both drafts. Eq. 5 admits an action only when the slack D* - t exceeds its floor L_pi + L_a +
L_commit + R_a + eps; with the fast prefix, L_REFRESH alone is 0.45-1.04 s at kappa 1.0 and above 0.6 s at kappa 1.5
and 2.0. Most of the registered S2 grid, [-0.1, 0.6] s in 10 ms steps (71 values), therefore admits no action, and the
check "admitted actions whose bound >= D*: must be 0" (Sec. 7.6) runs only on the band above the floor. Development S2
runs of `framelease_v4/protocol/stress_bench.py` (labelled "development run, not the registered S2"):

| states | kappa | slack floor of the first admissible action, min / p50 / max (s) | grid values at or below every state's floor | first admitting grid value | admitted actions checked per network |
|---|---|---|---:|---|---:|
| recorded: the 14 P1-0 smoke runs (route 18305), 1000 states | 1.0 | 0.503 / 0.514 / 1.091 | 61 of 71 | 0.51 s | 8352 |
| synthetic, 5000 states (4843 with an active candidate) | 1.0 | 0.455 / 0.778 / 1.115 | 56 of 71 | 0.46 s | 2349 |
| synthetic | 1.5 | 0.655 / 1.124 / 1.639 | 71 of 71 | none | 0 |
| synthetic | 2.0 | 0.854 / 1.481 / 2.153 | 71 of 71 | none | 0 |

Sources: `outputs/framelease_v4/build/STRESS/s2_dev_recorded_smoke_report_v2.json` and `s2_dev_report_v2.json`
(fields `slack_floor` and `networks.<name>.by_kappa`). Every admitted action in these runs had its bound below D*
(0 violations).

### A7a: the registered grid stays; Table II-B reports the slack floor next to it

**Amendment A7, {{datetime}} (Beijing time): the Eq. 5 slack floor is reported next to the registered S2 grid
(Sec. 7.6, Table II-B; no change of grid, run or criterion).**
* Cause. The registered S2 grid lies mostly below the Eq. 5 slack floor of the decision states: on the 1000 recorded
  P1-0 smoke states (kappa 1.0) 61 of its 71 values admit no action for any state (floor min 0.503 s, p50 0.514 s),
  and on synthetic states at kappa 1.5 and 2.0 none of them admits an action (floor min 0.655 s and 0.854 s). The
  "must be 0" check therefore covers only the band from the floor to 0.6 s at kappa 1.0 and no admitted action at
  kappa 1.5 and 2.0.
* Change. The S2 grid, the states and the criteria stay as registered. Table II-B reports next to every S2 result,
  per kappa: the distribution of the states' slack floor (min, p50, max of the first-admissible slack), the number of
  grid values at or below every state's floor, the first admitting grid value and the number of admitted actions
  checked against D* (the S2 report fields `slack_floor` and `by_kappa`). The S2 statement in the paper names the
  checked band: "0 of N admitted actions at slack s in [first admitting value, 0.6] s had a bound >= D*".
* In-place text, Sec. 7.6, S2, a fourth item of "Report": "per kappa, the Eq. 5 slack floors of the states (min, p50,
  max), the grid values at or below every state's floor, the first admitting grid value and the admitted actions
  checked (Amendment A7)."
* Scope. The registered S2 runs (P3 on synthetic states, Phase 7 on recorded states) and the Table II-B text. No code
  change (`stress_bench.py`, Amendment A3, writes these fields), no run, job file or pin changes.
* Files. `framelease_v4/protocol/stress_bench.py` (`{{sha256:framelease_v4/protocol/stress_bench.py}}`, Amendment
  A3); development reports `outputs/framelease_v4/build/STRESS/s2_dev_recorded_smoke_report_v2.json`
  (`{{sha256:outputs/framelease_v4/build/STRESS/s2_dev_recorded_smoke_report_v2.json}}`) and
  `outputs/framelease_v4/build/STRESS/s2_dev_report_v2.json`
  (`{{sha256:outputs/framelease_v4/build/STRESS/s2_dev_report_v2.json}}`).
* Tests. `framelease_v4/protocol/tests/test_stress_bench.py::S2Test::test_slack_floors_and_admitted_actions_per_kappa`
  (Amendment A3 log `pytest_protocol_tools.log`).
* Manifest and seal after this amendment: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.

### A7b: a supplementary grid relative to each state's own slack floor

**Amendment A7, {{datetime}} (Beijing time): a supplementary S2 grid relative to each state's Eq. 5 slack floor
(Sec. 7.6, Table II-B; the registered S2 grid, runs and criteria stay; the supplementary results are labelled
supplementary).**
* Cause. Eq. 5 admits an action only above the state's slack floor L_pi + L_a + L_commit + R_a + eps. On the 1000
  recorded P1-0 smoke states (kappa 1.0) 61 of the 71 registered grid values admit no action for any state (floor
  min 0.503 s, p50 0.514 s, first admitting value 0.51 s); on synthetic states at kappa 1.5 and 2.0 none of them
  admits an action (floor min 0.655 s and 0.854 s). The "must be 0" bound check is therefore exercised at kappa 1.0
  only on the band 0.51-0.60 s on the recorded states (0.46-0.60 s on the synthetic states), and on no admitted action
  at kappa 1.5 and 2.0 (development reports below).
* Change.
  * The registered S2 runs and is reported unchanged. Next to every S2 result, Table II-B reports per kappa the
    distribution of the states' slack floor (min, p50, max), the grid values at or below every state's floor, the
    first admitting grid value and the admitted actions checked (report fields `slack_floor` and `by_kappa`).
  * In addition, every S2 run (P3 synthetic, Phase 7 recorded) repeats the sweep on a grid relative to each state's
    own floor f(state), the first-admissible slack of the state (Eq. 5: L_pi + L_a + L_commit + R_a + eps, minimised
    over the actions the state can admit at some slack; `stress_bench.slack_floor(state)['any']`): D* = t + f(state)
    + delta for delta in [-0.1, 0.6] s in 10 ms steps (71 values); D_cand moves with D* exactly as in the registered
    sweep. A state that admits no action at any slack (no newer frame and REFINE excluded) has no floor; it is
    counted and not swept. Reported per delta and per kappa: the share admitted, the admitted actions whose bound >= D*
    (must be 0), the Q-network bypass rate split into its near-deadline and CPU-timing parts. The results appear in
    Table II-B and its supplement under the label "supplementary: S2 relative to the slack floor" and never replace
    the registered S2.
  * Tool change in `framelease_v4/protocol/stress_bench.py`: an option `s2 --grid relative` (default `registered`)
    that sweeps delta per state with the registered checks; the report records `grid: relative_to_floor`, the offsets
    and, per state, f(state); a registered run of the relative grid is labelled supplementary. Tests: every state
    with a floor admits an action from the first positive delta on; the bound check is exercised at every kappa (a
    shield without eps or without R_REFINE yields admitted actions with bound >= D*, as for the registered grid); the
    registered grid's report is byte-identical with and without the new code path. The change and its review precede
    the application of Amendment A3, which then registers the extended `stress_bench.py`.
* In-place text, Sec. 7.6, S2, a fourth item of "Report": "per kappa, the Eq. 5 slack floors of the states (min, p50,
  max), the grid values at or below every state's floor, the first admitting grid value and the admitted actions
  checked (Amendment A7)"; and after the list: "Supplementary (Amendment A7): the same sweep with
  D* = t + f(state) + delta, f the state's first-admissible slack, delta in [-0.1, 0.6] s in 10 ms steps; reported as
  supplementary, never in place of the registered grid."
* Scope. S2 reports and Table II-B only. No closed-loop run, job file or pin changes; the registered grid and its
  criterion are unchanged.
* Files. `framelease_v4/protocol/stress_bench.py` (`{{sha256:framelease_v4/protocol/stress_bench.py}}`, with the
  option) and `framelease_v4/protocol/tests/test_stress_bench.py`
  (`{{sha256:framelease_v4/protocol/tests/test_stress_bench.py}}`), both registered by Amendment A3; development
  reports `outputs/framelease_v4/build/STRESS/s2_dev_recorded_smoke_report_v2.json`
  (`{{sha256:outputs/framelease_v4/build/STRESS/s2_dev_recorded_smoke_report_v2.json}}`) and
  `outputs/framelease_v4/build/STRESS/s2_dev_report_v2.json`
  (`{{sha256:outputs/framelease_v4/build/STRESS/s2_dev_report_v2.json}}`).
* Tests. `test_stress_bench.py`, the relative-grid tests above:
  {{pytest:outputs/framelease_v4/amendment_a7/pytest_stress_bench.log}} (`pytest_stress_bench.log`,
  `{{sha256:outputs/framelease_v4/amendment_a7/pytest_stress_bench.log}}`); a development relative-grid S2 run on the
  recorded smoke states (`{{path and sha256 of the report}}`).
* Manifest and seal after this amendment: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.

---

## A8: background load during P1 and the 2026-11-11 pause

**Amendment A8, {{datetime}} (Beijing time): background CPU load during P1, its countermeasures, and the pause of
2026-11-11 15:36-23:39 (Secs. 2.3, 8.4, 9.7, 11.2 item 3; no run repeated or excluded, no selection rule changed).**
* Cause. The runtime charges the measured CPU time of every scheduler boundary and the measured CUDA-event time of the
  prefix to the simulated timeline (Sec. 2.3), so CPU load from other processes inflates the charged times (threat
  11.2 item 3). Background load on 2026-11-11: 13:20-13:45 the review of the P1 stage driver (tests); 13:59-15:20 the
  builds and reviews of the Phase 2-7 tooling (tests at nice 19 on every core); from about 15:21 a CPU-bound platform
  of another project on the same machine. Measured on every final P1 run up to the pause (`summary.json`
  `prefix_cost_s`; the 35 runs of the block `ref`, kappa 1.0; table in
  `outputs/framelease_v4/validity_notes/background_load_20261111.md`), by start time: 12:29-13:22, 16 runs, prefix
  p50 0.4161-0.4221 s (median 0.4176 s); 13:25, 0.4246 s; 13:29-15:00, 12 runs, 0.4257-0.4760 s, p95 up to 0.5334 s
  (the largest p50, Fast Only at 14:42, is 14% above the idle median); 15:07 and 15:13, while the builds paused,
  0.4242 s and 0.4210 s; 15:16-15:28, 4 runs, 0.4270-0.4635 s. Every run stayed inside the Sec. 9.7 band
  kappa x [0.35, 0.60] s.
* Countermeasures, from 15:35. No concurrent build of the tooling; every CPU process of the work that runs while a
  closed-loop job runs is pinned to the E-cores 12-15 (`taskset -c 12-15`), at nice 19 and idle I/O class, one
  process at a time, with one BLAS thread. The runner, the disk watchdog and the P1 stage driver keep nice 0.
* The pause. On the user's instruction (translated: "pause DAC first; let CSMH finish running, then I will tell
  you"; CSMH is the other project's platform), the P1 stage driver stopped at 15:36:33
  (`outputs/framelease_v4/p1_driver/STOP`) and the runner was stopped by SIGTERM at 15:36:37 (exit 4). At that time
  42 jobs of `queue_p1` were final (the 7 P1-0 smoke jobs and 35 `ref` jobs) and 86 were pending. The
  running job `v4p1_fixed_deep_k1.0_s11_r28093` (attempt 1, run directory
  `tuning/ref/fixed_deep/runs/20261111T073306_dbd64835`) ended with "runner received signal 15" and was not counted:
  it used no retry (Sec. 8.4), the stage selection never uses an uncounted attempt (Sec. 4.2), and the aggregator never
  selects it (R-1) but audits its commits (R-2). On the user's word, P1 resumed at 23:39 after these checks: no process
  of the other project and no CARLA process alive, the GPU free; the CARLA install used by P1
  (`/home/kang/opt/CARLA_0.9.15` -> `/opt/csmh-joint-runtime/carla`) unchanged, the symlink intact and the 22 files of
  `outputs/framelease_v4/validity_notes/carla_fingerprint_20261111.sha256` (written at the pause) verified with
  `sha256sum -c`; `registration.py --verify` both seals OK. The STOP file was kept as
  `outputs/framelease_v4/p1_driver/STOP.20261111_pause.resolved.txt`. The runner (nice 0) restarted the interrupted job
  as attempt 2, final at 23:46:24 (counted; prefix p50 0.4193 s, inside the idle band). One development aggregation
  (Amendment A9; 23:39:44-23:40:06, E-cores, nice 19) overlapped the first minute of that attempt.
* Background-load flag (aggregator R-3, `framelease_v4/analysis/manipulation.py`). Every run's charged prefix p50 is
  compared with the idle band kappa x [0.416, 0.426] s, the pilot range of Sec. 9.7 (registered before P1; the 16
  runs of 12:29-13:22 lie inside it): `bg_load_status` within, above or below, and `bg_load_excess_s`, reported per
  run and per protocol arm and kappa. The flag is reported, never used to exclude a run or a route: the analysis
  population and the contrasts stay those of Secs. 9.1 and 9.8. At the pause, 15 of the 35 `ref` runs were above the
  band (8 Fixed Deep, 7 Fast Only), all started at 13:29 or later.
* In-place text, Sec. 11.2 item 3, the last sentence ("The runner records GPU samples; CPU load is reported from the
  run logs where available."), replaced by (Amendment A8): "The runner records GPU samples. CPU load is measured: every
  run's charged prefix p50 is compared with the idle band kappa x [0.416, 0.426] s (the pilot range of Sec. 9.7) and
  flagged, never excluded (Amendment A8)."
* Scope. The P1 `ref` block (the untuned references Fixed Deep and Fast Only on T22, reported for context, never
  selected; Sec. 4.8) holds every run measured under the background load; no stage selection had been made at the
  pause. No run is repeated, excluded or reweighted, and no selection rule, criterion or job file changes. Table I,
  Fig. 3 and the training-route operating-point table report the flag counts per arm; the paper states the threat
  with these numbers.
* Files. `outputs/framelease_v4/validity_notes/background_load_20261111.md`
  (`{{sha256:outputs/framelease_v4/validity_notes/background_load_20261111.md}}`),
  `outputs/framelease_v4/validity_notes/carla_fingerprint_20261111.sha256`
  (`{{sha256:outputs/framelease_v4/validity_notes/carla_fingerprint_20261111.sha256}}`),
  `outputs/framelease_v4/p1_driver/STOP.20261111_pause.resolved.txt`
  (`{{sha256:outputs/framelease_v4/p1_driver/STOP.20261111_pause.resolved.txt}}`), the runner's records of the
  interrupted and the counted attempt (`outputs/framelease_v4/queue_p1/status.jsonl`, the two `end` records of
  `v4p1_fixed_deep_k1.0_s11_r28093`); the flag is computed by `framelease_v4/analysis/manipulation.py` (registered
  by Amendment A3, which cites its sha256).
* Tests. `framelease_v4/analysis/tests/test_manipulation.py` (the band check with the edges 0.416 s and 0.426 s and
  its "reported, never excluded" rule): {{pytest:outputs/framelease_v4/amendment_a8/pytest_manipulation.log}}
  (`outputs/framelease_v4/amendment_a8/pytest_manipulation.log`,
  `{{sha256:outputs/framelease_v4/amendment_a8/pytest_manipulation.log}}`). The per-run prefix p50 of the aggregator
  equals the table of the validity note (e.g. 12:29:59 Fixed Deep 0.4200 against 0.4201; 14:42:06 Fast Only 0.4759
  against 0.4760; `outputs/framelease_v4/build/AGG/smoke_B/`).
* Manifest and seal after this amendment: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.

---

## A9: Sec. 9.12 deviation, the aggregator's development data

**Amendment A9, {{datetime}} (Beijing time): the aggregator was developed with read-only runs on finished P1
training-route runs (Sec. 9.12; no test-route result examined; no effect on any run or criterion).**
* Cause. Sec. 9.12 states that `aggregate_v4.py` and `analyze_v4.py` "are written and tested on synthetic CSVs only".
  The aggregator (`framelease_v4/analysis/`, Amendment A3) was tested on synthetic run directories and, in addition,
  run read-only on the finished runs of `outputs/framelease_v4/queue_p1`: the P1-0 smoke runs and the P1 `ref` runs,
  all on training routes, which are examined by design (Sec. 9.11: "Training-route results are examined by design
  (Phase 1, D1, Phase 3)").
* What was run (every execution on real data, 2026-11-11).
  * Seven development aggregations over the 128 jobs of `queue_p1` (42 final: the 7 P1-0 smoke jobs and 35 `ref`
    jobs) into four output directories: `outputs/framelease_v4/build/AGG/smoke_A` three times (18:57, then 18:58 and
    19:00 with `--force`), `smoke_B` once (19:18), `smoke_C` twice (19:35, then 19:38 with `--force`), all during the
    pause, and `smoke_D` once (23:39:44-23:40:06).
  * Probe executions of refused requests on the same data into `smoke_C` (19:35, `--force`, outputs unchanged):
    `--arm-summary test` and `all` and `--analysis-freeze` with an invalid record (exit 4), `--write-freeze-record`
    (exit 2: 86 jobs not final).
  * A guard check over 6 `ref` jobs, run twice (19:36 and 19:38; `smoke_C_guard`: the training route 17569 declared
    an extra test route to exercise the Sec. 9.11 guard on real logs).
  * Two determinism runs of the independent review (`build/AGG/review/det_1`, `det_2`, 19:48-19:50).
  * Their outputs were written only under `outputs/framelease_v4/build/AGG/`. No test-route run existed; none was
    read. The values were used to check the code (hand recomputation of DS, RC, infractions per km, DMR, EIR, R_cond,
    P_both, prefix p50, lease utilization and premature expiry from the raw logs of 5 runs, all equal), never to
    choose a metric, a rule or a parameter of the analysis.
* Rule from this entry on. `analyze_v4.py` (R-4) is written and tested on synthetic CSVs only, as Sec. 9.12 states.
  During development the aggregator runs on training-route runs (P1, P2) only; before the analysis freeze it shows
  test-route runs as job health only (the Sec. 9.11 guard, Amendment A3).
* In-place text, Sec. 9.12, after "Both are written and tested on synthetic CSVs only.": "The aggregator was also run
  read-only on finished P1 training-route runs during development (Amendment A9)."
* Scope. No run, job file, selection or criterion changes; the registered analysis is unchanged.
* Files. `framelease_v4/analysis/aggregate_v4.py` (`{{sha256:framelease_v4/analysis/aggregate_v4.py}}`) and
  `framelease_v4/analysis/interim_guard.py` (`{{sha256:framelease_v4/analysis/interim_guard.py}}`), both
  Amendment A3, whose docstrings state this deviation; the output manifests of the development runs (each written by
  the last execution into its directory) `outputs/framelease_v4/build/AGG/smoke_A/SHA256SUMS` (`{{sha256:outputs/framelease_v4/build/AGG/smoke_A/SHA256SUMS}}`),
  `smoke_B/SHA256SUMS` (`{{sha256:outputs/framelease_v4/build/AGG/smoke_B/SHA256SUMS}}`), `smoke_C/SHA256SUMS`
  (`{{sha256:outputs/framelease_v4/build/AGG/smoke_C/SHA256SUMS}}`), `smoke_C_guard/SHA256SUMS`
  (`{{sha256:outputs/framelease_v4/build/AGG/smoke_C_guard/SHA256SUMS}}`) and `smoke_D/SHA256SUMS`
  (`{{sha256:outputs/framelease_v4/build/AGG/smoke_D/SHA256SUMS}}`).
* Tests. `framelease_v4/analysis/tests/test_interim_guard.py` (health-only rows before the freeze, a development
  record never releases a registered test route; Amendment A3 log `pytest_analysis.log`).
* Manifest and seal after this amendment: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.

---

## Appendix: sha256 at drafting (2026-11-12, after the review fixes; for the check at application)

A value at application that differs from this list means the file changed after drafting; its review status is
re-checked before the entry is applied. Files staged for A6 are installed byte-identical.

```
e201064a33be799a7342df90ce0e4265c760a481daaa674c03b72b04710f4d55  framelease_v4/analysis/__init__.py
9daae5c32e4aff6dcc4e7a63a0d34d989a34e164aa2587caf15ef10ee22e81fc  framelease_v4/analysis/aggregate_v4.py
96dd22c424ca2263c85843d31fd63bf5ae9019d6aa60c8ea35275b9126bff279  framelease_v4/analysis/commit_audit.py
53050f6bed5aa48054d5217832fb84ed4089b3ae80e8fdcf965769af2af79c4c  framelease_v4/analysis/extra_metrics.py
5453a3573e7cca958cad1bc1c44d53995a11e034e251bba634fe09390efed9c7  framelease_v4/analysis/interim_guard.py
aa5965620b8ea0177b00ba584dbf447379d927919d300fcacddeb2885ac9a953  framelease_v4/analysis/manipulation.py
81c2a17cb940ac82dc3c12bf659986b4a1eaf7568b2b2baefa439e7333a8f07a  framelease_v4/analysis/tests/test_aggregate_v4.py
8e4cb39d46b2ce9d95885709e0afb951ccdfb7d96026850ad34a3d60be51a985  framelease_v4/analysis/tests/test_commit_audit.py
1587fb40872ebf6895defd58030fe2b347e723333e0dd508bdcea6284488b632  framelease_v4/analysis/tests/test_extra_metrics.py
8531bf2b048266d6816f0eeaab4afdf89907541833b3abbfd734370d027647f0  framelease_v4/analysis/tests/test_interim_guard.py
893423604b097d3996f19ca0434ee92175f52617a02ce1f4ab68167481249425  framelease_v4/analysis/tests/test_manipulation.py
405ee5c3ba30cf9aa8e634710e980c72494542bc2502a9c2a6154fdf2e47c4e4  framelease_v4/arms_ext/agent_ext.py
456bb04fa8564bf208f8b863f7eabae3f91ad57740c82431a60d02dd87eebdce  framelease_v4/arms_ext/arms_ext.py
885d56ee0d45c533b7d6f2a72ae50f6b2d9d7f018fd3d99226e536b48f8abc41  framelease_v4/arms_ext/global_shield.py
3932f70fcc48605d4f36a86097084cfeb8ad66a0a4a9c5d575a5d15a2ad1299e  framelease_v4/arms_ext/__init__.py
4e5968ede4f2b3292ed74cf3346e8a5c962bcd23e457a1bf02ec5549564e808c  framelease_v4/arms_ext/run_closed_loop_ext.py
64e29d34e1e982f023d5562ec2f44ece93c08795c13412674f433859fdd1957c  framelease_v4/arms_ext/tests/helpers_ext.py
11f870d3f06bc66da4e5a06cfe71bbf7681de797e83c828f227d7889ddf8b6af  framelease_v4/arms_ext/tests/test_agent_ext.py
d93201ce0afe434cc473add3ac7718d9db716781c2871f6a6967672f5f030f4e  framelease_v4/arms_ext/tests/test_arms_ext.py
fdd3ff374c1cbf54b3f9a009d9d0b662e4ab9ecf61723350a24700aaef142115  framelease_v4/arms_ext/tests/test_drift_guard.py
495615aede7a08a15849606d12da06eb63655c358fef5856011a636ebb8d4393  framelease_v4/arms_ext/tests/test_global_shield.py
5cdb14358b43c516beb97b5959743156bc622931143ebeb09b282d80dacf0eee  framelease_v4/arms_ext/tests/test_launcher_ext.py
584cbdc19c2fa547c59e632974b923a962da141f667eebad064e70d0fc632210  framelease_v4/protocol/check_smoke_ext.py
830482d14745cfdc5f53b2cb498cd8628903a09ec85e355120ff54bf1433eb4b  framelease_v4/protocol/p2_check.py
104408ee6f096f1ca16b72230ba1c8eb5e85623b0c675cfcadd63630bea97377  framelease_v4/protocol/p2_jobs.py
3effcb39677cb8a285288af89d776326cb334e15d2ced8a54b534f1367e931ca  framelease_v4/protocol/p3_rl.py
2e49890413fdf672d7c60d72b77c08dc57eeaf23954069f61babd511bbc8ae5d  framelease_v4/protocol/stress_bench.py
866f350ee8966b385c5e806725d475f8edb5b00a247c4f30bd14030a5da471dd  framelease_v4/protocol/test_freeze.py
2ea6899d07b990f244d3481366eea2dec02e24cbb3af4944049ac78b36639151  framelease_v4/protocol/test_jobs.py
b73a029cc88e30c7abc60ec8a84fb52a312c0e5badded437c140057f676a2fb3  framelease_v4/protocol/tests/test_check_smoke_ext.py
30de3b6e6f8bfa6cf8984f7d72158ce82979bc285bde61cadc9139673e2b28c2  framelease_v4/protocol/tests/test_fl_full_qnet_agent.py
edd09fdfbd4c6ce9f6650ce1b3f04dee91e849f0ae00f56b65d1bba54d567961  framelease_v4/protocol/tests/test_p2_check.py
87a6f7682469c8900774ade51bf8ac81d0ef6d1d1375303a443c207359821a81  framelease_v4/protocol/tests/test_p2_jobs.py
0060405b8bc4cf320f848d4c68c4d76de12e777547aefc04d0888373cce64fcd  framelease_v4/protocol/tests/test_p3_rl.py
88b80ce1673598bc2dadd53289e1f09ab337f4e35f1584e08895ec065dff47d5  framelease_v4/protocol/tests/test_stress_bench.py
d848d23287642bb08f4ce04f86767237a9c044bfd13f79cfdd40f4084921d735  framelease_v4/protocol/tests/test_test_freeze.py
1a28bc010c1c0c1a6e95f323423f9c6fcf2fe67c805060e9d4a3a92947cfdab3  framelease_v4/protocol/tests/test_test_jobs.py
7d8cf7da7615ecb79e63a4c87d5df256884a4dc56143ca1ec84a4f9eac8f9dff  outputs/framelease_v4/p2_jobs/README.md
53bbf8c69124519c6bb2133961695aa4f238c6d52e325f0d8e7de53008d23f3f  framelease_v4/rl/qnet.py
269e8e8392c308ba1ceb4adcd82bbca3736e98bc7ac5e62e5b86c570b316405e  framelease_v4/rl/ope.py
27f0ecebdcb0ec0431c84a0659f0a748b07544900e5f7547d0fcb5c53ec4e8a3  framelease_v4/rl/RL_PROTOCOL.md
fb595d7fe0f684cccd7f5b347fd9762d9fd25eddf1222a3aeb51e16c397c44c8  framelease_v4/rl/trainers.py
dace32b90d3f7bcc636b1a285bf1a255cad9d8e9983e542b98bb6dbee586fac8  outputs/framelease_v4/build/AMEND/staged/ope.py
c12b935b740494fda4c54d6c162d7d8776a0a29bfe84e5b3ec14b482d1bf2557  outputs/framelease_v4/build/AMEND/staged/RL_PROTOCOL.md
53b9b4c47095bad992a37c3f1e1a3012edd2307cf5ba1998d86e32ce48d76175  outputs/framelease_v4/build/AMEND/staged/test_ope_support.py
c466acc768b9a805697ced427cebadf507c258da783a5e5e90d5925260b3a3fb  outputs/framelease_v4/build/AMEND/staged/logs/pytest_ope_support_registered.log
979fcb5981daa271d0da11a10c691a84e9818c8acab6c31b415f9d2463a95f5c  outputs/framelease_v4/build/AMEND/staged/logs/pytest_ope_support_patched.log
bc70ee3710f34cffdd2a647e45b13f3594bb846e68f0b7e2108f89b579ce501e  outputs/framelease_v4/build/AMEND/staged/logs/pytest_ope_support_dedc93f6.log
8c91907873af20d2df43913271bcac33eace0ca5479cc855e3283eb3ca8a4df3  outputs/framelease_v4/build/AMEND/staged/logs/pytest_rl_tests_patched.log
f7f9161a874ca3825bf9295e69d6aa7465c6423fa53008cc7e81b9264fd009ae  outputs/framelease_v4/build/AMEND/staged/logs/pytest_p3_rl_overlay_patched.log
26543b1729a58ebe5bb52763387bf6a4f70ea906b0ef4f2a69d1cf07a0c4b6ba  outputs/framelease_v4/build/AMEND/staged/logs/p3_rl_dev_dstar4_overlay_patched.log
b2458a3ff78735c20cac80d3f9f63352d596ab3ab9a39a1d766c2f3fbfc90049  outputs/framelease_v4/build/AMEND/staged/compare_supported.out.json
56e78d869b8837d27bd54cc017722bb9c92e4409610c478cf6ed52b2ddf982e0  outputs/framelease_v4/build/AMEND/a5_disable_rule_tests.log
6d2649992cc82987062bf5cafce4a5a3d29f2ceae343358fb364023ece4b596c  outputs/framelease_v4/build/QNET/review/test_review_qnet.py
2e49209408436c941dda60cceb18d193cb23e2596162c95f0212816bcbc2fdf7  outputs/framelease_v4/build/QNET/review/repro_qnet1_review.out.json
e5937a5f6d3b176a8f9164078c3bd14ec121959da3e9b738a5009c75b171ead7  outputs/framelease_v4/build/STRESS/s2_dev_recorded_smoke_report_v2.json
94f3950b539bbb5f8a7573414f4aa82d8fd680c2074cb18249572348d1075d02  outputs/framelease_v4/build/STRESS/s2_dev_report_v2.json
957c7633c3b5f9882bfab451e6f3b39f1651063c5d638bc9f6cd18c11e7abb28  outputs/framelease_v4/validity_notes/background_load_20261111.md
80285726ea7d95b5b1c11af7b97c6a21bb2f549af6ccfaf62373c80042faa598  outputs/framelease_v4/validity_notes/carla_fingerprint_20261111.sha256
81e31322daf670eb7acb92d1dade6dc051dbde91d89727eea51f47c7a8950cf0  outputs/framelease_v4/p1_driver/STOP.20261111_pause.resolved.txt
21f835a54a403d553ddae7b5334cf04e27c419313cd7464293a1aa017de0b397  outputs/framelease_v4/build/AGG/smoke_A/SHA256SUMS
eb69c49d1c69ef2a1c1c7115d46b29e16488de19133a0391f48bf7f14928276e  outputs/framelease_v4/build/AGG/smoke_B/SHA256SUMS
06751835016a6a001e1efcd38089e7ae09585bde52445e82b8b7155e3953a6a5  outputs/framelease_v4/build/AGG/smoke_C/SHA256SUMS
cbb0d53198b122d3cedc012f9a77bc383a8504de4a72c6582653b7c27d11a7e4  outputs/framelease_v4/build/AGG/smoke_C_guard/SHA256SUMS
97f28abfa9da7f595f9344cf25e005a3f80197e73ae5cbf8efede789161bf312  outputs/framelease_v4/build/AGG/smoke_D/SHA256SUMS
```
