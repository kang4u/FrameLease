#!/bin/bash
# The RUNBOOK block (launch with "> console.txt ... &", then grep in the same shell) against a console.txt left by an
# earlier attempt: how often does the first grep read the earlier attempt's exit line? Scratch directory only.
d=/tmp/A10A11/recheck1/race
mkdir -p "$d" && cd "$d" || exit 1
n=0
stale=0
for i in $(seq 1 40); do
    echo "apply_locked: exit 93 (output of the earlier attempt)" > console.txt
    setsid nohup bash -c 'sleep 0.3; echo "apply_locked: exit 0 (this attempt)"' > console.txt 2>&1 < /dev/null &
    out=$(grep 'apply_locked: exit' console.txt)
    case "$out" in *earlier*) stale=$((stale + 1)) ;; esac
    n=$((n + 1))
    sleep 0.5
done
echo "$stale of $n first greps right after the launch read the earlier attempt's exit line"
rm -f console.txt
