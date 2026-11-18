#!/usr/bin/env python3
"""Registration manifest and seal of framelease_v4/PROTOCOL.md (Secs. 12.2, 13.1). CPU only; reads files, writes only
under outputs/framelease_v4/registration/.

  cd /home/kang/Desktop/DAC
  .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/registration.py --verify          # check the manifest
  .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/registration.py --write-manifest  # at registration
  .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/registration.py --seal            # after the entry

MANIFEST.sha256 (sha256sum format; paths relative to the project root, absolute outside it) lists every file the
registered plan depends on, except PROTOCOL.md itself (it cites the manifest's sha256 in its registration entry):
  * every framelease_v4 file (sources, tests, documents) except PROTOCOL.md, PIPELINE_STATE.md (workflow state),
    .protocol_progress.md (scratch) and byte-code caches;
  * every file pinned by a registered Phase-1 job line (require_sha256 of the P1-0 smoke block and of the FULL and
    TRIMMED job files: the v2 / v3 / fast-prefix / v4 sources, the routes XML, linux/env.sh, the envelopes);
  * the generated tables, job files, stage specs and checks, the envelope export, the offline inputs of the lease, the
    RL collection plans, the text extracts of the outline and the guide, the test logs of the registration;
  * the files of PROTOCOL Sec. 12.1 (outline, guide, test routes, checkpoint, v2 q95 lease file, statistics module,
    runner, RA rule, RND report).
SEAL.sha256 then holds the sha256 of PROTOCOL.md (with its registration entry) and of MANIFEST.sha256; REGISTRATION.json
records the same with the time. `sha256sum -c outputs/framelease_v4/registration/SEAL.sha256` (from the project root)
shows that neither changed since registration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG_DIR = ROOT / 'outputs/framelease_v4/registration'
MANIFEST = REG_DIR / 'MANIFEST.sha256'
SEAL = REG_DIR / 'SEAL.sha256'
RECORD = REG_DIR / 'REGISTRATION.json'
PROTOCOL = ROOT / 'framelease_v4/PROTOCOL.md'
EXCLUDE_V4 = {'framelease_v4/PROTOCOL.md', 'framelease_v4/PIPELINE_STATE.md', 'framelease_v4/.protocol_progress.md'}
REGISTERED_JOB_FILES = ('outputs/framelease_v4/p1_jobs/P1-0/b00_smoke.jsonl',
                        'outputs/framelease_v4/p1_jobs/FULL/b01_ref.jsonl',
                        'outputs/framelease_v4/p1_jobs/FULL/b02_lease_s1.jsonl',
                        'outputs/framelease_v4/p1_jobs/FULL/b03_event_s1.jsonl',
                        'outputs/framelease_v4/p1_jobs/TRIMMED/b02_lease_s1.jsonl',
                        'outputs/framelease_v4/p1_jobs/TRIMMED/b03_event_s1.jsonl')
OUTPUT_GLOBS = ('outputs/framelease_v4/envelopes/*', 'outputs/framelease_v4/protocol/*.json',
                'outputs/framelease_v4/protocol/*.md', 'outputs/framelease_v4/protocol/MANIFEST.sha256',
                'outputs/framelease_v4/protocol/sources/*', 'outputs/framelease_v4/p1_jobs/*',
                'outputs/framelease_v4/p1_jobs/*/*', 'outputs/framelease_v4/rl_dev/collection_plan/*.json',
                'outputs/framelease_v4/readiness_fixes/pytest_*.log')
OUTPUT_FILES = ('outputs/framelease_v4/offline_ablation/frontier.csv',
                'outputs/framelease_v4/offline_ablation/envelopes/train_E0.json')
SEC_12_1 = ('/home/kang/Desktop/NEW/FrameLease1109.docx',
            '/home/kang/Downloads/FrameLease+的+Introduction+可以从+背景.docx',
            'outputs/framelease_v2/closed_loop_matrix/routes.json',
            'third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/data/bench2drive220.xml',
            'checkpoints/UniDriveVLA/b5ac33e9483f6f61633c53353a8b53fbd96e2bc5/UniDriveVLA_Stage3_Bench2drive_2B.pt',
            'outputs/framelease_v2/c2_calibration/full_20261107T045343Z/lease_params_q95_envelope.json',
            'framelease_v2/analyze_closed_loop.py', 'framelease_v2/gpu_queue.py',
            'framelease_v3/renewal/renewal_compute.py', 'framelease_v3/RND_REPORT_20261110.md')


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def _key(path):
    p = Path(path)
    p = p if p.is_absolute() else ROOT / p
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def job_pins(files=REGISTERED_JOB_FILES):
    """{path: sha256} union of require_sha256 over the registered job lines (a path pinned twice must agree)."""
    pins = {}
    for f in files:
        for line in (ROOT / f).read_text(encoding='utf-8').splitlines():
            for k, v in json.loads(line)['require_sha256'].items():
                if pins.setdefault(k, v) != v:
                    raise ValueError(f'{k} pinned with two different sha256')
    return pins


def manifest_paths():
    paths = set()
    for p in (ROOT / 'framelease_v4').rglob('*'):
        rel = _key(p)
        if p.is_file() and '__pycache__' not in p.parts and rel not in EXCLUDE_V4:
            paths.add(rel)
    paths |= set(job_pins())
    for g in OUTPUT_GLOBS:
        paths |= {_key(p) for p in ROOT.glob(g) if p.is_file()}
    paths |= {_key(p) for p in OUTPUT_FILES + SEC_12_1}
    return sorted(paths)


def build_manifest():
    lines, pins = [], job_pins()
    for rel in manifest_paths():
        p = Path(rel) if Path(rel).is_absolute() else ROOT / rel
        sha = sha256_file(p)
        if rel in pins and pins[rel] != sha:
            raise ValueError(f'{rel}: the tree differs from the job pins')
        lines.append(f'{sha}  {rel}\n')
    return ''.join(lines)


def read_manifest(path=MANIFEST):
    out = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        sha, rel = line.split('  ', 1)
        out[rel] = sha
    return out


def verify(path=MANIFEST):
    """[(path, expected, found)] of the manifest entries that differ from the tree ([] if all match)."""
    bad = []
    for rel, sha in read_manifest(path).items():
        p = Path(rel) if Path(rel).is_absolute() else ROOT / rel
        try:
            got = sha256_file(p)
        except OSError as e:
            got = f'unreadable ({e.strerror})'
        if got != sha:
            bad.append((rel, sha, got))
    return bad


def seal():
    if not MANIFEST.is_file():
        raise FileNotFoundError(f'{MANIFEST} not written yet')
    man_sha, pro_sha = sha256_file(MANIFEST), sha256_file(PROTOCOL)
    if man_sha not in PROTOCOL.read_text(encoding='utf-8'):
        raise ValueError('PROTOCOL.md does not cite the manifest sha256 in its registration entry')
    SEAL.write_text(f'{pro_sha}  {_key(PROTOCOL)}\n{man_sha}  {_key(MANIFEST)}\n', encoding='utf-8')
    RECORD.write_text(json.dumps({'schema': 'framelease_v4.registration/1', 'variant': 'FULL',
                                  'sealed': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'protocol': _key(PROTOCOL),
                                  'protocol_sha256': pro_sha, 'manifest': _key(MANIFEST), 'manifest_sha256': man_sha,
                                  'manifest_files': len(read_manifest()),
                                  'script_sha256': sha256_file(Path(__file__))}, indent=1, sort_keys=True) + '\n',
                      encoding='utf-8')
    return pro_sha, man_sha


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--write-manifest', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--seal', action='store_true')
    a = ap.parse_args(argv)
    if a.write_manifest:
        if MANIFEST.exists() and not a.force:
            print(f'refusing to overwrite {MANIFEST} (registered; use --force only before the registration entry)',
                  file=sys.stderr)
            return 2
        REG_DIR.mkdir(parents=True, exist_ok=True)
        text = build_manifest()
        MANIFEST.write_text(text, encoding='utf-8')
        print(f'wrote {MANIFEST}: {text.count(chr(10))} files, sha256 {sha256_file(MANIFEST)}')
    if a.verify:
        bad = verify()
        print('manifest: OK' if not bad else f'manifest: {len(bad)} files differ: {bad[:10]}')
        if SEAL.is_file():
            for line in SEAL.read_text(encoding='utf-8').splitlines():
                sha, rel = line.split('  ', 1)
                print(f'seal {rel}: {"OK" if sha256_file(ROOT / rel) == sha else "CHANGED"}')
        if bad:
            return 1
    if a.seal:
        pro, man = seal()
        print(f'sealed: PROTOCOL.md {pro}, manifest {man}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
