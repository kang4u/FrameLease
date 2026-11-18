"""Check the two Sec. 13.2 entry drafts of item AMEND2 (read only; writes nothing).

  cd /home/kang/Desktop/DAC
  .conda-unidrive-linux/bin/python -I -B outputs/framelease_v4/build/AMEND2/check_drafts.py

Checks, per entry template in outputs/framelease_v4/build/AMEND2/final/:
  * placeholders: only {{datetime}}, {{manifest:files}}, {{sha256:<path>}} and {{pytest:<log>}}; every <path> exists
    now, or is a file written at application (a test log of the entry, the registration manifest);
  * the filled text (placeholders replaced by values of the right length: the current sha256 where the file exists,
    the drafting test logs for {{pytest:...}}): prose lines at most 120 columns (table rows excepted); no line starts
    with '## ', with the anchor "Each amendment gets the date and time", with a heading of a driver, as an entry of
    the P1 stage driver (p1_driver.ENTRY_RE) or of the phase driver (phase_driver.ENTRY_RE); the title of A10 is the
    only line that reads as an amendment title (phase_driver.AMEND_RE), the operational addition has none;
  * simulated application on a copy of PROTOCOL.md in memory (the operational addition and the phase driver's
    heading with one gate entry unless PROTOCOL.md holds them already, then A10, each before the anchor as
    apply_entry.py and the phase driver place them; the in-place texts of A10_spec.json that exist now):
    p1_driver.protocol_view and phase_driver.phase_view raise no ALERT, the P1 entries and the phase driver's entries
    are unchanged by A10, the amendment A10 is read once, and the line that cites analyze_v4.py belongs to A10
    (phase_driver.citing_amendment, the reading of gate G8);
  * the specs (A10_spec.json, OP_spec.json): the template paths, the test logs equal the {{pytest:...}} logs of the
    template, must_equal equals the current sha256 (a difference is reported: the file changed after drafting),
    max_new_registered equals the number of framelease_v4 files the entry cites by sha256; the lines an A10 in-place
    text produces are at most 120 columns; the code the coverage reuses outside the manifest (must_equal files
    outside framelease_v4/) has the sha256 that gate2's config.json records;
  * AMENDMENTS2_DRAFT.md holds each template verbatim;
  * open preconditions of the entry texts (APPLY_PLAN2.md): step 0 done (commit_audit.py holds the horizon_cap rule
    that A10 finding 1 states), and the edits E1-E4 of build/AMEND/AMENDMENTS_DRAFT.md made (APPLY_PLAN2.md Sec. 3,
    step 0: the A9 list header and rule, A3 item 6, the A3 test log).
Exit 0 ("all checks passed") when every check passes and nothing is open, 1 on a problem, 2 when the checks pass but a
precondition is open (not ready for application).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path('/home/kang/Desktop/DAC')
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from framelease_v4.protocol import p1_driver as P1  # noqa: E402
from framelease_v4.protocol import phase_driver as PD  # noqa: E402

HERE = ROOT / 'outputs/framelease_v4/build/AMEND2'
FINAL = HERE / 'final'
DRAFT = HERE / 'AMENDMENTS2_DRAFT.md'
PROTOCOL = ROOT / 'framelease_v4/PROTOCOL.md'
MANIFEST = 'outputs/framelease_v4/registration/MANIFEST.sha256'
ENTRIES = {'OP': ('OP_phase_driver_entry.md', 'OP_spec.json'), 'A10': ('A10_entry.md', 'A10_spec.json')}
PLACEHOLDER = re.compile(r'\{\{([^}]+)\}\}')
FAKE_SHA = 'a' * 64
FAKE_DATETIME = '2026-11-15 10:00'
FAKE_FILES = '212'
OP_TITLE_MARK = '(Beijing time): the phase driver of Phases 2-7'   # the title line of the operational addition
GATE2_CONFIG = ROOT / 'outputs/framelease_v3/gate2_offline/gate2_20261109/config.json'
AMEND_DRAFT = ROOT / 'outputs/framelease_v4/build/AMEND/AMENDMENTS_DRAFT.md'
COMMIT_AUDIT = ROOT / 'framelease_v4/analysis/commit_audit.py'
# commit_audit.py of build/R7/dev/agg_p1 (A10 finding 1)
COMMIT_AUDIT_AGG_P1 = '96dd22c424ca2263c85843d31fd63bf5ae9019d6aa60c8ea35275b9126bff279'
# texts of build/AMEND/AMENDMENTS_DRAFT.md that APPLY_PLAN2.md Sec. 3, step 0 replaces before step 3 (whitespace
# flattened): (APPLY_PLAN2 edit, old text)
AMEND_OLD_TEXTS = (
    ('E1 (A9 list header)', 'What was run (every execution on real data, 2026-11-11).'),
    ('E2 (A9 rule)', '`analyze_v4.py` (R-4) is written and tested on synthetic CSVs only, as Sec. 9.12 states.'),
    ('E3 (A3 item 6)', 'A null commit margin passes only where the validity record names no relevant agent;'),
    ('E4 (A3 test log)',
     '* `framelease_v4/analysis/tests` and `framelease_v4/arms/tests/test_metrics_realized_keys.py`:'),
)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def pytest_summary(log):
    """The summary line of a pytest log, as apply_entry.py reads it."""
    lines = [ln.strip('= ').strip() for ln in Path(log).read_text(errors='replace').splitlines()
             if re.search(r'\d+ (passed|failed|error)', ln)]
    return lines[-1] if lines else ''


def drafting_log(app_log):
    """The drafting log that stands for a log written at application (same file name)."""
    return HERE / 'logs' / Path(app_log).name


def placeholder_problems(name, text, spec):
    """Unknown placeholder kinds, and {{sha256:path}} of a path that neither exists nor is written at application."""
    later = {t['log'] for t in spec.get('tests', [])} | {MANIFEST}
    out = []
    for key in PLACEHOLDER.findall(text):
        kind, _, arg = key.partition(':')
        if key in ('datetime', 'manifest:files'):
            continue
        if kind not in ('sha256', 'pytest'):
            out.append(f'{name}: unknown placeholder {{{{{key}}}}}')
        elif kind == 'sha256' and not (ROOT / arg).is_file() and arg not in later:
            out.append(f'{name}: {{{{{key}}}}} names a file that does not exist and is not written at application')
        elif kind == 'pytest' and arg not in later:
            out.append(f'{name}: {{{{{key}}}}} is not a test log of the spec')
    return out


def fill(text):
    """The template with every placeholder replaced by a value of the length it has at application."""
    def sub(m):
        key = m.group(1)
        if key == 'datetime':
            return FAKE_DATETIME
        if key == 'manifest:files':
            return FAKE_FILES
        kind, _, arg = key.partition(':')
        if kind == 'sha256':
            return sha256(ROOT / arg) if (ROOT / arg).is_file() else FAKE_SHA
        log = drafting_log(arg)
        return pytest_summary(log) if log.is_file() else '99 passed in 99.99s'
    return PLACEHOLDER.sub(sub, text)


def line_problems(name, filled):
    """Width and parser collisions of the filled entry text."""
    out = []
    lines = filled.splitlines()
    for i, ln in enumerate(lines, 1):
        if len(ln) > 120 and not ln.lstrip().startswith('|'):
            out.append(f'{name}: line {i} has {len(ln)} columns')
        if ln.startswith('## ') or ln.startswith(P1.ANCHOR):
            out.append(f'{name}: line {i} starts with a heading or the anchor')
        if ln.strip() in (P1.HEADING, PD.HEADING):
            out.append(f'{name}: line {i} is a driver heading')
        if P1.ENTRY_RE.match(ln) or PD.ENTRY_RE.match(ln):
            out.append(f'{name}: line {i} reads as a driver entry')
        if PD.AMEND_RE.match(ln) and not (name == 'A10' and i == 1):
            out.append(f'{name}: line {i} reads as an amendment title')
        if re.match(r'^\s*(\d+\)|[-+>#])(\s|$)', ln) or (re.match(r'^\s*\d+\.\s', ln) and not ln.startswith('  ')):
            out.append(f'{name}: line {i} starts like a list item, a quote or a heading Markdown would read')
    if name == 'A10' and not (PD.AMEND_RE.match(lines[0]) and PD.AMEND_RE.match(lines[0]).group('id') == 'A10'):
        out.append('A10: the first line is not read as the title of Amendment A10')
    if P1.ANCHOR in filled:                 # apply_entry.py inserts at text.index(ANCHOR) and needs it exactly once
        out.append(f'{name}: the text contains the anchor phrase "{P1.ANCHOR}"')
    if name == 'OP' and PD.A7B_RE.search(' '.join(filled.split())):
        out.append('OP: the text matches phase_driver.A7B_RE (read as part of an Amendment A7 placed above it)')
    return out


def insert_before_anchor(text, block):
    """apply_entry.py's insertion: the block as its own paragraph directly before the anchor paragraph."""
    k = text.index(P1.ANCHOR)
    return text[:k].rstrip('\n') + '\n\n' + block.strip('\n') + '\n\n' + text[k:]


def phase_heading_with_entry(text):
    """The phase driver's heading with one gate entry (its own insertion, phase_driver.insert_entry with cfg None)."""
    line = (f'* **G1 D1 decision** ({FAKE_DATETIME}, Beijing time). Decision `continue`; manifest and seal: '
            f'`MANIFEST.sha256`, {FAKE_FILES} files, sha256 `{"b" * 64}`, sealed with this entry.')
    return PD.insert_entry(None, text, [line])


def simulate(filled, specs):
    """Problems of the simulated application (module docstring). Before step 3 of APPLY_PLAN2.md the operational
    addition and the phase driver's heading with one gate entry are inserted first; once PROTOCOL.md holds them
    (the pre-check of A10, step 6), only A10 and its in-place texts are applied, and the phase driver's entries must
    stay as they read before."""
    out = []
    text = PROTOCOL.read_text(encoding='utf-8')
    try:
        p1_before = P1.protocol_view(None, text)['entries']
        if OP_TITLE_MARK not in text:
            text = insert_before_anchor(text, filled['OP'])
        if PD.phase_view(None, text)['heading'] is None:
            text = phase_heading_with_entry(text)
        phase_before = {k: v['text'] for k, v in PD.phase_view(None, text)['entries'].items()}
    except Exception as exc:                 # an ALERT of either driver's parser
        return [f'simulation (before A10): {type(exc).__name__}: {exc}']
    for r in specs['A10'].get('inplace', []):
        if text.count(r['old']) == 1:
            text = text.replace(r['old'], r['new'])
            k = text.index(r['new'])
            span = text[text.rfind('\n', 0, k) + 1:text.find('\n', k + len(r['new']) - 1)]
            out += [f'simulation: in-place text "{r["old"].strip()[:40]}": a line of {len(ln)} columns'
                    for ln in span.splitlines() if len(ln) > 120]
    text = insert_before_anchor(text, filled['A10'])
    try:
        pv = P1.protocol_view(None, text)
        view = PD.phase_view(None, text)
    except Exception as exc:                 # an ALERT of either driver's parser
        return out + [f'simulation: {type(exc).__name__}: {exc}']
    if {k: v['text'] for k, v in pv['entries'].items()} != {k: v['text'] for k, v in p1_before.items()}:
        out.append('simulation: the P1 driver entries changed')
    if {k: v['text'] for k, v in view['entries'].items()} != phase_before or not phase_before:
        out.append(f'simulation: the phase driver reads the entries {list(view["entries"])}, '
                   f'before A10 {list(phase_before)}')
    if 'A10' not in view['amendments'] or len(view['amendments']['A10']) != 1:
        out.append(f'simulation: amendment titles read: {view["amendments"]}')
    a_sha = sha256(ROOT / 'framelease_v4/analysis/analyze_v4.py')
    s, e = view['sec']
    line = next((i + 1 for i in range(s, e) if a_sha in view['lines'][i]), None)
    owner = PD.citing_amendment(view, line) if line else None
    if owner != 'A10':
        out.append(f'simulation: the first Sec. 13.2 line citing analyze_v4.py ({line}) belongs to {owner!r}, not A10')
    heading = view['heading']
    op_lines = [i for i in range(s, e) if OP_TITLE_MARK in view['lines'][i]]
    if len(op_lines) != 1 or heading is None or not op_lines[0] < heading < view['anchor']:
        out.append(f'simulation: the phase heading ({heading}) is not between the one operational addition '
                   f'(lines {op_lines}) and the anchor')
    return out


def spec_problems(name, template, spec, filled):
    """Spec against template and tree (module docstring)."""
    out = []
    if (ROOT / spec['template']).resolve() != (FINAL / ENTRIES[name][0]).resolve():
        out.append(f'{name}: spec template {spec["template"]}')
    logs = {k.partition(':')[2] for k in PLACEHOLDER.findall(template) if k.startswith('pytest:')}
    if logs != {t['log'] for t in spec['tests']}:
        out.append(f'{name}: template logs {sorted(logs)} != spec logs')
    for p, want in spec.get('must_equal', {}).items():
        have = sha256(ROOT / p)
        if have != want:
            out.append(f'{name}: {p} changed after drafting ({want[:12]} -> {have[:12]}): re-check its review')
    cited = sorted({k.partition(':')[2] for k in PLACEHOLDER.findall(template)
                    if k.startswith('sha256:framelease_v4/')})
    if spec.get('max_new_registered') != len(cited):
        out.append(f'{name}: max_new_registered {spec.get("max_new_registered")} != {len(cited)} cited files')
    return out


def reused_problems(spec):
    """The code the coverage reuses outside the manifest (A10 "Evidence"; spec must_equal outside framelease_v4/):
    each file's sha256 must be the one gate2's config.json records."""
    rec = GATE2_CONFIG.read_text(encoding='utf-8') if GATE2_CONFIG.is_file() else ''
    return [f'A10: {p} sha256 is not the one recorded in {GATE2_CONFIG.relative_to(ROOT)}'
            for p in spec.get('must_equal', {}) if not p.startswith('framelease_v4/') and sha256(ROOT / p) not in rec]


def open_items():
    """Preconditions of the entry texts that are not met yet (APPLY_PLAN2.md): step 0 (A10 finding 1 states the
    settled commit-audit rule) and the edits E1-E4 of the AMEND drafts (Sec. 3, step 0)."""
    out = []
    src = COMMIT_AUDIT.read_text(encoding='utf-8')
    if sha256(COMMIT_AUDIT) == COMMIT_AUDIT_AGG_P1 or 'horizon_cap' not in src:
        out.append('step 0: commit_audit.py does not hold the horizon_cap rule that A10 finding 1 states')
    flat = ' '.join(AMEND_DRAFT.read_text(encoding='utf-8').split()) if AMEND_DRAFT.is_file() else ''
    out += [f'{edit}: build/AMEND/AMENDMENTS_DRAFT.md still holds "{old[:60]}..."'
            for edit, old in AMEND_OLD_TEXTS if old in flat]
    return out


def draft_problems(templates):
    if not DRAFT.is_file():
        return [f'{DRAFT.name} missing']
    text = DRAFT.read_text(encoding='utf-8')
    return [f'{DRAFT.name} does not hold {ENTRIES[n][0]} verbatim' for n, t in templates.items()
            if t.strip('\n') not in text]


def main():
    templates = {n: (FINAL / t).read_text(encoding='utf-8') for n, (t, _) in ENTRIES.items()}
    specs = {n: json.loads((FINAL / s).read_text(encoding='utf-8')) for n, (_, s) in ENTRIES.items()}
    filled = {n: fill(t) for n, t in templates.items()}
    problems = []
    for n in ENTRIES:
        problems += placeholder_problems(n, templates[n], specs[n])
        problems += line_problems(n, filled[n])
        problems += spec_problems(n, templates[n], specs[n], filled[n])
    problems += simulate(filled, specs)
    problems += reused_problems(specs['A10'])
    problems += draft_problems(templates)
    opened = open_items()
    for n in ENTRIES:
        keys = PLACEHOLDER.findall(templates[n])
        print(f'{n}: {len(filled[n].splitlines())} lines, {len(keys)} placeholders, '
              f'{sum(k.startswith("sha256:framelease_v4/") for k in set(keys))} framelease_v4 files cited by sha256')
    text = PROTOCOL.read_text(encoding='utf-8')
    for r in specs['A10']['inplace']:
        print(f'A10 in-place found {text.count(r["old"])}x now: {r["old"].strip()[:70]!r}')
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
