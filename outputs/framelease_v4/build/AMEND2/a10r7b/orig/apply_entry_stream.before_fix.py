"""Apply one PROTOCOL Sec. 13.2 entry that installs no file (e.g. Amendments A5, A8), from a template with placeholders.

  cd /home/kang/Desktop/DAC
  .conda-unidrive-linux/bin/python -I -B outputs/framelease_v4/paper_tools/apply_entry.py SPEC.json --tests   # no lock
  flock -w 600 framelease_v4/.protocol.lock .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/paper_tools/apply_entry.py SPEC.json --apply

SPEC.json: {"name": "A5", "template": <path of a file holding exactly the entry text with {{...}} placeholders>,
            "tests": [{"log": <path>, "argv": [...pytest args after 'pytest -q -p no:cacheprovider'...]}],
            "inplace": [{"old": <exact text>, "new": <text>}], "must_equal": {<path>: <sha256>},
            "max_new_registered": 0}
Placeholders: {{datetime}}, {{sha256:<path>}}, {{pytest:<log>}}, {{manifest:files}}. The entry goes before the paragraph
"Each amendment gets the date and time" as its own block. Pre-checks: the seal verifies, no registered file (P1 driver
baseline) differs, no driver transaction or ALERT, every in-place text occurs exactly once, every test log ends with
no failure. After write-manifest: no registered file changed. After the seal: verify.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/home/kang/Desktop/DAC')
PY = str(ROOT / '.conda-unidrive-linux/bin/python')
REG = [PY, '-I', '-B', str(ROOT / 'framelease_v4/protocol/registration.py')]
PROTO = ROOT / 'framelease_v4/PROTOCOL.md'
MAN = ROOT / 'outputs/framelease_v4/registration/MANIFEST.sha256'
BASELINE = ROOT / 'outputs/framelease_v4/p1_driver/registered_baseline.json'
ANCHOR = 'Each amendment gets the date and time'
ENTRY_RE = re.compile(r'^\* \*\*(?P<label>[^*]+)\*\*, (?P<when>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \(')


def sha(p):
    h = hashlib.sha256()                    # streamed in 1 MiB blocks (a registered checkpoint has 5.9 GB)
    with open(p, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def reg(*flags):
    p = subprocess.run(REG + list(flags), cwd=ROOT, capture_output=True, text=True)
    print('registration', *flags, '->', p.returncode, '|', p.stdout.strip()[-400:].replace('\n', ' | '))
    return p


def manifest():
    return {ln.split('  ', 1)[1]: ln.split('  ', 1)[0] for ln in MAN.read_text().splitlines() if '  ' in ln}


def die(msg):
    print('STOP:', msg)
    sys.exit(1)


def pytest_summary(log):
    lines = [ln.strip('= ').strip() for ln in Path(log).read_text(errors='replace').splitlines()
             if re.search(r'\d+ (passed|failed|error)', ln)]
    return lines[-1] if lines else ''


spec = json.loads(Path(sys.argv[1]).read_text())
mode = sys.argv[2] if len(sys.argv) > 2 else '--check'

if mode == '--tests':
    env = {**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
           'OPENBLAS_NUM_THREADS': '1'}
    for t in spec['tests']:
        Path(ROOT / t['log']).parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(['taskset', '-c', '12-15', 'nice', '-n', '19', 'ionice', '-c', '3', PY, '-I', '-B', '-m',
                            'pytest', '-q', '-p', 'no:cacheprovider', '-rA'] + t['argv'], cwd=ROOT, capture_output=True,
                           text=True, env=env)
        (ROOT / t['log']).write_text(r.stdout + r.stderr, encoding='utf-8')
        print(t['log'], 'exit', r.returncode, '|', pytest_summary(ROOT / t['log']))
    sys.exit(0)

# ---------------------------------------------------------------------------------------------- pre-checks
p = reg('--verify')
if p.stdout.count('seal framelease_v4/PROTOCOL.md: OK') != 1 or 'MANIFEST.sha256: OK' not in p.stdout:
    die('the seal does not verify')
base = json.loads(BASELINE.read_text())['files']
sealed = manifest()
reg_differ = [k for k, v in sealed.items() if k in base and (ROOT / k).is_file() and sha(ROOT / k) != v]
if reg_differ:
    die(f'registered files differ from the sealed manifest: {reg_differ}')
for f in ('protocol_txn.json', 'ALERT.txt'):
    if (ROOT / 'outputs/framelease_v4/p1_driver' / f).exists():
        die(f'p1_driver/{f} exists')
for path, want in spec.get('must_equal', {}).items():
    if sha(ROOT / path) != want:
        die(f'{path} is not {want}')
for t in spec['tests']:
    s = pytest_summary(ROOT / t['log'])
    if not s or 'failed' in s or 'error' in s:
        die(f'test log {t["log"]}: {s!r}')
text = PROTO.read_text(encoding='utf-8')
title = f'**Amendment {spec["name"]},'
if title in text:
    die(f'an entry "{title}" exists already')
for r in spec.get('inplace', []):
    if text.count(r['old']) != 1:
        die(f'in-place text found {text.count(r["old"])} times: {r["old"][:80]!r}')
if text.count(ANCHOR) != 1:
    die('anchor not unique')
tmpl = Path(ROOT / spec['template']).read_text(encoding='utf-8').strip('\n') + '\n'
bad = [ln for ln in tmpl.splitlines() if ln.startswith(('## ', ANCHOR)) or ENTRY_RE.match(ln)]
if bad or not tmpl.startswith(title):
    die(f'template problem: {bad[:3]} / starts {tmpl[:40]!r}')
if mode != '--apply':
    print('check: pre-checks passed')
    sys.exit(0)

# ---------------------------------------------------------------------------------------------- transaction
p = reg('--write-manifest', '--force')
if p.returncode != 0:
    die('write-manifest failed (nothing else changed; the next seal rewrites it)')
new_man = manifest()
changed = [k for k in base if k in new_man and k in sealed and new_man[k] != sealed[k]]
if changed:
    die(f'registered files changed in the new manifest: {changed}')
fill = {'datetime': time.strftime('%Y-%m-%d %H:%M'), 'manifest:files': str(len(new_man))}


def sub(m):
    key = m.group(1)
    if key in fill:
        return fill[key]
    if key.startswith('sha256:'):
        return sha(ROOT / key.split(':', 1)[1])
    if key.startswith('pytest:'):
        return pytest_summary(ROOT / key.split(':', 1)[1])
    raise KeyError(key)


entry = re.sub(r'\{\{([^}]+)\}\}', sub, tmpl)
if '{{' in entry:
    die('unfilled placeholder')
cited_new = [k for k, v in new_man.items() if k not in base and v in entry]
if len(cited_new) > spec.get('max_new_registered', 0):
    die(f'the entry cites the sha256 of unregistered manifest files (it would register them): {cited_new}')
cur = PROTO.read_text(encoding='utf-8')
if cur != text:
    die('PROTOCOL.md changed during the transaction')
for r in spec.get('inplace', []):
    cur = cur.replace(r['old'], r['new'])
k = cur.index(ANCHOR)
before = cur[:k].rstrip('\n') + '\n\n'
cur = before + entry + '\n' + cur[k:]
mode_bits = PROTO.stat().st_mode & 0o7777
tmp = PROTO.with_name('.PROTOCOL.md.entrytmp')
tmp.write_text(cur, encoding='utf-8')
os.chmod(tmp, mode_bits)
os.replace(tmp, PROTO)
p = reg('--seal')
if p.returncode != 0:
    die('seal failed: PROTOCOL.md holds the entry but is not sealed; seal by hand')
p = reg('--verify')
print('PROTOCOL', sha(PROTO), 'MANIFEST', sha(MAN), len(new_man), 'files; newly cited manifest files:', cited_new)
print(entry)
