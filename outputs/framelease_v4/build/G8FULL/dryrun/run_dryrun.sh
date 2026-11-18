#!/bin/bash
# End-to-end dry run of RUNBOOK.md on the scratch tree /tmp/G8FULL/root with SYNTHETIC run directories (DRYRUN.md),
# with the first (cut) analysis freeze of Amendment A13 already entered: the tree's PROTOCOL.md is the project's
# (Amendments A13-A17), its first record and job-status files are byte copies, its first analysis and verification
# are synthetic stand-ins made with the G8CUT tools.
#   cd /home/kang/Desktop/DAC && bash outputs/framelease_v4/build/G8FULL/dryrun/run_dryrun.sh
# One line per step in /tmp/G8FULL/dryrun_steps.log: time, step, expected and actual exit code, wall time.
# Every process: taskset -c 12-15 nice -n 19 ionice -c 3 (this shell is pinned, every child inherits), one BLAS
# thread, no CUDA, one at a time.
set -u
taskset -cp 12-15 $$ > /dev/null && renice -n 19 -p $$ > /dev/null && ionice -c 3 -p $$ || exit 98
SRC=/home/kang/Desktop/DAC
T=/tmp/G8FULL/root
D=$SRC/outputs/framelease_v4/build/G8FULL/dryrun
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' MPLBACKEND=Agg
export G8F_TREE_STANDIN=1      # honoured only outside the project root (g8f_lib.py)
X="taskset -c 12-15 nice -n 19 ionice -c 3"
PYB=$SRC/.conda-unidrive-linux/bin/python
TIME="/usr/bin/time -f TIME_%e_s_maxRSS_%M_KB"
LOG=/tmp/G8FULL/dryrun_steps.log
OUT=/tmp/G8FULL/out
V4=outputs/framelease_v4
S=$V4/build/G8FULL
FIRST=$V4/analysis/final_20261116T091445
VFIRST=$V4/verification/final_20261116T091445
mkdir -p /tmp/G8FULL
rm -rf $OUT /tmp/G8FULL/neg
mkdir -p $OUT /tmp/G8FULL/neg
: > $LOG
T_START=$(date +%s)
step() {        # step NAME EXPECTED CMD...
    local name=$1 want=$2; shift 2
    local t0; t0=$(date +%s.%N)
    "$@" > $OUT/$name.txt 2>&1
    local rc=$?
    local dt; dt=$(echo "$(date +%s.%N) - $t0" | bc)
    local ok=OK; [ "$rc" = "$want" ] || ok=UNEXPECTED
    printf '%s %-34s expected %s exit %s %7.1f s %s\n' "$(date +%H:%M:%S)" "$name" "$want" "$rc" "$dt" "$ok" | tee -a $LOG
}
g8f() { (cd $T && G8_ROOT=$T G8F_TREE_STANDIN=1 bash $T/$S/"$@"); }
py() { (cd $T && $X $TIME $PYB -I -B "$@"); }
newdir() { (cd $T && ls -d $V4/analysis/final_* | grep -v final_20261116T091445); }
first_analysis() {      # the stand-in first analysis: the G8CUT step d on the copied first record (it is cited by A13)
    cd $T && G8_ROOT=$T G8_TREE_FIGURES_NO_RL=1 bash $V4/build/G8CUT/g8_analysis.sh A13
}
first_verification() {  # the stand-in first verifications (the registered verifiers, as G8CUT step e runs them)
    cd $T && mkdir -p $V4/verification && \
    $X $TIME $PYB -I -B framelease_v4/analysis/verify_independent.py --queue $V4/queue_p4 \
        --analysis-freeze $FIRST/analysis_freeze.json --agg $FIRST/agg_p4 --analysis $FIRST/analysis --out $VFIRST
    [ $? -le 1 ] || return 2
    $X $TIME $PYB -I -B framelease_v4/analysis/verify_table1_extra.py --analysis-freeze $FIRST --queue $V4/queue_p4 \
        --agg $FIRST/agg_p4 --analysis $FIRST/analysis --out ${VFIRST}_table1_extra
    [ $? -le 1 ] || return 2
    $X $TIME $PYB -I -B $V4/build/AMEND2/a10r7b/f1/f1_class_report.py ${VFIRST}_table1_extra \
        --out ${VFIRST}_table1_extra_f1_class.json
}
neg_first_record() {    # the first record releases its 127 jobs and none of the 505 runs of Amendment A17
    cd $T && $X $TIME $PYB -I -B framelease_v4/analysis/aggregate_v4.py --queue $V4/queue_p4 \
        --specs $V4/test_jobs/FULL --rl-freeze $V4/rl_freeze/rl_freeze.json --tuning-freeze $V4/tuning/selection.json \
        --analysis-freeze $FIRST/analysis_freeze.json --required-job-files $FIRST/required_job_files.json \
        --out /tmp/G8FULL/neg/first_record_agg || return 2
    $X $PYB -I -B -c "
import csv, json, collections, sys
rec = json.load(open('$FIRST/analysis_freeze.json'))
c = collections.Counter()
for r in csv.DictReader(open('/tmp/G8FULL/neg/first_record_agg/runs.csv')):
    side = 'new' if rec['jobs'][r['job']]['outcome'] == 'cut' else 'first'
    c[side + ' ' + (r.get('guard_note') or '').split(':')[0]] += 1
print(dict(c))
sys.exit(0 if c == {'first released': 127, 'new withheld': 505} else 1)"
}
neg_two_dirs() {        # two new final_* directories: the check refuses
    mkdir $T/$V4/analysis/final_29991231T000000 $T/$V4/analysis/final_29991231T000001
    g8f g8f_check.sh stopped; local rc=$?
    rmdir $T/$V4/analysis/final_29991231T000000 $T/$V4/analysis/final_29991231T000001
    return $rc
}
neg_first_changed() {   # one byte appended to the first record: 'first' refuses; restored afterwards
    local f=$T/$FIRST/analysis_freeze.json
    cp -p $f /tmp/G8FULL/neg/first_record.bak && printf ' ' >> $f
    py $S/g8f_lib.py first; local rc=$?
    cp -p /tmp/G8FULL/neg/first_record.bak $f
    py $S/g8f_lib.py first > /dev/null || return 9
    return $rc
}
neg_resolution() {      # tampered copies of the second verify_table1_extra.py output: the resolution rule stops
    local v=$1 F VX d
    F=$(newdir); VX=$V4/verification/${F##*/}_table1_extra
    d=$(cd $T && $X $PYB -I -B $D/tamper_verify.py $v $VX) || return 8
    py $V4/build/AMEND2/a10r7b/f1/f1_class_report.py $d --out /tmp/G8FULL/neg/report_$v.json || return 7
    (cd $T && G8F_TREE_STANDIN=1 $X $PYB -I -B $S/g8f_lib.py resolution --name A99 --verify-dir $d \
        --class-report /tmp/G8FULL/neg/report_$v.json --dir $F --extra-name A98)
    local rc=$?
    [ ! -e $T/$S/entries/A99_spec.json ] || return 6
    return $rc
}
registration_verify_tree() { (cd $T && $X $PYB -I -B framelease_v4/protocol/registration.py --verify); }

step build_tree 0 $X $PYB -I -B $D/build_tree.py --fresh
step synthetic_cut 0 bash -c "cd $T && $X $PYB -I -B $D/make_runs.py --stage cut"
step link_p2_sources 0 $X $PYB -I -B $D/build_tree.py --link-p2-sources
step first_analysis_standin 0 first_analysis
step first_verification_standin 0 first_verification
step synthetic_a17_pending 0 bash -c "cd $T && $X $PYB -I -B $D/make_runs.py --stage a17_pending"
step check_pending 3 g8f g8f_check.sh
step synthetic_a17_final 0 bash -c "cd $T && $X $PYB -I -B $D/make_runs.py --stage a17_final"
step check_final 0 g8f g8f_check.sh
step NEG_freeze_before_stop 2 g8f g8f_freeze.sh
step NEG_first_record_new_runs 0 neg_first_record
step stop 0 g8f g8f_stop.sh
step stop_again 0 g8f g8f_stop.sh
step NEG_two_new_dirs 2 neg_two_dirs
step NEG_first_record_changed 2 neg_first_changed
step freeze 0 g8f g8f_freeze.sh
step freeze_again 0 g8f g8f_freeze.sh
step apply_A18 0 g8f g8f_apply.sh A18 "$(newdir)"
step freeze_after_entry 0 g8f g8f_freeze.sh
step analysis 0 env G8_TREE_FIGURES_NO_RL=1 bash -c "cd $T && G8_ROOT=$T G8F_TREE_STANDIN=1 bash $T/$S/g8f_analysis.sh A18"
step analysis_again 0 env G8_TREE_FIGURES_NO_RL=1 bash -c "cd $T && G8_ROOT=$T G8F_TREE_STANDIN=1 bash $T/$S/g8f_analysis.sh A18"
step verify 0 g8f g8f_verify.sh A18
step NEG_resolution_A_other_row 3 neg_resolution A
step NEG_resolution_B_value_row 3 neg_resolution B
step NEG_resolution_C_rcond_defined 3 neg_resolution C
step apply_A19 0 g8f g8f_apply.sh A19
step apply_A20 0 g8f g8f_apply.sh A20
step apply_A21 0 g8f g8f_apply.sh A21
step verify_after_entries 0 g8f g8f_verify.sh A18
step figs 0 g8f g8f_figs.sh A18
step registration_verify_tree 0 registration_verify_tree
T_END=$(date +%s); echo "total $(( T_END - T_START )) s" | tee -a $LOG
echo "dry run done: $LOG ($(grep -c UNEXPECTED $LOG) unexpected)"
