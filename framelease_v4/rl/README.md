# FrameLease v4 RL pipeline (`framelease_v4/rl/`)

This directory is the utility selector of the 1109 outline: Sec. III-B, Eqs. 6-8; the RL rows of Table II-A; and the
policy rows of Table II-B.

* **Lease and shield.** Unchanged v3 code, imported read-only: `framelease_v3/runtime`. No v2 or v3 file is edited.
* **Hardware.** CPU only. Nothing here starts the GPU or CARLA, or enqueues a job.
* **Design.** `RL_PROTOCOL.md` here, and `framelease_v4/PROTOCOL.md` Secs. 4.7 and 5.

## Files

| file | content |
|---|---|
| `features.py` | 16 state features from the logged 32 (6 lease-derived), missing values and clipping, allocation-free vectorizer |
| `behaviour.py` | a_det^d (`v4_adet_d<d>`) and the epsilon-random behaviour utility (`v4_eps<eps>_seed<s>[_d<d>]`, logs `v4_mu`); `register_utility_name` puts v4 names into `v3_shield.UTILITIES` (also `v4_qnet_<sha12>`) |
| `agent_entry.py` | evaluator agent entry: registers the utility named in the v3 agent config, then the unchanged v3 / fast-prefix agent; `v4_rl.json` + `summary.json['v4_rl']` |
| `run_closed_loop_rl.py` | launcher = unchanged fast-prefix launcher with in-process substitutions (utility, entry, frozen v4 sources, Q-network file); `--dry-run` only so far |
| `collection_plan.py` | behaviour-data plan (FULL: 44 training routes x kappa {1.0, 1.5, 2.0}; TRIMMED: 22 routes x 2 behaviour seeds) through the v4 arms launcher, arm `fl_behaviour` (JSON; not enqueued) |
| `prefix_score.py` | S(t) = RC(t) x P(t) from hero positions + official infraction messages (Bench2Drive scorer rules), S(T) = DS |
| `dataset.py` | run dirs -> decision epochs, choice-epoch SMDP transitions, rewards (Eq. 7), propensities, test-route guard, evaluation-only covariates |
| `trainers.py` | FQI (finite horizon, undiscounted), contextual bandit, FQI without lease features; support + pessimism; numpy MLP distillation; export |
| `ope.py` | FQE with Watkins lambda = 1 traces, route-grouped cross-fitting, selection, route-cluster bootstrap, behaviour calibration, WPDIS / WDR |
| `qnet.py` | CPU Q-network: fixed read-only weights, preallocated buffers, budgeted call, bypass to a_det^d, sha-pinned name |
| `bench_qnet.py` | CPU microbenchmark (P50 / P99) on real choice-state feature dicts |
| `smoke.py` | end-to-end smoke on the 12 fast-prefix pilot runs (resumable stages) |
| `tests/` | 51 tests (49 + 2 skipped without the official stack variables) |

## How to run

```
cd /home/kang/Desktop/DAC
.conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider framelease_v4/rl/tests     # 49 passed, 2 skipped
source linux/env.sh && CUDA_VISIBLE_DEVICES= .conda-unidrive-linux/bin/python -B -m pytest -q -p no:cacheprovider \
    -W ignore framelease_v4/rl/tests                                                               # 51 passed
OMP_NUM_THREADS=1 .conda-unidrive-linux/bin/python -I -B framelease_v4/rl/smoke.py --fresh       # ~4 s
OMP_NUM_THREADS=1 .conda-unidrive-linux/bin/python -I -B framelease_v4/rl/bench_qnet.py --model MODEL.json
.conda-unidrive-linux/bin/python -I -B framelease_v4/rl/collection_plan.py --d-det D --envelope L.json
source linux/env.sh && .conda-unidrive-linux/bin/python -B framelease_v4/rl/run_closed_loop_rl.py \
    --utility v4_eps0.300_seed123 --arm fl_v3_heuristic --route-id 18305 --port 2905 --output-dir DIR --dry-run
```

**Offline workflow once the behaviour runs exist:**
1. `D.build_dataset(D.discover_runs([root]), out_dir)`.
2. For each family, `O.select(ds, TR.grid(family, d_det=d*))`.
3. Refit the selected candidate on all training episodes.
4. `TR.distill`, then `TR.export_qnet`.
5. Run `fl_full` with the utility `v4_qnet_<sha12>` and `FRAMELEASE_V4_QNET=<file>`.

`smoke.py` does exactly these steps on the pilot.

## Smoke results (2026-11-10, `outputs/framelease_v4/rl_dev/smoke_20261110/`)

The smoke exercises the code. It makes no claim.

**Reward identity** (`reward_proof.json`, `reward_proof.md`).
* On all 12 pilot runs, S(t_1) + sum r_n equals the official DS with an absolute error of exactly 0.0. This holds over
  all decision epochs (v3 runs) or job-step boundaries (v2 runs), and over the choice SMDP.
* The pilot runs are 4 routes x {fast_only, fast_only_fp, fl_v3_heuristic_fp}.
* The penalty model reproduces the official score_penalty on every run. The one non-exact case is 0.141476 against
  0.141473: the message rounds the outside-lanes percentage, and the official value is used at the end.
* Collisions match the hero trajectory at 0.0 m. Stop signs match at 2.4-6.5 m (the sign position).
* Unanchored route-completion reconstruction error: median 1.5 RC points, max 6.2 (route 2086, a junction turn). It is
  anchored to the official value at the end.

**Dataset.**
* 310 choice transitions from the 4 v3 episodes (144 / 9 / 18 / 139). P_both is 0.25 / 0.06 / 0.05 / 0.24.
* The heuristic chose REFINE at all 310 choice states, with mu = 1. REFRESH therefore has no support at choice
  states.

**Behaviour replay.** The 310 logged choice states were replayed through `v3_shield.decide` with `v4_eps0.300_seed20261110`.
* REFRESH share 11.9% (expected 15%; 310 draws).
* 0 answers outside A_feas.
* The utility was called exactly at the 310 choice rows and never at a forced row.

**Selection** (leave-one-route-out, smoke grid of 2 candidates per family).
* As expected, every family reduces to a_det: the REFRESH head is unsupported. All paired deltas are 0.0, CI [0, 0].
* On-policy FQE reproduces the logged DS: 49.62 / 4.58 / 4.59 / 27.59 against 49.66 / 4.58 / 4.59 / 27.59.

**Exported networks.** `v4_qnet_1fcac6089089` (fqi), `v4_qnet_82933eeffea6` (bandit), `v4_qnet_6479fc17e9ed` (fqi_nolease).
* Distillation agreement 1.0.
* Replayed through `v3_shield.decide` at the 310 choice states: 0 answers outside A_feas, 0 bypasses.

**CPU benchmark** (`bench_qnet.json`).

| path | P50 (µs) | P99 (µs) |
|---|---|---|
| Q-network forward (16-32-32-2) | 4.4 | 4.9 |
| featurize + forward | 7.0 | 8.2 |
| `QUtility.select` | 8.9 | 10.9 |
| `v3_shield.decide` with the Q-network (Eq. 8 end to end) | 9.5 | 11.6 |
| `v3_shield.decide`, v3 heuristic | 0.57 | 0.68 |
| `v3_shield.decide`, bypass | 1.1 | 1.5 |

* Setup: Intel i5-14490F, one thread, 20 000 calls after 2 000 warm-up calls, real pilot feature dicts.
* The policy budget B_pi = 100 µs is about 9x the P99.
* The v3 runtime charged 55 / 66 µs (P50 / P99) per decision with the heuristic (`framelease_v3/runtime/README.md`).

## Open items

1. **No exploration data yet.** Every RL claim needs the `fl_behaviour` runs: 132 runs, about 20 GPU-h at the
   pilot's mean of 555 s per job, which is not started. The pilot's P_both was 0.05-0.25 with the default q95 envelope. If P_both stays below 0.05 at the
   selected lease point, PROTOCOL Sec. 5.8 labels RL "not testable".
2. **The launcher has only been run as `--dry-run`.** A real run would start CARLA.
3. **Route completion is approximate in junctions.** RC(t) inside junction gaps uses Hermite curves, because the
   planner's lane path needs the CARLA map. Rewards inside a junction can shift by a few RC points; the episode
   total is exact.
4. **Behaviour seeds are not used as policy features.** The draws are exogenous.
