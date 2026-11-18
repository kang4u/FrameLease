"""Reviewer's independent check of a step-3 result in a scratch tree (read only).
  verify_result.py ROOT WORK  (WORK: the transaction directory with PROTOCOL.sealed.md)"""
import difflib, hashlib, json, os, re, sys
root, work = sys.argv[1], sys.argv[2]
old = open(f'{work}/PROTOCOL.sealed.md', encoding='utf-8').read().split('\n')
new = open(f'{root}/framelease_v4/PROTOCOL.md', encoding='utf-8').read().split('\n')
spec = json.load(open('/home/kang/Desktop/DAC/outputs/framelease_v4/build/AMEND2/step3/step3_spec.json'))
def sha(p):
    return hashlib.sha256(open(p if os.path.isabs(p) else os.path.join(root, p), 'rb').read()).hexdigest()
sm = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
anchor = next(i for i, l in enumerate(old) if l.startswith('Each amendment gets the date and time'))
hunks = [op for op in sm.get_opcodes() if op[0] != 'equal']
print('hunks:', len(hunks))
for tag, i1, i2, j1, j2 in hunks:
    where = 'before anchor (Sec. 13.2 insertion)' if i1 == anchor else f'old lines {i1+1}-{i2}'
    print(f'  {tag:8s} {where}: -{i2-i1} +{j2-j1}; first new line: {new[j1][:70]!r}' if j2 > j1 else f'  {tag} {where}')
added = [new[j] for tag, i1, i2, j1, j2 in hunks for j in range(j1, j2)]
long_ = [l for l in added if len(l) > 120 and not l.lstrip().startswith('|')]
print('added lines:', len(added), '; added non-table lines over 120 columns:', len(long_))
print('placeholder braces in added lines:', sum('{{' in l or '}}' in l for l in added))
ins = '\n'.join(new[hunks[-1][3]:hunks[-1][4]])
stamps = re.findall(r'^\*\*(?:Amendment (A\d+)|Operational addition), (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \(Beijing time\)', ins, re.M)
print('entry titles and stamps:', stamps)
man = {l.split('  ', 1)[1]: l.split('  ', 1)[0] for l in open(f'{root}/outputs/framelease_v4/registration/MANIFEST.sha256').read().splitlines()}
msha = sha('outputs/framelease_v4/registration/MANIFEST.sha256')
clauses = re.findall(r'`MANIFEST\.sha256`, (\d+) files, sha256\s+`([0-9a-f]{64})`, sealed with this entry', ins)
print('manifest clauses:', len(clauses), 'all cite the sealed manifest:', all(n == str(len(man)) and s == msha for n, s in clauses))
# every (`path` ... `sha`) pair: a cited path followed by its 64-hex value within the same entry
flat = ' '.join(ins.split())
pairs = re.findall(r'`((?:framelease_v4|outputs)/[^`]+)`[^`]{0,40}?\(?`([0-9a-f]{64})`', flat)
bad = [(p, s[:12], sha(p)[:12]) for p, s in pairs if os.path.isfile(os.path.join(root, p)) and sha(p) != s]
print('path/sha256 pairs checked:', len(pairs), 'wrong:', bad or 'none')
cited = set(re.findall(r'[0-9a-f]{64}', ins))
base = json.load(open(f'{root}/outputs/framelease_v4/p1_driver/registered_baseline.json'))['files']
oldtxt = '\n'.join(old)
newly = sorted(p for p, s in man.items() if p not in base and not p.startswith('outputs/framelease_v4/p1_jobs/')
               and s in '\n'.join(new) and s not in oldtxt)
print('newly registered by the new text:', len(newly), '== spec expected:', newly == spec['expected_new_registered'])
others = sorted(p for p, s in man.items() if s in cited and p not in base and p not in newly
                and not p.startswith('outputs/framelease_v4/p1_jobs/'))
print('other manifest files whose sha256 the five entries cite:', others or 'none')
