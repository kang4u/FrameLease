"""Compare environment variable NAMES (values not printed) of the running P1 stage driver, a running closed-loop job
and this shell (the coordinating session's kind of shell), for RUNBOOK step 6 (read only: /proc/<pid>/environ)."""
import os, re, sys
def env_of(pid):
    try:
        raw = open(f'/proc/{pid}/environ', 'rb').read().split(b'\0')
    except OSError as e:
        return None
    return dict(x.decode(errors='replace').split('=', 1) for x in raw if b'=' in x)
def find(pattern):
    for d in os.listdir('/proc'):
        if d.isdigit():
            try:
                cmd = open(f'/proc/{d}/cmdline', 'rb').read().replace(b'\0', b' ').decode(errors='replace')
            except OSError:
                continue
            if re.search(pattern, cmd) and 'env_compare' not in cmd:
                return int(d), cmd[:100]
    return None, None
p1, p1cmd = find(r'framelease_v4/protocol/p1_driver\.py')
job, jobcmd = find(r'run_closed_loop_v4\.py')
e_p1, e_job, e_sh = env_of(p1) or {}, env_of(job) or {}, dict(os.environ)
print('p1_driver pid', p1, '| job pid', job, (jobcmd or '')[:60])
relevant = re.compile(r'^(OMP|MKL|OPENBLAS|NUMEXPR|VECLIB|GOTO|BLIS)_|^CUDA|^PYTORCH|^TORCH|^PYTHON|^LD_|^MALLOC|^HF_|'
                      r'^TRANSFORMERS|^TOKENIZERS|^KMP_|^NCCL|^XLA|^TF_|^LC_|^LANG$|^TZ$|^PATH$|^HOME$')
for name, other in (('this shell', e_sh), ('closed-loop job', e_job)):
    extra = sorted(k for k in other if k not in e_p1)
    miss = sorted(k for k in e_p1 if k not in other)
    print(f'{name}: {len(other)} names; not in the P1 driver: {len(extra)}; relevant among them: '
          f'{[k for k in extra if relevant.search(k)]}')
    print(f'   names of the P1 driver missing here: {len(miss)}; relevant among them: '
          f'{[k for k in miss if relevant.search(k)]}')
    diff = sorted(k for k in other if k in e_p1 and other[k] != e_p1[k] and relevant.search(k))
    print(f'   relevant names with a different value: {diff}')
print('P1 driver relevant names:', sorted(k for k in e_p1 if relevant.search(k)))
