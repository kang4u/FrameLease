"""Agent-process tests of the Q-network arm fl_full with exported networks (GAP_AUDIT Sec. 3.3 P3-3; PROTOCOL Secs. 4.1,
5.6-5.8, 6.4). CPU only: fake model backend, fake CARLA world; no GPU, no CARLA server, nothing written outside a
temporary directory.

  cd /home/kang/Desktop/DAC && source linux/env.sh && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 nice -n 19 \
      .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/protocol/tests/test_fl_full_qnet_agent.py

Networks: the three exported dev networks of outputs/framelease_v4/rl_dev/smoke_20261110 (qnet_fqi.json and
qnet_bandit.json with 16 inputs, qnet_fqi_nolease.json with the 10 non-lease inputs; all a_det^10 with only the REFINE
head supported, so they never deviate), plus three networks exported here with trainers.export_qnet, all a_det^4: two
with both heads supported that deviate in part of the state space (16 and 10 inputs) and one with only the REFINE head
supported (16 inputs), so that the deviation path and a d* other than 10 run in the agent too.

What is shown:
  (iii) every network loads through the pinned registration path (behaviour.register_utility_name ->
        v3_shield.UTILITIES -> qnet.QUtility.from_environment) with its own feature layout; the online Q values of the
        16- and of the 10-input networks equal an independent re-computation (features.vector + numpy,
        check_smoke_ext.IndependentQ); the 10-input network does not read the lease-derived features;
  (i)   the v4 launcher's --dry-run (a fresh interpreter running the job-line command) accepts fl_full with each dev
        network at each exported envelope E5 / E10 / B0 and records the network: utility block (name, the default
        registrar, FRAMELEASE_V4_QNET = the absolute path, the file's sha256), the evaluator environment and the
        envelope sha256; it writes nothing;
  (ii)  the one agent class (agent_v4.FrameLeaseV4Agent: official agent stack, fake model, fake world) runs 300 ticks of
        fl_full with each network, the utility registered by the agent's own setup (as in the evaluator's fresh
        process): every admitted action lies in A_feas and an action is admitted iff A_feas is not empty; every
        choice epoch (|A_feas| = 2) has reason 'both_feasible:<name>' and logs v4_q_refine, v4_q_refresh, v4_qnet_s,
        v4_bypass; every action follows the network rule (check_smoke_ext.qnet_rows_check: bypass state machine, head
        support, margin, independent Q re-computation); every bypassed or non-deviating choice is a_det^{d*} with
        d* the network's a_det depth; the policy's utility object is that network (name, depth, inputs, call and
        bypass counts equal to the logged rows); every accepted commit passed Eq. 9 (margin > delta); the 16- and
        the 10-input feature specs both run in the agent; the refine-only a_det^4 network acts exactly as a_det^4;
        and fl_full with a non-deviating dev network reproduces fl_heuristic decision by decision and job by job.
The launcher test needs CHECKPOINT (linux/env.sh) and the CARLA server script (file checks only). The agent test needs
the official agent stack; -I ignores PYTHONPATH, so the linux/env.sh import paths are added here. Each is skipped
when its prerequisites are missing.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ARMS_TESTS = ROOT / 'framelease_v4' / 'arms' / 'tests'
if str(ARMS_TESTS) not in sys.path:
    sys.path.append(str(ARMS_TESTS))                    # helpers_v4 and the v4 agent test harness (read-only import)
os.environ['CUDA_VISIBLE_DEVICES'] = ''
sys.dont_write_bytecode = True

import numpy as np  # noqa: E402

from helpers_v4 import DT, FakeBackend, dets_with  # noqa: E402

from framelease_v3.runtime import v3_shield as VS  # noqa: E402
from framelease_v4.arms import arms_v4 as AV  # noqa: E402
from framelease_v4.protocol import check_smoke_ext as X  # noqa: E402
from framelease_v4.rl import behaviour as B  # noqa: E402
from framelease_v4.rl import features as F  # noqa: E402
from framelease_v4.rl import qnet as Q  # noqa: E402
from framelease_v4.rl import trainers as TR  # noqa: E402

PY = str(ROOT / '.conda-unidrive-linux/bin/python')
LAUNCHER = 'framelease_v4/arms/run_closed_loop_v4.py'
DEV_DIR = ROOT / 'outputs/framelease_v4/rl_dev/smoke_20261110'
DEV_NETS = {'fqi': (DEV_DIR / 'qnet_fqi.json', 16), 'bandit': (DEV_DIR / 'qnet_bandit.json', 16),
            'fqi_nolease': (DEV_DIR / 'qnet_fqi_nolease.json', 10)}
ENVELOPES = {k: ROOT / f'outputs/framelease_v4/envelopes/{k}.json' for k in ('E5', 'E10', 'B0')}
ROUTE = '18305'                                         # the P1-0 smoke route (training, outside T22)
TICKS = 300
D_SYNTH = 4


def sha256(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def official_stack_paths():
    """The PYTHONPATH entries of linux/env.sh (python -I ignores PYTHONPATH)."""
    work = ROOT / 'third_party/UniDriveVLA-linux/Bench2Drive'
    bench = ROOT / 'third_party/bench2drive-linux'
    carla = Path(os.environ.get('CARLA_ROOT') or '/home/kang/opt/CARLA_0.9.15')
    return [work, bench, bench / 'leaderboard', bench / 'scenario_runner', carla / 'PythonAPI',
            carla / 'PythonAPI' / 'carla']


def synthetic_spec(family, d_det=D_SYNTH, supported=(True, True)):
    """An exported network (trainers.export_qnet) with Q_REFRESH - Q_REFINE = obs_age_s - 0.6 [- 0.1 lease_slack_s with
    16 inputs]: with both heads supported it deviates from a_det^d in part of the state space; with the REFRESH head
    unsupported (as the dev networks) it always acts as a_det^d."""
    cols = list(TR.Candidate(family).columns)
    n = len(cols)
    W1 = np.zeros((n, 2))
    W1[cols.index(F.NAMES.index('obs_age_s')), 0] = 1.0                    # obs age in [0, 3]: ReLU is the identity
    b1 = np.array([0.0, 3.0])
    if F.NAMES.index('lease_slack_s') in cols:
        W1[cols.index(F.NAMES.index('lease_slack_s')), 1] = 1.0           # lease slack + 3 in [0, 6]
    W2 = np.array([[0.0, 1.0], [0.0, -0.1]])
    b2 = np.array([0.0, -0.6 + 0.3])
    cand = TR.Candidate(family, d_det=d_det)
    return json.loads(json.dumps(TR.export_qnet({'W': [W1, W2], 'b': [b1, b2]}, cand, list(supported),
                                                provenance={'test': 'synthetic network'})))


def feature_rows(rng, n=200):
    """Logged-like 32-feature dicts: numbers inside and outside the clip ranges, None, NaN and strings."""
    from framelease_v3.runtime.v3_scheduler import FEATURE_NAMES
    rows = []
    for _ in range(n):
        f = {k: float(rng.normal(0.5, 2.0)) for k in FEATURE_NAMES}
        f['depth'] = int(rng.integers(1, 11))
        f['newer_frames'] = int(rng.integers(0, 80))
        f['n_relevant'] = int(rng.integers(0, 60))
        for k in rng.choice(FEATURE_NAMES, size=4, replace=False):
            f[str(k)] = [None, float('nan'), 'x', 1e9][int(rng.integers(0, 4))]
        rows.append(f)
    return rows


class _Env:
    """Set / remove environment variables, restoring them afterwards."""

    def __init__(self, **values):
        self.values = values
        self.saved = {}

    def __enter__(self):
        for k, v in self.values.items():
            self.saved[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = str(v)
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _drop_v4_utilities():
    for k in [k for k in VS.UTILITIES if k.startswith('v4_')]:
        del VS.UTILITIES[k]


# ============================================================================================ (iii) feature layouts

class NetworkLayoutTest(unittest.TestCase):
    """The pinned loading path and the 16- / 10-input feature layouts (no official stack needed)."""

    def tearDown(self):
        _drop_v4_utilities()
        os.environ.pop(Q.ENV_QNET, None)

    def nets(self):
        out = {k: (Q.load_spec(p), n) for k, (p, n) in DEV_NETS.items()}
        out['synth16'] = (synthetic_spec('fqi'), 16)
        out['synth10'] = (synthetic_spec('fqi_nolease'), 10)
        return out

    def test_dev_networks_are_the_expected_exports(self):
        for fam, (path, n) in DEV_NETS.items():
            spec = Q.load_spec(path)
            self.assertEqual(X.spec_problems(spec), [], fam)
            self.assertEqual(X.network_family(spec), fam)
            self.assertEqual(len(spec['feature_columns']), n, fam)
            self.assertEqual(spec['a_det'], {'rule': 'refine_below_depth', 'depth': 10}, fam)
            self.assertEqual(spec['supported'], [True, False], fam)           # smoke data: REFRESH never logged
            self.assertEqual(spec['policy_budget_s'], X.POLICY_BUDGET_S, fam)

    def test_registered_name_loads_each_layout(self):
        for key, (spec, n) in self.nets().items():
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'q.json'
                path.write_text(json.dumps(spec))
                with _Env(**{Q.ENV_QNET: path}):
                    _drop_v4_utilities()
                    self.assertTrue(B.register_utility_name(spec['name']), key)
                    self.assertEqual(AV.utility_kind(spec['name']), 'qnet', key)
                    u = VS.make_utility(spec['name'])
                self.assertIsInstance(u, Q.QUtility, key)
                self.assertEqual((u.name, u.net.n_in, u.d_det), (spec['name'], n, spec['a_det']['depth']), key)
                self.assertEqual([s[0] for s in u.net.vec.spec], [d['name'] for d in spec['feature_spec']], key)
                self.assertEqual([d['index'] for d in spec['feature_spec']],
                                 list(F.ALL_COLUMNS if n == 16 else F.NO_LEASE_COLUMNS), key)

    def test_online_q_equals_an_independent_recomputation(self):
        rng = np.random.default_rng(20261111)
        rows = feature_rows(rng)
        for key, (spec, n) in self.nets().items():
            net, ref = Q.QNetwork(spec), X.IndependentQ(spec)
            for f in rows:
                q = net.q_from_features(f)
                r0, r1 = ref.q(f)
                self.assertTrue(math.isfinite(q[0]) and math.isfinite(q[1]), key)
                self.assertAlmostEqual(float(q[0]), r0, delta=1e-9 * max(1.0, abs(r0)), msg=key)
                self.assertAlmostEqual(float(q[1]), r1, delta=1e-9 * max(1.0, abs(r1)), msg=key)

    def test_ten_input_network_ignores_the_lease_features(self):
        rng = np.random.default_rng(7)
        nets = self.nets()
        for key in ('fqi_nolease', 'synth10', 'synth16'):
            spec, n = nets[key]
            net = Q.QNetwork(spec)
            changed = 0
            for f in feature_rows(rng, 50):
                base = tuple(float(x) for x in net.q_from_features(f))
                g = dict(f, **{k: float(rng.uniform(-3, 3)) for k in F.LEASE_DERIVED})
                after = tuple(float(x) for x in net.q_from_features(g))
                if n == 10:
                    self.assertEqual(base, after, key)
                changed += int(base != after)
            if n == 16:
                self.assertGreater(changed, 0, key)                         # the 16-input network reads them

    def test_synthetic_networks_deviate_both_ways(self):
        for family in ('fqi', 'fqi_nolease'):
            u = Q.QUtility(synthetic_spec(family), budget_s=1e6)
            sr = VS.shield(10.0, 12.5, 12.5, 2, 10, True, VS.ShieldBounds(0.001, 0.02, 0.47, 0.001, 0.05))
            young = {'obs_age_s': 0.1, 'depth': 2, 'lease_slack_s': 0.0}
            old = {'obs_age_s': 2.0, 'depth': 2, 'lease_slack_s': 0.0}
            self.assertEqual(VS.decide(sr, u, dict(young))[0], VS.REFINE, family)   # a_det^4 at depth 2
            self.assertEqual(VS.decide(sr, u, dict(old))[0], VS.REFRESH, family)    # deviation to REFRESH
            sr6 = VS.shield(10.0, 12.5, 12.5, 6, 10, True, VS.ShieldBounds(0.001, 0.02, 0.47, 0.001, 0.05))
            self.assertEqual(VS.decide(sr6, u, dict(young, depth=6))[0], VS.REFINE, family)  # deviation to REFINE
            self.assertEqual(VS.decide(sr6, u, dict(old, depth=6))[0], VS.REFRESH, family)   # a_det^4 at depth 6


# ============================================================================================ (i) launcher dry runs

class LauncherDryRunTest(unittest.TestCase):
    """The job-line command with --dry-run in a fresh interpreter (as gpu_queue runs it, with -I -B)."""

    @classmethod
    def setUpClass(cls):
        ckpt = os.environ.get('CHECKPOINT')
        carla = Path(os.environ.get('CARLA_ROOT') or '/home/kang/opt/CARLA_0.9.15')
        if not ckpt or not Path(ckpt).is_file() or not (carla / 'CarlaUE4.sh').is_file():
            raise unittest.SkipTest('CHECKPOINT / CARLA_ROOT not set (source linux/env.sh)')

    def dry_run(self, net, name, envelope, out_dir, extra=()):
        cmd = [PY, '-I', '-B', LAUNCHER, '--arm', 'fl_full', '--fast-prefix', 'sdpa,gpu_preproc,lora_merged',
               '--kappa', '1.0', '--seed', '11', '--route-id', ROUTE, '--port', '2600', '--output-dir', str(out_dir),
               '--envelope', str(envelope), '--policy-params', json.dumps({'utility': name}),
               '--utility-env', f'{Q.ENV_QNET}={net}', '--timeout-s', '1410', '--lock-wait-s', '600', '--dry-run',
               *extra]
        env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1')
        env.pop(Q.ENV_QNET, None)
        return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=600, env=env)

    def test_fl_full_dry_run_records_each_network(self):
        for fam, (path, n) in DEV_NETS.items():
            spec = Q.load_spec(path)
            file_sha = sha256(path)
            for label, env_path in ENVELOPES.items():
                with tempfile.TemporaryDirectory() as tmp:
                    p = self.dry_run(path, spec['name'], env_path, Path(tmp) / 'out')
                    self.assertEqual(p.returncode, 0, (fam, label, p.stderr[-1500:]))
                    out = json.loads(p.stdout)
                    cfg = out['agent_runtime_config']
                    self.assertEqual((out['status'], out['v4_arm'], out['kind']), ('NOT_STARTED', 'fl_full', 'shield'))
                    u = cfg['utility']
                    self.assertEqual(u['name'], spec['name'], fam)
                    self.assertEqual(u['registrar'], AV.DEFAULT_UTILITY_REGISTRAR, fam)
                    self.assertEqual(u['env'], {Q.ENV_QNET: str(path)}, fam)
                    self.assertEqual(u['env_files_sha256'], {str(path): file_sha}, fam)   # the network's sha256
                    self.assertEqual(cfg['agent']['policy_params'], {'utility': spec['name']}, fam)
                    self.assertEqual(cfg['v3']['policy_params'], {'utility': spec['name']}, fam)
                    self.assertEqual(cfg['agent']['runtime']['max_depth'], 10, fam)
                    self.assertEqual(cfg['v3']['envelope_sha256'], sha256(env_path), (fam, label))
                    self.assertEqual(out['environment_overrides'][Q.ENV_QNET], str(path), fam)
                    self.assertTrue(out['command'][out['command'].index('--agent') + 1]
                                    .endswith('framelease_v4_arms_agent_entry.py'))
                    self.assertEqual(list(Path(tmp).iterdir()), [], (fam, label))   # a dry run writes nothing

    def test_dry_run_refuses_a_mismatched_network(self):
        """The name pins the weights: another network file behind the configured name is refused in the launcher."""
        fqi = Q.load_spec(DEV_NETS['fqi'][0])
        with tempfile.TemporaryDirectory() as tmp:
            p = self.dry_run(DEV_NETS['bandit'][0], fqi['name'], ENVELOPES['E5'], Path(tmp) / 'out')
            self.assertNotEqual(p.returncode, 0)
            self.assertIn(fqi['name'], p.stderr)
            self.assertEqual(list(Path(tmp).iterdir()), [])


# ============================================================================================ (ii) agent process

class FlFullAgentTest(unittest.TestCase):
    """fl_full on the one v4 agent class (FrameLeaseV4Agent) with each network (official stack, fake model)."""

    @classmethod
    def setUpClass(cls):
        added = [str(p) for p in official_stack_paths() if p.is_dir() and str(p) not in sys.path]
        i = sys.path.index(str(ROOT)) + 1 if str(ROOT) in sys.path else 0
        sys.path[i:i] = added                                # the linux/env.sh order, ahead of site-packages
        cls._added_paths = added
        cls._env = _Env(IS_BENCH2DRIVE='1', IS_VISUALIZE='0', PLANNER_TYPE='traj')
        cls._env.__enter__()
        try:
            import test_agent_launcher_v4 as TAL                 # the v4 agent harness (setUpClass skips without stack)
            cls.TAL = TAL
            TAL.AgentV4Test.setUpClass.__func__(cls)
        except BaseException:
            cls.tearDownClass()
            raise
        cls.tmp = tempfile.TemporaryDirectory()
        cls.synth = {}
        for key, family, n, sup in (('synth_fqi', 'fqi', 16, (True, True)),
                                    ('synth_fqi_nolease', 'fqi_nolease', 10, (True, True)),
                                    ('synth_d4_refine_only', 'fqi', 16, (True, False))):
            spec = synthetic_spec(family, supported=sup)
            path = Path(cls.tmp.name) / f'{key}.json'
            path.write_text(json.dumps(spec))
            cls.synth[key] = (path, n)
        cls.results = {}

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, 'tmp', None) is not None:
            cls.tmp.cleanup()
        cls._env.__exit__(None, None, None)
        for p in getattr(cls, '_added_paths', []):
            if p in sys.path:
                sys.path.remove(p)
        _drop_v4_utilities()

    # the official-agent fakes of framelease_v4/arms/tests/test_agent_launcher_v4.AgentV4Test, reused unchanged
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

    @staticmethod
    def dets(obs):
        """Detections that make the lease vary: none (lease H_bar), a stopped car in the ego path (short lease,
        forced and empty feasible sets) and a car closing in on the next lane."""
        phase = obs.obs_id % 90
        if phase < 30:
            return dets_with(obs, np.zeros((0, 7)))
        if phase < 50:
            return dets_with(obs, [[0.0, 9.0, 4.4, 1.9, math.pi / 2, 0.0, 0.0]])
        return dets_with(obs, [[3.2, 16.0 - 0.2 * (phase - 50), 4.4, 1.9, math.pi / 2, 0.0, -2.0]])

    def run_agent(self, arm, utility=None, qnet_path=None, envelope=ENVELOPES['E5'], ticks=TICKS):
        """One run of the v4 agent (fl_full: fresh-process conditions, i.e. the utility is not registered and
        FRAMELEASE_V4_QNET comes from the evaluator environment that run_closed_loop_v4.evaluator_env builds)."""
        from framelease_v2 import latency_agent as la
        from framelease_v4.arms import agent_v4 as AG
        AE, FP = self.AE, self.FP
        rng = np.random.default_rng(5)
        w, hero = self.world()
        backends, applied, holder = [], [], {}
        with tempfile.TemporaryDirectory() as tmp, _Env(**{Q.ENV_QNET: None}):
            cfg, _, env_file = AV.build_config(arm, runtime_params={'overhead_scale': 0.0},
                                               fast_prefix=self.fp_config('v4'),
                                               policy_params={'utility': utility} if utility else {},
                                               envelope=envelope,
                                               utility_env={Q.ENV_QNET: str(qnet_path)} if qnet_path else None)
            if utility and utility.startswith(B.PREFIX):
                VS.UTILITIES.pop(utility, None)              # the evaluator's agent process registers it itself
            cfg_path = Path(tmp) / 'agent_runtime_config.json'
            cfg_path.write_text(json.dumps(cfg))
            official_setup = self.official.UniDriveVLAB2DAgent.setup
            real_backend, real_apply = la.UniDriveFlowBackend, FP.apply_fast_prefix
            test = self

            def fake_backend(agent_self, agent_cfg):
                b = FakeBackend(prefix_s=0.45, step_s=0.018, dets_fn=test.dets,
                                use_payload=agent_self._fl_model_inputs)
                backends.append(b)
                return b

            def fake_apply(head, options, strict_sources=True):
                applied.append(tuple(options))
                return test.fake_handle()
            env = {AG.ENV_V4_CONFIG: cfg_path, 'SAVE_PATH': tmp, AE.ENV_FASTPREFIX_CONFIG: None,
                   Q.ENV_QNET: str(qnet_path) if qnet_path else None}
            with _Env(**env):
                self.official.UniDriveVLAB2DAgent.setup = lambda s, p: test.fake_official_setup(s, p, hero)
                la.UniDriveFlowBackend = fake_backend
                FP.apply_fast_prefix = fake_apply
                try:
                    cls = AG.build_agent_class(world_fn=lambda: w)
                    agent = cls.__new__(cls)
                    agent.setup('unused')
                    holder['policy'] = agent._fl_runtime.policy
                    holder['registered_in_agent'] = utility in VS.UTILITIES if utility else None
                    for k in range(ticks):
                        agent.run_step(self.input_data(rng, k + 1), (k + 1) * DT)
                        w.step(DT)
                    agent.destroy()
                finally:
                    self.official.UniDriveVLAB2DAgent.setup = official_setup
                    la.UniDriveFlowBackend, FP.apply_fast_prefix = real_backend, real_apply
            out = Path(tmp) / 'framelease'

            def stream(s):
                p = out / f'{s}.jsonl'
                return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
            return {'cls': cls.__name__, 'applied': applied, 'backends': backends, 'policy': holder['policy'],
                    'registered_in_agent': holder['registered_in_agent'], 'cfg': cfg, 'envelope': env_file,
                    'summary': json.loads((out / 'summary.json').read_text()),
                    'agent_config': json.loads((out / 'agent_config.json').read_text()),
                    'decisions': stream('decisions'), 'jobs': stream('jobs'), 'ticks': stream('ticks')}

    def result(self, key):
        """The run of network `key` (dev family or synthetic), computed once per class."""
        if key not in self.results:
            path, n = DEV_NETS.get(key) or self.synth[key]
            spec = Q.load_spec(path)
            self.results[key] = (spec, n, self.run_agent('fl_full', spec['name'], path))
        return self.results[key]

    def check_network_run(self, key):
        spec, n, r = self.result(key)
        name, d_star = spec['name'], int(spec['a_det']['depth'])
        rows = r['decisions']
        self.assertEqual(r['cls'], 'FrameLeaseV4Agent', key)
        self.assertEqual(r['applied'], [self.FP.OPTIONS], key)
        self.assertTrue(r['registered_in_agent'], key)
        s = r['summary']
        self.assertEqual((s['v4']['runtime_class'], s['v4']['policy_kind']), ('V4Runtime', 'shield'), key)
        self.assertEqual(s['policy']['utility'], name, key)                       # the agent's policy names it
        self.assertEqual(r['agent_config']['policy']['utility'], name, key)
        self.assertEqual(s['v4']['decisions'], len(rows), key)
        self.assertEqual([x['epoch'] for x in rows], list(range(1, len(rows) + 1)), key)
        self.assertEqual(s['ticks'], TICKS, key)
        # the deployed utility object is the network of the file
        u = r['policy'].utility
        self.assertIsInstance(u, Q.QUtility, key)
        self.assertEqual((u.name, u.d_det, u.net.n_in), (name, d_star, n), key)
        self.assertEqual([x[0] for x in u.net.vec.spec], [d['name'] for d in spec['feature_spec']], key)
        # A_feas: a choice only inside it; admitted iff A_feas is not empty
        choice = [x for x in rows if x['p_both']]
        for x in rows:
            self.assertEqual(x['admitted'], x['action'] in x['feasible'], (key, x['epoch']))
            self.assertEqual(x['admitted'], bool(x['feasible']), (key, x['epoch']))
            self.assertEqual(x['p_both'], len(x['feasible']) == 2, (key, x['epoch']))
        for x in choice:
            self.assertEqual(x['reason'], f'both_feasible:{name}', (key, x['epoch']))
            for k in ('v4_q_refine', 'v4_q_refresh', 'v4_qnet_s', 'v4_bypass'):
                self.assertIn(k, x['features'], (key, x['epoch'], k))
            a_det = B.a_det_action(x['depth'], d_star)
            if x['features']['v4_bypass'] is not None or not all(spec['supported']):
                self.assertEqual(x['action'], a_det, (key, x['epoch']))          # a_det^{d*}: the default action
        # every action follows the network (bypass rule, support, margin, Q re-computed from the logged state)
        problems, vals = X.qnet_rows_check(rows, spec, name)
        self.assertEqual(problems, [], key)
        st = u.stats()
        self.assertEqual(st['network_calls'], vals['network_calls'], key)
        self.assertEqual(st['select_calls'], len(choice), key)
        self.assertEqual(st['not_both_calls'], 0, key)
        self.assertEqual({k: v for k, v in st['bypass'].items()}, vals['bypass'], key)
        self.assertEqual(st['actions'], vals['actions'], key)
        self.assertEqual(st['disabled'], vals['disabled_at_epoch'] is not None, key)
        self.assertGreater(vals['network_calls'], 0, key)                       # the network really ran
        self.assertGreater(len(choice), 20, key)
        self.assertGreater(len(rows) - len(choice), 0, key)                     # forced / empty epochs occur too
        # Eq. 9 unchanged: every accepted commit beat its margin check (delta = 0.2 m; None = +inf, no relevant agent)
        commits = [st_.get('commit') for j in r['jobs'] for st_ in (j.get('steps') or []) if st_.get('commit')]
        accepted = [c for c in commits if c['accepted']]
        self.assertTrue(accepted, key)
        for c in accepted:
            self.assertTrue(c['margin_at_commit_m'] is None or c['margin_at_commit_m'] > 0.2, (key, c))
        self.assertTrue(any(c['margin_at_commit_m'] is not None for c in accepted), key)   # finite margins too
        return spec, vals, choice

    def test_dev_fqi_network_16_inputs(self):
        spec, vals, choice = self.check_network_run('fqi')
        self.assertEqual((vals['n_inputs'], vals['a_det_depth'], vals['deviations']), (16, 10, 0))
        self.assertTrue(all(x['action'] == 'REFINE' for x in choice))           # a_det^10 refines while feasible
        called = [x for x in choice if x['features']['v4_bypass'] is None]
        self.assertTrue(called and all(x['features']['v4_q_refresh'] is None for x in called))   # unsupported head

    def test_dev_bandit_network_16_inputs(self):
        spec, vals, choice = self.check_network_run('bandit')
        self.assertEqual((vals['n_inputs'], vals['a_det_depth'], vals['deviations']), (16, 10, 0))

    def test_dev_fqi_nolease_network_10_inputs(self):
        spec, vals, choice = self.check_network_run('fqi_nolease')
        self.assertEqual((vals['n_inputs'], vals['a_det_depth'], vals['deviations']), (10, 10, 0))

    def test_deviating_network_16_inputs_d4(self):
        spec, vals, choice = self.check_network_run('synth_fqi')
        self.assertEqual((vals['n_inputs'], vals['a_det_depth']), (16, D_SYNTH))
        self.assertGreater(vals['deviations'], 0)
        dev = [x for x in choice if x['action'] != B.a_det_action(x['depth'], D_SYNTH)]
        self.assertTrue(dev and all(x['features']['v4_bypass'] is None for x in dev))   # deviations: network calls only

    def test_refine_only_network_deploys_a_det_d4(self):
        """REFRESH head unsupported (like the dev networks) but a_det^4: the agent's choices are exactly a_det^{d*}
        with d* = 4 (REFINE below depth 4, REFRESH from depth 4 on), so the deployed default is the file's."""
        spec, vals, choice = self.check_network_run('synth_d4_refine_only')
        self.assertEqual((vals['n_inputs'], vals['a_det_depth'], vals['deviations']), (16, D_SYNTH, 0))
        for x in choice:
            self.assertEqual(x['action'], 'REFINE' if x['depth'] < D_SYNTH else 'REFRESH', x['epoch'])
        self.assertTrue(any(x['depth'] >= D_SYNTH for x in choice))
        self.assertTrue(any(x['depth'] < D_SYNTH for x in choice))

    def test_deviating_network_10_inputs_d4(self):
        spec, vals, choice = self.check_network_run('synth_fqi_nolease')
        self.assertEqual((vals['n_inputs'], vals['a_det_depth']), (10, D_SYNTH))
        self.assertGreater(vals['deviations'], 0)

    def test_non_deviating_network_reproduces_fl_heuristic(self):
        """The dev networks support only REFINE (a_det^10), so fl_full with one of them must reproduce fl_heuristic
        ('heuristic' = a_det^10) decision by decision and job by job on the same fakes: the Q-network path adds its
        logging, never a decision (scheduler CPU time is not charged here, overhead_scale 0)."""
        spec, n, r = self.result('fqi_nolease')
        ref = self.run_agent('fl_heuristic', None, None)
        self.assertEqual(ref['summary']['policy']['utility'], 'heuristic')

        def proj(rows):
            return [(x['epoch'], x['sim_s'], x['depth'], tuple(x['feasible']), x['action'], x['admitted'])
                    for x in rows]
        self.assertEqual(proj(ref['decisions']), proj(r['decisions']))
        self.assertEqual([(j['job_id'], j['obs_id'], j['final_depth'], tuple(j['committed_depths']))
                          for j in ref['jobs']],
                         [(j['job_id'], j['obs_id'], j['final_depth'], tuple(j['committed_depths']))
                          for j in r['jobs']])

if __name__ == '__main__':
    unittest.main()
