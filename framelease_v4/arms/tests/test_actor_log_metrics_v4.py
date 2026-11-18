"""CPU tests of the evaluation-only actor log, realized validity and the metric extraction (fake CARLA world).

What is shown:
  * the log round-trips positions (1 cm), yaw, velocity and box offsets, converts to the right-handed frame of
    framelease_v2.geometry, ignores the hero / sensors / signs, catalogues static props once, keeps the nearest
    max_actors inside radius_m;
  * size: a 4000-tick run (the route tick limit seen in the pilot) with 50 nearby actors stays far below 2 MB, a
    tiny budget triggers the documented decimation, a crash-truncated last gzip member loses only that chunk, an
    erroring world never raises and disables the logger after max_errors;
  * realized validity: a plan driving at a parked car conflicts at the analytic first-contact time, misses / R_cond /
    realized-invalid ticks follow their definitions, the true and estimated capture poses agree in the fake world;
  * metrics: Bench2Drive success follows statistic_route_json.is_success, the per-run row recomputed from the log
    streams equals the runtime summary (GPU usage, deadline misses, P_both), the per-arm summary pools correctly.
"""
from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from helpers_v4 import DT, BBox, FakeBackend, FakeWorld, busy_world, config, lease_env, make_obs, stub_env

from framelease_v2 import latency_agent as la
from framelease_v4.arms import actor_log as AL
from framelease_v4.arms import metrics_v4 as MV
from framelease_v4.arms import policies_v4 as PV
from framelease_v4.arms import realized as RZ
from framelease_v4.arms import runtime_v4 as RV


def run_logger(world, hero, n, tmp, params=None, est_fn=None, dt=DT):
    lg = AL.ActorBoxLogger(tmp, params, world_fn=lambda: world, hero_fn=lambda: hero)
    for k in range(n):
        lg.tick(k, k * dt, est_fn(k) if est_fn else None)
        world.step(dt)
    lg.close()
    return lg


class ActorLogTest(unittest.TestCase):
    def test_params(self):
        self.assertEqual(AL.normalize_params()['budget_bytes'], 2_000_000)
        for bad in ({'radius_m': 0}, {'max_actors': 0}, {'strides': [1, 2]}, {'decimate_fractions': [0.8, 0.5]},
                    {'foo': 1}, {'compresslevel': 12}):
            with self.assertRaises(ValueError):
                AL.normalize_params(bad)
        self.assertEqual(AL.classify('vehicle.bh.crossbike'), 'vehicle')
        self.assertEqual(AL.classify('walker.pedestrian.0012'), 'walker')
        self.assertEqual(AL.classify('static.prop.trafficcone01'), 'static')
        self.assertIsNone(AL.classify('traffic.traffic_light'))
        self.assertIsNone(AL.classify('sensor.camera.rgb'))
        self.assertEqual(AL.classify('vehicle.lincoln.mkz_2020', 'hero'), 'hero')

    def test_round_trip_and_frames(self):
        w = FakeWorld()
        hero = w.add(1, 'vehicle.lincoln.mkz_2020', 100.0, -50.0, 30.0, 4.0, 1.0, BBox(2.45, 1.06, ox=0.2), 'hero')
        w.add(7, 'vehicle.audi.a2', 110.0, -45.0, -60.0, -2.0, 3.0, BBox(1.9, 0.9, ox=0.3, oy=-0.1))
        w.add(8, 'walker.pedestrian.0001', 95.0, -52.0, 170.0, 0.5, -0.4, BBox(0.3, 0.25))
        w.add(9, 'vehicle.tesla.model3', 400.0, 400.0)                       # outside radius
        w.add(10, 'sensor.camera.rgb', 100.0, -50.0)
        w.add(11, 'static.prop.trafficcone01', 105.0, -50.0, 15.0, bbox=BBox(0.2, 0.2))
        with tempfile.TemporaryDirectory() as tmp:
            run_logger(w, hero, 30, tmp)
            log = AL.read_actor_log(tmp)
            self.assertEqual(log.n_ticks, 30)
            self.assertEqual(set(log.catalog), {7, 8, 9, 11})                   # hero / sensor never catalogued
            self.assertEqual(log.catalog[11]['k'], 'static')
            r = log.ticks[10]
            self.assertEqual(sorted(a[0] for a in r['a']), [7, 8])
            t = 10 * DT
            ex, ey = 100.0 + 4.0 * t, -50.0 + 1.0 * t
            self.assertAlmostEqual(r['e'][0] / 100.0, ex, delta=0.006)
            self.assertAlmostEqual(r['e'][1] / 100.0, ey, delta=0.006)
            a7 = [a for a in r['a'] if a[0] == 7][0]
            self.assertAlmostEqual((r['e'][0] + a7[1]) / 100.0, 110.0 - 2.0 * t, delta=0.006)
            self.assertAlmostEqual((r['e'][1] + a7[2]) / 100.0, -45.0 + 3.0 * t, delta=0.006)
            rows_ = log.gt_rows()
            g = [x for x in rows_[10]['actors'] if x['id'] == '7'][0]
            yaw = math.radians(-60.0)
            cx = 110.0 - 2.0 * t + math.cos(yaw) * 0.3 - math.sin(yaw) * (-0.1)
            cy = -45.0 + 3.0 * t + math.sin(yaw) * 0.3 + math.cos(yaw) * (-0.1)
            self.assertAlmostEqual(g['center_xy'][0], cx, delta=0.01)
            self.assertAlmostEqual(g['center_xy'][1], -cy, delta=0.01)          # right-handed: y -> -y
            self.assertAlmostEqual(g['yaw'], math.radians(60.0), delta=1e-3)     # yaw -> -yaw
            self.assertEqual(g['velocity_xy'], [-2.0, -3.0])
            self.assertEqual((g['half_length'], g['half_width']), (1.9, 0.9))
            self.assertEqual(rows_[10]['frame_idx'], 10)
            gt = log.gt_track()
            self.assertEqual(set(gt.ids), {'7', '8'})
            boxes = log.static_boxes()
            self.assertEqual(len(boxes), 1)
            self.assertAlmostEqual(boxes[0][2][1], 50.0, delta=0.01)
            st = json.loads((Path(tmp) / AL.MANIFEST_NAME).read_text())
            self.assertEqual((st['ticks_logged'], st['errors'], st['evaluation_only']), (30, 0, True))

    def test_nearest_cap_and_radius(self):
        w = FakeWorld()
        hero = w.add(1, 'vehicle.lincoln.mkz_2020', 0, 0, role='hero')
        for i in range(30):
            w.add(100 + i, 'vehicle.audi.a2', 2.0 + 2.0 * i, 0.0)              # 2 ... 60 m
        with tempfile.TemporaryDirectory() as tmp:
            run_logger(w, hero, 3, tmp, {'max_actors': 5, 'radius_m': 30.0})
            log = AL.read_actor_log(tmp)
            r = log.ticks[0]
            self.assertEqual(r['n'], 15)                                         # 2 ... 30 m inside the radius
            self.assertEqual([a[0] for a in r['a']], [100, 101, 102, 103, 104])  # the nearest five

    def test_size_budget_and_decimation(self):
        rng = np.random.default_rng(3)
        w, hero = busy_world(rng)
        with tempfile.TemporaryDirectory() as tmp:
            lg = run_logger(w, hero, 4000, tmp)
            st = lg.status()
            self.assertLess(st['bytes'], 2_000_000)
            self.assertEqual((st['ticks_logged'], st['decimation_events'], st['errors']), (4000, [], 0))
            self.assertGreater(st['actor_rows'], 4000)
        w, hero = busy_world(np.random.default_rng(4))
        with tempfile.TemporaryDirectory() as tmp:
            lg = run_logger(w, hero, 4000, tmp, {'budget_bytes': 40_000, 'flush_every': 50})
            st = lg.status()
            levels = [e['level'] for e in st['decimation_events']]
            self.assertEqual(levels, sorted(levels))
            self.assertEqual(levels[-1], 3)                                      # budget reached: ego rows only
            self.assertLess(st['bytes'], 40_000 * 1.6)
            self.assertLess(st['ticks_logged'], 4000)
            log = AL.read_actor_log(tmp)
            self.assertEqual(log.n_ticks, st['ticks_logged'])
            self.assertTrue(any(r['a'] is None for r in log.ticks))
            self.assertGreaterEqual(log.stride_s(), DT)

    def test_truncated_member_and_errors(self):
        w, hero = busy_world(np.random.default_rng(5))
        with tempfile.TemporaryDirectory() as tmp:
            run_logger(w, hero, 250, tmp, {'flush_every': 100})
            p = Path(tmp) / AL.FILE_NAME
            data = p.read_bytes()
            p.write_bytes(data[:-25])                                             # a crash inside the last member
            log = AL.read_actor_log(tmp)
            self.assertTrue(log.truncated)
            self.assertEqual(log.n_ticks, 200)
        calls = []

        def broken():
            calls.append(1)
            raise RuntimeError('simulator gone')
        with tempfile.TemporaryDirectory() as tmp:
            lg = AL.ActorBoxLogger(tmp, {'max_errors': 4}, world_fn=broken, hero_fn=lambda: None)
            for k in range(10):
                lg.tick(k, k * DT)                                                # never raises
            self.assertFalse(lg.enabled)
            self.assertEqual((lg.errors, len(calls)), (4, 4))
            lg.close()
            st = json.loads((Path(tmp) / AL.MANIFEST_NAME).read_text())
            self.assertIn('consecutive errors', st['disabled_reason'])

    def test_disabled_writes_no_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            lg = AL.ActorBoxLogger(tmp, {'enabled': False}, world_fn=lambda: None)
            lg.tick(0, 0.0)
            lg.close()
            self.assertFalse((Path(tmp) / AL.FILE_NAME).exists())
            self.assertEqual(json.loads((Path(tmp) / AL.MANIFEST_NAME).read_text())['ticks_seen'], 0)


def simulated_run(tmp, policy, world, hero, n=120, cfg=None, result=None, obs_fn=make_obs):
    """A run directory with the agent's layout: runtime logs + actor log + summary + metrics/result.json."""
    d = Path(tmp) / 'raw' / 'agent' / 'framelease'
    d.mkdir(parents=True)
    lg = AL.ActorBoxLogger(d, world_fn=lambda: world, hero_fn=lambda: hero)
    logger = la.JsonlLogger(d)
    rt = RV.V4Runtime(FakeBackend(), policy, cfg or config(), logger, timer=lambda: 0.0)
    for k in range(n):
        now = k * DT
        obs = obs_fn(k)
        rt.add_observation(obs)
        rt.advance(now)
        ref = rt.control_reference(now, obs)
        rt.record_tick(now, ref)
        lg.tick(k, now, obs.lidar2global)
        world.step(DT)
    logger.close()
    lg.close()
    s = rt.summary()
    s['actor_log'] = lg.status()
    (d / 'summary.json').write_text(json.dumps(la.jsonable(s)))
    (Path(tmp) / 'metrics').mkdir()
    res = result or {'route_records': 1, 'route_status': 'Completed', 'scores': {'score_composed': 80.0,
                     'score_route': 100.0, 'score_penalty': 0.8}, 'infractions': {'min_speed_infractions': ['x']},
                     'meta': {'route_length': 500.0, 'duration_game': n * DT}}
    res = {**res, 'agent_summary': json.loads((d / 'summary.json').read_text())}
    (Path(tmp) / 'metrics' / 'result.json').write_text(json.dumps(res))
    (Path(tmp) / 'config.json').write_text(json.dumps({'arm': 'x_fp', 'route': {'route_id': '1'}}))
    return rt


def parked_car_world():
    """Hero static at the origin heading +y (right-handed) = CARLA yaw -90 deg; a car parked 12 m ahead."""
    w = FakeWorld()
    hero = w.add(1, 'vehicle.lincoln.mkz_2020', 0.0, 0.0, -90.0, 0, 0, BBox(2.45, 1.06), 'hero')
    w.add(200, 'vehicle.tesla.model3', 0.0, -12.0, -90.0, 0, 0, BBox(2.3, 1.0))
    return w, hero


class RealizedValidityTest(unittest.TestCase):
    def test_conflict_time_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            w, hero = parked_car_world()
            simulated_run(tmp, PV.logged_v2_class('fixed_deep')(env=None), w, hero, n=120)
            r = RZ.realized_validity(tmp, with_candidates=True)
            cands = r.pop('candidates')
            # ego box centre 0.3837 m ahead of the LiDAR origin (B2D ego shape), LiDAR 0.39 m behind the ego origin:
            # front at 2.4462 - 0.0063 m, car rear at 12 - 2.3 = 9.7 m, plan at 5 m/s -> contact (d_safe 0.5) at
            # tau = (9.7 - 0.5 - 2.4462 + 0.0063) / 5
            want = (9.7 - 0.5 - (2.4462 - 0.0063)) / 5.0
            vs = [c['V'] for c in cands.values() if c['status'] == 'ok' and c['conflict']]
            self.assertTrue(vs)
            for v in vs:
                self.assertAlmostEqual(v, want, delta=0.01)
            self.assertEqual(r['conflict_plans'], len(vs))
            self.assertEqual(r['misses'], r['conflict_plans'])                    # fixed deep: H = 3.0 > V_suf
            self.assertEqual(r['r_cond'], 1.0)
            self.assertLess(r['est_vs_true_lidar_offset_m']['max'], 1e-6)
            ticks = rows_from(tmp, 'ticks')
            n_invalid = 0
            for t in ticks:
                if t['mode'] != 'track':
                    continue
                c = cands.get(f'{t["incumbent"]["job_id"]}:{t["incumbent"]["depth"]}')
                if c and c['status'] == 'ok' and c['conflict'] and t['sim_s'] - t['incumbent']['capture_s'] >= \
                        c['V_suf'] - 1e-9:
                    n_invalid += 1
            self.assertEqual(r['realized_invalid_ticks'], n_invalid)
            self.assertGreater(n_invalid, 0)

    def test_no_conflict_without_actor(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = FakeWorld()
            hero = w.add(1, 'vehicle.lincoln.mkz_2020', 0.0, 0.0, -90.0, 0, 0, BBox(2.45, 1.06), 'hero')
            w.add(201, 'vehicle.tesla.model3', 6.0, -12.0, -90.0, 0, 0, BBox(2.3, 1.0))   # next lane
            simulated_run(tmp, PV.logged_v2_class('fast_only')(env=None), w, hero, n=100)
            r = RZ.realized_validity(tmp)
            self.assertEqual((r['conflict_plans'], r['misses'], r['realized_invalid_ticks']), (0, 0, 0))
            self.assertIsNone(r['r_cond'])
            self.assertGreater(r['evaluated_plans'], 3)

    def test_short_age_lease_avoids_misses(self):
        """Age-Only with A = 0.6 s certifies plans for less than V_suf (0.85 s): conflicts without misses."""
        with tempfile.TemporaryDirectory() as tmp:
            w, hero = parked_car_world()
            simulated_run(tmp, PV.AgeLeasePolicy(env=lease_env(), age_lease_s=0.6), w, hero, n=120,
                          cfg=config(max_age_s=2.5))
            r = RZ.realized_validity(tmp)
            self.assertGreater(r['conflict_plans'], 0)
            self.assertEqual((r['misses'], r['realized_invalid_ticks']), (0, 0))
            self.assertEqual(r['r_cond'], 0.0)


def rows_from(tmp, stream):
    p = Path(tmp) / 'raw' / 'agent' / 'framelease' / f'{stream}.jsonl'
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


class MetricsTest(unittest.TestCase):
    def test_b2d_success_definition(self):
        cases = ((('Completed', {'min_speed_infractions': ['a']}), True), (('Perfect', {}), True),
                 (('Completed', {'collisions_vehicle': ['c']}), False),
                 (('Completed', {'red_light': ['r'], 'min_speed_infractions': []}), False),
                 (('Failed - Agent got blocked', {}), False), (('Failed - TickRuntime', {}), False))
        for (status, inf), want in cases:
            self.assertEqual(MV.b2d_success(status, inf), want, (status, inf))
        b = MV.b2d_metrics({'route_records': 1, 'route_status': 'Failed - Agent crashed', 'scores': {}})
        self.assertEqual(b['valid_record'], 0)
        b = MV.b2d_metrics({'route_records': 1, 'route_status': 'Completed',
                            'scores': {'score_composed': 60.0, 'score_route': 50.0, 'score_penalty': 0.6},
                            'infractions': {'collisions_vehicle': ['x', 'y'], 'collisions_layout': ['z']},
                            'meta': {'route_length': 400.0}})
        self.assertEqual((b['success'], b['collisions_total'], b['km_driven']), (0, 3, 0.2))
        self.assertAlmostEqual(b['collisions_per_km'], 15.0)

    def test_run_row_matches_summary_and_arm_pooling(self):
        rows_ = []
        with tempfile.TemporaryDirectory() as tmp:
            for i, pol in enumerate((PV.EventTriggeredV4(env=stub_env()),
                                     PV.AgeLeasePolicy(env=lease_env(), age_lease_s=1.0))):
                d = Path(tmp) / f'r{i}'
                d.mkdir()
                w, hero = parked_car_world()
                rt = simulated_run(d, pol, w, hero, n=140, cfg=config(max_age_s=2.5 if i else 3.0))
                s = rt.summary()
                row = MV.run_metrics(d, realized=True)
                self.assertAlmostEqual(row['gpu_usage'], s['v4']['gpu_usage'], delta=1e-12)
                self.assertAlmostEqual(row['deadline_miss_ratio'], s['v4']['deadline_miss_ratio'], delta=1e-12)
                self.assertEqual(row['fallback_episodes'], s['v4']['fallback_episodes'])
                checks = json.loads(row['checks'])
                self.assertLess(checks['deadline_miss_vs_summary'], 1e-12)
                self.assertGreaterEqual(checks['gpu_usage_summary_minus_recomputed'], -1e-12)
                if i:
                    self.assertAlmostEqual(row['p_both'], s['v4']['p_both'], delta=1e-12)
                    self.assertLess(checks['p_both_vs_summary'], 1e-12)
                else:
                    self.assertIsNone(row['p_both'])
                    self.assertAlmostEqual(row['gpu_usage'], row['gpu_usage_recomputed'], delta=0.03)
                self.assertTrue(row['realized_available'])
                self.assertEqual((row['success'], row['valid_record']), (1, 1))
                rows_.append(row)
            found = MV.find_runs(tmp)
            self.assertEqual(len(found), 2)
        arms = MV.arm_summary(rows_)
        self.assertEqual(len(arms), 1)
        a = arms[0]
        self.assertEqual(a['routes'], 2)
        self.assertAlmostEqual(a['deadline_miss_ratio_pooled'],
                               sum(r['fallback_ticks'] for r in rows_) / sum(r['ticks'] for r in rows_))
        self.assertAlmostEqual(a['p_both_pooled'], rows_[1]['p_both'])          # only the shield run has epochs
        self.assertEqual(a['success_rate'], 1.0)


if __name__ == '__main__':
    unittest.main()
