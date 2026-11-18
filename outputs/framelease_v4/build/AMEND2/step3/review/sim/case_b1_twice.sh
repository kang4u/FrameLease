#!/bin/bash
# B1: an in-place "old" text that occurs twice in the sealed PROTOCOL.md (a copy of the Sec. 8.3 lead sentence added
# at the end of Sec. 14, then re-sealed in the scratch). Pre-check and the locked part (run alone) must STOP, nothing
# applied.
source "$(dirname "$(readlink -f "$0")")/common.sh"
snap_load p1end
printf '\nEvery job carries `require_sha256` for (49 files, plus the envelope and the Q-network where they apply):\n' >> "$T/framelease_v4/PROTOCOL.md"
"${P[@]}" "$PY" -I -B "$T/framelease_v4/protocol/registration.py" --seal > "$L/B1_reseal.log" 2>&1
echo "B1 setup: duplicate old text appended, re-sealed: $(tail -1 "$L/B1_reseal.log" | cut -c1-60); verify: $(verify | cut -c150-400)"
before="$(state)"
"${P[@]}" bash "$S3/amend_step3.sh" --root "$T" --precheck-only --work "$R/B1a" > "$L/B1a_precheck.log" 2>&1
echo "B1a precheck: exit $?; $(grep -E '^PROBLEM' "$L/B1a_precheck.log" | cut -c1-140 | tr '\n' '|')"
mkdir -p "$R/B1b"
"${TXN[@]}" locked --root "$T" --work "$R/B1b" --datetime '2026-11-15 08:30' > "$L/B1b_locked.log" 2>&1
rc=$?
echo "B1b locked alone: exit $rc; $(grep -E 'FAILURE|STOP' "$L/B1b_locked.log" | cut -c1-160 | tr '\n' '|')"
echo "B1b state before $before; after $(state); seals OK $(seals)"
