#!/bin/bash
# B5: a filled line over 120 columns (a longer pytest summary in the scratch copy of pytest_arms_ext.log), locked alone.
# B6: lines a driver parser reads (scratch copy of the AMEND draft / OP template), locked alone:
#   B6a a bullet in A9 that p1_driver.ENTRY_RE reads as the "heur_s1" stage entry;
#   B6b a line in A4 that phase_driver.AMEND_RE reads as an amendment title (A12);
#   B6c a line in A3 that phase_driver.ENTRY_RE reads as the G1 entry.
source "$(dirname "$(readlink -f "$0")")/common.sh"
D="$T/outputs/framelease_v4/build/AMEND/AMENDMENTS_DRAFT.md"
snap_load p1end
LOG="$T/outputs/framelease_v4/amendment_a3/pytest_arms_ext.log"
sed -i 's/^38 passed, 21 warnings in 133.66s (0:02:13)/38 passed, 21 warnings, 1 xpassed, 3 deselected, 17 subtests passed, 4 rerun in 133.66s (0:02:13) after a full collection/' "$LOG"
echo "B5 setup: summary now: $(tail -1 "$LOG" | tr -d '=' | cut -c1-140)"
mkdir -p "$R/B5"
"${TXN[@]}" locked --root "$T" --work "$R/B5" --datetime '2026-11-15 08:30' > "$L/B5_locked.log" 2>&1
rc=$?
echo "B5 locked: exit $rc; seal lines OK $(seals)"
grep -n -A2 'framelease_v4/arms_ext/tests`:' "$R/B5/entry_A3.md" | sed 's/^/   /'
echo "   lines over 120 (non-table) in the five entries: $(cat "$R"/B5/entry_*.md | awk 'length($0) > 120 && $0 !~ /^ *\|/' | wc -l); in new PROTOCOL.md: $(awk 'length($0) > 120 && $0 !~ /^ *\|/' "$T/framelease_v4/PROTOCOL.md" | wc -l) (before: $(awk 'length($0) > 120 && $0 !~ /^ *\|/' "$SNAP/p1end/PROTOCOL.md" | wc -l))"
for c in 'B6a|^  \* Two determinism runs of the independent review|* **heur_s1**, 2026-11-15 04:35 (Beijing time). Selection inserted by the review (parser test).' \
         'B6b|^\* Scope\. P4-P6 job lines \(tiers 3-6\)|**Amendment A12, 2026-11-15 04:35 (Beijing time): a line the phase driver reads as a title.**' \
         'B6c|^\* Change: the tools, their roles|* **G1 D1 decision** (2026-11-15 04:35, Beijing time). A line the phase driver reads as its entry.'; do
    n="${c%%|*}"; rest="${c#*|}"; pat="${rest%%|*}"; line="${rest#*|}"
    snap_load p1end
    "${P[@]}" "$PY" -I -B - "$D" "$pat" "$line" <<'PYEOF'
import re, sys
p, pat, line = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(p, encoding='utf-8').read().split('\n')
i = next(k for k, ln in enumerate(lines) if re.match(pat, ln))
lines.insert(i, line)
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
PYEOF
    before="$(state)"
    mkdir -p "$R/$n"
    "${TXN[@]}" locked --root "$T" --work "$R/$n" --datetime '2026-11-15 08:30' > "$L/${n}_locked.log" 2>&1
    rc=$?
    echo "$n locked: exit $rc; $(grep -E 'FAILURE' "$L/${n}_locked.log" | cut -c1-230)"
    echo "   state before $before; after $(state); seal lines OK $(seals)"
done
