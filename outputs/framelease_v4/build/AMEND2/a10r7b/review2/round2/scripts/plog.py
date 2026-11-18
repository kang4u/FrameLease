"""Append one PROGRESS line (wrapped at 120 columns, '- ' then '  ') to review2/PROGRESS.md.

usage: plog.py TEXT...           append
       plog.py --rewrap-last     rewrap the last line of the file (it was appended unwrapped)
"""
import sys
import textwrap
from pathlib import Path

P = Path('/home/kang/Desktop/DAC/outputs/framelease_v4/build/AMEND2/a10r7b/review2/PROGRESS.md')


def wrap(text):
    text = ' '.join(text.split())
    if text.startswith('- '):
        text = text[2:]
    return '\n'.join(textwrap.wrap(text, width=120, initial_indent='- ', subsequent_indent='  ',
                                   break_long_words=False, break_on_hyphens=False)) + '\n'


if sys.argv[1:] == ['--rewrap-last']:
    lines = P.read_text(encoding='utf-8').splitlines(keepends=True)
    last = lines.pop()
    P.write_text(''.join(lines) + wrap(last), encoding='utf-8')
else:
    with open(P, 'a', encoding='utf-8') as fh:
        fh.write(wrap(' '.join(sys.argv[1:])))
print(P.read_text(encoding='utf-8').splitlines()[-1][:120])
