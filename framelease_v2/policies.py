"""Scheduling policies for the FrameLease latency-aware closed-loop runtime.

The eight methods of the blueprint's baseline table (FrameLease.docx Sec. 6.3), each with an explicit
algorithm and explicit tuning parameters (all logged in the run configuration):

  fast_only      Fast Only        minimal depth (1 flow step) per observation; refresh whenever the GPU is free
  fixed_deep     Fixed Deep       all 10 flow steps; only the final plan is exposed; refresh whenever free
  fixed_refresh  Fixed Refresh    new observation every period_s on a fixed grid; anytime refinement in between
  risk_adaptive  Risk-Adaptive    flow depth chosen from a scene-risk score of the job's own detections
  aoi            AoI-Based        refresh priority from observation age only (constant age budget)
  ttc            TTC-Based        refresh when the TTC from the model's own detections drops below a threshold
  event          Event-Triggered  inference only when ego state / detections change beyond thresholds
  framelease     FrameLease       action-validity lease + refresh-time reservation (docx Sec. 4-5)

Decision points (simulation seconds; cooperative; information available at that simulated time only):

  on_job_start(job, ctx)                 a job was started on the newest observation (sets job.target_depth)
  after_prefix(job, ctx)                 the non-preemptible prefix finished; job.dets exist from now on
  validity(cand, ctx) -> dict            deadline of a released candidate: used at commit (versioned commit)
                                         and at every control tick (strict expiry -> safety fallback)
  offers(job, depth) -> bool             is the candidate of this depth exposed to the committer?
  continue_refinement(job, ctx)          at a step boundary with depth >= 1: one more flow step? (bool, reason)
  idle_start_time(ctx) -> float | None   GPU idle: absolute start time of the next job (None = re-check at the
                                         next tick). The runtime clamps it to the time the GPU became free.

The runtime (latency_agent.LatencyRuntime) enforces the minimum depth (1: a job must produce a plan), the
maximum depth (10), the latest-frame rule (a job takes the newest observation captured by its start time and an
observation is never processed twice), versioned commit, strict expiry and the logged safety fallback.

Validity (expiry) used by the baselines is the common global cap H_max = config.max_age_s (blueprint Sec. 4.3:
"global maximum allowed observation age"); only FrameLease shortens it with its action-conditioned lease.
Refresh-time reservation, where a policy uses it, is the blueprint's slack rule

    S(t) = D - t - L_refresh_bound - G,   continue one more step only while S(t) >= next step cost,

with L_refresh_bound and the next step cost taken from the measured latency profile (kappa-scaled).

Duck-typed inputs (defined in latency_agent.py):
  ctx:  now_s, newest_obs, incumbent, job, last_job, idle_since_s, profile, config, latest_dets, prev_dets,
        episode_start_s
  obs:  obs_id, capture_s, lidar2global (4x4, agent GNSS/IMU estimate), speed_mps, yaw_rad, command
  job:  job_id, obs, start_s, depth, dets, target_depth, last_deadline_s, policy_state (dict)
  cand: obs, obs_id, capture_s, depth, plan_xy (6,2), dets
  dets: boxes [N,7] (decode_boxes), scores [N], labels [N], valid, obs_id, capture_s, lidar2global
No policy reads simulator ground truth: only the model's detections, the committed plan and the agent's own
speedometer / GNSS / IMU / route-command signals.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np

MAX_DEPTH = 10
EPS_S = 1e-6

POLICY_NAMES = ('fast_only', 'fixed_deep', 'fixed_refresh', 'risk_adaptive', 'aoi', 'ttc', 'event', 'framelease')
RUNTIME_MODES = POLICY_NAMES + ('oracle_sync',)
POLICY_TITLES = {'fast_only': 'Fast Only', 'fixed_deep': 'Fixed Deep', 'fixed_refresh': 'Fixed Refresh',
                 'risk_adaptive': 'Risk-Adaptive', 'aoi': 'AoI-Based', 'ttc': 'TTC-Based',
                 'event': 'Event-Triggered', 'framelease': 'FrameLease', 'oracle_sync': 'Oracle (zero latency)'}


def wrap_angle(a):
    return (float(a) + math.pi) % (2.0 * math.pi) - math.pi


# ----------------------------------------------------------------------------------------------- environment

@dataclass
class PolicyEnv:
    """Static knowledge shared by the policies (never simulator state).

    ego           lease.EgoShape of the hero vehicle (vehicle constants)
    lease_params  lease.LeaseParams (calibrated bounds, or the documented placeholders)
    lease_fn      compute_lease(plan_xy, dets, scores, labels, ego, params) -> dict (Interface 2)
    ttc_fn        ttc_seconds(speed_mps, dets, scores, labels, ego, params) -> float (constant-velocity footprint
                  TTC against d_safe; the same definition the offline C2 evaluation uses)
    group_fn      labels -> array of 'vehicle' | 'pedestrian' | 'other'
    """
    ego: Any
    lease_params: Any
    lease_fn: Callable
    ttc_fn: Callable
    group_fn: Callable
    lease_params_source: str = 'unspecified'

    def describe(self):
        def as_dict(x):
            if hasattr(x, 'to_dict'):
                return x.to_dict()
            if hasattr(x, '__dict__'):
                return {k: v for k, v in vars(x).items() if not k.startswith('_')}
            return repr(x)
        return {'ego': as_dict(self.ego), 'lease_params': as_dict(self.lease_params),
                'lease_params_source': self.lease_params_source,
                'lease_fn': getattr(self.lease_fn, '__module__', '?') + '.' + getattr(self.lease_fn, '__name__', '?'),
                'ttc_fn': getattr(self.ttc_fn, '__module__', '?') + '.' + getattr(self.ttc_fn, '__name__', '?')}


def default_policy_env(lease_params_path=None):
    """PolicyEnv from framelease_v2.lease (Worker C) and the calibrated parameter file, if given."""
    from framelease_v2 import lease as L
    if lease_params_path:
        params = L.load_lease_params(lease_params_path)
        ego = L.load_ego_shape(lease_params_path, default=L.B2D_EGO)
        source = str(lease_params_path)
    else:
        params = L.LeaseParams().validate()
        ego = L.B2D_EGO
        source = 'UNCALIBRATED_DEFAULTS(framelease_v2.lease.LeaseParams())'
    return PolicyEnv(ego=ego, lease_params=params, lease_fn=L.compute_lease, ttc_fn=L.ttc_seconds,
                     group_fn=L.resolve_groups, lease_params_source=source)


# ----------------------------------------------------------------------------------------------- helpers

def max_age_validity(cand, ctx):
    """Common validity of every non-lease policy: the global maximum observation age H_max."""
    h = float(ctx.config.max_age_s)
    return {'deadline_s': float(cand.capture_s) + h, 'lease_s': h, 'source': 'max_age'}


def reservation_slack(deadline_s, ctx, depth, reserve=True):
    """Blueprint Sec. 5.1: S = D - now - L_refresh_bound - G minus the cost of the next step (depth+1).

    Continue one more refinement step only while the returned value is >= 0.
    """
    reserve_s = (ctx.profile.refresh_bound_s + ctx.config.guard_s) if reserve else 0.0
    return float(deadline_s) - float(ctx.now_s) - reserve_s - ctx.profile.next_step_bound_s(depth + 1)


def _relevant(dets, group_fn, score_threshold, groups):
    if dets is None or not getattr(dets, 'valid', True) or len(dets.scores) == 0:
        return np.zeros(0, dtype=bool)
    g = np.asarray(group_fn(dets.labels), dtype=object).reshape(-1)
    return (np.asarray(dets.scores, dtype=float) >= score_threshold) & np.isin(g, list(groups))


def ego_center_lidar(env):
    off = getattr(env.ego, 'center_offset_xy', (0.0, 0.0))
    return np.asarray(off, dtype=float).reshape(2)


def detection_ttc(env, dets, speed_mps, score_threshold, groups):
    """TTC (s) of the ego at constant speed along its forward axis against the model's own detections."""
    mask = _relevant(dets, env.group_fn, score_threshold, groups)
    if dets is not None and not getattr(dets, 'valid', True):
        return 0.0, 'perception_unavailable'
    if not mask.any():
        return math.inf, 'no_relevant_detection'
    try:
        ttc = float(env.ttc_fn(float(max(speed_mps, 0.0)), np.asarray(dets.boxes)[mask],
                               np.asarray(dets.scores)[mask], np.asarray(dets.labels)[mask], env.ego,
                               env.lease_params))
    except Exception as e:  # noqa: BLE001  fail conservative (TTC 0) and keep the cause in the logs
        return 0.0, f'ttc_error:{type(e).__name__}:{str(e)[:200]}'
    return (ttc if not math.isnan(ttc) else 0.0), 'ok'


def scene_risk(env, dets, speed_mps, p):
    """Risk in [0, 1] = max(TTC term, proximity term) over relevant detections (model output only)."""
    if dets is not None and not getattr(dets, 'valid', True):
        return 1.0, {'reason': 'perception_unavailable'}
    mask = _relevant(dets, env.group_fn, p['score_threshold'], p['groups'])
    if not mask.any():
        return 0.0, {'reason': 'no_relevant_detection', 'n_relevant': 0}
    ttc, _ = detection_ttc(env, dets, speed_mps, p['score_threshold'], p['groups'])
    r_ttc = float(np.clip((p['ttc_high_s'] - ttc) / (p['ttc_high_s'] - p['ttc_low_s']), 0.0, 1.0)) \
        if math.isfinite(ttc) else 0.0
    centers = np.asarray(dets.boxes, dtype=float)[mask, :2]
    dist = float(np.min(np.linalg.norm(centers - ego_center_lidar(env)[None], axis=1)))
    r_dist = float(np.clip((p['dist_high_m'] - dist) / (p['dist_high_m'] - p['dist_low_m']), 0.0, 1.0))
    return max(r_ttc, r_dist), {'ttc_s': ttc, 'min_center_distance_m': dist, 'r_ttc': r_ttc, 'r_dist': r_dist,
                                'n_relevant': int(mask.sum())}


def detection_brief(dets, index, group_fn=None):
    """Log record of detection `index` of a DetectionSet: label, group, score, decode_boxes() row.

    Diagnostics only (which agent binds a lease); never raises and returns None when unavailable.
    """
    try:
        if dets is None or index is None:
            return None
        i = int(index)
        label = np.asarray(dets.labels).reshape(-1)[i]
        label = label.item() if hasattr(label, 'item') else label
        out = {'index': i, 'label': label, 'score': float(np.asarray(dets.scores, dtype=float).reshape(-1)[i]),
               'box': [float(v) for v in np.asarray(dets.boxes, dtype=float)[i]]}
        if group_fn is not None:
            out['group'] = str(np.asarray(group_fn(np.asarray([label])), dtype=object).reshape(-1)[0])
        return out
    except Exception:  # noqa: BLE001  logging must never change or break the lease
        return None


def _to_frame(points_xy, src_l2g, dst_l2g):
    T = np.linalg.inv(np.asarray(dst_l2g, dtype=float)) @ np.asarray(src_l2g, dtype=float)
    return np.asarray(points_xy, dtype=float) @ T[:2, :2].T + T[:2, 3]


def detection_change(prev, cur, env, score_threshold, groups, radius_m, shift_m):
    """Observable scene change between two consecutive detection sets (both model outputs).

    The previous set is propagated to the current capture time with its own velocities and moved into the
    current LiDAR frame with the agent's pose estimates. A relevant object within radius_m that has no same-group
    counterpart within shift_m (appeared / moved) or a previous one that disappeared counts as a change.
    """
    if prev is None or cur is None:
        return False, {'reason': 'no_reference'}
    if not getattr(prev, 'valid', True) or not getattr(cur, 'valid', True):
        return True, {'reason': 'perception_unavailable'}
    mp = _relevant(prev, env.group_fn, score_threshold, groups)
    mc = _relevant(cur, env.group_fn, score_threshold, groups)
    pb = np.asarray(prev.boxes, dtype=float)[mp] if mp.any() else np.zeros((0, 7))
    cb = np.asarray(cur.boxes, dtype=float)[mc] if mc.any() else np.zeros((0, 7))
    dt = float(cur.capture_s) - float(prev.capture_s)
    pc = _to_frame(pb[:, :2] + pb[:, 5:7] * dt, prev.lidar2global, cur.lidar2global) if len(pb) else np.zeros((0, 2))
    cc = cb[:, :2]
    pg = np.asarray(env.group_fn(np.asarray(prev.labels)[mp]), dtype=object).reshape(-1) if len(pb) else np.zeros(0, object)
    cg = np.asarray(env.group_fn(np.asarray(cur.labels)[mc]), dtype=object).reshape(-1) if len(cb) else np.zeros(0, object)
    pin = np.linalg.norm(pc, axis=1) <= radius_m if len(pc) else np.zeros(0, bool)
    cin = np.linalg.norm(cc, axis=1) <= radius_m if len(cc) else np.zeros(0, bool)
    if len(pc) and len(cc):
        d = np.linalg.norm(cc[:, None, :] - pc[None, :, :], axis=2)
        d = np.where(cg[:, None] == pg[None, :], d, np.inf)
        appeared = int(np.sum(cin & (d.min(axis=1) > shift_m)))
        vanished = int(np.sum(pin & (d.min(axis=0) > shift_m)))
    else:
        appeared, vanished = int(cin.sum()), int(pin.sum())
    changed = appeared + vanished > 0
    return changed, {'reason': 'changed' if changed else 'stable', 'appeared_or_moved': appeared,
                     'vanished': vanished, 'n_prev': int(pin.sum()), 'n_cur': int(cin.sum()), 'dt_s': dt}


def ego_state_change(ref_obs, obs, speed_delta_mps, yaw_delta_rad, command_change=True):
    """Ego-state events from the agent's own speedometer / compass / route command."""
    reasons = []
    if abs(float(obs.speed_mps) - float(ref_obs.speed_mps)) > speed_delta_mps:
        reasons.append('speed')
    if abs(wrap_angle(float(obs.yaw_rad) - float(ref_obs.yaw_rad))) > yaw_delta_rad:
        reasons.append('yaw')
    if command_change and int(obs.command) != int(ref_obs.command):
        reasons.append('command')
    return reasons


# ----------------------------------------------------------------------------------------------- base

class Policy:
    """Base class: work-conserving, fixed target depth, final-depth-only exposure, H_max validity."""
    name = 'base'
    PARAMS: dict = {}

    def __init__(self, env: Optional[PolicyEnv] = None, **params):
        unknown = sorted(set(params) - set(self.PARAMS))
        if unknown:
            raise ValueError(f'{self.name}: unknown parameters {unknown}; allowed {sorted(self.PARAMS)}')
        self.params = {**self.PARAMS, **params}
        if 'groups' in self.params:
            self.params['groups'] = tuple(self.params['groups'])
        self.env = env
        self._check()

    def _check(self):
        for key in ('depth', 'min_depth', 'max_depth'):
            if key in self.params and not 1 <= int(self.params[key]) <= MAX_DEPTH:
                raise ValueError(f'{self.name}: {key} must be in [1, {MAX_DEPTH}]')

    # -- description
    @property
    def anytime(self):
        """Expose every intermediate depth to the committer (anytime refinement)."""
        return False

    @property
    def work_conserving(self):
        return True

    def describe(self):
        return {'name': self.name, 'title': POLICY_TITLES.get(self.name, self.name), 'class': type(self).__name__,
                'anytime': self.anytime, 'work_conserving': self.work_conserving, 'params': dict(self.params)}

    # -- decisions
    def on_job_start(self, job, ctx):
        job.target_depth = int(ctx.config.max_depth)

    def after_prefix(self, job, ctx):
        pass

    def validity(self, cand, ctx):
        return max_age_validity(cand, ctx)

    def offers(self, job, depth):
        return True if self.anytime else depth == job.target_depth

    def continue_refinement(self, job, ctx):
        if job.depth < job.target_depth:
            return True, 'below_target_depth'
        return False, 'target_depth'

    def idle_start_time(self, ctx):
        return ctx.idle_since_s


# ----------------------------------------------------------------------------------------------- baselines

class FastOnly(Policy):
    """Minimal necessary inference per observation; a new observation whenever the GPU is free."""
    name = 'fast_only'
    PARAMS = {'depth': 1}

    def on_job_start(self, job, ctx):
        job.target_depth = int(self.params['depth'])


class FixedDeep(Policy):
    """All refinement steps; only the complete plan reaches the committer; refresh whenever free."""
    name = 'fixed_deep'
    PARAMS = {'depth': MAX_DEPTH}

    def on_job_start(self, job, ctx):
        job.target_depth = int(self.params['depth'])


class FixedRefresh(Policy):
    """Observation refresh on a fixed grid t0 + phase_s + k * period_s (t0 = first control tick).

    Between refreshes the job refines up to `depth` (anytime: every depth is offered when anytime=True); a
    refresh instant that falls inside a job preempts it at the next step boundary (after the minimum depth).
    The GPU idles until the next grid instant once the target depth is reached (not work-conserving).
    """
    name = 'fixed_refresh'
    PARAMS = {'period_s': 1.0, 'phase_s': 0.0, 'depth': MAX_DEPTH, 'anytime': True}

    def _check(self):
        super()._check()
        if not self.params['period_s'] > 0:
            raise ValueError('fixed_refresh: period_s must be > 0')

    @property
    def anytime(self):
        return bool(self.params['anytime'])

    @property
    def work_conserving(self):
        return False

    def next_refresh_after(self, t, ctx):
        origin = float(ctx.episode_start_s) + float(self.params['phase_s'])
        period = float(self.params['period_s'])
        k = math.floor((float(t) - origin) / period + 1e-9) + 1
        return origin + max(k, 0) * period

    def on_job_start(self, job, ctx):
        job.target_depth = int(self.params['depth'])
        job.policy_state['next_refresh_s'] = self.next_refresh_after(job.start_s, ctx)

    def continue_refinement(self, job, ctx):
        if ctx.now_s >= job.policy_state['next_refresh_s'] - EPS_S:
            return False, 'period_elapsed'
        return super().continue_refinement(job, ctx)

    def idle_start_time(self, ctx):
        if ctx.last_job is None:
            return ctx.idle_since_s
        return self.next_refresh_after(ctx.last_job.start_s, ctx)


class RiskAdaptive(Policy):
    """Budget routing: depth = min_depth + round((max_depth - min_depth) * risk) (high risk -> deeper).

    risk = max(TTC term, proximity term) from the job's own detections, decided when the prefix finishes (the
    first moment they exist). high_risk_deep=False reverses the mapping (high risk -> shallower, fresher).
    Only the chosen depth is exposed; refresh whenever the GPU is free.
    """
    name = 'risk_adaptive'
    PARAMS = {'min_depth': 1, 'max_depth': MAX_DEPTH, 'ttc_low_s': 1.5, 'ttc_high_s': 4.0, 'dist_low_m': 8.0,
              'dist_high_m': 25.0, 'score_threshold': 0.3, 'groups': ('vehicle', 'pedestrian'),
              'high_risk_deep': True}

    def _check(self):
        super()._check()
        p = self.params
        if not (p['min_depth'] <= p['max_depth'] and p['ttc_low_s'] < p['ttc_high_s']
                and p['dist_low_m'] < p['dist_high_m']):
            raise ValueError('risk_adaptive: need min_depth <= max_depth, ttc_low < ttc_high, dist_low < dist_high')

    def on_job_start(self, job, ctx):
        job.target_depth = int(self.params['max_depth'])  # provisional until the detections exist

    def after_prefix(self, job, ctx):
        p = self.params
        risk, info = scene_risk(self.env, job.dets, job.obs.speed_mps, p)
        span = int(p['max_depth']) - int(p['min_depth'])
        steps = int(round(span * risk))
        depth = int(p['min_depth']) + steps if p['high_risk_deep'] else int(p['max_depth']) - steps
        job.target_depth = depth
        job.policy_state.update(risk=risk, risk_info=info, chosen_depth=depth)


class AoIBased(Policy):
    """Age-only scheduling: refine the newest observation while its age budget, with refresh reservation, allows.

    continue while (t_k + age_budget_s) - now - [L_refresh_bound + G] >= next step cost. Work-conserving by
    default (refresh immediately when the budget is spent or refinement is complete); with work_conserving=False
    the GPU waits until the incumbent's age budget minus the reservation is reached.
    """
    name = 'aoi'
    PARAMS = {'age_budget_s': 2.0, 'reservation': True, 'work_conserving': True}

    @property
    def anytime(self):
        return True

    @property
    def work_conserving(self):
        return bool(self.params['work_conserving'])

    def continue_refinement(self, job, ctx):
        slack = reservation_slack(job.obs.capture_s + float(self.params['age_budget_s']), ctx, job.depth,
                                  bool(self.params['reservation']))
        job.policy_state['last_slack_s'] = slack
        return (True, 'age_budget_slack') if slack >= 0 else (False, 'age_budget_exhausted')

    def idle_start_time(self, ctx):
        if self.work_conserving or ctx.incumbent is None:
            return ctx.idle_since_s
        reserve = ctx.profile.refresh_bound_s + ctx.config.guard_s if self.params['reservation'] else 0.0
        return max(ctx.idle_since_s, ctx.incumbent.capture_s + float(self.params['age_budget_s']) - reserve)


class TTCBased(Policy):
    """Refresh as soon as the TTC from the model's own detections drops below threshold_s.

    TTC is computed once per observation (when its prefix finishes) with the ego at its measured speed along the
    forward axis and the detected agents at constant velocity (framelease_v2.lease.ttc_seconds), and aged
    linearly afterwards: TTC(now) = TTC(t_k) - (now - t_k). While TTC(now) >= threshold the observation is
    refined (anytime) up to max depth; max_age_reservation additionally refreshes in time for H_max.
    """
    name = 'ttc'
    PARAMS = {'threshold_s': 3.0, 'score_threshold': 0.3, 'groups': ('vehicle', 'pedestrian'),
              'max_age_reservation': True}

    @property
    def anytime(self):
        return True

    def after_prefix(self, job, ctx):
        ttc, status = detection_ttc(self.env, job.dets, job.obs.speed_mps, self.params['score_threshold'],
                                    self.params['groups'])
        job.policy_state.update(ttc_at_capture_s=ttc, ttc_status=status)

    def continue_refinement(self, job, ctx):
        ttc_now = float(job.policy_state.get('ttc_at_capture_s', 0.0)) - (ctx.now_s - job.obs.capture_s)
        job.policy_state['ttc_now_s'] = ttc_now
        if ttc_now < float(self.params['threshold_s']):
            return False, 'ttc_below_threshold'
        if self.params['max_age_reservation'] and \
                reservation_slack(job.obs.capture_s + ctx.config.max_age_s, ctx, job.depth) < 0:
            return False, 'max_age_reservation'
        return True, 'ttc_clear'


class EventTriggered(Policy):
    """Inference triggered by observable scene changes; the GPU otherwise idles.

    Events: ego speed / heading / route-command change since the capture of the newest processed observation
    (agent sensors), or a detection-set change between the two most recent prefixes (model outputs). A running
    job is preempted at the next step boundary on an ego event; otherwise it refines (anytime) up to max depth.
    Without events the next job starts when the incumbent reaches H_max minus the refresh reservation.
    """
    name = 'event'
    PARAMS = {'speed_delta_mps': 1.0, 'yaw_delta_rad': 0.10, 'command_change': True, 'det_shift_m': 2.0,
              'det_radius_m': 30.0, 'score_threshold': 0.3, 'groups': ('vehicle', 'pedestrian'),
              'max_age_reservation': True}

    @property
    def anytime(self):
        return True

    @property
    def work_conserving(self):
        return False

    def _ego_event(self, ref_obs, obs):
        p = self.params
        return ego_state_change(ref_obs, obs, p['speed_delta_mps'], p['yaw_delta_rad'], p['command_change'])

    def after_prefix(self, job, ctx):
        p = self.params
        changed, info = detection_change(ctx.prev_dets, job.dets, self.env, p['score_threshold'], p['groups'],
                                         p['det_radius_m'], p['det_shift_m'])
        job.policy_state.update(det_event=bool(changed), det_change=info)

    def continue_refinement(self, job, ctx):
        reasons = self._ego_event(job.obs, ctx.newest_obs)
        if reasons:
            return False, 'event:' + '+'.join(reasons)
        if self.params['max_age_reservation'] and \
                reservation_slack(job.obs.capture_s + ctx.config.max_age_s, ctx, job.depth) < 0:
            return False, 'max_age_reservation'
        return True, 'no_event'

    def idle_start_time(self, ctx):
        last = ctx.last_job
        if last is None:
            return ctx.idle_since_s
        if last.policy_state.get('det_event'):
            return ctx.idle_since_s
        if self._ego_event(last.obs, ctx.newest_obs):
            return ctx.now_s
        base = ctx.incumbent.capture_s if ctx.incumbent is not None else last.obs.capture_s
        cap = base + ctx.config.max_age_s - (ctx.profile.refresh_bound_s + ctx.config.guard_s)
        return max(ctx.idle_since_s, cap)


class FrameLease(Policy):
    """Action-validity lease + refresh-time reservation (blueprint Sec. 4-5, Algorithm 1).

    Every released candidate gets H_k = compute_lease(plan, own detections) (recomputed whenever refinement changes
    the plan) and the deadline D_k = t_k + H_k, which is both its commit deadline and its control expiry. At each
    step boundary the job continues only while D_k - now - L_refresh_bound - G >= next step cost; otherwise the
    GPU refreshes the newest frame. Work-conserving: once refinement is complete the newest frame is processed.
    Ablations: lease_source in {'action', 'fixed', 'ttc'} (A1: action-conditioned vs fixed TTL / age-only vs
    TTC-only validity), reservation=False (A2), versioned commit is a runtime switch (A3).
    """
    name = 'framelease'
    PARAMS = {'lease_source': 'action', 'reservation': True, 'work_conserving': True, 'fixed_lease_s': 1.5,
              'ttc_threshold_s': 3.0, 'plan_change_tol_m': 1e-3}
    # Lease-result keys copied into the logged validity (diagnostics; the deadline uses lease_s alone).
    VALIDITY_LOG_KEYS = ('margin_m', 'binding_index', 'reason', 'ttc_s', 'error', 'binding_group', 'binding_tau_s',
                         'closest_index', 'n_confident', 'n_low_confidence', 'lease_confident_only_s', 'binding_det',
                         'closest_det')

    def __init__(self, env=None, **params):
        super().__init__(env, **params)
        self._cache = {}  # job_id -> (plan, result) of the latest computed lease

    def _check(self):
        super()._check()
        if self.params['lease_source'] not in ('action', 'fixed', 'ttc'):
            raise ValueError('framelease: lease_source must be action, fixed or ttc')

    @property
    def anytime(self):
        return True

    @property
    def work_conserving(self):
        return bool(self.params['work_conserving'])

    def _h_max(self):
        return float(getattr(self.env.lease_params, 'h_max_s', 2.0))

    def _lease(self, cand):
        dets = cand.dets
        source = self.params['lease_source']
        if dets is None or not getattr(dets, 'valid', True):
            return {'lease_s': 0.0, 'margin_m': None, 'binding_index': None, 'reason': 'perception_unavailable'}
        if source == 'fixed':
            return {'lease_s': float(np.clip(self.params['fixed_lease_s'], 0.0, self._h_max())), 'margin_m': None,
                    'binding_index': None, 'reason': 'fixed_ttl'}
        if source == 'ttc':
            ttc, status = detection_ttc(self.env, dets, cand.obs.speed_mps, self.env.lease_params.score_threshold,
                                        tuple(getattr(self.env.lease_params, 'relevant_groups',
                                                      ('vehicle', 'pedestrian'))))
            lease = float(np.clip(ttc - float(self.params['ttc_threshold_s']), 0.0, self._h_max())) \
                if not math.isnan(ttc) else 0.0
            return {'lease_s': lease, 'margin_m': None, 'binding_index': None, 'reason': 'ttc:' + status,
                    'ttc_s': ttc}
        try:
            r = self.env.lease_fn(np.asarray(cand.plan_xy, dtype=float), np.asarray(dets.boxes, dtype=float),
                                  np.asarray(dets.scores, dtype=float), np.asarray(dets.labels), self.env.ego,
                                  self.env.lease_params)
        except Exception as e:  # noqa: BLE001  a failed validity check never extends validity: lease 0
            return {'lease_s': 0.0, 'margin_m': None, 'binding_index': None,
                    'reason': f'lease_error:{type(e).__name__}', 'error': str(e)[:300]}
        out = dict(r)
        # Diagnostics only (RUNTIME_CHANGES.md): the binding and the closest confident detection; the deadline
        # still depends on lease_s alone.
        for key, index_key in (('binding_det', 'binding_index'), ('closest_det', 'closest_index')):
            brief = detection_brief(dets, out.get(index_key), self.env.group_fn)
            if brief is not None:
                out[key] = brief
        return out

    def validity(self, cand, ctx):
        t0 = time.perf_counter()
        prev = self._cache.get(cand.job_id)
        plan = np.asarray(cand.plan_xy, dtype=float)
        plan_dependent = self.params['lease_source'] == 'action'
        if prev is not None and (not plan_dependent or (
                prev[0].shape == plan.shape and
                float(np.max(np.abs(prev[0] - plan))) <= float(self.params['plan_change_tol_m']))):
            result, recomputed = prev[1], False
        else:
            result, recomputed = self._lease(cand), True
            self._cache = {cand.job_id: (plan.copy(), result)}
        lease_s = result.get('lease_s')
        lease_s = float(lease_s) if lease_s is not None and np.isfinite(lease_s) else 0.0
        lease_s = max(lease_s, 0.0)
        out = {'deadline_s': float(cand.capture_s) + lease_s, 'lease_s': lease_s,
               'source': 'lease:' + self.params['lease_source'], 'recomputed': recomputed,
               'lease_wall_s': time.perf_counter() - t0}
        for key in self.VALIDITY_LOG_KEYS:
            if key in result:
                out[key] = result[key]
        return out

    def continue_refinement(self, job, ctx):
        deadline = float(job.last_deadline_s)
        slack = reservation_slack(deadline, ctx, job.depth, bool(self.params['reservation']))
        job.policy_state['last_slack_s'] = slack
        if slack >= 0:
            return True, 'lease_slack'
        return False, ('lease_expired' if deadline <= ctx.now_s else 'lease_slack_exhausted')

    def idle_start_time(self, ctx):
        if self.work_conserving or ctx.incumbent is None:
            return ctx.idle_since_s
        reserve = ctx.profile.refresh_bound_s + ctx.config.guard_s if self.params['reservation'] else 0.0
        return max(ctx.idle_since_s, ctx.incumbent.deadline_s - reserve)


POLICY_CLASSES = {cls.name: cls for cls in (FastOnly, FixedDeep, FixedRefresh, RiskAdaptive, AoIBased, TTCBased,
                                            EventTriggered, FrameLease)}
assert tuple(POLICY_CLASSES) == POLICY_NAMES


def make_policy(name, params=None, env=None):
    if name not in POLICY_CLASSES:
        raise ValueError(f'unknown policy {name!r}; choose from {POLICY_NAMES}')
    return POLICY_CLASSES[name](env=env, **(params or {}))


def validate_policy_params(name, params=None):
    """Parameter check without an environment (used by the launcher before anything is started)."""
    if name == 'oracle_sync':
        if params:
            raise ValueError('oracle_sync takes no policy parameters')
        return {}
    return make_policy(name, params, env=None).params
