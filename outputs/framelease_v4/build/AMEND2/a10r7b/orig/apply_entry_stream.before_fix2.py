"""Apply one PROTOCOL Sec. 13.2 entry from a template with placeholders (item a10r7b: Amendments A10 and A11).

outputs/framelease_v4/paper_tools/apply_entry.py with the changes of item a10r7b and of its review (RUNBOOK.md Sec. 0;
the full diff is apply_entry_stream.diff): sha256 streamed in 1 MiB blocks; the registered files are those of both
drivers' baselines and every manifest file whose sha256 PROTOCOL.md cites; a registered file that differs, is missing
or leaves the manifest stops the application; the template and the filled entry are checked against the line forms of
both drivers; every placeholder has a value before the manifest is rewritten; Beijing time only; no leftover
temporary file; no transaction or ALERT file of either driver.

  cd /home/kang/Desktop/DAC
  .conda-unidrive-linux/bin/python -I -B outputs/framelease_v4/build/AMEND2/a10r7b/apply_entry_stream.py SPEC --tests
  .conda-unidrive-linux/bin/python -I -B outputs/framelease_v4/build/AMEND2/a10r7b/apply_entry_stream.py SPEC
  bash outputs/framelease_v4/build/AMEND2/a10r7b/apply_locked.sh SPEC OUTDIR      # --apply under the protocol lock

SPEC.json: {"name": "A10", "template": <path of a file holding exactly the entry text with {{...}} placeholders>,
            "tests": [{"log": <path>, "argv": [...pytest args after 'pytest -q -p no:cacheprovider'...]}],
            "inplace": [{"old": <exact text>, "new": <text>}], "must_equal": {<path>: <sha256>},
            "max_new_registered": 8}
Placeholders: {{datetime}}, {{sha256:<path>}}, {{pytest:<log>}}, {{manifest:files}}. The entry goes before the paragraph
"Each amendment gets the date and time" as its own block.
Pre-checks (check mode and --apply; nothing is written before all pass): no framelease_v4/.PROTOCOL.md.entrytmp; no
protocol_txn.json or ALERT.txt of the P1 stage driver or the phase driver; the seal verifies; every registered file is
in the sealed manifest and equals it on disk (registered: the files of p1_driver/ and phase_driver/
registered_baseline.json and every manifest file whose sha256 PROTOCOL.md cites, the rule of
phase_driver.refresh_baseline); must_equal; every test log ends with no failure; the entry does not exist yet; every
in-place text occurs exactly once; the anchor occurs once; the template starts with the title, holds the anchor phrase
nowhere and no further line that a driver reads as an entry, an amendment title or a heading; every placeholder is
known, every {{sha256:...}} file exists (the manifest is written later) and every {{pytest:...}} log is a test log of
the spec; the local time zone is Beijing time (+0800).
Transaction (--apply): write-manifest; no registered file changed or left the new manifest; fill; the filled entry
passes the line checks; it cites the sha256 of at most max_new_registered unregistered manifest files; PROTOCOL.md is
unchanged since the pre-check; in-place texts and the entry are written through the temporary file; seal; verify.
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
MAN_REL = 'outputs/framelease_v4/registration/MANIFEST.sha256'
BASELINES = (ROOT / 'outputs/framelease_v4/p1_driver/registered_baseline.json',
             ROOT / 'outputs/framelease_v4/phase_driver/registered_baseline.json')
DRIVER_FILES = tuple(ROOT / 'outputs/framelease_v4' / d / f for d in ('p1_driver', 'phase_driver')
                     for f in ('protocol_txn.json', 'ALERT.txt'))
TMP = PROTO.with_name('.PROTOCOL.md.entrytmp')
ANCHOR = 'Each amendment gets the date and time'
ENTRY_RE = re.compile(r'^\* \*\*(?P<label>[^*]+)\*\*, (?P<when>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \(')      # p1_driver
PHASE_ENTRY_RE = re.compile(r'^\* \*\*(?P<gate>G\d) (?P<label>[^*]+)\*\* \((?P<when>\d{4}-\d{2}-\d{2} \d{2}:\d{2}), ')
AMEND_RE = re.compile(r'^\*\*Amendment (?P<id>A\d+[a-z]?)[,:.]? ')                                   # phase_driver
DRIVER_HEADINGS = ('**Stage selections (P1, FULL).**', '**Phase gates (P2-P7, FULL).**')
PLACEHOLDER = re.compile(r'\{\{([^}]+)\}\}')


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


def line_problems(entry_text):
    """Lines after the title that a driver would read as an entry, an amendment title or a heading."""
    return [ln for ln in entry_text.splitlines()[1:] if ln.startswith(('## ', ANCHOR)) or ENTRY_RE.match(ln)
            or PHASE_ENTRY_RE.match(ln) or AMEND_RE.match(ln) or ln.strip() in DRIVER_HEADINGS]


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
if TMP.exists():
    die(f'{TMP.relative_to(ROOT)} exists: the temporary file of an interrupted application (RUNBOOK.md Sec. 1)')
for f in DRIVER_FILES:
    if f.exists():
        die(f'{f.relative_to(ROOT)} exists')
p = reg('--verify')
if p.stdout.count('seal framelease_v4/PROTOCOL.md: OK') != 1 or 'MANIFEST.sha256: OK' not in p.stdout:
    die('the seal does not verify')
text = PROTO.read_text(encoding='utf-8')
sealed = manifest()
registered = set()
for b in BASELINES:
    if not b.is_file():
        die(f'{b.relative_to(ROOT)} is missing: the registered files cannot be determined')
    registered |= set(json.loads(b.read_text())['files'])
registered |= {k for k, v in sealed.items() if v in text}       # cited by PROTOCOL.md (phase_driver.refresh_baseline)
absent = sorted(registered - set(sealed))
if absent:
    die(f'registered files absent from the sealed manifest: {absent}')
reg_differ = [k for k, v in sealed.items() if k in registered and (not (ROOT / k).is_file() or sha(ROOT / k) != v)]
if reg_differ:
    die(f'registered files differ from the sealed manifest or are missing: {reg_differ}')
for path, want in spec.get('must_equal', {}).items():
    if not (ROOT / path).is_file() or sha(ROOT / path) != want:
        die(f'{path} is not {want}')
for t in spec['tests']:
    s = pytest_summary(ROOT / t['log']) if (ROOT / t['log']).is_file() else ''
    if not s or 'failed' in s or 'error' in s:
        die(f'test log {t["log"]}: {s!r}')
title = f'**Amendment {spec["name"]},'
if title in text:
    die(f'an entry "{title}" exists already')
for r in spec.get('inplace', []):
    if text.count(r['old']) != 1:
        die(f'in-place text found {text.count(r["old"])} times: {r["old"][:80]!r}')
if text.count(ANCHOR) != 1:
    die('anchor not unique')
tmpl = Path(ROOT / spec['template']).read_text(encoding='utf-8').strip('\n') + '\n'
bad = line_problems(tmpl)
if bad or not tmpl.startswith(title) or ANCHOR in tmpl:
    die(f'template problem: {bad[:3]} / starts {tmpl[:40]!r} / anchor phrase {tmpl.count(ANCHOR)} times')
logs = {t['log'] for t in spec['tests']}
unfilled = [k for k in PLACEHOLDER.findall(tmpl) if not (
    k in ('datetime', 'manifest:files') or (k.startswith('pytest:') and k.split(':', 1)[1] in logs)
    or (k.startswith('sha256:') and (k.split(':', 1)[1] == MAN_REL or (ROOT / k.split(':', 1)[1]).is_file())))]
if unfilled:
    die(f'placeholders without a value (unknown kind, missing file, or a test log the spec does not run): {unfilled}')
if time.strftime('%z') != '+0800':
    die(f'the local time zone is UTC{time.strftime("%z")}, not Beijing time (+0800), which the entry states')
if mode != '--apply':
    print('check: pre-checks passed')
    sys.exit(0)

# ---------------------------------------------------------------------------------------------- transaction
p = reg('--write-manifest', '--force')
if p.returncode != 0:
    die('write-manifest failed (nothing else changed; the next seal rewrites it)')
new_man = manifest()
changed = sorted(k for k in registered if k in sealed and new_man.get(k) != sealed[k])
if changed:
    die(f'registered files changed or left the new manifest: {changed}')
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


entry = PLACEHOLDER.sub(sub, tmpl)
if '{{' in entry:
    die('unfilled placeholder')
bad = line_problems(entry)
if bad or ANCHOR in entry:
    die(f'filled entry problem: {bad[:3]} / anchor phrase {entry.count(ANCHOR)} times')
cited_new = [k for k, v in new_man.items() if k not in registered and v in entry]
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
try:
    TMP.write_text(cur, encoding='utf-8')
    os.chmod(TMP, mode_bits)
    os.replace(TMP, PROTO)
except BaseException:
    TMP.unlink(missing_ok=True)
    raise
p = reg('--seal')
if p.returncode != 0:
    die('seal failed: PROTOCOL.md holds the entry but is not sealed; seal by hand')
p = reg('--verify')
print('PROTOCOL', sha(PROTO), 'MANIFEST', sha(MAN), len(new_man), 'files; newly cited manifest files:', cited_new)
print(entry)
