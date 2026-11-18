"""Interim-look guard of the P7 aggregator (framelease_v4/PROTOCOL.md Secs. 9.11, 9.12 and 13; GAP_AUDIT Sec. 1.5).
CPU only; reads the analysis-freeze record, PROTOCOL.md, its seal and the registration manifest; writes only the guard
log it is given (and a freeze record where aggregate_v4.py --write-freeze-record names one).

Sec. 9.11: no test-route result is examined before the analysis freeze, except infrastructure monitoring (job health,
timing, disk), and such reads are never summarized across arms. The aggregator therefore
  * takes the test routes from the registered split (outputs/framelease_v4/protocol/route_split.json, its sha256
    checked against the registration manifest; a caller may add routes, never remove one: test_routes) and keeps a row
    health-only (job health, prefix timing, the health and configuration checks, no outcome metric) when its job line
    names a test route, when the job line does not declare a training route, or when the selected run recorded a test
    route;
  * lifts that restriction only for the job lines a VALID analysis-freeze record covers (release);
  * withholds the R-2 commit audit (H5 is a registered outcome, Sec. 9.5) of every run directory of a guarded row the
    freeze did not release, and of every run directory whose config.json records a test route (or, for a run that
    matches no job line, cannot be read) (release_run): such a run is not audited, carries no count and is left out of
    the audit totals; it is released together with its row;
  * refuses (GuardRefused; aggregate_v4.py exit 4) an invalid record and any cross-arm summary that includes test
    routes before the freeze (summary_refusal), and logs every such request, granted or refused, in the guard log
    (JSON lines, interim_guard.jsonl in the output directory: log_request). The guard state (record, its sha256,
    whether it is the registered PROTOCOL.md that cites it, the rows released and withheld) is part of aggregate.json
    (guard_document) and every guarded row carries its guard_note, so no path lifts the guard silently.
A record cited only by a development copy of PROTOCOL.md (registered False: any copy and seal a caller writes; tests)
never releases a route of the registered split: it releases only rows (and run audits) whose job-line route and
recorded run route are extra routes a caller added (test_routes), and summary_rows refuses a test / all summary under it
over any row of a registered test route. Only the registered PROTOCOL.md and its seal release registered test routes.

Development data (a deviation from PROTOCOL Sec. 9.12, which says the analysis code is 'written and tested on
synthetic CSVs only'; GAP_AUDIT Sec. 1.5 allows development on P1/P2 training-route runs): the unit tests use synthetic
run directories only; in addition the builder ran read-only smoke aggregations of the real P1 training-route runs
(queue_p1, smoke_p1_0, tuning/ref) into outputs/framelease_v4/build/AGG/. No test-route run existed or was read. The
PROTOCOL wins: this deviation is to be recorded in the Sec. 13 entry of the analysis code.

Analysis-freeze record (schema framelease_v4.analysis_freeze/1; built by freeze_record from an aggregation of the
P4-P6 job files, written by aggregate_v4.py --write-freeze-record, entered by its sha256 as a dated Sec. 13 entry):
  frozen          the time of the freeze (Sec. 9.12: 'the time and the job status are recorded')
  trigger         'all_final' (every registered job of tiers 3-6 is final) or 'cut' (a cut recorded as an amendment,
                  Sec. 10.2; cut_amendment names it; the jobs it removed never started and carry the outcome 'cut')
  job_files       {job file: sha256}
  jobs            {job id: {'job_file', 'outcome' (ok, agent_crashed, sim_failure or cut), 'run_dir'}}, every job
                  line of those files
  analysis_code   {path: sha256} of the aggregator and its sibling modules (Sec. 9.12: frozen before the analysis)
  route_split_sha256  the registered split the record was made with
A record is valid (load_freeze) when its fields are as above, its sha256 is cited in Sec. 13 of PROTOCOL.md,
PROTOCOL.md equals its seal (outputs/framelease_v4/registration/SEAL.sha256), the analysis code and the route split
it names equal the files on disk and, when the job files of the test freeze are given (required_job_files: {job file:
sha256}, the registered tier 3-6 job files the test freeze enters in Sec. 13, Sec. 8.1; aggregate_v4.py
--required-job-files), it lists each of them with that sha256. A valid record releases the row of a job line when the
job file's sha256 equals the record's, the job is in the record, and its current outcome and selected run equal the
recorded ones (and, for a development record, the routes are outside the registered split); every other guarded row
stays health-only and its guard_note says why.
"""
from __future__ import annotations

import getpass
import json
import os
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v4.arms import metrics_v4 as MV  # noqa: E402
from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402
from framelease_v4.protocol import registration as REG  # noqa: E402

FREEZE_SCHEMA = 'framelease_v4.analysis_freeze/1'
LOG_SCHEMA = 'framelease_v4.interim_guard_log/1'
LOG_NAME = 'interim_guard.jsonl'
TRIGGERS = ('all_final', 'cut')
FINAL_OUTCOMES = ('ok', 'agent_crashed', 'sim_failure')    # select_stage.job_outcome outcomes with a final record
CUT = 'cut'
SUMMARY_SPLITS = ('training', 'test', 'all')               # aggregate_v4.py --arm-summary
ANALYSIS_MODULES = ('aggregate_v4.py', 'extra_metrics.py', 'commit_audit.py', 'manipulation.py', 'interim_guard.py')
RULE = ('PROTOCOL Sec. 9.11: no test-route result is examined before the analysis freeze, except job health, timing '
        'and disk; such reads are never summarized across arms')
RELEASED = 'released'                                      # the first word of a released row's guard_note


class GuardRefused(PermissionError):
    """A request the Sec. 9.11 guard refuses: an invalid analysis-freeze record, a changed route split, a cross-arm
    summary of test routes before the analysis freeze, a test-route row with outcome metrics but no release."""


# ============================================================================================ test routes, code

def analysis_code():
    """{path: sha256} of the aggregator and its sibling modules (ANALYSIS_MODULES), the code an analysis-freeze record
    freezes (Sec. 9.12)."""
    here = Path(__file__).resolve().parent
    return {PJ.rel(here / n): PJ.sha256_file(here / n) for n in ANALYSIS_MODULES}


def registered_split(split=PJ.ROUTE_SPLIT, manifest=REG.MANIFEST):
    """{'path', 'sha256', 'manifest', 'manifest_sha256', 'test': {route ids}} of the registered route split;
    GuardRefused when the file differs from its registration manifest entry (the test-route set itself could no longer
    be trusted)."""
    path = PJ.rel(split)
    sha = PJ.sha256_file(split)
    want = REG.read_manifest(manifest).get(path)
    if want != sha:
        raise GuardRefused(f'{path} (sha256 {sha}) differs from its registration manifest entry {want}: the test-route '
                           'set of the guard cannot be trusted')
    doc = json.loads(Path(split).read_text(encoding='utf-8'))
    return {'path': path, 'sha256': sha, 'manifest': PJ.rel(manifest), 'manifest_sha256': PJ.sha256_file(manifest),
            'test': {str(r['route_id']) for r in doc['test']}}


def test_routes(extra=(), split=None):
    """(test route ids, {'path', 'sha256', 'manifest', 'manifest_sha256', 'n_registered', 'n_extra'}): the registered
    test routes (registered_split or the given one) plus any extra routes a caller adds (tests); no caller can remove a
    registered test route."""
    split = registered_split() if split is None else split
    routes = set(split['test']) | {str(r) for r in extra}
    return routes, {'path': split['path'], 'sha256': split['sha256'], 'manifest': split.get('manifest'),
                    'manifest_sha256': split.get('manifest_sha256'), 'n_registered': len(split['test']),
                    'n_extra': len(routes) - len(split['test'])}


def recorded_route(run_dir, root=ROOT):
    """The route id a run directory's config.json records (a relative run_dir is under root), None when it records
    none or cannot be read."""
    if not run_dir:
        return None
    p = Path(run_dir)
    cfg = MV.read_json((p if p.is_absolute() else Path(root) / p) / 'config.json')
    route = cfg.get('route') if isinstance(cfg, dict) else None
    route = route.get('route_id') if isinstance(route, dict) else None
    return None if route is None else str(route)


# ============================================================================================ the analysis-freeze record

def protocol_sec13(text):
    """The text of Sec. 13 'Registration and amendments' of PROTOCOL.md (its heading to the next level-2 heading)."""
    i = text.find('\n## 13.')
    if i < 0:
        return ''
    j = text.find('\n## ', i + 1)
    return text[i:j if j >= 0 else len(text)]


def sealed_sha256(seal, path):
    """The sha256 the seal file (registration SEAL.sha256 format: 'sha256  path' per line, paths relative to the
    project root) records for path, None if it records none."""
    if not Path(seal).is_file():
        return None
    want = Path(path).resolve()
    for line in Path(seal).read_text(encoding='utf-8').splitlines():
        sha, _, rel = line.partition('  ')
        p = Path(rel) if Path(rel).is_absolute() else ROOT / rel
        if rel and p.resolve() == want:
            return sha
    return None


def coverage_problems(files, required):
    """[problems] of a record's job files ({job file: sha256}) against the job files it must cover (required: {job
    file: sha256}, the registered tier 3-6 job files of the test freeze, Sec. 8.1): each listed, with that sha256."""
    missing = sorted(f for f in required if f not in files)
    differ = sorted(f for f in required if f in files and files[f] != required[f])
    out = []
    if missing:
        out.append(f'{len(missing)} registered job files of the test freeze are not in the record: {missing[:5]}')
    if differ:
        out.append(f'{len(differ)} job files differ from the test freeze\'s sha256: {differ[:5]}')
    return out


def record_problems(doc, code=None, split_sha256=None, required_job_files=None):
    """[problems] of a record's content: schema and fields (module docstring), every job final (or cut, under a cut),
    the analysis code equal to code (default: the files on disk), the route split equal to split_sha256 (default:
    the registered split) and, when required_job_files ({job file: sha256}) is given, every such job file covered
    (coverage_problems)."""
    if not isinstance(doc, dict) or doc.get('schema') != FREEZE_SCHEMA:
        return [f'not an analysis-freeze record (schema {FREEZE_SCHEMA})']
    probs = []
    if not doc.get('frozen'):
        probs.append('no freeze time')
    trig = doc.get('trigger')
    if trig not in TRIGGERS:
        probs.append(f'trigger {trig!r} not in {TRIGGERS}')
    if trig == CUT and not doc.get('cut_amendment'):
        probs.append('a cut without the amendment that records it (Sec. 10.2)')
    files, jobs = doc.get('job_files'), doc.get('jobs')
    if not isinstance(files, dict) or not files:
        probs.append('no job files')
        files = {}
    if not isinstance(jobs, dict) or not jobs:
        probs.append('no jobs')
        jobs = {}
    allowed = FINAL_OUTCOMES + ((CUT,) if trig == CUT else ())
    not_final = sorted(j for j, v in jobs.items() if not isinstance(v, dict) or v.get('outcome') not in allowed)
    if not_final:
        probs.append(f'{len(not_final)} jobs without a final outcome in {allowed}: {not_final[:5]}')
    stray = sorted(j for j, v in jobs.items() if isinstance(v, dict) and v.get('job_file') not in files)
    if stray:
        probs.append(f'{len(stray)} jobs of job files the record does not list: {stray[:5]}')
    code = analysis_code() if code is None else code
    rec_code = doc.get('analysis_code') if isinstance(doc.get('analysis_code'), dict) else {}
    differ = sorted(p for p in code if rec_code.get(p) != code[p])
    if differ:
        probs.append(f'the analysis code differs from the frozen code (Sec. 9.12): {differ}')
    split_sha256 = registered_split()['sha256'] if split_sha256 is None else split_sha256
    if doc.get('route_split_sha256') != split_sha256:
        probs.append(f'route split sha256 {doc.get("route_split_sha256")} != {split_sha256}')
    if required_job_files is not None:
        probs += coverage_problems(files, required_job_files)
    return probs


def load_freeze(path, protocol=REG.PROTOCOL, seal=REG.SEAL, code=None, required_job_files=None):
    """The guard's view of a VALID analysis-freeze record: {'path', 'sha256', 'doc', 'frozen', 'trigger',
    'cut_amendment', 'protocol', 'protocol_sha256', 'seal', 'registered', 'required_job_files'} (registered: the record
    is cited by the registered PROTOCOL.md and seal, not by a development copy; required_job_files: the job files of
    the test freeze the record was checked to cover, None when no such list was given). GuardRefused, naming every
    problem, otherwise."""
    path, protocol, seal = Path(path), Path(protocol), Path(seal)
    if not path.is_file():
        raise GuardRefused(f'{PJ.rel(path)}: no analysis-freeze record there')
    sha = PJ.sha256_file(path)
    if required_job_files is not None and not isinstance(required_job_files, dict):
        raise GuardRefused('the job files the record must cover are not a {job file: sha256} object')
    try:
        doc = json.loads(path.read_text(encoding='utf-8'))
    except ValueError as e:
        doc, probs = None, [f'not JSON ({e})']
    else:
        probs = record_problems(doc, code, required_job_files=required_job_files)
    p_sha = PJ.sha256_file(protocol) if protocol.is_file() else None
    if p_sha is None or sha not in protocol_sec13(protocol.read_text(encoding='utf-8')):
        probs.append(f'its sha256 is not cited in Sec. 13 of {PJ.rel(protocol)}')
    if p_sha is None or sealed_sha256(seal, protocol) != p_sha:
        probs.append(f'{PJ.rel(protocol)} does not equal its seal {PJ.rel(seal)} (re-seal after the Sec. 13 entry)')
    if probs:
        raise GuardRefused(f'analysis-freeze record {PJ.rel(path)} (sha256 {sha}) is not valid: ' + '; '.join(probs))
    return {'path': PJ.rel(path), 'sha256': sha, 'doc': doc, 'frozen': doc['frozen'], 'trigger': doc['trigger'],
            'cut_amendment': doc.get('cut_amendment'), 'protocol': PJ.rel(protocol), 'protocol_sha256': p_sha,
            'seal': PJ.rel(seal),
            'registered': protocol.resolve() == REG.PROTOCOL.resolve() and seal.resolve() == REG.SEAL.resolve(),
            'required_job_files': None if required_job_files is None else dict(sorted(required_job_files.items()))}


def freeze_record(rows, job_files, cut_amendment=None, created=None, split_sha256=None):
    """The analysis-freeze record (module docstring) of an aggregation: rows of aggregate_v4.aggregate over the P4-P6
    job files, job_files {job file: sha256} of those files (aggregate.json job_files). Under a cut (cut_amendment) a
    job that never started (missing_reason not_launched) is recorded as 'cut'. ValueError while any job is not final
    (pending, running, a selection error): the freeze waits for them (Sec. 9.12). The record is not valid until its
    sha256 is entered in Sec. 13 of PROTOCOL.md and PROTOCOL.md is re-sealed."""
    jobs, open_ = {}, []
    for r in rows:
        if r['outcome'] in FINAL_OUTCOMES:
            jobs[r['job']] = {'job_file': r['job_file'], 'outcome': r['outcome'], 'run_dir': r.get('selected_run')}
        elif cut_amendment and r.get('missing_reason') == 'not_launched':
            jobs[r['job']] = {'job_file': r['job_file'], 'outcome': CUT, 'run_dir': None}
        else:
            open_.append(f'{r["job"]} ({r.get("missing_reason") or r["outcome"]})')
    if open_:
        raise ValueError(f'{len(open_)} job lines are not final: {open_[:10]}')
    if not jobs:
        raise ValueError('no job lines')
    files = sorted({r['job_file'] for r in rows})
    missing = [f for f in files if f not in job_files]
    if missing:
        raise ValueError(f'no sha256 for the job files {missing}')
    return {'schema': FREEZE_SCHEMA, 'frozen': created or time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'trigger': CUT if cut_amendment else 'all_final', 'cut_amendment': cut_amendment,
            'job_files': {f: job_files[f] for f in files}, 'jobs': dict(sorted(jobs.items())),
            'analysis_code': analysis_code(),
            'route_split_sha256': registered_split()['sha256'] if split_sha256 is None else split_sha256}


# ============================================================================================ rows

DEV_WITHHELD = 'withheld: a development record never releases a registered test route'


def release(freeze, job, job_file, job_file_sha256, outcome, registered=None, root=ROOT):
    """(released, guard_note) of a guarded job line (one whose row is health-only before the freeze): job_file and its
    sha256 as aggregate_v4 read them, outcome its select_stage outcome now. A development record (registered False:
    cited by a development copy of PROTOCOL.md) releases only rows whose job-line route and recorded run route
    (recorded_route of the outcome's run; unreadable: withheld) are outside the registered split (registered: its test
    route ids, default registered_split()), i.e. extra routes a caller added. Notes start with 'pre_freeze',
    'withheld' or 'released'."""
    if freeze is None:
        return False, 'pre_freeze: no valid analysis-freeze record (Sec. 9.11)'
    doc = freeze['doc']
    rec_sha = doc['job_files'].get(job_file)
    if rec_sha is None:
        return False, f'withheld: job file {job_file} is not in the analysis-freeze record'
    if rec_sha != job_file_sha256:
        return False, f'withheld: job file {job_file} changed since the freeze (sha256 {job_file_sha256} != {rec_sha})'
    rec = doc['jobs'].get(job['id'])
    if rec is None or rec.get('job_file') != job_file:
        return False, 'withheld: the job is not in the analysis-freeze record'
    want = ('pending', None) if rec['outcome'] == CUT else (rec['outcome'], rec.get('run_dir'))
    got = (outcome.get('outcome'), outcome.get('run_dir'))
    if got != want:
        return False, f'withheld: outcome / run {got} differs from the record\'s {want}'
    if not freeze.get('registered'):
        reg = registered_split()['test'] if registered is None else {str(r) for r in registered}
        run_dir = outcome.get('run_dir')
        run_route = recorded_route(run_dir, root)
        if str(job.get('route_id')) in reg or (run_dir and (run_route is None or run_route in reg)):
            return False, DEV_WITHHELD
    dev = '' if freeze.get('registered') else ' (DEVELOPMENT record: not cited by the registered PROTOCOL.md)'
    return True, f'{RELEASED}: by the analysis-freeze record {freeze["sha256"][:12]}{dev}'


def release_run(freeze, run_route, test_routes, registered=None):
    """(released, guard_note) of the R-2 commit audit of one run directory (aggregate_v4.commit_audit) by the route its
    config.json records (None: unreadable), after the rows of the job lines it belongs to were released (a guarded
    row the freeze did not release withholds its runs before this is asked). Not guarded (True, None) on a route
    outside test_routes; a test route or an unreadable route is withheld before the freeze, released by a registered
    analysis-freeze record (every test-route result may be examined after it) and, by a development record, only on a
    route outside the registered split (registered, default registered_split())."""
    route = None if run_route is None else str(run_route)
    if route is not None and route not in test_routes:
        return True, None
    if freeze is None:
        what = 'its route is unreadable' if route is None else f'it recorded the test route {route}'
        return False, f'pre_freeze: a run directory whose audit is withheld, {what} (Sec. 9.11)'
    if freeze.get('registered'):
        return True, f'{RELEASED}: by the analysis-freeze record {freeze["sha256"][:12]}'
    reg = registered_split()['test'] if registered is None else {str(r) for r in registered}
    if route is None or route in reg:
        return False, DEV_WITHHELD
    return True, (f'{RELEASED}: by the analysis-freeze record {freeze["sha256"][:12]} (DEVELOPMENT record: not cited '
                  'by the registered PROTOCOL.md)')


def note_category(note):
    """'pre_freeze', 'withheld' or 'released' of a guard_note (None for an unguarded row)."""
    return None if not note else note.split(':', 1)[0]


def guard_document(rows, freeze, routes_info, summary=None):
    """The 'interim_guard' entry of aggregate.json: status (pre_freeze, frozen, or frozen_development for a record cited
    by a development copy of PROTOCOL.md), the record, the test-route set, the guarded / released / health-only row
    counts, the withheld rows of a frozen aggregation and the summary request (summary_refusal)."""
    guarded = [r for r in rows if r.get('guard_note')]
    cats = {}
    for r in guarded:
        c = note_category(r['guard_note'])
        cats[c] = cats.get(c, 0) + 1
    keys = ('path', 'sha256', 'frozen', 'trigger', 'cut_amendment', 'protocol', 'protocol_sha256', 'seal', 'registered',
            'required_job_files')
    return {'status': 'pre_freeze' if freeze is None else 'frozen' if freeze['registered'] else 'frozen_development',
            'rule': RULE, 'freeze': None if freeze is None else {k: freeze.get(k) for k in keys},
            'test_routes': routes_info, 'guarded_rows': len(guarded),
            'test_route_rows': sum(1 for r in rows if r.get('test_route')),
            'released_rows': cats.get(RELEASED, 0), 'health_only_rows': sum(1 for r in rows if r.get('health_only')),
            'notes': dict(sorted(cats.items())),
            'withheld': [{'job': r['job'], 'note': r['guard_note']} for r in guarded
                         if note_category(r['guard_note']) == 'withheld'],
            'summary': summary}


# ============================================================================================ summaries and the log

def summary_refusal(split, freeze):
    """None if a cross-arm summary of split ('training', 'test', 'all') is allowed, else the reason it is refused:
    training routes are examined by design (Sec. 9.11, Phase 1, D1, Phase 3); a summary with test routes needs a valid
    analysis-freeze record."""
    if split not in SUMMARY_SPLITS:
        raise ValueError(f'summary split {split!r} not in {SUMMARY_SPLITS}')
    if split != 'training' and freeze is None:
        return (f'a cross-arm summary of test routes ({split}) before the analysis freeze: no valid analysis-freeze '
                f'record ({RULE})')
    return None


def summary_rows(rows, split, freeze, registered=None):
    """The rows a cross-arm summary of split may use (analysis_use rows: declared training routes for 'training',
    released test-route rows for 'test', both for 'all'). GuardRefused when summary_refusal refuses, when a row that
    would enter the summary is a test-route row without a release (rows that were not made by the guard), and when a
    development record (registered False) is asked for a test / all summary of rows of which any is on a route of the
    registered split (registered: its test route ids, default registered_split()), released or not."""
    reason = summary_refusal(split, freeze)
    if reason:
        raise GuardRefused(reason)
    if split != 'training' and not freeze.get('registered'):
        reg = registered_split()['test'] if registered is None else {str(r) for r in registered}
        hit = sorted({str(r.get('route_id')) for r in rows} & reg)
        if hit:
            raise GuardRefused(f'a {split} summary with a development analysis-freeze record over rows of the registered '
                               f'test routes {hit[:5]}: a development record never summarizes a registered test route '
                               f'({RULE})')
    out = []
    for r in rows:
        if not r.get('analysis_use'):
            continue
        cat = note_category(r.get('guard_note'))
        if (r.get('test_route') or cat is not None) and cat != RELEASED:
            raise GuardRefused(f'row {r.get("job")}: a guarded row (test route {r.get("test_route")}, guard note '
                               f'{r.get("guard_note")!r}) with analysis_use and no release; refusing the summary')
        if (cat is None and split in ('training', 'all')) or (cat == RELEASED and split in ('test', 'all')):
            out.append(r)
    return out


def log_request(log_path, request, decision, reason=None, freeze=None, argv=None, **extra):
    """Append one entry (schema LOG_SCHEMA: time, user, host, pid, argv, request, decision granted / refused, reason,
    the record's path and sha256) to the guard log (JSON lines, created with its directory) and return it. The file
    is flushed and synced before the request is served or refused."""
    entry = {'schema': LOG_SCHEMA, 'time': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'user': getpass.getuser(),
             'host': socket.gethostname(), 'pid': os.getpid(), 'argv': list(sys.argv if argv is None else argv),
             'request': request, 'decision': decision, 'reason': reason,
             'freeze': None if freeze is None else {'path': freeze['path'], 'sha256': freeze['sha256'],
                                                    'registered': freeze['registered']}, **extra}
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, sort_keys=True, default=str) + '\n')
        f.flush()
        os.fsync(f.fileno())
    return entry


def log_state(log_path):
    """{'path', 'sha256', 'entries', 'refused'} of the guard log (None without one): aggregate.json records it."""
    path = Path(log_path)
    if not path.is_file():
        return None
    entries = MV.read_jsonl(path)
    return {'path': PJ.rel(path), 'sha256': PJ.sha256_file(path), 'entries': len(entries),
            'refused': sum(1 for e in entries if e.get('decision') == 'refused')}


__all__ = ['FREEZE_SCHEMA', 'LOG_SCHEMA', 'LOG_NAME', 'TRIGGERS', 'FINAL_OUTCOMES', 'CUT', 'SUMMARY_SPLITS',
           'ANALYSIS_MODULES', 'RULE', 'RELEASED', 'DEV_WITHHELD', 'GuardRefused', 'analysis_code', 'registered_split',
           'test_routes', 'recorded_route', 'protocol_sec13', 'sealed_sha256', 'coverage_problems', 'record_problems',
           'load_freeze', 'freeze_record', 'release', 'release_run', 'note_category', 'guard_document',
           'summary_refusal', 'summary_rows', 'log_request', 'log_state']
