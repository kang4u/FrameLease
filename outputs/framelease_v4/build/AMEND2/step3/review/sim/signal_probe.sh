#!/bin/bash
# Which signal does a command receive when the tool that runs it times out? A parent bash and a child python, each
# recording the signals they get into /tmp/AMEND3_review/signal_probe.log (the parent's own process group is printed).
LOG=/tmp/AMEND3_review/signal_probe.log
: > "$LOG"
echo "parent pid $$ pgid $(ps -o pgid= -p $$ | tr -d ' ') sid $(ps -o sid= -p $$ | tr -d ' ')" >> "$LOG"
for s in TERM HUP INT; do trap "echo \"parent got SIG$s at \$(date +%T.%N)\" >> $LOG" $s; done
/home/kang/Desktop/DAC/.conda-unidrive-linux/bin/python -I -B -c "
import signal, time, os
log = open('$LOG', 'a', buffering=1)
log.write(f'child pid {os.getpid()} pgid {os.getpgid(0)}\n')
for s in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
    signal.signal(s, lambda n, f: log.write(f'child got {signal.Signals(n).name} at {time.strftime(\"%H:%M:%S\")}\n'))
t0 = time.time()
while time.time() - t0 < 30:
    time.sleep(0.2)
log.write('child ended normally\n')
" &
wait
echo "parent ended" >> "$LOG"
