"""Disk watchdog and queue launch wrapper (framelease_v4/protocol/disk_watchdog.sh, launch_queue.sh; PROTOCOL Secs.
8.2, 8.5). CPU only; NOTHING is launched: the runner is never started (launch_queue.sh runs only with --dry-run or into
its refusals), the watched "runner" is a sleep process, and every queue directory is temporary.

  cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/protocol/tests/test_launch_tools.py

What is shown: the watchdog places STOP (with its reason) below the free-space threshold and not above it, never
signals the watched process, exits when that process exits, refuses a pid whose command line is not the runner's and
exits quietly for a pid that does not run; the wrapper prints the exact runner command (--exit-when-empty
--min-free-gib 6, logs) and the watchdog command, refuses without job files, with a STOP file or while another runner
holds the queue lock, writes nothing in a dry run; its launch-record code writes the hashes of the runner, the
watchdog, the wrapper and every job file.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WATCHDOG = ROOT / 'framelease_v4/protocol/disk_watchdog.sh'
LAUNCH = ROOT / 'framelease_v4/protocol/launch_queue.sh'
PY = str(ROOT / '.conda-unidrive-linux/bin/python')


def run(cmd, timeout=60, **kw):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, **kw)


class WatchdogTest(unittest.TestCase):
    def test_stop_below_threshold_and_exit_with_the_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = Path(tmp) / 'q'
            q.mkdir()
            fake = subprocess.Popen(['sleep', '4'])
            try:
                t0 = time.monotonic()
                p = run(['bash', str(WATCHDOG), str(q), str(fake.pid), '--expect-cmd', 'sleep',
                         '--min-free-gib', '1000000', '--interval-s', '1'], timeout=30)
                elapsed = time.monotonic() - t0
            finally:
                fake.wait(timeout=10)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertTrue((q / 'STOP').is_file())
            self.assertIn('disk_watchdog', (q / 'STOP').read_text())
            self.assertIn('STOP placed', p.stdout)
            self.assertIn('exited', p.stdout)
            self.assertEqual(fake.returncode, 0)                 # the watched process ran to its end (never signalled)
            self.assertLess(elapsed, 15)

    def test_no_stop_above_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = Path(tmp) / 'q'
            q.mkdir()
            fake = subprocess.Popen(['sleep', '2'])
            try:
                p = run(['bash', str(WATCHDOG), str(q), str(fake.pid), '--expect-cmd', 'sleep',
                         '--min-free-gib', '0.001', '--interval-s', '1'], timeout=30)
            finally:
                fake.wait(timeout=10)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertFalse((q / 'STOP').exists())

    def test_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = Path(tmp) / 'q'
            q.mkdir()
            fake = subprocess.Popen(['sleep', '5'])
            try:
                p = run(['bash', str(WATCHDOG), str(q), str(fake.pid)])          # default --expect-cmd gpu_queue.py
                self.assertEqual(p.returncode, 2)
                self.assertIn('is not the runner', p.stderr)
            finally:
                fake.kill()
                fake.wait(timeout=10)
            p = run(['bash', str(WATCHDOG), str(q), '999999999'])
            self.assertEqual(p.returncode, 0)
            self.assertIn('not running', p.stdout)
            self.assertEqual(run(['bash', str(WATCHDOG), str(q)]).returncode, 2)
            self.assertEqual(run(['bash', str(WATCHDOG), str(Path(tmp) / 'missing'), '1']).returncode, 2)
            self.assertEqual(run(['bash', str(WATCHDOG), str(q), '1', '--min-free-gib', '0']).returncode, 2)
            self.assertFalse((q / 'STOP').exists())


class LaunchWrapperTest(unittest.TestCase):
    def test_dry_run_prints_the_exact_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = Path(tmp) / 'queue_p1'
            (q / 'jobs.d').mkdir(parents=True)
            (q / 'jobs.d' / 'b00_smoke.jsonl').write_text('{}\n')
            before = sorted(str(p) for p in Path(tmp).rglob('*'))
            p = run(['bash', str(LAUNCH), str(q), '--dry-run'])
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn(f'{PY} -I -B framelease_v2/gpu_queue.py --queue-dir {q} --exit-when-empty --min-free-gib 6 '
                          f'>> {q}/runner.nohup.log 2>&1', p.stdout)
            self.assertIn(f'bash framelease_v4/protocol/disk_watchdog.sh {q} <runner pid> --min-free-gib 5 '
                          f'>> {q}/disk_watchdog.log 2>&1', p.stdout)
            self.assertIn('b00_smoke.jsonl', p.stdout)
            self.assertIn('dry run: nothing started', p.stdout)
            self.assertEqual(sorted(str(p) for p in Path(tmp).rglob('*')), before)   # wrote nothing

    def test_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = Path(tmp) / 'q'
            q.mkdir()
            p = run(['bash', str(LAUNCH), str(q), '--dry-run'])
            self.assertEqual(p.returncode, 2)
            self.assertIn('jobs.d not found', p.stderr)
            (q / 'jobs.d').mkdir()
            p = run(['bash', str(LAUNCH), str(q), '--dry-run'])
            self.assertEqual(p.returncode, 2)
            self.assertIn('no *.jsonl job file', p.stderr)
            (q / 'jobs.d' / 'b00.jsonl').write_text('{}\n')
            (q / 'STOP').write_text('disk_watchdog: low disk\n')
            p = run(['bash', str(LAUNCH), str(q), '--dry-run'])
            self.assertEqual(p.returncode, 2)
            self.assertIn('STOP exists', p.stderr)
            (q / 'STOP').unlink()
            fd = os.open(q / 'runner.lock', os.O_RDWR | os.O_CREAT, 0o644)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)                    # another "runner" holds the lock
                p = run(['bash', str(LAUNCH), str(q), '--dry-run'])
                self.assertEqual(p.returncode, 2)
                self.assertIn('another runner holds', p.stderr)
            finally:
                os.close(fd)
            self.assertEqual(run(['bash', str(LAUNCH), str(q), '--dry-run']).returncode, 0)
            self.assertEqual(run(['bash', str(LAUNCH)]).returncode, 2)
            self.assertEqual(run(['bash', str(LAUNCH), str(q), '--bogus']).returncode, 2)

    def test_launch_record_code(self):
        text = LAUNCH.read_text()
        code = re.search(r"<<'PYEOF'\n(.*?)\nPYEOF\n", text, re.S).group(1)
        with tempfile.TemporaryDirectory() as tmp:
            q = Path(tmp) / 'q'
            (q / 'jobs.d').mkdir(parents=True)
            (q / 'jobs.d' / 'b01_ref.jsonl').write_text('{"id": "x"}\n')
            p = run([PY, '-I', '-B', '-', str(q), '20261111T000000Z', '123', '456', '17.50', 'runner cmd', 'wd cmd'],
                    input=code)
            self.assertEqual(p.returncode, 0, p.stderr)
            rec = json.loads((q / 'launch_20261111T000000Z.json').read_text())
            self.assertEqual((rec['runner_pid'], rec['watchdog_pid'], rec['free_disk_gib']), (123, 456, 17.5))
            import hashlib
            self.assertEqual(rec['job_files'], {'b01_ref.jsonl': hashlib.sha256(b'{"id": "x"}\n').hexdigest()})
            self.assertEqual(rec['runner_sha256'],
                             hashlib.sha256((ROOT / 'framelease_v2/gpu_queue.py').read_bytes()).hexdigest())
            self.assertEqual(rec['watchdog_sha256'], hashlib.sha256(WATCHDOG.read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
