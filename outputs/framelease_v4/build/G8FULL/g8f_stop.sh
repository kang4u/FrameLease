#!/bin/bash
# G8FULL step b (RUNBOOK.md Sec. 4): queue_p4/STOP once every job of the six registered job files is final and the
# runner has exited (no runner ever starts in queue_p4 again), then the phase driver's G6 verification on jobs.d.
#   cd /home/kang/Desktop/DAC && bash outputs/framelease_v4/build/G8FULL/g8f_stop.sh
# Refuses (exit 3 / 2) unless g8f_lib.py check is READY; idempotent once STOP exists. Exit 0 done.
source "${BASH_SOURCE%/*}/g8f_common.sh"
seal_ok || exit 2
run g8f_stop $PY -I -B $LIB stop
rc=$?
grep -E '^(STOP|CHECK)' "$(lastlog g8f_stop)"
[ $rc -eq 0 ] || exit $rc
run test_freeze_verify $PY -I -B framelease_v4/protocol/test_freeze.py --verify --jobs-dir $V4/test_jobs \
    --rl-freeze $RL_FREEZE --selection $TUNING --stress-dir $V4/stress --out-dir $V4/test_freeze \
    --queue-dir $Q4/jobs.d
rc=$?
tail -4 "$(lastlog test_freeze_verify)"
exit $rc
