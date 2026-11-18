"""Run the applier in-process with subprocess.run patched (scratch-tree fault injection of sim_tree.py).
Environment: INJECT_APPLIER (the scratch applier), INJECT_MODE (kill_after_manifest | kill_before_seal |
touch_after_manifest | break_seal_then_kill | foreign_edit_then_kill | lock_reg_then_kill | lock_all_then_kill),
INJECT_TARGET (the file appended to after --write-manifest, the manifest, PROTOCOL.md or the registration directory of
the tree), INJECT_TARGET2 (lock_all_then_kill: the tree's framelease_v4/, made not writable as well)."""
import os
import runpy
import subprocess
import sys
applier, mode, target = os.environ['INJECT_APPLIER'], os.environ['INJECT_MODE'], os.environ.get('INJECT_TARGET', '')
if not applier.startswith('/tmp/A10A11/') or (target and not os.path.realpath(target).startswith('/tmp/A10A11/')):
    raise SystemExit('inject: refused outside /tmp/A10A11/')
real_run = subprocess.run


def patched(cmd, *a, **k):
    if mode == 'kill_before_seal' and '--seal' in cmd:
        sys.stdout.flush()
        os._exit(137)
    if mode == 'break_seal_then_kill' and '--seal' in cmd:
        with open(target, 'a', encoding='utf-8') as fh:       # PROTOCOL.md no longer cites the manifest's sha256
            fh.write('0' * 64 + '  framelease_v4/zz_scratch_probe_line\n')
        print('inject: appended a line to the manifest, killed before --seal', flush=True)
        os._exit(137)
    if mode == 'foreign_edit_then_kill' and '--seal' in cmd:
        with open(target, 'a', encoding='utf-8') as fh:
            fh.write('\nscratch-tree probe: an edit of PROTOCOL.md by another hand\n')
        print('inject: appended a line to PROTOCOL.md, killed before --seal', flush=True)
        os._exit(137)
    if mode in ('lock_reg_then_kill', 'lock_all_then_kill') and '--seal' in cmd:
        os.chmod(os.path.join(target, 'SEAL.sha256'), 0o444)
        os.chmod(target, 0o555)
        if mode == 'lock_all_then_kill':
            v4 = os.environ['INJECT_TARGET2']
            if not os.path.realpath(v4).startswith('/tmp/A10A11/'):
                raise SystemExit('inject: refused outside /tmp/A10A11/')
            os.chmod(v4, 0o555)
        print(f'inject: SEAL.sha256 read only, registration/ not writable ({mode}), killed before --seal', flush=True)
        os._exit(137)
    r = real_run(cmd, *a, **k)
    if '--write-manifest' in cmd:
        if mode == 'kill_after_manifest':
            print('inject: killed after --write-manifest', flush=True)
            os._exit(137)
        if mode == 'touch_after_manifest':
            with open(target, 'a', encoding='utf-8') as fh:
                fh.write('# scratch-tree probe: changed between the manifest and the seal\n')
            print('inject: appended a line to', target, flush=True)
    return r


subprocess.run = patched
sys.argv = [applier] + sys.argv[1:]
runpy.run_path(applier, run_name='__main__')
