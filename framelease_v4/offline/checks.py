#!/usr/bin/env python3
"""Reproduction checks of stage F against earlier, independently produced outputs (read-only).

    .conda-unidrive-linux/bin/python -I -B framelease_v4/offline/checks.py

(1) Suffix tau* (TRAIN E0 q80 / q90 / q95 / q99 / q99.5, the v2 file, no envelope) and V against gate2 frames.csv
    (15 VAL clips, depth 1; gate2 stored 6 significant digits).
(2) Global-Margin lease of the v2 file at the deployed 2.0 s cap against framelease_v2 c2_eval
    merged20_q95_envelope frames.csv H_avl_s (the v2 lease as deployed; 15 VAL clips, depth 1).
(3) Plan and conflict counts against MERGE_NOTE / gate2 (15 VAL: 2447 plans, 246 conflicts; 17 new: 2970 plans,
    663 conflicts at depth 1).
(4) End-to-end metrics of the analysis code (continuity at 1.842 s, R_marg, R_cond) for four Suffix configurations
    against gate2 metrics.csv (15 VAL clips, T_c 0.5 s, depth 1; gate2 stored 6 significant digits).
Output: OUT/checks/crosscheck.json; exit 1 on a failed check.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault('OMP_NUM_THREADS', '1')
sys.dont_write_bytecode = True

import csv  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v4.offline import common as C  # noqa: E402
from framelease_v4.offline import stage_frames as S  # noqa: E402

TOL = 2e-5
MAP_G2 = {'T_q80': 'E0_q80_ORIG', 'T_q90': 'E0_q90_ORIG', 'T_q95': 'E0_q95_ORIG', 'T_q99': 'E0_q99_ORIG',
          'T_q99.5': 'E0_q99.5_ORIG', 'V2file': 'E0orig_q95_ORIG', 'T_x0.00': 'B0_q0_NONE'}


def main():
    lists = C.load_lists()
    g2 = {}
    with open(C.GATE2 / 'frames.csv', newline='') as f:
        for r in csv.DictReader(f):
            if r['depth'] == '1':
                g2[(r['clip'], int(r['frame_idx']))] = r
    v2 = {}
    with open(C.V2_C2EVAL / 'frames.csv', newline='') as f:
        for r in csv.DictReader(f):
            if r['depth'] == '1':
                v2[(r['clip'], int(r['frame_idx']))] = r
    res = {'suffix_vs_gate2_max_abs_s': {k: 0.0 for k in MAP_G2}, 'V_vs_gate2_max_abs_s': 0.0,
           'global_v2file_cap2_vs_v2_c2eval_max_abs_s': 0.0, 'n_compared_gate2': 0, 'n_compared_v2': 0,
           'frame_sets_equal_gate2': True, 'frame_sets_equal_v2': True, 'counts': {}}
    totals = {}
    for clip in lists['all']:
        d = S.load_clip(clip)
        split = 'train' if clip in lists['train'] else ('val15' if clip in lists['val15'] else 'new17')
        t = totals.setdefault(split, {'plans': 0, 'conflicts': 0, 'v0': 0, 'v0_static': 0})
        t['plans'] += len(d['V'])
        t['conflicts'] += int((~d['censored']).sum())
        t['v0'] += int(d['v0'].sum())
        t['v0_static'] += int((d['v0'] & (d['speed'] < C.STATIONARY_MPS)).sum())
        if split != 'val15':
            continue
        keys = {(clip, int(f)) for f in d['frame_idx']}
        if keys != {k for k in g2 if k[0] == clip}:
            res['frame_sets_equal_gate2'] = False
        if keys != {k for k in v2 if k[0] == clip}:
            res['frame_sets_equal_v2'] = False
        nT = d['names_T']
        for i, fidx in enumerate(d['frame_idx']):
            r = g2.get((clip, int(fidx)))
            if r is not None:
                res['n_compared_gate2'] += 1
                res['V_vs_gate2_max_abs_s'] = max(res['V_vs_gate2_max_abs_s'], abs(d['V'][i] - float(r['V_s'])))
                for mine, theirs in MAP_G2.items():
                    x = abs(d['ts_T'][i, nT.index(mine)] - float(r[f'tau_star__{theirs}']))
                    res['suffix_vs_gate2_max_abs_s'][mine] = max(res['suffix_vs_gate2_max_abs_s'][mine], x)
            q = v2.get((clip, int(fidx)))
            if q is not None:
                res['n_compared_v2'] += 1
                x = abs(min(d['hg_T'][i, nT.index('V2file')], 2.0) - float(q['H_avl_s']))
                res['global_v2file_cap2_vs_v2_c2eval_max_abs_s'] = max(
                    res['global_v2file_cap2_vs_v2_c2eval_max_abs_s'], x)
    totals['val32'] = {k: totals['val15'][k] + totals['new17'][k] for k in totals['val15']}
    # (4) end-to-end metrics (continuity at 1.842 s, R_marg, R_cond) of the Suffix design vs gate2 metrics.csv
    from framelease_v4.offline import analyze as A
    g2m = {}
    with open(C.GATE2 / 'metrics.csv', newline='') as f:
        for r in csv.DictReader(f):
            if r['depth'] == '1' and r['T_c'] == '0.5':
                g2m[r['config']] = r
    e2e = {}
    for mine, theirs in (('V2file', 'E0orig_q95_ORIG'), ('T_q80', 'E0_q80_ORIG'), ('T_q95', 'E0_q95_ORIG'),
                         ('T_x0.00', 'B0_q0_NONE')):
        tot = {'n': 0.0, 'conf': 0.0, 'over': 0.0, 'cont': 0.0}
        for clip in lists['val15']:
            d = S.load_clip(clip)
            names, _, H = A.candidates('SUFFIX', d)
            k = names.index(mine)
            sm = A.clip_sums(H[:, k:k + 1], d, np.ones(len(d['V']), dtype=bool))
            for key in ('n', 'conf', 'over'):
                tot[key] += sm[key][0]
            tot['cont'] += sm[('cont', 'meas')][0]
        r = g2m[theirs]
        e2e[f'{mine} vs {theirs}'] = max(abs(tot['cont'] / tot['n'] - float(r['continuous_fraction'])),
                                        abs(tot['over'] / tot['n'] - float(r['overestimation_rate'])),
                                        abs(tot['over'] / tot['conf'] - float(r['overestimation_rate_conflict'])))
    res['metrics_vs_gate2_max_abs'] = e2e
    res['counts'] = totals
    expect = {'val15': {'plans': 2447, 'conflicts': 246}, 'new17': {'plans': 2970, 'conflicts': 663}}
    res['counts_expected'] = expect
    ok = (res['frame_sets_equal_gate2'] and res['frame_sets_equal_v2']
          and res['n_compared_gate2'] == 2447 and res['n_compared_v2'] == 2447
          and max(res['suffix_vs_gate2_max_abs_s'].values()) < TOL and res['V_vs_gate2_max_abs_s'] < TOL
          and res['global_v2file_cap2_vs_v2_c2eval_max_abs_s'] < TOL
          and all(totals[s][k] == v for s, e in expect.items() for k, v in e.items())
          and max(e2e.values()) < 1e-5)
    res['tolerance_s'] = TOL
    res['pass'] = bool(ok)
    C.write_json(C.OUT / 'checks' / 'crosscheck.json', res)
    C.log_progress(f'checks: pass={ok}')
    print(json.dumps(C.clean_json(res), indent=1))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
