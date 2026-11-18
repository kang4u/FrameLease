#!/usr/bin/env python3
"""The test freeze of framelease_v4/PROTOCOL.md (Secs. 3.3 rule 4, 5.9, 7.6, 8.1, 8.3, 9.11, 13.2; GAP_AUDIT Sec. 3.5
rows G-2 and G-3). CPU only: it never starts a job, CARLA or the GPU, never enqueues a job file and never reads a
test-route result (Sec. 9.11: the test-route guard asks only whether a run directory or a queue status record exists).

  cd /home/kang/Desktop/DAC
  PY=".conda-unidrive-linux/bin/python -I -B"
  $PY framelease_v4/protocol/test_freeze.py              # check every input, print what the freeze records
  $PY framelease_v4/protocol/test_freeze.py --write      # check, write the record and its manifest, print the entry
  $PY framelease_v4/protocol/test_freeze.py --entry      # print the Sec. 13.2 entry of the written record again
  $PY framelease_v4/protocol/test_freeze.py --verify     # after the entry and the seal: the freeze holds
While a runner is active, prefix every command with "nice -n 19 ionice -c 3" (GAP_AUDIT Sec. 1.4).

What the freeze records (GAP_AUDIT G-2), each input checked first:
  * the tuning freeze outputs/framelease_v4/tuning/selection.json through test_jobs.load_tuning (the P2 gate
    p2_jobs.load_freeze plus A*, theta* / A_hb* and the fl_risk lease point against their registered grids): its
    sha256 cited in PROTOCOL Sec. 13.2 (Sec. 4.9), PROTOCOL.md the sealed version, and every stage selection it names
    at its sha256 and cited there as well (Sec. 4.2);
  * the RL freeze outputs/framelease_v4/rl_freeze/rl_freeze.json through test_jobs.load_rl (p3_rl.load_rl_freeze: a
    frozen production record, every named file and source log at its sha256, every network loadable at its name, file
    sha256, arm, a_det depth and absolute path; made from this tuning freeze), with every file it names (the P2 data
    manifest, the RL dataset, the reports of every stage, the networks: p3_rl.freeze_files), its deviations and its
    implementation notes (p3_rl.SEC13_NOTES). It is entered in Sec. 13 by this freeze (Secs. 5.9, 8.1), and so is the
    P2 data manifest when Sec. 13.2 does not cite it yet;
  * every P4-P6 job file, block spec and check (test_jobs.py --check --write, outputs/framelease_v4/test_jobs/FULL/):
    index.json names every block of test_jobs.BLOCKS in order with the sha256 of its three files (the skipped s_risk
    block with its reason and no file); each job file is byte-identical to what test_jobs.build_all generates now from
    the same two freezes, each block spec equal to the regenerated one, each check clean (no problem, every line ok
    with a NOT_STARTED --dry-run through its launcher, the ids of the job file, made by the test_jobs.py and the
    checking modules of the tree now); the static checks (test_jobs.static_problems, cross_block_problems) pass again
    on the lines read;
  * every pin: the union of require_sha256 over the P4-P6 lines (registration.job_pins: a path pinned with two
    sha256 is refused), each file at its pinned sha256 now (gpu_queue.pin_mismatches);
  * the registered S1-S3 reports of framelease_v4/protocol/stress_bench.py (Sec. 7.6; --stress S<k>=PATH, by default
    the one outputs/framelease_v4/stress/s<k>_registered_*.json per test): labelled registered, made by the code of
    the tree now, run on the deployed networks of the RL freeze (S1 and S2; S1 with the L* envelope and the loads
    0 / 4 / 8 / 15); S3 with >= 1e5 sequences on both targets, full fault coverage and 0 violations; S2 with 0
    admitted actions whose bound reaches D* and 0 violations (Sec. 7.6: "must be 0");
  * the code of the freeze and of the generators (CODE_FILES) at its sha256;
  * the registered inputs of the generator, route_split.json, its source routes.json and the envelope manifest
    (test_jobs.REGISTERED_INPUTS), and the registered code it runs (REGISTERED_CODE), each at its sha256 of the sealed
    registration manifest (registered_inputs in the record);
  * a sha256 manifest over all of these files (GAP_AUDIT G-3, recommended option: the test freeze's own manifest,
    cited in the Sec. 13 entry and sealed with it; registration.py is not changed).
It refuses (exit 2) while any test-route run exists (test_jobs.existing_runs: a runs/ entry in an output directory of
the P4-P6 lines or under matrix/, fig3/, ablation/, replicates/, or a status record in queue_p4) and while an input
that Sec. 13.2 must already cite is uncited (the tuning freeze and its stage selections) or PROTOCOL.md is not sealed.

Outputs (--write; only under outputs/framelease_v4/test_freeze/ or --out-dir outside every queue):
  test_freeze.json   the record (schema framelease_v4.test_freeze/1): every input above with its sha256, the checks'
                     outcome, the deviations of this implementation, and the manifest's path and sha256;
  MANIFEST.sha256    sha256sum format, paths relative to the project root (absolute outside it): every file the record
                     names, except the record itself (which cites the manifest).
An existing file is kept when it is equal (the record: equal up to its 'written' time, so its sha256 stays the one
printed); a different one is refused without --force, and with --force too once PROTOCOL Sec. 13.2 cites its sha256.
Procedure. Before --write, the coordinating session runs registration.py --verify: both seal lines must read OK, and
every file the manifest line lists as differing must be one that a Sec. 13.2 entry names as not registered (Amendment
A2: the Phase 2-7 tooling in development; registration.verify() gives the full list). Any other differing file is a
registered file that changed: stop; no test freeze before an amendment restores or registers it (the rule of the P1
driver's pre-check, p1_driver.precheck_tree). build_freeze itself compares the registered inputs it reads with the
sealed registration manifest (route_split.json, routes.json, the envelope manifest and REGISTERED_CODE:
test_jobs.registered_inputs) and every pin of the P4-P6 lines except the network files and the extension sources with
the registered P1 pins (test_jobs.static_problems), so the later registration.py --write-manifest --force re-hashes no
changed input of the freeze unnoticed. After --write the script prints the text of the Sec. 13.2 entry. The
coordinating session appends it under the protocol lock (flock framelease_v4/.protocol.lock), runs registration.py
--write-manifest --force, adds the line of the new registration manifest, runs registration.py --seal and --verify, and
then test_freeze.py --verify, which passes only when Sec. 13.2 cites the record and the manifest, PROTOCOL.md is sealed,
every file of the manifest is at its sha256 and every *.jsonl in queue_p4/jobs.d/ is a frozen job file at its sha256.
Only then are the six job files copied, in name order, into outputs/framelease_v4/queue_p4/jobs.d/; --verify run again
after the copy checks the copies.
Exit codes: 0 done, 1 check failed (an input is inconsistent, a pin is not the registered one or a stress test failed;
--verify: a file changed or a queue copy differs), 2 refused (an input missing, uncited or unsealed; a registered input
or code file that differs from the sealed registration manifest; a test-route run exists; a queue path; an existing
file with other content or a recorded one).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402
from framelease_v4.protocol import p2_jobs as P2J  # noqa: E402
from framelease_v4.protocol import test_jobs as TJ  # noqa: E402

__test__ = False        # the file name matches pytest's test_*.py pattern: it is a tool, not a test module
THIS_REL = 'framelease_v4/protocol/test_freeze.py'
SCHEMA = 'framelease_v4.test_freeze/1'
OUT_DIR = ROOT / 'outputs/framelease_v4/test_freeze'
RECORD_NAME = 'test_freeze.json'
MANIFEST_NAME = 'MANIFEST.sha256'
STRESS_DIR = ROOT / 'outputs/framelease_v4/stress'          # = stress_bench.OUT_DIR
STRESS_TESTS = ('S1', 'S2', 'S3')
# the code of the freeze, of the P4-P6 generator and of the modules that checked its inputs (the 55 pins of the job
# lines are recorded separately, under 'pins')
CODE_FILES = ('framelease_v4/protocol/test_freeze.py', 'framelease_v4/protocol/test_jobs.py',
              'framelease_v4/protocol/p1_jobs.py', 'framelease_v4/protocol/p2_jobs.py',
              'framelease_v4/protocol/select_stage.py', 'framelease_v4/protocol/p3_rl.py',
              'framelease_v4/protocol/check_smoke_ext.py', 'framelease_v4/protocol/stress_bench.py',
              'framelease_v4/protocol/registration.py', 'framelease_v2/gpu_queue.py')
# the registered code among them and the registered budget tables the generator reads (PROTOCOL Secs. 10.1, 13.1):
# each must be at its sealed registration manifest entry (test_jobs.registered_inputs); p2_jobs.py, p3_rl.py,
# check_smoke_ext.py and stress_bench.py are Phase 2-7 tooling that Amendment A2 does not register, test_jobs.py and
# test_freeze.py are newer: this freeze registers them
REGISTERED_CODE = ('framelease_v4/protocol/p1_jobs.py', 'framelease_v4/protocol/select_stage.py',
                   'framelease_v4/protocol/registration.py', 'framelease_v4/protocol/make_protocol_tables.py',
                   'framelease_v2/gpu_queue.py')
# where this implementation fixes what PROTOCOL leaves open or departs from the GAP_AUDIT wording; recorded in the
# record and named in the Sec. 13.2 entry
DEVIATIONS = (
    'Test-route guard (G-2 "refuses while any test-route run exists"): a run is detected by its existence only, a '
    'runs/ entry in an output directory of the P4-P6 lines or under matrix/, fig3/, ablation/, replicates/ (Sec. 8.6), '
    'or a status record in outputs/framelease_v4/queue_p4; no result file is opened (Sec. 9.11).',
    'Stress tests: the freeze takes one registered report per test (stress_bench.py --registered) and refuses S2 or S3 '
    'with a violation (Sec. 7.6: the admitted actions with bound >= D* and the commits violating Eq. 9 "must be 0"); '
    'S1 has no pass criterion and is recorded as measured.',
    'G-3: the P4-P6 job files, the RL freeze and the test-freeze record are covered by the test freeze\'s own sha256 '
    'manifest, cited in this entry and sealed with it; registration.py is unchanged.',
    'The P2 data manifest is entered in Sec. 13.2 by this entry when no earlier entry cites it (Sec. 5.9: the dataset '
    'manifest is entered in Sec. 13 as part of the test freeze).',
    'Arm identity (GAP_AUDIT Sec. 2, "Recommended labelling"; Sec. 4.1 names no launcher arm for these arms): '
    'fl_bandit and fl_fqi_nolease run through the launcher arm fl_full with the network file of their family, fl_risk '
    'through fl_heuristic at its lease point; each such arm is the pair (launcher arm, network file sha256 or envelope '
    'sha256), recorded in the job line (protocol_arm), in the output directory (ablation/<arm>/) and in the block '
    'spec.',
)


def _abs(p):
    p = Path(p)
    return p if p.is_absolute() else ROOT / p


def _cited(sha, protocol):
    return P2J.citations(sha, Path(protocol).read_text(encoding='utf-8'))


# ---------------------------------------------------------------------------------------- the freezes

def stage_selections(doc, protocol=P2J.PROTOCOL):
    """[{'stage', 'path', 'sha256', 'cited_lines'}] of the stage selections the tuning freeze names (select_stage.freeze
    'stages'). ValueError for a file that is missing or no longer at its sha256; PermissionError for one whose sha256
    PROTOCOL Sec. 13.2 does not cite (Sec. 4.2: every selection is entered before the next job file is generated)."""
    out = []
    for stage, ref in sorted((doc.get('stages') or {}).items()):
        path, sha = _abs(ref.get('path') or ''), ref.get('sha256')
        cur = PJ.sha256_file(path) if path.is_file() else None
        if cur != sha:
            raise ValueError(f'stage selection {stage}: {ref.get("path")} has sha256 {cur}, the tuning freeze names '
                             f'{sha}')
        cited = _cited(sha, protocol)
        if not cited:
            raise PermissionError(f'stage selection {stage} ({ref.get("path")}, sha256 {sha}) is not cited in PROTOCOL '
                                  'Sec. 13.2 (Sec. 4.2); refusing a freeze built on an unrecorded selection')
        out.append({'stage': stage, 'path': PJ.rel(path), 'sha256': sha, 'cited_lines': cited})
    return out


def load_freezes(selection=None, rl_freeze=None, protocol=P2J.PROTOCOL, seal=P2J.SEAL):
    """(tuning, rl, rl_doc, stages): test_jobs.load_tuning and test_jobs.load_rl (their refusals unchanged: seal None
    skips the seal check, tests only), the RL freeze document as read and verified there (the same bytes), and the
    stage selections (stage_selections)."""
    tuning = TJ.load_tuning(selection or TJ.SS.FREEZE_PATH, protocol, seal)
    raw = _abs(tuning['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != tuning['sha256']:
        raise ValueError(f'{tuning["path"]} changed while it was read')
    stages = stage_selections(json.loads(raw.decode('utf-8')), protocol)
    rl = TJ.load_rl(tuning, rl_freeze or TJ.RL_FREEZE, protocol)
    raw = _abs(rl['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != rl['sha256']:
        raise ValueError(f'{rl["path"]} changed while it was read')
    return tuning, rl, json.loads(raw.decode('utf-8')), stages


def tuning_record(tuning, stages):
    L = tuning['L']
    return {'path': tuning['path'], 'sha256': tuning['sha256'], 'cited_lines': tuning['cited_lines'],
            'L_star': {k: L[k] for k in ('label', 'path', 'sha256')}, 'd_star': tuning['d'],
            'd_utility': tuning['d_utility'], 'A_star': tuning['A_star'], 'event_star': tuning['event'],
            'fl_risk': {'lease_point': (tuning['risk'] or {}).get('label'), 'reason': tuning['risk_reason']},
            'stage_selections': stages}


def rl_record(rl, doc, protocol=P2J.PROTOCOL):
    """The RL freeze as the test freeze records it: path, sha256, P_both, the networks per protocol arm (arm and FILE
    sha256 identify a network), the names shared by arms, the P2 data manifest with its Sec. 13.2 citations now, the
    files it names, its deviations and implementation notes."""
    p2 = doc.get('p2_manifest') or {}
    return {'path': rl['path'], 'sha256': rl['sha256'], 'cited_lines': rl['cited_lines'],
            'p_both_label': rl['p_both_label'], 'networks': rl['networks'],
            'shared_names': doc.get('shared_names') or {},
            'p2_manifest': {'path': p2.get('path'), 'sha256': p2.get('sha256'),
                            'cited_lines': _cited(p2['sha256'], protocol) if p2.get('sha256') else []},
            'n_files': len(doc.get('files') or {}), 'deviations': doc.get('deviations') or [],
            'sec13_notes': list((doc.get('sec13_notes') or {}).get('items') or [])}


# ---------------------------------------------------------------------------------------- the P4-P6 job files

SPEC_VOLATILE = ('protocol', 'tuning_freeze_cited_lines', 'rl_freeze_cited_lines')   # PROTOCOL.md state at generation


def check_record_problems(blk, chk, lines, job_sha):
    """Problems of a block's .check.json (the test_jobs.check_doc contract) against the job file read: clean, every
    line ok with a NOT_STARTED --dry-run, the job file's ids and sha256, and made by the test_jobs.py and the checking
    modules of the tree now (otherwise the check does not describe the code that runs)."""
    name, p = blk['block'], []
    if chk.get('schema') != TJ.CHECK_SCHEMA or chk.get('block') != name:
        p.append(f'{name}: the check is not a {TJ.CHECK_SCHEMA} record of this block')
        return p
    if chk.get('job_file_sha256') != job_sha or chk.get('n_lines') != len(lines):
        p.append(f'{name}: the check names another job file ({chk.get("job_file_sha256")}, {chk.get("n_lines")} lines)')
    if chk.get('problems') or chk.get('cross_block_problems'):
        p.append(f'{name}: the check lists problems: {(chk.get("problems") or chk.get("cross_block_problems"))[:3]}')
    results = chk.get('lines') or []
    if [r.get('id') for r in results] != [j.get('id') for j in lines]:
        p.append(f'{name}: the check\'s lines are not the job ids of the file, in order')
    bad = [r.get('id') for r in results if not r.get('ok') or (r.get('dry_run') or {}).get('status') != 'NOT_STARTED']
    if chk.get('all_dry_runs_ok') is not True or bad:
        p.append(f'{name}: not every line passed its checks and its --dry-run ({len(bad)} lines, e.g. {bad[:3]})')
    code = {PJ.rel(TJ.__file__): chk.get('script_sha256'), **(chk.get('reused_sha256') or {})}
    stale = [f for f, sha in sorted(code.items()) if not _abs(f).is_file() or PJ.sha256_file(_abs(f)) != sha]
    if stale:
        p.append(f'{name}: the check was made by other code than the tree\'s ({stale}): generate and check again')
    return p


def job_files_record(tuning, rl, jobs_dir=None):
    """The P4-P6 job files as test_jobs.py --check --write left them, against a regeneration from the same freezes
    (test_jobs.build_all): index.json names the blocks of test_jobs.BLOCKS in order with the sha256 of each block's
    job file, spec and check (a skipped block: its reason and no file); each job file byte-identical to the
    regeneration, each spec equal to it (up to the PROTOCOL.md state at generation, SPEC_VOLATILE), each check clean
    (check_record_problems); test_jobs.static_problems and cross_block_problems on the lines read. FileNotFoundError
    without index.json. Returns (record, {path: sha256}, lines, problems)."""
    base = Path(jobs_dir or TJ.JOBS_DIR) / TJ.VARIANT
    ipath = base / TJ.INDEX_NAME
    if not ipath.is_file():
        raise FileNotFoundError(f'{PJ.rel(ipath)}: no P4-P6 job files yet (test_jobs.py --check --write)')
    index = json.loads(ipath.read_text(encoding='utf-8'))
    files, problems = {PJ.rel(ipath): PJ.sha256_file(ipath)}, []
    built = TJ.build_all(tuning, rl)
    refs = TJ.freeze_refs(tuning, rl)
    gen = PJ.sha256_file(Path(TJ.__file__))
    entries = index.get('blocks') or []
    if index.get('schema') != TJ.INDEX_SCHEMA or [b.get('block') for b in entries] != [b['block'] for b in TJ.BLOCKS]:
        raise ValueError(f'{PJ.rel(ipath)} is not a {TJ.INDEX_SCHEMA} index of the blocks '
                         f'{[b["block"] for b in TJ.BLOCKS]}')
    if (index.get('tuning_freeze'), index.get('rl_freeze')) != (refs['tuning_freeze'], refs['rl_freeze']):
        problems.append(f'{PJ.rel(ipath)} was made from other freezes: {index.get("tuning_freeze")}, '
                        f'{index.get("rl_freeze")}')
    if index.get('cross_block_problems') or index.get('script_sha256') != gen:
        problems.append(f'{PJ.rel(ipath)}: cross-block problems or another test_jobs.py ({index.get("script_sha256")})')
    arms, cache, read, blocks = TJ.frozen_arms(tuning, rl), {}, [], []
    for (blk, lines, spec), entry in zip(built, entries):
        paths = TJ.block_paths(blk, jobs_dir)
        row = {'block': blk['block'], 'no': blk['no'], 'tier': blk['tier'], 'phase': blk['phase'],
               'budget_block': blk['budget'], 'n_lines': len(lines), 'skipped': spec['skipped']}
        if not lines:
            if entry.get('n_lines') != 0 or entry.get('skipped') != spec['skipped'] or any(p.exists() for p in paths):
                problems.append(f'{blk["block"]}: skipped now ({spec["skipped"]}), but index.json lists {entry} or its '
                                'files exist')
            read.append((blk, [], spec))
            blocks.append(row)
            continue
        missing = [PJ.rel(p) for p in paths if not p.is_file()]
        if missing:
            problems.append(f'{blk["block"]}: {missing} missing')
            read.append((blk, [], spec))
            continue
        text = paths[0].read_text(encoding='utf-8')
        shas = [PJ.sha256_file(p) for p in paths]
        listed = [entry.get(k) for k in ('job_file', 'stage_spec', 'check', 'n_lines', 'skipped')]
        if [entry.get(k) for k in ('job_file_sha256', 'stage_spec_sha256', 'check_sha256')] != shas \
                or listed != [*(PJ.rel(p) for p in paths), len(text.splitlines()), None]:
            problems.append(f'{blk["block"]}: the files differ from index.json (sha256, paths or line count)')
        if text != P2J.jsonl(lines):
            problems.append(f'{blk["block"]}: {PJ.rel(paths[0])} is not the job file test_jobs.py generates from these '
                            'freezes now')
        got = [json.loads(x) for x in text.splitlines()]
        doc = json.loads(paths[1].read_text(encoding='utf-8'))
        want = {**spec, 'job_file': PJ.rel(paths[0]), 'job_file_sha256': shas[0]}
        if {k: v for k, v in doc.items() if k not in SPEC_VOLATILE} \
                != {k: v for k, v in want.items() if k not in SPEC_VOLATILE}:
            problems.append(f'{blk["block"]}: {PJ.rel(paths[1])} is not the block spec of the job file')
        problems += check_record_problems(blk, json.loads(paths[2].read_text(encoding='utf-8')), got, shas[0])
        problems += TJ.static_problems(blk, got, arms, tuning, rl, cache)
        files.update(zip((PJ.rel(p) for p in paths), shas))
        read.append((blk, got, doc))
        blocks.append({**row, 'n_lines': len(got), 'expected_runs_sec_10_1': spec['expected_runs_sec_10_1'],
                       'job_file': PJ.rel(paths[0]), 'job_file_sha256': shas[0], 'stage_spec': PJ.rel(paths[1]),
                       'stage_spec_sha256': shas[1], 'check': PJ.rel(paths[2]), 'check_sha256': shas[2],
                       'protocol_arms': list(blk['arms']), 'route_set': blk['routes'], 'kappas': list(blk['kappas']),
                       'seed': blk['seed']})
    problems += TJ.cross_block_problems(read)
    lines = [j for _, got, _ in read for j in got]
    if index.get('n_lines') != len(lines):
        problems.append(f'{PJ.rel(ipath)}: n_lines {index.get("n_lines")} != the {len(lines)} lines of the job files')
    rec = {'dir': PJ.rel(base), 'index': {'path': PJ.rel(ipath), 'sha256': files[PJ.rel(ipath)]}, 'blocks': blocks,
           'n_lines': len(lines), 'expected_runs_sec_10_1': sum(b.get('expected_runs_sec_10_1', 0) for b in blocks),
           'generator': {'path': PJ.rel(TJ.__file__), 'sha256': gen}, 'queue': TJ.QUEUE_REL,
           'enqueue': index.get('enqueue'), 'not_for_launch_before': TJ.NOT_BEFORE,
           'pin_sets': {a['protocol_arm']: {'n': len(TJ.arm_pins(a, cache)),
                                            'sha256': PJ.sha256_text(json.dumps(TJ.arm_pins(a, cache), sort_keys=True))}
                        for a in arms.values()}}
    return rec, files, lines, problems


# ---------------------------------------------------------------------------------------- pins and stress tests

def pins_record(job_files):
    """{'n', 'files': {path: sha256}, 'mismatches'}: the union of require_sha256 over the P4-P6 job files
    (registration.job_pins: a path pinned with two sha256 is a ValueError) and the pinned files that differ from the
    tree now (gpu_queue.pin_mismatches)."""
    from framelease_v2 import gpu_queue as GQ
    from framelease_v4.protocol import registration as REG
    pins = REG.job_pins(tuple(job_files))
    return {'n': len(pins), 'files': pins, 'mismatches': GQ.pin_mismatches(pins)}


def stress_paths(given=(), stress_dir=STRESS_DIR):
    """{test: path} of S1-S3: --stress S<k>=PATH, else the one registered report of the test in stress_dir
    (s<k>_registered_<UTC>.json, as stress_bench.py --registered names it). FileNotFoundError for none, ValueError for
    several (name one) or a malformed --stress."""
    out = {}
    for item in given or ():
        test, _, path = str(item).partition('=')
        if test not in STRESS_TESTS or not path or test in out:
            raise ValueError(f'--stress {item!r}: one S1=PATH, S2=PATH or S3=PATH per test')
        out[test] = Path(path)
    for test in STRESS_TESTS:
        if test in out:
            continue
        found = sorted(Path(stress_dir).glob(f'{test.lower()}_registered_*.json'))
        if not found:
            raise FileNotFoundError(f'no registered {test} report in {PJ.rel(stress_dir)} (stress_bench.py '
                                    f'{test.lower()} --registered, PROTOCOL Sec. 7.6: before the test freeze)')
        if len(found) > 1:
            raise ValueError(f'{len(found)} registered {test} reports in {PJ.rel(stress_dir)}: name one with --stress '
                             f'{test}=PATH')
        out[test] = found[0]
    return out


def stress_check(test, path, tuning, rl):
    """(summary, problems) of one stress_bench report (Sec. 7.6). Every test: schema and test, a registered run, made by
    the code of the tree now (provenance.code_sha256). S1 and S2: the deployed networks of the RL freeze, each name
    with one of its files (two arms with one decision core share a name, p3_rl.JOB_LINES_RULE). S1: the loads 0 / 4 /
    8 / 15, the lease on the L* envelope, an exclusive CPU. S2: the 71 slack values, 0 admitted actions with bound >=
    D*, 0 violations, replay fidelity where states are recorded. S3: >= 1e5 sequences on the gate and the runtime, the
    fault coverage, 0 violations. ValueError for a file that is no stress report of the test."""
    from framelease_v4.protocol import stress_bench as SB
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f'{PJ.rel(path)}: no {test} report')
    raw = path.read_bytes()
    doc = json.loads(raw.decode('utf-8'))
    if not isinstance(doc, dict) or (doc.get('schema'), doc.get('test')) != (SB.SCHEMA, test):
        raise ValueError(f'{PJ.rel(path)} is not a {test} report (schema {SB.SCHEMA})')
    code = (doc.get('provenance') or {}).get('code_sha256') or {}
    summ = {'test': test, 'path': PJ.rel(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'label': doc.get('label'),
            'registered': doc.get('registered'), 'code_sha256': code}
    p = []
    if doc.get('registered') is not True or doc.get('label') != SB.label_for(test, True):
        p.append(f'{test}: {summ["path"]} is not a registered run ({doc.get("label")!r})')
    stale = [f for f, h in sorted(code.items()) if not _abs(f).is_file() or PJ.sha256_file(_abs(f)) != h]
    if not code or stale:
        p.append(f'{test}: {summ["path"]} was made by other code than the tree\'s ({stale or "no code_sha256"})')
    names = {}
    for net in rl['networks'].values():
        names.setdefault(net['name'], set()).add(net['sha256'])

    def networks_problems(tested):
        if set(tested) != set(names) or any(tested[n] not in names[n] for n in tested):
            return [f'{test}: the networks {tested} are not the deployed networks of the RL freeze '
                    f'{ {n: sorted(s) for n, s in names.items()} }']
        return []

    if test == 'S3':
        targets = sorted(doc.get('targets') or {})
        summ.update(n_sequences=doc.get('n_sequences'), targets=targets, coverage_ok=doc.get('coverage_ok'),
                    violations_total=doc.get('violations_total'), passed=doc.get('pass'))
        if not isinstance(doc.get('n_sequences'), int) or doc['n_sequences'] < SB.S3_MIN_SEQUENCES \
                or targets != ['gate', 'runtime']:
            p.append(f'S3: {doc.get("n_sequences")} sequences on {targets}; Sec. 7.6 asks >= {SB.S3_MIN_SEQUENCES} on '
                     'the commit gate and the runtime')
        if doc.get('pass') is not True or doc.get('violations_total') != 0 or doc.get('coverage_ok') is not True:
            p.append(f'S3: {doc.get("violations_total")} commits violate Eq. 9 (must be 0) or a fault class is not '
                     f'covered (coverage_ok {doc.get("coverage_ok")})')
    elif test == 'S2':
        nets = doc.get('networks') or {}
        summ.update(n_states=doc.get('n_states'), n_swept=doc.get('n_swept'), states=doc.get('states'),
                    n_slack_values=len(doc.get('slack_grid_s') or []), violations_total=doc.get('violations_total'),
                    passed=doc.get('pass'),
                    networks={n: {k: v.get(k) for k in ('file_sha256', 'family', 'admitted_bound_ge_Dstar',
                                                        'violations_total', 'share_admitted', 'bypass_rate',
                                                        'bypass_rate_slack', 'bypass_rate_timing')}
                              for n, v in sorted(nets.items())})
        p += networks_problems({n: v.get('file_sha256') for n, v in nets.items()})
        if summ['n_slack_values'] != len(SB.SLACK_GRID_MS):
            p.append(f'S2: {summ["n_slack_values"]} slack values; Sec. 7.6 sweeps [-0.1, 0.6] s in 10 ms steps')
        bound = {n: v.get('admitted_bound_ge_Dstar') for n, v in nets.items()}
        if doc.get('pass') is not True or doc.get('violations_total') != 0 or any(b != 0 for b in bound.values()):
            p.append(f'S2: admitted actions with bound >= D* {bound} (must be 0), violations '
                     f'{doc.get("violations_total")}')
        fid = doc.get('replay_fidelity')
        if fid is not None and not fid.get('ok'):
            p.append('S2: the recorded states do not replay faithfully (replay_fidelity)')
    else:
        plan = doc.get('plan') or {}
        tested = {n.get('name'): n.get('file_sha256') for n in plan.get('networks') or []}
        loads = [r.get('load') for r in doc.get('per_load') or []]
        summ.update(loads=loads, networks=tested, envelope=doc.get('envelope'), states=plan.get('states'),
                    scenes=plan.get('scenes'), shared_cpu=doc.get('shared_cpu'),
                    foreign_cpu_accepted=doc.get('foreign_cpu_accepted'))
        p += networks_problems(tested)
        if loads != list(SB.LOADS) or plan.get('loads') != list(SB.LOADS):
            p.append(f'S1: loads {loads}; Sec. 7.6 asks {list(SB.LOADS)} background busy processes')
        if (doc.get('envelope') or {}).get('sha256') != tuning['L']['sha256']:
            p.append(f'S1: the lease ran on {doc.get("envelope")}, not on L* = {tuning["L"]["label"]}')
        if doc.get('shared_cpu') is not False:
            p.append('S1: not run on an exclusive CPU (shared_cpu)')
    return summ, p


# ---------------------------------------------------------------------------------------- the freeze

def code_record():
    return {f: PJ.sha256_file(ROOT / f) for f in CODE_FILES}


def merge_files(files, more, what):
    """files += more (in place); ValueError for a path named with two sha256."""
    for k, v in sorted(more.items()):
        if files.setdefault(k, v) != v:
            raise ValueError(f'{k} is named with sha256 {files[k]} and {v} ({what})')
    return files


def build_freeze(selection=None, rl_freeze=None, jobs_dir=None, stress=(), stress_dir=STRESS_DIR,
                 protocol=P2J.PROTOCOL, seal=P2J.SEAL, root=ROOT):
    """(record, {path: sha256} of the manifest, problems) of the test freeze; nothing is written. Refusals raise:
    PermissionError (an uncited tuning freeze or stage selection, an unsealed PROTOCOL.md, an RL development record,
    a test-route run under `root`), FileNotFoundError (an input missing), ValueError (an inconsistent input, or a
    registered input or code file that differs from the sealed registration manifest: test_jobs.registered_inputs of
    test_jobs.REGISTERED_INPUTS and REGISTERED_CODE); the problems are those of the checks (job files, pins against the
    tree and against the registered P1 pins, stress tests)."""
    tuning, rl, rl_doc, stages = load_freezes(selection, rl_freeze, protocol, seal)
    registered = TJ.registered_inputs(TJ.REGISTERED_INPUTS + tuple(ROOT / f for f in REGISTERED_CODE))
    jobs, job_files, lines, problems = job_files_record(tuning, rl, jobs_dir)
    runs = TJ.existing_runs(lines, root)
    if runs:
        raise PermissionError(f'refusing the test freeze: {runs[0]} exists ({len(runs)} test-route run path(s); '
                              'PROTOCOL Secs. 8.1, 9.11: the test freeze precedes every test-route run)')
    pins = pins_record([b['job_file'] for b in jobs['blocks'] if b.get('job_file')])
    problems += [f'pin {m["file"]}: sha256 {m["found"]} != pinned {m["expected"]}' for m in pins['mismatches']]
    stress_rec = {}
    for test, path in stress_paths(stress, stress_dir).items():
        stress_rec[test], p = stress_check(test, path, tuning, rl)
        problems += p
    code = code_record()
    files = {}
    merge_files(files, {tuning['path']: tuning['sha256']}, 'the tuning freeze')
    merge_files(files, {s['path']: s['sha256'] for s in stages}, 'the stage selections')
    merge_files(files, {rl['path']: rl['sha256']}, 'the RL freeze')
    merge_files(files, rl_doc.get('files') or {}, 'the files of the RL freeze')
    merge_files(files, job_files, 'the P4-P6 job files, block specs, checks and index')
    merge_files(files, pins['files'], 'the pins of the P4-P6 lines')
    merge_files(files, {s['path']: s['sha256'] for s in stress_rec.values()}, 'the S1-S3 reports')
    merge_files(files, code, 'the code of the freeze')
    merge_files(files, registered, 'the route split, routes.json, the envelope manifest and the registered code')
    record = {'schema': SCHEMA, 'variant': TJ.VARIANT, 'script': THIS_REL, 'protocol': tuning['protocol'],
              'tuning_freeze': tuning_record(tuning, stages), 'rl_freeze': rl_record(rl, rl_doc, protocol),
              'job_files': jobs, 'pins': {'n': pins['n'], 'files': pins['files']}, 'stress': stress_rec,
              'code_sha256': code, 'registered_inputs': registered,
              'test_route_runs': {'existing': runs, 'checked': [
                  f'runs/ in the {len({j["output_dir"] for j in lines})} output directories of the {len(lines)} lines',
                  *[f'{TJ.OUT_REL}/{r}/*/runs' for r in TJ.P4P6_ROOTS], f'{TJ.QUEUE_REL}/status.jsonl']},
              'deviations': list(DEVIATIONS),
              'entry': 'PROTOCOL Secs. 3.3 rule 4, 5.9 and 8.1: the coordinating session enters the sha256 of this '
                       'record and of its manifest in Sec. 13.2 and seals; no test-route run starts before '
                       '(test_freeze.py --verify)'}
    return record, files, problems


def manifest_text(files):
    """sha256sum format (`sha256sum -c` from the project root), sorted by path."""
    return ''.join(f'{sha}  {path}\n' for path, sha in sorted(files.items()))


def _same_record(text, rec):
    try:
        old = json.loads(text)
    except ValueError:
        return False
    return isinstance(old, dict) and {k: v for k, v in old.items() if k != 'written'} \
        == {k: v for k, v in rec.items() if k != 'written'}


def write_freeze(record, files, out_dir=None, protocol=P2J.PROTOCOL, force=False):
    """Write MANIFEST.sha256 and test_freeze.json (the record plus the manifest's path, sha256 and size, and the time).
    An equal file is kept (the record: equal up to 'written'); refusals: PermissionError for a queue path or a file
    whose sha256 PROTOCOL Sec. 13.2 cites and that would change, FileExistsError for other content without force.
    Nothing is written unless every refusal test passes."""
    out = Path(out_dir or OUT_DIR)
    hits = P2J.queue_parts(out)
    if hits:
        raise PermissionError(f'refusing to write under {out}: {hits[0]} belongs to a runner queue')
    mpath, rpath = out / MANIFEST_NAME, out / RECORD_NAME
    mtext = manifest_text(files)
    rec = {**record, 'manifest': {'path': PJ.rel(mpath), 'sha256': PJ.sha256_text(mtext), 'n_files': len(files)},
           'written': time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    keep = rpath.is_file() and _same_record(rpath.read_text(encoding='utf-8'), rec)
    todo = [(mpath, mtext)] + ([] if keep else [(rpath, json.dumps(rec, indent=1, sort_keys=True) + '\n')])
    for path, new in todo:
        if path.exists() and path.read_text(encoding='utf-8') != new:
            cited = TJ.recorded(path, protocol)
            if cited:
                raise PermissionError(f'refusing to overwrite {PJ.rel(path)}: its sha256 is recorded in PROTOCOL Sec. '
                                      f'13.2 (lines {cited}); the test freeze is never rewritten')
            if not force:
                raise FileExistsError(f'refusing to overwrite {PJ.rel(path)} with other content (use --force; no '
                                      'entry may cite it)')
    out.mkdir(parents=True, exist_ok=True)
    for path, new in todo:
        path.write_text(new, encoding='utf-8')
    return {'record': PJ.rel(rpath), 'record_sha256': PJ.sha256_file(rpath), 'manifest': PJ.rel(mpath),
            'manifest_sha256': PJ.sha256_file(mpath), 'n_files': len(files), 'record_kept': keep}


# ---------------------------------------------------------------------------------------- the Sec. 13.2 entry

def _cite(lines):
    return f'entered above in line(s) {", ".join(map(str, lines))}' if lines else 'entered by this entry'


def entry_lines(rec, record_sha, when=None):
    """The Sec. 13.2 entry of the written record (Markdown, 120 columns, the form of the earlier entries; p1_driver's
    entry_time and wrap_entry). The registration manifest line follows it, added by the coordinating session after
    registration.py --write-manifest --force."""
    import textwrap
    from framelease_v4.protocol import p1_driver as PD
    tf, rl, jf, st, man = rec['tuning_freeze'], rec['rl_freeze'], rec['job_files'], rec['stress'], rec['manifest']
    L, ev, nets = tf['L_star'], tf['event_star'], rl['networks']
    head = (f'**Test freeze, {when or PD.entry_time()}: P4-P6 job files, RL freeze and stress tests (PROTOCOL '
            'Secs. 3.3 rule 4, 5.9, 7.6, 8.1).** No test-route run existed at the freeze: no runs/ entry in the output '
            f'directories of the {jf["n_lines"]} P4-P6 lines or under '
            f'{", ".join(f"`{TJ.OUT_REL}/{r}/`" for r in TJ.P4P6_ROOTS)}, and no status record in `{TJ.QUEUE_REL}`. '
            'P4 starts once this entry is sealed and `framelease_v4/protocol/test_freeze.py --verify` passes.')
    shared = ''.join(f' Arms {", ".join(f"`{a}`" for a in arms)} share the name `{n}` (identical decision cores).'
                     for n, arms in sorted((rl.get('shared_names') or {}).items()))
    devs = rl['deviations']
    blocks = '; '.join(
        f'`{Path(b["job_file"]).name}` tier {b["tier"]} ({b["phase"]}), {b["n_lines"]} lines, sha256 '
        f'`{b["job_file_sha256"]}`' if b.get('job_file') else f'{b["block"]}: no job file ({b["skipped"]})'
        for b in jf['blocks'])
    s1, s2, s3 = st['S1'], st['S2'], st['S3']
    bullets = [
        f'Record. `{rec["script"]}` wrote `{PJ.rel(Path(man["path"]).parent / RECORD_NAME)}` (sha256 `{record_sha}`) '
        f'and its sha256 manifest `{man["path"]}` ({man["n_files"]} files, sha256 `{man["sha256"]}`). The manifest '
        'lists every file named in this entry, the pins of the P4-P6 lines, the code of the freeze, the route split, '
        'its source `routes.json` and the envelope manifest; these files are registered from this entry on, and '
        '`sha256sum -c` of the manifest from the project root shows that none changed. The route split, '
        '`routes.json`, the envelope manifest, the registered code the freeze runs and every pin except the network '
        'files and the extension sources were at their sha256 of the sealed registration manifest.',
        f'Tuning freeze (Sec. 4.9). `{tf["path"]}` (sha256 `{tf["sha256"]}`, {_cite(tf["cited_lines"])}): L* = '
        f'{L["label"]} (`{L["path"]}`, sha256 `{L["sha256"]}`), d* = {tf["d_star"]} (utility `{tf["d_utility"]}`), '
        f'A* = {tf["A_star"]} s, Event-Triggered `{ev["candidate"]}` ({json.dumps(ev["policy_params"], sort_keys=True)}'
        f'). {tf["fl_risk"]["reason"]}. Its {len(tf["stage_selections"])} stage selections are entered above.',
        f'RL freeze (Sec. 5.9). `{rl["path"]}` (sha256 `{rl["sha256"]}`), made from this tuning freeze, names '
        f'{rl["n_files"]} files, among them the P2 data manifest `{rl["p2_manifest"]["path"]}` (sha256 '
        f'`{rl["p2_manifest"]["sha256"]}`, {_cite(rl["p2_manifest"]["cited_lines"])}). P_both: {rl["p_both_label"]}. '
        'Deployed networks (an arm is identified by its arm and the network file sha256; the name pins neither B_pi '
        'nor the provenance): ' + '; '.join(f'`{a}` `{n["name"]}` (family {n["family"]}, `{n["path"]}`, file sha256 '
                                             f'`{n["sha256"]}`)' for a, n in nets.items()) + '.' + shared,
        'RL freeze deviations (GAP_AUDIT Sec. 6 item 5): ' + ('none.' if not devs else '; '.join(
            f'{d.get("stage")}: case {d.get("case")}, option {d.get("option")} ({d.get("rule")})' for d in devs) + '.'),
        *[f'RL implementation note: {x}' for x in rl['sec13_notes']],
        f'Job files (Secs. 7.2-7.5, 8.2, 8.3, 8.6, 10.1). `{jf["dir"]}/`, generated by `{jf["generator"]["path"]}` '
        f'(sha256 `{jf["generator"]["sha256"]}`), index `{Path(jf["index"]["path"]).name}` (sha256 '
        f'`{jf["index"]["sha256"]}`): {blocks}. {jf["n_lines"]} lines in total, the registered budget of Sec. 10.1. '
        'Every line passed gpu_queue\'s job contract, the pins, the test routes of its block\'s subset, the kappa and '
        'seed of its block, the launcher\'s parsing, configuration build and preflight and the `--dry-run` of the '
        'exact command through its launcher (`framelease_v4/arms/run_closed_loop_v4.py`; '
        '`framelease_v4/arms_ext/run_closed_loop_ext.py` for `fl_global_shield`), as the `.check.json` files record; '
        'the block specs (`.stage.json`) give for every job id the protocol arm, route, kappa, seed, configuration '
        'and the envelope and network sha256.',
        f'Fixed by this entry: the block numbers 11-16 and the job file names, the Fig. 3 cell order (arm-major over '
        f'kappa 1.5, 2.0) and one queue `{TJ.QUEUE_REL}` for tiers 3-6: the job files are copied in name order into '
        'its `jobs.d/`, so a cut takes the bottom tiers first (Sec. 10.2).',
        f'Pins (Sec. 8.3). {rec["pins"]["n"]} files pinned by the P4-P6 lines (the 49 code files of every line, the '
        'envelopes, the three network files, the 5 extension sources of `fl_global_shield`), every one at its pinned '
        'sha256.',
        f'Stress tests (Sec. 7.6), registered runs. S3 `{s3["path"]}` (sha256 `{s3["sha256"]}`): {s3["n_sequences"]} '
        'random event sequences on the commit gate and on the V4Runtime commit path, every fault class covered, 0 '
        f'commits violating Eq. 9. S2 `{s2["path"]}` (sha256 `{s2["sha256"]}`): {s2["n_swept"]} decision states x '
        f'{s2["n_slack_values"]} slack values per deployed network, 0 admitted actions with bound >= D*, 0 '
        f'violations. S1 `{s1["path"]}` (sha256 `{s1["sha256"]}`): loads {"/".join(map(str, s1["loads"]))} busy '
        'processes on an exclusive CPU, every deployed network, the lease on L*.',
        'Implementation choices of the freeze: ' + ' '.join(rec['deviations']),
    ]
    out = textwrap.wrap(head, width=120, break_long_words=False, break_on_hyphens=False)
    for b in bullets:
        out += PD.wrap_entry(b)
    return out


# ---------------------------------------------------------------------------------------- reading it back

def read_written(out_dir=None):
    """(record, record sha256, problems) of the written freeze: the record names its manifest by sha256 and every file
    of the manifest is at its sha256 now (registration.verify on the manifest). FileNotFoundError without one."""
    from framelease_v4.protocol import registration as REG
    out = Path(out_dir or OUT_DIR)
    mpath, rpath = out / MANIFEST_NAME, out / RECORD_NAME
    if not rpath.is_file() or not mpath.is_file():
        raise FileNotFoundError(f'{PJ.rel(out)}: no test freeze written yet (test_freeze.py --write)')
    rec = json.loads(rpath.read_text(encoding='utf-8'))
    if not isinstance(rec, dict) or rec.get('schema') != SCHEMA:
        raise ValueError(f'{PJ.rel(rpath)} is not a test-freeze record (schema {SCHEMA})')
    problems = []
    man = rec.get('manifest') or {}
    msha = PJ.sha256_file(mpath)
    if (man.get('path'), man.get('sha256'), man.get('n_files')) \
            != (PJ.rel(mpath), msha, len(REG.read_manifest(mpath))):
        problems.append(f'{PJ.rel(rpath)} names the manifest {man}, {PJ.rel(mpath)} has sha256 {msha}')
    problems += [f'{f}: sha256 {got} != {want} of the test-freeze manifest' for f, want, got in REG.verify(mpath)]
    return rec, PJ.sha256_file(rpath), problems


def queue_copy_problems(rec, queue_dir=None):
    """(names copied, problems) of the job files in the P4-P6 queue's jobs.d/ (GAP_AUDIT E-1: the frozen job files,
    copied by hand in name order after --verify): every *.jsonl there must be a job file of the record under its own
    name and at its frozen sha256. A job file not copied yet is no problem."""
    qdir = Path(queue_dir or ROOT / TJ.QUEUE_REL / 'jobs.d')
    frozen = {Path(b['job_file']).name: b['job_file_sha256'] for b in rec['job_files']['blocks'] if b.get('job_file')}
    copied, problems = [], []
    for f in sorted(qdir.glob('*.jsonl')) if qdir.is_dir() else []:
        sha = PJ.sha256_file(f)
        if f.name not in frozen:
            problems.append(f'{PJ.rel(f)}: not a job file of the test freeze ({", ".join(sorted(frozen))})')
        elif sha != frozen[f.name]:
            problems.append(f'{PJ.rel(f)}: sha256 {sha} != {frozen[f.name]} of the frozen {f.name}')
        else:
            copied.append(f.name)
    return copied, problems


def verify_freeze(out_dir=None, protocol=P2J.PROTOCOL, seal=P2J.SEAL, queue_dir=None):
    """After the entry and the seal: ({'record', 'record_sha256', 'manifest_sha256', 'cited_lines', 'queue_copies'},
    problems). PermissionError while PROTOCOL Sec. 13.2 does not cite the record and the manifest, or PROTOCOL.md is
    not the sealed version (seal None skips: tests only); problems: read_written's and queue_copy_problems' (the
    copies in queue_dir, default outputs/framelease_v4/queue_p4/jobs.d)."""
    rec, rsha, problems = read_written(out_dir)
    copied, queue_problems = queue_copy_problems(rec, queue_dir)
    problems += queue_problems
    if seal is not None:
        s = P2J.protocol_seal(protocol, seal)
        if not s['sealed']:
            raise PermissionError(f'PROTOCOL.md (sha256 {s["protocol_sha256"]}) is not the sealed version '
                                  f'({s["sealed_sha256"]}): seal the test-freeze entry first')
    msha = (rec.get('manifest') or {}).get('sha256')
    cited = {'record': _cited(rsha, protocol), 'manifest': _cited(msha, protocol) if msha else []}
    if not cited['record'] or not cited['manifest']:
        raise PermissionError(f'PROTOCOL Sec. 13.2 does not cite the test freeze yet (record {rsha}: lines '
                              f'{cited["record"]}; manifest {msha}: lines {cited["manifest"]})')
    return {'record': PJ.rel(Path(out_dir or OUT_DIR) / RECORD_NAME), 'record_sha256': rsha, 'manifest_sha256': msha,
            'cited_lines': cited, 'queue_copies': copied}, problems


# ---------------------------------------------------------------------------------------- CLI

def summary_lines(rec, files):
    tf, rl, jf = rec['tuning_freeze'], rec['rl_freeze'], rec['job_files']
    out = [f'test freeze: {len(files)} files (NOT written unless --write)',
           f'  tuning freeze {tf["path"]} {tf["sha256"][:12]} (Sec. 13.2 lines {tf["cited_lines"]}): L* = '
           f'{tf["L_star"]["label"]}, d* = {tf["d_star"]}, A* = {tf["A_star"]}, event {tf["event_star"]["candidate"]}; '
           f'{len(tf["stage_selections"])} stage selections cited',
           f'  RL freeze {rl["path"]} {rl["sha256"][:12]}: {rl["n_files"]} files, P_both {rl["p_both_label"]}, '
           f'{len(rl["deviations"])} deviations; P2 manifest {rl["p2_manifest"]["path"]} (Sec. 13.2 lines '
           f'{rl["p2_manifest"]["cited_lines"]})',
           f'  job files {jf["dir"]}: {jf["n_lines"]} lines (Sec. 10.1: {jf["expected_runs_sec_10_1"]}), '
           + ', '.join(f'{b["block"]} {b["n_lines"]}' for b in jf['blocks']),
           f'  pins {rec["pins"]["n"]}; stress ' + ', '.join(f'{t} {s["path"]}' for t, s in rec['stress'].items()),
           f'  test-route runs: {rec["test_route_runs"]["existing"] or "none"}']
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--selection', type=Path, default=TJ.SS.FREEZE_PATH, help='the tuning freeze (selection.json)')
    ap.add_argument('--rl-freeze', type=Path, default=TJ.RL_FREEZE, help='the RL freeze (rl_freeze.json)')
    ap.add_argument('--jobs-dir', type=Path, default=TJ.JOBS_DIR, help='test_jobs.py --jobs-dir')
    ap.add_argument('--stress', action='append', default=[], metavar='S<k>=PATH',
                    help='a registered stress report (default: the one s<k>_registered_*.json per test)')
    ap.add_argument('--stress-dir', type=Path, default=STRESS_DIR)
    ap.add_argument('--protocol', type=Path, default=P2J.PROTOCOL)
    ap.add_argument('--seal', type=Path, default=P2J.SEAL)
    ap.add_argument('--out-dir', type=Path, default=OUT_DIR)
    ap.add_argument('--queue-dir', type=Path, default=ROOT / TJ.QUEUE_REL / 'jobs.d',
                    help='--verify: the jobs.d/ whose copies must be the frozen job files')
    ap.add_argument('--write', action='store_true', help='write the record and its manifest, print the entry')
    ap.add_argument('--entry', action='store_true', help='print the Sec. 13.2 entry of the written record')
    ap.add_argument('--verify', action='store_true', help='after the entry and the seal: the freeze holds')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args(argv)
    if sum((a.write, a.entry, a.verify)) > 1:
        ap.error('one of --write, --entry, --verify')
    try:
        if a.verify:
            info, problems = verify_freeze(a.out_dir, a.protocol, a.seal, a.queue_dir)
            if problems:
                print('TEST FREEZE CHANGED\n  ' + '\n  '.join(problems[:40]), file=sys.stderr)
                return 1
            print(json.dumps(info, indent=1))
            print(f'test freeze OK: the P4-P6 job files may be copied, in name order, into {TJ.QUEUE_REL}/jobs.d/')
            return 0
        if a.entry:
            rec, rsha, problems = read_written(a.out_dir)
            if problems:
                print('TEST FREEZE CHANGED\n  ' + '\n  '.join(problems[:40]), file=sys.stderr)
                return 1
            print('\n'.join(entry_lines(rec, rsha)))
            return 0
        record, files, problems = build_freeze(a.selection, a.rl_freeze, a.jobs_dir, a.stress, a.stress_dir,
                                               a.protocol, a.seal)
    except (FileNotFoundError, ValueError, PermissionError) as e:
        print(f'REFUSED: {e}', file=sys.stderr)
        return 2
    print('\n'.join(summary_lines(record, files)))
    if problems:
        print('CHECK FAILED\n  ' + '\n  '.join(problems[:40]), file=sys.stderr)
        return 1
    if not a.write:
        return 0
    try:
        info = write_freeze(record, files, a.out_dir, a.protocol, a.force)
    except (PermissionError, FileExistsError) as e:
        print(f'REFUSED: {e}', file=sys.stderr)
        return 2
    print(json.dumps(info, indent=1))
    rec, rsha, problems = read_written(a.out_dir)
    if problems or rsha != info['record_sha256']:
        print('WRITTEN FREEZE INCONSISTENT\n  ' + '\n  '.join(problems[:40]), file=sys.stderr)
        return 1
    print('\n---- PROTOCOL Sec. 13.2 entry (appended by the coordinating session under the protocol lock; then '
          'registration.py --write-manifest --force, the manifest line, --seal, --verify, test_freeze.py --verify):\n')
    print('\n'.join(entry_lines(rec, rsha)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
