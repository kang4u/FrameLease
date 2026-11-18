"""Rerun the harness of review 2 (review2/review2_sim.py) against the applier and wrapper of fix pass 2 (item a10r7b;
read only on the project and on the review directory).

  cd /home/kang/Desktop/DAC
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' \
      taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/a10r7b/rerun_review2_sim.py [CASE ...]

review2_sim.py is loaded unchanged as a module. Replaced: LOGS = a10r7b/review_rerun/review2_logs (the review's logs
stay as the reviewer left them; build() of the harness does not copy review_rerun/ into the trees); HERE = a scratch
directory whose proposed_apply_entry_stream.py and proposed_apply_locked.sh link to the files of this directory, so
case X runs on them; note() records each step; build() removes the earlier trees first (/tmp is a RAM file system).
BASE stays /tmp/A10A11/applier (the harness's helper scripts accept nothing else); it is removed at the end. The cases
A-T, C, D, Y run on the fixed applier and wrapper (the module's defaults are this directory's files). Case R reads the
copies named *.sealed.before_apply, which the fixed wrapper no longer writes, and the race of case K waits for the line
"seal it now", which it no longer prints: both are replaced by R2 and K4R below (same faults, real SIGKILL).

Expected after the fix (EXPECT): every step EXPECTED, except the steps that reproduced a defect (FINDING in the
review), which must now read UNEXPECTED (the defect is gone) and pass the positive checks on their logs listed here;
T 4.7-4.9 stop earlier (the check-mode preview) and K "4 a driver cycle" cannot start (no unsealed window). Every
step id of the review's last run of each case must occur. expectations.txt and results.txt go to LOGS. Exit 0 when
every expectation holds.
"""
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

SRC = Path('/home/kang/Desktop/DAC')
HERE = SRC / 'outputs/framelease_v4/build/AMEND2/a10r7b'
LOGS = HERE / 'review_rerun/review2_logs'
XHERE = Path('/tmp/A10A11/fix2/xhere')
BASE = Path('/tmp/A10A11/applier')
REVIEW_RESULTS = HERE / 'review2/logs/results.txt'
REC = []

# (case, step id) -> ('UNEXPECTED', [(log, [required substrings], [forbidden substrings])]) for the steps whose
# behaviour the fix changes; every other step must read EXPECTED.
NO_MANIFEST = 'registration --write-manifest'
EXPECT = {
    ('P', '2'): [('P2_check.log', ['(exit 1', 'STOP: registered files differ', 'b04_lease_s2.check.json'], []),
                 ('P3_wrapper.log', ['(exit 1', 'the manifest equals the sealed one'], [NO_MANIFEST]),
                 ('P4_driver_precheck_after.log', ['b04_lease_s2.check.json'], [])],
    ('K', '3'): [('K3_wrapper_kill9_before_seal.log', ['(exit 94', 'SEALED it with the manifest the entry names',
                                                       'inject: SIGKILL before --seal'], []),
                 ('K3_driver_g1.log', ['"result": "done"'], ['alert'])],
    ('K', '4'): [],
    ('O', '1'): [('O1_wrapper_kill9_during_manifest.log', ['(exit 137', 'apply_locked: waited',
                                                          'RESTORED the sealed manifest'], []),
                 ('O3_driver_g1.log', ['"result": "done"'], ['alert'])],
    ('L', '3'): [('L3_apply_without_wrapper_lock_held.log', ['(exit 1', 'STOP: --apply runs only under'], [])],
    ('T', '2'): [('T2_wrapper_early_clock.log', ['(exit 1', 'is earlier than the last stamp of Sec. 13.2 '
                                                 '(2026-11-15 06:43)'], [NO_MANIFEST])],
    ('T', '3'): [('T3_check_long_line.log', ['(exit 1', 'filled entry (preview) problem'], []),
                 ('T3_wrapper_long_line.log', ['(exit 1', 'filled entry (preview) problem'], [NO_MANIFEST])],
    ('T', '4.7'): [('T4_7_check.log', ['(exit 1', 'filled entry (preview) problem'], []),
                   ('T4_7_wrapper.log', ['(exit 1', 'filled entry (preview) problem'], [NO_MANIFEST])],
    ('T', '4.8'): [('T4_8_check.log', ['(exit 1', 'filled entry (preview) problem'], []),
                   ('T4_8_wrapper.log', ['(exit 1', 'filled entry (preview) problem'], [NO_MANIFEST])],
    ('T', '4.9'): [('T4_9_check.log', ['(exit 1', 'filled entry (preview) problem'], []),
                   ('T4_9_wrapper.log', ['(exit 1', 'filled entry (preview) problem'], [NO_MANIFEST])],
    ('T', '4.10'): [('T4_10_check.log', ['(exit 1', 'template problem', '### 13.2 Amendments'], []),
                    ('T4_10_wrapper.log', ['(exit 1', 'template problem'], [NO_MANIFEST])],
    ('T', '5'): [('T5_wrapper_empty_file.log', ['(exit 1', 'would register', 'zz_empty_probe',
                                                'RESTORED the sealed manifest'], [])],
    ('S', '1'): [('S1_wrapper_sigint_group.log', ['(exit 0)', 'apply_locked: exit 0'], []),
                 ('S2_driver_g1.log', ['"result": "done"'], ['alert'])],
    ('Y', '1'): [('Y1_wrapper_touch_cited_after_manifest.log', ['(exit 1', 'cited files changed after '
                                                                '--write-manifest', 'analyze_v4.py'], []),
                 ('Y2_driver_refresh.log', ['"new": []'], ['alert'])],
}
REPLACED = {('R', '1'), ('K', '4b')}          # replaced by R2 and K4R (they cannot run on the fixed wrapper)


def load():
    spec = importlib.util.spec_from_file_location('review2_sim', HERE / 'review2/review2_sim.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    if m.BASE != BASE:
        raise SystemExit(f'the harness BASE is {m.BASE}, not {BASE}')
    XHERE.mkdir(parents=True, exist_ok=True)
    for name, target in (('proposed_apply_entry_stream.py', HERE / 'apply_entry_stream.py'),
                         ('proposed_apply_locked.sh', HERE / 'apply_locked.sh')):
        link = XHERE / name
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(target)
    m.LOGS, m.HERE = LOGS, XHERE
    if m.APPLIER != HERE / 'apply_entry_stream.py' or m.WRAPPER != HERE / 'apply_locked.sh':
        raise SystemExit('the harness does not default to the files of this directory')
    build0 = m.build

    def build(name):
        for old in BASE.glob('tree*'):
            if old.is_dir() and not old.is_symlink():
                shutil.rmtree(old)
        return build0(name)

    def note(case, step, kind, detail):
        REC.append((case, step.split()[0], kind, step, detail))
        print(f'{case} {step}: {kind} {detail}'[:600], flush=True)

    m.build, m.note = build, note
    return m


def case_R2(m):
    """R after the fix: a SIGKILL before --seal (exit 94, sealed), the wrapper again (STOP), two attempt copies."""
    t = m.build('treeR2')
    app = m.scratch_applier(t)
    s0 = m.state(t)
    rc, so, ao = m.wrapper(t, m.A10_SPEC, m.O10, m.BASE / 'inject.py', LOGS / 'R2_1_wrapper_kill9_before_seal.log',
                           {'INJECT_APPLIER': str(app), 'INJECT_MODE': 'kill9_before_seal'})
    s1, sealed = m.state(t), m.sealed_now(t)
    rc2, so2, ao2 = m.wrapper(t, m.A10_SPEC, m.O10, app, LOGS / 'R2_2_wrapper_again.log')
    dirs = sorted((t / m.O10).glob('attempt_*'))
    pair = [(m.sha(d / 'PROTOCOL.md'), m.sha(d / 'MANIFEST.sha256')) for d in dirs]
    first_out = (dirs[0] / 'apply.out').read_text(encoding='utf-8') if dirs and (dirs[0] / 'apply.out').is_file() \
        else ''
    m.expect('R2', '1 after a kill before --seal (exit 94, sealed) the wrapper again stops (entry exists); each '
                   'attempt keeps its own copies', rc == 94 and sealed and rc2 == 1 and 'exists already' in ao2
             and len(dirs) == 2 and pair[0] == s0[:2] and pair[1] == s1[:2] and 'SEALED it' in first_out,
             f'exit {rc} then {rc2}; attempts {[d.name for d in dirs]}')


def case_K4R(m):
    """K4 after the fix: a driver cycle that starts while the wrapper recovers from a SIGKILL before --seal."""
    t = m.build('treeK4R')
    app = m.scratch_applier(t)
    env = {**m.ENV, 'APPLY_ROOT': str(t), 'APPLIER': str(m.BASE / 'inject.py'), 'INJECT_APPLIER': str(app),
           'INJECT_MODE': 'kill9_before_seal'}
    w = subprocess.Popen(['bash', str(m.WRAPPER), m.A10_SPEC, str(t / m.O10)], cwd=t, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, env=env)
    ao_p = t / m.O10 / 'apply.out'
    d = None
    while w.poll() is None:
        if d is None and ao_p.is_file() and 'inject: SIGKILL' in ao_p.read_text(encoding='utf-8'):
            d = subprocess.Popen([m.PY, '-I', '-B', m.BASE / 'drv.py', 'g1', t, '300'], cwd=t, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        time.sleep(0.05)
    out, err = w.communicate()
    (LOGS / 'K4R_wrapper.log').write_text(f'(exit {w.returncode})\n{out}{err}', encoding='utf-8')
    if d is None:
        m.expect('K4R', '1 race', False, 'the wrapper ended before the driver stand-in started')
        return
    dout, derr = d.communicate()
    (LOGS / 'K4R_driver_during_recovery.log').write_text(dout + derr, encoding='utf-8')
    g = json.loads(dout.strip().splitlines()[-1]) if dout.strip() else {'error': derr[-300:]}
    g2 = m.drv(t, 'g1', LOGS / 'K4R_driver_g1_next_cycle.log')
    m.expect('K4R', '1 a driver cycle during the recovery: no ALERT (it waits or finds the seal); the next cycle '
                    'passes',
             w.returncode == 94 and 'alert' not in g and 'error' not in g and g2.get('result') == 'done'
             and m.sealed_now(t), f'wrapper exit {w.returncode}; during {json.dumps(g)[:200]}; next {g2}')


def review_steps():
    """{case: {step id}} of the review's last run of each case (results.txt)."""
    runs, cur = {}, None
    for ln in REVIEW_RESULTS.read_text(encoding='utf-8').splitlines():
        if ln.startswith('# run '):
            cur = ln
            continue
        parts = ln.split(' ', 2)
        if len(parts) == 3 and len(parts[0]) == 1 and parts[0].isalpha() and parts[1] != 'done:':
            runs.setdefault(parts[0], {}).setdefault(cur, set()).add(parts[1])
    return {c: by_run[max(by_run)] for c, by_run in runs.items()}


def log_ok(name, need, never):
    p = LOGS / name
    if not p.is_file():
        return False, f'{name} missing'
    text = p.read_text(encoding='utf-8')
    miss = [s for s in need if s not in text]
    bad = [s for s in never if s in text]
    return not miss and not bad, f'{name}: missing {miss}, present {bad}' if miss or bad else f'{name}: ok'


def main():
    names = sys.argv[1:] or ['A', 'B', 'P', 'K', 'O', 'L', 'T', 'M', 'S', 'C', 'D', 'Y', 'X', 'R2', 'K4R']
    m = load()
    BASE.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    for name, text in (('inject.py', m.INJECT), ('drv.py', m.DRV), ('prober.py', m.PROBER), ('holder.py', m.HOLDER)):
        (BASE / name).write_text(text, encoding='utf-8')
    own = {'R2': case_R2, 'K4R': case_K4R}
    for n in names:
        t0 = time.time()
        if n in own:
            own[n](m)
        else:
            m.CASES[n]()
        m.note(n, 'done', 'INFO', f'{time.time() - t0:.0f} s')
    want = review_steps()
    lines, ok = [], True
    for case in [n for n in names if n not in own]:
        got = {s for c, s, _, _, _ in REC if c == case and s != 'done'}
        missing = sorted(want.get(case, set()) - got - {s for c, s in REPLACED if c == case})
        if missing:
            ok = False
            lines.append(f'{case}: FAIL steps of the review missing: {missing}')
    for case, step, kind, text, detail in REC:
        if kind == 'INFO' and not (case, step) in EXPECT:
            continue
        if (case, step) in EXPECT:
            checks = [log_ok(*c) for c in EXPECT[(case, step)]]
            good = kind == 'UNEXPECTED' and all(c[0] for c in checks)
            why = f'{kind} (the review\'s defect no longer reproduces); ' + '; '.join(c[1] for c in checks)
        else:
            good = kind == 'EXPECTED'
            why = kind
        ok = ok and good
        lines.append(f'{case} {step}: {"PASS" if good else "FAIL"} {why} | {text[:90]} | {detail[:200]}')
    (LOGS / 'expectations.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    with open(LOGS / 'results.txt', 'a', encoding='utf-8') as fh:
        fh.write(f'# run {time.strftime("%Y-%m-%d %H:%M:%S %z")} cases {names}\n'
                 + '\n'.join(f'{c} {t}: {k} {d}' for c, s, k, t, d in REC) + '\n')
    print('\n'.join(lines))
    print('ALL EXPECTED' if ok else 'SOME EXPECTATION FAILED')
    shutil.rmtree(BASE)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
