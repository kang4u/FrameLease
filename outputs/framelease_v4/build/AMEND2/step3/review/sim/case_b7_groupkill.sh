#!/bin/bash
# B7: a signal to the whole process group of amend_step3.sh during the locked part (what a terminal Ctrl-C, a tool
# time-out or a scope stop sends), after the new manifest was written (step 'post_manifest_check').
source "$(dirname "$(readlink -f "$0")")/common.sh"
for c in "B7a|SIGTERM" "B7b|SIGINT"; do
    n="${c%%|*}"; sig="${c#*|}"
    snap_load p1end
    before="$(state)"
    mkdir -p "$R/$n"; rm -f "$R/$n/journal.json"
    setsid "${P[@]}" bash "$S3/amend_step3.sh" --root "$T" --work "$R/$n" > "$L/${n}_outer.log" 2>&1 < /dev/null &
    sp=$!
    "${P[@]}" "$PY" -I -B -c "import time; time.sleep(0.5)"
    pg="$(ps -o pgid= -p $sp | tr -d ' ')"
    "${P[@]}" "$PY" -I -B "$RV/sim/watch_and_act.py" "$R/$n/journal.json" post_manifest_check killpg "$pg" "$sig" > "$L/${n}_watch.log" 2>&1
    "${P[@]}" "$PY" -I -B "$RV/sim/wait_pgroup.py" "$pg" > "$L/${n}_wait.log" 2>&1
    wait $sp 2>/dev/null
    echo "$n ($sig to process group $pg): $(cat "$L/${n}_watch.log"); $(cat "$L/${n}_wait.log")"
    echo "   journal steps: $(grep -o '"step": "[a-z_]*"' "$R/$n/journal.json" | cut -d'"' -f4 | tr '\n' ' ')"
    echo "   amend_step3.log tail: $(tail -3 "$R/$n/amend_step3.log" | cut -c1-150 | tr '\n' '|')"
    echo "   outer log (stdout of the group): $(tail -3 "$L/${n}_outer.log" | cut -c1-200 | tr '\n' '|')"
    echo "   state before $before; after $(state); seal lines OK $(seals)"
    echo "   verify: $(verify | cut -c1-60) ... $(verify | grep -o 'seal [^ ]*: [A-Z]*' | tr '\n' ' ')"
    if [ "$(seals)" -ne 2 ] || [ "$before" != "$(state)" ]; then
        "${TXN[@]}" restore --root "$T" --work "$R/$n" > "$L/${n}_restore.log" 2>&1
        echo "   manual restore: exit $?; state $(state); seal lines OK $(seals)"
    fi
done
