"""Fault helper of the step-3 simulation (scratch only): wait until a transaction journal lists a step, then act once.

  watch_and_act.py JOURNAL STEP killpg PID SIG   # SIG to the process group led by PID (a process started by setsid)
  watch_and_act.py JOURNAL STEP append FILE      # a comment line appended to FILE (a real file under /tmp/AMEND3/)

Refuses a PID that is not the leader of its own process group (never signals the caller's group) and a FILE that
resolves outside /tmp/AMEND3/ (a symlink of the scratch tree into the project). Exit 0 after acting, 2 refused,
3 time-out (120 s).
"""
import json
import os
import signal
import sys
import time


def main():
    journal, step, action = sys.argv[1], sys.argv[2], sys.argv[3]
    t0 = time.time()
    while time.time() - t0 < 120:
        try:
            with open(journal, encoding='utf-8') as fh:
                if step in [s.get('step') for s in json.load(fh).get('steps', [])]:
                    break
        except (OSError, ValueError):
            pass
        time.sleep(0.02)
    else:
        print('timeout')
        return 3
    if action == 'killpg':
        pid, sig = int(sys.argv[4]), getattr(signal, sys.argv[5])
        if os.getpgid(pid) != pid:
            print(f'refused: pid {pid} is not the leader of its process group ({os.getpgid(pid)})')
            return 2
        os.killpg(pid, sig)
        print(f'{time.strftime("%H:%M:%S")} sent {sys.argv[5]} to process group {pid} after journal step {step}')
    elif action == 'append':
        f = os.path.realpath(sys.argv[4])
        if not f.startswith('/tmp/AMEND3/'):
            print(f'refused: {f} is not under /tmp/AMEND3/')
            return 2
        with open(f, 'a', encoding='utf-8') as fh:
            fh.write('# changed by the step-3 simulation\n')
        print(f'{time.strftime("%H:%M:%S")} appended a line to {f} after journal step {step}')
    else:
        print(f'refused: action {action}')
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
