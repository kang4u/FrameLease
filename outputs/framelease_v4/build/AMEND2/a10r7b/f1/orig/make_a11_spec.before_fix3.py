"""Write outputs/framelease_v4/build/AMEND2/a10r7b/A11_spec.json, the apply_entry.py spec of Amendment A11 (item R7B:
registration of framelease_v4/analysis/verify_table1_extra.py and its tests). Reads the A10 spec and the tree; writes
only the A11 spec.

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/a10r7b/make_a11_spec.py [--check]

* in-place text: the Sec. 9.12 "**Verification.**" paragraph as Amendment A10 leaves it ("old" = the "new" of the A10
  in-place text that starts with "**Verification.**", byte for byte) with the clause OLD_CLAUSE replaced by
  NEW_CLAUSE and the paragraph rewrapped greedily at 120 columns (words never split). A11 is applied after A10, so
  this "old" occurs once in PROTOCOL.md exactly when A10's in-place text was applied as specified.
* tests: the builder's tests and the review tests of item R7B, and the tests of the class report of the reporting
  rule (f1/test_f1_class_report.py, item F1A11), each with its own log in outputs/framelease_v4/amendment_a11/.
* must_equal: the two files A11 registers and the review test file, at their current sha256 (MUST_EQUAL below; the
  files at the end of item R7B, attempt 6, 2026-11-15 13:28, reviewed GO by build/R7B/rereview/REVIEW.md, the second
  review of the fixes; attempt 5, a8bf57b7 / c3bf160c, until item F1A11), and the class report and its tests (cited
  under "Evidence"; fix pass 2 of item F1A11). A different sha256 on the tree is reported and stops the writing: a
  changed file carries its review first; then MUST_EQUAL is updated here.
* max_new_registered 2: the entry cites by full sha256 exactly the two R7B files among the manifest files outside the
  registered set of apply_entry_stream.py (both drivers' baselines, the sealed-manifest files whose sha256 PROTOCOL.md
  cites, the P1 job files); after --write-manifest the applier counts every such file whose new-manifest sha256 the
  composed PROTOCOL.md holds.
--check: compare the written spec with the one this script would write (exit 0 equal, 1 different); write nothing.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path('/home/kang/Desktop/DAC')
HERE = ROOT / 'outputs/framelease_v4/build/AMEND2/a10r7b'
A10_SPEC = ROOT / 'outputs/framelease_v4/build/AMEND2/final/A10_spec.json'
OUT = HERE / 'A11_spec.json'
TEMPLATE = 'outputs/framelease_v4/build/AMEND2/a10r7b/A11_entry.md'
WIDTH = 120
OLD_CLAUSE = ('a second script, registered by its own amendment before the analysis freeze, recomputes the other '
              'Table I columns,')
NEW_CLAUSE = ('Amendment A11: `framelease_v4/analysis/verify_table1_extra.py` recomputes GPU usage, DMR, action age '
              'p50 and p95, fallback ratio, EIR, P_both and the closed-loop R_cond,')
TESTS = (('outputs/framelease_v4/amendment_a11/pytest_verify_table1_extra.log',
          ['framelease_v4/analysis/tests/test_verify_table1_extra.py']),
         ('outputs/framelease_v4/amendment_a11/pytest_review_r7b.log',
          ['outputs/framelease_v4/build/R7B/review/test_review_r7b.py']),
         ('outputs/framelease_v4/amendment_a11/pytest_f1_class_report.log',
          ['outputs/framelease_v4/build/AMEND2/a10r7b/f1/test_f1_class_report.py']))
MUST_EQUAL = {
    'framelease_v4/analysis/verify_table1_extra.py':
        'f77b2dcf34484d2537a4c22d804912f0c155c3e3c26a576f433b9f4f73d83c27',
    'framelease_v4/analysis/tests/test_verify_table1_extra.py':
        'f0e74336e2244eea7136f3a94475ab0d96d5dfcd4b7fe0d8f97308877ac50154',
    'outputs/framelease_v4/build/R7B/review/test_review_r7b.py':
        '63c4359d5cf4991a4904bac1f1c95b4519856d84e4e96431182496b1b45ce0d0',
    'outputs/framelease_v4/build/AMEND2/a10r7b/f1/f1_class_report.py':
        '4c7f3af5981bf0328caa9897e6525f63ca891dc1e08f48cc9a29148b65cf30e7',
    'outputs/framelease_v4/build/AMEND2/a10r7b/f1/test_f1_class_report.py':
        'f26ffb38558420a83d35300ec5b8797f516e21fb1bfcff21a6094194272c2955',
}


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def flat(text):
    return ' '.join(text.split())


def wrap(words, indent=''):
    out, cur = [], ''
    for w in words:
        if not cur:
            cur = indent + w
        elif len(cur) + 1 + len(w) <= WIDTH:
            cur += ' ' + w
        else:
            out.append(cur)
            cur = indent + w
    if cur:
        out.append(cur)
    return out


def verification_inplace(a10_spec):
    """{'old', 'new'}: A10's Verification paragraph (its in-place "new") and the A11 text of it."""
    hits = [r for r in a10_spec['inplace'] if r['old'].startswith('**Verification.**')]
    if len(hits) != 1:
        raise SystemExit(f'STOP: the A10 spec holds {len(hits)} in-place texts that start with "**Verification.**"')
    old = hits[0]['new']
    f = flat(old)
    if f.count(OLD_CLAUSE) != 1:
        raise SystemExit(f'STOP: the A10 Verification text holds the clause {f.count(OLD_CLAUSE)} times: {OLD_CLAUSE}')
    new = '\n'.join(wrap(f.replace(OLD_CLAUSE, NEW_CLAUSE).split(' '))) + '\n'
    if not old.endswith('\n') or max(len(ln) for ln in new.splitlines()) > WIDTH:
        raise SystemExit('STOP: the derived Verification text is malformed')
    return {'old': old, 'new': new}


def build():
    a10 = json.loads(A10_SPEC.read_text(encoding='utf-8'))
    changed = {p: (w[:12], sha(ROOT / p)[:12]) for p, w in MUST_EQUAL.items() if sha(ROOT / p) != w}
    if changed:
        raise SystemExit(f'STOP: files changed since their pin (review them first, then update MUST_EQUAL): {changed}')
    return {
        'name': 'A11',
        'note': 'Amendment A11 (item R7B); apply after Amendment A10 (its in-place text is the A10 Verification text); '
                'RUNBOOK: outputs/framelease_v4/build/AMEND2/a10r7b/RUNBOOK.md',
        'template': TEMPLATE,
        'tests': [{'log': log, 'argv': argv} for log, argv in TESTS],
        'inplace': [verification_inplace(a10)],
        'must_equal': dict(MUST_EQUAL),
        'max_new_registered': 2,
    }


def main():
    text = json.dumps(build(), indent=1) + '\n'
    if '--check' in sys.argv[1:]:
        same = OUT.is_file() and OUT.read_text(encoding='utf-8') == text
        print(f'{OUT.relative_to(ROOT)}: ' + ('equal to the generated spec' if same else 'DIFFERS from the generated '
                                                                                     'spec'))
        return 0 if same else 1
    tmp = OUT.with_name('.' + OUT.name + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    os.replace(tmp, OUT)
    print(f'written {OUT.relative_to(ROOT)} ({sha(OUT)})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
