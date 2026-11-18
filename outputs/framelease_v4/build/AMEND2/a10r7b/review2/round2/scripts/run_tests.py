"""Run the pytest commands of the A10 and A11 specs exactly as apply_entry_stream.py --tests does, but with every log
under /tmp/A10A11/recheck1/tests/ (the project's test logs, which the entries cite, stay untouched); one at a time."""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/home/kang/Desktop/DAC')
PY = str(ROOT / '.conda-unidrive-linux/bin/python')
OUT = Path('/tmp/A10A11/recheck1/tests')
SPECS = (ROOT / 'outputs/framelease_v4/build/AMEND2/final/A10_spec.json',
         ROOT / 'outputs/framelease_v4/build/AMEND2/a10r7b/A11_spec.json')


def summary(text):
    lines = [ln.strip('= ').strip() for ln in text.splitlines() if re.search(r'\d+ (passed|failed|error)', ln)]
    return lines[-1] if lines else ''


OUT.mkdir(parents=True, exist_ok=True)
env = {**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
       'OPENBLAS_NUM_THREADS': '1'}
ok = True
for sp in SPECS:
    spec = json.loads(sp.read_text())
    for t in spec['tests']:
        log = OUT / Path(t['log']).name
        t0 = time.time()
        r = subprocess.run(['taskset', '-c', '12-15', 'nice', '-n', '19', 'ionice', '-c', '3', PY, '-I', '-B', '-m',
                            'pytest', '-q', '-p', 'no:cacheprovider', '-rA'] + t['argv'], cwd=ROOT, capture_output=True,
                           text=True, env=env)
        log.write_text(r.stdout + r.stderr, encoding='utf-8')
        proj = ROOT / t['log']
        ps = summary(proj.read_text(errors='replace')) if proj.is_file() else 'missing'
        print(f'{spec["name"]} {log.name}: exit {r.returncode}, {time.time() - t0:.1f} s | now: {summary(r.stdout)} | '
              f'project log: {ps}', flush=True)
        ok = ok and r.returncode == 0
sys.exit(0 if ok else 1)
