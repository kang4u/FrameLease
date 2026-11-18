"""Figures of the v4 method paper (framelease_v4/analysis/figures_tables.py; PROTOCOL Secs. 7.1, 7.3, 9.9, 9.11, 9.13;
GAP_AUDIT Sec. 3.7 row R-6). CPU only. The analysis is synthetic: analyze_v4.main on synthetic route ids
920000-920043 with the registered scenario types (small bootstrap counts), in a temporary directory that also holds
every output; the Fig. 1 files of the offline ablation (computed before registration), the registered route split, its
manifest and PROTOCOL.md are only read.

  cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/analysis/tests/test_figures_tables.py

What is shown: the palette separates the series a figure shows together under simulated protan, deutan and tritan
vision (OKLab Delta E, Machado 2009 matrices) and in normal vision, and the type is IEEE's; numbers.json refuses a key
written twice with different contents; an analysis whose files differ from its SHA256SUMS or analysis.json is refused;
the Sec. 9.11 check refuses results on a registered test route without a valid registered analysis-freeze record
(cells.csv edited onto a registered route, a guard document with test-route rows, a record that does not exist),
--require-registered refuses a development analysis, and an inconsistent status is an error; every Fig. 1, Fig. 3 and
Table I number equals its source row (the release-age interpolation and the v2 kappa-2.0 means by hand); a condition
without rows becomes a point with n 0 and the figure still renders; Table I escapes LaTeX text and compiles with
IEEEtran and booktabs without an overfull box; the command line writes vector PDFs at the IEEE widths with embedded
TrueType fonts, PNGs at 300 dpi, the LaTeX table, numbers.json, figures.json and SHA256SUMS, byte-identical on a second
run, stamps development figures, logs every request and refuses occupied, protected or input directories.
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.text  # noqa: F401
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ.setdefault('MPLBACKEND', 'Agg')
sys.dont_write_bytecode = True

import test_analyze_v4 as T  # noqa: E402

from framelease_v4.analysis import analyze_v4 as AN  # noqa: E402
from framelease_v4.analysis import figures_tables as FT  # noqa: E402
from framelease_v4.analysis import interim_guard as G  # noqa: E402

OFFLINE_FIG1 = ROOT / FT.OFFLINE_REL / FT.FIG1_REL
NO_ANALYSIS_TEXT = 'no analysis given'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows_of(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


# ============================================================================== colour separation (OKLab x 100)

CVD = {'protan': ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
       'deutan': ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
       'tritan': ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900))}


def _linear(hexcol):
    c = np.array([int(hexcol[i:i + 2], 16) / 255.0 for i in (1, 3, 5)])
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _oklab(rgb):
    lms = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                    [0.0883024619, 0.2817188376, 0.6299787005]]) @ np.clip(rgb, 0.0, 1.0)
    return np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                     [0.0259040371, 0.7827717662, -0.8086757660]]) @ np.cbrt(lms)


def delta_e(a, b, mode=None):
    """OKLab Delta E x 100 between two colours, in normal vision or under a simulated dichromacy (severity 1)."""
    x, y = _linear(a), _linear(b)
    if mode:
        x, y = np.array(CVD[mode]) @ x, np.array(CVD[mode]) @ y
    return 100.0 * float(np.linalg.norm(_oklab(x) - _oklab(y)))


def worst(colours):
    pairs = list(itertools.combinations(colours, 2))
    return (min(delta_e(a, b) for a, b in pairs), min(delta_e(a, b, m) for a, b in pairs for m in CVD))


# ============================================================================== the synthetic analysis

AGE = {'fixed_deep': 0.78, 'fast_only': 0.52, 'age_only': 0.6, 'event_triggered': 0.66, 'fl_original': 0.7,
       'fl_heuristic': 0.86, 'fl_full': 0.82, 'fl_global_shield': 0.8, 'fl_bandit': 0.84, 'fl_fqi_nolease': 0.83,
       'fl_risk': 0.9}
GPU = {'fixed_deep': 0.97, 'fast_only': 0.99, 'age_only': 0.9, 'event_triggered': 0.7, 'fl_original': 0.75,
       'fl_heuristic': 0.62, 'fl_full': 0.6, 'fl_global_shield': 0.64, 'fl_bandit': 0.61, 'fl_fqi_nolease': 0.6,
       'fl_risk': 0.55}
F3_ARMS = ('fl_full', 'fixed_deep', 'fast_only', 'fl_heuristic')


def _per_route(values):
    return lambda i: float(values[i])


SHIELD_ARMS = ('age_only', 'fl_heuristic', 'fl_full', 'fl_global_shield', 'fl_bandit', 'fl_fqi_nolease', 'fl_risk')
RL_ARMS = ('fl_full', 'fl_bandit', 'fl_fqi_nolease')


def _overhead(arm, kappa, j):
    """The per-run log columns of Sec. 7.6 panel B for a shield arm (aggregate_v4 runs.csv names): deterministic in
    the route index i, with one Q-network p99 above B_pi (route 0 of Full FrameLease at kappa 2.0)."""
    k = kappa
    out = {'decision_wall_s_p50': lambda i: 1.1e-4 * k + 1e-7 * i,
           'decision_wall_s_p99': lambda i: 2.0e-4 * k + 2e-7 * i,
           'lease_wall_s_p50': lambda i: 1.4e-3 + 1e-6 * i, 'lease_wall_s_p99': lambda i: 2.6e-3 + 2e-6 * i,
           'prefix_quantum_s_p50': lambda i: 0.42 * k, 'prefix_quantum_s_p99': lambda i: 0.45 * k + 1e-4 * i,
           'step_quantum_s_p50': lambda i: 0.0146 * k, 'step_quantum_s_p99': lambda i: 0.02 * k,
           'switching_latency_s_p50': lambda i: 0.002 + 1e-5 * j, 'switching_latency_s_p99': lambda i: 0.006,
           'cancelled_gpu_share': lambda i: 0.05 + 0.001 * (i % 5), 'validation_s_p50': lambda i: 3e-5,
           'validation_s_p99': lambda i: 8e-5 + 1e-7 * i, 'budget_overrun_ratio': lambda i: 0.0,
           'budget_overruns': lambda i: int(i == 3), 'shield_violations': lambda i: 0,
           'fallback_episodes': lambda i: i % 3, 'bypass_epochs': lambda i: i % 2, 'gate_rejects': lambda i: 2,
           'gate_rejects_by_reason': lambda i: json.dumps({'expired_before_commit': 1, 'stale_version:not_deeper': 1}),
           'bypass_by_reason': lambda i: json.dumps({'slack': i % 2}), 'cancelled_gpu_s': lambda i: 0.5}
    if arm in RL_ARMS:
        out.update(qnet_s_p50=lambda i: 1.2e-5 + 1e-8 * i,
                   qnet_s_p99=lambda i: 1.5e-4 if (arm, k, i) == ('fl_full', 2.0, 0) else 2.5e-5 + 1e-8 * i)
    return out


def _extra(arms, kappa, seed):
    """Per-arm, per-kappa action ages, EIR and GPU usage (fixed generators); the log columns of the shield arms."""
    out = {}
    for j, arm in enumerate(arms):
        rng = np.random.default_rng(1000 + 10 * j + int(10 * kappa) + seed)
        p50 = np.clip(AGE[arm] * kappa ** 0.8 + rng.normal(0.0, 0.05, 44), 0.2, None).round(3)
        p95 = (p50 + 0.35 * kappa + np.abs(rng.normal(0.0, 0.1, 44))).round(3)
        eir = np.clip(0.004 * kappa * (1 + j % 3) + rng.normal(0.0, 0.003, 44), 0.0, None).round(4)
        gpu = np.clip(GPU[arm] / kappa ** 0.15 + rng.normal(0.0, 0.02, 44), 0.0, 1.0).round(4)
        out[arm] = {'action_age_p50_s': _per_route(p50), 'action_age_p95_s': _per_route(p95),
                    'realized_invalid_tick_ratio': _per_route(eir), 'gpu_usage': _per_route(gpu),
                    **(_overhead(arm, kappa, j) if arm in SHIELD_ARMS else {})}
    return out


def synthetic_rows():
    """Every registered cell: Table I x 44, the Fig. 3 arms at kappa 1.5 / 2.0 on E, the ablation arms on E, seed 12
    on R; synthetic route ids with the registered scenario types (test_analyze_v4.TABLE_B2D)."""
    table = T.TABLE_B2D
    E, R = table['subsets']['E'], table['subsets']['R']
    rows = T.matrix({a: T.noisy(5 * k, 100 + k) for k, a in enumerate(T.TABLE_I)}, arms=T.TABLE_I,
                    routes=table['routes'], extra=_extra(T.TABLE_I, 1.0, 11))
    for kap, shift in ((1.5, -6), (2.0, -12)):
        rows += T.matrix({'fl_full': T.noisy(10 + shift, 200 + int(kap * 10)), 'fixed_deep': T.noisy(shift - 4, 201),
                          'fast_only': T.noisy(shift, 202 + int(kap * 10)), 'fl_heuristic': T.noisy(3 + shift, 203)},
                         arms=F3_ARMS, kappa=kap, routes=E, extra=_extra(F3_ARMS, kap, 11))
    ab = ('fl_global_shield', 'fl_bandit', 'fl_fqi_nolease', 'fl_risk')
    rows += T.matrix({a: T.noisy(0, 300 + j) for j, a in enumerate(ab)}, arms=ab, routes=E, extra=_extra(ab, 1.0, 11))
    rows += T.matrix({'fl_full': T.noisy(10, 400), 'fixed_deep': T.noisy(0, 401), 'fast_only': T.noisy(0, 402),
                      'fl_heuristic': T.noisy(3, 403)}, arms=F3_ARMS, seed=12, routes=R, extra=_extra(F3_ARMS, 1.0, 12))
    for j, r in enumerate(rows):
        r.update(collisions_total=j % 3, km_driven=(0.0 if j % 17 == 0 else 0.4 + (j % 7) / 5))
    return rows


def resign(d, doc_edit=None, table_edit=None):
    """Edit a copied analysis (doc_edit(doc) in place; table_edit: {table: function(rows) -> rows}) and make
    analysis.json 'outputs' and SHA256SUMS agree with the files again."""
    d = Path(d)
    doc = json.loads((d / 'analysis.json').read_text(encoding='utf-8'))
    for name, fn in (table_edit or {}).items():
        rows = rows_of(d / name)
        cols = list(rows[0])
        rows = fn(rows)
        with open(d / name, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        doc['outputs'][name] = sha(d / name)
    if doc_edit:
        doc_edit(doc)
    (d / 'analysis.json').write_text(json.dumps(doc, indent=1, sort_keys=True), encoding='utf-8')
    names = [n for n in AN.read_sums(d / 'SHA256SUMS')]
    (d / 'SHA256SUMS').write_text(''.join(f'{sha(d / n)}  {n}\n' for n in names), encoding='utf-8')
    return d


# ============================================================================== synthetic sources of Tables II

TRAIN_IDS = ('930001', '930002', '930003')        # synthetic training route ids (no registered route)


def write_json(path, doc):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding='utf-8')
    return path


COV_ENVS = ('E5', 'E10', 'B0')


def write_coverage(d, status='no_tuning_freeze', guarded=()):
    """A prop1_coverage.py output directory with synthetic coverages (coverage.csv: per_tau at 0-3 s in 0.5 s steps,
    the two whole-path metrics), coverage.json and SHA256SUMS."""
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    rows = []
    for e, env in enumerate(COV_ENVS):
        for c, cls in enumerate(('vehicle', 'pedestrian')):
            base = {'envelope': env, 'config': f'T_x{0.6 - 0.3 * e:.2f}', 'envelope_sha256': '0' * 64,
                    'role': 'candidate', 'deployed': True, 'class': cls}
            for t in range(7):
                cov = round(0.9 - 0.1 * e - 0.01 * t - 0.02 * c, 4)
                rows.append({**base, 'metric': 'per_tau', 'tau_s': f'{0.5 * t:.1f}', 'n': 1000 - t,
                             'covered': round(cov * (1000 - t)), 'coverage': cov, 'ci_lo': round(cov - 0.05, 4),
                             'ci_hi': round(cov + 0.04, 4), 'clips_with_n': 32, 'clips': 32, 'complete': True})
            for m, cov in (('path_coverage_0_3s', 0.5 - 0.1 * e), ('path_coverage_0_2.5s', 0.52 - 0.1 * e)):
                rows.append({**base, 'metric': m, 'tau_s': None, 'n': 1000, 'covered': round(cov * 1000),
                             'coverage': round(cov - 0.01 * c, 4), 'ci_lo': round(cov - 0.06, 4),
                             'ci_hi': round(cov + 0.05, 4), 'clips_with_n': 32, 'clips': 32, 'complete': True})
    T.write_csv(d / 'coverage.csv', rows)
    doc = {'schema': FT.COVERAGE_SCHEMA, 'outputs': {'coverage.csv': sha(d / 'coverage.csv')},
           'checks': {'pooled': {'pass': True}, 'gate2': {'pass': True}},
           'deployed': {'status': status, 'deployed': list(COV_ENVS), 'roles': {e: 'candidate' for e in COV_ENVS},
                        'warnings': []},
           'split': {'evaluated': 'VAL', 'n_clips': 32}, 'arguments': {'n_boot': 2000, 'seed': 20261109},
           'complete': True, 'interim_guard': {'guarded_clips': list(guarded), 'released_clips': []}}
    write_json(d / 'coverage.json', doc)
    (d / 'SHA256SUMS').write_text(''.join(f'{sha(d / n)}  {n}\n' for n in ('coverage.csv', 'coverage.json')),
                                  encoding='utf-8')
    return d


def rl_doc(mode='development', routes=TRAIN_IDS):
    """An RL freeze document (p3_rl.py schema) with the bandit family not trainable."""
    fams = {}
    for i, (f, arm) in enumerate(FT.RL_FAMILIES):
        nt = f == 'bandit'
        fams[f] = {'arm': arm, 'not_trainable': nt, 'selected': None if nt else f'{f}_c{i}',
                   'estimate': {'mean_delta': None if nt else 0.5 + i,
                                'ci90': [None, None] if nt else [-0.25 + i, 1.25 + i]}}
    return {'schema': FT.RL_SCHEMA, 'mode': mode, 'frozen': mode == 'production', 'families': fams,
            'p_both': {'p_both': 0.1886, 'label': 'testable', 'threshold': 0.05, 'kappa': 1.0},
            'dataset': {'episodes': [{'route_id': r} for r in routes]}}


def _stat(p50, p99, mx):
    return {'n': 1000, 'p50_us': p50, 'p99_us': p99, 'max_us': mx, 'mean_us': p50 * 1.05}


def s1_doc(registered=False, shared=False):
    nets = [{'name': 'v4_qnet_bandit', 'family': 'bandit'}, {'name': 'v4_qnet_fqi', 'family': 'fqi'}]
    per = []
    for i, load in enumerate((0, 4, 8, 15)):
        f = 1 + 0.3 * i
        per.append({'load': load,
                    'qnet_call': {n['name']: {**_stat(15 * f + j, 22 * f, 80 * f), 'budget_s': 1e-4, 'overruns': i,
                                              'overrun_rate': i / 1000} for j, n in enumerate(nets)},
                    'shield_decision': {lab: {'all': _stat(110 * f + j, 180 * f, 900 * f),
                                              'choice_epochs': _stat(130 * f, 200 * f, 950 * f)}
                                        for j, lab in enumerate(['heuristic'] + [n['name'] for n in nets])},
                    'lease': _stat(1400 * f, 2600 * f, 9000 * f), 'commit_check': _stat(35 * f, 60 * f, 300 * f)})
    return {'schema': FT.STRESS_SCHEMA, 'test': 'S1', 'registered': registered, 'shared_cpu': shared,
            'label': 'registered S1 run' if registered else 'development run, not the registered S1',
            'plan': {'networks': nets, 'states': {'source': 'synthetic'}, 'scenes': {'source': 'synthetic'}},
            'per_load': per}


def s2_doc(relative=False, routes=TRAIN_IDS[:1], allow=False, registered=False):
    nets = {}
    for i, (f, _) in enumerate(FT.RL_FAMILIES):
        nets[f'v4_qnet_{f}'] = {'family': f, 'share_admitted': 0.12 + 0.7 * relative, 'admitted_bound_ge_Dstar': 0,
                                'bypass_rate': 0.002 * (i + 1), 'bypass_rate_slack': 0.002 * (i + 1),
                                'bypass_rate_timing': 0.0, 'violations_total': 0,
                                **({'floor_check': {'ok': True}} if relative else {})}
    doc = {'schema': FT.STRESS_SCHEMA, 'test': 'S2', 'registered': registered, 'n_swept': 1000, 'pass': True,
           'label': 'development run, not the registered S2', 'networks': nets,
           'states': {'source': 'recorded', 'runs': [{'route_id': r} for r in routes], 'allow_test_routes': allow},
           'slack_floor': {'1.0': {'floor_any_s': {'p50': 0.5136}}}}
    if relative:
        doc.update(supplementary=True, grid='relative_to_floor')
    return doc


def s3_doc(registered=False):
    tg = {t: {'sequences': 100000, 'offers': 1722750 + i, 'accepted': 371199 + i, 'violations_total': 0,
              'coverage_ok': True} for i, t in enumerate(('gate', 'runtime'))}
    return {'schema': FT.STRESS_SCHEMA, 'test': 'S3', 'registered': registered, 'n_sequences': 100000, 'pass': True,
            'label': 'development run, not the registered S3', 'targets': tg}


def _cand(name, arm, tag, k, shield=True, outcomes=None):
    return {'candidate': name, 'arm': arm, 'tag': tag, 'valid_runs': 3, 'n_kept': 3, 'mean_ds_kept': 40.0 + k,
            'ds': 41.0 + k, 'rc': 70.0 + k, 'sr': 0.1 * k, 'fallback_ratio': 0.2 + 0.01 * k, 'dmr': 0.15,
            'eir': 0.05 + 0.001 * k, 'r_cond': 0.5 if shield else None, 'p_both': 0.3 if shield else None,
            'outcomes': outcomes or {'ok': 3}}


def d1_doc(routes=TRAIN_IDS):
    blocks = [{'block': 'ref', 'grid': 'ref', 'stage': 0, 'route_set': 'T22', 'routes': list(routes),
               'kept_routes': list(routes), 'pending': 0, 'flags': [], 'selection': None,
               'candidates': [_cand('fixed_deep', 'fixed_deep', '', 0, False),
                              _cand('fast_only', 'fast_only', '', 1, False)]},
              {'block': 'lease_s1', 'grid': 'lease', 'stage': 1, 'route_set': 'T22a', 'routes': list(routes),
               'kept_routes': list(routes)[:2], 'pending': 1,
               'dropped_routes': {routes[-1]: ['B0: queue: timeout (None)']},
               'flags': [{'candidate': 'B0', 'setup_failures': 2, 'routes': [routes[-1]]}],
               'selection': {'survivors': ['E5', 'B0'], 'selected': None},
               'candidates': [_cand(e, 'fl_heuristic', f'{e}_d10', 2 + i,
                                    outcomes={'ok': 2, 'sim_failure': 1} if e == 'B0' else None)
                              for i, e in enumerate(COV_ENVS)]}]
    return {'schema': FT.D1_SCHEMA, 'variant': 'FULL', 'training_routes_only': True, 'blocks': blocks,
            'tuning_freeze': None}


def write_sources(d):
    """Every optional source of the tables (development), as CLI paths."""
    d = Path(d)
    return {'coverage': write_coverage(d / 'coverage'), 'rl_freeze': write_json(d / 'rl_freeze_dev.json', rl_doc()),
            's1': write_json(d / 's1.json', s1_doc(shared=True)), 's2': write_json(d / 's2.json', s2_doc()),
            's2_relative': write_json(d / 's2_relative.json', s2_doc(relative=True)),
            's3': write_json(d / 's3.json', s3_doc()), 'd1': write_json(d / 'd1.json', d1_doc())}


def source_args(sources):
    return [x for k, p in sources.items() for x in (FT.SOURCE_OPTIONS[k], str(p))]


_TMP = None
ANALYSIS = None
SOURCES = None


def setUpModule():
    global _TMP, ANALYSIS, SOURCES
    _TMP = tempfile.TemporaryDirectory()
    root = Path(_TMP.name)
    agg = T.write_agg(root / 'agg', synthetic_rows())
    ANALYSIS = root / 'analysis'
    code = AN.main(['--agg', str(agg), '--out', str(ANALYSIS)], settings=T.FAST, table=T.TABLE_B2D)
    assert code == 0, code
    SOURCES = write_sources(root / 'sources')


def tearDownModule():
    _TMP.cleanup()


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def copy(self, name='analysis_copy'):
        d = self.tmp / name
        shutil.copytree(ANALYSIS, d, ignore=shutil.ignore_patterns(G.LOG_NAME))
        return d


# ============================================================================== palette and type

class PaletteTest(unittest.TestCase):
    def test_fig3_arms_separate_in_every_vision(self):
        normal, cvd = worst([c for c, _ in FT.ARM_STYLE.values()])
        self.assertGreaterEqual(normal, 24.0)
        self.assertGreaterEqual(cvd, 9.0)
        self.assertEqual(len({m for _, m in FT.ARM_STYLE.values()}), len(FT.ARM_STYLE))

    def test_depth_and_diverging_scale(self):
        d1, d10 = FT.DEPTH_STYLE[1][0], FT.DEPTH_STYLE[10][0]
        self.assertEqual((d1, d10), (FT.ARM_STYLE['fast_only'][0], FT.ARM_STYLE['fixed_deep'][0]))
        self.assertGreaterEqual(worst([d1, d10, FT.DEPTH_STYLE[5][0]])[1], 9.0)
        lo, hi = FT.DIVERGING[0], FT.DIVERGING[-1]
        self.assertGreaterEqual(worst([lo, hi])[1], 15.0)
        lab = _oklab(_linear(FT.DIVERGING[2]))
        self.assertLess(float(np.hypot(lab[1], lab[2])), 0.01)      # a neutral (achromatic) midpoint
        self.assertEqual((FT.DIVERGING[1], FT.DIVERGING[3]), (d1, d10))

    def test_ieee_type_and_sizes(self):
        rc = FT.rc_params()
        for k in ('font.size', 'axes.labelsize', 'xtick.labelsize', 'ytick.labelsize', 'legend.fontsize',
                  'axes.titlesize'):
            self.assertEqual(rc[k], 8)
        self.assertEqual((rc['pdf.fonttype'], rc['font.family']), (42, 'serif'))
        self.assertEqual((FT.COL_W_IN, FT.DCOL_W_IN), (3.5, 7.16))
        self.assertEqual(list(rc['axes.prop_cycle'].by_key()['color']), list(FT.PALETTE))


# ============================================================================== numbers.json

class NumbersTest(unittest.TestCase):
    def test_registry(self):
        n = FT.Numbers()
        src = OFFLINE_FIG1 / 'c1_age_vs_depth.csv'
        n.add('k', 1.5, src, 'f', {'a': 1}, shown='1.5')
        n.add('k', 1.5, src, 'f', {'a': 1}, shown='1.5')                 # the same entry again
        for other in ((2.0, src, 'f', {'a': 1}, '1.5'), (1.5, src, 'g', {'a': 1}, '1.5'),
                      (1.5, src, 'f', {'a': 2}, '1.5'), (1.5, src, 'f', {'a': 1}, '1.50')):
            with self.assertRaises(ValueError):
                n.add('k', *other[:4], shown=other[4])
        self.assertIsNone(n.add('nan', float('nan'), src, 'f'))
        doc = n.doc('development', ['why'])
        self.assertEqual(doc['sources'], {FT.PJ.rel(src): sha(src)})
        self.assertEqual((doc['schema'], doc['status'], doc['numbers']['k']['value']),
                         (FT.NUMBERS_SCHEMA, 'development', 1.5))


# ============================================================================== loading and the Sec. 9.11 check

class LoadTest(Base):
    def test_loads_the_analysis(self):
        src = FT.load_analysis(ANALYSIS)
        self.assertEqual((src['doc']['schema'], src['doc']['status']), (AN.SCHEMA, 'development'))
        self.assertEqual(len(FT.analysis_table(src, 'conditions.csv')), len(rows_of(ANALYSIS / 'conditions.csv')))

    def test_changed_files_are_refused(self):
        d = self.copy()
        with open(d / 'conditions.csv', 'a', encoding='utf-8') as f:
            f.write('\n')
        with self.assertRaisesRegex(FT.FigureError, 'SHA256SUMS'):
            FT.load_analysis(d)
        d = self.copy('b')
        resign(d, doc_edit=lambda doc: doc['outputs'].update({'per_ability.csv': '0' * 64}))
        with self.assertRaisesRegex(FT.FigureError, 'outputs'):
            FT.load_analysis(d)
        d = self.copy('c')
        src = FT.load_analysis(d)
        (d / 'cells.csv').write_text('changed after loading\n', encoding='utf-8')
        with self.assertRaisesRegex(FT.FigureError, 'cells.csv'):
            FT.analysis_table(src, 'cells.csv')
        with self.assertRaisesRegex(FT.FigureError, 'not an analysis'):
            FT.load_analysis(self.tmp)

    def test_offline_check_must_pass(self):
        d = self.tmp / 'offline' / FT.FIG1_REL
        shutil.copytree(OFFLINE_FIG1, d)
        FT.load_offline(d.parent)
        (d / 'fig1_check.json').write_text(json.dumps({'pass': False}), encoding='utf-8')
        with self.assertRaisesRegex(FT.FigureError, 'fig1_check'):
            FT.load_offline(d.parent)


class PermissionTest(Base):
    def test_synthetic_analysis_is_development(self):
        status, dev, scope = FT.analysis_permission(FT.load_analysis(ANALYSIS))
        self.assertEqual((status, scope['registered_test_routes_used'], scope['freeze']), ('development', 0, None))
        self.assertTrue(dev)
        with self.assertRaisesRegex(FT.GuardRefused, 'require-registered'):
            FT.analysis_permission(FT.load_analysis(ANALYSIS), require_registered=True)

    def test_results_on_a_registered_test_route_are_refused(self):
        src = FT.load_analysis(ANALYSIS)
        with self.assertRaisesRegex(FT.GuardRefused, 'registered test routes used'):
            FT.analysis_permission(src, registered={T.TABLE_B2D['routes'][0]})
        real = sorted(G.registered_split()['test'])[0]
        d = self.copy()
        resign(d, table_edit={'cells.csv': lambda rows: [
            {**r, 'route_id': real} if r['route_id'] == T.TABLE_B2D['routes'][0] else r for r in rows]})
        with self.assertRaisesRegex(FT.GuardRefused, 'without a registered analysis-freeze record'):
            FT.analysis_permission(FT.load_analysis(d))

    def test_guard_document_with_test_rows_needs_a_valid_record(self):
        d = resign(self.copy(), doc_edit=lambda doc: doc['interim_guard'].update(test_input_rows=3))
        with self.assertRaisesRegex(FT.GuardRefused, 'without an analysis-freeze record'):
            FT.analysis_permission(FT.load_analysis(d))
        fz = {'path': str(self.tmp / 'no_record.json'), 'sha256': '0' * 64, 'protocol': 'framelease_v4/PROTOCOL.md',
              'seal': 'outputs/framelease_v4/registration/SEAL.sha256', 'registered': True}
        d = resign(self.copy('b'), doc_edit=lambda doc: doc['interim_guard'].update(
            test_input_rows=3, status='frozen', freeze=fz))
        with self.assertRaisesRegex(FT.GuardRefused, 'no analysis-freeze record there'):
            FT.analysis_permission(FT.load_analysis(d))

    def test_status_consistency(self):
        d = resign(self.copy(), doc_edit=lambda doc: doc.update(status='registered'))
        with self.assertRaises(FT.FigureError):
            FT.analysis_permission(FT.load_analysis(d))
        d = resign(self.copy('b'), doc_edit=lambda doc: doc.update(status='registered', development=[]))
        self.assertEqual(FT.analysis_permission(FT.load_analysis(d), require_registered=True)[0], 'registered')
        d = resign(self.copy('c'), doc_edit=lambda doc: doc.update(status='final'))
        with self.assertRaises(FT.FigureError):
            FT.analysis_permission(FT.load_analysis(d))


# ============================================================================== Fig. 1 numbers

class Fig1Test(Base):
    @classmethod
    def setUpClass(cls):
        cls.nums = FT.Numbers()
        cls.data = FT.fig1_data(FT.load_analysis(ANALYSIS), FT.load_offline(None, cls.nums), cls.nums)

    def test_interpolate(self):
        self.assertEqual(FT.interpolate([0.0, 1.0, 2.0], [0.0, 2.0, 3.0], 1.5), (2.5, 1.0, 2.0))
        with self.assertRaises(ValueError):
            FT.interpolate([0.0, 1.0], [0.0, 1.0], 1.2)

    def test_age_curves_and_release_points(self):
        rows = FT.select(rows_of(OFFLINE_FIG1 / 'c1_age_vs_depth.csv'), run='R1m', window_s='1', split='val')
        for depth in (1, 5, 10):
            mine = self.data['curves'][depth]
            ref = sorted(FT.select(rows, depth=depth), key=lambda r: float(r['age_s']))
            self.assertEqual(mine['mean'], [float(r['exec_err_mean_m']) for r in ref])
            self.assertEqual(mine['lo'], [float(r['t95_lo']) for r in ref])
            self.assertEqual(mine['n_clips'], [15])
        at = {(int(r['depth']), r['age_s']): float(r['exec_err_mean_m']) for r in rows}
        want = {('fast', 1): (0.457, '0.4', '0.5'), ('fast', 10): (0.5884, '0.5', '0.6'),
                ('unmodified', 1): (0.896, '0.8', '0.9'), ('unmodified', 10): (1.027, '1', '1.1')}
        self.assertEqual(len(self.data['release']), 4)
        for p in self.data['release']:
            age, a0, a1 = want[(p['prefix'], p['depth'])]
            v0, v1 = at[(p['depth'], a0)], at[(p['depth'], a1)]
            self.assertAlmostEqual(p['error'], v0 + (age - float(a0)) / (float(a1) - float(a0)) * (v1 - v0), 12)
            entry = self.nums.items[f'fig1.a.release.{p["prefix"]}.depth{p["depth"]}.error_m']
            self.assertIn('linear interpolation', entry['derivation'])
            self.assertEqual(self.nums.items[f'fig1.a.release.{p["prefix"]}.depth{p["depth"]}.age_s']['value'], age)

    def test_kappa_contrast(self):
        rkm, r1m = self.data['kappa']
        ref = FT.select(rows_of(OFFLINE_FIG1 / 'c1_fresh_vs_deep_kappa.csv'), run='RKm', split='val',
                        quantity='fast_fresh_minus_deep_old')
        self.assertEqual(rkm['value'], [float(r['value_m']) for r in sorted(ref, key=lambda r: float(r['kappa']))])
        self.assertEqual((rkm['kappa'][0], rkm['kappa'][-1], r1m['kappa']), (1.0, 2.4, [1.0, 1.5]))

    def test_closed_loop_by_ability(self):
        per = rows_of(ANALYSIS / 'per_ability.csv')
        for k, con in FT.DEPTH_CONTRASTS.items():
            for ab in FT.ABILITY_ROWS:
                r = FT.select_one(per, 'per_ability', group='depth', contrast=con.cid, metric='driving_score',
                                  ability=ab)
                c = self.data['v4'][k][ab]
                self.assertEqual((c['mean'], c['n']), (float(r['mean']), int(r['n'])))
                self.assertEqual(c['lo'], float(r['ci95_lo']) if r['ci95_lo'] else None)
        ab_rows = rows_of(OFFLINE_FIG1 / 'closed_loop_ds_by_ability.csv')
        r = FT.select_one(ab_rows, 'v2', ability='Overtaking', series='kappa 1.5, seed 11')
        self.assertEqual(self.data['v2'][1.5]['Overtaking']['mean'], float(r['mean_DS_diff']))
        routes = [r for r in rows_of(OFFLINE_FIG1 / 'closed_loop_ds_by_route.csv') if r['DS_diff_k2.0_s11']]
        self.assertEqual(len(routes), 11)
        for ab in FT.F1.ABILITIES:
            v = [float(r['DS_diff_k2.0_s11']) for r in routes if ab in r['abilities'].split('|')]
            c = self.data['v2'][2.0][ab]
            self.assertEqual((c['n'], c['lo']), (len(v), None))
            self.assertAlmostEqual(c['mean'], float(np.mean(v)), 12)
        self.assertEqual(self.data['v2'][2.0]['all']['n'], 11)
        self.assertAlmostEqual(self.data['v2'][2.0]['all']['mean'], -11.176, 3)

    def test_by_scenario(self):
        sc = self.data['scenarios']
        self.assertEqual(len(sc['types']), 44)
        pd = rows_of(ANALYSIS / 'paired_differences.csv')
        for k, con in FT.DEPTH_CONTRASTS.items():
            ref = {r['scenario_type']: float(r['difference']) for r in pd
                   if r['table'] == 'descriptive' and r['contrast'] == con.cid and r['metric'] == 'driving_score'}
            got = {t: v for t, v in sc['v4'][k].items() if v is not None}
            self.assertEqual(got, ref)
            self.assertEqual(len(got), 44 if k == 1.0 else 22)
        self.assertEqual([sum(v is not None for v in sc['v2'][k].values()) for k in FT.KAPPAS], [44, 44, 11])

    def test_without_an_analysis(self):
        nums = FT.Numbers()
        data = FT.fig1_data(None, FT.load_offline(None, nums), nums)
        self.assertEqual((data['v4'], data['scenarios']['v4']), ({}, {}))
        self.assertFalse(any(k.startswith('fig1.c.v4') for k in nums.items))


# ============================================================================== Fig. 3 numbers

class Fig3Test(Base):
    def test_points_equal_conditions(self):
        nums = FT.Numbers()
        pts = FT.fig3_points(FT.load_analysis(ANALYSIS), nums)
        cond = rows_of(ANALYSIS / 'conditions.csv')
        for arm in FT.FIG3_ARMS:
            for k in FT.KAPPAS:
                for metric in ('driving_score', 'action_age_p50_s', 'action_age_p95_s', 'eir', 'gpu_usage'):
                    r = FT.select_one(cond, 'conditions', condition=f'{arm}_k{k:.1f}_s11', subset='E', metric=metric,
                                      statistic='route_mean')
                    p = pts[arm][k][metric]
                    self.assertEqual((p['mean'], p['lo'], p['hi'], p['n']),
                                     (float(r['mean']), float(r['ci95_lo']), float(r['ci95_hi']), 22))
                e = nums.items[f'fig3.{arm}.kappa{k:.1f}.eir.mean']
                self.assertEqual(e['shown'], f'{100 * e["value"]:.1f}%')
                g = nums.items[f'fig3.{arm}.kappa{k:.1f}.gpu_usage.mean']
                self.assertEqual(g['shown'], f'{100 * g["value"]:.0f}%')

    def test_missing_condition_and_background_load(self):
        d = resign(self.copy(), table_edit={'conditions.csv': lambda rows: [
            r for r in rows if r['condition'] != 'fl_full_k2.0_s11']},
            doc_edit=lambda doc: doc['manipulation']['by_condition']['fast_only_k1.5_s11'].update(
                bg_load={'above': 3, 'below': 0, 'within': 19}))
        nums = FT.Numbers()
        pts = FT.fig3_points(FT.load_analysis(d), nums)
        self.assertEqual((pts['fl_full'][2.0]['driving_score']['mean'], pts['fl_full'][2.0]['driving_score']['n']),
                         (None, 0))
        self.assertEqual(pts['fast_only'][1.5]['bg_load'], {'above': 3, 'below': 0, 'within': 19, 'runs': 22})
        self.assertEqual(nums.items['fig3.fast_only.kappa1.5.bg_load.above']['field'],
                         'manipulation.by_condition.fast_only_k1.5_s11.bg_load.above')
        self.assertEqual(FT.figure_3(pts, 'development', self.tmp, layout='single'),
                         ['fig3_single.pdf', 'fig3_single.png'])


# ============================================================================== Table I

class Table1Test(Base):
    def test_numbers_equal_their_rows(self):
        nums = FT.Numbers()
        data = FT.table1_data(FT.load_analysis(ANALYSIS), nums)
        cond = rows_of(ANALYSIS / 'conditions.csv')
        for arm in FT.TABLE1_ARMS:
            for _, metric, stat, nd, scale, _ in FT.TABLE1_COLUMNS:
                r = FT.select_one(cond, 'conditions', condition=f'{arm}_k1.0_s11', subset='all', metric=metric,
                                  statistic=stat)
                e = nums.items[f'tab1.{arm}.{metric}.mean']
                self.assertEqual((e['value'], e['shown']), (float(r['mean']), f'{scale * float(r["mean"]):.{nd}f}'))
                self.assertEqual(data['arms'][arm][metric]['n'], 44)
        self.assertEqual(nums.items['tab1.fl_full.collisions_per_km_pooled.mean']['row']['statistic'],
                         'pooled_ratio')
        fam = rows_of(ANALYSIS / 'family_H1.csv')
        self.assertEqual([h['b'] for h in data['h1']], ['fixed_deep', 'fast_only', 'age_only', 'event_triggered'])
        for h in data['h1']:
            r = FT.select_one(fam, 'H1', contrast=f'fl_full_minus_{h["b"]}_k1.0_s11_all')
            self.assertEqual((h['mean'], h['p_adjusted'], h['label']),
                             (float(r['mean']), float(r['p_adjusted']), r['label']))

    def test_latex_text(self):
        self.assertEqual(FT.latex_escape('a_b & 5% <x> {y}'),
                         'a\\_b \\& 5\\% \\textless{}x\\textgreater{} \\{y\\}')
        self.assertEqual((FT.fmt_p(0.0004), FT.fmt_p(0.01234), FT.fmt_p(None)), ('< 0.001', '0.012', '--'))
        self.assertEqual(FT.fmt_ci(1.234, 0.5, None, 1), '1.2')
        self.assertEqual(FT.fmt_ci(1.234, 0.5, 2.0, 2), '1.23 [0.50, 2.00]')
        self.assertEqual(FT.hdr('DS', '[95% CI]').count('\\\\{}'), 1)

    def test_compiles_without_overfull_boxes(self):
        nums = FT.Numbers()
        self.assertEqual(FT.table_1(FT.table1_data(FT.load_analysis(ANALYSIS), nums), 'development', self.tmp),
                         ['table1.tex'])
        tex = (self.tmp / 'table1.tex').read_text(encoding='utf-8')
        self.assertIn('% ' + FT.DEV_STAMP, tex)
        self.assertIn('\\caption{\\textbf{[', tex)
        self.assertEqual(tex.count('\\toprule'), 1)
        compile_tex(self, self.tmp, 'table1.tex')


def compile_tex(tc, d, name):
    """pdflatex (IEEEtran conference, booktabs) on a document that inputs d/name: exit 0 and no overfull box."""
    if shutil.which('pdflatex') is None:
        tc.skipTest('pdflatex not installed')
    import subprocess
    stem = f'main_{Path(name).stem}'
    (Path(d) / f'{stem}.tex').write_text('\\documentclass[conference]{IEEEtran}\n\\usepackage{booktabs}\n'
                                         f'\\begin{{document}}\n\\input{{{name}}}\nx\n\\end{{document}}\n',
                                         encoding='utf-8')
    res = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', f'{stem}.tex'], cwd=d,
                         capture_output=True, text=True, timeout=120)
    log = (Path(d) / f'{stem}.log').read_text(encoding='utf-8', errors='replace')
    tc.assertEqual(res.returncode, 0, log[-2000:])
    tc.assertNotIn('Overfull \\hbox', log)


# ============================================================================== Tables II-A, II-B, training routes

def cond_row(rows, arm, metric, subset='E', kappa=1.0, statistic='route_mean'):
    return FT.select_one(rows, 'conditions', condition=f'{arm}_k{kappa:.1f}_s11', subset=subset, metric=metric,
                         statistic=statistic)


class Table2ATest(Base):
    @classmethod
    def setUpClass(cls):
        cls.nums = FT.Numbers()
        cls.src = FT.load_analysis(ANALYSIS)
        cls.data = FT.table2a_data(cls.src, None, FT.load_rnd(), FT.load_coverage(SOURCES['coverage']),
                                   FT.load_rl_freeze(SOURCES['rl_freeze']), cls.nums)

    def test_offline_panel_and_cited_rows(self):
        off = self.data['offline']
        nested = rows_of(ROOT / FT.OFFLINE_REL / 'nested.csv')
        for design, _ in FT.OFFLINE_DESIGNS:
            for need in FT.OFFLINE_NEEDS:
                r = FT.select_one(nested, 'nested', design=design, subset='all', alpha='0.05', risk='R_cond',
                                  need=need)
                for m in FT.OFFLINE_METRICS:
                    c = off['designs'][(design, need)][m]
                    self.assertEqual((c['value'], [c['lo'], c['hi']]), (float(r[m]), json.loads(r[f'{m}_ci'])))
        self.assertEqual((off['n_plans'], off['n_conflicts'], off['n_clips']), (5417, 909, 32))
        want = {('ra', 'model'): (57.8, 38.7, 75.4, 10.1, 0.8, 27.5),
                ('std', 'model'): (48.5, 26.0, 69.7, 9.6, 0.8, 27.1),
                ('ra', 'oracle'): (73.3, 56.5, 87.5, 4.9, 0.0, 15.8),
                ('std', 'oracle'): (80.8, 62.9, 93.0, 5.1, 0.0, 16.0)}
        for key, vals in want.items():                                   # PROTOCOL Sec. 7.4, by hand
            self.assertEqual(tuple(off['cited'][key][f] for f in FT.RND_FIELDS), vals)
        h4 = FT.select_one(rows_of(ANALYSIS / 'h4_offline.csv'), 'h4', role='primary')
        self.assertEqual((off['h4']['diff'], off['h4']['r_cond_hi'], off['h4']['label']),
                         (float(h4['diff']), float(h4['r_cond_hi']), h4['label']))
        self.assertEqual(self.nums.items['tab2a.offline.cited.ra.model.continuity']['source'], FT.RND_REL)

    def test_coverage_panel(self):
        cov = rows_of(Path(SOURCES['coverage']) / 'coverage.csv')
        self.assertEqual([(c['envelope'], c['class']) for c in self.data['coverage']],
                         [(e, c) for e in COV_ENVS for c in FT.COVERAGE_CLASSES])
        for c in self.data['coverage']:
            for tau in FT.COVERAGE_TAUS:
                r = FT.select_one(cov, 'cov', envelope=c['envelope'], **{'class': c['class']}, metric='per_tau',
                                  tau_s=tau)
                self.assertEqual(c['tau'][tau], float(r['coverage']))
            r = FT.select_one(cov, 'cov', envelope=c['envelope'], **{'class': c['class']}, metric=FT.COVERAGE_PATH)
            self.assertEqual((c['path'], c['lo'], c['hi'], c['n']),
                             (float(r['coverage']), float(r['ci_lo']), float(r['ci_hi']), int(r['n'])))

    def test_closed_loop_and_rl_panels(self):
        cond = rows_of(ANALYSIS / 'conditions.csv')
        for arm, _ in FT.T2A_LEASE:
            for m, *_ in FT.T2A_LEASE_COLUMNS:
                c, r = self.data['lease']['arms'][arm][m], cond_row(cond, arm, m)
                self.assertEqual((c['mean'], c['lo'], c['n']), (float(r['mean']), float(r['ci95_lo']), 22))
        doc = json.loads((ANALYSIS / 'analysis.json').read_text(encoding='utf-8'))
        rl = rl_doc()
        for arm, _, fam in FT.T2A_RL:
            c = self.data['rl']['arms'][arm]
            for m, *_ in FT.T2A_RL_COLUMNS:
                self.assertEqual(c[m]['mean'], float(cond_row(cond, arm, m)['mean']))
            cname = f'{arm}_k1.0_s11'
            for q in FT.QNET_KEYS:
                self.assertEqual(c[q], doc['overhead'][cname][q]['median'])
            self.assertEqual(c['qnet_s_p50'] is None, arm == 'fl_heuristic')
            if fam is not None:
                est = rl['families'][fam]['estimate']
                self.assertEqual((c['fqe']['mean'], c['fqe']['lo'], c['fqe']['hi']), (est['mean_delta'], *est['ci90']))
        for fam, key in (('H4-cl', 'h4cl'), ('RL-abl', 'rlabl'), ('H2', 'h2')):
            got = self.data['lease'][key] if key == 'h4cl' else self.data['rl'][key]
            rows = rows_of(ANALYSIS / f'family_{fam}.csv')
            self.assertEqual([(h['b'], h['mean'], h['p_adjusted'], h['label']) for h in got],
                             [(r['b'].split('_k')[0], float(r['mean']), float(r['p_adjusted']), r['label'])
                              for r in rows])
        self.assertIsNone(self.data['rl']['p_both'])                    # the analysis read no RL freeze
        self.assertEqual(self.data['rl']['rl_benefit'], doc['decisions']['H2']['rl_benefit'])

    def test_cross_checks(self):
        d = resign(self.copy(), doc_edit=lambda doc: doc['h4_offline']['files'].update(
            {f'{FT.OFFLINE_REL}/paired.csv': '0' * 64}))
        with self.assertRaisesRegex(FT.FigureError, 'paired.csv'):
            FT.offline_panel_data(None, FT.load_analysis(d), FT.load_rnd(), FT.Numbers())
        rnd = self.tmp / 'RND.md'
        rnd.write_bytes((ROOT / FT.RND_REL).read_bytes() + b'\n')
        with self.assertRaisesRegex(FT.FigureError, 'registered'):
            FT.load_rnd(rnd)
        proto = self.tmp / 'PROTOCOL.md'
        proto.write_text(G.REG.PROTOCOL.read_text(encoding='utf-8').replace('57.8% [38.7, 75.4]', '57.9% [38.7, 75.4]'),
                         encoding='utf-8')
        with self.assertRaisesRegex(FT.FigureError, 'not quoted in PROTOCOL'):
            FT.load_rnd(protocol=proto)
        cov = write_coverage(self.tmp / 'cov')
        (cov / 'coverage.csv').write_text('changed\n', encoding='utf-8')
        with self.assertRaisesRegex(FT.FigureError, 'SHA256SUMS'):
            FT.load_coverage(cov)

    def test_compiles(self):
        self.assertEqual(FT.table_2a(self.data, 'development', self.tmp), ['table2a.tex'])
        tex = (self.tmp / 'table2a.tex').read_text(encoding='utf-8')
        self.assertEqual(tex.count('\\toprule'), 4)
        self.assertIn('RA validity, model detections$^\\S$ & 10.1 [0.8, 27.5]', tex)     # not the dagger
        self.assertNotIn('$^\\dagger$', tex)                           # no closed-loop value with fewer routes
        self.assertIn('not compared statistically', tex)
        self.assertIn('\\renewcommand{\\thetable}{\\Roman{table}-A}', tex)
        self.assertNotIn('of the RL dataset', tex)                       # the analysis read no RL freeze
        self.assertIn('the Sec. 5.8 $P_\\mathrm{both}$ label', tex)     # the analysis's statement, P_both in math
        compile_tex(self, self.tmp, 'table2a.tex')


class Table2BTest(Base):
    @classmethod
    def setUpClass(cls):
        cls.nums = FT.Numbers()
        cls.stress = {k: FT.load_stress(SOURCES[k], k) for k in FT.STRESS_SLOTS}
        cls.data = FT.table2b_data(FT.load_analysis(ANALYSIS), cls.stress, cls.nums)

    def test_logs_panel_equals_overhead(self):
        doc = json.loads((ANALYSIS / 'analysis.json').read_text(encoding='utf-8'))
        for arm, kappa in FT.T2B_CONDS:
            cname = f'{arm}_k{kappa:.1f}_s11'
            over, cells = doc['overhead'][cname], self.data['logs']['cells'][cname]
            for label, kind, keys, _, _ in FT.T2B_ROWS:
                want = {'runs': lambda: (over['runs'],), 'q': lambda: tuple(over[k]['median'] for k in keys),
                        'mean': lambda: (over[keys[0]]['mean'],), 'count': lambda: (over[keys[0]]['total'],),
                        'above': lambda: (over['qnet_s_p99']['runs_above_b_pi'], over['qnet_s_p99']['runs']),
                        'bypass': lambda: (over['bypass_epochs']['total'], over['bypass_rate']['mean'])}[kind]()
                self.assertEqual(cells[label], want, (cname, label))
        self.assertEqual(self.data['logs']['cells']['fl_full_k2.0_s11']['Runs with Q-network p99 $> B_\\pi$'], (1, 22))
        self.assertEqual(self.data['logs']['cells']['fl_full_k1.0_s11']['Runs'], (44,))
        runs = 3 * 44 + 2 * 22                            # one reject of each reason per run of the five conditions
        self.assertEqual(self.data['logs']['reasons'],
                         {'expired_before_commit': runs, 'stale_version:not_deeper': runs})
        self.assertIn('derivation', self.nums.items['tab2b.logs.gate_rejects_by_reason'])

    def test_stress_panels(self):
        s1, s1d = self.data['s1'], s1_doc(shared=True)
        self.assertEqual(s1['network'], 'v4_qnet_fqi')
        for row, lv in zip(s1['rows'], s1d['per_load']):
            self.assertEqual((row['load'], row[('qnet_call', 'p50_us')], row[('shield_decision', 'p99_us')],
                              row[('lease', 'max_us')], row[('commit_check', 'p50_us')],
                              row[('qnet_call', 'overrun_rate')]),
                             (lv['load'], lv['qnet_call']['v4_qnet_fqi']['p50_us'],
                              lv['shield_decision']['v4_qnet_fqi']['all']['p99_us'], lv['lease']['max_us'],
                              lv['commit_check']['p50_us'], lv['qnet_call']['v4_qnet_fqi']['overrun_rate']))
        grids = {g['grid']: g for g in self.data['s2']}
        self.assertEqual(sorted(grids), ['registered', 'relative'])
        for grid, rel in (('registered', False), ('relative', True)):
            doc = s2_doc(relative=rel)
            self.assertEqual([n['family'] for n in grids[grid]['nets']], ['fqi', 'bandit', 'fqi_nolease'])
            for n in grids[grid]['nets']:
                for f, *_ in FT.S2_FIELDS:
                    self.assertEqual(n[f], doc['networks'][n['name']][f])
            self.assertEqual('floor_check_ok' in grids[grid]['nets'][0], rel)
        self.assertEqual([(t['target'], t['offers'], t['violations_total']) for t in self.data['s3']['targets']],
                         [('gate', 1722750, 0), ('runtime', 1722751, 0)])

    def test_slots_and_the_s3_of_the_analysis(self):
        with self.assertRaisesRegex(FT.FigureError, 'supplementary'):
            FT.load_stress(SOURCES['s2_relative'], 's2')
        with self.assertRaisesRegex(FT.FigureError, 'registered'):
            FT.load_stress(SOURCES['s2'], 's2_relative')
        with self.assertRaisesRegex(FT.FigureError, 'not a S3 report'):
            FT.load_stress(SOURCES['s2'], 's3')
        d = resign(self.copy(), doc_edit=lambda doc: doc['h5'].update(s3={'path': 'other.json', 'sha256': '0' * 64}))
        with self.assertRaisesRegex(FT.FigureError, 'judged H5'):
            FT.s3_panel_data(self.stress['s3'], FT.load_analysis(d), FT.Numbers())
        reasons = FT.load_stress(write_json(self.tmp / 's1.json', s1_doc(registered=True, shared=True)), 's1')
        self.assertEqual(len(reasons['development']), 1)
        self.assertIn('exclusive CPU', reasons['development'][0])
        self.assertEqual(FT.load_stress(write_json(self.tmp / 's3.json', s3_doc(True)), 's3')['development'], [])

    def test_compiles(self):
        self.assertEqual(FT.table_2b(self.data, 'development', self.tmp), ['table2b.tex'])
        tex = (self.tmp / 'table2b.tex').read_text(encoding='utf-8')
        self.assertEqual(tex.count('\\toprule'), 4)
        self.assertIn('Supplementary (A7)', tex)
        self.assertIn('never in its place', tex)
        self.assertIn('Commit audit (Eq. 9): no commit audit in the analysis', tex)     # never a 0 without an audit
        self.assertIn('Runs with Q-network p99 $> B_\\pi$ & -- & -- & 0/44 & -- & 1/22 \\\\', tex)
        self.assertIn('16 cores; network Full FrameLease (FQI)}', tex)                    # NET_LABEL, not the id
        self.assertIn('\\addtocounter{table}{-1}\n\\renewcommand{\\thetable}{\\Roman{table}-B}', tex)
        compile_tex(self, self.tmp, 'table2b.tex')

    def test_small_rates_are_not_zero(self):
        """A positive rate below the shown resolution prints as '< 0.01' (S2 supplementary bypass 3.8e-5)."""
        doc = s2_doc(relative=True)
        doc['networks']['v4_qnet_fqi_nolease']['bypass_rate'] = 3.8e-5
        s2r = FT.load_stress(write_json(self.tmp / 's2r.json', doc), 's2_relative')
        nums = FT.Numbers()
        grids = FT.s2_panel_data(None, s2r, nums)
        self.assertEqual(nums.items['tab2b.s2.relative.fqi_nolease.bypass_rate']['shown'], '< 0.01')
        data = {**self.data, 's2': grids}
        FT.table_2b(data, 'development', self.tmp)
        tex = (self.tmp / 'table2b.tex').read_text(encoding='utf-8')
        self.assertIn('FQI w/o lease features &  & 82.0 & 0 & $<$ 0.01 &', tex)
        compile_tex(self, self.tmp, 'table2b.tex')

    def test_table_two_parts_are_numbered_ii_a_and_ii_b(self):
        """Table II-A and Table II-B, input one after the other after Table I, are TABLE II-A and TABLE II-B."""
        if shutil.which('pdflatex') is None:
            self.skipTest('pdflatex not installed')
        import subprocess
        built = FT.build(['table1', 'table2a', 'table2b'], ANALYSIS, sources=SOURCES)
        FT.render(built, ['table1', 'table2a', 'table2b'], self.tmp)
        (self.tmp / 'main.tex').write_text('\\documentclass[conference]{IEEEtran}\n\\usepackage{booktabs}\n'
                                           '\\begin{document}\n\\input{table1.tex}\n\\input{table2a.tex}\n'
                                           '\\input{table2b.tex}\nx\n\\end{document}\n', encoding='utf-8')
        res = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', 'main.tex'], cwd=self.tmp,
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(res.returncode, 0, res.stdout[-2000:])
        aux = (self.tmp / 'main.aux').read_text(encoding='utf-8')
        for label, number in (('tab:table1', 'I'), ('tab:table2a', 'II-A'), ('tab:table2b', 'II-B')):
            self.assertIn(f'\\newlabel{{{label}}}{{{{{number}}}', aux)
        self.assertNotIn('Overfull \\hbox', (self.tmp / 'main.log').read_text(encoding='utf-8', errors='replace'))


class TrainTableTest(Base):
    def test_numbers_marks_and_compile(self):
        nums = FT.Numbers()
        d1 = FT.load_d1(SOURCES['d1'])
        self.assertTrue(d1['development'])
        data = FT.train_table_data(d1, nums)
        doc = d1_doc()
        self.assertEqual([b['block'] for b in data['blocks']], ['ref', 'lease_s1'])
        for b, bd in zip(data['blocks'], doc['blocks']):
            self.assertEqual((b['kept'], b['routes'], b['pending']),
                             (len(bd['kept_routes']), len(bd['routes']), bd['pending']))
            for c, cd in zip(b['candidates'], bd['candidates']):
                for col, *_ in FT.TRAIN_COLUMNS:
                    self.assertEqual(c[col], cd[col])
        self.assertEqual([c['mark'] for c in data['blocks'][1]['candidates']], ['survivor', '', 'survivor'])
        self.assertEqual(FT.table_train(data, 'development', self.tmp), ['table_train.tex'])
        tex = (self.tmp / 'table_train.tex').read_text(encoding='utf-8')
        self.assertIn('E5\\_d10$^+$', tex)
        self.assertIn('1 set-up flags', tex)
        self.assertIn('Run outcomes other than ok: lease\\_s1 B0\\_d10: sim\\_failure 1.', tex)       # Sec. 4.8
        self.assertIn('Dropped routes: lease\\_s1 route 930003 (B0: queue: timeout (None)).', tex)
        self.assertIn('lease\\_s1 B0: 2 set-up failures (routes 930003).', tex)
        self.assertEqual(nums.items['tabtrain.lease_s1.B0.outcomes']['value'], '{"ok": 2, "sim_failure": 1}')
        self.assertIn(' & 41.0 & 42.0 & 71.0 & 10.0 & ', tex)            # Fast Only: SR with one decimal
        compile_tex(self, self.tmp, 'table_train.tex')
        bad = write_json(self.tmp / 'd1_trimmed.json', {**doc, 'variant': 'TRIMMED'})
        with self.assertRaisesRegex(FT.FigureError, 'variant'):
            FT.load_d1(bad)


class SourceGuardTest(Base):
    def test_test_route_sources_are_refused(self):
        real = sorted(G.registered_split()['test'])[:2]
        frozen = {'freeze': {'registered': True}}
        rl = FT.load_rl_freeze(write_json(self.tmp / 'rl.json', rl_doc(routes=(TRAIN_IDS[0], real[0]))))
        d1 = FT.load_d1(write_json(self.tmp / 'd1.json', d1_doc(routes=(TRAIN_IDS[0], real[1]))))
        for kind, s in (('rl_freeze', rl), ('d1', d1)):
            for scope in (None, frozen):                   # training data never holds a test route
                with self.assertRaisesRegex(FT.GuardRefused, 'training data holding registered test routes'):
                    FT.source_permission({kind: s}, scope)
        s2 = FT.load_stress(write_json(self.tmp / 's2.json', s2_doc(routes=(real[0],))), 's2')
        s2a = FT.load_stress(write_json(self.tmp / 's2a.json', s2_doc(allow=True)), 's2')
        cov = FT.load_coverage(write_coverage(self.tmp / 'cov', guarded=('Clip_Town01_Route1_Weather0',)))
        for kind, s in (('s2', s2), ('s2', s2a), ('coverage', cov)):
            with self.assertRaisesRegex(FT.GuardRefused, 'Sec. 9.11'):
                FT.source_permission({kind: s}, None)
            FT.source_permission({kind: s}, frozen)        # after the analysis freeze
        FT.source_permission({k: FT.load_source(k, p) for k, p in SOURCES.items()}, None)

    def test_status_of_the_sources(self):
        built = FT.build(['table2a', 'table2b', 'table_train'], ANALYSIS, sources=SOURCES)
        self.assertEqual(built['status'], 'development')
        dev = ' | '.join(built['development'])
        for what in ('rl_freeze_dev.json: a development RL record', 's1.json: S1 shared the CPU',
                     's2_relative.json: development run', 'coverage: deployed status', 'd1.json: not the D1 summary'):
            self.assertIn(what, dev)
        built = FT.build(['table2a', 'table2b'], ANALYSIS)
        self.assertIn('no --s1 given: its panel is absent', built['development'])
        self.assertIsNone(built['data']['table2a']['coverage'])
        self.assertEqual(FT.table_2b(built['data']['table2b'], 'development', self.tmp), ['table2b.tex'])
        with self.assertRaisesRegex(FT.FigureError, '--d1'):
            FT.build(['table_train'])
        with self.assertRaisesRegex(FT.GuardRefused, 'require-registered'):
            FT.build(['table_train'], sources={'d1': SOURCES['d1']}, require_registered=True)


# ============================================================================== secondary families, RL freeze, RL gain

class SecondaryFamiliesTest(Base):
    """Sec. 7.2 ('Contrasts. As in Sec. 9.'), Secs. 1.2, 9.3, 9.8, 9.13: H3, S-coll and S-dmr in the Table I notes, F3
    in the Fig. 3 caption, labelled secondary, with the n of every contrast and its dropped routes."""

    def test_table1_secondary_families_and_n(self):
        nums = FT.Numbers()
        data = FT.table1_data(FT.load_analysis(ANALYSIS), nums)
        for fam, key in (('H3', 'h3'), ('S-coll', 'scoll'), ('S-dmr', 'sdmr')):
            rows = rows_of(ANALYSIS / f'family_{fam}.csv')
            self.assertEqual([(h['a'], h['b'], h['mean'], h['p_adjusted'], h['n'], h['n_expected'], h['label'])
                              for h in data[key]],
                             [(r['a'].split('_k')[0], r['b'].split('_k')[0], float(r['mean']), float(r['p_adjusted']),
                               int(r['n']), int(r['n_expected']), r['label']) for r in rows])
        self.assertEqual(sorted(k for k in nums.items if k.startswith('tab1.h3.') and k.endswith('.mean')),
                         ['tab1.h3.fl_full_minus_fl_original_k1.0.mean',
                          'tab1.h3.fl_heuristic_minus_fl_original_k1.0.mean'])
        self.assertEqual(nums.items['tab1.sdmr.fixed_deep.mean']['shown'],
                         f'{100 * data["sdmr"][0]["mean"]:.1f}')                  # percentage points
        self.assertEqual(FT.table_1(data, 'development', self.tmp), ['table1.tex'])
        tex = (self.tmp / 'table1.tex').read_text(encoding='utf-8')
        h3 = data['h3'][0]
        self.assertIn(f'H3 (each $-$ Original FrameLease, DS, Holm over 2): FrameLease + Heuristic '
                      f'{FT.tex_minus(FT.fmt_num(h3["mean"], 1))} [', tex)
        for what in ('Secondary (labelled secondary', 'S-coll (Full FrameLease $-$ each, collisions/km per route',
                     'S-dmr (Full FrameLease $-$ each, DMR in percentage points', 'H1 (primary;'):
            self.assertIn(what, tex)
        self.assertEqual(tex.count('n = 44 routes each'), 4)                     # H1, H3, S-coll, S-dmr
        c = data['arms']['fixed_deep']['collisions_per_km_pooled']
        self.assertIn(f'Fixed Deep [{c["lo"]:.2f}, {c["hi"]:.2f}]', tex)        # the route-cluster interval

    def test_incomplete_contrast_shows_n_and_dropped_routes(self):
        def drop(rows):
            return [{**r, 'n': '43', 'dropped_routes': '920005: agent crashed | 920007: no run'}
                    if r['a'].startswith('fl_full') else r for r in rows]
        d = resign(self.copy(), table_edit={'family_H3.csv': drop})
        nums = FT.Numbers()
        data = FT.table1_data(FT.load_analysis(d), nums)
        self.assertEqual(nums.items['tab1.h3.fl_full_minus_fl_original_k1.0.dropped_routes']['value'],
                         '920005: agent crashed | 920007: no run')
        FT.table_1(data, 'development', self.tmp)
        tex = (self.tmp / 'table1.tex').read_text(encoding='utf-8')
        self.assertIn(', n 43 of 44 (dropped: 920005: agent crashed \\textbar{} 920007: no run)', tex)
        self.assertEqual(tex.count('n = 44 routes each'), 3)                     # not for H3
        compile_tex(self, self.tmp, 'table1.tex')

    def test_f3_in_the_fig3_caption(self):
        src, nums = FT.load_analysis(ANALYSIS), FT.Numbers()
        pts, f3 = FT.fig3_points(src, nums), FT.family_rows(src, nums, 'F3', 'fig3.f3')
        rows = rows_of(ANALYSIS / 'family_F3.csv')
        self.assertEqual([(h['b'], h['kappa'], h['mean']) for h in f3],
                         [(r['b'].split('_k')[0], float(r['kappa']), float(r['mean'])) for r in rows])
        self.assertIn('fig3.f3.fl_full_minus_fast_only_k2.0.p_adjusted', nums.items)
        text = FT.fig3_caption(pts, f3)
        self.assertIn('F3 (secondary; Full FrameLease $-$ each on E, DS, Holm over 4)', text)
        for h in f3:
            self.assertIn(f'$\\kappa$ {h["kappa"]:.1f} {FT.ARM_LABEL[h["b"]]} {FT.fmt_num(h["mean"], 1)} '
                          f'[{FT.fmt_num(h["lo"], 1)}, {FT.fmt_num(h["hi"], 1)}]', text)
        self.assertIn('n = 22 routes each', text)
        self.assertIn('Full FrameLease 0/44, 0/22, 0/22', text)                  # background-load counts
        self.assertEqual(FT.write_caption(self.tmp, 'fig3', 'fig3', text, 'development'), 'fig3_caption.tex')
        cap = (self.tmp / 'fig3_caption.tex').read_text(encoding='utf-8')
        self.assertTrue(cap.startswith('% ' + FT.THIS_REL))
        self.assertIn('\\caption{\\textbf{[DEVELOPMENT DATA', cap)
        self.assertIn('\\label{fig:fig3}%', cap)
        self.assertIsNone(FT.MINUS_RE.search(cap))                           # a typographic minus only
        self.assertIn('$-$', cap)


class RLLinkTest(Base):
    """Secs. 5.8, 9.13: the RL-benefit statement and the dataset P_both of Table II-A come from the analysis; the RL
    freeze given for the FQE column must be the one the analysis read."""

    def p_both_of(self, path, **over):
        return {'path': FT.PJ.rel(Path(path)), 'sha256': sha(path), 'frozen': False, 'p_both': 0.1886,
                'label': 'testable', 'kappa': 1.0, 'threshold': 0.05, **over}

    def test_the_rl_freeze_of_the_analysis(self):
        pb = self.p_both_of(SOURCES['rl_freeze'])
        d = resign(self.copy(), doc_edit=lambda doc: doc['decisions']['H2'].update(
            p_both=pb, p_both_label='testable', rl_benefit='not claimed (H2 inconclusive)'))
        built = FT.build(['table2a'], d, sources={'rl_freeze': SOURCES['rl_freeze'], 'coverage': SOURCES['coverage']})
        self.assertFalse(any('used no RL freeze' in x for x in built['development']))
        p = built['data']['table2a']['rl']['p_both']
        self.assertEqual((p['p_both'], p['label'], p['threshold']), (0.1886, 'testable', 0.05))
        self.assertEqual(built['nums'].items['tab2a.rl.dataset.p_both.label']['source'], FT.PJ.rel(d / 'analysis.json'))
        FT.render(built, ['table2a'], self.tmp)
        tex = (self.tmp / 'table2a.tex').read_text(encoding='utf-8')
        self.assertIn('RL benefit: not claimed (H2 inconclusive). $P_\\mathrm{both}$ of the RL dataset ($\\kappa$ = '
                      '1.0 episodes): 18.9\\% (testable; threshold 5\\%).', tex)
        built = FT.build(['table2a'], d)                                         # no --rl-freeze: no FQE column
        self.assertEqual(built['data']['table2a']['rl']['p_both']['label'], 'testable')
        self.assertIsNone(built['data']['table2a']['rl']['arms']['fl_full'].get('fqe'))

    def test_another_rl_freeze_is_refused(self):
        other = write_json(self.tmp / 'rl_other.json', {**rl_doc(), 'p_both': {
            'p_both': 0.031, 'label': 'not testable at this operating point', 'threshold': 0.05, 'kappa': 1.0}})
        pb = self.p_both_of(other, p_both=0.031, label='not testable at this operating point')
        d = resign(self.copy(), doc_edit=lambda doc: doc['decisions']['H2'].update(p_both=pb))
        with self.assertRaisesRegex(FT.FigureError, 'not the RL freeze the analysis read'):
            FT.build(['table2a'], d, sources={'rl_freeze': SOURCES['rl_freeze']})
        with self.assertRaisesRegex(FT.FigureError, 'not the RL freeze the analysis read'):
            FT.rl_panel_data(FT.load_analysis(d), FT.load_rl_freeze(SOURCES['rl_freeze']), FT.Numbers())
        FT.build(['table2a'], d, sources={'rl_freeze': other})                  # the analysis's own freeze
        d2 = resign(self.copy('b'), doc_edit=lambda doc: doc['sources'][0].update(rl_sha256='c' * 64))
        with self.assertRaisesRegex(FT.FigureError, 'the RL freeze of its aggregations'):
            FT.build(['table2a'], d2, sources={'rl_freeze': SOURCES['rl_freeze']})
        d3 = resign(self.copy('c'), doc_edit=lambda doc: (doc['decisions']['H2'].update(p_both=pb),
                                                          doc['sources'][0].update(rl_sha256='c' * 64)))
        with self.assertRaisesRegex(FT.FigureError, 'names 2 RL freezes'):
            FT.build(['table2a'], d3)
        out = self.tmp / 'cli'
        with mock.patch('sys.stderr'):
            self.assertEqual(FT.main(['--out', str(out), '--only', 'table2a', '--analysis', str(d),
                                      '--rl-freeze', str(SOURCES['rl_freeze'])]), 2)
        self.assertFalse((out / 'table2a.tex').exists())

    def test_rl_freeze_with_an_analysis_that_read_none(self):
        built = FT.build(['table2a'], ANALYSIS, sources={'rl_freeze': SOURCES['rl_freeze']})
        self.assertTrue(any('the analysis used no RL freeze' in x for x in built['development']))
        self.assertIsNone(built['data']['table2a']['rl']['p_both'])
        self.assertEqual(built['data']['table2a']['rl']['arms']['fl_full']['fqe']['mean'], 0.5)


class RLGainTest(Base):
    """Sec. 7.5: the breakdown of the RL gain (by ability, kappa and seed) equals analysis.json 'rl_gain'."""

    def test_breakdown_equals_the_analysis(self):
        nums = FT.Numbers()
        gain = FT.rl_gain_data(FT.load_analysis(ANALYSIS), nums)
        doc = json.loads((ANALYSIS / 'analysis.json').read_text(encoding='utf-8'))['rl_gain']
        self.assertEqual([a for a, _ in gain['ability']], [r['ability'] for r in doc['by_ability']])
        for (_, c), r in zip(gain['ability'], doc['by_ability']):
            self.assertEqual((c['mean'], c['n'], (c['lo'], c['hi'])),
                             (r['mean'], r['n'], tuple(r['ci95']) if r['ci95'] else (None, None)))
        self.assertEqual([k for k, _ in gain['kappa']], ['1.0', '1.5', '2.0'])
        self.assertEqual([x for x, _ in gain['seed']], ['11', '12'])
        for k, c in gain['kappa']:
            self.assertEqual((c['mean'], c['n']), (doc['by_kappa_on_E'][k]['mean'], doc['by_kappa_on_E'][k]['n']))
        for x, c in gain['seed']:
            self.assertEqual(c['hi'], doc['by_seed_on_R'][x]['ci95'][1])
        self.assertEqual(nums.items['tab2a.rl_gain.kappa2.0.mean']['row'],
                         {'json_path': ['rl_gain', 'by_kappa_on_E', '2.0', 'mean']})
        note = FT._rl_gain_note(gain)
        self.assertIn(f'by GPU budget on E, $\\kappa$ 1.0: {doc["by_kappa_on_E"]["1.0"]["mean"]:.1f} [', note)
        self.assertIn(f'seed 12: {doc["by_seed_on_R"]["12"]["mean"]:.1f} [', note)
        d = resign(self.copy(), doc_edit=lambda doc: doc.pop('rl_gain'))
        with self.assertRaisesRegex(FT.FigureError, 'rl_gain'):
            FT.rl_gain_data(FT.load_analysis(d), FT.Numbers())


# ============================================================================== layout, formats, offline outputs

def text_layout(fig):
    """(overlapping text pairs, texts outside the figure, number of texts) of the texts a figure draws: every text but
    the tick labels, and the tick labels of the ticks inside the view (matplotlib keeps Tick objects for ticks outside
    the axis limits without drawing them; none of an axes without axis); the development stamp, drawn across the
    plot on purpose, is left out."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    axes = [ax.xaxis for ax in fig.axes] + [ax.yaxis for ax in fig.axes]
    ticks = {id(x) for a in axes for t in a.majorTicks + a.minorTicks for x in (t.label1, t.label2)}
    drawn = [x for a in axes if a.axes.axison and a.get_visible() for t in a._update_ticks()
             for x in (t.label1, t.label2)]
    texts = [t for t in fig.findobj(matplotlib.text.Text) if id(t) not in ticks] + drawn
    boxes = [(t.get_text(), t.get_window_extent(r)) for t in texts
             if t.get_visible() and t.get_text().strip() and t.get_text() != FT.DEV_STAMP]
    fb = fig.bbox
    outside = [s for s, b in boxes
               if b.x0 < fb.x0 - 0.5 or b.x1 > fb.x1 + 0.5 or b.y0 < fb.y0 - 0.5 or b.y1 > fb.y1 + 0.5]
    overlaps = [(a, b) for (a, ba), (b, bb) in itertools.combinations(boxes, 2) if ba.overlaps(bb)]
    return overlaps, outside, len(boxes)


class LayoutTest(Base):
    def test_no_text_overlaps_and_no_clipping(self):
        """Every text of every figure (tick labels, labels, legends, panel titles, colour-bar end labels) lies inside
        the figure and overlaps no other text; the colour bar of the companion spans the figure width."""
        items = ['fig1', 'fig1_scenarios', 'fig3']
        built = FT.build(items, analysis=ANALYSIS)
        found = {}

        def keep(fig, out, name, status):
            found[name] = text_layout(fig)
            if name == 'fig1_scenarios':
                cax = [a for a in fig.axes if a.xaxis.label.get_text().startswith('DS, Fixed Deep')][0]
                found['bar_share'] = cax.get_window_extent().width / fig.bbox.width
                found['ends'] = sorted(t.get_text() for t in cax.texts)
            plt.close(fig)
            return [f'{name}.pdf', f'{name}.png']
        with mock.patch.object(FT, 'save_figure', keep):
            FT.render(built, items, self.tmp)
            FT.render(built, ['fig3'], self.tmp, layout='single')
        for name in ('fig1', 'fig1_scenarios', 'fig3', 'fig3_single'):
            overlaps, outside, n = found[name]
            self.assertGreater(n, 10, name)
            self.assertEqual((overlaps, outside), ([], []), name)
        self.assertGreater(found['bar_share'], 0.85)
        self.assertEqual(found['ends'], ['Fast Only better', 'Fixed Deep better'])
        cap = (self.tmp / 'fig1_scenarios_caption.tex').read_text(encoding='utf-8')
        self.assertIn('hatched: no paired run', cap)
        self.assertIn('earlier measurement', (self.tmp / 'fig1_caption.tex').read_text(encoding='utf-8'))


class FormatTest(unittest.TestCase):
    def test_floor_minus_and_symbols(self):
        self.assertEqual(FT.fmt_num(3.8e-5, 2, 100.0, floor=True), '< 0.01')
        self.assertEqual(FT.fmt_num(3.8e-5, 2, 100.0), '0.00')
        self.assertEqual(FT.fmt_num(0.0, 2, 100.0, floor=True), '0.00')
        self.assertEqual(FT.fmt_num(0.004, 0, 100.0, floor=True), '< 1')
        self.assertEqual(FT.fmt_num(None, 2, floor=True), '--')
        self.assertEqual(FT.tex_minus('< 0.01 and -0.5 and $a < -b$'), '$<$ 0.01 and $-$0.5 and $a < -b$')
        self.assertEqual(FT.tex_text('undetermined: P_both < 5%'), 'undetermined: $P_\\mathrm{both}$ \\textless{} 5\\%')
        rows = [{'a': 'fl_full', 'b': 'fixed_deep', 'mean': 1.0, 'lo': -1.0, 'hi': 3.0, 'p_adjusted': 0.5, 'n': 22,
                 'n_expected': 22, 'dropped': None, 'label': 'inconclusive', 'nd': 1, 'scale': 1.0}]
        self.assertEqual(FT.fmt_contrasts(rows), 'Fixed Deep 1.0 [-1.0, 3.0], $p$ 0.500, inconclusive; n = 22 routes')


class OfflineOutputsTest(Base):
    def test_offline_sha256(self):
        """The offline outputs read equal OFFLINE_SHA256; a copy elsewhere is development, a changed file names
        itself (only for the items that read it)."""
        d = ROOT / FT.OFFLINE_REL
        for n, h in FT.OFFLINE_SHA256.items():
            self.assertEqual(sha(d / n), h, n)
        self.assertEqual(FT.offline_development(None, ['fig1', 'fig1_scenarios', 'table2a']), [])
        copy = self.tmp / 'offline'
        shutil.copytree(d / FT.FIG1_REL, copy / FT.FIG1_REL)
        for n in ('nested.csv', 'nested_folds.csv', 'paired.csv'):
            shutil.copy(d / n, copy / n)
        dev = FT.offline_development(copy, ['fig1'])
        self.assertEqual(len(dev), 1)
        self.assertIn('not the registered', dev[0])
        with open(copy / 'nested.csv', 'a', encoding='utf-8') as f:
            f.write('\n')
        dev = FT.offline_development(copy, ['table2a'])
        self.assertEqual(len(dev), 2)
        self.assertIn('nested.csv: sha256', dev[1])
        self.assertEqual(len(FT.offline_development(copy, ['fig1'])), 1)       # Fig. 1 does not read nested.csv
        built = FT.build(['table2a'], ANALYSIS, offline=copy)
        self.assertTrue(any('nested.csv: sha256' in x for x in built['development']))


# ============================================================================== rendering and the command line

def mediabox(pdf):
    m = re.search(rb'/MediaBox \[\s*0 0 ([0-9.]+) ([0-9.]+)\s*\]', Path(pdf).read_bytes())
    return float(m.group(1)), float(m.group(2))


def png_size(png):
    b = Path(png).read_bytes()
    return int.from_bytes(b[16:20], 'big'), int.from_bytes(b[20:24], 'big')


def check_numbers(tc, ndoc):
    """Every entry of numbers.json against its source: a JSON source at its key path; a CSV source at the one row its
    selectors (the columns among them) pick, the field read as a number (an interval cell '[lo, hi]' by the key's
    .lo / .hi) or as text; the source sha256 equals the file. Entries with a derivation, from PROTOCOL.md or from the
    RND report are counted without a lookup (tested by hand). Returns the number of entries checked."""
    cache = {}
    for key, e in ndoc['numbers'].items():
        src = e['source']
        path = Path(src) if Path(src).is_absolute() else ROOT / src
        tc.assertEqual(ndoc['sources'][src], sha(path), src)
        if e.get('derivation') or src.endswith('.md'):
            continue
        if src not in cache:
            cache[src] = json.loads(path.read_text(encoding='utf-8')) if src.endswith('.json') else rows_of(path)
        data = cache[src]
        if src.endswith('.json'):
            if 'json_path' in e['row']:
                tc.assertEqual(e['value'], FT._jget(data, e['row']['json_path']), key)
            continue
        cols = set(data[0]) if data else set()
        where = {k: v for k, v in e['row'].items() if k in cols and isinstance(v, (str, int, float))}
        hit = FT.select(data, **where)
        if e['value'] is None and not hit:
            continue
        tc.assertEqual(len(hit), 1, (key, where))
        raw = hit[0][e['field']]
        if e['field'].endswith('_ci'):
            want = FT._ci_pair(raw)[0 if key.endswith('.lo') else 1]
        elif isinstance(e['value'], str):
            want = raw
        else:
            want = FT._num(raw)
        tc.assertEqual(e['value'], want, key)
    return len(ndoc['numbers'])


class CommandLineTest(Base):
    def run_cli(self, *args):
        return FT.main([str(a) for a in args])

    def log(self, out):
        return [json.loads(x) for x in (Path(out) / G.LOG_NAME).read_text(encoding='utf-8').splitlines()]

    def test_end_to_end_and_deterministic(self):
        out1, out2 = self.tmp / 'out1', self.tmp / 'out2'
        self.assertEqual(self.run_cli('--out', out1, '--analysis', ANALYSIS, *source_args(SOURCES)), 0)
        self.assertEqual(self.run_cli('--out', out2, '--analysis', ANALYSIS, *source_args(SOURCES)), 0)
        names = FT.output_names(list(FT.FIGURES))
        for n in names:
            self.assertTrue((out1 / n).is_file(), n)
        sums = AN.read_sums(out1 / 'SHA256SUMS')
        self.assertEqual(sorted(sums), sorted(names[:-1]))
        self.assertTrue(all(sha(out1 / n) == s for n, s in sums.items()))
        for n in names[:-2]:                                             # every figure file and numbers.json
            self.assertEqual(sha(out1 / n), sha(out2 / n), n)
        self.assertIn('\\begin{table*}', (out1 / 'table1.tex').read_text(encoding='utf-8'))
        widths = {'fig1': FT.DCOL_W_IN, 'fig1_scenarios': FT.COL_W_IN, 'fig3': FT.DCOL_W_IN}
        for f, w in widths.items():
            pdf = (out1 / f'{f}.pdf').read_bytes()
            self.assertAlmostEqual(mediabox(out1 / f'{f}.pdf')[0], 72.0 * w, 2)
            self.assertEqual(png_size(out1 / f'{f}.png')[0], round(FT.PNG_DPI * w))
            self.assertIn(b'/FontFile2', pdf)                            # embedded TrueType
            self.assertNotIn(b'/Subtype /Type3', pdf)
            self.assertNotIn(b'/CreationDate', pdf)
        nums = json.loads((out1 / 'numbers.json').read_text(encoding='utf-8'))
        doc = json.loads((out1 / 'figures.json').read_text(encoding='utf-8'))
        self.assertEqual((nums['status'], doc['status'], doc['analysis']),
                         ('development', 'development', FT.PJ.rel(ANALYSIS)))
        self.assertEqual(sum(d['numbers'] for d in doc['figures'].values()), len(nums['numbers']))
        self.assertTrue(all(v['source'] in nums['sources'] for v in nums['numbers'].values()))
        self.assertEqual(nums['sources'][FT.PJ.rel(ANALYSIS / 'conditions.csv')], sha(ANALYSIS / 'conditions.csv'))
        self.assertEqual([e['decision'] for e in self.log(out1)], ['granted'])
        for t in FT.TABLES:
            tex = (out1 / f'{t}.tex').read_text(encoding='utf-8')
            self.assertIn('% ' + FT.DEV_STAMP, tex)
            self.assertEqual(sum(1 for k in nums['numbers'] if k.startswith(FT.FIGURE_KEYS[t])),
                             doc['figures'][t]['numbers'])
            self.assertGreater(doc['figures'][t]['numbers'], 50)
        self.assertEqual(doc['sources'], {k: FT.PJ.rel(Path(p)) for k, p in SOURCES.items()})
        self.assertEqual(check_numbers(self, nums), len(nums['numbers']))

    def test_development_stamp(self):
        import matplotlib.pyplot as plt
        for status, calls in (('development', 1), ('registered', 0)):
            with mock.patch.object(FT, 'dev_stamp') as stamp:
                fig = plt.figure(figsize=(1, 1))
                FT.save_figure(fig, self.tmp, f'stamp_{status}', status)
                self.assertEqual(stamp.call_count, calls)

    def test_refusals(self):
        out = self.tmp / 'out'
        self.assertEqual(self.run_cli('--out', out, '--only', 'fig1', '--analysis', ANALYSIS), 0)
        self.assertEqual(self.run_cli('--out', out, '--only', 'fig1', '--analysis', ANALYSIS), 1)
        self.assertEqual(self.run_cli('--out', out, '--only', 'fig1', '--analysis', ANALYSIS, '--force'), 0)
        self.assertEqual([e['decision'] for e in self.log(out)], ['granted', 'refused', 'granted'])
        self.assertEqual(self.run_cli('--out', ROOT / 'framelease_v4' / 'figures_x', '--only', 'fig1'), 1)
        self.assertFalse((ROOT / 'framelease_v4' / 'figures_x').exists())
        self.assertEqual(self.run_cli('--out', ANALYSIS, '--analysis', ANALYSIS), 1)
        out = self.tmp / 'reg'
        self.assertEqual(self.run_cli('--out', out, '--analysis', ANALYSIS, '--require-registered'), 4)
        self.assertEqual([e['decision'] for e in self.log(out)], ['refused'])
        self.assertEqual(sorted(p.name for p in out.iterdir()), [G.LOG_NAME])
        real = sorted(G.registered_split()['test'])[0]
        d = resign(self.copy(), table_edit={'cells.csv': lambda rows: [
            {**r, 'route_id': real} if r['route_id'] == T.TABLE_B2D['routes'][2] else r for r in rows]})
        out = self.tmp / 'guard'
        self.assertEqual(self.run_cli('--out', out, '--analysis', d), 4)
        entry = self.log(out)[0]
        self.assertEqual(entry['decision'], 'refused')
        self.assertIn('Sec. 9.11', entry['reason'])
        self.assertEqual(sorted(p.name for p in out.iterdir()), [G.LOG_NAME])
        self.assertEqual(self.run_cli('--out', self.tmp / 'nofig3', '--only', 'fig3'), 2)
        self.assertFalse((self.tmp / 'nofig3').exists())
        self.assertEqual(self.run_cli('--out', self.tmp / 'notrain', '--only', 'table_train'), 2)

    def test_test_route_tables_are_refused(self):
        """Sec. 9.11 through the command line: Table II-B from an S2 report on decision states of a registered test
        route, and the training-route table from a D1 summary holding one, are refused before anything is written
        (exit 4, logged); --require-registered refuses development sources."""
        real = sorted(G.registered_split()['test'])[0]
        s2 = write_json(self.tmp / 's2_test.json', s2_doc(routes=(real,)))
        d1 = write_json(self.tmp / 'd1_test.json', d1_doc(routes=(TRAIN_IDS[0], real)))
        for name, args in (('t2b', ('--only', 'table2b', '--analysis', ANALYSIS, '--s2', s2)),
                           ('train', ('--only', 'table_train', '--d1', d1)),
                           ('reg', ('--only', 'table_train', '--d1', SOURCES['d1'], '--require-registered'))):
            out = self.tmp / name
            self.assertEqual(self.run_cli('--out', out, *args), 4, name)
            entry = self.log(out)[0]
            self.assertEqual(entry['decision'], 'refused')
            self.assertIn('require-registered' if name == 'reg' else 'Sec. 9.11', entry['reason'])
            self.assertEqual(sorted(p.name for p in out.iterdir()), [G.LOG_NAME])
        out = self.tmp / 'train_ok'
        self.assertEqual(self.run_cli('--out', out, '--only', 'table_train', '--d1', SOURCES['d1']), 0)
        nums = json.loads((out / 'numbers.json').read_text(encoding='utf-8'))
        self.assertEqual(nums['status'], 'development')
        self.assertFalse(any(NO_ANALYSIS_TEXT in d for d in nums['development']))


if __name__ == '__main__':
    unittest.main()
