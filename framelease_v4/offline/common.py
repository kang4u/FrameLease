"""Shared constants, clip lists, envelope configurations and small helpers of the v4 offline lease ablation.

CPU only. Read-only imports of framelease_v2 (sweep reader, lease kernels, realized validity) and framelease_v3
(gate2 constants and kernels, residual envelopes, tracking clip lists). Nothing in those packages is modified; outputs
go only to outputs/framelease_v4/offline_ablation/.

Three lease designs, all on the same depth-1 UniDriveVLA plans, the same detections (vehicles and pedestrians with
score >= 0.1) and the same realized validity:
  AGE     Age-Only lease: H = T_age for every plan (fixed observation-age deadline), knob T_age.
  GLOBAL  Global-Margin lease (v2, framelease_v2/lease.py margin_mode='global'): m_j = min over the whole plan horizon
          [0, 3 s] of the footprint clearance to detection j minus d_safe; H_j = sup{D : m_j - B_j(D) > delta} with the
          staleness-indexed envelope B(D) = vbar D + abar D^2 / 2 + sigma; H = min_j H_j, capped (2.5 s aligned cap;
          v2 deployed 2.0 s, reported as a sensitivity). Knob: the envelope.
  SUFFIX  Suffix-Aligned lease (outline Eq. 1-3, framelease_v3/suffix_lease_eval.py): M(Delta) = min over tau in
          [Delta, Delta + T_c] of m(tau) - B(tau); H = first Delta with M(Delta) <= delta, capped at Hbar = T_pred - T_c.
          Knob: the envelope.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault('OMP_NUM_THREADS', '1')
sys.dont_write_bytecode = True

import hashlib  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v3 import suffix_lease_eval as sle  # noqa: E402  (constants and kernels, read-only)

VIEW = ROOT / 'outputs/framelease_v3/c1_sweep_ext/merged_37clips_20261109T145344Z'
MERGE_NOTE = ROOT / 'outputs/framelease_v3/c1_sweep_ext/MERGE_NOTE.json'
GATE2 = ROOT / 'outputs/framelease_v3/gate2_offline/gate2_20261109'
TRK_ENV = ROOT / 'outputs/framelease_v3/tracking_offline/run_20261110/envelopes/raw.npz'
V2_PARAMS = sle.OLD_PARAMS            # v2 deployed lease file (E0-orig q95, global, h_max 2.0)
V2_C2EVAL = ROOT / 'outputs/framelease_v2/c2_eval/merged20_q95_envelope'
OUT = ROOT / 'outputs/framelease_v4/offline_ablation'
CODE_DIR = Path(__file__).resolve().parent

T_PRED, DT, D_SAFE, DELTA = sle.T_PRED, sle.DT, sle.D_SAFE, sle.DELTA      # 3.0 s, 0.05 s, 0.5 m, 0.2 m
T_C = 0.5
HBAR = T_PRED - T_C                                                       # 2.5 s
DEPTH = 1
WARMUP_STEPS = sle.WARMUP_STEPS
GATE_M = sle.GATE_M
STATIONARY_MPS = 0.1                  # static V = 0 plans: ego speed below this (extend/conflict_counts.py)
OVER_EPS = sle.OVER_EPS               # violation: H > V_suf + 1e-6
GLOBAL_CAPS = (2.5, 2.0)              # aligned cap (primary) and the v2 deployed cap (sensitivity)

L_REL_FAST = 0.457                    # fast-prefix depth-1 release p50 (fastprefix run_20261110, Table 8)
L_REL_MEAS = 0.896                    # measured depth-1 release p50 (C1_RESULTS Sec. 1)
OVERHEAD_S = 0.05
NEEDS = {'fast': round(2 * L_REL_FAST + OVERHEAD_S, 3), 'meas': round(2 * L_REL_MEAS + OVERHEAD_S, 3)}   # 0.964, 1.842
NEED_LABEL = {'fast': 'fast-prefix need 2 x 0.457 + 0.05 = 0.964 s', 'meas': 'measured need 2 x 0.896 + 0.05 = 1.842 s'}

BOOT_N = 2000
BOOT_SEED = 20261109
ALPHAS = (0.02, 0.05, 0.10, 0.15, 0.20, 0.30)       # risk-matched levels (frontier)
NESTED_ALPHAS = (0.05, 0.10)                        # nested leave-one-clip-out and TRAIN selection
PRIMARY_ALPHA = 0.05

# ----------------------------------------------------------------------------- knob grids
T_AGE_GRID = tuple(round(0.05 * i, 2) for i in range(int(round(HBAR / 0.05)) + 1))          # 0 ... 2.5 s
Q_GRID_TRAIN = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 0.995)
LAMBDA_GRID = tuple(round(0.05 * i, 2) for i in range(41))                                   # 0 ... 2.0
Q_GRID_LOCO = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 0.995)                                    # tracking raw.npz
GROUPS = ('vehicle', 'pedestrian')

STATUS_CODES = {'none': 0, 'confident': 1, 'low_confidence': 2, 'undetected': 3, 'absent_at_capture': 4}
GROUP_CODES = {'none': 0, 'vehicle': 1, 'pedestrian': 2}
LEASE_STATUS_CODES = {'ok': 0, 'invalid_plan': 1, 'invalid_detection': 2}


def qtag(q):
    return sle.qtag(q)


def lam_tag(lam):
    return f'{lam:.2f}'


def train_config_names():
    """TRAIN-calibrated envelope configurations (evaluated on every clip) + the v2 deployed file."""
    names = [f'T_q{qtag(q)}' for q in Q_GRID_TRAIN] + [f'T_x{lam_tag(l)}' for l in LAMBDA_GRID] + ['V2file']
    return names


def loco_config_names():
    """LOCO-36 envelope configurations (VAL clips only; sensitivity)."""
    return [f'L_q{qtag(q)}' for q in Q_GRID_LOCO] + [f'L_x{lam_tag(l)}' for l in LAMBDA_GRID]


def config_label(name):
    if name == 'V2file':
        return 'v2 deployed E0-orig q95 (TRAIN)'
    fam, rest = name.split('_', 1)
    src = 'TRAIN' if fam == 'T' else 'LOCO-36'
    if rest.startswith('q'):
        return f'E0 q{rest[1:]} ({src})'
    return f'{rest[1:]} x E0 q95 ({src})'


def config_family(name):
    if name == 'V2file':
        return 'v2file'
    fam, rest = name.split('_', 1)
    return f'{fam}_{"q" if rest.startswith("q") else "x"}'


# ----------------------------------------------------------------------------- clip lists

def load_lists():
    """TRAIN (5), VAL (32 = gate2's 15 + the 17 new clips), all 37 (as framelease_v3/tracking/common.load_lists)."""
    from framelease_v2.calibration import TRAIN_CLIPS
    g2 = json.loads((GATE2 / 'config.json').read_text(encoding='utf-8'))
    note = json.loads(MERGE_NOTE.read_text(encoding='utf-8'))
    val15 = list(g2['val_clips'])
    new17 = [c['clip'] for c in note['new_clips']]
    train = list(TRAIN_CLIPS)
    if list(g2['train_clips']) != train:
        raise SystemExit('gate2 TRAIN list differs from calibration.TRAIN_CLIPS')
    val = sorted(val15 + new17)
    have = sorted(p.stem for p in (VIEW / 'clips').glob('*.npz'))
    if sorted(train + val) != have:
        raise SystemExit(f'view {VIEW} does not hold exactly TRAIN + VAL: {sorted(set(have) ^ set(train + val))}')
    flags = [f['clip'] for f in note.get('flags', [])]
    return {'train': train, 'val': val, 'val15': sorted(val15), 'new17': sorted(new17), 'all': sorted(train + val),
            'slope_flagged': flags}


def scenario_of(clip):
    return clip.split('_')[0]


# ----------------------------------------------------------------------------- io helpers

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def free_gb(path=ROOT):
    return shutil.disk_usage(path).free / 1e9


def check_disk(min_gb=1.5, log=print):
    g = free_gb()
    if g < min_gb:
        log(f'STOP: free disk {g:.2f} GB < {min_gb} GB')
        raise SystemExit(3)
    return g


def dir_size_mb(p):
    return sum(f.stat().st_size for f in Path(p).rglob('*') if f.is_file()) / 1e6


def atomic_savez(path, **arrays):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + '.tmp.npz')
    np.savez_compressed(tmp, **arrays)
    os.replace(tmp, path)


def atomic_write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    os.replace(tmp, path)


def clean_json(x):
    if isinstance(x, dict):
        return {str(k): clean_json(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean_json(v) for v in x]
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.floating):
        v = float(x)
        return v if np.isfinite(v) else None
    if isinstance(x, float):
        return x if np.isfinite(x) else None
    if isinstance(x, np.ndarray):
        return clean_json(x.tolist())
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def write_json(path, obj):
    atomic_write_text(path, json.dumps(clean_json(obj), indent=1, sort_keys=False) + '\n')


def write_csv(path, rows, fields=None):
    import csv
    import io
    rows = list(rows)
    if fields is None:
        fields = []
        for r in rows:
            for k in r:
                if k not in fields:
                    fields.append(k)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction='ignore', lineterminator='\n')
    w.writeheader()
    for r in rows:
        w.writerow({k: _fmt(v) for k, v in r.items()})
    atomic_write_text(path, buf.getvalue())


def _fmt(v):
    if isinstance(v, (float, np.floating)):
        v = float(v)
        if not np.isfinite(v):
            return ''
        return f'{v:.6g}'
    if isinstance(v, (list, tuple)):
        return json.dumps(clean_json(v))
    return v


def log_progress(msg):
    """Append a timestamped line to OUT/PROGRESS.md (survives a lost gateway)."""
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / 'PROGRESS.md', 'a', encoding='utf-8') as f:
        f.write(f'- {time.strftime("%Y-%m-%d %H:%M:%S")} {msg}\n')


def code_sha256():
    return {str(p.relative_to(ROOT)): sha256_file(p) for p in sorted(CODE_DIR.rglob('*.py'))}
