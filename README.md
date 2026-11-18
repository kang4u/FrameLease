# FrameLease

Action-validity-aware compute scheduling for a deep-reasoning driving VLA (UniDriveVLA) in closed-loop CARLA /
Bench2Drive. FrameLease turns the validity of each candidate trajectory into a compute deadline (action-conditioned,
suffix-aligned validity lease), admits only refinement or refresh operations that can commit before the active plan
expires (feasibility shield), ranks the admitted operations with an offline-trained CPU Q-network, and commits only
unexpired, uncancelled, non-regressive candidates (versioned commit, watchdog, cooperative preemption).

This repository holds the code, the pre-registered experimental protocol with its amendments, the registered job files
and the registered results of the experiment. It is the state of 2026-11-18.

## Status

| part | state |
|---|---|
| Protocol | `framelease_v4/PROTOCOL.md` (FULL), sealed; amendments A1-A17 in its Sec. 13.2 |
| Phase 1 (tuning on training routes) | done: L* = B0, d* = 1, A* = 1.0 s, Event-Triggered s_hb2.0 (`outputs/framelease_v4/tuning/`) |
| Phase 2-3 (offline RL data, FQI, stress tests S1-S3, test freeze) | done (`rl_data/`, `rl_freeze/`, `stress/`, `test_freeze/`) |
| Test phase, cut analysis | 14 of 44 test routes (Amendment A12), frozen (A13), verified (A14-A16): `outputs/framelease_v4/analysis/final_20261116T091445/`, `outputs/framelease_v4/verification/` |
| Test phase, remaining 505 jobs | running under Amendment A17; not included; analysed after a second freeze |

Registered results of the cut analysis (14 test routes, kappa 1.0; `analysis/final_20261116T091445/analysis/`):
H1 (Full FrameLease vs. Fixed Deep, Fast Only, Age-Only, Event-Triggered) inconclusive for all four contrasts;
H2 (RL vs. heuristic utility) inconclusive; H3 (vs. the earlier design) improves; secondary DMR family worse;
secondary collision family inconclusive; H5 (commit invariant) contradicted under the registered rule with 0 violations
in 94,650 audited commits, because one interrupted Phase-1 attempt left no logs.

## Layout

| path | content |
|---|---|
| `framelease_v4/` | method, arms, runtime, RL pipeline, protocol tools, analysis and verification code, tests; `PROTOCOL.md` |
| `framelease_v2/`, `framelease_v3/` | earlier modules that v4 imports (lease geometry, queue runner, latency agent, fast prefix, profiling) |
| `framelease_common.py`, `stage02_real_vla.py`, `stage05_carla_closed_loop.py` | registered root modules used by the closed-loop launcher |
| `linux/`, `configs/` | environment setup scripts, CARLA start script, requirement lists (`configs/requirements_lock_linux.txt`: exact Python packages) |
| `outputs/framelease_v4/registration/` | registration manifest (`MANIFEST.sha256`, 221 files) and seal |
| `outputs/framelease_v4/{p1_jobs,p2_jobs,test_jobs,cut_*}/` | registered job files |
| `outputs/framelease_v4/{tuning,rl_data,rl_freeze,stress,offline_ablation,envelopes}/` | registered selections, RL freeze, stress reports, offline ablation |
| `outputs/framelease_v4/{analysis,verification}/` | frozen cut analysis (aggregations, contrasts, figures, `numbers.json`) and its independent verifications |
| `outputs/framelease_v4/amendment_*/`, `build/AMEND2/` | amendment application records and the appliers |
| `docs/EXTERNAL_FILES.md` | registered files not in this repository (model weights, unmodified third-party code, source documents) |
| `scripts/verify_registration.sh` | checks every registered file present here against the manifest and the seal |

## Integrity

```
bash scripts/verify_registration.sh
```

checks the 206 registered files in this repository against `MANIFEST.sha256` (the other 15 are listed in
`docs/EXTERNAL_FILES.md`), the seal of `PROTOCOL.md` and the manifest, and every sha256 list of the included outputs.
Result at packaging: no mismatch.

## Environment

Ubuntu 26.04, one NVIDIA RTX 4090 D (driver 595.99), CUDA 12.4, Python 3.10.22, PyTorch 2.5.1+cu124, CARLA 0.9.15,
Bench2Drive, UniDriveVLA (github.com/xiaomi-research/unidrivevla, commit a93c175) with the checkpoint
`UniDriveVLA_Stage3_Bench2drive_2B.pt` (sha256 in `docs/EXTERNAL_FILES.md`). Package versions:
`configs/requirements_lock_linux.txt`. Setup scripts: `linux/`.

The code expects the project root at `/home/kang/Desktop/DAC` in several registered modules (absolute paths). The
registered files stay byte-identical to their registered sha256; place or link a checkout at that path to run the tools
unchanged.

## Reproduction

* Statistics, figures and tables from the included aggregations: `framelease_v4/analysis/analyze_v4.py`,
  `figures_tables.py`, `verify_independent.py` on `outputs/framelease_v4/analysis/final_20261116T091445/agg_p{1,2,4}`
  (commands: `outputs/framelease_v4/build/G8CUT/RUNBOOK.md` in the source project, Sec. 7-8; a scripted check in this
  repository follows).
* Closed-loop experiment: the phases P0-P7 of `PROTOCOL.md` Secs. 8 and 10 (about 131 GPU-hours for the FULL plan),
  with the external files of `docs/EXTERNAL_FILES.md`.

Raw run directories (about 6 GB) are not in this repository.

## License

MIT (`LICENSE`). Third-party code and model weights keep their own licenses.
