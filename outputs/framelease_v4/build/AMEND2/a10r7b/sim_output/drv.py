"""Functions of the project's phase_driver.py on a scratch tree (sim_tree.py): drv.py refresh|g1 TREE."""
import json
import sys
from pathlib import Path
sys.path.insert(0, '/home/kang/Desktop/DAC')
sys.dont_write_bytecode = True
from framelease_v4.protocol import phase_driver as PD  # noqa: E402
mode, tree = sys.argv[1], Path(sys.argv[2]).resolve()
if not str(tree).startswith('/tmp/A10A11/'):
    raise SystemExit('drv: refused outside /tmp/A10A11/')
cfg = PD.Cfg(PD.parse_args(['--root', str(tree), '--watch-queues', '', '--normal-priority', '--no-consistency-check',
                            '--lock-timeout-s', '5']))
for name in ('protocol', 'protocol_lock', 'reg_dir', 'driver_dir', 'p1_dir', 'jobs_dir', 'analyze_code'):
    if not str(getattr(cfg, name)).startswith(str(tree) + '/'):
        raise SystemExit(f'drv: {name} outside the tree')
ctx = PD.Ctx(cfg)
out = {'mode': mode}
try:
    if mode == 'g1':
        out['result'] = PD.gate_g1(cfg, ctx)
    elif mode == 'refresh':
        old = json.loads(cfg.baseline_path.read_text())['files']
        files = PD.sealed_baseline(cfg, ctx)
        out['result'] = {'files': len(files), 'new': sorted(set(files) - set(old)),
                         'dropped': sorted(set(old) - set(files)),
                         'changed': sorted(q for q in files if q in old and old[q] != files[q])}
except PD.Alert as exc:
    out['alert'] = f'{exc.step}: {exc.problem}'
except PD.Wait as exc:
    out['wait'] = str(exc)
print(json.dumps(out))
