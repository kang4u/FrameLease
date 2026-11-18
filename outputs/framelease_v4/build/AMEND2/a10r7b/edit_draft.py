"""Bring outputs/framelease_v4/build/AMEND2/AMENDMENTS2_DRAFT.md in line with the edited A10 template (item a10r7b).

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/a10r7b/edit_draft.py [--check]

Three replacements. A step whose new text the draft already holds once is skipped; otherwise its old text must be
found exactly once (else nothing is written, exit 1):
  1. the embedded A10 template -> final/A10_entry.md. The old text is the block from the A10 title line
     "**Amendment A10, {{datetime}} (Beijing time):" (exactly once in the draft) to the end of the first manifest line
     "`{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry." after it, whatever
     version of the template the draft holds; final/A10_entry.md must begin and end with the same two markers;
  2. the last sentence of the A10 preface (second and fifth in-place texts) -> their state after step 3;
  3. after the appendix code block, the sha256 of the three files the edited template adds to "Evidence".
--check: report whether the draft already holds the edited template verbatim (exit 0) or not (exit 1); write nothing.
The draft is written through a temporary file in the same directory and renamed, and only when a step changed it.
"""
import hashlib
import os
import sys
from pathlib import Path

ROOT = Path('/home/kang/Desktop/DAC')
AM2 = ROOT / 'outputs/framelease_v4/build/AMEND2'
DRAFT = AM2 / 'AMENDMENTS2_DRAFT.md'
NEW_T = AM2 / 'final/A10_entry.md'
START = '**Amendment A10, {{datetime}} (Beijing time):'
END = '`{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.'
ADDED = ('outputs/framelease_v4/build/AGG/step0_reaudit/SHA256SUMS',
         'outputs/framelease_v4/build/R7B/dev/agg_now/SHA256SUMS',
         'outputs/framelease_v4/build/R7B/dev/agg_snap_2203/SHA256SUMS')

PREFACE_OLD = """drives `apply_entry.py` (`--tests`, then `--apply` under the lock); its second in-place text starts at the end of the
Sec. 9.12 paragraph that A9 extends, and its fifth exists only after A3: both are confirmed after step 3
(`APPLY_PLAN2.md` Sec. 4).
"""
PREFACE_NEW = """drives `apply_entry.py` (`--tests`, then `--apply` under the lock); its second in-place text starts at the end of the
Sec. 9.12 paragraph that A9 extends and occurs once in the PROTOCOL.md sealed with step 3 (2026-11-15 06:40); its
fifth is the Sec. 4.1 status paragraph of A3 as sealed then, derived by `a10r7b/derive_inplace5.py`
(`a10r7b/RUNBOOK.md`).
"""
APPENDIX_ANCHOR = """48417c1fc9ce6d0e7d604da1292f6a002ab266c500f9226b4cd17fbbf490691c  framelease_v3/suffix_lease_eval.py
```
"""


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def template_block(text):
    """The embedded A10 template of the draft (from its title line to the end of its manifest line), or None."""
    if text.count(START) != 1:
        return None
    s = text.index(START)
    e = text.find(END, s)
    return None if e < 0 else text[s:e + len(END)]


def main():
    text = DRAFT.read_text(encoding='utf-8')
    new_t = NEW_T.read_text(encoding='utf-8').strip('\n')
    if '--check' in sys.argv[1:]:
        ok = text.count(new_t) == 1
        print('the draft holds final/A10_entry.md verbatim' if ok else 'the draft does NOT hold final/A10_entry.md')
        return 0 if ok else 1
    if not (new_t.startswith(START) and new_t.endswith(END)):
        print('STOP: final/A10_entry.md does not begin with the A10 title or end with its manifest line')
        return 1
    added = ''.join(f'{sha(ROOT / p)}  {p}\n' for p in ADDED)
    appendix_new = (APPENDIX_ANCHOR + '\nAdded on 2026-11-15 (item a10r7b: A10 "Evidence", the development '
                    'aggregations and the re-audit of\ndeviation 1 and finding 1):\n\n```\n' + added + '```\n')
    steps = ((template_block(text), new_t, 'embedded A10 template'), (PREFACE_OLD, PREFACE_NEW, 'A10 preface'),
             (APPENDIX_ANCHOR, appendix_new, 'appendix'))
    report = []
    for old, new, what in steps:
        if text.count(new) == 1:
            report.append(f'{what}: held already')
            continue
        if not old or text.count(old) != 1:
            print(f'STOP: {what}: the old text occurs {text.count(old) if old else 0} times (exactly 1 expected); '
                  'nothing written')
            return 1
        text = text.replace(old, new)
        report.append(f'{what}: replaced')
    if all(r.endswith('held already') for r in report):
        print('nothing to change:', '; '.join(report))
        return 0
    long = [i for i, ln in enumerate(text.splitlines(), 1) if len(ln) > 120 and not ln.lstrip().startswith('|')
            and not ln.startswith(tuple('0123456789abcdef'))]
    tmp = DRAFT.with_name('.' + DRAFT.name + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    os.replace(tmp, DRAFT)
    print(f'written {DRAFT.relative_to(ROOT)}: {"; ".join(report)}; prose lines over 120 columns: {long or "none"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
