# Offline RL for the utility selector: implementation protocol (framelease_v4/rl)

Written 2026-11-10, before any behaviour (exploration) data exists. It fixes, at code level, how the RL part of
`framelease_v4/PROTOCOL.md` (Secs. 4.7 and 5) is executed. If the two documents disagree, the top-level protocol
governs the experimental design (routes, arms, kappas, freezes), and this file governs the estimators exactly as
implemented. The differences are listed in Sec. 8.

## 1. Data and leakage guard

* **Episodes.** Closed-loop run directories of the v4 arms launcher (arm `fl_behaviour`, `V4Runtime`; the v3 block of
  the configuration is read from `config.json` `v4.v3`) or of the v3 launcher: `config.json`,
  `raw/official_results.json`, `raw/agent/metric_info.json` and `raw/agent/framelease/{decisions,ticks}.jsonl`.
* **Training data.** Only training-route episodes. The data set is the `fl_behaviour` runs: FULL 44 training routes x
  kappa {1.0, 1.5, 2.0} x seed 11; TRIMMED the 22 training routes outside T22 x 2 behaviour seeds (rep 0 at kappa 1.0,
  rep 1 at kappa 1.5 / 2.0) (`collection_plan.py`, PROTOCOL Secs. 5.3 and 14).
* **Test-route guard.** `dataset.build_dataset` raises `PermissionError` on any of the 44 test routes
  (`outputs/framelease_v2/closed_loop_matrix/routes.json`). With `allow_test=True` it marks them `split=test`
  instead, and `trainers.fit_candidate` refuses them.
* **Policy-free runs.** v2-policy runs have no shield and no features. They are used only for the reward identity.

## 2. Decision process

* **Decision epochs.** One per row of `decisions.jsonl`, i.e. per refinement-quantum boundary of the running job.
* **Choice epochs.** Decision epochs with |A_feas| = 2. These are the only states where Eq. 8 consults the utility.
* **Forced epochs.** All other decision epochs. The shield decides there, whatever the utility, so they belong to the
  transition.
* **SMDP transition.** From one choice epoch to the next, with its elapsed time and the number of forced epochs in
  between.
* **Actions.** 0 = REFINE, 1 = REFRESH. FALLBACK and RECOVERY_REFRESH are never learned actions.
* **Default action.** a_det^d(s) = REFINE if depth(s) < d, else REFRESH. d = d*, the tuned heuristic depth; d = 10 is
  the v3 heuristic.

## 3. State, reward and propensities

**State.** 16 features from the logged 32 (`features.py`):

| group | features |
|---|---|
| lease-derived (6) | `lease_slack_s`, `cand_slack_s`, `refine_margin_s`, `refresh_margin_s`, `min_g_m`, `tau_star_s` |
| other (10) | `obs_age_s`, `depth`, `plan_delta_m`, `active_age_s`, `newer_frames`, `L_refine_s`, `L_refresh_s`, `kappa`, `ego_speed_mps`, `n_relevant` |

* Each feature has a fixed value for missing entries and a fixed clipping range. They are frozen into every exported
  network.
* `fqi_nolease` drops the six lease-derived features. The shield is unchanged in that ablation.

**Prefix score** (`prefix_score.py`). S(t) = RC(t) x P(t).
* RC(t) replays the official RouteCompletionTest (window 3, dot-product passing test, 100% once above 99% and
  within 10 m) on the logged hero positions, against the routes-XML keypoints densified to 1 m. Junction gaps are
  bridged by Hermite curves. RC is then rescaled so that its final value equals the official route completion. The
  unanchored error is reported.
* P(t) is the product of the Bench2Drive penalty factors:
  * pedestrian 0.5, vehicle 0.6, layout 0.65;
  * red light 0.7, stop 0.8, scenario timeout 0.7, yield to an emergency vehicle 0.7;
  * outside lanes 1 - %/100;
  * min speed: unused.
  * The factors are tested against the evaluator's `statistics_manager.py`.
  * Located events take the time of the ego's first closest approach to the message location (+0.05 m). Collisions
    match at 0.0 m on the pilot.
  * Unlocated events and route-ending events apply at the end of the episode.
* S(T) is the official DS.

**Reward (Eq. 7).**
* R_i = S(t_{c,i+1}) - S(t_{c,i}); the last transition gets DS - S(t_{c,last}).
* The identity pre_choice + sum R_i = DS is checked to 1e-9 per episode, both over all decision epochs and over the
  choice SMDP.
* Missing logs give a terminal-only reward, and the episode is flagged.

**Propensities.**
* Logged by the behaviour utility (`v4_mu`).
* Deterministic utilities (the v3 heuristic, `v4_adet_d<d>`, `v4_qnet_*`) have mu = 1.
* An unknown utility gives NaN, which excludes the episode from the importance-sampling diagnostics only.

## 4. Behaviour policy and data collection

**Utility name.** `v4_eps0.300_seed<s>[_d<d*>]` (`behaviour.py`).
* At a choice epoch it returns a_det^{d*}(s) with probability 0.7. Otherwise it picks one of the two feasible
  actions uniformly.
* mu = 0.85 for a_det^{d*}(s) and 0.15 for the other action.

**Seeds.** sha256(`framelease_v4_behaviour`, 20261110, route, kappa, rep) mod 2^62, so draws are independent across
runs (`collection_plan.py`).

**Plan.** `outputs/framelease_v4/rl_dev/collection_plan/plan_eps0.300_d10_k1.0-1.5-2.0_per1.json` (FULL, 132 runs) and
`plan_trimmed_eps0.300_d10.json` (TRIMMED, 44 runs).
* Every run is `framelease_v4/arms/run_closed_loop_v4.py --arm fl_behaviour` with an explicit `--fast-prefix`, the
  lease point `--envelope`, `--timeout-s 1410`, `--lock-wait-s 600`, port 2600 + 10 (i mod 4) and the output directory
  `outputs/framelease_v4/rl_data/k<kappa>/`.
* The training pool matches `outputs/framelease_v4/protocol/route_split.json`.
* The plan is regenerated with `--d-det d* --envelope L*` once the tuning freeze fixes them.
* Nothing is enqueued.

## 5. Trainers and grids (12 candidates per family; `trainers.grid`)

**FQI (`fqi`).** Finite-horizon, undiscounted.
* Q_0 = 0 and Q_k = fit(R + (1 - done) Q~_{k-1}(s', pi_{k-1}(s'))) for k = 1..K.
* pi_k is the greedy policy with the support and default rules below.
* Grid: K in {8, 32, 128} x leaf in {10, 40} x beta in {0, 1}.

**Bandit (`bandit`).** One fit, no bootstrap.
* Target: R up to the next choice epoch (`step`), or the equal-duration window gain S(t + W) - S(t) with W in {1, 2} s.
* Grid: window x leaf x beta.

**FQI without lease features (`fqi_nolease`).** The FQI grid on the 10 non-lease features.

**Fixed for all families.**
* ExtraTrees, one forest per action head: 100 trees, `max_features` 1.0, `random_state` 0 (+7919 for the REFRESH
  head).
* `min_support` 30 samples per head, deviation margin 0.

**Support rule.** The policy deviates from a_det^d(s) to the other action only if both heads are supported. A run
stops with an error if the default action's head is unsupported anywhere it is needed (`trainers.fit_candidate`).
Inside the selection this never stops the family: a training fold in which it would happen makes the candidate
unsupported in that fold (Sec. 6; PROTOCOL Amendment A6).

**Pessimism.** The deviating action's head is lowered by beta x the per-tree standard deviation. The default action
uses the plain mean.

## 6. Off-policy evaluation and selection (`ope.select`)

* **Folds.** 5 route-grouped folds over the training episodes (seed 20261110). Every episode is held out once.

**FQE of a deterministic pi on the held-out episodes.**
* lambda = 1 returns cut at the first disagreement (Watkins). For a transition i:
  * Y_i = R_i if the episode ends;
  * Y_i = R_i + Y_{i+1} if the next logged action equals pi(s');
  * otherwise Y_i = R_i + Q_{k-1}(s', pi(s')).
* No importance weights are needed: a segment is followed only while the logged actions are pi's.
* Iterations = (the largest number of bootstrap points along a held-out episode) + 2, capped at 600. A run that hits
  the cap is flagged `converged = false`.
* Value model: ExtraTrees with 50 trees, leaf 10 and `min_support` 5 per head. Its inputs are the 16 features plus
  three evaluation-only covariates: RC so far, P so far and elapsed time. They come from the hero state and are never
  a policy input. The same value model is used for every candidate.
* V_e(pi) = pre_choice_e + Q(s_first, pi(s_first)).
* A policy that needs a head the held-out data cannot fit is "unsupported" and cannot be selected.
* So is a candidate whose training fold cannot fit it (`ope.fit_support`: no head with `min_support` samples, or the
  a_det^{d*} head unsupported where it is needed). It is not fitted in that fold, its fold record carries
  `fit_unsupported` (the sample counts per head), and the selection continues with every other candidate and fold
  (PROTOCOL Amendment A6). Folds that support the candidate are evaluated exactly as before.

**Selection.**
* Statistic: the mean over held-out episodes of Delta_e = V_e(pi_c) - V_e(a_det^{d*}). Both values come from the
  same FQE configuration on the same data.
* Rule: argmax. Ties within 1e-6 go to the simplest candidate: shorter K or window, then larger leaf, then smaller
  beta.
* The selected candidate of each family is deployed whatever the sign. Its estimate and a 90% route-cluster
  bootstrap interval (2000 resamples) are reported.

**Reported, not used for selection.**
* Behaviour calibration: the value model's on-policy value of the logged policy against the Monte Carlo DS of the
  same held-out episodes.
* WPDIS and WDR with the logged propensities, and their effective sample sizes.
* The deviation rate from a_det^{d*} and the agreement with the logged actions.

## 7. Final model and deployment

**Final model.**
* The selected candidate is refit on all training episodes.
* It is distilled into a ReLU MLP 16 -> 32 -> 32 -> 2 (10 inputs for `fqi_nolease`):
  * masked MSE on the supported heads, Adam, 20% validation split, early stopping;
  * normalisation folded into the weights;
  * if greedy agreement with the forest is below 0.98, one retry at 64 -> 64.
* Export: `trainers.export_qnet`. The name `v4_qnet_<sha12>` pins the sha256 of the decision-relevant content
  (features, weights, supported heads, margin, a_det^d).

**Runtime** (`qnet.QUtility`, Eq. 8).
* Called only if |A_feas| = 2.
* Policy budget B_pi = 100 µs. The network is bypassed to a_det^{d*} if:
  * a shield margin is below B_pi;
  * the call overran B_pi (its result is discarded);
  * more than 5% of the last 256 calls overran (the network is disabled for the run).
* Logged: `v4_q_refine`, `v4_q_refresh`, `v4_qnet_s`, `v4_bypass`, `v4_mu`.

## 8. Precisions relative to `framelease_v4/PROTOCOL.md` Sec. 5.5

* **Value-model inputs.** "ExtraTrees on all 16 features" is implemented as the 16 features plus three
  evaluation-only progress covariates. Without them, the value model cannot tell early from late states of an
  episode.
* **Iterations.** "Iterated to convergence" is implemented as Watkins lambda = 1 FQE with a finite number of
  iterations (Sec. 6). Plain one-step FQE stays available (`FQEConfig(trace='one_step')`).
  * On-policy it reproduces the logged DS: on the four pilot episodes, 49.62 / 4.58 / 4.59 / 27.59 against
    49.66 / 4.58 / 4.59 / 27.59.
  * Plain one-step FQE with leaf 5 gave 33.6 / 4.06 / 3.18 / 19.3 without the covariates and 45.8 / 4.12 / 3.18 /
    24.4 with them, i.e. shrinkage compounded over up to 145 steps.
