#!/usr/bin/env python3
"""Export the lease operating points E5, E10 and B0 of PROTOCOL Sec. 4.3 as v3 envelope files (CPU only).

    cd /home/kang/Desktop/DAC
    .conda-unidrive-linux/bin/python -I -B framelease_v4/offline/export_envelopes.py            # export (+ verify)
    .conda-unidrive-linux/bin/python -I -B framelease_v4/offline/export_envelopes.py --check    # re-derive, compare

Inputs (read only, both written by the offline lease ablation before any closed-loop run):
  outputs/framelease_v4/offline_ablation/envelopes/train_E0.json   multi-configuration TRAIN family (52 configurations:
                                                                   E0 q30 ... q99.5, lambda x E0 q95, the v2 file);
                                                                   framelease_v3/runtime v3_lease.load_envelope cannot
                                                                   read it, hence this export
  outputs/framelease_v4/offline_ablation/frontier.csv              in-sample rule-(a) picks on the 32 VAL clips

Operating points (PROTOCOL Sec. 4.3):
  E5   the SUFFIX candidate of the frontier row (design SUFFIX, subset all, need fast = 0.964 s, risk R_cond,
       alpha 0.05): rule (a), maximal continuity at the need subject to R_cond <= alpha
  E10  the same row at alpha 0.10
  B0   T_x0.00 (lambda = 0: no envelope, B = 0; the nominal suffix margin with d_safe 0.5 m and delta 0.2 m)
Pruning (Sec. 4.3): E10 is dropped if it is the same candidate as E5; E5 or E10 is dropped if it is B0 (T_x0.00) or if
its alpha selection returned ZERO (no candidate meets alpha). The validity definition is the standard one (Eqs. 1-3);
the responsibility-aware (RA) rule is not part of the closed-loop grid (offline sensitivity only).

Output (outputs/framelease_v4/envelopes/):
  E5.json, E10.json, B0.json   {"kind": "iso", "sigma_m", "vbar_mps", "abar_mps2", "calibration_clips", "n_pairs",
                                "protocol", "_meta"}: the isotropic quadratic envelope B_c(tau) = vbar_c tau +
                                abar_c tau^2 / 2 + sigma_c of framelease_v3.runtime.v3_lease (byte-deterministic: the
                                same inputs give the same sha256)
  manifest.json                sha256 of every exported file and input, the grid after pruning, and the verification
--verify (default on export): every recorded frame of the offline stage (outputs/framelease_v4/offline_ablation/
frames, 37 clips) is recomputed with the v3 runtime lease (v3_lease.compute_suffix_lease on the clip's depth-1 plan and
detections, envelope = the exported file, ego = the v2 lease parameter file) and must reproduce the offline tau* and
H = clip(tau* - T_c, 0, H_bar) within 5e-6 s.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault('OMP_NUM_THREADS', '1')
sys.dont_write_bytecode = True

import argparse  # noqa: E402
import csv  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v4.offline import common as C  # noqa: E402

TRAIN_ENVELOPES = C.OUT / 'envelopes' / 'train_E0.json'
FRONTIER = C.OUT / 'frontier.csv'
OUT_DIR = ROOT / 'outputs/framelease_v4/envelopes'
MANIFEST = 'manifest.json'
LEASE_PARAMS = ROOT / 'outputs/framelease_v2/c2_calibration/full_20261107T045343Z/lease_params_q95_envelope.json'
PARAMS = ('sigma_m', 'vbar_mps', 'abar_mps2')
B0_CONFIG = 'T_x0.00'
ROW_KEY = {'design': 'SUFFIX', 'subset': 'all', 'need': 'fast', 'risk': 'R_cond'}
ALPHAS = {'E5': 0.05, 'E10': 0.10}
ORDER = ('E5', 'E10', 'B0')               # candidate order of the lease grid (most conservative first)
TOL_S = 5e-6
SCHEMA = 'framelease_v4.envelopes/1'


def rel(p):
    p = Path(p).resolve()
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def frontier_rows(path=FRONTIER):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def frontier_pick(rows, alpha):
    """The frontier row (design SUFFIX, subset all, need fast, risk R_cond) at this alpha (exactly one)."""
    hit = [r for r in rows if all(r.get(k) == v for k, v in ROW_KEY.items())
           and abs(float(r['alpha']) - float(alpha)) < 1e-12]
    if len(hit) != 1:
        raise ValueError(f'expected one frontier row for {ROW_KEY} alpha {alpha}, found {len(hit)}')
    return hit[0]


def grid(picks):
    """Apply the Sec. 4.3 pruning rules to {'E5': candidate, 'E10': candidate}. Returns (kept labels, dropped)."""
    kept, dropped = [], {}
    for label in ORDER:
        if label == 'B0':
            kept.append(label)
            continue
        cand = picks[label]
        if cand == 'ZERO':
            dropped[label] = 'alpha selection returned ZERO (no candidate meets alpha)'
        elif cand == B0_CONFIG:
            dropped[label] = 'the pick is B0 itself (lambda = 0); B0 keeps its own slot'
        elif label == 'E10' and cand == picks.get('E5') and 'E5' in kept:
            dropped[label] = 'same candidate as E5'
        else:
            kept.append(label)
    return kept, dropped


def envelope_doc(label, config, train, row=None, source_sha=None, frontier_sha=None):
    """The v3 isotropic envelope JSON of one operating point (deterministic content, no timestamps)."""
    conf = train['configs'][config]
    meta = {'label': label, 'config': config, 'config_label': C.config_label(config),
            'lambda': conf.get('lambda'), 'of': conf.get('of'),
            'form': train['form'], 'validity': 'std (Eqs. 1-3; RA is an offline sensitivity only)',
            'source': rel(TRAIN_ENVELOPES), 'source_sha256': source_sha,
            'exported_by': 'framelease_v4/offline/export_envelopes.py'}
    if row is not None:
        meta.update(frontier=rel(FRONTIER), frontier_sha256=frontier_sha,
                    rule=('rule (a): maximal continuity at the fast-prefix need 0.964 s subject to R_cond <= alpha '
                          'on the 32 VAL clips pooled (in-sample frontier); ties: lower R_cond, then candidate order'),
                    frontier_row={k: row[k] for k in ('design', 'subset', 'need', 'risk', 'alpha', 'candidate',
                                                      'continuity', 'R_cond', 'R_marg', 'utilization',
                                                      'premature_refresh', 'mean_H_s', 'n')})
    else:
        meta['rule'] = 'B0: no envelope (lambda = 0), the availability end of the frontier'
    return {'kind': 'iso',
            'sigma_m': {g: float(conf['sigma_m'][g]) for g in C.GROUPS},
            'vbar_mps': {g: float(conf['vbar_mps'][g]) for g in C.GROUPS},
            'abar_mps2': {g: float(conf['abar_mps2'][g]) for g in C.GROUPS},
            'calibration_clips': list(train['calibration_clips']), 'n_pairs': dict(train['n_pairs']),
            'protocol': f'framelease_v4/PROTOCOL.md Sec. 4.3 lease operating point {label}', '_meta': meta}


def dumps(doc):
    return json.dumps(doc, indent=1, sort_keys=True) + '\n'


def build(train_path=TRAIN_ENVELOPES, frontier_path=FRONTIER):
    """{label: (config, doc)} of the kept operating points, the picks and the pruning record."""
    train = json.loads(Path(train_path).read_text(encoding='utf-8'))
    rows = frontier_rows(frontier_path)
    src_sha, fr_sha = C.sha256_file(train_path), C.sha256_file(frontier_path)
    picks, picked_rows = {}, {}
    for label, alpha in ALPHAS.items():
        row = frontier_pick(rows, alpha)
        picks[label], picked_rows[label] = row['candidate'], row
    kept, dropped = grid(picks)
    docs = {}
    for label in kept:
        config = B0_CONFIG if label == 'B0' else picks[label]
        if config not in train['configs']:
            raise ValueError(f'{label}: configuration {config} is not in {train_path}')
        docs[label] = (config, envelope_doc(label, config, train, picked_rows.get(label), src_sha, fr_sha))
    return {'docs': docs, 'picks': picks, 'kept': kept, 'dropped': dropped, 'source_sha256': src_sha,
            'frontier_sha256': fr_sha, 'rows': picked_rows}


# ============================================================================================ verification

def runtime_envs(paths):
    from framelease_v3.runtime import v3_lease as VL
    return {label: VL.build_lease_env(str(LEASE_PARAMS), str(path)) for label, path in paths.items()}


def verify(paths, configs, clips=None, every=1, tol=TOL_S):
    """Recompute tau* and H of the recorded offline frames with the v3 runtime lease and the exported envelopes.

    paths: {label: exported file}; configs: {label: offline configuration name}. Returns a summary dict."""
    from framelease_v2.calibration import SweepClip
    from framelease_v3.runtime import v3_lease as VL
    from framelease_v4.offline import stage_frames as SF
    envs = runtime_envs(paths)
    clips = clips or C.load_lists()['all']
    out = {'tolerance_s': tol, 'clips': len(clips), 'every': every, 'frames': 0, 'comparisons': 0,
           'max_abs_tau_star_s': {k: 0.0 for k in paths}, 'max_abs_H_s': {k: 0.0 for k in paths},
           'violations': [], 'statuses': {}}
    for name in clips:
        d = SF.load_clip(name)
        cols = {label: d['names_T'].index(configs[label]) for label in paths}
        sc = SweepClip(C.VIEW, name)
        kidx = {int(f): k for k, f in enumerate(sc.frame_idx)}
        for i in range(0, len(d['frame_idx']), every):
            k = kidx[int(d['frame_idx'][i])]
            plan = sc.cand[k, C.DEPTH - 1]
            det7, score, label = sc.dets(k)
            out['frames'] += 1
            for lab, env in envs.items():
                res = VL.compute_suffix_lease(plan, det7, score, label, env)
                ts_off = float(d['ts_T'][i, cols[lab]])
                h_off = float(np.clip(ts_off - C.T_C, 0.0, C.HBAR))
                ts_rt = float(res.tau_star_s)
                ts_rt = C.T_PRED if not math.isfinite(ts_rt) else min(ts_rt, C.T_PRED)
                e_ts, e_h = abs(ts_rt - ts_off), abs(float(res.lease_s) - h_off)
                out['comparisons'] += 1
                out['statuses'][res.reason] = out['statuses'].get(res.reason, 0) + 1
                out['max_abs_tau_star_s'][lab] = max(out['max_abs_tau_star_s'][lab], e_ts)
                out['max_abs_H_s'][lab] = max(out['max_abs_H_s'][lab], e_h)
                if e_ts > tol or e_h > tol:
                    out['violations'].append({'clip': name, 'frame_idx': int(d['frame_idx'][i]), 'label': lab,
                                              'tau_star_offline': ts_off, 'tau_star_runtime': ts_rt,
                                              'H_offline': h_off, 'H_runtime': float(res.lease_s),
                                              'reason': res.reason})
    out['violations'] = out['violations'][:50]
    out['pass'] = not out['violations'] and out['comparisons'] > 0
    return out


# ============================================================================================ main

def export(out_dir=OUT_DIR, force=False, do_verify=True, every=1):
    out_dir = Path(out_dir)
    b = build()
    targets = {label: out_dir / f'{label}.json' for label in b['docs']}
    texts = {label: dumps(doc) for label, (_, doc) in b['docs'].items()}
    for label, path in targets.items():
        if path.exists() and path.read_text(encoding='utf-8') != texts[label] and not force:
            raise SystemExit(f'{path} exists with other content (use --force; jobs pin its sha256)')
    out_dir.mkdir(parents=True, exist_ok=True)
    for label, path in targets.items():
        if not path.exists() or path.read_text(encoding='utf-8') != texts[label]:
            C.atomic_write_text(path, texts[label])
    from framelease_v3.runtime import v3_lease as VL
    loaded = {label: VL.load_envelope(path).describe() for label, path in targets.items()}
    ver = verify(targets, {lab: cfg for lab, (cfg, _) in b['docs'].items()}, every=every) if do_verify else None
    manifest = {
        'schema': SCHEMA, 'written': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'grid_order': list(ORDER), 'kept': b['kept'], 'dropped': b['dropped'], 'picks': b['picks'],
        'validity': 'std', 'ra': 'not in the closed-loop grid (offline sensitivity only)',
        'files': {label: {'path': rel(path), 'sha256': C.sha256_file(path), 'config': b['docs'][label][0],
                          'kind': loaded[label]['kind'], 'sigma_m': loaded[label]['sigma_m'],
                          'vbar_mps': loaded[label]['vbar_mps'], 'abar_mps2': loaded[label]['abar_mps2']}
                  for label, path in targets.items()},
        'inputs': {rel(TRAIN_ENVELOPES): b['source_sha256'], rel(FRONTIER): b['frontier_sha256'],
                   rel(LEASE_PARAMS): C.sha256_file(LEASE_PARAMS)},
        'frontier_rows': {label: {k: row[k] for k in ('alpha', 'candidate', 'continuity', 'R_cond')}
                          for label, row in b['rows'].items()},
        'script_sha256': C.sha256_file(Path(__file__)),
        'verification': ver,
        'reader': 'framelease_v3.runtime.v3_lease.load_envelope / build_lease_env(lease_params, envelope)'}
    C.write_json(out_dir / MANIFEST, manifest)
    return manifest


def check(out_dir=OUT_DIR):
    """Re-derive the documents and compare them byte for byte with the exported files and the manifest."""
    out_dir = Path(out_dir)
    b = build()
    problems = []
    man_path = out_dir / MANIFEST
    man = json.loads(man_path.read_text(encoding='utf-8')) if man_path.is_file() else None
    if man is None:
        problems.append('manifest missing')
    for label, (_, doc) in b['docs'].items():
        path = out_dir / f'{label}.json'
        if not path.is_file():
            problems.append(f'{label}: file missing')
            continue
        if path.read_text(encoding='utf-8') != dumps(doc):
            problems.append(f'{label}: content differs from the re-derived envelope')
        if man and man['files'].get(label, {}).get('sha256') != C.sha256_file(path):
            problems.append(f'{label}: sha256 differs from the manifest')
    if man and sorted(man['kept']) != sorted(b['kept']):
        problems.append('kept grid differs from the manifest')
    if man and man.get('verification') is not None and not man['verification'].get('pass'):
        problems.append('manifest verification did not pass')
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, default=OUT_DIR)
    ap.add_argument('--check', action='store_true', help='re-derive and compare; write nothing')
    ap.add_argument('--no-verify', action='store_true')
    ap.add_argument('--every', type=int, default=1, help='verify every n-th recorded frame (default all)')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args(argv)
    if a.check:
        problems = check(a.out)
        print(json.dumps({'problems': problems}, indent=1))
        return 1 if problems else 0
    C.check_disk(min_gb=0.5)
    man = export(a.out, a.force, not a.no_verify, a.every)
    print(json.dumps({k: man[k] for k in ('kept', 'dropped', 'picks')}, indent=1))
    for label, f in man['files'].items():
        print(f'{label:4s} {f["config"]:8s} {f["sha256"]}  {f["path"]}')
    v = man['verification']
    if v is not None:
        print(f'verification: {v["comparisons"]} comparisons on {v["frames"]} frames of {v["clips"]} clips, '
              f'max |d tau*| {max(v["max_abs_tau_star_s"].values()):.3g} s, '
              f'max |d H| {max(v["max_abs_H_s"].values()):.3g} s, pass {v["pass"]}')
        return 0 if v['pass'] else 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
