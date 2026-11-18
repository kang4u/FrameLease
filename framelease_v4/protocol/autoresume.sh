#!/usr/bin/env bash
# Guarded auto-resume of FrameLease v4 queues after a reboot or a power loss (user request of 2026-11-10: survive a
# pause or a power cut). Operational tooling only: it changes no run, no criterion and no job file.
#
# Installed as one user crontab line (crontab -l shows it):
#   @reboot /bin/bash /home/kang/Desktop/DAC/framelease_v4/protocol/autoresume.sh >> /home/kang/Desktop/DAC/outputs/framelease_v4/autoresume.log 2>&1
#
# It does something only while outputs/framelease_v4/AUTORESUME exists. That file lists queue directories, one per
# line, relative to the project root ('#' starts a comment). To disable it, delete that file, or remove the crontab line
# with `crontab -e`.
#
# For every listed queue that has a jobs.d/, no STOP file and pending or interrupted jobs, it runs
# framelease_v4/protocol/launch_queue.sh <queue>. That wrapper refuses a queue whose runner.lock is still held (flock),
# sources linux/env.sh and starts the runner with the disk watchdog. The runner skips final jobs and re-runs
# interrupted attempts without using up their attempt budget. CARLA is started off-screen by the evaluator
# (-RenderOffScreen), so no desktop session is needed.
#
# Usage: autoresume.sh [--dry-run]     (--dry-run prints the decision per queue and launches nothing)
set -u
ROOT=/home/kang/Desktop/DAC
FLAG="$ROOT/outputs/framelease_v4/AUTORESUME"
PY="$ROOT/.conda-unidrive-linux/bin/python"
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

echo "=== autoresume $(date '+%F %T %z') dry_run=$DRY ==="
[ -f "$FLAG" ] || { echo "disabled: $FLAG does not exist"; exit 0; }
cd "$ROOT" || { echo "cannot cd to $ROOT"; exit 1; }

if [ "$DRY" -eq 0 ]; then
    # let the system settle: the GPU driver must answer; give a desktop session up to 10 minutes to appear (not required)
    for _ in $(seq 90); do nvidia-smi >/dev/null 2>&1 && break; sleep 10; done
    nvidia-smi >/dev/null 2>&1 || { echo "GPU not available after 15 minutes; nothing launched"; exit 1; }
    for _ in $(seq 60); do pgrep -u "$(id -u)" -x gnome-shell >/dev/null 2>&1 && break; sleep 10; done
    sleep "${AUTORESUME_EXTRA_DELAY_S:-120}"
fi

while IFS= read -r line || [ -n "$line" ]; do
    q="${line%%#*}"
    q="$(echo "$q" | xargs)"
    [ -z "$q" ] && continue
    if [ ! -d "$q/jobs.d" ]; then echo "skip $q: no jobs.d"; continue; fi
    if [ -f "$q/STOP" ]; then echo "skip $q: STOP present (check the disk, then remove STOP by hand)"; continue; fi
    counts="$("$PY" -I -B framelease_v2/gpu_queue.py --list --queue-dir "$q" 2>/dev/null | grep '^counts:' || true)"
    echo "$q $counts"
    if echo "$counts" | grep -q -E '"pending"|"RUNNING"|"interrupted"'; then
        if [ "$DRY" -eq 1 ]; then
            echo "would run: bash framelease_v4/protocol/launch_queue.sh $q"
        else
            bash framelease_v4/protocol/launch_queue.sh "$q" || echo "launch_queue.sh refused or failed for $q"
        fi
    else
        echo "nothing to resume in $q"
    fi
done < "$FLAG"
echo "=== autoresume done $(date '+%F %T %z') ==="
