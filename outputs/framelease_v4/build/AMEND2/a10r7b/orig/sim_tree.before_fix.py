"""Dry run of Amendments A10 and A11 on scratch copies of the project tree (item a10r7b; read only on the project).

  cd /home/kang/Desktop/DAC
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' \
      taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/a10r7b/sim_tree.py [--out /tmp/AMEND3/a10r7b/sim_tree]

Every scratch tree lies under --out (refused outside /tmp/AMEND3/). A tree holds real copies of framelease_v4/ (without
__pycache__; registration.py finds its root from its own path, so the copy is its own root), of
outputs/framelease_v4/{registration,p1_driver,amendment_a10,amendment_a11}/ and of build/AMEND2/ (without step3/), a
real directory build/R7B/ whose entries link to the project's, and symbolic links (read only) for every other entry of
the project root, of outputs/ and of outputs/framelease_v4/ and build/. Never linked: the runners' queues (queue_*),
pipeline_state.json and phase_driver/. Before anything runs in a tree, every path a run writes (PROTOCOL.md, its
temporary file, the lock, registration/) is checked to resolve inside the tree.

The applier is apply_entry_stream.py (paper_tools/apply_entry.py with a streamed sha256) with one more line changed,
ROOT = the tree; the script checks that the copy differs from it in that line only. Cases:
  A  A10 check, A10 --apply (flock on the tree's lock), seal check, parsers; then A11 with a stand-in of the review
     of the R7B fixes in the tree: check, --apply, seal check, parsers (p1_driver.protocol_view,
     phase_driver.phase_view, citing_amendment, analysis_registration), a later gate entry of the phase driver.
  B  A11 before A10: the check stops (its in-place text is not in PROTOCOL.md).
  C  A10 applied, then A11 without the review file: the fill fails after write-manifest; the state is recorded
     (PROTOCOL.md unchanged, seal state).
  D  apply_locked.sh: A10 sealed through it; then a new file in the manifest scope and A11 without the review file:
     the wrapper restores the sealed manifest and the seal verifies.
Writes the logs of every step and summary.txt under --out. Exit 0 when every case gives its expected result.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path('/home/kang/Desktop/DAC')
sys.path.insert(0, str(SRC))
sys.dont_write_bytecode = True

from framelease_v4.protocol import p1_driver as P1  # noqa: E402
from framelease_v4.protocol import phase_driver as PD  # noqa: E402

HERE = SRC / 'outputs/framelease_v4/build/AMEND2/a10r7b'
PY = str(SRC / '.conda-unidrive-linux/bin/python')
APPLIER = HERE / 'apply_entry_stream.py'
A10_SPEC = 'outputs/framelease_v4/build/AMEND2/final/A10_spec.json'
A11_SPEC = 'outputs/framelease_v4/build/AMEND2/a10r7b/A11_spec.json'
REREVIEW = 'outputs/framelease_v4/build/R7B/rereview/REVIEW.md'
COPY_V4 = ('registration', 'p1_driver', 'amendment_a10', 'amendment_a11')
NEVER = ('queue_', 'pipeline_state.json', 'phase_driver')
GATE_LINE = ('* **G3 P2 data manifest** (2026-11-15 23:00, Beijing time). Simulated gate entry; manifest and seal: '
             '`MANIFEST.sha256`, 999 files, sha256 `' + 'd' * 64 + '`, sealed with this entry.')
ENV = {**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
       'OPENBLAS_NUM_THREADS': '1'}


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
    rsync(v4 / 'registration', dst / 'outputs/framelease_v4/registration')


def safety(dst):
    """Every path a run writes resolves inside the tree, and the applier copy points to the tree."""
    real = dst.resolve()
    reg = 'outputs/framelease_v4/registration'
    for rel in ('framelease_v4', 'framelease_v4/PROTOCOL.md', 'framelease_v4/.protocol.lock', reg,
                f'{reg}/MANIFEST.sha256', f'{reg}/SEAL.sha256', f'{reg}/REGISTRATION.json',
                'outputs/framelease_v4/p1_driver', 'outputs/framelease_v4/build/AMEND2',
                'outputs/framelease_v4/build/R7B'):
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
    p = out / 'apply_entry_scratch.py'
    p.write_text(new, encoding='utf-8')
    return p


def run(cmd, log, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=ENV)
    log.write_text(f'$ {" ".join(map(str, cmd))}\n(exit {r.returncode})\n' + r.stdout + r.stderr, encoding='utf-8')
    return r


def verify(dst, log):
    r = run([PY, '-I', '-B', str(dst / 'framelease_v4/protocol/registration.py'), '--verify'], log, dst)
    return (r.stdout.count(': OK') == 3 and 'FAIL' not in r.stdout), r.stdout.strip().replace('\n', ' | ')


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='/tmp/AMEND3/a10r7b/sim_tree')
    a = ap.parse_args()
    out = Path(a.out)
    if not str(out.resolve()).startswith('/tmp/AMEND3/'):
        raise SystemExit(f'refused: {out} is not under /tmp/AMEND3/')
    out.mkdir(parents=True, exist_ok=True)
    results, ok = [], True

    def note(case, step, passed, detail):
        nonlocal ok
        ok = ok and passed
        results.append(f'{case} {step}: {"PASS" if passed else "FAIL"} {detail}')
        print(results[-1], flush=True)

    # ------------------------------------------------------------------------------------------------- case A
    t = out / 'treeA'
    build_tree(t)
    safety(t)
    app = applier(t, out)
    good, s = verify(t, out / 'A0_verify.log')
    note('A', '0 tree seal', good, s)
    lock = t / 'framelease_v4/.protocol.lock'
    r = run([PY, '-I', '-B', app, A10_SPEC], out / 'A1_a10_check.log', t)
    note('A', '1 A10 check', r.returncode == 0 and 'check: pre-checks passed' in r.stdout, f'exit {r.returncode}')
    r = run(['flock', '-w', '60', lock, PY, '-I', '-B', app, A10_SPEC, '--apply'], out / 'A2_a10_apply.log', t)
    newly = [ln for ln in r.stdout.splitlines() if 'newly cited manifest files' in ln]
    note('A', '2 A10 apply', r.returncode == 0 and len(newly) == 1, (newly or [r.stdout[-300:]])[0][:400])
    good, s = verify(t, out / 'A3_verify.log')
    note('A', '3 seal after A10', good, s)
    probs, info = parse(t, ('A3', 'A4', 'A7', 'A9', 'A10'))
    (out / 'A4_parse_after_a10.json').write_text(json.dumps(info, indent=1), encoding='utf-8')
    note('A', '4 parsers after A10', not probs and info['first_citing_line_owner'].get(
        'framelease_v4/analysis/analyze_v4.py') == 'A10' and not info['G8_analysis_registration_waits'],
        probs or f'analyze_v4.py cited by {info["first_citing_line_owner"]["framelease_v4/analysis/analyze_v4.py"]};'
                  f' G8 registration waits {info["G8_analysis_registration_waits"]}')
    stand_in = t / REREVIEW
    if (SRC / REREVIEW).is_file():
        detail = 'the real review file (linked)'
    else:                                   # the tree's build/R7B is a real directory; rereview/ does not exist in it
        stand_in.parent.mkdir()
        if not str(stand_in.parent.resolve()).startswith(str(t.resolve()) + '/'):
            raise SystemExit('SAFETY STOP: the stand-in would lie outside the tree')
        stand_in.write_text('# Simulation stand-in (scratch tree only) for the review of the R7B fixes\n\n'
                            '**Verdict: GO.**\n', encoding='utf-8')
        detail = 'a stand-in in the tree'
    note('A', '4b review of the R7B fixes', stand_in.is_file(), detail)
    r = run([PY, '-I', '-B', app, A11_SPEC], out / 'A5_a11_check.log', t)
    note('A', '5 A11 check', r.returncode == 0 and 'check: pre-checks passed' in r.stdout, f'exit {r.returncode}')
    r = run(['flock', '-w', '60', lock, PY, '-I', '-B', app, A11_SPEC, '--apply'], out / 'A6_a11_apply.log', t)
    newly = [ln for ln in r.stdout.splitlines() if 'newly cited manifest files' in ln]
    want = str(['framelease_v4/analysis/tests/test_verify_table1_extra.py',
                'framelease_v4/analysis/verify_table1_extra.py'])
    note('A', '6 A11 apply', r.returncode == 0 and len(newly) == 1 and newly[0].endswith(want),
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
    r = run(['diff', SRC / 'framelease_v4/PROTOCOL.md', t / 'framelease_v4/PROTOCOL.md'], out / 'A9_protocol.diff', t)
    note('A', '9 diff written', r.returncode == 1, f'{len(r.stdout.splitlines())} diff lines')

    # ------------------------------------------------------------------------------------------------- case B
    t = out / 'treeB'
    build_tree(t)
    safety(t)
    app = applier(t, out)
    before = sha(t / 'framelease_v4/PROTOCOL.md')
    r = run([PY, '-I', '-B', app, A11_SPEC], out / 'B1_a11_before_a10.log', t)
    note('B', '1 A11 before A10 stops', r.returncode == 1 and 'in-place text found 0 times' in r.stdout
         and sha(t / 'framelease_v4/PROTOCOL.md') == before, r.stdout.strip().splitlines()[-1][:200])

    # ------------------------------------------------------------------------------------------------- case C
    t = out / 'treeC'
    build_tree(t)
    safety(t)
    app = applier(t, out)
    lock = t / 'framelease_v4/.protocol.lock'
    r = run(['flock', '-w', '60', lock, PY, '-I', '-B', app, A10_SPEC, '--apply'], out / 'C1_a10_apply.log', t)
    note('C', '1 A10 apply', r.returncode == 0, f'exit {r.returncode}')
    before = sha(t / 'framelease_v4/PROTOCOL.md')
    man_before = sha(t / 'outputs/framelease_v4/registration/MANIFEST.sha256')
    r = run(['flock', '-w', '60', lock, PY, '-I', '-B', app, A11_SPEC, '--apply'], out / 'C2_a11_no_review.log', t)
    crashed = r.returncode != 0 and 'FileNotFoundError' in r.stderr
    good, s = verify(t, out / 'C3_verify.log')
    same = sha(t / 'outputs/framelease_v4/registration/MANIFEST.sha256') == man_before
    note('C', '2 A11 without the review file fails in the fill', crashed and sha(t / 'framelease_v4/PROTOCOL.md') ==
         before, f'exit {r.returncode}; PROTOCOL.md unchanged; manifest rewritten '
                 f'{"identical" if same else "DIFFERENT"}; seal check after it: {s}')

    # ------------------------------------------------------------------------------------------------- case D
    # apply_locked.sh: A10 sealed; then a new file in the manifest scope and A11 without the review file: the applier
    # fails in the fill after write-manifest (a manifest that now differs), and the wrapper restores the sealed one.
    t = out / 'treeD'
    build_tree(t)
    safety(t)
    app = applier(t, out)
    wrap = HERE / 'apply_locked.sh'
    env = {**ENV, 'APPLY_ROOT': str(t), 'APPLIER': str(app)}
    r = subprocess.run(['bash', str(wrap), A10_SPEC, str(t / 'outputs/framelease_v4/amendment_a10')], cwd=t,
                       capture_output=True, text=True, env=env)
    log = (t / 'outputs/framelease_v4/amendment_a10/apply.out').read_text(encoding='utf-8')
    (out / 'D1_wrapper_a10.log').write_text(r.stdout + r.stderr + log, encoding='utf-8')
    note('D', '1 apply_locked.sh A10', r.returncode == 0 and log.count(': OK') >= 6,
         r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:])
    probe = t / 'framelease_v4/zz_scratch_probe.txt'
    probe.write_text('scratch-tree probe: a new file in the manifest scope\n', encoding='utf-8')
    before = sha(t / 'framelease_v4/PROTOCOL.md')
    sealed = sha(t / 'outputs/framelease_v4/registration/MANIFEST.sha256')
    r = subprocess.run(['bash', str(wrap), A11_SPEC, str(t / 'outputs/framelease_v4/amendment_a11')], cwd=t,
                       capture_output=True, text=True, env=env)
    log = (t / 'outputs/framelease_v4/amendment_a11/apply.out').read_text(encoding='utf-8')
    (out / 'D2_wrapper_a11_no_review.log').write_text(r.stdout + r.stderr + log, encoding='utf-8')
    good, s = verify(t, out / 'D3_verify.log')
    note('D', '2 apply_locked.sh restores the sealed manifest',
         r.returncode == 1 and 'RESTORED the sealed manifest' in log
         and sha(t / 'outputs/framelease_v4/registration/MANIFEST.sha256') == sealed and good
         and sha(t / 'framelease_v4/PROTOCOL.md') == before, f'exit {r.returncode}; seal check: {s}')
    (out / 'summary.txt').write_text('\n'.join(results) + '\n', encoding='utf-8')
    print('ALL EXPECTED' if ok else 'SOME CASE NOT AS EXPECTED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
