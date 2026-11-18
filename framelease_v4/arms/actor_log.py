"""Compact CARLA ground-truth actor-box log, EVALUATION ONLY (framelease_v4/arms).

Purpose: realized validity violations of committed plans can be computed after a closed-loop run (realized.py),
the closed-loop analogue of the offline V (first time the plan's ego footprint comes within d_safe of a real actor).
Contract: the logger observes the simulator AFTER the agent has computed the control of the tick and writes a file;
no policy, lease, shield, runtime or controller holds a reference to it or reads that file (tested: the simulated
timeline and every control are identical with the logger on or off).

Per logged control tick, one JSON line {"t": agent step, "s": sim time, "e": ego truth, "g": ego estimate,
"n": actors in radius, "a": [[id, dx, dy, yaw, vx, vy], ...]}:
  e  hero CARLA transform and velocity: [x_cm, y_cm, yaw_cdeg, vx_cms, vy_cms]
  g  planar pose of the agent's OWN lidar2global of this tick (GNSS + compass; right-handed model world):
     [x_cm, y_cm, yaw_cdeg] (the frame the plan of this tick's observation is expressed in), or null
  a  vehicles (cars, trucks, bikes, motorbikes) and walkers within radius_m of the hero, nearest max_actors:
     id, location relative to the hero location (world axes, cm), CARLA yaw (centi-degrees), velocity (cm/s)
Once per actor, at first sight, a catalog line {"c": id, "k": class, "ty": type_id, "ext": [hx, hy, hz]_cm,
"off": [ox, oy]_cm (bounding-box centre in the actor frame), "role": role_name, "t": step}; static props
(static.prop.*) are catalogued once with their pose "p": [x_cm, y_cm, yaw_cdeg] and never repeated. A header line
{"h": schema, ...} opens the file. Units are integers: cm, centi-degrees, cm/s. "e", "a", "p" and "ext" are in CARLA's
LEFT-handed world frame; read_actor_log converts to the right-handed frame of framelease_v2.geometry (y -> -y,
yaw -> -yaw).

File: <SAVE_PATH>/framelease/actors.jsonl.gz, one gzip member appended per flush (every flush_every logged ticks and
at destroy), so a crash loses at most one chunk and every complete member stays readable. Manifest: actor_log.json.
Size: byte budget (default 2,000,000) with adaptive decimation: every tick below 50 % of the budget, every 2nd tick
below 75 %, every 4th tick below 100 %, then ego-only rows every 4th tick. Changes are recorded in the manifest.
"""
from __future__ import annotations

import gzip
import json
import math
import os
import time
import traceback
import zlib
from collections import Counter, deque
from pathlib import Path

import numpy as np

SCHEMA = 'framelease_v4.actor_log/1'
FILE_NAME = 'actors.jsonl.gz'
MANIFEST_NAME = 'actor_log.json'
FRAME_DT_S = 0.05
DEFAULT_PARAMS = {'enabled': True, 'radius_m': 50.0, 'max_actors': 64, 'log_static_props': True,
                  'flush_every': 100, 'budget_bytes': 2_000_000, 'decimate_fractions': [0.5, 0.75, 1.0],
                  'strides': [1, 2, 4, 4], 'rescan_every': 20, 'max_errors': 20, 'compresslevel': 6}
DYNAMIC = ('vehicle', 'walker')


def normalize_params(params=None):
    """Validated copy of the logger parameters (raises ValueError)."""
    p = dict(DEFAULT_PARAMS)
    unknown = sorted(set(params or {}) - set(DEFAULT_PARAMS))
    if unknown:
        raise ValueError(f'unknown actor-log parameters {unknown}; allowed {sorted(DEFAULT_PARAMS)}')
    p.update(params or {})
    p['enabled'] = bool(p['enabled'])
    p['log_static_props'] = bool(p['log_static_props'])
    for k in ('radius_m',):
        if not (math.isfinite(float(p[k])) and float(p[k]) > 0):
            raise ValueError(f'{k} must be > 0')
        p[k] = float(p[k])
    for k in ('max_actors', 'flush_every', 'budget_bytes', 'rescan_every', 'max_errors', 'compresslevel'):
        if int(p[k]) != p[k] or int(p[k]) < 1:
            raise ValueError(f'{k} must be a positive integer')
        p[k] = int(p[k])
    if p['compresslevel'] > 9:
        raise ValueError('compresslevel must be 1..9')
    fr = [float(x) for x in p['decimate_fractions']]
    st = [int(x) for x in p['strides']]
    if len(st) != len(fr) + 1 or any(b <= a for a, b in zip(fr, fr[1:])) or not all(x > 0 for x in fr):
        raise ValueError('need increasing decimate_fractions and len(strides) = len(decimate_fractions) + 1')
    if any(s < 1 for s in st) or any(b < a for a, b in zip(st, st[1:])):
        raise ValueError('strides must be non-decreasing positive integers')
    p['decimate_fractions'], p['strides'] = fr, st
    return p


def classify(type_id, role_name=''):
    """'hero' | 'vehicle' | 'walker' | 'static' | None (sensors, traffic lights / signs, spectator, controllers)."""
    if role_name == 'hero':
        return 'hero'
    t = str(type_id or '')
    if t.startswith('vehicle.'):
        return 'vehicle'
    if t.startswith('walker.pedestrian'):
        return 'walker'
    if t.startswith('static.prop'):
        return 'static'
    return None


def _cm(v):
    return int(round(float(v) * 100.0))


def _bbox(actor):
    """(half extents cm [x, y, z], centre offset cm [x, y]) of an actor's bounding box, zeros if unavailable."""
    try:
        bb = actor.bounding_box
        return [_cm(bb.extent.x), _cm(bb.extent.y), _cm(bb.extent.z)], [_cm(bb.location.x), _cm(bb.location.y)]
    except Exception:  # noqa: BLE001  props / unusual actors may lack a usable box
        return [0, 0, 0], [0, 0]


def se2_of(lidar2global):
    """(x, y, yaw) of a 4x4 transform (planar projection), or None."""
    try:
        T = np.asarray(lidar2global, dtype=float)
        if T.shape != (4, 4) or not np.isfinite(T).all():
            return None
        return float(T[0, 3]), float(T[1, 3]), float(math.atan2(T[1, 0], T[0, 0]))
    except Exception:  # noqa: BLE001
        return None


class ActorBoxLogger:
    """Per-tick ground-truth actor boxes near the hero (evaluation only; see the module docstring)."""

    def __init__(self, out_dir, params=None, world_fn=None, hero_fn=None, clock=time.perf_counter):
        self.p = normalize_params(params)
        self.dir = Path(out_dir)
        self.path = self.dir / FILE_NAME
        self.manifest_path = self.dir / MANIFEST_NAME
        self._world_fn = world_fn or _carla_world
        self._hero_fn = hero_fn
        self._clock = clock
        self.enabled = self.p['enabled']
        self.disabled_reason = None if self.enabled else 'disabled by configuration'
        self._lines = []
        self._known = {}                      # actor id -> class (None = ignored)
        self._dynamic = []                    # ids of vehicles / walkers (catalogued)
        self._last_len = None
        self._last_scan = -10 ** 9
        self._hero_id = None
        self._hero_actor = None
        self._header_written = False
        self.stride = self.p['strides'][0]
        self.level = 0
        self.ticks_seen = 0
        self.ticks_logged = 0
        self.actor_rows = 0
        self.ego_only_rows = 0
        self.max_in_radius = 0
        self.catalog = Counter()
        self.bytes = 0
        self.flushes = 0
        self.decimation_events = []
        self.errors = 0
        self.consecutive_errors = 0
        self.error_samples = []
        self.wall_s = deque(maxlen=100000)
        if self.enabled:
            self.dir.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                raise FileExistsError(f'{self.path} exists; the actor log is written once per run')

    # ------------------------------------------------------------------ helpers
    def _hero(self):
        return self._hero_fn() if self._hero_fn is not None else None

    def _header(self, hero):
        ext, off = _bbox(hero) if hero is not None else ([0, 0, 0], [0, 0])
        self._lines.append(json.dumps({
            'h': SCHEMA, 'frame': 'carla_world_left_handed', 'est_frame': 'right_handed_model_world_lidar2global',
            'units': {'xy': 'cm', 'yaw': 'centi-degrees', 'v': 'cm/s', 's': 'simulation seconds'},
            'params': self.p, 'evaluation_only': True,
            'hero': {'id': getattr(hero, 'id', None), 'ty': getattr(hero, 'type_id', None), 'ext': ext, 'off': off}},
            separators=(',', ':'), sort_keys=True))
        self._header_written = True

    def _register(self, world, ids, step):
        try:
            actors = list(world.get_actors(list(ids)))
        except Exception:  # noqa: BLE001  fall back to one lookup per id
            actors = []
            for i in ids:
                try:
                    a = world.get_actor(i)
                except Exception:  # noqa: BLE001
                    a = None
                if a is not None:
                    actors.append(a)
        found = set()
        for a in actors:
            aid = int(a.id)
            found.add(aid)
            role = ''
            try:
                role = str((a.attributes or {}).get('role_name', ''))
            except Exception:  # noqa: BLE001
                pass
            cls = 'hero' if aid == self._hero_id else classify(getattr(a, 'type_id', ''), role)
            self._known[aid] = cls
            if cls == 'hero' and self._hero_id is None:
                self._hero_id, self._hero_actor = aid, a
            if cls in DYNAMIC or (cls == 'static' and self.p['log_static_props']):
                ext, off = _bbox(a)
                row = {'c': aid, 'k': cls, 'ty': str(getattr(a, 'type_id', '')), 'ext': ext, 'off': off,
                       'role': role, 't': int(step)}
                if cls == 'static':
                    try:
                        tr = a.get_transform()
                        row['p'] = [_cm(tr.location.x), _cm(tr.location.y), _cm(tr.rotation.yaw)]
                    except Exception:  # noqa: BLE001
                        row['p'] = None
                self._lines.append(json.dumps(row, separators=(',', ':'), sort_keys=True))
                self.catalog[cls] += 1
                if cls in DYNAMIC:
                    self._dynamic.append(aid)
        for i in ids:
            if int(i) not in found:
                self._known[int(i)] = None       # vanished before it could be looked up

    def _scan(self, world, snap, step):
        try:
            n = len(snap)
        except Exception:  # noqa: BLE001
            n = None
        if n is not None and n == self._last_len and self.ticks_seen - self._last_scan < self.p['rescan_every']:
            return
        ids = [int(a.id) for a in snap]
        new = [i for i in ids if i not in self._known]
        if new:
            self._register(world, new, step)
        self._last_len = n
        self._last_scan = self.ticks_seen

    # ------------------------------------------------------------------ per tick
    def tick(self, step, sim_s, est_lidar2global=None):
        """Log the simulator state of this control tick (call after the control was computed)."""
        if not self.enabled:
            return
        self.ticks_seen += 1
        if (self.ticks_seen - 1) % self.stride != 0:
            return
        t0 = self._clock()
        try:
            self._tick(int(step), float(sim_s), est_lidar2global)
            self.consecutive_errors = 0
        except Exception as e:  # noqa: BLE001  logging must never break or change the run
            self.errors += 1
            self.consecutive_errors += 1
            if len(self.error_samples) < 5:
                self.error_samples.append({'step': int(step), 'error': f'{type(e).__name__}: {str(e)[:300]}',
                                           'traceback': traceback.format_exc()[-1500:]})
            if self.consecutive_errors >= self.p['max_errors']:
                self.enabled = False
                self.disabled_reason = f'{self.consecutive_errors} consecutive errors'
                self.flush()
        finally:
            self.wall_s.append(self._clock() - t0)

    def _tick(self, step, sim_s, est):
        world = self._world_fn()
        hero = self._hero() or self._hero_actor
        if self._hero_id is None and hero is not None:
            self._hero_id = int(hero.id)
            self._hero_actor = hero
            self._known[self._hero_id] = 'hero'
        snap = world.get_snapshot()
        if self._hero_id is None:                        # no hero handle: find it by role_name among the actors
            self._scan(world, snap, step)
            hero = self._hero_actor
        if not self._header_written:
            self._header(hero)
        hs = snap.find(self._hero_id) if self._hero_id is not None else None
        src = hs if hs is not None else hero
        if src is None:
            raise RuntimeError('hero actor unavailable')
        tr, vel = src.get_transform(), src.get_velocity()
        ex, ey = _cm(tr.location.x), _cm(tr.location.y)
        row = {'t': step, 's': round(sim_s, 4), 'e': [ex, ey, _cm(tr.rotation.yaw), _cm(vel.x), _cm(vel.y)]}
        pose = se2_of(est) if est is not None else None
        row['g'] = None if pose is None else [_cm(pose[0]), _cm(pose[1]), _cm(math.degrees(pose[2]))]
        if self.level < len(self.p['decimate_fractions']):
            self._scan(world, snap, step)
            r2 = self.p['radius_m'] ** 2
            hx, hy = tr.location.x, tr.location.y
            near = []
            keep = []
            for aid in self._dynamic:
                a = snap.find(aid)
                if a is None:
                    continue
                keep.append(aid)
                atr = a.get_transform()
                dx, dy = atr.location.x - hx, atr.location.y - hy
                d2 = dx * dx + dy * dy
                if d2 <= r2:
                    near.append((d2, aid, atr, a))
            self._dynamic = keep
            near.sort(key=lambda x: x[0])
            self.max_in_radius = max(self.max_in_radius, len(near))
            out = []
            for _, aid, atr, a in near[:self.p['max_actors']]:
                v = a.get_velocity()
                out.append([aid, _cm(atr.location.x) - ex, _cm(atr.location.y) - ey, _cm(atr.rotation.yaw),
                            _cm(v.x), _cm(v.y)])
            row['n'] = len(near)
            row['a'] = out
            self.actor_rows += len(out)
        else:
            row['n'] = None
            row['a'] = None
            self.ego_only_rows += 1
        self._lines.append(json.dumps(row, separators=(',', ':')))
        self.ticks_logged += 1
        if self.ticks_logged % self.p['flush_every'] == 0:
            self.flush()

    # ------------------------------------------------------------------ output
    def flush(self):
        if not self._lines:
            return
        data = ('\n'.join(self._lines) + '\n').encode('utf-8')
        self._lines = []
        with open(self.path, 'ab') as f:
            f.write(gzip.compress(data, compresslevel=self.p['compresslevel']))
        self.flushes += 1
        self.bytes = os.path.getsize(self.path)
        fr = self.bytes / float(self.p['budget_bytes'])
        level = sum(1 for x in self.p['decimate_fractions'] if fr >= x)
        if level > self.level:
            self.level = level
            self.stride = self.p['strides'][level]
            self.decimation_events.append({'ticks_seen': self.ticks_seen, 'bytes': self.bytes, 'level': level,
                                           'stride': self.stride,
                                           'actors': 'off (ego only)' if level >= len(self.p['decimate_fractions'])
                                           else 'on'})

    def status(self):
        w = sorted(self.wall_s)

        def q(p):
            return float(w[min(len(w) - 1, int(p * (len(w) - 1) + 0.5))]) if w else None
        return {'schema': SCHEMA, 'file': FILE_NAME, 'manifest': MANIFEST_NAME, 'evaluation_only': True,
                'enabled': self.enabled, 'disabled_reason': self.disabled_reason, 'params': self.p,
                'ticks_seen': self.ticks_seen, 'ticks_logged': self.ticks_logged, 'actor_rows': self.actor_rows,
                'ego_only_rows': self.ego_only_rows, 'max_actors_in_radius': self.max_in_radius,
                'catalog': dict(self.catalog), 'bytes': self.bytes, 'budget_bytes': self.p['budget_bytes'],
                'stride': self.stride, 'decimation_events': list(self.decimation_events), 'flushes': self.flushes,
                'errors': self.errors, 'error_samples': list(self.error_samples),
                'wall_s': {'p50': q(0.5), 'p99': q(0.99), 'max': w[-1] if w else None, 'n': len(w)}}

    def close(self):
        """Flush the last chunk and write the manifest (idempotent)."""
        try:
            self.flush()
        finally:
            if self.p['enabled'] or self.manifest_path.parent.is_dir():
                self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.manifest_path.with_name(MANIFEST_NAME + '.tmp')
                tmp.write_text(json.dumps(self.status(), indent=1, sort_keys=True), encoding='utf-8')
                os.replace(tmp, self.manifest_path)


def _carla_world():
    from srunner.scenariomanager.carla_data_provider import CarlaDataProvider
    return CarlaDataProvider.get_world()


# ============================================================================================ decoder

def _read_lines(path):
    """JSON rows of every complete gzip member (a member truncated by a crash ends the read)."""
    raw = Path(path).read_bytes()
    rows, truncated = [], False
    pos = 0
    while pos < len(raw):
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        try:
            text = d.decompress(raw[pos:])
        except zlib.error:
            truncated = True
            break
        if not d.eof:
            truncated = True
            break
        pos = len(raw) - len(d.unused_data)
        for line in text.decode('utf-8').splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows, truncated


class ActorLog:
    """Decoded actor log. Arrays are SI (m, rad, m/s); right-handed unless the name says carla."""

    def __init__(self, header, catalog, ticks, truncated=False, path=None):
        self.header = header or {}
        self.catalog = catalog
        self.ticks = ticks
        self.truncated = truncated
        self.path = path
        hero = (self.header.get('hero') or {})
        self.hero_ext = np.asarray(hero.get('ext') or [0, 0, 0], dtype=float) / 100.0
        self.hero_off = np.asarray(hero.get('off') or [0, 0], dtype=float) / 100.0
        e = np.asarray([r['e'] for r in ticks], dtype=float).reshape(-1, 5)
        self.step = np.asarray([int(r['t']) for r in ticks], dtype=int)
        self.sim_s = np.asarray([float(r['s']) for r in ticks], dtype=float)
        self.ego_carla = e / 100.0                                   # x, y (m), yaw (deg), vx, vy (m/s)
        g = [r.get('g') for r in ticks]
        self.est = np.asarray([x if x is not None else [np.nan] * 3 for x in g], dtype=float).reshape(-1, 3)
        self.est[:, :2] /= 100.0
        self.est[:, 2] = np.radians(self.est[:, 2] / 100.0)
        self.index_of_step = {int(s): i for i, s in enumerate(self.step)}

    @property
    def n_ticks(self):
        return len(self.ticks)

    def stride_s(self):
        return float(np.median(np.diff(self.sim_s))) if len(self.sim_s) > 1 else FRAME_DT_S

    def ego_right_handed(self):
        """(T, 3) hero transform pose (x, y, yaw) in the right-handed frame."""
        c = self.ego_carla
        return np.stack([c[:, 0], -c[:, 1], -np.radians(c[:, 2])], -1)

    def lidar_pose_true(self):
        """(T, 3) planar pose of the TRUE lidar2global: hero transform + official lidar2ego (B2D convention: the ego
        frame origin is the vehicle transform; the model's plan / detections live in this LiDAR frame)."""
        from framelease_v2.latency_agent import planar_lidar2global
        out = np.full((self.n_ticks, 3), np.nan)
        for i, (x, y, yaw) in enumerate(self.ego_right_handed()):
            out[i] = se2_of(planar_lidar2global(float(x), float(y), float(yaw)))
        return out

    def lidar_pose_estimate(self):
        """(T, 3) planar pose of the agent's own lidar2global (GNSS + compass), NaN where not logged."""
        return self.est.copy()

    def _centre(self, x, y, yaw_deg, off):
        c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
        return x + c * off[0] - s * off[1], y + s * off[0] + c * off[1]

    def gt_rows(self, classes=DYNAMIC):
        """Rows for framelease_v2.geometry.GTTrack (right-handed; frame_idx = round(sim_s / 0.05))."""
        rows = {}
        hl, hw = float(self.hero_ext[0]), float(self.hero_ext[1])
        for i, r in enumerate(self.ticks):
            ex, ey, eyaw = self.ego_carla[i, 0], self.ego_carla[i, 1], self.ego_carla[i, 2]
            cx, cy = self._centre(ex, ey, eyaw, self.hero_off)
            actors = []
            for a in r.get('a') or []:
                aid, dx, dy, yaw_c, vx, vy = a
                meta = self.catalog.get(int(aid))
                if meta is None or meta['k'] not in classes:
                    continue
                x = (r['e'][0] + dx) / 100.0
                y = (r['e'][1] + dy) / 100.0
                yaw = yaw_c / 100.0
                off = np.asarray(meta.get('off') or [0, 0], dtype=float) / 100.0
                ax, ay = self._centre(x, y, yaw, off)
                vxm, vym = vx / 100.0, vy / 100.0
                ext = np.asarray(meta.get('ext') or [0, 0, 0], dtype=float) / 100.0
                actors.append({'id': str(int(aid)), 'class': meta['k'], 'center_xy': [ax, -ay],
                               'yaw': -math.radians(yaw), 'half_length': float(ext[0]),
                               'half_width': float(ext[1]), 'speed': math.hypot(vxm, vym),
                               'velocity_xy': [vxm, -vym]})
            frame = int(round(float(r['s']) / FRAME_DT_S))
            rows[frame] = {'frame_idx': frame, 'ego': {'center_xy': [cx, -cy], 'yaw': -math.radians(eyaw),
                                                       'half_length': hl, 'half_width': hw},
                           'actors': actors}
        return [rows[k] for k in sorted(rows)]

    def gt_track(self, max_gap_s=None, classes=DYNAMIC):
        from framelease_v2.geometry import GTTrack
        gap = max_gap_s if max_gap_s is not None else max(0.25, 1.5 * self.stride_s())
        rows = self.gt_rows(classes)
        rows = [r for r in rows if r['frame_idx'] >= 0]
        return GTTrack(rows, max_gap_s=gap, frame_dt_s=FRAME_DT_S)

    def static_boxes(self):
        """Right-handed boxes of the catalogued static props: list of (id, type_id, center_xy, yaw, hl, hw)."""
        out = []
        for aid, m in sorted(self.catalog.items()):
            if m['k'] != 'static' or not m.get('p'):
                continue
            x, y, yaw = m['p'][0] / 100.0, m['p'][1] / 100.0, m['p'][2] / 100.0
            off = np.asarray(m.get('off') or [0, 0], dtype=float) / 100.0
            cx, cy = self._centre(x, y, yaw, off)
            ext = np.asarray(m.get('ext') or [0, 0, 0], dtype=float) / 100.0
            out.append((aid, m.get('ty'), (cx, -cy), -math.radians(yaw), float(ext[0]), float(ext[1])))
        return out


def read_actor_log(path):
    """ActorLog of a run's actors.jsonl.gz (accepts the file or the directory that holds it)."""
    path = Path(path)
    if path.is_dir():
        path = path / FILE_NAME
    rows, truncated = _read_lines(path)
    header, catalog, ticks = None, {}, []
    for r in rows:
        if 'h' in r:
            header = r
        elif 'c' in r:
            catalog[int(r['c'])] = r
        elif 't' in r:
            ticks.append(r)
    return ActorLog(header, catalog, ticks, truncated, path)


__all__ = ['SCHEMA', 'FILE_NAME', 'MANIFEST_NAME', 'DEFAULT_PARAMS', 'normalize_params', 'classify', 'se2_of',
           'ActorBoxLogger', 'ActorLog', 'read_actor_log']
