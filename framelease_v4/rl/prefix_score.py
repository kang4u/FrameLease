"""Prefix driving score S(t) = route completion so far x infraction penalty so far, for outline Eq. 7
(r_n = S_{n+1} - S_n), reconstructed offline from a closed-loop run directory of the v2 / v3 / fast-prefix launchers.

Official scorer (Bench2Drive leaderboard used by the evaluator, third_party/bench2drive-linux; identical copy under
third_party/UniDriveVLA-linux/Bench2Drive): DS = score_route x score_penalty with
  * score_route: RouteCompletionTest's percentage of the dense route (GlobalRoutePlanner, 1 m hop) whose waypoint
    the ego has passed (dot product with the waypoint's forward vector, window of WINDOWS_SIZE + 1 = 3 waypoints per
    tick); 100 once > 99% and within 10 m of the last waypoint;
  * score_penalty: product over infraction events of PENALTY_VALUE_DICT factors (pedestrian 0.5, vehicle 0.6,
    layout 0.65, red light 0.7, stop 0.8, scenario timeout 0.7, yield to emergency vehicle 0.7), outside-route-lanes
    (1 - percentage / 100), min-speed 'unused' (factor 1); route deviation / blocked / route timeout end the route
    without a factor.

The run directory keeps only the final record (messages, no timestamps) and the per-tick hero state of
raw/agent/metric_info.json (location, evaluation only), aligned with raw/agent/framelease/ticks.jsonl by tick. So:
  * RC_hat(t): the RouteCompletionTest logic replayed on the logged ego positions against the route's keypoints from
    the routes XML, densified to 1 m (linear for keypoint gaps <= 3 m; cubic Hermite with the neighbouring segment
    directions across junction gaps, standing in for the planner's lane-following path, which needs the CARLA map).
    RC(t) = RC_hat(t) x RC_official / RC_hat(T) (monotone; exact at the end). The unanchored end error is reported.
  * infraction times: penalized events whose message has a location ("... at (x, y, z)": collisions = ego location
    at impact, red light / stop = the light / sign) get the first tick at which the ego is within (closest approach
    + 0.05 m) of that location, in message order per category (messages of a category are chronological). Events
    without a location (outside-route-lanes, scenario timeout, yield to emergency vehicle, min speed) and the
    route-ending events (deviation, blocked, route timeout; no factor) are placed at the end of the episode.
  * P(t) = product of the factors of the located events with time <= t; at the last tick P = score_penalty
    (official). The parsed product is checked against the official penalty (messages round percentages to 0.01).
  * S(t) = RC(t) x P(t) at every tick, and S(T) = score_composed (the official DS) at the last tick, so any reward
    sequence over epochs t_1 < ... < t_N telescopes: S(t_1) + sum_n r_n = DS exactly (up to float summation).
If metric_info or the route is missing, the reward is terminal-only (S = 0 before the last tick, DS at the last),
which the outline allows ("if the score is only valid at the end of the episode, use a terminal-only reward").
"""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from framelease_v4.rl import common as C

PENALTY_VALUE = {'collisions_pedestrian': 0.5, 'collisions_vehicle': 0.6, 'collisions_layout': 0.65,
                 'red_light': 0.7, 'stop_infraction': 0.8, 'scenario_timeouts': 0.7,
                 'yield_emergency_vehicle_infractions': 0.7}
PERCENT_RULE = {'outside_route_lanes': 'increases', 'min_speed_infractions': 'unused'}
FAILURE_ONLY = ('route_dev', 'vehicle_blocked', 'route_timeout')
KNOWN_KEYS = tuple(PENALTY_VALUE) + tuple(PERCENT_RULE) + FAILURE_ONLY
LOC_RE = re.compile(r'at \(x=(?P<x>-?\d+(?:\.\d+)?), y=(?P<y>-?\d+(?:\.\d+)?), z=(?P<z>-?\d+(?:\.\d+)?)\)')
OUTSIDE_RE = re.compile(r'\((?P<p>\d+(?:\.\d+)?)% of the completed route\)')
MINSPEED_RE = re.compile(r'Average speed is (?P<p>\d+(?:\.\d+)?)%')

ROUTE_WINDOW = 2            # RouteCompletionTest.WINDOWS_SIZE
SUCCESS_PERCENT = 99.0      # RouteCompletionTest.PERCENTAGE_THRESHOLD
SUCCESS_DISTANCE_M = 10.0   # RouteCompletionTest.DISTANCE_THRESHOLD
HOP_M = 1.0                 # interpolate_trajectory hop resolution
JUNCTION_GAP_M = 3.0        # keypoint gaps above this are bridged by a Hermite curve
MATCH_TOL_M = 0.05
PENALTY_REL_TOL = 2e-4      # message percentages are rounded to 0.01 (factor error <= 5e-5)


# ============================================================================================ official record

def official_record(run_dir):
    """The single route record of raw/official_results.json (dict)."""
    d = C.read_json(Path(run_dir) / 'raw' / 'official_results.json')
    recs = (d.get('_checkpoint') or {}).get('records') or []
    if len(recs) != 1:
        raise ValueError(f'{run_dir}: expected exactly one route record, found {len(recs)}')
    return recs[0]


@dataclass
class Infraction:
    key: str
    message: str
    factor: float
    location: tuple = None
    percentage: float = None
    timing: str = 'terminal'      # 'located' | 'terminal'
    order: int = 0                # index within its category (chronological)
    tick: int = None
    t_s: float = None
    match_dist_m: float = None

    def as_dict(self):
        return {'key': self.key, 'message': self.message, 'factor': self.factor, 'location': self.location,
                'percentage': self.percentage, 'timing': self.timing, 'order': self.order, 'tick': self.tick,
                't_s': self.t_s, 'match_dist_m': self.match_dist_m}


def parse_infractions(record):
    """Infraction events of a route record with their penalty factors (Bench2Drive scorer rules)."""
    out = []
    infr = record.get('infractions') or {}
    unknown = sorted(k for k, v in infr.items() if v and k not in KNOWN_KEYS)
    if unknown:
        raise ValueError(f'unknown infraction categories {unknown}')
    for key in KNOWN_KEYS:
        for i, msg in enumerate(infr.get(key) or []):
            msg = str(msg)
            loc = None
            m = LOC_RE.search(msg)
            if m:
                loc = (float(m.group('x')), float(m.group('y')), float(m.group('z')))
            pct = None
            if key in PENALTY_VALUE:
                factor = PENALTY_VALUE[key]
            elif key == 'outside_route_lanes':
                m2 = OUTSIDE_RE.search(msg)
                if not m2:
                    raise ValueError(f'cannot parse outside-route-lanes percentage: {msg!r}')
                pct = float(m2.group('p'))
                factor = 1.0 - pct / 100.0
            elif key == 'min_speed_infractions':
                m2 = MINSPEED_RE.search(msg)
                pct = float(m2.group('p')) if m2 else None
                factor = 1.0                                        # 'unused' in Bench2Drive
            else:
                factor = 1.0                                        # failure-only events
            # failure-only events (deviation, blocked, timeout) end the route: they happen at its end
            timing = 'located' if loc is not None and key in PENALTY_VALUE else 'terminal'
            out.append(Infraction(key, msg, float(factor), loc, pct, timing, i))
    return out


# ============================================================================================ route

def load_route_keypoints(route_id, xml_path=None):
    xml_path = Path(xml_path or C.ROUTES_XML)
    for r in ET.parse(xml_path).getroot().iter('route'):
        if r.get('id') == str(route_id):
            pts = [(float(p.get('x')), float(p.get('y'))) for p in r.find('waypoints').iter('position')]
            if len(pts) < 2:
                raise ValueError(f'route {route_id}: fewer than 2 keypoints')
            return np.asarray(pts, dtype=np.float64)
    raise KeyError(f'route {route_id} not in {xml_path}')


def _unit(v):
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-9 else v


def densify_route(kp, gap_m=JUNCTION_GAP_M, hop_m=HOP_M):
    """Dense route (M, 2) at ~hop_m spacing through the keypoints, and its length."""
    kp = np.asarray(kp, dtype=np.float64)
    pts = [kp[0]]
    n = len(kp)
    for i in range(n - 1):
        a, b = kp[i], kp[i + 1]
        c = float(np.linalg.norm(b - a))
        if c < 1e-9:
            continue
        if c <= gap_m:
            m = max(1, int(math.ceil(c / 0.25)))
            for s in np.linspace(0.0, 1.0, m + 1)[1:]:
                pts.append(a + (b - a) * s)
            continue
        d0 = _unit(kp[i] - kp[i - 1]) if i > 0 else _unit(b - a)
        d1 = _unit(kp[i + 2] - kp[i + 1]) if i + 2 < n else _unit(b - a)
        d0, d1 = d0 * c, d1 * c
        for s in np.linspace(0.0, 1.0, max(8, int(math.ceil(4 * c))) + 1)[1:]:
            h00, h10 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s
            h01, h11 = -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
            pts.append(h00 * a + h10 * d0 + h01 * b + h11 * d1)
    P = np.asarray(pts)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    length = float(cum[-1])
    k = max(1, int(round(length / hop_m)))
    s = np.linspace(0.0, length, k + 1)
    R = np.stack([np.interp(s, cum, P[:, 0]), np.interp(s, cum, P[:, 1])], axis=1)
    return R, length


def simulate_route_completion(R, ego_xy):
    """RouteCompletionTest.update() replayed per tick on a dense route R (M, 2). Returns RC_hat per tick (percent)."""
    R = np.asarray(R, dtype=np.float64)
    n = len(R)
    fwd = np.gradient(R, axis=0)
    fwd /= np.maximum(np.linalg.norm(fwd, axis=1, keepdims=True), 1e-9)
    seg = np.linalg.norm(np.diff(R, axis=0), axis=1)
    acc = np.concatenate([[0.0], np.cumsum(seg)])
    acc = acc / acc[-1] * 100.0
    target = R[-1]
    idx, val, success = 0, 0.0, False
    out = np.empty(len(ego_xy), dtype=np.float64)
    for k, e in enumerate(np.asarray(ego_xy, dtype=np.float64)):
        if not success and np.all(np.isfinite(e)):
            for j in range(idx, min(idx + ROUTE_WINDOW + 1, n)):
                if float(np.dot(e - R[j], fwd[j])) > 0.0:
                    idx = j
                    val = float(acc[idx])
            val = round(val, 2)
            if val > SUCCESS_PERCENT and float(np.linalg.norm(e - target)) < SUCCESS_DISTANCE_M:
                success = True
                val = 100.0
        out[k] = val
    return out


# ============================================================================================ ticks

def load_ticks(run_dir):
    """(tick ids, sim_s, ego_xy or None) aligned by tick: ticks.jsonl x metric_info.json[str(tick)]['location']."""
    run_dir = Path(run_dir)
    rows = C.read_jsonl(run_dir / 'raw' / 'agent' / 'framelease' / 'ticks.jsonl')
    if not rows:
        raise ValueError(f'{run_dir}: empty ticks.jsonl')
    ticks = np.asarray([int(r['tick']) for r in rows], dtype=np.int64)
    sim = np.asarray([float(r['sim_s']) for r in rows], dtype=np.float64)
    if np.any(np.diff(sim) <= 0):
        raise ValueError(f'{run_dir}: tick times not strictly increasing')
    mi_path = run_dir / 'raw' / 'agent' / 'metric_info.json'
    ego = None
    if mi_path.is_file():
        mi = C.read_json(mi_path)
        ego = np.full((len(rows), 2), np.nan)
        for k, t in enumerate(ticks):
            e = mi.get(str(int(t)))
            if e and e.get('location') is not None:
                ego[k] = e['location'][:2]
        if np.all(np.isnan(ego[:, 0])):
            ego = None
        else:                                             # forward-fill rare gaps (never at the start: back-fill)
            good = np.where(np.isfinite(ego[:, 0]))[0]
            pos = np.searchsorted(good, np.arange(len(ego)), side='right') - 1
            pos = np.where(pos < 0, 0, pos)
            ego = ego[good[pos]]
    return ticks, sim, ego


# ============================================================================================ prefix score

@dataclass
class PrefixScore:
    run_dir: str
    route_id: str
    sim_s: np.ndarray
    rc: np.ndarray
    penalty: np.ndarray
    S: np.ndarray
    rc_hat: np.ndarray = None
    events: list = field(default_factory=list)
    record: dict = field(default_factory=dict)
    diagnostics: dict = field(default_factory=dict)

    @property
    def ds(self):
        return float(self.record['score_composed'])

    @property
    def t_end(self):
        return float(self.sim_s[-1])

    def at(self, t):
        """S at time t: value after the last tick with sim_s <= t (+1e-9); 0 before the first tick."""
        k = int(np.searchsorted(self.sim_s, float(t) + 1e-9, side='right')) - 1
        return 0.0 if k < 0 else float(self.S[k])

    def at_many(self, times):
        k = np.searchsorted(self.sim_s, np.asarray(times, dtype=np.float64) + 1e-9, side='right') - 1
        out = np.where(k < 0, 0.0, self.S[np.clip(k, 0, len(self.S) - 1)])
        return out.astype(np.float64)

    def rewards(self, times):
        """(pre, r) for epochs at `times` (non-decreasing): pre = S(t_1), r_n = S(t_{n+1}) - S(t_n),
        r_N = DS - S(t_N). pre + fsum(r) = DS."""
        times = np.asarray(times, dtype=np.float64)
        if len(times) == 0:
            return self.ds, np.zeros(0)
        if np.any(np.diff(times) < 0):
            raise ValueError('epoch times must be non-decreasing')
        s = self.at_many(times)
        r = np.empty(len(times), dtype=np.float64)
        r[:-1] = s[1:] - s[:-1]
        r[-1] = self.ds - s[-1]
        return float(s[0]), r

    def progress_at(self, times):
        """(RC, P) at the given times (values after the last tick <= t; (0, 1) before the first tick). Evaluation-only
        covariates (they come from the simulator's hero state): used by OPE, never by a deployed policy."""
        k = np.searchsorted(self.sim_s, np.asarray(times, dtype=np.float64) + 1e-9, side='right') - 1
        kk = np.clip(k, 0, len(self.S) - 1)
        rc = np.where(k < 0, 0.0, self.rc[kk])
        pen = np.where(k < 0, 1.0, self.penalty[kk])
        return rc.astype(np.float64), pen.astype(np.float64)

    def window_gain(self, times, window_s):
        """S(min(t + W, T)) - S(t) per time; the end of the episode counts DS."""
        times = np.asarray(times, dtype=np.float64)
        ends = np.minimum(times + float(window_s), self.t_end)
        return self.at_many(ends) - self.at_many(times)


def reconstruct(run_dir, xml_path=None, mode='prefix'):
    """PrefixScore of a run directory. mode 'prefix' (falls back to 'terminal' if inputs are missing) or 'terminal'."""
    run_dir = Path(run_dir)
    rec = official_record(run_dir)
    scores = rec['scores']
    rc_off, p_off, ds_off = float(scores['score_route']), float(scores['score_penalty']), float(scores['score_composed'])
    route_id = str(rec['route_id']).split('_')[1] if str(rec['route_id']).startswith('RouteScenario_') \
        else str(rec['route_id'])
    ticks, sim, ego = load_ticks(run_dir)
    events = parse_infractions(rec)
    xml_used = Path(xml_path or C.ROUTES_XML)
    cfg_path = run_dir / 'config.json'
    want_sha = C.read_json(cfg_path).get('routes_sha256') if cfg_path.is_file() else None
    diag = {'rc_official': rc_off, 'penalty_official': p_off, 'ds_official': ds_off,
            'routes_xml_sha256_match': (C.sha256_file(xml_used) == want_sha) if want_sha else None,
            'composed_minus_product': ds_off - rc_off * p_off, 'route_length_official_m': (rec.get('meta') or {}).get(
                'route_length'), 'status': rec.get('status'), 'n_ticks': int(len(sim)), 'mode_requested': mode}
    parsed_p = math.prod(e.factor for e in events) if events else 1.0
    diag['penalty_parsed'] = parsed_p
    diag['penalty_rel_err'] = abs(parsed_p - p_off) / max(p_off, 1e-12) if p_off > 0 else abs(parsed_p - p_off)
    diag['penalty_check_ok'] = bool(diag['penalty_rel_err'] <= PENALTY_REL_TOL or abs(parsed_p - p_off) <= 1e-6)
    use_prefix = mode == 'prefix' and ego is not None
    rc_hat = None
    if use_prefix:
        try:
            kp = load_route_keypoints(route_id, xml_path)
        except (KeyError, ValueError) as e:
            use_prefix = False
            diag['prefix_unavailable'] = f'route: {e}'
    elif mode == 'prefix':
        diag['prefix_unavailable'] = 'metric_info.json missing or empty'
    n = len(sim)
    if use_prefix:
        R, length = densify_route(kp)
        rc_hat = simulate_route_completion(R, ego)
        end = float(rc_hat[-1])
        diag.update(route_polyline_m=length, rc_hat_end=end, rc_abs_err_unanchored=abs(end - rc_off))
        if rc_off <= 0.0:
            rc = np.zeros(n)
            diag['rc_mode'] = 'zero'
        elif end > 0.0:
            scale = rc_off / end
            rc = np.minimum(rc_hat * scale, rc_off)
            diag.update(rc_mode='scaled', rc_scale=scale)
        else:
            rc = np.zeros(n)
            rc[-1] = rc_off
            diag['rc_mode'] = 'terminal_rc'
        penalty = np.ones(n)
        last_tick_by_key = {}
        dmax = 0.0
        for e in events:
            if e.timing != 'located':
                continue
            start = last_tick_by_key.get(e.key, 0)
            d = np.linalg.norm(ego[start:] - np.asarray(e.location[:2]), axis=1)
            dmin = float(np.min(d))
            k = start + int(np.argmax(d <= dmin + MATCH_TOL_M))
            e.tick, e.t_s, e.match_dist_m = int(ticks[k]), float(sim[k]), dmin
            last_tick_by_key[e.key] = k
            dmax = max(dmax, dmin)
            if e.factor != 1.0:
                penalty[k:] *= e.factor
        for e in events:
            if e.timing == 'terminal':
                e.tick, e.t_s = int(ticks[-1]), float(sim[-1])
        penalty[-1] = p_off
        S = rc * penalty
        S[-1] = ds_off
        diag.update(mode='prefix', located_events=sum(e.timing == 'located' for e in events),
                    terminal_events=sum(e.timing == 'terminal' for e in events), max_match_dist_m=dmax,
                    S_decreases=int(np.sum(np.diff(S) < -1e-12)))
    else:
        rc = np.zeros(n)
        rc[-1] = rc_off
        penalty = np.ones(n)
        penalty[-1] = p_off
        S = np.zeros(n)
        S[-1] = ds_off
        for e in events:
            e.tick, e.t_s, e.timing = int(ticks[-1]), float(sim[-1]), 'terminal'
        diag.update(mode='terminal', rc_mode='terminal')
    return PrefixScore(str(run_dir), route_id, sim, rc, penalty, S, rc_hat, events,
                       {'route_id': route_id, 'status': rec.get('status'), 'score_route': rc_off,
                        'score_penalty': p_off, 'score_composed': ds_off}, diag)


__all__ = ['PENALTY_VALUE', 'PERCENT_RULE', 'FAILURE_ONLY', 'official_record', 'Infraction', 'parse_infractions',
           'load_route_keypoints', 'densify_route', 'simulate_route_completion', 'load_ticks', 'PrefixScore',
           'reconstruct']
