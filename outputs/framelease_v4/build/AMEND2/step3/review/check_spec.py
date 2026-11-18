"""Independent read-only check of step3_spec.json and final/OP_spec.json against the tree (review of item Step3)."""
import hashlib, json, os, re, sys
ROOT = '/home/kang/Desktop/DAC'
S3 = f'{ROOT}/outputs/framelease_v4/build/AMEND2/step3'
def sha(p):
    h = hashlib.sha256()
    with open(p if os.path.isabs(p) else os.path.join(ROOT, p), 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()
spec = json.load(open(f'{S3}/step3_spec.json'))
op = json.load(open(f'{ROOT}/outputs/framelease_v4/build/AMEND2/final/OP_spec.json'))
bad = 0
for name, d in (('OP_spec must_equal', op['must_equal']), ('step3 must_equal', spec['must_equal']),
                ('step3 a3_files', spec['a3_files'])):
    diff = {p: (w[:12], sha(p)[:12]) for p, w in d.items() if sha(p) != w}
    print(f'{name}: {len(d)} files, differing: {diff or "none"}')
    bad += len(diff)
print('expected_new_registered:', len(spec['expected_new_registered']))
print('a3 framelease_v4 files == expected - OP files:',
      sorted(p for p in spec['a3_files'] if p.startswith('framelease_v4/')) ==
      sorted(set(spec['expected_new_registered']) - set(op['must_equal'])))
# test logs: summary line, failures, mtime vs. the newest file they cover
logs = {
 'outputs/framelease_v4/amendment_a3/pytest_protocol_tools.log': ['framelease_v4/protocol'],
 'outputs/framelease_v4/amendment_a3/pytest_arms_ext.log': ['framelease_v4/arms_ext'],
 'outputs/framelease_v4/amendment_a3/pytest_analysis.log': ['framelease_v4/analysis', 'framelease_v4/arms/tests/test_metrics_realized_keys.py'],
 'outputs/framelease_v4/amendment_a7/pytest_stress_bench.log': ['framelease_v4/protocol/stress_bench.py', 'framelease_v4/protocol/tests/test_stress_bench.py'],
 'outputs/framelease_v4/operational_phase_driver/pytest_phase_driver.log': ['framelease_v4/protocol/phase_driver.py', 'framelease_v4/protocol/tests/test_phase_driver.py', 'framelease_v4/protocol/start_phase_driver.sh'],
 'outputs/framelease_v4/operational_phase_driver/pytest_review_phase.log': ['outputs/framelease_v4/build/PHASE/review/test_review_phase.py', 'framelease_v4/protocol/phase_driver.py'],
}
for log, covered in logs.items():
    p = os.path.join(ROOT, log)
    txt = open(p, errors='replace').read()
    lines = [ln.strip('= ').strip() for ln in txt.splitlines() if re.search(r'\d+ (passed|failed|error)', ln)]
    summ = lines[-1] if lines else ''
    newest = 0
    for c in covered:
        cp = os.path.join(ROOT, c)
        if os.path.isdir(cp):
            for dp, dn, fn in os.walk(cp):
                if '__pycache__' in dp:
                    continue
                for f in fn:
                    if f.endswith(('.py', '.sh')):
                        newest = max(newest, os.path.getmtime(os.path.join(dp, f)))
        else:
            newest = max(newest, os.path.getmtime(cp))
    fails = len(re.findall(r'^(FAILED|ERROR) ', txt, re.M))
    print(f'{log}: {summ!r}; FAILED/ERROR lines {fails}; log newer than covered code: {os.path.getmtime(p) > newest}; sha {sha(log)[:12]}')
    if not summ or 'failed' in summ or 'error' in summ or fails:
        bad += 1
sys.exit(1 if bad else 0)
