#!/bin/bash
# Review proposal (a10r7b review, must-fix M1 / should-fix S1-S3): apply_locked.sh with the fixes found by the
# scratch-tree cases D, E, F and G of review_sim.py. Same interface and hooks as the builder's apply_locked.sh:
#
#   cd /home/kang/Desktop/DAC
#   bash <this script> SPEC.json OUTDIR
#
# Changes against a10r7b/apply_locked.sh:
#   * TZ=Asia/Shanghai for the applier (the template says "Beijing time"; case G);
#   * inside the lock, before anything: no phase_driver/protocol_txn.json or ALERT.txt (exit 96);
#   * PROTOCOL.md is copied next to the sealed manifest; after a failure the sealed manifest is put back only when
#     PROTOCOL.md is still the sealed one; when PROTOCOL.md already holds the entry the rewritten manifest (the one the
#     entry names) is kept and the output says to seal it now (case F2);
#   * the applier runs unbuffered (python -u), so apply.out shows how far it got even after a kill;
#   * exit 95 when the applier reported success but registration.py --verify does not read "manifest: OK" and both
#     seals OK (a registered file changed between --write-manifest and --seal; case E).
# The applier must also check every registered file (P1 and phase driver baselines; case D): see REVIEW.md, M1.
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
    PY=/home/kang/Desktop/DAC/.conda-unidrive-linux/bin/python
    X="taskset -c 12-15 nice -n 19 ionice -c 3"
    for f in outputs/framelease_v4/phase_driver/protocol_txn.json outputs/framelease_v4/phase_driver/ALERT.txt \
             outputs/framelease_v4/p1_driver/protocol_txn.json outputs/framelease_v4/p1_driver/ALERT.txt; do
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
            if ! cmp -s "$MAN" "$OUT/MANIFEST.sealed.before_apply"; then
                cp -p "$OUT/MANIFEST.sealed.before_apply" "$MAN" \
                    && echo "apply_locked: PROTOCOL.md unchanged; RESTORED the sealed manifest" >> "$OUT/apply.out"
            fi
        else
            echo "apply_locked: PROTOCOL.md holds the entry but is not sealed; the rewritten manifest (the one the" \
                 "entry names) is kept: seal now under the lock (registration.py --seal), then --verify" \
                 >> "$OUT/apply.out"
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
