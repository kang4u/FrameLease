"""P1 stage driver (framelease_v4/protocol/p1_driver.py and start_p1_driver.sh; PROTOCOL Secs. 4.2, 4.8, 4.9, 13.2;
outputs/framelease_v4/p1_jobs/README.md steps 4-5). CPU only, /tmp sandboxes only: the driver runs as a subprocess with
--root <sandbox>; select_stage.py, p1_jobs.py, d1_summary.py and launch_queue.sh are mocks written into the sandbox (they
read synthetic queue records and write synthetic selections / job files); registration.py is the REAL module with its
paths pointed at the sandbox by a wrapper, so the seal rule (PROTOCOL.md must cite the manifest sha256) is the real one.
The sandbox PROTOCOL.md is a copy of the real one (with any driver subsection removed). Nothing outside /tmp is written;
no GPU, no CARLA, no runner. The last check compares the real registration, PROTOCOL.md and queue files before / after.

  cd /home/kang/Desktop/DAC && nice -n 19 .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/protocol/tests/test_p1_driver.py

What is shown:
  * dry run: prints the plan and changes no file (select_stage runs without --write; no lock file is created);
  * not final: select_stage exit 3 -> nothing written, the stage waits, no launch without a copied block;
  * the whole chain (lease_s1 -> ... -> age_s2, event_s1 -> event_s2, freeze, D1): one Sec. 13.2 entry per stage plus the
    freeze and D1 under one heading placed just before "Each amendment gets the date and time", in recording order;
    each block generated only after its dependency is recorded and sealed (the p1_jobs mock refuses otherwise), with
    linux/env.sh sourced and CUDA hidden; every block copied once; seal and registration.py --verify OK; P1_DONE.json;
    a later start changes nothing;
  * select_stage exit 2: ALERT with the full output, nothing advanced, a restart refuses while ALERT.txt exists;
  * FLAG: ALERT, the selection is not recorded; without an acknowledgement it stays stopped; with FLAG_ACK_<stage>.txt
    citing the selection sha256 it records (citing the acknowledgement) and continues;
  * crash / restart at 7 points of a stage (after the selection, txn begin, manifest written, PROTOCOL.md written,
    sealed, block generated, block copied): no duplicate entry, no duplicate copy, no second select / p1_jobs call;
  * crash in the final steps (after the freeze, after D1): freeze and D1 written once, recorded once;
  * runner rules: 'queue empty' exit -> launch_queue.sh after the copy; a runner holding runner.lock -> no launch;
    circuit breaker -> ALERT, no launch; queue STOP -> no launch, attention, STOP kept; launch failure -> ALERT;
  * protocol lock contention: nothing recorded while another process holds framelease_v4/.protocol.lock, no ALERT;
    recorded once after it is released (select_stage not called again);
  * an unsealed foreign edit of PROTOCOL.md, or a registered file changed after the seal: ALERT, nothing recorded;
  * registered vs swept-in files: a framelease_v4 file in development (in the manifest only by its glob) may change
    between seals (the next entry names it) and while the driver re-seals (--verify tolerated, attention); a registered
    file changed while re-sealing is an ALERT before the next block; another editor's seal registers a new file only
    if PROTOCOL.md cites its sha256 (registered_baseline.json), and a later unamended change of it is an ALERT;
  * start_p1_driver.sh: detached start with a pid file, a second start and a second driver are refused (flock), a start
    during another start is refused (start.lock, not kept by the driver), STOP and SIGTERM stop it, a start is refused
    while STOP exists.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DRIVER = ROOT / 'framelease_v4/protocol/p1_driver.py'
START = ROOT / 'framelease_v4/protocol/start_p1_driver.sh'
REAL_PROTOCOL = ROOT / 'framelease_v4/PROTOCOL.md'
REAL_REGISTRATION = ROOT / 'framelease_v4/protocol/registration.py'
REAL_REG_DIR = ROOT / 'outputs/framelease_v4/registration'
PY = sys.executable
CRASH_ENV = 'P1_DRIVER_TEST_CRASH_AT'
TOUCH_ENV = 'P1_DRIVER_TEST_TOUCH_AT'
HEADING = '**Stage selections (P1, FULL).**'
ANCHOR = 'Each amendment gets the date and time'
STAGES = ('lease_s1', 'lease_s2', 'heur_s1', 'heur_s2', 'age_s1', 'age_s2', 'event_s1', 'event_s2')
QREL = 'outputs/framelease_v4/queue_p1'
PROTO = 'framelease_v4/PROTOCOL.md'
SELDIR = 'outputs/framelease_v4/tuning/selection/FULL'
DRV = 'outputs/framelease_v4/p1_driver'
ALERT = f'{DRV}/ALERT.txt'
DONE = f'{DRV}/P1_DONE.json'
MANIFEST = 'outputs/framelease_v4/registration/MANIFEST.sha256'
SEAL = 'outputs/framelease_v4/registration/SEAL.sha256'
BLOCK_FILES = {'lease_s2': 'b04_lease_s2.jsonl', 'event_s2': 'b05_event_s2.jsonl', 'heur_s1': 'b06_heur_s1.jsonl',
               'heur_s2': 'b07_heur_s2.jsonl', 'age_s1': 'b08_age_s1.jsonl', 'age_s2': 'b09_age_s2.jsonl'}

_spec = importlib.util.spec_from_file_location('p1_driver_under_test', DRIVER)
D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(D)

ENV_SH = 'export P1D_ENV_SOURCED=1\nexport CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"\n'

MOCKCOMMON = r'''
import hashlib, json, os, sys, time
from pathlib import Path

R = Path.cwd()
Q = R / 'outputs/framelease_v4/queue_p1'
JOBS = R / 'outputs/framelease_v4/p1_jobs/FULL'
SEL = R / 'outputs/framelease_v4/tuning/selection/FULL'
BLOCK_NO = {'ref': 1, 'lease_s1': 2, 'event_s1': 3, 'lease_s2': 4, 'event_s2': 5, 'heur_s1': 6, 'heur_s2': 7,
            'age_s1': 8, 'age_s2': 9}
DEP = {'lease_s2': 'lease_s1', 'event_s2': 'event_s1', 'heur_s1': 'lease_s2', 'heur_s2': 'heur_s1',
       'age_s1': 'heur_s2', 'age_s2': 'age_s1'}
FINAL = ('lease_s2', 'event_s2', 'heur_s2', 'age_s2')
GRID = {'lease': ['E5', 'E10', 'B0'], 'event': ['v2_hb2.0', 'v2_hb1.0', 's_hb2.0', 's_hb1.0'],
        'heur': ['d10', 'd4', 'd1'], 'age': ['A1.0', 'A1.5', 'A2.0', 'A2.5'], 'ref': ['fixed_deep', 'fast_only']}
ROUTES = {0: ['101', '102', '103', '201', '202', '203'], 1: ['101', '102', '103'], 2: ['201', '202', '203']}


def grid_of(block):
    return block.split('_')[0]


def stage_no(block):
    return 0 if block == 'ref' else int(block[-1])


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rel(p):
    return str(Path(p).resolve().relative_to(R.resolve()))


def log_call(tool, **extra):
    with open(R / 'mock/calls.jsonl', 'a') as f:
        f.write(json.dumps({'tool': tool, 'argv': sys.argv[1:], 't': time.time(), 'nice': os.nice(0),
                            'env_sourced': os.environ.get('P1D_ENV_SOURCED'),
                            'cuda': os.environ.get('CUDA_VISIBLE_DEVICES'), **extra}) + '\n')


def scenario():
    p = R / 'mock/scenario.json'
    return json.loads(p.read_text()) if p.exists() else {}


def paths(block):
    base = JOBS / f'b{BLOCK_NO[block]:02d}_{block}'
    return base.with_suffix('.jsonl'), Path(str(base) + '.stage.json'), Path(str(base) + '.check.json')


def candidates(block):
    g, s = grid_of(block), stage_no(block)
    if s in (0, 1):
        names = list(GRID[g])
    else:
        dep = json.loads((SEL / f'{DEP[block]}.json').read_text())
        names = [c for c in GRID[g] if c in dep['survivors']]
    reused = [c for c in names if g == 'heur' and c == 'd10']
    return names, reused


def write_block(block, inputs):
    names, reused = candidates(block)
    routes = ROUTES[stage_no(block)]
    lines = [{'id': f'v4p1_{block}_{c}_r{r}', 'kind': 'closed_loop', 'tier': 1, 'cmd': ['true'], 'wall_cap_s': 60,
              'block': block, 'candidate': c, 'route_id': r, 'require_sha256': {}}
             for r in routes for c in names if c not in reused]
    jp, sp, cp = paths(block)
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(''.join(json.dumps(j, sort_keys=True) + '\n' for j in lines))
    js = sha(jp)
    cands = [{'name': c, 'order': GRID[grid_of(block)].index(c), 'reused_from': 'lease' if c in reused else None}
             for c in names]
    spec = {'schema': 'framelease_v4.p1_stage/1', 'variant': 'FULL', 'block': block, 'block_no': BLOCK_NO[block],
            'grid': grid_of(block), 'stage': stage_no(block), 'final_stage': block in FINAL, 'routes': routes,
            'candidates': cands, 'n_lines': len(lines), 'inputs': inputs, 'job_file': rel(jp), 'job_file_sha256': js}
    sp.write_text(json.dumps(spec, indent=1, sort_keys=True) + '\n')
    cp.write_text(json.dumps({'schema': 'framelease_v4.p1_check/1', 'job_file': rel(jp), 'job_file_sha256': js,
                              'n_lines': len(lines), 'problems': [], 'all_dry_runs_ok': True, 'lines': []},
                             indent=1, sort_keys=True) + '\n')
    return jp
'''

MOCK_INIT = r'''
import shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mockcommon as M
for b in ('ref', 'lease_s1', 'event_s1'):
    jp = M.write_block(b, {})
    (M.Q / 'jobs.d').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(jp, M.Q / 'jobs.d' / jp.name)
'''

MOCK_SELECT = r'''
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mockcommon as M

a = sys.argv[1:]
sc = M.scenario()
now = time.strftime('%Y-%m-%dT%H:%M:%S%z')


def finals():
    out = {}
    p = M.Q / 'status.jsonl'
    if p.exists():
        for line in p.read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get('event') == 'end' and r.get('final'):
                out[r['id']] = r
    return out


if '--freeze' in a:
    path = M.R / 'outputs/framelease_v4/tuning/selection.json'
    M.log_call('freeze', pre_exists=path.exists())
    if path.exists() and '--force' not in a:
        print(f'ERROR: refusing to overwrite {path} (use --force)', file=sys.stderr)
        sys.exit(2)
    sels = {}
    for s in ('lease_s1', 'event_s1', 'lease_s2', 'event_s2', 'heur_s1', 'heur_s2', 'age_s1', 'age_s2'):
        p = M.SEL / f'{s}.json'
        if not p.exists():
            print(f'ERROR: FULL {s}: selection {p} not written yet', file=sys.stderr)
            sys.exit(2)
        sels[s] = (json.loads(p.read_text()), M.sha(p), M.rel(p))
    L = sels['lease_s2'][0]['selected']
    d = int(sels['heur_s2'][0]['selected'][1:])
    A = float(sels['age_s2'][0]['selected'][1:])
    ev = sels['event_s2'][0]['selected']
    doc = {'schema': 'framelease_v4.tuning_selection/1', 'variant': 'FULL', 'written': now,
           'L_star': {'label': L, 'envelope_path': f'outputs/framelease_v4/envelopes/{L}.json',
                      'envelope_sha256': '0' * 64, 'validity': 'std'},
           'd_star': {'d': d, 'utility': 'heuristic' if d == 10 else f'v4_adet_d{d}'}, 'A_star': {'age_lease_s': A},
           'event_star': {'candidate': ev, 'policy_params': {'heartbeat_s': float(ev.split('_hb')[1])}},
           'fl_risk': {'lease_point': 'E5', 'rule': 'L* = B0'} if L == 'B0' else None,
           'stages': {s: {'path': v[2], 'sha256': v[1]} for s, v in sels.items()},
           'flags': {s: v[0]['flags'] for s, v in sels.items() if v[0].get('flags')}}
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n')
    print(json.dumps({k: doc[k] for k in ('variant', 'L_star', 'd_star', 'A_star', 'event_star', 'fl_risk', 'flags')},
                     indent=1))
    print(f'wrote {path}  sha256 {M.sha(path)}')
    sys.exit(0)

stage = a[a.index('--stage') + 1]
write = '--write' in a
M.log_call('select', stage=stage, write=write, pre_exists=(M.SEL / f'{stage}.json').exists())
ssc = (sc.get('select') or {}).get(stage) or {}
if ssc.get('exit') == 2:
    print('ERROR: ' + ssc.get('message', 'synthetic: a runner ok record without a matching run directory'),
          file=sys.stderr)
    sys.exit(2)
jp, sp, cp = M.paths(stage)
lines = [json.loads(ln) for ln in (M.Q / 'jobs.d' / jp.name).read_text().splitlines() if ln.strip()]
fin = finals()
pending = [j['id'] for j in lines if j['id'] not in fin]
if pending:
    print(f'NOT SELECTED: FULL {stage}: {len(pending)} jobs have no final outcome yet, e.g. {pending[:3]}',
          file=sys.stderr)
    sys.exit(3)
if ssc.get('all_dropped'):
    print(f'NOT SELECTED: FULL {stage}: every route was dropped', file=sys.stderr)
    sys.exit(3)
spec = json.loads(sp.read_text())
names = [c['name'] for c in spec['candidates']]
order = {c['name']: c['order'] for c in spec['candidates']}
ds = {}
for c in names:
    vals = [fin[j['id']]['result']['scores']['score_composed'] for j in lines if j['candidate'] == c]
    ds[c] = sum(vals) / len(vals) if vals else 50.0
ranking = sorted(names, key=lambda c: (-ds[c], order[c]))
final = stage in M.FINAL
table = []
for c in names:
    row = {'candidate': c, 'order': order[c], 'mean_ds': ds[c], 'n': len(spec['routes']),
           'outcomes': {'ok': len(spec['routes'])}}
    if final:
        row.update(mean_ds_T22=ds[c] - 1.0, n_T22=2 * len(spec['routes']))
    table.append(row)
flags = []
if ssc.get('flag'):
    flags = [{'candidate': names[-1], 'setup_failures': 2, 'routes': [spec['routes'][0]],
              'flag': "repeated agent set-up failures (Agent couldn't be set up)"}]
sel = {'schema': 'framelease_v4.p1_selection/1', 'variant': 'FULL', 'stage': stage, 'grid': spec['grid'],
       'stage_no': spec['stage'], 'final': final, 'complete': True, 'provisional': False,
       'stage_spec': M.rel(sp), 'stage_spec_sha256': M.sha(sp), 'job_file': M.rel(jp), 'job_file_sha256': M.sha(jp),
       'queue': 'outputs/framelease_v4/queue_p1', 'finality': 'runner records (--queue)', 'routes': spec['routes'],
       'kept_routes': spec['routes'], 'dropped_routes': {}, 'pending': [], 'table': table, 'flags': flags,
       'candidates': [{'name': c, 'order': order[c]} for c in names], 'warnings': [], 'ranking': ranking,
       'script_sha256': 'mock', 'written': now}
if final:
    sel['selected'] = ranking[0]
    sel['ranking_T22'] = ranking
else:
    k = (len(names) + 1) // 2
    sel['survivors'] = [c for c in names if c in ranking[:k]]
print(f'FULL {stage} (complete; finality: runner records (--queue)): {len(spec["routes"])}/{len(spec["routes"])} '
      'routes kept')
for row in table:
    print(f'  {row["candidate"]:<12} mean DS {row["mean_ds"]:>8}  n {row["n"]:>2}  {row["outcomes"]}')
print(f'  selected: {sel["selected"]}' if final else f'  survivors: {sel["survivors"]}')
for f in flags:
    print(f'  FLAG {f["candidate"]}: 2 set-up failures on routes {f["routes"]}: {f["flag"]}')
if write:
    path = M.SEL / f'{stage}.json'
    if path.exists():
        print(f'ERROR: refusing to overwrite {path} with a different selection (use --force)', file=sys.stderr)
        sys.exit(2)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sel, indent=1, sort_keys=True) + '\n')
    print(f'wrote {path}  sha256 {M.sha(path)}')
'''

MOCK_JOBS = r'''
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mockcommon as M

a = sys.argv[1:]
block = a[a.index('--block') + 1]
M.log_call('jobs', block=block, pre_exists=M.paths(block)[0].exists())
if not ('--check' in a and '--write' in a and a[a.index('--variant') + 1] == 'FULL'):
    print('ERROR: not the README command', file=sys.stderr)
    sys.exit(1)
if os.environ.get('P1D_ENV_SOURCED') != '1' or os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    print('ERROR: linux/env.sh not sourced or CUDA not hidden', file=sys.stderr)
    sys.exit(1)
dep = M.DEP[block]
sp = M.SEL / f'{dep}.json'
if not sp.exists():
    print(f'FULL {block}: cannot be generated yet: selection {sp} not written', file=sys.stderr)
    sys.exit(2)
dsha = M.sha(sp)
proto = M.R / 'framelease_v4/PROTOCOL.md'
seal = {}
for line in (M.R / 'outputs/framelease_v4/registration/SEAL.sha256').read_text().splitlines():
    s, p = line.split('  ', 1)
    seal[p] = s
man = M.R / 'outputs/framelease_v4/registration/MANIFEST.sha256'
if (dsha not in proto.read_text() or seal.get('framelease_v4/PROTOCOL.md') != M.sha(proto)
        or seal.get('outputs/framelease_v4/registration/MANIFEST.sha256') != M.sha(man)):
    print(f'ERROR: the {dep} selection is not recorded in PROTOCOL.md and sealed before {block} is generated',
          file=sys.stderr)
    sys.exit(1)
if M.scenario().get('jobs_fail') == block:
    print(f'{block}: CHECK FAILED\n  synthetic problem', file=sys.stderr)
    sys.exit(1)
jp = M.write_block(block, {M.rel(sp): dsha})
print(f'{block}: job lines -> {M.rel(jp)} (NOT launched)')
print(json.dumps({'job_file': M.rel(jp), 'sha256': M.sha(jp)}))
'''

MOCK_D1 = r'''
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mockcommon as M

M.log_call('d1')
a = sys.argv[1:]
assert a[a.index('--queue') + 1] == 'outputs/framelease_v4/queue_p1' and '--write' in a
fz = M.R / 'outputs/framelease_v4/tuning/selection.json'
out = M.R / 'outputs/framelease_v4/tuning/d1'
out.mkdir(parents=True, exist_ok=True)
doc = {'schema': 'framelease_v4.d1_summary/1', 'variant': 'FULL', 'written': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
       'blocks': [{'block': b, 'pending': 0} for b in M.BLOCK_NO],
       'tuning_freeze': {'sha256': M.sha(fz)} if fz.exists() else None}
j, md = out / 'FULL_d1_summary.json', out / 'FULL_d1_summary.md'
j.write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n')
md.write_text('# D1 training-route summary (mock)\n')
print('# D1 training-route summary (mock)')
print(f'wrote {j}  sha256 {M.sha(j)}')
print(f'wrote {md}  sha256 {M.sha(md)}')
'''

MOCK_LAUNCH = r'''#!/usr/bin/env bash
# records the call; like the real runner, the "started" runner appends its runner_start record (it never holds the lock)
echo "$(date +%s.%N) $*" >> "$PWD/mock/launch_calls.log"
if [ -e "$PWD/mock/launch_fail" ]; then echo "launch_queue: the runner did not start" >&2; exit 1; fi
echo '{"event": "runner_start", "pid": 99999, "utc": "mock"}' >> "$PWD/$1/status.jsonl"
echo "started runner pid 99999 and disk watchdog pid 99998"
'''

REG_WRAPPER = r'''
import importlib.util, sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mockcommon as Mc

Mc.log_call('registration')
spec = importlib.util.spec_from_file_location('registration_real', '@REAL@')
REG = importlib.util.module_from_spec(spec)
spec.loader.exec_module(REG)
R = Path.cwd()
REG.ROOT = R
REG.REG_DIR = R / 'outputs/framelease_v4/registration'
REG.MANIFEST = REG.REG_DIR / 'MANIFEST.sha256'
REG.SEAL = REG.REG_DIR / 'SEAL.sha256'
REG.RECORD = REG.REG_DIR / 'REGISTRATION.json'
REG.PROTOCOL = R / 'framelease_v4/PROTOCOL.md'
REG.REGISTERED_JOB_FILES = ('outputs/framelease_v4/p1_jobs/FULL/b02_lease_s1.jsonl',
                            'outputs/framelease_v4/p1_jobs/FULL/b03_event_s1.jsonl')
REG.OUTPUT_FILES = ()
REG.SEC_12_1 = ()
REG.verify.__defaults__ = (REG.MANIFEST,)          # defaults bound at definition time point at the real files
REG.read_manifest.__defaults__ = (REG.MANIFEST,)
REG.job_pins.__defaults__ = (REG.REGISTERED_JOB_FILES,)
sys.exit(REG.main(sys.argv[1:]))
'''

MOCKS = {'mockcommon.py': MOCKCOMMON, 'init.py': MOCK_INIT, 'select_stage.py': MOCK_SELECT, 'p1_jobs.py': MOCK_JOBS,
         'd1_summary.py': MOCK_D1, 'launch_queue.sh': MOCK_LAUNCH,
         'registration_sandbox.py': REG_WRAPPER.replace('@REAL@', str(REAL_REGISTRATION))}


# ---------------------------------------------------------------------------------------------------- helpers

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(cmd, cwd, timeout=180, env=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)


def strip_driver_subsection(text):
    lines = text.split('\n')
    stripped = [ln.strip() for ln in lines]
    if HEADING not in stripped:
        return text
    i = stripped.index(HEADING)
    j = i + 1
    while j < len(lines) and lines[j].strip():
        j += 1
    del lines[i:j + 1]
    return '\n'.join(lines)


def reg(R, *flags):
    return run([PY, '-I', '-B', 'mock/registration_sandbox.py', *flags], R)


def make_sandbox(test):
    tmp = tempfile.mkdtemp(prefix='p1drv_', dir='/tmp')
    test.addCleanup(shutil.rmtree, tmp, True)
    R = Path(tmp) / 'root'
    for d in ('framelease_v4/protocol', 'mock', 'linux'):
        (R / d).mkdir(parents=True)
    (R / 'linux/env.sh').write_text(ENV_SH)
    (R / 'framelease_v4/protocol/tool.py').write_text('# sandbox stand-in for a registered tool\n')
    for name, text in MOCKS.items():
        (R / 'mock' / name).write_text(text)
    p = run([PY, '-I', '-B', 'mock/init.py'], R)
    assert p.returncode == 0, p.stderr
    proto = strip_driver_subsection(REAL_PROTOCOL.read_text(encoding='utf-8'))
    (R / PROTO).write_text(proto, encoding='utf-8')
    p = reg(R, '--write-manifest', '--force')
    assert p.returncode == 0, p.stdout + p.stderr
    m0 = sha(R / MANIFEST)
    real_m = next(ln.split('  ')[0] for ln in (REAL_REG_DIR / 'SEAL.sha256').read_text().splitlines()
                  if ln.endswith('MANIFEST.sha256'))
    if real_m in proto:
        proto = proto.replace(real_m, m0)
    else:
        proto = proto.replace(ANCHOR, f'Sandbox registration: manifest sha256 `{m0}`.\n\n{ANCHOR}', 1)
    (R / PROTO).write_text(proto, encoding='utf-8')
    p = reg(R, '--seal')
    assert p.returncode == 0, p.stdout + p.stderr
    return R


def finish_jobs(R, only=None, exit_reason='queue empty', exit_code=0, runner_exit=True):
    """The 'runner': final ok records for every job in jobs.d without one (DS by the candidate's grid order), then
    optionally its exit record."""
    q = R / QREL
    status = q / 'status.jsonl'
    finals = set()
    if status.exists():
        for ln in status.read_text().splitlines():
            r = json.loads(ln)
            if r.get('event') == 'end' and r.get('final'):
                finals.add(r['id'])
    grid = {'E5': 0, 'E10': 1, 'B0': 2, 'v2_hb2.0': 0, 'v2_hb1.0': 1, 's_hb2.0': 2, 's_hb1.0': 3, 'd10': 0, 'd4': 1,
            'd1': 2, 'A1.0': 0, 'A1.5': 1, 'A2.0': 2, 'A2.5': 3, 'fixed_deep': 0, 'fast_only': 1}
    recs = [{'event': 'runner_start', 'pid': 4242, 'utc': '2026-11-11T00:00:00+00:00'}]
    for f in sorted((q / 'jobs.d').glob('*.jsonl')):
        for ln in f.read_text().splitlines():
            j = json.loads(ln)
            if j['id'] in finals or (only is not None and not only(j)):
                continue
            ds = 90.0 - 10.0 * grid[j['candidate']]
            recs += [{'event': 'start', 'id': j['id'], 'attempt': 1},
                     {'event': 'end', 'id': j['id'], 'attempt': 1, 'final': True, 'counted': True, 'outcome': 'ok',
                      'result': {'scores': {'score_composed': ds}}}]
    if runner_exit:
        recs.append({'event': 'runner_exit', 'pid': 4242, 'reason': exit_reason, 'exit_code': exit_code})
    with status.open('a') as fh:
        for r in recs:
            fh.write(json.dumps(r, sort_keys=True) + '\n')


def drive(R, *extra, crash=None, touch=None, timeout=300):
    cmd = [PY, '-I', '-B', str(DRIVER), '--root', str(R), '--python', PY,
           '--select-script', str(R / 'mock/select_stage.py'), '--jobs-script', str(R / 'mock/p1_jobs.py'),
           '--d1-script', str(R / 'mock/d1_summary.py'),
           '--registration-script', str(R / 'mock/registration_sandbox.py'),
           '--launch-script', str(R / 'mock/launch_queue.sh'), '--env-script', str(R / 'linux/env.sh'),
           '--lock-timeout-s', '2', '--allow-nice-launch']        # the tests run under nice 19
    if '--dry-run' not in extra:
        cmd.append('--once')
    cmd += list(extra)
    env = {k: v for k, v in os.environ.items() if k not in (CRASH_ENV, TOUCH_ENV, 'CUDA_VISIBLE_DEVICES')}
    if crash:
        env[CRASH_ENV] = crash
    if touch:
        env[TOUCH_ENV] = touch
    return run(cmd, R, timeout, env)


def calls(R, tool=None):
    p = R / 'mock/calls.jsonl'
    out = [json.loads(ln) for ln in p.read_text().splitlines()] if p.exists() else []
    return [c for c in out if tool is None or c['tool'] == tool]


def launches(R):
    p = R / 'mock/launch_calls.log'
    return p.read_text().splitlines() if p.exists() else []


def entries(R):
    return D.protocol_view(None, (R / PROTO).read_text(encoding='utf-8'))['entries']


def state(R):
    return json.loads((R / 'outputs/framelease_v4/pipeline_state.json').read_text())


def seal_ok(R):
    seal = {}
    for ln in (R / SEAL).read_text().splitlines():
        s, p = ln.split('  ', 1)
        seal[p] = s
    return seal.get(PROTO) == sha(R / PROTO) and seal.get(MANIFEST) == sha(R / MANIFEST)


def verify_ok(R):
    p = reg(R, '--verify')
    return p.returncode == 0 and 'manifest: OK' in p.stdout and 'CHANGED' not in p.stdout


def tree(R):
    out = {}
    for p in sorted(R.rglob('*')):
        if p.is_file() and p.relative_to(R).parts[0] != 'mock':
            out[str(p.relative_to(R))] = (sha(p), p.stat().st_mtime_ns)
    return out


def jobs_d(R):
    return sorted(p.name for p in (R / QREL / 'jobs.d').iterdir())


def out_of(p):
    return f'exit {p.returncode}\n--- stdout ---\n{p.stdout[-6000:]}\n--- stderr ---\n{p.stderr[-6000:]}'


def alert_text(R):
    p = R / ALERT
    return p.read_text() if p.exists() else ''


def real_snapshot():
    snap = {str(f): sha(f) for f in (REAL_PROTOCOL, REAL_REG_DIR / 'MANIFEST.sha256', REAL_REG_DIR / 'SEAL.sha256',
                                     REAL_REG_DIR / 'REGISTRATION.json')}
    snap['jobs.d'] = sorted(p.name for p in (ROOT / QREL / 'jobs.d').iterdir())
    snap['p1_jobs/FULL'] = sorted(p.name for p in (ROOT / 'outputs/framelease_v4/p1_jobs/FULL').iterdir())
    sel = ROOT / 'outputs/framelease_v4/tuning/selection'
    snap['selection'] = sorted(str(p) for p in sel.rglob('*')) if sel.exists() else None
    snap['state'] = (ROOT / 'outputs/framelease_v4/pipeline_state.json').exists()
    snap['protocol_lock'] = (ROOT / 'framelease_v4/.protocol.lock').exists()
    d = ROOT / DRV
    snap['driver'] = sorted(p.name for p in d.iterdir() if p.name in ('ALERT.txt', 'P1_DONE.json', 'driver.log',
                                                                     'driver.lock', 'driver.pid', 'protocol_txn.json',
                                                                     'manifest_sealed.sha256')) if d.exists() else None
    return snap


def foreign_amendment(R, paragraph):
    """Another editor's amendment: write the manifest, add a paragraph citing it before the anchor, seal."""
    p = reg(R, '--write-manifest', '--force')
    assert p.returncode == 0, p.stdout + p.stderr
    text = (R / PROTO).read_text(encoding='utf-8')
    text = text.replace(ANCHOR, f'{paragraph} Manifest sha256 `{sha(R / MANIFEST)}`.\n\n{ANCHOR}', 1)
    (R / PROTO).write_text(text, encoding='utf-8')
    p = reg(R, '--seal')
    assert p.returncode == 0, p.stdout + p.stderr


def flat(R, key):
    return entries(R)[key]['text'].replace('\n  ', ' ')


class LockHolder:
    """A separate process holding an exclusive flock on `path` until stopped."""

    def __init__(self, path):
        code = ('import fcntl, os, sys, time\nfd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o644)\n'
                'fcntl.flock(fd, fcntl.LOCK_EX)\nprint("held", flush=True)\ntime.sleep(300)\n')
        self.p = subprocess.Popen([PY, '-I', '-B', '-c', code, str(path)], stdout=subprocess.PIPE, text=True)
        assert self.p.stdout.readline().strip() == 'held'

    def stop(self):
        self.p.kill()
        self.p.wait(timeout=10)
        self.p.stdout.close()


# ---------------------------------------------------------------------------------------------------- tests

class EntryFormatTest(unittest.TestCase):
    def test_heading_created_once_before_the_anchor(self):
        text = strip_driver_subsection(REAL_PROTOCOL.read_text(encoding='utf-8'))
        e1 = D.wrap_entry('**lease_s1**, 2026-11-11 21:00 (Beijing time). Selection `x` (sha256 `' + 'a' * 64 + '`). '
                          + 'word ' * 60 + '1. - * # not list starts')
        t1 = D.insert_entry(None, text, e1)
        e2 = D.wrap_entry('**event_s1**, 2026-11-11 21:05 (Beijing time). Selection `y` (sha256 `' + 'b' * 64 + '`).')
        t2 = D.insert_entry(None, t1, e2)
        v = D.protocol_view(None, t2)
        lines = v['lines']
        self.assertEqual([ln.strip() for ln in lines].count(HEADING), 1)
        h = v['heading']
        self.assertEqual(lines[h - 1], '')
        self.assertEqual(set(v['entries']), {'lease_s1', 'event_s1'})
        self.assertLess(v['entries']['lease_s1']['line'], v['entries']['event_s1']['line'])
        self.assertEqual(lines[v['anchor'] - 1], '')
        for ln in e1[1:]:
            self.assertTrue(ln.startswith('  ') and not D.LIST_START.match(ln[2:]), ln)
        self.assertTrue(all(len(ln) <= 120 for ln in e1 + e2))
        self.assertIn('a' * 64, v['entries']['lease_s1']['shas'])
        # the rest of the document is unchanged
        self.assertEqual(t2.replace('\n'.join([HEADING] + e1 + e2 + ['']) + '\n', ''), text)


class DriverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real_before = real_snapshot()

    @classmethod
    def tearDownClass(cls):
        after = real_snapshot()
        if after != cls.real_before:
            raise AssertionError(f'the real tree changed during the tests: {cls.real_before} -> {after}')

    # -------------------------------------------------------------------------------- dry run and waiting
    def test_dry_run_changes_nothing(self):
        R = make_sandbox(self)
        finish_jobs(R)
        before = tree(R)
        p = drive(R, '--dry-run')
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(tree(R), before)
        self.assertFalse((R / 'framelease_v4/.protocol.lock').exists())
        self.assertIn('WOULD: lease_s1: select_stage --write (the stage is final)', p.stdout)
        self.assertIn('WOULD: event_s1: select_stage --write (the stage is final)', p.stdout)
        sel_calls = calls(R, 'select')
        self.assertEqual(sorted(c['stage'] for c in sel_calls), ['event_s1', 'lease_s1'])
        self.assertFalse(any(c['write'] for c in sel_calls))

    def test_not_final_waits(self):
        R = make_sandbox(self)
        finish_jobs(R, only=lambda j: j['block'] != 'lease_s1' or j['route_id'] != '103', runner_exit=False)
        before = sha(R / PROTO)
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertFalse((R / SELDIR / 'lease_s1.json').exists())
        self.assertTrue((R / SELDIR / 'event_s1.json').exists())        # the other chain is final and advances
        self.assertEqual(set(entries(R)), {'event_s1'})
        st = state(R)
        self.assertEqual(st['stages']['lease_s1']['status'], 'waiting_final')
        self.assertIn('NOT SELECTED', st['stages']['lease_s1']['note'])
        self.assertEqual(st['stages']['lease_s2']['status'], 'not_queued')
        self.assertEqual(st['stages']['event_s1']['status'], 'done')
        self.assertNotEqual(sha(R / PROTO), before)
        self.assertEqual(alert_text(R), '')
        self.assertEqual([c['block'] for c in calls(R, 'jobs')], ['event_s2'])
        # event_s2 was copied while the last runner start has no exit record: launch after the copy (task rule)
        self.assertEqual(len(launches(R)), 1)
        self.assertIn('not final yet', (R / DRV / 'driver.log').read_text())
        # a second cycle while nothing changed: no new block, no relaunch without a copy or a normal exit
        n_calls = len(calls(R, 'jobs'))
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(len(calls(R, 'jobs')), n_calls)
        self.assertEqual(len(launches(R)), 1)
        self.assertTrue(any('no runner holds' in a for a in state(R)['attention']), state(R)['attention'])

    # -------------------------------------------------------------------------------- the whole chain
    def test_full_chain_to_done(self):
        R = make_sandbox(self)
        finish_jobs(R)
        for _ in range(10):
            p = drive(R)
            self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
            if (R / DONE).exists():
                break
            finish_jobs(R)
        self.assertTrue((R / DONE).exists(), out_of(p))
        text = (R / PROTO).read_text(encoding='utf-8')
        v = D.protocol_view(None, text)
        order = ['lease_s1', 'event_s1', 'lease_s2', 'event_s2', 'heur_s1', 'heur_s2', 'age_s1', 'age_s2', 'freeze',
                 'd1']
        self.assertEqual(sorted(v['entries'], key=lambda k: v['entries'][k]['line']), order)
        lines = v['lines']
        self.assertEqual([ln.strip() for ln in lines].count(HEADING), 1)
        self.assertEqual(lines[v['heading'] - 1], '')
        self.assertEqual(v['entries']['lease_s1']['line'], v['heading'] + 2)
        self.assertEqual(lines[v['anchor'] - 1], '')
        last = v['entries']['d1']
        self.assertEqual(last['line'] + len(last['text'].split('\n')), v['anchor'])   # entries end right before it
        for s in STAGES:
            ent = v['entries'][s]
            flat = ent['text'].replace('\n  ', ' ')
            self.assertIn(sha(R / SELDIR / f'{s}.json'), ent['shas'])
            self.assertIn(f'{SELDIR}/{s}.json', flat)
            self.assertIn('Beijing time' if time.strftime('%z') == '+0800' else 'UTC', flat)
            self.assertIn('Selected: `' if s in D.FINAL_STAGES else 'Survivors (top ', flat)
            self.assertIn('Manifest and seal: `MANIFEST.sha256`', flat)
        self.assertIn('Survivors (top 2): `E5`, `E10`', v['entries']['lease_s1']['text'].replace('\n  ', ' '))
        # the manifest clause names the files that entered the manifest with each seal
        self.assertIn('new in it: `framelease_v4/.protocol.lock`', v['entries']['lease_s1']['text'].replace('\n  ', ' '))
        self.assertIn('`outputs/framelease_v4/p1_jobs/FULL/b04_lease_s2.jsonl`',
                      v['entries']['event_s1']['text'].replace('\n  ', ' '))
        self.assertIn('Selected: `E5`', v['entries']['lease_s2']['text'].replace('\n  ', ' '))
        self.assertTrue(all(len(ln) <= 120 for k in order for ln in v['entries'][k]['text'].split('\n')))
        fz = R / 'outputs/framelease_v4/tuning/selection.json'
        self.assertIn(sha(fz), v['entries']['freeze']['shas'])
        self.assertIn(sha(R / 'outputs/framelease_v4/tuning/d1/FULL_d1_summary.json'), v['entries']['d1']['shas'])
        self.assertIn(sha(R / 'outputs/framelease_v4/tuning/d1/FULL_d1_summary.md'), v['entries']['d1']['shas'])
        # the newest entry cites the sealed manifest; seal and verify pass
        self.assertIn(sha(R / MANIFEST), v['entries']['d1']['shas'])
        self.assertTrue(seal_ok(R))
        self.assertTrue(verify_ok(R))
        man = (R / MANIFEST).read_text()
        self.assertIn('outputs/framelease_v4/p1_jobs/FULL/b08_age_s1.jsonl', man)
        self.assertIn('framelease_v4/.protocol.lock', man)
        # every block generated once, after its dependency was recorded and sealed (the mock refuses otherwise),
        # with linux/env.sh sourced, CUDA hidden and at low priority; copied once
        self.assertEqual(sorted(c['block'] for c in calls(R, 'jobs')), sorted(BLOCK_FILES))
        self.assertTrue(all(c['env_sourced'] == '1' and c['cuda'] == '' and c['nice'] >= 10
                            for c in calls(R, 'jobs')))
        self.assertEqual(jobs_d(R), sorted(['b01_ref.jsonl', 'b02_lease_s1.jsonl', 'b03_event_s1.jsonl']
                                           + list(BLOCK_FILES.values())))
        for f in BLOCK_FILES.values():
            self.assertEqual(sha(R / QREL / 'jobs.d' / f), sha(R / 'outputs/framelease_v4/p1_jobs/FULL' / f))
        sel_calls = [c for c in calls(R, 'select') if c['write']]
        self.assertFalse(any(c['pre_exists'] for c in sel_calls))
        self.assertEqual(len(calls(R, 'freeze')), 1)
        self.assertEqual(len(calls(R, 'd1')), 1)
        self.assertEqual(len(launches(R)), len(BLOCK_FILES))
        self.assertTrue(all(ln.split()[1] == QREL for ln in launches(R)))
        st = state(R)
        self.assertEqual(st['driver']['status'], 'DONE')
        self.assertTrue(all(st['stages'][s]['status'] == 'done' for s in STAGES), st['stages'])
        done = json.loads((R / DONE).read_text())
        self.assertEqual(done['stages']['lease_s2']['winners']['selected'], 'E5')
        self.assertEqual(done['freeze']['d_star']['d'], 4)
        self.assertTrue(done['seal_ok'])
        self.assertIn('no later phase', done['next'])
        # a later start changes nothing and calls nothing
        before, n = tree(R), len(calls(R))
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(len(calls(R)), n)
        after = tree(R)
        for k in set(before) | set(after):
            if not k.startswith(DRV) and not k.endswith('pipeline_state.json'):
                self.assertEqual(before.get(k), after.get(k), k)
        self.assertEqual(alert_text(R), '')

    # -------------------------------------------------------------------------------- errors and FLAG
    def test_select_error_alerts_and_blocks_restart(self):
        R = make_sandbox(self)
        (R / 'mock/scenario.json').write_text(json.dumps(
            {'select': {'lease_s1': {'exit': 2, 'message': 'v4p1_x_r101: the runner says ok but no run directory'}}}))
        finish_jobs(R)
        before = sha(R / PROTO)
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        alert = alert_text(R)
        self.assertIn('select_stage.py exited 2', alert)
        self.assertIn('the runner says ok but no run directory', alert)
        self.assertIn('--stage lease_s1', alert)
        self.assertEqual(sha(R / PROTO), before)
        self.assertFalse((R / SELDIR).exists() and any((R / SELDIR).iterdir()))
        self.assertEqual(calls(R, 'jobs'), [])
        self.assertEqual([c['stage'] for c in calls(R, 'select')], ['lease_s1'])   # stopped at the first error
        self.assertEqual(state(R)['driver']['status'], 'ALERT')
        n = len(calls(R))
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('ALERT.txt exists', p.stderr)
        self.assertEqual(len(calls(R)), n)
        self.assertEqual(state(R)['driver']['status'], 'ALERT (unresolved)')

    def test_all_routes_dropped_alerts(self):
        # select_stage exit 3 because every route was dropped (all jobs final): never selectable, so ALERT (not a wait)
        R = make_sandbox(self)
        (R / 'mock/scenario.json').write_text(json.dumps({'select': {'lease_s1': {'all_dropped': True}}}))
        finish_jobs(R)
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('every route of the stage was dropped', alert_text(R))
        self.assertIn('NOT SELECTED: FULL lease_s1: every route was dropped', alert_text(R))
        self.assertEqual(entries(R), {})
        self.assertEqual(calls(R, 'jobs'), [])

    def test_flag_stops_until_acknowledged(self):
        R = make_sandbox(self)
        (R / 'mock/scenario.json').write_text(json.dumps({'select': {'event_s1': {'flag': True}}}))
        finish_jobs(R)
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('FLAG s_hb1.0', alert_text(R))
        self.assertTrue((R / SELDIR / 'event_s1.json').exists())
        self.assertEqual(set(entries(R)), {'lease_s1'})                  # the lease chain ran first and advanced
        self.assertNotIn('b05_event_s2.jsonl', jobs_d(R))
        self.assertEqual([c['block'] for c in calls(R, 'jobs')], ['lease_s2'])
        (R / ALERT).rename(R / DRV / 'ALERT.1.resolved.txt')
        p = drive(R)                                                      # no acknowledgement: stops again
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('does not acknowledge', alert_text(R))
        self.assertEqual(set(entries(R)), {'lease_s1'})
        self.assertFalse(any(c['pre_exists'] for c in calls(R, 'select') if c['write']))
        (R / ALERT).rename(R / DRV / 'ALERT.2.resolved.txt')
        sel_sha = sha(R / SELDIR / 'event_s1.json')
        (R / DRV / 'FLAG_ACK_event_s1.txt').write_text(f'{sel_sha}\nInvestigated: CARLA start-up hiccup on route 101; '
                                                       'the registered rule applies.\n')
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        ent = entries(R)['event_s1']
        self.assertIn(sel_sha, ent['shas'])
        self.assertIn('FLAG_ACK_event_s1.txt', ent['text'].replace('\n  ', ' '))
        self.assertIn('b05_event_s2.jsonl', jobs_d(R))
        self.assertTrue(seal_ok(R) and verify_ok(R))

    # -------------------------------------------------------------------------------- crash and restart
    def check_first_cycle(self, R):
        self.assertEqual(alert_text(R), '')
        ents = entries(R)
        self.assertEqual(set(ents), {'lease_s1', 'event_s1'})
        text = (R / PROTO).read_text(encoding='utf-8')
        self.assertEqual([ln.strip() for ln in text.split('\n')].count(HEADING), 1)
        for s in ('lease_s1', 'event_s1'):
            self.assertEqual(text.count(f'* **{s}**, '), 1)
            self.assertIn(sha(R / SELDIR / f'{s}.json'), ents[s]['shas'])
        self.assertTrue(seal_ok(R))
        self.assertTrue(verify_ok(R))
        self.assertFalse((R / DRV / 'protocol_txn.json').exists())
        self.assertEqual(jobs_d(R), ['b01_ref.jsonl', 'b02_lease_s1.jsonl', 'b03_event_s1.jsonl', 'b04_lease_s2.jsonl',
                                     'b05_event_s2.jsonl'])
        self.assertEqual(sorted(c['block'] for c in calls(R, 'jobs')), ['event_s2', 'lease_s2'])
        writes = [c for c in calls(R, 'select') if c['write'] and c['stage'] in ('lease_s1', 'event_s1')]
        self.assertEqual(sorted(c['stage'] for c in writes), ['event_s1', 'lease_s1'])
        self.assertFalse(any(c['pre_exists'] for c in writes))
        self.assertGreaterEqual(len(launches(R)), 1)

    def test_crash_restart_idempotence(self):
        for point in ('selection_written', 'txn_begin', 'manifest_written', 'protocol_written', 'sealed',
                      'block_generated', 'copied'):
            with self.subTest(point=point):
                R = make_sandbox(self)
                finish_jobs(R)
                p = drive(R, crash=point)
                self.assertEqual(p.returncode, 70, out_of(p))
                p = drive(R)
                self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
                self.check_first_cycle(R)
                before, n = sha(R / PROTO), len(calls(R, 'jobs'))
                p = drive(R)                                              # nothing new is final: nothing changes
                self.assertEqual(p.returncode, 0, out_of(p))
                self.assertEqual(sha(R / PROTO), before)
                self.assertEqual(len(calls(R, 'jobs')), n)
                self.check_first_cycle(R)

    def test_crash_in_final_steps(self):
        R = make_sandbox(self)
        finish_jobs(R)
        p = None
        for _ in range(10):
            p = drive(R, crash='freeze_written')
            if p.returncode == 70:
                break
            self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
            finish_jobs(R)
        self.assertEqual(p.returncode, 70, out_of(p))
        self.assertTrue((R / 'outputs/framelease_v4/tuning/selection.json').exists())
        p = drive(R, crash='d1_written')
        self.assertEqual(p.returncode, 70, out_of(p))
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertTrue((R / DONE).exists())
        self.assertEqual(len(calls(R, 'freeze')), 1)
        self.assertEqual(len(calls(R, 'd1')), 1)
        text = (R / PROTO).read_text(encoding='utf-8')
        self.assertEqual(text.count('* **Tuning freeze**, '), 1)
        self.assertEqual(text.count('* **D1 summary**, '), 1)
        self.assertTrue(seal_ok(R) and verify_ok(R))

    # -------------------------------------------------------------------------------- runner
    def test_runner_relaunch_rules(self):
        with self.subTest('queue empty exit: launch after the copy'):
            R = make_sandbox(self)
            finish_jobs(R)
            p = drive(R)
            self.assertEqual(p.returncode, 0, out_of(p))
            self.assertEqual([ln.split()[1:] for ln in launches(R)], [[QREL], [QREL]])   # lease_s2, event_s2
        with self.subTest('a runner holds runner.lock: no launch'):
            R = make_sandbox(self)
            finish_jobs(R, runner_exit=False)
            holder = LockHolder(R / QREL / 'runner.lock')
            try:
                p = drive(R)
            finally:
                holder.stop()
            self.assertEqual(p.returncode, 0, out_of(p))
            self.assertEqual(launches(R), [])
            self.assertIn('b04_lease_s2.jsonl', jobs_d(R))
        with self.subTest('circuit breaker: ALERT, no launch'):
            R = make_sandbox(self)
            finish_jobs(R, exit_reason='circuit breaker: 6 failed attempts in a row', exit_code=3)
            p = drive(R)
            self.assertEqual(p.returncode, 1, out_of(p))
            self.assertIn('circuit breaker', alert_text(R))
            self.assertEqual(launches(R), [])
        with self.subTest('signal exit (exit 4): attention, no launch, the stage still advances'):
            R = make_sandbox(self)
            finish_jobs(R, exit_reason='signal 15', exit_code=4)
            p = drive(R)
            self.assertEqual(p.returncode, 0, out_of(p))
            self.assertEqual(launches(R), [])
            self.assertEqual(alert_text(R), '')
            self.assertIn('b04_lease_s2.jsonl', jobs_d(R))
            self.assertTrue(any('stopped by a signal' in a for a in state(R)['attention']), state(R)['attention'])
        with self.subTest('STOP in the queue: no launch, attention, STOP kept'):
            R = make_sandbox(self)
            finish_jobs(R)
            (R / QREL / 'STOP').write_text('disk_watchdog: 4.2 GiB free < 5 GiB\n')
            p = drive(R)
            self.assertEqual(p.returncode, 0, out_of(p))
            self.assertEqual(launches(R), [])
            self.assertEqual(alert_text(R), '')
            self.assertTrue((R / QREL / 'STOP').exists())
            self.assertTrue(any('STOP exists' in a for a in state(R)['attention']), state(R)['attention'])
        with self.subTest('launch_queue.sh fails: ALERT'):
            R = make_sandbox(self)
            finish_jobs(R)
            (R / 'mock/launch_fail').write_text('')
            p = drive(R)
            self.assertEqual(p.returncode, 1, out_of(p))
            self.assertIn('launch_queue.sh exited 1', alert_text(R))

    # -------------------------------------------------------------------------------- protocol lock and registration
    def test_protocol_lock_contention(self):
        R = make_sandbox(self)
        finish_jobs(R)
        before = sha(R / PROTO)
        holder = LockHolder(R / 'framelease_v4/.protocol.lock')
        try:
            t0 = time.monotonic()
            p = drive(R)
            elapsed = time.monotonic() - t0
        finally:
            holder.stop()
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(alert_text(R), '')
        self.assertEqual(sha(R / PROTO), before)
        self.assertTrue((R / SELDIR / 'lease_s1.json').exists() and (R / SELDIR / 'event_s1.json').exists())
        st = state(R)
        self.assertEqual(st['stages']['lease_s1']['status'], 'waiting_lock')
        self.assertEqual(st['stages']['event_s1']['status'], 'waiting_lock')
        self.assertNotIn('b04_lease_s2.jsonl', jobs_d(R))
        self.assertEqual(calls(R, 'jobs'), [])
        self.assertLess(elapsed, 60)
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p))
        self.check_first_cycle(R)
        self.assertEqual(len([c for c in calls(R, 'select') if c['stage'] == 'lease_s1']), 1)

    def test_unsealed_edit_or_changed_registered_file_alerts(self):
        with self.subTest('unsealed edit of PROTOCOL.md'):
            R = make_sandbox(self)
            finish_jobs(R)
            with open(R / PROTO, 'a', encoding='utf-8') as f:
                f.write('\nA foreign line that was never sealed.\n')
            before = sha(R / PROTO)
            p = drive(R)
            self.assertEqual(p.returncode, 1, out_of(p))
            self.assertIn('unsealed edit', alert_text(R))
            self.assertEqual(sha(R / PROTO), before)
            self.assertEqual(entries(R), {})
        with self.subTest('registered file changed after the seal'):
            R = make_sandbox(self)
            finish_jobs(R)
            (R / 'framelease_v4/protocol/tool.py').write_text('# changed after the seal\n')
            man = sha(R / MANIFEST)
            p = drive(R)
            self.assertEqual(p.returncode, 1, out_of(p))
            self.assertIn('differ from the sealed manifest', alert_text(R))
            self.assertIn('tool.py', alert_text(R))
            self.assertEqual(entries(R), {})
            self.assertEqual(sha(R / MANIFEST), man)

    def test_refuses_to_run_niced(self):
        # a runner launched by a niced driver would inherit its priority (scheduler CPU time is charged to the timeline)
        R = make_sandbox(self)
        finish_jobs(R)
        cmd = ['nice', '-n', '5', PY, '-I', '-B', str(DRIVER), '--root', str(R), '--python', PY, '--once',
               '--select-script', str(R / 'mock/select_stage.py'), '--no-chain-check']
        p = run(cmd, R, 60)
        self.assertEqual(p.returncode, 2, out_of(p))
        self.assertIn('nice', p.stderr)
        self.assertEqual(calls(R, 'select'), [])                       # nothing ran (only the sandbox set-up)
        self.assertFalse((R / 'outputs/framelease_v4/pipeline_state.json').exists())

    # -------------------------------------------------------------------------------- registered vs swept-in files
    def test_unregistered_files_may_change_between_seals(self):
        # code in development under framelease_v4/ enters the manifest by its glob; editing it does not stop P1
        R = make_sandbox(self)
        dev = R / 'framelease_v4/protocol/dev_p2_jobs.py'
        dev.write_text('# P2 generator, in development\n')
        finish_jobs(R, only=lambda j: j['block'] in ('ref', 'lease_s1'), runner_exit=False)
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertEqual(set(entries(R)), {'lease_s1'})
        self.assertIn('`framelease_v4/protocol/dev_p2_jobs.py`', flat(R, 'lease_s1').split('new in it')[1])
        base = json.loads((R / DRV / 'registered_baseline.json').read_text())
        self.assertIn('framelease_v4/protocol/tool.py', base['files'])          # the sandbox registration
        self.assertNotIn('framelease_v4/protocol/dev_p2_jobs.py', base['files'])
        dev.write_text('# P2 generator, in development (edited)\n')
        finish_jobs(R, only=lambda j: j['block'] == 'event_s1', runner_exit=False)
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertEqual(alert_text(R), '')
        self.assertIn('changed since the previous seal (not registered files): '
                      '`framelease_v4/protocol/dev_p2_jobs.py`', flat(R, 'event_s1'))
        self.assertIn('b05_event_s2.jsonl', jobs_d(R))
        self.assertTrue(seal_ok(R) and verify_ok(R))

    def test_change_while_resealing(self):
        with self.subTest('unregistered file: tolerated, named at the next seal'):
            R = make_sandbox(self)
            dev = R / 'framelease_v4/protocol/dev_p2_jobs.py'
            dev.write_text('# in development\n')
            finish_jobs(R, only=lambda j: j['block'] in ('ref', 'lease_s1'), runner_exit=False)
            p = drive(R, touch='protocol_written:framelease_v4/protocol/dev_p2_jobs.py')
            self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
            self.assertEqual(alert_text(R), '')
            self.assertTrue(seal_ok(R))
            self.assertFalse(verify_ok(R))                    # the edited file differs from the sealed manifest
            self.assertIn('b04_lease_s2.jsonl', jobs_d(R))     # the stage advanced
            self.assertTrue(any('changed while the driver re-sealed' in a for a in state(R)['attention']),
                            state(R)['attention'])
            finish_jobs(R, only=lambda j: j['block'] == 'event_s1', runner_exit=False)
            p = drive(R)
            self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
            self.assertIn('`framelease_v4/protocol/dev_p2_jobs.py`',
                          flat(R, 'event_s1').split('changed since the previous seal')[1])
            self.assertTrue(seal_ok(R) and verify_ok(R))
        with self.subTest('registered file: ALERT, the block is not generated'):
            R = make_sandbox(self)
            finish_jobs(R, only=lambda j: j['block'] in ('ref', 'lease_s1'), runner_exit=False)
            p = drive(R, touch='protocol_written:framelease_v4/protocol/tool.py')
            self.assertEqual(p.returncode, 1, out_of(p))
            self.assertIn('registration.py --verify', alert_text(R))
            self.assertNotIn('b04_lease_s2.jsonl', jobs_d(R))
            self.assertEqual(calls(R, 'jobs'), [])
        with self.subTest('registered file changed between the pre-check and --write-manifest: ALERT, not sealed'):
            R = make_sandbox(self)
            finish_jobs(R, only=lambda j: j['block'] in ('ref', 'lease_s1'), runner_exit=False)
            tool = R / 'framelease_v4/protocol/tool.py'
            orig, seal_before = tool.read_text(), (R / SEAL).read_text()
            p = drive(R, touch='txn_begin:framelease_v4/protocol/tool.py')
            self.assertEqual(p.returncode, 1, out_of(p))
            self.assertIn('changed while the driver re-sealed', alert_text(R))
            self.assertIn('framelease_v4/protocol/tool.py', alert_text(R))
            self.assertEqual((R / SEAL).read_text(), seal_before)          # nothing was sealed
            self.assertNotIn('lease_s1', entries(R))
            self.assertNotIn('b04_lease_s2.jsonl', jobs_d(R))
            self.assertEqual(calls(R, 'jobs'), [])
            tool.write_text(orig)                                             # restore the registered file, restart
            (R / ALERT).rename(R / DRV / 'ALERT.resolved.txt')
            p = drive(R)
            self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
            self.assertEqual(sum(1 for k in entries(R) if k == 'lease_s1'), 1)
            self.assertEqual((R / PROTO).read_text().count('**lease_s1**'), 1)
            self.assertTrue(seal_ok(R) and verify_ok(R))
            self.assertIn('b04_lease_s2.jsonl', jobs_d(R))
            self.assertFalse((R / DRV / 'protocol_txn.json').exists())

    def test_other_seal_registers_cited_files_only(self):
        R = make_sandbox(self)
        a, b = R / 'framelease_v4/protocol/new_a.py', R / 'framelease_v4/protocol/new_b.py'
        finish_jobs(R, only=lambda j: j['block'] in ('ref', 'lease_s1'), runner_exit=False)
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        a.write_text('# registered by amendment X\n')
        b.write_text('# swept in by the manifest glob\n')
        foreign_amendment(R, f'**Amendment X (test).** New file `framelease_v4/protocol/new_a.py` (sha256 `{sha(a)}`).')
        p = drive(R)                                            # nothing new is final; the cycle reads the new seal
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        base = json.loads((R / DRV / 'registered_baseline.json').read_text())
        self.assertEqual(base['manifest_sha256'], sha(R / MANIFEST))
        self.assertIn('framelease_v4/protocol/new_a.py', base['files'])
        self.assertNotIn('framelease_v4/protocol/new_b.py', base['files'])
        self.assertIn('framelease_v4/protocol/tool.py', base['files'])
        b.write_text('# edited: not registered, allowed\n')
        a.write_text('# edited without an amendment\n')
        finish_jobs(R, only=lambda j: j['block'] == 'event_s1', runner_exit=False)
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('new_a.py', alert_text(R))
        self.assertNotIn('new_b.py', alert_text(R))
        self.assertNotIn('event_s1', entries(R))
        self.assertNotIn('b05_event_s2.jsonl', jobs_d(R))

    # -------------------------------------------------------------------------------- start script
    def test_start_script_single_instance(self):
        R = make_sandbox(self)                         # nothing final: the started driver waits and keeps its lock
        pdir = R / 'framelease_v4/protocol'
        shutil.copyfile(DRIVER, pdir / 'p1_driver.py')
        shutil.copyfile(START, pdir / 'start_p1_driver.sh')
        for name in ('mockcommon.py', 'select_stage.py', 'p1_jobs.py', 'd1_summary.py', 'launch_queue.sh'):
            shutil.copyfile(R / 'mock' / name, pdir / name)
        shutil.copyfile(R / 'mock/registration_sandbox.py', pdir / 'registration.py')
        (R / '.conda-unidrive-linux/bin').mkdir(parents=True)
        os.symlink(PY, R / '.conda-unidrive-linux/bin/python')
        env = {k: v for k, v in os.environ.items() if k not in (CRASH_ENV, TOUCH_ENV)}
        start = ['bash', str(pdir / 'start_p1_driver.sh'), '--no-chain-check', '--interval-s', '3600',
                 '--allow-nice-launch']
        p = run(start, R, 60, env)
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertIn('started p1_driver pid', p.stdout)
        pid = int((R / DRV / 'driver.pid').read_text())
        try:
            self.assertIn('p1_driver.py', Path(f'/proc/{pid}/cmdline').read_bytes().decode(errors='replace'))
            p2 = run(start, R, 60, env)
            self.assertEqual(p2.returncode, 2, out_of(p2))
            self.assertIn('another p1_driver holds', p2.stderr)
            # the running driver does not keep start.lock; a start while another start runs is refused
            probe = run([PY, '-I', '-B', '-c', 'import fcntl, os, sys; fd = os.open(sys.argv[1], os.O_RDWR); '
                         'fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); print("free")', str(R / DRV / 'start.lock')],
                        R, 30)
            self.assertEqual(probe.stdout.strip(), 'free', out_of(probe))
            holder = LockHolder(R / DRV / 'start.lock')
            try:
                p2b = run(start, R, 60, env)
            finally:
                holder.stop()
            self.assertEqual(p2b.returncode, 2, out_of(p2b))
            self.assertIn('another start_p1_driver.sh is running', p2b.stderr)
            p3 = run([PY, '-I', '-B', str(pdir / 'p1_driver.py'), '--once', '--no-chain-check',
                      '--allow-nice-launch'], R, 60, env)
            self.assertEqual(p3.returncode, 2, out_of(p3))
            self.assertIn('another instance holds', p3.stderr)
            (R / DRV / 'STOP').write_text('')
            for _ in range(40):
                if not Path(f'/proc/{pid}').exists():
                    break
                time.sleep(0.25)
            self.assertFalse(Path(f'/proc/{pid}').exists())
            self.assertFalse((R / DRV / 'driver.pid').exists())
            p4 = run(start, R, 60, env)
            self.assertEqual(p4.returncode, 2, out_of(p4))
            self.assertIn('STOP exists', p4.stderr)
            (R / DRV / 'STOP').unlink()
            p5 = run(start, R, 60, env)
            self.assertEqual(p5.returncode, 0, out_of(p5))
            pid = int((R / DRV / 'driver.pid').read_text())
            os.kill(pid, signal.SIGTERM)
            for _ in range(40):
                if not Path(f'/proc/{pid}').exists():
                    break
                time.sleep(0.25)
            self.assertFalse(Path(f'/proc/{pid}').exists())
            log = (R / DRV / 'driver.log').read_text()
            self.assertIn('signal 15', log)
            self.assertEqual(state(R)['driver']['status'], 'stopped')
        finally:
            if Path(f'/proc/{pid}').exists():
                os.kill(pid, signal.SIGKILL)


if __name__ == '__main__':
    unittest.main()
