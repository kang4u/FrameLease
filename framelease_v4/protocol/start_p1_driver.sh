#!/usr/bin/env bash
# Start the P1 stage driver (framelease_v4/protocol/p1_driver.py) detached: setsid nohup, output appended to
# outputs/framelease_v4/p1_driver/driver.nohup.log (the driver's own log is driver.log, its state
# outputs/framelease_v4/pipeline_state.json). One instance only: the driver holds an exclusive flock on
# outputs/framelease_v4/p1_driver/driver.lock for its lifetime; this script refuses while that lock is held (flock test)
# and the driver itself refuses to run a second time. Concurrent starts are serialized by a flock on start.lock. The
# driver writes its pid into driver.pid once it holds the lock.
#
#   cd /home/kang/Desktop/DAC
#   bash framelease_v4/protocol/start_p1_driver.sh [p1_driver.py options, e.g. --interval-s 300]
#
# Stop: touch outputs/framelease_v4/p1_driver/STOP (the driver exits at its next check; remove STOP before a new start),
# or kill <pid in driver.pid> (SIGTERM: it exits at the next safe point). Refuses to start while
# outputs/framelease_v4/p1_driver/ALERT.txt or STOP exists; does nothing once P1_DONE.json exists. Start it at normal
# priority (no nice): the runner it may launch inherits its priority, and the driver refuses to run niced.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$ROOT/.conda-unidrive-linux/bin/python"
DIR="$ROOT/outputs/framelease_v4/p1_driver"
LOCK="$DIR/driver.lock"
PIDF="$DIR/driver.pid"
LOG="$DIR/driver.nohup.log"
for a in "$@"; do
    case "$a" in
        --dry-run|--once) echo "start_p1_driver: run p1_driver.py $a in the foreground instead" >&2; exit 2 ;;
        -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    esac
done
cd "$ROOT"
mkdir -p "$DIR"
exec 8>>"$DIR/start.lock"
flock -n 8 || { echo "start_p1_driver: another start_p1_driver.sh is running right now" >&2; exit 2; }
[ -x "$PY" ] || { echo "start_p1_driver: interpreter not found: $PY" >&2; exit 2; }
[ ! -e "$DIR/ALERT.txt" ] || { echo "start_p1_driver: $DIR/ALERT.txt exists: resolve it, move it aside, then start" >&2; exit 2; }
[ ! -e "$DIR/STOP" ] || { echo "start_p1_driver: $DIR/STOP exists: remove it to start the driver" >&2; exit 2; }
if [ -e "$DIR/P1_DONE.json" ]; then echo "start_p1_driver: P1 is done ($DIR/P1_DONE.json); nothing to start"; exit 0; fi
if [ -e "$LOCK" ] && ! flock -n "$LOCK" true; then
    echo "start_p1_driver: another p1_driver holds $LOCK ($(cat "$LOCK" 2>/dev/null))" >&2
    exit 2
fi
rm -f "$PIDF"                           # stale (no driver holds the lock); the new driver writes its own pid
unset P1_DRIVER_TEST_CRASH_AT P1_DRIVER_TEST_TOUCH_AT
# fd 8 (start.lock) is not passed on: the driver's own lock is driver.lock
setsid nohup "$PY" -I -B framelease_v4/protocol/p1_driver.py "$@" >> "$LOG" 2>&1 < /dev/null 8>&- &
SPAWN=$!
for _ in $(seq 60); do
    sleep 0.5
    pid="$(cat "$PIDF" 2>/dev/null || true)"
    if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null \
            && [[ "$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null)" == *p1_driver.py* ]]; then
        echo "started p1_driver pid $pid (lock $LOCK: $(cat "$LOCK" 2>/dev/null))"
        echo "logs: $DIR/driver.log  $LOG   state: $ROOT/outputs/framelease_v4/pipeline_state.json"
        echo "stop: touch $DIR/STOP   (or kill $pid)"
        exit 0
    fi
    kill -0 "$SPAWN" 2>/dev/null || break
done
echo "start_p1_driver: the driver did not start (or exited at once); see $LOG and $DIR/driver.log:" >&2
tail -n 20 "$LOG" >&2 || true
exit 1
