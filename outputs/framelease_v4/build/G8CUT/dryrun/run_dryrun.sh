#!/bin/bash
# End-to-end dry run of RUNBOOK.md on the scratch tree /tmp/G8CUT/root with SYNTHETIC run directories (DRYRUN.md).
#   cd /home/kang/Desktop/DAC && bash outputs/framelease_v4/build/G8CUT/dryrun/run_dryrun.sh
# One line per step in /tmp/G8CUT/dryrun_steps.log: step, expected and actual exit code, wall time.
# Every process: taskset -c 12-15 nice -n 19 ionice -c 3, one BLAS thread, no CUDA, one at a time.
set -u
SRC=/home/kang/Desktop/DAC
T=/tmp/G8CUT/root
D=$SRC/outputs/framelease_v4/build/G8CUT/dryrun
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' MPLBACKEND=Agg
X="taskset -c 12-15 nice -n 19 ionice -c 3"
PYB=$SRC/.conda-unidrive-linux/bin/python
LOG=/tmp/G8CUT/dryrun_steps.log
OUT=/tmp/G8CUT/out
mkdir -p $OUT
: > $LOG
step() {        # step NAME EXPECTED CMD...
    local name=$1 want=$2; shift 2
    local t0; t0=$(date +%s.%N)
    "$@" > $OUT/$name.txt 2>&1
    local rc=$?
    local dt; dt=$(echo "$(date +%s.%N) - $t0" | bc)
    local ok=OK; [ "$rc" = "$want" ] || ok=UNEXPECTED
    printf '%s %-28s expected %s exit %s %7.1f s %s\n' "$(date +%H:%M:%S)" "$name" "$want" "$rc" "$dt" "$ok" | tee -a $LOG
}
g8() { (cd $T && G8_ROOT=$T bash $T/outputs/framelease_v4/build/G8CUT/"$@"); }
apply_a11() {
    cd $T || return 99
    local A2=outputs/framelease_v4/build/AMEND2/a10r7b O=outputs/framelease_v4/amendment_a11
    mkdir -p $O
    APPLY_ROOT=$T APPLIER=$T/$A2/apply_entry_stream.py setsid nohup $X bash $A2/apply_locked.sh \
        outputs/framelease_v4/build/G8CUT/dryrun/A11_standin_spec.json $O > $O/console.txt 2>&1 < /dev/null &
    until grep -q 'apply_locked: exit' $O/console.txt 2>/dev/null; do sleep 1; done
    cat $O/apply.out
    return "$(sed -n 's/.*apply_locked: exit \([0-9]*\).*/\1/p' $O/console.txt | tail -1)"
}
neg_reduced() {
    cd $T && rm -rf /tmp/G8CUT/neg && $X $PYB -I -B framelease_v4/analysis/aggregate_v4.py \
        --queue outputs/framelease_v4/queue_p4 --specs outputs/framelease_v4/test_jobs/FULL \
        --rl-freeze outputs/framelease_v4/rl_freeze/rl_freeze.json --tuning-freeze outputs/framelease_v4/tuning/selection.json \
        --write-freeze-record /tmp/G8CUT/neg/reduced/analysis_freeze.json --cut-amendment A12 --out /tmp/G8CUT/neg/reduced
}
neg_analysis() {
    cd $T && F=$(ls -d outputs/framelease_v4/analysis/final_*) && $X $PYB -I -B framelease_v4/analysis/analyze_v4.py \
        --agg $F --analysis-freeze $F/analysis_freeze.json --required-job-files $F/required_job_files.json \
        --rl-freeze outputs/framelease_v4/rl_freeze/rl_freeze.json --out /tmp/G8CUT/neg/analysis_on_freeze_agg
}
final() { (cd $T && ls -d outputs/framelease_v4/analysis/final_*); }
verify_tree() { (cd $T && $X $PYB -I -B framelease_v4/protocol/registration.py --verify); }

step build_tree 0 $X $PYB -I -B $D/build_tree.py --fresh
step synthetic_pending 0 bash -c "cd $T && $X $PYB -I -B $D/make_runs.py --stage pending --no-log-attempt"
step check_pending 3 g8 g8_check.sh
step synthetic_final 0 bash -c "cd $T && $X $PYB -I -B $D/make_runs.py --stage final --no-log-attempt"
step check_without_A11 3 g8 g8_check.sh
step apply_A11_standin 0 apply_a11
step check_ready 0 g8 g8_check.sh
step NEG_aggregate_reduced 2 neg_reduced
step swap 0 g8 g8_swap.sh
step swap_again 0 g8 g8_swap.sh
step freeze 0 g8 g8_freeze.sh
step apply_A13 0 g8 g8_apply.sh A13 "$(final)"
step NEG_analyze_freeze_agg 2 neg_analysis
step analysis_1_p2_logs_absent 2 g8 g8_analysis.sh A13
step link_p2_sources 0 $X $PYB -I -B $D/build_tree.py --link-p2-sources
step analysis_2_registered_cmd 2 g8 g8_analysis.sh A13
step analysis_3_tree_no_rl 0 env G8_TREE_FIGURES_NO_RL=1 bash -c "cd $T && G8_ROOT=$T bash $T/outputs/framelease_v4/build/G8CUT/g8_analysis.sh A13"
step verify 0 g8 g8_verify.sh A13
step apply_A14 0 g8 g8_apply.sh A14
step apply_A15 0 g8 g8_apply.sh A15
step registration_verify_tree 0 verify_tree
echo "dry run done: $LOG"
