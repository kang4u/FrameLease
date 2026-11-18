"""Registration manifest of PROTOCOL.md (framelease_v4/protocol/registration.py; Secs. 12.2, 13.1). CPU only; no file
of the registration is written (the manifest is checked through a temporary copy; the 5.9 GB checkpoint is not hashed).

  cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/protocol/tests/test_registration.py

What is shown: the job pins of every registered job line agree with each other and with the tree (49 code and data
files + 3 envelopes); the manifest covers the protocol scripts, the smoke checker, the job files, the runner and the
Sec. 12.1 files, and excludes PROTOCOL.md (sealed separately), the workflow state and byte-code caches; verify() reports
exactly the entries that differ.
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from framelease_v4.protocol import registration as REG  # noqa: E402


class RegistrationTest(unittest.TestCase):
    def test_job_pins(self):
        pins = REG.job_pins()
        self.assertEqual(len(pins), 52)
        self.assertEqual(len([k for k in pins if k.startswith('outputs/framelease_v4/envelopes/')]), 3)
        self.assertEqual(len([k for k in pins if k.startswith('framelease_v4/')]), 12)
        for rel, sha in pins.items():
            self.assertEqual(REG.sha256_file(ROOT / rel), sha, rel)

    def test_manifest_coverage(self):
        paths = set(REG.manifest_paths())
        for rel in ('framelease_v4/protocol/check_smoke.py', 'framelease_v4/protocol/select_stage.py',
                    'framelease_v4/protocol/p1_jobs.py', 'framelease_v4/protocol/disk_watchdog.sh',
                    'framelease_v4/protocol/launch_queue.sh', 'framelease_v4/protocol/d1_summary.py',
                    'framelease_v4/protocol/registration.py', 'framelease_v4/protocol/tests/test_check_smoke.py',
                    'outputs/framelease_v4/p1_jobs/P1-0/b00_smoke.jsonl', 'outputs/framelease_v4/p1_jobs/README.md',
                    'outputs/framelease_v4/p1_jobs/FULL/b03_event_s1.check.json',
                    'outputs/framelease_v4/protocol/budget.md', 'outputs/framelease_v4/envelopes/manifest.json',
                    'outputs/framelease_v4/protocol/sources/FrameLease1109.md', 'framelease_v2/gpu_queue.py',
                    'framelease_v2/run_closed_loop.py', '/home/kang/Desktop/NEW/FrameLease1109.docx',
                    'checkpoints/UniDriveVLA/b5ac33e9483f6f61633c53353a8b53fbd96e2bc5/UniDriveVLA_Stage3_Bench2drive_2B.pt'):
            self.assertIn(rel, paths)
        for rel in REG.EXCLUDE_V4:
            self.assertNotIn(rel, paths)
        self.assertFalse(any('__pycache__' in p for p in paths))
        self.assertFalse(any(p.startswith('outputs/framelease_v4/registration/') for p in paths))

    def test_verify_reports_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = 'framelease_v4/protocol/check_smoke.py'
            man = Path(tmp) / 'MANIFEST.sha256'
            man.write_text(f'{REG.sha256_file(ROOT / good)}  {good}\n'
                           f'{hashlib.sha256(b"x").hexdigest()}  framelease_v4/protocol/p1_jobs.py\n')
            bad = REG.verify(man)
            self.assertEqual([b[0] for b in bad], ['framelease_v4/protocol/p1_jobs.py'])


if __name__ == '__main__':
    unittest.main()
