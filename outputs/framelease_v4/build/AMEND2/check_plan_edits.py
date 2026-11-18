"""The edits E1-E4 of APPLY_PLAN2.md Sec. 3, step 0, against check_drafts.AMEND_OLD_TEXTS and a copy of the AMEND draft
(read only; writes only /tmp/AMEND2/AMENDMENTS_DRAFT_E.md): each old text equals check_drafts' and occurs once in
build/AMEND/AMENDMENTS_DRAFT.md; with E1-E4 applied to the copy, check_drafts.open_items reports step 0 only."""
import importlib.util
import re
from pathlib import Path

H = Path('/home/kang/Desktop/DAC/outputs/framelease_v4/build/AMEND2')
spec = importlib.util.spec_from_file_location('check_drafts', H / 'check_drafts.py')
CD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CD)
plan = ' '.join((H / 'APPLY_PLAN2.md').read_text(encoding='utf-8').split())
t = CD.AMEND_DRAFT.read_text(encoding='utf-8')
for label, old in CD.AMEND_OLD_TEXTS:
    e = label.split()[0]
    m = re.search(re.escape(e) + r', [^.]*?\. Old: "(.*?)"\.? New: "(.*?)"', plan)
    assert m and m.group(1) == old, (e, m and m.group(1))
    pat = r'\s+'.join(re.escape(w) for w in old.split())
    assert len(re.findall(pat, t)) == 1, e
    t = re.sub(pat, lambda _: m.group(2), t)
    print(e, 'plan old == check_drafts old; new:', m.group(2)[:70])
Path('/tmp/AMEND2').mkdir(exist_ok=True)
p = Path('/tmp/AMEND2/AMENDMENTS_DRAFT_E.md')
p.write_text(t, encoding='utf-8')
CD.AMEND_DRAFT = p
print('open after E1-E4:', CD.open_items())
