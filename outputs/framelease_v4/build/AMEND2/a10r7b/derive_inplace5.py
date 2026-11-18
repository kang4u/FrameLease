"""Derive the fifth in-place text of Amendment A10 from a PROTOCOL.md that holds Amendment A3 (read only on PROTOCOL).

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/a10r7b/derive_inplace5.py [--protocol P] [--template T] [--spec S]
      [--write OUT]

The text (APPLY_PLAN2.md Sec. 4, step 1, "the fifth in-place text"): Sec. 4.1 holds, after item 4 of "Still required,
not needed for Phase 1", the status paragraph that Amendment A3 inserted (with the sentence that Amendment A4 appended).
Amendment A10 replaces the clause OLD of that paragraph by NEW, both quoted in the "In-place text" bullet of the A10
template ('Sec. 4.1, the status sentence of Amendment A3: "OLD" becomes "NEW"'). A3's own entry quotes the same clause
in Sec. 13.2, wrapped and indented differently; that quotation is never touched.

Procedure (every step must hold, else exit 1 and nothing is written):
  1. OLD and NEW are read from the template (default final/A10_entry.md), whitespace flattened.
  2. In PROTOCOL.md (default framelease_v4/PROTOCOL.md; --protocol for a scratch copy), the section from the heading
     '### 4.1' to the heading '### 4.2' holds exactly one paragraph that starts with 'Status (Amendment A3):'; its
     flattened text holds OLD exactly once.
  3. "old" = that paragraph exactly as it stands (its lines, its indentation, the final newline); "new" = the paragraph
     with OLD replaced by NEW, rewrapped greedily at 120 columns with the indentation of its first line (words are
     never split; a line keeps every word that fits).
  4. Checks: "old" occurs exactly once in the whole PROTOCOL.md (apply_entry.py requires it); the flattened "new"
     equals the flattened "old" with OLD replaced by NEW; no line of "new" is longer than 120 columns, starts like a
     list item, a quote or a heading Markdown would read, or reads as a driver heading, a driver entry
     (p1_driver.ENTRY_RE, phase_driver.ENTRY_RE) or an amendment title (phase_driver.AMEND_RE); the paragraph lies
     outside Sec. 13.2.
  5. Output: the derived {"old", "new"} as JSON and the changed lines. With --spec S (default final/A10_spec.json) the
     spec's in-place text whose flattened "old" holds OLD is identified (exactly one) and compared; --write OUT writes
     a copy of the spec with that in-place text replaced (OUT may be the spec itself; written through a temporary file
     in the same directory and renamed). Without --write nothing is written.
Exit codes: 0 derived and checked (and, with --spec but without --write, the spec already holds the derived text: 0;
it holds another text: 3), 1 a failed step.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path('/home/kang/Desktop/DAC')
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from framelease_v4.protocol import p1_driver as P1  # noqa: E402
from framelease_v4.protocol import phase_driver as PD  # noqa: E402

TEMPLATE = ROOT / 'outputs/framelease_v4/build/AMEND2/final/A10_entry.md'
SPEC = ROOT / 'outputs/framelease_v4/build/AMEND2/final/A10_spec.json'
PROTOCOL = ROOT / 'framelease_v4/PROTOCOL.md'
WIDTH = 120
STATUS_START = 'Status (Amendment A3):'
BULLET_RE = re.compile(r'Sec\. 4\.1, the status sentence of Amendment A3: "(?P<old>[^"]+)" becomes "(?P<new>[^"]+)"')


class Fail(Exception):
    pass


def flat(text):
    return ' '.join(text.split())


def clauses(template_text):
    """(OLD, NEW) of the Sec. 4.1 in-place bullet of the A10 template, whitespace flattened."""
    m = list(BULLET_RE.finditer(flat(template_text)))
    if len(m) != 1:
        raise Fail(f'the template holds {len(m)} Sec. 4.1 status bullets (exactly 1 expected)')
    return m[0].group('old'), m[0].group('new')


def section_41(lines):
    """(start, end) line indices of Sec. 4.1: from '### 4.1' up to '### 4.2'."""
    starts = [i for i, ln in enumerate(lines) if ln.startswith('### 4.1 ')]
    ends = [i for i, ln in enumerate(lines) if ln.startswith('### 4.2 ')]
    if len(starts) != 1 or len(ends) != 1 or not starts[0] < ends[0]:
        raise Fail(f'Sec. 4.1 headings: {len(starts)} x "### 4.1", {len(ends)} x "### 4.2"')
    return starts[0], ends[0]


def status_paragraph(lines, s, e):
    """(first, last) line indices of the one paragraph in [s, e) that starts with STATUS_START."""
    firsts = [i for i in range(s, e) if lines[i].lstrip().startswith(STATUS_START)
              and (i == 0 or not lines[i - 1].strip())]
    if len(firsts) != 1:
        raise Fail(f'Sec. 4.1 holds {len(firsts)} paragraphs that start with "{STATUS_START}" (exactly 1 expected; '
                   'Amendment A3 inserts it)')
    i = j = firsts[0]
    while j + 1 < e and lines[j + 1].strip():
        j += 1
    return i, j


def wrap(words, indent):
    """Greedy wrap at WIDTH columns; every line starts with indent; words are never split."""
    out, cur = [], ''
    for w in words:
        if not cur:
            cur = indent + w
        elif len(cur) + 1 + len(w) <= WIDTH:
            cur += ' ' + w
        else:
            out.append(cur)
            cur = indent + w
    if cur:
        out.append(cur)
    return out


def line_problems(lines):
    """The line rules of check_drafts.line_problems for text that is not an entry title."""
    out = []
    for k, ln in enumerate(lines, 1):
        if len(ln) > WIDTH:
            out.append(f'line {k} has {len(ln)} columns')
        if ln.startswith('## ') or ln.startswith(P1.ANCHOR) or ln.strip() in (P1.HEADING, PD.HEADING):
            out.append(f'line {k} starts with a heading, the anchor or a driver heading')
        if P1.ENTRY_RE.match(ln) or PD.ENTRY_RE.match(ln) or PD.AMEND_RE.match(ln):
            out.append(f'line {k} reads as a driver entry or an amendment title')
        if re.match(r'^\s*(\d+\)|[-+>#])(\s|$)', ln) or re.match(r'^\s*\d+\.\s', ln):
            out.append(f'line {k} starts like a list item, a quote or a heading')
    return out


def derive(protocol_text, template_text):
    old_clause, new_clause = clauses(template_text)
    lines = protocol_text.split('\n')
    s, e = section_41(lines)
    i, j = status_paragraph(lines, s, e)
    par = lines[i:j + 1]
    flat_old = flat('\n'.join(par))
    if flat_old.count(old_clause) != 1:
        raise Fail(f'the status paragraph (lines {i + 1}-{j + 1}) holds the clause {flat_old.count(old_clause)} times '
                   f'(exactly 1 expected): "{old_clause}"')
    indent = par[0][:len(par[0]) - len(par[0].lstrip())]
    new_lines = wrap(flat_old.replace(old_clause, new_clause).split(' '), indent)
    old = '\n'.join(par) + '\n'
    new = '\n'.join(new_lines) + '\n'
    problems = []
    if protocol_text.count(old) != 1:
        problems.append(f'"old" occurs {protocol_text.count(old)} times in PROTOCOL.md (exactly 1 expected)')
    if flat(new) != flat_old.replace(old_clause, new_clause):
        problems.append('the flattened "new" is not the flattened "old" with the clause replaced')
    problems += [f'"new": {p}' for p in line_problems(new_lines)]
    sec13 = next((k for k, ln in enumerate(lines) if ln.startswith('### 13.2')), None)
    if sec13 is not None and i >= sec13:
        problems.append('the status paragraph lies in Sec. 13.2')
    if problems:
        raise Fail('; '.join(problems))
    return {'old': old, 'new': new, 'lines': (i + 1, j + 1), 'old_clause': old_clause, 'new_clause': new_clause}


def spec_index(spec, old_clause):
    hits = [k for k, r in enumerate(spec.get('inplace', [])) if old_clause in flat(r['old'])]
    if len(hits) != 1:
        raise Fail(f'the spec holds {len(hits)} in-place texts whose "old" holds the clause (exactly 1 expected)')
    return hits[0]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--protocol', default=str(PROTOCOL))
    ap.add_argument('--template', default=str(TEMPLATE))
    ap.add_argument('--spec', default=None, help=f'spec to compare or update (e.g. {SPEC.relative_to(ROOT)})')
    ap.add_argument('--write', default=None, help='write the updated spec here (requires --spec)')
    a = ap.parse_args(argv)
    try:
        d = derive(Path(a.protocol).read_text(encoding='utf-8'), Path(a.template).read_text(encoding='utf-8'))
    except Fail as exc:
        print(f'FAIL: {exc}')
        return 1
    print(f'protocol {a.protocol}: Sec. 4.1 status paragraph, lines {d["lines"][0]}-{d["lines"][1]}')
    print(json.dumps({'old': d['old'], 'new': d['new']}, indent=1, ensure_ascii=False))
    for tag, txt in (('-', d['old']), ('+', d['new'])):
        for ln in txt.splitlines():
            print(f'{tag} {ln}')
    if a.write and not a.spec:
        print('FAIL: --write needs --spec')
        return 1
    if not a.spec:
        return 0
    spec = json.loads(Path(a.spec).read_text(encoding='utf-8'))
    try:
        k = spec_index(spec, d['old_clause'])
    except Fail as exc:
        print(f'FAIL: {exc}')
        return 1
    same = spec['inplace'][k] == {'old': d['old'], 'new': d['new']}
    print(f'spec {a.spec}: in-place text {k + 1} ' + ('equals the derived text' if same else 'differs from the '
                                                       'derived text'))
    if not a.write:
        return 0 if same else 3
    spec['inplace'][k] = {'old': d['old'], 'new': d['new']}
    out = Path(a.write)
    tmp = out.with_name('.' + out.name + '.tmp')
    tmp.write_text(json.dumps(spec, indent=1) + '\n', encoding='utf-8')
    os.replace(tmp, out)
    print(f'written: {out} (in-place text {k + 1})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
