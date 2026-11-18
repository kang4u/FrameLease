#!/usr/bin/env python3
"""Scratch tree of the G8FULL dry run (outputs/framelease_v4/build/G8FULL/RUNBOOK.md, DRYRUN.md): a copy of the project
in which the registered tools and the G8FULL scripts run on SYNTHETIC run directories, with the first (cut) analysis
freeze of Amendment A13 already entered. Read only on the project; writes only under /tmp/G8FULL/. Adapted from
outputs/framelease_v4/build/G8CUT/dryrun/build_tree.py (unchanged there).

  cd /home/kang/Desktop/DAC
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' \
      taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/G8FULL/dryrun/build_tree.py --fresh | --refresh-scripts | --link-p2-sources

Tree /tmp/G8FULL/root is its own root. Real copies (p1_jobs.rel resolves symbolic links):
  * the code: framelease_v2/, framelease_v3/, framelease_v4/ (no __pycache__), framelease_common.py; PROTOCOL.md is the
    project's, with Amendments A13-A17, and MANIFEST.sha256 / SEAL.sha256 equal the project's;
  * every file of the sealed registration manifest below 50 MB (the 5.9 GB checkpoint stays a link to the file);
  * outputs/framelease_v4: registration/, protocol/, envelopes/, offline_ablation/, p1_jobs/, p2_jobs/, rl_freeze/,
    stress/, test_jobs/, test_freeze/, cut_20261115T231415/, rl_dev/, readiness_fixes/, paper_sources/, the tuning
    freeze, rl_data/{data_manifest.json,p2_check.json}, both drivers' registered_baseline.json,
    phase_driver/{P4_QUEUED.json,STOP};
  * the first analysis freeze, job status only: the six top-level files of analysis/final_20261116T091445/ that the
    record and its SHA256SUMS name (analysis_freeze.json, required_job_files.json, SHA256SUMS and the health-only
    aggregation runs.csv / aggregate.json it lists, the guard log interim_guard.jsonl). Every test-route row of that
    aggregation is health-only (Sec. 9.11; Amendment A13): no outcome metric. The analysis subdirectories of the first
    freeze and verification/ are NOT copied: the dry run makes synthetic stand-ins with the G8CUT tools;
  * the G8CUT scripts (imported by g8f_lib.py; their g8_analysis.sh makes the stand-in first analysis) and the G8FULL
    scripts; the appliers (apply_entry_stream.py with ROOT = the tree, the only changed line; apply_locked.sh) and
    f1_class_report.py with its ROOT line set to the tree (g8f_lib.py compares its sha256 with the ROOT line restored).
Everything else of the project root and of outputs/ (outside outputs/framelease_v4) is a read-only link. No link leads
into outputs/framelease_v4: the queues, the test-route run directories (matrix, fig3, ablation, replicates), the
P1 / P1-0 / P2 run directories, analysis/ (beyond the copies above) and verification/ hold synthetic data only
(make_runs.py).
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

SRC = Path('/home/kang/Desktop/DAC')
BASE = Path('/tmp/G8FULL')
ROOT = BASE / 'root'
V4 = 'outputs/framelease_v4'
BIG = 50 * 2 ** 20
CODE_TREES = ('framelease_v2', 'framelease_v3', 'framelease_v4', 'framelease_common.py')
V4_TREES = ('registration', 'protocol', 'envelopes', 'offline_ablation', 'p1_jobs', 'p2_jobs', 'rl_freeze', 'stress',
            'test_jobs', 'test_freeze', 'cut_20261115T231415', 'rl_dev', 'readiness_fixes', 'paper_sources',
            'tuning/selection', 'tuning/d1')
V4_FILES = ('p1_driver/registered_baseline.json', 'phase_driver/registered_baseline.json',
            'phase_driver/P4_QUEUED.json', 'phase_driver/STOP', 'tuning/selection.json', 'rl_data/data_manifest.json',
            'rl_data/p2_check.json')
FIRST = f'{V4}/analysis/final_20261116T091445'
FIRST_FILES = ('analysis_freeze.json', 'required_job_files.json', 'SHA256SUMS', 'runs.csv', 'aggregate.json',
               'interim_guard.jsonl')
G8CUT_FILES = ('g8_lib.py', 'g8_check.sh', 'g8_swap.sh', 'g8_freeze.sh', 'g8_analysis.sh', 'g8_verify.sh',
               'g8_common.sh', 'g8_apply.sh')
G8FULL_FILES = ('g8f_lib.py', 'g8f_common.sh', 'g8f_check.sh', 'g8f_stop.sh', 'g8f_freeze.sh', 'g8f_apply.sh',
                'g8f_analysis.sh', 'g8f_verify.sh', 'g8f_figs.sh', 'fig3/make_fig3_panels_full.py',
                'fig3/make_fig3ab_table1_full.py')
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
    for here, names in (('G8CUT', G8CUT_FILES), ('G8FULL', G8FULL_FILES)):
        src = SRC / V4 / 'build' / here
        for n in names:
            if (src / n).is_file():
                (ROOT / V4 / 'build' / here / n).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src / n, ROOT / V4 / 'build' / here / n)


def link_p2_sources():
    man = json.loads((SRC / V4 / 'rl_data/data_manifest.json').read_text(encoding='utf-8'))
    dirs = sorted({a['run_dir'] for e in man['episodes'] for a in e.get('attempts') or [] if a.get('run_dir')}
                  | {r['run_dir'] for r in man.get('excluded_runs') or [] if r.get('run_dir')})
    n = 0
    for rel in dirs:
        if not rel.startswith(f'{V4}/rl_data/') or '/runs/' not in rel + '/':
            sys.exit(f'unexpected source path {rel}')
        (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
        if not (ROOT / rel).exists() and not (ROOT / rel).is_symlink():
            os.symlink(SRC / rel, ROOT / rel)
            n += 1
    print(f'{n} P2 run directories linked ({len(dirs)} named by the P2 data manifest; training routes, read by '
          'p3_rl.load_rl_freeze for their sha256 only)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fresh', action='store_true', help='remove an earlier tree first')
    ap.add_argument('--refresh-scripts', action='store_true', help='only copy the G8CUT and G8FULL scripts again')
    ap.add_argument('--link-p2-sources', action='store_true',
                    help='link the P2 training run directories that the P2 data manifest names (p3_rl.load_rl_freeze '
                         'hashes their logs when figures_tables.py reads the RL freeze); after the P2 aggregation')
    a = ap.parse_args()
    if a.link_p2_sources:
        link_p2_sources()
        return 0
    if a.refresh_scripts:
        copy_scripts()
        print('scripts refreshed')
        return 0
    if ROOT.exists():
        if not a.fresh:
            sys.exit(f'{ROOT} exists (use --fresh)')
        if ROOT.resolve().parent != BASE:
            sys.exit('refusing to remove a tree outside /tmp/G8FULL')
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
    (ROOT / FIRST).mkdir(parents=True)
    for n in FIRST_FILES:
        shutil.copy2(SRC / FIRST / n, ROOT / FIRST / n)
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
            if (t == str(SRC / V4) or t.startswith(str(SRC / V4) + '/')) and not t.endswith('.pt'):
                sys.exit(f'link into {V4}: {p} -> {t}')
    for rel in ('framelease_v4/PROTOCOL.md', f'{V4}/registration/MANIFEST.sha256', f'{V4}/registration/SEAL.sha256',
                *(f'{FIRST}/{n}' for n in FIRST_FILES)):
        if (ROOT / rel).read_bytes() != (SRC / rel).read_bytes():
            sys.exit(f'{rel} differs from the project')
    print(f'tree {ROOT}: {links} links; registered inputs, code, the first freeze record (job status only) and the '
          'G8CUT / G8FULL scripts copied')
    return 0


if __name__ == '__main__':
    sys.exit(main())
