"""Fig. 3 of the FrameLease paper as three separate figures (PNG, 300 dpi, and PDF) from a given analysis directory.

Parameterized copy of /home/kang/Desktop/FrameLease_figure_code/fig3_panels/make_fig3_panels.py (sha256
8e87da92f38391647899068456e194b7aa886aea2ac6ce04010cce331c03be97; the original stays unchanged and keeps its analysis
final_20261116T091445). Changes: the project root, the analysis directory and the output directory are arguments;
both the PNG and the PDF go to --out (the original writes the PNG onto the Desktop and the PDF next to itself); the
docstring states no route count. Drawing code, style constants and the check against numbers.json are the original's.

  (a) driving score against action-age p50, (b) against action-age p95, (c) EIR and GPU usage of every point.

Data: the registered, frozen analysis given by --final (the second analysis freeze under Amendment A17, all
registered jobs final), read through the registered functions of framelease_v4/analysis/figures_tables.py
(load_analysis, fig3_points), unchanged and imported read-only; every value is checked against the registered
figures/numbers.json of that analysis before anything is drawn. Panel (c) states the number of routes behind every
point.

    cd /home/kang/Desktop/DAC
    .conda-unidrive-linux/bin/python -I -B outputs/framelease_v4/build/G8FULL/fig3/make_fig3_panels_full.py \
        --final outputs/framelease_v4/analysis/final_<stamp> --out outputs/framelease_v4/build/G8FULL/fig3_full_<stamp>
"""
import argparse
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
NAMES = {'a': 'Fig3a_DS_vs_action_age_p50', 'b': 'Fig3b_DS_vs_action_age_p95', 'c': 'Fig3c_EIR_GPU_usage'}
if FINAL.name == 'final_20261116T091445':
    sys.exit('this copy draws the second analysis; the original script draws final_20261116T091445')
if str(PNG_OUT.resolve()).startswith(str(Path('/home/kang/Desktop').resolve()) + '/') \
        and not str(PNG_OUT.resolve()).startswith(str(Path('/home/kang/Desktop/DAC').resolve()) + '/'):
    sys.exit('--out lies on the Desktop outside the project: the Desktop figure files stay unchanged')
if str(PNG_OUT.resolve()).startswith(str(FINAL.resolve()) + '/') or PNG_OUT.resolve() == FINAL.resolve():
    sys.exit('--out lies inside the analysis directory (its ANALYSIS_OUTPUTS.sha256 would no longer list every file)')


def load_points():
    src = FT.load_analysis(FINAL / 'analysis')
    nums = FT.Numbers()
    points = FT.fig3_points(src, nums)
    reg = json.loads((FINAL / 'figures/numbers.json').read_text())
    reg = reg.get('numbers', reg)
    checked = 0
    for arm in FT.FIG3_ARMS:
        for k in FT.KAPPAS:
            for metric in (FT.FIG3_Y, *FT.FIG3_X.values(), *FT.FIG3_NOTES):
                for field in ('mean', 'lo', 'hi', 'n'):
                    key = f'fig3.{arm}.kappa{k:.1f}.{metric}.{field}'
                    want = reg[key]['value'] if isinstance(reg.get(key), dict) else reg.get(key)
                    got = points[arm][k][metric][field]
                    if want != got and not (isinstance(want, float) and isinstance(got, float)
                                            and abs(want - got) <= 1e-12 * max(1.0, abs(want))):
                        raise SystemExit(f'{key}: registered {want!r} != {got!r}')
                    checked += 1
    print(f'{checked} values equal to the registered numbers.json of {FINAL.name}')
    return points


def legend_handles():
    arms = [Line2D([], [], color=FT.ARM_STYLE[a][0], marker=FT.ARM_STYLE[a][1], markersize=FT.MARKER_PT + 1.0,
                   linewidth=FT.LINE_W, label=FT.ARM_LABEL[a]) for a in FT.FIG3_ARMS]
    kap = [Line2D([], [], color=FT.INK_2, marker='o', linestyle='none', markersize=FT.MARKER_PT + 1.0,
                  fillstyle=FT.KAPPA_FILL[k], markerfacecoloralt='white',
                  label=rf'$\kappa$ = {k:.1f} (GPU share {FT.KAPPA_SHARE[k]})') for k in FT.KAPPAS]
    return arms, kap


def save(fig, stem):
    fig.savefig(PNG_OUT / f'{stem}.png', dpi=300, metadata={'Software': None})
    fig.savefig(PDF_OUT / f'{stem}.pdf', metadata={'CreationDate': None, 'ModDate': None, 'Creator': None})
    plt.close(fig)
    print('wrote', PNG_OUT / f'{stem}.png', 'and .pdf')


def panel_ab(points, which):
    xkey = FT.FIG3_X['p50' if which == 'a' else 'p95']
    q = 'p50' if which == 'a' else 'p95'
    with plt.rc_context(FT.rc_params()):
        fig = plt.figure(figsize=(FT.COL_W_IN, 3.2))
        ax = fig.add_axes([0.13, 0.355, 0.83, 0.575])
        FT.draw_fig3_panel(ax, points, xkey, f'Action age {q} (s), mean over routes')
        ax.set_title(f'({which}) Driving score vs. action age {q}')
        arms, kap = legend_handles()
        fig.legend(handles=[arms[0], kap[0], arms[1], kap[1], arms[2], kap[2], arms[3]], loc='lower center',
                   bbox_to_anchor=(0.5, 0.005), ncol=2, columnspacing=1.2, handlelength=1.8)
        save(fig, NAMES[which])


def panel_c(points):
    arms = FT.FIG3_ARMS
    with plt.rc_context(FT.rc_params()):
        fig = plt.figure(figsize=(FT.COL_W_IN, 3.0))
        ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
        ax.axis('off')
        t = dict(transform=ax.transAxes, va='center')
        x_name, cols = 0.03, {k: 0.525 + 0.185 * j for j, k in enumerate(FT.KAPPAS)}
        ax.text(0.02, 0.955, '(c) EIR, GPU usage and routes of every point', ha='left', **t)
        y_head = 0.875
        for k, x in cols.items():
            ax.plot([x - 0.045], [y_head], transform=ax.transAxes, linestyle='none', marker='o',
                    markersize=FT.MARKER_PT + 1.0, fillstyle=FT.KAPPA_FILL[k], markerfacecolor=FT.INK_2,
                    markerfacecoloralt='white', markeredgecolor=FT.INK_2, clip_on=False)
            ax.text(x + 0.015, y_head, rf'$\kappa$ {k:.1f}', ha='center', **t)
        ax.plot([0.02, 0.98], [0.83, 0.83], transform=ax.transAxes, color=FT.AXIS_C, linewidth=FT.AX_W)
        row_h = 0.175
        for i, arm in enumerate(arms):
            y = 0.74 - row_h * i
            color, marker = FT.ARM_STYLE[arm]
            ax.plot([x_name], [y], transform=ax.transAxes, linestyle='none', marker=marker,
                    markersize=FT.MARKER_PT + 1.0, markerfacecolor=color, markeredgecolor=color, clip_on=False)
            ax.text(x_name + 0.03, y, FT.ARM_LABEL[arm], ha='left', **t)
            for k, x in cols.items():
                p = points[arm][k]
                n = p[FT.FIG3_Y]['n']
                eir = FT.FIG3_SHOWN['eir'](p['eir']['mean'])
                gpu = FT.FIG3_SHOWN['gpu_usage'](p['gpu_usage']['mean'])
                ax.text(x, y, f'EIR {eir}\nGPU {gpu}\nn = {n}', ha='center', linespacing=1.12, color=FT.INK_2, **t)
            if i < len(arms) - 1:
                ax.plot([0.02, 0.98], [y - row_h / 2] * 2, transform=ax.transAxes, color=FT.GRID_C, linewidth=0.4)
        y_end = 0.74 - row_h * (len(arms) - 1) - row_h / 2
        ax.plot([0.02, 0.98], [y_end, y_end], transform=ax.transAxes, color=FT.AXIS_C, linewidth=FT.AX_W)
        ax.text(0.02, y_end - 0.045, 'EIR and GPU usage: means over the routes of the point; n: test routes.',
                ha='left', color=FT.INK_2, **t)
        save(fig, NAMES['c'])


def main():
    PNG_OUT.mkdir(parents=True, exist_ok=True)
    points = load_points()
    panel_ab(points, 'a')
    panel_ab(points, 'b')
    panel_c(points)


if __name__ == '__main__':
    main()
