# FrameLease v3 R&D sprint (2026-11-09 to 2026-11-12): consolidated report

**Version.** Drafted 2026-11-10 at about 03:00 +0800 and re-checked number by number against the sources at about 03:20 +0800, while the closed-loop pilot was running. Updated on 2026-11-10 with the pilot results (§5) and the day-3 checks (§3.9, §3.10, Table 9 rows 29-33). Section 5 was filled from the finished pilot at about 04:10 +0800 (12/12 jobs, exit 0). These are R&D results for a future paper, not for the DAC 2027 submission. No computation was re-run for this report. Every number is copied from the run outputs in Table 0. The only exceptions are numbers marked "(this report)", which are simple arithmetic on cited numbers.

**Conventions.**
- Paths are relative to `/home/kang/Desktop/DAC` unless they are absolute.
- A tag such as [REN §Nested] names a source file from Table 0 and a section inside it.
- Defaults unless stated otherwise:
  - UniDriveVLA depth-1 plans and T_c = 0.5 s.
  - Nested leave-one-clip-out (LOCO) selection with rule (a) at R_cond <= 5%.
  - 95% clip-bootstrap intervals in square brackets.
- In verdict columns, "M" means MARGINAL and "P" means PASS.
- `T` stands for `/tmp/claude-1000/-home-kang/09bd4f19-14e0-4f90-bc47-2e02a3931f54/tasks`.

**Table 0. Source files.**

| tag | file | content |
|---|---|---|
| OUT | `/tmp/fl_extract/FrameLease1109.md` (text extract of `/home/kang/Desktop/NEW/FrameLease1109.docx`) | the 2026-11-09 outline that motivated the sprint (Chinese) |
| G2 | `outputs/framelease_v3/gate2_offline/gate2_20261109/README.md` | G2' gate run |
| VG2 | `T/wwi9aayoo.output`, JSON `result.verify` | independent verifier of G2 |
| RF | `outputs/framelease_v3/gate2_offline/risk_frontier_20261109/README.md` | risk-continuity frontier, nested LOCO, checks J-M |
| LIT | `T/wc41r2ftv.output`, JSON `result.synth` | decision memo of the literature workflow and its "References (verified sources only)" |
| REN | `outputs/framelease_v3/renewal_offline/run_20261110/README.md` and `interpretation.md` | lease renewal study |
| V1 | `T/w9ez2rfn8.output`, JSON `result.renewal.verify` (verifier) and `result.gpu.extend` (extension report) | day-1 workflow results |
| PROF | `outputs/framelease_v3/profiling/run_20261110/report.md` | GPU component profiling |
| EXT | `outputs/framelease_v3/c1_sweep_ext/MERGE_NOTE.json` | held-out data extension |
| TRK | `outputs/framelease_v3/tracking_offline/run_20261110/README.md` | tracking-based lease input |
| PQ | `outputs/framelease_v3/perception_quality/run_20261110/README.md` (+ `interpretation.md`) | perception-quality requirement grid |
| V2 | `T/w20gbxjvt.output`, JSON `result.verify` | day-2 verifier (covers TRK and PQ) |
| FP | `outputs/framelease_v3/fastprefix/run_20261110/README.md` | fast-prefix runtime option and pilot job file |
| PIL | `outputs/framelease_v3/fastprefix/run_20261110/pilot/` (`matrix.json`, `<arm>/runs/<run>/metrics/result.json`, `raw/agent/framelease/summary.json`); `.../pilot_queue/progress.json`, `runner.log` | pilot design and results |
| QS | `outputs/framelease_v3/quality_seeds/run_20261110/` (README.md, cells_summary.csv, iso_line.csv, per_seed_results.csv.gz) | 20-seed robustness of the requirement grid (day 3) |
| MEM | `outputs/framelease_v3/memory_lease/run_20261110/` (README.md, interpretation.md, caveats.md, results.csv, seed_summary.csv, paired_vs_k1.csv) | lease with memory, K-frame certificates (day 3) |
| V3 | `T/w6iaeve21.output`, JSON `result.verify` | day-3 verifier (covers QS and MEM) |

---

## 1. Executive summary

**Question.** The 2026-11-09 outline [OUT §III] chains an action-conditioned, suffix-aligned validity lease (Eq. 1-3) into a real-time feasibility shield (Eq. 5), inside which a light RL policy chooses REFINE or REFRESH. That needs a lease, computed at runtime from the VLA's own perception, that is **trustworthy** (it rarely certifies a plan that runs into a real actor) and **available** (the plan in use stays certified until its successor is released). Does this hold on UniDriveVLA (one RTX 4090 D, Bench2Drive replay), and if not, what binds?

**Gate.** The pre-registered G2' gate (R_marg <= 2%) failed [G2]. The gate used since then is nested-LOCO R_cond <= 5% (point estimate), clip-bootstrap upper 95% bound <= 10%, and continuity >= 85% [LIT §2]. R_cond, the miss rate given a real conflict, is the per-demand quantity that runtime monitors with a fallback keep below ε, conventionally 0.05 (range 0.02-0.10) [2, 3, 20]. The 85% is our application requirement; the oracle reaches 93.1% [G2].

**Verdict: not feasible on UniDriveVLA with its own perception.** With all clips and frames of each study, T_c 0.5 s and standard validity, no configuration that uses the model's detections exceeds 60.3% nested continuity at the 5% selection without memory, or 65.3% with the day-3 five-frame memory plus fast prefix and renewal (Table 9, rows 12 and 33): original lease 15-42% (by conflict definition and data), renewal 44.5-50.8%, Kalman tracking 51.4%, 2x faster prefix 54.5%, fast prefix plus renewal 60.3%. The last assumes a 0.03 s perception pass; the cheapest measured pass takes 59 ms [PROF]. Realized R_cond is 3.5-13.3% (mostly above 5%), and every clip-bootstrap upper bound (12-50%) exceeds 10%. The responsibility-aware definition change (Section 3.3) reaches at most 63.7%, in a hypothetical cell with a 0.3 s release and separate perception hardware [REN §Exploratory].

**Binding constraint: perception quality, above all velocity, together with prefix latency.**
- With ground-truth boxes the same machinery reaches 85.2% (MARGINAL) at the measured 0.896 s release, with the perception pass on separate hardware and aligned with the release [REN]. At a 0.45 s release it reaches 86.3% (MARGINAL), and a PASS of 87.7% at R_cond 3.7% (upper bound 6.4%) without the static V = 0 frames [PQ].
- The pass line is near σ_v <= 0.1 m/s, σ_p <= 0.05-0.1 m and recall >= 0.99 at L_rel 0.45 s (static V = 0 frames excluded). Velocity is the steepest axis: continuity falls 86.3 → 74.4 → 66.1% as σ_v goes 0 → 0.5 → 1 m/s, the other axes perfect [PQ].
- UniDriveVLA's vehicles within 20 m are far from that line [PQ §Where the model's own detections sit]:

  | quantity | UniDriveVLA (RMS) | robust | pass line |
  |---|---|---|---|
  | σ_v | 1.18 m/s | 0.43 m/s (p95 \|e_v\| 3.55 m/s) | <= 0.1 m/s |
  | σ_p | 0.26 m | 0.15 m | <= 0.05-0.1 m |
  | recall | 0.959 | – | >= 0.99 |

  The velocity gap is about 12x on the RMS and 4x on the robust value [PQ §Bottom line 5], or 2.5x with a per-axis MAD (0.25 m/s) [V2].
- At 0.896 s even perfect perception stops at 81.1% (84.0% without the static V = 0 frames) [PQ], so latency is a co-constraint.

**What works.**
- **A 2.1x faster prefix** (SDPA attention, exact GPU image preprocessing, merged LoRA): prefix p50 946 → 439 ms, depth-1 release 962 → 457 ms. Plans move 1-5 cm (2-4x the GPU non-determinism floor, far inside the seed-to-seed spread); boxes stay at the floor. It is an opt-in closed-loop option. In the 12-job CARLA pilot it validated on all 8 fast runs and halved the median action age (1.45 to 0.70 s). In the same pilot the v3 lease (default q95 envelope) failed as predicted offline: median lease 0 s, 89-97% fallback ticks, two of four routes blocked (§5) [FP; PIL].
- **An audited evaluation harness** (nested LOCO, clip bootstrap, four independent check layers). Its constant-lease reference shows that R_marg limits can be gamed: 100% continuity at R_marg 6.9% but R_cond 68.3% [RF].
- **17 new held-out clips**, 32 VAL clips in total [EXT].

**What does not.** Lease renewal (44.5% at realized R_cond 9.6%, gate row [REN]); Kalman tracking (51.4% at 5.1% [TRK]; the decoder's errors are temporally correlated, with a frame-to-frame correlation of 0.66 for the along-heading position error [V2]); anisotropic or motion-conditioned envelopes [G2].

**Day-3 checks (both independently verified [V3]).**
- **20-seed robustness of the requirement grid [QS].** On all frames no grid cell passes in any seed at either latency. At 0.45 s without the static V = 0 frames, PASS holds in at least 80% of seeds only at recall 1, with σ_p <= 0.1 m at σ_v = 0 or σ_p <= 0.05 m at σ_v <= 0.1 m/s. Recall 0.99 is a boundary row that passes in about 65-85% of draws, and only 6 of the 16 single-draw PASS cells are robust. The cell nearest the model fails in all 20 seeds: 65.4 ± 0.7% at 0.45 s and 58.9 ± 0.5% at 0.896 s, all frames. The gap to the line is therefore not sampling noise.
- **Lease with memory, K-frame certificates [MEM].** On degraded ground truth (σ_p 0.05 m, σ_v 0.1 m/s, 0.45 s, static frames excluded), fixing K at 2-3 removes the recall cliff: PASS holds down to recall 0.9 (K = 2) or 0.85 (K = 3), against 0.99 for K = 1. But when the nested selection also chooses K, PASS is rare (0 of 5 seeds at recall 0.85-0.97), and the fixed-K PASS cells clear 85% by only 0.05-0.5 points [V3]. On UniDriveVLA's own detections memory adds a few points (from -11 to +11 across cells), with a best of 63-65%, and all 120 gate cells FAIL.

**Recommended next direction (future paper, not DAC 2027).** Reframe the work as "what perception a driving VLA needs before its actions can be certified at runtime". It would rest on the requirement curve, on the mechanism (detection error at τ = 0 and velocity error dominate; neither renewal nor tracking removes them) and on the fast prefix as the latency enabler. Next steps, in order: (1) a multi-seed rerun of the requirement grid and (2) a lease with memory (multi-frame certificates), both CPU-only on the existing harness; (3) velocity estimation that does not rely on the decoder's single-frame velocity.

---

## 2. Problem and definitions

### 2.1 What the outline needs from the lease

The outline defines the following [OUT §III-A]:
- Suffix margin: M(Δ) = min over τ in [Δ, Δ + T_c] of m(τ) − B(Δ, τ).
- First-failure horizon: H = inf({Δ in [0, H̄] : M(Δ) <= δ} ∪ {H̄}), with H̄ = max(0, T_pred − T_c).
- Deadline: D = t_k + H.
- Proposition 1 gives conditional validity when the envelope B bounds the true margin error. For a statistically calibrated B, the outline requires reporting coverage and failure rates and forbids claiming an unconditional guarantee.

The shield (Eq. 5) admits an action only if its time bounds end before D* [OUT §III-B]. RL ranks actions only when both are feasible. The outline itself warns that a low P_both = P(|A_feas| = 2) limits what RL can show [OUT §IV-B]. The ablation it asks for is that "suffix lease should give a larger usable window at a similar validity risk" [OUT §IV-B].

### 2.2 The lease as implemented

All of the following comes from [G2 §What was computed]; RF, REN, TRK and PQ reuse these kernels.

**Plan and grid.**
- Plan: the depth-d candidate, 6 waypoints at 0.5 ... 3.0 s, so T_pred = 3.0 s.
- Time grid: 0.05 s.

**Margin per relevant detection j.**
- Relevant detections: vehicles and pedestrians with score >= 0.1. Detections with scores of 0.1-0.3 count as real.
- cm_j(τ) = distance between the ego footprint following the plan and the detected box moved at its own (constant) velocity and inflated by B(τ), minus d_safe.
- d_safe = 0.5 m, δ = 0.2 m, T_c in {0.3, 0.5, 1.0} s.

**Lease.**
- H = clip(τ* − T_c, 0, H̄), where τ* is the first time min_j cm_j(τ) <= δ.
- An invalid plan gives H = 0. A frame with no relevant detection gives H = H̄ (2.5 s at T_c 0.5 s).

**Envelopes.**

| name | form |
|---|---|
| E0 | isotropic, B(τ) = v̄τ + ½āτ² + σ |
| E1 | anisotropic along/across-heading tables |
| E2 | E1 per motion state |
| B0 | no envelope |
| quantile sweeps | q80 ... q99.5 in G2; extended down to q30 in RF and q20 in PQ |
| scaled envelopes | λ·B |

Calibration uses matched (confident detection, ground-truth actor) pairs of the other clips (LOCO). Ground truth is used only for calibration and scoring.

### 2.3 Continuity and the need 2 L_rel + 0.05 s

The pipeline is serial:
1. A plan captured at t_k is released after L_rel.
2. The next plan is captured at that release.
3. The next plan is released another L_rel later.

The plan in use must therefore stay certified for need_d = 2 L_rel(d) + 0.05 s.
- At the measured L_rel the need is 1.842 s at depth 1 (L_rel 0.896 s) and 2.104 s at depth 10 (L_rel 1.027 s) [G2].
- With the fast prefix it falls to 0.96 s [FP §3].

Continuity (availability) is defined as follows [REN §Definitions]:
- without renewal: P(H >= need);
- with renewal: the share of plans whose certification chain holds.

The oracle (realized validity) is continuous in 93.1% of depth-1 frames [G2].

### 2.4 Realized validity, conflicts and the two risk measures

**Realized validity V** [RF §Definitions]:
- V is the first τ at which the plan footprint comes within d_safe of a real ground-truth vehicle or walker in the non-reactive replay, censored at 3 s.
- V_suf = clip(V − T_c, 0, H̄).
- A conflict is an uncensored V.
- A miss (over-estimate) is H > V_suf.

**The two risk measures:**
- R_marg = P(H > V_suf) over all frames. This is the original gate's "over-estimation".
- R_cond = P(H > V_suf | conflict) = misses / real conflicts.
- Every over-estimate is a conflict frame, so R_marg = R_cond × P(conflict). P(conflict) is 10.1% at depth 1 (246 of 2447 frames) [RF].

**Two conflict definitions are in use. Their numbers are not interchangeable.**

| definition | used in | conflict | miss |
|---|---|---|---|
| 3 s horizon | G2, RF | uncensored V, as above | H > V_suf |
| execution window | REN, TRK, PQ | plan comes within d_safe of a real actor at some t* in [L', 2L' + T_c] | the scheme still certifies the plan at the decision time s* = max(t* − T_c, L') [REN §Definitions] |

For the same no-renewal lease (25 envelope configurations, nested), the 3 s horizon gives 14.5% at R_cond 7.7%, and the execution window gives 28.3% at 8.8% [REN §Relation to the risk-frontier numbers].

### 2.5 Why R_cond and not R_marg

**Dilution.** About 90% of frames contain no conflict.
- R_marg <= 2% still allows about 20% of real conflicts to be missed.
- R_marg <= 5% allows about half [RF §Session-5 verification].

**Gaming.** A constant lease H = need = 1.842 s for every frame ignores perception entirely. It is 100% continuous at R_marg 6.9 [2.4, 13.0]% while missing R_cond 68.3 [44.0, 84.9]% of conflicts [RF §Bottom line]. R_marg limits of this size do not constrain the lease at all.

**Literature** [LIT §1]:
- Runtime monitors with a fallback limit the conditional false-negative rate and report unnecessary fallbacks separately as the availability cost [2, 3, 20].
- Standards decompose risk per hazardous situation (ISO 21448 Annex C, as summarized by [42]) or per demand (IEC 61508, as summarized by [45]).
- R_marg is the "envelope over-estimation probability" of [19]. It is kept only as a safety performance indicator (SPI) in the sense of the UL 4600 draft [44].

### 2.6 The gate and its literature basis

**Original G2' gate.** Pre-registered on 2026-11-09 afternoon; evaluated under LOCO at T_c 0.5 s, depth 1 [G2 §Verdict].
- PASS if continuity >= 85% with R_marg <= 2% and its upper bound <= 5%.
- MARGINAL if continuity is 70-85% under the same risk limits.
- FAIL otherwise.

**Gate used from 2026-11-09 evening on.** It was set post hoc and is disclosed as such [LIT §2, §4.2].
- PASS if nested-LOCO R_cond <= 5% (point), its clip-bootstrap upper 95% bound <= 10%, and continuity >= 85%.
- MARGINAL if both point estimates pass but the bound does not.
- FAIL otherwise [REN §Definitions].

**Literature basis** [LIT §1-2; only sources from its verified list are cited]:
- ε = 0.05 is the modal level for the class-conditional miss rate of a monitor with fallback (range 0.02-0.10): Luo et al. [2], Sinha et al. [3], Farid et al. [20].
- δ = 0.05 is the convention for trajectory-level coverage (Lindemann et al. [1]).
- The ISO/PAS 8800 use case requires 95% detection in frames that contain a stop sign [43].
- No verified source sets a per-frame limit for stale-plan validity, and none sets an availability floor. The 85% is our requirement (8 points below the 93% oracle) [LIT §0, §2].
- The guarantee is statistical and marginal over calibration draws, not per run or per scenario [6].

**Why the upper bound is 10% and not 5%.** With 15 clips a 5% bound cannot be demonstrated. With zero failures, a 95% bound below 5% needs about 60 independent conflict events [LIT §2, marked there as the memo's own inference]. The evidence floor in RF agrees:
- with zero failures and independent frames, a one-sided 95% binomial bound would be 1.2% for R_cond at depth 1 (246 conflicts);
- the clip bootstrap shows a design effect of about 17;
- so R_cond limits below about 1% cannot be demonstrated offline with 15 clips [RF §Caveats].

**What R_cond is not** [LIT §4.2]:
- R_cond is a component-level SPI, not a per-hour accident rate.
- 5% per demand corresponds only to the low-demand SIL1 band; driving is high-demand, so no SIL can be claimed [45].
- The validity event is "within 0.5 m", not a collision.

**Stale execution.** The verified literature evaluates at most about 0.5 s of stale execution: about 0.3 s in real-time chunking (Black et al. [31]), 0.5 s in [30], and <= 0.2 s in [32]. FrameLease plans are about 0.9 s old at release [LIT §4.2], and 0.46 s with the fast prefix [FP §3].

Note on the memo [LIT]: its frontier recomputation produced no result (the memo's failure statement (B)), so the memo carries no nested numbers. The frontier was completed and verified separately in RF (checks J-M), and RF is the source of every nested risk-frontier number in this report.

### 2.7 Evaluation data

**Model.** UniDriveVLA, the Bench2Drive stage-2 2B configuration [PROF §1]:
- Qwen3-VL ViT and LLM prefix;
- perception expert and sparse decoder;
- flow-matching action expert;
- depth = number of Euler refinement steps (1 or 10).

Hardware: RTX 4090 D with torch 2.5.1+cu124 [PROF header].

**Data.** Offline, open-loop, non-reactive 10 Hz replay of Bench2Drive clips (C1 sweep):

| data set | clips | plans | used by |
|---|---|---|---|
| merged 20-clip sweep `outputs/framelease_v2/c1_sweep/merged_20clips_20261108T0052` | 5 TRAIN + 15 VAL | 2447 frames per depth on the 15 VAL clips after warm-up with 3 s of future ground truth | G2, RF, REN [G2] |
| extension (`merged_37clips_20261109T145344Z`) | 17 more official val clips, 32 VAL clips in total | 5417 depth-1 plans | TRK, PQ [EXT; TRK] |

### 2.8 Nested LOCO and the clip bootstrap

**LOCO.** The envelope used on clip h is calibrated on all other clips (19 clips, or 36 after the extension).

**Nested LOCO selection.** For each held-out clip h:
1. Choose the candidate with maximal pooled continuity subject to pooled R_cond <= α on the other clips.
2. Evaluate it on h.
3. Pool the held-out outcomes.

There are two versions:
- **strict:** the selection clips' envelopes are recalibrated without h (leave-two-out);
- **simple:** the stored LOCO envelopes are used, and those saw h.

RF reports both. REN, TRK and PQ use the simple version [RF §Definitions; REN §Caveats; TRK §Caveats; PQ §Caveats].

**Clip bootstrap.** Percentile 95% intervals, 2000 resamples, seed 20261109, with clips as the resampling units [RF §Definitions].

---

## 3. Results, one subsection per study

### 3.1 G2' gate: suffix lease with tighter envelopes (`gate2_20261109`)

**Setup.**
- 15 VAL clips, 2447 frames per depth, depths 1 and 10.
- Envelope families E0/E1/E2 at q80-q99.5 under LOCO and ORIG (ORIG = calibration on the 5 TRAIN clips).
- 15 LOCO gate candidates, plus E0-orig (the existing v2 parameter file) and the B0 reference.
- CPU only, 89 s wall time [G2].

**Table 1.** Depth 1, T_c 0.5 s. Source: [G2 §Headline table].

| variant | protocol | continuity % [CI] | R_marg % [CI] | over-estimation among conflicts |
|---|---|---|---|---|
| oracle (realized validity) | – | 93.1 | – | – |
| E0 iso q95 | LOCO | 13.9 [6.3, 25.5] | 0.4 [0.0, 1.0] | 4.1% |
| E1 aniso q95 | LOCO | 13.2 [5.9, 24.7] | 0.3 [0.0, 0.8] | 3.3% |
| E2 aniso + motion q95 | LOCO | 13.1 [5.9, 24.2] | 0.4 [0.0, 1.0] | 4.1% |
| E0 iso q80 (best risk-compliant on the grid) | LOCO | 37.8 [16.2, 61.5] | 1.0 [0.0, 2.4] | 10.2% |
| E1 aniso q80 | LOCO | 37.6 [16.8, 60.9] | 0.9 [0.1, 2.2] | 9.3% |
| E2 aniso + motion q80 | LOCO | 37.7 [16.1, 62.5] | 1.0 [0.2, 2.4] | 10.2% |
| E0-orig q95 (v2 file, used by the pilot's FL arm) | ORIG | 31.5 [10.8, 54.8] | 0.8 [0.0, 1.8] | 7.7% |
| B0, no envelope (reference) | – | 86.3 [74.4, 94.5] | 5.0 [2.2, 9.2] | 49.6% |

**Mechanism** [G2 §Verdict]. The envelopes are large because the vehicle containment residual has a heavy tail:
- At τ = 2 s its q95 is 8.9 m along the detected heading and 2.9 m across it.
- 9.4% of pairs exceed 7 m longitudinally.
- Pairs with a velocity error below 1 m/s still have a longitudinal q95 of 7.3 m (true accelerations).
- The τ = 0 detection error ends the lease immediately for parked or queued vehicles 1-2 m from the path.

**Suffix versus global lease** [G2 §Self-tests]. The old global (whole-horizon minimum) lease has a median of 0.00 s and P(H = 0) = 50.1%. The old pointwise lease reaches its 2.0 s cap in 35.3% of frames.

**Verdict.** FAIL at depth 1 and at depth 10. Anisotropic and motion-conditioned envelopes do not beat the isotropic one at matched coverage under LOCO.

**Verification.** [VG2] verdict: CONFIRMED_WITH_CAVEATS, gate verdict supported.
- Independent recomputation reproduces the oracle (93.13%), the E0-orig rows, and E0 q80 LOCO (37.8% at 1.02%).
- **Major caveat:** q80 is the grid edge.
  - Extending the grid downward, E0 q50 LOCO reaches 51.3% [31.7, 71.6] at R_marg 1.88% [0.59, 3.74].
  - The risk-limited frontier is therefore about 45-51%, still far below 70%.
  - Confident detections only: 47.2%. Ignoring rear vehicles: 44.5%.

**Caveats.**
- Open-loop, non-reactive replay with 15 VAL clips.
- Constant-velocity prediction.
- Rear followers end about a quarter of the non-continuous frames.
- PedestrianCrossing_Town13 (477 of 2447 frames) dominates the q95 comparisons [VG2].

### 3.2 Risk frontier and the literature-grounded gate (`risk_frontier_20261109`)

**Setup.**
- 69 candidates: the 32 G2 configurations, 15 new low-quantile LOCO envelopes (E0/E1/E2 at q30-q70) and 22 λ-scaled envelopes (λ·E0 q95 and λ·E1 q95, λ = 0 ... 1).
- Four risk definitions over a grid of α values.
- Rules (a) and (b).
- In-sample versus nested (strict and simple) selection [RF §Definitions].

**Table 2.** Depth 1, T_c 0.5 s. Source: [RF §Bottom line, §Nested summary (strict and simple), §Inverse frontier, §What the remaining misses are].

| quantity | value |
|---|---|
| conflict frames | 246 of 2447 (10.1%) in 10 of 15 clips; 26 with V = 0; 33 with V <= T_c |
| in-sample best continuity, R_cond <= 5% (rule a) | 22.4 [9.8, 36.1]% (`E0_q95_LOCO_x0.9`, R_cond 4.9 [0.0, 14.6]%) |
| **nested strict, R_cond <= 5% (gate statistic)** | **15.4 [6.8, 28.7]% at realized R_cond 7.7 [0.0, 21.0]%**; 3 of 15 held-out clips above α |
| nested simple, R_cond <= 5% | 22.4 [9.8, 36.2]% at 7.7 [0.0, 21.0]% |
| nested strict, rule (b), R_cond <= 5% | 4.9 [0.7, 11.6]% at 1.6 [0.0, 7.5]% |
| nested strict, R_cond <= 10% | 39.2 [17.2, 62.7]% at 11.4 [0.0, 30.8]% |
| lowest R_cond with continuity >= 70% | 35.0 [14.2, 61.3]% (`E1_q40_LOCO`, 70.1%) |
| lowest R_cond with continuity >= 85% | 49.6 [27.2, 78.0]% (B0, no envelope, 86.3%) |
| constant lease H = 1.842 s (reference) | continuity 100%, R_marg 6.9 [2.4, 13.0]%, R_cond 68.3 [44.0, 84.9]% |
| perception-miss floor | 32 of 246 conflicts (13.0%) involve an actor undetected (12) or absent (20) at capture; 9 of the 12 misses at the R_cond 5% point are of this kind |

**Verdict.** Not feasible at literature risk levels. The memo's conclusion is FAIL for any ε in [0.02, 0.20] [LIT §0, §3]. The gate fails on continuity by about 70 points (15.4% against 85%).

**Verification.** Four layers, all PASS [RF §Self-checks, §Session-5 verification]:
- **J:** cross-check from the CSV outputs.
- **K:** independent re-implementation audit, including its own leave-two-out refits.
  - 2400 of 2400 nested fold choices match.
- **L:** resume verification and byte comparison with an earlier run.
- **M:** new code written in a separate session.
  - M2: 0 continuity or over-estimation decisions flip.
  - M4: 2400 of 2400 strict fold choices match.

**Caveats** [RF §Caveats]:
- The in-sample frontier suffers from the winner's curse.
- The CIs condition on the chosen candidates.
- The candidate grid is coarse between q95 and q99.
- Frontier points that sit exactly at a limit are fragile.
- The evidence floor above applies.

### 3.3 Lease renewal with fresh perception (`renewal_offline/run_20261110`)

**Setup** [REN §Definitions]:
- Every Δ, a perception pass re-validates the active plan. The lease restarts at each perception frame.
- On a shared GPU the planner slows to L' = L_rel / (1 − c/Δ), and L_det = c + 0.02 s.
- Grid: Δ in {0.1, 0.2, 0.3} s, c in {0.03, 0.06, 0.10, 0.20} s.
- Phases: late, or aligned (a pass completes at the release). A separate-hardware reference is also run.
- Perception: model detections or oracle ground-truth boxes.
- Validity: standard, or responsibility-aware (RA, a definition change).
- 25 envelope configurations; execution-window conflicts; simple nested selection.

**Feasibility constraint.** The chain must satisfy 2L' + 0.05 <= 3 − T_c, so c/Δ <= about 0.27. Only c = 0.03 s (Δ 0.2 or 0.3 s) and c = 0.06 s (Δ 0.3 s) are feasible [REN §Which renewal settings can be continuous; interpretation item 4].

**Table 3.** Nested continuity % [CI] at realized R_cond % [CI], 15 VAL clips. Source: [REN §Nested leave-one-clip-out selection].

| candidate set | model detections | oracle ground-truth boxes |
|---|---|---|
| no renewal | 28.3 [13.0, 45.1] at 8.8 [0.0, 26.0] | 47.2 [25.7, 68.6] at 6.1 [0.0, 19.0] |
| shared-GPU renewal (pre-specified gate row) | **44.5 [22.9, 66.7] at 9.6 [0.0, 29.0]** (17 misses of 178 conflicts) | 67.6 [47.6, 84.3] at 6.2 [0.0, 18.8] |
| shared GPU, pass aligned with the release | 48.5 [26.0, 69.7] at 9.6 [0.8, 27.1] | 80.8 [62.9, 93.0] at 5.1 [0.0, 16.0] |
| separate hardware, aligned | 44.1 [22.3, 66.3] at 12.2 [0.0, 34.8] | 85.2 [71.9, 94.5] at 4.1 [0.0, 12.4] (MARGINAL) |
| RA validity (definition change), shared aligned | 57.8 [38.7, 75.4] at 10.1 [0.8, 27.5] | 73.3 [56.5, 87.5] at 4.9 [0.0, 15.8] |

The perfect-foresight bound is 93.7% [REN §Bottom line].

**Table 3b.** What if the prefix were faster? An exploratory sensitivity analysis: nested continuity at the 5% selection, at realized R_cond (upper bound). Source: [REN §Exploratory: what if the prefix were faster].

| set | L = 0.896 s | 0.75 s | 0.6 s | 0.45 s | 0.3 s |
|---|---|---|---|---|---|
| model, no renewal | 28.3 at 8.8 (26) | 19.0 at 8.7 (28) | 42.7 at 15.6 (55) | 47.7 at 12.8 (53) | 53.9 at 11.1 (61) |
| model, shared renewal | 44.5 at 9.6 (29) | 44.2 at 8.8 (27) | 44.5 at 14.1 (45) | 48.3 at 13.3 (50) | 55.1 at 10.0 (61) |
| oracle, shared aligned | 80.8 at 5.1 (16) | 85.2 at 4.9 (14) | 86.1 at 6.1 (21) | 89.5 at 4.7 (16) | 91.1 at 6.2 (33) |

**Mechanism** [REN interpretation items 2-3]:
- 65-88% of non-continuous plans are never released, because the first certificate already ends before the release.
- About 97% of the lease-ending agents have a real vehicle within 2 m.
- The model's envelope does not shrink below the detection error at τ → 0. For E2 q95 vehicles it is 1.45 × 0.93 m when moving and 1.61 × 1.40 m when static, whereas the oracle envelope is 0 at τ = 0 [REN §Envelope size].

**Verdict.**
- Gate row: FAIL.
- MARGINAL only with oracle boxes, separate hardware and the aligned phase.
- With model detections, a faster prefix moves the numbers slowly, and realized R_cond is 8.7-15.6% [REN interpretation item 8].

**Verification.**
- **In-run independent re-implementation** [REN §Self-checks; its checks are named V1-V5, not to be confused with the tag V1]:
  - check V1: 8400 world-frame τ* checks, 0 mismatches.
  - check V3: 12810 per-clip counts, 0 differ.
  - check V4: 160 nested rows reproduced (max abs diff 4.9e-7). The gate row with an own bootstrap gives 44.5% [21.6, 66.3] at 9.6% [0.0, 29.3].
- **Verifier [V1]:** CONFIRMED_WITH_CAVEATS. It reproduces the gate row as 44.5% [21.1, 67.3] at 9.6% (17/178). Its six issues are all minor: the wording of the "literal" conflict variant; one headline sentence that contradicts a table row (model/RA/no-renewal reaches 4.5%); rule (b) nested results that depend on the bootstrap seed (28.9% → 6.9% in one row); τ* up to 2.5 ms shorter for heavy-tailed configurations (conservative); one conflict-boundary convention; and the description of the oracle velocity.

**Caveats** [REN §Caveats]:
- The cost model is an assumption: the per-pass cost c is swept, not measured.
- Renewal frames come from the 10 Hz warm-bank sweep.
- Nested selection is the simple version.
- The aligned phase is exploratory.
- The RA numbers rest on a different validity definition and are not safety evidence.

### 3.4 GPU component profiling (`profiling/run_20261110`)

**Setup.**
- Official `forward_test`, bf16 autocast, CUDA events.
- 240 frames over 3 clips (225 with warm banks).
- The machine was loaded (ToDesk, the renewal study, powersave governor, full swap), so ratios are robust and absolute values are not [PROF §2, §10].

**Table 4a.** p50 latency. Source: [PROF §0, §2].

| stage | ms |
|---|---|
| non-preemptible prefix (this session; stored sweep on the same frames: 882.6) | 970.3 |
| LLM prefix (28 layers, 3670 tokens, eager attention) | 373.2 |
| perception expert | 217.1 |
| Qwen3-VL ViT | 141.6 |
| HF image processor on the CPU (in-model) | 109.7 |
| GPU→CPU→PIL→GPU round trip | 41.6 |
| decoder stage 1 / stage 2 | 38.5 / 31.7 |
| one Euler step | 16.0 |
| depth-1 release / full forward | 986.1 / 1132.8 |

**Table 4b.** Perception-only passes. Source: [PROF §0, §2, §4, §9].

| pass | p50 ms | boxes |
|---|---|---|
| P0: prefix without the Euler loop | 972.1 | official (at the run-to-run floor) |
| P1: ViT + decoder stage 1, no LLM | 337.6 | stage-1 boxes; recall vehicles 0.720 vs 0.818 official, pedestrians 0.595 vs 0.919 |
| P1g: P1 with exact GPU preprocessing | 182.8 | same as P1 (99.6% matched) |
| P1f: fresh front camera + cached other cameras | 58.6 | front-35° vehicle recall 0.702 (other cameras 0.5 s stale) vs 0.840 official |
| P2: stage 2 on stage-1 features | 373.5 | unusable (recovers 3% of the official boxes) |

**Table 4c.** Prefix speed-ups, wrapper only. Plan deviation is the depth-10 mean waypoint L2 against the baseline. Source: [PROF §6].

| variant | prefix p50 ms | speed-up | plan deviation p50 / p95 m |
|---|---|---|---|
| baseline | 908.4 | 1.00x | – |
| SDPA attention | 575.6 | 1.58x | 0.014 / 0.058 |
| exact GPU preprocessing | 788.5 | 1.15x | 0.005 / 0.012 |
| both | 456.3 | 1.99x | 0.015 / 0.062 |
| both + LoRA merged | 435.5 | 2.09x | 0.017 / 0.060 |
| GPU non-determinism floor (baseline repeated) | 913.5 | – | 0.005 / 0.015 |
| model sampling spread (other seed) | 919.7 | – | 0.532 / 1.825 |

**Interleaving** [PROF §8]:
- RENEW (P1g) interleaved in one process on the default stream stretches the official plan forward from 1098 to 1439 ms.
- It achieves only one RENEW per ~0.48-0.53 s, whatever Δ is requested.
- A second CUDA stream crashed, because `deformable_aggregation` launches on the legacy default stream.

**Verdict.**
- Perception is only partially separable.
- An exact RENEW costs a whole prefix and is infeasible at Δ <= 0.3 s.
- A 2x prefix speed-up is available with centimetre-level plan deviation.

**Verification.**
- Built-in exactness checks against the run-to-run floor [PROF §3].
- This run was not reviewed by a separate verifier agent: the day-1 workflow result has no verify block for it [V1 file].
- The speed-up was re-measured in the separate FP run (prefix 2.14x).

**Caveats.**
- The machine was loaded (see Setup).
- P1/P1g box quality comes from 3 clips and is indicative only.
- RENEW passes ran from the official 10 Hz bank state, which a deployment would not have [PROF §10].

### 3.5 Held-out data extension (`c1_sweep_ext`)

**Setup** [EXT `selection_rule`, `sweep_settings`, `caveats`]:
- The selection rule was frozen before any download: official Bench2Drive val, not in the released UniDriveVLA training annotation, ranked by ability tier.
- Sweep: the unchanged `framelease_v2/c1_depth_sweep.py` (sha256 e8ee541e...), sequential, bank-hz 10, seed 11.
- Only annotations, expert assessments and the 6 RGB cameras were kept.

**Table 5.** Source: [EXT `n_new_clips`, `new_frames`, `conflict_counts`, `pending_sweeps`, `not_acquired`, `views`].

| item | value |
|---|---|
| new clips swept | 17 official val clips, 3565 frames |
| views | `merged_37clips_20261109T145344Z` (20 + 17); `ext_only_17clips_20261109T145344Z` (pure held-out) |
| depth-1 conflicts on the new clips | 663 of 2970 frames, in 13 clips; detection status of the conflict actors: confident 576, low-confidence 55, undetected 28, absent 4 |
| comparison | the original 15 VAL clips have 246 conflicts in 2447 frames |
| BlockedIntersection_Town03_Route135 | 300 conflicts, 232 of them V = 0 with the ego stationary; the ego is stopped about 0 m behind a stopped car on a ~22° slope (slope-aligned gap −0.06 m) |
| pending | 14 clips, 4174 frames, sweep `PAUSED_DISK`; resuming needs >= 12.375 GiB free |
| not acquired | 4 large archives (disk reserve) |

**Verdict.** PARTIAL [V1 `result.gpu.extend.status`]. 17 clips are usable, and the statistical power is much higher (more conflicts).

**Verification.**
- Per-clip validation: `clips_failed_validation` is empty. Three clips carry tilt flags: road grade makes their GT-yaw and world-versus-LiDAR ADE checks differ, while centres and sizes agree exactly [EXT `flags`, `flag_explanation`].
- The conflict counter reproduces the 15-clip reference exactly (`conflicts/check_15val.json`).
- The day-2 verifier independently reproduced the 32-clip plan and conflict counts: 5417 plans, 268 static V = 0 plans, 531 conflicts [V2].

**Caveats** [EXT `caveats`; V2]:
- Full pretraining exposure of the checkpoint cannot be proven.
- The timing fields were recorded under load.
- Three clips are slope-flagged.
- 36 of the 268 static V = 0 plans lie outside BlockedIntersection, so "slope artifact" is not an exact label.

### 3.6 Tracking-based lease input (`tracking_offline/run_20261110`)

**Setup** [TRK §Tracker, §Envelopes, §Definitions]:
- Constant-velocity Kalman filter per track, tuned on TRAIN only. The tuning switched coasting off.
- Inputs:
  - (a) raw detections;
  - (b) tracks updated at plan frames only;
  - (c) tracks updated at every 10 Hz frame.
- Envelopes: E0/E1/E2, plus covariance-normalized conformal envelopes (CNi isotropic, CNa anisotropic).
- 32 VAL clips with 36-clip LOCO.
- The primary cell was declared before stage B.

**Table 6.** Nested continuity % at realized R_cond % (upper bound), all 32 VAL clips. Source: [TRK §Bottom line, §Nested].

| input | no renewal | shared-GPU renewal | aligned renewal |
|---|---|---|---|
| (a) raw detections | 41.6 at 5.5 (15.2) | 46.7 at 7.7 (17.8) | 50.8 at 5.6 (13.2) |
| (b) tracks at plan frames | 41.2 at 6.2 (16.1) | – | – |
| (c) tracks at 10 Hz | 40.8 at 6.6 (16.3) | **51.4 [37.7, 66.0] at 5.1 [0.9, 12.6]** (primary cell; 24 misses of 469 conflicts) | 58.8 at 7.5 (16.4) |

**Paired differences, (c) − (a), 5% selection** [TRK §Tracks versus raw detections]:

| candidate set | difference [CI] |
|---|---|
| no renewal | −0.7 [−2.7, +1.1] |
| shared renewal | +4.7 [+2.1, +7.9] |
| aligned renewal | +8.0 [+3.4, +13.1] |

**Why filtering does not help** [TRK interpretation item 4; §Tracker]. On TRAIN, for the same population, the tracked residuals equal the raw ones:

| quantity (moving vehicles) | raw detections | 10 Hz tracks |
|---|---|---|
| longitudinal q95 at τ = 0 | 1.07 m | 1.10 m |
| longitudinal q95 at 1 s | 2.79 m | 2.85 m |
| longitudinal q95 at 2 s | 8.05 m | 8.11 m |
| velocity-error q95 | 2.18 m/s | 2.02 m/s |

Tracking halves the false agents (0.264 → 0.133 per ground-truth actor at recall 0.894 vs 0.892). But 97% of the lease-ending agents are real vehicles within 2 m, so this barely matters.

**Verdict.** FAIL in all 70 gate cells; none is MARGINAL. The primary cell misses the continuity requirement by about 34 points.

**Verification.** [V2] verdict: CONFIRMED_WITH_CAVEATS.
- The raw-detection baseline is reproduced exactly (525 candidate rows, identical counts).
- An independently written tracker gives 48.8% at R_cond 7.2% in the primary cell.
- No envelope choice can rescue the tracks: with no envelope at all (B0) they reach 77.5% (late phase) and 85.3% (aligned) in-sample, at R_cond 29.2% and 29.0%.
- Caveats kept from V2:
  - The 8-point aligned gain comes entirely from the CNa envelope family, which only the tracked input has. Without the CN families, tracks reach 48.7% against 50.8% for raw detections.
  - The late-phase gain shrinks to +2.1 points with the independent tracker.
  - The +9.8 / +10.5-point no-renewal gains in the "without both" subset are selection artifacts.
  - Nested selection is the simple version.

**Caveats** [TRK §Caveats]:
- Input (c) assumes a full perception pass at every 10 Hz frame, which the profiling did not find on one GPU, so the tracked-renewal numbers are upper bounds.
- The CN box-extent floor was introduced after inspecting a pooled quantile, before any lease result existed.

### 3.7 Perception-quality requirement grid (`perception_quality/run_20261110`)

**Setup** [PQ §Definitions]:
- Ground-truth boxes are degraded with common random numbers (seed 20261110):
  - per-axis position noise σ_p;
  - per-axis velocity noise σ_v;
  - independent per-actor-frame recall r, or the model's measured range-dependent recall profile.
- Size and heading are exact, and there are no false positives.
- Data: 32 VAL clips, 5417 plans.
- Schedules: no renewal and SA_D0.2_c0.03 (shared GPU, aligned, Δ 0.2 s, c 0.03 s).
- Release latencies: L_rel 0.896 and 0.45 s.
- Envelopes: B0, E0 and E2 at q50-q99.5, LOCO-calibrated on the degraded stream.
- Selection: simple nested at R_cond <= 5%.

**Table 7a.** Renewal candidate set. Cells give continuity % (realized R_cond % / upper bound %) and the verdict. Source: [PQ §Main table, §Refinement around the boundary, §Where the model's own detections sit].

| cell (σ_p m, σ_v m/s, recall) | 0.896 s, all frames | 0.45 s, all frames | 0.45 s, static V = 0 frames excluded |
|---|---|---|---|
| perfect (0, 0, 1) | 81.1 (3.9/8.0) FAIL | 86.3 (4.1/13.5) M | 87.7 (3.7/6.4) P |
| (0.05, 0.1, 0.99) | 78.4 (3.9/8.1) | 82.1 (5.1/13.5) | 85.7 (3.7/6.4) P |
| (0.1, 0, 1) | 77.5 (3.5/7.5) | 85.1 (4.3/13.5) M | 85.3 (2.9/5.5) P |
| (0, 0.2, 1) | 77.6 (2.6/6.7) | 81.3 (4.5/14.9) | 84.6 (2.6/4.8) |
| (0, 0.5, 1) | 70.0 (2.4/7.0) | 74.4 (1.4/4.0) | – |
| (0, 1, 1) | 60.2 (2.4/6.7) | 66.1 (1.4/4.0) | – |
| (0.25, 0, 1) | 72.3 (3.5/7.4) | 77.4 (1.6/5.0) | – |
| (0, 0, 0.95) | 69.6 (4.8/9.1) | 72.3 (4.9/7.1) | 76.5 (4.8/7.7) |
| (0, 0, 0.9), single draw | 50.5 (5.4/7.8) | 20.5 (5.1/7.8) | – |
| near the model: (0.25, 1, model profile) | 58.8 (3.7/8.4) | 65.4 (2.1/3.7) | – |
| model's own detections, same pipeline | 50.6 (5.2/12.4) | 60.3 (3.5/13.9) | 56.9 (5.9/14.8) |

**Where the model sits** [PQ §Where the model's own detections sit]. All 37 clips, score >= 0.1, matched within 2 m:

| class, range | σ_p RMS (robust) | σ_v RMS (robust) | recall |
|---|---|---|---|
| vehicles, 0-20 m | 0.26 m (0.15) | 1.18 m/s (0.43) | 0.959 |
| vehicles, 0-30 m | 0.37 m | 1.20 m/s | 0.888 |
| pedestrians, 0-20 m | 0.33 m | 0.35 m/s | 0.967 |

**Per-axis sensitivity** at 0.45 s, all frames, other axes perfect [PQ §Bottom line 3]:

| axis | values | continuity % |
|---|---|---|
| velocity σ_v (m/s) | 0 / 0.1 / 0.2 / 0.3 / 0.5 / 1 / 2 | 86.3 / 85.8 / 81.3 / 78.7 / 74.4 / 66.1 / 55.9 |
| position σ_p (m) | 0 / 0.05 / 0.1 / 0.15 / 0.2 / 0.25 / 0.5 / 1 | 86.3 / 85.7 / 85.1 / 80.5 / 78.9 / 77.4 / 70.8 / 64.9 |
| recall r | 1 / 0.99 / 0.97 / 0.95 / 0.9 / 0.85 / 0.8 / 0.7 | 86.3 / 84.0 / 83.7 / 72.3 / 20.5 / 0.9 / 0 / 0 |

Noise is paid in continuity, while missed actors are paid in risk [PQ §Bottom line 3]. For a fixed candidate, R_cond rises from 1.2% to 29.4% as r falls from 1 to 0.7. The perfect-foresight bound is 90-95% [PQ §Bottom line 6, §Diagnostics].

**Verdict** [PQ §Bottom line; §Where the gate passes]:
- No grid cell passes on the full data.
- A PASS region exists only without the static V = 0 frames (or without BlockedIntersection), only at 0.45 s, and only for near-ground-truth perception: σ_v <= ~0.1 m/s, σ_p <= 0.05-0.1 m, recall >= 0.99.
- With the envelope family extended below q50, the line moves by about one grid step, i.e. ±0.1-0.2 m/s in σ_v.

**Verification.** [V2] verdict: CONFIRMED_WITH_CAVEATS.
- The perfect point is reproduced exactly: 81.1 / 84.0 / 83.6 at 0.896 s, and 86.3 M / 87.7 P / 87.2 P / 87.5 P at 0.45 s.
- The model reference is reproduced exactly (50.6% and 60.3%).

**Caveats kept from V2.**
- **The boundary cells and the low-recall cells come from a single random draw; seed variance is not reported.**
  - (0.25, 0.5, 0.9) at 0.45 s gives 12.8% with the study's seed, and 4.9% and 58.2% with two other seeds.
  - Without BlockedIntersection, the boundary cell (0.05, 0.1, 0.99) gives 85.0 / 84.6 / 85.1 / 84.98 over 4 seeds, so it flips between PASS and FAIL.
  - Without the static frames, it passes in all 4 seeds, but only by 0.5-0.7 points.
- **The recall cliff is partly a design artifact of single-frame certificates.** A certificate trusts one frame and has no memory, so independent per-frame drops add about 1 − r to R_cond.
- The robust σ values depend on the estimator: a per-axis MAD gives σ_v 0.25 m/s and σ_p 0.12 m.
- Nested selection is the simple version.
- The PASS cells sit 0.0-2.7 points above 85%, and their continuity CIs reach down to about 77%.

**Caveats from PQ itself** [PQ §Caveats]:
- The synthetic noise is white, isotropic and Gaussian, and the grid has no false positives.
- The constant-velocity predictor is fixed, so the grid measures what better perception buys with this predictor.
- SA_D0.2_c0.03 assumes a 0.03 s pass, but the cheapest measured pass takes 0.059 s.

### 3.8 Fast-prefix runtime option (`fastprefix/run_20261110`)

**Setup** [FP §1-3]:
- The three wrapper-level optimizations of PROF are packaged as an opt-in option for the v2/v3 closed loop: `run_closed_loop_fast.py --fast-prefix sdpa,gpu_preproc,lora_merged`.
- The base agent classes and the timeline accounting are unchanged.
- An upstream-hash contract pins the replaced functions.
- A validation runs inside the discarded warm-up pass.
- Equivalence was measured on 269 warm frames from 6 VAL clips, with two model copies interleaved frame by frame.

**Table 8.** Source: [FP §Bottom line, §2, §3, §4].

| quantity | baseline | fast prefix | controls |
|---|---|---|---|
| prefix p50 / p95 / p99 ms | 946 / 1164 / 1212 | 439 / 571 / 596 | paired speed-up 2.14x |
| depth-1 release p50 ms | 962 | 457 | 2.09x |
| full forward p50 ms | 1114 | 611 | 1.80x |
| continuity need 2 L_rel + 0.05 s | 1.97 s | 0.96 s | – |
| plan deviation, depth 1, mean-waypoint L2 p50 / p95 | – | 0.019 / 0.049 m | floor 0.009 / 0.025; seed spread 0.123 / 0.333 |
| plan deviation, depth 10 | – | 0.011 / 0.042 m | floor 0.004 / 0.011; seed spread 0.320 / 0.935 |
| boxes recovered, score >= 0.3 / >= 0.1 | – | 99.3% / 95.5% | floor 98.9% / 95.8% |
| peak extra GPU memory of a forward, p50 | 2.82 GiB | 1.10 GiB | – |
| agent smoke (real model, no CARLA) | – | PASS for the v2 and v3 bases; charged prefix p50 427 / 428 ms | – |

**Verdict.**
- NOT_APPLICABLE to the lease gate: this is runtime engineering.
- It works as designed.
- On its own it does not make the model-detection lease pass (Table 3b, Table 7a).

**Verification.**
- 23 CPU tests, including:
  - an identical simulated timeline to the base agent given the same costs;
  - a GPU-preprocessing replica that is bit-identical to the HF processor.
- Equivalence judged against floor and seed-spread controls.
- An agent smoke run.
- `pilot_jobs.py --check`.
- No separate verifier agent reviewed this run. Its latency gain agrees with the independently measured PROF value (908 → 436 ms prefix) [FP §3].

**Caveats** [FP §7]:
- The fast path is not bit-identical: SDPA and the merged LoRA change the numerics.
- The in-run SDPA check rule was changed twice, both times before any equivalence result was looked at (disclosed).
- Latency was measured on a loaded machine (load average p50 8.3).
- The LoRA merge is irreversible inside a running process.
- GPU contention with CARLA was not measured.

---


### 3.9 Multi-seed robustness of the requirement grid (`quality_seeds/run_20261110`)

**Setup.** Twenty independent perception draws went through the original grid pipeline, imported unchanged except for an
exact, faster replica of the E2 LOCO fit. Each draw covers all 38 (σ_p, σ_v) combinations × 9 recall settings, at L_rel
0.896 and 0.45 s, on all frames and without the static V = 0 frames. Within a seed every cell shares the same random
numbers. With the original seed, the pipeline reproduces the published grid row by row (10,944 rows) [QS].

**Table 10.** Nested continuity %, mean ± sd over 20 seeds, and the share of seeds that PASS / MARGINAL / FAIL. Settings:
selection at R_cond <= 5%, 32 VAL clips, renewal candidate set [QS `cells_summary.csv`].

| cell (σ_p m, σ_v m/s, recall) | 0.45 s, all frames | 0.45 s, no static V = 0 |
|---|---|---|
| (0, 0, 1) perfect | 86.3 ± 0.0; 0/100/0 | 87.7 ± 0.0; 100/0/0 |
| (0.05, 0, 1) | 85.8 ± 0.1; 0/90/10 | 86.5 ± 0.1; 100/0/0 |
| (0.1, 0, 1) | 85.1 ± 0.8; 0/70/30 | 85.4 ± 0.2; 95/0/5 |
| (0.05, 0.1, 1) | 85.5 ± 0.2; 0/95/5 | 85.7 ± 0.1; 100/0/0 |
| (0.1, 0.1, 1) | 83.9 ± 1.7; 0/35/65 | 84.8 ± 0.2; 5/0/95 |
| (0, 0.2, 1) | 83.2 ± 1.8; 0/5/95 | 84.4 ± 0.2; 0/0/100 |
| (0, 0, 0.99) | 85.0 ± 1.1; 0/45/55 | 86.3 ± 2.5; 65/0/35 |
| (0, 0, model recall profile) | 84.2 ± 0.8; 0/15/85 | 85.0 ± 3.6; 40/0/60 |
| (0, 0, 0.95) | 66.5 ± 9.3; 0/0/100 | 72.4 ± 7.1; 0/0/100 |
| (0, 0, 0.9) | 25.0 ± 17.7; 0/0/100 | 48.5 ± 14.3; 0/0/100 |
| (0.25, 1, model profile), nearest the model | 65.4 ± 0.7; 0/0/100 | 68.2 ± 1.1; 0/0/100 |

At 0.896 s no cell passes in any seed; the best is 84.0% (perfect perception, static frames excluded) [QS].

**Verdict.** The σ_p and σ_v limits of §3.7 hold. The recall requirement tightens from ">= 0.99" to "about 1, with 0.99
borderline". At recall <= 0.9 the single-draw values of §3.7 are draw noise (seed sd 9-18 points) and should not be read
cell by cell. The model-nearest cell fails in every seed.

**Verification [V3].** An independent recomputation of 2 cells × 3 new seeds × 2 latencies × 4 data subsets (48 rows) is
identical to `per_seed_results.csv.gz`, with identical verdicts. The verifier adds two qualifications. First, the
recall-0.99 cells cannot be ranked against each other with 20 seeds. Second, a further draw from the memory study passes
at recall 0.95, so "never" in [QS] means "in none of its 20 seeds".

**Caveats.** The synthetic perception has white, isotropic noise and independent drops, with no false positives. The seeds
vary only the perception draw, not the clips. P(PASS) from 20 draws has wide Wilson intervals. The PASS boundary at 0.45 s
comes down to about 3 misses out of 273 conflicts. The run directory had no README; the coordinating session saved the
agent's report as README.md on 2026-11-10.

### 3.10 Lease with memory: K-frame certificates (`memory_lease/run_20261110`)

**Setup.** The certificate for the active plan uses every actor detected in any of the last K perception frames (K = 1, 2,
3, 5). Each actor is propagated at constant velocity from its last detection, and its envelope is evaluated at the full
age of that evidence, so older evidence costs more margin. Duplicate detections are either merged by a gated association
(2 m gate) or all kept. The memory is evaluated on degraded ground truth (5 seeds) and on the model's own detections, with
and without renewal, at L_rel 0.896 and 0.45 s, with nested LOCO at R_cond <= 5% [MEM].

**Table 11.** Main results [MEM `results.csv`, `seed_summary.csv`, `paired_vs_k1.csv`; V3].

| perception | L_rel | frames | K = 1 | with memory | verdict |
|---|---|---|---|---|---|
| degraded GT (σ_p 0.05 m, σ_v 0.1 m/s) | 0.45 s | no static V = 0 | PASS 5/5 only at recall >= 0.99 (85.6%) | K = 2: PASS 5/5 at recall 0.9 (85.3%, R_cond 4.2%, upper 7.2%) but 4/5 at 0.95; K = 3: PASS 5/5 down to 0.85 (85.1%) | PASS only for a fixed K |
| same, K chosen by the nested selection | 0.45 s | no static V = 0 | - | PASS in 0/5 seeds at recall 0.97, 0.9 and 0.85; 1/5 at 0.95; 3/5 at recall 1 [V3] | mostly FAIL |
| same | 0.45 s | all frames | MARGINAL 5/5 only at recall 1 (upper bound 13.8%) | MARGINAL down to 0.97 (K = 2) or 0.95 (K = 3) | MARGINAL |
| degraded GT, σ_p 0.1 m | 0.45 s | both | <= 84.8% | holds 84.6% down to recall 0.9, no PASS | FAIL |
| degraded GT, either noise level | 0.896 s | both | <= 81.4% | <= 81.4% | FAIL |
| UniDriveVLA, renewal set | 0.896 s | all | 50.6% at R_cond 5.2% | K = 2: 55.1% at 5.0% (paired +4.5 [+2.1, +7.4]); K = 5 kept: 60.3% at 3.9% | FAIL |
| UniDriveVLA, renewal set | 0.896 s | no static V = 0 | 53.2% at 5.4% | K = 5 kept: 63.1% at 4.1% [0.0, 9.9] | FAIL |
| UniDriveVLA, renewal set | 0.45 s | all | 60.3% at 3.5% | K = 5 kept: 65.3% at 5.0% (upper 14.0%); K = 3 kept: 66.9% at 8.0% | FAIL |
| UniDriveVLA, no renewal | 0.896 / 0.45 s | all | 40.8% / 54.5% | K = 2 kept: 44.3% / 64.6% | FAIL |

**Verdict.** Memory does what single-frame certificates cannot: on degraded ground truth with independent drops it
removes the recall cliff, but only for a K fixed in advance. With K selected, and with margins of 0.05-0.5 points, that
PASS is fragile. On the model's own detections all 120 gate cells FAIL. The change from K = 1 ranges from -11.2 to
+10.6 points, and at 0.45 s the gains (+1.3 to +6.7) come with realized R_cond of 5.0-8.0% [V3]. The binding constraint
stays σ_v and σ_p, not recall.

**Verification [V3].** The verifier wrote its own memory stage from `definitions.md` alone. It reproduced the K = 3
degraded-GT and model cells and confirmed causality (only past frames are used), the evidence-age envelope growth and the
deduplication rule. Its major caveat is the post-hoc K choice described above.

**Caveats.** Independent synthetic drops are the best case for memory, because real misses are correlated over time
(occlusion). The memory frames for the model come from the 10 Hz warm-bank sweep. The renewal schedule assumes a 0.03 s
perception pass, while the cheapest measured pass takes 0.059 s. Envelope tables are extrapolated beyond 3 s for old
evidence without renewal.

## 4. Synthesis

**Table 9.** Best nested continuity at the R_cond <= 5% selection, with realized R_cond, for every configuration. All rows use depth 1, T_c 0.5 s and rule (a).
- Gate: PASS needs continuity >= 85%, realized R_cond <= 5% and its upper bound <= 10%. MARGINAL means both point estimates pass but the upper bound does not.
- M* = MARGINAL by the gate rule applied in this report; the source reports the numbers without a verdict.
- "upper" = clip-bootstrap upper 95% bound of R_cond.

| # | configuration | perception | L_rel (s) | data | nested continuity % | realized R_cond % | gate | source |
|---|---|---|---|---|---|---|---|---|
| 1 | original lease, 69 envelope candidates | model | 0.896 | 15 VAL, 3 s horizon, strict nested | 15.4 [6.8, 28.7] | 7.7 [0.0, 21.0] | FAIL | RF §Nested summary |
| 2 | original lease, 25 envelope configurations | model | 0.896 | 15 VAL, execution window | 28.3 [13.0, 45.1] | 8.8 [0.0, 26.0] | FAIL | REN §Nested |
| 3 | original lease, 36-clip LOCO envelopes | model | 0.896 | 32 VAL | 41.6 [27.8, 56.8] | 5.5 [1.5, 15.2] | FAIL | TRK §Nested |
| 4 | renewal, shared GPU (gate row) | model | 0.896 | 15 VAL | 44.5 [22.9, 66.7] | 9.6 [0.0, 29.0] | FAIL | REN §Nested |
| 5 | renewal, pass aligned with the release | model | 0.896 | 15 VAL | 48.5 [26.0, 69.7] | 9.6 [0.8, 27.1] | FAIL | REN §Nested |
| 6 | renewal aligned + responsibility-aware validity (definition change) | model | 0.896 | 15 VAL | 57.8 [38.7, 75.4] | 10.1 [0.8, 27.5] | FAIL | REN §Nested |
| 7 | renewal, shared GPU | model | 0.896 | 32 VAL | 46.7 [33.1, 61.5] | 7.7 [1.9, 17.8] | FAIL | TRK §Nested |
| 8 | renewal, aligned | model | 0.896 | 32 VAL | 50.8 [37.6, 64.5] | 5.6 [1.2, 13.2] | FAIL | TRK §Nested |
| 9 | Kalman tracks (10 Hz) + shared renewal (primary cell) | model, tracked | 0.896 | 32 VAL | 51.4 [37.7, 66.0] (independent tracker: 48.8 [V2]) | 5.1 [0.9, 12.6] (7.2 [V2]) | FAIL | TRK §Nested |
| 10 | Kalman tracks + aligned renewal (CNa envelope) | model, tracked | 0.896 | 32 VAL | 58.8 [46.0, 71.7] | 7.5 [1.9, 16.4] | FAIL | TRK §Nested |
| 11 | fast prefix, no renewal | model | 0.45 | 32 VAL | 54.5 [41.5, 68.5] | 4.1 [0.7, 18.0] | FAIL | PQ §model's own detections |
| 12 | fast prefix + aligned renewal (assumes c = 0.03 s) | model | 0.45 | 32 VAL | 60.3 [47.4, 73.5] | 3.5 [0.5, 13.9] | FAIL | PQ §model's own detections |
| 13 | fast prefix + shared renewal | model | 0.45 | 15 VAL | 48.3 [25, 71] | 13.3 (upper 50) | FAIL | REN §faster prefix |
| 14 | oracle boxes, no renewal | ground truth | 0.896 | 15 VAL | 47.2 [25.7, 68.6] | 6.1 [0.0, 19.0] | FAIL | REN §Nested |
| 15 | oracle boxes, aligned shared renewal | ground truth | 0.896 | 15 VAL | 80.8 [62.9, 93.0] | 5.1 [0.0, 16.0] | FAIL | REN §Nested |
| 16 | oracle boxes, aligned renewal on separate hardware | ground truth | 0.896 | 15 VAL | 85.2 [71.9, 94.5] | 4.1 [0.0, 12.4] | M | REN §Nested |
| 17 | oracle boxes, aligned shared renewal | ground truth | 0.45 | 15 VAL | 89.5 [79, 97] | 4.7 (upper 16) | M* | REN §faster prefix |
| 18 | grid: perfect boxes (0, 0, 1), renewal set | ground truth | 0.896 | 32 VAL, all frames | 81.1 | 3.9 (upper 8.0) | FAIL | PQ §Main table |
| 19 | grid: perfect boxes (0, 0, 1) | ground truth | 0.45 | 32 VAL, all frames | 86.3 | 4.1 (upper 13.5) | M | PQ §Main table |
| 20 | grid: perfect boxes (0, 0, 1) | ground truth | 0.45 | 32 VAL, static V = 0 excluded | 87.7 | 3.7 (upper 6.4) | P | PQ §Refinement |
| 21 | grid: (0.05 m, 0.1 m/s, 0.99) | degraded ground truth | 0.45 | 32 VAL, static V = 0 excluded | 85.7 | 3.7 (upper 6.4) | P (margin 0.7 pt) | PQ §Refinement |
| 22 | grid: (0.1 m, 0, 1) | degraded ground truth | 0.45 | 32 VAL, all frames | 85.1 | 4.3 (upper 13.5) | M | PQ §Main table |
| 23 | grid: (0, 0.5 m/s, 1) | degraded ground truth | 0.45 | 32 VAL, all frames | 74.4 | 1.4 (upper 4.0) | FAIL | PQ §Main table |
| 24 | grid: (0, 1 m/s, 1) | degraded ground truth | 0.45 | 32 VAL, all frames | 66.1 | 1.4 (upper 4.0) | FAIL | PQ §Main table |
| 25 | grid: (0, 0, recall 0.95) | degraded ground truth | 0.45 | 32 VAL, all frames | 72.3 | 4.9 (upper 7.1) | FAIL | PQ §Main table |
| 26 | grid: (0, 0, recall 0.9), single draw | degraded ground truth | 0.45 | 32 VAL, all frames | 20.5 | 5.1 (upper 7.8) | FAIL | PQ §Main table |
| 27 | grid near the model: (0.25 m, 1 m/s, model recall profile) | degraded ground truth | 0.45 | 32 VAL, all frames | 65.4 | 2.1 (upper 3.7) | FAIL | PQ §Main table |
| 28 | model's own detections through the grid pipeline | model | 0.896 | 32 VAL, all frames | 50.6 [36.9, 64.9] | 5.2 [1.1, 12.4] | FAIL | PQ §model's own detections |

| 29 | grid nearest the model, 20 seeds | degraded ground truth | 0.45 | 32 VAL, all frames | 65.4 ± 0.7 (seed sd) | - | FAIL in 20/20 seeds | QS |
| 30 | grid (0, 0, 0.99), 20 seeds | degraded ground truth | 0.45 | 32 VAL, static V = 0 excluded | 86.3 ± 2.5 (seed sd) | - | PASS in 13/20 seeds | QS |
| 31 | memory lease K = 2 (fixed), (0.05 m, 0.1 m/s, recall 0.9) | degraded ground truth | 0.45 | 32 VAL, static V = 0 excluded | 85.3 | 4.2 (upper 7.2) | P in 5/5 seeds (fixed K only) | MEM |
| 32 | memory lease K = 5 kept + renewal | model | 0.896 | 32 VAL, all frames | 60.3 | 3.9 [0.0, 9.7] | FAIL | MEM |
| 33 | memory lease K = 5 kept + renewal | model | 0.45 | 32 VAL, all frames | 65.3 | 5.0 (upper 14.0) | FAIL | MEM |

**How to read Table 9.**
- Moving down the model-detection rows (1-13), every mechanism adds a few points. The best row (60.3%) is still about 25 points short of 85%. The day-3 memory lease (rows 32-33) reaches 65.3%, about 20 points short.
- Replacing the model's boxes with ground truth (rows 14-20) adds 19-41 points at the same schedule and data (this report: row pairs 2/14, 5/15, 28/18 and 12/19, and the separate-hardware pair of Table 3).
- Degrading ground truth back toward the model's error levels (rows 21-27) removes those points again, fastest along the velocity axis.

**Why perception error dominates.**
- The lease certifies the plan against the model's own boxes, extrapolated at constant velocity and inflated by an envelope. Without renewal the certificate must reach τ = need + T_c = 2.34 s at the measured latency (this report: 1.842 + 0.5 s). The envelope must cover three error sources:
  - the detection error at τ = 0;
  - the velocity error, which grows linearly with τ;
  - the actors' real accelerations, which no constant-velocity prediction captures.
- The model's per-axis velocity error is 1.18 m/s RMS, with a p95 speed error of 3.55 m/s [PQ]. Over 2.34 s this alone shifts the extrapolated box by about 2.8 m (RMS) and 8.3 m (p95) (this report: 1.18 × 2.342 and 3.55 × 2.342).
- The measured vehicle containment residual at τ = 2 s has a longitudinal q95 of 8.9 m. For pairs with a velocity error below 1 m/s it is still 7.3 m, so real accelerations add a tail of similar size [G2].
- The grid separates the two sources [PQ]. With exact boxes and velocities, only prediction error remains, and the same machinery reaches 81-88% (perfect-foresight ceiling 90-95%). Adding the model's level of velocity noise alone (σ_v = 1 m/s) costs about 20 points (86.3 → 66.1% at 0.45 s, 81.1 → 60.2% at 0.896 s).
- An envelope large enough for these errors touches the planned footprint early in most frames, while a small envelope misses conflicts.
- At τ → 0 the envelope cannot fall below the detection error (E2 q95 vehicles: 1.45 × 0.93 m moving, 1.61 × 1.40 m static) [REN]. Queued or parked cars near the path therefore end the lease at every frame, and 65-88% of the non-continuous plans are never released [REN].
- With ground-truth boxes the τ = 0 term vanishes. That is why the identical machinery jumps to 80-85% (rows 15-16).

**Why tracking cannot fix temporally correlated errors.**
- A Kalman filter averages independent per-frame noise.
- UniDriveVLA's decoder carries temporal instance banks, so consecutive detections of one object share their error. V2 measured the frame-to-frame correlation of the matched vehicle errors [V2]:
  - along-heading position error: 0.66 at 0.1 s and 0.44 at 0.9 s;
  - velocity components: 0.91 and 0.86 at 0.1 s, 0.53 and 0.25 at 0.9 s.
- Averaging such errors changes little: the tracked residuals equal the raw ones [TRK].
- Beyond about 1 s the residual is the actors' real acceleration, which no constant-velocity filter predicts [TRK interpretation item 4].
- What tracking does remove, false agents, is not what ends the leases [TRK].

**Why the fast prefix alone is insufficient.**
- Halving L_rel halves the need (1.97 → 0.96 s) and shortens the extrapolation horizon [FP].
- With model detections, however, the binding failure is at small τ: plans that are never released or fail the release check. Latency does not touch that failure.
- Model-detection continuity therefore rises only to 48.3% (15 clips, renewal) or 54.5-60.3% (32 clips), with realized R_cond up to 13.3% (rows 11-13).

**Why near-perfect perception plus 0.45 s passes.**
- With exact boxes and velocities, the envelope only has to cover prediction error from real accelerations. At L_rel 0.45 s the need is 0.95 s, so a certificate without renewal must reach about 1.45 s instead of 2.34 s (this report: 2 × 0.45 + 0.05 + 0.5 s). Renewal also re-anchors the certificate every 0.2 s.
- Perfect boxes then reach 86.3% (MARGINAL on all frames; the upper bound is driven by single clips) and 87.7% (PASS) without the static V = 0 frames (rows 19-20). The perfect-foresight ceiling is 90-95% [PQ].
- At 0.896 s even perfect boxes stop at 81-84% [PQ §Bottom line 2, 5]. The longer horizon accumulates more prediction error (this report's reading of PQ §Bottom line 6).

---

## 5. Closed-loop pilot (completed 2026-11-10 03:55 +0800)

**Status.** All 12 jobs finished with exit 0. The runner exited at 03:55 +0800, free disk stayed at or above 6.6 GiB, and the disk watchdog never placed a `STOP` file [PIL `runner.log`, `progress.json`]. The results are in §5.1 below; every number in it was read from `pilot/<arm>/runs/<run>/metrics/result.json` and `raw/agent/framelease/summary.json` [PIL].

**Purpose.** The pilot is an integration and latency test in the measured-latency CARLA closed loop (kappa 1.0). It checks:
- whether the fast-prefix agent runs end to end;
- what the fast prefix changes in plan age, fallbacks and driving scores.

It is **not** a test of a gate-passing lease. The FrameLease arm uses the default isotropic q95 envelope file `outputs/framelease_v2/c2_calibration/full_20261107T045343Z/lease_params_q95_envelope.json` [PIL `arms`]. That file is G2's E0-orig q95, which was 31.5% continuous at need 1.842 s with 7.7% of conflict frames over-estimated (Table 1). Under the fast prefix's need of 0.96 s, the nearest offline number is P(H >= 1 s) = 42% for that envelope [G2 §Diagnostics]. The runtime review's open-loop replay gave a fallback ratio of 0.66 with this envelope (`T/whrjr5y9n.output`, `result.review`). Frequent fallbacks are therefore expected (this report's reading).

**Design** [FP §5; PIL]:
- 12 jobs = 4 non-test pilot routes × 3 arms.
- Seed 11, kappa 1.0, wall cap 1500 s per job.
- Ports 2900-2955, one output directory per arm.
- 37 sha256 pins per job.
- Arm order rotated by one position per route.

| route | scenario |
|---|---|
| 2086 | NonSignalizedJunctionLeftTurn |
| 18305 | ParkingCutIn |
| 2554 | ParkedObstacle |
| 1792 | HazardAtSideLane |

| arm | launcher | configuration |
|---|---|---|
| `fast_only` | `framelease_v3/runtime/run_closed_loop_v3.py` (delegates to unchanged v2) | baseline, unmodified prefix, max_age 3.0 s |
| `fast_only_fp` | `framelease_v3/fastprefix/run_closed_loop_fast.py` | same configuration + fast prefix |
| `fl_v3_heuristic_fp` | `framelease_v3/fastprefix/run_closed_loop_fast.py` | v3 suffix lease + shield + heuristic scheduler + versioned commit + watchdog (max_age 2.5 s, profile quantile 0.99, q95 envelope above) + fast prefix |

**What will be measured** [FP §5, "What to read after the pilot"]:
- Per arm: DS, RC, infractions, fallback ratio and action age.
- The charged prefix cost: expected p50 about 0.44 s for the `_fp` arms against about 0.9 s for the baseline.
- `raw/agent/framelease/fast_prefix.json`: it must report `stage: final`, a passed validation and SDPA calls > 0.
- For `fl_v3_heuristic_fp`: `summary.json["v3"]` (P_both and deadline misses).

**Suggested reading rules (this report, fixed before any result).** With 4 routes and 1 seed the pilot is descriptive only. Report:
- whether all runs completed with validation ok;
- whether the charged prefix p50 of the `_fp` arms is near 0.44 s;
- the change in action age;
- the fallback ratio and P_both of the FrameLease arm.

Make no claim about driving-score differences.

**Table 10 (to be filled).**

| arm | runs ok / 4 | DS mean | RC mean | infractions | fallback ratio | action age p50 / p95 (s) | charged prefix p50 (s) | P_both | deadline misses |
|---|---|---|---|---|---|---|---|---|---|
| fast_only | TBD | TBD | TBD | TBD | TBD | TBD | TBD | n/a | n/a |
| fast_only_fp | TBD | TBD | TBD | TBD | TBD | TBD | TBD | n/a | n/a |
| fl_v3_heuristic_fp | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

---


### 5.1 Results

Per route and arm (seed 11, kappa 1.0). "fallback" is the share of control ticks spent in fallback and "expired" the share
caused by an expired lease. "age p50" is the median action age. "lease p50" is the median lease of committed candidates
(v3 arm only). "DL miss" is the deadline-miss tick ratio. Source: [PIL] run directories.

| route (scenario) | arm | DS | RC | route status | fallback | expired | age p50 (s) | lease p50 (s) | P_both | DL miss |
|---|---|---|---|---|---|---|---|---|---|---|
| 1792 (HazardAtSideLane) | fast_only | 60.0 | 100 | Completed | 4.5% | 0.0% | 1.45 | - | - | - |
| 1792 | fast_only_fp | 36.0 | 100 | Completed | 2.1% | 0.0% | 0.70 | - | - | - |
| 1792 | fl_v3_heuristic_fp | 49.7 | 49.7 | Failed - TickRuntime | 88.6% | 88.4% | 0.70 | 0.00 | 0.237 | 88.6% |
| 18305 (ParkingCutIn) | fast_only | 95.5 | 100 | Completed | 4.0% | 0.0% | 1.45 | - | - | - |
| 18305 | fast_only_fp | 100.0 | 100 | Completed | 1.8% | 0.0% | 0.70 | - | - | - |
| 18305 | fl_v3_heuristic_fp | 4.6 | 4.6 | Failed - Agent got blocked | 96.8% | 96.0% | 1.45 | 0.00 | 0.060 | 96.7% |
| 2086 (NonSignalizedJunctionLeftTurn) | fast_only | 10.2 | 59.2 | Failed - TickRuntime | 0.5% | 0.0% | 1.45 | - | - | - |
| 2086 | fast_only_fp | 5.5 | 38.6 | Failed - Agent got blocked | 0.2% | 0.0% | 0.70 | - | - | - |
| 2086 | fl_v3_heuristic_fp | 27.6 | 34.5 | Failed - TickRuntime | 94.4% | 94.1% | 0.80 | 0.00 | 0.249 | 94.3% |
| 2554 (ParkedObstacle) | fast_only | 100.0 | 100 | Completed | 3.4% | 0.0% | 1.45 | - | - | - |
| 2554 | fast_only_fp | 60.0 | 100 | Completed | 1.4% | 0.0% | 0.70 | - | - | - |
| 2554 | fl_v3_heuristic_fp | 4.6 | 4.6 | Failed - Agent got blocked | 96.1% | 95.7% | 0.65 | 0.00 | 0.055 | 96.1% |

Means over the 4 routes (this report): DS 66.4 / 50.4 / 21.6 and RC 89.8 / 84.6 / 23.3 for `fast_only` /
`fast_only_fp` / `fl_v3_heuristic_fp`.

Charged prefix cost, p50 per run: 0.905-0.935 s for `fast_only` and 0.416-0.426 s for both `_fp` arms. All 8 `_fp` runs
report a passed fast-prefix validation with SDPA active (4,424-41,832 SDPA calls per run). Infractions are dominated by
min-speed infractions in every arm. Vehicle collisions: 4 (`fast_only`), 5 plus 1 layout collision (`fast_only_fp`), 0
(`fl_v3_heuristic_fp`, which instead got blocked on two routes).

### 5.2 Reading

1. **The fast prefix works end to end in CARLA.** Every `_fp` run validated. The charged prefix halves (about 0.92 to
   0.42 s), the median action age halves (1.45 to 0.70 s), and fallback ticks from a missing plan fall from 0.5-4.5% to
   0.2-2.1%.
2. **No driving-score conclusion about the fast prefix.** With 4 routes and one seed, the mean DS difference (-16 points)
   is well inside the route-level variability measured in the v2 matrix (paired DS differences of roughly 28 points SD at
   n = 44). RC is equal on 3 of 4 routes. A matched closed-loop matrix would be needed.
3. **The closed loop reproduces the offline lease failure.** With the default q95 isotropic envelope on the model's own
   detections, the median committed lease is 0 s, 89-97% of ticks are fallback, and the deadline-miss ratio is 89-97%.
   P_both is only 0.05-0.25. On two routes the vehicle never got going (RC 4.6%, "Agent got blocked"). This is worse
   than the open-loop replay's 0.66 fallback ratio for the same envelope: once the ego stops close behind traffic or an
   obstacle, every new plan passes within the inflated envelope of a nearby real vehicle and the lease stays at zero.
   This matches the binding constraint identified offline (§3, §4).
4. **Caveats.** These are non-test pilot routes; n = 4 with seed 11 and kappa 1.0. Other projects loaded the CPU during
   the run, so absolute latencies are inflated (the ratios are robust). The v3 arm used the default q95 envelope, not a
   frontier point, so it says nothing about the best achievable lease. It only confirms the mechanism.

## 6. Implications and next steps for a future paper (not DAC 2027)

### 6.1 What the results mean for the outline's design

**The shield would rarely have both actions available.** The lease is the shield's only source of deadlines. With at most about 60% continuity at R_cond 5% using model detections (Table 9), the shield would often see only FALLBACK or a single feasible action. The G2 verifier found the P_both proxy roughly equal to continuity (37.4-37.6% for the q80 LOCO variants) [VG2]. The outline itself names a low P_both as a threat to the RL claim [OUT §IV-B, paragraph 2].

**Suffix alignment helps, but the envelope term dominates.** Relative to the old global-minimum lease (median 0 s, P(H = 0) 50.1%), suffix alignment does help [G2 §Self-tests]. The binding term, though, is the envelope needed for perception and prediction error, not the alignment.

**Proposition 1 is only conditional.** Per-τ coverage of a quantile envelope does not imply path coverage. For E0 q95 LOCO, vehicle per-τ coverage is 93.8-96.8%, but whole-path coverage (0-2.5 s) is 87.8% [G2 §Diagnostics]. Any statistical version of the proposition must therefore be stated at the trajectory level. The outline already requires coverage to be reported for a calibrated envelope and forbids presenting it as an unconditional guarantee [OUT §III-A, paragraph 4].

### 6.2 Candidate framings

1. **Perception requirement for runtime action-validity certification (recommended primary framing).**
   - Claim: before a driving VLA's plans can be certified at runtime at a literature-standard per-demand risk (R_cond 5%, nested LOCO), its perception must reach roughly σ_v <= 0.1 m/s, σ_p <= 0.05-0.1 m and recall >= 0.99, and its release latency must be about 0.45 s. UniDriveVLA is about 12x away on velocity RMS.
   - Evidence in hand:
     - Tables 7a and 9;
     - the mechanism decomposition into detection error at τ = 0, prediction error and latency;
     - negative results for renewal and tracking;
     - the R_marg gaming example.
   - Missing: multi-seed robustness, a lease with memory, strict nested selection, and a second backbone or detector.
2. **Fast-prefix engineering for flow-matching VLAs.**
   - 2.1x prefix speed-up at centimetre-level plan deviation, plus a component profile and perception-separability facts (Tables 4 and 8).
   - On its own this is a small contribution. Its closed-loop value depends on the pilot (Section 5).
3. **Lease with memory / multi-frame certificates.**
   - A certificate that trusts a single frame turns every independent drop into risk. This is the recall cliff, and V2 calls it partly a design artifact.
   - A certificate built over the last few frames could flatten the cliff and catch actors that were missed only briefly.
   - Expected gain is small on R_cond (TRK counts 3-6 such misses per cell) but potentially large on robustness to recall. Untested.
4. **Better velocity estimation.**
   - Velocity is the steepest axis (Table 7a). Kalman tracking of the decoder's own velocities did not help.
   - Candidates: velocity from positions over a longer baseline, a learned short-horizon predictor that does not consume single-frame velocity, or an independent velocity source.
   - Target: the grid's σ_v <= 0.1-0.3 m/s per axis.
5. **Responsibility-aware validity.**
   - Ignoring followers that approach from behind (an RSS-motivated rule [29]) lifts model-detection renewal from 48.5% to 57.8% (Table 9, rows 5-6).
   - It changes the validity definition for both lease and conflict, so it needs its own justification and cannot count as safety evidence [REN §Caveats].

### 6.3 Remaining open checks, in priority order

1. **DONE (day 3, §3.9): multi-seed robustness of the requirement grid** (CPU).
   - Rerun at least the boundary cells and the recall rows with 5 or more seeds, and report the spread.
   - The full study took about 75 min on 6 workers [PQ §Commands].
2. **DONE (day 3, §3.10): lease-with-memory variant** (CPU).
   - Implement a k-frame certificate on the existing stage-A data of REN, TRK and PQ.
   - Report the continuity and R_cond shift along the recall axis.
3. **Strict nested selection for REN, TRK and PQ** (CPU).
   - These studies used the simple version.
   - On RF's data the strict version was 7 points lower at the 5% point (15.4 vs 22.4%) [RF]. That matters for PASS cells that sit 0-2.7 points above 85%.
4. **Sweep the 14 pending clips** (GPU).
   - 4174 frames at about 1.3 s per frame, i.e. about 1.5 GPU-hours [EXT `resume`; 4174 × 1.3 s, this report].
   - Resuming needs at least 12.375 GiB free, so it is blocked at the current disk level.
5. **Conflict-definition sensitivity** (CPU).
   - TTC-based conflicts as used by the benchmarks: NAVSIM 0.9 s [38], nuPlan 0.95 s [37], SSAM 1.5 s [41] [LIT §4.2, item 5].
   - Report R_cond with and without the static V = 0 plans.
6. **Closed-loop matrix.** `outputs/framelease_v3/closed_loop/main/matrix.json` holds 220 jobs (44 routes × 5 arms), not launched. Two notes:
   - Its `fl_v3_heuristic` and `fl_global` arms are wired to the same q95 envelope file.
   - Launch it only after an offline lease passes, or reframe it as a frontier characterization.
   - At the mean wall time of the six finished pilot jobs (555 s; range 177-906 s) it would take about 34 GPU-hours (this report: 220 × 555 s; rough, because job times vary fourfold by route) [PIL `progress.json`, `runner.log`].
7. **RENEW feasibility.**
   - The certificate schedules that help assume a perception pass of about 0.03 s. The cheapest measured pass takes 59 ms with lower recall [PROF].
   - True overlap would need the `deformable_aggregation` extension rebuilt for the current stream, or a second model process (about 6 GB) [PROF §0, §8].

### 6.4 Resource notes

**Disk.**
- 6718 MiB (about 6.6 GiB, 7.0 GB) free at 03:20 +0800, down from 8033 MiB at about 02:55 (`df`). Only the pilot runner's 6 GiB start floor and the 5 GiB watchdog lie below this level, so the pilot may stall before its last jobs (Section 5).
- Other projects drain about 1-3 GiB/h: the user's CSMH project (`CSMH_v0.7.0/docs/research_two_map_linux/city-repair`) and the Codex session logs under `~/.codex` [V1 `result.gpu.extend`; EXT `acquisition_policy_changes`]. The two `df` readings above imply about 3 GiB/h (this report). Their files must not be deleted.
- The sprint's own outputs are small: FP wrote 6.3 MiB, and a closed-loop run writes 3-15 MB [FP §5, §8].
- The pilot is protected by `--min-free-gib 6` and the 5 GiB watchdog.

**GPU.** The pilot holds the one RTX 4090 D until about 04:16 +0800 (runner estimate at 03:20).

**Volatile sources.** These live under `/tmp` and will not survive a reboot. Copy them if they are to be kept:
- the outline extract;
- the verifier outputs (VG2, V1, V2, LIT);
- the verifiers' scratch code (`/tmp/fl_verify`, `/tmp/fl_verify_renewal`, `/tmp/fl_verify_day2`).

---

## 7. Provenance appendix

All run directories are under `outputs/framelease_v3/` and all code is under `framelease_v3/`, unless a path says otherwise. New code lives only under `framelease_v3/`. The studies call `framelease_v2/` code unchanged; the G2 `config.json`, the extension's `sweep_settings` and the pilot jobs record its sha256.

| study | run directory | code | verification artifacts | verification status |
|---|---|---|---|---|
| G2' gate | `gate2_offline/gate2_20261109/` (README.md, summary.json, metrics.csv, frames.csv, per_clip.csv, envelopes/) | `suffix_lease_eval.py`, `envelopes.py`, `make_gate2_readme.py` (sha256 prefixes in G2 §Files) | in-run self-tests (i)-(iv); verifier output `T/wwi9aayoo.output` (`result.verify`); scratch `/tmp/fl_verify/` | CONFIRMED_WITH_CAVEATS (grid-edge caveat: frontier about 45-51%) |
| risk frontier | `gate2_offline/risk_frontier_20261109/` (candidate_metrics.csv, frontier.csv, nested_selection.csv, nested_folds.csv, inverse_frontier.csv, summary.json) | `risk_frontier.py` (sha256 2d71af88fc2f) | `crosscheck_rf.py` + `crosscheck.txt` (J), `audit_independent.py` + `.txt`/`.json` (K), `resume_check.py` + `.txt`/`.json` (L), `verify_m*.py` + `verify_m.txt` (M), all inside the run directory | J, K, L, M all PASS |
| literature memo | `T/wc41r2ftv.output` (`result.synth`; 49 verified references) | literature workflow (4 search angles, each citation verified) | verification phase of that workflow; excluded sources listed in the memo | citations verified; its frontier phase failed and is superseded by RF |
| lease renewal | `renewal_offline/run_20261110/` (README.md, interpretation.md, candidate_metrics.csv, nested_selection.csv, nested_folds.csv, stageA/, sensitivity_Lrel/, verify/) | `renewal/renewal_compute.py`, `renewal_analyze.py`, `renewal_readme.py`, `renewal_sensitivity.py`, `verify_independent.py`, `tests/test_renewal_core.py` | `verify/verify_independent.txt` (V1-V5); verifier `T/w9ez2rfn8.output` (`result.renewal.verify`); scratch `/tmp/fl_verify_renewal/` | CONFIRMED_WITH_CAVEATS (6 minor issues) |
| profiling | `profiling/run_20261110/` (report.md, timings.json, micro.json, concurrency.json, components/, variants/, frontcam/) | `profiling/profile_unidrive.py`, `profile_concurrency.py`, `profile_frontcam.py`, `analyze_profile.py`, `launch*.sh` | exactness checks in report §3 | self-checked only; speed-up re-measured by FP |
| held-out extension | `c1_sweep_ext/` (MERGE_NOTE.json, merged_37clips_20261109T145344Z/, ext_only_17clips_20261109T145344Z/, conflicts/, sweep_20261109T145344Z_b1-b3/, acq_20261109T145344Z/) | `extend/extend.py`, `sweep_wrapper.py`, `conflict_counts.py`, `launch.sh`; unchanged `framelease_v2/c1_depth_sweep.py` | per-batch `sweep_*/validation.json` and `validation_clips/`; `conflicts/check_15val.json`; `equivalence/equivalence.json`; 32-clip counts reproduced by V2 | PARTIAL (17 of 31 acquired clips swept; 14 paused for disk) |
| tracking | `tracking_offline/run_20261110/` (README.md, candidate_metrics.csv, nested_selection.csv, paired_vs_raw.csv, tuning/, tracks/, envelopes/, stageA/) | `tracking/tracker.py`, `common.py`, `tune_train.py`, `stage_tracks.py`, `fit_envelopes.py`, `lease_kernels.py`, `stage_a.py`, `stage_b.py`, `verify_kernel.py`, `make_readme.py`, `tests/` | `verify_kernel.json` (444000 τ* values, max diff 0); verifier `T/w20gbxjvt.output` (`result.verify`); scratch `/tmp/fl_verify_day2/` | CONFIRMED_WITH_CAVEATS |
| perception quality | `perception_quality/run_20261110/` (README.md, interpretation.md, definitions.md, grid_results.csv, requirement.csv, model_reference.csv, refine/, lowq/, refine_lowq/, extended/, maskcheck/, verify/) | `perception_quality/pq_core.py`, `pq_run.py`, `pq_verify.py`, `pq_report.py`, `pq_report_ext.py`, `pq_maskcheck.py`, `pq_diag.py`, `pq_readme.py` | `verify/verify_kernels.json`, `verify/verify_results.json`, `maskcheck/`; verifier V2 | CONFIRMED_WITH_CAVEATS (single-draw cells; recall cliff partly a design artifact) |
| fast prefix | `fastprefix/run_20261110/` (README.md, equivalence.json, timings.json, equivalence/, agent_smoke/, smoke_equivalence/) | `fastprefix/fast_path.py`, `agent_entry.py`, `run_closed_loop_fast.py`, `pilot_jobs.py`, `aggregate_pilot.py`, `equivalence.py`, `analyze_equivalence.py`, `agent_smoke.py`, `make_readme.py`, `tests/` (23 tests) | tests; equivalence controls (floor, seed spread); agent smoke | self-checked only (no separate verifier agent) |
| v3 runtime used by the pilot | – | `runtime/v3_lease.py`, `v3_shield.py`, `v3_scheduler.py`, `v3_commit.py`, `v3_agent.py`, `v3_arms.py`, `v3_matrix.py`, `run_closed_loop_v3.py`, `bench_v3.py`, `tests/` | review in `T/whrjr5y9n.output` (`result.review`): 56 tests pass on the official stack; microbenchmark `closed_loop/microbench/bench_20261109T082826Z.json` | READY_FOR_PILOT |
| closed-loop pilot (completed, 12/12) | `fastprefix/run_20261110/pilot/`, `.../pilot_queue/` (read only here) | the fast-prefix and runtime code above; runner `framelease_v2/gpu_queue.py` | `progress.json`, `runner.log`, `status.jsonl` | running: 6 of 12 done (0 failed) at 03:20 +0800 |
| quality seeds (day 3) | `quality_seeds/run_20261110/` (README.md, cells_summary.csv, iso_line.csv, recall_mechanism.csv, per_seed_results.csv.gz, checks/) | `quality_seeds/qs_core.py`, `qs_run.py`, `qs_check.py`, `qs_report.py`, `qs_tables.py` | `checks/`; V3 own recomputation in `/tmp/fl_verify_day3/` | CONFIRMED_WITH_CAVEATS (V3) |
| memory lease (day 3) | `memory_lease/run_20261110/` (README.md, interpretation.md, caveats.md, definitions.md, results.csv, seed_summary.csv, paired_vs_k1.csv, verify/) | `memory_lease/` | `verify/`; V3 own memory stage | CONFIRMED_WITH_CAVEATS (V3) |
| queued, not launched | `closed_loop/pilot_queue/` (8 jobs, plus 8 optional envelope-variant jobs in `optional/`), `closed_loop/main_queue/` (220 jobs), `closed_loop/main/matrix.json` | `runtime/v3_matrix.py` | – | not launched |

**References.** Only entries from the "References (verified sources only)" list of [LIT] are cited. The numbers are the memo's numbers. The normative texts of ISO 21448, ISO/PAS 8800, UL 4600 and IEC 61508 were not verified directly; they are cited only through the summaries listed below.

- [1] L. Lindemann, M. Cleaveland, G. Shim, G. J. Pappas, "Safe Planning in Dynamic Environments using Conformal Prediction," IEEE RA-L 8(8):5116-5123, 2023.
- [2] R. Luo, S. Zhao, J. Kuck, B. Ivanovic, S. Savarese, E. Schmerling, M. Pavone, "Sample-Efficient Safety Assurances using Conformal Prediction," WAFR 2022 (SPAR vol. 25, pp. 149-169); IJRR 43(9):1409-1424, 2024.
- [3] R. Sinha, E. Schmerling, M. Pavone, "Closing the Loop on Runtime Monitors with Fallback-Safe MPC," IEEE CDC 2023, pp. 6533-6540.
- [6] L. Lindemann, Y. Zhao, X. Yu, G. J. Pappas, J. V. Deshmukh, "Formal Verification and Control With Conformal Prediction: Practical Safety Guarantees for Autonomous Systems," IEEE Control Systems Magazine 45(6):72-122, 2025.
- [19] J. Bernhard, P. Hart, A. Sahu, C. Schöller, M. Guzman Cancimance, "Risk-Based Safety Envelopes for Autonomous Vehicles Under Perception Uncertainty," IEEE IV 2022, pp. 104-111.
- [20] A. Farid, S. Veer, B. Ivanovic, K. Leung, M. Pavone, "Task-Relevant Failure Detection for Trajectory Predictors in Autonomous Vehicles," CoRL 2022.
- [29] S. Shalev-Shwartz, S. Shammah, A. Shashua, "On a Formal Model of Safe and Scalable Self-driving Cars," arXiv:1708.06374, 2017.
- [30] Z. Zhang et al., "Bench2Drive-Robust: Benchmarking Closed-Loop Autonomous Driving under Deployment Perturbations," arXiv:2605.18059, 2026 (preprint).
- [31] K. Black, M. Y. Galliker, S. Levine, "Real-Time Execution of Action Chunking Flow Policies," NeurIPS 2025.
- [32] Y. Li et al., "Think at 5 Hz, Act at 20 Hz: Asynchronous Fast-Slow Vision-Language-Action Inference for Closed-Loop Driving," arXiv:2607.15621, 2026 (preprint).
- [37] Motional, nuPlan devkit documentation: Metrics.
- [38] D. Dauner et al., "NAVSIM: Data-Driven Non-Reactive Autonomous Vehicle Simulation and Benchmarking," NeurIPS 2024 Datasets and Benchmarks.
- [41] D. Gettman, L. Pu, T. Sayed, S. Shelby, "Surrogate Safety Assessment Model and Validation: Final Report," FHWA-HRT-08-051, 2008.
- [42] L. Putze, L. Westhofen, T. Koopmann, E. Böde, C. Neurohr, "On Quantification for SOTIF Validation of Automated Driving Systems," IEEE IV 2023 (summary of the ISO 21448 Annex C decomposition).
- [43] R. Hawkins (Univ. of York), "Use case application of PD ISO/PAS 8800 for machine learning (ML) components," BSI, Jan 2025.
- [44] UL STP 4600, "UL 4600 Standard for Safety for the Evaluation of Autonomous Products," voting draft, 13 Dec 2019.
- [45] Intertek, "IEC 61508: Understanding Demand Modes," 1 Apr 2026 (secondary source for IEC 61508-1:2010 Tables 2 and 3).
