#!/usr/bin/env python3
"""Scratch tree of the G8CUT dry run (outputs/framelease_v4/build/G8CUT/RUNBOOK.md, DRYRUN.md): a copy of the project in
which the registered G8 tools run on SYNTHETIC run directories. Read only on the project; writes only under /tmp/G8CUT/.

  cd /home/kang/Desktop/DAC
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' \
      taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/G8CUT/dryrun/build_tree.py --fresh | --refresh-scripts

Tree /tmp/G8CUT/root is its own root (every registered tool finds the root from its own path). p1_jobs.rel resolves
symbolic links, so every file a tool looks up by its path relative to the root is a REAL copy:
  * the code: framelease_v2/, framelease_v3/, framelease_v4/ (no __pycache__), framelease_common.py;
  * every file of the sealed registration manifest below 50 MB (the 5.9 GB checkpoint stays a link to the file);
  * outputs/framelease_v4: registration/, protocol/, envelopes/, offline_ablation/, p1_jobs/, p2_jobs/, rl_freeze/,
    stress/, test_jobs/, test_freeze/, cut_20261115T231415/, rl_dev/, readiness_fixes/, paper_sources/, the tuning
    freeze (tuning/selection.json, selection/, d1/), rl_data/{data_manifest.json,p2_check.json}, both drivers'
    registered_baseline.json, phase_driver/{P4_QUEUED.json,STOP}; the G8CUT scripts, the stand-in A11 files and the
    appliers (apply_entry_stream.py with ROOT = the tree, the only changed line, and apply_locked.sh), f1_class_report.py.
Everything else of the project root and of outputs/ (outside outputs/framelease_v4) is a read-only link. NOTHING else
of outputs/framelease_v4 is linked or copied: the test-route run directories (matrix, fig3, ablation, replicates), the
queues, the P1 / P1-0 / P2 run directories (tuning/, smoke_p1_0/, rl_data/), analysis/ and verification/ are real
directories of the tree that hold synthetic data only (make_runs.py). The build checks that no link leads into
outputs/framelease_v4 and that the tree's PROTOCOL.md, MANIFEST.sha256 and SEAL.sha256 equal the project's.
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

SRC = Path('/home/kang/Desktop/DAC')
BASE = Path('/tmp/G8CUT')
ROOT = BASE / 'root'
V4 = 'outputs/framelease_v4'
BIG = 50 * 2 ** 20
CODE_TREES = ('framelease_v2', 'framelease_v3', 'framelease_v4', 'framelease_common.py')
V4_TREES = ('registration', 'protocol', 'envelopes', 'offline_ablation', 'p1_jobs', 'p2_jobs', 'rl_freeze', 'stress',
            'test_jobs', 'test_freeze', 'cut_20261115T231415', 'rl_dev', 'readiness_fixes', 'paper_sources',
            'tuning/selection', 'tuning/d1')
V4_FILES = ('p1_driver/registered_baseline.json', 'phase_driver/registered_baseline.json', 'phase_driver/P4_QUEUED.json',
            'phase_driver/STOP', 'tuning/selection.json', 'rl_data/data_manifest.json', 'rl_data/p2_check.json')
G8CUT_FILES = ('g8_lib.py', 'g8_check.sh', 'g8_swap.sh', 'g8_freeze.sh', 'g8_analysis.sh', 'g8_verify.sh',
               'g8_common.sh', 'g8_apply.sh', 'dryrun/A11_standin_entry.md', 'dryrun/A11_standin_spec.json')
SKIP = ('__pycache__', '.git', '.pytest_cache')


def ignore(_d, names):
    return [n for n in names if n in SKIP or n.endswith('.pyc')]


def needed_files():
    """Relative paths that must be real copies (the manifest files under 50 MB outside outputs/framelease_v4)."""
    out = set()
    for ln in (SRC / V4 / 'registration/MANIFEST.sha256').read_text(encoding='utf-8').splitlines():
        rel = ln.split('  ', 1)[1]
        if rel.startswith('/') or rel.startswith(V4 + '/') or rel.split('/')[0] in CODE_TREES:
            continue
        out.add(rel)
    return out


def mirror(rel_dir, needed):
    """Real directory ROOT/rel_dir: an entry that is (an ancestor of) a needed file is copied (a file under 50 MB) or
    recursed into; every other entry is a link to the project's. outputs/framelease_v4 is never linked."""
    src, dst = SRC / rel_dir, ROOT / rel_dir
    dst.mkdir(parents=True, exist_ok=True)
    for e in sorted(src.iterdir()):
        rel = f'{rel_dir}/{e.name}' if rel_dir else e.name
        if e.name in SKIP or rel == V4 or (dst / e.name).exists() or (dst / e.name).is_symlink():
            continue
        if rel in needed:
            if e.stat().st_size < BIG:
                shutil.copy2(e, dst / e.name)
            else:
                os.symlink(e, dst / e.name)
        elif any(n.startswith(rel + '/') for n in needed) and e.is_dir() and not e.is_symlink():
            mirror(rel, needed)
        else:
            os.symlink(e, dst / e.name)


def copy_scripts():
    g8 = SRC / V4 / 'build/G8CUT'
    for n in G8CUT_FILES:
        if (g8 / n).is_file():
            (ROOT / V4 / 'build/G8CUT' / n).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(g8 / n, ROOT / V4 / 'build/G8CUT' / n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fresh', action='store_true', help='remove an earlier tree first')
    ap.add_argument('--refresh-scripts', action='store_true', help='only copy the G8CUT scripts again')
    ap.add_argument('--link-p2-sources', action='store_true',
                    help='link the P2 training run directories that the P2 data manifest names (p3_rl.load_rl_freeze '
                         'hashes their logs when figures_tables.py reads the RL freeze); after the P2 aggregation')
    a = ap.parse_args()
    if a.link_p2_sources:
        man = json.loads((SRC / V4 / 'rl_data/data_manifest.json').read_text(encoding='utf-8'))
        dirs = sorted({a['run_dir'] for e in man['episodes'] for a in e.get('attempts') or [] if a.get('run_dir')}
                      | {r['run_dir'] for r in man.get('excluded_runs') or [] if r.get('run_dir')})
        n = 0
        for rel in dirs:
            if not rel.startswith(f'{V4}/rl_data/') or '/runs/' not in rel + '/':
                sys.exit(f'unexpected source path {rel}')
            (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
            if not (ROOT / rel).exists():
                os.symlink(SRC / rel, ROOT / rel)
                n += 1
        print(f'{n} P2 run directories linked ({len(dirs)} named by the P2 data manifest)')
        return 0
    if a.refresh_scripts:
        copy_scripts()
        print('scripts refreshed')
        return 0
    if ROOT.exists():
        if not a.fresh:
            sys.exit(f'{ROOT} exists (use --fresh)')
        if ROOT.resolve().parent != BASE:
            sys.exit('refusing to remove a tree outside /tmp/G8CUT')
        shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True)
    for n in CODE_TREES:
        if (SRC / n).is_dir():
            shutil.copytree(SRC / n, ROOT / n, ignore=ignore)
        else:
            shutil.copy2(SRC / n, ROOT / n)
    for n in V4_TREES:
        shutil.copytree(SRC / V4 / n, ROOT / V4 / n, ignore=ignore)
    for n in V4_FILES:
        (ROOT / V4 / n).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SRC / V4 / n, ROOT / V4 / n)
    mirror('', needed_files())
    mirror('outputs', needed_files())
    copy_scripts()
    a2 = SRC / V4 / 'build/AMEND2/a10r7b'
    t2 = ROOT / V4 / 'build/AMEND2/a10r7b'
    (t2 / 'f1').mkdir(parents=True, exist_ok=True)
    fsrc = (a2 / 'f1/f1_class_report.py').read_text(encoding='utf-8')     # its root is fixed in the file: the tree's
    fold = "ROOT = '/home/kang/Desktop/DAC'"
    if fsrc.count(fold) != 1:
        sys.exit('f1_class_report.py: the ROOT line is not found once')
    (t2 / 'f1/f1_class_report.py').write_text(fsrc.replace(fold, f"ROOT = '{ROOT}'"), encoding='utf-8')
    src = (a2 / 'apply_entry_stream.py').read_text(encoding='utf-8')
    old = "ROOT = Path('/home/kang/Desktop/DAC')"
    if src.count(old) != 1:
        sys.exit('apply_entry_stream.py: the ROOT line is not found once')
    (t2 / 'apply_entry_stream.py').write_text(src.replace(old, f"ROOT = Path('{ROOT}')"), encoding='utf-8')
    shutil.copy2(a2 / 'apply_locked.sh', t2 / 'apply_locked.sh')
    links = 0
    for p in ROOT.rglob('*'):
        if p.is_symlink():
            links += 1
            t = os.readlink(p)
            if t == str(SRC / V4) or t.startswith(str(SRC / V4) + '/'):
                if not t.endswith('.pt'):
                    sys.exit(f'link into {V4}: {p} -> {t}')
    for rel in ('framelease_v4/PROTOCOL.md', f'{V4}/registration/MANIFEST.sha256', f'{V4}/registration/SEAL.sha256'):
        if (ROOT / rel).read_bytes() != (SRC / rel).read_bytes():
            sys.exit(f'{rel} differs from the project')
    print(f'tree {ROOT}: {links} links; registered inputs, code and the G8CUT scripts copied')
    return 0


if __name__ == '__main__':
    sys.exit(main())
