#!/usr/bin/env bash
# Disk watchdog of a framelease_v2/gpu_queue.py runner (framelease_v4/PROTOCOL.md Secs. 8.2, 8.5).
#
#   bash framelease_v4/protocol/disk_watchdog.sh <queue_dir> <runner_pid> [--min-free-gib 5] [--interval-s 30]
#        [--disk-path /home/kang/Desktop/DAC] [--expect-cmd gpu_queue.py]
#
# Every --interval-s seconds it reads the free space of the file system that holds --disk-path (default: the project
# root, the file system the runner checks with --min-free-gib 6). Below --min-free-gib GiB it places <queue_dir>/STOP
# (the runner finishes the running job, then exits; the file names the reason). It never deletes anything and never
# signals any process. It exits when the runner exits: the process <runner_pid>, identified by its start time and by
# its command line containing --expect-cmd, is gone (or a zombie). Started by framelease_v4/protocol/launch_queue.sh;
# log lines (UTC) go to stdout. Exit codes: 0 the runner exited, 2 usage error or <runner_pid> is not the runner.
set -u

usage() {
    sed -n '2,13p' "$0" >&2
    exit 2
}

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
MIN_FREE_GIB=5
INTERVAL_S=30
DISK_PATH="$ROOT"
EXPECT_CMD="gpu_queue.py"
POS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --min-free-gib) MIN_FREE_GIB="${2:?}"; shift 2 ;;
        --interval-s) INTERVAL_S="${2:?}"; shift 2 ;;
        --disk-path) DISK_PATH="${2:?}"; shift 2 ;;
        --expect-cmd) EXPECT_CMD="${2:?}"; shift 2 ;;
        -h|--help) usage ;;
        --*) echo "unknown option $1" >&2; usage ;;
        *) POS+=("$1"); shift ;;
    esac
done
[ "${#POS[@]}" -eq 2 ] || usage
QUEUE="${POS[0]}"
PID="${POS[1]}"
[[ "$PID" =~ ^[0-9]+$ ]] || { echo "runner pid must be an integer: $PID" >&2; exit 2; }
[[ "$INTERVAL_S" =~ ^[0-9]+$ ]] && [ "$INTERVAL_S" -ge 1 ] || { echo "--interval-s must be a positive integer" >&2; exit 2; }
[ -d "$QUEUE" ] || { echo "queue directory not found: $QUEUE" >&2; exit 2; }
QUEUE="$(cd -- "$QUEUE" && pwd)"
MIN_BYTES="$(awk -v g="$MIN_FREE_GIB" 'BEGIN { if (g + 0 <= 0) exit 1; printf "%.0f", g * 1073741824 }')" \
    || { echo "--min-free-gib must be > 0: $MIN_FREE_GIB" >&2; exit 2; }

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) disk_watchdog[$$] $*"; }

start_time() {  # field 22 of /proc/<pid>/stat (after the command name, which may contain spaces)
    local stat
    stat="$(cat "/proc/$1/stat" 2>/dev/null)" || return 1
    stat="${stat##*) }"
    # shellcheck disable=SC2086
    set -- $stat
    [ "$1" != "Z" ] || return 1           # a zombie has exited
    echo "${20}"
}

free_bytes() { df -B1 --output=avail -- "$DISK_PATH" 2>/dev/null | tail -n 1 | tr -d ' '; }

START0="$(start_time "$PID")" || { log "runner pid $PID is not running; nothing to watch"; exit 0; }
CMDLINE="$(tr '\0' ' ' < "/proc/$PID/cmdline" 2>/dev/null)"
case "$CMDLINE" in
    *"$EXPECT_CMD"*) ;;
    *) echo "pid $PID is not the runner (command line '$CMDLINE' lacks '$EXPECT_CMD')" >&2; exit 2 ;;
esac
log "watching runner pid $PID ($CMDLINE); STOP in $QUEUE below $MIN_FREE_GIB GiB free on $DISK_PATH; every $INTERVAL_S s"
placed=0
low=0
while :; do
    now="$(start_time "$PID")" || { log "runner pid $PID exited; watchdog exits"; exit 0; }
    [ "$now" = "$START0" ] || { log "pid $PID was reused by another process; the runner exited; watchdog exits"; exit 0; }
    avail="$(free_bytes)"
    if [[ "$avail" =~ ^[0-9]+$ ]]; then
        gib="$(awk -v b="$avail" 'BEGIN { printf "%.2f", b / 1073741824 }')"
        if [ "$avail" -lt "$MIN_BYTES" ]; then
            if [ ! -e "$QUEUE/STOP" ]; then
                printf '%s disk_watchdog: %s GiB free < %s GiB on %s; the runner stops after the current job\n' \
                    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$gib" "$MIN_FREE_GIB" "$DISK_PATH" > "$QUEUE/.STOP.tmp.$$"
                mv -f "$QUEUE/.STOP.tmp.$$" "$QUEUE/STOP"
                placed=$((placed + 1))
                log "STOP placed: $gib GiB free < $MIN_FREE_GIB GiB"
            elif [ "$low" -eq 0 ]; then
                log "low disk: $gib GiB free < $MIN_FREE_GIB GiB (STOP already present)"
            fi
            low=1
        else
            [ "$low" -eq 0 ] || log "free space back to $gib GiB (STOP, if placed, stays until removed by hand)"
            low=0
        fi
    else
        log "WARNING: cannot read the free space of $DISK_PATH"
    fi
    for _ in $(seq "$INTERVAL_S"); do        # wake every second so the watchdog ends promptly with the runner
        now="$(start_time "$PID")" || break
        [ "$now" = "$START0" ] || break
        sleep 1
    done
done
