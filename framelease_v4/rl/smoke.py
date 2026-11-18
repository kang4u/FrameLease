#!/usr/bin/env python3
"""Smoke run of the v4 RL pipeline on the 12 fast-prefix pilot runs (CPU only; exercises the code, no claims).

  cd /home/kang/Desktop/DAC && OMP_NUM_THREADS=1 .conda-unidrive-linux/bin/python -I -B framelease_v4/rl/smoke.py \
      [--out outputs/framelease_v4/rl_dev/smoke_20261110] [--fresh]

Stages (each recorded in <out>/progress.jsonl; a rerun skips finished stages whose outputs exist):
  dataset           12 pilot runs -> dataset/ (4 v3 episodes with decisions, 8 v2-policy episodes for the reward
                    identity only);
                    reward_proof.json / reward_proof.md: pre + sum r_n = official DS per run, reconstruction checks
  behaviour_replay  the pilot's logged decision rows replayed through v3_shield.decide with the registered
                    epsilon-random behaviour utility (eps 0.3): A_feas never left, propensities, call counts
  select_<family>   route-grouped (leave-one-route-out) cross-fitted FQE selection on the smoke grid
  final_<family>    selected candidate refit on all training episodes, distilled to the MLP, exported
  qnet_replay       every exported Q-network registered by name and replayed through v3_shield.decide
  bench             CPU microbenchmark of the exported FQI Q-network (P50 / P99)
  summary           smoke_summary.json, SUMMARY.md
The pilot used the deterministic v3 heuristic (a_det^10: REFINE at every choice state), so REFRESH has no support at
choice states: every learned policy must reduce to a_det there, and OPE differences must be exactly 0. That is the
expected outcome; the learning code paths with exploration data are covered by the unit tests (toy SMDPs).
"""
from __future__ import annotations

import os

for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '1')
os.environ['CUDA_VISIBLE_DEVICES'] = ''

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from framelease_v4.rl import behaviour as B  # noqa: E402
from framelease_v4.rl import common as C  # noqa: E402
from framelease_v4.rl import dataset as D  # noqa: E402
from framelease_v4.rl import ope as O  # noqa: E402
from framelease_v4.rl import qnet as Q  # noqa: E402
from framelease_v4.rl import trainers as TR  # noqa: E402

DEFAULT_OUT = C.OUT_ROOT / 'smoke_20261110'
SMOKE_FQE = O.FQEConfig(n_estimators=20, min_samples_leaf=5, min_support=5, iter_cap=300)


def stage_dataset(out):
    runs = D.discover_runs([C.PILOT_ROOT])
    ds, eps_ = D.build_dataset(runs, out_dir=out / 'dataset')
    rows = []
    for m in ds.episodes:
        p, g = m['proof'], m['reconstruction']
        rows.append({'arm': m['arm'], 'route_id': m['route_id'], 'run_id': m['run_id'], 'status': m['status'],
                     'epoch_source': p['epoch_source'], 'n_epochs': p['n_epochs'], 'n_choice': p['n_choice'],
                     'ds_official': p['ds_official'], 'pre_epoch_return': p['pre_epoch_return'],
                     'sum_r': p['sum_r_epochs'], 'pre_plus_sum_r': p['pre_plus_sum_r'],
                     'abs_err': p['abs_err_epochs'], 'abs_err_choice_smdp': p['abs_err_choice'],
                     'identity_ok': p['identity_ok'], 'rc_official': g['rc_official'], 'rc_hat_end': g['rc_hat_end'],
                     'rc_abs_err_unanchored': g['rc_abs_err_unanchored'], 'penalty_official': g['penalty_official'],
                     'penalty_parsed': g['penalty_parsed'], 'penalty_check_ok': g['penalty_check_ok'],
                     'located_events': g['located_events'], 'terminal_events': g['terminal_events'],
                     'max_match_dist_m': g['max_match_dist_m'], 'reward_mode': p['reward_mode'],
                     'routes_xml_sha256_match': g['routes_xml_sha256_match']})
    proof = {'schema': 'framelease_v4.reward_proof/1', 'n_runs': len(rows),
             'all_identity_ok': all(r['identity_ok'] for r in rows),
             'all_penalty_ok': all(r['penalty_check_ok'] for r in rows),
             'max_abs_err': max(r['abs_err'] for r in rows), 'max_abs_err_smdp': max(r['abs_err_choice_smdp'] for r in rows),
             'rc_unanchored_abs_err': {'max': max(r['rc_abs_err_unanchored'] for r in rows),
                                       'median': float(np.median([r['rc_abs_err_unanchored'] for r in rows]))},
             'definition': 'S(t) = RC(t) x P(t); r_n = S(t_{n+1}) - S(t_n); r_N = DS - S(t_N); check |S(t_1) + fsum(r) '
                           '- DS| <= 1e-9 per run (all decision epochs, and the choice-epoch SMDP)',
             'runs': rows}
    C.atomic_json(out / 'reward_proof.json', proof)
    L = ['# Reward identity on the 12 fast-prefix pilot runs', '',
         'S(t) = route completion so far x infraction penalty so far (framelease_v4/rl/prefix_score.py); '
         'r_n = S(t_{n+1}) - S(t_n) over the decision epochs, last r = DS - S(t_N). Check: pre + sum r_n = official DS.',
         '', '| arm | route | status | epochs (choice) | official DS | pre + sum r | abs err | SMDP abs err | RC hat / '
         'official | penalty parsed / official |', '|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        L.append(f"| {r['arm']} | {r['route_id']} | {r['status']} | {r['n_epochs']} ({r['n_choice']}) | "
                 f"{r['ds_official']:.6f} | {r['pre_plus_sum_r']:.6f} | {r['abs_err']:.1e} | "
                 f"{r['abs_err_choice_smdp']:.1e} | {r['rc_hat_end']:.2f} / {r['rc_official']:.2f} | "
                 f"{r['penalty_parsed']:.6f} / {r['penalty_official']:.6f} |")
    L += ['', f"All identities hold: {proof['all_identity_ok']} (max abs err {proof['max_abs_err']:.2e}); penalty model "
          f"reproduces the official penalty on every run: {proof['all_penalty_ok']}. Unanchored route-completion "
          f"reconstruction error: median {proof['rc_unanchored_abs_err']['median']:.2f}, max "
          f"{proof['rc_unanchored_abs_err']['max']:.2f} points (anchored to the official value at the end).", '']
    C.atomic_write_text(out / 'reward_proof.md', '\n'.join(L))
    return {'n_transitions': ds.n, 'all_identity_ok': proof['all_identity_ok'], 'max_abs_err': proof['max_abs_err']}


def _pilot_rows():
    out = []
    for p in sorted(C.PILOT_ROOT.glob('*/runs/*/raw/agent/framelease/decisions.jsonl')):
        out.append((p, C.read_jsonl(p)))
    return out


def _shield_result(row):
    from framelease_v3.runtime import v3_shield as VS
    s = row['shield']
    return VS.ShieldResult(s['t'], s['D_star'] if s['D_star'] is not None else -math.inf,
                           s['D_cand'] if s['D_cand'] is not None else -math.inf, s['depth'], s['newer_frame'],
                           s['refine_ok'], s['refresh_ok'], s['refine_lhs'], s['refresh_lhs'], s['refine_cand_lhs'],
                           s['refine_why'], s['refresh_why'])


def replay(utility_name, rows_by_run):
    """Replay logged decision rows through v3_shield.decide with a registered utility (fresh instance per run)."""
    from framelease_v3.runtime import v3_shield as VS
    B.register_utility_name(utility_name)
    out = {'utility': utility_name, 'runs': []}
    for path, rows in rows_by_run:
        u = VS.make_utility(utility_name)
        n_choice = n_left = 0
        acts = {'REFINE': 0, 'REFRESH': 0}
        mus = []
        for r in rows:
            sr = _shield_result(r)
            assert tuple(sr.feasible) == tuple(r['feasible']), 'shield replay mismatch'
            feats = dict(r['features'])
            a, reason = VS.decide(sr, u, feats)
            if sr.both:
                n_choice += 1
                acts[a] += 1
                if 'v4_mu' in feats:
                    mus.append(feats['v4_mu'])
            if sr.feasible and a not in sr.feasible:
                n_left += 1
        st = u.stats() if hasattr(u, 'stats') else {}
        out['runs'].append({'decisions': str(path), 'rows': len(rows), 'choice_rows': n_choice,
                            'left_feasible_set': n_left, 'actions_at_choice': acts,
                            'mu_values': sorted(set(round(m, 6) for m in mus)), 'utility_stats': st})
    return out


def stage_behaviour(out):
    name = B.behaviour_name(0.3, 20261110)
    rep = replay(name, _pilot_rows())
    tot = sum(r['choice_rows'] for r in rep['runs'])
    ref = sum(r['actions_at_choice']['REFRESH'] for r in rep['runs'])
    rep['summary'] = {'choice_rows': tot, 'refresh_share': ref / tot if tot else None, 'expected_refresh_share': 0.15,
                      'left_feasible_set': sum(r['left_feasible_set'] for r in rep['runs']),
                      'select_calls_equal_choice_rows': all(r['utility_stats'].get('draws') == r['choice_rows']
                                                            for r in rep['runs'])}
    C.atomic_json(out / 'behaviour_replay.json', rep)
    return rep['summary']


def stage_select(out, family, ds, n_jobs):
    rep = O.select(ds, TR.grid(family, smoke=True), ds.train_episode_ids(), n_folds=4, fqe_cfg=SMOKE_FQE,
                   n_jobs=n_jobs, n_boot=500)
    C.atomic_json(out / f'select_{family}.json', rep)
    return {'selected': rep['selected'], 'candidates': [{'label': r['label'], 'mean_delta': r['mean_delta'],
                                                         'bootstrap': r['bootstrap']} for r in rep['candidates']]}


def stage_final(out, family, ds):
    rep = C.read_json(out / f'select_{family}.json')
    cand = next(TR.Candidate(**r['candidate']) for r in rep['candidates'] if r['label'] == rep['selected'])
    ids = ds.train_episode_ids()
    q, info = TR.fit_candidate(ds, ids, cand)
    m = ds.episode_mask(ids)
    states = np.concatenate([ds.X[m], ds.XN[m & ~ds.DONE]])
    mlp, fid = TR.distill(q, cand, states, epochs=200)
    spec = TR.export_qnet(mlp, cand, q.supported, provenance={
        'dataset': str(out / 'dataset'), 'dataset_manifest_sha256': C.sha256_file(out / 'dataset' / 'manifest.json'),
        'train_episodes': ids, 'train_routes': sorted({ds.episodes[i]['route_id'] for i in ids}),
        'selection': f'select_{family}.json', 'fit_info': {k: v for k, v in info.items() if k != 'iterations'},
        'distillation': fid, 'smoke': True})
    path = C.atomic_json(out / f'qnet_{family}.json', spec)
    Q.load_spec(path)
    return {'model': str(path), 'name': spec['name'], 'candidate': cand.label, 'supported': q.supported,
            'distillation_agreement': fid['final']['agreement'], 'train_deviation_rate': info.get('train_deviation_rate')}


def stage_qnet_replay(out):
    res = {}
    rows = _pilot_rows()
    for family in TR.FAMILIES:
        path = out / f'qnet_{family}.json'
        spec = Q.load_spec(path)
        os.environ[Q.ENV_QNET] = str(path)
        rep = replay(spec['name'], rows)
        res[family] = {'name': spec['name'], 'left_feasible_set': sum(r['left_feasible_set'] for r in rep['runs']),
                       'choice_rows': sum(r['choice_rows'] for r in rep['runs']),
                       'network_calls': sum(r['utility_stats']['network_calls'] for r in rep['runs']),
                       'select_calls': sum(r['utility_stats']['select_calls'] for r in rep['runs']),
                       'actions_at_choice': {a: sum(r['actions_at_choice'][a] for r in rep['runs'])
                                             for a in ('REFINE', 'REFRESH')},
                       'bypass': {k: sum(r['utility_stats']['bypass'][k] for r in rep['runs'])
                                  for k in ('slack', 'disabled', 'overrun', 'nonfinite')}}
    os.environ.pop(Q.ENV_QNET, None)
    C.atomic_json(out / 'qnet_replay.json', res)
    return res


def stage_bench(out):
    from framelease_v4.rl import bench_qnet as BQ
    spec = Q.load_spec(out / 'qnet_fqi.json')
    rows = BQ.choice_feature_dicts()
    res = BQ.run(spec, rows, n=20000, warm=2000)
    doc = {'schema': 'framelease_v4.qnet_bench/1', 'utc': C.utc_stamp(), 'model': str(out / 'qnet_fqi.json'),
           'model_name': spec['name'], 'results': res, 'loadavg': os.getloadavg(), 'cpu': BQ.cpu_model(),
           'nproc': os.cpu_count(), 'n_feature_dicts': len(rows),
           'threads': {v: os.environ.get(v) for v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')}}
    C.atomic_json(out / 'bench_qnet.json', doc)
    return {k: {'p50_us': v['p50_us'], 'p99_us': v['p99_us']} for k, v in res.items() if 'p50_us' in v}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--out', type=Path, default=DEFAULT_OUT)
    p.add_argument('--fresh', action='store_true', help='delete the output directory first')
    p.add_argument('--n-jobs', type=int, default=1)
    args = p.parse_args(argv)
    out = args.out.resolve()
    C._check_writable(out)
    if args.fresh and out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    prog = C.Progress(out)
    done = prog.done()
    summary = {k: v.get('result') for k, v in done.items()}
    t_start = time.time()

    def run_stage(name, fn, outputs=()):
        if name in done and all((out / o).exists() for o in outputs):
            print(f'[skip] {name}', flush=True)
            return done[name].get('result')
        t0 = time.time()
        prog.mark(name, status='started')
        res = fn()
        prog.mark(name, status='done', seconds=round(time.time() - t0, 2), result=res)
        summary[name] = res
        print(f'[done] {name} ({time.time() - t0:.1f} s): {json.dumps(C.jsonable(res))[:400]}', flush=True)
        return res

    run_stage('dataset', lambda: stage_dataset(out), ('dataset/transitions.npz', 'reward_proof.json'))
    ds = D.load_dataset(out / 'dataset')
    run_stage('behaviour_replay', lambda: stage_behaviour(out), ('behaviour_replay.json',))
    for fam in TR.FAMILIES:
        run_stage(f'select_{fam}', lambda f=fam: stage_select(out, f, ds, args.n_jobs), (f'select_{fam}.json',))
    for fam in TR.FAMILIES:
        run_stage(f'final_{fam}', lambda f=fam: stage_final(out, f, ds), (f'qnet_{fam}.json',))
    run_stage('qnet_replay', lambda: stage_qnet_replay(out), ('qnet_replay.json',))
    run_stage('bench', lambda: stage_bench(out), ('bench_qnet.json',))

    def finish():
        doc = {'schema': 'framelease_v4.rl_smoke/1', 'utc': C.utc_stamp(), 'out': str(out), 'stages': summary,
               'code_sha256': C.code_hashes(), 'note': 'smoke run on the heuristic pilot (no exploration data): '
               'exercises the code only; REFRESH is unsupported at choice states, so all learned policies equal a_det'}
        C.atomic_json(out / 'smoke_summary.json', doc)
        return {'wall_s': round(time.time() - t_start, 1)}
    run_stage('summary', finish, ('smoke_summary.json',))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
