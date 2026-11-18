#!/bin/bash
# Apply one Sec. 13.2 entry with apply_entry_stream.py under framelease_v4/.protocol.lock (item a10r7b, RUNBOOK.md).
#
#   cd /home/kang/Desktop/DAC
#   bash outputs/framelease_v4/build/AMEND2/a10r7b/apply_locked.sh SPEC.json OUTDIR
#
# SIGINT, SIGTERM and SIGHUP are ignored from the start (the applier and registration.py inherit this): a terminal, a
# closed session or a tool timeout cannot cut the transaction. Inside one hold of the protocol lock (600 s wait; the
# drivers lock the same file with fcntl.flock):
#   1. refuse (exit 96, nothing done) while a protocol_txn.json or ALERT.txt of the P1 stage driver or of the phase
#      driver, or the applier's temporary file framelease_v4/.PROTOCOL.md.entrytmp, exists, or while SEAL.sha256 does
#      not match PROTOCOL.md and MANIFEST.sha256;
#   2. copy PROTOCOL.md, MANIFEST.sha256, SEAL.sha256 and REGISTRATION.json (sealed, checked in step 1) to
#      OUTDIR/attempt_<time>/ (one directory per attempt, never overwritten);
#   3. run the applier with --apply, unbuffered, in Beijing time (TZ=Asia/Shanghai), output OUTDIR/apply.out;
#   4. wait until no registration.py that the applier started runs any more (a killed applier leaves its child);
#   5. when the applier failed: PROTOCOL.md equal to its copy: put the sealed manifest back when the rewritten one
#      differs and remove a temporary file the applier left (exit: the applier's); PROTOCOL.md holds the entry and the
#      seal matches: nothing to do (the applier stopped after its seal; exit 94); PROTOCOL.md holds the entry and the
#      seal does not match: registration.py --seal with the manifest the entry names (exit 94), and when that fails
#      roll PROTOCOL.md (temporary file, rename), the manifest, SEAL.sha256 and REGISTRATION.json back to the copies
#      (exit 93). The lock is never released while SEAL.sha256 does not match PROTOCOL.md and MANIFEST.sha256;
#   6. registration.py --verify into OUTDIR/verify.out, appended to apply.out.
# Exit code: the applier's (0 sealed, 1 STOP or a traceback, 137 killed, ...); 93 rolled back (nothing applied); 94 the
# wrapper completed the seal of the entry (read the verification); 95 sealed, but the verification does not read
# "manifest: OK" and both seals OK; 96 refused by step 1; 97 the lock was not obtained in 600 s; 98 a copy failed;
# 99 the root does not exist. APPLY_ROOT and APPLIER (environment) replace the project root and the applier for the
# scratch-tree dry runs only.
set -u
trap '' INT TERM HUP
ROOT="${APPLY_ROOT:-/home/kang/Desktop/DAC}"
APPLIER="${APPLIER:-$ROOT/outputs/framelease_v4/build/AMEND2/a10r7b/apply_entry_stream.py}"
SPEC="$1"
OUT="$2"
cd "$ROOT" || exit 99
mkdir -p "$OUT" || exit 98
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' TZ=Asia/Shanghai
export ROOT APPLIER SPEC OUT
flock -w 600 -E 97 framelease_v4/.protocol.lock bash -c '
    R=outputs/framelease_v4/registration
    MAN=$R/MANIFEST.sha256
    PRO=framelease_v4/PROTOCOL.md
    TMP=framelease_v4/.PROTOCOL.md.entrytmp
    PY=/home/kang/Desktop/DAC/.conda-unidrive-linux/bin/python
    X="taskset -c 12-15 nice -n 19 ionice -c 3"
    for f in outputs/framelease_v4/p1_driver/protocol_txn.json outputs/framelease_v4/p1_driver/ALERT.txt \
             outputs/framelease_v4/phase_driver/protocol_txn.json outputs/framelease_v4/phase_driver/ALERT.txt \
             "$TMP"; do
        if [ -e "$f" ]; then
            echo "apply_locked: $f exists: nothing applied" > "$OUT/apply.out"
            exit 96
        fi
    done
    if ! sha256sum -c --status "$R/SEAL.sha256"; then
        echo "apply_locked: SEAL.sha256 does not match PROTOCOL.md and MANIFEST.sha256: nothing applied" \
            > "$OUT/apply.out"
        exit 96
    fi
    D="$OUT/attempt_$(date +%Y%m%dT%H%M%S)"
    mkdir -p "$D" || exit 98
    cp -p "$PRO" "$MAN" "$R/SEAL.sha256" "$R/REGISTRATION.json" "$D/" || exit 98
    echo "apply_locked: copies of the sealed files in $D" > "$OUT/apply.out"
    $X "$PY" -u -I -B "$APPLIER" "$SPEC" --apply >> "$OUT/apply.out" 2>&1
    rc=$?
    n=0
    while pgrep -f -- "$ROOT/framelease_v4/protocol/registration.py" > /dev/null && [ "$n" -lt 3600 ]; do
        sleep 1
        n=$((n + 1))
    done
    [ "$n" -gt 0 ] && echo "apply_locked: waited $n s for a registration.py the applier started" >> "$OUT/apply.out"
    if [ "$rc" -ne 0 ]; then
        if cmp -s "$PRO" "$D/PROTOCOL.md"; then
            if cmp -s "$MAN" "$D/MANIFEST.sha256"; then
                echo "apply_locked: PROTOCOL.md unchanged; the manifest equals the sealed one" >> "$OUT/apply.out"
            elif cp -p "$D/MANIFEST.sha256" "$MAN"; then
                echo "apply_locked: PROTOCOL.md unchanged; RESTORED the sealed manifest" >> "$OUT/apply.out"
            else
                echo "apply_locked: PROTOCOL.md unchanged; restoring the sealed manifest FAILED" >> "$OUT/apply.out"
            fi
            if [ -e "$TMP" ] && rm -f "$TMP"; then
                echo "apply_locked: removed the temporary file $TMP of the applier" >> "$OUT/apply.out"
            fi
        elif sha256sum -c --status "$R/SEAL.sha256"; then
            echo "apply_locked: PROTOCOL.md holds the entry and the seal matches (the applier stopped after --seal)" \
                >> "$OUT/apply.out"
            rc=94
        elif $X "$PY" -I -B framelease_v4/protocol/registration.py --seal >> "$OUT/apply.out" 2>&1; then
            echo "apply_locked: PROTOCOL.md held the entry unsealed: SEALED it with the manifest the entry names" \
                >> "$OUT/apply.out"
            rc=94
        elif cp -p "$D/PROTOCOL.md" "$TMP" && mv -f "$TMP" "$PRO" && cp -p "$D/MANIFEST.sha256" "$MAN" \
                && cp -p "$D/SEAL.sha256" "$D/REGISTRATION.json" "$R/"; then
            echo "apply_locked: the seal failed: ROLLED BACK PROTOCOL.md, the manifest and the seal" >> "$OUT/apply.out"
            rc=93
        else
            echo "apply_locked: ROLL BACK FAILED: restore $D by hand before the lock is released" >> "$OUT/apply.out"
            rc=93
        fi
    fi
    $X "$PY" -I -B framelease_v4/protocol/registration.py --verify > "$OUT/verify.out" 2>&1
    cat "$OUT/verify.out" >> "$OUT/apply.out"
    if [ "$rc" -eq 0 ] || [ "$rc" -eq 94 ]; then
        if ! grep -q "^manifest: OK$" "$OUT/verify.out" || [ "$(grep -c ": OK$" "$OUT/verify.out")" -ne 3 ]; then
            echo "apply_locked: sealed, but registration.py --verify does not read manifest OK and both seals OK" \
                >> "$OUT/apply.out"
            rc=95
        fi
    fi
    exit "$rc"
'
rc=$?
echo "apply_locked: exit $rc (output $OUT/apply.out)"
exit "$rc"
