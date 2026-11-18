"""Independent check of a step-3 result in a scratch tree (read only; the step-3 simulation, case 08b).

  check_result.py ROOT WORK      # WORK: the transaction directory (PROTOCOL.sealed.md, MANIFEST.sealed.sha256)

Checks, without the code of step3_txn.py: the changes of PROTOCOL.md are the in-place hunks plus ONE insertion that
ends directly before the paragraph "Each amendment gets the date and time"; no added line over 120 columns (table rows
excepted) and no placeholder brace; the inserted titles are A3, A9, A7, A4 and the operational addition, in this order,
with one time stamp; each of the five manifest clauses cites the sealed manifest (file count and sha256); every
`path` (`sha256`) pair of the inserted text holds the file's sha256; the files newly registered (manifest files outside
the registered baseline and the P1 job files whose sha256 the new text cites and the sealed one did not) are the 40 of
step3_spec.json; the A7 entry names its test log with the directory; SEAL.sha256 holds the sha256 of PROTOCOL.md and of
MANIFEST.sha256. Exit 0 when every check holds, 1 otherwise.
"""
import difflib
import hashlib
import json
import os
import re
import sys

ANCHOR = 'Each amendment gets the date and time'
SPEC = '/home/kang/Desktop/DAC/outputs/framelease_v4/build/AMEND2/step3/step3_spec.json'


def main():
    root, work = sys.argv[1], sys.argv[2]

    def path(p):
        return p if os.path.isabs(p) else os.path.join(root, p)

    def sha(p):
        h = hashlib.sha256()
        with open(path(p), 'rb') as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b''):
                h.update(chunk)
        return h.hexdigest()

    spec = json.load(open(SPEC, encoding='utf-8'))
    old = open(f'{work}/PROTOCOL.sealed.md', encoding='utf-8').read().split('\n')
    new_text = open(path('framelease_v4/PROTOCOL.md'), encoding='utf-8').read()
    new = new_text.split('\n')
    bad = []
    anchor = [i for i, ln in enumerate(old) if ln.startswith(ANCHOR)]
    hunks = [op for op in difflib.SequenceMatcher(a=old, b=new, autojunk=False).get_opcodes() if op[0] != 'equal']
    inserts = [h for h in hunks if h[0] == 'insert' and h[1] in anchor]
    print(f'hunks: {len(hunks)} (in-place {len(hunks) - len(inserts)}, insertion before the anchor {len(inserts)})')
    if len(inserts) != 1 or len(anchor) != 1:
        bad.append('not exactly one insertion directly before the anchor paragraph')
    added = [new[j] for _, _, _, j1, j2 in hunks for j in range(j1, j2)]
    long_ = [ln for ln in added if len(ln) > 120 and not ln.lstrip().startswith('|')]
    braces = [ln for ln in added if '{{' in ln or '}}' in ln]
    print(f'added lines: {len(added)}; over 120 columns (tables excepted): {len(long_)}; with a placeholder brace: '
          f'{len(braces)}')
    if long_ or braces:
        bad.append('an added line over 120 columns or with a placeholder brace')
    ins = '\n'.join(new[inserts[0][3]:inserts[0][4]]) if inserts else ''
    titles = re.findall(r'^\*\*(?:Amendment (A\d+)|(Operational addition)), (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) '
                        r'\(Beijing time\)', ins, re.M)
    names = [a or 'OP' for a, _, _ in titles]
    stamps = {s for _, _, s in titles}
    print(f'inserted titles: {names}; time stamps: {sorted(stamps)}')
    if names != ['A3', 'A9', 'A7', 'A4', 'OP'] or len(stamps) != 1:
        bad.append('the inserted titles are not A3, A9, A7, A4, OP with one time stamp')
    man = {}
    for ln in open(path('outputs/framelease_v4/registration/MANIFEST.sha256'), encoding='utf-8').read().splitlines():
        s, p = ln.split('  ', 1)
        man[p] = s
    msha = sha('outputs/framelease_v4/registration/MANIFEST.sha256')
    flat = ' '.join(ins.split())
    clauses = re.findall(r'`MANIFEST\.sha256`, (\d+) files, sha256 `([0-9a-f]{64})`, sealed with this entry', flat)
    ok_clauses = len(clauses) == 5 and all(n == str(len(man)) and s == msha for n, s in clauses)
    print(f'manifest clauses: {len(clauses)}; all cite the sealed manifest ({len(man)} files, {msha[:16]}): '
          f'{ok_clauses}')
    if not ok_clauses:
        bad.append('the manifest clauses do not all cite the sealed manifest')
    pairs = re.findall(r'`((?:framelease_v4|outputs)/[^`]+)`[^`]{0,40}?\(?`([0-9a-f]{64})`', flat)
    wrong = [(p, s[:12]) for p, s in pairs if os.path.isfile(path(p)) and sha(p) != s]
    print(f'path / sha256 pairs: {len(pairs)}; wrong: {wrong or "none"}')
    if wrong or len(pairs) < 40:
        bad.append('a path / sha256 pair is wrong (or fewer than 40 pairs found)')
    base = json.load(open(path('outputs/framelease_v4/p1_driver/registered_baseline.json'), encoding='utf-8'))['files']
    old_text = '\n'.join(old)
    newly = sorted(p for p, s in man.items() if p not in base and not p.startswith('outputs/framelease_v4/p1_jobs/')
                   and s in new_text and s not in old_text)
    print(f'newly registered: {len(newly)}; equal to the 40 of the spec: {newly == spec["expected_new_registered"]}')
    if newly != spec['expected_new_registered']:
        bad.append('the newly registered files differ from the spec')
    a7 = ins[ins.find('**Amendment A7,'):ins.find('**Amendment A4,')]
    a7_log = '`outputs/framelease_v4/amendment_a7/pytest_stress_bench.log`' in ' '.join(a7.split())
    print(f'A7 names its test log with the directory: {a7_log}')
    if not a7_log:
        bad.append('the A7 entry does not name outputs/framelease_v4/amendment_a7/pytest_stress_bench.log')
    seal = dict(reversed(ln.split('  ', 1)) for ln in
                open(path('outputs/framelease_v4/registration/SEAL.sha256'), encoding='utf-8').read().splitlines())
    sealed = (seal.get('framelease_v4/PROTOCOL.md') == sha('framelease_v4/PROTOCOL.md')
              and seal.get('outputs/framelease_v4/registration/MANIFEST.sha256') == msha)
    print(f'SEAL.sha256 holds PROTOCOL.md and MANIFEST.sha256: {sealed}')
    if not sealed:
        bad.append('the seal does not hold the new PROTOCOL.md and manifest')
    print('check_result: ' + ('all checks hold' if not bad else 'FAILED: ' + '; '.join(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
