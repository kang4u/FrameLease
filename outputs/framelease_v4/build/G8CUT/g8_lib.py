#!/usr/bin/env python3
"""Checks and records of the manual analysis freeze (gate G8) under the cut of Amendment A12 (RUNBOOK.md in this
directory). Run from the project root (or a scratch tree, which is then the root: every path is relative to the working
directory); CPU only; job health only before the freeze (PROTOCOL Sec. 9.11: no outcome, metric or route of a
test-route run is read or printed by check / swap).

  P="taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B"
  $P outputs/framelease_v4/build/G8CUT/g8_lib.py check [--expect reduced|registered]
  $P outputs/framelease_v4/build/G8CUT/g8_lib.py swap
  $P outputs/framelease_v4/build/G8CUT/g8_lib.py required --out FILE
  $P outputs/framelease_v4/build/G8CUT/g8_lib.py record --dir outputs/framelease_v4/analysis/final_<stamp>
  $P outputs/framelease_v4/build/G8CUT/g8_lib.py entry --dir ... [--name A13]
  $P outputs/framelease_v4/build/G8CUT/g8_lib.py simulate --dir ... [--name A13]
  $P outputs/framelease_v4/build/G8CUT/g8_lib.py post --dir ... [--name A13]
  $P outputs/framelease_v4/build/G8CUT/g8_lib.py result-entry --kind verify|extra --name A14 --verify-dir DIR
                                                        [--class-report FILE]

check     completion check: queue_p4/jobs.d holds the six job files, each at its A12 reduced sha256 (--expect reduced,
          before the swap) or at its registered G6 sha256 (--expect registered, after it); every job line of jobs.d has a
          final runner record; no runner holds the queue (runner.lock pid, flock) and the last runner record is an exit;
          the 505 cut job lines (registered minus reduced) have no runner record; the phase driver is stopped
          (phase_driver/STOP, no live driver process); no ALERT.txt / protocol_txn.json of either driver and no
          framelease_v4/.PROTOCOL.md.entrytmp; Sec. 13.2 holds Amendments A10, A11 and A12 once each, cites the cut plan,
          the analysis code (analyze_v4.py and the five aggregator modules) and verify_table1_extra.py at their sha256 on
          disk; no outputs/framelease_v4/analysis/final_* directory yet (or report the one there). Exit 0 ready, 3 not
          final yet (wait), 2 a problem.
swap      precondition: check --expect reduced passes. Writes queue_p4/STOP (no runner may start a cut job: the
          registered files hold the 505 never-started lines) and replaces each reduced job file in jobs.d by its
          registered copy (cut_20261115T231415/jobs_registered/, at the G6 sha256), each through a temporary file and a
          rename; then the six files must be at their G6 sha256. Idempotent (an already registered file is left).
required  writes {queue copy: G6 sha256} of the six registered job files (phase_driver/P4_QUEUED.json, every sha256
          cited by the G6 entry): the --required-job-files of aggregate_v4.py / analyze_v4.py.
record    validates the analysis-freeze record and its aggregation (before the entry): interim_guard.record_problems
          with the required job files; trigger 'cut', cut_amendment 'A12'; the 127 kept jobs final (ok, agent_crashed,
          sim_failure) and the 505 cut jobs 'cut', each in its own registered job file; the analysis code = the
          registered files on disk, each sha256 cited in PROTOCOL.md; SHA256SUMS of the directory holds; the
          aggregation ran without --arm-summary and --analysis-freeze (aggregate.json). Prints the counts.
entry     writes entries/<name>_entry.md (the dated Sec. 13.2 entry, placeholders for the applier) and
          entries/<name>_spec.json (apply_entry_stream.py) and checks the lines (120 columns, no driver form).
simulate  composes PROTOCOL.md + the entry (filled with the current values) in a scratch copy under /tmp/G8CUT_sim/,
          reads it with p1_driver.protocol_view and phase_driver.phase_view, seals the copy and calls
          interim_guard.load_freeze on it (registered False): the record is accepted once the entry is sealed.
post      after the application: interim_guard.load_freeze with the registered PROTOCOL.md and seal (registered True,
          required job files); both parsers; the title read once; the first Sec. 13.2 line that cites the record
          belongs to the entry.
result-entry  the entry template and spec of a verification result (APPLY_PLAN2 step 8): --kind verify
          (verify_independent.py, Amendment A10 use rule 4) or extra (verify_table1_extra.py and the class report,
          Amendment A11 use rules 1-3).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import textwrap
import time
from pathlib import Path

ROOT = Path.cwd().resolve()
if not (ROOT / 'framelease_v4/PROTOCOL.md').is_file():
    sys.exit('run from the project root (framelease_v4/PROTOCOL.md not found)')
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

V4 = 'outputs/framelease_v4'
Q4 = f'{V4}/queue_p4'
CUT_DIR = f'{V4}/cut_20261115T231415'
CUT_PLAN = f'{CUT_DIR}/CUT_PLAN.json'
CUT_PLAN_SHA = '9285400b7af3b8f62f98f62d2cdcea31e68a2ab3a5c3b5e35692b99671af78e3'
P4_QUEUED = f'{V4}/phase_driver/P4_QUEUED.json'
TEST_FREEZE = f'{V4}/test_freeze/test_freeze.json'
ANALYSIS_DIR = f'{V4}/analysis'
RECORD = 'analysis_freeze.json'
REQUIRED = 'required_job_files.json'
ANALYSIS_CODE = ('aggregate_v4.py', 'extra_metrics.py', 'commit_audit.py', 'manipulation.py', 'interim_guard.py')
ANALYZE = 'framelease_v4/analysis/analyze_v4.py'
R7B = 'framelease_v4/analysis/verify_table1_extra.py'
F1_REPORT = f'{V4}/build/AMEND2/a10r7b/f1/f1_class_report.py'
KEPT, CUT_N, TOTAL = 127, 505, 632
FINAL = ('ok', 'agent_crashed', 'sim_failure')
HERE = f'{V4}/build/G8CUT'
WIDTH = 120
ANCHOR = 'Each amendment gets the date and time'
LINE_START = re.compile(r'^(>|(\d+[.)]|[-*+#|=])(\s|$))')


def sha(p):
    h = hashlib.sha256()
    with open(ROOT / p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def read_json(p):
    return json.loads((ROOT / p).read_text(encoding='utf-8'))


def job_ids(path):
    return [json.loads(ln)['id'] for ln in (ROOT / path).read_text(encoding='utf-8').splitlines() if ln.strip()]


def drivers():
    from framelease_v4.protocol import p1_driver as P1
    from framelease_v4.protocol import phase_driver as PD
    return P1, PD


class QCfg:
    def __init__(self, q):
        self.queue = ROOT / q
        self.queue_arg = q
        self.jobs_d = self.queue / 'jobs.d'


def plan():
    if sha(CUT_PLAN) != CUT_PLAN_SHA:
        raise SystemExit(f'{CUT_PLAN} is not at the sha256 Amendment A12 cites')
    doc = read_json(CUT_PLAN)
    queued = {Path(c['copy']).name: c for c in read_json(P4_QUEUED)['copies']}
    out = {}
    for stem, b in doc['blocks'].items():
        name = f'{stem}.jsonl'
        c = queued[name]
        if c['sha256'] != b['sha256_registered']:
            raise SystemExit(f'{name}: P4_QUEUED.json sha256 {c["sha256"]} != CUT_PLAN {b["sha256_registered"]}')
        out[name] = {'copy': c['copy'], 'registered': f'{CUT_DIR}/jobs_registered/{name}',
                     'reduced': f'{CUT_DIR}/jobs_reduced/{name}', 'sha_registered': b['sha256_registered'],
                     'sha_reduced': b['sha256_reduced'], 'kept': b['jobs_kept'], 'n_registered': b['jobs_registered'],
                     'routes': b['routes'], 'tier': c['tier'], 'test_jobs': c['job_file']}
    return out


def sec13(text):
    i = text.find('\n### 13.2 Amendments')
    j = text.find('\n## 14.', i)
    return text[i:j if j > 0 else len(text)]


def amend_lines(text, ident):
    return [ln for ln in text.splitlines() if re.match(r'^\*\*Amendment ' + re.escape(ident) + r'[,:.]? ', ln)]


def runner_status(q):
    P1, _ = drivers()
    cfg = QCfg(q)
    qs = P1.queue_status(cfg)
    return qs, P1.runner_lock_held(cfg)


def pid_alive_with(pid_file, marker):
    try:
        pid = int((ROOT / pid_file).read_text().split()[0])
        cmd = Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
        return marker in cmd, pid
    except (OSError, ValueError, IndexError):
        return False, None


# ------------------------------------------------------------------------------------------------ check / swap

def check(expect):
    probs, waits, info = [], [], {}
    pl = plan()
    jd = ROOT / Q4 / 'jobs.d'
    names = sorted(p.name for p in jd.glob('*.jsonl'))
    if names != sorted(pl):
        probs.append(f'{Q4}/jobs.d holds {names}, not the six job files {sorted(pl)}')
    state = set()
    for n, b in pl.items():
        if not (jd / n).is_file():
            continue
        h = sha(f'{Q4}/jobs.d/{n}')
        state.add('reduced' if h == b['sha_reduced'] else 'registered' if h == b['sha_registered'] else 'other')
        if sha(b['registered']) != b['sha_registered'] or sha(b['reduced']) != b['sha_reduced']:
            probs.append(f'{n}: a copy in {CUT_DIR} is not at its A12 sha256')
        if sha(b['test_jobs']) != b['sha_registered']:
            probs.append(f'{b["test_jobs"]} is not at its G6 sha256')
    info['jobs_d'] = sorted(state)
    if state != {expect}:
        probs.append(f'jobs.d files are {sorted(state)}, expected all {expect}')
    reg_ids, red_ids = set(), set()
    for n, b in pl.items():
        r, d = job_ids(b['registered']), job_ids(b['reduced'])
        if len(r) != b['n_registered'] or len(d) != b['kept'] or not set(d) <= set(r):
            probs.append(f'{n}: {len(d)} kept / {len(r)} registered lines, not {b["kept"]} / {b["n_registered"]}')
        reg_ids |= set(r)
        red_ids |= set(d)
    cut_ids = reg_ids - red_ids
    info.update(registered_lines=len(reg_ids), kept_lines=len(red_ids), cut_lines=len(cut_ids))
    if (len(reg_ids), len(red_ids), len(cut_ids)) != (TOTAL, KEPT, CUT_N):
        probs.append(f'{len(reg_ids)} registered, {len(red_ids)} kept, {len(cut_ids)} cut lines; A12: 632 / 127 / 505')
    qs, held = runner_status(Q4)
    finals = {i for i in qs['ids'] if i not in qs['pending']}
    kept_final = len(red_ids & finals)
    info.update(kept_final=kept_final, kept_pending=len(red_ids - finals), runner_alive=qs['runner_alive'],
                runner_lock_held=held, stop_file=qs['stop_file'],
                last_runner_exit=(qs['runner_exit'] or {}).get('utc'))
    if red_ids - finals:
        waits.append(f'{len(red_ids - finals)} kept jobs without a final runner record')
    if qs['runner_alive'] or held:
        waits.append(f'a runner holds {Q4} (pid {qs["runner_pid"]}, lock held {held})')
    elif qs['runner_exit'] is None and qs['last_runner_start'] is not None:
        waits.append('the last runner start has no later runner exit record (the runner may still run)')
    seen = set()
    for ln in (ROOT / Q4 / 'status.jsonl').read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if r.get('event') in ('start', 'end') and r.get('id') in cut_ids:
            seen.add(r['id'])
    info['cut_lines_with_runner_record'] = len(seen)
    if seen:
        probs.append(f'{len(seen)} cut job lines have runner records (A12: they never start): {sorted(seen)[:5]}')
    pd = f'{V4}/phase_driver'
    if not (ROOT / pd / 'STOP').exists():
        probs.append(f'{pd}/STOP is missing (Amendment A12 keeps the phase driver stopped)')
    alive, pid = pid_alive_with(f'{pd}/driver.pid', 'phase_driver.py')
    if alive:
        probs.append(f'the phase driver runs (pid {pid}); it stays stopped under the cut')
    for f in (f'{V4}/p1_driver/ALERT.txt', f'{V4}/p1_driver/protocol_txn.json', f'{pd}/ALERT.txt',
              f'{pd}/protocol_txn.json', 'framelease_v4/.PROTOCOL.md.entrytmp'):
        if (ROOT / f).exists():
            probs.append(f'{f} exists')
    text = (ROOT / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    s13 = sec13(text)
    for a in ('A10', 'A11', 'A12'):
        n = len(amend_lines(s13, a))
        if n != 1:
            (waits if a == 'A11' and n == 0 else probs).append(f'Amendment {a} found {n} times in Sec. 13.2')
    if CUT_PLAN_SHA not in s13:
        probs.append('Sec. 13.2 does not cite the cut plan')
    code = {f'framelease_v4/analysis/{m}': sha(f'framelease_v4/analysis/{m}') for m in ANALYSIS_CODE}
    code[ANALYZE] = sha(ANALYZE)
    unc = [p for p, h in code.items() if h not in s13]
    if unc:
        probs.append(f'analysis code not cited at its sha256 on disk: {unc}')
    if (ROOT / R7B).is_file() and sha(R7B) not in s13:
        waits.append(f'{R7B} is not cited at its sha256 (Amendment A11 not entered yet)')
    finals_dirs = sorted(p.name for p in (ROOT / ANALYSIS_DIR).glob('final_*')) if (ROOT / ANALYSIS_DIR).is_dir() \
        else []
    info['analysis_dirs'] = finals_dirs
    if finals_dirs:
        probs.append(f'{ANALYSIS_DIR} already holds {finals_dirs}: one analysis freeze only (check it first)')
    info['problems'], info['waits'] = probs, waits
    print(json.dumps(info, indent=1, sort_keys=True))
    if probs:
        print('CHECK: PROBLEM')
        return 2
    if waits:
        print('CHECK: NOT FINAL (wait)')
        return 3
    print(f'CHECK: READY ({expect})')
    return 0


def swap():
    rc = check('reduced')
    if rc == 2:
        rc2 = check('registered')
        if rc2 == 0:
            print('SWAP: the registered copies are in jobs.d already; nothing to do')
            return 0
        return 2
    if rc != 0:
        print('SWAP: refused (the queue is not final)')
        return rc
    stop = ROOT / Q4 / 'STOP'
    tmp = ROOT / Q4 / '.STOP.g8tmp'
    tmp.write_text(f'{time.strftime("%Y-%m-%dT%H:%M:%S%z")} G8 under Amendment A12: the registered job files are back '
                   'in jobs.d for the analysis-freeze record; their 505 cut lines never start. Do not remove.\n')
    os.replace(tmp, stop)
    for n, b in plan().items():
        dst = ROOT / Q4 / 'jobs.d' / n
        if sha(f'{Q4}/jobs.d/{n}') == b['sha_registered']:
            continue
        t = dst.with_name(f'.{n}.g8tmp')
        shutil.copyfile(ROOT / b['registered'], t)
        os.replace(t, dst)
    bad = [n for n, b in plan().items() if sha(f'{Q4}/jobs.d/{n}') != b['sha_registered']]
    if bad:
        print(f'SWAP: FAILED, not at the G6 sha256: {bad}')
        return 2
    print(f'SWAP: done; {Q4}/STOP written; the six registered job files are in jobs.d at their G6 sha256')
    return check('registered')


def required_map():
    _, PD = drivers()
    view = PD.phase_view(None, (ROOT / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8'))
    g6 = view['entries'].get('test_freeze')
    out = {}
    for n, b in sorted(plan().items()):
        if g6 is None or b['sha_registered'] not in g6['shas']:
            raise SystemExit(f'{n}: sha256 {b["sha_registered"]} is not cited by the G6 entry')
        out[b['copy']] = b['sha_registered']
    return out


# ------------------------------------------------------------------------------------------------ the record

def record_info(d):
    from framelease_v4.analysis import interim_guard as G
    d = Path(d)
    rec, req = d / RECORD, d / REQUIRED
    doc = json.loads((ROOT / rec).read_text(encoding='utf-8'))
    want = required_map()
    if json.loads((ROOT / req).read_text(encoding='utf-8')) != want:
        raise SystemExit(f'{req} differs from the registered job files of the test freeze')
    probs = G.record_problems(doc, required_job_files=want)
    if doc.get('trigger') != 'cut' or doc.get('cut_amendment') != 'A12':
        probs.append(f'trigger {doc.get("trigger")!r}, cut amendment {doc.get("cut_amendment")!r}')
    if doc.get('job_files') != want:
        probs.append(f'job files {doc.get("job_files")} != {want}')
    pl = plan()
    by_copy = {b['copy']: (set(job_ids(b['reduced'])), set(job_ids(b['registered']))) for b in pl.values()}
    jobs = doc.get('jobs') or {}
    counts, per_file = {}, {}
    for jid, v in jobs.items():
        o = v.get('outcome')
        counts[o] = counts.get(o, 0) + 1
        kept, regd = by_copy.get(v.get('job_file'), (set(), set()))
        pf = per_file.setdefault(v.get('job_file'), {})
        pf[o] = pf.get(o, 0) + 1
        if jid not in regd:
            probs.append(f'{jid}: not a line of {v.get("job_file")}')
        elif jid in kept and o not in FINAL:
            probs.append(f'kept job {jid} has outcome {o!r}')
        elif jid not in kept and o != 'cut':
            probs.append(f'cut job {jid} has outcome {o!r}')
    if len(jobs) != TOTAL or counts.get('cut') != CUT_N or sum(counts.get(o, 0) for o in FINAL) != KEPT:
        probs.append(f'{len(jobs)} jobs, outcomes {counts}: A12 has 632 jobs, 127 final and 505 cut')
    text = (ROOT / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    code = doc.get('analysis_code') or {}
    unc = [p for p, h in code.items() if h not in text or sha(p) != h]
    if unc:
        probs.append(f'analysis code of the record not registered or changed on disk: {unc}')
    _, PD = drivers()
    sums = d / 'SHA256SUMS'
    probs += PD.sha256sums_problems(type('C', (), {'rel': staticmethod(lambda p: str(p))})(), ROOT / d, ROOT / sums)
    agg = json.loads((ROOT / d / 'aggregate.json').read_text(encoding='utf-8'))
    g = agg.get('interim_guard') or {}
    if g.get('status') != 'pre_freeze' or g.get('summary') is not None or (ROOT / d / 'arm_summary.csv').exists():
        probs.append(f'the aggregation is not the guarded one (guard {g.get("status")}, summary {g.get("summary")})')
    if (agg.get('arguments') or {}).get('queues') != [Q4]:
        probs.append(f'aggregation queues {(agg.get("arguments") or {}).get("queues")} != [{Q4}]')
    return {'record': str(rec), 'sha256': sha(rec), 'required': str(req), 'required_sha256': sha(req),
            'sha256sums': str(sums), 'sha256sums_sha256': sha(sums), 'frozen': doc.get('frozen'),
            'trigger': doc.get('trigger'), 'cut_amendment': doc.get('cut_amendment'), 'outcomes': counts,
            'per_file': per_file, 'code': code, 'route_split_sha256': doc.get('route_split_sha256'),
            'guard': {k: g.get(k) for k in ('status', 'guarded_rows', 'test_route_rows', 'health_only_rows')},
            'runner_exit': (runner_status(Q4)[0]['runner_exit'] or {}).get('utc'), 'problems': probs}


# ------------------------------------------------------------------------------------------------ entries

def wrap_entry(title, bullets):
    """Title paragraph and '* ' bullets at WIDTH columns; no continuation line starts a list, a heading or a quote."""
    out = []
    for width in range(WIDTH, 96, -1):
        lines = textwrap.wrap(title, width=width, break_long_words=False, break_on_hyphens=False)
        if all(not LINE_START.match(x) for x in lines[1:]):
            break
    out += lines
    for b in bullets:
        for width in range(WIDTH, 96, -1):
            lines = textwrap.wrap(b, width=width, initial_indent='* ', subsequent_indent='  ', break_long_words=False,
                                  break_on_hyphens=False)
            if all(not LINE_START.match(x[2:]) for x in lines[1:]):
                break
        out += lines
    return '\n'.join(out) + '\n'


def next_name(text):
    ids = [int(m.group(1)) for m in re.finditer(r'^\*\*Amendment A(\d+)[a-z]?[,:.]? ', sec13(text), re.M)]
    return f'A{max(ids) + 1}'


def placeholders(text, values):
    """Replace each filled value by its placeholder (the sha256 of a file the applier hashes at application)."""
    for value, ph in values:
        text = text.replace(value, ph)
    return text


def freeze_entry(d, name):
    info = record_info(d)
    if info['problems']:
        raise SystemExit(f'the record does not validate: {info["problems"]}')
    pl = plan()
    stamp = time.strftime('%Y-%m-%d %H:%M')
    rec, req, sums = info['record'], info['required'], info['sha256sums']
    o = info['outcomes']
    files = '; '.join(f'`{b["copy"]}` (tier {b["tier"]}, {b["kept"]} of {b["n_registered"]} lines kept, sha256 '
                      f'`{b["sha_registered"]}`)' for n, b in sorted(pl.items()))
    mods = ', '.join(f'`{Path(p).name}` (sha256 `{h}`)' for p, h in sorted(info['code'].items()))
    status = ', '.join(f'{k} {o.get(k, 0)}' for k in FINAL + ('cut',))
    kept_status = ', '.join(f'{k} {o.get(k, 0)}' for k in FINAL)
    title = (f'**Amendment {name}, {stamp} (Beijing time): the analysis freeze (Sec. 9.12) under the cut of Amendment '
             'A12, carried out by the coordinating session with the registered tools in place of gate G8 of the phase '
             'driver; no run, job line, criterion or analysis rule changes.**')
    bullets = [
        f'Freeze. Every job that Amendment A12 keeps in tiers 3-6 was final and the runner of `{Q4}` had exited (last '
        f'runner exit {info["runner_exit"]}). `aggregate_v4.py --queue {Q4} --specs {V4}/test_jobs/FULL --rl-freeze '
        f'{V4}/rl_freeze/rl_freeze.json --tuning-freeze {V4}/tuning/selection.json --write-freeze-record {rec} '
        f'--cut-amendment A12` wrote `{rec}` (sha256 `{info["sha256"]}`; trigger {info["trigger"]}, cut amendment '
        f'{info["cut_amendment"]}, frozen {info["frozen"]}).',
        f'Job status: {TOTAL} jobs of the 6 job files of the test freeze (entry "G6 Test freeze", record '
        f'`{TEST_FREEZE}` sha256 `{sha(TEST_FREEZE)}`): {files}; outcomes {status}. The {KEPT} jobs kept by '
        f'Amendment A12 are final ({kept_status}); the {CUT_N} cut jobs have no runner record and no run directory '
        'and carry the outcome cut.',
        f'Job files. The runner ran the kept jobs from the reduced job files of Amendment A12 (`{CUT_DIR}/jobs_reduced/`'
        f', byte-identical subsets). Once every kept job was final and the runner had exited, `{Q4}/STOP` was written '
        f'and the registered copies (`{CUT_DIR}/jobs_registered/`) were put back into `{Q4}/jobs.d`, so that the record '
        'covers the registered job files of the test freeze at their sha256 of the G6 entry; `test_freeze.py '
        '--verify` passed on them. The STOP file stays: no runner starts a cut job.',
        f'Analysis code frozen by the record: {mods}; the analysis script `{ANALYZE}` (sha256 `{sha(ANALYZE)}`) is '
        f'registered in Sec. 13.2 by Amendment A10 and `{R7B}` (sha256 `{sha(R7B)}`) by Amendment A11. Route split '
        f'sha256 `{info["route_split_sha256"]}`.',
        'Interim looks (Sec. 9.11). The aggregation that made the record ran without --arm-summary and without '
        '--analysis-freeze: every test-route row stayed health-only and no cross-arm summary was made. Its outputs and '
        f'its guard log are in `{d}` (`SHA256SUMS` sha256 `{info["sha256sums_sha256"]}`); `{req}` (sha256 '
        f'`{info["required_sha256"]}`) lists the six queue copies at their G6 sha256 (the --required-job-files of the '
        'analysis).',
        'Validity. The record is valid from this entry on (its sha256 in Sec. 13 of the sealed PROTOCOL.md, '
        f'`interim_guard.load_freeze`). The confirmatory analysis (Amendments A3 and A10) writes its outputs into '
        f'directories inside `{d}`, each with its sha256 manifest. The phase driver stays stopped '
        f'(`{V4}/phase_driver/STOP`, Amendment A12): this entry takes the place of its G8 entry.',
        'Manifest and seal after this entry: `MANIFEST.sha256`, {{manifest:files}} files, sha256 '
        '`{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.']
    filled = wrap_entry(title, bullets)
    tmpl = placeholders(filled, [(f'{name}, {stamp} (Beijing', f'{name}, {{{{datetime}}}} (Beijing'),
                                 (info['sha256'], f'{{{{sha256:{rec}}}}}'),
                                 (info['sha256sums_sha256'], f'{{{{sha256:{sums}}}}}'),
                                 (info['required_sha256'], f'{{{{sha256:{req}}}}}')])
    must = {rec: info['sha256'], sums: info['sha256sums_sha256'], req: info['required_sha256'], CUT_PLAN: CUT_PLAN_SHA,
            TEST_FREEZE: sha(TEST_FREEZE), ANALYZE: sha(ANALYZE), R7B: sha(R7B),
            **{b['copy']: b['sha_registered'] for b in pl.values()}, **info['code']}
    return tmpl, must, info


def result_entry(kind, name, vdir, class_report=None):
    stamp = time.strftime('%Y-%m-%d %H:%M')
    vdir = Path(vdir)
    if kind == 'verify':
        vj = vdir / 'verification.json'
        doc = json.loads((ROOT / vj).read_text(encoding='utf-8'))
        verdict, status = doc.get('verdict'), doc.get('status')
        title = (f'**Amendment {name}, {stamp} (Beijing time): result of the independent verification of H1 and of '
                 'the Table I columns DS, SR, RC, collisions/km and infractions/km (Sec. 9.12; Amendment A10, use rule '
                 '4); no run, job line, criterion or analysis rule changes.**')
        n_diff = len((doc.get('comparisons') or {}).get('differences') or []) if isinstance(
            (doc.get('comparisons') or {}).get('differences'), list) else (doc.get('comparisons') or {}).get(
            'differences')
        bullets = [
            f'Run. An independent session ran `framelease_v4/analysis/verify_independent.py` (sha256 '
            f'`{sha("framelease_v4/analysis/verify_independent.py")}`) after the analysis freeze, with the record, the '
            f'released aggregation, the analysis and `--queue {Q4}`, into `{vdir}`.',
            f'Result. `{vj}` (sha256 `{sha(vj)}`): status {status}, verdict {verdict}, differences {n_diff}; '
            f'`SHA256SUMS` sha256 `{sha(vdir / "SHA256SUMS")}`. '
            + ('AGREE releases H1 and its findings and the verified Table I columns (use rule 4).'
               if verdict == 'AGREE' else 'Every difference of `differences.csv` is resolved and its cause entered in '
               'Sec. 13 before any of these numbers enters the paper (use rule 4).'),
            'Manifest and seal after this entry: `MANIFEST.sha256`, {{manifest:files}} files, sha256 '
            '`{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.']
        files = [vj, vdir / 'SHA256SUMS']
    else:
        tj = vdir / 'table1_extra.json'
        doc = json.loads((ROOT / tj).read_text(encoding='utf-8'))
        rep = json.loads((ROOT / class_report).read_text(encoding='utf-8'))
        cls = rep.get('differences_by_class') or {}
        sizes = ', '.join(f'{c} {n}' for c, n in cls.items())
        release = rep.get('release')
        use = {'AGREE': 'AGREE releases these columns (use rule 2).',
               'pre-specified classes only': 'Every difference lies in a pre-specified class: these columns are '
               'released with the registered values, and the paper states each class, its cause and its size (use '
               'rule 2).'}.get(release, 'A difference without a pre-specified class is a verification failure: each '
                               'such difference is resolved and its cause entered in Sec. 13 before any of these '
                               'numbers enters the paper (use rule 2; Amendment A10, use rule 4).')
        title = (f'**Amendment {name}, {stamp} (Beijing time): result of the independent recomputation of the Table I '
                 'columns GPU usage, DMR, action age, fallback ratio, EIR and P_both and of the closed-loop R_cond '
                 '(Sec. 9.12; Amendment A11, use rules 1-3); no run, job line, criterion or analysis rule changes.**')
        bullets = [
            f'Run. An independent session ran `{R7B}` (sha256 `{sha(R7B)}`) after the analysis freeze, with the '
            f'record, `--queue {Q4}`, the released aggregation and the analysis, into `{vdir}`, and the class report '
            f'`{F1_REPORT}` (sha256 `{sha(F1_REPORT)}`) on that directory.',
            f'Result. `{tj}` (sha256 `{sha(tj)}`): status {doc.get("status")}, verdict {doc.get("verdict")}; '
            f'`SHA256SUMS` sha256 `{sha(vdir / "SHA256SUMS")}`; class report `{class_report}` (sha256 '
            f'`{sha(class_report)}`): outcome {rep.get("outcome")}, release {rep.get("release")}; differences per '
            f'class: {sizes or "none"}.',
            f'Use. {use}',
            'Manifest and seal after this entry: `MANIFEST.sha256`, {{manifest:files}} files, sha256 '
            '`{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.']
        files = [tj, vdir / 'SHA256SUMS', Path(class_report)]
    filled = wrap_entry(title, bullets)
    subs = [(f'{name}, {stamp} (Beijing', f'{name}, {{{{datetime}}}} (Beijing')]
    subs += [(sha(f), f'{{{{sha256:{f}}}}}') for f in files]
    return placeholders(filled, subs), {str(f): sha(f) for f in files}


def line_problems(text):
    _, PD = drivers()
    P1, _ = drivers()
    lines = text.splitlines()
    bad = [ln for ln in lines[1:] if ln.startswith(('## ', ANCHOR)) or P1.ENTRY_RE.match(ln) or PD.ENTRY_RE.match(ln)
           or PD.AMEND_RE.match(ln) or ln.strip() in (P1.HEADING, PD.HEADING, '### 13.2 Amendments')]
    bad += [ln for ln in lines if len(re.sub(r'\{\{sha256:[^}]+\}\}', 'x' * 64, ln).replace(
        '{{datetime}}', 'YYYY-MM-DD HH:MM').replace('{{manifest:files}}', '999')) > WIDTH]
    return bad + ([ANCHOR] if ANCHOR in text else [])


def write_spec(name, tmpl, must):
    out = ROOT / HERE / 'entries'
    out.mkdir(parents=True, exist_ok=True)
    t = out / f'{name}_entry.md'
    t.write_text(tmpl, encoding='utf-8')
    spec = {'name': name, 'template': str(t.relative_to(ROOT)), 'tests': [], 'inplace': [], 'must_equal':
            {str(k): v for k, v in sorted(must.items())}, 'max_new_registered': 0}
    s = out / f'{name}_spec.json'
    s.write_text(json.dumps(spec, indent=1) + '\n', encoding='utf-8')
    bad = line_problems(tmpl)
    print(f'{t.relative_to(ROOT)} ({len(tmpl.splitlines())} lines), {s.relative_to(ROOT)}; line problems: {bad}')
    return 2 if bad else 0


def compose(text, entry):
    k = text.index(ANCHOR)
    return text[:k].rstrip('\n') + '\n\n' + entry + '\n' + text[k:]


def fill_preview(tmpl):
    def sub(m):
        key = m.group(1)
        if key == 'datetime':
            return time.strftime('%Y-%m-%d %H:%M')
        if key == 'manifest:files':
            return str(len((ROOT / V4 / 'registration/MANIFEST.sha256').read_text().splitlines()))
        if key.startswith('sha256:'):
            return sha(key.split(':', 1)[1])
        raise KeyError(key)
    return re.sub(r'\{\{([^}]+)\}\}', sub, tmpl)


def parse_checks(old, new, name):
    P1, PD = drivers()
    probs = []
    try:
        pv0, v0 = P1.protocol_view(None, old), PD.phase_view(None, old)
        pv1, v1 = P1.protocol_view(None, new), PD.phase_view(None, new)
    except Exception as e:  # noqa: BLE001
        return [f'{type(e).__name__}: {e}'], None
    if len(v1['amendments'].get(name, [])) != 1:
        probs.append(f'{name} read at lines {v1["amendments"].get(name)}')
    if {a: len(x) for a, x in v1['amendments'].items() if a != name} != {a: len(x) for a, x in v0['amendments'].items()}:
        probs.append('other amendment titles changed')
    for key, a, b in (('P1', pv0, pv1), ('phase', v0, v1)):
        if {k: e['text'] for k, e in a['entries'].items()} != {k: e['text'] for k, e in b['entries'].items()}:
            probs.append(f'the {key} driver entries changed')
    return probs, v1


def simulate(d, name):
    from framelease_v4.analysis import interim_guard as G
    spec = json.loads((ROOT / HERE / 'entries' / f'{name}_spec.json').read_text())
    tmpl = (ROOT / spec['template']).read_text(encoding='utf-8')
    text = (ROOT / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    entry = fill_preview(tmpl)
    new = compose(text, entry)
    probs, v1 = parse_checks(text, new, name)
    rec = Path(d) / RECORD
    rsha = sha(rec)
    sim = Path('/tmp/G8CUT_sim') / f'{name}_{os.getpid()}'
    sim.mkdir(parents=True)
    (sim / 'PROTOCOL.md').write_text(new, encoding='utf-8')
    (sim / 'SEAL.sha256').write_text(f'{hashlib.sha256(new.encode()).hexdigest()}  {sim / "PROTOCOL.md"}\n')
    if v1 is not None:
        s, e = v1['sec']
        line = next((i + 1 for i in range(s, e) if rsha in v1['lines'][i]), None)
        _, PD = drivers()
        owner = PD.citing_amendment(v1, line) if line else None
        if owner != name:
            probs.append(f'the record sha256 is first cited by {owner}, not {name}')
    try:
        fz = G.load_freeze(ROOT / rec, protocol=sim / 'PROTOCOL.md', seal=sim / 'SEAL.sha256',
                           required_job_files=json.loads((ROOT / d / REQUIRED).read_text()))
        got = {k: fz[k] for k in ('sha256', 'trigger', 'cut_amendment', 'registered')}
    except G.GuardRefused as e:
        probs.append(f'load_freeze refused: {e}')
        got = None
    try:
        G.load_freeze(ROOT / rec, required_job_files=json.loads((ROOT / d / REQUIRED).read_text()))
        probs.append('load_freeze accepts the record BEFORE the entry')
    except G.GuardRefused:
        pass
    shutil.rmtree(sim)
    print(json.dumps({'composed_sha256': hashlib.sha256(new.encode()).hexdigest(), 'load_freeze_on_copy': got,
                      'problems': probs}, indent=1))
    print('SIMULATE: OK' if not probs else 'SIMULATE: PROBLEM')
    return 0 if not probs else 2


def post(d, name):
    from framelease_v4.analysis import interim_guard as G
    text = (ROOT / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    P1, PD = drivers()
    probs = []
    try:
        P1.protocol_view(None, text)
        v = PD.phase_view(None, text)
    except Exception as e:  # noqa: BLE001
        print(f'POST: PROBLEM {type(e).__name__}: {e}')
        return 2
    if len(v['amendments'].get(name, [])) != 1:
        probs.append(f'{name} read at lines {v["amendments"].get(name)}')
    rec = Path(d) / RECORD
    rsha = sha(rec)
    s, e = v['sec']
    line = next((i + 1 for i in range(s, e) if rsha in v['lines'][i]), None)
    owner = PD.citing_amendment(v, line) if line else None
    if owner != name:
        probs.append(f'the record sha256 is first cited by {owner}, not {name}')
    fz = None
    try:
        fz = G.load_freeze(ROOT / rec, required_job_files=json.loads((ROOT / d / REQUIRED).read_text()))
        if not fz['registered']:
            probs.append('load_freeze: not the registered PROTOCOL.md')
    except G.GuardRefused as e:
        probs.append(f'load_freeze refused: {e}')
    print(json.dumps({'record': str(rec), 'sha256': rsha, 'cited_line': line, 'owner': owner,
                      'load_freeze': None if fz is None else {k: fz[k] for k in ('trigger', 'cut_amendment',
                                                                                 'registered', 'protocol_sha256')},
                      'problems': probs}, indent=1))
    print('POST: OK' if not probs else 'POST: PROBLEM')
    return 0 if not probs else 2


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('cmd', choices=('check', 'swap', 'required', 'record', 'entry', 'simulate', 'post',
                                    'result-entry', 'next-name'))
    ap.add_argument('--expect', choices=('reduced', 'registered'), default='reduced')
    ap.add_argument('--dir')
    ap.add_argument('--out')
    ap.add_argument('--name')
    ap.add_argument('--kind', choices=('verify', 'extra'))
    ap.add_argument('--verify-dir')
    ap.add_argument('--class-report')
    a = ap.parse_args()
    text = (ROOT / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')
    if a.cmd == 'check':
        return check(a.expect)
    if a.cmd == 'swap':
        return swap()
    if a.cmd == 'next-name':
        print(next_name(text))
        return 0
    if a.cmd == 'required':
        out = ROOT / a.out
        if out.exists():
            print(f'{a.out} exists')
            return 1
        tmp = out.with_name(f'.{out.name}.tmp')
        tmp.write_text(json.dumps(required_map(), indent=1, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(tmp, out)
        print(f'{a.out}: sha256 {sha(a.out)}')
        return 0
    if a.cmd == 'record':
        info = record_info(a.dir)
        print(json.dumps(info, indent=1, sort_keys=True))
        print('RECORD: OK' if not info['problems'] else 'RECORD: PROBLEM')
        return 0 if not info['problems'] else 2
    name = a.name or next_name(text)
    if a.cmd == 'entry':
        if a.name is None and name in ('A11', 'A12'):
            sys.exit(f'next free amendment name {name}: Amendment A11 is not entered yet')
        tmpl, must, _ = freeze_entry(a.dir, name)
        return write_spec(name, tmpl, must)
    if a.cmd == 'simulate':
        return simulate(a.dir, name)
    if a.cmd == 'post':
        return post(a.dir, a.name or 'A13')
    if a.cmd == 'result-entry':
        tmpl, must = result_entry(a.kind, name, a.verify_dir, a.class_report)
        return write_spec(name, tmpl, must)
    return 2


if __name__ == '__main__':
    sys.exit(main())
