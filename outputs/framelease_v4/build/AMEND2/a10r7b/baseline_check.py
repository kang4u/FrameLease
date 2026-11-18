"""Read-only registration check of item a10r7b (start and end of the item).

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/a10r7b/baseline_check.py

Prints: the number of files of outputs/framelease_v4/p1_driver/registered_baseline.json 'files', those whose file on
disk differs from the baseline sha256, those whose sealed-manifest sha256 differs from the baseline, the manifest files
that differ from the tree (registered or not), and the sha256 of PROTOCOL.md, MANIFEST.sha256, SEAL.sha256 and
REGISTRATION.json. Writes nothing. Exit 0 when no baseline file differs (tree or manifest), else 1.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path('/home/kang/Desktop/DAC')
BASELINE = ROOT / 'outputs/framelease_v4/p1_driver/registered_baseline.json'
MANIFEST = ROOT / 'outputs/framelease_v4/registration/MANIFEST.sha256'


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    base = json.loads(BASELINE.read_text(encoding='utf-8'))['files']
    man = {}
    for ln in MANIFEST.read_text(encoding='utf-8').splitlines():
        if '  ' in ln:
            digest, path = ln.split('  ', 1)
            man[path] = digest
    tree_differ = [k for k, v in base.items() if not (ROOT / k).is_file() or sha256(ROOT / k) != v]
    man_differ = [k for k, v in base.items() if man.get(k) != v]
    man_vs_tree = [k for k, v in man.items() if not (ROOT / k).is_file() or sha256(ROOT / k) != v]
    print(f'registered_baseline.json files: {len(base)}')
    print(f'baseline files differing from the tree: {tree_differ or "none"}')
    print(f'baseline files differing from the sealed manifest: {man_differ or "none"}')
    print(f'manifest files: {len(man)}; differing from the tree: '
          f'{[(k, "registered" if k in base else "unregistered") for k in man_vs_tree] or "none"}')
    for p in ('framelease_v4/PROTOCOL.md', 'outputs/framelease_v4/registration/MANIFEST.sha256',
              'outputs/framelease_v4/registration/SEAL.sha256', 'outputs/framelease_v4/registration/REGISTRATION.json'):
        print(f'{p}: {sha256(ROOT / p)}')
    return 0 if not tree_differ and not man_differ else 1


if __name__ == '__main__':
    sys.exit(main())
