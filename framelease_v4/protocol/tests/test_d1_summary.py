"""The D1 training-route summary (framelease_v4/protocol/d1_summary.py; PROTOCOL Sec. 4.8). CPU only; job files,
selections and run directories are synthetic, in a temporary directory.

  cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/protocol/tests/test_d1_summary.py

What is shown: the references and every candidate of a stage are tabulated with the selection statistic and DS, RC,
SR, fallback ratio, DMR, realized validity and P_both recomputed from the run logs (metrics_v4), pending and dropped
routes are reported, the stage selection marks survivors, the Markdown table is written, and test routes are refused.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ['CUDA_VISIBLE_DEVICES'] = ''
sys.dont_write_bytecode = True

from framelease_v4.protocol import d1_summary as D1  # noqa: E402
from framelease_v4.protocol import p1_jobs as PJ  # noqa: E402
from framelease_v4.protocol import select_stage as SS  # noqa: E402


class World:
    def __init__(self, tmp):
        self.tmp = Path(tmp)
        self.jobs, self.sel, self.root = self.tmp / 'jobs', self.tmp / 'sel', self.tmp / 'root'
        self.n = 0

    def block(self, variant, name):
        lines, spec = PJ.build_block(variant, name, self.sel, self.jobs)
        # write_block refuses a block whose output directories already hold runs; the synthetic runs live under
        # self.root, so the guard looks there and not in the project's outputs (which hold real P1 runs)
        with mock.patch.object(PJ, 'ROOT', self.root):
            PJ.write_block(PJ.stage_paths(variant, name, self.jobs), lines, spec, [], [])
        return PJ.load_stage_spec(variant, name, self.jobs)[0]

    def run(self, job, c, route, ds, rc=None, status='Completed', shield=False):
        self.n += 1
        d = self.root / job['output_dir'] / 'runs' / f'20261111T{self.n:06d}_x'
        fl = d / 'raw' / 'agent' / 'framelease'
        (d / 'metrics').mkdir(parents=True)
        fl.mkdir(parents=True)
        cfg = {'route': {'route_id': route}, 'v4_arm': c['arm'], 'arm': c['arm'], 'kappa': 1.0, 'seed': 11,
               'v4': {'agent': {'policy_params': c['policy_params']}},
               'envelope_sha256': c['envelope']['sha256'] if c.get('envelope') else None}
        (d / 'config.json').write_text(json.dumps(cfg))
        (d / 'metrics' / 'result.json').write_text(json.dumps(
            {'route_records': 1, 'route_status': status, 'infractions': {}, 'meta': {'route_length': 1000.0},
             'scores': {'score_composed': ds, 'score_route': ds if rc is None else rc, 'score_penalty': 1.0}}))
        with open(fl / 'ticks.jsonl', 'w') as f:      # 10 ticks: 2 in fallback before the first commit at 0.10 s
            for k in range(10):
                t = 0.05 * (k + 1)
                row = {'sim_s': t, 'mode': 'fallback' if k < 2 else 'track',
                       'fallback_reason': 'no_plan' if k < 2 else None,
                       'incumbent': None if k < 2 else {'job_id': 1, 'depth': 1, 'capture_s': 0.0}}
                f.write(json.dumps(row) + '\n')
        (fl / 'events.jsonl').write_text(json.dumps({'kind': 'commit', 'commit_s': 0.10, 'sim_s': 0.10}) + '\n')
        with open(fl / 'decisions.jsonl', 'w') as f:
            for e in range(1, 5):
                f.write(json.dumps({'epoch': e, 'p_both': (e % 2 == 0) if shield else None,
                                    'admitted': True, 'action': 'REFINE'}) + '\n')
        return d


class D1SummaryTest(unittest.TestCase):
    def test_full_stage_one_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            W = World(tmp)
            ref = W.block('FULL', 'ref')
            lease = W.block('FULL', 'lease_s1')
            for c in ref['candidates']:
                for r, job in c['jobs'].items():
                    W.run(job, c, r, 30.0 if c['name'] == 'fixed_deep' else 20.0)
            sim_route = lease['routes'][0]
            pend_route = lease['routes'][1]
            for c in lease['candidates']:
                for r, job in c['jobs'].items():
                    if c['name'] == 'B0' and r == pend_route:
                        continue                                          # not run yet: pending
                    if c['name'] == 'E10' and r == sim_route:
                        W.run(job, c, r, 0.0, status='Failed - Simulation crashed')
                        W.run(job, c, r, 0.0, status='Failed - Simulation crashed')
                        continue
                    W.run(job, c, r, {'E5': 50.0, 'E10': 60.0, 'B0': 70.0}[c['name']], rc=80.0, shield=True)
            doc = D1.summarize('FULL', W.root, W.jobs, W.sel, None, realized=False, freeze_path=None)
            blocks = {b['block']: b for b in doc['blocks']}
            self.assertEqual(list(blocks), ['ref', 'lease_s1'])               # only blocks with a job file
            refs = {c['candidate']: c for c in blocks['ref']['candidates']}
            self.assertEqual((refs['fixed_deep']['ds'], refs['fast_only']['ds']), (30.0, 20.0))
            self.assertEqual(refs['fixed_deep']['valid_runs'], 22)
            self.assertAlmostEqual(refs['fixed_deep']['fallback_ratio'], 0.2)
            self.assertAlmostEqual(refs['fixed_deep']['dmr'], 1 / 9)
            self.assertIsNone(refs['fixed_deep']['p_both'])
            b = blocks['lease_s1']
            self.assertEqual(b['dropped_routes'], {sim_route: ['E10: Failed - Simulation crashed']})
            self.assertEqual(b['pending'], 1)
            rows = {c['candidate']: c for c in b['candidates']}
            self.assertEqual(rows['E5']['outcomes'], {'ok': 11})
            self.assertEqual(rows['B0']['outcomes'], {'ok': 10, 'pending': 1})
            self.assertAlmostEqual(rows['E5']['mean_ds_kept'], 50.0)
            self.assertAlmostEqual(rows['E5']['rc'], 80.0)
            self.assertAlmostEqual(rows['E5']['p_both'], 0.5)
            self.assertEqual(rows['E5']['sr'], 1.0)
            self.assertIsNone(rows['E5']['eir'])                              # realized validity off
            self.assertIsNone(b['selection'])
            md = D1.markdown(doc)
            self.assertIn('## lease_s1', md)
            self.assertIn('| fixed_deep |', md)
            # with every job final the stage is selected, and the summary marks the survivors
            W.run(next(c for c in lease['candidates'] if c['name'] == 'B0')['jobs'][pend_route],
                  next(c for c in lease['candidates'] if c['name'] == 'B0'), pend_route, 70.0, shield=True)
            SS.write_selection(SS.select('FULL', 'lease_s1', W.root, W.jobs, W.sel), W.sel)
            doc = D1.summarize('FULL', W.root, W.jobs, W.sel, None, realized=True, freeze_path=None)
            b = {x['block']: x for x in doc['blocks']}['lease_s1']
            self.assertEqual(b['selection']['survivors'], ['E10', 'B0'])
            self.assertIn('B0 (survivor)', D1.markdown(doc))
            self.assertIsNone(next(c for c in b['candidates'] if c['candidate'] == 'E5')['eir'])  # no actor log

    def test_test_routes_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            W = World(tmp)
            W.block('TRIMMED', 'lease_s1')
            _, spec_path = PJ.load_stage_spec('TRIMMED', 'lease_s1', W.jobs)
            spec = json.loads(spec_path.read_text())
            spec['routes'][0] = PJ.route_split()['test'][0]['route_id']
            spec_path.write_text(json.dumps(spec))
            with self.assertRaises(PermissionError):
                D1.summarize('TRIMMED', W.root, W.jobs, W.sel, None, realized=False, freeze_path=None)


if __name__ == '__main__':
    unittest.main()
