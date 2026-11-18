"""CPU tests of the v4 agent class, the launcher and the dry-run job lines (fake model, fake CARLA world, no GPU,
no CARLA server). The agent tests need the official stack (`source linux/env.sh`), the launcher / job tests need
CHECKPOINT and CARLA_ROOT; both are skipped otherwise.

  cd /home/kang/Desktop/DAC && source linux/env.sh && CUDA_VISIBLE_DEVICES= \
      .conda-unidrive-linux/bin/python -B -m pytest -q -p no:cacheprovider -W ignore framelease_v4/arms/tests

What is shown:
  * one agent class runs every arm: the real FrameLeaseV4Agent (v2 latency agent + v4 setup + fast prefix + actor log)
    goes through setup / run_step / destroy for each arm and writes ticks, jobs, decisions, summary (with the 'v4',
    'fast_prefix' and 'actor_log' blocks), the fast-prefix manifest and a decodable actor log;
  * same substrate as before: given the same measured costs, the v4 agent's Fixed Deep reproduces every job and tick
    of the fast-prefix v2 agent (FrameLeaseFastPrefixV2Agent), and its FrameLease + Heuristic every job, tick and
    decision row of the fast-prefix v3 agent;
  * evaluation only: with the actor log on or off every tick, job and decision row is identical;
  * the launcher builds, for the v2-rule arms, exactly the agent configuration of the v3-matrix baseline arms and, for
    fl_heuristic, exactly run_closed_loop_v3.v3_configs; command and environment differ from framelease_v2's only by
    the entry and $FRAMELEASE_V4_ARMS_CONFIG; a dry run writes nothing; fl_full needs a learned utility;
  * the 2 x 7 dry-run job lines pass gpu_queue's contract, the pins, the launcher and the exact command's --dry-run.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from helpers_v4 import DT, BBox, FakeBackend, FakeWorld, ROOT

from framelease_v2 import latency_agent as la
from framelease_v4.arms import actor_log as AL
from framelease_v4.arms import arms_v4 as AV


def scrub(x):
    if isinstance(x, dict):
        return {k: scrub(v) for k, v in x.items() if 'wall' not in k}
    if isinstance(x, list):
        return [scrub(v) for v in x]
    return x


def job_projection(row):
    steps = [(s.get('depth'), s.get('release_s'), (s.get('commit') or {}).get('commit_s'),
              (s.get('commit') or {}).get('accepted')) for s in row.get('steps') or []]
    return (row['job_id'], row['obs_id'], row['capture_s'], row['start_s'], row['prefix_end_s'], row['end_s'],
            row['final_depth'], row['stop_reason'], tuple(row['committed_depths']), tuple(steps))


def _official_pid_kwargs(path):
    import ast
    tree = ast.parse(Path(path).read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'PIDControllerVAD']
    return {k.arg: ast.literal_eval(k.value) for k in calls[0].keywords}


class AgentV4Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import torch
            import carla  # noqa: F401
            import team_code.unidrivevla_b2d_agent as official
            from team_code.pid_controller import PIDController
            from mmcv import Config
        except Exception as e:  # noqa: BLE001
            raise unittest.SkipTest(f'official agent stack not importable here: {type(e).__name__}: {e}')
        assert not torch.cuda.is_available(), 'tests must not see the GPU'
        from framelease_v3.fastprefix import agent_entry as AE
        from framelease_v3.fastprefix import fast_path as FP
        cls.official, cls.PID, cls.AE, cls.FP = official, PIDController, AE, FP
        cls.pid_kwargs = _official_pid_kwargs(official.__file__)
        repo = Path(os.environ.get('FRAMELEASE_UNIDRIVE_REPO', ROOT / 'third_party/UniDriveVLA-linux'))
        cls.aug = Config.fromfile(str(repo / 'Bench2Drive/projects/configs/unidrivevla_b2d_stage2_unified_2b.py')).data_aug_conf

    # ------------------------------------------------------------------ fakes
    def world(self):
        import carla
        w = FakeWorld()
        w.add(1, 'vehicle.lincoln.mkz_2020', 10.0, 20.0, 30.0, 4.0, 0.5, BBox(2.45, 1.06), 'hero')
        w.add(7, 'vehicle.audi.a2', 25.0, 22.0, 30.0, 3.0, 0.0, BBox(1.9, 0.9))
        w.add(8, 'walker.pedestrian.0001', 15.0, 30.0, 0.0, 0.0, -1.0, BBox(0.3, 0.3))
        w.add(9, 'traffic.traffic_light', 0.0, 0.0)

        class Hero:
            id, type_id, bounding_box, attributes = 1, 'vehicle.lincoln.mkz_2020', BBox(2.45, 1.06), {'role_name': 'hero'}

            def get_transform(self):
                x, y, yaw, _, _ = w.state[1]
                return carla.Transform(carla.Location(x, y, 0.0), carla.Rotation(yaw=yaw))

            def get_velocity(self):
                return carla.Vector3D(w.state[1][3], w.state[1][4], 0.0)

            def get_acceleration(self):
                return carla.Vector3D(0.1, 0.2, 0.0)

            def get_angular_velocity(self):
                return carla.Vector3D(0.0, 0.0, 0.01)
        return w, Hero()

    def fake_official_setup(self, a, path, hero):
        from agents.navigation.local_planner import RoadOption
        off = self.official
        a.step, a.frame_rate, a.use_bgr_img, a.device = -1, 20, True, 'cpu'
        a.lidar2img, a.lidar2cam, a.lidar2ego = off.LIDAR2IMG, off.LIDAR2CAM, off.LIDAR2EGO
        a.data_aug_conf = self.aug
        a.lat_ref, a.lon_ref = 0.0, 0.0
        a.initialized = True
        a.is_visualize = False
        a.save_path = Path(os.environ['SAVE_PATH'])
        a.save_name = 'cpu_test'
        a.metric_info = {}
        a.prev_control_cache = []
        a.pidcontroller = self.PID(**self.pid_kwargs)

        class Planner:
            def run_step(self, pos):
                return np.array([pos[0] + 5.0, pos[1]]), RoadOption.LANEFOLLOW
        a._route_planner = Planner()

        def pipeline(inputs):
            return {'img': np.zeros((6, 3, 4, 4), np.float32), 'img_metas': np.zeros(1, np.float32),
                    'projection_mat': np.zeros((6, 4, 4), np.float32), 'image_wh': inputs['image_wh'],
                    'timestamp': np.asarray(inputs['timestamp'], np.float64), 'gt_ego_fut_cmd': inputs['gt_ego_fut_cmd'],
                    'ego_status': inputs['ego_status']}
        a.inference_only_pipeline = pipeline

        class Model:
            planning_head = object()

            def __call__(self, **kw):
                raise AssertionError('the latency agent never runs the full model')
        a.model = Model()
        a.hero_actor = hero

    @staticmethod
    def input_data(rng, frame):
        cams = ('CAM_FRONT', 'CAM_FRONT_LEFT', 'CAM_FRONT_RIGHT', 'CAM_BACK', 'CAM_BACK_LEFT', 'CAM_BACK_RIGHT')
        data = {c: (frame, rng.integers(0, 255, (90, 160, 4), dtype=np.uint8)) for c in cams}
        return {**data, 'GPS': (frame, np.array([1.0e-4, 2.0e-4, 0.0])), 'SPEED': (frame, {'speed': np.float64(4.2)}),
                'IMU': (frame, np.array([0.3, -0.1, 9.8, 0.01, -0.02, 0.05, 1.2])),
                'bev': (frame, np.zeros((64, 64, 4), np.uint8))}

    def fp_config(self, base):
        return {'schema': self.AE.CONFIG_SCHEMA, 'base': base, 'options': list(self.FP.OPTIONS), 'validate': True,
                'on_validation_failure': 'raise', 'strict_sources': True, 'arm': 'x_fp', 'base_arm': 'x'}

    def fake_handle(self):
        FP = self.FP

        class FakeHandle(FP.FastPrefix):
            def __init__(self):
                super().__init__(FP.OPTIONS, {}, True)
                self.lora = {'lora_layers': 196}

            @property
            def active(self):
                return {o: True for o in FP.OPTIONS}

            def _judge(self, *args):
                return {'ok': True, 'failures': []}
        return FakeHandle()

    # ------------------------------------------------------------------ runner
    def run_agent(self, kind, arm=None, ticks=70, actor_log=None, policy_params=None, unregister=()):
        """kind 'v4' (FrameLeaseV4Agent, arm) | 'v2fp' (fast-prefix v2 agent, fixed_deep) | 'v3fp' (fast-prefix v3).

        unregister: utility names removed from v3_shield.UTILITIES after the configuration is built, so the agent's
        own setup must register them again (as in the evaluator's fresh agent process)."""
        from framelease_v2 import run_closed_loop as R2
        from framelease_v3.runtime import run_closed_loop_v3 as L
        from framelease_v3.runtime.v3_agent import ENV_V3_CONFIG
        from framelease_v4.arms import agent_v4 as AG
        AE, FP = self.AE, self.FP
        rng = np.random.default_rng(5)
        w, hero = self.world()
        backends, applied = [], []
        with tempfile.TemporaryDirectory() as tmp:
            if kind == 'v4':
                cfg, _, _ = AV.build_config(arm, runtime_params={'overhead_scale': 0.0}, fast_prefix=self.fp_config('v4'),
                                            actor_log=actor_log, policy_params=policy_params)
                env_name, fp_path = AG.ENV_V4_CONFIG, None
                from framelease_v3.runtime import v3_shield as VS
                for name in unregister:
                    VS.UTILITIES.pop(name, None)
            elif kind == 'v2fp':
                with contextlib.redirect_stderr(io.StringIO()):
                    a = L.parse_args(['--arm', 'fixed_deep', '--route-id', '2086', '--output-dir', tmp])
                    cfg = R2.agent_config(R2.parse_args(L.v2_argv(a)))
                cfg['runtime']['overhead_scale'] = 0.0
                env_name = la.ENV_RUNTIME_CONFIG
            else:
                with contextlib.redirect_stderr(io.StringIO()):
                    a = L.parse_args(['--arm', 'fl_v3_heuristic', '--route-id', '2086', '--output-dir', tmp,
                                      '--runtime-params', '{"overhead_scale": 0.0}'])
                    cfg, _, _ = L.v3_configs(a)
                env_name = ENV_V3_CONFIG
            cfg_path = Path(tmp) / 'agent_runtime_config.json'
            cfg_path.write_text(json.dumps(cfg))
            names = (env_name, AE.ENV_FASTPREFIX_CONFIG, 'SAVE_PATH')
            old_env = {k: os.environ.get(k) for k in names}
            os.environ[env_name] = str(cfg_path)
            os.environ['SAVE_PATH'] = tmp
            if kind != 'v4':
                fp_path = Path(tmp) / 'fast_prefix_config.json'
                fp_path.write_text(json.dumps(self.fp_config('v2' if kind == 'v2fp' else 'v3')))
                os.environ[AE.ENV_FASTPREFIX_CONFIG] = str(fp_path)
            official_setup = self.official.UniDriveVLAB2DAgent.setup
            real_backend, real_apply = la.UniDriveFlowBackend, FP.apply_fast_prefix
            test = self

            def fake_backend(agent_self, agent_cfg):
                b = FakeBackend(prefix_s=0.45, step_s=0.018, use_payload=agent_self._fl_model_inputs)
                backends.append(b)
                return b

            def fake_apply(head, options, strict_sources=True):
                applied.append(tuple(options))
                return test.fake_handle()
            self.official.UniDriveVLAB2DAgent.setup = lambda s, p: test.fake_official_setup(s, p, hero)
            la.UniDriveFlowBackend = fake_backend
            FP.apply_fast_prefix = fake_apply
            try:
                if kind == 'v4':
                    cls = AG.build_agent_class(world_fn=lambda: w)
                else:
                    cls = AE.build_agent_class('v2' if kind == 'v2fp' else 'v3')
                agent = cls.__new__(cls)
                agent.setup('unused')
                for k in range(ticks):
                    agent.run_step(self.input_data(rng, k + 1), (k + 1) * DT)
                    w.step(DT)
                agent.destroy()
            finally:
                self.official.UniDriveVLAB2DAgent.setup = official_setup
                la.UniDriveFlowBackend, FP.apply_fast_prefix = real_backend, real_apply
                for k, v in old_env.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
            out = Path(tmp) / 'framelease'

            def stream(name):
                p = out / f'{name}.jsonl'
                return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
            res = {'cls': cls.__name__, 'applied': applied, 'backends': backends,
                   'summary': json.loads((out / 'summary.json').read_text()), 'ticks': stream('ticks'),
                   'jobs': stream('jobs'), 'decisions': stream('decisions'), 'events': stream('events'),
                   'files': sorted(p.name for p in out.iterdir()),
                   'fp_manifest': json.loads((out / AE.MANIFEST_NAME).read_text())}
            if (out / AL.FILE_NAME).exists():
                res['actor_log'] = AL.read_actor_log(out)
                res['actor_manifest'] = json.loads((out / AL.MANIFEST_NAME).read_text())
        return res

    # ------------------------------------------------------------------ tests
    def test_every_arm_runs_on_the_one_agent_class(self):
        arms = [a for a in AV.TABLE_I_ORDER if not AV.ARMS[a].requires_utility]
        for arm in arms:
            r = self.run_agent('v4', arm)
            self.assertEqual(r['cls'], 'FrameLeaseV4Agent', arm)
            self.assertEqual(r['applied'], [self.FP.OPTIONS], arm)            # fast prefix applied once
            self.assertEqual(r['backends'][0].warmups, 1, arm)
            s = r['summary']
            self.assertEqual(s['v4']['runtime_class'], 'V4Runtime', arm)
            self.assertEqual(s['v4']['policy_kind'], 'shield' if AV.ARMS[arm].kind in ('shield', 'age') else 'v2_rule')
            self.assertTrue(s['fast_prefix']['validated'] and s['fast_prefix']['validation_ok'], arm)
            self.assertEqual(s['actor_log']['ticks_logged'], 70, arm)
            self.assertEqual(s['actor_log']['errors'], 0, arm)
            self.assertEqual(r['fp_manifest']['stage'], 'final', arm)
            log = r['actor_log']
            self.assertEqual(log.n_ticks, 70, arm)
            self.assertEqual(sorted(log.catalog), [7, 8], arm)
            self.assertTrue(np.isfinite(log.lidar_pose_estimate()).all(), arm)   # the agent's own lidar2global
            self.assertEqual([int(x) for x in log.step[:3]], [0, 1, 2], arm)
            self.assertGreater(len(r['jobs']), 1, arm)
            self.assertTrue(r['decisions'], arm)
            self.assertIn('agent_config.json', r['files'])
            prefix = {round(j['prefix']['cost_s'], 6) for j in r['jobs']}
            self.assertEqual(prefix, {0.45}, arm)                             # charged = measured (kappa 1)

    def test_fixed_deep_reproduces_the_fast_prefix_v2_agent(self):
        ref = self.run_agent('v2fp')
        new = self.run_agent('v4', 'fixed_deep')
        self.assertEqual(ref['cls'], 'FrameLeaseFastPrefixV2Agent')
        self.assertEqual([job_projection(j) for j in ref['jobs']], [job_projection(j) for j in new['jobs']])
        drop = ('v3',)
        self.assertEqual([scrub({k: v for k, v in t.items() if k not in drop}) for t in ref['ticks']],
                         [scrub({k: v for k, v in t.items() if k not in drop}) for t in new['ticks']])
        self.assertEqual(ref['backends'][0].calls, new['backends'][0].calls)
        for key in ('jobs', 'commits', 'ticks', 'fallback_tick_ratio', 'action_age_s', 'gpu_busy_ratio'):
            self.assertEqual(ref['summary'][key], new['summary'][key], key)

    def test_fl_heuristic_reproduces_the_fast_prefix_v3_agent(self):
        ref = self.run_agent('v3fp')
        new = self.run_agent('v4', 'fl_heuristic')
        self.assertEqual(ref['cls'], 'FrameLeaseFastPrefixV3Agent')
        self.assertEqual([job_projection(j) for j in ref['jobs']], [job_projection(j) for j in new['jobs']])
        self.assertEqual(scrub(ref['ticks']), scrub(new['ticks']))
        self.assertEqual(scrub(ref['decisions']), scrub(new['decisions']))
        self.assertEqual(ref['summary']['v3']['p_both'], new['summary']['v3']['p_both'])

    def test_actor_log_is_evaluation_only(self):
        for arm in ('event_triggered', 'age_only'):
            on = self.run_agent('v4', arm)
            off = self.run_agent('v4', arm, actor_log={'enabled': False})
            self.assertNotIn(AL.FILE_NAME, off['files'])
            for key in ('ticks', 'jobs', 'decisions'):
                self.assertEqual(scrub(on[key]), scrub(off[key]), (arm, key))
            self.assertEqual(scrub({k: v for k, v in on['summary'].items() if k != 'actor_log'}),
                             scrub({k: v for k, v in off['summary'].items() if k != 'actor_log'}))

    def test_behaviour_arm_with_a_registered_utility(self):
        r = self.run_agent('v4', 'fl_behaviour', policy_params={'utility': 'v4_eps0.300_seed11'},
                           unregister=('v4_eps0.300_seed11',))
        self.assertEqual(r['summary']['v4']['policy_kind'], 'shield')
        both = [d for d in r['decisions'] if d['p_both']]
        self.assertTrue(both)
        self.assertTrue(all(d['reason'] == 'both_feasible:v4_eps0.300_seed11' for d in both))
        self.assertTrue(all(d['features'].get('v4_mu') in (0.15, 0.85) for d in both))
        self.assertTrue(all(d['action'] in d['feasible'] or not d['admitted'] for d in r['decisions']))

    def test_depth_limited_heuristic_in_the_agent(self):
        """a_det^d (v4_adet_d<d>) is registered by the agent's own setup for the age and shield arms, and at every
        both-feasible decision it refines iff depth < d (Eq. 8 consults it only when |A_feas| = 2)."""
        from framelease_v3.runtime import v3_shield as VS
        seen = {}
        for arm, d in (('age_only', 4), ('fl_heuristic', 4), ('fl_heuristic', 1)):
            name = f'v4_adet_d{d}'
            r = self.run_agent('v4', arm, policy_params={'utility': name}, unregister=(name,))
            self.assertIn(name, VS.UTILITIES, arm)
            self.assertEqual(r['summary']['v4']['policy_kind'], 'shield', arm)
            both = [x for x in r['decisions'] if x['p_both']]
            for x in both:
                self.assertEqual(x['reason'], f'both_feasible:{name}', arm)
                self.assertEqual(x['action'], 'REFINE' if x['depth'] < d else 'REFRESH', (arm, d, x['depth']))
            self.assertTrue(all(x['depth'] <= 10 for x in r['decisions']), arm)
            seen[(arm, d)] = len(both)
        self.assertTrue(any(seen.values()), seen)                       # some both-feasible decisions were made


class LauncherV4Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('CHECKPOINT') or not Path(os.environ['CHECKPOINT']).is_file():
            raise unittest.SkipTest('CHECKPOINT not set (source linux/env.sh)')
        from framelease_v2 import run_closed_loop as R2
        from framelease_v3.runtime import run_closed_loop_v3 as L
        from framelease_v4.arms import run_closed_loop_v4 as RL
        cls.R2, cls.L, cls.RL = R2, L, RL

    def prep(self, argv):
        with contextlib.redirect_stderr(io.StringIO()):
            args = self.RL.parse_args(argv)
            return args, self.RL.prepare(args)

    def test_v2_rule_arms_equal_the_v3_baseline_configurations(self):
        for arm in ('fixed_deep', 'fast_only', 'fl_original'):
            with tempfile.TemporaryDirectory() as tmp:
                _, prep = self.prep(['--arm', arm, '--route-id', '2086', '--port', '3300', '--output-dir', tmp])
                v3_arm = AV.ARMS[arm].v3_arm
                with contextlib.redirect_stderr(io.StringIO()):
                    ref = self.R2.agent_config(self.R2.parse_args(self.L.v2_argv(self.L.parse_args(
                        ['--arm', v3_arm, '--route-id', '2086', '--port', '3300', '--output-dir', tmp]))))
                self.assertEqual(prep['cfg']['agent'], ref, arm)

    def test_fl_heuristic_equals_v3_configs(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, prep = self.prep(['--arm', 'fl_heuristic', '--route-id', '2086', '--output-dir', tmp])
            with contextlib.redirect_stderr(io.StringIO()):
                ref, _, _ = self.L.v3_configs(self.L.parse_args(['--arm', 'fl_v3_heuristic', '--route-id', '2086',
                                                                 '--output-dir', tmp]))
            self.assertEqual(prep['cfg']['agent'], ref['agent'])
            self.assertEqual(prep['cfg']['v3'], ref['v3'])

    def test_new_arms_share_every_other_agent_setting(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, ref = self.prep(['--arm', 'fixed_deep', '--route-id', '2086', '--output-dir', tmp])
            for arm in ('age_only', 'event_triggered', 'fl_heuristic'):
                _, prep = self.prep(['--arm', arm, '--route-id', '2086', '--output-dir', tmp])
                a, b = dict(ref['cfg']['agent']), dict(prep['cfg']['agent'])
                for k in ('mode', 'policy_params', 'runtime', 'lease_params_path'):
                    a.pop(k)
                    b.pop(k)
                self.assertEqual(a, b, arm)
                self.assertEqual(prep['cfg']['agent']['runtime']['kappa'], 1.0)
                self.assertEqual(prep['cfg']['actor_log'], AL.normalize_params())
                self.assertEqual(prep['fp']['options'], ['sdpa', 'gpu_preproc', 'lora_merged'])

    def test_command_environment_and_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, prep = self.prep(['--arm', 'event_triggered', '--route-id', '2086', '--port', '3305',
                                    '--output-dir', tmp])
            run_dir = Path(tmp) / 'runs' / 'X'
            cmd = self.RL.evaluator_command(prep, run_dir, Path('/ckpt'))
            ref = self.R2.evaluator_command(prep['ns'], run_dir, Path('/ckpt'))
            i = cmd.index('--agent')
            self.assertEqual(cmd[i + 1], str(run_dir / 'raw' / 'framelease_v4_arms_agent_entry.py'))
            self.assertEqual(cmd[:i + 1] + cmd[i + 2:], ref[:i + 1] + ref[i + 2:])
            old = os.environ.get('FRAMELEASE_V3_RUNTIME_CONFIG')
            os.environ['FRAMELEASE_V3_RUNTIME_CONFIG'] = '/x'
            try:
                env, over = self.RL.evaluator_env(prep, run_dir)
            finally:
                if old is None:
                    os.environ.pop('FRAMELEASE_V3_RUNTIME_CONFIG', None)
                else:
                    os.environ['FRAMELEASE_V3_RUNTIME_CONFIG'] = old
            ref_env, ref_over = self.R2.evaluator_env(prep['ns'], run_dir)
            self.assertEqual(over.pop('FRAMELEASE_V4_ARMS_CONFIG'), str(run_dir / 'raw' / 'agent_runtime_config.json'))
            ref_over.pop(la.ENV_RUNTIME_CONFIG)
            self.assertEqual(over, ref_over)
            for k in ('FRAMELEASE_V2_RUNTIME_CONFIG', 'FRAMELEASE_V3_RUNTIME_CONFIG', 'FRAMELEASE_FASTPREFIX_CONFIG'):
                self.assertNotIn(k, env)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(self.RL.main(['--arm', 'age_only', '--route-id', '2086', '--output-dir', tmp,
                                               '--policy-params', '{"age_lease_s": 1.25}', '--dry-run']), 0)
            out = json.loads(buf.getvalue())
            self.assertEqual(out['agent_runtime_config']['agent']['policy_params'], {'age_lease_s': 1.25})
            self.assertEqual(list(Path(tmp).iterdir()), [])                     # a dry run writes nothing

    def test_depth_limited_heuristic_dry_run(self):
        """The launcher process (a fresh interpreter, exactly as a gpu_queue job line) registers v4_adet_d<d> for
        age_only and fl_heuristic, builds the policy and records the utility block and the pins' sources."""
        import subprocess
        py = str(ROOT / '.conda-unidrive-linux/bin/python')
        for arm in ('age_only', 'fl_heuristic'):
            with tempfile.TemporaryDirectory() as tmp:
                cmd = [py, '-B', 'framelease_v4/arms/run_closed_loop_v4.py', '--arm', arm, '--route-id', '2086',
                       '--fast-prefix', 'sdpa,gpu_preproc,lora_merged', '--port', '2600', '--output-dir', tmp,
                       '--policy-params', '{"utility": "v4_adet_d4"}', '--timeout-s', '1410', '--lock-wait-s', '600',
                       '--dry-run']
                p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=600,
                                   env=dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1'))
                self.assertEqual(p.returncode, 0, p.stderr[-1500:])
                out = json.loads(p.stdout)
                cfg = out['agent_runtime_config']
                self.assertEqual(cfg['utility']['name'], 'v4_adet_d4', arm)
                self.assertEqual(cfg['agent']['policy_params']['utility'], 'v4_adet_d4', arm)
                self.assertEqual(cfg['agent']['runtime']['max_depth'], 10, arm)
                self.assertEqual(list(Path(tmp).iterdir()), [], arm)            # a dry run writes nothing

    def test_invalid_configurations(self):
        bad = [['--arm', 'fl_full', '--route-id', '2086'],
               ['--arm', 'fl_full', '--route-id', '2086', '--policy-params', '{"utility": "heuristic"}'],
               ['--arm', 'fl_heuristic', '--route-id', '2086', '--policy-params', '{"utility": "v4_eps0.1_seed1"}'],
               ['--arm', 'fixed_deep', '--route-id', '2086', '--envelope', '/tmp/x.json'],
               ['--arm', 'age_only', '--route-id', '2086', '--envelope', '/tmp/x.json'],
               ['--arm', 'event_triggered', '--route-id', '2086', '--policy-params', '{"foo": 1}'],
               ['--arm', 'age_only', '--route-id', '2086', '--policy-params', '{"age_lease_s": -1}'],
               ['--arm', 'fast_only', '--route-id', '999999'],
               ['--arm', 'fast_only', '--route-id', '2086', '--kappa', '1.5', '--runtime-params', '{"kappa": 1.0}'],
               ['--arm', 'fast_only', '--route-id', '2086', '--actor-log', '{"radius_m": -1}'],
               ['--arm', 'fl_heuristic', '--route-id', '2086', '--policy-params', '{"max_depth": 4}'],
               ['--arm', 'age_only', '--route-id', '2086', '--runtime-params', '{"max_depth": 4}'],
               ['--arm', 'age_only', '--route-id', '2086', '--policy-params', '{"utility": "v4_eps0.300_seed1"}'],
               ['--arm', 'fl_full', '--route-id', '2086', '--policy-params', '{"utility": "v4_adet_d4"}'],
               ['--arm', 'fl_behaviour', '--route-id', '2086'],
               ['--arm', 'fl_behaviour', '--route-id', '2086', '--policy-params', '{"utility": "v4_adet_d4"}']]
        for argv in bad:
            with self.assertRaises((SystemExit, ValueError), msg=argv), contextlib.redirect_stderr(io.StringIO()):
                self.prep(argv + ['--output-dir', '/tmp/unused_v4_arms'])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.RL.parse_args(['--arm', 'fast_only', '--route-id', '2086', '--fast-prefix', 'flash'])


class DryRunJobsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('CHECKPOINT') or not Path(os.environ['CHECKPOINT']).is_file():
            raise unittest.SkipTest('CHECKPOINT not set (source linux/env.sh)')
        from framelease_v4.arms import jobs_v4 as J
        cls.J = J

    def test_two_routes_by_seven_arms(self):
        J = self.J
        rts = J.routes()
        self.assertEqual([r['route_id'] for r in rts], ['2086', '18305'])
        ready, pending, pins = J.build(rts)
        self.assertEqual((len(ready), len(pending)), (12, 2))
        self.assertTrue(all(j['arm_name'] == 'fl_full' and j['blocked'] for j in pending))
        self.assertEqual({j['arm_name'] for j in ready + pending}, set(AV.TABLE_I_ORDER))
        for r in rts:
            self.assertEqual(len([j for j in ready + pending if j['route_id'] == r['route_id']]), 7)
        self.assertTrue(all('framelease_v4/arms/agent_v4.py' in j['require_sha256'] for j in ready))
        results, problems = J.check_all(ready, pending, subprocess_dry_run=True)
        self.assertEqual(problems, [])
        self.assertTrue(all('blocked_as_expected' in r for r in results if 'fl_full' in r['id']))
        self.assertTrue(all(r['dry_run']['status'] == 'NOT_STARTED' for r in results if 'fl_full' not in r['id']))


if __name__ == '__main__':
    unittest.main()
