#!/usr/bin/env bash
# Start the phase driver (framelease_v4/protocol/phase_driver.py: the gates G0-G8 after P1) detached, in a dedicated
# systemd user scope with OOMPolicy=continue, so that a kernel OOM kill of another process never stops it
# (outputs/framelease_v4/validity_notes/oom_20261112.md; the P1 driver was moved the same way by
# outputs/framelease_v4/paper_tools/relaunch_isolated.sh):
#   setsid nohup systemd-run --user --scope --unit=framelease-phase-driver-<ts> -p OOMPolicy=continue \
#       .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/phase_driver.py [options]
# Output is appended to outputs/framelease_v4/phase_driver/driver.nohup.log (the driver's own log is driver.log, its
# state state.json). One instance only: the driver holds an exclusive flock on outputs/framelease_v4/phase_driver/
# driver.lock for its lifetime; this script refuses while that lock is held (flock test) and the driver itself refuses
# to run a second time. Concurrent starts are serialized by a flock on start.lock. The driver writes its pid into
# driver.pid once it holds the lock.
#
#   cd /home/kang/Desktop/DAC
#   bash framelease_v4/protocol/start_phase_driver.sh [phase_driver.py options, e.g. --interval-s 300]
#
# Stop: touch outputs/framelease_v4/phase_driver/STOP (the driver exits at its next check; remove STOP before a new
# start), or kill <pid in driver.pid> (SIGTERM: it exits at the next safe point). Refuses to start while
# outputs/framelease_v4/phase_driver/ALERT.txt or STOP exists; does nothing once P2_STOPPED.json (D1 = stop) or
# PHASES_DONE.json exists. Start it at normal priority (nice 0) on every CPU (no taskset pinning): the runners it
# launches (queue_p2, queue_p4: CARLA and the evaluator) inherit both, and the script and the driver refuse a niced or
# CPU-pinned start. The tools it runs get their own priority (P3 and the stress tests: every core at nice 10).
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$ROOT/.conda-unidrive-linux/bin/python"
DIR="$ROOT/outputs/framelease_v4/phase_driver"
LOCK="$DIR/driver.lock"
PIDF="$DIR/driver.pid"
LOG="$DIR/driver.nohup.log"
SYSTEMD_RUN=systemd-run
# tests only: a stand-in for systemd-run, honoured only in a sandbox copy of this script (never in the project tree)
if [ -n "${PHASE_DRIVER_TEST_SYSTEMD_RUN:-}" ] && [ "$ROOT" != "/home/kang/Desktop/DAC" ]; then
    SYSTEMD_RUN="$PHASE_DRIVER_TEST_SYSTEMD_RUN"
fi
ALLOW_NICE=0
for a in "$@"; do
    case "$a" in
        --dry-run|--once) echo "start_phase_driver: run phase_driver.py $a in the foreground instead" >&2; exit 2 ;;
        --allow-nice-launch) ALLOW_NICE=1 ;;
        -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    esac
done
cd "$ROOT"
mkdir -p "$DIR"
exec 8>>"$DIR/start.lock"
flock -n 8 || { echo "start_phase_driver: another start_phase_driver.sh is running right now" >&2; exit 2; }
[ -x "$PY" ] || { echo "start_phase_driver: interpreter not found: $PY" >&2; exit 2; }
command -v "$SYSTEMD_RUN" > /dev/null || { echo "start_phase_driver: $SYSTEMD_RUN not found" >&2; exit 2; }
[ ! -e "$DIR/ALERT.txt" ] || { echo "start_phase_driver: $DIR/ALERT.txt exists: resolve it, move it aside, then start" >&2; exit 2; }
[ ! -e "$DIR/STOP" ] || { echo "start_phase_driver: $DIR/STOP exists: remove it to start the driver" >&2; exit 2; }
if [ -e "$DIR/P2_STOPPED.json" ]; then echo "start_phase_driver: D1 = stop ($DIR/P2_STOPPED.json); nothing to start"; exit 0; fi
if [ -e "$DIR/PHASES_DONE.json" ]; then echo "start_phase_driver: every phase is done ($DIR/PHASES_DONE.json); nothing to start"; exit 0; fi
# the CPUs this shell may run on (nproc without OMP_NUM_THREADS / OMP_THREAD_LIMIT, which nproc would otherwise honour)
NCPU="$(env -u OMP_NUM_THREADS -u OMP_THREAD_LIMIT nproc)"
if [ "$NCPU" != "$(nproc --all)" ] && [ "$ALLOW_NICE" -eq 0 ]; then
    echo "start_phase_driver: this shell is pinned to $NCPU of $(nproc --all) CPUs (CPU affinity: $(LC_ALL=C taskset -pc $$ 2>/dev/null | sed 's/.*: //')); start the driver without taskset (its runners inherit the affinity)" >&2
    exit 2
fi
if [ "$(nice)" != 0 ] && [ "$ALLOW_NICE" -eq 0 ]; then
    echo "start_phase_driver: this shell runs at nice $(nice); start the driver at nice 0 (its runners inherit it)" >&2
    exit 2
fi
if [ -e "$LOCK" ] && ! flock -n "$LOCK" true; then
    echo "start_phase_driver: another phase_driver holds $LOCK ($(cat "$LOCK" 2>/dev/null))" >&2
    exit 2
fi
rm -f "$PIDF"                           # stale (no driver holds the lock); the new driver writes its own pid
unset PHASE_DRIVER_TEST_CRASH_AT PHASE_DRIVER_TEST_TOUCH_AT
UNIT="framelease-phase-driver-$(date +%Y%m%dT%H%M%S)"
# fd 8 (start.lock) is not passed on: the driver's own lock is driver.lock
setsid nohup "$SYSTEMD_RUN" --user --scope --unit="$UNIT" -p OOMPolicy=continue \
    "$PY" -I -B framelease_v4/protocol/phase_driver.py "$@" >> "$LOG" 2>&1 < /dev/null 8>&- &
SPAWN=$!
for _ in $(seq 60); do
    sleep 0.5
    pid="$(cat "$PIDF" 2>/dev/null || true)"
    if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null \
            && [[ "$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null)" == *phase_driver.py* ]]; then
        echo "started phase_driver pid $pid in scope $UNIT (lock $LOCK: $(cat "$LOCK" 2>/dev/null))"
        echo "cgroup: $(cat "/proc/$pid/cgroup" 2>/dev/null | tail -n 1)"
        echo "logs: $DIR/driver.log  $LOG   state: $DIR/state.json"
        echo "stop: touch $DIR/STOP   (or kill $pid)"
        exit 0
    fi
    kill -0 "$SPAWN" 2>/dev/null || break
done
echo "start_phase_driver: the driver did not start (or exited at once); see $LOG and $DIR/driver.log:" >&2
tail -n 20 "$LOG" >&2 || true
exit 1
