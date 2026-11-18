# FrameLease

Action-validity-aware compute scheduling for a deep-reasoning driving VLA (UniDriveVLA) in closed-loop CARLA /
Bench2Drive. FrameLease turns the validity of each candidate trajectory into a compute deadline (action-conditioned,
suffix-aligned validity lease), admits only refinement or refresh operations that can commit before the active plan
expires (feasibility shield), ranks the admitted operations with an offline-trained CPU Q-network, and commits only
unexpired, uncancelled, non-regressive candidates (versioned commit, watchdog, cooperative preemption).

This repository holds the code, the pre-registered experimental protocol with its amendments, the registered job files
and the registered results of the experiment. It is the state of 2026-11-18.


## Layout

| path | content |
|---|---|
| `framelease/` | method, arms, runtime, RL pipeline, protocol tools, analysis and verification code, tests; `PROTOCOL.md` |
| `framelease_common.py`, `stage02_real_vla.py`, `stage05_carla_closed_loop.py` | registered root modules used by the closed-loop launcher |
| `linux/`, `configs/` | environment setup scripts, CARLA start script, requirement lists (`configs/requirements_lock_linux.txt`: exact Python packages) |
| `outputs/framelease/registration/` | registration manifest (`MANIFEST.sha256`, 221 files) and seal |
| `outputs/framelease/{p1_jobs,p2_jobs,test_jobs,cut_*}/` | registered job files |
| `outputs/framelease/{tuning,rl_data,rl_freeze,stress,offline_ablation,envelopes}/` | registered selections, RL freeze, stress reports, offline ablation |
| `outputs/framelease/{analysis,verification}/` | frozen cut analysis (aggregations, contrasts, figures, `numbers.json`) and its independent verifications |
| `outputs/framelease/amendment_*/`, `build/AMEND2/` | amendment application records and the appliers |
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

## License

MIT (`LICENSE`). Third-party code and model weights keep their own licenses.
