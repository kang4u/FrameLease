"""Print an entry template with its placeholders filled, by the rules of outputs/framelease_v4/paper_tools/apply_entry.py
(read only; writes nothing). For a transaction that apply_entry.py cannot run: the operational addition (its title is
not "**Amendment <name>,"), or several entries under one manifest and one seal (APPLY_PLAN2.md Sec. 3).

  cd /home/kang/Desktop/DAC
  .conda-unidrive-linux/bin/python -I -B outputs/framelease_v4/build/AMEND2/fill_entry.py TEMPLATE [--datetime 'YYYY-MM-DD HH:MM']

Run it after registration.py --write-manifest --force (inside the lock): {{manifest:files}} is the line count of
outputs/framelease_v4/registration/MANIFEST.sha256 and {{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}
its sha256 at that moment. {{datetime}} defaults to now; give the same --datetime to every entry of one transaction.
{{sha256:<path>}} is the sha256 of <path>, {{pytest:<log>}} the summary line of the log (apply_entry.pytest_summary).
Exit 1 (nothing printed) when a placeholder cannot be filled, a test log reports a failure or an error, or the filled
text contains the anchor phrase "Each amendment gets the date and time"; stderr lists the framelease_v4 files the entry
cites by sha256 (the files it registers when they are not registered yet).
"""
import argparse
import hashlib
import re
import sys
import time
from pathlib import Path

ROOT = Path('/home/kang/Desktop/DAC')
MANIFEST = ROOT / 'outputs/framelease_v4/registration/MANIFEST.sha256'
ANCHOR = 'Each amendment gets the date and time'


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def pytest_summary(log):
    lines = [ln.strip('= ').strip() for ln in Path(log).read_text(errors='replace').splitlines()
             if re.search(r'\d+ (passed|failed|error)', ln)]
    return lines[-1] if lines else ''


def fill(text, when):
    """(filled text, [problems])."""
    problems = []

    def sub(m):
        key = m.group(1)
        if key == 'datetime':
            return when
        if key == 'manifest:files':
            return str(sum(1 for ln in MANIFEST.read_text().splitlines() if '  ' in ln))
        kind, _, arg = key.partition(':')
        path = ROOT / arg
        if kind not in ('sha256', 'pytest') or not path.is_file():
            problems.append(f'cannot fill {{{{{key}}}}}')
            return m.group(0)
        if kind == 'sha256':
            return sha256(path)
        s = pytest_summary(path)
        if not s or 'failed' in s or 'error' in s:
            problems.append(f'test log {arg}: {s!r}')
        return s

    out = re.sub(r'\{\{([^}]+)\}\}', sub, text)
    if ANCHOR in out:
        problems.append(f'the text contains the anchor phrase "{ANCHOR}"')
    return out, problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('template')
    ap.add_argument('--datetime', default=time.strftime('%Y-%m-%d %H:%M'))
    a = ap.parse_args()
    tmpl = Path(a.template).read_text(encoding='utf-8').strip('\n') + '\n'
    cited = sorted({k for k in re.findall(r'\{\{sha256:(framelease_v4/[^}]+)\}\}', tmpl)})
    out, problems = fill(tmpl, a.datetime)
    if problems:
        print('\n'.join(problems), file=sys.stderr)
        return 1
    print('framelease_v4 files cited by sha256:', ', '.join(cited) or 'none', file=sys.stderr)
    sys.stdout.write(out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
