#!/usr/bin/env python3
"""Envelope parameters of the v4 lease ablation (CPU only).

    cd /home/kang/Desktop/DAC
    .conda-unidrive-linux/bin/python -I -B framelease_v4/offline/envelopes_v4.py

* TRAIN family (primary): the isotropic quadratic envelope E0, B_c(tau) = vbar_c tau + abar_c tau^2 / 2 + sigma_c,
  fitted with framelease_v3.envelopes.fit_iso on the calibration samples (framelease_v3.envelopes.clip_samples:
  confident detections matched to ground truth within 2 m) of the 5 TRAIN clips only, at quantiles q30 ... q99.5
  (T_q*), and lambda x E0 q95 for lambda = 0, 0.05, ..., 2.0 (T_x*; lambda = 0 is no envelope). No VAL clip enters.
  The v2 deployed parameter file (E0-orig q95, TRAIN clips, old D grid) is the extra configuration V2file.
  Self-check: the q80 / q90 / q95 / q99 / q99.5 fits must reproduce gate2's E0_q*_ORIG.json and V2file gate2's
  E0orig_q95_ORIG.json.
* LOCO-36 family (sensitivity, VAL clips only): the stored 36-clip leave-one-clip-out E0 fits of the tracking study
  (outputs/framelease_v3/tracking_offline/run_20261110/envelopes/raw.npz, q50 ... q99.5; L_q*) and lambda x their q95
  (L_x*). The fold of VAL clip h was calibrated on the other 36 clips (31 VAL + 5 TRAIN).

Output: OUT/envelopes/train_E0.json, OUT/envelopes/loco36_E0.json, OUT/envelopes/selfcheck.json.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault('OMP_NUM_THREADS', '1')
sys.dont_write_bytecode = True

import argparse  # noqa: E402
import json  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from multiprocessing import get_context  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v2.calibration import SweepClip  # noqa: E402
from framelease_v2.geometry import time_grid  # noqa: E402
from framelease_v3 import envelopes as envmod  # noqa: E402
from framelease_v4.offline import common as C  # noqa: E402

ENV_DIR = C.OUT / 'envelopes'
PARAMS = ('sigma_m', 'vbar_mps', 'abar_mps2')


def _samples(name):
    clip = SweepClip(C.VIEW, name)
    tau = time_grid(C.T_PRED, C.DT)
    S = envmod.clip_samples(clip, tau, gate_m=C.GATE_M, score_threshold=C.sle.SCORE_THRESHOLD,
                            warmup_steps=C.WARMUP_STEPS)
    return name, S


def scaled(env, lam):
    return {p: {g: float(lam) * float(env[p][g]) for g in C.GROUPS} for p in PARAMS}


def strip(env):
    return {p: {g: float(env[p][g]) for g in C.GROUPS} for p in PARAMS}


def fit_train(workers=5):
    lists = C.load_lists()
    with ProcessPoolExecutor(max_workers=workers, mp_context=get_context('fork')) as ex:
        res = dict(ex.map(_samples, lists['train']))
    tau = time_grid(C.T_PRED, C.DT)
    P = envmod.pool_samples(res, lists['train'])
    fits = {}
    for q in C.Q_GRID_TRAIN:
        e = envmod.fit_iso(P, q, tau)
        fits[f'T_q{C.qtag(q)}'] = {**strip(e), 'q': q, 'n_pairs': e['n_pairs'], 'notes': e['notes'],
                                   'd_grid_s': e['d_grid_s']}
    base = fits['T_q95']
    for lam in C.LAMBDA_GRID:
        fits[f'T_x{C.lam_tag(lam)}'] = {**scaled(base, lam), 'lambda': lam, 'of': 'T_q95'}
    v2 = json.loads(Path(C.V2_PARAMS).read_text(encoding='utf-8'))
    fits['V2file'] = {**{p: {g: float(v2[p][g]) for g in C.GROUPS} for p in PARAMS},
                      'source': str(C.V2_PARAMS), 'h_max_s_deployed': float(v2['h_max_s']),
                      'margin_mode_deployed': v2['margin_mode']}
    # ---- self-check against gate2's stored ORIG envelopes
    chk = {}
    for q in (0.8, 0.9, 0.95, 0.99, 0.995):
        g2 = json.loads((C.GATE2 / 'envelopes' / f'E0_q{C.qtag(q)}_ORIG.json').read_text(encoding='utf-8'))['envelope']
        mine = fits[f'T_q{C.qtag(q)}']
        chk[f'T_q{C.qtag(q)} vs gate2 E0_q{C.qtag(q)}_ORIG'] = max(abs(mine[p][g] - float(g2[p][g]))
                                                                  for p in PARAMS for g in C.GROUPS)
    g2o = json.loads((C.GATE2 / 'envelopes' / 'E0orig_q95_ORIG.json').read_text(encoding='utf-8'))['envelope']
    chk['V2file vs gate2 E0orig_q95_ORIG'] = max(abs(fits['V2file'][p][g] - float(g2o[p][g]))
                                                 for p in PARAMS for g in C.GROUPS)
    n_pairs = {g: int((P['group'] == envmod.GROUP_ID[g]).sum()) for g in C.GROUPS}
    return fits, chk, n_pairs


def loco36():
    with np.load(C.TRK_ENV, allow_pickle=False) as z:
        folds = [str(f) for f in z['folds']]
        qs = [float(q) for q in z['quantiles']]
        E0 = z['E0'].astype(float)                       # (fold, q, param [sigma, vbar, abar], group)
    if [round(q, 4) for q in qs] != [round(q, 4) for q in C.Q_GRID_LOCO]:
        raise SystemExit(f'unexpected LOCO quantiles {qs}')
    lists = C.load_lists()
    if sorted(folds) != sorted(lists['val']):
        raise SystemExit('LOCO folds differ from the 32 VAL clips')
    out = {}
    for fi, clip in enumerate(folds):
        d = {}
        for qi, q in enumerate(qs):
            d[f'L_q{C.qtag(q)}'] = {p: {g: float(E0[fi, qi, pi, gi]) for gi, g in enumerate(envmod.GROUPS)}
                                    for pi, p in enumerate(PARAMS)}
        base = d['L_q95']
        for lam in C.LAMBDA_GRID:
            d[f'L_x{C.lam_tag(lam)}'] = scaled(base, lam)
        out[clip] = d
    return out


def load_train():
    return json.loads((ENV_DIR / 'train_E0.json').read_text(encoding='utf-8'))['configs']


def load_loco():
    return json.loads((ENV_DIR / 'loco36_E0.json').read_text(encoding='utf-8'))['folds']


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--workers', type=int, default=5)
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args(argv)
    ENV_DIR.mkdir(parents=True, exist_ok=True)
    if (ENV_DIR / 'train_E0.json').is_file() and (ENV_DIR / 'loco36_E0.json').is_file() and not a.force:
        print('envelopes exist; use --force to refit')
        return 0
    C.check_disk()
    fits, chk, n_pairs = fit_train(a.workers)
    ok = all(v < 1e-9 for v in chk.values())
    C.write_json(ENV_DIR / 'selfcheck.json', {'max_abs_diff': chk, 'pass': ok, 'train_pairs': n_pairs})
    if not ok:
        print('SELF-CHECK FAILED', chk)
        return 2
    C.write_json(ENV_DIR / 'train_E0.json', {'calibration_clips': C.load_lists()['train'], 'n_pairs': n_pairs,
                                             'form': 'B_c(tau) = vbar_c tau + abar_c tau^2 / 2 + sigma_c',
                                             'configs': fits})
    C.write_json(ENV_DIR / 'loco36_E0.json', {'source': str(C.TRK_ENV), 'sha256': C.sha256_file(C.TRK_ENV),
                                              'folds': loco36()})
    C.log_progress(f'envelopes fitted: TRAIN self-check pass={ok} {chk}; pairs {n_pairs}')
    print(json.dumps({'selfcheck': chk, 'pass': ok, 'pairs': n_pairs}, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
