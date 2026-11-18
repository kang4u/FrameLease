#!/usr/bin/env python3
"""CPU microbenchmark of the Q-network utility (outline Sec. IV-B, "CPU Q-Network inference: P50, P99").

  cd /home/kang/Desktop/DAC && OMP_NUM_THREADS=1 .conda-unidrive-linux/bin/python -I -B framelease_v4/rl/bench_qnet.py \
      [--model QNET.json] [--n 20000] [--out outputs/framelease_v4/rl_dev/bench]

Inputs: the exported model (default: a random-weight model of the deployed shape 16-32-32-2) and REAL choice-state
feature dicts (|A_feas| = 2 decision rows of the fast-prefix pilot's v3 runs; cycled). Per call, time.perf_counter_ns:
  forward           network only, on a prepared feature vector
  featurize+forward q_from_features on a logged features dict (16 lookups, missing values, clipping)
  select            QUtility.select (budget checks, timed call, decision, logging into the dict)
  decide_q          framelease_v3.runtime.v3_shield.decide(shield result, QUtility, features): Eq. 8 end to end
  decide_heuristic  the same with the v3 heuristic utility (reference)
  decide_bypass     the same with QUtility when the slack check bypasses the network
Single thread (BLAS / OpenMP threads pinned to 1 before numpy is imported); other projects may load the CPU, so the
load average is recorded. CPU only; nothing else is started.
"""
from __future__ import annotations

import os

for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ.setdefault(_v, '1')
os.environ['CUDA_VISIBLE_DEVICES'] = ''

import argparse  # noqa: E402
import json  # noqa: E402
import platform  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from framelease_v4.rl import common as C  # noqa: E402
from framelease_v4.rl import features as F  # noqa: E402
from framelease_v4.rl import qnet as Q  # noqa: E402
from framelease_v4.rl import trainers as TR  # noqa: E402


def random_model(seed=0, hidden=(32, 32)):
    rng = np.random.default_rng(seed)
    sizes = [F.N_FEATURES, *hidden, 2]
    Ws = [rng.normal(0, np.sqrt(2.0 / i), (i, o)) for i, o in zip(sizes[:-1], sizes[1:])]
    bs = [np.zeros(o) for o in sizes[1:]]
    spec = TR.export_qnet({'W': Ws, 'b': bs}, TR.Candidate('fqi'), [True, True],
                          provenance={'note': 'random weights of the deployed shape (benchmark only)'})
    return json.loads(json.dumps(spec))


def choice_feature_dicts(root=C.PILOT_ROOT, limit=5000):
    out = []
    for p in sorted(Path(root).glob('*/runs/*/raw/agent/framelease/decisions.jsonl')):
        for r in C.read_jsonl(p):
            if r.get('p_both'):
                out.append((r['features'], r['shield']))
            if len(out) >= limit:
                return out
    return out


def cpu_model():
    try:
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.startswith('model name'):
                return line.split(':', 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def stats_us(ns):
    a = np.asarray(ns, dtype=np.float64) / 1e3
    return {'n': int(a.size), 'p50_us': float(np.percentile(a, 50)), 'p90_us': float(np.percentile(a, 90)),
            'p99_us': float(np.percentile(a, 99)), 'p999_us': float(np.percentile(a, 99.9)),
            'max_us': float(a.max()), 'mean_us': float(a.mean())}


def run(spec, rows, n=20000, warm=2000):
    from framelease_v3.runtime import v3_shield as VS
    util = Q.QUtility(spec, log_to_features=True)
    net = util.net
    k = len(rows)
    feats = [dict(rows[i % k][0]) for i in range(n + warm)]
    xs = [F.vector(f, tuple(spec['feature_columns'])) for f in feats[:k]]
    pc = time.perf_counter_ns
    res = {}

    def loop(fn, name):
        for i in range(warm):
            fn(i)
        out = []
        for i in range(warm, warm + n):
            t0 = pc()
            fn(i)
            out.append(pc() - t0)
        res[name] = stats_us(out)

    loop(lambda i: net.forward(xs[i % k]), 'forward')
    loop(lambda i: net.q_from_features(feats[i]), 'featurize_forward')
    sel_feats = [dict(f) for f in feats]
    loop(lambda i: util.select(sel_feats[i], (VS.REFINE, VS.REFRESH)), 'select')
    b = VS.ShieldBounds(L_pi=0.001, L_refine=0.02, L_refresh=0.47, L_commit=0.001, eps=0.05)
    sr = VS.shield(10.0, 12.5, 12.5, 3, 10, True, b)
    assert sr.both
    dq = [dict(f) for f in feats]
    loop(lambda i: VS.decide(sr, util, dq[i]), 'decide_q')
    heur = VS.HeuristicUtility()
    dh = [dict(f) for f in feats]
    loop(lambda i: VS.decide(sr, heur, dh[i]), 'decide_heuristic')
    byp = Q.QUtility(spec, budget_s=1e6)                     # every margin < budget: the slack check bypasses
    db = [dict(f) for f in feats]
    loop(lambda i: VS.decide(sr, byp, db[i]), 'decide_bypass')
    res['utility_stats'] = util.stats()
    res['bypass_stats'] = byp.stats()
    return res


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--model', type=Path, default=None)
    p.add_argument('--n', type=int, default=20000)
    p.add_argument('--warm', type=int, default=2000)
    p.add_argument('--out', type=Path, default=C.OUT_ROOT / 'bench')
    args = p.parse_args(argv)
    spec = Q.load_spec(args.model) if args.model else random_model()
    rows = choice_feature_dicts()
    if not rows:
        raise SystemExit('no pilot choice-state rows found')
    load0 = os.getloadavg()
    t0 = time.time()
    res = run(spec, rows, args.n, args.warm)
    out = {'schema': 'framelease_v4.qnet_bench/1', 'utc': C.utc_stamp(), 'model': str(args.model) if args.model else
           'random weights (deployed shape)', 'model_name': spec['name'],
           'layers': [[len(L['W']), len(L['W'][0])] for L in spec['layers']], 'n_feature_dicts': len(rows),
           'results': res, 'loadavg_start': load0, 'loadavg_end': os.getloadavg(), 'wall_s': time.time() - t0,
           'threads': {v: os.environ.get(v) for v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')},
           'python': platform.python_version(), 'numpy': np.__version__, 'cpu': cpu_model(), 'nproc': os.cpu_count(), 'code_sha256': C.code_hashes(['qnet.py', 'features.py',
                                                                                         'bench_qnet.py'])}
    path = C.atomic_json(args.out / f'qnet_bench_{out["utc"]}.json', out)
    print(json.dumps({k: res[k] for k in res if not k.endswith('stats')}, indent=1))
    print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
