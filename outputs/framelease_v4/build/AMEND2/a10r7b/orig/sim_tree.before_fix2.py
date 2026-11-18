"""Dry run of Amendments A10 and A11 on scratch copies of the project tree (item a10r7b; read only on the project).

  cd /home/kang/Desktop/DAC
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' \
      taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/a10r7b/sim_tree.py [--out /tmp/AMEND3/a10r7b/sim_tree] [--cases ABCDEFG]

Every scratch tree lies under --out (refused outside /tmp/AMEND3/). A tree holds real copies of framelease_v4/ (without
__pycache__; registration.py finds its root from its own path, so the copy is its own root), of
outputs/framelease_v4/{registration,p1_driver,amendment_a10,amendment_a11}/, of phase_driver/registered_baseline.json
(only that file) and of build/AMEND2/ (without step3/), a real directory build/R7B/ whose entries link to the
project's, and symbolic links (read only) for every other entry of the project root, of outputs/ and of
outputs/framelease_v4/ and build/. Never linked: the runners' queues (queue_*), pipeline_state.json and the rest of
phase_driver/. Before anything runs in a tree, every path a run writes (PROTOCOL.md, its temporary file, the lock,
registration/, the drivers' directories) is checked to resolve inside the tree.

The applier is apply_entry_stream.py with one line changed, ROOT = the tree (the script checks that the copy differs in
that line only); the wrapper is apply_locked.sh with APPLY_ROOT / APPLIER. inject.py (written under --out) runs the
applier in-process with subprocess.run patched for the fault cases (kill after --write-manifest, kill before --seal,
a registered file changed after --write-manifest). Cases:
  A  A10 check, A10 --apply (flock on the tree's lock), seal check, parsers; then, before any refresh of the phase
     driver's baseline, A11 with a stand-in of the review of the R7B fixes in the tree: check, --apply, seal check,
     parsers (p1_driver.protocol_view, phase_driver.phase_view, citing_amendment, analysis_registration), a later gate
     entry of the phase driver; diff against the project PROTOCOL.md.
  B  A11 before A10: the check stops (its in-place text is not in PROTOCOL.md).
  C  A10 applied, then A11 without the review file: STOP at the pre-check (a placeholder without a value); nothing
     changed, the seal verifies.
  D  apply_locked.sh: A10 sealed through it; a new file in the manifest scope and A11 killed right after
     --write-manifest: the wrapper restores the sealed manifest, the seal verifies; A11 again: sealed.
  E  registered files (review M1): a file of the phase driver's baseline only (commit_audit.py), the G4 tool p3_rl.py,
     a removed file of the phase driver's baseline only and a removed file of the P1 baseline: each stops before
     --write-manifest with nothing changed; with every file restored, A10 is sealed.
  F  F1: a new file in the manifest scope and A10 killed before --seal: PROTOCOL.md holds the entry, the wrapper keeps
     the rewritten manifest; the hand seal gives the manifest the entry names (review S1). F2: a registered file
     changed after --write-manifest: the wrapper exits 95 (review S2).
  G  TZ=UTC: the applier alone stops, the wrapper stamps Beijing time (S3); a leftover temporary file and the
     drivers' transaction and ALERT files stop the wrapper (exit 96) or the applier (S5, S6); template lines read as a
     phase-driver entry, an amendment title, a driver heading or holding the anchor phrase stop the check (S4).
Writes the logs of every step and summary.txt under --out. Exit 0 when every case gives its expected result.
"""
import argparse
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
sys.path.insert(0, str(SRC))
sys.dont_write_bytecode = True

from framelease_v4.protocol import p1_driver as P1  # noqa: E402
from framelease_v4.protocol import phase_driver as PD  # noqa: E402

HERE = SRC / 'outputs/framelease_v4/build/AMEND2/a10r7b'
PY = str(SRC / '.conda-unidrive-linux/bin/python')
APPLIER = HERE / 'apply_entry_stream.py'
WRAPPER = HERE / 'apply_locked.sh'
A10_SPEC = 'outputs/framelease_v4/build/AMEND2/final/A10_spec.json'
A11_SPEC = 'outputs/framelease_v4/build/AMEND2/a10r7b/A11_spec.json'
A11_TEMPLATE = 'outputs/framelease_v4/build/AMEND2/a10r7b/A11_entry.md'
REREVIEW = 'outputs/framelease_v4/build/R7B/rereview/REVIEW.md'
REG = 'outputs/framelease_v4/registration'
MAN = f'{REG}/MANIFEST.sha256'
PHASE_BASELINE = 'outputs/framelease_v4/phase_driver/registered_baseline.json'
O10, O11 = 'outputs/framelease_v4/amendment_a10', 'outputs/framelease_v4/amendment_a11'
COPY_V4 = ('registration', 'p1_driver', 'amendment_a10', 'amendment_a11')
NEVER = ('queue_', 'pipeline_state.json', 'phase_driver')
R7B_NEW = str(['framelease_v4/analysis/tests/test_verify_table1_extra.py',
               'framelease_v4/analysis/verify_table1_extra.py'])
GATE_LINE = ('* **G3 P2 data manifest** (2026-11-15 23:00, Beijing time). Simulated gate entry; manifest and seal: '
             '`MANIFEST.sha256`, 999 files, sha256 `' + 'd' * 64 + '`, sealed with this entry.')
ENV = {**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
       'OPENBLAS_NUM_THREADS': '1'}
INJECT = r'''"""Run the applier in-process with subprocess.run patched (scratch-tree fault injection of sim_tree.py).
Environment: INJECT_APPLIER (the scratch applier), INJECT_MODE (kill_after_manifest | kill_before_seal |
touch_after_manifest), INJECT_TARGET (the file appended to after --write-manifest)."""
import os
import runpy
import subprocess
import sys
applier, mode, target = os.environ['INJECT_APPLIER'], os.environ['INJECT_MODE'], os.environ.get('INJECT_TARGET', '')
if not applier.startswith('/tmp/AMEND3/') or (target and not target.startswith('/tmp/AMEND3/')):
    raise SystemExit('inject: refused outside /tmp/AMEND3/')
real_run = subprocess.run


def patched(cmd, *a, **k):
    if mode == 'kill_before_seal' and '--seal' in cmd:
        sys.stdout.flush()
        os._exit(137)
    r = real_run(cmd, *a, **k)
    if '--write-manifest' in cmd:
        if mode == 'kill_after_manifest':
            print('inject: killed after --write-manifest', flush=True)
            os._exit(137)
        if mode == 'touch_after_manifest':
            with open(target, 'a', encoding='utf-8') as fh:
                fh.write('# scratch-tree probe: changed between the manifest and the seal\n')
            print('inject: appended a line to', target, flush=True)
    return r


subprocess.run = patched
sys.argv = [applier] + sys.argv[1:]
runpy.run_path(applier, run_name='__main__')
'''


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def rsync(src, dst, *excl):
    cmd = ['rsync', '-a'] + [f'--exclude={e}' for e in excl] + [f'{src}/', f'{dst}/']
    subprocess.run(cmd, check=True)


def build_tree(dst):
    if not str(dst.resolve()).startswith('/tmp/AMEND3/'):
        raise SystemExit(f'SAFETY STOP: {dst} is not under /tmp/AMEND3/')
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for e in list(SRC.iterdir()):
        if e.name not in ('framelease_v4', 'outputs'):
            (dst / e.name).symlink_to(e)
    rsync(SRC / 'framelease_v4', dst / 'framelease_v4', '__pycache__')
    (dst / 'outputs/framelease_v4').mkdir(parents=True)
    for e in (SRC / 'outputs').iterdir():
        if e.name != 'framelease_v4':
            (dst / 'outputs' / e.name).symlink_to(e)
    v4 = SRC / 'outputs/framelease_v4'
    for e in v4.iterdir():
        if e.name.startswith(NEVER[0]) or e.name in NEVER[1:]:
            continue
        if e.name in COPY_V4:
            rsync(e, dst / 'outputs/framelease_v4' / e.name)
        elif e.name != 'build':
            (dst / 'outputs/framelease_v4' / e.name).symlink_to(e)
    (dst / 'outputs/framelease_v4/phase_driver').mkdir()
    shutil.copy2(SRC / PHASE_BASELINE, dst / PHASE_BASELINE)
    b = dst / 'outputs/framelease_v4/build'
    b.mkdir()
    for e in (v4 / 'build').iterdir():
        if e.name == 'AMEND2':
            rsync(e, b / 'AMEND2', '/step3')
        elif e.name == 'R7B':
            (b / 'R7B').mkdir()
            for f in e.iterdir():
                (b / 'R7B' / f.name).symlink_to(f)
        else:
            (b / e.name).symlink_to(e)
    # the copies of PROTOCOL.md and of registration/ must belong together: copy both again, then verify the seal
    shutil.copy2(SRC / 'framelease_v4/PROTOCOL.md', dst / 'framelease_v4/PROTOCOL.md')
    rsync(v4 / 'registration', dst / REG)


def safety(dst):
    """Every path a run writes resolves inside the tree."""
    real = dst.resolve()
    for rel in ('framelease_v4', 'framelease_v4/PROTOCOL.md', 'framelease_v4/.protocol.lock',
                'framelease_v4/.PROTOCOL.md.entrytmp', REG, MAN, f'{REG}/SEAL.sha256', f'{REG}/REGISTRATION.json',
                'outputs/framelease_v4/p1_driver', 'outputs/framelease_v4/phase_driver', PHASE_BASELINE, O10, O11,
                'outputs/framelease_v4/build/AMEND2', A11_TEMPLATE, 'outputs/framelease_v4/build/R7B'):
        p = dst / rel
        if p.is_symlink() or not str(p.resolve()).startswith(str(real) + '/'):
            raise SystemExit(f'SAFETY STOP: {p} does not resolve inside the scratch tree')


def applier(dst, out):
    src = APPLIER.read_text(encoding='utf-8')
    old = "ROOT = Path('/home/kang/Desktop/DAC')\n"
    if src.count(old) != 1:
        raise SystemExit('SAFETY STOP: the ROOT line of the applier is not unique')
    new = src.replace(old, f"ROOT = Path('{dst}')\n")
    diff = [(a, b) for a, b in zip(src.splitlines(), new.splitlines()) if a != b]
    if len(diff) != 1 or len(src.splitlines()) != len(new.splitlines()):
        raise SystemExit(f'SAFETY STOP: the applier copy differs in {len(diff)} lines')
    p = out / f'apply_entry_scratch_{dst.name}.py'
    p.write_text(new, encoding='utf-8')
    return p


def fresh(out, name):
    t = out / name
    build_tree(t)
    safety(t)
    return t, applier(t, out)


def run(cmd, log, cwd, env=None):
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, env=env or ENV)
    log.write_text(f'$ {" ".join(map(str, cmd))}\n(exit {r.returncode})\n' + r.stdout + r.stderr, encoding='utf-8')
    return r


def verify(dst, log):
    r = run([PY, '-I', '-B', dst / 'framelease_v4/protocol/registration.py', '--verify'], log, dst)
    return (r.stdout.count(': OK') == 3 and 'manifest: OK' in r.stdout), r.stdout.strip().replace('\n', ' | ')


def wrapper(t, spec, out_rel, app, log, env_extra=None):
    """apply_locked.sh on the tree; returns (exit code, stdout + stderr, apply.out)."""
    env = {**ENV, 'APPLY_ROOT': str(t), 'APPLIER': str(app), **(env_extra or {})}
    r = subprocess.run(['bash', str(WRAPPER), spec, str(t / out_rel)], cwd=t, capture_output=True, text=True, env=env)
    p = t / out_rel / 'apply.out'
    ao = p.read_text(encoding='utf-8') if p.is_file() else ''
    log.write_text(r.stdout + r.stderr + ao, encoding='utf-8')
    return r.returncode, r.stdout + r.stderr, ao


def state(t):
    return sha(t / 'framelease_v4/PROTOCOL.md'), sha(t / MAN), sha(t / f'{REG}/SEAL.sha256')


def stand_in(t):
    p = t / REREVIEW
    if (SRC / REREVIEW).is_file():
        return 'the real review file (linked)'
    p.parent.mkdir(exist_ok=True)       # the tree's build/R7B is a real directory; rereview/ does not exist in it
    if not str(p.parent.resolve()).startswith(str(t.resolve()) + '/'):
        raise SystemExit('SAFETY STOP: the stand-in would lie outside the tree')
    p.write_text('# Simulation stand-in (scratch tree only) for the review of the R7B fixes\n\n**Verdict: GO.**\n',
                 encoding='utf-8')
    return 'a stand-in in the tree'


def parse(dst, expect):
    """Problems of the parsers on the tree's PROTOCOL.md (expect: amendments that must be read exactly once)."""
    text = (dst / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    out = []
    try:
        pv = P1.protocol_view(None, text)
        view = PD.phase_view(None, text)
        later = PD.phase_view(None, PD.insert_entry(None, text, [GATE_LINE]))
    except Exception as exc:
        return [f'{type(exc).__name__}: {exc}'], {}
    for a in expect:
        if len(view['amendments'].get(a, [])) != 1:
            out.append(f'Amendment {a} read at lines {view["amendments"].get(a)}')
    s, e = view['sec']
    owners = {}
    for path in ('framelease_v4/analysis/analyze_v4.py', 'framelease_v4/analysis/verify_table1_extra.py',
                 'framelease_v4/analysis/tests/test_verify_table1_extra.py'):
        h = sha(dst / path)
        line = next((i + 1 for i in range(s, e) if h in view['lines'][i]), None)
        owners[path] = PD.citing_amendment(view, line) if line else None
    cfg = type('Cfg', (), {'analyze_code': dst / 'framelease_v4/analysis/analyze_v4.py',
                           'rel': staticmethod(lambda p: str(Path(p).relative_to(dst)))})()
    waits, _, _ = PD.analysis_registration(cfg, view)
    if set(later['entries']) != set(view['entries']) | {'p2_data'}:
        out.append(f'a later gate entry is not read: {list(later["entries"])}')
    info = {'p1_entries': list(pv['entries']), 'phase_entries': list(view['entries']),
            'amendments': {k: v for k, v in view['amendments'].items()
                           if k in ('A3', 'A4', 'A7', 'A9', 'A10', 'A11')},
            'first_citing_line_owner': owners, 'G8_analysis_registration_waits': waits,
            'phase_entries_after_a_gate': list(later['entries'])}
    return out, info


def last(text, n=1):
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    return ' / '.join(lines[-n:])[:300]


def stops_before_manifest(ao):
    return 'STOP:' in ao and 'registration --write-manifest' not in ao


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='/tmp/AMEND3/a10r7b/sim_tree')
    ap.add_argument('--cases', default='ABCDEFG')
    a = ap.parse_args()
    out = Path(a.out)
    if not str(out.resolve()).startswith('/tmp/AMEND3/'):
        raise SystemExit(f'refused: {out} is not under /tmp/AMEND3/')
    out.mkdir(parents=True, exist_ok=True)
    inj = out / 'inject.py'
    inj.write_text(INJECT, encoding='utf-8')
    results, ok = [], True

    def note(case, step, passed, detail):
        nonlocal ok
        ok = ok and passed
        results.append(f'{case} {step}: {"PASS" if passed else "FAIL"} {detail}')
        print(results[-1], flush=True)

    # ------------------------------------------------------------------------------------------------- case A
    if 'A' in a.cases:
        t, app = fresh(out, 'treeA')
        good, s = verify(t, out / 'A0_verify.log')
        note('A', '0 tree seal', good, s)
        lock = t / 'framelease_v4/.protocol.lock'
        r = run([PY, '-I', '-B', app, A10_SPEC], out / 'A1_a10_check.log', t)
        note('A', '1 A10 check', r.returncode == 0 and 'check: pre-checks passed' in r.stdout, f'exit {r.returncode}')
        r = run(['flock', '-w', '60', lock, PY, '-I', '-B', app, A10_SPEC, '--apply'], out / 'A2_a10_apply.log', t)
        newly = [ln for ln in r.stdout.splitlines() if 'newly cited manifest files' in ln]
        note('A', '2 A10 apply', r.returncode == 0 and len(newly) == 1 and newly[0].count('framelease_v4/') == 8,
             (newly or [r.stdout[-300:]])[0][:400])
        good, s = verify(t, out / 'A3_verify.log')
        note('A', '3 seal after A10', good, s)
        probs, info = parse(t, ('A3', 'A4', 'A7', 'A9', 'A10'))
        (out / 'A4_parse_after_a10.json').write_text(json.dumps(info, indent=1), encoding='utf-8')
        owner = info.get('first_citing_line_owner', {}).get('framelease_v4/analysis/analyze_v4.py')
        note('A', '4 parsers after A10', not probs and owner == 'A10' and not info['G8_analysis_registration_waits'],
             probs or f'analyze_v4.py cited by {owner}; G8 registration waits {info["G8_analysis_registration_waits"]}')
        detail = stand_in(t)
        note('A', '4b review of the R7B fixes', (t / REREVIEW).is_file(), detail)
        r = run([PY, '-I', '-B', app, A11_SPEC], out / 'A5_a11_check.log', t)
        note('A', '5 A11 check (phase baseline not refreshed after A10)',
             r.returncode == 0 and 'check: pre-checks passed' in r.stdout, f'exit {r.returncode}')
        r = run(['flock', '-w', '60', lock, PY, '-I', '-B', app, A11_SPEC, '--apply'], out / 'A6_a11_apply.log', t)
        newly = [ln for ln in r.stdout.splitlines() if 'newly cited manifest files' in ln]
        note('A', '6 A11 apply', r.returncode == 0 and len(newly) == 1 and newly[0].endswith(R7B_NEW),
             (newly or [r.stdout[-300:]])[0][:400])
        good, s = verify(t, out / 'A7_verify.log')
        note('A', '7 seal after A11', good, s)
        probs, info = parse(t, ('A3', 'A4', 'A7', 'A9', 'A10', 'A11'))
        (out / 'A8_parse_after_a11.json').write_text(json.dumps(info, indent=1), encoding='utf-8')
        own = info.get('first_citing_line_owner', {})
        note('A', '8 parsers after A11', not probs and own.get('framelease_v4/analysis/analyze_v4.py') == 'A10'
             and own.get('framelease_v4/analysis/verify_table1_extra.py') == 'A11'
             and own.get('framelease_v4/analysis/tests/test_verify_table1_extra.py') == 'A11'
             and not info['G8_analysis_registration_waits'], probs or json.dumps(own))
        shutil.copy2(t / 'framelease_v4/PROTOCOL.md', out / 'PROTOCOL.after_A10_A11.md')
        r = run(['diff', SRC / 'framelease_v4/PROTOCOL.md', t / 'framelease_v4/PROTOCOL.md'], out / 'A9_protocol.diff',
                t)
        note('A', '9 diff written', r.returncode == 1, f'{len(r.stdout.splitlines())} diff lines')

    # ------------------------------------------------------------------------------------------------- case B
    if 'B' in a.cases:
        t, app = fresh(out, 'treeB')
        before = sha(t / 'framelease_v4/PROTOCOL.md')
        r = run([PY, '-I', '-B', app, A11_SPEC], out / 'B1_a11_before_a10.log', t)
        note('B', '1 A11 before A10 stops', r.returncode == 1 and 'in-place text found 0 times' in r.stdout
             and sha(t / 'framelease_v4/PROTOCOL.md') == before, last(r.stdout)[:200])

    # ------------------------------------------------------------------------------------------------- case C
    if 'C' in a.cases:
        t, app = fresh(out, 'treeC')
        lock = t / 'framelease_v4/.protocol.lock'
        r = run(['flock', '-w', '60', lock, PY, '-I', '-B', app, A10_SPEC, '--apply'], out / 'C1_a10_apply.log', t)
        note('C', '1 A10 apply', r.returncode == 0, f'exit {r.returncode}')
        s0 = state(t)
        r = run(['flock', '-w', '60', lock, PY, '-I', '-B', app, A11_SPEC, '--apply'], out / 'C2_a11_no_review.log', t)
        good, s = verify(t, out / 'C3_verify.log')
        note('C', '2 A11 without the review file stops at the pre-check',
             r.returncode == 1 and 'placeholders without a value' in r.stdout and REREVIEW in r.stdout
             and 'registration --write-manifest' not in r.stdout and state(t) == s0 and good,
             f'exit {r.returncode}; {last(r.stdout)[:160]}; state unchanged {state(t) == s0}; seal check: {s}')

    # ------------------------------------------------------------------------------------------------- case D
    if 'D' in a.cases:
        t, app = fresh(out, 'treeD')
        rc, so, ao = wrapper(t, A10_SPEC, O10, app, out / 'D1_wrapper_a10.log')
        note('D', '1 apply_locked.sh A10', rc == 0 and 'newly cited manifest files' in ao
             and ao.count(': OK') >= 6 and (t / O10 / 'PROTOCOL.sealed.before_apply').is_file(), last(so))
        stand_in(t)
        (t / 'framelease_v4/zz_scratch_probe.txt').write_text('scratch-tree probe: a new file in the manifest scope\n',
                                                              encoding='utf-8')
        s0 = state(t)
        env = {'INJECT_APPLIER': str(app), 'INJECT_MODE': 'kill_after_manifest'}
        rc, so, ao = wrapper(t, A11_SPEC, O11, inj, out / 'D2_wrapper_a11_killed_after_manifest.log', env)
        good, s = verify(t, out / 'D3_verify.log')
        note('D', '2 killed after --write-manifest: the wrapper restores the sealed manifest',
             rc == 137 and 'inject: killed after --write-manifest' in ao and 'RESTORED the sealed manifest' in ao
             and state(t) == s0 and good, f'exit {rc}; state unchanged {state(t) == s0}; seal check: {s}')
        rc, so, ao = wrapper(t, A11_SPEC, O11, app, out / 'D4_wrapper_a11.log')
        newly = [ln for ln in ao.splitlines() if 'newly cited manifest files' in ln]
        good, s = verify(t, out / 'D5_verify.log')
        note('D', '3 A11 again: sealed', rc == 0 and len(newly) == 1 and newly[0].endswith(R7B_NEW) and good,
             f'exit {rc}; {s}')

    # ------------------------------------------------------------------------------------------------- case E
    if 'E' in a.cases:
        t, app = fresh(out, 'treeE')
        for k, (rel, how) in enumerate((('framelease_v4/analysis/commit_audit.py', 'append'),
                                        ('framelease_v4/protocol/p3_rl.py', 'append'),
                                        ('framelease_v4/arms_ext/tests/test_drift_guard.py', 'remove'),
                                        ('framelease_v4/rl/RL_PROTOCOL.md', 'remove')), 1):
            p1b = json.loads((t / 'outputs/framelease_v4/p1_driver/registered_baseline.json').read_text())['files']
            phb = json.loads((t / PHASE_BASELINE).read_text())['files']
            if how == 'append':
                with open(t / rel, 'a', encoding='utf-8') as fh:
                    fh.write('# scratch-tree probe: a registered file changed outside a transaction\n')
            else:
                (t / rel).unlink()
            s0 = state(t)
            r = run([PY, '-I', '-B', app, A10_SPEC], out / f'E{k}_check.log', t)
            rc, so, ao = wrapper(t, A10_SPEC, O10, app, out / f'E{k}_wrapper.log')
            note('E', f'{k} {how} {rel} (P1 baseline {rel in p1b}, phase baseline {rel in phb})',
                 r.returncode == 1 and rel in r.stdout and rc == 1 and stops_before_manifest(ao) and state(t) == s0,
                 f'check exit {r.returncode}, wrapper exit {rc}; {last(r.stdout)[:150]}')
            shutil.copy2(SRC / rel, t / rel)
        rc, so, ao = wrapper(t, A10_SPEC, O10, app, out / 'E5_wrapper_a10.log')
        note('E', '5 every file restored: A10 sealed', rc == 0 and verify(t, out / 'E5_verify.log')[0], last(so))

    # ------------------------------------------------------------------------------------------------- case F
    if 'F' in a.cases:
        t, app = fresh(out, 'treeF1')
        (t / 'framelease_v4/zz_scratch_probe.txt').write_text('scratch-tree probe: a new file in the manifest scope\n',
                                                              encoding='utf-8')
        man0 = sha(t / MAN)
        env = {'INJECT_APPLIER': str(app), 'INJECT_MODE': 'kill_before_seal'}
        rc, so, ao = wrapper(t, A10_SPEC, O10, inj, out / 'F1_wrapper_killed_before_seal.log', env)
        text = (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
        m = re.compile(r'Manifest and seal after this amendment: `MANIFEST\.sha256`, (\d+) files, sha256\s+'
                       r'`([0-9a-f]{64})`').search(text, max(text.find('**Amendment A10,'), 0))
        named = m.group(2) if m and '**Amendment A10,' in text else None
        note('F', '1 killed before --seal: the rewritten manifest is kept',
             rc == 137 and named is not None and sha(t / MAN) == named != man0 and 'seal it now' in ao,
             f'exit {rc}; entry names {named and named[:12]}, manifest now {sha(t / MAN)[:12]}, before {man0[:12]}')
        r = run(['flock', '-w', '60', t / 'framelease_v4/.protocol.lock', PY, '-I', '-B',
                 t / 'framelease_v4/protocol/registration.py', '--seal'], out / 'F1_hand_seal.log', t)
        good, s = verify(t, out / 'F1_verify.log')
        seal = dict(ln.split('  ', 1)[::-1] for ln in (t / f'{REG}/SEAL.sha256').read_text().splitlines())
        note('F', '1b hand seal: consistent', r.returncode == 0 and good and seal.get(MAN) == named, s)
        t, app = fresh(out, 'treeF2')
        env = {'INJECT_APPLIER': str(app), 'INJECT_MODE': 'touch_after_manifest',
               'INJECT_TARGET': str(t / 'framelease_v4/analysis/manipulation.py')}
        rc, so, ao = wrapper(t, A10_SPEC, O10, inj, out / 'F2_wrapper_touch_after_manifest.log', env)
        note('F', '2 registered file changed after --write-manifest: exit 95',
             rc == 95 and 'registration --seal -> 0' in ao and 'does not read manifest OK' in ao, last(so))

    # ------------------------------------------------------------------------------------------------- case G
    if 'G' in a.cases:
        t, app = fresh(out, 'treeG')
        r = run([PY, '-I', '-B', app, A10_SPEC], out / 'G1_check_tz_utc.log', t, env={**ENV, 'TZ': 'UTC'})
        note('G', '1 TZ=UTC: the applier alone stops', r.returncode == 1 and 'not Beijing time' in r.stdout,
             last(r.stdout)[:150])
        s0 = state(t)
        for k, rel in enumerate(('framelease_v4/.PROTOCOL.md.entrytmp', 'outputs/framelease_v4/phase_driver/'
                                 'protocol_txn.json', 'outputs/framelease_v4/phase_driver/ALERT.txt',
                                 'outputs/framelease_v4/p1_driver/protocol_txn.json',
                                 'outputs/framelease_v4/p1_driver/ALERT.txt'), 2):
            (t / rel).write_text('scratch-tree probe\n', encoding='utf-8')
            rc, so, ao = wrapper(t, A10_SPEC, O10, app, out / f'G{k}_wrapper.log')
            r = run([PY, '-I', '-B', app, A10_SPEC], out / f'G{k}_check.log', t)
            note('G', f'{k} {rel} exists: wrapper exit 96, check stops', rc == 96 and 'nothing applied' in ao
                 and r.returncode == 1 and rel.split('/')[-1] in r.stdout and state(t) == s0,
                 f'wrapper exit {rc}, check exit {r.returncode}')
            (t / rel).unlink()
        t0 = time.time()
        rc, so, ao = wrapper(t, A10_SPEC, O10, app, out / 'G7_wrapper_a10_tz_utc.log', {'TZ': 'UTC'})
        title = next((ln for ln in (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8').split('\n')
                      if ln.startswith('**Amendment A10,')), '')
        stamp = title[len('**Amendment A10, '):len('**Amendment A10, ') + 16]
        beijing = {time.strftime('%Y-%m-%d %H:%M', time.gmtime(x + 8 * 3600)) for x in (t0, t0 + 60, time.time())}
        note('G', '7 caller TZ=UTC: the wrapper stamps Beijing time', rc == 0 and stamp in beijing,
             f'exit {rc}; title {title[:60]!r}')
        stand_in(t)
        tp = t / A11_TEMPLATE
        txt = tp.read_text(encoding='utf-8')
        k0 = txt.index('* Scope.')
        for k, bad in enumerate(('* **G3 P2 data manifest** (2026-11-15 12:00, Beijing time). Probe.',
                                 '**Amendment A12, 2026-11-15 12:00 (Beijing time): probe.**',
                                 '**Phase gates (P2-P7, FULL).**',
                                 '* Probe. Each amendment gets the date and time of its entry.'), 8):
            tp.write_text(txt[:k0] + bad + '\n' + txt[k0:], encoding='utf-8')
            r = run([PY, '-I', '-B', app, A11_SPEC], out / f'G{k}_template_check.log', t)
            note('G', f'{k} template line {bad[:40]!r}: check stops', r.returncode == 1 and 'template problem' in
                 r.stdout, last(r.stdout)[:150])
        tp.write_text(txt, encoding='utf-8')
        r = run([PY, '-I', '-B', app, A11_SPEC], out / 'G12_template_restored_check.log', t)
        note('G', '12 template restored: check passes', r.returncode == 0 and 'check: pre-checks passed' in r.stdout,
             f'exit {r.returncode}')

    (out / 'summary.txt').write_text('\n'.join(results) + '\n', encoding='utf-8')
    print('ALL EXPECTED' if ok else 'SOME CASE NOT AS EXPECTED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
