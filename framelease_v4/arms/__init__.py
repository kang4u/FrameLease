"""FrameLease v4 Table I arms: baselines, the common runtime substrate, metrics and evaluation-only actor logging.

policies_v4.py        Age-Only (v3 shield + constant observation-age lease) and Event-Triggered (v2 rules + heartbeat
                      + v3-schema decision rows); DecisionRowsMixin for the v2 baselines
runtime_v4.py         V4Runtime: ONE runtime class for every arm (v2 timeline, v3 commit gate / watchdog, uniform
                      summary block)
arms_v4.py            the seven arms of Table I, their exact configuration and the policy factory
actor_log.py          compact CARLA ground-truth actor-box log (evaluation only) and its decoder
realized.py           realized validity of committed plans from the actor log (closed-loop analogue of the offline V)
agent_v4.py           evaluator agent: v2 latency agent + v4 setup + fast prefix + actor log
run_closed_loop_v4.py launcher composing the v3 launcher helpers and the fast-prefix option
metrics_v4.py         per-run and per-arm metrics (DS, RC, SR, GPU usage, deadline misses, action age, fallback, P_both)
jobs_v4.py            dry-run job lines (written, never launched)
See README.md.
"""
