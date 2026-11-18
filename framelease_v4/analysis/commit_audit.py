"""Commit audit of one closed-loop run (R-2; framelease_v4/PROTOCOL.md Sec. 7.6 'Commit audit (all runs)', H5; GAP_AUDIT
Sec. 3.7 'R-2'). Read-only on the run directory; CPU only.

Records: every steps[].commit of raw/agent/framelease/jobs.jsonl (accepted and rejected offers) and, for a job that was
still running when the run ended (no jobs.jsonl row), its commit events in events.jsonl. Every ACCEPTED commit is
re-checked against Eq. 9 (framelease_v3/runtime/v3_commit.py):
  deadline   t_commit < D, the candidate's own deadline (steps[].validity.deadline_s; missing or NaN fails)
  margin     M(t_commit - t_k) > delta, for the arms with a lease, the shield and the commit-time margin (kind shield
             or age); delta is the run's resolved lease constant (config.json v4.v3.resolved.lease.delta_m), default
             0.2 m (PROTOCOL Sec. 2.4). The runtime logs a non-finite margin as null (v3_scheduler.margin_check;
             +inf: no agent able to bind). Null-margin rule: an accepted commit with a null margin passes, counted as
             margin_unrecorded, when its candidate's validity record names no relevant agent (n_relevant 0, else
             reason 'no_relevant_agents') or has reason 'horizon_cap' and n_computed 0. The second case is the lease
             prefilter (framelease_v3/runtime/v3_lease.py suffix_lease) keeping no relevant agent: each has g > delta
             on the whole grid, H = H_bar, and LeaseResult.margin is +inf for every window that ends by T_pred, i.e.
             for every commit with t_commit < D = t_k + H_bar (H_bar + T_c <= T_pred), so Eq. 9 holds. Any other
             accepted commit with a null margin whose record names a relevant agent is a margin violation. A commit
             event carries no validity record: its null margin is counted as margin_unrecorded
  version    (obs_id, depth) newer than the previous accepted commit in commit order: a newer observation, or the same
             observation at a greater depth
  cancelled  the job was open at the commit (t_commit <= its end_s), and the gate itself accepted the candidate
             (reason 'accepted', not overridden by the unversioned ablation); otherwise 'not_gate_accepted'
Log consistency: the accepted step commits of jobs.jsonl and the commit events of the same jobs are the same (job, depth,
t_commit) set. A commit in one of the two logs only (log_mismatches) is not an Eq. 9 violation, but the audit of that
run is incomplete (a commit recorded only in events.jsonl for a job with a jobs.jsonl row is not re-checked), so the run
is an ERROR, never a PASS.
Status: PASS (no violation), FAIL (any violation), NO_LOG (neither jobs.jsonl nor events.jsonl), ERROR (a
malformed record, or no violation but a log mismatch; reported with the cause).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v4.analysis import extra_metrics as XM  # noqa: E402
from framelease_v4.arms import metrics_v4 as MV  # noqa: E402

DELTA_M = 0.2                              # PROTOCOL Sec. 2.4 reserve delta (SuffixLeaseConfig default)
CHECKS = ('deadline', 'margin', 'version', 'cancelled', 'not_gate_accepted')
MAX_EXAMPLES = 5
NO_RELEVANT_REASON = 'no_relevant_agents'  # the validity reason of a candidate without a relevant agent (M = +inf)
HORIZON_CAP_REASON = 'horizon_cap'         # with n_computed 0: the prefilter kept no relevant agent (M = +inf)


def lease_delta(cfg):
    """delta of the run's resolved lease configuration (DELTA_M if it recorded none)."""
    lease = (((cfg.get('v4') or {}).get('v3') or {}).get('resolved') or {}).get('lease') or {}
    v = MV.num(lease.get('delta_m'))
    return DELTA_M if v is None else v


def _key(c):
    return int(c['job_id']), int(c['depth']), float(c['commit_s'])


def no_relevant_agents(validity):
    """True when a candidate's validity record says it had no relevant agent (n_relevant 0, else reason
    NO_RELEVANT_REASON), False when it says it had one, None when it records neither (a commit event)."""
    v = validity if isinstance(validity, dict) else {}
    if v.get('n_relevant') is not None:
        return int(v['n_relevant']) == 0
    if v.get('reason') is not None:
        return v['reason'] == NO_RELEVANT_REASON
    return None


def null_margin_explained(validity):
    """The null-margin rule (module docstring): True when a candidate's validity record explains a null (+inf) commit
    margin, i.e. it names no relevant agent (no_relevant_agents) or has reason HORIZON_CAP_REASON and n_computed 0 (the
    lease prefilter kept no relevant agent); False when it names a relevant agent otherwise (a missing n_computed is not
    0); None when it records neither n_relevant nor a reason (a commit event)."""
    none_relevant = no_relevant_agents(validity)
    if none_relevant is not False:
        return none_relevant
    return (validity.get('reason') == HORIZON_CAP_REASON and validity.get('n_computed') is not None
            and int(validity['n_computed']) == 0)


def commit_records(jobs, events):
    """(records, events_only, log_mismatches): one record per commit offer of jobs.jsonl plus the commit events of jobs
    without a jobs.jsonl row; each record {'job_id', 'obs_id', 'depth', 'accepted', 'reason', 'overridden', 'commit_s',
    'deadline_s', 'margin', 'null_margin_ok', 'job_end_s', 'source', 'order'} (null_margin_ok: null_margin_explained of
    the candidate's validity record, None for a commit event)."""
    out, logged = [], set()
    for j in jobs:
        for s in j.get('steps') or []:
            c = s.get('commit')
            if not isinstance(c, dict):
                continue
            out.append({'job_id': int(j['job_id']), 'obs_id': int(j['obs_id']), 'depth': int(s['depth']),
                        'accepted': bool(c.get('accepted')), 'reason': c.get('reason'),
                        'overridden': bool(c.get('overridden')), 'commit_s': MV.num(c.get('commit_s')),
                        'deadline_s': MV.num((s.get('validity') or {}).get('deadline_s')),
                        'margin': c.get('margin_at_commit_m'),
                        'null_margin_ok': null_margin_explained(s.get('validity')),
                        'job_end_s': MV.num(j.get('end_s')), 'source': 'jobs.jsonl', 'order': len(out)})
            if c.get('accepted') and c.get('commit_s') is not None:
                logged.add(_key({**c, 'job_id': j['job_id'], 'depth': s['depth']}))
    in_jobs = {int(j['job_id']) for j in jobs}
    ended = {int(e['job_id']): MV.num(e.get('sim_s')) for e in events if e.get('kind') == 'job_end'}
    seen, events_only = set(), 0
    for e in events:
        if e.get('kind') != 'commit' or e.get('commit_s') is None:
            continue
        jid = int(e['job_id'])
        if jid in in_jobs:
            seen.add(_key(e))
            continue
        events_only += 1
        out.append({'job_id': jid, 'obs_id': int(e['obs_id']), 'depth': int(e['depth']), 'accepted': True,
                    'reason': 'accepted', 'overridden': e.get('would_reject') is not None,
                    'commit_s': float(e['commit_s']), 'deadline_s': MV.num(e.get('deadline_s')),
                    'margin': e.get('margin_at_commit_m'), 'null_margin_ok': None, 'job_end_s': ended.get(jid),
                    'source': 'events.jsonl', 'order': len(out)})
    return out, events_only, len(logged ^ seen)


def audit_records(records, lease_arm, delta=DELTA_M):
    """({check: count}, margin_unrecorded, [examples]) over the accepted records in commit order (module docstring)."""
    acc = sorted((r for r in records if r['accepted']),
                 key=lambda r: (math.inf if r['commit_s'] is None else r['commit_s'], r['order']))
    counts = {k: 0 for k in CHECKS}
    unrecorded, examples, prev = 0, [], None
    for r in acc:
        bad = []
        t, dl = r['commit_s'], r['deadline_s']
        if t is None or dl is None or not t < dl:
            bad.append('deadline')
        if lease_arm:
            m = MV.num(r['margin'])
            if r['margin'] is None and r.get('null_margin_ok') is False:
                bad.append('margin')                # a null margin the validity record does not explain
            elif r['margin'] is None:
                unrecorded += 1
            elif m is None or not m > delta:
                bad.append('margin')
        if prev is not None and not (r['obs_id'] > prev['obs_id']
                                     or (r['obs_id'] == prev['obs_id'] and r['depth'] > prev['depth'])):
            bad.append('version')
        if t is not None and r['job_end_s'] is not None and t > r['job_end_s'] + XM.EPS:
            bad.append('cancelled')
        if r['reason'] != 'accepted' or r['overridden']:
            bad.append('not_gate_accepted')
        for k in bad:
            counts[k] += 1
        if bad and len(examples) < MAX_EXAMPLES:
            examples.append({'job_id': r['job_id'], 'obs_id': r['obs_id'], 'depth': r['depth'], 'commit_s': t,
                             'deadline_s': dl, 'margin': r['margin'], 'source': r['source'], 'violations': bad})
        prev = r
    return counts, unrecorded, examples


def audit_run(run_dir, logs=None):
    """The commit audit of one run directory (module docstring)."""
    run_dir = Path(run_dir)
    fl = run_dir / 'raw' / 'agent' / 'framelease'
    logs = XM.load_logs(run_dir) if logs is None else logs
    cfg = logs['cfg']
    lease_arm = XM.arm_kind(cfg) in XM.LEASE_KINDS
    delta = lease_delta(cfg)
    out = {'run_dir': str(run_dir), 'arm_kind': XM.arm_kind(cfg), 'margin_checked': lease_arm,
           'delta_m': delta if lease_arm else None}
    if not (fl / 'jobs.jsonl').is_file() and not (fl / 'events.jsonl').is_file():
        return {**out, 'status': 'NO_LOG', 'offers': 0, 'accepted': 0, 'events_only': 0, 'margin_unrecorded': 0,
                'violations': {k: 0 for k in CHECKS}, 'n_violations': 0, 'log_mismatches': 0, 'examples': []}
    try:
        records, events_only, mismatches = commit_records(logs['jobs'], logs['events'])
        counts, unrecorded, examples = audit_records(records, lease_arm, delta)
    except (KeyError, TypeError, ValueError) as e:      # a malformed record: reported, never silently passed
        return {**out, 'status': 'ERROR', 'error': f'{type(e).__name__}: {e}', 'offers': 0, 'accepted': 0,
                'events_only': 0, 'margin_unrecorded': 0, 'violations': {k: 0 for k in CHECKS}, 'n_violations': 0,
                'log_mismatches': 0, 'examples': []}
    n = sum(counts.values())
    # a commit in one log only was not checked against Eq. 9 in the other: never a pass (H5 needs every commit)
    status = 'FAIL' if n else 'ERROR' if mismatches else 'PASS'
    extra = {'error': f'{mismatches} accepted commits differ between jobs.jsonl and events.jsonl'} \
        if status == 'ERROR' else {}
    return {**out, 'status': status, **extra, 'offers': len(records),
            'accepted': sum(1 for r in records if r['accepted']), 'events_only': events_only,
            'margin_unrecorded': unrecorded, 'violations': counts, 'n_violations': n, 'log_mismatches': mismatches,
            'examples': examples}


__all__ = ['DELTA_M', 'CHECKS', 'NO_RELEVANT_REASON', 'HORIZON_CAP_REASON', 'lease_delta', 'no_relevant_agents',
           'null_margin_explained', 'commit_records', 'audit_records', 'audit_run']
