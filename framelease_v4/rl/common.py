"""Shared helpers of framelease_v4/rl: paths, hashing, atomic JSON, the test-route guard, progress files.

Everything here is CPU-only and side-effect free except the explicit writers (atomic_json, write_jsonl, Progress).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]                      # /home/kang/Desktop/DAC
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_ROOT = ROOT / 'outputs' / 'framelease_v4' / 'rl_dev'
PILOT_ROOT = ROOT / 'outputs' / 'framelease_v3' / 'fastprefix' / 'run_20261110' / 'pilot'
TEST_ROUTES_JSON = ROOT / 'outputs' / 'framelease_v2' / 'closed_loop_matrix' / 'routes.json'
ROUTES_XML = ROOT / 'third_party' / 'UniDriveVLA-linux' / 'Bench2Drive' / 'bench2drive' / 'leaderboard' / 'data' / \
    'bench2drive220.xml'
# the scorer the evaluator imports ($PYTHONPATH of linux/env.sh: third_party/bench2drive-linux/leaderboard first)
B2D_STATISTICS = ROOT / 'third_party' / 'bench2drive-linux' / 'leaderboard' / 'leaderboard' / 'utils' / \
    'statistics_manager.py'
B2D_CRITERIA = ROOT / 'third_party' / 'bench2drive-linux' / 'scenario_runner' / 'srunner' / 'scenariomanager' / \
    'scenarioatomics' / 'atomic_criteria.py'
V4_RL_DIR = Path(__file__).resolve().parent

# protected trees: v4 never writes there (checked by writers below)
PROTECTED = (ROOT / 'framelease_v2', ROOT / 'framelease_v3', ROOT / 'outputs' / 'framelease_v2',
             ROOT / 'outputs' / 'framelease_v3')


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def utc_stamp():
    return time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())


def _check_writable(path):
    p = Path(path).resolve()
    for prot in PROTECTED:
        try:
            p.relative_to(prot.resolve())
        except ValueError:
            continue
        raise PermissionError(f'framelease_v4 never writes under {prot}: {p}')
    return p


def jsonable(x):
    """JSON-safe copy: numpy scalars / arrays to Python, non-finite floats to None, tuples to lists."""
    try:
        import numpy as np
    except ImportError:                                           # pragma: no cover
        np = None
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if np is not None:
        if isinstance(x, np.ndarray):
            return jsonable(x.tolist())
        if isinstance(x, np.generic):
            return jsonable(x.item())
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, Path):
        return str(x)
    return x


def atomic_write_text(path, text):
    p = _check_writable(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.' + uuid.uuid4().hex + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)
    return p


def atomic_json(path, obj, indent=1):
    return atomic_write_text(path, json.dumps(jsonable(obj), indent=indent, sort_keys=True, allow_nan=False) + '\n')


def write_jsonl(path, rows):
    text = ''.join(json.dumps(jsonable(r), sort_keys=True, allow_nan=False) + '\n' for r in rows)
    return atomic_write_text(path, text)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_jsonl(path):
    out = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def test_route_ids(path=TEST_ROUTES_JSON):
    """The 44 held-out test routes of the closed-loop matrix (one per scenario type; v2 PREREGISTRATION Sec. 3).

    Nothing in the RL pipeline may train or tune on these routes."""
    d = read_json(path)
    ids = {str(r['route_id']) for r in d['routes']}
    if len(ids) != 44:
        raise ValueError(f'{path}: expected 44 test routes, found {len(ids)}')
    return frozenset(ids)


def code_hashes(names=None):
    """sha256 of the v4 RL sources (provenance of every output)."""
    files = sorted(V4_RL_DIR.glob('*.py')) if names is None else [V4_RL_DIR / n for n in names]
    return {f.name: sha256_file(f) for f in files if f.is_file()}


class Progress:
    """Append-only progress journal (JSON lines) + resumable stage markers for a flaky session."""

    def __init__(self, out_dir):
        self.dir = _check_writable(out_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / 'progress.jsonl'

    def done(self):
        if not self.path.is_file():
            return {}
        out = {}
        for r in read_jsonl(self.path):
            if r.get('status') == 'done':
                out[r['stage']] = r
        return out

    def mark(self, stage, status='done', **info):
        row = {'stage': stage, 'status': status, 'utc': utc_stamp(), **jsonable(info)}
        with open(self.path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(row, sort_keys=True) + '\n')
            f.flush()
            os.fsync(f.fileno())
        return row


__all__ = ['ROOT', 'OUT_ROOT', 'PILOT_ROOT', 'TEST_ROUTES_JSON', 'ROUTES_XML', 'B2D_STATISTICS', 'B2D_CRITERIA',
           'sha256_file', 'sha256_bytes', 'utc_stamp', 'jsonable', 'atomic_write_text', 'atomic_json', 'write_jsonl',
           'read_json', 'read_jsonl', 'test_route_ids', 'code_hashes', 'Progress']
