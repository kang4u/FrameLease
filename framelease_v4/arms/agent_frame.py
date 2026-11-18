"""Frame of the official UniDriveVLA agent's GNSS-derived poses (evaluation only).

The official agent (third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/team_code/
unidrivevla_b2d_agent.py) turns the leaderboard GNSS reading into metres with gps_to_location (lines 451-459). It uses
lat_ref / lon_ref, which init() (lines 354-375) solves with scipy.optimize.fsolve from the first point of the
interpolated global plan (its world coordinates and its GNSS coordinates; initial guess [0, 0]). The leaderboard
computes those GNSS coordinates with route_manipulation._location_to_gps and the map's OpenDRIVE geoReference
(_get_latlon_ref: +lat_0 / +lon_0, default 42.0 / 2.0).

As a result, the agent's metric frame is not the CARLA world frame. On maps whose geoReference is lat_0 = lon_0 = 0
(Town12, Town13), fsolve returns lat_ref = 0, and the longitude equation reduces to lon_ref = longitude of the route's
first point. The agent's x axis therefore starts at the route's first point: x_agent = x_world - x_first. The y axis
is the world's (up to the y sign convention of the right-handed model world). The agent drives on relative transforms
between its own poses, so this translation never affects its control. It matters only when the agent's logged pose
estimate is compared with the true pose (framelease_v4/protocol/check_smoke.py, pose_offset).

This module reproduces that chain with the official equations, copied verbatim, so that a true world position can be
mapped into the agent's frame:
    world (right-handed model world, y = -y_carla)
      -> CARLA world -> leaderboard GNSS (map geoReference)
      -> official gps_to_location (agent lat_ref / lon_ref)
      -> agent frame (right-handed).
Nothing in the agent, launcher, runtime, lease, shield or any policy imports this module.

Approximation, documented: the agent solves its references at the first point of the INTERPOLATED global plan, which
is the lane waypoint at the route's first XML position. This module uses the first XML position itself. The two differ
by centimetres, far below the 0.9-1.9 m pose_offset band.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_AGENT = ROOT / ('third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/team_code/'
                         'unidrivevla_b2d_agent.py')
LEADERBOARD_ROUTE_MANIPULATION = ROOT / ('third_party/UniDriveVLA-linux/Bench2Drive/bench2drive/leaderboard/'
                                         'leaderboard/utils/route_manipulation.py')
EARTH_RADIUS_EQUA = 6378137.0
DEFAULT_GEO_REFERENCE = (42.0, 2.0)          # leaderboard _get_latlon_ref default when the map has no geoReference


# ------------------------------------------------------------------------------------------------ map and route inputs

def xodr_search_dirs(town):
    """Directories searched for <town>.xodr, in order."""
    dirs = []
    for d in (os.environ.get('FRAMELEASE_XODR_DIRS') or '').split(os.pathsep):
        if d:
            dirs.append(Path(d))
    carla = Path(os.environ.get('CARLA_ROOT') or '/home/kang/opt/CARLA_0.9.15')
    dirs += [carla / 'CarlaUE4/Content/Carla/Maps/OpenDrive',
             carla / f'CarlaUE4/Content/Carla/Maps/{town}/OpenDrive',
             Path.home() / f'carlaCache/0.9.15/Carla/Maps/{town}/OpenDrive']
    return dirs


def find_xodr(town):
    """Path of the town's OpenDRIVE file; FileNotFoundError naming every searched directory."""
    dirs = xodr_search_dirs(town)
    for d in dirs:
        p = d / f'{town}.xodr'
        if p.is_file():
            return p
    raise FileNotFoundError(f'{town}.xodr not found in: ' + ', '.join(str(d) for d in dirs))


def geo_reference(xodr_text):
    """(lat_ref, lon_ref) of the map, parsed as the leaderboard's _get_latlon_ref does (default 42.0 / 2.0)."""
    lat_ref, lon_ref = DEFAULT_GEO_REFERENCE
    m = re.search(r'<geoReference>(.*?)</geoReference>', xodr_text, re.S)
    if m:
        text = m.group(1).replace('<![CDATA[', '').replace(']]>', '')
        for item in text.split(' '):
            if '+lat_0' in item:
                lat_ref = float(item.split('=')[1])
            if '+lon_0' in item:
                lon_ref = float(item.split('=')[1])
    return lat_ref, lon_ref


def first_route_waypoint(routes_xml, route_id):
    """(x, y) in the CARLA world of the first <position> of the route in a leaderboard routes XML."""
    text = Path(routes_xml).read_text(encoding='utf-8')
    m = re.search(r'<route id="%s"[^>]*>\s*<waypoints>\s*<position x="([-0-9.eE]+)" y="([-0-9.eE]+)"'
                  % re.escape(str(route_id)), text)
    if not m:
        raise ValueError(f'route {route_id} or its first waypoint not found in {routes_xml}')
    return float(m.group(1)), float(m.group(2))


# ------------------------------------------------------------------------------------- the official equations, verbatim

def location_to_gps(lat_ref, lon_ref, x, y):
    """leaderboard route_manipulation._location_to_gps for a CARLA world location (x, y); returns (lat, lon)."""
    scale = math.cos(lat_ref * math.pi / 180.0)
    mx = scale * lon_ref * math.pi * EARTH_RADIUS_EQUA / 180.0
    my = scale * EARTH_RADIUS_EQUA * math.log(math.tan((90.0 + lat_ref) * math.pi / 360.0))
    mx += x
    my -= y
    lon = mx * 180.0 / (math.pi * EARTH_RADIUS_EQUA * scale)
    lat = 360.0 * math.atan(math.exp(my / (EARTH_RADIUS_EQUA * scale))) / math.pi - 90.0
    return lat, lon


def solve_agent_refs(locx, locy, lat, lon):
    """Official UniDriveVLAB2DAgent.init(): fsolve of the agent's two equations from the route's first point."""
    from scipy.optimize import fsolve

    def equations(vars):
        x, y = vars
        eq1 = ((lon * math.cos(x * math.pi / 180) - (locx * x * 180) / (math.pi * EARTH_RADIUS_EQUA)) -
               math.cos(x * math.pi / 180) * y)
        eq2 = (math.log(math.tan((lat + 90) * math.pi / 360)) * EARTH_RADIUS_EQUA
               * math.cos(x * math.pi / 180) + locy - math.cos(x * math.pi / 180)
               * EARTH_RADIUS_EQUA * math.log(math.tan((90 + x) * math.pi / 360)))
        return [eq1, eq2]

    import warnings
    with warnings.catch_warnings():               # the official solve emits the same RuntimeWarning; it is harmless
        warnings.simplefilter('ignore', RuntimeWarning)
        solution = fsolve(equations, [0, 0])
    return float(solution[0]), float(solution[1])


def gps_to_location(lat_ref, lon_ref, lat, lon):
    """Official UniDriveVLAB2DAgent.gps_to_location; returns the agent's (x, y) (CARLA y sign)."""
    scale = math.cos(lat_ref * math.pi / 180.0)
    my = math.log(math.tan((lat + 90) * math.pi / 360.0)) * (EARTH_RADIUS_EQUA * scale)
    mx = (lon * (math.pi * EARTH_RADIUS_EQUA * scale)) / 180.0
    y = scale * EARTH_RADIUS_EQUA * math.log(math.tan((90.0 + lat_ref) * math.pi / 360.0)) - my
    x = mx - scale * lon_ref * math.pi * EARTH_RADIUS_EQUA / 180.0
    return x, y


# ------------------------------------------------------------------------------------------------------- the frame

def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


class AgentFrame:
    """The official agent's metric frame for one route: map(x_rh, y_rh) -> agent (x, y), both right-handed."""

    def __init__(self, town, routes_xml, route_id, xodr_path=None):
        self.town, self.routes_xml, self.route_id = str(town), str(routes_xml), str(route_id)
        self.xodr_path = Path(xodr_path) if xodr_path else find_xodr(self.town)
        self.map_lat_ref, self.map_lon_ref = geo_reference(self.xodr_path.read_text(encoding='utf-8', errors='replace'))
        self.first_xy = first_route_waypoint(self.routes_xml, self.route_id)
        lat0, lon0 = location_to_gps(self.map_lat_ref, self.map_lon_ref, *self.first_xy)
        self.agent_lat_ref, self.agent_lon_ref = solve_agent_refs(self.first_xy[0], self.first_xy[1], lat0, lon0)

    def map_point(self, x_rh, y_rh):
        """A right-handed model-world point (y = -y_carla) in the agent's right-handed frame."""
        lat, lon = location_to_gps(self.map_lat_ref, self.map_lon_ref, float(x_rh), -float(y_rh))
        xa, ya = gps_to_location(self.agent_lat_ref, self.agent_lon_ref, lat, lon)
        return xa, -ya

    def map_xy(self, xy_rh):
        """Vectorised map_point over an (N, 2) array (NaN rows stay NaN)."""
        import numpy as np
        xy = np.asarray(xy_rh, dtype=float)
        out = np.full_like(xy, np.nan)
        for i, (x, y) in enumerate(xy):
            if math.isfinite(x) and math.isfinite(y):
                out[i] = self.map_point(x, y)
        return out

    def translation_at(self, x_rh, y_rh):
        xa, ya = self.map_point(x_rh, y_rh)
        return xa - float(x_rh), ya - float(y_rh)

    def summary(self):
        fx, fy = self.first_xy
        tx, ty = self.translation_at(fx, -fy)
        return {'town': self.town, 'route_id': self.route_id, 'xodr': str(self.xodr_path),
                'xodr_sha256': _sha256(self.xodr_path), 'map_geo_reference': [self.map_lat_ref, self.map_lon_ref],
                'first_waypoint_carla_xy': [fx, fy], 'agent_refs': [self.agent_lat_ref, self.agent_lon_ref],
                'translation_at_first_waypoint_m': [tx, ty]}


def frame_for_run_config(cfg):
    """AgentFrame of a closed-loop run's config.json (route town / route_id and the routes XML path)."""
    route = cfg.get('route') or {}
    town, rid, xml = route.get('town'), route.get('route_id'), cfg.get('routes')
    if not (town and rid and xml):
        raise ValueError('config.json lacks route.town, route.route_id or routes')
    return AgentFrame(town, xml, rid)
