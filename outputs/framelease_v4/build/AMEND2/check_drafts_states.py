"""check_drafts.simulate on PROTOCOL.md states before and after step 3 of APPLY_PLAN2.md (read only; writes only
/tmp/AMEND2/PROTOCOL_sim.md). Exit 0 when every state gives the expected result."""
import importlib.util
import json
import sys
import textwrap
from pathlib import Path

H = Path('/home/kang/Desktop/DAC/outputs/framelease_v4/build/AMEND2')
spec = importlib.util.spec_from_file_location('check_drafts', H / 'check_drafts.py')
CD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CD)
real = CD.PROTOCOL
templates = {n: (CD.FINAL / t).read_text(encoding='utf-8') for n, (t, _) in CD.ENTRIES.items()}
specs = {n: json.loads((CD.FINAL / s).read_text(encoding='utf-8')) for n, (_, s) in CD.ENTRIES.items()}
filled = {n: CD.fill(t) for n, t in templates.items()}
base = real.read_text(encoding='utf-8')
Path('/tmp/AMEND2').mkdir(exist_ok=True)


def run(label, text, expect_ok):
    p = Path('/tmp/AMEND2/PROTOCOL_sim.md')
    p.write_text(text, encoding='utf-8')
    CD.PROTOCOL = p
    probs = CD.simulate(filled, specs)
    ok = (not probs) == expect_ok
    print('PASS' if ok else 'FAIL', label, probs[:3])
    return ok


after3 = CD.insert_before_anchor(base, filled['OP'].replace('2026-11-15 10:00', '2026-11-15 09:00'))
res = [run('before step 3 (current PROTOCOL.md)', base, True),
       run('after step 3, no phase heading yet', after3, True),
       run('after step 3 and the G1 entry', CD.phase_heading_with_entry(after3), True),
       run('the OP entry twice', CD.insert_before_anchor(after3, filled['OP']), False)]
# A9 in-place sentence with the Code paragraph rewrapped at 120 columns (one plausible form of step 3)
a = base.index('**Code.** `framelease_v4/analysis/aggregate_v4.py`')
b = base.index('\n\n**Freeze.**', a)
para = ' '.join(base[a:b].split()).replace(
    'Both are written and tested on synthetic CSVs only.', 'Both are written and tested on synthetic CSVs only. The '
    'aggregator was also run read-only on finished P1 training-route runs during development (Amendment A9).')
a9 = base[:a] + '\n'.join(textwrap.wrap(para, 120)) + base[b:]
print('A9-rewrapped Code paragraph, last line:', repr(a9[:a9.index('\n\n**Freeze.**')].rsplit('\n', 1)[1]))
CD.PROTOCOL = Path('/tmp/AMEND2/PROTOCOL_sim.md')
Path('/tmp/AMEND2/PROTOCOL_sim.md').write_text(a9, encoding='utf-8')
print('A9-rewrapped: in-place 2 found', a9.count(specs['A10']['inplace'][1]['old']), 'x; simulate:',
      CD.simulate(filled, specs))
CD.PROTOCOL = real
sys.exit(0 if all(res) else 1)
