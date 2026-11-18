"""Post-check of Amendment A10 or A11 on the project after its application (read only; writes nothing).

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/a10r7b/post_check.py A10|A11 [--root SCRATCH_TREE]

Checks: registration.py --verify (manifest OK and both seal lines OK); PROTOCOL.md parses without an ALERT of
p1_driver.protocol_view and phase_driver.phase_view; the amendment is read exactly once (and A10 before A11); the first
Sec. 13.2 line citing analyze_v4.py belongs to A10 and, for A11, the lines citing the two R7B files belong to A11
(phase_driver.citing_amendment); phase_driver.analysis_registration has no wait reason (A10 registers the analysis
code that gate G8 needs); every in-place text of the spec is applied (its "new" occurs once, its "old" no more, unless
the "new" contains the "old"); no phase_driver/ALERT.txt or protocol_txn.json; the files the entry cites by sha256 are
in phase_driver/registered_baseline.json at that sha256 once the phase driver's next cycle has refreshed it (reported as
'pending' before that). Exit 0 all passed, 1 a failure, 3 only the baseline refresh is pending. --root: a scratch
tree of the dry run instead of the project (the specs are always the project's).
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path('/home/kang/Desktop/DAC')
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from framelease_v4.protocol import p1_driver as P1  # noqa: E402
from framelease_v4.protocol import phase_driver as PD  # noqa: E402

SPECS = {'A10': ROOT / 'outputs/framelease_v4/build/AMEND2/final/A10_spec.json',
         'A11': ROOT / 'outputs/framelease_v4/build/AMEND2/a10r7b/A11_spec.json'}
FILES = {'A10': ('framelease_v4/analysis/analyze_v4.py', 'framelease_v4/analysis/prop1_coverage.py',
                 'framelease_v4/analysis/figures_tables.py', 'framelease_v4/analysis/verify_independent.py',
                 'framelease_v4/analysis/tests/test_analyze_v4.py',
                 'framelease_v4/analysis/tests/test_prop1_coverage.py',
                 'framelease_v4/analysis/tests/test_figures_tables.py',
                 'framelease_v4/analysis/tests/test_verify_independent.py'),
         'A11': ('framelease_v4/analysis/verify_table1_extra.py',
                 'framelease_v4/analysis/tests/test_verify_table1_extra.py')}
PHASE = ROOT / 'outputs/framelease_v4/phase_driver'


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    global ROOT, PHASE
    args = sys.argv[1:]
    name = args[0] if args else ''
    if '--root' in args:
        ROOT = Path(args[args.index('--root') + 1])
        PHASE = ROOT / 'outputs/framelease_v4/phase_driver'
    if name not in SPECS:
        print('usage: post_check.py A10|A11 [--root SCRATCH_TREE]')
        return 1
    fails, pending = [], []
    r = subprocess.run([str(ROOT / '.conda-unidrive-linux/bin/python'), '-I', '-B',
                        str(ROOT / 'framelease_v4/protocol/registration.py'), '--verify'],
                       cwd=ROOT, capture_output=True, text=True)
    seal_ok = r.stdout.count(': OK') == 3 and 'FAIL' not in r.stdout
    print('registration --verify:', r.stdout.strip().replace('\n', ' | '))
    if not seal_ok:
        fails.append('registration.py --verify')
    text = (ROOT / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    try:
        P1.protocol_view(None, text)
        view = PD.phase_view(None, text)
    except Exception as exc:
        print(f'FAIL: parser: {type(exc).__name__}: {exc}')
        return 1
    seen = {a: view['amendments'].get(a, []) for a in ('A10', 'A11')}
    print('amendment titles at lines:', seen)
    if len(seen[name]) != 1:
        fails.append(f'{name} read {len(seen[name])} times')
    if name == 'A11' and not (len(seen['A10']) == 1 and seen['A10'][0] < seen['A11'][0]):
        fails.append('A10 is not entered once before A11')
    s, e = view['sec']
    want = {'framelease_v4/analysis/analyze_v4.py': 'A10'}
    if name == 'A11':
        want.update({p: 'A11' for p in FILES['A11']})
    for p, owner in want.items():
        h = sha256(ROOT / p)
        line = next((i + 1 for i in range(s, e) if h in view['lines'][i]), None)
        got = PD.citing_amendment(view, line) if line else None
        print(f'first Sec. 13.2 line citing {p}: {line} ({got})')
        if got != owner:
            fails.append(f'{p} is first cited by {got}, not {owner}')
    cfg = type('Cfg', (), {'analyze_code': ROOT / 'framelease_v4/analysis/analyze_v4.py',
                           'rel': staticmethod(lambda q: str(Path(q).relative_to(ROOT)))})()
    waits, _, _ = PD.analysis_registration(cfg, view)
    print('G8 analysis_registration waits:', waits)
    if waits:
        fails.append('analysis_registration waits')
    spec = json.loads(SPECS[name].read_text(encoding='utf-8'))
    for k, rule in enumerate(spec['inplace'], 1):
        n_new, n_old = text.count(rule['new']), text.count(rule['old'])
        ok = n_new == 1 and (n_old == 0 or rule['old'] in rule['new'])
        print(f'in-place text {k}: new {n_new}x, old {n_old}x', '' if ok else '<- not applied as specified')
        if not ok:
            fails.append(f'in-place text {k}')
    for f in ('ALERT.txt', 'protocol_txn.json'):
        if (PHASE / f).exists():
            fails.append(f'phase_driver/{f} exists')
    base = json.loads((PHASE / 'registered_baseline.json').read_text(encoding='utf-8')).get('files', {})
    for p in FILES[name]:
        h = sha256(ROOT / p)
        if h not in text:
            fails.append(f'PROTOCOL.md does not cite {p} ({h[:12]})')
        elif base.get(p) != h:
            pending.append(p)
    print('phase driver baseline:', 'holds every file at its cited sha256' if not pending else
          f'pending refresh for {len(pending)} files (the driver refreshes at its next cycle)')
    if pending and (PHASE / 'STOP').exists():
        print('phase_driver/STOP exists: the driver refreshes its baseline after its restart; exit 3 with only this '
              'refresh pending is the expected state while it is stopped (RUNBOOK.md Sec. 3)')
    if fails:
        print('FAIL:', '; '.join(fails))
        return 1
    if pending:
        return 3
    print(f'post-check {name}: passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
