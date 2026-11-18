**Amendment A7, 2026-11-15 06:22 (Beijing time): a supplementary S2 grid relative to each state's Eq. 5 slack floor
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
  `8c50b99209af9648f0ff35c95a8725a1c6585f221dbd26ea1d56545a2e60e0c9`, sealed with this entry.
