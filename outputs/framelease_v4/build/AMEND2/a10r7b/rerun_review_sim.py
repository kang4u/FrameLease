"""Rerun the review's scratch-tree harness (review/review_sim.py) against the fixed applier and wrapper (item a10r7b,
fix pass; read only on the project and on the review directory).

  cd /home/kang/Desktop/DAC
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' \
      taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/a10r7b/rerun_review_sim.py [CASE ...]

review_sim.py is loaded unchanged as a module; only its locations and its proposal hooks are replaced:
  BASE = /tmp/AMEND3/a10r7b/rsim (scratch trees; the review's /tmp/AMEND3_review/ is not used), WORK = BASE/work,
  LOGS = a10r7b/review_rerun/logs (the review's logs and proposal files stay as the reviewer left them);
  INJECT: its scratch-prefix checks name BASE;
  fixed_applier = applier, fixed_wrapper = wrapper and VANISH_REPLACEMENTS = (): the applier and the wrapper of this
  directory hold the proposed fixes now, so the review's "fix" cases run on them unchanged.
Every case of the review therefore runs on the fixed files. The result each case must give after the fix is checked
here (EXPECT); summary_<case>.json and expectations.txt go to LOGS. Exit 0 when every expectation holds.
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

SRC = Path('/home/kang/Desktop/DAC')
HERE = SRC / 'outputs/framelease_v4/build/AMEND2/a10r7b'
BASE = Path('/tmp/AMEND3/a10r7b/rsim')
LOGS = HERE / 'review_rerun/logs'
A10_SPEC = 'outputs/framelease_v4/build/AMEND2/final/A10_spec.json'
A11_SPEC = 'outputs/framelease_v4/build/AMEND2/a10r7b/A11_spec.json'
A10_FILES = sorted(('framelease_v4/analysis/analyze_v4.py', 'framelease_v4/analysis/prop1_coverage.py',
                    'framelease_v4/analysis/figures_tables.py', 'framelease_v4/analysis/verify_independent.py',
                    'framelease_v4/analysis/tests/test_analyze_v4.py',
                    'framelease_v4/analysis/tests/test_prop1_coverage.py',
                    'framelease_v4/analysis/tests/test_figures_tables.py',
                    'framelease_v4/analysis/tests/test_verify_independent.py'))
R7B_FILES = sorted(('framelease_v4/analysis/verify_table1_extra.py',
                    'framelease_v4/analysis/tests/test_verify_table1_extra.py'))
VERIFY_OK = ('manifest: OK | seal framelease_v4/PROTOCOL.md: OK | '
             'seal outputs/framelease_v4/registration/MANIFEST.sha256: OK')


def load():
    spec = importlib.util.spec_from_file_location('review_sim', HERE / 'review/review_sim.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    if not str(BASE).startswith('/tmp/AMEND3/'):
        raise SystemExit('refused: BASE outside /tmp/AMEND3/')
    for old in ("'/tmp/AMEND3_review/a10r7b/'", "'/tmp/AMEND3_review/'"):
        if m.INJECT.count(old) != 1:
            raise SystemExit(f'INJECT: {old} found {m.INJECT.count(old)} times')
        m.INJECT = m.INJECT.replace(old, f"'{BASE}/'")
    m.BASE, m.WORK, m.LOGS = BASE, BASE / 'work', LOGS
    m.fixed_applier = m.applier
    m.fixed_wrapper = m.wrapper
    m.VANISH_REPLACEMENTS = ()
    m.REVIEW = BASE / 'no_review_writes'            # no case may write into the review directory
    return m


def listed(text):
    """The Python list printed after 'newly cited manifest files: '."""
    return sorted(eval(text.split('newly cited manifest files: ')[-1])) if text else None   # noqa: S307 (own output)


def beijing_now():
    return {time.strftime('%Y-%m-%d %H:%M', time.gmtime(time.time() + 8 * 3600 - d)) for d in range(0, 600, 60)}


def title_time(title):
    return title[len('**Amendment A10, '):len('**Amendment A10, ') + 16]


def expect_tests(r):
    a10, a11 = r[A10_SPEC], r[A11_SPEC]
    log = LOGS / 'ttree_amendment_a10_pytest_prop1_coverage.log'
    failed = [ln for ln in log.read_text(encoding='utf-8').splitlines() if ln.startswith('FAILED')] if log.is_file() \
        else ['no log']
    artifact = ['FAILED framelease_v4/analysis/tests/test_prop1_coverage.py::Reproducible::'
                'test_reproduces_development_run']
    return {'analyze_v4 48 passed, 107 subtests': '48 passed, 107 subtests passed' in a10[0] and 'exit 0' in a10[0],
            'prop1_coverage 22 passed, or 21 and the tree artifact the review names (Reproducible)':
                'exit 0 | 22 passed' in a10[1] or ('1 failed, 21 passed' in a10[1]
                                                   and [f.split(' - ')[0] for f in failed] == artifact),
            'figures_tables 50 passed': 'exit 0 | 50 passed' in a10[2],
            'verify_independent 28 passed, 20 subtests': 'exit 0 | 28 passed, 20 subtests' in a10[3],
            'verify_table1_extra 71 passed, 67 subtests': 'exit 0 | 71 passed, 67 subtests' in a11[0],
            'review_r7b 14 passed, 2 subtests': 'exit 0 | 14 passed, 2 subtests' in a11[1],
            'no protected path, no __pycache__ in the tree': not r['protected_paths_created_in_tree']
            and not r['pycache_in_tree']}


def expect_A(r):
    return {'A10 sealed, newly cited = the 8 A10 files': r['A10_apply_rc'] == 0 and len(r['A10_newly']) == 1
            and listed(r['A10_newly'][0]) == A10_FILES,
            'verify after A10': r['verify_after_A10']['all_ok'],
            'parsers after A10 without problem': r['parse_after_A10']['problems'] == []
            and not r['parse_after_A10']['G8_waits'],
            'refresh after A10: +8, none changed': sorted(r['refresh_after_A10']['added']) == A10_FILES
            and r['refresh_after_A10']['changed'] == [],
            'A10 lines: no prose line > 120, no pattern': r['lines_A10'][0] == [] and r['lines_A10'][2] == [],
            'A11 sealed, newly cited = the 2 R7B files': r['A11_apply_rc'] == 0 and len(r['A11_newly']) == 1
            and listed(r['A11_newly'][0]) == R7B_FILES,
            'verify after A11': r['verify_after_A11']['all_ok'],
            'parsers after A11 without problem': r['parse_after_A11']['problems'] == []
            and not r['parse_after_A11']['G8_waits']
            and r['parse_after_A11']['later_gate']['read'] and r['parse_after_A11']['later_gate']['others_unchanged'],
            'A11 lines: no prose line > 120, no pattern': r['lines_A11'][0] == [] and r['lines_A11'][2] == [],
            'post_check A11 exit 0 (refresh written)': r['post_check_A11'][0] == 0,
            'post_check A10 after A11 fails on in-place 4 only (as the review found)': r['post_check_A10'][0] == 1
            and 'in-place text 4' in r['post_check_A10'][1][0]}


def expect_B(r):
    return {'A11 first: STOP in-place 0 times, nothing changed': r['rc'] == 1 and r['unchanged']
            and any('in-place text found 0 times' in s for s in r['stop']) and r['verify']['all_ok']}


def expect_C(r):
    o = r['old_twice']
    return {'no overlap of the 5 A10 in-place texts': r['A10_inplace_overlap'] == [],
            'old text twice: STOP before write-manifest, nothing changed': o['rc'] == 1 and o['unchanged']
            and any('found 2 times' in s for s in o['stop']),
            'derive_inplace5 exits 1 on the doubled paragraph': r['derive_on_doubled'][0] == 1}


def expect_D(r):
    c = r['control_p1_file']
    return {'commit_audit.py changed: STOP before write-manifest (was: sealed)': r['apply_rc'] == 1
            and 'STOP' in ' '.join(r['check']) and not r['sealed_manifest_has_new_sha']
            and not r['verify_after']['manifest_ok'],
            'phase refresh adopts nothing': r['phase_refresh']['changed_sha256_adopted'] == [],
            'control realized.py: STOP, nothing changed': c['rc'] == 1 and c['unchanged'] and c['stop'] != []}


def expect_E(r):
    return {f'{k}: sealed, wrapper exit 95 (was: 0)': r[k]['rc'] == 95 and r[k]['sealed']
            for k in ('phase_only', 'p1_baseline')}


def expect_F(r):
    f1, f2, f3 = r['F1_no_scope_change'], r['F2_scope_change'], r['F3_truncated']
    held = 'PROTOCOL.md holds the entry but is not sealed'
    return {'F1: killed before the seal: entry kept, hand seal consistent': f1['rc'] == 137 and f1['protocol_changed']
            and any(held in n for n in f1['wrapper_notes']) and f1['hand_seal_rc'] == 0
            and f1['verify_after_hand_seal']['all_ok'] and f1['sealed_manifest_is_the_one_the_entry_names'],
            'F2: the rewritten manifest is kept (was: restored), hand seal consistent': f2['rc'] == 137
            and any(held in n for n in f2['wrapper_notes']) and not f2['manifest_now_equals_sealed_before']
            and f2['entry_manifest_sha'] == f2['manifest_now'] and f2['hand_seal_rc'] == 0
            and f2['verify_after_hand_seal']['all_ok'] and f2['sealed_manifest_is_the_one_the_entry_names'],
            'F3: truncated PROTOCOL.md: STOP at the seal check': f3['rc'] == 1 and f3['manifest_unchanged']
            and any('the seal does not verify' in s for s in f3['stop'])}


def expect_G(r):
    return {'caller TZ=UTC: sealed with Beijing time (was: UTC)': r['rc'] == 0
            and title_time(r['title']) in beijing_now() and r['verify']['all_ok']}


def expect_H(r):
    return {'template line read as the G3 entry: check STOP, apply STOP (was: sealed)': r['A10_rc'] == 0
            and 'STOP: template problem' in ' '.join(r['A11_check_with_gate_line']) and r['A11_apply_rc'] == 1
            and 'p2_data' not in r['phase_entries_read'] and not r['A11_title_line']}


def expect_fix(r):
    full = [ln for ln in (LOGS / 'fixA.out').read_text(encoding='utf-8').splitlines() if 'newly cited' in ln]
    return {'A: A10 and A11 sealed with the 8 and the 2 files': list(r['A']['rc']) == [0, 0]
            and [listed(x) for x in full] == [A10_FILES, R7B_FILES] and r['A']['verify'] == VERIFY_OK,
            'D: STOP, nothing changed': r['D']['rc'] == 1 and r['D']['unchanged'] and r['D']['stop'] != [],
            'E: exit 95': r['E']['rc'] == 95,
            'F2: kept, hand seal consistent': r['F2']['rc'] == 137 and r['F2']['hand_seal_rc'] == 0
            and r['F2']['verify'] == VERIFY_OK and r['F2']['sealed_manifest_is_the_one_the_entry_names'],
            'G: applier alone under UTC stops; wrapper stamps Beijing time': 'not Beijing time' in
            ' '.join(r['G_applier_alone_utc']) and r['G_wrapper']['rc'] == 0
            and title_time(r['G_wrapper']['title']) in beijing_now(),
            'H: template STOP': 'STOP: template problem' in ' '.join(r['H']['A11_check'])}


def expect_V(r):
    out = {}
    for k in ('p1_baseline', 'phase_only'):
        out[f'{k}: removed registered file: STOP (was: sealed), the manifest still lists it'] = r[k]['rc'] == 1 \
            and r[k]['sealed_manifest_lists_it'] and r[k]['phase_refresh_keeps_it']
        f = r[k + '_fix']
        out[f'{k}_fix: STOP, nothing changed'] = f['rc'] == 1 and f['unchanged'] and f['stop'] != []
    return out


def expect_T(r):
    return {'leftover temporary file: wrapper exit 96 (was: sealed into the manifest)': r['rc'] == 96
            and not r['sealed_manifest_lists_tmp'] and r['verify'] == VERIFY_OK}


def expect_D3(r):
    return {'p3_rl.py changed: STOP (was: sealed)': r['rc'] == 1 and r['refresh_changed_sha256_adopted'] == []
            and r['gate_code_check_pending'] and not r['new_sha256_cited_in_PROTOCOL']}


def expect_fixAV(r):
    own = r['owners'] or {}
    return {'A10 then refresh then A11: 8 and 2 files, verify OK, parsers clean': list(r['rc']) == [0, 0]
            and [listed(x) for x in r['newly']] == [A10_FILES, R7B_FILES] and r['verify'] == VERIFY_OK
            and r['problems'] == [] and not r['G8_waits'],
            'owners: A10 files by A10, R7B files by A11': all(own.get(p) == 'A10' for p in A10_FILES)
            and all(own.get(p) == 'A11' for p in R7B_FILES)}


EXPECT = {'tests': expect_tests, 'A': expect_A, 'B': expect_B, 'C': expect_C, 'D': expect_D, 'E': expect_E,
          'F': expect_F, 'G': expect_G, 'H': expect_H, 'fix': expect_fix, 'V': expect_V, 'T': expect_T,
          'D3': expect_D3, 'fixAV': expect_fixAV}


def main():
    m = load()
    m.WORK.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    names = sys.argv[1:] or list(EXPECT)
    lines, ok = [], True
    for n in names:
        t0 = time.time()
        res = m.CASES[n]()
        (LOGS / f'summary_{n}.json').write_text(json.dumps(res, indent=1, default=str), encoding='utf-8')
        try:
            checks = EXPECT[n](res)
        except Exception as exc:                            # a missing key is a failed expectation
            checks = {f'evaluation: {type(exc).__name__}: {exc}': False}
        for what, passed in checks.items():
            ok = ok and bool(passed)
            lines.append(f'{n}: {"PASS" if passed else "FAIL"} {what}')
            print(lines[-1], flush=True)
        lines.append(f'{n}: {time.time() - t0:.0f} s')
        (LOGS / 'expectations.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    lines.append('ALL EXPECTED' if ok else 'SOME EXPECTATION FAILED')
    (LOGS / 'expectations.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(lines[-1])
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
