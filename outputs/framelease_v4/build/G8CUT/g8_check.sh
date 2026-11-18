#!/bin/bash
# G8CUT step a (RUNBOOK.md Sec. 3): completion check of queue_p4 under Amendment A12. Job health only (Sec. 9.11).
#   cd /home/kang/Desktop/DAC && bash outputs/framelease_v4/build/G8CUT/g8_check.sh [reduced|registered]
# reduced (default): before the swap, jobs.d holds the six A12 reduced job files; registered: after g8_swap.sh.
# Exit 0 READY, 3 NOT FINAL (wait and run again), 2 PROBLEM (read the log), 99 no root.
source "${BASH_SOURCE%/*}/g8_common.sh"
EXPECT=${1:-reduced}
seal_ok || exit 2
run g8_check $PY -I -B $LIB check --expect "$EXPECT"
rc=$?
sed -n '/^{/,/^CHECK/p' "$(ls -t $LOGS/g8_check.*.log | head -1)" | tail -40
exit $rc
