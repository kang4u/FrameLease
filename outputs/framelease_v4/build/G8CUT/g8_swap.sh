#!/bin/bash
# G8CUT step b1 (RUNBOOK.md Sec. 4): put the registered P4-P6 job files back into queue_p4/jobs.d after every kept job
# is final and the runner has exited; queue_p4/STOP first, so that no runner ever starts one of the 505 cut lines.
#   cd /home/kang/Desktop/DAC && bash outputs/framelease_v4/build/G8CUT/g8_swap.sh
# Refuses (exit 3 / 2) unless g8_lib.py check --expect reduced is READY; idempotent after a completed swap.
# Then test_freeze.py --verify on the copies (the phase driver's G6 command). Exit 0 done.
source "${BASH_SOURCE%/*}/g8_common.sh"
seal_ok || exit 2
run g8_swap $PY -I -B $LIB swap
rc=$?
tail -12 "$(ls -t $LOGS/g8_swap.*.log | head -1)"
[ $rc -eq 0 ] || exit $rc
run test_freeze_verify $PY -I -B framelease_v4/protocol/test_freeze.py --verify --jobs-dir $V4/test_jobs \
    --rl-freeze $RL_FREEZE --selection $TUNING --stress-dir $V4/stress --out-dir $V4/test_freeze \
    --queue-dir $Q4/jobs.d
rc=$?
tail -4 "$(ls -t $LOGS/test_freeze_verify.*.log | head -1)"
exit $rc
