# FrameLease v4 offline lease ablation (Table II-A) and Fig. 1 data

Generated 2026-11-10 16:01 +0800 by `framelease_v4/offline/make_readme.py` from the CSV/JSON files in this directory; every number below is read from them. CPU only: no GPU, no CARLA, no model inference; the plans and detections are the stored UniDriveVLA depth-1 outputs of the C1 sweep. Code: `framelease_v4/offline/`. Inputs are read-only (`framelease_v2`, `framelease_v3` imported unchanged).

**Question (outline Sec. IV-B, paragraph 1).** Does the suffix-aligned, action-conditioned validity lease (Eq. 1-3) give a larger usable computation window than an observation-age deadline (Age-Only) and the v2 whole-horizon lease (Global-Margin) at a similar validity risk?

## 0. Bottom line

Data: 32 held-out VAL clips, 5417 depth-1 plans, 909 conflict plans (a real actor within d_safe = 0.5 m inside the 3 s horizon). TRAIN: 5 clips, 1004 plans, 12 conflicts. Needs: plan in use certified until its successor is released, 2 L_rel + 0.05 s = 0.964 s with the fast prefix and 1.842 s at the measured latency. R_cond = share of conflict plans whose lease runs past the realized validity.

1. **Age-Only cannot be risk-controlled.** Every positive age deadline already misses 42.0% of the conflicts (T_age = 0.05 s; plans whose conflict starts within T_c of capture). The shortest deadline that covers the need misses 62.8% [38.3, 74.3] (T_age 1.00 s, need 0.964 s; R_marg 10.5%) and 80.4% (1.85 s, need 1.842 s). At any R_cond limit up to 30% (TRAIN-selected, nested and in-sample alike) it can only fall back: continuity 0%, premature refresh 100%.
2. **Action-conditioned leases make the risk controllable.** At R_cond <= 5% (nested leave-one-clip-out, held-out per clip) the Suffix-Aligned lease keeps 53.1% of plans continuous at 0.964 s (realized R_cond 5.0%, utilization 54.8%) and 40.8% at 1.842 s; Age-Only keeps 0%.
3. **Suffix alignment is not better than the whole-horizon leases at matched risk.** Nested at R_cond <= 5%: Suffix 53.1% vs Global-Margin 52.1% continuity at 0.964 s (paired difference +1.0 [-4.8, +5.6] points) and 40.8% vs 43.7% at 1.842 s (-2.9 [-7.3, +1.2]); utilization 54.8% vs 54.4%. The whole-horizon control with the same tau-indexed envelope reaches 53.6% at both needs (Suffix minus control at 1.842 s: -12.8 [-19.1, -7.2]). The outline's expected effect ("larger usable window at a similar validity risk") is not observed on UniDriveVLA's own detections.
4. **Where suffix alignment does help: the high-continuity end.** Without an envelope the whole-horizon leases saturate at 73.8% continuity (R_cond 14.7%), while the suffix lease reaches 83.0% at 0.964 s (R_cond 23.8%) because it ignores approaches after the need. That region is above every literature risk level used so far (5-10%).
5. **TRAIN-selected settings (the "best training-clip setting")** are not risk-matched: TRAIN has only 12 conflicts, so R_cond <= 5% on TRAIN means zero TRAIN misses. Suffix picks E0 q70 (TRAIN) and Global E0 q80 (TRAIN); on VAL Suffix has 62.5% vs 42.4% continuity (0.964 s) but also R_cond 7.2% vs 3.3% (above the 5% limit for Suffix).
6. **The v2 deployed lease** (Global-Margin, E0-orig q95, 2.0 s cap) is a low-risk, low-availability point: continuity 37.2% / 27.4% (0.964 / 1.842 s) at R_cond 0.9%; P(H = 0) 49.4%.
7. **Conclusion for Table II-A.** The validity-lease row that the data supports is "action-conditioned vs age-only", not "suffix vs global". All conclusions hold without the static V = 0 plans, without BlockedIntersection and with the 36-clip LOCO envelopes; if only violations inside the replacement window count (every lease capped at the need) the whole-horizon lease is ahead of Suffix: -9.3 [-18.8, -2.3] points at 0.964 s and -12.0 [-19.2, -5.9] at 1.842 s (Sec. 5).

## 1. What was compared

| design | lease H of a depth-1 plan captured at t_k | knob (candidates) |
|---|---|---|
| Age-Only | H = T_age for every plan (fixed observation-age deadline) | T_age = 0, 0.05, ..., 2.5 s (51) |
| Global-Margin (v2) | `framelease_v2/lease.py` margin_mode `global`: m_j = min over the whole horizon [0, 3 s] of the clearance between the planned ego footprint and detection j moved at constant velocity, minus d_safe; H_j = sup{D : m_j - B_j(D) > delta}, envelope indexed by staleness D; H = min_j H_j, capped at 2.5 s (v2 deployed: 2.0 s, Sec. 5) | envelope (53) |
| Suffix-Aligned (Eq. 1-3) | `framelease_v3/suffix_lease_eval.py`: M(Delta) = min over tau in [Delta, Delta + T_c] of m(tau) - B(tau), H = first Delta with M(Delta) <= delta, capped at Hbar = T_pred - T_c = 2.5 s | envelope (53) |
| Whole-horizon control | same tau-indexed envelope as Suffix, minimum over the whole horizon: H = Hbar if m(tau) - B(tau) > delta for all tau in [0, 3 s], else 0 (isolates the alignment from the v2 envelope indexing) | envelope (53) |

Shared: d_safe 0.5 m, delta 0.2 m, T_c 0.5 s, 0.05 s grid, T_pred 3 s; relevant detections = vehicles and pedestrians with score >= 0.1; a non-finite relevant detection gives H = 0 for the envelope designs. Envelope candidates: ZERO (H = 0, always fall back); the isotropic E0 envelope B_c(tau) = vbar_c tau + abar_c tau^2 / 2 + sigma_c fitted on the **5 TRAIN clips only** at q30, q40, ..., q99.5; lambda x E0 q95 for lambda = 0 (no envelope), 0.05, ..., 2.0; and the v2 deployed parameter file. No VAL clip enters any envelope.

Metrics, all against the same realized validity: V = first tau at which the planned ego footprint comes within d_safe of a real vehicle / walker footprint (non-reactive replay, censored at 3 s); V_suf = clip(V - T_c, 0, 2.5); conflict = V not censored.

| metric | definition |
|---|---|
| validity violation | H > V_suf (the lease allows the plan beyond its realized validity); R_marg = violations / plans, R_cond = violations / conflict plans |
| continuity | P(H >= need): the plan in use stays certified until its successor is released |
| lease utilization | mean over plans with V_suf > 0 of min(H, V_suf) / V_suf (capped at 1: over-estimates do not count as use) |
| premature refresh | P(H < need given V_suf >= need): the deadline expires before the next commit although the realized validity still covered it |

Protocols (rule (a): maximal continuity at the need subject to R_cond <= alpha; ties: lower R_cond, then grid order; nothing qualifies -> fallback H = 0; declared before any VAL number was computed, see PROGRESS.md):

- **TRAIN-selected** ("best training-clip setting"): knob chosen on the 5 TRAIN clips, evaluated on the 32 VAL clips.
- **Nested (risk-matched, held-out)**: for each VAL clip the knob is chosen on the other 31 VAL clips and evaluated on it; pooled. The envelopes are TRAIN-fitted, so nothing of the held-out clip enters its choice.
- **Frontier (descriptive)**: best candidate at each alpha in-sample on VAL (winner's curse).

CIs: clip bootstrap, 2000 resamples, seed 20261109, conditional on the chosen candidates. Paired differences resample clips jointly.

## 2. Table II-A candidate: each design at its TRAIN-selected setting, evaluated on 32 VAL clips

Selection on TRAIN at R_cond <= 5%. Cells: % [95% CI].

| design | need | setting chosen on TRAIN (TRAIN misses / conflicts) | continuity | R_cond | R_marg | utilization | premature refresh | mean H (s) |
|---|---|---|---|---|---|---|---|---|
| Age-Only | 0.964 s (fast prefix) | T_age = 0.00s (0 / 12) | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.00 [0.00, 0.00] | 0.0 [0.0, 0.0] | 100.0 [100.0, 100.0] | 0.00 |
| Age-Only | 1.842 s (measured) | T_age = 0.00s (0 / 12) | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.00 [0.00, 0.00] | 0.0 [0.0, 0.0] | 100.0 [100.0, 100.0] | 0.00 |
| Global-Margin (v2) | 0.964 s (fast prefix) | E0 q80 (TRAIN) (0 / 12) | 42.4 [29.0, 57.1] | 3.3 [1.0, 8.4] | 0.55 [0.17, 1.08] | 45.9 [32.8, 59.6] | 52.8 [38.4, 66.6] | 1.06 |
| Global-Margin (v2) | 1.842 s (measured) | E0 q80 (TRAIN) (0 / 12) | 36.1 [21.7, 51.4] | 3.3 [1.0, 8.4] | 0.55 [0.17, 1.08] | 45.9 [32.8, 59.6] | 58.4 [42.8, 74.1] | 1.06 |
| Suffix-Aligned (Eq. 1-3) | 0.964 s (fast prefix) | E0 q70 (TRAIN) (0 / 12) | 62.5 [51.7, 74.0] | 7.2 [3.4, 14.8] | 1.20 [0.52, 2.07] | 63.4 [51.6, 74.1] | 30.7 [20.1, 42.6] | 1.44 |
| Suffix-Aligned (Eq. 1-3) | 1.842 s (measured) | E0 q70 (TRAIN) (0 / 12) | 46.6 [32.4, 62.0] | 7.2 [3.4, 14.8] | 1.20 [0.52, 2.07] | 63.4 [51.6, 74.1] | 46.5 [32.2, 61.8] | 1.44 |

Selection on TRAIN at R_cond <= 10%. Cells: % [95% CI].

| design | need | setting chosen on TRAIN (TRAIN misses / conflicts) | continuity | R_cond | R_marg | utilization | premature refresh | mean H (s) |
|---|---|---|---|---|---|---|---|---|
| Age-Only | 0.964 s (fast prefix) | T_age = 0.00s (0 / 12) | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.00 [0.00, 0.00] | 0.0 [0.0, 0.0] | 100.0 [100.0, 100.0] | 0.00 |
| Age-Only | 1.842 s (measured) | T_age = 0.00s (0 / 12) | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.00 [0.00, 0.00] | 0.0 [0.0, 0.0] | 100.0 [100.0, 100.0] | 0.00 |
| Global-Margin (v2) | 0.964 s (fast prefix) | E0 q70 (TRAIN) (1 / 12) | 48.5 [36.1, 61.9] | 4.0 [1.5, 9.7] | 0.66 [0.24, 1.24] | 51.0 [38.5, 63.7] | 46.1 [33.3, 59.3] | 1.18 |
| Global-Margin (v2) | 1.842 s (measured) | E0 q70 (TRAIN) (1 / 12) | 40.0 [26.2, 55.3] | 4.0 [1.5, 9.7] | 0.66 [0.24, 1.24] | 51.0 [38.5, 63.7] | 53.9 [38.7, 68.6] | 1.18 |
| Suffix-Aligned (Eq. 1-3) | 0.964 s (fast prefix) | E0 q60 (TRAIN) (1 / 12) | 69.2 [59.2, 79.9] | 11.9 [6.1, 22.0] | 1.99 [0.95, 3.38] | 71.6 [61.6, 80.6] | 23.5 [14.5, 33.8] | 1.63 |
| Suffix-Aligned (Eq. 1-3) | 1.842 s (measured) | E0 q60 (TRAIN) (1 / 12) | 55.8 [43.5, 69.1] | 11.9 [6.1, 22.0] | 1.99 [0.95, 3.38] | 71.6 [61.6, 80.6] | 36.2 [24.6, 49.1] | 1.63 |

Paired differences on VAL (TRAIN-selected, R_cond <= 5%), points [95% CI]:

| pair | need | continuity | R_cond | utilization | premature refresh |
|---|---|---|---|---|---|
| Suffix-Aligned (Eq. 1-3) - Global-Margin (v2) | 0.964 s (fast prefix) | +20.1 [+14.9, +26.0] | +3.9 [+1.7, +7.6] | +17.5 [+13.1, +22.1] | -22.0 [-29.0, -15.8] |
| Suffix-Aligned (Eq. 1-3) - Global-Margin (v2) | 1.842 s (measured) | +10.5 [+6.7, +15.8] | +3.9 [+1.7, +7.6] | +17.5 [+13.1, +22.1] | -12.0 [-17.4, -7.7] |
| Suffix-Aligned (Eq. 1-3) - Age-Only | 0.964 s (fast prefix) | +62.5 [+51.7, +74.0] | +7.2 [+3.4, +14.8] | +63.4 [+51.6, +74.1] | -69.3 [-79.9, -57.4] |
| Suffix-Aligned (Eq. 1-3) - Age-Only | 1.842 s (measured) | +46.6 [+32.4, +62.0] | +7.2 [+3.4, +14.8] | +63.4 [+51.6, +74.1] | -53.5 [-67.8, -38.2] |
| Global-Margin (v2) - Age-Only | 0.964 s (fast prefix) | +42.4 [+29.0, +57.1] | +3.3 [+1.0, +8.4] | +45.9 [+32.8, +59.6] | -47.2 [-61.6, -33.4] |
| Global-Margin (v2) - Age-Only | 1.842 s (measured) | +36.1 [+21.7, +51.4] | +3.3 [+1.0, +8.4] | +45.9 [+32.8, +59.6] | -41.6 [-57.2, -25.9] |

Reading: with 12 TRAIN conflicts the TRAIN rule cannot match risk across designs; Suffix gains continuity partly by taking more risk (its VAL R_cond exceeds 5%). Section 3 compares at matched risk.

## 3. Risk-matched comparison: nested leave-one-clip-out selection over the 32 VAL clips

| design | need | alpha | modal choice | continuity | realized R_cond | R_marg | utilization | premature refresh | misses / conflicts |
|---|---|---|---|---|---|---|---|---|---|
| Age-Only | 0.964 s (fast prefix) | 5% | T_age = 0.00s (32/32) | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.00 [0.00, 0.00] | 0.0 [0.0, 0.0] | 100.0 [100.0, 100.0] | 0 / 909 |
| Global-Margin (v2) | 0.964 s (fast prefix) | 5% | 0.30 x E0 q95 (TRAIN) (25/32) | 52.1 [39.4, 65.6] | 4.8 [1.8, 11.7] | 0.81 [0.32, 1.49] | 54.4 [42.3, 66.6] | 42.2 [29.3, 55.7] | 44 / 909 |
| Whole-horizon control | 0.964 s (fast prefix) | 5% | E0 q30 (TRAIN) (20/32) | 53.6 [41.2, 66.9] | 5.0 [2.0, 13.3] | 0.83 [0.39, 1.48] | 57.5 [45.5, 69.2] | 40.6 [29.4, 52.5] | 45 / 909 |
| Suffix-Aligned (Eq. 1-3) | 0.964 s (fast prefix) | 5% | 0.60 x E0 q95 (TRAIN) (23/32) | 53.1 [40.6, 66.8] | 5.0 [1.6, 12.9] | 0.83 [0.29, 1.55] | 54.8 [42.3, 66.7] | 41.0 [28.4, 53.8] | 45 / 909 |
| Age-Only | 1.842 s (measured) | 5% | T_age = 0.00s (32/32) | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.00 [0.00, 0.00] | 0.0 [0.0, 0.0] | 100.0 [100.0, 100.0] | 0 / 909 |
| Global-Margin (v2) | 1.842 s (measured) | 5% | 0.30 x E0 q95 (TRAIN) (25/32) | 43.7 [30.4, 57.8] | 4.8 [1.8, 11.7] | 0.81 [0.32, 1.49] | 54.5 [42.3, 66.6] | 49.8 [36.0, 63.7] | 44 / 909 |
| Whole-horizon control | 1.842 s (measured) | 5% | E0 q30 (TRAIN) (20/32) | 53.6 [41.2, 66.9] | 5.0 [2.0, 13.3] | 0.83 [0.39, 1.48] | 57.5 [45.5, 69.2] | 38.7 [27.6, 50.5] | 45 / 909 |
| Suffix-Aligned (Eq. 1-3) | 1.842 s (measured) | 5% | 0.60 x E0 q95 (TRAIN) (23/32) | 40.8 [26.1, 56.2] | 5.0 [1.6, 12.9] | 0.83 [0.29, 1.55] | 54.8 [42.3, 66.7] | 53.0 [38.3, 68.6] | 45 / 909 |
| Age-Only | 0.964 s (fast prefix) | 10% | T_age = 0.00s (32/32) | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.00 [0.00, 0.00] | 0.0 [0.0, 0.0] | 100.0 [100.0, 100.0] | 0 / 909 |
| Global-Margin (v2) | 0.964 s (fast prefix) | 10% | 0.10 x E0 q95 (TRAIN) (30/32) | 67.0 [55.1, 79.6] | 9.7 [4.4, 22.6] | 1.62 [0.77, 2.60] | 69.4 [59.3, 78.9] | 25.8 [16.7, 35.7] | 88 / 909 |
| Whole-horizon control | 0.964 s (fast prefix) | 10% | 0.10 x E0 q95 (TRAIN) (27/32) | 59.5 [47.1, 72.3] | 8.8 [3.7, 22.0] | 1.48 [0.66, 2.42] | 63.8 [52.6, 74.1] | 34.1 [24.2, 45.4] | 80 / 909 |
| Suffix-Aligned (Eq. 1-3) | 0.964 s (fast prefix) | 10% | 0.30 x E0 q95 (TRAIN) (23/32) | 65.4 [54.4, 76.8] | 10.0 [4.8, 19.5] | 1.68 [0.80, 2.81] | 66.7 [55.4, 77.1] | 27.6 [17.3, 39.4] | 91 / 909 |
| Age-Only | 1.842 s (measured) | 10% | T_age = 0.00s (32/32) | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.00 [0.00, 0.00] | 0.0 [0.0, 0.0] | 100.0 [100.0, 100.0] | 0 / 909 |
| Global-Margin (v2) | 1.842 s (measured) | 10% | 0.10 x E0 q95 (TRAIN) (30/32) | 60.5 [47.9, 73.2] | 9.7 [4.4, 22.6] | 1.62 [0.77, 2.60] | 69.4 [59.3, 78.9] | 30.8 [21.1, 42.3] | 88 / 909 |
| Whole-horizon control | 1.842 s (measured) | 10% | 0.10 x E0 q95 (TRAIN) (27/32) | 59.5 [47.1, 72.3] | 8.8 [3.7, 22.0] | 1.48 [0.66, 2.42] | 63.8 [52.6, 74.1] | 32.1 [22.7, 43.1] | 80 / 909 |
| Suffix-Aligned (Eq. 1-3) | 1.842 s (measured) | 10% | 0.30 x E0 q95 (TRAIN) (23/32) | 50.0 [36.5, 64.4] | 10.0 [4.8, 19.5] | 1.68 [0.80, 2.81] | 66.7 [55.4, 77.1] | 42.8 [29.1, 56.9] | 91 / 909 |

Paired differences (nested choices, clip bootstrap of the difference), points [95% CI]; share = bootstrap share of differences <= 0:

| pair | need | alpha | continuity | utilization | premature refresh | R_cond |
|---|---|---|---|---|---|---|
| Suffix-Aligned (Eq. 1-3) - Global-Margin (v2) | 0.964 s (fast prefix) | 5% | +1.0 [-4.8, +5.6] (share 0.33) | +0.4 [-2.8, +3.5] | -1.2 [-6.3, +5.1] | +0.1 [-2.6, +3.3] |
| Suffix-Aligned (Eq. 1-3) - Global-Margin (v2) | 1.842 s (measured) | 5% | -2.9 [-7.3, +1.2] (share 0.92) | +0.3 [-2.9, +3.4] | +3.2 [-1.4, +8.3] | +0.1 [-2.6, +3.3] |
| Suffix-Aligned (Eq. 1-3) - Global-Margin (v2) | 0.964 s (fast prefix) | 10% | -1.7 [-11.6, +5.9] (share 0.63) | -2.8 [-11.4, +4.5] | +1.9 [-7.0, +12.5] | +0.3 [-7.9, +4.7] |
| Suffix-Aligned (Eq. 1-3) - Global-Margin (v2) | 1.842 s (measured) | 10% | -10.5 [-20.2, -2.5] (share 1.00) | -2.8 [-11.4, +4.5] | +12.0 [+2.7, +22.7] | +0.3 [-7.9, +4.7] |
| Suffix-Aligned (Eq. 1-3) - Whole-horizon control | 0.964 s (fast prefix) | 5% | -0.4 [-6.0, +4.4] (share 0.54) | -2.8 [-7.7, +1.7] | +0.4 [-5.1, +6.6] | +0.0 [-4.7, +3.6] |
| Suffix-Aligned (Eq. 1-3) - Whole-horizon control | 1.842 s (measured) | 5% | -12.8 [-19.1, -7.2] (share 1.00) | -2.8 [-7.7, +1.7] | +14.4 [+8.2, +21.1] | +0.0 [-4.7, +3.6] |
| Suffix-Aligned (Eq. 1-3) - Whole-horizon control | 0.964 s (fast prefix) | 10% | +5.9 [-3.4, +12.9] (share 0.10) | +2.8 [-6.1, +10.0] | -6.5 [-15.1, +3.7] | +1.2 [-7.6, +6.5] |
| Suffix-Aligned (Eq. 1-3) - Whole-horizon control | 1.842 s (measured) | 10% | -9.5 [-19.1, -2.1] (share 1.00) | +2.8 [-6.1, +10.0] | +10.7 [+2.1, +20.9] | +1.2 [-7.6, +6.5] |
| Suffix-Aligned (Eq. 1-3) - Age-Only | 0.964 s (fast prefix) | 5% | +53.1 [+40.6, +66.8] (share 0.00) | +54.8 [+42.3, +66.7] | -59.0 [-71.6, -46.2] | +5.0 [+1.6, +12.9] |
| Suffix-Aligned (Eq. 1-3) - Age-Only | 1.842 s (measured) | 5% | +40.8 [+26.1, +56.2] (share 0.00) | +54.8 [+42.3, +66.7] | -47.0 [-61.7, -31.4] | +5.0 [+1.6, +12.9] |
| Suffix-Aligned (Eq. 1-3) - Age-Only | 0.964 s (fast prefix) | 10% | +65.4 [+54.4, +76.8] (share 0.00) | +66.7 [+55.4, +77.1] | -72.4 [-82.7, -60.6] | +10.0 [+4.8, +19.5] |
| Suffix-Aligned (Eq. 1-3) - Age-Only | 1.842 s (measured) | 10% | +50.0 [+36.5, +64.4] (share 0.00) | +66.7 [+55.4, +77.1] | -57.2 [-70.9, -43.1] | +10.0 [+4.8, +19.5] |

Choices across the 32 folds (R_cond <= 5%): Global-Margin (v2) @ 0.964 s: 0.30 x E0 q95 (TRAIN) x25, 0.20 x E0 q95 (TRAIN) x3, E0 q60 (TRAIN) x2, 0.25 x E0 q95 (TRAIN) x1, 0.45 x E0 q95 (TRAIN) x1; Global-Margin (v2) @ 1.842 s: 0.30 x E0 q95 (TRAIN) x25, E0 q60 (TRAIN) x5, 0.25 x E0 q95 (TRAIN) x1, 0.45 x E0 q95 (TRAIN) x1; Whole-horizon control @ 0.964 s: E0 q30 (TRAIN) x20, E0 q50 (TRAIN) x7, E0 q40 (TRAIN) x4, 0.20 x E0 q95 (TRAIN) x1; Whole-horizon control @ 1.842 s: E0 q30 (TRAIN) x20, E0 q50 (TRAIN) x7, E0 q40 (TRAIN) x4, 0.20 x E0 q95 (TRAIN) x1; Suffix-Aligned (Eq. 1-3) @ 0.964 s: 0.60 x E0 q95 (TRAIN) x23, 0.55 x E0 q95 (TRAIN) x3, 0.65 x E0 q95 (TRAIN) x3, 0.80 x E0 q95 (TRAIN) x1, 0.50 x E0 q95 (TRAIN) x1, 0.45 x E0 q95 (TRAIN) x1; Suffix-Aligned (Eq. 1-3) @ 1.842 s: 0.60 x E0 q95 (TRAIN) x23, 0.55 x E0 q95 (TRAIN) x3, 0.65 x E0 q95 (TRAIN) x3, 0.80 x E0 q95 (TRAIN) x1, 0.50 x E0 q95 (TRAIN) x1, 0.45 x E0 q95 (TRAIN) x1.

## 4. In-sample frontier on VAL (descriptive): best continuity at R_cond <= alpha

Cells: continuity % (realized R_cond %, utilization %). Each design's best candidate on the 32 VAL clips; optimistic (winner's curse), shown for the shape of the trade-off.

Need 0.964 s (fast prefix):

| alpha | Age-Only | Global-Margin (v2) | Whole-horizon control | Suffix-Aligned |
|---|---|---|---|---|
| 2% | 0.0 (0.0, 0.0) | 38.4 (1.8, 38.8) | 40.2 (1.8, 43.2) | 41.0 (2.0, 36.7) |
| 5% | 0.0 (0.0, 0.0) | 51.5 (4.2, 53.1) | 53.1 (4.8, 57.1) | 52.8 (4.8, 54.6) |
| 10% | 0.0 (0.0, 0.0) | 66.6 (7.9, 68.2) | 57.0 (6.8, 61.1) | 64.3 (8.8, 65.8) |
| 15% | 0.0 (0.0, 0.0) | 73.8 (14.7, 78.9) | 73.8 (14.7, 78.9) | 70.4 (13.2, 72.4) |
| 20% | 0.0 (0.0, 0.0) | 73.8 (14.7, 78.9) | 73.8 (14.7, 78.9) | 79.2 (19.1, 81.8) |
| 30% | 0.0 (0.0, 0.0) | 73.8 (14.7, 78.9) | 73.8 (14.7, 78.9) | 83.0 (23.8, 87.3) |

Need 1.842 s (measured):

| alpha | Age-Only | Global-Margin (v2) | Whole-horizon control | Suffix-Aligned |
|---|---|---|---|---|
| 2% | 0.0 (0.0, 0.0) | 31.8 (1.8, 38.8) | 40.2 (1.8, 43.2) | 16.4 (2.0, 36.7) |
| 5% | 0.0 (0.0, 0.0) | 41.4 (4.2, 53.1) | 53.1 (4.8, 57.1) | 40.6 (4.8, 54.6) |
| 10% | 0.0 (0.0, 0.0) | 58.4 (7.9, 68.2) | 57.0 (6.8, 61.1) | 48.9 (8.8, 65.8) |
| 15% | 0.0 (0.0, 0.0) | 73.8 (14.7, 78.9) | 73.8 (14.7, 78.9) | 55.8 (11.9, 71.6) |
| 20% | 0.0 (0.0, 0.0) | 73.8 (14.7, 78.9) | 73.8 (14.7, 78.9) | 65.7 (19.1, 81.8) |
| 30% | 0.0 (0.0, 0.0) | 73.8 (14.7, 78.9) | 73.8 (14.7, 78.9) | 73.4 (23.8, 87.3) |

Age-Only along its knob (VAL, all plans; continuity is 0 below the need and 100% at or above it):

| T_age (s) | R_cond % [CI] | R_marg % | utilization % | R_cond without static V = 0 plans % |
|---|---|---|---|---|
| 0.05 | 42.0 [15.2, 60.9] | 7.1 | 2.6 | 17.8 |
| 0.50 | 52.3 [25.9, 66.9] | 8.8 | 23.0 | 32.3 |
| 1.00 | 62.8 [38.3, 74.3] | 10.5 | 43.4 | 47.3 |
| 1.85 | 80.4 [65.5, 86.8] | 13.5 | 76.2 | 72.2 |
| 2.50 | 100.0 [100.0, 100.0] | 16.8 | 100.0 | 100.0 |

Of the 909 VAL conflict plans, 378 have V_suf = 0 (the conflict starts within T_c of capture; 268 of them are static V = 0 plans, 232 in BlockedIntersection_Town03_Route135); any positive age deadline misses all of them.

## 5. Sensitivities (nested selection at R_cond <= 5%)

| variant | need | Age-Only | Global-Margin | Whole-horizon control | Suffix-Aligned | Suffix - Global (points) |
|---|---|---|---|---|---|---|
| main (all plans) | 0.964 s (fast prefix) | 0.0 (R_cond 0.0) | 52.1 (R_cond 4.8) | 53.6 (R_cond 5.0) | 53.1 (R_cond 5.0) | +1.0 [-4.8, +5.6] |
| main (all plans) | 1.842 s (measured) | 0.0 (R_cond 0.0) | 43.7 (R_cond 4.8) | 53.6 (R_cond 5.0) | 40.8 (R_cond 5.0) | -2.9 [-7.3, +1.2] |
| without the 268 static V = 0 plans (selection and evaluation) | 0.964 s (fast prefix) | 0.0 (R_cond 0.0) | 47.9 (R_cond 5.0) | 49.2 (R_cond 4.7) | 51.0 (R_cond 5.5) | +3.2 [-2.6, +8.1] |
| without the 268 static V = 0 plans (selection and evaluation) | 1.842 s (measured) | 0.0 (R_cond 0.0) | 39.9 (R_cond 5.0) | 49.2 (R_cond 4.7) | 35.2 (R_cond 5.5) | -4.7 [-10.2, -0.7] |
| BlockedIntersection excluded from evaluation (same choices) | 0.964 s (fast prefix) | 0.0 (R_cond 0.0) | 55.6 (R_cond 7.1) | 57.3 (R_cond 7.4) | 56.1 (R_cond 7.4) | - |
| BlockedIntersection excluded from evaluation (same choices) | 1.842 s (measured) | 0.0 (R_cond 0.0) | 46.3 (R_cond 7.1) | 57.3 (R_cond 7.4) | 43.1 (R_cond 7.4) | - |
| 36-clip LOCO envelopes (stored tracking-study fits) | 0.964 s (fast prefix) | - | 53.1 (R_cond 5.0) | - | 53.7 (R_cond 4.7) | +0.6 [-4.3, +4.7] |
| 36-clip LOCO envelopes (stored tracking-study fits) | 1.842 s (measured) | - | 45.2 (R_cond 5.0) | - | 42.0 (R_cond 4.7) | -3.2 [-8.2, +1.2] |
| every lease capped at the need (only violations inside the replacement window count) | 0.964 s (fast prefix) | 0.0 (R_cond 0.0) | 70.7 (R_cond 5.1) | 66.0 (R_cond 4.7) | 61.4 (R_cond 4.7) | -9.3 [-18.8, -2.3] |
| every lease capped at the need (only violations inside the replacement window count) | 1.842 s (measured) | 0.0 (R_cond 0.0) | 55.3 (R_cond 5.2) | 57.0 (R_cond 4.3) | 43.2 (R_cond 5.3) | -12.0 [-19.2, -5.9] |
| Global-Margin with the v2 deployed 2.0 s cap | 0.964 s (fast prefix) | - | 62.2 (R_cond 5.2) | - | - | - |
| Global-Margin with the v2 deployed 2.0 s cap | 1.842 s (measured) | - | 54.3 (R_cond 5.0) | - | - | - |

BlockedIntersection holds 300 of the 909 VAL conflicts, 232 of them static V = 0 plans (ego stopped about 0 m behind a stopped car, MERGE_NOTE). The nested choices miss 1 / 0 / 0 of them (Global / control / Suffix, 0.964 s), so these easy conflicts dilute R_cond: with the clip removed from the evaluation the realized R_cond of the same choices rises to about 7%. The static-V = 0 row, which removes these plans from the selection as well, is the consistent sensitivity (realized R_cond back at about 5%).

The 2.0 s cap lowers the Global-Margin risk at an unchanged continuity (needs < 2 s), so the selection can use a smaller envelope; a cap is itself a risk knob and any design capped near the need would gain the same way. The main comparison caps every design at the same Hbar = 2.5 s.

Fixed reference settings (no selection), VAL:

| setting | need | continuity | R_cond | R_marg | utilization | premature refresh | P(H = 0) |
|---|---|---|---|---|---|---|---|
| v2 deployed lease (Global-Margin, E0-orig q95, 2.0 s cap) | 0.964 s (fast prefix) | 37.2 [23.0, 52.4] | 0.9 [0.0, 3.1] | 0.15 | 32.0 | 58.5 | 49.4 |
| v2 deployed lease (Global-Margin, E0-orig q95, 2.0 s cap) | 1.842 s (measured) | 27.4 [15.7, 40.8] | 0.9 [0.0, 3.1] | 0.15 | 32.0 | 68.4 | 49.4 |
| Suffix-Aligned with the same v2 envelope file | 0.964 s (fast prefix) | 45.4 [31.1, 60.7] | 3.1 [0.8, 8.7] | 0.52 | 43.1 | 49.4 | 33.0 |
| Suffix-Aligned with the same v2 envelope file | 1.842 s (measured) | 27.5 [16.1, 40.9] | 3.1 [0.8, 8.7] | 0.52 | 43.1 | 68.3 | 33.0 |
| Suffix-Aligned, E0 q95 (TRAIN) | 0.964 s (fast prefix) | 44.7 [30.4, 60.1] | 2.9 [0.8, 8.1] | 0.48 | 41.7 | 50.1 | 33.1 |
| Suffix-Aligned, E0 q95 (TRAIN) | 1.842 s (measured) | 25.7 [14.6, 38.7] | 2.9 [0.8, 8.1] | 0.48 | 41.7 | 70.5 | 33.1 |
| Global-Margin, E0 q95 (TRAIN), 2.5 s cap | 0.964 s (fast prefix) | 37.1 [22.9, 52.4] | 1.2 [0.1, 3.9] | 0.20 | 35.6 | 58.6 | 49.4 |
| Global-Margin, E0 q95 (TRAIN), 2.5 s cap | 1.842 s (measured) | 26.1 [14.8, 39.5] | 1.2 [0.1, 3.9] | 0.20 | 35.6 | 69.9 | 49.4 |
| Suffix-Aligned, no envelope | 0.964 s (fast prefix) | 86.4 [78.8, 93.7] | 30.1 [16.3, 51.9] | 5.06 | 91.9 | 5.6 | 8.8 |
| Suffix-Aligned, no envelope | 1.842 s (measured) | 80.1 [71.1, 88.9] | 30.1 [16.3, 51.9] | 5.06 | 91.9 | 9.7 | 8.8 |
| Global-Margin, no envelope | 0.964 s (fast prefix) | 73.8 [62.1, 85.0] | 14.7 [8.0, 30.4] | 2.47 | 78.9 | 18.7 | 26.2 |
| Global-Margin, no envelope | 1.842 s (measured) | 73.8 [62.1, 85.0] | 14.7 [8.0, 30.4] | 2.47 | 78.9 | 16.4 | 26.2 |

## 6. What the remaining misses are (nested, R_cond <= 5%, all plans)

Capture-time detection status of the real actor that ends V, for the violated conflict plans:

| design | need | misses | confident detection | low-confidence detection | undetected | absent at capture |
|---|---|---|---|---|---|---|
| Global-Margin (v2) | 0.964 s (fast prefix) | 44 | 20 | 7 | 7 | 10 |
| Global-Margin (v2) | 1.842 s (measured) | 44 | 20 | 7 | 7 | 10 |
| Whole-horizon control | 0.964 s (fast prefix) | 45 | 23 | 4 | 8 | 10 |
| Whole-horizon control | 1.842 s (measured) | 45 | 23 | 4 | 8 | 10 |
| Suffix-Aligned (Eq. 1-3) | 0.964 s (fast prefix) | 45 | 21 | 1 | 13 | 10 |
| Suffix-Aligned (Eq. 1-3) | 1.842 s (measured) | 45 | 21 | 1 | 13 | 10 |

All VAL conflicts by status: confident 782, low-confidence 63, undetected 40, absent at capture 24. Undetected and absent actors cannot be seen by any perception-driven lease; they set a floor under R_cond that only better perception removes.

## 7. Fig. 1 data (freshness-depth evidence; preliminary, the final figure uses the new test matrix)

Files in `fig1/` (all re-derived or copied from the v2 sources listed in `fig1/fig1_sources.json`; checks in `fig1/fig1_check.json`: C1 panel a reproduced to 4e-16 m, closed-loop route means identical to the frozen contrasts):

- `c1_age_vs_depth.csv`: execution error vs observation age for flow depths 1 / 5 / 10 (offline replay, W = 1 s and 0.5 s; 15 held-out, 5 train, 20 all clips; mean of per-clip means, Student-t 95% interval).
- `c1_fresh_vs_deep_kappa.csv`: Fast@Fresh (depth 1, fresh) minus Deep@Old (depth 10, old) execution error vs kappa, and its staleness-gain / depth-cost decomposition.
- `closed_loop_ds_by_route.csv`, `closed_loop_ds_by_ability.csv`, `closed_loop_kappa_trend.csv`: closed-loop DS of Fixed Deep and Fast Only (measured-latency CARLA loop, 44 one-route-per-scenario-type routes).

Offline execution error (m), 15 held-out clips, W = 1 s, mean [t 95%]:

| age (s) | depth 1 | depth 5 | depth 10 |
|---|---|---|---|
| 0 | 0.306 [0.220, 0.393] | 0.304 [0.215, 0.392] | 0.312 [0.221, 0.402] |
| 0.5 | 0.726 [0.480, 0.972] | 0.726 [0.473, 0.978] | 0.734 [0.473, 0.995] |
| 1 | 1.263 [0.780, 1.746] | 1.266 [0.773, 1.760] | 1.265 [0.758, 1.771] |
| 1.5 | 1.870 [1.090, 2.650] | 1.876 [1.084, 2.668] | 1.861 [1.051, 2.670] |
| 2 | 2.547 [1.420, 3.674] | 2.552 [1.407, 3.697] | 2.523 [1.355, 3.691] |

Fast@Fresh minus Deep@Old (m; < 0: the fresher shallow plan is better), held-out clips, W = 0.5 s (RKm):

| kappa | delta [t 95%] | staleness gain | depth cost | clips fresh better |
|---|---|---|---|---|
| 1 | -0.114 [-0.192, -0.036] | -0.109 | -0.004 | 12 / 15 |
| 1.5 | -0.134 [-0.247, -0.020] | -0.154 | +0.020 | 12 / 15 |
| 2 | -0.218 [-0.410, -0.026] | -0.243 | +0.025 | 13 / 15 |
| 2.4 | -0.272 [-0.501, -0.043] | -0.310 | +0.038 | 13 / 15 |

Closed loop, DS difference Fixed Deep - Fast Only (route-paired):

| kappa | seed | routes | mean DS difference [95% CI] | p (two-sided) | status |
|---|---|---|---|---|---|
| 1.0 | 11 | 44 | +9.09 [+0.03, +18.49] | 0.067 | inconclusive |
| 1.0 | 12 | 15 | +3.91 [-13.23, +21.13] | 0.670 | inconclusive |
| 1.5 | 11 | 44 | +6.47 [-2.71, +15.64] | 0.187 | inconclusive |
| 2.0 | 11 | 11 | -11.18 [-28.49, +6.75] | n/a | exploratory |
| 1.0 (the 11 kappa-2.0 routes) | 11 | 11 | +18.84 [+3.79, +35.90] | n/a | descriptive |
| 1.5 (the 11 kappa-2.0 routes) | 11 | 11 | +13.03 [-2.61, +31.05] | n/a | descriptive |

By Bench2Drive ability at kappa 1.0 (abilities overlap; bootstrap 95% CI over routes, seed 20261109):

| ability | routes | seed 11: mean [CI]; routes deep better / fresh better / tie | mean over seeds 11/12 [CI] |
|---|---|---|---|
| Merging | 16 | +5.9 [-10.5, +24.1]; 5 / 8 / 3 | +4.3 [-9.6, +19.9] |
| Overtaking | 9 | +20.0 [+2.5, +36.9]; 6 / 3 / 0 | +20.0 [+3.4, +36.7] |
| Emergency_Brake | 12 | -1.9 [-17.3, +13.4]; 7 / 4 / 1 | -2.9 [-18.6, +12.7] |
| Give_Way | 2 | +47.5; 2 / 0 / 0 | +22.2 |
| Traffic_Signs | 19 | +8.5 [-3.4, +22.5]; 10 / 8 / 1 | +4.8 [-4.5, +15.9] |
| all | 44 | +9.1 [-0.0, +19.0]; 22 / 17 / 5 | +6.6 [-1.5, +14.8] |

No interval for fewer than 5 routes.

On the 11 routes of the kappa-2.0 arm the kappa-1.0 difference is +18.8 and the kappa-1.5 difference +13.0, so the sign change at kappa 2.0 is not a route-selection artifact (descriptive).

Reading: offline, freshness dominates depth at every kappa (age adds about 1 m of error per second on held-out clips while depth changes it by centimetres), and the fresh-shallow advantage grows with kappa. In the closed loop at kappa 1.0 the deeper, older plan scores higher on average (+9.1 DS, p = 0.067, n = 44; seed 12: +3.9, n = 15), with large heterogeneity across scenario types (Overtaking +20, Emergency_Brake -2), and the sign reverses at kappa 2.0 (-11.2, n = 11, exploratory). This is a latency-dependent crossover in closed loop, not a significant one at any single kappa; the final Fig. 1 should come from the new test matrix.

## 8. What Table II-A can and cannot say

Supported (offline, 32 held-out clips, UniDriveVLA detections):

- An observation-age deadline cannot separate plans that are about to conflict from plans that are not: any positive age deadline misses 42% of conflict plans (18% without the static V = 0 plans), and covering the need costs 63-80% R_cond. The three action-conditioned leases keep 41-54% of the plans continuous at a realized R_cond of about 5% (nested, both needs), where Age-Only keeps none.
- Premature refresh at matched risk: Age-Only refreshes every plan whose realized validity would have covered the need; the Suffix lease cuts this by 59 points at 0.964 s (-59.0 [-71.6, -46.2]) and 47 points at 1.842 s (-47.0 [-61.7, -31.4]).

Not supported:

- "Suffix alignment gives a larger usable window than the global margin at a similar risk": at R_cond 5% and 10% the paired continuity differences at the 0.964 s need are within +/-6 points with CIs spanning 0, and at the 1.842 s need the whole-horizon leases are as good or better (significantly so for the control at 5% and 10% and for Global-Margin at 10%, Sec. 3). Utilization differences are within +/-3 points. The suffix lease only extends the frontier where R_cond is 20-30% (Sec. 4).
- Any closed-loop Driving Score claim for a lease: the DS column of Table II-A needs the closed-loop matrix.

Mechanism (consistent with the v3 R&D report): the risk at the 5% level is set by perception error at small tau (detection error, undetected actors), not by the far-future part of the plan that suffix alignment removes. With noisy detections and constant-velocity prediction, a predicted close approach later in the plan is itself evidence of near-term risk; the whole-horizon leases use that evidence and can therefore run with a much smaller envelope (0.3 x q95 or q30) at the same R_cond, while the suffix lease discards it and needs 0.6 x q95. Suffix alignment pays off only when larger risk is accepted or, presumably, when perception is accurate enough that the far future carries no extra information (the v3 requirement grid).

## 9. Checks, provenance and reproduction

- Envelope self-check (`envelopes/selfcheck.json`): TRAIN E0 fits at q80-q99.5 and the v2 file reproduce gate2's ORIG envelopes exactly (max abs diff 0.0e+00); pass = True. TRAIN calibration pairs: {'vehicle': 4596, 'pedestrian': 194}.
- Cross-checks (`checks/crosscheck.json`, pass = True): suffix tau* and V reproduce gate2 frames.csv on all 2447 plans of the 15 VAL clips (max abs diff 5.0e-06 s, CSV precision); the Global-Margin lease with the v2 file and 2.0 s cap reproduces the v2 c2_eval `H_avl_s` (max abs diff 4.9e-06 s); plan and conflict counts equal MERGE_NOTE (2447 / 246 and 2970 / 663); the analysis code reproduces gate2's continuity / R_marg / R_cond for four suffix configurations on the 15 clips (max abs diff 4.7e-07).
- Fig. 1 checks (`fig1/fig1_check.json`): pass = True.
- Tests: `framelease_v4/offline/tests/test_offline.py` (metric definitions on hand-made cases, kernel equivalence with `framelease_v2.lease.compute_lease`).
- Code sha256: `analysis.json` (`code_sha256`). Inputs: the merged 37-clip view `outputs/framelease_v3/c1_sweep_ext/merged_37clips_20261109T145344Z` (clip and GT sha256 in each `frames/<clip>.npz` meta), gate2 envelopes and frames.csv, the v2 lease file, the tracking-study LOCO envelopes (`envelopes/loco36_E0.json` records its sha256).

```
cd /home/kang/Desktop/DAC; export OMP_NUM_THREADS=1; PY=".conda-unidrive-linux/bin/python -I -B"
$PY framelease_v4/offline/envelopes_v4.py        # TRAIN-only E0 fits + self-check (seconds)
$PY framelease_v4/offline/stage_frames.py --workers 8   # per-plan V, tau*, H_glob for 37 clips (~15 s)
$PY framelease_v4/offline/checks.py              # reproduction checks against gate2 / v2 c2_eval
$PY framelease_v4/offline/analyze.py             # metrics, frontier, nested, TRAIN-selected, paired
$PY framelease_v4/offline/fig1_data.py           # Fig. 1 data
$PY framelease_v4/offline/make_readme.py         # this README + summary.json
$PY -m pytest -q framelease_v4/offline/tests
```

Files: `candidate_metrics.csv` (every design x candidate x need x subset, VAL with CIs and TRAIN point values), `frontier.csv`, `nested.csv`, `nested_folds.csv`, `train_selected.csv`, `paired.csv`, `per_clip_selected.csv`, `analysis.json`, `frames/` (per-plan inputs, 4.6 MB), `envelopes/`, `checks/`, `fig1/`.

## 10. Caveats

- Offline, open-loop, non-reactive replay; constant-velocity prediction of the detections; depth-1 plans; T_c = 0.5 s. Validity is "within 0.5 m of a real actor", not a collision. No Driving Score here.
- One-shot leases computed at capture. The runtime re-checks the lease at commit (Eq. 9) and could renew it; neither changes the comparison of the deadlines themselves, but renewal results are in the v3 report.
- The TRAIN split is small (12 conflicts) and consists of official training routes the checkpoint has probably seen; TRAIN-fitted envelopes are optimistic for VAL, equally for both envelope designs.
- 32 VAL clips with very uneven conflict counts (BlockedIntersection alone holds 300 of 909); clip-bootstrap CIs are wide and condition on the chosen candidates. The frontier (Sec. 4) is in-sample.
- Only the isotropic E0 envelope family is compared, because the v2 global lease is defined for it; the v3 anisotropic families did not beat E0 at matched coverage in the gate2 study.
- Fig. 1 closed-loop data: one route per scenario type, seed 11 (44 routes) and 12 (15 routes); kappa 2.0 is an exploratory 11-route arm.

