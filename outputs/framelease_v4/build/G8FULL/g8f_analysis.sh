#!/bin/bash
# G8FULL step d (RUNBOOK.md Sec. 7): the registered analysis on the entered second analysis-freeze record (Amendments
# A3, A10; exactly the commands of G8CUT step d), into the NEW outputs/framelease_v4/analysis/final_<stamp>/:
#   agg_p4/     aggregate_v4.py over queue_p4 with --analysis-freeze and --required-job-files (the released rows) and
#               --arm-summary test (the verifiers compare arm_summary.csv)
#   agg_p1/     aggregate_v4.py over queue_p1 (P1-0 and P1, training routes) and agg_p2/ over queue_p2 (P2): the
#               commit audit of every phase that H5 requires (Sec. 9.5; analyze_v4.H5_PHASES)
#   analysis/   analyze_v4.py --agg agg_p4 agg_p1 agg_p2 --analysis-freeze --required-job-files --rl-freeze --offline --s3
#   coverage/   prop1_coverage.py with the cited tuning freeze (L* = B0 and the fl_risk point E5), 32 VAL clips
#   figures/    figures_tables.py --require-registered with every source (offline, coverage, RL freeze, S1, S2,
#               S2 relative, S3, D1 summary)
#   ANALYSIS_OUTPUTS.sha256   sha256 of every file below final_<stamp>/ except itself (paths from the project root,
#               sha256sum -c from the root); its temporary file is written in G8FULL/logs and renamed into place, so
#               the list never names it (Amendment A16, correction 2); every line is checked after the write
#   cd /home/kang/Desktop/DAC && bash outputs/framelease_v4/build/G8FULL/g8f_analysis.sh NAME
# NAME: the amendment id of the second freeze entry (A18). Refuses (exit 4) unless g8f_lib.py post passes. A step whose
# output directory holds SHA256SUMS is skipped (resume); exit 2 at the first failure. final_20261116T091445 is never
# written.
source "${BASH_SOURCE%/*}/g8f_common.sh"
NAME=${1:?amendment id of the second freeze entry}
F=$(new_dir) || exit 2
[ "$F" != "$FIRST" ] || exit 2
REC=$F/analysis_freeze.json
REQ=$F/required_job_files.json
seal_ok || exit 2
run post_check $PY -I -B $LIB post --dir $F --name $NAME || { echo "the record is not valid yet"; exit 4; }
RAN=0
step() {        # step DIR LABEL CMD...: skipped when DIR/SHA256SUMS exists
    local d=$1 label=$2; shift 2
    if [ -e "$d/SHA256SUMS" ]; then echo "[$label] $d exists: skipped"; return 0; fi
    RAN=1
    run "$label" "$@" || { tail -25 "$(lastlog $label)"; exit 2; }
}
step $F/agg_p4 aggregate_p4 $PY -I -B framelease_v4/analysis/aggregate_v4.py --queue $Q4 --specs $V4/test_jobs/FULL \
    --rl-freeze $RL_FREEZE --tuning-freeze $TUNING --analysis-freeze $REC --required-job-files $REQ \
    --arm-summary test --out $F/agg_p4
step $F/agg_p1 aggregate_p1 $PY -I -B framelease_v4/analysis/aggregate_v4.py --queue $V4/queue_p1 \
    --specs $V4/p1_jobs/FULL --out $F/agg_p1
step $F/agg_p2 aggregate_p2 $PY -I -B framelease_v4/analysis/aggregate_v4.py --queue $V4/queue_p2 \
    --specs $V4/p2_jobs/FULL --out $F/agg_p2
step $F/analysis analyze $PY -I -B framelease_v4/analysis/analyze_v4.py --agg $F/agg_p4 --agg $F/agg_p1 \
    --agg $F/agg_p2 --analysis-freeze $REC --required-job-files $REQ --rl-freeze $RL_FREEZE --offline $OFFLINE \
    --s3 $S3 --out $F/analysis
$P -c "import json,sys; d=json.load(open(sys.argv[1])); print('analysis status', d['status'], '| H5', d['h5']['label'],
'| development reasons', d.get('development'))" $F/analysis/analysis.json
step $F/coverage coverage $PY -I -B framelease_v4/analysis/prop1_coverage.py --tuning-freeze $TUNING --out $F/coverage
RLARGS="--rl-freeze $RL_FREEZE --require-registered"
if [ "$G8_ROOT" != /home/kang/Desktop/DAC ] && [ "${G8_TREE_FIGURES_NO_RL:-0}" = 1 ]; then
    RLARGS=     # scratch tree only: the RL freeze names networks by the project's absolute paths (DRYRUN.md)
fi
step $F/figures figures $PY -I -B framelease_v4/analysis/figures_tables.py --out $F/figures --analysis $F/analysis \
    --offline $OFFLINE --coverage $F/coverage --s1 $S1 --s2 $S2 --s2-relative $S2R --s3 $S3 --d1 $D1 $RLARGS
$P -c "import json,sys; d=json.load(open(sys.argv[1])); print('figures status', d['status'], '| reasons',
d.get('development'), '| numbers', len(d['numbers']))" $F/figures/numbers.json
if [ $RAN = 0 ] && [ -e $F/ANALYSIS_OUTPUTS.sha256 ]; then
    run outputs_list_check $PY -I -B $LIB manifest-check --dir $F || { tail -3 "$(lastlog outputs_list_check)"; exit 2; }
else
    run outputs_list $PY -I -B $LIB manifest --dir $F || { tail -3 "$(lastlog outputs_list)"; exit 2; }
fi
grep -h 'ANALYSIS_OUTPUTS' "$(ls -t $LOGS/outputs_list*.log | head -1)" | tail -1
echo "ANALYSIS DONE: $F ($(wc -l < $F/ANALYSIS_OUTPUTS.sha256) files in ANALYSIS_OUTPUTS.sha256)"
