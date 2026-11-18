#!/bin/bash
# G8CUT step b2-c1 (RUNBOOK.md Secs. 5-6): the analysis-freeze record under Amendment A12 and its dated entry.
#   cd /home/kang/Desktop/DAC && bash outputs/framelease_v4/build/G8CUT/g8_freeze.sh
# 1. g8_lib.py check --expect registered must be READY (after g8_swap.sh): every kept job final, no runner, the
#    registered job files in jobs.d, Amendments A10-A12 entered, no final_* directory yet;
# 2. aggregate_v4.py --write-freeze-record --cut-amendment A12 into outputs/framelease_v4/analysis/final_<stamp>/
#    (never --arm-summary, never --analysis-freeze); a final_<stamp>/ left without a record by an interrupted run is
#    redone there with --force; one with a record is never rewritten (steps 3-6 are then checked again);
# 3. required_job_files.json (the six queue copies at their G6 sha256);
# 4. g8_lib.py record: trigger cut / A12, 127 final + 505 cut, job files, code, SHA256SUMS, guarded aggregation;
# 5. g8_lib.py entry: entries/<A13>_entry.md + _spec.json (the next free amendment id after A11 and A12);
# 6. g8_lib.py simulate (scratch copy: both parsers, load_freeze accepts the record once the entry is sealed) and
#    apply_entry_stream.py in check mode ("check: pre-checks passed").
# Nothing is entered here: g8_apply.sh <name> applies the entry. Exit 0 ready to apply.
source "${BASH_SOURCE%/*}/g8_common.sh"
seal_ok || exit 2
F=$(final_dir 2>/dev/null)
if [ -z "$F" ]; then
    run g8_check_registered $PY -I -B $LIB check --expect registered || { echo "not READY: see the log"; exit 3; }
    F=$V4/analysis/final_$(date +%Y%m%dT%H%M%S)
    FORCE=
else
    echo "resuming in $F"
    if [ -e "$F/analysis_freeze.json" ]; then FORCE=skip; else FORCE=--force; fi
fi
if [ "$FORCE" != skip ]; then
    run aggregate_freeze $PY -I -B framelease_v4/analysis/aggregate_v4.py --queue $Q4 --specs $V4/test_jobs/FULL \
        --rl-freeze $RL_FREEZE --tuning-freeze $TUNING --write-freeze-record $F/analysis_freeze.json \
        --cut-amendment A12 --out $F $FORCE || exit 2
    L=$(ls -t $LOGS/aggregate_freeze.*.log | head -1)
    grep -E '^(analysis-freeze record|interim guard|outcomes|missing reasons|commit audit)' "$L" | cut -c1-240
    line=$(grep '^analysis-freeze record ' "$L")
    want=$(echo "$line" | sed -n 's/.*: sha256 \([0-9a-f]\{64\}\), .*/\1/p')
    have=$(sha256sum "$F/analysis_freeze.json" | cut -c1-64)
    [ -n "$want" ] && [ "$want" = "$have" ] || { echo "the record sha256 $have is not the one reported ($want)"; exit 2; }
fi
[ -e "$F/required_job_files.json" ] || run required $PY -I -B $LIB required --out $F/required_job_files.json || exit 2
run record_check $PY -I -B $LIB record --dir $F || { tail -30 "$(ls -t $LOGS/record_check.*.log | head -1)"; exit 2; }
grep -E '"(outcomes|trigger|cut_amendment|sha256|frozen)"' "$(ls -t $LOGS/record_check.*.log | head -1)" | head -8
NAME=$($PY $LIB next-name)
case "$NAME" in A11|A12) echo "next amendment id $NAME: Amendment A11 is not entered"; exit 3;; esac
run entry $PY -I -B $LIB entry --dir $F --name $NAME || exit 2
run simulate $PY -I -B $LIB simulate --dir $F --name $NAME || { tail -20 "$(ls -t $LOGS/simulate.*.log | head -1)"; exit 2; }
run applier_check $PY -I -B $A2/apply_entry_stream.py $HERE/entries/${NAME}_spec.json || {
    tail -5 "$(ls -t $LOGS/applier_check.*.log | head -1)"; exit 2; }
grep -h 'check: pre-checks passed' "$(ls -t $LOGS/applier_check.*.log | head -1)"
echo "READY TO APPLY: bash $HERE/g8_apply.sh $NAME $F"
