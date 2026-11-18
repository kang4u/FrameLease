"""Write final/A10_spec.json and final/OP_spec.json (apply_entry.py specs) and report the in-place counts on the
current PROTOCOL.md (read only). Provenance of the specs at drafting: "must_equal" holds the sha256 at drafting, so this
script is not rerun at application."""
import hashlib
import json
from pathlib import Path

ROOT = Path('/home/kang/Desktop/DAC')
OUT = ROOT / 'outputs/framelease_v4/build/AMEND2/final'
A10_FILES = ['framelease_v4/analysis/analyze_v4.py', 'framelease_v4/analysis/prop1_coverage.py',
             'framelease_v4/analysis/figures_tables.py', 'framelease_v4/analysis/verify_independent.py',
             'framelease_v4/analysis/tests/test_analyze_v4.py', 'framelease_v4/analysis/tests/test_prop1_coverage.py',
             'framelease_v4/analysis/tests/test_figures_tables.py',
             'framelease_v4/analysis/tests/test_verify_independent.py']
# code the coverage reuses outside the registration manifest (cited under "Evidence"; equal to gate2's config.json);
# in "must_equal" only: citing their sha256 registers nothing (no manifest file)
A10_REUSED = ['framelease_v3/envelopes.py', 'framelease_v2/calibration.py', 'framelease_v3/suffix_lease_eval.py']
OP_FILES = ['framelease_v4/protocol/phase_driver.py', 'framelease_v4/protocol/start_phase_driver.sh',
            'framelease_v4/protocol/tests/test_phase_driver.py',
            'outputs/framelease_v4/build/PHASE/review/test_review_phase.py']


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


INPLACE_A10 = [
    {'section': '9.4, last sentence',
     'old': 'If an offline output lacks a paired quantity, the v4 analysis script computes it from '
            '`per_clip_selected.csv` with the\nsame bootstrap.\n',
     'new': 'If an offline output lacks a paired quantity, the v4 analysis script computes it from '
            '`per_clip_selected.csv` with the\nsame bootstrap, within that file\'s scope (TRAIN-selected candidates, '
            'subset all, alpha 0.05); a nested quantity comes\nfrom `paired.csv` only (Amendment A10).\n'},
    # one in-place text for both edits before "**Freeze.**" (apply_entry.py replaces in order: two overlapping texts
    # would lose the second); "old" starts at the last word of the "**Code.**" paragraph, which Amendment A9 rewraps
    {'section': '9.12, "**Code.**", end of the last sentence, and a new paragraph before "**Freeze.**"',
     'old': 'freeze.\n\n**Freeze.** The analysis freeze happens when every registered job of tiers 3-6 is final',
     'new': 'freeze (the aggregator: Amendment A3; the analysis code:\nAmendment A10).\n\n'
            '**Analysis code (Amendment A10).** `analyze_v4.py`, `prop1_coverage.py`, `figures_tables.py` and\n'
            '`verify_independent.py` (`framelease_v4/analysis/`) are registered by Amendment A10. Besides synthetic '
            'data, they were\nrun read-only during development on training-route aggregations, the offline VAL clips '
            'and P1 run directories, never\non a test-route run.\n\n**Freeze.** The analysis freeze happens when '
            'every registered job of tiers 3-6 is final'},
    {'section': '9.12, "**Freeze.**", last sentence',
     'old': '`outputs/framelease_v4/analysis/final_<stamp>/`, with a sha256 manifest.\n',
     'new': '`outputs/framelease_v4/analysis/final_<stamp>/`, with a sha256 manifest; the analysis writes into its '
            'subdirectory\n`analysis/` with its own manifest (Amendment A10).\n'},
    {'section': '9.12, "**Verification.**"',
     'old': '**Verification.** Before any number enters the paper, an independent session recomputes the H1 '
            'contrasts and the\nTable I columns from the raw run directories.\n',
     'new': '**Verification.** Before any number enters the paper, an independent session recomputes the H1 '
            'contrasts and the\nTable I columns from the raw run directories (Amendment A10: '
            '`framelease_v4/analysis/verify_independent.py`\nrecomputes DS, SR, RC, collisions/km and '
            'infractions/km; a second script, registered by its own amendment before\nthe analysis freeze, '
            'recomputes the other Table I columns, which enter the paper once its result is entered in\nSec. 13).\n'},
    {'section': '4.1, the status sentence of Amendment A3 (exists only after A3; confirm the wrapping, APPLY_PLAN2 '
                'Sec. 4)',
     'old': 'the analysis script, the Proposition-1 coverage and the figure and table generators remain required '
            'before the analysis freeze',
     'new': 'the analysis script, the Proposition-1 coverage, the figure and table generator and the independent '
            'verification script are registered by Amendment A10'},
]


def main():
    tests_a10 = [{'log': f'outputs/framelease_v4/amendment_a10/pytest_{n}.log',
                  'argv': [f'framelease_v4/analysis/tests/test_{n}.py']}
                 for n in ('analyze_v4', 'prop1_coverage', 'figures_tables', 'verify_independent')]
    a10 = {'name': 'A10', 'template': 'outputs/framelease_v4/build/AMEND2/final/A10_entry.md', 'tests': tests_a10,
           'inplace': [{'old': r['old'], 'new': r['new']} for r in INPLACE_A10],
           'must_equal': {p: sha(p) for p in A10_FILES + A10_REUSED}, 'max_new_registered': len(A10_FILES)}
    op = {'name': 'OP', 'note': 'apply_entry.py --tests only: the transaction is the manual one of APPLY_PLAN2.md '
                                'Sec. 3 (apply_entry.py requires a title "**Amendment <name>,"; --check and --apply '
                                'stop at the template check)',
          'template': 'outputs/framelease_v4/build/AMEND2/final/OP_phase_driver_entry.md',
          'tests': [{'log': 'outputs/framelease_v4/operational_phase_driver/pytest_phase_driver.log',
                     'argv': ['framelease_v4/protocol/tests/test_phase_driver.py']},
                    {'log': 'outputs/framelease_v4/operational_phase_driver/pytest_review_phase.log',
                     'argv': ['outputs/framelease_v4/build/PHASE/review/test_review_phase.py']}],
          'inplace': [], 'must_equal': {p: sha(p) for p in OP_FILES}, 'max_new_registered': 3}
    (OUT / 'A10_spec.json').write_text(json.dumps(a10, indent=1) + '\n', encoding='utf-8')
    (OUT / 'OP_spec.json').write_text(json.dumps(op, indent=1) + '\n', encoding='utf-8')
    text = (ROOT / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    for r in INPLACE_A10:
        print(f'{text.count(r["old"])}x  {r["section"]}')
        for ln in r['new'].splitlines():
            if len(ln) > 120:
                print('   new line over 120:', len(ln), ln[:60])


main()
