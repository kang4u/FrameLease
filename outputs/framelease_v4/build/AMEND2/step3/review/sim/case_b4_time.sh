#!/bin/bash
# B4: a wrong time stamp. B4a: earlier than the P1 driver's "D1 summary" entry; B4b: an impossible date.
source "$(dirname "$(readlink -f "$0")")/common.sh"
for c in "B4a|2026-11-14 00:00" "B4b|2026-13-45 99:99"; do
    n="${c%%|*}"; dt="${c#*|}"
    snap_load p1end
    mkdir -p "$R/$n"
    "${TXN[@]}" locked --root "$T" --work "$R/$n" --datetime "$dt" > "$L/${n}_locked.log" 2>&1
    rc=$?
    d1="$(grep -o '^\* \*\*D1 summary\*\*, [0-9-]* [0-9:]*' "$T/framelease_v4/PROTOCOL.md")"
    a3="$(grep -o '^\*\*Amendment A3, [^(]*' "$T/framelease_v4/PROTOCOL.md")"
    echo "$n --datetime '$dt': locked exit $rc; seal lines OK $(seals); D1 entry: '$d1'; A3 entry: '$a3'"
    "${P[@]}" "$PY" -I -B "$T/framelease_v4/protocol/phase_driver.py" --dry-run > "$L/${n}_dry.log" 2>&1
    echo "   phase_driver --dry-run exit $?: $(grep -E '^  G[01] ' "$L/${n}_dry.log" | cut -c1-90 | tr '\n' '|')"
done
