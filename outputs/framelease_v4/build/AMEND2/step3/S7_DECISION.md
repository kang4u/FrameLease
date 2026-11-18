# S7 decision (coordinating session, 2026-11-15 06:45 Beijing time)

Question (RUNBOOK step 0, open issue S7): adopt the optional hardening of `framelease_v4/analysis/commit_audit.py`
proposed by the AGG0 review (should-fix S2 and S4) before step 3 registers the file?

Decision: not adopted. Step 3 registers `commit_audit.py` at the AGG0-reviewed version (7439a4ea...).

Reasons, from the AGG0 review (workflow wf_73fd0158-072, review:AGG0, verdict GO):
* S2 (check lease_s = H_bar on the horizon_cap pass): the review states that real runs cannot produce the inconsistent
  record. The commit gate rejects M = -inf, v3_lease sets H = H_bar on this path, and all 12,958 real horizon_cap
  commits of lease_s1 / lease_s2 have lease_s 2.5 s and a window end of at most 1.378 s. The check adds no detection.
* S4 (exclude VL.INVALID_REASONS from the n_relevant-0 case): an invalid v3 lease (perception_unavailable,
  invalid_detection) logs n_relevant 0 and passes the margin line, but the deadline line flags the same commit (lease 0,
  D = t_k). The H5 audit therefore still counts the commit as a violation; S4 changes which line reports it, not
  whether it is reported.

Consequence: H5 is decided by the registered rule of E3 / A10 finding 1. A later change of `commit_audit.py` needs an
amendment that installs the file under the lock (APPLY_PLAN2 Sec. 5, item 1).
