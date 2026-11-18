"""Versioned commit (outline Eq. 9) as a small pure state machine, shared by the runtime and the fault-injection tests.

A candidate may become the controller's action only if, at the commit instant t_commit:

  1. it is not cancelled (its job is not closed and the candidate was not cancelled explicitly);
  2. it is a finite, kinematically plausible 6 x 2 plan (framelease_v2.latency_agent.kinematic_check);
  3. its version is admissible: a newer observation than the latest committed candidate, or the same observation at
     a greater refinement depth (a late result of an older observation never overwrites a newer one);
  4. t_commit < D (its own lease deadline; a NaN deadline fails);
  5. M(t_commit - t_k) > delta (the suffix margin at the commit age, Eq. 1; implied by 4 for an exact lease and
     checked independently).

The checks run in this order and the first failure is the logged reason. The reasons of 2-4 are those of
framelease_v2.latency_agent.versioned_commit_check, so with nothing cancelled and the margin satisfied the gate
decides exactly as v2 does (tested). Program invariant (tested on >= 100000 random event sequences): an expired,
cancelled, invalid or regressive candidate is never committed, and committed versions strictly increase.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Version:
    obs_id: int
    depth: int

    def newer_than(self, other: Optional['Version']):
        if other is None:
            return True
        return self.obs_id > other.obs_id or (self.obs_id == other.obs_id and self.depth > other.depth)


REASONS = ('accepted', 'cancelled', 'invalid', 'stale_version:older_observation', 'stale_version:not_deeper',
           'expired_before_commit', 'margin_violated_at_commit')


class CommitGate:
    """State: the version of the latest committed candidate, closed jobs and explicitly cancelled candidates."""

    def __init__(self):
        self.latest: Optional[Version] = None
        self.latest_job: Optional[int] = None
        self.latest_deadline_s = -math.inf
        self.closed_jobs = set()
        self.cancelled = set()
        self.counts = {}

    # -------------------------------------------------------------- cancellation
    def close_job(self, job_id):
        """Every later completion of this job is cancelled (REFRESH / end of job)."""
        self.closed_jobs.add(int(job_id))

    def cancel(self, job_id, depth=None):
        """Cancel one candidate (job_id, depth) or, with depth None, the whole job."""
        if depth is None:
            self.close_job(job_id)
        else:
            self.cancelled.add((int(job_id), int(depth)))

    def is_cancelled(self, job_id, depth):
        return int(job_id) in self.closed_jobs or (int(job_id), int(depth)) in self.cancelled

    # -------------------------------------------------------------- check / commit
    def check(self, job_id, version: Version, deadline_s, t_commit, valid=(True, 'ok'), margin_ok=True):
        """(accept, reason) without changing state. valid = (bool, why) of the kinematic check."""
        if self.is_cancelled(job_id, version.depth):
            return False, 'cancelled'
        ok, why = valid
        if not ok:
            return False, 'invalid:' + str(why)
        latest = self.latest
        if latest is not None:
            if version.obs_id < latest.obs_id:
                return False, 'stale_version:older_observation'
            if version.obs_id == latest.obs_id and version.depth <= latest.depth:
                return False, 'stale_version:not_deeper'
        d = float(deadline_s)
        if math.isnan(d) or not float(t_commit) < d:
            return False, 'expired_before_commit'
        if not margin_ok:
            return False, 'margin_violated_at_commit'
        return True, 'accepted'

    def offer(self, job_id, version: Version, deadline_s, t_commit, valid=(True, 'ok'), margin_ok=True):
        ok, reason = self.check(job_id, version, deadline_s, t_commit, valid, margin_ok)
        key = reason.split(':')[0] if reason.startswith('invalid') else reason
        self.counts[key] = self.counts.get(key, 0) + 1
        if ok:
            self.latest = version
            self.latest_job = int(job_id)
            self.latest_deadline_s = float(deadline_s)
        return ok, reason


__all__ = ['Version', 'CommitGate', 'REASONS']
