#!/bin/bash
# R10: the whole transaction (amend_step3.sh: pre-check, locked part, post-check) on the snapshot 'p1end'; R11 a second
# run; R12 write_d1_decision.py; R13 phase_driver.py --dry-run with the decision; R14 snapshot 'step3done'.
source "$(dirname "$(readlink -f "$0")")/common.sh"
snap_load p1end
before="$(state)"
/usr/bin/time -v "${P[@]}" bash "$S3/amend_step3.sh" --root "$T" --work "$R/R10" > "$L/R10_transaction.log" 2> "$L/R10_time.txt"
rc=$?
echo "R10 transaction: exit $rc; last line: $(grep -E '^(PASS|STOP)' "$L/R10_transaction.log" | head -1)"
echo "   wall $(grep 'Elapsed (wall' "$L/R10_time.txt" | awk '{print $NF}'); max RSS $(grep 'Maximum resident' "$L/R10_time.txt" | awk '{print $NF}') KB"
echo "   lock held/released: $(grep -E '^lock (held|released)' "$L/R10_transaction.log" | cut -c1-40 | tr '\n' ' ')"
echo "   state before $before; after $(state); seal lines OK $(seals)"
grep -E '^    G[0-8] |G5 plan|files registered by|check_drafts.py on the new' "$L/R10_transaction.log" | cut -c1-150 | sed 's/^/   /'
"${P[@]}" bash "$S3/amend_step3.sh" --root "$T" --precheck-only --work "$R/R11" > "$L/R11_second.log" 2>&1
echo "R11 second run (precheck-only): exit $?; $(grep -c '^PROBLEM' "$L/R11_second.log") problems, e.g. $(grep '^PROBLEM' "$L/R11_second.log" | grep -m1 'entered already' | cut -c1-90)"
"${P[@]}" bash "$S3/amend_step3.sh" --root "$T" --work "$R/R11b" > "$L/R11b_second_full.log" 2>&1
echo "R11b second run (full): exit $?; state $(state)"
snap_save step3done
cp -a "$T/framelease_v4/PROTOCOL.md" "$SNAP/step3done/"
echo "snapshot step3done saved"
