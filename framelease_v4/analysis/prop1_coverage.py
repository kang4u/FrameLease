#!/usr/bin/env python3
"""Proposition-1 coverage of the deployed lease envelope E* on the 32 VAL clips (framelease_v4/PROTOCOL.md Secs. 1.3,
4.3, 7.4, 9.13; GAP_AUDIT Sec. 3.7 row R-5). CPU only; reads the merged 37-clip view, the exported envelopes and the
tuning freeze, writes only under --out.

  cd /home/kang/Desktop/DAC
  .conda-unidrive-linux/bin/python -I -B framelease_v4/analysis/prop1_coverage.py --out DIR \
      [--tuning-freeze outputs/framelease_v4/tuning/selection.json] [--clips CLIP ...] [--n-boot 2000] \
      [--seed 20261109] [--analysis-freeze RECORD] [--force]

Proposition 1 holds only under its envelope assumption: at t_k + tau the true footprint of every relevant actor lies
within B_c(tau) (Hausdorff distance) of the constant-velocity (CV) extrapolation of its detection. Its coverage is
reported and never stated as a guarantee (Secs. 1.3, 9.13); for B0 (B = 0) the assumption is that of zero error (Sec.
4.3), and its coverage shows how far that is from the data.

Envelopes (Sec. 4.3): the exported lease operating points E5, E10 and B0 (outputs/framelease_v4/envelopes; every file
checked against the envelope manifest, p1_jobs.envelopes, and against the registration manifest), in the isotropic form
B_c(tau) = vbar_c tau + abar_c tau^2 / 2 + sigma_c for c = vehicle, pedestrian. The deployed E* is L* of the tuning
freeze (outputs/framelease_v4/tuning/selection.json, select_stage.py --freeze; Sec. 4.9), together with the fl_risk
lease point when L* = B0 (FULL); the freeze counts once its sha256 is cited in Sec. 13 of the sealed PROTOCOL.md. Until
then every kept envelope is a deployed candidate (role 'candidate', deployed True). Every kept envelope is computed in
either case; after the freeze the others carry deployed False (role 'not deployed').

Samples: framelease_v3.envelopes.clip_samples on the merged 37-clip view (framelease_v4/offline/common.VIEW), clip by
clip, with the settings of the offline stage (framelease_v4/offline/envelopes_v4._samples): the tau grid 0 ... 3 s in
0.05 s steps, confident detections (score >= 0.3) matched one-to-one to ground-truth actors within 2 m after the
5-step warm-up, actors within 50 m of the LiDAR. iso(tau) is the Hausdorff distance between the CV-extrapolated
detection box and the ground-truth box at t_k + tau (NaN where the actor is not recorded). Only the class and iso(tau)
of each matched pair are kept. The tracking raw.npz holds only fitted envelopes, not samples, so it is not used.

Coverage (framelease_v3.envelopes.iso_inside and coverage_summary), per class, pooled over the evaluated clips:
  per-tau       P(iso(tau) <= B_c(tau)) over the pairs recorded at tau: at 0, 0.5, ..., 3 s (coverage_summary;
                coverage.csv) and on the whole 0.05 s grid (per_tau.csv)
  whole-path    P(iso(tau) <= B_c(tau) at every recorded tau) over the pairs recorded at some tau, on [0, 3 s] and,
                gate2's convention, on [0, 2.5 s]
  sample        over every recorded (pair, tau)
The pooled values are coverage_summary's on the concatenated samples; they must equal the ratios of the summed per-clip
counts (check 'pooled'). CIs: clip-level percentile bootstrap of those ratios, 2000 resamples, seed 20261109 (Sec. 7.4;
framelease_v4/offline/analyze.boot_weights and ci); a resample without a pair of the class is left out.

Split: the evaluated clips are the 32 VAL clips (framelease_v4/offline/common.load_lists) or, for development, a subset
(--clips; the result is then marked incomplete). A TRAIN clip, a calibration clip of any envelope or an unknown clip is
refused: VAL and TRAIN samples are never pooled.

Checks (coverage.json 'checks'; any failure is an error, exit 2, and nothing is written):
  inputs         every clip's npz and ground-truth sha256 equal those the offline stage recorded
                 (outputs/framelease_v4/offline_ablation/frames/<clip>.npz, meta)
  envelope_link  every exported envelope equals lambda x T_q95 of the registered train_E0.json exactly
  gate2          with all 15 gate2 VAL clips evaluated: their sha256 equal gate2's (config.json), and the coverage of
                 gate2's E0_q95_ORIG (= T_q95), E0orig_q95_ORIG (the v2 file) and B0_q0_NONE on them reproduces
                 outputs/framelease_v3/gate2_offline/gate2_20261109/summary.json envelope_coverage_out_of_sample
                 within 1e-12 (skipped, not failed, for a subset without them)
  pooled         coverage_summary equals the summed per-clip counts

Interim-look guard (Sec. 9.11; interim_guard.py): the offline clips are recorded dataset clips, not leaderboard routes
(Sec. 3.3, item 2), and this tool reads no closed-loop run. A clip whose route id (the 'Route<N>' of its name) is a test
route of the registered split (interim_guard.test_routes), or whose name gives no route id, is refused (exit 4) unless
a valid analysis-freeze record is given (--analysis-freeze; interim_guard.load_freeze); a record cited only by a
development copy of PROTOCOL.md never releases a route of the registered split. Every guard decision of the CLI is
logged in <out>/interim_guard.jsonl: granted (before any clip is read) or refused (an invalid record, a guarded clip,
existing outputs); a protected --out takes no log.

Development data: PROTOCOL Sec. 9.12 says the analysis code is 'written and tested on synthetic CSVs only'. The unit
tests use synthetic samples, envelopes and freezes, and in addition read the real inputs of this item: the 32 VAL
clips of the offline stage (recorded dataset clips, not routes; the offline analysis of Sec. 7.4 ran on them before
registration, Sec. 11) and the registered envelopes; the development run is outputs/framelease_v4/build/R5/dev_run.
No closed-loop run and no test route was read. The PROTOCOL wins: this is to be recorded in the Sec. 13 entry that
enters the sha256 of this code (Sec. 9.12).

Outputs (under --out): coverage.json (schema framelease_v4.prop1_coverage/1: arguments, the envelopes and their roles,
the coverage of each envelope per class with counts and CIs, coverage_summary's own output, the per-clip inputs with
their sha256, the checks, and the sha256 of every input file and of the code), coverage.csv (envelope x class x metric
at the coverage_summary marks), per_tau.csv (envelope x class x tau on the 0.05 s grid), per_clip.csv (envelope x clip x
class counts) and SHA256SUMS (those four files). The four files are byte-deterministic (no time stamps); the guard log
is append-only and never replaced.

Exit codes: 0 written, 1 refused (outputs exist without --force, protected directory), 2 inconsistent inputs or a
failed check (nothing written), 4 refused by the interim-look guard (logged).
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault('OMP_NUM_THREADS', '1')
sys.dont_write_bytecode = True

import argparse  # noqa: E402
import json  # noqa: E402
import platform  # noqa: E402
import re  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v2.calibration import SweepClip  # noqa: E402
from framelease_v2.geometry import time_grid  # noqa: E402
from framelease_v3 import envelopes as envmod  # noqa: E402
from framelease_v4.analysis import interim_guard as G  # noqa: E402
from framelease_v4.arms import metrics_v4 as MV  # noqa: E402
from framelease_v4.offline import analyze as OA  # noqa: E402
from framelease_v4.offline import common as C  # noqa: E402
from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402
from framelease_v4.protocol import registration as REG  # noqa: E402
from framelease_v4.protocol import select_stage as SS  # noqa: E402

SCHEMA = 'framelease_v4.prop1_coverage/1'
THIS_REL = 'framelease_v4/analysis/prop1_coverage.py'
GROUPS = envmod.GROUPS                                   # ('vehicle', 'pedestrian'); class id = index
MARKS_S = (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0)            # coverage_summary's per-tau marks
PATH25_S = 2.5                                           # coverage_summary's [0, 2.5 s] path (gate2 convention)
PATH_KEYS = ('path_coverage_0_3s', 'path_coverage_0_2.5s', 'sample_coverage_all_tau')
TRAIN_E0 = C.OUT / 'envelopes' / 'train_E0.json'
FRAMES_DIR = C.OUT / 'frames'                            # offline stage outputs: per-clip input sha256 (meta)
GATE2_VAL_ENVELOPES = ('E0_q95_ORIG', 'E0orig_q95_ORIG', 'B0_q0_NONE')
CHECK_TOL = 1e-12
ROUTE_RE = re.compile(r'_Route(\d+)_')
ROLE_LSTAR, ROLE_RISK, ROLE_CAND, ROLE_OTHER = 'L*', 'fl_risk', 'candidate', 'not deployed'
OUTPUT_FILES = ('coverage.json', 'coverage.csv', 'per_tau.csv', 'per_clip.csv', 'SHA256SUMS')
# never an output directory: the code tree, the registered and other phases' outputs, and this tool's inputs (the
# aggregator's list, aggregate_v4.PROTECTED, plus the offline inputs read here)
PROTECTED = ('framelease_v2', 'framelease_v3', 'framelease_v4', 'linux', 'third_party', 'checkpoints',
             'outputs/framelease_v2', 'outputs/framelease_v3', 'outputs/framelease_v4/offline_ablation',
             'outputs/framelease_v4/p1_driver', 'outputs/framelease_v4/p1_jobs', 'outputs/framelease_v4/tuning',
             'outputs/framelease_v4/registration', 'outputs/framelease_v4/rl_dev', 'outputs/framelease_v4/envelopes',
             'outputs/framelease_v4/protocol', 'outputs/framelease_v4/smoke_p1_0', 'outputs/framelease_v4/rl_data',
             'outputs/framelease_v4/rl_freeze', 'outputs/framelease_v4/phase_driver')
PROTECTED_PREFIXES = ('outputs/framelease_v4/queue_', 'outputs/framelease_v4/amendment_')
# code whose sha256 enters coverage.json
CODE_FILES = (THIS_REL, 'framelease_v3/envelopes.py', 'framelease_v2/calibration.py', 'framelease_v2/geometry.py',
              'framelease_v4/offline/common.py', 'framelease_v4/offline/analyze.py',
              'framelease_v4/analysis/interim_guard.py', 'framelease_v4/protocol/p1_jobs.py',
              'framelease_v4/protocol/select_stage.py', 'framelease_v4/protocol/registration.py')

GuardRefused = G.GuardRefused        # a request the Sec. 9.11 guard refuses (interim_guard.py): exit 4, logged


class CoverageError(RuntimeError):
    """Inconsistent inputs (envelopes, tuning freeze, clip lists) or a failed check: nothing is written."""


# ============================================================================================ envelopes

ENV_PARAMS = ('sigma_m', 'vbar_mps', 'abar_mps2')


def load_envelopes(envs=None, manifest=REG.MANIFEST):
    """{label: {'path', 'sha256', 'config', 'lambda', 'of', 'calibration_clips', 'env'}} of the kept exported envelopes
    in grid order (p1_jobs.envelopes: each file equals its envelope-manifest sha256 and the export was verified), each
    file also equal to its registration-manifest entry; env is the isotropic envelope iso_inside reads. envs ({label:
    {'path', 'sha256', 'config'}}) replaces p1_jobs.envelopes (tests); manifest None skips the registration check."""
    envs = PJ.envelopes() if envs is None else envs
    reg = REG.read_manifest(manifest) if manifest is not None else None
    out = {}
    for label, e in envs.items():
        path = Path(e['path']) if Path(e['path']).is_absolute() else ROOT / e['path']
        sha = PJ.sha256_file(path)
        if sha != e['sha256']:
            raise CoverageError(f'envelope {label} ({e["path"]}) differs from its manifest sha256')
        if reg is not None and reg.get(PJ.rel(path)) != sha:
            raise CoverageError(f'envelope {label} ({PJ.rel(path)}, sha256 {sha}) differs from its registration '
                                f'manifest entry {reg.get(PJ.rel(path))}')
        doc = json.loads(path.read_text(encoding='utf-8'))
        if doc.get('kind') != 'iso':
            raise CoverageError(f'envelope {label}: kind {doc.get("kind")!r}, only the isotropic form is exported')
        env = {'kind': 'iso'}
        for p in ENV_PARAMS:
            env[p] = {g: float(doc[p][g]) for g in GROUPS}
        meta = doc.get('_meta') or {}
        out[label] = {'path': PJ.rel(path), 'sha256': sha, 'config': e.get('config', meta.get('config')),
                      'lambda': meta.get('lambda'), 'of': meta.get('of'),
                      'calibration_clips': sorted(doc.get('calibration_clips') or []), 'env': env}
    if not out:
        raise CoverageError('no exported envelope')
    return out


def _param_diff(a, b):
    return max(abs(float(a[p][g]) - float(b[p][g])) for p in ENV_PARAMS for g in GROUPS)


def envelope_link(envs, train_e0=TRAIN_E0, gate2=C.GATE2):
    """Check 'envelope_link': each exported envelope equals the train_E0.json configuration it names, that
    configuration is lambda x its base fit ('of', T_q95), and the base fit equals gate2's E0_q95_ORIG (the envelope of
    the gate2 reproduction check), all exactly. {'pass', 'max_abs_diff': {label: x}, 'base_vs_gate2': {base: x},
    'inputs': {path: sha256}}."""
    configs = json.loads(Path(train_e0).read_text(encoding='utf-8'))['configs']
    diffs, base_diffs, inputs, problems = {}, {}, {PJ.rel(train_e0): PJ.sha256_file(train_e0)}, []
    for label, e in envs.items():
        cfg = configs.get(e['config'])
        if cfg is None:
            problems.append(f'{label}: configuration {e["config"]!r} not in {PJ.rel(train_e0)}')
            continue
        d = _param_diff(e['env'], cfg)
        lam, of = cfg.get('lambda'), cfg.get('of')
        if lam is not None and of is not None:
            base = configs[of]
            d = max(d, max(abs(float(cfg[p][g]) - float(lam) * float(base[p][g])) for p in ENV_PARAMS for g in GROUPS))
            if of not in base_diffs:
                g2 = Path(gate2) / 'envelopes' / f'E0_{of.split("_", 1)[1]}_ORIG.json'
                if g2.is_file():
                    base_diffs[of] = _param_diff(base, json.loads(g2.read_text(encoding='utf-8'))['envelope'])
                    inputs[PJ.rel(g2)] = PJ.sha256_file(g2)
                else:
                    problems.append(f'{of}: no gate2 envelope {PJ.rel(g2)}')
        diffs[label] = d
    ok = not problems and all(v == 0.0 for v in list(diffs.values()) + list(base_diffs.values()))
    return {'pass': ok, 'max_abs_diff': diffs, 'base_vs_gate2': base_diffs, 'problems': problems,
            'inputs': dict(sorted(inputs.items()))}


def deployed_envelopes(envs, freeze_path=SS.FREEZE_PATH, protocol=REG.PROTOCOL, seal=REG.SEAL):
    """The deployed E* (Sec. 4.9): {'status', 'deployed': [labels], 'roles': {label: role}, 'tuning_freeze': {...} or
    None, 'warnings'}. status 'tuning_freeze': the freeze exists, its sha256 is cited in Sec. 13 of protocol and
    protocol equals its seal; L* (and, when L* = B0, the fl_risk lease point) is deployed, every other kept envelope is
    'not deployed'. status 'no_tuning_freeze' or 'tuning_freeze_not_cited': every kept envelope is a deployed
    candidate. CoverageError when the freeze is not a tuning freeze or names an envelope other than the exported one."""
    path = Path(freeze_path)
    labels = list(envs)
    if not path.is_file():
        return {'status': 'no_tuning_freeze', 'deployed': labels, 'roles': {lab: ROLE_CAND for lab in labels},
                'tuning_freeze': None, 'warnings': []}
    doc = MV.read_json(path)
    if not isinstance(doc, dict) or doc.get('schema') != SS.FREEZE_SCHEMA:
        raise CoverageError(f'{PJ.rel(path)}: not a tuning freeze (schema {SS.FREEZE_SCHEMA})')
    sha = PJ.sha256_file(path)
    lstar = doc.get('L_star') or {}
    label = lstar.get('label')
    if label not in envs:
        raise CoverageError(f'{PJ.rel(path)}: L* {label!r} is not a kept exported envelope {labels}')
    if lstar.get('envelope_sha256') != envs[label]['sha256'] or PJ.rel(lstar.get('envelope_path') or '') != \
            envs[label]['path']:
        raise CoverageError(f'{PJ.rel(path)}: L* {label} names {lstar.get("envelope_path")} '
                            f'({lstar.get("envelope_sha256")}), not the exported {envs[label]["path"]} '
                            f'({envs[label]["sha256"]})')
    risk = doc.get('fl_risk') if isinstance(doc.get('fl_risk'), dict) else {}
    point = risk.get('lease_point')
    if point is not None and point not in envs:
        raise CoverageError(f'{PJ.rel(path)}: fl_risk lease point {point!r} is not a kept exported envelope')
    protocol, seal = Path(protocol), Path(seal)
    p_sha = PJ.sha256_file(protocol) if protocol.is_file() else None
    cited = p_sha is not None and sha in G.protocol_sec13(protocol.read_text(encoding='utf-8'))
    sealed = p_sha is not None and G.sealed_sha256(seal, protocol) == p_sha
    info = {'path': PJ.rel(path), 'sha256': sha, 'variant': doc.get('variant'), 'L_star': label,
            'L_star_sha256': lstar.get('envelope_sha256'), 'fl_risk_lease_point': point,
            'cited_in_sec13': cited, 'protocol': PJ.rel(protocol), 'protocol_sealed': sealed,
            'registered_protocol': protocol.resolve() == REG.PROTOCOL.resolve()}
    if not (cited and sealed):
        why = 'its sha256 is not cited in Sec. 13 of ' if not cited else 'it is cited, but not sealed, in '
        return {'status': 'tuning_freeze_not_cited', 'deployed': labels, 'roles': {lab: ROLE_CAND for lab in labels},
                'tuning_freeze': info,
                'warnings': [f'tuning freeze {PJ.rel(path)} exists but {why}{PJ.rel(protocol)}: every kept envelope '
                             'is reported as a deployed candidate']}
    roles = {lab: ROLE_OTHER for lab in labels}
    roles[label] = ROLE_LSTAR
    if point is not None and point != label:
        roles[point] = ROLE_RISK
    deployed = [lab for lab in labels if roles[lab] != ROLE_OTHER]
    warnings = [] if info['registered_protocol'] else [f'the tuning freeze is cited by a development copy '
                                                       f'{PJ.rel(protocol)}, not by the registered PROTOCOL.md']
    return {'status': 'tuning_freeze', 'deployed': deployed, 'roles': roles, 'tuning_freeze': info,
            'warnings': warnings}


# ============================================================================================ clips, split and guard

def evaluation_clips(lists, envs, clips=None):
    """(the evaluated clips in VAL order, complete): the 32 VAL clips of lists (common.load_lists), or the given subset
    of them. CoverageError when a clip is a TRAIN clip, a calibration clip of an envelope or not a VAL clip, when the
    VAL and TRAIN lists overlap, or when an envelope was calibrated on clips other than the TRAIN clips: the VAL and
    TRAIN samples are never pooled."""
    val, train = list(lists['val']), list(lists['train'])
    if set(val) & set(train):
        raise CoverageError(f'VAL and TRAIN lists overlap: {sorted(set(val) & set(train))}')
    for label, e in envs.items():
        if e['calibration_clips'] and sorted(e['calibration_clips']) != sorted(train):
            raise CoverageError(f'envelope {label} was calibrated on {e["calibration_clips"]}, not on the TRAIN clips')
    calib = set(train).union(*(set(e['calibration_clips']) for e in envs.values()))
    if clips is None:
        chosen = val
    else:
        chosen = list(dict.fromkeys(clips))
        bad_train = [c for c in chosen if c in calib]
        if bad_train:
            raise CoverageError(f'TRAIN / calibration clips are never evaluated: {bad_train}')
        unknown = [c for c in chosen if c not in val]
        if unknown:
            raise CoverageError(f'not VAL clips of the merged view: {unknown}')
        chosen = [c for c in val if c in set(chosen)]
    if not chosen:
        raise CoverageError('no clip to evaluate')
    if set(chosen) & calib:
        raise CoverageError(f'calibration clips among the evaluated clips: {sorted(set(chosen) & calib)}')
    return chosen, chosen == val


def clip_route(name):
    """The route id of a clip name ('..._Route<N>_...'), None if it gives none."""
    m = ROUTE_RE.search(str(name))
    return m.group(1) if m else None


def guard_clips(clips, freeze=None, routes=None, registered=None):
    """The Sec. 9.11 guard of the evaluated clips: {'status', 'test_routes', 'guarded_clips', 'released_clips',
    'freeze'}. A clip is guarded when its route id is a test route (routes: interim_guard.test_routes' set, default the
    registered split's) or cannot be read. GuardRefused for a guarded clip without a valid analysis-freeze record
    (freeze: interim_guard.load_freeze's view) and, under a development record (registered False), for a guarded clip
    whose route is in the registered split (registered: its test route ids) or unreadable."""
    if routes is None:
        routes, info = G.test_routes()
    else:
        routes, info = {str(r) for r in routes}, {'n_registered': None, 'n_extra': None, 'given': True}
    guarded = [c for c in clips if clip_route(c) is None or clip_route(c) in routes]
    status = 'pre_freeze' if freeze is None else 'frozen' if freeze.get('registered') else 'frozen_development'
    doc = {'status': status, 'rule': G.RULE, 'test_routes': info, 'guarded_clips': guarded, 'released_clips': [],
           'freeze': None if freeze is None else {k: freeze.get(k) for k in ('path', 'sha256', 'frozen', 'registered')}}
    if not guarded:
        return doc
    if freeze is None:
        raise GuardRefused(f'test-route (or unnamed-route) clips before the analysis freeze: {guarded[:5]} '
                           f'(no valid analysis-freeze record; {G.RULE})')
    if not freeze.get('registered'):
        reg = G.registered_split()['test'] if registered is None else {str(r) for r in registered}
        hit = [c for c in guarded if clip_route(c) is None or clip_route(c) in reg]
        if hit:
            raise GuardRefused(f'{G.DEV_WITHHELD}: clips {hit[:5]}')
    doc['released_clips'] = guarded
    return doc


# ============================================================================================ samples

def tau_grid():
    """The offline stage's tau grid: 0 ... T_pred = 3 s in 0.05 s steps (61 points)."""
    return time_grid(C.T_PRED, C.DT)


def clip_val_samples(name, tau, view=C.VIEW):
    """The calibration samples of one clip of the merged view (framelease_v3.envelopes.clip_samples with the offline
    stage's settings, as framelease_v4/offline/envelopes_v4._samples), reduced to what coverage needs: {'group' (P,),
    'iso' (P, M)} plus the clip's 'npz_sha256', 'gt_sha256', 'dataset_split', 'frames' and 'n_frames' (frames after
    the warm-up)."""
    clip = SweepClip(view, name)
    S = envmod.clip_samples(clip, tau, gate_m=C.GATE_M, score_threshold=C.sle.SCORE_THRESHOLD,
                            warmup_steps=C.WARMUP_STEPS)
    return {'group': np.asarray(S['group'], dtype=np.int8), 'iso': np.asarray(S['iso'], dtype=float),
            'npz_sha256': clip.sha256, 'gt_sha256': clip.gt_sha256, 'dataset_split': clip.split,
            'frames': int(len(clip)), 'n_frames': int(S['n_frames'])}


def input_check(clip_meta, frames_dir=FRAMES_DIR):
    """Check 'inputs': each clip's npz and ground-truth sha256 (clip_meta {clip: {'npz_sha256', 'gt_sha256'}}) equal
    those the offline stage recorded (frames_dir/<clip>.npz, meta). {'pass', 'clips', 'mismatch', 'missing',
    'inputs': {frames file: sha256}}."""
    mismatch, missing, inputs = [], [], {}
    for name, m in clip_meta.items():
        p = Path(frames_dir) / f'{name}.npz'
        if not p.is_file():
            missing.append(name)
            continue
        with np.load(p, allow_pickle=False) as z:
            meta = json.loads(str(z['meta']))
        inputs[PJ.rel(p)] = PJ.sha256_file(p)
        if meta.get('clip') != name or meta.get('clip_sha256') != m['npz_sha256'] or \
                meta.get('gt_sha256') != m['gt_sha256']:
            mismatch.append(name)
    return {'pass': not mismatch and not missing, 'clips': len(clip_meta), 'mismatch': mismatch, 'missing': missing,
            'inputs': dict(sorted(inputs.items()))}


# ============================================================================================ coverage

def metric_names(tau):
    """Names of the K = M + 3 count columns: per-tau 'tau_<t>' on the grid, then PATH_KEYS."""
    return [f'tau_{t:g}' for t in np.round(tau, 4)] + list(PATH_KEYS)


def clip_counts(inside, ok, gid, tau):
    """(G, M + 3, 2) int64 [covered, n] of one clip and envelope (iso_inside's inside, ok, gid): per class, per tau of
    the grid (pairs recorded at tau, covered among them), then coverage_summary's whole path on [0, 3 s] and on
    [0, 2.5 s] (pairs recorded at some tau of the horizon, covered at every recorded tau of the interval) and all
    recorded (pair, tau) samples."""
    M = len(tau)
    m25 = int(round(PATH25_S / (tau[1] - tau[0]))) + 1
    out = np.zeros((len(GROUPS), M + 3, 2), dtype=np.int64)
    for k in range(len(GROUPS)):
        sel = gid == k
        ins, okk = inside[sel], ok[sel]
        out[k, :M, 0] = (ins & okk).sum(0)
        out[k, :M, 1] = okk.sum(0)
        whole = okk.any(1)
        out[k, M] = (((ins | ~okk).all(1) & whole).sum(), whole.sum())
        out[k, M + 1] = (((ins[:, :m25] | ~okk[:, :m25]).all(1) & whole).sum(), whole.sum())
        out[k, M + 2] = ((ins & okk).sum(), okk.sum())
    return out


def pooled_check(summary, counts, tau):
    """Check 'pooled': coverage_summary of one envelope (summary) against the summed per-clip counts ((G, M + 3, 2)):
    max abs difference of every coverage and every n (0 expected: both are ratios of the same integer sums)."""
    M = len(tau)
    dt = tau[1] - tau[0]
    worst = 0.0
    for k, g in enumerate(GROUPS):
        s, c = summary.get(g), counts[k]
        if s is None:
            worst = max(worst, float(c[M, 1]))       # no pair of the class: every count must be 0
            continue
        for t in MARKS_S:
            m = int(round(t / dt))
            pt = s['per_tau'][f'{t:g}']
            worst = max(worst, abs(pt['n'] - int(c[m, 1])))
            if pt['coverage'] is not None:
                worst = max(worst, abs(pt['coverage'] - c[m, 0] / c[m, 1]))
        worst = max(worst, abs(s['n_pairs'] - int(c[M, 1])))
        for j, key in enumerate(PATH_KEYS):
            if s[key] is not None:
                worst = max(worst, abs(s[key] - c[M + j, 0] / c[M + j, 1]))
    return worst


def envelope_coverage(samples, envs, tau):
    """Coverage of every envelope on the samples ([(clip, compact samples)] in evaluation order): (counts (n clips, E,
    G, M + 3, 2) int64, {label: coverage_summary of the concatenated samples}, {label: pooled-check difference}). One
    envelope at a time; the concatenated indicators of one envelope are the only pooled arrays held."""
    labels = list(envs)
    counts = np.zeros((len(samples), len(labels), len(GROUPS), len(tau) + 3, 2), dtype=np.int64)
    summaries, diffs = {}, {}
    for e, label in enumerate(labels):
        parts = []
        for c, (_, S) in enumerate(samples):
            inside, ok, gid = envmod.iso_inside(envs[label]['env'], S, tau)
            counts[c, e] = clip_counts(inside, ok, gid, tau)
            parts.append((inside, ok, gid))
        summaries[label] = envmod.coverage_summary(np.concatenate([p[0] for p in parts]),
                                                   np.concatenate([p[1] for p in parts]),
                                                   np.concatenate([p[2] for p in parts]), tau)
        diffs[label] = pooled_check(summaries[label], counts[:, e].sum(0), tau)
        del parts
    return counts, summaries, diffs


def bootstrap(counts, n_boot=C.BOOT_N, seed=C.BOOT_SEED):
    """(point (E, G, K), lo, hi) of the count ratios: point = summed covered / summed n over the clips; lo, hi = the
    clip-level percentile bootstrap 95% interval (framelease_v4/offline/analyze.boot_weights: row 0 the point
    estimate, then n_boot multinomial resamples of the clips, seed; analyze.ci over the finite resamples). NaN where
    there is no pair (point) or no finite resample (interval)."""
    n = counts.shape[0]
    W = np.asarray(OA.boot_weights(n, n_boot, seed), dtype=float)              # (B + 1, n)
    num = np.tensordot(W, counts[..., 0].astype(float), axes=(1, 0))         # (B + 1, E, G, K)
    den = np.tensordot(W, counts[..., 1].astype(float), axes=(1, 0))
    with np.errstate(invalid='ignore', divide='ignore'):
        r = num / den
    point = r[0]
    lo, hi = np.full(point.shape, np.nan), np.full(point.shape, np.nan)
    for idx in np.ndindex(point.shape):
        lo[idx], hi[idx] = OA.ci(r[(slice(1, None),) + idx])
    return point, lo, hi


def _summary_diff(mine, ref):
    """Max abs difference of two coverage_summary class entries (every coverage and every n); inf when the structure
    or a None differs."""
    if mine is None or ref is None:
        return 0.0 if mine is ref else float('inf')
    worst = 0.0
    pairs = [(mine['n_pairs'], ref['n_pairs'])] + [(mine[k], ref[k]) for k in PATH_KEYS]
    for t, v in mine['per_tau'].items():
        r = ref['per_tau'].get(t)
        if r is None:
            return float('inf')
        pairs += [(v['n'], r['n']), (v['coverage'], r['coverage'])]
    for a, b in pairs:
        if (a is None) != (b is None):
            return float('inf')
        if a is not None:
            worst = max(worst, abs(float(a) - float(b)))
    return worst


def gate2_check(samples, tau, gate2=C.GATE2):
    """Check 'gate2': the gate2 study's out-of-sample coverage, reproduced on its 15 VAL clips (a subset of the 32)
    from the same view and code: the clips' npz / ground-truth sha256 equal gate2's config.json, and coverage_summary
    of gate2's envelopes E0_q95_ORIG (= T_q95, the base of E5 and E10), E0orig_q95_ORIG (the v2 file) and B0_q0_NONE
    (no envelope) equals summary.json envelope_coverage_out_of_sample within CHECK_TOL. Skipped ('pass' None) unless
    every gate2 VAL clip is among the samples ({clip: compact samples})."""
    gate2 = Path(gate2)
    cfg = json.loads((gate2 / 'config.json').read_text(encoding='utf-8'))
    ref = json.loads((gate2 / 'summary.json').read_text(encoding='utf-8'))['envelope_coverage_out_of_sample']
    clips = list(cfg['val_clips'])
    inputs = {PJ.rel(gate2 / n): PJ.sha256_file(gate2 / n) for n in ('config.json', 'summary.json')}
    absent = [c for c in clips if c not in samples]
    if absent:
        return {'pass': None, 'skipped': f'{len(absent)} of the {len(clips)} gate2 VAL clips not evaluated',
                'clips': len(clips), 'inputs': inputs}
    sha_bad = [c for c in clips if samples[c]['npz_sha256'] != cfg['clip_npz_sha256'].get(c)
               or samples[c]['gt_sha256'] != cfg['clip_gt_sha256'].get(c)]
    diffs = {}
    for name in GATE2_VAL_ENVELOPES:
        p = gate2 / 'envelopes' / f'{name}.json'
        env = json.loads(p.read_text(encoding='utf-8'))['envelope']
        inputs[PJ.rel(p)] = PJ.sha256_file(p)
        ins = [envmod.iso_inside(env, samples[c], tau) for c in clips]
        cs = envmod.coverage_summary(np.concatenate([i[0] for i in ins]), np.concatenate([i[1] for i in ins]),
                                     np.concatenate([i[2] for i in ins]), tau)
        diffs[name] = max(_summary_diff(cs[g], ref[name][g]) for g in GROUPS)
    ok = not sha_bad and all(v <= CHECK_TOL for v in diffs.values())
    return {'pass': ok, 'clips': len(clips), 'sha256_mismatch': sha_bad, 'max_abs_diff': diffs, 'tolerance': CHECK_TOL,
            'reference': PJ.rel(gate2 / 'summary.json') + ' envelope_coverage_out_of_sample',
            'inputs': dict(sorted(inputs.items()))}


# ============================================================================================ rows and document

def _num(x):
    """A float for JSON / CSV: None for NaN."""
    x = float(x)
    return x if np.isfinite(x) else None


def class_coverage(counts_e, point, lo, hi, tau):
    """{class: {'n_pairs', 'per_tau': {mark: {'n', 'covered', 'coverage', 'ci95'}}, PATH_KEYS...: {'n', 'covered',
    'coverage', 'ci95'}}} of one envelope: counts_e (G, K, 2) summed over clips; point / lo / hi (G, K)."""
    M = len(tau)
    dt = tau[1] - tau[0]
    out = {}
    for k, g in enumerate(GROUPS):
        def cell(j):
            return {'n': int(counts_e[k, j, 1]), 'covered': int(counts_e[k, j, 0]), 'coverage': _num(point[k, j]),
                    'ci95': [_num(lo[k, j]), _num(hi[k, j])]}
        out[g] = {'n_pairs': int(counts_e[k, M, 1]),
                  'per_tau': {f'{t:g}': cell(int(round(t / dt))) for t in MARKS_S},
                  **{key: cell(M + j) for j, key in enumerate(PATH_KEYS)}}
    return out


def coverage_rows(envs, roles, counts, point, lo, hi, tau, clips, complete):
    """coverage.csv: one row per envelope x class x metric (per-tau at the coverage_summary marks, then PATH_KEYS)."""
    M = len(tau)
    dt = tau[1] - tau[0]
    total = counts.sum(0)
    cols = [('per_tau', int(round(t / dt)), t) for t in MARKS_S] + [(key, M + j, None) for j, key in
                                                                    enumerate(PATH_KEYS)]
    rows = []
    for e, (label, env) in enumerate(envs.items()):
        for k, g in enumerate(GROUPS):
            for metric, j, t in cols:
                rows.append({'envelope': label, 'config': env['config'], 'envelope_sha256': env['sha256'],
                             'role': roles[label], 'deployed': roles[label] != ROLE_OTHER, 'class': g,
                             'metric': metric, 'tau_s': t, 'n': int(total[e, k, j, 1]),
                             'covered': int(total[e, k, j, 0]), 'coverage': _num(point[e, k, j]),
                             'ci_lo': _num(lo[e, k, j]), 'ci_hi': _num(hi[e, k, j]),
                             'clips_with_n': int((counts[:, e, k, j, 1] > 0).sum()), 'clips': len(clips),
                             'complete': complete})
    return rows


def per_tau_rows(envs, roles, counts, point, lo, hi, tau):
    """per_tau.csv: one row per envelope x class x tau of the 0.05 s grid (mark: a coverage_summary mark)."""
    total = counts.sum(0)
    marks = {int(round(t / (tau[1] - tau[0]))) for t in MARKS_S}
    rows = []
    for e, label in enumerate(envs):
        for k, g in enumerate(GROUPS):
            for m, t in enumerate(tau):
                rows.append({'envelope': label, 'role': roles[label], 'class': g, 'tau_s': round(float(t), 4),
                             'mark': m in marks, 'n': int(total[e, k, m, 1]), 'covered': int(total[e, k, m, 0]),
                             'coverage': _num(point[e, k, m]), 'ci_lo': _num(lo[e, k, m]), 'ci_hi': _num(hi[e, k, m])})
    return rows


def per_clip_rows(envs, counts, clips, tau):
    """per_clip.csv: one row per envelope x clip x class: pairs, whole-path [0, 3 s] and sample counts."""
    M = len(tau)
    rows = []
    for e, label in enumerate(envs):
        for c, name in enumerate(clips):
            for k, g in enumerate(GROUPS):
                x = counts[c, e, k]
                rows.append({'envelope': label, 'clip': name, 'scenario': C.scenario_of(name), 'class': g,
                             'n_pairs': int(x[M, 1]), 'path_covered_0_3s': int(x[M, 0]),
                             'path_coverage_0_3s': _num(x[M, 0] / x[M, 1]) if x[M, 1] else None,
                             'n_samples': int(x[M + 2, 1]), 'samples_covered': int(x[M + 2, 0]),
                             'sample_coverage_all_tau': _num(x[M + 2, 0] / x[M + 2, 1]) if x[M + 2, 1] else None})
    return rows


CHECKS = ('inputs', 'envelope_link', 'gate2', 'pooled')


def code_sha256():
    """{path: sha256} of this script and the code it reuses (CODE_FILES)."""
    return {p: PJ.sha256_file(ROOT / p) for p in CODE_FILES}


def compute(clips=None, tuning_freeze=SS.FREEZE_PATH, n_boot=C.BOOT_N, seed=C.BOOT_SEED, freeze=None, envs=None,
            lists=None, load=None, checks=CHECKS, protocol=REG.PROTOCOL, seal=REG.SEAL, routes=None, registered=None,
            log=print, on_guard=None):
    """(coverage.json document, {csv name: rows}) of the evaluated clips (evaluation_clips; clips None: the 32 VAL
    clips). Order: envelopes and their registration (load_envelopes), the split (evaluation_clips), the Sec. 9.11
    guard (guard_clips; freeze: interim_guard.load_freeze's view or None; on_guard(guard document) is called once it
    grants, before any clip is read), the deployed E* (deployed_envelopes), the samples clip by clip (load(name, tau),
    default clip_val_samples), the coverage of every envelope, the clip bootstrap and the checks. GuardRefused before
    any clip is read; CoverageError for inconsistent inputs or a failed check. envs / lists / load / routes /
    registered replace the real inputs (tests); checks names the checks that run (CHECKS; the CLI runs all)."""
    tau = tau_grid()
    envs = load_envelopes() if envs is None else envs
    lists = C.load_lists() if lists is None else lists
    chosen, complete = evaluation_clips(lists, envs, clips)
    guard = guard_clips(chosen, freeze, routes, registered)
    if on_guard is not None:
        on_guard(guard)
    dep = deployed_envelopes(envs, tuning_freeze, protocol, seal)
    load = clip_val_samples if load is None else load
    samples, t0 = {}, time.perf_counter()
    for i, name in enumerate(chosen):
        samples[name] = load(name, tau)
        log(f'[{i + 1}/{len(chosen)}] {name}: {len(samples[name]["group"])} matched pairs '
            f'({time.perf_counter() - t0:.0f} s)')
    counts, summaries, pooled = envelope_coverage([(n, samples[n]) for n in chosen], envs, tau)
    point, lo, hi = bootstrap(counts, n_boot, seed)
    res, inputs = {}, {}
    if 'inputs' in checks:
        res['inputs'] = input_check({n: samples[n] for n in chosen})
    if 'envelope_link' in checks:
        res['envelope_link'] = envelope_link(envs)
    if 'gate2' in checks:
        res['gate2'] = gate2_check(samples, tau)
    if 'pooled' in checks:
        res['pooled'] = {'pass': all(v == 0.0 for v in pooled.values()), 'max_abs_diff': pooled}
    for name in CHECKS:
        if name not in res:
            res[name] = {'pass': None, 'skipped': 'not run'}
        inputs.update(res[name].pop('inputs', {}))
    failed = {k: v for k, v in res.items() if v['pass'] is False}
    if failed:
        raise CoverageError(f'failed checks: {json.dumps(failed, sort_keys=True, default=str)}')
    roles = dep['roles']
    env_doc = {}
    for label, e in envs.items():
        env_doc[label] = {k: e[k] for k in ('path', 'sha256', 'config', 'lambda', 'of', 'calibration_clips')}
        env_doc[label].update(params={p: e['env'][p] for p in ENV_PARAMS}, role=roles[label],
                              deployed=roles[label] != ROLE_OTHER)
        inputs[e['path']] = e['sha256']
    inputs[PJ.rel(PJ.ENVELOPE_MANIFEST)] = PJ.sha256_file(PJ.ENVELOPE_MANIFEST)
    if dep['tuning_freeze']:
        inputs[dep['tuning_freeze']['path']] = dep['tuning_freeze']['sha256']
    if guard['test_routes'].get('path'):
        inputs[guard['test_routes']['path']] = guard['test_routes']['sha256']
    totals = counts.sum(0)
    doc = {'schema': SCHEMA,
           'protocol': 'framelease_v4/PROTOCOL.md Secs. 1.3, 4.3, 7.4, 9.13; GAP_AUDIT Sec. 3.7 row R-5',
           'statement': 'Proposition 1 is conditional on its envelope assumption; these are the empirical coverages of '
                        'the envelope on the VAL clips, not a guarantee (Secs. 1.3, 9.13)',
           'arguments': {'clips': None if clips is None else list(clips), 'n_boot': int(n_boot), 'seed': int(seed),
                         'tuning_freeze': PJ.rel(tuning_freeze), 'checks': list(checks)},
           'complete': complete,
           'split': {'evaluated': 'VAL', 'n_clips': len(chosen), 'clips': chosen, 'n_val': len(lists['val']),
                     'train_clips_never_evaluated': list(lists['train']), 'view': PJ.rel(C.VIEW)},
           'settings': {'tau_s': {'start': 0.0, 'stop': float(tau[-1]), 'step': float(tau[1] - tau[0]),
                                  'points': len(tau)},
                        'gate_m': C.GATE_M, 'score_threshold': C.sle.SCORE_THRESHOLD, 'warmup_steps': C.WARMUP_STEPS,
                        'error_range_m': 50.0, 'marks_s': list(MARKS_S), 'path_short_s': PATH25_S,
                        'bootstrap': {'unit': 'clip', 'resamples': int(n_boot), 'seed': int(seed),
                                      'interval': 'percentile 95%'}},
           'deployed': dep,
           'envelopes': env_doc,
           'coverage': {label: class_coverage(totals[e], point[e], lo[e], hi[e], tau)
                        for e, label in enumerate(envs)},
           'coverage_summary': summaries,
           'clips': {n: {'route_id': clip_route(n), 'npz_sha256': samples[n]['npz_sha256'],
                         'gt_sha256': samples[n]['gt_sha256'], 'dataset_split': samples[n]['dataset_split'],
                         'frames': samples[n]['frames'], 'frames_after_warmup': samples[n]['n_frames'],
                         'pairs': {g: int((np.asarray(samples[n]['group']) == k).sum()) for k, g in enumerate(GROUPS)}}
                     for n in chosen},
           'checks': res,
           'interim_guard': guard,
           'inputs': dict(sorted(inputs.items())),
           'code': code_sha256(),
           'environment': {'python': platform.python_version(), 'numpy': np.__version__}}
    tables = {'coverage.csv': coverage_rows(envs, roles, counts, point, lo, hi, tau, chosen, complete),
              'per_tau.csv': per_tau_rows(envs, roles, counts, point, lo, hi, tau),
              'per_clip.csv': per_clip_rows(envs, counts, chosen, tau)}
    return doc, tables


# ============================================================================================ outputs and CLI

def check_out_dir(out):
    """PermissionError for an output directory inside the code tree, another phase's directories or this tool's
    inputs (PROTECTED). A relative out is taken from the working directory, where it is written."""
    rel = PJ.rel(Path(out).resolve())
    if Path(rel).is_absolute():
        return
    if rel in ('.', 'outputs', 'outputs/framelease_v4') or rel in PROTECTED \
            or any(rel.startswith(p + '/') for p in PROTECTED) or rel.startswith(PROTECTED_PREFIXES):
        raise PermissionError(f'{rel}: prop1_coverage never writes there (PROTECTED)')


def _write_text(path, text):
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    tmp.replace(path)


def _write_csv(path, rows):
    tmp = Path(str(path) + '.tmp')
    MV.write_csv(tmp, rows)
    tmp.replace(path)


def write_outputs(out, doc, tables, force=False):
    """coverage.json (doc plus the sha256 of the three CSV files), coverage.csv, per_tau.csv, per_clip.csv and
    SHA256SUMS under out; FileExistsError when earlier outputs exist and force is not given. The guard log is never
    touched here. Returns the written document."""
    out = Path(out)
    check_out_dir(out)
    present = [n for n in OUTPUT_FILES if (out / n).exists()]
    if present and not force:
        raise FileExistsError(f'{PJ.rel(out)} already holds {present} (use --force to replace them)')
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        if not rows:
            raise CoverageError(f'{name}: no rows')
        _write_csv(out / name, rows)
    doc = {**doc, 'outputs': {n: PJ.sha256_file(out / n) for n in sorted(tables)}}
    _write_text(out / 'coverage.json', json.dumps(doc, indent=1, sort_keys=True, default=str) + '\n')
    names = sorted(list(tables) + ['coverage.json'])
    _write_text(out / 'SHA256SUMS', ''.join(f'{PJ.sha256_file(out / n)}  {n}\n' for n in names))
    return doc


def _fmt(x):
    return 'n/a' if x is None else f'{x:.3f}'


def summary_lines(doc, out):
    """Console summary: deployed status, then per envelope and class the whole-path, sample and per-tau coverages."""
    d = doc['deployed']
    lines = [f'Proposition-1 coverage on {doc["split"]["n_clips"]} VAL clips'
             f'{"" if doc["complete"] else " (SUBSET: incomplete)"} -> {PJ.rel(out)}',
             f'deployed E*: {d["status"]}: {d["deployed"]} (roles {d["roles"]})']
    lines += [f'WARNING: {w}' for w in d['warnings']]
    for label, cov in doc['coverage'].items():
        for g in GROUPS:
            c = cov[g]
            p3, ps = c['path_coverage_0_3s'], c['sample_coverage_all_tau']
            taus = ' '.join(f'{t}:{_fmt(v["coverage"])}' for t, v in c['per_tau'].items())
            lines.append(f'  {label:<4} {doc["envelopes"][label]["role"]:<12} {g:<10} pairs {c["n_pairs"]:>6}  '
                         f'path[0,3s] {_fmt(p3["coverage"])} [{_fmt(p3["ci95"][0])}, {_fmt(p3["ci95"][1])}]  '
                         f'sample {_fmt(ps["coverage"])}  per-tau {taus}')
    chk = {k: v['pass'] for k, v in doc['checks'].items()}
    lines.append(f'checks: {chk}; interim guard: {doc["interim_guard"]["status"]}, '
                 f'{len(doc["interim_guard"]["guarded_clips"])} guarded clips')
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out', required=True, help='output directory (never a protected one)')
    ap.add_argument('--tuning-freeze', default=str(SS.FREEZE_PATH),
                    help='select_stage.py selection.json (Sec. 4.9); absent or not cited in Sec. 13: every kept '
                         'envelope is a deployed candidate')
    ap.add_argument('--clips', nargs='+', help='development: a subset of the VAL clips (the result is incomplete)')
    ap.add_argument('--n-boot', type=int, default=C.BOOT_N, help='clip bootstrap resamples (Sec. 7.4: 2000)')
    ap.add_argument('--seed', type=int, default=C.BOOT_SEED, help='bootstrap seed (Sec. 7.4: 20261109)')
    ap.add_argument('--analysis-freeze', help='a valid analysis-freeze record (interim_guard.py); needed only for a '
                                              'clip on a test route (Sec. 9.11)')
    ap.add_argument('--force', action='store_true', help='replace earlier outputs in --out')
    a = ap.parse_args(argv)
    if a.n_boot < 1:
        ap.error('--n-boot must be positive')
    argv = list(sys.argv if argv is None else [sys.argv[0], *argv])
    log = Path(a.out) / G.LOG_NAME
    params = {'clips': a.clips, 'analysis_freeze': a.analysis_freeze, 'tuning_freeze': a.tuning_freeze,
              'out': PJ.rel(a.out)}

    def refuse(reason, code, freeze=None, logged=True):
        if logged:
            G.log_request(log, 'prop1_coverage', 'refused', reason, freeze, argv, **params)
        where = f', logged in {PJ.rel(log)}' if logged else ''
        print(f'REFUSED{" (interim-look guard" + where + ")" if code == 4 else ""}: {reason}', file=sys.stderr)
        return code

    try:
        check_out_dir(a.out)
    except PermissionError as e:                       # nothing is written into a protected directory, not even a log
        return refuse(str(e), 1, logged=False)
    if not a.force and any((Path(a.out) / n).exists() for n in OUTPUT_FILES):
        return refuse(f'{a.out} already holds outputs (use --force to replace them)', 1)
    freeze = None

    def granted(guard):                                # logged before any clip is read
        G.log_request(log, 'prop1_coverage', 'granted', None, freeze, argv, guarded_clips=guard['guarded_clips'],
                      **params)

    try:
        if a.analysis_freeze:
            freeze = G.load_freeze(a.analysis_freeze)
        doc, tables = compute(a.clips, a.tuning_freeze, a.n_boot, a.seed, freeze=freeze, on_guard=granted)
    except GuardRefused as e:
        return refuse(str(e), 4, freeze)
    except (CoverageError, FileNotFoundError, ValueError, KeyError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2
    doc = write_outputs(a.out, doc, tables, force=a.force)
    for line in summary_lines(doc, a.out):
        print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
