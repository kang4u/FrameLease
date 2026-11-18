"""Re-check harness (review 2, round 2) of the fixed applier and wrapper of item a10r7b on scratch trees under
/tmp/A10A11/recheck1/own/ (one tree at a time, removed at the end). Read only on the project. The tree builder, the
scratch applier (ROOT line only) and the driver helper come from a10r7b/sim_tree.py, loaded unchanged as a module; the
wrapper is the reviewed apply_locked.sh (APPLY_ROOT / APPLIER). holder2.py stands in for a driver that wants the lock
during every run and records, at each acquisition, whether the seal matched. inject2.py injects the faults.

  recheck_sim.py [CASE ...]      cases: E KS OS OM SG KI CK WD IP TL LK RF
"""
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

SRC = Path('/home/kang/Desktop/DAC')
HERE = SRC / 'outputs/framelease_v4/build/AMEND2/a10r7b'
BASE = Path('/tmp/A10A11/recheck1')
OUT = BASE / 'own'
INJ, HOLD = BASE / 'inject2.py', BASE / 'holder2.py'
_s = importlib.util.spec_from_file_location('sim_tree', HERE / 'sim_tree.py')
ST = importlib.util.module_from_spec(_s)
_s.loader.exec_module(ST)
PY, WRAPPER = ST.PY, HERE / 'apply_locked.sh'
A10_SPEC, A11_SPEC, O10, O11, MAN, REG = ST.A10_SPEC, ST.A11_SPEC, ST.O10, ST.O11, ST.MAN, ST.REG
A10_TMPL = 'outputs/framelease_v4/build/AMEND2/final/A10_entry.md'
ENV = dict(ST.ENV)
RES = []


def note(case, step, ok, detail):
    RES.append(f'{case} {step}: {"PASS" if ok else "FAIL"} {detail}')
    print(RES[-1][:900], flush=True)


def inside(t, rel):
    p = t / rel
    if p.is_symlink() or not str(p.resolve()).startswith(str(t.resolve()) + '/'):
        raise SystemExit(f'SAFETY STOP: {p} does not resolve inside the tree')
    return p


def closing(ao):
    return [ln for ln in ao.splitlines() if ln.startswith('apply_locked:')]


def sealed(t):
    seal = dict(ln.split('  ', 1)[::-1] for ln in (t / f'{REG}/SEAL.sha256').read_text().splitlines())
    return seal.get('framelease_v4/PROTOCOL.md') == ST.sha(t / 'framelease_v4/PROTOCOL.md') and \
        seal.get(MAN) == ST.sha(t / MAN)


def holder_start(t, tag):
    stop = OUT / f'{tag}.holder_stop'
    stop.unlink(missing_ok=True)
    hj = OUT / f'{tag}_holder.json'
    hp = subprocess.Popen([PY, '-I', '-B', str(HOLD), str(t), str(stop), str(hj)], cwd=t, env=ENV)
    time.sleep(0.5)
    return hp, stop, hj


def holder_end(hp, stop, hj):
    time.sleep(0.6)
    stop.write_text('stop\n')
    hp.wait(timeout=120)
    stop.unlink()
    recs = json.loads(hj.read_text())
    bad = [r for r in recs if not r['consistent']]
    return recs, bad


def hsum(recs, bad):
    longest = max((r['wait_s'] for r in recs), default=0)
    return f'holder: {len(recs)} acquisitions, {len(bad)} with a seal mismatch, longest wait {longest:.1f} s'


def wrap(t, spec, out_rel, log, app=None, mode=None, extra=None, during=None, tag='w', timed=True):
    """apply_locked.sh on the tree with the holder running; app: the scratch applier, mode: an inject2 mode.
    Returns (exit, stdout+stderr, apply.out, holder records, holder mismatches, max RSS kB)."""
    env = {**ENV, 'APPLY_ROOT': str(t), 'APPLIER': str(INJ if mode else app)}
    if mode:
        env.update({'INJECT_APPLIER': str(app), 'INJECT_MODE': mode})
    env.update(extra or {})
    hp, stop, hj = holder_start(t, tag)
    tf = OUT / f'{tag}.time'
    cmd = (['/usr/bin/time', '-v', '-o', str(tf)] if timed else []) + ['bash', str(WRAPPER), spec, str(t / out_rel)]
    t0 = time.time()
    w = subprocess.Popen(cmd, cwd=t, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    info = {}
    if during:
        info = during(t, w, out_rel) or {}
    so, _ = w.communicate()
    t1 = time.time()
    recs, bad = holder_end(hp, stop, hj)
    p = t / out_rel / 'apply.out'
    ao = p.read_text(encoding='utf-8') if p.is_file() else ''
    rss = None
    if timed and tf.is_file():
        m = re.search(r'Maximum resident set size \(kbytes\): (\d+)', tf.read_text())
        rss = int(m.group(1)) if m else None
    log.write_text(f'(exit {w.returncode}, {t1 - t0:.1f} s, max RSS {rss} kB)\n{so}\n--- apply.out\n{ao}\n--- holder\n'
                   + json.dumps(recs) + '\n' + json.dumps(info) + '\n', encoding='utf-8')
    return w.returncode, so, ao, recs, bad, rss, t0, t1, info


def detached(t, spec, out_rel, log, app, mode=None, during=None, tag='d'):
    """The RUNBOOK form: setsid nohup bash apply_locked.sh SPEC OUTDIR > console.txt 2>&1 < /dev/null &."""
    env = {**ENV, 'APPLY_ROOT': str(t), 'APPLIER': str(INJ if mode else app)}
    if mode:
        env.update({'INJECT_APPLIER': str(app), 'INJECT_MODE': mode})
    od = inside(t, out_rel)
    console = od / 'console.txt'
    console.unlink(missing_ok=True)
    hp, stop, hj = holder_start(t, tag)
    t0 = time.time()
    subprocess.run(f'setsid nohup bash {WRAPPER} {spec} {od} > {console} 2>&1 < /dev/null &', shell=True, cwd=t,
                   env=env, check=True)
    info = {}
    if during:
        info = during(t, None, out_rel) or {}
    while not (console.is_file() and 'apply_locked: exit' in console.read_text()):
        if time.time() - t0 > 900:
            break
        time.sleep(0.2)
    t1 = time.time()
    recs, bad = holder_end(hp, stop, hj)
    co = console.read_text() if console.is_file() else ''
    ao = (od / 'apply.out').read_text(encoding='utf-8') if (od / 'apply.out').is_file() else ''
    m = re.search(r'apply_locked: exit (\d+)', co)
    rc = int(m.group(1)) if m else None
    log.write_text(f'(console exit {rc}, {t1 - t0:.1f} s)\n--- console.txt\n{co}\n--- apply.out\n{ao}\n--- holder\n'
                   + json.dumps(recs) + '\n' + json.dumps(info) + '\n', encoding='utf-8')
    return rc, co, ao, recs, bad, t0, t1, info


def wait_for(path, marker, limit=120):
    t0 = time.time()
    while time.time() - t0 < limit:
        if path.is_file() and marker in path.read_text(encoding='utf-8', errors='replace'):
            return True
        time.sleep(0.02)
    return False


def procs():
    """{pid: (ppid, pgid, args)} of every process."""
    out = {}
    for d in Path('/proc').iterdir():
        if not d.name.isdigit():
            continue
        try:
            st = (d / 'stat').read_text()
            rest = st[st.rindex(')') + 2:].split()
            args = (d / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
            out[int(d.name)] = (int(rest[1]), int(rest[2]), args)
        except (OSError, ValueError):
            continue
    return out


def run(cmd, log, cwd, env=None):
    t0 = time.time()
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, env=env or ENV)
    log.write_text(f'$ {" ".join(map(str, cmd))}\n(exit {r.returncode}, {time.time() - t0:.1f} s)\n' + r.stdout
                   + r.stderr, encoding='utf-8')
    return r


def check(t, app, spec, log, mode=None, extra=None):
    env = {**ENV}
    if mode:
        env.update({'INJECT_APPLIER': str(app), 'INJECT_MODE': mode, **(extra or {})})
        return run([PY, '-I', '-B', INJ, spec], log, t, env)
    return run([PY, '-I', '-B', app, spec], log, t, env)


def post(t, name, log):
    r = run([PY, '-I', '-B', HERE / 'post_check.py', name, '--root', t], log, SRC)
    return r.returncode, r.stdout + r.stderr


def probe_spec(t, name, tmpl_text=None, inplace=None):
    """A copy of the tree's A10 spec (and template) under a probe name inside the tree's build/AMEND2/final/."""
    base = json.loads(inside(t, A10_SPEC).read_text(encoding='utf-8'))
    if tmpl_text is not None:
        rel = f'outputs/framelease_v4/build/AMEND2/final/{name}_entry.md'
        inside(t, 'outputs/framelease_v4/build/AMEND2/final')
        (t / rel).write_text(tmpl_text, encoding='utf-8')
        base['template'] = rel
    if inplace is not None:
        base['inplace'] = inplace
    rel = f'outputs/framelease_v4/build/AMEND2/final/{name}_spec.json'
    (t / rel).write_text(json.dumps(base, indent=1), encoding='utf-8')
    return rel


def tmpl_with(t, line, before='* Change: the files'):
    txt = inside(t, A10_TMPL).read_text(encoding='utf-8')
    if txt.count(before) != 1:
        raise SystemExit('probe anchor not unique in the template')
    return txt.replace(before, line + '\n' + before, 1)


# ----------------------------------------------------------------------------------------------------------- cases
def case_E():
    t, app = ST.fresh(OUT, 'treeE')
    s0 = ST.state(t)
    rc, so, ao, recs, bad, rss, t0, t1, _ = wrap(t, A10_SPEC, O10, OUT / 'E1_wrapper_a10.log', app, tag='E1')
    newly = [ln for ln in ao.splitlines() if 'newly cited manifest files' in ln]
    good = ST.verify(t, OUT / 'E1_verify.log')[0]
    note('E', '1 A10 through the wrapper with a lock-wanting stand-in driver running', rc == 0 and len(newly) == 1
         and newly[0].count('framelease_v4/') == 8 and good and not bad and len(recs) >= 2
         and any(r['A10'] for r in recs) and any(not r['A10'] for r in recs),
         f'exit {rc}, {t1 - t0:.1f} s, max RSS {rss} kB; {hsum(recs, bad)}; seal/verify {good}')
    rcp, outp = post(t, 'A10', OUT / 'E2_post_check_a10.log')
    g = ST.drv(OUT, t, 'refresh', OUT / 'E3_driver_refresh.log')
    rcp2, outp2 = post(t, 'A10', OUT / 'E4_post_check_a10_after_refresh.log')
    g1 = ST.drv(OUT, t, 'g1', OUT / 'E5_driver_g1.log')
    note('E', '2 post_check A10 3 -> driver refresh (+8 A10 files) -> 0; gate_g1 done', rcp == 3
         and (g.get('result') or {}).get('new') == ST.A10_FILES and rcp2 == 0 and g1.get('result') == 'done',
         f'post_check {rcp} -> {rcp2}; refresh new {len((g.get("result") or {}).get("new", []))}; g1 {g1}')
    probs, info = ST.parse(t, ('A3', 'A4', 'A7', 'A9', 'A10'))
    (OUT / 'E6_parse_after_a10.json').write_text(json.dumps(info, indent=1), encoding='utf-8')
    note('E', '3 parsers: analyze_v4.py first cited by A10 (citing_amendment), G8 analysis_registration no wait',
         not probs and info['first_citing_line_owner'].get('framelease_v4/analysis/analyze_v4.py') == 'A10'
         and not info['G8_analysis_registration_waits'], probs or json.dumps(info['first_citing_line_owner']))
    ST.stand_in(t)
    rc, so, ao, recs, bad, rss2, t0, t1, _ = wrap(t, A11_SPEC, O11, OUT / 'E7_wrapper_a11.log', app, tag='E7')
    newly = [ln for ln in ao.splitlines() if 'newly cited manifest files' in ln]
    rcp, outp = post(t, 'A11', OUT / 'E8_post_check_a11.log')
    g = ST.drv(OUT, t, 'refresh', OUT / 'E9_driver_refresh.log')
    rcp2, outp2 = post(t, 'A11', OUT / 'E10_post_check_a11_after_refresh.log')
    note('E', '4 A11 through the wrapper; post_check A11 3 -> refresh (+2) -> 0', rc == 0 and len(newly) == 1
         and newly[0].endswith(ST.R7B_NEW) and not bad and rcp == 3 and rcp2 == 0
         and len((g.get('result') or {}).get('new', [])) == 2,
         f'exit {rc}, max RSS {rss2} kB; {hsum(recs, bad)}; post_check {rcp} -> {rcp2}; refresh {g.get("result")}')
    shutil.copy2(t / 'framelease_v4/PROTOCOL.md', OUT / 'E_PROTOCOL.after_A10_A11.md.txt')
    note('E', '0 state before', True, f'PROTOCOL {s0[0][:12]} MANIFEST {s0[1][:12]} SEAL {s0[2][:12]}')


def case_KS():
    t, app = ST.fresh(OUT, 'treeKS')
    rc, so, ao, recs, bad, rss, t0, t1, _ = wrap(t, A10_SPEC, O10, OUT / 'KS_wrapper_kill9_after_seal.log', app,
                                                 'kill_after_seal', tag='KS')
    note('KS', '1 SIGKILL right after --seal: exit 94 "the seal matches", sealed, verify OK, holder never mismatched',
         rc == 94 and 'the seal matches' in ao and sealed(t) and ST.verify(t, OUT / 'KS_verify.log')[0] and not bad,
         f'exit {rc}; {closing(ao)[-2:]}; {hsum(recs, bad)}')


def case_OS():
    t, app = ST.fresh(OUT, 'treeOS')
    rc, so, ao, recs, bad, rss, t0, t1, _ = wrap(t, A10_SPEC, O10, OUT / 'OS_wrapper_orphan_slow_seal.log', app,
                                                 'slow_seal_kill', tag='OS')
    m = re.search(r'waited (\d+) s', ao)
    g1 = ST.drv(OUT, t, 'g1', OUT / 'OS_driver_g1.log')
    note('OS', '1 SIGKILL while the --seal child starts late: the wrapper waits for it, exit 94, sealed, g1 done',
         rc == 94 and m is not None and int(m.group(1)) >= 2 and 'the seal matches' in ao and sealed(t) and not bad
         and g1.get('result') == 'done', f'exit {rc}; {closing(ao)[-3:]}; {hsum(recs, bad)}; g1 {g1}')


def case_OM():
    t, app = ST.fresh(OUT, 'treeOM')
    inside(t, 'framelease_v4').joinpath('zz_scratch_probe.txt').write_text('scratch: a new file in scope\n')
    s0 = ST.state(t)
    rc, co, ao, recs, bad, t0, t1, _ = detached(t, A10_SPEC, O10, OUT / 'OM_detached_orphan_slow_manifest.log', app,
                                                'slow_manifest_kill', tag='OM')
    m = re.search(r'waited (\d+) s', ao)
    note('OM', '1 RUNBOOK form (setsid nohup, detached); SIGKILL while --write-manifest starts late: waited, RESTORED, '
               'exit 137, state of before, holder never mismatched',
         rc == 137 and m is not None and int(m.group(1)) >= 2 and 'RESTORED the sealed manifest' in ao
         and ST.state(t) == s0 and not bad, f'exit {rc}; {closing(ao)[-3:]}; {hsum(recs, bad)}')


def case_SG():
    t, app = ST.fresh(OUT, 'treeSG')
    sent = {}

    def during(t_, w, out_rel):
        ao = t_ / out_rel / 'apply.out'
        if not wait_for(ao, 'manifest difference'):
            return {'error': 'no manifest difference line'}
        pr = procs()
        top = [p for p, (pp, pg, a) in pr.items() if str(WRAPPER) in a and str(t_) in a and a.startswith('bash ')]
        if not top:
            return {'error': 'wrapper not found'}
        pg = pr[top[0]][1]
        members = sorted(p for p, v in pr.items() if v[1] == pg)
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            os.killpg(pg, sig)
            time.sleep(0.05)
        sent.update({'pgid': pg, 'wrapper_pid': top[0], 'group': len(members), 'session_leader': pg == top[0]})
        return sent

    rc, co, ao, recs, bad, t0, t1, info = detached(t, A10_SPEC, O10, OUT / 'SG_detached_signals.log', app,
                                                   during=during, tag='SG')
    note('SG', '1 RUNBOOK form; SIGINT, SIGTERM, SIGHUP to the whole process group after --write-manifest: ignored, '
               'exit 0, sealed', rc == 0 and sealed(t) and not bad and info.get('session_leader') is True
         and 'apply_locked: exit 0' in co, f'exit {rc}; signals {info}; {hsum(recs, bad)}')


def case_KI():
    t, app = ST.fresh(OUT, 'treeKI')
    s0 = ST.state(t)

    def during(t_, w, out_rel):
        ao = t_ / out_rel / 'apply.out'
        if not wait_for(ao, 'manifest difference'):
            return {'error': 'no manifest difference line'}
        pr = procs()
        top = [p for p, (pp, pg, a) in pr.items() if str(WRAPPER) in a and str(t_) in a and a.startswith('bash ')]
        fl = [p for p, (pp, pg, a) in pr.items() if top and pp == top[0] and a.startswith('flock ')]
        inner = [p for p, (pp, pg, a) in pr.items() if fl and pp == fl[0] and a.startswith('bash -c')]
        app_p = [p for p, (pp, pg, a) in pr.items() if inner and pp == inner[0]]
        if not inner:
            return {'error': f'inner shell not found {top} {fl}'}
        os.kill(inner[0], signal.SIGKILL)
        tk = time.time()
        while app_p and Path(f'/proc/{app_p[0]}').exists():
            try:
                if Path(f'/proc/{app_p[0]}/stat').read_text().split(') ')[1][0] == 'Z':
                    break
            except OSError:
                break
            time.sleep(0.01)
        return {'killed_inner': inner[0], 't_kill': tk, 'applier': app_p, 't_applier_end': time.time()}

    rc, so, ao, recs, bad, rss, t0, t1, info = wrap(t, A10_SPEC, O10, OUT / 'KI_wrapper_inner_shell_killed.log', app,
                                                    during=during, tag='KI', timed=False)
    time.sleep(3)
    ao = (t / O10 / 'apply.out').read_text(encoding='utf-8')
    after = [r for r in recs if r['t_acq'] >= info.get('t_kill', 1e18)]
    first = after[0]['t_acq'] if after else None
    note('KI', '1 observation: SIGKILL of the inner shell only: the outer wrapper prints its exit line while the applier '
               'keeps the lock descriptor and finishes; no closing apply_locked line in apply.out',
         True, f'outer exit {rc} ({so.strip()[-80:]!r}); applier end {info.get("t_applier_end", 0) - t0:.1f} s, '
               f'first holder acquisition after the kill at {(first or 0) - t0:.1f} s; sealed {sealed(t)}, A10 in '
               f'PROTOCOL.md {"**Amendment A10," in (t / "framelease_v4/PROTOCOL.md").read_text()}; closing lines '
               f'{closing(ao)}; {hsum(recs, bad)}; state changed {ST.state(t) != s0}')


def case_CK():
    t, app = ST.fresh(OUT, 'treeCK')
    s0 = ST.state(t)
    r = check(t, app, A10_SPEC, OUT / 'CK1_check_clock_0630.log', 'clock', {'INJECT_CLOCK': '2026-11-15 06:30'})
    note('CK', '1 check mode, clock 06:30', r.returncode == 1 and 'earlier than the last stamp of Sec. 13.2 '
         '(2026-11-15 06:43)' in r.stdout, r.stdout.strip().splitlines()[-1][:160])
    rc, so, ao, recs, bad, *_ = wrap(t, A10_SPEC, O10, OUT / 'CK2_wrapper_clock_0630.log', app, 'clock',
                                     {'INJECT_CLOCK': '2026-11-15 06:30'}, tag='CK2', timed=False)
    note('CK', '2 wrapper, clock 06:30: STOP before --write-manifest, state unchanged', rc == 1 and 'earlier than'
         in ao and 'registration --write-manifest' not in ao and ST.state(t) == s0 and not bad, f'exit {rc}')
    rc, so, ao, recs, bad, *_ = wrap(t, A10_SPEC, O10, OUT / 'CK3_wrapper_clock_back_at_fill.log', app, 'clock',
                                     {'INJECT_CLOCK': '2026-11-15 06:30', 'INJECT_CLOCK_FROM': '2'}, tag='CK3',
                                     timed=False)
    note('CK', '3 wrapper, the clock set back between the pre-check and the fill: STOP after --write-manifest, '
               'PROTOCOL.md unchanged, state of before', rc == 1 and 'earlier than' in ao
         and 'registration --write-manifest' in ao and 'PROTOCOL.md unchanged' in ao and ST.state(t) == s0
         and not bad, f'exit {rc}; {closing(ao)[-2:]}')
    rc, so, ao, recs, bad, *_ = wrap(t, A10_SPEC, O10, OUT / 'CK4_wrapper_clock_equal_last.log', app, 'clock',
                                     {'INJECT_CLOCK': '2026-11-15 06:43'}, tag='CK4', timed=False)
    title = next((ln for ln in (t / 'framelease_v4/PROTOCOL.md').read_text().split('\n')
                  if ln.startswith('**Amendment A10,')), '')
    note('CK', '4 wrapper, clock equal to the last stamp (06:43): sealed with that stamp', rc == 0
         and title.startswith('**Amendment A10, 2026-11-15 06:43 ') and sealed(t), f'exit {rc}; {title[:50]!r}')
    t, app = ST.fresh(OUT, 'treeCK5')
    p = inside(t, 'framelease_v4/PROTOCOL.md')
    line = ('* **G3 P2 data manifest** (2026-11-16 00:30, Beijing time). Simulated gate entry; manifest and seal: '
            '`MANIFEST.sha256`, 221 files, sha256 `' + ST.sha(t / MAN) + '`, sealed with this entry.')
    p.write_text(ST.PD.insert_entry(None, p.read_text(encoding='utf-8'), [line]), encoding='utf-8')
    rs = run([PY, '-I', '-B', t / 'framelease_v4/protocol/registration.py', '--seal'], OUT / 'CK5_reseal.log', t)
    r = check(t, app, A10_SPEC, OUT / 'CK5_check_after_later_gate_entry.log')
    note('CK', '5 a later phase-driver entry (2026-11-16 00:30) in Sec. 13.2: check mode stops on the real clock',
         rs.returncode == 0 and r.returncode == 1 and '(2026-11-16 00:30)' in r.stdout,
         r.stdout.strip().splitlines()[-1][:160])


def case_WD():
    t, app = ST.fresh(OUT, 'treeWD')
    s0 = ST.state(t)
    filler = 'Width probe of the scratch tree, prose that the reviewers fill to an exact number of columns here'

    def line(n, prefix='* '):
        s = (prefix + filler + ' x' * 100)[:n]
        return s[:-1] + 'y' if s.endswith(' ') else s

    l120, l121 = line(120), line(121)
    assert len(l120) == 120 and len(l121) == 121, (len(l120), len(l121))
    row = '| ' + 'w' * 146 + ' |'
    ph = '* Probe cites `{{sha256:framelease_v4/analysis/analyze_v4.py}}` '
    l104 = ph + 'y' * (104 - len(ph))
    cases = [('1 prose line of 120 columns: passes', l120, 0, 'check: pre-checks passed'),
             ('2 prose line of 121 columns: template STOP', l121, 1, 'template problem'),
             ('3 table row of 150 columns: passes', row, 0, 'check: pre-checks passed'),
             ('4 placeholder line, 104 columns, 121 filled: preview STOP in check mode', l104, 1,
              'filled entry (preview) problem')]
    for k, (what, ln, want_rc, want) in enumerate(cases, 1):
        spec = probe_spec(t, f'WD{k}', tmpl_with(t, ln))
        r = check(t, app, spec, OUT / f'WD{k}_check.log')
        note('WD', what, r.returncode == want_rc and want in r.stdout and ST.state(t) == s0,
             f'line {len(ln)} cols, exit {r.returncode}: {r.stdout.strip().splitlines()[-1][:120]}')
    spec = probe_spec(t, 'WD4w', tmpl_with(t, l104))
    rc, so, ao, recs, bad, *_ = wrap(t, spec, O10, OUT / 'WD4w_wrapper.log', app, tag='WD4w', timed=False)
    note('WD', '4w the same through the wrapper: STOP before --write-manifest', rc == 1 and 'filled entry (preview)'
         in ao and 'registration --write-manifest' not in ao and ST.state(t) == s0, f'exit {rc}')
    inplace = json.loads(inside(t, A10_SPEC).read_text(encoding='utf-8'))['inplace']
    wide = [dict(r) for r in inplace]
    wide[0]['new'] = wide[0]['new'].rstrip('\n') + '\n' + 'z' * 121 + '\n'
    spec = probe_spec(t, 'WD5', inplace=wide)
    r = check(t, app, spec, OUT / 'WD5_check_inplace_121.log')
    note('WD', '5 an in-place "new" with a changed line of 121 columns: STOP', r.returncode == 1 and 'in-place problem'
         in r.stdout, r.stdout.strip().splitlines()[-1][:140])
    wide[0]['new'] = inplace[0]['new'].rstrip('\n') + '\n' + 'z' * 120 + '\n'
    spec = probe_spec(t, 'WD6', inplace=wide)
    r = check(t, app, spec, OUT / 'WD6_check_inplace_120.log')
    note('WD', '6 an in-place "new" with a changed line of 120 columns: passes', r.returncode == 0,
         r.stdout.strip().splitlines()[-1][:140])
    # an in-place text that starts in the middle of a line: the line it produces is the rest of that line + "new"
    text = (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    s13 = text.index('### 13.2 Amendments')
    pick = None
    for ln in text[:s13].split('\n'):
        if 105 <= len(ln) <= 120 and not ln.lstrip().startswith('|') and text.count(ln[-30:] + '\n') == 1:
            pick = ln
            break
    old = pick[-30:] + '\n'
    new = pick[-30:] + ' with a probe clause of 24\n'
    spec = probe_spec(t, 'WD7', inplace=inplace + [{'old': old, 'new': new}])
    r = check(t, app, spec, OUT / 'WD7_check_inplace_midline.log')
    produced = len(pick) + len(new) - len(old)
    note('WD', '7 FINDING CHECK: an in-place text that starts mid-line and produces a line of more than 120 columns '
               '(PASS = the applier stops it)', r.returncode == 1 and 'in-place problem' in r.stdout,
         f'produced line {produced} columns, "new" fragment {len(new) - 1} columns; check exit {r.returncode}: '
         f'{r.stdout.strip().splitlines()[-1][:100]}')


def case_IP():
    t, app = ST.fresh(OUT, 'treeIP')
    s0 = ST.state(t)
    text = (t / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    twice = next((ln for ln in text.split('\n') if len(ln) > 20 and text.count(ln + '\n') == 2), None)
    if twice is None:
        note('IP', '1 harness', False, 'no line occurs exactly twice in PROTOCOL.md')
        return
    inplace = json.loads(inside(t, A10_SPEC).read_text(encoding='utf-8'))['inplace']
    spec = probe_spec(t, 'IP1', inplace=[{'old': twice + '\n', 'new': twice + ' (probe)\n'}] + inplace)
    r = check(t, app, spec, OUT / 'IP1_check_old_twice.log')
    rc, so, ao, recs, bad, *_ = wrap(t, spec, O10, OUT / 'IP1_wrapper_old_twice.log', app, tag='IP1', timed=False)
    note('IP', '1 an in-place "old" found twice: check and wrapper STOP before --write-manifest', r.returncode == 1
         and 'in-place text found 2 times' in r.stdout and rc == 1 and 'registration --write-manifest' not in ao
         and ST.state(t) == s0, f'check exit {r.returncode}, wrapper exit {rc}; {twice[:60]!r}')
    seq = [dict(x) for x in inplace]
    seq[0]['new'] = seq[0]['new'] + seq[1]['old']
    spec = probe_spec(t, 'IP2', inplace=seq)
    r = check(t, app, spec, OUT / 'IP2_check_sequential.log')
    note('IP', '2 the first in-place "new" repeats the second "old": counted after the first replacement, STOP',
         r.returncode == 1 and 'in-place text found 2 times' in r.stdout, r.stdout.strip().splitlines()[-1][:140])


def case_TL():
    t, app = ST.fresh(OUT, 'treeTL')
    for k, ln in enumerate(('* **D1 summary**, 2026-11-15 12:00 (probe of the P1 driver entry form).',
                            '* **G4 RL freeze** (2026-11-15 12:00, probe of the phase driver entry form).',
                            '**Amendment A12: probe of the amendment title form.**',
                            '**Amendment A12, 2026-11-15 12:00 (Beijing time): probe.**',
                            '### 13.2 Amendments',
                            '**Stage selections (P1, FULL).**'), 1):
        spec = probe_spec(t, f'TL{k}', tmpl_with(t, ln))
        r = check(t, app, spec, OUT / f'TL{k}_check.log')
        pv = ST.P1.ENTRY_RE.match(ln) is not None
        ph = ST.PD.ENTRY_RE.match(ln) is not None or ST.PD.AMEND_RE.match(ln) is not None
        note('TL', f'{k} template line {ln[:44]!r} (p1 ENTRY_RE {pv}, phase ENTRY_RE/AMEND_RE {ph}): STOP',
             r.returncode == 1 and 'template problem' in r.stdout, r.stdout.strip().splitlines()[-1][:120])


def case_LK():
    t, app = ST.fresh(OUT, 'treeLK')
    s0 = ST.state(t)
    lock = t / 'framelease_v4/.protocol.lock'
    h = subprocess.Popen(['flock', '-o', str(lock), 'sleep', '40'], cwd=t)
    time.sleep(0.5)
    r = run([PY, '-I', '-B', app, A10_SPEC, '--apply'], OUT / 'LK1_apply_lock_held_elsewhere.log', t)
    r2 = run(['bash', '-c', f'exec 9<{lock}; flock -n 9 || echo busy; {PY} -I -B {app} {A10_SPEC} --apply'],
             OUT / 'LK2_apply_with_own_unlocked_fd_while_held.log', t)
    h.kill()
    h.wait()
    note('LK', '1 --apply run directly while another process holds the lock: STOP, nothing written',
         r.returncode == 1 and 'runs only under' in r.stdout and r2.returncode == 1 and 'runs only under' in r2.stdout
         and ST.state(t) == s0, f'exit {r.returncode} / {r2.returncode}')
    r = run(['flock', '-w', '60', lock, PY, '-I', '-B', app, A10_SPEC, '--apply'], OUT / 'LK3_apply_under_flock.log', t)
    note('LK', '2 --apply under flock(1): sealed', r.returncode == 0 and sealed(t), f'exit {r.returncode}')


def case_RF():
    """Registered files around the manifest: changed before --write-manifest (STOP, restored) and after it (exit 95)."""
    t, app = ST.fresh(OUT, 'treeRF')
    s0 = ST.state(t)
    rel = 'framelease_v4/analysis/manipulation.py'
    tgt = inside(t, rel)
    rc, so, ao, recs, bad, *_ = wrap(t, A10_SPEC, O10, OUT / 'RF1_wrapper_touch_before_manifest.log', app,
                                     'touch_before_manifest', {'INJECT_TARGET': str(tgt)}, tag='RF1', timed=False)
    note('RF', '1 a registered file (manipulation.py, cited by A3) changed right before --write-manifest: STOP, '
               'sealed manifest restored, PROTOCOL.md unchanged', rc == 1 and 'registered files changed or left the '
         'new manifest' in ao and 'RESTORED the sealed manifest' in ao and ST.state(t) == s0 and not bad,
         f'exit {rc}; {closing(ao)[-2:]}')
    shutil.copy2(SRC / rel, tgt)
    rc, so, ao, recs, bad, *_ = wrap(t, A10_SPEC, O10, OUT / 'RF2_wrapper_touch_after_manifest.log', app,
                                     'touch_after_manifest', {'INJECT_TARGET': str(tgt)}, tag='RF2', timed=False)
    note('RF', '2 the same file changed right after --write-manifest: sealed, exit 95 (verification names it)',
         rc == 95 and sealed(t) and 'manipulation.py' in ao.split('--- apply.out')[-1].split('sealed:')[-1]
         and not bad, f'exit {rc}; {closing(ao)[-1:]}')


CASES = {'E': case_E, 'KS': case_KS, 'OS': case_OS, 'OM': case_OM, 'SG': case_SG, 'KI': case_KI, 'CK': case_CK,
         'WD': case_WD, 'IP': case_IP, 'TL': case_TL, 'LK': case_LK, 'RF': case_RF}


def main():
    names = sys.argv[1:] or list(CASES)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'drv.py').write_text(ST.DRV, encoding='utf-8')
    for n in names:
        t0 = time.time()
        try:
            CASES[n]()
        except Exception as exc:  # noqa: BLE001
            note(n, 'harness error', False, f'{type(exc).__name__}: {exc}')
        print(f'{n} done in {time.time() - t0:.0f} s', flush=True)
    with open(OUT / 'results.txt', 'a', encoding='utf-8') as fh:
        fh.write(f'# run {time.strftime("%Y-%m-%d %H:%M:%S %z")} cases {names}\n' + '\n'.join(RES) + '\n')
    for old in OUT.glob('tree*'):
        if old.is_dir() and not old.is_symlink() and str(old.resolve()).startswith('/tmp/A10A11/'):
            shutil.rmtree(old)
    ok = all(': PASS ' in r for r in RES)
    print('ALL AS EXPECTED' if ok else 'SOME STEP FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
