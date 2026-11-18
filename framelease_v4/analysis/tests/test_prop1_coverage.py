"""Proposition-1 coverage of the deployed envelope (framelease_v4/analysis/prop1_coverage.py; PROTOCOL Secs. 4.3, 4.9,
7.4, 9.11, 9.13; GAP_AUDIT Sec. 3.7 row R-5). CPU only; the synthetic samples, envelopes, tuning freezes, protocol
copies, seals and outputs live in a temporary directory; the merged 37-clip view, the exported envelopes and their
manifests, the gate2 study, the registered route split and the development run (outputs/framelease_v4/build/R5/dev_run)
are only read.

  cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/analysis/tests/test_prop1_coverage.py

What is shown: an envelope that covers everything gives 1.0 and one that covers nothing gives 0.0 (every per-tau,
whole-path and sample coverage, the counts, the bootstrap intervals and the CSV rows, through compute); the counts of a
hand-made case (recorded taus only, whole path on [0, 3 s] and [0, 2.5 s], samples) equal coverage_summary and the
expected values; the clip bootstrap (point estimate, a class absent from a resample); the VAL / TRAIN split is never
mixed (the 32 VAL clips only, a TRAIN, calibration or unknown clip refused, the loader never asked for a TRAIN clip,
TRAIN samples cannot change the result); the deployed E* from the tuning freeze (absent, not cited, not sealed,
cited, L* = B0 with the fl_risk point, inconsistent); the Sec. 9.11 guard on clip route ids (refused before any clip is
read, released by a registered record, a development record never releases a registered test route; no real clip is
on a test route); the exported envelopes against their pins; the CLI refusals and its guard log; and on the real data
the result for the exported envelopes, with the registered 2000 resamples, reproduced byte for byte against the
development run.
"""
from __future__ import annotations

import hashlib
import json
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

import numpy as np  # noqa: E402

from framelease_v3 import envelopes as envmod  # noqa: E402
from framelease_v4.analysis import prop1_coverage as P  # noqa: E402
from framelease_v4.offline import common as C  # noqa: E402
from framelease_v4.protocol import select_stage as SS  # noqa: E402

TAU = P.tau_grid()
M = len(TAU)
GROUPS = P.GROUPS
DEV_RUN = ROOT / 'outputs/framelease_v4/build/R5/dev_run'
# PROTOCOL Sec. 4.3 (envelope files) and Sec. 12.2 (b)
PINS = {'E5': '21d0b4a441cf80e32e4f04ddeb9bf309b5a0a74c9495652fd04a88331c47df3a',
        'E10': 'bf61635ba3a38b7a307a4e1e4db4ad0541d7afc65cfd9afc432f9f054e1a2229',
        'B0': '9ef8479f04dab873d22b50e8732176804ed67f351f17584355b241e424fa1927'}
TRAIN = ['TrainA_Town01_Route1_Weather0', 'TrainB_Town02_Route2_Weather0']
VAL = ['ValA_Town03_Route11_Weather0', 'ValB_Town04_Route12_Weather0', 'ValC_Town05_Route13_Weather0']
LISTS = {'train': TRAIN, 'val': VAL}
NO_ROUTES = {'999999'}


def quiet(*_):
    pass


def iso_env(sigma, vbar=0.0, abar=0.0):
    return {'kind': 'iso', 'sigma_m': {g: float(sigma) for g in GROUPS}, 'vbar_mps': {g: float(vbar) for g in GROUPS},
            'abar_mps2': {g: float(abar) for g in GROUPS}}


def entry(label, env, calib=TRAIN):
    return {'path': f'synthetic/{label}.json', 'sha256': hashlib.sha256(label.encode()).hexdigest(),
            'config': f'cfg_{label}', 'lambda': None, 'of': None, 'calibration_clips': sorted(calib), 'env': env}


ALL_NONE = {'ALL': entry('ALL', iso_env(1e6)), 'NONE': entry('NONE', iso_env(-1.0))}


def samples(n_veh=40, n_ped=12, seed=0, low=0.05, high=3.0):
    """Synthetic compact samples: iso strictly positive; each pair is recorded up to a random tau (NaN after), the
    first pair of each class over the whole horizon."""
    rng = np.random.default_rng(seed)
    group = np.array([0] * n_veh + [1] * n_ped, dtype=np.int8)
    iso = rng.uniform(low, high, size=(len(group), M))
    for i in range(len(group)):
        if i not in (0, n_veh):
            iso[i, int(rng.integers(10, M + 1)):] = np.nan
    return {'group': group, 'iso': iso, 'npz_sha256': '0' * 64, 'gt_sha256': '1' * 64, 'dataset_split': 'val',
            'frames': 10, 'n_frames': 5}


class Loader:
    """A sample loader that records every clip it is asked for."""

    def __init__(self, make=None):
        self.asked = []
        self.make = make or (lambda name, i: samples(seed=i))

    def __call__(self, name, tau):
        self.asked.append(name)
        return self.make(name, len(self.asked))


def run(envs=ALL_NONE, lists=LISTS, load=None, n_boot=50, tuning_freeze=None, **kw):
    tf = tuning_freeze or Path(tempfile.gettempdir()) / 'r5_no_tuning_freeze_here.json'
    return P.compute(tuning_freeze=tf, n_boot=n_boot, seed=7, envs=envs, lists=lists, load=load or Loader(),
                     checks=('pooled',), routes=kw.pop('routes', NO_ROUTES), log=quiet, **kw)


def coverage_values(cov_class):
    """Every coverage of one class entry of coverage.json 'coverage' with n > 0, with its counts and interval."""
    cells = [v for v in cov_class['per_tau'].values()] + [cov_class[k] for k in P.PATH_KEYS]
    return [c for c in cells if c['n'] > 0]


# ============================================================================================ synthetic envelopes

class SyntheticEnvelopes(unittest.TestCase):
    def test_all_and_nothing(self):
        doc, tables = run()
        for g in GROUPS:
            all_cells = coverage_values(doc['coverage']['ALL'][g])
            none_cells = coverage_values(doc['coverage']['NONE'][g])
            self.assertEqual(len(all_cells), len(P.MARKS_S) + 3)
            for c in all_cells:
                self.assertEqual(c['coverage'], 1.0)
                self.assertEqual(c['covered'], c['n'])
                self.assertEqual(c['ci95'], [1.0, 1.0])
            for c in none_cells:
                self.assertEqual(c['coverage'], 0.0)
                self.assertEqual(c['covered'], 0)
                self.assertEqual(c['ci95'], [0.0, 0.0])
            s_all, s_none = doc['coverage_summary']['ALL'][g], doc['coverage_summary']['NONE'][g]
            for key in P.PATH_KEYS:
                self.assertEqual((s_all[key], s_none[key]), (1.0, 0.0))
            for t in s_all['per_tau']:
                self.assertEqual((s_all['per_tau'][t]['coverage'], s_none['per_tau'][t]['coverage']), (1.0, 0.0))
        self.assertTrue(doc['checks']['pooled']['pass'])
        for name, rows in tables.items():
            for r in rows:
                want = {'ALL': 1.0, 'NONE': 0.0}[r['envelope']]
                for key in ('coverage', 'path_coverage_0_3s', 'sample_coverage_all_tau', 'ci_lo', 'ci_hi'):
                    if key in r and r.get('n', r.get('n_pairs')) and r[key] is not None:
                        self.assertEqual(r[key], want, (name, r))
        self.assertTrue(all(r['n'] > 0 for r in tables['coverage.csv']))
        self.assertEqual(len(tables['per_tau.csv']), 2 * len(GROUPS) * M)

    def test_zero_envelope_on_positive_errors_is_zero(self):
        envs = {'B0like': entry('B0like', iso_env(0.0))}
        doc, _ = run(envs=envs)
        for g in GROUPS:
            for c in coverage_values(doc['coverage']['B0like'][g]):
                self.assertEqual(c['coverage'], 0.0)

    def test_hand_made_counts(self):
        """Pair A: covered except at tau 2.75 s; B: recorded to 1 s only; C: never recorded; D (pedestrian): uncovered
        at tau 0. Envelope B = 1 m at every tau."""
        iso = np.full((4, M), 0.5)
        iso[0, 55] = 2.0
        iso[1, 21:] = np.nan
        iso[2, :] = np.nan
        iso[3, 0] = 1.5
        S = {'group': np.array([0, 0, 0, 1], dtype=np.int8), 'iso': iso}
        inside, ok, gid = envmod.iso_inside(iso_env(1.0), S, TAU)
        cnt = P.clip_counts(inside, ok, gid, TAU)
        veh, ped = cnt[0], cnt[1]
        self.assertEqual(veh[M].tolist(), [1, 2])            # whole path [0, 3 s]: A fails at 2.75 s, B covered
        self.assertEqual(veh[M + 1].tolist(), [2, 2])        # [0, 2.5 s]: both covered
        self.assertEqual(veh[M + 2].tolist(), [81, 82])      # samples: A 60 of 61, B 21 of 21
        self.assertEqual(veh[0].tolist(), [2, 2])
        self.assertEqual(veh[55].tolist(), [0, 1])
        self.assertEqual(veh[60].tolist(), [1, 1])
        self.assertEqual(ped[0].tolist(), [0, 1])
        self.assertEqual(ped[10].tolist(), [1, 1])
        self.assertEqual(ped[M].tolist(), [0, 1])
        self.assertEqual(ped[M + 1].tolist(), [0, 1])
        self.assertEqual(ped[M + 2].tolist(), [60, 61])
        summ = envmod.coverage_summary(inside, ok, gid, TAU)
        self.assertEqual(P.pooled_check(summ, cnt, TAU), 0.0)
        self.assertEqual(summ['vehicle']['n_pairs'], 2)
        self.assertEqual(summ['vehicle']['path_coverage_0_3s'], 0.5)

    def test_pooled_equals_concatenation_across_clips(self):
        env = {'E': entry('E', iso_env(1.0, 0.3, 0.2))}
        parts = [(f'c{i}', samples(seed=i)) for i in range(4)]
        counts, summ, diffs = P.envelope_coverage(parts, env, TAU)
        self.assertEqual(diffs['E'], 0.0)
        cat = {'group': np.concatenate([p[1]['group'] for p in parts]),
               'iso': np.concatenate([p[1]['iso'] for p in parts])}
        ref = envmod.coverage_summary(*envmod.iso_inside(env['E']['env'], cat, TAU), TAU)
        self.assertEqual(summ['E'], ref)
        self.assertGreater(ref['vehicle']['sample_coverage_all_tau'], 0.0)
        self.assertLess(ref['vehicle']['sample_coverage_all_tau'], 1.0)

    def test_bootstrap(self):
        counts = np.zeros((2, 1, 2, 1, 2), dtype=np.int64)
        counts[0, 0, 0, 0] = (10, 10)                      # clip 0: vehicles all covered, 4 pedestrians, 1 covered
        counts[1, 0, 0, 0] = (0, 10)                       # clip 1: vehicles none covered, no pedestrian
        counts[0, 0, 1, 0] = (1, 4)
        point, lo, hi = P.bootstrap(counts, n_boot=400, seed=3)
        self.assertEqual(point[0, 0, 0], 0.5)
        self.assertEqual(point[0, 1, 0], 0.25)
        self.assertTrue(0.0 <= lo[0, 0, 0] <= 0.5 <= hi[0, 0, 0] <= 1.0)
        self.assertEqual((lo[0, 1, 0], hi[0, 1, 0]), (0.25, 0.25))    # resamples without clip 0 are left out
        again = P.bootstrap(counts, n_boot=400, seed=3)
        self.assertTrue(all(np.array_equal(a, b, equal_nan=True) for a, b in zip((point, lo, hi), again)))
        empty = np.zeros((2, 1, 2, 1, 2), dtype=np.int64)
        p, lo2, hi2 = P.bootstrap(empty, n_boot=10, seed=3)
        self.assertTrue(np.isnan(p).all() and np.isnan(lo2).all() and np.isnan(hi2).all())


# ============================================================================================ VAL / TRAIN split

class Split(unittest.TestCase):
    def test_real_lists_val_only(self):
        lists, envs = C.load_lists(), P.load_envelopes()
        chosen, complete = P.evaluation_clips(lists, envs)
        self.assertTrue(complete)
        self.assertEqual(chosen, lists['val'])
        self.assertEqual(len(chosen), 32)
        self.assertEqual(len(lists['train']), 5)
        self.assertFalse(set(chosen) & set(lists['train']))
        for e in envs.values():
            self.assertEqual(e['calibration_clips'], sorted(lists['train']))
        with self.assertRaisesRegex(P.CoverageError, 'TRAIN / calibration'):
            P.evaluation_clips(lists, envs, [lists['val'][0], lists['train'][0]])
        with self.assertRaisesRegex(P.CoverageError, 'not VAL clips'):
            P.evaluation_clips(lists, envs, ['NoSuchClip_Town01_Route5_Weather0'])
        sub, complete = P.evaluation_clips(lists, envs, [lists['val'][3], lists['val'][1], lists['val'][3]])
        self.assertEqual((sub, complete), ([lists['val'][1], lists['val'][3]], False))

    def test_inconsistent_lists_or_calibration_refused(self):
        with self.assertRaisesRegex(P.CoverageError, 'overlap'):
            P.evaluation_clips({'train': TRAIN, 'val': VAL + [TRAIN[0]]}, ALL_NONE)
        bad = {'E': entry('E', iso_env(1.0), calib=TRAIN + [VAL[0]])}
        with self.assertRaisesRegex(P.CoverageError, 'not on the TRAIN clips'):
            P.evaluation_clips(LISTS, bad)

    def test_train_samples_never_enter(self):
        """VAL samples are never covered by envelope E (iso 5 m > B = 1 m), TRAIN samples always (iso 0): the result is
        0.0 and the loader is asked for the VAL clips only."""
        def make(name, i):
            s = samples(seed=i)
            s['iso'] = np.where(np.isfinite(s['iso']), 0.0 if name in TRAIN else 5.0, np.nan)
            return s
        load = Loader(make)
        doc, _ = run(envs={'E': entry('E', iso_env(1.0))}, load=load)
        self.assertEqual(load.asked, VAL)
        self.assertEqual(doc['split']['clips'], VAL)
        self.assertEqual(doc['split']['train_clips_never_evaluated'], TRAIN)
        for g in GROUPS:
            for c in coverage_values(doc['coverage']['E'][g]):
                self.assertEqual(c['coverage'], 0.0)
        load = Loader(make)
        with self.assertRaises(P.CoverageError):
            run(load=load, clips=[VAL[0], TRAIN[1]])
        self.assertEqual(load.asked, [])


# ============================================================================================ deployed E*

def write_json(path, doc):
    Path(path).write_text(json.dumps(doc), encoding='utf-8')
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def protocol_copy(d, cite=None, seal_ok=True):
    """A development PROTOCOL.md copy (citing cite in Sec. 13) and its seal."""
    p = Path(d) / 'PROTOCOL.md'
    p.write_text('# P\n\n## 4. Arms\nnothing\n\n## 13. Registration and amendments\n'
                 + (f'tuning freeze sha256 {cite}\n' if cite else 'none\n') + '\n## 14. TRIMMED\n', encoding='utf-8')
    seal = Path(d) / 'SEAL.sha256'
    sha = hashlib.sha256(p.read_bytes()).hexdigest() if seal_ok else 'e' * 64
    seal.write_text(f'{sha}  {p}\n', encoding='utf-8')
    return p, seal


class Deployed(unittest.TestCase):
    ENVS = {lab: entry(lab, iso_env(s)) for lab, s in (('E5', 1.0), ('E10', 0.5), ('B0', 0.0))}

    def freeze_doc(self, label='E10', risk=None, **override):
        e = self.ENVS[label]
        doc = {'schema': SS.FREEZE_SCHEMA, 'variant': 'FULL',
               'L_star': {'label': label, 'envelope_path': e['path'], 'envelope_sha256': e['sha256'],
                          'validity': 'std'},
               'fl_risk': {'lease_point': risk, 'rule': 'test'} if risk else None}
        doc.update(override)
        return doc

    def test_no_freeze_all_three(self):
        with tempfile.TemporaryDirectory() as d:
            dep = P.deployed_envelopes(self.ENVS, Path(d) / 'selection.json')
        self.assertEqual(dep['status'], 'no_tuning_freeze')
        self.assertEqual(dep['deployed'], ['E5', 'E10', 'B0'])
        self.assertEqual(set(dep['roles'].values()), {P.ROLE_CAND})

    def test_not_cited_or_not_sealed(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'selection.json'
            sha = write_json(f, self.freeze_doc())
            for cite, seal_ok in ((None, True), (sha, False)):
                p, seal = protocol_copy(d, cite, seal_ok)
                dep = P.deployed_envelopes(self.ENVS, f, p, seal)
                self.assertEqual(dep['status'], 'tuning_freeze_not_cited')
                self.assertEqual(dep['deployed'], ['E5', 'E10', 'B0'])
                self.assertEqual(dep['tuning_freeze']['sha256'], sha)
                self.assertTrue(dep['warnings'])

    def test_cited_freeze(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'selection.json'
            sha = write_json(f, self.freeze_doc())
            p, seal = protocol_copy(d, sha)
            dep = P.deployed_envelopes(self.ENVS, f, p, seal)
            self.assertEqual(dep['status'], 'tuning_freeze')
            self.assertEqual(dep['deployed'], ['E10'])
            self.assertEqual(dep['roles'], {'E5': P.ROLE_OTHER, 'E10': P.ROLE_LSTAR, 'B0': P.ROLE_OTHER})
            self.assertFalse(dep['tuning_freeze']['registered_protocol'])
            self.assertIn('development copy', dep['warnings'][0])
            doc, tables = run(envs=self.ENVS, tuning_freeze=f, protocol=p, seal=seal)
            self.assertEqual({r['envelope'] for r in tables['coverage.csv'] if r['deployed']}, {'E10'})
            self.assertEqual(doc['envelopes']['E10']['role'], P.ROLE_LSTAR)
            self.assertEqual(doc['inputs'][P.PJ.rel(f)], sha)

    def test_b0_with_fl_risk(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'selection.json'
            sha = write_json(f, self.freeze_doc('B0', risk='E5'))
            p, seal = protocol_copy(d, sha)
            dep = P.deployed_envelopes(self.ENVS, f, p, seal)
        self.assertEqual(dep['deployed'], ['E5', 'B0'])
        self.assertEqual(dep['roles'], {'E5': P.ROLE_RISK, 'E10': P.ROLE_OTHER, 'B0': P.ROLE_LSTAR})

    def test_inconsistent_freeze_refused(self):
        bad_lstar = {'label': 'E10', 'envelope_path': 'synthetic/E10.json', 'envelope_sha256': 'f' * 64}
        cases = (('schema', self.freeze_doc(schema='other/1')),
                 ('not the exported', self.freeze_doc(L_star=bad_lstar)),
                 ('not a kept', self.freeze_doc(L_star={'label': 'E7'})),
                 ('fl_risk lease point', self.freeze_doc('B0', risk='E99')))
        with tempfile.TemporaryDirectory() as d:
            for msg, doc in cases:
                f = Path(d) / 'selection.json'
                write_json(f, doc)
                with self.assertRaisesRegex(P.CoverageError, msg):
                    P.deployed_envelopes(self.ENVS, f)


# ============================================================================================ interim-look guard

class Guard(unittest.TestCase):
    TEST_CLIP = 'ParkingCutIn_Town12_Route1711_Weather0'

    def test_refused_before_freeze(self):
        with self.assertRaises(P.GuardRefused):
            P.guard_clips([VAL[0], self.TEST_CLIP], routes={'1711'})
        with self.assertRaises(P.GuardRefused):                 # no route id: guarded
            P.guard_clips(['SomeClipWithoutRoute'], routes={'1711'})
        doc = P.guard_clips(VAL, routes={'1711'})
        self.assertEqual((doc['status'], doc['guarded_clips']), ('pre_freeze', []))

    def test_release(self):
        reg = {'path': 'r.json', 'sha256': 'f' * 64, 'frozen': 'now', 'registered': True}
        doc = P.guard_clips([self.TEST_CLIP], freeze=reg, routes={'1711'})
        self.assertEqual((doc['status'], doc['released_clips']), ('frozen', [self.TEST_CLIP]))
        dev = {**reg, 'registered': False}
        with self.assertRaisesRegex(P.GuardRefused, 'development record'):
            P.guard_clips([self.TEST_CLIP], freeze=dev, routes={'1711'}, registered={'1711'})
        doc = P.guard_clips([self.TEST_CLIP], freeze=dev, routes={'1711'}, registered={'2000'})
        self.assertEqual((doc['status'], doc['released_clips']), ('frozen_development', [self.TEST_CLIP]))

    def test_compute_refuses_before_reading(self):
        lists = {'train': TRAIN, 'val': VAL + [self.TEST_CLIP]}
        load = Loader()
        with self.assertRaises(P.GuardRefused):
            run(lists=lists, load=load, routes={'1711'})
        self.assertEqual(load.asked, [])

    def test_real_clips_not_on_test_routes(self):
        lists = C.load_lists()
        doc = P.guard_clips(lists['all'])
        self.assertEqual(doc['guarded_clips'], [])
        self.assertEqual(doc['test_routes']['n_registered'], 44)
        self.assertTrue(all(P.clip_route(c) for c in lists['all']))


# ============================================================================================ exported envelopes

class Envelopes(unittest.TestCase):
    def test_pinned_files(self):
        envs = P.load_envelopes()
        self.assertEqual(list(envs), ['E5', 'E10', 'B0'])
        self.assertEqual({k: v['sha256'] for k, v in envs.items()}, PINS)
        self.assertEqual([envs[k]['config'] for k in envs], ['T_x0.60', 'T_x0.30', 'T_x0.00'])
        self.assertTrue(all(v == 0.0 for p in P.ENV_PARAMS for v in envs['B0']['env'][p].values()))
        link = P.envelope_link(envs)
        self.assertTrue(link['pass'], link)

    def test_changed_file_refused(self):
        src = ROOT / 'outputs/framelease_v4/envelopes/E5.json'
        with tempfile.TemporaryDirectory() as d:
            doc = json.loads(src.read_text(encoding='utf-8'))
            doc['sigma_m']['vehicle'] += 0.01
            f = Path(d) / 'E5.json'
            sha = write_json(f, doc)
            with self.assertRaisesRegex(P.CoverageError, 'manifest sha256'):
                P.load_envelopes({'E5': {'path': str(f), 'sha256': PINS['E5'], 'config': 'T_x0.60'}})
            with self.assertRaisesRegex(P.CoverageError, 'registration manifest'):
                P.load_envelopes({'E5': {'path': str(f), 'sha256': sha, 'config': 'T_x0.60'}})
            env = P.load_envelopes({'E5': {'path': str(f), 'sha256': sha, 'config': 'T_x0.60'}}, manifest=None)
            self.assertFalse(P.envelope_link(env)['pass'])


# ============================================================================================ CLI

def sums_ok(out):
    for line in (Path(out) / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        sha, name = line.split('  ', 1)
        if hashlib.sha256((Path(out) / name).read_bytes()).hexdigest() != sha:
            return False
    return True


def log_entries(out):
    p = Path(out) / 'interim_guard.jsonl'
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()] if p.is_file() else []


class Cli(unittest.TestCase):
    def test_protected_out_refused_without_log(self):
        out = ROOT / 'outputs/framelease_v4/envelopes/r5_test_never_written'
        self.assertEqual(P.main(['--out', str(out), '--clips', C.load_lists()['val'][0]]), 1)
        self.assertFalse(out.exists())

    def test_cli_subset_and_refusals(self):
        val = C.load_lists()['val']
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'sub'
            self.assertEqual(P.main(['--out', str(out), '--clips', val[2], val[0], '--n-boot', '20',
                                     '--tuning-freeze', str(Path(d) / 'none.json')]), 0)
            self.assertTrue(sums_ok(out))
            self.assertEqual(sorted(p.name for p in out.iterdir()), sorted(P.OUTPUT_FILES + ('interim_guard.jsonl',)))
            doc = json.loads((out / 'coverage.json').read_text(encoding='utf-8'))
            self.assertFalse(doc['complete'])
            self.assertEqual(doc['split']['clips'], [val[0], val[2]])
            self.assertIsNone(doc['checks']['gate2']['pass'])
            self.assertTrue(all(doc['checks'][k]['pass'] for k in ('inputs', 'envelope_link', 'pooled')))
            self.assertEqual([e['decision'] for e in log_entries(out)], ['granted'])
            self.assertEqual(P.main(['--out', str(out), '--clips', val[0]]), 1)       # outputs exist, no --force
            self.assertEqual([e['decision'] for e in log_entries(out)], ['granted', 'refused'])
            bad = Path(d) / 'bogus_record.json'
            bad.write_text('{"schema": "x"}', encoding='utf-8')
            out2 = Path(d) / 'guard'
            self.assertEqual(P.main(['--out', str(out2), '--clips', val[0], '--analysis-freeze', str(bad)]), 4)
            self.assertEqual([e['decision'] for e in log_entries(out2)], ['refused'])
            self.assertFalse((out2 / 'coverage.json').exists())
            out3 = Path(d) / 'train'
            self.assertEqual(P.main(['--out', str(out3), '--clips', C.load_lists()['train'][0]]), 2)
            self.assertFalse((out3 / 'coverage.json').exists())


# ============================================================================================ real data: reproducible

class Reproducible(unittest.TestCase):
    """The exported envelopes on the 32 VAL clips with the registered 2000 resamples, recomputed here and compared
    byte for byte with the development run (its own process, earlier)."""

    RESULT_KEYS = ('complete', 'split', 'settings', 'envelopes', 'coverage', 'coverage_summary', 'clips', 'checks')

    def test_reproduces_development_run(self):
        if not (DEV_RUN / 'coverage.json').is_file():
            self.skipTest(f'no development run in {DEV_RUN}')
        self.assertTrue(sums_ok(DEV_RUN))
        ref = json.loads((DEV_RUN / 'coverage.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as d:
            tf = ref['arguments']['tuning_freeze']
            if ref['deployed']['status'] == 'no_tuning_freeze':
                tf = Path(d) / 'no_tuning_freeze.json'
            doc, tables = P.compute(tuning_freeze=tf, log=quiet)
            self.assertEqual((doc['settings']['bootstrap']['resamples'], doc['settings']['bootstrap']['seed']),
                             (2000, 20261109))
            self.assertTrue(doc['complete'])
            self.assertEqual(doc['split']['n_clips'], 32)
            self.assertEqual({k: v['sha256'] for k, v in doc['envelopes'].items()}, PINS)
            self.assertTrue(all(v['pass'] for v in doc['checks'].values()), doc['checks'])
            self.assertEqual(doc['checks']['gate2']['max_abs_diff'],
                             {n: 0.0 for n in P.GATE2_VAL_ENVELOPES})
            out = Path(d) / 'again'
            P.write_outputs(out, doc, tables)
            for name in tables:
                self.assertEqual((out / name).read_bytes(), (DEV_RUN / name).read_bytes(), name)
            again = json.loads((out / 'coverage.json').read_text(encoding='utf-8'))
            for key in self.RESULT_KEYS:
                self.assertEqual(again[key], ref[key], key)
        for g in GROUPS:                                  # B0 is the zero-error assumption: nothing is covered
            self.assertEqual(ref['coverage']['B0'][g]['path_coverage_0_3s']['coverage'], 0.0)


if __name__ == '__main__':
    unittest.main()
