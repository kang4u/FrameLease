"""P4-P6 job files (framelease_v4/protocol/test_jobs.py; PROTOCOL Secs. 2.6, 3.1, 4.1, 4.3, 7.2-7.5, 8.1-8.4, 8.6, 9.11,
10.1; GAP_AUDIT Sec. 3.5 G-1, Sec. 2 "Recommended labelling", Sec. 3.6 E-1). CPU only; nothing is launched or enqueued.
The tuning freeze, the RL freeze (made from copies of the development networks
outputs/framelease_v4/rl_dev/smoke_20261110/qnet_*.json, named by their absolute paths), a P2 data manifest stand-in,
PROTOCOL.md and its seal are synthetic files in a temporary directory, and every file is written to a temporary
directory; the real envelopes, route split, budget and code pins are only read.

  cd /home/kang/Desktop/DAC && OMP_NUM_THREADS=1 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      -m pytest -q -p no:cacheprovider framelease_v4/protocol/tests/test_test_jobs.py
  # + the in-process launcher checks and the --dry-run through both launchers (official stack variables):
  source linux/env.sh && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 nice -n 19 ionice -c 3 \
      .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/protocol/tests/test_test_jobs.py

What is shown:
  * the run counts: every block holds the runs of its PROTOCOL Sec. 10.1 row (308, 176, 22, 44, 60, and 22 for s_risk
    only if L* = B0 with a fl_risk lease point, else no line and the reason), every arm x kappa x route cell once, the
    seeds of Sec. 2.6 (11; 12 for the replicates), the tiers 3-6 and the block numbers 11-16 in file-name order, which
    one queue's scan (gpu_queue) runs tier 3 first (GAP_AUDIT E-1);
  * the subsets: test_all, E and R are the route lists of PROTOCOL Sec. 3.1 (index % 2, index % 3 of the id-sorted
    test list), no training route, every line on a route of its block's subset; a route split that breaks the rule is
    refused, and so is a consistent swap of a test and a training route (the test rows must be the routes of
    routes.json) and a route split, routes.json or envelope manifest that differs from the sealed registration
    manifest;
  * the lines: ids, launchers, launcher arms, options, wall cap, ports, output directories (Sec. 8.6), the frozen
    parameters of every arm, the order rule of Sec. 8.2, and not_for_launch_before;
  * determinism: the same inputs give byte-identical job files, block specs, checks and index (also in a fresh
    interpreter with another hash seed);
  * the pins: 49 code files for every line, + the envelope (shield arms), + the network FILE (Q-network arms, at the RL
    freeze sha256, FRAMELEASE_V4_QNET absolute), + the 5 extension sources for fl_global_shield only (55); a network
    with the same name and another B_pi is caught by the file pin, and two arms that share a name keep their files;
    every pin but the network files and the extension sources is at the sha256 of the registered P1 lines, and a code
    file or envelope that changed after registration is a problem of every line that pins it;
  * the labels the aggregator reads (framelease_v4/analysis/aggregate_v4.py): protocol_arm in every line, ablation/<arm>
    output directories, the block specs' jobs[] (check_specs, spec_jobs, protocol_label, output_dir_arm), and
    load_specs on the written specs with no patch (LabelsTest.test_the_aggregator_loads_the_block_specs fails while
    aggregate_v4.STAGE_SCHEMAS lacks framelease_v4.test_stage/1: the open cross-item issue M-1 of the review, item
    AGG);
  * the static checks catch every mutation of a line (kappa, seed, route, port, pin, arm, envelope, network, output
    directory, id, an added option such as a lease override, completeness, run count, ids and output directories
    across blocks);
  * every refusal: uncited / unsealed / inconsistent freezes, an RL freeze not made from the tuning freeze, a relative
    or changed network, the write guards (queue path, existing test-route runs also with --force, other content,
    a recorded file, stale s_risk files), the CLI exit codes;
  * with the official stack: one line of every block x arm x kappa passes the in-process preparation and the --dry-run
    through its launcher (run_closed_loop_v4.py; run_closed_loop_ext.py for fl_global_shield, which refuses a lease
    override), and check_lines passes on whole blocks.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ['CUDA_VISIBLE_DEVICES'] = ''
sys.dont_write_bytecode = True

from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402
from framelease_v4.protocol import p2_jobs as P2J  # noqa: E402
from framelease_v4.protocol import registration as REG  # noqa: E402
from framelease_v4.protocol import select_stage as SS  # noqa: E402
from framelease_v4.protocol import test_jobs as TJ  # noqa: E402
from framelease_v4.protocol.tests import test_p2_jobs as T2J  # noqa: E402  (the PROTOCOL.md skeleton, the freeze entry)

STACK = bool(os.environ.get('CHECKPOINT')) and Path(os.environ.get('CHECKPOINT', '/nonexistent')).is_file()
DEV_NETS = ROOT / 'outputs/framelease_v4/rl_dev/smoke_20261110'
# PROTOCOL Sec. 3.1, the subset table (route ids, id-sorted)
SUBSET_E = ['1711', '1790', '1852', '2050', '2084', '2127', '2164', '2204', '2286', '2390', '2509', '2664', '2790',
            '3248', '3436', '3540', '3936', '14842', '17752', '23695', '23901', '28087']
SUBSET_R = ['1711', '1825', '2050', '2115', '2164', '2273', '2390', '2534', '2790', '3364', '3540', '14194', '17752',
            '23771', '28087']
# PROTOCOL Sec. 10.1, the budget rows of tiers 3-6
SEC_10_1 = {'ti_main': ('P4', 3, 'TI-main', 308), 'f3_k': ('P5', 4, 'F3-k', 176), 'a_lease': ('P6', 5, 'A-lease', 22),
            'a_rl': ('P6', 5, 'A-rl', 44), 's_seed12': ('P6', 6, 'S-seed12', 60), 's_risk': ('P6', 6, 'S-risk', 22)}
RISK_RECORD = {'lease_point': 'E10',
               'rule': 'L* = B0: fl_risk runs the better of E5 / E10 by mean DS on lease_s1 (T22a), ties earlier'}


def freeze_doc(label='B0', d=10, risk='auto', a_star=1.5, event=('s', 1.0), stages=None):
    """A synthetic tuning freeze in the select_stage.freeze() format (risk: the fl_risk record; 'auto': RISK_RECORD
    if L* = B0, else None, as select_stage.freeze writes it)."""
    if risk == 'auto':
        risk = RISK_RECORD if label == 'B0' else None
    e = PJ.envelopes()[label]
    u = PJ.heur_utility(d)
    ev = PJ.event_cand(*event)
    return {'schema': SS.FREEZE_SCHEMA, 'variant': 'FULL', 'written': '2026-11-12T09:00:00+0800',
            'L_star': {'label': label, 'envelope_path': e['path'], 'envelope_sha256': e['sha256'],
                       'config': e['config'], 'validity': 'std'},
            'd_star': {'d': d, 'utility': u}, 'A_star': {'age_lease_s': a_star},
            'event_star': {'candidate': ev['name'], 'policy_params': ev['policy_params']},
            'arms': {'fl_heuristic': {'envelope': e['path'], 'policy_params': {'utility': u}},
                     'fl_full': {'envelope': e['path'], 'a_det_depth': d},
                     'fl_behaviour': {'envelope': e['path'], 'base_depth': d},
                     'age_only': {'policy_params': {'age_lease_s': a_star, 'utility': u}},
                     'event_triggered': {'policy_params': ev['policy_params']}},
            'fl_risk': copy.deepcopy(risk), 'stages': dict(stages or {}), 'tables': {}, 'flags': {},
            'script_sha256': {}}


def dump(path, doc):
    Path(path).write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n', encoding='utf-8')


def registration_copy(tmp, change=None, sealed=True):
    """(manifest, seal): a copy of the sealed registration manifest in tmp with the entries of `change` ({path:
    sha256}) replaced, and a seal that names it (sealed) or another manifest sha256; for mock.patch of
    registration.MANIFEST / SEAL."""
    man = {**REG.read_manifest(), **(change or {})}
    mpath, spath = Path(tmp) / 'MANIFEST.sha256', Path(tmp) / 'SEAL.sha256'
    mpath.write_text(''.join(f'{s}  {p}\n' for p, s in sorted(man.items())), encoding='utf-8')
    msha = PJ.sha256_file(mpath) if sealed else '2' * 64
    spath.write_text(f'{"0" * 64}  framelease_v4/PROTOCOL.md\n{msha}  {PJ.rel(mpath)}\n', encoding='utf-8')
    return mpath, spath


def swapped_split(test_id='1711', train_id='18305'):
    """route_split.json with a test and a training route swapped consistently: indices and subsets re-derived by the
    Sec. 3.1 rule, so every rule of the split itself holds (review S-1)."""
    doc = copy.deepcopy(PJ.route_split())
    t = next(r for r in doc['test'] if r['route_id'] == test_id)
    s = next(r for r in doc['training'] if r['route_id'] == train_id)
    t['route_id'], s['route_id'] = train_id, test_id
    for key in ('test', 'training'):
        for i, r in enumerate(sorted(doc[key], key=lambda r: int(r['route_id']))):
            r['index'] = i
    ids = [r['route_id'] for r in sorted(doc['test'], key=lambda r: int(r['route_id']))]
    doc['subsets'].update(test_all=ids, E=ids[::2], R=ids[::3])
    return doc


class Env:
    """Synthetic freezes in a temporary directory: selection.json (cited in the Sec. 13.2 of a synthetic PROTOCOL.md,
    sealed), copies of the development networks at absolute paths, a P2 data manifest stand-in and a production RL
    freeze made from that tuning freeze (p3_rl.load_rl_freeze accepts it). extra: more Sec. 13.2 lines."""

    def __init__(self, tmp, label='B0', d=10, risk='auto', doc=None, cite=True, sealed=True):
        from framelease_v4.protocol import p3_rl as P3
        from framelease_v4.rl import qnet as Q
        self.tmp = Path(tmp)
        if self.tmp.exists():
            shutil.rmtree(self.tmp)
        (self.tmp / 'nets').mkdir(parents=True)
        self.sel, self.rl_path = self.tmp / 'selection.json', self.tmp / 'rl_freeze.json'
        self.protocol, self.seal = self.tmp / 'PROTOCOL.md', self.tmp / 'SEAL.sha256'
        self.jobs, self.root = self.tmp / 'jobs', self.tmp / 'root'
        self.p2 = self.tmp / 'data_manifest.json'
        self.extra, self.cite, self.sealed = [], cite, sealed
        self.write_selection(doc or freeze_doc(label, d, risk), rl=False)
        dump(self.p2, {'schema': P3.P2_MANIFEST_SCHEMA, 'synthetic': True})
        fams, lines, files = {}, {}, {}
        for fam, arm in P3.ARM_OF.items():
            dst = self.tmp / 'nets' / f'qnet_{fam}.json'
            shutil.copyfile(DEV_NETS / f'qnet_{fam}.json', dst)
            ref, _ = P3.network_ref(dst)
            fams[fam] = {'arm': arm, 'not_trainable': False, 'network': {**ref, 'arm': arm, 'note': None}}
            lines[arm] = {'utility': ref['name'], Q.ENV_QNET: ref['abs_path'], 'qnet_file_sha256': ref['file_sha256']}
            files[ref['path']] = ref['file_sha256']
        files[PJ.rel(self.p2)] = PJ.sha256_file(self.p2)
        self.rl_doc = {'schema': P3.FREEZE_SCHEMA, 'variant': 'FULL', 'mode': 'production', 'frozen': True,
                       'dataset': {'episodes': []}, 'families': fams, 'job_lines': lines,
                       'p_both': {'label': 'testable'}, 'files': dict(sorted(files.items())),
                       'p2_manifest': {'path': PJ.rel(self.p2), 'sha256': PJ.sha256_file(self.p2), 'cited_lines': []},
                       'deviations': [], 'sec13_notes': {'items': list(P3.SEC13_NOTES), 'note': 'synthetic'},
                       'shared_names': {}}
        self.write_rl()

    def write_protocol(self, sealed=None):
        sealed = self.sealed if sealed is None else sealed
        entries = ([T2J.freeze_entry(PJ.sha256_file(self.sel))] if self.cite else []) + list(self.extra)
        self.protocol.write_text(T2J.protocol_text('\n'.join(entries)), encoding='utf-8')
        psha = PJ.sha256_file(self.protocol) if sealed else '0' * 64
        self.seal.write_text(f'{psha}  {self.protocol}\n{"1" * 64}  {self.tmp / "MANIFEST.sha256"}\n')

    def write_selection(self, doc, rl=True):
        """A new selection.json, cited (unless cite is off) and sealed; the RL freeze names it (rl)."""
        self.doc = copy.deepcopy(doc)
        dump(self.sel, self.doc)
        self.write_protocol()
        if rl:
            self.write_rl()

    def write_rl(self, mutate=None):
        """The RL freeze, made from the current selection.json; mutate(doc) changes it before it is written."""
        e = PJ.envelopes()[self.doc['L_star']['label']]
        d = self.doc['d_star']['d']
        self.rl_doc.update(d_star=d, tuning_freeze={'path': PJ.rel(self.sel), 'sha256': PJ.sha256_file(self.sel),
                                                    'd': d, 'cited_lines': [],
                                                    'L_star': {'label': self.doc['L_star']['label'],
                                                               'sha256': e['sha256']}})
        doc = copy.deepcopy(self.rl_doc)
        if mutate:
            mutate(doc)
        dump(self.rl_path, doc)

    def tuning(self, seal=True):
        return TJ.load_tuning(self.sel, self.protocol, self.seal if seal else None)

    def load(self):
        tuning = self.tuning()
        return tuning, TJ.load_rl(tuning, self.rl_path, self.protocol)

    def build(self):
        """(tuning, rl, built) of test_jobs.build_all."""
        tuning, rl = self.load()
        return tuning, rl, TJ.build_all(tuning, rl)

    def main(self, *extra):
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            rc = TJ.main(['--selection', str(self.sel), '--rl-freeze', str(self.rl_path), '--protocol',
                          str(self.protocol), '--seal', str(self.seal), '--jobs-dir', str(self.jobs)] + list(extra))
        return rc, out.getvalue(), err.getvalue()


def opts(cmd):
    return T2J.opts(cmd)


class Built(unittest.TestCase):
    """Two synthetic freezes, built once per class: L* = B0 with fl_risk at E10 (632 lines) and L* = E5 (610)."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.B = Env(Path(cls._tmp.name) / 'b0')
        cls.tuning, cls.rl, cls.built = cls.B.build()
        cls.arms = TJ.frozen_arms(cls.tuning, cls.rl)
        cls.A = Env(Path(cls._tmp.name) / 'e5', 'E5')
        cls.tuningA, cls.rlA, cls.builtA = cls.A.build()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def lines_of(self, block, built=None):
        return next(x for x in (built or self.built) if x[0]['block'] == block)


class BlocksTest(Built):
    def test_run_counts_are_the_budget_of_sec_10_1(self):
        from framelease_v4.protocol import make_protocol_tables as MPT
        plan = {b[2]: b for b in MPT.plan_blocks('FULL')}
        self.assertEqual([b['block'] for b in TJ.BLOCKS], list(SEC_10_1))
        for blk, lines, spec in self.built:
            phase, tier, budget, runs = SEC_10_1[blk['block']]
            self.assertEqual((blk['phase'], blk['tier'], blk['budget']), (phase, tier, budget))
            self.assertEqual((plan[budget][0], plan[budget][1], int(plan[budget][4])), (phase, tier, runs))
            self.assertEqual(TJ.budget_runs(blk), runs)
            self.assertEqual(len(lines), runs, blk['block'])
            self.assertEqual((spec['n_lines'], spec['expected_runs_sec_10_1'], spec['skipped']), (runs, runs, None))
        per_phase = {}
        for blk, lines, _ in self.built:
            per_phase[blk['phase']] = per_phase.get(blk['phase'], 0) + len(lines)
        self.assertEqual(per_phase, {'P4': 308, 'P5': 176, 'P6': 148})          # the phase table of Sec. 10.1
        self.assertEqual(TJ.cross_block_problems(self.built), [])
        # L* = E5: fl_risk is not run (Sec. 4.3); s_risk has no line, its spec says why, the total drops by 22
        counts = {blk['block']: len(lines) for blk, lines, _ in self.builtA}
        self.assertEqual(counts, {**{k: v[3] for k, v in SEC_10_1.items()}, 's_risk': 0})
        _, _, spec = self.lines_of('s_risk', self.builtA)
        self.assertEqual((spec['n_lines'], spec['expected_runs_sec_10_1'], spec['jobs'], spec['arms']), (0, 0, [], {}))
        self.assertIn('E5 is not B0', spec['skipped'])
        self.assertNotIn('fl_risk', TJ.frozen_arms(self.tuningA, self.rlA))
        self.assertEqual(TJ.cross_block_problems(self.builtA), [])

    def test_every_cell_once_at_the_seed_and_kappas_of_its_block(self):
        fig3 = ('fixed_deep', 'fast_only', 'fl_heuristic', 'fl_full')
        want = {'ti_main': (('fixed_deep', 'fast_only', 'age_only', 'event_triggered', 'fl_original', 'fl_heuristic',
                             'fl_full'), (1.0,), 44, 11),
                'f3_k': (fig3, (1.5, 2.0), 22, 11), 'a_lease': (('fl_global_shield',), (1.0,), 22, 11),
                'a_rl': (('fl_bandit', 'fl_fqi_nolease'), (1.0,), 22, 11), 's_seed12': (fig3, (1.0,), 15, 12),
                's_risk': (('fl_risk',), (1.0,), 22, 11)}
        for blk, lines, spec in self.built:
            arms, kappas, n_routes, seed = want[blk['block']]
            self.assertEqual((tuple(blk['arms']), tuple(blk['kappas']), blk['seed']), (arms, kappas, seed))
            cells = [(j['protocol_arm'], j['kappa'], j['route_id']) for j in lines]
            self.assertEqual(len(set(cells)), len(cells))
            self.assertEqual(set(cells), {(a, k, r) for a in arms for k in kappas
                                          for r in TJ.route_subset(blk['routes'])})
            self.assertEqual(spec['runs_per_arm_kappa'], {f'{a}_k{k:.1f}': n_routes for a in arms for k in kappas})
            self.assertEqual({(j['seed'], j['tier'], j['phase'], j['block_no']) for j in lines},
                             {(seed, blk['tier'], blk['phase'], blk['no'])})
            self.assertEqual({opts(j['cmd'])['--seed'] for j in lines}, {str(seed)})
            self.assertEqual({opts(j['cmd'])['--kappa'] for j in lines}, {f'{k:.1f}' for k in kappas})

    def test_block_numbers_file_names_and_one_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            names = [TJ.block_paths(blk, tmp)[0].name for blk in TJ.BLOCKS]
        self.assertEqual(names, ['b11_ti_main.jsonl', 'b12_f3_k.jsonl', 'b13_a_lease.jsonl', 'b14_a_rl.jsonl',
                                 'b15_s_seed12.jsonl', 'b16_s_risk.jsonl'])
        self.assertEqual(sorted(names), names)                  # name order = tier order: a cut takes tiers 6, 5, ...
        self.assertEqual([b['tier'] for b in TJ.BLOCKS], [3, 4, 5, 5, 6, 6])
        self.assertEqual([b['no'] for b in TJ.BLOCKS], list(range(P2J.BLOCK_NO + 1, P2J.BLOCK_NO + 7)))   # 11-16
        self.assertEqual(TJ.QUEUE_REL, 'outputs/framelease_v4/queue_p4')    # GAP_AUDIT E-1
        for _, _, spec in self.built:
            self.assertEqual((spec['queue'], spec['schema'], spec['variant']), (TJ.QUEUE_REL, TJ.STAGE_SCHEMA, 'FULL'))

    def test_one_queue_runs_the_tiers_in_order(self):
        """GAP_AUDIT E-1: the six files copied into one queue's jobs.d/ are read (gpu_queue's own scan, as --list
        reads them; no runner starts) in file-name, then line order: tier 3 first, every line valid, no id twice."""
        from framelease_v2 import gpu_queue as GQ
        with tempfile.TemporaryDirectory() as tmp:
            TJ.write_all(self.built, fake_checked(self.built), [], Path(tmp) / 'jobs', self.B.protocol,
                         root=self.B.root)
            q = Path(tmp) / 'queue_scratch'
            (q / 'jobs.d').mkdir(parents=True)
            for f in sorted((Path(tmp) / 'jobs' / 'FULL').glob('*.jsonl')):
                shutil.copyfile(f, q / 'jobs.d' / f.name)
            runner = GQ.Runner(GQ.parse_args(['--queue-dir', str(q), '--gpu-lock-root', str(Path(tmp) / 'lock')]))
            jobs = runner.scan_jobs(report=False)
            self.assertFalse((q / 'status.jsonl').exists() or (q / 'runner.log').exists())
        want = [j['id'] for _, lines, _ in self.built for j in lines]
        self.assertEqual([j['spec']['id'] for j in jobs], want)
        tiers = [j['spec']['tier'] for j in jobs]
        self.assertEqual(tiers, sorted(tiers))
        self.assertEqual((tiers[0], tiers[-1], len(jobs)), (3, 6, 632))


class SubsetTest(Built):
    def test_subsets_are_the_route_lists_of_sec_3_1(self):
        test = sorted((r['route_id'] for r in PJ.route_split()['test']), key=int)
        self.assertEqual(len(test), 44)
        self.assertEqual(TJ.route_subset('test_all'), test)
        self.assertEqual(TJ.route_subset('E'), SUBSET_E)
        self.assertEqual(TJ.route_subset('R'), SUBSET_R)
        self.assertEqual(SUBSET_E, [r for i, r in enumerate(test) if i % 2 == 0])    # the rule: v2 index % 2
        self.assertEqual(SUBSET_R, [r for i, r in enumerate(test) if i % 3 == 0])    # v2 index % 3
        self.assertFalse(set(test) & set(PJ.training_routes()))
        self.assertEqual({b['block']: b['routes'] for b in TJ.BLOCKS},
                         {'ti_main': 'test_all', 'f3_k': 'E', 'a_lease': 'E', 'a_rl': 'E', 's_seed12': 'R',
                          's_risk': 'E'})

    def test_every_line_runs_a_test_route_of_its_block_subset(self):
        rows = TJ.route_table()
        train = set(PJ.training_routes())
        for blk, lines, spec in self.built:
            subset = TJ.route_subset(blk['routes'])
            self.assertEqual(spec['routes'], subset)
            for j in lines:
                r = j['route_id']
                self.assertIn(r, subset)
                self.assertNotIn(r, train)
                self.assertEqual(opts(j['cmd'])['--route-id'], r)
                self.assertEqual((j['test_route'], j['training_route'], j['route_set']), (True, False, blk['routes']))
                self.assertEqual((j['route_index'], j['town'], j['scenario_type']),
                                 (rows[r]['index'], rows[r]['town'], rows[r]['scenario_type']))

    def test_a_route_split_that_breaks_the_rule_is_refused(self):
        split = PJ.route_split()
        train_id = next(iter(PJ.training_routes()))
        bad_subset = copy.deepcopy(split)
        bad_subset['subsets']['E'] = bad_subset['subsets']['E'][:-1] + [SUBSET_R[1]]
        bad_index = copy.deepcopy(split)
        a, b = bad_index['test'][0], bad_index['test'][1]
        a['index'], b['index'] = b['index'], a['index']
        bad_train = copy.deepcopy(split)
        bad_train['test'][0] = {**bad_train['test'][0], 'route_id': train_id}
        for what, doc, subset in (('subset E', bad_subset, 'E'), ('index', bad_index, 'R'),
                                  ('training route', bad_train, 'test_all')):
            with mock.patch.object(PJ, 'route_split', return_value=doc), self.assertRaises(ValueError, msg=what):
                TJ.route_subset(subset)

    def test_a_consistent_swap_with_a_training_route_is_refused(self):
        """Review S-1: test route 1711 swapped with training route 18305 (the P1-0 smoke route), indices and subsets
        re-derived, passes every rule of the split itself; the comparison with routes.json (Sec. 3.1) refuses it."""
        doc = swapped_split()
        self.assertIn('18305', doc['subsets']['test_all'])
        with mock.patch.object(PJ, 'route_split', return_value=doc):
            for name in ('test_all', 'E', 'R'):
                with self.assertRaisesRegex(ValueError, 'not the 44 routes of outputs/framelease_v2/'):
                    TJ.route_subset(name)
            with self.assertRaisesRegex(ValueError, 'not the 44 routes of'):
                TJ.build_block(TJ.BLOCKS[4], self.arms, self.tuning, self.rl, {})
            rc, out, err = self.B.main()
        self.assertEqual(rc, 2)
        self.assertIn('REFUSED', err)
        # a subset whose routes.json membership list differs (route 1711 no longer in 'even')
        rows = TJ.v2_routes()
        rows['1711'] = {**rows['1711'], 'subsets': [s for s in rows['1711']['subsets'] if s != 'even']}
        with mock.patch.object(TJ, 'v2_routes', return_value=rows):
            self.assertEqual(TJ.route_subset('R')[0], '1711')
            with self.assertRaisesRegex(ValueError, "routes.json list 'even'"):
                TJ.route_subset('E')

    def test_the_route_inputs_are_the_registered_files(self):
        """Review S-1: route_split.json, routes.json and the envelope manifest at their entries of the sealed
        registration manifest; an entry that differs, or a manifest that is not the sealed one, refuses generation."""
        self.assertEqual(TJ.registered_inputs(), {PJ.rel(p): PJ.sha256_file(p) for p in TJ.REGISTERED_INPUTS})
        self.assertEqual({PJ.rel(p) for p in TJ.REGISTERED_INPUTS},
                         {'outputs/framelease_v4/protocol/route_split.json',
                          'outputs/framelease_v2/closed_loop_matrix/routes.json',
                          'outputs/framelease_v4/envelopes/manifest.json'})
        for _, _, spec in self.built:
            self.assertEqual({k: v for k, v in spec['inputs'].items() if k in TJ.registered_inputs()},
                             TJ.registered_inputs())
        with tempfile.TemporaryDirectory() as tmp:
            for i, path in enumerate(TJ.REGISTERED_INPUTS):
                sub = Path(tmp) / str(i)
                sub.mkdir()
                man, seal = registration_copy(sub, {PJ.rel(path): '0' * 64})
                with mock.patch.object(REG, 'MANIFEST', man), mock.patch.object(REG, 'SEAL', seal):
                    with self.assertRaisesRegex(ValueError, 'differs from its registration manifest entry'):
                        TJ.build_block(TJ.BLOCKS[4], self.arms, self.tuning, self.rl, {})
                    rc, out, err = self.B.main()
                self.assertEqual(rc, 2, PJ.rel(path))
                self.assertIn(PJ.rel(path), err)
            man, seal = registration_copy(tmp, sealed=False)
            with mock.patch.object(REG, 'MANIFEST', man), mock.patch.object(REG, 'SEAL', seal), \
                    self.assertRaisesRegex(ValueError, 'not the sealed registration manifest'):
                TJ.route_subset('E')


def fake_checked(built):
    """{block: (results, problems)} as test_jobs.check_lines returns them for clean lines whose --dry-run did not start
    the run (NOT_STARTED): the write path without the launcher (the launcher checks are LauncherTest's)."""
    return {blk['block']: ([{'id': j['id'], 'ok': True, 'problems': [], 'dry_run': {'status': 'NOT_STARTED'}}
                            for j in lines], []) for blk, lines, _ in built if lines}


OUT_LAYOUT = {'ti_main': 'matrix/{a}', 'f3_k': 'fig3/{a}_k{k:.1f}', 'a_lease': 'ablation/{a}', 'a_rl': 'ablation/{a}',
              's_seed12': 'replicates/{a}', 's_risk': 'ablation/{a}'}          # PROTOCOL Sec. 8.6


class LinesTest(Built):
    def expected_arms(self, tuning, rl):
        """{protocol arm: (launcher arm, launcher, config, policy params, envelope label)} at the synthetic freeze."""
        d, L = tuning['d'], tuning['L']['label']
        u = PJ.heur_utility(d)
        ev = PJ.event_cand('s', 1.0)
        out = {a: (a, 'v4', None, {}, None) for a in ('fixed_deep', 'fast_only', 'fl_original')}
        out.update({'age_only': ('age_only', 'v4', f'A1.5_d{d}', {'age_lease_s': 1.5, 'utility': u}, None),
                    'event_triggered': ('event_triggered', 'v4', 's_hb1.0', ev['policy_params'], None),
                    'fl_heuristic': ('fl_heuristic', 'v4', f'{L}_d{d}', {'utility': u}, L),
                    'fl_global_shield': ('fl_global_shield', 'ext', f'{L}_d{d}', {'utility': u}, L)})
        for arm in ('fl_full', 'fl_bandit', 'fl_fqi_nolease'):
            name = rl['networks'][arm]['name']
            out[arm] = ('fl_full', 'v4', f'{L}_d{d}_{name}', {'utility': name}, L)
        if tuning['risk'] is not None:
            out['fl_risk'] = ('fl_heuristic', 'v4', f'E10_d{d}', {'utility': u}, 'E10')
        return out

    def test_the_frozen_arms(self):
        envs = PJ.envelopes()
        for tuning, rl in ((self.tuning, self.rl), (self.tuningA, self.rlA)):
            want = self.expected_arms(tuning, rl)
            arms = TJ.frozen_arms(tuning, rl)
            self.assertEqual(set(arms), set(want))
            for a, (larm, launcher, config, params, env) in want.items():
                got = arms[a]
                self.assertEqual((got['protocol_arm'], got['launcher_arm'], got['launcher'], got['config'],
                                  got['policy_params']), (a, larm, launcher, config, params), a)
                self.assertEqual((got['envelope'] or {}).get('label'), env, a)
                if env:
                    self.assertEqual((got['envelope']['path'], got['envelope']['sha256']),
                                     (envs[env]['path'], envs[env]['sha256']))
                self.assertEqual(got['network'] is not None, a in TJ.QNET_FAMILY, a)

    def test_d_star_names_the_utility(self):
        with tempfile.TemporaryDirectory() as tmp:
            E = Env(tmp, 'E10', 4)
            tuning = E.tuning()
            arms = TJ.frozen_arms(tuning, self.rl)
            self.assertEqual(arms['age_only']['policy_params'], {'age_lease_s': 1.5, 'utility': 'v4_adet_d4'})
            self.assertEqual(arms['age_only']['config'], 'A1.5_d4')
            for a in ('fl_heuristic', 'fl_global_shield'):
                self.assertEqual((arms[a]['config'], arms[a]['policy_params']), ('E10_d4', {'utility': 'v4_adet_d4'}))
            # the development networks have a_det depth 10: an RL freeze at d* = 4 that names them is refused
            with self.assertRaises(ValueError):
                TJ.load_rl(tuning, E.rl_path, E.protocol)

    def test_every_line_carries_its_frozen_arm_and_the_sec_8_2_fields(self):
        from framelease_v4.rl import qnet as Q
        for tuning, rl, built in ((self.tuning, self.rl, self.built), (self.tuningA, self.rlA, self.builtA)):
            want = self.expected_arms(tuning, rl)
            refs = TJ.freeze_refs(tuning, rl)
            envs = PJ.envelopes()
            for blk, lines, _ in built:
                prefix = {'P4': 'v4p4', 'P5': 'v4p5', 'P6': 'v4p6'}[blk['phase']]
                for i, j in enumerate(lines):
                    a, k, r = j['protocol_arm'], j['kappa'], j['route_id']
                    larm, launcher, config, params, env = want[a]
                    o = opts(j['cmd'])
                    rel = TJ.EXT_LAUNCHER_REL if launcher == 'ext' else 'framelease_v4/arms/run_closed_loop_v4.py'
                    self.assertEqual((j['cmd'][:3], j['launcher']), ([PJ.PYTHON, '-B', rel], rel))
                    self.assertEqual((o['--arm'], j['arm_name']), (larm, larm))
                    self.assertEqual((o['--fast-prefix'], o['--timeout-s'], o['--lock-wait-s'], o['--routes']),
                                     ('sdpa,gpu_preproc,lora_merged', '1410', '600', PJ.ROUTES_XML_REL))
                    self.assertEqual((j['kind'], j['wall_cap_s'], j['matrix']), ('closed_loop', 1500, TJ.MATRIX))
                    self.assertEqual((j['port'], o['--port']), (2600 + 10 * (i % 4), str(2600 + 10 * (i % 4))))
                    self.assertEqual(json.loads(o.get('--policy-params', '{}')), params)
                    self.assertEqual(j['policy_params'], params)
                    self.assertEqual(o.get('--envelope'), envs[env]['path'] if env else None)
                    self.assertEqual((j['envelope'] or {}).get('sha256'), envs[env]['sha256'] if env else None)
                    out = f'outputs/framelease_v4/{OUT_LAYOUT[blk["block"]].format(a=a, k=k)}'
                    self.assertEqual((j['output_dir'], o['--output-dir']), (out, out))
                    mid = f'{a}_{config}' if config else a
                    self.assertEqual(j['id'], f'{prefix}_{mid}_k{k:.1f}_s{blk["seed"]}_r{r}')
                    self.assertRegex(j['id'], r'^v4p[456]_[a-z_]+(_[A-Za-z0-9_.]+)?_k[12]\.[05]_s1[12]_r\d+$')
                    self.assertEqual((j['config'], j['candidate'], j['budget_block']), (config, a, blk['budget']))
                    self.assertEqual(j['not_for_launch_before'], TJ.NOT_BEFORE)
                    self.assertIn('test freeze', j['not_for_launch_before'])
                    self.assertEqual({x: j[x] for x in refs}, refs)
                    self.assertEqual(j.get('d_star'), tuning['d'] if 'utility' in params else None)
                    self.assertEqual(Q.ENV_QNET in json.dumps(j['cmd']), a in TJ.QNET_FAMILY)

    def test_order_is_the_rule_of_sec_8_2(self):
        self.assertEqual(PJ.ORDER_SEED, 20261110)
        for blk, lines, spec in self.built:
            cells = [(a, float(k)) for a in blk['arms'] for k in blk['kappas']]      # f3_k: arm-major
            rs = sorted(TJ.route_subset(blk['routes']), key=int)
            random.Random(20261110 + blk['no']).shuffle(rs)
            self.assertEqual(spec['route_order'], rs)
            n = len(cells)
            self.assertEqual(len(lines), n * len(rs))
            for pos, r in enumerate(rs):
                group = lines[pos * n:(pos + 1) * n]
                self.assertEqual({j['route_id'] for j in group}, {r})
                self.assertEqual([(j['protocol_arm'], j['kappa']) for j in group], cells[pos % n:] + cells[:pos % n])


DETERMINISM_CODE = '''
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
sys.dont_write_bytecode = True
from framelease_v4.protocol import p2_jobs as P2J
from framelease_v4.protocol import test_jobs as TJ
tmp = Path(sys.argv[2])
tuning = TJ.load_tuning(tmp / 'selection.json', tmp / 'PROTOCOL.md', tmp / 'SEAL.sha256')
built = TJ.build_all(tuning, TJ.load_rl(tuning, tmp / 'rl_freeze.json', tmp / 'PROTOCOL.md'))
sha = lambda t: hashlib.sha256(t.encode()).hexdigest()
print(json.dumps({b['block']: [sha(P2J.jsonl(l)), sha(json.dumps(s, sort_keys=True))] for b, l, s in built}))
'''


class DeterminismTest(Built):
    def test_the_same_inputs_give_the_same_bytes(self):
        _, _, again = self.B.build()
        for (blk, l1, s1), (_, l2, s2) in zip(self.built, again):
            self.assertEqual(P2J.jsonl(l1), P2J.jsonl(l2), blk['block'])
            self.assertEqual(json.dumps(s1, sort_keys=True), json.dumps(s2, sort_keys=True), blk['block'])
        # written twice into one directory: the second write keeps every byte
        with tempfile.TemporaryDirectory() as tmp:
            TJ.write_all(self.built, fake_checked(self.built), [], tmp, self.B.protocol, root=self.B.root)
            first = {p.name: p.read_bytes() for p in sorted((Path(tmp) / 'FULL').iterdir())}
            self.assertEqual(len(first), 6 * 3 + 1)
            TJ.write_all(again, fake_checked(again), [], tmp, self.B.protocol, root=self.B.root)
            self.assertEqual({p.name: p.read_bytes() for p in sorted((Path(tmp) / 'FULL').iterdir())}, first)
        # a fresh interpreter (its own hash seed) generates the same job files and block specs
        p = subprocess.run([sys.executable, '-I', '-B', '-c', DETERMINISM_CODE, str(ROOT), str(self.B.tmp)],
                           capture_output=True, text=True, timeout=300, cwd=str(self.B.tmp),
                           env=dict(os.environ, CUDA_VISIBLE_DEVICES=''))
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        want = {blk['block']: [PJ.sha256_text(P2J.jsonl(lines)), PJ.sha256_text(json.dumps(spec, sort_keys=True))]
                for blk, lines, spec in self.built}
        self.assertEqual(json.loads(p.stdout), want)


QNET_CORE = ('schema', 'feature_columns', 'feature_spec', 'layers', 'activation', 'actions', 'supported',
             'deviation_margin', 'a_det', 'weights_sha256', 'name')        # qnet._canonical_sha's fields + its name


def share_core(E, src='fqi', dst='bandit'):
    """The dst family's network file rewritten with the src family's decision core (its candidate kept), so two arms
    share a network name with two network files (p3_rl.JOB_LINES_RULE: e.g. two not-trainable families); the RL
    freeze written again as p3_rl.stage_freeze records it (shared_names)."""
    from framelease_v4.protocol import p3_rl as P3
    from framelease_v4.rl import qnet as Q
    path = E.tmp / 'nets' / f'qnet_{dst}.json'
    spec = json.loads(path.read_text())
    spec.update({k: v for k, v in json.loads((E.tmp / 'nets' / f'qnet_{src}.json').read_text()).items()
                 if k in QNET_CORE})
    dump(path, spec)
    ref, _ = P3.network_ref(path)
    arm = P3.ARM_OF[dst]
    E.rl_doc['families'][dst]['network'] = {**ref, 'arm': arm, 'note': None}
    E.rl_doc['job_lines'][arm] = {'utility': ref['name'], Q.ENV_QNET: ref['abs_path'],
                                  'qnet_file_sha256': ref['file_sha256']}
    E.rl_doc['files'][ref['path']] = ref['file_sha256']
    E.rl_doc['shared_names'] = {n: a for n, a in P3.shared_names(E.rl_doc['families']).items() if len(a) > 1}
    E.write_rl()
    return ref


class PinsTest(Built):
    def test_two_arms_that_share_a_network_name_are_told_apart_by_the_file(self):
        from framelease_v4.analysis import aggregate_v4 as AG
        with tempfile.TemporaryDirectory() as tmp:
            E = Env(tmp)
            share_core(E)
            tuning, rl, built = E.build()
            full, bandit = rl['networks']['fl_full'], rl['networks']['fl_bandit']
            self.assertEqual(full['name'], bandit['name'])
            self.assertNotEqual(full['sha256'], bandit['sha256'])
            arms = TJ.frozen_arms(tuning, rl)
            self.assertEqual(arms['fl_full']['config'], arms['fl_bandit']['config'])
            for blk, lines, _ in built:
                self.assertEqual(TJ.static_problems(blk, lines, arms, tuning, rl, {}), [], blk['block'])
            self.assertEqual(TJ.cross_block_problems(built), [])
            lines = [j for _, ls, _ in built for j in ls if j['protocol_arm'] in ('fl_full', 'fl_bandit')]
            for j in lines:
                net = rl['networks'][j['protocol_arm']]
                self.assertEqual((j['network']['sha256'], j['require_sha256'][net['path']], j['utility_env']),
                                 (net['sha256'], net['sha256'], {'FRAMELEASE_V4_QNET': net['abs_path']}))
            agg_rl, agg_tuning = AG.load_rl_freeze(E.rl_path), AG.load_tuning_freeze(E.sel)
            for j in lines:
                self.assertEqual(AG.protocol_label(j, config_stub(j), {}, agg_rl, agg_tuning)[:3:2],
                                 (j['protocol_arm'], []))

    def test_the_pin_set_of_every_arm(self):
        from framelease_v2 import gpu_queue as GQ
        from framelease_v4.arms import jobs_v4 as J
        from framelease_v4.arms_ext import arms_ext as X
        base = J.code_pins([])
        self.assertEqual(len(base), 49)                         # the pins of every P1 line
        envs, L = PJ.envelopes(), self.tuning['L']
        ext = {f: PJ.sha256_file(ROOT / f) for f in X.EXT_CODE}
        self.assertEqual(len(ext), 5)
        lpin = {L['path']: L['sha256']}
        want = {a: {} for a in ('fixed_deep', 'fast_only', 'fl_original', 'age_only', 'event_triggered')}
        want.update(fl_heuristic=lpin, fl_global_shield={**lpin, **ext},
                    fl_risk={envs['E10']['path']: envs['E10']['sha256']},
                    **{a: {**lpin, n['path']: n['sha256']} for a, n in self.rl['networks'].items()})
        n = {a: len(base) + len(v) for a, v in want.items()}
        self.assertEqual(n, {'fixed_deep': 49, 'fast_only': 49, 'fl_original': 49, 'age_only': 49,
                             'event_triggered': 49, 'fl_heuristic': 50, 'fl_risk': 50, 'fl_full': 51, 'fl_bandit': 51,
                             'fl_fqi_nolease': 51, 'fl_global_shield': 55})
        union = {}
        for _, lines, spec in self.built:
            for j in lines:
                self.assertEqual(j['require_sha256'], {**base, **want[j['protocol_arm']]}, j['id'])
                for f, h in j['require_sha256'].items():
                    self.assertEqual(union.setdefault(f, h), h)
            self.assertEqual({a: s['pins']['n'] for a, s in spec['arms'].items()}, {a: n[a] for a in spec['arms']})
        self.assertEqual(GQ.pin_mismatches(union), [])
        self.assertEqual(len(union), 49 + 2 + 3 + 5)            # + B0 and E10, the three networks, the extension

    def test_every_pin_is_a_registered_p1_pin_except_the_networks_and_the_extension(self):
        """Review S-2: every pin of a line is pinned by a registered P1 line at the same sha256 (registration.job_pins),
        except the network file of a Q-network arm and the 5 extension sources of fl_global_shield; a registered code
        file or envelope that changed after registration is a problem of every line that pins it."""
        from framelease_v2 import gpu_queue as GQ
        from framelease_v4.arms import jobs_v4 as J
        from framelease_v4.arms_ext import arms_ext as X
        reg = REG.job_pins()
        for _, lines, _ in self.built:
            for j in lines:
                arm = self.arms[j['protocol_arm']]
                self.assertEqual(TJ.unregistered_pins(j['require_sha256'], arm, reg), [], j['id'])
                own = ({arm['network']['path']} if arm['network'] else set()) \
                    | (set(X.EXT_CODE) if arm['launcher'] == 'ext' else set())
                self.assertEqual(set(j['require_sha256']) - set(reg), own, j['id'])
        # a pinned code file that changed after registration (the tree reports another sha256): the lines pin the new
        # sha256, the tree agrees with them, and the registered P1 pins do not
        target = 'framelease_v4/arms/policies_v4.py'

        def fake(real):
            return lambda p: 'f' * 64 if str(p).endswith(target) else real(p)

        with mock.patch.object(J, 'sha256', fake(J.sha256)), mock.patch.object(GQ, 'sha256_file', fake(GQ.sha256_file)):
            arms = TJ.frozen_arms(self.tuning, self.rl)
            for blk in TJ.BLOCKS[2:5]:                          # a_lease (extension), a_rl (Q-network), s_seed12
                lines, _ = TJ.build_block(blk, arms, self.tuning, self.rl, {})
                self.assertEqual({j['require_sha256'][target] for j in lines}, {'f' * 64})
                probs = TJ.static_problems(blk, lines, arms, self.tuning, self.rl, {})
                self.assertEqual(len(probs), len(lines), blk['block'])
                self.assertTrue(all('registered P1 lines' in p and target in p for p in probs), probs[:2])
        # the envelope L* registered at another sha256 than the tree's: every line on L* is a problem
        blk, lines, _ = self.lines_of('ti_main')
        L = self.tuning['L']['path']
        with mock.patch.object(REG, 'job_pins', return_value={**reg, L: '0' * 64}):
            probs = TJ.static_problems(blk, lines, self.arms, self.tuning, self.rl, {})
        self.assertEqual({p.split(':')[0] for p in probs}, {j['id'] for j in lines if j['envelope']})
        self.assertTrue(all(L in p for p in probs))

    def test_q_network_lines_pin_the_network_file_at_its_absolute_path(self):
        from framelease_v4.protocol import check_smoke_ext as CSX
        from framelease_v4.rl import qnet as Q
        rl_doc = json.loads(self.B.rl_path.read_text())
        nets = {str((self.B.tmp / 'nets' / f'qnet_{f}.json').resolve()) for f in TJ.QNET_FAMILY.values()}
        seen = set()
        for _, lines, _ in self.built:
            for j in lines:
                a = j['protocol_arm']
                if a not in TJ.QNET_FAMILY:
                    self.assertFalse({'network', 'utility_env'} & set(j), j['id'])
                    self.assertNotIn('--utility-env', j['cmd'])
                    self.assertFalse(nets & set(j['require_sha256']), j['id'])
                    continue
                fam, line = TJ.QNET_FAMILY[a], rl_doc['job_lines'][a]
                path = line[Q.ENV_QNET]
                self.assertEqual(path, str((self.B.tmp / 'nets' / f'qnet_{fam}.json').resolve()))
                self.assertTrue(Path(path).is_absolute())               # finding QNET-1
                sha = PJ.sha256_file(path)
                self.assertEqual(sha, line['qnet_file_sha256'])
                self.assertEqual(TJ._utility_envs(j['cmd']), [f'{Q.ENV_QNET}={path}'])
                self.assertEqual(j['utility_env'], {Q.ENV_QNET: path})
                self.assertEqual((j['network']['family'], j['network']['name'], j['network']['abs_path'],
                                  j['network']['sha256']), (fam, line['utility'], path, sha))
                self.assertEqual(j['require_sha256'][j['network']['path']], sha)     # the FILE, not the name
                self.assertEqual((j['arm_name'], j['policy_params']), ('fl_full', {'utility': line['utility']}))
                self.assertEqual(CSX.qnet_line_problems(j), [])
                seen.add((a, fam, sha))
        self.assertEqual(len(seen), 3)
        self.assertEqual(len({s for _, _, s in seen}), 3)

    def test_a_network_with_the_same_name_and_another_b_pi_is_caught_by_the_file_pin(self):
        from framelease_v4.rl import qnet as Q
        with tempfile.TemporaryDirectory() as tmp:
            E = Env(tmp)
            tuning, rl, built = E.build()
            blk, lines, _ = next(x for x in built if x[0]['block'] == 'a_rl')
            self.assertEqual(TJ.static_problems(blk, lines, TJ.frozen_arms(tuning, rl), tuning, rl), [])
            net = rl['networks']['fl_bandit']
            spec = json.loads(Path(net['abs_path']).read_text())
            spec['policy_budget_s'] = 2 * float(spec['policy_budget_s'])
            Path(net['abs_path']).write_text(json.dumps(spec))
            self.assertEqual(Q.load_spec(net['abs_path'])['name'], net['name'])     # the name does not pin B_pi
            probs = TJ.static_problems(blk, lines, TJ.frozen_arms(tuning, rl), tuning, rl)
            bandit = [j['id'] for j in lines if j['protocol_arm'] == 'fl_bandit']
            self.assertTrue(all(any(p.startswith(f'{i}: pinned files differ') for p in probs) for i in bandit))
            self.assertFalse(any('fl_fqi_nolease' in p for p in probs))
            with self.assertRaises(ValueError):                 # the RL freeze names the file by its sha256
                E.load()

    def test_extension_sources_only_in_the_global_shield_lines(self):
        from framelease_v4.arms_ext import arms_ext as X
        from framelease_v4.arms_ext import run_closed_loop_ext as XL
        ext, L = set(X.EXT_CODE), self.tuning['L']
        n = 0
        for blk, lines, _ in self.built:
            for j in lines:
                if j['protocol_arm'] != 'fl_global_shield':
                    self.assertFalse(any(p.startswith('framelease_v4/arms_ext/') for p in j['require_sha256']))
                    self.assertNotIn('arms_ext', ' '.join(j['cmd']))
                    continue
                n += 1
                self.assertEqual(ext & set(j['require_sha256']), ext)
                self.assertEqual(j['require_sha256'], XL.job_pins(L['path']))
                ref = XL.job_line(j['route_id'], j['port'], j['output_dir'], L['path'], L['label'],
                                  utility='heuristic', job_id=j['id'], kappa=1.0, seed=11, wall_cap_s=1500, tier=5,
                                  phase='P6', block='a_lease', envelope_config=L['config'])
                keys = ('id', 'kind', 'tier', 'cmd', 'wall_cap_s', 'arm_name', 'protocol_arm', 'launcher',
                        'policy_params', 'envelope', 'kappa', 'seed', 'fast_prefix', 'route_id', 'port', 'output_dir',
                        'require_sha256', 'phase', 'block')
                self.assertEqual({k: j[k] for k in keys}, {k: ref[k] for k in keys})
                self.assertFalse({'--lease-overrides', '--lease-params', '--runtime-params'} & set(j['cmd']))
        self.assertEqual(n, 22)


def config_stub(job):
    """The fields of a run's config.json that aggregate_v4.protocol_label reads, as the launcher of the line writes
    them (v4_arm = the launcher arm, the envelope sha256, the Q-network's env file sha256, the extension block)."""
    if job['protocol_arm'] == 'fl_global_shield':
        return {'v4_arm': job['arm_name'], 'envelope_sha256': job['envelope']['sha256'],
                'v4': {'arm': job['arm_name'], 'extension': {'global_lease': {'h_bar_s': 2.5}}}}
    cfg = {'v4_arm': job['arm_name'], 'envelope_sha256': (job.get('envelope') or {}).get('sha256'), 'v4': {}}
    if job.get('network'):
        cfg['v4']['utility'] = {'env_files_sha256': {job['network']['abs_path']: job['network']['sha256']}}
    return cfg


class LabelsTest(Built):
    """GAP_AUDIT Sec. 2 "Recommended labelling": the protocol arm in the job line, the output directory and the block
    spec, as framelease_v4/analysis/aggregate_v4.py reads them."""

    def test_the_block_spec_names_every_job(self):
        for blk, lines, spec in self.built:
            self.assertEqual(len(spec['jobs']), len(lines))
            for i, (s, j) in enumerate(zip(spec['jobs'], lines)):
                self.assertEqual(set(s), set(TJ.SPEC_JOB_KEYS))
                net, env = j.get('network') or {}, j.get('envelope') or {}
                self.assertEqual(
                    (s['line'], s['id'], s['block'], s['protocol_arm'], s['launcher_arm'], s['launcher'],
                     s['route_id'], s['kappa'], s['seed'], s['config'], s['policy_params'], s['output_dir'],
                     s['port']),
                    (i + 1, j['id'], blk['block'], j['protocol_arm'], j['arm_name'], j['launcher'], j['route_id'],
                     j['kappa'], j['seed'], j['config'], j['policy_params'], j['output_dir'], j['port']))
                self.assertEqual((s['envelope_label'], s['envelope_sha256'], s['network_name'], s['network_family'],
                                  s['network_sha256']),
                                 (env.get('label'), env.get('sha256'), net.get('name'), net.get('family'),
                                  net.get('sha256')))
                if j['protocol_arm'] in TJ.QNET_FAMILY:
                    self.assertEqual(s['network_sha256'], PJ.sha256_file(net['abs_path']))
            for a, arm in spec['arms'].items():
                self.assertEqual(arm['output_dirs'], {f'{k:.1f}': TJ.output_dir(blk, self.arms[a], k)
                                                      for k in blk['kappas']})

    def test_the_aggregator_reads_the_labels(self):
        from framelease_v4.analysis import aggregate_v4 as AG
        with tempfile.TemporaryDirectory() as tmp:
            TJ.write_all(self.built, fake_checked(self.built), [], tmp, self.B.protocol, root=self.B.root)
            d = Path(tmp) / 'FULL'
            jobs, file_sha = [], {}
            for f in sorted(d.glob('*.jsonl')):
                file_sha[str(f)] = PJ.sha256_file(f)
                jobs += [(j, f, None) for j in AG.load_job_file(f)]
            self.assertEqual(len(jobs), 632)
            specs = [(f, json.loads(f.read_text())) for f in sorted(d.glob('*.stage.json'))]
            where, problems = AG.check_specs(specs, jobs, file_sha)
            self.assertEqual(problems, [])
            self.assertEqual(set(where), {j['id'] for j, _, _ in jobs})
            by_id = {j['id']: j for j, _, _ in jobs}
            for _, spec in specs:
                for jid, s in AG.spec_jobs(spec).items():
                    self.assertEqual(s['protocol_arm'], by_id[jid]['protocol_arm'])
        rl, tuning = AG.load_rl_freeze(self.B.rl_path), AG.load_tuning_freeze(self.B.sel)
        labels = {}
        for job, _, _ in jobs:
            sources = {AG.GLOBAL_SOURCE: 3} if job['protocol_arm'] == 'fl_global_shield' else {}
            arm, _, probs = AG.protocol_label(job, config_stub(job), sources, rl, tuning)
            self.assertEqual((arm, probs), (job['protocol_arm'], []), job['id'])
            labels[arm] = labels.get(arm, 0) + 1
            in_ablation = job['output_dir'].startswith('outputs/framelease_v4/ablation/')
            self.assertEqual(AG.output_dir_arm(job['output_dir']), job['protocol_arm'] if in_ablation else None)
            self.assertEqual(in_ablation, job['block'] in ('a_lease', 'a_rl', 's_risk'))
        self.assertEqual(labels, {'fixed_deep': 44 + 44 + 15, 'fast_only': 44 + 44 + 15, 'age_only': 44,
                                  'event_triggered': 44, 'fl_original': 44, 'fl_heuristic': 44 + 44 + 15,
                                  'fl_full': 44 + 44 + 15, 'fl_global_shield': 22, 'fl_bandit': 22,
                                  'fl_fqi_nolease': 22, 'fl_risk': 22})
        # a relabelled line is caught: the bandit network under protocol_arm fl_fqi_nolease
        job = copy.deepcopy(next(j for j, _, _ in jobs if j['protocol_arm'] == 'fl_bandit'))
        job['protocol_arm'] = 'fl_fqi_nolease'
        self.assertNotEqual(AG.protocol_label(job, config_stub(job), {}, rl, tuning)[2], [])

    def test_the_aggregator_loads_the_block_specs(self):
        """aggregate_v4.load_specs (aggregate_v4.py --specs outputs/framelease_v4/test_jobs/FULL) reads the written
        block specs as they are, with no patch. OPEN cross-item issue M-1 of the review (item AGG): this test fails
        while aggregate_v4.STAGE_SCHEMAS does not list test_jobs.STAGE_SCHEMA (framelease_v4.test_stage/1)."""
        from framelease_v4.analysis import aggregate_v4 as AG
        with tempfile.TemporaryDirectory() as tmp:
            TJ.write_all(self.built, fake_checked(self.built), [], tmp, self.B.protocol, root=self.B.root)
            d = Path(tmp) / 'FULL'
            try:
                specs = AG.load_specs([d])
            except AG.AggregateError as e:
                self.fail(f'OPEN cross-item issue M-1 (item AGG): aggregate_v4.STAGE_SCHEMAS {AG.STAGE_SCHEMAS} does '
                          f'not list {TJ.STAGE_SCHEMA}: {e}')
            self.assertEqual([f for f, _ in specs], sorted(d.glob('*.stage.json')))
            self.assertEqual({s['schema'] for _, s in specs}, {TJ.STAGE_SCHEMA})
            self.assertEqual(sum(len(AG.spec_jobs(s)) for _, s in specs), 632)


def set_opt(j, flag, value):
    """Change option `flag` of the line's command (and its line key where the line carries one)."""
    cmd = j['cmd']
    cmd[cmd.index(flag) + 1] = value
    key = {'--kappa': 'kappa', '--seed': 'seed', '--route-id': 'route_id', '--port': 'port',
           '--output-dir': 'output_dir'}.get(flag)
    if key:
        j[key] = {'kappa': float, 'seed': int, 'port': int}.get(key, str)(value)


class StaticChecksTest(Built):
    """test_jobs.static_problems / cross_block_problems catch every departure of a line from its block."""

    def problems(self, block, mutate, pick=lambda j: True):
        blk, lines, _ = self.lines_of(block)
        lines = copy.deepcopy(lines)
        k = next(i for i, j in enumerate(lines) if pick(j))
        mutate(lines[k])
        return lines[k]['id'], TJ.static_problems(blk, lines, self.arms, self.tuning, self.rl, self.cache)

    def setUp(self):
        self.cache = {}

    def test_clean_blocks(self):
        for built, tuning, rl in ((self.built, self.tuning, self.rl), (self.builtA, self.tuningA, self.rlA)):
            arms = TJ.frozen_arms(tuning, rl)
            for blk, lines, _ in built:
                self.assertEqual(TJ.static_problems(blk, lines, arms, tuning, rl, {}), [], blk['block'])
            self.assertEqual(TJ.cross_block_problems(built), [])

    def test_every_mutation_of_a_line_is_caught(self):
        from framelease_v4.rl import qnet as Q
        envs, train = PJ.envelopes(), next(iter(PJ.training_routes()))
        bandit = lambda j: j['protocol_arm'] == 'fl_bandit'     # noqa: E731
        cases = [
            ('ti_main', lambda j: set_opt(j, '--kappa', '1.5'), None, 'kappa 1.5'),
            ('f3_k', lambda j: set_opt(j, '--kappa', '1.0'), None, 'kappa 1.0'),
            ('s_seed12', lambda j: set_opt(j, '--seed', '11'), None, 'seed 11'),
            ('ti_main', lambda j: set_opt(j, '--seed', '12'), None, 'seed 12'),
            ('a_lease', lambda j: set_opt(j, '--route-id', train), None, 'is not a test route'),
            ('f3_k', lambda j: set_opt(j, '--route-id', SUBSET_R[1]), None, 'is not a test route of subset E'),
            ('s_seed12', lambda j: set_opt(j, '--route-id', SUBSET_E[1]), None, 'is not a test route of subset R'),
            ('ti_main', lambda j: j.update(training_route=True), None, 'is not a test route'),
            ('ti_main', lambda j: set_opt(j, '--port', '2610'), None, 'port'),
            ('ti_main', lambda j: j['require_sha256'].pop(sorted(j['require_sha256'])[0]), None,
             'require_sha256 is not the pin set'),
            ('a_rl', lambda j: j['require_sha256'].update({j['network']['path']: '0' * 64}), bandit,
             'pinned files differ from the tree'),
            ('a_rl', lambda j: j.update(protocol_arm='fl_fqi_nolease'), bandit, 'network'),
            ('ti_main', lambda j: j.update(protocol_arm='fl_bandit'), None, 'is not an arm of ti_main'),
            ('ti_main', lambda j: set_opt(j, '--output-dir', 'outputs/framelease_v4/ablation/fl_full'),
             lambda j: j['protocol_arm'] == 'fl_full', 'output directory'),
            ('a_rl', lambda j: set_opt(j, '--utility-env', f'{Q.ENV_QNET}=nets/qnet_bandit.json'), bandit, 'relative'),
            ('ti_main', lambda j: (j['cmd'].extend(['--envelope', envs['E5']['path']]),
                                   j.update(envelope={'label': 'E5', **envs['E5']})),
             lambda j: j['protocol_arm'] == 'fixed_deep', 'an envelope on an arm without a suffix lease'),
            ('ti_main', lambda j: set_opt(j, '--envelope', envs['E5']['path']),
             lambda j: j['protocol_arm'] == 'fl_heuristic', 'the envelope is not B0'),
            ('s_risk', lambda j: set_opt(j, '--envelope', envs['E5']['path']), None, 'the envelope is not E10'),
            ('ti_main', lambda j: set_opt(j, '--policy-params', '{"age_lease_s": 2.0, "utility": "heuristic"}'),
             lambda j: j['protocol_arm'] == 'age_only', '--policy-params / policy_params are not the frozen'),
            ('a_lease', lambda j: j['cmd'].__setitem__(2, PJ.LAUNCHER_REL), None, 'not the'),
            ('ti_main', lambda j: j.update(not_for_launch_before=None), None, 'not_for_launch_before'),
            ('ti_main', lambda j: j.update(tuning_freeze={'path': 'x', 'sha256': '0' * 64}), None,
             'freeze references differ'),
            ('ti_main', lambda j: j.update(id=j['id'] + 'x'), None, 'id !='),
            ('ti_main', lambda j: j.pop('wall_cap_s'), None, 'gpu_queue rejects the job'),
            ('ti_main', lambda j: j.update(tier=4), None, 'kind / tier / wall cap'),
            ('ti_main', lambda j: set_opt(j, '--timeout-s', '1500'), None, '--timeout-s'),
            ('ti_main', lambda j: j['cmd'].extend(['--lease-overrides', '{"T_pred": 2.0}']),
             lambda j: j['protocol_arm'] == 'fl_heuristic', 'the command is not the generated one'),
            ('a_lease', lambda j: j['cmd'].extend(['--lease-overrides', '{"T_pred": 2.0}']), None,
             'the command is not the generated one'),
            ('ti_main', lambda j: j['cmd'].extend(['--runtime-params', '{"max_depth": 4}']),
             lambda j: j['protocol_arm'] == 'fl_full', 'the command is not the generated one'),
        ]
        for block, mutate, pick, want in cases:
            jid, probs = self.problems(block, mutate, pick or (lambda j: True))
            self.assertTrue(any(p.startswith(f'{jid}:') and want in p for p in probs), (block, want, probs[:4]))

    def test_completeness_and_counts(self):
        blk, lines, _ = self.lines_of('a_rl')
        for what, mutate in (('dropped', lambda ls: ls.pop(3)), ('duplicated', lambda ls: ls.append(dict(ls[0]))),
                             ('moved', lambda ls: ls.insert(0, ls.pop(5)))):
            ls = copy.deepcopy(lines)
            mutate(ls)
            probs = TJ.static_problems(blk, ls, self.arms, self.tuning, self.rl, self.cache)
            self.assertTrue(probs, what)
            if what != 'moved':
                self.assertTrue(any('not every arm x kappa x route of the block once' in p for p in probs), what)
                self.assertTrue(any('runs of block A-rl in PROTOCOL Sec. 10.1' in p for p in probs), what)
        # s_risk lines although fl_risk is not run (L* = E5)
        blk, lines, _ = self.lines_of('s_risk')
        probs = TJ.static_problems(blk, lines, TJ.frozen_arms(self.tuningA, self.rlA), self.tuningA, self.rlA)
        self.assertTrue(any('is not an arm of s_risk' in p or 's_risk: 22 lines' in p for p in probs))

    def test_cross_block_problems(self):
        built = copy.deepcopy(self.built)
        self.assertEqual(TJ.cross_block_problems(built), [])
        dup = copy.deepcopy(built[0][1][0])
        built[4][1].append(dup)                                 # a Table I line again in s_seed12
        probs = TJ.cross_block_problems(built)
        self.assertTrue(any(p.startswith(f'{dup["id"]}: in ti_main and in s_seed12') for p in probs))
        self.assertTrue(any('output directory shared by' in p for p in probs))
        self.assertTrue(any('633 lines != 632 runs of PROTOCOL Sec. 10.1' in p for p in probs))
        built = copy.deepcopy(self.built)
        j = built[3][1][0]
        j['output_dir'] = built[2][1][0]['output_dir']          # an a_rl line in ablation/fl_global_shield
        self.assertTrue(any('output directory shared by' in p for p in TJ.cross_block_problems(built)))


@contextlib.contextmanager
def isolated_root(root):
    """test_jobs' test-route run guard (existing_runs, p2_jobs.runs_present) on `root` instead of the project root, for
    the code paths that use the default (main, write_all, check_lines)."""
    runs, present = TJ.existing_runs, P2J.runs_present

    def existing_runs(lines, root_=None, queue=TJ.QUEUE_REL):
        return runs(lines, root, queue)

    with mock.patch.object(TJ, 'existing_runs', existing_runs), \
            mock.patch.object(P2J, 'runs_present', lambda lines, root_=None: present(lines, root)):
        yield


def make_run(root, rel):
    """A run directory below root (a test-route run as the guard sees it: only its existence)."""
    d = Path(root) / rel
    d.mkdir(parents=True)
    return d


class FreezeRefusalTest(unittest.TestCase):
    def test_the_tuning_freeze_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            E = Env(Path(tmp) / 'a', cite=False)
            with self.assertRaises(PermissionError):                # not cited in Sec. 13.2
                E.tuning()
            E = Env(Path(tmp) / 'b', sealed=False)
            with self.assertRaises(PermissionError):                # PROTOCOL.md is not the sealed version
                E.tuning()
            self.assertEqual(E.tuning(seal=False)['L']['label'], 'B0')     # seal None: tests only
            E = Env(Path(tmp) / 'c')
            E.tuning()
            E.sel.write_text(E.sel.read_text() + ' ')
            with self.assertRaises(PermissionError):                # changed after its entry
                E.tuning()
            E.sel.unlink()
            with self.assertRaises(FileNotFoundError):
                E.tuning()

    def test_the_frozen_parameters_are_checked_against_their_grids(self):
        def bad(label='B0', **kw):
            doc = freeze_doc(label)
            for path, value in kw.items():
                *keys, last = path.split('__')
                d = doc
                for k in keys:
                    d = d[k]
                d[last] = value
            return doc
        e5 = PJ.envelopes()['E5']['path']
        cases = {'A* off the grid': (bad(A_star__age_lease_s=1.2, arms__age_only__policy_params__age_lease_s=1.2),
                                     r'A\*: .* is not an Age-Only candidate'),
                 'Age-Only utility is not a_det^d*': (bad(arms__age_only__policy_params__utility='v4_adet_d4'),
                                                      r'A\*: .* with utility heuristic'),
                 'event candidate not of the grid': (bad(event_star__candidate='s_hb3.0'), r'theta\*, A_hb\*'),
                 'event params differ from arms.event_triggered': (bad(arms__event_triggered__policy_params={
                     **PJ.THETA['v2'], 'heartbeat_s': 1.0}), r'differs from arms.event_triggered'),
                 'fl_heuristic not at L*': (bad(arms__fl_heuristic__envelope=e5), r'are not \(L\* = '),
                 'fl_full not at d*': (bad(arms__fl_full__a_det_depth=4), r'are not \(L\* = .*, d\* = 10\)'),
                 'fl_risk although L* is not B0': (bad('E5', fl_risk=dict(RISK_RECORD)), r'L\* = E5 is not B0'),
                 'L* = B0 without a fl_risk record': (bad(fl_risk=None), r'holds no fl_risk record'),
                 'fl_risk at B0': (bad(fl_risk__lease_point='B0'), r'is not an exported E5 / E10 envelope'),
                 'fl_risk at a point not exported': (bad(fl_risk__lease_point='E7'), r'not an exported E5 / E10'),
                 'TRIMMED': (bad(variant='TRIMMED'), r'variant .TRIMMED.')}
        with tempfile.TemporaryDirectory() as tmp:
            for i, (what, (doc, why)) in enumerate(cases.items()):
                E = Env(Path(tmp) / str(i), doc=doc)
                with self.assertRaisesRegex(ValueError, why, msg=what):
                    E.tuning()
            # L* = B0 and neither E5 nor E10 remains: accepted, fl_risk is not run, s_risk has no line
            E = Env(Path(tmp) / 'none', doc=bad(fl_risk__lease_point=None))
            tuning, rl, built = E.build()
            self.assertIsNone(tuning['risk'])
            self.assertIn('neither E5 nor E10', tuning['risk_reason'])
            self.assertEqual([len(x[1]) for x in built], [308, 176, 22, 44, 60, 0])
            self.assertEqual(TJ.cross_block_problems(built), [])

    def test_the_rl_freeze_must_be_the_production_freeze_of_this_tuning_freeze(self):
        from framelease_v4.rl import qnet as Q

        def other_line(d):
            d['job_lines']['fl_bandit'] = dict(d['job_lines']['fl_fqi_nolease'])

        cases = [('development record', PermissionError, lambda d: d.update(mode='development', frozen=False)),
                 ('not frozen', PermissionError, lambda d: d.update(frozen=False)),
                 ('other tuning freeze', ValueError, lambda d: d['tuning_freeze'].update(sha256='0' * 64)),
                 ('other d*', ValueError, lambda d: d['tuning_freeze'].update(d=4)),
                 ('other L*', ValueError, lambda d: d['tuning_freeze']['L_star'].update(sha256='0' * 64)),
                 ('relative network path', ValueError,
                  lambda d: d['job_lines']['fl_bandit'].update({Q.ENV_QNET: 'nets/qnet_bandit.json'})),
                 ('job line file sha256', ValueError, lambda d: d['job_lines']['fl_full'].update(
                     qnet_file_sha256='0' * 64)),
                 ('another family\'s network', ValueError, other_line),
                 ('a named file changed', ValueError, lambda d: d['files'].update(
                     {d['p2_manifest']['path']: '0' * 64})),
                 ('other schema', ValueError, lambda d: d.update(schema='framelease_v4.rl_freeze/0'))]
        with tempfile.TemporaryDirectory() as tmp:
            E = Env(tmp)
            tuning = E.tuning()
            for what, exc, mutate in cases:
                E.write_rl(mutate)
                with self.assertRaises(exc, msg=what):
                    TJ.load_rl(tuning, E.rl_path, E.protocol)
            E.write_rl()
            TJ.load_rl(tuning, E.rl_path, E.protocol)
            net = E.tmp / 'nets' / 'qnet_fqi.json'
            net.write_text(net.read_text() + ' ')                   # a network file changed after the freeze
            with self.assertRaises(ValueError):
                TJ.load_rl(tuning, E.rl_path, E.protocol)
            E.rl_path.unlink()
            with self.assertRaises(FileNotFoundError):
                TJ.load_rl(tuning, E.rl_path, E.protocol)


class RunGuardTest(Built):
    """No test-route run before the test freeze (PROTOCOL Secs. 8.1, 9.11; GAP_AUDIT G-1 'no run directory exists
    yet'): only the existence of a run directory or of a queue status record is read."""

    def test_existing_runs(self):
        lines = [j for _, ls, _ in self.built for j in ls]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(TJ.existing_runs(lines, root), [])
            (root / 'outputs/framelease_v4/matrix/fixed_deep/runs').mkdir(parents=True)      # empty runs/: no run
            q = root / TJ.QUEUE_REL
            q.mkdir(parents=True)
            (q / 'status.jsonl').write_text('')                                             # empty status: no job
            make_run(root, 'outputs/framelease_v4/rl_data/k1.0/runs/r1')                     # P2: training routes
            make_run(root, 'outputs/framelease_v4/tuning/lease_s1/runs/r1')                  # P1
            self.assertEqual(TJ.existing_runs(lines, root), [])
            self.assertEqual(TJ.run_problems(lines, root), [])
            (q / 'status.jsonl').write_text('{"id": "x", "state": "running"}\n')
            self.assertEqual(TJ.existing_runs(lines, root), [PJ.rel(q / 'status.jsonl')])
        for rel in ('matrix/fixed_deep', 'fig3/fl_full_k2.0', 'ablation/fl_bandit', 'ablation/another_arm',
                    'replicates/fast_only'):
            with tempfile.TemporaryDirectory() as tmp:
                runs = make_run(tmp, f'outputs/framelease_v4/{rel}/runs/20261120T000000Z_r1711').parent
                self.assertEqual(TJ.existing_runs(lines, tmp), [PJ.rel(runs)])
                self.assertIn('a test-route run exists', TJ.run_problems(lines, tmp)[0])

    def test_check_lines_reports_a_run_of_the_block_and_its_limits(self):
        blk, lines, _ = self.lines_of('a_rl')
        stub = lambda j, *a, **k: {'id': j['id'], 'problems': []}      # noqa: E731
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(TJ, 'check_in_process', stub), \
                mock.patch.object(TJ, 'check_ext_line', stub):
            _, probs = TJ.check_lines(blk, lines, self.arms, self.tuning, self.rl, dry_run=False, root=tmp)
            self.assertEqual(probs, [])
            make_run(tmp, lines[0]['output_dir'] + '/runs/r1')
            _, probs = TJ.check_lines(blk, lines, self.arms, self.tuning, self.rl, dry_run=False, root=tmp)
            self.assertEqual(len(probs), 1)
            self.assertIn('a test-route run exists in an output directory of a_rl', probs[0])
            for w in (0, 3):
                with self.assertRaises(ValueError):
                    TJ.check_lines(blk, lines, self.arms, self.tuning, self.rl, dry_run=False, workers=w, root=tmp)
            with mock.patch.object(PJ, '_stack_ready', return_value=False), self.assertRaises(SystemExit):
                TJ.check_lines(blk, lines, self.arms, self.tuning, self.rl, dry_run=True, root=tmp)


class WriteGuardTest(Built):
    def write(self, jobs_dir, built=None, protocol=None, root=None, force=False):
        built = built or self.built
        return TJ.write_all(built, fake_checked(built), TJ.cross_block_problems(built), jobs_dir,
                            protocol or self.B.protocol, force=force, root=root or self.B.root)

    def test_the_write_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for q in (tmp / 'queue_p4', tmp / 'x' / 'jobs.d'):             # a runner queue: refused
                with self.assertRaises(PermissionError):
                    self.write(q)
                self.assertFalse(q.exists())
            root = tmp / 'root'
            make_run(root, 'outputs/framelease_v4/ablation/fl_bandit/runs/r1')
            for force in (False, True):                                     # a test-route run: refused with force
                with self.assertRaises(PermissionError):
                    self.write(tmp / 'j0', root=root, force=force)
            self.assertFalse((tmp / 'j0').exists())
            info = self.write(tmp / 'j1')
            self.assertEqual([b['n_lines'] for b in info['blocks']], [308, 176, 22, 44, 60, 22])
            snap = {p: p.read_bytes() for p in sorted((tmp / 'j1').rglob('*')) if p.is_file()}
            self.assertEqual(len(snap), 19)
            other = copy.deepcopy(self.built)
            other[0][1][0]['config'] = 'changed'
            with self.assertRaises(FileExistsError):                        # other content without --force
                self.write(tmp / 'j1', other)
            self.assertEqual({p: p.read_bytes() for p in snap}, snap)       # nothing written
            prot = tmp / 'PROTOCOL.md'
            jf = TJ.block_paths(TJ.BLOCKS[0], tmp / 'j1')[0]
            prot.write_text(T2J.protocol_text(f'* P4 job file `{jf.name}` (sha256 `{PJ.sha256_file(jf)}`).'))
            self.assertEqual(len(TJ.recorded(jf, prot)), 1)
            with self.assertRaises(PermissionError):                        # a recorded file: refused with --force
                self.write(tmp / 'j1', other, protocol=prot, force=True)
            self.assertEqual({p: p.read_bytes() for p in snap}, snap)
            self.write(tmp / 'j1', other, force=True)                       # not recorded: --force rewrites
            self.assertNotEqual(jf.read_bytes(), snap[jf])
            self.write(tmp / 'j2')
            with self.assertRaises(FileExistsError):                        # fl_risk no longer run: stale s_risk files
                self.write(tmp / 'j2', self.builtA, force=True)
            self.write(tmp / 'j3', self.builtA)
            index = json.loads((tmp / 'j3/FULL/index.json').read_text())
            self.assertEqual((index['n_lines'], index['blocks'][5]['n_lines'], index['blocks'][5]['skipped']),
                             (610, 0, self.builtA[5][2]['skipped']))
            self.assertFalse(TJ.block_paths(TJ.BLOCKS[5], tmp / 'j3')[0].exists())


def stub_launchers(dry_problems=()):
    """The launcher layers of check_lines replaced by clean results (the real ones: LauncherTest, official stack):
    check_in_process, the --dry-run subprocess (p1_jobs.dry_run_line; NOT_STARTED) and check_ext_line."""
    def in_process(job):
        return {'id': job['id'], 'problems': [], 'agent_runtime_config_sha256': 'c' * 64}

    def dry(job, env):
        return {'status': 'NOT_STARTED'}, 'c' * 64, list(dry_problems)

    def ext(job, dry_run=True):
        return {'id': job['id'], 'problems': list(dry_problems), 'dry_run': {'status': 'NOT_STARTED'}}

    stack = contextlib.ExitStack()
    for target, name, value in ((TJ, 'check_in_process', in_process), (PJ, 'dry_run_line', dry),
                                (TJ, 'check_ext_line', ext), (PJ, '_stack_ready', lambda: True)):
        stack.enter_context(mock.patch.object(target, name, value))
    return stack


class CliTest(unittest.TestCase):
    def test_refusals_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            E = Env(Path(tmp) / 'a', cite=False)
            rc, out, err = E.main()
            self.assertEqual(rc, 2)
            self.assertIn('not cited in PROTOCOL.md Sec. 13.2', err)
            self.assertNotIn('Traceback', err)
            E.sel.unlink()
            self.assertIn('no tuning freeze yet', E.main()[2])
            E = Env(Path(tmp) / 'b')
            E.rl_path.unlink()
            rc, out, err = E.main()
            self.assertEqual((rc, 'no RL freeze yet' in err), (2, True))
            E = Env(Path(tmp) / 'c')
            E.write_rl(lambda d: d.update(mode='development', frozen=False))
            self.assertEqual(E.main()[0], 2)
            for bad in (['--write'], ['--check', '--write', '--no-dry-run'], ['--workers', '3'], ['--workers', '0']):
                with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(io.StringIO()):
                    E.main(*bad)
                self.assertEqual(cm.exception.code, 2, bad)
            E = Env(Path(tmp) / 'd')
            with isolated_root(E.root):
                rc, out, err = E.main()                                     # no --check: printed, nothing written
                self.assertEqual(rc, 0, err)
                self.assertIn('632 job lines', out)
                self.assertIn('NOT launched, NOT enqueued', out)
                self.assertFalse(E.jobs.exists())
                make_run(E.root, 'outputs/framelease_v4/matrix/fixed_deep/runs/r1')
                rc, out, err = E.main()
                self.assertEqual(rc, 0)
                self.assertIn('the job files can no longer be written', err)
                with stub_launchers():
                    rc, out, err = E.main('--check', '--write')
                self.assertEqual(rc, 1)                                     # a test-route run fails the check
                self.assertIn('a test-route run exists', err)
                self.assertFalse(E.jobs.exists())

    def test_check_and_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            E = Env(Path(tmp) / 'a')
            with isolated_root(E.root), stub_launchers():
                rc, out, err = E.main('--check', '--write')
                self.assertEqual(rc, 0, err)
                files = {p: p.read_bytes() for p in sorted(E.jobs.rglob('*')) if p.is_file()}
                self.assertEqual(len(files), 19)
                index = json.loads((E.jobs / 'FULL' / TJ.INDEX_NAME).read_text())
                self.assertEqual((index['schema'], index['n_lines'], index['queue'], index['cross_block_problems']),
                                 (TJ.INDEX_SCHEMA, 632, TJ.QUEUE_REL, []))
                self.assertEqual(index['script_sha256'], PJ.sha256_file(ROOT / 'framelease_v4/protocol/test_jobs.py'))
                for b, blk in zip(index['blocks'], TJ.BLOCKS):
                    paths = TJ.block_paths(blk, E.jobs)
                    self.assertEqual((b['block'], b['job_file_sha256'], b['stage_spec_sha256'], b['check_sha256']),
                                     (blk['block'], *(PJ.sha256_file(p) for p in paths)))
                    chk = json.loads(paths[2].read_text())
                    self.assertEqual((chk['schema'], chk['problems'], chk['all_dry_runs_ok'], chk['n_lines']),
                                     (TJ.CHECK_SCHEMA, [], True, b['n_lines']))
                    self.assertEqual(chk['job_file_sha256'], PJ.sha256_file(paths[0]))
                    spec = json.loads(paths[1].read_text())
                    self.assertEqual((spec['job_file'], spec['job_file_sha256']),
                                     (PJ.rel(paths[0]), PJ.sha256_file(paths[0])))
                rc, out, err = E.main('--check', '--write')                 # the same inputs: every byte kept
                self.assertEqual(rc, 0, err)
                self.assertEqual({p: p.read_bytes() for p in files}, files)
            with isolated_root(E.root), stub_launchers(['dry run exit 1: synthetic']):
                rc, out, err = E.main('--check', '--write')                 # a failed dry run: nothing written
                self.assertEqual(rc, 1)
                self.assertIn('CHECK FAILED', err)
                self.assertEqual({p: p.read_bytes() for p in files}, files)
            E.write_selection(freeze_doc('E5'))
            with isolated_root(E.root), stub_launchers():
                rc, out, err = E.main('--check', '--write')                 # other freezes: other content, refused
                self.assertEqual(rc, 2)
                self.assertIn('REFUSED', err)
                self.assertEqual({p: p.read_bytes() for p in files}, files)


@unittest.skipUnless(STACK, 'official stack variables not set (source linux/env.sh)')
class LauncherTest(Built):
    """The launchers themselves (run_closed_loop_v4.py; run_closed_loop_ext.py for fl_global_shield): the in-process
    parsing, configuration build and preflight, and the --dry-run of the exact command (writes nothing)."""

    def sample(self):
        seen, out = set(), []
        for blk, lines, _ in self.built:
            for j in lines:
                if (blk['block'], j['protocol_arm'], j['kappa']) not in seen:
                    seen.add((blk['block'], j['protocol_arm'], j['kappa']))
                    out.append(j)
        return out

    def test_one_line_of_every_block_arm_and_kappa_through_its_launcher(self):
        sample = self.sample()
        self.assertEqual(len(sample), 7 + 8 + 1 + 2 + 4 + 1)
        self.assertEqual({j['protocol_arm'] for j in sample}, set(self.arms))
        env = P2J._dry_run_env()
        for j in sample:
            before = (ROOT / j['output_dir']).exists()
            if j['launcher'] == TJ.EXT_LAUNCHER_REL:
                r = TJ.check_ext_line(j, dry_run=True)
            else:
                r = TJ.check_in_process(j)
                self.assertEqual(r['problems'], [], j['id'])
                self.assertEqual((float(r['kappa']), r['seed'], r['utility']),
                                 (j['kappa'], j['seed'], j['policy_params'].get('utility')))
                PJ._merge_dry_run(r, PJ.dry_run_line(j, dict(env)))
            self.assertEqual(r['problems'], [], j['id'])
            self.assertEqual(r['dry_run']['status'], 'NOT_STARTED', j['id'])
            self.assertEqual((ROOT / j['output_dir']).exists(), before)

    def test_the_launchers_refuse_what_they_must(self):
        _, lines, _ = self.lines_of('a_lease')
        j = copy.deepcopy(lines[0])
        j['cmd'] += ['--lease-overrides', '{"T_pred": 2.0}']               # the lease constants are fixed
        r = TJ.check_ext_line(j, dry_run=False)
        self.assertTrue(any('lease-overrides are refused' in p for p in r['problems']), r['problems'])
        _, lines, _ = self.lines_of('f3_k')
        j = copy.deepcopy(lines[0])
        set_opt(j, '--kappa', '1.0')
        j['kappa'] = 1.5                                                   # the line says 1.5, the command 1.0
        self.assertTrue(any('kappa / seed of the configuration' in p for p in TJ.check_in_process(j)['problems']))
        _, lines, _ = self.lines_of('a_rl')
        j = copy.deepcopy(lines[0])
        other = next(n for a, n in self.rl['networks'].items() if a != j['protocol_arm'])
        set_opt(j, '--utility-env', f'FRAMELEASE_V4_QNET={other["abs_path"]}')     # another family's network file
        probs = TJ.check_in_process(j)['problems']
        self.assertTrue(any(f'model {other["name"]} != expected {j["network"]["name"]}' in p for p in probs), probs)

    def test_check_lines_on_whole_blocks(self):
        for block in ('a_lease', 'a_rl'):
            blk, lines, _ = self.lines_of(block)
            results, probs = TJ.check_lines(blk, lines, self.arms, self.tuning, self.rl, dry_run=True, workers=2,
                                            root=self.B.root)
            self.assertEqual(probs, [], block)
            self.assertEqual([r['id'] for r in results], [j['id'] for j in lines])
            self.assertTrue(all(r['ok'] and r['dry_run']['status'] == 'NOT_STARTED' for r in results))
