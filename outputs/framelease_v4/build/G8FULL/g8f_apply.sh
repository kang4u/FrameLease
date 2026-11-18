#!/bin/bash
# G8FULL entry application (RUNBOOK.md Secs. 6, 8, 9): one dated Sec. 13.2 entry of entries/<NAME>_spec.json through the
# registered appliers outputs/framelease_v4/build/AMEND2/a10r7b/apply_locked.sh + apply_entry_stream.py (their RUNBOOK
# Secs. 0 and 1: detached wrapper, exit codes 0 / 92-98), then registration.py --verify and, for the freeze entry, the
# post-check.
#   cd /home/kang/Desktop/DAC && bash outputs/framelease_v4/build/G8FULL/g8f_apply.sh NAME [FINAL_DIR]
# FINAL_DIR given (the freeze entry): g8f_lib.py post (load_freeze accepts the second record with the registered
# PROTOCOL.md, first cited by NAME; the first record stays valid; both parsers). Output:
# outputs/framelease_v4/amendment_<name>/ (apply.out, verify.out, console.txt, attempt_*/). Exit: the wrapper's exit
# code when it is not 0 or 94; else the post-check's.
source "${BASH_SOURCE%/*}/g8f_common.sh"
NAME=$1
F=${2:-}
SPEC=$HERE/entries/${NAME}_spec.json
[ -f "$SPEC" ] || { echo "$SPEC missing"; exit 2; }
O=$V4/amendment_$(echo "$NAME" | tr 'A-Z' 'a-z')
mkdir -p "$O"
if [ "$G8_ROOT" != /home/kang/Desktop/DAC ]; then        # scratch-tree dry run: the tree's applier copy
    export APPLY_ROOT="$G8_ROOT" APPLIER="$G8_ROOT/$A2/apply_entry_stream.py"
fi
if grep -q 'apply_locked: exit 0' "$O/apply.out" 2>/dev/null; then
    echo "$NAME applied already ($O)"
else
    t0=$(date +%s)
    setsid nohup $X bash $A2/apply_locked.sh $SPEC $O > $O/console.txt 2>&1 < /dev/null &
    until grep -q 'apply_locked: exit' $O/console.txt 2>/dev/null; do
        sleep 2
        if [ $(( $(date +%s) - t0 )) -gt 1500 ] && ! pgrep -f "$A2/apply_locked.sh $SPEC" > /dev/null; then
            echo "no 'apply_locked: exit' line and no wrapper process: hand recovery (a10r7b RUNBOOK.md Sec. 1)"
            exit 91
        fi
    done
    rc=$(sed -n 's/.*apply_locked: exit \([0-9]*\).*/\1/p' $O/console.txt | tail -1)
    echo "$(date '+%Y-%m-%d %H:%M:%S') apply_$NAME exit $rc ($(( $(date +%s) - t0 )) s) $O/apply.out" >> "$LOGS/steps.log"
    echo "[apply $NAME] wrapper exit $rc; $O/apply.out"
    grep -E '^(registration|manifest difference|composed|PROTOCOL |STOP|apply_locked)' $O/apply.out | cut -c1-200
    case "$rc" in 0|94) ;; *) echo "not applied: RUNBOOK.md Sec. 6 (exit $rc)"; exit "$rc";; esac
fi
seal_ok || exit 2
if [ -n "$F" ]; then
    run post_$NAME $PY -I -B $LIB post --dir $F --name $NAME
    rc=$?
    grep -E '"(owner|trigger|cut_amendment|registered)"|^POST' "$(lastlog post_$NAME)"
    exit $rc
fi
