#!/usr/bin/env python3
"""Write the D1 decision of the coordinating session, outputs/framelease_v4/phase_driver/D1_DECISION.json
(APPLY_PLAN2.md Sec. 3 "Step 4"; PROTOCOL Sec. 4.8; gate G1 of framelease_v4/protocol/phase_driver.py).

  cd /home/kang/Desktop/DAC
  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/step3/write_d1_decision.py --decision continue \
      --rationale-file <file> [--dry-run]

Reads outputs/framelease_v4/tuning/d1/FULL_d1_summary.json and checks, as gate G1 does (phase_driver.load_decision):
the file is a D1 summary of FULL (schema framelease_v4.d1_summary/1); its sha256 is the one the P1 stage driver's
"D1 summary" entry in PROTOCOL.md Sec. 13.2 cites (and the one P1_DONE.json records); no D1 decision entry of the
phase driver exists yet; D1_DECISION.json does not exist yet (a decision is never replaced). The rationale (the
reasons, from the D1 summary) is read from --rationale-file; it enters Sec. 13.2 through the G1 entry, so it must be
non-empty, at most 4000 characters as one line (the driver cuts longer text), and free of the anchor phrase "Each
amendment gets the date and time", of '{{' / '}}' and of any mention of who or what wrote it.
Writes (without --dry-run) the decision as a temporary file in the same directory, then renames it to
D1_DECISION.json (the driver reads a partial file again for 120 s, then raises an ALERT):
  {"schema": "framelease_v4.d1_decision/1", "decision": "continue" | "stop", "rationale": "<text>",
   "d1_summary_sha256": "<sha256>", "decided": "<ISO time>", "by": "the coordinating session"}
The G1 entry of the phase driver reads "... decided <time> by <by>, on the D1 summary ...": --by (default "the
coordinating session", the driver's own wording when the key is absent) is one line of at most 120 characters, free of
the anchor phrase, of '{{' / '}}' and of any mention of who or what wrote the text.
--dry-run prints the JSON only. --root names a scratch copy (tests). Exit 0 written / printed, 1 refused.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

REAL_ROOT = Path('/home/kang/Desktop/DAC')
SCHEMA = 'framelease_v4.d1_decision/1'
D1_SCHEMA = 'framelease_v4.d1_summary/1'
SUMMARY = 'outputs/framelease_v4/tuning/d1/FULL_d1_summary.json'
DECISION = 'outputs/framelease_v4/phase_driver/D1_DECISION.json'
P1_DONE = 'outputs/framelease_v4/p1_driver/P1_DONE.json'
PROTOCOL = 'framelease_v4/PROTOCOL.md'
ANCHOR = 'Each amendment gets the date and time'
RATIONALE_LIMIT = 4000                       # phase_driver.one_line: longer text is cut in the G1 entry
AUTHORSHIP = re.compile(r'\b(AI|LLM|GPT|ChatGPT|Claude|chatbot|language model|assistant)\b', re.I)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def problems_of(root, decision, rationale, by='the coordinating session'):
    """(problems, d1 summary sha256)."""
    probs = []
    by_text = ' '.join(by.split())
    if not by_text or len(by_text) > 120 or by_text != by or ANCHOR in by or '{{' in by or '}}' in by:
        probs.append(f'--by {by!r}: one line of at most 120 characters without the anchor phrase or placeholder braces')
    if AUTHORSHIP.search(by):
        probs.append(f'--by names who or what wrote the text ({AUTHORSHIP.search(by).group(0)!r})')
    if decision not in ('continue', 'stop'):
        probs.append(f'decision {decision!r} (continue or stop)')
    text = ' '.join(rationale.split())
    if not text:
        probs.append('the rationale is empty')
    if len(text) > RATIONALE_LIMIT:
        probs.append(f'the rationale has {len(text)} characters as one line (at most {RATIONALE_LIMIT})')
    if ANCHOR in text or '{{' in text or '}}' in text:
        probs.append(f'the rationale holds the anchor phrase "{ANCHOR}" or a placeholder brace')
    if AUTHORSHIP.search(text):
        probs.append(f'the rationale names who or what wrote it ({AUTHORSHIP.search(text).group(0)!r})')
    spath = root / SUMMARY
    if not spath.is_file():
        return probs + [f'{SUMMARY} does not exist (P1 has not ended)'], None
    want = sha256(spath)
    try:
        doc = json.loads(spath.read_text(encoding='utf-8'))
    except ValueError:
        doc = None
    if not isinstance(doc, dict) or doc.get('schema') != D1_SCHEMA or doc.get('variant') != 'FULL':
        probs.append(f'{SUMMARY} is not a D1 summary of FULL ({D1_SCHEMA})')
    sys.dont_write_bytecode = True
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from framelease_v4.protocol import phase_driver as PD
    if Path(PD.__file__).resolve() != (root / 'framelease_v4/protocol/phase_driver.py').resolve():
        return probs + [f'phase_driver imported from {PD.__file__}'], want
    view = PD.phase_view(None, (root / PROTOCOL).read_text(encoding='utf-8'))
    ent = view['p1_entries'].get('d1')
    if ent is None:
        probs.append('PROTOCOL.md Sec. 13.2 has no "D1 summary" entry of the P1 stage driver')
    elif want not in ent['shas']:
        probs.append(f'the "D1 summary" entry (line {ent["line"]}) does not cite {want}, the sha256 of {SUMMARY}')
    if 'd1_decision' in view['entries']:
        probs.append(f'Sec. 13.2 holds the G1 D1 decision entry already (line '
                     f'{view["entries"]["d1_decision"]["line"]})')
    done = root / P1_DONE
    try:
        rec = json.loads(done.read_text(encoding='utf-8')).get('d1', {}).get('json_sha256')
    except (OSError, ValueError, AttributeError):
        rec = None
    if rec != want:
        probs.append(f'{P1_DONE} records the D1 summary sha256 {rec}, not {want}')
    if (root / DECISION).exists():
        probs.append(f'{DECISION} exists already: a decision is never replaced')
    return probs, want


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--decision', required=True, choices=('continue', 'stop'))
    ap.add_argument('--rationale-file', required=True)
    ap.add_argument('--dry-run', action='store_true', help='print the JSON only; write nothing')
    ap.add_argument('--root', default=str(REAL_ROOT), help='project root (tests: a scratch copy)')
    ap.add_argument('--by', default='the coordinating session',
                    help='who decided (G1 entry: "by <by>"); default: the coordinating session')
    a = ap.parse_args()
    root = Path(a.root).resolve()
    try:
        rationale = Path(a.rationale_file).read_text(encoding='utf-8')
    except OSError as e:
        print(f'REFUSED: --rationale-file: {e}')
        return 1
    probs, d1_sha = problems_of(root, a.decision, rationale, a.by)
    if probs:
        for p in probs:
            print(f'REFUSED: {p}')
        return 1
    doc = {'schema': SCHEMA, 'decision': a.decision, 'rationale': ' '.join(rationale.split()),
           'd1_summary_sha256': d1_sha, 'decided': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'by': a.by}
    text = json.dumps(doc, indent=1) + '\n'
    if a.dry_run:
        sys.stdout.write(text)
        return 0
    path = root / DECISION
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_name(f'.D1_DECISION.json.tmp.{os.getpid()}')
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    if path.exists():                                   # appeared meanwhile: never replaced
        tmp.unlink()
        print(f'REFUSED: {DECISION} appeared while this decision was written')
        return 1
    os.rename(tmp, path)
    print(f'wrote {DECISION}: decision {a.decision}, sha256 {sha256(path)}; D1 summary sha256 {d1_sha}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
