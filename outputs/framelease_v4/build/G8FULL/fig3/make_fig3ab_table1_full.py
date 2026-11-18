"""Fig. 3 (a) and (b) after the layout of Table I, from a given analysis directory: the six implemented policies of
Table I at kappa 1.0, driving score (mean, 95% route-bootstrap interval) against action-age p50 (a) and p95 (b), each
with its own 95% interval. PNG (300 dpi) and PDF.

Parameterized copy of /home/kang/Desktop/FrameLease_figure_code/fig3_panels/make_fig3ab_table1.py (sha256
b2130b6f91e6be3980595449778c5419edbb93a3d37aa7f18d3a3d95d7a1ceb8; the original stays unchanged and keeps its analysis
final_20261116T091445). Changes: the project root, the analysis directory and the output directory are arguments;
both the PNG and the PDF go to --out; the title states the number of routes from the data (the n of the six
driving-score means: "n = 44 routes" when all are equal, "n = <min>-<max> routes" otherwise) instead of the fixed
"n = 14 routes". Drawing code, style and the check against numbers.json are the original's.

Data: the registered, frozen analysis given by --final (the second analysis freeze under Amendment A17, all
registered jobs final) only, conditions.csv rows <arm>_k1.0_s11, subset all, statistic route_mean; every plotted mean
is checked against the registered figures/numbers.json of that analysis (tab1.<arm>.<metric>.mean, as shown there).
Style: the registered generator's palette, markers and 8 pt serif type.

    cd /home/kang/Desktop/DAC
    .conda-unidrive-linux/bin/python -I -B outputs/framelease_v4/build/G8FULL/fig3/make_fig3ab_table1_full.py \
        --final outputs/framelease_v4/analysis/final_<stamp> --out outputs/framelease_v4/build/G8FULL/fig3_full_<stamp>
"""
import argparse
import csv
import json
import sys
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
ap.add_argument('--root', default='/home/kang/Desktop/DAC', help='project root (framelease_v4/ is imported from it)')
ap.add_argument('--final', required=True, help='analysis directory final_<stamp> (relative to --root or absolute)')
ap.add_argument('--out', required=True, help='output directory of the PNG and PDF files (created)')
ARGS = ap.parse_args()

ROOT = Path(ARGS.root).resolve()
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from framelease_v4.analysis import figures_tables as FT  # noqa: E402

import matplotlib  # noqa: E402

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

FINAL = Path(ARGS.final) if Path(ARGS.final).is_absolute() else ROOT / ARGS.final
PNG_OUT = Path(ARGS.out) if Path(ARGS.out).is_absolute() else Path.cwd() / ARGS.out
PDF_OUT = PNG_OUT
if FINAL.name == 'final_20261116T091445':
    sys.exit('this copy draws the second analysis; the original script draws final_20261116T091445')
if str(PNG_OUT.resolve()).startswith(str(Path('/home/kang/Desktop').resolve()) + '/') \
        and not str(PNG_OUT.resolve()).startswith(str(Path('/home/kang/Desktop/DAC').resolve()) + '/'):
    sys.exit('--out lies on the Desktop outside the project: the Desktop figure files stay unchanged')
if str(PNG_OUT.resolve()).startswith(str(FINAL.resolve()) + '/') or PNG_OUT.resolve() == FINAL.resolve():
    sys.exit('--out lies inside the analysis directory (its ANALYSIS_OUTPUTS.sha256 would no longer list every file)')
ARMS = ('fixed_deep', 'fast_only', 'age_only', 'event_triggered', 'fl_heuristic', 'fl_full')
STYLE = {**FT.ARM_STYLE, 'age_only': (FT.PALETTE[4], 'v'), 'event_triggered': (FT.PALETTE[6], 'P')}
LABEL = {'fixed_deep': 'Fixed Deep (10 steps)', 'fast_only': 'Fast Only', 'age_only': 'Age-Only',
         'event_triggered': 'Event-Triggered', 'fl_heuristic': 'FrameLease + Heuristic', 'fl_full': 'Full FrameLease'}
METRICS = ('driving_score', 'action_age_p50_s', 'action_age_p95_s')


def load():
    with open(FINAL / 'analysis/conditions.csv', newline='') as fh:
        rows = list(csv.DictReader(fh))
    reg = json.loads((FINAL / 'figures/numbers.json').read_text())['numbers']
    pts = {}
    for arm in ARMS:
        pts[arm] = {}
        for m in METRICS:
            hit = [r for r in rows if r['condition'] == f'{arm}_k1.0_s11' and r['subset'] == 'all'
                   and r['metric'] == m and r['statistic'] == 'route_mean']
            if len(hit) != 1:
                raise SystemExit(f'{arm} {m}: {len(hit)} rows')
            r = hit[0]
            pts[arm][m] = {k: float(r[c]) for k, c in (('mean', 'mean'), ('lo', 'ci95_lo'), ('hi', 'ci95_hi'))}
            pts[arm][m]['n'] = int(r['n'])
            key = f'tab1.{arm}.{m}.mean'
            if key in reg and abs(reg[key]['value'] - pts[arm][m]['mean']) > 1e-9:
                raise SystemExit(f'{key}: registered {reg[key]["value"]} != {pts[arm][m]["mean"]}')
    print('means equal to the registered numbers.json:', {a: pts[a]['driving_score']['mean'] for a in ARMS})
    return pts


def routes_text(pts):
    ns = sorted({pts[a]['driving_score']['n'] for a in ARMS})
    return f'n = {ns[0]} routes' if len(ns) == 1 else f'n = {ns[0]}-{ns[-1]} routes'


def panel(pts, which):
    xm = 'action_age_p50_s' if which == 'a' else 'action_age_p95_s'
    q = 'p50' if which == 'a' else 'p95'
    with plt.rc_context(FT.rc_params()):
        fig = plt.figure(figsize=(FT.COL_W_IN, 3.2))
        ax = fig.add_axes([0.13, 0.36, 0.83, 0.57])
        for arm in ARMS:
            color, marker = STYLE[arm]
            x, y = pts[arm][xm], pts[arm]['driving_score']
            ax.plot([x['lo'], x['hi']], [y['mean']] * 2, color=color, linewidth=FT.ERR_W, alpha=0.8, zorder=1)
            ax.plot([x['mean']] * 2, [y['lo'], y['hi']], color=color, linewidth=FT.ERR_W, alpha=0.8, zorder=1)
            ax.plot([x['mean']], [y['mean']], linestyle='none', marker=marker, markersize=FT.MARKER_PT + 2.0,
                    markerfacecolor=color, markeredgecolor=color, zorder=3)
        ax.set_xlabel(f'Action age {q} (s), mean over routes')
        ax.set_ylabel('Driving score (mean)')
        ax.set_title(f'({which}) Driving score vs. action age {q} ($\\kappa$ = 1.0, {routes_text(pts)})')
        FT._ax_style(ax, 'both')
        handles = [Line2D([], [], linestyle='none', marker=STYLE[a][1], markersize=FT.MARKER_PT + 2.0,
                          markerfacecolor=STYLE[a][0], markeredgecolor=STYLE[a][0], label=LABEL[a]) for a in ARMS]
        fig.legend(handles=handles, loc='lower center', bbox_to_anchor=(0.5, 0.005), ncol=2, columnspacing=1.2)
        stem = f'Fig3{which}_TableI_methods_DS_vs_age_{q}'
        fig.savefig(PNG_OUT / f'{stem}.png', dpi=300, metadata={'Software': None})
        fig.savefig(PDF_OUT / f'{stem}.pdf', metadata={'CreationDate': None, 'ModDate': None, 'Creator': None})
        plt.close(fig)
        print('wrote', PNG_OUT / f'{stem}.png', 'and .pdf', f'({routes_text(pts)})')


if __name__ == '__main__':
    PNG_OUT.mkdir(parents=True, exist_ok=True)
    p = load()
    panel(p, 'a')
    panel(p, 'b')
