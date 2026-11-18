#!/usr/bin/env python3
"""Sequential GPU job queue runner (FrameLease v2): one GPU job at a time, resumable, wall-capped.

Queue contract (all workers)
  Job files: <queue>/jobs.d/*.jsonl, one JSON object per line:
      {"id": unique str, "kind": "closed_loop" | "sweep", "tier": int, "cmd": [argv run from the project root],
       "wall_cap_s": int}
  Files are processed in name order and lines in order. The directory is re-scanned before every job, so files
  added later are picked up. Extra keys are copied into the status records. Invalid lines (bad JSON, missing or
  wrong-typed fields) and repeated ids are skipped and logged once per runner start. A last line without a newline
  that does not parse yet is treated as still being written.
  Status: <queue>/status.jsonl (append-only, fsync'd JSON lines):
      runner_start | start | end | invalid_line | runner_exit
  An id is done when it has an 'end' record with final = true. Other files in <queue>: runner.log (progress log),
  logs/<id>.a<attempt>.log (stdout/stderr of the job), progress.json (counts, current job, ETA),
  current_job.json (processes of the running job; used to recover after a runner crash), runner.lock.

  python framelease_v2/gpu_queue.py                      # run; keeps polling for new jobs (STOP file ends it)
  python framelease_v2/gpu_queue.py --list               # state of every job; starts nothing
  python framelease_v2/gpu_queue.py --exit-when-empty    # exit once no job is pending

Guarantees
  * Never two GPU jobs at once: jobs run strictly one after another; an exclusive flock on runner.lock refuses a
    second runner on the same queue; before each job the runner waits until the shared GPU lock
    (results/shared_gpu_resource/.writer.lock, framelease_common.writer_lock) is free, until no foreign GPU compute
    process holds more than --foreign-gpu-mib, until --min-free-gpu-mib are free, and (closed_loop) until the CARLA
    ports (--port, +1, +2, +6000) can be bound. The job itself takes the shared lock (run_closed_loop.py and
    c1_depth_sweep.py both do).
  * Disk: no job starts while less than --min-free-gib GiB are free on the project file system (default 20.5).
  * Resumable: ids with a final 'end' record are skipped. If the runner dies mid-job, the next runner finds
    current_job.json: it adopts the still-running job (waits for it under the same wall cap) or, if the job is
    gone, classifies whatever it left on disk; a job without a valid result is re-run.
  * Wall cap: measured from the job's launch. On expiry the job gets SIGINT (run_closed_loop.py then stops its
    evaluator and CARLA and writes its result), after --grace-s SIGTERM, then SIGKILL to its process group.
  * Cleanup: the runner makes itself a child subreaper (prctl PR_SET_CHILD_SUBREAPER), so processes that the job
    started and orphaned (the CARLA server is started by the evaluator with setsid) stay its descendants. Every
    descendant is recorded with its creation time while the job runs; anything still alive after the job ends,
    or after a timeout, is terminated (SIGTERM, then SIGKILL). No other process is ever signalled. A shared GPU
    lock file left behind by a process of the job (killed before it could release the lock) is removed; the lock
    of any other holder is never touched.
  * Retries: a closed_loop attempt without a valid official route record (no record, an execution-failure status
    such as 'Simulation crashed' or 'Agent crashed', a launch error or a wall-cap timeout) and a failed sweep
    attempt are re-run, up to --max-attempts attempts in total. A valid route record is final whatever the
    driving outcome ('Failed - Agent got blocked', 'Failed - TickRuntime', ... are results). A launcher that
    could not obtain the shared GPU lock does not use up an attempt. --retry-failed gives jobs whose final
    attempt failed a new attempt budget.
  * Circuit breaker: after --max-consecutive-failures failed attempts in a row the runner exits (code 3).
  * Pinned code: a job may carry "require_sha256": {path relative to the project root: sha256}. It is not started
    while any of these files differs (logged as BLOCKED; the queue waits rather than mixing code versions).
  * Control files in <queue>: STOP (finish the current job, then exit), PAUSE (start no new job while present).
"""
from __future__ import annotations

import argparse
import ctypes
import fcntl
import hashlib
import json
import os
import re
import resource
import shutil
import signal
import socket
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUEUE = ROOT / 'outputs/framelease_v2/gpu_queue'
DEFAULT_GPU_LOCK_ROOT = ROOT / 'results/shared_gpu_resource'
DEFAULT_CLOSED_LOOP_OUTPUT = ROOT / 'outputs/framelease_v2/closed_loop'   # run_closed_loop.py --output-dir default
DEFAULT_SWEEP_ROOT = ROOT / 'outputs/framelease_v2/c1_sweep'               # c1_depth_sweep.py --run-name parent
KINDS = ('closed_loop', 'sweep')
REQUIRED_KEYS = ('id', 'kind', 'tier', 'cmd', 'wall_cap_s')
# run_closed_loop.EXECUTION_FAILURE_STATUS (leaderboard statistics_manager.FAILURE_MESSAGES): the run itself broke.
EXECUTION_FAILURE_STATUS = ('Simulation crashed', "Agent's sensors were invalid", "Agent couldn't be set up",
                            'Agent crashed')
LOCK_HELD_MARKER = 'shared GPU lock is held'
OK_OUTCOMES = ('ok', 'result_with_warnings')
PR_SET_CHILD_SUBREAPER = 36
GIB = 1024 ** 3
ETA_PRIOR_S = {'latency': 420.0, 'oracle': 2600.0}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def local_iso(epoch):
    return datetime.fromtimestamp(epoch).astimezone().isoformat(timespec='minutes')


def safe_name(text):
    return re.sub(r'[^A-Za-z0-9._-]', '_', text)[:180]


def atomic_write_json(path, data):
    path = Path(path)
    tmp = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True, default=str) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def read_json_file(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def cmd_option(cmd, name, default=None):
    """Value of '--name value' or '--name=value' in an argv list (last occurrence wins)."""
    value = default
    for i, arg in enumerate(cmd):
        if arg == name and i + 1 < len(cmd):
            value = cmd[i + 1]
        elif arg.startswith(name + '='):
            value = arg.split('=', 1)[1]
    return value


def validate_job(job):
    if not isinstance(job, dict):
        return 'not a JSON object'
    missing = [k for k in REQUIRED_KEYS if k not in job]
    if missing:
        return f'missing keys {missing}'
    if not isinstance(job['id'], str) or not job['id'].strip():
        return 'id must be a non-empty string'
    if job['kind'] not in KINDS:
        return f'kind must be one of {KINDS}'
    if isinstance(job['tier'], bool) or not isinstance(job['tier'], int):
        return 'tier must be an int'
    if not isinstance(job['cmd'], list) or not job['cmd'] or not all(isinstance(a, str) for a in job['cmd']):
        return 'cmd must be a non-empty list of strings'
    cap = job['wall_cap_s']
    if isinstance(cap, bool) or not isinstance(cap, (int, float)) or cap <= 0 or int(cap) != cap:
        return 'wall_cap_s must be a positive int'
    pins = job.get('require_sha256')
    if pins is not None and (not isinstance(pins, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                                   for k, v in pins.items())):
        return 'require_sha256 must map file paths (relative to the project root) to sha256 strings'
    return None


def job_extras(spec):
    """Descriptive job keys for the status records (the sha256 pins are summarized by their count)."""
    extra = {k: v for k, v in spec.items() if k not in REQUIRED_KEYS and k != 'require_sha256'}
    if spec.get('require_sha256'):
        extra['pinned_files'] = len(spec['require_sha256'])
    return extra


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def pin_mismatches(pins):
    """Files whose sha256 differs from the job's optional "require_sha256" pins ([] if all match)."""
    bad = []
    for rel, want in sorted((pins or {}).items()):
        path = Path(rel) if Path(rel).is_absolute() else ROOT / rel
        try:
            got = sha256_file(path)
        except OSError as e:
            got = f'unreadable ({e.strerror})'
        if got != want:
            bad.append({'file': rel, 'expected': want, 'found': got})
    return bad


def gpu_snapshot(timeout_s=20):
    """nvidia-smi memory / utilization and compute processes; None if nvidia-smi is unavailable."""
    try:
        q = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,memory.total,utilization.gpu',
                            '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=timeout_s,
                           check=True)
        used, total, util = [float(x) for x in q.stdout.strip().splitlines()[0].split(',')[:3]]
        a = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,used_memory,process_name',
                            '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=timeout_s,
                           check=True)
        apps = []
        for line in a.stdout.strip().splitlines():
            parts = [x.strip() for x in line.split(',')]
            if len(parts) >= 2 and parts[0].isdigit():
                try:
                    mib = float(parts[1])
                except ValueError:
                    mib = 0.0
                apps.append({'pid': int(parts[0]), 'used_mib': mib, 'name': ','.join(parts[2:])[:120]})
        return {'used_mib': used, 'total_mib': total, 'util_pct': util, 'apps': apps}
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def ports_free(ports):
    """Same test as stage05.require_free_ports: every port can be bound on 127.0.0.1."""
    for port in ports:
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1', int(port)))
            except OSError:
                return False
    return True


def process_alive(pid, create_time=None):
    """True if pid runs (not a zombie) and, when given, has this creation time (guards against pid reuse)."""
    try:
        p = psutil.Process(int(pid))
        if create_time is not None and abs(p.create_time() - float(create_time)) > 0.01:
            return False
        return p.status() != psutil.STATUS_ZOMBIE
    except (psutil.Error, ValueError):
        return False


def _no_core_dumps():
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (ValueError, OSError):
        pass


class Runner:
    def __init__(self, args):
        self.args = args
        self.qdir = args.queue_dir.resolve()
        self.jobs_dir = self.qdir / 'jobs.d'
        self.status_path = self.qdir / 'status.jsonl'
        self.log_path = self.qdir / 'runner.log'
        self.logs_dir = self.qdir / 'logs'
        self.current_path = self.qdir / 'current_job.json'
        self.progress_path = self.qdir / 'progress.json'
        self.stop_file = self.qdir / 'STOP'
        self.pause_file = self.qdir / 'PAUSE'
        self.gpu_lock_file = args.gpu_lock_root.resolve() / '.writer.lock'
        self.stop_signal = None
        self.warned = set()
        self.tracked = {}
        self.current = None
        self.job_gpu = {}
        self.consecutive_failures = 0
        self.jobs_run = 0
        self.retry_generation = 0
        self._lock_fd = None
        self._last_wait_log = {}
        self._port_wait_start = {}

    # ------------------------------------------------------------------------------------------------ logging
    def log(self, msg, **kv):
        line = f'{utc_now()} {msg}'
        if kv:
            line += ' ' + json.dumps(kv, sort_keys=True, default=str)
        with self.log_path.open('a', encoding='utf-8') as f:
            f.write(line + '\n')

    def log_throttled(self, key, msg, every_s=600, **kv):
        now = time.monotonic()
        if key not in self._last_wait_log or now - self._last_wait_log[key] >= every_s:
            self._last_wait_log[key] = now
            self.log(msg, **kv)

    def status(self, record):
        record = {'utc': utc_now(), **record}
        with self.status_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(record, sort_keys=True, default=str) + '\n')
            f.flush()
            os.fsync(f.fileno())

    # ------------------------------------------------------------------------------------------------ queue state
    def scan_jobs(self, report=True):
        jobs, seen = [], {}
        for path in sorted(self.jobs_dir.glob('*.jsonl')):
            try:
                text = path.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError) as e:
                self.warn_once(('read', path.name), f'cannot read {path.name}: {e}', report)
                continue
            lines = text.split('\n')
            for no, line in enumerate(lines, 1):
                if not line.strip():
                    continue
                partial = no == len(lines)          # no trailing newline: may still be being written
                try:
                    job = json.loads(line)
                except json.JSONDecodeError as e:
                    if not partial:
                        self.warn_once((path.name, no, 'json'), f'{path.name}:{no}: invalid JSON ({e})', report)
                    continue
                problem = validate_job(job)
                if problem:
                    self.warn_once((path.name, no, problem), f'{path.name}:{no}: {problem}', report)
                    continue
                if job['id'] in seen:
                    self.warn_once((path.name, no, 'dup'), f'{path.name}:{no}: duplicate id {job["id"]!r} '
                                   f'(first at {seen[job["id"]]}); skipped', report)
                    continue
                seen[job['id']] = f'{path.name}:{no}'
                jobs.append({'file': path.name, 'line': no, 'spec': job})
        return jobs

    def warn_once(self, key, msg, report=True):
        if key in self.warned or not report:
            return
        self.warned.add(key)
        self.log('INVALID LINE ' + msg)
        self.status({'event': 'invalid_line', 'message': msg})

    def load_records(self):
        records = []
        if self.status_path.exists():
            for line in self.status_path.read_text(encoding='utf-8').splitlines():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    @staticmethod
    def job_states(records):
        """id -> {attempts (highest attempt number), counted (counted attempts since the last final), final, open}."""
        states = {}
        for r in records:
            if r.get('event') not in ('start', 'end') or 'id' not in r:
                continue
            s = states.setdefault(r['id'], {'attempts': 0, 'counted': 0, 'final': None, 'open': None, 'ends': []})
            s['attempts'] = max(s['attempts'], int(r.get('attempt') or 0))
            if r['event'] == 'start':
                s['open'] = r
            else:
                s['open'] = None
                s['ends'].append(r)
                if r.get('final'):
                    s['final'] = r
                    s['counted'] = 0
                elif r.get('counted'):
                    s['counted'] += 1
        return states

    def is_done(self, job_id, states):
        s = states.get(job_id)
        if not s or s['final'] is None:
            return False
        if self.args.retry_failed and s['final'].get('outcome') not in OK_OUTCOMES:
            # a new attempt budget: done again only once a later final record exists
            return s['final'].get('retry_generation', 0) >= self.retry_generation
        return True

    # ------------------------------------------------------------------------------------------------ setup
    def acquire_runner_lock(self):
        self.qdir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.qdir / 'runner.lock', os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            holder = Path(self.qdir / 'runner.lock').read_text(errors='replace').strip()
            os.close(fd)
            print(f'another runner holds {self.qdir / "runner.lock"} ({holder}); exiting', file=sys.stderr)
            return False
        os.ftruncate(fd, 0)
        os.write(fd, f'pid {os.getpid()} started {utc_now()}\n'.encode())
        self._lock_fd = fd
        return True

    def install_signals(self):
        def handler(signum, _frame):
            self.stop_signal = signum
        signal.signal(signal.SIGTERM, handler)
        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGHUP, signal.SIG_IGN)

    def become_subreaper(self):
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            ok = libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) == 0
        except (OSError, AttributeError):
            ok = False
        if not ok:
            self.log('WARNING: could not become a child subreaper; orphaned job processes are still tracked by pid')
        return ok

    def environment_problems(self):
        if self.args.skip_env_check:
            return []
        problems = []
        for var in ('FRAMELEASE_ROOT', 'CHECKPOINT', 'CARLA_ROOT'):
            if not os.environ.get(var):
                problems.append(f'{var} is not set (source linux/env.sh before starting the runner)')
        ckpt = os.environ.get('CHECKPOINT')
        if ckpt and not Path(ckpt).is_file():
            problems.append(f'CHECKPOINT does not exist: {ckpt}')
        if not (Path(sys.prefix) / 'conda-meta').is_dir():
            problems.append('run inside the project Conda environment')
        return problems

    def child_env(self, job_id):
        env = os.environ.copy()
        if not env.get('CUDA_VISIBLE_DEVICES'):
            env['CUDA_VISIBLE_DEVICES'] = '0'      # GPU jobs; the runner itself never touches CUDA
        env['PYTHONUNBUFFERED'] = '1'
        env['FRAMELEASE_GPU_QUEUE_JOB'] = job_id
        return env

    def stop_requested(self):
        if self.stop_signal is not None:
            return f'signal {self.stop_signal}'
        if self.stop_file.exists():
            return 'STOP file'
        if self.args.max_jobs and self.jobs_run >= self.args.max_jobs:
            return f'--max-jobs {self.args.max_jobs} reached'
        return None

    # ------------------------------------------------------------------------------------------------ readiness
    def disk_free_gib(self):
        return shutil.disk_usage(self.args.disk_path).free / GIB

    def foreign_gpu_apps(self, snap, threshold_mib):
        ours = set(self.tracked) | {os.getpid()}
        return [a for a in (snap or {}).get('apps', []) if a['pid'] not in ours and a['used_mib'] >= threshold_mib]

    def ready(self, job):
        """(True, info) when the job may start now; (False, reason) after waiting a poll interval."""
        if self.pause_file.exists():
            self.log_throttled('pause', 'PAUSE file present; not starting new jobs')
            return False, 'pause'
        bad = pin_mismatches(job['spec'].get('require_sha256'))
        if bad:
            self.log_throttled(('pins', job['spec']['id']), f'BLOCKED: pinned code of {job["spec"]["id"]} changed; '
                               'not starting it (restore the files or amend the pre-registration and the job file)',
                               mismatches=bad)
            return False, 'code_mismatch'
        free = self.disk_free_gib()
        if free < self.args.min_free_gib:
            self.log_throttled('disk', f'WAITING: only {free:.2f} GiB free (< {self.args.min_free_gib} GiB); '
                                       'no job starts until space is freed')
            return False, 'disk'
        if self.gpu_lock_file.exists():
            holder = read_json_file(self.gpu_lock_file) or {}
            alive = process_alive(holder['pid']) if isinstance(holder.get('pid'), int) else None
            self.log_throttled('lock', 'WAITING for the shared GPU lock', holder=holder, holder_alive=alive)
            return False, 'gpu_lock'
        snap = gpu_snapshot()
        if snap is None:
            self.log_throttled('nvsmi', 'WARNING: nvidia-smi unavailable; GPU memory check skipped')
        else:
            foreign = self.foreign_gpu_apps(snap, self.args.foreign_gpu_mib)
            free_mib = snap['total_mib'] - snap['used_mib']
            if foreign or free_mib < self.args.min_free_gpu_mib:
                self.log_throttled('gpu', 'WAITING for the GPU: foreign compute processes or too little free memory',
                                   free_mib=free_mib, foreign=foreign)
                return False, 'gpu'
        if job['spec']['kind'] == 'closed_loop':
            try:
                port = int(cmd_option(job['spec']['cmd'], '--port', '2400'))
            except ValueError:
                port = None
            if port is not None:
                ports = [port, port + 1, port + 2, port + 6000]
                key = ('ports', job['spec']['id'])
                if not ports_free(ports):
                    first = self._port_wait_start.setdefault(job['spec']['id'], time.monotonic())
                    if time.monotonic() - first < self.args.port_wait_s:
                        self.log_throttled(key, f'WAITING for ports {ports}', every_s=120)
                        return False, 'ports'
                    self.log(f'ports {ports} still busy after {self.args.port_wait_s:.0f} s; launching anyway '
                             '(the launcher refuses busy ports and the attempt is retried)')
                self._port_wait_start.pop(job['spec']['id'], None)
        return True, {'gpu': snap, 'disk_free_gib': round(free, 2)}

    # ------------------------------------------------------------------------------------------------ processes
    def write_current(self):
        if self.current is not None:
            self.current['tracked'] = {str(k): v for k, v in self.tracked.items()}
            atomic_write_json(self.current_path, self.current)

    def track(self, root_pid=None):
        """Record every descendant (pid, creation time) of the runner, or of root_pid for an adopted job."""
        try:
            base = psutil.Process(root_pid) if root_pid else psutil.Process()
            kids = base.children(recursive=True)
            if root_pid:
                kids = [base] + kids
        except psutil.Error:
            kids = []
        if root_pid is not None:
            try:  # an adopted job's orphans are reparented to this runner only if they were orphaned after its start
                kids += psutil.Process().children(recursive=True)
            except psutil.Error:
                pass
        changed = False
        for p in kids:
            if p.pid in self.tracked or p.pid == os.getpid():
                continue
            try:
                self.tracked[p.pid] = {'create_time': p.create_time(), 'name': p.name(),
                                       'cmd': ' '.join(p.cmdline()[:4])[:300]}
                changed = True
            except psutil.Error:
                continue
        if changed:
            self.write_current()

    def reap(self, keep_pid=None):
        """waitpid() zombie children other than keep_pid (orphans reparented to this subreaper)."""
        try:
            kids = psutil.Process().children()
        except psutil.Error:
            return
        for p in kids:
            if p.pid == keep_pid:
                continue
            try:
                if p.status() == psutil.STATUS_ZOMBIE:
                    os.waitpid(p.pid, os.WNOHANG)
            except (psutil.Error, ChildProcessError, OSError):
                pass

    def wait_gone(self, procs, timeout_s, keep_pid=None):
        deadline = time.monotonic() + timeout_s
        while True:
            self.reap(keep_pid)
            alive = [p for p in procs if process_alive(p.pid, p.create_time_)]
            if not alive or time.monotonic() >= deadline:
                return alive
            time.sleep(0.5)

    def cleanup_leftovers(self, keep_pid=None):
        """Terminate every recorded descendant of the job that is still alive. Returns what was done."""
        victims = []
        for pid, info in sorted(self.tracked.items()):
            if pid == os.getpid() or not process_alive(pid, info['create_time']):
                continue
            try:
                p = psutil.Process(pid)
                p.create_time_ = info['create_time']
                victims.append(p)
            except psutil.Error:
                continue
        report = {'terminated': [], 'killed': [], 'survivors': []}
        if not victims:
            self.reap(keep_pid)
            return report
        self.log('cleanup: terminating leftover job processes',
                 processes=[(p.pid, self.tracked[p.pid]['name']) for p in victims])
        for p in victims:
            try:
                p.send_signal(signal.SIGTERM)
                report['terminated'].append([p.pid, self.tracked[p.pid]['name']])
            except psutil.Error:
                pass
        alive = self.wait_gone(victims, 10, keep_pid)
        for p in alive:
            try:
                p.send_signal(signal.SIGKILL)
                report['killed'].append([p.pid, self.tracked[p.pid]['name']])
            except psutil.Error:
                pass
        alive = self.wait_gone(alive, 15, keep_pid)
        report['survivors'] = [[p.pid, self.tracked[p.pid]['name']] for p in alive]
        if alive:
            self.log('ERROR: job processes survived SIGKILL', survivors=report['survivors'])
        return report

    def release_stale_gpu_lock(self):
        """Remove the shared GPU lock only if its holder is a process of this job that no longer runs."""
        data = read_json_file(self.gpu_lock_file)
        if not data or not isinstance(data.get('pid'), int):
            return None
        info = self.tracked.get(data['pid'])
        if info is None or process_alive(data['pid'], info['create_time']):
            return None
        again = read_json_file(self.gpu_lock_file)
        if again != data:
            return None
        try:
            self.gpu_lock_file.unlink()
        except FileNotFoundError:
            return None
        self.log('removed the shared GPU lock left by a dead process of this job', lock=data)
        return data

    def signal_launcher(self, proc, sig):
        try:
            os.kill(proc.pid, sig)
        except ProcessLookupError:
            pass

    def killpg(self, pgid, sig):
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError):
            pass

    def terminate(self, proc, reason):
        """SIGINT (graceful), then SIGTERM, then SIGKILL to the launcher's process group."""
        self.log(f'terminating job ({reason}): SIGINT to launcher pid {proc.pid}')
        self.signal_launcher(proc, signal.SIGINT)
        steps = [(self.args.grace_s, signal.SIGTERM), (15, signal.SIGKILL), (30, None)]
        for wait_s, next_sig in steps:
            deadline = time.monotonic() + wait_s
            while proc.poll() is None and time.monotonic() < deadline:
                self.track()
                self.reap(proc.pid)
                time.sleep(1)
            if proc.poll() is not None or next_sig is None:
                break
            self.log(f'launcher still running; {signal.Signals(next_sig).name} to its process group {proc.pid}')
            self.killpg(proc.pid, next_sig)
        if proc.poll() is None:
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.log('ERROR: launcher survived SIGKILL', pid=proc.pid)

    def sample_gpu(self):
        snap = gpu_snapshot()
        if snap is None:
            return
        g = self.job_gpu
        g['max_used_mib'] = max(g.get('max_used_mib', 0.0), snap['used_mib'])
        g['samples'] = g.get('samples', 0) + 1
        foreign = self.foreign_gpu_apps(snap, self.args.foreign_gpu_mib)
        if foreign:
            g['foreign_max_mib'] = max(g.get('foreign_max_mib', 0.0), max(a['used_mib'] for a in foreign))
            names = {f'{a["pid"]}:{a["name"]}' for a in foreign} | set(g.get('foreign_apps', []))
            g['foreign_apps'] = sorted(names)[:20]
            self.log_throttled('foreign_gpu', 'WARNING: foreign GPU compute process during a job', foreign=foreign)

    def heartbeat(self, elapsed_s):
        """Refresh progress.json during a job (liveness for observers; the counts are from the job's start)."""
        prog = read_json_file(self.progress_path)
        if not isinstance(prog, dict):
            return
        prog['heartbeat_utc'] = utc_now()
        prog['current_elapsed_s'] = round(elapsed_s)
        prog['current_tracked_processes'] = len(self.tracked)
        try:
            atomic_write_json(self.progress_path, prog)
        except OSError:
            pass

    # ------------------------------------------------------------------------------------------------ results
    def run_dir_from_log(self, log_file):
        try:
            lines = Path(log_file).read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError:
            return None
        for line in reversed(lines):
            line = line.strip()
            if line.startswith('{') and '"run_dir"' in line:
                try:
                    value = json.loads(line).get('run_dir')
                except ValueError:
                    continue
                if value:
                    return value
        return None

    def find_run_dir(self, spec, log_file, out_dir, runs_before):
        from_log = self.run_dir_from_log(log_file)
        if from_log:
            return from_log, []
        if spec['kind'] == 'closed_loop' and out_dir is not None:
            runs = out_dir / 'runs'
            new = sorted(set(os.listdir(runs)) - set(runs_before)) if runs.is_dir() else []
            if new:
                return str(runs / new[-1]), [str(runs / n) for n in new]
            return None, []
        if spec.get('run_dir'):
            return str(spec['run_dir']), []
        name = cmd_option(spec['cmd'], '--run-name')
        if name:
            return str(DEFAULT_SWEEP_ROOT / name), []
        return None, []

    @staticmethod
    def closed_loop_result(run_dir):
        """Summary of a run_closed_loop.py run directory (empty dict if it has no result yet)."""
        if not run_dir:
            return {}
        run_dir = Path(run_dir)
        res = read_json_file(run_dir / 'metrics/result.json')
        man = read_json_file(run_dir / 'manifest.json') or {}
        out = {'run_status': man.get('status'), 'blockers': man.get('blockers')}
        if res is None:
            out.update(route_records=0, valid_record=False, result_json=False)
            return out
        status = res.get('route_status')
        execution_failure = any(m in str(status) for m in EXECUTION_FAILURE_STATUS)
        agent = res.get('agent_summary') or {}
        out.update(result_json=True, route_records=res.get('route_records') or 0, route_status=status,
                   execution_failure=execution_failure, scores=res.get('scores'), timed_out=res.get('timed_out'),
                   launcher_wall_s=res.get('wall_s'), meta=res.get('meta'), returncode=res.get('returncode'),
                   error_head=(res.get('error') or '')[-400:] or None,
                   fallback_tick_ratio=agent.get('fallback_tick_ratio'),
                   action_age_p50_s=(agent.get('action_age_s') or {}).get('p50'))
        out['valid_record'] = bool(out['route_records']) and not execution_failure
        return out

    def classify(self, spec, exit_code, timed_out, interrupted, launch_error, result, log_file, counted_so_far):
        """outcome, counted (uses up an attempt), final."""
        if interrupted:
            return 'interrupted', False, False
        if spec['kind'] == 'closed_loop':
            if result.get('valid_record'):
                # exit code unknown (job adopted / finished while no runner was alive): use the run's own status
                clean = exit_code == 0 or (exit_code is None and result.get('run_status') == 'COMPLETED')
                return ('ok' if clean else 'result_with_warnings'), True, True
            text = (result.get('error_head') or '') + ' ' + ' '.join(map(str, result.get('blockers') or []))
            if LOCK_HELD_MARKER in text or self._log_mentions(log_file, LOCK_HELD_MARKER):
                return 'gpu_lock_busy', False, False
            if launch_error:
                outcome = 'launch_error'
            elif timed_out or result.get('timed_out'):
                outcome = 'timeout'
            else:
                outcome = 'infra_failure'
        else:
            if exit_code == 0 and not timed_out and not launch_error:
                return 'ok', True, True
            if exit_code is None and not timed_out and not launch_error:
                return 'exit_unknown', False, False     # adopted after a runner restart; sweeps resume, so re-run
            if self._log_mentions(log_file, 'GPU lock busy') or self._log_mentions(log_file, LOCK_HELD_MARKER):
                return 'gpu_lock_busy', False, False
            outcome = 'launch_error' if launch_error else ('timeout' if timed_out else 'failed')
        final = counted_so_far + 1 >= self.args.max_attempts
        return outcome, True, final

    @staticmethod
    def _log_mentions(log_file, text):
        try:
            with open(log_file, 'rb') as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - 65536))
                return text.encode() in f.read()
        except OSError:
            return False

    # ------------------------------------------------------------------------------------------------ execution
    def closed_loop_output_dir(self, cmd):
        value = cmd_option(cmd, '--output-dir')
        if value is None:
            return DEFAULT_CLOSED_LOOP_OUTPUT
        p = Path(value)
        return (p if p.is_absolute() else ROOT / p).resolve()

    def execute(self, job, attempt, state, ready_info):
        spec = job['spec']
        jid = spec['id']
        log_file = self.logs_dir / f'{safe_name(jid)}.a{attempt}.log'
        out_dir = self.closed_loop_output_dir(spec['cmd']) if spec['kind'] == 'closed_loop' else None
        runs_before = sorted(os.listdir(out_dir / 'runs')) if out_dir and (out_dir / 'runs').is_dir() else []
        extra = job_extras(spec)
        start_utc, start_epoch = utc_now(), time.time()
        self.status({'event': 'start', 'id': jid, 'attempt': attempt, 'file': job['file'], 'line': job['line'],
                     'kind': spec['kind'], 'tier': spec['tier'], 'wall_cap_s': int(spec['wall_cap_s']),
                     'cmd': spec['cmd'], 'log': str(log_file.relative_to(self.qdir)), 'runner_pid': os.getpid(),
                     'gpu': ready_info.get('gpu'), 'disk_free_gib': ready_info.get('disk_free_gib'), 'job': extra})
        self.log(f'START {jid} attempt {attempt} (tier {spec["tier"]}, {job["file"]}:{job["line"]}, '
                 f'wall cap {int(spec["wall_cap_s"])} s)')
        self.tracked, self.job_gpu = {}, {}
        self.current = {'id': jid, 'attempt': attempt, 'file': job['file'], 'line': job['line'], 'spec': spec,
                        'start_utc': start_utc, 'start_epoch': start_epoch, 'log': str(log_file),
                        'out_dir': str(out_dir) if out_dir else None, 'runs_before': runs_before,
                        'runner_pid': os.getpid(), 'counted_before': state['counted'],
                        'retry_generation': self.retry_generation}
        t0 = time.monotonic()
        proc, launch_error, timed_out, interrupted = None, None, False, None
        try:
            with log_file.open('ab') as out:
                proc = subprocess.Popen(spec['cmd'], cwd=ROOT, env=self.child_env(jid), stdin=subprocess.DEVNULL,
                                        stdout=out, stderr=subprocess.STDOUT, start_new_session=True,
                                        preexec_fn=_no_core_dumps)
        except (OSError, ValueError) as e:
            launch_error = f'{type(e).__name__}: {e}'
            self.log(f'LAUNCH ERROR {jid}: {launch_error}')
        if proc is not None:
            try:
                self.current['launcher'] = {'pid': proc.pid, 'create_time': psutil.Process(proc.pid).create_time()}
            except psutil.Error:
                self.current['launcher'] = {'pid': proc.pid, 'create_time': None}
            self.write_current()
            timed_out, interrupted = self.supervise(proc, float(spec['wall_cap_s']), t0)
        exit_code = proc.returncode if proc is not None else None
        return self.finish_job(job, attempt, state, start_utc, time.monotonic() - t0, exit_code, timed_out,
                               interrupted, launch_error, log_file, out_dir, runs_before, keep_pid=None)

    def supervise(self, proc, cap_s, t0, adopted=False):
        """Wait for the job; enforce the wall cap and runner signals. Returns (timed_out, interrupted)."""
        last_gpu = last_beat = 0.0
        while True:
            self.track(proc.pid if adopted else None)
            if not adopted:
                self.reap(proc.pid)
            if proc.poll() is not None:
                return False, None
            now = time.monotonic()
            if now - t0 > cap_s:
                self.log(f'WALL CAP: {cap_s:.0f} s exceeded')
                self.terminate(proc, 'wall cap')
                return True, None
            if self.stop_signal is not None:
                reason = f'runner received signal {self.stop_signal}'
                self.terminate(proc, reason)
                return False, reason
            if now - last_gpu >= self.args.gpu_sample_s:
                self.sample_gpu()
                last_gpu = now
            if now - last_beat >= 60:
                self.heartbeat(now - t0)
                last_beat = now
            time.sleep(self.args.poll_s)

    def finish_job(self, job, attempt, state, start_utc, wall_s, exit_code, timed_out, interrupted, launch_error,
                   log_file, out_dir, runs_before, keep_pid=None, note=None):
        spec = job['spec']
        cleanup = self.cleanup_leftovers(keep_pid)
        stale = self.release_stale_gpu_lock()
        run_dir, new_runs = self.find_run_dir(spec, log_file, out_dir, runs_before)
        result = self.closed_loop_result(run_dir) if spec['kind'] == 'closed_loop' else {}
        outcome, counted, final = self.classify(spec, exit_code, timed_out, interrupted, launch_error, result,
                                                log_file, state['counted'])
        record = {'event': 'end', 'id': spec['id'], 'attempt': attempt, 'start_utc': start_utc,
                  'end_utc': utc_now(), 'wall_s': round(wall_s, 1), 'exit_code': exit_code, 'outcome': outcome,
                  'counted': counted, 'final': final, 'retry_generation': self.retry_generation,
                  'will_retry': bool(counted and not final and outcome not in OK_OUTCOMES) or outcome in
                  ('interrupted', 'gpu_lock_busy', 'exit_unknown'),
                  'timed_out_runner': timed_out, 'interrupted': interrupted, 'launch_error': launch_error,
                  'run_dir': run_dir, 'other_new_run_dirs': [r for r in new_runs if r != run_dir] or None,
                  'result': result or None, 'cleanup': cleanup, 'stale_gpu_lock_removed': stale,
                  'gpu': self.job_gpu or None, 'log': str(Path(log_file).relative_to(self.qdir)),
                  'kind': spec['kind'], 'tier': spec['tier'], 'file': job['file'], 'line': job['line'],
                  'job': job_extras(spec), 'note': note}
        self.status(record)
        scores = (result or {}).get('scores') or {}
        self.log(f'END {spec["id"]} attempt {attempt}: {outcome} (exit {exit_code}, {wall_s:.0f} s'
                 + (f', route status {result.get("route_status")!r}, DS {scores.get("score_composed")}, '
                    f'RC {scores.get("score_route")}' if result.get('result_json') else '')
                 + f'){" final" if final else ""}', run_dir=run_dir)
        if outcome in OK_OUTCOMES:
            self.consecutive_failures = 0
        elif counted:
            self.consecutive_failures += 1
        self.current = None
        self.tracked = {}
        try:
            self.current_path.unlink()
        except FileNotFoundError:
            pass
        return record

    # ------------------------------------------------------------------------------------------------ recovery
    def recover_inflight(self):
        """After a runner crash: adopt a still-running job, or classify what the dead job left on disk."""
        cur = read_json_file(self.current_path)
        records = self.load_records()
        states = self.job_states(records)
        if cur is None:
            for jid, s in states.items():
                if s['open'] is not None:
                    o = s['open']
                    self.status({'event': 'end', 'id': jid, 'attempt': o.get('attempt'), 'outcome': 'interrupted',
                                 'counted': False, 'final': False, 'start_utc': o.get('utc'),
                                 'note': 'runner stopped during this attempt; no in-flight state was found'})
                    self.log(f'RECOVERY: {jid} attempt {o.get("attempt")} had no end record; marked interrupted')
            return
        spec = cur['spec']
        self.log(f'RECOVERY: in-flight job {spec["id"]} attempt {cur["attempt"]} from runner pid {cur.get("runner_pid")}')
        self.tracked = {int(k): v for k, v in (cur.get('tracked') or {}).items()}
        self.current = cur
        launcher = cur.get('launcher') or {}
        job = {'file': cur.get('file'), 'line': cur.get('line'), 'spec': spec}
        state = {'counted': cur.get('counted_before', 0)}
        out_dir = Path(cur['out_dir']) if cur.get('out_dir') else None
        timed_out, interrupted, note = False, None, 'recovered after a runner restart'
        if launcher.get('pid') and process_alive(launcher['pid'], launcher.get('create_time')):
            elapsed = time.time() - float(cur['start_epoch'])
            self.log(f'RECOVERY: launcher pid {launcher["pid"]} still running ({elapsed:.0f} s); adopting it')
            proc = _AdoptedProcess(launcher['pid'], launcher.get('create_time'))
            timed_out, interrupted = self.supervise(proc, float(spec['wall_cap_s']),
                                                    time.monotonic() - elapsed, adopted=True)
            note += '; adopted the running launcher (exit code unknown)'
        wall_s = time.time() - float(cur['start_epoch'])
        self.finish_job(job, cur['attempt'], state, cur['start_utc'], wall_s, None, timed_out, interrupted, None,
                        cur['log'], out_dir, cur.get('runs_before') or [], note=note)

    # ------------------------------------------------------------------------------------------------ progress
    @staticmethod
    def job_class(spec):
        if spec['kind'] == 'sweep':
            return 'sweep'
        return 'oracle' if 'oracle_sync' in spec['cmd'] else 'latency'

    def write_progress(self, jobs, states, state_label, current=None):
        counts = {'total': len(jobs), 'done_ok': 0, 'done_failed': 0, 'pending': 0}
        by_file = {}
        walls = {}
        for s in states.values():
            for e in s['ends']:
                if e.get('outcome') in OK_OUTCOMES and e.get('wall_s'):
                    cls = 'sweep' if e.get('kind') == 'sweep' else (
                        'oracle' if (e.get('job') or {}).get('policy') == 'oracle_sync' else 'latency')
                    walls.setdefault(cls, []).append(float(e['wall_s']))
        mean = {k: sum(v) / len(v) for k, v in walls.items()}
        remaining = 0.0
        for j in jobs:
            spec = j['spec']
            f = by_file.setdefault(j['file'], {'total': 0, 'done_ok': 0, 'done_failed': 0, 'pending': 0})
            f['total'] += 1
            s = states.get(spec['id'])
            if self.is_done(spec['id'], states):
                key = 'done_ok' if s['final'].get('outcome') in OK_OUTCOMES else 'done_failed'
            else:
                key = 'pending'
                cls = self.job_class(spec)
                est = mean.get(cls, ETA_PRIOR_S.get(cls, 0.5 * float(spec['wall_cap_s'])))
                if current and current.get('id') == spec['id']:
                    est = max(0.0, est - (time.time() - current['start_epoch']))
                remaining += est
            counts[key] += 1
            f[key] += 1
        progress = {'utc': utc_now(), 'runner_pid': os.getpid(), 'state': state_label, 'counts': counts,
                    'by_file': by_file, 'consecutive_failures': self.consecutive_failures,
                    'current': None if not current else {k: current.get(k) for k in
                                                         ('id', 'attempt', 'start_utc', 'file', 'line')},
                    'eta': {'remaining_s': round(remaining), 'finish_local': local_iso(time.time() + remaining),
                            'mean_wall_s_by_class': {k: round(v, 1) for k, v in mean.items()},
                            'finished_samples': {k: len(v) for k, v in walls.items()},
                            'prior_s_when_no_samples': ETA_PRIOR_S,
                            'basis': 'pending jobs x mean wall time of finished jobs of the same class '
                                     '(latency arm / oracle_sync / sweep); priors until samples exist'}}
        atomic_write_json(self.progress_path, progress)
        return progress

    # ------------------------------------------------------------------------------------------------ main loop
    def run(self):
        if not self.acquire_runner_lock():
            return 2
        problems = self.environment_problems()
        if problems:
            msg = 'environment check failed:\n  ' + '\n  '.join(problems)
            self.log('EXIT ' + msg.replace('\n', ' '))
            print(msg, file=sys.stderr)
            return 2
        self.install_signals()
        subreaper = self.become_subreaper()
        self.retry_generation = self.next_retry_generation() if self.args.retry_failed else 0
        self.status({'event': 'runner_start', 'pid': os.getpid(), 'argv': sys.argv, 'subreaper': subreaper,
                     'python': sys.executable, 'retry_generation': self.retry_generation,
                     'settings': {k: str(v) for k, v in vars(self.args).items()},
                     'env': {k: os.environ.get(k) for k in ('CUDA_VISIBLE_DEVICES', 'CHECKPOINT', 'CARLA_ROOT',
                                                            'FRAMELEASE_ROOT', 'CONDA_PREFIX')}})
        self.log(f'RUNNER START pid {os.getpid()} queue {self.qdir} (subreaper={subreaper})')
        exit_code, reason = 0, None
        try:
            self.recover_inflight()
            idle_since = None
            while True:
                reason = self.stop_requested()
                if reason:
                    exit_code = 4 if self.stop_signal is not None else 0
                    break
                jobs = self.scan_jobs()
                states = self.job_states(self.load_records())
                pending = [j for j in jobs if not self.is_done(j['spec']['id'], states)]
                if not pending:
                    self.write_progress(jobs, states, 'idle')
                    if self.args.exit_when_empty:
                        reason = 'queue empty'
                        break
                    idle_since = idle_since or time.monotonic()
                    if self.args.idle_exit_h and time.monotonic() - idle_since > self.args.idle_exit_h * 3600:
                        reason = f'idle for {self.args.idle_exit_h} h'
                        break
                    self.log_throttled('idle', 'queue empty; polling for new job files', every_s=3600)
                    self.sleep(self.args.idle_poll_s)
                    continue
                idle_since = None
                job = pending[0]
                ok, info = self.ready(job)
                if not ok:
                    self.write_progress(jobs, states, f'waiting:{info}')
                    self.sleep(self.args.wait_poll_s)
                    continue
                s = states.get(job['spec']['id']) or {'attempts': 0, 'counted': 0}
                attempt = s['attempts'] + 1
                self.current = {'id': job['spec']['id'], 'attempt': attempt, 'start_utc': utc_now(),
                                'start_epoch': time.time(), 'file': job['file'], 'line': job['line']}
                self.write_progress(jobs, states, 'running', self.current)
                record = self.execute(job, attempt, s, info)
                self.jobs_run += 1
                states = self.job_states(self.load_records())
                self.write_progress(self.scan_jobs(report=False), states, 'between_jobs')
                if record['outcome'] == 'interrupted':
                    continue
                if record['outcome'] == 'gpu_lock_busy':
                    self.sleep(self.args.wait_poll_s)
                if self.args.max_consecutive_failures and \
                        self.consecutive_failures >= self.args.max_consecutive_failures:
                    reason = f'circuit breaker: {self.consecutive_failures} failed attempts in a row'
                    self.log('CIRCUIT BREAKER ' + reason + '; fix the cause, then restart (with --retry-failed '
                             'for jobs whose attempts are used up)')
                    exit_code = 3
                    break
        except Exception:  # noqa: BLE001
            tb = traceback.format_exc()
            self.log('RUNNER ERROR ' + tb.replace('\n', ' | '))
            reason, exit_code = 'runner error: ' + tb.strip().splitlines()[-1], 1
            if self.current is not None and self.current.get('launcher'):
                self.log('runner error during a job: its processes are left for recovery by the next runner')
        finally:
            try:
                jobs = self.scan_jobs(report=False)
                self.write_progress(jobs, self.job_states(self.load_records()), 'exited')
            except Exception:  # noqa: BLE001
                pass
            self.status({'event': 'runner_exit', 'pid': os.getpid(), 'reason': reason, 'exit_code': exit_code})
            self.log(f'RUNNER EXIT ({reason}) code {exit_code}')
        return exit_code

    def next_retry_generation(self):
        gens = [int(r.get('retry_generation') or 0) for r in self.load_records() if r.get('event') == 'runner_start']
        return max(gens, default=0) + 1

    def sleep(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline and self.stop_signal is None and not self.stop_file.exists():
            time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))

    # ------------------------------------------------------------------------------------------------ --list
    def list_jobs(self):
        jobs = self.scan_jobs(report=False)
        states = self.job_states(self.load_records())
        self.retry_generation = 0
        counts = {}
        for j in jobs:
            spec = j['spec']
            s = states.get(spec['id']) or {}
            if s.get('open'):
                label = 'RUNNING'
            elif self.is_done(spec['id'], states):
                label = 'done:' + s['final'].get('outcome', '?')
            elif s.get('ends'):
                label = 'pending(retry after ' + s['ends'][-1].get('outcome', '?') + ')'
            else:
                label = 'pending'
            counts[label.split('(')[0]] = counts.get(label.split('(')[0], 0) + 1
            last = (s.get('ends') or [{}])[-1]
            res = last.get('result') or {}
            sc = res.get('scores') or {}
            print(f'{j["file"]}:{j["line"]:<4} t{spec["tier"]} {spec["id"]:<48} {label:<28} '
                  f'att {s.get("attempts", 0)} '
                  + (f'DS {sc.get("score_composed")} RC {sc.get("score_route")} {res.get("route_status")!s:.30}'
                     if sc else ''))
        print('counts:', json.dumps(counts, sort_keys=True))
        prog = read_json_file(self.progress_path)
        if prog:
            print('progress.json:', json.dumps({k: prog.get(k) for k in ('utc', 'state', 'current', 'eta')},
                                               default=str))
        return 0


class _AdoptedProcess:
    """Popen-like view of a launcher started by an earlier runner (not our child: no exit code)."""

    def __init__(self, pid, create_time):
        self.pid = pid
        self.create_time = create_time
        self.returncode = None

    def poll(self):
        return None if process_alive(self.pid, self.create_time) else -1

    def wait(self, timeout=None):
        deadline = time.monotonic() + (timeout or 0)
        while self.poll() is None:
            if timeout is not None and time.monotonic() > deadline:
                raise subprocess.TimeoutExpired('adopted', timeout)
            time.sleep(0.5)
        return -1


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--queue-dir', type=Path, default=DEFAULT_QUEUE)
    p.add_argument('--gpu-lock-root', type=Path, default=DEFAULT_GPU_LOCK_ROOT,
                   help='directory of the shared GPU lock (.writer.lock)')
    p.add_argument('--disk-path', type=Path, default=ROOT, help='file system whose free space is checked')
    p.add_argument('--min-free-gib', type=float, default=20.5, help='start no job below this free space')
    p.add_argument('--min-free-gpu-mib', type=float, default=18500.0,
                   help='start no job with less free GPU memory (a closed-loop job peaks at about 18 GB)')
    p.add_argument('--foreign-gpu-mib', type=float, default=1024.0,
                   help='a GPU compute process of someone else above this size blocks the start and is flagged')
    p.add_argument('--max-attempts', type=int, default=2, help='attempts per job without a valid result')
    p.add_argument('--max-consecutive-failures', type=int, default=6, help='circuit breaker (0 disables)')
    p.add_argument('--grace-s', type=float, default=120.0, help='after SIGINT, before SIGTERM')
    p.add_argument('--poll-s', type=float, default=1.0, help='job supervision interval')
    p.add_argument('--gpu-sample-s', type=float, default=60.0, help='nvidia-smi sampling interval during a job')
    p.add_argument('--wait-poll-s', type=float, default=15.0, help='re-check interval while a start is blocked')
    p.add_argument('--port-wait-s', type=float, default=600.0, help='wait this long for busy CARLA ports')
    p.add_argument('--idle-poll-s', type=float, default=60.0, help='re-scan interval when no job is pending')
    p.add_argument('--idle-exit-h', type=float, default=24.0, help='exit after this long without pending jobs (0: never)')
    p.add_argument('--exit-when-empty', action='store_true')
    p.add_argument('--max-jobs', type=int, default=0, help='exit after this many attempts (0: no limit)')
    p.add_argument('--retry-failed', action='store_true', help='give jobs whose final attempt failed a new budget')
    p.add_argument('--skip-env-check', action='store_true', help='tests only')
    p.add_argument('--list', action='store_true', help='print the state of every job and exit')
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    runner = Runner(args)
    if args.list:
        return runner.list_jobs()
    return runner.run()


if __name__ == '__main__':
    raise SystemExit(main())
