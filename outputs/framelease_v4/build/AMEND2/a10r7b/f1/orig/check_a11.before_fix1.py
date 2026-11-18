"""Check the Amendment A11 draft (item R7B) and simulate its application after Amendment A10 (read only on the project).

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/a10r7b/check_a11.py [--protocol P] [--write-sim DIR]

Checks (template A11_entry.md and spec A11_spec.json of this directory):
  * placeholders: only {{datetime}}, {{manifest:files}}, {{sha256:<path>}} and {{pytest:<log>}}; every <path> exists
    now or is written at application (a test log of the spec, the registration manifest). apply_entry.py fills the
    template only after `registration.py --write-manifest`: a missing file there stops it with the manifest rewritten
    and not sealed, so no placeholder may name a missing file;
  * the filled text (the current sha256 where the file exists, the application test logs of the spec where they exist,
    else the drafting copies in logs/): prose lines at most 120 columns (table rows excepted); no line starts with
    '## ', the anchor or a driver heading, reads as a driver entry (p1_driver.ENTRY_RE, phase_driver.ENTRY_RE) or as
    an amendment title (phase_driver.AMEND_RE) except the first, which is read as Amendment A11; no line starts like a
    list item, quote or heading Markdown would read; the anchor phrase occurs nowhere;
  * the spec: template path, test logs equal the {{pytest:...}} logs of the template, must_equal against the tree,
    max_new_registered equals the number of framelease_v4 files the template cites by sha256 (2), and the manifest
    files outside the registered set of apply_entry_stream.py at A11 (the files of both drivers' registered baselines,
    every sealed-manifest file whose sha256 PROTOCOL.md after A10 cites, and the P1 job files under
    outputs/framelease_v4/p1_jobs/) whose sha256 in the manifest that --write-manifest writes (the files outside that
    set hashed on disk) the composed PROTOCOL.md after A11 holds are exactly the two R7B files (the count
    apply_entry_stream.py compares with max_new_registered after --write-manifest);
  * no template line holds 'TODO'; the template holds the sentences of the reporting rule of finding F1 (RULE_PHRASES);
  * evidence pins: every file the template cites by {{sha256:...}} (except the manifest and the spec's test logs) is
    listed in f1/evidence_a11_sha256.txt at its current sha256, and the list names no other file (--write-evidence
    writes the list from the current files);
  * simulation on PROTOCOL.md in memory: Amendment A10 first when PROTOCOL.md does not hold it yet (the A10 template
    filled by check_drafts.fill, its in-place texts, inserted before the anchor as apply_entry.py does), then A11
    (its in-place text, which must occur once, and the entry before the anchor), then a later gate entry of the phase
    driver (phase_driver.insert_entry). p1_driver.protocol_view and phase_driver.phase_view raise no ALERT; the P1
    entries are unchanged; the phase driver's entries are unchanged by A10 and A11 and the later gate entry is read;
    Amendments A10 and A11 are each read once; the first Sec. 13.2 line citing analyze_v4.py belongs to A10 and the
    line citing verify_table1_extra.py to A11 (phase_driver.citing_amendment); no line that an in-place text
    produces is longer than 120 columns; phase_driver.analysis_registration has no wait reason once A10 is in.
  * open preconditions (exit 2): A10 not yet in PROTOCOL.md (simulated here); the review of the fixes
    (build/R7B/rereview/REVIEW.md, named in the template) missing or with a verdict other than GO; an application
    test log of the spec missing, not ending with no failure, or older than a file of must_equal (the tests ran on
    another version: rerun apply_entry_stream.py ... --tests). The fill uses a log that is not older than the files of
    must_equal: the application log, else the drafting copy in f1/logs/ or logs/.
--write-sim DIR (under /tmp/AMEND3/ or /tmp/A10A11/ only): also write the simulated texts (PROTOCOL.after_A10.md,
PROTOCOL.after_A11.md, PROTOCOL.after_gate.md) and the filled A11 entry there.
Exit 0 "all checks passed", 1 a problem, 2 the checks pass but a precondition is open.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path('/home/kang/Desktop/DAC')
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'outputs/framelease_v4/build/AMEND2'))
sys.dont_write_bytecode = True

from framelease_v4.protocol import p1_driver as P1  # noqa: E402
from framelease_v4.protocol import phase_driver as PD  # noqa: E402
import check_drafts as CD  # noqa: E402

HERE = ROOT / 'outputs/framelease_v4/build/AMEND2/a10r7b'
TEMPLATE = HERE / 'A11_entry.md'
SPEC = HERE / 'A11_spec.json'
A10_TEMPLATE = ROOT / 'outputs/framelease_v4/build/AMEND2/final/A10_entry.md'
A10_SPEC = ROOT / 'outputs/framelease_v4/build/AMEND2/final/A10_spec.json'
MANIFEST = 'outputs/framelease_v4/registration/MANIFEST.sha256'
BASELINES = (ROOT / 'outputs/framelease_v4/p1_driver/registered_baseline.json',
             ROOT / 'outputs/framelease_v4/phase_driver/registered_baseline.json')
REREVIEW = 'outputs/framelease_v4/build/R7B/rereview/REVIEW.md'
P1_JOBS = 'outputs/framelease_v4/p1_jobs/'                     # P1 job files: registered (p1_driver.is_strict)
F1DIR = HERE / 'f1'
EVIDENCE = F1DIR / 'evidence_a11_sha256.txt'
DRAFT_LOG_DIRS = (F1DIR / 'logs', HERE / 'logs')
SIM_ROOTS = ('/tmp/AMEND3/', '/tmp/A10A11/')
# The reporting rule of finding F1 (item F1A11): sentences the template must hold (whitespace-normalized).
RULE_PHRASES = (
    '* Reporting rule for finding F1 (fixed by this entry). `framelease_v4/arms/realized.py` stays as registered: '
    'F1 is not corrected.',
    'The registered values, those of the aggregator and the analysis through `realized.py`, are the values of Tables I '
    'and II and of the paper; the recomputation changes none of them.',
    "reports every difference whose cause in `differences.csv` is 'F1' as one class, class F1, with that cause",
    'per arm, the number of runs with such a difference',
    'the largest absolute difference.',
    'The paper states class F1, its cause and its size next to the verification result.',
    "A difference of any other cause, 'F3', 'F1+F3' or none, is a verification failure handled by the rules of "
    'Amendment A10 (use rule 4; Sec. 9.12).',
    'On DIFFER with every difference in class F1, these columns are released with the registered values and class F1 '
    'is reported (reporting rule above).',
)
R7B_FILES = ('framelease_v4/analysis/verify_table1_extra.py',
             'framelease_v4/analysis/tests/test_verify_table1_extra.py')
PLACEHOLDER = re.compile(r'\{\{([^}]+)\}\}')
HEX64 = re.compile(r'\b[0-9a-f]{64}\b')
FAKE_SHA = 'c' * 64
FAKE_DATETIME = '2026-11-15 12:00'
FAKE_FILES = '231'
GATE_LINE = (f'* **G3 P2 data manifest** ({FAKE_DATETIME}, Beijing time). Simulated gate entry; manifest and seal: '
             f'`MANIFEST.sha256`, {FAKE_FILES} files, sha256 `{"d" * 64}`, sealed with this entry.')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def flat(text):
    return ' '.join(text.split())


def newest_code(spec):
    """mtime of the newest file of must_equal: a test log older than it ran on another version."""
    return max((ROOT / p).stat().st_mtime for p in spec.get('must_equal', {}) if (ROOT / p).is_file())


def stale(log, spec):
    return log.stat().st_mtime < newest_code(spec)


def log_for(app_log, spec):
    """The application log if it exists and is not older than the files of must_equal, else the first such drafting
    copy (same file name) in f1/logs/ or logs/; else whichever of them exists."""
    cands = [ROOT / app_log] + [d / Path(app_log).name for d in DRAFT_LOG_DIRS]
    fresh = [p for p in cands if p.is_file() and not stale(p, spec)]
    if fresh:
        return fresh[0]
    return next((p for p in cands if p.is_file()), cands[0])


def fill(text, spec):
    def sub(m):
        key = m.group(1)
        if key == 'datetime':
            return FAKE_DATETIME
        if key == 'manifest:files':
            return FAKE_FILES
        kind, _, arg = key.partition(':')
        if kind == 'sha256':
            return sha256(ROOT / arg) if (ROOT / arg).is_file() and arg != MANIFEST else FAKE_SHA
        log = log_for(arg, spec)
        return CD.pytest_summary(log) if log.is_file() else '99 passed in 99.99s'
    return PLACEHOLDER.sub(sub, text)


def placeholder_problems(text, spec):
    """Unknown kinds and missing files; the review of the fixes (REREVIEW) is an open precondition instead."""
    later = {t['log'] for t in spec.get('tests', [])} | {MANIFEST, REREVIEW}
    out = []
    for key in PLACEHOLDER.findall(text):
        kind, _, arg = key.partition(':')
        if key in ('datetime', 'manifest:files'):
            continue
        if kind not in ('sha256', 'pytest'):
            out.append(f'unknown placeholder {{{{{key}}}}}')
        elif kind == 'sha256' and not (ROOT / arg).is_file() and arg not in later:
            out.append(f'{{{{{key}}}}} names a file that does not exist and is not written at application')
        elif kind == 'pytest' and arg not in later:
            out.append(f'{{{{{key}}}}} is not a test log of the spec')
    return out


def line_problems(filled):
    out = []
    lines = filled.splitlines()
    for i, ln in enumerate(lines, 1):
        if len(ln) > 120 and not ln.lstrip().startswith('|'):
            out.append(f'line {i} has {len(ln)} columns')
        if ln.startswith('## ') or ln.startswith(P1.ANCHOR) or ln.strip() in (P1.HEADING, PD.HEADING):
            out.append(f'line {i} starts with a heading, the anchor or a driver heading')
        if P1.ENTRY_RE.match(ln) or PD.ENTRY_RE.match(ln):
            out.append(f'line {i} reads as a driver entry')
        if PD.AMEND_RE.match(ln) and i != 1:
            out.append(f'line {i} reads as an amendment title')
        if re.match(r'^\s*(\d+\)|[-+>#])(\s|$)', ln) or (re.match(r'^\s*\d+\.\s', ln) and not ln.startswith('  ')):
            out.append(f'line {i} starts like a list item, a quote or a heading Markdown would read')
        if 'TODO' in ln:
            out.append(f'line {i} holds a TODO: {ln.strip()[:80]!r}')
    m = PD.AMEND_RE.match(lines[0]) if lines else None
    if not m or m.group('id') != 'A11':
        out.append('the first line is not read as the title of Amendment A11')
    if P1.ANCHOR in filled:
        out.append(f'the text contains the anchor phrase "{P1.ANCHOR}"')
    return out


def manifest():
    out = {}
    for ln in (ROOT / MANIFEST).read_text(encoding='utf-8').splitlines():
        if '  ' in ln:
            digest, path = ln.split('  ', 1)
            out[path] = digest
    return out


def registered_at_a11(man, after_a10):
    """The registered set of apply_entry_stream.py when A11 is applied: both baselines, the sealed-manifest files whose
    sha256 PROTOCOL.md (after A10) cites, the P1 job files."""
    base = {k for b in BASELINES for k in json.loads(b.read_text(encoding='utf-8'))['files']}
    base |= {k for k, v in man.items() if v in after_a10}
    base |= {k for k in man if k.startswith(P1_JOBS)}
    return base


def manifest_after_write(man, registered):
    """The manifest as --write-manifest writes it for the files of the sealed one: a registered file must equal its
    sealed sha256 (else the applier stops), every other file is hashed on disk; a missing file leaves it."""
    return {k: (v if k in registered else sha256(ROOT / k)) for k, v in man.items() if (ROOT / k).is_file()}


def spec_problems(template, spec, filled, after_a10, after_a11):
    out = []
    if (ROOT / spec['template']).resolve() != TEMPLATE.resolve():
        out.append(f'spec template {spec["template"]} is not {TEMPLATE.relative_to(ROOT)}')
    logs = {k.partition(':')[2] for k in PLACEHOLDER.findall(template) if k.startswith('pytest:')}
    if logs != {t['log'] for t in spec['tests']}:
        out.append(f'template logs {sorted(logs)} != spec logs')
    for p, want in spec.get('must_equal', {}).items():
        have = sha256(ROOT / p)
        if have != want:
            out.append(f'{p} changed ({want[:12]} -> {have[:12]}): review the change, then update the spec')
    cited = sorted({k.partition(':')[2] for k in PLACEHOLDER.findall(template)
                    if k.startswith('sha256:framelease_v4/')})
    if spec.get('max_new_registered') != len(cited) or tuple(cited) != tuple(sorted(R7B_FILES)):
        out.append(f'max_new_registered {spec.get("max_new_registered")}, framelease_v4 files cited: {cited}')
    man = manifest()
    base = registered_at_a11(man, after_a10)
    new_man = manifest_after_write(man, base)
    cited_new = sorted(k for k, v in new_man.items() if k not in base and v in after_a11)
    if cited_new != sorted(R7B_FILES):
        out.append(f'unregistered manifest files cited by sha256 (apply_entry_stream.py count after --write-manifest): '
                   f'{cited_new}')
    stray = sorted({h for h in HEX64.findall(filled)} & {v for k, v in new_man.items() if k not in R7B_FILES})
    if stray:
        out.append(f'the entry holds the sha256 of other manifest files: '
                   f'{[k for k, v in new_man.items() if v in stray]}')
    changed = sorted(k for k in new_man if new_man[k] != man[k])
    return out, cited_new, changed


def rule_problems(template):
    """The sentences of the reporting rule of finding F1 (RULE_PHRASES) in the template."""
    f = flat(template)
    return [f'the template lacks the F1 rule text: {ph[:70]!r}' for ph in RULE_PHRASES if flat(ph) not in f]


def shown(path):
    """A path relative to the project root where it lies under it."""
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def evidence_paths(template, spec):
    """The files the template cites by {{sha256:...}} except the manifest and the spec's test logs."""
    logs = {t['log'] for t in spec.get('tests', [])}
    return sorted({k.partition(':')[2] for k in PLACEHOLDER.findall(template) if k.startswith('sha256:')}
                  - logs - {MANIFEST})


def evidence_problems(template, spec, write=False):
    """f1/evidence_a11_sha256.txt lists every cited file at its current sha256 and nothing else (--write-evidence
    writes it)."""
    paths = evidence_paths(template, spec)
    if write:
        missing = [q for q in paths if not (ROOT / q).is_file()]
        if missing:
            return [f'--write-evidence: cited files missing: {missing}']
        text = ''.join(f'{sha256(ROOT / q)}  {q}\n' for q in paths)
        tmp = EVIDENCE.with_name('.' + EVIDENCE.name + '.tmp')
        tmp.write_text(text, encoding='utf-8')
        tmp.replace(EVIDENCE)
        print(f'written {shown(EVIDENCE)} ({len(paths)} files, {sha256(EVIDENCE)})')
    if not EVIDENCE.is_file():
        return [f'{shown(EVIDENCE)} is missing (--write-evidence)']
    listed = {}
    for ln in EVIDENCE.read_text(encoding='utf-8').splitlines():
        if '  ' in ln:
            digest, path = ln.split('  ', 1)
            listed[path] = digest
    out = [f'evidence {q}: not listed in {EVIDENCE.name}' for q in paths if q not in listed]
    out += [f'evidence {q}: listed but not cited by the template' for q in sorted(set(listed) - set(paths))]
    for q in paths:
        if q in listed and (not (ROOT / q).is_file() or sha256(ROOT / q) != listed[q]):
            out.append(f'evidence {q}: changed since {EVIDENCE.name} ({listed[q][:12]})')
    return out


def inplace(text, rules, label):
    """Apply in-place texts that occur once; problems for a count other than 1 and for produced lines > 120."""
    out = []
    for r in rules:
        n = text.count(r['old'])
        if n != 1:
            out.append(f'{label}: in-place text found {n} times: {r["old"].strip()[:60]!r}')
            continue
        text = text.replace(r['old'], r['new'])
        k = text.index(r['new'])
        span = text[text.rfind('\n', 0, k) + 1:text.find('\n', k + len(r['new']) - 1)]
        out += [f'{label}: in-place text "{r["old"].strip()[:40]}" produces a line of {len(ln)} columns'
                for ln in span.splitlines() if len(ln) > 120]
    return text, out


def simulate(protocol_text, a11_filled, spec, write_dir=None):
    out, notes = [], []
    text = protocol_text
    try:
        p1_before = {k: v['text'] for k, v in P1.protocol_view(None, text)['entries'].items()}
        phase_before = {k: v['text'] for k, v in PD.phase_view(None, text)['entries'].items()}
    except Exception as exc:
        return [f'simulation (current PROTOCOL.md): {type(exc).__name__}: {exc}'], notes, None, None
    if '**Amendment A10,' not in text:
        notes.append('A10 is not in PROTOCOL.md: simulated (check_drafts.fill, A10 in-place texts, entry before the '
                     'anchor)')
        a10_spec = json.loads(A10_SPEC.read_text(encoding='utf-8'))
        text, problems = inplace(text, a10_spec['inplace'], 'A10')
        out += problems
        text = CD.insert_before_anchor(text, CD.fill(A10_TEMPLATE.read_text(encoding='utf-8')))
    after_a10 = text
    text, problems = inplace(text, spec['inplace'], 'A11')
    out += problems
    text = CD.insert_before_anchor(text, a11_filled)
    after_a11 = text
    try:
        after_gate = PD.insert_entry(None, text, [GATE_LINE])
    except Exception as exc:
        return out + [f'simulation (gate entry after A11): {type(exc).__name__}: {exc}'], notes, after_a10, after_a11
    for label, t in (('after A11', after_a11), ('after a later gate entry', after_gate)):
        try:
            pv = P1.protocol_view(None, t)
            view = PD.phase_view(None, t)
        except Exception as exc:
            out.append(f'simulation {label}: {type(exc).__name__}: {exc}')
            continue
        if {k: v['text'] for k, v in pv['entries'].items()} != p1_before:
            out.append(f'simulation {label}: the P1 driver entries changed')
        entries = {k: v['text'] for k, v in view['entries'].items()}
        if any(entries.get(k) != v for k, v in phase_before.items()):
            out.append(f'simulation {label}: the phase driver entries changed: {list(entries)}')
        if label != 'after A11' and len(entries) != len(phase_before) + 1:
            out.append(f'simulation {label}: the gate entry is not read ({list(entries)} vs {list(phase_before)})')
        for a in ('A10', 'A11'):
            if len(view['amendments'].get(a, [])) != 1:
                out.append(f'simulation {label}: Amendment {a} titles read at lines {view["amendments"].get(a)}')
        s, e = view['sec']
        for path, owner in (('framelease_v4/analysis/analyze_v4.py', 'A10'), (R7B_FILES[0], 'A11'),
                            (R7B_FILES[1], 'A11')):
            h = sha256(ROOT / path)
            line = next((i + 1 for i in range(s, e) if h in view['lines'][i]), None)
            got = PD.citing_amendment(view, line) if line else None
            if got != owner:
                out.append(f'simulation {label}: the first Sec. 13.2 line citing {path} ({line}) belongs to {got!r}')
        cfg = type('Cfg', (), {'analyze_code': ROOT / 'framelease_v4/analysis/analyze_v4.py',
                               'rel': staticmethod(lambda p: str(Path(p).relative_to(ROOT)))})()
        waits, _, _ = PD.analysis_registration(cfg, view)
        if waits:
            out.append(f'simulation {label}: phase_driver.analysis_registration waits: {waits}')
    if write_dir:
        d = Path(write_dir)
        if not str(d.resolve()).startswith(SIM_ROOTS):
            out.append(f'--write-sim {d} refused: only under {" or ".join(SIM_ROOTS)}')
        else:
            d.mkdir(parents=True, exist_ok=True)
            for name, t in (('PROTOCOL.after_A10.md', after_a10), ('PROTOCOL.after_A11.md', after_a11),
                            ('PROTOCOL.after_gate.md', after_gate), ('A11_filled.md', a11_filled)):
                (d / name).write_text(t, encoding='utf-8')
            notes.append(f'simulated texts written to {d}')
    return out, notes, after_a10, after_a11


def open_items(spec, template, protocol_text):
    out = []
    if '**Amendment A10,' not in protocol_text:
        out.append('Amendment A10 is not in PROTOCOL.md yet (A11 is applied after A10)')
    if REREVIEW in template:
        p = ROOT / REREVIEW
        if not p.is_file():
            out.append(f'{REREVIEW} (the review of the R7B fixes, named in the template) does not exist yet')
        else:
            m = re.search(r'Verdict:?\**\s*\**\s*([A-Z_-]+)', p.read_text(encoding='utf-8'))
            if not m or m.group(1).rstrip('.') != 'GO':
                out.append(f'{REREVIEW}: verdict {m.group(1) if m else None}, the template states GO: apply and review '
                           'its fixes, then update the template, must_equal and this check')
    for t in spec['tests']:
        p = ROOT / t['log']
        s = CD.pytest_summary(p) if p.is_file() else ''
        if not s or 'failed' in s or 'error' in s:
            out.append(f'application test log {t["log"]}: {s or "missing"!r} (apply_entry_stream.py ... --tests)')
        elif stale(p, spec):
            out.append(f'application test log {t["log"]} ({s!r}) is older than a file of must_equal: rerun '
                       'apply_entry_stream.py A11_spec.json --tests')
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--protocol', default=str(ROOT / 'framelease_v4/PROTOCOL.md'))
    ap.add_argument('--write-sim', default=None)
    ap.add_argument('--write-evidence', action='store_true')
    a = ap.parse_args(argv)
    template = TEMPLATE.read_text(encoding='utf-8')
    spec = json.loads(SPEC.read_text(encoding='utf-8'))
    filled = fill(template, spec).strip('\n') + '\n'
    protocol_text = Path(a.protocol).read_text(encoding='utf-8')
    problems = placeholder_problems(template, spec) + line_problems(filled) + rule_problems(template)
    problems += evidence_problems(template, spec, a.write_evidence)
    sim, notes, after_a10, after_a11 = simulate(protocol_text, filled, spec, a.write_sim)
    problems += sim
    if after_a10 is None:
        after_a10, after_a11 = protocol_text, protocol_text + filled
    sp, cited_new, changed = spec_problems(template, spec, filled, after_a10, after_a11)
    problems += sp
    notes.append(f'--write-manifest changes the sealed sha256 of {changed}')
    opened = open_items(spec, template, protocol_text)
    keys = PLACEHOLDER.findall(template)
    print(f'A11: {len(filled.splitlines())} lines, {len(keys)} placeholders, '
          f'{sum(k.startswith("sha256:framelease_v4/") for k in set(keys))} framelease_v4 files cited by sha256; '
          f'apply_entry_stream.py would count {len(cited_new)} newly cited manifest files: {cited_new}')
    print(f'A11 in-place text found {protocol_text.count(spec["inplace"][0]["old"])}x in {a.protocol} now '
          '(1x after A10)')
    for n in notes:
        print(f'note: {n}')
    if problems:
        print('\n'.join(problems))
        return 1
    if opened:
        print('\n'.join(f'OPEN: {o}' for o in opened))
        print(f'checks passed; {len(opened)} open precondition(s): not ready for application')
        return 2
    print('all checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
