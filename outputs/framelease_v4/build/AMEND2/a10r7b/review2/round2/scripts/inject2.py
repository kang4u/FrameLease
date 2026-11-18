"""Run a scratch applier in-process with a fault or a fixed clock (re-check harness, scratch trees only).

Environment: INJECT_APPLIER (the scratch applier, under /tmp/A10A11/), INJECT_MODE:
  none                  no fault
  kill_after_manifest   SIGKILL right after registration.py --write-manifest returned
  kill_before_seal      SIGKILL instead of registration.py --seal (PROTOCOL.md is written)
  kill_after_seal       SIGKILL right after registration.py --seal returned
  slow_seal_kill        start registration.py --seal 3 s late in a child of the same process group, SIGKILL at once
  slow_manifest_kill    the same for registration.py --write-manifest --force
  touch_before_manifest append to INJECT_TARGET, then registration.py --write-manifest
  touch_after_manifest  registration.py --write-manifest, then append to INJECT_TARGET
  clock                 time.strftime('%Y-%m-%d %H:%M') returns INJECT_CLOCK from call INJECT_CLOCK_FROM on
"""
import os
import runpy
import signal
import subprocess
import sys
import time

applier = os.environ['INJECT_APPLIER']
mode = os.environ.get('INJECT_MODE', 'none')
target = os.environ.get('INJECT_TARGET', '')
if not os.path.realpath(applier).startswith('/tmp/A10A11/') or (
        target and not os.path.realpath(target).startswith('/tmp/A10A11/')):
    raise SystemExit('inject2: refused outside /tmp/A10A11/')
real_run = subprocess.run
SLOW = ('import runpy, sys, time; time.sleep(float(sys.argv[1])); sys.argv = sys.argv[2:]; '
        'runpy.run_path(sys.argv[0], run_name="__main__")')


def kill9(why):
    print(f'inject2: SIGKILL {why}', flush=True)
    os.kill(os.getpid(), signal.SIGKILL)


def touch():
    with open(target, 'a', encoding='utf-8') as fh:
        fh.write('# scratch-tree probe line\n')
    print('inject2: appended a line to', target, flush=True)


def patched(cmd, *a, **k):
    cmd = list(cmd)
    if (mode == 'slow_seal_kill' and '--seal' in cmd) or (mode == 'slow_manifest_kill' and '--write-manifest' in cmd):
        subprocess.Popen([cmd[0], '-I', '-B', '-c', SLOW, '3'] + cmd[3:], cwd=k.get('cwd'))
        kill9(f'after starting a slow {cmd[4:]}')
    if mode == 'kill_before_seal' and '--seal' in cmd:
        kill9('before --seal')
    if mode == 'touch_before_manifest' and '--write-manifest' in cmd:
        touch()
    r = real_run(cmd, *a, **k)
    if '--write-manifest' in cmd:
        if mode == 'kill_after_manifest':
            kill9('after --write-manifest')
        if mode == 'touch_after_manifest':
            touch()
    if mode == 'kill_after_seal' and '--seal' in cmd:
        kill9('after --seal')
    return r


if mode == 'clock':
    fixed, start = os.environ['INJECT_CLOCK'], int(os.environ.get('INJECT_CLOCK_FROM', '1'))
    real_strftime, calls = time.strftime, [0]

    def strftime(fmt, *a):
        if fmt == '%Y-%m-%d %H:%M' and not a:
            calls[0] += 1
            if calls[0] >= start:
                print(f'inject2: clock call {calls[0]} -> {fixed}', flush=True)
                return fixed
        return real_strftime(fmt, *a)
    time.strftime = strftime

subprocess.run = patched
sys.argv = [applier] + sys.argv[1:]
runpy.run_path(applier, run_name='__main__')
