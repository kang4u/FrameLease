"""Write step3_spec.json, the fixed input of the step-3 transaction (APPLY_PLAN2.md Sec. 3; amend_step3.sh).

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/step3/make_step3_spec.py [--root DIR] [--out FILE]

Read only on the tree; writes only the spec (default: step3_spec.json next to this file). The spec holds:
  * the five entries in the order of step 3 (A3, A9, A7 = A7b, A4, the operational addition) and where their templates
    are (the sections of build/AMEND/AMENDMENTS_DRAFT.md, final/OP_phase_driver_entry.md);
  * the in-place texts, in the order they are applied (A3: Sec. 4.1 status paragraph, Sec. 8.6 layout; A9: Sec. 9.12
    "Code."; A7b: Sec. 7.6 S2; A4: Sec. 8.3 lead sentence, Sec. 8.3 pin bullets and per-arm totals, Sec. 4.1 status
    paragraph appended). Each "old" is the exact text of the current PROTOCOL.md (A4's Sec. 4.1 "old" is A3's new
    paragraph); each "new" is wrapped at 120 columns and names its amendment;
  * must_equal: the sha256 now of every file the five entries cite by {{sha256:...}} or {{pytest:...}} (the manifest
    excepted), of the four files of final/OP_spec.json "must_equal", and of the inputs of the transaction (the AMEND
    draft, the OP template, fill_entry.py, check_drafts.py, final/OP_spec.json and final/A10_spec.json, which
    check_drafts.py reads);
  * a3_files: the 38 files of Amendment A3 with the reviewed sha256 that A3 registers (the appendix of the AMEND
    draft: its list, then the last value of its review record table); the generator refuses to write the spec when a
    file differs from it;
  * expected_new_registered: the framelease_v4 files the five entries cite by sha256 (the 37 framelease_v4 files of A3
    and the three of the operational addition), which become registered by the transaction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import textwrap
import time
from pathlib import Path

REAL_ROOT = Path('/home/kang/Desktop/DAC')
HERE = Path(__file__).resolve().parent
SCHEMA = 'framelease_v4.amend_step3_spec/1'
DRAFT = 'outputs/framelease_v4/build/AMEND/AMENDMENTS_DRAFT.md'
A2 = 'outputs/framelease_v4/build/AMEND2'
OP_TEMPLATE = f'{A2}/final/OP_phase_driver_entry.md'
OP_SPEC = f'{A2}/final/OP_spec.json'
A10_SPEC = f'{A2}/final/A10_spec.json'
MANIFEST = 'outputs/framelease_v4/registration/MANIFEST.sha256'
PROTOCOL = 'framelease_v4/PROTOCOL.md'
# (name, amendment id or None, template: (file, heading of its section) or a template file)
ENTRIES = (('A3', 'A3', DRAFT, '## A3: registration of the Phase 2-7 tooling'),
           ('A9', 'A9', DRAFT, "## A9: Sec. 9.12 deviation, the aggregator's development data"),
           ('A7', 'A7', DRAFT, "### A7b: a supplementary grid relative to each state's own slack floor"),
           ('A4', 'A4', DRAFT, '## A4: realisation of the ablation arms'),
           ('OP', None, OP_TEMPLATE, None))
OP_TITLE_MARK = '(Beijing time): the phase driver of Phases 2-7'
PLACEHOLDER = re.compile(r'\{\{([^}]+)\}\}')
LIST_START = re.compile(r'^(>|(\d+[.)]|[-*+#|=])(\s|$))')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def wrap(text, first='', cont='', width=120):
    """Words of `text` wrapped at `width` (no word broken); no continuation line starts like a list item."""
    words = ' '.join(text.split())
    for w in range(width, 90, -1):
        lines = textwrap.wrap(words, width=w, initial_indent=first, subsequent_indent=cont, break_long_words=False,
                              break_on_hyphens=False)
        if all(not LIST_START.match(ln[len(cont):]) for ln in lines[1:]):
            return lines
    raise ValueError(f'cannot wrap: {words[:80]}')


def entry_template(root, name):
    """The entry text of `name` (from its bold title line to its manifest-and-seal line) as the transaction reads it."""
    _, aid, path, heading = next(e for e in ENTRIES if e[0] == name)
    text = (root / path).read_text(encoding='utf-8')
    if heading is None:
        return text.strip('\n') + '\n'
    lines = text.split('\n')
    starts = [i for i, ln in enumerate(lines) if ln == heading]
    if len(starts) != 1:
        raise ValueError(f'{path}: heading {heading!r} found {len(starts)} times')
    title = f'**Amendment {aid}, {{{{datetime}}}} (Beijing time):'
    i = next(j for j in range(starts[0], len(lines)) if lines[j].startswith(title))
    if any(lines[j].startswith('#') for j in range(starts[0] + 1, i)):
        raise ValueError(f'{name}: the title is not in the section {heading!r}')
    k = next(j for j in range(i, len(lines)) if lines[j].rstrip().endswith('sealed with this entry.'))
    if not any(lines[j].startswith('* Manifest and seal after this amendment:') for j in range(k - 2, k + 1)):
        raise ValueError(f'{name}: the entry does not end with its manifest-and-seal line')
    return '\n'.join(lines[i:k + 1]) + '\n'


# ------------------------------------------------------------------------------------------------ in-place texts

STATUS_A3 = ('Status (Amendment A3): the `fl_global_shield` lease of item 1, the aggregator of item 2 (with '
             'infractions '
             'per km), item 3 and item 4 are implemented and registered; the analysis script, the Proposition-1 '
             'coverage and the figure and table generators remain required before the analysis freeze.')
STATUS_A4 = ('`fl_bandit` and `fl_fqi_nolease` of item 1 are configurations of launcher arm `fl_full` with the '
             'networks '
             'of their families (Amendment A4).')
ITEM4 = "4. the P2-P6 job generators (the P2 run list is `framelease_v4/rl/collection_plan.py`).\n"
PLANNED = ("Planned for P4-P6 (generators not yet written):\n"
           "* `outputs/framelease_v4/matrix/<arm>/runs/`\n"
           "* `outputs/framelease_v4/fig3/<arm>_k<kappa>/runs/`\n"
           "* `outputs/framelease_v4/ablation/<arm>/runs/` and `outputs/framelease_v4/replicates/<arm>/runs/`\n"
           "* `outputs/framelease_v4/queue_p2/` and later queue directories\n")
LAYOUT_A3 = ('As fixed for P2-P6 by Amendment A3:', (
    '`outputs/framelease_v4/p2_jobs/FULL/b10_rl_data.{jsonl,stage.json,check.json}` (the P2 job file, its stage spec '
    "and its check; not a queue) and `outputs/framelease_v4/queue_p2/` (the runner's queue of P2);",
    '`outputs/framelease_v4/rl_freeze/` (the RL freeze, Sec. 5.9) and `outputs/framelease_v4/stress/` (the S1-S3 '
    'reports, Sec. 7.6);',
    '`outputs/framelease_v4/test_jobs/FULL/b<NN>_<block>.{jsonl,stage.json,check.json}` and `index.json` (the P4-P6 '
    'job files of tiers 3-6, blocks 11-16; not a queue) and `outputs/framelease_v4/test_freeze/` (the test freeze and '
    'its own sha256 manifest);',
    "`outputs/framelease_v4/queue_p4/` (the one runner's queue of P4-P6: the six job files in name order);",
    '`outputs/framelease_v4/matrix/<arm>/runs/`, `outputs/framelease_v4/fig3/<arm>_k<kappa>/runs/`, '
    '`outputs/framelease_v4/ablation/<arm>/runs/` and `outputs/framelease_v4/replicates/<arm>/runs/` (the P4-P6 runs; '
    '`<arm>` is the protocol arm).'))
CODE_912 = ("**Code.** `framelease_v4/analysis/aggregate_v4.py` (per-run rows, recomputed metrics, commit audit) and\n"
            "`framelease_v4/analysis/analyze_v4.py` (Secs. 9.1-9.9). Both are written and tested on synthetic CSVs "
            "only. "
            "Their\nsha256 is entered in Sec. 13 before the analysis freeze.\n")
A9_SENTENCE = ('The aggregator was also run read-only on finished P1 training-route runs during development '
               '(Amendment A9).')
S2_OLD = ("* **S2, near deadline.** Recorded states with D* moved so that the slack spans [-0.1, 0.6] s in 10 ms "
          "steps. "
          "Report:\n"
          "  * the share of admitted actions;\n"
          "  * the number of admitted actions whose bound >= D* (must be 0);\n"
          "  * the Q-network bypass rate.\n")
S2_ITEM4 = ("per kappa, the Eq. 5 slack floors of the states (min, p50, max), the grid values at or below every "
            "state's "
            "floor, the first admitting grid value and the admitted actions checked (Amendment A7).")
S2_SUPPLEMENTARY = ('Supplementary (Amendment A7): the same sweep with D* = t + f(state) + delta, f the state\'s '
                    'first-admissible slack, delta in [-0.1, 0.6] s in 10 ms steps; reported as supplementary, never '
                    'in place of the registered grid.')
LEAD_83 = "Every job carries `require_sha256` for (49 files, plus the envelope and the Q-network where they apply):\n"
LEAD_83_A4 = ('Every job carries `require_sha256` for (49 files, plus the envelope, the Q-network file and the '
              'extension '
              'sources where they apply; Amendment A4):')
PINS_83 = ("* the envelope file, for the shield arms;\n"
           "* the Q-network file, for `fl_full`, `fl_bandit` and `fl_fqi_nolease`.\n\n"
           "The runner blocks a job whose pinned files changed.")
PINS_83_A4 = (('the envelope file, for the arms with a lease (`fl_heuristic`, `fl_risk`, `fl_behaviour`, `fl_full`, '
               '`fl_bandit`, `fl_fqi_nolease`, `fl_global_shield`);'),
              ('the Q-network FILE, at the sha256 the RL freeze records, for `fl_full`, `fl_bandit` and '
               '`fl_fqi_nolease` (the network name pins neither B_pi nor the provenance);'),
              ('the five extension sources '
               '`framelease_v4/arms_ext/{__init__,global_shield,arms_ext,agent_ext,run_closed_loop_ext}.py`, for '
               '`fl_global_shield` (they are frozen into every run of the arm).'))
TOTALS_83_A4 = ('Pins per job line: 49 for `fixed_deep`, `fast_only`, `fl_original`, `age_only` and `event_triggered`; '
                '50 for `fl_heuristic`, `fl_risk` and `fl_behaviour`; 51 for `fl_full`, `fl_bandit` and '
                '`fl_fqi_nolease`; 55 for `fl_global_shield`. Every P4-P6 common pin equals the pin of the registered '
                'P1 lines (`registration.job_pins`).')


def block(lines):
    return '\n'.join(lines) + '\n'


def inplace_texts():
    """[{amendment, where, old, new}] in the order of application (module docstring)."""
    status_a3 = wrap(STATUS_A3)
    status_a4 = status_a3[:-1] + wrap(status_a3[-1] + ' ' + STATUS_A4)    # the earlier lines keep their breaks
    layout = [LAYOUT_A3[0]] + [ln for item in LAYOUT_A3[1] for ln in wrap(item, '* ', '  ')]
    code = wrap(' '.join(CODE_912.split()).replace('Both are written and tested on synthetic CSVs only.',
                                                   'Both are written and tested on synthetic CSVs only. '
                                                   + A9_SENTENCE))
    s2 = S2_OLD.replace('  * the Q-network bypass rate.\n', '  * the Q-network bypass rate;\n')
    s2 += block(wrap(S2_ITEM4, '  * ', '    ')) + '\n' + block(wrap(S2_SUPPLEMENTARY, '  ', '  '))
    pins = ''.join(block(wrap(p, '* ', '  ')) for p in PINS_83_A4) + '\n' + block(wrap(TOTALS_83_A4)) + \
        '\nThe runner blocks a job whose pinned files changed.'
    return [
        {'amendment': 'A3', 'where': 'Sec. 4.1, after item 4 of "Still required, not needed for Phase 1": the status '
                                     'paragraph', 'old': ITEM4, 'new': ITEM4 + '\n' + block(status_a3)},
        {'amendment': 'A3', 'where': 'Sec. 8.6, "Planned for P4-P6 (generators not yet written)" replaced by the '
                                     'layout '
                                     'that Amendment A3 fixes', 'old': PLANNED, 'new': block(layout)},
        {'amendment': 'A9', 'where': 'Sec. 9.12, "**Code.**": the A9 sentence after "Both are written and tested on '
                                     'synthetic CSVs only."', 'old': CODE_912, 'new': block(code)},
        {'amendment': 'A7', 'where': 'Sec. 7.6, S2: a fourth item of "Report" and the supplementary paragraph after '
                                     'the '
                                     'list (variant A7b)', 'old': S2_OLD, 'new': s2},
        {'amendment': 'A4', 'where': 'Sec. 8.3, the lead sentence', 'old': LEAD_83, 'new': block(wrap(LEAD_83_A4))},
        {'amendment': 'A4', 'where': 'Sec. 8.3, the last two pin bullets replaced by three, the per-arm totals after '
                                     'the '
                                     'list', 'old': PINS_83, 'new': pins},
        {'amendment': 'A4', 'where': 'Sec. 4.1, the status paragraph of Amendment A3, appended',
         'old': block(status_a3), 'new': block(status_a4)},
    ]


def apply_inplace(text, inplace):
    """text with every in-place replacement applied in order; ValueError when an "old" does not occur exactly once."""
    for r in inplace:
        n = text.count(r['old'])
        if n != 1:
            raise ValueError(f'in-place text of {r["amendment"]} ({r["where"]}) found {n} times')
        text = text.replace(r['old'], r['new'])
    return text


# ------------------------------------------------------------------------------------------------ A3 review record

def a3_reviewed(root):
    """{path: the sha256 Amendment A3 registers}: the appendix list of the AMEND draft, overridden by the last value of
    each row of its review record table."""
    text = (root / DRAFT).read_text(encoding='utf-8')
    app = text[text.index('## Appendix: sha256 at drafting'):]
    listed = dict(reversed(m.groups()) for m in re.finditer(r'^([0-9a-f]{64})  (\S+)$', app, re.M))
    a3_paths = [k for k in PLACEHOLDER.findall(entry_template(root, 'A3')) if k.startswith('sha256:')
                and not k.endswith('MANIFEST.sha256') and '/build/' not in k and 'amendment_a3' not in k]
    want = {}
    for key in dict.fromkeys(a3_paths):
        p = key.partition(':')[2]
        want[p] = listed[p]
    for row in re.finditer(r'^\| `([^`]+)` \| `([0-9a-f]{64})` \|(.*)$', app, re.M):
        vals = re.findall(r'`([0-9a-f]{64})`', row.group(3))
        if row.group(1) in want and vals:
            want[row.group(1)] = vals[-1]
    return want


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=str(REAL_ROOT))
    ap.add_argument('--out', default=str(HERE / 'step3_spec.json'))
    a = ap.parse_args()
    root = Path(a.root)
    templates = {n: entry_template(root, n) for n, *_ in ENTRIES}
    inplace = inplace_texts()
    text = (root / PROTOCOL).read_text(encoding='utf-8')
    after = apply_inplace(text, inplace)                     # each "old" exactly once at its turn (raises otherwise)
    for r in inplace:
        for ln in r['new'].splitlines():
            if len(ln) > 120:
                raise ValueError(f'{r["amendment"]} in-place line of {len(ln)} columns: {ln[:60]}')
    keys = [k for t in templates.values() for k in PLACEHOLDER.findall(t)]
    cited = sorted({k.partition(':')[2] for k in keys if k.partition(':')[0] in ('sha256', 'pytest')} - {MANIFEST})
    bad = [k for k in keys
           if k not in ('datetime', 'manifest:files') and k.partition(':')[0] not in ('sha256', 'pytest')]
    if bad:
        raise ValueError(f'placeholders the fill rules do not know: {bad}')
    missing = [p for p in cited if not (root / p).is_file()]
    if missing:
        raise ValueError(f'cited files missing: {missing}')
    op_spec = json.loads((root / OP_SPEC).read_text(encoding='utf-8'))
    inputs = [DRAFT, OP_TEMPLATE, OP_SPEC, A10_SPEC, f'{A2}/fill_entry.py', f'{A2}/check_drafts.py']
    must = {p: sha256(root / p) for p in sorted(set(cited) | set(op_spec['must_equal']) | set(inputs))}
    drift = {p: (s, op_spec['must_equal'][p]) for p, s in must.items() if op_spec['must_equal'].get(p, s) != s}
    if drift:
        raise ValueError(f'final/OP_spec.json must_equal differs from the tree: {drift}')
    a3 = a3_reviewed(root)
    a3_drift = {p: (s, must.get(p) or sha256(root / p)) for p, s in a3.items()
                if (must.get(p) or sha256(root / p)) != s}
    if len(a3) != 38 or a3_drift:
        raise ValueError(f'A3 files: {len(a3)} (expected 38); not at the reviewed sha256: {a3_drift}')
    new_reg = sorted({k.partition(':')[2] for k in keys if k.startswith('sha256:framelease_v4/')})
    a3_v4 = sorted(p for p in a3 if p.startswith('framelease_v4/'))
    op_v4 = sorted(p for p in op_spec['must_equal'] if p.startswith('framelease_v4/'))
    if new_reg != sorted(a3_v4 + op_v4) or len(new_reg) != 40:
        raise ValueError(f'framelease_v4 files cited by sha256: {len(new_reg)}, expected the 37 of A3 and the 3 of the '
                         f'operational addition')
    spec = {'schema': SCHEMA, 'generated': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'note': 'input of amend_step3.sh / step3_txn.py (APPLY_PLAN2.md Sec. 3); written by make_step3_spec.py',
            'entries': [{'name': n, 'amendment': aid, 'template': p, 'heading': h} for n, aid, p, h in ENTRIES],
            'op_title_mark': OP_TITLE_MARK,
            'inplace': inplace, 'must_equal': must, 'a3_files': a3, 'expected_new_registered': new_reg,
            'protocol_sha256_at_generation': sha256(root / PROTOCOL),
            'protocol_after_inplace_sha256_at_generation': hashlib.sha256(after.encode('utf-8')).hexdigest()}
    Path(a.out).write_text(json.dumps(spec, indent=1, sort_keys=False) + '\n', encoding='utf-8')
    print(f'wrote {a.out}: {len(inplace)} in-place texts, {len(must)} files in must_equal, {len(a3)} A3 files, '
          f'{len(new_reg)} files registered by the transaction; sha256 {sha256(a.out)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
