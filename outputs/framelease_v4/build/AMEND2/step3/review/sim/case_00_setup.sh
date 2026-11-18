#!/bin/bash
# R01-R03: pre-check before the fake P1 end (STOP), fake P1 end, pre-check (PASS); snapshot 'p1end'.
source "$(dirname "$(readlink -f "$0")")/common.sh"
"${P[@]}" bash "$S3/amend_step3.sh" --root "$T" --precheck-only --work "$R/R01" > "$L/R01_precheck_before.log" 2>&1
echo "R01 precheck before P1 end: exit $? ; $(grep -c '^PROBLEM' "$L/R01_precheck_before.log") problems: $(grep '^PROBLEM' "$L/R01_precheck_before.log" | cut -c1-90 | tr '\n' '|')"
"${P[@]}" "$PY" -I -B "$RV/sim/fake_p1_end_review.py" "$T" > "$L/R02_fake_p1_end.log" 2>&1
echo "R02 fake P1 end: exit $? ; seals OK: $(seals); state $(state)"
"${P[@]}" bash "$S3/amend_step3.sh" --root "$T" --precheck-only --work "$R/R03" > "$L/R03_precheck.log" 2>&1
echo "R03 precheck after P1 end: exit $? ; last: $(tail -1 "$L/R03_precheck.log")"
echo '# changed by the step-3 review (unregistered file)' >> "$T/framelease_v4/analysis/verify_table1_extra.py"
snap_save p1end
echo "snapshot p1end saved; state $(state); verify: $(verify)"
