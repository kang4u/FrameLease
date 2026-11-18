"""Tests of framelease_v4/arms/agent_frame.py (amendment A1): the official agent's route-anchored GNSS frame.

  cd /home/kang/Desktop/DAC && .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/arms/tests/test_agent_frame.py
"""
import glob
import math
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

import numpy as np  # noqa: E402

from framelease_v4.arms import actor_log as AL  # noqa: E402
from framelease_v4.arms import agent_frame as AF  # noqa: E402

ROUTES_XML = ROOT / 'third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/data/bench2drive220.xml'
SMOKE_LOGS = sorted(glob.glob(str(ROOT / 'outputs/framelease_v4/smoke_p1_0/*/runs/*/raw/agent/framelease/actors.jsonl.gz')))


class OfficialSourceFidelity(unittest.TestCase):
    """The copied equations must still be the ones in the official agent and leaderboard sources."""

    def test_official_lines_present(self):
        agent = AF.OFFICIAL_AGENT.read_text(encoding='utf-8')
        for line in ('eq1 = ((lon * math.cos(x * math.pi / 180) - (locx * x * 180) / (math.pi * EARTH_RADIUS_EQUA)) -',
                     'math.cos(x * math.pi / 180) * y)',
                     'initial_guess = [0, 0]',
                     'scale = math.cos(self.lat_ref * math.pi / 180.0)',
                     'my = math.log(math.tan((lat + 90) * math.pi / 360.0)) * (EARTH_RADIUS_EQUA * scale)',
                     'mx = (lon * (math.pi * EARTH_RADIUS_EQUA * scale)) / 180.0',
                     'x = mx - scale * self.lon_ref * math.pi * EARTH_RADIUS_EQUA / 180.0'):
            self.assertIn(line, agent)
        lb = AF.LEADERBOARD_ROUTE_MANIPULATION.read_text(encoding='utf-8')
        for line in ('mx = scale * lon_ref * math.pi * EARTH_RADIUS_EQUA / 180.0', 'mx += location.x',
                     'my -= location.y', "lat_ref = 42.0", "lon_ref = 2.0"):
            self.assertIn(line, lb)


class Town12Route18305(unittest.TestCase):
    def setUp(self):
        self.f = AF.AgentFrame('Town12', ROUTES_XML, 18305)

    def test_references_and_translation(self):
        self.assertEqual((self.f.map_lat_ref, self.f.map_lon_ref), (0.0, 0.0))
        self.assertEqual(self.f.first_xy, (1176.6, 5544.2))
        self.assertAlmostEqual(self.f.agent_lat_ref, 0.0, places=9)
        lat, lon = AF.location_to_gps(0.0, 0.0, 1176.6, 5544.2)
        self.assertAlmostEqual(self.f.agent_lon_ref, lon, places=12)        # lon_ref = longitude of the first point
        for x, y in ((1176.6, -5544.2), (0.0, 0.0), (1500.0, -5000.0), (-300.0, 2000.0)):
            tx, ty = self.f.translation_at(x, y)
            self.assertAlmostEqual(tx, -1176.6, places=6)
            self.assertAlmostEqual(ty, 0.0, places=6)

    def test_map_xy_keeps_nan(self):
        out = self.f.map_xy([[1176.6, -5544.2], [np.nan, 1.0]])
        self.assertTrue(np.isfinite(out[0]).all())
        self.assertTrue(np.isnan(out[1]).all())


class OtherMaps(unittest.TestCase):
    def test_town13_nonzero_georeference_is_smooth(self):
        rid = next(r for r, t in __import__('re').findall(r'<route id="(\d+)"[^>]*town="(Town13)"',
                                                           ROUTES_XML.read_text(encoding='utf-8')))
        f = AF.AgentFrame('Town13', ROUTES_XML, rid)
        self.assertNotEqual((f.map_lat_ref, f.map_lon_ref), (0.0, 0.0))
        x0, y0 = f.first_xy
        t0 = np.array(f.translation_at(x0, -y0))
        t1 = np.array(f.translation_at(x0 + 50.0, -y0 + 50.0))
        self.assertTrue(np.isfinite(t0).all() and np.isfinite(t1).all())
        self.assertLess(float(np.hypot(*(t1 - t0))), 1.0)     # locally a near-translation over 70 m

    def test_missing_town_raises_with_search_dirs(self):
        with self.assertRaises(FileNotFoundError) as cm:
            AF.find_xodr('TownDoesNotExist')
        self.assertIn('TownDoesNotExist.xodr not found in', str(cm.exception))

    def test_geo_reference_default(self):
        self.assertEqual(AF.geo_reference('<OpenDRIVE><header></header></OpenDRIVE>'), AF.DEFAULT_GEO_REFERENCE)


@unittest.skipUnless(SMOKE_LOGS, 'no P1-0 smoke logs on this machine')
class RealSmokeLogs(unittest.TestCase):
    """Regression on the P1-0 smoke logs of 2026-11-10 (Town12, route 18305)."""

    def test_corrected_offset_is_the_gnss_lever_arm(self):
        f = AF.AgentFrame('Town12', ROUTES_XML, 18305)
        for path in SMOKE_LOGS:
            log = AL.read_actor_log(path)
            est, true = log.lidar_pose_estimate(), log.lidar_pose_true()
            ok = np.isfinite(est).all(axis=1) & np.isfinite(true).all(axis=1)
            mapped = f.map_xy(true[ok, :2])
            d = np.hypot(est[ok, 0] - mapped[:, 0], est[ok, 1] - mapped[:, 1])
            raw = np.hypot(est[ok, 0] - true[ok, 0], est[ok, 1] - true[ok, 1])
            self.assertTrue(0.9 <= float(np.median(d)) <= 1.9, (path, float(np.median(d))))
            self.assertLessEqual(float(np.quantile(d, 0.95)), 3.0, path)
            self.assertGreater(float(np.median(raw)), 1000.0, path)


if __name__ == '__main__':
    unittest.main()
