"""Agent-process tests of fl_global_shield (framelease_v4/arms_ext/agent_ext.py; PROTOCOL Secs. 4.1, 7.4, 2.3-2.5).
CPU only: the official agent stack with a fake model backend and a fake CARLA world (the fakes of the pinned
framelease_v4/arms/tests/test_agent_launcher_v4.AgentV4Test, reused unchanged); no GPU, no CARLA server; nothing is
written outside temporary directories.

  cd /home/kang/Desktop/DAC && source linux/env.sh && export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 && \
      nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/arms_ext/tests/test_agent_ext.py

What is shown (300 ticks per run, E5, measured costs fixed, scheduler CPU time not charged so that runs compare
exactly; the scene cycles through every lease case, helpers_ext.scene_boxes):
  * the run: FrameLeaseV4ExtAgent, a subclass of the pinned FrameLeaseV4Agent (agent_v4.build_agent_class), goes
    through setup / run_step / destroy with the fast prefix and the actor log; the agent's own setup registers the
    a_det^4 utility (as in the evaluator's fresh process); runtime V4Runtime, policy kind shield, policy
    GlobalMarginShieldPolicy with the configured global lease;
  * every released candidate's lease equals the offline GLOBAL design recomputed independently from the logged plan
    and the observation's detections (stage_frames.global_H on framelease_v2.lease.lease_geometry, cap H_bar), bit for
    bit; validity source 'global_lease', D = t_k + H; every lease reason of the scene occurs;
  * Eq. 9 with the synthetic margin: every accepted commit has t_commit < D and a margin above delta; no candidate is
    rejected by the margin check (it agrees with the deadline rule); every decision row follows the shield, and every
    choice epoch a_det^4;
  * the extension agent runs an arms_v4 arm (fl_heuristic) exactly as the pinned agent does: identical jobs, ticks,
    decisions and summary blocks (wall-clock fields aside);
  * without relevant agents both leases are H_bar, and fl_global_shield reproduces fl_heuristic job by job, tick by
    tick and decision by decision: the two arms differ only through the lease;
  * the pinned agent refuses the extension arm's configuration.
-I ignores PYTHONPATH, so the import path of linux/env.sh is inserted into sys.path here; the tests skip when the
official agent stack cannot be imported.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

import helpers_ext as H

from framelease_v3.runtime import v3_shield as VS
from framelease_v4.arms_ext import global_shield as GS

TICKS = 300
E5 = str(H.ENVELOPES['E5'])
UTILITY = 'v4_adet_d4'


def scrub(x):
    """Drop wall-clock fields (measured, not simulated) and the run's temporary paths."""
    if isinstance(x, dict):
        return {k: scrub(v) for k, v in x.items() if 'wall' not in k and k not in ('path', 'dir', 'save_path')}
    if isinstance(x, list):
        return [scrub(v) for v in x]
    return x


def empty_dets(obs):
    return H.la.DetectionSet.empty(obs)


class AgentExtTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._paths = H.add_official_stack_paths()
        cls._env = H.Env(IS_BENCH2DRIVE='1', IS_VISUALIZE='0', PLANNER_TYPE='traj')
        cls._env.__enter__()
        try:
            import test_agent_launcher_v4 as TAL              # the pinned v4 agent harness (read-only import)
            cls.TAL = TAL
            TAL.AgentV4Test.setUpClass.__func__(cls)          # official stack or SkipTest
        except BaseException:
            cls.tearDownClass()
            raise
        cls.runs = {}

    @classmethod
    def tearDownClass(cls):
        cls._env.__exit__(None, None, None)
        H.remove_paths(cls._paths)
        H.drop_v4_utilities()

    # ------------------------------------------------------------------ the pinned fakes, reused unchanged
    def world(self):
        return self.TAL.AgentV4Test.world(self)

    def fake_official_setup(self, a, path, hero):
        return self.TAL.AgentV4Test.fake_official_setup(self, a, path, hero)

    def fp_config(self, base):
        return self.TAL.AgentV4Test.fp_config(self, base)

    def fake_handle(self):
        return self.TAL.AgentV4Test.fake_handle(self)

    def input_data(self, rng, frame):
        return self.TAL.AgentV4Test.input_data(rng, frame)

    # ------------------------------------------------------------------ runner
    def run_agent(self, arm, agent='ext', dets_fn=H.scene_dets, utility=UTILITY, ticks=TICKS):
        """One run of the extension agent (agent='ext') or of the pinned FrameLeaseV4Agent ('v4'), configured by
        arms_ext.build_config; the utility is registered by the agent's own setup (fresh-process conditions)."""
        from framelease_v2 import latency_agent as la
        from framelease_v4.arms import agent_v4 as AG
        from framelease_v4.arms_ext import agent_ext as AGX
        from framelease_v4.arms_ext import arms_ext as X
        AE, FP = self.AE, self.FP
        rng = np.random.default_rng(5)
        w, hero = self.world()
        backends, applied, holder = [], [], {}
        with tempfile.TemporaryDirectory() as tmp:
            cfg, _, _ = X.build_config(arm, runtime_params={'overhead_scale': 0.0}, fast_prefix=self.fp_config('v4'),
                                       envelope=E5, policy_params={'utility': utility} if utility else {})
            H.drop_v4_utilities()
            cfg_path = Path(tmp) / 'agent_runtime_config.json'
            cfg_path.write_text(json.dumps(cfg))
            official_setup = self.official.UniDriveVLAB2DAgent.setup
            real_backend, real_apply = la.UniDriveFlowBackend, FP.apply_fast_prefix
            test = self

            def fake_backend(agent_self, agent_cfg):
                b = H.HV.FakeBackend(prefix_s=0.45, step_s=0.018, dets_fn=dets_fn,
                                     use_payload=agent_self._fl_model_inputs)
                backends.append(b)
                return b

            def fake_apply(head, options, strict_sources=True):
                applied.append(tuple(options))
                return test.fake_handle()
            with H.Env(**{AG.ENV_V4_CONFIG: cfg_path, 'SAVE_PATH': tmp, AE.ENV_FASTPREFIX_CONFIG: None}):
                self.official.UniDriveVLAB2DAgent.setup = lambda s, p: test.fake_official_setup(s, p, hero)
                la.UniDriveFlowBackend = fake_backend
                FP.apply_fast_prefix = fake_apply
                try:
                    cls = (AGX if agent == 'ext' else AG).build_agent_class(world_fn=lambda: w)
                    obj = cls.__new__(cls)
                    obj.setup('unused')
                    holder['policy'] = obj._fl_runtime.policy
                    holder['mro'] = [c.__name__ for c in type(obj).__mro__]
                    holder['registered'] = utility in VS.UTILITIES if utility else None
                    for k in range(ticks):
                        obj.run_step(self.input_data(rng, k + 1), (k + 1) * H.HV.DT)
                        w.step(H.HV.DT)
                    obj.destroy()
                finally:
                    self.official.UniDriveVLAB2DAgent.setup = official_setup
                    la.UniDriveFlowBackend, FP.apply_fast_prefix = real_backend, real_apply
            out = Path(tmp) / 'framelease'

            def stream(name):
                p = out / f'{name}.jsonl'
                return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
            return {'cls': cls.__name__, 'mro': holder['mro'], 'policy': holder['policy'],
                    'registered': holder['registered'], 'applied': applied, 'backends': backends, 'cfg': cfg,
                    'summary': json.loads((out / 'summary.json').read_text()),
                    'agent_config': json.loads((out / 'agent_config.json').read_text()),
                    'ticks': stream('ticks'), 'jobs': stream('jobs'), 'decisions': stream('decisions'),
                    'files': sorted(p.name for p in out.iterdir())}

    def cached(self, key, *args, **kw):
        """run_agent once per class (several tests read the same run)."""
        if key not in self.runs:
            self.runs[key] = self.run_agent(*args, **kw)
        return self.runs[key]

    # ------------------------------------------------------------------ tests
    def test_global_shield_run(self):
        r = self.cached('gs_scene', 'fl_global_shield')
        self.assertEqual(r['cls'], 'FrameLeaseV4ExtAgent')
        self.assertEqual(r['mro'][1], 'FrameLeaseV4Agent')                  # the pinned agent class, subclassed
        self.assertEqual(r['applied'], [self.FP.OPTIONS])                    # fast prefix applied once
        self.assertEqual(r['backends'][0].warmups, 1)
        self.assertTrue(r['registered'])                                     # a_det^4 registered by the agent
        pol = r['policy']
        self.assertIsInstance(pol, GS.GlobalMarginShieldPolicy)
        self.assertEqual((pol.utility.name, pol.params['max_depth']), (UTILITY, 10))
        s = r['summary']
        self.assertEqual((s['v4']['runtime_class'], s['v4']['policy_kind'], s['v4']['policy_name']),
                         ('V4Runtime', 'shield', 'fl_global_shield'))
        self.assertEqual(s['ticks'], TICKS)
        self.assertEqual(s['actor_log']['ticks_logged'], TICKS)
        self.assertEqual(s['actor_log']['errors'], 0)
        self.assertIn('agent_config.json', r['files'])
        ac = r['agent_config']
        self.assertEqual((ac['v4']['arm'], ac['policy']['class'], ac['runtime_class']),
                         ('fl_global_shield', 'GlobalMarginShieldPolicy', 'V4Runtime'))
        self.assertEqual(ac['policy']['global_lease'], r['cfg']['extension']['global_lease'])
        # every released candidate: the offline GLOBAL lease, recomputed independently
        env = H.lease_env('E5')
        prm = GS.global_lease_params(env)
        reasons, n = {}, 0
        for job in r['jobs']:
            boxes, scores, labels = H.scene_boxes(job['obs_id'])
            for st in job['steps']:
                v = st.get('validity')
                if v is None:
                    continue
                n += 1
                want = H.plain_global_H(np.asarray(st['plan'], dtype=float), boxes, scores, labels, env, prm)
                self.assertEqual(v['lease_s'], want, (job['job_id'], st['depth'], v['reason']))
                self.assertEqual((v['source'], v['tau_star_s'], v['lease_kind']), ('global_lease', None, 'global'))
                self.assertEqual(v['deadline_s'], float(job['capture_s']) + float(v['lease_s']))
                self.assertIn(v['reason'], GS.REASONS)
                reasons[v['reason']] = reasons.get(v['reason'], 0) + 1
                c = st.get('commit') or {}
                if c.get('accepted'):
                    self.assertLess(c['commit_s'], v['deadline_s'])
                    self.assertGreater(c['margin_at_commit_m'], env.cfg.delta_m)
                self.assertNotEqual(c.get('reason'), 'margin_violated_at_commit')
                if c.get('reason') == 'expired_before_commit':
                    self.assertGreaterEqual(c['commit_s'], v['deadline_s'])
        self.assertGreater(n, 50)
        self.assertLessEqual(set(H.SCENE_PHASES), set(reasons), reasons)
        self.assertEqual(s['v3']['margin_rejects'], 0)
        self.assertEqual(s['v3']['lease_reasons'], reasons)
        self.assertGreater(s['commits'], 10)
        # decisions: the shield and a_det^4
        rows = r['decisions']
        self.assertEqual(s['v4']['decisions'], len(rows))
        self.assertTrue(all(x['action'] in x['feasible'] or not x['admitted'] for x in rows))
        both = [x for x in rows if x['p_both']]
        self.assertTrue(both)
        for x in both:
            self.assertEqual(x['reason'], f'both_feasible:{UTILITY}')
            self.assertEqual(x['action'], 'REFINE' if x['depth'] < 4 else 'REFRESH')
        self.assertTrue(all(x['features']['tau_star_s'] is None and x['features']['min_g_m'] is None
                            for x in rows))
        print('\nfl_global_shield run:', {'candidates': n, 'lease_reasons': reasons, 'commits': s['commits'],
                                          'decisions': len(rows), 'choice_epochs': len(both)})

    def test_extension_agent_runs_an_arms_v4_arm_as_the_pinned_agent(self):
        ext = self.cached('ext_flh', 'fl_heuristic', agent='ext')
        pin = self.cached('v4_flh', 'fl_heuristic', agent='v4')
        self.assertEqual((ext['cls'], pin['cls']), ('FrameLeaseV4ExtAgent', 'FrameLeaseV4Agent'))
        self.assertEqual(type(ext['policy']).__name__, 'ShieldedHeuristicPolicy')
        for key in ('jobs', 'ticks', 'decisions'):
            self.assertEqual(scrub(ext[key]), scrub(pin[key]), key)
        self.assertGreater(len(ext['jobs']), 10)
        for key in ('v3', 'v4', 'jobs', 'commits', 'ticks', 'fallback_tick_ratio', 'action_age_s', 'gpu_busy_ratio'):
            self.assertEqual(scrub(ext['summary'][key]), scrub(pin['summary'][key]), key)
        a, b = dict(ext['agent_config']), dict(pin['agent_config'])
        self.assertEqual(scrub(a['policy']), scrub(b['policy']))
        self.assertEqual(a['v4'], b['v4'])

    def test_without_agents_the_arm_reproduces_fl_heuristic(self):
        gs = self.cached('gs_empty', 'fl_global_shield', dets_fn=empty_dets, utility=None)
        fh = self.cached('flh_empty', 'fl_heuristic', agent='v4', dets_fn=empty_dets, utility=None)
        jp = self.TAL.job_projection
        self.assertEqual([jp(j) for j in gs['jobs']], [jp(j) for j in fh['jobs']])
        self.assertEqual([H.HV.tick_projection(t) for t in gs['ticks']], [H.HV.tick_projection(t) for t in fh['ticks']])
        self.assertEqual(scrub(gs['decisions']), scrub(fh['decisions']))
        self.assertGreater(len(gs['decisions']), 50)
        sv, fv = scrub(gs['summary']['v3']), scrub(fh['summary']['v3'])
        self.assertEqual(sv, fv)
        released = sum(1 for j in gs['jobs'] for st in j['steps'] if 'validity' in st)
        self.assertEqual(sv['lease_reasons'], {'no_relevant_agents': released})
        g4, f4 = scrub(gs['summary']['v4']), scrub(fh['summary']['v4'])
        self.assertEqual((g4.pop('policy_name'), f4.pop('policy_name')), ('fl_global_shield', 'fl_v3_heuristic'))
        self.assertEqual(g4, f4)
        sources = {st['validity']['source'] for j in gs['jobs'] for st in j['steps'] if 'validity' in st}
        self.assertEqual(sources, {'global_lease'})

    def test_the_pinned_agent_refuses_the_extension_arm(self):
        with self.assertRaises((KeyError, ValueError)):
            self.run_agent('fl_global_shield', agent='v4', ticks=1)


if __name__ == '__main__':
    unittest.main()
