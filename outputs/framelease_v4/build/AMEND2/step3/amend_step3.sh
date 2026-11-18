#!/bin/bash
# Step 3 of outputs/framelease_v4/build/AMEND2/APPLY_PLAN2.md Sec. 3: Amendments A3, A9, A7 (A7b), A4 and the
# operational addition of the phase driver in ONE transaction (one manifest, one seal), with the pre-checks of step 1
# and the post-checks of step 4. The logic is in step3_txn.py (same directory); its input is step3_spec.json.
#
#   cd /home/kang/Desktop/DAC
#   O=outputs/framelease_v4/build/AMEND2/step3/step3_$(date +%Y%m%dT%H%M%S).out
#   setsid nohup taskset -c 12-15 nice -n 19 ionice -c 3 bash outputs/framelease_v4/build/AMEND2/step3/amend_step3.sh \
#       > "$O" 2>&1 < /dev/null &
#   (then wait for the line "PASS: ..." or "STOP: ..." in $O; RUNBOOK.md step 3)
#
# Options: --precheck-only (step 1 only; writes nothing outside the transaction directory)
#          --datetime 'YYYY-MM-DD HH:MM' (the one time stamp of the five entries, Beijing time; default: the time the
#            lock is taken; refused when earlier than the latest time stamp of Sec. 13.2 or later than now)
#          --work DIR (transaction directory; default outputs/framelease_v4/build/AMEND2/step3/txn_<time>)
#          --root DIR (a scratch copy for the simulation; default the project)
#          --lock-timeout S (default 600)
# 1. pre-check, no lock: step3_txn.py precheck. Any problem: STOP, nothing changed.
# 3. under framelease_v4/.protocol.lock (flock -w 600 on the lock file, which stays empty): step3_txn.py locked. From
#    the lock on, this script ignores SIGINT, SIGTERM and SIGHUP (so does the log process from the start): a signal to
#    the whole process group reaches the helper only, which restores the sealed state before the seal and ignores
#    signals from the seal on; this script then prints its PASS/STOP line and releases the lock. Any failure before the
#    seal restores PROTOCOL.md and MANIFEST.sha256 from the copies in the transaction directory and verifies both
#    seals: STOP, nothing applied. The lock is released after registration.py --verify.
# 4. post-check, no lock: step3_txn.py postcheck.
# The last line is "PASS: ..." or "STOP: ..."; the exit code is that of the failing step (0 = PASS). The helper also
# writes every message into <transaction directory>/step3_txn.log itself; the journal is journal.json there.
set -u -o pipefail
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
HERE="$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")" && pwd)"
ROOT=/home/kang/Desktop/DAC
DT=''
WORK=''
LOCK_TIMEOUT=600
ONLY_PRE=0
while [ $# -gt 0 ]; do
    case "$1" in
        --root) ROOT="$2"; shift 2 ;;
        --datetime) DT="$2"; shift 2 ;;
        --work) WORK="$2"; shift 2 ;;
        --lock-timeout) LOCK_TIMEOUT="$2"; shift 2 ;;
        --precheck-only) ONLY_PRE=1; shift ;;
        *) echo "STOP: unknown option $1"; exit 2 ;;
    esac
done
ROOT="$(cd -- "$ROOT" && pwd -P)" || { echo "STOP: no root"; exit 2; }
if [ -n "$DT" ] && ! [[ "$DT" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}$ ]]; then
    echo "STOP: --datetime must be 'YYYY-MM-DD HH:MM'"; exit 2
fi
STAMP="$(date +%Y%m%dT%H%M%S)"
WORK="${WORK:-$ROOT/outputs/framelease_v4/build/AMEND2/step3/txn_$STAMP}"
mkdir -p "$WORK/precheck" || { echo "STOP: cannot create $WORK"; exit 2; }
WORK="$(cd -- "$WORK" && pwd -P)"
# the log process ignores the signals of the group and keeps writing the log file when its own output pipe breaks
exec > >(trap '' INT TERM HUP; exec tee -p -a "$WORK/amend_step3.log") 2>&1
TEE_PID=$!
trap 'exec 1>&- 2>&-; wait "$TEE_PID" 2>/dev/null' EXIT
PY="$ROOT/.conda-unidrive-linux/bin/python"
TXN=(taskset -c 12-15 nice -n 19 ionice -c 3 "$PY" -I -B "$HERE/step3_txn.py")
DTARG=()
[ -n "$DT" ] && DTARG=(--datetime "$DT")
# the step the journal ended at (its top-level "step" key)
journal_step() { sed -n 's/^ "step": "\([a-z_]*\)",\{0,1\}$/\1/p' "$WORK/journal.json" 2>/dev/null | tail -n 1; }
cd "$ROOT" || { echo "STOP: cd $ROOT"; exit 2; }
echo "amend_step3.sh $(date -Iseconds) (pid $$): root $ROOT; transaction directory $WORK"
echo "inputs: step3_txn.py $(sha256sum "$HERE/step3_txn.py" | cut -c1-64),"
echo "        step3_spec.json $(sha256sum "$HERE/step3_spec.json" | cut -c1-64)"

echo "== 1. pre-check (no lock)"
"${TXN[@]}" precheck --root "$ROOT" --work "$WORK/precheck" --txn-root "$(dirname "$WORK")" "${DTARG[@]}"
rc=$?
if [ $rc -ne 0 ]; then
    echo "STOP: pre-check failed (exit $rc); nothing was changed. See $WORK/amend_step3.log"
    exit 1
fi
if [ $ONLY_PRE -eq 1 ]; then
    echo "PASS: pre-check passed (--precheck-only; nothing was changed)"
    exit 0
fi

echo "== 3. locked part (framelease_v4/.protocol.lock, wait up to $LOCK_TIMEOUT s)"
LOCK="$ROOT/framelease_v4/.protocol.lock"
[ -f "$LOCK" ] || { echo "STOP: $LOCK does not exist (nothing was changed)"; exit 1; }
exec 9<"$LOCK" || { echo "STOP: cannot open $LOCK (nothing was changed)"; exit 1; }
if ! flock -w "$LOCK_TIMEOUT" 9; then
    echo "STOP: the protocol lock was not free within $LOCK_TIMEOUT s (another editor); nothing was changed"
    exit 1
fi
trap '' INT TERM HUP PIPE
DT="${DT:-$(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M')}"
echo "lock held $(date -Iseconds); time stamp of the five entries: $DT; from here on this script ignores SIGINT,"
echo "     SIGTERM and SIGHUP (the helper undoes everything on a signal before the seal)"
"${TXN[@]}" locked --root "$ROOT" --work "$WORK" --datetime "$DT"
rc=$?
flock -u 9
exec 9<&-
echo "lock released $(date -Iseconds)"
last="$(journal_step)"
case $rc in
    0) ;;
    1) if [ "$last" = restored ]; then
           echo "STOP: the transaction failed before the seal and was undone: PROTOCOL.md and MANIFEST.sha256 are"
           echo "     restored and both seals verify (journal step 'restored'; nothing applied). Cause: the FAILURE"
           echo "     line in $WORK/amend_step3.log; journal $WORK/journal.json"
       else
           echo "STOP: the locked part stopped before it changed anything (journal step '${last:-none}'; nothing was"
           echo "     changed). Cause: the STOPPED / STOP line in $WORK/amend_step3.log"
       fi
       exit 1 ;;
    2) echo "STOP: the transaction failed before the seal and the restore did not verify (journal step"
       echo "     '${last:-none}'). Do not rerun this script. Read $WORK/journal.json, then (the command takes the"
       echo "     protocol lock itself):"
       echo "     ${TXN[*]} restore --root $ROOT --work $WORK"
       exit 2 ;;
    3) echo "STOP: sealed (the entries are in PROTOCOL.md), but a seal line or a registered file does not verify;"
       echo "     see $WORK/amend_step3.log and $WORK/journal.json"
       exit 3 ;;
    *) echo "STOP: step3_txn.py locked exited $rc (killed?); journal step '${last:-none}'. Do not rerun this script."
       case "$last" in
           sealed|verified|verify_not_clean)
               echo "     The transaction is sealed: run the post-check alone:"
               echo "     ${TXN[*]} postcheck --root $ROOT --work $WORK" ;;
           refused|restored)
               echo "     Nothing is applied (journal $WORK/journal.json)." ;;
           *)
               echo "     Not sealed: restore the sealed state (the command takes the protocol lock itself):"
               echo "     ${TXN[*]} restore --root $ROOT --work $WORK" ;;
       esac
       exit "$rc" ;;
esac

echo "== 4. post-check (no lock)"
"${TXN[@]}" postcheck --root "$ROOT" --work "$WORK"
rc=$?
if [ $rc -ne 0 ]; then
    echo "STOP: post-check failed (exit $rc); the transaction is sealed. See $WORK/amend_step3.log"
    exit 4
fi
echo "PASS: Amendments A3, A9, A7 (A7b), A4 and the operational addition entered at $DT, one manifest, one seal;"
echo "      post-checks passed. Next: update framelease_v4/PIPELINE_STATE.md, then the D1 decision (RUNBOOK.md)."
exit 0
