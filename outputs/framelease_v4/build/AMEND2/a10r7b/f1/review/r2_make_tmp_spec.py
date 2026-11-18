"""Round-2 review of A11: a temporary copy of A11_spec.json and of its template whose three test logs are the fix's
logs in f1/logs/ (read only on the project; writes only /tmp/A11R2/A11_spec.tmp.json and /tmp/A11R2/A11_entry.tmp.md)."""
import json
import sys

ROOT = '/home/kang/Desktop/DAC/'
A = 'outputs/framelease_v4/build/AMEND2/a10r7b/'
OLD, NEW = 'outputs/framelease_v4/amendment_a11/', A + 'f1/logs/'
spec = json.load(open(ROOT + A + 'A11_spec.json'))
tmpl = open(ROOT + spec['template'], encoding='utf-8').read()
n = tmpl.count(OLD)
spec['template'] = '/tmp/A11R2/A11_entry.tmp.md'
for t in spec['tests']:
    assert t['log'].startswith(OLD)
    t['log'] = t['log'].replace(OLD, NEW)
open('/tmp/A11R2/A11_entry.tmp.md', 'w', encoding='utf-8').write(tmpl.replace(OLD, NEW))
json.dump(spec, open('/tmp/A11R2/A11_spec.tmp.json', 'w'), indent=1)
print('replaced %d occurrences; logs %s' % (n, [t['log'] for t in spec['tests']]))
sys.exit(0)
