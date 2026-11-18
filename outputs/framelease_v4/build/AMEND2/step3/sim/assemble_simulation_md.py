"""Fill the @@EMBED...@@ markers of step3/SIMULATION.md with the evidence files of step3/sim_output/ (in place; each
file in a fenced block). Run once after sim/run_simulation.sh and the copy of its outputs into sim_output/."""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / 'sim_output'
DOC = HERE / 'SIMULATION.md'


def fence(text):
    return '```text\n' + text.rstrip('\n') + '\n```'


def diff_outside_13_2():
    hunks = re.split(r'(?m)^(?=@@ )', (OUT / 'protocol_step3.diff').read_text(encoding='utf-8'))
    keep = [h for h in hunks if h.startswith('@@ ') and '**Amendment A3,' not in h]
    return fence(''.join(keep))


def g1_entry():
    lines = (OUT / 'phase_driver_dry_run_after_decision.txt').read_text(encoding='utf-8').splitlines()
    return fence('\n'.join(ln.split('| ', 1)[1] for ln in lines if ln.startswith('      | ')))


def a10():
    s = json.loads((OUT / 'a10_inplace5_suggestion.json').read_text(encoding='utf-8'))
    return 'old:\n\n' + fence(s['old']) + '\n\nnew:\n\n' + fence(s['new'])


def main():
    text = DOC.read_text(encoding='utf-8')
    text = text.replace('@@EMBED_DIFF_OUTSIDE_13_2@@', diff_outside_13_2())
    text = text.replace('@@EMBED_G1@@', g1_entry())
    text = text.replace('@@EMBED_A10@@', a10())
    text = re.sub(r'@@EMBED ([^@]+)@@', lambda m: fence((OUT / m.group(1)).read_text(encoding='utf-8')), text)
    if '@@EMBED' in text:
        print('unfilled marker')
        return 1
    DOC.write_text(text, encoding='utf-8')
    print(f'{DOC}: {len(text.splitlines())} lines')
    return 0


if __name__ == '__main__':
    sys.exit(main())
