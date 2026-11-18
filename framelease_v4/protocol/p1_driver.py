#!/usr/bin/env python3
"""P1 stage driver of the FrameLease v4 protocol, variant FULL (framelease_v4/PROTOCOL.md Secs. 4.2, 4.8, 4.9, 8.1,
13.2; outputs/framelease_v4/p1_jobs/README.md steps 4 and 5). CPU only: it never starts CARLA or a GPU job itself, starts
the runner only through framelease_v4/protocol/launch_queue.sh, and never starts Phase 2 or any later phase.

  cd /home/kang/Desktop/DAC
  .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/p1_driver.py --dry-run   # what it would do now
  bash framelease_v4/protocol/start_p1_driver.sh                                          # detached (nohup, pid file)
  .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/p1_driver.py --once      # one cycle, foreground

Every cycle (--interval-s, default 300 s) walks the two dependency chains of README step 4,
  lease_s1 -> lease_s2 -> heur_s1 -> heur_s2 -> age_s1 -> age_s2   and   event_s1 -> event_s2,
and for every stage whose job file b<NN>_<stage>.jsonl is in <queue>/jobs.d:
  1. Selection. If outputs/framelease_v4/tuning/selection/FULL/<stage>.json does not exist:
       .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/select_stage.py --variant FULL --stage <stage> \
           --queue outputs/framelease_v4/queue_p1 --write
     exit 3: the stage is not final, wait for the next cycle (but exit 3 because every route was dropped, with every
     job final, can never resolve: ALERT). Exit 2 (or any other non-zero exit), or a FLAG line: ALERT and stop. A
     written selection is never rewritten (re-running select_stage --write would change its 'written' time and so its
     sha256).
  2. Record (PROTOCOL Sec. 4.2: the selection's hash is entered in Sec. 13 before the next job file is generated). Under an
     exclusive flock on framelease_v4/.protocol.lock: PROTOCOL.md and MANIFEST.sha256 must be the sealed ones and every
     REGISTERED file of the sealed manifest must still match it (below); then registration.py --write-manifest --force;
     then a dated entry is appended to Sec. 13.2 under the subsection heading "**Stage selections (P1, FULL).**" (created
     once, just before the paragraph that starts "Each amendment gets the date and time"): stage, selection path and
     sha256, the job file it was made for, mean DS per candidate, the winners (survivors or the selected candidate), the
     times and the new manifest sha256; then registration.py --seal and registration.py --verify. registration.py --seal
     refuses a PROTOCOL.md that does not cite the manifest's sha256, so the manifest is written before the entry that
     cites it. Any failure: ALERT and stop.
     Registered files (p1_driver/registered_baseline.json): the registration manifest as amended (a later seal by
     another editor adds a new file only if PROTOCOL.md cites its sha256), plus the P1 job files, stage specs and checks.
     registration.py's manifest also sweeps in every other framelease_v4 file (code in development, the lock file); such
     a file may change between seals: the next entry names it ("changed since the previous seal (not registered
     files)") instead of stopping P1, and a change of it while the driver re-seals does not fail the --verify step.
  3. Next block. source linux/env.sh && CUDA_VISIBLE_DEVICES= .conda-unidrive-linux/bin/python -I -B
     framelease_v4/protocol/p1_jobs.py --variant FULL --block <next> --check --write; its .check.json must show no
     problem and every dry run passed, and its stage spec must cite the recorded selection sha256. The job file is then
     copied into <queue>/jobs.d/ (temporary name, then an atomic rename; never over a different file, never twice).
  4. Runner. If no runner holds <queue>/runner.lock (non-blocking flock test, as launch_queue.sh does):
     bash framelease_v4/protocol/launch_queue.sh outputs/framelease_v4/queue_p1. Not while <queue>/STOP exists (that is
     the disk watchdog's or the user's; reported, never removed); after a runner exit by the circuit breaker (exit 3) or a
     runner error (exit 1): ALERT; after a runner exit by a signal (exit 4: stopped on purpose, or a shutdown): reported
     in pipeline_state.json 'attention', never relaunched (a deliberate stop is not overridden; stop the runner with the
     queue's STOP file). Between blocks it relaunches only after a normal 'queue empty' exit (the runner may exit as
     empty just while a block is copied).
     Record step 2 also checks, after registration.py --write-manifest, that every registered file entered the new
     manifest with its sealed sha256 (a change between the pre-check and the manifest write: ALERT, nothing sealed).
After age_s2 and event_s2 are recorded (README step 5): select_stage.py --variant FULL --freeze --write, recorded the same
way; when every job in jobs.d is final: d1_summary.py --variant FULL --queue outputs/framelease_v4/queue_p1 --write,
recorded the same way; then outputs/framelease_v4/p1_driver/P1_DONE.json, and the driver stops. D1 is the user's decision.

Files (outputs/framelease_v4/): pipeline_state.json (stage -> status, selection sha256, block files, times; rewritten
atomically after every step) and in p1_driver/: driver.log, ALERT.txt, P1_DONE.json, driver.lock (one instance),
driver.pid, protocol_txn.json (an interrupted record transaction), manifest_sealed.sha256 (copy of the last sealed
manifest, for the pre-check after an interrupted record), registered_baseline.json (the registered files, step 2), STOP
(the driver exits at its next check).

Restart and idempotence: the state is reconstructed from the files at every cycle (selections present, Sec. 13.2 entries
present, block files generated and present in jobs.d); an entry is never written twice (the entry for a key is detected,
and so is the selection's sha256 anywhere in PROTOCOL.md), a block is never generated or copied twice, a selection or the
freeze is never rewritten. An interrupted record transaction is finished from protocol_txn.json.

ALERT: the driver writes p1_driver/ALERT.txt (step, problem, command, full output), exits 1 and refuses to start while the
file exists. Fix the cause, move the file aside (mv ALERT.txt ALERT.<UTC>.resolved.txt), start again. A FLAG (repeated
"Agent couldn't be set up" attempts of a candidate, PROTOCOL Sec. 4.2) is investigated; to continue under the registered
rule, write the selection's sha256 and the investigation note into p1_driver/FLAG_ACK_<stage>.txt (the entry cites it).

Priority: every tool runs under nice 10 / ionice best-effort 7 (hashing, job-file checks and summaries take little CPU
from the closed-loop job that runs meanwhile; its scheduler CPU time is charged to the simulated timeline, PROTOCOL Secs.
2.3, 11.2). launch_queue.sh runs at the driver's own priority, so the driver refuses to run niced: the runner it starts
must keep nice 0 like every P1 runner before it.

Other editors of PROTOCOL.md hold the same lock for the whole amendment (the edit of a registered file, the entry and
the re-seal), e.g. flock framelease_v4/.protocol.lock -c '<edit; entry; re-seal>'. While the lock is held elsewhere the
driver waits --lock-timeout-s (default 300 s) and retries at the next cycle (no ALERT).
Exit codes: 0 done / one cycle done / stopped / dry run; 1 ALERT; 2 refused (another instance, STOP file, niced, setup).
"""
from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import textwrap
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VARIANT = 'FULL'
CHAINS = (('lease_s1', 'lease_s2', 'heur_s1', 'heur_s2', 'age_s1', 'age_s2'), ('event_s1', 'event_s2'))
STAGES = tuple(s for chain in CHAINS for s in chain)
BLOCK_NO = {'ref': 1, 'lease_s1': 2, 'event_s1': 3, 'lease_s2': 4, 'event_s2': 5, 'heur_s1': 6, 'heur_s2': 7,
            'age_s1': 8, 'age_s2': 9}
NEXT = {'lease_s1': 'lease_s2', 'lease_s2': 'heur_s1', 'heur_s1': 'heur_s2', 'heur_s2': 'age_s1', 'age_s1': 'age_s2',
        'age_s2': None, 'event_s1': 'event_s2', 'event_s2': None}
PREV = {n: s for s, n in NEXT.items() if n}
FINAL_STAGES = ('lease_s2', 'event_s2', 'heur_s2', 'age_s2')     # p1_jobs.FINAL_STAGE['FULL']: these select one winner
LAST = ('age_s2', 'event_s2')                                     # README step 5 runs after these two are recorded
HEADING = '**Stage selections (P1, FULL).**'
ANCHOR = 'Each amendment gets the date and time'
SEC_START = '### 13.2 Amendments'
LABEL = {**{s: s for s in STAGES}, 'freeze': 'Tuning freeze', 'd1': 'D1 summary'}
KEY_OF_LABEL = {v: k for k, v in LABEL.items()}
ENTRY_RE = re.compile(r'^\* \*\*(?P<label>[^*]+)\*\*, (?P<when>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \(')
SHA_RE = re.compile(r'\b[0-9a-f]{64}\b')
LIST_START = re.compile(r'^(\d+[.)]|[-*+#>|=])(\s|$)')
SELECTION_SCHEMA = 'framelease_v4.p1_selection/1'
FREEZE_SCHEMA = 'framelease_v4.tuning_selection/1'
D1_SCHEMA = 'framelease_v4.d1_summary/1'
STATE_SCHEMA = 'framelease_v4.p1_driver_state/1'
DONE_SCHEMA = 'framelease_v4.p1_driver_done/1'
CRASH_ENV = 'P1_DRIVER_TEST_CRASH_AT'          # tests only: os._exit at a named point (fault injection)
TOUCH_ENV = 'P1_DRIVER_TEST_TOUCH_AT'          # tests only: '<point>:<file>' appends a line to <root>/<file> there
ABNORMAL_RUNNER_EXIT = {1: 'runner error', 3: 'circuit breaker'}
SIGNAL_RUNNER_EXIT = 4                         # gpu_queue.py: stopped by SIGTERM / SIGINT (never by the disk watchdog)
TIMEOUTS = {'select': 1800, 'jobs': 7200, 'registration': 3600, 'd1': 21600, 'launch': 300, 'freeze': 1800}


class Alert(Exception):
    """A failure the driver never advances past: ALERT.txt, then exit 1."""

    def __init__(self, step, problem, output='', cmd=None):
        super().__init__(f'{step}: {problem}')
        self.step, self.problem, self.output, self.cmd = step, problem, output, cmd


class Wait(Exception):
    """Nothing can be done now (the protocol lock is held by another process); retried at the next cycle."""


class Stop(Exception):
    """A stop was requested (SIGTERM / SIGINT, or the driver's STOP file)."""


# ---------------------------------------------------------------------------------------------------- small helpers

def now_iso():
    return time.strftime('%Y-%m-%dT%H:%M:%S%z')


def entry_time():
    """'YYYY-MM-DD HH:MM (Beijing time)', the form of the earlier Sec. 13.2 entries (the machine runs at +0800)."""
    zone = 'Beijing time' if time.strftime('%z') == '+0800' else f'UTC{time.strftime("%z")}'
    return f'{time.strftime("%Y-%m-%d %H:%M")} ({zone})'


def mtime_iso(path):
    try:
        return time.strftime('%Y-%m-%dT%H:%M:%S%z', time.localtime(Path(path).stat().st_mtime))
    except OSError:
        return None


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def _fsync_dir(d):
    try:
        fd = os.open(d, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def atomic_write(path, text, mode=None, tmp_dir=None):
    """Write `text` to a temporary file (in tmp_dir, default the target's directory; same file system) and rename it."""
    path = Path(path)
    tmp = Path(tmp_dir or path.parent) / f'.{path.name}.p1_driver.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    if mode is not None:
        os.chmod(tmp, mode)
    try:
        os.replace(tmp, path)
    except OSError as e:
        if e.errno != errno.EXDEV:
            raise
        with open(path, 'w', encoding='utf-8') as f:      # other file system: in place (the caller holds its lock)
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        tmp.unlink()
    _fsync_dir(path.parent)


def show(cmd):
    return ' '.join(shlex.quote(str(c)) for c in cmd)


def fmt(v, d=1):
    try:
        return f'{float(v):.{d}f}'
    except (TypeError, ValueError):
        return '-'


def job_file_name(stage):
    return f'b{BLOCK_NO[stage]:02d}_{stage}.jsonl'


def job_ids(path):
    ids = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.strip():
            ids.append(json.loads(line)['id'])
    return ids


def crash_point(ctx, name):
    """Test fault injection; inert unless --root is a sandbox (not the tree this script lives in)."""
    if ctx.cfg.root == ROOT:
        return
    point, _, rel = os.environ.get(TOUCH_ENV, '').partition(':')
    if point == name and rel:
        with open(ctx.cfg.root / rel, 'a', encoding='utf-8') as f:
            f.write(f'# changed by the test hook at {name}\n')
    if os.environ.get(CRASH_ENV) == name:
        ctx.log(f'TEST fault injection: exiting at {name}')
        os._exit(70)


# ---------------------------------------------------------------------------------------------------- configuration

class Cfg:
    def __init__(self, a):
        self.root = Path(a.root).resolve()
        self.queue = self.path(a.queue)
        self.queue_arg = self.rel(self.queue)
        self.jobs_d = self.queue / 'jobs.d'
        self.jobs_dir = self.path(a.jobs_dir)
        self.selection_dir = self.path(a.selection_dir)
        self.freeze_path = self.path(a.freeze_path)
        self.d1_dir = self.path(a.d1_dir)
        self.protocol = self.path(a.protocol)
        self.protocol_lock = self.path(a.protocol_lock)
        self.reg_dir = self.path(a.registration_dir)
        self.manifest = self.reg_dir / 'MANIFEST.sha256'
        self.seal = self.reg_dir / 'SEAL.sha256'
        self.driver_dir = self.path(a.driver_dir)
        self.state_path = self.path(a.state_file)
        self.python = str(a.python)
        self.select_script = str(a.select_script)
        self.jobs_script = str(a.jobs_script)
        self.d1_script = str(a.d1_script)
        self.registration_script = str(a.registration_script)
        self.launch_script = str(a.launch_script)
        self.env_script = str(a.env_script)
        self.interval_s = float(a.interval_s)
        self.lock_timeout_s = float(a.lock_timeout_s)
        self.dry_run = bool(a.dry_run)
        self.once = bool(a.once)
        self.json_out = bool(getattr(a, 'json', False))
        self.check_chain = not a.no_chain_check
        self.low_prio = [] if a.normal_priority else ['nice', '-n', '10', 'ionice', '-c2', '-n7']
        self.allow_nice_launch = bool(a.allow_nice_launch)
        d = self.driver_dir
        self.alert_path, self.done_path, self.log_path = d / 'ALERT.txt', d / 'P1_DONE.json', d / 'driver.log'
        self.txn_path, self.stop_path, self.lock_path = d / 'protocol_txn.json', d / 'STOP', d / 'driver.lock'
        self.pid_path, self.sealed_copy = d / 'driver.pid', d / 'manifest_sealed.sha256'
        self.baseline_path = d / 'registered_baseline.json'

    def path(self, p):
        p = Path(p)
        return p if p.is_absolute() else self.root / p

    def rel(self, p):
        p = Path(p)
        try:
            return str(p.relative_to(self.root))
        except ValueError:
            return str(p)

    def selection_path(self, stage):
        return self.selection_dir / VARIANT / f'{stage}.json'

    def block_paths(self, stage):
        base = self.jobs_dir / VARIANT / f'b{BLOCK_NO[stage]:02d}_{stage}'
        return base.with_suffix('.jsonl'), Path(str(base) + '.stage.json'), Path(str(base) + '.check.json')

    def d1_paths(self):
        return self.d1_dir / f'{VARIANT}_d1_summary.json', self.d1_dir / f'{VARIANT}_d1_summary.md'

    # commands (as in outputs/framelease_v4/p1_jobs/README.md, run from the project root)
    def select_cmd(self, stage, write=True):
        cmd = [self.python, '-I', '-B', self.select_script, '--variant', VARIANT, '--stage', stage, '--queue',
               self.queue_arg]
        return cmd + (['--write'] if write else [])

    def freeze_cmd(self):
        return [self.python, '-I', '-B', self.select_script, '--variant', VARIANT, '--freeze', '--write']

    def d1_cmd(self):
        return [self.python, '-I', '-B', self.d1_script, '--variant', VARIANT, '--queue', self.queue_arg, '--write']

    def jobs_cmd(self, block):
        script = 'source "$1" && CUDA_VISIBLE_DEVICES= exec "$2" -I -B "$3" --variant "$4" --block "$5" --check --write'
        return ['bash', '-c', script, 'p1_driver', self.env_script, self.python, self.jobs_script, VARIANT, block]

    def reg_cmd(self, *flags):
        return [self.python, '-I', '-B', self.registration_script, *flags]

    def launch_cmd(self):
        return ['bash', self.launch_script, self.queue_arg]


# ---------------------------------------------------------------------------------------------------- context / state

def _blank_stage(stage):
    return {'block_no': BLOCK_NO[stage], 'depends_on': PREV.get(stage), 'next': NEXT[stage],
            'final_stage': stage in FINAL_STAGES, 'status': 'unknown', 'note': None, 'job_file': None,
            'job_file_sha256': None, 'selection': None, 'selection_sha256': None, 'winners': None, 'flags': None,
            'entry': None, 'next_block': None, 'times': {}, 'last_check': None}


class Ctx:
    def __init__(self, cfg, prev_state=None, echo=False):
        self.cfg = cfg
        self.echo = echo
        self.plan = []
        self.attention = []
        self.lock_busy = False
        self.stop = False
        self.cycle = 0
        prev = prev_state if isinstance(prev_state, dict) and prev_state.get('schema') == STATE_SCHEMA else {}
        stages = {}
        for s in STAGES:
            st = _blank_stage(s)
            old = (prev.get('stages') or {}).get(s) or {}
            if old.get('last_check'):
                st['last_check'] = old['last_check']
            stages[s] = st
        self.state = {'schema': STATE_SCHEMA, 'variant': VARIANT, 'updated': None,
                      'driver': {'pid': os.getpid(), 'started': now_iso(), 'mode': 'dry-run' if cfg.dry_run else 'run',
                                 'interval_s': cfg.interval_s, 'cycle': 0, 'status': 'starting',
                                 'script': str(Path(__file__).resolve())},
                      'chains': [list(c) for c in CHAINS], 'queue': None, 'registration': None, 'stages': stages,
                      'final': {'freeze': None, 'd1': None, 'p1_done': None, 'status': None},
                      'attention': [], 'alert': None,
                      'files': {'log': cfg.rel(cfg.log_path), 'alert': cfg.rel(cfg.alert_path),
                                'done': cfg.rel(cfg.done_path), 'txn': cfg.rel(cfg.txn_path)}}

    def st(self, stage):
        return self.state['stages'][stage]

    def log(self, msg):
        line = f'{now_iso()} {msg}'
        if self.cfg.dry_run:
            print(f'  {msg}', flush=True)
            return
        with open(self.cfg.log_path, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
        if self.echo:
            print(line, flush=True)

    def add_plan(self, msg):
        self.plan.append(msg)
        if self.cfg.dry_run:
            print(f'  WOULD: {msg}', flush=True)

    def add_attention(self, msg):
        if msg not in self.attention:
            self.attention.append(msg)
            self.log(f'ATTENTION: {msg}')

    def save(self):
        self.state['updated'] = now_iso()
        self.state['driver']['cycle'] = self.cycle
        self.state['attention'] = list(self.attention)
        if self.cfg.dry_run:
            return
        self.cfg.state_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(self.cfg.state_path, json.dumps(self.state, indent=1, sort_keys=True, default=str) + '\n')


def check_stop(ctx):
    if ctx.stop or (not ctx.cfg.dry_run and ctx.cfg.stop_path.exists()):
        raise Stop()


def run_cmd(ctx, cmd, timeout, env_extra=None, low=True):
    """(exit code or None after a timeout, stdout, stderr). The child gets its own session; on timeout its whole process
    group is terminated (launch_queue.sh starts the runner in another session, so the runner is never touched).
    low: run the tool under nice 10 / ionice best-effort 7, so that the hashing, the job-file checks and the summaries
    take little CPU from the closed-loop job that runs at the same time (its scheduler CPU time is charged to the
    simulated timeline, PROTOCOL Secs. 2.3, 11.2). The runner is launched with low=False (it keeps normal priority)."""
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    if low and ctx.cfg.low_prio:
        cmd = list(ctx.cfg.low_prio) + list(cmd)
    t0 = time.monotonic()
    try:
        p = subprocess.Popen(cmd, cwd=ctx.cfg.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             stdin=subprocess.DEVNULL, encoding='utf-8', errors='replace', start_new_session=True,
                             env=env)
    except OSError as e:
        ctx.log(f'cannot start {show(cmd)}: {e}')
        return None, '', f'cannot start {cmd[0]}: {e}'
    try:
        out, err = p.communicate(timeout=timeout)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        for sig, wait_s in ((signal.SIGTERM, 15), (signal.SIGKILL, 15)):
            try:
                os.killpg(p.pid, sig)
            except OSError:
                pass
            try:
                p.wait(timeout=wait_s)
                break
            except subprocess.TimeoutExpired:
                continue
        out, err = p.communicate()
        rc = None
        err = (err or '') + f'\n[p1_driver] killed after the {timeout} s timeout'
    ctx.log(f'ran ({time.monotonic() - t0:.1f} s, exit {rc}): {show(cmd)}')
    return rc, out or '', err or ''


def both(out, err):
    return f'--- stdout ---\n{out}\n--- stderr ---\n{err}'


# ---------------------------------------------------------------------------------------------------- queue

def pid_cmdline(pid):
    try:
        return Path(f'/proc/{int(pid)}/cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
    except (OSError, ValueError):
        return ''


def queue_status(cfg):
    """Job files in jobs.d, final ids (status.jsonl 'end' records with final = true), the last runner start / exit, the
    runner's pid from runner.lock (read only) and the control files. Never writes anything in the queue directory."""
    files = sorted(cfg.jobs_d.glob('*.jsonl')) if cfg.jobs_d.is_dir() else []
    ids, per_file = {}, {}
    for f in files:
        try:
            fids = job_ids(f)
        except (OSError, ValueError, KeyError, TypeError) as e:
            raise Alert('queue', f'cannot read the job file {f}: {e}')
        per_file[f.name] = {'jobs': len(fids), 'sha256': sha256_file(f)}
        for i in fids:
            ids.setdefault(i, f.name)
    finals, last_start, last_exit = {}, None, None
    status = cfg.queue / 'status.jsonl'
    if status.is_file():
        for k, line in enumerate(status.read_text(encoding='utf-8', errors='replace').splitlines()):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            ev = r.get('event')
            if ev == 'end' and r.get('final') and 'id' in r:
                finals[r['id']] = r
            elif ev == 'runner_start':
                last_start = (k, r)
            elif ev == 'runner_exit':
                last_exit = (k, r)
    exit_rec = last_exit[1] if last_exit and (last_start is None or last_exit[0] > last_start[0]) else None
    for name in per_file:
        per_file[name]['final'] = sum(1 for i, f in ids.items() if f == name and i in finals)
    holder = None
    try:
        holder = (cfg.queue / 'runner.lock').read_text(errors='replace').strip() or None
    except OSError:
        pass
    pid = None
    m = re.match(r'pid (\d+)', holder or '')
    if m:
        pid = int(m.group(1))
    cmd = pid_cmdline(pid) if pid else ''
    alive = bool(pid) and 'gpu_queue.py' in cmd and str(cfg.queue) in cmd
    pending = [i for i in ids if i not in finals]
    return {'path': cfg.queue_arg, 'job_files': per_file, 'jobs': len(ids), 'final': len(ids) - len(pending),
            'pending': pending, 'runner_lock': holder, 'runner_pid': pid, 'runner_alive': alive,
            'last_runner_start': (last_start[1] if last_start else None), 'runner_exit': exit_rec,
            'stop_file': (cfg.queue / 'STOP').exists(), 'pause_file': (cfg.queue / 'PAUSE').exists(), 'ids': ids}


def queue_summary(q):
    def short(r):
        return None if r is None else {k: r.get(k) for k in ('utc', 'pid', 'reason', 'exit_code') if k in r}
    return {'path': q['path'], 'job_files': q['job_files'], 'jobs': q['jobs'], 'final': q['final'],
            'pending': len(q['pending']), 'runner_pid': q['runner_pid'], 'runner_alive': q['runner_alive'],
            'last_runner_start': short(q['last_runner_start']), 'last_runner_exit': short(q['runner_exit']),
            'stop_file': q['stop_file'], 'pause_file': q['pause_file']}


def runner_lock_held(cfg):
    """True if a process holds an exclusive flock on <queue>/runner.lock. Non-blocking shared-lock test on a read-only
    descriptor (the flock test of launch_queue.sh); never creates or writes the file."""
    try:
        fd = os.open(cfg.queue / 'runner.lock', os.O_RDONLY)
    except FileNotFoundError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except OSError as e:
            if e.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                return True
            raise
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------------------------------- PROTOCOL.md

def protocol_view(cfg, text=None):
    """Sec. 13.2 of PROTOCOL.md: its bounds, the anchor paragraph, the driver's heading and the driver's entries."""
    if text is None:
        text = cfg.protocol.read_text(encoding='utf-8')
    lines = text.split('\n')
    starts = [i for i, ln in enumerate(lines) if ln.strip() == SEC_START]
    if len(starts) != 1:
        raise Alert('PROTOCOL.md', f'expected exactly one "{SEC_START}" heading, found {len(starts)}')
    s = starts[0]
    e = next((i for i in range(s + 1, len(lines)) if lines[i].startswith('## ')), len(lines))
    anchors = [i for i in range(s, e) if lines[i].startswith(ANCHOR)]
    if len(anchors) != 1:
        raise Alert('PROTOCOL.md', f'expected exactly one paragraph starting "{ANCHOR}" in Sec. 13.2, found '
                                   f'{len(anchors)}')
    heads = [i for i in range(s, e) if lines[i].strip() == HEADING]
    if len(heads) > 1:
        raise Alert('PROTOCOL.md', f'the heading {HEADING} occurs {len(heads)} times in Sec. 13.2')
    entries = {}
    for i in range(s, e):
        m = ENTRY_RE.match(lines[i])
        if not m or m.group('label') not in KEY_OF_LABEL:
            continue
        j = i + 1
        while j < e and lines[j].startswith('  ') and lines[j].strip():
            j += 1
        body = '\n'.join(lines[i:j])
        key = KEY_OF_LABEL[m.group('label')]
        if key in entries:
            raise Alert('PROTOCOL.md', f'two Sec. 13.2 entries for {m.group("label")} (lines {entries[key]["line"]} '
                                       f'and {i + 1})')
        entries[key] = {'line': i + 1, 'when': m.group('when'), 'shas': SHA_RE.findall(body), 'text': body}
    return {'text': text, 'lines': lines, 'sec': (s, e), 'anchor': anchors[0],
            'heading': heads[0] if heads else None, 'entries': entries}


def wrap_entry(text):
    """A Markdown bullet wrapped at 120 columns; no continuation line may start like a list item or a heading."""
    for width in range(120, 96, -1):
        lines = textwrap.wrap(text, width=width, initial_indent='* ', subsequent_indent='  ',
                              break_long_words=False, break_on_hyphens=False)
        if all(not LIST_START.match(ln[2:]) for ln in lines[1:]):
            return lines
    return ['* ' + ' '.join(text.split())]


def insert_entry(cfg, text, entry_lines):
    """PROTOCOL.md text with the entry appended to the driver's subsection (created just before the anchor paragraph)."""
    view = protocol_view(cfg, text)
    lines = list(view['lines'])
    if view['heading'] is None:
        a = view['anchor']
        block = [HEADING] + list(entry_lines) + ['']
        if a > 0 and lines[a - 1].strip():
            block = [''] + block
        lines[a:a] = block
    else:
        i = view['heading'] + 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(ANCHOR):
            i += 1
        lines[i:i] = list(entry_lines) + ([''] if lines[i].startswith(ANCHOR) else [])
    return '\n'.join(lines)


def registration_view(cfg):
    P = sha256_file(cfg.protocol)
    M = sha256_file(cfg.manifest) if cfg.manifest.is_file() else None
    seal = {}
    if cfg.seal.is_file():
        for line in cfg.seal.read_text(encoding='utf-8', errors='replace').splitlines():
            if '  ' in line:
                sha, rel = line.split('  ', 1)
                seal[rel.strip()] = sha.strip()
    sp, sm = seal.get(cfg.rel(cfg.protocol)), seal.get(cfg.rel(cfg.manifest))
    n = None
    if cfg.manifest.is_file():
        n = sum(1 for ln in cfg.manifest.read_text(encoding='utf-8', errors='replace').splitlines() if ln.strip())
    return {'protocol': cfg.rel(cfg.protocol), 'protocol_sha256': P, 'manifest': cfg.rel(cfg.manifest),
            'manifest_sha256': M, 'manifest_files': n, 'seal_protocol': sp, 'seal_manifest': sm,
            'seal_ok': bool(sp) and P == sp and M == sm}


# The tree against a manifest, with registration.verify()'s semantics (paths relative to the root, absolute outside it),
# run as a separate low-priority process (hashing the 6 GB checkpoint must not take CPU from the closed-loop job).
HASH_CHECK_CODE = r'''
import hashlib, json, os, sys
root, man = sys.argv[1], sys.argv[2]
n, differ = 0, []
with open(man, encoding='utf-8') as fh:
    for line in fh:
        line = line.rstrip('\n')
        if '  ' not in line:
            continue
        sha, rel = line.split('  ', 1)
        n += 1
        p = rel if os.path.isabs(rel) else os.path.join(root, rel)
        try:
            h = hashlib.sha256()
            with open(p, 'rb') as f:
                for b in iter(lambda: f.read(1 << 20), b''):
                    h.update(b)
            got = h.hexdigest()
        except OSError as e:
            got = 'unreadable (%s)' % (e.strerror,)
        if got != sha:
            differ.append([rel, sha, got])
print(json.dumps({'entries': n, 'differ': differ}))
'''
MANIFEST_CLAUSE_RE = re.compile(r'Manifest and seal: `MANIFEST\.sha256`, \d+ files.*?sha256 `([0-9a-f]{64})`, sealed with '
                                r'this entry')


def parse_manifest_text(text):
    out = {}
    for ln in text.splitlines():
        if '  ' in ln:
            sha, rel = ln.split('  ', 1)
            out[rel] = sha
    return out


def tree_differences(cfg, ctx, manifest_path):
    """[(path, sha256 in the manifest, sha256 of the tree or 'unreadable (...)')] for every entry of the manifest that
    differs from the tree ([] if all match)."""
    cmd = [cfg.python, '-I', '-B', '-c', HASH_CHECK_CODE, str(cfg.root), str(manifest_path)]
    rc, out, err = run_cmd(ctx, cmd, TIMEOUTS['registration'])
    try:
        res = json.loads(out.strip().splitlines()[-1])
        n_listed = len(parse_manifest_text(Path(manifest_path).read_text(encoding='utf-8')))
        ok = rc == 0 and res['entries'] == n_listed
    except (ValueError, IndexError, KeyError, TypeError, OSError):
        ok = False
    if not ok:
        raise Alert('registration', f'the hash check of {cfg.rel(manifest_path)} failed (exit {rc})',
                    both(out[-5000:], err[-5000:]), ['python', '-c', '<hash check>', str(cfg.root), str(manifest_path)])
    return [tuple(d) for d in res['differ']]


def driver_manifest_shas(view):
    """sha256 of the manifests sealed with the driver's own Sec. 13.2 entries (their manifest clause)."""
    shas = set()
    for ent in view['entries'].values():
        m = MANIFEST_CLAUSE_RE.search(' '.join(ent['text'].split()))
        if m:
            shas.add(m.group(1))
    return shas


def refresh_baseline(cfg, ctx, view, reg, sealed_text):
    """{path: sha256} of the REGISTERED files: the registration manifest (PROTOCOL Sec. 13.1) as amended, kept in
    p1_driver/registered_baseline.json. sealed_text is the sealed manifest (the caller checked its sha256).
      * The first baseline is the sealed manifest the driver finds when the seal is not its own (at its first cycle:
        the registration manifest as amended so far).
      * A later seal by another editor (an amendment) keeps every baseline file, with its newly sealed sha256, and adds
        a file that is new in its manifest only if PROTOCOL.md cites that file's sha256 (an amendment that registers
        it). A file that the manifest's glob merely swept in (every framelease_v4 file, e.g. code still in
        development, or the lock file) is not registered by that.
      * The driver's own seals never change the baseline.
    Never written in a dry run."""
    base = read_json(cfg.baseline_path)
    base = base if isinstance(base, dict) and isinstance(base.get('files'), dict) else None
    sealed = parse_manifest_text(sealed_text)
    if reg['seal_manifest'] in driver_manifest_shas(view):
        if base is None:
            ctx.add_attention(f'{cfg.rel(cfg.baseline_path)} is missing while the seal is the driver\'s own: every file '
                              'of the sealed manifest is treated as registered')
            return sealed
        return base['files']
    if base is not None and base.get('manifest_sha256') == reg['seal_manifest']:
        return base['files']
    if base is None:
        files, how = dict(sealed), 'first baseline: the sealed manifest'
    else:
        old = base['files']
        files = {p: s for p, s in sealed.items() if p in old or s in view['text']}
        how = (f'another seal (manifest {reg["seal_manifest"]}): {len(files)} registered files, '
               f'{len([p for p in files if p not in old])} newly registered (sha256 cited in PROTOCOL.md), '
               f'{len([p for p in sealed if p not in files])} manifest files not registered')
    if cfg.dry_run:
        return files
    atomic_write(cfg.baseline_path, json.dumps({'schema': 'framelease_v4.p1_driver_baseline/1', 'updated': now_iso(),
                                               'manifest_sha256': reg['seal_manifest'],
                                               'protocol_sha256': reg['seal_protocol'], 'how': how,
                                               'previous_manifest_sha256': (base or {}).get('manifest_sha256'),
                                               'files': files}, indent=1, sort_keys=True) + '\n')
    ctx.log(f'registered baseline {cfg.rel(cfg.baseline_path)}: {how} ({len(files)} files)')
    return files


def is_strict(cfg, path, baseline):
    """A file that may not change without an amendment: a registered file, or a P1 job file / stage spec / check (the
    driver generates these and never rewrites them). The protocol lock file never counts."""
    if path == cfg.rel(cfg.protocol_lock):
        return False
    return path in baseline or path.startswith(cfg.rel(cfg.jobs_dir).rstrip('/') + '/')


def precheck_tree(cfg, ctx, baseline):
    """The tree against the sealed manifest (copy) before the driver re-seals. A registered file that differs: ALERT
    (the driver never seals a changed registered file). Other differing files (unregistered files the manifest's glob
    swept in at an earlier seal, e.g. code in development) are returned; the entry names them."""
    diffs = tree_differences(cfg, ctx, cfg.sealed_copy)
    strict = [d for d in diffs if is_strict(cfg, d[0], baseline)]
    if strict:
        raise Alert('registration', f'{len(strict)} registered file(s) differ from the sealed manifest: '
                                    f'{[d[0] for d in strict][:10]}; the driver never seals a changed registered file: '
                                    'restore them, or amend the protocol (entry + re-seal under the protocol lock)',
                    json.dumps(strict, indent=1))
    lock = cfg.rel(cfg.protocol_lock)
    loose = [d for d in diffs if d[0] != lock]
    if loose:
        ctx.log(f'unregistered files changed since the last seal (named in the entry): {[d[0] for d in loose]}')
    return loose


def read_txn(cfg):
    t = read_json(cfg.txn_path)
    return t if isinstance(t, dict) and t.get('key') else None


def write_txn(cfg, txn):
    atomic_write(cfg.txn_path, json.dumps(txn, indent=1, sort_keys=True) + '\n')


def clear_txn(cfg):
    try:
        cfg.txn_path.unlink()
    except FileNotFoundError:
        pass


def run_write_manifest(cfg, ctx):
    """registration.py --write-manifest --force. A file that vanished while registration.py listed and hashed the tree
    (FileNotFoundError, e.g. an editor's temporary file under framelease_v4/) is retried twice after 10 s."""
    cmd = cfg.reg_cmd('--write-manifest', '--force')
    for attempt in range(3):
        rc, out, err = run_cmd(ctx, cmd, TIMEOUTS['registration'], {'CUDA_VISIBLE_DEVICES': ''})
        if rc == 0 or 'FileNotFoundError' not in err or attempt == 2:
            break
        ctx.log(f'registration.py --write-manifest: a file vanished while it hashed the tree; retry in 10 s: '
                f'{err.strip().splitlines()[-1][:300]}')
        time.sleep(10)
    m = re.search(r'^wrote (.+?): (\d+) files, sha256 ([0-9a-f]{64})$', out, re.M)
    if rc != 0 or not m:
        raise Alert('registration --write-manifest', f'registration.py --write-manifest --force exited {rc}',
                    both(out, err), cmd)
    if sha256_file(cfg.manifest) != m.group(3):
        raise Alert('registration --write-manifest', 'the written MANIFEST.sha256 does not have the printed sha256',
                    both(out, err), cmd)
    return m.group(3), int(m.group(2))


def run_seal(cfg, ctx, expect_protocol, expect_manifest):
    cmd = cfg.reg_cmd('--seal')
    rc, out, err = run_cmd(ctx, cmd, TIMEOUTS['registration'], {'CUDA_VISIBLE_DEVICES': ''})
    m = re.search(r'^sealed: PROTOCOL\.md ([0-9a-f]{64}), manifest ([0-9a-f]{64})$', out, re.M)
    if rc != 0 or not m or m.group(1) != expect_protocol or m.group(2) != expect_manifest:
        raise Alert('registration --seal', f'registration.py --seal exited {rc} or sealed other files than the driver '
                                           f'wrote (expected PROTOCOL.md {expect_protocol}, manifest {expect_manifest})',
                    both(out, err), cmd)
    if not registration_view(cfg)['seal_ok']:
        raise Alert('registration --seal', 'SEAL.sha256 does not match PROTOCOL.md and MANIFEST.sha256 after --seal',
                    both(out, err), cmd)


def run_verify(cfg, ctx, baseline):
    """registration.py --verify after the seal. The seal lines must both be OK. A manifest difference is an ALERT unless
    every differing file is unregistered (changed by another process, e.g. code in development, while the driver
    re-sealed): that is logged and named at the next seal. Returns the tolerated differences."""
    cmd = cfg.reg_cmd('--verify')
    rc, out, err = run_cmd(ctx, cmd, TIMEOUTS['registration'], {'CUDA_VISIBLE_DEVICES': ''})
    seals = re.findall(r'^seal (.+): (OK|CHANGED)$', out, re.M)
    seal_ok = len(seals) == 2 and all(s == 'OK' for _, s in seals)
    if rc == 0 and seal_ok and re.search(r'^manifest: OK$', out, re.M):
        return []
    if seal_ok and rc == 1 and re.search(r'^manifest: \d+ files differ', out, re.M):
        diffs = tree_differences(cfg, ctx, cfg.manifest)
        strict = [d for d in diffs if is_strict(cfg, d[0], baseline)]
        if not strict:
            names = [d[0] for d in diffs]
            ctx.log(f'registration.py --verify: only unregistered files differ (changed while the driver re-sealed; '
                    f'named at the next seal): {names}')
            if names:
                ctx.add_attention(f'unregistered files changed while the driver re-sealed (named at the next seal): '
                                  f'{names[:10]}')
            return diffs
    raise Alert('registration --verify', f'registration.py --verify exited {rc} or reported a difference of a '
                                         'registered file or of the seal', both(out, err), cmd)


class ProtocolLock:
    """Exclusive flock on framelease_v4/.protocol.lock, waiting up to --lock-timeout-s. The file stays empty."""

    def __init__(self, cfg, ctx):
        self.cfg, self.ctx, self.fd, self.acquired = cfg, ctx, None, False

    def __enter__(self):
        if self.ctx.lock_busy:
            return self
        self.fd = os.open(self.cfg.protocol_lock, os.O_RDWR | os.O_CREAT, 0o664)
        deadline = time.monotonic() + self.cfg.lock_timeout_s
        while True:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.acquired = True
                return self
            except OSError as e:
                if e.errno not in (errno.EWOULDBLOCK, errno.EAGAIN):
                    raise
            if time.monotonic() >= deadline or self.ctx.stop:
                self.ctx.lock_busy = True
                return self
            time.sleep(0.5)

    def __exit__(self, *exc):
        if self.fd is not None:
            if self.acquired:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
        return False


def lock_wait_message(cfg):
    return (f'the protocol lock {cfg.rel(cfg.protocol_lock)} is held by another process (waited '
            f'{cfg.lock_timeout_s:.0f} s); retried at the next cycle')


def sealed_baseline(cfg, ctx):
    """refresh_baseline() from the current files when the seal matches PROTOCOL.md and MANIFEST.sha256 (a consistent
    snapshot); else the saved baseline (None if there is none)."""
    reg = registration_view(cfg)
    if reg['seal_ok']:
        text = cfg.manifest.read_text(encoding='utf-8')
        if sha256_text(text) == reg['seal_manifest']:
            return refresh_baseline(cfg, ctx, protocol_view(cfg), reg, text)
    base = read_json(cfg.baseline_path)
    return base['files'] if isinstance(base, dict) and isinstance(base.get('files'), dict) else None


def baseline_summary(cfg, files):
    base = read_json(cfg.baseline_path)
    base = base if isinstance(base, dict) else {}
    return {'file': cfg.rel(cfg.baseline_path), 'saved': cfg.baseline_path.is_file(),
            'registered_files': None if files is None else len(files),
            'from_manifest_sha256': base.get('manifest_sha256'), 'updated': base.get('updated')}


def finish_open_txn(cfg, ctx):
    """Finish a record transaction that an earlier run left open (call with the protocol lock held)."""
    txn = read_txn(cfg)
    if not txn:
        return
    reg = registration_view(cfg)
    step = txn.get('step')
    what = f'interrupted record of {LABEL.get(txn["key"], txn["key"])} (step {step})'
    if step in ('protocol', 'sealed'):
        if reg['protocol_sha256'] == txn.get('protocol_after'):
            if not reg['seal_ok']:
                if reg['manifest_sha256'] != txn.get('manifest'):
                    raise Alert('registration', f'{what}: PROTOCOL.md holds the entry but MANIFEST.sha256 is not the '
                                                'manifest the entry cites; re-seal by hand after checking')
                run_seal(cfg, ctx, txn['protocol_after'], txn['manifest'])
            run_verify(cfg, ctx, sealed_baseline(cfg, ctx) or {})
            clear_txn(cfg)
            ctx.log(f'finished the {what}: sealed and verified')
            return
        if reg['protocol_sha256'] == txn.get('protocol_before'):
            write_txn(cfg, {**txn, 'step': 'manifest'})
            ctx.log(f'{what}: PROTOCOL.md was not replaced; the entry is written again')
            return
        if reg['seal_ok']:
            clear_txn(cfg)
            ctx.log(f'{what}: superseded by a sealed PROTOCOL.md; the transaction is closed')
            return
        raise Alert('registration', f'{what}: PROTOCOL.md is neither the version before nor the version after the '
                                    "driver's edit, and SEAL.sha256 does not match it")
    if reg['seal_ok']:
        clear_txn(cfg)
        ctx.log(f'{what}: nothing was written to PROTOCOL.md and the seal matches; the transaction is closed')


def ensure_open_txn_finished(cfg, ctx):
    if not read_txn(cfg):
        return
    if cfg.dry_run:
        txn = read_txn(cfg)
        ctx.add_plan(f'finish the interrupted record of {LABEL.get(txn["key"], txn["key"])} (step {txn.get("step")}) '
                     'under the protocol lock (seal, verify)')
        return
    with ProtocolLock(cfg, ctx) as lock:
        if not lock.acquired:
            raise Wait(lock_wait_message(cfg))
        finish_open_txn(cfg, ctx)


def manifest_paths_of(text):
    return {ln.split('  ', 1)[1] for ln in text.splitlines() if '  ' in ln}


def manifest_added(cfg):
    """Paths in the newly written manifest that the sealed manifest (copy) does not list."""
    try:
        old = manifest_paths_of(cfg.sealed_copy.read_text(encoding='utf-8'))
        new = manifest_paths_of(cfg.manifest.read_text(encoding='utf-8'))
    except OSError:
        return []
    return sorted(new - old)


def manifest_clause(m_new, n_files, added, changed=()):
    """added: files new in the manifest; changed: unregistered files whose content changed since the previous seal."""
    def names(files, what):
        if not files:
            return ''
        if len(files) <= 12:
            return f'; {what}: ' + ', '.join(f'`{a}`' for a in files)
        return f'; {len(files)} files {what} (listed in `outputs/framelease_v4/p1_driver/driver.log`)'
    extra = names(added, 'new in it') + names(changed, 'changed since the previous seal (not registered files)')
    return f' Manifest and seal: `MANIFEST.sha256`, {n_files} files{extra}, sha256 `{m_new}`, sealed with this entry.'


def cited_consistent(reg, txn):
    """An entry already in PROTOCOL.md counts as recorded when the seal matches, or when the only difference is the
    manifest rewritten by the driver's own interrupted record of another entry (PROTOCOL.md itself still sealed)."""
    if reg['seal_ok']:
        return True
    return (bool(txn) and txn.get('step') in ('begin', 'manifest')
            and reg['protocol_sha256'] == reg['seal_protocol'])


def ensure_recorded(cfg, ctx, key, sha, build):
    """Entry `key` citing `sha` in PROTOCOL Sec. 13.2, sealed and verified. build() -> the entry text; the driver
    appends the manifest clause (file count, the files new in the manifest, its sha256). Returns 'recorded' (earlier),
    'written' (now) or None (dry run)."""
    view = protocol_view(cfg)
    ent = view['entries'].get(key)
    if ent is not None and sha not in ent['shas']:
        raise Alert('PROTOCOL.md', f'the Sec. 13.2 entry {LABEL[key]} (line {ent["line"]}) does not cite sha256 {sha} '
                                   'of the current file: the file changed after it was recorded')
    reg = registration_view(cfg)
    cited = ent is not None or sha in view['text']
    if cited and cited_consistent(reg, read_txn(cfg)):
        return 'recorded'
    if cfg.dry_run:
        if cited:
            ctx.add_plan(f'{LABEL[key]}: PROTOCOL.md cites sha256 {sha} but the seal does not match: finish the '
                         'interrupted driver record (seal, verify) if one explains it, else ALERT')
            return None
        ctx.add_plan(f'record {LABEL[key]} (sha256 {sha}) under the lock {cfg.rel(cfg.protocol_lock)}: check the seal '
                     'and the registered files against the sealed manifest; registration.py --write-manifest --force; '
                     'append the '
                     f'entry under {HEADING} in Sec. 13.2' + ('' if view['heading'] is not None else
                                                                f' (heading created before "{ANCHOR}")')
                     + '; registration.py --seal; registration.py --verify')
        for ln in wrap_entry(build() + manifest_clause('<new manifest sha256>', '<n>', [])):
            print(f'      | {ln}')
        return None
    check_stop(ctx)
    with ProtocolLock(cfg, ctx) as lock:
        if not lock.acquired:
            raise Wait(lock_wait_message(cfg))
        finish_open_txn(cfg, ctx)
        text = cfg.protocol.read_text(encoding='utf-8')
        view = protocol_view(cfg, text)
        ent = view['entries'].get(key)
        if ent is not None and sha not in ent['shas']:
            raise Alert('PROTOCOL.md', f'the Sec. 13.2 entry {LABEL[key]} (line {ent["line"]}) does not cite sha256 '
                                       f'{sha} of the current file')
        reg = registration_view(cfg)
        if ent is not None or sha in text:
            if cited_consistent(reg, read_txn(cfg)):
                return 'recorded'
            raise Alert('registration', f'PROTOCOL.md already cites {LABEL[key]} (sha256 {sha}) but SEAL.sha256 does '
                                        'not match PROTOCOL.md / MANIFEST.sha256 (an unsealed edit); seal or explain it '
                                        'before the driver continues')
        if reg['protocol_sha256'] != reg['seal_protocol']:
            raise Alert('registration', f'PROTOCOL.md (sha256 {reg["protocol_sha256"]}) is not the sealed version '
                                        f'({reg["seal_protocol"]}): an unsealed edit by another process; seal it '
                                        '(registration.py --write-manifest --force with an entry citing the manifest, '
                                        '--seal) or revert it before the driver continues')
        txn = read_txn(cfg)
        own = bool(txn) and txn.get('step') in ('begin', 'manifest')
        if reg['manifest_sha256'] != reg['seal_manifest'] and not own:
            raise Alert('registration', f'MANIFEST.sha256 (sha256 {reg["manifest_sha256"]}) is not the sealed manifest '
                                        f'({reg["seal_manifest"]}) and no interrupted driver record explains it')
        if reg['manifest_sha256'] == reg['seal_manifest']:
            atomic_write(cfg.sealed_copy, cfg.manifest.read_text(encoding='utf-8'))
        elif not (cfg.sealed_copy.is_file() and sha256_file(cfg.sealed_copy) == reg['seal_manifest']):
            raise Alert('registration', 'MANIFEST.sha256 was rewritten by an interrupted driver record and no copy of '
                                        'the sealed manifest exists to check the tree against')
        sealed_text = cfg.sealed_copy.read_text(encoding='utf-8')
        if sha256_text(sealed_text) != reg['seal_manifest']:
            raise Alert('registration', 'the copy of the sealed manifest does not have the sealed sha256')
        baseline = refresh_baseline(cfg, ctx, view, reg, sealed_text)
        changed = [d[0] for d in precheck_tree(cfg, ctx, baseline)]
        P = reg['protocol_sha256']
        base = {'key': key, 'sha256': sha, 'protocol_before': P, 'started': now_iso()}
        write_txn(cfg, {**base, 'step': 'begin'})
        crash_point(ctx, 'txn_begin')
        m_new, n_files = run_write_manifest(cfg, ctx)
        write_txn(cfg, {**base, 'step': 'manifest', 'manifest': m_new})
        crash_point(ctx, 'manifest_written')
        # A registered file must enter the new manifest with its sealed sha256: a change between the pre-check above and
        # --write-manifest would otherwise be sealed silently (the next pre-check compares against the new seal).
        old_map = parse_manifest_text(sealed_text)
        new_map = parse_manifest_text(cfg.manifest.read_text(encoding='utf-8'))
        laundered = [(p, old_map.get(p, baseline.get(p)), s) for p, s in new_map.items()
                     if is_strict(cfg, p, baseline) and old_map.get(p, baseline.get(p)) not in (None, s)]
        if laundered:
            raise Alert('registration', f'{len(laundered)} registered file(s) changed while the driver re-sealed: '
                                        f'{[d[0] for d in laundered][:10]}; restore them (the unsealed manifest is '
                                        'redone at the restart) or amend the protocol', json.dumps(laundered, indent=1))
        added = manifest_added(cfg)
        if added:
            ctx.log(f'{LABEL[key]}: {len(added)} files are new in the manifest: {added}')
        changed = [c for c in changed if c not in added]
        new_text = insert_entry(cfg, text, wrap_entry(build() + manifest_clause(m_new, n_files, added, changed)))
        chk = protocol_view(cfg, new_text)['entries'].get(key)
        if chk is None or sha not in chk['shas'] or m_new not in new_text:
            raise Alert('PROTOCOL.md', f'internal: the composed entry {LABEL[key]} does not parse back with its sha256')
        after = sha256_text(new_text)
        if sha256_file(cfg.protocol) != P:
            raise Alert('PROTOCOL.md', 'PROTOCOL.md changed while the driver held the protocol lock (an editor that '
                                       'does not take the lock); the driver did not write PROTOCOL.md, but '
                                       'MANIFEST.sha256 was rewritten and is not sealed (p1_driver/protocol_txn.json, '
                                       "step 'manifest'): seal the other edit, then restart the driver")
        write_txn(cfg, {**base, 'step': 'protocol', 'manifest': m_new, 'protocol_after': after})
        mode = cfg.protocol.stat().st_mode & 0o7777
        atomic_write(cfg.protocol, new_text, mode=mode, tmp_dir=cfg.driver_dir)
        crash_point(ctx, 'protocol_written')
        run_seal(cfg, ctx, after, m_new)
        write_txn(cfg, {**base, 'step': 'sealed', 'manifest': m_new, 'protocol_after': after})
        crash_point(ctx, 'sealed')
        run_verify(cfg, ctx, baseline)
        clear_txn(cfg)
    ctx.log(f'recorded {LABEL[key]} in PROTOCOL.md Sec. 13.2 (sha256 {sha}); manifest {m_new} ({n_files} files), '
            f'PROTOCOL.md {after}; sealed and verified')
    return 'written'


# ---------------------------------------------------------------------------------------------------- stage steps

def load_selection(cfg, stage, path):
    sel = read_json(path)
    where = cfg.rel(path)
    if not isinstance(sel, dict):
        raise Alert(f'{stage} selection', f'{where} exists but is not readable JSON (an interrupted write?); the driver '
                                          'never overwrites a selection')
    problems = []
    if sel.get('schema') != SELECTION_SCHEMA:
        problems.append(f'schema {sel.get("schema")!r}')
    if sel.get('variant') != VARIANT or sel.get('stage') != stage:
        problems.append(f'variant / stage {sel.get("variant")!r} / {sel.get("stage")!r}')
    if sel.get('complete') is not True or sel.get('provisional'):
        problems.append('not complete')
    if stage in FINAL_STAGES and not sel.get('selected'):
        problems.append('no selected candidate')
    if stage not in FINAL_STAGES and not sel.get('survivors'):
        problems.append('no survivors')
    jf = cfg.jobs_d / job_file_name(stage)
    if jf.is_file() and sel.get('job_file_sha256') != sha256_file(jf):
        problems.append(f'job_file_sha256 differs from the queued {cfg.rel(jf)}')
    spec = cfg.block_paths(stage)[1]
    if spec.is_file() and sel.get('stage_spec_sha256') != sha256_file(spec):
        problems.append(f'stage_spec_sha256 differs from {cfg.rel(spec)}')
    if problems:
        raise Alert(f'{stage} selection', f'{where}: ' + '; '.join(problems))
    return sel


def winners(stage, sel):
    if stage in FINAL_STAGES:
        row = next((r for r in sel.get('table') or [] if r.get('candidate') == sel.get('selected')), {})
        return {'selected': sel.get('selected'), 'mean_ds_T22': row.get('mean_ds_T22'), 'mean_ds': row.get('mean_ds')}
    return {'survivors': list(sel.get('survivors') or [])}


def ensure_selection(cfg, ctx, stage):
    """(selection, sha256, 'ok') or (None, None, 'waiting' | 'dry')."""
    st = ctx.st(stage)
    path = cfg.selection_path(stage)
    if path.exists():
        sel = load_selection(cfg, stage, path)
        sha = sha256_file(path)
        st.update(selection=cfg.rel(path), selection_sha256=sha, winners=winners(stage, sel),
                  flags=sel.get('flags') or None)
        st['times']['selection_written'] = sel.get('written')
        return sel, sha, 'ok'
    check_stop(ctx)
    cmd = cfg.select_cmd(stage, write=not cfg.dry_run)
    rc, out, err = run_cmd(ctx, cmd, TIMEOUTS['select'], {'CUDA_VISIBLE_DEVICES': ''})
    msg = (err.strip() or out.strip()).splitlines()
    st['last_check'] = {'time': now_iso(), 'exit': rc, 'message': (msg[0][:400] if msg else '')}
    flag_lines = [ln.strip() for ln in out.splitlines() if ln.strip().startswith('FLAG ')]
    if rc == 3 and 'every route was dropped' in err:
        raise Alert(f'select_stage {stage}', 'every route of the stage was dropped (all jobs final): the stage can never '
                                             'be selected; investigate before the chain continues', both(out, err), cmd)
    if rc == 3:
        st.update(status='waiting_final', note=st['last_check']['message'])
        ctx.log(f'{stage}: not final yet (select_stage exit 3): {st["last_check"]["message"][:300]}')
        return None, None, 'waiting'
    if rc != 0:
        raise Alert(f'select_stage {stage}', f'select_stage.py exited {rc}', both(out, err), cmd)
    if cfg.dry_run:
        for ln in out.splitlines():
            print(f'      | {ln}')
        if flag_lines:
            ctx.add_plan(f'{stage}: select_stage --write, then ALERT and stop on its FLAG line(s): {flag_lines}')
        else:
            ctx.add_plan(f'{stage}: select_stage --write (the stage is final), then record it in Sec. 13.2, re-seal'
                         + (f', generate {NEXT[stage]}, copy it into jobs.d and launch the runner if none runs'
                            if NEXT[stage] else ''))
        st.update(status='final_not_selected', note='select_stage (no --write) exit 0')
        return None, None, 'dry'
    if flag_lines:
        raise Alert(f'select_stage {stage}', f'FLAG: {len(flag_lines)} flagged candidate(s); the selection was written '
                    f'({cfg.rel(path)}) but the driver does not advance: investigate (PROTOCOL Sec. 4.2, Flags); to '
                    f'continue under the registered rule write the selection sha256 and the note into '
                    f'{cfg.rel(cfg.driver_dir / ("FLAG_ACK_" + stage + ".txt"))}', both(out, err), cmd)
    m = re.search(r'^wrote (?P<p>.+?)  sha256 (?P<s>[0-9a-f]{64})$', out, re.M)
    if not m or not path.is_file() or Path(m.group('p')).resolve() != path.resolve():
        raise Alert(f'select_stage {stage}', f'exit 0 without the selection file at {cfg.rel(path)}', both(out, err),
                    cmd)
    sha = sha256_file(path)
    if sha != m.group('s'):
        raise Alert(f'select_stage {stage}', 'the selection file does not have the printed sha256', both(out, err), cmd)
    ctx.log(f'{stage}: selection written {cfg.rel(path)} sha256 {sha}\n' + out.rstrip())
    crash_point(ctx, 'selection_written')
    sel = load_selection(cfg, stage, path)
    if sel.get('flags'):
        raise Alert(f'select_stage {stage}', 'the selection lists flags (no FLAG line was printed)', both(out, err), cmd)
    st.update(selection=cfg.rel(path), selection_sha256=sha, winners=winners(stage, sel), flags=None,
              status='selected', note=None)
    st['times']['selection_written'] = sel.get('written')
    ctx.save()
    return sel, sha, 'ok'


def check_flags(cfg, ctx, stage, sel, sha):
    """None without flags; the acknowledgement file if every flag is acknowledged; else ALERT."""
    flags = sel.get('flags') or []
    if not flags:
        return None
    ack = cfg.driver_dir / f'FLAG_ACK_{stage}.txt'
    if ack.is_file() and sha in ack.read_text(encoding='utf-8', errors='replace'):
        return ack
    text = json.dumps(flags, indent=1)
    if cfg.dry_run:
        ctx.add_plan(f'{stage}: ALERT and stop: the selection has flags and {cfg.rel(ack)} does not cite its sha256')
        return None
    raise Alert(f'{stage} FLAG', f'the selection {cfg.rel(cfg.selection_path(stage))} (sha256 {sha}) has flags and '
                                 f'{cfg.rel(ack)} does not acknowledge them (it must contain this sha256)', text)


def stage_entry(cfg, stage, sel, sha, ack):
    rows = sorted(sel.get('table') or [], key=lambda r: r.get('order', 0))
    final = stage in FINAL_STAGES
    parts = []
    for r in rows:
        p = f'`{r.get("candidate")}` {fmt(r.get("mean_ds"))} (n {r.get("n")})'
        if final and 'mean_ds_T22' in r:
            p += f', over T22 {fmt(r.get("mean_ds_T22"))} (n {r.get("n_T22")})'
        parts.append(p)
    kept = f'{len(sel.get("kept_routes") or [])} of {len(sel.get("routes") or [])} routes kept'
    dropped = sel.get('dropped_routes') or {}
    if dropped:
        kept += ' (dropped: ' + ', '.join(sorted(dropped, key=lambda x: (len(x), x))) + ')'
    if final:
        win = f'Selected: `{sel.get("selected")}`'
    else:
        win = (f'Survivors (top {len(sel.get("survivors") or [])}): '
               + ', '.join(f'`{s}`' for s in sel.get('survivors') or []))
    flag = ''
    if sel.get('flags'):
        names = ', '.join(f'`{f.get("candidate")}`' for f in sel['flags'])
        flag = (f' Flags: {names} (repeated agent set-up failures; the registered rule dropped those routes), '
                f'investigated and acknowledged in `{cfg.rel(ack)}` (sha256 `{sha256_file(ack)}`) before the next block.')
    warn = ''
    if sel.get('warnings'):
        warn = f' The selection lists {len(sel["warnings"])} warning(s).'
    nxt = NEXT[stage]
    after = (f' The `{nxt}` block is generated from this selection after this entry.' if nxt
             else f' Final stage of the {sel.get("grid")} grid.')
    return (f'**{stage}**, {entry_time()}. Selection `{cfg.rel(cfg.selection_path(stage))}` (sha256 `{sha}`), '
            f'written {sel.get("written")} by `select_stage.py --variant {VARIANT} --stage {stage} --queue '
            f'{cfg.queue_arg} --write` for the job file `{sel.get("job_file")}` (sha256 `{sel.get("job_file_sha256")}`); '
            f'{kept}. Mean DS over the kept routes: {"; ".join(parts)}. {win}.{flag}{warn}{after}')


def block_problems(cfg, block, dep, dep_sha):
    """[] if the generated block files of `block` are complete, passed their check and cite the dependency selection."""
    jsonl, spec_p, check_p = cfg.block_paths(block)
    missing = [cfg.rel(p) for p in (jsonl, spec_p, check_p) if not p.is_file()]
    if missing:
        return [f'missing {missing}']
    problems = []
    sha = sha256_file(jsonl)
    check, spec = read_json(check_p), read_json(spec_p)
    if not isinstance(check, dict) or not isinstance(spec, dict):
        return ['unreadable .check.json or .stage.json']
    try:
        lines = [json.loads(ln) for ln in jsonl.read_text(encoding='utf-8').splitlines() if ln.strip()]
    except ValueError as e:
        return [f'job file does not parse: {e}']
    if check.get('problems'):
        problems.append(f'check problems: {check["problems"][:5]}')
    if check.get('all_dry_runs_ok') is not True:
        problems.append('the check does not report every dry run as passed')
    if check.get('job_file_sha256') != sha or spec.get('job_file_sha256') != sha:
        problems.append('job_file_sha256 of the check / stage spec differs from the job file')
    if not (len(lines) == check.get('n_lines') == spec.get('n_lines')) or not lines:
        problems.append(f'line counts: file {len(lines)}, check {check.get("n_lines")}, spec {spec.get("n_lines")}')
    if spec.get('block') != block or spec.get('variant') != VARIANT:
        problems.append('stage spec of another block / variant')
    sel_key = cfg.rel(cfg.selection_path(dep))
    if (spec.get('inputs') or {}).get(sel_key) != dep_sha:
        problems.append(f'the stage spec does not cite the recorded selection {sel_key} sha256 {dep_sha}')
    ids = [j.get('id') for j in lines]
    if len(set(ids)) != len(ids) or any(j.get('block') != block for j in lines):
        problems.append('duplicate ids or lines of another block')
    return problems


def ensure_block(cfg, ctx, stage, nxt, sel_sha):
    """Generate the next block from the recorded selection (p1_jobs.py --check --write). 'ok' or None (dry run)."""
    st = ctx.st(stage)
    jsonl, spec_p, check_p = cfg.block_paths(nxt)
    queued = cfg.jobs_d / jsonl.name
    if jsonl.is_file() and spec_p.is_file() and check_p.is_file():
        probs = block_problems(cfg, nxt, stage, sel_sha)
        if not probs:
            st['next_block'] = {'block': nxt, 'job_file': cfg.rel(jsonl), 'sha256': sha256_file(jsonl),
                                'check': cfg.rel(check_p), 'generated': mtime_iso(check_p)}
            return 'ok'
        if queued.exists() or read_json(check_p) is not None and (read_json(check_p) or {}).get('problems'):
            raise Alert(f'{nxt} block', f'the generated files of {nxt} do not validate: {probs}')
    elif queued.exists():
        raise Alert(f'{nxt} block', f'{cfg.rel(queued)} is in jobs.d but {cfg.rel(jsonl)} or its stage spec / check is '
                                    'missing')
    if cfg.dry_run:
        ctx.add_plan(f'generate {nxt}: {show(cfg.jobs_cmd(nxt))}')
        return None
    check_stop(ctx)
    cmd = cfg.jobs_cmd(nxt)
    rc, out, err = run_cmd(ctx, cmd, TIMEOUTS['jobs'])
    if rc != 0:
        raise Alert(f'p1_jobs {nxt}', f'p1_jobs.py --block {nxt} --check --write exited {rc}', both(out, err), cmd)
    crash_point(ctx, 'block_generated')
    probs = block_problems(cfg, nxt, stage, sel_sha)
    if probs:
        raise Alert(f'p1_jobs {nxt}', f'the generated block {nxt} does not validate: {probs}', both(out, err), cmd)
    ctx.log(f'{nxt}: generated {cfg.rel(jsonl)} (sha256 {sha256_file(jsonl)}) from {stage} (sha256 {sel_sha})\n'
            + out.rstrip()[-3000:])
    st['next_block'] = {'block': nxt, 'job_file': cfg.rel(jsonl), 'sha256': sha256_file(jsonl),
                        'check': cfg.rel(check_p), 'generated': mtime_iso(check_p)}
    ctx.save()
    return 'ok'


def ensure_copied(cfg, ctx, stage, nxt):
    """Copy the generated job file of `nxt` into jobs.d once. 'present', 'copied' or None (dry run)."""
    src = cfg.block_paths(nxt)[0]
    dst = cfg.jobs_d / src.name
    src_sha = sha256_file(src)
    nb = ctx.st(stage).get('next_block') or {}
    ctx.st(stage)['next_block'] = nb
    if dst.exists():
        if sha256_file(dst) != src_sha:
            raise Alert(f'{nxt} copy', f'{cfg.rel(dst)} exists and differs from {cfg.rel(src)}; the driver never '
                                       'overwrites a queued job file')
        nb.update(copied_to=cfg.rel(dst), copied=mtime_iso(dst))
        return 'present'
    new_ids = set(job_ids(src))
    dup = {}
    for f in sorted(cfg.jobs_d.glob('*.jsonl')):
        for i in job_ids(f):
            if i in new_ids:
                dup.setdefault(f.name, []).append(i)
    if dup:
        raise Alert(f'{nxt} copy', f'job ids of {src.name} already exist in jobs.d (the runner would skip them): '
                                   f'{ {k: v[:3] for k, v in dup.items()} }')
    if cfg.dry_run:
        ctx.add_plan(f'copy {cfg.rel(src)} into {cfg.rel(cfg.jobs_d)}/')
        return None
    check_stop(ctx)
    tmp = cfg.jobs_d / f'.{src.name}.p1_driver.tmp'
    data = src.read_bytes()
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, dst)
    _fsync_dir(cfg.jobs_d)
    if sha256_file(dst) != src_sha:
        raise Alert(f'{nxt} copy', f'the copy {cfg.rel(dst)} does not have the sha256 of {cfg.rel(src)}')
    ctx.log(f'{nxt}: copied {cfg.rel(src)} into {cfg.rel(dst)} ({len(new_ids)} jobs, sha256 {src_sha})')
    nb.update(copied_to=cfg.rel(dst), copied=mtime_iso(dst))
    ctx.save()
    crash_point(ctx, 'copied')
    return 'copied'


def ensure_runner(cfg, ctx, copied_now, q=None):
    """Start the runner with launch_queue.sh when pending jobs have none (rules in the module docstring)."""
    q = q or queue_status(cfg)
    ctx.state['queue'] = queue_summary(q)
    if not q['pending']:
        return 'idle'
    if q['runner_alive'] or runner_lock_held(cfg):     # the pid check first: no lock test while the runner runs
        if q['pause_file']:
            ctx.add_attention(f'{cfg.queue_arg}/PAUSE exists: the runner starts no new job')
        return 'running'
    if q['stop_file']:
        ctx.add_attention(f'{cfg.queue_arg}/STOP exists and no runner runs: {len(q["pending"])} jobs wait. Check the '
                          'disk (df -h), remove STOP by hand, then relaunch (bash framelease_v4/protocol/launch_queue.sh '
                          f'{cfg.queue_arg})')
        return 'stop_file'
    ex = q['runner_exit']
    if ex is not None and ex.get('exit_code') in ABNORMAL_RUNNER_EXIT:
        msg = (f'the runner exited with {ex.get("reason")!r} (exit {ex.get("exit_code")}, '
               f'{ABNORMAL_RUNNER_EXIT[ex["exit_code"]]}) and {len(q["pending"])} jobs are pending; the driver does not '
               'relaunch it (a relaunch could use up the attempts of further jobs): fix the cause, then relaunch')
        if cfg.dry_run:
            ctx.add_plan('ALERT and stop: ' + msg)
            return 'alert'
        raise Alert('runner', msg, json.dumps(ex, indent=1, default=str))
    if ex is not None and ex.get('exit_code') == SIGNAL_RUNNER_EXIT:
        ctx.add_attention(f'the runner was stopped by a signal ({ex.get("reason")!r}, exit {SIGNAL_RUNNER_EXIT}) and '
                          f'{len(q["pending"])} jobs are pending; the driver never relaunches a runner that was stopped '
                          'on purpose (or by a shutdown): relaunch by hand with bash framelease_v4/protocol/'
                          f'launch_queue.sh {cfg.queue_arg} (to stop the runner on purpose, place {cfg.queue_arg}/STOP)')
        return 'attention'
    if not copied_now and not (ex is not None and ex.get('reason') == 'queue empty'):
        last = ('no exit record after its last start (killed or crashed)' if ex is None and q['last_runner_start']
                else f'exit {ex.get("reason")!r}' if ex is not None else 'never started')
        ctx.add_attention(f'no runner holds {cfg.queue_arg}/runner.lock and {len(q["pending"])} jobs are pending (last '
                          f'runner: {last}); the driver relaunches only after copying a block or after a normal '
                          f"'queue empty' exit: relaunch by hand with bash framelease_v4/protocol/launch_queue.sh "
                          f'{cfg.queue_arg}')
        return 'attention'
    if cfg.dry_run:
        ctx.add_plan(f'launch the runner: {show(cfg.launch_cmd())}')
        return 'dry'
    check_stop(ctx)
    if os.nice(0) != 0 and not cfg.allow_nice_launch:
        raise Alert('runner', f'the driver runs at nice {os.nice(0)}: a runner it launched would inherit that priority '
                              '(the P1 runners ran at nice 0; scheduler CPU time is charged to the simulated timeline, '
                              'PROTOCOL Secs. 2.3, 11.2); restart the driver at normal priority')
    cmd = cfg.launch_cmd()
    rc, out, err = run_cmd(ctx, cmd, TIMEOUTS['launch'], low=False)
    if rc == 0:
        ctx.log('runner launched: ' + ' | '.join(ln for ln in out.splitlines() if ln.strip())[-1500:])
        ctx.state['queue'] = queue_summary(queue_status(cfg))
        ctx.save()
        return 'launched'
    if 'another runner holds' in err:
        ctx.log('launch_queue.sh: another runner started meanwhile; nothing to do')
        return 'running'
    if '/STOP exists' in err:
        ctx.add_attention(f'launch_queue.sh refused: {err.strip()[:300]}')
        return 'stop_file'
    raise Alert('launch_queue', f'launch_queue.sh exited {rc}', both(out, err), cmd)


def advance_stage(cfg, ctx, stage):
    """Process one stage as far as possible. 'done' (recorded; next block generated, queued and running), or a waiting
    status ('blocked', 'waiting', 'dry')."""
    st = ctx.st(stage)
    jf = cfg.jobs_d / job_file_name(stage)
    st['job_file'] = cfg.rel(jf)
    if not jf.is_file():
        prev = PREV.get(stage)
        st.update(status='not_queued',
                  note=(f'generated after the {prev} selection is written and recorded' if prev
                        else f'{job_file_name(stage)} (a registered block) is not in jobs.d'))
        return 'blocked'
    st['job_file_sha256'] = sha256_file(jf)
    st['times']['queued'] = mtime_iso(jf)
    sel, sha, how = ensure_selection(cfg, ctx, stage)
    if sel is None:
        return how
    ack = check_flags(cfg, ctx, stage, sel, sha)
    if sel.get('flags') and ack is None:          # dry run: the ALERT is in the plan
        return 'dry'
    st.update(status='selected', note=None)
    r = ensure_recorded(cfg, ctx, stage, sha, lambda: stage_entry(cfg, stage, sel, sha, ack))
    if r is None:
        st['note'] = 'selection written, not yet recorded in Sec. 13.2'
        return 'dry'
    ent = protocol_view(cfg)['entries'].get(stage)
    st['entry'] = {'line': ent['line'], 'when': ent['when']} if ent else {'cited': True}
    st['times']['recorded'] = ent['when'] if ent else None
    st['status'] = 'recorded'
    ctx.save()
    nxt = NEXT[stage]
    if nxt is None:
        st['status'] = 'done'
        return 'done'
    if ensure_block(cfg, ctx, stage, nxt, sha) is None:
        return 'dry'
    c = ensure_copied(cfg, ctx, stage, nxt)
    if c is None:
        return 'dry'
    st['times']['next_generated'] = (st.get('next_block') or {}).get('generated')
    st['times']['next_copied'] = (st.get('next_block') or {}).get('copied')
    if c == 'copied':                                  # a block copied earlier is covered by the end-of-cycle check
        ensure_runner(cfg, ctx, copied_now=True)
    st.update(status='done', note=None)
    ctx.save()
    return 'done'


# ---------------------------------------------------------------------------------------------------- freeze, D1, done

def freeze_problems(cfg, doc):
    if not isinstance(doc, dict):
        return ['not readable JSON']
    probs = []
    if doc.get('schema') != FREEZE_SCHEMA or doc.get('variant') != VARIANT:
        probs.append(f'schema / variant {doc.get("schema")!r} / {doc.get("variant")!r}')
    stages = doc.get('stages') or {}
    for s in STAGES:
        p = cfg.selection_path(s)
        if (stages.get(s) or {}).get('sha256') != (sha256_file(p) if p.is_file() else None):
            probs.append(f'{s}: sha256 differs from {cfg.rel(p)}')
    return probs


def ensure_freeze(cfg, ctx):
    path = cfg.freeze_path
    fin = ctx.state['final']
    if path.exists():
        doc = read_json(path)
        probs = freeze_problems(cfg, doc)
        if probs:
            raise Alert('tuning freeze', f'{cfg.rel(path)} exists but does not match the recorded stage selections '
                                         f'({probs[:4]}); the driver never overwrites it')
        sha = sha256_file(path)
        fin['freeze'] = {'path': cfg.rel(path), 'sha256': sha, 'written': doc.get('written')}
        return doc, sha
    if cfg.dry_run:
        ctx.add_plan(f'tuning freeze: {show(cfg.freeze_cmd())}; then record it in Sec. 13.2 and re-seal')
        return None, None
    check_stop(ctx)
    cmd = cfg.freeze_cmd()
    rc, out, err = run_cmd(ctx, cmd, TIMEOUTS['freeze'], {'CUDA_VISIBLE_DEVICES': ''})
    m = re.search(r'^wrote (?P<p>.+?)  sha256 (?P<s>[0-9a-f]{64})$', out, re.M)
    if rc != 0 or not m or Path(m.group('p')).resolve() != path.resolve() or not path.is_file():
        raise Alert('tuning freeze', f'select_stage.py --freeze --write exited {rc} or wrote no {cfg.rel(path)}',
                    both(out, err), cmd)
    sha = sha256_file(path)
    doc = read_json(path)
    probs = freeze_problems(cfg, doc)
    if sha != m.group('s') or probs:
        raise Alert('tuning freeze', f'the written freeze does not validate: {probs[:4]}', both(out, err), cmd)
    ctx.log(f'tuning freeze written {cfg.rel(path)} sha256 {sha}\n' + out.rstrip()[-3000:])
    crash_point(ctx, 'freeze_written')
    fin['freeze'] = {'path': cfg.rel(path), 'sha256': sha, 'written': doc.get('written')}
    ctx.save()
    return doc, sha


def freeze_entry(cfg, doc, sha):
    L, d, A = doc.get('L_star') or {}, doc.get('d_star') or {}, doc.get('A_star') or {}
    ev = doc.get('event_star') or {}
    pp = ev.get('policy_params') or {}
    theta = str(ev.get('candidate') or '').split('_hb')[0]
    risk = doc.get('fl_risk')
    if risk is None:
        risk_txt = 'no extra lease point (L* is not B0)'
    elif isinstance(risk, dict):
        risk_txt = f'lease point `{risk.get("lease_point")}` ({risk.get("rule")})'
    else:
        risk_txt = str(risk)
    flags = sorted((doc.get('flags') or {}).keys())
    return (f'**Tuning freeze**, {entry_time()}. `{cfg.rel(cfg.freeze_path)}` (sha256 `{sha}`), written '
            f'{doc.get("written")} by `select_stage.py --variant {VARIANT} --freeze --write` from the eight stage '
            f'selections above (Sec. 4.9): L* = `{L.get("label")}` (`{L.get("envelope_path")}`, sha256 '
            f'`{L.get("envelope_sha256")}`, validity {L.get("validity")}); d* = {d.get("d")} (utility '
            f'`{d.get("utility")}`); A* = {A.get("age_lease_s")} s; Event-Triggered `{ev.get("candidate")}` (theta* = '
            f'{theta}, A_hb* = {pp.get("heartbeat_s")} s); fl_risk: {risk_txt}.'
            + (f' Stage flags carried into the freeze: {", ".join(flags)} (acknowledged in their entries).' if flags
               else ''))


def d1_problems(cfg, doc, freeze_sha):
    if not isinstance(doc, dict):
        return ['not readable JSON']
    probs = []
    if doc.get('schema') != D1_SCHEMA or doc.get('variant') != VARIANT:
        probs.append('schema / variant')
    if (doc.get('tuning_freeze') or {}).get('sha256') != freeze_sha:
        probs.append('it does not include the recorded tuning freeze')
    blocks = doc.get('blocks') or []
    if len(blocks) != len(BLOCK_NO) or any(int(b.get('pending') or 0) for b in blocks):
        probs.append(f'{len(blocks)} blocks, pending jobs {[b.get("block") for b in blocks if b.get("pending")]}')
    if not cfg.d1_paths()[1].is_file():
        probs.append('the .md file is missing')
    return probs


def ensure_d1(cfg, ctx, freeze_sha):
    jpath, mpath = cfg.d1_paths()
    fin = ctx.state['final']
    ent = protocol_view(cfg)['entries'].get('d1')
    doc = read_json(jpath)
    if ent is None and (not jpath.is_file() or d1_problems(cfg, doc, freeze_sha)):
        if cfg.dry_run:
            ctx.add_plan(f'D1 summary: {show(cfg.d1_cmd())}; then record it in Sec. 13.2, re-seal, write '
                         f'{cfg.rel(cfg.done_path)} and stop')
            return None
        check_stop(ctx)
        cmd = cfg.d1_cmd()
        rc, out, err = run_cmd(ctx, cmd, TIMEOUTS['d1'], {'CUDA_VISIBLE_DEVICES': ''})
        wrote = {Path(p).resolve(): s for p, s in re.findall(r'^wrote (.+?)  sha256 ([0-9a-f]{64})$', out, re.M)}
        if rc != 0 or jpath.resolve() not in wrote or mpath.resolve() not in wrote:
            raise Alert('D1 summary', f'd1_summary.py --write exited {rc} or did not write both files',
                        both(out[-20000:], err), cmd)
        doc = read_json(jpath)
        probs = d1_problems(cfg, doc, freeze_sha)
        if probs or sha256_file(jpath) != wrote[jpath.resolve()] or sha256_file(mpath) != wrote[mpath.resolve()]:
            raise Alert('D1 summary', f'the written D1 summary does not validate: {probs}', both(out[-20000:], err), cmd)
        ctx.log(f'D1 summary written {cfg.rel(jpath)} and {cfg.rel(mpath)}')
        crash_point(ctx, 'd1_written')
    if not isinstance(doc, dict) or not mpath.is_file():
        raise Alert('D1 summary', f'{cfg.rel(jpath)} / {cfg.rel(mpath)} missing or unreadable although Sec. 13.2 has '
                                  'a D1 entry')
    jsha, msha = sha256_file(jpath), sha256_file(mpath)
    fin['d1'] = {'json': cfg.rel(jpath), 'json_sha256': jsha, 'md': cfg.rel(mpath), 'md_sha256': msha,
                 'written': doc.get('written')}
    ctx.save()
    return doc, jsha, msha


def d1_entry(cfg, doc, jsha, msha, freeze_sha):
    jpath, mpath = cfg.d1_paths()
    return (f'**D1 summary**, {entry_time()}. `{cfg.rel(jpath)}` (sha256 `{jsha}`) and `{cfg.rel(mpath)}` (sha256 '
            f'`{msha}`), written {doc.get("written")} by `d1_summary.py --variant {VARIANT} --queue {cfg.queue_arg} '
            f'--write` after every job of the queue was final: {len(doc.get("blocks") or [])} blocks on training routes '
            f'only, with the tuning freeze (sha256 `{freeze_sha}`). D1, continuing or stopping, is the user\'s decision '
            f'(Sec. 4.8); no later phase was started.')


def write_done(cfg, ctx, fdoc, fsha, d1):
    doc, jsha, msha = d1
    reg = registration_view(cfg)
    view = protocol_view(cfg)
    stages = {}
    for s in STAGES:
        st = ctx.st(s)
        stages[s] = {'selection': st.get('selection'), 'sha256': st.get('selection_sha256'), 'winners': st.get('winners'),
                     'job_file': st.get('job_file'), 'entry_line': (view['entries'].get(s) or {}).get('line')}
    done = {'schema': DONE_SCHEMA, 'written': now_iso(), 'variant': VARIANT, 'queue': cfg.queue_arg, 'stages': stages,
            'freeze': {'path': cfg.rel(cfg.freeze_path), 'sha256': fsha,
                       **{k: fdoc.get(k) for k in ('L_star', 'd_star', 'A_star', 'event_star', 'fl_risk')},
                       'entry_line': (view['entries'].get('freeze') or {}).get('line')},
            'd1': {'json': cfg.rel(cfg.d1_paths()[0]), 'json_sha256': jsha, 'md': cfg.rel(cfg.d1_paths()[1]),
                   'md_sha256': msha, 'entry_line': (view['entries'].get('d1') or {}).get('line')},
            'protocol_sha256': reg['protocol_sha256'], 'manifest_sha256': reg['manifest_sha256'],
            'manifest_files': reg['manifest_files'], 'seal_ok': reg['seal_ok'],
            'next': 'D1 goes to the user, who decides whether the work continues (PROTOCOL Sec. 4.8). The driver started '
                    'no later phase (P2 and later are not started).'}
    atomic_write(cfg.done_path, json.dumps(done, indent=1, sort_keys=True, default=str) + '\n')
    ctx.state['final']['p1_done'] = cfg.rel(cfg.done_path)
    ctx.log(f'P1 DONE: {cfg.rel(cfg.done_path)} written; D1 goes to the user; the driver stops')


def advance_final(cfg, ctx):
    fin = ctx.state['final']
    if not all(ctx.st(s).get('status') == 'done' for s in LAST):
        fin['status'] = 'waiting for the age_s2 and event_s2 selections to be recorded'
        return 'blocked'
    doc, fsha = ensure_freeze(cfg, ctx)
    if doc is None:
        return 'dry'
    if ensure_recorded(cfg, ctx, 'freeze', fsha, lambda: freeze_entry(cfg, doc, fsha)) is None:
        return 'dry'
    q = queue_status(cfg)
    ctx.state['queue'] = queue_summary(q)
    if q['pending'] and protocol_view(cfg)['entries'].get('d1') is None:
        fin['status'] = f'freeze recorded; D1 waits for {len(q["pending"])} jobs in jobs.d to be final'
        ctx.log(fin['status'])
        return 'waiting'
    d1 = ensure_d1(cfg, ctx, fsha)
    if d1 is None:
        return 'dry'
    ddoc, jsha, msha = d1
    if ensure_recorded(cfg, ctx, 'd1', jsha, lambda: d1_entry(cfg, ddoc, jsha, msha, fsha)) is None:
        return 'dry'
    if cfg.dry_run:
        ctx.add_plan(f'write {cfg.rel(cfg.done_path)} and stop')
        return 'dry'
    write_done(cfg, ctx, doc, fsha, d1)
    fin['status'] = 'P1 done'
    return 'done'


# ---------------------------------------------------------------------------------------------------- cycle and main

def write_alert(cfg, ctx, a):
    ctx.state['alert'] = {'time': now_iso(), 'step': a.step, 'problem': a.problem, 'file': cfg.rel(cfg.alert_path)}
    ctx.state['driver']['status'] = 'ALERT'
    if cfg.dry_run:
        ctx.add_plan(f'ALERT and stop: {a.step}: {a.problem}')
        if a.output:
            for ln in a.output.splitlines()[:40]:
                print(f'      | {ln}')
        return
    text = (f'P1 DRIVER ALERT {now_iso()}\nstep:    {a.step}\nproblem: {a.problem}\n'
            + (f'command: {show(a.cmd)}\n' if a.cmd else '') + f'\n{a.output}\n\n---\n'
            'The driver stopped (exit 1) and refuses to start while this file exists. Investigate and fix the cause, '
            'then move this file aside (mv ALERT.txt ALERT.<UTC>.resolved.txt) and start the driver again. A FLAG is '
            'acknowledged by writing the selection sha256 and the investigation note into FLAG_ACK_<stage>.txt in '
            'this directory.\n')
    path = cfg.alert_path
    if path.exists():
        path = cfg.driver_dir / f'ALERT.{time.strftime("%Y%m%dT%H%M%S")}.txt'
    atomic_write(path, text)
    ctx.log(f'ALERT ({cfg.rel(path)}): {a.step}: {a.problem}')


def mark_rest(cfg, ctx, stages, blocker):
    """Status of the stages behind the first stage of a chain that is not done (informational)."""
    for s in stages:
        st = ctx.st(s)
        jf = cfg.jobs_d / job_file_name(s)
        st['job_file'] = cfg.rel(jf)
        if jf.is_file():
            st.update(status='queued', note=f'waits for {blocker}')
        else:
            st.update(status='not_queued', note=f'generated after {PREV.get(s)} is selected and recorded (the chain '
                                                f'waits for {blocker})')


def cycle(cfg, ctx):
    """One pass over both chains and the final steps. 'done', 'alert', 'stopped' or 'continue'."""
    ctx.attention = []
    ctx.lock_busy = False
    ctx.plan = []
    ctx.state['driver']['status'] = 'running'
    try:
        check_stop(ctx)
        try:
            ensure_open_txn_finished(cfg, ctx)
        except Wait as w:
            ctx.add_attention(str(w))
        try:                    # the registered baseline, from a consistent sealed state (first cycle: the registration)
            ctx.state['registered_baseline'] = baseline_summary(cfg, sealed_baseline(cfg, ctx))
        except Alert as a:      # a broken Sec. 13.2 structure: an ALERT only when an entry has to be written
            ctx.add_attention(f'{a.step}: {a.problem}')
        q = queue_status(cfg)
        ctx.state['queue'] = queue_summary(q)
        for chain in CHAINS:
            for k, stage in enumerate(chain):
                check_stop(ctx)
                try:
                    r = advance_stage(cfg, ctx, stage)
                except Wait as w:
                    ctx.st(stage).update(status='waiting_lock', note=str(w))
                    ctx.log(f'{stage}: {w}')
                    r = 'waiting'
                if r != 'done':
                    mark_rest(cfg, ctx, chain[k + 1:], stage)
                    break
        try:
            r = advance_final(cfg, ctx)
        except Wait as w:
            ctx.state['final']['status'] = str(w)
            ctx.log(f'final steps: {w}')
            r = 'waiting'
        if r == 'done':
            ctx.state['driver']['status'] = 'DONE'
            return 'done'
        runner = ensure_runner(cfg, ctx, copied_now=False)
        q = queue_status(cfg)
        if runner in ('idle', 'attention', 'stop_file') and not q['pending'] and not q['runner_alive']:
            for s in STAGES:
                if ctx.st(s)['status'] == 'waiting_final':
                    ctx.add_attention(f'{s}: select_stage reports jobs without a final outcome, but every job in jobs.d '
                                      'has a final runner record and no runner runs: check the queue (a --retry-failed '
                                      'generation, or a job of the stage outside jobs.d?)')
        ctx.state['driver']['status'] = 'waiting'
        return 'continue'
    except Alert as a:
        write_alert(cfg, ctx, a)
        return 'alert'
    except Stop:
        ctx.state['driver']['status'] = 'stopped'
        ctx.log('stop requested: the driver exits')
        return 'stopped'
    except Exception as e:  # noqa: BLE001  (a bug or an unexpected state: never advance past it)
        write_alert(cfg, ctx, Alert('driver', f'unexpected {type(e).__name__}: {e}', traceback.format_exc()))
        return 'alert'
    finally:
        try:
            ctx.state['registration'] = registration_view(cfg)
        except OSError:
            pass
        ctx.save()


def check_chain():
    """The chain, block numbers and dependencies hard-coded here must equal framelease_v4/protocol/p1_jobs.py."""
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from framelease_v4.protocol import p1_jobs as PJ
    except Exception as e:  # noqa: BLE001
        return [f'cannot import framelease_v4/protocol/p1_jobs.py: {e}']
    probs = []
    blocks = PJ.BLOCKS[VARIANT]
    if set(blocks) != set(BLOCK_NO):
        probs.append(f'blocks {sorted(blocks)} != {sorted(BLOCK_NO)}')
    for b, (no, grid, stage, rset, dep) in blocks.items():
        if BLOCK_NO.get(b) != no:
            probs.append(f'{b}: block number {no} != {BLOCK_NO.get(b)}')
        if b != 'ref' and PREV.get(b) != dep:
            probs.append(f'{b}: dependency {dep} != {PREV.get(b)}')
    if set(PJ.FINAL_STAGE[VARIANT].values()) != set(FINAL_STAGES):
        probs.append(f'final stages {PJ.FINAL_STAGE[VARIANT]} != {FINAL_STAGES}')
    return probs


def lock_holder_text(path):
    try:
        return Path(path).read_text(errors='replace').strip()
    except OSError:
        return ''


def driver_running(cfg):
    """(running, holder text): the pid written into driver.lock is alive and runs p1_driver.py. No lock is taken (a
    test lock could make a driver that starts at that instant refuse to run)."""
    holder = lock_holder_text(cfg.lock_path)
    m = re.match(r'pid (\d+)', holder)
    return bool(m) and 'p1_driver.py' in pid_cmdline(m.group(1)), holder


def dry_run(cfg):
    ctx = Ctx(cfg, read_json(cfg.state_path))
    print(f'p1_driver --dry-run {now_iso()} (changes nothing; select_stage runs without --write)')
    print(f'root:     {cfg.root}')
    try:
        q = queue_status(cfg)
        held = runner_lock_held(cfg)
        files = ', '.join(f'{k} {v["final"]}/{v["jobs"]}' for k, v in q['job_files'].items())
        print(f'queue:    {cfg.queue_arg}: {q["jobs"]} jobs, {q["final"]} final, {len(q["pending"])} pending ({files})')
        print(f'runner:   runner.lock "{q["runner_lock"]}"; flock test: {"held" if held else "free"}; pid alive and '
              f'gpu_queue: {q["runner_alive"]}; STOP {q["stop_file"]}, PAUSE {q["pause_file"]}; last exit after the '
              f'last start: {q["runner_exit"] and {k: q["runner_exit"].get(k) for k in ("reason", "exit_code")}}')
        reg = registration_view(cfg)
        view = protocol_view(cfg)
        print(f'protocol: {cfg.rel(cfg.protocol)} sha256 {reg["protocol_sha256"]}; MANIFEST {reg["manifest_sha256"]} '
              f'({reg["manifest_files"]} files); seal {"OK" if reg["seal_ok"] else "MISMATCH"}; heading {HEADING} '
              + (f'at line {view["heading"] + 1}' if view['heading'] is not None
                 else f'absent (created at the first entry, before line {view["anchor"] + 1}: "{ANCHOR} ...")')
              + f'; driver entries: {sorted(view["entries"]) or "none"}')
    except Alert as a:
        print(f'WOULD ALERT and stop: {a.step}: {a.problem}')
        return 1
    running, holder = driver_running(cfg)
    print(f'driver:   another driver running: {running}{" (" + holder + ")" if holder else ""}; ALERT.txt '
          f'{cfg.alert_path.exists()}; STOP {cfg.stop_path.exists()}; P1_DONE.json {cfg.done_path.exists()}; open '
          f'record transaction: {bool(read_txn(cfg))}; protocol lock file exists: {cfg.protocol_lock.exists()}')
    if cfg.alert_path.exists():
        print('NOTE: the driver refuses to start while ALERT.txt exists')
    if cfg.done_path.exists():
        print('P1 is done (P1_DONE.json): the driver would exit at once')
        return 0
    probs = check_chain() if cfg.check_chain else []
    print(f'chain:    {" -> ".join(CHAINS[0])}; {" -> ".join(CHAINS[1])}; consistent with p1_jobs.BLOCKS: '
          f'{"yes" if not probs else probs}')
    print('cycle (as the driver would run it now):')
    outcome = cycle(cfg, ctx)
    print('stages:')
    for s in STAGES:
        st = ctx.st(s)
        extra = ''
        if st.get('selection_sha256'):
            extra = f' selection {st["selection_sha256"][:16]}... winners {st.get("winners")}'
        print(f'  {s:<9} {st["status"]:<18} {st.get("note") or ""}{extra}')
    print(f'final:    {ctx.state["final"].get("status")}')
    b = ctx.state.get('registered_baseline') or {}
    if b:
        print(f'baseline: {b.get("file")}: ' + (f'saved, {b.get("registered_files")} registered files (from manifest '
                                                 f'{b.get("from_manifest_sha256")})' if b.get('saved') else
                                                 f'not saved yet; the first cycle saves {b.get("registered_files")} '
                                                 'registered files (the sealed manifest)'))
    for a in ctx.attention:
        print(f'ATTENTION: {a}')
    if ctx.plan:
        print('would do now:')
        for p in ctx.plan:
            print(f'  - {p}')
    else:
        waiting = [s for s in STAGES if ctx.st(s)['status'] in ('waiting_final', 'waiting_lock')]
        print('would do now: nothing; waiting for ' + (', '.join(waiting) if waiting else 'nothing')
              + (' to become final (select_stage exit 3); re-checked every '
                 f'{cfg.interval_s:.0f} s' if waiting else ''))
    if cfg.json_out:
        print(json.dumps(ctx.state, indent=1, sort_keys=True, default=str))
    return 0 if outcome != 'alert' else 1


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('--dry-run', action='store_true', help='print what the driver would do now; change nothing')
    ap.add_argument('--json', action='store_true', help='with --dry-run: also print the would-be pipeline_state.json')
    ap.add_argument('--once', action='store_true', help='run one cycle in the foreground and exit')
    ap.add_argument('--interval-s', type=float, default=300.0)
    ap.add_argument('--lock-timeout-s', type=float, default=300.0, help='wait for the protocol lock this long per cycle')
    ap.add_argument('--root', default=str(ROOT), help='project root (tests: a sandbox)')
    ap.add_argument('--queue', default='outputs/framelease_v4/queue_p1')
    ap.add_argument('--jobs-dir', default='outputs/framelease_v4/p1_jobs')
    ap.add_argument('--selection-dir', default='outputs/framelease_v4/tuning/selection')
    ap.add_argument('--freeze-path', default='outputs/framelease_v4/tuning/selection.json')
    ap.add_argument('--d1-dir', default='outputs/framelease_v4/tuning/d1')
    ap.add_argument('--protocol', default='framelease_v4/PROTOCOL.md')
    ap.add_argument('--protocol-lock', default='framelease_v4/.protocol.lock')
    ap.add_argument('--registration-dir', default='outputs/framelease_v4/registration')
    ap.add_argument('--driver-dir', default='outputs/framelease_v4/p1_driver')
    ap.add_argument('--state-file', default='outputs/framelease_v4/pipeline_state.json')
    ap.add_argument('--python', default=str(ROOT / '.conda-unidrive-linux/bin/python'))
    ap.add_argument('--select-script', default='framelease_v4/protocol/select_stage.py')
    ap.add_argument('--jobs-script', default='framelease_v4/protocol/p1_jobs.py')
    ap.add_argument('--d1-script', default='framelease_v4/protocol/d1_summary.py')
    ap.add_argument('--registration-script', default='framelease_v4/protocol/registration.py')
    ap.add_argument('--launch-script', default='framelease_v4/protocol/launch_queue.sh')
    ap.add_argument('--env-script', default='linux/env.sh')
    ap.add_argument('--no-chain-check', action='store_true', help='tests: skip the comparison with p1_jobs.BLOCKS')
    ap.add_argument('--normal-priority', action='store_true',
                    help='run the tools without the nice 10 / ionice prefix (never needed in production)')
    ap.add_argument('--allow-nice-launch', action='store_true',
                    help='tests only: run (and launch the mock runner) although the driver itself runs niced')
    return ap.parse_args(argv)


def main(argv=None):
    a = parse_args(argv)
    cfg = Cfg(a)
    if cfg.dry_run:
        return dry_run(cfg)
    cfg.driver_dir.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(cfg.lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(f'p1_driver: another instance holds {cfg.lock_path} ({lock_holder_text(cfg.lock_path)}); exiting',
              file=sys.stderr)
        os.close(lock_fd)
        return 2
    os.ftruncate(lock_fd, 0)
    os.write(lock_fd, f'pid {os.getpid()} started {now_iso()}\n'.encode())
    atomic_write(cfg.pid_path, f'{os.getpid()}\n')
    ctx = Ctx(cfg, read_json(cfg.state_path), echo=cfg.once or sys.stdout.isatty())
    ctx.log(f'START pid {os.getpid()} root {cfg.root} queue {cfg.queue_arg} interval {cfg.interval_s:.0f} s'
            + (' (--once)' if cfg.once else ''))
    code = 2
    try:
        code = run_driver(cfg, ctx)
    finally:
        ctx.log(f'EXIT code {code}')
        try:
            if cfg.pid_path.read_text().strip() == str(os.getpid()):
                cfg.pid_path.unlink()
        except OSError:
            pass
        os.close(lock_fd)
    return code


def run_driver(cfg, ctx):
    """The start checks and the cycle loop of main() (the instance lock is held). Returns the exit code."""
    if cfg.alert_path.exists():
        ctx.state['driver']['status'] = 'ALERT (unresolved)'
        ctx.state['alert'] = {'file': cfg.rel(cfg.alert_path), 'note': 'present at start; the driver refuses to run'}
        ctx.save()
        ctx.log(f'refusing to run: {cfg.rel(cfg.alert_path)} exists (resolve it, then move it aside)')
        print(f'p1_driver: {cfg.alert_path} exists; resolve it first', file=sys.stderr)
        return 1
    if cfg.stop_path.exists():
        ctx.log(f'refusing to run: {cfg.rel(cfg.stop_path)} exists (remove it to start the driver)')
        print(f'p1_driver: {cfg.stop_path} exists; remove it to start', file=sys.stderr)
        return 2
    if cfg.done_path.exists():
        ctx.state['driver']['status'] = 'DONE'
        ctx.state['final']['p1_done'] = cfg.rel(cfg.done_path)
        ctx.save()
        ctx.log('P1_DONE.json exists: P1 is done; nothing to do (the driver never starts a later phase)')
        return 0
    if os.nice(0) != 0 and not cfg.allow_nice_launch:
        msg = (f'the driver runs at nice {os.nice(0)}; a runner it launches would inherit that priority (the P1 runners '
               'run at nice 0): start it at normal priority (the tools it runs get nice 10 by themselves)')
        ctx.log(f'refusing to run: {msg}')
        print(f'p1_driver: {msg}', file=sys.stderr)
        return 2
    probs = check_chain() if cfg.check_chain else []
    if probs:
        ctx.log(f'refusing to run: the driver chain differs from p1_jobs.py: {probs}')
        print(f'p1_driver: chain mismatch with p1_jobs.py: {probs}', file=sys.stderr)
        return 2

    def on_signal(signum, _frame):
        ctx.stop = True
        ctx.log(f'signal {signum}: stopping at the next safe point')
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    while True:
        ctx.cycle += 1
        outcome = cycle(cfg, ctx)
        if outcome == 'done':
            return 0
        if outcome == 'alert':
            return 1
        if outcome == 'stopped' or cfg.once:
            return 0
        end = time.monotonic() + cfg.interval_s
        while time.monotonic() < end and not ctx.stop and not cfg.stop_path.exists():
            time.sleep(min(1.0, max(0.0, end - time.monotonic())))
        if ctx.stop or cfg.stop_path.exists():
            ctx.state['driver']['status'] = 'stopped'
            ctx.save()
            ctx.log('stop requested (signal or STOP file): the driver exits')
            return 0


if __name__ == '__main__':
    raise SystemExit(main())
