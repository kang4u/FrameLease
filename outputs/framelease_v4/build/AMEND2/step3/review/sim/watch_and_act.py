"""Reviewer's fault helper (scratch only): wait until <journal> names step <step>, then act once.
  watch_and_act.py JOURNAL STEP append FILE        -> append a comment line to FILE (refuses outside /tmp/AMEND3_review/)
  watch_and_act.py JOURNAL STEP killpg PGID SIG    -> send SIG to the process group PGID
Exits 0 after acting, 3 on timeout (120 s)."""
import json, os, signal, sys, time
journal, step, action = sys.argv[1], sys.argv[2], sys.argv[3]
t0 = time.time()
while time.time() - t0 < 120:
    try:
        j = json.load(open(journal))
        if step in [s['step'] for s in j.get('steps', [])]:
            break
    except (OSError, ValueError):
        pass
    time.sleep(0.02)
else:
    print('timeout'); sys.exit(3)
if action == 'append':
    f = os.path.realpath(sys.argv[4])
    if not f.startswith('/tmp/AMEND3_review/'):
        print('refused', f); sys.exit(2)
    with open(f, 'a') as fh:
        fh.write('# changed by the step-3 review between the manifest and the seal\n')
    print(f'{time.strftime("%H:%M:%S")} appended to {f} after step {step}')
elif action == 'killpg':
    os.killpg(int(sys.argv[4]), getattr(signal, sys.argv[5]))
    print(f'{time.strftime("%H:%M:%S")} sent {sys.argv[5]} to process group {sys.argv[4]} after step {step}')
