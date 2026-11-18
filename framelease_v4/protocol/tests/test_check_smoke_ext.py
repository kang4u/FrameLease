"""The checker of runs of the new configurations (framelease_v4/protocol/check_smoke_ext.py; GAP_AUDIT A-2; PROTOCOL
Secs. 4.1, 4.7, 5.7, 6.4, 8.1). CPU only; every run directory is synthetic and lives in a temporary directory: the
layout comes from the check_smoke test builder (test_check_smoke.make_run: official record, pins, fast prefix, actor log
written by the real ActorBoxLogger, ...), and the Q-network decision rows are produced by the pinned code itself
(v3_shield.shield, v3_shield.decide and qnet.QUtility with a scripted timer), then written as the v3 runtime logs them.

  cd /home/kang/Desktop/DAC && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 nice -n 19 \
      .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/protocol/tests/test_check_smoke_ext.py

What is shown:
  * Q-network runs of the three dev networks (protocol arms fl_full, fl_bandit, fl_fqi_nolease through launcher arm
    fl_full) and of a deviating network PASS every criterion, and the report carries the Sec. 6.4 numbers;
  * the check_smoke criteria are applied unchanged: on the seven P1-0 smoke runs check_run_ext returns exactly
    check_smoke.check_run's results (plus qnet N/A); on Q-network runs every criterion but the replaced 'utility'
    equals check_smoke's, including its FAILs (timed-out launcher, pin mismatch, decision gap, slow ticks);
  * check_smoke.c_utility cannot judge a Q-network run (it raises), which is why 'utility' is replaced there;
  * each new check FAILS on its own defect: the agent's utility or a reason names another utility; an action against
    the network rule, a tampered Q value, a missing key, a wrong bypass (slack / overrun / disabled), a value logged for
    an unsupported head, v4_mu != 1, network keys on a forced epoch, a non-admitted choice; a changed or unpinned
    network file, a relative network path, another utility in the configuration; d* or protocol-arm expectations
    (family, inputs, margin, hidden layers) not met;
  * a run without choice epochs, or whose choice epochs all bypassed the network, is DEFERRED (verdict PASS); the
    overrun-disable rule is replayed exactly on rows of a network that disables itself;
  * job lines: qnet_line_problems rejects a relative FRAMELEASE_V4_QNET path, an unpinned or mismatched network, a
    wrong launcher arm; load_jobs refuses test routes, other kappa / seed, undeclared extension arms;
  * the hook: fl_global_shield (an arm arms_v4 does not list) is refused until declared, then judged by every
    criterion, its utility as fl_heuristic's, plus its own criterion (N/A on other arms); the command line loads it
    with --extension MODULE:FUNCTION and writes the report only to an explicit --report path;
  * the fixes of the review (ReviewFixesTest; outputs/framelease_v4/build/QNET/review/REVIEW.md):
    MF-1 a Q-network line labelled with any protocol arm but fl_full / fl_bandit / fl_fqi_nolease (fl_global_shield
    included) is refused, and a Q-network utility FAILS 'utility' on a launcher arm whose arms_v4 base does not take
    'qnet'; MF-2 a run whose every network call overran or was non-finite (no network decision) is DEFERRED; SF-1 an
    extension criterion that returns anything but a check_smoke._res result FAILS its criterion, and an unexpected
    exception exits 2, not 1; SF-2 --write refuses jobs.d, outputs/framelease_v4/{queue_*, registration, p1_driver,
    p1_jobs, tuning}, the code trees, MANIFEST entries and existing non-report files (also with --force); SF-3 the raw
    +-inf of an overrunning call of a non-finite network is accepted, a non-finite value where the network is finite is
    not; SF-4 the exact disable rule of qnet.QUtility (no disable before call 64, 5 % of min(n, 256), 12 / 13 of 256)
    is replayed on QUtility's own rows.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
for p in (ROOT, HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ['CUDA_VISIBLE_DEVICES'] = ''
sys.dont_write_bytecode = True

import test_check_smoke as TCS  # noqa: E402  (the check_smoke test builder, reused unchanged)
from test_fl_full_qnet_agent import synthetic_spec  # noqa: E402

from framelease_v2 import latency_agent as la  # noqa: E402
from framelease_v3.runtime import v3_shield as VS  # noqa: E402
from framelease_v3.runtime.v3_scheduler import FEATURE_NAMES  # noqa: E402
from framelease_v4.protocol import check_smoke as CS  # noqa: E402
from framelease_v4.protocol import check_smoke_ext as X  # noqa: E402
from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402
from framelease_v4.protocol import select_stage as SS  # noqa: E402
from framelease_v4.rl import qnet as Q  # noqa: E402

DEV_DIR = ROOT / 'outputs/framelease_v4/rl_dev/smoke_20261110'
DEV = {'fl_full': DEV_DIR / 'qnet_fqi.json', 'fl_bandit': DEV_DIR / 'qnet_bandit.json',
       'fl_fqi_nolease': DEV_DIR / 'qnet_fqi_nolease.json'}
BOUNDS = VS.ShieldBounds(L_pi=0.001, L_refine=0.02, L_refresh=0.47, L_commit=0.001, eps=0.05)


# ============================================================================================ synthetic rows

class CallTimer:
    """qnet.QUtility's timer: a network call reads it twice; call i takes wall_fn(i) seconds."""

    def __init__(self, wall_fn):
        self.wall_fn, self.calls, self.t, self.open = wall_fn, 0, 0.0, False

    def __call__(self):
        if self.open:
            self.t += float(self.wall_fn(self.calls))
            self.calls += 1
        self.open = not self.open
        return self.t


def default_pattern(e):
    return 'refresh' if e % 7 == 0 else 'none' if e % 11 == 0 else 'slack' if e % 13 == 0 else 'both'


def qnet_rows(spec, n=60, pattern=default_pattern, wall_fn=lambda i: 2e-5):
    """Decision rows (v3 format, JSON round trip like the runtime's logger) made by the pinned code: the shield (Eq. 5)
    at a deadline chosen per epoch kind ('both', 'slack' = both feasible with the REFINE margin below B_pi,
    'refresh' = only REFRESH, 'none'), the 32 v3 features, v3_shield.decide (Eq. 8) and qnet.QUtility."""
    u = Q.QUtility(spec, timer=CallTimer(wall_fn))
    rows = []
    for e in range(1, n + 1):
        kind = pattern(e)
        t = 0.5 * e
        depth = 1 + (e - 1) % 9
        refine_lhs = t + BOUNDS.L_pi + BOUNDS.L_refine + BOUNDS.L_commit + BOUNDS.R_refine + BOUNDS.eps
        refresh_lhs = t + BOUNDS.L_pi + BOUNDS.L_refresh + BOUNDS.L_commit + BOUNDS.R_refresh + BOUNDS.eps
        d_star = {'both': t + 1.0 + 0.1 * (e % 5), 'slack': refine_lhs + 5e-5,
                  'refresh': 0.5 * (refine_lhs + refresh_lhs), 'none': refresh_lhs - 0.01}[kind]
        sr = VS.shield(t, d_star, t + 2.5, depth, 10, True, BOUNDS)
        feats = {k: 0.0 for k in FEATURE_NAMES}
        feats.update(depth=depth, obs_age_s=0.3 + 0.08 * (e % 7), lease_slack_s=d_star - t, cand_slack_s=2.5,
                     refine_margin_s=d_star - sr.refine_lhs, refresh_margin_s=d_star - sr.refresh_lhs,
                     L_refine_s=BOUNDS.L_refine, L_refresh_s=BOUNDS.L_refresh, kappa=1.0, newer_frames=1 + e % 3,
                     n_relevant=e % 4, min_g_m=1.0 + 0.1 * (e % 9), tau_star_s=None if e % 3 else 1.5,
                     ego_speed_mps=5.0)
        action, reason = VS.decide(sr, u, feats)
        rows.append(la.jsonable({
            'kind': 'decision', 'epoch': e, 'sim_s': t, 'job_id': e, 'obs_id': e, 'capture_s': t - 0.4,
            'depth': depth, 'at_max_depth': False, 'active': None, 'feasible': list(sr.feasible), 'p_both': sr.both,
            'action': action, 'reason': reason, 'admitted': action in sr.feasible, 'shield': sr.as_dict(),
            'bounds': BOUNDS.as_dict(), 'features': feats, 'decision_wall_s': 1e-4}))
    return json.loads(json.dumps(rows)), u


# ============================================================================================ synthetic jobs and runs

def qnet_job(base, net_path, protocol_arm=None, d_star=None, out_dir=None, candidate=None):
    """A Q-network job line built like the P1 lines (p1_jobs.command) from the smoke block's fl_heuristic line:
    launcher arm fl_full, the network named in --policy-params, --utility-env FRAMELEASE_V4_QNET=<absolute path>,
    the network pinned by its repository-relative path."""
    spec = Q.load_spec(net_path)
    sha, rel = PJ.sha256_file(net_path), PJ.rel(net_path)
    label = candidate or protocol_arm or 'synthetic'
    out = out_dir or f'outputs/framelease_v4/infra_smoke_test/{label}'
    j = copy.deepcopy(base)
    c = {'arm': 'fl_full', 'envelope': j['envelope'], 'policy_params': {'utility': spec['name']}}
    j.update(id=f'v4ext_{label}_E5_k1.0_s11_r{j["route_id"]}', arm_name='fl_full', candidate=label,
             policy_params={'utility': spec['name']}, output_dir=str(out), config=f'E5_{spec["name"]}',
             cmd=PJ.command(c, j['route_id'], j['port'], str(out)) + ['--utility-env',
                                                                        f'{Q.ENV_QNET}={Path(net_path).resolve()}'],
             network={'path': rel, 'sha256': sha, 'name': spec['name'], 'family': X.network_family(spec),
                      'n_inputs': len(spec['feature_columns'])})
    j['require_sha256'] = {**j['require_sha256'], rel: sha}
    if protocol_arm:
        j['protocol_arm'] = protocol_arm
    if d_star is not None:
        j['d_star'] = int(d_star)
    return j


def edit_json(path, fn):
    d = json.loads(Path(path).read_text())
    fn(d)
    Path(path).write_text(json.dumps(d))


def fl(run):
    return Path(run) / 'raw' / 'agent' / 'framelease'


def write_rows(run, rows):
    (fl(run) / 'decisions.jsonl').write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows))
    edit_json(fl(run) / 'summary.json', lambda d: d['v4'].update(decisions=len(rows)))


def read_rows(run):
    return [json.loads(x) for x in (fl(run) / 'decisions.jsonl').read_text().splitlines()]


def make_qnet_run(root, job, rows=None, name='20261111T050505_qqqqqqqq', **kw):
    """A complete Q-network run: test_check_smoke.make_run's layout (built for a heuristic utility, which its builder
    can parse), then what a fl_full run adds: the utility block with the absolute FRAMELEASE_V4_QNET and the file's
    sha256, the frozen network copy raw/source_v4/<rel>, the network in the manifest's code identity, the agent's
    policy utility and the Q-network decision rows."""
    spec = Q.load_spec(job_net_path(job))
    run = TCS.make_run(root, {**job, 'policy_params': {'utility': 'heuristic'}}, name=name, **kw)
    path = job_net_path(job)
    sha, rel = PJ.sha256_file(path), PJ.rel(path)

    def cfg_edit(d):
        d['v4']['agent']['policy_params'] = dict(job['policy_params'])
        d['v4']['utility'] = {'name': spec['name'], 'registrar': 'framelease_v4.rl.behaviour:register_utility_name',
                              'env': {Q.ENV_QNET: str(path)}, 'env_files_sha256': {str(path): sha}}
    edit_json(run / 'config.json', cfg_edit)
    if not Path(rel).is_absolute():
        frozen = run / 'raw' / 'source_v4' / rel
        frozen.parent.mkdir(parents=True, exist_ok=True)
        frozen.write_bytes(Path(path).read_bytes())
        edit_json(run / 'raw' / 'source_v4' / 'hashes.json', lambda d: d.update({rel: sha}))
    edit_json(run / 'manifest.json', lambda d: d['identity']['code'].update({str(path): sha}))
    if (fl(run) / 'summary.json').is_file():
        edit_json(fl(run) / 'summary.json', lambda d: d['policy'].update(utility=spec['name']))
        write_rows(run, rows if rows is not None else qnet_rows(spec)[0])
    return run


def job_net_path(job):
    return Path(X.utility_env_args(job['cmd'])[Q.ENV_QNET])


class Setup:
    """The smoke block's lines (templates and the unchanged-criteria comparison), four Q-network lines (the three dev
    networks as their protocol arms, one deviating synthetic network) and their job file, in a temporary root."""

    def __init__(self, tmp):
        self.tmp = Path(tmp)
        self.smoke = TCS.Smoke(tmp)
        self.root = self.smoke.root
        base = self.smoke.by_arm['fl_heuristic']
        self.synth_path = self.tmp / 'synthetic_fqi_d4.json'
        self.synth_path.write_text(json.dumps(synthetic_spec('fqi')))
        self.jobs = [qnet_job(base, DEV[a], a, d_star=10) for a in ('fl_full', 'fl_bandit', 'fl_fqi_nolease')]
        self.jobs.append(qnet_job(base, self.synth_path, candidate='synthetic', d_star=4))
        self.by = {j['candidate']: j for j in self.jobs}
        self.job_file = self.tmp / 'jobs_ext.jsonl'
        self.write_jobs(self.jobs)

    def write_jobs(self, jobs, path=None):
        path = path or self.job_file
        Path(path).write_text(''.join(json.dumps(j, sort_keys=True) + '\n' for j in jobs))
        return path

    def all_runs(self, **kw):
        return {j['candidate']: make_qnet_run(self.root, j, **kw) for j in self.jobs}

    def check(self, jobs=None, queue=None):
        return X.check(jobs or X.load_jobs(self.job_file), self.root, queue, self.job_file, self.tmp / 'no_manifest')


def crit(rep, cand, name):
    return next(r for r in rep['jobs'] if r['candidate'] == cand)['criteria'][name]


def outcome_of(job, root):
    c = {'name': job['candidate'], 'arm': job['arm_name'], 'policy_params': job['policy_params'],
         'envelope': job.get('envelope')}
    return SS.job_outcome(job, job['route_id'], c, root, None)


# ============================================================================================ tests

class QNetRunsTest(unittest.TestCase):
    def test_complete_qnet_runs_pass_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Setup(tmp)
            S.all_runs()
            rep = S.check()
            self.assertEqual(rep['verdict'], 'PASS', json.dumps([r for r in rep['jobs'] if r['status'] != 'PASS'],
                                                                indent=1)[:4000])
            self.assertEqual(rep['criteria'], list(CS.CRITERIA) + ['qnet'])
            self.assertEqual(rep['deferred'], [])
            for r in rep['jobs']:
                self.assertEqual(set(r['criteria']), set(rep['criteria']))
                self.assertTrue(all(c['status'] == 'PASS' for c in r['criteria'].values()), r['job'])
            for parm, fam, n in (('fl_full', 'fqi', 16), ('fl_bandit', 'bandit', 16),
                                 ('fl_fqi_nolease', 'fqi_nolease', 10)):
                v = crit(rep, parm, 'qnet')['values']
                self.assertEqual((v['family'], v['n_inputs'], v['a_det_depth'], v['protocol_arm']), (fam, n, 10, parm))
                self.assertEqual(v['deviations'], 0)                          # REFRESH head unsupported
                self.assertGreater(v['network_calls'], 0)
                self.assertEqual(v['bypass']['slack'], 4)                     # epochs 13, 26, 39, 52
                self.assertEqual(v['network'], PJ.rel(DEV[parm]))
            v = crit(rep, 'synthetic', 'qnet')['values']
            self.assertEqual((v['n_inputs'], v['a_det_depth']), (16, 4))
            self.assertGreater(v['deviations'], 0)
            self.assertAlmostEqual(v['deviation_rate'], v['deviations'] / v['choice_epochs'])
            self.assertLessEqual(v['max_abs_q_error'], 1e-9)
            self.assertEqual(crit(rep, 'synthetic', 'utility')['values']['utility'], S.by['synthetic']['policy_params']
                             ['utility'])
            self.assertFalse(rep['script_registered'])
            lines = X.summary_lines(rep)
            self.assertTrue(lines[0].startswith('check of the new configurations: PASS'))
            self.assertTrue(any('qnet v4_qnet_' in x for x in lines))

    def test_check_smoke_utility_cannot_judge_a_qnet_run(self):
        """Why 'utility' is replaced: check_smoke.c_utility parses the Q-network name as an a_det name and raises;
        inside check_smoke.check_run that becomes a FAIL of a correct run."""
        with tempfile.TemporaryDirectory() as tmp:
            S = Setup(tmp)
            j = S.by['fl_full']
            run = make_qnet_run(S.root, j)
            summary = json.loads((fl(run) / 'summary.json').read_text())
            with self.assertRaises((IndexError, ValueError)):
                CS.c_utility(j, run, summary, read_rows(run))
            base = CS.check_run(j, outcome_of(j, S.root), run)
            self.assertEqual(base['utility']['status'], CS.FAIL)
            self.assertIn('check raised', base['utility']['detail'])
            ext = X.check_run_ext(j, outcome_of(j, S.root), run)
            self.assertEqual(ext['utility']['status'], CS.PASS)


class UnchangedCriteriaTest(unittest.TestCase):
    def test_smoke_runs_get_check_smokes_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = TCS.Smoke(tmp)
            runs = S.all_runs()
            for j in S.jobs:
                out = outcome_of(j, S.root)
                base = CS.check_run(j, out, runs[j['arm_name']])
                ext = X.check_run_ext(j, out, runs[j['arm_name']])
                self.assertEqual(ext.pop('qnet')['status'], CS.NA, j['arm_name'])
                self.assertEqual(ext, base, j['arm_name'])                   # every criterion, values included
            rep = X.check(S.jobs, S.root, None, S.job_file, Path(tmp) / 'no_manifest')
            self.assertEqual(rep['verdict'], 'PASS')

    def test_existing_criteria_fail_on_qnet_runs_as_in_check_smoke(self):
        def slow(run):
            p = fl(run) / 'ticks.jsonl'
            rows = [json.loads(x) for x in p.read_text().splitlines()]
            p.write_text(''.join(json.dumps({**r, 'wall_s': 0.3}) + '\n' for r in rows))

        def gap(run):
            rows = read_rows(run)
            del rows[3]
            (fl(run) / 'decisions.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))

        def bad_pin(run):
            edit_json(run / 'raw/source_v4/hashes.json', lambda d: d.update({'framelease_v4/rl/qnet.py': 'f' * 64}))
        mutations = (('route_record', lambda run: edit_json(run / 'metrics/result.json',
                                                            lambda d: d.update(timed_out=True))),
                     ('config', bad_pin), ('decisions', gap), ('tick_wall', slow),
                     ('summary_v4', lambda run: edit_json(fl(run) / 'summary.json', lambda d: d.pop('v4'))))
        for criterion, mutate in mutations:
            with tempfile.TemporaryDirectory() as tmp:
                S = Setup(tmp)
                j = S.by['fl_bandit']
                run = make_qnet_run(S.root, j)
                mutate(run)
                out = outcome_of(j, S.root)
                base, ext = CS.check_run(j, out, run), X.check_run_ext(j, out, run)
                self.assertEqual(ext[criterion]['status'], CS.FAIL, criterion)
                for k in CS.CRITERIA:
                    if k != 'utility':
                        self.assertEqual(ext[k], base[k], (criterion, k))       # check_smoke's own result
                rep = S.check()                                            # the other jobs: INCOMPLETE
                self.assertEqual(rep['verdict'], 'FAIL', criterion)


class QNetCriterionTest(unittest.TestCase):
    def broken(self, cand, mutate, criterion='qnet', expect=CS.FAIL, needle=None, job_edit=None):
        """A complete set of runs with one defect in the run of `cand`; returns the criterion's result."""
        with tempfile.TemporaryDirectory() as tmp:
            S = Setup(tmp)
            runs = S.all_runs()
            mutate(runs[cand], S.by[cand])
            if job_edit is not None:
                job = job_edit(copy.deepcopy(S.by[cand]))
                res = X.check_run_ext(job, outcome_of(job, S.root), runs[cand])[criterion]
            else:
                rep = S.check()
                res = crit(rep, cand, criterion)
                self.assertEqual(rep['verdict'], 'FAIL' if expect == CS.FAIL else 'PASS', (criterion, res))
            self.assertEqual(res['status'], expect, res)
            if needle:
                self.assertIn(needle, res['detail'])
            return res

    @staticmethod
    def rows_edit(fn):
        def mutate(run, job):
            rows = read_rows(run)
            fn(rows)
            write_rows(run, rows)
        return mutate

    @staticmethod
    def first(rows, pred):
        return next(r for r in rows if pred(r))

    def test_utility_defects(self):
        self.broken('fl_full', lambda run, j: edit_json(fl(run) / 'summary.json',
                                                         lambda d: d['policy'].update(utility='heuristic')),
                    'utility', needle='reports utility')

        def reason(rows):
            self.first(rows, lambda r: r.get('p_both'))['reason'] = 'both_feasible:heuristic'
        self.broken('fl_bandit', self.rows_edit(reason), 'utility', needle='reason')

    def test_action_and_value_defects(self):
        called = (lambda r: r.get('p_both') and r['features'].get('v4_bypass') is None)

        def flip(rows):
            r = self.first(rows, called)
            r['action'] = 'REFRESH' if r['action'] == 'REFINE' else 'REFINE'
        self.broken('fl_full', self.rows_edit(flip), needle='action')
        self.broken('synthetic', self.rows_edit(flip), needle='action')     # a deviation (or its absence) changed

        def tamper(rows):
            self.first(rows, called)['features']['v4_q_refine'] += 0.5
        self.broken('fl_fqi_nolease', self.rows_edit(tamper), needle="the network's")

        def unsupported_value(rows):
            self.first(rows, called)['features']['v4_q_refresh'] = 0.0
        self.broken('fl_full', self.rows_edit(unsupported_value), needle='support False')

        def missing_key(rows):
            self.first(rows, called)['features'].pop('v4_qnet_s')
        self.broken('fl_bandit', self.rows_edit(missing_key), needle='without')

        def mu(rows):
            self.first(rows, called)['features']['v4_mu'] = 0.5
        self.broken('synthetic', self.rows_edit(mu), needle='v4_mu')

        def leak(rows):
            self.first(rows, lambda r: not r.get('p_both'))['features']['v4_bypass'] = None
        self.broken('fl_full', self.rows_edit(leak), needle='outside a choice epoch')

        def not_admitted(rows):
            self.first(rows, called)['admitted'] = False
        self.broken('fl_full', self.rows_edit(not_admitted), needle='not admitted')

    def test_bypass_defects(self):
        called = (lambda r: r.get('p_both') and r['features'].get('v4_bypass') is None)

        def fake_slack(rows):
            r = self.first(rows, called)
            r['features'].update(v4_bypass='slack', v4_q_refine=None, v4_q_refresh=None, v4_qnet_s=None)
        self.broken('fl_full', self.rows_edit(fake_slack), needle='both shield margins')

        def ignored_slack(rows):
            r = self.first(rows, lambda r: r.get('p_both') and r['features'].get('v4_bypass') == 'slack')
            r['features'].update(v4_bypass=None, v4_q_refine=1.0, v4_qnet_s=1e-5)
        self.broken('fl_full', self.rows_edit(ignored_slack), needle='< B_pi')

        def late_kept(rows):
            self.first(rows, called)['features']['v4_qnet_s'] = 5e-4             # > B_pi but no overrun bypass
        self.broken('synthetic', self.rows_edit(late_kept), needle='late result')

        def disabled(rows):
            r = self.first(rows, called)
            r['features'].update(v4_bypass='disabled', v4_q_refine=None, v4_q_refresh=None, v4_qnet_s=None)
        self.broken('fl_full', self.rows_edit(disabled), needle='disabled')

    def test_network_identity_defects(self):
        def changed_file(run, job):
            p = run / 'raw' / 'source_v4' / PJ.rel(DEV['fl_bandit'])
            p.write_text(p.read_text().replace('"provenance"', '"provenance_x"', 1))
        self.broken('fl_bandit', changed_file, needle='sha256')

        def relative(run, job):
            def edit(d):
                path = d['v4']['utility']['env'][Q.ENV_QNET]
                rel = PJ.rel(path)
                d['v4']['utility']['env'][Q.ENV_QNET] = rel
                d['v4']['utility']['env_files_sha256'] = {rel: d['v4']['utility']['env_files_sha256'][path]}
            edit_json(run / 'config.json', edit)
        self.broken('fl_full', relative, needle='relative')

        def other_name(run, job):
            edit_json(run / 'config.json', lambda d: d['v4']['utility'].update(name='v4_qnet_000000000000'))
        self.broken('fl_full', other_name, needle='utility block names')
        nothing = (lambda run, job: None)
        self.broken('fl_full', nothing, job_edit=lambda j: {**j, 'require_sha256': {
            k: v for k, v in j['require_sha256'].items() if not k.startswith('outputs/')}}, needle='does not pin')
        self.broken('fl_full', nothing, job_edit=lambda j: {**j, 'd_star': 4}, needle='d*')
        self.broken('fl_full', nothing, job_edit=lambda j: {**j, 'protocol_arm': 'fl_fqi_nolease'},
                    needle='needs a fqi_nolease network')
        self.broken('synthetic', nothing, job_edit=lambda j: {**j, 'protocol_arm': 'fl_full'},
                    needle='hidden layers')

    def test_deferred_without_exercised_network(self):
        for pattern, needle in ((lambda e: 'refresh' if e % 2 else 'none', 'no choice epoch'),
                                (lambda e: 'slack' if e % 2 else 'refresh', 'all bypassed')):
            with tempfile.TemporaryDirectory() as tmp:
                S = Setup(tmp)
                spec = Q.load_spec(DEV['fl_bandit'])
                for j in S.jobs:
                    rows = qnet_rows(spec, pattern=pattern)[0] if j['candidate'] == 'fl_bandit' else None
                    make_qnet_run(S.root, j, rows=rows)
                rep = S.check()
                c = crit(rep, 'fl_bandit', 'qnet')
                self.assertEqual(c['status'], CS.DEFERRED, c)
                self.assertIn(needle, c['detail'])
                self.assertEqual(rep['verdict'], 'PASS')
                self.assertEqual(len(rep['deferred']), 1)

    def test_overrun_disable_rule_is_replayed(self):
        """A network whose calls overrun B_pi every 8th call (12.5 % > 5 %) disables itself at call 64 (the first
        overrun at or after MIN_CALLS_TO_DISABLE); the real QUtility rows pass, a row that keeps using the network
        after that fails, and so does an overrun that is not discarded."""
        spec = synthetic_spec('fqi')
        rows, u = qnet_rows(spec, n=150, pattern=lambda e: 'both', wall_fn=lambda i: 5e-4 if i % 8 == 7 else 1e-5)
        self.assertTrue(u.disabled)
        problems, v = X.qnet_rows_check(rows, spec, spec['name'])
        self.assertEqual(problems, [])
        self.assertEqual(v['network_calls'], u.n_calls)
        self.assertEqual(v['bypass'], u.bypass)
        self.assertEqual(v['disabled_at_epoch'], 64)
        self.assertEqual(v['bypass']['overrun'], 8)
        after = [r for r in rows if r['epoch'] > 64]
        self.assertTrue(after and all(r['features']['v4_bypass'] == 'disabled' for r in after))
        bad = copy.deepcopy(rows)
        bad[100]['features'].update(v4_bypass=None, v4_q_refine=0.0, v4_q_refresh=0.0, v4_qnet_s=1e-5)
        self.assertTrue(any('after the network was disabled' in p for p in X.qnet_rows_check(bad, spec)[0]))
        bad = copy.deepcopy(rows)
        r = next(r for r in bad if r['features']['v4_bypass'] == 'overrun')
        r['action'] = 'REFRESH' if r['action'] == 'REFINE' else 'REFINE'
        self.assertTrue(any('after an overrun' in p for p in X.qnet_rows_check(bad, spec)[0]))


class JobLinesTest(unittest.TestCase):
    def test_line_problems(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Setup(tmp)
            for j in S.jobs:
                self.assertEqual(X.qnet_line_problems(j), [], j['id'])
            self.assertEqual(X.qnet_line_problems(S.smoke.by_arm['fl_heuristic']), [])   # no Q-network: nothing
            j = S.by['fl_full']
            rel = PJ.rel(DEV['fl_full'])
            relative = {**j, 'cmd': [c if not c.startswith(Q.ENV_QNET) else f'{Q.ENV_QNET}={rel}' for c in j['cmd']]}
            self.assertTrue(any('is relative' in p for p in X.qnet_line_problems(relative)))
            no_env = {**j, 'cmd': j['cmd'][:-2]}
            self.assertTrue(any('no --utility-env' in p for p in X.qnet_line_problems(no_env)))
            unpinned = {**j, 'require_sha256': {k: v for k, v in j['require_sha256'].items() if k != rel}}
            self.assertTrue(any('not pinned' in p for p in X.qnet_line_problems(unpinned)))
            other = qnet_job(S.smoke.by_arm['fl_heuristic'], DEV['fl_bandit'], 'fl_bandit')
            swapped = {**other, 'policy_params': j['policy_params']}
            self.assertTrue(any('the line names' in p for p in X.qnet_line_problems(swapped)))
            self.assertTrue(any('--policy-params differ' in p for p in X.qnet_line_problems(swapped)))
            self.assertTrue(any('launcher arm fl_full' in p
                                for p in X.qnet_line_problems({**j, 'arm_name': 'fl_heuristic'})))
            self.assertTrue(any('fqi_nolease' in p
                                for p in X.qnet_line_problems({**j, 'protocol_arm': 'fl_fqi_nolease'})))
            twice = {**j, 'cmd': j['cmd'] + j['cmd'][-2:]}
            self.assertTrue(any('twice' in p for p in X.qnet_line_problems(twice)))

    def test_load_jobs_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Setup(tmp)
            self.assertEqual(len(X.load_jobs(S.job_file)), 4)
            j = S.by['fl_full']
            rel = PJ.rel(DEV['fl_full'])
            bad = S.write_jobs([{**j, 'cmd': [c if not c.startswith(Q.ENV_QNET) else f'{Q.ENV_QNET}={rel}'
                                              for c in j['cmd']]}], Path(tmp) / 'relative.jsonl')
            with self.assertRaises(ValueError) as cm:
                X.load_jobs(bad)
            self.assertIn('is relative', str(cm.exception))
            test_route = PJ.route_split()['test'][0]['route_id']
            with self.assertRaises(PermissionError):
                X.load_jobs(S.write_jobs([{**j, 'route_id': test_route}], Path(tmp) / 'test.jsonl'))
            with self.assertRaises(ValueError):
                X.load_jobs(S.write_jobs([{**j, 'kappa': 1.5}], Path(tmp) / 'kappa.jsonl'))
            with self.assertRaises(ValueError):
                X.load_jobs(S.write_jobs([j, j], Path(tmp) / 'dup.jsonl'))


def global_lease_criterion(job, run, summary, rows):
    """A stand-in for the extension's own criterion (the real one lives in framelease_v4/arms_ext)."""
    mode = ((summary or {}).get('policy') or {}).get('lease_mode')
    return CS._res(CS.PASS if mode == 'global_margin' else CS.FAIL, f'lease mode {mode!r}', lease_mode=mode)


class ExtensionHookTest(unittest.TestCase):
    def tearDown(self):
        X.unregister_extension_arm('fl_global_shield')
        sys.modules.pop('qnet_ext_hook_mod', None)

    def global_job(self, S, utility='v4_adet_d4'):
        base = S.smoke.by_arm['fl_heuristic']
        j = copy.deepcopy(base)
        j.update(id=f'v4ext_global_E5_k1.0_s11_r{j["route_id"]}', arm_name='fl_global_shield',
                 candidate='fl_global_shield',
                 protocol_arm='fl_global_shield', policy_params={'utility': utility},
                 output_dir='outputs/framelease_v4/infra_smoke_test/fl_global_shield')
        return j

    def global_run(self, S, j, lease_mode='global_margin'):
        run = TCS.make_run(S.root, {**j, 'arm_name': 'fl_heuristic'}, name='20261111T060606_gggggggg')
        edit_json(run / 'config.json', lambda d: d.update(v4_arm='fl_global_shield'))
        edit_json(fl(run) / 'summary.json', lambda d: d['policy'].update(lease_mode=lease_mode))
        return run

    def test_undeclared_arm_is_refused_then_judged_after_registration(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Setup(tmp)
            g = self.global_job(S)
            S.write_jobs(S.jobs + [g])
            with self.assertRaises(ValueError) as cm:
                X.load_jobs(S.job_file)
            self.assertIn('register_extension_arm', str(cm.exception))
            X.register_extension_arm('fl_global_shield', 'shield', 'fl_heuristic',
                                     {'global_lease': global_lease_criterion}, source='test')
            with self.assertRaises(ValueError):
                X.register_extension_arm('fl_x', 'shield', 'fl_heuristic', {'qnet': global_lease_criterion})
            with self.assertRaises(ValueError):
                X.register_extension_arm('fl_x', 'shield', 'fixed_deep')
            S.all_runs()
            self.global_run(S, g)
            rep = S.check()
            self.assertEqual(rep['verdict'], 'PASS', json.dumps([r for r in rep['jobs'] if r['status'] != 'PASS'],
                                                                indent=1)[:3000])
            self.assertEqual(rep['criteria'], list(CS.CRITERIA) + ['qnet', 'global_lease'])
            self.assertEqual(crit(rep, 'fl_global_shield', 'global_lease')['status'], CS.PASS)
            self.assertEqual(crit(rep, 'fl_global_shield', 'qnet')['status'], CS.NA)
            self.assertEqual(crit(rep, 'fl_global_shield', 'utility')['values']['utility'], 'v4_adet_d4')
            self.assertEqual(crit(rep, 'fl_full', 'global_lease')['status'], CS.NA)
            self.assertEqual(rep['extensions']['fl_global_shield']['base_arm'], 'fl_heuristic')

    def test_extension_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Setup(tmp)
            g = self.global_job(S)
            X.register_extension_arm('fl_global_shield', 'shield', 'fl_heuristic',
                                     {'global_lease': global_lease_criterion})
            S.all_runs()
            run = self.global_run(S, g, lease_mode='suffix')                      # the extension's criterion fails
            rows = read_rows(run)
            r = next(r for r in rows if r.get('p_both') and r['depth'] < 4)
            r['action'] = 'REFRESH'                                               # against a_det^4 (fl_heuristic rule)
            write_rows(run, rows)
            rep = S.check(S.jobs + [g])
            self.assertEqual(rep['verdict'], 'FAIL')
            self.assertEqual(crit(rep, 'fl_global_shield', 'global_lease')['status'], CS.FAIL)
            self.assertIn('a_det^4', crit(rep, 'fl_global_shield', 'utility')['detail'])

            def boom(job, run, summary, rows):
                raise RuntimeError('broken extension criterion')
            X.register_extension_arm('fl_global_shield', 'shield', 'fl_heuristic', {'global_lease': boom})
            c = crit(S.check(S.jobs + [g]), 'fl_global_shield', 'global_lease')
            self.assertEqual(c['status'], CS.FAIL)
            self.assertIn('check raised RuntimeError', c['detail'])

    def test_command_line_with_extension_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Setup(tmp)
            out_root = Path(tmp) / 'abs_runs'
            jobs = [{**j, 'output_dir': str(out_root / j['candidate'])} for j in S.jobs]   # absolute: root = ROOT
            g = self.global_job(S)
            g['output_dir'] = str(out_root / 'global')
            jf = S.write_jobs(jobs + [g], Path(tmp) / 'cli_jobs.jsonl')
            for j in jobs:
                make_qnet_run(S.root, j)
            self.global_run(S, g)
            mod = Path(tmp) / 'qnet_ext_hook_mod.py'
            mod.write_text('def register(checker):\n'
                           '    import test_check_smoke_ext as T\n'
                           '    checker.register_extension_arm("fl_global_shield", "shield", "fl_heuristic",\n'
                           '                                   {"global_lease": T.global_lease_criterion},\n'
                           '                                   "cli test")\n')
            sys.path.insert(0, tmp)
            try:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(X.main(['--jobs-file', str(jf), '--write']), 2)          # no --report
                    self.assertEqual(X.main(['--jobs-file', str(jf)]), 2)                    # undeclared arm
                    report = Path(tmp) / 'report.json'
                    code = X.main(['--jobs-file', str(jf), '--extension', 'qnet_ext_hook_mod:register', '--write',
                                   '--report', str(report)])
                self.assertEqual(code, 0, buf.getvalue()[-3000:])
                rep = json.loads(report.read_text())
                self.assertEqual(rep['verdict'], 'PASS')
                self.assertEqual(rep['job_file_sha256'], PJ.sha256_file(jf))
                self.assertIn('fl_global_shield', rep['extensions'])
                self.assertEqual(len(rep['jobs']), 5)
            finally:
                sys.path.remove(tmp)


# ============================================================================================ review fixes

def resigned(spec):
    """spec with weights_sha256 and name recomputed by the pinned qnet hash (after an edit of its weights)."""
    sha = Q._canonical_sha(spec)
    spec.update(weights_sha256=sha, name=f'v4_qnet_{sha[:12]}')
    Q.verify_spec(spec)
    return spec


def nonfinite_spec():
    """The synthetic 16-input network with output weights +-1e308: finite weights whose Q values overflow to +inf /
    -inf in the states of qnet_rows (positive hidden units), the case of qnet.py's 'nonfinite' bypass."""
    spec = synthetic_spec('fqi')
    spec['layers'][-1]['W'] = [[1e308, -1e308] for _ in spec['layers'][-1]['W']]
    return resigned(spec)


def over_at(calls):
    """wall_fn of CallTimer: the network calls numbered (from 1) in `calls` overrun B_pi, the others take 10 us."""
    calls = set(calls)
    return lambda i: 5e-4 if i + 1 in calls else 1e-5


class ReviewFixesTest(unittest.TestCase):
    """The fixes of the QNET review (outputs/framelease_v4/build/QNET/review/REVIEW.md: MF-1, MF-2, SF-1 to SF-4)."""

    def tearDown(self):
        X.unregister_extension_arm('fl_global_shield')

    # ---- MF-1: only fl_full / fl_bandit / fl_fqi_nolease take a Q-network (PROTOCOL Sec. 4.1)
    def test_mf1_qnet_line_with_another_protocol_arm_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Setup(tmp)
            j = S.by['fl_full']
            for parm in ('fl_global_shield', 'fl_heuristic', 'fl_risk', 'age_only', 'fl_behaviour'):
                probs = X.qnet_line_problems({**j, 'protocol_arm': parm})
                self.assertTrue(any('does not take a Q-network utility' in p for p in probs), (parm, probs))
            for parm in ('fl_full', 'fl_bandit', 'fl_fqi_nolease'):
                self.assertEqual(X.qnet_line_problems(S.by[parm]), [], parm)
            X.register_extension_arm('fl_global_shield', 'shield', 'fl_heuristic')     # declared: still refused
            bad = S.write_jobs([{**j, 'protocol_arm': 'fl_global_shield'}], Path(tmp) / 'mislabelled.jsonl')
            with self.assertRaises(ValueError) as cm:
                X.load_jobs(bad)
            self.assertIn("protocol arm 'fl_global_shield' does not take a Q-network utility", str(cm.exception))
            QNetCriterionTest().broken('fl_full', lambda run, job: None, job_edit=lambda jj: {
                **jj, 'protocol_arm': 'fl_global_shield'}, needle='does not take a Q-network utility')

    def test_mf1_qnet_utility_only_on_an_arm_whose_base_takes_qnet(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Setup(tmp)
            j = S.by['fl_full']
            run = make_qnet_run(S.root, j)
            summary, rows = json.loads((fl(run) / 'summary.json').read_text()), read_rows(run)
            self.assertEqual(X.c_utility_ext(j, run, summary, rows)['status'], CS.PASS)
            X.register_extension_arm('fl_global_shield', 'shield', 'fl_heuristic')
            for arm, needle in (('fl_global_shield', 'judged as its base arm fl_heuristic'),
                                ('fl_heuristic', 'accepts heuristic, adet'), ('fl_behaviour', 'accepts behaviour')):
                res = X._guarded(lambda: X.c_utility_ext({**j, 'arm_name': arm}, run, summary, rows))
                self.assertEqual(res['status'], CS.FAIL, (arm, res))
                self.assertIn('does not take a Q-network utility', res['detail'])
                self.assertIn(needle, res['detail'])

    # ---- MF-2: a run whose network never decided is DEFERRED
    def test_mf2_all_overrun_run_is_deferred(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Setup(tmp)
            spec = Q.load_spec(DEV['fl_full'])
            for j in S.jobs:
                rows = None
                if j['candidate'] == 'fl_full':
                    rows = qnet_rows(spec, n=200, pattern=lambda e: 'both', wall_fn=lambda i: 5e-4)[0]
                make_qnet_run(S.root, j, rows=rows)
            rep = S.check()
            c = crit(rep, 'fl_full', 'qnet')
            v = c['values']
            self.assertEqual(c['status'], CS.DEFERRED, c)
            self.assertIn('no network decision', c['detail'])
            self.assertEqual((v['network_calls'], v['network_decisions'], v['disabled_at_epoch']), (64, 0, 64))
            self.assertEqual(v['bypass'], {'slack': 0, 'disabled': 136, 'overrun': 64, 'nonfinite': 0})
            self.assertEqual(rep['verdict'], 'PASS')
            self.assertEqual(len(rep['deferred']), 1)
            self.assertIn('no network decision', rep['deferred'][0])
            for cand in ('fl_bandit', 'fl_fqi_nolease', 'synthetic'):                # the network decided: PASS
                v = crit(rep, cand, 'qnet')['values']
                self.assertEqual(crit(rep, cand, 'qnet')['status'], CS.PASS)
                self.assertEqual(v['network_decisions'], v['network_calls'])
            self.assertIn('network_decisions = 0', X.__doc__)

    def test_mf2_sf3_nonfinite_network_runs_are_deferred_without_false_fail(self):
        """Every call of a non-finite network is a 'nonfinite' bypass (fast calls) or an overrun that logs the raw
        +-inf (slow calls, SF-3): no problem in either run, and the network never decided: DEFERRED."""
        with tempfile.TemporaryDirectory() as tmp:
            S = Setup(tmp)
            spec = nonfinite_spec()
            path = Path(tmp) / 'nonfinite_fqi.json'
            path.write_text(json.dumps(spec))
            for label, wall_fn, byp in (('nf_fast', lambda i: 1e-5, 'nonfinite'), ('nf_slow', lambda i: 5e-4,
                                                                                    'overrun')):
                j = qnet_job(S.smoke.by_arm['fl_heuristic'], path, candidate=label)
                self.assertEqual(X.qnet_line_problems(j), [])
                with np.errstate(over='ignore', invalid='ignore'):
                    rows, u = qnet_rows(spec, n=150, pattern=lambda e: 'both', wall_fn=wall_fn)
                    run = make_qnet_run(S.root, j, rows=rows, name=f'20261111T080808_{label}xx')
                    res = X.check_run_ext(j, outcome_of(j, S.root), run)
                self.assertGreater(u.bypass[byp], 0, label)
                self.assertEqual(res['qnet']['status'], CS.DEFERRED, (label, res['qnet']))
                self.assertIn('no network decision', res['qnet']['detail'])
                self.assertEqual(res['qnet']['values']['bypass'], u.bypass, label)
                self.assertEqual(res['utility']['status'], CS.PASS, label)

    # ---- SF-1: a malformed criterion result FAILS its criterion; an unexpected error exits 2
    def test_sf1_malformed_extension_results_fail_the_criterion(self):
        malformed = ((None, 'returned NoneType'), ('PASS', 'returned str'),
                     ({'status': 'OK', 'detail': ''}, 'status'), ({'status': CS.PASS}, 'detail'),
                     ({'status': CS.PASS, 'detail': 3}, 'detail'),
                     ({'status': CS.PASS, 'detail': '', 'values': [1]}, 'values'),
                     ({'status': CS.PASS, 'detail': '', 'values': {'x': object()}}, 'JSON'),
                     ({'status': CS.PASS, 'detail': '', 'extra': 1}, 'unexpected keys'))
        for res, needle in malformed:
            self.assertIn(needle, X.result_problem(res), res)
        for ok in (CS._res(CS.PASS, 'fine', a=1.0, b=[1, None]), CS._res(CS.NA), CS._res(CS.DEFERRED, 'later')):
            self.assertIsNone(X.result_problem(ok))
        with tempfile.TemporaryDirectory() as tmp:
            S = Setup(tmp)
            S.all_runs()
            g = ExtensionHookTest.global_job(None, S)
            ExtensionHookTest.global_run(None, S, g)
            for res, needle in malformed:
                X.register_extension_arm('fl_global_shield', 'shield', 'fl_heuristic',
                                         {'global_lease': lambda job, run, summary, rows, res=res: res})
                rep = S.check(S.jobs + [g])                                    # never raises
                c = crit(rep, 'fl_global_shield', 'global_lease')
                self.assertEqual(c['status'], CS.FAIL, res)
                self.assertIn('malformed criterion result', c['detail'])
                self.assertIn(needle, c['detail'])
                self.assertEqual(rep['verdict'], 'FAIL')
                json.dumps(rep, sort_keys=True)                                 # the report stays writable

    def test_sf1_unexpected_exception_is_an_error_not_a_fail(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            S = Setup(tmp)
            err = io.StringIO()
            with mock.patch.object(X, 'check', side_effect=RuntimeError('broken checker')), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                self.assertEqual(X.main(['--jobs-file', str(S.job_file)]), 2)
            self.assertIn('Traceback', err.getvalue())
            self.assertIn('unexpected RuntimeError: broken checker', err.getvalue())
            mod = Path(tmp) / 'qnet_ext_broken_mod.py'
            mod.write_text('def register(checker):\n    raise ZeroDivisionError("broken extension")\n')
            sys.path.insert(0, tmp)
            err = io.StringIO()
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                    self.assertEqual(X.main(['--jobs-file', str(S.job_file), '--extension',
                                             'qnet_ext_broken_mod:register']), 2)
            finally:
                sys.path.remove(tmp)
                sys.modules.pop('qnet_ext_broken_mod', None)
            self.assertIn('unexpected ZeroDivisionError', err.getvalue())

    # ---- SF-2: --write refuses the runner's, driver's, generator's, tuning's and registration's files
    def test_sf2_report_path_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'root'
            out = root / 'outputs' / 'framelease_v4'
            (out / 'build' / 'X').mkdir(parents=True)
            manifest = Path(tmp) / 'MANIFEST.sha256'
            manifest.write_text(f'{"0" * 64}  outputs/framelease_v4/build/X/registered.json\n')
            (out / 'queue_p1').mkdir()
            (Path(tmp) / 'link').symlink_to(out / 'queue_p1')
            not_report = out / 'build' / 'X' / 'notes.json'
            not_report.write_text('{"schema": "something else"}\n')
            old_report = out / 'build' / 'X' / 'old_report.json'
            old_report.write_text(json.dumps({'schema': X.SCHEMA}))

            def problem(p):
                return X.report_path_problem(p, root, manifest)
            refused = {None: 'explicit --report', Path(tmp) / 'q' / 'jobs.d' / 'r.json': 'jobs.d',
                       out / 'queue_p1' / 'r.json': 'queue_p1', out / 'queue_p1_smoke2' / 'a' / 'r.json': 'queue_p1',
                       out / 'registration' / 'r.json': 'registration', out / 'p1_driver' / 'r.json': 'p1_driver',
                       out / 'p1_jobs' / 'r.json': 'p1_jobs', out / 'tuning' / 'sel' / 'r.json': 'tuning',
                       Path(tmp) / 'copy' / 'outputs' / 'framelease_v4' / 'tuning' / 'r.json': 'tuning',
                       Path(tmp) / 'link' / 'r.json': 'queue_p1', root / 'framelease_v4' / 'r.json': 'code tree',
                       root / 'third_party' / 'r.json': 'code tree', root / 'checkpoints' / 'r.json': 'code tree',
                       out / 'build' / 'X' / 'registered.json': 'registration manifest',
                       not_report: 'not a report', out / 'build': 'not a file'}
            for p, needle in refused.items():
                self.assertIn(needle, problem(p) or '', p)
            for p in (out / 'build' / 'X' / 'new.json', old_report, Path(tmp) / 'report.json',
                      out / 'build' / 'queue_notes.json'):
                self.assertIsNone(problem(p), p)
            # this ROOT: the registered files and the live directories (path checks only, nothing is written)
            for p in (CS.REGISTRATION_MANIFEST, ROOT / 'framelease_v4' / 'PROTOCOL.md',
                      ROOT / 'outputs/framelease_v4/p1_driver/report.json',
                      ROOT / 'outputs/framelease_v4/queue_p1/report.json', ROOT / 'framelease_v4/protocol/x.json'):
                self.assertIsNotNone(X.report_path_problem(p), p)

    def test_sf2_command_line_refuses_protected_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = Setup(tmp)
            jobs = [{**j, 'output_dir': str(Path(tmp) / 'abs' / j['candidate'])} for j in S.jobs]
            jf = S.write_jobs(jobs, Path(tmp) / 'jobs.jsonl')
            for j in jobs:
                make_qnet_run(S.root, j)
            qdir = Path(tmp) / 'outputs' / 'framelease_v4' / 'queue_x'
            qdir.mkdir(parents=True)
            other = Path(tmp) / 'other.json'
            other.write_text('{"keep": true}\n')
            report = Path(tmp) / 'report.json'
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                self.assertEqual(X.main(['--jobs-file', str(jf), '--write', '--report', str(qdir / 'r.json')]), 2)
                for force in ([], ['--force']):
                    self.assertEqual(X.main(['--jobs-file', str(jf), '--write', '--report', str(other)] + force), 2)
                    self.assertEqual(X.main(['--jobs-file', str(jf), '--write', '--report', str(jf)] + force), 2)
                self.assertEqual(X.main(['--jobs-file', str(jf), '--write', '--report', str(report)]), 0)
                self.assertEqual(X.main(['--jobs-file', str(jf), '--write', '--report', str(report)]), 0)
            self.assertFalse((qdir / 'r.json').exists())
            self.assertEqual(other.read_text(), '{"keep": true}\n')
            self.assertEqual(json.loads(report.read_text())['schema'], X.SCHEMA)
            self.assertIn('queue_x', err.getvalue())

    # ---- SF-3: the raw non-finite values of an overrunning call
    def test_sf3_overrun_raw_values(self):
        spec = nonfinite_spec()
        with np.errstate(over='ignore', invalid='ignore'):
            rows, u = qnet_rows(spec, n=100, pattern=lambda e: 'both', wall_fn=lambda i: 5e-4)
            self.assertEqual(u.bypass['overrun'], 64)
            over = [r for r in rows if r['features']['v4_bypass'] == 'overrun']
            self.assertEqual({(r['features']['v4_q_refine'], r['features']['v4_q_refresh']) for r in over},
                             {('inf', '-inf')})                                # la.jsonable's strings
            self.assertEqual(X.qnet_rows_check(rows, spec)[0], [])
            bad = copy.deepcopy(rows)
            next(r for r in bad if r['features']['v4_bypass'] == 'overrun')['features']['v4_q_refine'] = 1.0
            self.assertTrue(any("v4_q_refine 1.0 != the network's inf" in p for p in X.qnet_rows_check(bad, spec)[0]))
        finite = synthetic_spec('fqi')
        rows = qnet_rows(finite, n=100, pattern=lambda e: 'both', wall_fn=lambda i: 5e-4)[0]
        self.assertEqual(X.qnet_rows_check(rows, finite)[0], [])
        for logged in ('inf', '-inf', 'nan', float('inf')):
            bad = copy.deepcopy(rows)
            next(r for r in bad if r['features']['v4_bypass'] == 'overrun')['features']['v4_q_refresh'] = logged
            self.assertTrue(any('is not a number' in p for p in X.qnet_rows_check(bad, finite)[0]), logged)
        self.assertFalse(X._close(1.0, float('inf')))
        self.assertTrue(X._close(1.0 + 1e-12, 1.0))

    # ---- SF-4 / QNET-2: the exact disable rule of qnet.QUtility, replayed
    def test_sf4_disable_rule_is_replayed_exactly(self):
        """(overrunning calls, network calls made, expected epoch of the disable or None). Every epoch is a choice
        epoch with a network call until the disable, so call n = epoch n."""
        spec = synthetic_spec('fqi')
        cases = (('13 overruns in the first 63 calls', range(1, 14), 63, None),
                 ('... and an overrun at call 64', list(range(1, 14)) + [64], 80, 64),
                 ('4 of the first 64 calls', (10, 20, 30, 64), 80, 64),
                 ('3 of the first 64 calls', (10, 20, 64), 80, None),
                 ('calls 95-99: 5 > 0.05 x 99', range(95, 100), 120, 99),
                 ('calls 96-100: 5 > 0.05 x 100 is false', range(96, 101), 120, None),
                 ('12 of the last 256 calls', range(245, 257), 300, None),
                 ('13 of the last 256 calls', range(244, 257), 300, 256),
                 ('13 overruns, the oldest leaving the window', list(range(1, 2)) + list(range(246, 258)), 300, None))
        for label, calls, n, want in cases:
            rows, u = qnet_rows(spec, n=n, pattern=lambda e: 'both', wall_fn=over_at(calls))
            problems, v = X.qnet_rows_check(rows, spec, spec['name'])
            self.assertEqual(problems, [], label)
            self.assertEqual(u.disabled, want is not None, label)
            self.assertEqual(v['disabled_at_epoch'], want, label)
            self.assertEqual((v['network_calls'], v['bypass']), (u.n_calls, u.bypass), label)
            if want is not None:
                self.assertEqual(u.n_calls, want, label)
                self.assertEqual(v['bypass']['disabled'], n - want, label)
                bad = copy.deepcopy(rows)
                bad[want]['features'].update(v4_bypass=None, v4_q_refine=0.0, v4_q_refresh=0.0, v4_qnet_s=1e-5)
                self.assertTrue(any('after the network was disabled' in p for p in X.qnet_rows_check(bad, spec)[0]))
            else:
                bad = copy.deepcopy(rows)
                r = bad[-1]
                r['action'] = Q.REFINE if r['depth'] < spec['a_det']['depth'] else Q.REFRESH
                r['features'].update(v4_bypass='disabled', v4_q_refine=None, v4_q_refresh=None, v4_qnet_s=None)
                self.assertTrue(any('bypass "disabled" although' in p for p in X.qnet_rows_check(bad, spec)[0]))
        # the threshold in integers: o > 0.05 x m  <=>  o >= floor(m / 20) + 1, m = min(n, 256)
        rate = Q.QUtility.MAX_OVERRUN_RATE
        for m in range(Q.QUtility.MIN_CALLS_TO_DISABLE, Q.QUtility.WINDOW + 1):
            self.assertEqual(min(o for o in range(m + 1) if o > rate * m), m // 20 + 1, m)
        t = X.QNET_THRESHOLDS
        self.assertEqual((t['overrun_window'], t['min_calls_to_disable'], t['overrun_max_rate']),
                         (Q.QUtility.WINDOW, Q.QUtility.MIN_CALLS_TO_DISABLE, Q.QUtility.MAX_OVERRUN_RATE))
        for phrase in ('floor(m / 20) + 1', 'MIN_CALLS_TO_DISABLE = 64', 'calls 95-99', 'calls 96-100'):
            self.assertIn(phrase, X.__doc__)


if __name__ == '__main__':
    unittest.main()
