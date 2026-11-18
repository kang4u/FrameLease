#!/bin/bash
# G8FULL steps c1-c2 (RUNBOOK.md Secs. 5-6): the second analysis-freeze record (trigger all_final, Amendment A17) and
# its dated entry.
#   cd /home/kang/Desktop/DAC && bash outputs/framelease_v4/build/G8FULL/g8f_freeze.sh
# 1. g8f_lib.py check --expect stopped must be READY (every job final, runner exited, queue_p4/STOP, first freeze
#    unchanged, at most one new final_* directory) and test_freeze.py --verify must pass;
# 2. aggregate_v4.py --write-freeze-record (no --cut-amendment; never --arm-summary, never --analysis-freeze) into a NEW
#    outputs/framelease_v4/analysis/final_<stamp>/ next to final_20261116T091445; a new final_<stamp>/ left without a
#    record by an interrupted run is redone there with --force; one with a record is never rewritten;
# 3. required_job_files.json (the six queue copies at their G6 sha256);
# 4. g8f_lib.py record: trigger all_final, 632 final jobs, job files, code, SHA256SUMS, guarded aggregation, no
#    collision with the first freeze, the 127 jobs of the first record unchanged;
# 5. g8f_lib.py entry: entries/<A18>_entry.md + _spec.json (the next free amendment id after A17);
# 6. g8f_lib.py simulate and apply_entry_stream.py in check mode.
# Nothing is entered here: g8f_apply.sh <name> <dir> applies the entry. Exit 0 ready to apply (or entered already).
source "${BASH_SOURCE%/*}/g8f_common.sh"
seal_ok || exit 2
run g8f_check_stopped $PY -I -B $LIB check --expect stopped
rc=$?
grep -E '^CHECK' "$(lastlog g8f_check_stopped)"
[ $rc -eq 0 ] || { echo "not READY: see $(lastlog g8f_check_stopped)"; exit $rc; }
F=$(new_dir 2>/dev/null)
if [ -z "$F" ]; then
    run test_freeze_verify $PY -I -B framelease_v4/protocol/test_freeze.py --verify --jobs-dir $V4/test_jobs \
        --rl-freeze $RL_FREEZE --selection $TUNING --stress-dir $V4/stress --out-dir $V4/test_freeze \
        --queue-dir $Q4/jobs.d || { tail -4 "$(lastlog test_freeze_verify)"; exit 2; }
    F=$V4/analysis/final_$(date +%Y%m%dT%H%M%S)
    [ "$F" != "$FIRST" ] && [ ! -e "$F" ] || { echo "$F exists"; exit 2; }
    FORCE=
else
    echo "resuming in $F"
    if [ -e "$F/analysis_freeze.json" ]; then FORCE=skip; else FORCE=--force; fi
fi
if [ "$FORCE" != skip ]; then
    run aggregate_freeze $PY -I -B framelease_v4/analysis/aggregate_v4.py --queue $Q4 --specs $V4/test_jobs/FULL \
        --rl-freeze $RL_FREEZE --tuning-freeze $TUNING --write-freeze-record $F/analysis_freeze.json \
        --out $F $FORCE || { tail -15 "$(lastlog aggregate_freeze)"; exit 2; }
    L=$(lastlog aggregate_freeze)
    grep -E '^(analysis-freeze record|interim guard|outcomes|missing reasons|commit audit)' "$L" | cut -c1-240
    line=$(grep '^analysis-freeze record ' "$L")
    want=$(echo "$line" | sed -n 's/.*: sha256 \([0-9a-f]\{64\}\), .*/\1/p')
    have=$(sha256sum "$F/analysis_freeze.json" | cut -c1-64)
    [ -n "$want" ] && [ "$want" = "$have" ] || { echo "the record sha256 $have is not the one reported ($want)"; exit 2; }
fi
[ -e "$F/required_job_files.json" ] || run required $PY -I -B $LIB required --out $F/required_job_files.json || exit 2
run record_check $PY -I -B $LIB record --dir $F || { tail -30 "$(lastlog record_check)"; exit 2; }
grep -E '"(outcomes|trigger|cut_amendment|sha256|frozen)"|^RECORD' "$(lastlog record_check)" | head -8
if $P $LIB entered --out $F/analysis_freeze.json > /dev/null; then
    echo "the record is entered already: bash $HERE/g8f_apply.sh <its amendment id> $F runs the post-check"
    exit 0
fi
NAME=$($P $LIB next-name)
run entry $PY -I -B $LIB entry --dir $F --name $NAME || { tail -5 "$(lastlog entry)"; exit 2; }
grep -h "line problems" "$(lastlog entry)"
run simulate $PY -I -B $LIB simulate --dir $F --name $NAME || { tail -20 "$(lastlog simulate)"; exit 2; }
grep -E '^SIMULATE' "$(lastlog simulate)"
run applier_check $PY -I -B $A2/apply_entry_stream.py $HERE/entries/${NAME}_spec.json || {
    tail -5 "$(lastlog applier_check)"; exit 2; }
grep -h 'check: pre-checks passed' "$(lastlog applier_check)"
echo "READY TO APPLY: bash $HERE/g8f_apply.sh $NAME $F"
