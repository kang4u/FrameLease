#!/usr/bin/env python3
"""P7 aggregator of the v4 closed-loop runs (framelease_v4/PROTOCOL.md Secs. 6, 9.1, 9.7, 9.8, 9.11, 9.12; GAP_AUDIT
Sec. 3.7 rows R-1, R-2, R-3; CPU only, reads run directories, writes only under --out).

  cd /home/kang/Desktop/DAC
  .conda-unidrive-linux/bin/python -I -B framelease_v4/analysis/aggregate_v4.py \
      --queue outputs/framelease_v4/queue_p1 [--queue DIR ...] [--jobs FILE ...] \
      [--specs outputs/framelease_v4/p1_jobs/FULL ...] [--rl-freeze outputs/framelease_v4/rl_freeze/rl_freeze.json] \
      [--tuning-freeze outputs/framelease_v4/tuning/selection.json] [--arm-summary training|test|all] \
      [--analysis-freeze RECORD [--required-job-files FILE] | --write-freeze-record FILE [--cut-amendment ID]] \
      --out DIR [--force]

Inputs:
  --queue DIR   a gpu_queue directory: its job files DIR/jobs.d/*.jsonl and the runner's DIR/status.jsonl
                (framelease_v2/gpu_queue.py Runner.job_states decides which attempts counted and which record is final)
  --jobs FILE   a job file outside a queue (its runs are inferred from the run directories alone, select_stage rule)
  --specs P     block specs (*.stage.json of p1_jobs.py / p2_jobs.py / test_jobs.py, STAGE_SCHEMAS; a directory is
                searched for *.stage.json, e.g. outputs/framelease_v4/test_jobs/FULL): every job a spec names must be a
                job line with the same id, block and output directory, and the spec's job file sha256 must be the
                sha256 of a job file read here
  --rl-freeze   the RL freeze of p3_rl.py (rl_freeze.json): network file sha256 -> family -> protocol arm
  --tuning-freeze  the tuning freeze of select_stage.py (selection.json): L*, d*, A*, theta*, A_hb*, fl_risk lease point
  --analysis-freeze  a valid analysis-freeze record (interim_guard.py; Sec. 9.11 below)
  --required-job-files  a JSON object {job file: sha256}: the registered tier 3-6 job files of the test freeze (Sec.
                 8.1); the record must list each of them with that sha256
  --arm-summary  also write arm_summary.csv: metrics_v4.arm_summary per protocol arm x candidate x kappa x seed x phase
                 x block x route split (SUMMARY_KEYS) over the analysis_use rows; 'training' always, 'test' / 'all'
                 (cross-arm test-route summaries) only with a valid analysis-freeze record, otherwise refused and logged
  --write-freeze-record  write the analysis-freeze record of this aggregation (interim_guard.freeze_record; every job
                 final, or never started under --cut-amendment); valid once its sha256 is a dated Sec. 13 entry of the
                 re-sealed PROTOCOL.md

Run selection (R-1): one row per job line. The final run of a job is select_stage.job_outcome's (the first valid
official record, or the runner's final record), evaluated with the job line's own candidate (launcher arm, policy
parameters, envelope), kappa and seed. Outcomes: ok, agent_crashed, sim_failure, pending, error (inconsistent runner
records: select_stage.SelectionError, reported, never selected).

Code check (Sec. 9.1): check_smoke.c_config(job, run): launcher arm, route, kappa, seed, policy parameters, envelope
sha256, fast-prefix options and every pinned sha256 the run recorded.

Protocol-arm labels (GAP_AUDIT Sec. 2 "Recommended labelling"): the launcher arm (config.json v4_arm) is the protocol
arm, except
  fl_full           the network file sha256 the run recorded (config.json v4.utility.env_files_sha256) maps through
                    the RL freeze to its family: fqi -> fl_full, bandit -> fl_bandit, fqi_nolease -> fl_fqi_nolease;
  fl_heuristic      at the fl_risk lease point of the tuning freeze (an envelope sha256 other than L*) -> fl_risk;
  fl_global_shield  identified by the arm name of its configuration (config.json v4.arm) and its validity source
                    'global_lease' (no import of framelease_v4/arms_ext).
A job line's protocol_arm, its block spec and its output directory (.../ablation/<arm>/..., where it names one) must
agree with the label; a disagreement is a label problem and excludes the run (a run that cannot be attributed to one
protocol arm cannot enter any Sec. 9.1 contrast). The configuration check of R-3 is reported only (manipulation.py).

Per-run rows: metrics_v4.run_metrics(run_dir, realized=True) (Amendment A2 keys realized_invalid_ticks /
realized_invalid_tick_ratio), the metrics metrics_v4 lacks (extra_metrics.py: infractions/km of Sec. 6.1 and the
route-ending events, DMR from the first commit, CUDA-s/s, closed-loop lease utilization and premature expiry of Sec.
6.3, the Sec. 6.4 scheduler metrics, the Table II-B timings), the per-run manipulation checks (manipulation.py: fast
prefix, charged prefix, background load, configuration, predicted expiry fallback, job durations by depth) and the
commit audit of the selected run, plus the selection, code-check and label fields. runs.csv carries km_driven floored at
0.001 km (Sec. 6.1, KM_FLOOR: route length x RC / 100, leaderboard floor), the km the per-km metrics divide by.

Interim-look guard (Sec. 9.11; interim_guard.py): the test routes are the registered split's (checked against the
registration manifest; test_routes may only add routes). A row is guarded when its job line names a test route or
declares no training route, or its run recorded a test route; a guarded row is health-only (job health, the prefix
timing, the health / configuration checks; no outcome metric) unless a VALID analysis-freeze record (its sha256 a Sec.
13 entry of the sealed PROTOCOL.md, the analysis code and the job file unchanged, the job's outcome and run as
recorded; a record cited only by a development copy of PROTOCOL.md never releases a registered test route) releases
it. Every guarded row carries its guard_note; aggregate.json records the guard state. Every CLI request is logged
(granted or refused) in <out>/interim_guard.jsonl; an invalid record and a cross-arm summary of test routes before the
freeze are refused (exit 4).

R-2 (commit_audit.py; PROTOCOL Sec. 7.6 'Commit audit (all runs)'): every commit record of every run directory of every
job line (all attempts, and the runs under the job lines' output directories that match no job line) is re-checked
against Eq. 9: t_commit < D, M(t_commit - t_k) > delta (arms with a lease), a newer version, not cancelled. H5 (Sec.
9.5) is a registered outcome, so before the analysis freeze the audit of the run directories of guarded rows, and of
runs that recorded a test route (or, matching no job line, cannot be read), is WITHHELD: not audited, no count, out of
the totals (runs_withheld only; the row's commit_audit_status is WITHHELD); it is released together with its row.
Status FAIL, ERROR, INCOMPLETE (runs withheld) or PASS.
R-3 (manipulation.py; Sec. 9.7, reported, not tested, no run excluded): per run in runs.csv, across runs in
aggregate.json (per protocol arm and kappa; predicted expiry, kappa scaling and P_both over non-health-only rows only).

Missing data (Sec. 9.8): nothing is imputed. Every row carries analysis_use and missing_reason: pending, not_launched,
selection_error, agent_crashed, sim_failure, no_metrics (run_metrics gave no row or no valid official record),
code_mismatch, label_problem, health_only (a guarded row not released by the analysis freeze). A secondary metric step
that fails on a malformed log (extra_metrics_error, metric_steps_failed; aggregate.json metric_errors) leaves only its
own columns empty and never removes a route with a valid record (Sec. 9.1: the analysis drops the route only from the
contrasts of the missing metrics). The commit audit and the R-3 checks report; they never exclude a run.

Development data: PROTOCOL Sec. 9.12 says the analysis code is 'written and tested on synthetic CSVs only'. The unit
tests use synthetic run directories only, but the builder also ran read-only smoke aggregations of the real P1
training-route runs (queue_p1; outputs in outputs/framelease_v4/build/AGG/), as GAP_AUDIT Sec. 1.5 allows ('developed
on P1/P2 training-route runs'). No test-route run was read. The PROTOCOL wins: this is a deviation, to be recorded in
the Sec. 13 entry that enters the sha256 of this code.

Outputs (under --out): runs.csv, aggregate.json (schema framelease_v4.aggregate/1: arguments, the sha256 of every input
file read, of this script, its sibling modules and the modules it reuses, and of runs.csv, the selection and
code-check counts, the label problems, the missing-data table, the commit audit, the manipulation checks, the
interim guard and the guard log's state), arm_summary.csv (with --arm-summary) and SHA256SUMS (every file written);
the guard log interim_guard.jsonl is append-only and never replaced.

Exit codes: 0 written, 1 refused (out directory exists without --force, protected path), 2 inconsistent inputs (or a
job not final for --write-freeze-record), 4 refused by the interim-look guard (logged).
"""
from __future__ import annotations

import argparse
import contextlib
import functools
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from framelease_v4.analysis import commit_audit as CA  # noqa: E402
from framelease_v4.analysis import extra_metrics as XM  # noqa: E402
from framelease_v4.analysis import interim_guard as G  # noqa: E402
from framelease_v4.analysis import manipulation as MC  # noqa: E402
from framelease_v4.arms import metrics_v4 as MV  # noqa: E402
from framelease_v4.protocol import check_smoke as CS  # noqa: E402
from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402
from framelease_v4.protocol import select_stage as SS  # noqa: E402

SCHEMA = 'framelease_v4.aggregate/1'
THIS_REL = 'framelease_v4/analysis/aggregate_v4.py'
# block-spec schemas of p1_jobs.py, p2_jobs.py and test_jobs.py (STAGE_SCHEMA of each; test_jobs: tiers 3-6, P4-P6)
STAGE_SCHEMAS = ('framelease_v4.p1_stage/1', 'framelease_v4.p2_stage/1', 'framelease_v4.test_stage/1')
RL_FREEZE_SCHEMA = 'framelease_v4.rl_freeze/1'                    # framelease_v4/protocol/p3_rl.py FREEZE_SCHEMA
RL_ARM_OF = {'fqi': 'fl_full', 'bandit': 'fl_bandit', 'fqi_nolease': 'fl_fqi_nolease'}   # p3_rl.ARM_OF (Sec. 5.6)
GLOBAL_SHIELD = 'fl_global_shield'                                # framelease_v4/arms_ext/global_shield.py NAME
GLOBAL_SOURCE = 'global_lease'                                    # its validity source
OUTCOME_REASON = {'pending': 'pending', 'agent_crashed': 'agent_crashed', 'sim_failure': 'sim_failure',
                  'error': 'selection_error'}
# files of a run directory the row reads (their sha256 enters aggregate.json)
RUN_INPUTS = ('config.json', 'manifest.json', 'metrics/result.json', 'raw/official_results.json',
              'raw/agent/framelease/summary.json', 'raw/agent/framelease/ticks.jsonl',
              'raw/agent/framelease/jobs.jsonl', 'raw/agent/framelease/events.jsonl',
              'raw/agent/framelease/decisions.jsonl', 'raw/agent/framelease/actors.jsonl.gz',
              'raw/agent/framelease/fast_prefix.json', 'raw/source_v4/hashes.json', 'raw/source_v3/hashes.json',
              'raw/source_fastprefix/hashes.json')
# the leading columns of runs.csv (selection, code check, label, missing data); metrics follow in metrics_v4 order
ID_COLUMNS = ('job', 'job_file', 'block_spec', 'phase', 'block', 'candidate', 'route_id', 'training_route', 'kappa',
              'seed', 'launcher_arm', 'protocol_arm', 'label_source', 'label_problem', 'outcome', 'selection_note',
              'attempts_found', 'queue_attempts', 'queue_counted', 'selected_run', 'code_check', 'code_detail',
              'analysis_use', 'missing_reason', 'health_only', 'test_route', 'guard_note')
# outputs that never take an aggregator output (read-only inputs of other phases)
PROTECTED = ('framelease_v2', 'framelease_v3', 'framelease_v4', 'linux', 'third_party', 'checkpoints',
             'outputs/framelease_v4/p1_driver', 'outputs/framelease_v4/p1_jobs', 'outputs/framelease_v4/tuning',
             'outputs/framelease_v4/registration', 'outputs/framelease_v4/rl_dev', 'outputs/framelease_v4/envelopes',
             'outputs/framelease_v4/protocol', 'outputs/framelease_v4/smoke_p1_0', 'outputs/framelease_v4/rl_data',
             'outputs/framelease_v4/rl_freeze')
PROTECTED_PREFIXES = ('outputs/framelease_v4/queue_', 'outputs/framelease_v4/amendment_')


class AggregateError(RuntimeError):
    """Inconsistent inputs (job files, block specs, freezes): nothing is written."""


GuardRefused = G.GuardRefused        # a request the Sec. 9.11 guard refuses (interim_guard.py): exit 4, logged


# ============================================================================================ inputs

JOB_KEYS = ('id', 'arm_name', 'route_id', 'kappa', 'seed', 'output_dir', 'policy_params', 'require_sha256')


def load_job_file(path):
    """The job lines of one job file (check_smoke.strict_jsonl: a line that does not parse is an error)."""
    rows, problem = CS.strict_jsonl(path)
    if problem or rows is None:
        raise AggregateError(f'{PJ.rel(path)}: {problem}')
    for i, job in enumerate(rows, 1):
        missing = [k for k in JOB_KEYS if k not in job]
        if missing:
            raise AggregateError(f'{PJ.rel(path)} line {i}: job line without {missing}')
    return rows


def collect_jobs(queues=(), job_files=()):
    """[(job, job file, queue directory or None)] in the order given: every job file of each queue's jobs.d/, then the
    --jobs files. A job id listed twice is an error (one final run per job)."""
    out = []
    for q in queues:
        q = Path(q)
        files = sorted((q / 'jobs.d').glob('*.jsonl'))
        if not files:
            raise AggregateError(f'{PJ.rel(q)}: no job files in jobs.d/')
        out += [(job, f, q) for f in files for job in load_job_file(f)]
    out += [(job, Path(f), None) for f in job_files for job in load_job_file(f)]
    seen = {}
    for job, f, _ in out:
        if job['id'] in seen:
            raise AggregateError(f'job {job["id"]} is listed in {PJ.rel(seen[job["id"]])} and in {PJ.rel(f)}')
        seen[job['id']] = f
    return out


def load_specs(paths=()):
    """[(path, spec)] of the block specs given (a directory: its *.stage.json). A spec must carry one of
    STAGE_SCHEMAS: p1_jobs.py (P1 blocks), p2_jobs.py (P2) or test_jobs.py ('framelease_v4.test_stage/1', the tier
    3-6 blocks of P4-P6 in outputs/framelease_v4/test_jobs/FULL, read as written); any other file is refused."""
    files = []
    for p in paths:
        p = Path(p)
        files += sorted(p.glob('*.stage.json')) if p.is_dir() else [p]
    out = []
    for f in files:
        doc = MV.read_json(f)
        if not isinstance(doc, dict) or doc.get('schema') not in STAGE_SCHEMAS:
            raise AggregateError(f'{PJ.rel(f)}: not a block spec (schemas {STAGE_SCHEMAS})')
        out.append((f, doc))
    return out


def spec_jobs(spec):
    """{job id: {'block', 'output_dir', 'route_id', 'protocol_arm'}} of one block spec: p1_jobs.py lists them per
    candidate (candidates[].jobs, runs reused from an earlier block keep that block), p2_jobs.py and test_jobs.py in
    jobs[]."""
    out = {}
    for c in spec.get('candidates') or []:
        for route, j in (c.get('jobs') or {}).items():
            out[j['id']] = {'block': j.get('block', spec.get('block')), 'output_dir': j.get('output_dir'),
                            'route_id': str(route), 'protocol_arm': c.get('protocol_arm')}
    for j in spec.get('jobs') or []:
        out[j['id']] = {'block': spec.get('block'), 'output_dir': j.get('output_dir'),
                        'route_id': str(j.get('route_id')), 'protocol_arm': j.get('protocol_arm',
                                                                                  spec.get('protocol_arm'))}
    return out


def check_specs(specs, jobs, file_sha):
    """({job id: [spec paths]}, [problems]) of the block specs against the job lines read: the spec's job file must be
    one of the job files read (by sha256), and every job it names must be a job line with the same block, route and
    output directory (and protocol arm, where both name one)."""
    by_id = {job['id']: job for job, _, _ in jobs}
    shas = set(file_sha.values())
    where, problems = {}, []
    for path, spec in specs:
        name = PJ.rel(path)
        if spec.get('job_file_sha256') not in shas:
            problems.append(f'{name}: its job file {spec.get("job_file")} (sha256 {spec.get("job_file_sha256")}) is '
                            'not among the job files read')
        for jid, s in spec_jobs(spec).items():
            job = by_id.get(jid)
            if job is None:
                problems.append(f'{name}: job {jid} is not a job line read')
                continue
            where.setdefault(jid, []).append(name)
            got = {'block': job.get('block'), 'output_dir': job.get('output_dir'), 'route_id': str(job['route_id'])}
            for k, v in got.items():
                if s[k] != v:
                    problems.append(f'{name}: job {jid} {k} {s[k]!r} != the job line\'s {v!r}')
            if s.get('protocol_arm') and job.get('protocol_arm') and s['protocol_arm'] != job['protocol_arm']:
                problems.append(f'{name}: job {jid} protocol arm {s["protocol_arm"]!r} != the job line\'s '
                                f'{job["protocol_arm"]!r}')
    return where, problems


def load_rl_freeze(path, allow_dev=False):
    """{'path', 'sha256', 'frozen', 'by_sha': {network file sha256: [protocol arms]}} of an RL freeze (p3_rl.py
    rl_freeze.json; read as JSON, p3_rl is not imported). The family -> arm map is RL_ARM_OF (p3_rl.ARM_OF); the
    record's own arm entries and job lines must agree with it. A development record (frozen false) is refused unless
    allow_dev (tests, smoke runs)."""
    doc = MV.read_json(path)
    if not isinstance(doc, dict) or doc.get('schema') != RL_FREEZE_SCHEMA:
        raise AggregateError(f'{PJ.rel(path)}: not an RL freeze (schema {RL_FREEZE_SCHEMA})')
    if doc.get('frozen') is not True and not allow_dev:
        raise AggregateError(f'{PJ.rel(path)}: a {doc.get("mode")} record (frozen {doc.get("frozen")}) is not a freeze')
    by_sha, problems = {}, []
    for fam, v in (doc.get('families') or {}).items():
        arm = RL_ARM_OF.get(fam)
        net = (v or {}).get('network') or {}
        sha = net.get('file_sha256')
        line = (doc.get('job_lines') or {}).get(arm) or {}
        if arm is None or not sha:
            problems.append(f'family {fam!r}: unknown family or no network file sha256')
            continue
        if net.get('arm', arm) != arm or line.get('qnet_file_sha256', sha) != sha:
            problems.append(f'family {fam}: network arm {net.get("arm")!r} / job line sha256 '
                            f'{line.get("qnet_file_sha256")} disagree with {arm} / {sha}')
        by_sha.setdefault(sha, []).append(arm)
    if problems:
        raise AggregateError(f'{PJ.rel(path)}: ' + '; '.join(problems))
    return {'path': PJ.rel(path), 'sha256': PJ.sha256_file(path), 'frozen': doc.get('frozen') is True,
            'd_star': doc.get('d_star'), 'by_sha': {k: sorted(v) for k, v in by_sha.items()}}


def load_tuning_freeze(path, envelopes=None):
    """{'path', 'sha256', 'L_star_sha256', 'd_star', 'utility', 'A_star', 'event_params', 'risk_point', 'risk_sha256',
    'inputs'} of the tuning freeze (select_stage.freeze, schema select_stage.FREEZE_SCHEMA): A_star = the frozen
    Age-Only policy parameters (A* and the utility of d*), event_params = the frozen Event-Triggered parameters
    (theta*, A_hb*). The fl_risk lease point (FULL, L* = B0) is an envelope label; its sha256 comes from envelopes
    ({label: {'sha256'}}, default p1_jobs.envelopes(), which reads the envelope manifest and verifies every exported
    envelope file: inputs = {path: sha256} of those files, for aggregate.json)."""
    doc = MV.read_json(path)
    if not isinstance(doc, dict) or doc.get('schema') != SS.FREEZE_SCHEMA:
        raise AggregateError(f'{PJ.rel(path)}: not a tuning freeze (schema {SS.FREEZE_SCHEMA})')
    risk = doc.get('fl_risk') if isinstance(doc.get('fl_risk'), dict) else {}
    point = risk.get('lease_point')
    risk_sha, inputs = None, {}
    if point is not None:
        envs = PJ.envelopes() if envelopes is None else envelopes
        if point not in envs:
            raise AggregateError(f'{PJ.rel(path)}: fl_risk lease point {point!r} is not an exported envelope')
        risk_sha = envs[point]['sha256']
        if envelopes is None:
            inputs = {PJ.rel(PJ.ENVELOPE_MANIFEST): PJ.sha256_file(PJ.ENVELOPE_MANIFEST),
                      **{e['path']: e['sha256'] for e in envs.values()}}
    arms = doc.get('arms') or {}
    return {'path': PJ.rel(path), 'sha256': PJ.sha256_file(path),
            'L_star_sha256': (doc.get('L_star') or {}).get('envelope_sha256'),
            'd_star': (doc.get('d_star') or {}).get('d'), 'utility': (doc.get('d_star') or {}).get('utility'),
            'A_star': dict((arms.get('age_only') or {}).get('policy_params') or {}),
            'event_params': dict((doc.get('event_star') or {}).get('policy_params') or {}),
            'risk_point': point, 'risk_sha256': risk_sha, 'inputs': dict(sorted(inputs.items()))}


# ============================================================================================ run selection (R-1)

def candidate_of(job):
    """The select_stage candidate of a job line: launcher arm, policy parameters and envelope."""
    return {'arm': job['arm_name'], 'name': job.get('candidate') or job['arm_name'],
            'policy_params': dict(job.get('policy_params') or {}), 'envelope': job.get('envelope')}


@contextlib.contextmanager
def job_kappa_seed(job):
    """select_stage.matches compares a run's kappa and seed with p1_jobs.KAPPA / SEED (P1: 1.0 and 11); a job of
    another kappa or seed (P2, P5, P6) is matched with its own values for the duration of the call."""
    old = PJ.KAPPA, PJ.SEED
    PJ.KAPPA, PJ.SEED = float(job['kappa']), int(job['seed'])
    try:
        yield
    finally:
        PJ.KAPPA, PJ.SEED = old


def select_run(job, states=None, root=ROOT):
    """select_stage.job_outcome of one job line (states: select_stage.queue_states of its queue, None for a job file
    outside a queue); select_stage.SelectionError -> outcome 'error' (reported, never selected)."""
    with job_kappa_seed(job):
        try:
            return SS.job_outcome(job, job['route_id'], candidate_of(job), root=root, states=states)
        except SS.SelectionError as e:
            return {'job': job['id'], 'outcome': 'error', 'cause': str(e)}


def missing_outcome_reason(outcome):
    """Sec. 9.8 reason of a job without a selected run: not_launched (no attempt and no run directory), pending,
    agent_crashed, sim_failure, selection_error."""
    if outcome['outcome'] == 'pending' and not outcome.get('attempts_found') \
            and not (outcome.get('queue') or {}).get('attempts'):
        return 'not_launched'
    return OUTCOME_REASON[outcome['outcome']]


# ============================================================================================ labels

def validity_sources(run_dir):
    """{validity source: steps} over every step of raw/agent/framelease/jobs.jsonl."""
    out = {}
    for j in MV.read_jsonl(Path(run_dir) / 'raw' / 'agent' / 'framelease' / 'jobs.jsonl'):
        for s in j.get('steps') or []:
            src = (s.get('validity') or {}).get('source')
            if src is not None:
                out[src] = out.get(src, 0) + 1
    return out


ABLATION_DIR = 'ablation'           # GAP_AUDIT Sec. 2: the output directory .../ablation/<protocol arm>/...


def output_dir_arm(output_dir):
    """The protocol arm an output directory names (the component after 'ablation', GAP_AUDIT Sec. 2 'Recommended
    labelling'), '' when 'ablation' is its last component, None when it names none."""
    parts = Path(str(output_dir or '')).parts
    if ABLATION_DIR not in parts:
        return None
    i = parts.index(ABLATION_DIR)
    return parts[i + 1] if i + 1 < len(parts) else ''


def protocol_label(job, cfg, sources, rl=None, tuning=None):
    """(protocol arm, label source, [problems]) of one run (GAP_AUDIT Sec. 2 'Recommended labelling'; module
    docstring). cfg: the run's config.json; sources: validity_sources(); rl / tuning: load_rl_freeze /
    load_tuning_freeze or None. A job line's protocol_arm, and the arm its output directory names (output_dir_arm),
    must equal the label (the block spec is checked against the job line in check_specs)."""
    launcher = cfg.get('v4_arm')
    v4 = cfg.get('v4') or {}
    problems = []
    if GLOBAL_SHIELD in (launcher, v4.get('arm')):
        arm, src = GLOBAL_SHIELD, 'configuration arm name'
        if not isinstance((v4.get('extension') or {}).get('global_lease'), dict):
            problems.append('no extension global_lease block in the configuration')
        other = {k: n for k, n in sources.items() if k != GLOBAL_SOURCE}
        if other:
            problems.append(f'validity sources other than {GLOBAL_SOURCE!r}: {other}')
    elif launcher == 'fl_full':
        shas = sorted(set(((v4.get('utility') or {}).get('env_files_sha256') or {}).values()))
        arm, src = 'fl_full', 'network file sha256 -> RL freeze family'
        if rl is None:
            problems.append('no RL freeze given: the network family is unchecked')
        elif len(shas) != 1:
            problems.append(f'{len(shas)} network files recorded (expected 1)')
        else:
            arms = rl['by_sha'].get(shas[0]) or []
            if not arms:
                problems.append(f'network sha256 {shas[0]} is not in the RL freeze')
            elif len(arms) == 1:
                arm = arms[0]
            elif job.get('protocol_arm') in arms:
                arm, src = job['protocol_arm'], f'job line protocol_arm (network shared by {arms})'
            else:
                problems.append(f'network sha256 {shas[0]} is shared by {arms} and the job line names none')
    elif launcher == 'fl_heuristic' and tuning is not None and tuning.get('risk_sha256') \
            and cfg.get('envelope_sha256') == tuning['risk_sha256'] != tuning.get('L_star_sha256'):
        arm, src = 'fl_risk', 'envelope sha256 = the fl_risk lease point of the tuning freeze'
    else:
        arm, src = launcher, 'launcher arm'
        if job.get('protocol_arm') == 'fl_risk' and tuning is None:
            problems.append('no tuning freeze given: the fl_risk lease point is unchecked')
    if job.get('protocol_arm') and job['protocol_arm'] != arm:
        problems.append(f'job line protocol_arm {job["protocol_arm"]!r} != label {arm!r}')
    out_arm = output_dir_arm(job.get('output_dir'))
    if out_arm is not None and out_arm != arm:
        problems.append(f'output directory {job.get("output_dir")!r} names the arm {out_arm!r} != label {arm!r}')
    return arm, src, problems


# ============================================================================================ rows (R-1)

# metrics_v4 keys a test-route row keeps before the analysis freeze (Sec. 9.11: job health, timing and disk)
HEALTH_KEYS = ('run_dir', 'run_created_utc', 'run_status', 'timed_out', 'wall_s', 'valid_record', 'actor_log_bytes',
               'actor_log_ticks', 'actor_log_errors')
# the prefix timing a health-only row keeps (the charged-prefix and background-load checks of manipulation.py)
HEALTH_TIMING_KEYS = ('prefix_quantum_s_p50', 'prefix_quantum_s_p99', 'prefix_quantum_s_n', 'prefix_measured_s_p50')


def test_route_ids():
    """The 44 test routes of the registered split (interim_guard.registered_split: its sha256 is checked against the
    registration manifest)."""
    return G.test_routes()[0]


def health_only(job, test_routes):
    """True unless the job line declares a training route that the registered split does not list as a test route:
    test-route rows (and rows of job lines that do not declare training_route) are guarded, i.e. health-only before
    the analysis freeze (Sec. 9.11; interim_guard.release lifts it for the job lines a valid record covers)."""
    return not (job.get('training_route') is True and str(job['route_id']) not in test_routes)


def run_inputs(run_dir, cfg=None):
    """{path: sha256} of the run files a row reads (RUN_INPUTS that exist) and of the lease parameter file the realized
    pass reads (config.json agent_config.lease_params_path)."""
    run_dir = Path(run_dir)
    out = {PJ.rel(run_dir / n): PJ.sha256_file(run_dir / n) for n in RUN_INPUTS if (run_dir / n).is_file()}
    lp = ((cfg or {}).get('agent_config') or {}).get('lease_params_path')
    if lp and Path(lp).is_file():
        out[PJ.rel(lp)] = PJ.sha256_file(lp)
    return out


# modules the row-making functions import inside functions (realized pass, labels, depth limit, a_det depth, v2 arm
# derivation): hashed by path, with the imported modules of code_sha256
CODE_FILES = ('framelease_v4/arms/actor_log.py', 'framelease_v4/arms/arms_v4.py', 'framelease_v4/rl/behaviour.py',
              'framelease_v2/c2_eval.py', 'framelease_v2/lease.py', 'framelease_v2/geometry.py',
              'framelease_v2/aggregate_closed_loop.py')


def code_sha256():
    """{path: sha256} of this script, of the modules whose functions make the rows and of CODE_FILES."""
    from framelease_v2 import gpu_queue as Q
    from framelease_v4.arms import realized as RZ
    out = {PJ.rel(m.__file__): PJ.sha256_file(m.__file__)
           for m in (sys.modules[__name__], XM, CA, MC, G, MV, RZ, SS, CS, PJ, G.REG, Q)}
    out.update({p: PJ.sha256_file(ROOT / p) for p in CODE_FILES})
    return dict(sorted(out.items()))


def frozen_d_star(refs):
    """d* of the tuning freeze, else of the RL freeze, else None (extra_metrics then uses the run's own utility)."""
    for key in ('tuning', 'rl'):
        r = (refs or {}).get(key)
        if r and r.get('d_star') is not None:
            return int(r['d_star'])
    return None


ROW_ERRORS = XM.STEP_ERRORS        # a malformed log record: the step fails, the aggregation goes on
KM_FLOOR = XM.MIN_KM               # PROTOCOL Sec. 6.1: km driven = route length x RC / 100, floored at 0.001 km


def floor_km(fields):
    """fields with km_driven floored at KM_FLOOR (Sec. 6.1), the value runs.csv carries; collisions_per_km and
    infractions_per_km divide by the same floored value; a missing km_driven stays missing (Sec. 9.8)."""
    km = MV.num(fields.get('km_driven'))
    if km is not None:
        fields['km_driven'] = max(km, KM_FLOOR)
    return fields


def run_fields(job, run, arm, refs=None, health=False, released=False):
    """(metrics_v4 row or None, the row's metric and check fields) of one selected run: metrics_v4.run_metrics
    (realized=True), extra_metrics.extra_metrics (the R-1 metrics metrics_v4 lacks) and manipulation.run_checks (R-3).
    A health-only row (Sec. 9.11) keeps HEALTH_KEYS, the prefix timing (HEALTH_TIMING_KEYS) and the health checks.
    Fail closed: outcome fields of a run on a registered test route (by its job line or its configuration) need
    released (job_row passes the interim_guard.release decision); otherwise GuardRefused. A malformed log never stops
    the aggregation and never removes the run's other metrics: each step (load_logs, run_metrics, the steps of
    extra_metrics, timing_metrics, run_checks) is guarded (extra_metrics.guarded), a failed step leaves only its own
    columns empty, and the failures are recorded in extra_metrics_error ('step: Type: message; ...') and
    metric_steps_failed (the step names). Without logs (load_logs failed) no log-derived step runs (an empty log would
    give zero counts, i.e. imputed values)."""
    if not health and not released:
        cfg_route = ((MV.read_json(Path(run) / 'config.json') or {}).get('route') or {}).get('route_id')
        hit = {str(job['route_id']), str(cfg_route)} & G.test_routes()[0]
        if hit:
            raise GuardRefused(f'{PJ.rel(run)}: outcome fields of the test route {sorted(hit)} without a release by a '
                               'valid analysis-freeze record (PROTOCOL Sec. 9.11)')
    errors = []
    step = functools.partial(XM.guarded, errors)
    logs = step('load_logs', XM.load_logs, run)
    metrics = step('run_metrics', MV.run_metrics, run, realized=not health)
    if health:
        t = (step('timing_metrics', XM.timing_metrics, logs['jobs'], logs['events'], logs['decisions'])
             if logs else None) or {}
        fields = {k: (metrics or {}).get(k) for k in HEALTH_KEYS}
        fields.update({k: t.get(k) for k in HEALTH_TIMING_KEYS})
        if logs:
            fields.update(step('run_checks', MC.run_checks, job, run, logs, t.get('prefix_quantum_s_p50'), None, arm,
                               refs, health_only=True) or {})
    else:
        x = (step('extra_metrics', XM.extra_metrics, run, metrics, frozen_d_star(refs), logs=logs, errors=errors)
             if logs else None) or {}
        fields = floor_km({**(metrics or {}), **x})
        if logs:
            fields.update(step('run_checks', MC.run_checks, job, run, logs, x.get('prefix_quantum_s_p50'),
                               x.get('expired_ratio_after_first_commit'), arm, refs) or {})
    if errors:
        fields['extra_metrics_error'] = '; '.join(f'{n}: {m}' for n, m in errors)
        fields['metric_steps_failed'] = ','.join(n for n, _ in errors)
    return metrics, fields


def guard_fields(job, test_routes, release=None, run_route=None):
    """{'health_only', 'test_route', 'guard_note'} of one row (Sec. 9.11): a guarded row (health_only()) is health-only
    unless release (interim_guard.release: (released, note)) releases it; a selected run that recorded a test route
    keeps the row health-only unless released, whatever its job line declares (fail closed)."""
    route = str(job['route_id'])
    test = route in test_routes or (run_route is not None and str(run_route) in test_routes)
    guarded = health_only(job, test_routes) or test
    if not guarded:
        return {'health_only': False, 'test_route': False, 'guard_note': None}
    released, note = release or (False, 'pre_freeze: no valid analysis-freeze record (Sec. 9.11)')
    if run_route is not None and str(run_route) != route and str(run_route) in test_routes and not released:
        note = f'withheld: the run recorded the test route {run_route} (job line route {route})'
    return {'health_only': not released, 'test_route': test, 'guard_note': note}


def job_row(job, job_file, outcome, refs=None, test_routes=frozenset(), release=None):
    """(row, {run file: sha256}) of one job line: the selection fields, the code check (check_smoke.c_config), the
    protocol-arm label, the Sec. 9.11 guard fields (guard_fields; release: interim_guard.release of the job line), the
    metric and check fields (run_fields; outcome metrics only for rows that are not health-only) and the Sec. 9.8
    fields analysis_use / missing_reason."""
    refs = refs or {}
    q = outcome.get('queue') or {}
    row = {k: None for k in ID_COLUMNS}
    row.update(job=job['id'], job_file=PJ.rel(job_file), phase=job.get('phase'), block=job.get('block'),
               candidate=job.get('candidate'), route_id=str(job['route_id']), training_route=job.get('training_route'),
               kappa=float(job['kappa']), seed=int(job['seed']), launcher_arm=job['arm_name'],
               protocol_arm=job.get('protocol_arm') or job['arm_name'], label_source='job line (no run read)',
               outcome=outcome['outcome'],
               selection_note=outcome.get('warning') or outcome.get('cause'),
               attempts_found=outcome.get('attempts_found'), queue_attempts=q.get('attempts'),
               queue_counted=q.get('counted'), selected_run=outcome.get('run_dir'),
               **guard_fields(job, test_routes, release))
    if outcome['outcome'] != 'ok':
        row.update(analysis_use=False, missing_reason=missing_outcome_reason(outcome))
        return row, {}
    run = Path(outcome['run_dir'])
    run = run if run.is_absolute() else ROOT / run            # select_stage.read_run names it with p1_jobs.rel
    cc = CS.c_config(job, run)
    cfg = MV.read_json(run / 'config.json') or {}
    row.update(guard_fields(job, test_routes, release, (cfg.get('route') or {}).get('route_id')))
    arm, src, probs = protocol_label(job, cfg, validity_sources(run), refs.get('rl'), refs.get('tuning'))
    row.update(code_check=cc['status'], code_detail=cc['detail'], protocol_arm=arm, label_source=src,
               label_problem='; '.join(probs) or None)
    metrics, fields = run_fields(job, run, arm, refs, row['health_only'],
                                 G.note_category(row['guard_note']) == G.RELEASED)
    reasons = []
    if metrics is None or not metrics.get('valid_record'):     # a failed secondary step only empties its columns
        reasons.append('no_metrics')
    if cc['status'] != CS.PASS:
        reasons.append('code_mismatch')
    if probs:
        reasons.append('label_problem')
    if row['health_only']:
        reasons.append('health_only')
    row.update(analysis_use=not reasons, missing_reason=','.join(reasons) or None)
    row.update({k: v for k, v in fields.items() if k not in ID_COLUMNS})
    return row, run_inputs(run, cfg)


# ============================================================================================ R-2, R-3, guard

def job_run_dirs(job, root=ROOT):
    """Every run directory of a job line, all attempts (select_stage's matching rule with the job's kappa / seed)."""
    with job_kappa_seed(job):
        return [Path(r['path']) for r in SS._job_runs(job, job['route_id'], candidate_of(job), root)]


WITHHELD = 'WITHHELD'               # the R-2 status of a run directory whose audit the Sec. 9.11 guard withholds


def run_release(run_dir, notes, freeze=None, test_routes=frozenset()):
    """(released, guard_note) of the R-2 audit of one run directory (Sec. 9.11): notes are the guard_notes of the rows
    of the job lines it belongs to ([] for a run that matches no job line); a guarded row the freeze did not release
    withholds it (its note), otherwise the route its config.json records decides (interim_guard.release_run: a test
    route, or an unreadable one, is withheld before the freeze)."""
    for note in notes:
        if note is not None and G.note_category(note) != G.RELEASED:
            return False, note
    return G.release_run(freeze, G.recorded_route(run_dir), test_routes)


def commit_audit(jobs, root=ROOT, guard=None, freeze=None, test_routes=frozenset()):
    """(document, {resolved run directory: audit}, {run file: sha256}) of R-2 (commit_audit.py; PROTOCOL Sec. 7.6
    'Commit audit (all runs)'): every run directory of every job line (all attempts), and every other run directory
    under the job lines' output directories (runs that match no job line), each audited once. Sec. 9.11 (H5 is a
    registered outcome, Sec. 9.5): guard {job id: guard_note of its row} and freeze decide per run directory
    (run_release); a withheld run is listed with status WITHHELD and its guard_note only (not audited, no count, out of
    the totals); it is released together with its row. Status FAIL (any Eq. 9 violation), ERROR (no violation, but a
    run whose log could not be audited), INCOMPLETE (neither, but runs withheld: H5 cannot be judged yet), else PASS."""
    guard = guard or {}
    owners, out_dirs = {}, set()
    for job, _, _ in jobs:
        for d in job_run_dirs(job, root):
            owners.setdefault(str(d.resolve()), (d, []))[1].append(job['id'])
        out_dirs.add(Path(root) / job['output_dir'] / 'runs')
    for od in sorted(out_dirs):
        for d in (sorted(od.iterdir()) if od.is_dir() else []):
            if d.is_dir() and (d / 'config.json').is_file():
                owners.setdefault(str(d.resolve()), (d, []))
    by_path, inputs = {}, {}
    for key, (d, jids) in owners.items():
        released, note = run_release(d, [guard.get(j) for j in jids], freeze, test_routes)
        by_path[key] = ({**CA.audit_run(d), 'run_dir': PJ.rel(d), 'jobs': jids} if released else
                        {'run_dir': PJ.rel(d), 'jobs': jids, 'status': WITHHELD, 'guard_note': note})
        inputs.update(run_inputs(d, MV.read_json(d / 'config.json')))
    runs = sorted(by_path.values(), key=lambda a: a['run_dir'])
    audits = [a for a in runs if a['status'] != WITHHELD]
    totals = {k: sum(a['violations'][k] for a in audits) for k in CA.CHECKS}
    errors = sum(1 for a in audits if a['status'] == 'ERROR')
    withheld = len(runs) - len(audits)
    # H5 (Sec. 9.5) needs 0 violations in every run: a run whose log could not be audited, or a withheld run, is never
    # a pass
    status = 'FAIL' if any(totals.values()) else 'ERROR' if errors else 'INCOMPLETE' if withheld else 'PASS'
    doc = {'status': status, 'runs_audited': len(audits), 'runs_withheld': withheld, 'runs_error': errors,
           'runs_matching_no_job': sum(1 for a in runs if not a['jobs']),
           'runs_without_log': sum(1 for a in audits if a['status'] == 'NO_LOG'),
           'offers': sum(a['offers'] for a in audits), 'accepted': sum(a['accepted'] for a in audits),
           'events_only_commits': sum(a['events_only'] for a in audits),
           'margin_unrecorded': sum(a['margin_unrecorded'] for a in audits),
           'log_mismatches': sum(a['log_mismatches'] for a in audits), 'violations': totals,
           'runs': runs}
    return doc, by_path, inputs


def audit_columns(row, by_path):
    """commit_audit_status / _accepted / _violations of a row's selected run (None without one; WITHHELD and None for
    a health-only row or a withheld run, Sec. 9.11)."""
    a = by_path.get(str((ROOT / row['selected_run']).resolve())) if row.get('selected_run') else None
    if row.get('selected_run') and (row.get('health_only') or (a is not None and a['status'] == WITHHELD)):
        return {'commit_audit_status': WITHHELD, 'commit_audit_accepted': None, 'commit_audit_violations': None}
    return {'commit_audit_status': a and a['status'], 'commit_audit_accepted': a and a['accepted'],
            'commit_audit_violations': a and a['n_violations']}


def manipulation_checks(rows, refs=None):
    """R-3 across runs (manipulation.manipulation_summary; PROTOCOL Sec. 9.7, reported, not tested): fast prefix,
    charged prefix, configuration and the background-load check per protocol arm and kappa, the flagged runs,
    predicted vs observed expiry fallback, kappa scaling, P_both of fl_full and fl_heuristic. Per-run values are
    runs.csv columns (job_row)."""
    return MC.manipulation_summary(rows)


# one summary group: a protocol arm's candidate at one kappa and seed, in one phase and block, on one route split (the
# P1-0 smoke and the P1 ref runs, the P6 seed-12 replicates and seed 11, the tuning candidates are never pooled)
SUMMARY_KEYS = ('protocol_arm', 'candidate', 'kappa', 'seed', 'phase', 'block', 'split')


def _summary_order(key):
    return tuple((v is None, v if isinstance(v, (int, float)) else str(v)) for v in key)


def arm_summary(rows, split, freeze=None):
    """Cross-arm summary rows (metrics_v4.arm_summary per SUMMARY_KEYS group) of the rows the Sec. 9.11 guard lets a
    summary of split use (interim_guard.summary_rows: 'training' always; 'test' / 'all' only with a valid
    analysis-freeze record, otherwise GuardRefused)."""
    use = G.summary_rows(rows, split, freeze)
    groups = {}
    for r in use:
        key = tuple(r.get(k) for k in SUMMARY_KEYS[:-1]) + ('test' if r.get('test_route') else 'training',)
        groups.setdefault(key, []).append({**r, 'arm': '|'.join(map(str, key))})
    out = []
    for key in sorted(groups, key=_summary_order):
        for s in MV.arm_summary(groups[key]):
            out.append({**dict(zip(SUMMARY_KEYS, key)), **{k: v for k, v in s.items() if k != 'arm'}})
    return out


# ============================================================================================ aggregation

def counts(rows, key):
    out = {}
    for r in rows:
        out[str(r.get(key))] = out.get(str(r.get(key)), 0) + 1
    return dict(sorted(out.items()))


def checked_freeze(freeze):
    """The analysis-freeze record of interim_guard.load_freeze, verified again from its files (a hand-made or stale
    dictionary is refused: GuardRefused); None stays None."""
    if freeze is None:
        return None
    if not isinstance(freeze, dict) or any(not isinstance(freeze.get(k), str) for k in ('path', 'protocol', 'seal')):
        raise GuardRefused('the analysis-freeze record given is not a record loaded by interim_guard.load_freeze')
    again = G.load_freeze(ROOT / freeze['path'], ROOT / freeze['protocol'], ROOT / freeze['seal'],
                          required_job_files=freeze.get('required_job_files'))
    if again['sha256'] != freeze.get('sha256'):
        raise GuardRefused(f'analysis-freeze record {freeze["path"]}: sha256 {again["sha256"]} != the one given '
                           f'{freeze.get("sha256")}')
    return again


def aggregate(queues=(), job_files=(), specs=(), rl_freeze=None, tuning_freeze=None, allow_dev_freeze=False,
              root=ROOT, test_routes=None, freeze=None):
    """(rows, doc) of one aggregation (nothing written). AggregateError for inconsistent inputs (a job id listed
    twice, block specs that disagree with the job lines, a malformed freeze). Sec. 9.11: test_routes ADDS routes to
    the registered test routes (tests; it never removes one); freeze is a valid analysis-freeze record
    (interim_guard.load_freeze, verified again here), None before the analysis freeze; GuardRefused for an invalid
    record or a route split that differs from the registration manifest."""
    freeze = checked_freeze(freeze)
    routes, routes_info = G.test_routes(test_routes or ())
    jobs = collect_jobs(queues, job_files)
    if not jobs:
        raise AggregateError('no job lines')
    file_sha = {}
    for _, f, _ in jobs:
        file_sha.setdefault(PJ.rel(f), PJ.sha256_file(f))
    inputs = dict(file_sha)
    states = {}
    for q in queues:
        states[Path(q)] = SS.queue_states(q)
        inputs[PJ.rel(Path(q) / 'status.jsonl')] = PJ.sha256_file(Path(q) / 'status.jsonl')
    spec_docs = load_specs(specs)
    inputs.update({PJ.rel(p): PJ.sha256_file(p) for p, _ in spec_docs})
    where, problems = check_specs(spec_docs, jobs, file_sha)
    if problems:
        raise AggregateError('block specs disagree with the job lines:\n  ' + '\n  '.join(problems[:40]))
    refs = {'rl': load_rl_freeze(rl_freeze, allow_dev_freeze) if rl_freeze else None,
            'tuning': load_tuning_freeze(tuning_freeze) if tuning_freeze else None}
    for r in refs.values():
        if r:
            inputs.update({r['path']: r['sha256'], **(r.get('inputs') or {})})
    inputs[routes_info['path']] = routes_info['sha256']
    if routes_info.get('manifest'):                          # registered_split checks the split against it
        inputs[routes_info['manifest']] = routes_info['manifest_sha256']
    if freeze is not None:
        inputs.update({freeze['path']: freeze['sha256'], freeze['protocol']: freeze['protocol_sha256'],
                       freeze['seal']: PJ.sha256_file(ROOT / freeze['seal'])})
    rows = []
    for job, f, q in jobs:
        outcome = select_run(job, None if q is None else states[Path(q)], root)
        release = G.release(freeze, job, PJ.rel(f), file_sha[PJ.rel(f)], outcome)
        row, ins = job_row(job, f, outcome, refs, routes, release)
        row['block_spec'] = ','.join(where.get(job['id'], [])) or None
        rows.append(row)
        inputs.update(ins)
    audit, by_path, audit_inputs = commit_audit(jobs, root, {r['job']: r['guard_note'] for r in rows}, freeze,
                                                routes)
    inputs.update(audit_inputs)
    for r in rows:
        r.update(audit_columns(r, by_path))
    keep = ('job', 'route_id', 'kappa', 'launcher_arm', 'protocol_arm', 'outcome', 'missing_reason')
    doc = {'schema': SCHEMA, 'script': THIS_REL, 'script_sha256': PJ.sha256_file(Path(__file__)),
           'code_sha256': code_sha256(),
           'created': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
           'arguments': {'queues': [PJ.rel(q) for q in queues], 'job_files': [PJ.rel(f) for f in job_files],
                         'specs': [PJ.rel(p) for p in specs], 'rl_freeze': rl_freeze and PJ.rel(rl_freeze),
                         'tuning_freeze': tuning_freeze and PJ.rel(tuning_freeze),
                         'allow_dev_freeze': bool(allow_dev_freeze)},
           'references': refs, 'n_jobs': len(rows), 'n_analysis_use': sum(1 for r in rows if r['analysis_use']),
           'outcomes': counts(rows, 'outcome'), 'code_check': counts(rows, 'code_check'),
           'missing_reasons': counts(rows, 'missing_reason'),
           'missing': [{k: r[k] for k in keep} for r in rows if not r['analysis_use']],
           'code_mismatches': [{'job': r['job'], 'detail': r['code_detail']} for r in rows
                               if r['code_check'] not in (None, CS.PASS)],
           'label_problems': [{'job': r['job'], 'problem': r['label_problem']} for r in rows if r['label_problem']],
           'selection_notes': [{'job': r['job'], 'outcome': r['outcome'], 'note': r['selection_note']} for r in rows
                               if r['selection_note'] and r['outcome'] in ('ok', 'error')],
           'metric_errors': [{'job': r['job'], 'steps': r.get('metric_steps_failed'), 'error': r['extra_metrics_error'],
                              'analysis_use': r['analysis_use']} for r in rows if r.get('extra_metrics_error')],
           'commit_audit': audit, 'manipulation_checks': manipulation_checks(rows, refs),
           'interim_guard': G.guard_document(rows, freeze, routes_info), 'stubs': [],
           'job_files': dict(sorted(file_sha.items())), 'inputs': dict(sorted(inputs.items()))}
    return rows, doc


# ============================================================================================ outputs

OUTPUT_FILES = ('runs.csv', 'aggregate.json', 'SHA256SUMS', 'arm_summary.csv')   # the guard log is never replaced


def check_out_dir(out):
    """PermissionError for an output directory inside the code tree or another phase's directories (PROTECTED)."""
    rel = PJ.rel(out)
    if Path(rel).is_absolute():
        return
    if rel in ('.', 'outputs', 'outputs/framelease_v4') or rel in PROTECTED \
            or any(rel.startswith(p + '/') for p in PROTECTED) or rel.startswith(PROTECTED_PREFIXES):
        raise PermissionError(f'{rel}: the aggregator never writes there (PROTECTED)')


def _write_text(path, text):
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    tmp.replace(path)


def write_outputs(out, rows, doc, force=False, summary=None):
    """runs.csv, aggregate.json (doc plus the sha256 of the files written), SHA256SUMS and, when summary is given (the
    rows of arm_summary), arm_summary.csv under out; refuses (FileExistsError) to replace earlier outputs without
    force; with force an earlier arm_summary.csv that this call does not write is removed (it would no longer match
    aggregate.json). The guard log (interim_guard.jsonl) is never touched here. Returns the written document."""
    out = Path(out)
    check_out_dir(out)
    present = [n for n in OUTPUT_FILES if (out / n).exists()]
    if present and not force:
        raise FileExistsError(f'{PJ.rel(out)} already holds {present} (use --force to replace them)')
    out.mkdir(parents=True, exist_ok=True)
    MV.write_csv(out / 'runs.csv', rows)
    written = ['runs.csv']
    if summary is not None:
        if summary:
            MV.write_csv(out / 'arm_summary.csv', summary)
        else:
            _write_text(out / 'arm_summary.csv', ','.join(SUMMARY_KEYS) + '\n')
        written.append('arm_summary.csv')
    elif (out / 'arm_summary.csv').exists():
        (out / 'arm_summary.csv').unlink()
    doc = {**doc, 'outputs': {n: PJ.sha256_file(out / n) for n in written}}
    _write_text(out / 'aggregate.json', json.dumps(doc, indent=1, sort_keys=True, default=str) + '\n')
    names = written + ['aggregate.json']
    _write_text(out / 'SHA256SUMS', ''.join(f'{PJ.sha256_file(out / n)}  {n}\n' for n in sorted(names)))
    return doc


def summary_lines(doc, out):
    lines = [f'{doc["n_jobs"]} job lines, {doc["n_analysis_use"]} rows for analysis -> {PJ.rel(out)}',
             f'outcomes: {doc["outcomes"]}', f'code check: {doc["code_check"]}',
             f'missing reasons: {doc["missing_reasons"]}']
    lines += [f'LABEL {p["job"]}: {p["problem"]}' for p in doc['label_problems']]
    lines += [f'CODE {p["job"]}: {p["detail"]}' for p in doc['code_mismatches']]
    lines += [f'NOTE {p["job"]} ({p["outcome"]}): {p["note"]}' for p in doc['selection_notes']]
    lines += [f'METRICS {p["job"]}: {p["error"]}' for p in doc.get('metric_errors') or []]
    a = doc.get('commit_audit') or {}
    if a:
        lines.append(f'commit audit (R-2): {a["status"]}, {a["runs_audited"]} run directories audited, '
                     f'{a.get("runs_withheld", 0)} withheld (Sec. 9.11), {a["accepted"]} accepted commits of '
                     f'{a["offers"]} offers, violations {a["violations"]}, log mismatches {a["log_mismatches"]}')
    m = doc.get('manipulation_checks') or {}
    for name, v in (m.get('per_arm') or {}).items():
        lines.append(f'R-3 {name}: {v["runs"]} runs, fast prefix not PASS {v["fast_prefix_not_pass"]}, charged prefix '
                     f'FLAG {v["charged_prefix_flag"]}, background load {v["bg_load"]}, prefix p50/kappa '
                     f'{v["prefix_p50_per_kappa_s"]}, config {v["config"]}')
    g = doc.get('interim_guard') or {}
    if g:
        fz = g.get('freeze') or {}
        lines.append(f'interim guard (Sec. 9.11): {g["status"]}{" record " + fz["path"] if fz else ""}, '
                     f'{g["guarded_rows"]} guarded rows ({g["test_route_rows"]} test-route), {g["released_rows"]} '
                     f'released, {g["health_only_rows"]} health-only, notes {g["notes"]}')
        if fz and not fz.get('registered'):
            lines.append(f'WARNING: the analysis-freeze record is cited by a development copy {fz["protocol"]}, not '
                         'by the registered PROTOCOL.md')
        lines += [f'GUARD {w["job"]}: {w["note"]}' for w in g.get('withheld') or []]
        if g.get('summary'):
            lines.append(f'arm summary ({g["summary"]["split"]}): {g["summary"]["rows"]} rows -> arm_summary.csv')
    return lines


def write_freeze_record(path, record):
    """Write an analysis-freeze record (interim_guard.freeze_record) to a new file outside the protected directories;
    FileExistsError / PermissionError otherwise. Returns its sha256."""
    path = Path(path)
    check_out_dir(path.parent)
    if path.exists():
        raise FileExistsError(f'{PJ.rel(path)} exists (a freeze record is never replaced)')
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_text(path, json.dumps(record, indent=1, sort_keys=True) + '\n')
    return PJ.sha256_file(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--queue', action='append', default=[], help='gpu_queue directory (jobs.d/, status.jsonl)')
    ap.add_argument('--jobs', action='append', default=[], help='job file outside a queue')
    ap.add_argument('--specs', action='append', default=[], help='block spec or a directory of *.stage.json')
    ap.add_argument('--rl-freeze', help='p3_rl.py rl_freeze.json')
    ap.add_argument('--tuning-freeze', help='select_stage.py selection.json')
    ap.add_argument('--allow-dev-freeze', action='store_true', help='accept a development RL record (tests, smoke)')
    ap.add_argument('--analysis-freeze', help='a valid analysis-freeze record (interim_guard.py): releases the guarded '
                                              'rows of the job lines it covers (Sec. 9.11)')
    ap.add_argument('--required-job-files', metavar='FILE',
                    help='with --analysis-freeze: a JSON object {job file: sha256}, the registered tier 3-6 job files '
                         'of the test freeze (Sec. 8.1); a record that does not list each with that sha256 is refused')
    ap.add_argument('--arm-summary', choices=G.SUMMARY_SPLITS,
                    help='also write arm_summary.csv (protocol arm x kappa x route split); test / all are cross-arm '
                         'test-route summaries: refused (exit 4) and logged before the analysis freeze')
    ap.add_argument('--write-freeze-record', metavar='FILE',
                    help='write the analysis-freeze record of this aggregation to FILE (every job final); it is valid '
                         'only once its sha256 is entered in Sec. 13 of PROTOCOL.md and PROTOCOL.md is re-sealed')
    ap.add_argument('--cut-amendment', help='with --write-freeze-record: the amendment that records a cut (Sec. 10.2); '
                                            'the job lines never started are recorded as cut')
    ap.add_argument('--out', required=True)
    ap.add_argument('--force', action='store_true', help='replace earlier outputs in --out')
    a = ap.parse_args(argv)
    if not a.queue and not a.jobs:
        ap.error('give --queue or --jobs')
    if a.cut_amendment and not a.write_freeze_record:
        ap.error('--cut-amendment needs --write-freeze-record')
    if a.write_freeze_record and a.analysis_freeze:
        ap.error('--write-freeze-record makes a record from a guarded aggregation; it does not take one')
    if a.required_job_files and not a.analysis_freeze:
        ap.error('--required-job-files needs --analysis-freeze')
    argv = list(sys.argv if argv is None else [sys.argv[0], *argv])
    log = Path(a.out) / G.LOG_NAME
    params = {'arm_summary': a.arm_summary, 'analysis_freeze': a.analysis_freeze,
              'required_job_files': a.required_job_files, 'write_freeze_record': a.write_freeze_record,
              'out': PJ.rel(a.out)}

    def refuse(reason, code, freeze=None, logged=True):
        if logged:
            G.log_request(log, 'aggregate', 'refused', reason, freeze, argv, **params)
        where = f', logged in {PJ.rel(log)}' if logged else ''
        print(f'REFUSED{" (interim-look guard" + where + ")" if code == 4 else ""}: {reason}', file=sys.stderr)
        return code

    try:
        check_out_dir(a.out)
    except PermissionError as e:                       # nothing is written into a protected directory, not even a log
        return refuse(str(e), 1, logged=False)
    try:
        if a.write_freeze_record:
            check_out_dir(Path(a.write_freeze_record).parent)
            if Path(a.write_freeze_record).exists():
                raise FileExistsError(f'{a.write_freeze_record} exists (a freeze record is never replaced)')
        if not a.force and any((Path(a.out) / n).exists() for n in OUTPUT_FILES):
            raise FileExistsError(f'{a.out} already holds outputs (use --force to replace them)')
    except (PermissionError, FileExistsError) as e:
        return refuse(str(e), 1)
    freeze = None
    try:
        if a.analysis_freeze:
            required = None
            if a.required_job_files:
                required = MV.read_json(a.required_job_files)
                if not isinstance(required, dict) or not required:
                    raise GuardRefused(f'{a.required_job_files}: not a JSON object {{job file: sha256}}')
            freeze = G.load_freeze(a.analysis_freeze, required_job_files=required)
        reason = G.summary_refusal(a.arm_summary, freeze) if a.arm_summary else None
        if reason:
            raise GuardRefused(reason)
    except GuardRefused as e:
        return refuse(str(e), 4, freeze)
    G.log_request(log, 'aggregate', 'granted', None, freeze, argv, **params)
    try:
        rows, doc = aggregate(a.queue, a.jobs, a.specs, a.rl_freeze, a.tuning_freeze, a.allow_dev_freeze,
                              freeze=freeze)
        if a.required_job_files:
            doc['inputs'] = dict(sorted({**doc['inputs'], PJ.rel(a.required_job_files):
                                         PJ.sha256_file(a.required_job_files)}.items()))
        summary = arm_summary(rows, a.arm_summary, freeze) if a.arm_summary else None
    except GuardRefused as e:
        return refuse(str(e), 4, freeze)
    except (AggregateError, FileNotFoundError, ValueError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2
    try:
        record = G.freeze_record(rows, doc['job_files'], a.cut_amendment) if a.write_freeze_record else None
    except ValueError as e:                            # the freeze waits for every job (Sec. 9.12); nothing written
        G.log_request(log, 'write_freeze_record', 'refused', str(e), None, argv, **params)
        print(f'ERROR: no analysis-freeze record: {e}', file=sys.stderr)
        return 2
    doc['interim_guard']['summary'] = None if summary is None else {'split': a.arm_summary, 'rows': len(summary)}
    doc['interim_guard']['log'] = G.log_state(log)
    doc = write_outputs(a.out, rows, doc, force=a.force, summary=summary)
    for line in summary_lines(doc, a.out):
        print(line)
    if record is not None:
        sha = write_freeze_record(a.write_freeze_record, record)
        print(f'analysis-freeze record {PJ.rel(a.write_freeze_record)}: sha256 {sha}, {len(record["jobs"])} jobs, '
              f'trigger {record["trigger"]}. Not valid until this sha256 is entered as a dated entry in Sec. 13 of '
              'framelease_v4/PROTOCOL.md and PROTOCOL.md is re-sealed (registration.py --seal).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
