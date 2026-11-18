"""Wait until no process of process group PGID is left (max 180 s); print the members seen."""
import os, sys, time
pg = int(sys.argv[1])
t0, seen = time.time(), set()
while time.time() - t0 < 180:
    alive = []
    for d in os.listdir('/proc'):
        if d.isdigit():
            try:
                st = open(f'/proc/{d}/stat').read()
                fields = st[st.rindex(')') + 2:].split()
                if int(fields[2]) == pg:
                    alive.append(d)
                    seen.add(open(f'/proc/{d}/cmdline', 'rb').read().split(b'\0')[0].decode()[-40:])
            except (OSError, ValueError, IndexError):
                pass
    if not alive:
        print(f'group {pg} empty after {time.time() - t0:.1f} s; members seen: {sorted(seen)}')
        sys.exit(0)
    time.sleep(0.1)
print('timeout'); sys.exit(3)
