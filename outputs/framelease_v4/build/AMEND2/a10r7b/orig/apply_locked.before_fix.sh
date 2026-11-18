#!/bin/bash
# Apply one Sec. 13.2 entry with apply_entry_stream.py under framelease_v4/.protocol.lock (item a10r7b, RUNBOOK.md).
#
#   cd /home/kang/Desktop/DAC
#   bash outputs/framelease_v4/build/AMEND2/a10r7b/apply_locked.sh SPEC.json OUTDIR
#
# Inside one hold of the protocol lock: copy the sealed MANIFEST.sha256 to OUTDIR/MANIFEST.sealed.before_apply, run the
# applier with --apply (output OUTDIR/apply.out), and when it fails after `registration.py --write-manifest` and before
# `--seal` (a STOP or a traceback in the fill, PROTOCOL.md unchanged) put the sealed manifest back if the rewritten one
# differs; then `registration.py --verify` (appended to apply.out). The exit code is the applier's (0 sealed, 1 STOP,
# other: an unexpected failure); 97 the lock was not obtained in 600 s, 98 the backup failed.
# APPLY_ROOT and APPLIER (environment) replace the project root and the applier for the scratch-tree dry run only.
set -u
ROOT="${APPLY_ROOT:-/home/kang/Desktop/DAC}"
APPLIER="${APPLIER:-$ROOT/outputs/framelease_v4/build/AMEND2/a10r7b/apply_entry_stream.py}"
SPEC="$1"
OUT="$2"
cd "$ROOT" || exit 99
mkdir -p "$OUT" || exit 98
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
export ROOT APPLIER SPEC OUT
flock -w 600 -E 97 framelease_v4/.protocol.lock bash -c '
    MAN=outputs/framelease_v4/registration/MANIFEST.sha256
    PY=/home/kang/Desktop/DAC/.conda-unidrive-linux/bin/python
    X="taskset -c 12-15 nice -n 19 ionice -c 3"
    cp -p "$MAN" "$OUT/MANIFEST.sealed.before_apply" || exit 98
    $X "$PY" -I -B "$APPLIER" "$SPEC" --apply > "$OUT/apply.out" 2>&1
    rc=$?
    if [ "$rc" -ne 0 ] && grep -q "^registration --write-manifest" "$OUT/apply.out" \
            && ! grep -q "^registration --seal" "$OUT/apply.out"; then
        if cmp -s "$MAN" "$OUT/MANIFEST.sealed.before_apply"; then
            echo "apply_locked: stopped after write-manifest; the rewritten manifest equals the sealed one" \
                >> "$OUT/apply.out"
        else
            cp -p "$OUT/MANIFEST.sealed.before_apply" "$MAN" \
                && echo "apply_locked: stopped after write-manifest; RESTORED the sealed manifest" \
                    >> "$OUT/apply.out"
        fi
    fi
    $X "$PY" -I -B framelease_v4/protocol/registration.py --verify >> "$OUT/apply.out" 2>&1
    exit "$rc"
'
rc=$?
echo "apply_locked: exit $rc (output $OUT/apply.out)"
exit "$rc"
