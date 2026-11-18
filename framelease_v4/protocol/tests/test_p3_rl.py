"""Phase-3 RL production driver (framelease_v4/protocol/p3_rl.py; PROTOCOL Secs. 4.7, 5.1-5.9, 8.1, 10.1, 13.2;
GAP_AUDIT Sec. 3.3 P3-1, P3-2, P3-4, P3-5 and Sec. 6 item 5). CPU only. Every output goes to a temporary directory;
the default output directory outputs/framelease_v4/rl_freeze is never written: setUpModule records its state and
refuses every framelease_v4 write under it (common._check_writable) while the module runs, tearDownModule checks the
state is unchanged, and its guards are tested on a patched path. outputs/framelease_v4/build is not written either (the
calibration guard is called, never written there). Read-only inputs: the development dataset
outputs/framelease_v4/rl_dev/smoke_20261110/dataset, the four v3 pilot runs it was built from (one run's logs are
copied where a test changes them; the production tests use P2 copies of all four, p2_runs, in the P2 output directory
of kappa 1.0 under a temporary root, config.json declaring the behaviour utility, with the registered P2 block
restricted to their pairs, pilot_plan), the envelope manifest and the route split; the tuning freeze, PROTOCOL.md and
its seal are synthetic (test_p2_jobs.Env), and so is the P2 block of the manifest interface test (test_p2_check.Block).

  cd /home/kang/Desktop/DAC && OMP_NUM_THREADS=1 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      -m pytest -q -p no:cacheprovider framelease_v4/protocol/tests/test_p3_rl.py

What is shown:
  * the stage machinery: each stage writes its record after its outputs, with the sha256 of its inputs and outputs
    (files under the output directory keyed '<out>/...'), its parameters and the sha256 of the previous record (a
    chain); a rerun skips consistent records; a changed output, input or parameter stops the driver unless --redo,
    which recomputes that stage and every later one; a copied output directory checks its own files; a missing input
    and an unwritten output are errors; one run per output directory (the lock refuses a second one);
  * the inputs: the tuning freeze passes only through the P2 gate (cited in Sec. 13.2, sealed PROTOCOL.md); p2_plan is
    the block of p2_jobs.py (132 runs, job ids, output directories); the P2 data manifest written by p2_check.py is
    accepted against the plan of its root and refused against the project's P2 output directories; a manifest of
    another freeze, d* or L*, another schema, a non-behaviour utility, another kappa or seed, a changed source log, a
    duplicate, miscounted counts, another job id, a run outside the P2 output directory of its kappa, a run or missing
    job outside the registered block is refused, a test route (episode or missing job) with PermissionError; missing
    episodes (missing jobs, registered runs the manifest does not list) stop (exit 4) unless --missing-episodes
    proceed, which is recorded as a deviation;
  * production stages dataset and p_both on a synthetic manifest over the P2 copies: reward identity per episode,
    P_both of the kappa-1.0 episodes, the cross-check of the dataset against the manifest and each run's own
    config.json (an entry naming a run of another DS, kappa, route, seed or utility stops the dataset stage); a
    development dataset with a test-route episode is refused; P_both equals metrics_v4.decision_metrics over the
    kappa-1.0 runs, and a decision row the dataset does not have stops stage p_both;
  * the development run end to end (smoke grid, 2 folds): 16 stages, three networks v4_qnet_<sha12> that qnet.load_spec
    reads back with a_det depth d*, 16 / 16 / 10 inputs and B_pi = 100 us, all skipped on resume; the deploy check
    (GAP_AUDIT P3-2: loaded by name with an absolute FRAMELEASE_V4_QNET, every logged decision row replayed, the sha256
    pin, bench p99 against B_pi) and the development freeze record (never a freeze); the status subcommand; the guards
    of the default output directory and the development options;
  * determinism given the seeds: a second run writes byte-identical dataset, reward identity, P_both, selection, refit
    and distillation files, forests with equal predictions, the same networks and the same replay counts; the
    selection with 2 joblib workers equals the one with 1 (n_jobs is not a stage parameter);
  * resumption: the driver killed in every stage in turn (after the outputs, before the record, with a partial
    temporary record; deploy_check inside the replay, FRAMELEASE_V4_QNET restored) resumes by repeating the command
    and ends with the uninterrupted result; a killed --redo resumes with --redo;
  * invalidation: a changed decision log invalidates p_both and every later stage, a changed development dataset
    every stage, a changed intermediate output its stage and every later one; each stops the driver until --redo;
  * the production command line up to p_both: refusals write nothing (a test-route episode, a changed or unhashed
    source log, another tuning freeze, a run outside the P2 output directory, another job id, an uncited
    selection.json: exit 1; missing episodes and a registered run the manifest does not list: exit 4); a rewritten P2
    manifest stops the resume until --redo; --missing-episodes proceed is recorded and needed again on resume;
  * the deploy check on synthetic networks: a deviating network with both heads (its counts checked through the bypass
    counters of the pinned QUtility, so an overrun bypass under load does not fail it), a network of another a_det
    depth, an answer outside A_feas, a relative network path (finding QNET-1), the pin, a bench over B_pi (no
    record, rerun);
  * the production freeze (P3-4, Sec. 5.9) on the synthetic manifest with one missing job: its contents, its
    completeness (episode list and every source log the dataset reads, three selection reports with the estimate and
    90% CI, three networks with sha256, name, family and arm, the distillation agreement, the P_both label and the
    metrics_v4 value, the sha256 of every file under framelease_v4/rl and of the P2 gate modules, the notes for the
    Sec. 13 entry, the deviation of option (c), every named file with its current sha256),
    load_rl_freeze, which refuses a development record, an uncited freeze when a citation is required, a changed
    network, a changed source log entry and a moved output directory, and the registered directory: once the freeze
    is cited, consistent stages skip and nothing is recomputed (a code change with --redo is refused);
  * the calibration (P3-5): list scheduling, the worker model of a hybrid SMT machine, the cost law, the synthetic
    dataset, the output guard and a small calibrate run with its in-sample validation;
  * the open cases of GAP_AUDIT Sec. 6 item 5: (a) no selectable candidate (ope.select selects none, with the held-out
    rule as the reason; or the a_det^{d*} head is unsupported in a training fold: the real case at d* 4, where the
    installed ope.select (Amendment A6) does not fit the candidate in that fold and writes the complete report, and
    the reason names each such fold with its per-head sample counts; a ValueError of ope.select stops the driver)
    and (b) a distillation shortfall stop with exit 4 by default; with --no-selectable adet /
    --distill-shortfall deploy_best the network is exported (the a_det^{d*}-equivalent one with both heads
    unsupported, its note and the name it shares with another arm / the best try), the deviation is in the stage
    records, the expensive stage does not rerun, and a resume without the option is refused.
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ.setdefault('PYTHONDONTWRITEBYTECODE', '1')       # also for the joblib workers of the n_jobs test
sys.dont_write_bytecode = True

from framelease_v4.protocol import p2_jobs as P2J  # noqa: E402
from framelease_v4.protocol import p3_rl as P  # noqa: E402
from framelease_v4.protocol.tests import test_p2_jobs as T2J  # noqa: E402  (the synthetic freeze and PROTOCOL.md)
from framelease_v4.protocol.tests import test_p2_check as T2C  # noqa: E402  (the synthetic P2 block)
from framelease_v4.rl import behaviour as B  # noqa: E402
from framelease_v4.rl import common as C  # noqa: E402
from framelease_v4.rl import qnet as Q  # noqa: E402

DEV_DATASET = ROOT / 'outputs' / 'framelease_v4' / 'rl_dev' / 'smoke_20261110' / 'dataset'
DEV_ARGS = ['--dev-dataset', str(DEV_DATASET), '--dev-d-star', '10', '--smoke', '--n-folds', '2']
BENCH_ARGS = ['--bench-n', '300']        # deploy_check: 300 timed calls per bench path (development option)
LOG_NAMES = ('config.json', 'raw/official_results.json', 'raw/agent/framelease/decisions.jsonl',
             'raw/agent/framelease/ticks.jsonl', 'raw/agent/metric_info.json')
N_PART_A = 2 + 4 * 3                     # dataset, p_both, then select/refit/distill/export per family
N_STAGES = N_PART_A + 2                  # + deploy_check, freeze
REAL_DEFAULT_OUT = P.DEFAULT_OUT         # outputs/framelease_v4/rl_freeze (GuardTest patches P.DEFAULT_OUT)
REAL_P2_PLAN = P.p2_plan                 # the registered P2 block (ProductionCliTest patches P.p2_plan)
_MODULE = {}


def tree_state(root):
    """{relative path: (size, mtime_ns)} of everything under root; None when root does not exist."""
    root = Path(root)
    if not root.exists():
        return None
    return {str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(root.rglob('*'))}


def setUpModule():
    """outputs/framelease_v4/rl_freeze is never written by these tests: its state is recorded here and compared in
    tearDownModule, and every framelease_v4 write under it (common._check_writable: atomic files, the dataset, the
    refit forests) is refused while the module runs."""
    real = C._check_writable

    def guarded(path):
        if P._inside(path, REAL_DEFAULT_OUT):
            raise PermissionError(f'test_p3_rl: the tests never write {REAL_DEFAULT_OUT}: {path}')
        return real(path)

    _MODULE['state'] = tree_state(REAL_DEFAULT_OUT)
    _MODULE['guard'] = mock.patch.object(C, '_check_writable', guarded)
    _MODULE['guard'].start()


def tearDownModule():
    _MODULE.pop('guard').stop()
    now = tree_state(REAL_DEFAULT_OUT)
    if now != _MODULE['state']:
        raise AssertionError(f'{REAL_DEFAULT_OUT} changed during the tests: {_MODULE["state"]} -> {now}')


def quiet(_msg):
    pass


def default_options(**kw):
    return {**{case: v[0] for case, v in P.OPEN_CASES.items()}, **kw}


def run_main(*argv):
    """(exit code, stdout, stderr) of p3_rl.main."""
    err, out = io.StringIO(), io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
        rc = P.main(list(argv))
    return rc, out.getvalue(), err.getvalue()


def records(out):
    return {p.stem: C.read_json(p) for p in sorted((Path(out) / 'stages').glob('*.json'))}


def pilot_episodes():
    """The four v3 pilot episodes of the development dataset (heuristic utility, kappa 1.0, training routes)."""
    return [e for e in C.read_json(DEV_DATASET / 'episodes.json') if e['kind'] == 'v3']


MISSING_ROUTE, MISSING_KAPPA = '14862', 1.5      # a training route of no pilot run: the missing job of the fixtures


def pilot_pairs():
    return [(str(e['route_id']), 1.0) for e in pilot_episodes()]


def pilot_plan(freeze, root, extra=()):
    """p3_rl.p2_plan restricted to the four pilot (route, kappa 1.0) pairs (plus extra), with the P2 output directories
    under root: the registered P2 block of the synthetic manifests."""
    keep = set(pilot_pairs()) | set(extra)
    return {pair: run for pair, run in REAL_P2_PLAN(freeze, root).items() if pair in keep}


def p2_runs(root, freeze):
    """The four v3 pilot runs as P2 behaviour runs: copies of their source logs in the P2 output directory of kappa
    1.0 under root (root/<p2_jobs.output_dir(1.0)>/runs/<run id>), config.json declaring the behaviour utility of the
    route at d* (the pilot used the heuristic; route, kappa 1.0 and seed 11 are the pilot's). Returns the run
    directories in pilot order."""
    d = int(freeze['d'])
    runs = []
    for e in pilot_episodes():
        src = Path(e['run_dir'])
        dst = Path(root) / P2J.output_dir(1.0) / 'runs' / src.name
        for n in LOG_NAMES:
            (dst / n).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src / n, dst / n)
        cfg = C.read_json(dst / 'config.json')
        cfg['v3']['policy_params'] = {'utility': P2J.behaviour_utility(e['route_id'], 1.0, d)[1]}
        write_json(dst / 'config.json', cfg)
        runs.append(dst)
    return runs


def missing_job(freeze, cause='timeout'):
    """A missing-job entry of the P2 manifest (p2_check.py format): route MISSING_ROUTE at kappa 1.5."""
    return {'job': P2J.job_id(freeze, MISSING_KAPPA, MISSING_ROUTE), 'route_id': MISSING_ROUTE,
            'kappa': MISSING_KAPPA, 'cause': cause, 'attempts': []}


def with_missing(doc, missing):
    """The manifest doc with the missing jobs and its counts (n_missing, n_jobs) set as p2_check.py writes them."""
    doc.update(missing=list(missing), n_missing=len(missing), n_jobs=len(doc['episodes']) + len(missing))
    return doc


def pilot_manifest(freeze, utility=None, runs=None):
    """A P2 data manifest (p2_check.py format, the fields P3 reads) over the four v3 pilot runs (runs: their P2 copies
    of p2_runs; None: the pilot run directories themselves, outside any P2 output directory), naming freeze, with the
    p2_jobs job ids. The entries declare the behaviour utility of the route at d* (the seed rule,
    p2_jobs.behaviour_utility), as a P2 manifest does."""
    d = int(freeze['d'])
    eps = []
    for i, e in enumerate(pilot_episodes()):
        rd = Path(e['run_dir']) if runs is None else Path(runs[i])
        eps.append({'job': P2J.job_id(freeze, 1.0, e['route_id']), 'route_id': e['route_id'], 'kappa': 1.0,
                    'seed': P.P2_SEED, 'utility': utility or P2J.behaviour_utility(e['route_id'], 1.0, d)[1],
                    'run_dir': str(rd), 'ds': e['ds'], 'n_choice': e['proof']['n_choice'],
                    'source_logs_sha256': {n: C.sha256_file(rd / n) for n in LOG_NAMES if (rd / n).is_file()}})
    return {'schema': P.P2_MANIFEST_SCHEMA, 'variant': 'FULL',
            'tuning_freeze': {'path': freeze['path'], 'sha256': freeze['sha256']},
            'd_star': {'d': d, 'utility': freeze.get('d_utility')},
            'L_star': {'label': freeze['L']['label'], 'sha256': freeze['L']['sha256']},
            'n_jobs': len(eps), 'n_episodes': len(eps), 'n_missing': 0, 'episodes': eps, 'missing': []}


def write_json(path, doc):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n')
    return path


class ToyChain:
    """Three file stages s1 -> s2 -> s3 (a.txt -> b.txt -> c.txt) for the stage machinery; calls lists the runs."""

    def __init__(self, seed='x', deviations=None):
        self.seed, self.calls, self.params, self.deviations = seed, [], {}, deviations or {}

    def stage(self, name, src, dst):
        def run(ctx):
            self.calls.append(name)
            text = (ctx.out / src).read_text() if src else self.seed
            path = C.atomic_write_text(ctx.out / dst, text + name)
            return {'outputs': [path], 'result': {'n': len(text)}, 'deviations': self.deviations.get(name, [])}
        return P.Stage(name, lambda ctx: [ctx.out / src] if src else [], run,
                       lambda ctx: {'p': self.params.get(name, 1)})

    def stages(self):
        return [self.stage('s1', None, 'a.txt'), self.stage('s2', 'a.txt', 'b.txt'), self.stage('s3', 'b.txt', 'c.txt')]


def ctx_dev(out, **options):
    return P.Ctx(out, 'development', 10, default_options(**options), log=quiet)


class StageMachineryTest(unittest.TestCase):
    def test_records_chain_skip_and_redo(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            T = ToyChain()
            done = P.drive(ctx_dev(out), T.stages())
            self.assertEqual([(n, how) for n, how, _ in done], [('s1', 'run'), ('s2', 'run'), ('s3', 'run')])
            recs = records(out)
            self.assertEqual(sorted(recs), ['s1', 's2', 's3'])
            for n, r in recs.items():
                self.assertEqual((r['schema'], r['stage'], r['script'], r['mode']),
                                 (P.STAGE_SCHEMA, n, P.THIS_REL, 'development'))
                self.assertEqual(r['params']['code_sha256'], P.code_sha256())
                self.assertEqual(r['params']['d_star'], 10)
            self.assertIsNone(recs['s1']['previous'])
            for a, b in (('s1', 's2'), ('s2', 's3')):
                self.assertEqual(recs[b]['previous'],
                                 {'stage': a, 'sha256': C.sha256_file(P.record_path(out, a))})
            self.assertEqual(recs['s1']['inputs'], {})
            self.assertEqual(recs['s2']['inputs'], {'<out>/a.txt': C.sha256_file(out / 'a.txt')})
            self.assertEqual(recs['s3']['outputs'], {'<out>/c.txt': C.sha256_file(out / 'c.txt')})
            self.assertEqual((out / 'c.txt').read_text(), 'xs1s2s3')
            # resume: every record consistent -> skipped
            done = P.drive(ctx_dev(out), T.stages())
            self.assertEqual([how for _, how, _ in done], ['skip'] * 3)
            self.assertEqual(T.calls, ['s1', 's2', 's3'])
            # a changed output stops the driver; --redo recomputes that stage and every later one
            (out / 'b.txt').write_text('tampered')
            with self.assertRaisesRegex(P.StageError, r's2: record .* inconsistent: output <out>/b.txt'):
                P.drive(ctx_dev(out), T.stages())
            done = P.drive(ctx_dev(out), T.stages(), redo=True)
            self.assertEqual([(n, how) for n, how, _ in done], [('s1', 'skip'), ('s2', 'run'), ('s3', 'run')])
            self.assertEqual((out / 'c.txt').read_text(), 'xs1s2s3')
            # a changed parameter stops the driver; --redo recomputes from that stage on
            T.params['s3'] = 2
            with self.assertRaisesRegex(P.StageError, r"s3: .*parameters differ: \['p'\]"):
                P.drive(ctx_dev(out), T.stages())
            T.calls.clear()
            P.drive(ctx_dev(out), T.stages(), redo=True)
            self.assertEqual(T.calls, ['s3'])
            # an earlier record rewritten (same content, new time stamps) breaks the chain link of the later ones
            T.seed = 'y'
            (out / 'a.txt').unlink()
            with self.assertRaisesRegex(P.StageError, r's1: .*output <out>/a.txt: sha256 None'):
                P.drive(ctx_dev(out), T.stages())
            P.record_path(out, 's1').unlink()
            with self.assertRaisesRegex(P.StageError, r's2: .*(chain: previous|input <out>/a.txt)'):
                P.drive(ctx_dev(out), T.stages())
            T.calls.clear()
            P.drive(ctx_dev(out), T.stages(), redo=True)
            self.assertEqual(T.calls, ['s2', 's3'])
            self.assertEqual((out / 'c.txt').read_text(), 'ys1s2s3')

    def test_copied_output_directory_checks_its_own_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, copy = Path(tmp) / 'out', Path(tmp) / 'copy'
            T = ToyChain()
            P.drive(ctx_dev(out), T.stages())
            shutil.copytree(out, copy)
            self.assertEqual([how for _, how, _ in P.drive(ctx_dev(copy), T.stages())], ['skip'] * 3)
            (copy / 'a.txt').write_text('tampered')
            with self.assertRaisesRegex(P.StageError, 's1: .*output <out>/a.txt'):
                P.drive(ctx_dev(copy), T.stages())
            self.assertEqual([how for _, how, _ in P.drive(ctx_dev(out), T.stages())], ['skip'] * 3)

    def test_stop_after_missing_inputs_and_unwritten_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            T = ToyChain()
            done = P.drive(ctx_dev(out), T.stages(), stop_after='s2')
            self.assertEqual([n for n, _, _ in done], ['s1', 's2'])
            self.assertEqual(sorted(records(out)), ['s1', 's2'])
            with self.assertRaisesRegex(P.StageError, '--stop-after'):
                P.drive(ctx_dev(out), T.stages(), stop_after='nope')
            missing = P.Stage('m', lambda ctx: [ctx.out / 'absent.txt'], lambda ctx: {})
            with self.assertRaisesRegex(P.StageError, r"m: missing inputs \['<out>/absent.txt'\]"):
                P.drive(ctx_dev(Path(tmp) / 'o2'), [missing])
            unwritten = P.Stage('u', lambda ctx: [], lambda ctx: {'outputs': [ctx.out / 'never.txt']})
            with self.assertRaisesRegex(P.StageError, 'u: outputs not written'):
                P.drive(ctx_dev(Path(tmp) / 'o3'), [unwritten])
            self.assertFalse(P.record_path(Path(tmp) / 'o3', 'u').exists())

    def test_a_record_that_used_an_open_case_option_needs_it_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            dv = P.deviation('distill_shortfall', 'deploy_best')
            self.assertEqual(dv['note'], P.RECORD_NOTE)
            T = ToyChain(deviations={'s2': [dv]})
            P.drive(ctx_dev(out, distill_shortfall='deploy_best'), T.stages())
            self.assertEqual(records(out)['s2']['deviations'], [dv])
            with self.assertRaisesRegex(P.StageError, 's2: .*--distill-shortfall deploy_best; pass it again'):
                P.drive(ctx_dev(out), T.stages())
            done = P.drive(ctx_dev(out, distill_shortfall='deploy_best'), T.stages())
            self.assertEqual([how for _, how, _ in done], ['skip'] * 3)

    def test_one_run_per_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            out.mkdir()
            T = ToyChain()
            with P.RunLock(out):
                self.assertRegex((out / P.LOCK_NAME).read_text(), rf'^pid {os.getpid()} since \d{{8}}T')
                with self.assertRaisesRegex(P.StageError, r'out/.p3_rl.lock is held by another p3_rl run \(pid '):
                    P.drive(ctx_dev(out), T.stages())
                rc, _, err = run_main('run', '--out', str(out), *DEV_ARGS)
                self.assertEqual(rc, 1, err)
                self.assertIn('held by another p3_rl run', err)
            self.assertEqual((T.calls, records(out)), ([], {}))
            self.assertEqual([how for _, how, _ in P.drive(ctx_dev(out), T.stages())], ['run'] * 3)
            self.assertTrue((out / P.LOCK_NAME).read_text().strip())                  # never an empty file
            self.assertEqual([how for _, how, _ in P.drive(ctx_dev(out), T.stages())], ['skip'] * 3)


class InputGateTest(unittest.TestCase):
    def test_the_tuning_freeze_passes_only_through_the_p2_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            E = T2J.Env(Path(tmp) / 'a')
            fr = P.load_tuning_freeze(E.sel, E.protocol, seal=E.seal)
            self.assertEqual((fr['sha256'], fr['d'], fr['L']['label']), (E.sha, 10, 'E5'))
            self.assertEqual(len(fr['cited_lines']), 1)
            E.write_protocol(T2J.protocol_text(''))                                     # not cited in Sec. 13.2
            with self.assertRaisesRegex(PermissionError, 'not cited in PROTOCOL.md Sec. 13.2'):
                P.load_tuning_freeze(E.sel, E.protocol, seal=E.seal)
            E2 = T2J.Env(Path(tmp) / 'b', sealed=False)                                  # an open amendment
            with self.assertRaisesRegex(PermissionError, 'not the sealed version'):
                P.load_tuning_freeze(E2.sel, E2.protocol, seal=E2.seal)
            # the CLI reads the registered PROTOCOL.md, which cites no synthetic freeze: exit 1, nothing written
            man = write_json(Path(tmp) / 'manifest.json', pilot_manifest(fr))
            out = Path(tmp) / 'out'
            rc, _, err = run_main('run', '--selection', str(E.sel), '--manifest', str(man), '--out', str(out))
            self.assertEqual(rc, 1, err)
            self.assertIn('PermissionError', err)
            self.assertFalse(out.exists())

    def test_the_manifest_written_by_p2_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            S = T2C.Block(tmp)                                                          # d* = 4: utilities _d4
            D = S.lines[3]
            S.attempt(D, 'launch_error', None, final=False)
            S.attempt(D, 'launch_error', None, final=True)
            S.complete(skip={D['id']})
            rep, man = S.check()
            self.assertEqual(rep['verdict'], 'PASS', rep['errors'] + rep['failed_criteria'])
            path = write_json(Path(tmp) / 'data_manifest.json', man)
            plan = P.p2_plan(S.freeze, S.root)                  # the registered block, its runs under the Block's root
            self.assertEqual(len(plan), 132)
            with self.assertRaisesRegex(P.Stop, r'131 episodes, 1 missing, 0 not listed, 132 registered runs: '
                                                r'.*launch_error'):
                P.load_p2_manifest(path, S.freeze, protocol=S.env.protocol, plan=plan)
            m = P.load_p2_manifest(path, S.freeze, 'proceed', protocol=S.env.protocol, plan=plan)
            self.assertEqual((len(m['run_dirs']), m['sha256'], m['cited_lines'], m['n_registered']),
                             (131, C.sha256_file(path), [], 132))
            self.assertEqual([e['run_dir'] for e in man['episodes']], [str(p) for p in m['run_dirs']])
            (dv,) = m['deviations']
            self.assertEqual((dv['case'], dv['option'], dv['note'], dv['n_not_listed']),
                             ('missing_episodes', 'proceed', P.RECORD_NOTE, 0))
            self.assertEqual(dv['missing'], [{'job': D['id'], 'route_id': D['route_id'], 'kappa': D['kappa'],
                                              'cause': 'launch_error'}])
            # the P2 output directories of the registered plan are those of the project: runs elsewhere are refused
            with self.assertRaisesRegex(ValueError, r'is not inside outputs/framelease_v4/rl_data/k1.0, the P2 output '
                                                    r'directory of kappa 1.0'):
                P.load_p2_manifest(path, S.freeze, 'proceed', protocol=S.env.protocol)
            # entered in Sec. 13.2: the citing line is recorded
            S.env.write_protocol(T2J.protocol_text(f'* P2 data manifest `{path}` (sha256 `{m["sha256"]}`).'))
            m = P.load_p2_manifest(path, S.freeze, 'proceed', protocol=S.env.protocol, plan=plan)
            self.assertEqual(len(m['cited_lines']), 1)
            # the manifest of another freeze is refused
            other = T2J.Env(Path(tmp) / 'other', d=4, doc={**T2J.freeze_doc(d=4), 'written': 'another freeze'})
            with self.assertRaisesRegex(ValueError, 'tuning freeze'):
                P.load_p2_manifest(path, other.freeze(), 'proceed', protocol=S.env.protocol, plan=plan)

    def test_the_registered_plan(self):
        """p2_plan is the P2 block of p2_jobs.py: 44 training routes x 3 kappas, the job ids and output directories."""
        with tempfile.TemporaryDirectory() as tmp:
            fr = T2J.Env(Path(tmp) / 'env').freeze()
            plan = P.p2_plan(fr)
            train, test = P2J.training_and_test()
            self.assertEqual(set(plan), {(str(r), k) for r in train for k in (1.0, 1.5, 2.0)})
            self.assertEqual(len(plan), 132)
            self.assertFalse({r for r, _ in plan} & set(test))
            lines, _ = P2J.build_block(fr)
            self.assertEqual({(str(j['route_id']), float(j['kappa'])): (j['id'], ROOT / j['output_dir'])
                              for j in lines},
                             {pair: (run['job'], run['output_dir']) for pair, run in plan.items()})

    def test_manifest_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            E = T2J.Env(Path(tmp) / 'env')
            fr = E.freeze()
            runs = p2_runs(tmp, fr)
            doc = pilot_manifest(fr, runs=runs)
            path = write_json(Path(tmp) / 'manifest.json', doc)
            plan4 = pilot_plan(fr, tmp)
            plan5 = pilot_plan(fr, tmp, [(MISSING_ROUTE, MISSING_KAPPA)])
            m = P.load_p2_manifest(path, fr, protocol=E.protocol, plan=plan4)
            self.assertEqual(([str(p) for p in m['run_dirs']], m['deviations'], m['missing'], m['n_registered']),
                             ([e['run_dir'] for e in doc['episodes']], [], [], 4))
            with self.assertRaises(FileNotFoundError):
                P.load_p2_manifest(Path(tmp) / 'absent.json', fr, protocol=E.protocol, plan=plan4)

            def refused(edit, exc=ValueError, pattern='', freeze=fr, plan=plan4, **kw):
                bad = json.loads(json.dumps(doc))
                edit(bad)
                p = write_json(Path(tmp) / 'bad.json', bad)
                with self.assertRaisesRegex(exc, pattern):
                    P.load_p2_manifest(p, freeze, protocol=E.protocol, plan=plan, **kw)

            def ep(k, **kv):
                return lambda d: d['episodes'][k].update(kv)

            refused(lambda d: d.update(schema='framelease_v4.p2_check/1'), pattern='not a P2 data manifest')
            refused(lambda d: d.update(variant='TRIMMED'), pattern='variant')
            refused(lambda d: d['tuning_freeze'].update(sha256='a' * 64), pattern='tuning freeze')
            refused(lambda d: d['d_star'].update(d=6), pattern=r'd\* 6 != freeze d\* 10')
            refused(lambda d: d['L_star'].update(label='E4'), pattern=r'L\* E4')
            refused(lambda d: None, pattern=r'd\* 10 != freeze d\* 6', freeze={**fr, 'd': 6})
            refused(ep(0, utility='heuristic'), pattern='not the behaviour utility')
            refused(ep(0, utility=B.behaviour_name(P.EPS, 5, 6)), pattern='not the behaviour utility')
            refused(ep(0, utility=B.behaviour_name(0.2, 5, 10)), pattern='not the behaviour utility')
            refused(ep(0, utility=B.behaviour_name(P.EPS, 5, 10)), pattern='behaviour seed rule')
            refused(ep(0, kappa=1.5), pattern='behaviour seed rule')                    # the seed of kappa 1.0
            refused(ep(1, kappa=1.2), pattern='kappa 1.2')
            refused(ep(1, seed=12), pattern='seed 12')
            refused(ep(2, run_dir=str(Path(tmp) / 'nowhere')), pattern='does not exist')
            refused(lambda d: d['episodes'][2]['source_logs_sha256'].update({'config.json': '0' * 64}),
                    pattern='config.json sha256')
            refused(lambda d: d['episodes'][2]['source_logs_sha256'].pop('raw/agent/framelease/ticks.jsonl'),
                    pattern='no sha256 of raw/agent/framelease/ticks.jsonl')
            refused(lambda d: d['episodes'].append(dict(d['episodes'][0])) or d.update(n_episodes=5, n_jobs=5),
                    pattern='duplicate')
            refused(lambda d: d.update(n_episodes=3), pattern=r'n_episodes 3 != 4 \(4 listed episodes, 0 missing')
            refused(lambda d: d.update(n_jobs=5), pattern=r'n_jobs 5 != 4')        # p2_check: episodes + missing jobs
            refused(lambda d: d.update(n_missing=1), pattern=r'n_missing 1 != 0')
            # the registered P2 block: job ids, the P2 output directory of the kappa, the registered pairs
            refused(ep(1, job='syn1'), pattern=r'syn1: job id != v4p2_fl_behaviour_E5_eps0.300_d10_k1.0_s11_r')
            refused(ep(3, run_dir=pilot_episodes()[3]['run_dir'], source_logs_sha256={
                n: C.sha256_file(Path(pilot_episodes()[3]['run_dir']) / n) for n in LOG_NAMES}),
                pattern=r'is not inside .*rl_data/k1.0, the P2 output directory of kappa 1.0')
            other = next(r for r in sorted(P2J.training_and_test()[0]) if (r, 1.0) not in pilot_pairs())
            refused(ep(0, route_id=other, utility=P2J.behaviour_utility(other, 1.0, 10)[1],
                       job=P2J.job_id(fr, 1.0, other)), pattern=f'route {other}, kappa 1.0. is not a run of the '
                                                                'registered P2 block')
            refused(lambda d: None, pattern='is not inside', plan=P.p2_plan(fr))           # the project's rl_data/
            # test routes: refused with PermissionError (the registered split and a given one), also as a missing job
            test_route = sorted(C.test_route_ids())[0]
            refused(ep(3, route_id=test_route), PermissionError, f'route {test_route} is a held-out test route')
            refused(lambda d: None, PermissionError, 'held-out test route',
                    test_routes=[doc['episodes'][1]['route_id']])
            refused(lambda d: with_missing(d, [{**missing_job(fr), 'route_id': test_route}]), PermissionError,
                    f'missing job .*route {test_route} is a held-out test route', plan=plan5)
            # missing jobs: registered runs with their job ids, never an episode's pair
            refused(lambda d: with_missing(d, [missing_job(fr)]), pattern='missing job .* is not a run of the '
                                                                          'registered P2 block')
            refused(lambda d: with_missing(d, [{**missing_job(fr), 'job': 'syn9'}]), pattern='syn9: job id',
                    plan=plan5)
            refused(lambda d: with_missing(d, [{**missing_job(fr), 'route_id': d['episodes'][0]['route_id'],
                                                'kappa': 1.0, 'job': d['episodes'][0]['job']}]), pattern='duplicate')
            # missing episodes (the manifest's missing jobs, registered runs it does not list): Stop (exit 4) unless
            # --missing-episodes proceed
            miss = [missing_job(fr)]
            refused(lambda d: with_missing(d, miss), P.Stop, r'--missing-episodes proceed', plan=plan5)
            refused(lambda d: None, P.Stop, r'4 episodes, 0 missing, 1 not listed, 5 registered runs: '
                                            r'v4p2_fl_behaviour_E5_eps0.300_d10_k1.5_s11_r14862 \(a registered P2 '
                                            r'run the manifest does not list', plan=plan5)
            m = P.load_p2_manifest(write_json(Path(tmp) / 'miss.json', with_missing(json.loads(json.dumps(doc)), miss)),
                                   fr, 'proceed', protocol=E.protocol, plan=plan5)
            self.assertEqual(m['deviations'][0]['missing'], [{k: miss[0][k] for k in ('job', 'route_id', 'kappa',
                                                                                       'cause')}])
            self.assertEqual((m['missing'], m['deviations'][0]['n_not_listed']), (miss, 0))
            m = P.load_p2_manifest(path, fr, 'proceed', protocol=E.protocol, plan=plan5)
            (dv,) = m['deviations']
            self.assertEqual((dv['n_not_listed'], [x['job'] for x in m['missing']]), (1, [miss[0]['job']]))


class ProductionStagesTest(unittest.TestCase):
    """Stages dataset and p_both in production mode on a synthetic P2 manifest over P2 copies of the four v3 pilot runs
    (Ctx built directly: the CLI reads the registered PROTOCOL.md, which cites no synthetic freeze)."""

    def test_dataset_reward_identity_and_p_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            E = T2J.Env(Path(tmp) / 'env')
            fr = E.freeze()
            miss = [missing_job(fr)]
            doc = with_missing(pilot_manifest(fr, runs=p2_runs(tmp, fr)), miss)
            path = write_json(Path(tmp) / 'manifest.json', doc)
            man = P.load_p2_manifest(path, fr, 'proceed', protocol=E.protocol,
                                     plan=pilot_plan(fr, tmp, [(MISSING_ROUTE, MISSING_KAPPA)]))
            out = Path(tmp) / 'out'
            ctx = P.Ctx(out, 'production', fr['d'], default_options(missing_episodes='proceed'), manifest=man,
                        freeze=fr, log=quiet)
            self.assertEqual((ctx.n_folds, ctx.n_boot, ctx.grid_kind, ctx.fqe_cfg), (5, 2000, 'registered',
                                                                                     P.O.FQEConfig()))
            self.assertEqual([len(ctx.grid(f)) for f in P.FAMILIES], [12, 12, 12])
            done = P.drive(ctx, P.stage_list(), stop_after='p_both')
            self.assertEqual([(n, how) for n, how, _ in done], [('dataset', 'run'), ('p_both', 'run')])
            rec = records(out)['dataset']
            self.assertEqual(set(rec['inputs']), {P.rel(path), fr['path'], P.rel(C.ROUTES_XML),
                                                  P.rel(C.TEST_ROUTES_JSON)})
            self.assertEqual(rec['inputs'][P.rel(path)], man['sha256'])
            self.assertEqual(rec['params']['p2_manifest'], man['path'])
            self.assertEqual([d['case'] for d in rec['deviations']], ['missing_episodes'])
            self.assertEqual((rec['result']['n_episodes'], rec['result']['n_missing'], rec['result']['n_registered']),
                             (4, 1, 5))
            ident = C.read_json(out / 'reward_identity.json')
            self.assertTrue(ident['all_identity_ok'])
            self.assertLessEqual(max(ident['max_abs_err_epochs'], ident['max_abs_err_choice']), 1e-9)
            self.assertEqual([r['run_dir'] for r in ident['episodes']],
                             [P.rel(e['run_dir']) for e in man['doc']['episodes']])
            ds = P.D.load_dataset(out / 'dataset')
            self.assertEqual([e['run_dir'] for e in ds.episodes], [str(p) for p in man['run_dirs']])
            self.assertEqual([(e['route_id'], e['kappa'], e['seed'], e['utility']) for e in ds.episodes],
                             [(e['route_id'], e['kappa'], e['seed'], e['utility']) for e in doc['episodes']])
            pb = C.read_json(out / 'p_both.json')
            eps = pilot_episodes()
            n_ch, n_ep = sum(e['proof']['n_choice'] for e in eps), sum(e['proof']['n_epochs'] for e in eps)
            self.assertEqual((pb['kappa'], pb['choice_epochs'], pb['decision_epochs']), (1.0, n_ch, n_ep))
            self.assertAlmostEqual(pb['p_both'], n_ch / n_ep, places=12)
            self.assertEqual(pb['label'], 'testable' if n_ch / n_ep >= 0.05 else 'not testable at this operating point')
            self.assertEqual(list(pb['by_kappa']), ['1.0'])
            self.assertEqual((pb['metrics_v4']['agrees'], pb['metrics_v4']['p_both'], pb['metrics_v4']['n_runs']),
                             (True, pb['p_both'], 4))
            # resume: both records consistent
            self.assertEqual([how for _, how, _ in P.drive(ctx, P.stage_list(), stop_after='p_both')], ['skip'] * 2)

    def test_the_dataset_must_agree_with_the_manifest_and_the_runs(self):
        """Each run's own config.json (route, kappa, seed, utility) and official DS must be what its manifest entry
        declares: an entry that passes every manifest check but names a run of another kappa, route, seed or utility
        stops the dataset stage (no record)."""
        with tempfile.TemporaryDirectory() as tmp:
            E = T2J.Env(Path(tmp) / 'env')
            fr = E.freeze()
            runs = p2_runs(tmp, fr)
            pilots = pilot_episodes()

            def check(case, edit, pattern, runs=runs, root=tmp):
                doc = pilot_manifest(fr, runs=runs)
                edit(doc)
                path = write_json(Path(tmp) / case / 'manifest.json', doc)
                pairs = {(str(e['route_id']), float(e['kappa'])) for e in doc['episodes']}   # the block: these runs
                plan = {pair: run for pair, run in P.p2_plan(fr, root).items() if pair in pairs}
                man = P.load_p2_manifest(path, fr, protocol=E.protocol, plan=plan)
                out = Path(tmp) / case / 'out'
                ctx = P.Ctx(out, 'production', fr['d'], default_options(), manifest=man, freeze=fr, log=quiet)
                with self.assertRaisesRegex(P.StageError, 'dataset: disagrees with the P2 manifest:\n  ' + pattern):
                    P.drive(ctx, P.stage_list(), stop_after='p_both')
                self.assertEqual(records(out), {}, case)

            def ds_plus_one(doc):
                doc['episodes'][2]['ds'] += 1.0
            check('ds', ds_plus_one, re.escape(P2J.job_id(fr, 1.0, pilots[2]['route_id'])) + ': official DS')

            # a kappa-1.0 run copied into the P2 output directory of kappa 1.5 and declared as the kappa-1.5 run
            k15 = Path(tmp) / P2J.output_dir(1.5) / 'runs' / runs[0].name
            shutil.copytree(runs[0], k15)
            r0 = pilots[0]['route_id']

            def kappa(doc):
                doc['episodes'][0].update(kappa=1.5, run_dir=str(k15), job=P2J.job_id(fr, 1.5, r0),
                                          utility=P2J.behaviour_utility(r0, 1.5, 10)[1])
            check('kappa', kappa, re.escape(P2J.job_id(fr, 1.5, r0)) + r": kappa 1.0 in the run's config.json != "
                  r'manifest 1.5')

            # a run declared as the run of another training route
            other = next(r for r in sorted(P2J.training_and_test()[0]) if (r, 1.0) not in pilot_pairs())

            def route(doc):
                doc['episodes'][0].update(route_id=other, job=P2J.job_id(fr, 1.0, other),
                                          utility=P2J.behaviour_utility(other, 1.0, 10)[1])
            check('route', route, re.escape(P2J.job_id(fr, 1.0, other)) + f": route_id '{r0}' in the run's "
                  f"config.json != manifest '{other}'")

            # a run of another seed or another utility (config.json edited in fresh copies; the manifest hashes them)
            for case, key, value in (('seed', 'seed', 12), ('utility', 'utility', B.behaviour_name(P.EPS, 5, 10))):
                root = Path(tmp) / case
                runs_c = p2_runs(root, fr)
                cfg = C.read_json(runs_c[1] / 'config.json')
                if key == 'seed':
                    cfg['seed'] = value
                else:
                    cfg['v3']['policy_params']['utility'] = value
                write_json(runs_c[1] / 'config.json', cfg)
                check(case, lambda doc: None, re.escape(P2J.job_id(fr, 1.0, pilots[1]['route_id'])) +
                      re.escape(f": {key} {value!r} in the run's config.json != manifest"), runs=runs_c, root=root)

    def test_a_development_dataset_with_a_test_route_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            dev = Path(tmp) / 'devds'
            shutil.copytree(DEV_DATASET, dev)
            eps = C.read_json(dev / 'episodes.json')
            eps[-1]['route_id'] = sorted(C.test_route_ids())[0]
            write_json(dev / 'episodes.json', eps)
            out = Path(tmp) / 'out'
            argv = ['run', '--out', str(out)] + DEV_ARGS
            argv[argv.index(str(DEV_DATASET))] = str(dev)
            rc, _, err = run_main(*argv)
            self.assertEqual(rc, 1, err)
            self.assertIn('test-route or non-training episodes', err)
            self.assertEqual(records(out), {})


class Interrupted(BaseException):
    """A kill of the driver (not caught by p3_rl.main, as KeyboardInterrupt or SIGKILL)."""


def interrupting(name):
    """Patch p3_rl.stage_list so that stage `name` is killed after its run wrote its outputs and before its record,
    leaving a partial temporary file of the record (a kill inside common.atomic_write_text). deploy_check is killed
    inside the network replay instead, while FRAMELEASE_V4_QNET is set."""
    real = P.stage_list

    def stages():
        out = real()
        st = next(s for s in out if s.name == name)
        run = st.run

        def killed(ctx):
            if name == 'deploy_check':
                calls = []

                def shield_result(row):
                    calls.append(row)
                    if len(calls) == 50:
                        raise Interrupted(name)
                    return real_shield(row)

                from framelease_v4.rl import smoke as RS
                real_shield = RS._shield_result
                with mock.patch.object(RS, '_shield_result', shield_result):
                    run(ctx)
            run(ctx)
            stages_dir = P.record_path(ctx.out, name).parent
            stages_dir.mkdir(parents=True, exist_ok=True)
            (stages_dir / f'{name}.json.{"0" * 32}.tmp').write_text('{"partial')
            raise Interrupted(name)

        st.run = killed
        return out

    return mock.patch.object(P, 'stage_list', stages)


def dev_args(dataset):
    return ['--dev-dataset', str(dataset)] + DEV_ARGS[2:]


DETERMINISTIC = ['dataset/manifest.json', 'dataset/episodes.json', 'dataset/transitions.npz', 'dataset/epochs.npz',
                 'reward_identity.json', 'p_both.json'] + \
    [f'{s}_{f}.json' for f in P.FAMILIES for s in ('select', 'refit', 'distill')]


def assert_same_results(tc, out, ref):
    """The deterministic outputs of run out (all, or those of the stages it ran) agree with the reference run ref
    (seeds fixed: route folds 20261110, bootstrap 7, FQE 1, trainers and distillation): byte-identical files
    (DETERMINISTIC), the same refit forests (equal predictions; the joblib bytes differ in the uninitialized padding
    of sklearn's tree node arrays), the same networks (name and weights sha256; the provenance names the output
    directory) and the same replay counts of the deploy check. Returns the number of byte-compared files."""
    same = [n for n in DETERMINISTIC if (Path(out) / n).is_file()]
    for n in same:
        tc.assertEqual(C.sha256_file(Path(out) / n), C.sha256_file(Path(ref) / n), n)
    ds = P.D.load_dataset(Path(ref) / 'dataset')
    for f in P.FAMILIES:
        if (Path(out) / f'refit_{f}.joblib').is_file():
            qa, qb = P.load_refit_model(out, f), P.load_refit_model(ref, f)
            x = P.TR._cols(P.train_states(ds, C.read_json(Path(ref) / f'refit_{f}.json')['train_episodes']),
                           qa.cand.columns)
            tc.assertTrue(np.array_equal(qa.predict(x), qb.predict(x), equal_nan=True), f)
        if (Path(out) / f'qnet_{f}.json').is_file():
            a, b = C.read_json(Path(out) / f'qnet_{f}.json'), C.read_json(Path(ref) / f'qnet_{f}.json')
            tc.assertEqual((a['name'], a['weights_sha256']), (b['name'], b['weights_sha256']), f)
    if (Path(out) / 'deploy_check.json').is_file():
        da, db = (C.read_json(Path(p) / 'deploy_check.json') for p in (out, ref))
        for f in P.FAMILIES:
            ra, rb = da['networks'][f]['replay'], db['networks'][f]['replay']
            tc.assertEqual({k: ra[k] for k in ('rows', 'choice_rows', 'deviations', 'problems')},
                           {k: rb[k] for k in ('rows', 'choice_rows', 'deviations', 'problems')}, f)
    return len(same)


class DevelopmentRunTest(unittest.TestCase):
    """The development run end to end on the smoke dataset (smoke grid, smoke FQE, 2 folds) through the CLI."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / 'out'
        cls.env_before = os.environ.get(Q.ENV_QNET)
        cls.rc, cls.stdout, cls.stderr = run_main('run', '--out', str(cls.out), *DEV_ARGS, *BENCH_ARGS)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_stages_records_and_chain(self):
        self.assertEqual(self.rc, 0, self.stderr)
        recs = records(self.out)
        names = P.stage_names()
        self.assertEqual(len(names), N_STAGES)
        self.assertEqual(sorted(recs), sorted(names))
        prev = None
        for n in names:
            r = recs[n]
            self.assertEqual(r['previous'], prev, n)
            self.assertEqual((r['mode'], r['deviations']), ('development', []))
            prev = {'stage': n, 'sha256': C.sha256_file(P.record_path(self.out, n))}
            for k, sha in {**r['inputs'], **r['outputs']}.items():
                self.assertEqual(C.sha256_file(P.rec_path(self.out, k)), sha, (n, k))
        self.assertEqual(recs['dataset']['params']['dev_dataset'], P.rel(DEV_DATASET))
        for f in P.FAMILIES:
            sp = recs[f'select_{f}']['params']
            self.assertEqual((sp['n_folds'], sp['grid'], sp['n_boot'], len(sp['candidates'])), (2, 'smoke', 500, 2))
            self.assertEqual({c['d_det'] for c in sp['candidates']}, {10})
            self.assertEqual(recs[f'distill_{f}']['params']['min_agreement'], 0.98)
        self.assertEqual({k: recs['deploy_check']['params'][k] for k in ('bench_n', 'bench_warm', 'gate')},
                         {'bench_n': 300, 'bench_warm': 300, 'gate': 'featurize_forward'})
        self.assertEqual(recs['freeze']['params']['file'], 'rl_freeze_dev.json')
        self.assertEqual(set(recs['freeze']['inputs']), {f'<out>/stages/{n}.json' for n in names[:-1]})
        ident = C.read_json(self.out / 'reward_identity.json')
        self.assertTrue(ident['all_identity_ok'])
        self.assertEqual(ident['n_episodes'], len(C.read_json(DEV_DATASET / 'episodes.json')))
        for n in ('manifest.json', 'episodes.json', 'transitions.npz', 'epochs.npz'):
            self.assertEqual(C.sha256_file(self.out / 'dataset' / n), C.sha256_file(DEV_DATASET / n))

    def test_networks(self):
        self.assertEqual(self.rc, 0, self.stderr)
        recs = records(self.out)
        for f, n_in in (('fqi', 16), ('bandit', 16), ('fqi_nolease', 10)):
            spec = Q.load_spec(self.out / f'qnet_{f}.json')
            self.assertRegex(spec['name'], r'^v4_qnet_[0-9a-f]{12}$')
            self.assertTrue(B.QNET_RE.match(spec['name']))
            self.assertEqual((spec['a_det']['depth'], len(spec['feature_columns']), spec['policy_budget_s']),
                             (10, n_in, P.POLICY_BUDGET_S))
            self.assertEqual([len(L['b']) for L in spec['layers']], [32, 32, 2])
            res = recs[f'export_{f}']['result']
            self.assertEqual((res['name'], res['arm'], res['n_inputs']), (spec['name'], P.ARM_OF[f], n_in))
            dis = C.read_json(self.out / f'distill_{f}.json')
            self.assertTrue(dis['ok'])
            self.assertGreaterEqual(dis['agreement'], 0.98)
            prov = spec['provenance']
            self.assertEqual((prov['mode'], prov['family'], prov['d_star'], prov['selected']),
                             ('development', f, 10, C.read_json(self.out / f'select_{f}.json')['selected']))
            self.assertEqual(prov['selection']['sha256'], C.sha256_file(self.out / f'select_{f}.json'))
            P.load_refit_model(self.out, f)                                          # sha256-gated unpickling

    def test_deploy_check(self):
        self.assertEqual(self.rc, 0, self.stderr)
        doc = C.read_json(self.out / 'deploy_check.json')
        files = [Path(e['run_dir']) / 'raw/agent/framelease/decisions.jsonl' for e in pilot_episodes()]
        rows = [r for f in files for r in C.read_jsonl(f)]
        n_choice = sum(1 for r in rows if len(r['feasible']) == 2)
        self.assertGreater(n_choice, 0)
        self.assertTrue(doc['ok'])
        self.assertEqual((doc['n_logged_runs'], doc['bench_states']), (4, {'n': n_choice, 'kind': 'choice states'}))
        names = {f: C.read_json(self.out / f'qnet_{f}.json')['name'] for f in P.FAMILIES}
        for f, v in doc['networks'].items():
            self.assertEqual((v['name'], v['arm'], v['family'], v['a_det_depth']), (names[f], P.ARM_OF[f], f, 10))
            self.assertEqual(v['abs_path'], str((self.out / f'qnet_{f}.json').resolve()))
            self.assertTrue(Path(v['abs_path']).is_absolute())
            self.assertTrue(all(v['identity'].values()))
            rep = v['replay']
            self.assertEqual((rep['runs'], rep['rows'], rep['choice_rows'], rep['problems']),
                             (4, len(rows), n_choice, {}))
            self.assertEqual(sum(rep['actions_at_choice'].values()), n_choice)
            self.assertEqual(rep['deviations'], 0)                     # the pilot logged no REFRESH at a choice state
            self.assertTrue(v['pin_refuses_other_file'])
            self.assertIn(v['pin_other'], set(names.values()) - {v['name']})
            self.assertEqual(set(v['bench_us']), {'forward', 'featurize_forward', 'select', 'decide_q',
                                                  'decide_heuristic', 'decide_bypass'})
            self.assertEqual(v['bench_us']['featurize_forward']['n'], 300)
            self.assertLessEqual(v['bench_gate_p99_us'], 100.0)
        rec = records(self.out)['deploy_check']
        self.assertEqual({k for k in rec['inputs'] if k.endswith('decisions.jsonl')}, {P.rel(f) for f in files})
        self.assertEqual(os.environ.get(Q.ENV_QNET), self.env_before)          # restored after every load

    def test_development_freeze_record(self):
        self.assertEqual(self.rc, 0, self.stderr)
        self.assertFalse((self.out / 'rl_freeze.json').exists())
        path = self.out / 'rl_freeze_dev.json'
        doc = C.read_json(path)
        self.assertEqual((doc['schema'], doc['mode'], doc['frozen'], doc['d_star'], doc['variant']),
                         (P.FREEZE_SCHEMA, 'development', False, 10, 'FULL'))
        self.assertEqual((doc['tuning_freeze'], doc['p2_manifest'], doc['dev_dataset']),
                         (None, None, P.rel(DEV_DATASET)))
        recs = records(self.out)
        for f in P.FAMILIES:
            fam, res = doc['families'][f], recs[f'export_{f}']['result']
            self.assertEqual((fam['network']['name'], fam['arm'], fam['distillation']['deployed_agreement']),
                             (res['name'], P.ARM_OF[f], res['agreement']))
            self.assertEqual(doc['job_lines'][P.ARM_OF[f]], {'utility': res['name'], Q.ENV_QNET: fam['network'][
                'abs_path'], 'qnet_file_sha256': C.sha256_file(self.out / f'qnet_{f}.json')})
            sel = C.read_json(self.out / f'select_{f}.json')
            self.assertEqual((fam['selected'], fam['estimate']['mean_delta'], fam['estimate']['ci90']),
                             (sel['selected'], sel['estimate']['mean_delta'],
                              [sel['estimate']['bootstrap']['lo'], sel['estimate']['bootstrap']['hi']]))
            self.assertEqual([c['label'] for c in fam['candidates']], [r['label'] for r in sel['candidates']])
            self.assertTrue(fam['deploy_check']['ok'])
        self.assertEqual(doc['p_both']['label'], C.read_json(self.out / 'p_both.json')['label'])
        self.assertEqual(doc['code_sha256'], P.code_sha256())
        self.assertIn('rl/qnet.py', doc['code_sha256'])
        self.assertEqual([s['stage'] for s in doc['stage_chain']], P.stage_names()[:-1])
        for s in doc['stage_chain']:
            self.assertEqual(s['record_sha256'], C.sha256_file(P.record_path(self.out, s['stage'])))
        for k, sha in doc['files'].items():
            self.assertEqual(C.sha256_file(P.abs_path(k)), sha, k)
        self.assertEqual(len(doc['dataset']['episodes']), doc['dataset']['n_episodes'])
        self.assertTrue(all(e['source_logs_sha256'] for e in doc['dataset']['episodes']))
        with self.assertRaisesRegex(PermissionError, 'never a freeze'):
            P.load_rl_freeze(path)

    def test_status(self):
        self.assertEqual(self.rc, 0, self.stderr)
        rc, stdout, err = run_main('status', '--out', str(self.out))
        self.assertEqual(rc, 0, err)
        self.assertEqual(stdout.count(' done  '), N_STAGES)
        self.assertIn(f'{N_STAGES} done, 0 inconsistent, 0 missing', stdout)
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / 'copy'
            shutil.copytree(self.out, copy)
            (copy / 'p_both.json').write_text('{}')
            P.record_path(copy, 'freeze').unlink()
            rc, stdout, _ = run_main('status', '--out', str(copy))
            self.assertEqual(rc, 1)
            self.assertIn('p_both                 INCONSISTENT: output <out>/p_both.json', stdout)
            self.assertIn('freeze                 missing', stdout)
            rc, stdout, _ = run_main('status', '--out', str(Path(tmp) / 'empty'))
            self.assertEqual(rc, 3)
            self.assertIn(f'0 done, 0 inconsistent, {N_STAGES} missing', stdout)
            self.assertFalse((Path(tmp) / 'empty').exists())                   # status reads only

    def test_determinism_and_resume(self):
        self.assertEqual(self.rc, 0, self.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            out2 = Path(tmp) / 'out2'
            rc, _, err = run_main('run', '--out', str(out2), '--stop-after', 'export_fqi_nolease', *DEV_ARGS)
            self.assertEqual(rc, 0, err)
            self.assertEqual(assert_same_results(self, out2, self.out), len(DETERMINISTIC))   # given the seeds
            self.assertEqual(C.read_json(out2 / 'refit_fqi.json')['model'], 'refit_fqi.joblib')  # location-free
            rc, stdout, err = run_main('run', '--out', str(out2), '--stop-after', 'export_fqi_nolease', *DEV_ARGS)
            self.assertEqual((rc, stdout.count('[skip]'), stdout.count('[run ]')), (0, N_PART_A, 0), err)
            rc, stdout, err = run_main('run', '--out', str(out2), *DEV_ARGS, *BENCH_ARGS)   # deploy_check, freeze
            self.assertEqual((rc, stdout.count('[skip]'), stdout.count('[run ]')), (0, N_PART_A, 2), err)
            self.assertEqual(len(records(out2)), N_STAGES)
            assert_same_results(self, out2, self.out)                                    # + the replay counts
            rc, stdout, err = run_main('run', '--out', str(out2), *DEV_ARGS, *BENCH_ARGS)
            self.assertEqual((rc, stdout.count('[skip]')), (0, N_STAGES), err)
            rc, _, err = run_main('run', '--out', str(out2), *DEV_ARGS)                      # another bench size
            self.assertEqual(rc, 1, err)
            self.assertIn("deploy_check: record", err)
            rc, _, err = run_main('run', '--out', str(out2), '--stop-after', 'export_fqi_nolease',
                                  *DEV_ARGS[:-1], '3')                                     # another n_folds
            self.assertEqual(rc, 1, err)
            self.assertIn("select_fqi: record", err)
            # the refit forests are unpickled only with the sha256 of their stage record
            (out2 / 'refit_bandit.joblib').write_bytes((out2 / 'refit_bandit.joblib').read_bytes() + b'\0')
            with self.assertRaisesRegex(P.StageError, 'refusing to load it'):
                P.load_refit_model(out2, 'bandit')

    def test_resume_after_an_interruption_at_every_stage(self):
        """The driver is killed in every stage in turn (after the stage's outputs and before its record, with a partial
        temporary record; deploy_check inside the replay). Repeating the command resumes: the finished stages are
        skipped, the killed one runs again, and the result equals the uninterrupted run. A killed --redo resumes with
        --redo (the records of the old chain after the recomputed stage are stale)."""
        self.assertEqual(self.rc, 0, self.stderr)
        names = P.stage_names()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            argv = ['run', '--out', str(out), *DEV_ARGS, *BENCH_ARGS]
            for k, n in enumerate(names):
                with interrupting(n), self.assertRaises(Interrupted):
                    run_main(*argv)
                self.assertEqual(sorted(records(out)), sorted(names[:k]), n)        # no record of the killed stage
                self.assertEqual(os.environ.get(Q.ENV_QNET), self.env_before, n)
            self.assertEqual(run_main('status', '--out', str(out))[0], 3)
            rc, stdout, err = run_main(*argv)
            self.assertEqual((rc, stdout.count('[skip]'), stdout.count('[run ]')), (0, N_STAGES - 1, 1), err)
            self.assertEqual(len(list((out / 'stages').glob('*.tmp'))), N_STAGES - 1)   # partial records: ignored
            self.assertEqual(assert_same_results(self, out, self.out), len(DETERMINISTIC))
            self.assertEqual(run_main('status', '--out', str(out))[0], 0)
            # a killed --redo: select_bandit.json changed, the redo killed in refit_bandit
            sel = out / 'select_bandit.json'
            sel.write_bytes(sel.read_bytes() + b' ')
            rc, _, err = run_main(*argv)
            self.assertEqual(rc, 1, err)
            self.assertRegex(err, 'select_bandit: record .* inconsistent: output <out>/select_bandit.json')
            with interrupting('refit_bandit'), self.assertRaises(Interrupted):
                run_main(*argv, '--redo')
            rc, _, err = run_main(*argv)
            self.assertEqual(rc, 1, err)
            self.assertRegex(err, r'refit_bandit: record .* inconsistent: chain: previous')
            rc, stdout, err = run_main(*argv, '--redo')
            k = names.index('refit_bandit')
            self.assertEqual((rc, stdout.count('[skip]'), stdout.count('[run ]')), (0, k, N_STAGES - k), err)
            self.assertEqual(assert_same_results(self, out, self.out), len(DETERMINISTIC))
            self.assertEqual(run_main('status', '--out', str(out))[0], 0)

    def test_the_selection_does_not_depend_on_n_jobs(self):
        """ope.select with 2 joblib workers writes the same report as with 1; n_jobs is not a stage parameter, so a
        resume with another --n-jobs skips the finished stages."""
        self.assertEqual(self.rc, 0, self.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            argv = ['run', '--out', str(out), '--stop-after', 'select_fqi', *DEV_ARGS]
            rc, _, err = run_main(*argv, '--n-jobs', '2')
            self.assertEqual(rc, 0, err)
            self.assertEqual(records(out)['select_fqi']['host']['n_jobs'], 2)
            self.assertEqual(C.sha256_file(out / 'select_fqi.json'), C.sha256_file(self.out / 'select_fqi.json'))
            rc, stdout, err = run_main(*argv)
            self.assertEqual((rc, stdout.count('[skip]'), stdout.count('[run ]')), (0, 3, 0), err)


class InvalidationTest(unittest.TestCase):
    """A changed input invalidates its stage and every later one: the driver stops (exit 1) until --redo, which
    recomputes exactly those stages; the earlier ones stay skipped."""

    def test_a_changed_log_dataset_or_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            dev = Path(tmp) / 'devds'                       # the development dataset, one v3 run read from a copy
            shutil.copytree(DEV_DATASET, dev)
            eps = C.read_json(dev / 'episodes.json')
            k = next(i for i, e in enumerate(eps) if e['kind'] == 'v3')
            run = Path(tmp) / 'run'
            for n in LOG_NAMES:
                (run / n).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(Path(eps[k]['run_dir']) / n, run / n)
            eps[k]['run_dir'] = str(run)
            write_json(dev / 'episodes.json', eps)
            out = Path(tmp) / 'out'
            argv = ['run', '--out', str(out), *dev_args(dev), *BENCH_ARGS]
            rc, stdout, err = run_main(*argv)
            self.assertEqual((rc, stdout.count('[run ]')), (0, N_STAGES), err)
            names = {f: C.read_json(out / f'qnet_{f}.json')['name'] for f in P.FAMILIES}
            dec = run / 'raw/agent/framelease/decisions.jsonl'
            self.assertIn(P.rel(dec), records(out)['deploy_check']['inputs'])
            self.assertIn(P.rel(dec), records(out)['p_both']['inputs'])                  # a kappa-1.0 shield run
            # a changed decision log (an input of p_both and deploy_check): p_both and every later stage
            dec.write_text(dec.read_text() + '\n')
            rc, _, err = run_main(*argv)
            self.assertEqual(rc, 1, err)
            self.assertRegex(err, r'p_both: record .* inconsistent: input .*decisions.jsonl: sha256')
            rc, stdout, err = run_main(*argv, '--redo')
            self.assertEqual((rc, stdout.count('[skip]'), stdout.count('[run ]')), (0, 1, N_STAGES - 1), err)
            self.assertEqual({f: C.read_json(out / f'qnet_{f}.json')['name'] for f in P.FAMILIES}, names)
            logs = C.read_json(out / 'rl_freeze_dev.json')['dataset']['episodes'][k]['source_logs_sha256']
            self.assertEqual(logs['raw/agent/framelease/decisions.jsonl'], C.sha256_file(dec))
            # a changed development dataset (the input of stage dataset): every stage
            man = C.read_json(dev / 'manifest.json')
            write_json(dev / 'manifest.json', {**man, 'note': 'changed'})
            rc, _, err = run_main(*argv)
            self.assertEqual(rc, 1, err)
            self.assertRegex(err, r'dataset: record .* inconsistent: input .*manifest.json: sha256')
            rc, stdout, err = run_main(*argv, '--redo')
            self.assertEqual((rc, stdout.count('[skip]'), stdout.count('[run ]')), (0, 0, N_STAGES), err)
            self.assertEqual({f: C.read_json(out / f'qnet_{f}.json')['name'] for f in P.FAMILIES}, names)
            # a changed intermediate output: its stage and every later one
            p = out / 'distill_bandit.json'
            p.write_bytes(p.read_bytes() + b' ')
            rc, _, err = run_main(*argv)
            self.assertEqual(rc, 1, err)
            self.assertRegex(err, 'distill_bandit: record .* inconsistent: output <out>/distill_bandit.json')
            rc, stdout, err = run_main(*argv, '--redo')
            i = P.stage_names().index('distill_bandit')
            self.assertEqual((rc, stdout.count('[skip]'), stdout.count('[run ]')), (0, i, N_STAGES - i), err)
            self.assertEqual(run_main('status', '--out', str(out))[0], 0)


class PBothMetricsTest(unittest.TestCase):
    """Sec. 5.8: the P_both of the dataset proofs equals metrics_v4.decision_metrics (the P_both of every table) over
    the kappa-1.0 shield runs; a decision log with a row the dataset does not have stops stage p_both (report written,
    no new record)."""

    def test_p_both_agrees_with_metrics_v4(self):
        from framelease_v4.arms import metrics_v4 as M
        with tempfile.TemporaryDirectory() as tmp:
            dev = Path(tmp) / 'devds'                       # the development dataset, one v3 run read from a copy
            shutil.copytree(DEV_DATASET, dev)
            eps = C.read_json(dev / 'episodes.json')
            k = next(i for i, e in enumerate(eps) if e['kind'] == 'v3')
            run = Path(tmp) / 'run'
            for n in LOG_NAMES:
                (run / n).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(Path(eps[k]['run_dir']) / n, run / n)
            eps[k]['run_dir'] = str(run)
            write_json(dev / 'episodes.json', eps)
            out = Path(tmp) / 'out'
            argv = ['run', '--out', str(out), '--stop-after', 'p_both', *dev_args(dev)]
            rc, _, err = run_main(*argv)
            self.assertEqual(rc, 0, err)
            pb = C.read_json(out / 'p_both.json')
            logs = [Path(e['run_dir']) / 'raw/agent/framelease/decisions.jsonl' for e in eps
                    if e['kind'] == 'v3' and e['kappa'] == 1.0]
            dms = [M.decision_metrics(M.read_jsonl(f)) for f in logs]
            counts = (sum(d['shield_epochs'] for d in dms), sum(round(d['p_both'] * d['shield_epochs']) for d in dms))
            self.assertEqual(counts, (pb['decision_epochs'], pb['choice_epochs']))
            m4 = pb['metrics_v4']
            self.assertEqual((m4['shield_epochs'], m4['choice_epochs'], m4['agrees'], m4['p_both']),
                             (*counts, True, pb['p_both']))
            self.assertEqual(m4['logs'], {P.rel(f): C.sha256_file(f) for f in logs})
            dec = run / 'raw/agent/framelease/decisions.jsonl'
            self.assertEqual(records(out)['p_both']['inputs'][P.rel(dec)], C.sha256_file(dec))
            self.assertEqual(records(out)['p_both']['result']['metrics_v4_p_both'], pb['p_both'])
            # a decision row the dataset does not have (the last row twice)
            rows = dec.read_text().splitlines()
            dec.write_text('\n'.join(rows + [rows[-1]]) + '\n')
            rc, _, err = run_main(*argv)
            self.assertEqual(rc, 1, err)
            self.assertRegex(err, r'p_both: record .* inconsistent: input .*decisions.jsonl: sha256')
            rc, _, err = run_main(*argv, '--redo')
            self.assertEqual(rc, 1, err)
            self.assertRegex(err, r'p_both: the dataset counts \d+ / \d+ differ from metrics_v4.decision_metrics')
            m4 = C.read_json(out / 'p_both.json')['metrics_v4']
            self.assertEqual((m4['agrees'], m4['shield_epochs']), (False, counts[0] + 1))
            self.assertIn('p_both', P.status(out, log=quiet)['inconsistent'])


class ProductionCliTest(unittest.TestCase):
    """The production command line (registered parameters) up to p_both on a synthetic P2 manifest over P2 copies of
    the four v3 pilot runs. The tuning freeze passes the real P2 gate (p2_jobs.load_freeze) against a synthetic
    PROTOCOL.md and seal (test_p2_jobs.Env): p3_rl.load_tuning_freeze is patched only to read those instead of the
    registered ones, and p3_rl.p2_plan to the block of the four pilot pairs (plus self.extra) under the temporary
    root."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.E = T2J.Env(self.tmp / 'env')
        self.fr = self.E.freeze()
        self.runs = p2_runs(self.tmp, self.fr)
        self.extra = []
        real = P.load_tuning_freeze
        for patch in (mock.patch.object(P, 'load_tuning_freeze',
                                        lambda path: real(path, self.E.protocol, seal=self.E.seal)),
                      mock.patch.object(P, 'p2_plan', lambda freeze: pilot_plan(freeze, self.tmp, self.extra))):
            patch.start()
            self.addCleanup(patch.stop)
        self.out = self.tmp / 'out'

    def manifest(self, edit=None):
        doc = pilot_manifest(self.fr, runs=self.runs)
        if edit is not None:
            edit(doc)
        return write_json(self.tmp / 'manifest.json', doc)

    def run_p3(self, manifest, *extra):
        return run_main('run', '--selection', str(self.E.sel), '--manifest', str(manifest), '--out', str(self.out),
                        '--stop-after', 'p_both', *extra)

    def test_refusals_write_nothing(self):
        test_route = sorted(C.test_route_ids())[0]
        miss = [(MISSING_ROUTE, MISSING_KAPPA)]
        pilot = pilot_episodes()[3]
        cases = [
            ('test route', lambda d: d['episodes'][0].update(route_id=test_route), [], 1,
             'PermissionError: .*held-out test route'),
            ('source log', lambda d: d['episodes'][1]['source_logs_sha256'].update({'config.json': '0' * 64}), [], 1,
             'ValueError: .*config.json sha256 [0-9a-f]{64} != manifest 0{64}'),
            ('unhashed log', lambda d: d['episodes'][2]['source_logs_sha256'].pop('raw/agent/metric_info.json'), [],
             1, 'no sha256 of raw/agent/metric_info.json'),
            ('missing episodes', lambda d: with_missing(d, [missing_job(self.fr)]), miss, 4,
             r'STOP .*1 missing, 0 not listed.*--missing-episodes proceed'),
            ('a registered run not listed', lambda d: None, miss, 4,
             r'STOP .*4 episodes, 0 missing, 1 not listed, 5 registered runs.*--missing-episodes proceed'),
            ('another freeze', lambda d: d['tuning_freeze'].update(sha256='a' * 64), [], 1,
             'ValueError: .*tuning freeze'),
            ('a run outside the P2 output directory',
             lambda d: d['episodes'][3].update(run_dir=pilot['run_dir'], source_logs_sha256={
                 n: C.sha256_file(Path(pilot['run_dir']) / n) for n in LOG_NAMES}), [], 1,
             'ValueError: .*is not inside .*rl_data/k1.0, the P2 output directory of kappa 1.0'),
            ('another job id', lambda d: d['episodes'][0].update(job='syn0'), [], 1, 'ValueError: .*syn0: job id'),
        ]
        for what, edit, extra, code, pattern in cases:
            self.extra = extra
            rc, _, err = self.run_p3(self.manifest(edit))
            self.assertEqual(rc, code, (what, err))
            self.assertRegex(err, '(?s)' + pattern)
            self.assertFalse(self.out.exists(), what)
        self.extra = []
        rc, stdout, err = self.run_p3(self.manifest())
        self.assertEqual((rc, stdout.count('[run ]')), (0, 2), err)
        self.assertEqual({r['mode'] for r in records(self.out).values()}, {'production'})
        self.E.write_protocol(T2J.protocol_text(''))                      # selection.json no longer cited
        out, self.out = self.out, self.tmp / 'out2'
        rc, _, err = self.run_p3(self.manifest())
        self.assertEqual(rc, 1, err)
        self.assertRegex(err, 'PermissionError: .*not cited in PROTOCOL.md Sec. 13.2')
        self.assertFalse(self.out.exists())
        self.assertEqual(len(records(out)), 2)

    def test_a_changed_manifest_and_missing_episodes(self):
        path = self.manifest()
        rc, stdout, err = self.run_p3(path)
        self.assertEqual((rc, stdout.count('[run ]')), (0, 2), err)
        rec = records(self.out)['dataset']
        self.assertEqual((rec['inputs'][P.rel(path)], rec['params']['tuning_freeze']), (C.sha256_file(path),
                                                                                         self.fr['path']))
        rc, stdout, err = self.run_p3(path)
        self.assertEqual((rc, stdout.count('[skip]')), (0, 2), err)
        # the manifest rewritten: its sha256 differs from the dataset record's, the driver stops until --redo
        write_json(path, {**C.read_json(path), 'note': 'rewritten'})
        rc, _, err = self.run_p3(path)
        self.assertEqual(rc, 1, err)
        self.assertRegex(err, r'dataset: record .* inconsistent: input .*manifest.json: sha256')
        rc, stdout, err = self.run_p3(path, '--redo')
        self.assertEqual((rc, stdout.count('[run ]')), (0, 2), err)
        # (c) missing episodes: exit 4 until --missing-episodes proceed, which is recorded and needed on resume
        self.extra = [(MISSING_ROUTE, MISSING_KAPPA)]
        job = missing_job(self.fr)['job']
        path = self.manifest(lambda d: with_missing(d, [missing_job(self.fr)]))
        rc, _, err = self.run_p3(path, '--redo')
        self.assertEqual(rc, 4, err)
        self.assertIn(f'4 episodes, 1 missing, 0 not listed, 5 registered runs: {job} (timeout)', err)
        rc, stdout, err = self.run_p3(path, '--redo', '--missing-episodes', 'proceed')
        self.assertEqual((rc, stdout.count('[run ]')), (0, 2), err)
        (dv,) = records(self.out)['dataset']['deviations']
        self.assertEqual((dv['case'], dv['option'], dv['note'], dv['missing'][0]['job']),
                         ('missing_episodes', 'proceed', P.RECORD_NOTE, job))
        self.assertEqual(records(self.out)['dataset']['result']['n_missing'], 1)
        self.assertEqual(self.run_p3(path)[0], 4)
        rc, stdout, err = self.run_p3(path, '--missing-episodes', 'proceed')
        self.assertEqual((rc, stdout.count('[skip]')), (0, 2), err)


class GuardTest(unittest.TestCase):
    def test_the_default_output_directory_is_guarded_while_the_tests_run(self):
        self.assertEqual(REAL_DEFAULT_OUT, P.ROOT / 'outputs' / 'framelease_v4' / 'rl_freeze')
        for p in (REAL_DEFAULT_OUT / 'rl_freeze.json', REAL_DEFAULT_OUT / 'stages' / 'dataset.json'):
            with self.assertRaisesRegex(PermissionError, 'the tests never write'):
                C._check_writable(p)                                             # checks, writes nothing
        self.assertEqual(tree_state(REAL_DEFAULT_OUT), _MODULE['state'])
        with self.assertRaises(PermissionError):
            P.Ctx(REAL_DEFAULT_OUT, 'development', 10, default_options())

    def test_default_output_directory_and_development_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_default = Path(tmp) / 'rl_freeze'
            under_pytest = {'PYTEST_CURRENT_TEST': os.environ.get('PYTEST_CURRENT_TEST', 'test_p3_rl (unittest)')}
            with mock.patch.object(P, 'DEFAULT_OUT', fake_default), mock.patch.dict(os.environ, under_pytest):
                rc, _, err = run_main('run', '--out', str(fake_default / 'x'), *DEV_ARGS)
                self.assertEqual(rc, 1, err)
                self.assertIn('development runs never write', err)
                rc, _, err = run_main('run', '--out', str(fake_default))
                self.assertEqual(rc, 1, err)
                self.assertIn('tests never write', err)
                for mode in ('development', 'production'):
                    with self.assertRaises(PermissionError):
                        P.Ctx(fake_default, mode, 10, default_options())
            self.assertFalse(fake_default.exists())
            with self.assertRaises(ValueError):
                P.Ctx(Path(tmp) / 'o', 'other', 10, default_options())
            rc, _, err = run_main('run', '--out', str(Path(tmp) / 'o'), '--smoke', '--n-folds', '2')
            self.assertEqual(rc, 1, err)
            self.assertIn('--smoke, --n-folds: development options need --dev-dataset', err)
            rc, _, err = run_main('run', '--out', str(Path(tmp) / 'o'), *BENCH_ARGS)
            self.assertEqual(rc, 1, err)
            self.assertIn('--bench-n: development options need --dev-dataset', err)
            rc, _, err = run_main('run', '--out', str(Path(tmp) / 'o'), '--dev-dataset', str(DEV_DATASET))
            self.assertEqual(rc, 1, err)
            self.assertIn('needs --dev-d-star', err)
            self.assertFalse((Path(tmp) / 'o').exists())
            with self.assertRaises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()):
                    P.main(['run', '--no-selectable', 'guess'])


PILOT_DECISIONS = [Path(e['run_dir']) / 'raw/agent/framelease/decisions.jsonl' for e in pilot_episodes()]


def write_net(path, refresh_bias=1.0, supported=(True, True), d_det=10):
    """An exported 16-input network whose Q(REFRESH) - Q(REFINE) = refresh_bias everywhere (zero weights)."""
    mlp = P.adet_mlp(16)
    mlp['b'][-1] = np.array([0.0, float(refresh_bias)])
    spec = P.TR.export_qnet(mlp, P.TR.Candidate('fqi', d_det=d_det), list(supported),
                            policy_budget_s=P.POLICY_BUDGET_S)
    return C.atomic_json(Path(path), spec).resolve(), spec['name']


def n_choice_rows():
    return sum(1 for f in PILOT_DECISIONS for r in C.read_jsonl(f) if len(r['feasible']) == 2)


def n_slack_rows(budget_s=P.POLICY_BUDGET_S):
    """Logged choice rows whose shield margin of either action is below B_pi: the slack bypass of qnet.QUtility (no
    network call; Sec. 5.7). Read from the logs, independent of the replay and of wall time."""
    return sum(1 for f in PILOT_DECISIONS for r in C.read_jsonl(f) if len(r['feasible']) == 2 and
               any(m is not None and m < budget_s
                   for m in ((r.get('features') or {}).get(k) for k in ('refine_margin_s', 'refresh_margin_s'))))


class DeployCheckTest(unittest.TestCase):
    """GAP_AUDIT P3-2 on synthetic networks replayed over the four logged pilot runs, and a failed check."""

    def test_a_deviating_network_and_head_support(self):
        """A network with both heads and Q(REFRESH) > Q(REFINE) everywhere deviates from a_det^{10} (REFINE at every
        logged choice state) wherever its answer is used. The pinned QUtility times each call against B_pi: on a
        loaded machine a call over B_pi is an overrun bypass (answer discarded, a_det^{d*}) and more than 5% overruns
        disable the instance (every later choice a_det^{d*}; Sec. 5.7). The counts are therefore checked through the
        instance's bypass counters, whatever their values: every choice row is a slack bypass, a disabled bypass or a
        network call; every network call that is not an overrun deviates (the AMEND review saw 309 deviations of 310
        under load), and at least one does (one call of the 310 within B_pi)."""
        with tempfile.TemporaryDirectory() as tmp:
            path, name = write_net(Path(tmp) / 'refresh.json', 1.0)
            rep = P.replay_network(name, path, PILOT_DECISIONS, 10)
            n = n_choice_rows()
            self.assertEqual((rep['runs'], rep['choice_rows'], rep['problems']), (4, n, {}))
            b = rep['bypass']
            self.assertEqual(b['nonfinite'], 0)
            n_slack = n_slack_rows()                       # a disabled instance bypasses before the slack check
            self.assertTrue(b['slack'] <= n_slack <= b['slack'] + b['disabled'], (b, n_slack))
            self.assertEqual(rep['network_calls'], n - b['slack'] - b['disabled'])
            self.assertEqual(rep['deviations'], rep['network_calls'] - b['overrun'])   # REFRESH wherever it is used
            self.assertGreater(rep['deviations'], 0)
            self.assertEqual(rep['actions_at_choice'], {'REFINE': n - rep['deviations'], 'REFRESH': rep['deviations']})
            path2, name2 = write_net(Path(tmp) / 'one_head.json', 1.0, supported=(True, False))
            rep2 = P.replay_network(name2, path2, PILOT_DECISIONS, 10)
            self.assertEqual((rep2['deviations'], rep2['problems']), (0, {}))      # never deviates with one head

    def test_another_a_det_depth_and_an_answer_outside_a_feas(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, name = write_net(Path(tmp) / 'd4.json', 0.0, d_det=4)
            rep = P.replay_network(name, path, PILOT_DECISIONS, 10)
            self.assertEqual(rep['problems']['depth_not_d_star'], 4)
            path, name = write_net(Path(tmp) / 'd10.json', 0.0)
            with mock.patch.object(Q.QUtility, 'select', lambda self, features, feasible: 'WAIT'):
                rep = P.replay_network(name, path, PILOT_DECISIONS, 10)
            n = n_choice_rows()
            self.assertEqual((rep['problems']['left_feasible_set'], rep['deviations']), (n, n))
            self.assertEqual(rep['actions_at_choice'], {'REFINE': n, 'REFRESH': 0})   # decide's own replacement

    def test_absolute_network_path_and_the_pin(self):
        before = os.environ.get(Q.ENV_QNET)
        with tempfile.TemporaryDirectory() as tmp:
            path, name = write_net(Path(tmp) / 'a.json', 1.0)
            other, _ = write_net(Path(tmp) / 'b.json', 2.0)
            with self.assertRaisesRegex(P.StageError, 'absolute path .finding QNET-1'):
                P.replay_network(name, Path('rel') / 'a.json', PILOT_DECISIONS, 10)
            self.assertTrue(P.pin_refused(name, other))
            self.assertFalse(P.pin_refused(name, path))
            with self.assertRaises(P.StageError):
                P.pin_refused(name, Path('b.json'))
        self.assertEqual(os.environ.get(Q.ENV_QNET), before)

    def test_a_failed_check_writes_the_report_but_no_record(self):
        def slow(spec, rows, n, warm):
            return {'featurize_forward': {'n': n, 'p50_us': 150.0, 'p90_us': 200.0, 'p99_us': 250.0, 'max_us': 300.0}}

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            rc, _, err = run_main('run', '--out', str(out), '--stop-after', 'export_fqi_nolease', *DEV_ARGS)
            self.assertEqual(rc, 0, err)
            with mock.patch.object(P, 'bench_network', slow):
                rc, _, err = run_main('run', '--out', str(out), *DEV_ARGS, *BENCH_ARGS)
            self.assertEqual(rc, 1, err)
            self.assertIn('deploy_check: 3 failed check(s)', err)
            self.assertIn('featurize_forward p99 250.0 us > B_pi 100 us', err)
            doc = C.read_json(out / 'deploy_check.json')
            self.assertFalse(doc['ok'])
            self.assertEqual(len(doc['failures']), 3)
            self.assertNotIn('deploy_check', records(out))
            rc, stdout, err = run_main('run', '--out', str(out), *DEV_ARGS, *BENCH_ARGS)   # the check is repeated
            self.assertEqual(rc, 0, err)
            self.assertIn('[run ] deploy_check', stdout)
            self.assertTrue(C.read_json(out / 'deploy_check.json')['ok'])


class ProductionFreezeTest(unittest.TestCase):
    """PROTOCOL Sec. 5.9 / GAP_AUDIT P3-4: the production chain on the synthetic manifest over P2 copies of the four v3
    pilot runs with one missing job under --missing-episodes proceed (smoke grid, 2 folds; Ctx built directly as in
    ProductionStagesTest, PROTOCOL.md synthetic), the RL freeze, its completeness, its reader load_rl_freeze, and the
    registered output directory once the freeze is cited."""

    @classmethod
    def setUpClass(cls):
        from framelease_v4.rl.smoke import SMOKE_FQE
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)
        cls.E = T2J.Env(cls.tmp / 'env')
        cls.fr = cls.E.freeze()
        cls.missing = [missing_job(cls.fr)]
        doc = with_missing(pilot_manifest(cls.fr, runs=p2_runs(cls.tmp, cls.fr)), cls.missing)
        cls.man = P.load_p2_manifest(write_json(cls.tmp / 'manifest.json', doc), cls.fr, 'proceed',
                                     protocol=cls.E.protocol,
                                     plan=pilot_plan(cls.fr, cls.tmp, [(MISSING_ROUTE, MISSING_KAPPA)]))
        cls.out = cls.tmp / 'out'
        cls.ctx = P.Ctx(cls.out, 'production', cls.fr['d'], default_options(missing_episodes='proceed'),
                        manifest=cls.man, freeze=cls.fr, grid_kind='smoke', n_folds=2, fqe_cfg=SMOKE_FQE, n_boot=500,
                        bench_n=300, bench_warm=100, log=quiet, protocol=cls.E.protocol)
        cls.done = P.drive(cls.ctx, P.stage_list())
        cls.path = cls.out / 'rl_freeze.json'

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_the_freeze_record(self):
        out, man, fr, path = self.out, self.man, self.fr, self.path
        self.assertEqual([how for _, how, _ in self.done], ['run'] * N_STAGES)
        self.assertFalse((out / 'rl_freeze_dev.json').exists())
        rec = records(out)['freeze']
        self.assertEqual(rec['outputs'], {'<out>/rl_freeze.json': C.sha256_file(path)})
        self.assertEqual(rec['inputs'][man['path']], man['sha256'])
        self.assertEqual(rec['inputs'][fr['path']], fr['sha256'])
        doc = C.read_json(path)
        self.assertEqual((doc['schema'], doc['variant'], doc['mode'], doc['frozen'], doc['d_star'], doc['dev_dataset']),
                         (P.FREEZE_SCHEMA, 'FULL', 'production', True, 10, None))
        self.assertEqual({k: doc['tuning_freeze'][k] for k in ('path', 'sha256', 'd', 'cited_lines')},
                         {'path': fr['path'], 'sha256': fr['sha256'], 'd': 10, 'cited_lines': fr['cited_lines']})
        self.assertEqual(doc['tuning_freeze']['L_star'], {'label': fr['L']['label'], 'sha256': fr['L']['sha256']})
        self.assertEqual(doc['p2_manifest'], {'path': man['path'], 'sha256': man['sha256'], 'cited_lines': []})
        self.assertEqual((doc['files'][man['path']], doc['files'][fr['path']]), (man['sha256'], fr['sha256']))
        for f in P.FAMILIES:
            self.assertEqual(doc['job_lines'][P.ARM_OF[f]], {
                'utility': C.read_json(out / f'qnet_{f}.json')['name'],
                Q.ENV_QNET: str((out / f'qnet_{f}.json').resolve()),
                'qnet_file_sha256': C.sha256_file(out / f'qnet_{f}.json')})
            self.assertTrue(Path(doc['job_lines'][P.ARM_OF[f]][Q.ENV_QNET]).is_absolute())      # finding QNET-1
        # the open case (c) used by this run: in the dataset record and in the freeze
        self.assertEqual([(d['case'], d['option'], d['stage']) for d in doc['deviations']],
                         [('missing_episodes', 'proceed', 'dataset')])
        self.assertEqual((doc['dataset']['n_missing'], doc['dataset']['n_registered'], doc['dataset']['missing']),
                         (1, 5, self.missing))
        self.assertEqual([s['stage'] for s in doc['stage_chain']], P.stage_names()[:-1])

    def test_the_freeze_is_complete(self):
        """Every item of PROTOCOL Sec. 5.9 and GAP_AUDIT P3-4 is in the record, with the sha256 of the files now."""
        out, path = self.out, self.path
        doc = C.read_json(path)
        # Sec. 5.9: the dataset manifest: the episode list and the sha256 of every source log the dataset reads
        eps = self.man['doc']['episodes']
        self.assertEqual([(e['job'], e['route_id'], e['kappa'], e['utility'], e['run_dir'])
                          for e in doc['dataset']['episodes']],
                         [(e['job'], e['route_id'], e['kappa'], e['utility'], e['run_dir']) for e in eps])
        self.assertEqual(doc['dataset']['n_episodes'], len(eps))
        for e in doc['dataset']['episodes']:
            rd = P.abs_path(e['run_dir'])
            self.assertEqual({n for n in P.SOURCE_LOGS if (rd / n).is_file()}, set(P.SOURCE_LOGS))
            self.assertLessEqual(set(P.SOURCE_LOGS), set(e['source_logs_sha256']))
            for n, h in e['source_logs_sha256'].items():
                self.assertEqual(C.sha256_file(rd / n), h, (e['job'], n))
        for n in ('manifest.json', 'episodes.json', 'transitions.npz', 'epochs.npz'):
            self.assertEqual(doc['dataset']['files'][P.rel(out / 'dataset' / n)], C.sha256_file(out / 'dataset' / n))
        # Sec. 5.9: the three selection reports; P3-4: the FQE estimate and 90% CI of the selected candidate
        for f in P.FAMILIES:
            fam = doc['families'][f]
            sp = out / f'select_{f}.json'
            sel = C.read_json(sp)
            self.assertEqual(fam['selection_report'], {'path': P.rel(sp), 'sha256': C.sha256_file(sp)})
            self.assertEqual(doc['files'][P.rel(sp)], C.sha256_file(sp))
            self.assertIsNotNone(sel['selected'])
            boot = sel['estimate']['bootstrap']
            self.assertEqual((fam['selected'], fam['estimate']['mean_delta'], fam['estimate']['ci90'],
                              fam['estimate']['coverage'], fam['estimate']['n_boot']),
                             (sel['selected'], sel['estimate']['mean_delta'], [boot['lo'], boot['hi']], 0.9, 500))
            self.assertLessEqual(boot['lo'], boot['hi'])
            self.assertEqual(len(fam['candidates']), len(sel['candidates']))
            # Sec. 5.9: the deployed network with its sha256 and name v4_qnet_<sha12>; P3-4: and its family
            qp = out / f'qnet_{f}.json'
            spec = Q.load_spec(qp)
            net = fam['network']
            self.assertEqual((net['name'], net['weights_sha256'], net['file_sha256'], net['family'], net['arm'],
                              net['abs_path'], net['a_det_depth']),
                             (f'v4_qnet_{spec["weights_sha256"][:12]}', spec['weights_sha256'], C.sha256_file(qp), f,
                              P.ARM_OF[f], str(qp.resolve()), 10))
            self.assertEqual(doc['files'][net['path']], C.sha256_file(qp))
            # P3-4: the distillation agreement (of the deployed network)
            dis = C.read_json(out / f'distill_{f}.json')
            self.assertEqual((fam['distillation']['deployed_agreement'], fam['distillation']['ok']),
                             (dis['agreement'], dis['ok']))
            self.assertTrue(fam['deploy_check']['ok'])
        # Sec. 5.9: the sha256 of every framelease_v4/rl source (every file under it, RL_PROTOCOL.md of Sec. 5.5 and
        # the tests included), of this driver and of the P2 gate modules
        rl = ROOT / 'framelease_v4' / 'rl'
        files = {f'rl/{f.relative_to(rl).as_posix()}' for f in rl.rglob('*')
                 if f.is_file() and '__pycache__' not in f.parts}
        self.assertEqual(set(doc['code_sha256']), {'p3_rl.py', 'protocol/p2_jobs.py', 'protocol/p2_check.py'} | files)
        self.assertLessEqual({'rl/RL_PROTOCOL.md', 'rl/README.md', 'rl/qnet.py', 'rl/tests/test_learning.py'},
                             set(doc['code_sha256']))
        for k, h in doc['code_sha256'].items():
            self.assertEqual(h, C.sha256_file(ROOT / 'framelease_v4' / ('protocol/p3_rl.py' if k == 'p3_rl.py'
                                                                        else k)), k)
        # the notes for the Sec. 13 test-freeze entry and the job-line rule
        self.assertEqual((doc['sec13_notes']['items'], doc['job_lines_rule'], doc['shared_names']),
                         (list(P.SEC13_NOTES), P.JOB_LINES_RULE, {}))
        # P3-4: the P_both label
        pb = C.read_json(out / 'p_both.json')
        self.assertEqual((doc['p_both']['label'], doc['p_both']['p_both'], doc['p_both']['metrics_v4_p_both']),
                         (pb['label'], pb['p_both'], pb['metrics_v4']['p_both']))
        self.assertEqual(pb['metrics_v4']['p_both'], pb['p_both'])
        # every file the record names is in its sha256 list, with the sha256 it has now
        named = [doc['reward_identity'], doc['p_both'], doc['deploy_check']] + [
            r for v in doc['families'].values() for r in (v['selection_report'], v['refit'], v['distillation'],
                                                          v['refit']['model'])]
        for r in named:
            self.assertEqual(doc['files'][r['path']], r['sha256'], r['path'])
        for k, h in doc['files'].items():
            self.assertEqual(C.sha256_file(P.abs_path(k)), h, k)

    def test_the_reader_and_the_registered_directory(self):
        out, E, path, tmp = self.out, self.E, self.path, self.tmp
        got = P.load_rl_freeze(path, protocol=E.protocol)
        self.assertEqual((got['sha256'], got['cited_lines']), (C.sha256_file(path), []))
        with self.assertRaisesRegex(PermissionError, 'not cited in PROTOCOL Sec. 13.2'):
            P.load_rl_freeze(path, require_cited=True, protocol=E.protocol)
        self.assertEqual(P.frozen_citations(out, E.protocol), [])
        entry = f'\n* **RL freeze** (sha256 `{got["sha256"]}`)'
        E.write_protocol(T2J.protocol_text(T2J.freeze_entry(E.sha) + entry))
        self.assertEqual(len(P.load_rl_freeze(path, require_cited=True, protocol=E.protocol)['cited_lines']), 1)
        # cited: the directory is registered: consistent stages skip, nothing is recomputed
        self.assertEqual(len(P.frozen_citations(out, E.protocol)), 1)
        self.assertEqual([how for _, how, _ in P.drive(self.ctx, P.stage_list())], ['skip'] * N_STAGES)
        code = P.code_sha256()
        with mock.patch.object(P, 'code_sha256', lambda: {**code, 'p3_rl.py': '0' * 64}):      # a code change
            with self.assertRaisesRegex(P.StageError, 'dataset: .*parameters differ'):
                P.drive(self.ctx, P.stage_list())
            with self.assertRaisesRegex(PermissionError, 'dataset: .*rl_freeze.json is cited in PROTOCOL Sec. 13.2'):
                P.drive(self.ctx, P.stage_list(), redo=True)
        self.assertEqual(C.sha256_file(path), got['sha256'])

        def refused(edit, pattern, exc=ValueError):
            bad = json.loads(path.read_text())
            edit(bad)
            with self.assertRaisesRegex(exc, pattern):
                P.load_rl_freeze(write_json(tmp / 'bad.json', bad), protocol=E.protocol)

        refused(lambda d: d.update(schema='x'), 'not an RL freeze')
        refused(lambda d: d.update(frozen=False), 'never a freeze', PermissionError)
        refused(lambda d: d['dataset']['episodes'][0]['source_logs_sha256'].update({'config.json': '0' * 64}),
                'config.json: sha256')
        refused(lambda d: d['job_lines']['fl_full'].update({Q.ENV_QNET: 'qnet_fqi.json'}), 'fqi: job line')
        refused(lambda d: d['families']['bandit']['network'].update(a_det_depth=4), 'bandit: network a_det_depth')
        original = (out / 'qnet_bandit.json').read_bytes()
        try:
            C.atomic_json(out / 'qnet_bandit.json', C.read_json(out / 'qnet_fqi.json'))   # another valid network
            with self.assertRaisesRegex(ValueError, 'qnet_bandit.json: sha256'):
                P.load_rl_freeze(path, protocol=E.protocol)
        finally:
            (out / 'qnet_bandit.json').write_bytes(original)
        moved = tmp / 'moved'
        out.rename(moved)
        try:
            with self.assertRaisesRegex(ValueError, 'sha256 None'):
                P.load_rl_freeze(moved / 'rl_freeze.json', protocol=E.protocol)
        finally:
            moved.rename(out)
        self.assertEqual(P.load_rl_freeze(path, require_cited=True, protocol=E.protocol)['sha256'], got['sha256'])


class CalibrateTest(unittest.TestCase):
    """GAP_AUDIT P3-5: the parts of the wall-time model and a small calibrate run (output in a temporary directory)."""

    def test_list_schedule_and_the_worker_model(self):
        self.assertEqual(P.list_schedule([3, 3, 2, 2], [1.0, 1.0]), 5.0)
        self.assertEqual(P.list_schedule([4, 1], [2.0, 1.0]), 2.0)              # a tie goes to the faster worker
        self.assertEqual(P.list_schedule([5, 1, 1, 1], [1.0]), 8.0)
        topo = [{'cpu': i, 'core': f'0:{i // 2}', 'max_khz': 4900000} for i in range(4)] + \
               [{'cpu': 4 + j, 'core': f'0:{10 + j}', 'max_khz': 3700000} for j in range(2)]
        r = 4900 / 3700
        sp = P.worker_speeds
        self.assertEqual(sp(1, topo, 3700000), [r])
        self.assertEqual(sp(4, topo, 3700000), [r, r, 1.0, 1.0])
        self.assertEqual(sp(6, topo, 3700000), [1.0, 1.0] + [r / 2] * 4)
        self.assertEqual(sp(5, topo, 3700000, smt_share=0.6), [r, 1.0, 1.0, 0.6 * r, 0.6 * r])
        self.assertEqual(sp(1, topo, 3700000, fast_core_ipc=1.2), [1.2 * r])
        self.assertEqual(sp(3, [], 1), [1.0] * 3)
        topo_now = P.cpu_topology()
        if topo_now:
            self.assertEqual(len(P.worker_speeds(len(topo_now), topo_now, topo_now[0]['max_khz'])), len(topo_now))

    def test_cost_law_and_the_synthetic_dataset(self):
        fit = P.cost_fit([(n, 0.5 + 1e-4 * n * math.log(n)) for n in (500, 1000, 4000)])
        self.assertAlmostEqual(fit['c'], 0.5, places=9)
        self.assertAlmostEqual(fit['a'], 1e-4, places=12)
        self.assertLess(fit['rel_residual'], 1e-9)
        self.assertAlmostEqual(P._cost(fit, 9000), 0.5 + 0.9 * math.log(9000), places=9)
        with self.assertRaisesRegex(ValueError, 'span less than a factor of 1.5'):
            P.cost_fit([(100, 1.0), (120, 1.1)])
        lengths = P.calibration_lengths(9)
        self.assertEqual(lengths, P.calibration_lengths(9))
        self.assertTrue(all(20 <= n <= 150 for n in lengths) and len(lengths) == 9)
        pool = P.train_lengths(DEV_DATASET)
        self.assertEqual(pool, [e['n_choice'] for e in C.read_json(DEV_DATASET / 'episodes.json')
                                if e['split'] == 'train' and e['n_choice'] > 0])
        self.assertTrue(set(P.calibration_lengths(7, lengths_from=DEV_DATASET)) <= set(pool))
        ds = P.synthetic_dataset([20, 30, 150, 25], 10)
        self.assertEqual((ds.n, [e['n_choice'] for e in ds.episodes]), (225, [20, 30, 150, 25]))
        self.assertEqual([(e['route_id'], e['kappa']) for e in ds.episodes],
                         [('cal0', 1.0), ('cal0', 1.5), ('cal0', 2.0), ('cal1', 1.0)])
        depth = ds.X[:, P.F.NAMES.index('depth')]
        self.assertTrue(depth.min() >= 1 and depth.max() <= 9)
        self.assertTrue(np.all(ds.MU == np.where(ds.A == ds.BASE, 0.85, 0.15)))
        self.assertEqual((int(ds.DONE.sum()), int(ds.FIRST.sum()), ds.train_episode_ids()), (4, 4, [0, 1, 2, 3]))
        self.assertTrue({'GW0.5', 'GW1', 'GW2', 'XE', 'XEN', 'G'} <= set(ds.arrays))
        explored = float(np.mean(ds.A != ds.BASE))
        self.assertTrue(0.05 < explored < 0.3, explored)                       # eps 0.3: 0.15 expected

    def test_output_guard(self):
        with self.assertRaises(PermissionError):
            P.calibration_out(P.DEFAULT_OUT / 'calibration.json')
        with self.assertRaises(PermissionError):
            P.calibration_out(ROOT / 'outputs' / 'framelease_v4' / 'tuning' / 'calibration.json')
        allowed = ROOT / 'outputs' / 'framelease_v4' / 'build' / 'P3RL' / 'never_written.json'
        self.assertEqual(P.calibration_out(allowed), allowed.resolve())
        self.assertFalse(allowed.exists())
        target = ROOT / 'outputs' / 'framelease_v4' / 'tuning' / 'cal_test.json'
        rc, _, err = run_main('calibrate', '--sizes', '4,9', '--out', str(target))
        self.assertEqual(rc, 1, err)
        self.assertFalse(target.exists())
        with tempfile.TemporaryDirectory() as tmp:
            rc, _, err = run_main('calibrate', '--sizes', '4', '--out', str(Path(tmp) / 'c.json'))
            self.assertEqual(rc, 1, err)
            self.assertIn('at least two probe sizes', err)

    def test_a_small_calibration(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'cal.json'
            rc, stdout, err = run_main('calibrate', '--sizes', '4,9', '--threads', '6', '--out', str(out))
            self.assertEqual(rc, 0, err)
            self.assertIn('calibrate: n_jobs', stdout)
            doc = C.read_json(out)
            self.assertEqual((doc['schema'], doc['kind']),
                             (P.CALIBRATION_SCHEMA, 'development (scaled-down probe sizes)'))
            self.assertEqual({k: doc['target'][k] for k in ('n_episodes', 'n_folds', 'candidates_per_family',
                                                            'tasks_per_family', 'threads')},
                             {'n_episodes': 132, 'n_folds': 5, 'candidates_per_family': 12, 'tasks_per_family': 60,
                              'threads': 6})
            self.assertEqual([p['n_episodes'] for p in doc['probe']['results']], [4, 9])
            self.assertEqual(len(doc['probe']['results'][0]['configs']), 12)          # 3 families x leaf x beta
            shapes = doc['target_shapes']
            self.assertEqual((shapes['n_episodes'], len(shapes['folds'])), (132, 5))
            self.assertEqual(sum(fo['n_eval'] for fo in shapes['folds']), shapes['n_rows'])
            for fo in shapes['folds']:
                it = fo['iterations']
                self.assertEqual(set(it), {'adet', 'dev0.1', 'dev0.3', 'dev0.5', 'worst'})
                self.assertEqual(fo['n_fit'] + fo['n_eval'], shapes['n_rows'])
                self.assertLessEqual(max(it.values()), it['worst'])
                self.assertLessEqual(it['worst'], 151)                                # 150 transitions + 1
            val = doc['validation']
            self.assertEqual(len(val['candidates']), 2)
            self.assertGreater(val['ratio_measured_to_predicted'], 0)
            self.assertEqual(doc['scale'], max(1.0, val['ratio_measured_to_predicted']))
            self.assertEqual(set(doc['prediction']), {'adet', 'dev0.1', 'dev0.3', 'dev0.5', 'worst'})
            walls = doc['prediction']['worst']['wall_s']
            self.assertEqual(sorted(walls, key=int), [str(w) for w in range(1, 7)])
            self.assertGreater(walls['1'], walls['6'])
            rec = doc['recommendation']
            self.assertTrue(1 <= rec['n_jobs'] <= 6)
            self.assertEqual(rec['worst_case_wall_s'], max(p['wall_s'][str(rec['n_jobs'])]
                                                           for p in doc['prediction'].values()))
            self.assertEqual(set(doc['refit_worst_s']), set(P.FAMILIES))


class OpenCasesTest(unittest.TestCase):
    """GAP_AUDIT Sec. 6 item 5 (a) and (b) on the development data (the selection or the distillation patched to
    produce the case), each continued to the development freeze record; (c) is in InputGateTest,
    ProductionStagesTest, ProductionCliTest and ProductionFreezeTest."""

    def finish(self, out, *option):
        """The rest of the chain (deploy_check, freeze) with the option; the freeze record (development)."""
        rc, stdout, err = run_main('run', '--out', str(out), *DEV_ARGS, *BENCH_ARGS, *option)
        self.assertEqual(rc, 0, err)
        self.assertEqual(stdout.count('[skip]'), P.stage_names().index('export_fqi') + 1)
        doc = C.read_json(out / 'rl_freeze_dev.json')
        self.assertTrue(doc['deploy_check']['ok'])
        for k, h in doc['files'].items():
            self.assertEqual(C.sha256_file(P.abs_path(k)), h, k)
        return doc

    def run_fqi(self, out, *extra):
        return run_main('run', '--out', str(out), '--stop-after', 'export_fqi', *DEV_ARGS, *extra)

    def test_a_no_selectable_candidate(self):
        real = P.O.select

        def nothing_selectable(*a, **kw):
            return {**real(*a, **kw), 'selected': None}

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            with mock.patch.object(P.O, 'select', nothing_selectable):
                rc, _, err = self.run_fqi(out)
            self.assertEqual(rc, 4, err)
            self.assertIn('STOP (open case, the user decides): refit_fqi: family fqi has no selectable candidate', err)
            self.assertEqual(sorted(records(out)), ['dataset', 'p_both', 'select_fqi'])
            self.assertTrue(records(out)['select_fqi']['result']['not_trainable'])
            rc, stdout, err = self.run_fqi(out, '--no-selectable', 'adet')       # the selection is not rerun
            self.assertEqual(rc, 0, err)
            self.assertIn('[skip] select_fqi', stdout)
            recs = records(out)
            for n in ('refit_fqi', 'export_fqi'):
                (dv,) = recs[n]['deviations']
                self.assertEqual((dv['case'], dv['option'], dv['family'], dv['note'], dv['reason']),
                                 ('no_selectable', 'adet', 'fqi', P.RECORD_NOTE, P.NOT_SELECTABLE))
            sel = C.read_json(out / 'select_fqi.json')     # every training fold fits: the held-out rule
            self.assertEqual((sel['not_trainable_reason'], sel['fit_unsupported']), (P.NOT_SELECTABLE, []))
            self.assertEqual(recs['export_fqi']['result']['note'], P.ADET_NOTE)
            spec = Q.load_spec(out / 'qnet_fqi.json')
            self.assertEqual((spec['supported'], spec['a_det']['depth'], len(spec['feature_columns'])),
                             ([False, False], 10, 16))
            self.assertTrue(spec['provenance']['not_trainable'])
            u = Q.QUtility(spec, log_to_features=False)
            for depth in range(0, 16):
                feats = {'depth': depth, 'refine_margin_s': 1.0, 'refresh_margin_s': 1.0}
                self.assertEqual(u.select(feats, ['REFINE', 'REFRESH']), 'REFINE' if depth < 10 else 'REFRESH')
            rc, _, err = self.run_fqi(out)                                         # resume without the option
            self.assertEqual(rc, 1, err)
            self.assertIn('the record used --no-selectable adet; pass it again', err)
            (out / 'refit_fqi.joblib').write_bytes(b'stale file of an earlier run')
            doc = self.finish(out, '--no-selectable', 'adet')
            fam = doc['families']['fqi']
            self.assertEqual((fam['not_trainable'], fam['selected'], fam['estimate']['mean_delta'],
                              fam['refit']['model'], fam['network']['supported']), (True, None, None, None,
                                                                                     [False, False]))
            self.assertNotIn(P.rel(out / 'refit_fqi.joblib'), doc['files'])
            self.assertEqual(doc['families']['bandit']['not_trainable'], False)
            self.assertEqual([(d['case'], d['stage']) for d in doc['deviations']],
                             [('no_selectable', 'refit_fqi'), ('no_selectable', 'export_fqi')])
            self.assertEqual(doc['deploy_check']['ok'], True)
            rep = C.read_json(out / 'deploy_check.json')['networks']['fqi']['replay']
            self.assertEqual((rep['deviations'], rep['problems']), (0, {}))     # a_det^{d*} at every choice state

    def test_a_the_a_det_head_unsupported_in_a_training_fold(self):
        """The development data log no REFRESH at a choice state; at d* = 4 the a_det^{d*} head is REFRESH from depth
        4 on, so no training fold can fit any candidate (ope.fit_support). The installed ope.select (Amendment A6)
        does not fit a candidate in such a fold: its evaluation there is unsupported, a regular unsupported evaluation
        of Sec. 5.6 rule 3, and the report is complete (every candidate, every fold). select_<f> records the family
        as not trainable with the reason taken from the fold records (each fold with its per-head sample counts) and
        lists those folds; folds without a fit are no FQE non-convergence. refit_<f> stops (open case (a), exit 4) and
        --no-selectable adet deploys the a_det^{d*}-equivalent network of every family; fl_full and fl_bandit then
        share one name, told apart by arm and file sha256. A ValueError of ope.select stops the driver (exit 1)."""
        args = ['--dev-dataset', str(DEV_DATASET), '--dev-d-star', '4', '--smoke', '--n-folds', '2', *BENCH_ARGS]
        cause = r'2 of 2 candidates \(min_support 5, a_det\^\{d\*\} needs the unsupported REFRESH head\)'
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            rc, _, err = run_main('run', '--out', str(out), *args)
            self.assertEqual(rc, 4, err)
            self.assertRegex(err, r'STOP .*refit_fqi: family fqi has no selectable candidate \(' +
                             re.escape(P.FIT_UNSUPPORTED) + rf': fold 0 with REFINE \d+ / REFRESH 0 logged samples: '
                             rf'{cause}; fold 1 with REFINE \d+ / REFRESH 0 logged samples: {cause}\)\. ')
            self.assertEqual(sorted(records(out)), ['dataset', 'p_both', 'select_fqi'])
            sel = C.read_json(out / 'select_fqi.json')
            self.assertEqual((sel['selected'], sel['not_trainable'], sel['estimate'], sel['n_folds'],
                              sel['fqe_not_converged']), (None, True, None, 2, []))
            ds = P.D.load_dataset(out / 'dataset')
            train = ds.train_episode_ids()
            grid = P.TR.grid('fqi', smoke=True, d_det=4)
            self.assertEqual([(r['label'], r['mean_delta'], r['unsupported_folds'], len(r['folds']))
                              for r in sel['candidates']], [(c.label, None, 2, 2) for c in grid])
            counts = []
            for k, ev in enumerate(sel['folds']):
                a = ds.A[ds.episode_mask(sorted(set(train) - set(ev)))]
                counts.append({'REFINE': int(np.sum(a == P.TR.REFINE)), 'REFRESH': int(np.sum(a == P.TR.REFRESH))})
                self.assertGreater(counts[k]['REFINE'], 0)
                self.assertEqual(counts[k]['REFRESH'], 0)
                for r in sel['candidates']:                  # evaluated, not fitted: no FQE, unsupported (A6)
                    f = r['folds'][k]
                    self.assertEqual((f['eval_episodes'], f['fit_episodes'], f['fqe_iterations'], f['fqe_converged'],
                                      f['unsupported_frac'], f['fit_unsupported']['ok'],
                                      f['fit_unsupported']['n_samples']),
                                     (ev, sorted(set(train) - set(ev)), 0, False, 1.0, False,
                                      [counts[k]['REFINE'], 0]))
            self.assertEqual(sel['fit_unsupported'],
                             [{'fold': k, 'n_samples': counts[k],
                               'candidates': [{'label': c.label, 'min_support': c.min_support, 'supported': ['REFINE'],
                                               'a_det_needs': ['REFINE', 'REFRESH']} for c in grid]}
                              for k in range(2)])
            self.assertEqual(sel['not_trainable_reason'], P.not_selectable_reason(sel, sel['fit_unsupported']))
            self.assertEqual(records(out)['select_fqi']['result']['fit_unsupported_folds'], [0, 1])
            rc, stdout, err = run_main('run', '--out', str(out), *args, '--no-selectable', 'adet')
            self.assertEqual(rc, 0, err)
            self.assertIn('[skip] select_fqi', stdout)
            doc = C.read_json(out / 'rl_freeze_dev.json')
            self.assertEqual([(d['case'], d['stage']) for d in doc['deviations']],
                             [('no_selectable', f'{s}_{f}') for f in P.FAMILIES for s in ('refit', 'export')])
            for d in doc['deviations']:
                fam = C.read_json(out / f'select_{d["family"]}.json')
                self.assertEqual(([e['fold'] for e in fam['fit_unsupported']], fam['fqe_not_converged']), ([0, 1], []))
                self.assertEqual(d['reason'], fam['not_trainable_reason'])
                self.assertTrue(d['reason'].startswith(P.FIT_UNSUPPORTED + ': fold 0 with REFINE '))
            for f in P.FAMILIES:
                net = doc['families'][f]['network']
                self.assertEqual((doc['families'][f]['not_trainable'], net['supported'], net['a_det_depth'],
                                  net['note']), (True, [False, False], 4, P.ADET_NOTE))
                prov = Q.load_spec(out / f'qnet_{f}.json')['provenance']
                self.assertEqual((prov['selected'], prov['candidate_field']),
                                 (None, 'columns only, not selected (ADET_NOTE)'))
            full, bandit = doc['families']['fqi']['network'], doc['families']['bandit']['network']
            self.assertEqual(full['name'], bandit['name'])
            self.assertNotEqual(full['file_sha256'], bandit['file_sha256'])
            self.assertEqual(doc['shared_names'], {full['name']: ['fl_full', 'fl_bandit']})
            self.assertEqual((doc['job_lines']['fl_full']['qnet_file_sha256'],
                              doc['job_lines']['fl_bandit']['qnet_file_sha256']),
                             (full['file_sha256'], bandit['file_sha256']))
            self.assertEqual(doc['job_lines_rule'], P.JOB_LINES_RULE)
        for msg in ('another error', 'the default action a_det^d is REFRESH at 214 states but that head has only 0 '
                    'samples'):                               # the second: trainers._check_default_support's error
            with tempfile.TemporaryDirectory() as tmp:
                with mock.patch.object(P.O, 'select', side_effect=ValueError(msg)):
                    rc, _, err = run_main('run', '--out', str(Path(tmp) / 'out'), '--stop-after', 'select_fqi',
                                          *DEV_ARGS)
                self.assertEqual(rc, 1, err)
                self.assertIn(f'ValueError: {msg}', err)
                self.assertEqual(sorted(records(Path(tmp) / 'out')), ['dataset', 'p_both'])

    def test_b_distillation_shortfall(self):
        real = P.TR.distill

        def unreachable(q, cand, states, **kw):
            if kw.get('min_agreement', P.MIN_AGREEMENT) > 0:
                kw['min_agreement'] = 1.01                                           # no try can reach it
            return real(q, cand, states, **kw)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            with mock.patch.object(P.TR, 'distill', unreachable):
                rc, _, err = self.run_fqi(out)
            self.assertEqual(rc, 4, err)
            self.assertIn('export_fqi: distillation agreement', err)
            self.assertIn('--distill-shortfall deploy_best', err)
            dis = C.read_json(out / 'distill_fqi.json')
            self.assertFalse(dis['ok'])
            self.assertEqual([t['hidden'] for t in dis['fidelity']['tries']], [[32, 32], [64, 64]])
            best = dis['best_try']
            self.assertEqual(best['agreement'], max(t['agreement'] for t in dis['fidelity']['tries']))
            self.assertNotIn('export_fqi', records(out))
            rc, stdout, err = self.run_fqi(out, '--distill-shortfall', 'deploy_best')   # distillation not rerun
            self.assertEqual(rc, 0, err)
            self.assertIn('[skip] distill_fqi', stdout)
            (dv,) = records(out)['export_fqi']['deviations']
            self.assertEqual((dv['case'], dv['option'], dv['agreement'], dv['hidden']),
                             ('distill_shortfall', 'deploy_best', best['agreement'], best['hidden']))
            spec = Q.load_spec(out / 'qnet_fqi.json')
            self.assertEqual([len(L['b']) for L in spec['layers']], [*best['hidden'], 2])
            mlp = dis['mlp'] if best['same_as_final'] else best['mlp']
            self.assertEqual(spec['layers'][0]['W'], mlp['W'][0])
            self.assertEqual(spec['provenance']['distillation']['agreement'], best['agreement'])
            rc, _, err = self.run_fqi(out)
            self.assertEqual(rc, 1, err)
            self.assertIn('the record used --distill-shortfall deploy_best; pass it again', err)
            doc = self.finish(out, '--distill-shortfall', 'deploy_best')
            dist = doc['families']['fqi']['distillation']
            self.assertEqual((dist['ok'], dist['deployed_agreement'], dist['deployed_hidden']),
                             (False, best['agreement'], best['hidden']))
            self.assertEqual([(d['case'], d['stage'], d['agreement']) for d in doc['deviations']],
                             [('distill_shortfall', 'export_fqi', best['agreement'])])


if __name__ == '__main__':
    unittest.main()
