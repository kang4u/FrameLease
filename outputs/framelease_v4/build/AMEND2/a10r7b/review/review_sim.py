"""Independent dry run of Amendments A10 and A11 (reviewer of item a10r7b; read only on the project).

  cd /home/kang/Desktop/DAC
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' \
      taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/a10r7b/review/review_sim.py CASE [CASE ...]

Every scratch tree lies under /tmp/AMEND3_review/a10r7b/ (anything else is refused). A tree holds real copies of
framelease_v4/ (no __pycache__), of outputs/framelease_v4/{registration,p1_driver,amendment_a10,amendment_a11}/, of
phase_driver/registered_baseline.json (only that file), of build/AMEND2/ (no step3/) and a real build/R7B/ whose entries
link to the project's; every other entry of the project root, outputs/, outputs/framelease_v4/ and build/ is a symbolic
link (read only), except the runners' queues, tuning/, analysis/, pipeline_state.json and phase_driver/ (never linked).
The test tree ('tests' case) instead copies every outputs/framelease_v4 directory a test reads or tries to write
(envelopes, offline_ablation, protocol, smoke_p1_0, build/R5/dev_run, build/STRESS) and links nothing else below
outputs/framelease_v4/. Before a tree is used, every path a run writes is checked to resolve inside it.

The applier is the builder's apply_entry_stream.py with only its ROOT line set to the tree (checked); the wrapper is the
builder's apply_locked.sh with APPLY_ROOT / APPLIER (its scratch-tree hooks). inject.py (written into the work
directory) runs the applier in-process with subprocess.run patched for the fault cases.

Cases: tests, A (normal order), B (A11 first), C (an "old" in-place text twice), D (a changed registered file before
the transaction), E (a registered file changed between the manifest and the seal), F (a crash after PROTOCOL.md is
written and before the seal; a truncated PROTOCOL.md), G (TZ=UTC), H (a line of the template read as a driver entry),
W (widths and line patterns of every added line; in-place overlap). Results: summary_<case>.json in the work
directory and the review directory's logs/.
"""
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path('/home/kang/Desktop/DAC')
BASE = Path('/tmp/AMEND3_review/a10r7b')
WORK = BASE / 'work'
REVIEW = SRC / 'outputs/framelease_v4/build/AMEND2/a10r7b/review'
LOGS = REVIEW / 'logs'
BUILDER = SRC / 'outputs/framelease_v4/build/AMEND2/a10r7b'
PY = str(SRC / '.conda-unidrive-linux/bin/python')
A10_SPEC = 'outputs/framelease_v4/build/AMEND2/final/A10_spec.json'
A11_SPEC = 'outputs/framelease_v4/build/AMEND2/a10r7b/A11_spec.json'
A11_TEMPLATE = 'outputs/framelease_v4/build/AMEND2/a10r7b/A11_entry.md'
REREVIEW = 'outputs/framelease_v4/build/R7B/rereview/REVIEW.md'
REG = 'outputs/framelease_v4/registration'
PHASE_BASELINE = 'outputs/framelease_v4/phase_driver/registered_baseline.json'
P1_BASELINE = 'outputs/framelease_v4/p1_driver/registered_baseline.json'
A10_FILES = ('framelease_v4/analysis/analyze_v4.py', 'framelease_v4/analysis/prop1_coverage.py',
             'framelease_v4/analysis/figures_tables.py', 'framelease_v4/analysis/verify_independent.py',
             'framelease_v4/analysis/tests/test_analyze_v4.py', 'framelease_v4/analysis/tests/test_prop1_coverage.py',
             'framelease_v4/analysis/tests/test_figures_tables.py',
             'framelease_v4/analysis/tests/test_verify_independent.py')
A11_FILES = ('framelease_v4/analysis/verify_table1_extra.py',
             'framelease_v4/analysis/tests/test_verify_table1_extra.py')
ENV = {**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
       'OPENBLAS_NUM_THREADS': '1'}
GATE_LINE = ('* **G3 P2 data manifest** (2026-11-15 23:00, Beijing time). Simulated later gate entry; manifest and '
             'seal: `MANIFEST.sha256`, 999 files, sha256 `' + 'e' * 64 + '`, sealed with this entry.')

sys.path.insert(0, str(SRC))
sys.dont_write_bytecode = True
from framelease_v4.protocol import p1_driver as P1  # noqa: E402
from framelease_v4.protocol import phase_driver as PD  # noqa: E402

INJECT = r'''"""Run the applier in-process with subprocess.run patched (review fault injection; scratch trees only).
Environment: INJECT_APPLIER (the scratch applier), INJECT_MODE (touch_after_manifest | kill_before_seal),
INJECT_TARGET (file appended to after --write-manifest)."""
import os
import runpy
import subprocess
import sys
applier, mode, target = os.environ['INJECT_APPLIER'], os.environ['INJECT_MODE'], os.environ.get('INJECT_TARGET', '')
if not applier.startswith('/tmp/AMEND3_review/a10r7b/') or (target and not target.startswith('/tmp/AMEND3_review/')):
    raise SystemExit('inject: refused outside the scratch trees')
real_run = subprocess.run


def patched(cmd, *a, **k):
    if mode == 'kill_before_seal' and '--seal' in cmd:
        sys.stdout.flush()
        os._exit(137)
    r = real_run(cmd, *a, **k)
    if mode == 'touch_after_manifest' and '--write-manifest' in cmd:
        with open(target, 'a', encoding='utf-8') as fh:
            fh.write('# review probe: changed between the manifest and the seal\n')
        print('inject: appended a line to', target, flush=True)
    return r


subprocess.run = patched
sys.argv = [applier] + sys.argv[1:]
runpy.run_path(applier, run_name='__main__')
'''


# ------------------------------------------------------------------------------------------------------ utilities

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def inside(p):
    return str(Path(p).resolve()).startswith(str(BASE) + '/')


def rsync(src, dst, *excl):
    if not inside(dst.parent):
        raise SystemExit(f'SAFETY STOP: rsync target {dst} outside {BASE}')
    subprocess.run(['rsync', '-a'] + [f'--exclude={e}' for e in excl] + [f'{src}/', f'{dst}/'], check=True)


def run(cmd, cwd, env=None, log=None):
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, env=env or ENV)
    if log is not None:
        Path(log).write_text(f'$ {" ".join(map(str, cmd))}\n(exit {r.returncode})\n{r.stdout}{r.stderr}',
                             encoding='utf-8')
    return r


def verify(tree, log=None):
    r = run([PY, '-I', '-B', tree / 'framelease_v4/protocol/registration.py', '--verify'], tree, log=log)
    out = r.stdout
    return {'manifest_ok': 'manifest: OK' in out, 'seal_lines': re.findall(r'^seal (.+): (OK|CHANGED)$', out, re.M),
            'all_ok': r.returncode == 0 and 'manifest: OK' in out and out.count(': OK') == 3,
            'text': out.strip().replace('\n', ' | ')[:600]}


def manifest(tree):
    out = {}
    for ln in (tree / REG / 'MANIFEST.sha256').read_text(encoding='utf-8').splitlines():
        h, p = ln.split('  ', 1)
        out[p] = h
    return out


# --------------------------------------------------------------------------------------------------------- trees

NEVER = ('pipeline_state.json', 'phase_driver', 'tuning', 'analysis')
COPY_V4 = ('registration', 'p1_driver', 'amendment_a10', 'amendment_a11')
TEST_COPY_V4 = ('envelopes', 'offline_ablation', 'protocol', 'smoke_p1_0')


def build_tree(dst, test_tree=False):
    if not str(dst).startswith(str(BASE) + '/'):
        raise SystemExit(f'SAFETY STOP: {dst} is not under {BASE}')
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for e in SRC.iterdir():
        if e.name in ('framelease_v4', 'outputs'):
            continue
        if test_tree and e.name in ('framelease_v2', 'framelease_v3'):
            rsync(e, dst / e.name, '__pycache__')     # their modules put their own (resolved) root on sys.path
        elif test_tree and e.suffix == '.py' and e.is_file() and not e.is_symlink():
            shutil.copy2(e, dst / e.name)
        else:
            (dst / e.name).symlink_to(e)
    rsync(SRC / 'framelease_v4', dst / 'framelease_v4', '__pycache__')
    (dst / 'outputs/framelease_v4').mkdir(parents=True)
    for e in (SRC / 'outputs').iterdir():
        if e.name != 'framelease_v4':
            (dst / 'outputs' / e.name).symlink_to(e)
    v4 = SRC / 'outputs/framelease_v4'
    for e in v4.iterdir():
        if e.name.startswith('queue_') or e.name in NEVER or e.name == 'build':
            continue
        if e.name in COPY_V4 or (test_tree and e.name in TEST_COPY_V4):
            rsync(e, dst / 'outputs/framelease_v4' / e.name)
        elif not test_tree:
            (dst / 'outputs/framelease_v4' / e.name).symlink_to(e)
    (dst / 'outputs/framelease_v4/phase_driver').mkdir()
    shutil.copy2(SRC / PHASE_BASELINE, dst / PHASE_BASELINE)
    b = dst / 'outputs/framelease_v4/build'
    b.mkdir()
    if test_tree:
        (b / 'R5').mkdir()
        rsync(v4 / 'build/R5/dev_run', b / 'R5/dev_run')
        rsync(v4 / 'build/STRESS', b / 'STRESS')
        (b / 'R7B').symlink_to(v4 / 'build/R7B')      # the review tests name the project paths themselves
    else:
        for e in (v4 / 'build').iterdir():
            if e.name == 'AMEND2':
                rsync(e, b / 'AMEND2', '/step3')
            elif e.name == 'R7B':
                (b / 'R7B').mkdir()
                for f in e.iterdir():
                    (b / 'R7B' / f.name).symlink_to(f)
            else:
                (b / e.name).symlink_to(e)
    shutil.copy2(SRC / 'framelease_v4/PROTOCOL.md', dst / 'framelease_v4/PROTOCOL.md')
    rsync(v4 / 'registration', dst / REG)
    safety(dst, test_tree)


def safety(dst, test_tree=False):
    rels = ['framelease_v4', 'framelease_v4/PROTOCOL.md', 'framelease_v4/.protocol.lock', REG,
            f'{REG}/MANIFEST.sha256', f'{REG}/SEAL.sha256', f'{REG}/REGISTRATION.json',
            'outputs/framelease_v4/p1_driver', 'outputs/framelease_v4/phase_driver', PHASE_BASELINE,
            'outputs/framelease_v4/amendment_a10', 'outputs/framelease_v4/amendment_a11']
    rels += (['outputs/framelease_v4/envelopes', 'outputs/framelease_v4/offline_ablation',
              'outputs/framelease_v4/protocol', 'outputs/framelease_v4/smoke_p1_0'] if test_tree else
             ['outputs/framelease_v4/build/AMEND2', 'outputs/framelease_v4/build/R7B'])
    for rel in rels:
        p = dst / rel
        if p.is_symlink() or not str(p.resolve()).startswith(str(dst.resolve()) + '/'):
            raise SystemExit(f'SAFETY STOP: {p} does not resolve inside the scratch tree')
    for rel in ('outputs/framelease_v4/tuning', 'outputs/framelease_v4/analysis', 'outputs/framelease_v4/queue_p1',
                'outputs/framelease_v4/queue_p2'):
        if (dst / rel).exists() or (dst / rel).is_symlink():
            raise SystemExit(f'SAFETY STOP: {rel} exists in the scratch tree')


def applier(tree, name='apply_entry_scratch.py'):
    src = (BUILDER / 'apply_entry_stream.py').read_text(encoding='utf-8')
    old = "ROOT = Path('/home/kang/Desktop/DAC')\n"
    if src.count(old) != 1:
        raise SystemExit('SAFETY STOP: the ROOT line of the applier is not unique')
    new = src.replace(old, f"ROOT = Path('{tree}')\n")
    diff = [(a, b) for a, b in zip(src.splitlines(), new.splitlines()) if a != b]
    if len(diff) != 1 or len(src.splitlines()) != len(new.splitlines()):
        raise SystemExit('SAFETY STOP: the applier copy differs in more than its ROOT line')
    p = WORK / f'{tree.name}_{name}'
    p.write_text(new, encoding='utf-8')
    return p


def wrapper(tree, spec, out_rel, app, env_extra=None):
    """The builder's apply_locked.sh on the tree (APPLY_ROOT / APPLIER); returns (rc, stdout, apply.out)."""
    env = {**ENV, 'APPLY_ROOT': str(tree), 'APPLIER': str(app), **(env_extra or {})}
    r = subprocess.run(['bash', str(BUILDER / 'apply_locked.sh'), spec, str(tree / out_rel)], cwd=tree,
                       capture_output=True, text=True, env=env)
    out = (tree / out_rel / 'apply.out')
    return r.returncode, r.stdout + r.stderr, out.read_text(encoding='utf-8') if out.is_file() else ''


def standin_review(tree):
    p = tree / REREVIEW
    if (SRC / REREVIEW).exists():
        return 'real review present (linked)'
    p.parent.mkdir()
    if not inside(p.parent):
        raise SystemExit('SAFETY STOP: stand-in outside the tree')
    p.write_text('# Scratch-tree stand-in for the review of the R7B fixes (reviewer dry run)\n\n**Verdict: GO.**\n',
                 encoding='utf-8')
    return 'stand-in written in the tree'


# ------------------------------------------------------------------------------------------------------- parsing

def views(text):
    return P1.protocol_view(None, text), PD.phase_view(None, text)


class FakeCfg:
    def __init__(self, tree):
        self.tree = tree
        self.analyze_code = tree / 'framelease_v4/analysis/analyze_v4.py'
        self.baseline_path = tree / PHASE_BASELINE
        self.p1_baseline = tree / P1_BASELINE
        self.driver_dir = tree / 'outputs/framelease_v4/phase_driver'
        self.dry_run = True

    def rel(self, p):
        return str(Path(p).relative_to(self.tree))


class FakeCtx:
    def __init__(self):
        self.notes = []

    def add_attention(self, msg):
        self.notes.append(('attention', msg))

    def log(self, msg):
        self.notes.append(('log', msg))


def refresh(tree, write=False):
    """phase_driver.refresh_baseline on the tree's seal (dry run): (files, newly registered, changed sha256)."""
    text = (tree / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    seal = dict((ln.split('  ', 1)[1], ln.split('  ', 1)[0]) for ln in
                (tree / REG / 'SEAL.sha256').read_text(encoding='utf-8').splitlines())
    reg = {'seal_protocol': seal['framelease_v4/PROTOCOL.md'], 'seal_manifest': seal[f'{REG}/MANIFEST.sha256']}
    sealed_text = (tree / REG / 'MANIFEST.sha256').read_text(encoding='utf-8')
    old = json.loads((tree / PHASE_BASELINE).read_text(encoding='utf-8'))
    cfg, ctx = FakeCfg(tree), FakeCtx()
    files = PD.refresh_baseline(cfg, ctx, PD.phase_view(None, text), reg, sealed_text)
    added = sorted(p for p in files if p not in old['files'])
    changed = sorted(p for p in files if p in old['files'] and old['files'][p] != files[p])
    if write:
        doc = {**old, 'files': files, 'manifest_sha256': reg['seal_manifest'], 'protocol_sha256': reg['seal_protocol'],
               'how': 'reviewer dry run: refresh_baseline result written into the scratch tree'}
        (tree / PHASE_BASELINE).write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return files, added, changed


def parse_report(tree, before_text):
    text = (tree / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    out = {'problems': []}
    try:
        pv0, ph0 = views(before_text)
        pv, ph = views(text)
    except Exception as exc:                                         # an ALERT of a parser
        out['problems'].append(f'parser: {type(exc).__name__}: {exc}')
        return out
    if {k: v['text'] for k, v in pv['entries'].items()} != {k: v['text'] for k, v in pv0['entries'].items()}:
        out['problems'].append('P1 entries changed')
    if {k: v['text'] for k, v in ph['entries'].items()} != {k: v['text'] for k, v in ph0['entries'].items()}:
        out['problems'].append('phase entries changed')
    out['amendments'] = {k: v for k, v in ph['amendments'].items() if k in ('A3', 'A4', 'A7', 'A9', 'A10', 'A11')}
    s, e = ph['sec']
    owners = {}
    for p in A10_FILES + A11_FILES:
        h = sha(tree / p)
        line = next((i + 1 for i in range(s, e) if h in ph['lines'][i]), None)
        owners[p] = PD.citing_amendment(ph, line) if line else None
    out['first_citing_owner'] = owners
    out['G8_waits'] = PD.analysis_registration(FakeCfg(tree), ph)[0]
    later = PD.insert_entry(None, text, [GATE_LINE])
    _, phl = views(later)
    g3 = phl['entries'].get('p2_data')
    a10 = phl['amendments'].get('A10', [None])[0]
    out['later_gate'] = {'read': g3 is not None, 'line': g3 and g3['line'], 'A10_title_line': a10,
                         'others_unchanged': {k: v['text'] for k, v in phl['entries'].items() if k != 'p2_data'}
                         == {k: v['text'] for k, v in ph['entries'].items()}}
    return out


ENTRY_LIKE = (P1.ENTRY_RE, PD.ENTRY_RE)


def added_lines(before, after):
    sm = difflib.SequenceMatcher(None, before.split('\n'), after.split('\n'), autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ('replace', 'insert'):
            out += [(j + 1, after.split('\n')[j]) for j in range(j1, j2)]
    return out


def line_report(lines):
    """Widths and line patterns of added lines: (prose lines > 120, table rows > 120, pattern problems)."""
    over, table_over, bad = [], [], []
    for n, ln in lines:
        if len(ln) > 120:
            (table_over if ln.lstrip().startswith('|') else over).append((n, len(ln)))
        if any(r.match(ln) for r in ENTRY_LIKE):
            bad.append((n, 'driver entry', ln[:80]))
        if PD.AMEND_RE.match(ln) and not ln.startswith(('**Amendment A10,', '**Amendment A11,')):
            bad.append((n, 'amendment title', ln[:80]))
        if ln.startswith('## ') or ln.startswith(P1.ANCHOR) or ln.strip() in (P1.HEADING, PD.HEADING):
            bad.append((n, 'heading / anchor', ln[:80]))
        if P1.LIST_START.match(ln) and not ln.startswith(('* ', '|')):
            bad.append((n, 'column-0 list or quote start', ln[:80]))
    return over, table_over, bad


# --------------------------------------------------------------------------------------------------------- cases

def case_tests():
    """A10 and A11 tests on a test tree through the scratch applier's --tests mode (logs in the tree)."""
    t = BASE / 'ttree'
    build_tree(t, test_tree=True)
    app = applier(t)
    res = {}
    for spec in (A10_SPEC, A11_SPEC):
        shutil.copy2(SRC / spec, WORK / Path(spec).name)
        r = run([PY, '-I', '-B', app, WORK / Path(spec).name, '--tests'], t, log=LOGS / f'tests_{Path(spec).stem}.out')
        res[spec] = r.stdout.strip().splitlines()
    for d in ('amendment_a10', 'amendment_a11'):
        for f in sorted((t / 'outputs/framelease_v4' / d).glob('pytest_*.log')):
            shutil.copy2(f, LOGS / f'ttree_{d}_{f.name}')
    created = [str(p.relative_to(t)) for p in (t / 'outputs/framelease_v4').iterdir()
               if p.name in ('tuning', 'analysis') or p.name.startswith('queue_')]
    res['protected_paths_created_in_tree'] = created
    res['pycache_in_tree'] = [str(p.relative_to(t)) for p in (t / 'framelease_v4').rglob('__pycache__')]
    return res


def case_A():
    t = BASE / 'treeA'
    build_tree(t)
    app = applier(t)
    res = {'verify0': verify(t)}
    before = (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    r = run([PY, '-I', '-B', app, A10_SPEC], t, log=LOGS / 'A1_a10_check.log')
    res['A10_check'] = r.stdout.strip().splitlines()[-1:]
    rc, so, ao = wrapper(t, A10_SPEC, 'outputs/framelease_v4/amendment_a10', app)
    (LOGS / 'A2_a10_apply.out').write_text(so + ao, encoding='utf-8')
    res['A10_apply_rc'] = rc
    res['A10_newly'] = [ln for ln in ao.splitlines() if 'newly cited' in ln]
    res['verify_after_A10'] = verify(t, LOGS / 'A3_verify.log')
    after_a10 = (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    res['parse_after_A10'] = parse_report(t, before)
    files, added, changed = refresh(t, write=True)
    res['refresh_after_A10'] = {'files': len(files), 'added': added, 'changed': changed}
    res['lines_A10'] = line_report(added_lines(before, after_a10))
    res['standin'] = standin_review(t)
    r = run([PY, '-I', '-B', app, A11_SPEC], t, log=LOGS / 'A5_a11_check.log')
    res['A11_check'] = r.stdout.strip().splitlines()[-1:]
    rc, so, ao = wrapper(t, A11_SPEC, 'outputs/framelease_v4/amendment_a11', app)
    (LOGS / 'A6_a11_apply.out').write_text(so + ao, encoding='utf-8')
    res['A11_apply_rc'] = rc
    res['A11_newly'] = [ln for ln in ao.splitlines() if 'newly cited' in ln]
    res['verify_after_A11'] = verify(t, LOGS / 'A7_verify.log')
    after_a11 = (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    res['parse_after_A11'] = parse_report(t, after_a10)
    files, added, changed = refresh(t, write=True)
    res['refresh_after_A11'] = {'files': len(files), 'added': added, 'changed': changed}
    res['lines_A11'] = line_report(added_lines(after_a10, after_a11))
    shutil.copy2(t / 'framelease_v4/PROTOCOL.md', LOGS / 'PROTOCOL.after_A10_A11.review_sim.md.txt')
    for name in ('A10', 'A11'):
        r = run([PY, '-I', '-B', BUILDER / 'post_check.py', name, '--root', t], SRC, log=LOGS / f'A8_post_{name}.log')
        res[f'post_check_{name}'] = (r.returncode, r.stdout.strip().splitlines()[-1:])
    return res


def case_B():
    t = BASE / 'treeB'
    build_tree(t)
    app = applier(t)
    h0 = sha(t / 'framelease_v4/PROTOCOL.md'), sha(t / REG / 'MANIFEST.sha256')
    rc, so, ao = wrapper(t, A11_SPEC, 'outputs/framelease_v4/amendment_a11', app)
    (LOGS / 'B_a11_first.out').write_text(so + ao, encoding='utf-8')
    return {'rc': rc, 'stop': [ln for ln in ao.splitlines() if ln.startswith('STOP')],
            'unchanged': h0 == (sha(t / 'framelease_v4/PROTOCOL.md'), sha(t / REG / 'MANIFEST.sha256')),
            'verify': verify(t)}


def reseal(t, log):
    """Seal the tree's (edited) PROTOCOL.md with its manifest (scratch only)."""
    return run([PY, '-I', '-B', t / 'framelease_v4/protocol/registration.py', '--seal'], t, log=log)


def case_C():
    res = {}
    spec = json.loads((SRC / A10_SPEC).read_text(encoding='utf-8'))
    # (a) overlap of the in-place texts within one spec (apply_entry.py replaces them one after the other)
    text = (SRC / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    over = []
    for i, ri in enumerate(spec['inplace']):
        for j, rj in enumerate(spec['inplace']):
            if i != j and (rj['old'] in ri['new'] or rj['old'] in ri['old']):
                over.append((i + 1, j + 1))
    spans = sorted((text.index(r['old']), text.index(r['old']) + len(r['old']), k + 1)
                   for k, r in enumerate(spec['inplace']))
    res['A10_inplace_overlap'] = over + [(a[2], b[2]) for a, b in zip(spans, spans[1:]) if b[0] < a[1]]
    # (b) the Sec. 4.1 status paragraph twice in a sealed PROTOCOL.md
    t = BASE / 'treeC'
    build_tree(t)
    app = applier(t)
    p = t / 'framelease_v4/PROTOCOL.md'
    old5 = spec['inplace'][4]['old']
    txt = p.read_text(encoding='utf-8')
    k = txt.index('### 4.2 ')
    p.write_text(txt[:k] + old5 + '\n' + txt[k:], encoding='utf-8')
    reseal(t, LOGS / 'C_reseal.log')
    h0 = sha(p), sha(t / REG / 'MANIFEST.sha256')
    rc, so, ao = wrapper(t, A10_SPEC, 'outputs/framelease_v4/amendment_a10', app)
    (LOGS / 'C_old_twice.out').write_text(so + ao, encoding='utf-8')
    res['old_twice'] = {'rc': rc, 'stop': [ln for ln in ao.splitlines() if ln.startswith('STOP')],
                        'unchanged': h0 == (sha(p), sha(t / REG / 'MANIFEST.sha256')), 'verify': verify(t)}
    # (c) derive_inplace5.py on that copy
    r = run([PY, '-I', '-B', BUILDER / 'derive_inplace5.py', '--protocol', p], SRC, log=LOGS / 'C_derive.log')
    res['derive_on_doubled'] = (r.returncode, r.stdout.strip().splitlines()[-1:])
    return res


def case_D():
    res = {}
    # (a) a file registered by A3 (phase driver baseline, not in the P1 driver baseline) changed before the apply
    t = BASE / 'treeD'
    build_tree(t)
    app = applier(t)
    p1b = json.loads((t / P1_BASELINE).read_text(encoding='utf-8'))['files']
    phb = json.loads((t / PHASE_BASELINE).read_text(encoding='utf-8'))['files']
    target = 'framelease_v4/analysis/commit_audit.py'
    res['target_in_p1_baseline'], res['target_in_phase_baseline'] = target in p1b, target in phb
    res['phase_only_registered_files'] = len([k for k in phb if k not in p1b])
    with open(t / target, 'a', encoding='utf-8') as fh:
        fh.write('# review probe: a registered file changed outside a transaction\n')
    new_sha = sha(t / target)
    res['verify_before'] = verify(t)
    r = run([PY, '-I', '-B', app, A10_SPEC], t, log=LOGS / 'D_check.log')
    res['check'] = r.stdout.strip().splitlines()[-1:]
    rc, so, ao = wrapper(t, A10_SPEC, 'outputs/framelease_v4/amendment_a10', app)
    (LOGS / 'D_changed_registered.out').write_text(so + ao, encoding='utf-8')
    res['apply_rc'] = rc
    res['verify_after'] = verify(t)
    res['sealed_manifest_has_new_sha'] = manifest(t).get(target) == new_sha
    files, added, changed = refresh(t)
    res['phase_refresh'] = {'added': added, 'changed_sha256_adopted': changed}
    # (b) control: a file of the P1 driver baseline changed before the apply
    t2 = BASE / 'treeD2'
    build_tree(t2)
    app2 = applier(t2)
    target2 = 'framelease_v4/arms/realized.py'
    with open(t2 / target2, 'a', encoding='utf-8') as fh:
        fh.write('# review probe\n')
    h0 = sha(t2 / 'framelease_v4/PROTOCOL.md'), sha(t2 / REG / 'MANIFEST.sha256')
    rc, so, ao = wrapper(t2, A10_SPEC, 'outputs/framelease_v4/amendment_a10', app2)
    (LOGS / 'D2_changed_p1_registered.out').write_text(so + ao, encoding='utf-8')
    res['control_p1_file'] = {'rc': rc, 'stop': [ln for ln in ao.splitlines() if ln.startswith('STOP')][:1],
                              'unchanged': h0 == (sha(t2 / 'framelease_v4/PROTOCOL.md'),
                                                  sha(t2 / REG / 'MANIFEST.sha256'))}
    return res


def write_inject():
    p = WORK / 'inject.py'
    p.write_text(INJECT, encoding='utf-8')
    return p


def case_E():
    res = {}
    inj = write_inject()
    for label, target in (('phase_only', 'framelease_v4/analysis/manipulation.py'),
                          ('p1_baseline', 'framelease_v4/arms/realized.py')):
        t = BASE / f'treeE_{label}'
        build_tree(t)
        app = applier(t)
        env = {'INJECT_APPLIER': str(app), 'INJECT_MODE': 'touch_after_manifest', 'INJECT_TARGET': str(t / target)}
        rc, so, ao = wrapper(t, A10_SPEC, 'outputs/framelease_v4/amendment_a10', inj, env)
        (LOGS / f'E_{label}.out').write_text(so + ao, encoding='utf-8')
        res[label] = {'rc': rc, 'wrapper_line': so.strip().splitlines()[-1:], 'final_verify_in_apply_out':
                      [ln for ln in ao.splitlines() if ln.startswith(('manifest:', 'seal '))][-3:],
                      'sealed': 'registration --seal -> 0' in ao, 'verify_now': verify(t)}
        r = run([PY, '-I', '-B', BUILDER / 'post_check.py', 'A10', '--root', t], SRC, log=LOGS / f'E_{label}_post.log')
        res[label]['post_check'] = (r.returncode, r.stdout.strip().splitlines()[-1:])
    return res


def case_F():
    res = {}
    inj = write_inject()
    # F1: killed right before the seal, nothing of the manifest scope changed
    for label, probe in (('F1_no_scope_change', False), ('F2_scope_change', True)):
        t = BASE / f'tree{label[:2]}'
        build_tree(t)
        app = applier(t)
        if probe:
            (t / 'framelease_v4/zz_review_probe.txt').write_text('review probe: a new file in the manifest scope\n',
                                                                  encoding='utf-8')
        pro0, man0 = sha(t / 'framelease_v4/PROTOCOL.md'), sha(t / REG / 'MANIFEST.sha256')
        env = {'INJECT_APPLIER': str(app), 'INJECT_MODE': 'kill_before_seal'}
        rc, so, ao = wrapper(t, A10_SPEC, 'outputs/framelease_v4/amendment_a10', inj, env)
        (LOGS / f'{label}.out').write_text(so + ao, encoding='utf-8')
        text = (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
        a10 = text.find('**Amendment A10,')
        m = re.compile(r'Manifest and seal after this amendment: `MANIFEST\.sha256`, (\d+) files, sha256\s+'
                       r'`([0-9a-f]{64})`').search(text, a10) if a10 >= 0 else None
        r = {'rc': rc, 'wrapper_notes': [ln for ln in ao.splitlines() if ln.startswith('apply_locked')],
             'protocol_changed': sha(t / 'framelease_v4/PROTOCOL.md') != pro0,
             'manifest_now_equals_sealed_before': sha(t / REG / 'MANIFEST.sha256') == man0,
             'entry_manifest_sha': m and m.group(2), 'manifest_now': sha(t / REG / 'MANIFEST.sha256'),
             'verify_now': verify(t)}
        # what a hand seal (RUNBOOK: "seal by hand") does in this state
        s = reseal(t, LOGS / f'{label}_hand_seal.log')
        r['hand_seal_rc'] = s.returncode
        r['verify_after_hand_seal'] = verify(t)
        r['sealed_manifest_is_the_one_the_entry_names'] = sha(t / REG / 'MANIFEST.sha256') == r['entry_manifest_sha']
        res[label] = r
    # F3: a truncated PROTOCOL.md before the apply
    t = BASE / 'treeF3'
    build_tree(t)
    app = applier(t)
    p = t / 'framelease_v4/PROTOCOL.md'
    p.write_bytes(p.read_bytes()[:150000])
    rc, so, ao = wrapper(t, A10_SPEC, 'outputs/framelease_v4/amendment_a10', app)
    (LOGS / 'F3_truncated.out').write_text(so + ao, encoding='utf-8')
    res['F3_truncated'] = {'rc': rc, 'stop': [ln for ln in ao.splitlines() if ln.startswith('STOP')][:1],
                           'manifest_unchanged': 'write-manifest' not in ao}
    return res


def case_G():
    t = BASE / 'treeG'
    build_tree(t)
    app = applier(t)
    rc, so, ao = wrapper(t, A10_SPEC, 'outputs/framelease_v4/amendment_a10', app, {'TZ': 'UTC'})
    (LOGS / 'G_tz_utc.out').write_text(so + ao, encoding='utf-8')
    text = (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    title = next(ln for ln in text.split('\n') if ln.startswith('**Amendment A10,'))
    _, ph = views(text)
    return {'rc': rc, 'title': title[:80], 'gate_times': {k: v['when'] for k, v in ph['entries'].items()},
            'parsers_accept': True, 'verify': verify(t)}


def case_H():
    t = BASE / 'treeH'
    build_tree(t)
    app = applier(t)
    rc, so, ao = wrapper(t, A10_SPEC, 'outputs/framelease_v4/amendment_a10', app)
    res = {'A10_rc': rc}
    standin_review(t)
    tp = t / A11_TEMPLATE
    txt = tp.read_text(encoding='utf-8')
    k = txt.index('* Scope.')
    bad = ('* **G3 P2 data manifest** (2026-11-15 12:00, Beijing time). A line of the template that the phase driver '
           'reads as its G3 entry.\n')
    tp.write_text(txt[:k] + bad + txt[k:], encoding='utf-8')
    r = run([PY, '-I', '-B', app, A11_SPEC], t, log=LOGS / 'H_check.log')
    res['A11_check_with_gate_line'] = r.stdout.strip().splitlines()[-1:]
    rc, so, ao = wrapper(t, A11_SPEC, 'outputs/framelease_v4/amendment_a11', app)
    (LOGS / 'H_apply.out').write_text(so + ao, encoding='utf-8')
    res['A11_apply_rc'] = rc
    _, ph = views((t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8'))
    res['phase_entries_read'] = {k: v['line'] for k, v in ph['entries'].items()}
    res['A11_title_line'] = ph['amendments'].get('A11')
    return res


# ------------------------------------------------------------------------------------- the proposed fixes, tested

FIX_REPLACEMENTS = (
    ("ENTRY_RE = re.compile(r'^\\* \\*\\*(?P<label>[^*]+)\\*\\*, (?P<when>\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}) \\(')\n",
     "ENTRY_RE = re.compile(r'^\\* \\*\\*(?P<label>[^*]+)\\*\\*, (?P<when>\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}) \\(')\n"
     "PHASE_BASELINE = ROOT / 'outputs/framelease_v4/phase_driver/registered_baseline.json'\n"
     "PHASE_ENTRY_RE = re.compile(r'^\\* \\*\\*(?P<gate>G\\d) (?P<label>[^*]+)\\*\\* \\("
     "(?P<when>\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}), ')  # phase_driver.ENTRY_RE\n"
     "AMEND_RE = re.compile(r'^\\*\\*Amendment (?P<id>A\\d+[a-z]?)[,:.]? ')        # phase_driver.AMEND_RE\n"
     "DRIVER_HEADINGS = ('**Stage selections (P1, FULL).**', '**Phase gates (P2-P7, FULL).**')\n"),
    ("base = json.loads(BASELINE.read_text())['files']\n",
     "base = json.loads(BASELINE.read_text())['files']\n"
     "if PHASE_BASELINE.is_file():           # every file registered after P1 (A3, the phase driver, ...) as well\n"
     "    base = {**base, **json.loads(PHASE_BASELINE.read_text())['files']}\n"),
    ("bad = [ln for ln in tmpl.splitlines() if ln.startswith(('## ', ANCHOR)) or ENTRY_RE.match(ln)]\n",
     "bad = [ln for ln in tmpl.splitlines()[1:] if ln.startswith(('## ', ANCHOR)) or ENTRY_RE.match(ln)\n"
     "       or PHASE_ENTRY_RE.match(ln) or AMEND_RE.match(ln) or ln.strip() in DRIVER_HEADINGS]\n"),
    ("if mode != '--apply':\n",
     "if time.strftime('%z') != '+0800':\n"
     "    die(f'the local time zone is UTC{time.strftime(\"%z\")}, not Beijing time (+0800); '\n"
     "        'the entry says Beijing time')\n"
     "if mode != '--apply':\n"),
)


def fixed_applier(tree):
    """apply_entry_stream.py with the proposed fixes (and ROOT = the tree); the diff is written to the review dir."""
    src = (BUILDER / 'apply_entry_stream.py').read_text(encoding='utf-8')
    new = src
    for old, rep in FIX_REPLACEMENTS:
        if new.count(old) != 1:
            raise SystemExit(f'fix: {old[:50]!r} found {new.count(old)} times')
        new = new.replace(old, rep)
    (REVIEW / 'proposed_apply_entry_stream.diff').write_text(''.join(difflib.unified_diff(
        src.splitlines(True), new.splitlines(True), 'a10r7b/apply_entry_stream.py', 'proposed')), encoding='utf-8')
    old_root = "ROOT = Path('/home/kang/Desktop/DAC')\n"
    if new.count(old_root) != 1:
        raise SystemExit('SAFETY STOP: the ROOT line of the applier is not unique')
    p = WORK / f'{tree.name}_apply_entry_fixed.py'
    p.write_text(new.replace(old_root, f"ROOT = Path('{tree}')\n"), encoding='utf-8')
    return p


def fixed_wrapper(tree, spec, out_rel, app, env_extra=None):
    env = {**ENV, 'APPLY_ROOT': str(tree), 'APPLIER': str(app), **(env_extra or {})}
    r = subprocess.run(['bash', str(REVIEW / 'proposed_apply_locked.sh'), spec, str(tree / out_rel)], cwd=tree,
                       capture_output=True, text=True, env=env)
    out = tree / out_rel / 'apply.out'
    return r.returncode, r.stdout + r.stderr, out.read_text(encoding='utf-8') if out.is_file() else ''


def case_fix():
    res = {}
    inj = write_inject()
    o10, o11 = 'outputs/framelease_v4/amendment_a10', 'outputs/framelease_v4/amendment_a11'
    # normal order with the fixes
    t = BASE / 'fixA'
    build_tree(t)
    app = fixed_applier(t)
    rc10, _, ao10 = fixed_wrapper(t, A10_SPEC, o10, app)
    refresh(t, write=True)
    standin_review(t)
    rc11, _, ao11 = fixed_wrapper(t, A11_SPEC, o11, app)
    (LOGS / 'fixA.out').write_text(ao10 + '\n' + ao11, encoding='utf-8')
    res['A'] = {'rc': (rc10, rc11), 'newly': [ln[-300:] for ln in (ao10 + ao11).splitlines() if 'newly cited' in ln],
                'verify': verify(t)['text']}
    # D: a file registered by A3 changed before the apply
    t = BASE / 'fixD'
    build_tree(t)
    app = fixed_applier(t)
    with open(t / 'framelease_v4/analysis/commit_audit.py', 'a', encoding='utf-8') as fh:
        fh.write('# review probe\n')
    h0 = sha(t / 'framelease_v4/PROTOCOL.md'), sha(t / REG / 'MANIFEST.sha256')
    rc, _, ao = fixed_wrapper(t, A10_SPEC, o10, app)
    (LOGS / 'fixD.out').write_text(ao, encoding='utf-8')
    res['D'] = {'rc': rc, 'stop': [ln for ln in ao.splitlines() if ln.startswith('STOP')][:1],
                'unchanged': h0 == (sha(t / 'framelease_v4/PROTOCOL.md'), sha(t / REG / 'MANIFEST.sha256'))}
    # E: a registered file changed between the manifest and the seal
    t = BASE / 'fixE'
    build_tree(t)
    app = fixed_applier(t)
    env = {'INJECT_APPLIER': str(app), 'INJECT_MODE': 'touch_after_manifest',
           'INJECT_TARGET': str(t / 'framelease_v4/analysis/manipulation.py')}
    rc, so, ao = fixed_wrapper(t, A10_SPEC, o10, inj, env)
    (LOGS / 'fixE.out').write_text(so + ao, encoding='utf-8')
    res['E'] = {'rc': rc, 'note': [ln for ln in ao.splitlines() if ln.startswith('apply_locked')]}
    # F2: killed after PROTOCOL.md was written, before the seal, with a manifest-scope change
    t = BASE / 'fixF'
    build_tree(t)
    app = fixed_applier(t)
    (t / 'framelease_v4/zz_review_probe.txt').write_text('review probe\n', encoding='utf-8')
    rc, so, ao = fixed_wrapper(t, A10_SPEC, o10, inj, {'INJECT_APPLIER': str(app), 'INJECT_MODE': 'kill_before_seal'})
    (LOGS / 'fixF.out').write_text(so + ao, encoding='utf-8')
    s = reseal(t, LOGS / 'fixF_hand_seal.log')
    text = (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    m = re.compile(r'Manifest and seal after this amendment: `MANIFEST\.sha256`, (\d+) files, sha256\s+'
                   r'`([0-9a-f]{64})`').search(text, text.find('**Amendment A10,'))
    res['F2'] = {'rc': rc, 'note': [ln for ln in ao.splitlines() if ln.startswith('apply_locked')],
                 'hand_seal_rc': s.returncode, 'verify': verify(t)['text'],
                 'sealed_manifest_is_the_one_the_entry_names':
                     bool(m) and sha(t / REG / 'MANIFEST.sha256') == m.group(2)}
    # G: TZ=UTC in the caller's environment; then the fixed applier alone under TZ=UTC
    t = BASE / 'fixG'
    build_tree(t)
    app = fixed_applier(t)
    r = run([PY, '-I', '-B', app, A10_SPEC], t, env={**ENV, 'TZ': 'UTC'}, log=LOGS / 'fixG_check_utc.log')
    res['G_applier_alone_utc'] = r.stdout.strip().splitlines()[-1:]
    rc, _, ao = fixed_wrapper(t, A10_SPEC, o10, app, {'TZ': 'UTC'})
    title = next((ln for ln in (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8').split('\n')
                  if ln.startswith('**Amendment A10,')), '')
    res['G_wrapper'] = {'rc': rc, 'title': title[:60], 'local_now': subprocess.run(
        ['date', '+%Y-%m-%d %H:%M'], capture_output=True, text=True, env={**ENV, 'TZ': 'Asia/Shanghai'}).stdout.strip()}
    # H: a template line read as a phase-driver entry
    t = BASE / 'fixH'
    build_tree(t)
    app = fixed_applier(t)
    rc, _, ao = fixed_wrapper(t, A10_SPEC, o10, app)
    standin_review(t)
    tp = t / A11_TEMPLATE
    txt = tp.read_text(encoding='utf-8')
    k = txt.index('* Scope.')
    tp.write_text(txt[:k] + '* **G3 P2 data manifest** (2026-11-15 12:00, Beijing time). Probe.\n' + txt[k:],
                  encoding='utf-8')
    r = run([PY, '-I', '-B', app, A11_SPEC], t, log=LOGS / 'fixH_check.log')
    res['H'] = {'A10_rc': rc, 'A11_check': r.stdout.strip().splitlines()[-1:]}
    return res


VANISH_REPLACEMENTS = (
    ("reg_differ = [k for k, v in sealed.items() if k in base and (ROOT / k).is_file() and sha(ROOT / k) != v]\n",
     "reg_differ = [k for k, v in sealed.items() if k in base and (not (ROOT / k).is_file() or sha(ROOT / k) != v)]\n"),
    ("changed = [k for k in base if k in new_man and k in sealed and new_man[k] != sealed[k]]\n",
     "changed = [k for k in base if k in sealed and new_man.get(k) != sealed[k]]   # changed or vanished\n"),
)


def case_V():
    """A registered file removed before the transaction: the builder's applier, then the applier with the fixes."""
    res = {}
    for label, target in (('p1_baseline', 'framelease_v4/rl/RL_PROTOCOL.md'),
                          ('phase_only', 'framelease_v4/arms_ext/tests/test_drift_guard.py')):
        t = BASE / f'treeV_{label}'
        build_tree(t)
        p1b = json.loads((t / P1_BASELINE).read_text(encoding='utf-8'))['files']
        phb = json.loads((t / PHASE_BASELINE).read_text(encoding='utf-8'))['files']
        app = applier(t)
        (t / target).unlink()
        rc, so, ao = wrapper(t, A10_SPEC, 'outputs/framelease_v4/amendment_a10', app)
        (LOGS / f'V_{label}.out').write_text(so + ao, encoding='utf-8')
        files, added, changed = refresh(t)
        res[label] = {'in_p1_baseline': target in p1b, 'in_phase_baseline': target in phb, 'rc': rc,
                      'sealed_manifest_lists_it': target in manifest(t), 'verify': verify(t)['text'],
                      'phase_refresh_keeps_it': target in files}
        # the same with the fixed applier (both replacement sets)
        t2 = BASE / f'treeV_{label}_fix'
        build_tree(t2)
        app2 = fixed_applier(t2)
        src = app2.read_text(encoding='utf-8')
        for old, rep in VANISH_REPLACEMENTS:
            if src.count(old) != 1:
                raise SystemExit(f'vanish fix: {old[:40]!r} found {src.count(old)} times')
            src = src.replace(old, rep)
        app2.write_text(src, encoding='utf-8')
        (t2 / target).unlink()
        h0 = sha(t2 / 'framelease_v4/PROTOCOL.md'), sha(t2 / REG / 'MANIFEST.sha256')
        rc, so, ao = fixed_wrapper(t2, A10_SPEC, 'outputs/framelease_v4/amendment_a10', app2)
        (LOGS / f'V_{label}_fix.out').write_text(so + ao, encoding='utf-8')
        res[label + '_fix'] = {'rc': rc, 'stop': [ln for ln in ao.splitlines() if ln.startswith('STOP')][:1],
                               'unchanged': h0 == (sha(t2 / 'framelease_v4/PROTOCOL.md'),
                                                   sha(t2 / REG / 'MANIFEST.sha256'))}
    return res


def case_T():
    """A temporary file left by an applier killed between its write and the rename (framelease_v4/ is in the manifest
    scope), then the apply is repeated."""
    t = BASE / 'treeT'
    build_tree(t)
    app = applier(t)
    (t / 'framelease_v4/.PROTOCOL.md.entrytmp').write_text('partial copy left by a killed applier\n', encoding='utf-8')
    rc, so, ao = wrapper(t, A10_SPEC, 'outputs/framelease_v4/amendment_a10', app)
    (LOGS / 'T_tmp_leftover.out').write_text(so + ao, encoding='utf-8')
    return {'rc': rc, 'wrapper_line': so.strip().splitlines()[-1:],
            'sealed_manifest_lists_tmp': 'framelease_v4/.PROTOCOL.md.entrytmp' in manifest(t),
            'tmp_exists_now': (t / 'framelease_v4/.PROTOCOL.md.entrytmp').exists(), 'verify': verify(t)['text']}


def case_D3():
    """As case D with a tool of a later gate (p3_rl.py, gate G4): after the seal, the gate's code check
    (phase_driver.require_registered_code compares the file with the refreshed baseline) sees nothing pending."""
    t = BASE / 'treeD3'
    build_tree(t)
    app = applier(t)
    target = 'framelease_v4/protocol/p3_rl.py'
    with open(t / target, 'a', encoding='utf-8') as fh:
        fh.write('# review probe: a registered tool changed outside a transaction\n')
    rc, so, ao = wrapper(t, A10_SPEC, 'outputs/framelease_v4/amendment_a10', app)
    (LOGS / 'D3_tool.out').write_text(so + ao, encoding='utf-8')
    files, added, changed = refresh(t)
    text = (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    h = sha(t / target)
    return {'rc': rc, 'verify': verify(t)['text'], 'refresh_changed_sha256_adopted': changed,
            'gate_code_check_pending': files.get(target) != h,
            'new_sha256_cited_in_PROTOCOL': h in text}


def case_fixAV():
    """The normal order with every proposed applier change (FIX_REPLACEMENTS and VANISH_REPLACEMENTS) and the proposed
    wrapper: A10, the phase driver's refresh, A11."""
    t = BASE / 'fixAV'
    build_tree(t)
    app = fixed_applier(t)
    src = app.read_text(encoding='utf-8')
    for old, rep in VANISH_REPLACEMENTS:
        if src.count(old) != 1:
            raise SystemExit(f'vanish fix: {old[:40]!r} found {src.count(old)} times')
        src = src.replace(old, rep)
    app.write_text(src, encoding='utf-8')
    before = (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    rc10, _, ao10 = fixed_wrapper(t, A10_SPEC, 'outputs/framelease_v4/amendment_a10', app)
    after10 = (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    p10 = parse_report(t, before)
    refresh(t, write=True)
    standin_review(t)
    rc11, _, ao11 = fixed_wrapper(t, A11_SPEC, 'outputs/framelease_v4/amendment_a11', app)
    p11 = parse_report(t, after10)
    (LOGS / 'fixAV.out').write_text(ao10 + '\n' + ao11, encoding='utf-8')
    newly = [ln.split('newly cited manifest files: ')[-1] for ln in (ao10 + ao11).splitlines() if 'newly cited' in ln]
    return {'rc': (rc10, rc11), 'newly': newly,
            'verify': verify(t)['text'], 'problems': p10['problems'] + p11['problems'],
            'owners': p11.get('first_citing_owner'), 'G8_waits': p11.get('G8_waits')}


CASES = {'tests': case_tests, 'A': case_A, 'B': case_B, 'C': case_C, 'D': case_D, 'E': case_E, 'F': case_F,
         'G': case_G, 'H': case_H, 'fix': case_fix, 'V': case_V, 'T': case_T, 'D3': case_D3, 'fixAV': case_fixAV}


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    names = sys.argv[1:] or list(CASES)
    for n in names:
        res = CASES[n]()
        (WORK / f'summary_{n}.json').write_text(json.dumps(res, indent=1, default=str), encoding='utf-8')
        (LOGS / f'summary_{n}.json').write_text(json.dumps(res, indent=1, default=str), encoding='utf-8')
        print(f'== case {n}')
        print(json.dumps(res, indent=1, default=str)[:6000], flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
