#!/bin/bash
# Reviewer's rerun of the step-2 test logs on the project tree, read only (the scratch layout breaks the path-based
# registration checks of the guard: route_split.json resolves through the symlink outside the scratch root). Same
# commands as APPLY_PLAN.md Sec. 4 (E4 file set for the analysis log) and OP_spec.json; logs only under
# /tmp/AMEND3_review/testlogs_real/. One process at a time.
set -u -o pipefail
REAL=/home/kang/Desktop/DAC
OUT=/tmp/AMEND3_review/testlogs_real
rm -rf "$OUT"; mkdir -p "$OUT"
touch "$OUT/.ref_start"
cd "$REAL" || exit 2
source linux/env.sh
export CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PYT=(taskset -c 12-15 nice -n 19 ionice -c 3 /usr/bin/time -v .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider)
t() {  # name, args...
    local n="$1"; shift
    local s; s=$(date +%s)
    "${PYT[@]}" "$@" > "$OUT/$n.log" 2> "$OUT/$n.time"
    echo "$n exit $? wall $(( $(date +%s) - s )) s maxrss $(grep 'Maximum resident' "$OUT/$n.time" | awk '{print $NF}') KB | $(grep -E '[0-9]+ (passed|failed|error)' "$OUT/$n.log" | tail -1)" >> "$OUT/summary.txt"
}
t pytest_analysis framelease_v4/analysis/tests/test_{aggregate_v4,commit_audit,extra_metrics,interim_guard,manipulation}.py \
    framelease_v4/arms/tests/test_metrics_realized_keys.py
t pytest_analysis_collect --collect-only -q framelease_v4/analysis/tests/test_{aggregate_v4,commit_audit,extra_metrics,interim_guard,manipulation}.py \
    framelease_v4/arms/tests/test_metrics_realized_keys.py
t pytest_analysis_dir_collect --collect-only -q framelease_v4/analysis/tests framelease_v4/arms/tests/test_metrics_realized_keys.py
t pytest_arms_ext framelease_v4/arms_ext/tests
t pytest_protocol_tools framelease_v4/protocol/tests/test_{p2_jobs,p2_check,p3_rl,stress_bench,check_smoke,check_smoke_ext,fl_full_qnet_agent,test_jobs,test_freeze}.py
t pytest_phase_driver -rA framelease_v4/protocol/tests/test_phase_driver.py
t pytest_review_phase -rA outputs/framelease_v4/build/PHASE/review/test_review_phase.py
echo "done $(date -Iseconds)" >> "$OUT/summary.txt"
