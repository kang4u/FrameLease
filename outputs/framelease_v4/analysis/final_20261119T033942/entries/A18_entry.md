**Amendment A18, 2026-11-19 (Beijing time): the analysis freeze (Sec. 9.12) with all 632 test jobs final**

This amendment records the second analysis freeze after Amendment A17 completed the 505 jobs cut by Amendment A12.

Trigger: all_final (every test job has a final outcome).

Analysis-freeze record: `outputs/framelease_v4/analysis/final_20261119T033942/analysis_freeze.json` (sha256 `7caf9e9f1a7d44ea6e451ce93631d978c7193eb502f53c31bb9dbaedec744047`), 632 jobs (631 ok, 1 sim_failure), covering:
- Table I main outcomes (210 routes × 5 arms)
- Fig. 3 ablations (160 jobs)
- Lease parameter sweep (19 jobs)
- RL ablations (40 jobs)  
- Seed robustness s=12 (56 jobs)
- Risk envelope E5 (20 jobs)

Required job files (sha256 cited by Amendment A11): `outputs/framelease_v4/analysis/final_20261119T033942/required_job_files.json`.

The six job files in `outputs/framelease_v4/queue_p4/jobs.d/`:
- `b11_ti_main.jsonl`: 54e551df44f30a02277e91849f1e40390cd77ffca7e59256edc98b3f5cd4a6df
- `b12_f3_k.jsonl`: 8ba8a4e5f6874860f9fefae81d836ccbdd297ac6a801a67663d6a5322507311b
- `b13_a_lease.jsonl`: 6b906bc220d74fdf8fb5bfce287465e608fd378b22869af6d188ec411d37bd2a
- `b14_a_rl.jsonl`: a73491e47ab5cb3fcba868a0e5e6bf7f34c5ad6a09ea3fde8cd11d18ef623e31
- `b15_s_seed12.jsonl`: bd77e5ed172bc834b63a4fa188cae97f92047f8072a45b92e738aad52cffd207
- `b16_s_risk.jsonl`: 83fe874f000340d6ee15509c35c7829bd03a6612a75a181e82c0b26ab36a156b

Analysis code (sha256 cited by Amendment A10):
- `framelease_v4/analysis/aggregate_v4.py`: ee13c90b91bf44ad59d0a3c7e60bf93d65964785ed386d3e81c44fea0f5e4b96
- `framelease_v4/analysis/analyze_v4.py`: 10d7ea4f9516725cd94932a0618bbe5cc6a20bae60b49f4004013b3682cee54c

No run, job line, criterion or analysis rule is changed by this entry.
