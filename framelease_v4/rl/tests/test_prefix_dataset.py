"""Prefix driving score (Bench2Drive scorer rules), reward identity and the dataset builder.

    cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
        framelease_v4/rl/tests/test_prefix_dataset.py
"""
from __future__ import annotations

import json
import math
import re
import tempfile
import unittest
from pathlib import Path

import helpers_rl as H

import numpy as np

from framelease_v4.rl import common as C
from framelease_v4.rl import dataset as D
from framelease_v4.rl import features as F
from framelease_v4.rl import prefix_score as PS


class ScorerContractTest(unittest.TestCase):
    """The penalty table and RouteCompletionTest constants are the evaluator's (parsed from its source)."""

    def test_penalty_values_match_the_official_statistics_manager(self):
        src = C.B2D_STATISTICS.read_text()
        names = dict(re.findall(r'TrafficEventType\.(\w+): \'(\w+)\'', src))
        values = dict(re.findall(r'^\s*TrafficEventType\.(\w+): ([0-9.]+),?\s*$', src, flags=re.M))
        for ev, factor in values.items():
            self.assertAlmostEqual(PS.PENALTY_VALUE[names[ev]], float(factor), places=12, msg=ev)
        self.assertEqual(len(values), len(PS.PENALTY_VALUE))
        self.assertIn("TrafficEventType.MIN_SPEED_INFRACTION: [0.7, 'unused']", src)
        self.assertIn("TrafficEventType.OUTSIDE_ROUTE_LANES_INFRACTION: [0, 'increases']", src)
        twin = C.ROOT / 'third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/leaderboard/utils/' \
                        'statistics_manager.py'
        if twin.is_file():
            self.assertEqual(C.sha256_file(twin), C.sha256_file(C.B2D_STATISTICS))

    def test_route_completion_constants_match_the_official_criterion(self):
        src = C.B2D_CRITERIA.read_text()
        block = src[src.index('class RouteCompletionTest'):src.index('class RunningRedLightTest')]
        self.assertIn(f'WINDOWS_SIZE = {PS.ROUTE_WINDOW}', block)
        self.assertIn(f'DISTANCE_THRESHOLD = {PS.SUCCESS_DISTANCE_M}', block)
        self.assertIn(f'PERCENTAGE_THRESHOLD = {int(PS.SUCCESS_PERCENT)}', block)
        self.assertIn('if wp_veh.dot(wp_dir) > 0:', block)


class PrefixScoreTest(unittest.TestCase):
    def test_parse_all_message_kinds(self):
        rec = {'infractions': {
            'collisions_vehicle': ['Agent collided against object with type=vehicle.a and id=1 at (x=1.5, y=-2.0, z=0.1)'],
            'collisions_layout': ['Agent collided against object with type=static.fence and id=0 at (x=3.0, y=4.0, z=0.0)'],
            'collisions_pedestrian': ['Agent collided against object with type=walker.x and id=9 at (x=0.0, y=0.0, z=0.0)'],
            'red_light': ['Agent ran a red light 77 at (x=10.0, y=1.0, z=0.0)'],
            'stop_infraction': ['Agent ran a stop with id=286 at (x=495.437, y=5834.324, z=365.262)'],
            'outside_route_lanes': ['Agent went outside its route lanes for about 12.065 meters (39.54% of the '
                                    'completed route)'],
            'min_speed_infractions': ["Average speed is 46.14% of the surrounding traffic's one"],
            'scenario_timeouts': ['Agent timed out a scenario'],
            'yield_emergency_vehicle_infractions': ['Agent failed to yield to an emergency vehicle'],
            'vehicle_blocked': ['Agent got blocked at (x=499.523, y=5844.188, z=365.315)'],
            'route_dev': [], 'route_timeout': ['Route timeout.']}}
        ev = {e.key: e for e in PS.parse_infractions(rec)}
        self.assertEqual(ev['collisions_vehicle'].factor, 0.6)
        self.assertEqual(ev['collisions_vehicle'].location, (1.5, -2.0, 0.1))
        self.assertEqual(ev['collisions_layout'].factor, 0.65)
        self.assertEqual(ev['collisions_pedestrian'].factor, 0.5)
        self.assertEqual((ev['red_light'].factor, ev['red_light'].timing), (0.7, 'located'))
        self.assertEqual((ev['stop_infraction'].factor, ev['stop_infraction'].location[0]), (0.8, 495.437))
        self.assertAlmostEqual(ev['outside_route_lanes'].factor, 1 - 0.3954, places=12)
        self.assertEqual(ev['outside_route_lanes'].timing, 'terminal')
        self.assertEqual((ev['min_speed_infractions'].factor, ev['min_speed_infractions'].percentage), (1.0, 46.14))
        self.assertEqual(ev['scenario_timeouts'].factor, 0.7)
        self.assertEqual(ev['yield_emergency_vehicle_infractions'].factor, 0.7)
        self.assertEqual((ev['vehicle_blocked'].factor, ev['vehicle_blocked'].timing), (1.0, 'terminal'))
        self.assertEqual(ev['route_timeout'].factor, 1.0)
        with self.assertRaises(ValueError):
            PS.parse_infractions({'infractions': {'new_kind': ['x']}})

    def test_route_completion_replay_on_a_straight_route(self):
        R, length = PS.densify_route(np.array([[0.0, 0.0], [2.0, 0.0], [4.0, 0.0], [100.0, 0.0]]))
        self.assertAlmostEqual(length, 100.0, places=9)
        self.assertLess(np.max(np.abs(np.diff(R[:, 0]) - 1.0)), 1e-9)
        ego = np.stack([np.linspace(0, 95, 400), np.zeros(400)], 1)
        rc = PS.simulate_route_completion(R, ego)
        self.assertTrue(np.all(np.diff(rc) >= 0))
        self.assertLess(abs(rc[-1] - 95.0), 1.01)
        ego2 = np.stack([np.linspace(0, 99.6, 400), np.zeros(400)], 1)
        self.assertEqual(PS.simulate_route_completion(R, ego2)[-1], 99.0)           # 99% is not > 99%
        ego3 = np.stack([np.linspace(0, 100.4, 400), np.zeros(400)], 1)
        self.assertEqual(PS.simulate_route_completion(R, ego3)[-1], 100.0)          # > 99% and within 10 m
        back = np.stack([np.r_[np.linspace(0, 50, 100), np.linspace(50, 10, 100)], np.zeros(200)], 1)
        rcb = PS.simulate_route_completion(R, back)
        self.assertEqual(rcb[-1], rcb[99])                                        # never decreases

    def test_junction_gap_is_bridged_by_a_smooth_curve(self):
        kp = np.array([[0, 0], [2, 0], [4, 0], [14, 10], [14, 12], [14, 14]], dtype=float)  # 90 degree left turn
        R, length = PS.densify_route(kp)
        chord = math.hypot(10, 10)
        self.assertGreater(length, 4 + chord + 4)                                  # longer than the chord
        self.assertLess(length, 4 + math.pi / 2 * 10 * 1.2 + 4)
        seg = np.linalg.norm(np.diff(R, axis=0), axis=1)
        self.assertLess(seg.max(), 1.05)

    def test_reconstruct_identity_and_located_collision_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            msg = 'Agent collided against object with type=vehicle.a and id=1 at (x=25.0, y=0.0, z=0.0)'
            run, xml = H.make_run_dir(tmp, ds=30.0, rc=50.0, penalty=0.6, n_ticks=200, speed=5.0,
                                      infractions={'collisions_vehicle': [msg]})
            ps = PS.reconstruct(run, xml_path=xml)
            ev = [e for e in ps.events if e.key == 'collisions_vehicle'][0]
            self.assertAlmostEqual(ev.t_s, 5.0, places=6)                          # x = 5 m/s * t = 25 m
            self.assertAlmostEqual(ev.match_dist_m, 0.0, places=9)
            self.assertEqual(ps.diagnostics['rc_mode'], 'scaled')
            self.assertTrue(ps.diagnostics['penalty_check_ok'])
            self.assertTrue(ps.diagnostics['routes_xml_sha256_match'])
            self.assertEqual(ps.S[-1], 30.0)
            k = int(np.searchsorted(ps.sim_s, 5.0 - 1e-9))
            self.assertAlmostEqual(ps.penalty[k - 1], 1.0)
            self.assertAlmostEqual(ps.penalty[k], 0.6)
            times = np.sort(np.random.default_rng(0).uniform(0.05, ps.t_end, 57))
            pre, r = ps.rewards(times)
            self.assertLess(abs(pre + math.fsum(r) - 30.0), 1e-9)
            self.assertLess(np.min(r), 0.0)                                         # the collision costs reward

    def test_terminal_only_without_metric_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, xml = H.make_run_dir(tmp, ds=42.0, rc=60.0, penalty=0.7, with_metric_info=False)
            ps = PS.reconstruct(run, xml_path=xml)
            self.assertEqual(ps.diagnostics['mode'], 'terminal')
            self.assertTrue(np.all(ps.S[:-1] == 0.0))
            pre, r = ps.rewards([1.0, 2.0, 3.0])
            self.assertEqual((pre, r.tolist()), (0.0, [0.0, 0.0, 42.0]))


class DatasetTest(unittest.TestCase):
    def _decisions(self):
        rows, t, epoch = [], 0.5, 0
        pattern = [('REFINE', 'REFRESH'), ('REFINE', 'REFRESH'), ('REFRESH',), (), ('REFINE', 'REFRESH'), ('REFINE',),
                   ('REFINE', 'REFRESH')]
        for k in range(28):
            feas = pattern[k % len(pattern)]
            epoch += 1
            if len(feas) == 2:
                a = 'REFRESH' if k % 3 == 0 else 'REFINE'
                mu = 0.15 if a == 'REFRESH' else 0.85
                rows.append(H.decision_row(epoch, t, feas, a, reason='both_feasible:v4_eps0.300_seed1', v4_mu=mu,
                                           v4_base_action='REFINE', v4_explore=int(a == 'REFRESH'), v4_draw=k,
                                           lease_slack_s=0.1 * k))
            else:
                a = feas[0] if feas else 'RECOVERY_REFRESH'
                rows.append(H.decision_row(epoch, t, feas, a))
            t += 0.3
        return rows

    def test_smdp_transitions_rewards_and_propensities(self):
        with tempfile.TemporaryDirectory() as tmp:
            dec = self._decisions()
            run, xml = H.make_run_dir(tmp, route_id='99902', ds=40.0, rc=40.0, decisions=dec)
            ds, eps_ = D.build_dataset([run], xml_path=xml, test_routes=set())
            m = ds.episodes[0]
            self.assertTrue(m['proof']['identity_ok'])
            self.assertEqual(m['proof']['n_epochs'], len(dec))
            choice = [r for r in dec if len(r['feasible']) == 2]
            self.assertEqual(ds.n, len(choice))
            self.assertEqual(int(ds.DONE.sum()), 1)
            self.assertTrue(ds.DONE[-1] and ds.FIRST[0])
            self.assertLess(abs(m['pre_choice_return'] + math.fsum(ds.R.tolist()) - 40.0), 1e-9)
            np.testing.assert_allclose(ds.MU, [r['features']['v4_mu'] for r in choice])
            np.testing.assert_array_equal(ds.A, [0 if r['action'] == 'REFINE' else 1 for r in choice])
            np.testing.assert_array_equal(ds.XN[:-1], ds.X[1:])                       # next choice state
            np.testing.assert_allclose(ds.X[:, F.NAMES.index('lease_slack_s')],
                                       [min(r['features']['lease_slack_s'], 3.0) for r in choice])
            idx = [i for i, r in enumerate(dec) if len(r['feasible']) == 2]
            np.testing.assert_array_equal(ds.NF[:-1], np.diff(idx) - 1)
            self.assertEqual(ds.NF[-1], len(dec) - idx[-1] - 1)
            np.testing.assert_allclose(ds.G, 40.0 - eps_[0].ps.at_many(ds.T))
            self.assertEqual(ds.manifest['identity_all_ok'], True)
            out = Path(tmp) / 'out'
            D.save_dataset(ds, out, eps_)
            ds2 = D.load_dataset(out)
            np.testing.assert_array_equal(ds2.X, ds.X)
            self.assertEqual(ds2.episodes[0]['route_id'], '99902')

    def test_v4_arms_launcher_runs(self):
        """Runs of the v4 arms launcher (arm fl_behaviour) keep the v3 block under config['v4']['v3']."""
        with tempfile.TemporaryDirectory() as tmp:
            name = 'v4_eps0.300_seed77'
            run, xml = H.make_run_dir(tmp, route_id='99904', ds=40.0, rc=40.0, decisions=self._decisions(),
                                      utility=name)
            cfg = json.loads((run / 'config.json').read_text())
            v3 = cfg.pop('v3')
            cfg.update({'arm': 'fl_behaviour_fp', 'v4_arm': 'fl_behaviour', 'v4': {'arm': 'fl_behaviour', 'v3': v3}})
            (run / 'config.json').write_text(json.dumps(cfg))
            self.assertEqual(D.run_meta(run)['utility'], name)
            ds, _ = D.build_dataset([run], xml_path=xml, test_routes=set())
            self.assertTrue(ds.episodes[0]['proof']['identity_ok'])
            self.assertEqual(ds.episodes[0]['utility'], name)

    def test_test_route_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, xml = H.make_run_dir(tmp, route_id='99903', decisions=self._decisions())
            with self.assertRaises(PermissionError):
                D.build_dataset([run], xml_path=xml, test_routes={'99903'})
            ds, _ = D.build_dataset([run], xml_path=xml, test_routes={'99903'}, allow_test=True)
            self.assertEqual(ds.episodes[0]['split'], 'test')
            self.assertEqual(ds.train_episode_ids(), [])
        self.assertEqual(len(C.test_route_ids()), 44)
        self.assertIn('1711', C.test_route_ids())
        self.assertNotIn('2086', C.test_route_ids())

    def test_v2_jobs_epochs_reward_only(self):
        jobs = [{'job_id': j, 'steps': [{'decision': {'boundary_s': 0.5 + 0.6 * j + 0.02 * d, 'continue': d < 2,
                                                      'reason': 'x'}} for d in range(3)]} for j in range(10)]
        with tempfile.TemporaryDirectory() as tmp:
            run, xml = H.make_run_dir(tmp, route_id='99904', ds=12.5, rc=25.0, penalty=0.5, jobs=jobs)
            ds, eps_ = D.build_dataset([run], xml_path=xml, test_routes=set())
            self.assertEqual(eps_[0].kind, 'v2')
            self.assertEqual(ds.n, 0)
            self.assertEqual(ds.episodes[0]['proof']['n_epochs'], 30)
            self.assertTrue(ds.episodes[0]['proof']['identity_ok'])
            self.assertEqual(ds.episodes[0]['pre_choice_return'], 12.5)

    def test_never_writes_into_protected_trees(self):
        for p in (C.ROOT / 'framelease_v3' / 'x.json', C.ROOT / 'outputs' / 'framelease_v2' / 'y' / 'z.json'):
            with self.assertRaises(PermissionError):
                C.atomic_json(p, {})


@unittest.skipUnless(H.PILOT_AVAILABLE, 'fast-prefix pilot runs not present')
class PilotTest(unittest.TestCase):
    def test_identity_on_the_12_pilot_runs(self):
        runs = D.discover_runs([C.PILOT_ROOT])
        self.assertEqual(len(runs), 12)
        ds, eps_ = D.build_dataset(runs)
        self.assertTrue(ds.manifest['identity_all_ok'])
        for m in ds.episodes:
            self.assertTrue(m['proof']['identity_ok'], m['run_dir'])
            self.assertLessEqual(m['proof']['abs_err_epochs'], 1e-9)
            self.assertTrue(m['reconstruction']['penalty_check_ok'], m['run_dir'])
            self.assertEqual(m['split'], 'train')
        self.assertEqual(sum(e.kind == 'v3' for e in eps_), 4)
        self.assertEqual(ds.n, sum(m['n_choice'] for m in ds.episodes))
        self.assertTrue(np.all(ds.MU == 1.0))                                  # deterministic heuristic
        self.assertTrue(np.all(ds.A == 0))                                     # REFINE at every choice state


if __name__ == '__main__':
    unittest.main()
