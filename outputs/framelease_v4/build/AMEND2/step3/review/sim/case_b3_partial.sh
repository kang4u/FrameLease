#!/bin/bash
# B3: a partial write. The locked part runs under `ulimit -f 200` (200 KiB): the sealed copy of PROTOCOL.md
# (~173 KB) fits, the new PROTOCOL.md (~226 KB) cannot be written completely. PROTOCOL.md must never be left partial.
source "$(dirname "$(readlink -f "$0")")/common.sh"
snap_load p1end
before="$(state)"
mkdir -p "$R/B3"
( ulimit -f 200; "${TXN[@]}" locked --root "$T" --work "$R/B3" --datetime '2026-11-15 08:30' ) > "$L/B3_locked.log" 2>&1
rc=$?
echo "B3 locked under ulimit -f 200: exit $rc"
echo "   $(grep -E 'FAILURE|restore' "$L/B3_locked.log" | cut -c1-220 | tr '\n' '|')"
echo "   last journal step: $(grep -o '"step": "[a-z_]*"' "$R/B3/journal.json" | tail -1)"
ls -la "$R/B3" | grep -E 'PROTOCOL|restore' | awk '{print "   " $5, $9}'
echo "   state before $before; after $(state); seal lines OK $(seals)"
