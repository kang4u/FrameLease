#!/bin/bash
# G8CUT step e (RUNBOOK.md Sec. 8): the independent verification, for the INDEPENDENT session (Sec. 9.12; Amendment
# A10 use rule 4; Amendment A11 use rules 1-3). Reads the record, queue_p4 and the run directories it names, and the
# outputs of g8_analysis.sh; writes outputs/framelease_v4/verification/final_<stamp>{,_table1_extra,
# _table1_extra_f1_class.json} and the entry files entries/<A14|A15>_{entry.md,spec.json}.
#   cd /home/kang/Desktop/DAC && bash outputs/framelease_v4/build/G8CUT/g8_verify.sh NAME
# NAME: the amendment id of the freeze entry (A13). The class report runs only when f1_class_report.py is at the
# sha256 that Amendment A11 cites. Exit 0 when every step ran (verdicts in the logs), 2 at a failure.
source "${BASH_SOURCE%/*}/g8_common.sh"
NAME=${1:?amendment id of the freeze entry}
F=$(final_dir) || exit 2
STAMP=${F##*/}
VD=$V4/verification/$STAMP
VX=${VD}_table1_extra
CR=${VD}_table1_extra_f1_class.json
seal_ok || exit 2
run post_check $PY -I -B $LIB post --dir $F --name $NAME || exit 4
[ -e $F/analysis/SHA256SUMS ] || { echo "no analysis in $F (g8_analysis.sh first)"; exit 2; }
if [ ! -e $VD/SHA256SUMS ]; then
    run verify_independent $PY -I -B framelease_v4/analysis/verify_independent.py --queue $Q4 \
        --analysis-freeze $F/analysis_freeze.json --agg $F/agg_p4 --analysis $F/analysis --out $VD
    rc=$?; [ $rc -le 1 ] || { tail -20 "$(ls -t $LOGS/verify_independent.*.log | head -1)"; exit 2; }
fi
$P -c "import json,sys; d=json.load(open(sys.argv[1])); print('verify_independent:', d.get('status'), d.get('verdict'))" \
    $VD/verification.json
if [ ! -e $VX/SHA256SUMS ]; then
    run verify_table1_extra $PY -I -B framelease_v4/analysis/verify_table1_extra.py --analysis-freeze $F \
        --queue $Q4 --agg $F/agg_p4 --analysis $F/analysis --out $VX
    rc=$?; [ $rc -le 1 ] || { tail -20 "$(ls -t $LOGS/verify_table1_extra.*.log | head -1)"; exit 2; }
fi
$P -c "import json,sys; d=json.load(open(sys.argv[1])); print('verify_table1_extra:', d.get('status'), d.get('verdict'))" \
    $VX/table1_extra.json
F1=$A2/f1/f1_class_report.py
F1SHA=$(sha256sum $F1 | cut -c1-64)
awk '/^\*\*Amendment A11[,:.]? /{a=1} /^\*\*Amendment A1[2-9][,:.]? /{a=0} a' framelease_v4/PROTOCOL.md | grep -q "$F1SHA" \
    || { echo "$F1 (sha256 $F1SHA) is not the file Amendment A11 cites: the class report does not run"; exit 2; }
[ -e $CR ] || run f1_class_report $PY -I -B $F1 $VX --out $CR || exit 2
$P -c "import json,sys; d=json.load(open(sys.argv[1])); print('class report:', d.get('outcome'), '| release', d.get('release'))" $CR
N1=$($PY $LIB next-name)
run entry_verify $PY -I -B $LIB result-entry --kind verify --name $N1 --verify-dir $VD || exit 2
N2=A$(( ${N1#A} + 1 ))
run entry_extra $PY -I -B $LIB result-entry --kind extra --name $N2 --verify-dir $VX --class-report $CR || exit 2
echo "ENTRIES: bash $HERE/g8_apply.sh $N1   then   bash $HERE/g8_apply.sh $N2"
