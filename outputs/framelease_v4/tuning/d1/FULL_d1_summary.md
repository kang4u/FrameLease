# D1 training-route summary, variant FULL (framelease_v4/protocol/d1_summary.py)

Written 2026-11-15T06:38:37+0800; training routes only; realized validity on. Percentages: SR, fallback ratio, DMR, EIR, R_cond, P_both.

## ref (grid ref, stage 0, T22): 22/22 routes kept, 0 jobs pending

| candidate | outcomes | mean DS (kept) | DS | RC | SR | fallback | DMR | EIR | R_cond | P_both |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed_deep | {"ok": 22} | 46.0 | 46.0 | 79.8 | 5 | 2.2 | 0.0 | 35.78 | 100.0 | - |
| fast_only | {"ok": 22} | 75.5 | 75.5 | 93.8 | 45 | 2.1 | 0.0 | 10.92 | 100.0 | - |

## lease_s1 (grid lease, stage 1, T22a): 10/11 routes kept, 0 jobs pending
Dropped routes: {"23659": ["B0: queue: timeout (None)"]}
Selection outputs/framelease_v4/tuning/selection/FULL/lease_s1.json: survivors ['E5', 'B0']

| candidate | outcomes | mean DS (kept) | DS | RC | SR | fallback | DMR | EIR | R_cond | P_both |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| E5 (survivor) | {"ok": 11} | 44.3 | 46.6 | 60.0 | 9 | 74.6 | 74.5 | 8.80 | 61.5 | 52.7 |
| E10 | {"ok": 11} | 35.3 | 39.2 | 48.8 | 9 | 50.6 | 50.2 | 8.23 | 70.9 | 68.9 |
| B0 (survivor) | {"ok": 10, "sim_failure": 1} | 52.4 | 52.4 | 76.2 | 20 | 29.0 | 27.7 | 13.91 | 91.2 | 76.1 |

## event_s1 (grid event, stage 1, T22a): 11/11 routes kept, 0 jobs pending
Selection outputs/framelease_v4/tuning/selection/FULL/event_s1.json: survivors ['s_hb2.0', 's_hb1.0']

| candidate | outcomes | mean DS (kept) | DS | RC | SR | fallback | DMR | EIR | R_cond | P_both |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v2_hb2.0 | {"ok": 11} | 56.3 | 56.3 | 89.9 | 0 | 1.9 | 0.0 | 11.00 | 100.0 | - |
| v2_hb1.0 | {"ok": 11} | 60.5 | 60.5 | 90.6 | 18 | 1.8 | 0.0 | 18.75 | 100.0 | - |
| s_hb2.0 (survivor) | {"ok": 11} | 63.0 | 63.0 | 99.7 | 36 | 1.6 | 0.0 | 22.82 | 100.0 | - |
| s_hb1.0 (survivor) | {"ok": 11} | 61.4 | 61.4 | 100.0 | 18 | 2.0 | 0.0 | 23.73 | 100.0 | - |

## lease_s2 (grid lease, stage 2, T22b): 11/11 routes kept, 0 jobs pending
Selection outputs/framelease_v4/tuning/selection/FULL/lease_s2.json: selected B0

| candidate | outcomes | mean DS (kept) | DS | RC | SR | fallback | DMR | EIR | R_cond | P_both |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| E5 | {"ok": 11} | 37.6 | 37.6 | 46.4 | 0 | 80.2 | 79.8 | 4.04 | 17.4 | 33.6 |
| B0 (selected) | {"ok": 11} | 47.8 | 47.8 | 62.8 | 27 | 32.9 | 32.1 | 7.17 | 84.2 | 83.0 |

## event_s2 (grid event, stage 2, T22b): 11/11 routes kept, 0 jobs pending
Selection outputs/framelease_v4/tuning/selection/FULL/event_s2.json: selected s_hb2.0

| candidate | outcomes | mean DS (kept) | DS | RC | SR | fallback | DMR | EIR | R_cond | P_both |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| s_hb2.0 (selected) | {"ok": 11} | 60.3 | 60.3 | 90.5 | 18 | 1.7 | 0.0 | 29.15 | 100.0 | - |
| s_hb1.0 | {"ok": 11} | 56.5 | 56.5 | 90.8 | 18 | 1.8 | 0.0 | 27.08 | 100.0 | - |

## heur_s1 (grid heur, stage 1, T22a): 10/11 routes kept, 0 jobs pending
Dropped routes: {"23659": ["d10: queue: timeout (None)"]}
Selection outputs/framelease_v4/tuning/selection/FULL/heur_s1.json: survivors ['d10', 'd1']

| candidate | outcomes | mean DS (kept) | DS | RC | SR | fallback | DMR | EIR | R_cond | P_both |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| d10 (survivor) | {"ok": 10, "sim_failure": 1} | 52.4 | 52.4 | 76.2 | 20 | 29.0 | 27.7 | 13.91 | 91.2 | 76.1 |
| d4 | {"ok": 11} | 50.0 | 48.8 | 76.5 | 9 | 36.8 | 35.6 | 9.22 | 80.9 | 64.8 |
| d1 (survivor) | {"ok": 11} | 65.0 | 68.2 | 88.2 | 27 | 27.3 | 25.8 | 6.90 | 66.0 | 39.2 |

## heur_s2 (grid heur, stage 2, T22b): 11/11 routes kept, 0 jobs pending
Selection outputs/framelease_v4/tuning/selection/FULL/heur_s2.json: selected d1

| candidate | outcomes | mean DS (kept) | DS | RC | SR | fallback | DMR | EIR | R_cond | P_both |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| d10 | {"ok": 11} | 47.8 | 47.8 | 62.8 | 27 | 32.9 | 32.1 | 7.17 | 84.2 | 83.0 |
| d1 (selected) | {"ok": 11} | 49.9 | 49.9 | 69.9 | 9 | 45.8 | 44.9 | 7.07 | 38.2 | 20.3 |

## age_s1 (grid age, stage 1, T22a): 11/11 routes kept, 0 jobs pending
Selection outputs/framelease_v4/tuning/selection/FULL/age_s1.json: survivors ['A1.0', 'A2.5']

| candidate | outcomes | mean DS (kept) | DS | RC | SR | fallback | DMR | EIR | R_cond | P_both |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A1.0 (survivor) | {"ok": 11} | 67.8 | 67.8 | 100.0 | 27 | 2.3 | 0.3 | 15.32 | 73.0 | 28.6 |
| A1.5 | {"ok": 11} | 63.3 | 63.3 | 92.1 | 27 | 1.9 | 0.0 | 13.74 | 75.1 | 97.9 |
| A2.0 | {"ok": 11} | 63.2 | 63.2 | 99.7 | 18 | 1.9 | 0.0 | 15.48 | 89.3 | 100.0 |
| A2.5 (survivor) | {"ok": 11} | 63.6 | 63.6 | 89.9 | 18 | 1.9 | 0.0 | 19.47 | 100.0 | 100.0 |

## age_s2 (grid age, stage 2, T22b): 11/11 routes kept, 0 jobs pending
Selection outputs/framelease_v4/tuning/selection/FULL/age_s2.json: selected A1.0

| candidate | outcomes | mean DS (kept) | DS | RC | SR | fallback | DMR | EIR | R_cond | P_both |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A1.0 (selected) | {"ok": 11} | 60.2 | 60.2 | 90.1 | 27 | 3.5 | 1.6 | 14.72 | 85.0 | 10.8 |
| A2.5 | {"ok": 11} | 52.7 | 52.7 | 87.9 | 9 | 1.9 | 0.0 | 21.24 | 100.0 | 100.0 |

Tuning freeze: {"A_star": {"age_lease_s": 1.0}, "L_star": {"config": "T_x0.00", "envelope_path": "outputs/framelease_v4/envelopes/B0.json", "envelope_sha256": "9ef8479f04dab873d22b50e8732176804ed67f351f17584355b241e424fa1927", "label": "B0", "validity": "std"}, "d_star": {"d": 1, "utility": "v4_adet_d1"}, "event_star": {"candidate": "s_hb2.0", "policy_params": {"det_shift_m": 1.0, "heartbeat_s": 2.0, "speed_delta_mps": 0.5, "yaw_delta_rad": 0.05}}, "fl_risk": {"lease_point": "E5", "rule": "L* = B0: fl_risk runs the better of E5 / E10 by mean DS on lease_s1 (T22a), ties earlier"}, "sha256": "652fcbdbf0a6adb498aa0691fcaaffb097fcd680b4bf40235a28639aed69b930"}
