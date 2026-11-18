"""Write outputs/framelease_v4/build/AMEND2/AMENDMENTS2_DRAFT.md: the front matter, the two entry templates of final/
verbatim, and the sha256 at drafting of every file the entries cite (and sha256_at_drafting.txt). Rerun only to rebuild
the draft after an entry template changed."""
import hashlib
import re
import time
from pathlib import Path

ROOT = Path('/home/kang/Desktop/DAC')
HERE = ROOT / 'outputs/framelease_v4/build/AMEND2'
MANIFEST = 'outputs/framelease_v4/registration/MANIFEST.sha256'


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


HEAD = """# PROTOCOL Sec. 13.2 entries of item AMEND2: drafts

Status: DRAFTS. `framelease_v4/PROTOCOL.md` is not edited by this item. The coordinating session applies each entry
under `framelease_v4/.protocol.lock` in the order and with the steps of `APPLY_PLAN2.md` (same directory). The entry
texts below are verbatim copies of the templates `final/OP_phase_driver_entry.md` and `final/A10_entry.md`, which are
the files an applier reads (`check_drafts.py` checks that both copies agree).

## Placeholders

As in `outputs/framelease_v4/build/AMEND/AMENDMENTS_DRAFT.md`:
* `{{datetime}}`: the time of application, `YYYY-MM-DD HH:MM` (Beijing time).
* `{{sha256:<path>}}`: the full 64-hex sha256 of `<path>` (project-relative) at application. The full value is what
  registers a manifest file (the phase driver's baseline adds a manifest file only when PROTOCOL.md cites its full
  sha256). The appendix lists the values at drafting; a different value at application means the file changed after
  drafting, and its review status is re-checked first (`final/*_spec.json` "must_equal" stops `apply_entry.py`).
* `{{pytest:<log>}}`: the summary line of that pytest log (`apply_entry.py` `pytest_summary`).
* `{{manifest:files}}` and `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`: the count and the sha256
  printed by `registration.py --write-manifest --force`.

## Constraints on the inserted text

Those of `AMEND/AMENDMENTS_DRAFT.md` ("Constraints on the inserted text"), and in addition:
* No entry contains the phrase "Each amendment gets the date and time" anywhere: `apply_entry.py` inserts at the first
  occurrence of the phrase and requires exactly one in PROTOCOL.md.
* No line reads as an entry of the phase driver (`phase_driver.ENTRY_RE`: a bullet that starts with a gate and its
  label in bold) or as its heading "**Phase gates (P2-P7, FULL).**" on a line of its own.
* The operational addition carries no line that `phase_driver.AMEND_RE` reads as an amendment title, does not cite the
  sha256 of `analyze_v4.py` (gate G8 attributes the first line that cites it to the amendment title above it,
  `phase_driver.citing_amendment`) and does not match `phase_driver.A7B_RE` (an operational addition placed after
  Amendment A7 is read as part of A7's text when the driver decides between A7a and A7b).
* A10 cites `analyze_v4.py` by sha256 in its Files table only, below its own title.
* Prose lines of the FILLED text are at most 120 columns (a 64-hex sha256 is longer than its placeholder); table rows
  stay single lines.

`check_drafts.py` (same directory, read only) checks all of this on the filled texts and simulates the application on
a copy of PROTOCOL.md in memory: the operational addition, the phase driver's heading with one gate entry and A10,
each inserted where `apply_entry.py` and the phase driver insert them, plus the in-place texts of A10 that exist now.
`p1_driver.protocol_view` and `phase_driver.phase_view` then raise no ALERT, the P1 entries are unchanged, and the
line citing `analyze_v4.py` belongs to A10. It also reports the open preconditions of the texts (exit 2): step 0 of
`APPLY_PLAN2.md` (A10 finding 1 states the settled commit-audit rule) and the edits E1-E4 of the AMEND drafts
(`APPLY_PLAN2.md` Sec. 3, step 0). Application needs exit 0, "all checks passed".

---

## Operational addition: the phase driver

Registers `framelease_v4/protocol/phase_driver.py`, `start_phase_driver.sh` and `tests/test_phase_driver.py`. Applied
together with Amendment A3 (the last entry of that transaction, `APPLY_PLAN2.md` Sec. 2, step 3) or right after it,
after P1 ends and before the phase driver starts (step 5). `apply_entry.py` cannot apply it (its title check requires
"**Amendment <name>,"); `final/OP_spec.json` serves its `--tests` mode only, and the transaction follows
`APPLY_PLAN2.md` Sec. 3. No in-place text.

"""

MID = """
---

## A10: registration of the analysis code

Registers `framelease_v4/analysis/{analyze_v4,prop1_coverage,figures_tables,verify_independent}.py` and their tests
(the five aggregator modules and `__init__.py` are Amendment A3's). Applied after A3 and before the analysis freeze
(gate G8 waits for it); recommended before the test freeze (`APPLY_PLAN2.md` Sec. 2, step 6). `final/A10_spec.json`
drives `apply_entry.py` (`--tests`, then `--apply` under the lock); its second in-place text starts at the end of the
Sec. 9.12 paragraph that A9 extends, and its fifth exists only after A3: both are confirmed after step 3
(`APPLY_PLAN2.md` Sec. 4).

"""


def main():
    op = (HERE / 'final/OP_phase_driver_entry.md').read_text(encoding='utf-8').strip('\n')
    a10 = (HERE / 'final/A10_entry.md').read_text(encoding='utf-8').strip('\n')
    paths = []
    for t in (op, a10):
        for key in re.findall(r'\{\{sha256:([^}]+)\}\}', t):
            if (ROOT / key).is_file() and key not in paths and key != MANIFEST:
                paths.append(key)
    later = sorted({k for t in (op, a10) for k in re.findall(r'\{\{sha256:([^}]+)\}\}', t)
                    if not (ROOT / k).is_file() or k == MANIFEST})
    app = ['', '---', '', f'## Appendix: sha256 at drafting ({time.strftime("%Y-%m-%d %H:%M")}, Beijing time)', '',
           'A value at application that differs from this list means the file changed after drafting; its review',
           'status is re-checked before the entry is applied.', '', '```']
    app += [f'{sha(ROOT / p)}  {p}' for p in paths] + ['```', '', 'Written at application (no value at drafting):', '']
    app += [f'* `{p}`' for p in later]
    text = HEAD + op + '\n' + MID + a10 + '\n' + '\n'.join(app) + '\n'
    (HERE / 'AMENDMENTS2_DRAFT.md').write_text(text, encoding='utf-8')
    (HERE / 'sha256_at_drafting.txt').write_text(''.join(f'{sha(ROOT / p)}  {p}\n' for p in paths), encoding='utf-8')
    print(len(paths), 'files with a sha256 at drafting;', len(later), 'written at application')


main()
