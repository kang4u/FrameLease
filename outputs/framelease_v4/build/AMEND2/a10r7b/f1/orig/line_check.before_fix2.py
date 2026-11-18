"""Line and parser check of a composed PROTOCOL.md against the sealed one (item F1A11; read only).

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/a10r7b/f1/line_check.py BEFORE AFTER [--expect A10,A11]

BEFORE is the sealed PROTOCOL.md, AFTER the text with the amendments inserted (a scratch copy, e.g. the PROTOCOL.md of
a sim_tree.py tree after A10 and A11). Checks of the lines that AFTER adds or changes (difflib): prose lines at most
120 columns (table rows excepted); no line that p1_driver or phase_driver reads as an entry, no driver heading, no
Markdown heading, no Sec. 13.2 start, no line that a driver reads as an amendment title other than the titles of the
expected amendments (each exactly once); no line holds 'TODO' or an unfilled placeholder. Whole text: the anchor
phrase and the Sec. 13.2 heading once each; p1_driver.protocol_view and phase_driver.phase_view read it without an
exception, with the entries of both drivers unchanged and every amendment of BEFORE still read; each expected
amendment read exactly once; a later gate entry of the phase driver (phase_driver.insert_entry) is read.
Exit 0 all checks passed, 1 a problem.
"""
import argparse
import difflib
import sys
from pathlib import Path

ROOT = Path('/home/kang/Desktop/DAC')
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from framelease_v4.protocol import p1_driver as P1  # noqa: E402
from framelease_v4.protocol import phase_driver as PD  # noqa: E402

WIDTH = 120
GATE_LINE = ('* **G3 P2 data manifest** (2026-11-15 23:59, Beijing time). Simulated gate entry; manifest and seal: '
             '`MANIFEST.sha256`, 231 files, sha256 `' + 'd' * 64 + '`, sealed with this entry.')


def added_lines(before, after):
    out = []
    sm = difflib.SequenceMatcher(None, before, after, autojunk=False)
    for tag, _, _, j1, j2 in sm.get_opcodes():
        if tag in ('replace', 'insert'):
            out += [(j + 1, after[j]) for j in range(j1, j2)]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('before')
    ap.add_argument('after')
    ap.add_argument('--expect', default='A10,A11')
    a = ap.parse_args(argv)
    expect = [x for x in a.expect.split(',') if x]
    tb = Path(a.before).read_text(encoding='utf-8')
    ta = Path(a.after).read_text(encoding='utf-8')
    new = added_lines(tb.splitlines(), ta.splitlines())
    probs, titles = [], []
    for n, ln in new:
        table = ln.lstrip().startswith('|')
        if len(ln) > WIDTH and not table:
            probs.append(f'line {n}: {len(ln)} columns')
        if P1.ENTRY_RE.match(ln) or PD.ENTRY_RE.match(ln):
            probs.append(f'line {n}: read as a driver entry')
        if ln.strip() in (P1.HEADING, PD.HEADING) or ln.startswith('#') or ln.startswith(P1.ANCHOR):
            probs.append(f'line {n}: a heading, a driver heading or the anchor')
        m = PD.AMEND_RE.match(ln)
        if m:
            titles.append(m.group('id'))
        if 'TODO' in ln or '{{' in ln or '}}' in ln:
            probs.append(f'line {n}: TODO or an unfilled placeholder')
    if sorted(titles) != sorted(expect):
        probs.append(f'amendment titles among the added lines: {titles}, expected {expect}')
    for label, phrase in (('anchor phrase', P1.ANCHOR), ('Sec. 13.2 heading', '### 13.2 Amendments')):
        if ta.count(phrase) != 1:
            probs.append(f'{label} occurs {ta.count(phrase)} times')
    try:
        p1b, p1a = P1.protocol_view(None, tb), P1.protocol_view(None, ta)
        pdb, pda = PD.phase_view(None, tb), PD.phase_view(None, ta)
        later = PD.phase_view(None, PD.insert_entry(None, ta, [GATE_LINE]))
    except Exception as exc:                                   # a parser that raises is a problem, not a crash
        probs.append(f'parsers: {type(exc).__name__}: {exc}')
        p1b = p1a = pdb = pda = later = None
    if pda is not None:
        if {k: v['text'] for k, v in p1a['entries'].items()} != {k: v['text'] for k, v in p1b['entries'].items()}:
            probs.append('the P1 driver entries changed')
        if {k: v['text'] for k, v in pda['entries'].items()} != {k: v['text'] for k, v in pdb['entries'].items()}:
            probs.append('the phase driver entries changed')
        lost = sorted(set(pdb['amendments']) - set(pda['amendments']))
        if lost:
            probs.append(f'amendments of BEFORE no longer read: {lost}')
        for x in expect:
            if len(pda['amendments'].get(x, [])) != 1:
                probs.append(f'Amendment {x} read at lines {pda["amendments"].get(x)}')
        if len(later['entries']) != len(pda['entries']) + 1:
            probs.append('a later gate entry is not read')
    wide = sum(1 for _, ln in new if len(ln) > WIDTH)
    rows = sum(1 for _, ln in new if ln.lstrip().startswith('|'))
    print(f'{a.after}: {len(new)} added or changed lines ({rows} table rows, {wide} lines over {WIDTH} columns, '
          f'all of them table rows: {all(ln.lstrip().startswith("|") for _, ln in new if len(ln) > WIDTH)}); '
          f'amendment titles {titles}')
    if pda is not None:
        print(f'phase driver: {len(pda["entries"])} entries, amendments {sorted(pda["amendments"])}; later gate entry '
              f'read: {len(later["entries"]) == len(pda["entries"]) + 1}; P1 entries {len(p1a["entries"])}')
    if probs:
        print('\n'.join(probs))
        return 1
    print('all checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
