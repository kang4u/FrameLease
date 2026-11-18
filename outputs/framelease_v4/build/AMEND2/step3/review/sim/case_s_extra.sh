#!/bin/bash
# X1: a P1 job file (always registered for both drivers) changed after P1 ended: pre-check and transaction.
# X2: `step3_txn.py restore` given the directory of an earlier, restored transaction after a later transaction sealed.
source "$(dirname "$(readlink -f "$0")")/common.sh"
snap_load p1end
# the scratch's p1_jobs becomes a real copy (same bytes, same manifest), so that it can be altered
if [ -L "$T/outputs/framelease_v4/p1_jobs" ]; then
    rm "$T/outputs/framelease_v4/p1_jobs"
    rsync -a "$REAL/outputs/framelease_v4/p1_jobs/" "$T/outputs/framelease_v4/p1_jobs/"
fi
J="$T/outputs/framelease_v4/p1_jobs/FULL/b08_age_s1.jsonl"
cp -a "$J" "$SIM/b08.keep"
echo "X1 setup: verify before the change: $(verify | cut -c1-80)"
printf '\n' >> "$J"
echo "X1 b08_age_s1.jsonl changed (one newline appended); its sha256 is cited by the age_s1 entry: $(grep -c 1cb6404a9c147ae60ad29fee9125222a9089efb7a2b15e11dddf3a414785b5a2 "$T/framelease_v4/PROTOCOL.md") time(s)"
"${P[@]}" bash "$S3/amend_step3.sh" --root "$T" --work "$R/X1" > "$L/X1_transaction.log" 2>&1
echo "X1 transaction: exit $?; $(grep -E '^(PASS|STOP)' "$L/X1_transaction.log" | head -1 | cut -c1-120)"
echo "   precheck PROBLEM lines: $(grep -c '^PROBLEM' "$L/X1_transaction.log")"
echo "   new manifest holds b08 at: $(grep 'FULL/b08_age_s1.jsonl$' "$T/outputs/framelease_v4/registration/MANIFEST.sha256" | cut -c1-16) (cited in PROTOCOL.md: 1cb6404a9c147ae6)"
echo "   verify after: $(verify | cut -c1-200)"
"${P[@]}" "$PY" -I -B "$T/framelease_v4/protocol/phase_driver.py" --dry-run > "$L/X1_dry.log" 2>&1
echo "   phase_driver --dry-run: $(grep -E '^  G0 ' "$L/X1_dry.log" | cut -c1-100)"
cp -a "$SIM/b08.keep" "$J"
# X2: the scratch now holds a sealed step-3 state (X1); the directory of B1b (an earlier transaction, restored) is given
sealed_now="$(state)"
"${TXN[@]}" restore --root "$T" --work "$R/B1b" > "$L/X2_restore_stale.log" 2>&1
echo "X2 restore with the stale directory of B1b: exit $?; $(grep -o 'restored \[[^]]*\]' "$L/X2_restore_stale.log")"
echo "   state before $sealed_now; after $(state); seal lines OK $(seals)"
echo "   amendments in PROTOCOL.md after: $(grep -c -E '^\*\*Amendment A(3|4|7|9), ' "$T/framelease_v4/PROTOCOL.md")"
