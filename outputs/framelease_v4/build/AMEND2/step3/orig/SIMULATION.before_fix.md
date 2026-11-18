# Step 3 of APPLY_PLAN2.md: simulation of the transaction on a scratch copy

Run 2026-11-15 04:33-04:36 (Beijing time) with `sim/run_simulation.sh`: 21 cases, 21 PASS, 0 FAIL. Every process ran
on the E-cores 12-15 at nice 19, idle I/O class, one BLAS thread, `CUDA_VISIBLE_DEVICES=''`, one at a time (largest
process 42 MB). The project tree was read only; everything the simulation wrote lies under `/tmp/AMEND3/`. The
transaction code and its input were the files of this directory: `step3_txn.py` (`86f69e70...`), `step3_spec.json`
(`89836a6f...`), `amend_step3.sh`, `write_d1_decision.py`. The evidence is copied into `sim_output/` (listed at the
end).

## 1. Scratch tree (`sim/make_scratch.sh`)

`/tmp/AMEND3/tree` is its own project root:
* real copies: `framelease_v4/` (without `__pycache__`; `registration.py`, `p1_driver.py` and `phase_driver.py` take
  their root from their own path, `Path(__file__).resolve().parents[2]`, so the copy hashes, seals and parses itself),
  `outputs/framelease_v4/registration/`, `outputs/framelease_v4/p1_driver/`, `build/AMEND/` and `build/AMEND2/` (the
  drafts and the transaction directories), `tuning/d1/` (empty, for the fake D1 summary);
* symlinks, read only: every other entry of the project root (the v2 / v3 sources, `linux/`, `checkpoints/`, the
  interpreter), of `outputs/`, of `outputs/framelease_v4/` and of `build/`, and `tuning/selection/`;
* never linked: `queue_p1` and `queue_p1_smoke2` (no flock test may touch the runner's locks) and
  `pipeline_state.json`.

## 2. Fake end of P1 (`sim/fake_p1_end.py`)

The scratch copy of the P1 stage driver's own code wrote the two entries: `p1_driver.ensure_recorded` (protocol lock,
`--write-manifest --force`, the entry under "**Stage selections (P1, FULL).**", `--seal`, `--verify`, baseline refresh),
with `--normal-priority` so that its tools inherited the E-core / nice 19 / idle I/O priority. Inputs: a FAKE tuning
freeze `tuning/selection.json` (L* `B0`, d* 1 and Event-Triggered `s_hb2.0` as selected so far; fl_risk `E5` by the
`lease_s1` means; A* 1.0 s stands in for the `age_s2` selection, which does not exist yet) and a FAKE D1 summary
`tuning/d1/FULL_d1_summary.{json,md}` (9 blocks, none pending). Every fake file carries
`"simulation": "FAKE: written by the step-3 simulation in /tmp/AMEND3 only; not a P1 result"`. Then
`p1_driver.write_done` wrote `P1_DONE.json`, and `p1_driver/driver.lock` was set to a pid that is not alive. The two
entries as the driver wrote them:

```text
* **Tuning freeze**, 2026-11-15 04:33 (Beijing time). `outputs/framelease_v4/tuning/selection.json` (sha256
  `4884295bba3e9524a6914832c27b06a512b963f3aaae2440dc0c5294e69e59b6`), written 2026-11-15T04:33:31+0800 by
  `select_stage.py --variant FULL --freeze --write` from the eight stage selections above (Sec. 4.9): L* = `B0`
  (`outputs/framelease_v4/envelopes/B0.json`, sha256 `9ef8479f04dab873d22b50e8732176804ed67f351f17584355b241e424fa1927`,
  validity std); d* = 1 (utility `v4_adet_d1`); A* = 1.0 s; Event-Triggered `s_hb2.0` (theta* = s, A_hb* = 2.0 s);
  fl_risk: lease point `E5` (L* = B0: fl_risk runs the better of E5 / E10 by mean DS on lease_s1 (T22a), ties earlier).
  Manifest and seal: `MANIFEST.sha256`, 221 files; new in it:
  `outputs/framelease_v4/p1_jobs/FULL/b09_age_s2.check.json`, `outputs/framelease_v4/p1_jobs/FULL/b09_age_s2.jsonl`,
  `outputs/framelease_v4/p1_jobs/FULL/b09_age_s2.stage.json`, sha256
  `4bfe7451a41b853042f181cbcd7c326649b4222279bc35dd9787afa38c8d4033`, sealed with this entry.

* **D1 summary**, 2026-11-15 04:33 (Beijing time). `outputs/framelease_v4/tuning/d1/FULL_d1_summary.json` (sha256
  `55fb5d05a6c029600cc4ee3fa4c91485cefb430135d225fed44ddd1158ac1a91`) and
  `outputs/framelease_v4/tuning/d1/FULL_d1_summary.md` (sha256
  `0f31816a869e1be35b408c191de67d490995b05cf7e6dd852578f479a59deae5`), written 2026-11-15T04:33:42+0800 by
  `d1_summary.py --variant FULL --queue outputs/framelease_v4/queue_p1 --write` after every job of the queue was final:
  9 blocks on training routes only, with the tuning freeze (sha256
  `4884295bba3e9524a6914832c27b06a512b963f3aaae2440dc0c5294e69e59b6`). D1, continuing or stopping, is the user's
  decision (Sec. 4.8); no later phase was started. Manifest and seal: `MANIFEST.sha256`, 221 files, sha256
  `4bfe7451a41b853042f181cbcd7c326649b4222279bc35dd9787afa38c8d4033`, sealed with this entry.
```

## 3. Cases and results (`sim_output/summary.txt`)

| case | what | result |
|---|---|---|
| 01 | `amend_step3.sh --precheck-only` before the fake P1 end | STOP (exit 1): P1_DONE.json missing, no "Tuning freeze" / "D1 summary" entry; nothing changed |
| 02 | fake P1 end | both seals OK; manifest 221 files `4bfe7451...` |
| 03 | `--precheck-only` after it | passed: seals, registered baseline (153 files) in the sealed manifest and unchanged, P1_DONE.json, no live driver of this root, the P1 entries, OP and spec `must_equal`, the 38 A3 files at their reviewed sha256, in-place texts, `check_drafts.py` exit 0, dry composition (40 files become registered) |
| (setup) | an unregistered file changes in the scratch tree (`verify_table1_extra.py`), so that every later manifest differs from the sealed one | - |
| 04 | injected failure at the post-manifest check | STOP (exit 1); MANIFEST.sha256 restored; PROTOCOL.md, MANIFEST.sha256, SEAL.sha256, REGISTRATION.json equal to before; both seals OK |
| 05 | injected failure after PROTOCOL.md was written, before the seal | STOP (exit 1); PROTOCOL.md and MANIFEST.sha256 restored; state as before |
| 06 | `--seal` failing | STOP (exit 1); PROTOCOL.md and MANIFEST.sha256 restored; state as before |
| 06b | SIGTERM after PROTOCOL.md was written | STOP (exit 1, "signal 15 during the transaction"); state restored |
| 06c | SIGKILL after PROTOCOL.md was written | the helper dies (exit 137), the lock is released, the journal stays at step "protocol", PROTOCOL.md is unsealed |
| 06d | `step3_txn.py restore --work <06c>` | the four files back to the copies; both seals OK; state as before |
| 07 | a REGISTERED file changed (`framelease_v4/protocol/p1_driver.py`), `locked` run without the pre-check | the post-manifest check of step 3.2 names it and stops; the sealed manifest is restored |
| 08 | the transaction | PASS: pre-check, locked part (one time stamp, one manifest, one seal), post-checks |
| 09 | a second run | STOP at the pre-check: "Amendment A3 is entered already" (also A4, A7, A9, the operational addition) |
| 10a-c | `write_d1_decision.py` with the anchor phrase in the rationale / a rationale that names its writer / a D1 summary changed after its entry | REFUSED (exit 1) each |
| 10d | `--dry-run` | the JSON printed, nothing written |
| 10e | the write | `phase_driver/D1_DECISION.json` created through a temporary file in the same directory and a rename; nothing else in `phase_driver/` |
| 10f | a second decision | REFUSED: a decision is never replaced |
| 10g-h | `phase_driver.py --dry-run` with the decision | G0 passed; G1 "dry": it would record the "G1 D1 decision" entry (shown in Sec. 7); the dry run wrote nothing |
| 11 | the project tree | none of the five entries in the project's PROTOCOL.md; its two seal lines OK; PROTOCOL.md unchanged during the run |

## 4. The transaction (case 08, `sim_output/08_transaction.log`)

```text
amend_step3.sh 2026-11-15T04:35:34+08:00: root /tmp/AMEND3/tree; transaction directory /tmp/AMEND3/runs/08_transaction
inputs: step3_txn.py 86f69e70c31edfc49e95cb07b55d62a4afc07e7b05e0e058b724407ed6c36ea0,
        step3_spec.json 89836a6f2e01ab0e99effb4467bc20fdb86059bcfb4689aeddceadb878c4cfcd
== 1. pre-check (no lock)
registration.py --verify (exit 1): manifest: 1 files differ: [('framelease_v4/analysis/verify_table1_extra.py', 'a8bf57b7c23f2c9e8746ab8af116490a215e3185a788921f3dee242af191acfa', 'd416bdedd8eb7ed4f19b03bdc559da2f4589dfd208e9b687f22545a6dfaaf4af')] | seal framelease_v4/PROTOCOL.md: OK | seal outputs/framelease_v4/registration/MANIFEST.sha256: OK
registered baseline: 153 files; in the sealed manifest at their sha256 and unchanged in the tree: yes
P1 driver entries: Tuning freeze line 2211, D1 summary line 2221; outputs/framelease_v4/tuning/d1/FULL_d1_summary.json sha256 55fb5d05a6c029600cc4ee3fa4c91485cefb430135d225fed44ddd1158ac1a91 cited by the D1 summary entry
check_drafts.py exit 0: all checks passed
dry composition: 2835 lines; entries A3 193 lines, A9 43 lines, A7 53 lines, A4 74 lines, OP 114 lines; 40 files become registered
precheck: passed (dry files in /tmp/AMEND3/runs/08_transaction/precheck)
== 3. locked part (framelease_v4/.protocol.lock, wait up to 600 s)
lock held 2026-11-15T04:35:41+08:00; time stamp of the five entries: 2026-11-15 04:35
sealed state copied into /tmp/AMEND3/runs/08_transaction: PROTOCOL.md b1e004ed93de6f56c8e4c1a39cfce057a059bf4787ed6841ec239cece1049de1, MANIFEST.sha256 4bfe7451a41b853042f181cbcd7c326649b4222279bc35dd9787afa38c8d4033
registration.py --write-manifest --force (exit 0): wrote /tmp/AMEND3/tree/outputs/framelease_v4/registration/MANIFEST.sha256: 221 files, sha256 8c50b99209af9648f0ff35c95a8725a1c6585f221dbd26ea1d56545a2e60e0c9
post-manifest check (step 3.2): OK
new manifest: 221 files, sha256 8c50b99209af9648f0ff35c95a8725a1c6585f221dbd26ea1d56545a2e60e0c9; new in it: none; changed since the seal (unregistered): ['framelease_v4/analysis/verify_table1_extra.py']
PROTOCOL.md written: sha256 0844a914d7808a527f30395fa07bb9f3443f1de28dce906c9610a67f44f9f8eb (2835 lines)
registration.py --seal (exit 0): sealed: PROTOCOL.md 0844a914d7808a527f30395fa07bb9f3443f1de28dce906c9610a67f44f9f8eb, manifest 8c50b99209af9648f0ff35c95a8725a1c6585f221dbd26ea1d56545a2e60e0c9 
registration.py --verify: manifest: OK | seal framelease_v4/PROTOCOL.md: OK | seal outputs/framelease_v4/registration/MANIFEST.sha256: OK
entry A3: 193 lines (/tmp/AMEND3/runs/08_transaction/entry_A3.md)
entry A9: 43 lines (/tmp/AMEND3/runs/08_transaction/entry_A9.md)
entry A7: 53 lines (/tmp/AMEND3/runs/08_transaction/entry_A7.md)
entry A4: 74 lines (/tmp/AMEND3/runs/08_transaction/entry_A4.md)
entry OP: 114 lines (/tmp/AMEND3/runs/08_transaction/entry_OP.md)
lock released 2026-11-15T04:35:48+08:00
== 4. post-check (no lock)
step 3.2 on the sealed manifest: OK
registration.py --verify: manifest: OK | seal framelease_v4/PROTOCOL.md: OK | seal outputs/framelease_v4/registration/MANIFEST.sha256: OK
phase_driver.py --dry-run (exit 0; full output /tmp/AMEND3/runs/08_transaction/phase_driver_dry_run.txt):
    G0 passed: P1 done, P1 entries ['freeze', 'd1'], amendments ['A3', 'A4', 'A7', 'A9']; seal OK, manifest OK
    G0  passed       seal OK, manifest OK
    G1  waiting      waiting for outputs/framelease_v4/phase_driver/D1_DECISION.json (the coordinating session's D1 decision under the delegation of 2026-11-14)
    G2  blocked      waits for G1
    G3  blocked      waits for G1
    G4  blocked      waits for G1
    G5  blocked      waits for G1
    G6  blocked      waits for G1
    G7  blocked      waits for G1
    G8  blocked      waits for G1
G5 plan (phase_driver.stress_runs on the sealed PROTOCOL.md): ['s3', 's2', 's2_relative', 's1']; A7b read from the A7 text: True; s2_relative: framelease_v4/protocol/stress_bench.py s2 --registered --states synthetic --qnet <network of the RL freeze> --grid relative
check_drafts.py on the new PROTOCOL.md (exit 0):
  OP: 114 lines, 12 placeholders, 3 framelease_v4 files cited by sha256
  A10: 230 lines, 34 placeholders, 8 framelease_v4 files cited by sha256
  A10 in-place found 1x now: 'If an offline output lacks a paired quantity, the v4 analysis script c'
  A10 in-place found 1x now: 'freeze.\n\n**Freeze.** The analysis freeze happens when every registered'
  A10 in-place found 1x now: '`outputs/framelease_v4/analysis/final_<stamp>/`, with a sha256 manifes'
  A10 in-place found 1x now: '**Verification.** Before any number enters the paper, an independent s'
  A10 in-place found 0x now: 'the analysis script, the Proposition-1 coverage and the figure and tab'
  all checks passed
files registered by this transaction (manifest files outside the P1 baseline whose sha256 the sealed PROTOCOL.md cites and the earlier one did not): 40
Sec. 4.1 status paragraph (the text the fifth A10 in-place "old" is taken from, APPLY_PLAN2.md Sec. 4 step 1):
  | Status (Amendment A3): the `fl_global_shield` lease of item 1, the aggregator of item 2 (with infractions per km), item
  | 3 and item 4 are implemented and registered; the analysis script, the Proposition-1 coverage and the figure and table
  | generators remain required before the analysis freeze. `fl_bandit` and `fl_fqi_nolease` of item 1 are configurations of
  | launcher arm `fl_full` with the networks of their families (Amendment A4).
postcheck: passed
PASS: Amendments A3, A9, A7 (A7b), A4 and the operational addition entered at 2026-11-15 04:35, one manifest, one seal;
      post-checks passed. Next: update framelease_v4/PIPELINE_STATE.md, then the D1 decision (RUNBOOK.md).
```

The manifest of the transaction differs from the fake D1 seal only in the unregistered file changed for the fault
cases; it is named as "changed since the seal (unregistered)". The five entries cite the same manifest (221 files,
`8c50b992...`), sealed with them. The files the transaction registers (manifest files outside the P1 baseline whose
sha256 the new PROTOCOL.md cites and the earlier one did not) are exactly the 37 `framelease_v4` files of A3 and the
three of the operational addition. The four P1 job files `b04`-`b07` that the stage-selection entries already cite
count as registered already (P1 job files are always registered for the phase driver) and are not counted.

## 5. The produced entries (inserted in this order before "Each amendment gets the date and time")

Filled by `fill_entry.py` with one time stamp; blocks with a filled line over 120 columns rewrapped (words unchanged,
checked); every line checked against `check_drafts.line_problems` (no line over 120 columns except table rows, no
line that a driver reads as an entry, a heading, the anchor or another amendment title, no list-like line start).

### A3

```text
**Amendment A3, 2026-11-15 04:35 (Beijing time): registration of the Phase 2-7 tooling (no effect on any P1 run, P1 job
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
```

### A9

```text
**Amendment A9, 2026-11-15 04:35 (Beijing time): the aggregator was developed with read-only runs on finished P1
training-route runs (Sec. 9.12; no test-route result examined; no effect on any run or criterion).**
* Cause. Sec. 9.12 states that `aggregate_v4.py` and `analyze_v4.py` "are written and tested on synthetic CSVs only".
  The aggregator (`framelease_v4/analysis/`, Amendment A3) was tested on synthetic run directories and, in addition,
  run read-only on the finished runs of `outputs/framelease_v4/queue_p1`: the P1-0 smoke runs and the P1 `ref` runs,
  all on training routes, which are examined by design (Sec. 9.11: "Training-route results are examined by design
  (Phase 1, D1, Phase 3)").
* What was run (every execution on real data up to the drafting of this entry, 2026-11-11; the read-only executions from
  2026-11-14 on are recorded in Amendment A10).
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
* Rule from this entry on. `analyze_v4.py` (R-4) runs during development on synthetic CSVs and, read-only, on
  training-route aggregations only (its runs of 2026-11-14 on `outputs/framelease_v4/build/AGG/smoke_D`: Amendment A10).
  During development the aggregator runs on training-route runs (P1, P2) only; before the analysis freeze it shows
  test-route runs as job health only (the Sec. 9.11 guard, Amendment A3).
* In-place text, Sec. 9.12, after "Both are written and tested on synthetic CSVs only.": "The aggregator was also run
  read-only on finished P1 training-route runs during development (Amendment A9)."
* Scope. No run, job file, selection or criterion changes; the registered analysis is unchanged.
* Files. `framelease_v4/analysis/aggregate_v4.py` (`ee13c90b91bf44ad59d0a3c7e60bf93d65964785ed386d3e81c44fea0f5e4b96`)
  and `framelease_v4/analysis/interim_guard.py` (`5453a3573e7cca958cad1bc1c44d53995a11e034e251bba634fe09390efed9c7`),
  both Amendment A3, whose docstrings state this deviation; the output manifests of the development runs (each written
  by the last execution into its directory) `outputs/framelease_v4/build/AGG/smoke_A/SHA256SUMS`
  (`21f835a54a403d553ddae7b5334cf04e27c419313cd7464293a1aa017de0b397`), `smoke_B/SHA256SUMS`
  (`eb69c49d1c69ef2a1c1c7115d46b29e16488de19133a0391f48bf7f14928276e`), `smoke_C/SHA256SUMS`
  (`06751835016a6a001e1efcd38089e7ae09585bde52445e82b8b7155e3953a6a5`), `smoke_C_guard/SHA256SUMS`
  (`cbb0d53198b122d3cedc012f9a77bc383a8504de4a72c6582653b7c27d11a7e4`) and `smoke_D/SHA256SUMS`
  (`97f28abfa9da7f595f9344cf25e005a3f80197e73ae5cbf8efede789161bf312`).
* Tests. `framelease_v4/analysis/tests/test_interim_guard.py` (health-only rows before the freeze, a development
  record never releases a registered test route; Amendment A3 log `pytest_analysis.log`).
* Manifest and seal after this amendment: `MANIFEST.sha256`, 221 files, sha256
  `8c50b99209af9648f0ff35c95a8725a1c6585f221dbd26ea1d56545a2e60e0c9`, sealed with this entry.
```

### A7 (variant A7b)

```text
**Amendment A7, 2026-11-15 04:35 (Beijing time): a supplementary S2 grid relative to each state's Eq. 5 slack floor
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
  * In addition, every S2 run (P3 synthetic, Phase 7 recorded) repeats the sweep on a grid relative to each state's own
    floor f(state), the first-admissible slack of the state (Eq. 5: L_pi + L_a + L_commit + R_a + eps, minimised over
    the actions the state can admit at some slack; `stress_bench.slack_floor(state)['any']`): D* = t + f(state) + delta
    for delta in [-0.1, 0.6] s in 10 ms steps (71 values); D_cand moves with D* exactly as in the registered sweep. A
    state that admits no action at any slack (no newer frame and REFINE excluded) has no floor; it is counted and not
    swept. Reported per delta and per kappa: the share admitted, the admitted actions whose bound >= D* (must be 0), the
    Q-network bypass rate split into its near-deadline and CPU-timing parts. The results appear in Table II-B and its
    supplement under the label "supplementary: S2 relative to the slack floor" and never replace the registered S2.
  * Tool change in `framelease_v4/protocol/stress_bench.py`: an option `s2 --grid relative` (default `registered`)
    that sweeps delta per state with the registered checks; the report records `grid: relative_to_floor`, the offsets
    and, per state, f(state); a registered run of the relative grid is labelled supplementary. The relative report
    passes only with 0 violations and its `floor_check` met: the feasible set of every replay equals the one the
    per-action floors predict (a replay within the tolerance of a floor is an Eq. 5 boundary case, counted and not
    judged). Tests: every state with a floor admits an action from the first positive delta on; the bound check is
    exercised at every kappa (a shield without eps or without R_REFINE yields admitted actions with bound >= D*, as for
    the registered grid); the registered grid's report is byte-identical with and without the new code path. The change
    and its review precede the application of Amendment A3, which then registers the extended `stress_bench.py`.
* In-place text, Sec. 7.6, S2, a fourth item of "Report": "per kappa, the Eq. 5 slack floors of the states (min, p50,
  max), the grid values at or below every state's floor, the first admitting grid value and the admitted actions
  checked (Amendment A7)"; and after the list: "Supplementary (Amendment A7): the same sweep with
  D* = t + f(state) + delta, f the state's first-admissible slack, delta in [-0.1, 0.6] s in 10 ms steps; reported as
  supplementary, never in place of the registered grid."
* Scope. S2 reports and Table II-B only. No closed-loop run, job file or pin changes; the registered grid and its
  criterion are unchanged.
* Files. `framelease_v4/protocol/stress_bench.py` (`0cff7b56e6fc09686601f06ff919bde29de17336d6342b9c66ea23bb617d04c2`,
  with the option) and `framelease_v4/protocol/tests/test_stress_bench.py`
  (`92abe721bd42643fab8942a231d99ab14d35b1a5c789d1e55610d2b3499c0f58`), both registered by Amendment A3; development
  reports `outputs/framelease_v4/build/STRESS/s2_dev_recorded_smoke_report_v2.json`
  (`e5937a5f6d3b176a8f9164078c3bd14ec121959da3e9b738a5009c75b171ead7`) and
  `outputs/framelease_v4/build/STRESS/s2_dev_report_v2.json`
  (`94f3950b539bbb5f8a7573414f4aa82d8fd680c2074cb18249572348d1075d02`).
* Tests. `test_stress_bench.py`, the relative-grid tests above:
  34 passed in 30.38s (`pytest_stress_bench.log`,
  `4ca00fbd23e75887174e4bc878d6ebb37582661dfa388726a40dc65729390a7c`); a development relative-grid S2 run on the
  recorded smoke states (`outputs/framelease_v4/build/STRESS/s2_dev_relative_recorded_smoke_a7.json`,
  `9c92900e7c4594b734c1204c274b9679ed10b79b48e90f24c767176923e8f779`; 1000 states at kappa 1.0 and
  three development networks: every state admits an action from the first positive delta on, 0 admitted actions with
  bound >= D*, `floor_check` without mismatch).
* Manifest and seal after this amendment: `MANIFEST.sha256`, 221 files, sha256
  `8c50b99209af9648f0ff35c95a8725a1c6585f221dbd26ea1d56545a2e60e0c9`, sealed with this entry.
```

### A4

```text
**Amendment A4, 2026-11-15 04:35 (Beijing time): realisation of the ablation arms `fl_bandit`, `fl_fqi_nolease`,
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
  `8c50b99209af9648f0ff35c95a8725a1c6585f221dbd26ea1d56545a2e60e0c9`, sealed with this entry.
```

### Operational addition: the phase driver

```text
**Operational addition, 2026-11-15 04:35 (Beijing time): the phase driver of Phases 2-7 (FULL; no change of any run, job
file, selection rule or criterion).**
* What it is. `framelease_v4/protocol/phase_driver.py` (sha256
  `2bf4147c610751c8380f55c59d10f889ce7062849c56351ebbaa8fac1ac7c994`) carries out the phase gates G0-G8 after P1 for
  FULL as registered (Secs. 4.8, 4.9, 5.3-5.9, 7.6, 8.1-8.6, 9.11, 9.12, 10.1;
  `outputs/framelease_v4/p1_driver/GAP_AUDIT.md` Sec. 3.6, item E-2). It imports the helpers of the registered
  `framelease_v4/protocol/p1_driver.py` and never edits it; it starts CARLA and the GPU only through
  `framelease_v4/protocol/launch_queue.sh`. Every cycle (default 300 s) walks the gates in order and stops at the first
  gate that is not passed. Its state lives in `outputs/framelease_v4/phase_driver/` and is rebuilt from the files at
  every cycle: no entry is written twice, no job file is generated, copied or recorded twice, and no report or freeze
  record is rewritten.

  | gate | what the driver does | PROTOCOL |
  |---|---|---|
  | G0 | waits, never with an ALERT, until `outputs/framelease_v4/p1_driver/P1_DONE.json` exists, the P1 stage driver has exited with no open record transaction, Sec. 13.2 holds the P1 driver's "Tuning freeze" and "D1 summary" entries and Amendments A3, A4, A7 and A9, and `registration.py --verify` passes | 4.9, 8.1, 13.2 |
  | G1 | D1: waits for `phase_driver/D1_DECISION.json` (`continue` or `stop`, a rationale, the sha256 of `outputs/framelease_v4/tuning/d1/FULL_d1_summary.json`); the sha256 must be the file's and the one the P1 driver's "D1 summary" entry cites (else ALERT); records the decision; `stop` writes `phase_driver/P2_STOPPED.json` and ends the driver, which never starts P2 later | 4.8 |
  | G2 | P2 job file: `p2_jobs.py --check --write` once (no `--variant` option exists: the tool writes FULL only); the check must be clean and the stage spec must cite the recorded tuning freeze; the job file, stage spec and check are recorded BEFORE the job file is copied atomically into `outputs/framelease_v4/queue_p2/jobs.d`; then the runner is launched | 5.3, 8.1, 8.2 |
  | G3 | once every P2 job is final and no runner holds the queue: `p2_check.py` without, then with `--write`; FAIL: ALERT; missing episodes: ALERT until `phase_driver/P2_MISSING_ACK.txt` names every one of them; the data manifest and the completion report are recorded | 5.3, 5.9, 8.1 |
  | G4 | P3, once no runner, closed-loop process or P1 driver is alive and the P3 code is registered: `p3_rl.py run --stop-after dataset`; `calibrate --sizes 33,66,132` (once, never overwritten); `run --n-jobs` with the recommended count (reduced only when the workers would exceed 75% of the available memory); `status`; `rl_freeze/rl_freeze.json` validated and recorded; an open case (exit 4): ALERT naming it, resolved only by `phase_driver/P3_OPEN_CASES.json` | 4.7, 5.4-5.9, 8.1 |
  | G5 | stress tests, once `stress_bench.py` is registered, each run once and never overwritten: S3; S2 on the registered grid; S2 on the grid relative to the slack floor (only under Amendment A7, variant A7b); S1 last, behind the exclusive-CPU guard (a process of this project: wait; foreign CPU load: retry after 600 s, ALERT after 3 retries, unless `phase_driver/S1_ACCEPT_FOREIGN_CPU.txt` gives the reason to accept it); every report checked as `test_freeze.py` checks it (S2 and S3: 0 violations) and recorded in one entry | 7.6, 9.5 |
  | G6 | test freeze, once `test_jobs.py`, `test_freeze.py`, `check_smoke_ext.py` and `framelease_v4/arms_ext/` are registered: `test_jobs.py --check --write` once; `registration.py --verify`; `test_freeze.py --write` and `--entry`; the record, with the entry text the tool prints; `test_freeze.py --verify`; the job files copied into `outputs/framelease_v4/queue_p4/jobs.d` in tier order; `--verify` again; `phase_driver/P4_QUEUED.json`; the runner | 3.3, 5.9, 8.1, 8.3, 10.1 |
  | G7 | P4-P6: job health only (per job file: jobs and final jobs; no outcome, metric or route of a test-route run is read or summarized); a job file the test freeze does not name: attention; passed when every job is final and the runner has exited | 8.4, 9.11 |
  | G8 | analysis freeze: waits (attention, no ALERT) until Sec. 13.2 cites the sha256 of `framelease_v4/analysis/analyze_v4.py` and PROTOCOL.md cites the sha256 of every aggregator module the record freezes; `queue_p4/jobs.d` must hold exactly the job files of the test freeze; `registration.py --verify`; then `aggregate_v4.py --write-freeze-record` over `queue_p4` once, into one `outputs/framelease_v4/analysis/final_<stamp>/` (never `--arm-summary`, never `--analysis-freeze`); the record must cover every registered job with a final outcome and the registered analysis code, and `SHA256SUMS` must hold; the record is entered, which makes it valid; `phase_driver/PHASES_DONE.json`; the driver stops | 9.11, 9.12 |

* Records. Each gate entry is written with the transaction of the P1 stage driver: an exclusive flock on
  `framelease_v4/.protocol.lock`; PROTOCOL.md and `MANIFEST.sha256` must be the sealed ones and every registered file
  must equal the sealed manifest; `registration.py --write-manifest --force`; every registered file must have entered
  the new manifest with its sealed sha256 and none may have vanished from it; the entry; `registration.py --seal`;
  `registration.py --verify`. An interrupted transaction is finished from `phase_driver/protocol_txn.json`. The entries
  stand under the heading "**Phase gates (P2-P7, FULL).**", created once directly before the closing paragraph of
  this section (the rule for dated entries); each is a bullet that starts with the gate and its label in bold and the
  date in parentheses, a form the P1 stage driver never reads as one of its entries. While another editor holds the
  lock, the driver waits up to 300 s and retries at its next cycle.
* Registered files. The driver keeps its baseline in `phase_driver/registered_baseline.json`, seeded read-only from
  the P1 stage driver's. A seal is the pair of the sealed PROTOCOL.md and the sealed manifest; at every new seal the
  baseline keeps each of its files at the newly sealed sha256 and adds a manifest file only when PROTOCOL.md cites
  that file's sha256 (an amendment that registers it). A changed or vanished registered file stops the driver with an
  ALERT; a change of an unregistered `framelease_v4` file (code in development) between seals is named in the next
  entry. Before G2-G6 run a tool, every file of its code must be registered (in the baseline, or cited by the sealed
  PROTOCOL.md); otherwise the gate waits. G8 applies the same rule to the analysis code.
* Tools. The long tools (G4, G5, G6, G8) write their output to `phase_driver/logs/`. A STOP file or a signal ends a P3
  or stress tool or the aggregation (its process group): `p3_rl.py` resumes its stages, a stress run is redone from
  scratch, an aggregation without a record is redone with `--force` in the same directory. A tool runs in its own
  session and can outlive a killed driver: before the driver starts any tool, `registration.py` included, or reads
  what it writes, it waits while a process runs that tool.
* Runners. One queue at a time (`queue_p2` at G2-G3, `queue_p4` at G6-G7), launched only as
  `systemd-run --user --scope --unit=framelease-<queue>-runner-<ts> -p OOMPolicy=continue bash
  framelease_v4/protocol/launch_queue.sh <queue>` at the driver's priority, nice 0 on every core: after the copy of a
  job file, after a 'queue empty' exit with pending jobs (not after two such exits in a row without a started job),
  and into a queue that never had a runner. Never while `<queue>/STOP` exists, while a runner of another queue of this
  project is alive, or with less free disk than the queue needs (P2: 7.3 GiB; `queue_p4`: 11.9 GiB at its first
  launch, Sec. 10.1). A circuit-breaker exit or a runner error: ALERT; a signal exit: no relaunch. A cut (Sec. 10.2)
  is not driven: the driver waits at G7 while a job is pending.
* Priority. Every tool runs at nice 10 (I/O class best-effort, level 7) while no closed-loop job runs, and on the
  E-cores 12-15 at nice 19 with one BLAS thread while one runs (its CPU time is charged to the simulated timeline,
  Secs. 2.3, 11.2; Amendment A8). The P3 and stress tools run only while no closed-loop job runs, on every core at
  nice 10. The runners keep nice 0.
* Launch in an isolated scope. `framelease_v4/protocol/start_phase_driver.sh` (sha256
  `5c70674fbf043bd4eb5fec9236b0a5fca2123bc5087bf12ddf75bac3c171a0ca`) starts the driver detached in a dedicated
  systemd user scope `framelease-phase-driver-<ts>` with `OOMPolicy=continue`, as Amendment A8 ("Isolation") moved
  the runner and the P1 stage driver: a kernel OOM kill then ends only the killed process
  (`outputs/framelease_v4/validity_notes/oom_20261112.md`). One instance runs (an exclusive flock on
  `phase_driver/driver.lock`). The script and the driver refuse a niced or CPU-pinned start, since the runners inherit
  priority and affinity, and refuse while `phase_driver/ALERT.txt` or `phase_driver/STOP` exists; after
  `P2_STOPPED.json` or `PHASES_DONE.json` nothing is started. The start passes neither of the two test options:
  `--allow-nice-launch` (lifts the refusal of a niced or pinned start) and `--normal-priority` (tools without nice,
  ionice and taskset) are used in the test sandboxes only. The driver stops at `phase_driver/STOP` or SIGTERM. An
  ALERT stops it until the cause is fixed and `ALERT.txt` is moved aside.
* Delegation of the phase gates and D1. The user instructed on 2026-11-14 at 04:00 (Beijing time; translated): "from
  now on, review yourself whether to proceed to the next phase". The coordinating session reads this instruction as
  covering every phase gate after P1, D1 included (Sec. 4.8: "Continuing or stopping is the user's decision"). The D1
  decision stays a recorded decision of the coordinating session; the driver never takes it. The coordinating
  session reads the D1 summary, decides and writes `phase_driver/D1_DECISION.json` (a temporary file in the same
  directory, then `mv`); G1 checks that the decision refers to the D1 summary the P1 stage driver entered and records
  it with the decision file's sha256, its rationale, the instruction quoted in translation and this reading. The
  other decision files (`P2_MISSING_ACK.txt`, `P3_OPEN_CASES.json`, `S1_ACCEPT_FOREIGN_CPU.txt`) are decisions of the
  coordinating session in the same way, each cited by the entry that uses it; the driver never chooses the
  alternative of an open case itself. The P1 stage driver and its operational addition of 2026-11-11 are unchanged:
  it stops after the D1 summary.
* Interim looks (Sec. 9.11). Before G8 the driver reads no outcome, metric or route of a test-route run and runs no
  aggregation; G7 stores per-file job counts only. At G8 every test-route row stays health-only until the record is
  entered.
* Departures (none changes a run, a pin or a criterion).
  1. `p2_jobs.py` has no `--variant` option; the driver runs it without one (FULL is the only variant it writes).
  2. G0 waits for Amendment A4, which the apply plan of Amendments A3-A9
     (`outputs/framelease_v4/build/AMEND/APPLY_PLAN.md`, row 9) allowed "during P2 or P3": A4 is entered before the
     driver passes G0.
  3. Review items M1 (a registration-only seal taken for the driver's own seal) and M3 (a registered file removed
     between the pre-check and `--write-manifest`) describe logic that the registered `p1_driver.py` shares;
     `p1_driver.py` is unchanged. At this entry every file of `outputs/framelease_v4/p1_driver/registered_baseline.json`
     is in the manifest sealed with it, at its registered sha256.
* Review. Independent review `outputs/framelease_v4/build/PHASE/review/REVIEW.md`
  (`d7ef679052cb6af5d3385ae231b0f086e8c522ac0d193b17900dc6bbe655bd0c`), verdict GO_WITH_FIXES; the must-fix items M1-M4
  and the should-fix items S1-S8 are applied (S7 through M2). After the fixes, chaos runs that kill the driver with
  SIGKILL at random times and after the n-th tool call (seeds 10-21, orphaned tools finishing first: 12 of 12; seeds
  30-35, immediate restarts: 6 of 6) reach `PHASES_DONE.json` with every entry once, no ALERT, the P1 driver's entries
  unchanged, and the seal and `--verify` OK.
* Tests (CPU; sandboxes under /tmp with mock tools, the real `registration.py` and a copy of PROTOCOL.md; no GPU, no
  CARLA, no runner, no systemd scope; logs in `outputs/framelease_v4/operational_phase_driver/`):
  * `framelease_v4/protocol/tests/test_phase_driver.py`
    (`b4e5bc442cc1374b8e6af7761644021afe14536122fe8b3e79e023d55dbacf63`; the gates G0-G8, the full chain to
    `PHASES_DONE.json`, crash and restart at every crash point, runner rules, the start script):
    24 passed in 163.00s (0:02:43) (`pytest_phase_driver.log`,
    `4bad59f73a81d186ac0bdb5502f1b9bae63cc4008ab7c558dc447548adb01116`);
  * the review tests `outputs/framelease_v4/build/PHASE/review/test_review_phase.py`
    (`c475f4f745d3de88208c8e7c0b994373526ffc6e0821bf20194f6a226bfa8cb4`; chaos SIGKILL, an orphaned tool, a
    registered file removed in the transaction, a P1 driver record between phase records, a registration-only
    amendment): 6 passed in 66.44s (0:01:06)
    (`pytest_review_phase.log`, `0fc25058fd7f340b9b40a9f172c33479ba7bea5de5ffad5828d35b95e6a0491b`).
* Scope. No P1 run, P1 job file, stage selection, tuning freeze or criterion changes, and no file pinned by a job line
  changes; no job line pins these files and no agent imports them. The driver is started after P1 has ended and after
  this entry is sealed. The three files are registered from this entry on; a change of any of them is an amendment.
* Manifest and seal after this addition: `MANIFEST.sha256`, 221 files, sha256
  `8c50b99209af9648f0ff35c95a8725a1c6585f221dbd26ea1d56545a2e60e0c9`, sealed with this entry.
```

## 6. The in-place texts (the changes of PROTOCOL.md outside Sec. 13.2)

Applied in this order: A3 (Sec. 4.1 status paragraph; Sec. 8.6 layout), A9 (Sec. 9.12 "Code."), A7b (Sec. 7.6 S2),
A4 (Sec. 8.3 lead sentence; Sec. 8.3 pin bullets and per-arm totals; Sec. 4.1 status paragraph appended). Every "old"
occurs exactly once at its turn; every produced line has at most 120 columns. The diff of the whole file is
`sim_output/protocol_step3.diff`; its part outside Sec. 13.2:

```text
@@ -480,6 +480,11 @@
 3. the CPU stress bench S1-S3 (Sec. 7.6; run on synthetic states before the test freeze, P3);
 4. the P2-P6 job generators (the P2 run list is `framelease_v4/rl/collection_plan.py`).
 
+Status (Amendment A3): the `fl_global_shield` lease of item 1, the aggregator of item 2 (with infractions per km), item
+3 and item 4 are implemented and registered; the analysis script, the Proposition-1 coverage and the figure and table
+generators remain required before the analysis freeze. `fl_bandit` and `fl_fqi_nolease` of item 1 are configurations of
+launcher arm `fl_full` with the networks of their families (Amendment A4).
+
 ### 4.2 Tuning objective and procedure
 
 **Objective.** Mean DS over training routes:
@@ -1107,7 +1112,12 @@
 * **S2, near deadline.** Recorded states with D* moved so that the slack spans [-0.1, 0.6] s in 10 ms steps. Report:
   * the share of admitted actions;
   * the number of admitted actions whose bound >= D* (must be 0);
-  * the Q-network bypass rate.
+  * the Q-network bypass rate;
+  * per kappa, the Eq. 5 slack floors of the states (min, p50, max), the grid values at or below every state's floor,
+    the first admitting grid value and the admitted actions checked (Amendment A7).
+
+  Supplementary (Amendment A7): the same sweep with D* = t + f(state) + delta, f the state's first-admissible slack,
+  delta in [-0.1, 0.6] s in 10 ms steps; reported as supplementary, never in place of the registered grid.
 * **S3, cancellation and regression.** At least 1e5 random event sequences against the commit gate: late completions of
   cancelled jobs, older observations completing after a newer commit, expired candidates, duplicate releases. Count
   commits that violate Eq. 9 (must be 0).
@@ -1227,7 +1237,8 @@
 
 ### 8.3 Code pins
 
-Every job carries `require_sha256` for (49 files, plus the envelope and the Q-network where they apply):
+Every job carries `require_sha256` for (49 files, plus the envelope, the Q-network file and the extension sources where
+they apply; Amendment A4):
 * the 16 files pinned by the v2 matrix (including `linux/env.sh`, the routes XML and the v2 q95 lease file);
 * `framelease_v2/__init__.py` and `framelease_v3/__init__.py`;
 * the 8 other `framelease_v3/runtime` sources;
@@ -1235,8 +1246,17 @@
 * every `framelease_v4` source the agent imports: `framelease_v4/__init__.py`, the 7 `framelease_v4/arms` sources
   (`__init__`, `policies_v4`, `runtime_v4`, `arms_v4`, `actor_log`, `agent_v4`, `run_closed_loop_v4`) and the v4
   utility modules `framelease_v4/rl/{__init__,behaviour,features,qnet}.py`;
-* the envelope file, for the shield arms;
-* the Q-network file, for `fl_full`, `fl_bandit` and `fl_fqi_nolease`.
+* the envelope file, for the arms with a lease (`fl_heuristic`, `fl_risk`, `fl_behaviour`, `fl_full`, `fl_bandit`,
+  `fl_fqi_nolease`, `fl_global_shield`);
+* the Q-network FILE, at the sha256 the RL freeze records, for `fl_full`, `fl_bandit` and `fl_fqi_nolease` (the network
+  name pins neither B_pi nor the provenance);
+* the five extension sources
+  `framelease_v4/arms_ext/{__init__,global_shield,arms_ext,agent_ext,run_closed_loop_ext}.py`, for `fl_global_shield`
+  (they are frozen into every run of the arm).
+
+Pins per job line: 49 for `fixed_deep`, `fast_only`, `fl_original`, `age_only` and `event_triggered`; 50 for
+`fl_heuristic`, `fl_risk` and `fl_behaviour`; 51 for `fl_full`, `fl_bandit` and `fl_fqi_nolease`; 55 for
+`fl_global_shield`. Every P4-P6 common pin equals the pin of the registered P1 lines (`registration.job_pins`).
 
 The runner blocks a job whose pinned files changed. Each run freezes its own sources. The full list and hashes are in
 Sec. 12.2 (registration); files created at the tuning and test freezes go into Sec. 13.
@@ -1283,11 +1303,18 @@
 * `outputs/framelease_v4/tuning/d1/<variant>_d1_summary.{json,md}` (D1 summary);
 * `outputs/framelease_v4/rl_data/k<kappa>/runs/` (P2; `framelease_v4/rl/collection_plan.py`).
 
-Planned for P4-P6 (generators not yet written):
-* `outputs/framelease_v4/matrix/<arm>/runs/`
-* `outputs/framelease_v4/fig3/<arm>_k<kappa>/runs/`
-* `outputs/framelease_v4/ablation/<arm>/runs/` and `outputs/framelease_v4/replicates/<arm>/runs/`
-* `outputs/framelease_v4/queue_p2/` and later queue directories
+As fixed for P2-P6 by Amendment A3:
+* `outputs/framelease_v4/p2_jobs/FULL/b10_rl_data.{jsonl,stage.json,check.json}` (the P2 job file, its stage spec and
+  its check; not a queue) and `outputs/framelease_v4/queue_p2/` (the runner's queue of P2);
+* `outputs/framelease_v4/rl_freeze/` (the RL freeze, Sec. 5.9) and `outputs/framelease_v4/stress/` (the S1-S3 reports,
+  Sec. 7.6);
+* `outputs/framelease_v4/test_jobs/FULL/b<NN>_<block>.{jsonl,stage.json,check.json}` and `index.json` (the P4-P6 job
+  files of tiers 3-6, blocks 11-16; not a queue) and `outputs/framelease_v4/test_freeze/` (the test freeze and its own
+  sha256 manifest);
+* `outputs/framelease_v4/queue_p4/` (the one runner's queue of P4-P6: the six job files in name order);
+* `outputs/framelease_v4/matrix/<arm>/runs/`, `outputs/framelease_v4/fig3/<arm>_k<kappa>/runs/`,
+  `outputs/framelease_v4/ablation/<arm>/runs/` and `outputs/framelease_v4/replicates/<arm>/runs/` (the P4-P6 runs;
+  `<arm>` is the protocol arm).
 
 The selection, RL-freeze and analysis outputs go to the directories named in Secs. 4.9, 5.9 and 9.12.
 
@@ -1433,8 +1460,9 @@
 ### 9.12 Analysis code, freeze and verification
 
 **Code.** `framelease_v4/analysis/aggregate_v4.py` (per-run rows, recomputed metrics, commit audit) and
-`framelease_v4/analysis/analyze_v4.py` (Secs. 9.1-9.9). Both are written and tested on synthetic CSVs only. Their
-sha256 is entered in Sec. 13 before the analysis freeze.
+`framelease_v4/analysis/analyze_v4.py` (Secs. 9.1-9.9). Both are written and tested on synthetic CSVs only. The
+aggregator was also run read-only on finished P1 training-route runs during development (Amendment A9). Their sha256 is
+entered in Sec. 13 before the analysis freeze.
 
 **Freeze.** The analysis freeze happens when every registered job of tiers 3-6 is final, or when a cut recorded as an
 amendment (Sec. 10.2) takes effect. The time and the job status are recorded. Outputs go to
```

## 7. Post-checks and the D1 decision

`phase_driver.py --dry-run` after the transaction (`sim_output/phase_driver_dry_run_after_step3.txt`): G0 passed
("P1 done, P1 entries ['freeze', 'd1'], amendments ['A3', 'A4', 'A7', 'A9']; seal OK, manifest OK"), G1 waiting for
`D1_DECISION.json`, G2-G8 blocked. The G5 plan read from the sealed PROTOCOL.md (`phase_driver.stress_runs`):
`['s3', 's2', 's2_relative', 's1']`, A7b detected from the A7 text, the supplementary run
`stress_bench.py s2 --registered --states synthetic --qnet <network> --grid relative`. `check_drafts.py` on the new
PROTOCOL.md: exit 0, "all checks passed" (the A10 simulation with the operational addition already present):

```text
OP: 114 lines, 12 placeholders, 3 framelease_v4 files cited by sha256
A10: 230 lines, 34 placeholders, 8 framelease_v4 files cited by sha256
A10 in-place found 1x now: 'If an offline output lacks a paired quantity, the v4 analysis script c'
A10 in-place found 1x now: 'freeze.\n\n**Freeze.** The analysis freeze happens when every registered'
A10 in-place found 1x now: '`outputs/framelease_v4/analysis/final_<stamp>/`, with a sha256 manifes'
A10 in-place found 1x now: '**Verification.** Before any number enters the paper, an independent s'
A10 in-place found 0x now: 'the analysis script, the Proposition-1 coverage and the figure and tab'
all checks passed
```

The decision of case 10d (`--dry-run`; the rationale text is a simulation text):

```text
{
 "schema": "framelease_v4.d1_decision/1",
 "decision": "continue",
 "rationale": "Every P1 block is final on the training routes; the tuning freeze fixes L* = B0, d* = 1 and the Event-Triggered point s_hb2.0 (simulation text).",
 "d1_summary_sha256": "55fb5d05a6c029600cc4ee3fa4c91485cefb430135d225fed44ddd1158ac1a91",
 "decided": "2026-11-15T04:36:02+0800",
 "by": "coordinating session"
}
```

`phase_driver.py --dry-run` with the decision written (case 10g): the G1 entry the driver would record:

```text
* **G1 D1 decision** (2026-11-15 04:36, Beijing time). D1 (Sec. 4.8): **continue**.
  `outputs/framelease_v4/phase_driver/D1_DECISION.json` (sha256
  `b6ead0e5ce7ad36ebe5fa8a03a770459b45d21ccc7ccdeb3ae038f7adb39580a`), decided 2026-11-15T04:36:02+0800 by coordinating
  session, on the D1 summary `outputs/framelease_v4/tuning/d1/FULL_d1_summary.json` (sha256
  `55fb5d05a6c029600cc4ee3fa4c91485cefb430135d225fed44ddd1158ac1a91`, cited by the P1 driver's entry "D1 summary").
  Rationale: Every P1 block is final on the training routes; the tuning freeze fixes L* = B0, d* = 1 and the
  Event-Triggered point s_hb2.0 (simulation text). The user instructed on 2026-11-14 (translated): "from now on, review
  yourself whether to proceed to the next phase". The coordinating session reads this instruction as covering every
  phase gate after P1, D1 included (Sec. 4.8: "Continuing or stopping is the user's decision"), and takes this decision
  under it. Phase 2 starts after this entry: the P2 job file is generated, entered in this section before it is queued,
  and launched (gate G2). Manifest and seal: `MANIFEST.sha256`, <n> files, sha256 `<new manifest sha256>`, sealed with
  this entry.
```

## 8. Differences between the simulation and the run at the end of P1

* `check_drafts.py` and `fill_entry.py` hard-code the project root; in a scratch root `step3_txn.py` runs them with
  that one line replaced in memory (the files are read, never changed, and keep their sha256). In the project tree they
  run as files, as APPLY_PLAN2.md writes them.
* The fault hooks (`AMEND_STEP3_FAULT`) act only in a scratch root; `step3_txn.py` refuses the variable in the project
  tree.
* The pre-check counts a `p1_driver.py` or `phase_driver.py` process as alive when its script argument, resolved
  against the process's working directory, is this root's file, and when `p1_driver/driver.lock` names a live
  `p1_driver.py` pid. In the simulation the project's P1 stage driver (pid 27145) ran and was correctly not counted
  for the scratch root; in the project it is counted until it exits.
* The P1 entries, the tuning freeze, the D1 summary and P1_DONE.json are fakes; at the end of P1 they are the P1 stage
  driver's. The transaction reads from them only: the presence of the two entries, P1_DONE.json's schema and, for the
  D1 decision, the D1 summary's sha256.
* `phase_driver.py --dry-run` runs `registration.py --verify` with its own tool prefix (`taskset -c 12-15 nice -n 19
  ionice -c2 -n7` while a closed-loop job runs): that one child ran at I/O class best-effort 7, not idle, for about 3 s.

## 9. Found and fixed by the preparation and the simulation

* The A7b draft had a continuation line starting with "+ delta" (Markdown reads it as a list item): rewrapped, words
  unchanged (edit F5 in `build/AMEND/PROGRESS.md`). The pre-check checks every filled entry for such line starts.
* The new A3 review-record line with the AGG0 review sha256 filled to 121 columns: line break moved (F3).
* The registration count first included the four P1 job files that the P1 driver's stage entries already cite; the
  count is now of the files newly cited by the transaction (the phase driver registers P1 job files anyway).
* The checks of the simulation script itself (seal-line count, the project tree check while the P1 stage driver
  re-sealed at 04:21 with its `age_s1` entry) were corrected before the final run.

## 10. For Amendment A10 (APPLY_PLAN2.md Sec. 4 step 1, the fifth in-place text)

After step 3 the clause "the analysis script, the Proposition-1 coverage and the figure and table generators remain
required before the analysis freeze" stands in the Sec. 4.1 status paragraph with a line break after "table"; the
one-line "old" of `final/A10_spec.json` occurs 0 times there (as APPLY_PLAN2.md expects), and A3's own entry quotes
the clause with a different break and indentation. `sim_output/a10_inplace5_suggestion.json` holds an "old" (the whole
paragraph as the transaction leaves it, found once) and a "new" (the clause replaced, rewrapped at 120 columns):

old:

```text
Status (Amendment A3): the `fl_global_shield` lease of item 1, the aggregator of item 2 (with infractions per km), item
3 and item 4 are implemented and registered; the analysis script, the Proposition-1 coverage and the figure and table
generators remain required before the analysis freeze. `fl_bandit` and `fl_fqi_nolease` of item 1 are configurations of
launcher arm `fl_full` with the networks of their families (Amendment A4).
```

new:

```text
Status (Amendment A3): the `fl_global_shield` lease of item 1, the aggregator of item 2 (with infractions per km), item
3 and item 4 are implemented and registered; the analysis script, the Proposition-1 coverage, the figure and table
generator and the independent verification script are registered by Amendment A10. `fl_bandit` and `fl_fqi_nolease` of
item 1 are configurations of launcher arm `fl_full` with the networks of their families (Amendment A4).
```

## Files in `sim_output/`

`summary.txt`; `08_transaction.log`, `journal_08_transaction.json`; `entry_{A3,A9,A7,A4,OP}.md`; `protocol_step3.diff`;
`fake_p1_entries.md`, `02_fake_p1_end.log`; `phase_driver_dry_run_after_step3.txt`, `check_drafts_after_step3.txt`,
`sec_4_1_status_paragraph.txt`, `a10_inplace5_suggestion.json`; `d1_decision_dry_run.json`,
`phase_driver_dry_run_after_decision.txt`; the logs of cases 01, 03, 04-06, 06b-06d (`journal_06c_kill.json`), 07, 09,
10a-c, 10e-f, 11.
