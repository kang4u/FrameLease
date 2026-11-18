#!/bin/bash
# Apply one Sec. 13.2 entry with apply_entry_stream.py under framelease_v4/.protocol.lock (item a10r7b, RUNBOOK.md).
#
#   cd /home/kang/Desktop/DAC
#   X="taskset -c 12-15 nice -n 19 ionice -c 3"
#   setsid nohup $X bash outputs/framelease_v4/build/AMEND2/a10r7b/apply_locked.sh SPEC.json OUTDIR \
#       > OUTDIR/console.txt 2>&1 < /dev/null &          # then wait for the line "apply_locked: exit" in console.txt
#
# SIGINT, SIGTERM and SIGHUP are ignored from the start (the applier and registration.py inherit this): a terminal, a
# closed session or a tool timeout cannot cut the transaction. Inside one hold of the protocol lock (600 s wait; the
# drivers lock the same file with fcntl.flock):
#   1. refuse (exit 96, nothing done) while a protocol_txn.json or ALERT.txt of the P1 stage driver or of the phase
#      driver, or the applier's temporary file framelease_v4/.PROTOCOL.md.entrytmp, exists, or while SEAL.sha256 does
#      not match PROTOCOL.md and MANIFEST.sha256;
#   2. copy PROTOCOL.md, MANIFEST.sha256, SEAL.sha256, REGISTRATION.json (sealed, checked in step 1) and both drivers'
#      registered_baseline.json to a new directory OUTDIR/attempt_<time>_<pid>/ (one per attempt, never overwritten);
#   3. run the applier with --apply, unbuffered, in Beijing time (TZ=Asia/Shanghai), output OUTDIR/apply.out;
#   4. wait until no registration.py that the applier started runs any more (a killed applier leaves its child; only
#      python processes of this process group that run this root's registration.py count);
#   5. when the applier failed:
#      * PROTOCOL.md equals its copy: put the sealed manifest back when the rewritten one differs (temporary file and
#        rename) and remove a temporary file the applier left (exit: the applier's);
#      * PROTOCOL.md is the text the applier composed (its line "composed PROTOCOL.md sha256 <hex>") and the seal
#        matches: nothing to do (the applier stopped after its seal; exit 94); the seal does not match:
#        registration.py --seal with the manifest the entry names (exit 94); when that fails, roll PROTOCOL.md, the
#        manifest, SEAL.sha256 and REGISTRATION.json back to the copies (each through a temporary file and a rename;
#        exit 93);
#      * PROTOCOL.md is neither: kept as OUTDIR/attempt_.../PROTOCOL.unexpected.md; rolled back as above when the seal
#        does not match it (exit 93), left alone when it does (exit 92);
#   6. exit 92 whenever SEAL.sha256 does not match PROTOCOL.md and MANIFEST.sha256 now: the lock is released with a
#      matching seal in every case but exit 92;
#   7. registration.py --verify into OUTDIR/verify.out, appended to apply.out; apply.out and verify.out copied to the
#      attempt directory.
# Exit code: the applier's (0 sealed, 1 STOP or a traceback, 137 killed, ...); 92 the sealed state of before could
# not be restored (a roll-back step failed: "ROLL BACK FAILED", unsealed, or "ROLL BACK INCOMPLETE", the seal matches
# again; or a sealed PROTOCOL.md that the applier did not compose): hand recovery at once (RUNBOOK.md Sec. 1); 93
# rolled back (nothing applied); 94 the wrapper completed the application (the entry is in PROTOCOL.md and sealed); 95
# sealed, but the verification does not read "manifest: OK" and both seals OK; 96 refused by step 1; 97 the lock was
# not obtained in 600 s; 98 a copy failed (nothing applied); 99 the root does not exist.
# APPLY_ROOT and APPLIER (environment) replace the project root and the applier for the scratch-tree dry runs only.
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
    log() { echo "apply_locked: $*" >> "$OUT/apply.out"; }
    put() {         # put FILE DEST: copy through a temporary file next to DEST and rename it (atomic for readers)
        if [ "$2" = "$PRO" ]; then t="$TMP"; else t="$(dirname "$2")/.$(basename "$2").apply_locked.tmp"; fi
        cp -p "$1" "$t" && mv -f "$t" "$2"
    }
    rollback() {
        put "$D/PROTOCOL.md" "$PRO" && put "$D/MANIFEST.sha256" "$MAN" && put "$D/SEAL.sha256" "$R/SEAL.sha256" \
            && put "$D/REGISTRATION.json" "$R/REGISTRATION.json"
    }
    rollback_failed() {
        if sha256sum -c --status "$R/SEAL.sha256"; then
            log "ROLL BACK INCOMPLETE: a copy failed part-way; SEAL.sha256 matches PROTOCOL.md and MANIFEST.sha256" \
                "now; compare every file with the copies in $D"
        else
            log "ROLL BACK FAILED: SEAL.sha256 does not match PROTOCOL.md and MANIFEST.sha256; restore the copies in" \
                "$D by hand at once"
        fi
    }
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
    D="$OUT/attempt_$(date +%Y%m%dT%H%M%S)_$$"
    if ! { mkdir "$D" && cp -p "$PRO" "$MAN" "$R/SEAL.sha256" "$R/REGISTRATION.json" "$D/" \
            && cp -p outputs/framelease_v4/p1_driver/registered_baseline.json "$D/p1_registered_baseline.json" \
            && cp -p outputs/framelease_v4/phase_driver/registered_baseline.json "$D/phase_registered_baseline.json"; }
    then
        echo "apply_locked: a copy into $D failed: nothing applied" > "$OUT/apply.out"
        exit 98
    fi
    echo "apply_locked: copies of the sealed files and of both baselines in $D" > "$OUT/apply.out"
    $X "$PY" -u -I -B "$APPLIER" "$SPEC" --apply >> "$OUT/apply.out" 2>&1
    rc=$?
    n=0
    while pgrep -g 0 -f -- "^[^ ]*python[^ ]* .*$ROOT/framelease_v4/protocol/registration\.py" > /dev/null \
            && [ "$n" -lt 3600 ]; do
        sleep 1
        n=$((n + 1))
    done
    if [ "$n" -gt 0 ]; then
        log "waited $n s for a registration.py the applier started"
    fi
    if [ "$rc" -ne 0 ]; then
        W=$(grep -E "^composed PROTOCOL\.md sha256 [0-9a-f]{64}\$" "$OUT/apply.out" | tail -n 1 | cut -d" " -f4)
        H=$(sha256sum "$PRO" | cut -d" " -f1)
        if cmp -s "$PRO" "$D/PROTOCOL.md"; then
            if cmp -s "$MAN" "$D/MANIFEST.sha256"; then
                log "PROTOCOL.md unchanged; the manifest equals the sealed one"
            elif put "$D/MANIFEST.sha256" "$MAN"; then
                log "PROTOCOL.md unchanged; RESTORED the sealed manifest"
            else
                log "PROTOCOL.md unchanged; restoring the sealed manifest FAILED: restore $D/MANIFEST.sha256 by hand"
            fi
            if [ -e "$TMP" ] && rm -f "$TMP"; then
                log "removed the temporary file $TMP of the applier"
            fi
        elif [ -n "$W" ] && [ "$H" = "$W" ]; then
            if sha256sum -c --status "$R/SEAL.sha256"; then
                log "PROTOCOL.md holds the entry and the seal matches (the applier stopped after --seal)"
                rc=94
            elif $X "$PY" -I -B framelease_v4/protocol/registration.py --seal >> "$OUT/apply.out" 2>&1; then
                log "PROTOCOL.md held the entry unsealed: SEALED it with the manifest the entry names"
                rc=94
            elif rollback; then
                log "the seal failed: ROLLED BACK PROTOCOL.md, the manifest, SEAL.sha256 and REGISTRATION.json to" \
                    "the copies in $D (nothing applied)"
                rc=93
            else
                rollback_failed
                rc=92
            fi
        else
            cp -p "$PRO" "$D/PROTOCOL.unexpected.md"
            if sha256sum -c --status "$R/SEAL.sha256"; then
                log "PROTOCOL.md (sha256 $H) is neither the sealed copy nor the text the applier composed, and it is" \
                    "sealed: left as it is (copy $D/PROTOCOL.unexpected.md); inspect it"
                rc=92
            elif rollback; then
                log "PROTOCOL.md (sha256 $H) was neither the sealed copy nor the text the applier composed (kept as" \
                    "$D/PROTOCOL.unexpected.md): ROLLED BACK to the copies in $D (nothing applied)"
                rc=93
            else
                rollback_failed
                rc=92
            fi
        fi
    fi
    if [ "$rc" -ne 92 ] && ! sha256sum -c --status "$R/SEAL.sha256"; then
        log "SEAL.sha256 does not match PROTOCOL.md and MANIFEST.sha256 (exit $rc before): restore the copies in $D" \
            "by hand at once"
        rc=92
    fi
    $X "$PY" -I -B framelease_v4/protocol/registration.py --verify > "$OUT/verify.out" 2>&1
    cat "$OUT/verify.out" >> "$OUT/apply.out"
    if [ "$rc" -eq 0 ] || [ "$rc" -eq 94 ]; then
        if ! grep -q "^manifest: OK$" "$OUT/verify.out" || [ "$(grep -c ": OK$" "$OUT/verify.out")" -ne 3 ]; then
            log "sealed, but registration.py --verify does not read manifest OK and both seals OK"
            rc=95
        fi
    fi
    cp -p "$OUT/apply.out" "$OUT/verify.out" "$D/" 2> /dev/null
    exit "$rc"
'
rc=$?
echo "apply_locked: exit $rc (output $OUT/apply.out)"
exit "$rc"
