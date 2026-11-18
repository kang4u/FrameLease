#!/usr/bin/env python3
"""Behaviour-data collection plan on TRAINING routes (a JSON plan only: nothing is enqueued or launched).

  cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B framelease_v4/rl/collection_plan.py \
      [--variant FULL|TRIMMED] [--eps 0.3] [--d-det D*] [--envelope outputs/framelease_v4/envelopes/<L*>.json] \
      [--out outputs/framelease_v4/rl_dev/collection_plan]

Runs (PROTOCOL Sec. 5.3 and Sec. 14):
  FULL     the 44 training routes (the second-lowest route id of each scenario type; PROTOCOL Sec. 3.2) x kappa
           {1.0, 1.5, 2.0} x seed 11, one behaviour seed each (rep 0): 132 runs;
  TRIMMED  the 22 training routes outside T22 (training index % 2 == 1) x 2 behaviour seeds: rep 0 at kappa 1.0 on
           all 22; rep 1 at kappa 1.5 on the routes at even positions of the id-sorted 22 and at kappa 2.0 on the
           others: 44 runs (22 at kappa 1.0, 11 at 1.5, 11 at 2.0, so the Q-network's kappa feature varies).
The pool is cross-checked against outputs/framelease_v4/protocol/route_split.json when it exists (read only).

The behaviour seed rule (one rule for every behaviour run, PROTOCOL Sec. 2.6):
    seed = int(sha256('framelease_v4_behaviour|20261110|<route>|<kappa:.2f>|<rep>')[:16], 16) mod 2^62
so exploration draws are independent across runs; the utility name is v4_eps<eps>_seed<seed>[_d<d*>] (behaviour
around a_det^{d*}; behaviour.py). Every run is the v4 arm fl_behaviour (V4Runtime, like every other arm, PROTOCOL
Sec. 2.3) through framelease_v4/arms/run_closed_loop_v4.py with an explicit --fast-prefix, --envelope (the selected
lease point L*; until the tuning freeze fixes it the plan says so), --timeout-s 1410, --lock-wait-s 600, CARLA port
2600 + 10 (i mod 4) for run i, and the output directory outputs/framelease_v4/rl_data/k<kappa>/ (PROTOCOL Sec. 8.6).
Turning the plan into gpu_queue job lines (with sha256 pins and the launcher's --dry-run) is a later step (P2).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v4.rl import behaviour as B  # noqa: E402
from framelease_v4.rl import common as C  # noqa: E402

BASE_SEED = 20261110
ROUTE_SPLIT = C.ROOT / 'outputs' / 'framelease_v4' / 'protocol' / 'route_split.json'
LAUNCHER = 'framelease_v4/arms/run_closed_loop_v4.py'
ARM = 'fl_behaviour'
FAST_PREFIX = 'sdpa,gpu_preproc,lora_merged'
ROUTES_XML = 'third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/data/bench2drive220.xml'
OUTPUT_ROOT = 'outputs/framelease_v4/rl_data'
TIMEOUT_S, LOCK_WAIT_S = 1410, 600
PORT_BASE, PORT_STEP, PORT_CYCLE = 2600, 10, 4
VARIANTS = ('FULL', 'TRIMMED')


def behaviour_seed(route_id, kappa, rep=0, base_seed=BASE_SEED):
    h = hashlib.sha256(f'framelease_v4_behaviour|{base_seed}|{route_id}|{float(kappa):.2f}|{rep}'.encode()).hexdigest()
    return int(h[:16], 16) % (2 ** 62)


def training_routes(per_type=1):
    """Per scenario type, the `per_type` lowest NON-test route ids (per_type 1 = the protocol's training pool)."""
    d = C.read_json(C.TEST_ROUTES_JSON)
    test = C.test_route_ids()
    out = []
    for r in d['routes']:
        pool = sorted((x for x in r['routes_of_type'] if x not in test), key=int)
        for rid in pool[:int(per_type)]:
            out.append({'route_id': rid, 'scenario_type': r['scenario_type'], 'town': r.get('town')})
    return out


def cross_check(routes):
    if not ROUTE_SPLIT.is_file():
        return {'route_split': None, 'match': None}
    split = C.read_json(ROUTE_SPLIT)
    want = sorted(str(r['route_id']) for r in split.get('training', []))
    have = sorted(r['route_id'] for r in routes)
    return {'route_split': str(ROUTE_SPLIT), 'route_split_sha256': C.sha256_file(ROUTE_SPLIT), 'match': want == have}


def schedule(variant, routes, kappas, reps):
    """[(route row, kappa, rep)] of a plan variant (routes: the id-sorted training pool)."""
    routes = sorted(routes, key=lambda r: int(r['route_id']))
    if variant == 'FULL':
        return [(r, float(k), rep) for rep in range(int(reps)) for k in kappas for r in routes]
    if variant == 'TRIMMED':
        outside = [r for i, r in enumerate(routes) if i % 2 == 1]          # training index % 2 == 1: not in T22
        out = [(r, 1.0, 0) for r in outside]
        out += [(r, 1.5 if pos % 2 == 0 else 2.0, 1) for pos, r in enumerate(outside)]
        return out
    raise ValueError(f'unknown variant {variant!r}')


def plan(eps=0.3, kappas=(1.0, 1.5, 2.0), d_det=10, envelope=None, per_type=1, reps=1, seed=11, variant='FULL',
         output_root=OUTPUT_ROOT):
    routes = training_routes(per_type)
    test = C.test_route_ids()
    runs = []
    for r, kappa, rep in schedule(variant, routes, kappas, reps):
        if r['route_id'] in test:
            raise AssertionError('test route in the collection plan')
        s = behaviour_seed(r['route_id'], kappa, rep)
        name = B.behaviour_name(eps, s, d_det)
        port = PORT_BASE + PORT_STEP * (len(runs) % PORT_CYCLE)
        argv = [LAUNCHER, '--arm', ARM, '--fast-prefix', FAST_PREFIX, '--kappa', f'{float(kappa):.1f}',
                '--seed', str(seed), '--routes', ROUTES_XML, '--route-id', r['route_id'], '--port', str(port),
                '--output-dir', f'{output_root}/k{float(kappa):.1f}', '--timeout-s', str(TIMEOUT_S),
                '--lock-wait-s', str(LOCK_WAIT_S), '--policy-params', json.dumps({'utility': name})]
        if envelope:
            argv += ['--envelope', str(envelope)]
        runs.append({**r, 'kappa': float(kappa), 'rep': rep, 'behaviour_seed': s, 'utility': name, 'argv': argv})
    kap = sorted({x['kappa'] for x in runs})
    return {'schema': 'framelease_v4.collection_plan/3', 'variant': variant, 'eps': eps, 'kappas': kap,
            'a_det_depth': int(d_det), 'envelope': str(envelope) if envelope else
            'NOT FIXED: pass the selected lease point L* (outputs/framelease_v4/tuning/selection.json)',
            'per_type': per_type, 'reps': (int(reps) if variant == 'FULL' else 2), 'n_runs': len(runs),
            'n_routes': len({r['route_id'] for r in runs}), 'n_types': len({r['scenario_type'] for r in runs}),
            'runs_per_kappa': {f'{k:.1f}': sum(1 for x in runs if x['kappa'] == k) for k in kap},
            'test_routes_excluded': len(test), 'training_pool_check': cross_check(routes),
            'expected_deviation_share_at_choice_states': eps / 2,
            'seed_rule': "int(sha256('framelease_v4_behaviour|20261110|<route>|<kappa:.2f>|<rep>')[:16], 16) mod 2^62",
            'launcher': LAUNCHER, 'arm': ARM, 'status': 'PLAN ONLY: not enqueued, not launched', 'runs': runs}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--variant', choices=VARIANTS, default='FULL')
    p.add_argument('--eps', type=float, default=0.3)
    p.add_argument('--kappas', default='1.0,1.5,2.0', help='FULL only')
    p.add_argument('--d-det', type=int, default=10, help='depth of the base heuristic a_det^{d*}')
    p.add_argument('--envelope', type=Path, default=None, help='selected lease point L* (v3 envelope JSON)')
    p.add_argument('--per-type', type=int, default=1)
    p.add_argument('--reps', type=int, default=1, help='FULL only')
    p.add_argument('--out', type=Path, default=C.OUT_ROOT / 'collection_plan')
    args = p.parse_args(argv)
    kappas = tuple(float(k) for k in args.kappas.split(','))
    doc = plan(args.eps, kappas, args.d_det, args.envelope, args.per_type, args.reps, variant=args.variant)
    kap = '-'.join(f'{k:.1f}' for k in doc['kappas'])
    name = (f'plan_eps{args.eps:.3f}_d{args.d_det}_k{kap}_per{args.per_type}.json' if args.variant == 'FULL' else
            f'plan_trimmed_eps{args.eps:.3f}_d{args.d_det}.json')
    path = C.atomic_json(args.out / name, doc)
    print(path, doc['n_runs'], 'runs on', doc['n_routes'], 'training routes of', doc['n_types'], 'types; pool check',
          doc['training_pool_check']['match'], doc['runs_per_kappa'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
