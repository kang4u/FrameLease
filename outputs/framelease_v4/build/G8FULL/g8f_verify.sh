#!/bin/bash
# G8FULL step e (RUNBOOK.md Sec. 8): the independent verifications of the second analysis, for the INDEPENDENT session
# (Sec. 9.12; Amendment A10 use rule 4; Amendment A11 use rules 1-3 with the resolution rule of Amendment A16,
# Amendment A17). Reads the second record, queue_p4 and the run directories it names, and the outputs of
# g8f_analysis.sh; writes outputs/framelease_v4/verification/final_<stamp>{,_table1_extra,_table1_extra_f1_class.json}
# and the entry files entries/<A19|A20|A21>_{entry.md,spec.json}.
#   cd /home/kang/Desktop/DAC && bash outputs/framelease_v4/build/G8FULL/g8f_verify.sh NAME
# NAME: the amendment id of the second freeze entry (A18). The verifiers take --agg final_<stamp>/agg_p4 (Amendment A16,
# "Aggregation path"); the class report runs only when f1_class_report.py is at the sha256 Amendment A11 cites. Entry
# ids: N1 = the next free id (A19, verify_independent.py), N1+1 (A20, verify_table1_extra.py and the class report),
# N1+2 (A21, the resolution entry: written only when every unexplained row is an R_cond 0/0 pairing-status row).
# Exit 0 when every step ran (verdicts in the logs; resolution written or not needed), 3 when unexplained rows fall
# outside the resolution rule (entries N1, N1+1 written, no resolution entry: resolve by hand), 2 at a failure.
source "${BASH_SOURCE%/*}/g8f_common.sh"
NAME=${1:?amendment id of the second freeze entry}
F=$(new_dir) || exit 2
STAMP=${F##*/}
VD=$V4/verification/$STAMP
VX=${VD}_table1_extra
CR=${VD}_table1_extra_f1_class.json
seal_ok || exit 2
run post_check $PY -I -B $LIB post --dir $F --name $NAME || exit 4
[ -e $F/analysis/SHA256SUMS ] || { echo "no analysis in $F (g8f_analysis.sh first)"; exit 2; }
if [ ! -e $VD/SHA256SUMS ]; then
    run verify_independent $PY -I -B framelease_v4/analysis/verify_independent.py --queue $Q4 \
        --analysis-freeze $F/analysis_freeze.json --agg $F/agg_p4 --analysis $F/analysis --out $VD
    rc=$?; [ $rc -le 1 ] || { tail -20 "$(lastlog verify_independent)"; exit 2; }
fi
$P -c "import json,sys; d=json.load(open(sys.argv[1])); print('verify_independent:', d.get('status'), d.get('verdict'))" \
    $VD/verification.json
if [ ! -e $VX/SHA256SUMS ]; then
    run verify_table1_extra $PY -I -B framelease_v4/analysis/verify_table1_extra.py --analysis-freeze $F \
        --queue $Q4 --agg $F/agg_p4 --analysis $F/analysis --out $VX
    rc=$?; [ $rc -le 1 ] || { tail -20 "$(lastlog verify_table1_extra)"; exit 2; }
fi
$P -c "import json,sys; d=json.load(open(sys.argv[1])); print('verify_table1_extra:', d.get('status'), d.get('verdict'))" \
    $VX/table1_extra.json
$P $LIB f1-ok || { echo "the class report does not run"; exit 2; }
[ -e $CR ] || run f1_class_report $PY -I -B $A2/f1/f1_class_report.py $VX --out $CR || exit 2
$P -c "import json,sys; d=json.load(open(sys.argv[1])); print('class report:', d.get('outcome'), '| release',
d.get('release'), '|', d.get('differences_by_class'))" $CR
if $P $LIB entered --out $VD/verification.json > /dev/null; then
    echo "the results are entered already (verification.json cited in Sec. 13.2): no entry files written"
    exit 0
fi
N1=$($P $LIB next-name)
N2=A$(( ${N1#A} + 1 ))
N3=A$(( ${N1#A} + 2 ))
run entry_verify $PY -I -B $LIB result-entry --kind verify --name $N1 --verify-dir $VD --dir $F --freeze-name $NAME || exit 2
run entry_extra $PY -I -B $LIB result-entry --kind extra --name $N2 --verify-dir $VX --dir $F --freeze-name $NAME \
    --class-report $CR || exit 2
rm -f $HERE/entries/${N3}_entry.md $HERE/entries/${N3}_spec.json $HERE/entries/${N3}_rows.json
run resolution $PY -I -B $LIB resolution --name $N3 --verify-dir $VX --class-report $CR --dir $F --extra-name $N2
rrc=$?
grep -E '^(RESOLUTION|  )' "$(lastlog resolution)" | head -45
[ $rrc -eq 0 ] || [ $rrc -eq 3 ] || exit 2
ORDER="$N1 $N2"
[ -e $HERE/entries/${N3}_spec.json ] && ORDER="$ORDER $N3"
for n in $ORDER; do
    run applier_check_$n $PY -I -B $A2/apply_entry_stream.py $HERE/entries/${n}_spec.json || {
        tail -5 "$(lastlog applier_check_$n)"; exit 2; }
    grep -h 'check: pre-checks passed' "$(lastlog applier_check_$n)"
done
echo "ENTRIES (apply in this order, after reading the results): $(for n in $ORDER; do printf 'bash %s/g8f_apply.sh %s; ' $HERE $n; done)"
[ $rrc -eq 0 ] || { echo "RESOLUTION STOP: unexplained rows outside the rule of Amendment A16 (log $(lastlog resolution))"; exit 3; }
