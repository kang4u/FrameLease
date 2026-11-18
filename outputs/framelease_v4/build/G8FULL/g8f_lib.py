#!/usr/bin/env python3
"""Checks and records of the second analysis freeze (Amendment A17: every registered job of the test freeze final, no
cut) and of its analysis and verifications (RUNBOOK.md in this directory). Run from the project root (or a scratch
tree, which is then the root: every path is relative to the working directory); CPU only; job health only before the
freeze (PROTOCOL Sec. 9.11: check and stop read job files, runner records, run-directory names of the records and
sha256 values, never an outcome metric of a test-route run). The pure helpers of the first freeze
(outputs/framelease_v4/build/G8CUT/g8_lib.py: entry wrapping, line checks, composition, preview fill, parser checks,
runner status) are imported from that file unchanged; nothing is written under G8CUT/.

  P="taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B"
  L=outputs/framelease_v4/build/G8FULL/g8f_lib.py
  $P $L check [--expect final|stopped]       completion check (exit 0 ready, 3 wait, 2 problem)
  $P $L stop                                 queue_p4/STOP after a READY check (idempotent)
  $P $L first                                the first freeze (Amendment A13) is valid and unchanged
  $P $L new-dir                              prints the one new final_<stamp> directory (exit 1: none or several)
  $P $L required --out FILE                  {queue copy: G6 sha256} of the six registered job files
  $P $L record --dir F                       validates the second record (trigger all_final) and its aggregation
  $P $L entry --dir F [--name A18]           the dated freeze entry + spec (entries/)
  $P $L simulate --dir F [--name A18]        composes, parses, seals a scratch copy; load_freeze on it
  $P $L post --dir F --name A18              after the application: both records valid with the sealed PROTOCOL.md
  $P $L manifest --dir F                     writes F/ANALYSIS_OUTPUTS.sha256 (temporary file outside F) and checks it
  $P $L result-entry --kind verify|extra --name A19 --verify-dir DIR --dir F --freeze-name A18 [--class-report FILE]
  $P $L resolution --name A21 --verify-dir DIR --class-report FILE --dir F --extra-name A20
  $P $L manifest-check --dir F               checks F/ANALYSIS_OUTPUTS.sha256 only
  $P $L final-check --dir F                  end state: both freezes, every manifest of the new analysis
  $P $L f1-ok | next-name | entered --out FILE

check     expect 'final' (before queue_p4/STOP) or 'stopped' (after it): registration not checked here (the scripts
          run registration.py --verify); queue_p4/jobs.d holds exactly the six registered job files at their G6
          sha256 (phase_driver/P4_QUEUED.json, each cited by the G6 entry and by Amendment A17); every one of the 632
          job lines has a final runner record (wait); no runner holds the queue (runner.lock pid, flock) and the last
          runner record is an exit (wait); queue_p4/STOP absent or present as expected; the 127 jobs that the first
          record holds as final have their recorded run as the final runner record and no start record after the
          first freeze (they never ran again); the phase driver is stopped (phase_driver/STOP, no live driver process);
          no ALERT.txt / protocol_txn.json of either driver and no framelease_v4/.PROTOCOL.md.entrytmp; Sec. 13.2
          holds Amendments A10-A17 once each and cites the analysis code (the five aggregator modules,
          analyze_v4.py, verify_independent.py, verify_table1_extra.py) at its sha256 on disk and
          f1_class_report.py at the sha256 of Amendment A11; the first freeze is valid and unchanged (first); at
          most one new outputs/framelease_v4/analysis/final_<stamp>/ besides final_20261116T091445 (reported:
          resume).
first     the first record final_20261116T091445/analysis_freeze.json at the sha256 Amendments A13 and A17 cite,
          accepted by interim_guard.load_freeze (trigger cut, A12, registered); the files of the first analysis and
          its verifications that Amendments A13-A16 cite by sha256 at that sha256 (in a scratch tree with
          G8F_TREE_STANDIN=1 the result files of A14-A16 are synthetic stand-ins and are not compared); every
          SHA256SUMS below final_20261116T091445/ and verification/final_20261116T091445* holds; every line of its
          ANALYSIS_OUTPUTS.sha256 holds except the temporary-file line of Amendment A16 (correction 2).
record    the second record: interim_guard.record_problems with the required job files; trigger all_final, no cut
          amendment (phase_driver.analysis_record_problems); the 632 job lines of the six files each once with a
          final outcome of its own job file; the analysis code = the registered files on disk, each sha256 cited;
          SHA256SUMS of the directory holds; the aggregation guarded (pre_freeze, no summary, no arm_summary.csv,
          queues [queue_p4]); no collision with the first freeze (another directory, another sha256, cited in
          Sec. 13 by no entry but its own after A17, frozen after the first record); every job final in the first
          record carries the same outcome and run directory, every job cut there is final here.
resolution  the resolution entry of Amendment A16's rule (Amendment A17): written when, and only when, the class
          report reads 'verification failure' and EVERY unexplained row (the rows of class 'unexplained', formed again
          with the functions of f1_class_report.py and checked against the report's counts) is a pairing-status row of
          the closed-loop R_cond (no cause; paired_differences.csv, field 'paired' against 'status', True / False;
          metric r_cond; note "status 'realized_r_cond missing: <conditions>'"), the analysis row carries that status
          and no value, no value / difference row of that key and no contrast-level row of that contrast and metric
          differs, no runs.csv comparison of R_cond, conflict plans or misses differs for the cells of the pair, and
          every condition the status names has R_cond undefined (no conflict plan, 0/0) in the registered aggregation
          (agg_p4/runs.csv: realized_r_cond empty, realized_conflict_plans 0) and in the recomputation
          (runs_recomputed.csv: r_cond empty, conflict_plans 0). Exit 0 entry written; 0 with 'not needed' when the
          report has no unexplained row; 3 STOP with the failing rows (no entry; Amendment A10 use rule 4 applies).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd().resolve()
if not (ROOT / 'framelease_v4/PROTOCOL.md').is_file():
    sys.exit('run from the project root (framelease_v4/PROTOCOL.md not found)')
PROJECT = Path('/home/kang/Desktop/DAC')
IN_TREE = ROOT != PROJECT
STANDIN = IN_TREE and os.environ.get('G8F_TREE_STANDIN') == '1'
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G8 = _load('g8cut_lib', ROOT / 'outputs/framelease_v4/build/G8CUT/g8_lib.py')

V4 = 'outputs/framelease_v4'
Q4 = f'{V4}/queue_p4'
P4_QUEUED = f'{V4}/phase_driver/P4_QUEUED.json'
TEST_FREEZE = f'{V4}/test_freeze/test_freeze.json'
ANALYSIS_DIR = f'{V4}/analysis'
VERIFY_DIR = f'{V4}/verification'
RECORD = 'analysis_freeze.json'
REQUIRED = 'required_job_files.json'
OUTPUTS_LIST = 'ANALYSIS_OUTPUTS.sha256'
ANALYSIS_CODE = ('aggregate_v4.py', 'extra_metrics.py', 'commit_audit.py', 'manipulation.py', 'interim_guard.py')
ANALYZE = 'framelease_v4/analysis/analyze_v4.py'
VI = 'framelease_v4/analysis/verify_independent.py'
R7B = 'framelease_v4/analysis/verify_table1_extra.py'
F1_REPORT = f'{V4}/build/AMEND2/a10r7b/f1/f1_class_report.py'
F1_SHA = 'ac82d65a9f4507a779dce5632e166b79e9d4c8d83f6c2b014ca27561e29145b6'        # Amendments A11, A15
F1_ROOT_LINE = "ROOT = '/home/kang/Desktop/DAC'"
HERE = f'{V4}/build/G8FULL'
FINAL = ('ok', 'agent_crashed', 'sim_failure')
TOTAL, KEPT, NEW = 632, 127, 505
AMENDS = tuple(f'A{i}' for i in range(10, 18))
FIRST = f'{ANALYSIS_DIR}/final_20261116T091445'
VFIRST = f'{VERIFY_DIR}/final_20261116T091445'
FIRST_RECORD = f'{FIRST}/{RECORD}'
FIRST_RECORD_SHA = 'fdda348027092724f74bf10cf0b5e33ed3219ffbfe5cfe6a57ac8aa9e4bd7c05'      # A13, A17
# Files of the first freeze that Sec. 13.2 cites by sha256: the record and its job-status files (A13) ...
FIRST_HEALTH = {FIRST_RECORD: FIRST_RECORD_SHA,
                f'{FIRST}/SHA256SUMS': '335317294a5d8d20af3f62f0b4eaeae5dce8a7454475b8a99b9d291e9d254ad3',
                f'{FIRST}/{REQUIRED}': 'f58321692f998d7e33f713aee2f212f54f8e7699babc0f13310bcfdb71521d6d'}
# ... and the results of its analysis and verifications (A14, A15, A16).
FIRST_RESULTS = {
    f'{FIRST}/agg_p4/runs.csv': '0c0f5d2dec0345c0a30dbab63c272189f584018ecf6bff280dd550d5e109fd1d',
    f'{FIRST}/analysis/paired_differences.csv': '8f3e3d038c6e435875b39b7060b0ff6f928762c19c3c29621c1a7684d662a47b',
    f'{VFIRST}/verification.json': '0ffc81044fec32ed5f8d9c5a601c7820a00728cd6b26e0cd7442bb6dfb3706e7',
    f'{VFIRST}/SHA256SUMS': 'a50c7b57ae44001e5d8e0436800a9c8d45466d232907328817f6a175aa173cc8',
    f'{VFIRST}_table1_extra/table1_extra.json': '2f5c8cbbe249bfaa8cd53abca327a6c155d87a8d846a7a7516fcccb40bbb4139',
    f'{VFIRST}_table1_extra/SHA256SUMS': '9bad4595e777270f154b526f37b7a987cc37e01a4e02b54de614a9e061f4b7a4',
    f'{VFIRST}_table1_extra/differences.csv': '60aae07289fe354669cd9d7ad2254faef799bc06acb7c99a289fdcbbc631314f',
    f'{VFIRST}_table1_extra/runs_recomputed.csv': '1be46e784a1d9d52f942cc30a3021b4e323bc26f93ccaf4d95d087cf5d08468d',
    f'{VFIRST}_table1_extra_f1_class.json': 'e90fe3fff420a87032b5fc08a745ab6e198c870a0d66216ff28cfe0217929151'}
TMP_LINE = '.ANALYSIS_OUTPUTS.tmp'
R_COND, R_COND_COLUMN = 'r_cond', 'realized_r_cond'
R_COND_RUN_COLUMNS = ('realized_r_cond', 'realized_conflict_plans', 'realized_misses', 'r_cond', 'conflict_plans',
                      'misses')
CLASS_NAMES = {'F1': 'F1', 'F3': 'F3', 'in_flight': 'in-flight', 'not_ok_record': 'not-ok record',
               'undefined_metric_pairing': 'undefined-metric pairing', 'unexplained': 'unexplained'}
MANIFEST_CLAUSE = ('Manifest and seal after this entry: `MANIFEST.sha256`, {{manifest:files}} files, sha256 '
                   '`{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.')

sha, read_json, job_ids = G8.sha, G8.read_json, G8.job_ids


def protocol_text():
    return (ROOT / 'framelease_v4/PROTOCOL.md').read_text(encoding='utf-8')


def cited(h, text=None):
    return h in G8.sec13(text or protocol_text())


def amend_par(text, ident):
    """The text of the Sec. 13.2 paragraph of an amendment (its title to the next amendment title or the anchor)."""
    s = G8.sec13(text)
    m = re.search(r'^\*\*Amendment ' + re.escape(ident) + r'[,:.]? ', s, re.M)
    if not m:
        return ''
    n = re.search(r'^(\*\*Amendment A\d+[a-z]?[,:.]? |' + re.escape(G8.ANCHOR) + ')', s[m.end():], re.M)
    return s[m.start():m.end() + (n.start() if n else len(s))]


def f1_sha():
    """sha256 of f1_class_report.py; in a scratch tree its ROOT line names the tree: the sha256 of the text with the
    project's ROOT line restored."""
    p = ROOT / F1_REPORT
    if not IN_TREE:
        return sha(F1_REPORT)
    text = p.read_text(encoding='utf-8').replace(f"ROOT = '{ROOT}'", F1_ROOT_LINE)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def rel(p):
    """A path relative to the root, by text only (no file-system access: run directories named by the runner records
    are never touched); a path outside the root stays absolute."""
    s = os.path.normpath(str(p))
    r = str(ROOT) + os.sep
    return s[len(r):] if s.startswith(r) else s


# ------------------------------------------------------------------------------------------------ registered files

def copies():
    """{queue copy: {'sha256', 'tier', 'job_file'}} of the six registered job files (P4_QUEUED.json), each sha256 cited
    by the G6 entry and by Amendment A17."""
    _, PD = G8.drivers()
    text = protocol_text()
    view = PD.phase_view(None, text)
    g6 = view['entries'].get('test_freeze')
    a17 = amend_par(text, 'A17')
    out = {}
    for c in read_json(P4_QUEUED)['copies']:
        if g6 is None or c['sha256'] not in g6['shas']:
            raise SystemExit(f'{c["copy"]}: sha256 {c["sha256"]} is not cited by the G6 entry')
        if c['sha256'] not in a17:
            raise SystemExit(f'{c["copy"]}: sha256 {c["sha256"]} is not cited by Amendment A17')
        out[c['copy']] = {'sha256': c['sha256'], 'tier': c.get('tier'), 'job_file': c.get('job_file')}
    if len(out) != 6:
        raise SystemExit(f'{P4_QUEUED} names {len(out)} copies, not 6')
    return dict(sorted(out.items()))


def required_map():
    return {c: v['sha256'] for c, v in copies().items()}


def code_map():
    code = {f'framelease_v4/analysis/{m}': sha(f'framelease_v4/analysis/{m}') for m in ANALYSIS_CODE}
    return code


# ------------------------------------------------------------------------------------------------ the first freeze

def sums_problems(d, sums):
    _, PD = G8.drivers()
    return PD.sha256sums_problems(type('C', (), {'rel': staticmethod(lambda p: rel(p))})(), ROOT / d, ROOT / sums)


def first_freeze():
    """(problems, info) of the first freeze: valid, cited, unchanged (module docstring, 'first')."""
    from framelease_v4.analysis import interim_guard as G
    probs, info = [], {'standin': STANDIN}
    text = protocol_text()
    for a, files in (('A13', FIRST_HEALTH), ('A17', {FIRST_RECORD: FIRST_RECORD_SHA})):
        par = amend_par(text, a)
        for p, h in files.items():
            if h not in par:
                probs.append(f'Amendment {a} does not cite {p} at {h[:12]}')
    for p, h in FIRST_RESULTS.items():
        if not cited(h, text):
            probs.append(f'Sec. 13.2 does not cite {p} at {h[:12]}')
    for p, h in FIRST_HEALTH.items():
        got = sha(p) if (ROOT / p).is_file() else 'missing'
        if got != h:
            probs.append(f'{p} is {got[:12]}, not the cited {h[:12]}')
    compared = 0
    for p, h in FIRST_RESULTS.items():
        if STANDIN:
            if not (ROOT / p).is_file():
                probs.append(f'{p} missing (tree stand-in)')
            continue
        got = sha(p) if (ROOT / p).is_file() else 'missing'
        compared += 1
        if got != h:
            probs.append(f'{p} is {got[:12]}, not the cited {h[:12]}')
    info['cited_files_compared'] = len(FIRST_HEALTH) + compared
    sums = sorted(rel(s) for base in (FIRST, VFIRST, f'{VFIRST}_table1_extra')
                  for s in (ROOT / base).rglob('SHA256SUMS')) if (ROOT / FIRST).is_dir() else []
    for s in sums:
        probs += sums_problems(str(Path(s).parent), s)
    info['sha256sums_checked'] = sums
    lst = ROOT / FIRST / OUTPUTS_LIST
    if lst.is_file():
        bad, n = [], 0
        for ln in lst.read_text(encoding='utf-8').splitlines():
            h, _, p = ln.partition('  ')
            if p.endswith('/' + TMP_LINE):
                continue
            n += 1
            if not (ROOT / p).is_file() or sha(p) != h:
                bad.append(p)
        info['analysis_outputs_lines_checked'] = n
        if bad:
            probs.append(f'{FIRST}/{OUTPUTS_LIST}: {len(bad)} files differ: {bad[:3]}')
    else:
        probs.append(f'{FIRST}/{OUTPUTS_LIST} missing')
    try:
        fz = G.load_freeze(ROOT / FIRST_RECORD, required_job_files=read_json(f'{FIRST}/{REQUIRED}'))
        info['load_freeze'] = {k: fz[k] for k in ('trigger', 'cut_amendment', 'registered')}
        if (fz['trigger'], fz['cut_amendment'], fz['registered']) != ('cut', 'A12', True):
            probs.append(f'first record: {info["load_freeze"]}')
    except G.GuardRefused as e:
        probs.append(f'the first record is refused: {e}')
    return probs, info


def new_dirs():
    d = ROOT / ANALYSIS_DIR
    return sorted(rel(p) for p in d.glob('final_*') if p.is_dir() and rel(p) != FIRST) if d.is_dir() else []


# ------------------------------------------------------------------------------------------------ check / stop

def status_records():
    out = []
    for ln in (ROOT / Q4 / 'status.jsonl').read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


def to_utc(stamp):
    """'2026-11-16T09:15:07+0800', '...+00:00' or '...Z' (fractional seconds allowed) -> seconds since the epoch."""
    s = re.sub(r'([+-]\d\d)(\d\d)$', r'\1:\2', stamp.strip().replace('Z', '+00:00'))
    return datetime.fromisoformat(s).timestamp()


def kept_rerun_problems(first_doc, recs):
    """Jobs final in the first record: their final runner record names the recorded run, and no start record after
    the first runner start later than the first freeze (they never ran again)."""
    probs = []
    t0 = to_utc(first_doc['frozen'])
    later = next((i for i, r in enumerate(recs) if r.get('event') == 'runner_start' and r.get('utc')
                  and to_utc(r['utc']) > t0), len(recs))
    final_run, restarted = {}, set()
    for i, r in enumerate(recs):
        if r.get('event') == 'end' and r.get('final') and r.get('id'):
            final_run[r['id']] = rel(r.get('run_dir')) if r.get('run_dir') else None
        if r.get('event') == 'start' and i > later:
            restarted.add(r.get('id'))
    kept = {j: v for j, v in first_doc['jobs'].items() if v['outcome'] in FINAL}
    moved = sorted(j for j, v in kept.items() if final_run.get(j) != v['run_dir'])
    again = sorted(j for j in kept if j in restarted)
    if moved:
        probs.append(f'{len(moved)} jobs of the first freeze have another final run than recorded: {moved[:5]}')
    if again:
        probs.append(f'{len(again)} jobs of the first freeze started again after it: {again[:5]}')
    return probs, len(kept)


def check(expect):
    probs, waits, info = [], [], {}
    cp = copies()
    jd = ROOT / Q4 / 'jobs.d'
    names = sorted(p.name for p in jd.glob('*.jsonl'))
    want_names = sorted(Path(c).name for c in cp)
    if names != want_names:
        probs.append(f'{Q4}/jobs.d holds {names}, not the six registered job files {want_names}')
    for c, v in cp.items():
        if (ROOT / c).is_file() and sha(c) != v['sha256']:
            probs.append(f'{c} is not at its G6 sha256')
        if v.get('job_file') and sha(v['job_file']) != v['sha256']:
            probs.append(f'{v["job_file"]} is not at its G6 sha256')
    ids = {}
    for c in cp:
        if (ROOT / c).is_file():
            for i in job_ids(c):
                ids[i] = c
    info['job_lines'] = len(ids)
    if len(ids) != TOTAL:
        probs.append(f'{len(ids)} job lines, not {TOTAL}')
    qs, held = G8.runner_status(Q4)
    pending = [i for i in ids if i in qs['pending']]
    info.update(final=len(ids) - len(pending), pending=len(pending), runner_alive=qs['runner_alive'],
                runner_lock_held=held, stop_file=qs['stop_file'],
                last_runner_start=(qs['last_runner_start'] or {}).get('utc'),
                last_runner_exit=(qs['runner_exit'] or {}).get('utc'))
    if pending:
        waits.append(f'{len(pending)} job lines without a final runner record')
    if qs['runner_alive'] or held:
        waits.append(f'a runner holds {Q4} (pid {qs["runner_pid"]}, lock held {held})')
    elif qs['runner_exit'] is None and qs['last_runner_start'] is not None:
        waits.append('the last runner start has no later runner exit record (the runner may still run)')
    if expect == 'stopped' and not qs['stop_file']:
        probs.append(f'{Q4}/STOP is missing: run g8f_stop.sh first')
    first_doc = read_json(FIRST_RECORD) if (ROOT / FIRST_RECORD).is_file() else None
    if first_doc is not None:
        p, n = kept_rerun_problems(first_doc, status_records())
        probs += p
        info['first_freeze_final_jobs'] = n
    pd = f'{V4}/phase_driver'
    if not (ROOT / pd / 'STOP').exists():
        probs.append(f'{pd}/STOP is missing (Amendments A12 and A17 keep the phase driver stopped)')
    alive, pid = G8.pid_alive_with(f'{pd}/driver.pid', 'phase_driver.py')
    if alive:
        probs.append(f'the phase driver runs (pid {pid}); it stays stopped')
    for f in (f'{V4}/p1_driver/ALERT.txt', f'{V4}/p1_driver/protocol_txn.json', f'{pd}/ALERT.txt',
              f'{pd}/protocol_txn.json', 'framelease_v4/.PROTOCOL.md.entrytmp'):
        if (ROOT / f).exists():
            probs.append(f'{f} exists')
    text = protocol_text()
    s13 = G8.sec13(text)
    for a in AMENDS:
        n = len(G8.amend_lines(s13, a))
        if n != 1:
            probs.append(f'Amendment {a} found {n} times in Sec. 13.2')
    code = code_map()
    code.update({ANALYZE: sha(ANALYZE), VI: sha(VI), R7B: sha(R7B)})
    unc = [p for p, h in code.items() if h not in s13]
    if unc:
        probs.append(f'analysis code not cited at its sha256 on disk: {unc}')
    if F1_SHA not in amend_par(text, 'A11') or f1_sha() != F1_SHA:
        probs.append(f'{F1_REPORT} is not at the sha256 Amendment A11 cites ({F1_SHA[:12]})')
    fp, finfo = first_freeze()
    probs += fp
    info['first_freeze'] = finfo
    nd = new_dirs()
    info['new_analysis_dirs'] = nd
    if len(nd) > 1:
        probs.append(f'{ANALYSIS_DIR} holds {len(nd)} new final_* directories {nd}: one second freeze only')
    info['next_amendment'] = G8.next_name(text)
    info['problems'], info['waits'] = probs, waits
    print(json.dumps(info, indent=1, sort_keys=True, default=str))
    if probs:
        print('CHECK: PROBLEM')
        return 2
    if waits:
        print('CHECK: NOT FINAL (wait)')
        return 3
    print(f'CHECK: READY ({expect})' + (f'; resume in {nd[0]}' if nd else ''))
    return 0


def stop():
    rc = check('stopped') if (ROOT / Q4 / 'STOP').exists() else check('final')
    if rc != 0:
        print('STOP: refused (the queue is not final, or a problem)')
        return rc
    stop_p = ROOT / Q4 / 'STOP'
    if stop_p.exists():
        print(f'STOP: {Q4}/STOP exists already; nothing to do')
        return 0
    tmp = ROOT / Q4 / '.STOP.g8ftmp'
    tmp.write_text(f'{time.strftime("%Y-%m-%dT%H:%M:%S%z")} G8 under Amendment A17: every job of the six registered '
                   'job files is final and the runner has exited; the second analysis-freeze record follows. No runner '
                   'starts in this queue. Do not remove.\n')
    os.replace(tmp, stop_p)
    print(f'STOP: {Q4}/STOP written')
    return check('stopped')


# ------------------------------------------------------------------------------------------------ the record

def record_info(d):
    from framelease_v4.analysis import interim_guard as G
    d = rel(d)
    rec, req = f'{d}/{RECORD}', f'{d}/{REQUIRED}'
    doc = read_json(rec)
    want = required_map()
    if read_json(req) != want:
        raise SystemExit(f'{req} differs from the registered job files of the test freeze')
    probs = G.record_problems(doc, required_job_files=want)
    if doc.get('trigger') != 'all_final' or doc.get('cut_amendment'):
        probs.append(f'trigger {doc.get("trigger")!r}, cut {doc.get("cut_amendment")!r}: Amendment A17 freezes when '
                     'every job is final, without a cut')
    if doc.get('job_files') != want:
        probs.append(f'job files {doc.get("job_files")} != {want}')
    ids = {i: c for c in want for i in job_ids(c)}
    jobs = doc.get('jobs') or {}
    if set(jobs) != set(ids):
        probs.append(f'{len(jobs)} jobs in the record, {len(ids)} job lines (differences '
                     f'{sorted(set(jobs) ^ set(ids))[:5]})')
    counts, per_file = {}, {}
    for jid, v in jobs.items():
        o = v.get('outcome')
        counts[o] = counts.get(o, 0) + 1
        pf = per_file.setdefault(v.get('job_file'), {})
        pf[o] = pf.get(o, 0) + 1
        if o not in FINAL or v.get('job_file') != ids.get(jid):
            probs.append(f'{jid}: outcome {o!r}, job file {v.get("job_file")}')
    code = doc.get('analysis_code') or {}
    if code != code_map():
        probs.append(f'the analysis code of the record is not the registered code on disk: {code}')
    unc = [p for p, h in code.items() if not cited(h)]
    if unc:
        probs.append(f'analysis code of the record not cited in Sec. 13.2: {unc}')
    sums = f'{d}/SHA256SUMS'
    probs += sums_problems(d, sums)
    agg = read_json(f'{d}/aggregate.json')
    g = agg.get('interim_guard') or {}
    if g.get('status') != 'pre_freeze' or g.get('summary') is not None or (ROOT / d / 'arm_summary.csv').exists():
        probs.append(f'the aggregation is not the guarded one (guard {g.get("status")}, summary {g.get("summary")})')
    if (agg.get('arguments') or {}).get('queues') != [Q4]:
        probs.append(f'aggregation queues {(agg.get("arguments") or {}).get("queues")} != [{Q4}]')
    rsha = sha(rec)
    first = read_json(FIRST_RECORD)
    if d == FIRST or rsha == FIRST_RECORD_SHA:
        probs.append('the record is the first freeze\'s')
    if cited(rsha):             # entered already: then its entry must be a new one (A18 or later), never A10-A17
        _, PD = G8.drivers()
        owner, _ = owner_of(PD.phase_view(None, protocol_text()), rsha)
        if owner is None or int(re.sub(r'\D', '', owner)) <= 17:
            probs.append(f'the record sha256 is cited in Sec. 13 by {owner}, not by a new entry after Amendment A17')
    if not doc.get('frozen') or to_utc(doc['frozen']) <= to_utc(first['frozen']):
        probs.append(f'frozen {doc.get("frozen")} is not after the first freeze {first["frozen"]}')
    kept_same = cut_final = 0
    by_first = {'kept': {}, 'new': {}}
    for jid, v in first['jobs'].items():
        now = jobs.get(jid) or {}
        if v['outcome'] in FINAL:
            if (now.get('outcome'), now.get('run_dir')) != (v['outcome'], v['run_dir']):
                probs.append(f'{jid}: {now.get("outcome")} / {now.get("run_dir")} here, {v["outcome"]} / '
                             f'{v["run_dir"]} in the first record')
            else:
                kept_same += 1
            k = by_first['kept']
        else:
            cut_final += int(now.get('outcome') in FINAL)
            k = by_first['new']
        k[now.get('outcome')] = k.get(now.get('outcome'), 0) + 1
    if (kept_same, cut_final) != (KEPT, NEW) or len(jobs) != TOTAL:
        probs.append(f'{kept_same} jobs as in the first record, {cut_final} cut jobs now final, {len(jobs)} jobs: '
                     f'Amendment A17 has {KEPT}, {NEW} and {TOTAL}')
    qs, _ = G8.runner_status(Q4)
    return {'record': rec, 'sha256': rsha, 'required': req, 'required_sha256': sha(req), 'sha256sums': sums,
            'sha256sums_sha256': sha(sums), 'frozen': doc.get('frozen'), 'trigger': doc.get('trigger'),
            'cut_amendment': doc.get('cut_amendment'), 'outcomes': dict(sorted(counts.items())),
            'per_file': per_file, 'by_first_record': by_first, 'code': code,
            'route_split_sha256': doc.get('route_split_sha256'),
            'guard': {k: g.get(k) for k in ('status', 'guarded_rows', 'test_route_rows', 'health_only_rows')},
            'runner_exit': (qs['runner_exit'] or {}).get('utc'), 'stop_file': qs['stop_file'], 'problems': probs}


# ------------------------------------------------------------------------------------------------ entries

def outcome_text(o, keys=FINAL):
    return ', '.join(f'{k} {o.get(k, 0)}' for k in keys)


def freeze_entry(d, name):
    info = record_info(d)
    if info['problems']:
        raise SystemExit(f'the record does not validate: {info["problems"]}')
    d = rel(d)
    cp = copies()
    stamp = time.strftime('%Y-%m-%d %H:%M')
    rec, req, sums = info['record'], info['required'], info['sha256sums']
    files = '; '.join(f'`{c}` (tier {v["tier"]}, {len(job_ids(c))} lines, sha256 `{v["sha256"]}`)'
                      for c, v in cp.items())
    mods = ', '.join(f'`{Path(p).name}` (sha256 `{h}`)' for p, h in sorted(info['code'].items()))
    bf = info['by_first_record']
    title = (f'**Amendment {name}, {stamp} (Beijing time): the second analysis freeze (Sec. 9.12) under Amendment A17, '
             'all registered jobs final, carried out by the coordinating session with the registered tools in place '
             'of gate G8 of the phase driver; no run, job line, criterion or analysis rule changes.**')
    bullets = [
        f'Freeze. Every job of the six registered job files of the test freeze was final and the runner of `{Q4}` had '
        f'exited (last runner exit {info["runner_exit"]}); `{Q4}/STOP` was written before the freeze and '
        f'`test_freeze.py --verify` passed on the job files in `{Q4}/jobs.d`. `aggregate_v4.py --queue {Q4} --specs '
        f'{V4}/test_jobs/FULL --rl-freeze {V4}/rl_freeze/rl_freeze.json --tuning-freeze {V4}/tuning/selection.json '
        f'--write-freeze-record {rec}` wrote `{rec}` (sha256 `{info["sha256"]}`; trigger {info["trigger"]}, no cut, '
        f'frozen {info["frozen"]}).',
        f'Job status: {TOTAL} jobs of the 6 job files of the test freeze (entry "G6 Test freeze", record '
        f'`{TEST_FREEZE}` sha256 `{sha(TEST_FREEZE)}`): {files}; outcomes {outcome_text(info["outcomes"])}; no job '
        f'cut. The {KEPT} jobs that the record of Amendment A13 holds as final carry the same outcomes and run '
        f'directories here ({outcome_text(bf["kept"])}); the {NEW} jobs that Amendment A12 cut and Amendment A17 runs '
        f'are final ({outcome_text(bf["new"])}).',
        f'Analysis code frozen by the record: {mods}; the analysis script `{ANALYZE}` (sha256 `{sha(ANALYZE)}`) and '
        f'`{VI}` (sha256 `{sha(VI)}`) are registered in Sec. 13.2 by Amendment A10, `{R7B}` (sha256 `{sha(R7B)}`) by '
        f'Amendment A11. Route split sha256 `{info["route_split_sha256"]}`.',
        'Interim looks (Sec. 9.11). The aggregation that made the record ran without --arm-summary and without '
        '--analysis-freeze: every test-route row stayed health-only and no cross-arm summary was made. Its outputs and '
        f'its guard log are in `{d}` (`SHA256SUMS` sha256 `{info["sha256sums_sha256"]}`); `{req}` (sha256 '
        f'`{info["required_sha256"]}`) lists the six queue copies at their G6 sha256 (the --required-job-files of the '
        'analysis).',
        f'First analysis freeze. The record of Amendment A13 (`{FIRST_RECORD}`, sha256 `{FIRST_RECORD_SHA}`) stays '
        f'valid and unchanged, as do its outputs in `{FIRST}` and `{VFIRST}*` (every `SHA256SUMS` there verifies). It '
        f'holds the {NEW} jobs of Amendment A17 as cut and releases none of their runs. Every result in the paper '
        'names the analysis it comes from (Amendment A17).',
        'Validity. The record is valid from this entry on (its sha256 in Sec. 13 of the sealed PROTOCOL.md, '
        '`interim_guard.load_freeze`). The confirmatory analysis (Amendments A3 and A10) writes its outputs into '
        f'directories inside `{d}`, each with its sha256 manifest; the independent verifications (Amendment A10, use '
        'rule 4; Amendment A11 with the resolution rule of Amendment A16) read the released aggregation '
        f'`{d}/agg_p4` (Amendment A16, "Aggregation path"). The phase driver stays stopped '
        f'(`{V4}/phase_driver/STOP`, Amendments A12 and A17): this entry takes the place of its G8 entry.',
        MANIFEST_CLAUSE]
    filled = G8.wrap_entry(title, bullets)
    tmpl = G8.placeholders(filled, [(f'{name}, {stamp} (Beijing', f'{name}, {{{{datetime}}}} (Beijing'),
                                    (info['sha256'], f'{{{{sha256:{rec}}}}}'),
                                    (info['sha256sums_sha256'], f'{{{{sha256:{sums}}}}}'),
                                    (info['required_sha256'], f'{{{{sha256:{req}}}}}')])
    must = {rec: info['sha256'], sums: info['sha256sums_sha256'], req: info['required_sha256'],
            TEST_FREEZE: sha(TEST_FREEZE), ANALYZE: sha(ANALYZE), VI: sha(VI), R7B: sha(R7B),
            FIRST_RECORD: FIRST_RECORD_SHA, **{c: v['sha256'] for c, v in cp.items()}, **info['code']}
    return tmpl, must, info


def write_spec(name, tmpl, must):
    out = ROOT / HERE / 'entries'
    out.mkdir(parents=True, exist_ok=True)
    t = out / f'{name}_entry.md'
    t.write_text(tmpl, encoding='utf-8')
    spec = {'name': name, 'template': str(t.relative_to(ROOT)), 'tests': [], 'inplace': [], 'must_equal':
            {str(k): v for k, v in sorted(must.items())}, 'max_new_registered': 0}
    s = out / f'{name}_spec.json'
    s.write_text(json.dumps(spec, indent=1) + '\n', encoding='utf-8')
    bad = G8.line_problems(tmpl) + G8.line_problems(G8.fill_preview(tmpl))
    print(f'{t.relative_to(ROOT)} ({len(tmpl.splitlines())} lines), {s.relative_to(ROOT)}; line problems: {bad}')
    return 2 if bad else 0


def owner_of(view, h):
    _, PD = G8.drivers()
    s, e = view['sec']
    line = next((i + 1 for i in range(s, e) if h in view['lines'][i]), None)
    return (PD.citing_amendment(view, line) if line else None), line


def simulate(d, name):
    from framelease_v4.analysis import interim_guard as G
    d = rel(d)
    spec = read_json(f'{HERE}/entries/{name}_spec.json')
    tmpl = (ROOT / spec['template']).read_text(encoding='utf-8')
    text = protocol_text()
    new = G8.compose(text, G8.fill_preview(tmpl))
    probs, v1 = G8.parse_checks(text, new, name)
    rec = f'{d}/{RECORD}'
    req = read_json(f'{d}/{REQUIRED}')
    sim = Path('/tmp/G8FULL_sim') / f'{name}_{os.getpid()}'
    sim.mkdir(parents=True)
    (sim / 'PROTOCOL.md').write_text(new, encoding='utf-8')
    (sim / 'SEAL.sha256').write_text(f'{hashlib.sha256(new.encode()).hexdigest()}  {sim / "PROTOCOL.md"}\n')
    if v1 is not None:
        owner, _ = owner_of(v1, sha(rec))
        if owner != name:
            probs.append(f'the record sha256 is first cited by {owner}, not {name}')
        owner1, _ = owner_of(v1, FIRST_RECORD_SHA)
        if owner1 != 'A13':
            probs.append(f'the first record is first cited by {owner1}, not A13')
    got = {}
    for label, path in (('second', ROOT / rec), ('first', ROOT / FIRST_RECORD)):
        try:
            fz = G.load_freeze(path, protocol=sim / 'PROTOCOL.md', seal=sim / 'SEAL.sha256',
                               required_job_files=req)
            got[label] = {k: fz[k] for k in ('trigger', 'cut_amendment', 'registered')}
        except G.GuardRefused as e:
            probs.append(f'load_freeze refused the {label} record on the composed copy: {e}')
    try:
        G.load_freeze(ROOT / rec, required_job_files=req)
        probs.append('load_freeze accepts the second record BEFORE the entry')
    except G.GuardRefused:
        pass
    shutil.rmtree(sim)
    print(json.dumps({'composed_sha256': hashlib.sha256(new.encode()).hexdigest(), 'load_freeze_on_copy': got,
                      'problems': probs}, indent=1))
    print('SIMULATE: OK' if not probs else 'SIMULATE: PROBLEM')
    return 0 if not probs else 2


def post(d, name):
    from framelease_v4.analysis import interim_guard as G
    d = rel(d)
    text = protocol_text()
    P1, PD = G8.drivers()
    probs = []
    try:
        P1.protocol_view(None, text)
        v = PD.phase_view(None, text)
    except Exception as e:  # noqa: BLE001
        print(f'POST: PROBLEM {type(e).__name__}: {e}')
        return 2
    if len(v['amendments'].get(name, [])) != 1:
        probs.append(f'{name} read at lines {v["amendments"].get(name)}')
    rec = f'{d}/{RECORD}'
    rsha = sha(rec)
    owner, line = owner_of(v, rsha)
    if owner != name:
        probs.append(f'the record sha256 is first cited by {owner}, not {name}')
    out = {}
    req = read_json(f'{d}/{REQUIRED}')
    for label, path, want in (('second', rec, ('all_final', None)), ('first', FIRST_RECORD, ('cut', 'A12'))):
        try:
            fz = G.load_freeze(ROOT / path, required_job_files=req)
            out[label] = {k: fz[k] for k in ('trigger', 'cut_amendment', 'registered', 'protocol_sha256')}
            if not fz['registered'] or (fz['trigger'], fz['cut_amendment']) != want:
                probs.append(f'load_freeze of the {label} record: {out[label]}')
        except G.GuardRefused as e:
            probs.append(f'load_freeze refused the {label} record: {e}')
    print(json.dumps({'record': rec, 'sha256': rsha, 'cited_line': line, 'owner': owner, 'load_freeze': out,
                      'problems': probs}, indent=1))
    print('POST: OK' if not probs else 'POST: PROBLEM')
    return 0 if not probs else 2


def result_entry(kind, name, vdir, d, freeze_name, class_report=None):
    stamp = time.strftime('%Y-%m-%d %H:%M')
    vdir, d = rel(vdir), rel(d)
    if kind == 'verify':
        vj = f'{vdir}/verification.json'
        doc = read_json(vj)
        verdict, status = doc.get('verdict'), doc.get('status')
        comp = doc.get('comparisons') or {}
        n_diff = len(comp['differences']) if isinstance(comp.get('differences'), list) else comp.get('differences')
        title = (f'**Amendment {name}, {stamp} (Beijing time): result of the independent verification of H1 and of '
                 'the Table I columns DS, SR, RC, collisions/km and infractions/km on the second analysis freeze '
                 f'(Amendment {freeze_name}; Sec. 9.12; Amendment A10, use rule 4); no run, job line, criterion or '
                 'analysis rule changes.**')
        bullets = [
            f'Run. An independent session ran `{VI}` (sha256 `{sha(VI)}`) after the analysis freeze of Amendment '
            f'{freeze_name}, with the record `{d}/{RECORD}`, the released aggregation `{d}/agg_p4`, the analysis '
            f'`{d}/analysis` and `--queue {Q4}`, into `{vdir}`.',
            f'Result. `{vj}` (sha256 `{sha(vj)}`): status {status}, verdict {verdict}, differences {n_diff}; '
            f'`SHA256SUMS` sha256 `{sha(vdir + "/SHA256SUMS")}`. '
            + ('AGREE releases H1 and its findings and the verified Table I columns of this analysis (use rule 4).'
               if verdict == 'AGREE' else 'Every difference of `differences.csv` is resolved and its cause entered in '
               'Sec. 13 before any of these numbers enters the paper (use rule 4).'),
            MANIFEST_CLAUSE]
        files = [vj, f'{vdir}/SHA256SUMS']
    else:
        tj = f'{vdir}/table1_extra.json'
        doc = read_json(tj)
        rep = read_json(class_report)
        sizes = ', '.join(f'{CLASS_NAMES.get(c, c)} {n}' for c, n in (rep.get('differences_by_class') or {}).items())
        release = rep.get('release')
        use = {'AGREE': 'AGREE releases these columns (use rule 2).',
               'pre-specified classes only': 'Every difference lies in a pre-specified class: these columns are '
               'released with the registered values, and the paper states each class, its cause and its size (use '
               'rule 2).'}.get(release, 'A difference without a pre-specified class is a verification failure: each '
                               'such difference is resolved and its cause entered in Sec. 13 before any of these '
                               'numbers enters the paper (use rule 2; Amendment A10, use rule 4); for pairing-status '
                               'rows of the closed-loop R_cond the resolution rule of Amendment A16 applies (Amendment '
                               'A17).')
        title = (f'**Amendment {name}, {stamp} (Beijing time): result of the independent recomputation of the Table I '
                 'columns GPU usage, DMR, action age, fallback ratio, EIR and P_both and of the closed-loop R_cond on '
                 f'the second analysis freeze (Amendment {freeze_name}; Sec. 9.12; Amendment A11, use rules 1-3); no '
                 'run, job line, criterion or analysis rule changes.**')
        bullets = [
            f'Run. An independent session ran `{R7B}` (sha256 `{sha(R7B)}`) after the analysis freeze of Amendment '
            f'{freeze_name}, with the record, `--queue {Q4}`, the released aggregation `{d}/agg_p4` and the analysis '
            f'`{d}/analysis`, into `{vdir}`, and the class report `{F1_REPORT}` (sha256 `{F1_SHA}`) on that '
            'directory.',
            f'Result. `{tj}` (sha256 `{sha(tj)}`): status {doc.get("status")}, verdict {doc.get("verdict")}; '
            f'`SHA256SUMS` sha256 `{sha(vdir + "/SHA256SUMS")}`; class report `{rel(class_report)}` (sha256 '
            f'`{sha(class_report)}`): outcome {rep.get("outcome")}, release {release}; differences per class: '
            f'{sizes or "none"}.',
            f'Use. {use}',
            MANIFEST_CLAUSE]
        files = [tj, f'{vdir}/SHA256SUMS', rel(class_report)]
    filled = G8.wrap_entry(title, bullets)
    subs = [(f'{name}, {stamp} (Beijing', f'{name}, {{{{datetime}}}} (Beijing')]
    subs += [(sha(f), f'{{{{sha256:{f}}}}}') for f in files]
    return G8.placeholders(filled, subs), {f: sha(f) for f in files}


# ------------------------------------------------------------------------------------------------ resolution (A16 rule)

def load_f1():
    if f1_sha() != F1_SHA:
        raise SystemExit(f'{F1_REPORT} is not at the sha256 Amendment A11 cites')
    return _load('f1_class_report_g8f', ROOT / F1_REPORT)


def classify(vdir):
    """The classes of differences.csv formed exactly as f1_class_report.report forms them: {class: [rows]}, the
    table1_extra.json document, and the recorded analysis paired_differences.csv path."""
    f1 = load_f1()
    paths, _ = f1.checked_inputs(vdir)
    diffs = f1.read_csv(paths['differences.csv'])
    runs_rows = f1.read_csv(paths['runs_recomputed.csv'])
    by_job, by_dir, row_of = f1.runs_index(runs_rows)
    with open(paths['table1_extra.json'], encoding='utf-8') as fh:
        t1 = json.load(fh)
    runtime_gpu_differs = {r.get('key') for r in diffs if r['target'] == 'runs.csv' and
                           (r.get('their_field') or r.get('field')) in f1.RUNTIME_GPU}
    outcomes, rows = {}, {}
    if any(f1.not_ok_candidate(r) for r in diffs):
        queues, runs_csv = f1.recorded_inputs(t1)
        outcomes, rows = f1.runner_outcomes(queues), f1.runs_csv_rows(runs_csv)
    analysis_rows, source = {}, None
    if any(f1.pairing_candidate(r) for r in diffs):
        p = f1.recorded_files(t1, ('paired_differences.csv',), 'analysis paired_differences.csv')
        if p['paired_differences.csv']:
            source = p['paired_differences.csv'][0]
            for a in f1.read_csv(source):
                analysis_rows[(a.get('table'), a.get('contrast'), a.get('metric'), str(a.get('route_id')))] = a
    value_keys = {r.get('key') for r in diffs if r['target'] == 'paired_differences.csv'
                  and r.get('field') in f1.PAIRED_VALUES}
    classes = {f1.CLASS: [], 'F3': [], f1.IN_FLIGHT: [], f1.NOT_OK: [], f1.PAIRING: [], f1.UNEXPLAINED: []}
    for r in diffs:
        cause = r.get('cause') or ''
        cname = next((c for c, causes in f1.CLASS_CAUSES.items() if cause in causes), None)
        if cname is None and f1.is_in_flight(r, row_of, runtime_gpu_differs):
            cname = f1.IN_FLIGHT
        if cname is None and f1.not_ok_candidate(r):
            if f1.not_ok_job(r.get('key') or '', outcomes, rows):
                cname = f1.NOT_OK
        if cname is None and f1.pairing_candidate(r):
            if f1.pairing_missing_arms(r, analysis_rows, value_keys, runs_rows) is not None:
                cname = f1.PAIRING
        classes[cname or f1.UNEXPLAINED].append(r)
    return f1, classes, diffs, runs_rows, row_of, analysis_rows, t1, source


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def rcond_rule(vdir, d):
    """(rows, failures, details) of the A16 rule over the unexplained rows (module docstring, 'resolution')."""
    f1, classes, diffs, runs_rows, row_of, analysis_rows, t1, source = classify(vdir)
    unexplained = classes[f1.UNEXPLAINED]
    rec = f1.recorded_files(t1, ('runs.csv', 'cells.csv'), 'runs.csv and cells.csv of the analysis')
    if len(rec['runs.csv']) != 1 or len(rec['cells.csv']) != 1:
        raise SystemExit(f'table1_extra.json inputs name {len(rec["runs.csv"])} runs.csv and {len(rec["cells.csv"])} '
                         'cells.csv')
    runs_csv, cells_csv = rec['runs.csv'][0], rec['cells.csv'][0]
    want_runs, want_pairs = f'{d}/agg_p4/runs.csv', f'{d}/analysis/paired_differences.csv'
    for got, want in ((runs_csv, want_runs), (source, want_pairs)):
        if got is not None and Path(got).resolve() != (ROOT / want).resolve():
            raise SystemExit(f'the verification read {got}, not {want}')
    agg = {r['job']: r for r in f1.read_csv(runs_csv)}
    cells = {}
    for c in f1.read_csv(cells_csv):
        cells[(c.get('condition'), str(c.get('route_id')))] = c
    contrast_rows = {}
    run_rows = {}
    for r in diffs:
        k = r.get('key') or ''
        if r['target'] == 'runs.csv':
            run_rows.setdefault(k, []).append(r)
        elif ':' in k and k.count('/') == 1:
            contrast_rows.setdefault(k.split(':', 1)[1], []).append(r)
    value_keys = {r.get('key') for r in diffs if r['target'] == 'paired_differences.csv'
                  and r.get('field') in f1.PAIRED_VALUES}
    failures, details = [], []
    for r in unexplained:
        why = []
        key = f1.pairing_key(r.get('key'))
        m = f1.PAIRING_NOTE.match(r.get('note') or '')
        if not f1.pairing_candidate(r):
            why.append('not a pairing-status row (cause, target, field or sides)')
        if key is None or key[2] != R_COND:
            why.append(f'metric {key[2] if key else None!r}, not r_cond')
        if m is None or m.group('column') != R_COND_COLUMN:
            why.append(f'note {r.get("note")!r} is not "status \'{R_COND_COLUMN} missing: <conditions>\'"')
        if why:
            failures.append({'row': r, 'why': why})
            continue
        table, contrast, metric, route = key
        a = analysis_rows.get(key)
        if a is None or (a.get('status') or '') != m.group('status') \
                or any((a.get(f) or '').strip() for f in f1.PAIRED_VALUES):
            why.append('the analysis row is absent, carries another status or holds a value')
        if r.get('key') in value_keys:
            why.append('a value_a / value_b / difference row of this key differs')
        if contrast_rows.get(f'{contrast}/{metric}'):
            why.append(f'{len(contrast_rows[f"{contrast}/{metric}"])} contrast-level rows of {contrast}/{metric} '
                       'differ')
        conds = [c.strip() for c in m.group('conds').split(',')]
        sides = []
        for cond in conds:
            cell = cells.get((cond, route))
            jobs = f1.as_json(cell.get('jobs'), []) if cell else []
            if not cell or cell.get('status') != 'used' or len(jobs) != 1:
                why.append(f'{cond} on route {route}: no single used cell')
                continue
            job = str(jobs[0])
            g, x = agg.get(job), row_of.get(job)
            reg = (g or {}).get('realized_r_cond', ''), _num((g or {}).get('realized_conflict_plans'))
            rcp = (x or {}).get('r_cond', ''), _num((x or {}).get('conflict_plans'))
            sides.append({'condition': cond, 'job': job, 'registered': reg, 'recomputed': rcp,
                          'recomputed_bounds': (x or {}).get('r_cond_bounds') or None})
            if g is None or x is None:
                why.append(f'{job}: no runs.csv or runs_recomputed.csv row')
            elif reg[0].strip() or reg[1] != 0 or rcp[0].strip() or rcp[1] != 0:
                why.append(f'{job}: R_cond is not 0/0 on both sides (registered {reg}, recomputed {rcp})')
            if any((rr.get('their_field') or rr.get('field')) in R_COND_RUN_COLUMNS for rr in run_rows.get(job, [])):
                why.append(f'{job}: a runs.csv comparison of R_cond, conflict plans or misses differs')
        if not sides:
            why.append('no condition named')
        if why:
            failures.append({'row': r, 'why': why})
        else:
            details.append({'key': r.get('key'), 'table': table, 'contrast': contrast, 'route_id': route,
                            'status': m.group('status'), 'sides': sides})
    return unexplained, failures, details, classes, f1


def resolution(name, vdir, class_report, d, extra_name):
    vdir, d, class_report = rel(vdir), rel(d), rel(class_report)
    rep = read_json(class_report)
    unexplained, failures, details, classes, f1 = rcond_rule(vdir, d)
    counts = {k: len(v) for k, v in classes.items()}
    if counts != (rep.get('differences_by_class') or {}):
        print(f'RESOLUTION: STOP: the classes formed again {counts} differ from the class report '
              f'{rep.get("differences_by_class")}')
        return 2
    if not unexplained:
        print(f'RESOLUTION: not needed (class report outcome {rep.get("outcome")}, no unexplained row)')
        return 0
    if rep.get('outcome') != 'verification failure':
        print(f'RESOLUTION: STOP: {len(unexplained)} unexplained rows but outcome {rep.get("outcome")!r}')
        return 2
    if failures:
        print(f'RESOLUTION: STOP: {len(failures)} of {len(unexplained)} unexplained rows are outside the resolution '
              'rule of Amendment A16 (no entry; each is resolved and its cause entered by hand, Amendment A10 use '
              'rule 4):')
        for f in failures[:40]:
            r = f['row']
            print(f'  {r.get("target")} | {r.get("key")} | {r.get("field")}/{r.get("their_field")} | '
                  f'{r.get("ours")!r} / {r.get("theirs")!r} | {r.get("note")!r}: {"; ".join(f["why"])}')
        if len(failures) > 40:
            print(f'  ... {len(failures) - 40} more')
        return 3
    stamp = time.strftime('%Y-%m-%d %H:%M')
    n = len(details)
    per = {}
    for x in details:
        per[x['contrast']] = per.get(x['contrast'], 0) + 1
    rows_text = '; '.join(f'`{c}` {k}' for c, k in sorted(per.items()))
    bounded = [x for x in details if any(s['recomputed_bounds'] for s in x['sides'])]
    rep_un = rep.get('unexplained') or {}
    an = {k: (rep.get(f'class_{k}') or {}).get('analysis_differences', 0) for k in ('F1', 'F3', 'in_flight')}
    jobs_no = sorted(((rep.get('class_not_ok_record') or {}).get('jobs') or {}))
    sizes = (f'F1 {counts["F1"]} differences ({an["F1"]} in the analysis scope), F3 {counts["F3"]} ({an["F3"]} in the '
             f'analysis scope), in-flight {counts["in_flight"]} ({an["in_flight"]} in the analysis scope), not-ok '
             f'record {counts["not_ok_record"]}'
             + (f' (jobs {", ".join(f"`{j}`" for j in jobs_no)})' if jobs_no else '')
             + f', undefined-metric pairing {counts["undefined_metric_pairing"]}, and the {n} above')
    files = {class_report: sha(class_report), f'{vdir}/differences.csv': sha(f'{vdir}/differences.csv'),
             f'{vdir}/runs_recomputed.csv': sha(f'{vdir}/runs_recomputed.csv'),
             f'{d}/agg_p4/runs.csv': sha(f'{d}/agg_p4/runs.csv'),
             f'{d}/analysis/paired_differences.csv': sha(f'{d}/analysis/paired_differences.csv')}
    title = (f'**Amendment {name}, {stamp} (Beijing time): resolution of the {n} differences outside the classes of '
             f'Amendment A11 in the recomputation of Amendment {extra_name}, by the resolution rule of Amendment A16 '
             '(Amendment A17); no run, job line, criterion or analysis rule changes.**')
    bullets = [
        f'Differences. The class report of Amendment {extra_name} (`{class_report}`, sha256 `{files[class_report]}`) '
        f'reads "verification failure" with {n} differences outside the five classes of Amendment A11 '
        f'({rep_un.get("analysis_differences", 0)} in the analysis scope). All {n} are status rows of the paired '
        'differences of the secondary metric closed-loop R_cond: the analysis records the route as missing for that '
        f'metric ("{R_COND_COLUMN} missing: <conditions>"), the recomputation records it as paired. No row holds a '
        'value, a difference or a different n on either side, and no per-run comparison of R_cond, conflict plans or '
        'misses differs for the cells of these pairs. For every condition that the analysis names, R_cond is '
        f'undefined (no conflict plan, 0/0) both in the registered aggregation (`{d}/agg_p4/runs.csv`, sha256 '
        f'`{files[f"{d}/agg_p4/runs.csv"]}`) and in the recomputation (`{vdir}/runs_recomputed.csv`, sha256 '
        f'`{files[f"{vdir}/runs_recomputed.csv"]}`). The analysis drops such a route from the contrast (Sec. 9.8); '
        'the recomputation pairs it with empty values.'
        + (f' In {len(bounded)} of the rows a cell left undefined carries a recomputed interval from plans left '
           'unevaluated; its point value is undefined on both sides.' if bounded else '')
        + f' The rows per contrast: {rows_text}. Evidence: `{vdir}/differences.csv` (sha256 '
        f'`{files[f"{vdir}/differences.csv"]}`) and `{d}/analysis/paired_differences.csv` (sha256 '
        f'`{files[f"{d}/analysis/paired_differences.csv"]}`).',
        'Resolution (Amendment A10, use rule 4; Amendment A11, use rule 2; Amendment A16). The differences have the '
        'cause that Amendment A16 resolved for the cut analysis, and no numeric value disagrees. The class report '
        'stays as computed and is reported as "verification failure" with this cause. With the cause entered here, the '
        'columns of Table I that Amendment A11 covers (GPU usage, DMR, action age p50 and p95, fallback ratio, EIR, '
        'P_both) and the closed-loop R_cond of this analysis enter the paper with their registered values, stated '
        f'together with the size of every class: {sizes}.',
        MANIFEST_CLAUSE]
    filled = G8.wrap_entry(title, bullets)
    subs = [(f'{name}, {stamp} (Beijing', f'{name}, {{{{datetime}}}} (Beijing')]
    subs += [(h, f'{{{{sha256:{f}}}}}') for f, h in files.items()]
    tmpl = G8.placeholders(filled, subs)
    rc = write_spec(name, tmpl, files)
    out = ROOT / HERE / 'entries' / f'{name}_rows.json'
    out.write_text(json.dumps({'rule': 'Amendment A16 resolution rule (R_cond 0/0 pairing status)', 'rows': details},
                              indent=1, default=str) + '\n', encoding='utf-8')
    print(f'RESOLUTION: entry written ({n} unexplained rows, all R_cond 0/0 pairing-status rows; '
          f'{out.relative_to(ROOT)})')
    return rc


# ------------------------------------------------------------------------------------------------ manifests, end state

def write_outputs_list(d):
    """F/ANALYSIS_OUTPUTS.sha256: '<sha256>  <path from the root>' of every file below F except the list itself, in
    path order; written to a temporary file OUTSIDE F (G8FULL/logs) and renamed into F, so that it never lists its own
    temporary file (Amendment A16, correction 2); then every line is checked."""
    d = rel(d)
    files = sorted(rel(p) for p in (ROOT / d).rglob('*') if p.is_file() and p.name != OUTPUTS_LIST)
    lines = ''.join(f'{sha(p)}  {p}\n' for p in files)
    tmp = ROOT / HERE / 'logs' / f'.{OUTPUTS_LIST}.{os.getpid()}.tmp'
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(lines, encoding='utf-8')
    os.replace(tmp, ROOT / d / OUTPUTS_LIST)
    return check_outputs_list(d)


def check_outputs_list(d):
    d = rel(d)
    lst = ROOT / d / OUTPUTS_LIST
    listed = [ln.partition('  ') for ln in lst.read_text(encoding='utf-8').splitlines()]
    probs = [p for h, _, p in listed if not (ROOT / p).is_file() or sha(p) != h]
    names = [p for _, _, p in listed]
    files = sorted(rel(p) for p in (ROOT / d).rglob('*') if p.is_file() and p.name != OUTPUTS_LIST)
    if names != files:
        probs.append(f'listed {len(names)} files, the directory holds {len(files)} besides the list '
                     f'(extra {sorted(set(names) - set(files))[:3]}, unlisted {sorted(set(files) - set(names))[:3]})')
    if any(Path(p).name.startswith('.') or p.endswith('.tmp') for p in names):
        probs.append('a temporary file is listed')
    print(f'{d}/{OUTPUTS_LIST}: {len(names)} files, problems {probs}')
    return 0 if not probs else 2


def final_check(d):
    d = rel(d)
    probs = []
    fp, finfo = first_freeze()
    probs += fp
    sums = sorted(rel(s) for s in (ROOT / d).rglob('SHA256SUMS'))
    for s in sums:
        probs += sums_problems(str(Path(s).parent), s)
    stamp = Path(d).name
    vsums = sorted(rel(s) for base in (f'{VERIFY_DIR}/{stamp}', f'{VERIFY_DIR}/{stamp}_table1_extra')
                   for s in (ROOT / base).rglob('SHA256SUMS'))
    for s in vsums:
        probs += sums_problems(str(Path(s).parent), s)
    if check_outputs_list(d):
        probs.append(f'{d}/{OUTPUTS_LIST} does not verify')
    if len(new_dirs()) != 1:
        probs.append(f'new final_* directories: {new_dirs()}')
    print(json.dumps({'first_freeze': finfo, 'sha256sums': sums + vsums, 'problems': probs}, indent=1, default=str))
    print('FINAL CHECK: OK' if not probs else 'FINAL CHECK: PROBLEM')
    return 0 if not probs else 2


# ------------------------------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('cmd', choices=('check', 'stop', 'first', 'new-dir', 'required', 'record', 'entry', 'simulate',
                                    'post', 'manifest', 'manifest-check', 'f1-ok', 'entered', 'result-entry',
                                    'resolution', 'final-check', 'next-name'))
    ap.add_argument('--expect', choices=('final', 'stopped'), default='final')
    ap.add_argument('--dir')
    ap.add_argument('--out')
    ap.add_argument('--name')
    ap.add_argument('--kind', choices=('verify', 'extra'))
    ap.add_argument('--verify-dir')
    ap.add_argument('--class-report')
    ap.add_argument('--freeze-name')
    ap.add_argument('--extra-name')
    a = ap.parse_args()
    text = protocol_text()
    if a.cmd == 'check':
        return check(a.expect)
    if a.cmd == 'stop':
        return stop()
    if a.cmd == 'first':
        probs, info = first_freeze()
        print(json.dumps({**info, 'problems': probs}, indent=1, default=str))
        print('FIRST: OK' if not probs else 'FIRST: PROBLEM')
        return 0 if not probs else 2
    if a.cmd == 'new-dir':
        nd = new_dirs()
        if len(nd) != 1:
            print(f'new final_* directories: {nd}', file=sys.stderr)
            return 1
        print(nd[0])
        return 0
    if a.cmd == 'next-name':
        print(G8.next_name(text))
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
    if a.cmd == 'manifest':
        return write_outputs_list(a.dir)
    if a.cmd == 'manifest-check':
        return check_outputs_list(a.dir)
    if a.cmd == 'f1-ok':
        ok = F1_SHA in amend_par(text, 'A11') and f1_sha() == F1_SHA
        print(f'{F1_REPORT}: ' + ('at the sha256 Amendment A11 cites' if ok else 'NOT at the sha256 Amendment A11 '
                                  f'cites ({F1_SHA[:12]})') + (' (tree copy, ROOT line restored)' if IN_TREE else ''))
        return 0 if ok else 2
    if a.cmd == 'entered':
        h = sha(a.out)
        print(f'{a.out}: sha256 {h} ' + ('cited in Sec. 13.2' if cited(h, text) else 'not cited'))
        return 0 if cited(h, text) else 1
    if a.cmd == 'final-check':
        return final_check(a.dir)
    name = a.name or G8.next_name(text)
    if a.cmd == 'entry':
        if int(name[1:]) < 18:
            sys.exit(f'amendment id {name}: the second freeze entry follows Amendment A17')
        tmpl, must, _ = freeze_entry(a.dir, name)
        return write_spec(name, tmpl, must)
    if a.cmd == 'simulate':
        return simulate(a.dir, name)
    if a.cmd == 'post':
        return post(a.dir, name)
    if a.cmd == 'result-entry':
        tmpl, must = result_entry(a.kind, name, a.verify_dir, a.dir, a.freeze_name, a.class_report)
        return write_spec(name, tmpl, must)
    if a.cmd == 'resolution':
        return resolution(name, a.verify_dir, a.class_report, a.dir, a.extra_name)
    return 2


if __name__ == '__main__':
    sys.exit(main())
