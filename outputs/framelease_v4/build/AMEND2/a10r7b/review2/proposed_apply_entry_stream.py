"""Apply one PROTOCOL Sec. 13.2 entry from a template with placeholders (item a10r7b: Amendments A10 and A11).

outputs/framelease_v4/paper_tools/apply_entry.py with the changes of item a10r7b and of its reviews (RUNBOOK.md Sec. 0;
the full diff is apply_entry_stream.diff): sha256 streamed in 1 MiB blocks; the registered files are those of both
drivers' baselines, every manifest file whose sha256 PROTOCOL.md cites and every P1 job file under
outputs/framelease_v4/p1_jobs/ (p1_driver.is_strict); a registered file that differs, is missing or leaves the manifest
stops the application; the template and the filled entry are checked against the line forms of both drivers and the
composed PROTOCOL.md against their parsers; every placeholder has a value before the manifest is rewritten; Beijing
time only, never earlier than the last stamp of Sec. 13.2; filled prose lines at most 120 columns; no leftover
temporary file; no transaction or ALERT file of either driver; --apply only under the protocol lock.

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
in the sealed manifest and equals it on disk; must_equal; every test log ends with no failure; the entry does not exist
yet; every in-place text occurs exactly once when it is applied (in order); the anchor occurs once; the template starts
with the title, holds the anchor phrase nowhere and no further line that a driver reads as an entry, an amendment title
or a heading; every placeholder is known, every {{sha256:...}} file exists (the manifest is written later) and every
{{pytest:...}} log is a test log of the spec; the local time zone is Beijing time (+0800) and the time is not earlier
than the last stamp of Sec. 13.2; a preview of the filled entry passes the line and width checks.
Transaction (--apply, under the protocol lock): write-manifest; no registered file changed or left the new manifest;
fill; every cited manifest file at its new-manifest sha256; the filled entry passes the line and width checks; the
composed PROTOCOL.md parses with p1_driver.protocol_view and phase_driver.phase_view (the entry read once, the drivers'
entries unchanged, each newly registered file first cited by the entry) and registers exactly the unregistered manifest
files the template cites (at most max_new_registered); PROTOCOL.md is unchanged since the pre-check; in-place texts and
the entry are written through the temporary file; seal; verify.
"""
import fcntl
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
LOCK = ROOT / 'framelease_v4/.protocol.lock'
P1_JOBS = 'outputs/framelease_v4/p1_jobs/'                  # P1 job files: always registered (p1_driver.is_strict)
BASELINES = (ROOT / 'outputs/framelease_v4/p1_driver/registered_baseline.json',
             ROOT / 'outputs/framelease_v4/phase_driver/registered_baseline.json')
DRIVER_FILES = tuple(ROOT / 'outputs/framelease_v4' / d / f for d in ('p1_driver', 'phase_driver')
                     for f in ('protocol_txn.json', 'ALERT.txt'))
TMP = PROTO.with_name('.PROTOCOL.md.entrytmp')
ANCHOR = 'Each amendment gets the date and time'
SEC_START = '### 13.2 Amendments'                                                                    # p1_driver
ENTRY_RE = re.compile(r'^\* \*\*(?P<label>[^*]+)\*\*, (?P<when>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \(')      # p1_driver
PHASE_ENTRY_RE = re.compile(r'^\* \*\*(?P<gate>G\d) (?P<label>[^*]+)\*\* \((?P<when>\d{4}-\d{2}-\d{2} \d{2}:\d{2}), ')
AMEND_RE = re.compile(r'^\*\*Amendment (?P<id>A\d+[a-z]?)[,:.]? ')                                   # phase_driver
STAMP_RE = re.compile(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}')
DRIVER_HEADINGS = ('**Stage selections (P1, FULL).**', '**Phase gates (P2-P7, FULL).**')
PLACEHOLDER = re.compile(r'\{\{([^}]+)\}\}')
WIDTH = 120


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
    """Lines after the title that a driver would read as an entry, an amendment title or a heading; prose lines over
    WIDTH columns (table rows excepted)."""
    return [ln for ln in entry_text.splitlines()[1:] if ln.startswith(('## ', ANCHOR)) or ENTRY_RE.match(ln)
            or PHASE_ENTRY_RE.match(ln) or AMEND_RE.match(ln) or ln.strip() in DRIVER_HEADINGS + (SEC_START,)] + \
        [ln for ln in entry_text.splitlines() if len(ln) > WIDTH and not ln.lstrip().startswith('|')]


def last_stamp(text):
    """The latest 'YYYY-MM-DD HH:MM' of an entry head or amendment title in Sec. 13.2."""
    lines = text.split('\n')
    s = next(i for i, ln in enumerate(lines) if ln.strip() == SEC_START)
    stamps = []
    for ln in lines[s + 1:]:
        if ln.startswith('## '):
            break
        if AMEND_RE.match(ln) or ENTRY_RE.match(ln) or PHASE_ENTRY_RE.match(ln):
            m = STAMP_RE.search(ln)
            if m:
                stamps.append(m.group(0))
    return max(stamps) if stamps else ''


def lock_held():
    """True when this process holds framelease_v4/.protocol.lock through a descriptor it inherited from flock(1) in
    apply_locked.sh (the drivers lock the same file with fcntl.flock)."""
    want = os.path.realpath(LOCK)
    for fd in os.listdir('/proc/self/fd'):
        try:
            if os.path.realpath(f'/proc/self/fd/{fd}') == want:
                fcntl.flock(int(fd), fcntl.LOCK_EX | fcntl.LOCK_NB)   # the same open file: succeeds only for the holder
                return True
        except OSError:
            continue
    return False


def parse_problems(old_text, new_text, name, new_files):
    """The composed PROTOCOL.md read by the drivers' own parsers."""
    sys.path.insert(0, str(ROOT))
    sys.dont_write_bytecode = True
    from framelease_v4.protocol import p1_driver as P1     # noqa: E402
    from framelease_v4.protocol import phase_driver as PD  # noqa: E402
    try:
        pv0, v0 = P1.protocol_view(None, old_text), PD.phase_view(None, old_text)
        pv1, v1 = P1.protocol_view(None, new_text), PD.phase_view(None, new_text)
    except Exception as exc:  # noqa: BLE001  (p1_driver.Alert: a broken Sec. 13.2)
        return [f'{type(exc).__name__}: {exc}']
    probs = []
    if len(v1['amendments'].get(name, [])) != 1:
        probs.append(f'{name} read at lines {v1["amendments"].get(name)}')
    others = {a: len(v) for a, v in v1['amendments'].items() if a != name}
    if others != {a: len(v) for a, v in v0['amendments'].items()}:
        probs.append('the other amendment titles changed')
    for key, a, b in (('P1', pv0, pv1), ('phase', v0, v1)):
        if {k: e['text'] for k, e in a['entries'].items()} != {k: e['text'] for k, e in b['entries'].items()}:
            probs.append(f'the {key} driver entries changed')
    s, e = v1['sec']
    for path, h in new_files.items():
        line = next((i + 1 for i in range(s, e) if h in v1['lines'][i]), None)
        owner = PD.citing_amendment(v1, line) if line else None
        if owner != name:
            probs.append(f'{path} is first cited in Sec. 13.2 by {owner}, not {name}')
    return probs


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
if mode == '--apply' and not lock_held():
    die(f'--apply runs only under {LOCK.relative_to(ROOT)} (apply_locked.sh holds it for the whole application)')
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
registered |= {k for k in sealed if k.startswith(P1_JOBS)}      # p1_driver.is_strict (both drivers)
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
probe = text
for r in spec.get('inplace', []):
    if probe.count(r['old']) != 1:
        die(f'in-place text found {probe.count(r["old"])} times: {r["old"][:80]!r}')
    probe = probe.replace(r['old'], r['new'])
if text.count(ANCHOR) != 1 or probe.count(ANCHOR) != 1:
    die('anchor not unique')
tmpl = Path(ROOT / spec['template']).read_text(encoding='utf-8').strip('\n') + '\n'
bad = [ln for ln in line_problems(tmpl) if PLACEHOLDER.search(ln) is None or len(ln) <= WIDTH]
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
if time.strftime('%Y-%m-%d %H:%M') < last_stamp(text):
    die(f'the time {time.strftime("%Y-%m-%d %H:%M")} is earlier than the last stamp of Sec. 13.2 ({last_stamp(text)})')
cited_paths = sorted({k.split(':', 1)[1] for k in PLACEHOLDER.findall(tmpl) if k.startswith('sha256:')} - {MAN_REL})


def filled(shas, n_files):
    def sub(m):
        key = m.group(1)
        if key == 'datetime':
            return time.strftime('%Y-%m-%d %H:%M')
        if key == 'manifest:files':
            return str(n_files)
        if key.startswith('sha256:'):
            return shas[key.split(':', 1)[1]]
        if key.startswith('pytest:'):
            return pytest_summary(ROOT / key.split(':', 1)[1])
        raise KeyError(key)
    return PLACEHOLDER.sub(sub, tmpl)


preview = filled({**{p: sha(ROOT / p) for p in cited_paths}, MAN_REL: sha(MAN)}, len(sealed))
bad = line_problems(preview)
if bad or ANCHOR in preview:
    die(f'filled entry (preview) problem: {bad[:3]} / anchor phrase {preview.count(ANCHOR)} times')
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
shas = {p: sha(ROOT / p) for p in cited_paths}
stale = [p for p in cited_paths if p in new_man and shas[p] != new_man[p]]
if stale:
    die(f'cited files changed after --write-manifest (the entry would cite another sha256 than the manifest): {stale}')
shas[MAN_REL] = sha(MAN)
if time.strftime('%Y-%m-%d %H:%M') < last_stamp(text):
    die(f'the time {time.strftime("%Y-%m-%d %H:%M")} is earlier than the last stamp of Sec. 13.2 ({last_stamp(text)})')
entry = filled(shas, len(new_man))
if '{{' in entry:
    die('unfilled placeholder')
bad = line_problems(entry)
if bad or ANCHOR in entry:
    die(f'filled entry problem: {bad[:3]} / anchor phrase {entry.count(ANCHOR)} times')
cur = text
for r in spec.get('inplace', []):
    cur = cur.replace(r['old'], r['new'])
k = cur.index(ANCHOR)
cur = cur[:k].rstrip('\n') + '\n\n' + entry + '\n' + cur[k:]
cited_new = sorted(k for k, v in new_man.items() if k not in registered and v in cur)  # what refresh_baseline adds
want_new = sorted(p for p in cited_paths if p in new_man and p not in registered)
if cited_new != want_new or len(cited_new) > spec.get('max_new_registered', 0):
    die(f'the composed PROTOCOL.md would register {cited_new}, the template cites {want_new} (at most '
        f'{spec.get("max_new_registered", 0)})')
probs = parse_problems(text, cur, spec['name'], {p: new_man[p] for p in cited_new})
if probs:
    die(f'the composed PROTOCOL.md as the drivers read it: {probs}')
if PROTO.read_text(encoding='utf-8') != text:
    die('PROTOCOL.md changed during the transaction')
mode_bits = PROTO.stat().st_mode & 0o7777
try:
    with open(TMP, 'w', encoding='utf-8') as fh:
        fh.write(cur)
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(TMP, mode_bits)
    os.replace(TMP, PROTO)
except BaseException:
    TMP.unlink(missing_ok=True)
    raise
p = reg('--seal')
if p.returncode != 0:
    die('seal failed: PROTOCOL.md holds the entry but is not sealed (apply_locked.sh seals or rolls back)')
p = reg('--verify')
print('PROTOCOL', sha(PROTO), 'MANIFEST', sha(MAN), len(new_man), 'files; newly cited manifest files:', cited_new)
added, removed = sorted(set(new_man) - set(sealed)), sorted(set(sealed) - set(new_man))
print('manifest: new', added, '/ left', removed, '/ changed',
      sorted(k for k in new_man if k in sealed and new_man[k] != sealed[k]))
print(entry)
