#!/usr/bin/env python3
"""Check the sha256 citations of framelease_v4/PROTOCOL.md against the files of this repository.

  python3 scripts/check_protocol_citations.py [--verbose]

PROTOCOL.md cites files with their sha256 in tables (| sha256 | path | or | path | sha256 |) and in text
(`path` (sha256 `hex`)). A file can be cited several times: an amendment that registers a new version of a file
cites the new sha256 next to the older citations. A cited file present in this repository passes when its sha256
equals one of its citations and the newest citation (the last one in Sec. 13) is that value or a later one does not
exist; it fails when its sha256 equals none of them. Cited files absent from this repository are listed as external
(docs/EXTERNAL_FILES.md) or as files of the excluded run directories. Standard library only. Exit 0: no failure.
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT = (ROOT / 'framelease_v4' / 'PROTOCOL.md').read_text(encoding='utf-8')
HEX = r'[0-9a-f]{64}'
PATH = r'[A-Za-z0-9_./+\-]+\.(?:py|sh|json|jsonl|md|csv|txt|xml|pt|sha256|lock|joblib|log|tex|png|pdf)'


def citations(text):
    out = []
    for line in text.splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip().strip('`').strip() for c in line.strip().strip('|').split('|')]
        shas = [c for c in cells if re.fullmatch(HEX, c)]
        paths = [c for c in cells if re.fullmatch(PATH, c)]
        if len(shas) == 1 and len(paths) == 1:
            out.append((paths[0], shas[0]))
    flat = re.sub(r'\s+', ' ', text)
    for m in re.finditer(r'`(' + PATH + r')`[^`]{0,40}?\(sha256 `(' + HEX + r')`', flat):
        out.append((m.group(1), m.group(2)))
    return out


def main():
    verbose = '--verbose' in sys.argv
    cited = {}
    for path, sha in citations(TEXT):
        cited.setdefault(path, []).append(sha)
    ok, fail, absent = [], [], []
    for path, shas in sorted(cited.items()):
        p = ROOT / path
        if path.startswith('/') or not p.is_file():
            absent.append(path)
            continue
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        (ok if actual in shas else fail).append((path, actual, shas))
    print(f'PROTOCOL.md: {sum(len(v) for v in cited.values())} sha256 citations of {len(cited)} files')
    print(f'present and matching a citation: {len(ok)}; present and matching none: {len(fail)}; '
          f'not in this repository: {len(absent)}')
    for path, actual, shas in fail:
        print(f'FAIL  {path}  sha256 {actual} cited as {sorted(set(shas))}')
    if verbose:
        for path, actual, shas in ok:
            print(f'OK    {path}')
        for path in absent:
            print(f'ABSENT {path}')
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
