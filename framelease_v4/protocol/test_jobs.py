#!/usr/bin/env python3
"""Job files of the test-route phases P4-P6 of framelease_v4/PROTOCOL.md: tiers 3-6 (Secs. 7.2-7.5, 8.1-8.4, 8.6, 9.6,
10.1), in the framelease_v2/gpu_queue.py format. WRITTEN, NEVER LAUNCHED OR ENQUEUED: the files go to
outputs/framelease_v4/test_jobs/FULL/ (not a queue jobs.d/ directory; any path inside a queue is refused), so no runner
picks them up; this script never starts a job, CARLA or the GPU, and it never reads a test-route result (Sec. 9.11: the
existing-runs guard only asks whether a run directory exists).

  cd /home/kang/Desktop/DAC
  .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/test_jobs.py                  # the blocks, unchecked
  source linux/env.sh && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 nice -n 19 ionice -c 3 \
      .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/test_jobs.py --check --write  # validate, then write

Inputs (PROTOCOL Secs. 4.9, 5.9, 8.1):
  * the tuning freeze outputs/framelease_v4/tuning/selection.json (select_stage.py --variant FULL --freeze --write;
    schema framelease_v4.tuning_selection/1) through the P2 gate p2_jobs.load_freeze: refused unless its sha256 is cited
    in PROTOCOL.md Sec. 13.2 and PROTOCOL.md is the sealed version; L* an exported, verified envelope, d* a depth of the
    registered heuristic grid. This script also checks A* (the Age-Only grid of Sec. 4.5, utility a_det^{d*}), theta*
    and A_hb* (a candidate of the Event-Triggered grid of Sec. 4.6) and the fl_risk lease point (Sec. 4.3: FULL, only if
    L* = B0; E5 or E10, or none, in which case fl_risk is not run);
  * the RL freeze outputs/framelease_v4/rl_freeze/rl_freeze.json (p3_rl.py; schema framelease_v4.rl_freeze/1) through
    p3_rl.load_rl_freeze: a production record, frozen, every named file at its recorded sha256, every network loadable
    and at its recorded name, file sha256, absolute path, arm and a_det depth. It must have been made from this tuning
    freeze (sha256, d* and L*). It is entered in Sec. 13 with the test freeze (Sec. 5.9), so it is not yet cited when
    the job files are generated. A Q-network is identified by its protocol arm and its FILE sha256, which every line
    pins: the name v4_qnet_<sha12> pins neither B_pi nor the provenance, and two not-trainable families share a name
    (p3_rl.JOB_LINES_RULE). FRAMELEASE_V4_QNET is the ABSOLUTE path (finding QNET-1: the evaluator runs in another
    working directory).

The blocks (block numbers 11-16, the first after the P1 blocks 0-9 and the P2 block 10 of Sec. 8.2; one job file per
block, b<NN>_<block>.jsonl, so name order is tier order and a cut takes the bottom tiers first, GAP_AUDIT E-1; all six
are copied into the one queue outputs/framelease_v4/queue_p4):
  block (no.)     tier phase  runs  content                                                      output directory
  ti_main  (11)   3    P4     308   Table I: the 7 arms x the 44 test routes, kappa 1.0, seed 11  matrix/<arm>
  f3_k     (12)   4    P5     176   Fig. 3: fixed_deep, fast_only, fl_heuristic, fl_full x kappa  fig3/<arm>_k<kappa>
                                    {1.5, 2.0} x E, seed 11 (the kappa-1.0 points are Table I's)
  a_lease  (13)   5    P6      22   Table II-A lease panel: fl_global_shield x E, kappa 1.0       ablation/<arm>
  a_rl     (14)   5    P6      44   Table II-A RL panel: fl_bandit, fl_fqi_nolease x E, kappa 1.0 ablation/<arm>
  s_seed12 (15)   6    P6      60   seed-12 replicates: fixed_deep, fast_only, fl_heuristic,      replicates/<arm>
                                    fl_full x R, kappa 1.0
  s_risk   (16)   6    P6   22 / 0  fl_risk x E, kappa 1.0, seed 11, only if L* = B0 and a risk    ablation/<arm>
                                    point remains (otherwise no job file)
  (output directories under outputs/framelease_v4/, Sec. 8.6; route sets of outputs/framelease_v4/protocol/
  route_split.json, Sec. 3.1: test_all, E = index % 2 == 0, R = index % 3 == 0, re-derived here from the test list.)
The run counts are checked against the registered budget (make_protocol_tables.plan_blocks('FULL'), PROTOCOL Sec. 10.1).

The arms (protocol arm -> launcher arm and configuration; GAP_AUDIT Sec. 2 "Recommended labelling": the protocol arm is
recorded in the job line (protocol_arm), in the output directory (ablation/<arm>/ for the ablation arms) and in the
block spec):
  fixed_deep, fast_only, fl_original   the arms_v4 arm, no parameters, no envelope
  age_only                             {"age_lease_s": A*, "utility": a_det^{d*}} (the freeze's arms.age_only)
  event_triggered                      theta* and A_hb* (the freeze's event_star policy parameters)
  fl_heuristic                         envelope L*, utility a_det^{d*} ('heuristic' if d* = 10, else v4_adet_d<d*>)
  fl_full / fl_bandit / fl_fqi_nolease launcher arm fl_full, envelope L*, utility = the network name of the fqi /
                                       bandit / fqi_nolease family (RL freeze job_lines), --utility-env
                                       FRAMELEASE_V4_QNET=<absolute path>; the network file is pinned
  fl_global_shield                     the extension launcher framelease_v4/arms_ext/run_closed_loop_ext.py
                                       (run_closed_loop_ext.job_line: envelope L*, utility a_det^{d*}, no lease
                                       override)
  fl_risk                              launcher arm fl_heuristic at the fl_risk lease point, utility a_det^{d*}
Every line (Secs. 8.2-8.3): [python, -B, launcher, --arm, --fast-prefix sdpa,gpu_preproc,lora_merged, --kappa, --seed,
--routes, --route-id, --port, --output-dir, --timeout-s 1410 (= the 1500 s wall cap - 90 s), --lock-wait-s 600,
--envelope (shield arms), --policy-params, --utility-env (Q-network arms)]; wall_cap_s 1500; id
v4<p4|p5|p6>_<protocol arm>[_<config>]_k<kappa>_s<seed>_r<route>; protocol_arm, arm_name (the launcher arm), the
freezes' paths and sha256, not_for_launch_before = the test freeze; require_sha256 = the 49 code files of every P1 line
(framelease_v4/arms/jobs_v4.code_pins), plus the envelope (shield arms), plus the network file (Q-network arms), plus
the 5 extension sources (fl_global_shield: run_closed_loop_ext.job_pins, 55 pins). Order (Sec. 8.2): the id-sorted
routes of the block shuffled with random.Random(20261110 + block number); the arms of a route back to back, rotated by
one position per route (p1_jobs.ordered; in f3_k the 8 arm x kappa cells, arm-major); CARLA port 2600 + 10 (i mod 4)
for line i of the file.

--check validates every line before anything is written: gpu_queue's job contract, the pins against the tree, against
the expected pin set of the arm and against the registered P1 pins, test routes of the block's subset only, kappa and
seed per block, the arm's launcher, envelope, policy parameters and (Q-network arms) check_smoke_ext.qnet_line_problems
(absolute network path, pinned file, network family and input count of the protocol arm, d*, B_pi), the exact command
(line_command: no added option such as a lease override, Secs. 2.4, 7.4), ids, ports, output directories,
completeness of every block and the run counts of Sec. 10.1, unique ids and output directories across the six files,
and that no test-route run exists yet (existing_runs: no runs/ entry in an output directory of the lines or under the
P4-P6 roots matrix/, fig3/, ablation/, replicates/, and no status record in queue_p4; existence only, Sec. 9.11);
then the launcher's own parsing, configuration build and preflight in this process (kappa and seed aware; the extension
arm through run_closed_loop_ext.check_job_line, which also refuses lease overrides); then the exact command with
--dry-run in a subprocess (writes nothing; at most 2 workers). --write (requires --check with the dry runs) writes, per
block, b<NN>_<block>.jsonl, b<NN>_<block>.stage.json (the block spec: for every job id the protocol arm, route, kappa,
seed, configuration and the envelope or network sha256) and b<NN>_<block>.check.json (the contract of p1_jobs.py and
p2_jobs.py), and index.json (every block, its files and sha256, the skipped block and why). It refuses a path inside a
queue, every write while an output directory of a block already holds runs (also with --force), a file that differs
from an existing one (unless --force), and with --force too an existing file whose sha256 PROTOCOL Sec. 13.2 cites.
The registered inputs are compared with the sealed registration manifest (PROTOCOL Sec. 13.1): route_split.json, its
source routes.json and the envelope manifest (registered_inputs; route_table also requires the test rows to be the 44
routes of routes.json), and every pin except the network files and the extension sources at the sha256 of the
registered P1 lines (registration.job_pins).
Exit codes: 0 done (without --check, an existing test-route run is printed as a NOTE), 1 check failed (--check: a line
problem, a cross-block problem, or an existing test-route run), 2 refused (a freeze missing, uncited, unsealed or
inconsistent; a registered input changed; with --write: a queue path, an existing test-route run, an existing file
with other content or a recorded one).
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from framelease_v4.arms import arms_v4 as AV  # noqa: E402
from framelease_v4.protocol import make_protocol_tables as MPT  # noqa: E402
from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402
from framelease_v4.protocol import p2_jobs as P2J  # noqa: E402
from framelease_v4.protocol import registration as REG  # noqa: E402
from framelease_v4.protocol import select_stage as SS  # noqa: E402

__test__ = False        # the file name matches pytest's test_*.py pattern: it is a generator, not a test module
VARIANT = 'FULL'
TEST_SEED, REPLICATE_SEED = PJ.SEED, 12             # Sec. 2.6: test matrix seed 11, replicates seed 12
OUT_REL = 'outputs/framelease_v4'
JOBS_DIR = ROOT / 'outputs/framelease_v4/test_jobs'
QUEUE_REL = 'outputs/framelease_v4/queue_p4'        # GAP_AUDIT E-1: one queue for tiers 3-6 (Sec. 8.6: later queues)
RL_FREEZE = ROOT / 'outputs/framelease_v4/rl_freeze/rl_freeze.json'     # = p3_rl.DEFAULT_OUT / 'rl_freeze.json'
EXT_LAUNCHER_REL = 'framelease_v4/arms_ext/run_closed_loop_ext.py'
STAGE_SCHEMA = 'framelease_v4.test_stage/1'         # aggregate_v4.load_specs reads it once STAGE_SCHEMAS lists it
CHECK_SCHEMA = 'framelease_v4.test_check/1'
INDEX_SCHEMA = 'framelease_v4.test_jobs_index/1'
INDEX_NAME = 'index.json'
MATRIX = 'framelease_v4_p4p6'
MAX_WORKERS = 2                                     # CPU discipline while a runner is active (GAP_AUDIT Sec. 1.4)
ID_PREFIX = {'P4': 'v4p4', 'P5': 'v4p5', 'P6': 'v4p6'}
TABLE_I_ARMS = tuple(AV.TABLE_I_ORDER)              # Sec. 7.2, in the Table I order
FIG3_ARMS = ('fixed_deep', 'fast_only', 'fl_heuristic', 'fl_full')     # Secs. 7.3 and 9.6 (seed-12 replicates)
GLOBAL_SHIELD = 'fl_global_shield'                  # = arms_ext.GLOBAL_SHIELD (Secs. 4.1, 7.4)
QNET_FAMILY = {'fl_full': 'fqi', 'fl_bandit': 'bandit', 'fl_fqi_nolease': 'fqi_nolease'}   # = p3_rl.ARM_OF inverted
LAUNCHER_ARM = {'fl_bandit': 'fl_full', 'fl_fqi_nolease': 'fl_full', 'fl_risk': 'fl_heuristic'}  # others: the same
ENVELOPE_ARMS = ('fl_heuristic', 'fl_full', 'fl_bandit', 'fl_fqi_nolease', GLOBAL_SHIELD, 'fl_risk')
SUBSET_MODULUS = {'test_all': 1, 'E': 2, 'R': 3}    # Sec. 3.1: subsets by the v2 index (index % m == 0)
V2_SUBSET = {'test_all': 'all', 'E': 'even', 'R': 'rep15'}     # the same subsets as routes.json lists them per route
# the registered route and envelope inputs (PROTOCOL Secs. 3.1, 13.1): the route split, its source routes.json (the 44
# test routes of Sec. 3.1) and the envelope manifest; each must be at its sealed registration manifest sha256
REGISTERED_INPUTS = (PJ.ROUTE_SPLIT, MPT.ROUTES_JSON, PJ.ENVELOPE_MANIFEST)
P4P6_ROOTS = ('matrix', 'fig3', 'ablation', 'replicates')   # Sec. 8.6: the output roots of P4-P6 under OUT_REL
# the blocks of tiers 3-6 (Secs. 7.2-7.5, 9.6, 10.1); 'budget' is the block id of Sec. 10.1 (make_protocol_tables)
BLOCKS = (
    {'block': 'ti_main', 'no': 11, 'tier': 3, 'phase': 'P4', 'budget': 'TI-main', 'arms': TABLE_I_ARMS,
     'kappas': (1.0,), 'seed': TEST_SEED, 'routes': 'test_all', 'layout': 'matrix',
     'what': 'Table I (Sec. 7.2): 7 arms x 44 test routes, kappa 1.0, seed 11'},
    {'block': 'f3_k', 'no': 12, 'tier': 4, 'phase': 'P5', 'budget': 'F3-k', 'arms': FIG3_ARMS,
     'kappas': (1.5, 2.0), 'seed': TEST_SEED, 'routes': 'E', 'layout': 'fig3',
     'what': 'Fig. 3 (Sec. 7.3): Fixed Deep, Fast Only, FL+H, Full FL x kappa {1.5, 2.0} x E, seed 11'},
    {'block': 'a_lease', 'no': 13, 'tier': 5, 'phase': 'P6', 'budget': 'A-lease', 'arms': (GLOBAL_SHIELD,),
     'kappas': (1.0,), 'seed': TEST_SEED, 'routes': 'E', 'layout': 'ablation',
     'what': 'Table II-A lease panel (Sec. 7.4): Global-Margin lease + shield + a_det^{d*} x E, kappa 1.0, seed 11'},
    {'block': 'a_rl', 'no': 14, 'tier': 5, 'phase': 'P6', 'budget': 'A-rl', 'arms': ('fl_bandit', 'fl_fqi_nolease'),
     'kappas': (1.0,), 'seed': TEST_SEED, 'routes': 'E', 'layout': 'ablation',
     'what': 'Table II-A RL panel (Sec. 7.5): Contextual Bandit, FQI without lease features x E, kappa 1.0, seed 11'},
    {'block': 's_seed12', 'no': 15, 'tier': 6, 'phase': 'P6', 'budget': 'S-seed12', 'arms': FIG3_ARMS,
     'kappas': (1.0,), 'seed': REPLICATE_SEED, 'routes': 'R', 'layout': 'replicates',
     'what': 'seed-12 replicates (Secs. 2.6, 9.6): Fixed Deep, Fast Only, FL+H, Full FL x R, kappa 1.0'},
    {'block': 's_risk', 'no': 16, 'tier': 6, 'phase': 'P6', 'budget': 'S-risk', 'arms': ('fl_risk',),
     'kappas': (1.0,), 'seed': TEST_SEED, 'routes': 'E', 'layout': 'ablation',
     'what': 'fl_risk sensitivity (Sec. 4.3): only if L* = B0, at the better of E5 / E10 x E, kappa 1.0, seed 11'},
)
NOT_BEFORE = ('the test freeze (PROTOCOL Secs. 3.3 rule 4 and 8.1): selection.json, the RL freeze and these job files '
              'with their sha256 and pins entered in PROTOCOL Sec. 13.2 and sealed')
ORDER_RULE = (f'routes: random.Random({PJ.ORDER_SEED} + block number).shuffle(id-sorted routes of the block); per '
              'route the arms of the block back to back (f3_k: the arm x kappa cells, arm-major), rotated by one '
              'position per route (p1_jobs.ordered); port 2600 + 10 (i mod 4) for line i of the file')


def _opts(cmd):
    return P2J._opts(cmd)


# ---------------------------------------------------------------------------------------- routes (PROTOCOL Sec. 3.1)

def registered_inputs(paths=REGISTERED_INPUTS, manifest=None, seal=None):
    """{path: sha256} of registered input files, each at its entry in the sealed registration manifest (PROTOCOL Sec.
    13.1; the manifest's own sha256 in SEAL.sha256). ValueError for a manifest that is not the sealed one and for a file
    that is missing, unlisted or at another sha256: a registered file changes only by an amendment (Sec. 13.2), and
    registration.py --write-manifest --force re-hashes the tree without comparing it."""
    manifest, seal = Path(manifest or REG.MANIFEST), Path(seal or REG.SEAL)
    msha = PJ.sha256_file(manifest)
    if REG.read_manifest(seal).get(PJ.rel(manifest)) != msha:
        raise ValueError(f'{PJ.rel(manifest)} (sha256 {msha}) is not the sealed registration manifest ({PJ.rel(seal)})')
    listed, out = REG.read_manifest(manifest), {}
    for p in paths:
        rel = PJ.rel(p)
        sha = PJ.sha256_file(ROOT / rel) if (ROOT / rel).is_file() else None
        if sha is None or listed.get(rel) != sha:
            raise ValueError(f'{rel} (sha256 {sha}) differs from its registration manifest entry {listed.get(rel)}: '
                             'a registered input changes only by an amendment (PROTOCOL Secs. 13.1, 13.2)')
        out[rel] = sha
    return out


def v2_routes():
    """{route_id: row} of outputs/framelease_v2/closed_loop_matrix/routes.json, the 44 test routes of PROTOCOL Sec. 3.1
    (make_protocol_tables.ROUTES_JSON, the source of route_split.json)."""
    doc = json.loads(Path(MPT.ROUTES_JSON).read_text(encoding='utf-8'))
    return {str(r['route_id']): r for r in doc['routes']}


def route_table():
    """{route_id: test row} of the 44 test routes of route_split.json. Raises ValueError unless route_split.json and
    routes.json are at their registered sha256 (registered_inputs), no test route is a training route, and the test
    rows (route id, index, scenario type, town) are the 44 routes of routes.json (Sec. 3.1): a split edited in place,
    or a consistent swap of a test and a training route, never reaches a job line."""
    registered_inputs((PJ.ROUTE_SPLIT, MPT.ROUTES_JSON))
    split = PJ.route_split()
    rows = {r['route_id']: r for r in split['test']}
    if set(rows) & set(PJ.training_routes()):
        raise ValueError('a test route is a training route (PROTOCOL Sec. 3.2: disjoint by construction)')
    if len(rows) != 44 or sorted(r['index'] for r in rows.values()) != list(range(44)):
        raise ValueError('route_split.json does not hold the 44 indexed test routes of PROTOCOL Sec. 3.1')

    def key(r):
        return str(r['route_id']), int(r['index']), r['scenario_type'], r['town']

    if sorted(map(key, rows.values())) != sorted(map(key, v2_routes().values())):
        raise ValueError(f'route_split.json: the test routes (id, index, scenario type, town) are not the 44 routes of '
                         f'{PJ.rel(MPT.ROUTES_JSON)} (PROTOCOL Sec. 3.1)')
    return rows


def route_subset(name):
    """The id-sorted test routes of subset `name` (test_all, E, R): route_split.json's list, which must equal the rule
    of PROTOCOL Sec. 3.1 re-derived from the test list (index % m == 0, the index being the position in the id-sorted
    list) and the subset as routes.json lists it per route (V2_SUBSET)."""
    rows = route_table()
    m = SUBSET_MODULUS[name]
    want = sorted((r for r, row in rows.items() if row['index'] % m == 0), key=int)
    if [r for r in sorted(rows, key=int)] != [r for r in sorted(rows, key=lambda x: rows[x]['index'])]:
        raise ValueError('route_split.json: the test index is not the position in the id-sorted list')
    got = sorted(PJ.route_split()['subsets'][name], key=int)
    if got != want:
        raise ValueError(f'route_split.json subset {name} differs from the rule index % {m} == 0 (Sec. 3.1)')
    v2 = sorted((r for r, row in v2_routes().items() if V2_SUBSET[name] in (row.get('subsets') or [])), key=int)
    if v2 != want:
        raise ValueError(f'subset {name} differs from the routes.json list {V2_SUBSET[name]!r} (Sec. 3.1)')
    return want


# ---------------------------------------------------------------------------------------- the freezes

def load_tuning(path=SS.FREEZE_PATH, protocol=P2J.PROTOCOL, seal=P2J.SEAL):
    """The tuning freeze as P4-P6 use it: p2_jobs.load_freeze (cited in PROTOCOL Sec. 13.2, PROTOCOL.md sealed, L* and
    d*; PermissionError / ValueError / FileNotFoundError as there; seal None skips the seal check: tests only) plus the
    frozen Table I parameters, each checked against its registered grid: A* (Sec. 4.5) with a_det^{d*}, theta* and A_hb*
    (Sec. 4.6), the fl_heuristic and fl_full arms at (L*, d*), and the fl_risk lease point (Sec. 4.3)."""
    fr = P2J.load_freeze(path, protocol, seal)
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != fr['sha256']:
        raise ValueError(f'{PJ.rel(path)} changed while it was read')
    doc = json.loads(raw.decode('utf-8'))
    L, d, u = fr['L'], fr['d'], fr['d_utility']
    arms = doc.get('arms') or {}
    age = dict((arms.get('age_only') or {}).get('policy_params') or {})
    a_star = (doc.get('A_star') or {}).get('age_lease_s')
    if a_star not in PJ.GRIDS[VARIANT]['age'] or age != {'age_lease_s': a_star, 'utility': u}:
        raise ValueError(f'A*: arms.age_only {age} / A_star {a_star!r} is not an Age-Only candidate of '
                         f'{PJ.GRIDS[VARIANT]["age"]} with utility {u} (PROTOCOL Sec. 4.5)')
    ev = doc.get('event_star') or {}
    grid = {PJ.event_cand(t, hb)['name']: PJ.event_cand(t, hb)['policy_params'] for t, hb in PJ.GRIDS[VARIANT]['event']}
    ev_params = dict(ev.get('policy_params') or {})
    if grid.get(ev.get('candidate')) != ev_params \
            or dict((arms.get('event_triggered') or {}).get('policy_params') or {}) != ev_params:
        raise ValueError(f'theta*, A_hb*: event_star {ev} is not an Event-Triggered candidate of the registered grid '
                         f'({", ".join(grid)}) or differs from arms.event_triggered (PROTOCOL Sec. 4.6)')
    flh, flf = arms.get('fl_heuristic') or {}, arms.get('fl_full') or {}
    if (flh.get('envelope'), flh.get('policy_params')) != (L['path'], {'utility': u}) \
            or (flf.get('envelope'), flf.get('a_det_depth')) != (L['path'], d):
        raise ValueError(f'arms.fl_heuristic {flh} / arms.fl_full {flf} are not (L* = {L["path"]}, d* = {d})')
    risk, envs = doc.get('fl_risk'), PJ.envelopes()
    if L['label'] != 'B0':
        if risk is not None:
            raise ValueError(f'fl_risk {risk!r} although L* = {L["label"]} is not B0 (PROTOCOL Sec. 4.3)')
        risk_env, risk_why = None, f'L* = {L["label"]} is not B0: fl_risk is not run (PROTOCOL Sec. 4.3)'
    elif not isinstance(risk, dict) or 'lease_point' not in risk:
        raise ValueError(f'L* = B0 but the freeze holds no fl_risk record ({risk!r}; select_stage.freeze)')
    elif risk['lease_point'] is None:
        risk_env, risk_why = None, 'L* = B0 and neither E5 nor E10 remains: fl_risk is not run (PROTOCOL Sec. 4.3)'
    elif risk['lease_point'] not in ('E5', 'E10') or risk['lease_point'] not in envs:
        raise ValueError(f'fl_risk lease point {risk["lease_point"]!r} is not an exported E5 / E10 envelope')
    else:
        risk_env = {'label': risk['lease_point'], **envs[risk['lease_point']]}
        risk_why = f'L* = B0: fl_risk at {risk["lease_point"]}, the better of E5 / E10 on lease_s1 (PROTOCOL Sec. 4.3)'
    return {**fr, 'A_star': a_star, 'age_params': age,
            'event': {'candidate': ev['candidate'], 'policy_params': ev_params},
            'risk': risk_env, 'risk_reason': risk_why}


def load_rl(tuning, path=RL_FREEZE, protocol=P2J.PROTOCOL):
    """The RL freeze as P4-P6 use it: p3_rl.load_rl_freeze (a frozen production record; every named file, network and
    job line verified there; PermissionError / ValueError as there), made from this tuning freeze (its sha256, d* and
    L*). Returns {'path', 'sha256', 'cited_lines', 'p_both_label', 'networks': {protocol arm: network}}, a network being
    {'family', 'name', 'path', 'abs_path', 'sha256' (the FILE sha256), 'n_inputs', 'a_det_depth'} as the job lines carry
    it (check_smoke_ext.expectation_problems reads name / family / n_inputs / sha256 / path)."""
    from framelease_v4.protocol import p3_rl as P3
    from framelease_v4.rl import qnet as Q
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f'{PJ.rel(path)}: no RL freeze yet (p3_rl.py run, PROTOCOL Sec. 5.9)')
    doc = P3.load_rl_freeze(path, require_cited=False, check_logs=True, protocol=protocol)
    tf = doc.get('tuning_freeze') or {}
    if (doc.get('d_star'), tf.get('sha256'), tf.get('d'), (tf.get('L_star') or {}).get('sha256')) \
            != (tuning['d'], tuning['sha256'], tuning['d'], tuning['L']['sha256']):
        raise ValueError(f'{PJ.rel(path)} was not made from the tuning freeze {tuning["path"]} (sha256 '
                         f'{tuning["sha256"]}, d* {tuning["d"]}, L* {tuning["L"]["label"]}): it names {tf}')
    nets = {}
    for arm, fam in QNET_FAMILY.items():
        if P3.ARM_OF.get(fam) != arm:
            raise ValueError(f'p3_rl.ARM_OF maps {fam} to {P3.ARM_OF.get(fam)}, not {arm} (PROTOCOL Sec. 5.6)')
        net = doc['families'][fam]['network']
        line = doc['job_lines'][arm]
        abs_path = line.get(Q.ENV_QNET)
        if not abs_path or not Path(abs_path).is_absolute() or abs_path != net['abs_path']:
            raise ValueError(f'{arm}: job line {Q.ENV_QNET}={abs_path!r} is not the network\'s absolute path '
                             '(finding QNET-1)')
        sha = PJ.sha256_file(abs_path)
        if (line.get('utility'), line.get('qnet_file_sha256'), net['family']) != (net['name'], sha, fam):
            raise ValueError(f'{arm}: job line {line} / network family {net["family"]!r} disagree with the network '
                             f'{net["name"]} (file sha256 {sha}, family {fam})')
        nets[arm] = {'family': fam, 'name': net['name'], 'path': PJ.rel(abs_path), 'abs_path': abs_path,
                     'sha256': sha, 'n_inputs': net['n_inputs'], 'a_det_depth': net['a_det_depth']}
    return {'path': doc['path'], 'sha256': doc['sha256'], 'cited_lines': doc['cited_lines'],
            'p_both_label': (doc.get('p_both') or {}).get('label'), 'networks': nets}


# ---------------------------------------------------------------------------------------- arms and lines

def frozen_arms(tuning, rl):
    """{protocol arm: {'protocol_arm', 'launcher_arm', 'launcher' ('v4' | 'ext'), 'config', 'policy_params',
    'envelope', 'network'}} of every arm of tiers 3-6 (PROTOCOL Sec. 4.1) at the frozen parameters; fl_risk only when
    the tuning freeze names its lease point."""
    L, d, u = dict(tuning['L']), tuning['d'], tuning['d_utility']
    out = {}

    def add(arm, config=None, params=None, envelope=None, network=None):
        out[arm] = {'protocol_arm': arm, 'launcher_arm': LAUNCHER_ARM.get(arm, arm),
                    'launcher': 'ext' if arm == GLOBAL_SHIELD else 'v4', 'config': config,
                    'policy_params': dict(params or {}), 'envelope': envelope, 'network': network}

    for arm in ('fixed_deep', 'fast_only', 'fl_original'):
        add(arm)
    add('age_only', f'A{tuning["A_star"]:.1f}_d{d}', tuning['age_params'])
    add('event_triggered', tuning['event']['candidate'], tuning['event']['policy_params'])
    add('fl_heuristic', f'{L["label"]}_d{d}', {'utility': u}, L)
    for arm in QNET_FAMILY:
        net = dict(rl['networks'][arm])
        add(arm, f'{L["label"]}_d{d}_{net["name"]}', {'utility': net['name']}, L, net)
    add(GLOBAL_SHIELD, f'{L["label"]}_d{d}', {'utility': u}, L)
    if tuning['risk'] is not None:
        add('fl_risk', f'{tuning["risk"]["label"]}_d{d}', {'utility': u}, dict(tuning['risk']))
    return out


def job_id(blk, arm, kappa, route):
    """v4<p4|p5|p6>_<protocol arm>[_<config>]_k<kappa>_s<seed>_r<route> (PROTOCOL Sec. 8.2)."""
    mid = f'{arm["protocol_arm"]}_{arm["config"]}' if arm['config'] else arm['protocol_arm']
    return f'{ID_PREFIX[blk["phase"]]}_{mid}_k{float(kappa):.1f}_s{int(blk["seed"])}_r{route}'


def output_dir(blk, arm, kappa):
    """PROTOCOL Sec. 8.6: matrix/<arm>, fig3/<arm>_k<kappa>, ablation/<arm>, replicates/<arm> (the protocol arm)."""
    a = arm['protocol_arm']
    sub = {'matrix': f'matrix/{a}', 'fig3': f'fig3/{a}_k{float(kappa):.1f}', 'ablation': f'ablation/{a}',
           'replicates': f'replicates/{a}'}[blk['layout']]
    return f'{OUT_REL}/{sub}'


def command(arm, route, port, out_dir, kappa, seed):
    """The v4 launcher argv of one line (the option order of p1_jobs.command, with the block's kappa and seed, and
    --utility-env FRAMELEASE_V4_QNET=<absolute path> for a Q-network arm)."""
    cmd = [PJ.PYTHON, '-B', PJ.LAUNCHER_REL, '--arm', arm['launcher_arm'], '--fast-prefix', PJ.FAST_PREFIX,
           '--kappa', f'{float(kappa):.1f}', '--seed', str(int(seed)), '--routes', PJ.ROUTES_XML_REL,
           '--route-id', str(route), '--port', str(int(port)), '--output-dir', out_dir,
           '--timeout-s', str(PJ.TIMEOUT_S), '--lock-wait-s', str(PJ.LOCK_WAIT_S)]
    if arm['envelope']:
        cmd += ['--envelope', arm['envelope']['path']]
    if arm['policy_params']:
        cmd += ['--policy-params', json.dumps(arm['policy_params'], sort_keys=True)]
    if arm['network']:
        from framelease_v4.rl import qnet as Q
        cmd += ['--utility-env', f'{Q.ENV_QNET}={arm["network"]["abs_path"]}']
    return cmd


def line_command(blk, arm, i, route, kappa):
    """The exact argv of line i of a block: command() for the v4 launcher, run_closed_loop_ext.job_command for
    fl_global_shield. line_problems compares every line with it, so an added option (a lease override, a runtime or
    lease parameter file, an actor-log setting; PROTOCOL Secs. 2.4, 7.4 fix the lease constants) is a problem."""
    out = output_dir(blk, arm, kappa)
    if arm['launcher'] == 'ext':
        from framelease_v4.arms_ext import run_closed_loop_ext as XL
        return XL.job_command(route, PJ.port_of(i), out, arm['envelope']['path'], arm['policy_params']['utility'],
                              kappa, blk['seed'], PJ.TIMEOUT_S, PJ.LOCK_WAIT_S)
    return command(arm, route, PJ.port_of(i), out, kappa, blk['seed'])


def arm_pins(arm, cache=None):
    """require_sha256 of the arm's lines (PROTOCOL Sec. 8.3): the 49 code files of every P1 line (jobs_v4.code_pins),
    plus the envelope, plus the network file (its repository-relative path inside the project), plus the extension
    sources for fl_global_shield (run_closed_loop_ext.job_pins: 55 pins). Cached per arm in `cache`."""
    if cache is not None and arm['protocol_arm'] in cache:
        return dict(cache[arm['protocol_arm']])
    if arm['launcher'] == 'ext':
        from framelease_v4.arms_ext import run_closed_loop_ext as XL
        pins = XL.job_pins(arm['envelope']['path'])
    else:
        extra = ([arm['envelope']['path']] if arm['envelope'] else []) + \
            ([arm['network']['path']] if arm['network'] else [])
        pins = PJ.code_pins(extra)
    if cache is not None:
        cache[arm['protocol_arm']] = dict(pins)
    return pins


def freeze_refs(tuning, rl):
    """The freezes as every line and block spec records them."""
    return {'tuning_freeze': {'path': tuning['path'], 'sha256': tuning['sha256']},
            'rl_freeze': {'path': rl['path'], 'sha256': rl['sha256']}}


def make_line(blk, arm, route, kappa, port, row, refs, d_star, cache=None):
    """One gpu_queue line: the v4 launcher (p1_jobs / p2_jobs line keys plus protocol_arm, the freezes and, for a
    Q-network arm, network / d_star / utility_env, the keys check_smoke_ext reads) or, for fl_global_shield,
    run_closed_loop_ext.job_line with the same descriptive keys."""
    out = output_dir(blk, arm, kappa)
    common = {'matrix': MATRIX, 'block_no': blk['no'], 'budget_block': blk['budget'],
              'protocol_arm': arm['protocol_arm'], 'candidate': arm['protocol_arm'], 'config': arm['config'],
              'route_index': row['index'], 'route_set': blk['routes'], 'scenario_type': row['scenario_type'],
              'town': row['town'], 'training_route': False, 'test_route': True, **refs,
              'not_for_launch_before': NOT_BEFORE}
    if arm['policy_params'].get('utility') is not None:
        common['d_star'] = int(d_star)
    if arm['launcher'] == 'ext':
        from framelease_v4.arms_ext import run_closed_loop_ext as XL
        env = arm['envelope']
        job = XL.job_line(route, port, out, env['path'], env['label'], utility=arm['policy_params']['utility'],
                          job_id=job_id(blk, arm, kappa, route), kappa=kappa, seed=blk['seed'],
                          wall_cap_s=PJ.WALL_CAP_S, tier=blk['tier'], phase=blk['phase'], block=blk['block'],
                          envelope_config=env.get('config'), **common)
        return {**job, 'launcher': EXT_LAUNCHER_REL}
    job = {'id': job_id(blk, arm, kappa, route), 'kind': 'closed_loop', 'tier': blk['tier'],
           'cmd': command(arm, route, port, out, kappa, blk['seed']), 'wall_cap_s': PJ.WALL_CAP_S,
           'phase': blk['phase'], 'block': blk['block'], **common, 'arm_name': arm['launcher_arm'],
           'launcher': PJ.LAUNCHER_REL, 'policy_params': dict(arm['policy_params']), 'envelope': arm['envelope'],
           'kappa': float(kappa), 'seed': int(blk['seed']), 'fast_prefix': PJ.FAST_PREFIX.split(','),
           'route_id': str(route), 'port': int(port), 'output_dir': out}
    if arm['network']:
        from framelease_v4.rl import qnet as Q
        net = arm['network']
        job['network'] = {k: net[k] for k in ('name', 'family', 'n_inputs', 'sha256', 'path', 'abs_path')}
        job['utility_env'] = {Q.ENV_QNET: net['abs_path']}
    job['require_sha256'] = arm_pins(arm, cache)
    return job


def budget_runs(blk):
    """The block's run count in the registered budget (make_protocol_tables.plan_blocks('FULL'), PROTOCOL Sec. 10.1)."""
    from framelease_v4.protocol import make_protocol_tables as MPT
    rows = [b for b in MPT.plan_blocks(VARIANT) if b[2] == blk['budget']]
    if len(rows) != 1 or (rows[0][0], rows[0][1]) != (blk['phase'], blk['tier']):
        raise ValueError(f'{blk["block"]}: budget block {blk["budget"]} is not ({blk["phase"]}, tier {blk["tier"]}) in '
                         'make_protocol_tables.plan_blocks')
    return int(rows[0][4])


SPEC_JOB_KEYS = ('line', 'id', 'block', 'protocol_arm', 'launcher_arm', 'launcher', 'route_id', 'route_index', 'kappa',
                 'seed', 'config', 'policy_params', 'utility', 'envelope_label', 'envelope_sha256', 'network_name',
                 'network_family', 'network_sha256', 'output_dir', 'port')


def spec_job(i, j):
    """The block-spec entry of line i (GAP_AUDIT G-1 block spec, read by the aggregator through spec_jobs): the
    protocol arm, route, kappa, seed, configuration, utility, and the envelope and network sha256 (the network's FILE
    sha256: a name pins neither B_pi nor the provenance)."""
    env, net = j.get('envelope') or {}, j.get('network') or {}
    return {'line': i + 1, 'id': j['id'], 'block': j['block'], 'protocol_arm': j['protocol_arm'],
            'launcher_arm': j['arm_name'], 'launcher': j['launcher'], 'route_id': j['route_id'],
            'route_index': j['route_index'], 'kappa': j['kappa'], 'seed': j['seed'], 'config': j['config'],
            'policy_params': j['policy_params'], 'utility': (j['policy_params'] or {}).get('utility'),
            'envelope_label': env.get('label'), 'envelope_sha256': env.get('sha256'), 'network_name': net.get('name'),
            'network_family': net.get('family'), 'network_sha256': net.get('sha256'), 'output_dir': j['output_dir'],
            'port': j['port']}


def build_block(blk, arms, tuning, rl, cache=None):
    """(job lines, block spec) of one block (nothing written). A block whose arms do not run (s_risk without a fl_risk
    lease point) has no line; its spec records why."""
    refs = freeze_refs(tuning, rl)
    present = [arms[a] for a in blk['arms'] if a in arms]
    routes = route_subset(blk['routes'])
    rows = route_table()
    lines, order = [], []
    if len(present) == len(blk['arms']):
        cells = [(a, float(k)) for a in present for k in blk['kappas']]
        pairs, order = PJ.ordered(blk['no'], routes, cells)
        lines = [make_line(blk, a, r, k, PJ.port_of(i), rows[r], refs, tuning['d'], cache)
                 for i, ((a, k), r) in enumerate(pairs)]
    elif present:
        raise ValueError(f'{blk["block"]}: only {[a["protocol_arm"] for a in present]} of {blk["arms"]} are defined')
    expected = budget_runs(blk) if lines or blk['block'] != 's_risk' else 0
    per_arm = {}
    for j in lines:
        key = f'{j["protocol_arm"]}_k{j["kappa"]:.1f}'
        per_arm[key] = per_arm.get(key, 0) + 1
    spec = {'schema': STAGE_SCHEMA, 'variant': VARIANT, 'phase': blk['phase'], 'block': blk['block'],
            'block_no': blk['no'], 'tier': blk['tier'], 'budget_block': blk['budget'], 'description': blk['what'],
            'protocol_arms': list(blk['arms']), 'kappas': list(blk['kappas']), 'seed': blk['seed'],
            'route_set': blk['routes'], 'routes': routes, 'route_order': order, 'order_rule': ORDER_RULE,
            'n_lines': len(lines), 'expected_runs_sec_10_1': expected, 'runs_per_arm_kappa': per_arm,
            'skipped': None if lines else tuning['risk_reason'],
            'arms': {a['protocol_arm']: {**{k: a[k] for k in ('launcher_arm', 'launcher', 'config', 'policy_params',
                                                              'envelope', 'network')},
                                         'launcher_rel': (EXT_LAUNCHER_REL if a['launcher'] == 'ext'
                                                          else PJ.LAUNCHER_REL),
                                         'output_dirs': {f'{k:.1f}': output_dir(blk, a, k) for k in blk['kappas']},
                                         'pins': {'n': len(arm_pins(a, cache)), 'sha256': PJ.sha256_text(
                                             json.dumps(arm_pins(a, cache), sort_keys=True))}}
                     for a in present},
            'jobs': [spec_job(i, j) for i, j in enumerate(lines)],
            **refs, 'tuning_freeze_cited_lines': tuning['cited_lines'], 'rl_freeze_cited_lines': rl['cited_lines'],
            'protocol': tuning['protocol'], 'p_both_label': rl['p_both_label'],
            'inputs': {tuning['path']: tuning['sha256'], rl['path']: rl['sha256'], **registered_inputs()},
            'queue': QUEUE_REL, 'not_for_launch_before': NOT_BEFORE,
            'not_registered_details': 'block numbers 11-16, the job file names, the Fig. 3 cell order and the queue '
                                      'name are entered in PROTOCOL Sec. 13.2 with the test freeze',
            'rules': 'PROTOCOL Secs. 2.6, 3.1, 4.1, 7.2-7.5, 8.2-8.4, 8.6, 10.1 (framelease_v4/protocol/test_jobs.py)'}
    return lines, spec


def build_all(tuning, rl):
    """[(block definition, job lines, block spec)] of the six blocks in file order (nothing written)."""
    arms = frozen_arms(tuning, rl)
    cache = {}
    return [(blk, *build_block(blk, arms, tuning, rl, cache)) for blk in BLOCKS]


# ---------------------------------------------------------------------------------------- checks (CPU only)

def _utility_envs(cmd):
    return [cmd[k + 1] for k in range(len(cmd) - 1) if cmd[k] == '--utility-env']


def line_problems(blk, i, j, arm, refs, routes, cache=None):
    """Problems of line i of a block found without the launcher (the arm, its launcher, envelope, parameters,
    network, kappa / seed, route, id, port and output directory); the gpu_queue contract and the pins are checked by
    static_problems."""
    from framelease_v4.rl import qnet as Q
    jid, cmd, o = j['id'], j['cmd'], _opts(j['cmd'])
    p = []
    launcher = EXT_LAUNCHER_REL if arm['launcher'] == 'ext' else PJ.LAUNCHER_REL
    if cmd[:3] != [PJ.PYTHON, '-B', launcher] or j.get('launcher') != launcher:
        p.append(f'{jid}: not the {launcher} command')
    want = ('closed_loop', blk['tier'], PJ.WALL_CAP_S, blk['phase'], blk['block'], blk['no'], blk['budget'], MATRIX)
    if tuple(j.get(k) for k in ('kind', 'tier', 'wall_cap_s', 'phase', 'block', 'block_no', 'budget_block',
                                'matrix')) != want:
        p.append(f'{jid}: kind / tier / wall cap / phase / block / matrix differ from {want}')
    if j.get('port') != PJ.port_of(i) or o.get('--port') != str(PJ.port_of(i)):
        p.append(f'{jid}: port {j.get("port")} != 2600 + 10 ({i} mod 4)')
    if (o.get('--fast-prefix'), o.get('--timeout-s'), o.get('--lock-wait-s'), o.get('--routes')) \
            != (PJ.FAST_PREFIX, str(PJ.TIMEOUT_S), str(PJ.LOCK_WAIT_S), PJ.ROUTES_XML_REL) \
            or j.get('fast_prefix') != PJ.FAST_PREFIX.split(','):
        p.append(f'{jid}: --fast-prefix / --timeout-s / --lock-wait-s / --routes are not the Sec. 8.2 values')
    k, s, r = j.get('kappa'), j.get('seed'), str(j.get('route_id'))
    if k not in blk['kappas'] or o.get('--kappa') != f'{float(k):.1f}' or s != blk['seed'] \
            or isinstance(s, bool) or o.get('--seed') != str(blk['seed']):
        p.append(f'{jid}: kappa {k} / seed {s} (block {blk["block"]}: kappa in {list(blk["kappas"])}, seed '
                 f'{blk["seed"]})')
        return p
    if r not in routes or o.get('--route-id') != r or (j.get('test_route'), j.get('training_route')) != (True, False):
        p.append(f'{jid}: route {r} is not a test route of subset {blk["routes"]} (PROTOCOL Secs. 3.1, 7)')
        return p
    if (o.get('--arm'), j.get('arm_name'), j.get('protocol_arm')) != (arm['launcher_arm'], arm['launcher_arm'],
                                                                       arm['protocol_arm']):
        p.append(f'{jid}: --arm / arm_name / protocol_arm are not {arm["launcher_arm"]} / {arm["protocol_arm"]}')
    env = arm['envelope']
    if (arm['protocol_arm'] in ENVELOPE_ARMS) != bool(env):
        p.append(f'{jid}: {arm["protocol_arm"]} takes an envelope iff it has a suffix or global lease (PROTOCOL '
                 'Sec. 4.1)')
    if env:
        if o.get('--envelope') != env['path'] or {x: (j.get('envelope') or {}).get(x) for x in env} != env \
                or (j.get('require_sha256') or {}).get(env['path']) != env['sha256']:
            p.append(f'{jid}: the envelope is not {env["label"]} ({env["path"]}, pinned)')
    elif '--envelope' in o or j.get('envelope'):
        p.append(f'{jid}: an envelope on an arm without a suffix lease')
    if json.loads(o.get('--policy-params', '{}')) != arm['policy_params'] \
            or j.get('policy_params') != arm['policy_params']:
        p.append(f'{jid}: --policy-params / policy_params are not the frozen {arm["policy_params"]}')
    envs = _utility_envs(cmd)
    if arm['network']:
        from framelease_v4.protocol import check_smoke_ext as CSX
        net = arm['network']
        if envs != [f'{Q.ENV_QNET}={net["abs_path"]}'] or j.get('utility_env') != {Q.ENV_QNET: net['abs_path']}:
            p.append(f'{jid}: --utility-env is not {Q.ENV_QNET}=<the absolute path of {net["name"]}>')
        if j.get('network', {}).get('sha256') != net['sha256'] or j.get('require_sha256', {}).get(net['path']) \
                != net['sha256']:
            p.append(f'{jid}: the network file {net["path"]} is not pinned with the RL freeze sha256')
        p += [f'{jid}: {x}' for x in CSX.qnet_line_problems(j)]
    elif envs or j.get('network') or j.get('utility_env'):
        p.append(f'{jid}: a utility environment on an arm without a Q-network')
    out = output_dir(blk, arm, k)
    if j.get('output_dir') != out or o.get('--output-dir') != out or 'jobs.d' in Path(out).parts:
        p.append(f'{jid}: output directory {j.get("output_dir")} != {out} (PROTOCOL Sec. 8.6)')
    want = line_command(blk, arm, i, r, k)
    if cmd != want:
        p.append(f'{jid}: the command is not the generated one (an option added, dropped or changed: '
                 f'{sorted(set(map(str, cmd)) ^ set(want))[:4]}; PROTOCOL Secs. 2.4, 7.4, 8.2)')
    if jid != job_id(blk, arm, k, r):
        p.append(f'{jid}: id != {job_id(blk, arm, k, r)}')
    if j.get('not_for_launch_before') != NOT_BEFORE or any(j.get(x) != v for x, v in refs.items()):
        p.append(f'{jid}: not_for_launch_before or the freeze references differ')
    return p


def unregistered_pins(pins, arm, registered):
    """The pins of a line of `arm` that are not at the sha256 of the registered P1 lines (registered =
    registration.job_pins(): the pins of the registered P1 job files). Every pin is one of them (the 49 code files,
    the envelope) except the network file of a Q-network arm and the extension sources of fl_global_shield, which the
    test freeze registers."""
    from framelease_v4.arms_ext import arms_ext as X
    own = ({arm['network']['path']} if arm['network'] else set()) \
        | (set(X.EXT_CODE) if arm['launcher'] == 'ext' else set())
    return sorted(p for p, sha in pins.items() if p not in own and registered.get(p) != sha)


def static_problems(blk, lines, arms, tuning, rl, cache=None):
    """Problems of one block found without the launcher: gpu_queue's job contract, the pins (the arm's expected set,
    against the registered P1 pins (unregistered_pins: a registered file changed after registration is pinned at
    its new sha256 otherwise) and against the tree, once per distinct pin set), line_problems of every line,
    completeness (every arm x kappa x route of the block once) and the run count of PROTOCOL Sec. 10.1."""
    from framelease_v2 import gpu_queue as Q
    refs = freeze_refs(tuning, rl)
    routes = set(route_subset(blk['routes']))
    present = [arms[a] for a in blk['arms'] if a in arms]
    registered, unreg = REG.job_pins(), {}
    problems, cells, checked = [], [], {}
    ids = [j.get('id') for j in lines]
    if len(set(ids)) != len(ids):
        problems.append(f'{blk["block"]}: duplicate job ids')
    for i, j in enumerate(lines):
        bad = Q.validate_job(j)
        if bad:
            problems.append(f'{j.get("id")}: gpu_queue rejects the job: {bad}')
            continue
        arm = arms.get(j.get('protocol_arm'))
        if arm is None or arm['protocol_arm'] not in blk['arms']:
            problems.append(f'{j["id"]}: protocol arm {j.get("protocol_arm")!r} is not an arm of {blk["block"]} '
                            f'{list(blk["arms"])}')
            continue
        if j.get('require_sha256') != arm_pins(arm, cache):
            problems.append(f'{j["id"]}: require_sha256 is not the pin set of {arm["protocol_arm"]} (PROTOCOL Sec. '
                            '8.3)')
        key = json.dumps(j['require_sha256'], sort_keys=True)
        if key not in checked:
            checked[key] = Q.pin_mismatches(j['require_sha256'])
        if checked[key]:
            problems.append(f'{j["id"]}: pinned files differ from the tree: {[m["file"] for m in checked[key]][:5]}')
        if (arm['protocol_arm'], key) not in unreg:
            unreg[arm['protocol_arm'], key] = unregistered_pins(j['require_sha256'], arm, registered)
        if unreg[arm['protocol_arm'], key]:
            problems.append(f'{j["id"]}: pinned at another sha256 than the registered P1 lines pin (registration.'
                            f'job_pins): {unreg[arm["protocol_arm"], key][:5]} (PROTOCOL Secs. 8.3, 13.1: a registered '
                            'file changes only by an amendment)')
        problems += line_problems(blk, i, j, arm, refs, routes, cache)
        cells.append((arm['protocol_arm'], float(j.get('kappa') or 0), str(j.get('route_id'))))
    want = {(a['protocol_arm'], float(k), r) for a in present for k in blk['kappas'] for r in routes}
    if len(set(cells)) != len(cells) or set(cells) != want:
        problems.append(f'{blk["block"]}: the lines are not every arm x kappa x route of the block once '
                        f'({len(cells)} lines, {len(set(cells))} distinct cells, {len(want - set(cells))} of the '
                        f'{len(want)} cells missing, {len(set(cells) - want)} foreign)')
    if blk['block'] == 's_risk' and (tuning['risk'] is None) != (not lines):
        problems.append(f's_risk: {len(lines)} lines, but {tuning["risk_reason"]}')
    expected = budget_runs(blk) if present else 0
    if len(lines) != expected:
        problems.append(f'{blk["block"]}: {len(lines)} lines != {expected} runs of block {blk["budget"]} in PROTOCOL '
                        'Sec. 10.1')
    return problems


def cross_block_problems(built):
    """Problems across the six files: an id twice (gpu_queue skips a duplicate id of a later file), an output directory
    shared by two blocks or by two (protocol arm, kappa, seed) cells (the aggregator's ablation/<arm> label and run
    selection read it), and the P4-P6 total of PROTOCOL Sec. 10.1."""
    problems, ids, dirs = [], {}, {}
    for blk, lines, _ in built:
        for j in lines:
            if j['id'] in ids:
                problems.append(f'{j["id"]}: in {ids[j["id"]]} and in {blk["block"]}')
            ids.setdefault(j['id'], blk['block'])
            dirs.setdefault(j['output_dir'], set()).add((blk['block'], j['protocol_arm'], j['kappa'], j['seed']))
    for d, cells in sorted(dirs.items()):
        if len(cells) != 1:
            problems.append(f'{d}: output directory shared by {sorted(cells)}')
    total = sum(len(lines) for _, lines, _ in built)
    want = sum(budget_runs(blk) for blk, lines, _ in built if lines or blk['block'] != 's_risk')
    if total != want:
        problems.append(f'P4-P6: {total} lines != {want} runs of PROTOCOL Sec. 10.1')
    return problems


def existing_runs(lines, root=ROOT, queue=QUEUE_REL):
    """Test-route runs that already exist (PROTOCOL Secs. 8.1 and 9.11: no test-route run before the test freeze;
    GAP_AUDIT G-1 'no run directory exists yet'): a non-empty runs/ in an output directory of the lines
    (p2_jobs.runs_present) or in any directory of the P4-P6 roots matrix/, fig3/, ablation/, replicates/ (Sec. 8.6),
    and a non-empty status.jsonl of the P4-P6 queue (its runner has started a job). Only the existence of a path is
    read, never a result."""
    out = list(P2J.runs_present(lines, root))
    base = Path(root) / OUT_REL
    for sub in P4P6_ROOTS:
        for runs in sorted((base / sub).glob('*/runs')):
            if runs.is_dir() and any(runs.iterdir()) and PJ.rel(runs) not in out:
                out.append(PJ.rel(runs))
    status = Path(root) / queue / 'status.jsonl'
    if status.is_file() and status.stat().st_size > 0:
        out.append(PJ.rel(status))
    return out


def run_problems(lines, root=ROOT):
    """existing_runs as check problems."""
    return [f'{r}: a test-route run exists (PROTOCOL Secs. 8.1, 9.11: no test-route run starts before the test freeze; '
            'the P4-P6 job files are generated and checked before any)' for r in existing_runs(lines, root)]


def check_in_process(job):
    """{'id', 'problems', ...}: the v4 launcher's own parsing, configuration build and preflight in this process for
    any arm, against the job's own kappa and seed (p1_jobs.check_in_process asserts kappa 1.0 and seed 11), its route,
    launcher arm, fast prefix, policy parameters, envelope sha256 (none for the arms without a suffix lease), the shield
    depth limit 10 and the utility block (none for 'heuristic'; a_det^d by name; a Q-network by name, absolute
    FRAMELEASE_V4_QNET and file sha256). Not thread-safe (stdout / stderr redirected, the environment restored, the
    working directory set to the project root): call it sequentially."""
    from framelease_v4.arms import run_closed_loop_v4 as RL
    from framelease_v4.rl import qnet as Q
    out = {'id': job['id'], 'problems': []}
    cmd = job['cmd']
    if cmd[:3] != [PJ.PYTHON, '-B', PJ.LAUNCHER_REL]:
        out['problems'].append('not the v4 launcher command')
        return out
    saved = dict(os.environ)
    try:
        with P2J._at_root(), contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            args = RL.parse_args(cmd[3:])
            prep = RL.prepare(args)
        cfg, info = prep['cfg'], prep['route']
        if (info['route_id'], info['town'], info['scenarios']) != (job['route_id'], job['town'],
                                                                   [job['scenario_type']]):
            out['problems'].append(f'route {info} does not match the job')
        if (cfg['arm'], prep['fp']['options']) != (job['arm_name'], job['fast_prefix']):
            out['problems'].append('arm / fast prefix differ from the job')
        rt = cfg['agent']['runtime']
        if float(rt['kappa']) != float(job['kappa']) or cfg['agent']['seed'] != job['seed']:
            out['problems'].append(f'kappa / seed of the configuration ({rt["kappa"]}, {cfg["agent"]["seed"]}) differ '
                                   f'from the job ({job["kappa"]}, {job["seed"]})')
        if cfg['kind'] in ('age', 'shield') and rt.get('max_depth') != AV.SHIELD_MAX_DEPTH:
            out['problems'].append('shield depth limit is not 10')
        pp = dict(cfg['agent']['policy_params'] or {})
        for k, v in job['policy_params'].items():
            if pp.get(k) != v:
                out['problems'].append(f'policy parameter {k}: {pp.get(k)!r} != {v!r}')
        if (cfg.get('v3') or {}).get('envelope_sha256') != (job['envelope'] or {}).get('sha256'):
            out['problems'].append('envelope sha256 of the configuration differs from the job')
        u, name = cfg.get('utility') or {}, job['policy_params'].get('utility')
        net = job.get('network')
        if net:
            want = (net['name'], {Q.ENV_QNET: net['abs_path']}, {net['abs_path']: net['sha256']})
        elif name in (None, 'heuristic'):
            want = (None, None, None)
        else:
            want = (name, {}, {})
        if (u.get('name'), u.get('env'), u.get('env_files_sha256')) != want:
            out['problems'].append(f'utility block {u} is not the job\'s utility {want}')
        out['agent_runtime_config_sha256'] = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
        out['utility'] = u.get('name') or name
        out['kappa'], out['seed'] = rt['kappa'], cfg['agent']['seed']
    except SystemExit as e:
        out['problems'].append(f'SystemExit: {e}')
    except BaseException as e:  # noqa: BLE001
        out['problems'].append(f'{type(e).__name__}: {e}')
    finally:
        os.environ.clear()
        os.environ.update(saved)
    return out


def check_ext_line(job, dry_run=True):
    """run_closed_loop_ext.check_job_line of a fl_global_shield line from the project root (gpu_queue's contract, the
    pins P1 + E* + the extension sources, the in-process preparation, the fixed lease constants: no lease override and
    the cap H_bar 2.5 s, and the --dry-run of the exact command)."""
    from framelease_v4.arms_ext import run_closed_loop_ext as XL
    with P2J._at_root():
        return XL.check_job_line(job, dry_run=dry_run)


def check_lines(blk, lines, arms, tuning, rl, dry_run=True, workers=MAX_WORKERS, cache=None, root=ROOT):
    """Every line of one block: static_problems, no run in an output directory of the block (run directories under
    `root`), the in-process launcher checks (sequential; the extension arm through check_ext_line, with its own
    --dry-run) and the --dry-run subprocesses of the v4 lines (p1_jobs.dry_run_line, at most MAX_WORKERS threads, each
    with its own copy of the environment). An output directory created by a check is looked for under the project
    ROOT, not under `root`: both launchers resolve --output-dir there (p2_jobs._at_root, dry_run_line cwd=ROOT).
    Returns (per-line results, problems)."""
    if not 1 <= int(workers) <= MAX_WORKERS:
        raise ValueError(f'workers must be 1..{MAX_WORKERS}')
    problems = static_problems(blk, lines, arms, tuning, rl, cache)
    problems += [f'{r}: a test-route run exists in an output directory of {blk["block"]} (PROTOCOL Secs. 8.1, 9.11)'
                 for r in P2J.runs_present(lines, root)]
    if dry_run and not PJ._stack_ready():
        raise SystemExit('--check needs the official stack variables (source linux/env.sh): CHECKPOINT is not set')
    dirs_before = {j['output_dir']: (ROOT / j['output_dir']).exists() for j in lines}
    results, v4 = [], []
    for j in lines:
        if j.get('launcher') == EXT_LAUNCHER_REL:
            results.append(check_ext_line(j, dry_run))
        else:
            results.append(check_in_process(j))
            v4.append((results[-1], j))
    if dry_run:
        env = P2J._dry_run_env()
        todo = [(r, j) for r, j in v4 if not r['problems']]
        with ThreadPoolExecutor(max_workers=int(workers)) as ex:
            outs = list(ex.map(lambda rj: PJ.dry_run_line(rj[1], dict(env)), todo))
        for (r, _), res in zip(todo, outs):
            PJ._merge_dry_run(r, res)
    for d, existed in dirs_before.items():
        if not existed and (ROOT / d).exists():
            problems.append(f'{d}: created by a check')
    for r in results:
        r['ok'] = not r['problems']
    problems += [f'{r["id"]}: {p}' for r in results for p in r['problems']]
    return results, problems


# ---------------------------------------------------------------------------------------- writing

def block_paths(blk, jobs_dir=None):
    base = Path(jobs_dir or JOBS_DIR) / VARIANT / f'b{blk["no"]:02d}_{blk["block"]}'
    return Path(str(base) + '.jsonl'), Path(str(base) + '.stage.json'), Path(str(base) + '.check.json')


def recorded(path, protocol=P2J.PROTOCOL):
    """1-based lines of PROTOCOL Sec. 13.2 that cite the sha256 of an existing file ([] if none or no file)."""
    path = Path(path)
    if not path.is_file():
        return []
    return P2J.citations(PJ.sha256_file(path), Path(protocol).read_text(encoding='utf-8'))


def check_doc(blk, path, text, results, problems, cross):
    """The block's check record (the p1_jobs.py / p2_jobs.py contract), with the sha256 of the checking modules."""
    from framelease_v4.arms_ext import run_closed_loop_ext as XL
    from framelease_v4.protocol import check_smoke_ext as CSX
    from framelease_v4.protocol import p3_rl as P3
    return {'schema': CHECK_SCHEMA, 'block': blk['block'], 'job_file': PJ.rel(path),
            'job_file_sha256': PJ.sha256_text(text), 'n_lines': len(results), 'problems': problems,
            'cross_block_problems': cross,
            'all_dry_runs_ok': bool(results) and all(r.get('ok') and (r.get('dry_run') or {}).get('status')
                                                     == 'NOT_STARTED' for r in results),
            'lines': results, 'script_sha256': PJ.sha256_file(Path(__file__)),
            'reused_sha256': {PJ.rel(m.__file__): PJ.sha256_file(m.__file__) for m in (PJ, P2J, SS, P3, CSX, XL)}}


def write_all(built, checked, cross, jobs_dir=None, protocol=P2J.PROTOCOL, force=False, root=ROOT):
    """Write every block's job file, block spec and check, and index.json (refusals: PermissionError for a queue path,
    existing runs or a file recorded in PROTOCOL Sec. 13.2 that would change; FileExistsError for an existing file
    with other content without force, or files of a block that has no lines now). checked: {block: (results,
    problems)}. Nothing is written unless every refusal test passes."""
    base = Path(jobs_dir or JOBS_DIR) / VARIANT
    hits = P2J.queue_parts(base)
    if hits:
        raise PermissionError(f'refusing to write under {base}: {hits[0]} belongs to a runner queue (the job files are '
                              'written outside every queue and copied into queue_p4/jobs.d by hand)')
    runs = existing_runs([j for _, lines, _ in built for j in lines], root)
    if runs:
        raise PermissionError(f'refusing to write: {runs[0]} exists (a test-route run: P4-P6 have started)')
    todo, index = [], []
    for blk, lines, spec in built:
        paths = block_paths(blk, jobs_dir)
        if not lines:
            stale = [PJ.rel(p) for p in paths if p.exists()]
            if stale:
                raise FileExistsError(f'{blk["block"]} has no lines now ({spec["skipped"]}), but {stale} exist: '
                                      'remove them by hand before the job files are generated again')
            index.append({'block': blk['block'], 'no': blk['no'], 'tier': blk['tier'], 'phase': blk['phase'],
                          'budget_block': blk['budget'], 'n_lines': 0, 'skipped': spec['skipped']})
            continue
        text = P2J.jsonl(lines)
        spec = {**spec, 'job_file': PJ.rel(paths[0]), 'job_file_sha256': PJ.sha256_text(text)}
        spec_text = json.dumps(spec, indent=1, sort_keys=True) + '\n'
        results, problems = checked[blk['block']]
        check_text = json.dumps(check_doc(blk, paths[0], text, results, problems, cross), indent=1,
                                sort_keys=True) + '\n'
        todo += list(zip(paths, (text, spec_text, check_text)))
        index.append({'block': blk['block'], 'no': blk['no'], 'tier': blk['tier'], 'phase': blk['phase'],
                      'budget_block': blk['budget'], 'n_lines': len(lines),
                      'expected_runs_sec_10_1': spec['expected_runs_sec_10_1'], 'job_file': PJ.rel(paths[0]),
                      'job_file_sha256': PJ.sha256_text(text), 'stage_spec': PJ.rel(paths[1]),
                      'stage_spec_sha256': PJ.sha256_text(spec_text), 'check': PJ.rel(paths[2]),
                      'check_sha256': PJ.sha256_text(check_text), 'skipped': None})
    first = next(spec for _, lines, spec in built)
    idx = {'schema': INDEX_SCHEMA, 'variant': VARIANT, 'blocks': index, 'n_lines': sum(b['n_lines'] for b in index),
           'cross_block_problems': cross, 'queue': QUEUE_REL, 'tuning_freeze': first['tuning_freeze'],
           'rl_freeze': first['rl_freeze'], 'protocol': first['protocol'], 'not_for_launch_before': NOT_BEFORE,
           'enqueue': f'after the test freeze: copy the job files, in name order, into {QUEUE_REL}/jobs.d/ (one queue '
                      'for tiers 3-6; a cut takes the bottom tiers first, PROTOCOL Sec. 10.2)',
           'script_sha256': PJ.sha256_file(Path(__file__))}
    todo.append((base / INDEX_NAME, json.dumps(idx, indent=1, sort_keys=True) + '\n'))
    for path, new in todo:
        if path.exists() and path.read_text(encoding='utf-8') != new:
            cited = recorded(path, protocol)
            if cited:
                raise PermissionError(f'refusing to overwrite {PJ.rel(path)}: its sha256 is recorded in PROTOCOL Sec. '
                                      f'13.2 (lines {cited}); a recorded file is never rewritten')
            if not force:
                raise FileExistsError(f'refusing to overwrite {PJ.rel(path)} with other content (use --force; no '
                                      'P4-P6 run may exist)')
    base.mkdir(parents=True, exist_ok=True)
    for path, new in todo:
        path.write_text(new, encoding='utf-8')
    return {'index': PJ.rel(base / INDEX_NAME), 'index_sha256': PJ.sha256_file(base / INDEX_NAME),
            'blocks': index}


def summary_lines(tuning, rl, built, jobs_dir=None):
    L = tuning['L']
    out = [f'P4-P6 test blocks: {sum(len(x[1]) for x in built)} job lines -> '
           f'{PJ.rel(Path(jobs_dir or JOBS_DIR) / VARIANT)} (NOT launched, NOT enqueued)',
           f'  tuning freeze {tuning["path"]} sha256 {tuning["sha256"]} (cited in PROTOCOL Sec. 13.2, line(s) '
           f'{tuning["cited_lines"]}): L* = {L["label"]}, d* = {tuning["d"]}, A* = {tuning["A_star"]}, '
           f'event {tuning["event"]["candidate"]}; {tuning["risk_reason"]}',
           f'  RL freeze {rl["path"]} sha256 {rl["sha256"]}; P_both label {rl["p_both_label"]}; networks '
           + ', '.join(f'{a} {n["name"]} ({n["sha256"][:12]})' for a, n in rl['networks'].items())]
    for blk, lines, spec in built:
        out.append(f'  {blk["block"]:<9} b{blk["no"]:02d} tier {blk["tier"]} {blk["phase"]}: {len(lines):>3} lines '
                   f'(Sec. 10.1: {spec["expected_runs_sec_10_1"]})' + (f'; {spec["skipped"]}' if not lines else ''))
        for j in lines[:2]:
            out.append(f'    {j["id"]:<72} port {j["port"]} -> {j["output_dir"]}')
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--selection', type=Path, default=SS.FREEZE_PATH, help='the tuning freeze (selection.json)')
    ap.add_argument('--rl-freeze', type=Path, default=RL_FREEZE, help='the RL freeze (rl_freeze.json)')
    ap.add_argument('--protocol', type=Path, default=P2J.PROTOCOL)
    ap.add_argument('--seal', type=Path, default=P2J.SEAL)
    ap.add_argument('--jobs-dir', type=Path, default=JOBS_DIR)
    ap.add_argument('--check', action='store_true', help='validate every line (needs source linux/env.sh)')
    ap.add_argument('--no-dry-run', action='store_true', help='skip the subprocess --dry-run of each line')
    ap.add_argument('--write', action='store_true', help='write the job files, block specs, checks and index '
                                                         '(needs --check with the dry runs)')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--workers', type=int, default=MAX_WORKERS,
                    help=f'dry-run subprocesses in parallel (1..{MAX_WORKERS})')
    a = ap.parse_args(argv)
    if a.write and (not a.check or a.no_dry_run):
        ap.error('--write requires --check with the --dry-run of every line (PROTOCOL Sec. 8.2)')
    if not 1 <= a.workers <= MAX_WORKERS:
        ap.error(f'--workers must be 1..{MAX_WORKERS}')
    try:
        tuning = load_tuning(a.selection, a.protocol, a.seal)
        rl = load_rl(tuning, a.rl_freeze, a.protocol)
        built = build_all(tuning, rl)
    except (FileNotFoundError, ValueError, PermissionError) as e:
        print(f'REFUSED: {e}', file=sys.stderr)
        return 2
    print('\n'.join(summary_lines(tuning, rl, built, a.jobs_dir)))
    started = run_problems([j for _, lines, _ in built for j in lines])
    if started:
        print('  NOTE: ' + '\n  NOTE: '.join(started[:3]) + '\n  the job files can no longer be written',
              file=sys.stderr)
    if not a.check:
        return 0
    arms, cache = frozen_arms(tuning, rl), {}
    cross = cross_block_problems(built) + started
    checked = {blk['block']: check_lines(blk, lines, arms, tuning, rl, not a.no_dry_run, a.workers, cache)
               for blk, lines, _ in built if lines}
    problems = cross + [p for _, ps in checked.values() for p in ps]
    if problems:
        print('CHECK FAILED\n  ' + '\n  '.join(problems[:40]), file=sys.stderr)
        return 1
    print('every line passes gpu_queue, the pins, the P4-P6 design (test routes of the block, kappa, seed, arm, '
          'envelope, network), the launcher (parse, configuration, preflight; kappa / seed aware)'
          + ('' if a.no_dry_run else ' and its --dry-run') + '; ids and output directories are unique across blocks')
    if a.write:
        try:
            info = write_all(built, checked, cross, a.jobs_dir, a.protocol, a.force)
        except (PermissionError, FileExistsError) as e:
            print(f'REFUSED: {e}', file=sys.stderr)
            return 2
        print(json.dumps(info, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
