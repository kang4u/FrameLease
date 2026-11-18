"""FrameLease v4 RL pipeline (outline 1109 Sec. III-B, Eq. 6-8; Table II-A ablations).

behaviour.py   epsilon-random behaviour utility inside the v3 shield (logged propensities), registered in
               framelease_v3.runtime.v3_shield.UTILITIES through framelease_v4 entries (no v3 file is edited)
agent_entry.py evaluator agent entry: registers the v4 utility named in the v3 agent config, then the v3 /
               fast-prefix agent runs unchanged
prefix_score.py  prefix driving score S(t) = route completion so far x infraction penalty so far (Bench2Drive scorer)
dataset.py     closed-loop run directories -> decision epochs, SMDP transitions over choice epochs, rewards (Eq. 7)
features.py    the 16 state features (lease slack, observation age, refinement progress, budget, latencies, ...)
trainers.py    finite-horizon undiscounted fitted Q-iteration, contextual bandit, FQI without lease features,
               distillation into a small MLP
ope.py         off-policy evaluation for pre-specified model selection (FQE primary; WPDIS / WDR diagnostics)
qnet.py        CPU Q-network: fixed weights, preallocated buffers, budgeted call, bypass to a_det^d (Eq. 8)
bench_qnet.py  CPU microbenchmark; smoke.py end-to-end smoke on the fast-prefix pilot runs
run_closed_loop_rl.py / collection_plan.py  launcher wrapper (dry-run) and the training-route collection plan
See README.md and RL_PROTOCOL.md (and framelease_v4/PROTOCOL.md Secs. 4.7, 5).
"""

import sys as _sys

# Never write byte-code caches into the read-only framelease_v2 / framelease_v3 trees (several of their files are
# sha256-pinned by queued jobs; caches are not pinned, but v4 must not add files there either).
_sys.dont_write_bytecode = True
