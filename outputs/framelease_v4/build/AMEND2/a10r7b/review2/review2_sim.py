"""Scratch-tree dry runs of the streaming applier and its wrapper (review2 of item a10r7b; read only on the project).

  cd /home/kang/Desktop/DAC
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' \
      taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/a10r7b/review2/review2_sim.py CASE [CASE ...]

Every tree lies under /tmp/A10A11/applier/ (refused elsewhere). A tree holds real copies of framelease_v4/ (without
__pycache__), of outputs/framelease_v4/{registration,p1_driver,amendment_a10,amendment_a11,p1_jobs,protocol}/, of
build/AMEND2/ (without step3/), a real phase_driver/ with copies of registered_baseline.json and D1_DECISION.json, a
real build/R7B/ of links, and read-only links for everything else (no queue, no pipeline_state.json). The project's
PROTOCOL.md, MANIFEST.sha256, SEAL.sha256 and REGISTRATION.json are copied as one consistent snapshot (the seal lines
must match the copies). Every path a run writes or a case changes is checked to resolve inside the tree through real
directories only.

The applier is apply_entry_stream.py with its ROOT line set to the tree (one line differs, checked); the wrapper is
apply_locked.sh with APPLY_ROOT / APPLIER (for case L2 a copy whose lock wait is 5 s instead of 600 s, one token
differs, checked). inject.py runs the applier in-process with faults: a real SIGKILL of itself after --write-manifest,
inside os.replace, before --seal, or while registration.py --write-manifest runs; a registered file changed before or
after --write-manifest; a fixed clock. drv.py runs functions of the project's phase_driver.py on a tree (Cfg --root
TREE): gate_g1 (what the running driver does at every cycle), sealed_baseline (its baseline refresh) and
p1_driver.precheck_tree (the pre-check of its own record transaction).

Logs: outputs/framelease_v4/build/AMEND2/a10r7b/review2/logs/<case>_*.log and results.txt (one line per step:
EXPECTED / FINDING / UNEXPECTED). Exit 0 when no step is UNEXPECTED.
"""
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

SRC = Path('/home/kang/Desktop/DAC')
BASE = Path('/tmp/A10A11/applier')
HERE = SRC / 'outputs/framelease_v4/build/AMEND2/a10r7b/review2'
LOGS = HERE / 'logs'
PY = str(SRC / '.conda-unidrive-linux/bin/python')
APPLIER = SRC / 'outputs/framelease_v4/build/AMEND2/a10r7b/apply_entry_stream.py'
WRAPPER = SRC / 'outputs/framelease_v4/build/AMEND2/a10r7b/apply_locked.sh'
POST = SRC / 'outputs/framelease_v4/build/AMEND2/a10r7b/post_check.py'
A10_SPEC = 'outputs/framelease_v4/build/AMEND2/final/A10_spec.json'
A10_TEMPLATE = 'outputs/framelease_v4/build/AMEND2/final/A10_entry.md'
A11_SPEC = 'outputs/framelease_v4/build/AMEND2/a10r7b/A11_spec.json'
REREVIEW = 'outputs/framelease_v4/build/R7B/rereview/REVIEW.md'
REG = 'outputs/framelease_v4/registration'
MAN = f'{REG}/MANIFEST.sha256'
SEAL = f'{REG}/SEAL.sha256'
PHASE = 'outputs/framelease_v4/phase_driver'
PHASE_BASELINE = f'{PHASE}/registered_baseline.json'
O10, O11 = 'outputs/framelease_v4/amendment_a10', 'outputs/framelease_v4/amendment_a11'
COPY_V4 = ('registration', 'p1_driver', 'amendment_a10', 'amendment_a11', 'p1_jobs', 'protocol')
A10_FILES = ['framelease_v4/analysis/analyze_v4.py', 'framelease_v4/analysis/figures_tables.py',
             'framelease_v4/analysis/prop1_coverage.py', 'framelease_v4/analysis/tests/test_analyze_v4.py',
             'framelease_v4/analysis/tests/test_figures_tables.py',
             'framelease_v4/analysis/tests/test_prop1_coverage.py',
             'framelease_v4/analysis/tests/test_verify_independent.py', 'framelease_v4/analysis/verify_independent.py']
R7B_FILES = ['framelease_v4/analysis/tests/test_verify_table1_extra.py', 'framelease_v4/analysis/verify_table1_extra.py']
ENV = {**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
       'OPENBLAS_NUM_THREADS': '1'}
RESULTS = []

INJECT = r'''"""Run the scratch applier in-process with a fault (review2_sim.py). Environment: INJECT_APPLIER, INJECT_MODE,
INJECT_TARGET (a file of the tree), INJECT_DELAY (s), INJECT_EPOCH (fixed clock)."""
import os
import runpy
import signal
import subprocess
import sys
import time
applier, mode = os.environ['INJECT_APPLIER'], os.environ['INJECT_MODE']
target, delay = os.environ.get('INJECT_TARGET', ''), float(os.environ.get('INJECT_DELAY', '1'))
for p in (applier, target):
    if p and not os.path.realpath(p).startswith('/tmp/A10A11/applier/'):
        raise SystemExit('inject: refused outside /tmp/A10A11/applier/')
real_run, real_replace = subprocess.run, os.replace


def kill9(why):
    print('inject: SIGKILL', why, flush=True)
    os.kill(os.getpid(), signal.SIGKILL)


def touch():
    with open(target, 'a', encoding='utf-8') as fh:
        fh.write('# review2 scratch probe\n')
    print('inject: appended a line to', target, flush=True)


def patched(cmd, *a, **k):
    if '--seal' in cmd and mode == 'kill9_before_seal':
        kill9('before --seal (PROTOCOL.md written)')
    if '--seal' in cmd and mode == 'sigint_group_before_seal':
        print('inject: SIGINT to the process group before --seal (as Ctrl-C would)', flush=True)
        os.killpg(os.getpgrp(), signal.SIGINT)
        time.sleep(5)
    if '--write-manifest' in cmd:
        if mode == 'touch_before_manifest':
            touch()
        if mode == 'remove_before_manifest':
            os.unlink(target)
            print('inject: removed', target, flush=True)
        if mode == 'kill9_during_manifest':
            subprocess.Popen(cmd, cwd=k.get('cwd'), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(delay)
            kill9(f'{delay} s after registration.py --write-manifest started')
    r = real_run(cmd, *a, **k)
    if '--write-manifest' in cmd:
        if mode == 'kill9_after_manifest':
            kill9('after --write-manifest')
        if mode == 'touch_after_manifest':
            touch()
    return r


def replace(src, dst):
    if mode == 'kill9_in_replace':
        kill9('inside os.replace (temporary file written, PROTOCOL.md not replaced)')
    return real_replace(src, dst)


subprocess.run = patched
os.replace = replace
if mode == 'fixed_clock':
    epoch, real_strftime = float(os.environ['INJECT_EPOCH']), time.strftime
    time.strftime = lambda fmt, t=None: real_strftime(fmt, time.localtime(epoch) if t is None else t)
    print('inject: clock fixed at', real_strftime('%Y-%m-%d %H:%M %z', time.localtime(epoch)), flush=True)
sys.argv = [applier] + sys.argv[1:]
runpy.run_path(applier, run_name='__main__')
'''

DRV = r'''"""Functions of the project's phase_driver.py on a scratch tree (review2_sim.py): drv.py MODE TREE [LOCK_TIMEOUT_S]."""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, '/home/kang/Desktop/DAC')
sys.dont_write_bytecode = True
from framelease_v4.protocol import p1_driver as P1  # noqa: E402
from framelease_v4.protocol import phase_driver as PD  # noqa: E402
mode, tree = sys.argv[1], Path(sys.argv[2]).resolve()
if not str(tree).startswith('/tmp/A10A11/applier/'):
    raise SystemExit('drv: refused outside /tmp/A10A11/applier/')
cfg = PD.Cfg(PD.parse_args(['--root', str(tree), '--watch-queues', '', '--normal-priority', '--no-consistency-check',
                            '--lock-timeout-s', sys.argv[3] if len(sys.argv) > 3 else '5']))
for name in ('protocol', 'protocol_lock', 'reg_dir', 'driver_dir', 'p1_dir', 'jobs_dir', 'analyze_code'):
    if not str(getattr(cfg, name)).startswith(str(tree) + '/'):
        raise SystemExit(f'drv: {name} outside the tree')
ctx = PD.Ctx(cfg)
out = {'mode': mode, 't_start': time.time()}
try:
    if mode == 'g1':
        out['result'] = PD.gate_g1(cfg, ctx)
    elif mode == 'refresh':
        old = json.loads(cfg.baseline_path.read_text())['files']
        files = PD.sealed_baseline(cfg, ctx)
        out['result'] = {'files': len(files), 'new': sorted(set(files) - set(old)),
                         'dropped': sorted(set(old) - set(files)),
                         'changed': sorted(p for p in files if p in old and old[p] != files[p])}
    elif mode == 'precheck':
        base = PD.strict_map(cfg, PD.sealed_baseline(cfg, ctx))
        out['result'] = [d[0] for d in P1.precheck_tree(cfg, ctx, base)]
except PD.Alert as a:
    out['alert'] = f'{a.step}: {a.problem}'
except PD.Wait as w:
    out['wait'] = str(w)
out['t_end'] = time.time()
print(json.dumps(out))
'''

PROBER = r'''"""Try the tree's protocol lock (LOCK_EX | LOCK_NB) every 0.05 s until DURATION s passed or STOPFILE exists;
print the state transitions [(time, 'free' | 'busy')] and the counts."""
import fcntl
import json
import os
import sys
import time
lock, duration = sys.argv[1], float(sys.argv[2])
stop = sys.argv[3] if len(sys.argv) > 3 else None
if not os.path.realpath(lock).startswith('/tmp/A10A11/applier/'):
    raise SystemExit('prober: refused outside /tmp/A10A11/applier/')
trans, n, last, t_end = [], {'free': 0, 'busy': 0}, None, time.time() + duration
while time.time() < t_end and not (stop and os.path.exists(stop)):
    fd = os.open(lock, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        now = 'free'
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        now = 'busy'
    os.close(fd)
    n[now] += 1
    if now != last:
        trans.append((time.time(), now))
        last = now
    time.sleep(0.05)
print(json.dumps({'transitions': trans, 'counts': n}))
'''

HOLDER = r'''"""Hold the tree's protocol lock (flock LOCK_EX) for HOLD s, as the phase driver does during its record."""
import fcntl
import os
import sys
import time
lock, hold = sys.argv[1], float(sys.argv[2])
if not os.path.realpath(lock).startswith('/tmp/A10A11/applier/'):
    raise SystemExit('holder: refused outside /tmp/A10A11/applier/')
fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o664)
fcntl.flock(fd, fcntl.LOCK_EX)
print('holder: locked', time.time(), flush=True)
time.sleep(hold)
fcntl.flock(fd, fcntl.LOCK_UN)
print('holder: released', time.time(), flush=True)
'''


# --------------------------------------------------------------------------------------------------------- helpers

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def note(case, step, kind, detail):
    line = f'{case} {step}: {kind} {detail}'
    RESULTS.append(line)
    print(line, flush=True)


def expect(case, step, ok, detail, finding=False):
    """ok: the step behaved as specified (EXPECTED). finding=True marks a step whose observed behaviour is a defect
    (ok then means: the defect was reproduced as described)."""
    if finding:
        note(case, step, 'FINDING' if ok else 'UNEXPECTED', detail)
    else:
        note(case, step, 'EXPECTED' if ok else 'UNEXPECTED', detail)


def inside(tree, rel):
    """The path rel of the tree, refused unless it resolves inside the tree through real directories only."""
    p = tree / rel
    real = tree.resolve()
    cur = tree
    for part in Path(rel).parts:
        cur = cur / part
        if cur.is_symlink():
            raise SystemExit(f'SAFETY STOP: {cur} is a symbolic link')
    if not str(p.resolve()).startswith(str(real) + '/'):
        raise SystemExit(f'SAFETY STOP: {p} does not resolve inside {tree}')
    return p


def rsync(src, dst, *excl):
    subprocess.run(['rsync', '-a'] + [f'--exclude={e}' for e in excl] + [f'{src}/', f'{dst}/'], check=True)


def build(name):
    dst = BASE / name
    if not str(dst.resolve()).startswith(str(BASE) + '/'):
        raise SystemExit(f'SAFETY STOP: {dst}')
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for e in SRC.iterdir():
        if e.name not in ('framelease_v4', 'outputs'):
            (dst / e.name).symlink_to(e)
    rsync(SRC / 'framelease_v4', dst / 'framelease_v4', '__pycache__')
    (dst / 'outputs/framelease_v4').mkdir(parents=True)
    for e in (SRC / 'outputs').iterdir():
        if e.name != 'framelease_v4':
            (dst / 'outputs' / e.name).symlink_to(e)
    v4 = SRC / 'outputs/framelease_v4'
    for e in v4.iterdir():
        if e.name.startswith('queue_') or e.name in ('pipeline_state.json', 'phase_driver', 'build'):
            continue
        if e.name in COPY_V4:
            rsync(e, dst / 'outputs/framelease_v4' / e.name)
        else:
            (dst / 'outputs/framelease_v4' / e.name).symlink_to(e)
    (dst / PHASE).mkdir()
    for f in ('registered_baseline.json', 'D1_DECISION.json'):
        shutil.copy2(v4 / 'phase_driver' / f, dst / PHASE / f)
    b = dst / 'outputs/framelease_v4/build'
    b.mkdir()
    for e in (v4 / 'build').iterdir():
        if e.name == 'AMEND2':
            rsync(e, b / 'AMEND2', '/step3', '/a10r7b/review2', '/a10r7b/sim_output*', '/a10r7b/review_rerun')
        elif e.name == 'R7B':
            (b / 'R7B').mkdir()
            for f in e.iterdir():
                (b / 'R7B' / f.name).symlink_to(f)
        else:
            (b / e.name).symlink_to(e)
    for attempt in range(5):        # one consistent snapshot of PROTOCOL.md and the registration files
        shutil.copy2(SRC / 'framelease_v4/PROTOCOL.md', dst / 'framelease_v4/PROTOCOL.md')
        for f in ('MANIFEST.sha256', 'SEAL.sha256', 'REGISTRATION.json'):
            shutil.copy2(SRC / REG / f, dst / REG / f)
        shutil.copy2(v4 / 'phase_driver/registered_baseline.json', dst / PHASE_BASELINE)
        seal = dict(ln.split('  ', 1)[::-1] for ln in (dst / SEAL).read_text().splitlines())
        if seal.get('framelease_v4/PROTOCOL.md') == sha(dst / 'framelease_v4/PROTOCOL.md') \
                and seal.get(MAN) == sha(dst / MAN):
            break
        time.sleep(5)
    else:
        raise SystemExit('the project seal did not match its files in 5 attempts')
    for rel in ('framelease_v4/PROTOCOL.md', 'framelease_v4/.protocol.lock', REG, MAN, SEAL, f'{REG}/REGISTRATION.json',
                'outputs/framelease_v4/p1_driver', PHASE, PHASE_BASELINE, O10, O11, 'outputs/framelease_v4/p1_jobs',
                'outputs/framelease_v4/protocol', 'outputs/framelease_v4/build/AMEND2/final/A10_entry.md',
                'outputs/framelease_v4/build/AMEND2/a10r7b/A11_entry.md', 'outputs/framelease_v4/build/R7B'):
        inside(dst, rel)
    return dst


def scratch_applier(tree, wait_s=None):
    src = APPLIER.read_text(encoding='utf-8')
    old = "ROOT = Path('/home/kang/Desktop/DAC')\n"
    if src.count(old) != 1:
        raise SystemExit('SAFETY STOP: the ROOT line of the applier is not unique')
    new = src.replace(old, f"ROOT = Path('{tree}')\n")
    diff = [(a, b) for a, b in zip(src.splitlines(), new.splitlines()) if a != b]
    if len(diff) != 1 or len(src.splitlines()) != len(new.splitlines()):
        raise SystemExit(f'SAFETY STOP: the applier copy differs in {len(diff)} lines')
    p = BASE / f'apply_entry_scratch_{tree.name}.py'
    p.write_text(new, encoding='utf-8')
    return p


def wrapper_copy(wait_s):
    src = WRAPPER.read_text(encoding='utf-8')
    old = 'flock -w 600 -E 97'
    if src.count(old) != 1:
        raise SystemExit('SAFETY STOP: the flock line of the wrapper is not unique')
    new = src.replace(old, f'flock -w {wait_s} -E 97')
    diff = [(a, b) for a, b in zip(src.splitlines(), new.splitlines()) if a != b]
    if len(diff) != 1:
        raise SystemExit('SAFETY STOP: the wrapper copy differs in more than one line')
    p = BASE / f'apply_locked_w{wait_s}.sh'
    p.write_text(new, encoding='utf-8')
    return p


def run(cmd, log, cwd, env=None, timed=False):
    cmd = [str(c) for c in cmd]
    if timed:
        cmd = ['/usr/bin/time', '-f', 'TIME %e s MAXRSS %M KB'] + cmd
    t0 = time.time()
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env or ENV)
    log.write_text(f'$ {" ".join(cmd)}\n(exit {r.returncode}, {time.time() - t0:.1f} s)\n' + r.stdout + r.stderr,
                   encoding='utf-8')
    return r


def rss(r):
    m = re.search(r'TIME ([\d.]+) s MAXRSS (\d+) KB', r.stderr)
    return f'{m.group(1)} s, max RSS {int(m.group(2)) / 1024:.0f} MB' if m else 'no time line'


def verify(tree, log):
    r = run([PY, '-I', '-B', tree / 'framelease_v4/protocol/registration.py', '--verify'], log, tree)
    good = 'manifest: OK' in r.stdout and r.stdout.count(': OK') == 3
    return good, r.stdout.strip().replace('\n', ' | ')[:300]


def wrapper(tree, spec, out_rel, app, log, env_extra=None, script=None, timed=False, popen=False):
    script = script or WRAPPER          # read at call time (case X switches to the proposed wrapper)
    env = {**ENV, 'APPLY_ROOT': str(tree), 'APPLIER': str(app), **(env_extra or {})}
    cmd = ['bash', str(script), spec, str(tree / out_rel)]
    if timed:
        cmd = ['/usr/bin/time', '-f', 'TIME %e s MAXRSS %M KB'] + cmd
    if popen:
        return subprocess.Popen(cmd, cwd=tree, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
                                start_new_session=True)
    t0 = time.time()
    r = subprocess.run(cmd, cwd=tree, capture_output=True, text=True, env=env)
    ao = tree / out_rel / 'apply.out'
    ao = ao.read_text(encoding='utf-8') if ao.is_file() else ''
    log.write_text(f'(exit {r.returncode}, {time.time() - t0:.1f} s)\n' + r.stdout + r.stderr + '\n--- apply.out\n' + ao,
                   encoding='utf-8')
    return r.returncode, r.stdout + r.stderr, ao


def state(tree):
    return tuple(sha(tree / p) for p in ('framelease_v4/PROTOCOL.md', MAN, SEAL))


def drv(tree, mode, log, lock_timeout='5'):
    r = run([PY, '-I', '-B', BASE / 'drv.py', mode, tree, lock_timeout], log, tree)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {'error': (r.stdout + r.stderr)[-600:]}


def post(tree, name, log):
    r = run([PY, '-I', '-B', POST, name, '--root', tree], log, SRC)
    return r.returncode, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:]


def sealed_now(tree):
    seal = dict(ln.split('  ', 1)[::-1] for ln in (tree / SEAL).read_text().splitlines())
    return seal.get('framelease_v4/PROTOCOL.md') == sha(tree / 'framelease_v4/PROTOCOL.md') \
        and seal.get(MAN) == sha(tree / MAN)


def stand_in(tree):
    p = inside(tree, 'outputs/framelease_v4/build/R7B') / 'rereview'
    if p.is_symlink() or p.exists():
        raise SystemExit('SAFETY STOP: build/R7B/rereview exists in the tree (a link to the project): not written')
    p.mkdir()
    (p / 'REVIEW.md').write_text('# Scratch stand-in of the review of the R7B fixes\n\n**Verdict: GO.**\n',
                                 encoding='utf-8')


def newly(ao):
    ln = [x for x in ao.splitlines() if 'newly cited manifest files' in x]
    return ln[-1].split('newly cited manifest files:', 1)[1].strip() if ln else None


def mutate(tree, rel, how):
    p = inside(tree, rel)
    if how == 'append':
        with open(p, 'a', encoding='utf-8') as fh:
            fh.write('\n')
    elif how == 'remove':
        p.unlink()
    return p


def restore(tree, rel):
    shutil.copy2(SRC / rel, inside(tree, rel))


def resealed_tree_with(tree, new_text):
    """Write new_text as the tree's PROTOCOL.md and seal the tree (scratch only)."""
    inside(tree, 'framelease_v4/PROTOCOL.md').write_text(new_text, encoding='utf-8')
    r = subprocess.run([PY, '-I', '-B', str(tree / 'framelease_v4/protocol/registration.py'), '--seal'], cwd=tree,
                       capture_output=True, text=True, env=ENV)
    return r.returncode == 0


# --------------------------------------------------------------------------------------------------------- parsers

def parse_report(tree, base_text):
    sys.path.insert(0, str(SRC))
    sys.dont_write_bytecode = True
    from framelease_v4.protocol import p1_driver as P1  # noqa: E402
    from framelease_v4.protocol import phase_driver as PD  # noqa: E402
    text = (tree / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    out = {}
    try:
        pv, view = P1.protocol_view(None, text), PD.phase_view(None, text)
        pv0, view0 = P1.protocol_view(None, base_text), PD.phase_view(None, base_text)
    except Exception as exc:  # noqa: BLE001
        return {'parser_error': f'{type(exc).__name__}: {exc}'}
    out['amendments'] = {k: v for k, v in view['amendments'].items() if k in ('A3', 'A4', 'A7', 'A9', 'A10', 'A11')}
    out['p1_entries_unchanged'] = {k: v['text'] for k, v in pv['entries'].items()} == \
        {k: v['text'] for k, v in pv0['entries'].items()}
    out['phase_entries_unchanged'] = {k: v['text'] for k, v in view['entries'].items()} == \
        {k: v['text'] for k, v in view0['entries'].items()}
    s, e = view['sec']
    owners = {}
    for rel in A10_FILES + R7B_FILES:
        h = sha(tree / rel)
        line = next((i + 1 for i in range(s, e) if h in view['lines'][i]), None)
        owners[rel] = PD.citing_amendment(view, line) if line else None
    out['first_citing_owner'] = owners
    cfg = type('Cfg', (), {'analyze_code': tree / 'framelease_v4/analysis/analyze_v4.py',
                           'rel': staticmethod(lambda q: str(Path(q).relative_to(tree)))})()
    out['g8_waits'] = PD.analysis_registration(cfg, view)[0]
    gate = ('* **G3 P2 data manifest** (2026-11-15 23:30, Beijing time). Scratch gate entry. Manifest and seal: '
            '`MANIFEST.sha256`, 999 files, sha256 `' + 'e' * 64 + '`, sealed with this entry.')
    later_text = PD.insert_entry(None, text, [gate])
    later = PD.phase_view(None, later_text)
    line = next((i + 1 for i in range(*later['sec']) if sha(tree / A10_FILES[0]) in later['lines'][i]), None)
    out['after_a_later_G3_entry'] = {'entries': sorted(later['entries']),
                                     'analyze_v4_owner': PD.citing_amendment(later, line) if line else None,
                                     'g8_waits': PD.analysis_registration(cfg, later)[0]}
    old_lines, new_lines = base_text.split('\n'), text.split('\n')
    import difflib
    added = [ln for ln in difflib.ndiff(old_lines, new_lines) if ln.startswith('+ ')]
    added = [ln[2:] for ln in added]
    out['added_lines'] = len(added)
    out['prose_over_120'] = [ln for ln in added if len(ln) > 120 and not ln.lstrip().startswith('|')]
    out['table_rows_over_120'] = len([ln for ln in added if len(ln) > 120 and ln.lstrip().startswith('|')])
    forms = [ln for ln in added if P1.ENTRY_RE.match(ln) or PD.ENTRY_RE.match(ln) or ln.strip() in
             (PD.HEADING, P1.HEADING, P1.SEC_START) or ln.startswith('## ') or ln.startswith(PD.ANCHOR)]
    out['driver_form_lines'] = forms
    out['amend_titles_added'] = [ln[:40] for ln in added if PD.AMEND_RE.match(ln)]
    return out


# --------------------------------------------------------------------------------------------------------- cases

def case_A():
    """A10 then A11 end to end through the wrapper, with the phase driver's functions after each."""
    t = build('treeA')
    app = scratch_applier(t)
    base_text = (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    good, s = verify(t, LOGS / 'A0_verify.log')
    expect('A', '0 tree seal', good, s)
    g = drv(t, 'g1', LOGS / 'A1_driver_g1_before.log')
    expect('A', '1 driver gate_g1 before A10', g.get('result') == 'done', json.dumps(g)[:200])
    r = run([PY, '-I', '-B', app, A10_SPEC], LOGS / 'A2_a10_check.log', t, timed=True)
    expect('A', '2 A10 check mode', r.returncode == 0 and 'check: pre-checks passed' in r.stdout, rss(r))
    stopf = BASE / 'treeA.prober.stop'
    stopf.unlink(missing_ok=True)
    prober = subprocess.Popen([PY, '-I', '-B', BASE / 'prober.py', t / 'framelease_v4/.protocol.lock', '1800', stopf],
                              stdout=subprocess.PIPE, text=True)
    time.sleep(1)
    t0 = time.time()
    rc, so, ao = wrapper(t, A10_SPEC, O10, app, LOGS / 'A3_wrapper_a10.log', timed=True)
    t1 = time.time()
    time.sleep(1)
    stopf.write_text('stop\n')
    pout = json.loads(prober.communicate()[0].strip().splitlines()[-1])
    stopf.unlink()
    busy = [(a, b) for a, b in zip(pout['transitions'], pout['transitions'][1:] + [(t1 + 99, 'end')])
            if a[1] == 'busy']
    (LOGS / 'A3c_lock_prober.json').write_text(json.dumps({'t_wrapper_start': t0, 't_wrapper_end': t1, **pout},
                                                          indent=1), encoding='utf-8')
    expect('A', '3c the lock is held in one interval from the wrapper start to its end (a driver cannot take it '
                'mid-way)', len(busy) == 1 and busy[0][0][0] - t0 < 2 and abs(busy[0][1][0] - t1) < 2,
           f'busy intervals {[(round(a[0] - t0, 1), round(b[0] - t0, 1)) for a, b in busy]} s after the start; wrapper '
           f'{t1 - t0:.1f} s')
    nc = newly(ao)
    expect('A', '3 A10 through the wrapper', rc == 0 and nc is not None and sorted(ast.literal_eval(nc)) == sorted(A10_FILES)
           and sealed_now(t), f'exit {rc}; newly cited {nc}; {rss(type("R", (), {"stderr": so})())}; '
           f'{t1 - t0:.0f} s')
    good, s = verify(t, LOGS / 'A3b_verify.log')
    expect('A', '3b seal after A10', good, s)
    rep = parse_report(t, base_text)
    (LOGS / 'A4_parse_after_a10.json').write_text(json.dumps(rep, indent=1), encoding='utf-8')
    ok = ('parser_error' not in rep and rep['amendments'].get('A10') and len(rep['amendments']['A10']) == 1
          and rep['p1_entries_unchanged'] and rep['phase_entries_unchanged']
          and all(rep['first_citing_owner'][f] == 'A10' for f in A10_FILES) and not rep['g8_waits']
          and not rep['prose_over_120'] and not rep['driver_form_lines'] and len(rep['amend_titles_added']) == 1
          and rep['after_a_later_G3_entry']['analyze_v4_owner'] == 'A10'
          and not rep['after_a_later_G3_entry']['g8_waits'] and 'p2_data' in rep['after_a_later_G3_entry']['entries'])
    expect('A', '4 parsers after A10 (citing_amendment, G8 analysis_registration, a later G3 entry)', ok,
           json.dumps({k: rep.get(k) for k in ('amendments', 'g8_waits', 'prose_over_120', 'table_rows_over_120',
                                                 'added_lines', 'after_a_later_G3_entry')})[:600])
    rc5, last = post(t, 'A10', LOGS / 'A5_post_check_a10.log')
    expect('A', '5 post_check A10 before the refresh', rc5 == 3, f'exit {rc5}; {last}')
    g = drv(t, 'refresh', LOGS / 'A6_driver_refresh.log')
    res = g.get('result') or {}
    expect('A', '6 driver baseline refresh after A10', sorted(res.get('new', [])) == sorted(A10_FILES)
           and not res.get('dropped') and not res.get('changed'), json.dumps(g)[:300])
    rc5, last = post(t, 'A10', LOGS / 'A6b_post_check_a10.log')
    expect('A', '6b post_check A10 after the refresh', rc5 == 0, f'exit {rc5}; {last}')
    g = drv(t, 'g1', LOGS / 'A7_driver_g1_after_a10.log')
    expect('A', '7 driver gate_g1 after A10', g.get('result') == 'done', json.dumps(g)[:200])
    stand_in(t)
    r = run([PY, '-I', '-B', app, A11_SPEC], LOGS / 'A8_a11_check.log', t)
    expect('A', '8 A11 check mode', r.returncode == 0 and 'check: pre-checks passed' in r.stdout, f'exit {r.returncode}')
    rc, so, ao = wrapper(t, A11_SPEC, O11, app, LOGS / 'A8b_wrapper_a11.log')
    nc = newly(ao)
    expect('A', '8b A11 through the wrapper', rc == 0 and nc is not None and sorted(ast.literal_eval(nc)) == sorted(R7B_FILES)
           and sealed_now(t), f'exit {rc}; newly cited {nc}')
    rep = parse_report(t, base_text)
    (LOGS / 'A9_parse_after_a11.json').write_text(json.dumps(rep, indent=1), encoding='utf-8')
    ok = ('parser_error' not in rep and len(rep['amendments'].get('A11', [])) == 1
          and len(rep['amendments'].get('A10', [])) == 1 and rep['amendments']['A10'][0] < rep['amendments']['A11'][0]
          and all(rep['first_citing_owner'][f] == 'A10' for f in A10_FILES)
          and all(rep['first_citing_owner'][f] == 'A11' for f in R7B_FILES) and not rep['g8_waits']
          and not rep['prose_over_120'] and not rep['driver_form_lines'])
    expect('A', '9 parsers after A11', ok, json.dumps({k: rep.get(k) for k in ('amendments', 'prose_over_120',
                                                                              'table_rows_over_120')})[:300])
    rc9, last = post(t, 'A11', LOGS / 'A9b_post_check_a11.log')
    g = drv(t, 'refresh', LOGS / 'A9c_driver_refresh.log')
    res = g.get('result') or {}
    rc9b, last9b = post(t, 'A11', LOGS / 'A9d_post_check_a11.log')
    expect('A', '9b post_check A11 (3 before, 0 after the refresh; refresh adds the 2 R7B files)',
           rc9 == 3 and rc9b == 0 and sorted(res.get('new', [])) == sorted(R7B_FILES), f'{rc9}/{rc9b}; {res}')
    shutil.copy2(t / 'framelease_v4/PROTOCOL.md', LOGS / 'PROTOCOL.after_A10_A11.scratch.md.txt')
    d = subprocess.run(['diff', str(SRC / 'framelease_v4/PROTOCOL.md'), str(t / 'framelease_v4/PROTOCOL.md')],
                       capture_output=True, text=True)
    hunks = [ln for ln in d.stdout.splitlines() if re.match(r'^\d', ln)]
    (LOGS / 'A10_protocol.diff').write_text(d.stdout, encoding='utf-8')
    note('A', '10 diff against the project PROTOCOL.md', 'INFO', f'hunks {hunks}')


def case_B():
    """Registered files changed or missing: each class stops before --write-manifest; the p1_jobs class does not."""
    t = build('treeB')
    app = scratch_applier(t)
    for k, (rel, how, cls) in enumerate((
            ('framelease_v4/arms/realized.py', 'append', 'P1 baseline'),
            ('framelease_v4/analysis/commit_audit.py', 'append', 'phase baseline only'),
            ('framelease_v4/protocol/stress_bench.py', 'remove', 'phase baseline only, missing on disk')), 1):
        mutate(t, rel, how)
        s0 = state(t)
        r = run([PY, '-I', '-B', app, A10_SPEC], LOGS / f'B{k}_check.log', t)
        rc, so, ao = wrapper(t, A10_SPEC, O10, app, LOGS / f'B{k}_wrapper.log')
        expect('B', f'{k} {how} {rel} ({cls})', r.returncode == 1 and rel in r.stdout and rc == 1 and 'STOP:' in ao
               and 'registration --write-manifest' not in ao and state(t) == s0,
               f'check exit {r.returncode}, wrapper exit {rc}: {[x for x in ao.splitlines() if "STOP" in x][:1]}')
        restore(t, rel)
    # a baseline that lists a file the sealed manifest does not hold
    pb = inside(t, PHASE_BASELINE)
    doc = json.loads(pb.read_text())
    doc['files']['framelease_v4/zz_ghost.py'] = 'f' * 64
    pb.write_text(json.dumps(doc, indent=1), encoding='utf-8')
    r = run([PY, '-I', '-B', app, A10_SPEC], LOGS / 'B4_check_absent.log', t)
    expect('B', '4 a registered file absent from the sealed manifest', r.returncode == 1
           and 'absent from the sealed manifest' in r.stdout and 'zz_ghost' in r.stdout, r.stdout.strip()[-160:])
    shutil.copy2(SRC / PHASE_BASELINE, pb)
    # changed between the pre-check and --write-manifest (post-manifest check), and vanished there
    inj = BASE / 'inject.py'
    for k, (mode, rel) in enumerate((('touch_before_manifest', 'framelease_v4/analysis/manipulation.py'),
                                     ('remove_before_manifest', 'framelease_v4/rl/RL_PROTOCOL.md')), 5):
        s0 = state(t)
        env = {'INJECT_APPLIER': str(app), 'INJECT_MODE': mode, 'INJECT_TARGET': str(inside(t, rel))}
        rc, so, ao = wrapper(t, A10_SPEC, O10, inj, LOGS / f'B{k}_wrapper_{mode}.log', env)
        expect('B', f'{k} {mode} {rel}', rc == 1 and 'registered files changed or left the new manifest' in ao
               and rel in ao and 'RESTORED the sealed manifest' in ao and state(t) == s0,
               f'exit {rc}; state unchanged {state(t) == s0}')
        restore(t, rel)
    good, s = verify(t, LOGS / 'B6b_verify.log')
    expect('B', '6b every file restored: the seal verifies', good, s)
    # a registered file changed between --write-manifest and --seal
    s0 = state(t)
    rel = 'framelease_v4/arms/realized.py'
    env = {'INJECT_APPLIER': str(app), 'INJECT_MODE': 'touch_after_manifest', 'INJECT_TARGET': str(inside(t, rel))}
    rc, so, ao = wrapper(t, A10_SPEC, O10, inj, LOGS / 'B7_wrapper_touch_after_manifest.log', env)
    g = drv(t, 'g1', LOGS / 'B7b_driver_g1.log')
    shutil.copy2(t / MAN, inside(t, f'{PHASE}/manifest_sealed.sha256'))
    pc = drv(t, 'precheck', LOGS / 'B7c_driver_precheck.log')
    expect('B', '7 registered file changed between --write-manifest and --seal: exit 95, the driver sees it',
           rc == 95 and 'registration --seal -> 0' in ao and rel in ao and g.get('result') == 'done'
           and 'realized.py' in pc.get('alert', ''), f'exit {rc}; g1 {g.get("result")}; precheck {pc}'[:400])


def case_P():
    """A P1 job file of outputs/framelease_v4/p1_jobs/ (strict for both drivers) changed before A10."""
    t = build('treeP')
    app = scratch_applier(t)
    rel = 'outputs/framelease_v4/p1_jobs/FULL/b04_lease_s2.check.json'
    mutate(t, rel, 'append')
    shutil.copy2(t / MAN, inside(t, f'{PHASE}/manifest_sealed.sha256'))
    pc = drv(t, 'precheck', LOGS / 'P1_driver_precheck_before.log')
    expect('P', '1 the phase driver\'s own pre-check refuses the changed P1 job file',
           rel in pc.get('alert', ''), json.dumps(pc)[:300])
    r = run([PY, '-I', '-B', app, A10_SPEC], LOGS / 'P2_check.log', t)
    rc, so, ao = wrapper(t, A10_SPEC, O10, app, LOGS / 'P3_wrapper.log')
    good, s = verify(t, LOGS / 'P3b_verify.log')
    shutil.copy2(t / MAN, inside(t, f'{PHASE}/manifest_sealed.sha256'))
    pc2 = drv(t, 'precheck', LOGS / 'P4_driver_precheck_after.log')
    man = dict(ln.split('  ', 1)[::-1] for ln in (t / MAN).read_text().splitlines())
    expect('P', '2 the applier seals it: check passes, wrapper exit 0, the sealed manifest holds the changed sha256, '
                'the driver\'s pre-check afterwards finds nothing', r.returncode == 0 and rc == 0 and good
           and man.get(rel) == sha(t / rel) and 'result' in pc2 and rel not in json.dumps(pc2),
           f'check exit {r.returncode}; wrapper exit {rc}; verify {s[:60]}; precheck after {json.dumps(pc2)[:120]}',
           finding=True)


def case_K():
    """Real SIGKILL of the applier at four points; the phase driver's gate_g1 afterwards."""
    inj = BASE / 'inject.py'
    for k, mode in enumerate(('kill9_after_manifest', 'kill9_in_replace', 'kill9_before_seal'), 1):
        t = build(f'treeK{k}')
        app = scratch_applier(t)
        (inside(t, 'framelease_v4') / 'zz_new_probe.txt').write_text('scratch: a new file in the manifest scope\n',
                                                                       encoding='utf-8')
        s0 = state(t)
        env = {'INJECT_APPLIER': str(app), 'INJECT_MODE': mode}
        rc, so, ao = wrapper(t, A10_SPEC, O10, inj, LOGS / f'K{k}_wrapper_{mode}.log', env)
        g = drv(t, 'g1', LOGS / f'K{k}_driver_g1.log')
        tmp_left = (t / 'framelease_v4/.PROTOCOL.md.entrytmp').exists()
        if mode != 'kill9_before_seal':
            expect('K', f'{k} {mode}: exit 137, sealed state restored, driver gate_g1 passes', rc == 137
                   and state(t) == s0 and not tmp_left and g.get('result') == 'done',
                   f'exit {rc}; state unchanged {state(t) == s0}; tmp left {tmp_left}; g1 {json.dumps(g)[:160]}; '
                   f'{[x for x in ao.splitlines() if x.startswith("apply_locked:")]}')
        else:
            expect('K', f'{k} {mode}: exit 137, the wrapper releases the lock with an unsealed PROTOCOL.md; the '
                        'phase driver\'s next cycle (gate_g1 -> ensure_recorded) raises an ALERT',
                   rc == 137 and 'seal it now' in ao and not sealed_now(t) and 'unsealed edit' in g.get('alert', ''),
                   f'exit {rc}; sealed {sealed_now(t)}; g1 {json.dumps(g)[:260]}', finding=True)
            r = run(['flock', '-w', '60', t / 'framelease_v4/.protocol.lock', PY, '-I', '-B',
                     t / 'framelease_v4/protocol/registration.py', '--seal'], LOGS / 'K3b_hand_seal.log', t)
            good, s = verify(t, LOGS / 'K3c_verify.log')
            g = drv(t, 'g1', LOGS / 'K3d_driver_g1_after_hand_seal.log')
            expect('K', '3b the RUNBOOK hand seal gives a consistent state', r.returncode == 0 and good
                   and g.get('result') == 'done', f'{s}; g1 {g.get("result")}')
    # the race: a driver cycle that waits on the lock while the wrapper finishes
    t = build('treeK4')
    app = scratch_applier(t)
    env = {**ENV, 'APPLY_ROOT': str(t), 'APPLIER': str(inj), 'INJECT_APPLIER': str(app),
           'INJECT_MODE': 'kill9_before_seal'}
    w = subprocess.Popen(['bash', str(WRAPPER), A10_SPEC, str(t / O10)], cwd=t, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, env=env)
    ao_p = t / O10 / 'apply.out'
    d = None
    while w.poll() is None:
        if d is None and ao_p.is_file() and 'seal it now' in ao_p.read_text(encoding='utf-8'):
            d = subprocess.Popen([PY, '-I', '-B', BASE / 'drv.py', 'g1', t, '300'], cwd=t, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        time.sleep(0.05)
    t_wrapper_end = time.time()
    if d is None:
        note('K', '4 race', 'UNEXPECTED', 'the wrapper ended before the driver stand-in started')
        return
    out, err = d.communicate()
    (LOGS / 'K4_race_driver.log').write_text(out + err, encoding='utf-8')
    g = json.loads(out.strip().splitlines()[-1]) if out.strip() else {'error': err[-300:]}
    lag = g.get('t_end', 0) - t_wrapper_end
    note('K', '4 a driver cycle that starts while the wrapper verifies (after "seal it now")', 'INFO',
         f'ended {lag:+.1f} s relative to the wrapper exit with {json.dumps({k: g.get(k) for k in ("result", "alert", "wait") if k in g})}'[:400])
    g = drv(t, 'g1', LOGS / 'K4b_driver_g1_next_cycle.log')
    expect('K', '4b the driver\'s next cycle after the wrapper exit: ALERT', 'unsealed edit' in g.get('alert', ''),
           json.dumps(g)[:200], finding=True)


def case_O():
    """SIGKILL of the applier while registration.py --write-manifest runs: the orphan keeps the lock and rewrites the
    manifest after the wrapper's restore decision."""
    t = build('treeO')
    app = scratch_applier(t)
    (inside(t, 'framelease_v4') / 'zz_new_probe.txt').write_text('scratch: a new file in the manifest scope\n',
                                                                   encoding='utf-8')
    s0 = state(t)
    inj = BASE / 'inject.py'
    env = {'INJECT_APPLIER': str(app), 'INJECT_MODE': 'kill9_during_manifest', 'INJECT_DELAY': '1'}
    rc, so, ao = wrapper(t, A10_SPEC, O10, inj, LOGS / 'O1_wrapper_kill9_during_manifest.log', env)
    prober = run([PY, '-I', '-B', BASE / 'prober.py', t / 'framelease_v4/.protocol.lock', '1'],
                 LOGS / 'O2_prober_right_after.log', t)
    busy_after = json.loads(prober.stdout.strip().splitlines()[-1])['counts'] if prober.stdout.strip() else None
    waited = 0
    while any('/tmp/A10A11/applier/treeO/framelease_v4/protocol/registration.py' in Path(f'/proc/{p}/cmdline')
              .read_bytes().decode(errors='replace').replace('\0', ' ') for p in os.listdir('/proc') if p.isdigit()
              and Path(f'/proc/{p}/cmdline').exists()) and waited < 600:
        time.sleep(1)
        waited += 1
    g = drv(t, 'g1', LOGS / 'O3_driver_g1.log')
    expect('O', '1 orphan registration.py: the wrapper decided on the old manifest, the orphan rewrote it, the seal '
                'no longer matches, the phase driver raises an ALERT',
           rc == 137 and state(t)[0] == s0[0] and state(t)[1] != s0[1] and not sealed_now(t)
           and 'unsealed edit' in g.get('alert', ''),
           f'exit {rc}; wrapper lines {[x for x in ao.splitlines() if x.startswith("apply_locked:")]}; lock busy right '
           f'after the wrapper {busy_after}; orphan ended {waited} s after the wrapper; g1 {g.get("alert", g)}'[:500],
           finding=True)


def case_L():
    """The protocol lock: a holder before the wrapper; the 5-s copy of the wrapper; --apply without the wrapper."""
    t = build('treeL')
    app = scratch_applier(t)
    lock = t / 'framelease_v4/.protocol.lock'
    h = subprocess.Popen([PY, '-I', '-B', BASE / 'holder.py', lock, '20'], stdout=subprocess.PIPE, text=True)
    time.sleep(1)
    t0 = time.time()
    rc, so, ao = wrapper(t, A10_SPEC, O10, app, LOGS / 'L1_wrapper_after_holder.log')
    h.wait()
    expect('L', '1 a driver holding the lock: the wrapper waits, then seals', rc == 0 and time.time() - t0 >= 18
           and sealed_now(t), f'exit {rc} after {time.time() - t0:.0f} s')
    t = build('treeL2')
    app = scratch_applier(t)
    lock = t / 'framelease_v4/.protocol.lock'
    s0 = state(t)
    h = subprocess.Popen([PY, '-I', '-B', BASE / 'holder.py', lock, '30'], stdout=subprocess.PIPE, text=True)
    time.sleep(1)
    rc, so, ao = wrapper(t, A10_SPEC, O10, app, LOGS / 'L2_wrapper_w5_busy.log', script=wrapper_copy(5))
    h.wait()
    expect('L', '2 lock busy longer than the wait: exit 97, nothing changed', rc == 97 and state(t) == s0,
           f'exit {rc}; state unchanged {state(t) == s0}')
    h = subprocess.Popen([PY, '-I', '-B', BASE / 'holder.py', lock, '120'], stdout=subprocess.PIPE, text=True)
    time.sleep(1)
    r = run([PY, '-I', '-B', app, A10_SPEC, '--apply'], LOGS / 'L3_apply_without_wrapper_lock_held.log', t,
            env={**ENV, 'TZ': 'Asia/Shanghai'})
    h.terminate()
    h.wait()
    expect('L', '3 --apply without the wrapper while another process holds the lock: the applier seals anyway',
           r.returncode == 0 and sealed_now(t) and state(t) != s0, f'exit {r.returncode}; sealed {sealed_now(t)}',
           finding=True)


def case_T():
    """Texts: an in-place text twice, an early clock, a long filled line, driver forms, Sec. 13.2 heading, empty file."""
    sys.path.insert(0, str(SRC))
    sys.dont_write_bytecode = True
    from framelease_v4.protocol import p1_driver as P1  # noqa: E402
    from framelease_v4.protocol import phase_driver as PD  # noqa: E402
    inj = BASE / 'inject.py'
    spec = json.loads((SRC / A10_SPEC).read_text())
    # T1: an "old" text twice in a sealed PROTOCOL.md
    t = build('treeT1')
    app = scratch_applier(t)
    text = (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    old3 = spec['inplace'][2]['old']
    k = text.index(old3) + len(old3)
    ok = resealed_tree_with(t, text[:k] + '\n' + old3 + text[k:])
    s0 = state(t)
    r = run([PY, '-I', '-B', app, A10_SPEC], LOGS / 'T1_check_old_twice.log', t)
    rc, so, ao = wrapper(t, A10_SPEC, O10, app, LOGS / 'T1_wrapper_old_twice.log')
    expect('T', '1 an in-place "old" twice: STOP before --write-manifest', ok and r.returncode == 1
           and 'found 2 times' in r.stdout and rc == 1 and 'registration --write-manifest' not in ao
           and state(t) == s0, f'check exit {r.returncode}; wrapper exit {rc}')
    # T2: a clock earlier than the last Sec. 13.2 entry (G2 06:43)
    t = build('treeT2')
    app = scratch_applier(t)
    epoch = time.mktime(time.strptime('2026-11-15 06:30', '%Y-%m-%d %H:%M'))
    env = {'INJECT_APPLIER': str(app), 'INJECT_MODE': 'fixed_clock', 'INJECT_EPOCH': str(epoch)}
    rc, so, ao = wrapper(t, A10_SPEC, O10, inj, LOGS / 'T2_wrapper_early_clock.log', env)
    title = next((ln for ln in (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8').split('\n')
                  if ln.startswith('**Amendment A10,')), '')
    expect('T', '2 entry stamped 06:30, before A3 (06:40) and G1 / G2 (06:42 / 06:43): sealed without a stop',
           rc == 0 and '2026-11-15 06:30' in title, f'exit {rc}; title {title[:52]!r}', finding=True)
    # T3: a filled prose line over 120 columns
    t = build('treeT3')
    app = scratch_applier(t)
    tp = inside(t, A10_TEMPLATE)
    tmpl = tp.read_text(encoding='utf-8')
    probe = ('* Probe. A scratch-tree prose line, its placeholder at the end: '
             '{{sha256:framelease_v4/analysis/analyze_v4.py}}.')
    if not 105 <= len(probe) <= 120:
        raise SystemExit(f'probe line has {len(probe)} columns')
    tp.write_text(tmpl.replace('* Scope.', probe + '\n* Scope.', 1), encoding='utf-8')
    r = run([PY, '-I', '-B', app, A10_SPEC], LOGS / 'T3_check_long_line.log', t)
    rc, so, ao = wrapper(t, A10_SPEC, O10, app, LOGS / 'T3_wrapper_long_line.log')
    longest = max((ln for ln in (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8').split('\n')
                   if ln.startswith('* Probe.')), key=len, default='')
    expect('T', '3 a filled prose line over 120 columns: sealed without a stop', rc == 0 and len(longest) > 120,
           f'template line {len(probe)} columns, filled {len(longest)} columns; check exit {r.returncode}; '
           f'wrapper exit {rc}',
           finding=True)
    # T4: template lines in driver forms (template check) and lines that take a driver form only when filled
    t = build('treeT4')
    app = scratch_applier(t)
    tp = inside(t, A10_TEMPLATE)
    for k, (line, where) in enumerate((
            ('* **lease_s1**, 2026-11-15 12:00 (Beijing time). Probe.', 'template'),
            ('* **G3 P2 data manifest** (2026-11-15 12:00, Beijing time). Probe.', 'template'),
            ('**Amendment A12, 2026-11-15 12:00 (Beijing time): probe.**', 'template'),
            ('**Phase gates (P2-P7, FULL).**', 'template'),
            ('**Stage selections (P1, FULL).**', 'template'),
            ('* Probe. Each amendment gets the date and time of its entry.', 'template'),
            ('* **lease_s1**, {{datetime}} (Beijing time). Probe.', 'filled'),
            ('* **G3 P2 data manifest** ({{datetime}}, Beijing time). Probe.', 'filled'),
            ('**Amendment A{{manifest:files}}: probe.**', 'filled'),
            ('### 13.2 Amendments', 'none')), 1):
        tp.write_text(tmpl.replace('* Scope.', line + '\n* Scope.', 1), encoding='utf-8')
        s0 = state(t)
        r = run([PY, '-I', '-B', app, A10_SPEC], LOGS / f'T4_{k}_check.log', t)
        if where == 'template':
            expect('T', f'4.{k} template line {line[:44]!r}: check STOP', r.returncode == 1
                   and 'template problem' in r.stdout, r.stdout.strip()[-120:])
        elif where == 'filled':
            rc, so, ao = wrapper(t, A10_SPEC, O10, app, LOGS / f'T4_{k}_wrapper.log')
            expect('T', f'4.{k} line {line[:44]!r}: template passes, the filled-entry check stops after '
                        '--write-manifest, the wrapper restores', r.returncode == 0 and rc == 1
                   and 'filled entry problem' in ao and state(t) == s0
                   and ('RESTORED the sealed manifest' in ao or 'the manifest equals the sealed one' in ao),
                   f'check exit {r.returncode}; wrapper exit {rc}')
        else:
            rc, so, ao = wrapper(t, A10_SPEC, O10, app, LOGS / f'T4_{k}_wrapper.log')
            text = (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
            try:
                P1.protocol_view(None, text)
                PD.phase_view(None, text)
                parsed = 'parsed'
            except Exception as exc:  # noqa: BLE001
                parsed = f'{type(exc).__name__}: {exc}'
            expect('T', f'4.{k} line {line!r}: check passes, sealed, both drivers\' parsers raise an Alert',
                   r.returncode == 0 and rc == 0 and parsed.startswith('Alert'), f'exit {rc}; {parsed}'[:220],
                   finding=True)
    # T5: an empty file in the manifest scope (its sha256 e3b0c442... is cited in PROTOCOL.md)
    t = build('treeT5')
    app = scratch_applier(t)
    (inside(t, 'framelease_v4') / 'zz_empty_probe.py').write_text('', encoding='utf-8')
    rc, so, ao = wrapper(t, A10_SPEC, O10, app, LOGS / 'T5_wrapper_empty_file.log')
    g = drv(t, 'refresh', LOGS / 'T5b_driver_refresh.log')
    rcp, last = post(t, 'A10', LOGS / 'T5c_post_check_a10.log')
    new = (g.get('result') or {}).get('new', [])
    n_app = len(ast.literal_eval(newly(ao) or '[]'))
    expect('T', '5 an empty file in scope: the applier reports 8 newly cited files, the driver registers 9, post_check '
                'passes', rc == 0 and n_app == 8 and 'framelease_v4/zz_empty_probe.py' in new
           and len(new) == 9 and rcp == 0, f'exit {rc}; driver new {len(new)}: {new[-1:]}; post_check {rcp}',
           finding=True)


def case_M():
    """Memory and time of check mode, of the wrapper with --apply and of post_check (the project's specs)."""
    t = build('treeM')
    app = scratch_applier(t)
    r = run([PY, '-I', '-B', app, A10_SPEC], LOGS / 'M1_check.log', t, timed=True)
    note('M', '1 A10 check mode', 'INFO', rss(r))
    rc, so, ao = wrapper(t, A10_SPEC, O10, app, LOGS / 'M2_wrapper.log', timed=True)
    note('M', '2 A10 wrapper --apply', 'INFO', f'exit {rc}; {rss(type("R", (), {"stderr": so})())}')
    r = run([PY, '-I', '-B', POST, 'A10', '--root', t], LOGS / 'M3_post_check.log', SRC, timed=True)
    note('M', '3 post_check A10', 'INFO', f'exit {r.returncode}; {rss(r)}')


def case_R():
    """After a kill before --seal (unsealed state), the wrapper run again instead of the hand seal."""
    t = build('treeR')
    app = scratch_applier(t)
    inj = BASE / 'inject.py'
    s0 = state(t)
    rc, so, ao = wrapper(t, A10_SPEC, O10, inj, LOGS / 'R1_wrapper_kill9_before_seal.log',
                         {'INJECT_APPLIER': str(app), 'INJECT_MODE': 'kill9_before_seal'})
    copies0 = (sha(t / O10 / 'PROTOCOL.sealed.before_apply'), sha(t / O10 / 'MANIFEST.sealed.before_apply'))
    rc2, so2, ao2 = wrapper(t, A10_SPEC, O10, app, LOGS / 'R2_wrapper_again_unsealed.log')
    copies1 = (sha(t / O10 / 'PROTOCOL.sealed.before_apply'), sha(t / O10 / 'MANIFEST.sealed.before_apply'))
    expect('R', '1 the wrapper run again on the unsealed state: STOP at the seal check, but the copies named '
                '"sealed.before_apply" are overwritten with the unsealed files and apply.out says "the manifest equals '
                'the sealed one"', rc == 137 and rc2 == 1 and 'the seal does not verify' in ao2
           and copies0 == s0[:2] and copies1 != copies0 and copies1 == state(t)[:2]
           and 'the manifest equals the sealed one' in ao2,
           f'exit {rc} then {rc2}; copies were the sealed files {copies0 == s0[:2]}, now the unsealed ones '
           f'{copies1 == state(t)[:2]}', finding=True)


def case_S():
    """SIGINT to the wrapper's process group before --seal (Ctrl-C, or a terminal or tool that interrupts it)."""
    t = build('treeS')
    app = scratch_applier(t)
    inj = BASE / 'inject.py'
    env = {**ENV, 'APPLY_ROOT': str(t), 'APPLIER': str(inj), 'INJECT_APPLIER': str(app),
           'INJECT_MODE': 'sigint_group_before_seal'}
    w = subprocess.Popen(['bash', str(WRAPPER), A10_SPEC, str(t / O10)], cwd=t, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, env=env, start_new_session=True)
    out, err = w.communicate()
    ao = (t / O10 / 'apply.out').read_text(encoding='utf-8') if (t / O10 / 'apply.out').is_file() else ''
    (LOGS / 'S1_wrapper_sigint_group.log').write_text(f'(exit {w.returncode})\n{out}{err}\n--- apply.out\n{ao}',
                                                     encoding='utf-8')
    g = drv(t, 'g1', LOGS / 'S2_driver_g1.log')
    expect('S', '1 SIGINT to the process group before --seal: no "apply_locked: exit" line, PROTOCOL.md holds the '
                'entry unsealed, the lock is free, the phase driver raises an ALERT',
           'apply_locked: exit' not in out and '**Amendment A10,' in (t / 'framelease_v4/PROTOCOL.md').read_text()
           and not sealed_now(t) and 'unsealed edit' in g.get('alert', ''),
           f'wrapper exit {w.returncode}; console {out.strip()[-80:]!r}; g1 {g.get("alert", g)}'[:400], finding=True)


def case_C():
    """Registered by citation only: after A10 (the phase baseline not refreshed) analyze_v4.py changes; A11 stops."""
    t = build('treeC')
    app = scratch_applier(t)
    rc, so, ao = wrapper(t, A10_SPEC, O10, app, LOGS / 'C1_wrapper_a10.log')
    base = json.loads((t / PHASE_BASELINE).read_text())['files']
    rel = 'framelease_v4/analysis/analyze_v4.py'
    mutate(t, rel, 'append')
    stand_in(t)
    s0 = state(t)
    r = run([PY, '-I', '-B', app, A11_SPEC], LOGS / 'C2_a11_check_cited_file_changed.log', t)
    rc2, so2, ao2 = wrapper(t, A11_SPEC, O11, app, LOGS / 'C3_wrapper_a11_cited_file_changed.log')
    expect('C', '1 a file registered only by its citation in A10 (not in either baseline) changed: A11 stops',
           rc == 0 and rel not in base and r.returncode == 1 and rel in r.stdout and rc2 == 1
           and 'registration --write-manifest' not in ao2 and state(t) == s0,
           f'A10 exit {rc}; in the phase baseline {rel in base}; A11 check exit {r.returncode}, wrapper exit {rc2}')


def case_D():
    """The wrapper's refusals: the temporary file and each driver's transaction and ALERT file (exit 96)."""
    t = build('treeD')
    app = scratch_applier(t)
    s0 = state(t)
    for k, rel in enumerate(('framelease_v4/.PROTOCOL.md.entrytmp', f'{PHASE}/protocol_txn.json', f'{PHASE}/ALERT.txt',
                             'outputs/framelease_v4/p1_driver/protocol_txn.json',
                             'outputs/framelease_v4/p1_driver/ALERT.txt'), 1):
        p = inside(t, rel)
        p.write_text('scratch probe\n', encoding='utf-8')
        rc, so, ao = wrapper(t, A10_SPEC, O10, app, LOGS / f'D{k}_wrapper.log')
        r = run([PY, '-I', '-B', app, A10_SPEC], LOGS / f'D{k}_check.log', t)
        expect('D', f'{k} {rel} exists: wrapper exit 96, check STOP, nothing changed', rc == 96 and 'nothing applied' in ao
               and r.returncode == 1 and Path(rel).name in r.stdout and state(t) == s0, f'exit {rc} / {r.returncode}')
        p.unlink()


def case_Y():
    """An unregistered cited file (analyze_v4.py) changed between --write-manifest and the fill (original applier)."""
    t = build('treeY')
    app = scratch_applier(t)
    inj = BASE / 'inject.py'
    rel = 'framelease_v4/analysis/analyze_v4.py'
    old_sha = sha(SRC / rel)
    env = {'INJECT_APPLIER': str(app), 'INJECT_MODE': 'touch_after_manifest', 'INJECT_TARGET': str(inside(t, rel))}
    rc, so, ao = wrapper(t, A10_SPEC, O10, inj, LOGS / 'Y1_wrapper_touch_cited_after_manifest.log', env)
    man = dict(ln.split('  ', 1)[::-1] for ln in (t / MAN).read_text().splitlines())
    text = (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    g = drv(t, 'refresh', LOGS / 'Y2_driver_refresh.log')
    new = (g.get('result') or {}).get('new', [])
    expect('Y', '1 the entry cites the new sha256 of analyze_v4.py, the sealed manifest holds the old one: exit 95, the '
                'driver registers 7 files (not analyze_v4.py)', rc == 95 and man.get(rel) == old_sha
           and sha(t / rel) in text and old_sha not in text and rel not in new and len(new) == 7,
           f'exit {rc}; manifest holds the old sha256 {man.get(rel) == old_sha}; entry cites the new one '
           f'{sha(t / rel) in text}; driver newly registered {len(new)}', finding=True)


def case_X():
    """The proposed applier and wrapper (review2/proposed_*): regression and every break case."""
    global APPLIER, WRAPPER
    APPLIER, WRAPPER = HERE / 'proposed_apply_entry_stream.py', HERE / 'proposed_apply_locked.sh'
    inj = BASE / 'inject.py'
    # X1: A10, the driver refresh, A11; and A11 right after A10
    t = build('treeX1')
    app = scratch_applier(t)
    base_text = (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    r = run([PY, '-I', '-B', app, A10_SPEC], LOGS / 'X1_a10_check.log', t, timed=True)
    rc, so, ao = wrapper(t, A10_SPEC, O10, app, LOGS / 'X1_wrapper_a10.log', timed=True)
    nc = newly(ao)
    rep = parse_report(t, base_text)
    rcp, _ = post(t, 'A10', LOGS / 'X1_post_check_a10.log')
    g = drv(t, 'refresh', LOGS / 'X1_driver_refresh.log')
    rcp2, _ = post(t, 'A10', LOGS / 'X1_post_check_a10_after.log')
    expect('X', '1 proposal: A10 check and wrapper, parsers, post_check 3 -> 0', r.returncode == 0 and rc == 0
           and sorted(ast.literal_eval(nc)) == sorted(A10_FILES) and not rep.get('g8_waits')
           and rep['first_citing_owner'][A10_FILES[0]] == 'A10' and rcp == 3 and rcp2 == 0,
           f'check {rss(r)}; wrapper exit {rc}, {rss(type("R", (), {"stderr": so})())}; post_check {rcp}/{rcp2}')
    stand_in(t)
    rc, so, ao = wrapper(t, A11_SPEC, O11, app, LOGS / 'X1_wrapper_a11.log')
    nc = newly(ao)
    expect('X', '1b proposal: A11 after the refresh', rc == 0 and sorted(ast.literal_eval(nc)) == sorted(R7B_FILES),
           f'exit {rc}; newly {nc}')
    t = build('treeX1c')
    app = scratch_applier(t)
    rc, so, ao = wrapper(t, A10_SPEC, O10, app, LOGS / 'X1c_wrapper_a10.log')
    stand_in(t)
    rc2, so2, ao2 = wrapper(t, A11_SPEC, O11, app, LOGS / 'X1c_wrapper_a11_no_refresh.log')
    expect('X', '1c proposal: A11 right after A10 (no refresh)', rc == 0 and rc2 == 0
           and sorted(ast.literal_eval(newly(ao2))) == sorted(R7B_FILES), f'exit {rc} / {rc2}')
    # X2: a P1 job file changed
    t = build('treeX2')
    app = scratch_applier(t)
    rel = 'outputs/framelease_v4/p1_jobs/FULL/b04_lease_s2.check.json'
    mutate(t, rel, 'append')
    s0 = state(t)
    r = run([PY, '-I', '-B', app, A10_SPEC], LOGS / 'X2_check_p1_job_file.log', t)
    rc, so, ao = wrapper(t, A10_SPEC, O10, app, LOGS / 'X2_wrapper_p1_job_file.log')
    expect('X', '2 proposal: a changed P1 job file stops the check and the wrapper', r.returncode == 1 and rel in r.stdout
           and rc == 1 and state(t) == s0, f'check exit {r.returncode}; wrapper exit {rc}')
    # X3-X5: kill before --seal, orphan registration.py, SIGINT to the group
    for k, (mode, extra) in enumerate((('kill9_before_seal', {}), ('kill9_during_manifest', {'INJECT_DELAY': '1'}),
                                       ('kill9_after_manifest', {}), ('kill9_in_replace', {})), 3):
        t = build(f'treeX{k}')
        app = scratch_applier(t)
        (inside(t, 'framelease_v4') / 'zz_new_probe.txt').write_text('scratch: a new file in scope\n', encoding='utf-8')
        s0 = state(t)
        rc, so, ao = wrapper(t, A10_SPEC, O10, inj, LOGS / f'X{k}_wrapper_{mode}.log',
                             {'INJECT_APPLIER': str(app), 'INJECT_MODE': mode, **extra})
        g = drv(t, 'g1', LOGS / f'X{k}_driver_g1.log')
        good, sv = verify(t, LOGS / f'X{k}_verify.log')
        if mode == 'kill9_before_seal':
            ok = rc == 94 and sealed_now(t) and good and '**Amendment A10,' in (t / 'framelease_v4/PROTOCOL.md').read_text()
        else:
            ok = rc == 137 and state(t) == s0 and good
        expect('X', f'{k} proposal: {mode}: consistent sealed state when the lock is released, driver gate_g1 passes',
               ok and g.get('result') == 'done',
               f'exit {rc}; {[x for x in ao.splitlines() if x.startswith("apply_locked:")]}; {sv[:40]}; g1 '
               f'{g.get("result", g.get("alert"))}'[:400])
    t = build('treeX7')
    app = scratch_applier(t)
    env = {**ENV, 'APPLY_ROOT': str(t), 'APPLIER': str(inj), 'INJECT_APPLIER': str(app),
           'INJECT_MODE': 'sigint_group_before_seal'}
    w = subprocess.Popen(['bash', str(WRAPPER), A10_SPEC, str(t / O10)], cwd=t, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, env=env, start_new_session=True)
    out, err = w.communicate()
    (LOGS / 'X7_wrapper_sigint_group.log').write_text(f'(exit {w.returncode})\n{out}{err}', encoding='utf-8')
    g = drv(t, 'g1', LOGS / 'X7_driver_g1.log')
    expect('X', '7 proposal: SIGINT to the process group is ignored, the entry is sealed', w.returncode == 0
           and sealed_now(t) and g.get('result') == 'done', f'exit {w.returncode}; {out.strip()[-60:]!r}')
    # X8: an unsealed PROTOCOL.md before the wrapper
    t = build('treeX8')
    app = scratch_applier(t)
    with open(inside(t, 'framelease_v4/PROTOCOL.md'), 'a', encoding='utf-8') as fh:
        fh.write('\n')
    rc, so, ao = wrapper(t, A10_SPEC, O10, app, LOGS / 'X8_wrapper_unsealed.log')
    expect('X', '8 proposal: an unsealed PROTOCOL.md: exit 96, no copies made', rc == 96
           and 'SEAL.sha256 does not match' in ao and not list((t / O10).glob('attempt_*')), f'exit {rc}')
    # X9: --apply without the wrapper while another process holds the lock
    t = build('treeX9')
    app = scratch_applier(t)
    s0 = state(t)
    h = subprocess.Popen([PY, '-I', '-B', BASE / 'holder.py', t / 'framelease_v4/.protocol.lock', '60'],
                         stdout=subprocess.PIPE, text=True)
    time.sleep(1)
    r = run([PY, '-I', '-B', app, A10_SPEC, '--apply'], LOGS / 'X9_apply_without_wrapper.log', t)
    h.terminate()
    h.wait()
    expect('X', '9 proposal: --apply without the lock stops', r.returncode == 1 and 'runs only under' in r.stdout
           and state(t) == s0, f'exit {r.returncode}; {r.stdout.strip()[-100:]}')
    # X10: early clock; X11: long filled line; X12: Sec. 13.2 heading line; X13: empty file; X14: cited file changed
    t = build('treeX10')
    app = scratch_applier(t)
    s0 = state(t)
    epoch = time.mktime(time.strptime('2026-11-15 06:30', '%Y-%m-%d %H:%M'))
    rc, so, ao = wrapper(t, A10_SPEC, O10, inj, LOGS / 'X10_wrapper_early_clock.log',
                         {'INJECT_APPLIER': str(app), 'INJECT_MODE': 'fixed_clock', 'INJECT_EPOCH': str(epoch)})
    expect('X', '10 proposal: a clock before the last Sec. 13.2 stamp stops before --write-manifest', rc == 1
           and 'earlier than the last stamp' in ao and 'write-manifest' not in ao and state(t) == s0, f'exit {rc}')
    t = build('treeX11')
    app = scratch_applier(t)
    tp = inside(t, A10_TEMPLATE)
    tmpl = tp.read_text(encoding='utf-8')
    for k, line in enumerate(('* Probe. A scratch-tree prose line, its placeholder at the end: '
                              '{{sha256:framelease_v4/analysis/analyze_v4.py}}.', '### 13.2 Amendments'), 11):
        tp.write_text(tmpl.replace('* Scope.', line + '\n* Scope.', 1), encoding='utf-8')
        r = run([PY, '-I', '-B', app, A10_SPEC], LOGS / f'X{k}_check.log', t)
        expect('X', f'{k} proposal: template line {line[:40]!r} stops the check', r.returncode == 1
               and 'problem' in r.stdout, r.stdout.strip()[-140:])
    tp.write_text(tmpl, encoding='utf-8')
    t = build('treeX13')
    app = scratch_applier(t)
    (inside(t, 'framelease_v4') / 'zz_empty_probe.py').write_text('', encoding='utf-8')
    s0 = state(t)
    rc, so, ao = wrapper(t, A10_SPEC, O10, app, LOGS / 'X13_wrapper_empty_file.log')
    expect('X', '13 proposal: an empty file in scope: STOP (9 files would be registered), manifest restored',
           rc == 1 and 'would register' in ao and 'zz_empty_probe' in ao and state(t) == s0, f'exit {rc}')
    t = build('treeX14')
    app = scratch_applier(t)
    s0 = state(t)
    rel = 'framelease_v4/analysis/analyze_v4.py'
    rc, so, ao = wrapper(t, A10_SPEC, O10, inj, LOGS / 'X14_wrapper_touch_cited_after_manifest.log',
                         {'INJECT_APPLIER': str(app), 'INJECT_MODE': 'touch_after_manifest',
                          'INJECT_TARGET': str(inside(t, rel))})
    expect('X', '14 proposal: a cited file changed after --write-manifest: STOP before PROTOCOL.md is written',
           rc == 1 and 'cited files changed after --write-manifest' in ao and state(t)[0] == s0[0], f'exit {rc}')


CASES = {'A': case_A, 'B': case_B, 'P': case_P, 'K': case_K, 'O': case_O, 'L': case_L, 'T': case_T, 'M': case_M,
         'R': case_R, 'S': case_S, 'X': case_X, 'Y': case_Y,
         'C': case_C, 'D': case_D}


def main():
    names = sys.argv[1:] or list(CASES)
    BASE.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    for name, text in (('inject.py', INJECT), ('drv.py', DRV), ('prober.py', PROBER), ('holder.py', HOLDER)):
        (BASE / name).write_text(text, encoding='utf-8')
    for n in names:
        t0 = time.time()
        CASES[n]()
        note(n, 'done', 'INFO', f'{time.time() - t0:.0f} s')
    with open(LOGS / 'results.txt', 'a', encoding='utf-8') as fh:
        fh.write(f'# run {time.strftime("%Y-%m-%d %H:%M:%S %z")} cases {names}\n' + '\n'.join(RESULTS) + '\n')
    bad = [x for x in RESULTS if 'UNEXPECTED' in x]
    print('NO UNEXPECTED STEP' if not bad else f'{len(bad)} UNEXPECTED STEP(S)')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
