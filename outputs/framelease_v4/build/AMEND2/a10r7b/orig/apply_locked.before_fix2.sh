#!/bin/bash
# Apply one Sec. 13.2 entry with apply_entry_stream.py under framelease_v4/.protocol.lock (item a10r7b, RUNBOOK.md).
#
#   cd /home/kang/Desktop/DAC
#   bash outputs/framelease_v4/build/AMEND2/a10r7b/apply_locked.sh SPEC.json OUTDIR
#
# Inside one hold of the protocol lock (600 s wait; the drivers lock the same file with fcntl.flock):
#   1. refuse (exit 96, nothing done) while a protocol_txn.json or ALERT.txt of the P1 stage driver or of the phase
#      driver, or the applier's temporary file framelease_v4/.PROTOCOL.md.entrytmp, exists;
#   2. copy the sealed MANIFEST.sha256 and PROTOCOL.md to OUTDIR/{MANIFEST,PROTOCOL}.sealed.before_apply;
#   3. run the applier with --apply, unbuffered, in Beijing time (TZ=Asia/Shanghai), output OUTDIR/apply.out;
#   4. when the applier failed: if PROTOCOL.md equals its copy (the entry is not written), put the sealed manifest back
#      when the rewritten one differs and remove a temporary file the applier left; if PROTOCOL.md holds the entry, keep
#      the rewritten manifest (the one the entry names) and say so: seal it by hand (RUNBOOK.md Sec. 1);
#   5. registration.py --verify into OUTDIR/verify.out, appended to apply.out.
# Exit code: the applier's (0 sealed, 1 STOP or a traceback, 137 killed, ...); 95 the applier sealed but the
# verification does not read "manifest: OK" and both seals OK; 96 refused by step 1; 97 the lock was not obtained in
# 600 s; 98 a copy failed; 99 the root does not exist. APPLY_ROOT and APPLIER (environment) replace the project root
# and the applier for the scratch-tree dry runs only.
set -u
ROOT="${APPLY_ROOT:-/home/kang/Desktop/DAC}"
APPLIER="${APPLIER:-$ROOT/outputs/framelease_v4/build/AMEND2/a10r7b/apply_entry_stream.py}"
SPEC="$1"
OUT="$2"
cd "$ROOT" || exit 99
mkdir -p "$OUT" || exit 98
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' TZ=Asia/Shanghai
export ROOT APPLIER SPEC OUT
flock -w 600 -E 97 framelease_v4/.protocol.lock bash -c '
    MAN=outputs/framelease_v4/registration/MANIFEST.sha256
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
    cp -p "$MAN" "$OUT/MANIFEST.sealed.before_apply" || exit 98
    cp -p "$PRO" "$OUT/PROTOCOL.sealed.before_apply" || exit 98
    $X "$PY" -u -I -B "$APPLIER" "$SPEC" --apply > "$OUT/apply.out" 2>&1
    rc=$?
    if [ "$rc" -ne 0 ]; then
        if cmp -s "$PRO" "$OUT/PROTOCOL.sealed.before_apply"; then
            if cmp -s "$MAN" "$OUT/MANIFEST.sealed.before_apply"; then
                echo "apply_locked: PROTOCOL.md unchanged; the manifest equals the sealed one" >> "$OUT/apply.out"
            elif cp -p "$OUT/MANIFEST.sealed.before_apply" "$MAN"; then
                echo "apply_locked: PROTOCOL.md unchanged; RESTORED the sealed manifest" >> "$OUT/apply.out"
            else
                echo "apply_locked: PROTOCOL.md unchanged; restoring the sealed manifest FAILED" >> "$OUT/apply.out"
            fi
            if [ -e "$TMP" ] && rm -f "$TMP"; then
                echo "apply_locked: removed the temporary file $TMP of the applier" >> "$OUT/apply.out"
            fi
        else
            echo "apply_locked: PROTOCOL.md holds the entry but is not sealed; the rewritten manifest (the one the" \
                 "entry names) is kept: seal it now under the lock (RUNBOOK.md Sec. 1)" >> "$OUT/apply.out"
        fi
    fi
    $X "$PY" -I -B framelease_v4/protocol/registration.py --verify > "$OUT/verify.out" 2>&1
    cat "$OUT/verify.out" >> "$OUT/apply.out"
    if [ "$rc" -eq 0 ]; then
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
