"""Exported lease operating points E5 / E10 / B0 (PROTOCOL Sec. 4.3; framelease_v4/offline/export_envelopes.py).

  cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/offline/tests/test_export_envelopes.py

What is shown (CPU only, reads the offline outputs and the C1 sweep view, writes only to a temporary directory):
  * the exported files are what framelease_v3/runtime v3_lease.load_envelope reads, carry exactly the offline TRAIN
    configurations T_x0.60 / T_x0.30 / T_x0.00 picked by the frontier rows (alpha 0.05 / 0.10) and match the manifest's
    sha256; a re-export is byte-identical;
  * the pruning rules of Sec. 4.3;
  * the runtime lease with an exported envelope reproduces the offline tau* and H on recorded frames within 5e-6 s;
  * the shield arm's configuration pins the file's sha256, and the agent refuses a changed file.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v4.offline import common as C  # noqa: E402
from framelease_v4.offline import export_envelopes as X  # noqa: E402

FILES = {label: X.OUT_DIR / f'{label}.json' for label in X.ORDER}
CONFIGS = {'E5': 'T_x0.60', 'E10': 'T_x0.30', 'B0': 'T_x0.00'}


class ExportedFilesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.man = json.loads((X.OUT_DIR / X.MANIFEST).read_text(encoding='utf-8'))
        cls.train = json.loads(X.TRAIN_ENVELOPES.read_text(encoding='utf-8'))

    def test_manifest_and_offline_configurations(self):
        from framelease_v3.runtime import v3_lease as VL
        self.assertEqual(self.man['kept'], ['E5', 'E10', 'B0'])
        self.assertEqual(self.man['picks'], {'E5': 'T_x0.60', 'E10': 'T_x0.30'})
        for label, path in FILES.items():
            self.assertEqual(self.man['files'][label]['sha256'], C.sha256_file(path), label)
            self.assertEqual(self.man['files'][label]['config'], CONFIGS[label])
            env = VL.load_envelope(path)                                   # the v3 runtime reader
            self.assertEqual(env.kind, 'iso')
            self.assertEqual(env.sha256, self.man['files'][label]['sha256'])
            conf = self.train['configs'][CONFIGS[label]]
            for p, table in (('sigma_m', env.sigma), ('vbar_mps', env.vbar), ('abar_mps2', env.abar)):
                self.assertEqual(table, {g: float(conf[p][g]) for g in C.GROUPS}, (label, p))   # exact
            lenv = VL.build_lease_env(str(X.LEASE_PARAMS), str(path))
            self.assertEqual(lenv.envelope.sha256, self.man['files'][label]['sha256'])
        b0 = VL.load_envelope(FILES['B0'])
        self.assertTrue(all(v == 0.0 for t in (b0.sigma, b0.vbar, b0.abar) for v in t.values()))
        self.assertTrue(self.man['verification']['pass'])
        self.assertGreater(self.man['verification']['comparisons'], 18000)
        self.assertEqual(self.man['inputs'][X.rel(X.TRAIN_ENVELOPES)], C.sha256_file(X.TRAIN_ENVELOPES))
        self.assertEqual(self.man['inputs'][X.rel(X.FRONTIER)], C.sha256_file(X.FRONTIER))

    def test_picks_follow_the_frontier_and_reexport_is_identical(self):
        rows = X.frontier_rows()
        self.assertEqual(X.frontier_pick(rows, 0.05)['candidate'], 'T_x0.60')
        self.assertEqual(X.frontier_pick(rows, 0.10)['candidate'], 'T_x0.30')
        self.assertEqual(X.check(), [])
        b = X.build()
        for label, (_, doc) in b['docs'].items():
            self.assertEqual(X.dumps(doc), FILES[label].read_text(encoding='utf-8'), label)
        with tempfile.TemporaryDirectory() as tmp:
            man = X.export(tmp, do_verify=False)
            for label in X.ORDER:
                self.assertEqual(man['files'][label]['sha256'], self.man['files'][label]['sha256'], label)

    def test_pruning_rules(self):
        self.assertEqual(X.grid({'E5': 'T_x0.60', 'E10': 'T_x0.30'}), (['E5', 'E10', 'B0'], {}))
        kept, dropped = X.grid({'E5': 'T_x0.60', 'E10': 'T_x0.60'})
        self.assertEqual((kept, list(dropped)), (['E5', 'B0'], ['E10']))
        kept, dropped = X.grid({'E5': 'ZERO', 'E10': 'T_x0.30'})
        self.assertEqual((kept, list(dropped)), (['E10', 'B0'], ['E5']))
        kept, dropped = X.grid({'E5': 'T_x0.60', 'E10': 'T_x0.00'})
        self.assertEqual((kept, list(dropped)), (['E5', 'B0'], ['E10']))
        kept, dropped = X.grid({'E5': 'ZERO', 'E10': 'ZERO'})
        self.assertEqual(kept, ['B0'])
        kept, _ = X.grid({'E5': 'ZERO', 'E10': 'T_x0.30'})            # E10 kept when E5 is dropped
        self.assertIn('E10', kept)

    def test_runtime_lease_reproduces_offline_tau_star_and_H(self):
        out = X.verify(FILES, CONFIGS, every=3)
        self.assertTrue(out['pass'], out['violations'][:3])
        self.assertGreater(out['comparisons'], 5000)
        self.assertEqual(out['clips'], 37)
        for label in FILES:
            self.assertLessEqual(out['max_abs_tau_star_s'][label], 5e-6, label)
            self.assertLessEqual(out['max_abs_H_s'][label], 5e-6, label)
        self.assertGreater(out['statuses'].get('first_failure', 0), 100)          # crossings inside the grid
        self.assertGreater(out['statuses'].get('immediate_failure', 0), 100)      # H = 0 cases
        self.assertGreater(out['statuses'].get('horizon_cap', 0), 100)            # H = H_bar cases

    def test_shield_arm_pins_the_exported_file(self):
        from framelease_v4.arms import arms_v4 as AV
        for label, path in FILES.items():
            cfg, _, env_path = AV.build_config('fl_heuristic', envelope=str(path))
            self.assertEqual(Path(env_path), path.resolve())
            self.assertEqual(cfg['v3']['envelope_sha256'], C.sha256_file(path), label)
            self.assertEqual(cfg['v3']['resolved']['envelope']['sigma_m'],
                             json.loads(path.read_text())['sigma_m'], label)
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / 'E5.json'
            shutil.copyfile(FILES['E5'], copy)
            cfg, _, _ = AV.build_config('fl_heuristic', envelope=str(copy))
            doc = json.loads(copy.read_text())
            doc['sigma_m']['vehicle'] += 0.01
            copy.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):
                AV.build_policy(json.loads(json.dumps(cfg)))


if __name__ == '__main__':
    unittest.main()
