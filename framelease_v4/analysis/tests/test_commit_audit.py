"""The commit audit R-2 (framelease_v4/analysis/commit_audit.py; PROTOCOL Sec. 7.6 'Commit audit (all runs)'). CPU only;
every log is synthetic: a clean log passes, and each Eq. 9 violation, injected alone, is counted under its own check.

  cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/analysis/tests/test_commit_audit.py
"""
from __future__ import annotations

import copy
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ['CUDA_VISIBLE_DEVICES'] = ''
sys.dont_write_bytecode = True

from framelease_v4.analysis import commit_audit as CA  # noqa: E402

# the base lease-parameter file of the v3 runtime tests (framelease_v3/runtime/tests/helpers_v3.py LEASE_PARAMS)
LEASE_PARAMS = ROOT / 'outputs/framelease_v2/c2_calibration/full_20261107T045343Z/lease_params_q95_envelope.json'


def step(depth, commit_s, deadline_s, accepted=True, margin=0.5, reason=None, overridden=False):
    return {'depth': depth, 'validity': {'deadline_s': deadline_s},
            'commit': {'accepted': accepted, 'reason': reason or ('accepted' if accepted else 'expired_before_commit'),
                       'commit_s': commit_s, 'margin_at_commit_m': margin, 'overridden': overridden}}


def clean_jobs():
    """Two finished jobs: obs 0 committed at depths 1 and 2, obs 5 at depth 1; one rejected offer."""
    return [{'job_id': 1, 'obs_id': 0, 'start_s': 0.0, 'end_s': 0.7,
             'steps': [step(1, 0.45, 1.0), step(2, 0.47, 1.1, margin=None), step(3, 0.69, 0.6, accepted=False)]},
            {'job_id': 2, 'obs_id': 5, 'start_s': 0.7, 'end_s': 1.3, 'steps': [step(1, 1.2, 2.0)]}]


def events_of(jobs, extra=()):
    out = []
    for j in jobs:
        for s in j['steps']:
            if s['commit']['accepted']:
                out.append({'kind': 'commit', 'job_id': j['job_id'], 'obs_id': j['obs_id'], 'depth': s['depth'],
                            'commit_s': s['commit']['commit_s'], 'deadline_s': s['validity']['deadline_s'],
                            'margin_at_commit_m': s['commit']['margin_at_commit_m'], 'would_reject': None})
        out.append({'kind': 'job_end', 'job_id': j['job_id'], 'sim_s': j['end_s']})
    return out + list(extra)


def audit(jobs, events=None, lease_arm=True):
    records, events_only, mismatches = CA.commit_records(jobs, events_of(jobs) if events is None else events)
    counts, unrecorded, examples = CA.audit_records(records, lease_arm)
    return counts, unrecorded, examples, events_only, mismatches


class Records(unittest.TestCase):
    def test_clean_log_passes(self):
        counts, unrecorded, examples, events_only, mismatches = audit(clean_jobs())
        self.assertEqual(sum(counts.values()), 0)
        self.assertEqual((unrecorded, events_only, mismatches, examples), (1, 0, 0, []))

    def one(self, mutate, lease_arm=True):
        jobs = clean_jobs()
        mutate(jobs)
        counts = audit(jobs, lease_arm=lease_arm)[0]
        return {k: v for k, v in counts.items() if v}

    def test_each_violation_alone(self):
        def late(j):
            j[1]['steps'][0]['validity']['deadline_s'] = 1.2             # t_commit = D
        def no_deadline(j):
            j[1]['steps'][0]['validity']['deadline_s'] = None
        def margin(j):
            j[0]['steps'][0]['commit']['margin_at_commit_m'] = 0.2       # M must exceed delta strictly
        def older(j):
            j[1]['obs_id'] = 0                                           # obs 0 depth 1 after obs 0 depth 2
        def not_deeper(j):
            j[0]['steps'][1]['depth'] = 1
        def cancelled(j):
            j[0]['end_s'] = 0.46                                         # depth 2 committed after the job closed
        def overridden(j):
            j[1]['steps'][0]['commit']['overridden'] = True
        def wrong_reason(j):
            j[1]['steps'][0]['commit']['reason'] = 'expired_before_commit'
        cases = [(late, {'deadline': 1}), (no_deadline, {'deadline': 1}), (margin, {'margin': 1}),
                 (older, {'version': 1}), (not_deeper, {'version': 1}), (cancelled, {'cancelled': 1}),
                 (overridden, {'not_gate_accepted': 1}), (wrong_reason, {'not_gate_accepted': 1})]
        for mutate, want in cases:
            with self.subTest(mutate.__name__):
                self.assertEqual(self.one(mutate), want)

    def test_margin_only_for_lease_arms(self):
        def margin(j):
            j[0]['steps'][0]['commit']['margin_at_commit_m'] = -1.0
        self.assertEqual(self.one(margin, lease_arm=False), {})
        counts, unrecorded = CA.audit_records(CA.commit_records(clean_jobs(), events_of(clean_jobs()))[0], False)[:2]
        self.assertEqual((sum(counts.values()), unrecorded), (0, 0))

    def test_rejected_offers_are_not_audited(self):
        jobs = clean_jobs()
        jobs[0]['steps'][2]['commit']['commit_s'] = 5.0                  # rejected: past its deadline, never applied
        self.assertEqual(sum(audit(jobs)[0].values()), 0)

    def test_running_job_commits_from_events(self):
        jobs = clean_jobs()
        tail = [{'kind': 'commit', 'job_id': 3, 'obs_id': 9, 'depth': 1, 'commit_s': 1.9, 'deadline_s': 1.8,
                 'margin_at_commit_m': 0.4, 'would_reject': None}]
        counts, _, examples, events_only, mismatches = audit(jobs, events_of(jobs, tail))
        self.assertEqual((events_only, mismatches), (1, 0))
        self.assertEqual({k: v for k, v in counts.items() if v}, {'deadline': 1})
        self.assertEqual((examples[0]['source'], examples[0]['violations']), ('events.jsonl', ['deadline']))
        tail[0].update(commit_s=1.5, obs_id=4)                             # obs 4 after obs 5: a regression
        counts = audit(jobs, events_of(jobs, tail))[0]
        self.assertEqual({k: v for k, v in counts.items() if v}, {'version': 1})

    def test_log_mismatch(self):
        jobs = clean_jobs()
        ev = [e for e in events_of(jobs) if not (e['kind'] == 'commit' and e['job_id'] == 2)]
        self.assertEqual(audit(jobs, ev)[4], 1)
        ev = events_of(jobs, [{'kind': 'commit', 'job_id': 1, 'obs_id': 0, 'depth': 3, 'commit_s': 0.69}])
        self.assertEqual(audit(jobs, ev)[4], 1)

    def test_null_margin_needs_no_relevant_agent(self):
        """The runtime logs M = +inf as null: a null margin passes when the candidate's validity record says it had
        no relevant agent (or carries no such record: a commit event); a record that names a relevant agent without
        the horizon_cap rule (next test) is a margin violation."""
        cases = [({'n_relevant': 0, 'reason': 'no_relevant_agents'}, {}, 1),
                 ({'reason': 'no_relevant_agents'}, {}, 1), ({'n_relevant': 0}, {}, 1),
                 ({'n_relevant': 2, 'reason': 'ok'}, {'margin': 1}, 0), ({'reason': 'ok'}, {'margin': 1}, 0),
                 ({}, {}, 1)]
        for validity, want, unrecorded in cases:
            with self.subTest(validity=validity):
                jobs = [{'job_id': 1, 'obs_id': 0, 'end_s': 0.7, 'steps': [step(1, 0.45, 1.0, margin=None)]}]
                jobs[0]['steps'][0]['validity'].update(validity)
                counts, unrec = audit(jobs)[:2]
                self.assertEqual(({k: v for k, v in counts.items() if v}, unrec), (want, unrecorded))
        self.assertEqual([CA.no_relevant_agents(v) for v in ({'n_relevant': 0, 'reason': 'x'}, {'reason': 'x'}, None)],
                         [True, False, None])

    def test_null_margin_of_a_horizon_cap_lease(self):
        """APPLY_PLAN2 Sec. 5 item 1: a null margin also passes when the record has reason horizon_cap and n_computed 0
        (the lease prefilter kept no relevant agent, M = +inf); horizon_cap with n_computed > 0 (or unrecorded), and
        n_computed 0 under another reason, leave a null margin with a relevant agent unexplained: a violation."""
        cap0 = {'n_relevant': 3, 'reason': 'horizon_cap', 'n_computed': 0, 'min_g_m': None}
        cases = [(cap0, {}, 1, True),
                 ({**cap0, 'n_computed': 2}, {'margin': 1}, 0, False),
                 ({**cap0, 'n_computed': 1, 'min_g_m': 0.9}, {'margin': 1}, 0, False),
                 ({'n_relevant': 3, 'reason': 'horizon_cap'}, {'margin': 1}, 0, False),
                 ({**cap0, 'reason': 'first_failure'}, {'margin': 1}, 0, False),
                 ({**cap0, 'n_computed': 0.0}, {}, 1, True),
                 ({'reason': 'horizon_cap', 'n_computed': 0}, {}, 1, True),
                 ({**cap0, 'n_relevant': 0}, {}, 1, True)]
        for validity, want, unrecorded, explained in cases:
            with self.subTest(validity=validity):
                self.assertIs(CA.null_margin_explained(validity), explained)
                jobs = [{'job_id': 1, 'obs_id': 0, 'end_s': 0.7, 'steps': [step(1, 0.45, 1.0, margin=None)]}]
                jobs[0]['steps'][0]['validity'].update(validity)
                counts, unrec, examples = audit(jobs)[:3]
                self.assertEqual(({k: v for k, v in counts.items() if v}, unrec), (want, unrecorded))
                if want:
                    self.assertEqual((examples[0]['margin'], examples[0]['violations']), (None, ['margin']))
        self.assertIsNone(CA.null_margin_explained(None))
        self.assertIsNone(CA.null_margin_explained({'deadline_s': 1.0}))
        jobs = [{'job_id': 1, 'obs_id': 0, 'end_s': 0.7, 'steps': [step(1, 0.45, 1.0, margin=0.1)]}]
        jobs[0]['steps'][0]['validity'].update(cap0)                     # the rule covers null margins only
        self.assertEqual({k: v for k, v in audit(jobs)[0].items() if v}, {'margin': 1})
        self.assertEqual({k: v for k, v in audit(jobs, lease_arm=False)[0].items() if v}, {})

    def test_null_margin_of_a_commit_event_is_unrecorded(self):
        """A commit event carries no validity record: its null margin keeps its treatment (margin_unrecorded)."""
        jobs = clean_jobs()
        tail = [{'kind': 'commit', 'job_id': 3, 'obs_id': 9, 'depth': 1, 'commit_s': 1.5, 'deadline_s': 1.8,
                 'margin_at_commit_m': None, 'would_reject': None}]
        counts, unrecorded, _, events_only, mismatches = audit(jobs, events_of(jobs, tail))
        self.assertEqual((sum(counts.values()), unrecorded, events_only, mismatches), (0, 2, 1, 0))

    @unittest.skipUnless(LEASE_PARAMS.is_file(), 'v3 lease-parameter file not present')
    def test_horizon_cap_premise_of_the_v3_lease(self):
        """The runtime premise of the rule (framelease_v3/runtime/v3_lease.py suffix_lease, read only): a relevant
        agent that the prefilter skips gives reason horizon_cap, n_computed 0, H = H_bar and M = +inf for every commit
        before D (logged as null by v3_scheduler.margin_check); its record passes the audit with a null margin."""
        import numpy as np
        from framelease_v3.runtime import v3_lease as VL
        env = VL.build_lease_env(str(LEASE_PARAMS))
        plan = np.stack([np.zeros(6), 2.5 * np.arange(1, 7)], -1)
        far = [[50.0, 50.0, 4.0, 1.8, 0.0, 0.0, 0.0]]
        res = VL.compute_suffix_lease(plan, far, [0.9], [0], env)
        validity = res.as_validity(10.0)
        self.assertEqual((validity['reason'], validity['n_relevant'], validity['n_computed'], validity['min_g_m'],
                          res.lease_s), ('horizon_cap', 1, 0, None, env.cfg.h_bar_s))
        for age in (0.0, 1.0, 2.0, env.cfg.h_bar_s - 1e-6):              # every commit with t_commit < D
            self.assertEqual(res.margin(age, env.cfg.t_c_s), math.inf)
        self.assertIs(CA.null_margin_explained(validity), True)
        jobs = [{'job_id': 1, 'obs_id': 0, 'end_s': 12.0,
                 'steps': [{'depth': 1, 'validity': validity,
                            'commit': {'accepted': True, 'reason': 'accepted', 'commit_s': 11.0,
                                       'margin_at_commit_m': None, 'overridden': False}}]}]
        counts, unrecorded = audit(jobs)[:2]
        self.assertEqual((sum(counts.values()), unrecorded), (0, 1))
        near = [[8.0, 8.0, 4.0, 1.8, 0.0, 0.0, 0.0]]                     # computed: a finite margin is logged
        self.assertGreater(VL.compute_suffix_lease(plan, near, [0.9], [0], env).info['n_computed'], 0)


class RunDirectory(unittest.TestCase):
    def write(self, root, kind='shield', jobs=None, events=None, delta=0.2):
        fl = Path(root) / 'raw' / 'agent' / 'framelease'
        fl.mkdir(parents=True)
        cfg = {'kind': kind, 'v4': {'v3': {'resolved': {'lease': {'delta_m': delta}}}}}
        (Path(root) / 'config.json').write_text(json.dumps(cfg))
        jobs = clean_jobs() if jobs is None else jobs
        (fl / 'jobs.jsonl').write_text(''.join(json.dumps(j) + '\n' for j in jobs))
        ev = events_of(jobs) if events is None else events
        (fl / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in ev))
        return Path(root)

    def test_audit_run_status_and_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.write(Path(tmp) / 'a')
            got = CA.audit_run(run)
            self.assertEqual((got['status'], got['offers'], got['accepted'], got['margin_unrecorded'],
                              got['delta_m']), ('PASS', 4, 3, 1, 0.2))
            strict = self.write(Path(tmp) / 'b', delta=0.5)                # margin 0.5 is not > 0.5
            got = CA.audit_run(strict)
            self.assertEqual((got['status'], got['violations']['margin'], got['n_violations']), ('FAIL', 2, 2))
            v2 = self.write(Path(tmp) / 'c', kind='v2_rule', delta=0.5)
            self.assertEqual((CA.audit_run(v2)['status'], CA.audit_run(v2)['delta_m']), ('PASS', None))

    def test_horizon_cap_null_margin_in_a_run(self):
        """A run directory whose accepted commit has a null margin: PASS with reason horizon_cap and n_computed 0, FAIL
        (one margin violation) with n_computed > 0."""
        def jobs_with(n_computed):
            jobs = clean_jobs()
            jobs[0]['steps'][1]['validity'].update(n_relevant=2, reason='horizon_cap', n_computed=n_computed)
            return jobs
        with tempfile.TemporaryDirectory() as tmp:
            got = CA.audit_run(self.write(Path(tmp) / 'cap0', jobs=jobs_with(0)))
            self.assertEqual((got['status'], got['n_violations'], got['margin_unrecorded']), ('PASS', 0, 1))
            got = CA.audit_run(self.write(Path(tmp) / 'cap2', jobs=jobs_with(2)))
            self.assertEqual((got['status'], got['violations']['margin'], got['n_violations'],
                              got['margin_unrecorded']), ('FAIL', 1, 1, 0))
            self.assertEqual((got['examples'][0]['depth'], got['examples'][0]['margin']), (2, None))

    def test_log_mismatch_is_an_error(self):
        """A commit in one log only was not re-checked against Eq. 9: never a PASS (a late commit recorded only in
        events.jsonl for a job with a jobs.jsonl row would otherwise pass unseen)."""
        jobs = [{'job_id': 1, 'obs_id': 0, 'end_s': 3.0, 'steps': []}]
        events = [{'kind': 'commit', 'job_id': 1, 'obs_id': 0, 'depth': 1, 'commit_s': 2.5, 'deadline_s': 2.4}]
        with tempfile.TemporaryDirectory() as tmp:
            got = CA.audit_run(self.write(Path(tmp) / 'm', jobs=jobs, events=events))
            self.assertEqual((got['status'], got['log_mismatches'], got['n_violations']), ('ERROR', 1, 0))
            self.assertIn('differ between jobs.jsonl and events.jsonl', got['error'])
            jobs[0]['steps'] = [step(1, 2.5, 2.4)]                       # in both logs: audited, a deadline FAIL
            got = CA.audit_run(self.write(Path(tmp) / 'f', jobs=jobs, events=events))
            self.assertEqual((got['status'], got['violations']['deadline']), ('FAIL', 1))

    def test_no_log_and_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / 'empty'
            empty.mkdir()
            (empty / 'config.json').write_text('{}')
            self.assertEqual(CA.audit_run(empty)['status'], 'NO_LOG')
            jobs = copy.deepcopy(clean_jobs())
            del jobs[0]['obs_id']
            bad = self.write(Path(tmp) / 'bad', jobs=jobs, events=[])
            got = CA.audit_run(bad)
            self.assertEqual(got['status'], 'ERROR')
            self.assertIn('KeyError', got['error'])

    def test_lease_delta_default(self):
        self.assertEqual(CA.lease_delta({}), CA.DELTA_M)
        self.assertEqual(CA.lease_delta({'v4': {'v3': {'resolved': {'lease': {'delta_m': 0.3}}}}}), 0.3)


if __name__ == '__main__':
    unittest.main()
