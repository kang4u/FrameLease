"""CPU tests of the additive arm registry framelease_v4/arms_ext/arms_ext.py (PROTOCOL Secs. 4.1, 7.4, 8.3; GAP_AUDIT
Sec. 2). No GPU, no CARLA, no model; nothing is written outside temporary directories.

  cd /home/kang/Desktop/DAC && source linux/env.sh && export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 && \
      nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/arms_ext/tests

What is shown:
  * additive: the registry is arms_v4.ARMS (the same objects, in the same order) plus fl_global_shield, which equals
    its base arm fl_heuristic in every field the arms_v4 functions read; arms_v4.ARMS and ALL_ARMS are unchanged;
  * delegation: for each of the 8 arms_v4 arms, arms_ext's build_config / agent_config_from / validate_config /
    build_policy return what arms_v4's return (equal configurations, the same policy class and description);
  * fl_global_shield: its configuration is fl_heuristic's for the same arguments (E5 / E10 / B0; utilities heuristic
    and v4_adet_d4) except arm / title / description and the 'extension' block, i.e. the base view is fl_heuristic's
    configuration; build_policy returns GlobalMarginShieldPolicy on fl_heuristic's LeaseEnv with its parameters and
    utility, and the global lease parameters are E* with the constants of PROTOCOL Sec. 2.4;
  * refusals: the agent refuses a changed E* (make_v3_policy's sha256 check through the base arm), a changed
    lease-parameter file and a missing or tampered extension block; the pinned arms_v4 functions refuse the new arm;
    configuration rules: E* required, isotropic quadratic E* only, a_det utilities only, shield depth 10;
  * fixed lease constants (PROTOCOL Secs. 2.4, 7.4): build_config refuses any lease override for fl_global_shield
    (fl_heuristic still accepts them, through arms_v4 and through the extension alike), and the configuration the
    previous version accepted (t_c_s 1.0, H_bar 2.0) or any configuration with lease overrides or another cap is
    refused by validate_config, agent_config_from and build_policy;
  * no pinned module attribute is rebound or mutated: a fresh interpreter that configures, validates and builds every
    arm through the extension (and, with linux/env.sh, dry-runs both launchers in process) changes exactly the
    attributes that the same work through arms_v4 and the pinned launcher alone changes (the v4 utility registration
    and the logged-v2-class cache of policies_v4), and adds none.
"""
from __future__ import annotations

import dataclasses
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers_ext as H

from framelease_v3.runtime import v3_lease as VL
from framelease_v4.arms import arms_v4 as AV
from framelease_v4.arms_ext import arms_ext as X
from framelease_v4.arms_ext import global_shield as GS

GS_ARM = 'fl_global_shield'


def jround(x):
    return json.loads(json.dumps(x))


class _EnvRestore(unittest.TestCase):
    """os.environ is restored after every test (utility environments are applied by build_config)."""

    def setUp(self):
        self._environ = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._environ)


class RegistryTest(_EnvRestore):
    def test_registry_is_additive(self):
        reg = X.register()
        self.assertIs(reg, X.ARMS)
        self.assertEqual(list(X.ARMS), list(AV.ALL_ARMS) + [GS_ARM])
        self.assertEqual(X.ALL_ARMS, tuple(AV.ALL_ARMS) + (GS_ARM,))
        for name in AV.ARMS:
            self.assertIs(X.ARMS[name], AV.ARMS[name], name)
        self.assertNotIn(GS_ARM, AV.ARMS)
        self.assertEqual(tuple(AV.ARMS), AV.ALL_ARMS)
        self.assertEqual(AV.ALL_ARMS, AV.TABLE_I_ORDER + AV.EXTRA_ARMS)
        arm, base = X.ARMS[GS_ARM], AV.ARMS['fl_heuristic']
        for f in X.DELEGATED_FIELDS:
            self.assertEqual(getattr(arm, f), getattr(base, f), f)
        self.assertEqual((arm.kind, arm.policy, arm.utilities, arm.requires_utility, arm.v3_arm),
                         ('shield', 'fl_v3_heuristic', ('heuristic', 'adet'), False, 'fl_v3_heuristic'))
        self.assertEqual(arm.runtime, {'max_age_s': 2.5, 'profile_quantile': 0.99})       # PROTOCOL Sec. 2.4
        self.assertEqual((X.base_arm(GS_ARM), X.base_arm('fixed_deep')), ('fl_heuristic', 'fixed_deep'))
        self.assertTrue(X.is_extension(GS_ARM) and not any(X.is_extension(a) for a in AV.ARMS))
        with self.assertRaises(ValueError):
            X.base_arm('fl_bandit')
        X.register()                                                                     # idempotent
        self.assertEqual(list(X.ARMS), list(AV.ALL_ARMS) + [GS_ARM])

    def test_register_refuses_a_diverging_or_clashing_arm(self):
        arm = X.EXT_ARMS[GS_ARM]
        for f, v in (('runtime', {'max_age_s': 2.0, 'profile_quantile': 0.99}), ('utilities', ('qnet',)),
                     ('kind', 'age'), ('requires_utility', True)):
            with mock.patch.dict(X.EXT_ARMS, {GS_ARM: dataclasses.replace(arm, **{f: v})}):
                with self.assertRaises(ValueError, msg=f):
                    X.register()
        with mock.patch.dict(X.EXT_ARMS, {'fl_heuristic': dataclasses.replace(arm, name='fl_heuristic')}, clear=True):
            with self.assertRaises(ValueError):
                X.register()
        X.register()
        self.assertEqual(list(X.ARMS), list(AV.ALL_ARMS) + [GS_ARM])


class DelegationTest(_EnvRestore):
    def test_arms_v4_arms_are_delegated_unchanged(self):
        for arm, kw in H.arm_kwargs().items():
            if X.is_extension(arm):
                continue
            got, want = X.build_config(arm, **kw), AV.build_config(arm, **kw)
            self.assertEqual(got, want, arm)
            cfg = want[0]
            self.assertEqual(X.agent_config_from(cfg), AV.agent_config_from(cfg), arm)
            px, pv = X.build_policy(jround(cfg)), AV.build_policy(jround(cfg))
            self.assertIs(type(px), type(pv), arm)
            self.assertEqual(px.describe(), pv.describe(), arm)
            vx, vv = X.validate_config(cfg), AV.validate_config(cfg)
            self.assertIs(type(vx), type(vv), arm)
            self.assertEqual(X.base_config(cfg), cfg, arm)
            with self.assertRaises(ValueError):
                X.check_extension(cfg)


class GlobalShieldConfigTest(_EnvRestore):
    def test_configuration_is_fl_heuristic_relabelled(self):
        for label in ('E5', 'E10', 'B0'):
            env_file = H.ENVELOPES[label]
            for pp in ({}, {'utility': 'heuristic'}, {'utility': 'v4_adet_d4'}):
                kw = dict(envelope=str(env_file), policy_params=pp, kappa=1.0, seed=11)
                cfg, lp, ep = X.build_config(GS_ARM, **kw)
                ref, lp2, ep2 = AV.build_config('fl_heuristic', **kw)
                self.assertEqual((lp, ep), (lp2, ep2))
                diff = sorted(k for k in set(cfg) | set(ref) if cfg.get(k) != ref.get(k))
                self.assertEqual(diff, ['arm', 'description', 'extension', 'title'], (label, pp))
                self.assertEqual(X.base_config(cfg), ref, (label, pp))           # the base view IS fl_heuristic's
                self.assertEqual((cfg['arm'], cfg['kind'], cfg['agent']['mode']), (GS_ARM, 'shield', 'fl_v3_heuristic'))
                ext = cfg['extension']
                self.assertEqual((ext['schema'], ext['arm'], ext['base_arm'], ext['lease']),
                                 (X.SCHEMA, GS_ARM, 'fl_heuristic', 'global_margin'))
                gl = ext['global_lease']
                sha = VL.sha256_file(env_file)
                self.assertEqual((gl['envelope_sha256'], cfg['v3']['envelope_sha256']), (sha, sha))
                self.assertEqual((gl['schema'], gl['margin_mode'], gl['h_bar_s'], gl['reserve_m']),
                                 (GS.SCHEMA, 'global', 2.5, 0.2))
                P = gl['lease_params']
                self.assertEqual((P['d_safe_m'], P['reserve_m'], P['horizon_s'], P['dt_s'], P['h_max_s']),
                                 (0.5, 0.2, 3.0, 0.05, 3.0))
                self.assertEqual((P['score_threshold'], P['low_score_floor'], P['low_conf_mode'], P['margin_mode']),
                                 (0.3, 0.1, 'cap', 'global'))
                self.assertEqual(P['relevant_groups'], ['vehicle', 'pedestrian'])
                spec = json.loads(env_file.read_text(encoding='utf-8'))
                for name in ('sigma_m', 'vbar_mps', 'abar_mps2'):
                    for g in ('vehicle', 'pedestrian'):
                        self.assertEqual(P[name][g], float(spec[name][g]), (label, name, g))
                policy = X.build_policy(jround(cfg))
                base = AV.build_policy(jround(ref))
                self.assertIsInstance(policy, GS.GlobalMarginShieldPolicy)
                self.assertEqual(type(base).__name__, 'ShieldedHeuristicPolicy')
                self.assertEqual(policy.params, base.params)
                self.assertEqual(policy.utility.name, base.utility.name)
                self.assertEqual(policy.env.describe(), base.env.describe())
                self.assertEqual(jround(policy.global_lease_spec()), gl)
                self.assertEqual(X.agent_config_from(cfg), AV.agent_config_from(ref))
                self.assertIsInstance(X.validate_config(cfg), GS.GlobalMarginShieldPolicy)
                d = policy.describe()
                self.assertEqual((d['name'], d['class'], d['global_lease']['margin_mode']),
                                 (GS_ARM, 'GlobalMarginShieldPolicy', 'global'))

    def test_the_agent_refuses_changed_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_copy = Path(tmp) / 'E5.json'
            shutil.copyfile(H.ENVELOPES['E5'], env_copy)
            lp_copy = Path(tmp) / 'lease_params.json'
            shutil.copyfile(H.LEASE_PARAMS, lp_copy)
            cfg, _, _ = X.build_config(GS_ARM, envelope=str(env_copy), lease_params=str(lp_copy))
            self.assertIsInstance(X.build_policy(jround(cfg)), GS.GlobalMarginShieldPolicy)
            d = json.loads(env_copy.read_text(encoding='utf-8'))
            d['sigma_m']['vehicle'] *= 0.5                                       # E* changed after configuration
            env_copy.write_text(json.dumps(d), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'envelope file changed'):
                X.build_policy(jround(cfg))
            shutil.copyfile(H.ENVELOPES['E5'], env_copy)
            self.assertIsInstance(X.build_policy(jround(cfg)), GS.GlobalMarginShieldPolicy)
            lp_copy.write_text(lp_copy.read_text(encoding='utf-8') + '\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'lease parameter file changed'):
                X.build_policy(jround(cfg))
        cfg, _, _ = X.build_config(GS_ARM, envelope=str(H.ENVELOPES['E5']))
        tampered = []
        for path, value in ((('global_lease', 'h_bar_s'), 2.0), (('global_lease', 'reserve_m'), 0.1),
                            (('global_lease', 'lease_params', 'sigma_m', 'vehicle'), 0.1),
                            (('global_lease', 'lease_params', 'h_max_s'), 2.0),
                            (('global_lease', 'envelope_sha256'), '0' * 64), (('base_arm',), 'fl_full'),
                            (('schema',), 'x'), (('arm',), 'fl_heuristic')):
            bad = jround(cfg)
            node = bad['extension']
            for k in path[:-1]:
                node = node[k]
            node[path[-1]] = value
            tampered.append(bad)
        missing = jround(cfg)
        del missing['extension']
        tampered.append(missing)
        no_env = jround(cfg)
        no_env['v3']['envelope_path'] = no_env['v3']['envelope_sha256'] = None
        tampered.append(no_env)
        for k, bad in enumerate(tampered):
            with self.assertRaises(ValueError, msg=k):
                X.build_policy(bad)
            with self.assertRaises(ValueError, msg=k):
                X.validate_config(bad)
        extra_key = jround(cfg)
        extra_key['global_lease'] = {}
        with self.assertRaisesRegex(ValueError, 'unknown configuration keys'):
            X.validate_config(extra_key)
        for fn in (AV.agent_config_from, AV.build_policy, AV.validate_config):      # the pinned code refuses the arm
            with self.assertRaises((KeyError, ValueError)):
                fn(jround(cfg))

    def test_lease_constants_are_fixed(self):
        e5 = str(H.ENVELOPES['E5'])
        cfg, _, _ = X.build_config(GS_ARM, envelope=e5)
        self.assertEqual(X.build_config(GS_ARM, envelope=e5, lease_overrides={})[0], cfg)
        self.assertEqual((cfg['v3']['lease'], cfg['extension']['global_lease']['h_bar_s']), ({}, 2.5))
        self.assertEqual((GS.H_BAR_S, VL.SuffixLeaseConfig().h_bar_s), (2.5, 2.5))
        self.assertEqual(X.fixed_lease_problems(cfg), [])
        for overrides in ({'t_c_s': 1.0}, {'t_c_s': 0.5}, {'d_safe_m': 0.3}, {'delta_m': 0.1}, {'prefilter': False}):
            with self.assertRaisesRegex(ValueError, 'lease-overrides are refused', msg=str(overrides)):
                X.build_config(GS_ARM, envelope=e5, lease_overrides=overrides)
        # fl_heuristic keeps accepting them (the refusal is the extension arm's only; delegation unchanged)
        ref, _, _ = AV.build_config('fl_heuristic', envelope=e5, lease_overrides={'t_c_s': 1.0})
        self.assertEqual(X.build_config('fl_heuristic', envelope=e5, lease_overrides={'t_c_s': 1.0})[0], ref)
        self.assertEqual(ref['v3']['lease'], {'t_c_s': 1.0})
        # the configuration the previous version built for --lease-overrides '{"t_c_s": 1.0}': H_bar 2.0
        old = jround(ref)
        old.update(arm=GS_ARM, title=X.EXT_ARMS[GS_ARM].title, description=X.EXT_ARMS[GS_ARM].description)
        old['extension'] = X.extension_block(GS_ARM, GS.GlobalMarginShieldPolicy(env=AV.build_policy(jround(ref)).env))
        self.assertEqual(old['extension']['global_lease']['h_bar_s'], 2.0)
        self.assertEqual(len(X.fixed_lease_problems(old)), 2)
        lease_only = jround(cfg)
        lease_only['v3']['lease'] = {'t_c_s': 0.5}                      # an override equal to the default
        cap_only = jround(cfg)
        cap_only['extension']['global_lease']['h_bar_s'] = 2.0
        no_lease = jround(cfg)
        no_lease['v3']['lease'] = None
        for k, bad in enumerate((old, lease_only, cap_only, no_lease)):
            self.assertTrue(X.fixed_lease_problems(bad), k)
            for fn in (X.validate_config, X.agent_config_from, X.build_policy):
                with self.assertRaises(ValueError, msg=(k, fn.__name__)):
                    fn(jround(bad))

    def test_configuration_rules(self):
        e5 = str(H.ENVELOPES['E5'])
        with tempfile.TemporaryDirectory() as tmp:
            table = Path(tmp) / 'iso_table.json'
            table.write_text(json.dumps({'kind': 'iso_table', 'tau_s': [0.0, 3.0],
                                         'B_m': {'vehicle': [0.1, 0.4], 'pedestrian': [0.1, 0.3]}}))
            AV.build_config('fl_heuristic', envelope=str(table))                 # a v3 envelope the suffix lease takes
            bad = [dict(),                                                       # E* is required
                   dict(envelope=str(table)),                                   # not B(D) = sigma + vbar D + abar D^2/2
                   dict(envelope=e5, policy_params={'utility': 'v4_eps0.300_seed1'}),
                   dict(envelope=e5, policy_params={'utility': H.QNET_NAME},
                        utility_env={'FRAMELEASE_V4_QNET': str(H.QNET_FILE)}),
                   dict(envelope=e5, policy_params={'utility': 'v4_adet_d11'}),
                   dict(envelope=e5, policy_params={'max_depth': 4}),
                   dict(envelope=e5, runtime_params={'max_depth': 4}),
                   dict(envelope=e5, policy_params={'age_lease_s': 1.0}),
                   dict(envelope=e5, kappa=1.5, runtime_params={'kappa': 1.0})]
            for kw in bad:
                with self.assertRaises(ValueError, msg=str(kw)):
                    X.build_config(GS_ARM, **kw)
                os.environ.clear()
                os.environ.update(self._environ)
        cfg, _, _ = X.build_config(GS_ARM, envelope=e5, policy_params={'max_depth': 10, 'utility': 'v4_adet_d1'})
        self.assertEqual(cfg['agent']['policy_params'], {'max_depth': 10, 'utility': 'v4_adet_d1'})
        self.assertEqual(cfg['utility']['name'], 'v4_adet_d1')
        self.assertEqual(X.build_policy(jround(cfg)).utility.name, 'v4_adet_d1')


class PinnedStateTest(unittest.TestCase):
    """No attribute of a pinned module is rebound and no pinned object is mutated by the extension (fresh
    interpreters; the control does the same work through arms_v4 and the pinned launcher only)."""

    def report(self, extension):
        code = ('import sys; sys.path.insert(0, %r); import helpers_ext as H; H.main_pinned_state(launcher=True, '
                'extension=%r)' % (str(H.EXT_TESTS), bool(extension)))
        p = H.run_python(['-c', code], timeout=900)
        self.assertEqual(p.returncode, 0, p.stderr[-3000:])
        return json.loads(p.stdout.strip().splitlines()[-1])

    def test_no_pinned_attribute_is_rebound_or_mutated(self):
        ctl, ext = self.report(False), self.report(True)
        self.assertEqual(ctl['arms_used'], list(AV.ALL_ARMS))
        self.assertEqual(ext['arms_used'], list(AV.ALL_ARMS) + [GS_ARM])
        self.assertGreater(ext['n_attributes'], 1000)
        self.assertEqual(ext['n_attributes'], ctl['n_attributes'])
        self.assertEqual((ext['removed'], ext['added']), ([], []))
        self.assertEqual((ctl['removed'], ctl['added']), ([], []))
        self.assertEqual(ext['changed'], ctl['changed'])                 # only what the pinned code itself changes
        self.assertLessEqual(set(ctl['changed']), {'framelease_v3.runtime.v3_shield.UTILITIES',
                                                   'framelease_v4.arms.policies_v4._LOGGED'})
        self.assertEqual(ext['utilities_registered'], ctl['utilities_registered'])
        self.assertEqual(set(ext['added_submodule_bindings']) - set(ctl['added_submodule_bindings']),
                         {'framelease_v4.arms_ext'})
        if H.stack_ready():
            self.assertEqual(len(ctl['dry_runs']), 8)
            self.assertEqual(len(ext['dry_runs']), 17)
            self.assertEqual(set(ctl['dry_runs'].values()) | set(ext['dry_runs'].values()), {0})
        print('\npinned state:', {'attributes': ext['n_attributes'], 'changed (both)': ext['changed'],
                                  'utilities': ext['utilities_registered'], 'dry_runs': len(ext['dry_runs'])})


if __name__ == '__main__':
    unittest.main()
