"""The Table II-B stress bench S1-S3 (framelease_v4/protocol/stress_bench.py; PROTOCOL Sec. 7.6). CPU only; no busy
process is ever started (subprocess.Popen is patched to fail wherever S1 code runs), no file outside a temporary
directory is written.

  cd /home/kang/Desktop/DAC && nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B -m pytest -q \
      -p no:cacheprovider framelease_v4/protocol/tests/test_stress_bench.py

What is shown:
  * S3: random sequences give 0 violations on CommitGate and on the V4Runtime commit path with every fault class
    covered, deterministically per seed. The oracle is not vacuous: gates with the deadline check removed, the margin
    ignored, cancellation ignored, the version check removed, the checks reordered or an over-strict deadline, and
    runtimes with the margin check always passing, job closing not reaching the gate, or a watchdog without expiry,
    are each caught by the matching invariant. The oracle's analytic M(Delta) equals LeaseResult.margin, the
    synthetic leases are exact (M > delta before D), and the synthetic plans fail kinematic_check for the intended
    reason.
  * Replay harness (S-1): decision rows logged by a real V3Runtime closed loop (fake backend, helpers_v3) are
    reproduced exactly (feasible set, Eq. 5 sums, the 32 features, the action); recorded states come from finished
    runs only, v2-rule rows are skipped, held-out test routes are refused unless allowed.
  * S2: 71 slack values from -0.1 to 0.6 s; nothing admitted at slack <= 0; the share admitted never decreases with
    the slack; no admitted action has a bound >= D*; the network is consulted exactly at choice epochs; the slack
    bypass fires when a shield margin is below B_pi; 16- and 10-input networks; recorded states through the CLI.
  * Supplementary S2 (Amendment A7, s2 --grid relative): with D* = t + f(state) + delta no state admits an action
    below its floor and every state admits one from the first positive offset on, at every kappa; every feasible set
    is the one the per-action floors predict; a state without a floor is counted, not swept; shields without eps or
    without R_REFINE are caught at every kappa (the registered grid checks nothing at kappa 2.0); the registered
    grid's report is byte-identical to the one before the option (pinned digest, Q-network timer frozen); the report
    is labelled supplementary, also when registered.
  * S1: --dry-run prints the plan and starts nothing; the guard refuses while a runner is alive; a tiny in-process
    run at load 0 reports every component; QUtility's disable rule is reproduced call for call; the busy-loop code
    ends by itself (run in-process with a 50 ms lifetime).
  * CLI and outputs: labelled development reports, protected output paths refused, no silent overwrite.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import math
import os
import random
import signal
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ['CUDA_VISIBLE_DEVICES'] = ''
sys.dont_write_bytecode = True

import numpy as np  # noqa: E402

from framelease_v2 import latency_agent as la  # noqa: E402
from framelease_v3.runtime import v3_commit as VC  # noqa: E402
from framelease_v3.runtime import v3_lease as VL  # noqa: E402
from framelease_v3.runtime import v3_shield as VS  # noqa: E402
from framelease_v3.runtime.tests import helpers_v3 as H3  # noqa: E402
from framelease_v4.arms import runtime_v4 as RV  # noqa: E402
from framelease_v4.protocol import registration as REG  # noqa: E402
from framelease_v4.protocol import stress_bench as SB  # noqa: E402
from framelease_v4.rl import common as C  # noqa: E402
from framelease_v4.rl import qnet as Q  # noqa: E402
from framelease_v4.rl import trainers as TR  # noqa: E402


def no_popen(*a, **kw):
    raise AssertionError('a subprocess was started')


def make_net(directory, family='fqi', seed=0, supported=(True, True), d_det=10, budget_s=1e-4):
    """A small exported network (trainers.export_qnet) of the family's input width, written to directory."""
    cand = TR.Candidate(family, d_det=d_det)
    rng = np.random.default_rng(seed)
    sizes = [len(cand.columns), 8, 2]
    mlp = {'W': [rng.normal(0.0, 0.5, (i, o)) for i, o in zip(sizes[:-1], sizes[1:])],
           'b': [rng.normal(0.0, 0.1, o) for o in sizes[1:]]}
    spec = TR.export_qnet(mlp, cand, list(supported), policy_budget_s=budget_s)
    path = Path(directory) / f'qnet_{family}_{seed}.json'
    path.write_text(json.dumps(spec), encoding='utf-8')
    return path


def closed_loop_rows(n_ticks=500):
    """Decision rows of a real V3Runtime closed loop (fake backend, scripted leases with a mix of feasible sets)."""
    leases = (0.2, 0.8, 1.4, 2.0, 2.5, 1.1)
    rt = H3.make_v3_runtime(lambda cand: leases[cand.obs_id % len(leases)],
                            backend=H3.FakeBackend(prefix_s=0.45, step_s=0.015),
                            cfg=H3.config(prior_prefix_s=0.45))
    H3.simulate(rt, n_ticks)
    return [r for r in H3.rows(rt, 'decisions') if r.get('kind') == 'decision']


def official_results(entry_status='Finished', statuses=('Completed',)):
    """raw/official_results.json of a Bench2Drive evaluator run (one record per finished route)."""
    return {'_checkpoint': {'global_record': {}, 'progress': [len(statuses), 1],
                            'records': [{'status': s, 'scores': {'score_composed': 50.0}} for s in statuses]},
            'entry_status': entry_status, 'eligible': entry_status == 'Finished'}


def write_run(root, name, route_id, rows, finished=True, kind='shield', official=None, trailing=''):
    """A launcher run directory. finished=False: no official_results.json at all; official overrides its content."""
    rd = Path(root) / name / 'runs' / 'r1'
    fl = rd / 'raw' / 'agent' / 'framelease'
    fl.mkdir(parents=True)
    cfg = {'kind': kind, 'v4_arm': name, 'kappa': 1.0, 'agent_config': {'policy_params': {'utility': 'heuristic'}}}
    if route_id is not None:
        cfg['route'] = {'route_id': str(route_id), 'scenarios': ['X']}
    (rd / 'config.json').write_text(json.dumps(cfg))
    if finished or official is not None:
        (rd / 'raw' / 'official_results.json').write_text(json.dumps(official or official_results()))
    (fl / 'ticks.jsonl').write_text('{}\n')
    (fl / 'decisions.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows) + trailing)
    return rd


def training_route():
    test = C.test_route_ids()
    return next(str(r) for r in range(1, 100000) if str(r) not in test)


def zero_timer(qnet_policy):
    """stress_bench.qnet_policy with the Q-network's timer frozen: no CPU-timing bypass, a deterministic report."""
    def policy(net, env):
        pol = qnet_policy(net, env)
        pol.utility.timer = lambda: 0.0
        return pol
    return policy


def canonical_report(report):
    """A report without its run-specific fields (provenance, network file paths, wall times), as canonical JSON."""
    r = json.loads(json.dumps(report))
    r.pop('provenance', None)
    for n in r.get('networks', {}).values():
        n.pop('path', None)
        n.pop('wall_s', None)
    return json.dumps(r, sort_keys=True, separators=(',', ':')).encode()


class NoRRefineBounds(VS.ShieldBounds):
    """Mutant budgets: REFINE without its reserve R_REFINE = L_REFRESH + L_commit."""
    R_refine = 0.0


def mutant_shield(kind):
    """v3_shield.shield with the budgets of a broken shield: 'no_eps' (eps = 0) or 'no_r_refine' (R_REFINE = 0)."""
    orig = VS.shield

    def shield(t, D_star, D_cand, depth, max_depth, newer, b):
        if kind == 'no_eps':
            b = VS.ShieldBounds(b.L_pi, b.L_refine, b.L_refresh, b.L_commit, 0.0)
        else:
            b = NoRRefineBounds(b.L_pi, b.L_refine, b.L_refresh, b.L_commit, b.eps)
        return orig(t, D_star, D_cand, depth, max_depth, newer, b)
    return shield


# ============================================================================================ S3

class S3Test(unittest.TestCase):
    def test_zero_violations_full_coverage(self):
        res = SB.run_s3(2000, seed=7)
        self.assertEqual(res['violations_total'], 0,
                         json.dumps({t: r['violations'] for t, r in res['targets'].items()}))
        self.assertTrue(res['pass'])
        self.assertTrue(res['coverage_ok'], json.dumps({t: r['coverage'] for t, r in res['targets'].items()}))
        for t in ('gate', 'runtime'):
            r = res['targets'][t]
            for k in r['coverage_keys']:
                self.assertGreater(r['coverage'][k], 0, (t, k))
            self.assertEqual(r['coverage'].get('ambiguous_margin', 0), 0)
        self.assertEqual(set(res['targets']['runtime']['violations']), set(SB.RUNTIME_INVARIANTS))
        self.assertEqual(set(res['targets']['gate']['violations']), set(SB.GATE_INVARIANTS))

    def test_deterministic_per_seed(self):
        a, b = SB.run_s3(150, seed=3), SB.run_s3(150, seed=3)
        for t in ('gate', 'runtime'):
            self.assertEqual(a['targets'][t]['coverage'], b['targets'][t]['coverage'])
            self.assertEqual(a['targets'][t]['expected_by_reason'], b['targets'][t]['expected_by_reason'])

    def _gate_violations(self, gate_cls, n=400):
        return SB.run_s3(n, seed=11, targets=('gate',), gate_factory=gate_cls)['targets']['gate']['violations']

    def test_mutated_gates_are_caught(self):
        class NoDeadline(VC.CommitGate):
            def check(self, job_id, version, deadline_s, t_commit, valid=(True, 'ok'), margin_ok=True):
                return super().check(job_id, version, math.inf, t_commit, valid, margin_ok)

        class IgnoreMargin(VC.CommitGate):
            def check(self, job_id, version, deadline_s, t_commit, valid=(True, 'ok'), margin_ok=True):
                return super().check(job_id, version, deadline_s, t_commit, valid, True)

        class IgnoreCancel(VC.CommitGate):
            def is_cancelled(self, job_id, depth):
                return False

        class NoVersion(VC.CommitGate):
            def check(self, job_id, version, deadline_s, t_commit, valid=(True, 'ok'), margin_ok=True):
                latest, self.latest = self.latest, None
                try:
                    return super().check(job_id, version, deadline_s, t_commit, valid, margin_ok)
                finally:
                    self.latest = latest

        class ExpiryFirst(VC.CommitGate):
            def check(self, job_id, version, deadline_s, t_commit, valid=(True, 'ok'), margin_ok=True):
                d = float(deadline_s)
                if math.isnan(d) or not float(t_commit) < d:
                    return False, 'expired_before_commit'
                return super().check(job_id, version, deadline_s, t_commit, valid, margin_ok)

        class TooStrict(VC.CommitGate):
            def check(self, job_id, version, deadline_s, t_commit, valid=(True, 'ok'), margin_ok=True):
                return super().check(job_id, version, float(deadline_s) - 0.2, t_commit, valid, margin_ok)

        cases = {NoDeadline: 'commit_at_or_after_deadline', IgnoreMargin: 'commit_with_margin_at_or_below_delta',
                 IgnoreCancel: 'commit_of_cancelled_candidate', NoVersion: 'commit_of_non_newer_version',
                 ExpiryFirst: 'wrong_rejection_reason', TooStrict: 'spurious_rejection'}
        for cls, inv in cases.items():
            v = self._gate_violations(cls)
            self.assertGreater(v[inv], 0, (cls.__name__, v))
        self.assertGreater(self._gate_violations(NoVersion)['committed_versions_not_increasing'], 0)
        self.assertEqual(sum(self._gate_violations(VC.CommitGate).values()), 0)

    def test_mutated_runtime_paths_are_caught(self):
        class MarginAlwaysOk(SB.ScriptedLeasePolicy):
            def margin_check(self, cand, commit_s):
                return True, None

        class CloseNotGated(RV.V4Runtime):
            def _end_job(self, job, t_end, reason):
                la.LatencyRuntime._end_job(self, job, t_end, reason)

        class NoExpiryWatchdog(RV.V4Runtime):
            def control_reference(self, now_s, obs_now):
                inc = self.incumbent_at(now_s)
                if inc is None:
                    return {'mode': 'fallback', 'reason': 'no_plan', 'incumbent': None}
                return {'mode': 'track', 'reason': None, 'incumbent': inc}

        def run(**kw):
            return SB.run_s3(300, seed=5, targets=('runtime',), **kw)['targets']['runtime']['violations']

        self.assertGreater(run(policy_cls=MarginAlwaysOk)['commit_with_margin_at_or_below_delta'], 0)
        self.assertGreater(run(runtime_cls=CloseNotGated)['commit_of_cancelled_candidate'], 0)
        self.assertGreater(run(runtime_cls=NoExpiryWatchdog)['tracked_at_or_after_deadline'], 0)
        self.assertEqual(sum(run().values()), 0)

    def test_exact_deadline_ties_catch_a_boundary_inclusive_gate(self):
        """Some offers commit exactly at t_commit = D (Eq. 9 (4) boundary); a gate or runtime that accepts t_commit = D
        is caught by commit_at_or_after_deadline, the deployed code is not."""
        env = SB.lease_env()
        rng = random.Random(3)
        ties = offers = 0
        for _ in range(2000):
            _, events = SB.generate_sequence(rng, env)
            for kind, x, t_commit, *_ in events:
                if kind == 'offer':
                    offers += 1
                    ties += int(t_commit == x.deadline_s)
        self.assertGreater(ties, 0.01 * offers)

        class BoundaryInclusive(VC.CommitGate):
            def check(self, job_id, version, deadline_s, t_commit, valid=(True, 'ok'), margin_ok=True):
                d = float(deadline_s)
                return super().check(job_id, version, math.nextafter(d, math.inf) if d == float(t_commit) else d,
                                     t_commit, valid, margin_ok)

        class BoundaryInclusiveRuntime(RV.V4Runtime):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                self.gate = BoundaryInclusive()

        res = SB.run_s3(600, seed=12, targets=('gate',), gate_factory=BoundaryInclusive)['targets']['gate']
        self.assertGreater(res['violations']['commit_at_or_after_deadline'], 0, res['violations'])
        res = SB.run_s3(600, seed=12, runtime_cls=BoundaryInclusiveRuntime, targets=('runtime',))['targets']['runtime']
        self.assertGreater(res['violations']['commit_at_or_after_deadline'], 0, res['violations'])
        res = SB.run_s3(600, seed=12)
        self.assertEqual(res['violations_total'], 0)
        for t in ('gate', 'runtime'):
            cov = res['targets'][t]['coverage']
            self.assertIn('deadline_tie', res['targets'][t]['coverage_keys'])
            self.assertGreaterEqual(cov['deadline_tie'], res['targets'][t]['coverage_min'])
            self.assertLessEqual(cov['deadline_tie'], cov['expired'])
        self.assertEqual(res['generator']['p_deadline_tie'], SB.P_DEADLINE_TIE)

    def test_margin_oracle_equals_lease_result_margin(self):
        env = SB.lease_env()
        rng = random.Random(1)
        tc, tl = env.cfg.t_c_s, float(env.tau[-1])
        n = 0
        for _ in range(3000):
            tau_star = rng.choice([math.inf, rng.uniform(0.0, 3.0)])
            agents = SB._agents(rng, tau_star, env.tau, env.cfg.delta_m)
            res = VL.LeaseResult(1.0, tau_star, 'first_failure', {}, env.tau, SB.g_matrix(agents, env.tau), None, None,
                                 env.cfg.t_pred_s)
            age = rng.uniform(-0.1, 2.8)
            a, b = SB.margin_oracle(agents, age, tc, tl), res.margin(age, tc)
            if math.isinf(a) or math.isinf(b):
                self.assertEqual(a, b, (agents, age))
            else:
                self.assertAlmostEqual(a, b, delta=1e-9, msg=(agents, age))
                n += 1
        self.assertGreater(n, 1000)

    def test_synthetic_leases_are_exact(self):
        env = SB.lease_env()
        cfg = env.cfg
        rng = random.Random(2)
        n = 0
        for _ in range(300):
            cands, _ = SB.generate_sequence(rng, env)
            for c in cands:
                h = VL.lease_closed_form(c.tau_star_s, cfg.t_c_s, cfg.h_bar_s)
                self.assertAlmostEqual(h, c.lease_true_s, delta=1e-12)
                for _ in range(3):
                    age = rng.uniform(0.0, c.lease_true_s)
                    if age < c.lease_true_s - 1e-9:
                        self.assertGreater(SB.margin_oracle(c.agents, age, cfg.t_c_s, float(env.tau[-1])),
                                           cfg.delta_m, (c, age))
                        n += 1
        self.assertGreater(n, 1000)

    def test_synthetic_plans_fail_for_the_intended_reason(self):
        for kind in ('ok',) + SB.INVALID_PLAN_KINDS:
            for speed in ((50.0, 79.0) if kind == 'speed_limit' else (0.0, 7.5, 19.9)):
                ok, why, _ = la.kinematic_check(SB.synth_plan(kind, speed))
                self.assertEqual((ok, why), (kind == 'ok', 'ok' if kind == 'ok' else kind))


# ============================================================================================ replay harness

class ReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = closed_loop_rows()
        cls.env = SB.lease_env()

    def test_closed_loop_rows_replay_exactly(self):
        rows = self.rows
        self.assertGreater(len(rows), 100)
        kinds = {len(r['feasible']) for r in rows}
        self.assertEqual(kinds, {0, 1, 2}, 'the closed loop must produce every feasible-set size')
        states = [SB.state_from_row(json.loads(json.dumps(r))) for r in rows]
        fid = SB.replay_fidelity(states, self.env)
        self.assertTrue(fid['ok'], fid)
        self.assertEqual(fid['n'], len(rows))
        self.assertEqual(fid['action_compared'], len(rows))

    def test_recorded_states_finished_runs_only_and_test_routes_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            v2_row = {'kind': 'decision', 'shield': None, 'bounds': None, 'features': {}, 'policy': 'fixed_deep'}
            write_run(tmp, 'fl_heuristic', training_route(), self.rows + [v2_row])
            write_run(tmp, 'unfinished', training_route(), self.rows, finished=False)
            states, meta = SB.recorded_states([Path(tmp)])
            self.assertEqual(len(states), len(self.rows))
            self.assertEqual([(r['shield_rows'], r['utility']) for r in meta['runs']], [(len(self.rows), 'heuristic')])
            capped, meta2 = SB.recorded_states([Path(tmp)], max_states=10)
            self.assertEqual((len(capped), meta2['n_available']), (10, len(self.rows)))
            test_route = sorted(C.test_route_ids())[0]
            write_run(tmp, 'on_test_route', test_route, self.rows)
            with self.assertRaises(PermissionError):
                SB.recorded_states([Path(tmp)])
            states, _ = SB.recorded_states([Path(tmp)], allow_test_routes=True)
            self.assertEqual(len(states), 2 * len(self.rows))

    def test_unfinished_and_failed_attempts_are_skipped_and_listed(self):
        """Only a finished run with one valid official record (Sec. 8.4) is taken; a still running or aborted attempt
        (entry_status 'Started', no record; a live log ending in a partial line), an execution failure that the retry
        rule repeats, and an unreadable log of a finished run are skipped and listed, never loaded or crashed on."""
        partial = '{"kind": "decision", "ep'
        with tempfile.TemporaryDirectory() as tmp:
            write_run(tmp, 'fl_heuristic', training_route(), self.rows)
            write_run(tmp, 'running', training_route(), self.rows, official=official_results('Started', ()),
                      trailing=partial)
            write_run(tmp, 'blocked', training_route(), self.rows,
                      official=official_results(statuses=('Failed - Agent got blocked',)))
            write_run(tmp, 'crashed', training_route(), self.rows,
                      official=official_results(statuses=('Failed - Agent crashed',)))
            write_run(tmp, 'two_records', training_route(), self.rows,
                      official=official_results(statuses=('Completed', 'Completed')))
            write_run(tmp, 'not_finished', training_route(), self.rows, official=official_results('Crashed'))
            write_run(tmp, 'torn_log', training_route(), self.rows, trailing=partial)
            states, meta = SB.recorded_states([Path(tmp)])
        self.assertEqual(len(states), 2 * len(self.rows))                # fl_heuristic and blocked (a valid record)
        self.assertEqual(sorted(r['arm'] for r in meta['runs']), ['blocked', 'fl_heuristic'])
        skipped = {r['run_dir'].split('/')[-3]: r['reason'] for r in meta['skipped_unfinished']}
        self.assertEqual(sorted(skipped), ['crashed', 'not_finished', 'running', 'two_records'])
        self.assertIn('found 0', skipped['running'])
        self.assertIn('Agent crashed', skipped['crashed'])
        self.assertIn("'Crashed'", skipped['not_finished'])
        self.assertEqual([r['run_dir'].split('/')[-3] for r in meta['skipped_unreadable']], ['torn_log'])

    def test_run_without_route_id_is_refused(self):
        """Fail closed (Sec. 9.11): a run whose route cannot be identified never passes the held-out-route guard."""
        for allow in (False, True):
            with tempfile.TemporaryDirectory() as tmp:
                write_run(tmp, 'fl_heuristic', None, self.rows)
                with self.assertRaises(PermissionError):
                    SB.recorded_states([Path(tmp)], allow_test_routes=allow)


# ============================================================================================ S2

class S2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.env = SB.lease_env()
        cls.nets = [SB.describe_qnet(make_net(cls.tmp.name, 'fqi', 1)),
                    SB.describe_qnet(make_net(cls.tmp.name, 'fqi_nolease', 2))]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self._env = mock.patch.dict(os.environ)
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def test_sweep_on_synthetic_states(self):
        states, _ = SB.synthetic_states(150, seed=4)
        res = SB.run_s2(states, self.nets, self.env)
        self.assertEqual(res['violations_total'], 0,
                         json.dumps({n: r['violations'] for n, r in res['networks'].items()}))
        self.assertTrue(res['pass'])
        grid = res['slack_grid_s']
        self.assertEqual((len(grid), grid[0], grid[-1]), (71, -0.1, 0.6))
        self.assertTrue(all(abs(b - a - 0.01) < 1e-12 for a, b in zip(grid, grid[1:])))
        self.assertEqual(self.nets[1]['n_inputs'], 10)
        for name, r in res['networks'].items():
            rows = r['per_slack']
            self.assertEqual(len(rows), 71)
            for row in rows:
                if row['slack_s'] <= 0.0:
                    self.assertEqual(row['admitted'], 0, (name, row['slack_s']))
                self.assertEqual(row['select_calls'], round(row['p_both'] * row['epochs']))
            shares = [row['share_admitted'] for row in rows]
            self.assertEqual(shares, sorted(shares), name)
            self.assertGreater(shares[-1], 0.0)
            self.assertGreater(r['select_calls'], 0)
            self.assertEqual(r['admitted_bound_ge_Dstar'], 0)
            self.assertAlmostEqual(r['bypass_rate'], r['bypass_rate_slack'] + r['bypass_rate_timing'] +
                                   r['bypass']['nonfinite'] / r['select_calls'], delta=1e-12)

    def test_slack_bypass_below_policy_budget(self):
        st = SB.synthetic_states(1, seed=9)[0][0]
        t = st['t']
        st.update(depth=3, at_max_depth=False, D_star=t + 1.0, D_cand=t + 1.0,
                  newest={'obs_id': st['obs_id'] + 5, 'capture_s': t - 0.01, 'speed_mps': 3.0},
                  active={'job_id': st['job_id'], 'obs_id': st['obs_id'], 'depth': 2, 'capture_s': st['capture_s'],
                          'lease_s': 1.5},
                  bounds={'L_pi': 0.002, 'L_refine': 0.02795, 'L_refresh': 0.45, 'L_commit': 0.005, 'eps': 0.05})
        res = SB.run_s2([st], self.nets[:1], self.env)
        rows = {round(r['slack_s'], 2): r for r in res['networks'][self.nets[0]['name']]['per_slack']}
        self.assertEqual(rows[0.53]['feasible'], {'REFRESH': 1})          # REFINE needs 0.53995 s
        self.assertEqual(rows[0.54]['feasible'], {'REFINE+REFRESH': 1})   # REFINE margin 50 us < B_pi = 100 us
        self.assertEqual((rows[0.54]['bypass']['slack'], rows[0.54]['network_calls']), (1, 0))
        self.assertEqual((rows[0.55]['bypass']['slack'], rows[0.55]['network_calls']), (0, 1))
        self.assertEqual((rows[0.54]['bypass_rate_slack'], rows[0.55]['bypass_rate_slack']), (1.0, 0.0))
        self.assertIsNone(rows[0.53]['bypass_rate'])                      # no choice epoch at 0.53 s
        self.assertEqual(res['violations_total'], 0)

    def test_slack_floors_and_admitted_actions_per_kappa(self):
        """slack_floor is exact (a state admits an action just above its floor and none just below), and the report
        gives per kappa the floors, the admitted actions checked and the grid values that admit nothing."""
        states, _ = SB.synthetic_states(150, seed=4)
        res = SB.run_s2(states, self.nets[:1], self.env)
        r = res['networks'][self.nets[0]['name']]
        floor = res['slack_floor']
        self.assertEqual(set(floor), {'1.0', '1.5', '2.0'})
        self.assertEqual(set(floor), set(r['by_kappa']))
        self.assertEqual(sum(f['n_states'] for f in floor.values()), res['n_swept'])
        for row in r['per_slack']:
            self.assertEqual(sum(row['admitted_by_kappa'].values()), row['admitted'])
            self.assertEqual(sum(row['epochs_by_kappa'].values()), row['epochs'])
        self.assertEqual(sum(b['admitted'] for b in r['by_kappa'].values()), r['admitted'])
        for k, f in floor.items():
            bk = r['by_kappa'][k]
            self.assertGreaterEqual(bk['grid_values_admitting_nothing'], f['grid_values_at_or_below_every_floor'])
            if bk['first_admitting_slack_s'] is not None:
                self.assertGreater(bk['first_admitting_slack_s'], f['floor_any_s']['min'])
        self.assertEqual(floor['2.0']['grid_values_at_or_below_every_floor'], 71)   # kappa 2: L_REFRESH > 0.6 s
        pol = SB.ReplayPolicy(self.env, 'heuristic')
        n = 0
        for st in states:
            if st['active'] is None:
                continue
            fl = SB.slack_floor(st)['any']
            if fl is None:
                self.assertFalse(SB.replay(pol, st, 3.0)[0]['admitted'])
                continue
            self.assertFalse(SB.replay(pol, st, fl - 1e-6)[0]['admitted'])
            self.assertTrue(SB.replay(pol, st, fl + 1e-6)[0]['admitted'])
            n += 1
        self.assertGreater(n, 100)

    def test_cli_on_recorded_states(self):
        rows = closed_loop_rows(300)
        with tempfile.TemporaryDirectory() as tmp:
            write_run(Path(tmp) / 'runs', 'fl_heuristic', training_route(), rows)
            out = Path(tmp) / 's2.json'
            argv = ['s2', '--qnet', self.nets[0]['abs_path'], '--states', 'recorded', '--runs-root',
                    str(Path(tmp) / 'runs'), '--out', str(out)]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(SB.main(argv), 0)
            rep = json.loads(out.read_text())
            self.assertEqual(rep['label'], 'development run, not the registered S2')
            self.assertTrue(rep['replay_fidelity']['ok'], rep['replay_fidelity'])
            self.assertEqual(rep['states']['source'], 'recorded')
            self.assertEqual(rep['n_states'], len(rows))
            self.assertTrue(rep['pass'])


# ============================================================================================ S2, supplementary grid

# Canonical report (canonical_report, Q-network timer frozen) of the registered-grid S2 written by the stress_bench.py
# before the relative grid was added (sha256 2e49890413fdf672...), for the inputs of
# S2RelativeTest.test_registered_grid_report_is_unchanged (make_net fqi seed 1 and fqi_nolease seed 2; 60 synthetic
# states, seed 5). A different value means the registered S2 report changed.
REGISTERED_S2_SHA256 = '93ba88c2d373b141a808e87239bb2bcc443c3e697289622fb541bf869693d28e'


class S2RelativeTest(unittest.TestCase):
    """Supplementary S2 (Amendment A7): the grid relative to each state's slack floor, D* = t + f(state) + delta."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.env = SB.lease_env()
        cls.nets = [SB.describe_qnet(make_net(cls.tmp.name, 'fqi', 1)),
                    SB.describe_qnet(make_net(cls.tmp.name, 'fqi_nolease', 2))]
        states, _ = SB.synthetic_states(150, seed=4)
        cls.states = states + [cls.no_floor_state()]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self._env = mock.patch.dict(os.environ)
        self._env.start()

    def tearDown(self):
        self._env.stop()

    @staticmethod
    def no_floor_state():
        """An active candidate, but no action at any slack: depth limit reached and no newer frame."""
        st = SB.synthetic_states(1, seed=9)[0][0]
        t = st['t']
        st.update(depth=SB.MAX_DEPTH, at_max_depth=True, D_star=t + 1.0, D_cand=t + 1.0,
                  newest={'obs_id': st['obs_id'], 'capture_s': st['capture_s'], 'speed_mps': 3.0},
                  active={'job_id': st['job_id'], 'obs_id': st['obs_id'], 'depth': 2, 'capture_s': st['capture_s'],
                          'lease_s': 1.5}, source='no_floor')
        return st

    def test_relative_grid_admits_as_the_floor_predicts(self):
        """D* = t + f(state) + delta: no state admits an action below its floor, every state with a floor admits one
        from the first positive offset on (at every kappa, so the bound check runs at every kappa), every feasible set
        is the one the per-action floors predict, and a state without a floor is counted, not swept."""
        res = SB.run_s2_relative(self.states, self.nets[:1], self.env)
        self.assertEqual(res['grid'], 'relative_to_floor')
        offsets = res['offsets_s']
        self.assertEqual((len(offsets), offsets[0], offsets[-1]), (71, -0.1, 0.6))
        self.assertTrue(all(abs(b - a - 0.01) < 1e-12 for a, b in zip(offsets, offsets[1:])))
        usable = [st for st in self.states if st['active'] is not None and math.isfinite(SB._deadline(st['D_star']))]
        floors = [SB.slack_floor(st)['any'] for st in usable]
        self.assertEqual([f['f_s'] for f in res['state_floors']], floors)
        self.assertEqual([f['source'] for f in res['state_floors']], [st['source'] for st in usable])
        self.assertEqual(res['state_floors'][-1], {'source': 'no_floor', 'kappa': SB._kappa_key(self.states[-1]),
                                                   'f_s': None, 'refine_s': None, 'refresh_s': None})
        self.assertEqual(res['no_floor'], sum(f is None for f in floors))
        self.assertEqual(res['n_swept'], len(usable) - res['no_floor'])
        self.assertGreater(res['n_swept'], 100)
        r = res['networks'][self.nets[0]['name']]
        self.assertEqual(res['violations_total'], 0, json.dumps(r['violations']))
        self.assertTrue(res['pass'] and res['floor_check_ok'])
        fc = r['floor_check']
        self.assertEqual((fc['mismatch'], fc['judged'] + fc['boundary']), (0, len(offsets) * res['n_swept']))
        self.assertGreaterEqual(fc['boundary'], res['n_swept'])            # delta = 0: every state's boundary
        self.assertEqual(len(r['per_offset']), 71)
        for row in r['per_offset']:
            d = row['delta_s']
            self.assertEqual(row['epochs'], res['n_swept'])
            if d < 0:
                self.assertEqual(row['admitted'], 0, d)
            elif d > 0:
                self.assertEqual(row['admitted'], row['epochs'], d)
            self.assertEqual(row['floor_mismatch'], 0)
            parts = row['by_kappa'].values()
            for key in ('epochs', 'admitted', 'select_calls', 'admitted_bound_ge_Dstar'):
                self.assertEqual(sum(p[key] for p in parts), row[key], (d, key))
            for reason, n in row['bypass'].items():
                self.assertEqual(sum(p['bypass'][reason] for p in parts), n, (d, reason))
        self.assertEqual(set(r['by_kappa']), {'1.0', '1.5', '2.0'})
        self.assertEqual(sum(b['admitted'] for b in r['by_kappa'].values()), r['admitted'])
        for k, b in r['by_kappa'].items():
            self.assertGreater(b['admitted'], 0, k)
            self.assertEqual(b['admitted_bound_ge_Dstar'], 0, k)
            self.assertIn(b['every_state_admits_from_offset_s'], (0.0, 0.01), k)
            self.assertIn(b['first_admitting_offset_s'], (0.0, 0.01), k)
            self.assertIn(b['offsets_admitting_nothing'], (10, 11), k)
            if b['select_calls']:
                self.assertAlmostEqual(b['bypass_rate'], b['bypass_rate_slack'] + b['bypass_rate_timing'] +
                                       b['bypass']['nonfinite'] / b['select_calls'], delta=1e-12)
        pol = SB.ReplayPolicy(self.env, 'heuristic')                          # the deployed decide(), not the harness
        n = 0
        for st, f in zip(usable[::5], floors[::5]):
            if f is None:
                continue
            for d in (-0.1, -0.01, 0.01, 0.6):
                self.assertEqual(SB.replay(pol, st, f + d)[0]['admitted'], d > 0, (st['source'], d))
            n += 1
        self.assertGreater(n, 20)
        self.assertFalse(SB.replay(pol, self.states[-1], 3.0)[0]['admitted'])
        reg = SB.run_s2(self.states, self.nets[:1], self.env)                 # the registered grid: nothing at 2.0
        self.assertEqual(reg['networks'][self.nets[0]['name']]['by_kappa']['2.0']['admitted'], 0)

    def test_bound_check_is_exercised_at_every_kappa(self):
        """A shield without eps or without R_REFINE admits actions whose bound >= D*: the relative grid catches both at
        every kappa, as the registered grid catches them where its values reach the floors; the registered grid
        checks no admitted action at kappa 2.0, where it lies below every floor."""
        name = self.nets[0]['name']
        for kind in ('no_eps', 'no_r_refine'):
            with mock.patch.object(VS, 'shield', mutant_shield(kind)):
                rel = SB.run_s2_relative(self.states, self.nets[:1], self.env)
                reg = SB.run_s2(self.states, self.nets[:1], self.env)
            self.assertFalse(rel['pass'], kind)
            self.assertFalse(rel['floor_check_ok'], kind)
            by_kappa = rel['networks'][name]['by_kappa']
            self.assertEqual(set(by_kappa), {'1.0', '1.5', '2.0'})
            for k, b in by_kappa.items():
                self.assertGreater(b['admitted_bound_ge_Dstar'], 0, (kind, k))
            self.assertGreater(reg['networks'][name]['admitted_bound_ge_Dstar'], 0, kind)
            if kind == 'no_eps':
                self.assertEqual(reg['networks'][name]['by_kappa']['2.0']['admitted'], 0)

    def test_registered_grid_report_is_unchanged(self):
        """The registered grid stays the default; its report (canonical_report, Q-network timer frozen) is
        byte-identical with and without --grid registered, and to the one of the stress_bench.py before the relative
        grid for the same inputs and seed (REGISTERED_S2_SHA256); it carries no supplementary field."""
        reps = []
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(SB, 'qnet_policy', zero_timer(SB.qnet_policy)), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            for extra in ([], ['--grid', 'registered']):
                out = Path(tmp) / f's2_{len(extra)}.json'
                argv = ['s2', '--qnet', self.nets[0]['abs_path'], '--qnet', self.nets[1]['abs_path'], '--states',
                        'synthetic', '--n-states', '60', '--seed', '5', '--out', str(out)] + extra
                self.assertEqual(SB.main(argv), 0)
                reps.append(json.loads(out.read_text()))
        default, explicit = (canonical_report(r) for r in reps)
        self.assertEqual(default, explicit)
        self.assertEqual(hashlib.sha256(default).hexdigest(), REGISTERED_S2_SHA256,
                         'the registered S2 report differs from the one before the relative grid')
        rep = reps[0]
        self.assertEqual(rep['label'], 'development run, not the registered S2')
        self.assertEqual(rep['notes'], SB.NOTES['S2'])
        for key in ('grid', 'supplementary', 'offsets_s', 'state_floors', 'no_floor', 'floor_check_ok'):
            self.assertNotIn(key, rep)
        self.assertEqual(len(rep['slack_grid_s']), 71)

    def test_relative_report_labels(self):
        """--grid relative writes a report labelled supplementary, also with --registered (never the registered S2
        label), with grid relative_to_floor, the offsets, f(state) per state and the supplementary notes; default
        report names s2_relative_...; an unknown grid is refused."""
        base = ['s2', '--qnet', self.nets[0]['abs_path'], '--states', 'synthetic', '--n-states', '40', '--grid']
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            dev, reg = Path(tmp) / 'dev.json', Path(tmp) / 'reg.json'
            self.assertEqual(SB.main(base + ['relative', '--out', str(dev)]), 0)
            self.assertEqual(SB.main(base + ['relative', '--registered', '--out', str(reg)]), 0)
            with self.assertRaises(SystemExit):
                SB.main(base + ['absolute', '--out', str(Path(tmp) / 'x.json')])
            d, r = json.loads(dev.read_text()), json.loads(reg.read_text())
        self.assertEqual(d['label'], 'supplementary: S2 relative to the slack floor; development run, not the '
                                     'registered S2')
        self.assertEqual(r['label'], 'supplementary: S2 relative to the slack floor (registered run, PROTOCOL Sec. '
                                     '7.6, Amendment A7; never in place of the S2 grid)')
        for rep, registered in ((d, False), (r, True)):
            self.assertEqual((rep['test'], rep['registered'], rep['supplementary']), ('S2', registered, True))
            self.assertTrue(rep['label'].startswith(SB.SUPPLEMENTARY_LABEL))
            self.assertNotEqual(rep['label'], SB.label_for('S2', True))
            self.assertEqual(rep['grid'], 'relative_to_floor')
            self.assertEqual(rep['notes'], SB.NOTES['S2'] + SB.NOTES['S2_relative'])
            self.assertTrue(rep['notes'][len(SB.NOTES['S2'])].startswith('Supplementary (Amendment A7)'))
            self.assertEqual(len(rep['offsets_s']), 71)
            self.assertNotIn('slack_grid_s', rep)
            self.assertEqual(len(rep['state_floors']), rep['n_swept'] + rep['no_floor'])
            self.assertTrue(rep['pass'] and rep['floor_check_ok'])
        self.assertEqual({k: v for k, v in d.items() if k not in ('label', 'registered', 'provenance', 'networks')},
                         {k: v for k, v in r.items() if k not in ('label', 'registered', 'provenance', 'networks')})
        out = SB._default_out('S2', False, 'relative')
        self.assertEqual(out.parent, SB.OUT_DIR / 'dev')
        self.assertTrue(out.name.startswith('s2_relative_dev_'))
        self.assertTrue(SB._default_out('S2', True, 'relative').name.startswith('s2_relative_registered_'))
        self.assertTrue(SB._default_out('S2', True).name.startswith('s2_registered_'))

    def test_relative_cli_on_recorded_states(self):
        rows = closed_loop_rows(300)
        with tempfile.TemporaryDirectory() as tmp:
            write_run(Path(tmp) / 'runs', 'fl_heuristic', training_route(), rows)
            out = Path(tmp) / 's2_relative.json'
            argv = ['s2', '--qnet', self.nets[0]['abs_path'], '--states', 'recorded', '--runs-root',
                    str(Path(tmp) / 'runs'), '--grid', 'relative', '--out', str(out)]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(SB.main(argv), 0)
            rep = json.loads(out.read_text())
        self.assertTrue(rep['replay_fidelity']['ok'], rep['replay_fidelity'])
        self.assertEqual((rep['states']['source'], rep['n_states']), ('recorded', len(rows)))
        self.assertGreater(rep['n_swept'], 0)
        self.assertTrue(all('#' in f['source'] for f in rep['state_floors']))
        self.assertTrue(rep['pass'] and rep['floor_check_ok'])


# ============================================================================================ S1

class S1Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.net_path = make_net(cls.tmp.name, 'fqi', 3)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self._env = mock.patch.dict(os.environ)
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def test_dry_run_prints_plan_and_starts_nothing(self):
        out = Path(self.tmp.name) / 's1_dry.json'
        buf = io.StringIO()
        with mock.patch.object(SB.subprocess, 'Popen', no_popen), contextlib.redirect_stdout(buf):
            rc = SB.main(['s1', '--qnet', str(self.net_path), '--dry-run', '--n-states', '40', '--scenes',
                          'synthetic', '--cpu-sample-s', '0.2', '--out', str(out)])
        self.assertEqual(rc, 0)
        plan = json.loads(buf.getvalue())
        self.assertEqual((plan['test'], plan['loads']), ('S1', [0, 4, 8, 15]))
        self.assertIn('blocking_processes', plan)
        self.assertEqual(plan['foreign_cpu']['sample_s'], 0.2)
        self.assertIsInstance(plan['foreign_cpu']['processes'], list)
        self.assertFalse(out.exists())

    def test_guard_refuses_while_a_runner_is_alive(self):
        blocker = [{'pid': 1, 'markers': ['gpu_queue'], 'cmdline': 'python framelease_v2/gpu_queue.py'}]
        out = Path(self.tmp.name) / 's1_refused.json'
        base = ['s1', '--qnet', str(self.net_path), '--n-states', '20', '--scenes', 'synthetic',
                '--cpu-sample-s', '0.05', '--out', str(out)]
        with mock.patch.object(SB, 'blocking_processes', return_value=blocker), \
                mock.patch.object(SB.subprocess, 'Popen', no_popen), contextlib.redirect_stdout(io.StringIO()):
            for extra in (['--loads', '4'], ['--loads', '0'], ['--loads', '0,4', '--allow-shared-cpu'], []):
                with self.assertRaises(SystemExit):
                    SB.main(base + extra)
            with self.assertRaises(RuntimeError):
                SB.run_s1([], [], [], None, None, loads=(0,), guard=True)
        self.assertFalse(out.exists())

    def test_blocking_processes_scan(self):
        with tempfile.TemporaryDirectory() as proc:
            for pid, cmd in ((101, b'python\0framelease_v2/gpu_queue.py\0--queue-dir\0q'),
                             (102, b'/opt/carla/CarlaUE4-Linux-Shipping\0CarlaUE4'), (103, b'bash\0-l'),
                             (os.getpid(), b'python\0p1_driver.py')):
                d = Path(proc) / str(pid)
                d.mkdir()
                (d / 'cmdline').write_bytes(cmd)
            (Path(proc) / 'self').mkdir()
            found = SB.blocking_processes(proc_root=proc)
        self.assertEqual([b['pid'] for b in found], [101, 102])
        self.assertEqual(found[0]['markers'], ['gpu_queue'])

    def test_tiny_in_process_run_at_load_zero(self):
        net = SB.describe_qnet(self.net_path)
        states, _ = SB.synthetic_states(40, seed=6)
        scenes, _ = SB.synthetic_scenes(4, seed=6)
        env = SB.lease_env()
        with mock.patch.object(SB.subprocess, 'Popen', no_popen):
            res = SB.run_s1([net], states, scenes, env, env, loads=(0,), n_calls=200, n_lease=30, settle_s=0.0,
                            guard=False, warm=10, cpu_sample_s=0.0)
        (r,) = res['per_load']
        self.assertEqual((r['load'], r['busy_pids']), (0, []))
        self.assertIsNone(r['foreign_cpu_before']['processes'])                   # not sampled
        q = r['qnet_call'][net['name']]
        self.assertEqual((q['n'], q['budget_s']), (200, 1e-4))
        self.assertTrue(0.0 <= q['overrun_rate'] <= 1.0)
        self.assertEqual(set(r['shield_decision']), {'heuristic', net['name']})
        self.assertEqual(r['shield_decision'][net['name']]['all']['n'], 200)
        self.assertIsNone(r['shield_decision']['heuristic']['bypass'])
        self.assertEqual((r['lease']['n'], r['commit_check']['n']), (30, 30))
        self.assertEqual(sum(r['commit_check']['outcomes'].values()), 30 + 200)   # warm-up included in outcomes
        for comp in (q, r['lease'], r['commit_check']):
            self.assertLessEqual(comp['p50_us'], comp['p99_us'])
            self.assertLessEqual(comp['p99_us'], comp['max_us'])

    HOG = {'sample_s': 0.1, 'min_share_of_one_core': SB.FOREIGN_CPU_MIN_SHARE, 'total_cpu_share': 0.9,
           'processes': [{'pid': 7, 'cpu_share': 0.9, 'comm': 'python', 'cmdline': 'python other_project/train.py'}]}

    def test_foreign_cpu_from_proc(self):
        """Foreign CPU consumers from /proc/<pid>/stat (fake /proc): this process, its children (the busy processes)
        and excluded pids are left out, as are processes below the share and processes that appeared in between."""
        me, hz = os.getpid(), os.sysconf('SC_CLK_TCK')
        procs = {201: ('py (x) y', 1), 202: ('idle', 1), 203: ('busy', me), 204: ('excluded', 1), me: ('bench', 1)}
        with tempfile.TemporaryDirectory() as proc:
            def write(pid, ticks):
                comm, ppid = procs.get(pid, ('new', 1))
                d = Path(proc) / str(pid)
                d.mkdir(exist_ok=True)
                (d / 'stat').write_text(f'{pid} ({comm}) R {ppid} 1 1 0 -1 0 0 0 0 0 {ticks} 3 0 0 20 0 1 0 1 1 1')
                (d / 'cmdline').write_bytes(f'/usr/bin/{comm}\0--x'.encode())

            for pid in procs:
                write(pid, 1000)
            (Path(proc) / 'self').mkdir()

            def sleep(s):
                used = {201: int(0.9 * hz * s), 202: int(0.02 * hz * s), 203: hz, 204: hz, me: hz}
                for pid, n in used.items():
                    write(pid, 1000 + n)
                write(999, 5000)

            found = SB.foreign_cpu(1.0, exclude=(204,), proc_root=proc, sleep=sleep)
        self.assertEqual(found, [{'pid': 201, 'cpu_share': 0.9, 'comm': 'py (x) y',
                                  'cmdline': '/usr/bin/py (x) y --x'}])
        self.assertIsNone(SB.foreign_cpu(0.0))

    def test_registered_run_refuses_foreign_cpu_unless_accepted(self):
        out = Path(self.tmp.name) / 's1_registered.json'
        base = ['s1', '--qnet', str(self.net_path), '--registered', '--n-states', '20', '--scenes', 'synthetic',
                '--out', str(out)]
        calls = []

        def fake_run_s1(*a, **kw):
            calls.append(kw)
            return {'per_load': [], 'n_feature_dicts': 0}

        sig = signal.getsignal(signal.SIGTERM)
        with mock.patch.object(SB, 'blocking_processes', return_value=[]), \
                mock.patch.object(SB, 'foreign_cpu_record', return_value=self.HOG), \
                mock.patch.object(SB.subprocess, 'Popen', no_popen), mock.patch.object(SB, 'run_s1', fake_run_s1), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                SB.main(base)
            self.assertIn('other_project/train.py', str(cm.exception))
            with self.assertRaises(SystemExit):
                SB.main(base + ['--cpu-sample-s', '0', '--accept-foreign-cpu'])
            self.assertEqual((calls, out.exists()), ([], False))
            self.assertEqual(SB.main(base + ['--accept-foreign-cpu']), 0)
        self.assertIs(signal.getsignal(signal.SIGTERM), sig)              # cmd_s1 restores the SIGTERM handler
        self.assertEqual(calls[0]['refuse_foreign'], False)
        rep = json.loads(out.read_text())
        self.assertEqual((rep['registered'], rep['foreign_cpu_accepted']), (True, True))
        self.assertEqual(rep['plan']['foreign_cpu'], self.HOG)

    def test_run_s1_refuses_a_level_while_foreign_cpu_is_used(self):
        states, _ = SB.synthetic_states(20, seed=6)
        env = SB.lease_env()
        with mock.patch.object(SB, 'foreign_cpu_record', return_value=self.HOG), \
                mock.patch.object(SB.subprocess, 'Popen', no_popen), mock.patch.object(SB, 's1_measure', no_popen):
            with self.assertRaises(RuntimeError):
                SB.run_s1([], states, [], env, env, loads=(0,), guard=False, refuse_foreign=True)
        with self.assertRaises(ValueError):
            SB.run_s1([], states, [], env, env, loads=(0,), guard=False, refuse_foreign=True, cpu_sample_s=0.0)

    def test_busy_code_ends_by_itself(self):
        cmd = SB.BusyLoad(4, max_s=0.05).command()
        self.assertEqual(cmd[1:5], ['-I', '-B', '-c', SB.BUSY_CODE])
        self.assertEqual(float(cmd[5]), 0.05)
        t0 = time.monotonic()
        with mock.patch.object(sys, 'argv', ['-c', cmd[5]]):      # run in this process: no subprocess is started
            exec(compile(SB.BUSY_CODE, '<busy>', 'exec'), {})
        self.assertLess(time.monotonic() - t0, 5.0)

    def test_disable_rule_matches_qutility(self):
        spec = Q.load_spec(self.net_path)
        rng = np.random.default_rng(0)
        walls = list(np.where(rng.random(600) < 0.04, 3e-4, 2e-5))
        walls[300:330] = [5e-4] * 30                                     # a burst of overruns
        ticks = []
        for w in walls:
            ticks += [0.0, float(w)]
        it = iter(ticks)
        u = Q.QUtility(spec, timer=lambda: next(it))
        feats = {'depth': 2, 'refine_margin_s': 0.5, 'refresh_margin_s': 0.6}
        disabled_at = None
        for i in range(len(walls)):
            u.select(dict(feats), ('REFINE', 'REFRESH'))
            if u.disabled and disabled_at is None:
                disabled_at = i
                break
        self.assertIsNotNone(disabled_at)
        self.assertEqual(SB.disable_index(walls, 1e-4), disabled_at)
        self.assertIsNone(SB.disable_index([2e-5] * 1000, 1e-4))


# ============================================================================================ CLI and outputs

class CliTest(unittest.TestCase):
    def test_s3_cli_report_label_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'deep' / 's3.json'
            argv = ['s3', '--n-sequences', '60', '--seed', '1', '--out', str(out)]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(SB.main(argv), 0)
                rep = json.loads(out.read_text())
                self.assertEqual((rep['test'], rep['registered']), ('S3', False))
                self.assertEqual(rep['label'], 'development run, not the registered S3')
                self.assertEqual(rep['n_sequences'], 60)
                self.assertEqual(set(rep['invariants']), set(SB.RUNTIME_INVARIANTS))
                self.assertIn('framelease_v3/runtime/v3_commit.py', rep['provenance']['code_sha256'])
                self.assertEqual(rep['provenance']['code_sha256']['framelease_v4/protocol/stress_bench.py'],
                                 C.sha256_file(ROOT / 'framelease_v4/protocol/stress_bench.py'))
                self.assertIn('finished_utc', rep['provenance'])
                self.assertEqual(rep['notes'], SB.NOTES['S3'])
                with self.assertRaises(FileExistsError):
                    SB.main(argv)
                self.assertEqual(SB.main(argv + ['--force']), 0)
                with self.assertRaises(SystemExit):
                    SB.main(['s3', '--n-sequences', '60', '--registered', '--out', str(Path(tmp) / 'r.json')])
                with self.assertRaises(SystemExit):
                    SB.main(['s3', '--targets', 'gate,commit', '--out', str(Path(tmp) / 'x.json')])

    def test_protected_output_paths_are_refused(self):
        for rel_path in ('outputs/framelease_v4/tuning/s3.json', 'outputs/framelease_v4/queue_p1/s3.json',
                         'outputs/framelease_v4/registration/s3.json', 'framelease_v4/protocol/s3.json',
                         'framelease_v3/s3.json', 'outputs/framelease_v4/p1_driver/s3.json',
                         'outputs/framelease_v4/rl_dev/s3.json', 'outputs/framelease_v4/amendment_a2/s3.json',
                         'outputs/framelease_v4/smoke_p1_0/s3.json', 'outputs/framelease_v4/protocol/s3.json',
                         'outputs/framelease_v4/p2_jobs/s3.json', 'outputs/framelease_v4/pipeline_state.json',
                         'outputs/framelease_v4/stress_x/s3.json', 'outputs/framelease_v4/stress', 'outputs/s3.json',
                         's3.json'):
            for force in (False, True):
                with self.assertRaises(PermissionError, msg=rel_path):
                    SB.check_out_path(ROOT / rel_path, force=force)
        for rel_path in ('outputs/framelease_v4/stress/dev/never_written.json',
                         'outputs/framelease_v4/build/STRESS/never_written.json'):
            self.assertEqual(SB.check_out_path(ROOT / rel_path), (ROOT / rel_path).resolve())

    def test_registered_files_are_never_written(self):
        """Every file of the registration manifest is refused, also with --force and wherever it lies (inside the
        project, or outside it: the user's documents of Sec. 12.1)."""
        files = REG.read_manifest()
        self.assertGreater(len(files), 100)
        self.assertTrue(any(Path(f).is_absolute() for f in files))
        for f in files:
            with self.assertRaises(PermissionError, msg=f):
                SB.check_out_path(Path(f) if Path(f).is_absolute() else ROOT / f, force=True)
        with tempfile.TemporaryDirectory() as tmp:                      # a manifest naming a file outside ROOT
            outside = Path(tmp) / 'registered.json'
            man = Path(tmp) / 'MANIFEST.sha256'
            man.write_text(f'{"0" * 64}  {outside}\n')
            with self.assertRaises(PermissionError):
                SB.check_out_path(outside, force=True, manifest=man)
            self.assertEqual(SB.check_out_path(Path(tmp) / 'free.json', manifest=man).name, 'free.json')

    def test_force_overwrites_only_a_stress_bench_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, other, broken = Path(tmp) / 'r.json', Path(tmp) / 'o.json', Path(tmp) / 'b.json'
            report.write_text(json.dumps({'schema': SB.SCHEMA, 'test': 'S3'}))
            other.write_text(json.dumps({'schema': 'framelease_v4.other/1'}))
            broken.write_text('{"schema": ')
            for p in (report, other, broken, Path(tmp)):
                with self.assertRaises(FileExistsError):
                    SB.check_out_path(p)
            self.assertEqual(SB.check_out_path(report, force=True), report.resolve())
            for p in (other, broken, Path(tmp)):
                with self.assertRaises(PermissionError, msg=str(p)):
                    SB.check_out_path(p, force=True)
            self.assertEqual(json.loads(other.read_text()), {'schema': 'framelease_v4.other/1'})


if __name__ == '__main__':
    unittest.main()
