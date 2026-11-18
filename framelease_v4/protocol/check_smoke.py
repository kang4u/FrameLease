#!/usr/bin/env python3
"""Mechanical P1-0 smoke check (framelease_v4/PROTOCOL.md Sec. 8.1): may Phase 1 start? CPU only; reads the smoke job
file, the smoke run directories (outputs/framelease_v4/smoke_p1_0/<arm>/runs/, training route 18305 only) and,
with --queue, the runner's status.jsonl; writes only the report (--write).

  cd /home/kang/Desktop/DAC
  .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/check_smoke.py --queue outputs/framelease_v4/queue_p1
  .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/check_smoke.py --queue outputs/framelease_v4/queue_p1 --write

This script was written and its sha256 registered (PROTOCOL Sec. 12.2, outputs/framelease_v4/registration/
MANIFEST.sha256) BEFORE any smoke run existed; the report records this script's sha256 and whether it equals the
registered one, and the same for the smoke job file. The criteria and thresholds below are those of Sec. 8.1.

Which run directory is checked: per smoke job, the final run that framelease_v4/protocol/select_stage.job_outcome
resolves (with --queue: the runner's final record, or the first matching valid run; attempts the runner did not count
are ignored). A job without a final outcome makes the check INCOMPLETE. A final attempt without a valid official record
(Simulation crashed, Agent crashed, set-up / sensor failure, timeout, launch error) FAILS the smoke check: P1-0 needs a
valid official record or a driving-outcome failure for every run.

Criteria (each PASS, FAIL, DEFERRED or N/A per run; Sec. 8.1):
  route_record  metrics/result.json holds >= 1 official route record whose status is not an execution failure (a
                driving failure such as 'Failed - Agent got blocked' passes), raw/official_results.json exists, the
                launcher did not time out and its wall time is within --timeout-s (1410 s)
  config        config.json is the job's configuration (arm, route, kappa, seed, policy parameters, envelope sha256,
                the three fast-prefix options) and every pinned file the run recorded (manifest identity, frozen
                raw/source_v4|source_v3|source_fastprefix hashes) has the job's require_sha256; every pinned
                framelease_v4 file is among them
  summary_v4    raw/agent/framelease/summary.json has the 'v4' block (schema framelease_v4.arms.runtime/1, V4Runtime),
                >= 1 tick, and the 'fast_prefix' and 'actor_log' blocks
  fast_prefix   raw/agent/framelease/fast_prefix.json: stage 'final', validation ok, sdpa / gpu_preproc / lora_merged
                active, > 0 SDPA calls; the launcher reported no fast-prefix problem
  decisions     decisions.jsonl complete: every line parses, epochs are exactly 1..N with N >= 1 and N = the summary's
                decision count, every row carries the 32 v3 state features
  utility       age / shield arms: the agent's policy reports the configured utility (registered in the agent process)
                and every choice epoch (|A_feas| = 2) has reason 'both_feasible:<utility>' and the action of that utility
                (heuristic: REFINE; v4_adet_d<d>: REFINE iff depth < d); fl_behaviour: every choice epoch logs
                v4_mu = (1 - eps) 1[a = base] + eps / 2, v4_explore in {0, 1}, v4_base_action = a_det^d(depth) and
                v4_draw = 0, 1, 2, ...; without any choice epoch the behaviour logging is DEFERRED to the first P2 run
                (P1 runs no behaviour utility); other arms: N/A (no utility block)
  actor_log     actors.jsonl.gz decodes completely (no truncated gzip member), actor_log.json: enabled, 0 errors,
                bytes = the file size <= 2,100,000 (the 2,000,000 B budget + 5 % for the ego-only tail), ticks_logged =
                the decoded tick rows >= 1
  ego_found     the log header names the hero (id and a vehicle type) and every tick row carries its state
  pose_offset   estimated (agent GNSS + compass lidar2global) vs true (hero transform + official lidar2ego) LiDAR pose
                over the logged ticks with an estimate (>= 50 % of them), with the true position first mapped into the
                official agent's own route-anchored GNSS frame (amendment A1; framelease_v4/arms/agent_frame.py):
                planar offset p50 in [0.9, 1.9] m (the GNSS is mounted 1.4 m behind the vehicle origin; leaderboard
                GNSS noise about 0.5 m), p95 <= 3.0 m, |yaw difference| p50 <= 5 degrees; the raw world-frame offset
                is reported, not judged
  tick_wall     per-tick wall time: the agent's mean (ticks.jsonl wall_s) + the actor logger's p99 <= 0.20 s and the
                logger's p99 <= 0.05 s (one simulated tick). With the pilot's 90 s set-up and 0.12 s of evaluator time
                per tick, a 4000-tick (TickRuntime-limited) route then needs <= 90 + 4000 x 0.32 = 1370 s < 1410 s
  run_size      the run directory <= 20 MB (twice the 10 MB planning figure of Sec. 8.5)
Verdict: PASS if every run passes (DEFERRED allowed, listed in 'deferred_to_P2'); FAIL if any criterion of any run
fails; INCOMPLETE if a job has no final outcome yet and none failed. Exit codes: 0 PASS, 1 FAIL, 2 error, 3 INCOMPLETE.
P1 may start only after a PASS (the report's path and sha256 are entered in PROTOCOL Sec. 13.2). The smoke runs are
infrastructure checks: their driving scores are never used for any selection or for RL.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402
from framelease_v4.protocol import select_stage as SS  # noqa: E402

SCHEMA = 'framelease_v4.p1_smoke_check/1'
THIS_REL = 'framelease_v4/protocol/check_smoke.py'
SMOKE_JOB_FILE = PJ.JOBS_DIR / PJ.SMOKE_DIR / 'b00_smoke.jsonl'
REPORT_PATH = ROOT / PJ.SMOKE_REL / 'smoke_check.json'
REGISTRATION_MANIFEST = ROOT / 'outputs/framelease_v4/registration/MANIFEST.sha256'
CRITERIA = ('route_record', 'config', 'summary_v4', 'fast_prefix', 'decisions', 'utility', 'actor_log', 'ego_found',
            'pose_offset', 'tick_wall', 'run_size')
THRESHOLDS = {
    'launcher_timeout_s': float(PJ.TIMEOUT_S),
    'actor_log_max_bytes': 2_100_000,
    'pose_offset_p50_m': [0.9, 1.9],
    'pose_offset_p95_max_m': 3.0,
    'pose_yaw_p50_max_deg': 5.0,
    'pose_min_estimate_share': 0.5,
    'tick_wall_agent_mean_plus_logger_p99_max_s': 0.20,
    'actor_log_tick_p99_max_s': 0.05,
    'run_dir_max_mb': 20.0,
}
V4_RUNTIME_SCHEMA = 'framelease_v4.arms.runtime/1'
FAST_PREFIX_OPTIONS = tuple(PJ.FAST_PREFIX.split(','))
PASS, FAIL, DEFERRED, NA = 'PASS', 'FAIL', 'DEFERRED', 'N/A'


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def _res(status, detail='', **values):
    out = {'status': status, 'detail': detail}
    if values:
        out['values'] = values
    return out


def _q(values, p):
    import numpy as np
    a = np.asarray([v for v in values if v is not None and math.isfinite(v)], dtype=float)
    return float(np.quantile(a, p)) if a.size else None


def strict_jsonl(path):
    """(rows, problem): every non-empty line must parse (a cut or corrupt line is a problem, not silently dropped)."""
    rows = []
    try:
        lines = Path(path).read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeDecodeError) as e:
        return None, f'{Path(path).name} unreadable: {e}'
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError as e:
            return rows, f'{Path(path).name}: line {i} does not parse ({e})'
    return rows, None


def arm_kind(arm):
    from framelease_v4.arms import arms_v4 as AV
    return AV.ARMS[arm].kind


# ============================================================================================ criteria (one run)

def c_route_record(outcome, run):
    res = _read_json(run / 'metrics' / 'result.json') or {}
    vals = {'outcome': outcome['outcome'], 'route_status': res.get('route_status'),
            'route_records': res.get('route_records'), 'timed_out': res.get('timed_out'), 'wall_s': res.get('wall_s')}
    if outcome['outcome'] != 'ok':
        return _res(FAIL, f'no valid official record after the retry ({outcome.get("cause") or outcome.get("status")})',
                    **vals)
    if not (run / 'raw' / 'official_results.json').is_file():
        return _res(FAIL, 'raw/official_results.json missing', **vals)
    if res.get('timed_out'):
        return _res(FAIL, 'the launcher hit its wall-clock budget', **vals)
    wall = res.get('wall_s')
    if wall is None or float(wall) > THRESHOLDS['launcher_timeout_s']:
        return _res(FAIL, f'launcher wall time {wall} s not within {THRESHOLDS["launcher_timeout_s"]:.0f} s', **vals)
    return _res(PASS, f'{res.get("route_status")}', **vals)


def _recorded_hashes(run):
    """{relative path: sha256} the run recorded: manifest identity code hashes and the frozen source hashes."""
    out = {}
    man = _read_json(run / 'manifest.json') or {}
    for path, sha in ((man.get('identity') or {}).get('code') or {}).items():
        out[PJ.rel(path)] = sha
    for sub in ('source_v4', 'source_v3', 'source_fastprefix'):
        for rel, sha in (_read_json(run / 'raw' / sub / 'hashes.json') or {}).items():
            if '/' in rel:
                out.setdefault(rel, sha)
                if out[rel] != sha:
                    out[rel] = f'conflict: {out[rel]} vs {sha}'
    return out


def c_config(job, run):
    cfg = _read_json(run / 'config.json') or {}
    problems = []
    want = {'v4_arm': job['arm_name'], 'route': job['route_id'], 'kappa': job['kappa'], 'seed': job['seed']}
    got = {'v4_arm': cfg.get('v4_arm'), 'route': str((cfg.get('route') or {}).get('route_id')),
           'kappa': cfg.get('kappa'), 'seed': cfg.get('seed')}
    for k in want:
        if str(want[k]) != str(got[k]):
            problems.append(f'{k} {got[k]!r} != {want[k]!r}')
    pp = dict((((cfg.get('v4') or {}).get('agent') or {}).get('policy_params')) or {})
    for k, v in (job['policy_params'] or {}).items():
        if pp.get(k) != v:
            problems.append(f'policy parameter {k}: {pp.get(k)!r} != {v!r}')
    if job.get('envelope') and cfg.get('envelope_sha256') != job['envelope']['sha256']:
        problems.append('envelope sha256 differs from the job')
    if list((cfg.get('fast_prefix') or {}).get('options') or []) != list(FAST_PREFIX_OPTIONS):
        problems.append(f'fast-prefix options {(cfg.get("fast_prefix") or {}).get("options")}')
    rec = _recorded_hashes(run)
    mism, checked = [], 0
    for rel, sha in sorted(job['require_sha256'].items()):
        if rel in rec:
            checked += 1
            if rec[rel] != sha:
                mism.append(rel)
    v4_missing = [rel for rel in job['require_sha256'] if rel.startswith('framelease_v4/') and rel not in rec]
    if mism:
        problems.append(f'recorded sha256 differs from the pins: {mism[:5]}')
    if v4_missing:
        problems.append(f'pinned framelease_v4 files not recorded by the run: {v4_missing[:5]}')
    vals = {'pins': len(job['require_sha256']), 'pins_recorded_by_run': checked}
    return _res(FAIL if problems else PASS, '; '.join(problems) or f'{checked} pinned files recorded and equal', **vals)


def c_summary(summary):
    if summary is None:
        return _res(FAIL, 'raw/agent/framelease/summary.json missing (the agent did not reach destroy)')
    v4 = summary.get('v4') or {}
    problems = []
    if v4.get('schema') != V4_RUNTIME_SCHEMA or v4.get('runtime_class') != 'V4Runtime':
        problems.append(f'v4 block {v4.get("schema")!r} / {v4.get("runtime_class")!r}')
    if not int(v4.get('ticks') or 0) >= 1:
        problems.append('no control tick')
    for k in ('fast_prefix', 'actor_log'):
        if not isinstance(summary.get(k), dict):
            problems.append(f'no {k!r} block')
    return _res(FAIL if problems else PASS, '; '.join(problems) or 'v4 block present',
                ticks=v4.get('ticks'), decisions=v4.get('decisions'), p_both=v4.get('p_both'),
                deadline_miss_ratio=v4.get('deadline_miss_ratio'))


def c_fast_prefix(run):
    fp = _read_json(run / 'raw' / 'agent' / 'framelease' / 'fast_prefix.json')
    if fp is None:
        return _res(FAIL, 'fast_prefix.json missing')
    body = fp.get('fast_prefix') or {}
    val = body.get('validation') or {}
    active = body.get('active') or {}
    sdpa = ((fp.get('stats') or body.get('stats') or {}).get('sdpa') or {}).get('sdpa_calls')
    problems = []
    if fp.get('stage') != 'final':
        problems.append(f'stage {fp.get("stage")!r} != final')
    if val.get('ok') is not True:
        problems.append(f'validation not passed ({val.get("failures")})')
    off = [o for o in FAST_PREFIX_OPTIONS if not active.get(o)]
    if off:
        problems.append(f'options not active: {off}')
    if not (isinstance(sdpa, (int, float)) and sdpa > 0):
        problems.append(f'SDPA calls {sdpa!r}')
    res = _read_json(run / 'metrics' / 'result.json') or {}
    lp = ((res.get('fast_prefix') or {}).get('problems'))
    if lp:
        problems.append(f'launcher: {lp}')
    return _res(FAIL if problems else PASS, '; '.join(problems) or 'final, validated, all options active',
                stage=fp.get('stage'), sdpa_calls=sdpa)


def c_decisions(run, summary, rows, problem):
    from framelease_v3.runtime.v3_scheduler import FEATURE_NAMES
    if rows is None:
        return _res(FAIL, problem or 'decisions.jsonl missing')
    if problem:
        return _res(FAIL, problem)
    n = len(rows)
    want = ((summary or {}).get('v4') or {}).get('decisions')
    problems = []
    if n < 1:
        problems.append('no decision row')
    if [r.get('epoch') for r in rows] != list(range(1, n + 1)):
        problems.append('epochs are not 1..N')
    if want is None or int(want) != n:
        problems.append(f'{n} rows != summary decisions {want}')
    bad = [r.get('epoch') for r in rows if not isinstance(r.get('features'), dict)
           or any(k not in r['features'] for k in FEATURE_NAMES)]
    if bad:
        problems.append(f'rows without the {len(FEATURE_NAMES)} v3 features: epochs {bad[:5]}')
    return _res(FAIL if problems else PASS, '; '.join(problems) or f'{n} rows, complete', rows=n, summary_decisions=want)


def c_utility(job, run, summary, rows):
    from framelease_v3.runtime import v3_shield as VS
    from framelease_v4.rl import behaviour as B
    kind = arm_kind(job['arm_name'])
    cfg = _read_json(run / 'config.json') or {}
    if kind not in ('age', 'shield'):
        if (cfg.get('v4') or {}).get('utility'):
            return _res(FAIL, 'a utility block in a non-utility arm')
        return _res(NA, 'no utility (v2-rule / event arm)')
    name = (job['policy_params'] or {}).get('utility') or 'heuristic'
    got = ((summary or {}).get('policy') or {}).get('utility')
    if got != name:
        return _res(FAIL, f'the agent\'s policy reports utility {got!r}, configured {name!r}')
    choice = [r for r in (rows or []) if r.get('p_both') is True]
    problems = []
    beh = B.parse_behaviour(name)
    d = B.MAX_DEPTH if name == 'heuristic' else (beh[2] if beh else int(name.rsplit('_d', 1)[1]))
    for r in choice:
        if r.get('reason') != f'both_feasible:{name}':
            problems.append(f'epoch {r.get("epoch")}: reason {r.get("reason")!r}')
            break
    if beh is None:
        for r in choice:
            exp = B.a_det_action((r.get('features') or {}).get('depth', r.get('depth')), d)
            if r.get('action') != exp:
                problems.append(f'epoch {r.get("epoch")}: action {r.get("action")} != a_det^{d} {exp}')
                break
        if problems:
            return _res(FAIL, '; '.join(problems), utility=got, choice_epochs=len(choice))
        return _res(PASS, f'utility {got} registered in the agent; {len(choice)} choice epochs consistent',
                    utility=got, choice_epochs=len(choice))
    eps = beh[0]
    draws = []
    for r in choice:
        f = r.get('features') or {}
        mu, ex, base, draw = (f.get(k) for k in B.LOG_KEYS)
        if not (isinstance(mu, (int, float)) and 0.0 < float(mu) <= 1.0) or ex not in (0, 1) \
                or base not in (VS.REFINE, VS.REFRESH) or not isinstance(draw, int):
            problems.append(f'epoch {r.get("epoch")}: behaviour keys {[mu, ex, base, draw]}')
            break
        if base != B.a_det_action(f.get('depth', r.get('depth')), d):
            problems.append(f'epoch {r.get("epoch")}: v4_base_action {base} is not a_det^{d}')
            break
        if abs(float(mu) - ((1.0 - eps) * float(r.get('action') == base) + eps / 2.0)) > 1e-9:
            problems.append(f'epoch {r.get("epoch")}: v4_mu {mu} inconsistent with eps {eps}')
            break
        draws.append(draw)
    if not problems and draws != list(range(len(draws))):
        problems.append('v4_draw is not 0, 1, 2, ... over the choice epochs')
    if problems:
        return _res(FAIL, '; '.join(problems), utility=got, choice_epochs=len(choice))
    if not choice:
        return _res(DEFERRED, 'behaviour utility registered in the agent, but no choice epoch in this run: the '
                              'v4_mu logging is checked on the first P2 run', utility=got, choice_epochs=0)
    return _res(PASS, f'behaviour utility registered; {len(choice)} choice epochs log v4_mu', utility=got,
                choice_epochs=len(choice), explored=sum(int((r.get('features') or {}).get('v4_explore') or 0)
                                                        for r in choice))


def _actor_log(run):
    from framelease_v4.arms import actor_log as AL
    fl = run / 'raw' / 'agent' / 'framelease'
    path, man_path = fl / AL.FILE_NAME, fl / AL.MANIFEST_NAME
    if not path.is_file():
        return None, None, f'{AL.FILE_NAME} missing'
    try:
        log = AL.read_actor_log(path)
    except Exception as e:  # noqa: BLE001  a corrupt log is a FAIL, not a crash of the check
        return None, None, f'{AL.FILE_NAME} does not decode: {type(e).__name__}: {e}'
    return log, _read_json(man_path), None


def c_actor_log(run, log, man, problem):
    if problem:
        return _res(FAIL, problem)
    size = (run / 'raw' / 'agent' / 'framelease' / 'actors.jsonl.gz').stat().st_size
    problems = []
    if log.truncated:
        problems.append('a truncated gzip member')
    if not isinstance(man, dict):
        problems.append('actor_log.json missing')
        man = {}
    else:
        if man.get('enabled') is not True:
            problems.append(f'disabled ({man.get("disabled_reason")})')
        if man.get('errors'):
            problems.append(f'{man.get("errors")} logger errors')
        if man.get('bytes') != size:
            problems.append(f'manifest bytes {man.get("bytes")} != file size {size}')
        if man.get('ticks_logged') != log.n_ticks:
            problems.append(f'ticks_logged {man.get("ticks_logged")} != {log.n_ticks} decoded tick rows')
    if size > THRESHOLDS['actor_log_max_bytes']:
        problems.append(f'{size} B > {THRESHOLDS["actor_log_max_bytes"]} B')
    if log.n_ticks < 1:
        problems.append('no tick row')
    return _res(FAIL if problems else PASS, '; '.join(problems) or f'{size} B, {log.n_ticks} tick rows',
                bytes=size, tick_rows=log.n_ticks, stride=man.get('stride'),
                decimation_events=len(man.get('decimation_events') or []), catalog=man.get('catalog'))


def c_ego(log, problem):
    if problem:
        return _res(FAIL, problem)
    hero = (log.header or {}).get('hero') or {}
    problems = []
    if not log.header:
        problems.append('no header line')
    if hero.get('id') is None:
        problems.append('hero id missing')
    if not str(hero.get('ty') or '').startswith('vehicle.'):
        problems.append(f'hero type {hero.get("ty")!r}')
    if log.n_ticks < 1 or any(not isinstance(r.get('e'), list) or len(r['e']) != 5 for r in log.ticks):
        problems.append('tick rows without the hero state')
    return _res(FAIL if problems else PASS, '; '.join(problems) or f'hero {hero.get("id")} ({hero.get("ty")})',
                hero_id=hero.get('id'), hero_type=hero.get('ty'))


def c_pose(log, problem, run=None):
    """Amendment A1 (PROTOCOL Sec. 13.2): the true LiDAR position is first mapped into the official agent's own
    GNSS frame (framelease_v4.arms.agent_frame: official init() fsolve on the route's first waypoint, official
    gps_to_location, map geoReference). That frame is route-anchored (Town12: x_agent = x_world - x_first). The
    thresholds are those registered in version 1.2. The raw world-frame offset is reported, not judged."""
    import numpy as np
    from framelease_v4.arms import agent_frame as AF
    if problem:
        return _res(FAIL, problem)
    est, true = log.lidar_pose_estimate(), log.lidar_pose_true()
    ok = np.isfinite(est).all(axis=1) & np.isfinite(true).all(axis=1)
    share = float(ok.mean()) if len(ok) else 0.0
    if share < THRESHOLDS['pose_min_estimate_share']:
        return _res(FAIL, f'only {share:.0%} of the logged ticks carry the agent\'s pose estimate', estimate_share=share)
    try:
        frame = AF.frame_for_run_config(_read_json(Path(run) / 'config.json') or {} if run is not None else {})
    except Exception as e:  # noqa: BLE001  no frame, no comparison: the criterion fails with the reason
        return _res(FAIL, f'agent frame unavailable: {type(e).__name__}: {e}', estimate_share=share)
    mapped = frame.map_xy(true[ok, :2])
    raw = np.hypot(est[ok, 0] - true[ok, 0], est[ok, 1] - true[ok, 1])
    d = np.hypot(est[ok, 0] - mapped[:, 0], est[ok, 1] - mapped[:, 1])
    dyaw = np.degrees(np.abs((est[ok, 2] - true[ok, 2] + np.pi) % (2 * np.pi) - np.pi))
    p50, p95, y50 = float(np.median(d)), float(np.quantile(d, 0.95)), float(np.median(dyaw))
    lo, hi = THRESHOLDS['pose_offset_p50_m']
    problems = []
    if not lo <= p50 <= hi:
        problems.append(f'offset p50 {p50:.3f} m outside [{lo}, {hi}] m')
    if p95 > THRESHOLDS['pose_offset_p95_max_m']:
        problems.append(f'offset p95 {p95:.3f} m > {THRESHOLDS["pose_offset_p95_max_m"]} m')
    if y50 > THRESHOLDS['pose_yaw_p50_max_deg']:
        problems.append(f'yaw difference p50 {y50:.2f} deg > {THRESHOLDS["pose_yaw_p50_max_deg"]} deg')
    return _res(FAIL if problems else PASS, '; '.join(problems) or f'offset p50 {p50:.3f} m, p95 {p95:.3f} m',
                offset_p50_m=p50, offset_p95_m=p95, offset_max_m=float(d.max()), yaw_p50_deg=y50,
                estimate_share=share, raw_world_offset_p50_m=float(np.median(raw)), agent_frame=frame.summary())


def c_tick_wall(run, man):
    rows, problem = strict_jsonl(run / 'raw' / 'agent' / 'framelease' / 'ticks.jsonl')
    if rows is None or problem:
        return _res(FAIL, problem or 'ticks.jsonl missing')
    walls = [float(r['wall_s']) for r in rows if isinstance(r.get('wall_s'), (int, float))]
    if not walls:
        return _res(FAIL, 'no per-tick wall time in ticks.jsonl')
    mean = sum(walls) / len(walls)
    lp99 = ((man or {}).get('wall_s') or {}).get('p99')
    if not isinstance(lp99, (int, float)):
        return _res(FAIL, 'the actor log reports no per-tick wall time', agent_mean_s=mean)
    problems = []
    if mean + lp99 > THRESHOLDS['tick_wall_agent_mean_plus_logger_p99_max_s']:
        problems.append(f'agent mean {mean:.4f} s + logger p99 {lp99:.4f} s > '
                        f'{THRESHOLDS["tick_wall_agent_mean_plus_logger_p99_max_s"]} s')
    if lp99 > THRESHOLDS['actor_log_tick_p99_max_s']:
        problems.append(f'logger p99 {lp99:.4f} s > {THRESHOLDS["actor_log_tick_p99_max_s"]} s')
    return _res(FAIL if problems else PASS, '; '.join(problems) or f'agent mean {mean:.4f} s, logger p99 {lp99:.4f} s',
                ticks=len(walls), agent_mean_s=mean, agent_p95_s=_q(walls, 0.95), agent_max_s=max(walls),
                logger_p50_s=((man or {}).get('wall_s') or {}).get('p50'), logger_p99_s=lp99,
                logger_max_s=((man or {}).get('wall_s') or {}).get('max'))


def c_run_size(run):
    size = sum(f.stat().st_size for f in run.rglob('*') if f.is_file())
    mb = size / 1e6
    ok = mb <= THRESHOLDS['run_dir_max_mb']
    return _res(PASS if ok else FAIL, f'{mb:.2f} MB' + ('' if ok else f' > {THRESHOLDS["run_dir_max_mb"]} MB'), mb=mb)


def check_run(job, outcome, run):
    """{criterion: result} for one final smoke run directory."""
    out = {'route_record': c_route_record(outcome, run)}
    fl = run / 'raw' / 'agent' / 'framelease'
    summary = _read_json(fl / 'summary.json')
    rows, problem = strict_jsonl(fl / 'decisions.jsonl') if (fl / 'decisions.jsonl').is_file() else (None, None)
    log, man, lproblem = _actor_log(run)
    steps = (('config', lambda: c_config(job, run)), ('summary_v4', lambda: c_summary(summary)),
             ('fast_prefix', lambda: c_fast_prefix(run)),
             ('decisions', lambda: c_decisions(run, summary, rows, problem)),
             ('utility', lambda: c_utility(job, run, summary, rows)),
             ('actor_log', lambda: c_actor_log(run, log, man, lproblem)), ('ego_found', lambda: c_ego(log, lproblem)),
             ('pose_offset', lambda: c_pose(log, lproblem, run)), ('tick_wall', lambda: c_tick_wall(run, man)),
             ('run_size', lambda: c_run_size(run)))
    for name, fn in steps:
        try:
            out[name] = fn()
        except Exception as e:  # noqa: BLE001  a malformed artefact fails its criterion, never the whole check
            out[name] = _res(FAIL, f'check raised {type(e).__name__}: {e}')
    return out


# ============================================================================================ all smoke jobs

def load_jobs(path=SMOKE_JOB_FILE):
    jobs = [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines() if x.strip()]
    train = PJ.training_routes()
    t22 = set(PJ.route_set('T22'))
    for j in jobs:
        if j.get('phase') != 'P1-0' or j.get('block') != 'smoke':
            raise ValueError(f'{j.get("id")}: not a P1-0 smoke job')
        if j['route_id'] not in train or j['route_id'] in t22:
            raise PermissionError(f'{j["id"]}: the smoke route must be a training route outside T22')
        if not str(j['output_dir']).startswith(PJ.SMOKE_REL + '/'):
            raise PermissionError(f'{j["id"]}: output directory outside {PJ.SMOKE_REL}')
    return jobs


def registered_hashes(path=REGISTRATION_MANIFEST):
    """{path: sha256} of the registration manifest (sha256sum format), {} if it does not exist."""
    out = {}
    p = Path(path)
    if not p.is_file():
        return out
    for line in p.read_text(encoding='utf-8').splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and len(parts[0]) == 64:
            out[parts[1].strip()] = parts[0]
    return out


def check(jobs, root=ROOT, queue_dir=None, job_file=SMOKE_JOB_FILE, registration=REGISTRATION_MANIFEST):
    states = SS.queue_states(queue_dir)
    per_job, deferred = [], []
    for j in jobs:
        cand = {'name': j['candidate'], 'arm': j['arm_name'], 'policy_params': j['policy_params'],
                'envelope': j.get('envelope')}
        outcome = SS.job_outcome(j, j['route_id'], cand, root, states)
        row = {'job': j['id'], 'arm': j['arm_name'], 'utility': (j['policy_params'] or {}).get('utility'),
               'outcome': outcome['outcome'], 'run_dir': outcome.get('run_dir'),
               'attempts_found': outcome.get('attempts_found'), 'queue': outcome.get('queue')}
        if outcome['outcome'] == 'pending':
            row.update(status='INCOMPLETE', cause=outcome.get('cause'), criteria={})
        elif outcome.get('run_dir') is None:
            row.update(status=FAIL, criteria={'route_record': _res(FAIL, f'no run directory '
                                                                         f'({outcome.get("cause")})')})
        else:
            run = SS._abs(outcome['run_dir'], root)
            crit = check_run(j, outcome, run)
            row['criteria'] = crit
            row['status'] = FAIL if any(c['status'] == FAIL for c in crit.values()) else PASS
            deferred += [f'{j["id"]}: {k}: {c["detail"]}' for k, c in crit.items() if c['status'] == DEFERRED]
        per_job.append(row)
    if any(r['status'] == FAIL for r in per_job):
        verdict = 'FAIL'
    elif any(r['status'] == 'INCOMPLETE' for r in per_job):
        verdict = 'INCOMPLETE'
    else:
        verdict = 'PASS'
    reg = registered_hashes(registration)
    this_sha = PJ.sha256_file(Path(__file__))
    job_rel = PJ.rel(job_file)
    job_sha = PJ.sha256_file(job_file)
    return {'schema': SCHEMA, 'verdict': verdict,
            'gate': 'Phase 1 may start only after a PASS (PROTOCOL Sec. 8.1); the report path and sha256 go into '
                    'PROTOCOL Sec. 13.2',
            'jobs': per_job, 'deferred_to_P2': deferred, 'thresholds': THRESHOLDS, 'criteria': list(CRITERIA),
            'queue': PJ.rel(queue_dir) if queue_dir else None,
            'job_file': job_rel, 'job_file_sha256': job_sha, 'job_file_registered': reg.get(job_rel) == job_sha,
            'script': THIS_REL, 'script_sha256': this_sha, 'script_registered': reg.get(THIS_REL) == this_sha,
            'registration_manifest': PJ.rel(registration) if Path(registration).is_file() else None,
            'written': time.strftime('%Y-%m-%dT%H:%M:%S%z')}


def summary_lines(rep):
    L = [f'P1-0 smoke check: {rep["verdict"]}  (checker registered: {rep["script_registered"]}, job file registered: '
         f'{rep["job_file_registered"]})']
    for r in rep['jobs']:
        bad = [f'{k}: {c["detail"]}' for k, c in (r.get('criteria') or {}).items() if c['status'] in (FAIL, DEFERRED)]
        L.append(f'  {r["status"]:<10} {r["job"]:<62} {r["outcome"]:<14}' + ('' if not bad else '  ' + ' | '.join(bad)))
        if r['status'] == 'INCOMPLETE':
            L.append(f'             {r.get("cause")}')
    for d in rep['deferred_to_P2']:
        L.append(f'  deferred to the first P2 run: {d}')
    return L


def write_report(rep, path=REPORT_PATH, force=False):
    path = Path(path)
    if path.exists() and not force:
        old = _read_json(path) or {}
        if {k: v for k, v in old.items() if k != 'written'} != {k: v for k, v in rep.items() if k != 'written'}:
            raise FileExistsError(f'refusing to overwrite {path} with a different report (use --force)')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rep, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--queue', type=Path, default=None, help='gpu_queue directory of the smoke block (status.jsonl)')
    ap.add_argument('--jobs-file', type=Path, default=SMOKE_JOB_FILE)
    ap.add_argument('--write', action='store_true', help=f'write the report ({PJ.rel(REPORT_PATH)})')
    ap.add_argument('--report', type=Path, default=REPORT_PATH)
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args(argv)
    try:
        jobs = load_jobs(a.jobs_file)
        rep = check(jobs, ROOT, a.queue, a.jobs_file)
        print('\n'.join(summary_lines(rep)))
        if a.write:
            path = write_report(rep, a.report, a.force)
            print(f'wrote {path}  sha256 {PJ.sha256_file(path)}')
    except (SS.SelectionError, FileNotFoundError, FileExistsError, ValueError, KeyError, PermissionError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2
    return {'PASS': 0, 'FAIL': 1, 'INCOMPLETE': 3}[rep['verdict']]


if __name__ == '__main__':
    raise SystemExit(main())
