#!/usr/bin/env python3
"""Fig. 1 data (freshness-depth evidence), exported read-only from the v2 outputs (CPU only, no model).

    cd /home/kang/Desktop/DAC
    .conda-unidrive-linux/bin/python -I -B framelease_v4/offline/fig1_data.py

Sources (framelease_v2/C1_RESULTS.md Sec. 13 and framelease_v2/CLOSED_LOOP_RESULTS.md):
  R1m  outputs/framelease_v2/c1_analysis/merged20_W1.0_pub   (W = 1 s; paper figure source)
  R05m outputs/framelease_v2/c1_analysis/merged20_W0.5_pub   (W = 0.5 s)
  RKm  outputs/framelease_v2/c1_analysis/merged20_W0.5_kappafine_pub (W = 0.5 s, kappa 1.0 ... 2.4)
  PF   outputs/framelease_v2/c1_analysis/paper_figure_merged20/c1_age_vs_depth_data.csv (reproduction check)
  CL   outputs/framelease_v2/closed_loop_matrix/final_20261108T2222/analysis/{per_route_by_scenario,contrasts}.csv
  CLX  outputs/framelease_v2/closed_loop_matrix/exploratory_20261109T0030/closed_loop_runs.csv (fast_only kappa 2.0)
  AB   third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/tools/ability_benchmark.py (official ability mapping,
       parsed with ast; sha256 pinned as in framelease_v3/extend/extend.py)

Outputs (OUT/fig1/):
  c1_age_vs_depth.csv          execution error (m) vs observation age for flow depths 1 / 5 / 10: mean over clips of
                               per-clip means and the Student-t 95% interval over clips, W = 1 s and 0.5 s,
                               splits val (15 held-out clips), train (5), all (20)
  c1_fresh_vs_deep_kappa.csv   Fast@Fresh - Deep@Old execution-error contrast vs kappa (depth-1 fast plan), with its
                               staleness-gain and depth-cost decomposition (copied from headline.csv)
  closed_loop_ds_by_route.csv  per route (= per scenario type; one route per type): DS / RC / action age of Fixed Deep
                               and Fast Only at kappa 1.0 (seed 11: 44 routes; seed 12: 15 routes), DS differences,
                               plus the kappa 1.5 and 2.0 differences where those arms ran
  closed_loop_ds_by_ability.csv DS difference Fixed Deep - Fast Only at kappa 1.0 aggregated by Bench2Drive ability
  closed_loop_kappa_trend.csv  mean paired DS difference vs kappa (registered contrasts copied from contrasts.csv;
                               kappa 2.0 recomputed from the exploratory runs)
  fig1_check.json, fig1_sources.json
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault('OMP_NUM_THREADS', '1')
sys.dont_write_bytecode = True

import ast  # noqa: E402
import csv  # noqa: E402
import re  # noqa: E402
from collections import defaultdict  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
from scipy.stats import t as student_t  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v4.offline import common as C  # noqa: E402

C1 = ROOT / 'outputs/framelease_v2/c1_analysis'
RUNS = {'R1m': C1 / 'merged20_W1.0_pub', 'R05m': C1 / 'merged20_W0.5_pub', 'RKm': C1 / 'merged20_W0.5_kappafine_pub'}
PF = C1 / 'paper_figure_merged20/c1_age_vs_depth_data.csv'
CLM = ROOT / 'outputs/framelease_v2/closed_loop_matrix'
CL_ROUTES = CLM / 'final_20261108T2222/analysis/per_route_by_scenario.csv'
CL_CONTRASTS = CLM / 'final_20261108T2222/analysis/contrasts.csv'
CLX_RUNS = CLM / 'exploratory_20261109T0030/closed_loop_runs.csv'
CL_ROUTES_JSON = CLM / 'routes.json'
AB = ROOT / 'third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/tools/ability_benchmark.py'
AB_SHA256 = '86d93698f68d836230cc93be72cba4f1b7e501c146425a424288c9bbacd2c686'
FIG1 = C.OUT / 'fig1'
DEPTHS = (1, 5, 10)
ABILITIES = ('Merging', 'Overtaking', 'Emergency_Brake', 'Give_Way', 'Traffic_Signs')


def read_csv(p):
    with open(p, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def t_interval(vals):
    v = np.asarray(vals, dtype=float)
    n = len(v)
    m = float(v.mean())
    if n < 2:
        return m, np.nan, np.nan
    q = float(student_t.ppf(0.975, n - 1))
    h = q * float(v.std(ddof=1)) / np.sqrt(n)
    return m, m - h, m + h


def ability_map():
    if C.sha256_file(AB) != AB_SHA256:
        raise SystemExit(f'{AB} sha256 differs from the pinned mapping')
    tree = ast.parse(AB.read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'Ability' for t in node.targets):
            return ast.literal_eval(node.value)
    raise SystemExit('Ability mapping not found')


def abilities_of(scenario, amap):
    norm = lambda s: s.replace('_', '')  # noqa: E731
    return sorted(a for a, names in amap.items() if norm(scenario) in {norm(n) for n in names})


# ----------------------------------------------------------------------------- C1 curves

def c1_curves():
    rows = []
    for run, window in (('R1m', 1.0), ('R05m', 0.5)):
        surf = read_csv(RUNS[run] / 'surface.csv')
        by = defaultdict(dict)        # (split, depth, age) -> clip -> err
        for r in surf:
            d = int(r['depth'])
            if d not in DEPTHS:
                continue
            age = round(float(r['age_s']), 3)
            by[(r['split'], d, age)][r['clip']] = float(r['exec_err_mean_m'])
            by[('all', d, age)][r['clip']] = float(r['exec_err_mean_m'])
        for (split, d, age), per_clip in sorted(by.items()):
            m, lo, hi = t_interval(list(per_clip.values()))
            rows.append({'run': run, 'window_s': window, 'split': split, 'depth': d, 'age_s': age,
                         'n_clips': len(per_clip), 'exec_err_mean_m': m, 't95_lo': lo, 't95_hi': hi})
    # reproduction check against the paper figure data (panel a, val, W = 1 s)
    pf = [r for r in read_csv(PF) if r['panel'] == 'a']
    mine = {(int(r['depth']), r['age_s']): r for r in rows if r['run'] == 'R1m' and r['split'] == 'val'}
    diffs = []
    for r in pf:
        d = int(r['series'].replace('depth', ''))
        x = mine[(d, round(float(r['x']), 3))]
        diffs.append(max(abs(x['exec_err_mean_m'] - float(r['y'])), abs(x['t95_lo'] - float(r['y_ci95_lo'])),
                         abs(x['t95_hi'] - float(r['y_ci95_hi']))))
    return rows, {'paper_figure_panel_a_points': len(pf), 'max_abs_diff_m': float(max(diffs))}


def c1_kappa():
    rows = []
    pat = re.compile(r'^(fast_fresh_minus_deep_old|staleness_gain|depth_cost_equal_age)_kappa([0-9.]+)_fast1$')
    for run, window in (('RKm', 0.5), ('R1m', 1.0)):
        for r in read_csv(RUNS[run] / 'headline.csv'):
            m = pat.match(r['quantity'])
            if not m:
                continue
            rows.append({'run': run, 'window_s': window, 'quantity': m.group(1), 'kappa': float(m.group(2)),
                         'split': r['split'], 'value_m': float(r['value']),
                         't95_lo': float(r['t_ci95_lo']) if r['t_ci95_lo'] else np.nan,
                         't95_hi': float(r['t_ci95_hi']) if r['t_ci95_hi'] else np.nan,
                         'sign_flip_p_two_sided': float(r['sign_flip_p_two_sided']) if r['sign_flip_p_two_sided'] else np.nan,
                         'n_clips': r['n_clips'], 'clips_pos': r['n_clips_positive'], 'clips_neg': r['n_clips_negative'],
                         'source': f'{run}/headline.csv:{r["quantity"]}'})
    rows.sort(key=lambda x: (x['run'], x['quantity'], x['split'], x['kappa']))
    return rows


# ----------------------------------------------------------------------------- closed loop

def closed_loop():
    amap = ability_map()
    pr = read_csv(CL_ROUTES)
    arm = defaultdict(dict)
    meta = {}
    for r in pr:
        if r['status'] != 'used':
            continue
        rid = int(r['route_id'])
        arm[r['arm']][rid] = r
        meta[rid] = (r['scenario_type'], r['town'], int(r['route_index']), r['subsets'])
    for r in read_csv(CLX_RUNS):
        if r['arm'] == 'fast_only_k2.0_s11' and r['analysis_use'] == '1':
            arm['fast_only_k2.0_s11'][int(r['route_id'])] = {'driving_score': r['driving_score'],
                                                           'route_completion': r['route_completion'],
                                                           'action_age_p50_s': r['action_age_p50_s']}
    pairs = {'k1.0_s11': ('fixed_deep_k1.0_s11', 'fast_only_k1.0_s11'),
             'k1.0_s12': ('fixed_deep_k1.0_s12', 'fast_only_k1.0_s12'),
             'k1.5_s11': ('fixed_deep_k1.5_s11', 'fast_only_k1.5_s11'),
             'k2.0_s11': ('fixed_deep_k2.0_s11', 'fast_only_k2.0_s11')}
    routes = []
    for rid in sorted(meta, key=lambda x: meta[x][2]):
        sc, town, idx, subsets = meta[rid]
        row = {'route_id': rid, 'route_index': idx, 'scenario_type': sc, 'town': town,
               'abilities': '|'.join(abilities_of(sc, amap)), 'subsets': subsets}
        for tag, (a, b) in pairs.items():
            ra, rb = arm[a].get(rid), arm[b].get(rid)
            if ra is None or rb is None:
                continue
            row[f'DS_fixed_deep_{tag}'] = float(ra['driving_score'])
            row[f'DS_fast_only_{tag}'] = float(rb['driving_score'])
            row[f'DS_diff_{tag}'] = float(ra['driving_score']) - float(rb['driving_score'])
            if tag.startswith('k1.0'):
                row[f'RC_fixed_deep_{tag}'] = float(ra['route_completion'])
                row[f'RC_fast_only_{tag}'] = float(rb['route_completion'])
                row[f'age_p50_fixed_deep_{tag}'] = float(ra['action_age_p50_s'])
                row[f'age_p50_fast_only_{tag}'] = float(rb['action_age_p50_s'])
        ds = [row[k] for k in ('DS_diff_k1.0_s11', 'DS_diff_k1.0_s12') if k in row]
        row['DS_diff_k1.0_seed_mean'] = float(np.mean(ds)) if ds else np.nan
        row['n_seeds_k1.0'] = len(ds)
        routes.append(row)
    # per ability (kappa 1.0): seed 11 (44 routes) and seed mean
    rng = np.random.default_rng(C.BOOT_SEED)
    abil = []
    for ab in ABILITIES + ('all',):
        sel = [r for r in routes if ab == 'all' or ab in r['abilities'].split('|')]
        for col, label in (('DS_diff_k1.0_s11', 'seed 11'), ('DS_diff_k1.0_seed_mean', 'mean over seeds 11/12'),
                           ('DS_diff_k1.5_s11', 'kappa 1.5, seed 11')):
            v = np.array([r[col] for r in sel if col in r and np.isfinite(r[col])], dtype=float)
            if not len(v):
                continue
            boot = v[rng.integers(0, len(v), size=(C.BOOT_N, len(v)))].mean(axis=1)
            small = len(v) < 5          # no interval for fewer than 5 routes
            abil.append({'ability': ab, 'series': label, 'n_routes': len(v), 'mean_DS_diff': float(v.mean()),
                         'boot95_lo': np.nan if small else float(np.quantile(boot, 0.025)),
                         'boot95_hi': np.nan if small else float(np.quantile(boot, 0.975)),
                         'routes_pos': int((v > 0).sum()), 'routes_neg': int((v < 0).sum()),
                         'routes_zero': int((v == 0).sum()),
                         'scenario_types': '|'.join(sorted(r['scenario_type'] for r in sel
                                                            if col in r and np.isfinite(r[col])))})
    # kappa trend: registered contrasts (copied) + kappa 2.0 exploratory (recomputed)
    con = {(r['contrast_id'], r['metric']): r for r in read_csv(CL_CONTRASTS)}
    trend = []
    for cid, kappa, seed in (('H2_fixed_deep_minus_fast_only_k1.0', 1.0, 11),
                             ('H2_fixed_deep_minus_fast_only_k1.0_s12', 1.0, 12),
                             ('H2_fixed_deep_minus_fast_only_k1.5', 1.5, 11)):
        for met in ('driving_score', 'route_completion', 'action_age_p50_s'):
            r = con[(cid, met)]
            trend.append({'kappa': kappa, 'seed': seed, 'metric': met, 'n_routes': int(r['n']),
                          'mean_diff': float(r['mean']), 'ci95_lo': float(r['ci95_lo']),
                          'ci95_hi': float(r['ci95_hi']), 'p_two_sided': float(r['p_two_sided']),
                          'p_method': r['p_method'], 'decision': r['decision'], 'role': r['role'],
                          'source': f'contrasts.csv:{cid}/{met}'})
    v = np.array([r['DS_diff_k2.0_s11'] for r in routes if 'DS_diff_k2.0_s11' in r])
    boot = v[rng.integers(0, len(v), size=(C.BOOT_N, len(v)))].mean(axis=1)
    trend.append({'kappa': 2.0, 'seed': 11, 'metric': 'driving_score', 'n_routes': len(v), 'mean_diff': float(v.mean()),
                  'ci95_lo': float(np.quantile(boot, 0.025)), 'ci95_hi': float(np.quantile(boot, 0.975)),
                  'p_two_sided': np.nan, 'p_method': 'not computed (exploratory arm; CLOSED_LOOP_RESULTS.md reports '
                  'exact sign-flip p = 0.2471)', 'decision': 'exploratory', 'role': 'exploratory',
                  'source': 'per_route_by_scenario.csv fixed_deep_k2.0_s11 - closed_loop_runs.csv fast_only_k2.0_s11'})
    # the same 11 routes at kappa 1.0 and 1.5 (like-for-like with the kappa 2.0 arm; descriptive)
    for tag, kappa in (('k1.0_s11', 1.0), ('k1.5_s11', 1.5)):
        u = np.array([r[f'DS_diff_{tag}'] for r in routes if 'DS_diff_k2.0_s11' in r and f'DS_diff_{tag}' in r])
        bu = u[rng.integers(0, len(u), size=(C.BOOT_N, len(u)))].mean(axis=1)
        trend.append({'kappa': kappa, 'seed': 11, 'metric': 'driving_score_on_kappa2_routes', 'n_routes': len(u),
                      'mean_diff': float(u.mean()), 'ci95_lo': float(np.quantile(bu, 0.025)),
                      'ci95_hi': float(np.quantile(bu, 0.975)), 'p_two_sided': np.nan,
                      'p_method': 'not computed (descriptive subset)', 'decision': 'descriptive', 'role': 'descriptive',
                      'source': f'per_route_by_scenario.csv, routes of the kappa 2.0 arm, {tag}'})
    # consistency checks with the frozen contrasts
    chk = {}
    for tag, cid in (('k1.0_s11', 'H2_fixed_deep_minus_fast_only_k1.0'), ('k1.0_s12', 'H2_fixed_deep_minus_fast_only_k1.0_s12'),
                     ('k1.5_s11', 'H2_fixed_deep_minus_fast_only_k1.5')):
        vals = [r[f'DS_diff_{tag}'] for r in routes if f'DS_diff_{tag}' in r]
        chk[tag] = {'n': len(vals), 'mean': float(np.mean(vals)),
                    'frozen_mean': float(con[(cid, 'driving_score')]['mean']),
                    'abs_diff': abs(float(np.mean(vals)) - float(con[(cid, 'driving_score')]['mean']))}
    chk['k2.0_s11'] = {'n': int(len(v)), 'mean': float(v.mean()), 'reported_in_CLOSED_LOOP_RESULTS': -11.176}
    return routes, abil, trend, chk


def main():
    FIG1.mkdir(parents=True, exist_ok=True)
    curves, cchk = c1_curves()
    kap = c1_kappa()
    routes, abil, trend, lchk = closed_loop()
    C.write_csv(FIG1 / 'c1_age_vs_depth.csv', curves)
    C.write_csv(FIG1 / 'c1_fresh_vs_deep_kappa.csv', kap)
    C.write_csv(FIG1 / 'closed_loop_ds_by_route.csv', routes)
    C.write_csv(FIG1 / 'closed_loop_ds_by_ability.csv', abil)
    C.write_csv(FIG1 / 'closed_loop_kappa_trend.csv', trend)
    ok = cchk['max_abs_diff_m'] < 1e-9 and all(x.get('abs_diff', 0) < 1e-6 for x in lchk.values())
    C.write_json(FIG1 / 'fig1_check.json', {'c1_vs_paper_figure': cchk, 'closed_loop_vs_frozen_contrasts': lchk,
                                            'pass': ok})
    srcs = [RUNS['R1m'] / 'surface.csv', RUNS['R05m'] / 'surface.csv', RUNS['R1m'] / 'headline.csv',
            RUNS['RKm'] / 'headline.csv', RUNS['R1m'] / 'summary.json', PF, CL_ROUTES, CL_CONTRASTS, CLX_RUNS, AB,
            CL_ROUTES_JSON]
    C.write_json(FIG1 / 'fig1_sources.json', {str(p.relative_to(ROOT)): C.sha256_file(p) for p in srcs})
    C.log_progress(f'fig1_data: check pass={ok}')
    print({'c1_check': cchk, 'cl_check': lchk, 'pass': ok})
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
