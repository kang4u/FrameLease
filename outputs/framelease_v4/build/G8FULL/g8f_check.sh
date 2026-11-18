#!/bin/bash
# G8FULL step a (RUNBOOK.md Sec. 3): completion check of queue_p4 under Amendment A17. Job health only (Sec. 9.11).
#   cd /home/kang/Desktop/DAC && bash outputs/framelease_v4/build/G8FULL/g8f_check.sh [final|stopped]
# final (default): before queue_p4/STOP; stopped: after g8f_stop.sh. Also checks that the first freeze (Amendment A13)
# is valid and unchanged. Exit 0 READY, 3 NOT FINAL (wait and run again), 2 PROBLEM (read the log), 99 no root.
source "${BASH_SOURCE%/*}/g8f_common.sh"
EXPECT=${1:-final}
seal_ok || exit 2
run g8f_check $PY -I -B $LIB check --expect "$EXPECT"
rc=$?
grep -E '"(final|pending|runner_alive|runner_lock_held|stop_file|last_runner_exit|first_freeze_final_jobs|next_amendment)"|^CHECK|^ *"[^"]*(wait|missing|differ|not )' "$(lastlog g8f_check)" | head -30
exit $rc
