"""Regression test of PROTOCOL Amendment A6 (framelease_v4/rl/ope.py): a candidate whose training fold cannot fit it.

The registered ope.select stops the whole family with ValueError when trainers.fit_candidate finds the a_det^{d*} head
(or every head) below min_support in a training fold (trainers._check_default_support, TreeQ.fit). PROTOCOL Secs.
5.5-5.6 define an unsupported candidate on the held-out data only (Sec. 5.5 "the held-out data", Sec. 5.6 rule 3
"held-out evaluation") and say nothing of a training fold. The fixed ope.select applies the same rule to the training
fold: it marks the candidate unsupported in that fold (ope.fit_support, record key 'fit_unsupported'), evaluates every
other candidate and fold as before, keeps the training-split guard of fit_candidate in every fold, and returns a
complete report. Toy SMDPs of helpers_rl.toy_dataset; CPU only, small
forests. Installed as framelease_v4/rl/tests/test_ope_support.py; it tests the ope.py of the tree it lies in (the
first parent directory holding framelease_v4/rl/ope.py):

    cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
        framelease_v4/rl/tests/test_ope_support.py
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock


def _tree_root():
    for p in Path(__file__).resolve().parents:
        if (p / 'framelease_v4' / 'rl' / 'ope.py').is_file():
            return p
    raise RuntimeError(f'no framelease_v4/rl/ope.py above {__file__}')


ROOT = _tree_root()
for _p in (ROOT / 'framelease_v4' / 'rl' / 'tests', ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import helpers_rl as H  # noqa: E402

import numpy as np  # noqa: E402

from framelease_v4.rl import features as F  # noqa: E402
from framelease_v4.rl import ope as O  # noqa: E402
from framelease_v4.rl import trainers as TR  # noqa: E402

REFINE, REFRESH = TR.REFINE, TR.REFRESH
DEPTH = F.NAMES.index('depth')
FQE = O.FQEConfig(n_estimators=5, min_samples_leaf=2, min_support=3, iter_cap=50)
SMALL = dict(min_samples_leaf=2, n_estimators=5)
# the keys of a fold record in the registered ope.select report (ope._eval_fold's record without 'V'); a supported
# fold keeps exactly these
FOLD_KEYS = {'candidate', 'fit_episodes', 'eval_episodes', 'delta', 'fqe_iterations', 'fqe_converged',
             'unsupported_frac', 'train_supported', 'eval_deviation_rate', 'eval_agreement_with_logged',
             'is_diagnostics'}


def concentrated_refresh(n_episodes=20, steps=10, seed=3, refresh_per_other_episode=0):
    """A toy dataset (10 routes, 2 episodes each) whose REFRESH samples sit in the routes of one fold.

    Fold f0 of the 5 route-grouped folds (ope.route_folds, seed 20261110) logs a_det^4 (REFRESH at depth >= 4); every
    other episode logs REFINE except `refresh_per_other_episode` REFRESH rows. With 0, the training fold of f0 holds no
    REFRESH sample at all while a_det^4 needs REFRESH there. Returns (ds, ids, folds, f0)."""
    ds = H.toy_dataset(n_episodes=n_episodes, steps=steps, eps=0.5, seed=seed)
    ids = ds.train_episode_ids()
    folds = O.route_folds(ds, ids, 5)
    f0 = 0
    A = ds.arrays['A']
    for e in ids:
        m = ds.EP == e
        if e in folds[f0]:
            A[m] = (ds.X[m][:, DEPTH] >= 4).astype(np.int8)
        else:
            a = np.zeros(int(m.sum()), np.int8)
            a[:refresh_per_other_episode] = REFRESH
            A[m] = a
    ds.arrays['MU'] = np.full(len(A), 0.5)
    return ds, ids, folds, f0


def fold_of(row, fold_eval_ids):
    """The fold record of a candidate row whose held-out episodes are fold_eval_ids."""
    return next(f for f in row['folds'] if sorted(f['eval_episodes']) == sorted(fold_eval_ids))


class ModuleTest(unittest.TestCase):
    def test_the_tested_module_is_the_tree_s_ope(self):
        self.assertEqual(Path(O.__file__).resolve(), (ROOT / 'framelease_v4' / 'rl' / 'ope.py').resolve())


class FitSupportTest(unittest.TestCase):
    def test_fit_support_is_false_exactly_when_fit_candidate_raises_for_support(self):
        """ope.fit_support against trainers.fit_candidate on 180 random folds: 'ok' False iff fit_candidate raises
        ValueError; both outcomes occur often, for every family."""
        rng = np.random.default_rng(20261112)
        outcomes = {f: [0, 0] for f in TR.FAMILIES}
        for trial in range(180):
            ds = H.toy_dataset(n_episodes=6, steps=6, eps=0.5, seed=int(rng.integers(1 << 30)))
            p_refresh = float(rng.choice([0.0, 0.03, 0.1, 0.5, 0.9, 1.0]))
            ds.arrays['A'] = (rng.uniform(size=ds.n) < p_refresh).astype(np.int8)
            family = TR.FAMILIES[trial % 3]
            cand = TR.Candidate(family, horizon=int(rng.integers(1, 3)), window='step', min_samples_leaf=1,
                                n_estimators=2, min_support=int(rng.choice([1, 3, 8, 20])),
                                d_det=int(rng.choice([1, 3, 5, 10])))
            fit_ids = sorted(rng.choice(6, size=int(rng.integers(1, 7)), replace=False).tolist())
            sup = O.fit_support(ds, fit_ids, cand)
            try:
                TR.fit_candidate(ds, fit_ids, cand)
                raised = False
            except ValueError:
                raised = True
            with self.subTest(trial=trial, family=family, support=sup):
                self.assertEqual(sup['ok'], not raised)
            outcomes[family][int(raised)] += 1
        for family, (n_ok, n_raised) in outcomes.items():
            self.assertGreaterEqual(n_ok, 10, family)
            self.assertGreaterEqual(n_raised, 10, family)

    def test_fit_support_record(self):
        ds, ids, folds, f0 = concentrated_refresh()
        fit = sorted(set(ids) - set(folds[f0]))
        sup = O.fit_support(ds, fit, TR.Candidate('fqi', horizon=2, min_support=5, d_det=4, **SMALL))
        n_refine = int(np.sum(ds.episode_mask(fit)))
        self.assertEqual(sup, {'n_samples': [n_refine, 0], 'min_support': 5, 'supported': [True, False],
                               'a_det_needs': [True, True], 'ok': False})
        sup10 = O.fit_support(ds, fit, TR.Candidate('fqi', horizon=2, min_support=5, d_det=10, **SMALL))
        self.assertEqual((sup10['a_det_needs'], sup10['ok']), ([True, False], True))     # a_det^10: REFINE only


class SelectionTest(unittest.TestCase):
    def test_a_family_whose_default_head_lacks_support_in_a_training_fold_completes(self):
        """Every family of the smoke grid at d* = 4: the training fold of f0 has no REFRESH sample. The registered
        ope.select raises ValueError; the fixed one returns a complete report, each candidate unsupported in f0 and
        not selectable, its other folds evaluated."""
        ds, ids, folds, f0 = concentrated_refresh()
        for family in TR.FAMILIES:
            cands = TR.grid(family, smoke=True, d_det=4)
            rep = O.select(ds, cands, ids, n_folds=5, fqe_cfg=FQE, n_boot=50)
            json.dumps(rep)                                     # the report stays JSON-able (p3_rl writes it)
            self.assertIsNone(rep['selected'], family)
            self.assertEqual(rep['n_folds'], 5)
            for row in rep['candidates']:
                with self.subTest(family=family, candidate=row['label']):
                    self.assertIsNone(row['mean_delta'])
                    self.assertGreaterEqual(row['unsupported_folds'], 1)
                    self.assertEqual(len(row['folds']), len(folds))
                    bad = fold_of(row, folds[f0])
                    self.assertEqual(bad['fit_unsupported']['n_samples'][REFRESH], 0)
                    self.assertFalse(bad['fit_unsupported']['ok'])
                    self.assertEqual((bad['fqe_iterations'], bad['fqe_converged'], bad['unsupported_frac']),
                                     (0, False, 1.0))
                    self.assertTrue(all(np.isnan(v) for v in bad['delta'].values()))
                    self.assertEqual(set(bad), FOLD_KEYS | {'fit_unsupported'})
                    for k, ev in enumerate(folds):
                        if k != f0:
                            other = fold_of(row, ev)
                            self.assertNotIn('fit_unsupported', other)          # fitted as before
                            self.assertEqual(set(other), FOLD_KEYS)
                            self.assertEqual(other['train_supported'], [True, True])

    def test_the_selection_continues_with_the_supported_candidates(self):
        """Two FQI candidates at d* = 4; the training fold of f0 holds 16 REFRESH samples: enough for min_support 5,
        not for min_support 20. The registered ope.select raises ValueError for the second; the fixed one marks it
        unsupported in f0 only (its other folds are fitted and evaluated) and selects the first."""
        ds, ids, folds, f0 = concentrated_refresh(refresh_per_other_episode=1)
        fit0 = sorted(set(ids) - set(folds[f0]))
        n_refresh = {k: int(np.sum(ds.A[ds.episode_mask(sorted(set(ids) - set(ev)))] == REFRESH))
                     for k, ev in enumerate(folds)}
        self.assertEqual(n_refresh[f0], len(fit0))                 # one REFRESH per episode outside f0
        self.assertLess(n_refresh[f0], 20)
        self.assertTrue(all(n >= 20 for k, n in n_refresh.items() if k != f0), n_refresh)
        lo = TR.Candidate('fqi', horizon=2, min_support=5, d_det=4, **SMALL)
        hi = TR.Candidate('fqi', horizon=3, min_support=20, d_det=4, **SMALL)
        rep = O.select(ds, [lo, hi], ids, n_folds=5, fqe_cfg=FQE, n_boot=50)
        rows = {r['label']: r for r in rep['candidates']}
        self.assertIsNotNone(rows[lo.label]['mean_delta'])
        self.assertIsNone(rows[hi.label]['mean_delta'])
        self.assertEqual(rows[hi.label]['unsupported_folds'], 1)
        self.assertEqual(rep['selected'], lo.label)
        bad = fold_of(rows[hi.label], folds[f0])
        self.assertEqual(bad['fit_unsupported']['n_samples'][REFRESH], n_refresh[f0])
        for k, ev in enumerate(folds):
            if k != f0:
                other = fold_of(rows[hi.label], ev)
                self.assertNotIn('fit_unsupported', other)
                self.assertGreater(other['fqe_iterations'], 0)
                self.assertTrue(all(np.isfinite(v) for v in other['delta'].values()))
        self.assertFalse(any('fit_unsupported' in f for f in rows[lo.label]['folds']))

    def test_a_supported_selection_keeps_the_registered_fold_records(self):
        ds = H.toy_dataset(n_episodes=20, steps=8, eps=0.5, seed=8)
        rep = O.select(ds, [TR.Candidate('fqi', horizon=2, min_support=5, **SMALL)], list(range(20)), n_folds=4,
                       fqe_cfg=FQE, n_boot=50)
        self.assertIsNotNone(rep['selected'])
        for f in rep['candidates'][0]['folds']:
            self.assertEqual(set(f), FOLD_KEYS)

    def test_a_non_training_episode_stops_the_selection_in_a_fold_without_a_fit(self):
        """The split guard of trainers.fit_candidate (PROTOCOL Sec. 3.3) holds in a fold that is not fitted: REFINE-only
        data, a_det^4 (needs REFRESH), one episode of ep_ids on the test split. No fold's fit data supports the
        candidate, so the fixed ope.select fits nothing; it still raises the PermissionError of fit_candidate, as the
        registered ope.select does."""
        ds = H.toy_dataset(n_episodes=10, steps=8, eps=0.5, seed=8)
        ds.arrays['A'][:] = REFINE
        ds.episodes[3]['split'] = 'test'
        ids = list(range(10))
        for ev in O.route_folds(ds, ids, 5):              # every fold: a_det^4 is REFRESH at a choice state of the fit
            fit = ds.episode_mask(sorted(set(ids) - set(ev)))
            self.assertTrue(np.any(TR.default_actions(ds.X[fit], 4) == REFRESH))
        for family in TR.FAMILIES:
            cand = TR.Candidate(family, horizon=2, min_support=5, d_det=4, **SMALL)
            with self.subTest(family=family):
                with self.assertRaisesRegex(PermissionError, r'^episodes \[3\] are not training episodes$'):
                    O.select(ds, [cand], ids, n_folds=5, fqe_cfg=FQE, n_boot=20)

    def test_another_value_error_of_the_fit_still_stops_the_selection(self):
        ds = H.toy_dataset(n_episodes=20, steps=8, eps=0.5, seed=8)
        with mock.patch.object(TR, 'fit_candidate', side_effect=ValueError('not a support failure')):
            with self.assertRaisesRegex(ValueError, 'not a support failure'):
                O.select(ds, [TR.Candidate('fqi', horizon=2, min_support=5, **SMALL)], list(range(20)), n_folds=4,
                         fqe_cfg=FQE, n_boot=50)


if __name__ == '__main__':
    unittest.main()
