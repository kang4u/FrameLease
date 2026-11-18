#!/bin/bash
# The step-3 simulation, end to end, on a scratch copy (/tmp/AMEND3/tree). Writes only under /tmp/AMEND3/.
#   taskset -c 12-15 nice -n 19 ionice -c 3 bash outputs/framelease_v4/build/AMEND2/step3/sim/run_simulation.sh
# Cases (logs in /tmp/AMEND3/logs/NN_*.log; a summary line per case in /tmp/AMEND3/logs/summary.txt):
#  01 pre-check before the fake P1 end: STOP (P1_DONE.json, the P1 entries)
#  02 fake P1 end (sim/fake_p1_end.py: tuning freeze + D1 summary entries by the P1 driver's own transaction)
#  03 pre-check: passed
#  04-06 the transaction with an injected failure (post_manifest, before_seal, seal_fail): STOP, state restored
#  06b SIGTERM to the helper after PROTOCOL.md was written: STOP, state restored; 06c SIGKILL there: the journal stays
#     at 'protocol'; 06e the pre-check names the unresolved transaction; 06d step3_txn.py restore brings the sealed
#     state back; 06f a second restore of it is refused
#  07 a registered file changed in the scratch tree, `locked` run without the pre-check: the post-manifest check of
#     step 3.2 stops it, the sealed manifest is restored
#  12a-d SIGTERM / SIGHUP to the whole process group of amend_step3.sh (started by setsid) after the journal steps
#     'post_manifest_check' and 'protocol': exit 1, both seals OK, the state as before, a STOP line
#  13a-b a registered file (P1 baseline; one of the 40) changed after PROTOCOL.md was written: the pre-seal check
#     stops, restored; 13c-d a cited test log changed before the lock: refused under the lock / at the pre-check
#  14a-b a P1 job file changed after P1: STOP at the pre-check; `locked` alone: the post-manifest check stops, restored
#  15a-d the time stamp: earlier than the latest Sec. 13.2 stamp, later than now, impossible: refused, nothing changed
#  17 a draft line that the P1 driver reads as a stage entry: STOP at the pre-check (dry fill)
#  08 the transaction: PASS (pre-check, locked part, post-checks); 08b the produced text checked independently
#  09 a second run: STOP at the pre-check (the amendments are entered); 09b a second `locked` alone: refused
#  16a-c restore after the seal: an already restored journal, a stale unresolved journal, the sealed one: refused;
#     16d restore started while a locked part holds the lock (that transaction seals meanwhile): refused
#  10 write_d1_decision.py: refusals, --dry-run, the write; phase_driver.py --dry-run then plans the G1 entry
#  11 the project tree: none of the five entries in its PROTOCOL.md, both seals OK
set -u -o pipefail
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
REAL=/home/kang/Desktop/DAC
HERE="$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd)"
SIM=/tmp/AMEND3
T="$SIM/tree"
L="$SIM/logs"
R="$SIM/runs"
K="$SIM/keep"
P=(taskset -c 12-15 nice -n 19 ionice -c 3)
PY="$REAL/.conda-unidrive-linux/bin/python"
TXN=("${P[@]}" "$PY" -I -B "$HERE/step3_txn.py")
AMEND=("${P[@]}" bash "$HERE/amend_step3.sh" --root "$T")
rm -rf "$L" "$R" "$K"
mkdir -p "$L" "$R" "$K"
S="$L/summary.txt"
real_before="$(cd "$REAL" && sha256sum framelease_v4/PROTOCOL.md outputs/framelease_v4/registration/MANIFEST.sha256 \
    outputs/framelease_v4/registration/SEAL.sha256)"
note() { echo "$*" | tee -a "$S"; }
state() { (cd "$T" && sha256sum framelease_v4/PROTOCOL.md outputs/framelease_v4/registration/MANIFEST.sha256 \
    outputs/framelease_v4/registration/SEAL.sha256 outputs/framelease_v4/registration/REGISTRATION.json | cut -c1-16 | tr '\n' ' '); }
seals() { "${P[@]}" "$PY" -I -B "$T/framelease_v4/protocol/registration.py" --verify | grep -c '^seal .*: OK$'; }
jstep() { sed -n 's/^ "step": "\([a-z_]*\)",\{0,1\}$/\1/p' "$1/journal.json" 2>/dev/null | tail -n 1; }
now() { TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M'; }
expect() {   # name, wanted exit, actual exit, extra condition (0 = ok)
    if [ "$3" -eq "$2" ] && [ "${4:-0}" -eq 0 ]; then note "PASS $1 (exit $3)"; else note "FAIL $1 (exit $3, wanted $2, extra $4)"; fi
}
restored_ok() {   # case dir, state before: the journal ends at 'restored', the state is as before, both seals OK
    [ "$(jstep "$1")" = restored ] && [ "$2" = "$(state)" ] && [ "$(seals)" -eq 2 ]
}

note "simulation $(date -Iseconds); step3_txn.py $(sha256sum "$HERE/step3_txn.py" | cut -c1-16), amend_step3.sh $(sha256sum "$HERE/amend_step3.sh" | cut -c1-16), spec $(sha256sum "$HERE/step3_spec.json" | cut -c1-16)"
"${P[@]}" bash "$HERE/sim/make_scratch.sh" "$T" > "$L/00_make_scratch.log" 2>&1
note "00 scratch tree: $(head -1 "$L/00_make_scratch.log")"

"${AMEND[@]}" --precheck-only --work "$R/01" > "$L/01_precheck_before_p1_end.log" 2>&1
rc=$?
grep -q 'P1_DONE.json does not exist' "$L/01_precheck_before_p1_end.log"; x=$?
expect "01 pre-check before the P1 end stops" 1 $rc $x

"${P[@]}" "$PY" -I -B "$HERE/sim/fake_p1_end.py" "$T" > "$L/02_fake_p1_end.log" 2>&1
rc=$?
expect "02 fake P1 end" 0 $rc
note "   seals after the fake P1 end: $(seals) of 2 OK; state $(state)"

"${AMEND[@]}" --precheck-only --work "$R/03" > "$L/03_precheck.log" 2>&1
expect "03 pre-check after the P1 end" 0 $?

# an unregistered development file changes (as code in development may), so that the new manifest differs from the
# sealed one and every restore below has a manifest to restore
echo '# changed by the step-3 simulation (unregistered file)' >> "$T/framelease_v4/analysis/verify_table1_extra.py"
note "   unregistered file changed in the scratch tree: framelease_v4/analysis/verify_table1_extra.py"
for f in post_manifest before_seal seal_fail; do
    n=$([ $f = post_manifest ] && echo 04 || ([ $f = before_seal ] && echo 05 || echo 06))
    before="$(state)"
    AMEND_STEP3_FAULT=$f "${AMEND[@]}" --work "$R/${n}_$f" > "$L/${n}_fault_$f.log" 2>&1
    rc=$?
    restored_ok "$R/${n}_$f" "$before" && grep -q '^STOP: the transaction failed before the seal and was undone' "$L/${n}_fault_$f.log"
    x=$?
    expect "$n injected failure $f: STOP, journal 'restored', PROTOCOL.md / MANIFEST / SEAL / REGISTRATION.json as before, both seals OK" 1 $rc $x
done

before="$(state)"
AMEND_STEP3_FAULT=signal_before_seal "${AMEND[@]}" --work "$R/06b_signal" > "$L/06b_fault_signal.log" 2>&1
rc=$?
restored_ok "$R/06b_signal" "$before" && grep -q 'signal 15 during the transaction' "$L/06b_fault_signal.log"; x=$?
expect "06b SIGTERM to the helper after PROTOCOL.md was written: STOP, state restored, both seals OK" 1 $rc $x
AMEND_STEP3_FAULT=kill_before_seal "${AMEND[@]}" --work "$R/06c_kill" > "$L/06c_fault_kill.log" 2>&1
rc=$?
[ "$before" != "$(state)" ] && [ "$(jstep "$R/06c_kill")" = protocol ] && grep -q 'Not sealed: restore the sealed state' "$L/06c_fault_kill.log"
x=$?
expect "06c SIGKILL to the helper after PROTOCOL.md was written: STOP, PROTOCOL.md left unsealed, journal at 'protocol'" 137 $rc $x
mkdir -p "$SIM/stale" && rm -rf "$SIM/stale/06c_copy" && cp -a "$R/06c_kill" "$SIM/stale/06c_copy"
"${AMEND[@]}" --precheck-only --work "$R/06e" > "$L/06e_precheck_unresolved.log" 2>&1
rc=$?
grep -q "PROBLEM: an interrupted step-3 transaction is not resolved: $R/06c_kill (journal step 'protocol')" "$L/06e_precheck_unresolved.log"
x=$?
expect "06e pre-check while the killed transaction is unresolved: STOP, its directory named" 1 $rc $x
"${TXN[@]}" restore --root "$T" --work "$R/06c_kill" > "$L/06d_restore.log" 2>&1
rc=$?
restored_ok "$R/06c_kill" "$before"; x=$?
expect "06d step3_txn.py restore after the kill (takes the scratch lock): the sealed state is back, both seals OK" 0 $rc $x
"${TXN[@]}" restore --root "$T" --work "$R/06c_kill" > "$L/06f_restore_again.log" 2>&1
rc=$?
[ "$before" = "$(state)" ] && grep -q "the journal says 'restored'" "$L/06f_restore_again.log"; x=$?
expect "06f a second restore of the same transaction: refused (journal 'restored'), nothing changed" 1 $rc $x

before="$(state)"
cp -p "$T/framelease_v4/protocol/p1_driver.py" "$K/p1_driver.py"
echo '# changed by the step-3 simulation (case 07)' >> "$T/framelease_v4/protocol/p1_driver.py"
mkdir -p "$R/07"
"${TXN[@]}" locked --root "$T" --work "$R/07" --datetime "$(now)" > "$L/07_registered_file_changed.log" 2>&1
rc=$?
cp -p "$K/p1_driver.py" "$T/framelease_v4/protocol/p1_driver.py"
grep -q "post-manifest check (step 3.2): \['framelease_v4/protocol/p1_driver.py'\]" "$L/07_registered_file_changed.log" \
    && restored_ok "$R/07" "$before"; x=$?
expect "07 registered file changed: the post-manifest check stops, the sealed manifest is restored" 1 $rc $x

# 12a-d: a signal to the whole process group of amend_step3.sh (a task stop, a group kill, a scope stop)
for c in "12a|SIGTERM|15|post_manifest_check" "12b|SIGTERM|15|protocol" "12c|SIGHUP|1|post_manifest_check" \
         "12d|SIGHUP|1|protocol"; do
    IFS='|' read -r n sig num at <<< "$c"
    before="$(state)"
    mkdir -p "$R/$n"
    setsid -w "${AMEND[@]}" --work "$R/$n" > "$L/${n}_group_${sig}.log" 2>&1 < /dev/null &
    sp=$!
    "${P[@]}" "$PY" -I -B "$HERE/sim/watch_and_act.py" "$R/$n/journal.json" "$at" killpg "$sp" "$sig" \
        > "$L/${n}_watch.log" 2>&1
    wait "$sp"
    rc=$?
    restored_ok "$R/$n" "$before" && grep -q " sent $sig to process group $sp " "$L/${n}_watch.log" \
        && grep -q '^STOP: the transaction failed before the seal and was undone' "$L/${n}_group_${sig}.log" \
        && grep -q "FAILURE before the seal: signal $num during the transaction" "$R/$n/step3_txn.log"; x=$?
    expect "$n $sig to the process group after journal step '$at': STOP line, journal 'restored', state as before, both seals OK" 1 $rc $x
done

# 13a-b: a registered file changes after PROTOCOL.md was written, before the seal (fault hook, scratch file)
for c in "13a|framelease_v4/protocol/p1_driver.py" "13b|framelease_v4/analysis/commit_audit.py"; do
    IFS='|' read -r n f <<< "$c"
    before="$(state)"
    cp -p "$T/$f" "$K/$n"
    AMEND_STEP3_FAULT=change_before_preseal AMEND_STEP3_FAULT_FILE="$f" "${AMEND[@]}" --work "$R/$n" \
        > "$L/${n}_changed_before_seal.log" 2>&1
    rc=$?
    cp -p "$K/$n" "$T/$f"
    restored_ok "$R/$n" "$before" && grep -q "FAILURE before the seal: pre-seal check: .*$f" "$L/${n}_changed_before_seal.log"
    x=$?
    expect "$n $f changed between the manifest and the seal: the pre-seal check stops, restored" 1 $rc $x
done
# 13c-d: a cited test log changes after the pre-check (locked alone) / before it
LOGF=outputs/framelease_v4/amendment_a3/pytest_arms_ext.log
cp -p "$T/$LOGF" "$K/13c"
echo '# changed by the step-3 simulation' >> "$T/$LOGF"
before="$(state)"
mkdir -p "$R/13c"
"${TXN[@]}" locked --root "$T" --work "$R/13c" --datetime "$(now)" > "$L/13c_input_changed_locked.log" 2>&1
rc=$?
[ "$(jstep "$R/13c")" = refused ] && [ "$before" = "$(state)" ] && grep -q "STOPPED before any change: $LOGF: sha256" "$L/13c_input_changed_locked.log"
x=$?
expect "13c a cited test log changed after the pre-check: refused under the lock before any change" 1 $rc $x
"${AMEND[@]}" --precheck-only --work "$R/13d" > "$L/13d_input_changed_precheck.log" 2>&1
rc=$?
grep -q "PROBLEM: $LOGF: sha256" "$L/13d_input_changed_precheck.log"; x=$?
expect "13d the same change at the pre-check: STOP" 1 $rc $x
cp -p "$K/13c" "$T/$LOGF"

# 14a-b: a P1 job file (always registered) changes after P1
JF=outputs/framelease_v4/p1_jobs/FULL/b08_age_s1.jsonl
cp -p "$T/$JF" "$K/14"
printf '\n' >> "$T/$JF"
before="$(state)"
"${AMEND[@]}" --work "$R/14a" > "$L/14a_p1_job_changed.log" 2>&1
rc=$?
[ "$before" = "$(state)" ] && grep -q "PROBLEM: P1 job files .*$JF" "$L/14a_p1_job_changed.log"; x=$?
expect "14a a P1 job file changed after P1: STOP at the pre-check, nothing changed" 1 $rc $x
mkdir -p "$R/14b"
"${TXN[@]}" locked --root "$T" --work "$R/14b" --datetime "$(now)" > "$L/14b_p1_job_changed_locked.log" 2>&1
rc=$?
restored_ok "$R/14b" "$before" && grep -q "P1 job files (always registered) not in the new manifest at their sealed sha256: \['$JF'\]" "$L/14b_p1_job_changed_locked.log"
x=$?
expect "14b the same, locked alone: the post-manifest check names the P1 job file, restored" 1 $rc $x
cp -p "$K/14" "$T/$JF"

# 15a-d: the time stamp
future="$(TZ=Asia/Shanghai date -d '+1 day' '+%Y-%m-%d %H:%M')"
for c in "15a|2026-11-14 00:00|is earlier than the latest time stamp of Sec. 13.2" \
         "15b|$future|is later than the current time" "15c|2026-13-45 99:99|is not a valid time"; do
    IFS='|' read -r n dt msg <<< "$c"
    before="$(state)"
    mkdir -p "$R/$n"
    "${TXN[@]}" locked --root "$T" --work "$R/$n" --datetime "$dt" > "$L/${n}_datetime.log" 2>&1
    rc=$?
    [ "$(jstep "$R/$n")" = refused ] && [ "$before" = "$(state)" ] && grep -q -- "$msg" "$L/${n}_datetime.log"; x=$?
    expect "$n --datetime '$dt': refused before any change ($msg)" 1 $rc $x
done
"${AMEND[@]}" --precheck-only --datetime '2026-11-14 00:00' --work "$R/15d" > "$L/15d_datetime_precheck.log" 2>&1
rc=$?
grep -q 'PROBLEM: --datetime 2026-11-14 00:00 is earlier than the latest time stamp' "$L/15d_datetime_precheck.log"; x=$?
expect "15d amend_step3.sh --datetime '2026-11-14 00:00': STOP at the pre-check" 1 $rc $x

# 17: a draft line that the P1 driver's parser reads as a stage entry (p1_driver.ENTRY_RE): the dry fill names it
DR=outputs/framelease_v4/build/AMEND/AMENDMENTS_DRAFT.md
cp -p "$T/$DR" "$K/17"
"${P[@]}" "$PY" -I -B - "$T/$DR" <<'PYEOF'
import sys
p = sys.argv[1]
lines = open(p, encoding='utf-8').read().split('\n')
a9 = next(k for k, ln in enumerate(lines) if ln.startswith('## A9:'))
i = next(k for k in range(a9, len(lines)) if lines[k].startswith('* Manifest and seal after this amendment:'))
lines.insert(i, '* **heur_s1**, 2026-11-15 04:35 (Beijing time). Selection inserted by the simulation (parser test).')
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
PYEOF
"${AMEND[@]}" --precheck-only --work "$R/17" > "$L/17_draft_line_read_as_entry.log" 2>&1
rc=$?
grep -q 'PROBLEM: dry fill: A9: line [0-9]* reads as a driver entry' "$L/17_draft_line_read_as_entry.log"; x=$?
expect "17 a draft line that p1_driver.ENTRY_RE reads as a stage entry: STOP at the pre-check (dry fill)" 1 $rc $x
cp -p "$K/17" "$T/$DR"

before="$(state)"
"${AMEND[@]}" --work "$R/08_transaction" > "$L/08_transaction.log" 2>&1
rc=$?
grep -q '^PASS: ' "$L/08_transaction.log" && [ "$(jstep "$R/08_transaction")" = verified ]; x=$?
expect "08 the transaction (pre-check, locked part, post-check)" 0 $rc $x
note "   state before $before"
note "   state after  $(state)"
"${P[@]}" "$PY" -I -B "$HERE/sim/check_result.py" "$T" "$R/08_transaction" > "$L/08b_check_result.log" 2>&1
expect "08b the produced PROTOCOL.md checked independently (sim/check_result.py)" 0 $?

"${AMEND[@]}" --precheck-only --work "$R/09" > "$L/09_second_run.log" 2>&1
rc=$?
grep -q 'Amendment A3 is entered already' "$L/09_second_run.log"; x=$?
expect "09 a second run stops at the pre-check" 1 $rc $x

sealed_now="$(state)"
mkdir -p "$R/09b"
"${TXN[@]}" locked --root "$T" --work "$R/09b" --datetime "$(now)" > "$L/09b_second_locked.log" 2>&1
rc=$?
[ "$(jstep "$R/09b")" = refused ] && [ "$sealed_now" = "$(state)" ] \
    && grep -q 'STOPPED before any change: .*Amendment A3 is entered already' "$L/09b_second_locked.log"; x=$?
expect "09b a second locked part (its pre-check passed before the first seal): refused before any change" 1 $rc $x
"${TXN[@]}" restore --root "$T" --work "$R/04_post_manifest" > "$L/16a_restore_restored_journal.log" 2>&1
rc=$?
[ "$sealed_now" = "$(state)" ] && grep -q "the journal says 'restored'" "$L/16a_restore_restored_journal.log"; x=$?
expect "16a restore with the directory of an earlier, restored transaction after the seal: refused, nothing changed" 1 $rc $x
"${TXN[@]}" restore --root "$T" --work "$SIM/stale/06c_copy" > "$L/16b_restore_stale_journal.log" 2>&1
rc=$?
[ "$sealed_now" = "$(state)" ] && grep -q "restore refused: PROTOCOL.md" "$L/16b_restore_stale_journal.log"; x=$?
expect "16b restore with a stale unresolved journal (copy of 06c before 06d) after the seal: refused by the guard" 1 $rc $x
"${TXN[@]}" restore --root "$T" --work "$R/08_transaction" > "$L/16c_restore_sealed.log" 2>&1
rc=$?
[ "$sealed_now" = "$(state)" ] && grep -q "the journal says 'verified': the transaction was sealed" "$L/16c_restore_sealed.log"; x=$?
expect "16c restore with the sealed transaction's directory: refused, nothing changed" 1 $rc $x

# 16d: restore started while a locked part holds the lock; that transaction seals meanwhile (its journal turns
# 'verified'): restore reads the journal under the lock and refuses (a copy of 08's directory whose journal is cut at
# 'preseal_check' stands for the running transaction; the scratch lock is held by flock for 6 s)
X="$SIM/stale/08_pending"
rm -rf "$X" && cp -a "$R/08_transaction" "$X"
"${P[@]}" "$PY" -I -B - "$X/journal.json" <<'PYEOF'
import json, sys
p = sys.argv[1]
j = json.load(open(p, encoding='utf-8'))
k = max(i for i, s in enumerate(j['steps']) if s['step'] == 'preseal_check')
j['steps'], j['step'] = j['steps'][:k + 1], 'preseal_check'
open(p, 'w', encoding='utf-8').write(json.dumps(j, indent=1) + '\n')
PYEOF
"${P[@]}" flock "$T/framelease_v4/.protocol.lock" sleep 6 &
lp=$!
sleep 1
"${TXN[@]}" restore --root "$T" --work "$X" > "$L/16d_restore_while_locked.log" 2>&1 &
rp=$!
sleep 2
cp "$R/08_transaction/journal.json" "$X/journal.json"
wait "$lp"
wait "$rp"
rc=$?
[ "$sealed_now" = "$(state)" ] && grep -q "the journal says 'verified': the transaction was sealed" "$L/16d_restore_while_locked.log"
x=$?
expect "16d restore started while a locked part held the lock, the transaction sealed meanwhile: refused (journal read under the lock)" 1 $rc $x

D="$SIM/d1"
rm -rf "$D"
mkdir -p "$D"
printf '%s\n' 'Every P1 block is final on the training routes; the tuning freeze fixes L* = B0, d* = 1 and the' \
    'Event-Triggered point s_hb2.0 (simulation text).' > "$D/ok.txt"
printf '%s\n' 'Continue. Each amendment gets the date and time.' > "$D/anchor.txt"
printf '%s\n' 'Continue; the AI agrees.' > "$D/authorship.txt"
W=("${P[@]}" "$PY" -I -B "$HERE/write_d1_decision.py" --root "$T")
"${W[@]}" --decision continue --rationale-file "$D/anchor.txt" > "$L/10a_anchor.log" 2>&1
expect "10a rationale with the anchor phrase refused" 1 $?
"${W[@]}" --decision continue --rationale-file "$D/authorship.txt" > "$L/10b_authorship.log" 2>&1
expect "10b rationale naming its writer refused" 1 $?
J="$T/outputs/framelease_v4/tuning/d1/FULL_d1_summary.json"
cp "$J" "$K/d1_summary.json"
echo ' ' >> "$J"
"${W[@]}" --decision continue --rationale-file "$D/ok.txt" > "$L/10c_summary_changed.log" 2>&1
expect "10c D1 summary not the one the entry cites: refused" 1 $?
cp "$K/d1_summary.json" "$J"
"${W[@]}" --decision continue --rationale-file "$D/ok.txt" --by 'Claude' > "$L/10j_by_authorship.log" 2>&1
expect "10j --by naming who or what wrote the text refused" 1 $?
"${W[@]}" --decision continue --rationale-file "$D/ok.txt" --dry-run > "$L/10d_dry_run.log" 2>&1
rc=$?
[ ! -e "$T/outputs/framelease_v4/phase_driver/D1_DECISION.json" ] && grep -q '"by": "the coordinating session"' "$L/10d_dry_run.log"
x=$?
expect "10d --dry-run prints the JSON (by: the coordinating session), writes nothing" 0 $rc $x
"${W[@]}" --decision continue --rationale-file "$D/ok.txt" > "$L/10e_write.log" 2>&1
rc=$?
[ -f "$T/outputs/framelease_v4/phase_driver/D1_DECISION.json" ] && \
    [ -z "$(ls -A "$T/outputs/framelease_v4/phase_driver" | grep -v '^D1_DECISION.json$')" ]; x=$?
expect "10e decision written (temporary file renamed; nothing else in phase_driver/)" 0 $rc $x
"${W[@]}" --decision stop --rationale-file "$D/ok.txt" > "$L/10f_second_write.log" 2>&1
expect "10f a second decision refused" 1 $?
"${P[@]}" "$PY" -I -B "$T/framelease_v4/protocol/phase_driver.py" --dry-run > "$L/10g_phase_driver_dry_run.log" 2>&1
rc=$?
grep -qE '^  G0 +passed' "$L/10g_phase_driver_dry_run.log" && grep -q 'record G1 D1 decision' "$L/10g_phase_driver_dry_run.log" \
    && sed -n 's/^      | //p' "$L/10g_phase_driver_dry_run.log" | tr '\n' ' ' | tr -s ' ' \
    | grep -q 'by the coordinating session, on the D1 summary'
x=$?
expect "10g phase_driver.py --dry-run: G0 passed, G1 would record the decision ('by the coordinating session')" 0 $rc $x
[ -z "$(ls -A "$T/outputs/framelease_v4/phase_driver" | grep -v '^D1_DECISION.json$')" ]; x=$?
expect "10h the dry run wrote nothing into phase_driver/" 0 0 $x

real_after="$(cd "$REAL" && sha256sum framelease_v4/PROTOCOL.md outputs/framelease_v4/registration/MANIFEST.sha256 \
    outputs/framelease_v4/registration/SEAL.sha256)"
"${P[@]}" "$PY" -I -B - "$REAL" > "$L/11_project_tree.log" 2>&1 <<'PYEOF'
import subprocess, sys
root = sys.argv[1]
text = open(f'{root}/framelease_v4/PROTOCOL.md', encoding='utf-8').read()
marks = ['**Amendment A3,', '**Amendment A9,', '**Amendment A7,', '**Amendment A4,',
         '(Beijing time): the phase driver of Phases 2-7']
found = [m for m in marks if m in text]
out = subprocess.run([f'{root}/.conda-unidrive-linux/bin/python', '-I', '-B', f'{root}/framelease_v4/protocol/registration.py',
                      '--verify'], capture_output=True, text=True).stdout
seals = sum(1 for ln in out.splitlines() if ln.startswith('seal ') and ln.endswith(': OK'))
p1 = [ln.split('**')[1] for ln in text.splitlines() if ln.startswith('* **') and '(Beijing time). Selection' in ln]
print('entries of this item in the project PROTOCOL.md:', found or 'none')
print('project registration.py --verify:', ' | '.join(out.strip().splitlines()))
print('P1 driver stage entries now:', p1)
sys.exit(0 if not found and seals == 2 else 1)
PYEOF
x=$?
if [ "$real_before" = "$real_after" ]; then how='unchanged'; else how='changed by the P1 stage driver only (its own entry)'; fi
expect "11 the project tree: none of the five entries in its PROTOCOL.md, both seals OK; PROTOCOL.md $how" 0 0 $x
note "   $(tr '\n' ' ' < "$L/11_project_tree.log" | cut -c1-400)"
note "simulation end $(date -Iseconds): $(grep -c '^PASS' "$S") PASS, $(grep -c '^FAIL' "$S") FAIL"
