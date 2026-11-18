"""Fake the end of P1 in a scratch copy of the project (step-3 simulation; refuses any root outside /tmp/AMEND3/).

  taskset -c 12-15 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      outputs/framelease_v4/build/AMEND2/step3/sim/fake_p1_end.py /tmp/AMEND3/tree

In the scratch root, with the scratch copy of the P1 stage driver's own code (framelease_v4/protocol/p1_driver.py,
imported from the scratch root, --normal-priority so that its tools inherit this process's E-core / nice 19 / idle
I/O priority):
  * a FAKE tuning freeze outputs/framelease_v4/tuning/selection.json (L* B0, d* 1 and Event-Triggered s_hb2.0 as
    selected; fl_risk E5 by the lease_s1 means; A* 1.0 s stands in for the age_s2 selection, which does not exist yet);
  * the driver's "Tuning freeze" entry recorded by p1_driver.ensure_recorded (lock, write-manifest, entry, seal,
    verify), as the driver records it;
  * a FAKE D1 summary outputs/framelease_v4/tuning/d1/FULL_d1_summary.{json,md} and the "D1 summary" entry, the same
    way;
  * P1_DONE.json by p1_driver.write_done, and p1_driver/driver.lock naming a pid that is not alive (the state after the
    driver has exited).
Every fake file carries "simulation": FAKE_NOTE. Nothing outside the scratch root is written.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

FAKE_NOTE = 'FAKE: written by the step-3 simulation in /tmp/AMEND3 only; not a P1 result'


def main():
    root = Path(sys.argv[1]).resolve()
    if not str(root).startswith('/tmp/AMEND3/'):
        print(f'refused: {root} is not under /tmp/AMEND3/')
        return 2
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root))
    from framelease_v4.protocol import p1_driver as P1
    if not str(Path(P1.__file__).resolve()).startswith(str(root)):
        print(f'refused: p1_driver imported from {P1.__file__}')
        return 2
    cfg = P1.Cfg(P1.parse_args(['--root', str(root), '--normal-priority', '--no-chain-check']))
    ctx = P1.Ctx(cfg, None, echo=True)
    b0 = {'label': 'B0', 'path': 'outputs/framelease_v4/envelopes/B0.json', 'config': 'T_x0.00',
          'sha256': P1.sha256_file(root / 'outputs/framelease_v4/envelopes/B0.json')}
    stages = {s: {'path': cfg.rel(cfg.selection_path(s)),
                  'sha256': P1.sha256_file(cfg.selection_path(s)) if cfg.selection_path(s).is_file() else None}
              for s in P1.STAGES}
    event_pp = {'det_shift_m': 1.0, 'heartbeat_s': 2.0, 'speed_delta_mps': 0.5, 'yaw_delta_rad': 0.05}
    doc = {'schema': P1.FREEZE_SCHEMA, 'variant': P1.VARIANT, 'simulation': FAKE_NOTE,
           'written': P1.now_iso(),
           'L_star': {'label': 'B0', 'envelope_path': b0['path'], 'envelope_sha256': b0['sha256'],
                      'config': b0['config'],
                      'validity': 'std'},
           'd_star': {'d': 1, 'utility': 'v4_adet_d1'},
           'A_star': {'age_lease_s': 1.0},
           'event_star': {'candidate': 's_hb2.0', 'policy_params': event_pp},
           'fl_risk': {'lease_point': 'E5',
                       'rule': 'L* = B0: fl_risk runs the better of E5 / E10 by mean DS on lease_s1 (T22a), ties '
                               'earlier'},
           'stages': stages, 'flags': {}}
    P1.atomic_write(cfg.freeze_path, json.dumps(doc, indent=1, sort_keys=True) + '\n')
    fsha = P1.sha256_file(cfg.freeze_path)
    print(f'fake tuning freeze {cfg.rel(cfg.freeze_path)} sha256 {fsha}')
    r = P1.ensure_recorded(cfg, ctx, 'freeze', fsha, lambda: P1.freeze_entry(cfg, doc, fsha))
    print(f'Tuning freeze entry: {r}')
    blocks = [{'block': b, 'block_no': n, 'pending': 0, 'simulation': FAKE_NOTE} for b, n in P1.BLOCK_NO.items()]
    ddoc = {'schema': P1.D1_SCHEMA, 'variant': P1.VARIANT, 'simulation': FAKE_NOTE, 'written': P1.now_iso(),
            'tuning_freeze': {'path': cfg.rel(cfg.freeze_path), 'sha256': fsha}, 'blocks': blocks}
    jpath, mpath = cfg.d1_paths()
    jpath.parent.mkdir(parents=True, exist_ok=True)
    P1.atomic_write(jpath, json.dumps(ddoc, indent=1, sort_keys=True) + '\n')
    P1.atomic_write(mpath, f'# D1 summary (FULL)\n\n{FAKE_NOTE}\n')
    jsha, msha = P1.sha256_file(jpath), P1.sha256_file(mpath)
    print(f'fake D1 summary {cfg.rel(jpath)} sha256 {jsha}; {cfg.rel(mpath)} sha256 {msha}')
    r = P1.ensure_recorded(cfg, ctx, 'd1', jsha, lambda: P1.d1_entry(cfg, ddoc, jsha, msha, fsha))
    print(f'D1 summary entry: {r}')
    P1.write_done(cfg, ctx, doc, fsha, (ddoc, jsha, msha))
    done = json.loads(cfg.done_path.read_text(encoding='utf-8'))
    done['simulation'] = FAKE_NOTE
    P1.atomic_write(cfg.done_path, json.dumps(done, indent=1, sort_keys=True) + '\n')
    dead = next(p for p in range(4_000_000, 4_100_000) if not os.path.exists(f'/proc/{p}'))
    cfg.lock_path.write_text(f'pid {dead} started 2026-11-14T21:55:18+0800\n', encoding='utf-8')
    print(f'P1_DONE.json written; driver.lock names pid {dead} (not alive)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
