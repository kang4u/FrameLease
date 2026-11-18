#!/bin/bash
# Rerun of the reviewer's break cases (review/sim/case_*.sh) against the fixed transaction, on a scratch copy under
# /tmp/AMEND3/rv/ (the reviewer's scripts, copied there with /tmp/AMEND3_review replaced by /tmp/AMEND3/rv and their
# helper directory pointed at the copy; nothing else of them changes). Writes only under /tmp/AMEND3/rv/.
#   taskset -c 12-15 nice -n 19 ionice -c 3 bash outputs/framelease_v4/build/AMEND2/step3/sim/run_review_cases.sh
# AMEND_STEP3_NOW (honoured in a scratch root only) stands for the current time of the time-stamp check, so that the
# reviewer's fixed stamp '2026-11-15 08:30' of the `locked` runs is not in the future before 08:30; cases B4a-b test
# the time stamp itself. Results: /tmp/AMEND3/rv/results.txt (the scripts' own lines, one block per case script).
set -u -o pipefail
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
export AMEND_STEP3_NOW='2026-11-15 23:59'
REAL=/home/kang/Desktop/DAC
S3="$REAL/outputs/framelease_v4/build/AMEND2/step3"
RV=/tmp/AMEND3/rv
P=(taskset -c 12-15 nice -n 19 ionice -c 3)
PY="$REAL/.conda-unidrive-linux/bin/python"
rm -rf "$RV"
mkdir -p "$RV/sim"
cp -p "$S3"/review/sim/* "$RV/sim/"
sed -i 's#/tmp/AMEND3_review#/tmp/AMEND3/rv#g' "$RV"/sim/*
sed -i 's#^RV="\$S3/review"$#RV=/tmp/AMEND3/rv#' "$RV/sim/common.sh"
grep -q '^RV=/tmp/AMEND3/rv$' "$RV/sim/common.sh" || { echo "common.sh: RV line not found"; exit 2; }
OUT="$RV/results.txt"
echo "review cases rerun $(date -Iseconds); step3_txn.py $(sha256sum "$S3/step3_txn.py" | cut -c1-16), amend_step3.sh $(sha256sum "$S3/amend_step3.sh" | cut -c1-16), spec $(sha256sum "$S3/step3_spec.json" | cut -c1-16); AMEND_STEP3_NOW=$AMEND_STEP3_NOW" > "$OUT"
"${P[@]}" bash "$RV/sim/make_scratch_review.sh" "$RV/tree" >> "$OUT" 2>&1
for c in case_00_setup case_b1_twice case_b2_regfile case_b3_partial case_b4_time case_b5_b6 case_b7_groupkill \
         case_b7b_groupkill case_r10_full; do
    echo "=== $c ($(date +%T))" >> "$OUT"
    "${P[@]}" bash "$RV/sim/$c.sh" >> "$OUT" 2>&1
done
echo "=== verify_result.py on R10 ($(date +%T))" >> "$OUT"
"${P[@]}" "$PY" -I -B "$RV/sim/verify_result.py" "$RV/tree" "$RV/runs/R10" >> "$OUT" 2>&1
for c in case_r12_d1 case_s_extra; do
    echo "=== $c ($(date +%T))" >> "$OUT"
    "${P[@]}" bash "$RV/sim/$c.sh" >> "$OUT" 2>&1
done
echo "=== end $(date -Iseconds)" >> "$OUT"
