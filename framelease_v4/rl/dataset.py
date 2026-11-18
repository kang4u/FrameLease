"""Offline-RL dataset from closed-loop run directories (v3 runtime / fast-prefix / v4 launchers; v2 runs for the
reward identity only).

Per run (episode):
  * decision epochs: v3-runtime runs log one row per refinement-quantum boundary in
    raw/agent/framelease/decisions.jsonl (epoch, sim_s, A_feas, action, reason, 32 features; the v4 behaviour
    utility adds v4_mu etc. to the features). v2-policy runs (no shield) have no decision rows; their epochs are the
    per-step decision boundaries of raw/agent/framelease/jobs.jsonl (REFINE = continue, REFRESH = end of job), used
    only to check the reward identity, never for training (no features, no choice).
  * per-tick logs: raw/agent/framelease/ticks.jsonl (sim_s, tick) + raw/agent/metric_info.json (hero location;
    evaluation-only), which prefix_score turns into S(t) = RC(t) x P(t) with S(T) = official DS.
  * rewards (outline Eq. 7): r_n = S(t_{n+1}) - S(t_n) over the epochs, r_N = DS - S(t_N) at the last epoch, plus the
    pre-epoch return S(t_1) (0 in practice: nothing moves before the first plan). pre + sum r_n = DS.

OPE value-model covariates XE / XEN (route completion so far, penalty so far, elapsed time at the choice state /
next choice state) come from the evaluation-only hero state; they are never a policy input.

Learning data: the choice epochs (|A_feas| = 2, the only states where Eq. 8 consults the utility). All other epochs are
forced by the shield whatever the utility, so they belong to the environment: between consecutive choice epochs the
system is a semi-Markov transition with
    R_i = S(t_{c_{i+1}}) - S(t_{c_i})   (last: DS - S(t_{c_last}), done)
and the episode return is pre_choice + sum_i R_i = DS with pre_choice = S(t_{c_0}). Actions: 0 = REFINE, 1 = REFRESH.
Behaviour propensity of the logged action: v4_mu (epsilon-random behaviour), 1.0 for deterministic utilities
(v3 heuristic, v4 Q-network), NaN if unknown. Windowed gains S(t + W) - S(t) (W = 0.5 / 1 / 2 s) are stored for the
contextual-bandit targets.

Guard: runs on the 44 test routes are refused unless allow_test=True (then marked split 'test'; the trainers refuse
'test' episodes). Hyperparameters are tuned only on training routes.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from framelease_v4.rl import common as C
from framelease_v4.rl import features as F
from framelease_v4.rl import prefix_score as PS

SCHEMA = 'framelease_v4.rl_dataset/1'
REFINE, REFRESH = 0, 1
CODES = {'REFINE': 0, 'REFRESH': 1, 'RECOVERY_REFRESH': 2, 'WAIT': 3}
CODE_NAMES = {v: k for k, v in CODES.items()}
WINDOWS_S = (0.5, 1.0, 2.0)
# evaluation-only covariates of a choice state (OPE value model; never a policy input): route completion so far,
# infraction penalty so far (prefix_score; from the evaluation-only hero state), elapsed simulated time
EVAL_COVARIATES = ('rc_so_far', 'penalty_so_far', 'sim_s')
SUM_TOL = 1e-9


def discover_runs(roots):
    """Run directories under the given roots (config.json + raw/official_results.json + framelease/ticks.jsonl)."""
    out = []
    for root in roots:
        root = Path(root)
        cands = [root] if (root / 'config.json').is_file() else sorted(p.parent for p in root.rglob('config.json'))
        for d in cands:
            if (d / 'raw' / 'official_results.json').is_file() and \
                    (d / 'raw' / 'agent' / 'framelease' / 'ticks.jsonl').is_file():
                out.append(d.resolve())
    seen, uniq = set(), []
    for d in out:
        if d not in seen:
            seen.add(d)
            uniq.append(d)
    return uniq


def run_meta(run_dir):
    run_dir = Path(run_dir)
    cfg = C.read_json(run_dir / 'config.json')
    v3 = cfg.get('v3') or (cfg.get('v4') or {}).get('v3') or {}         # v3 launcher runs / v4 arms launcher runs
    utility = (v3.get('policy_params') or {}).get('utility', 'heuristic') if v3 else None
    rec = PS.official_record(run_dir)
    arm = cfg.get('arm') or (run_dir.parent.parent.name if run_dir.parent.name == 'runs' else None)
    return {'run_dir': str(run_dir), 'run_id': run_dir.name, 'arm': arm, 'policy': cfg.get('policy'),
            'route_id': str((cfg.get('route') or {}).get('route_id')),
            'scenario': ((cfg.get('route') or {}).get('scenarios') or [None])[0], 'seed': cfg.get('seed'),
            'kappa': cfg.get('kappa'), 'utility': utility, 'status': rec.get('status'),
            'ds': float(rec['scores']['score_composed']), 'rc': float(rec['scores']['score_route']),
            'penalty': float(rec['scores']['score_penalty'])}


def _propensity(row):
    """(mu of the logged action, base action code) of a choice epoch."""
    feats = row.get('features') or {}
    reason = str(row.get('reason', ''))
    if feats.get('v4_mu') is not None:
        base = CODES.get(str(feats.get('v4_base_action')), -1)
        return float(feats['v4_mu']), base
    util = reason.split(':', 1)[1] if reason.startswith('both_feasible:') else ''
    if util == 'heuristic' or util.startswith('v4_qnet_'):
        return 1.0, REFINE if util == 'heuristic' else -1
    return math.nan, -1


def load_epochs(run_dir):
    """('v3', rows) from decisions.jsonl, ('v2', rows) from jobs.jsonl step boundaries, or ('none', [])."""
    base = Path(run_dir) / 'raw' / 'agent' / 'framelease'
    dec = base / 'decisions.jsonl'
    if dec.is_file() and dec.stat().st_size > 0:
        rows = C.read_jsonl(dec)
        rows.sort(key=lambda r: (float(r['sim_s']), int(r['epoch'])))
        out = []
        for r in rows:
            feas = tuple(r.get('feasible') or ())
            choice = len(feas) == 2
            mu, b = _propensity(r) if choice else (1.0, CODES[r['action']])
            out.append({'t': float(r['sim_s']), 'code': CODES[r['action']], 'choice': choice,
                        'refine_ok': 'REFINE' in feas, 'refresh_ok': 'REFRESH' in feas, 'mu': mu, 'base': b,
                        'features': r.get('features') or {}, 'reason': r.get('reason'), 'epoch': int(r['epoch'])})
        return 'v3', out
    jobs = base / 'jobs.jsonl'
    if jobs.is_file() and jobs.stat().st_size > 0:
        out = []
        for j in C.read_jsonl(jobs):
            for s in j.get('steps') or []:
                d = s.get('decision')
                if isinstance(d, dict) and d.get('boundary_s') is not None:
                    out.append({'t': float(d['boundary_s']), 'code': REFINE if d.get('continue') else REFRESH,
                                'choice': False, 'refine_ok': None, 'refresh_ok': None, 'mu': 1.0, 'base': -1,
                                'features': None, 'reason': d.get('reason'), 'epoch': len(out) + 1})
        out.sort(key=lambda r: r['t'])
        return 'v2', out
    return 'none', []


@dataclass
class Episode:
    meta: dict
    kind: str
    epochs: list
    ps: PS.PrefixScore
    split: str
    proof: dict = field(default_factory=dict)


def build_episode(run_dir, test_routes, reward_mode='prefix', xml_path=None):
    meta = run_meta(run_dir)
    split = 'test' if meta['route_id'] in test_routes else 'train'
    kind, epochs = load_epochs(run_dir)
    ps = PS.reconstruct(run_dir, xml_path=xml_path, mode=reward_mode)
    T = ps.t_end
    epochs = [e for e in epochs if e['t'] <= T + 1e-9]          # boundaries after the last tick never act
    times = np.asarray([e['t'] for e in epochs], dtype=np.float64)
    pre, r = ps.rewards(times)
    total = pre + math.fsum(r.tolist())
    choice_idx = [i for i, e in enumerate(epochs) if e['choice']]
    ct = times[choice_idx] if choice_idx else np.zeros(0)
    pre_c, rc = ps.rewards(ct)
    total_c = pre_c + math.fsum(rc.tolist())
    proof = {'ds_official': ps.ds, 'n_epochs': len(epochs), 'pre_epoch_return': pre,
             'sum_r_epochs': math.fsum(r.tolist()), 'pre_plus_sum_r': total, 'abs_err_epochs': abs(total - ps.ds),
             'n_choice': len(choice_idx), 'pre_choice_return': pre_c, 'sum_R_choice': math.fsum(rc.tolist()),
             'abs_err_choice': abs(total_c - ps.ds),
             'identity_ok': bool(abs(total - ps.ds) <= SUM_TOL and abs(total_c - ps.ds) <= SUM_TOL),
             'p_both': (len(choice_idx) / len(epochs)) if epochs else None, 'epoch_source': kind,
             'reward_mode': ps.diagnostics.get('mode')}
    for e, ri in zip(epochs, r):
        e['r'] = float(ri)
    return Episode(meta, kind, epochs, ps, split, proof)


def smdp_arrays(ep, columns=F.ALL_COLUMNS):
    """Transitions over the choice epochs of one episode (dict of arrays; empty arrays if no choice epoch)."""
    ch = [e for e in ep.epochs if e['choice']]
    m = len(ch)
    d = len(columns)
    out = {'X': np.zeros((m, d)), 'XN': np.zeros((m, d)), 'A': np.zeros(m, np.int8), 'R': np.zeros(m),
           'DONE': np.zeros(m, bool), 'MU': np.full(m, np.nan), 'BASE': np.full(m, -1, np.int8),
           'T': np.zeros(m), 'DT': np.zeros(m), 'NF': np.zeros(m, np.int32), 'G': np.zeros(m),
           'FIRST': np.zeros(m, bool), 'X32': np.full((m, 32), np.nan), 'XE': np.zeros((m, len(EVAL_COVARIATES))),
           'XEN': np.zeros((m, len(EVAL_COVARIATES)))}
    for w in WINDOWS_S:
        out[f'GW{w:g}'] = np.zeros(m)
    if m == 0:
        return out, float(ep.ps.ds)            # no choice epoch: the whole return is policy-independent
    from framelease_v3.runtime.v3_scheduler import FEATURE_NAMES
    times = np.asarray([e['t'] for e in ch])
    pre, R = ep.ps.rewards(times)
    X = F.matrix([e['features'] for e in ch], columns)
    idx_all = [i for i, e in enumerate(ep.epochs) if e['choice']]
    for i, e in enumerate(ch):
        out['X'][i] = X[i]
        if i + 1 < m:
            out['XN'][i] = X[i + 1]
            out['DT'][i] = times[i + 1] - times[i]
            out['NF'][i] = idx_all[i + 1] - idx_all[i] - 1
        else:
            out['DONE'][i] = True
            out['DT'][i] = ep.ps.t_end - times[i]
            out['NF'][i] = len(ep.epochs) - idx_all[i] - 1
        if e['code'] not in (REFINE, REFRESH):
            raise ValueError(f'{ep.meta["run_dir"]}: choice epoch with action {CODE_NAMES[e["code"]]}')
        out['A'][i] = e['code']
        out['MU'][i] = e['mu']
        out['BASE'][i] = e['base']
        out['T'][i] = e['t']
        for k, name in enumerate(FEATURE_NAMES):
            v = e['features'].get(name)
            if v is not None and not isinstance(v, str):
                out['X32'][i, k] = float(v)
    out['R'][:] = R
    out['G'][:] = ep.ps.ds - ep.ps.at_many(times)                 # behaviour return-to-go (Monte Carlo)
    rc, pen = ep.ps.progress_at(times)
    out['XE'][:] = np.stack([rc, pen, times], axis=1)
    out['XEN'][:-1] = out['XE'][1:]                              # terminal rows keep zeros (never bootstrapped)
    out['FIRST'][0] = True
    for w in WINDOWS_S:
        out[f'GW{w:g}'][:] = ep.ps.window_gain(times, w)
    return out, pre


@dataclass
class Dataset:
    """Concatenated SMDP transitions of many episodes (all arrays aligned; EP = episode index)."""
    arrays: dict
    episodes: list           # per-episode dicts: meta + proof + pre_choice + split
    manifest: dict

    def __getattr__(self, k):
        a = self.__dict__.get('arrays')
        if a is not None and k in a:
            return a[k]
        raise AttributeError(k)

    @property
    def n(self):
        return int(len(self.arrays['R']))

    def episode_mask(self, ep_ids):
        return np.isin(self.arrays['EP'], np.asarray(sorted(ep_ids), dtype=np.int64))

    def train_episode_ids(self):
        return [i for i, e in enumerate(self.episodes) if e['split'] == 'train' and e['n_choice'] > 0]

    def routes(self):
        return [e['route_id'] for e in self.episodes]


def build_dataset(run_dirs, out_dir=None, allow_test=False, reward_mode='prefix', xml_path=None,
                  test_routes=None):
    """Build (and optionally write) the dataset. Returns (Dataset, list of Episode)."""
    test_routes = C.test_route_ids() if test_routes is None else frozenset(test_routes)
    eps_, parts, metas = [], [], []
    for k, rd in enumerate(run_dirs):
        ep = build_episode(rd, test_routes, reward_mode, xml_path)
        if ep.split == 'test' and not allow_test:
            raise PermissionError(f'{rd}: route {ep.meta["route_id"]} is a held-out test route; refusing to build '
                                  'a training dataset from it (allow_test=True marks it split=test instead)')
        eps_.append(ep)
        arr, pre = smdp_arrays(ep) if ep.kind == 'v3' else smdp_arrays(Episode(ep.meta, ep.kind, [], ep.ps, ep.split))
        arr['EP'] = np.full(len(arr['R']), len(metas), np.int32)
        parts.append(arr)
        g = ep.ps.diagnostics
        metas.append({**ep.meta, 'split': ep.split, 'kind': ep.kind, 'n_epochs': len(ep.epochs),
                      'n_choice': int(len(arr['R'])), 'pre_choice_return': pre, 'proof': ep.proof,
                      'reconstruction': {k2: g.get(k2) for k2 in (
                          'mode', 'rc_mode', 'rc_hat_end', 'rc_official', 'rc_abs_err_unanchored', 'rc_scale',
                          'route_polyline_m', 'route_length_official_m', 'penalty_parsed', 'penalty_official',
                          'penalty_rel_err', 'penalty_check_ok', 'composed_minus_product', 'located_events',
                          'terminal_events', 'max_match_dist_m', 'S_decreases', 'routes_xml_sha256_match',
                          'prefix_unavailable')},
                      'events': [e.as_dict() for e in ep.ps.events if e.factor != 1.0],
                      'mu_known': bool(np.all(np.isfinite(arr['MU']))) if len(arr['MU']) else None,
                      'actions_at_choice': {'REFINE': int(np.sum(arr['A'] == REFINE)),
                                            'REFRESH': int(np.sum(arr['A'] == REFRESH))}})
    keys = parts[0].keys() if parts else []
    arrays = {k: np.concatenate([p[k] for p in parts]) for k in keys}
    manifest = {'schema': SCHEMA, 'created_utc': C.utc_stamp(), 'n_episodes': len(metas),
                'n_transitions': int(len(arrays.get('R', []))), 'features': F.spec_dict(),
                'feature_columns_all': list(F.ALL_COLUMNS), 'feature_columns_no_lease': list(F.NO_LEASE_COLUMNS),
                'lease_derived': list(F.LEASE_DERIVED), 'actions': {'REFINE': REFINE, 'REFRESH': REFRESH},
                'eval_covariates': list(EVAL_COVARIATES),
                'windows_s': list(WINDOWS_S), 'reward_mode': reward_mode,
                'reward': 'S(t) = RC(t) x P(t) (prefix_score.py); r_n = S(t_{n+1}) - S(t_n); last r = DS - S(t_N)',
                'test_route_guard': {'allow_test': allow_test, 'n_test_routes': len(test_routes),
                                     'test_episodes': sum(m['split'] == 'test' for m in metas)},
                'identity_all_ok': all(m['proof']['identity_ok'] for m in metas),
                'inputs': [{'run_dir': m['run_dir'], 'official_results_sha256': C.sha256_file(
                    Path(m['run_dir']) / 'raw' / 'official_results.json')} for m in metas],
                'code_sha256': C.code_hashes()}
    ds = Dataset(arrays, metas, manifest)
    if out_dir is not None:
        save_dataset(ds, out_dir, eps_)
    return ds, eps_


def save_dataset(ds, out_dir, episodes=None):
    out_dir = Path(out_dir)
    C._check_writable(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / 'transitions.tmp.npz'
    np.savez_compressed(tmp, **ds.arrays)
    tmp.replace(out_dir / 'transitions.npz')
    if episodes is not None:
        ep_rows = {'EP': [], 'T': [], 'CODE': [], 'CHOICE': [], 'R': [], 'REFINE_OK': [], 'REFRESH_OK': []}
        for k, ep in enumerate(episodes):
            for e in ep.epochs:
                ep_rows['EP'].append(k)
                ep_rows['T'].append(e['t'])
                ep_rows['CODE'].append(e['code'])
                ep_rows['CHOICE'].append(e['choice'])
                ep_rows['R'].append(e.get('r', 0.0))
                ep_rows['REFINE_OK'].append(-1 if e['refine_ok'] is None else int(e['refine_ok']))
                ep_rows['REFRESH_OK'].append(-1 if e['refresh_ok'] is None else int(e['refresh_ok']))
        tmp2 = out_dir / 'epochs.tmp.npz'
        np.savez_compressed(tmp2, EP=np.asarray(ep_rows['EP'], np.int32), T=np.asarray(ep_rows['T']),
                            CODE=np.asarray(ep_rows['CODE'], np.int8), CHOICE=np.asarray(ep_rows['CHOICE'], bool),
                            R=np.asarray(ep_rows['R']), REFINE_OK=np.asarray(ep_rows['REFINE_OK'], np.int8),
                            REFRESH_OK=np.asarray(ep_rows['REFRESH_OK'], np.int8))
        tmp2.replace(out_dir / 'epochs.npz')
    C.atomic_json(out_dir / 'episodes.json', ds.episodes)
    C.atomic_json(out_dir / 'manifest.json', ds.manifest)
    return out_dir


def load_dataset(out_dir):
    out_dir = Path(out_dir)
    with np.load(out_dir / 'transitions.npz') as z:
        arrays = {k: z[k] for k in z.files}
    return Dataset(arrays, C.read_json(out_dir / 'episodes.json'), C.read_json(out_dir / 'manifest.json'))


__all__ = ['SCHEMA', 'REFINE', 'REFRESH', 'CODES', 'WINDOWS_S', 'discover_runs', 'run_meta', 'load_epochs',
           'Episode', 'build_episode', 'smdp_arrays', 'Dataset', 'build_dataset', 'save_dataset', 'load_dataset']
