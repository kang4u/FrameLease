"""Round-2 review of A11: insert the filled A11 entry into a scratch copy of the CURRENT sealed PROTOCOL.md (A10 and
A12 in it) as apply_entry_stream.py composes it, and read the result with both drivers' parsers. Read only on the
project; writes only under /tmp/A11R2/.

  taskset -c 12-15 nice -n 19 ionice -c 3 <wrapper> python -I -B r2_insert_check.py /tmp/A11R2/PROTOCOL.sealed.md \
      --stamp '2026-11-16 02:00' --logs-dir outputs/framelease_v4/build/AMEND2/a10r7b/f1/logs --out /tmp/A11R2/sim

The fill: {{datetime}} = --stamp; {{sha256:<path>}} = the current sha256 (the manifest: its current sha256, which
--write-manifest leaves unchanged when no file changed); {{pytest:<log>}} = the pytest summary of the log of the same
name in --logs-dir (also with a summary two characters longer, to cover a slower test run); {{manifest:files}} = the
number of files of the current manifest.
"""
import argparse
import hashlib
import json
import os
import re
import sys

sys.dont_write_bytecode = True
ROOT = '/home/kang/Desktop/DAC'
sys.path.insert(0, ROOT)
from framelease_v4.protocol import p1_driver as P1  # noqa: E402
from framelease_v4.protocol import phase_driver as PD  # noqa: E402

A = ROOT + '/outputs/framelease_v4/build/AMEND2/a10r7b'
ANCHOR = 'Each amendment gets the date and time'
MAN = 'outputs/framelease_v4/registration/MANIFEST.sha256'
PH = re.compile(r'\{\{([^}]+)\}\}')
R7B = ('framelease_v4/analysis/verify_table1_extra.py', 'framelease_v4/analysis/tests/test_verify_table1_extra.py')
HEDGE = re.compile(r'\b(may|might|could|perhaps|possibly|probably|likely|seems?|appears?|arguably|roughly|'
                   r'approximately|we believe|should be|hopefully)\b', re.I)


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def summary(log):
    lines = [ln.strip('= ').strip() for ln in open(log, errors='replace').read().splitlines()
             if re.search(r'\d+ (passed|failed|error)', ln)]
    return lines[-1] if lines else ''


def fill(tmpl, stamp, logs_dir, n_files, pad=0):
    def sub(m):
        k = m.group(1)
        if k == 'datetime':
            return stamp
        if k == 'manifest:files':
            return str(n_files)
        if k.startswith('sha256:'):
            p = k.split(':', 1)[1]
            if p.startswith('outputs/framelease_v4/amendment_a11/'):       # a test log: its copy in --logs-dir
                p = os.path.join(logs_dir, os.path.basename(p))
            return sha(os.path.join(ROOT, p))
        if k.startswith('pytest:'):
            s = summary(os.path.join(ROOT, logs_dir, os.path.basename(k.split(':', 1)[1])))
            return s + 'x' * pad
        raise KeyError(k)
    return PH.sub(sub, tmpl)


def driver_line(ln):
    return (ln.startswith(('## ', ANCHOR)) or P1.ENTRY_RE.match(ln) or PD.ENTRY_RE.match(ln) or PD.AMEND_RE.match(ln)
            or ln.strip() in (P1.HEADING, PD.HEADING, P1.SEC_START))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('protocol')
    ap.add_argument('--stamp', required=True)
    ap.add_argument('--logs-dir', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    if not os.path.realpath(a.out).startswith('/tmp/A11R2/'):
        sys.exit('--out must lie under /tmp/A11R2/')
    os.makedirs(a.out, exist_ok=True)
    text = open(a.protocol, encoding='utf-8').read()
    spec = json.load(open(A + '/A11_spec.json'))
    tmpl = open(os.path.join(ROOT, spec['template']), encoding='utf-8').read().strip('\n') + '\n'
    n_files = sum(1 for ln in open(os.path.join(ROOT, MAN)) if '  ' in ln)
    res = {'protocol_sha256': hashlib.sha256(text.encode()).hexdigest(), 'stamp': a.stamp, 'problems': []}
    for pad in (0, 2):
        entry = fill(tmpl, a.stamp, a.logs_dir, n_files, pad)
        lines = entry.splitlines()
        wide = [(i + 1, len(ln)) for i, ln in enumerate(lines) if len(ln) > 120 and not ln.lstrip().startswith('|')]
        res['pad%d_wide_prose_lines' % pad] = wide
        res['pad%d_max_prose_width' % pad] = max(len(ln) for ln in lines if not ln.lstrip().startswith('|'))
        if wide:
            res['problems'].append('prose lines over 120 columns (pad %d): %s' % (pad, wide))
    entry = fill(tmpl, a.stamp, a.logs_dir, n_files)
    lines = entry.splitlines()
    res['entry_lines'] = len(lines)
    res['table_rows_over_120'] = sum(1 for ln in lines if len(ln) > 120 and ln.lstrip().startswith('|'))
    res['driver_lines_after_title'] = [ln[:80] for ln in lines[1:] if driver_line(ln)]
    res['title_amend_re'] = bool(PD.AMEND_RE.match(lines[0])) and PD.AMEND_RE.match(lines[0]).group('id')
    res['unfilled'] = PH.findall(entry)
    res['anchor_in_entry'] = entry.count(ANCHOR)
    res['lines_starting_star_star'] = [ln[:60] for ln in lines[1:] if ln.startswith('**')]
    res['hedge_words'] = sorted({m.group(0).lower() for m in HEDGE.finditer(entry)})
    res['ai_mentions'] = [ln[:80] for ln in lines if re.search(r'\b(AI|LLM|Claude|GPT|assistant)\b', ln)]
    for k in ('driver_lines_after_title', 'unfilled', 'lines_starting_star_star'):
        if res[k]:
            res['problems'].append('%s: %s' % (k, res[k]))
    if res['anchor_in_entry'] or res['title_amend_re'] != 'A11':
        res['problems'].append('anchor in entry or title not read as A11')
    # compose as apply_entry_stream.py does
    cur = text
    for r in spec['inplace']:
        res.setdefault('inplace_count', []).append(cur.count(r['old']))
        cur = cur.replace(r['old'], r['new'])
    if text.count(ANCHOR) != 1:
        res['problems'].append('anchor count %d' % text.count(ANCHOR))
    k = cur.index(ANCHOR)
    cur = cur[:k].rstrip('\n') + '\n\n' + entry + '\n' + cur[k:]
    old_lines = set(text.split('\n'))
    added = [ln for ln in cur.split('\n') if ln not in old_lines]
    res['added_or_changed_lines'] = len(added)
    res['added_prose_over_120'] = [ln[:60] for ln in added if len(ln) > 120 and not ln.lstrip().startswith('|')]
    if res['added_prose_over_120']:
        res['problems'].append('added prose over 120: %s' % res['added_prose_over_120'])
    # the drivers' parsers
    pv0, v0 = P1.protocol_view(None, text), PD.phase_view(None, text)
    pv1, v1 = P1.protocol_view(None, cur), PD.phase_view(None, cur)
    res['amendments_before'] = {x: len(y) for x, y in sorted(v0['amendments'].items())}
    res['amendments_after'] = {x: len(y) for x, y in sorted(v1['amendments'].items())}
    res['a11_lines'] = v1['amendments'].get('A11')
    if res['amendments_after'] != dict(res['amendments_before'], A11=1):
        res['problems'].append('amendment titles after A11: %s' % res['amendments_after'])
    for key, x, y in (('p1', pv0, pv1), ('phase', v0, v1)):
        same = {i: e['text'] for i, e in x['entries'].items()} == {i: e['text'] for i, e in y['entries'].items()}
        res['%s_entries' % key] = [len(x['entries']), len(y['entries']), same]
        if not same:
            res['problems'].append('%s driver entries changed' % key)
    man = {ln.split('  ', 1)[1]: ln.split('  ', 1)[0] for ln in open(os.path.join(ROOT, MAN)).read().splitlines()
           if '  ' in ln}
    s, e = v1['sec']
    owners = {}
    for path in R7B:
        h = man[path]
        line = next((i + 1 for i in range(s, e) if h in v1['lines'][i]), None)
        owners[path] = [line, PD.citing_amendment(v1, line) if line else None, h in text]
    res['r7b_first_cited'] = owners
    if any(o[1] != 'A11' or o[2] for o in owners.values()):
        res['problems'].append('R7B files first cited by %s' % owners)
    res['a11_before_anchor_after_a12'] = (v1['amendments']['A12'][0] < v1['amendments']['A11'][0]
                                          < v1['anchor'] + 1)
    res['anchor_line_after'] = v1['anchor'] + 1
    # Sec. 9.12 after the in-place text
    i = cur.index('**Verification.** Before any number')
    res['sec912_verification_after'] = cur[i:cur.index('\n\n', i)]
    # a later gate entry of the phase driver (the first gate not entered yet)
    key = next((x for x in PD.LABELS if x not in v1['entries']), None)
    if key is not None:
        gate, label = PD.LABELS[key]
        gl = ('* **%s %s** (2026-11-16 03:00, Beijing time). Simulated gate entry of the round-2 review; manifest and '
              'seal: `MANIFEST.sha256`, 221 files, sha256 `%s`, sealed with this entry.' % (gate, label, 'd' * 64))
        cur2 = PD.insert_entry(None, cur, [gl])
        v2, pv2 = PD.phase_view(None, cur2), P1.protocol_view(None, cur2)
        res['later_gate'] = [gate, label, key in v2['entries'], len(v2['amendments'].get('A11', [])),
                             {i: x['text'] for i, x in pv2['entries'].items()} ==
                             {i: x['text'] for i, x in pv1['entries'].items()}]
        if not (key in v2['entries'] and len(v2['amendments'].get('A11', [])) == 1 and res['later_gate'][4]):
            res['problems'].append('later gate entry: %s' % res['later_gate'])
        with open(os.path.join(a.out, 'PROTOCOL.after_gate.md.txt'), 'w', encoding='utf-8') as f:
            f.write(cur2)
    try:
        res['analysis_registration_wait'] = PD.analysis_registration(None, v1)
    except Exception as exc:  # noqa: BLE001
        res['analysis_registration_wait'] = '%s: %s' % (type(exc).__name__, exc)
    with open(os.path.join(a.out, 'PROTOCOL.after_A11.md.txt'), 'w', encoding='utf-8') as f:
        f.write(cur)
    with open(os.path.join(a.out, 'A11_filled.md.txt'), 'w', encoding='utf-8') as f:
        f.write(entry)
    res['composed_sha256'] = hashlib.sha256(cur.encode()).hexdigest()
    json.dump(res, sys.stdout, indent=1, default=str)
    print()
    return 1 if res['problems'] else 0


if __name__ == '__main__':
    sys.exit(main())
