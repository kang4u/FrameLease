"""Amendment A2 (PROTOCOL Sec. 13.2): realized-validity keys of framelease_v4/arms/metrics_v4.run_metrics.

Run under the protocol lock, from anywhere:
  cd /home/kang/Desktop/DAC && flock -w 600 framelease_v4/.protocol.lock \
      .conda-unidrive-linux/bin/python -I -B /tmp/a2/amend_a2.py [--dry-run]

Steps (all-or-nothing for the tree): pre-check (seal and manifest verify), install the reviewed files (sha256 pinned
below), run the tests in the real tree, then manifest, entry, seal, verify. Any test failure restores the original
metrics_v4.py, removes the new test file and exits 1 before anything is sealed.
"""
import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/home/kang/Desktop/DAC')
PY = str(ROOT / '.conda-unidrive-linux/bin/python')
REG = [PY, '-I', '-B', str(ROOT / 'framelease_v4/protocol/registration.py')]
PROTO = ROOT / 'framelease_v4/PROTOCOL.md'
MAN = ROOT / 'outputs/framelease_v4/registration/MANIFEST.sha256'
ANCHOR = 'Each amendment gets the date and time'
TARGET = ROOT / 'framelease_v4/arms/metrics_v4.py'
NEWTEST = ROOT / 'framelease_v4/arms/tests/test_metrics_realized_keys.py'
STAGED = Path('/tmp/a2/staged')
SHA_ORIG = '7849b11e5a9ea7bc29ffe7aaf33003780bb76a0d74a6c71c01ef9fb9e6b094d8'
SHA_NEW = '4c4b17dbfc6eeefae0282f773450dde2e97d8eb1da71554d8b611e7d9df098b4'
SHA_TEST = '1953e2ddd09ae9affac430196b877f3af5f8743a3897e864c04c2cae2e313c6f'
LOGDIR = ROOT / 'outputs/framelease_v4/amendment_a2'
TESTS = ['framelease_v4/arms/tests/', 'framelease_v4/protocol/tests/test_d1_summary.py']
DRY = '--dry-run' in sys.argv


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def reg(*flags):
    p = subprocess.run(REG + list(flags), cwd=ROOT, capture_output=True, text=True)
    print('registration', *flags, '->', p.returncode, '|', p.stdout.strip()[-600:], p.stderr.strip()[-600:])
    return p


def die(msg):
    print('STOP:', msg)
    sys.exit(1)


# ---------------------------------------------------------------- pre-checks (nothing written yet)
p = reg('--verify')
if p.returncode != 0 or 'manifest: OK' not in p.stdout or p.stdout.count(': OK') != 3:
    die('the current seal does not verify')
if sha(TARGET) != SHA_ORIG:
    die(f'{TARGET} is not the registered version {SHA_ORIG}')
if NEWTEST.exists():
    die(f'{NEWTEST} exists already')
if sha(STAGED / 'metrics_v4.py') != SHA_NEW or sha(STAGED / 'test_metrics_realized_keys.py') != SHA_TEST:
    die('the staged files are not the reviewed ones')
text = PROTO.read_text(encoding='utf-8')
if 'Amendment A2,' in text:
    die('an Amendment A2 entry exists already')
if text.count(ANCHOR) != 1:
    die('anchor not unique')
old_lines = TARGET.read_text(encoding='utf-8').splitlines()
new_lines = (STAGED / 'metrics_v4.py').read_text(encoding='utf-8').splitlines()
import difflib  # noqa: E402
diff = [ln for ln in difflib.unified_diff(old_lines, new_lines, lineterm='', n=0) if ln[:1] in '+-'
        and not ln.startswith(('+++', '---'))]
print('diff:', *diff, sep='\n  ')
if len(diff) != 4 or sum(1 for ln in diff if ln.startswith('-')) != 1:
    die('unexpected diff size')
if DRY:
    print('dry run: pre-checks passed; nothing written')
    sys.exit(0)

# ---------------------------------------------------------------- install, test in the real tree
orig_bytes = TARGET.read_bytes()
mode = TARGET.stat().st_mode & 0o7777
tmp = TARGET.with_name('.metrics_v4.py.a2tmp')
tmp.write_bytes((STAGED / 'metrics_v4.py').read_bytes())
os.chmod(tmp, mode)
os.replace(tmp, TARGET)
NEWTEST.write_bytes((STAGED / 'test_metrics_realized_keys.py').read_bytes())
LOGDIR.mkdir(parents=True, exist_ok=True)
env = {**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
       'OPENBLAS_NUM_THREADS': '1'}
t = subprocess.run(['nice', '-n', '19', 'ionice', '-c', '3', PY, '-I', '-B', '-m', 'pytest', '-q', '-p',
                    'no:cacheprovider'] + TESTS, cwd=ROOT, capture_output=True, text=True, env=env)
log = LOGDIR / 'pytest.log'
log.write_text(t.stdout + t.stderr, encoding='utf-8')
summary = [ln for ln in t.stdout.splitlines() if ' passed' in ln or ' failed' in ln or ' error' in ln][-1:]
print('pytest exit', t.returncode, summary)
if t.returncode != 0 or ' failed' in (summary[0] if summary else 'failed') or 'error' in (summary[0] if summary else ''):
    tmp.write_bytes(orig_bytes)
    os.chmod(tmp, mode)
    os.replace(tmp, TARGET)
    NEWTEST.unlink()
    if sha(TARGET) != SHA_ORIG:
        die('RESTORE FAILED: metrics_v4.py is not the registered version; fix by hand before the driver records')
    die(f'tests failed; original metrics_v4.py restored, new test removed; log {log}')

# ---------------------------------------------------------------- manifest, entry, seal, verify
old_man = {ln.split('  ', 1)[1]: ln.split('  ', 1)[0] for ln in MAN.read_text(encoding='utf-8').splitlines() if '  ' in ln}
p = reg('--write-manifest', '--force')
if p.returncode != 0:
    die('write-manifest failed (the tree now holds the amended files; seal by hand)')
new_man = {ln.split('  ', 1)[1]: ln.split('  ', 1)[0] for ln in MAN.read_text(encoding='utf-8').splitlines() if '  ' in ln}
man, n = sha(MAN), len(new_man)
added = sorted(set(new_man) - set(old_man) - {str(NEWTEST.relative_to(ROOT))})
changed = sorted(k for k in set(new_man) & set(old_man) if new_man[k] != old_man[k] and k != str(TARGET.relative_to(ROOT)))
if changed:
    die(f'registered files other than metrics_v4.py differ from the sealed manifest: {changed}')
when = time.strftime('%Y-%m-%d %H:%M')
dev = (' The manifest also lists ' + str(len(added)) + ' new files under `framelease_v4/` that this entry does not '
       'register (tooling for Phases 2-7 in development): ' + ', '.join(f'`{a}`' for a in added) + '.') if added else ''
entry = f"""**Amendment A2, {when} (Beijing time): the realized-validity keys of `metrics_v4.run_metrics` (no effect on any
run, job file, selection or criterion).**
* Cause. `realized.realized_validity` returns `realized_invalid_ticks` and `realized_invalid_tick_ratio` with the
  prefix already in the name, and `run_metrics` prefixed every key again (`realized_realized_*`). The two readers of
  `realized_invalid_tick_ratio`, `metrics_v4.arm_summary` and the EIR column of `framelease_v4/protocol/d1_summary.py`
  (Sec. 4.8), therefore always read None. The defect was found while the P7 aggregator was built.
* Change. `framelease_v4/arms/metrics_v4.py` (sha256 `{sha(TARGET)}`) keeps the name of a key that already carries
  the prefix; every other key stays `realized_<key>`. New regression test
  `framelease_v4/arms/tests/test_metrics_realized_keys.py` (`{sha(NEWTEST)}`): the per-run row, `arm_summary` and the
  D1 EIR equal the values of `realized_validity`; the test fails on the previous version.
* Scope. `metrics_v4.py` is analysis code: no job line pins it, and no agent, launcher or runtime module imports it.
  Stage selections use the mean DS over the kept routes (Sec. 4.2) and never read these keys. R_cond
  (`realized_conflict_plans`, `realized_misses`) was not affected. No run, job file or selection changes; the D1
  summary written at the end of P1 reports EIR as Sec. 4.8 defines it.
* Tests. {summary[0].strip() if summary else ''} (`outputs/framelease_v4/amendment_a2/pytest.log`, `{sha(log)}`).{dev}
* Manifest and seal after this amendment: `MANIFEST.sha256`, {n} files, sha256 `{man}`, sealed with this entry.

"""
if sha(PROTO) != sha(PROTO):  # pragma: no cover
    pass
cur = PROTO.read_text(encoding='utf-8')
if cur != text:
    die('PROTOCOL.md changed during the amendment (an editor without the lock); the manifest is rewritten but not sealed')
i = cur.index(ANCHOR)
pmode = PROTO.stat().st_mode & 0o7777
ptmp = PROTO.with_name('.PROTOCOL.md.a2tmp')
ptmp.write_text(cur[:i] + entry + cur[i:], encoding='utf-8')
os.chmod(ptmp, pmode)
os.replace(ptmp, PROTO)
p = reg('--seal')
if p.returncode != 0:
    die('seal failed')
p = reg('--verify')
if p.returncode != 0 or p.stdout.count(': OK') != 3:
    die('verify after the seal failed')
print('PROTOCOL', sha(PROTO), 'MANIFEST', man, n, 'files')
print(entry)
