"""Stand-in of a driver cycle that wants the protocol lock (scratch trees only): take the tree's protocol lock with a
blocking flock(LOCK_EX) as p1_driver.ProtocolLock does, check under it whether SEAL.sha256 matches PROTOCOL.md and
MANIFEST.sha256 (the condition under which phase_driver.ensure_recorded raises its ALERT), release, wait 30 ms, again;
until STOPFILE exists. Writes the list of acquisitions as JSON to OUT.

  holder2.py TREE STOPFILE OUT
"""
import fcntl
import hashlib
import json
import os
import sys
import time

tree, stopfile, out = sys.argv[1], sys.argv[2], sys.argv[3]
if not os.path.realpath(tree).startswith('/tmp/A10A11/'):
    raise SystemExit('holder2: refused outside /tmp/A10A11/')
lock = os.path.join(tree, 'framelease_v4/.protocol.lock')
seal_p = os.path.join(tree, 'outputs/framelease_v4/registration/SEAL.sha256')
pro_p = os.path.join(tree, 'framelease_v4/PROTOCOL.md')
man_p = os.path.join(tree, 'outputs/framelease_v4/registration/MANIFEST.sha256')


def h(p):
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


recs = []
while not os.path.exists(stopfile):
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o664)
    t0 = time.time()
    fcntl.flock(fd, fcntl.LOCK_EX)
    t1 = time.time()
    seal = {}
    with open(seal_p, encoding='utf-8') as fh:
        for ln in fh:
            if '  ' in ln:
                s, r = ln.rstrip('\n').split('  ', 1)
                seal[r] = s
    pro, man = h(pro_p), h(man_p)
    ok = seal.get('framelease_v4/PROTOCOL.md') == pro and \
        seal.get('outputs/framelease_v4/registration/MANIFEST.sha256') == man
    with open(pro_p, encoding='utf-8') as fh:
        txt = fh.read()
    recs.append({'t_req': round(t0, 3), 't_acq': round(t1, 3), 'wait_s': round(t1 - t0, 3), 'consistent': ok,
                 'protocol': pro[:12], 'A10': '**Amendment A10,' in txt, 'A11': '**Amendment A11,' in txt})
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)
    time.sleep(0.03)
with open(out, 'w', encoding='utf-8') as fh:
    json.dump(recs, fh, indent=0)
