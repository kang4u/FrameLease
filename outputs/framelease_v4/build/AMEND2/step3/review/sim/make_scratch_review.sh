#!/bin/bash
# Reviewer's scratch tree for the step-3 review (default /tmp/AMEND3_review/tree; refuses any other place).
# Same layout as the builder's sim/make_scratch.sh, plus real copies of the three test-log directories
# (amendment_a3, amendment_a7, operational_phase_driver) so that break tests can alter logs without touching the
# project. Read only on the project.
set -euo pipefail
SRC=/home/kang/Desktop/DAC
DST="${1:-/tmp/AMEND3_review/tree}"
case "$DST" in /tmp/AMEND3_review/?*) ;; *) echo "refused: $DST is not under /tmp/AMEND3_review/"; exit 2 ;; esac
rm -rf "$DST"
mkdir -p "$DST"
for e in "$SRC"/* "$SRC"/.[!.]*; do
    n="$(basename "$e")"
    case "$n" in framelease_v4|outputs) continue ;; esac
    ln -s "$e" "$DST/$n"
done
rsync -a --exclude __pycache__ "$SRC/framelease_v4/" "$DST/framelease_v4/"
mkdir -p "$DST/outputs/framelease_v4"
for e in "$SRC"/outputs/*; do
    n="$(basename "$e")"
    [ "$n" = framelease_v4 ] || ln -s "$e" "$DST/outputs/$n"
done
V="$SRC/outputs/framelease_v4"
for e in "$V"/*; do
    n="$(basename "$e")"
    case "$n" in
        registration|p1_driver|amendment_a3|amendment_a7|operational_phase_driver)
            rsync -a "$e/" "$DST/outputs/framelease_v4/$n/" ;;
        build|tuning|phase_driver|queue_*|pipeline_state.json) ;;
        *) ln -s "$e" "$DST/outputs/framelease_v4/$n" ;;
    esac
done
mkdir -p "$DST/outputs/framelease_v4/build" "$DST/outputs/framelease_v4/tuning/d1"
for e in "$V"/build/*; do
    n="$(basename "$e")"
    case "$n" in
        AMEND|AMEND2) rsync -a --exclude 'txn_*' --exclude '/step3/review' "$e/" "$DST/outputs/framelease_v4/build/$n/" ;;
        *) ln -s "$e" "$DST/outputs/framelease_v4/build/$n" ;;
    esac
done
ln -s "$V/tuning/selection" "$DST/outputs/framelease_v4/tuning/selection"
echo "scratch tree $DST: $(find "$DST" -maxdepth 1 | wc -l) root entries; framelease_v4 $(du -sh "$DST/framelease_v4" | cut -f1)"
echo "symlinks into queue dirs: $(find "$DST" -type l -lname '*queue_*' | wc -l)"
