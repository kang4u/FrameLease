# FrameLease v4 Table I arms (`framelease_v4/arms/`)

Baselines, one common runtime substrate, metric extraction and evaluation-only actor logging for the closed-loop
matrix of the 1109 outline (Table I, Fig. 3, Table II-A/B). Everything upstream is imported read-only:
`framelease_v2/`, `framelease_v3/` and `framelease_v4/rl/` are never edited. CPU tests only. Nothing here starts
the GPU, CARLA or a queue job.

## Files

| file | content |
|---|---|
| `policies_v4.py` | `AgeLeasePolicy` (Age-Only), `EventRules` / `EventTriggeredV4` (Event-Triggered), `DecisionRowsMixin`, `logged_v2_class` |
| `runtime_v4.py` | `V4Runtime`: one runtime class for every arm (v3 `V3Runtime` with a summary that works for every policy kind, plus a uniform `v4` block) |
| `arms_v4.py` | the seven arms, their exact configuration (`build_config`), the policy factory (`build_policy`) and learned-utility registration |
| `actor_log.py` | `ActorBoxLogger` (CARLA ground-truth boxes near the hero, gzip JSON lines, byte budget) and its decoder `read_actor_log` / `ActorLog` |
| `realized.py` | realized validity of committed plans from the actor log (closed-loop analogue of the offline V) |
| `agent_v4.py` | `FrameLeaseV4Agent`: v2 latency agent + v4 setup + fast prefix + actor log, used by every arm |
| `run_closed_loop_v4.py` | launcher: one route under one arm, with the fast prefix (v2 / v3 / fast-prefix launcher helpers composed) |
| `metrics_v4.py` | per-run and per-arm metrics, recomputed from the logs and cross-checked against `summary.json` |
| `jobs_v4.py` | dry-run job lines, 2 routes x 7 arms (written to `outputs/framelease_v4/arms_dev/dryrun/`, never launched) |
| `tests/` | 38 CPU tests (fake model, fake clock, fake CARLA world) |

## The seven arms

All arms share:
- the same UniDriveVLA checkpoint;
- the fast prefix (SDPA, exact GPU preprocessing, merged LoRA);
- seed 11 and kappa 1.0;
- the same agent class, runtime class (`V4Runtime`) and cost model, which charges kappa x the measured CUDA time of
  the prefix and of every flow step, plus the measured scheduler CPU time at every boundary;
- the same commit gate, watchdog and full-brake fallback;
- the same evaluation-only actor log.

They differ only in the scheduling policy and its validity rule.

| arm | Table I row | policy | validity of a committed plan |
|---|---|---|---|
| `fixed_deep` | Fixed Deep | v2 `FixedDeep`: 10 flow steps, refresh whenever the GPU is free | max age 3.0 s |
| `fast_only` | Fast Only | v2 `FastOnly`: 1 flow step, refresh whenever the GPU is free | max age 3.0 s |
| `age_only` | Age-Only | v3 shield + a_det with a constant age lease (see below) | D = t_k + clip(A, 0, 2.5 s), A = `age_lease_s` (prior 2.0 s) |
| `event_triggered` | Event-Triggered | v2 `EventTriggered` rules (see below) | max age 3.0 s |
| `fl_original` | Original FrameLease | v2 FrameLease (see below) | v2 lease, at most 2.0 s |
| `fl_heuristic` | FrameLease + Heuristic | v3 suffix lease (Eq. 1-3), shield (Eq. 5), a_det (Eq. 8), versioned commit (Eq. 9) | suffix lease, at most H_bar = 2.5 s |
| `fl_full` | Full FrameLease | `fl_heuristic` + a learned utility among feasible actions (Eq. 6) | suffix lease |

Details:
- **Age-Only.** It refines while the age budget leaves room for a refresh, and it refreshes by age only. It does not
  use perception.
- **Event-Triggered.** Ego speed, heading and route command, plus a change in the model's own detection set, trigger
  inference. An ego event preempts refinement. Without events, a heartbeat refresh happens at the max age minus the
  refresh reservation; `heartbeat_s` can override it.
- **Original FrameLease vs Full FrameLease.** The outline asks for the exact difference:
  - Original = global minimum margin over the whole plan, with the q95 isotropic envelope and a 2.0 s cap; a
    refresh-time reservation rule; no shield; no learned selection.
  - Full = suffix-aligned first-failure lease, action-specific shield and Eq. 8 decision rule, learned utility only
    inside A_feas, and a commit-time margin check.

The defaults are documented priors. The tunable hyperparameters (`ArmV4.tunable`) must be selected on training routes
only, and passed through `--policy-params`, `--envelope` or `--lease-overrides`:
- Age-Only: A (and the inherited utility a_det^{d*});
- Event-Triggered: its thresholds and heartbeat;
- the FrameLease arms: the envelope (`--envelope outputs/framelease_v4/envelopes/<E5|E10|B0>.json`) and the heuristic
  depth d through the utility name `v4_adet_d<d>`, never through `max_depth`.

Utilities (`policy_params.utility`; Eq. 8 consults them only when |A_feas| = 2), checked by `arms_v4.arm_utility`:
- `age_only` and `fl_heuristic`: `heuristic` (= a_det^10) or `v4_adet_d<d>` only;
- `fl_full`: a Q-network `v4_qnet_<sha12>` only, with `--utility-env FRAMELEASE_V4_QNET=<weights.json>`;
- `fl_behaviour` (offline-RL data, not a Table I arm): a behaviour name `v4_eps<eps>_seed<s>[_d<d>]` only.

Every v4 utility is registered through `framelease_v4.rl.behaviour.register_utility_name` in the launcher
(`build_config`) and again in the evaluator's agent process (`build_policy`, called by `agent_v4.setup_v4`); the agent
re-checks the utility block and the depth limit (`agent_config_from`). A policy or runtime `max_depth` other than 10 is
rejected for every age / shield arm (`check_shield_depth`). The modules the agent imports for this,
`framelease_v4/rl/{__init__,behaviour,features,qnet}.py`, are frozen into every run and pinned by every job.

### Same substrate, shown by tests

- **v2 rules on `V4Runtime`.** `V4Runtime` and `DecisionRowsMixin` give every v2 rule the same jobs, ticks, commits
  and rejects as v2's `LatencyRuntime`. This also holds with a stepping scheduler clock, so charged CPU time is
  included.
- **Real agent class, same measured costs.** With identical fake costs, `FrameLeaseV4Agent` reproduces:
  - for `fixed_deep`, every job and tick of the fast-prefix v2 agent;
  - for `fl_heuristic`, every job, tick and decision row of the fast-prefix v3 agent.
- **Event-Triggered.** `EventRules` equals v2 `EventTriggered` bit for bit in every log stream, over 7 event
  scenarios.
- **Launcher configurations.** For `fixed_deep`, `fast_only` and `fl_original`, the launcher's agent configuration
  equals the v3-matrix baseline arms' configuration. For `fl_heuristic` it equals `run_closed_loop_v3.v3_configs`.

## Metrics (`metrics_v4.py`; the same definitions are in `summary.json['v4']`)

| metric | definition |
|---|---|
| driving score, route completion, penalty | official record (`score_composed`, `score_route`, `score_penalty`) |
| success | Bench2Drive `statistic_route_json.is_success`: status Completed or Perfect, and no infraction except `min_speed_infractions` |
| collisions/km | pedestrian + vehicle + layout collisions / max(route length x completion, 0.001 km) |
| GPU usage | GPU-busy simulated s / simulated s. Busy = cost-model intervals of prefixes and flow steps inside [first tick, last tick + 0.05 s] |
| deadline-miss ratio | control ticks without a valid committed action (no plan, expired, re-anchoring failed) / ticks. The variant `_after_first_commit` excludes the start-up |
| expired ratio | ticks whose committed action's deadline has passed / ticks |
| fallback | the full brake is applied exactly on the deadline-miss ticks. Reported separately: episodes (entries into fallback) and ticks by reason |
| action age | tick time - capture time of the tracked action's observation, over tracked ticks (p50, p95, mean) |
| P_both | shield decision epochs with \|A_feas\| = 2 / shield decision epochs. None for arms without a shield |
| realized validity | `--realized`, from the actor log: conflict plans, misses (H > V_suf), closed-loop R_cond, realized-invalid ticks (`realized.py`) |

`metrics_v4.py` recomputes everything from `ticks.jsonl`, `jobs.jsonl`, `events.jsonl` and `decisions.jsonl` and
reports the differences against `summary.json` (`checks`).

Check on the 12 fast-prefix pilot runs (read-only): every difference is 0.0, and the per-arm DS means 66.4 / 50.4 /
21.6 and the P_both values reproduce `RND_REPORT_20261110.md` §5.1.

## Actor log (`actor_log.py`; evaluation only)

The log observes the simulator after the control of the tick is computed. No policy, lease, shield, runtime or
controller holds a reference to it. A test shows that ticks, jobs, decisions and the summary are identical with the
log on or off.

File: `raw/agent/framelease/actors.jsonl.gz`, gzip JSON lines with one member per 100 logged ticks. Each tick writes
one row:
- `e`: hero truth (CARLA x, y, yaw, vx, vy);
- `g`: the agent's own planar `lidar2global`;
- `a`: vehicles and walkers within 50 m (nearest 64) as `[id, dx, dy, yaw, vx, vy]`.

Each actor gets one catalog line (class, type, box half extents and centre offset). Static props are catalogued once,
with their pose. All values are integers: cm, centi-degrees, cm/s.

Size budget: 2,000,000 B, with adaptive decimation:

| share of budget used | logging |
|---|---|
| below 50% | every tick |
| 50-75% | every 2nd tick |
| 75-100% | every 4th tick |
| 100% and above | ego-only rows |

Measured on the fake world: 4000 ticks (the pilot's tick limit) with 50 actors give 140 kB, and dense jittered traffic
gives 600 kB.

`read_actor_log` converts to the right-handed frame of `framelease_v2.geometry` and builds a `GTTrack`. A crash loses
only the last chunk.

Realized validity (`realized.py`) places each committed plan with the true capture LiDAR pose (hero transform plus the
official lidar2ego). It then runs `framelease_v2.c2_eval.observed_validity`, the function the offline studies use.

## How to run

```
cd /home/kang/Desktop/DAC
# CPU tests: 27 in isolated mode (the agent / launcher / job tests skip without the official stack)
.conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider framelease_v4/arms/tests
source linux/env.sh && CUDA_VISIBLE_DEVICES= .conda-unidrive-linux/bin/python -B -m pytest -q -p no:cacheprovider \
    -W ignore framelease_v4/arms/tests                                              # 38 passed
# one route, dry run (validates, prints the evaluator command, starts nothing)
source linux/env.sh && .conda-unidrive-linux/bin/python -B framelease_v4/arms/run_closed_loop_v4.py \
    --arm event_triggered --route-id 2086 --output-dir outputs/framelease_v4/arms_dev/adhoc --dry-run
# dry-run job lines (2 routes x 7 arms; written, never launched)
source linux/env.sh && .conda-unidrive-linux/bin/python -B framelease_v4/arms/jobs_v4.py --check --write
# metrics of finished runs
.conda-unidrive-linux/bin/python -I -B framelease_v4/arms/metrics_v4.py --runs-root <dir> --out runs.csv \
    --arm-summary arms.csv [--realized]
```

## Open items

1. **`fl_full` is blocked until `framelease_v4/rl` delivers a Q-network.** Its two dry-run lines are in
   `pending_fl_full.jsonl` with a placeholder utility, and the check confirms the launcher rejects them. To regenerate:
   `jobs_v4.py --fl-full-utility v4_qnet_<sha12> --fl-full-env FRAMELEASE_V4_QNET=<file> --check --write --force`.
   The plumbing itself is tested with the RL task's behaviour utility.
2. **No hyperparameter is tuned yet.** The dry-run lines use the priors:
   - Age-Only: A = 2.0 s;
   - Event-Triggered: v2 thresholds, heartbeat = max age;
   - FrameLease + Heuristic: the default q95 envelope, the one that put the pilot at 89-97% fallback.
   They must be replaced by values selected on training routes before any test-route run.
3. **GPU usage is 1.0 by construction for work-conserving arms** (Fixed Deep, Fast Only, Original FrameLease, and the
   shield arms). Only Event-Triggered idles. Fig. 3's "constrained GPU budgets" needs a budget mechanism that does
   not exist yet, for example kappa sweeps or a duty-cycle cap.
4. **Untested against a live CARLA server:** the actor log and the agent class. They were tested with the real agent
   class, a fake model and a fake world. On the first real run, check:
   - per-tick wall time and size;
   - that the hero is found;
   - the estimated-vs-true LiDAR offset: about 1.4 m is expected, because the GNSS sits at x = -1.4 m and the agents
     place plans with the GNSS position.
5. **Limits of closed-loop realized validity:**
   - actors react to the ego (the offline replay is non-reactive);
   - static props are catalogued but not counted, as offline;
   - decimation, if it ever triggers, coarsens the time resolution.
6. **Each arm is charged its own boundary CPU time.** For the v2 rules this includes the decision-row features,
   which v2 never computed: tens of microseconds per boundary.
7. **The dry-run lines use ports 3300-3365 / 9300-9365 and the development routes 2086 and 18305.** They form a
   smoke matrix, not Table I.
8. **Two runtime settings stay per method, as each method was defined.**
   - `profile_quantile`: 0.95 for the v2 rules (v2 default) and 0.99 for the shield arms (v3 "p99 bounds"). It only
     matters where a rule consults latency bounds: Event-Triggered's heartbeat reservation, Original FrameLease's
     refresh reservation, and the shield.
   - `max_age_s`: 3.0 s for the non-lease arms, 2.0 s for Original FrameLease (its H_max), and 2.5 s (= H_bar) for
     the shield arms, where the lease validity does not read it.
   The shared substrate (cost model, commit gate, fallback, agent) is identical. If the protocol wants one quantile
   for every arm, pass `--runtime-params '{"profile_quantile": 0.99}'`.
