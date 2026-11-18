"""Phase driver after P1 (framelease_v4/protocol/phase_driver.py and start_phase_driver.sh; PROTOCOL Secs. 4.8, 5.3,
5.9, 7.6, 8.1, 9.11, 9.12, 13.2; GAP_AUDIT Sec. 3.6, item E-2): the gates G0-G8. CPU only, /tmp sandboxes only: the
driver runs as a subprocess with --root <sandbox>; p2_jobs.py, p2_check.py, p3_rl.py, stress_bench.py, test_jobs.py,
test_freeze.py, aggregate_v4.py, launch_queue.sh and systemd-run are mocks written into the sandbox that log their
calls (they read synthetic queue records and write synthetic job files, reports and freezes in the tools' formats; the
aggregate mock refuses a cross-arm test-route summary as the real guard does); registration.py is the
REAL module with its paths pointed at the sandbox by a wrapper, so the seal rule is the real one. The sandbox
PROTOCOL.md is a copy of the real one (driver subsections removed, real amendment titles renamed) with a synthetic P1
driver block (Tuning freeze, D1 summary) and synthetic amendment titles (A7 titled as the variant A7b); stand-ins for
the code G4 and G6 check (framelease_v4/rl, check_smoke_ext.py, arms_ext) are registered by the first seal (the mock
tools lie outside framelease_v4/ and are not checked). Nothing outside /tmp is written; no GPU, no
CARLA, no runner, no systemd scope. The last check compares the real registration, PROTOCOL.md and queue files.

  cd /home/kang/Desktop/DAC && OMP_NUM_THREADS=1 taskset -c 12-15 nice -n 19 ionice -c 3 \
      .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/protocol/tests/test_phase_driver.py

What is shown:
  * the entry form: the heading "**Phase gates (P2-P7, FULL).**" is created once, after the P1 driver's block and the
    amendments and before "Each amendment gets the date and time"; the P1 driver's entries are unchanged and
    p1_driver.ENTRY_RE never reads an entry of this driver;
  * G0 waits without an ALERT for P1_DONE.json, the P1 entries, Amendments A3, A4, A7, A9 and a verified seal;
  * dry run: plan only, no file changes, no lock file;
  * the full chain G0 -> G8 to PHASES_DONE.json (test_full_chain_to_phases_done); on the way G1 -> G2 -> G3: the D1
    decision recorded (citing its sha256 and the delegation of 2026-11-14); the P2 job
    file generated once (linux/env.sh sourced, CUDA hidden), recorded with its spec and check sha256 BEFORE the copy,
    copied once, the runner launched once through systemd-run --user --scope --unit=framelease-p2-runner-<ts> -p
    OOMPolicy=continue bash launch_queue.sh outputs/framelease_v4/queue_p2; after every job is final the completion
    check (without, then with --write) and the data manifest recorded; seal and --verify OK;
  * G4 waits while a runner of another queue of the project is alive; G6 waits (no ALERT) when PROTOCOL.md is not
    sealed right after test_jobs.py;
  * on to G6 in one cycle: P3 (run --stop-after dataset, calibrate at the production sizes 33,66,132 on the
    dataset's lengths with d*, run with the recommended --n-jobs, status; the RL freeze validated and recorded with
    the calibration and network sha256); the stress tests s3, s2 (registered grid), s2 --grid relative (Amendment
    A7) and s1 on L* and the deployed networks, recorded together; test_jobs.py once (env.sh, CUDA hidden),
    test_freeze.py --write / --entry, the entry text nested under the G6 bullet (the same words, 120 columns, sha256
    on one line), --verify before and after the copies, the five job files copied in tier order after the entry, the
    runner of queue_p4 launched in a scope framelease-p4-runner-<ts>; a further cycle runs no tool;
  * G7 (job health only): the progress per job file (counts only, no outcome) in state.json; passed when every job is
    final and the runner has exited; G8 waits (attention, no ALERT, no aggregation) for analyze_v4.py and for its
    citation in Sec. 13.2; then one aggregate_v4.py --write-freeze-record over queue_p4 (never --arm-summary, never
    --analysis-freeze; no aggregation of any kind before G8), the record validated and recorded (record, SHA256SUMS,
    analyze_v4.py by the amendment that registers it, the analysis modules, the job status), PHASES_DONE.json, every
    gate passed; a restart does nothing;
  * P4-P6 runner rules on queue_p4: a signal exit is not relaunched; 'queue empty' with pending jobs is relaunched in
    a scope framelease-p4-runner-<ts> (systemd-run --user --scope -p OOMPolicy=continue); STOP with and without a live
    runner: attention, no launch; circuit breaker: ALERT; every job final while the runner lives: wait; a job file the
    test freeze does not name: attention at G7, ALERT at G8; a dry run at G8 plans the aggregation and changes nothing;
  * G8 ALERTs: the aggregation fails (exit 2); an analysis module changed while the record was made; a record of
    other job files (kept, never rewritten, the same ALERT after a restart); two final_* directories; the outputs of an
    aggregation stopped before its record are redone with --force; a crash at every G8 point (after the aggregation,
    in the record transaction): one entry, one aggregation after the crash, PHASES_DONE.json once;
  * P3 open cases: exit 4 -> ALERT naming the case; a malformed P3_OPEN_CASES.json -> ALERT; the decision passed to
    the run and cited; case (c) follows from the G3 acknowledgement;
  * stress: a failing S2 -> ALERT, never rerun over the report; the S1 guard: foreign CPU (the driver's sample or
    stress_bench's refusal) retried, ALERT after 3 retries (the series closed), a project runner -> wait (not
    counted), S1_ACCEPT_FOREIGN_CPU.txt -> --accept-foreign-cpu, cited;
  * crash / restart at every G3-G6 point (P3 steps, record transactions, stress runs, test_jobs / test_freeze, copy,
    P4_QUEUED.json, launch): each entry once, one calibration, one full P3 run, each stress run once, one test_jobs,
    each job file copied once, one launch per queue;
  * D1 'stop': recorded, P2_STOPPED.json, no P2 file, a restart does nothing; a decision on another D1 summary: ALERT;
  * crash / restart at every point (record transaction steps, P2 generated, copied, launched, P2 check written): each
    entry once, one generation, one copy, one launch, one --write;
  * p2_check FAIL: ALERT, nothing written; missing episodes: ALERT until P2_MISSING_ACK.txt names them, then the
    entry cites the acknowledgement;
  * runner rules on queue_p2: a signal exit is not relaunched; 'queue empty' with pending jobs is relaunched in a
    scope; STOP or a live runner of another queue: no launch; circuit breaker: ALERT;
  * the protocol lock held elsewhere: no record, no ALERT, recorded after release;
  * a registered file changed: ALERT before any entry; an unregistered file may change and is named;
  * review fixes: M1 a registration-only amendment ("A3b", the manifest of the driver's last seal unchanged) enters
    the driver baseline; M2 a tool still running (a registration.py at G0, a stress_bench.py at G5): wait with
    attention, the tool is not started again; M3 a registered file removed between the pre-check and --write-manifest:
    ALERT, nothing sealed; M4 an unregistered file under framelease_v4/rl: G4 waits (attention, no P3 tool) until an
    amendment cites it; S1/S2 the G1 wording (the instruction quoted in translation, the date once) and no line
    numbers of other entries; S3 SHA256SUMS checked (sha256sum -c) before the G8 entry; S4 the relative S2 grid only
    under A7b (unit test with the draft texts); S5 a decision file being written: wait, then ALERT; S6 an emptied
    queue_p2/jobs.d at G3: ALERT; S8 no relaunch after a second 'queue empty' exit in a row without a job started;
  * the tool priority (nice 10, or E-cores at nice 19 while a closed-loop job runs; P3 and stress: every core at nice
    10); refusal to run niced or pinned to some CPUs;
  * the nested entry form (unit test) and the driver's copies of the tools' constants (read from the real sources);
  * start_phase_driver.sh: a CPU-pinned shell refused; started in a (mock) scope framelease-phase-driver-<ts>, single
    instance, STOP / ALERT refusals, SIGTERM.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DRIVER = ROOT / 'framelease_v4/protocol/phase_driver.py'
P1DRIVER = ROOT / 'framelease_v4/protocol/p1_driver.py'
START = ROOT / 'framelease_v4/protocol/start_phase_driver.sh'
REAL_PROTOCOL = ROOT / 'framelease_v4/PROTOCOL.md'
REAL_REGISTRATION = ROOT / 'framelease_v4/protocol/registration.py'
REAL_REG_DIR = ROOT / 'outputs/framelease_v4/registration'
PY = sys.executable
CRASH_ENV = 'PHASE_DRIVER_TEST_CRASH_AT'
TOUCH_ENV = 'PHASE_DRIVER_TEST_TOUCH_AT'
HEADING = '**Phase gates (P2-P7, FULL).**'
P1_HEADING = '**Stage selections (P1, FULL).**'
ANCHOR = 'Each amendment gets the date and time'
PROTO = 'framelease_v4/PROTOCOL.md'
DRV = 'outputs/framelease_v4/phase_driver'
P1D = 'outputs/framelease_v4/p1_driver'
ALERT = f'{DRV}/ALERT.txt'
Q2 = 'outputs/framelease_v4/queue_p2'
Q1 = 'outputs/framelease_v4/queue_p1'
P2FILES = 'outputs/framelease_v4/p2_jobs/FULL/b10_rl_data'
RLDATA = 'outputs/framelease_v4/rl_data'
MANIFEST = 'outputs/framelease_v4/registration/MANIFEST.sha256'
SEAL = 'outputs/framelease_v4/registration/SEAL.sha256'
FREEZE = 'outputs/framelease_v4/tuning/selection.json'
ENVELOPE = 'outputs/framelease_v4/envelopes/E5.json'
Q4 = 'outputs/framelease_v4/queue_p4'
RLF = 'outputs/framelease_v4/rl_freeze/rl_freeze.json'
CAL = 'outputs/framelease_v4/build/phase_driver/p3_calibration.json'
STRESS = 'outputs/framelease_v4/stress'
TFREEZE = 'outputs/framelease_v4/test_freeze/test_freeze.json'
FOREIGN_ENV = 'PHASE_DRIVER_TEST_FOREIGN_CPU'
P4_NAMES = ['b11_ti_main.jsonl', 'b12_f3_k.jsonl', 'b13_a_lease.jsonl', 'b14_a_rl.jsonl', 'b15_s_seed12.jsonl']
LABELS = {'d1_decision': 'G1 D1 decision', 'p2_jobs': 'G2 P2 job file', 'p2_data': 'G3 P2 data manifest',
          'rl_freeze': 'G4 RL freeze', 'stress': 'G5 Stress tests', 'test_freeze': 'G6 Test freeze'}
ANALYSIS = 'outputs/framelease_v4/analysis'
ANALYZE = 'framelease_v4/analysis/analyze_v4.py'
ANALYSIS_FILES = [f'framelease_v4/analysis/{m}' for m in ('aggregate_v4.py', 'extra_metrics.py', 'commit_audit.py',
                                                          'manipulation.py', 'interim_guard.py')]
DONE = 'outputs/framelease_v4/phase_driver/PHASES_DONE.json'
CODE_STANDINS = ('framelease_v4/rl/qnet.py', 'framelease_v4/protocol/check_smoke_ext.py',
                 'framelease_v4/arms_ext/__init__.py')
A7B_TITLE = ("a supplementary S2 grid relative to each state's Eq. 5 slack floor (`s2 --grid relative`)")
D1JSON = 'outputs/framelease_v4/tuning/d1/FULL_d1_summary.json'
SCRATCH = Path('/tmp/PHASE')

sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location('phase_driver_under_test', DRIVER)
D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(D)
P1 = D.P1

ENV_SH = 'export PHD_ENV_SOURCED=1\nexport CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"\n'

MOCKCOMMON = r'''
import hashlib, json, os, sys, time
from pathlib import Path

R = Path.cwd()
Q2 = R / 'outputs/framelease_v4/queue_p2'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def log_call(tool, **extra):
    with open(R / 'mock/calls.jsonl', 'a') as f:
        f.write(json.dumps({'tool': tool, 'argv': sys.argv[1:], 't': time.time(), 'nice': os.nice(0),
                            'env_sourced': os.environ.get('PHD_ENV_SOURCED'),
                            'cuda': os.environ.get('CUDA_VISIBLE_DEVICES'), **extra}) + '\n')


def scenario():
    p = R / 'mock/scenario.json'
    return json.loads(p.read_text()) if p.exists() else {}


def opt(a, name, default=None):
    return a[a.index(name) + 1] if name in a else default
'''

MOCK_P2_JOBS = r'''
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mockcommon as M

a = sys.argv[1:]
M.log_call('p2_jobs')
if not ('--check' in a and '--write' in a) or '--variant' in a:
    print('usage: p2_jobs.py [--check] [--write] [--jobs-dir DIR]', file=sys.stderr)
    sys.exit(2)
if os.environ.get('PHD_ENV_SOURCED') != '1' or os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    print('ERROR: linux/env.sh not sourced or CUDA not hidden', file=sys.stderr)
    sys.exit(1)
proto = (M.R / 'framelease_v4/PROTOCOL.md').read_text()
fz = M.R / 'outputs/framelease_v4/tuning/selection.json'
fsha = M.sha(fz)
seal_lines = (M.R / 'outputs/framelease_v4/registration/SEAL.sha256').read_text().splitlines()
seal = dict(reversed(ln.split('  ', 1)) for ln in seal_lines)
if fsha not in proto or seal.get('framelease_v4/PROTOCOL.md') != M.sha(M.R / 'framelease_v4/PROTOCOL.md'):
    print('REFUSED: the freeze is not cited in Sec. 13.2 or PROTOCOL.md is not sealed', file=sys.stderr)
    sys.exit(2)
if M.scenario().get('p2_jobs_fail'):
    print('CHECK FAILED\n  synthetic problem', file=sys.stderr)
    sys.exit(1)
base = M.R / M.opt(a, '--jobs-dir') / 'FULL' / 'b10_rl_data'
lines = []
for i, (r, k) in enumerate([(r, k) for r in ('101', '102') for k in (1.0, 1.5, 2.0)]):
    lines.append({'id': f'v4p2_fl_behaviour_E5_eps0.300_d4_k{k:.1f}_s11_r{r}', 'kind': 'closed_loop', 'tier': 2,
                  'cmd': ['true'], 'wall_cap_s': 60, 'block': 'rl_data', 'block_no': 10, 'route_id': r, 'kappa': k,
                  'training_route': True, 'output_dir': f'outputs/framelease_v4/rl_data/k{k:.1f}',
                  'tuning_freeze': {'path': 'outputs/framelease_v4/tuning/selection.json', 'sha256': fsha},
                  'require_sha256': {}})
text = ''.join(json.dumps(j, sort_keys=True) + '\n' for j in lines)
jp, sp, cp = (Path(str(base) + s) for s in ('.jsonl', '.stage.json', '.check.json'))
js = __import__('hashlib').sha256(text.encode()).hexdigest()
spec = {'schema': 'framelease_v4.p2_stage/1', 'variant': 'FULL', 'phase': 'P2', 'block': 'rl_data', 'block_no': 10,
        'tier': 2, 'arm': 'fl_behaviour', 'eps': 0.3, 'kappas': [1.0, 1.5, 2.0], 'seed': 11, 'route_set': 'RL',
        'routes': ['101', '102'], 'n_lines': len(lines), 'runs_per_kappa': {'1.0': 2, '1.5': 2, '2.0': 2},
        'L_star': {'label': 'E5', 'path': 'outputs/framelease_v4/envelopes/E5.json', 'sha256': '5' * 64},
        'd_star': {'d': 4, 'utility': 'v4_adet_d4'},
        'code_pins': {'n': 50, 'sha256': '6' * 64,
                      'rule': 'framelease_v4/arms/jobs_v4.code_pins([L*]) (PROTOCOL Sec. 8.3)'},
        'tuning_freeze': {'path': 'outputs/framelease_v4/tuning/selection.json', 'sha256': fsha},
        'queue': 'outputs/framelease_v4/queue_p2', 'order_rule': 'routes shuffled with random.Random(20261110 + 10)',
        'job_file': str(jp.relative_to(M.R)), 'job_file_sha256': js}
check = {'schema': 'framelease_v4.p2_check/1', 'job_file': spec['job_file'], 'job_file_sha256': js,
         'n_lines': len(lines), 'problems': [], 'all_dry_runs_ok': True, 'lines': []}
todo = ((jp, text), (sp, json.dumps(spec, indent=1, sort_keys=True) + '\n'),
        (cp, json.dumps(check, indent=1, sort_keys=True) + '\n'))
for p, new in todo:
    if p.exists() and p.read_text() != new:
        print(f'REFUSED: refusing to overwrite {p} with other content', file=sys.stderr)
        sys.exit(2)
jp.parent.mkdir(parents=True, exist_ok=True)
for p, new in todo:
    p.write_text(new)
print(f'P2 block rl_data (no. 10): {len(lines)} job lines -> {spec["job_file"]} (NOT launched)')
print(json.dumps({'job_file': spec['job_file'], 'sha256': js}, indent=1))
'''

MOCK_P2_CHECK = r'''
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mockcommon as M

a = sys.argv[1:]
write = '--write' in a
M.log_call('p2_check', write=write)
q = M.R / M.opt(a, '--queue')
jf = M.R / M.opt(a, '--job-file')
report, manifest = M.opt(a, '--report'), M.opt(a, '--manifest')
jobs = [json.loads(ln) for ln in jf.read_text().splitlines() if ln.strip()]
finals = {}
st = q / 'status.jsonl'
for ln in st.read_text().splitlines():
    r = json.loads(ln)
    if r.get('event') == 'end' and r.get('final'):
        finals[r['id']] = r
sc = M.scenario()
pending = [j['id'] for j in jobs if j['id'] not in finals]
missing_ids = sc.get('p2_missing') or []
verdict = 'FAIL' if sc.get('p2_fail') else ('INCOMPLETE' if pending else 'PASS')
episodes = [{'job': j['id'], 'kappa': j['kappa'], 'route_id': j['route_id']} for j in jobs
            if j['id'] not in pending and j['id'] not in missing_ids]
missing = [{'job': i, 'cause': 'Simulation crashed (twice)'} for i in missing_ids]
print(f'P2 check: {verdict}  ({len(jobs)} jobs: {len(episodes)} episodes, {len(missing)} missing, '
      f'{len(pending)} pending)')
for m in missing:
    print(f'  missing episode {m["job"]}: {m["cause"]}')
common = {'variant': 'FULL', 'phase': 'P2', 'job_file': M.opt(a, '--job-file'), 'job_file_sha256': M.sha(jf),
          'queue': M.opt(a, '--queue'), 'status_jsonl_sha256': M.sha(st), 'n_jobs': len(jobs),
          'episodes_per_kappa': {k: sum(1 for e in episodes if f'{e["kappa"]:.1f}' == k)
                                 for k in ('1.0', '1.5', '2.0')}}
rep = {'schema': 'framelease_v4.p2_completion_check/1', 'verdict': verdict, **common,
       'counts': {'episode': len(episodes), 'missing': len(missing), 'pending': len(pending), 'error': 0,
                  'failed_criteria': 0}, 'missing': missing, 'written': time.strftime('%Y-%m-%dT%H:%M:%S%z')}
man = None
if verdict == 'PASS':
    man = {'schema': 'framelease_v4.p2_data_manifest/1', **common, 'n_episodes': len(episodes), 'episodes': episodes,
           'n_missing': len(missing), 'missing': missing, 'excluded_runs': [],
           'written': time.strftime('%Y-%m-%dT%H:%M:%S%z')}
if write:
    for doc, rel in ((rep, report), (man, manifest)):
        if doc is None:
            print(f'no data manifest written (verdict {verdict})')
            continue
        p = M.R / rel
        if p.exists():
            old = json.loads(p.read_text())
            if {k: v for k, v in old.items() if k != 'written'} == {k: v for k, v in doc.items() if k != 'written'}:
                print(f'unchanged {rel}  sha256 {M.sha(p)}')
                continue
            print(f'ERROR: refusing to overwrite {rel} with a different document (use --force)', file=sys.stderr)
            sys.exit(2)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n')
        print(f'wrote {rel}  sha256 {M.sha(p)}')
sys.exit({'PASS': 0, 'FAIL': 1, 'INCOMPLETE': 3}[verdict])
'''

MOCK_LAUNCH = r'''#!/usr/bin/env bash
# records the call; like the real runner, the "started" runner appends its runner_start record (it never holds the lock)
echo "$(date +%s.%N) $*" >> "$PWD/mock/launch_calls.log"
if [ -e "$PWD/mock/launch_fail" ]; then echo "launch_queue: the runner did not start" >&2; exit 1; fi
echo '{"event": "runner_start", "pid": 99999, "utc": "mock"}' >> "$PWD/$1/status.jsonl"
echo "started runner pid 99999 and disk watchdog pid 99998"
'''

MOCK_SYSTEMD_RUN = r'''#!/usr/bin/env bash
# stands in for systemd-run --user --scope: records the call, drops the options, runs the command in place
echo "$*" >> "$PWD/mock/systemd_calls.log"
while [ $# -gt 0 ]; do
    case "$1" in
        -p) shift 2 ;;
        --*) shift ;;
        *) break ;;
    esac
done
exec "$@"
'''

MOCK_P3_RL = r'''
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mockcommon as M

a = sys.argv[1:]
sub = a[0]
M.log_call('p3_rl', sub=sub)
sc = M.scenario()
out = M.R / M.opt(a, '--out', 'outputs/framelease_v4/rl_freeze')
if sub == 'calibrate':
    lengths = M.opt(a, '--lengths-from')
    if not (M.R / lengths / 'episodes.json').is_file():
        print('ERROR: FileNotFoundError: no dataset', file=sys.stderr)
        sys.exit(1)
    doc = {'schema': 'framelease_v4.p3_rl_calibration/1', 'kind': 'production size',
           'probe': {'sizes': [int(x) for x in M.opt(a, '--sizes').split(',')]},
           'target': {'d_star': int(M.opt(a, '--d-star')), 'lengths': lengths, 'n_episodes': 6},
           'recommendation': {'n_jobs': sc.get('cal_n_jobs', 6), 'worst_case_wall_s': 5400.0},
           'memory': {'probe_max_rss_mb': sc.get('cal_rss_mb', 50.0)}}
    (M.R / M.opt(a, '--out')).write_text(json.dumps(doc, indent=1) + '\n')
    print(f'calibrate: n_jobs {doc["recommendation"]["n_jobs"]}')
    sys.exit(0)
if sub == 'status':
    sys.exit(0 if (out / 'rl_freeze.json').is_file() else 3)
man, sel = M.R / M.opt(a, '--manifest'), M.R / M.opt(a, '--selection')
mdoc = json.loads(man.read_text())
opts = {k: M.opt(a, '--' + k.replace('_', '-'), 'stop') for k in ('missing_episodes', 'no_selectable',
                                                                   'distill_shortfall')}
if mdoc.get('missing') and opts['missing_episodes'] != 'proceed':
    print(f'STOP (open case, the user decides): P2 data manifest {man.name}: {len(mdoc["missing"])} missing. GAP_AUDIT '
          'Sec. 6 item 5 (c) P2 jobs without a valid record; rerun with --missing-episodes proceed to use it',
          file=sys.stderr)
    sys.exit(4)
(out / 'dataset').mkdir(parents=True, exist_ok=True)
(out / 'stages').mkdir(parents=True, exist_ok=True)
eps = [{'job': e['job'], 'split': 'train', 'n_choice': 5} for e in mdoc['episodes']]
(out / 'dataset/episodes.json').write_text(json.dumps(eps) + '\n')
(out / 'stages/dataset.json').write_text(json.dumps({'stage': 'dataset'}) + '\n')
if M.opt(a, '--stop-after') == 'dataset':
    print('[done] dataset')
    sys.exit(0)
if sc.get('p3_stop_case') == 'no_selectable' and opts['no_selectable'] != 'adet':
    print('STOP (open case, the user decides): refit_fqi: family fqi has no selectable candidate (every candidate '
          'unsupported). GAP_AUDIT Sec. 6 item 5 (a) a family has no selectable candidate; rerun with --no-selectable '
          'adet (to be recorded in PROTOCOL Sec. 13 when used)', file=sys.stderr)
    sys.exit(4)
fams, files = {}, {}
for f, arm in (('fqi', 'fl_full'), ('bandit', 'fl_bandit'), ('fqi_nolease', 'fl_fqi_nolease')):
    qp = out / f'qnet_{f}.json'
    qp.write_text(json.dumps({'family': f, 'inputs': 10 if f == 'fqi_nolease' else 16}) + '\n')
    (out / 'stages' / f'select_{f}.json').write_text(json.dumps({'host': {'n_jobs': int(M.opt(a, '--n-jobs', '1'))}}))
    rel = str(qp.relative_to(M.R))
    fams[f] = {'arm': arm, 'network': {'path': rel, 'name': 'v4_qnet_' + M.sha(qp)[:12], 'file_sha256': M.sha(qp),
                                       'abs_path': str(qp), 'arm': arm}}
    files[rel] = M.sha(qp)
for p in (man, sel, out / 'dataset/episodes.json'):
    files[str(p.relative_to(M.R))] = M.sha(p)
devs = [{'case': k, 'option': v, 'stage': 'dataset' if k == 'missing_episodes' else 'refit_fqi'}
        for k, v in sorted(opts.items()) if v != 'stop']
doc = {'schema': 'framelease_v4.rl_freeze/1', 'variant': 'FULL', 'mode': 'production', 'frozen': True, 'd_star': 4,
       'tuning_freeze': {'path': str(sel.relative_to(M.R)), 'sha256': M.sha(sel)},
       'p2_manifest': {'path': str(man.relative_to(M.R)), 'sha256': M.sha(man)},
       'dataset': {'n_episodes': len(eps), 'n_transitions': 5 * len(eps), 'n_missing': len(mdoc.get('missing') or [])},
       'p_both': {'label': 'P_both >= 0.05'}, 'families': fams, 'files': files, 'deviations': devs,
       'code_sha256': {'p3_rl.py': M.sha(__file__)}}
(out / 'rl_freeze.json').write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n')
print('[done] freeze')
'''

MOCK_STRESS = r'''
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mockcommon as M

a = sys.argv[1:]
sub = a[0]
M.log_call('stress', sub=sub, grid=M.opt(a, '--grid'), accept='--accept-foreign-cpu' in a, states=M.opt(a, '--states'))
sc = M.scenario()
if '--registered' not in a:
    sys.exit(2)
qnets = [a[i + 1] for i, x in enumerate(a) if x == '--qnet']
nets = [{'name': 'v4_qnet_' + M.sha(q)[:12], 'file_sha256': M.sha(q)} for q in qnets]
test = sub.upper()
head = {'schema': 'framelease_v4.stress_bench/1', 'test': test, 'registered': True,
        'label': f'registered {test} run (PROTOCOL Sec. 7.6)',
        'provenance': {'code_sha256': {'framelease_v4/protocol/tool.py':
                                       M.sha(M.R / 'framelease_v4/protocol/tool.py')}}}
stamp = time.strftime('%Y%m%dT%H%M%S') + f'_{time.time_ns()}'
rep = None
if sub == 's1':
    cnt = M.R / 'mock/s1_refusals'
    n = int(cnt.read_text()) if cnt.exists() else 0
    if n < sc.get('s1_refuse', 0):
        cnt.write_text(str(n + 1))
        print('s1: refusing a registered run while these processes use CPU (S1 needs an exclusive CPU; '
              '--accept-foreign-cpu runs anyway and records it in the report):\n  4242 0.50 core /usr/bin/firefox',
              file=sys.stderr)
        sys.exit(1)
    env = M.opt(a, '--envelope')
    rep = {**head, 'plan': {'networks': nets, 'loads': [0, 4, 8, 15]}, 'per_load': [{'load': x} for x in (0, 4, 8, 15)],
           'envelope': {'path': env, 'sha256': M.sha(M.R / env)}, 'shared_cpu': False,
           'foreign_cpu_accepted': '--accept-foreign-cpu' in a}
    name = f's1_registered_{stamp}.json'
elif sub == 's2':
    relative = M.opt(a, '--grid') == 'relative'
    viol = 1 if sc.get('s2_fail') and not relative else 0
    rep = {**head, 'networks': {n['name']: {'file_sha256': n['file_sha256'], 'admitted_bound_ge_Dstar': viol}
                                for n in nets},
           'n_swept': 2000, 'violations_total': viol, 'pass': viol == 0}
    if relative:
        rep.update(label='supplementary: S2 relative to the slack floor (registered run, PROTOCOL Sec. 7.6, Amendment '
                         'A7; never in place of the S2 grid)', supplementary=True, grid='relative_to_floor')
        name = f's2_relative_registered_{stamp}.json'
    else:
        rep['slack_grid_s'] = [round(-0.1 + 0.01 * i, 2) for i in range(71)]
        name = f's2_registered_{stamp}.json'
else:
    rep = {**head, 'n_sequences': 100000, 'targets': {'gate': {}, 'runtime': {}}, 'coverage_ok': True,
           'violations_total': 0, 'pass': True}
    name = f's3_registered_{stamp}.json'
p = M.R / 'outputs/framelease_v4/stress' / name
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(rep, indent=1, sort_keys=True) + '\n')
print(json.dumps({'out': str(p), 'pass': rep.get('pass', True)}))
sys.exit(0 if rep.get('pass', True) else 1)
'''

MOCK_TEST_JOBS = r'''
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mockcommon as M

a = sys.argv[1:]
M.log_call('test_jobs')
if not ('--check' in a and '--write' in a):
    sys.exit(2)
if os.environ.get('PHD_ENV_SOURCED') != '1' or os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    print('ERROR: linux/env.sh not sourced or CUDA not hidden', file=sys.stderr)
    sys.exit(1)
if not (M.R / 'outputs/framelease_v4/rl_freeze/rl_freeze.json').is_file():
    print('REFUSED: no RL freeze', file=sys.stderr)
    sys.exit(2)
base = M.R / M.opt(a, '--jobs-dir') / 'FULL'
base.mkdir(parents=True, exist_ok=True)
blocks = []
for name, no, tier in (('ti_main', 11, 3), ('f3_k', 12, 4), ('a_lease', 13, 5), ('a_rl', 14, 5), ('s_seed12', 15, 6)):
    stem = base / f'b{no}_{name}'
    lines = [{'id': f'v4p{min(tier + 1, 6)}_{name}_r{i}', 'kind': 'closed_loop', 'tier': tier, 'cmd': ['true'],
              'wall_cap_s': 60} for i in range(2)]
    text = ''.join(json.dumps(j, sort_keys=True) + '\n' for j in lines)
    spec = json.dumps({'schema': 'framelease_v4.test_stage/1', 'block': name, 'n_lines': 2}) + '\n'
    check = json.dumps({'schema': 'framelease_v4.test_check/1', 'block': name, 'problems': [],
                        'all_dry_runs_ok': True, 'n_lines': 2}) + '\n'
    ent = {'block': name, 'no': no, 'tier': tier, 'n_lines': 2, 'skipped': None}
    for suffix, content, key in (('.jsonl', text, 'job_file'), ('.stage.json', spec, 'stage_spec'),
                                 ('.check.json', check, 'check')):
        p = Path(str(stem) + suffix)
        if p.exists() and p.read_text() != content:
            print(f'REFUSED: refusing to overwrite {p}', file=sys.stderr)
            sys.exit(2)
        p.write_text(content)
        ent[key], ent[key + '_sha256'] = str(p.relative_to(M.R)), M.sha(p)
    blocks.append(ent)
blocks.append({'block': 's_risk', 'no': 16, 'tier': 6, 'n_lines': 0, 'skipped': 'L* is not B0'})
idx = {'schema': 'framelease_v4.test_jobs_index/1', 'variant': 'FULL', 'blocks': blocks, 'n_lines': 10,
       'queue': 'outputs/framelease_v4/queue_p4', 'cross_block_problems': []}
(base / 'index.json').write_text(json.dumps(idx, indent=1, sort_keys=True) + '\n')
print('every line passes')
'''

MOCK_TEST_FREEZE = r'''
import json, sys, textwrap, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mockcommon as M

a = sys.argv[1:]
flag = a[0]
M.log_call('test_freeze', flag=flag)
out_dir, qdir, jobs = (M.R / M.opt(a, k) for k in ('--out-dir', '--queue-dir', '--jobs-dir'))
rp, mp = out_dir / 'test_freeze.json', out_dir / 'MANIFEST.sha256'


def rel(p):
    return str(Path(p).relative_to(M.R))


def bullet(text):
    return textwrap.wrap(text, width=120, initial_indent='* ', subsequent_indent='  ', break_long_words=False,
                         break_on_hyphens=False)


def entry(rec, rsha):
    man = rec['manifest']
    head = (f'**Test freeze, {rec["entry_time"]}: P4-P6 job files, RL freeze and stress tests (PROTOCOL Secs. 3.3 rule '
            '4, 5.9, 7.6, 8.1).** No test-route run existed at the freeze. P4 starts once this entry is sealed and '
            '`framelease_v4/protocol/test_freeze.py --verify` passes.')
    out = textwrap.wrap(head, width=120, break_long_words=False, break_on_hyphens=False)
    out += bullet(f'Record. `{rec["script"]}` wrote `{rel(rp)}` (sha256 `{rsha}`) and its sha256 manifest '
                  f'`{man["path"]}` ({man["n_files"]} files, sha256 `{man["sha256"]}`).')
    out += bullet(f'RL freeze (Sec. 5.9). `{rec["rl_freeze"]["path"]}` (sha256 `{rec["rl_freeze"]["sha256"]}`).')
    out += bullet('Job files: ' + '; '.join(f'`{Path(b["job_file"]).name}` tier {b["tier"]}, sha256 '
                                            f'`{b["job_file_sha256"]}`' for b in rec['job_files']['blocks']
                                            if b.get('job_file')) + '.')
    out += bullet('Fixed by this entry: the block numbers 11-16 and the job file names, copied in name order so that '
                  'a cut takes the bottom tiers first; list-like words follow: - a dash, 1. a number, # a hash, > a '
                  'quote, + a plus, * a star, 2) a parenthesis.')
    return out


if flag == '--write':
    idx = json.loads((jobs / 'FULL/index.json').read_text())
    stress = {}
    for t in ('s1', 's2', 's3'):
        hits = sorted((M.R / M.opt(a, '--stress-dir')).glob(f'{t}_registered_*.json'))
        if len(hits) != 1:
            print(f'REFUSED: {len(hits)} registered {t} reports', file=sys.stderr)
            sys.exit(2)
        stress[t] = {'path': rel(hits[0]), 'sha256': M.sha(hits[0])}
    rl = M.R / M.opt(a, '--rl-freeze')
    files = {b['job_file']: b['job_file_sha256'] for b in idx['blocks'] if b.get('job_file')}
    files[rel(rl)] = M.sha(rl)
    files.update({s['path']: s['sha256'] for s in stress.values()})
    mtext = ''.join(f'{s}  {p}\n' for p, s in sorted(files.items()))
    import hashlib
    rec = {'schema': 'framelease_v4.test_freeze/1', 'script': 'framelease_v4/protocol/test_freeze.py',
           'entry_time': '2026-11-20 09:00 (Beijing time)', 'job_files': {'blocks': idx['blocks']},
           'rl_freeze': {'path': rel(rl), 'sha256': M.sha(rl)}, 'stress': stress,
           'manifest': {'path': rel(mp), 'sha256': hashlib.sha256(mtext.encode()).hexdigest(), 'n_files': len(files)},
           'written': time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    old = json.loads(rp.read_text()) if rp.exists() else None
    keep = old is not None and {k: v for k, v in old.items() if k != 'written'} == \
        {k: v for k, v in rec.items() if k != 'written'}
    if old is not None and not keep:
        print(f'REFUSED: refusing to overwrite {rel(rp)} with other content', file=sys.stderr)
        sys.exit(2)
    out_dir.mkdir(parents=True, exist_ok=True)
    mp.write_text(mtext)
    if not keep:
        rp.write_text(json.dumps(rec, indent=1, sort_keys=True) + '\n')
    print(json.dumps({'record': rel(rp), 'record_sha256': M.sha(rp), 'record_kept': keep}, indent=1))
    print('\n---- PROTOCOL Sec. 13.2 entry (appended by the coordinating session ...):\n')
    print('\n'.join(entry(json.loads(rp.read_text()), M.sha(rp))))
    sys.exit(0)
rec = json.loads(rp.read_text())
rsha = M.sha(rp)
if flag == '--entry':
    print('\n'.join(entry(rec, rsha)))
    sys.exit(0)
proto = (M.R / 'framelease_v4/PROTOCOL.md').read_text()
seal = dict(reversed(ln.split('  ', 1)) for ln in (M.R / 'outputs/framelease_v4/registration/SEAL.sha256')
            .read_text().splitlines())
if rsha not in proto or rec['manifest']['sha256'] not in proto \
        or seal.get('framelease_v4/PROTOCOL.md') != M.sha(M.R / 'framelease_v4/PROTOCOL.md'):
    print('REFUSED: PROTOCOL Sec. 13.2 does not cite the test freeze yet, or PROTOCOL.md is not sealed',
          file=sys.stderr)
    sys.exit(2)
frozen = {Path(b['job_file']).name: b['job_file_sha256'] for b in rec['job_files']['blocks'] if b.get('job_file')}
copies, probs = [], []
for f in sorted(qdir.glob('*.jsonl')) if qdir.is_dir() else []:
    if frozen.get(f.name) != M.sha(f):
        probs.append(f.name)
    copies.append(f.name)
if probs:
    print(f'TEST FREEZE CHANGED {probs}', file=sys.stderr)
    sys.exit(1)
print(json.dumps({'record_sha256': rsha, 'queue_copies': copies}, indent=1))
print('test freeze OK: the P4-P6 job files may be copied, in name order, into outputs/framelease_v4/queue_p4/jobs.d/')
'''

MOCK_AGGREGATE = r'''
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mockcommon as M

a = sys.argv[1:]
M.log_call('aggregate', arm_summary=M.opt(a, '--arm-summary'), analysis_freeze=M.opt(a, '--analysis-freeze'),
           record=M.opt(a, '--write-freeze-record'), force='--force' in a)
sc = M.scenario()
out = M.R / M.opt(a, '--out')
rec = M.opt(a, '--write-freeze-record')
queues = [M.R / a[i + 1] for i, x in enumerate(a) if x == '--queue']
outputs = ('runs.csv', 'aggregate.json', 'SHA256SUMS', 'arm_summary.csv')


def guard_log(decision):
    out.mkdir(parents=True, exist_ok=True)
    with open(out / 'interim_guard.jsonl', 'a') as f:
        f.write(json.dumps({'request': 'aggregate', 'decision': decision, 'argv': a}) + '\n')


if M.opt(a, '--arm-summary') in ('test', 'all') and not M.opt(a, '--analysis-freeze'):
    guard_log('refused')
    print('REFUSED (interim-look guard): a cross-arm summary of test routes before the analysis freeze',
          file=sys.stderr)
    sys.exit(4)
if rec and (M.R / rec).exists():
    print(f'REFUSED: {rec} exists (a freeze record is never replaced)', file=sys.stderr)
    sys.exit(1)
if '--force' not in a and any((out / n).exists() for n in outputs):
    print(f'REFUSED: {out} already holds outputs (use --force to replace them)', file=sys.stderr)
    sys.exit(1)
guard_log('granted')
if sc.get('agg_inconsistent'):
    print('ERROR: block specs disagree with the job lines', file=sys.stderr)
    sys.exit(2)
finals, rows, job_files = {}, [], {}
for q in queues:
    st = q / 'status.jsonl'
    for ln in (st.read_text().splitlines() if st.exists() else []):
        r = json.loads(ln)
        if r.get('event') == 'end' and r.get('final'):
            finals[r['id']] = r
    for f in sorted((q / 'jobs.d').glob('*.jsonl')):
        rel = str(f.relative_to(M.R))
        job_files[rel] = M.sha(f)
        for ln in f.read_text().splitlines():
            j = json.loads(ln)
            fin = finals.get(j['id'])
            rows.append({'job': j['id'], 'job_file': rel, 'outcome': fin.get('outcome', 'ok') if fin else 'pending',
                         'selected_run': f'runs/{j["id"]}' if fin else None})
pending = [r['job'] for r in rows if r['outcome'] == 'pending']
if rec and pending:
    print(f'ERROR: no analysis-freeze record: {len(pending)} job lines are not final: {pending[:10]}', file=sys.stderr)
    sys.exit(2)
(out / 'runs.csv').write_text('job,outcome,analysis_use\n' + ''.join(f'{r["job"]},health_only,health_only\n'
                                                                       for r in rows))
(out / 'aggregate.json').write_text(json.dumps({'schema': 'framelease_v4.aggregate/1', 'job_files': job_files}) + '\n')
(out / 'SHA256SUMS').write_text(''.join(f'{M.sha(out / n)}  {n}\n' for n in ('runs.csv', 'aggregate.json')))
if sc.get('agg_bad_sums'):                     # an output changed after SHA256SUMS was written
    with open(out / 'runs.csv', 'a') as f:
        f.write('changed,after,sums\n')
print(f'{len(rows)} rows (every test-route row health-only)')
if rec:
    code = {f'framelease_v4/analysis/{m}': M.sha(M.R / 'framelease_v4/analysis' / m)
            for m in ('aggregate_v4.py', 'extra_metrics.py', 'commit_audit.py', 'manipulation.py', 'interim_guard.py')}
    if sc.get('agg_extra_job_file'):
        job_files['outputs/framelease_v4/queue_p4/jobs.d/b99_extra.jsonl'] = '9' * 64
    doc = {'schema': 'framelease_v4.analysis_freeze/1', 'frozen': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
           'trigger': 'all_final', 'cut_amendment': None, 'job_files': job_files,
           'jobs': {r['job']: {'job_file': r['job_file'], 'outcome': r['outcome'], 'run_dir': r['selected_run']}
                    for r in rows},
           'analysis_code': code, 'route_split_sha256': '7' * 64}
    p = M.R / rec
    p.write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n')
    print(f'analysis-freeze record {rec}: sha256 {M.sha(p)}, {len(doc["jobs"])} jobs, trigger all_final. Not valid '
          'until this sha256 is entered as a dated entry in Sec. 13 of framelease_v4/PROTOCOL.md and PROTOCOL.md is '
          're-sealed (registration.py --seal).')
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
REG.REGISTERED_JOB_FILES = ()
REG.OUTPUT_FILES = ()
REG.SEC_12_1 = ()
REG.verify.__defaults__ = (REG.MANIFEST,)          # defaults bound at definition time point at the real files
REG.read_manifest.__defaults__ = (REG.MANIFEST,)
REG.job_pins.__defaults__ = (REG.REGISTERED_JOB_FILES,)
sys.exit(REG.main(sys.argv[1:]))
'''

MOCKS = {'mockcommon.py': MOCKCOMMON, 'p2_jobs.py': MOCK_P2_JOBS, 'p2_check.py': MOCK_P2_CHECK,
         'launch_queue.sh': MOCK_LAUNCH, 'systemd-run': MOCK_SYSTEMD_RUN, 'p3_rl.py': MOCK_P3_RL,
         'stress_bench.py': MOCK_STRESS, 'test_jobs.py': MOCK_TEST_JOBS, 'test_freeze.py': MOCK_TEST_FREEZE,
         'aggregate_v4.py': MOCK_AGGREGATE,
         'registration_sandbox.py': REG_WRAPPER.replace('@REAL@', str(REAL_REGISTRATION))}


# ---------------------------------------------------------------------------------------------------- helpers

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(cmd, cwd, timeout=180, env=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)


def strip_block(text, heading):
    lines = text.split('\n')
    stripped = [ln.strip() for ln in lines]
    if heading not in stripped:
        return text
    i = stripped.index(heading)
    j = i + 1
    while j < len(lines) and lines[j].strip():
        j += 1
    del lines[i:j + 1]
    return '\n'.join(lines)


def sandbox_protocol(fsha, dsha, amendments):
    """The real PROTOCOL.md without driver subsections, real amendment titles renamed, plus a synthetic P1 driver block
    and the given amendment titles before the anchor."""
    text = strip_block(strip_block(REAL_PROTOCOL.read_text(encoding='utf-8'), P1_HEADING), HEADING)
    text = re.sub(r'^\*\*Amendment A', '**Real amendment A', text, flags=re.M)
    block = [P1_HEADING,
             f'* **Tuning freeze**, 2026-11-15 08:00 (Beijing time). `{FREEZE}` (sha256 `{fsha}`), sandbox.',
             f'* **D1 summary**, 2026-11-15 09:00 (Beijing time). `{D1JSON}` (sha256 `{dsha}`), sandbox.', '']
    for a in amendments:
        what = f', {A7B_TITLE}' if a == 'A7' else ''
        block += [f'**Amendment {a}, 2026-11-15 09:30 (Beijing time): sandbox amendment {a}{what}.** No effect.', '']
    return text.replace(ANCHOR, '\n'.join(block) + '\n' + ANCHOR, 1)


def reg(R, *flags):
    return run([PY, '-I', '-B', 'mock/registration_sandbox.py', *flags], R)


def seal_with(R, text):
    """Write the manifest, put its sha256 into `text` (the registration entry), write PROTOCOL.md, seal."""
    p = reg(R, '--write-manifest', '--force')
    assert p.returncode == 0, p.stdout + p.stderr
    m0 = sha(R / MANIFEST)
    text = text.replace(ANCHOR, f'Sandbox seal: manifest sha256 `{m0}`.\n\n{ANCHOR}', 1)
    (R / PROTO).write_text(text, encoding='utf-8')
    p = reg(R, '--seal')
    assert p.returncode == 0, p.stdout + p.stderr


def make_sandbox(test, p1_done=True, amendments=('A3', 'A4', 'A7', 'A9')):
    SCRATCH.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='phdrv_', dir=str(SCRATCH))
    test.addCleanup(shutil.rmtree, tmp, True)
    R = Path(tmp) / 'root'
    for d in ('framelease_v4/protocol', 'mock', 'linux', P1D, 'outputs/framelease_v4/p1_jobs/FULL',
              'outputs/framelease_v4/tuning/d1', 'outputs/framelease_v4/registration',
              'outputs/framelease_v4/envelopes'):
        (R / d).mkdir(parents=True)
    (R / 'linux/env.sh').write_text(ENV_SH)
    (R / 'framelease_v4/protocol/tool.py').write_text('# sandbox stand-in for a registered tool\n')
    for rel in CODE_STANDINS:                   # the code G4 and G6 check beyond the (mock) tool scripts, registered
        (R / rel).parent.mkdir(parents=True, exist_ok=True)
        (R / rel).write_text(f'# sandbox stand-in for {rel}\n')
    (R / 'framelease_v4/analysis').mkdir(parents=True)
    for rel in ANALYSIS_FILES:
        (R / rel).write_text(f'# sandbox stand-in for {rel}\n')
    (R / 'outputs/framelease_v4/p1_jobs/FULL/b01_ref.jsonl').write_text('{"id": "v4p1_ref_x"}\n')
    for name, text in MOCKS.items():
        (R / 'mock' / name).write_text(text)
    os.chmod(R / 'mock/systemd-run', 0o755)
    (R / ENVELOPE).write_text('{"kind": "iso", "sigma_m": 0.5}\n')
    (R / FREEZE).write_text(json.dumps({'schema': 'framelease_v4.tuning_selection/1', 'variant': 'FULL',
                                        'L_star': {'label': 'E5', 'envelope_path': ENVELOPE,
                                                   'envelope_sha256': sha(R / ENVELOPE), 'validity': 'std'},
                                        'd_star': {'d': 4, 'utility': 'v4_adet_d4'}}) + '\n')
    (R / D1JSON).write_text(json.dumps({'schema': 'framelease_v4.d1_summary/1', 'variant': 'FULL'}) + '\n')
    (R / D1JSON).with_suffix('.md').write_text('# D1 (sandbox)\n')
    seal_with(R, sandbox_protocol(sha(R / FREEZE), sha(R / D1JSON), amendments))
    files = dict(ln.split('  ', 1)[::-1] for ln in (R / MANIFEST).read_text().splitlines())
    (R / P1D / 'registered_baseline.json').write_text(json.dumps(
        {'schema': 'framelease_v4.p1_driver_baseline/1', 'manifest_sha256': sha(R / MANIFEST), 'files': files},
        indent=1) + '\n')
    if p1_done:
        write_p1_done(R)
    return R


def write_p1_done(R):
    (R / P1D / 'P1_DONE.json').write_text(json.dumps({'schema': 'framelease_v4.p1_driver_done/1', 'variant': 'FULL'})
                                          + '\n')


def foreign_amendment(R, paragraph):
    """Another editor's amendment: write the manifest, add a paragraph citing it before the anchor, seal."""
    p = reg(R, '--write-manifest', '--force')
    assert p.returncode == 0, p.stdout + p.stderr
    text = (R / PROTO).read_text(encoding='utf-8')
    text = text.replace(ANCHOR, f'{paragraph} Manifest sha256 `{sha(R / MANIFEST)}`.\n\n{ANCHOR}', 1)
    (R / PROTO).write_text(text, encoding='utf-8')
    p = reg(R, '--seal')
    assert p.returncode == 0, p.stdout + p.stderr


def decide(R, decision='continue', d1_sha=None, **extra):
    doc = {'schema': 'framelease_v4.d1_decision/1', 'decision': decision,
           'rationale': 'Sandbox rationale: the training-route summary shows no blocking defect',
           'd1_summary_sha256': d1_sha or sha(R / D1JSON), 'decided': '2026-11-15T10:00:00+0800', **extra}
    (R / DRV).mkdir(parents=True, exist_ok=True)
    (R / DRV / 'D1_DECISION.json').write_text(json.dumps(doc, indent=1) + '\n')


def scenario(R, **kw):
    (R / 'mock/scenario.json').write_text(json.dumps(kw))


def drive(R, *extra, crash=None, touch=None, timeout=300, nice_ok=True, normal=True, foreign=None, retry_s='0'):
    cmd = [PY, '-I', '-B', str(DRIVER), '--root', str(R), '--python', PY,
           '--registration-script', str(R / 'mock/registration_sandbox.py'),
           '--p2-jobs-script', str(R / 'mock/p2_jobs.py'), '--p2-check-script', str(R / 'mock/p2_check.py'),
           '--p3-rl-script', str(R / 'mock/p3_rl.py'), '--stress-script', str(R / 'mock/stress_bench.py'),
           '--test-jobs-script', str(R / 'mock/test_jobs.py'), '--test-freeze-script', str(R / 'mock/test_freeze.py'),
           '--aggregate-script', str(R / 'mock/aggregate_v4.py'),
           '--launch-script', str(R / 'mock/launch_queue.sh'), '--env-script', str(R / 'linux/env.sh'),
           '--systemd-run', str(R / 'mock/systemd-run'), '--lock-timeout-s', '2', '--s1-retry-s', retry_s]
    if nice_ok:
        cmd.append('--allow-nice-launch')           # the tests run under nice 19
    if normal:
        cmd.append('--normal-priority')             # the tools inherit nice 19 / ionice idle of the test
    if '--dry-run' not in extra:
        cmd.append('--once')
    cmd += list(extra)
    env = {k: v for k, v in os.environ.items()
           if k not in (CRASH_ENV, TOUCH_ENV, FOREIGN_ENV, 'CUDA_VISIBLE_DEVICES')}
    if crash:
        env[CRASH_ENV] = crash
    if touch:
        env[TOUCH_ENV] = touch
    if foreign is not None:
        env[FOREIGN_ENV] = json.dumps(foreign)
    return run(cmd, R, timeout, env)


def calls(R, tool=None):
    p = R / 'mock/calls.jsonl'
    out = [json.loads(ln) for ln in p.read_text().splitlines()] if p.exists() else []
    return [c for c in out if tool is None or c['tool'] == tool]


def lines_of(R, name):
    p = R / 'mock' / name
    return p.read_text().splitlines() if p.exists() else []


def view(R):
    return D.phase_view(None, (R / PROTO).read_text(encoding='utf-8'))


def entries(R):
    return view(R)['entries']


def flat(R, key):
    return entries(R)[key]['text'].replace('\n  ', ' ')


def state(R):
    return json.loads((R / DRV / 'state.json').read_text())


def seal_ok(R):
    seal = dict(ln.split('  ', 1)[::-1] for ln in (R / SEAL).read_text().splitlines())
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


def out_of(p):
    return f'exit {p.returncode}\n--- stdout ---\n{p.stdout[-6000:]}\n--- stderr ---\n{p.stderr[-6000:]}'


def alert_text(R):
    p = R / ALERT
    return p.read_text() if p.exists() else ''


def resolve_alert(R):
    (R / ALERT).rename(R / DRV / f'ALERT.{time.time_ns()}.resolved.txt')


def finish_p2(R, only=None, exit_reason='queue empty', exit_code=0, runner_exit=True, queue=Q2, outcome=None):
    """The 'runner': final records (outcome ok, or outcome(job)) for every job in <queue>/jobs.d without one, then
    optionally its exit record."""
    q = R / queue
    status = q / 'status.jsonl'
    finals = set()
    if status.exists():
        for ln in status.read_text().splitlines():
            r = json.loads(ln)
            if r.get('event') == 'end' and r.get('final'):
                finals.add(r['id'])
    recs = [{'event': 'runner_start', 'pid': 4242, 'utc': '2026-11-15T00:00:00+00:00'}]
    for f in sorted((q / 'jobs.d').glob('*.jsonl')):
        for ln in f.read_text().splitlines():
            j = json.loads(ln)
            if j['id'] in finals or (only is not None and not only(j)):
                continue
            recs += [{'event': 'start', 'id': j['id'], 'attempt': 1},
                     {'event': 'end', 'id': j['id'], 'attempt': 1, 'final': True, 'counted': True,
                      'outcome': outcome(j) if outcome else 'ok'}]
    if runner_exit:
        recs.append({'event': 'runner_exit', 'pid': 4242, 'reason': exit_reason, 'exit_code': exit_code})
    with status.open('a') as fh:
        for r in recs:
            fh.write(json.dumps(r, sort_keys=True) + '\n')


def runner_event(R, reason, code, queue=Q2):
    with (R / queue / 'status.jsonl').open('a') as fh:
        fh.write(json.dumps({'event': 'runner_start', 'pid': 4343, 'utc': 'x'}) + '\n')
        fh.write(json.dumps({'event': 'runner_exit', 'pid': 4343, 'reason': reason, 'exit_code': code}) + '\n')


def register_analysis(R):
    """The coordinating session's amendment that registers the analysis code before the analysis freeze (PROTOCOL Sec.
    9.12): analyze_v4.py and the analysis modules cited by sha256, sealed."""
    if not (R / ANALYZE).exists():
        (R / ANALYZE).write_text('# sandbox stand-in for analyze_v4.py (R-4)\n')
    cites = '; '.join(f'`{rel}` (sha256 `{sha(R / rel)}`)' for rel in [ANALYZE] + ANALYSIS_FILES)
    foreign_amendment(R, f'**Amendment A10, 2026-11-28 09:00 (Beijing time): sandbox registration of the analysis '
                         f'code.** {cites}.')


def to_p4_running(test):
    """A sandbox at G7: P1 done, D1 continue, P2 run and recorded, P3, the stress tests and the test freeze recorded,
    the P4-P6 job files queued and their runner launched (two drives)."""
    R = make_sandbox(test)
    decide(R)
    p = drive(R)
    test.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
    finish_p2(R)
    p = drive(R)
    test.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
    test.assertEqual(state(R)['gates']['G7']['status'], 'running', out_of(p))
    test.assertEqual([ln.split()[-1] for ln in lines_of(R, 'launch_calls.log')], [Q2, Q4])
    return R


def final_dirs(R):
    d = R / ANALYSIS
    return sorted(x.name for x in d.iterdir() if x.name.startswith('final_')) if d.is_dir() else []


class FakeRunner:
    """A process whose command line looks like the runner of `queue` (gpu_queue.py --queue-dir <abs queue>), named in
    <queue>/runner.lock as the real runner writes it (no lock is held)."""

    def __init__(self, R, queue):
        qd = R / queue
        qd.mkdir(parents=True, exist_ok=True)
        self.p = subprocess.Popen([PY, '-I', '-B', '-c', 'import time; time.sleep(120)', 'gpu_queue.py',
                                   '--queue-dir', str(qd)])
        (qd / 'runner.lock').write_text(f'pid {self.p.pid} started test\n')

    def stop(self):
        self.p.kill()
        self.p.wait(timeout=10)


class FakeTool:
    """A process whose command line names `script` as the driver starts a tool (python -I -B ... <script>): a tool left
    running by a killed driver process."""

    def __init__(self, script):
        self.p = subprocess.Popen([PY, '-I', '-B', '-c', 'import time; time.sleep(120)', str(script)])

    def stop(self):
        self.p.kill()
        self.p.wait(timeout=10)


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


def real_snapshot():
    """What the tests must never change in the project tree. The coordinating session may amend PROTOCOL.md while the
    tests run: a changed PROTOCOL.md / MANIFEST.sha256 must then still match the real SEAL.sha256 (a sealed amendment)
    and hold no text of these tests (the driver heading, sandbox titles)."""
    text = REAL_PROTOCOL.read_text(encoding='utf-8')
    seal = dict(ln.split('  ', 1)[::-1] for ln in (REAL_REG_DIR / 'SEAL.sha256').read_text().splitlines())
    snap = {'sealed': (seal.get(PROTO) == sha(REAL_PROTOCOL)
                       and seal.get(MANIFEST) == sha(REAL_REG_DIR / 'MANIFEST.sha256')),
            'test_text_in_protocol': [s for s in (HEADING, 'sandbox amendment', 'Sandbox seal', 'Sandbox rationale')
                                      if s in text]}
    for rel in (DRV, Q2, 'outputs/framelease_v4/p2_jobs/FULL', RLDATA, 'outputs/framelease_v4/rl_freeze', STRESS,
                'outputs/framelease_v4/test_jobs', 'outputs/framelease_v4/test_freeze', Q4,
                'outputs/framelease_v4/build/phase_driver', ANALYSIS):
        d = ROOT / rel
        snap[rel] = sorted(p.name for p in d.iterdir()) if d.exists() else None
    snap['protocol_lock'] = (ROOT / 'framelease_v4/.protocol.lock').exists()
    return snap


# ---------------------------------------------------------------------------------------------------- tests

class EntryFormatTest(unittest.TestCase):
    def test_heading_after_the_p1_block_and_no_collision_with_p1_entries(self):
        text = sandbox_protocol('a' * 64, 'b' * 64, ('A3', 'A4'))
        p1_before = P1.protocol_view(None, text)['entries']
        e1 = P1.wrap_entry('**G1 D1 decision** (2026-11-15 10:00, Beijing time). `x` (sha256 `' + 'c' * 64 + '`). '
                           + 'word ' * 60 + '1. - * # not list starts')
        t1 = D.insert_entry(None, text, e1)
        e2 = P1.wrap_entry('**G2 P2 job file** (2026-11-15 10:05, Beijing time). `y` (sha256 `' + 'd' * 64 + '`).')
        t2 = D.insert_entry(None, t1, e2)
        v = D.phase_view(None, t2)
        lines = v['lines']
        self.assertEqual([ln.strip() for ln in lines].count(HEADING), 1)
        self.assertEqual(set(v['entries']), {'d1_decision', 'p2_jobs'})
        self.assertLess(v['entries']['d1_decision']['line'], v['entries']['p2_jobs']['line'])
        self.assertIn('c' * 64, v['entries']['d1_decision']['shas'])
        h = v['heading']
        self.assertLess(v['p1_heading'], h)                       # after the P1 driver's block
        self.assertLess(max(x for ln in v['amendments'].values() for x in ln), h + 1)   # and after the amendments
        self.assertLess(h, v['anchor'])
        self.assertEqual(lines[h - 1], '')
        self.assertEqual(lines[v['anchor'] - 1], '')
        # the P1 driver's view is unchanged: same entries, none of this driver's lines parses as a P1 entry
        p1_after = P1.protocol_view(None, t2)['entries']
        self.assertEqual({k: x['text'] for k, x in p1_after.items()}, {k: x['text'] for k, x in p1_before.items()})
        self.assertEqual(set(p1_after), {'freeze', 'd1'})
        for ln in e1 + e2:
            self.assertIsNone(P1.ENTRY_RE.match(ln), ln)
        for ln in e1[1:]:
            self.assertTrue(ln.startswith('  ') and not P1.LIST_START.match(ln[2:]), ln)
        self.assertTrue(all(len(ln) <= 120 for ln in e1 + e2))
        self.assertEqual(t2.replace('\n'.join([HEADING] + e1 + e2 + ['']) + '\n', ''), text)
        self.assertEqual(sorted(v['amendments']), ['A3', 'A4'])

    def test_nested_entry_of_a_tool(self):
        """The entry text test_freeze.py prints (head paragraph, '* ' bullets) nested under the G6 bullet: the same
        words, 120 columns, no list-like continuation line, every sha256 on one line, parsed as one entry."""
        head = ('**Test freeze, 2026-11-20 09:00 (Beijing time): P4-P6 job files (Secs. 3.3 rule 4, 5.9).** '
                + 'word ' * 30 + '`' + 'a' * 64 + '`.')
        b1 = 'Record. `x` (sha256 `' + 'b' * 64 + '`) ' + 'filler ' * 20 + '1. starts like a list - and # and > quote'
        b2 = 'Fixed: ' + ' '.join(f'plain words here {m} marker' for m in ('- dash', '1. one', '# hash', '+ plus',
                                                                           '>= D*', '>= D*', '>= D*'))
        printed = (textwrap.wrap(head, 120, break_long_words=False, break_on_hyphens=False) + P1.wrap_entry(b1)
                   + P1.wrap_entry(b2))
        nested, paras = D.nest_entry_lines(printed)
        self.assertEqual(paras, [' '.join(t.split()) for t in (head, b1, b2)])
        self.assertTrue(all(ln.startswith('  ') and len(ln) <= 120 for ln in nested))
        self.assertEqual(sum(ln.startswith('  * ') for ln in nested), 2)
        for ln in nested:
            body = ln[4:] if ln.startswith('    ') else ln[2:]
            self.assertTrue(ln.startswith('  * ') or not D.LINE_START.match(body), ln)
        self.assertTrue(any('a' * 64 in ln for ln in nested) and any('b' * 64 in ln for ln in nested))
        self.assertEqual(D.nest_entry_lines([ln[2:] for ln in nested])[1], paras)       # the round trip
        text = sandbox_protocol('a' * 64, 'b' * 64, ('A3',))
        e = P1.wrap_entry('**G6 Test freeze** (2026-11-20 09:05, Beijing time). The freeze `' + 'c' * 64 + '`.')
        e += nested
        t = D.insert_entry(None, text, e)
        v = D.phase_view(None, t)
        self.assertEqual(set(v['entries']), {'test_freeze'})
        self.assertIn('b' * 64, v['entries']['test_freeze']['shas'])
        self.assertEqual({k: x['text'] for k, x in P1.protocol_view(None, t)['entries'].items()},
                         {k: x['text'] for k, x in P1.protocol_view(None, text)['entries'].items()})
        for bad in (printed[:1] + [''] + printed[1:], ['  indented head'], ['* bullet only']):
            with self.assertRaises(ValueError):
                D.nest_entry_lines(bad)

    def test_constants_match_the_tools(self):
        """The driver's copies of the tools' constants (read from the real sources; nothing is imported from the RL
        stack)."""
        self.assertEqual(D.consistency_problems(), [])
        self.assertEqual(D.source_constants(ROOT / 'framelease_v4/protocol/p3_rl.py', {'DEFAULT_OUT'}),
                         {'DEFAULT_OUT': 'outputs/framelease_v4/rl_freeze'})
        # the record line aggregate_v4.py prints (G8 reads the record's path and sha256 from it)
        src = (ROOT / 'framelease_v4/analysis/aggregate_v4.py').read_text(encoding='utf-8')
        self.assertIn("print(f'analysis-freeze record {PJ.rel(a.write_freeze_record)}: sha256 {sha}, "
                      "{len(record[\"jobs\"])} jobs, '", src)
        self.assertIn("f'trigger {record[\"trigger\"]}. Not valid until", src)
        m = D.AGG_RECORD_RE.search(f'x\nanalysis-freeze record {ANALYSIS}/final_1/analysis_freeze.json: sha256 '
                                   f'{"a" * 64}, 12 jobs, trigger all_final. Not valid until this sha256 ...\n')
        self.assertEqual(m.groups(), (f'{ANALYSIS}/final_1/analysis_freeze.json', 'a' * 64, '12', 'all_final'))

    def test_a7_variant_and_the_stress_runs(self):
        """Review fix S4: the supplementary relative S2 grid runs (and is entered) only when the Amendment A7 in Sec.
        13.2 is the variant A7b; the wording of both variants is read from the amendment draft when it exists."""
        base = sandbox_protocol('1' * 64, '2' * 64, ('A3',))
        variants = [(f'**Amendment A7, 2026-11-15 09:40 (Beijing time): {A7B_TITLE}.** No effect.', True),
                    ('**Amendment A7, 2026-11-15 09:40 (Beijing time): the Eq. 5 slack floor is reported next to the '
                     'registered S2 grid.** No change of grid.', False)]
        draft = ROOT / 'outputs/framelease_v4/build/AMEND/AMENDMENTS_DRAFT.md'
        if draft.is_file():
            parts = re.split(r'^### (A7a|A7b)\b.*$', draft.read_text(encoding='utf-8'), flags=re.M)
            for name, body in zip(parts[1::2], parts[2::2]):
                body = re.split(r'^##+ ', body, flags=re.M)[0].strip().replace('{{datetime}}', '2026-11-15 09:40')
                variants.append((body, name == 'A7b'))
            self.assertEqual(len(variants), 4, 'the draft holds A7a and A7b')
        for para, sup in variants:
            v = D.phase_view(None, base.replace(ANCHOR, para + '\n\n' + ANCHOR, 1))
            self.assertIn('A7', v['amendments'])
            self.assertIs(D.a7_supplementary(v), sup, para[:120])
            self.assertEqual([r[0] for r in D.stress_runs(v)],
                             ['s3', 's2'] + (['s2_relative'] if sup else []) + ['s1'])
        self.assertIs(D.a7_supplementary(D.phase_view(None, base)), False)              # no A7 entered
        # the G5 entry without the supplementary report (A7a)
        SCRATCH.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix='phdrv_a7_', dir=str(SCRATCH)))
        self.addCleanup(shutil.rmtree, tmp, True)
        reps = {}
        for k in ('s3', 's2', 's1'):
            (tmp / f'{k}.json').write_text('{}\n')
            reps[k] = (tmp / f'{k}.json', {'n_sequences': 100000, 'n_swept': 10, 'violations_total': 0,
                                           'slack_grid_s': [0.0] * 71, 'envelope': {'path': ENVELOPE}})
        cfg = D.Cfg(D.parse_args(['--root', str(tmp)]))
        text = D.stress_entry(cfg, reps, [{'name': 'v4_qnet_x'}], None, None)
        self.assertNotIn('upplementary', text)
        self.assertTrue(text.endswith('The test freeze takes the S1, S2 and S3 reports.'), text[-200:])


class DriverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real_before = real_snapshot()

    @classmethod
    def tearDownClass(cls):
        after = real_snapshot()
        if after != cls.real_before or not after['sealed'] or after['test_text_in_protocol']:
            raise AssertionError(f'the real tree changed during the tests: {cls.real_before} -> {after}')

    def to_p2_running(self):
        """A sandbox where G1 and G2 have run: the decision and the P2 job file recorded, the job file queued, one
        launch."""
        R = make_sandbox(self)
        decide(R)
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertEqual(set(entries(R)), {'d1_decision', 'p2_jobs'}, out_of(p))
        self.assertEqual(len(lines_of(R, 'launch_calls.log')), 1, out_of(p))
        return R

    # -------------------------------------------------------------------------------- G0
    def test_g0_waits_without_alert(self):
        R = make_sandbox(self, p1_done=False, amendments=('A3', 'A4'))
        decide(R)
        before = sha(R / PROTO)
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(alert_text(R), '')
        g0 = state(R)['gates']['G0']
        self.assertEqual(g0['status'], 'waiting')
        self.assertIn('P1_DONE.json does not exist', g0['note'])
        self.assertIn("['A7', 'A9']", g0['note'])
        self.assertEqual(state(R)['gates']['G1']['status'], 'blocked')
        self.assertEqual(sha(R / PROTO), before)
        self.assertEqual(calls(R, 'p2_jobs'), [])
        # an unsealed foreign edit: still a wait, no ALERT
        write_p1_done(R)
        foreign_amendment(R, '**Amendment A7, 2026-11-15 09:40 (Beijing time): sandbox.**')
        foreign_amendment(R, '**Amendment A9, 2026-11-15 09:41 (Beijing time): sandbox.**')
        sealed = (R / PROTO).read_text(encoding='utf-8')
        (R / PROTO).write_text(sealed + '\nunsealed edit\n', encoding='utf-8')
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(alert_text(R), '')
        self.assertIn('the seal does not verify', state(R)['gates']['G0']['note'])
        self.assertTrue(any('seal does not verify' in a for a in state(R)['attention']))
        (R / PROTO).write_text(sealed, encoding='utf-8')
        # every condition holds: G0 passes and G1 records the decision
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertEqual(state(R)['gates']['G0']['status'], 'passed')
        self.assertIn('d1_decision', entries(R))
        self.assertTrue(any(c['argv'] == ['--verify'] for c in calls(R, 'registration')))

    def test_g1_waits_for_the_decision(self):
        R = make_sandbox(self)
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p))
        st = state(R)
        self.assertEqual(st['gates']['G0']['status'], 'passed')
        self.assertEqual(st['gates']['G1']['status'], 'waiting')
        self.assertIn('D1_DECISION.json', st['gates']['G1']['note'])
        self.assertEqual(entries(R), {})
        base = json.loads((R / DRV / 'registered_baseline.json').read_text())
        self.assertIn('framelease_v4/protocol/tool.py', base['files'])
        self.assertEqual(base['seeded_from'], f'{P1D}/registered_baseline.json')

    # -------------------------------------------------------------------------------- dry run
    def test_dry_run_changes_nothing(self):
        R = make_sandbox(self)
        decide(R)
        before = tree(R)
        p = drive(R, '--dry-run')
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(tree(R), before)
        self.assertFalse((R / 'framelease_v4/.protocol.lock').exists())
        self.assertIn('WOULD: record G1 D1 decision', p.stdout)
        self.assertIn('| * **G1 D1 decision** (', p.stdout)
        self.assertEqual(calls(R, 'p2_jobs'), [])

    # -------------------------------------------------------------------------------- the path G1 -> G3
    def test_full_chain_to_phases_done(self):
        R = self.to_p2_running()
        # G1: the decision entry cites the decision file and the D1 summary and states the delegation
        g1 = flat(R, 'd1_decision')
        self.assertIn(sha(R / DRV / 'D1_DECISION.json'), g1)
        self.assertIn(sha(R / D1JSON), g1)
        self.assertIn('**continue**', g1)
        self.assertEqual(g1.split('Rationale:')[1].count('2026-11-14'), 1)     # the instruction's date once
        self.assertIn('(translated): "from now on, review yourself whether to proceed to the next phase"', g1)
        self.assertIn('covering every phase gate after P1, D1 included (Sec. 4.8', g1)
        self.assertIn('cited by the P1 driver\'s entry "D1 summary"', g1)
        self.assertNotIn(' at line ', g1)                                # other entries by label and sha256 (S2)
        # G2: one generation with env.sh sourced and CUDA hidden; the entry cites the job file, spec and check
        gen = calls(R, 'p2_jobs')
        self.assertEqual(len(gen), 1)
        self.assertEqual((gen[0]['env_sourced'], gen[0]['cuda']), ('1', ''))
        g2 = flat(R, 'p2_jobs')
        for suffix in ('.jsonl', '.stage.json', '.check.json'):
            self.assertIn(sha(R / (P2FILES + suffix)), g2)
        self.assertIn('block number 10', g2)
        self.assertIn(f'`{Q2}`', g2)
        self.assertIn('cited by the P1 driver\'s entry "Tuning freeze"', g2)
        self.assertNotIn(' at line ', g2)
        self.assertEqual(sorted(p.name for p in (R / Q2 / 'jobs.d').iterdir()), ['b10_rl_data.jsonl'])
        self.assertEqual(sha(R / Q2 / 'jobs.d/b10_rl_data.jsonl'), sha(R / (P2FILES + '.jsonl')))
        # the entry was sealed before the copy (the log order) and the runner was launched in a scope
        log = (R / DRV / 'driver.log').read_text()
        self.assertLess(log.index('recorded G2 P2 job file'), log.index('G2 P2: copied'))
        scope = lines_of(R, 'systemd_calls.log')
        self.assertEqual(len(scope), 1)
        self.assertRegex(scope[0], r'^--user --scope --unit=framelease-p2-runner-\d{8}T\d{6} -p OOMPolicy=continue '
                                   + 'bash ' + re.escape(str(R / 'mock/launch_queue.sh')) + ' ' + re.escape(Q2) + '$')
        self.assertTrue(lines_of(R, 'launch_calls.log')[0].endswith(Q2))
        self.assertEqual(state(R)['gates']['G3']['status'], 'running')
        # a second cycle while nothing is final: nothing new, no second launch
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(len(calls(R, 'p2_jobs')), 1)
        self.assertEqual(len(lines_of(R, 'launch_calls.log')), 1)
        self.assertEqual(calls(R, 'p2_check'), [])
        # every job final, the runner exited: G3 records the data manifest. A file under framelease_v4/rl still in
        # development (swept into the manifest by the G3 seal, not registered): G4 waits (attention, no ALERT, no P3
        # tool) until an amendment registers it, the split "A3b" of APPLY_PLAN Sec. 2, which cites its sha256 and
        # re-seals with the manifest of the driver's G3 seal: the driver baseline takes it (review fixes M4, M1)
        dev = R / 'framelease_v4/rl/p3_dev.py'
        dev.write_text('# P3 code in development\n')
        finish_p2(R)
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        st = state(R)
        self.assertEqual((st['gates']['G3']['status'], st['gates']['G4']['status']), ('passed', 'waiting'))
        self.assertIn('framelease_v4/rl/p3_dev.py', st['gates']['G4']['note'])
        self.assertTrue(any(a.startswith('G4: the code of its tools is not registered') for a in st['attention']))
        self.assertEqual(st['gates']['G4']['code']['unregistered'], ['framelease_v4/rl/p3_dev.py'])
        self.assertIn('framelease_v4/rl/p3_dev.py', flat(R, 'p2_data'))          # named as new in the manifest
        self.assertEqual((calls(R, 'p3_rl'), alert_text(R)), ([], ''))
        m_g3 = sha(R / MANIFEST)
        foreign_amendment(R, '**Amendment A3b, 2026-11-16 09:00 (Beijing time): sandbox registration of the P3 '
                             f'code.** `framelease_v4/rl/p3_dev.py` (sha256 `{sha(dev)}`).')
        self.assertEqual(sha(R / MANIFEST), m_g3)                     # a registration-only amendment
        # G4 then waits while a runner of another queue of the project is alive (P3 uses every core and needs the
        # GPU idle), no P3 tool runs
        other = FakeRunner(R, Q1)
        try:
            p = drive(R)
        finally:
            other.stop()
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        st = state(R)
        self.assertEqual(st['gates']['G4']['status'], 'waiting')
        self.assertIn(f'the runner of {Q1}', st['gates']['G4']['note'])
        self.assertEqual(st['gates']['G4']['code']['registered'], True)
        base = json.loads((R / DRV / 'registered_baseline.json').read_text())
        self.assertEqual(base['files'].get('framelease_v4/rl/p3_dev.py'), sha(dev))
        self.assertEqual(calls(R, 'p3_rl'), [])
        # then G4 (P3), G5 (stress tests) and G6 in one cycle; an unsealed edit of PROTOCOL.md right after
        # test_jobs.py (hook): G6 waits before the test freeze (no ALERT); the edit reverted, G6 goes on (test freeze,
        # P4-P6 queued, runner launched)
        p = drive(R, touch='test_jobs_written:framelease_v4/PROTOCOL.md')
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        st = state(R)
        self.assertEqual((st['gates']['G5']['status'], st['gates']['G6']['status']), ('passed', 'waiting'))
        self.assertIn('the seal does not verify', st['gates']['G6']['note'])
        self.assertEqual(calls(R, 'test_freeze'), [])
        text = (R / PROTO).read_text(encoding='utf-8')
        (R / PROTO).write_text(text.replace('# changed by the test hook at test_jobs_written\n', ''), encoding='utf-8')
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertEqual([c['write'] for c in calls(R, 'p2_check')], [False, True])
        ent = entries(R)
        order = ['d1_decision', 'p2_jobs', 'p2_data', 'rl_freeze', 'stress', 'test_freeze']
        self.assertEqual(sorted(ent, key=lambda k: ent[k]['line']), order)
        g3 = flat(R, 'p2_data')
        self.assertIn(sha(R / RLDATA / 'data_manifest.json'), g3)
        self.assertIn(sha(R / RLDATA / 'p2_check.json'), g3)
        self.assertIn('no missing episode', g3)
        # G4: dataset stage, calibration at the production sizes, the run with the recommended n_jobs, status
        p3 = calls(R, 'p3_rl')
        self.assertEqual([c['sub'] for c in p3], ['run', 'calibrate', 'run', 'status'])
        self.assertEqual(p3[0]['argv'][p3[0]['argv'].index('--stop-after') + 1], 'dataset')
        cal_argv = p3[1]['argv']
        for k, v in (('--sizes', '33,66,132'), ('--d-star', '4'), ('--out', CAL),
                     ('--lengths-from', 'outputs/framelease_v4/rl_freeze/dataset')):
            self.assertEqual(cal_argv[cal_argv.index(k) + 1], v, k)
        self.assertEqual(p3[2]['argv'][p3[2]['argv'].index('--n-jobs') + 1], '6')
        self.assertNotIn('--stop-after', p3[2]['argv'])
        g4 = flat(R, 'rl_freeze')
        rl = json.loads((R / RLF).read_text())
        for s in [sha(R / RLF), sha(R / CAL)] + [rl['families'][f]['network']['file_sha256'] for f in rl['families']]:
            self.assertIn(s, g4)
        self.assertIn('none used', g4)
        self.assertIn('n_jobs fqi 6, bandit 6, fqi_nolease 6', g4)
        # G5: s3, s2 on the registered grid, s2 on the relative grid (A7b), s1 last on L*, synthetic states
        st_calls = calls(R, 'stress')
        self.assertEqual([(c['sub'], c['grid']) for c in st_calls],
                         [('s3', None), ('s2', 'registered'), ('s2', 'relative'), ('s1', None)])
        self.assertEqual({c['states'] for c in st_calls[1:]}, {'synthetic'})
        s1_argv = st_calls[3]['argv']
        self.assertEqual(s1_argv[s1_argv.index('--envelope') + 1], ENVELOPE)
        self.assertEqual(sorted(s1_argv[i + 1] for i, x in enumerate(s1_argv) if x == '--qnet'),
                         sorted(str(R / rl['families'][f]['network']['path']) for f in rl['families']))
        g5 = flat(R, 'stress')
        reports = sorted((R / STRESS).glob('*.json'))
        self.assertEqual(len(reports), 4)
        for r in reports:
            self.assertIn(sha(r), g5)
        self.assertIn('supplementary: S2 relative to the slack floor', g5)
        self.assertIn(sha(R / DRV / 's1_guard.json'), g5)
        # G6: the job files once (env.sh sourced, CUDA hidden), the freeze written, its printed entry nested under
        # the driver's bullet, verified before and after the copy, the copies in tier order, the runner in a scope
        tj = calls(R, 'test_jobs')
        self.assertEqual([(c['env_sourced'], c['cuda']) for c in tj], [('1', '')])
        self.assertEqual([c['flag'] for c in calls(R, 'test_freeze')], ['--write', '--entry', '--verify', '--verify'])
        self.assertEqual(sorted(p.name for p in (R / Q4 / 'jobs.d').iterdir()), P4_NAMES)
        copied = [ln for ln in (R / DRV / 'driver.log').read_text().splitlines() if 'G6 P4-P6: copied' in ln]
        self.assertEqual([re.search(r'into \S+/(b\d\d_\w+\.jsonl)', ln).group(1) for ln in copied], P4_NAMES)
        log = (R / DRV / 'driver.log').read_text()
        self.assertLess(log.index('recorded G6 Test freeze'), log.index('G6 P4-P6: copied'))
        scope = lines_of(R, 'systemd_calls.log')
        self.assertEqual(len(scope), 2)
        self.assertRegex(scope[1], r'^--user --scope --unit=framelease-p4-runner-\d{8}T\d{6} -p OOMPolicy=continue '
                                   + 'bash ' + re.escape(str(R / 'mock/launch_queue.sh')) + ' ' + re.escape(Q4) + '$')
        g6 = entries(R)['test_freeze']['text']
        self.assertIn(sha(R / TFREEZE), flat(R, 'test_freeze'))
        printed = run([PY, '-I', '-B', str(R / 'mock/test_freeze.py'), '--entry', '--out-dir',
                       'outputs/framelease_v4/test_freeze', '--queue-dir', f'{Q4}/jobs.d', '--jobs-dir',
                       'outputs/framelease_v4/test_jobs'], R).stdout.rstrip('\n').split('\n')
        glines = g6.split('\n')
        k = next(i for i, ln in enumerate(glines) if ln.startswith('  **Test freeze, '))
        self.assertEqual(D.nest_entry_lines([ln[2:] for ln in glines[k:]])[1], D.nest_entry_lines(printed)[1])
        self.assertTrue(all(len(ln) <= 120 for ln in glines))
        self.assertTrue(any(sha(R / TFREEZE) in ln for ln in glines))      # cited on one line (Sec. 13.2 citations)
        for ln in glines[1:]:
            body = ln[4:] if ln.startswith('    ') else ln[2:]
            self.assertTrue(ln.startswith('  * ') or not D.LINE_START.match(body), ln)
        # every check: seal, verify, statuses; the P1 entries unchanged; one heading
        self.assertTrue(seal_ok(R))
        self.assertTrue(verify_ok(R))
        st = state(R)
        self.assertEqual([st['gates'][g]['status'] for g in D.GATES], ['passed'] * 7 + ['running', 'blocked'])
        self.assertEqual(alert_text(R), '')
        v = view(R)
        self.assertEqual(set(v['p1_entries']), {'freeze', 'd1'})
        self.assertEqual([ln.strip() for ln in v['lines']].count(HEADING), 1)
        for key, e in v['entries'].items():          # no continuation line starts a list, a heading or a quote
            for ln in e['text'].split('\n')[1:]:
                self.assertFalse(D.LINE_START.match(ln[4:] if ln.startswith('    ') else ln[2:])
                                 and not ln.startswith('  * '), (key, ln))
        # idempotent: another cycle runs no tool, writes no entry and launches nothing
        before = sha(R / PROTO)
        n = len(calls(R))
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(sha(R / PROTO), before)
        self.assertEqual([c['tool'] for c in calls(R)[n:]], [])
        self.assertEqual(len(lines_of(R, 'systemd_calls.log')), 2)
        # G7: job health only, the progress per job file in state.json; half of the jobs final
        prog = state(R)['gates']['G7']['progress']
        self.assertEqual((prog['jobs'], prog['final'], prog['pending']), (10, 0, 10))
        self.assertEqual(prog['per_job_file']['b11_ti_main.jsonl'],
                         {'tier': 3, 'jobs': 2, 'final': 0, 'registered': True})
        finish_p2(R, queue=Q4, only=lambda j: j['id'].endswith('_r0'), runner_exit=False)
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        st = state(R)
        self.assertEqual((st['gates']['G7']['status'], st['gates']['G8']['status']), ('running', 'blocked'))
        self.assertEqual(st['gates']['G7']['progress']['final'], 5)
        self.assertNotIn('outcome', json.dumps(st['gates']['G7']))       # counts only (Sec. 9.11)
        # every job final and the runner exited: G7 passes; G8 waits (no ALERT) for analyze_v4.py and its entry
        finish_p2(R, queue=Q4, outcome=lambda j: 'agent_crashed' if j['id'] == 'v4p4_ti_main_r1' else 'ok')
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        st = state(R)
        self.assertEqual((st['gates']['G7']['status'], st['gates']['G8']['status']), ('passed', 'waiting'))
        self.assertIn(f'{ANALYZE} does not exist yet', st['gates']['G8']['note'])
        (R / ANALYZE).write_text('# sandbox stand-in for analyze_v4.py (R-4)\n')
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertIn(f'Sec. 13.2 does not cite {ANALYZE}', state(R)['gates']['G8']['note'])
        self.assertTrue(any(a.startswith('G8: the analysis freeze waits') for a in state(R)['attention']))
        self.assertEqual(alert_text(R), '')
        self.assertEqual(calls(R, 'aggregate'), [])          # no aggregation of any kind before G8
        # the analysis code registered: one aggregation with --write-freeze-record, the record validated and
        # recorded, PHASES_DONE.json, the driver ends
        register_analysis(R)
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        agg = calls(R, 'aggregate')
        self.assertEqual(len(agg), 1)
        (out_name,) = final_dirs(R)
        self.assertRegex(out_name, r'^final_\d{8}T\d{6}$')
        out_rel, rec_rel = f'{ANALYSIS}/{out_name}', f'{ANALYSIS}/{out_name}/analysis_freeze.json'
        argv = agg[0]['argv']
        for k, v in (('--queue', Q4), ('--specs', 'outputs/framelease_v4/test_jobs/FULL'), ('--rl-freeze', RLF),
                     ('--tuning-freeze', FREEZE), ('--write-freeze-record', rec_rel), ('--out', out_rel)):
            self.assertEqual(argv[argv.index(k) + 1], v, k)
        for flag in ('--force', '--arm-summary', '--analysis-freeze', '--jobs'):
            self.assertNotIn(flag, argv)
        g8 = flat(R, 'analysis_freeze')
        for s in (sha(R / rec_rel), sha(R / out_rel / 'SHA256SUMS'), sha(R / ANALYZE)):
            self.assertIn(s, g8)
        self.assertIn('outcomes ok 9, agent_crashed 1, sim_failure 0', g8)
        self.assertIn('10 jobs of the 5 job files of the test freeze', g8)
        self.assertIn(f'`{ANALYZE}` (sha256 `{sha(R / ANALYZE)}`) is registered in Sec. 13.2 by Amendment A10.', g8)
        self.assertNotIn(' at line ', g8)                    # entries by label and sha256, never by line (S2)
        self.assertIn(f'(entry "G6 Test freeze", record `{TFREEZE}` sha256 `{sha(R / TFREEZE)}`)', g8)
        g8_lines = entries(R)['analysis_freeze']['text'].split('\n')
        self.assertTrue(all(len(ln) <= 120 for ln in g8_lines))
        self.assertTrue(all(ln.startswith('  ') and not D.LINE_START.match(ln[2:]) for ln in g8_lines[1:]))
        (SCRATCH / 'g8_entry_sample.txt').write_text('\n'.join(g8_lines) + '\n')       # for inspection
        for rel in ANALYSIS_FILES:
            self.assertIn(sha(R / rel), g8)
        rec = json.loads((R / rec_rel).read_text())
        self.assertEqual(set(rec['job_files']), {f'{Q4}/jobs.d/{n}' for n in P4_NAMES})
        done = json.loads((R / DONE).read_text())
        self.assertEqual(done['schema'], 'framelease_v4.phase_driver_done/1')
        self.assertEqual((done['analysis_freeze']['sha256'], done['analysis_freeze']['record']),
                         (sha(R / rec_rel), rec_rel))
        self.assertEqual([e['key'] for e in done['entries']], order + ['analysis_freeze'])
        self.assertTrue(done['seal_ok'])
        st = state(R)
        self.assertEqual([st['gates'][g]['status'] for g in D.GATES], ['passed'] * 9)
        self.assertEqual(st['driver']['status'], 'DONE')
        self.assertTrue(seal_ok(R))
        self.assertTrue(verify_ok(R))
        self.assertEqual(alert_text(R), '')
        # the driver ends: a restart does nothing
        before, n = sha(R / PROTO), len(calls(R))
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertIn('every phase is done', (R / DRV / 'driver.log').read_text())
        self.assertEqual((sha(R / PROTO), len(calls(R))), (before, n))
        self.assertTrue(all(c['arm_summary'] is None and c['analysis_freeze'] is None for c in calls(R, 'aggregate')))

    # -------------------------------------------------------------------------------- G1 decisions
    def test_d1_stop_ends_the_driver(self):
        R = make_sandbox(self)
        decide(R, 'stop')
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertIn('**stop**', flat(R, 'd1_decision'))
        done = json.loads((R / DRV / 'P2_STOPPED.json').read_text())
        self.assertEqual(done['decision']['decision'], 'stop')
        self.assertEqual(calls(R, 'p2_jobs'), [])
        self.assertFalse((R / Q2).exists())
        before = sha(R / PROTO)
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertIn('nothing to do', (R / DRV / 'driver.log').read_text())
        self.assertEqual(sha(R / PROTO), before)

    def test_decision_on_another_d1_summary_alerts(self):
        R = make_sandbox(self)
        decide(R, d1_sha='e' * 64)
        before = sha(R / PROTO)
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('d1_summary_sha256', alert_text(R))
        self.assertEqual(sha(R / PROTO), before)
        p = drive(R)                                  # refuses while ALERT.txt exists
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('refusing to run', (R / DRV / 'driver.log').read_text())
        resolve_alert(R)
        decide(R, 'maybe')
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn("decision 'maybe'", alert_text(R))
        # a decision file being written (not readable JSON, modified just now): wait, attention, no ALERT; unchanged
        # beyond the grace period: ALERT naming the atomic write (review fix S5)
        resolve_alert(R)
        (R / DRV / 'D1_DECISION.json').write_text('{"decision": "contin')
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(alert_text(R), '')
        self.assertEqual(state(R)['gates']['G1']['status'], 'waiting')
        self.assertTrue(any('is not readable JSON yet' in a for a in state(R)['attention']), state(R)['attention'])
        old = time.time() - 600
        os.utime(R / DRV / 'D1_DECISION.json', (old, old))
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('write it atomically', alert_text(R))
        self.assertEqual(entries(R), {})

    # -------------------------------------------------------------------------------- crash and restart
    def test_crash_restart_idempotence(self):
        R = make_sandbox(self)
        decide(R)
        # each crash hits the next occurrence of its point: G1's record transaction, the P2 generation, G2's record,
        # the copy, the launch; then the P2 completion check
        for point in ('txn_begin', 'manifest_written', 'protocol_written', 'p2_generated', 'sealed', 'copied',
                      'launched'):
            p = drive(R, crash=point)
            self.assertEqual(p.returncode, 70, f'{point}: ' + out_of(p) + alert_text(R))
            self.assertIn(f'exiting at {point}', (R / DRV / 'driver.log').read_text())
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        finish_p2(R)
        p = drive(R, crash='p2_check_written')
        self.assertEqual(p.returncode, 70, out_of(p) + alert_text(R))
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        text = (R / PROTO).read_text(encoding='utf-8')
        for gate, label in (('G1', 'D1 decision'), ('G2', 'P2 job file'), ('G3', 'P2 data manifest')):
            self.assertEqual(text.count(f'* **{gate} {label}** ('), 1, gate)
        self.assertEqual(len(calls(R, 'p2_jobs')), 1)
        self.assertEqual(sorted(p.name for p in (R / Q2 / 'jobs.d').iterdir()), ['b10_rl_data.jsonl'])
        self.assertEqual([ln.split()[-1] for ln in lines_of(R, 'launch_calls.log')], [Q2, Q4])   # P2, then P4-P6
        self.assertEqual([c['write'] for c in calls(R, 'p2_check')], [False, True])
        self.assertFalse((R / DRV / 'protocol_txn.json').exists())
        self.assertTrue(seal_ok(R))
        self.assertTrue(verify_ok(R))
        self.assertEqual(alert_text(R), '')

    # -------------------------------------------------------------------------------- G3 outcomes
    def test_p2_check_fail_and_missing_episodes(self):
        R = self.to_p2_running()
        finish_p2(R)
        scenario(R, p2_fail=True)
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('FAIL', alert_text(R))
        self.assertEqual([c['write'] for c in calls(R, 'p2_check')], [False])
        self.assertFalse((R / RLDATA).exists())
        self.assertNotIn('p2_data', entries(R))
        resolve_alert(R)
        missing = 'v4p2_fl_behaviour_E5_eps0.300_d4_k1.5_s11_r102'
        scenario(R, p2_missing=[missing])
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn(missing, alert_text(R))
        self.assertIn('P2_MISSING_ACK.txt', alert_text(R))
        self.assertNotIn('p2_data', entries(R))
        resolve_alert(R)
        (R / DRV / 'P2_MISSING_ACK.txt').write_text(f'{missing}: accepted (Sec. 9.8), sandbox decision\n')
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        g3 = flat(R, 'p2_data')
        self.assertIn(missing, g3)
        self.assertIn(sha(R / DRV / 'P2_MISSING_ACK.txt'), g3)
        self.assertIn('1 missing episode(s)', g3)

    # -------------------------------------------------------------------------------- G4 open cases
    def test_p3_open_case_and_missing_episodes(self):
        R = self.to_p2_running()
        missing = 'v4p2_fl_behaviour_E5_eps0.300_d4_k1.5_s11_r102'
        scenario(R, p2_missing=[missing], p3_stop_case='no_selectable')
        (R / DRV / 'P2_MISSING_ACK.txt').write_text(f'{missing}: accepted (Sec. 9.8), sandbox decision\n')
        finish_p2(R)
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        al = alert_text(R)
        for s in ("case 'no_selectable'", '(a)', 'P3_OPEN_CASES.json', '"no_selectable": "adet"'):
            self.assertIn(s, al)
        p3 = calls(R, 'p3_rl')
        self.assertEqual([c['sub'] for c in p3], ['run', 'calibrate', 'run'])
        for c in (p3[0], p3[2]):                         # case (c) follows from the G3 acknowledgement
            self.assertEqual(c['argv'][c['argv'].index('--missing-episodes') + 1], 'proceed')
        self.assertIn('p2_data', entries(R))
        self.assertNotIn('rl_freeze', entries(R))
        # a malformed decision: ALERT before any run
        resolve_alert(R)
        (R / DRV / 'P3_OPEN_CASES.json').write_text(json.dumps({'options': {'no_selectable': 'maybe'}}) + '\n')
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn("option no_selectable: 'maybe'", alert_text(R))
        self.assertIn('no rationale', alert_text(R))
        self.assertEqual(len(calls(R, 'p3_rl')), 3)
        # the coordinating session's decision: passed to the run (with the derived case (c)), cited by the entry
        resolve_alert(R)
        (R / DRV / 'P3_OPEN_CASES.json').write_text(json.dumps(
            {'schema': 'framelease_v4.p3_open_cases/1', 'options': {'no_selectable': 'adet'},
             'rationale': 'Sandbox: the audit default'}) + '\n')
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        p3 = calls(R, 'p3_rl')
        self.assertEqual([c['sub'] for c in p3], ['run', 'calibrate', 'run', 'run', 'status'])   # calibrated once
        last = p3[3]['argv']
        self.assertEqual(last[last.index('--no-selectable') + 1], 'adet')
        self.assertEqual(last[last.index('--missing-episodes') + 1], 'proceed')
        g4 = flat(R, 'rl_freeze')
        for s in (sha(R / DRV / 'P3_OPEN_CASES.json'), sha(R / DRV / 'P2_MISSING_ACK.txt'),
                  '--no-selectable adet (case (a))', '--missing-episodes proceed (case (c))',
                  'refit_fqi: case no_selectable, option adet', 'Sandbox: the audit default.'):
            self.assertIn(s, g4)
        self.assertIn('test_freeze', entries(R))

    # -------------------------------------------------------------------------------- G5 stress tests
    def test_stress_reports_and_the_s1_guard(self):
        R = self.to_p2_running()
        finish_p2(R)
        # a stress_bench.py still running (left by a killed driver): G5 waits, attention, no stress run (review fix M2)
        orphan = FakeTool(R / 'mock/stress_bench.py')
        try:
            p = drive(R)
        finally:
            orphan.stop()
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertEqual(state(R)['gates']['G5']['status'], 'waiting')
        self.assertIn('stress_bench.py (pids', state(R)['gates']['G5']['note'])
        self.assertEqual(calls(R, 'stress'), [])
        self.assertIn('rl_freeze', entries(R))
        scenario(R, s2_fail=True)
        busy = [{'pid': 777, 'cpu_share': 0.8, 'comm': 'firefox', 'cmdline': '/usr/bin/firefox'}]
        p = drive(R, foreign=busy)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('does not pass', alert_text(R))
        self.assertIn('admitted actions with bound >= D*', alert_text(R))
        self.assertNotIn('stress', entries(R))
        # the failing report moved aside by hand; then the driver's foreign-CPU sample refuses S1 4 times: ALERT
        bad = next((R / STRESS).glob('s2_registered_*.json'))
        bad.rename(R / STRESS / ('failed_' + bad.name + '.aside'))
        scenario(R)
        resolve_alert(R)
        for k in range(1, 4):
            p = drive(R, foreign=busy)
            self.assertEqual(p.returncode, 0, f'{k}: ' + out_of(p) + alert_text(R))
            self.assertEqual(len(json.loads((R / DRV / 's1_guard.json').read_text())['attempts']), k)
            self.assertTrue(any('S1 refused because of foreign CPU load' in a for a in state(R)['attention']))
        p = drive(R, foreign=busy)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('refused 4 times', alert_text(R))
        self.assertIn('S1_ACCEPT_FOREIGN_CPU.txt', alert_text(R))
        guard = json.loads((R / DRV / 's1_guard.json').read_text())
        self.assertEqual((len(guard['attempts']), len(guard['closed_series'])), (0, 1))
        self.assertEqual([c['sub'] for c in calls(R, 'stress')], ['s3', 's2', 's2', 's2'])   # no s1 started
        # a dry run at G5 plans S1 and changes nothing
        resolve_alert(R)
        before = tree(R)
        p = drive(R, '--dry-run')
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(tree(R), before)
        self.assertIn('WOULD: G5: sample the foreign CPU, then', p.stdout)
        self.assertIn('stress_bench.py s1 --registered', p.stdout)
        # a runner of this project alive: S1 waits, no attempt counted
        other = FakeRunner(R, Q1)
        try:
            p = drive(R)
        finally:
            other.stop()
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(json.loads((R / DRV / 's1_guard.json').read_text())['attempts'], [])
        self.assertTrue(any('S1 needs an exclusive CPU' in a for a in state(R)['attention']), state(R)['attention'])
        # stress_bench.py's own foreign-CPU refusal counts the same way
        scenario(R, s1_refuse=1)
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertEqual([a['source'] for a in json.loads((R / DRV / 's1_guard.json').read_text())['attempts']],
                         ["stress_bench.py's guard"])
        # the load accepted by the coordinating session: --accept-foreign-cpu, cited by the entry
        (R / DRV / 'S1_ACCEPT_FOREIGN_CPU.txt').write_text('Sandbox: the desktop load is accepted and recorded\n')
        p = drive(R, foreign=busy)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertEqual([c['accept'] for c in calls(R, 'stress') if c['sub'] == 's1'], [False, True])
        g5 = flat(R, 'stress')
        self.assertIn(sha(R / DRV / 'S1_ACCEPT_FOREIGN_CPU.txt'), g5)
        self.assertIn('1 earlier attempt(s) in this series and 1 closed series', g5)
        self.assertNotIn('failed_', g5)
        self.assertIn('test_freeze', entries(R))

    # -------------------------------------------------------------------------------- crash and restart, G3 -> G6
    def test_crash_restart_p3_to_p4(self):
        R = self.to_p2_running()
        finish_p2(R)
        points = ('p2_check_written', 'manifest_written', 'p3_dataset_done', 'p3_calibrated', 'p3_run_done',
                  'protocol_written', 'stress_s3_done', 'stress_s2_done', 'stress_s2_relative_done', 'stress_s1_done',
                  'sealed', 'test_jobs_written', 'test_freeze_written', 'txn_begin', 'copied', 'p4_queued', 'launched')
        for point in points:
            p = drive(R, crash=point)
            self.assertEqual(p.returncode, 70, f'{point}: ' + out_of(p) + alert_text(R))
            self.assertIn(f'exiting at {point}', (R / DRV / 'driver.log').read_text())
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        text = (R / PROTO).read_text(encoding='utf-8')
        for key, label in LABELS.items():
            self.assertEqual(text.count(f'* **{label}** ('), 1, key)
        p3 = [c['sub'] + ('/dataset' if '--stop-after' in c['argv'] else '') for c in calls(R, 'p3_rl')]
        self.assertEqual(p3, ['run/dataset', 'run/dataset', 'calibrate', 'run', 'status'])
        self.assertEqual(sorted(f'{c["sub"]}/{c["grid"]}' for c in calls(R, 'stress')),
                         ['s1/None', 's2/registered', 's2/relative', 's3/None'])
        self.assertEqual(len(calls(R, 'test_jobs')), 1)
        self.assertEqual(sorted(p.name for p in (R / Q4 / 'jobs.d').iterdir()), P4_NAMES)
        self.assertEqual([ln.split()[-1] for ln in lines_of(R, 'launch_calls.log')], [Q2, Q4])
        self.assertFalse((R / DRV / 'protocol_txn.json').exists())
        self.assertTrue(seal_ok(R))
        self.assertTrue(verify_ok(R))
        self.assertEqual(alert_text(R), '')
        self.assertEqual(state(R)['gates']['G6']['status'], 'passed')

    # -------------------------------------------------------------------------------- G7 P4-P6 job health
    def test_p4_job_health_and_runner_rules(self):
        """G7 on queue_p4: a signal exit is never relaunched; 'queue empty' with pending jobs is relaunched in a scope;
        STOP: attention, no launch; an unregistered job file: attention, then an ALERT at G8; circuit breaker: ALERT;
        every job final while the runner lives: wait; a dry run at G8 changes nothing. No aggregation before G8."""
        R = to_p4_running(self)
        n = len(lines_of(R, 'launch_calls.log'))
        runner_event(R, 'signal 15', 4, queue=Q4)
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertEqual(len(lines_of(R, 'launch_calls.log')), n)
        att = state(R)['attention']
        self.assertTrue(any('stopped by a signal' in a and Q4 in a for a in att), att)
        runner_event(R, 'queue empty', 0, queue=Q4)
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertEqual(len(lines_of(R, 'launch_calls.log')), n + 1)
        self.assertRegex(lines_of(R, 'systemd_calls.log')[-1],
                         r'^--user --scope --unit=framelease-p4-runner-\d{8}T\d{6} -p OOMPolicy=continue bash '
                         r'\S+/launch_queue.sh ' + re.escape(Q4) + '$')
        runner_event(R, 'queue empty', 0, queue=Q4)
        (R / Q4 / 'STOP').write_text('disk\n')
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(len(lines_of(R, 'launch_calls.log')), n + 1)
        self.assertTrue(any(f'{Q4}/STOP exists and no runner runs' in a for a in state(R)['attention']))
        runner = FakeRunner(R, Q4)                       # alive with STOP: attention, nothing launched
        try:
            p = drive(R)
        finally:
            runner.stop()
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertTrue(any(f'{Q4}/STOP exists: the runner starts no new job' in a for a in state(R)['attention']))
        self.assertIs(state(R)['gates']['G7']['progress']['runner_alive'], True)
        self.assertTrue((R / Q4 / 'STOP').exists())
        (R / Q4 / 'STOP').unlink()
        runner_event(R, 'signal 15', 4, queue=Q4)
        extra = R / Q4 / 'jobs.d/b99_extra.jsonl'
        extra.write_text('{"id": "v4p6_extra_r0", "kind": "closed_loop", "cmd": ["true"]}\n')
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertTrue(any('job files that the test freeze does not name' in a for a in state(R)['attention']))
        self.assertFalse(state(R)['gates']['G7']['progress']['per_job_file']['b99_extra.jsonl']['registered'])
        runner_event(R, 'circuit breaker', 3, queue=Q4)
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('circuit breaker', alert_text(R))
        self.assertEqual(len(lines_of(R, 'launch_calls.log')), n + 1)
        resolve_alert(R)
        # every job final, the runner still alive: G7 waits for its exit
        finish_p2(R, queue=Q4)
        runner = FakeRunner(R, Q4)
        try:
            p = drive(R)
        finally:
            runner.stop()
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertIn('waiting for the runner to exit', state(R)['gates']['G7']['note'])
        self.assertEqual(state(R)['gates']['G8']['status'], 'blocked')
        # G8 refuses the unregistered job file once the analysis code is registered
        register_analysis(R)
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('holds job files that the test freeze does not name', alert_text(R))
        self.assertEqual((calls(R, 'aggregate'), final_dirs(R)), ([], []))
        resolve_alert(R)
        extra.unlink()
        # a dry run at G8: the aggregation planned, nothing changed
        before = tree(R)
        p = drive(R, '--dry-run')
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(tree(R), before)
        self.assertIn('WOULD: G8: ', p.stdout)
        self.assertIn('aggregate_v4.py --queue outputs/framelease_v4/queue_p4', p.stdout)
        self.assertIn('--write-freeze-record outputs/framelease_v4/analysis/final_', p.stdout)
        self.assertEqual(calls(R, 'aggregate'), [])
        self.assertEqual(alert_text(R), '')

    # -------------------------------------------------------------------------------- G8 analysis freeze
    def test_analysis_freeze_alerts_and_crash_restart(self):
        """G8: an aggregation that fails (exit 2) or a record that does not validate: ALERT, never rewritten; an
        analysis module changed while the record was made: ALERT; outputs of an aggregation stopped before its record:
        redone with --force; two final_* directories: ALERT; a crash at every G8 point: one entry, one PHASES_DONE."""
        R = to_p4_running(self)
        finish_p2(R, queue=Q4)
        register_analysis(R)
        scenario(R, agg_inconsistent=True)
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('exited 2', alert_text(R))
        (first,) = final_dirs(R)
        self.assertFalse((R / ANALYSIS / first / 'analysis_freeze.json').exists())
        resolve_alert(R)
        # an analysis module changed after the record was written (hook at aggregate_written): ALERT; restored, the
        # record of the registered code is used
        scenario(R)
        mod = R / ANALYSIS_FILES[0]
        original = mod.read_text()
        p = drive(R, touch=f'aggregate_written:{ANALYSIS_FILES[0]}')
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('the analysis code changed while aggregate_v4.py made the record', alert_text(R))
        self.assertNotIn('analysis_freeze', entries(R))
        self.assertEqual(final_dirs(R), [first])
        self.assertTrue((R / ANALYSIS / first / 'analysis_freeze.json').exists())
        mod.write_text(original)
        resolve_alert(R)
        # that directory moved aside by hand; a directory with the outputs of an aggregation stopped before its
        # record: redone there with --force; a record of other job files: ALERT, kept
        (R / ANALYSIS / first).rename(R / ANALYSIS / f'aside_{first}')
        stopped = R / ANALYSIS / 'final_20261201T000000'
        stopped.mkdir()
        (stopped / 'runs.csv').write_text('job,outcome\n')
        scenario(R, agg_extra_job_file=True, agg_bad_sums=True)
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('does not validate', alert_text(R))
        self.assertIn('are not the registered P4-P6 copies', alert_text(R))
        self.assertIn('SHA256SUMS: runs.csv is at sha256', alert_text(R))         # sha256sum -c (review fix S3)
        self.assertEqual([c['force'] for c in calls(R, 'aggregate')], [False, False, True])
        p = drive(R)                                     # refuses while ALERT.txt exists
        self.assertEqual(p.returncode, 1, out_of(p))
        resolve_alert(R)
        p = drive(R)                                     # the record is never rewritten: the same ALERT
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('does not validate', alert_text(R))
        self.assertEqual(len(calls(R, 'aggregate')), 3)
        resolve_alert(R)
        stopped.rename(R / ANALYSIS / 'aside_2')
        (R / ANALYSIS / 'final_20261202T000000').mkdir()
        (R / ANALYSIS / 'final_20261203T000000').mkdir()
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('2 directories final_*', alert_text(R))
        resolve_alert(R)
        for d in ('final_20261202T000000', 'final_20261203T000000'):
            (R / ANALYSIS / d).rmdir()
        scenario(R)
        # a crash at every G8 point (after the aggregation, then in the record transaction: a restart after
        # 'protocol_written' finishes the transaction from protocol_txn.json, so 'sealed' is not reached again here;
        # it is covered by the crash tests of G1-G6), then a clean cycle
        for point in ('aggregate_written', 'txn_begin', 'manifest_written', 'protocol_written'):
            p = drive(R, crash=point)
            self.assertEqual(p.returncode, 70, f'{point}: ' + out_of(p) + alert_text(R))
            self.assertIn(f'exiting at {point}', (R / DRV / 'driver.log').read_text())
            self.assertFalse((R / DONE).exists())
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertEqual(len(calls(R, 'aggregate')), 4)
        (out_name,) = final_dirs(R)
        text = (R / PROTO).read_text(encoding='utf-8')
        self.assertEqual(text.count('* **G8 Analysis freeze** ('), 1)
        for key, label in LABELS.items():
            self.assertEqual(text.count(f'* **{label}** ('), 1, key)
        rec = R / ANALYSIS / out_name / 'analysis_freeze.json'
        self.assertIn(sha(rec), flat(R, 'analysis_freeze'))
        self.assertEqual(json.loads((R / DONE).read_text())['analysis_freeze']['sha256'], sha(rec))
        self.assertFalse((R / DRV / 'protocol_txn.json').exists())
        self.assertTrue(seal_ok(R))
        self.assertTrue(verify_ok(R))
        self.assertEqual([ln.split()[-1] for ln in lines_of(R, 'launch_calls.log')], [Q2, Q4])
        self.assertTrue(all(c['arm_summary'] is None and c['analysis_freeze'] is None for c in calls(R, 'aggregate')))

    # -------------------------------------------------------------------------------- runner rules
    def test_runner_rules(self):
        R = self.to_p2_running()
        # a launch record without any runner record (the runner did not start): attention, no relaunch loop; without
        # the launch record the queue never had a runner: launched
        (R / Q2 / 'status.jsonl').write_text('')
        (R / Q2 / 'launch_20261115T000000Z.json').write_text('{"runner_pid": 99999}\n')
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(len(lines_of(R, 'launch_calls.log')), 1)
        self.assertTrue(any('the runner did not start' in a for a in state(R)['attention']), state(R)['attention'])
        (R / Q2 / 'launch_20261115T000000Z.json').unlink()
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertEqual(len(lines_of(R, 'launch_calls.log')), 2)
        n = len(lines_of(R, 'launch_calls.log'))
        # stopped by a signal: attention, never relaunched
        runner_event(R, 'signal 15', 4)
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(len(lines_of(R, 'launch_calls.log')), n)
        self.assertTrue(any('stopped by a signal' in a for a in state(R)['attention']), state(R)['attention'])
        # a normal 'queue empty' exit with pending jobs: relaunched in a scope
        runner_event(R, 'queue empty', 0)
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertEqual(len(lines_of(R, 'launch_calls.log')), n + 1)
        self.assertEqual(len(lines_of(R, 'systemd_calls.log')), n + 1)
        self.assertIn('--unit=framelease-p2-runner-', lines_of(R, 'systemd_calls.log')[-1])
        # STOP in the queue: attention, no launch, STOP kept
        runner_event(R, 'queue empty', 0)
        (R / Q2 / 'STOP').write_text('disk\n')
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(len(lines_of(R, 'launch_calls.log')), n + 1)
        self.assertTrue((R / Q2 / 'STOP').exists())
        self.assertTrue(any('STOP exists' in a for a in state(R)['attention']))
        (R / Q2 / 'STOP').unlink()
        # a runner of another queue of the project is alive: no launch (the queues share the GPU)
        other = FakeRunner(R, Q1)
        try:
            p = drive(R)
        finally:
            other.stop()
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(len(lines_of(R, 'launch_calls.log')), n + 1)
        self.assertTrue(any('runner of' in a and Q1 in a for a in state(R)['attention']), state(R)['attention'])
        self.assertTrue(state(R)['priority']['closed_loop_active'])
        # the second 'queue empty' exit in a row without a job started (after the relaunch): no further launch,
        # attention (review fix S8)
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertEqual(len(lines_of(R, 'launch_calls.log')), n + 1)
        self.assertTrue(any("exited 'queue empty' 2 times in a row without starting a job" in a
                            for a in state(R)['attention']), state(R)['attention'])
        # circuit breaker: ALERT, no launch
        runner_event(R, 'circuit breaker', 3)
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('circuit breaker', alert_text(R))
        self.assertEqual(len(lines_of(R, 'launch_calls.log')), n + 1)
        # queue_p2/jobs.d emptied after G2 (G3 called in process): ALERT, as at G7 (review fix S6)
        (R / Q2 / 'jobs.d/b10_rl_data.jsonl').rename(R / Q2 / 'b10_rl_data.jsonl.aside')
        cfg = D.Cfg(D.parse_args(['--root', str(R), '--no-consistency-check', '--normal-priority']))
        with self.assertRaises(D.Alert) as cm:
            D.gate_g3(cfg, D.Ctx(cfg))
        self.assertIn('holds no job although G2 queued b10_rl_data.jsonl', cm.exception.problem)

    def test_launch_failure_alerts_without_fallback(self):
        R = make_sandbox(self)
        decide(R)
        (R / 'mock/launch_fail').write_text('')
        p = drive(R)
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('never falls back', alert_text(R))
        self.assertIn('p2_jobs', entries(R))                     # recorded and copied before the launch
        self.assertTrue((R / Q2 / 'jobs.d/b10_rl_data.jsonl').exists())

    # -------------------------------------------------------------------------------- protocol lock, registered files
    def test_protocol_lock_contention(self):
        R = make_sandbox(self)
        decide(R)
        # a registration.py still running (left by a killed driver): the driver waits, attention, no ALERT (review
        # fixes M2, S7)
        n_reg = len(calls(R, 'registration'))
        orphan = FakeTool(R / 'mock/registration_sandbox.py')
        try:
            p = drive(R)
        finally:
            orphan.stop()
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual((alert_text(R), entries(R)), ('', {}))
        self.assertEqual(state(R)['gates']['G0']['status'], 'waiting')
        self.assertTrue(any('registration_sandbox.py (pids' in a for a in state(R)['attention']), state(R)['attention'])
        self.assertEqual(len(calls(R, 'registration')), n_reg)          # no registration.py started
        holder = LockHolder(R / 'framelease_v4/.protocol.lock')
        try:
            p = drive(R)
        finally:
            holder.stop()
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertEqual(alert_text(R), '')
        self.assertEqual(entries(R), {})
        self.assertEqual(state(R)['gates']['G1']['status'], 'waiting_lock')
        p = drive(R)
        self.assertEqual(p.returncode, 0, out_of(p) + alert_text(R))
        self.assertIn('d1_decision', entries(R))

    def test_registered_and_unregistered_files(self):
        R = make_sandbox(self)
        dev = R / 'framelease_v4/protocol/dev_tool.py'
        dev.write_text('# code in development, swept into the manifest by its glob\n')
        foreign_amendment(R, '**Operational note (sandbox).** No file registered.')
        p = drive(R)                                     # G1 waits; the baseline follows the new seal
        self.assertEqual(p.returncode, 0, out_of(p))
        base = json.loads((R / DRV / 'registered_baseline.json').read_text())
        self.assertNotIn('framelease_v4/protocol/dev_tool.py', base['files'])
        self.assertIn('framelease_v4/protocol/tool.py', base['files'])
        dev.write_text('# edited: not registered, allowed\n')
        decide(R)
        tool = R / 'framelease_v4/protocol/tool.py'
        original = tool.read_text()
        # the registered tool.py is edited after the G1 record (at the P2 generation): the G2 pre-check stops
        p = drive(R, touch='p2_generated:framelease_v4/protocol/tool.py')
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('framelease_v4/protocol/dev_tool.py', flat(R, 'd1_decision'))   # named as changed
        self.assertIn('framelease_v4/protocol/tool.py', alert_text(R))
        self.assertIn('registered file(s) differ from the sealed manifest', alert_text(R))
        self.assertNotIn('p2_jobs', entries(R))
        self.assertFalse((R / Q2).exists())
        # restored; then edited between the pre-check and --write-manifest: the post-manifest check stops (F1)
        tool.write_text(original)
        resolve_alert(R)
        before = sha(R / PROTO)
        p = drive(R, touch='txn_begin:framelease_v4/protocol/tool.py')
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('changed while the driver re-sealed', alert_text(R))
        self.assertEqual(sha(R / PROTO), before)
        self.assertNotIn('p2_jobs', entries(R))
        self.assertFalse((R / Q2).exists())
        # restored; then removed in the same window: it would leave the sealed manifest unreported, the post-manifest
        # check stops (review fix M3)
        tool.write_text(original)
        resolve_alert(R)
        p = drive(R, touch='txn_begin:-framelease_v4/protocol/tool.py')
        self.assertEqual(p.returncode, 1, out_of(p))
        self.assertIn('vanished while the driver re-sealed', alert_text(R))
        self.assertIn('framelease_v4/protocol/tool.py', alert_text(R))
        self.assertEqual(sha(R / PROTO), before)
        self.assertNotIn('p2_jobs', entries(R))
        self.assertTrue(seal_ok(R) is False and (R / DRV / 'protocol_txn.json').exists())   # nothing sealed

    # -------------------------------------------------------------------------------- priority
    def test_tool_priority(self):
        R = make_sandbox(self)
        cfg = D.Cfg(D.parse_args(['--root', str(R)]))
        self.assertEqual(cfg.low_prio, ['nice', '-n', '10', 'ionice', '-c2', '-n7'])
        self.assertNotIn('OMP_NUM_THREADS', cfg.tool_env())
        fake = FakeRunner(R, Q2)
        try:
            self.assertEqual(cfg.low_prio, ['taskset', '-c', '12-15', 'nice', '-n', '19', 'ionice', '-c2', '-n7'])
            self.assertEqual(cfg.tool_env()['OMP_NUM_THREADS'], '1')
        finally:
            fake.stop()
        self.assertFalse(cfg.closed_loop_active())
        self.assertEqual(cfg.launch_cmd(cfg.p2_queue, 'TS'),
                         ['systemd-run', '--user', '--scope', '--unit=framelease-p2-runner-TS', '-p',
                          'OOMPolicy=continue', 'bash', 'framelease_v4/protocol/launch_queue.sh', Q2])
        self.assertEqual(cfg.launch_cmd(cfg.p4_queue, 'TS')[3], '--unit=framelease-p4-runner-TS')
        # the P3 and stress tools: every core at nice 10 (they run only while no closed-loop job runs)
        self.assertEqual(cfg.heavy_prio, ['taskset', '-c', '0-15', 'nice', '-n', '10', 'ionice', '-c2', '-n7'])
        self.assertEqual(D.Cfg(D.parse_args(['--root', str(R), '--normal-priority'])).heavy_prio, [])

    def test_refuses_to_run_niced_or_pinned(self):
        R = make_sandbox(self)
        p = drive(R, nice_ok=False)                   # the tests run pinned to some CPUs and under nice 19
        self.assertEqual(p.returncode, 2, out_of(p))
        log = (R / DRV / 'driver.log').read_text()
        self.assertIn('refusing to run', log)
        self.assertTrue('CPU affinity' in log or 'nice' in log, log)
        p = run(['taskset', '-c', '12', PY, '-I', '-B', '-c', 'import os, sys; sys.path.insert(0, sys.argv[1]); '
                 'from framelease_v4.protocol import phase_driver as D; print(D.launch_priority_problem())',
                 str(ROOT)], R)
        self.assertIn('pinned to CPUs [12]', p.stdout, out_of(p))

    # -------------------------------------------------------------------------------- start script
    def test_start_script_single_instance(self):
        R = make_sandbox(self)                         # no decision: the started driver waits at G1 and keeps its lock
        pdir = R / 'framelease_v4/protocol'
        for src, name in ((DRIVER, 'phase_driver.py'), (P1DRIVER, 'p1_driver.py'), (START, 'start_phase_driver.sh'),
                          (R / 'mock/registration_sandbox.py', 'registration.py'),
                          (R / 'mock/mockcommon.py', 'mockcommon.py')):
            shutil.copyfile(src, pdir / name)
        (R / '.conda-unidrive-linux/bin').mkdir(parents=True)
        os.symlink(PY, R / '.conda-unidrive-linux/bin/python')
        env = {k: v for k, v in os.environ.items() if k not in (CRASH_ENV, TOUCH_ENV)}
        env['PHASE_DRIVER_TEST_SYSTEMD_RUN'] = str(R / 'mock/systemd-run')
        # a shell pinned to some CPUs: refused (the runners would inherit the affinity); OMP_NUM_THREADS, which nproc
        # alone would report, does not count
        p0 = run(['taskset', '-c', '12,13', 'bash', str(pdir / 'start_phase_driver.sh'), '--no-consistency-check'], R,
                 60, {**env, 'OMP_NUM_THREADS': '4'})
        self.assertEqual(p0.returncode, 2, out_of(p0))
        self.assertIn('is pinned to 2 of', p0.stderr)
        self.assertIn('CPU affinity: 12,13)', p0.stderr)
        self.assertEqual(lines_of(R, 'systemd_calls.log'), [])
        start = ['bash', str(pdir / 'start_phase_driver.sh'), '--no-consistency-check', '--interval-s', '3600',
                 '--allow-nice-launch', '--normal-priority']
        p = run(start, R, 60, env)
        self.assertEqual(p.returncode, 0, out_of(p))
        self.assertIn('started phase_driver pid', p.stdout)
        self.assertRegex(p.stdout, r'in scope framelease-phase-driver-\d{8}T\d{6}')
        scope = lines_of(R, 'systemd_calls.log')
        self.assertEqual(len(scope), 1)
        self.assertRegex(scope[0], r'^--user --scope --unit=framelease-phase-driver-\d{8}T\d{6} -p OOMPolicy=continue '
                                   r'\S+/python -I -B framelease_v4/protocol/phase_driver.py --no-consistency-check')
        pid = int((R / DRV / 'driver.pid').read_text())
        try:
            self.assertIn('phase_driver.py', Path(f'/proc/{pid}/cmdline').read_bytes().decode(errors='replace'))
            p2 = run(start, R, 60, env)
            self.assertEqual(p2.returncode, 2, out_of(p2))
            self.assertIn('another phase_driver holds', p2.stderr)
            holder = LockHolder(R / DRV / 'start.lock')
            try:
                p2b = run(start, R, 60, env)
            finally:
                holder.stop()
            self.assertEqual(p2b.returncode, 2, out_of(p2b))
            self.assertIn('another start_phase_driver.sh is running', p2b.stderr)
            p3 = run([PY, '-I', '-B', str(pdir / 'phase_driver.py'), '--once', '--no-consistency-check',
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
            self.assertIn('signal 15', (R / DRV / 'driver.log').read_text())
            self.assertEqual(state(R)['driver']['status'], 'stopped')
            (R / ALERT).write_text('sandbox alert\n')
            p6 = run(start, R, 60, env)
            self.assertEqual(p6.returncode, 2, out_of(p6))
            self.assertIn('ALERT.txt exists', p6.stderr)
            (R / ALERT).unlink()
            (R / DRV / 'P2_STOPPED.json').write_text('{}\n')
            p7 = run(start, R, 60, env)
            self.assertEqual(p7.returncode, 0, out_of(p7))
            self.assertIn('nothing to start', p7.stdout)
            self.assertEqual(len(lines_of(R, 'systemd_calls.log')), 2)
        finally:
            if Path(f'/proc/{pid}').exists():
                os.kill(pid, signal.SIGKILL)


if __name__ == '__main__':
    unittest.main()
