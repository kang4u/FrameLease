"""CPU-only fixtures of the framelease_v4/rl tests: synthetic run directories, toy SMDP datasets, v3 timeline helpers.

    cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
        framelease_v4/rl/tests
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True                     # never write caches into the read-only v3 test directory

import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
from pathlib import Path  # noqa: E402

os.environ['CUDA_VISIBLE_DEVICES'] = ''

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
V3_TESTS = ROOT / 'framelease_v3' / 'runtime' / 'tests'
if str(V3_TESTS) not in sys.path:
    sys.path.append(str(V3_TESTS))                 # helpers_v3 (read-only import of the v3 fakes)

import numpy as np  # noqa: E402

from framelease_v4.rl import common as C  # noqa: E402
from framelease_v4.rl import dataset as D  # noqa: E402
from framelease_v4.rl import features as F  # noqa: E402

PILOT_AVAILABLE = C.PILOT_ROOT.is_dir() and any(C.PILOT_ROOT.glob('*/runs/*/raw/official_results.json'))


def write_routes_xml(path, route_id, keypoints, town='Town12'):
    pts = '\n'.join(f'            <position x="{x:.1f}" y="{y:.1f}" z="0.0" />' for x, y in keypoints)
    Path(path).write_text(f'<routes>\n   <route id="{route_id}" town="{town}">\n         <waypoints>\n{pts}\n'
                          f'         </waypoints>\n   </route>\n</routes>\n', encoding='utf-8')
    return Path(path)


def feature_row(**over):
    """A 32-feature dict like the v3 runtime logs (choice-state-like defaults)."""
    from framelease_v3.runtime.v3_scheduler import FEATURE_NAMES
    base = {n: 0.0 for n in FEATURE_NAMES}
    base.update({'lease_slack_s': 1.5, 'obs_age_s': 0.5, 'depth': 2, 'active_age_s': 0.6, 'active_depth': 1,
                 'active_lease_s': 2.0, 'cand_lease_s': 2.0, 'cand_slack_s': 1.5, 'refine_margin_s': 0.4,
                 'refresh_margin_s': 0.9, 'L_pi_s': 0.001, 'L_refine_s': 0.02, 'L_refresh_s': 0.47, 'L_commit_s': 0.001,
                 'ego_speed_mps': 5.0, 'n_relevant': 3, 'min_g_m': 2.0, 'tau_star_s': 2.6, 'newer_frames': 9,
                 'kappa': 1.0, 'plan_delta_m': 0.05})
    base.update(over)
    return base


def make_run_dir(tmp, route_id='99901', ds=50.0, rc=50.0, penalty=1.0, n_ticks=200, speed=5.0, decisions=None,
                 infractions=None, status='Failed - Agent got blocked', route_len=200.0, with_metric_info=True,
                 jobs=None, utility='heuristic'):
    """A synthetic closed-loop run directory with the layout the dataset builder reads.

    The ego moves along +x at `speed` from x = 0 on a straight route of route_len metres (keypoints every 2 m)."""
    tmp = Path(tmp)
    run = tmp / 'runs' / f'run_{route_id}'
    (run / 'raw' / 'agent' / 'framelease').mkdir(parents=True, exist_ok=True)
    xml = write_routes_xml(tmp / f'routes_{route_id}.xml', route_id,
                           [(x, 0.0) for x in np.arange(0.0, route_len + 1e-9, 2.0)])
    cfg = {'arm': 'synthetic', 'policy': 'fl_v3_heuristic', 'route': {'route_id': route_id, 'scenarios': ['Toy']},
           'seed': 11, 'kappa': 1.0, 'routes_sha256': C.sha256_file(xml),
           'v3': {'policy_params': {'utility': utility}}}
    (run / 'config.json').write_text(json.dumps(cfg))
    infr = {k: [] for k in ('collisions_layout', 'collisions_pedestrian', 'collisions_vehicle', 'red_light',
                            'stop_infraction', 'outside_route_lanes', 'min_speed_infractions',
                            'yield_emergency_vehicle_infractions', 'scenario_timeouts', 'route_dev',
                            'vehicle_blocked', 'route_timeout')}
    infr.update(infractions or {})
    rec = {'route_id': f'RouteScenario_{route_id}_rep0', 'status': status, 'infractions': infr,
           'scores': {'score_route': rc, 'score_penalty': penalty, 'score_composed': ds},
           'meta': {'route_length': route_len}}
    (run / 'raw' / 'official_results.json').write_text(json.dumps({'_checkpoint': {'records': [rec]}}))
    ticks, mi = [], {}
    for k in range(n_ticks):
        t = 0.05 * (k + 1)
        ticks.append({'tick': k, 'sim_s': t, 'mode': 'track'})
        mi[str(k)] = {'location': [speed * t, 0.0, 0.0]}
    with open(run / 'raw' / 'agent' / 'framelease' / 'ticks.jsonl', 'w') as f:
        for r in ticks:
            f.write(json.dumps(r) + '\n')
    if with_metric_info:
        (run / 'raw' / 'agent' / 'metric_info.json').write_text(json.dumps(mi))
    if decisions is not None:
        with open(run / 'raw' / 'agent' / 'framelease' / 'decisions.jsonl', 'w') as f:
            for r in decisions:
                f.write(json.dumps(r) + '\n')
    if jobs is not None:
        with open(run / 'raw' / 'agent' / 'framelease' / 'jobs.jsonl', 'w') as f:
            for r in jobs:
                f.write(json.dumps(r) + '\n')
    return run, xml


def decision_row(epoch, t, feasible, action, reason=None, **feat):
    feats = feature_row(**feat)
    return {'kind': 'decision', 'epoch': epoch, 'sim_s': t, 'feasible': list(feasible), 'action': action,
            'p_both': len(feasible) == 2, 'reason': reason or ('both_feasible:heuristic' if len(feasible) == 2 else
                                                               'only'), 'features': feats}


def toy_dataset(n_episodes=40, steps=12, eps=0.5, seed=0, signal='lease_slack_s', delayed=True, route_prefix='r',
                refresh_cost=0.2):
    """Toy choice-epoch SMDP with a known optimum.

    Each episode visits `steps` choice states; the binary context c = 1[signal feature > 0] (lease slack by default)
    is drawn per state. REFRESH in a c = 1 state costs refresh_cost at once and earns +1 DS that arrives
    (delayed=True) with the NEXT transition, whose state carries the pending credit in the 'plan_delta_m' column
    (Markov); REFRESH in a c = 0 state costs -1 at once; REFINE earns 0. Optimal: REFRESH iff c = 1. A one-step bandit
    on R sees only the immediate cost of its own REFRESH (the +1 arrives one step later) and keeps REFINE; 2+ FQI
    iterations see the credit. Behaviour: epsilon-random around REFINE (mu logged)."""
    rng = np.random.default_rng(seed)
    idx = F.NAMES.index(signal)
    pend = F.NAMES.index('plan_delta_m')
    arrays = {k: [] for k in ('X', 'XN', 'A', 'R', 'DONE', 'MU', 'BASE', 'T', 'DT', 'NF', 'G', 'FIRST', 'EP', 'X32',
                              'GW0.5', 'GW1', 'GW2', 'XE', 'XEN')}
    episodes = []
    for e in range(n_episodes):
        X = rng.uniform(0.0, 1.0, (steps, F.N_FEATURES))
        X[:, idx] = rng.choice([-1.0, 1.0], steps)
        X[:, pend] = 0.0
        X[:, F.NAMES.index('depth')] = rng.integers(1, 10, steps)          # choice states: depth 1..9
        A = np.where(rng.uniform(size=steps) < eps, rng.integers(0, 2, steps), 0).astype(np.int8)
        mu = np.where(A == 0, 1 - eps / 2, eps / 2)
        R = np.zeros(steps)
        for i in range(steps):
            c = X[i, idx] > 0
            R[i] += X[i, pend]                       # pending credit of the previous REFRESH
            if A[i] == 1 and not c:
                R[i] -= 1.0
            elif A[i] == 1 and c:
                R[i] -= refresh_cost
                if delayed and i + 1 < steps:
                    X[i + 1, pend] = 1.0
                else:
                    R[i] += 1.0
        ds_e = float(R.sum())
        G = np.cumsum(R[::-1])[::-1]
        XN = np.vstack([X[1:], np.zeros((1, F.N_FEATURES))])
        done = np.zeros(steps, bool)
        done[-1] = True
        first = np.zeros(steps, bool)
        first[0] = True
        T = np.arange(steps) * 0.1
        XE = np.stack([np.cumsum(R) - R, np.ones(steps), T], 1)              # (S so far, penalty, time)
        XEN = np.vstack([XE[1:], np.zeros((1, 3))])
        for k, v in (('XE', XE), ('XEN', XEN), ('X', X), ('XN', XN), ('A', A), ('R', R), ('DONE', done), ('MU', mu),
                     ('BASE', np.zeros(steps, np.int8)), ('T', np.arange(steps) * 0.1), ('DT', np.full(steps, 0.1)),
                     ('NF', np.zeros(steps, np.int32)), ('G', G), ('FIRST', first), ('EP', np.full(steps, e, np.int32)),
                     ('X32', np.full((steps, 32), np.nan)), ('GW0.5', R), ('GW1', R), ('GW2', R)):
            arrays[k].append(v)
        episodes.append({'route_id': f'{route_prefix}{e % 10}', 'split': 'train', 'n_choice': steps, 'ds': ds_e,
                         'pre_choice_return': 0.0, 'run_id': f'toy{e}'})
    arrays = {k: np.concatenate(v) for k, v in arrays.items()}
    return D.Dataset(arrays, episodes, {'schema': 'toy'})


def toy_policy_value(policy, n_episodes=400, steps=12, seed=99, signal='lease_slack_s', refresh_cost=0.2):
    """Monte Carlo value (mean episode return) of a deterministic policy on the toy SMDP of toy_dataset."""
    rng = np.random.default_rng(seed)
    idx = F.NAMES.index(signal)
    pend = F.NAMES.index('plan_delta_m')
    total = 0.0
    for _ in range(n_episodes):
        X = rng.uniform(0.0, 1.0, (steps, F.N_FEATURES))
        X[:, idx] = rng.choice([-1.0, 1.0], steps)
        X[:, pend] = 0.0
        X[:, F.NAMES.index('depth')] = rng.integers(1, 10, steps)
        for i in range(steps):
            a = int(policy(X[i:i + 1])[0])
            total += X[i, pend]
            c = X[i, idx] > 0
            if a == 1 and not c:
                total -= 1.0
            elif a == 1 and c:
                total -= refresh_cost
                if i + 1 < steps:
                    X[i + 1, pend] = 1.0
    return total / n_episodes


def optimal_actions(X, signal='lease_slack_s'):
    return (X[:, F.NAMES.index(signal)] > 0).astype(np.int8)


__all__ = ['ROOT', 'PILOT_AVAILABLE', 'write_routes_xml', 'feature_row', 'make_run_dir', 'decision_row',
           'toy_dataset', 'optimal_actions']
