#!/bin/bash
# G8FULL step f (RUNBOOK.md Sec. 9): the two Desktop Fig. 3 scripts, as parameterized copies (fig3/*_full.py; the
# originals in /home/kang/Desktop/FrameLease_figure_code/fig3_panels/ stay unchanged and keep FINAL =
# final_20261116T091445), against the new final_<stamp>/, into $HERE/fig3_full_<stamp>/ (PNG 300 dpi and PDF; nothing is
# written on the Desktop or into final_<stamp>/), then g8f_lib.py final-check (both freezes, every manifest).
#   cd /home/kang/Desktop/DAC && bash outputs/framelease_v4/build/G8FULL/g8f_figs.sh NAME
# NAME: the amendment id of the second freeze entry (A18). Exit 0 done, 2 a failure.
source "${BASH_SOURCE%/*}/g8f_common.sh"
NAME=${1:?amendment id of the second freeze entry}
F=$(new_dir) || exit 2
STAMP=${F##*/final_}
OUT=$HERE/fig3_full_$STAMP
run post_check $PY -I -B $LIB post --dir $F --name $NAME || exit 4
[ -e $F/figures/numbers.json ] || { echo "no figures in $F (g8f_analysis.sh first)"; exit 2; }
mkdir -p $OUT
run fig3_panels $PY -I -B $HERE/fig3/make_fig3_panels_full.py --root "$G8_ROOT" --final $F --out $OUT || {
    tail -5 "$(lastlog fig3_panels)"; exit 2; }
grep -E 'values equal|wrote' "$(lastlog fig3_panels)"
run fig3ab_table1 $PY -I -B $HERE/fig3/make_fig3ab_table1_full.py --root "$G8_ROOT" --final $F --out $OUT || {
    tail -5 "$(lastlog fig3ab_table1)"; exit 2; }
grep -E 'means equal|wrote' "$(lastlog fig3ab_table1)" | cut -c1-200
(cd $OUT && sha256sum *.png *.pdf > SHA256SUMS)
run final_check $PY -I -B $LIB final-check --dir $F
rc=$?
grep -E '^FINAL CHECK' "$(lastlog final_check)"
echo "FIGURES: $OUT ($(ls $OUT | grep -c -E '\.(png|pdf)$') files)"
exit $rc
