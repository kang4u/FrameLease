"""Reviewer's start / end check (read only): registration.py --verify; every file of the P1 stage driver's and of the
phase driver's registered baseline against the tree and the sealed manifest; the seal against PROTOCOL.md; files
under framelease_v4/ changed since a reference time, new __pycache__ directories and empty files there.

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/a10r7b/review/end_check.py [--since 'YYYY-MM-DD HH:MM']
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/home/kang/Desktop/DAC')
PY = str(ROOT / '.conda-unidrive-linux/bin/python')
MAN = ROOT / 'outputs/framelease_v4/registration/MANIFEST.sha256'
SEAL = ROOT / 'outputs/framelease_v4/registration/SEAL.sha256'
BASELINES = {'p1_driver': ROOT / 'outputs/framelease_v4/p1_driver/registered_baseline.json',
             'phase_driver': ROOT / 'outputs/framelease_v4/phase_driver/registered_baseline.json'}


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    since = sys.argv[sys.argv.index('--since') + 1] if '--since' in sys.argv else None
    r = subprocess.run([PY, '-I', '-B', str(ROOT / 'framelease_v4/protocol/registration.py'), '--verify'], cwd=ROOT,
                       capture_output=True, text=True)
    print('registration --verify (exit %d): %s' % (r.returncode, r.stdout.strip().replace('\n', ' | ')))
    sealed = {}
    for ln in MAN.read_text(encoding='utf-8').splitlines():
        h, p = ln.split('  ', 1)
        sealed[p] = h
    seal = dict(reversed(ln.split('  ', 1)) for ln in SEAL.read_text(encoding='utf-8').splitlines())
    print('seal names manifest', seal.get('outputs/framelease_v4/registration/MANIFEST.sha256', '')[:12],
          '| MANIFEST.sha256 is', sha(MAN)[:12], '| PROTOCOL.md is', sha(ROOT / 'framelease_v4/PROTOCOL.md')[:12],
          '| seal names PROTOCOL', seal.get('framelease_v4/PROTOCOL.md', '')[:12])
    cache = {}
    for name, path in BASELINES.items():
        files = json.loads(path.read_text(encoding='utf-8'))['files']
        tree_diff, man_diff = [], []
        for p, h in files.items():
            q = Path(p) if Path(p).is_absolute() else ROOT / p
            if p not in cache:
                cache[p] = sha(q) if q.is_file() else 'missing'
            if cache[p] != h:
                tree_diff.append(p)
            if sealed.get(p) != h:
                man_diff.append(p)
        print(f'{name} baseline: {len(files)} files; differ from the tree: {tree_diff or "none"}; '
              f'differ from the sealed manifest: {man_diff or "none"}')
    if since:
        t0 = time.mktime(time.strptime(since, '%Y-%m-%d %H:%M'))
        changed = sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'framelease_v4').rglob('*')
                         if p.stat().st_mtime >= t0)
        print(f'framelease_v4 entries changed since {since}:', changed or 'none')
        caches = sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'framelease_v4').rglob('__pycache__')
                        if p.stat().st_mtime >= t0)
        print('new __pycache__ under framelease_v4:', caches or 'none')
    empty = sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'framelease_v4').rglob('*') if p.is_file()
                   and p.stat().st_size == 0)
    print('empty files under framelease_v4:', empty)
    return 0


if __name__ == '__main__':
    sys.exit(main())
