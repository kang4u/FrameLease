#!/usr/bin/env python3
"""Phase-2 job file of framelease_v4/PROTOCOL.md: the offline-RL data block (Secs. 5.3, 8.1-8.4, 8.6), in the
framelease_v2/gpu_queue.py format. WRITTEN, NEVER LAUNCHED OR ENQUEUED: the files go to
outputs/framelease_v4/p2_jobs/FULL/ (not a queue jobs.d/ directory; any path inside a queue is refused), so no runner
picks them up; this script never starts a job, CARLA or the GPU.

  cd /home/kang/Desktop/DAC
  .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/p2_jobs.py               # the block, nothing checked
  source linux/env.sh && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 nice -n 19 ionice -c 3 \
      .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/p2_jobs.py --check --write   # validate, then write

Input (PROTOCOL Secs. 4.9, 5.3): the tuning freeze outputs/framelease_v4/tuning/selection.json (select_stage.py
--variant FULL --freeze --write; schema framelease_v4.tuning_selection/1), which fixes L* (the lease envelope) and d*
(the heuristic depth), and the run list of framelease_v4/rl/collection_plan.py plan(variant FULL, eps 0.3, kappa
{1.0, 1.5, 2.0}, d_det = d*, envelope = L*). The freeze is refused unless its sha256 is cited in PROTOCOL.md Sec. 13.2
(Sec. 4.9: its hash is entered in Sec. 13 before Phase 2 starts; the P1 driver writes that entry) and PROTOCOL.md is
the sealed version (outputs/framelease_v4/registration/SEAL.sha256). L* must be an exported, verified envelope
(outputs/framelease_v4/envelopes/manifest.json) and d* a depth of the registered heuristic grid {10, 4, 1}. Only the
registered variant FULL has a P2 block here (TRIMMED, Sec. 14, is not registered).

The block (132 lines; block number 10, the first after the P1 blocks 0-9 of Sec. 8.2; not registered, so it is
entered in Sec. 13.2 with the job file):
  arm fl_behaviour (V4Runtime, shield depth limit 10, fast prefix, actor log; Sec. 5.3) with the behaviour utility
  v4_eps0.300_seed<s>[_d<d*>] around a_det^{d*}, seed s = collection_plan.behaviour_seed(route, kappa, rep 0)
  (Sec. 2.6), on the 44 training routes (Sec. 3.2, subset RL; never a test route, Sec. 3.3) x kappa {1.0, 1.5, 2.0} x
  seed 11.
Every line (Secs. 8.2-8.3): the plan's launcher arguments (framelease_v4/arms/run_closed_loop_v4.py, explicit
--fast-prefix sdpa,gpu_preproc,lora_merged, --envelope L*, --policy-params, --kappa, --seed 11, --timeout-s 1410 =
the 1500 s wall cap - 90 s, --lock-wait-s 600) after [python, -B]; tier 2; wall_cap_s 1500; id
v4p2_fl_behaviour_<L*>_eps0.300_d<d*>_k<kappa>_s11_r<route>; output directory outputs/framelease_v4/rl_data/k<kappa>
(Sec. 8.6); require_sha256 = framelease_v4/arms/jobs_v4.code_pins([L*]) (the 49 code files of Sec. 8.3 and the
envelope). Order (Sec. 8.2 with the kappas in the place of the arms): the id-sorted routes shuffled with
random.Random(20261110 + 10); the 3 kappas of a route back to back, in the order (1.0, 1.5, 2.0) rotated by one
position per route (p1_jobs.ordered), so every prefix of the block is balanced over kappa (the per-kappa counts differ
by at most 1); CARLA port 2600 + 10 (i mod 4) for line i, recomputed after the ordering.

--check validates every line before anything is written: gpu_queue's job contract, the pins against the tree and
against jobs_v4.code_pins([L*]), training routes only, the behaviour name's seed rule, the envelope L*, ids, ports,
output directories, completeness (44 routes x 3 kappas) and the kappa balance of every prefix; then the launcher's own
parsing, configuration build and preflight in this process, kappa-aware (p1_jobs.check_in_process asserts kappa 1.0);
then the exact command with --dry-run in a subprocess (p1_jobs.dry_run_line; writes nothing; at most 2 workers).
--write (requires --check with the dry runs) writes b10_rl_data.jsonl, b10_rl_data.stage.json (the stage spec that
framelease_v4/protocol/p2_check.py reads) and b10_rl_data.check.json, the contract of p1_jobs.py. It refuses an
output path inside a queue, any file that differs from an existing one (unless --force), and every write while a P2
output directory already holds runs (also with --force).
Exit codes: 0 done, 1 check failed, 2 refused (no freeze, freeze not cited or PROTOCOL.md not sealed, a test route,
existing runs, a queue path, an existing file with other content).
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402
from framelease_v4.protocol import select_stage as SS  # noqa: E402

VARIANT = 'FULL'
PHASE, BLOCK, BLOCK_NO, TIER = 'P2', 'rl_data', 10, 2
ARM = 'fl_behaviour'
EPS = 0.3
KAPPAS = (1.0, 1.5, 2.0)
SEED, REP = PJ.SEED, 0
ID_PREFIX = 'v4p2'
ROUTE_SET = 'RL'                                   # route_split.json subset: all 44 training routes (Sec. 3.2)
RL_DATA_REL = 'outputs/framelease_v4/rl_data'
QUEUE_REL = 'outputs/framelease_v4/queue_p2'       # Sec. 8.6 (planned queue directories)
JOBS_DIR = ROOT / 'outputs/framelease_v4/p2_jobs'
PROTOCOL = ROOT / 'framelease_v4/PROTOCOL.md'
SEAL = ROOT / 'outputs/framelease_v4/registration/SEAL.sha256'
SEC_13_2 = '### 13.2 Amendments'
STAGE_SCHEMA = 'framelease_v4.p2_stage/1'
CHECK_SCHEMA = 'framelease_v4.p2_check/1'
MAX_WORKERS = 2                                    # CPU discipline while a runner is active (GAP_AUDIT Sec. 1.4)
SHA_RE = re.compile(r'\b[0-9a-f]{64}\b')
NOT_BEFORE = ("the tuning freeze entered in PROTOCOL Sec. 13.2 (Sec. 4.9), this job file entered in Sec. 13.2, and "
              "the user's D1 decision to continue (Sec. 4.8)")
ORDER_RULE = (f'routes: random.Random({PJ.ORDER_SEED} + {BLOCK_NO}).shuffle(id-sorted training routes); per route '
              f'the kappas {list(KAPPAS)} back to back, rotated by one position per route (p1_jobs.ordered); port '
              '2600 + 10 (i mod 4) for line i')


def _opts(cmd):
    return {cmd[k]: cmd[k + 1] for k in range(len(cmd) - 1) if cmd[k].startswith('--')}


# ---------------------------------------------------------------------------------------- the tuning freeze

def sec_13_2(text):
    """(first line index, end line index, lines) of PROTOCOL Sec. 13.2: from its heading to the next heading of level 2
    or 3."""
    lines = text.split('\n')
    starts = [i for i, ln in enumerate(lines) if ln.strip() == SEC_13_2]
    if len(starts) != 1:
        raise ValueError(f'PROTOCOL.md: expected exactly one "{SEC_13_2}" heading, found {len(starts)}')
    s = starts[0]
    e = next((i for i in range(s + 1, len(lines)) if lines[i].startswith(('## ', '### '))), len(lines))
    return s, e, lines


def citations(sha, text):
    """1-based line numbers of PROTOCOL Sec. 13.2 that cite the sha256 `sha`."""
    s, e, lines = sec_13_2(text)
    return [i + 1 for i in range(s, e) if sha in SHA_RE.findall(lines[i])]


def protocol_seal(protocol=PROTOCOL, seal=SEAL):
    """{'protocol_sha256', 'sealed_sha256', 'sealed'}: PROTOCOL.md against its line in SEAL.sha256 (registration.py
    --seal writes '<sha256>  framelease_v4/PROTOCOL.md')."""
    psha = PJ.sha256_file(protocol)
    sealed = None
    for line in Path(seal).read_text(encoding='utf-8').splitlines():
        parts = line.split('  ', 1)
        if len(parts) == 2 and SS._same_path(parts[1].strip(), protocol):
            sealed = parts[0].strip()
    return {'protocol_sha256': psha, 'sealed_sha256': sealed, 'sealed': sealed == psha}


def load_freeze(path=SS.FREEZE_PATH, protocol=PROTOCOL, seal=SEAL):
    """The tuning freeze as P2 uses it: {'path', 'sha256', 'L': {label, path, sha256, config}, 'd', 'd_utility',
    'cited_lines', 'protocol'}. Refuses (PermissionError) a freeze whose sha256 PROTOCOL Sec. 13.2 does not cite and an
    unsealed PROTOCOL.md (seal None skips the seal check: tests only); ValueError for an inconsistent freeze."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f'{PJ.rel(path)}: no tuning freeze yet (select_stage.py --variant FULL --freeze '
                                '--write after age_s2 and event_s2, PROTOCOL Sec. 4.9)')
    sha = PJ.sha256_file(path)
    try:
        doc = json.loads(path.read_text(encoding='utf-8'))
    except ValueError as e:
        raise ValueError(f'{PJ.rel(path)}: not JSON ({e})') from e
    if not isinstance(doc, dict) or doc.get('schema') != SS.FREEZE_SCHEMA:
        raise ValueError(f'{PJ.rel(path)}: not a tuning freeze (schema {SS.FREEZE_SCHEMA})')
    if doc.get('variant') != VARIANT:
        raise ValueError(f'{PJ.rel(path)}: variant {doc.get("variant")!r}; the P2 block is generated for the '
                         'registered plan FULL only (TRIMMED, PROTOCOL Sec. 14, is not registered)')
    cited = citations(sha, Path(protocol).read_text(encoding='utf-8'))
    if not cited:
        raise PermissionError(f'{PJ.rel(path)} (sha256 {sha}) is not cited in PROTOCOL.md Sec. 13.2: the tuning freeze '
                              'is entered there before Phase 2 starts (Sec. 4.9); refusing an unrecorded freeze')
    seal_info = None
    if seal is not None:
        seal_info = protocol_seal(protocol, seal)
        if not seal_info['sealed']:
            raise PermissionError(f'PROTOCOL.md (sha256 {seal_info["protocol_sha256"]}) is not the sealed version '
                                  f'({seal_info["sealed_sha256"]}, {PJ.rel(seal)}): an amendment is open; generate the '
                                  'P2 block after it is sealed')
    L = doc.get('L_star') or {}
    envs = PJ.envelopes()
    label = L.get('label')
    if label not in envs:
        raise ValueError(f'L* {label!r} is not an exported, kept envelope ({", ".join(envs)})')
    env = envs[label]
    if (L.get('envelope_path'), L.get('envelope_sha256')) != (env['path'], env['sha256']):
        raise ValueError(f'L* {label}: the freeze names {L.get("envelope_path")} / {L.get("envelope_sha256")}, the '
                         f'envelope manifest {env["path"]} / {env["sha256"]}')
    if L.get('validity') != 'std':
        raise ValueError(f'L*: validity {L.get("validity")!r} != std (PROTOCOL Sec. 4.3)')
    dd = doc.get('d_star') or {}
    d = dd.get('d')
    if isinstance(d, bool) or not isinstance(d, int) or d not in PJ.GRIDS[VARIANT]['heur']:
        raise ValueError(f'd* {d!r} is not a depth of the registered heuristic grid {PJ.GRIDS[VARIANT]["heur"]}')
    if dd.get('utility') != PJ.heur_utility(d):
        raise ValueError(f'd* = {d}: utility {dd.get("utility")!r} != {PJ.heur_utility(d)!r}')
    beh = (doc.get('arms') or {}).get(ARM) or {}
    if (beh.get('envelope'), beh.get('base_depth')) != (env['path'], d):
        raise ValueError(f'arms.{ARM} of the freeze ({beh}) is not (L*, d*)')
    return {'path': PJ.rel(path), 'sha256': sha,
            'L': {'label': label, **{k: env[k] for k in ('path', 'sha256', 'config')}}, 'd': d,
            'd_utility': dd['utility'], 'cited_lines': cited,
            'protocol': {'path': PJ.rel(protocol), 'sha256': PJ.sha256_file(protocol), 'seal': seal_info}}


# ---------------------------------------------------------------------------------------- the plan and the lines

def behaviour_plan(freeze):
    """collection_plan.plan() of the registered P2 design at (L*, d*)."""
    from framelease_v4.rl import collection_plan as CP
    return CP.plan(eps=EPS, kappas=KAPPAS, d_det=freeze['d'], envelope=freeze['L']['path'], variant=VARIANT)


def behaviour_utility(route, kappa, d):
    """(seed, utility name) of the behaviour run of (route, kappa) by the seed rule of PROTOCOL Sec. 2.6 (rep 0)."""
    from framelease_v4.rl import behaviour as B
    from framelease_v4.rl import collection_plan as CP
    seed = CP.behaviour_seed(route, kappa, REP)
    return seed, B.behaviour_name(EPS, seed, d)


def config_tag(freeze):
    return f'{freeze["L"]["label"]}_eps{EPS:.3f}_d{freeze["d"]}'


def job_id(freeze, kappa, route):
    return f'{ID_PREFIX}_{ARM}_{config_tag(freeze)}_k{float(kappa):.1f}_s{SEED}_r{route}'


def output_dir(kappa):
    return f'{RL_DATA_REL}/k{float(kappa):.1f}'


def training_and_test():
    return PJ.training_routes(), {r['route_id'] for r in PJ.route_split()['test']}


def plan_runs(plan, freeze):
    """{(route, kappa): plan run}, after checking the plan against the registered P2 design. A test route raises
    PermissionError (PROTOCOL Sec. 3.3); any other difference raises ValueError."""
    train, test = training_and_test()
    if (plan.get('variant'), plan.get('eps'), plan.get('a_det_depth')) != (VARIANT, EPS, freeze['d']):
        raise ValueError(f'the collection plan is not (FULL, eps {EPS}, d* {freeze["d"]})')
    if (plan.get('training_pool_check') or {}).get('match') is not True:
        raise ValueError('the collection plan\'s training pool differs from route_split.json')
    runs = {}
    for run in plan.get('runs') or []:
        r, k = str(run.get('route_id')), float(run.get('kappa'))
        if r in test or r not in train:
            raise PermissionError(f'route {r} is not a training route: test routes are never used for RL data '
                                  '(PROTOCOL Sec. 3.3)')
        if k not in KAPPAS or run.get('rep') != REP or (r, k) in runs:
            raise ValueError(f'plan run ({r}, kappa {k}, rep {run.get("rep")}) is not one of the 132 registered runs')
        seed, name = behaviour_utility(r, k, freeze['d'])
        if (run.get('behaviour_seed'), run.get('utility')) != (seed, name):
            raise ValueError(f'plan run ({r}, kappa {k}): behaviour {run.get("utility")} breaks the seed rule ({name})')
        argv = list(run.get('argv') or [])
        o = _opts(argv)
        want = {'--arm': ARM, '--fast-prefix': PJ.FAST_PREFIX, '--kappa': f'{k:.1f}', '--seed': str(SEED),
                '--routes': PJ.ROUTES_XML_REL, '--route-id': r, '--output-dir': output_dir(k),
                '--timeout-s': str(PJ.TIMEOUT_S), '--lock-wait-s': str(PJ.LOCK_WAIT_S),
                '--envelope': freeze['L']['path']}
        bad = sorted(key for key, v in want.items() if o.get(key) != v)
        if not argv or argv[0] != PJ.LAUNCHER_REL or '--port' not in o or bad \
                or json.loads(o.get('--policy-params', '{}')) != {'utility': name}:
            raise ValueError(f'plan run ({r}, kappa {k}): launcher arguments differ from the P2 design ({bad})')
        runs[(r, k)] = run
    want_cells = {(r, k) for r in PJ.route_set(ROUTE_SET) for k in KAPPAS}
    if set(runs) != want_cells:
        raise ValueError(f'the plan holds {len(runs)} runs, not the 44 training routes x {len(KAPPAS)} kappas')
    return runs


def build_block(freeze, plan=None):
    """(job lines, stage spec) of the P2 block (nothing written)."""
    plan = behaviour_plan(freeze) if plan is None else plan
    runs = plan_runs(plan, freeze)
    train, _ = training_and_test()
    routes = sorted({r for r, _ in runs}, key=int)
    pairs, order = PJ.ordered(BLOCK_NO, routes, list(KAPPAS))
    L = freeze['L']
    pins = PJ.code_pins([L['path']])
    lines = []
    for i, (k, r) in enumerate(pairs):
        run = runs[(r, k)]
        port = PJ.port_of(i)
        argv = list(run['argv'])
        argv[argv.index('--port') + 1] = str(port)
        row = train[r]
        lines.append({
            'id': job_id(freeze, k, r), 'kind': 'closed_loop', 'tier': TIER, 'cmd': [PJ.PYTHON, '-B'] + argv,
            'wall_cap_s': PJ.WALL_CAP_S, 'matrix': 'framelease_v4_p2', 'phase': PHASE, 'block': BLOCK,
            'block_no': BLOCK_NO, 'arm_name': ARM, 'config': config_tag(freeze),
            'policy_params': {'utility': run['utility']}, 'envelope': dict(L), 'kappa': k, 'seed': SEED,
            'fast_prefix': PJ.FAST_PREFIX.split(','),
            'behaviour': {'eps': EPS, 'seed': run['behaviour_seed'], 'rep': REP, 'base_depth': freeze['d'],
                          'utility': run['utility'],
                          'seed_rule': 'collection_plan.behaviour_seed(route, kappa, rep 0) (PROTOCOL Sec. 2.6)'},
            'route_id': r, 'route_index': row['index'], 'scenario_type': row['scenario_type'], 'town': row['town'],
            'port': port, 'output_dir': output_dir(k), 'training_route': True,
            'tuning_freeze': {'path': freeze['path'], 'sha256': freeze['sha256']},
            'not_for_launch_before': NOT_BEFORE, 'require_sha256': pins})
    counts = {f'{k:.1f}': sum(1 for j in lines if j['kappa'] == k) for k in KAPPAS}
    from framelease_v4.rl import collection_plan as CP
    spec = {'schema': STAGE_SCHEMA, 'variant': VARIANT, 'phase': PHASE, 'block': BLOCK, 'block_no': BLOCK_NO,
            'tier': TIER, 'arm': ARM, 'eps': EPS, 'kappas': list(KAPPAS), 'seed': SEED, 'rep': REP,
            'L_star': dict(L), 'd_star': {'d': freeze['d'], 'utility': freeze['d_utility']},
            'route_set': ROUTE_SET, 'routes': routes, 'route_order': order, 'order_rule': ORDER_RULE,
            'n_lines': len(lines), 'runs_per_kappa': counts,
            'output_dirs': {f'{k:.1f}': output_dir(k) for k in KAPPAS},
            'jobs': [{'line': i + 1, 'id': j['id'], 'route_id': j['route_id'], 'kappa': j['kappa'],
                      'behaviour_seed': j['behaviour']['seed'], 'utility': j['policy_params']['utility'],
                      'output_dir': j['output_dir'], 'port': j['port']} for i, j in enumerate(lines)],
            'code_pins': {'n': len(pins), 'sha256': PJ.sha256_text(json.dumps(pins, sort_keys=True)),
                          'rule': 'framelease_v4/arms/jobs_v4.code_pins([L*]) (PROTOCOL Sec. 8.3)'},
            'tuning_freeze': {'path': freeze['path'], 'sha256': freeze['sha256'],
                              'cited_in_protocol_sec_13_2_lines': freeze['cited_lines']},
            'protocol': freeze['protocol'],
            'collection_plan': {'schema': plan.get('schema'), 'n_runs': plan.get('n_runs'),
                                'sha256': PJ.sha256_text(json.dumps(plan, sort_keys=True)),
                                'script': PJ.rel(CP.__file__), 'script_sha256': PJ.sha256_file(CP.__file__)},
            'inputs': {freeze['path']: freeze['sha256'], PJ.rel(PJ.ROUTE_SPLIT): PJ.sha256_file(PJ.ROUTE_SPLIT),
                       PJ.rel(PJ.ENVELOPE_MANIFEST): PJ.sha256_file(PJ.ENVELOPE_MANIFEST)},
            'queue': QUEUE_REL, 'not_for_launch_before': NOT_BEFORE,
            'completion_check': f'framelease_v4/protocol/p2_check.py --queue {QUEUE_REL} (PROTOCOL Sec. 8.1: P2 ends '
                                'with the data manifest)',
            'not_registered_details': 'block number 10, the route order and the queue name are entered in PROTOCOL '
                                      'Sec. 13.2 with this job file',
            'rules': 'PROTOCOL Secs. 5.3, 8.2-8.4, 8.6 (framelease_v4/protocol/p2_jobs.py)'}
    return lines, spec


# ---------------------------------------------------------------------------------------- checks (CPU only)

def kappa_spread(lines):
    """The largest difference between the per-kappa line counts over all prefixes of the block (balanced: <= 1)."""
    counts = {k: 0 for k in KAPPAS}
    worst = 0
    for j in lines:
        k = float(j.get('kappa'))
        counts[k] = counts.get(k, 0) + 1
        worst = max(worst, max(counts.values()) - min(counts.values()))
    return worst


def static_problems(lines, freeze):
    """Problems found without the launcher: gpu_queue's contract, pins, the P2 design of every line (training routes,
    seed rule, L*, kappa, ids, ports, output directories, explicit options), completeness and kappa balance."""
    from framelease_v2 import gpu_queue as Q
    from framelease_v4.rl import behaviour as B
    train, test = training_and_test()
    L, d = freeze['L'], freeze['d']
    pins = PJ.code_pins([L['path']])
    problems, cells = [], []
    ids = [j.get('id') for j in lines]
    if len(set(ids)) != len(ids):
        problems.append('duplicate job ids')
    for i, j in enumerate(lines):
        jid = j.get('id')
        bad = Q.validate_job(j)
        if bad:
            problems.append(f'{jid}: gpu_queue rejects the job: {bad}')
            continue
        if j.get('require_sha256') != pins:
            problems.append(f'{jid}: require_sha256 differs from jobs_v4.code_pins([L*])')
        mism = Q.pin_mismatches(j.get('require_sha256'))
        if mism:
            problems.append(f'{jid}: pinned files differ from the tree: {[m["file"] for m in mism][:5]}')
        cmd, o = j['cmd'], _opts(j['cmd'])
        k, r = j.get('kappa'), str(j.get('route_id'))
        cells.append((r, k))
        if cmd[:3] != [PJ.PYTHON, '-B', PJ.LAUNCHER_REL]:
            problems.append(f'{jid}: not the v4 launcher command')
        if (j.get('kind'), j.get('tier'), j.get('wall_cap_s'), j.get('phase')) != ('closed_loop', TIER, PJ.WALL_CAP_S,
                                                                                    PHASE):
            problems.append(f'{jid}: kind / tier / wall cap / phase')
        if j.get('port') != PJ.port_of(i) or o.get('--port') != str(PJ.port_of(i)):
            problems.append(f'{jid}: port {j.get("port")} != 2600 + 10 ({i} mod 4)')
        if o.get('--fast-prefix') != PJ.FAST_PREFIX:
            problems.append(f'{jid}: --fast-prefix not explicit')
        if (o.get('--timeout-s'), o.get('--lock-wait-s')) != (str(PJ.TIMEOUT_S), str(PJ.LOCK_WAIT_S)):
            problems.append(f'{jid}: --timeout-s / --lock-wait-s')
        if k not in KAPPAS or o.get('--kappa') != f'{float(k):.1f}' or o.get('--seed') != str(SEED) \
                or j.get('seed') != SEED:
            problems.append(f'{jid}: kappa {k} / seed {j.get("seed")} (kappa in {list(KAPPAS)}, seed {SEED})')
            continue
        if (o.get('--arm'), j.get('arm_name')) != (ARM, ARM):
            problems.append(f'{jid}: arm is not {ARM}')
        env = j.get('envelope') or {}
        if o.get('--envelope') != L['path'] or (env.get('path'), env.get('sha256')) != (L['path'], L['sha256']) \
                or (j.get('require_sha256') or {}).get(L['path']) != L['sha256']:
            problems.append(f'{jid}: the envelope is not L* = {L["label"]} ({L["path"]}, pinned)')
        if r not in train or r in test or o.get('--route-id') != r:
            problems.append(f'{jid}: route {r} is not a training route')
            continue
        seed, name = behaviour_utility(r, k, d)
        beh = j.get('behaviour') or {}
        if j.get('policy_params') != {'utility': name} \
                or json.loads(o.get('--policy-params', '{}')) != {'utility': name} \
                or B.parse_behaviour(name) != (EPS, seed, d) or (beh.get('seed'), beh.get('utility')) != (seed, name):
            problems.append(f'{jid}: the behaviour utility does not follow the seed rule ({name}; PROTOCOL Sec. 2.6)')
        if j.get('output_dir') != output_dir(k) or o.get('--output-dir') != output_dir(k) \
                or 'jobs.d' in str(j.get('output_dir')):
            problems.append(f'{jid}: output directory {j.get("output_dir")} != {output_dir(k)}')
        if jid != job_id(freeze, k, r):
            problems.append(f'{jid}: id != {job_id(freeze, k, r)}')
    want = {(r, k) for r in PJ.route_set(ROUTE_SET) for k in KAPPAS}
    if len(set(cells)) != len(cells) or set(cells) != want:
        problems.append(f'the block is not the 44 training routes x kappa {list(KAPPAS)} once each '
                        f'({len(set(cells))} distinct cells of {len(want)})')
    spread = kappa_spread(lines)
    if spread > 1:
        problems.append(f'a prefix of the block is unbalanced over kappa (per-kappa counts differ by {spread} > 1)')
    return problems


@contextlib.contextmanager
def _at_root():
    """The launcher resolves the relative --routes / --output-dir of a job line against the working directory."""
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        yield
    finally:
        os.chdir(cwd)


def check_in_process(job):
    """{'id', 'problems', ...}: the launcher's own parsing, configuration build and preflight in this process, against
    the job's own kappa (p1_jobs.check_in_process asserts kappa 1.0). Not thread-safe (stdout / stderr redirected, the
    environment restored, the working directory set to the project root): call it sequentially."""
    from framelease_v4.arms import run_closed_loop_v4 as RL
    from framelease_v4.rl import behaviour as B
    out = {'id': job['id'], 'problems': []}
    cmd = job['cmd']
    if cmd[:3] != [PJ.PYTHON, '-B', PJ.LAUNCHER_REL]:
        out['problems'].append('not the v4 launcher command')
        return out
    saved = dict(os.environ)
    try:
        with _at_root(), contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            args = RL.parse_args(cmd[3:])
            prep = RL.prepare(args)
        cfg, info = prep['cfg'], prep['route']
        if (info['route_id'], info['town'], info['scenarios']) != (job['route_id'], job['town'],
                                                                   [job['scenario_type']]):
            out['problems'].append(f'route {info} does not match the job')
        if (cfg['arm'], cfg['kind'], prep['fp']['options']) != (job['arm_name'], 'shield', job['fast_prefix']):
            out['problems'].append('arm / kind / fast prefix differ from the job')
        rt = cfg['agent']['runtime']
        if float(rt['kappa']) != float(job['kappa']) or cfg['agent']['seed'] != job['seed']:
            out['problems'].append(f'kappa / seed of the configuration ({rt["kappa"]}, {cfg["agent"]["seed"]}) differ '
                                   f'from the job ({job["kappa"]}, {job["seed"]})')
        if rt.get('max_depth') != 10:
            out['problems'].append('shield depth limit is not 10')
        pp = dict(cfg['agent']['policy_params'] or {})
        for k, v in job['policy_params'].items():
            if pp.get(k) != v:
                out['problems'].append(f'policy parameter {k}: {pp.get(k)!r} != {v!r}')
        u = cfg.get('utility') or {}
        beh = job['behaviour']
        if u.get('name') != job['policy_params']['utility'] or u.get('env') \
                or B.parse_behaviour(u.get('name')) != (EPS, beh['seed'], beh['base_depth']):
            out['problems'].append(f'utility block {u.get("name")!r} is not the job\'s behaviour utility')
        if (cfg.get('v3') or {}).get('envelope_sha256') != job['envelope']['sha256']:
            out['problems'].append('envelope sha256 of the configuration differs from L*')
        out['agent_runtime_config_sha256'] = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
        out['utility'] = u.get('name')
        out['kappa'] = rt['kappa']
    except SystemExit as e:
        out['problems'].append(f'SystemExit: {e}')
    except BaseException as e:  # noqa: BLE001
        out['problems'].append(f'{type(e).__name__}: {e}')
    finally:
        os.environ.clear()
        os.environ.update(saved)
    return out


def _dry_run_env():
    return dict(os.environ, PYTHONDONTWRITEBYTECODE='1', CUDA_VISIBLE_DEVICES='')


def check_line(job, dry_run=True):
    """{'id', 'ok', 'problems', ...} of one line: check_in_process, then (if dry_run) its --dry-run subprocess."""
    out = check_in_process(job)
    if dry_run and not out['problems']:
        before = (ROOT / job['output_dir']).exists()
        PJ._merge_dry_run(out, PJ.dry_run_line(job, _dry_run_env()))
        if not before and (ROOT / job['output_dir']).exists():
            out['problems'].append('the dry run created the output directory')
    out['ok'] = not out['problems']
    return out


def check_lines(lines, freeze, dry_run=True, workers=MAX_WORKERS):
    """Every line: static checks, the in-process launcher checks (sequential) and the --dry-run subprocesses (at most
    MAX_WORKERS threads, each with its own copy of the environment). Returns (per-line results, problems)."""
    if not 1 <= int(workers) <= MAX_WORKERS:
        raise ValueError(f'workers must be 1..{MAX_WORKERS}')
    problems = static_problems(lines, freeze)
    if dry_run and not PJ._stack_ready():
        raise SystemExit('--check needs the official stack variables (source linux/env.sh): CHECKPOINT is not set')
    results = [check_in_process(j) for j in lines]
    if dry_run:
        dirs_before = {j['output_dir']: (ROOT / j['output_dir']).exists() for j in lines}
        env = _dry_run_env()
        todo = [(r, j) for r, j in zip(results, lines) if not r['problems']]
        with ThreadPoolExecutor(max_workers=int(workers)) as ex:
            outs = list(ex.map(lambda rj: PJ.dry_run_line(rj[1], dict(env)), todo))
        for (r, _), res in zip(todo, outs):
            PJ._merge_dry_run(r, res)
        for d, existed in dirs_before.items():
            if not existed and (ROOT / d).exists():
                problems.append(f'{d}: created by a dry run')
    for r in results:
        r['ok'] = not r['problems']
    problems += [f'{r["id"]}: {p}' for r in results for p in r['problems']]
    return results, problems


# ---------------------------------------------------------------------------------------- writing

def block_paths(jobs_dir=None):
    base = Path(jobs_dir or JOBS_DIR) / VARIANT / f'b{BLOCK_NO:02d}_{BLOCK}'
    return Path(str(base) + '.jsonl'), Path(str(base) + '.stage.json'), Path(str(base) + '.check.json')


def queue_parts(path):
    """Directories on `path` that belong to a runner queue: named jobs.d or queue*, or holding jobs.d/, status.jsonl
    or runner.lock (framelease_v2/gpu_queue.py)."""
    p = Path(path).resolve()
    hits = []
    for d in [p] + list(p.parents):
        if d.name == 'jobs.d' or d.name.startswith('queue') or (d / 'jobs.d').is_dir() \
                or (d / 'status.jsonl').is_file() or (d / 'runner.lock').exists():
            hits.append(str(d))
    return hits


def runs_present(lines, root=ROOT):
    """Output directories of the block that already hold run directories (P2 has started)."""
    out = []
    for d in sorted({j['output_dir'] for j in lines}):
        runs = Path(root) / d / 'runs'
        if runs.is_dir() and any(runs.iterdir()):
            out.append(PJ.rel(runs))
    return out


def jsonl(lines):
    return ''.join(json.dumps(j, sort_keys=True) + '\n' for j in lines)


def write_block(paths, lines, spec, results, problems, force=False, root=ROOT):
    """Write the job file, its stage spec and its check (refusals: PermissionError for a queue path or existing runs,
    FileExistsError for an existing file with other content without force)."""
    job_path, spec_path, check_path = (Path(p) for p in paths)
    hits = queue_parts(job_path.parent)
    if hits:
        raise PermissionError(f'refusing to write {job_path}: {hits[0]} belongs to a runner queue (the P2 job file is '
                              'written outside every queue and copied into queue_p2/jobs.d by hand)')
    runs = runs_present(lines, root)
    if runs:
        raise PermissionError(f'refusing to write {PJ.rel(job_path)}: {runs[0]} already holds runs (P2 has started)')
    text = jsonl(lines)
    spec = {**spec, 'job_file': PJ.rel(job_path), 'job_file_sha256': PJ.sha256_text(text)}
    spec_text = json.dumps(spec, indent=1, sort_keys=True) + '\n'
    check = {'schema': CHECK_SCHEMA, 'job_file': spec['job_file'], 'job_file_sha256': spec['job_file_sha256'],
             'n_lines': len(lines), 'problems': problems,
             'all_dry_runs_ok': bool(results) and len(results) == len(lines) and all(
                 r.get('ok') and r.get('dry_run', {}).get('status') == 'NOT_STARTED' for r in results),
             'lines': results, 'script_sha256': PJ.sha256_file(Path(__file__)),
             'p1_jobs_sha256': PJ.sha256_file(Path(PJ.__file__))}
    check_text = json.dumps(check, indent=1, sort_keys=True) + '\n'
    todo = ((job_path, text), (spec_path, spec_text), (check_path, check_text))
    for path, new in todo:
        if path.exists() and path.read_text(encoding='utf-8') != new and not force:
            raise FileExistsError(f'refusing to overwrite {PJ.rel(path)} with other content (use --force; no P2 run '
                                  'may exist, and a recorded file is never rewritten)')
    job_path.parent.mkdir(parents=True, exist_ok=True)
    for path, new in todo:
        path.write_text(new, encoding='utf-8')
    return {'job_file': PJ.rel(job_path), 'sha256': PJ.sha256_file(job_path), 'lines': len(lines),
            'stage_spec': PJ.rel(spec_path), 'stage_spec_sha256': PJ.sha256_file(spec_path),
            'check': PJ.rel(check_path), 'check_sha256': PJ.sha256_file(check_path)}


def summary_lines(freeze, lines, spec, paths):
    L = freeze['L']
    out = [f'P2 block {BLOCK} (no. {BLOCK_NO}): {len(lines)} job lines -> {PJ.rel(paths[0])} (NOT launched)',
           f'  tuning freeze {freeze["path"]} sha256 {freeze["sha256"]} (cited in PROTOCOL Sec. 13.2, line(s) '
           f'{freeze["cited_lines"]})',
           f'  L* = {L["label"]} ({L["path"]}, {L["sha256"][:12]}); d* = {freeze["d"]}; eps {EPS}; '
           f'per kappa {spec["runs_per_kappa"]}; prefix kappa spread {kappa_spread(lines)}']
    for j in lines[:3]:
        out.append(f'  {j["id"]:<66} port {j["port"]} -> {j["output_dir"]}')
    if len(lines) > 3:
        out.append(f'  ... {len(lines) - 3} more')
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--selection', type=Path, default=SS.FREEZE_PATH, help='the tuning freeze (selection.json)')
    ap.add_argument('--protocol', type=Path, default=PROTOCOL)
    ap.add_argument('--seal', type=Path, default=SEAL)
    ap.add_argument('--jobs-dir', type=Path, default=JOBS_DIR)
    ap.add_argument('--check', action='store_true', help='validate every line (needs source linux/env.sh)')
    ap.add_argument('--no-dry-run', action='store_true', help='skip the subprocess --dry-run of each line')
    ap.add_argument('--write', action='store_true', help='write the job file, stage spec and check (needs --check)')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--workers', type=int, default=MAX_WORKERS,
                    help=f'dry-run subprocesses in parallel (1..{MAX_WORKERS})')
    a = ap.parse_args(argv)
    if a.write and (not a.check or a.no_dry_run):
        ap.error('--write requires --check with the --dry-run of every line (PROTOCOL Sec. 8.2)')
    if not 1 <= a.workers <= MAX_WORKERS:
        ap.error(f'--workers must be 1..{MAX_WORKERS}')
    paths = block_paths(a.jobs_dir)
    try:
        freeze = load_freeze(a.selection, a.protocol, a.seal)
        lines, spec = build_block(freeze)
    except (FileNotFoundError, ValueError, PermissionError) as e:
        print(f'REFUSED: {e}', file=sys.stderr)
        return 2
    print('\n'.join(summary_lines(freeze, lines, spec, paths)))
    started = runs_present(lines)
    if started:
        print(f'  NOTE: {started} already hold runs: the job file can no longer be written', file=sys.stderr)
    if not a.check:
        return 0
    results, problems = check_lines(lines, freeze, not a.no_dry_run, a.workers)
    if problems:
        print('CHECK FAILED\n  ' + '\n  '.join(problems[:40]), file=sys.stderr)
        return 1
    print('every line passes gpu_queue, the pins, the P2 design, the launcher (parse, configuration, preflight; kappa '
          'aware)' + ('' if a.no_dry_run else ' and its --dry-run'))
    if a.write:
        try:
            info = write_block(paths, lines, spec, results, problems, a.force)
        except (PermissionError, FileExistsError) as e:
            print(f'REFUSED: {e}', file=sys.stderr)
            return 2
        print(json.dumps(info, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
