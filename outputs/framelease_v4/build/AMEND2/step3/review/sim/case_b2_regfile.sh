#!/bin/bash
# B2: a registered file changes after the post-manifest check (step 3.2) and before the seal.
#  B2a: the P1 baseline file framelease_v4/protocol/p1_driver.py, changed after 'post_manifest_check'
#  B2b: an A3 file the transaction registers (framelease_v4/analysis/commit_audit.py), changed after 'filled'
#  B2c: the same A3 file changed after 'post_manifest_check' (before the fill)
source "$(dirname "$(readlink -f "$0")")/common.sh"
W=("${P[@]}" "$PY" -I -B "$RV/sim/watch_and_act.py")
run_case() {  # name step file
    snap_load p1end
    local before; before="$(state)"
    mkdir -p "$R/$1"; rm -f "$R/$1/journal.json"
    "${W[@]}" "$R/$1/journal.json" "$2" append "$T/$3" > "$L/$1_watch.log" 2>&1 &
    local wp=$!
    "${TXN[@]}" locked --root "$T" --work "$R/$1" --datetime '2026-11-15 08:30' > "$L/$1_locked.log" 2>&1
    local rc=$?
    wait $wp
    echo "$1 ($3 changed after step $2): locked exit $rc; watcher: $(cat "$L/$1_watch.log")"
    echo "   last journal step: $(grep -o '"step": "[a-z_]*"' "$R/$1/journal.json" | tail -1)"
    echo "   $(grep -E 'FAILURE|registered files differ|verify' "$L/$1_locked.log" | cut -c1-200 | tr '\n' '|')"
    echo "   state before $before; after $(state); seal lines OK $(seals)"
    echo "   entries in PROTOCOL.md now: $(grep -c -E '^\*\*Amendment A(3|4|7|9), 2026-11-15 08:30|^\*\*Operational addition, 2026-11-15 08:30' "$T/framelease_v4/PROTOCOL.md")"
}
run_case B2a post_manifest_check framelease_v4/protocol/p1_driver.py
run_case B2b filled framelease_v4/analysis/commit_audit.py
run_case B2c post_manifest_check framelease_v4/analysis/commit_audit.py
