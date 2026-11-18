"""FrameLease v4 arm extension (new files only; nothing in framelease_v2 / framelease_v3 / framelease_v4/arms is edited).

global_shield.py        GlobalMarginShieldPolicy: the v3 shield and a_det^d with the v2 global-margin lease (E* as B(D),
                        cap H_bar 2.5 s, synthetic commit-time margin): Table II-A arm fl_global_shield (PROTOCOL
                        Secs. 4.1, 7.4)
arms_ext.py             register(): the additive arm registry (arms_v4 arms delegated unchanged, fl_global_shield runs
                        as its base arm fl_heuristic with the new policy class); build_config / agent_config_from /
                        validate_config / build_policy
agent_ext.py            evaluator agent of the extension arms (the pinned FrameLeaseV4Agent with the extension registry
                        in setup()) and its entry file
run_closed_loop_ext.py  launcher: arms_v4 arms -> the pinned run_closed_loop_v4.main unchanged; fl_global_shield -> a
                        copy of its run() with the extension entry and sources; job_line() / check_job_line()
tests/                  CPU tests (offline frames, commit margin, additive-only registry and launcher, the copied run(),
                        fake-backend agent runs, job line, fixed lease constants, drift guard of the copied functions)
No attribute of a pinned module is rebound and no pinned object is mutated (PROTOCOL Sec. 8.3; tested).

Side effect of importing this package: sys.dont_write_bytecode = True for the whole process (set below, so that no
byte-code cache is written into the pinned trees). In the evaluator's agent process of a fl_global_shield run the entry
file imports the package before the agent class is built, so that process writes no cache for the modules it imports
afterwards (the agent, policy, runtime and model stack), while fl_heuristic's agent process may write them. Reading
is unchanged: an existing cache is still used, and a module without one is compiled in memory as in any process. The
setting acts at import time only. The agent's modules are imported before the first tick (entry import,
get_entry_point, setup()), so it cannot change the simulated timeline. The launcher processes of every arm already run
with python -B.

  cd /home/kang/Desktop/DAC && source linux/env.sh
  .conda-unidrive-linux/bin/python -B framelease_v4/arms_ext/run_closed_loop_ext.py --arm fl_global_shield \
      --route-id R --envelope outputs/framelease_v4/envelopes/<E*>.json --policy-params '{"utility": "<a_det^d*>"}' \
      [--dry-run]                                     # job lines: run_closed_loop_ext.job_line / check_job_line
  export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 && nice -n 19 .conda-unidrive-linux/bin/python -I -B -m pytest -q \
      -p no:cacheprovider framelease_v4/arms_ext/tests
"""

import sys as _sys

# Never write byte-code caches into the read-only framelease_v2 / framelease_v3 trees (several of their files are
# sha256-pinned by queued jobs; caches are not pinned, but the extension must not add files there either).
_sys.dont_write_bytecode = True
