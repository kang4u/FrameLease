#!/usr/bin/env python3
"""Step 3 of outputs/framelease_v4/build/AMEND2/APPLY_PLAN2.md Sec. 3: Amendments A3, A9, A7 (A7b), A4 and the
operational addition of the phase driver in ONE transaction (one manifest, one seal). Called by amend_step3.sh, which
takes framelease_v4/.protocol.lock around the subcommand `locked`; every process runs on the E-cores 12-15 at nice 19,
idle I/O class, one BLAS thread, CUDA_VISIBLE_DEVICES=''.

  step3_txn.py precheck  --root R [--work W] [--txn-root T] [--datetime D]   # Sec. 3 step 1 (no lock)
  step3_txn.py locked    --root R --work W --datetime D   # Sec. 3 step 3 (the caller holds the protocol lock)
  step3_txn.py postcheck --root R --work W                # Sec. 3 step 4
  step3_txn.py restore   --root R --work W                # after an interrupted `locked`: back to the sealed state;
                                                          # takes the protocol lock itself (never run it under flock)

Input: step3_spec.json next to this file (make_step3_spec.py): the entries, the in-place texts in their order, the
sha256 of every file the entries cite (must_equal), the reviewed sha256 of the 38 A3 files, the files the transaction
registers. Output: every message is printed and also appended to W/step3_txn.log, which this process writes itself;
when the output pipe breaks (the log process of amend_step3.sh gone), fd 1 and 2 are pointed to /dev/null and the
messages go to W/step3_txn.log only, so that no output error interrupts a restore.

precheck (writes only into W): registration.py --verify (both seal lines OK; a manifest difference only of
unregistered files); the registered baseline and every P1 job file of the sealed manifest (outputs/framelease_v4/
p1_jobs/, always registered: p1_driver.is_strict) unchanged in the tree; P1_DONE.json (schema
framelease_v4.p1_driver_done/1); no p1_driver.py or phase_driver.py process of this root (process table and
driver.lock); no p1_driver/protocol_txn.json, p1_driver/ALERT.txt, phase_driver/ALERT.txt or phase_driver/
protocol_txn.json; no transaction directory under T (default: none) whose journal ended at a step that is neither
sealed nor resolved (an interrupted transaction is resolved by `restore` or, once sealed, by `postcheck`); the P1
driver's "Tuning freeze" and "D1 summary" entries in Sec. 13.2; final/OP_spec.json "must_equal" and the spec's
must_equal; every A3 file at the sha256 its review record gives (APPLY_PLAN.md Sec. 4); no title of A3, A4, A7, A9 or
the operational addition in PROTOCOL.md yet; every in-place "old" exactly once at its turn; check_drafts.py exit 0
("all checks passed"); the time stamp D when given (as in `locked`); a dry run of the whole composition in memory.

locked: under the lock and before any change: the time stamp D ('YYYY-MM-DD HH:MM', Beijing time: a valid date, not
earlier than the latest time stamp of Sec. 13.2, not later than now); none of the five entries and no heading of the
phase driver in PROTOCOL.md (a second run whose pre-check passed before the first one sealed); PROTOCOL.md and
MANIFEST.sha256 the sealed ones; no protocol_txn.json or ALERT.txt of either driver; W on the file system of
PROTOCOL.md; the inputs again (must_equal, OP must_equal, the A3 review record). A failed check stops with journal step
'refused': nothing was changed. Then:
copies of PROTOCOL.md, MANIFEST.sha256, SEAL.sha256 and REGISTRATION.json into W, their sha256 in the journal (the
sealed state); registration.py --write-manifest --force (file count, sha256); the post-manifest check of step 3.2
(every file of p1_driver/registered_baseline.json in the new manifest at its sealed sha256, none vanished; the same
for every P1 job file of the sealed manifest); the five entries filled with ONE time stamp by fill_entry.py (the rules
of apply_entry.py: {{datetime}}, {{sha256:...}}, {{pytest:...}}, {{manifest:files}}) and every block with a filled
line over 120 columns rewrapped (words unchanged; table rows stay single lines); every entry checked (no line that a
driver reads as an entry, a heading, the anchor or another amendment title; the manifest clause cites the new
manifest); the in-place texts applied in their order; the entries inserted, each its own block, directly before the
paragraph "Each amendment gets the date and time" in the order A3, A9, A7, A4, operational addition; the new text
checked with the parsers of both drivers (the P1 entries unchanged; A3, A4, A7 and A9 each read once, A7 read as A7b;
the heading of the phase driver absent; the operational addition once); the manifest files that become registered
(not in the registered baseline, sha256 cited by PROTOCOL.md) exactly the 40 expected ones; PROTOCOL.md written
atomically; the pre-seal check (PROTOCOL.md and MANIFEST.sha256 on disk the composed text and the new manifest; every
file of the registered baseline, every P1 job file and the 40 newly registered files at their new-manifest sha256;
every must_equal file at its prepared sha256); registration.py --seal; registration.py --verify (both seals OK; a
manifest difference only of unregistered files, which the next seal names, as the drivers allow). SIGTERM, SIGINT and
SIGHUP raise a STOP from the start of `locked` until the seal has returned; from then on, and during every restore,
they are ignored. Every failure after the copies (a signal included) restores PROTOCOL.md and MANIFEST.sha256 (and
SEAL.sha256 and REGISTRATION.json if --seal touched them) from the copies whose sha256 the journal holds, and checks
that both seals verify again: nothing is applied. W/journal.json records each step; the journal step comes first,
then the restore, then the messages.

restore (standalone): takes the protocol lock (waits up to --lock-timeout s), then reads the journal (a locked part
that still ran when the command started has ended by then); refuses a journal that ended at 'refused', 'restored',
'sealed', 'verified' or 'verify_not_clean' (nothing to restore, or sealed); proceeds only when PROTOCOL.md is the
sealed copy or the text this transaction composed (and, if it composed and wrote it, the very file it wrote: same
inode and mtime), MANIFEST.sha256 is the sealed copy or the manifest this transaction wrote (or, with no manifest step
journaled, PROTOCOL.md and SEAL.sha256 are the sealed copies), and SEAL.sha256 and REGISTRATION.json are the sealed
copies unless the transaction reached --seal; else STOP, naming the files. It records 'restored' or
'restore_incomplete' in the journal.

postcheck: the command of step 3.2 on the sealed manifest prints OK; every P1 job file of the earlier sealed manifest
at the same sha256 in the new one; registration.py --verify (as above); phase_driver.py --dry-run shows G0 passed and
G1 waiting for D1_DECISION.json; the G5 plan of phase_driver.stress_runs on the sealed PROTOCOL.md holds `s2 --grid
relative` (A7b read from the A7 text); check_drafts.py exit 0 on the new PROTOCOL.md; the Sec. 4.1 status paragraph as
it now reads (the "old" of the fifth A10 in-place text, APPLY_PLAN2.md Sec. 4 step 1).

Simulation (a scratch copy, --root other than the project): check_drafts.py and fill_entry.py hard-code the project
root, so they run with ROOT replaced in memory (the files themselves are unchanged); AMEND_STEP3_FAULT=post_manifest |
before_seal | seal_fail | signal_before_seal (SIGTERM to this process) | kill_before_seal (SIGKILL, then `restore`) |
change_before_preseal (a comment line appended to AMEND_STEP3_FAULT_FILE, a file of the scratch root, before the
pre-seal check) injects a failure at that point; AMEND_STEP3_NOW='YYYY-MM-DD HH:MM' stands for the current time of the
time-stamp check. All three are refused in the project tree.
Exit codes: 0 OK; 1 STOP, nothing applied (journal 'refused': nothing was changed; 'restored': the sealed state is back
and both seals verify); 2 STOP, the restore needs a manual check (journal); 3 STOP after the seal (sealed; a seal line
or a registered file does not verify); 4 a post-check failed (sealed).
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

REAL_ROOT = Path('/home/kang/Desktop/DAC')
HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / 'step3_spec.json'
PREFIX = ['taskset', '-c', '12-15', 'nice', '-n', '19', 'ionice', '-c', '3']
ENV = {**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
       'OPENBLAS_NUM_THREADS': '1'}
ANCHOR = 'Each amendment gets the date and time'
PROTOCOL = 'framelease_v4/PROTOCOL.md'
MANIFEST = 'outputs/framelease_v4/registration/MANIFEST.sha256'
SEAL = 'outputs/framelease_v4/registration/SEAL.sha256'
RECORD = 'outputs/framelease_v4/registration/REGISTRATION.json'
REGISTRATION = 'framelease_v4/protocol/registration.py'
PHASE_DRIVER = 'framelease_v4/protocol/phase_driver.py'
BASELINE = 'outputs/framelease_v4/p1_driver/registered_baseline.json'
LOCK = 'framelease_v4/.protocol.lock'
P1_DIR = 'outputs/framelease_v4/p1_driver'
PD_DIR = 'outputs/framelease_v4/phase_driver'
P1_JOBS = 'outputs/framelease_v4/p1_jobs/'      # always registered (p1_driver.is_strict; phase driver docstring)
FILL = 'outputs/framelease_v4/build/AMEND2/fill_entry.py'
CHECK = 'outputs/framelease_v4/build/AMEND2/check_drafts.py'
OP_SPEC = 'outputs/framelease_v4/build/AMEND2/final/OP_spec.json'
P1_DONE_SCHEMA = 'framelease_v4.p1_driver_done/1'
ROOT_LINE = "ROOT = Path('/home/kang/Desktop/DAC')"
FAULT_ENV = 'AMEND_STEP3_FAULT'
FAULT_FILE_ENV = 'AMEND_STEP3_FAULT_FILE'
NOW_ENV = 'AMEND_STEP3_NOW'
FAULTS = ('post_manifest', 'before_seal', 'seal_fail', 'signal_before_seal', 'kill_before_seal',
          'change_before_preseal')
ORDER = ('A3', 'A9', 'A7', 'A4', 'OP')
TXN_FILES = (f'{P1_DIR}/protocol_txn.json', f'{P1_DIR}/ALERT.txt', f'{PD_DIR}/protocol_txn.json',
             f'{PD_DIR}/ALERT.txt')
TERMINAL = ('refused', 'restored', 'sealed', 'verified', 'verify_not_clean')
SIGNALS = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
BEIJING = dt.timezone(dt.timedelta(hours=8))
STAMP = '%Y-%m-%d %H:%M'
STAMP_RE = re.compile(r'(?<!\d)(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})(?!\d)')
BULLET = re.compile(r'^( *)(\* |\d+\. )')
LIST_LIKE = re.compile(r'^\s*(\d+\)|[-+>#])(\s|$)')
STEP32 = ("import json; b=json.load(open('outputs/framelease_v4/p1_driver/registered_baseline.json'))['files']; "
          "m=dict(reversed(l.rstrip('\\n').split('  ',1)) for l in open('outputs/framelease_v4/registration/"
          "MANIFEST.sha256')); print([k for k,v in b.items() if m.get(k)!=v] or 'OK')")


class Stop(Exception):
    """A failed check: the message names it."""


_OUT = {'log': None, 'dead': False}


def say(msg=''):
    """Print one message and append it to W/step3_txn.log; never raises (module docstring, "Output")."""
    line = str(msg)
    if _OUT['log'] is not None:
        try:
            with open(_OUT['log'], 'a', encoding='utf-8') as fh:
                fh.write(line + '\n')
        except OSError:
            pass
    if _OUT['dead']:
        return
    try:
        print(line, flush=True)
    except (OSError, ValueError):
        _OUT['dead'] = True
        try:
            fd = os.open(os.devnull, os.O_WRONLY)
            os.dup2(fd, 1)
            os.dup2(fd, 2)
            os.close(fd)
        except OSError:
            pass
        if _OUT['log'] is not None:
            try:
                with open(_OUT['log'], 'a', encoding='utf-8') as fh:
                    fh.write(f'(output closed at {time.strftime("%Y-%m-%dT%H:%M:%S%z")}: every later message is in '
                             'this file only)\n')
            except OSError:
                pass


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sys.dont_write_bytecode = True
MS = load_module('make_step3_spec', HERE / 'make_step3_spec.py')


def drivers(root):
    """p1_driver and phase_driver of `root` (imported from it; nothing is written)."""
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from framelease_v4.protocol import p1_driver as P1  # noqa: E402
    from framelease_v4.protocol import phase_driver as PD  # noqa: E402
    if Path(PD.__file__).resolve() != (root / PHASE_DRIVER).resolve():
        raise Stop(f'phase_driver imported from {PD.__file__}, not from {root}')
    return P1, PD


def py(root):
    return str(root / '.conda-unidrive-linux/bin/python')


def run(cmd, root, timeout=3600):
    p = subprocess.run(PREFIX + cmd, cwd=root, capture_output=True, text=True, env=ENV, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def tool_cmd(root, rel, args):
    """check_drafts.py / fill_entry.py of `root`: run as files in the project tree; in a scratch copy with their
    hard-coded ROOT replaced in memory (the file is read, never changed)."""
    script = str(root / rel)
    if root == REAL_ROOT:
        return [py(root), '-I', '-B', script] + list(args)
    loader = ("import sys, pathlib; s, r = sys.argv[1], sys.argv[2]; sys.argv = [s] + sys.argv[3:]; "
              "src = pathlib.Path(s).read_text(encoding='utf-8'); old = " + repr(ROOT_LINE) + "; "
              "assert src.count(old) == 1, 'ROOT line'; src = src.replace(old, 'ROOT = Path(%r)' % r); "
              "g = {'__name__': '__main__', '__file__': s}; exec(compile(src, s, 'exec'), g)")
    return [py(root), '-I', '-B', '-c', loader, script, str(root)] + list(args)


def registration(root, *flags):
    return run([py(root), '-I', '-B', str(root / REGISTRATION)] + list(flags), root)


def seal_lines_ok(out):
    return out.count(f'seal {PROTOCOL}: OK') == 1 and out.count(f'seal {MANIFEST}: OK') == 1


def manifest_map(path):
    out = {}
    for ln in Path(path).read_text(encoding='utf-8').splitlines():
        if '  ' in ln:
            s, rel = ln.split('  ', 1)
            out[rel] = s
    return out


def baseline_files(root):
    doc = json.loads((root / BASELINE).read_text(encoding='utf-8'))
    files = doc.get('files')
    if not isinstance(files, dict) or not files:
        raise Stop(f'{BASELINE} holds no files')
    return files


def tree_sha(root, rel):
    p = Path(rel) if Path(rel).is_absolute() else root / rel
    try:
        return sha256(p)
    except OSError as e:
        return f'unreadable ({e.strerror})'


def driver_pids(root, script):
    """pids of processes that run <root>/framelease_v4/protocol/<script> (argv resolved against their cwd)."""
    target = os.path.realpath(root / 'framelease_v4/protocol' / script)
    pids = []
    for d in os.listdir('/proc'):
        if not d.isdigit() or int(d) == os.getpid():
            continue
        try:
            argv = Path(f'/proc/{d}/cmdline').read_bytes().split(b'\0')
            cwd = os.readlink(f'/proc/{d}/cwd')
        except OSError:
            continue
        for a in argv[1:]:
            a = a.decode(errors='replace')
            if a.endswith(script) and os.path.realpath(a if os.path.isabs(a) else os.path.join(cwd, a)) == target:
                pids.append(int(d))
                break
    return pids


def spec_load():
    spec = json.loads(SPEC_PATH.read_text(encoding='utf-8'))
    if spec.get('schema') != MS.SCHEMA:
        raise Stop(f'{SPEC_PATH}: schema {spec.get("schema")}')
    return spec


def now_beijing():
    """The current time, Beijing time, to the minute (AMEND_STEP3_NOW in a simulation)."""
    if os.environ.get(NOW_ENV):
        return dt.datetime.strptime(os.environ[NOW_ENV], STAMP)
    return dt.datetime.now(BEIJING).replace(tzinfo=None, second=0, microsecond=0)


def datetime_problems(when, view):
    """Problems of the one time stamp of the five entries: a valid 'YYYY-MM-DD HH:MM', not earlier than the latest
    time stamp in Sec. 13.2 (the entries stand in the order of application), not later than now."""
    try:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', when or ''):
            raise ValueError(when)
        t = dt.datetime.strptime(when, STAMP)
    except ValueError:
        return [f"--datetime {when!r} is not a valid time 'YYYY-MM-DD HH:MM' (Beijing time)"]
    s, e = view['sec']
    stamps = []
    for ln in view['lines'][s:e]:
        for d, hm in STAMP_RE.findall(ln):
            try:
                stamps.append(dt.datetime.strptime(f'{d} {hm}', STAMP))
            except ValueError:
                pass
    probs = []
    if stamps and t < max(stamps):
        probs.append(f'--datetime {when} is earlier than the latest time stamp of Sec. 13.2 '
                     f'({max(stamps):{STAMP}}): the entries of Sec. 13.2 stand in the order of application')
    now = now_beijing()
    if t > now:
        probs.append(f'--datetime {when} is later than the current time ({now:{STAMP}}, Beijing time)')
    return probs


# ------------------------------------------------------------------------------------------------ entries

def rewrap(text, width=120):
    """Every paragraph block (a bullet with its continuation lines, or a plain paragraph) that holds a line over
    `width` columns, rewrapped with the same first-line prefix and continuation indent; other lines unchanged."""
    lines = text.rstrip('\n').split('\n')
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip() or ln.lstrip().startswith('|'):
            out.append(ln)
            i += 1
            continue
        m = BULLET.match(ln)
        ind = len(m.group(0)) if m else len(ln) - len(ln.lstrip(' '))
        j = i + 1
        while j < len(lines) and lines[j].strip() and not lines[j].lstrip().startswith('|') \
                and not BULLET.match(lines[j]) and len(lines[j]) - len(lines[j].lstrip(' ')) == ind:
            j += 1
        blk = lines[i:j]
        if any(len(x) > width for x in blk):
            blk = MS.wrap(' '.join([ln[ind:]] + [x.strip() for x in blk[1:]]), ln[:ind], ' ' * ind, width)
        out.extend(blk)
        i = j
    return '\n'.join(out) + '\n'


def entry_problems(P1, PD, name, aid, text, op_mark, m_sha, n_files):
    """Problems of one filled entry (module docstring)."""
    out = []
    lines = text.rstrip('\n').split('\n')
    for k, ln in enumerate(lines, 1):
        if len(ln) > 120 and not ln.lstrip().startswith('|'):
            out.append(f'{name}: line {k} has {len(ln)} columns')
        if ln.startswith('## ') or ln.startswith(ANCHOR) or ln.strip() in (P1.HEADING, PD.HEADING):
            out.append(f'{name}: line {k} starts with a heading or the anchor')
        if P1.ENTRY_RE.match(ln) or PD.ENTRY_RE.match(ln):
            out.append(f'{name}: line {k} reads as a driver entry')
        if PD.AMEND_RE.match(ln) and not (aid and k == 1):
            out.append(f'{name}: line {k} reads as an amendment title')
        if LIST_LIKE.match(ln) or (re.match(r'^\s*\d+\.\s', ln) and not ln.startswith('  ')):
            out.append(f'{name}: line {k} starts like a list item, a quote or a heading')
    first = PD.AMEND_RE.match(lines[0])
    if aid and (not first or first.group('id') != aid):
        out.append(f'{name}: the first line is not the title of Amendment {aid}')
    if not aid and op_mark not in lines[0] + ' ' + (lines[1] if len(lines) > 1 else ''):
        out.append(f'{name}: the title of the operational addition is missing')
    if not aid and PD.A7B_RE.search(' '.join(text.split())):
        out.append(f'{name}: the text matches phase_driver.A7B_RE')
    if ANCHOR in text or '{{' in text or '}}' in text:
        out.append(f'{name}: anchor phrase or unfilled placeholder in the text')
    flat = ' '.join(text.split())
    if f'`MANIFEST.sha256`, {n_files} files, sha256 `{m_sha}`, sealed with this entry.' not in flat:
        out.append(f'{name}: the manifest-and-seal line does not cite {n_files} files, sha256 {m_sha}')
    return out


def fill_entries(root, spec, work, when, P1, PD, m_sha, n_files, tag=''):
    """{name: filled and rewrapped entry}; each template, raw fill and entry written into `work`."""
    entries, problems = {}, []
    for e in spec['entries']:
        name, aid = e['name'], e['amendment']
        tmpl = work / f'template_{name}{tag}.md'
        tmpl.write_text(MS.entry_template(root, name), encoding='utf-8')
        rc, out, err = run(tool_cmd(root, FILL, [str(tmpl), '--datetime', when]), root, 600)
        (work / f'fill_{name}{tag}.stderr.txt').write_text(err, encoding='utf-8')
        if rc != 0:
            problems.append(f'{name}: fill_entry.py exit {rc}: {err.strip()[-600:]}')
            continue
        (work / f'filled_{name}{tag}.raw.md').write_text(out, encoding='utf-8')
        text = rewrap(out)
        (work / f'entry_{name}{tag}.md').write_text(text, encoding='utf-8')
        if ' '.join(text.split()) != ' '.join(out.split()):
            problems.append(f'{name}: the rewrap changed words')
        problems += entry_problems(P1, PD, name, aid, text, spec['op_title_mark'], m_sha, n_files)
        if aid and not text.startswith(f'**Amendment {aid}, {when} (Beijing time):'):
            problems.append(f'{name}: the title does not carry the time stamp {when}')
        if not aid and not text.startswith(f'**Operational addition, {when} (Beijing time):'):
            problems.append(f'{name}: the title does not carry the time stamp {when}')
        entries[name] = text
    return entries, problems


def compose(P1, PD, spec, text, entries):
    """(new PROTOCOL.md text, problems): the in-place texts in order, then the entries before the anchor."""
    problems = []
    if text.count(ANCHOR) != 1:
        return None, [f'the anchor phrase occurs {text.count(ANCHOR)} times in PROTOCOL.md']
    p1_before = {k: v['text'] for k, v in P1.protocol_view(None, text)['entries'].items()}
    try:
        new = MS.apply_inplace(text, spec['inplace'])
    except ValueError as e:
        return None, [str(e)]
    for name in ORDER:
        k = new.index(ANCHOR)
        new = new[:k].rstrip('\n') + '\n\n' + entries[name].strip('\n') + '\n\n' + new[k:]
    try:
        pv = P1.protocol_view(None, new)
        view = PD.phase_view(None, new)
    except Exception as exc:             # an ALERT of either driver's parser
        return new, [f'driver parser on the new text: {type(exc).__name__}: {exc}']
    if {k: v['text'] for k, v in pv['entries'].items()} != p1_before:
        problems.append('the P1 driver entries changed')
    for aid in ('A3', 'A4', 'A7', 'A9'):
        if len(view['amendments'].get(aid, [])) != 1:
            problems.append(f'Amendment {aid} read {len(view["amendments"].get(aid, []))} times')
    if view['heading'] is not None or view['entries']:
        problems.append('the phase driver heading or a phase driver entry exists already')
    if not PD.a7_supplementary(view):
        problems.append('the entered A7 is not read as the variant A7b (phase_driver.a7_supplementary)')
    s, e = view['sec']
    if sum(spec['op_title_mark'] in view['lines'][i] for i in range(s, e)) != 1:
        problems.append('the operational addition is not read exactly once in Sec. 13.2')
    if new.count(ANCHOR) != 1:
        problems.append('the anchor phrase is not unique after the insertion')
    return new, problems


def verify_classified(root, registered):
    """registration.py --verify, with the differing manifest files split into registered ones (in `registered`, or a
    P1 job file) and the others (unregistered development files: tolerated, named at the next seal, as the drivers
    do). Returns (seal lines OK, registered differences, other differences, output)."""
    rc, out, err = registration(root, '--verify')
    if 'manifest: OK' in out:
        return seal_lines_ok(out), [], [], out
    diffs = []
    for p, s in manifest_map(root / MANIFEST).items():
        got = tree_sha(root, p)
        if got != s:
            diffs.append(p)
    strict = [p for p in diffs if p in registered or p.startswith(P1_JOBS)]
    return seal_lines_ok(out), strict, [p for p in diffs if p not in strict], out


def registered_by(old_text, new_text, man, base):
    """Manifest files the transaction registers: outside the registered baseline and the P1 job files, with a sha256
    that the new PROTOCOL.md cites and the sealed one does not (the rule of phase_driver.refresh_baseline)."""
    return sorted(k for k, v in man.items()
                  if k not in base and not k.startswith(P1_JOBS) and v in new_text and v not in old_text)


def p1_job_check(old_man, new_man):
    """(P1 job files of the earlier sealed manifest that the new manifest lacks or holds at another sha256, P1 job
    files new in it): the post-manifest check of the P1 job files (p1_driver.is_strict)."""
    bad = sorted(k for k, v in old_man.items() if k.startswith(P1_JOBS) and new_man.get(k) != v)
    new = sorted(k for k in new_man if k.startswith(P1_JOBS) and k not in old_man)
    return bad, new


# ------------------------------------------------------------------------------------------------ precheck

def check_inputs(root, spec):
    probs = []
    op_spec = json.loads((root / OP_SPEC).read_text(encoding='utf-8'))
    for p, want in sorted({**op_spec['must_equal'], **spec['must_equal']}.items()):
        have = tree_sha(root, p)
        if have != want:
            probs.append(f'{p}: sha256 {have[:16]} != {want[:16]} (prepared / OP_spec.json): the file changed after '
                         'the preparation; a changed file carries its review, then make_step3_spec.py is run again')
    want_a3 = MS.a3_reviewed(root)
    if want_a3 != spec['a3_files']:
        probs.append('the A3 review record of the AMEND draft differs from step3_spec.json')
    for p, want in sorted(want_a3.items()):
        if tree_sha(root, p) != want:
            probs.append(f'A3 file {p} is not at the sha256 of its review record ({want[:16]})')
    return probs


def open_transactions(txn_root, work):
    """Transaction directories under `txn_root` (other than the current one) whose journal ended at a step that is
    neither sealed nor resolved."""
    out = []
    if txn_root is None or not Path(txn_root).is_dir():
        return out
    for j in sorted(Path(txn_root).glob('*/journal.json')):
        if work is not None and j.parent.resolve() in (Path(work).resolve(), Path(work).resolve().parent):
            continue
        try:
            step = json.loads(j.read_text(encoding='utf-8')).get('step')
        except (OSError, ValueError):
            step = 'unreadable journal'
        if step not in TERMINAL:
            out.append(f'{j.parent} (journal step {step!r})')
    return out


def precheck(root, spec, work, txn_root=None, when=None):
    P1, PD = drivers(root)
    probs, notes = [], []
    rc, out, err = registration(root, '--verify')
    say(f'registration.py --verify (exit {rc}): ' + ' | '.join(out.strip().splitlines()))
    if not seal_lines_ok(out):
        probs.append('registration.py --verify: the two seal lines are not both OK')
    base = baseline_files(root)
    sealed = manifest_map(root / MANIFEST)
    reg_diff = [p for p, s in base.items() if sealed.get(p) != s or tree_sha(root, p) != s]
    if reg_diff:
        probs.append(f'registered files differ from the sealed manifest or the tree: {reg_diff[:10]}')
    say(f'registered baseline: {len(base)} files; in the sealed manifest at their sha256 and unchanged in the tree: '
        f'{"yes" if not reg_diff else "NO"}')
    jobs = {p: s for p, s in sealed.items() if p.startswith(P1_JOBS)}
    jobs_diff = [p for p, s in sorted(jobs.items()) if tree_sha(root, p) != s]
    if jobs_diff:
        probs.append(f'P1 job files (always registered, p1_driver.is_strict) differ from the sealed manifest: '
                     f'{jobs_diff[:10]}')
    say(f'P1 job files: {len(jobs)} in the sealed manifest; unchanged in the tree: {"yes" if not jobs_diff else "NO"}')
    done = P1.read_json(root / P1_DIR / 'P1_DONE.json')
    if not (root / P1_DIR / 'P1_DONE.json').is_file():
        probs.append(f'{P1_DIR}/P1_DONE.json does not exist (P1 has not ended)')
    elif not isinstance(done, dict) or done.get('schema') != P1_DONE_SCHEMA:
        probs.append(f'{P1_DIR}/P1_DONE.json is not a P1 completion record ({P1_DONE_SCHEMA})')
    for script in ('p1_driver.py', 'phase_driver.py'):
        pids = driver_pids(root, script)
        if pids:
            probs.append(f'{script} of this root is alive: pids {pids}')
    cfg = PD.Cfg(PD.parse_args(['--root', str(root), '--dry-run']))
    if PD.p1_driver_alive(cfg):
        probs.append(f'{P1_DIR}/driver.lock names a live p1_driver.py process')
    for rel in TXN_FILES:
        if (root / rel).exists():
            probs.append(f'{rel} exists')
    for t in open_transactions(txn_root, work):
        probs.append(f'an interrupted step-3 transaction is not resolved: {t}; run `step3_txn.py restore` on it '
                     '(before its seal) or `step3_txn.py postcheck` (sealed) first')
    text = (root / PROTOCOL).read_text(encoding='utf-8')
    view = PD.phase_view(None, text)
    miss = [P1.LABEL[k] for k in ('freeze', 'd1') if k not in view['p1_entries']]
    if miss:
        probs.append(f'Sec. 13.2 has no P1 driver entry {miss}')
    else:
        d1 = cfg.d1_paths()[0]
        jsha = tree_sha(root, d1)
        say(f'P1 driver entries: Tuning freeze line {view["p1_entries"]["freeze"]["line"]}, D1 summary line '
            f'{view["p1_entries"]["d1"]["line"]}; {cfg.rel(d1)} sha256 {jsha} '
            f'{"cited by the D1 summary entry" if jsha in view["p1_entries"]["d1"]["shas"] else "NOT CITED"}')
        if jsha not in view['p1_entries']['d1']['shas']:
            probs.append(f'the D1 summary entry does not cite the sha256 of {cfg.rel(d1)}')
    if when is not None:
        dprobs = datetime_problems(when, view)
        probs += dprobs
        say(f'time stamp {when}: {"valid" if not dprobs else "NOT valid"}')
    for aid in ('A3', 'A4', 'A7', 'A9'):
        if aid in view['amendments']:
            probs.append(f'Amendment {aid} is entered already (lines {view["amendments"][aid]})')
    if spec['op_title_mark'] in text:
        probs.append('the operational addition of the phase driver is entered already')
    if view['heading'] is not None:
        probs.append(f'the heading {PD.HEADING} exists already')
    probs += check_inputs(root, spec)
    try:
        MS.apply_inplace(text, spec['inplace'])
    except ValueError as e:
        probs.append(str(e))
    rc, out, err = run(tool_cmd(root, CHECK, []), root, 600)
    say(f'check_drafts.py exit {rc}: {out.strip().splitlines()[-1] if out.strip() else err.strip()[-300:]}')
    if rc != 0 or 'all checks passed' not in out:
        probs.append(f'check_drafts.py exit {rc}: ' + ' | '.join(out.strip().splitlines()[-6:]))
    # dry composition with the current manifest (nothing written outside `work`)
    m_sha, n_files = sha256(root / MANIFEST), len(sealed)
    entries, fprobs = fill_entries(root, spec, work, '2000-01-01 00:00', P1, PD, m_sha, n_files, tag='.dry')
    probs += [f'dry fill: {p}' for p in fprobs]
    if not fprobs:
        new, cprobs = compose(P1, PD, spec, text, entries)
        probs += [f'dry composition: {p}' for p in cprobs]
        if new is not None and not cprobs:
            got = registered_by(text, new, sealed, base)
            if got != spec['expected_new_registered']:
                probs.append(f'dry composition registers {len(got)} files, expected '
                             f'{len(spec["expected_new_registered"])}: '
                             f'{sorted(set(got) ^ set(spec["expected_new_registered"]))[:10]}')
            say(f'dry composition: {len(new.splitlines())} lines; entries '
                + ', '.join(f'{n} {len(entries[n].splitlines())} lines' for n in ORDER)
                + f'; {len(got)} files become registered')
    for n in notes:
        say(n)
    return probs


# ------------------------------------------------------------------------------------------------ locked part

class Txn:
    """The journal W/journal.json (rewritten atomically after each step)."""

    def __init__(self, root, work, state=None):
        self.work = work
        self.journal = work / 'journal.json'
        self.state = state or {'root': str(root), 'started': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'steps': []}

    def step(self, name, **kw):
        self.state['step'] = name
        self.state['steps'].append({'step': name, 'time': time.strftime('%Y-%m-%dT%H:%M:%S%z'), **kw})
        tmp = self.journal.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.state, indent=1) + '\n', encoding='utf-8')
        os.replace(tmp, self.journal)

    def safe_step(self, name, **kw):
        """step() on a failure path: an error writing the journal never prevents the restore."""
        try:
            self.step(name, **kw)
        except Exception as e:                   # noqa: BLE001 (any error: the journal is best effort here)
            say(f'note: the journal step {name!r} could not be written ({type(e).__name__}: {e})')

    def record(self, name):
        return next((s for s in reversed(self.state.get('steps', [])) if s.get('step') == name), None)


def atomic_copy(src, dst, work, mode=None):
    tmp = work / f'.restore_{Path(dst).name}.tmp'
    shutil.copyfile(src, tmp)
    if mode is not None:
        os.chmod(tmp, mode)
    os.replace(tmp, dst)


SAVED = ((PROTOCOL, 'PROTOCOL.sealed.md'), (MANIFEST, 'MANIFEST.sealed.sha256'), (SEAL, 'SEAL.before.sha256'),
         (RECORD, 'REGISTRATION.before.json'))


def restore(root, work, txn):
    """(ok, summary): PROTOCOL.md, MANIFEST.sha256, SEAL.sha256 and REGISTRATION.json back to the copies taken at the
    start of the locked part (only the files that differ), each copy used only at the sha256 the journal's 'copied'
    step records; ok when every file equals its copy and both seal lines verify OK afterwards. Without a 'copied' step
    nothing was changed and nothing is copied."""
    rec = txn.record('copied')
    restored, problems = [], []
    copies = (rec or {}).get('copies') or {}
    for rel, name in SAVED:
        want = copies.get(rel)
        if want is None:
            continue
        src, dst = work / name, root / rel
        try:
            if not src.is_file() or sha256(src) != want:
                problems.append(f'the copy {name} is not at the sha256 the journal records ({want[:16]})')
                continue
            if not dst.is_file() or sha256(dst) != want:
                atomic_copy(src, dst, work, dst.stat().st_mode & 0o7777 if dst.exists() else None)
                restored.append(rel)
        except OSError as e:
            problems.append(f'{rel}: {type(e).__name__}: {e}')
    try:
        _, out, _ = registration(root, '--verify')
    except Exception as e:                       # noqa: BLE001
        out = f'registration.py --verify failed: {type(e).__name__}: {e}'
    same = all(tree_sha(root, rel) == copies[rel] for rel, _ in SAVED if copies.get(rel))
    ok = not problems and same and seal_lines_ok(out)
    what = restored or ('nothing (unchanged)' if rec else 'nothing (no copies: the transaction stopped before its '
                                                            'first change)')
    summary = (f'restore: restored {what}; registration.py --verify: ' + ' | '.join(out.strip().splitlines())
               + (f'; problems: {problems}' if problems else '') + f' -> {"sealed state OK" if ok else "NOT OK"}')
    return ok, summary


def quiet():
    """From the seal on (and during a restore) a signal no longer interrupts the transaction."""
    for s in SIGNALS:
        signal.signal(s, signal.SIG_IGN)


def fault(name, root):
    return os.environ.get(FAULT_ENV) == name and root != REAL_ROOT


def fault_change_file(root):
    """AMEND_STEP3_FAULT=change_before_preseal: a comment line appended to AMEND_STEP3_FAULT_FILE (a file of the
    scratch root, never one reached through a symlink out of it)."""
    rel = os.environ.get(FAULT_FILE_ENV, '')
    p = (root / rel).resolve()
    if not rel or not str(p).startswith(str(root.resolve()) + os.sep) or not p.is_file():
        raise Stop(f'{FAULT_FILE_ENV}={rel!r} is not a file of the scratch root {root}')
    with open(p, 'a', encoding='utf-8') as fh:
        fh.write('# changed by the step-3 simulation between the manifest and the seal\n')


def preseal_problems(root, spec, base, new_man, m_sha, new_text):
    """The pre-seal check (module docstring)."""
    probs = []
    if tree_sha(root, PROTOCOL) != sha256_text(new_text):
        probs.append('PROTOCOL.md on disk is not the composed text')
    if tree_sha(root, MANIFEST) != m_sha:
        probs.append('MANIFEST.sha256 on disk is not the manifest of this transaction')
    strict = set(base) | {k for k in new_man if k.startswith(P1_JOBS)} | set(spec['expected_new_registered'])
    for p in sorted(strict):
        want = new_man.get(p)
        if want is None:
            probs.append(f'{p} (registered) is not in the new manifest')
        elif tree_sha(root, p) != want:
            probs.append(f'{p} (registered) changed after --write-manifest')
    for p, want in sorted(spec['must_equal'].items()):
        if tree_sha(root, p) != want:
            probs.append(f'{p} is not at its prepared sha256 {want[:16]}')
    return probs


def locked(root, spec, work, when):
    txn = Txn(root, work)

    def interrupted(signum, _frame):
        quiet()
        raise Stop(f'signal {signum} during the transaction')
    for s in SIGNALS:
        signal.signal(s, interrupted)
    entries = {}
    try:
        txn.step('begin', datetime=when, pid=os.getpid())
        P1, PD = drivers(root)
        text = (root / PROTOCOL).read_text(encoding='utf-8')
        view = PD.phase_view(None, text)
        refuse = datetime_problems(when, view)
        refuse += [f'Amendment {aid} is entered already' for aid in ('A3', 'A4', 'A7', 'A9')
                   if aid in view['amendments']]
        if spec['op_title_mark'] in text or view['heading'] is not None:
            refuse.append('the operational addition or the heading of the phase driver is in PROTOCOL.md already')
        reg = P1.registration_view(PD.Cfg(PD.parse_args(['--root', str(root), '--dry-run'])))
        if not reg['seal_ok']:
            refuse.append('PROTOCOL.md / MANIFEST.sha256 are not the sealed versions (an unsealed edit since the '
                          'pre-check)')
        refuse += [f'{rel} exists' for rel in TXN_FILES if (root / rel).exists()]
        if os.stat(work).st_dev != os.stat(root / PROTOCOL).st_dev or \
                os.stat(work).st_dev != os.stat(root / MANIFEST).st_dev:
            refuse.append(f'{work} is not on the file system of PROTOCOL.md and MANIFEST.sha256 (atomic rename)')
        refuse += check_inputs(root, spec)
        if refuse:
            raise Stop('; '.join(refuse))
        for rel, name in SAVED:
            shutil.copyfile(root / rel, work / name)
        copies = {rel: sha256(work / name) for rel, name in SAVED}
        if sha256_text(text) != copies[PROTOCOL]:
            raise Stop('PROTOCOL.md changed while it was read and copied (an editor without the lock)')
        txn.step('copied', copies=copies, protocol_sha256=copies[PROTOCOL], manifest_sha256=copies[MANIFEST])
        say(f'sealed state copied into {work}: PROTOCOL.md {copies[PROTOCOL]}, MANIFEST.sha256 {copies[MANIFEST]}')
        rc, out, err = registration(root, '--write-manifest', '--force')
        m = re.search(r'^wrote .*MANIFEST\.sha256: (\d+) files, sha256 ([0-9a-f]{64})$', out, re.M)
        txn.step('manifest', exit=rc, output=out.strip(), manifest_sha256=m.group(2) if m else None)
        say(f'registration.py --write-manifest --force (exit {rc}): {out.strip()}')
        if rc != 0 or not m:
            raise Stop(f'--write-manifest failed: {err.strip()[-500:]}')
        n_files, m_sha = int(m.group(1)), m.group(2)
        new_man = manifest_map(root / MANIFEST)
        if sha256(root / MANIFEST) != m_sha or len(new_man) != n_files:
            raise Stop('the manifest on disk is not the one --write-manifest reported')
        # step 3.2: the post-manifest check, before anything is inserted; the same for the P1 job files
        base = baseline_files(root)
        bad = [k for k, v in base.items() if new_man.get(k) != v]
        if fault('post_manifest', root):
            bad = bad or ['(simulated post-manifest failure)']
        sealed_man = manifest_map(work / 'MANIFEST.sealed.sha256')
        jobs_bad, jobs_new = p1_job_check(sealed_man, new_man)
        txn.step('post_manifest_check', result='OK' if not bad else bad, p1_jobs='OK' if not jobs_bad else jobs_bad)
        say(f'post-manifest check (step 3.2): {bad or "OK"}; P1 job files of the sealed manifest: '
            f'{jobs_bad or "OK"}; P1 job files new in the manifest: {jobs_new or "none"}')
        if bad:
            raise Stop(f'post-manifest check: registered files not in the new manifest at their sealed sha256: '
                       f'{bad[:10]}')
        if jobs_bad:
            raise Stop(f'post-manifest check: P1 job files (always registered) not in the new manifest at their '
                       f'sealed sha256: {jobs_bad[:10]}')
        added = sorted(set(new_man) - set(sealed_man))
        changed = sorted(k for k in new_man if k in sealed_man and new_man[k] != sealed_man[k])
        say(f'new manifest: {n_files} files, sha256 {m_sha}; new in it: {added or "none"}; changed since the seal '
            f'(unregistered): {changed or "none"}')
        entries, probs = fill_entries(root, spec, work, when, P1, PD, m_sha, n_files)
        txn.step('filled', problems=probs)
        if probs:
            raise Stop('entries: ' + '; '.join(probs))
        if sha256(root / PROTOCOL) != copies[PROTOCOL]:
            raise Stop('PROTOCOL.md changed while the lock was held (an editor without the lock)')
        new, probs = compose(P1, PD, spec, text, entries)
        if not probs:
            got = registered_by(text, new, new_man, base)
            if got != spec['expected_new_registered']:
                probs.append(f'the transaction would register {len(got)} files, expected '
                             f'{len(spec["expected_new_registered"])}: '
                             f'{sorted(set(got) ^ set(spec["expected_new_registered"]))[:10]}')
        txn.step('composed', problems=probs, protocol_after_sha256=sha256_text(new) if new else None)
        if probs:
            raise Stop('composition: ' + '; '.join(probs))
        (work / 'PROTOCOL.new.md').write_text(new, encoding='utf-8')
        mode = (root / PROTOCOL).stat().st_mode & 0o7777
        atomic_copy(work / 'PROTOCOL.new.md', root / PROTOCOL, work, mode)
        st = os.stat(root / PROTOCOL)
        txn.step('protocol', protocol_sha256=sha256(root / PROTOCOL), inode=[st.st_dev, st.st_ino, st.st_mtime_ns])
        say(f'PROTOCOL.md written: sha256 {sha256(root / PROTOCOL)} ({len(new.splitlines())} lines)')
        if fault('before_seal', root):
            raise Stop('simulated failure after PROTOCOL.md was written, before the seal')
        if fault('signal_before_seal', root):
            os.kill(os.getpid(), signal.SIGTERM)
        if fault('kill_before_seal', root):
            os.kill(os.getpid(), signal.SIGKILL)
        if fault('change_before_preseal', root):
            fault_change_file(root)
        probs = preseal_problems(root, spec, base, new_man, m_sha, new)
        txn.step('preseal_check', problems=probs)
        say(f'pre-seal check (PROTOCOL.md and the new manifest on disk; registered baseline, P1 job files and the 40 '
            f'newly registered files at their new-manifest sha256; must_equal): {probs or "OK"}')
        if probs:
            raise Stop('pre-seal check: ' + '; '.join(probs[:10]))
        rc, out, err = (1, '', 'simulated seal failure') if fault('seal_fail', root) else registration(root, '--seal')
        quiet()        # from here on the seal either stands (verified below) or is undone by the restore
        say(f'registration.py --seal (exit {rc}): {out.strip()} {err.strip()[-300:]}')
        sm = re.search(r'sealed: PROTOCOL\.md ([0-9a-f]{64}), manifest ([0-9a-f]{64})', out)
        if rc != 0 or not sm or sm.group(1) != sha256_text(new) or sm.group(2) != m_sha:
            raise Stop(f'--seal failed (exit {rc})')
        txn.step('sealed', protocol_sha256=sm.group(1), manifest_sha256=sm.group(2))
    except BaseException as e:                   # every failure (a signal included): journal, restore, messages
        quiet()
        reason = str(e) if isinstance(e, Stop) else f'{type(e).__name__}: {e}'
        if txn.record('copied') is None:
            txn.safe_step('refused', reason=reason)
            say(f'STOPPED before any change: {reason}')
            return 1
        txn.safe_step('failed', reason=reason)
        try:
            ok, summary = restore(root, work, txn)
        except BaseException as e2:              # noqa: BLE001
            ok, summary = False, f'restore: {type(e2).__name__}: {e2}'
        txn.safe_step('restored' if ok else 'restore_incomplete')
        say(f'FAILURE before the seal: {reason}')
        say(summary)
        return 1 if ok else 2
    registered = set(base) | set(spec['expected_new_registered'])
    seal_ok, strict, loose, out = verify_classified(root, registered)
    ok = seal_ok and not strict
    txn.step('verified' if ok else 'verify_not_clean', output=out.strip(), registered_differ=strict,
             unregistered_differ=loose)
    say('registration.py --verify: ' + ' | '.join(out.strip().splitlines()))
    if loose:
        say(f'note: unregistered files changed during the transaction (named at the next seal): {loose[:10]}')
    if strict:
        say(f'registered files differ from the sealed manifest: {strict[:10]}')
    for n in ORDER:
        say(f'entry {n}: {len(entries[n].splitlines())} lines ({work / f"entry_{n}.md"})')
    return 0 if ok else 3


# ------------------------------------------------------------------------------------------------ restore command

def take_lock(root, timeout):
    """An exclusive flock on framelease_v4/.protocol.lock (opened read only, never created); the fd, or Stop."""
    path = root / LOCK
    if not path.is_file():
        raise Stop(f'{LOCK} does not exist')
    fd = os.open(path, os.O_RDONLY)
    t0 = time.monotonic()
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            if time.monotonic() - t0 > timeout:
                os.close(fd)
                raise Stop(f'the protocol lock was not free within {timeout} s (another editor; this command takes '
                           'the lock itself: never run it under flock)') from None
            time.sleep(0.5)


def restore_guard(root, work, txn):
    """Reasons not to restore (module docstring, "restore")."""
    rec = txn.record('copied')
    if rec is None:
        return []
    copies = rec.get('copies') or {PROTOCOL: rec.get('protocol_sha256'), MANIFEST: rec.get('manifest_sha256')}
    composed = {s.get('protocol_after_sha256') for s in txn.state['steps'] if s.get('step') == 'composed'} - {None}
    written = txn.record('protocol')
    manifests = {s.get('manifest_sha256') for s in txn.state['steps'] if s.get('step') == 'manifest'} - {None}
    cur = {rel: tree_sha(root, rel) for rel, _ in SAVED}
    out = []
    if cur[PROTOCOL] != copies.get(PROTOCOL):
        if cur[PROTOCOL] not in composed:
            out.append(f'PROTOCOL.md ({cur[PROTOCOL][:16]}) is neither the sealed copy nor the text this transaction '
                       'composed (a later edit or transaction)')
        elif written and written.get('inode'):
            st = os.stat(root / PROTOCOL)
            if [st.st_dev, st.st_ino, st.st_mtime_ns] != written['inode']:
                out.append('PROTOCOL.md holds the text this transaction composed, but it is not the file this '
                           'transaction wrote (another inode: written again later, e.g. by a later transaction)')
    if cur[MANIFEST] != copies.get(MANIFEST) and cur[MANIFEST] not in manifests:
        unjournaled = (not txn.record('manifest') and cur[PROTOCOL] == copies.get(PROTOCOL)
                       and cur[SEAL] == copies.get(SEAL))
        if not unjournaled:
            out.append(f'MANIFEST.sha256 ({cur[MANIFEST][:16]}) is neither the sealed copy nor the manifest this '
                       'transaction wrote')
    if not written:
        for rel in (SEAL, RECORD):
            if copies.get(rel) and cur[rel] != copies[rel]:
                out.append(f'{rel} differs from the copy although this transaction never reached --seal')
    return out


def restore_command(root, work, lock_timeout):
    if not (work / 'journal.json').is_file():
        raise Stop(f'{work} holds no journal.json: no locked part ran there; nothing is restored')
    fd = take_lock(root, lock_timeout)
    try:
        quiet()
        # read under the lock: a locked part that still ran when this command started has ended by now
        state = json.loads((work / 'journal.json').read_text(encoding='utf-8'))
        if state.get('root') != str(root):
            raise Stop(f'the journal is of the root {state.get("root")}, not of {root}')
        last = state.get('step')
        if last in TERMINAL:
            raise Stop(f'the journal says {last!r}: '
                       + ('the transaction was sealed; run `postcheck`, never `restore`' if last in
                          ('sealed', 'verified', 'verify_not_clean') else 'nothing is left to restore')
                       + '; nothing is restored')
        txn = Txn(root, work, state)
        guard = restore_guard(root, work, txn)
        if guard:
            raise Stop('restore refused: ' + '; '.join(guard))
        txn.safe_step('restore_started', by='step3_txn.py restore', pid=os.getpid())
        ok, summary = restore(root, work, txn)
        txn.safe_step('restored' if ok else 'restore_incomplete', by='step3_txn.py restore')
        say(f'journal step before this restore: {last!r}')
        say(summary)
        return 0 if ok else 2
    finally:
        os.close(fd)


# ------------------------------------------------------------------------------------------------ post-check

def postcheck(root, spec, work):
    P1, PD = drivers(root)
    probs = []
    rc, out, err = run([py(root), '-I', '-B', '-c', STEP32], root)
    say(f'step 3.2 on the sealed manifest: {out.strip() or err.strip()[-300:]}')
    if out.strip() != 'OK':
        probs.append(f'step 3.2: {out.strip()[:300]}')
    man = manifest_map(root / MANIFEST)
    jobs_bad, jobs_new = p1_job_check(manifest_map(work / 'MANIFEST.sealed.sha256'), man)
    say(f'P1 job files of the earlier sealed manifest at their sha256 in the sealed manifest: {jobs_bad or "OK"}; '
        f'new: {jobs_new or "none"}')
    if jobs_bad:
        probs.append(f'P1 job files: {jobs_bad[:10]}')
    seal_ok, strict, loose, out = verify_classified(root, set(baseline_files(root))
                                                    | set(spec['expected_new_registered']))
    say('registration.py --verify: ' + ' | '.join(out.strip().splitlines()))
    if loose:
        say(f'note: unregistered files differ from the sealed manifest (named at the next seal): {loose[:10]}')
    if not seal_ok or strict:
        probs.append(f'registration.py --verify: seal lines OK {seal_ok}; registered files differing: {strict[:10]}')
    rc, out, err = run([py(root), '-I', '-B', str(root / PHASE_DRIVER), '--dry-run'], root, 3600)
    (work / 'phase_driver_dry_run.txt').write_text(out + ('\n--- stderr\n' + err if err else ''), encoding='utf-8')
    gates = [ln for ln in out.splitlines() if re.match(r'^  G\d ', ln)]
    say(f'phase_driver.py --dry-run (exit {rc}; full output {work / "phase_driver_dry_run.txt"}):')
    for ln in gates:
        say('  ' + ln)
    decision = (root / PD_DIR / 'D1_DECISION.json').exists()
    if rc != 0 or 'WOULD ALERT' in out:
        probs.append(f'phase_driver.py --dry-run exit {rc}')
    if not any(re.match(r'^  G0\s+passed\b', ln) for ln in gates):
        probs.append('phase_driver.py --dry-run: G0 is not passed')
    if not decision and not any(re.match(r'^  G1\s+waiting\b.*D1_DECISION\.json', ln) for ln in gates):
        probs.append('phase_driver.py --dry-run: G1 does not wait for D1_DECISION.json')
    cfg = PD.Cfg(PD.parse_args(['--root', str(root), '--dry-run']))
    view = PD.phase_view(cfg)
    runs = [r[0] for r in PD.stress_runs(view)]
    cmd = cfg.stress_cmd('s2_relative', ['<network of the RL freeze>']) if 's2_relative' in runs else []
    say(f'G5 plan (phase_driver.stress_runs on the sealed PROTOCOL.md): {runs}; A7b read from the A7 text: '
        f'{PD.a7_supplementary(view)}; s2_relative: {" ".join(cmd[3:])}')
    if runs != ['s3', 's2', 's2_relative', 's1'] or '--grid relative' not in ' '.join(cmd):
        probs.append('the G5 plan holds no `s2 --grid relative`')
    rc, out, err = run(tool_cmd(root, CHECK, []), root, 600)
    (work / 'check_drafts_after.txt').write_text(out + err, encoding='utf-8')
    say(f'check_drafts.py on the new PROTOCOL.md (exit {rc}):')
    for ln in out.strip().splitlines():
        say('  ' + ln)
    if rc != 0 or 'all checks passed' not in out:
        probs.append(f'check_drafts.py exit {rc}')
    text = (root / PROTOCOL).read_text(encoding='utf-8')
    base = baseline_files(root)
    before = (work / 'PROTOCOL.sealed.md').read_text(encoding='utf-8')
    got = registered_by(before, text, man, base)
    say(f'files registered by this transaction (manifest files outside the P1 baseline whose sha256 the sealed '
        f'PROTOCOL.md cites and the earlier one did not): {len(got)}')
    if got != spec['expected_new_registered']:
        probs.append(f'registered files {len(got)} != expected {len(spec["expected_new_registered"])}')
    i = text.index('Status (Amendment A3):')
    para = text[i:text.index('\n\n', i)]
    (work / 'sec_4_1_status_paragraph.txt').write_text(para + '\n', encoding='utf-8')
    say('Sec. 4.1 status paragraph (the text the fifth A10 in-place "old" is taken from, APPLY_PLAN2.md Sec. 4 '
        'step 1):')
    for ln in para.splitlines():
        say('  | ' + ln)
    return probs


# ------------------------------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('command', choices=('precheck', 'locked', 'postcheck', 'restore'))
    ap.add_argument('--root', default=str(REAL_ROOT))
    ap.add_argument('--work', help='transaction directory (the copies, the filled entries, the journal)')
    ap.add_argument('--datetime', help="'YYYY-MM-DD HH:MM' (Beijing time), the one time stamp of the five entries")
    ap.add_argument('--txn-root', help='precheck: the directory whose */journal.json are checked for an interrupted '
                                       'transaction (amend_step3.sh: the parent of the transaction directory)')
    ap.add_argument('--lock-timeout', type=float, default=600.0, help='restore: wait for the protocol lock (s)')
    a = ap.parse_args()
    root = Path(a.root).resolve()
    work = Path(a.work).resolve() if a.work else None
    if a.command == 'precheck' and work is None:
        work = Path(f'/tmp/amend_step3_precheck_{os.getpid()}')
        work.mkdir(parents=True, exist_ok=True)
    if work is not None and work.is_dir():
        _OUT['log'] = str(work / 'step3_txn.log')
    say(f'step3_txn.py {a.command} {time.strftime("%Y-%m-%dT%H:%M:%S%z")} (pid {os.getpid()}): root {root}, '
        f'work {work}')
    hooks = [v for v in (FAULT_ENV, FAULT_FILE_ENV, NOW_ENV) if os.environ.get(v)]
    if hooks and (root == REAL_ROOT or os.environ.get(FAULT_ENV, FAULTS[0]) not in FAULTS):
        say(f'STOP: {hooks} are simulation hooks; refused here')
        return 1
    try:
        spec = spec_load()
        if a.command == 'precheck':
            probs = precheck(root, spec, work, Path(a.txn_root).resolve() if a.txn_root else None, a.datetime)
            for p in probs:
                say(f'PROBLEM: {p}')
            say(f'precheck: {"passed" if not probs else f"{len(probs)} problem(s)"} (dry files in {work})')
            return 0 if not probs else 1
        if work is None or not work.is_dir():
            raise Stop('--work must name an existing directory')
        if a.command == 'restore':
            return restore_command(root, work, a.lock_timeout)
        if a.command == 'locked':
            if not a.datetime:
                raise Stop("--datetime 'YYYY-MM-DD HH:MM' is required")
            return locked(root, spec, work, a.datetime)
        probs = postcheck(root, spec, work)
        for p in probs:
            say(f'PROBLEM: {p}')
        say(f'postcheck: {"passed" if not probs else f"{len(probs)} problem(s)"}')
        return 0 if not probs else 4
    except Stop as e:
        say(f'STOP: {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
