**Amendment A3, 2026-11-15 06:22 (Beijing time): registration of the Phase 2-7 tooling (no effect on any P1 run, P1 job
file, stage selection or criterion).**
* Cause. Secs. 4.1 ("Still required", items 1-4), 5.9, 7.6, 8.1, 8.6 and 9.12 require tools that did not exist at
  registration: the P2 job generator and completion check, the RL production driver and the RL freeze, the CPU stress
  bench, the arm `fl_global_shield`, a checker for Q-network and extension-arm runs, the P4-P6 job generator, the test
  freeze and the aggregator. Amendment A2 listed 21 of the 37 `framelease_v4` files below in its manifest without
  registering them; the other 16 were written later. `outputs/framelease_v4/p2_jobs/README.md` lies outside the
  manifest; the sealed PROTOCOL.md fixes it by its sha256. Each tool was built against
  `outputs/framelease_v4/p1_driver/GAP_AUDIT.md`, reviewed independently
  (`outputs/framelease_v4/build/<item>/review/REVIEW.md`; verdicts GO or GO_WITH_FIXES) and every must-fix item of
  every review is applied. This entry registers them. The changes made after the drafting of this entry were reviewed in
  the same way: the idle band of the background-load flag, the reading of the P4-P6 block specs by the aggregator, the
  adaptation of `p3_rl.py` to Amendment A6 and the option `s2 --grid relative` of `stress_bench.py` in
  `outputs/framelease_v4/build/AMEND/review_prereq/REVIEW.md`
  (`0a17b25da97133a6653aaed96b22ca46798f9fb0858e4467fefc8db9273db9ee`), and the null-margin rule of the commit audit
  and the `km_driven` floor of `runs.csv` in `outputs/framelease_v4/build/AGG0/review/REVIEW.md`
  (`77b39102e3fbbedbc2188417e99b25688a74b27e9cbf2dd6fb71407fea781366`); both verdicts GO. From this entry on, a change
  of any file below is an amendment.
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
     counts the steps up to the deepest commit as used. A null commit margin passes where the validity record names no
     relevant agent, or has reason `horizon_cap` and n_computed 0 (the lease prefilter showed g > delta for every
     relevant agent, so M = +inf); any other null margin with a relevant agent is a violation; a commit present in one
     log only is an ERROR. Arm summaries are keyed by protocol arm, candidate, kappa, seed, phase, block and split. The
     background-load flag is Amendment A8; the real-data development smokes are Amendment A9.
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
  | `framelease_v4/protocol/p2_jobs.py` | `104408ee6f096f1ca16b72230ba1c8eb5e85623b0c675cfcadd63630bea97377` |
  | `framelease_v4/protocol/p2_check.py` | `830482d14745cfdc5f53b2cb498cd8628903a09ec85e355120ff54bf1433eb4b` |
  | `framelease_v4/protocol/p3_rl.py` | `10a8590d511a9ab4858b87a93ad41e3a2961ad7a17af626bf27aedc781eab94b` |
  | `framelease_v4/protocol/stress_bench.py` | `0cff7b56e6fc09686601f06ff919bde29de17336d6342b9c66ea23bb617d04c2` |
  | `framelease_v4/protocol/check_smoke_ext.py` | `584cbdc19c2fa547c59e632974b923a962da141f667eebad064e70d0fc632210` |
  | `framelease_v4/protocol/test_jobs.py` | `2ea6899d07b990f244d3481366eea2dec02e24cbb3af4944049ac78b36639151` |
  | `framelease_v4/protocol/test_freeze.py` | `866f350ee8966b385c5e806725d475f8edb5b00a247c4f30bd14030a5da471dd` |
  | `framelease_v4/protocol/tests/test_p2_jobs.py` | `87a6f7682469c8900774ade51bf8ac81d0ef6d1d1375303a443c207359821a81` |
  | `framelease_v4/protocol/tests/test_p2_check.py` | `edd09fdfbd4c6ce9f6650ce1b3f04dee91e849f0ae00f56b65d1bba54d567961` |
  | `framelease_v4/protocol/tests/test_p3_rl.py` | `16de84c3de824a272168606e14947b9817a29fad5732650db5d3591076e2cda1` |
  | `framelease_v4/protocol/tests/test_stress_bench.py` | `92abe721bd42643fab8942a231d99ab14d35b1a5c789d1e55610d2b3499c0f58` |
  | `framelease_v4/protocol/tests/test_check_smoke_ext.py` | `b73a029cc88e30c7abc60ec8a84fb52a312c0e5badded437c140057f676a2fb3` |
  | `framelease_v4/protocol/tests/test_fl_full_qnet_agent.py` | `30de3b6e6f8bfa6cf8984f7d72158ce82979bc285bde61cadc9139673e2b28c2` |
  | `framelease_v4/protocol/tests/test_test_jobs.py` | `1a28bc010c1c0c1a6e95f323423f9c6fcf2fe67c805060e9d4a3a92947cfdab3` |
  | `framelease_v4/protocol/tests/test_test_freeze.py` | `d848d23287642bb08f4ce04f86767237a9c044bfd13f79cfdd40f4084921d735` |
  | `framelease_v4/arms_ext/__init__.py` | `3932f70fcc48605d4f36a86097084cfeb8ad66a0a4a9c5d575a5d15a2ad1299e` |
  | `framelease_v4/arms_ext/global_shield.py` | `885d56ee0d45c533b7d6f2a72ae50f6b2d9d7f018fd3d99226e536b48f8abc41` |
  | `framelease_v4/arms_ext/arms_ext.py` | `456bb04fa8564bf208f8b863f7eabae3f91ad57740c82431a60d02dd87eebdce` |
  | `framelease_v4/arms_ext/agent_ext.py` | `405ee5c3ba30cf9aa8e634710e980c72494542bc2502a9c2a6154fdf2e47c4e4` |
  | `framelease_v4/arms_ext/run_closed_loop_ext.py` | `4e5968ede4f2b3292ed74cf3346e8a5c962bcd23e457a1bf02ec5549564e808c` |
  | `framelease_v4/arms_ext/tests/helpers_ext.py` | `64e29d34e1e982f023d5562ec2f44ece93c08795c13412674f433859fdd1957c` |
  | `framelease_v4/arms_ext/tests/test_agent_ext.py` | `11f870d3f06bc66da4e5a06cfe71bbf7681de797e83c828f227d7889ddf8b6af` |
  | `framelease_v4/arms_ext/tests/test_arms_ext.py` | `d93201ce0afe434cc473add3ac7718d9db716781c2871f6a6967672f5f030f4e` |
  | `framelease_v4/arms_ext/tests/test_drift_guard.py` | `fdd3ff374c1cbf54b3f9a009d9d0b662e4ab9ecf61723350a24700aaef142115` |
  | `framelease_v4/arms_ext/tests/test_global_shield.py` | `495615aede7a08a15849606d12da06eb63655c358fef5856011a636ebb8d4393` |
  | `framelease_v4/arms_ext/tests/test_launcher_ext.py` | `5cdb14358b43c516beb97b5959743156bc622931143ebeb09b282d80dacf0eee` |
  | `framelease_v4/analysis/__init__.py` | `e201064a33be799a7342df90ce0e4265c760a481daaa674c03b72b04710f4d55` |
  | `framelease_v4/analysis/aggregate_v4.py` | `ee13c90b91bf44ad59d0a3c7e60bf93d65964785ed386d3e81c44fea0f5e4b96` |
  | `framelease_v4/analysis/commit_audit.py` | `7439a4eac0986cad6a25b7395975a0411b7483944a988d68dabb656bd2544ec7` |
  | `framelease_v4/analysis/extra_metrics.py` | `53050f6bed5aa48054d5217832fb84ed4089b3ae80e8fdcf965769af2af79c4c` |
  | `framelease_v4/analysis/interim_guard.py` | `5453a3573e7cca958cad1bc1c44d53995a11e034e251bba634fe09390efed9c7` |
  | `framelease_v4/analysis/manipulation.py` | `78f18dacf323832ef16684b0b81a2ba03b2ffb00186259780d1bafe7e656cbd0` |
  | `framelease_v4/analysis/tests/test_aggregate_v4.py` | `1dfe52c7f43f7c6e38f8428bb5aa7e16a53ef5999ac1c0d691fc1a9e3e140bf8` |
  | `framelease_v4/analysis/tests/test_commit_audit.py` | `c9fa943acb95380bd3396068282f171fdb14eba95540edaba4d5d5112131496d` |
  | `framelease_v4/analysis/tests/test_extra_metrics.py` | `1587fb40872ebf6895defd58030fe2b347e723333e0dd508bdcea6284488b632` |
  | `framelease_v4/analysis/tests/test_interim_guard.py` | `8531bf2b048266d6816f0eeaab4afdf89907541833b3abbfd734370d027647f0` |
  | `framelease_v4/analysis/tests/test_manipulation.py` | `07a63194b423e6c0d6f79464f9e0b61d3640f8d7be4c176091d5cb354cfac231` |
  | `outputs/framelease_v4/p2_jobs/README.md` | `7d8cf7da7615ecb79e63a4c87d5df256884a4dc56143ca1ec84a4f9eac8f9dff` |

* Tests (CPU, run at application with `source linux/env.sh` and then `CUDA_VISIBLE_DEVICES=''`; logs in
  `outputs/framelease_v4/amendment_a3/`):
  * `framelease_v4/protocol/tests/test_<tool>.py` for the tools `p2_jobs`, `p2_check`, `p3_rl`, `stress_bench`,
    `check_smoke`, `check_smoke_ext`, `fl_full_qnet_agent`, `test_jobs` and `test_freeze`:
    194 passed, 21 warnings in 284.98s (0:04:44)
    (`pytest_protocol_tools.log`, `c84a284e3dd4d433c6cc3313fd678857fe083fa37881a0bc86997e789c63f8a5`);
  * `framelease_v4/arms_ext/tests`: 38 passed, 21 warnings in 133.66s (0:02:13)
    (`pytest_arms_ext.log`, `ffbd12d131a0f5691ac38c4b174c217b17f09cfdef2208a742dd3f56cf29f2ec`);
  * the aggregator tests `framelease_v4/analysis/tests/test_aggregate_v4.py`, `test_commit_audit.py`,
    `test_extra_metrics.py`, `test_interim_guard.py` and `test_manipulation.py`, and
    `framelease_v4/arms/tests/test_metrics_realized_keys.py` (the A10 test files have their own logs, Amendment A10):
    83 passed, 103 subtests passed in 1.24s
    (`pytest_analysis.log`, `abf4a435e8c83a5e617281eca8b06c56e7f3f9164ecdcc6ce441fc3e2eac083a`).

  `test_test_jobs.py::LabelsTest::test_the_aggregator_loads_the_block_specs` passes: the aggregator reads the P4-P6
  block specs (schema `framelease_v4.test_stage/1`). The three logs above hold the test counts of the registered
  versions; the development runs of each tool are recorded in `outputs/framelease_v4/build/<item>/PROGRESS.md`.
* In-place text. Sec. 4.1, after item 4 of "Still required, not needed for Phase 1", the sentence: "Status
  (Amendment A3): the `fl_global_shield` lease of item 1, the aggregator of item 2 (with infractions per km), item 3
  and item 4 are implemented and registered; the analysis script, the Proposition-1 coverage and the figure and table
  generators remain required before the analysis freeze." (`fl_bandit` and `fl_fqi_nolease` of item 1: Amendment A4.)
  Sec. 8.6, "Planned for P4-P6 (generators not yet written)": replaced by the layout fixed above (Amendment A3).
* Manifest and seal after this amendment: `MANIFEST.sha256`, 221 files, sha256
  `8c50b99209af9648f0ff35c95a8725a1c6585f221dbd26ea1d56545a2e60e0c9`, sealed with this entry.
