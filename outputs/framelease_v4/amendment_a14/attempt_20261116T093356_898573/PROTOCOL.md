# FrameLease v4 method-paper experiments: pre-registration protocol

**Status.** Version 1.2, 2026-11-10 (Beijing time). REGISTERED on 2026-11-10, variant FULL: the checklist of Sec. 13.1
is complete and the dated registration entry is there. At registration no v4 closed-loop run existed and no v4 job had
been enqueued. `outputs/framelease_v4/` held only offline, development, preparation and registration outputs
(`offline_ablation/`, `arms_dev/`, `rl_dev/`, `protocol/`, `envelopes/`, `p1_jobs/`, `p1_prep/`, `readiness_fixes/`,
`registration/` and the review directories `review_phase0/`, `review_p1prep/`). Every later change is an amendment
(Sec. 13.2).

**Version 1.3, 2026-11-11 (Beijing time): amendment A1 and smoke report 2 = PASS (Sec. 13.2).** The P1-0 smoke check of 2026-11-10 failed on
`pose_offset` only. The official agent anchors its GNSS frame at the route's first waypoint, so the criterion now
maps the true position into that frame before comparing; its thresholds are unchanged. No pinned file and no job
file changes. The smoke block is run again (Sec. 8.1).

**Changes in version 1.1** (before registration, after the phase-0 review; no closed-loop run existed):
1. The depth-limited heuristic a_det^d is the utility `v4_adet_d<d>`, registered for the age and shield arms in the
   launcher and in the agent process; `max_depth` is never used to tune d (Secs. 2.4, 4.1, 4.4).
2. The lease operating points E5, E10 and B0 are exported as v3 envelope files and verified against the offline
   tau* and H (Sec. 4.3).
3. The responsibility-aware (RA) rule is dropped from the closed-loop grid. It remains an offline sensitivity only
   (Secs. 4.3, 6.3).
4. The Phase-1 job generator and the stage selection script exist; the P1-0 smoke block is added (Secs. 4.2, 8).
5. Sec. 5.5 describes the FQE estimator as implemented; Sec. 2.6 has one behaviour-seed rule; Sec. 8.6 lists the
   output directories the code uses.
6. A reduced plan, TRIMMED, is defined in Sec. 14. FULL (Secs. 1-13) stays the registered default until the user
   chooses.

**Changes in version 1.2** (before registration, after the P1-readiness review of 2026-11-10; no closed-loop run existed):
1. The P1-0 smoke check has mechanical criteria and thresholds (Sec. 8.1), implemented in
   `framelease_v4/protocol/check_smoke.py` and registered before any smoke run existed. The smoke `age_only` run uses
   a_det^4 (utility `v4_adet_d4`), so the smoke covers every Phase-1 utility kind; it is still 7 runs.
2. The runner is started by `framelease_v4/protocol/launch_queue.sh` together with the disk watchdog
   `framelease_v4/protocol/disk_watchdog.sh` (Secs. 8.2, 8.5); the exact commands are in
   `outputs/framelease_v4/p1_jobs/README.md`.
3. Stage selection (Sec. 4.2): with `--queue`, a job is final only through the runner's final record or a valid run;
   a runner `ok` without a matching run directory is an error; repeated agent set-up failures are flagged; every error
   ends with a message and an exit code. The D1 summary script exists (Sec. 4.8).
4. The budget tables are computed from run counts, never by adding rounded values; disk prerequisites are rounded up
   (Secs. 10.1, 14). FULL is 1046 runs, 130.8 GPU-h.
5. The RA offline sensitivity of Table II-A cites RND Sec. 3.3; no new computation (Sec. 7.4).
6. The RL refit uses all episodes of the RL dataset: 132 in FULL, 44 in TRIMMED (Sec. 5.6).
7. The user decided that this work does not target DAC 2027 and approved the FULL budget (Sec. 13.1); no schedule-only
   reduction is registered (Sec. 10.2).
8. The CPU stress tests S1-S3 on synthetic states run before the test freeze (P3), not before registration (Secs. 4.1,
   7.6, 8.1).
9. Sec. 12.2 holds the full pin list and the script hashes; the registration manifest is
   `outputs/framelease_v4/registration/MANIFEST.sha256` (Sec. 13.1).
10. The registration checklist no longer lists the commit-audit test: the commit audit is part of the v4 aggregator and
    is tested with it before the analysis freeze (Sec. 13.1, item 1).

**Scope.** This file pre-registers every experiment of the method paper. The paper follows two documents strictly:

* the outline `/home/kang/Desktop/NEW/FrameLease1109.docx` (text in `/tmp/fl_extract/FrameLease1109.md`): Secs. I-VI,
  Eqs. 1-9, Algorithm 1, Table I with seven methods, Fig. 1, Fig. 3, Table II-A and Table II-B;
* the Introduction guide `/home/kang/Downloads/FrameLease+的+Introduction+可以从+背景.docx` (text in
  `/tmp/fl_extract/FrameLease_intro_guide.md`): background, three challenges, three mechanisms, contributions C1-C3.

**Framing.** UniDriveVLA has a latency defect: each plan takes about 0.9 s to compute (about 0.44 s with the fast prefix),
so every plan is executed on an observation that is already old and keeps aging until its successor is released.
FrameLease is the method proposed to address this defect. The experiments test whether it does. They do not
characterize the backbone.

**Rules.**
1. Every number is a real measurement.
2. Every hyperparameter of every arm is tuned on training routes only. No test route is used for tuning.
3. All arms share the backbone, the fast prefix, the GPU budget (kappa) and the runtime substrate.
4. Everything registered here is reported, including null and negative results.

**Conventions.**
* Paths are relative to `/home/kang/Desktop/DAC` unless they are absolute. Times are Beijing time.
* "Outline" means FrameLease1109; "guide" means the Introduction guide.
* "RND" means `framelease_v3/RND_REPORT_20261110.md`, the record of the offline R&D results this protocol builds on.
* Code: new code lives only under `framelease_v4/`; `framelease_v2/` and `framelease_v3/` are imported read-only.
* Outputs: new outputs go only under `outputs/framelease_v4/`.

## 0. Map from the outline and the guide to the experiments

| outline / guide element | experiment | arms, routes | section |
|---|---|---|---|
| Fig. 1, freshness-depth crossover (Sec. II) | offline C1 execution error vs observation age by depth (existing data), plus per-scenario Fixed Deep - Fast Only DS in closed loop | C1 sweep; Table I runs (44 test routes) | 7.1 |
| Sec. II objective: max E[S_drive] subject to validity, timing and GPU budget | DS is the primary metric; validity: lease, shield and commit; timing: deadline misses; GPU budget: kappa | all | 2.3, 6 |
| Eqs. 1-3, Proposition 1 (lease, coverage) | offline lease ablation with envelope coverage; closed-loop realized validity | 32 VAL clips; all shield arms | 7.4, 6 |
| Eq. 5 shield, Eq. 8 decision | every shield arm; P_both, shield violations, budget overruns | Table I | 4.1, 6 |
| Eqs. 6-8 RL (CPU Q-network), Eq. 7 reward | offline FQI on training routes, deployed in Full FrameLease | Sec. 5 | 5, 7.5 |
| Eq. 9 versioned commit, watchdog | commit invariant audit of every run; fault injection | all runs; CPU | 7.6 |
| Algorithm 1 | the runtime of every shield arm | Table I | 2.3, 4.1 |
| Table I, seven methods | main matrix: 7 arms x 44 test routes, kappa 1.0 | test | 7.2 |
| Fig. 3, DS vs action age under GPU budgets | 4 arms x kappa {1.0, 1.5, 2.0} | test subset E | 7.3 |
| Table II-A, lease ablation | Age-Only vs Global-Margin vs Suffix-Aligned leases (violation rate, utilization, premature refresh, DS) | offline: 32 VAL clips; closed loop: `age_only`, `fl_global_shield`, `fl_heuristic` on E | 7.4 |
| Table II-A, RL ablation and P_both | Heuristic vs Bandit vs FQI vs FQI without lease features | E (and all 44 for Heuristic vs FQI) | 7.5 |
| Table II-B, runtime overhead and stress | timing from the logs; CPU stress tests S1-S3; kappa 2.0 as GPU contention (S4) | all shield-arm runs; CPU bench | 7.6 |
| IV-A main findings 1-3 | hypotheses H1-H3 | Table I arms, 44 test routes | 1.2, 9 |
| "report RL gain by scenario category, GPU budget and seed" | descriptive breakdowns of Full - Heuristic | by ability (44), kappa (E), seed (R) | 7.5 |
| "training and test scenarios strictly separated" | route split and leakage rules | 44 test / 44 training routes | 3 |
| guide C1 (action-conditioned validity lease) | Table II-A lease panel, coverage, realized validity (H4) | 32 VAL clips; E | 7.4 |
| guide C2 (validity-constrained utility-aware scheduling) | Table I (H1), RL panel (H2), P_both | 44 test routes; E | 7.2, 7.5 |
| guide C3 (runtime integration and evaluation) | Table II-B, deadline misses, commit invariant (H5) | all runs; CPU bench | 7.6 |
| guide challenges 1 / 2 / 3 | Fig. 1 / Age-Only arm and Age-Only lease / shield plus RL | as in the rows above | 7.1 / 7.2, 7.4 / 7.2, 7.5 |

The rows above describe FULL, the registered plan. TRIMMED (Sec. 14) keeps every row but runs Fig. 3 and the Table II-A
closed loop on subset C, tunes on T22a only and has no seed-12 replicates.

## 1. Purpose, claim and hypotheses

### 1.1 The defect and the method

**The defect.** UniDriveVLA (Bench2Drive stage-3 2B checkpoint) computes a plan in two parts on an RTX 4090 D:
* a non-preemptible prefix (vision encoder, LLM and perception expert): 881 ms p50 in C1 and 946 ms in the fast-prefix
  equivalence run;
* flow-matching refinement steps of 14.6 ms each (`framelease_v2/C1_RESULTS.md` Sec. 1; RND Table 8).

Under measured-latency execution every plan therefore acts on an old observation. In the v2 matrix at kappa 1.0 the
median action age was 1.40 s for Fast Only and 1.60 s for Fixed Deep. On the 22 routes of subset E, the synchronous
evaluation (world paused during inference) scored higher than measured-latency execution:
* +37.5 DS points [20.6, 53.2] over Fast Only (exact sign-flip p = 0.0005);
* +19.7 DS points [2.9, 35.8] over Fixed Deep (p = 0.034, Holm 0.068)
(`framelease_v2/CLOSED_LOOP_RESULTS.md`). These results are known before registration (Sec. 11).

**The method.** FrameLease addresses the defect by scheduling the GPU around action validity rather than observation age
(outline Sec. III):
1. **Suffix-aligned validity lease (Eqs. 1-3).** Each candidate plan gets a deadline D = t_k + H.
2. **Feasibility shield (Eq. 5).** The shield admits REFINE or REFRESH only if the action's result can be committed
   before the deadline of the active plan.
3. **Utility selection (Eqs. 6 and 8).** A CPU Q-network chooses between the admissible actions when both are admissible.
4. **Runtime safeguards (Eq. 9, watchdog, budgeted policy).** These keep expired, cancelled or regressive plans out of
   the controller.

### 1.2 Hypotheses

Decision rules are in Sec. 9. "Matched compute" means the same checkpoint, the same fast prefix, the same kappa and the
same runtime class (Sec. 2).

* **H1 (primary; outline IV-A findings 1 and 2).** At kappa 1.0 with matched compute, Full FrameLease achieves a higher
  driving score (DS) than each of Fixed Deep, Fast Only, Age-Only and Event-Triggered on the 44 test routes. There are
  four contrasts, with Holm correction across them.
* **H2 (key secondary; finding 3).** Full FrameLease achieves a higher DS than FrameLease + Heuristic (same lease and
  shield; only the utility selector differs). The outline requires this to be claimed only if the data support it.
* **H3 (key secondary).** The new design improves on the earlier one: FrameLease + Heuristic, and Full FrameLease,
  achieve a higher DS than Original FrameLease.
* **H4 (lease ablation; guide C1).**
  * Offline, at matched conditional risk R_cond, the suffix-aligned lease leaves a larger usable window than the
    global-margin lease. The window is measured by continuity at the fast-prefix need and by utilization.
  * In closed loop on subset E, FrameLease + Heuristic achieves a higher DS than the same scheduler with the
    global-margin lease or with the Age-Only lease.
* **H5 (runtime; guide C3).**
  * No expired, cancelled, invalid or regressive candidate is ever committed. This is a program invariant, checked on
    every run and under fault injection.
  * Scheduler overheads stay within the shield's budgets: policy p99 within B_pi, and budget overruns and deadline
    misses reported.

Fig. 3 is analysed descriptively, with a secondary contrast family (Sec. 9.3).

### 1.3 What this protocol does not claim

* The lease is calibrated statistically, from residual quantiles on offline clips. Proposition 1 holds only under its
  envelope assumption, so its coverage is reported and never stated as an unconditional guarantee (outline III-A,
  paragraph 4).
* The shield uses empirical p99 latency bounds. Its timing protection is soft real time, not a hard guarantee (outline
  III-B, paragraph 2; III-C).

## 2. Common settings (system under test)

### 2.1 Backbone, simulator and hardware

The settings below are identical to the v2 matrix (`framelease_v2/PREREGISTRATION.md` Sec. 4) unless stated otherwise.

**Model.**
* UniDriveVLA Stage-3 Bench2Drive 2B checkpoint, sha256 `b127eebb319aa52dbd35f2099bb1bda5c1c7732c2f811cae88454ce15e6c23fc`;
  source commit a93c175.
* Precision `bf16-autocast`, prompt command `official`, warm-up on.

**Simulator and evaluator.**
* Official Bench2Drive leaderboard evaluator, SENSORS track at 20 Hz, with the crash-cleanup narrowing of stage05.
* CARLA 0.9.15 offscreen, one route per launch, `IS_VISUALIZE=0` (no images are written).
* Official sensors, preprocessing and PID controller.

**Hardware and software.**
* One RTX 4090 D (24 GB), 16 CPU cores, 30 GB RAM.
* torch 2.5.1+cu124. Interpreter `.conda-unidrive-linux/bin/python` with `linux/env.sh`.
* The GPU is serialized through the shared GPU lock of `framelease_v2/gpu_queue.py`.

### 2.2 Fast prefix (all arms)

Every arm runs with the fast-prefix option `--fast-prefix sdpa,gpu_preproc,lora_merged` (`framelease_v3/fastprefix`;
RND Sec. 3.8). It combines SDPA attention, exact GPU image preprocessing and a merged LoRA.

| quantity | baseline | fast prefix |
|---|---|---|
| prefix p50 | 946 ms | 439 ms (2.14x) |
| depth-1 release p50 | 962 ms | 457 ms |
| continuity need 2 L_rel + 0.05 s | 1.97 s | 0.96 s |

* Plans change by 1-5 cm, within the seed-to-seed spread.
* The option validated in all 8 fast runs of the CARLA pilot: charged prefix 0.42 s against 0.92 s, and median action
  age 0.70 s against 1.45 s (RND Sec. 5).
* Every run must report `raw/agent/framelease/fast_prefix.json` with `stage: final`, a passed validation and more than
  0 SDPA calls (manipulation check, Sec. 9.7).

### 2.3 Runtime substrate, cost model and GPU budget

**One runtime class.** Every arm runs on `V4Runtime` (`framelease_v4/arms/runtime_v4.py`). It is v3's `V3Runtime`, which
is v2's measured-latency `LatencyRuntime` plus:
* the Eq. 9 commit gate;
* job cancellation;
* watchdog accounting;
* decision logging;
* a uniform summary block for every arm.

For a v2 rule (Fixed Deep, Fast Only, Event-Triggered, Original FrameLease) it must produce the same timeline as v2.
This is a CPU test in `framelease_v4/arms` and a registration requirement (Sec. 13.1).

**Common runtime settings.**
* `cost_mode = measured`, `temporal_mode = latest`, `extrapolation = constant_velocity`.
* `fallback_brake = 1.0`: full brake while no valid committed plan exists.
* `versioned_commit = true`, `guard_s = 0.05`.
* Latest-frame rule: a job takes the newest captured frame, and no frame is processed twice.

**Time charging (unchanged v2 cost model).**
* The prefix and every flow step run for real on the GPU and are charged kappa x their measured CUDA-event time on the
  simulated timeline.
* Every scheduler boundary is charged its measured CPU time (lease, commit check and decision; `overhead_scale` 1).
* Cooperative preemption happens only at refinement-quantum boundaries. A quantum is the prefix (plus step 1) or one
  flow step.

**GPU budget.**
* The budget is the contention scale kappa. kappa 1.0 is the primary setting; kappa 1.5 and 2.0 are used for Fig. 3.
* kappa corresponds to a GPU share b = 1/kappa (100%, 67%, 50%).
* All arms of a contrast run at the same kappa.
* The outline's Eq. 5 term G(a) <= G_rem is vacuous in this single-tenant setting. The budget acts through the
  kappa-scaled latency bounds of the shield and through the timeline. This is a stated simplification.

**GPU usage** is the measured outcome (Sec. 6), not a constraint.

### 2.4 Lease, shield and commit constants (shield arms)

The values are those of `framelease_v3/runtime` (README "Mapping to the outline").

**Lease.**
* T_pred = 3.0 s (6 waypoints x 0.5 s), T_c = 0.5 s, d_safe = 0.5 m, delta = 0.2 m.
* Time grid of 0.05 s; H_bar = 2.5 s.
* Relevant agents: vehicles and pedestrians with score >= 0.1. Low-confidence detections use mode `cap` and can only
  shorten the lease.
* A non-finite plan or missing perception gives H = 0. No relevant agent gives H = H_bar.
* Margins come from the model's own detections at constant velocity, inflated by the residual envelope (Sec. 4.3).

**Shield (Eq. 5).**
* Feasibility requires t + L_pi + L_a + L_commit + R_a + eps < D*, with:
  * eps = 0.05 s;
  * R_REFINE = L_REFRESH + L_commit, R_REFRESH = 0;
  * bounds at the p99 of the runtime's own measured latency profile (`profile_quantile 0.99`), kappa-scaled.
* C_REFINE: depth d < 10, and the refined result can still be committed before the running candidate's own deadline.
* C_REFRESH: a frame newer than the running job's observation exists.
* The maximum depth in C_REFINE is 10 in every shield arm. The heuristic's depth limit d* is a utility parameter, not a
  shield parameter (Sec. 4.4). This keeps the shield identical for FrameLease + Heuristic and Full FrameLease.
  `framelease_v4/arms/arms_v4.py` enforces it in the launcher and again in the agent: a policy or runtime `max_depth`
  other than 10 is rejected for every age and shield arm, and d is set only through the utility name
  `v4_adet_d<d>`.

**Decision (Eq. 8).**
* |A_feas| = 2: the utility selector chooses.
* Exactly one feasible action: that action.
* None: control mode FALLBACK. The controller keeps the active plan until D*, then the watchdog brakes. A recovery
  refresh starts at once, or the scheduler WAITs for a newer frame.

**Commit (Eq. 9).** The gate checks, in this order:
1. not cancelled;
2. valid plan;
3. admissible version (newer observation, or the same observation at greater depth);
4. t_commit < D;
5. M(t_commit - t_k) > delta.

Runtime `max_age_s` is 2.5 (= H_bar) for the shield arms.

### 2.5 Logging (all arms)

**Per run** (`raw/agent/framelease/`):
* the v2/v3 logs `ticks.jsonl`, `jobs.jsonl`, `events.jsonl` and `summary.json`;
* `decisions.jsonl`: v3 schema, one row per boundary decision with 32 state features, plus `v4_*` keys for the RL
  utilities;
* the official `raw/official_results.json` and `raw/agent/metric_info.json`.

**Actor-box log** (`framelease_v4/arms/actor_log.py`), for evaluation only:
* CARLA ground-truth vehicle and walker boxes per tick, quantized, gzip JSONL, with a budget of <= 2 MB per run
  (adaptive decimation);
* it is never read by any policy;
* it feeds the realized-validity metrics (Sec. 6).

No camera images are written.

### 2.6 Seeds

* Test matrix: seed 11; the Traffic Manager seed equals the run seed.
* Replicates: seed 12 (subset R).
* Tuning and RL-data runs: seed 11.
* The behaviour utility's exploration generator has one seed per run, by one rule
  (`framelease_v4/rl/collection_plan.py` `behaviour_seed`, also used for the P1-0 smoke run):
  seed = int(sha256(`framelease_v4_behaviour|20261110|<route>|<kappa formatted %.2f>|<rep>`)[:16], 16) mod 2^62.
  `rep` is 0 for the single behaviour run of a route and kappa (FULL) and 0 / 1 for the two behaviour seeds of a route
  (TRIMMED, Sec. 14). The utility name is `v4_eps0.300_seed<seed>[_d<d*>]`, so the name records the seed.

## 3. Routes

The machine-readable split is `outputs/framelease_v4/protocol/route_split.json`. It is generated by
`framelease_v4/protocol/make_protocol_tables.py` (`--check` re-derives it) from `bench2drive220.xml` (sha256
`ffff24b3...0e8`; 220 routes, 44 scenario types x 5).

### 3.1 Test set (44 routes)

**The set.** The 44 routes of `outputs/framelease_v2/closed_loop_matrix/routes.json` (sha256 `09f581de...3f2`): the
lowest route id of each scenario type. Route 2086 was excluded there; this did not change the selection, and 2084 is used.
* The table with town and type is in `framelease_v2/PREREGISTRATION.md` Sec. 3.
* By town: Town12 33, Town13 8, Town04 2, Town07 1 (from the XML).
* Total length: 4.61 km (XML polyline).

Subsets are by the v2 index, i.e. the position in the id-sorted list:

| subset | rule | n | routes |
|---|---|---:|---|
| E | index % 2 == 0 | 22 | 1711, 1790, 1852, 2050, 2084, 2127, 2164, 2204, 2286, 2390, 2509, 2664, 2790, 3248, 3436, 3540, 3936, 14842, 17752, 23695, 23901, 28087 |
| C | index % 4 == 0 | 11 | 1711, 1852, 2084, 2164, 2286, 2509, 2790, 3436, 3936, 17752, 23901 |
| R | index % 3 == 0 | 15 | 1711, 1825, 2050, 2115, 2164, 2273, 2390, 2534, 2790, 3364, 3540, 14194, 17752, 23771, 28087 |

### 3.2 Training pool (44 routes)

**The pool.** The second-lowest route id of each scenario type. It is disjoint from the test set by construction
(checked by the script). It contains the development route 2086 and the four fast-prefix pilot routes 2086, 18305, 2554
and 1792.
* By town: Town12 29, Town13 7, Town01 2, Town07 2, Town10HD 2, Town04 1, Town15 1.
* Total length: 4.49 km.

**Subsets.** The index is the position in the id-sorted training list.
* T22a = index % 4 == 0 (11 routes).
* T22b = index % 4 == 2 (11 routes).
* T22 = T22a ∪ T22b, the 22 tuning routes.
* RL = all 44 training routes, used for the offline-RL data.

| idx | route | town | scenario type | test route of the type | subset |
|---:|---:|---|---|---:|---|
| 0 | 1792 | Town12 | HazardAtSideLane | 1790 | T22a (pilot) |
| 1 | 1833 | Town12 | ConstructionObstacleTwoWays | 1825 | |
| 2 | 2086 | Town12 | NonSignalizedJunctionLeftTurn | 2084 | T22b (dev, pilot) |
| 3 | 2129 | Town12 | OppositeVehicleTakingPriority | 2127 | |
| 4 | 2215 | Town12 | BlockedIntersection | 2204 | T22a |
| 5 | 2283 | Town12 | MergerIntoSlowTraffic | 2273 | |
| 6 | 2397 | Town12 | VanillaNonSignalizedTurn | 2390 | T22b |
| 7 | 2513 | Town12 | ConstructionObstacle | 2509 | |
| 8 | 2539 | Town12 | Accident | 2534 | T22a |
| 9 | 2554 | Town12 | ParkedObstacle | 1773 | (pilot) |
| 10 | 2643 | Town12 | AccidentTwoWays | 1852 | T22b |
| 11 | 2668 | Town12 | ParkedObstacleTwoWays | 2664 | |
| 12 | 2715 | Town12 | StaticCutIn | 2709 | T22a |
| 13 | 2802 | Town12 | InvadingTurn | 2790 | |
| 14 | 2844 | Town12 | OppositeVehicleRunningRedLight | 2082 | T22b |
| 15 | 2903 | Town12 | NonSignalizedJunctionRightTurn | 2115 | |
| 16 | 2943 | Town12 | VehicleTurningRoute | 2144 | T22a |
| 17 | 3072 | Town12 | HighwayCutIn | 2286 | |
| 18 | 3090 | Town12 | CrossingBicycleFlow | 3086 | T22b |
| 19 | 3144 | Town12 | VanillaSignalizedTurnEncounterRedLight | 2373 | |
| 20 | 3184 | Town12 | VanillaNonSignalizedTurnEncounterStopsign | 2416 | T22a |
| 21 | 3255 | Town13 | ParkingCrossingPedestrian | 3248 | |
| 22 | 3373 | Town13 | YieldToEmergencyVehicle | 3364 | T22b |
| 23 | 3472 | Town13 | VehicleOpensDoorTwoWays | 3464 | |
| 24 | 3514 | Town13 | ParkingExit | 1956 | T22a |
| 25 | 3731 | Town13 | VehicleTurningRoutePedestrian | 2164 | |
| 26 | 3749 | Town13 | EnterActorFlow | 2201 | T22b |
| 27 | 4183 | Town12 | SignalizedJunctionLeftTurn | 3936 | |
| 28 | 4937 | Town12 | SignalizedJunctionRightTurn | 2050 | T22a |
| 29 | 14862 | Town12 | VanillaSignalizedTurnEncounterGreenLight | 14842 | |
| 30 | 17569 | Town12 | SequentialLaneChange | 17563 | T22b |
| 31 | 18305 | Town12 | ParkingCutIn | 1711 | (pilot) |
| 32 | 23659 | Town12 | HighwayExit | 23658 | T22a |
| 33 | 23700 | Town12 | InterurbanAdvancedActorFlow | 23695 | |
| 34 | 23910 | Town12 | InterurbanActorFlow | 23901 | T22b |
| 35 | 24092 | Town13 | MergerIntoSlowTrafficV2 | 23771 | |
| 36 | 24211 | Town01 | DynamicObjectCrossing | 17752 | T22a |
| 37 | 24258 | Town07 | HazardAtSideLaneTwoWays | 3436 | |
| 38 | 24330 | Town10HD | HardBreakRoute | 3540 | T22b |
| 39 | 24340 | Town10HD | ControlLoss | 3561 | |
| 40 | 25863 | Town07 | PedestrianCrossing | 14194 | T22a |
| 41 | 28035 | Town01 | T_Junction | 26458 | |
| 42 | 28093 | Town04 | NonSignalizedJunctionLeftTurnEnterFlow | 28087 | T22b |
| 43 | 28198 | Town15 | SignalizedJunctionLeftTurnEnterFlow | 28099 | |

### 3.3 Leakage rules

1. **No tuning on test routes.** No test route is used for any tuning, selection, RL training, RL model selection,
   envelope fitting or threshold choice. The RL dataset builder refuses test routes (`framelease_v4/rl/dataset.py`
   guard). The selection scripts read only training-route run directories.
2. **Fixed offline inputs.** The offline inputs of the lease were fixed before this protocol. These are the envelope
   candidates, fitted on the 5 TRAIN clips of the C1 sweep, and the offline selection on the 32 VAL clips. The offline
   clips are recorded dataset clips (Bench2Drive base train/val), not leaderboard routes, so they share no route with
   the closed-loop test set.
3. **Shared town and scenario types.** Training and test routes share scenario types and, mostly, towns. As in every
   Bench2Drive evaluation, test routes come from the same generator as the training data.
4. **Test runs start only after the test freeze (Sec. 8.1).** Before that freeze every selected parameter, the Q-network
   files and the job files of Phases 4-6 are fixed and hashed.

## 4. Arms of Table I and their tuning on training routes

### 4.1 Arm definitions (code level)

All arms share the settings of Sec. 2: checkpoint, fast prefix, `V4Runtime`, cost model, kappa, controller, fallback and
logging. Policy classes are in `framelease_v4/arms/policies_v4.py`, which subclasses v2 and v3 and edits nothing
upstream.

Notation used below:
* a_det^{d} is the heuristic utility of Sec. 4.4.
* E* is the selected lease operating point (Sec. 4.3; validity definition std).
* d*, A* and (theta*, A_hb*) are the selected heuristic depth, Age-Only threshold and Event-Triggered configuration
  (Secs. 4.4-4.6).

| arm id | Table I name | policy | refinement and exposure | validity (deadline) | scheduling | tuned on T22 |
|---|---|---|---|---|---|---|
| `fixed_deep` | Fixed Deep | `logged_v2_class('fixed_deep')` = v2 `FixedDeep(depth=10)` | 10 flow steps; only the depth-10 plan is offered | observation age < `max_age_s` 3.0 s | work-conserving: next job on the newest frame when the GPU is free | none |
| `fast_only` | Fast Only | v2 `FastOnly(depth=1)` | 1 flow step | age < 3.0 s | work-conserving | none |
| `age_only` | Age-Only | `AgeLeasePolicy(age_lease_s=A*)`, utility a_det^{d*} (`heuristic` if d* = 10, else `v4_adet_d<d*>`) | anytime, up to depth 10 | constant-age lease D = t_k + clip(A*, 0, 2.5 s) | shield Eq. 5 + Eq. 8 | A* (Sec. 4.5); d* inherited |
| `event_triggered` | Event-Triggered | `EventTriggeredV4(theta*, heartbeat_s=A_hb*)` | anytime up to depth 10; preempted at the next quantum on an ego event | age < 3.0 s | non-work-conserving: a job starts on an event or at the heartbeat | (theta, A_hb) (Sec. 4.6) |
| `fl_original` | Original FrameLease | `logged_v2_class('framelease')` with `lease_params_q95_envelope.json` | anytime | global-margin lease, H_max 2.0 s | v2 refresh-time reservation rule | none: the registered v2 design |
| `fl_heuristic` | FrameLease + Heuristic | v3 `ShieldedHeuristicPolicy`, envelope E* (exported file, Sec. 4.3), utility a_det^{d*} (`heuristic` or `v4_adet_d<d*>`; no other utility is accepted) | anytime | suffix lease Eqs. 1-3 (<= 2.5 s) | shield Eq. 5 + Eq. 8 | E* (Sec. 4.3); d* (Sec. 4.4) |
| `fl_full` | Full FrameLease | as `fl_heuristic`, utility `v4_qnet_<sha12>` (FQI family, Sec. 5; only Q-network utilities are accepted) | anytime | as `fl_heuristic` | shield + CPU Q-network (Eqs. 6, 8), bypass to a_det^{d*} | as `fl_heuristic`, plus the Q-network (Sec. 5.6) |

Ablation and data-collection arms. These are not in Table I. All use the shield, E* and d* of `fl_heuristic`
unless stated otherwise.

| arm id | role | difference from `fl_heuristic` |
|---|---|---|
| `fl_global_shield` | Table II-A, Global-Margin lease | The suffix lease is replaced by the global-margin lease. This is the offline `GLOBAL` design of `framelease_v4/offline/common.py`: the v2 lease with `margin_mode='global'`, the same envelope E* used as the staleness-indexed B(D), the standard validity definition, and the cap 2.5 s. The commit-time margin check uses a synthetic margin that crosses delta exactly at H, as `AgeLeasePolicy` does. |
| `fl_bandit` | Table II-A, Shield + Contextual Bandit | utility = the bandit family's selected network |
| `fl_fqi_nolease` | Table II-A, FQI without lease-slack features | utility = the `fqi_nolease` family's selected network (10 non-lease features); the shield is unchanged |
| `fl_risk` | sensitivity, only if L* = B0 (Sec. 4.3; FULL only) | lease point = the better of E5 and E10 by mean DS on T22a |
| `fl_behaviour` | offline-RL data (training routes only) | behaviour utility `v4_eps0.300_seed<s>[_d<d*>]`, eps = 0.3 around a_det^{d*} (Sec. 5.3); a registered arm of the v4 launcher (V4Runtime, actor log), accepting only behaviour utilities |

**Event-Triggered in detail.** The v2 rules are kept unchanged.

Events are observable at runtime only:
* ego speed change > Δv;
* heading change > Δψ since the capture of the newest processed observation (agent speedometer and compass);
* a route-command change;
* a change of the confident detection set (score >= 0.3) within 30 m between the two most recent prefixes: a relevant
  object appeared, moved more than the shift threshold from its constant-velocity prediction, or vanished.

Without an event, the next job starts when the incumbent's age reaches A_hb minus the refresh reservation
(L_refresh^bnd + guard).

**Original FrameLease versus Full FrameLease.** The outline requires the difference between these two arms to be defined
precisely:

| aspect | Original FrameLease (`fl_original`) | Full FrameLease (`fl_full`) |
|---|---|---|
| margin | global: per agent, the minimum clearance over the whole plan [0, T_pred], past prefix included | suffix-aligned: minimum over [Δ, Δ + T_c] (Eq. 1) |
| horizon | H_j = sup{D : m_j - B(D) > delta}, H = min_j H_j, capped at H_max = 2.0 s = runtime `max_age_s` | first failure (Eq. 2), H_bar = 2.5 s, D = t_k + H (Eq. 3) |
| envelope | v2 isotropic q95 file calibrated on the 5 TRAIN clips, reserve 0.2 m (sha256 `00c62aad...10e8`) | the selected E* (Sec. 4.3; standard validity) |
| scheduling | v2 reservation rule: keep refining while D - now - L_refresh^bnd - G >= next step cost, else refresh; no feasible set | shield Eq. 5 with per-action bounds, recovery reserve R_REFINE and eps (Sec. 2.4) |
| utility | none (rule) | CPU Q-network (Eqs. 6, 8) with policy budget and bypass to a_det^{d*} |
| commit | version, deadline and plan validity | Eq. 9: also cancellation and M(t_commit - t_k) > delta |
| fallback | expiry, then full brake | the same plus recovery refresh and watchdog accounting |
| tuning | none (registered v2 configuration, 2026-11-07) | E* and d* on T22 (TRIMMED: T22a); Q-network on training routes (Sec. 5) |

A tuned counterpart of the global margin, which isolates suffix alignment from everything else, is `fl_global_shield`
(Sec. 7.4).

**Implementation status (version 1.2, at registration), and what is still required.**

Present and tested on the CPU:
* `framelease_v4/arms`: `AgeLeasePolicy`, `EventTriggeredV4`, `logged_v2_class`, `V4Runtime`, the actor-box log,
  realized validity, the arms `fl_behaviour` and the utility rules of Sec. 2.4 (`arms_v4.arm_utility`,
  `check_shield_depth`; registration in `build_config` and `build_policy`, i.e. launcher and agent process).
* `framelease_v4/rl`: the behaviour utility, the a_det^d utility `v4_adet_d<d>`, prefix score, dataset (v3 and v4
  launcher runs), trainers, OPE and Q-network, with a_det^{d*} as the default action of trainers, OPE and Q-network.
* `framelease_v4/offline/export_envelopes.py`: the envelope files E5, E10, B0 (Sec. 4.3).
* `framelease_v4/protocol/p1_jobs.py` and `select_stage.py`: Phase-1 job files and stage selection (Secs. 4.2, 8).
* `framelease_v4/protocol/check_smoke.py` (the P1-0 criteria of Sec. 8.1), `d1_summary.py` (the D1 table of Sec. 4.8),
  `launch_queue.sh` and `disk_watchdog.sh` (runner launch with the disk watchdog, Secs. 8.2, 8.5); tests in
  `framelease_v4/protocol/tests`.

Still required, not needed for Phase 1:
1. the `fl_global_shield` lease and the arms `fl_bandit` and `fl_fqi_nolease` (before the P4-P6 job files, Sec. 8.1);
2. the v4 aggregator and the analysis script (before the analysis freeze, Sec. 9.12), including infractions per km
   (Sec. 6.1) and the Proposition-1 coverage of the deployed E* (Sec. 7.4);
3. the CPU stress bench S1-S3 (Sec. 7.6; run on synthetic states before the test freeze, P3);
4. the P2-P6 job generators (the P2 run list is `framelease_v4/rl/collection_plan.py`).

Status (Amendment A3): the `fl_global_shield` lease of item 1, the aggregator of item 2 (with infractions per km), item
3 and item 4 are implemented and registered; the analysis script, the Proposition-1 coverage, the figure and table
generator and the independent verification script are registered by Amendment A10. `fl_bandit` and `fl_fqi_nolease` of
item 1 are configurations of launcher arm `fl_full` with the networks of their families (Amendment A4).

### 4.2 Tuning objective and procedure

**Objective.** Mean DS over training routes:
* closed loop, kappa 1.0, seed 11, fast prefix;
* every other setting as in the test matrix.

This is the outline's utility objective (Sec. II), and it keeps tuning off the test set (IV-A, paragraph 1).

**Procedure: successive halving (SH) with two stages of 11 routes,** for a grid of K candidates listed in a fixed
candidate order.
1. **Stage 1.** Run every candidate on T22a (11 routes). Rank by mean DS. The top ceil(K/2) survive. Ties at the cut
   go to the earlier candidate in the order.
2. **Stage 2.** Run every survivor on T22b (11 routes), unless that run already exists.
3. **Selection.** Select the survivor with the highest mean DS over all 22 routes of T22. Ties (difference < 1e-9) go
   to the earlier candidate.

**Failed runs.** A run without a valid official record after the single infrastructure retry (Sec. 8.4) is handled by
cause:
* simulator-side failure (`Simulation crashed`, CARLA timeout, launch error): the route is dropped from that stage for
  every candidate;
* `Agent crashed`: it counts as DS = 0 for that candidate, because the agent code is part of the candidate.

Every other cause without a valid record (`Agent's sensors were invalid`, `Agent couldn't be set up`, a wall-clock
timeout without a record) is handled like a simulator-side failure, and the selection output lists it by cause.

**Recorded but not used for selection.** RC, success, collisions/km, fallback ratio, DMR, action age, realized
validity (EIR and closed-loop R_cond, standard yardstick), P_both, lease p50 and GPU usage. Together they form the
training-route operating-point table, reported in full in the paper or its appendix.

**Selection scripts.** `framelease_v4/protocol/select_stage.py` is deterministic and its sha256 is recorded at
registration (Sec. 12.2). Its output JSON is written, and its hash entered in Sec. 13, before the job file of the next
block is generated. As implemented:
* Input: the stage spec that `framelease_v4/protocol/p1_jobs.py` writes next to each job file (candidates in the
  registered order, the job id and output directory of every candidate x route, runs reused from an earlier block),
  the run directories of those jobs, and the runner's `status.jsonl` (`--queue outputs/framelease_v4/queue_p1`, the
  protocol's mode).
* Finality, with `--queue`: a job is final only through a matching valid run directory or the runner's final `end`
  record (the runner's own `Runner.job_states`). Attempts the runner did not count (shared GPU lock busy, runner
  interrupted) never make a job final, and a job that the runner re-tries after a final record (`--retry-failed`) is
  pending again. A runner record `ok` or `result_with_warnings` that names no matching valid run directory of the
  candidate is an error: the selection stops and is never written, and the route is never silently dropped. Without
  `--queue`, finality is inferred from the run directories (two failed attempts with a result; attempts that met a
  busy GPU lock are not counted).
* Per job: the first valid record gives the DS; otherwise the cause of the final attempt decides (`Agent crashed`:
  DS 0; anything else: the route is dropped for every candidate of the stage). A job with no final outcome makes the
  stage incomplete, and no selection is written (exit code 3).
* Flags: a candidate with two or more attempts ending in `Agent couldn't be set up` in a stage is flagged in the
  selection output. The rule above is unchanged (those routes are dropped for every candidate); the flag is
  investigated before the next block is generated, because a configuration that cannot set up the agent is an
  implementation defect, and it is reported at D1.
* Errors: an unknown stage, the reference block `ref` (reported, not selected; Sec. 4.8), a missing stage spec or
  selection, a missing `status.jsonl` and inconsistent runner records end with a message and exit code 2.
* A non-final stage keeps the top ceil(K/2); the final stage selects (FULL: over T22; TRIMMED: over T22a).
* `p1_jobs.py` generates a dependent block only from a complete selection whose recorded stage-spec sha256 equals the
  current stage spec of the previous block, and records the selection's sha256 in the new stage spec.
* `select_stage.py --freeze` writes the tuning freeze (Sec. 4.9).

**Precision and fairness.** The paired SD of route DS differences was about 31 points in the v2 matrix (Sec. 9.10). The
SE of a candidate difference is therefore about 9 points on 11 routes and 6.6 points on 22 routes. Tuning can separate
only large differences. This applies equally to every tuned arm. The number of closed-loop configurations each arm was
selected from is reported:
* FrameLease: 3 lease points + 2 extra depths;
* Age-Only: 4;
* Event-Triggered: 4.

(TRIMMED, Sec. 14: 3 + 1, 3 and 2.)

### 4.3 Lease operating-point grid (FrameLease + Heuristic, Full FrameLease, RL arms)

**Envelope levels.** They come from the offline candidates of RND Secs. 3.1-3.10, fixed before any closed-loop run.

* **E5.** The Suffix-Aligned candidate selected by rule (a) at R_cond <= 5% on the 32 VAL clips pooled. This is the
  in-sample row (`design SUFFIX`, `subset all`, `need fast` = 0.964 s, `risk R_cond`, `alpha 0.05`) of
  `outputs/framelease_v4/offline_ablation/frontier.csv`.
  * Rule (a): maximal continuity at the need, subject to R_cond <= alpha; ties go to lower R_cond, then candidate order.
  * The candidate family is fitted on the 5 TRAIN clips only:
    * E0 isotropic at q30 ... q99.5;
    * λ x E0 q95 for λ = 0 ... 2;
    * the v2 file.
  * Its out-of-sample performance is the nested leave-one-clip-out estimate reported in Table II-A.
* **E10.** The same rule at alpha = 0.10.
* **B0.** No envelope (λ = 0, B ≡ 0): the nominal suffix margin with d_safe 0.5 m and delta 0.2 m.

**Validity definition.** `std`: Eqs. 1-3 as written; every relevant agent counts. This is the only validity
definition of the closed-loop grid and of every closed-loop arm.

The responsibility-aware rule `RA_RULE` of `framelease_v3/renewal/renewal_compute.py` (RND Sec. 3.3) is not part of
the closed-loop grid. It changes the definition of validity (a contact interval of a vehicle behind the rear edge line
of the planned ego box, heading within 60° of the ego heading, is ignored), so a closed-loop gain from it could not be
separated from the definition change. It is kept only as an offline sensitivity of Table II-A, cited from RND Sec. 3.3
(Sec. 7.4), labelled as a definition change, and never presented as standard-validity safety evidence.

**Grid,** in candidate order (most conservative first):

| candidate | E5 | E10 | B0 |
|---|---|---|---|
| envelope | T_x0.60 (0.60 x E0 q95) | T_x0.30 (0.30 x E0 q95) | T_x0.00 (none) |
| offline in-sample row | continuity 0.528, R_cond 0.048 | continuity 0.643, R_cond 0.088 | (availability end) |
| validity | std | std | std |

* If E5 and E10 are the same candidate, E10 is dropped.
* If E5 or E10 is itself B0 (λ = 0), it is dropped; B0 keeps its own slot.
* If an alpha selection returns `ZERO` (no candidate meets alpha), its slot is dropped.
* K is the number of remaining candidates; ceil(K/2) survive Stage 1. At writing no rule applies: K = 3, so 2 survive.
* During this grid FrameLease + Heuristic uses d = 10 (utility `heuristic`), the v3 slack-filling heuristic.

**Envelope files.** `framelease_v4/offline/export_envelopes.py` (sha256 `e01589a8...ead67`) reads the multi-configuration
file `outputs/framelease_v4/offline_ablation/envelopes/train_E0.json` (sha256 `86821422...dff8`) and the frontier
`outputs/framelease_v4/offline_ablation/frontier.csv` (sha256 `9941574c...d5f7`), applies the pruning rules above and
writes the v3 isotropic form `{"kind": "iso", "sigma_m", "vbar_mps", "abar_mps2", ...}` that
`framelease_v3/runtime` `v3_lease.load_envelope` reads:

| point | file | configuration | sha256 |
|---|---|---|---|
| E5 | `outputs/framelease_v4/envelopes/E5.json` | T_x0.60 | `21d0b4a441cf80e32e4f04ddeb9bf309b5a0a74c9495652fd04a88331c47df3a` |
| E10 | `outputs/framelease_v4/envelopes/E10.json` | T_x0.30 | `bf61635ba3a38b7a307a4e1e4db4ad0541d7afc65cfd9afc432f9f054e1a2229` |
| B0 | `outputs/framelease_v4/envelopes/B0.json` | T_x0.00 | `9ef8479f04dab873d22b50e8732176804ed67f351f17584355b241e424fa1927` |

* The files are byte-deterministic (a re-export gives the same sha256) and listed with every input hash in
  `outputs/framelease_v4/envelopes/manifest.json`.
* Verification: the v3 runtime lease with each exported file recomputes all 6421 recorded frames of the offline stage
  (37 clips, 19263 comparisons) and reproduces the offline tau* and H = clip(tau* - T_c, 0, H_bar) within 5e-6 s; the
  largest difference was 0 s (`framelease_v4/offline/tests/test_export_envelopes.py`).
* Every shield-arm job passes `--envelope` explicitly and pins the file's sha256; the launcher freezes a copy into every
  run and the agent refuses a changed file (v3 `make_v3_policy`).

**Why these candidates and not others (RND Secs. 3.1-3.10).**

| family | status | reason |
|---|---|---|
| isotropic E0 envelopes | kept | anisotropic and motion-conditioned envelopes did not beat them (3.1) |
| risk levels 5% and 10% | kept | the literature's ε = 0.05 and the top of its 0.02-0.10 range (2.6, 3.2) |
| B0 | kept | the availability end of the frontier (3.1, 3.2) |
| RA | offline sensitivity only | a definition change, not a lease (3.3; 6.2, item 5); see above |
| renewal | excluded | needs a perception pass that profiling found infeasible on one GPU (3.3, 3.4) |
| Kalman tracking | excluded | no gain (3.6) |
| memory certificates | excluded | need per-frame detections the runtime does not produce; at most about +5 points at R_cond 5-8% (3.10) |
| perception-quality cells | excluded | UniDriveVLA does not have that perception (3.7, 3.9) |

**Risk disclosure and the `fl_risk` sensitivity.** DS may select a point that is not risk-constrained (B0). The
realized risk of the selected point is reported in every case:
* offline nested R_cond, in Table II-A;
* closed-loop EIR and R_cond, in Table I.

If L* is B0, Proposition 1 holds only under a zero-error assumption, and the paper states this. In that case (FULL
only) the sensitivity arm `fl_risk` runs on E in Phase 6 (22 runs, tier 6), with d*. Its lease point is the better of
E5 and E10 by mean DS on T22a, the stage every candidate ran; ties go to the earlier candidate. If neither remains
after pruning, `fl_risk` is not run.

### 4.4 Heuristic grid (FrameLease + Heuristic; inherited by Age-Only)

**The utility.** a_det^{d}(s) = REFINE if depth(s) < d, else REFRESH. It is consulted only when |A_feas| = 2. When only
one action is feasible the shield decides (Eq. 8).
* d = 10 is the v3 heuristic: refine while feasible, i.e. fill the lease slack. Its utility name is `heuristic`.
* d < 10 is the utility `v4_adet_d<d>` (`framelease_v4/rl/behaviour.py` `DepthHeuristicUtility`), passed as
  `--policy-params '{"utility": "v4_adet_d<d>"}'` and registered in the launcher and in the agent process. The shield's
  depth limit stays 10 (Sec. 2.4).
* d = 1 refreshes at every choice.

**Grid.** d in {10, 4, 1}, in that order, at the selected lease point L*.
* Stage 1: d = 4 and d = 1 run on T22a. The d = 10 runs at L* are reused from the lease grid, where L* ran on T22a
  and T22b.
* The top two of the three survive.
* Stage 2: survivors without T22b runs run on T22b.
* Selection by mean DS over T22.

### 4.5 Age-Only grid

* A in {1.0, 1.5, 2.0, 2.5} s, in that order.
* The cap is H_bar = 2.5 s. The fast-prefix continuity need of 0.96 s is the smallest A that can avoid gaps.
* Utility a_det^{d*}.
* SH with 4 candidates, 2 survivors.
* Job parameters: `{"age_lease_s": A, "utility": <a_det^{d*} name>}`.

### 4.6 Event-Triggered grid

**Thresholds.**
* theta_v2 = (Δv 1.0 m/s, Δψ 0.10 rad, shift 2.0 m), the v2 defaults.
* theta_s = (0.5 m/s, 0.05 rad, 1.0 m), twice as sensitive.

**Heartbeat.** A_hb in {2.0, 1.0} s.

**Fixed.** Radius 30 m, score threshold 0.3, command events on, refresh reservation on, `max_age_s` 3.0 s.

**Grid order.** (theta_v2, 2.0), (theta_v2, 1.0), (theta_s, 2.0), (theta_s, 1.0). SH with 4 candidates, 2 survivors.
Job parameters: `{"speed_delta_mps", "yaw_delta_rad", "det_shift_m", "heartbeat_s"}`; candidate names
`v2_hb2.0`, `v2_hb1.0`, `s_hb2.0`, `s_hb1.0`.

### 4.7 RL hyperparameter grids (equal budget per family)

**Grid per family.** Each family gets 12 candidates (`framelease_v4/rl/trainers.py` `grid()`):
* `min_samples_leaf` in {10, 40};
* pessimism beta in {0, 1};
* plus one family-specific axis:
  * `fqi` and `fqi_nolease`: horizon K in {8, 32, 128} SMDP steps;
  * `bandit`: target window in {`step` (to the next choice epoch), 1 s, 2 s}.

**Fixed.**
* ExtraTrees with 100 trees per action head, `max_features` 1.0, seed 0;
* `min_support` 30 logged samples per head;
* deviation margin 0.

**Deployed network.** A ReLU MLP 16 -> 32 -> 32 -> 2 (10 inputs for `fqi_nolease`), distilled from the selected forest
(`trainers.distill`, agreement target 0.98).

The selection rule is in Sec. 5.6.

### 4.8 Training-route references and decision point D1

**References.** Fixed Deep and Fast Only run on T22 (44 runs, untuned, Table I settings; block `ref`). They put the
tuned arms' training DS in context. TRIMMED has no reference block (Sec. 14).

**Decision point D1.** After Phase 1 a training-route summary goes to the user, written by
`framelease_v4/protocol/d1_summary.py --variant FULL --queue outputs/framelease_v4/queue_p1 --write` to
`outputs/framelease_v4/tuning/d1/FULL_d1_summary.{json,md}`:
* every candidate of every grid and the two references, per block, with the outcome counts, the dropped routes, the
  set-up failure flags and the stage selections;
* the selection statistic (mean DS over the kept routes), and over each candidate's valid runs: DS, RC, SR, fallback
  ratio, DMR and EIR (means over routes), closed-loop R_cond (pooled misses / conflict plans) and P_both (pooled over
  shield decision epochs), recomputed from the run logs by `framelease_v4/arms/metrics_v4.py`.

D1 uses training routes only. Continuing or stopping is the user's decision.
* If the work continues, nothing registered here changes.
* If it stops, the protocol and the training-route results are reported as they are.

### 4.9 Tuning freeze

`outputs/framelease_v4/tuning/selection.json` (`select_stage.py --variant <V> --freeze --write`) records:
* the variant (FULL or TRIMMED);
* L* (envelope file and sha256, validity definition std), d* (and its utility name), A*, theta* and A_hb*;
* the arm parameters derived from them, and the `fl_risk` lease point (FULL, if L* = B0);
* every stage selection with its sha256, and every stage table;
* the sha256 of `select_stage.py` and `p1_jobs.py`.

The file is written, and its hash entered in Sec. 13, before Phase 2 starts.

## 5. Offline RL for the utility selector (outline Sec. III-B, Eqs. 6-8)

### 5.1 Decision epochs and the semi-Markov process

**Epochs.**
* **Decision epochs** are the refinement-quantum boundaries of the running job (depth >= 1, including the
  at-max-depth boundary) at which the shield is evaluated.
* **Choice epochs** are the decision epochs with |A_feas| = 2. Only there does Eq. 8 consult the utility.
* **Forced epochs** are all the others: one feasible action, or none, which means FALLBACK plus a recovery refresh. They
  are part of the environment.

**Transitions.** A transition runs from one choice epoch to the next. Durations are unequal because quanta, refreshes
and queueing differ, so the process is semi-Markov (outline III-B, paragraph 1). An episode is one route run.

### 5.2 State, action and reward

**State.** 16 scalars (`framelease_v4/rl/features.py`), read from the v3 decision row by name, with fixed values for
missing entries and fixed clipping ranges.

| group | features |
|---|---|
| lease-derived (6) | `lease_slack_s` (s_lease = D* - t), `cand_slack_s`, `refine_margin_s`, `refresh_margin_s`, `min_g_m`, `tau_star_s` |
| other (10) | `obs_age_s`, `depth`, `plan_delta_m`, `active_age_s`, `newer_frames`, `L_refine_s`, `L_refresh_s`, `kappa`, `ego_speed_mps`, `n_relevant` |

These cover the outline's key features:
* lease slack;
* observation age;
* refinement progress (depth, plan change);
* GPU budget (kappa);
* runtime latency (L_refine, L_refresh).

**Actions.** REFINE and REFRESH. FALLBACK is a control mode, not an RL action (Eq. 8).

**Reward (Eq. 7).**
* r_i = S(t_{c,i+1}) - S(t_{c,i}), where S(t) = RC(t) x P(t) is the prefix driving score. It is reconstructed from the
  logged ego positions and the official infraction messages (`framelease_v4/rl/prefix_score.py`), with S(T) = the
  official DS.
* The last transition gets DS - S(t_{c,last}).
* Rewards are undiscounted. The pre-choice return plus the sum of rewards equals the official DS; this identity is
  checked for every episode.
* If an episode's reconstruction is impossible (missing logs), its reward is terminal-only, as the outline allows, and
  the episode is flagged.

### 5.3 Behaviour policy and data (Phase 2)

**Arm.** `fl_behaviour`: the `fl_heuristic` configuration at L*, maximum depth 10, with the behaviour utility
`v4_eps0.300_seed<s>[_d<d*>]` (seed rule of Sec. 2.6). It is an arm of the v4 launcher
`framelease_v4/arms/run_closed_loop_v4.py`, so the RL data run on `V4Runtime` with the fast prefix and the actor-box
log like every other arm; the run list is `framelease_v4/rl/collection_plan.py` (output
`outputs/framelease_v4/rl_data/k<kappa>/`). `framelease_v4/rl/run_closed_loop_rl.py` (v3 runtime) is a development tool
and is not used for protocol runs.

**Behaviour rule.** At a choice epoch it returns a_det^{d*}(s) with probability 0.7. Otherwise it draws uniformly from
A_feas, so a deviation happens with probability 0.15. The utility only ever chooses inside A_feas.

**Logged per choice.** The propensity mu(a|s) and the exploration flag (`v4_mu`, `v4_explore`, `v4_base_action`,
`v4_draw`).

**Runs.** 44 training routes x kappa {1.0, 1.5, 2.0} x seed 11 = 132 episodes (TRIMMED: Sec. 14). The RL dataset is
exactly these episodes; Phase-1 tuning runs and the P1-0 smoke runs are not used for RL. Test-route episodes are refused
by the dataset builder.

### 5.4 Trainers (families of Table II-A)

**`fqi`: finite-horizon, undiscounted fitted Q-iteration on the 16 features.**
* Q_0 = 0.
* Q_k(s, a) <- R + (1 - done) max_{a' in A_feas(s')} Q~_{k-1}(s', a') for k = 1..K. Every s' is a choice state.
* Terminal transitions carry no bootstrap term.
* One ExtraTrees forest per action, refit every iteration (Ernst et al. 2005).

**`bandit`: contextual bandit.** One-step targets: R up to the next choice epoch, or the fixed-window gain S(t + W) -
S(t).

**`fqi_nolease`.** `fqi` on the 10 features that are not lease-derived. The shield is unchanged.

**Action coverage and out-of-distribution actions** (outline: "offline data coverage and OOD action values").
* An action head is fitted only with >= `min_support` samples.
* The learned policy deviates from a_det^{d*} only where both heads are supported.
* The deviating action's value is lowered by beta x the per-tree standard deviation (pessimism).

### 5.5 Off-policy evaluation

**Estimator, as implemented** (`framelease_v4/rl/ope.py` `select` and `fqe` with the default `FQEConfig`;
`framelease_v4/rl/RL_PROTOCOL.md` Secs. 6 and 8). Route-grouped 5-fold cross-fitted fitted-Q evaluation (FQE):
* Folds: 5 route-grouped folds over the training episodes (seed 20261110); every training episode is held out exactly
  once.
* Target: undiscounted, on the choice-epoch process, with lambda = 1 returns cut at the first disagreement (Watkins):
  Y_i = R_i if the episode ends; Y_i = R_i + Y_{i+1} if the next logged action equals pi(s'); otherwise
  Y_i = R_i + Q_{k-1}(s', pi(s')). No importance weights are needed, because a segment is followed only while the
  logged actions are pi's. Plain one-step FQE (`trace='one_step'`) is available but not used.
* Iterations: k = 1 .. min(B + 1, 600), B = the largest number of bootstrap points along a held-out episode (every
  terminal reward reaches the first state); a run that hits the cap is flagged `converged = false`.
* Value model: one ExtraTrees forest per action, 50 trees, `min_samples_leaf` 10, `max_features` 1.0, `min_support` 5
  samples per head. Its inputs are the 16 state features plus three evaluation-only covariates (route completion so
  far, penalty so far, elapsed time; from the hero state, never a policy input). It is the same model for every
  candidate, whatever features the candidate uses.
* Value of an episode: V_e(pi) = pre_choice_e + Q(s_e,first, pi(s_e,first)). A candidate that needs an action head the
  held-out data cannot fit is unsupported and cannot be selected; so is a candidate in a fold whose training data
  cannot fit it (Amendment A6).

**Selection statistic.** For a candidate pi, the mean over held-out episodes of Δ_e = V_e(pi) - V_e(a_det^{d*}).

**Uncertainty.** Route-cluster bootstrap, 2000 resamples, 90% interval.

**Calibration** (reported, not used for selection): FQE of the logged behaviour policy against its own Monte Carlo DS on
the held-out episodes.

**Diagnostics only** (not used for selection):
* weighted per-decision importance sampling (WPDIS) and weighted doubly robust (WDR) estimates with the logged
  propensities, and their effective sample sizes;
* the deviation rate of pi;
* the agreement of pi with the logged actions.

### 5.6 Model selection rule (fixed in advance)

Within each family:
1. The candidate with the largest cross-fitted mean Δ is selected.
2. Ties within 1e-6 go to the simplest candidate: shorter horizon or window, then larger leaf, then smaller beta.
3. A candidate whose held-out evaluation is unsupported cannot be selected.
4. Each family's selected candidate is deployed whatever the sign of its estimate. The estimate and its CI are reported.
5. The selected candidate is refit on all episodes of the RL dataset (FULL: 132; TRIMMED: 44, Sec. 14) and distilled
   into the deployed MLP. The distillation agreement is reported.

The FQI family's network becomes `fl_full`. The bandit and `fqi_nolease` networks become `fl_bandit` and
`fl_fqi_nolease`.

### 5.7 Deployment: budgeted CPU policy execution (outline III-C, paragraph 3)

`framelease_v4/rl/qnet.py` `QUtility`:
* **Network.** Fixed float64 weights in C-contiguous, read-only arrays. Buffers are preallocated, so a call allocates
  nothing.
* **When it is called.** Only when |A_feas| = 2.
* **Bypass to a_det^{d*}.** In three cases:
  * the shield margin of either action is below the policy budget B_pi = 100 µs;
  * the network has been disabled: at an overrunning call, once at least 64 network calls were made in the run, the
    network is disabled for the rest of the run if more than 5% of the last min(n, 256) calls overran B_pi (n = the
    network calls so far, this one included; Amendment A5);
  * this call overran B_pi, in which case its result is discarded.
* **Output.** The answer is always in A_feas. The commit check of Eq. 9 is unchanged.
* **Logged.** `v4_q_refine`, `v4_q_refresh`, `v4_qnet_s` (network wall time) and `v4_bypass`.

### 5.8 P_both rule

P_both = Pr(|A_feas| = 2) over decision epochs (outline IV-B, paragraph 2).

If P_both < 0.05 in the kappa-1.0 episodes of the RL dataset:
* the RL contribution is labelled "not testable at this operating point";
* the RL arms still run;
* H2 is still computed and reported, with that label.

P_both is reported for every shield arm in every table.

### 5.9 RL freeze (before any test-route run)

The freeze records:
* the dataset manifest: episode list, and the sha256 of every source log;
* the three selection reports;
* the three deployed networks, with their sha256 and names `v4_qnet_<sha12>`;
* the sha256 of every `framelease_v4/rl` source.

All of this is entered in Sec. 13 as part of the test freeze.

## 6. Metrics (per route and arm; the route is the unit)

### 6.1 Driving outcomes

These come from the official record.
* **DS.** `score_composed`, 0-100: route completion x infraction penalty. This is the primary metric.
* **RC** (`score_route`) and **IP** (`score_penalty`).
* **Success** (Bench2Drive definition, `third_party/bench2drive-linux/tools/statistic_route_json.py` `is_success`): the
  status is `Completed` or `Perfect`, and no infraction list other than `min_speed_infractions` is non-empty.
  SR is the share of successful routes.
* **Collisions per km.** Pedestrian + vehicle + layout collisions divided by km driven.
  * km driven = route length x RC / 100, with a floor of 0.001 km (leaderboard definition).
  * Route-level values are used for paired contrasts (v2 definition).
  * The arm-level value is pooled (sum of collisions / sum of km), with a route-cluster bootstrap CI.
* **Infractions per km.** All penalized infraction events per km driven:
  * counted: collisions, red light, stop, outside-route-lanes events, scenario timeout, yield to emergency vehicle;
  * excluded: min-speed records, which Bench2Drive appends at every 5% of progress with no penalty;
  * the route-ending events (deviation, blocked, route timeout) are reported separately.

### 6.2 Compute and timing

These come from the `V4Runtime` summary and are recomputed from the logs by the v4 aggregator.
* **GPU usage.** GPU-busy simulated seconds per simulated second. "Busy" means the cost-model intervals of prefixes and
  flow steps within the run. CUDA-seconds per second (GPU usage / kappa) is also reported.
* **Deadline miss rate (DMR).** Ticks from the first commit on at which no committed action is valid (expired, invalid
  or none), divided by those ticks. "Valid" follows the arm's own validity rule:
  * the lease deadline, for the shield arms and Original FrameLease;
  * observation age < `max_age_s`, for the others.

  The all-ticks variant and expired-only ticks are also reported.
* **Fallback ratio.** The share of all control ticks with the full-brake fallback applied, before the first plan
  included. Fallback episodes (entries into fallback) are also counted.
* **Action age p50 / p95.** Per route, over tracked ticks: now minus the capture time of the observation behind the
  applied plan. The arm-level value is the mean over routes.

### 6.3 Validity outcomes (actor-box log; `framelease_v4/arms/realized.py`)

**Realized validity of a committed plan.**
* V is the first τ in [0, T_pred] at which the ego footprint along the plan, placed with the true capture pose, comes
  within d_safe of a real logged vehicle or walker box at the absolute time t_k + τ.
* V_suf = clip(V - T_c, 0, H_bar).
* A conflict means V is uncensored. Plans with V = 0 are reported separately.

**Validity metrics.**
* **Executed-invalid tick rate (EIR).** Tracked ticks whose applied plan, at age Δ, has a conflict with Δ >= V_suf,
  divided by tracked ticks. This is the common safety yardstick for all arms.
* **Closed-loop R_cond.** Committed conflict plans with H > V_suf, divided by committed conflict plans. H is the
  validity the arm actually used: lease, or age cap.
* **Closed-loop lease utilization** (shield arms). Mean over committed plans with V_suf > 0 of min(H, V_suf) / V_suf.
* **Premature expiry** (shield arms). Committed plans whose deadline passed before their successor's commit while
  V_suf still covered that time.

EIR and R_cond use the standard validity definition (Eqs. 1-3). The RA rule appears only in the offline sensitivity of
Table II-A (Sec. 4.3).

### 6.4 Scheduler outcomes

These apply to shield arms.
* P_both;
* lease p50 of committed candidates;
* deviation rate of the utility from a_det^{d*};
* policy bypass rate;
* budget overruns: the actual commit later than the shield's predicted bound;
* shield violations: an expiry that the last admitted decision promised to avoid;
* commit-gate rejects, by reason.

## 7. Experiments mapped to the outline

### 7.1 Fig. 1: freshness-depth trade-off from real data (Sec. II)

**Panel (a): offline, existing data, no new run.** Data: `framelease_v4/offline/fig1_data.py`, read-only from v2
outputs, written to `outputs/framelease_v4/offline_ablation/fig1/`.
* Execution error (m) against observation age for depths 1, 5 and 10. C1 sweep, W = 1 s, 15 held-out clips, Student-t
  intervals over clips.
* Markers at the release ages:
  * unmodified prefix: depth 1 at 0.896 s, depth 10 at 1.027 s;
  * fast prefix: depth 1 at 0.457 s, depth 10 at about 0.59 s (0.457 + 9 x 0.0146 s).
* The Fast@Fresh - Deep@Old contrast against kappa (`c1_fresh_vs_deep_kappa.csv`).

**Panel (b): closed loop.** The paired DS difference Fixed Deep - Fast Only:
* per scenario type, and per Bench2Drive ability (Overtaking, Merging, Emergency_Brake, Give_Way, Traffic_Signs; the
  official multi-label mapping of `tools/ability_benchmark.py`);
* at kappa 1.0 from the Table I runs (fast prefix, 44 routes);
* at kappa 1.5 and 2.0 from the Fig. 3 runs (E).

The v2 matrix (unmodified prefix; kappa 1.0 and 1.5 on 44 routes, kappa 2.0 on 11) is drawn alongside and labelled as
the earlier measurement.

**What the figure shows.** Where Deep@Old beats Fast@Fresh and where it does not, drawn from the data whatever they
show. The outline's illustrative curve is not used. The panels are descriptive and carry no test.

### 7.2 Table I: end-to-end performance under matched compute (Sec. IV-A)

**Design.** 7 arms x 44 test routes, kappa 1.0, seed 11, fast prefix: 308 runs.

**Setup paragraph contents.** Benchmark and split (Sec. 3), model and refinement (Sec. 2.1), hardware (Sec. 2.1),
runtime (control at 20 Hz, kappa, quanta; Sec. 2.3), and evaluation (44 routes, 1 seed, SR and DS).

**Columns.**
* DS: mean and 95% CI;
* SR;
* collisions/km and infractions/km;
* GPU usage;
* DMR;
* action age p50 / p95;
* fallback ratio;
* EIR (standard yardstick);
* P_both.

RC and closed-loop R_cond go to the table notes or the text.

**Contrasts.** As in Sec. 9.

### 7.3 Fig. 3: driving score versus action age under constrained GPU budgets (Sec. IV-A)

**Design.**
* Arms: Fixed Deep, Fast Only, FrameLease + Heuristic and Full FrameLease.
* kappa in {1.0, 1.5, 2.0}, i.e. GPU share 100%, 67% and 50%.
* Subset E (22 routes).
* The kappa-1.0 points are the Table I runs restricted to E.
* New runs: 4 x 2 x 22 = 176.
* Tuned parameters are not re-tuned per kappa. The Q-network receives kappa as a feature.

**Plot.**
* x: mean over routes of the per-route action-age p50, with p95 in a second panel.
* y: mean DS.
* 95% route-bootstrap CIs on both axes.
* One line per method through its three budgets.

**Annotation of every point.** EIR and GPU usage. FrameLease does not minimize action age, so lower age must not be
read as better without the validity and budget columns (outline IV-A, paragraph 3).

### 7.4 Table II-A, lease panel (Age-Only vs Global-Margin vs Suffix-Aligned; C1)

#### Offline

**Data and status.** 32 VAL clips, 5417 depth-1 plans. Code in `framelease_v4/offline`, outputs in
`outputs/framelease_v4/offline_ablation`. The analysis was already run before registration (Sec. 11).

**Designs.**
* `AGE`: H = T_age.
* `GLOBAL`: v2 global margin, cap 2.5 s; the v2 2.0 s cap is a sensitivity analysis.
* `SUFFIX`: Eqs. 1-3.

All three share the TRAIN-fitted envelope candidates. LOCO-36 envelopes are a sensitivity analysis.

**RA sensitivity (definition change; cited, not recomputed).** The v4 offline code does not implement the RA rule
(Sec. 4.3), and no new RA computation is registered. Table II-A cites the earlier renewal study instead (RND Sec. 3.3,
Table 3: 15 VAL clips, model detections, nested selection at R_cond <= 5%, unmodified-prefix need 1.842 s). With
renewal on a shared GPU and the perception pass aligned with the release:
* RA validity: continuity 57.8% [38.7, 75.4] at realized R_cond 10.1% [0.8, 27.5];
* standard validity, same setting: 48.5% [26.0, 69.7] at 9.6% [0.8, 27.1];
* with oracle boxes: RA 73.3% [56.5, 87.5] at 4.9% [0.0, 15.8]; standard 80.8% [62.9, 93.0] at 5.1% [0.0, 16.0].

These numbers come from another setting (lease renewal, 15 clips, the unmodified prefix) and another validity
definition. They are labelled as such, are not compared statistically with the v4 rows, and are never presented as
standard-validity safety evidence (RND Sec. 3.3, caveats).

**Metrics.**
* validity violation rate: R_cond (primary) and R_marg;
* lease utilization;
* premature refresh rate: H < need <= V_suf, conditional on V_suf >= need;
* continuity at the fast-prefix need 0.964 s (and at 1.842 s);
* Proposition 1 reporting for the deployed E*: per-τ and whole-path envelope coverage for vehicles and pedestrians on
  the 32 VAL clips.

**Protocols.**
* Primary: nested leave-one-clip-out over the 32 VAL clips with rule (a) at R_cond <= 5%.
* Secondary: the same at 10%, and TRAIN-only selection.
* Descriptive: the in-sample frontier.
* Subsets: all plans (primary), and without the static V = 0 plans.
* CIs: clip bootstrap, 2000 resamples, seed 20261109.

**Primary offline contrast (H4 offline).** SUFFIX - GLOBAL continuity at need 0.964 s under nested selection at
R_cond <= 5%, paired by clip, together with the paired difference in realized R_cond.

#### Closed loop

**Design.** Subset E, kappa 1.0, seed 11. Three leases with the same shield and the same utility a_det^{d*}:
* Age-Only lease: the `age_only` Table I runs on E;
* Global-Margin lease: `fl_global_shield`, 22 new runs;
* Suffix-Aligned lease: the `fl_heuristic` Table I runs on E.

**Metrics.** DS, fallback ratio, DMR, closed-loop utilization, premature expiry, EIR and closed-loop R_cond.

### 7.5 Table II-A, RL panel (C2) and P_both

**Arms.**
* Heuristic: `fl_heuristic`.
* Contextual Bandit: `fl_bandit`.
* FQI: `fl_full`.
* FQI without lease features: `fl_fqi_nolease`.

**Routes.** All four run on subset E (44 new runs for the bandit and `fqi_nolease`). Heuristic and FQI are also
compared on all 44 routes through Table I.

**Columns.**
* DS;
* P_both;
* deviation rate from a_det^{d*};
* bypass rate;
* Q-network p50 / p99;
* the FQE estimate and CI of each family's selected candidate (offline).

**Breakdown of the RL gain** (Full FrameLease - FrameLease + Heuristic; descriptive; outline IV-B, paragraph 2):
* by Bench2Drive ability (44 routes);
* by GPU budget (kappa 1.0, 1.5, 2.0 on E);
* by seed (seed 11 vs seed 12 on R).

### 7.6 Table II-B: runtime overhead and stress tests (C3)

**Panel B, from the logs.** Sources: the kappa-1.0 Table I runs of every shield arm, plus the kappa-2.0 Fig. 3 runs as
GPU contention.
* CPU Q-network inference p50 / p99, and the bypass count and rate.
* Shield + lease computation p50 / p99 (`decision_wall_s`, `lease_wall_s`).
* GPU quantum blocking, i.e. the non-preemptible quanta: charged prefix and flow-step durations, p50 / p99.
* Switching latency: the boundary CPU time charged between a REFRESH decision and the next job's start, p50 / p99.
* Cancelled GPU work: the share of GPU-busy time spent on candidates that were never committed.
* Versioned-commit overhead: release-to-commit validation time, p50 / p99; rejects by reason.
* DMR, fallback episodes, shield violations and budget overruns.

**Stress tests.** CPU only, `framelease_v4` bench; run on synthetic states before the test freeze (P3) and in Phase 7 on
recorded states.
* **S1, CPU contention.** The Q-network call, shield + decision, lease and commit check on recorded decision states from
  training runs. Load: 0, 4, 8 and 15 background busy processes on the 16-core machine. Report p50, p99 and max, and the
  overrun rate against B_pi.
* **S2, near deadline.** Recorded states with D* moved so that the slack spans [-0.1, 0.6] s in 10 ms steps. Report:
  * the share of admitted actions;
  * the number of admitted actions whose bound >= D* (must be 0);
  * the Q-network bypass rate;
  * per kappa, the Eq. 5 slack floors of the states (min, p50, max), the grid values at or below every state's floor,
    the first admitting grid value and the admitted actions checked (Amendment A7).

  Supplementary (Amendment A7): the same sweep with D* = t + f(state) + delta, f the state's first-admissible slack,
  delta in [-0.1, 0.6] s in 10 ms steps; reported as supplementary, never in place of the registered grid.
* **S3, cancellation and regression.** At least 1e5 random event sequences against the commit gate: late completions of
  cancelled jobs, older observations completing after a newer commit, expired candidates, duplicate releases. Count
  commits that violate Eq. 9 (must be 0).
* **S4, GPU contention.** The kappa-2.0 closed-loop runs: DMR, budget overruns and shield violations, compared with
  kappa 1.0.

**Commit audit (all runs).** Every commit record in `jobs.jsonl` is re-checked against Eq. 9:
* t_commit < D;
* M(t_commit - t_k) > delta, for shield arms;
* the version is admissible relative to the previous commit;
* the candidate was not cancelled.

## 8. Execution

### 8.1 Phases and freezes

| phase | resource | content | ends with |
|---|---|---|---|
| P0 | CPU | implementation (Sec. 4.1, items present), tests, envelope export, dry-run job files, smoke checker, launch wrapper and disk watchdog | registration (Sec. 13.1) |
| P1-0 | GPU | smoke block: 7 runs on training route 18305 (outside T22): `fixed_deep`, `fast_only`, `age_only` (A 2.0 s, utility `v4_adet_d4`), `event_triggered` (theta_v2, 2.0 s), `fl_original`, `fl_heuristic` at E5 (utility `heuristic`), `fl_behaviour` at E5 | smoke check (below); never used for selection or RL |
| P1 | GPU | tuning and references on training routes (Secs. 4.2-4.8), stage by stage | tuning freeze (Sec. 4.9); decision point D1 |
| P2 | GPU | offline-RL data: `fl_behaviour` on 44 training routes x 3 kappa (Sec. 5.3) | data manifest |
| P3 | CPU | RL training, FQE selection, distillation (Secs. 5.4-5.6); stress tests S1-S3 on synthetic states (Sec. 7.6); job files of P4-P6 generated, validated and pinned | test freeze |
| P4 | GPU | Table I (tier 3) | |
| P5 | GPU | Fig. 3 (tier 4) | |
| P6 | GPU | Table II-A closed loop (tier 5); seed-12 replicates and the conditional `fl_risk` (tier 6) | |
| P7 | CPU | aggregation, analysis freeze, confirmatory analysis, stress tests on recorded states, independent verification | report |

**Gating.**
* P1 starts only after the P1-0 smoke check passes. The check is mechanical:
  `framelease_v4/protocol/check_smoke.py --queue outputs/framelease_v4/queue_p1 --write`, registered before any smoke
  run existed (Sec. 12.2). Per smoke job it checks the final run (the runner's final record, or the first valid run;
  attempts the runner did not count are ignored), with these criteria:

  | criterion | passes when |
  |---|---|
  | `route_record` | `metrics/result.json` holds >= 1 official route record whose status is not an execution failure (a driving failure such as `Failed - Agent got blocked` passes); `raw/official_results.json` exists; the launcher did not time out and ran <= 1410 s |
  | `config` | `config.json` is the job's configuration (arm, route, kappa, seed, policy parameters, envelope sha256, the three fast-prefix options); every pinned file the run recorded (manifest identity, frozen source hashes) has the job's sha256, and every pinned `framelease_v4` file is recorded |
  | `summary_v4` | `raw/agent/framelease/summary.json` has the `v4` block (`V4Runtime`), >= 1 tick, and the `fast_prefix` and `actor_log` blocks |
  | `fast_prefix` | `fast_prefix.json`: `stage: final`, validation passed, `sdpa`, `gpu_preproc` and `lora_merged` active, > 0 SDPA calls; the launcher reported no fast-prefix problem |
  | `decisions` | `decisions.jsonl` is complete: every line parses, the epochs are exactly 1..N with N >= 1 and N equal to the summary's decision count, and every row carries the 32 v3 state features |
  | `utility` | age and shield arms: the agent's policy reports the configured utility (registered in the agent process), and every choice epoch has reason `both_feasible:<utility>` and that utility's action (`heuristic`: REFINE; `v4_adet_d<d>`: REFINE iff depth < d). `fl_behaviour`: every choice epoch logs `v4_mu` = (1 - eps) 1[a = base] + eps / 2, `v4_explore`, `v4_base_action` = a_det^d(depth) and `v4_draw` = 0, 1, 2, ...; without any choice epoch this item is deferred to the first P2 run (P1 runs no behaviour utility). Other arms: no utility block |
  | `actor_log` | `actors.jsonl.gz` decodes completely (no truncated gzip member); `actor_log.json`: enabled, 0 errors, size equal to the file size and <= 2,100,000 B (the 2,000,000 B budget + 5% for the ego-only tail after full decimation), logged ticks equal to the decoded tick rows and >= 1 |
  | `ego_found` | the log header names the hero (an id and a vehicle type) and every tick row carries the hero state |
  | `pose_offset` | estimated LiDAR pose (the agent's GNSS + compass `lidar2global`) against the true one (hero transform + official lidar2ego), with the true position first mapped into the official agent's own GNSS frame (amendment A1: `framelease_v4/arms/agent_frame.py` reproduces the official `init()` fsolve on the route's first waypoint, the official `gps_to_location` and the map's OpenDRIVE geoReference; the raw world-frame offset is reported, not judged), on the >= 50% of logged ticks that carry an estimate: planar offset p50 in [0.9, 1.9] m (the GNSS sits 1.4 m behind the vehicle origin; leaderboard GNSS noise is about 0.5 m), p95 <= 3.0 m, yaw difference p50 <= 5 degrees |
  | `tick_wall` | the agent's mean per-tick wall time (`ticks.jsonl` `wall_s`) plus the actor logger's per-tick p99 <= 0.20 s, and the logger's p99 <= 0.05 s (one simulated tick). With the pilot's 90 s of set-up and 0.12 s of evaluator time per tick, a 4000-tick (TickRuntime-limited) route then takes <= 90 + 4000 x 0.32 = 1370 s, below the launcher's 1410 s |
  | `run_size` | the run directory is <= 20 MB (twice the planning figure of Sec. 8.5) |

  Verdict: PASS when every criterion of every run passes (deferred items are allowed and listed); FAIL when any
  criterion of any run fails; INCOMPLETE while a job has no final outcome. After a FAIL the cause is fixed and the
  smoke block is run again; a fix that changes a pinned file or a criterion is an amendment (Sec. 13.2), and the job
  file is regenerated. The path and sha256 of every smoke report are entered in Sec. 13.2, and P1 starts only after a
  PASS. The smoke runs are infrastructure checks: their DS is not used for any selection or for RL.
* No test-route run starts before the test freeze.
* The test freeze records, in Sec. 13: `selection.json`, the RL freeze (Sec. 5.9), and the job files with their
  sha256 and pins.
* Phase-1 stages run in dependency order (block names of `framelease_v4/protocol/p1_jobs.py`):
  1. `ref`, `lease_s1` and `event_s1` (no dependency);
  2. `lease_s2` and `event_s2`;
  3. `heur_s1` (needs L*), then `heur_s2`;
  4. `age_s1` (needs d*), then `age_s2`.
  TRIMMED (Sec. 14): `lease_s1` and `event_s1`; then `heur_s1`; then `age_s1`.
* After each stage the selection script runs before the next job file is generated.

### 8.2 Job files and runner

**Runner.** `framelease_v2/gpu_queue.py`, unchanged:
* one job at a time on the shared GPU lock;
* no foreign GPU compute process above 1 GiB, and at least 18.5 GiB of free GPU memory;
* `--min-free-gib 6`, plus a disk watchdog that places `STOP` in the queue directory below 5 GiB free
  (`framelease_v4/protocol/disk_watchdog.sh`, Sec. 8.5);
* `--exit-when-empty`: the runner exits when no job of its queue is pending;
* resumable, with `STOP` / `PAUSE` files.

**Launch.** `bash framelease_v4/protocol/launch_queue.sh <queue_dir>` sources `linux/env.sh`, refuses to start while
`<queue_dir>/STOP` exists, while another runner holds the queue lock or without a job file in `<queue_dir>/jobs.d/`,
then starts, detached, the unchanged runner (`.conda-unidrive-linux/bin/python -I -B framelease_v2/gpu_queue.py
--queue-dir <queue_dir> --exit-when-empty --min-free-gib 6`, output appended to `<queue_dir>/runner.nohup.log`) and the
disk watchdog on the runner's pid (log `<queue_dir>/disk_watchdog.log`), and writes `<queue_dir>/launch_<UTC>.json`
(pids, commands, free disk, sha256 of the runner, the watchdog, the wrapper and every job file). `--dry-run` prints the
checks and commands and starts nothing. The exact command sequence of P1-0 and P1 is in
`outputs/framelease_v4/p1_jobs/README.md`.

**Job files and queue directories.** `framelease_v4/protocol/p1_jobs.py` writes the job files to
`outputs/framelease_v4/p1_jobs/<P1-0|FULL|TRIMMED>/b<NN>_<block>.jsonl`, with a stage spec (`.stage.json`; the smoke:
`.meta.json`) and the validation of every line (`.check.json`). That directory is not a queue: nothing there is run.
At launch the user checks each registered job file against the registration manifest (`sha256sum -c`), copies the files
of the registered variant, block by block, into `outputs/framelease_v4/queue_p1/jobs.d/` (P1-0 and P1 share this queue;
one file per block, processed in name order) and starts the runner with `launch_queue.sh`.

**Ordering.** Within a block, routes are shuffled with `random.Random(20261110 + block number)`, applied to the
id-sorted route list. All candidates or arms of a route run back to back, in an order rotated by one position per
route (counterbalanced). Block numbers: smoke 0, `ref` 1, `lease_s1` 2, `event_s1` 3, `lease_s2` 4, `event_s2` 5,
`heur_s1` 6, `heur_s2` 7, `age_s1` 8, `age_s2` 9 (TRIMMED uses the numbers of its stage-1 blocks).

**Job ids.** `v4<phase>_<arm>[_<config>]_k<kappa>_s<seed>_r<route>`, e.g. `v4p1_fl_heuristic_E5_d10_k1.0_s11_r1792`,
`v4p1_age_only_A1.5_d4_k1.0_s11_r1792`, `v4p1_event_triggered_v2_hb2.0_k1.0_s11_r1792`; smoke `v4p1smoke_...`.
A run that is identical in FULL and TRIMMED has the same id and output directory in both, so a TRIMMED block can be
extended to FULL without re-running it.

**Ports.** Line i uses CARLA port 2600 + 10 (i mod 4). Ports +1, +2 and +6000 (Traffic Manager) are also used. These
are disjoint from the v2 (2500-2530) and v3 (2700-2955) ranges.

**Wall cap.** 25 min per job. The launcher's `--timeout-s` is the cap minus 90 s; `--lock-wait-s` is 600.

**Command.** Every job runs one route under one arm through the v4 launcher
(`framelease_v4/arms/run_closed_loop_v4.py`):
* `[.conda-unidrive-linux/bin/python, -B, framelease_v4/arms/run_closed_loop_v4.py, --arm, ..., --fast-prefix
  sdpa,gpu_preproc,lora_merged, --kappa, --seed, --routes, --route-id, --port, --output-dir, --timeout-s 1410,
  --lock-wait-s 600, --envelope (shield arms), --policy-params]`;
* the fast prefix is always on and always explicit;
* arm parameters, envelope file, utility name and Q-network path are explicit arguments;
* the exact argument list of every job is materialized in its job file;
* all job files are validated before they are written: gpu_queue's job contract, the pins against the current tree,
  the launcher's own parsing, configuration build and preflight, and the exact command with `--dry-run` in a
  subprocess (which writes nothing), without starting CARLA.

### 8.3 Code pins

Every job carries `require_sha256` for (49 files, plus the envelope, the Q-network file and the extension sources where
they apply; Amendment A4):
* the 16 files pinned by the v2 matrix (including `linux/env.sh`, the routes XML and the v2 q95 lease file);
* `framelease_v2/__init__.py` and `framelease_v3/__init__.py`;
* the 8 other `framelease_v3/runtime` sources;
* the 11 `framelease_v3/fastprefix` files (sources and the upstream files the fast prefix patches);
* every `framelease_v4` source the agent imports: `framelease_v4/__init__.py`, the 7 `framelease_v4/arms` sources
  (`__init__`, `policies_v4`, `runtime_v4`, `arms_v4`, `actor_log`, `agent_v4`, `run_closed_loop_v4`) and the v4
  utility modules `framelease_v4/rl/{__init__,behaviour,features,qnet}.py`;
* the envelope file, for the arms with a lease (`fl_heuristic`, `fl_risk`, `fl_behaviour`, `fl_full`, `fl_bandit`,
  `fl_fqi_nolease`, `fl_global_shield`);
* the Q-network FILE, at the sha256 the RL freeze records, for `fl_full`, `fl_bandit` and `fl_fqi_nolease` (the network
  name pins neither B_pi nor the provenance);
* the five extension sources
  `framelease_v4/arms_ext/{__init__,global_shield,arms_ext,agent_ext,run_closed_loop_ext}.py`, for `fl_global_shield`
  (they are frozen into every run of the arm).

Pins per job line: 49 for `fixed_deep`, `fast_only`, `fl_original`, `age_only` and `event_triggered`; 50 for
`fl_heuristic`, `fl_risk` and `fl_behaviour`; 51 for `fl_full`, `fl_bandit` and `fl_fqi_nolease`; 55 for
`fl_global_shield`. Every P4-P6 common pin equals the pin of the registered P1 lines (`registration.job_pins`).

The runner blocks a job whose pinned files changed. Each run freezes its own sources. The full list and hashes are in
Sec. 12.2 (registration); files created at the tuning and test freezes go into Sec. 13.

### 8.4 Retry rule (infrastructure only)

The rule of `framelease_v2/PREREGISTRATION.md` Sec. 5 is unchanged.

**Retried once, with the identical command:** an attempt without a valid official route record. That means no record,
`Simulation crashed`, `Agent crashed`, `Agent's sensors were invalid`, `Agent couldn't be set up`, a launch error, or a
wall-cap timeout.

**Final, whatever the driving outcome:** a valid record. This includes `Failed - Agent got blocked`,
`Failed - TickRuntime` (the 200 s limit), `Failed - Agent deviated from the route` and `Failed - Agent timed out`.

### 8.5 Disk

**Expected size per run.** Pilot runs averaged 6.05 MB (2.2-12.1 MB). The actor-box log adds at most 2 MB. The
planning figure is 10 MB per run, about 10.5 GB in total for FULL and 5.8 GB for TRIMMED (Secs. 10, 14).

**Watchdog.** `framelease_v4/protocol/disk_watchdog.sh <queue_dir> <runner pid>` reads the free space of the project
file system every 30 s. Below 5 GiB it places `<queue_dir>/STOP` with the reason; the runner finishes the running job
and exits. The watchdog never deletes a file and never signals a process; it exits when the runner exits. `STOP` stays
until the user removes it after checking the disk, and `launch_queue.sh` refuses to start while it exists. The
runner's own `--min-free-gib 6` keeps it from starting a job below 6 GiB.

**Compaction.** Lossless compaction is allowed only if it is implemented, read transparently by every v4 reader, and
tested before registration: gzip of the per-tick logs of final, aggregated runs, and hardlinks for identical frozen
sources. Nothing outside `outputs/framelease_v4` is ever deleted. Files of other projects are never touched.

### 8.6 Output layout

As implemented for P0-P2:
* `outputs/framelease_v4/envelopes/` (E5, E10, B0 and the manifest);
* `outputs/framelease_v4/p1_jobs/<P1-0|FULL|TRIMMED>/` (job files, stage specs, validations; not a queue);
* `outputs/framelease_v4/registration/` (registration manifest and seal, Sec. 13.1);
* `outputs/framelease_v4/queue_p1/` (the runner's queue of P1-0 and P1: `jobs.d/`, `status.jsonl`, logs, launch records);
* `outputs/framelease_v4/smoke_p1_0/<arm>/runs/` (P1-0) and `outputs/framelease_v4/smoke_p1_0/smoke_check.json` (the
  smoke report);
* `outputs/framelease_v4/tuning/<block>/<arm>_<config>/runs/` (P1; e.g. `tuning/lease_s1/fl_heuristic_E5_d10/`,
  `tuning/ref/fixed_deep/`);
* `outputs/framelease_v4/tuning/selection/<variant>/<block>.json` (stage selections) and
  `outputs/framelease_v4/tuning/selection.json` (tuning freeze);
* `outputs/framelease_v4/tuning/d1/<variant>_d1_summary.{json,md}` (D1 summary);
* `outputs/framelease_v4/rl_data/k<kappa>/runs/` (P2; `framelease_v4/rl/collection_plan.py`).

As fixed for P2-P6 by Amendment A3:
* `outputs/framelease_v4/p2_jobs/FULL/b10_rl_data.{jsonl,stage.json,check.json}` (the P2 job file, its stage spec and
  its check; not a queue) and `outputs/framelease_v4/queue_p2/` (the runner's queue of P2);
* `outputs/framelease_v4/rl_freeze/` (the RL freeze, Sec. 5.9) and `outputs/framelease_v4/stress/` (the S1-S3 reports,
  Sec. 7.6);
* `outputs/framelease_v4/test_jobs/FULL/b<NN>_<block>.{jsonl,stage.json,check.json}` and `index.json` (the P4-P6 job
  files of tiers 3-6, blocks 11-16; not a queue) and `outputs/framelease_v4/test_freeze/` (the test freeze and its own
  sha256 manifest);
* `outputs/framelease_v4/queue_p4/` (the one runner's queue of P4-P6: the six job files in name order);
* `outputs/framelease_v4/matrix/<arm>/runs/`, `outputs/framelease_v4/fig3/<arm>_k<kappa>/runs/`,
  `outputs/framelease_v4/ablation/<arm>/runs/` and `outputs/framelease_v4/replicates/<arm>/runs/` (the P4-P6 runs;
  `<arm>` is the protocol arm).

The selection, RL-freeze and analysis outputs go to the directories named in Secs. 4.9, 5.9 and 9.12.

## 9. Statistical analysis plan

### 9.1 General

**Unit and pairing.** The route is the unit. A contrast A - B uses the per-route differences on routes where both arms
have a final valid record whose code matches the pins. The estimate is the mean paired difference.

**Test.** The exact two-sided sign-flip test of the mean paired difference:
* complete enumeration for n <= 22;
* for n = 44, the exact distribution by dynamic programming over differences rounded to the metric grid: 0.01 for DS,
  RC and collisions/km; 1e-4 for fractions; 1 ms for ages;
* a Monte Carlo cross-check with 200,000 sign vectors.

The functions are `sign_flip_test`, `bootstrap_ci`, `holm` and `label_directional` of
`framelease_v2/analyze_closed_loop.py` (sha256 `5478c9f9...cc84`), imported unchanged.

**Confidence intervals.** Percentile bootstrap over routes, 10,000 resamples, with a fresh
`numpy.random.default_rng(20261110)` for every contrast and metric. Intervals are 95% unless stated otherwise.

**Decision labels.** "Improves" if the mean difference is in the hypothesized direction with Holm-adjusted p < 0.05.
"Worse" if it is in the opposite direction with Holm-adjusted p < 0.05. Otherwise "inconclusive": no difference was
demonstrated, which is not evidence of equivalence.

**Holm.** Applied within each family named below. A missing p counts as 1, so the family size is kept.

### 9.2 Primary family (H1): DS, kappa 1.0, 44 test routes, Holm over 4

The four contrasts are Full FrameLease minus each of:
1. Fixed Deep;
2. Fast Only;
3. Age-Only;
4. Event-Triggered.

Reporting:
* each contrast is reported with its label;
* the outline's finding 1 ("improves over fixed-depth and fixed-refresh methods") may be stated only if contrasts 1
  and 2 are both "improves";
* finding 2 ("action-aware scheduling uses compute better than Age-Only and Event-Triggered") may be stated only if
  contrasts 3 and 4 are both "improves". It is shown next to the GPU-usage contrasts, which are descriptive;
* mixed outcomes are reported as mixed.

### 9.3 Secondary families (labelled secondary)

| family | contrasts | routes | correction |
|---|---|---|---|
| S-coll | collisions/km for the four H1 contrasts (lower is better) | 44 | Holm over 4 |
| S-dmr | DMR for the four H1 contrasts (lower is better) | 44 | Holm over 4 |
| H2 | DS, Full FrameLease - FrameLease + Heuristic | 44 | single test |
| H3 | DS, FrameLease + Heuristic - Original FrameLease; Full FrameLease - Original FrameLease | 44 | Holm over 2 |
| F3 | DS, Full FrameLease - Fixed Deep and Full FrameLease - Fast Only, at kappa 1.5 and 2.0 | E (22) | Holm over 4 |
| H4-cl | DS, FrameLease + Heuristic - `fl_global_shield`; FrameLease + Heuristic - Age-Only | E (22) | Holm over 2 |
| RL-abl | DS, Full FrameLease - `fl_bandit`; Full FrameLease - `fl_fqi_nolease` | E (22) | Holm over 2 |

Every other paired quantity is secondary or descriptive, uncorrected and labelled. For every Table I contrast this
includes SR (sign-flip test on the success indicator), RC, infractions/km, GPU usage, action age p50 / p95, fallback
ratio, EIR and closed-loop R_cond (standard validity), and P_both. The Fig. 3 curves are descriptive.

### 9.4 H4 offline decision rule

The quantity is SUFFIX - GLOBAL under nested selection at R_cond <= 5%, need 0.964 s, all plans, paired by clip, with
2000 clip-bootstrap resamples.

| label | condition |
|---|---|
| supported | the 95% CI of the continuity difference lies above 0, and the 95% CI of the realized-R_cond difference contains 0 or lies below 0 |
| contradicted | the continuity CI lies below 0 |
| inconclusive | otherwise |

Secondary, with the same rule: the same comparison at 10%; SUFFIX - AGE; utilization and premature refresh.

If an offline output lacks a paired quantity, the v4 analysis script computes it from `per_clip_selected.csv` with the
same bootstrap, within that file's scope (TRAIN-selected candidates, subset all, alpha 0.05); a nested quantity comes
from `paired.csv` only (Amendment A10).

### 9.5 H5 decision rule

* **Supported** if both hold:
  1. the commit audit (Sec. 7.6) finds 0 commits violating Eq. 9 in every run of every phase;
  2. stress test S3 finds 0 violations.
* **Contradicted** otherwise, with every violation listed.

The overhead quantities (Q-network p99 against B_pi, shield p99, budget overruns, DMR) are reported as measured.

### 9.6 Replicates and noise floor

Seed-12 replicates run on R (15 routes) for Fixed Deep, Fast Only, FrameLease + Heuristic and Full FrameLease. Reported:
* the per-arm seed-to-seed |DS(s11) - DS(s12)|, which is the noise floor;
* the seed-12 contrasts on R (descriptive);
* the RL gain by seed.

### 9.7 Manipulation checks (reported, not tested)

* **Fast prefix.** Active and validated in every run.
* **Charged prefix.** The p50 of every run lies within kappa x [0.35, 0.60] s; the pilot measured 0.416-0.426 s at kappa
  1.0. Deviations are flagged.
* **Configuration.** The configuration recorded in every run equals the registered one: arm, kappa, seed, envelope
  sha256, utility name (and so d*), A*, theta*, A_hb*, Q-network sha256, and the shield depth limit 10.
* **Predicted expiry fallback.** By the v2 rule, max(0, 2L + 0.05 - H) / L with the fast-prefix release time L:
  * Fixed Deep: L is about kappa x 0.6 s, so with the 3.0 s cap the prediction is about 0 at all three kappas;
  * Fast Only: about 0;
  * Age-Only: predicted from A* and its measured L, and compared with the observation;
  * a deviation of more than 5 percentage points is reported as a possible runtime problem.
* **kappa scaling.** Job durations at kappa 1.5 and 2.0 are within ±10% of kappa x the kappa-1.0 durations.
* **Shared shield.** `fl_full` and `fl_heuristic` have similar P_both (descriptive).

### 9.8 Missing data

Contrasts use pairwise-complete routes. Nothing is imputed. The n of every contrast and the dropped routes are reported.

### 9.9 Per-scenario and per-ability results

Descriptive only, with no per-scenario tests. Abilities follow the official multi-label mapping.

### 9.10 Sensitivity (minimum detectable effects)

**Variance estimate.** In the v2 matrix the paired DS difference Fixed Deep - Fast Only at kappa 1.0 had a 95% CI
half-width of 9.2 points at n = 44. That implies an SD of paired route differences of about 31 points.

**Minimum detectable effects** (80% power, two-sided):

| setting | n | alpha | MDE (DS points) |
|---|---:|---|---:|
| H1, first Holm step | 44 | 0.0125 | about 15.6 |
| H1, last Holm step | 44 | 0.05 | about 13.1 |
| families on E | 22 | 0.025 | about 20 |
| families on E | 22 | 0.05 | about 18.5 |

A non-significant contrast therefore means no difference larger than these was detected. It is not evidence of no
effect.

### 9.11 Interim looks

No test-route result is examined before the analysis freeze, except infrastructure monitoring: job health, timing and
disk.

The runner prints each run's status, DS and RC on its END line, and log tails may be read during monitoring. This is
disclosed. Such reads are never summarized across arms and are never used.

Training-route results are examined by design (Phase 1, D1, Phase 3).

### 9.12 Analysis code, freeze and verification

**Code.** `framelease_v4/analysis/aggregate_v4.py` (per-run rows, recomputed metrics, commit audit) and
`framelease_v4/analysis/analyze_v4.py` (Secs. 9.1-9.9). Both are written and tested on synthetic CSVs only. The
aggregator was also run read-only on finished P1 training-route runs during development (Amendment A9). Their sha256 is
entered in Sec. 13 before the analysis freeze (the aggregator: Amendment A3; the analysis code:
Amendment A10).

**Analysis code (Amendment A10).** `analyze_v4.py`, `prop1_coverage.py`, `figures_tables.py` and
`verify_independent.py` (`framelease_v4/analysis/`) are registered by Amendment A10. Besides synthetic data, they were
run read-only during development on training-route aggregations, the offline VAL clips and P1 run directories, never
on a test-route run.

**Freeze.** The analysis freeze happens when every registered job of tiers 3-6 is final, or when a cut recorded as an
amendment (Sec. 10.2) takes effect. The time and the job status are recorded. Outputs go to
`outputs/framelease_v4/analysis/final_<stamp>/`, with a sha256 manifest; the analysis writes into its subdirectory
`analysis/` with its own manifest (Amendment A10).

**Verification.** Before any number enters the paper, an independent session recomputes the H1 contrasts and the Table I
columns from the raw run directories (Amendment A10: `framelease_v4/analysis/verify_independent.py` recomputes DS, SR,
RC, collisions/km and infractions/km; Amendment A11: `framelease_v4/analysis/verify_table1_extra.py` recomputes GPU
usage, DMR, action age p50 and p95, fallback ratio, EIR, P_both and the closed-loop R_cond, which enter the paper once
its result is entered in Sec. 13).

### 9.13 Reporting rules

* Every registered result appears in the paper or its supplement.
* Null and negative results are stated as such, with their CIs.
* RL benefit is claimed only if H2 is "improves". With P_both < 0.05 it is labelled not testable (Sec. 5.8).
* Proposition 1 is stated as conditional. Envelope coverage and realized validity are reported. The RA rule appears
  only as an offline sensitivity, labelled as a definition change.
* The fast prefix is applied to every arm and is not counted as a FrameLease gain.
* The DS-risk position of the selected lease point is disclosed (Secs. 4.3, 7.2, 7.4).

## 10. Run budget and phased schedule

### 10.1 Budget

**Planning figures.**
* Wall time: 450 s per closed-loop run, the measured mean of the 12 fast-prefix pilot jobs (min 173 s, median 260 s,
  max 906 s). For reference, the v2 tier-1 jobs averaged 346 s per run with the unmodified prefix.
* Disk: 10 MB per run.
* Worst case: every run hits the 1500 s wall cap.

Generated by `framelease_v4/protocol/make_protocol_tables.py` into `outputs/framelease_v4/protocol/budget.md` (FULL,
the registered plan; TRIMMED: `budget_trimmed.md` and Sec. 14). GPU-h at 7.5 min (450 s) per run, disk at 10 MB per run.
Every figure is computed from its own run count (exact, then rounded half up: GPU-h to 0.1, GB to 0.01); no figure is a
sum of rounded values, so a column need not add up to its rounded total.

| phase | tier | block | content | runs | GPU-h | GPU-h worst | disk GB |
|---|---:|---|---|---:|---:|---:|---:|
| P1-0 | 0 | smoke | P1-0 real-CARLA smoke: fixed_deep, fast_only, age_only, event_triggered, fl_original, fl_heuristic at E5, behaviour policy at E5 x 1 training route outside T22 (18305) | 7 | 0.9 | 2.9 | 0.07 |
| P1 | 1 | T-ref | references, untuned: Fixed Deep and Fast Only x T22 | 44 | 5.5 | 18.3 | 0.44 |
| P1 | 1 | T-lease-s1 | lease grid {E5, E10, B0} x T22a (FL+H, d = 10, std validity) | 33 | 4.1 | 13.8 | 0.33 |
| P1 | 1 | T-event-s1 | Event-Triggered grid, 4 candidates x T22a | 44 | 5.5 | 18.3 | 0.44 |
| P1 | 1 | T-lease-s2 | lease grid, top 2 x T22b | 22 | 2.8 | 9.2 | 0.22 |
| P1 | 1 | T-event-s2 | Event-Triggered grid, top 2 x T22b | 22 | 2.8 | 9.2 | 0.22 |
| P1 | 1 | T-heur-s1 | heuristic d in {4, 1} x T22a at L* (d = 10 reused from the lease grid) | 22 | 2.8 | 9.2 | 0.22 |
| P1 | 1 | T-heur-s2 | heuristic survivors without T22b runs x T22b (at most 2) | 22 | 2.8 | 9.2 | 0.22 |
| P1 | 1 | T-age-s1 | Age-Only grid, 4 candidates x T22a (utility a_det^{d*}) | 44 | 5.5 | 18.3 | 0.44 |
| P1 | 1 | T-age-s2 | Age-Only grid, top 2 x T22b | 22 | 2.8 | 9.2 | 0.22 |
| P2 | 2 | RL-data | behaviour policy (eps 0.3) at L*, 44 training routes x kappa {1.0, 1.5, 2.0} | 132 | 16.5 | 55.0 | 1.32 |
| P4 | 3 | TI-main | Table I: 7 arms x 44 test routes, kappa 1.0, seed 11 | 308 | 38.5 | 128.3 | 3.08 |
| P5 | 4 | F3-k | Fig. 3: 4 arms x kappa {1.5, 2.0} x subset E | 176 | 22.0 | 73.3 | 1.76 |
| P6 | 5 | A-lease | Table II-A closed loop: Global-Margin lease + shield + heuristic x E | 22 | 2.8 | 9.2 | 0.22 |
| P6 | 5 | A-rl | Table II-A RL: Bandit and FQI w/o lease features x E | 44 | 5.5 | 18.3 | 0.44 |
| P6 | 6 | S-seed12 | seed-12 replicates: Fixed Deep, Fast Only, FL+H, Full FL x R | 60 | 7.5 | 25.0 | 0.6 |
| P6 | 6 | S-risk | conditional (only if L* = B0): fl_risk at the better of E5 / E10 x E | 22 | 2.8 | 9.2 | 0.22 |

| phase | runs | GPU-h | GPU-h worst | disk GB | free disk needed at phase start, rest of the plan (GiB) | free disk needed for this phase alone (GiB) |
|---|---:|---:|---:|---:|---:|---:|
| P1-0 | 7 | 0.9 | 2.9 | 0.07 | 15.8 | 6.1 |
| P1 | 275 | 34.4 | 114.6 | 2.75 | 15.7 | 8.6 |
| P2 | 132 | 16.5 | 55.0 | 1.32 | 13.2 | 7.3 |
| P4 | 308 | 38.5 | 128.3 | 3.08 | 11.9 | 8.9 |
| P5 | 176 | 22.0 | 73.3 | 1.76 | 9.1 | 7.7 |
| P6 | 148 | 18.5 | 61.7 | 1.48 | 7.4 | 7.4 |
| total | 1046 | 130.8 | 435.8 | 10.46 | | |

Without the P1-0 smoke block: 1039 runs, 129.9 GPU-h, 10.39 GB.

Upper bounds: the grid sizes assume 3 lease candidates and that d = 10 is not a heuristic survivor (if it survives,
`heur_s2` has 11 runs instead of 22). Pruned grids (Sec. 4.3) and reused runs only lower the counts.

**Disk prerequisite.** The "rest of the plan" column is the disk of the runs that remain from that phase on plus the
runner's 6 GiB floor; "this phase alone" is the phase's own runs plus the floor. Both are rounded up to 0.1 GiB.
* To run the whole plan without intervention: at least 15.8 GiB free before P1-0.
* To start P1-0 alone: at least 6.1 GiB free; P1 alone: 8.6 GiB.

The user freed disk space before registration; the free space at registration is recorded in the registration entry
(Sec. 13.1). The disk is shared with other projects: the runner's floor and the disk watchdog (Sec. 8.5) protect it,
and files of other projects are never deleted by this work.

### 10.2 Schedule

**Duration.**

| phase | duration |
|---|---|
| P0 | about 1 day of CPU work, in parallel with the disk clean-up |
| P1-0 | 0.9 h + the smoke check (about 1 h) |
| P1 | 34.4 h + stage gaps (about 1.5 h) |
| D1 | user |
| P2 | 16.5 h |
| P3 | about 3 h CPU; the GPU idles |
| P4 | 38.5 h |
| P5 | 22 h |
| P6 | 18.5 h |
| P7 | about 0.5-1 day CPU |

The GPU time totals about 131 h (FULL: 130.8 h), i.e. about 5.5 days of continuous use; TRIMMED about 72 h (Sec. 14).

**Example calendar (FULL).** Assuming P1-0 starts on 2026-11-11 at 12:00 and D1 takes no time:

| phase | ends about |
|---|---|
| P1-0 | 11-11 14:00 |
| P1 | 11-13 02:00 |
| P2 | 11-13 18:15 |
| P3 | 11-13 21:15 |
| P4 | 11-15 11:45 |
| P5 | 11-16 09:45 |
| P6 | 11-17 04:15 |
| P7 | 11-18 |

**No deadline.** The user decided on 2026-11-10 that this work does not target DAC 2027. No deadline constrains the
schedule, and the registered plan (FULL) runs to completion.

**Cuts.** No schedule-only reduction is registered. A cut is made only by the user's decision, recorded as an amendment
(Sec. 13.2) before the affected phase starts. It may depend on measured run times and resources only, never on results;
tiers are cut from the bottom (tier 6, then 5, then 4), and tier 3 (Table I) is never cut. A cut is recorded with the
job status at the cutoff.

## 11. Known before registration; threats to validity

### 11.1 Results known to the authors before registration

1. **The v2 matrix,** on the same 44 test routes with the unmodified prefix (2026-11-07/08;
   `framelease_v2/CLOSED_LOOP_RESULTS.md`).
   * Fixed Deep DS 48.4 and Fast Only 39.3 at kappa 1.0. The paired difference was +9.09 [0.03, 18.49], p = 0.067.
   * The synchronous oracle beat measured-latency execution (Sec. 1.1).
   * Fixed Deep at kappa 2.0 scored DS 32.5 on C.

   The test routes are therefore not fresh: the authors know the baseline outcomes there. The v4 arms and grids were
   designed with that knowledge, but no v4 parameter is tuned on these routes.
2. **v2 FrameLease-Global,** i.e. Original FrameLease without the fast prefix: DS 1.7 on C, with 94.4% fallback ticks.
3. **The fast-prefix pilot** on the training routes 2086, 18305, 2554 and 1792 (seed 11, kappa 1.0; RND Sec. 5).
   * Fast Only vs Fast Only with the fast prefix: charged prefix 0.92 vs 0.42 s; action age p50 1.45 vs 0.70 s.
   * The v3 FrameLease + Heuristic arm with the q95 envelope: 89-97% fallback ticks and median lease 0 s; 2 of 4 routes
     blocked.
   * Mean DS over the 4 routes: 66.4 / 50.4 / 21.6 for the three arms.
4. **The offline R&D** (RND Secs. 3.1-3.10). With UniDriveVLA's own detections the lease is conservative:
   * best nested continuity at R_cond <= 5%: 15.4% (15 VAL clips, need 1.842 s) and 54.5% (32 VAL clips, fast-prefix
     need; RND Table 9 row 11);
   * B0 is 86.3% continuous at R_cond 49.6% (need 1.842 s).

   The closed-loop cost of this conservativeness is what the lease grid (Sec. 4.3) measures on training routes.
5. **The v4 offline lease ablation** (Table II-A, offline) was computed by a parallel task on 2026-11-10, 15:42-15:59,
   before this registration.
   * Its selection rules were declared in its progress log before any VAL metric was viewed (per that log).
   * The author of this protocol viewed only the column headers of its CSV outputs, not its values.
   * The H4 offline rule (Sec. 9.4) is fixed here, but its data already exist. It is labelled "pre-specified in code,
     executed before registration".
6. **The `framelease_v4/rl` and `framelease_v4/arms` code** is being smoke-tested on the 12 pilot runs, which are
   training routes.

### 11.2 Threats to validity

1. **Noise.** One seed per route, and large route-level noise (paired SD about 31 DS points). Seed-12 replicates on R
   quantify it.
2. **Contention is simulated.** kappa scales the measured CUDA times. The GPU budget is a capacity share, not a
   duty-cycle limit, so Eq. 5's G_rem term is vacuous here.
3. **Shared CPU.** Scheduler CPU time is measured on a CPU shared with other projects and charged to the timeline. Load
   inflates it, more for arms with more CPU work per boundary. The runner records GPU samples. CPU load is measured:
   every run's charged prefix p50 is compared with the idle band kappa x [0.416, 0.426] s (the pilot range of
   Sec. 9.7) and flagged, never excluded (Amendment A8).
4. **The fast prefix is not bit-identical.** Plans move 1-5 cm. It applies to every arm.
5. **The lease uses the model's own detections** and a statistically calibrated envelope. Proposition 1 is conditional,
   and the shield is soft real time.
6. **DS-based tuning may select a high-risk lease point.** It is disclosed (Sec. 4.3), and `fl_risk` is the
   sensitivity check (FULL). The RA rule is not used in closed loop.
7. **Tuning precision.** Tuning uses 22 routes in successive-halving stages of 11; selection noise is large (Sec. 4.2).
8. **The Eq. 7 reward is approximate within an episode** (prefix-score reconstruction), though exact at its end.
   P_both may be low.
9. **Realized validity in closed loop** is measured against actors that react to the ego. It is not a counterfactual.
10. **Town mix.** Test routes are mostly Town12 and Town13. The training pool adds Town01, Town07, Town10HD and Town15.
11. **Envelope calibration data.** The envelopes were calibrated on clips of the official Bench2Drive training split,
    which the checkpoint has probably seen. The VAL clips are official validation clips.
12. **Min-speed records** are excluded from infraction counts (no penalty, Sec. 6.1).

## 12. Provenance

### 12.1 Fixed at writing

| sha256 | file |
|---|---|
| 51917f83aca2acf7488a8133823342a5719b8634e2685b41612bb0028a7723b9 | /home/kang/Desktop/NEW/FrameLease1109.docx (outline) |
| 5e3d8dd2218de8d9566c1688465e6cd950921b57508bb8ea7653aec5997b2c7f | /home/kang/Downloads/FrameLease+的+Introduction+可以从+背景.docx (guide) |
| 60f49f692ce855b9ca784c3e05433f1c4d43e93356724fad75db371dd4ca7b18 | /tmp/fl_extract/FrameLease1109.md (text extract) |
| 1b1db8edc3ee04caa5f731a042db36a67ee3b0bed425a7c5327d272be0db174c | /tmp/fl_extract/FrameLease_intro_guide.md (text extract) |
| 09f581de9828bae882d6ca29e7d61cbe70a49ef12a684bc1b8469e717fac73f2 | outputs/framelease_v2/closed_loop_matrix/routes.json (test routes) |
| ffff24b3a2b8584632730fb42de7cb6036af780c3952cfef08ee8cf96a712f88 | third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/data/bench2drive220.xml |
| 555f6869cb62d89082efc0fefc8f125ee133b16fd36a6fcf9f68bb1269fa527e | outputs/framelease_v4/protocol/route_split.json |
| see `outputs/framelease_v4/protocol/MANIFEST.sha256` | framelease_v4/protocol/make_protocol_tables.py, budget.json, budget.md |
| b127eebb319aa52dbd35f2099bb1bda5c1c7732c2f811cae88454ce15e6c23fc | checkpoints/UniDriveVLA/b5ac33e9.../UniDriveVLA_Stage3_Bench2drive_2B.pt (5,923,425,558 bytes) |
| 00c62aad25d041312d6ba1918d6fb5ecb41c3ea1259f58be5977abcb3cce10e8 | outputs/framelease_v2/c2_calibration/full_20261107T045343Z/lease_params_q95_envelope.json (Original FrameLease) |
| 5478c9f9cfb327c87361bf3f7832d3b6315be622414345f40fba82bd8093cc84 | framelease_v2/analyze_closed_loop.py (statistics functions, imported) |
| 7a44bc95269d606a71bba32e89605bdd7a6822d5a0c3ff4d0607124195ad4e04 | framelease_v2/gpu_queue.py (runner) |
| 038636f72912dd6062ebbf48da9b99e22dbc1233645d986055de81240c953f9f | framelease_v3/renewal/renewal_compute.py (`RA_RULE`; offline sensitivity only) |
| 1ca847572e4cca37766ed17f820d96de1c6f51166c43f64ca586b3c7e677aa2e | framelease_v3/RND_REPORT_20261110.md |

The text extracts live under `/tmp` and do not survive a reboot. At registration they were copied, unchanged (same
sha256), into `outputs/framelease_v4/protocol/sources/`.

### 12.2 Filled at registration (2026-11-10)

**Registration manifest.** `outputs/framelease_v4/registration/MANIFEST.sha256` (sha256sum format; paths relative to
`/home/kang/Desktop/DAC` unless absolute) lists every file of this section and of Sec. 12.1, every `framelease_v4`
source, test and document except this file, `framelease_v4/PIPELINE_STATE.md` (workflow state) and scratch files, the
job files with their stage specs and checks, the generated tables, the RL collection plans, the text extracts of the
outline and the guide, and the logs of the registration test runs. This file cites the manifest's sha256 in its
registration entry (Sec. 13.1); both are sealed in `outputs/framelease_v4/registration/SEAL.sha256`.
`framelease_v4/protocol/registration.py --verify` re-checks every entry.

**(a) Pinned by every Phase-1 job line** (`require_sha256`, Sec. 8.3; 49 files). The runner does not start a line while
any of these differs from the pin.

| sha256 | file |
|---|---|
| 27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516 | checkpoints/Qwen3-VL-2B-Instruct/89644892e4d85e24eaac8bacfd4f463576704203/preprocessor_config.json |
| 4f7328974c88703caf17d709cb238f28de543e698b8ad9ca3b4a9ae23a8ee576 | framelease_common.py |
| e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | framelease_v2/__init__.py |
| b26ccab28d00219b18d9dd59bce112f54917ba05c9f293cbb6357288b7954006 | framelease_v2/geometry.py |
| 285f2fc4f328d360dba2aecd84bbb7fc81c072c964ee793b2a43362e7c467bfc | framelease_v2/latency_agent.py |
| d3895edfd8d8640a8514ebe8c7eb3b0efb9c32847e3614158a4562c59fe466b6 | framelease_v2/lease.py |
| 5fb8d34d8b405a668b2286452f0ec8a66b867d909b76c7c30998b779f97f6074 | framelease_v2/policies.py |
| 7876025b56fe18d220366d86c50feff5bf280565162e73129e15448c12cde425 | framelease_v2/run_closed_loop.py |
| ee2b2cea1a2496ac54b3b301399de352dde0fc9cf6c9ecebb1b676525aaec97b | framelease_v2/unidrive_boxes.py |
| e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | framelease_v3/__init__.py |
| 7b2370e7c4a3708b4a44f07fc03857168ea416558a7779da888708907a445155 | framelease_v3/fastprefix/__init__.py |
| 08d739166aac34c89783b0193eb32834fed21f15bbda2f068b8e638325cea6c7 | framelease_v3/fastprefix/agent_entry.py |
| 480fbb5ae0dcfdbf71a1527034b496ae3447b135ecaf3190fd548dd2291e5524 | framelease_v3/fastprefix/fast_path.py |
| 3cf3cc3c11d4913e85009faa715a7cb42bbb743563a03013c475902d571ba89f | framelease_v3/fastprefix/run_closed_loop_fast.py |
| 49e484f41e0d9feb5168f08d99feda3448f08d8e62906c88c95ddeedc42f021e | framelease_v3/runtime/__init__.py |
| e9f945bd1a579a42cb8ecbd4352b676f2e9726498b5a2278a6820cc8eda9f4ec | framelease_v3/runtime/run_closed_loop_v3.py |
| b9f1324df71a25ef3379197b05ba84cdf120d492c883ff351fcaccd05e925c63 | framelease_v3/runtime/v3_agent.py |
| 1b9dd78a47406086323faa8ec30345e1559b23c8aea87e40cbcda64696b1f205 | framelease_v3/runtime/v3_arms.py |
| 72892940f22b610da3c2f6b7c47fd69020a09977fc394201ae85ec1c54c79987 | framelease_v3/runtime/v3_commit.py |
| 64d56c95e9b6c2aac23ceb35d494f0054bd5b48a6cd9f84528afabc587d471b3 | framelease_v3/runtime/v3_lease.py |
| c64e97d9ba2fc578ca8fa6142998939ca4e6f82f2ded189894134ab0ac71217b | framelease_v3/runtime/v3_scheduler.py |
| 138d6b8b186e2397b8d1a13a12711150d42fad214509271ff777052d867b2a84 | framelease_v3/runtime/v3_shield.py |
| f596deb9464c3955bb62f7a2ac0344f9bf97a6432adf3ffe052996d0446c4757 | framelease_v4/__init__.py |
| e5c3b076fead1edd2321c8cfa7d42a84fd9cb5bb911f65717aace0d3110271d9 | framelease_v4/arms/__init__.py |
| 0fd0218a1e566bc6531fdf2b112c459bfa97e25eb58574c55516d57004d10b3b | framelease_v4/arms/actor_log.py |
| d81ae1d7ac79baf1edfce024f154668469a30812d0bebce6beccfbed21a43c7a | framelease_v4/arms/agent_v4.py |
| 3a20c70e6ddcbe3da0c8a61594bedf23f7c8b77fcd0adda585b6dad4a53b8606 | framelease_v4/arms/arms_v4.py |
| 6b98ccbedec7f0bab2e04f24fe589e8928d18fa58cf3732563eaba979805b748 | framelease_v4/arms/policies_v4.py |
| cf60d3e12048a76f058ae431a281e48d4a092543d706ed46074d7e93f732829b | framelease_v4/arms/run_closed_loop_v4.py |
| a316f2fa201d24f7c31c2022ff8116c18e6b64f36f973b79ef6d2612710c626b | framelease_v4/arms/runtime_v4.py |
| d807a3471e4dc141ebc039956af55eb7d28ea6718b2229b0d6d9ecdb24bc1f46 | framelease_v4/rl/__init__.py |
| 3ba13de1569b79dadf3a2019ec6495ff1ae1f4113a8d9f2e72b69e987dba8345 | framelease_v4/rl/behaviour.py |
| 537ee597e34f3e8ab44ae7e3f08f35293a81e6fd266a9e838774a34cca40e6e3 | framelease_v4/rl/features.py |
| 53bbf8c69124519c6bb2133961695aa4f238c6d52e325f0d8e7de53008d23f3f | framelease_v4/rl/qnet.py |
| 208260089a7726972b2b6114b4acd4cab2bd751bc989567bb70102bcc1f02e23 | linux/env.sh |
| 00c62aad25d041312d6ba1918d6fb5ecb41c3ea1259f58be5977abcb3cce10e8 | outputs/framelease_v2/c2_calibration/full_20261107T045343Z/lease_params_q95_envelope.json |
| a98abe92c6cf5f8ec38106ac20241bb9c4ccc61fd8ec40527dd7da8dca24fcbc | stage02_real_vla.py |
| 0a6142eed3b057c1c8b1ee037c25fb18750d35a575488a0992517c3a3a7d9a0b | stage05_carla_closed_loop.py |
| ffff24b3a2b8584632730fb42de7cb6036af780c3952cfef08ee8cf96a712f88 | third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/data/bench2drive220.xml |
| 5cbd28779050575dcd8f86f7b0805d0791ff41000319d83e16379e902bbe358f | third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/leaderboard/leaderboard_evaluator.py |
| 2276269fca0befdf31a34cd3e22052495e0eac34dcbbab54ada1dea6ff71c6d6 | third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/team_code/pid_controller.py |
| 96d347c1b0eacc6a5036670595b1baaed2654dd2c44e1a674564617ccae8d284 | third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/team_code/unidrivevla_b2d_agent.py |
| 39aaf2d834165d9d9a19867720b03c8817381e1b5d7111f9412c924bd2eff4af | third_party/UniDriveVLA-linux/Bench2Drive/projects/configs/unidrivevla_b2d_stage2_unified_2b.py |
| b61293f8b9f94b20edbcee828f7008d18c475408f3e3a67697c61e57131654cf | third_party/UniDriveVLA-linux/Bench2Drive/projects/mmdet3d_plugin/models/vla/qwenvl3_vla_planning_head.py |
| c7f28dde1d485049f0d69e62a61bae862f5905a5b93a9264ce8dd046928bf181 | third_party/UniDriveVLA-linux/Bench2Drive/projects/mmdet3d_plugin/models/vla/unidrivevla_vlm_qwenvl3.py |
| 2276269fca0befdf31a34cd3e22052495e0eac34dcbbab54ada1dea6ff71c6d6 | third_party/bench2drive-linux/leaderboard/team_code/pid_controller.py |
| 99178efb83af3d02068d7346732948cef445ad76a756caf2f95d489147aece31 | third_party/bench2drive-linux/leaderboard/team_code/planner.py |
| 96d347c1b0eacc6a5036670595b1baaed2654dd2c44e1a674564617ccae8d284 | third_party/bench2drive-linux/leaderboard/team_code/unidrivevla_b2d_agent.py |
| 4fc1f406bc9dc908411c4fb142179bb021c32afc3515f6f140ec956d66320509 | third_party/transformers-linux/src/transformers/models/qwen3_vl/modeling_qwen3_vl.py |

**(b) Envelope files** (pinned in addition by the shield-arm lines, `fl_heuristic` and `fl_behaviour`) and the inputs and
code of their export (Sec. 4.3):

| sha256 | file |
|---|---|
| 21d0b4a441cf80e32e4f04ddeb9bf309b5a0a74c9495652fd04a88331c47df3a | outputs/framelease_v4/envelopes/E5.json |
| bf61635ba3a38b7a307a4e1e4db4ad0541d7afc65cfd9afc432f9f054e1a2229 | outputs/framelease_v4/envelopes/E10.json |
| 9ef8479f04dab873d22b50e8732176804ed67f351f17584355b241e424fa1927 | outputs/framelease_v4/envelopes/B0.json |
| 7c364867f4aa515855f72e827c393052e564add8f6f6a3201d75c63893af6cbb | outputs/framelease_v4/envelopes/manifest.json |
| 9941574c2c10244f111a3974512b3e34f0409192c5c37b749cc9bce5126ed5f7 | outputs/framelease_v4/offline_ablation/frontier.csv |
| 86821422482caa38ea69f7402ff47ba313c63a3890c97b370c3b625c01f8dff8 | outputs/framelease_v4/offline_ablation/envelopes/train_E0.json |
| e01589a874734e4b5694dfc1414d24a74b0a66bbe3bf4a73d04db8fcba9ead67 | framelease_v4/offline/export_envelopes.py |

**(c) Protocol scripts and tools** (registered; not imported by the agent, so not pinned by the job lines):

| sha256 | file | role |
|---|---|---|
| d953cb18b92f6f3d627e3e13b9cf5c685abbffbd8a845feb8db31203c1825fad | framelease_v4/protocol/p1_jobs.py | Phase-1 job files and their checks (Secs. 4.2, 8.2) |
| 146b8b1a3f75a467a7a21f1080a0b7c46b5e8a8500fe85c311487b6d9f12c867 | framelease_v4/protocol/select_stage.py | stage selection and tuning freeze (Secs. 4.2, 4.9) |
| bf8287d0867a4c4f84fcab12ed7a05527fc0fbc6936aa01d05f9402883ca9948 | framelease_v4/protocol/check_smoke.py | P1-0 smoke check (Sec. 8.1), amendment A1; version 1.2 (`0ad0f1e3...cd61e`) was registered before any smoke run existed |
| e0264cbb5acb588fa01e00115da6ba9914b74a86dbb880dd1dade31c6223d4cd | framelease_v4/arms/agent_frame.py | official agent GNSS frame for `pose_offset` (amendment A1); not imported by the agent |
| e12130fab39449afa1ae2ced4996d415cabcc79fbd051745dc0473dcbbf508f9 | framelease_v4/protocol/d1_summary.py | D1 training-route summary (Sec. 4.8) |
| 4fa918882f6908e019452c9bd3056944282be103dd0c7d9656c6b57c494dd722 | framelease_v4/protocol/launch_queue.sh | runner launch (Sec. 8.2) |
| b01694dfd348f47191425dcced3b7f3864d0194e3c71f64374b2a4253f4af2aa | framelease_v4/protocol/disk_watchdog.sh | disk watchdog (Sec. 8.5) |
| e2afe1c0c5ab25c402ef4a43a03b8bd9ae7178323bb542fa6711a49c6f466842 | framelease_v4/protocol/make_protocol_tables.py | route split and budgets (Secs. 3, 10, 14) |
| 1f1cc02314635a674733e70cfc0729cb2815b50275d4e599fe263fce5568f1b8 | framelease_v4/protocol/registration.py | registration manifest and seal (Sec. 13.1) |
| 7849b11e5a9ea7bc29ffe7aaf33003780bb76a0d74a6c71c01ef9fb9e6b094d8 | framelease_v4/arms/metrics_v4.py | per-run metrics (Secs. 4.8, 6) |
| ad00b08d837d683fce4f6d97daf48a21eea113afdefdf64058c54905d2b2a337 | framelease_v4/arms/realized.py | realized validity (Sec. 6.3) |
| 6c8bd36ef0f49aa82b06abc82b94e37da7e9860570626b6a79f8ccf6ad1c9bc0 | framelease_v4/rl/collection_plan.py | P2 run list and behaviour seeds (Secs. 2.6, 5.3) |
| 7a44bc95269d606a71bba32e89605bdd7a6822d5a0c3ff4d0607124195ad4e04 | framelease_v2/gpu_queue.py | the runner, unchanged (Sec. 8.2) |

**(d) Job files and generated tables.** Every line of the job files passed gpu_queue's contract, the pins, the launcher's
parsing, configuration build and preflight and the `--dry-run` of its exact command, on the CPU without CARLA
(`.check.json` next to each file, written at registration by `p1_jobs.py` with the sha256 of (c)). The TRIMMED files are
not part of the registered plan (Sec. 14).

| sha256 | file | lines |
|---|---|---:|
| 32c6d0b5e813fc0b26e41c5a0228683d0366a92081209537192731878928e2c2 | outputs/framelease_v4/p1_jobs/P1-0/b00_smoke.jsonl | 7 |
| ca41d996e59d03fb99e84189fc7968d0be79fcf9f305e77a00ffc8cb02d721e5 | outputs/framelease_v4/p1_jobs/FULL/b01_ref.jsonl | 44 |
| 24223de6aa8998b80df23dfbe17369c18c22f82fc55f825442424b5c9bf268e7 | outputs/framelease_v4/p1_jobs/FULL/b02_lease_s1.jsonl | 33 |
| a80b7b6c206bcaa8b7b673229ebd1fb5a9423b2bbc22e86558b64305ee8285e1 | outputs/framelease_v4/p1_jobs/FULL/b03_event_s1.jsonl | 44 |
| 24223de6aa8998b80df23dfbe17369c18c22f82fc55f825442424b5c9bf268e7 | outputs/framelease_v4/p1_jobs/TRIMMED/b02_lease_s1.jsonl | 33 |
| 97dd3f76531da45de3645fdca90760553050ea25f60672cc9972bc14717765a8 | outputs/framelease_v4/p1_jobs/TRIMMED/b03_event_s1.jsonl | 22 |
| c62813304c6bfa00c89e07aa904cbb8313c95aa2979376ea666651f5c1fb8c9a | outputs/framelease_v4/p1_jobs/P1-0/b00_smoke.meta.json | |
| 1b75a988aad1f1053dbfc1cb1f73fe9b3af2a8528b14cd43855388d207050809 | outputs/framelease_v4/p1_jobs/FULL/b01_ref.stage.json | |
| d5b9089688f713a61ed7736353eb5cdc41cf36085cfab4e5734d140967188c04 | outputs/framelease_v4/p1_jobs/FULL/b02_lease_s1.stage.json | |
| bc7c58dfbc6db3cc85047008f1f81191322cec122a5f09c21b9c8bca77188323 | outputs/framelease_v4/p1_jobs/FULL/b03_event_s1.stage.json | |
| 555f6869cb62d89082efc0fefc8f125ee133b16fd36a6fcf9f68bb1269fa527e | outputs/framelease_v4/protocol/route_split.json | |
| 1144d139f43332dfbd16d603978f4eb0dc21baefda9c0453c07784587e6efa16 | outputs/framelease_v4/protocol/budget.json | |
| d98d6bb0d91fa28b4ad3f0114358c1faa0db38a4b6499cd19e160a353b204590 | outputs/framelease_v4/protocol/budget.md | |
| aec5c82f27229f3b75e7cc43fe7a74241ea1883b567b5f1e3df6b062cbb3a5f3 | outputs/framelease_v4/protocol/budget_trimmed.md | |

Files created later (`selection.json`, the Q-networks, the P4-P6 job files) are entered in Sec. 13 at the tuning and
test freezes.


## 13. Registration and amendments

### 13.1 Registration checklist

Registration happens when all of the following hold. It is recorded below with date and time.

1. **Implementation.** The Sec. 4.1 items marked present are implemented, and the CPU tests of `framelease_v4/arms`,
   `framelease_v4/rl`, `framelease_v4/offline` and `framelease_v4/protocol` pass. The tests include:
   * V4Runtime timeline equality with v2 for the v2 rules;
   * the exported envelopes reproduce the offline tau* and H on recorded frames within 5e-6 s;
   * a_det^{d} behaviour, its registration in the launcher and in a fresh agent process, and the max_depth guard;
   * the job contract, the stage selection rules, the smoke checker, the disk watchdog and the launch wrapper, the D1
     summary and the registration manifest (`framelease_v4/protocol/tests`).

   The commit audit of Sec. 7.6 is part of the v4 aggregator (Sec. 4.1, still required, item 2) and is tested with it,
   on synthetic violations, before the analysis freeze; it is not needed before P4.
2. **Phase-1 job files** are generated and validated by gpu_queue's contract, the pins, the launcher's parsing,
   configuration build and preflight, and the `--dry-run` of the exact command, on the CPU without CARLA. Done at
   registration for P1-0 and the blocks without a dependency (FULL `ref`, `lease_s1`, `event_s1`; TRIMMED `lease_s1`,
   `event_s1`); the dependent blocks are generated after each selection.
3. **Envelope files** E5, E10 and B0 are exported and hashed (done in version 1.1). The grid is pruned by the rules of
   Sec. 4.3 (no rule applied: K = 3).
4. **Sec. 12.2** is filled.
5. **Disk.** The prerequisite of Sec. 10.1 (FULL) or Sec. 14 (TRIMMED) is met and the disk watchdog is in place.
6. **Approval.** The user approves the GPU and disk budget of Sec. 10 or Sec. 14. The GPU and the disk are shared with
   other projects.
7. **Variant.** The user chooses FULL (default) or TRIMMED (Sec. 14); the choice is recorded here before P1.

**Registration entry, 2026-11-10 22:45 (Beijing time): REGISTERED, variant FULL, protocol version 1.2.**
* Variant and budget (items 6 and 7): FULL (Secs. 1-13): 1046 closed-loop runs, 130.8 GPU-h at the planning figure
  (435.8 GPU-h worst case), about 10.5 GB of disk. These are the user's decisions of 2026-11-10, recorded in
  `framelease_v4/PIPELINE_STATE.md` and relayed to the registering session: budget = the FULL protocol (about
  131 GPU-h); the work does not target DAC 2027 (no deadline); disk space was freed. With these decisions the user
  instructed a pause after P1-0: the 7 smoke runs are run and checked, and P1 starts only when the user says to
  continue.
* Implementation and tests (item 1): the CPU tests pass, 138 passed and 17 skipped without the official stack and
  155 passed with it (`outputs/framelease_v4/readiness_fixes/pytest_isolated.log`, `pytest_official.log`).
* Job files (item 2): regenerated and checked at registration by `framelease_v4/protocol/p1_jobs.py` (sha256
  `d953cb18b92f6f3d627e3e13b9cf5c685abbffbd8a845feb8db31203c1825fad`): P1-0 7 lines; FULL 44 + 33 + 44; TRIMMED
  33 + 22. Every line passed gpu_queue's contract, the pins, the launcher's checks and its `--dry-run` (`.check.json`).
  The FULL and TRIMMED job files are byte-identical to version 1.1; the smoke file is new (`age_only` with
  `v4_adet_d4`).
* Envelopes (item 3): E5, E10 and B0 as in Secs. 4.3 and 12.2; no pruning rule applied (K = 3).
* Pins and script hashes (item 4): Sec. 12.2.
* Disk (item 5): 17.72 GiB free on the project file system at 22:44, against the FULL prerequisite of 15.8 GiB.
  `disk_watchdog.sh` and `launch_queue.sh` are registered (Sec. 12.2); the wrapper starts the watchdog with the runner.
* Manifest: `outputs/framelease_v4/registration/MANIFEST.sha256`, 144 files, sha256
  `f5d1028d750b3919c3014055052f437c13f0a1bea1dc2f66f268cae0e3378932`. This file, with this entry, and the manifest are
  sealed in `outputs/framelease_v4/registration/SEAL.sha256` (details in `REGISTRATION.json`).
* State at registration: no v4 closed-loop run, no queue directory and no smoke result existed. The smoke checker
  `framelease_v4/protocol/check_smoke.py` (sha256 `0ad0f1e3e757c89e2adb4556baaa85976053be83af5c6d2fb55f741991bcd61e`)
  was registered before any smoke run.

### 13.2 Amendments

**Smoke report 1, 2026-11-10 23:43 (Beijing time): FAIL.** `outputs/framelease_v4/smoke_p1_0/smoke_check_attempt1_FAIL.json`
(sha256 `2f7617a7053108a7a333db56841bdff21d80ce19386deb9b9375cad346e807df`; the same bytes were written as
`smoke_check.json`). Queue `outputs/framelease_v4/queue_p1`, 7 of 7 runs final. 10 of 11 criteria passed on every run;
`pose_offset` failed on every run with a planar offset p50 of 1176.54-1176.73 m.

**Amendment A1, 2026-11-11 (Beijing time): the `pose_offset` reference frame.** No P1 run exists.
* Cause. The official agent solves its GNSS reference in `init()` (`unidrivevla_b2d_agent.py` lines 354-375; fsolve
  from [0, 0]) from the first point of the global plan. On maps with geoReference lat_0 = lon_0 = 0 (Town12; also
  Town01/04/07/10HD), the longitude equation reduces to lon_ref = the longitude of that point. Its metric frame is
  therefore the world frame translated by -x of the route's first waypoint. For route 18305 that is -1176.6 m, which
  is the observed offset; on Town13 (lat_0 = 41.09, lon_0 = -81.59) the full chain applies. The agent controls with
  relative transforms, so its driving is unaffected. The realized-validity evaluation (`realized.py`, default `true`)
  anchors plans with the true pose and is unaffected. Only the criterion's reference frame was wrong.
* Change. `check_smoke.py` maps the true LiDAR position through `framelease_v4/arms/agent_frame.py`, the verbatim
  official equations (`init()` fsolve, `gps_to_location`) and the leaderboard's `_location_to_gps` with the map's
  geoReference. It then applies the registered version-1.2 thresholds unchanged. The raw world-frame offset and the
  frame summary are reported, not judged.
* Independent check before the change. With the official chain, route 18305's translation is (-1176.6, 0.0) m at
  every point. Mapping the true pose of the 7 smoke logs gives offset p50 1.530-1.558 m and p95 2.415-2.446 m: the
  1.4 m GNSS lever arm plus noise. The correction comes from the official code, the map file and the routes XML,
  not from the smoke data.
* Files. New: `framelease_v4/arms/agent_frame.py` (sha256 `e0264cbb5acb588fa01e00115da6ba9914b74a86dbb880dd1dade31c6223d4cd`), `framelease_v4/arms/tests/test_agent_frame.py`
  (`82e7f037d56a1b0de92f42f10d3d0cadc4d691aea0c63b28226c20e0b105e407`). Changed: `framelease_v4/protocol/check_smoke.py` (`bf8287d0867a4c4f84fcab12ed7a05527fc0fbc6936aa01d05f9402883ca9948`), `framelease_v4/protocol/tests/test_check_smoke.py`
  (`4866b4ce3799c9ca1202d2f220717e971085f5bc06fbf0eb6acb86835f11866c`; synthetic estimates now live in the agent frame, and three new failure cases are added). No file pinned by
  a job line changes, and no job file changes.
* Tests. 146 passed and 17 skipped without the official stack; 163 passed with it
  (`outputs/framelease_v4/amendment_a1/pytest_isolated.log` `fd031da3a256cb7a6c6e00f6c12a1c63b127359940cce18089ab6f8b8bbf7e94`, `pytest_official.log` `ebd762c90f8b2c5330847596909157d11e394c5118d0c9443b6236c5d25f0df3`).
* Runs. As Sec. 8.1 requires after a FAIL, the smoke block runs again unchanged (same job file) in a fresh queue,
  `outputs/framelease_v4/queue_p1_smoke2`; its report is entered below. P1 starts only after a PASS and uses
  `queue_p1`. The version-1.2 registration files are kept in `outputs/framelease_v4/registration/v1.2/`.
* Manifest and seal: `outputs/framelease_v4/registration/MANIFEST.sha256`, 146 files, sha256 `4d14ab0ec454fc101387c9ba4fb72eb659cecb975832837f20b3e39072f07585`, sealed with this
  entry in `SEAL.sha256` (`registration.py --seal`).

**Smoke report 2, 2026-11-11 12:28 (Beijing time): PASS.** `outputs/framelease_v4/smoke_p1_0/smoke_check_attempt2_PASS.json`
(sha256 `08c40e615415290ad8af498fd754ef07343b9370b94653c2295011e9ede32d68`). Queue `outputs/framelease_v4/queue_p1_smoke2`,
same job file `b00_smoke.jsonl`, 7 of 7 runs final, every criterion passed on every run. The checker was the
amendment-A1 version, registered before this re-run. `pose_offset` in the agent frame: p50 1.521-1.563 m, p95
2.400-2.448 m; raw world-frame offset 1176.6-1176.7 m (reported). The report 1 file was not overwritten
(`--report`). P1 may start (Sec. 8.1).

**Operational addition, 2026-11-11 (no effect on any run or criterion).** `framelease_v4/protocol/autoresume.sh`
(sha256 `5e697b51b2b0a001d23d83e7e513a673f5d19ed127a9920a254334c8af8fc96c`) resumes listed queues after a reboot through `launch_queue.sh`. It acts only while
`outputs/framelease_v4/AUTORESUME` exists and only if the user installs its `@reboot` crontab line. Installing it is
the user's decision; it was not installed by the registering session.
* Manifest and seal after this addition: `MANIFEST.sha256`, 147 files, sha256 `094f085ca8358d307a2ad4535d35a63ea5fb40b6ed1d8916250f261f783d55af`, sealed with this entry.

**Operational addition, 2026-11-11 13:55 (Beijing time): the P1 stage driver (no effect on any run or criterion).**
`framelease_v4/protocol/p1_driver.py` (sha256 `e881692e40db20786bf5a821f113d0554edd3db47b0633ef3a94821208cdebcb`) carries out steps 4 and 5 of
`outputs/framelease_v4/p1_jobs/README.md` for FULL as registered (Secs. 4.2, 4.8, 4.9, 8.1). When a stage is final it
runs `select_stage.py --write` once and records the selection below under "Stage selections (P1, FULL)" (entry,
re-seal, verify) before the next block is generated with `p1_jobs.py --check --write`; it then copies that block into
`queue_p1/jobs.d`. After `age_s2` and `event_s2` it records the tuning freeze and, when every P1 job is final, the D1
summary, and stops; D1 stays the user's decision. It starts the runner only through `launch_queue.sh`, at nice 0, and
never after a runner error, a circuit-breaker exit or a signal exit, or while a queue STOP file exists. It changes no
selection rule, candidate grid, route set or criterion. Any failure or FLAG stops it with
`outputs/framelease_v4/p1_driver/ALERT.txt`. A registered file that differs from the sealed manifest, before or during a
re-seal, stops it; a change of an unregistered `framelease_v4` file (code in development) between seals is named in the
next entry. `framelease_v4/protocol/start_p1_driver.sh` (`e73e1872ed943b21991bdb4e0e22c3e5395cb49358aa54a14c576889bf4aff93`) starts it detached.
* Tests. `framelease_v4/protocol/tests/test_p1_driver.py` (`370ba8cbff06722c6908a4545e786cdb78ecd31ec2cff0e045cca825ae495517`): 17 tests passed, among them a registered file
  changed between the pre-check and `--write-manifest` (stopped, nothing sealed) and a runner stopped by a signal (not
  relaunched). All protocol tests: 54 passed, 1 skipped (`outputs/framelease_v4/p1_driver/pytest_protocol_tests_after_F1_F2.log`,
  `61433aa136b2397c67e79b17ac96d5a5580b0ce92498ebe590e3a7db3c1f7fa5`). `framelease_v4/protocol/tests/test_d1_summary.py` (`3c661a098167683d5ca9e44921a17e52e3c8d70eb3fda1221086807276560815`) changes in its fixture only: the
  existing-runs guard of `p1_jobs.write_block` now looks under the test's temporary root instead of the project
  outputs, which hold P1 runs. No file pinned by a job line changes, and no job file changes. These files are
  registered from this entry on; a change of them is an amendment.
* Manifest and seal after this addition: `MANIFEST.sha256`, 151 files, sha256 `a48d2eeb5af7aeafa8f4d90cc291dd7c456a57d10ff14e4ec63f7dbccb9bf4f8`, sealed with this entry.

**Amendment A2, 2026-11-11 15:23 (Beijing time): the realized-validity keys of `metrics_v4.run_metrics` (no effect on any
run, job file, selection or criterion).**
* Cause. `realized.realized_validity` returns `realized_invalid_ticks` and `realized_invalid_tick_ratio` with the
  prefix already in the name, and `run_metrics` prefixed every key again (`realized_realized_*`). The two readers of
  `realized_invalid_tick_ratio`, `metrics_v4.arm_summary` and the EIR column of `framelease_v4/protocol/d1_summary.py`
  (Sec. 4.8), therefore always read None. The defect was found while the P7 aggregator was built.
* Change. `framelease_v4/arms/metrics_v4.py` (sha256 `4c4b17dbfc6eeefae0282f773450dde2e97d8eb1da71554d8b611e7d9df098b4`) keeps the name of a key that already carries
  the prefix; every other key stays `realized_<key>`. New regression test
  `framelease_v4/arms/tests/test_metrics_realized_keys.py` (`1953e2ddd09ae9affac430196b877f3af5f8743a3897e864c04c2cae2e313c6f`): the per-run row, `arm_summary` and the
  D1 EIR equal the values of `realized_validity`; the test fails on the previous version.
* Scope. `metrics_v4.py` is analysis code: no job line pins it, and no agent, launcher or runtime module imports it.
  Stage selections use the mean DS over the kept routes (Sec. 4.2) and never read these keys. R_cond
  (`realized_conflict_plans`, `realized_misses`) was not affected. No run, job file or selection changes; the D1
  summary written at the end of P1 reports EIR as Sec. 4.8 defines it.
* Tests. 48 passed, 13 skipped in 6.26s (`outputs/framelease_v4/amendment_a2/pytest.log`, `22ddb595e82b4ec50f5db8234d260c2a5e8139b8b0edc0adaaed1e3ce5832030`). The manifest also lists 21 new files under `framelease_v4/` that this entry does not register (tooling for Phases 2-7 in development): `framelease_v4/analysis/__init__.py`, `framelease_v4/arms_ext/__init__.py`, `framelease_v4/arms_ext/agent_ext.py`, `framelease_v4/arms_ext/arms_ext.py`, `framelease_v4/arms_ext/global_shield.py`, `framelease_v4/arms_ext/run_closed_loop_ext.py`, `framelease_v4/arms_ext/tests/helpers_ext.py`, `framelease_v4/arms_ext/tests/test_agent_ext.py`, `framelease_v4/arms_ext/tests/test_arms_ext.py`, `framelease_v4/arms_ext/tests/test_global_shield.py`, `framelease_v4/arms_ext/tests/test_launcher_ext.py`, `framelease_v4/protocol/check_smoke_ext.py`, `framelease_v4/protocol/p2_check.py`, `framelease_v4/protocol/p2_jobs.py`, `framelease_v4/protocol/p3_rl.py`, `framelease_v4/protocol/stress_bench.py`, `framelease_v4/protocol/tests/test_check_smoke_ext.py`, `framelease_v4/protocol/tests/test_fl_full_qnet_agent.py`, `framelease_v4/protocol/tests/test_p2_check.py`, `framelease_v4/protocol/tests/test_p2_jobs.py`, `framelease_v4/protocol/tests/test_stress_bench.py`.
* Manifest and seal after this amendment: `MANIFEST.sha256`, 173 files, sha256 `394a825e4b768e5c977f63ff60cc7ea75eadffcbdeec145eae79835f99de7b15`, sealed with this entry.

**Amendment A6, 2026-11-14 03:54 (Beijing time): `framelease_v4/rl/ope.py`: a candidate whose training fold cannot fit it
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
  `dace32b90d3f7bcc636b1a285bf1a255cad9d8e9983e542b98bb6dbee586fac8`), `framelease_v4/rl/RL_PROTOCOL.md`
  (`27f0ecebdcb0ec0431c84a0659f0a748b07544900e5f7547d0fcb5c53ec4e8a3` -> `c12b935b740494fda4c54d6c162d7d8776a0a29bfe84e5b3ec14b482d1bf2557`).
  New: `framelease_v4/rl/tests/test_ope_support.py` (`53b9b4c47095bad992a37c3f1e1a3012edd2307cf5ba1998d86e32ce48d76175`).
  The installed files equal the staged copies `outputs/framelease_v4/build/AMEND/staged/{ope.py,RL_PROTOCOL.md,
  test_ope_support.py}` (unified diffs `ope.patch`, `RL_PROTOCOL.patch`).
* Tests.
  * Regression test `test_ope_support.py` (8 tests, 189 subtests), run in an overlay copy of the tree (every
    project-root entry a symlink to the tree except a copied `framelease_v4/`; `outputs/` a directory of symlinks):
    with the registered `ope.py` 4 failed, 4 passed (`fit_support` missing, twice; the ValueError of
    `trainers._check_default_support`, twice; the split-guard test passes, as the registered guard is kept;
    `staged/logs/pytest_ope_support_registered.log`,
    `c466acc768b9a805697ced427cebadf507c258da783a5e5e90d5925260b3a3fb`); with the fixed
    `ope.py` 8 passed (`staged/logs/pytest_ope_support_patched.log`,
    `979fcb5981daa271d0da11a10c691a84e9818c8acab6c31b415f9d2463a95f5c`). Its tests: the tree's
    own `ope.py` is tested; `fit_support` is false exactly when `fit_candidate` raises, on 180 random folds of the
    three families; the fold record; every family of the smoke grid at d* = 4 completes with each candidate
    unsupported in the fold that lacks REFRESH samples and fitted in every other fold; a family continues and selects
    the candidate whose `min_support` the fold meets; a non-training episode among the fit episodes raises the
    PermissionError of `fit_candidate` in every family although no fold is fitted; a supported selection keeps the
    registered fold records; any other ValueError of a fit still stops the selection.
  * Registered against fixed `select` (`staged/compare_supported.py`, output `staged/compare_supported.out.json`,
    `b2458a3ff78735c20cac80d3f9f63352d596ab3ab9a39a1d766c2f3fbfc90049`): 18 cases, the 15 supported
    ones byte-identical, the 3 pilot cases at d* = 4 ValueError (registered) and complete reports with `selected` None
    (fixed).
  * At application (logs in `outputs/framelease_v4/amendment_a6/`): `framelease_v4/rl/tests`,
    59 passed, 3 skipped, 189 subtests passed in 15.86s (`pytest_rl.log`,
    `6fb096d95a5187bef95d2aa9fd23f552126f20558e064def17438a6dbabf43e3`; at staging 59 passed, 3 skipped without the
    official stack, 189 subtests).
  * The unchanged driver with the fixed `ope.py`, in the overlay copy: `test_p3_rl.py` gives 37 passed and 3 failed,
    namely the pinned ValueError path and two path checks that fail only in the overlay copy
    (`staged/logs/pytest_p3_rl_overlay_patched.log`,
    `f7f9161a874ca3825bf9295e69d6aa7465c6423fa53008cc7e81b9264fd009ae`); the development
    run at d* = 4 stops at open case (a) with exit 4 (`staged/logs/p3_rl_dev_dstar4_overlay_patched.log`,
    `26543b1729a58ebe5bb52763387bf6a4f70ea906b0ef4f2a69d1cf07a0c4b6ba`).
* Manifest and seal after this amendment: `MANIFEST.sha256`, 190 files, sha256
  `f5eb50eb21a77d193361c2fc3ff4865cc3f8b2dd4d169ee1802ea06dd19768de`, sealed with this entry.

**Amendment A5, 2026-11-14 05:13 (Beijing time): the overrun-disable rule of the Q-network utility, stated as the
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
* Files. `framelease_v4/rl/qnet.py`, unchanged: `53bbf8c69124519c6bb2133961695aa4f238c6d52e325f0d8e7de53008d23f3f` (must equal the registered and
  pinned `53bbf8c69124519c6bb2133961695aa4f238c6d52e325f0d8e7de53008d23f3f`); the replaying checker
  `framelease_v4/protocol/check_smoke_ext.py` (registered by Amendment A3, which cites its sha256).
* Tests.
  `framelease_v4/protocol/tests/test_check_smoke_ext.py::ReviewFixesTest::test_sf4_disable_rule_is_replayed_exactly`
  (nine overrun patterns on rows of the pinned `QUtility`; the integer form floor(m / 20) + 1 for every m in
  64..256) and the three tests of `ProtocolTextTest` in `outputs/framelease_v4/build/QNET/review/test_review_qnet.py`
  (`6d2649992cc82987062bf5cafce4a5a3d29f2ceae343358fb364023ece4b596c`; no disable before call 64; 12 versus 13
  overruns of 256; the denominator below 256 calls): 4 passed
  (`outputs/framelease_v4/amendment_a5/pytest_disable_rule.log`,
  `078d85db7cd5a4c8d82b990d03e9b277bf136be0ca42c0f56926ef0784dac1fc`; at drafting 4 passed in 0.66 s,
  `outputs/framelease_v4/build/AMEND/a5_disable_rule_tests.log`).
* Manifest and seal after this amendment: `MANIFEST.sha256`, 193 files, sha256
  `bb88e2f6f7118174b3669088c4afc21b76e630ca691b97b80a122100268b1606`, sealed with this entry.

**Amendment A8, 2026-11-14 05:15 (Beijing time): background load and memory during P1, their countermeasures, the pause of
2026-11-11 15:36-23:39 and the stop of 2026-11-12 03:40 (Secs. 2.3, 8.4, 9.7, 11.2 item 3; no run repeated or excluded,
no selection rule changed).**
* Cause. The runtime charges the measured CPU time of every scheduler boundary and the measured CUDA-event time of the
  prefix to the simulated timeline (Sec. 2.3), so load from other processes inflates the charged times (threat 11.2
  item 3). Background load on 2026-11-11: 13:20-13:45 the review of the P1 stage driver (tests); 13:59-15:20 the builds
  and reviews of the Phase 2-7 tooling (tests at nice 19 on every core); from about 15:21 a CPU-bound platform of
  another project on the same machine. Measured per run (`summary.json` `prefix_cost_s`; table in
  `outputs/framelease_v4/validity_notes/background_load_20261111.md`), kappa 1.0, by start time: 12:29-13:22, 16 runs,
  prefix p50 0.4161-0.4221 s (median 0.4176 s); 13:25, 0.4246 s; 13:29-15:00, 12 runs, 0.4257-0.4760 s, p95 up to
  0.5334 s (the largest p50, Fast Only at 14:42, is 14% above the idle median); 15:07 and 15:13, while the builds
  paused, 0.4242 s and 0.4210 s; 15:16-15:28, 4 runs, 0.4270-0.4635 s. Every run stayed inside the Sec. 9.7 band
  kappa x [0.35, 0.60] s.
* Countermeasures, from 15:35 on 2026-11-11. No concurrent build of the tooling; every CPU process of the work that
  runs while a closed-loop job runs is pinned to the E-cores 12-15 (`taskset -c 12-15`), at nice 19 and idle I/O class,
  one process at a time, with one BLAS thread and, from 2026-11-14, under 1.5 GB of memory. The runner, the disk
  watchdog and the P1 stage driver keep nice 0. With these rules the 25 runs started 2026-11-11 23:39 to
  2026-11-12 02:58 measured a prefix p50 of 0.4170-0.4204 s while one pinned build process ran, and the 8 runs
  started 2026-11-14 03:50-04:44 measured 0.4162-0.4244 s.
* The pause. On the user's instruction (translated: "pause DAC first; let CSMH finish running, then I will tell
  you"; CSMH is the other project's platform), the P1 stage driver stopped at 15:36:33
  (`outputs/framelease_v4/p1_driver/STOP`) and the runner was stopped by SIGTERM at 15:36:37 (exit 4). At that time
  42 jobs of `queue_p1` were final (the 7 P1-0 smoke jobs and 35 `ref` jobs) and 86 were pending. The running job
  `v4p1_fixed_deep_k1.0_s11_r28093` (attempt 1, run directory `tuning/ref/fixed_deep/runs/20261111T073306_dbd64835`)
  ended with "runner received signal 15" and was not counted: it used no retry (Sec. 8.4), the stage selection never
  uses an uncounted attempt (Sec. 4.2), and the aggregator never selects it (R-1) but audits its commits (R-2). On the
  user's word, P1 resumed at 23:39 after these checks: no process of the other project and no CARLA process alive,
  the GPU free; the CARLA install used by P1 (`/home/kang/opt/CARLA_0.9.15` -> `/opt/csmh-joint-runtime/carla`)
  unchanged, the symlink intact and the 22 files of
  `outputs/framelease_v4/validity_notes/carla_fingerprint_20261111.sha256` (written at the pause) verified with
  `sha256sum -c`; `registration.py --verify` both seals OK. The STOP file was kept
  as `outputs/framelease_v4/p1_driver/STOP.20261111_pause.resolved.txt`. The runner restarted the interrupted job as
  attempt 2, final at 23:46:24 (counted; prefix p50 0.4193 s).
* The stop of 2026-11-12 03:40 (`outputs/framelease_v4/validity_notes/oom_20261112.md`, from the kernel journal). At
  03:40:41 a global out-of-memory condition made the kernel kill the evaluator of the running job
  `v4p1_fl_heuristic_E10_d10_k1.0_s11_r3514` (attempt 1; 12.96 GB resident; CARLA held 10.43 GB on that route; 28.3 GB
  of 30.4 GB resident in total). The runner and the P1 stage driver had been started from a shell of the editor's
  systemd scope, whose default OOM policy stopped the whole scope: the runner ended by SIGTERM (exit 4) and the driver
  stopped. The runner recorded the killed attempt as `infra_failure` (exit -15), counted: it used the single
  infrastructure retry of Sec. 8.4, and attempt 2 became final on 2026-11-14 04:02:51 with a valid record. No run
  started between 03:40 on 2026-11-12 and 03:50 on 2026-11-14 (the machine was off from 09:52 on 2026-11-12 to 03:41 on
  2026-11-14). P1 resumed at 03:50 after the checks of the pause (CARLA fingerprint verified, seals OK). The 5 runs
  started 2026-11-12 02:59-03:36, the last before the stop, measured a prefix p50 of 0.4316-0.4328 s, at most 0.0068 s
  above the idle band below; memory was close to exhaustion at 03:40.
* Isolation, from 2026-11-14 05:11. The runner (with its disk watchdog and job processes) and the P1 stage driver run
  in dedicated systemd user scopes with `OOMPolicy=continue` (`outputs/framelease_v4/paper_tools/relaunch_isolated.sh`,
  `bba05b8744f24630275ef8a16123615964076b22dc9b96a205e96a4215a9b81f`; log `relaunch_isolated.log`,
  `367925be588a07ef63a415df9f3db292a85f084c3ecb7de41d0fbbbb7101899e`): an OOM kill then ends only the killed process
  and the runner applies Sec. 8.4. The move waited for the running job to finish (queue STOP, runner exit 'STOP file',
  no attempt lost); every later runner of this work starts the same way.
* Background-load flag (aggregator R-3, `framelease_v4/analysis/manipulation.py`). Every run's charged prefix p50 is
  compared with the idle band kappa x [0.416, 0.426] s, the pilot range of Sec. 9.7 (registered before P1; the 16
  runs of 2026-11-11 12:29-13:22 lie inside it): `bg_load_status` within, above or below, and `bg_load_excess_s`,
  reported per run and per protocol arm and kappa. The flag is reported, never used to exclude a run or a route: the
  analysis population and the contrasts stay those of Secs. 9.1 and 9.8. Of the 73 P1 runs started up to 2026-11-14
  04:44, 20 are above the band (8 Fixed Deep and 7 Fast Only of the block `ref`; 2 E5, 2 E10 and 1 B0 of the stage
  `lease_s1`) and none below.
* In-place text, Sec. 11.2 item 3, the last sentence ("The runner records GPU samples; CPU load is reported from the
  run logs where available."), replaced by (Amendment A8): "The runner records GPU samples. CPU load is measured: every
  run's charged prefix p50 is compared with the idle band kappa x [0.416, 0.426] s (the pilot range of Sec. 9.7) and
  flagged, never excluded (Amendment A8)."
* Scope. The P1 `ref` block (the untuned references, reported for context, never selected; Sec. 4.8) and 5 runs of the
  stage `lease_s1`, spread over all three candidates, were measured above the band. No run is repeated, excluded or
  reweighted, and no selection rule, criterion or job file changes: the `lease_s1` selection uses the mean DS over the
  kept routes as registered (Sec. 4.2). Table I, Fig. 3 and the training-route operating-point table report the flag
  counts per arm; the paper states the threat with these numbers.
* Files. `outputs/framelease_v4/validity_notes/background_load_20261111.md`
  (`957c7633c3b5f9882bfab451e6f3b39f1651063c5d638bc9f6cd18c11e7abb28`),
  `outputs/framelease_v4/validity_notes/carla_fingerprint_20261111.sha256`
  (`80285726ea7d95b5b1c11af7b97c6a21bb2f549af6ccfaf62373c80042faa598`),
  `outputs/framelease_v4/validity_notes/oom_20261112.md` (`fd6f1f685b2c522204c62edebbc0989767b6b7fa45d53f8b4f95a4b0662599dd`),
  `outputs/framelease_v4/p1_driver/STOP.20261111_pause.resolved.txt`
  (`81e31322daf670eb7acb92d1dade6dc051dbde91d89727eea51f47c7a8950cf0`), the runner's records of the attempts
  named above (`outputs/framelease_v4/queue_p1/status.jsonl`); the flag is computed by
  `framelease_v4/analysis/manipulation.py` (registered by Amendment A3, which cites its sha256).
* Tests. `framelease_v4/analysis/tests/test_manipulation.py` (the band check with the edges 0.416 s and 0.426 s and
  its "reported, never excluded" rule): 11 passed, 33 subtests passed in 0.17s
  (`outputs/framelease_v4/amendment_a8/pytest_manipulation.log`,
  `925f93216b2b9c4696d4a8645da5da96ce8d9c2104c52526dadb229ffb8db88e`).
* Manifest and seal after this amendment: `MANIFEST.sha256`, 193 files, sha256
  `52319cbea3a4a8e84a8b169752c3a4b2c0fe2830f1e7bbc8bf97bc47807245a4`, sealed with this entry.

**Stage selections (P1, FULL).**
* **lease_s1**, 2026-11-14 06:06 (Beijing time). Selection `outputs/framelease_v4/tuning/selection/FULL/lease_s1.json`
  (sha256 `f23a6522c28aedc27b02494521cb763331fbf3097b8114b8ece8cd83021fa261`), written 2026-11-14T06:06:08+0800 by
  `select_stage.py --variant FULL --stage lease_s1 --queue outputs/framelease_v4/queue_p1 --write` for the job file
  `outputs/framelease_v4/p1_jobs/FULL/b02_lease_s1.jsonl` (sha256
  `24223de6aa8998b80df23dfbe17369c18c22f82fc55f825442424b5c9bf268e7`); 10 of 11 routes kept (dropped: 23659). Mean DS
  over the kept routes: `E5` 44.3 (n 10); `E10` 35.3 (n 10); `B0` 52.4 (n 10). Survivors (top 2): `E5`, `B0`. The
  `lease_s2` block is generated from this selection after this entry. Manifest and seal: `MANIFEST.sha256`, 193 files;
  changed since the previous seal (not registered files): `framelease_v4/protocol/phase_driver.py`,
  `framelease_v4/protocol/start_phase_driver.sh`, `framelease_v4/protocol/tests/test_phase_driver.py`, sha256
  `4669940551d242e060bf13cd4acbce8d411b012086c0fcc1b4dd9ff080e80662`, sealed with this entry.
* **event_s1**, 2026-11-14 09:41 (Beijing time). Selection `outputs/framelease_v4/tuning/selection/FULL/event_s1.json`
  (sha256 `b66a83c6c5d1b4e7ee6db23a6eaa942276ce7fcf3e89c9d0736c4002f61cfc0f`), written 2026-11-14T09:41:33+0800 by
  `select_stage.py --variant FULL --stage event_s1 --queue outputs/framelease_v4/queue_p1 --write` for the job file
  `outputs/framelease_v4/p1_jobs/FULL/b03_event_s1.jsonl` (sha256
  `a80b7b6c206bcaa8b7b673229ebd1fb5a9423b2bbc22e86558b64305ee8285e1`); 11 of 11 routes kept. Mean DS over the kept
  routes: `v2_hb2.0` 56.3 (n 11); `v2_hb1.0` 60.5 (n 11); `s_hb2.0` 63.0 (n 11); `s_hb1.0` 61.4 (n 11). Survivors (top
  2): `s_hb2.0`, `s_hb1.0`. The `event_s2` block is generated from this selection after this entry. Manifest and seal:
  `MANIFEST.sha256`, 202 files; new in it: `framelease_v4/analysis/analyze_v4.py`,
  `framelease_v4/analysis/figures_tables.py`, `framelease_v4/analysis/prop1_coverage.py`,
  `framelease_v4/analysis/tests/test_analyze_v4.py`, `framelease_v4/analysis/tests/test_figures_tables.py`,
  `framelease_v4/analysis/tests/test_prop1_coverage.py`, `outputs/framelease_v4/p1_jobs/FULL/b04_lease_s2.check.json`,
  `outputs/framelease_v4/p1_jobs/FULL/b04_lease_s2.jsonl`, `outputs/framelease_v4/p1_jobs/FULL/b04_lease_s2.stage.json`;
  changed since the previous seal (not registered files): `framelease_v4/protocol/phase_driver.py`,
  `framelease_v4/protocol/tests/test_phase_driver.py`, sha256
  `82603bb5fb17349916db8f4f5204db73be79c5f7dc9764a24f188ccaaa5ff386`, sealed with this entry.
* **lease_s2**, 2026-11-14 12:57 (Beijing time). Selection `outputs/framelease_v4/tuning/selection/FULL/lease_s2.json`
  (sha256 `bc2f7299f438309d99ddfb6017ab86d1593e996247e50456c51b747e0a332351`), written 2026-11-14T12:56:58+0800 by
  `select_stage.py --variant FULL --stage lease_s2 --queue outputs/framelease_v4/queue_p1 --write` for the job file
  `outputs/framelease_v4/p1_jobs/FULL/b04_lease_s2.jsonl` (sha256
  `54cfb8ede715928f11b7d599069f0724c0a1a0c8754b74471cbf0b04a0cd7465`); 11 of 11 routes kept. Mean DS over the kept
  routes: `E5` 37.6 (n 11), over T22 40.8 (n 21); `B0` 47.8 (n 11), over T22 50.0 (n 21). Selected: `B0`. The `heur_s1`
  block is generated from this selection after this entry. Manifest and seal: `MANIFEST.sha256`, 207 files; new in it:
  `framelease_v4/analysis/tests/test_verify_independent.py`, `framelease_v4/analysis/verify_independent.py`,
  `outputs/framelease_v4/p1_jobs/FULL/b05_event_s2.check.json`, `outputs/framelease_v4/p1_jobs/FULL/b05_event_s2.jsonl`,
  `outputs/framelease_v4/p1_jobs/FULL/b05_event_s2.stage.json`; changed since the previous seal (not registered files):
  `framelease_v4/analysis/figures_tables.py`, `framelease_v4/analysis/tests/test_figures_tables.py`, sha256
  `e24d18cc66e2ec6f75af2cb0b45ea55128ea60529b41db34cbbf8135837a45f5`, sealed with this entry.
* **event_s2**, 2026-11-14 14:47 (Beijing time). Selection `outputs/framelease_v4/tuning/selection/FULL/event_s2.json`
  (sha256 `682a8e0560a388047fb89c4e77ce4f51869e5e23342ffa0ecfa829c5451ec659`), written 2026-11-14T14:47:21+0800 by
  `select_stage.py --variant FULL --stage event_s2 --queue outputs/framelease_v4/queue_p1 --write` for the job file
  `outputs/framelease_v4/p1_jobs/FULL/b05_event_s2.jsonl` (sha256
  `779badf855ef6929fbdb148637bfcd17b233111098046ae41d21215f4ba44bd2`); 11 of 11 routes kept. Mean DS over the kept
  routes: `s_hb2.0` 60.3 (n 11), over T22 61.6 (n 22); `s_hb1.0` 56.5 (n 11), over T22 58.9 (n 22). Selected: `s_hb2.0`.
  Final stage of the event grid. Manifest and seal: `MANIFEST.sha256`, 211 files; new in it:
  `framelease_v4/analysis/verify_table1_extra.py`, `outputs/framelease_v4/p1_jobs/FULL/b06_heur_s1.check.json`,
  `outputs/framelease_v4/p1_jobs/FULL/b06_heur_s1.jsonl`, `outputs/framelease_v4/p1_jobs/FULL/b06_heur_s1.stage.json`;
  changed since the previous seal (not registered files): `framelease_v4/analysis/aggregate_v4.py`,
  `framelease_v4/analysis/commit_audit.py`, `framelease_v4/analysis/tests/test_aggregate_v4.py`,
  `framelease_v4/analysis/tests/test_commit_audit.py`, sha256
  `6635379d00de306a2bffd3e2100fd13bf8029f912c20972f87953ddb4e8af53a`, sealed with this entry.
* **heur_s1**, 2026-11-14 23:40 (Beijing time). Selection `outputs/framelease_v4/tuning/selection/FULL/heur_s1.json`
  (sha256 `03d1145dba118b22806a0246fbca35d41338a815a9e9cb9f8d4d79ca2e230914`), written 2026-11-14T23:40:27+0800 by
  `select_stage.py --variant FULL --stage heur_s1 --queue outputs/framelease_v4/queue_p1 --write` for the job file
  `outputs/framelease_v4/p1_jobs/FULL/b06_heur_s1.jsonl` (sha256
  `57711230b7c3ca45a065d22c1e2babef36a21c86dd648937785c5e7936ac7cba`); 10 of 11 routes kept (dropped: 23659). Mean DS
  over the kept routes: `d10` 52.4 (n 10); `d4` 50.0 (n 10); `d1` 65.0 (n 10). Survivors (top 2): `d10`, `d1`. The
  `heur_s2` block is generated from this selection after this entry. Manifest and seal: `MANIFEST.sha256`, 212 files;
  new in it: `framelease_v4/analysis/tests/test_verify_table1_extra.py`; changed since the previous seal (not registered
  files): `framelease_v4/analysis/verify_table1_extra.py`, sha256
  `554e6f89fa3d5ebfa39335f4d99e475a2c16a3c089c207a0a6f59e70a13bb0b7`, sealed with this entry.
* **heur_s2**, 2026-11-15 01:05 (Beijing time). Selection `outputs/framelease_v4/tuning/selection/FULL/heur_s2.json`
  (sha256 `ca497c268b94cd18b19cbd5fd36ba174a3e86bdd739695c7954de948c919ac4d`), written 2026-11-15T01:05:46+0800 by
  `select_stage.py --variant FULL --stage heur_s2 --queue outputs/framelease_v4/queue_p1 --write` for the job file
  `outputs/framelease_v4/p1_jobs/FULL/b07_heur_s2.jsonl` (sha256
  `9eb9b7b8bacaaeb27e2f24f99a83644676b0184756847a22f3263b3374c9a14c`); 11 of 11 routes kept. Mean DS over the kept
  routes: `d10` 47.8 (n 11), over T22 50.0 (n 21); `d1` 49.9 (n 11), over T22 57.1 (n 21). Selected: `d1`. The `age_s1`
  block is generated from this selection after this entry. Manifest and seal: `MANIFEST.sha256`, 215 files; new in it:
  `outputs/framelease_v4/p1_jobs/FULL/b07_heur_s2.check.json`, `outputs/framelease_v4/p1_jobs/FULL/b07_heur_s2.jsonl`,
  `outputs/framelease_v4/p1_jobs/FULL/b07_heur_s2.stage.json`; changed since the previous seal (not registered files):
  `framelease_v4/analysis/tests/test_verify_table1_extra.py`, `framelease_v4/analysis/verify_table1_extra.py`, sha256
  `fdebe7a4935aed4b5cfb47a436a568c4c1e0ec9dd11f71c58f3f8c954dfee605`, sealed with this entry.
* **age_s1**, 2026-11-15 04:21 (Beijing time). Selection `outputs/framelease_v4/tuning/selection/FULL/age_s1.json`
  (sha256 `88fa28271484e92758978b5b1ddcdeba42567fa1a7979715eedddc5bad31acdc`), written 2026-11-15T04:21:15+0800 by
  `select_stage.py --variant FULL --stage age_s1 --queue outputs/framelease_v4/queue_p1 --write` for the job file
  `outputs/framelease_v4/p1_jobs/FULL/b08_age_s1.jsonl` (sha256
  `1cb6404a9c147ae60ad29fee9125222a9089efb7a2b15e11dddf3a414785b5a2`); 11 of 11 routes kept. Mean DS over the kept
  routes: `A1.0` 67.8 (n 11); `A1.5` 63.3 (n 11); `A2.0` 63.2 (n 11); `A2.5` 63.6 (n 11). Survivors (top 2): `A1.0`,
  `A2.5`. The `age_s2` block is generated from this selection after this entry. Manifest and seal: `MANIFEST.sha256`,
  218 files; new in it: `outputs/framelease_v4/p1_jobs/FULL/b08_age_s1.check.json`,
  `outputs/framelease_v4/p1_jobs/FULL/b08_age_s1.jsonl`, `outputs/framelease_v4/p1_jobs/FULL/b08_age_s1.stage.json`;
  changed since the previous seal (not registered files): `framelease_v4/analysis/tests/test_verify_table1_extra.py`,
  `framelease_v4/analysis/verify_table1_extra.py`, sha256
  `4e424763c5cea4c30641e47bac351db292febc937832523d09065e0af53b18e3`, sealed with this entry.
* **age_s2**, 2026-11-15 06:36 (Beijing time). Selection `outputs/framelease_v4/tuning/selection/FULL/age_s2.json`
  (sha256 `b79b9440bde4b8f1c4fad1d7bcfb41fe88f3995fd0eb501084bd38c5e178b355`), written 2026-11-15T06:36:37+0800 by
  `select_stage.py --variant FULL --stage age_s2 --queue outputs/framelease_v4/queue_p1 --write` for the job file
  `outputs/framelease_v4/p1_jobs/FULL/b09_age_s2.jsonl` (sha256
  `8a1dd8879dd5a2f8db14e61b624eeeebc39cd4d19e2869dc569fb95b79e31efd`); 11 of 11 routes kept. Mean DS over the kept
  routes: `A1.0` 60.2 (n 11), over T22 64.0 (n 22); `A2.5` 52.7 (n 11), over T22 58.1 (n 22). Selected: `A1.0`. Final
  stage of the age grid. Manifest and seal: `MANIFEST.sha256`, 221 files; new in it:
  `outputs/framelease_v4/p1_jobs/FULL/b09_age_s2.check.json`, `outputs/framelease_v4/p1_jobs/FULL/b09_age_s2.jsonl`,
  `outputs/framelease_v4/p1_jobs/FULL/b09_age_s2.stage.json`, sha256
  `4bfe7451a41b853042f181cbcd7c326649b4222279bc35dd9787afa38c8d4033`, sealed with this entry.
* **Tuning freeze**, 2026-11-15 06:36 (Beijing time). `outputs/framelease_v4/tuning/selection.json` (sha256
  `652fcbdbf0a6adb498aa0691fcaaffb097fcd680b4bf40235a28639aed69b930`), written 2026-11-15T06:36:48+0800 by
  `select_stage.py --variant FULL --freeze --write` from the eight stage selections above (Sec. 4.9): L* = `B0`
  (`outputs/framelease_v4/envelopes/B0.json`, sha256 `9ef8479f04dab873d22b50e8732176804ed67f351f17584355b241e424fa1927`,
  validity std); d* = 1 (utility `v4_adet_d1`); A* = 1.0 s; Event-Triggered `s_hb2.0` (theta* = s, A_hb* = 2.0 s);
  fl_risk: lease point `E5` (L* = B0: fl_risk runs the better of E5 / E10 by mean DS on lease_s1 (T22a), ties earlier).
  Manifest and seal: `MANIFEST.sha256`, 221 files, sha256
  `4bfe7451a41b853042f181cbcd7c326649b4222279bc35dd9787afa38c8d4033`, sealed with this entry.
* **D1 summary**, 2026-11-15 06:38 (Beijing time). `outputs/framelease_v4/tuning/d1/FULL_d1_summary.json` (sha256
  `d8c0a76eba80c0c5d4faf93346146ff3db59d162d27636c2411cd206a09a2fb3`) and
  `outputs/framelease_v4/tuning/d1/FULL_d1_summary.md` (sha256
  `c53d08903830001d20656853205b5b48546924f0527da799c260f60dcaf5c989`), written 2026-11-15T06:38:37+0800 by
  `d1_summary.py --variant FULL --queue outputs/framelease_v4/queue_p1 --write` after every job of the queue was final:
  9 blocks on training routes only, with the tuning freeze (sha256
  `652fcbdbf0a6adb498aa0691fcaaffb097fcd680b4bf40235a28639aed69b930`). D1, continuing or stopping, is the user's
  decision (Sec. 4.8); no later phase was started. Manifest and seal: `MANIFEST.sha256`, 221 files, sha256
  `4bfe7451a41b853042f181cbcd7c326649b4222279bc35dd9787afa38c8d4033`, sealed with this entry.

**Amendment A3, 2026-11-15 06:40 (Beijing time): registration of the Phase 2-7 tooling (no effect on any P1 run, P1 job
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
  `4bfe7451a41b853042f181cbcd7c326649b4222279bc35dd9787afa38c8d4033`, sealed with this entry.

**Amendment A9, 2026-11-15 06:40 (Beijing time): the aggregator was developed with read-only runs on finished P1
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
  `4bfe7451a41b853042f181cbcd7c326649b4222279bc35dd9787afa38c8d4033`, sealed with this entry.

**Amendment A7, 2026-11-15 06:40 (Beijing time): a supplementary S2 grid relative to each state's Eq. 5 slack floor
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
  34 passed in 30.38s
  (`outputs/framelease_v4/amendment_a7/pytest_stress_bench.log`,
  `4ca00fbd23e75887174e4bc878d6ebb37582661dfa388726a40dc65729390a7c`); a development relative-grid S2 run on the
  recorded smoke states (`outputs/framelease_v4/build/STRESS/s2_dev_relative_recorded_smoke_a7.json`,
  `9c92900e7c4594b734c1204c274b9679ed10b79b48e90f24c767176923e8f779`; 1000 states at kappa 1.0 and
  three development networks: every state admits an action from the first positive delta on, 0 admitted actions with
  bound >= D*, `floor_check` without mismatch).
* Manifest and seal after this amendment: `MANIFEST.sha256`, 221 files, sha256
  `4bfe7451a41b853042f181cbcd7c326649b4222279bc35dd9787afa38c8d4033`, sealed with this entry.

**Amendment A4, 2026-11-15 06:40 (Beijing time): realisation of the ablation arms `fl_bandit`, `fl_fqi_nolease`,
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

**Operational addition, 2026-11-15 06:40 (Beijing time): the phase driver of Phases 2-7 (FULL; no change of any run, job
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
    24 passed in 163.54s (0:02:43) (`pytest_phase_driver.log`,
    `42b12b9d6205dd7d6a8d7749f0f63e37c7e5345f5780849c3800e0b4cd2dd7e9`);
  * the review tests `outputs/framelease_v4/build/PHASE/review/test_review_phase.py`
    (`c475f4f745d3de88208c8e7c0b994373526ffc6e0821bf20194f6a226bfa8cb4`; chaos SIGKILL, an orphaned tool, a
    registered file removed in the transaction, a P1 driver record between phase records, a registration-only
    amendment): 6 passed in 66.11s (0:01:06)
    (`pytest_review_phase.log`, `e5f2c98e88088eda4803c8f29f5ba9059921a707eb70a0b839c9938fdcc6b0c1`).
* Scope. No P1 run, P1 job file, stage selection, tuning freeze or criterion changes, and no file pinned by a job line
  changes; no job line pins these files and no agent imports them. The driver is started after P1 has ended and after
  this entry is sealed. The three files are registered from this entry on; a change of any of them is an amendment.
* Manifest and seal after this addition: `MANIFEST.sha256`, 221 files, sha256
  `4bfe7451a41b853042f181cbcd7c326649b4222279bc35dd9787afa38c8d4033`, sealed with this entry.

**Phase gates (P2-P7, FULL).**
* **G1 D1 decision** (2026-11-15 06:42, Beijing time). D1 (Sec. 4.8): **continue**.
  `outputs/framelease_v4/phase_driver/D1_DECISION.json` (sha256
  `95f3f9903900ed2e182f88964173129b7d1c5504179cb8f7e19ee88d99cc264e`), decided 2026-11-15T06:42:15+0800 by the
  coordinating session, on the D1 summary `outputs/framelease_v4/tuning/d1/FULL_d1_summary.json` (sha256
  `d8c0a76eba80c0c5d4faf93346146ff3db59d162d27636c2411cd206a09a2fb3`, cited by the P1 driver's entry "D1 summary").
  Rationale: P1 is complete. Every job of the ten P1 blocks (smoke, ref, lease_s1, event_s1, lease_s2, event_s2,
  heur_s1, heur_s2, age_s1, age_s2) has a final record: 270 ok and 1 timeout. The timeout is a simulator-side failure on
  training route 23659 (lease_s1, B0 at d = 10); by the registered rule the route is dropped from lease_s1 and from
  heur_s1, which reuses that run, for every candidate. No block carries a set-up failure flag. Every stage selection
  follows the registered successive-halving rule and is entered in Sec. 13.2. Tuning freeze (sha256
  652fcbdbf0a6adb498aa0691fcaaffb097fcd680b4bf40235a28639aed69b930): L* = B0 (T_x0.00, standard validity); d* = 1
  (utility v4_adet_d1); A* = 1.0 s; Event-Triggered at s_hb2.0 (heartbeat 2.0 s, detection shift 1.0 m, speed change 0.5
  m/s, yaw change 0.05 rad). Since L* = B0, the registered sensitivity arm fl_risk is active with lease point E5
  (lease_s1: E5 44.3 vs E10 35.3 mean DS on the kept T22a routes). Training-route driving scores (mean DS over kept
  routes). References on T22: Fixed Deep 46.0, Fast Only 75.5. FrameLease + Heuristic at L* = B0 and d* = 1: 65.0 on
  T22a and 49.9 on T22b. Age-Only at A* = 1.0 s: 67.8 on T22a and 60.2 on T22b. Event-Triggered at s_hb2.0: 63.0 on T22a
  and 60.3 on T22b. At the selected FrameLease point the fallback ratio is 27.3% (T22a) and 45.8% (T22b), P_both is
  39.2% and 20.3%, and the closed-loop R_cond is 66.0% and 38.2%. These are training-route tuning results and test no
  hypothesis; Secs. 9.2-9.5 decide on the 44 test routes. Decision: continue. Under Sec. 4.8 nothing registered changes:
  Phase 2 collects the registered RL data with the behaviour policy at L* on the 44 training routes at kappa 1.0, 1.5
  and 2.0, and the later phases run as registered. The training-route results are reported as they are, together with
  the test-route results. The user instructed on 2026-11-14 (translated): "from now on, review yourself whether to
  proceed to the next phase". The coordinating session reads this instruction as covering every phase gate after P1, D1
  included (Sec. 4.8: "Continuing or stopping is the user's decision"), and takes this decision under it. Phase 2 starts
  after this entry: the P2 job file is generated, entered in this section before it is queued, and launched (gate G2).
  Manifest and seal: `MANIFEST.sha256`, 221 files, sha256
  `4bfe7451a41b853042f181cbcd7c326649b4222279bc35dd9787afa38c8d4033`, sealed with this entry.
* **G2 P2 job file** (2026-11-15 06:43, Beijing time). `outputs/framelease_v4/p2_jobs/FULL/b10_rl_data.jsonl` (sha256
  `7974792f11ce322f192230e8c871228b44828db988bfcb6251cdd04a18670089`), 132 job lines: block `rl_data`, block number 10,
  tier 2, arm `fl_behaviour`, eps 0.3, kappa [1.0, 1.5, 2.0] (kappa 1.0: 44, kappa 1.5: 44, kappa 2.0: 44), seed 11, 44
  training routes (subset RL). Stage spec `outputs/framelease_v4/p2_jobs/FULL/b10_rl_data.stage.json` (sha256
  `7ffd399284486b529e416a416ec27885bc6ceb6ecfb12c7bc72c1d465d00a9be`) and check
  `outputs/framelease_v4/p2_jobs/FULL/b10_rl_data.check.json` (sha256
  `b7b5abc98d9c9dde88affce7d74230d430f43048d0f2489c2f65b2b563b11fe1`; no problem, every dry run passed), written by
  `source linux/env.sh && CUDA_VISIBLE_DEVICES= p2_jobs.py --check --write` from the tuning freeze
  `outputs/framelease_v4/tuning/selection.json` (sha256
  `652fcbdbf0a6adb498aa0691fcaaffb097fcd680b4bf40235a28639aed69b930`, cited by the P1 driver's entry "Tuning freeze"):
  L* = `B0` (`outputs/framelease_v4/envelopes/B0.json`, sha256
  `9ef8479f04dab873d22b50e8732176804ed67f351f17584355b241e424fa1927`), d* = 1 (utility `v4_adet_d1`). Code pins: 50
  files, rule framelease_v4/arms/jobs_v4.code_pins([L*]) (PROTOCOL Sec. 8.3). Not registered, entered here with the job
  file (GAP_AUDIT Sec. 6 item 5(d)): the block number 10, the route order (routes: random.Random(20261110 +
  10).shuffle(id-sorted training routes); per route the kappas [1.0, 1.5, 2.0] back to back, rotated by one position per
  route (p1_jobs.ordered); port 2600 + 10 (i mod 4) for line i) and the queue `outputs/framelease_v4/queue_p2`. After
  this entry the job file is copied into `outputs/framelease_v4/queue_p2/jobs.d` and its runner is launched in a
  dedicated systemd user scope (`systemd-run --user --scope -p OOMPolicy=continue bash
  framelease_v4/protocol/launch_queue.sh`). Manifest and seal: `MANIFEST.sha256`, 221 files, sha256
  `4bfe7451a41b853042f181cbcd7c326649b4222279bc35dd9787afa38c8d4033`, sealed with this entry.
* **G3 P2 data manifest** (2026-11-15 20:13, Beijing time). `outputs/framelease_v4/rl_data/data_manifest.json` (sha256
  `c29168e54f3102d9ab02f2ead828d47ea501afc0edbcba409dda267574a45bc4`) and the completion check
  `outputs/framelease_v4/rl_data/p2_check.json` (sha256
  `0534942bbce5f1c56c12b9d9ea821e143df90aaaa59b14c8c3ccd5339ff775f5`), written 2026-11-15T20:13:33+0800 by `p2_check.py
  --queue outputs/framelease_v4/queue_p2 --write` after every job of the queue was final and its runner had exited:
  PASS; 132 jobs, 132 episodes (kappa 1.0: 44, kappa 1.5: 44, kappa 2.0: 44); no missing episode; 1 run directories
  excluded (failed or uncounted attempts); 0 errors. Job file sha256
  `7974792f11ce322f192230e8c871228b44828db988bfcb6251cdd04a18670089` (entry "G2 P2 job file"); runner records
  `outputs/framelease_v4/queue_p2/status.jsonl` sha256
  `0e290254fb4db879020cf058598f9d8f31ebfa1e204b819bcd9ec13479b5bfb3`. P2 ends with this data manifest (Sec. 8.1); P3
  builds the offline-RL dataset from exactly its episodes (Sec. 5.9). Manifest and seal: `MANIFEST.sha256`, 221 files;
  changed since the previous seal (not registered files): `framelease_v4/analysis/tests/test_verify_table1_extra.py`,
  `framelease_v4/analysis/verify_table1_extra.py`, sha256
  `0fdb720ea103b891218cf538960a8fb93f9f8d46dcef59c421716c0c6137dca3`, sealed with this entry.
* **G4 RL freeze** (2026-11-15 20:28, Beijing time). `outputs/framelease_v4/rl_freeze/rl_freeze.json` (sha256
  `a9e08c1931ea8cc6ab0f74111fa8bfb6a0b043ed44606fe0e7657c2d254db31d`), the RL freeze of Sec. 5.9, written by `p3_rl.py
  run` (sha256 `10a8590d511a9ab4858b87a93ad41e3a2961ad7a17af626bf27aedc781eab94b`): d* = 1, from the tuning freeze
  `outputs/framelease_v4/tuning/selection.json` (sha256
  `652fcbdbf0a6adb498aa0691fcaaffb097fcd680b4bf40235a28639aed69b930`) and the P2 data manifest
  `outputs/framelease_v4/rl_data/data_manifest.json` (sha256
  `c29168e54f3102d9ab02f2ead828d47ea501afc0edbcba409dda267574a45bc4`, entry "G3 P2 data manifest"); 132 episodes, 6591
  transitions, 0 missing; P_both label: testable. Deployed networks: `fl_full` `v4_qnet_5d8ffd7cf7dd` (family fqi,
  `outputs/framelease_v4/rl_freeze/qnet_fqi.json`, file sha256
  `b98de0ea0c0e55a3fa7c9a8accd8780b72f0ae9bc62c19bdf95f1e66e7f390f9`); `fl_bandit` `v4_qnet_1c3d57e3d8e7` (family
  bandit, `outputs/framelease_v4/rl_freeze/qnet_bandit.json`, file sha256
  `d70c979df81780ac9e97eb36b8b88d7e52bbc71c19d5d84b32174d8c5b2018a7`); `fl_fqi_nolease` `v4_qnet_6d5026a7b46f` (family
  fqi_nolease, `outputs/framelease_v4/rl_freeze/qnet_fqi_nolease.json`, file sha256
  `757d7b99c76d5f69217acf50b3633d407555f2346492736447c58ea6b5cfdc23`). Workers: `p3_rl.py calibrate` at the production
  sizes [33, 66, 132] on the choice-transition counts of `outputs/framelease_v4/rl_freeze/dataset` with d* = 1:
  `outputs/framelease_v4/build/phase_driver/p3_calibration.json` (sha256
  `36b42cb9a01cf95d6394a357b3bd16196b03b456cc8678d9984bdf43d4c7539e`), recommended n_jobs 10 (predicted select wall time
  0.25 h, worst case); the select stages ran with n_jobs fqi 10, bandit 10, fqi_nolease 10 (no stage parameter). Open
  cases of GAP_AUDIT Sec. 6 item 5: --distill-shortfall deploy_best (case (b)), decided in
  `outputs/framelease_v4/phase_driver/P3_OPEN_CASES.json` (sha256
  `499486e96ef6d6b7093c85f4d3ac0731ab90708c1beedfbe9aea5fa58f3474ea`): Open case GAP_AUDIT Sec. 6 item 5 (b): the
  distillation agreement of the selected FQI policy (fqi_K128_leaf40_beta0_d1; FQE mean Delta 42.0, 95% route-bootstrap
  interval [28.9, 56.9] over 44 routes) is 0.930 on 13,051 states after the registered 64x64 retry, below the 0.98
  target. The audit's registered default applies: the best try is deployed and its agreement is reported. The deployed
  network acts only inside the feasible set of the shield and under the budgeted call with deterministic fallback, so
  the timing and commit guarantees are unchanged; the FQE estimate refers to the FQI policy, and the agreement 0.930 is
  reported with the RL results (Table II-A, RL panel) as the distance between the deployed network and that policy. The
  RL freeze records the deviation. Decided by the coordinating session under the user's delegation of the phase gates
  (2026-11-14). Deviations recorded in the freeze: export_fqi: case distill_shortfall, option deploy_best;
  export_bandit: case distill_shortfall, option deploy_best; export_fqi_nolease: case distill_shortfall, option
  deploy_best. `p3_rl.py status`: every stage done and consistent; the driver re-hashed the 24 files the freeze names.
  P3 ran on every core at nice 10 while no closed-loop job ran (GPU idle). Entered when P3 ends (Sec. 8.1); the test
  freeze enters it again with the P4-P6 job files (Sec. 5.9). From this entry on `p3_rl.py` never recomputes a stage in
  `outputs/framelease_v4/rl_freeze` (`p3_rl.frozen_citations`). Manifest and seal: `MANIFEST.sha256`, 221 files, sha256
  `0fdb720ea103b891218cf538960a8fb93f9f8d46dcef59c421716c0c6137dca3`, sealed with this entry.
* **G5 Stress tests** (2026-11-15 20:42, Beijing time). Stress tests of Sec. 7.6 before the test freeze (Secs. 7.6,
  8.1), each `stress_bench.py <test> --registered` (sha256
  `0cff7b56e6fc09686601f06ff919bde29de17336d6342b9c66ea23bb617d04c2`) on synthetic decision states, S1 and S2 on the
  deployed networks `v4_qnet_1c3d57e3d8e7`, `v4_qnet_5d8ffd7cf7dd`, `v4_qnet_6d5026a7b46f` of the RL freeze (entry "G4
  RL freeze"). S3 `outputs/framelease_v4/stress/s3_registered_20261115T122819Z.json` (sha256
  `90b0393cbfef9ab76821271134479d7dc80aa645042cf623f43e26f54a98c6d4`): 100000 random event sequences on the commit
  gate and the runtime commit path, coverage ok, 0 violations of Eq. 9. S2
  `outputs/framelease_v4/stress/s2_registered_20261115T123104Z.json` (sha256
  `80b3c1b046febeed565544cc30a526683b6e43328e79fd1397629f4ad6d7ef12`): 1944 states x 71 slack values, 0 admitted
  actions with bound >= D*, 0 violations. Supplementary S2 relative to the slack floor (Amendment A7, the
  supplementary grid) `outputs/framelease_v4/stress/s2_relative_registered_20261115T123118Z.json` (sha256
  `53f2f89d691e0ef305a7acc0023aabd15a8d0d5926a5ef5279803f30ca23a92a`): 1881 states swept, 0 admitted actions with
  bound >= D*, 0 violations; labelled "supplementary: S2 relative to the slack floor", never in place of the
  registered S2. S1 `outputs/framelease_v4/stress/s1_registered_20261115T124141Z.json` (sha256
  `c04d06a20e9686878fb0a6c91dcd5b33cc77cbee2ed14d034f8b6b03f2fc5673`): loads 0/4/8/15 busy processes, the lease on L*
  (`outputs/framelease_v4/envelopes/B0.json`), every core at nice 10; the driver's guard found no process of this
  project alive and sampled the foreign CPU before the run (5 process(es) at >= 5% of one core over 2 s: ToDesk,
  gnome-shell, ToDesk_Service, WebKitWebProces, ToDesk_Session); 1 earlier attempt(s) in this series and 0 closed
  series (`outputs/framelease_v4/phase_driver/s1_guard.json`, sha256
  `028d1c3d713fa848f9cbbc121f8660ea156cd03af13b5b6bff922b4741019a5a`); foreign CPU load accepted by the coordinating
  session (`outputs/framelease_v4/phase_driver/S1_ACCEPT_FOREIGN_CPU.txt`, sha256
  `232bda527607539308a9d8656d2ab4e07462b85e1adc3e94cdf720ce59f5d490`; --accept-foreign-cpu). The test freeze takes the
  S1, S2 and S3 reports; the supplementary report is entered here only. Manifest and seal: `MANIFEST.sha256`, 221
  files, sha256 `0fdb720ea103b891218cf538960a8fb93f9f8d46dcef59c421716c0c6137dca3`, sealed with this entry.
* **G6 Test freeze** (2026-11-15 20:43, Beijing time). The test freeze (Secs. 3.3 rule 4, 5.9, 7.6, 8.1; GAP_AUDIT Sec.
  3.5 G-2, G-3), recorded by the phase driver: `test_freeze.py --write` wrote
  `outputs/framelease_v4/test_freeze/test_freeze.json` (sha256
  `e9e2d309fefd49209d1303356328049f8c0e89534f1b0cfaffffea82ed1ba633`) and its manifest
  `outputs/framelease_v4/test_freeze/MANIFEST.sha256` (125 files, sha256
  `69aae833d875d64003b3729ea83a386bcc0ce61f23da767b9cc03103763b2a93`) after `source linux/env.sh &&
  CUDA_VISIBLE_DEVICES= test_jobs.py --check --write` (index `outputs/framelease_v4/test_jobs/FULL/index.json`, sha256
  `34c528abc28688b816f2704bd1630ecf8dca15706d66ccf8ca933cd4e228a9ce`; every line checked with its --dry-run) and
  `registration.py --verify` (seal OK, manifest OK). Nested below: the entry text that `test_freeze.py --entry` printed,
  unchanged except for its line breaks. After this entry is sealed: `test_freeze.py --verify`; the 6 job files copied in
  name order (= tier order) into `outputs/framelease_v4/queue_p4/jobs.d`; `test_freeze.py --verify` again (the copies);
  then the runner of `outputs/framelease_v4/queue_p4` launched in a dedicated systemd user scope (`systemd-run --user
  --scope -p OOMPolicy=continue bash framelease_v4/protocol/launch_queue.sh`). Manifest and seal: `MANIFEST.sha256`, 221
  files, sha256 `0fdb720ea103b891218cf538960a8fb93f9f8d46dcef59c421716c0c6137dca3`, sealed with this entry.
  **Test freeze, 2026-11-15 20:43 (Beijing time): P4-P6 job files, RL freeze and stress tests (PROTOCOL Secs. 3.3 rule
  4, 5.9, 7.6, 8.1).** No test-route run existed at the freeze: no runs/ entry in the output directories of the 632
  P4-P6 lines or under `outputs/framelease_v4/matrix/`, `outputs/framelease_v4/fig3/`,
  `outputs/framelease_v4/ablation/`, `outputs/framelease_v4/replicates/`, and no status record in
  `outputs/framelease_v4/queue_p4`. P4 starts once this entry is sealed and `framelease_v4/protocol/test_freeze.py
  --verify` passes.
  * Record. `framelease_v4/protocol/test_freeze.py` wrote `outputs/framelease_v4/test_freeze/test_freeze.json` (sha256
    `e9e2d309fefd49209d1303356328049f8c0e89534f1b0cfaffffea82ed1ba633`) and its sha256 manifest
    `outputs/framelease_v4/test_freeze/MANIFEST.sha256` (125 files, sha256
    `69aae833d875d64003b3729ea83a386bcc0ce61f23da767b9cc03103763b2a93`). The manifest lists every file named in this
    entry, the pins of the P4-P6 lines, the code of the freeze, the route split, its source `routes.json` and the
    envelope manifest; these files are registered from this entry on, and `sha256sum -c` of the manifest from the
    project root shows that none changed. The route split, `routes.json`, the envelope manifest, the registered code the
    freeze runs and every pin except the network files and the extension sources were at their sha256 of the sealed
    registration manifest.
  * Tuning freeze (Sec. 4.9). `outputs/framelease_v4/tuning/selection.json` (sha256
    `652fcbdbf0a6adb498aa0691fcaaffb097fcd680b4bf40235a28639aed69b930`, entered above in line(s) 2261, 2274, 2772, 2798,
    2827): L* = B0 (`outputs/framelease_v4/envelopes/B0.json`, sha256
    `9ef8479f04dab873d22b50e8732176804ed67f351f17584355b241e424fa1927`), d* = 1 (utility `v4_adet_d1`), A* = 1.0 s,
    Event-Triggered `s_hb2.0` ({"det_shift_m": 1.0, "heartbeat_s": 2.0, "speed_delta_mps": 0.5, "yaw_delta_rad": 0.05}).
    L* = B0: fl_risk at E5, the better of E5 / E10 on lease_s1 (PROTOCOL Sec. 4.3). Its 8 stage selections are entered
    above.
  * RL freeze (Sec. 5.9). `outputs/framelease_v4/rl_freeze/rl_freeze.json` (sha256
    `a9e08c1931ea8cc6ab0f74111fa8bfb6a0b043ed44606fe0e7657c2d254db31d`), made from this tuning freeze, names 24 files,
    among them the P2 data manifest `outputs/framelease_v4/rl_data/data_manifest.json` (sha256
    `c29168e54f3102d9ab02f2ead828d47ea501afc0edbcba409dda267574a45bc4`, entered above in line(s) 2810, 2829). P_both:
    testable. Deployed networks (an arm is identified by its arm and the network file sha256; the name pins neither B_pi
    nor the provenance): `fl_bandit` `v4_qnet_1c3d57e3d8e7` (family bandit,
    `outputs/framelease_v4/rl_freeze/qnet_bandit.json`, file sha256
    `d70c979df81780ac9e97eb36b8b88d7e52bbc71c19d5d84b32174d8c5b2018a7`); `fl_fqi_nolease` `v4_qnet_6d5026a7b46f` (family
    fqi_nolease, `outputs/framelease_v4/rl_freeze/qnet_fqi_nolease.json`, file sha256
    `757d7b99c76d5f69217acf50b3633d407555f2346492736447c58ea6b5cfdc23`); `fl_full` `v4_qnet_5d8ffd7cf7dd` (family fqi,
    `outputs/framelease_v4/rl_freeze/qnet_fqi.json`, file sha256
    `b98de0ea0c0e55a3fa7c9a8accd8780b72f0ae9bc62c19bdf95f1e66e7f390f9`).
  * RL freeze deviations (GAP_AUDIT Sec. 6 item 5): export_fqi: case distill_shortfall, option deploy_best ((b) the
    distillation agreement stays below 0.98 after the 64x64 retry: deploy the best try and report its agreement);
    export_bandit: case distill_shortfall, option deploy_best ((b) the distillation agreement stays below 0.98 after the
    64x64 retry: deploy the best try and report its agreement); export_fqi_nolease: case distill_shortfall, option
    deploy_best ((b) the distillation agreement stays below 0.98 after the 64x64 retry: deploy the best try and report
    its agreement).
  * RL implementation note: GAP_AUDIT P3-2 ("bench_qnet.py: p50 / p99 against B_pi") is a hard gate here: deploy_check
    passes only when the featurize_forward p99 is at most B_pi = 100 us; PROTOCOL Sec. 5.7 defines B_pi only as the
    run-time bypass. The gate is stricter and changes no network.
  * RL implementation note: GAP_AUDIT P3-5 ("time ope.select on a synthetic dataset of the expected size") is p3_rl.py
    calibrate: CPU-time probes of every part of an ope.select task at three sizes, a cost law c + a n ln n and one real
    ope.select at the smallest size as an in-sample check; it sets --n-jobs only, which is no stage parameter.
  * RL implementation note: GAP_AUDIT Sec. 6 item 5: an a_det^{d*} head without support in a training fold is a regular
    unsupported evaluation (Amendment A6: ope.select marks the candidate unsupported in that fold and continues), so
    open case (a) covers a family that it leaves without a selectable candidate; open case (c) also covers a registered
    P2 run that the P2 data manifest does not list. Either is a deviation only when used (deviations).
  * Job files (Secs. 7.2-7.5, 8.2, 8.3, 8.6, 10.1). `outputs/framelease_v4/test_jobs/FULL/`, generated by
    `framelease_v4/protocol/test_jobs.py` (sha256 `2ea6899d07b990f244d3481366eea2dec02e24cbb3af4944049ac78b36639151`),
    index `index.json` (sha256 `34c528abc28688b816f2704bd1630ecf8dca15706d66ccf8ca933cd4e228a9ce`): `b11_ti_main.jsonl`
    tier 3 (P4), 308 lines, sha256 `54e551df44f30a02277e91849f1e40390cd77ffca7e59256edc98b3f5cd4a6df`; `b12_f3_k.jsonl`
    tier 4 (P5), 176 lines, sha256 `8ba8a4e5f6874860f9fefae81d836ccbdd297ac6a801a67663d6a5322507311b`;
    `b13_a_lease.jsonl` tier 5 (P6), 22 lines, sha256
    `6b906bc220d74fdf8fb5bfce287465e608fd378b22869af6d188ec411d37bd2a`; `b14_a_rl.jsonl` tier 5 (P6), 44 lines, sha256
    `a73491e47ab5cb3fcba868a0e5e6bf7f34c5ad6a09ea3fde8cd11d18ef623e31`; `b15_s_seed12.jsonl` tier 6 (P6), 60 lines,
    sha256 `bd77e5ed172bc834b63a4fa188cae97f92047f8072a45b92e738aad52cffd207`; `b16_s_risk.jsonl` tier 6 (P6), 22 lines,
    sha256 `83fe874f000340d6ee15509c35c7829bd03a6612a75a181e82c0b26ab36a156b`. 632 lines in total, the registered budget
    of Sec. 10.1. Every line passed gpu_queue's job contract, the pins, the test routes of its block's subset, the kappa
    and seed of its block, the launcher's parsing, configuration build and preflight and the `--dry-run` of the exact
    command through its launcher (`framelease_v4/arms/run_closed_loop_v4.py`;
    `framelease_v4/arms_ext/run_closed_loop_ext.py` for `fl_global_shield`), as the `.check.json` files record; the
    block specs (`.stage.json`) give for every job id the protocol arm, route, kappa, seed, configuration and the
    envelope and network sha256.
  * Fixed by this entry: the block numbers 11-16 and the job file names, the Fig. 3 cell order (arm-major over kappa
    1.5, 2.0) and one queue `outputs/framelease_v4/queue_p4` for tiers 3-6: the job files are copied in name order into
    its `jobs.d/`, so a cut takes the bottom tiers first (Sec. 10.2).
  * Pins (Sec. 8.3). 59 files pinned by the P4-P6 lines (the 49 code files of every line, the envelopes, the three
    network files, the 5 extension sources of `fl_global_shield`), every one at its pinned sha256.
  * Stress tests (Sec. 7.6), registered runs. S3 `outputs/framelease_v4/stress/s3_registered_20261115T122819Z.json`
    (sha256 `90b0393cbfef9ab76821271134479d7dc80aa645042cf623f43e26f54a98c6d4`): 100000 random event sequences on the
    commit gate and on the V4Runtime commit path, every fault class covered, 0 commits violating Eq. 9. S2
    `outputs/framelease_v4/stress/s2_registered_20261115T123104Z.json` (sha256
    `80b3c1b046febeed565544cc30a526683b6e43328e79fd1397629f4ad6d7ef12`): 1944 decision states x 71 slack values per
    deployed network, 0 admitted actions with bound >= D*, 0 violations. S1
    `outputs/framelease_v4/stress/s1_registered_20261115T124141Z.json` (sha256
    `c04d06a20e9686878fb0a6c91dcd5b33cc77cbee2ed14d034f8b6b03f2fc5673`): loads 0/4/8/15 busy processes on an exclusive
    CPU, every deployed network, the lease on L*.
  * Implementation choices of the freeze: Test-route guard (G-2 "refuses while any test-route run exists"): a run is
    detected by its existence only, a runs/ entry in an output directory of the P4-P6 lines or under matrix/, fig3/,
    ablation/, replicates/ (Sec. 8.6), or a status record in outputs/framelease_v4/queue_p4; no result file is opened
    (Sec. 9.11). Stress tests: the freeze takes one registered report per test (stress_bench.py --registered) and
    refuses S2 or S3 with a violation (Sec. 7.6: the admitted actions with bound >= D* and the commits violating Eq. 9
    "must be 0"); S1 has no pass criterion and is recorded as measured. G-3: the P4-P6 job files, the RL freeze and the
    test-freeze record are covered by the test freeze's own sha256 manifest, cited in this entry and sealed with it;
    registration.py is unchanged. The P2 data manifest is entered in Sec. 13.2 by this entry when no earlier entry cites
    it (Sec. 5.9: the dataset manifest is entered in Sec. 13 as part of the test freeze). Arm identity (GAP_AUDIT Sec.
    2, "Recommended labelling"; Sec. 4.1 names no launcher arm for these arms): fl_bandit and fl_fqi_nolease run through
    the launcher arm fl_full with the network file of their family, fl_risk through fl_heuristic at its lease point;
    each such arm is the pair (launcher arm, network file sha256 or envelope sha256), recorded in the job line
    (protocol_arm), in the output directory (ablation/<arm>/) and in the block spec.

**Amendment A10, 2026-11-15 20:15 (Beijing time): registration of the analysis code: the analysis script, the
Proposition-1 coverage, the figure and table generator and the independent verification (Sec. 9.12; no effect on any
run, job file, selection or criterion).**
* Cause. Sec. 9.12 requires the sha256 of the analysis code in Sec. 13 before the analysis freeze. Amendment A3
  registers the aggregator (GAP_AUDIT rows R-1 to R-3: `framelease_v4/analysis/__init__.py`, `aggregate_v4.py`,
  `commit_audit.py`, `extra_metrics.py`, `interim_guard.py`, `manipulation.py`) and leaves the analysis script, the
  Proposition-1 coverage and the figure and table generators to their own entry. The phase driver (operational
  addition) holds the analysis freeze, gate G8, until an amendment cites the sha256 of `analyze_v4.py`. Each file
  below was built against `outputs/framelease_v4/p1_driver/GAP_AUDIT.md` Sec. 3.7 and reviewed independently
  (`outputs/framelease_v4/build/<item>/review/REVIEW.md`): R4 GO_WITH_FIXES, R5 GO, R6 GO_WITH_FIXES, R7
  GO_WITH_FIXES. Every must-fix item is applied; the second step of R7 must-fix 4 is replaced by the verification
  scope rule below. This entry registers the four files and their tests. From this entry on, a change of any of them
  is an amendment.
* Change: the files, their roles and the PROTOCOL sections they implement.

  | file | role | PROTOCOL | GAP_AUDIT | review |
  |---|---|---|---|---|
  | `framelease_v4/analysis/analyze_v4.py` | the registered analysis: the families H1, S-coll, S-dmr, H2, H3, F3, H4-cl and RL-abl with `sign_flip_test`, `bootstrap_ci`, `holm` and `label_directional` of `framelease_v2/analyze_closed_loop.py` (its sha256 checked against Sec. 12.2), the uncorrected secondary rows, the descriptive contrasts (noise floor, seed 12, RL gain by ability, kappa and seed, the depth contrast of Fig. 1, `fl_risk`), per scenario and per ability, the per-condition columns of Table I, Fig. 3 and Table II-A, the sensitivity, H4 offline, H5, the overhead quantities of Table II-B, the manipulation checks and the missing data; the Sec. 9.11 guard on the command line and in the Python API | 6, 7.2-7.6, 9.1-9.13 | R-4 | `build/R4/review/REVIEW.md`: GO_WITH_FIXES; must-fix 1-2 and should-fix 1-5 applied |
  | `framelease_v4/analysis/prop1_coverage.py` | Proposition-1 coverage of the deployed E* (L* of the cited tuning freeze, and the `fl_risk` point when L* = B0) on the 32 VAL clips: per-tau and whole-path coverage per class from `framelease_v3/envelopes.py` `clip_samples`, `iso_inside` and `coverage_summary` on the merged 37-clip view; clip bootstrap, 2000 resamples, seed 20261109; checks of the inputs, the envelope link, the gate2 reproduction and the pooled counts | 1.3, 4.3, 7.4, 9.13 | R-5 | `build/R5/review/REVIEW.md`: GO; should-fix S1-S5 not applied (below), S6 is this entry |
  | `framelease_v4/analysis/figures_tables.py` | Fig. 1 (with the scenario-type companion), Fig. 3, Table I, Table II-A, Table II-B and the training-route operating-point table with their captions, from the analysis outputs, the offline outputs, the coverage, the RL freeze, the stress reports and the D1 summary only; every shown number in `numbers.json` with its source file, field and row; the Sec. 9.11 permission check of every source; 'registered' only when every used source is registered | 4.8, 7.1-7.6, 9.8, 9.9, 9.11, 9.13 | R-6 | `build/R6/review/REVIEW.md`: GO_WITH_FIXES; must-fix 1-4 applied, should-fix items applied except those named below |
  | `framelease_v4/analysis/verify_independent.py` | the Sec. 9.12 verification: H1 and its findings, S-coll, the secondary SR, RC and infractions/km contrasts and the Table I cells DS (with its CI), SR, RC, collisions/km (route mean and pooled) and infractions/km recomputed from the job files, the runner's final records and the run directories they name; standard library and numpy only (it imports no project module and reads no analysis source); compared with the outputs of `aggregate_v4.py` and `analyze_v4.py` under tolerances fixed in its docstring | 6.1, 9.1-9.3, 9.8, 9.11, 9.12 | R-7 | `build/R7/review/REVIEW.md`: GO_WITH_FIXES; must-fix 1-3 and step 1 of must-fix 4 applied; should-fix items applied except the comparison with `numbers.json` |

* Use of the registered files (fixed by this entry).
  1. Analysis. After the analysis freeze is entered, `analyze_v4.py` runs on the aggregation of the freeze
     (`outputs/framelease_v4/analysis/final_<stamp>/`) with `--analysis-freeze`, `--required-job-files` (the tier 3-6
     job files of the test freeze), `--rl-freeze`, `--offline` (`outputs/framelease_v4/offline_ablation`, written before
     registration) and `--s3` (the registered S3 report), into `final_<stamp>/analysis/`. Its output counts as
     registered only when every condition the script states holds (the registered route table and settings, aggregations
     as the only inputs, the record checked against the registered job files, an RL freeze with a decisive P_both label,
     the offline outputs at their registered location, the registered S3 run, a determined H5 label, the location
     above); any other run is 'development' and lists why. The script reads a test-route row only under a valid
     analysis-freeze record and with its own sha256 cited in Sec. 13 (this entry).
  2. Figures and tables of the paper: `figures_tables.py --require-registered` on registered sources only. Any other
     run carries the development stamp in every figure, table and caption and never enters the paper.
  3. Proposition-1 coverage: `prop1_coverage.py` with the cited tuning freeze on the 32 VAL clips with the registered
     bootstrap; `figures_tables.py` counts a coverage run as registered only in that setting.
  4. Verification (Sec. 9.12): the procedure of the `verify_independent.py` docstring. An independent session
     (Sec. 9.12) runs it after the analysis freeze is entered, with the record, the freeze's aggregation and analysis
     and one `--queue` per queue the aggregation covers. AGREE releases H1 and its findings and the verified Table I
     columns; on DIFFER every difference is resolved and its cause entered in Sec. 13 before any of these numbers
     enters the paper. The sha256 of `verification.json` is entered in its own dated Sec. 13 entry. The other Table I
     columns follow deviation 9.
* Deviations from GAP_AUDIT and PROTOCOL recorded by the reviews (PROTOCOL governs; none changes a run, a pin or a
  criterion).
  1. Development data (Sec. 9.12: "written and tested on synthetic CSVs only"). No test-route run existed or was
     read. The values were used to check the code, never to choose a metric, a rule or a parameter. Every execution
     on real data from 2026-11-14 to the application of this entry read its inputs only; each is listed with its time
     (2026-11-14 unless a date is given) and its output directory (`build/` stands for `outputs/framelease_v4/build/`).
     * `analyze_v4.py`: synthetic CSVs (unit tests; the synthetic 632-row matrix of item R4, kept as
       `build/R7/dev/syn_r4/`) and the development aggregation of P1 training-route runs `build/AGG/smoke_D` of
       Amendment A9: a load check (07:35) and six command-line runs (07:40, 07:47 and 08:05 into scratch directories
       under /tmp; 08:14, 08:16 and 08:42, the last with the final code and `--force`, into
       `build/R4/smoke_train_D/`), with no test-route row and every family at n 0; its H4 functions on the offline
       outputs written before registration (07:59, a scratch script). Its tests read these offline outputs and the
       development S3 report `build/STRESS/s3_dev_report_v2.json` at every run.
     * `prop1_coverage.py`: synthetic samples, envelopes and freezes, and the real inputs of its item, the 32 VAL
       clips of the offline stage (recorded dataset clips, not routes; Sec. 7.4 ran on them before registration) and
       the registered envelopes: a check on the 15 gate2 VAL clips (08:54), a 3-clip run into /tmp (08:55), three
       runs into `build/R5/dev_run/` (08:56, 09:00 and 09:02, the last with the final code) and the full and subset
       runs of its review into scratch directories (09:03-09:14). Its tests recompute the coverage of the 32 VAL
       clips into a temporary directory at every run and compare it with `build/R5/dev_run/`.
     * `figures_tables.py`: a synthetic analysis on synthetic route ids (`build/R6/dev_run/`) and training-route
       sources: the analysis `build/R4/smoke_train_D/`, the R5 coverage run, a development RL freeze from the pilot
       runs, development stress reports and a development D1 summary computed read-only from `queue_p1` at 10:09
       (`build/R6/dev_inputs/d1/`), rendered into /tmp (09:45; the training-route table alone at 10:10) and into
       `build/R6/dev/` (10:29 and 11:25, the last with the final code); from 09:25 on, the offline outputs written
       before registration and the v2 matrix (Sec. 11.1, items 1 and 4-5), which its tests also read at every run.
     * `analyze_v4.py` and `figures_tables.py` on 2026-11-15, 01:24 to 03:33: item FILL0 (the fill of the paper's
       placeholders, `build/FILL0/`) and its review ran both on synthetic aggregations through the harness of
       `tests/test_figures_tables.py`, into scratch directories under /tmp (`/tmp/FILL0/`, `/tmp/review_FILL0/`, the
       temporary directories of the FILL0 tests); with the default `--offline` both read the offline outputs written
       before registration, as their own tests do at every run.
     * `verify_independent.py`: two synthetic matrices (`build/R7/dev/syn_r4/`, `build/R7/dev/syn_varied/`) and a
       copy of the `queue_p1` runner records made at 11:46 with the run directories they name
       (`build/R7/dev/p1_snapshot/`: 172 job lines, 139 usable training-route runs): runs into
       `build/R7/dev/verify_p1/` (11:50, 12:00 and 12:31, the last with the final code), a tie-rate check of the DS
       values with its rounding function (12:02), and, into scratch directories, the determinism runs and the import
       and file audit of its review (12:02-12:15) and the rerun of that audit (12:31).
     * The aggregator (`aggregate_v4.py` and the modules it imports), in addition to the runs of Amendment A9: on
       `build/R7/dev/p1_snapshot/` into `build/R7/dev/agg_p1/` (11:46-11:50; 0 test-route rows); two runs with
       `--write-freeze-record` on copies of the 7 P1-0 smoke job lines of route 18305 under /tmp (11:33 and 11:57),
       whose development analysis-freeze records (`build/R7/dev/scratch/freeze_probe_all_final.json`,
       `freeze_probe_cut.json`) no entry cites, so neither is valid; the earlier `commit_audit.py` (sha256
       `96dd22c4...bff279`, a copy under /tmp) and the current one (the rule of finding 1) on the 48 audited
       `fl_heuristic` runs of `build/R7/dev/agg_p1/` (14:09 and 14:10, `build/AGG/step0_reaudit/`); and, as the
       comparison target of the second independent script of deviation 9, on the same snapshot (14:50-14:55,
       `build/R7B/dev/agg_now/`) and on a copy of the `queue_p1` runner records made at 22:03
       (`build/R7B/dev/p1_snap_2203/`; 22:04-22:08, `build/R7B/dev/agg_snap_2203/`), each written under /tmp and
       then copied into `build/R7B/dev/`.
  2. Values of data that existed before registration were computed during development. The H4 offline label (Sec. 9.4;
     `build/R4/smoke_train_D/h4_offline.csv`: all 12 rows 'inconclusive'), the Table II-A offline panel and Fig. 1
     (a)-(b) from the offline outputs written before registration (Sec. 11.1 item 5 records that only their column
     headers, not their values, were viewed before registration), and the Proposition-1 coverage of E5, E10 and B0 on
     the 32 VAL clips. The H4 rule, the coverage definitions and their bootstraps are those of Secs. 7.4 and 9.4; no
     selection reads these values (the lease operating point is selected on closed-loop training DS, Secs. 4.2-4.9).
  3. Output location (Sec. 9.12: outputs go to `final_<stamp>/` with a sha256 manifest). The aggregation of the
     analysis freeze occupies `final_<stamp>/` with its own `SHA256SUMS`; the analysis writes into
     `final_<stamp>/analysis/` with its own `SHA256SUMS` and refuses a directory that holds an aggregation.
  4. Collisions per km (Sec. 6.1). The route-level value (`collisions_per_km`) is used by the paired contrasts and
     S-coll. The arm-level value is the pooled ratio (`collisions_per_km_pooled`): the sum of collisions over the sum
     of km driven with the 0.001 km floor per route, over the routes with both values, with a route-cluster
     percentile bootstrap (routes resampled, the ratio of sums per resample; 10,000 resamples, a fresh
     `default_rng(20261110)`, the draws of `bootstrap_ci`; 95%). Table I shows the pooled value and its interval.
  5. Sign-flip test (Sec. 9.1). The Monte Carlo cross-check (Sec. 9.1 names no seed) uses 200,000 sign vectors with
     the registered v4 seed 20261110; decisions use the exact p. Beyond 2^23 bins the registered `sign_flip_test`
     coarsens its DP grid (1-2-5 steps); `analyze_v4.py` reports the grid used next to the registered one (`dp_grid`,
     `dp_grid_registered`), and the verification reports its own p on that grid as a diagnostic.
  6. H4 offline (Sec. 9.4: "If an offline output lacks a paired quantity, the v4 analysis script computes it from
     `per_clip_selected.csv` with the same bootstrap"). `per_clip_selected.csv` holds the TRAIN-selected candidates only
     (subset all, alpha 0.05, AGE, GLOBAL and SUFFIX) and cannot supply a nested quantity; utilization cannot be pooled
     from it (the positives are not recorded). The script uses it only within that scope, reports any other missing
     quantity as missing with its reason, and recomputes every in-scope `paired.csv` row as a check (30 TRAIN rows
     agree, maximum difference 5.0e-6). On the offline outputs of Sec. 11.1 item 5 `paired.csv` supplies all 12 H4 rows.
     The secondary rows are the full crossing of Sec. 9.4's variations (2 comparisons x 2 risk levels x 3 quantities: 1
     primary and 11 secondary rows); 7 of them combine two or more variations; each is secondary and uses the same rule.
  7. H5 (Sec. 9.5 has the labels supported and contradicted). 'undetermined' marks incomplete evidence (an input
     without the commit audit, runs withheld by the interim-look guard, a phase not covered, no registered S3 report)
     and makes the run 'development'; the registered analysis has a determined label. A run the audit could not
     check leaves condition 1 unmet: status ERROR, or NO_LOG (neither `jobs.jsonl` nor `events.jsonl`) when the
     `runs.csv` row that selects the run records commits or no row records them; every NO_LOG run is listed.
  8. Table II-B (Sec. 7.6). `analyze_v4.py` reports the panel-B log quantities per condition as distributions of the
     per-run values (per-run quantiles are never pooled across runs); `figures_tables.py` renders Table II-B with S1-S4.
  9. Verification scope (Sec. 9.12: "recomputes the H1 contrasts and the Table I columns"). `verify_independent.py`
     recomputes DS, SR, RC, collisions/km and infractions/km. GPU usage, DMR, action age p50 and p95, fallback ratio,
     EIR, P_both and the closed-loop R_cond of the notes are registered results (Secs. 7.2, 9.13) and are recomputed
     by a second independent script from the run directories (Secs. 6.2-6.4, including the realized validity of the
     actor boxes behind EIR, R_cond and P_both). That script is registered by its own amendment before the analysis
     freeze and runs after it next to `verify_independent.py`; these columns enter the paper once its result is
     entered in Sec. 13.
  10. Verification statistics. The DP rounds `d / grid` with `numpy.rint`, the rounding of the registered
      `sign_flip_test`; the two decimal readings of "rounded" are reported at exact half-grid ties as diagnostics. A
      missing p counts as 1 in Holm and has no adjusted p. With the registered resamples and seed on both sides every
      bootstrap endpoint is judged to 1e-9. A DP support above 40,000,001 states makes that contrast 'not computable'.
      Every expected file, column and field is compared; an absent one is a difference.
  11. Figure layout (Sec. 7.1: panel (a) offline, the error against observation age and the Fast@Fresh - Deep@Old
      contrast against kappa; panel (b) closed loop, Fixed Deep - Fast Only per scenario type and per ability). Fig. 1
      has the offline panels (a) error against observation age and (b) Fast@Fresh - Deep@Old against kappa, and the
      closed-loop panel (c) Fixed Deep - Fast Only by ability next to the earlier measurement; the per-scenario-type
      difference (44 named rows) is a companion figure in the supplement (Sec. 9.13).
  12. Results that `figures_tables.py` does not render: the secondary offline protocols of Sec. 7.4, the uncorrected
      secondary rows of Sec. 9.3 (`secondary.csv`), the replicates and the noise floor (Sec. 9.6; `descriptive.csv`)
      and the manipulation checks beyond the background-load counts (Sec. 9.7; `analysis.json`). They enter the
      supplement from these files (Sec. 9.13). Compact main-text variants of Tables II-A and II-B are not built.
* Known limitations accepted (review should-fix items not applied; none affects a registered number or the Sec. 9.11
  guard of a command-line run).
  * `prop1_coverage.py`: in the Python API, `compute(routes=...)` replaces the registered test-route set instead of
    adding to it, and route ids are compared as strings (R5 S1, S2; the command line always uses the registered
    split, and no clip is on a test route); `CODE_FILES` omits `framelease_v3/suffix_lease_eval.py` and
    `framelease_v4/arms/metrics_v4.py` (S5; the reused code outside the manifest is fixed by its sha256 under
    "Evidence"). A run outside the registered setting carries no marker of its own (S3); `figures_tables.py` treats
    it as development.
  * `verify_independent.py`: the rendered Table I is not compared with `numbers.json`; `figures_tables.py` traces
    every printed number to its source row instead. The review tests `GuardRecordVocabulary` (a registered test
    route under a copy of PROTOCOL.md) and `ForgedProtocolCopy` exclude each other: under the registered rule the
    first is refused; on a synthetic test route the same three cases pass
    (`build/R7/fix/test_review_R7_vocab_synthetic.py`).
* Reporting rules for Proposition 1 (R5 review S4). With the coverage, the paper states: the lambda of E5 and E10 was
  selected on the same 32 VAL clips (the in-sample row of `frontier.csv`, Sec. 4.3), so the VAL coverage is not held
  out with respect to lambda; the coverage is conditional on a confident detection matched within 2 m and within
  50 m of the LiDAR, so missed actors lie outside it; whole-path coverage counts the recorded taus of each pair only;
  the pedestrian intervals rest on 6 clip clusters.
* Findings of the development runs carried to the analysis freeze (files of Amendment A3; this entry changes none).
  1. Commit audit, null margins. On `build/R7/dev/agg_p1` the commit audit (R-2) of the version of `commit_audit.py`
     used there (sha256 `96dd22c4...bff279`) reported FAIL with 12,958 'margin' violations in 38 of the 48 audited
     `fl_heuristic` runs of the stages `lease_s1` and `lease_s2` (violations: B0 8,179, E10 2,625, E5 2,154); the
     development aggregations `build/AGG/smoke_B`, `smoke_C` and `smoke_D` of 2026-11-11 (P1-0 smoke and `ref` runs
     only; 4,109 accepted commits) were PASS. Every flagged commit is an accepted commit whose logged margin is null
     (+inf) and whose validity record has n_relevant > 0, n_computed 0 and reason `horizon_cap`: the lease prefilter
     (`framelease_v3/runtime/v3_lease.py`) computed no agent because the distance lower bound of every relevant agent
     keeps its margin above delta, so the lease is the horizon cap and the margin at the commit is +inf. That version
     accepted a null margin only when the record named no relevant agent (n_relevant 0 or reason
     `no_relevant_agents`). The rule was settled in `commit_audit.py` before Amendment A3, which registers it
     (departure 6): a null commit margin passes where the validity record names no relevant agent, or has reason
     `horizon_cap` and n_computed 0 (the lease prefilter showed g > delta for every relevant agent, so M = +inf); any
     other null margin with a relevant agent is a violation. Under this rule the re-audit of the 48 runs
     (`build/AGG/step0_reaudit/`) finds 0 violations (47 PASS, 1 NO_LOG), and the development aggregations
     `build/R7B/dev/agg_now/` and `agg_snap_2203/` (184 and 194 audited runs) are PASS. H5 is decided by the
     registered commit audit.
  2. Kilometres of a run with RC 0. In `build/R7/dev/agg_p1/` the aggregator's `runs.csv` holds `km_driven` 0.0 for
     the smoke run of `fl_heuristic` on route 18305 (RC 0), where Sec. 6.1 floors km at 0.001 (the one difference
     of `build/R7/dev/verify_p1/`); its collisions/km and infractions/km agree with the verification. The floor was
     added to `runs.csv` in `aggregate_v4.py` before Amendment A3, which registers it: `build/R7B/dev/agg_snap_2203/`
     holds 0.001 for that run, the value that collisions/km, infractions/km and the pooled ratio use.
  3. Run selection without a runner record. For a job whose runner records are absent (a probe with its status lines
     removed) the aggregator selects a run from the job's output directory and the freeze record lists it; the
     verification reads the runner's final record only and lists such a job as a 'freeze record' difference. At the
     analysis freeze every job of `queue_p4` has a final runner record (gate G8).
* In-place text.
  * Sec. 4.1, the status sentence of Amendment A3: "the analysis script, the Proposition-1 coverage and the figure and
    table generators remain required before the analysis freeze" becomes "the analysis script, the Proposition-1
    coverage, the figure and table generator and the independent verification script are registered by Amendment
    A10".
  * Sec. 9.4, the last sentence, ends: "... with the same bootstrap, within that file's scope (TRAIN-selected
    candidates, subset all, alpha 0.05); a nested quantity comes from `paired.csv` only (Amendment A10)."
  * Sec. 9.12, "**Code.**", the last sentence ends: "... before the analysis freeze (the aggregator: Amendment A3; the
    analysis code: Amendment A10)."; then a new paragraph before "**Freeze.**":
    "**Analysis code (Amendment A10).** `analyze_v4.py`, `prop1_coverage.py`, `figures_tables.py` and
    `verify_independent.py` (`framelease_v4/analysis/`) are registered by Amendment A10. Besides synthetic data, they
    were run read-only during development on training-route aggregations, the offline VAL clips and P1 run
    directories, never on a test-route run."
  * Sec. 9.12, "**Freeze.**", the last sentence ends: "..., with a sha256 manifest; the analysis writes into its
    subdirectory `analysis/` with its own manifest (Amendment A10)."
  * Sec. 9.12, "**Verification.**", ends: "... from the raw run directories (Amendment A10:
    `framelease_v4/analysis/verify_independent.py` recomputes DS, SR, RC, collisions/km and infractions/km; a second
    script, registered by its own amendment before the analysis freeze, recomputes the other Table I columns, which
    enter the paper once its result is entered in Sec. 13)."
* Scope. No run, job file, pin, stage selection, freeze or criterion changes. No job line pins these files and no
  agent process imports them. The analysis-freeze record freezes the aggregator modules (Amendment A3); the analysis
  script checks its own citation (this entry) before it reads any test-route row; G8 of the phase driver waits for
  this entry. This entry precedes the analysis freeze.
* Files (sha256).

  | file | sha256 |
  |---|---|
  | `framelease_v4/analysis/analyze_v4.py` | `10d7ea4f9516725cd94932a0618bbe5cc6a20bae60b49f4004013b3682cee54c` |
  | `framelease_v4/analysis/prop1_coverage.py` | `ffaee8ddf74e707901208d1d28ad0f692fefda2a4f4ce24f9e36e6eba1c852c0` |
  | `framelease_v4/analysis/figures_tables.py` | `bd4ed54c60fbc5259aeb2ed56f5301ad612c3006fd4172f06b889f2ea0c2118c` |
  | `framelease_v4/analysis/verify_independent.py` | `4935152684abcfdaef547438772bb041f323344dcbfe636d41b2a161ff149bff` |
  | `framelease_v4/analysis/tests/test_analyze_v4.py` | `1a59a3e044478d56a0bb1700d756bfcf80f9c4b2e4b1c38c83fa2a111780564c` |
  | `framelease_v4/analysis/tests/test_prop1_coverage.py` | `fa72530489076fe1620002e77997abbae46b9f602b8cf39c987de8206a0d1bd3` |
  | `framelease_v4/analysis/tests/test_figures_tables.py` | `8b61b3b35933e1f4dbc33c682462a6533500158013053182ab0aae6281ae793e` |
  | `framelease_v4/analysis/tests/test_verify_independent.py` | `c647f9091c99944fa6d39e97e2f8c7283a819aeb820e668ae512885f2ff77823` |

* Evidence (outside the manifest; fixed by these sha256). Reviews: `outputs/framelease_v4/build/R4/review/REVIEW.md`
  (`4cfda4da4ff9efe19fc69c5583f297e8fdf0fab15bf83ddc994480c43601832f`), `build/R5/review/REVIEW.md`
  (`4dbdb3fe1bea1ca387036ed4ab2a4225b8e84fdd8e65be913bfd4f9922fd7fb2`), `build/R6/review/REVIEW.md`
  (`40b29a2cfb0fbfde1961870da96d3bca71d60088ef1c56a249c3c62fbb137abf`), `build/R7/review/REVIEW.md`
  (`e4333416adefd2109ccf7f574ab2ce06ab22a41a1c4f5410f22c7688772e4917`). Output manifests of the development runs:
  `build/R4/smoke_train_D/SHA256SUMS` (`375c92331006f0aac9a0a30ff39698a082d0d2758596daa49dedb27c55c3470d`),
  `build/R5/dev_run/SHA256SUMS` (`ccb795dc4db10fbbd9a0ede6005c467c328623ed1f6f715b783116a1d516fa56`),
  `build/R6/dev/SHA256SUMS` (`931ca0644b7690c72db4c9650eb19ee96e6e091fd160f180a3989f42ab3c77dd`),
  `build/R6/dev_run/SHA256SUMS` (`503766a2d9bca8adf5eec080fc5eb320b72c8ed78dcd884929571f352e2e100f`),
  `build/R7/dev/agg_p1/SHA256SUMS` (`672a57ee3b336fa494eb7825b3aa99c8964f9be19f8bdf2435c059ce4233786b`),
  `build/R7/dev/verify_p1/SHA256SUMS` (`5824a84f4bfbcdc20353bc538e02d124c7459d53e7503d3c5ac815e7b9f63442`),
  `build/R7/dev/syn_r4/verify/SHA256SUMS` (`a9a4f543bbd3efad4fadc8c9e735c6e3896fb19457b532b0b70a5f0e45171071`),
  `build/R7/dev/syn_varied/verify/SHA256SUMS`
  (`ea082386a43bdd2794cd4144681d6046ee76923dc7b14a295a4771542227f232`),
  `build/AGG/step0_reaudit/SHA256SUMS` (`1977399e03f0a77fa16c18dbd4be8a6676f9760242f2b08742da61ce302683ed`),
  `build/R7B/dev/agg_now/SHA256SUMS` (`b88ba6693f3e69a9094d2c9b7ecc38b880bea5fc6728a99e5acb3a4da9ab4cbb`),
  `build/R7B/dev/agg_snap_2203/SHA256SUMS`
  (`f7c93dcee758cc424279fa8397eae25369794d9441df81c51eb934f17fec73dc`). Code that the coverage reuses
  outside the registration manifest, equal to the sha256 recorded in
  `outputs/framelease_v3/gate2_offline/gate2_20261109/config.json` (R5 review Sec. 3): `framelease_v3/envelopes.py`
  (`4b50e33d5abcf1e791fe87d84039cdc560be313827db457ef7160968e633307c`), `framelease_v2/calibration.py`
  (`eb69bae0a64ece0fabc4c5133d18985f9d83f7c41fc3b42dca39e789f6193e2b`) and `framelease_v3/suffix_lease_eval.py`
  (`48417c1fc9ce6d0e7d604da1292f6a002ab266c500f9226b4cd17fbbf490691c`).
* Tests (CPU; logs in `outputs/framelease_v4/amendment_a10/`):
  * `tests/test_analyze_v4.py`: 48 passed, 107 subtests passed in 16.64s
    (`pytest_analyze_v4.log`, `3d6c4e3bd50d61cacec60d0bbbafc4531dcd5b3e0674c028f48f0f4f207c5e18`);
  * `tests/test_prop1_coverage.py`: 22 passed in 20.15s
    (`pytest_prop1_coverage.log`, `19d26691f913722dada248000164eea1d9729028967268a6d4f75f3195a87152`);
  * `tests/test_figures_tables.py`: 50 passed, 422 warnings in 24.53s
    (`pytest_figures_tables.log`, `7f27d7c271a0960e4af368c308550422d052b3e9eba990a9b080d6edbc97e3d0`);
  * `tests/test_verify_independent.py`: 28 passed, 20 subtests passed in 14.30s
    (`pytest_verify_independent.log`, `527b6de39dc8039fca790d485d31f78ae36bdb2971189b3f36a25428a3cf5b36`).

  At drafting (2026-11-14): 48 passed and 107 subtests; 22 passed; 50 passed; 28 passed and 20 subtests
  (`outputs/framelease_v4/build/AMEND2/logs/`).
* Manifest and seal after this amendment: `MANIFEST.sha256`, 221 files, sha256
  `0fdb720ea103b891218cf538960a8fb93f9f8d46dcef59c421716c0c6137dca3`, sealed with this entry.

**Amendment A12, 2026-11-15 23:30 (Beijing time): cut of the test blocks P4-P6 by the user's decision (Sec. 10.2): Table
I runs on 14 of the 44 test routes and every other block on its first routes among those 14; no criterion, arm, job
line or analysis rule changes.**
* Decision. On 2026-11-15 at about 23:05 the user asked to shorten the test phase so that the results and a complete
  paper exist in about 11 to 12 hours, by reducing every block rather than whole tiers, and chose 14 routes for
  Table I. The measured rate at the decision was 28 of the 308 Table I jobs final after 2 h 20 min (one of them a
  1500 s timeout twice), so the registered P4-P6 plan of 632 jobs needed about three days. The cut depends on run
  time only. No test-route outcome was examined: the runner's END lines were read for job health only and never
  summarized (Sec. 9.11).
* Departure from Sec. 10.2. Sec. 10.2 cuts tiers from the bottom and never cuts tier 3 (Table I). This cut reduces
  every tier, Table I included, by the user's decision. The registered analysis applies unchanged to the jobs that
  remain; the paper reports every result with its number of routes and labels the reduced blocks.
* Rule. S = the first 14 routes of the registered order of `outputs/framelease_v4/test_jobs/FULL/b11_ti_main.jsonl`:
  26458, 2790, 23658, 2390, 2084, 2204, 2115, 2050, 3248, 17563, 3464, 2509, 2286, 3561. Each other block keeps its
  first k routes, in its own registered order, among the routes of S. The kept job lines are byte-identical to the
  registered ones.

  | block | routes kept | jobs kept / registered |
  |---|---|---|
  | `b11_ti_main` (tier 3, Table I) | the 14 routes of S | 98 / 308 |
  | `b12_f3_k` (tier 4, Fig. 3, kappa 1.5 and 2.0) | 3248, 2390 | 16 / 176 |
  | `b13_a_lease` (tier 5, Table II-A lease panel) | 2050, 2204, 2286 | 3 / 22 |
  | `b14_a_rl` (tier 5, Table II-A RL panel) | 3248, 2509 | 4 / 44 |
  | `b15_s_seed12` (tier 6, seed-12 replicates) | 2050 | 4 / 60 |
  | `b16_s_risk` (tier 6, `fl_risk`) | 2286, 3248 | 2 / 22 |

  127 of the 632 registered jobs remain; the other 505 never start and carry the outcome "cut" in the analysis-freeze
  record. The plan with the kept routes per block: `outputs/framelease_v4/cut_20261115T231415/CUT_PLAN.json`
  (`9285400b7af3b8f62f98f62d2cdcea31e68a2ab3a5c3b5e35692b99671af78e3`).
* Job status at the cutoff. 29 jobs of `b11_ti_main` final (28 ok; `v4p4_fl_original_k1.0_s11_r23658` timeout after
  two attempts), the last of them `v4p4_fl_original_k1.0_s11_r2084`, which was running when the cut was decided; all
  of them on routes of S. No job of tiers 4-6 had started.
* Execution. The registered job files in `outputs/framelease_v4/test_jobs/FULL/` stay unchanged (their sha256 as the
  G6 entry cites). The runner of `outputs/framelease_v4/queue_p4` stopped after its running job and runs the reduced
  files, each a byte-identical subset of the registered file, kept in `outputs/framelease_v4/cut_20261115T231415/`:
  `jobs_reduced/b11_ti_main.jsonl` (`f2ca9523bebe100ea7f81c94705c85f8529b3efc6deb3bc8709548b6165c4b76`),
  `b12_f3_k.jsonl` (`f109356426295d766cbdf2b16ecb7e46c1a34fbd1e5e7fa2f54595198e0c1e91`),
  `b13_a_lease.jsonl` (`d8553d2fad38ebf93245315497ab7ea92e500d70dd60812ecb8b966eab0e0b2c`),
  `b14_a_rl.jsonl` (`29b3040630d1597818486db8f5767af18e3ceea155308d56e45ddd64c9a97508`),
  `b15_s_seed12.jsonl` (`bed17136118812267838bd8d869460d43db9d366c34ab37d465c0e7f7b166dd5`) and
  `b16_s_risk.jsonl` (`c1bb5723ab8ab2a0771a1579b0c0b427c8a98bb909a1805608b356a19593bc57`); the
  registered copies that `jobs.d` held are kept in `jobs_registered/`. The phase driver is stopped, because its G7
  requires the registered copies in `jobs.d`. When every kept job is final, the coordinating session carries out G8
  with the registered tools: `aggregate_v4.py --queue outputs/framelease_v4/queue_p4 --specs
  outputs/framelease_v4/test_jobs/FULL --write-freeze-record <record> --cut-amendment A12` (the job lines that never
  started are recorded as cut), the record entered by its sha256 as a dated Sec. 13 entry, then the registered
  analysis (Amendments A3 and A10).
* Later runs. The cut jobs keep their lines in the registered files. Running them later is a new amendment with its
  own freeze and analysis; the analysis under this cut stays as frozen.
* Manifest and seal after this amendment: `MANIFEST.sha256`, 221 files, sha256
  `0fdb720ea103b891218cf538960a8fb93f9f8d46dcef59c421716c0c6137dca3`, sealed with this entry.

**Amendment A11, 2026-11-16 00:59 (Beijing time): registration of the independent recomputation of the Table I columns
GPU usage, DMR, action age, fallback ratio, EIR and P_both and of the closed-loop R_cond, and the reporting rule of
its differences (Secs. 6.3, 7.2, 9.12, 9.13; no effect on any run, job file, selection or criterion).**
* Cause. Sec. 7.2 lists GPU usage, DMR, action age p50 and p95, fallback ratio, EIR and P_both as columns of Table I and
  puts the closed-loop R_cond in the table notes or the text; Sec. 9.13 puts every registered result in the paper or its
  supplement; Sec. 9.12 requires an independent recomputation of the Table I columns from the raw run directories before
  any number enters the paper. Amendment A10 registers `verify_independent.py`, which recomputes DS, SR, RC,
  collisions/km and infractions/km, and leaves the other columns to a second independent script registered by its own
  amendment before the analysis freeze (Amendment A10, deviation 9). This entry registers that script and its tests.
  Item R7B built it from the PROTOCOL text and the data formats, independently of the aggregator, the analysis and the
  implementation of these metrics (Sec. 9.12; `outputs/framelease_v4/build/R7B/`). The review returned GO_WITH_FIXES;
  must-fix M1-M5 and should-fix S1-S5 are applied. The review of the fixes returned GO_WITH_FIXES; its must-fix M1 (the
  cause of a difference) and M2 (the clearance interpolation of V) and should-fix S1-S4 are applied. The second review
  of the fixes returned GO; its should-fix S1 and S2 are not applied (Known limitations). The review of the reporting
  rule (`build/AMEND2/a10r7b/f1/REVIEW.md`) returned GO_WITH_FIXES; its must-fix M1-M3 and should-fix S1-S7 are applied
  (S1 as decided by the coordinating session: the classes of the differences). Its second round
  (`build/AMEND2/a10r7b/f1/review/REVIEW_round2.md`) returned GO_WITH_FIXES; its must-fix M1 and M2 and should-fix S1-S5
  are applied. Its third round (`build/AMEND2/a10r7b/f1/review/REVIEW_round3.md`) returned GO; its should-fix N1 is
  applied, and the fifth class of the reporting rule was added after it by the decision of the coordinating session. Its
  fourth round (`build/AMEND2/a10r7b/f1/review/REVIEW_round4.md`) returned GO; its should-fix N2 is not applied (Known
  limitations). The recomputation and the registered `realized.py` differ by the conventions F1 and F3 (and F2, inside
  the bounds; findings below); `realized.py` keeps them, and this entry fixes the reporting rule of the differences.
  From this entry on, a change of either file is an amendment.
* Change: the files, their roles and the PROTOCOL sections they implement.

  | file | role | PROTOCOL | review |
  |---|---|---|---|
  | `framelease_v4/analysis/verify_table1_extra.py` | the recomputation, per run from the raw logs, of GPU usage (and CUDA-seconds per second), DMR (from the first commit on; the all-ticks and expired-only variants), action age p50 and p95, the fallback ratio and episodes, P_both, EIR and the closed-loop R_cond (also without the V = 0 plans), and its comparison with the aggregator's `runs.csv` and `arm_summary.csv`, the runtime's `summary.json`, the runner's END-line results and the analysis outputs, each difference with its cause where a convention of the registered implementation explains it; the Sec. 9.11 guard | 5.1, 5.8, 6.2-6.4, 7.2, 9.11-9.13 | `build/R7B/review/REVIEW.md`: GO_WITH_FIXES, must-fix M1-M5 and should-fix S1-S5 applied; `build/R7B/rereview/REVIEW_round1.md`: GO_WITH_FIXES, must-fix M1, M2 and should-fix S1-S4 applied; `build/R7B/rereview/REVIEW.md`: GO, should-fix S1 and S2 not applied |
  | `framelease_v4/analysis/tests/test_verify_table1_extra.py` | known answers on synthetic run directories, the run-level and analysis-level comparisons, the causes of differences, the Sec. 6.3 definitions, the actor-log decoder, the guard, the imports, and the P1-0 smoke runs against their `summary.json` | as above | as above |

* What it computes (its docstring fixes every definition; the route is the unit, arm-level values are means over
  routes).
  * Inputs: the runner's `status.jsonl` (the last final 'end' record of a job names its run directory) and, in each run
    directory, `config.json`, `raw/agent/framelease/{ticks,jobs,events,decisions}.jsonl`, `summary.json` where present,
    the actor-box log `raw/agent/framelease/actors.jsonl.gz` and the lease parameter file that the config names.
  * GPU usage: the union of the cost-model intervals of prefixes and flow steps (`jobs.jsonl`; for a job still running
    at the end, its `job_start` event and the step quanta in the ticks) over the span of the ticks.
  * DMR: the ticks from the first commit on whose committed action, rebuilt from the accepted commit events, is not
    valid by the arm's rule (before the deadline for the lease arms; below the age cap for Fixed Deep, Fast Only and
    Event-Triggered), over those ticks. Fallback ratio: the ticks in mode 'fallback' over all ticks. Action age: the
    tick time minus the capture time of the committed action over the tracked ticks, p50 and p95 by linear
    interpolation. P_both: the decision rows at depth >= 1 with the shield evaluated and two feasible actions, over
    those rows.
  * EIR and the closed-loop R_cond (Sec. 6.3, standard validity): every accepted commit is a committed plan, placed
    with the true capture pose of the actor-box log; the ego footprint is the lease footprint of Eqs. 1-3 (headings by
    central differences, the ego box of the lease parameter file); the actor boxes are those of the log at t_k + tau.
    V is the first time at which the footprint comes within d_safe = 0.5 m of an actor box (the first conflicting
    sample of the 0.05 s grid brackets it; bisection refines it to 1e-4 s) and V_suf = clip(V - T_c, 0, H_bar). A
    conflict plan is a miss when H > V_suf; EIR counts the tracked ticks whose committed plan is a conflict plan at an
    age of at least V_suf. Plans that cannot be evaluated and the bisection resolution of V (a band of 1e-3 s around
    the miss rule) give bounds.
  * Causes of differences. The script also forms the Sec. 6.3 values under the conventions F1 and F3 of the registered
    implementation (findings below; F1, F3 and both, F1+F3), from the same plans and with bounds formed in the same
    way. A difference whose other side agrees with one of them carries that convention as its cause (`differences.csv`
    'cause', the first of F1, F3, F1+F3) and remains a difference; `table1_extra.json` counts the differences by
    cause, and `cause_plans.csv` lists every plan a convention changes (run directory, job, depth, sample, sample
    time, time of the last actor-log row, capture time, V, V_lin, H, the outcomes on both sides).
  * Not recomputed: the CIs and p-values of the contrasts of these metrics (the S-dmr family and the secondary rows;
    their per-route values and means are compared), the ability membership of the per-ability rows, and the
    closed-loop lease utilization and premature expiry (Sec. 6.3; not columns of Table I).
* Independence. Standard library, `zlib` and numpy only. It imports nothing of `framelease_v4/analysis`,
  `framelease_v4/arms/metrics_v4.py`, `realized.py`, `actor_log.py` or `framelease_v2` and uses no code of them: the
  definitions follow the PROTOCOL text and the documented conventions of the lease footprint, its own RFC 1952 decoder
  reads the gzip members of the actor-box log, and only data formats are taken from elsewhere. The block comparison of
  the review (`build/R7B/review/scripts/blocks.py`) finds no shared block of four or more lines with these files other
  than import lists; must-fix M3 removed the one copied block. The second review of the fixes repeats the comparison
  on the registered version with the same result; the conventions F1 and F3 emulate the registered behaviour and reuse
  no code.
* Tolerances (in the docstring: stated before the first comparison of each part; the time resolution of V with must-fix
  M1). Counts are compared exactly; fractions, ratios and times at 1e-6 absolute (the mean episode count at 1e-9). A
  value with bounds (the in-flight step quanta of a job still running at the end; Sec. 6.3: the unevaluable plans and
  the plans with |H - V_suf| < 1e-3 s, a band that covers the bisection resolution of V only) agrees when the other
  side lies within the bounds widened by the tolerance; these agreements are counted by kind. A difference below the
  registered grid (1e-4 for fractions, 1 ms for ages) is flagged 'below_grid' and remains a difference. An expected
  column, field or file that is absent is a difference. Every comparison has a scope: 'analysis' for a value the
  analysis reads for a column of Table I, 'record' for every other value; the verdict counts every difference.
* Interim looks (Sec. 9.11). Before any log is read, every input that names a route is classified with the registered
  route split (runner records, `runs.csv` rows, run directories, the jobs of `cells.csv` and every route list of the
  analysis outputs; a route id in any integral form, such as '1711.0' or '+1711', is that integer); an input whose route
  is unknown counts as a registered test route. A test route is released only by a valid analysis-freeze record that
  covers the input (its sha256 cited in Sec. 13, PROTOCOL.md equal to its seal, the recorded route split and analysis
  code on disk); otherwise the run is refused (exit 4) and only `guard_log.jsonl` is written. Under the registered
  record (status 'final') every run directory is recomputed: the development option `--runs-csv-values` is refused
  there. The test options `--route-split`, `--protocol` and `--seal` apply to synthetic test routes only.
* Development data (Secs. 9.11, 9.12; `build/` stands for `outputs/framelease_v4/build/`). No test-route run existed or
  was read. The values were used to check the code and to find the conventions F1 and F3 of the registered
  implementation, never to choose a definition or a tolerance; the reporting rule and its classes were fixed with their
  P1 sizes known (development comparison below). Synthetic run directories with known answers (the tests); with
  `--runs-csv-values`, the synthetic analysis outputs `build/R7/dev/syn_r4/`, `build/R7/dev/syn_varied/` and
  `build/R6/dev_inputs/`; the 14 P1-0 smoke run directories of training route 18305 (the tests); and the P1
  training-route run directories named by two copies of the `queue_p1` runner records (`build/R7/dev/p1_snapshot/`, made
  on 2026-11-14 at 11:46; `build/R7B/dev/p1_snap_2203/`, made on 2026-11-14 at 22:03), compared with the development
  aggregations `build/R7/dev/agg_p1/`, `build/R7B/dev/agg_now/` and `build/R7B/dev/agg_snap_2203/` (Amendment A10,
  deviation 1), from 2026-11-14 14:39 to 2026-11-15 13:22, into `build/R7B/dev/verify_p1*/` and scratch directories
  under /tmp (`build/R7B/PROGRESS.md`). The review of item R7B ran the reviewed version (with injected `runs.csv` values
  and guard probes), monkeypatched variants of it and a plan-by-plan comparison with `realized.py` on the 180 run
  directories of `build/R7B/dev/p1_snap_2203/`, from 2026-11-14 23:22 to 2026-11-15 00:20, into /tmp/review_R7B/ and
  `build/R7B/review/logs/` (`build/R7B/review/PROGRESS.md`). The review of the fixes ran the version under review on the
  P1 runs of `build/R7B/dev/p1_snap_2203/` against `build/R7B/dev/agg_snap_2203/` (2026-11-15 12:02-12:04) and on the
  272 P1 run directories under `outputs/framelease_v4/tuning/` (12:17-12:19), its decoder on the 180 actor logs of that
  snapshot (12:17), its own scripts on these run directories (12:05-12:23) and `realized.py` on the run directory of
  route 2086 in stage lease_s2 (12:13), into /tmp/A10A11/r7b/ (`build/R7B/rereview/PROGRESS.md`). Item R7B ran its fixed
  version on the same snapshot (2026-11-15 13:06-13:08 and 13:17-13:19, into `build/R7B/dev/verify_p1_snap_2203_d/`) and
  on the 272 run directories (13:09-13:11 and 13:19-13:21, into /tmp/A10A11/r7bfix/), and its development scripts
  `check_vlin.py` and `reconcile_p1.py` on these outputs (13:11-13:12 and 13:21, into `build/R7B/dev/`)
  (`build/R7B/PROGRESS.md`). The second review of the fixes ran the registered version on the P1 runs of
  `build/R7B/dev/p1_snap_2203/` against `build/R7B/dev/agg_snap_2203/` (2026-11-15 13:36-13:38) and on the 272 P1 run
  directories under `outputs/framelease_v4/tuning/` (13:39-13:41), with `--runs-csv-values` on the synthetic analysis
  outputs (13:57), and its own scripts and `realized.py` on these run directories (13:38-13:47 and 14:01), into
  /tmp/A10A11/r7b/round2/ (`build/R7B/rereview/PROGRESS.md`). Class F1 of the development comparison and the
  capture-time offsets were read from the outputs of the snapshot and of the 272 run directories (2026-11-15
  14:06-14:13, `f1_class_report.py`, into `build/AMEND2/a10r7b/f1/`). The review of the reporting rule read the same
  outputs and `build/R7B/dev/agg_snap_2203/runs.csv` (2026-11-15 14:40-14:58, its own scripts and `f1_class_report.py`,
  into `build/AMEND2/a10r7b/f1/review/` and /tmp/A10A11/f1rev/; `build/AMEND2/a10r7b/f1/review/PROGRESS.md`). The fixes
  of that review read the same outputs again (2026-11-15 15:16, `fix1_numbers.py` and `f1_class_report.py`; 23:36-23:57,
  `f1_class_report.py`, which also reads `build/R7B/dev/p1_snap_2203/status.jsonl` and
  `build/R7B/dev/agg_snap_2203/runs.csv`, a scratch probe and one-line reads of `differences.csv`, `runs_recomputed.csv`
  and `table1_extra.json` of the snapshot output and of `build/R7B/dev/agg_snap_2203/runs.csv`; into
  `build/AMEND2/a10r7b/f1/` and /tmp/A10A11/f1fix/; `build/AMEND2/a10r7b/f1/PROGRESS.md`). The second review of the
  reporting rule read the same outputs, `build/R7B/dev/agg_snap_2203/runs.csv` and
  `build/R7B/dev/p1_snap_2203/status.jsonl` (2026-11-16 00:05-00:12, its own scripts, into
  `build/AMEND2/a10r7b/f1/review/` and /tmp/A11R2/; `build/AMEND2/a10r7b/f1/review/PROGRESS.md`). The fixes of that
  review ran `f1_class_report.py` on the same outputs, with the same runner records and `runs.csv` (2026-11-16
  00:20-00:22 and 00:39-00:42, into /tmp/A10A11/f1fix/ and `build/AMEND2/a10r7b/f1/`;
  `build/AMEND2/a10r7b/f1/PROGRESS.md`). The definitions and tolerances were fixed in the docstring before the first
  comparison; the corrections of must-fix M1 and M2 of the review (the continuous V, the lease footprint) follow the
  text of Sec. 6.3, and the fixes of the review of the fixes change no value of the script
  (`build/R7B/rereview/REVIEW.md`).
* Development comparison of the registered version (2026-11-15, `build/R7B/dev/verify_p1_snap_2203_d/`). On the P1 runs
  of `build/R7B/dev/p1_snap_2203/` against `build/R7B/dev/agg_snap_2203/` (the aggregator of Amendment A3): 180 run
  directories recomputed, 179 `runs.csv` rows with analysis_use, 12,259 comparisons, 136 differences, 1 of them in a
  value the analysis reads. Every Sec. 6.3 difference other than the empty cells of an unused run carries cause F1: 26
  values (the Sec. 6.3 counts of 19 runs and the `fast_only` EIR mean of `arm_summary.csv`), among them the one value
  the analysis reads (`fast_only`, route 1792: EIR 94/412 = 0.2282 recomputed, 85/412 = 0.2063 in `runs.csv`). The 110
  differences without a cause: 69 in the cross-check columns `gpu_usage_recomputed` (31), `gpu_busy_recomputed_s` (31)
  and `commits` (7) of `runs.csv` in the 31 runs that end with a job still running, whose work the aggregator omits
  there (the `gpu_usage` that the analysis reads agrees within the in-flight bounds), and 41 of the timed-out run of job
  `v4p1_fl_heuristic_B0_d10_k1.0_s11_r23659` (not used; outcome 'sim_failure'), whose `runs.csv` row carries no metric
  (39 cells, 2 runner result fields). Two runs agree only within the Sec. 6.3 bounds: route 24211 (EIR, finding F2) and
  route 2086 (EIR, finding F2; its misses, R_cond and R_cond without V = 0 equal the values under F3: plan 240:2, V
  2.86375 s by the first crossing, 2.86985 s by the clearance interpolation, H 2.36612 s). `summary.json`: 3,759
  comparisons, 0 differences. On all 272 P1 run directories under `outputs/framelease_v4/tuning/`: `summary.json` 5,523
  comparisons, 0 differences; F1 changes 47 plans in 26 run directories and F3 2 plans in 2. On the synthetic analysis
  outputs (`--runs-csv-values`; `build/R7B/dev/syn_r4_d/`, `r6_dev_inputs_d/`, `syn_varied_d/`): AGREE with 25,746,
  25,746 and 20,242 comparisons. Classes of this comparison (reporting rule below;
  `build/AMEND2/a10r7b/f1/f1_class_dev.json`). Class F1: 26 differences, 1 of them in scope 'analysis'; runs per arm
  `event_triggered` 6, `fast_only` 5, `fixed_deep` 4, `fl_heuristic` 4 (19 of the 180 runs, all with analysis_use);
  largest absolute difference per column: in `runs.csv` realized_log_censored_plans 10, realized_invalid_ticks 9,
  realized_conflict_plans 1, realized_misses 1 and realized_invalid_tick_ratio 0.0218 (`fast_only`, route 1792, the
  value the analysis reads), in `arm_summary.csv` realized_invalid_tick_ratio 0.0010; each of the 26 has an absolute
  difference. Class in-flight: the 69, none in scope 'analysis'; runs per arm `event_triggered` 8, `fast_only` 2,
  `fixed_deep` 11, `fl_heuristic` 9, `fl_original` 1 (31 runs); largest absolute difference `gpu_usage_recomputed`
  0.0136, `gpu_busy_recomputed_s` 0.212 s, `commits` 7. Class F3: none. Class not-ok record: the 41 of the timed-out run
  (runner outcome 'timeout'), none in scope 'analysis', none with an absolute difference. Class undefined-metric
  pairing: none (the development comparison reads no analysis output). No difference is without a class. P1 rates behind
  the expected sizes of the final run (`build/AMEND2/a10r7b/f1/F1_RULE.md`, Sec. 4): an F1 plan in 26 of the 271 run
  directories, a job in flight at the end in 31 of the 180 runs of the snapshot and 36 of the 272 run directories, an F3
  plan outside the 1e-3 s band in 1 of the 271, a job whose outcome is not 'ok' in 1 of the 180 runs; Amendment A12
  records one such Table I job (`v4p4_fl_original_k1.0_s11_r23658`, timeout after two attempts). Class undefined-metric
  pairing has no P1 rate; the dry run of gate G8 on synthetic runs of the A12 plan (`build/G8CUT/DRYRUN.md`) gives 76
  such rows: 14 x 3 for P_both of `fl_full` against `fixed_deep`, `fast_only` and `event_triggered`, 13 x 2 for
  `fl_heuristic` and `fl_full` against `fl_original` (one route without a used `fl_original` cell, the timed-out job)
  and 2 x 4 for Fig. 3 at kappa 1.5 and 2.0.
* Findings about registered files (Sec. 6.3), carried to the analysis freeze; this entry changes no registered file.
  * F1. `framelease_v4/arms/actor_log.py` places a row of the actor-box log at its frame time, a multiple of 0.05 s,
    and `realized.py` (through `GTTrack._bracket` of `framelease_v2/geometry.py`) treats a time above the last row by
    more than 1e-9 s as outside the log, while the plan sample times `capture_s + tau` lie above the 0.05 s grid by the
    runtime's clock offset (a drift of 1.49e-8 s per s: up to 3.0e-6 s in 200 s; 1.4e-7 to 2.0e-6 s at the plans that
    F1 changes on P1): a sample that lands on the last row has no actors, so a conflict first found there is lost and
    a clear plan whose horizon ends at that row counts as log-censored. On the P1 runs above this changes the Sec. 6.3
    counts of 19 of the 180 runs (38 plans clear here and log-censored there; 2 conflict plans here, both misses,
    log-censored there) and one EIR value the analysis reads; 26 of the 271 recomputed P1 run directories carry such a
    plan (47 plans).
  * F2. `realized.py` places a plan only through the actor-log row of its capture step: a plan without that row (a
    decimated log) and the commits of a job still running at the end leave the counts and, with their tracked ticks,
    the EIR denominator, which Sec. 6.3 forms from all tracked ticks. The recomputation bounds the commits of a job
    still running at the end (no logged plan: unevaluable); it takes the capture pose of a plan without its row between
    the bracketing rows and evaluates the plan, so a decimated log gives differences without a cause. No P1 log was
    decimated: the largest of the 271 logs holds 425 kB, and decimation starts at half of the 2,000,000-byte budget.
  * F3. `realized.py` takes V by linear interpolation of the clearance between the grid samples j - 1 and j
    (`framelease_v2/c2_eval.py`, `observed_validity`; `geometry.py`, `first_crossing_time`): V = tau_{j-1} +
    0.05 c_{j-1} / (c_{j-1} - c_j), with c the least box distance minus d_safe over the vehicles and walkers whose
    centre-distance lower bound is at most d_safe + 5 m, and V = tau_j without such an actor at sample j - 1, where
    Sec. 6.3 defines V as the first time the footprint comes within d_safe. On the 271 recomputed P1 run directories
    the two differ by up to 31.7 ms, by more than 1 ms for 914 of the 7,078 conflict plans whose first conflicting
    sample lies after tau 0, and decide the miss of 2 plans differently (route 2086 plan 240:2, outside the 1e-3 s
    band; one more within it). The cause F3 of the recomputation omits the candidate radius d_safe + 5 m (Known
    limitations).
  * Gaps inside a log. A plan whose first unknown sample lies before the end of the log (rows more than 0.2 s apart,
    or rows without actors) is log-censored in the recomputation; `realized.py` interpolates across gaps up to 0.25 s,
    treats a row without actors as a row without conflict and counts a plan as log-censored only when its horizon
    passes the end of the log. Such a plan gives a difference without a cause. No P1 log has such a gap or row: the
    rows of all 271 logs lie 0.05 s apart, and every row lists at least one actor.
  A difference whose registered value equals the value under F1, F3 or both, at the tolerances or within the bounds
  under that convention, carries that cause (`differences.csv` 'cause'); the reporting rule below assigns it to its
  class, and a difference that no class explains is a verification failure (use rule 2).
* Reporting rule for the differences (fixed by this entry). `framelease_v4/arms/realized.py` stays as registered: F1
  and F3 are not corrected. The registered values, those of the aggregator and the analysis through `realized.py`, are
  the values of Tables I and II and of the paper; the recomputation changes none of them. The run of use rule 1
  assigns every difference of `differences.csv` to one of five classes, each defined by its mechanism:
  * class F1: the cause 'F1' (finding F1);
  * class F3: the cause 'F3', or 'F1+F3' for a value that agrees only under both conventions (finding F3); the
    verifier gives a cause only when the other side agrees with the value under that convention at its tolerances or
    within the bounds formed under it;
  * class in-flight: a difference without a cause in the `runs.csv` cross-check columns `gpu_usage_recomputed`,
    `gpu_busy_recomputed_s` and `commits` (scope 'record') of a run that ended with a job still running. The aggregator
    (`metrics_v4.py`) forms them from `jobs.jsonl`, which lacks that job: the GPU columns without its step quanta,
    `commits` without its commits; the recomputation includes both. Required for the GPU columns: in-flight GPU
    boundaries in `runs_recomputed.csv`, the registered value below the lower bound of the recomputed one, and no
    difference in the run's `runs.csv` columns `gpu_usage` and `gpu_busy_in_span_s` (the runtime's busy time, which
    includes that job); for `commits`: in-flight GPU boundaries and a registered count lower by exactly the commits of
    jobs without a `jobs.jsonl` row. For the GPU columns the class tests the in-flight boundaries of the run and the
    direction of the difference, not its size against the omitted step quanta, which the verifier's outputs do not hold;
    the class report states the largest difference. The analysis reads none of these columns: `analyze_v4.py` reads
    `gpu_usage`, and `commits` only for a run without `jobs.jsonl` and `events.jsonl` (H5), which carries no recomputed
    value; `figures_tables.py` reads no `runs.csv`;
  * class not-ok record: a difference without a cause, scope 'record', in `runs.csv` or the runner's result fields,
    whose registered value is empty, of a job whose final runner outcome is a failure (not 'ok' or
    'result_with_warnings': timeout, crash, simulator failure), whose `runs.csv` row carries an outcome other than 'ok'
    and analysis_use false. For such a job `aggregate_v4.py` (`job_row`) records no metric and the runner no result
    values, while the recomputation recomputes the run that the runner's final record names; the analysis drops the row
    (Sec. 9.8). A valid run whose metric step failed (`runs.csv` outcome 'ok', missing_reason 'no_metrics') is outside
    the class. The outcome and the row come from the runner records and the `runs.csv` that `table1_extra.json` names
    with their sha256. A non-empty registered value in such a run, or a row the analysis reads, stays outside the class;
  * class undefined-metric pairing: a difference without a cause in the pairing status of a route in
    `paired_differences.csv` ('paired' here, not there) for a metric undefined by design for an arm of the contrast:
    P_both (Sec. 6.4) has no value for an arm without the shield of Eqs. 5 and 8 (`verify_table1_extra.py`: every arm
    outside SHIELD_ARMS, namely `fixed_deep`, `fast_only`, `event_triggered` and `fl_original`). `analyze_v4.py` drops
    the route from that metric with the status '<column> missing: <conditions>', while the recomputation pairs it
    because both cells are used. Required: the status names only conditions of such arms and the metric's column; the
    analysis row (from the `paired_differences.csv` that `table1_extra.json` names with its sha256) carries no value_a,
    value_b or difference; `differences.csv` holds no value_a, value_b or difference row of that route; every recomputed
    run of each named arm has no P_both. A difference in a numeric value, or a pairing where the metric is defined for
    both arms, stays outside the class.
  Each class is reported with its cause: the number of its differences, all and in scope 'analysis'; per arm, the
  number of runs with such a difference (the run directories of its `runs.csv`, `summary.json` and runner
  comparisons, the arm from `runs_recomputed.csv`); and per affected column (the target, metric and compared column
  of `differences.csv`) the largest absolute difference and the number of its differences without one (a side empty
  or not a number). `build/AMEND2/a10r7b/f1/f1_class_report.py` assigns the classes and forms these numbers from the
  output directory of that run after checking its inputs against the directory's `SHA256SUMS` (sha256 under
  Evidence; the rule with its evidence and the expected rates: `build/AMEND2/a10r7b/f1/F1_RULE.md`). The paper states
  each class, its cause and its size next to the verification result. A difference that no class explains, in
  particular one in a value the analysis reads, is a verification failure handled by the rules of Amendment A10 (use
  rule 4; Sec. 9.12).
* Known limitations accepted (should-fix S1 and S2 of the second review of the fixes, not applied; no P1 value is
  changed by them). The cause F3 omits the candidate radius of the registered clearance (finding F3): when a vehicle or
  walker enters the log next to the footprint at the conflicting sample and every actor at sample j - 1 lies beyond the
  radius, `realized.py` gives V = tau_j and the recomputation V_lin up to 4.5 ms earlier, a difference without a cause.
  Four branches have no test of their own (F1 at sample 0, an actor entering the log at the conflicting sample, a test
  entry of a route split without a route id, the upper bound of the log-censored plans with unevaluable plans); the
  second review of the fixes found each right on synthetic cases or a guard probe. Class undefined-metric pairing does
  not check that the conditions the analysis status names are those of the contrast (should-fix N2 of the fourth round
  of the review of the reporting rule, not applied): the registered `analyze_v4.py` (`paired`) names only the contrast's
  own conditions, and a pair dropped otherwise also changes the n of the contrast row, a difference without a class.
* Use of the registered files (fixed by this entry).
  1. After the analysis freeze is entered and `analyze_v4.py` has written `final_<stamp>/analysis/` (Amendment A10, use
     rule 1), an independent session (Sec. 9.12) runs `verify_table1_extra.py` next to `verify_independent.py`
     (Amendment A10, use rule 4): with `--analysis-freeze` (the record, or the `final_<stamp>/` directory that holds
     it), one `--queue` for every queue whose job lines the aggregation covers, `--agg final_<stamp>/`,
     `--analysis final_<stamp>/analysis/` and `--out` a new directory such as
     `outputs/framelease_v4/verification/final_<stamp>_table1_extra/`; never with `--runs-csv-values` or a test option.
     Only a result with status 'final' in `table1_extra.json` counts, and the class report releases it only when its
     `script_sha256` is the sha256 of the registered `verify_table1_extra.py` and `--runs-csv-values` was off.
  2. AGREE releases the Table I columns GPU usage, DMR, action age p50 and p95, fallback ratio, EIR and P_both and the
     closed-loop R_cond (table notes or text). On DIFFER with every difference in one of the five classes, these
     columns are released with the registered values and each class is reported (reporting rule above). Any other
     difference is a verification failure: it is resolved and its cause entered in Sec. 13 before any of these
     numbers enters the paper (Amendment A10, use rule 4; Sec. 9.12).
  3. The sha256 of `table1_extra.json`, of the `SHA256SUMS` of that directory and of the class report
     (`f1_class_report.py` at the sha256 cited under Evidence, on that directory), with the numbers of each class, are
     entered in their own dated Sec. 13 entry before the paper is written.
* In-place text. Sec. 9.12, "**Verification.**" (as Amendment A10 leaves it): "a second script, registered by its own
  amendment before the analysis freeze, recomputes the other Table I columns," becomes "Amendment A11:
  `framelease_v4/analysis/verify_table1_extra.py` recomputes GPU usage, DMR, action age p50 and p95, fallback ratio,
  EIR, P_both and the closed-loop R_cond,".
* Scope. No run, job file, pin, stage selection, freeze or criterion changes. No job line pins these files, no agent
  process imports them, and neither the aggregator nor the analysis imports them; the analysis-freeze record does not
  list them. The reporting rule changes no registered file and no registered value. This entry precedes the
  analysis freeze; the phase driver's gate G8 waits for Amendment A10 only.
* Files (sha256).

  | file | sha256 |
  |---|---|
  | `framelease_v4/analysis/verify_table1_extra.py` | `f77b2dcf34484d2537a4c22d804912f0c155c3e3c26a576f433b9f4f73d83c27` |
  | `framelease_v4/analysis/tests/test_verify_table1_extra.py` | `f0e74336e2244eea7136f3a94475ab0d96d5dfcd4b7fe0d8f97308877ac50154` |

* Evidence (outside the manifest; fixed by these sha256). Reviews: `outputs/framelease_v4/build/R7B/review/REVIEW.md`
  (`0aeac210c746641abf1f4290a1779acfbcde268c96197bdc420f9e82946ce57e`), the reviews of the fixes
  `build/R7B/rereview/REVIEW_round1.md` (`f7eb872fa6cb60bc55b854c2decce640ad99ffc7033d7e5bb850b32edbfb78f5`) and
  `build/R7B/rereview/REVIEW.md` (`e1220a896ebeda3e5380bd2c4fe02483951daca0a6a96f52ec13f5fe12694cdb`); the review tests
  `build/R7B/review/test_review_r7b.py` (`63c4359d5cf4991a4904bac1f1c95b4519856d84e4e96431182496b1b45ce0d0`),
  `build/R7B/rereview/test_rereview_r7b.py`
  (`b378a152e713da5396a1b780689ad64c28f329c0a2037a67e292b741c46d9ee2`) and
  `build/R7B/rereview/test_rereview_r7b_round2.py`
  (`16473afeb663e7b3a2c977699502f0c560436fc36f117404798a75d3e894bcd9`). Development comparison:
  `build/R7B/dev/verify_p1_snap_2203_d/SHA256SUMS`
  (`33f12f0fbe738df7e1da562c5d0250f5b40a25574d534eae954a26dc74670ff6`),
  `build/R7B/dev/reconcile_p1_d.json` (`21375e999bc7522e6519edeefcbf378c083b1876f2d24948d8d994dd5087b184`),
  `build/R7B/dev/check_vlin_snap_2203.json`
  (`c7b79d81cba2ba3c0c92cf2980e6f93637f1f7e091732abdcc7b8a42867b9d3d`), `build/R7B/dev/check_vlin_p1.json`
  (`e58153953d801d2574aeeb754257eef1f6e0b8d374441e06950524966fa0e7ab`), `build/R7B/dev/syn_r4_d/SHA256SUMS`
  (`7ad0803cf2d84414b5d14d72088ee34b0e02a4d3c3d36c7c92467e2044d3619c`), `build/R7B/dev/r6_dev_inputs_d/SHA256SUMS`
  (`87255bced2e2246faa2a9d646579a9deef12eba1b6f1778f59d40a69b409b62d`),
  `build/R7B/dev/syn_varied_d/SHA256SUMS` (`5bac8cfc6c7aeb3e5d67fd94e9d7fb02e92cf276de806b05d85290cfe058162a`).
  Mutation test of the tests: `build/R7B/logs/mutate_round1.log`
  (`e139bc5ac871842644fb983cedc62e643d3ba5ab0b88c41ba5ec3979cf0efdcd`; 138 of 138 mutants killed). Reporting rule
  of the differences: `build/AMEND2/a10r7b/f1/f1_class_report.py`
  (`ac82d65a9f4507a779dce5632e166b79e9d4c8d83f6c2b014ca27561e29145b6`), its tests
  `build/AMEND2/a10r7b/f1/test_f1_class_report.py`
  (`b2d3388c8b0d1efd2e142dbe63b388e1c3e675e12685db58f5255dd6d756c090`; the third test below), its
  output on the development comparison `build/AMEND2/a10r7b/f1/f1_class_dev.json`
  (`22ceb51f96fb797b9a1cd039a0056611716775929ba34ddbfe1e853557a580d7`) and the rule with its evidence
  `build/AMEND2/a10r7b/f1/F1_RULE.md` (`e117ade3adc7c09336bf6920a84db83066eaa971c30dc8c2e669ee5b9d5c0ad7`); the
  reviews of the rule `build/AMEND2/a10r7b/f1/REVIEW.md`
  (`9e2f2eabbc2632d0fad8f93ef6712f35d03a24b8f890a6d9da743f618a0ce33b`),
  `build/AMEND2/a10r7b/f1/review/REVIEW_round2.md`
  (`dd465845f105644674c1f2b6c693ec11debdf093a125af10de0b389e0a32e9d1`),
  `build/AMEND2/a10r7b/f1/review/REVIEW_round3.md`
  (`973d59ef13b9c35b9cb5e58bc2714ff5c9b5397410e83fdc23278fd8f3223b66`) and
  `build/AMEND2/a10r7b/f1/review/REVIEW_round4.md`
  (`79b4e6b156f9047544e304326711307f2674618f7b55057054a54c08dd60bc61`).
* Tests (CPU; logs in `outputs/framelease_v4/amendment_a11/`):
  * `tests/test_verify_table1_extra.py`: 87 passed, 80 subtests passed in 6.54s
    (`pytest_verify_table1_extra.log`, `e8fc11649986a93ca46458e9635123f21d69a57262ec71490cbbc1b4a9835e94`);
  * the review tests `build/R7B/review/test_review_r7b.py`:
    14 passed, 2 subtests passed in 4.85s
    (`pytest_review_r7b.log`, `ea4aab73c7574c1a579ad9c192fb46fa47aae79f9359f7a4df9e42c3e82b18ee`);
  * the tests of the class report `build/AMEND2/a10r7b/f1/test_f1_class_report.py`:
    34 passed, 59 subtests passed in 0.78s
    (`pytest_f1_class_report.log`, `ed762d1dac92497da4ea1c05eb1789b33ba4f64b5557974afdb7c700a035bfa2`).

  At drafting (2026-11-16): 87 passed and 80 subtests; 14 passed and 2 subtests; 34 passed and 59 subtests
  (`outputs/framelease_v4/build/AMEND2/a10r7b/f1/logs/`). Besides synthetic run directories, the tests read the 14 P1-0
  smoke run directories of training route 18305 and the review tests three P1 training-route run directories and
  `build/R7B/dev/agg_snap_2203/runs.csv`, all read only; the tests of the class report read synthetic run directories
  only.
* Manifest and seal after this amendment: `MANIFEST.sha256`, 221 files, sha256
  `0fdb720ea103b891218cf538960a8fb93f9f8d46dcef59c421716c0c6137dca3`, sealed with this entry.

**Amendment A13, 2026-11-16 09:15 (Beijing time): the analysis freeze (Sec. 9.12) under the cut of Amendment A12,
carried out by the coordinating session with the registered tools in place of gate G8 of the phase driver; no run, job
line, criterion or analysis rule changes.**
* Freeze. Every job that Amendment A12 keeps in tiers 3-6 was final and the runner of `outputs/framelease_v4/queue_p4`
  had exited (last runner exit 2026-11-16T01:12:24+00:00). `aggregate_v4.py --queue outputs/framelease_v4/queue_p4
  --specs outputs/framelease_v4/test_jobs/FULL --rl-freeze outputs/framelease_v4/rl_freeze/rl_freeze.json
  --tuning-freeze outputs/framelease_v4/tuning/selection.json --write-freeze-record
  outputs/framelease_v4/analysis/final_20261116T091445/analysis_freeze.json --cut-amendment A12` wrote
  `outputs/framelease_v4/analysis/final_20261116T091445/analysis_freeze.json` (sha256
  `fdda348027092724f74bf10cf0b5e33ed3219ffbfe5cfe6a57ac8aa9e4bd7c05`; trigger cut, cut amendment A12, frozen
  2026-11-16T09:15:07+0800).
* Job status: 632 jobs of the 6 job files of the test freeze (entry "G6 Test freeze", record
  `outputs/framelease_v4/test_freeze/test_freeze.json` sha256
  `e9e2d309fefd49209d1303356328049f8c0e89534f1b0cfaffffea82ed1ba633`):
  `outputs/framelease_v4/queue_p4/jobs.d/b11_ti_main.jsonl` (tier 3, 98 of 308 lines kept, sha256
  `54e551df44f30a02277e91849f1e40390cd77ffca7e59256edc98b3f5cd4a6df`);
  `outputs/framelease_v4/queue_p4/jobs.d/b12_f3_k.jsonl` (tier 4, 16 of 176 lines kept, sha256
  `8ba8a4e5f6874860f9fefae81d836ccbdd297ac6a801a67663d6a5322507311b`);
  `outputs/framelease_v4/queue_p4/jobs.d/b13_a_lease.jsonl` (tier 5, 3 of 22 lines kept, sha256
  `6b906bc220d74fdf8fb5bfce287465e608fd378b22869af6d188ec411d37bd2a`);
  `outputs/framelease_v4/queue_p4/jobs.d/b14_a_rl.jsonl` (tier 5, 4 of 44 lines kept, sha256
  `a73491e47ab5cb3fcba868a0e5e6bf7f34c5ad6a09ea3fde8cd11d18ef623e31`);
  `outputs/framelease_v4/queue_p4/jobs.d/b15_s_seed12.jsonl` (tier 6, 4 of 60 lines kept, sha256
  `bd77e5ed172bc834b63a4fa188cae97f92047f8072a45b92e738aad52cffd207`);
  `outputs/framelease_v4/queue_p4/jobs.d/b16_s_risk.jsonl` (tier 6, 2 of 22 lines kept, sha256
  `83fe874f000340d6ee15509c35c7829bd03a6612a75a181e82c0b26ab36a156b`); outcomes ok 126, agent_crashed 0, sim_failure 1,
  cut 505. The 127 jobs kept by Amendment A12 are final (ok 126, agent_crashed 0, sim_failure 1); the 505 cut jobs have
  no runner record and no run directory and carry the outcome cut.
* Job files. The runner ran the kept jobs from the reduced job files of Amendment A12
  (`outputs/framelease_v4/cut_20261115T231415/jobs_reduced/`, byte-identical subsets). Once every kept job was final and
  the runner had exited, `outputs/framelease_v4/queue_p4/STOP` was written and the registered copies
  (`outputs/framelease_v4/cut_20261115T231415/jobs_registered/`) were put back into
  `outputs/framelease_v4/queue_p4/jobs.d`, so that the record covers the registered job files of the test freeze at
  their sha256 of the G6 entry; `test_freeze.py --verify` passed on them. The STOP file stays: no runner starts a cut
  job.
* Analysis code frozen by the record: `aggregate_v4.py` (sha256
  `ee13c90b91bf44ad59d0a3c7e60bf93d65964785ed386d3e81c44fea0f5e4b96`), `commit_audit.py` (sha256
  `7439a4eac0986cad6a25b7395975a0411b7483944a988d68dabb656bd2544ec7`), `extra_metrics.py` (sha256
  `53050f6bed5aa48054d5217832fb84ed4089b3ae80e8fdcf965769af2af79c4c`), `interim_guard.py` (sha256
  `5453a3573e7cca958cad1bc1c44d53995a11e034e251bba634fe09390efed9c7`), `manipulation.py` (sha256
  `78f18dacf323832ef16684b0b81a2ba03b2ffb00186259780d1bafe7e656cbd0`); the analysis script
  `framelease_v4/analysis/analyze_v4.py` (sha256 `10d7ea4f9516725cd94932a0618bbe5cc6a20bae60b49f4004013b3682cee54c`) is
  registered in Sec. 13.2 by Amendment A10 and `framelease_v4/analysis/verify_table1_extra.py` (sha256
  `f77b2dcf34484d2537a4c22d804912f0c155c3e3c26a576f433b9f4f73d83c27`) by Amendment A11. Route split sha256
  `555f6869cb62d89082efc0fefc8f125ee133b16fd36a6fcf9f68bb1269fa527e`.
* Interim looks (Sec. 9.11). The aggregation that made the record ran without --arm-summary and without
  --analysis-freeze: every test-route row stayed health-only and no cross-arm summary was made. Its outputs and its
  guard log are in `outputs/framelease_v4/analysis/final_20261116T091445` (`SHA256SUMS` sha256
  `335317294a5d8d20af3f62f0b4eaeae5dce8a7454475b8a99b9d291e9d254ad3`);
  `outputs/framelease_v4/analysis/final_20261116T091445/required_job_files.json` (sha256
  `f58321692f998d7e33f713aee2f212f54f8e7699babc0f13310bcfdb71521d6d`) lists the six queue copies at their G6 sha256 (the
  --required-job-files of the analysis).
* Validity. The record is valid from this entry on (its sha256 in Sec. 13 of the sealed PROTOCOL.md,
  `interim_guard.load_freeze`). The confirmatory analysis (Amendments A3 and A10) writes its outputs into directories
  inside `outputs/framelease_v4/analysis/final_20261116T091445`, each with its sha256 manifest. The phase driver stays
  stopped (`outputs/framelease_v4/phase_driver/STOP`, Amendment A12): this entry takes the place of its G8 entry.
* Manifest and seal after this entry: `MANIFEST.sha256`, 221 files, sha256
  `0fdb720ea103b891218cf538960a8fb93f9f8d46dcef59c421716c0c6137dca3`, sealed with this entry.

Each amendment gets the date and time, the reason, and what changes for which runs. Every smoke report
(Sec. 8.1), every stage selection, the tuning freeze, the test freeze, any cut (Sec. 10.2) and the analysis freeze are
recorded here as dated entries with their sha256.

## 14. TRIMMED plan (reduced budget; not registered: the user chose FULL)

**Status.** FULL (Secs. 1-13) is the registered plan: the user chose it on 2026-11-10 (Sec. 13.1). TRIMMED, with about
72 instead of about 131 GPU-h, stays documented as the alternative. Switching after P1 has started is an amendment
(Sec. 13.2); runs that already exist are reused, because identical runs have identical ids and directories in both
variants (Sec. 8.2).

**What changes.** Everything not listed here is as in FULL.

| item | FULL | TRIMMED |
|---|---|---|
| tuning routes and procedure | T22 = T22a + T22b, successive halving (Sec. 4.2) | T22a only (11 routes), one stage: every candidate runs on T22a and the best mean DS over the kept routes is selected; ties go to the earlier candidate; failed runs as in Sec. 4.2 |
| references (block `ref`) | Fixed Deep and Fast Only x T22 (44) | none (the P1-0 smoke gives one reference route) |
| lease grid | {E5, E10, B0} x T22a, then top 2 x T22b | {E5, E10, B0} x T22a (the same 33 runs as FULL `lease_s1`) |
| heuristic grid | d in {10, 4, 1} | d in {10, 4} (d = 10 reused from the lease grid; 11 new runs) |
| Age-Only grid | A in {1.0, 1.5, 2.0, 2.5} s | A in {1.0, 1.5, 2.0} s |
| Event-Triggered grid | 4 settings | (theta_v2, 2.0 s) and (theta_s, 1.0 s): the least and the most aggressive corner of the FULL grid |
| RL data (P2) | 44 training routes x kappa {1.0, 1.5, 2.0} (132) | the 22 training routes outside T22 (training index % 2 == 1) x 2 behaviour seeds: rep 0 at kappa 1.0 on all 22; rep 1 at kappa 1.5 on the routes at even positions of the id-sorted 22, at kappa 2.0 on the others (44 runs: 22 / 11 / 11) |
| Table I (P4) | 7 arms x 44 test routes | the same (308) |
| Fig. 3 (P5) | 4 methods x kappa {1.5, 2.0} x E (22) | x C (11): 88 runs |
| Table II-A closed loop (P6) | `fl_global_shield`, `fl_bandit`, `fl_fqi_nolease` x E | the same arms x C: 33 runs |
| seed-12 replicates on R | 60 runs | none |
| `fl_risk` | conditional, 22 runs | none |

**Why the RL data are designed this way.** The Q-network takes kappa as a feature (GPU budget, outline III-B), and Full
FrameLease runs at kappa 1.5 and 2.0 in Fig. 3. With every behaviour run at kappa 1.0 that feature would be constant in
training and the deployed network would extrapolate at the other budgets. The second behaviour seed of each route
therefore runs at a contended budget. Routes outside T22 keep the RL episodes disjoint from every tuning route. The
alternative, both seeds at kappa 1.0 (more data at the primary setting), is the user's decision before P2; it does not
change the run count. Run list: `framelease_v4/rl/collection_plan.py --variant TRIMMED`
(`outputs/framelease_v4/rl_dev/collection_plan/plan_trimmed_eps0.300_d10.json`; regenerated with `--d-det d*
--envelope L*` after the tuning freeze). Seeds follow Sec. 2.6 with rep 0 and rep 1.

**Statistical consequences.**
* H1, H2 and H3 are unchanged: Table I runs on all 44 test routes.
* The families F3, H4-cl and RL-abl run on C (n = 11), with the complete sign-flip enumeration (2048 sign vectors).
  With the paired SD of about 31 DS points (Sec. 9.10) the minimum detectable effect (80% power, two-sided, normal
  approximation) is about 26 DS points at alpha 0.05, about 29 at 0.025 and about 31 at 0.0125. Fig. 3 is descriptive
  in both variants.
* There are no seed-12 replicates. The seed-to-seed noise floor is quoted from the v2 seed-12 replicates on R
  (`framelease_v2/CLOSED_LOOP_RESULTS.md`, the `H2_replicate_seed11_minus_seed12` rows; unmodified prefix) and labelled
  as such; the RL gain is broken down by ability (44 routes) and by GPU budget (C) only.
* Tuning precision: every candidate has 11 routes, so the SE of a candidate difference is about 9 DS points
  (Sec. 4.2). Configurations each arm was selected from: FrameLease 3 lease points + 1 extra depth, Age-Only 3,
  Event-Triggered 2; reported with the results.
* Without `fl_risk`: if L* = B0, Proposition 1 holds only under a zero-error assumption, and the paper states it; the
  realized risk of L* is reported in Tables I and II-A as in FULL.

**Budget (TRIMMED).** Generated into `outputs/framelease_v4/protocol/budget_trimmed.md` (7.5 min and 10 MB per run;
every figure from its own run count, as in Sec. 10.1):

| phase | tier | block | content | runs | GPU-h | GPU-h worst | disk GB |
|---|---:|---|---|---:|---:|---:|---:|
| P1-0 | 0 | smoke | P1-0 real-CARLA smoke: fixed_deep, fast_only, age_only, event_triggered, fl_original, fl_heuristic at E5, behaviour policy at E5 x 1 training route outside T22 (18305) | 7 | 0.9 | 2.9 | 0.07 |
| P1 | 1 | T-lease | lease grid {E5, E10, B0} x T22a (FL+H, d = 10, std validity; one stage) | 33 | 4.1 | 13.8 | 0.33 |
| P1 | 1 | T-event | Event-Triggered (theta_v2, 2.0 s) and (theta_s, 1.0 s) x T22a | 22 | 2.8 | 9.2 | 0.22 |
| P1 | 1 | T-heur | heuristic d = 4 x T22a at L* (d = 10 reused from the lease grid) | 11 | 1.4 | 4.6 | 0.11 |
| P1 | 1 | T-age | Age-Only A in {1.0, 1.5, 2.0} s x T22a (utility a_det^{d*}) | 33 | 4.1 | 13.8 | 0.33 |
| P2 | 2 | RL-data | behaviour policy (eps 0.3) at L*, the 22 training routes outside T22 x 2 behaviour seeds (rep 0 at kappa 1.0; rep 1 at kappa 1.5 / 2.0, alternating) | 44 | 5.5 | 18.3 | 0.44 |
| P4 | 3 | TI-main | Table I: 7 arms x 44 test routes, kappa 1.0, seed 11 | 308 | 38.5 | 128.3 | 3.08 |
| P5 | 4 | F3-k | Fig. 3: 4 arms x kappa {1.5, 2.0} x subset C | 88 | 11.0 | 36.7 | 0.88 |
| P6 | 5 | A-lease | Table II-A closed loop: Global-Margin lease + shield + heuristic x C | 11 | 1.4 | 4.6 | 0.11 |
| P6 | 5 | A-rl | Table II-A RL: Bandit and FQI w/o lease features x C | 22 | 2.8 | 9.2 | 0.22 |

| phase | runs | GPU-h | GPU-h worst | disk GB | free disk needed at phase start, rest of the plan (GiB) | free disk needed for this phase alone (GiB) |
|---|---:|---:|---:|---:|---:|---:|
| P1-0 | 7 | 0.9 | 2.9 | 0.07 | 11.4 | 6.1 |
| P1 | 99 | 12.4 | 41.3 | 0.99 | 11.4 | 7.0 |
| P2 | 44 | 5.5 | 18.3 | 0.44 | 10.5 | 6.5 |
| P4 | 308 | 38.5 | 128.3 | 3.08 | 10.0 | 8.9 |
| P5 | 88 | 11.0 | 36.7 | 0.88 | 7.2 | 6.9 |
| P6 | 33 | 4.1 | 13.8 | 0.33 | 6.4 | 6.4 |
| total | 579 | 72.4 | 241.3 | 5.79 | | |

Without the P1-0 smoke block: 572 runs, 71.5 GPU-h, 5.72 GB. This is slightly above the 60-70 GPU-h target; the
largest optional cuts are the second Event-Triggered setting (11 runs, 1.4 GPU-h) or Fig. 3 at kappa 2.0 only (44 runs,
5.5 GPU-h), each an amendment if chosen after registration.

**Disk prerequisite (TRIMMED).** The whole plan needs 11.4 GiB free before P1-0; P1-0 alone 6.1 GiB; P1 alone 7.0 GiB
(0.99 GB plus the 6 GiB floor, rounded up).

**Example calendar (TRIMMED).** From a P1-0 start on 2026-11-11 at 12:00, D1 taking no time: P1-0 ends about 11-11
14:00, P1 11-12 03:45, P2 11-12 09:15, P3 11-12 12:15, P4 11-14 02:45, P5 11-14 13:45, P6 11-14 18:00, P7 11-15.

**Job files (TRIMMED).** `outputs/framelease_v4/p1_jobs/TRIMMED/b02_lease_s1.jsonl` (byte-identical to the FULL
`lease_s1` file) and `b03_event_s1.jsonl`; `heur_s1` and `age_s1` are generated after the selections
(`p1_jobs.py --variant TRIMMED --block heur_s1 --check --write`, then `age_s1`). The P1-0 smoke block is shared.

**Cuts.** As in Sec. 10.2 (only by the user's decision, recorded as an amendment, never based on results), except that P5
and P6 already run on C and there are no replicates: tiers are cut from the bottom (tier 5, then 4); tier 3 (Table I)
is never cut.
