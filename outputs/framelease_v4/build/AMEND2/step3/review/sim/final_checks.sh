#!/bin/bash
# End-of-review checks on the project (read only): registration --verify, the registered baseline, what changed
# under framelease_v4/ and outputs/framelease_v4/ since the review started (/tmp/AMEND3_review/.ref_start), pycache
# and empty files under framelease_v4/.
set -u
REAL=/home/kang/Desktop/DAC
cd "$REAL" || exit 2
export CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
P=(taskset -c 12-15 nice -n 19 ionice -c 3)
echo "== registration.py --verify ($(date -Iseconds))"
"${P[@]}" .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/registration.py --verify
echo "== registered baseline"
"${P[@]}" .conda-unidrive-linux/bin/python -I -B outputs/framelease_v4/build/AMEND2/step3/review/check_baseline.py
echo "== sha256 now"
sha256sum framelease_v4/PROTOCOL.md outputs/framelease_v4/registration/{MANIFEST.sha256,SEAL.sha256,REGISTRATION.json} | cut -c1-16,65-
echo "== changed under framelease_v4/ since the review started"
find framelease_v4 -newer /tmp/AMEND3_review/.ref_start -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' | sort
echo "== changed under outputs/framelease_v4/ since the review started (queue_p1 and tuning/ runs excluded)"
find outputs/framelease_v4 -path outputs/framelease_v4/queue_p1 -prune -o -path outputs/framelease_v4/tuning -prune \
    -o -path outputs/framelease_v4/build/AMEND2/step3/review -prune -o -newer /tmp/AMEND3_review/.ref_start \
    -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' | sort | head -40
echo "== tuning/ changes (P1 runs, listed by top directory)"
find outputs/framelease_v4/tuning -newer /tmp/AMEND3_review/.ref_start -printf '%P\n' | cut -d/ -f1-2 | sort | uniq -c | head
echo "== __pycache__ / .pyc / .pytest_cache under framelease_v4/ and build/ newer than the start"
find framelease_v4 outputs/framelease_v4/build \( -name __pycache__ -o -name '*.pyc' -o -name .pytest_cache \) -newer /tmp/AMEND3_review/.ref_start
echo "== empty files under framelease_v4/"
find framelease_v4 -type f -empty
echo "== phase_driver dir exists: $([ -e outputs/framelease_v4/phase_driver ] && echo yes || echo no); P1_DONE: $([ -e outputs/framelease_v4/p1_driver/P1_DONE.json ] && echo yes || echo no)"
