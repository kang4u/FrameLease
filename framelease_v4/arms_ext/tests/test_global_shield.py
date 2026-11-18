"""CPU tests of the global-margin lease of fl_global_shield (framelease_v4/arms_ext/global_shield.py; PROTOCOL Secs. 4.1,
7.4, 2.4). No GPU, no CARLA, no model; reads the exported envelopes and the recorded offline frames, writes nothing.

  cd /home/kang/Desktop/DAC && nice -n 19 env CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 \
      .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider framelease_v4/arms_ext/tests

What is shown:
  * P equals the offline lease parameters (framelease_v3/suffix_lease_eval.iso_params of the configuration each exported
    file holds: T_x0.60 / T_x0.30 / T_x0.00) except margin_mode, and the constants are those of PROTOCOL Sec. 2.4;
  * on every recorded frame of the offline stage (37 clips, depth-1 plans, the model's own detections), H of the
    policy equals the stored global lease min(hg_T, H_bar) of stage_frames.global_H for E5, E10 and B0 exactly, as
    test_export_envelopes.py shows it for the suffix lease; the plain (non-prefiltered) evaluation and the offline
    function itself, recomputed on lease_geometry, agree bit for bit;
  * the exact prefilter changes nothing on random scenes either (moving agents, low-confidence detections, clutter);
  * invalid perception or a non-finite plan gives H = 0, no relevant agent gives H_bar; an internal error gives H = 0
    and no commit-time margin, still labelled as a global lease;
  * the commit-time margin agrees with the deadline rule: M(t_commit - t_k) > delta <=> t_commit - t_k < H, and the
    Eq. 9 gate with the policy's margin check decides as the deadline alone;
  * the validity row is a global lease (source 'global_lease', no tau*), and the per-candidate CPU time of the lease
    is that of the v3 suffix lease, not of the plain v2 evaluation (reported).
"""
from __future__ import annotations

import math
import time
import unittest

import numpy as np

import helpers_ext as H

from framelease_v2 import lease as L2
from framelease_v3.runtime import v3_commit as VC
from framelease_v3.runtime import v3_lease as VL
from framelease_v3.runtime import v3_scheduler as S
from framelease_v4.arms import policies_v4 as PV
from framelease_v4.arms_ext import global_shield as GS

LABELS = ('E5', 'E10', 'B0')


class ParametersTest(unittest.TestCase):
    def test_lease_params_are_the_offline_iso_params(self):
        import json
        from framelease_v3 import suffix_lease_eval as sle
        from framelease_v4.offline import common as C
        from framelease_v4.offline import export_envelopes as X
        train = json.loads(X.TRAIN_ENVELOPES.read_text(encoding='utf-8'))
        for label in LABELS:
            env = H.lease_env(label)
            p = GS.global_lease_params(env)
            ref = sle.iso_params({k: train['configs'][H.OFFLINE_CONFIGS[label]][k] for k in X.PARAMS})
            a, b = p.to_dict(), ref.to_dict()
            self.assertEqual((a.pop('margin_mode'), b.pop('margin_mode')), ('global', 'time_resolved'), label)
            self.assertEqual(a, b, label)
            # PROTOCOL Sec. 2.4: T_pred 3.0 s (0.05 s grid), T_c 0.5 s, H_bar 2.5 s, d_safe 0.5 m, delta 0.2 m;
            # vehicles and pedestrians with score >= 0.1 count (mode cap), confident at 0.3
            cfg = env.cfg
            self.assertEqual((cfg.t_pred_s, cfg.t_c_s, cfg.h_bar_s, cfg.dt_s), (3.0, 0.5, 2.5, 0.05))
            self.assertEqual((p.d_safe_m, p.reserve_m, p.horizon_s, p.dt_s, p.h_max_s), (0.5, 0.2, 3.0, 0.05, 3.0))
            self.assertEqual((p.score_threshold, p.low_score_floor, p.low_conf_mode), (0.3, 0.1, 'cap'))
            self.assertEqual(p.relevant_groups, ('vehicle', 'pedestrian'))
            self.assertEqual(env.envelope.sha256, C.sha256_file(H.ENVELOPES[label]))
            spec = GS.global_lease_spec(env)
            self.assertEqual((spec['h_bar_s'], spec['reserve_m'], spec['margin_mode']), (2.5, 0.2, 'global'))

    def test_only_isotropic_envelopes_without_motion_bins(self):
        base = H.lease_env('E5')
        for spec in ({'kind': 'iso_table', 'tau_s': [0.0, 3.0], 'B_m': {'vehicle': [0.1, 0.2],
                                                                         'pedestrian': [0.1, 0.2]}},
                     {'kind': 'iso', 'motion_bins': True, 'sigma_m': {'vehicle': 0.1, 'pedestrian': 0.1},
                      'vbar_mps': {'vehicle': 0.1, 'pedestrian': 0.1}, 'abar_mps2': {'vehicle': 0.1,
                                                                                      'pedestrian': 0.1}}):
            env = VL.build_lease_env(str(H.LEASE_PARAMS), envelope_spec=spec)
            with self.assertRaises(ValueError):
                GS.global_lease_params(env)
            with self.assertRaises(ValueError):
                GS.GlobalMarginShieldPolicy(env=env)
        pol = GS.GlobalMarginShieldPolicy(env=base)
        self.assertIsInstance(pol, S.ShieldedHeuristicPolicy)
        self.assertEqual(pol.params, S.ShieldedHeuristicPolicy(env=base).params)       # fl_heuristic's parameters
        d = pol.describe()
        self.assertEqual((d['name'], d['class'], d['utility']), ('fl_global_shield', 'GlobalMarginShieldPolicy',
                                                                 'heuristic'))
        self.assertEqual(d['global_lease'], GS.global_lease_spec(base))


class RecordedFramesTest(unittest.TestCase):
    """The policy's H on the recorded offline frames equals the stored global lease (stage_frames.global_H, hg_T)."""

    @classmethod
    def setUpClass(cls):
        if not H.offline_ready():
            raise unittest.SkipTest('offline lease-ablation frames not available')
        cls.envs = {label: H.lease_env(label) for label in LABELS}
        cls.pols = {label: GS.GlobalMarginShieldPolicy(env=env) for label, env in cls.envs.items()}

    def test_policy_H_equals_stored_global_lease_on_every_frame(self):
        out = {label: {'n': 0, 'max_abs': 0.0, 'reasons': {}} for label in LABELS}
        frames, clips = 0, set()
        for name, i, d, plan, det7, score, label in H.recorded_frames():
            frames += 1
            clips.add(name)
            dets = H.dets_ns(det7, score, label)
            for lab, pol in self.pols.items():
                col = d['names_T'].index(H.OFFLINE_CONFIGS[lab])
                stored = float(min(d['hg_T'][i, col], pol.env.cfg.h_bar_s))
                pol.after_prefix(H.candidate(plan, dets, job_id=frames), None)
                res = pol.compute_lease(H.candidate(plan, dets, job_id=frames))
                o = out[lab]
                o['n'] += 1
                o['max_abs'] = max(o['max_abs'], abs(float(res.lease_s) - stored))
                o['reasons'][res.reason] = o['reasons'].get(res.reason, 0) + 1
                self.assertEqual(float(res.lease_s), stored, (name, i, lab, res.reason))
        self.assertEqual(len(clips), 37)
        self.assertEqual(frames, 6421)
        for lab in LABELS:
            self.assertEqual(out[lab]['max_abs'], 0.0, lab)
            r = out[lab]['reasons']
            self.assertGreater(r.get('global_zero', 0), 100, (lab, r))                # H = 0 cases
            self.assertGreater(r.get('global_cap', 0) + r.get('no_relevant_agents', 0), 100, (lab, r))   # H_bar
            if lab != 'B0':                                                            # B = 0: H is 0 or H_bar
                self.assertGreater(r.get('global_lease', 0), 100, (lab, r))
            self.assertTrue(set(r) <= set(GS.REASONS), r)
        print('\nrecorded frames:', frames, {lab: (out[lab]['n'], out[lab]['max_abs'], out[lab]['reasons'])
                                             for lab in LABELS})

    def test_prefilter_plain_and_offline_function_agree(self):
        """Every 3rd frame: prefiltered == every agent at every grid point == stage_frames.global_H on lease_geometry
        (the offline function itself, recomputed), bit for bit; the CPU time per candidate is reported."""
        t = {'prefiltered': 0.0, 'plain': 0.0, 'suffix_v3': 0.0, 'v2_lease_geometry': 0.0}
        n = 0
        for name, i, d, plan, det7, score, label in H.recorded_frames(every=3):
            for lab, env in self.envs.items():
                pol = self.pols[lab]
                agents = VL.prepare_agents(det7, score, label, env)
                t0 = time.perf_counter()
                h_pre, r_pre, _ = GS.global_margin_lease(plan, agents, env, pol.lease_params, prefilter=True)
                t1 = time.perf_counter()
                h_all, r_all, _ = GS.global_margin_lease(plan, agents, env, pol.lease_params, prefilter=False)
                t2 = time.perf_counter()
                VL.suffix_lease(plan, agents, env)
                t3 = time.perf_counter()
                h_off = H.plain_global_H(plan, det7, score, label, env, pol.lease_params)
                t4 = time.perf_counter()
                t['prefiltered'] += t1 - t0
                t['plain'] += t2 - t1
                t['suffix_v3'] += t3 - t2
                t['v2_lease_geometry'] += t4 - t3
                n += 1
                self.assertEqual((h_pre, r_pre), (h_all, r_all), (name, i, lab))
                self.assertEqual(h_pre, h_off, (name, i, lab))
        self.assertGreater(n, 6000)
        ms = {k: round(1e3 * v / n, 3) for k, v in t.items()}
        print('\nCPU ms per candidate (every 3rd frame x 3 envelopes):', n, ms)


class RandomScenesTest(unittest.TestCase):
    def test_prefilter_is_exact_on_random_scenes(self):
        rng = np.random.default_rng(20261111)
        envs = {label: H.lease_env(label) for label in LABELS}
        params = {label: GS.global_lease_params(env) for label, env in envs.items()}
        seen = {}
        for trial in range(400):
            n = int(rng.integers(0, 14))
            boxes = np.stack([rng.uniform(-25, 25, n), rng.uniform(-15, 45, n), rng.uniform(0.5, 6.0, n),
                              rng.uniform(0.5, 2.6, n), rng.uniform(-np.pi, np.pi, n), rng.uniform(-9, 9, n),
                              rng.uniform(-9, 9, n)], -1) if n else np.zeros((0, 7))
            scores = rng.uniform(0.0, 1.0, n)
            labels = rng.choice([0, 1, 2, 3, 4, 7, 8], n)
            speed = rng.uniform(0.0, 12.0)
            turn = rng.uniform(-0.15, 0.15)
            t = 0.5 * np.arange(1, 7)
            plan = np.stack([turn * (speed * t) ** 2 / 10.0, speed * t], -1)
            for lab, env in envs.items():
                agents = VL.prepare_agents(boxes, scores, labels, env)
                a = GS.global_margin_lease(plan, agents, env, params[lab], prefilter=True)
                b = GS.global_margin_lease(plan, agents, env, params[lab], prefilter=False)
                self.assertEqual(a[:2], b[:2], (trial, lab))
                self.assertEqual(a[2]['binding_index'], b[2]['binding_index'], (trial, lab))
                self.assertEqual(a[0], H.plain_global_H(plan, boxes, scores, labels, env, params[lab]), (trial, lab))
                seen[a[1]] = seen.get(a[1], 0) + 1
        for reason in ('global_zero', 'global_lease', 'global_cap', 'no_relevant_agents'):
            self.assertGreater(seen.get(reason, 0), 10, seen)

    def test_invalid_inputs_and_empty_scenes(self):
        env = H.lease_env('E5')
        pol = GS.GlobalMarginShieldPolicy(env=env)
        plan = H.HV.straight_plan(None, 1)
        near = [H.vehicle(0.0, 6.0)]
        cases = [
            (np.full((6, 2), np.nan), H.dets_ns(near, [0.9], [0]), 0.0, 'invalid_plan'),
            (plan, None, 0.0, 'perception_unavailable'),
            (plan, H.dets_ns(near, [0.9], [0], valid=False), 0.0, 'perception_unavailable'),
            (plan, H.dets_ns([[0.0, np.nan, 4.5, 1.9, 0.0, 0.0, 0.0]], [0.9], [0]), 0.0, 'invalid_detection'),
            (plan, H.dets_ns(np.zeros((0, 7)), [], []), 2.5, 'no_relevant_agents'),
            (plan, H.dets_ns(near, [0.05], [0]), 2.5, 'no_relevant_agents'),              # below the 0.1 floor
            (plan, H.dets_ns(near, [0.9], [5]), 2.5, 'no_relevant_agents'),               # traffic cone: not relevant
            (plan, H.dets_ns(near, [0.9], [0]), 0.0, 'global_zero'),                      # on the path
            (plan, H.dets_ns(near, [0.2], [0]), 0.0, 'global_zero'),                      # low confidence caps too
            (plan, H.dets_ns([H.vehicle(40.0, 60.0)], [0.9], [0]), 2.5, 'global_cap'),
        ]
        for k, (p, dets, want_h, want_reason) in enumerate(cases):
            cand = H.candidate(p, dets, job_id=k)
            pol.after_prefix(cand, None)
            v = pol.validity(cand, None)
            self.assertEqual((v['lease_s'], v['reason']), (want_h, want_reason), k)
            self.assertEqual((v['source'], v['tau_star_s'], v['lease_kind']), ('global_lease', None, 'global'), k)
            self.assertAlmostEqual(v['deadline_s'], want_h, delta=1e-12)
        cand = H.candidate(plan, H.dets_ns(near, [0.9, 0.8], [0]), job_id=99)    # broken detection set
        pol.after_prefix(cand, None)
        v = pol.validity(cand, None)
        self.assertEqual((v['lease_s'], v['reason']), (0.0, 'perception_unavailable'))
        self.assertIn('error', v)

    def test_an_internal_error_is_conservative_and_keeps_the_label(self):
        env = H.lease_env('E5')
        pol = GS.GlobalMarginShieldPolicy(env=env)
        cand = H.candidate(H.HV.straight_plan(None, 1), H.dets_ns([H.vehicle(0.0, 20.0)], [0.9], [0]), job_id=5)
        coarse = H.lease_env('E5', dt_s=0.1)                                     # agents prepared on another grid
        pol._agents = {5: VL.prepare_agents(cand.dets.boxes, cand.dets.scores, cand.dets.labels, coarse)}
        v = pol.validity(cand, None)
        self.assertEqual((v['lease_s'], v['reason'], v['source'], v['tau_star_s']),
                         (0.0, 'lease_error:ValueError', 'global_lease', None))
        self.assertIn('grid', v['error'])
        self.assertEqual(pol.margin_check(cand, 0.01), (False, None))           # no margin: the commit check fails
        self.assertEqual(pol.counts['lease_reasons']['lease_error:ValueError'], 1)

    def test_binding_agent_and_low_confidence(self):
        env = H.lease_env('E10')
        pol = GS.GlobalMarginShieldPolicy(env=env)
        plan = H.HV.straight_plan(None, 1)
        boxes = [H.vehicle(0.0, 26.0, vy=-1.0), H.vehicle(3.6, 22.0), H.vehicle(-30.0, 0.0)]   # ahead, next lane, far
        for scores, want in (([0.9, 0.9, 0.9], 1), ([0.9, 0.15, 0.9], 1), ([0.9, 0.05, 0.9], 0)):
            cand = H.candidate(plan, H.dets_ns(boxes, scores, [0, 0, 0]))
            pol.after_prefix(cand, None)
            v = pol.validity(cand, None)
            self.assertEqual(v['reason'], 'global_lease', scores)
            self.assertEqual(v['binding_index'], want, scores)
            self.assertEqual(v['binding_confident'], scores[want] >= 0.3, scores)
            self.assertEqual(v['binding_det']['index'], want)
            self.assertTrue(0.0 < v['lease_s'] < 2.5)
            geom = L2.lease_geometry(plan, np.asarray(boxes), np.asarray(scores), np.zeros(3, int), env.ego,
                                     pol.lease_params)
            m = geom.clearance.min(axis=1)
            j = list(geom.index).index(want)
            self.assertAlmostEqual(v['binding_margin_m'], m[j], delta=1e-12)
            self.assertEqual(v['n_relevant'], len(geom.index))


class CommitMarginTest(unittest.TestCase):
    """Eq. 9: the synthetic commit-time margin agrees with the deadline rule t_commit < D = t_k + H."""

    def test_margin_agrees_with_the_deadline(self):
        env = H.lease_env('E5')
        cfg = env.cfg
        plan = H.HV.straight_plan(None, 1)
        rng = np.random.default_rng(7)
        hs = [0.0, 1e-6, 0.05, 0.4644, 0.96, 1.5, 2.2, 2.5 - 1e-6, 2.5] + list(rng.uniform(0.0, 2.5, 40))
        for h in hs:
            syn = PV.age_lease_result(env, h, plan)
            res = GS.GlobalLeaseResult(float(h), syn.tau_star_s, 'global_lease', {}, syn.tau, syn.g, None, None,
                                       syn.t_pred_s)
            self.assertEqual(res.lease_s, syn.lease_s)
            ages = list(rng.uniform(0.0, 2.6, 60)) + [0.0, h, h + 1e-6, max(h - 1e-6, 0.0), 2.5, 2.5 + 1e-6]
            for age in ages:
                if abs(age - h) < 1e-9:
                    continue                                  # the boundary itself (rounding of the interpolant)
                m = res.margin(age, cfg.t_c_s)
                self.assertEqual(m > cfg.delta_m, age < h or (h >= cfg.h_bar_s and age <= cfg.h_bar_s + 1e-9),
                                 (h, age, m))

    def test_gate_with_the_policy_margin_decides_as_the_deadline(self):
        env = H.lease_env('E10')
        pol = GS.GlobalMarginShieldPolicy(env=env)
        plan = H.HV.straight_plan(None, 1)
        rng = np.random.default_rng(11)
        scenes = [[], [H.vehicle(0.0, 6.0)], [H.vehicle(40.0, 60.0)], [H.vehicle(0.0, 32.0, vy=-1.0)],
                  [H.vehicle(3.6, 22.0)], [H.vehicle(0.0, 26.0, vy=-2.0), H.vehicle(-3.5, 12.0, vy=3.0)]]
        checked, lease_values = 0, set()
        for k, boxes in enumerate(scenes):
            dets = H.dets_ns(np.asarray(boxes).reshape(-1, 7), [0.9] * len(boxes), [0] * len(boxes))
            cand = H.candidate(plan, dets, job_id=k + 1, capture_s=10.0)
            pol.after_prefix(cand, None)
            v = pol.validity(cand, None)
            h = v['lease_s']
            lease_values.add(round(h, 6))
            for age in list(rng.uniform(0.0, 2.7, 80)) + [h - 1e-6, h + 1e-6, 0.0]:
                if age < 0 or abs(age - h) < 1e-9:
                    continue
                t_commit = 10.0 + age
                ok_m, m_val = pol.margin_check(cand, t_commit)
                gate = VC.CommitGate()
                accept, reason = gate.check(cand.job_id, VC.Version(cand.obs_id, 1), v['deadline_s'], t_commit,
                                            (True, 'ok'), ok_m)
                self.assertEqual(accept, t_commit < v['deadline_s'], (k, h, age, reason, m_val))
                self.assertNotEqual(reason, 'margin_violated_at_commit', (k, h, age))
                checked += 1
        self.assertGreater(checked, 400)
        self.assertTrue({0.0, 2.5} <= lease_values and any(0 < x < 2.5 for x in lease_values), lease_values)


if __name__ == '__main__':
    unittest.main()
