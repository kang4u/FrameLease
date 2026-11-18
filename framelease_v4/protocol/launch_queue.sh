#!/usr/bin/env bash
# Start the GPU job runner on a queue directory, with the disk watchdog (framelease_v4/PROTOCOL.md Secs. 8.2, 8.5).
#
#   cd /home/kang/Desktop/DAC
#   bash framelease_v4/protocol/launch_queue.sh <queue_dir> [--dry-run]
#
# 1. sources linux/env.sh (official stack variables: the runner refuses to start without them);
# 2. refuses to start if <queue_dir>/STOP exists (remove it by hand after checking the disk), if another runner
#    holds <queue_dir>/runner.lock, or if <queue_dir>/jobs.d/ holds no *.jsonl job file;
# 3. starts, detached (setsid nohup), the unchanged runner
#      .conda-unidrive-linux/bin/python -I -B framelease_v2/gpu_queue.py --queue-dir <queue_dir> --exit-when-empty \
#          --min-free-gib 6
#    with stdout / stderr appended to <queue_dir>/runner.nohup.log (the runner's own progress log is
#    <queue_dir>/runner.log, its records <queue_dir>/status.jsonl);
# 4. starts, detached, framelease_v4/protocol/disk_watchdog.sh <queue_dir> <runner pid> (STOP below 5 GiB free;
#    it exits when the runner exits), log <queue_dir>/disk_watchdog.log;
# 5. writes <queue_dir>/launch_<UTC>.json (commands, pids, free disk, sha256 of the runner, of the watchdog and of
#    every job file in jobs.d/) and prints the pids and log paths.
# --dry-run prints the checks and the two commands and starts nothing. This script never writes job files: copy the
# registered job files into <queue_dir>/jobs.d/ first (outputs/framelease_v4/p1_jobs/README.md).
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$ROOT/.conda-unidrive-linux/bin/python"
MIN_FREE_GIB_RUNNER=6
MIN_FREE_GIB_WATCHDOG=5
DRY=0
POS=()
for a in "$@"; do
    case "$a" in
        --dry-run) DRY=1 ;;
        -h|--help) sed -n '2,21p' "$0"; exit 0 ;;
        --*) echo "unknown option $a" >&2; exit 2 ;;
        *) POS+=("$a") ;;
    esac
done
[ "${#POS[@]}" -eq 1 ] || { sed -n '2,21p' "$0" >&2; exit 2; }
cd "$ROOT"
QUEUE="${POS[0]}"
case "$QUEUE" in /*) ;; *) QUEUE="$ROOT/$QUEUE" ;; esac
QUEUE="${QUEUE%/}"

# shellcheck disable=SC1091
source "$ROOT/linux/env.sh"

fail() { echo "launch_queue: $*" >&2; exit 2; }
[ -x "$PY" ] || fail "interpreter not found: $PY"
[ -d "$QUEUE/jobs.d" ] || fail "$QUEUE/jobs.d not found: create it and copy the job files of the block into it"
shopt -s nullglob
JOBS=("$QUEUE"/jobs.d/*.jsonl)
shopt -u nullglob
[ "${#JOBS[@]}" -gt 0 ] || fail "no *.jsonl job file in $QUEUE/jobs.d"
[ ! -e "$QUEUE/STOP" ] || fail "$QUEUE/STOP exists ($(head -c 300 "$QUEUE/STOP")); check the disk, then remove it by hand"
if [ -e "$QUEUE/runner.lock" ] && ! flock -n "$QUEUE/runner.lock" true; then
    fail "another runner holds $QUEUE/runner.lock ($(cat "$QUEUE/runner.lock" 2>/dev/null))"
fi
FREE_GIB="$(df -B1 --output=avail -- "$ROOT" | tail -n 1 | awk '{ printf "%.2f", $1 / 1073741824 }')"
RUNNER_CMD=("$PY" -I -B framelease_v2/gpu_queue.py --queue-dir "$QUEUE" --exit-when-empty --min-free-gib "$MIN_FREE_GIB_RUNNER")
WATCHDOG_CMD=(bash framelease_v4/protocol/disk_watchdog.sh "$QUEUE" "<runner pid>" --min-free-gib "$MIN_FREE_GIB_WATCHDOG")
echo "queue:      $QUEUE"
echo "job files:  ${JOBS[*]##*/}"
echo "free disk:  $FREE_GIB GiB (the runner starts no job below $MIN_FREE_GIB_RUNNER GiB; STOP below $MIN_FREE_GIB_WATCHDOG GiB)"
awk -v f="$FREE_GIB" -v m="$MIN_FREE_GIB_RUNNER" 'BEGIN { exit !(f < m) }' \
    && echo "WARNING: less than $MIN_FREE_GIB_RUNNER GiB free: the runner will wait for space" >&2
echo "runner:     ${RUNNER_CMD[*]} >> $QUEUE/runner.nohup.log 2>&1"
echo "watchdog:   ${WATCHDOG_CMD[*]} >> $QUEUE/disk_watchdog.log 2>&1"
if [ "$DRY" -eq 1 ]; then
    echo "dry run: nothing started"
    exit 0
fi

UTC="$(date -u +%Y%m%dT%H%M%SZ)"
setsid nohup "${RUNNER_CMD[@]}" >> "$QUEUE/runner.nohup.log" 2>&1 < /dev/null &
SPAWN_PID=$!
# the runner writes "pid <pid> started <utc>" into runner.lock once it holds the lock: that pid is the one watched
RUNNER_PID=""
for _ in $(seq 20); do
    sleep 0.5
    cand="$(awk '$1 == "pid" { print $2; exit }' "$QUEUE/runner.lock" 2>/dev/null || true)"
    if [[ "$cand" =~ ^[0-9]+$ ]] && kill -0 "$cand" 2>/dev/null; then
        cmdline="$(tr '\0' ' ' < "/proc/$cand/cmdline" 2>/dev/null || true)"
        if [[ "$cmdline" == *"gpu_queue.py --queue-dir $QUEUE "* ]]; then
            RUNNER_PID="$cand"
            break
        fi
    fi
    kill -0 "$SPAWN_PID" 2>/dev/null || break
done
if [ -z "$RUNNER_PID" ]; then
    echo "launch_queue: the runner did not start (or exited at once); see $QUEUE/runner.nohup.log:" >&2
    tail -n 20 "$QUEUE/runner.nohup.log" >&2 || true
    exit 1
fi
WATCHDOG_CMD[3]="$RUNNER_PID"
setsid nohup "${WATCHDOG_CMD[@]}" >> "$QUEUE/disk_watchdog.log" 2>&1 < /dev/null &
WATCHDOG_PID=$!
sleep 1
kill -0 "$WATCHDOG_PID" 2>/dev/null || echo "WARNING: the disk watchdog exited at once; see $QUEUE/disk_watchdog.log" >&2
kill -0 "$RUNNER_PID" 2>/dev/null || echo "WARNING: the runner has already exited; see $QUEUE/runner.nohup.log and $QUEUE/runner.log" >&2

"$PY" -I -B - "$QUEUE" "$UTC" "$RUNNER_PID" "$WATCHDOG_PID" "$FREE_GIB" "${RUNNER_CMD[*]}" "${WATCHDOG_CMD[*]}" <<'PYEOF'
import hashlib, json, sys
from pathlib import Path
q, utc, rpid, wpid, free, rcmd, wcmd = sys.argv[1:8]
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
root = Path(q).resolve()
proj = Path.cwd()
rec = {'schema': 'framelease_v4.launch_queue/1', 'utc': utc, 'queue': str(root), 'runner_pid': int(rpid),
       'watchdog_pid': int(wpid), 'free_disk_gib': float(free), 'runner_cmd': rcmd, 'watchdog_cmd': wcmd,
       'runner_sha256': sha(proj / 'framelease_v2/gpu_queue.py'),
       'watchdog_sha256': sha(proj / 'framelease_v4/protocol/disk_watchdog.sh'),
       'launcher_sha256': sha(proj / 'framelease_v4/protocol/launch_queue.sh'),
       'job_files': {p.name: sha(p) for p in sorted((root / 'jobs.d').glob('*.jsonl'))}}
(root / f'launch_{utc}.json').write_text(json.dumps(rec, indent=1, sort_keys=True) + '\n')
PYEOF
echo "started runner pid $RUNNER_PID and disk watchdog pid $WATCHDOG_PID"
echo "logs: $QUEUE/runner.log  $QUEUE/runner.nohup.log  $QUEUE/disk_watchdog.log  $QUEUE/status.jsonl"
echo "launch record: $QUEUE/launch_$UTC.json"
echo "state: $PY -I -B framelease_v2/gpu_queue.py --queue-dir $QUEUE --list"
