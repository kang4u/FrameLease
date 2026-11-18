**Amendment A4, 2000-01-01 00:00 (Beijing time): realisation of the ablation arms `fl_bandit`, `fl_fqi_nolease`,
`fl_risk` and `fl_global_shield`, and the code pins of their job lines (Secs. 4.1, 7.4, 7.5, 8.3; no effect on any P1 or
P2 run).**
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
  `framelease_v4/protocol/test_jobs.py` (`2ea6899d07b990f244d3481366eea2dec02e24cbb3af4944049ac78b36639151`),
  `framelease_v4/arms_ext/run_closed_loop_ext.py` (`4e5968ede4f2b3292ed74cf3346e8a5c962bcd23e457a1bf02ec5549564e808c`),
  `framelease_v4/arms_ext/arms_ext.py` (`456bb04fa8564bf208f8b863f7eabae3f91ad57740c82431a60d02dd87eebdce`),
  `framelease_v4/protocol/check_smoke_ext.py` (`584cbdc19c2fa547c59e632974b923a962da141f667eebad064e70d0fc632210`),
  `framelease_v4/protocol/p3_rl.py` (`10a8590d511a9ab4858b87a93ad41e3a2961ad7a17af626bf27aedc781eab94b`;
  `JOB_LINES_RULE`, the freeze's `job_lines`) and `framelease_v4/analysis/aggregate_v4.py`
  (`ee13c90b91bf44ad59d0a3c7e60bf93d65964785ed386d3e81c44fea0f5e4b96`).
* Tests (in the Amendment A3 logs): `test_test_jobs.py` (labels in the three places, pins 49 / 50 / 51 / 55, absolute
  network path, relabelled network caught, lease overrides refused, the aggregator reads the block specs);
  `test_launcher_ext.py` (the 55 pins, byte-identical dry runs of the 8 arms_v4 arms, fixed lease constants);
  `test_check_smoke_ext.py` (`qnet_line_problems`; QNET-1); `test_fl_full_qnet_agent.py` (16- and 10-input networks
  in the agent process of launcher arm `fl_full`); `test_aggregate_v4.py` (protocol labels, output-directory label,
  network-file and envelope identities). QNET-1 reproduction:
  `outputs/framelease_v4/build/QNET/review/repro_qnet1_review.out.json`
  (`2e49209408436c941dda60cceb18d193cb23e2596162c95f0212816bcbc2fdf7`).
* Manifest and seal after this amendment: `MANIFEST.sha256`, 221 files, sha256
  `4bfe7451a41b853042f181cbcd7c326649b4222279bc35dd9787afa38c8d4033`, sealed with this entry.
