"""Drift guard of the functions framelease_v4/arms_ext copies from pinned framelease_v4/arms modules (GSHIELD review,
should-fix 5). CPU only; nothing is imported from the evaluator stack (no torch, CARLA or official agent) and nothing
is written.

  cd /home/kang/Desktop/DAC && export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 && \
      nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B -m pytest -q -p no:cacheprovider \
      framelease_v4/arms_ext/tests/test_drift_guard.py

The copies and their pinned sources:
  run_closed_loop_ext.run          <- run_closed_loop_v4.run     (GAP_AUDIT Sec. 2 item 4, the alternative to rebinding)
  run_closed_loop_ext.prepare      <- run_closed_loop_v4.prepare
  agent_ext.setup_ext              <- agent_v4.setup_v4
  FrameLeaseV4ExtAgent.setup       <- FrameLeaseV4Agent.setup    (both classes inside build_agent_class)

What is shown, for each copy:
  * text: the pinned source with the substitutions listed below applied (each exactly the stated number of times, in
    the stated order) equals the copy, line for line (docstrings excluded; the source is read with ast from the files).
    So a copy differs from its pinned source only by these substitutions, which are the ones the module docstrings of
    run_closed_loop_ext.py and agent_ext.py document. An edit of a copy, or an amendment of a pinned source, fails here
    until the list is reviewed;
  * bindings (run, prepare, setup_ext): every module-level name the copy reads is the same object as the pinned
    module's binding of that name (modules, classes, helpers; equal values for constants), except the extension's own
    functions of the same name (prepare, evaluator_command, run_config, code_dependencies, STAGE in run(): each of them
    differs from the pinned one by the extension's entry, sources or block) and the names the substitutions introduce;
    the pinned names a substitution removes are reached through the pinned module (RV4.<name>, AG.<name>);
  * FrameLeaseV4ExtAgent overrides setup() only, and build_agent_class imports what the pinned one imports plus
    agent_v4 (AG) and arms_v4 (AV, moved out of the pinned setup()).
"""
from __future__ import annotations

import ast
import textwrap
import types
import unittest
from pathlib import Path

import helpers_ext as H

from framelease_v4.arms import agent_v4 as AG
from framelease_v4.arms import run_closed_loop_v4 as RV4
from framelease_v4.arms_ext import agent_ext as AGX
from framelease_v4.arms_ext import run_closed_loop_ext as RX

PINNED_LAUNCHER = 'framelease_v4/arms/run_closed_loop_v4.py'
PINNED_AGENT = 'framelease_v4/arms/agent_v4.py'
EXT_LAUNCHER = 'framelease_v4/arms_ext/run_closed_loop_ext.py'
EXT_AGENT = 'framelease_v4/arms_ext/agent_ext.py'

# (pinned text, copy text, occurrences in the pinned source, what the substitution is)
VIA_RV4 = 'a pinned run_closed_loop_v4 helper, called through RV4 (the same object)'
RUN_SUBSTITUTIONS = (
    ("args.port + 6000]}, indent=1, default=str))",
     "args.port + 6000],\n                          'extension': extension_info(prep)}, indent=1, default=str))", 1,
     'the extension block of the dry-run output'),
    ('evaluator_env(prep, ', 'RV4.evaluator_env(prep, ', 2, VIA_RV4),
    ("    atomic_json(raw / 'source_v4' / 'hashes.json', freeze_v4_sources(raw, prep))\n",
     "    v4_hashes = RV4.freeze_v4_sources(raw, prep)\n    v4_hashes.update(freeze_ext_sources(raw))\n"
     "    atomic_json(raw / 'source_v4' / 'hashes.json', v4_hashes)\n", 1,
     'the extension sources frozen and hashed with the v4 sources'),
    ('raw / CONFIG_NAME', 'raw / RV4.CONFIG_NAME', 1, VIA_RV4),
    ('raw / FP_CONFIG_NAME', 'raw / RV4.FP_CONFIG_NAME', 1, VIA_RV4),
    ('(raw / AG.ENTRY_NAME).write_text(AG.ENTRY_SOURCE', '(raw / AGX.ENTRY_NAME).write_text(AGX.ENTRY_SOURCE', 1,
     'the extension entry file'),
    ('actor_log_outcome(run_dir, cfg)', 'RV4.actor_log_outcome(run_dir, cfg)', 1, VIA_RV4),
)
PREPARE_SUBSTITUTIONS = (
    ('fp = fast_prefix_config(args)', 'fp = RV4.fast_prefix_config(args)', 1, VIA_RV4),
    ('cfg, lease_params, envelope = AV.build_config(', 'cfg, lease_params, envelope = X.build_config(', 1,
     'arms_ext.build_config (the extension registry; arms_v4 arms delegated)'),
    ('ns = namespace(args, lease_params)', 'ns = RV4.namespace(base_args(args), lease_params)', 1,
     VIA_RV4 + ', on the base-arm view of the arguments'),
    ('for rel in V4_CODE if', 'for rel in RV4.V4_CODE + X.EXT_CODE if', 1, 'the extension sources must exist too'),
    ("{'arm': AV.ARMS[args.arm]", "{'arm': X.ARMS[args.arm]", 1, 'the extension registry'),
)
SETUP_EXT_SUBSTITUTIONS = (
    ('def setup_v4(', 'def setup_ext(', 1, 'the function name'),
    ('    from framelease_v4.arms import arms_v4 as AV\n', '    from framelease_v4.arms import agent_v4 as AG\n', 1,
     'agent_v4 instead of arms_v4'),
    ('    full = load_v4_config()\n',
     '    from framelease_v4.arms_ext import arms_ext as X\n    full = AG.load_v4_config()\n', 1,
     'arms_ext imported; the pinned agent_v4 helper called through AG'),
    ('AV.agent_config_from(full)', 'X.agent_config_from(full)', 1, 'arms_ext.agent_config_from'),
    ('AV.build_policy(full)', 'X.build_policy(full)', 1, 'arms_ext.build_policy'),
)
AGENT_SETUP_SUBSTITUTIONS = (
    ('    from framelease_v4.arms import arms_v4 as AV\n', '', 1, 'arms_v4 is imported by build_agent_class'),
    ('full = setup_v4(self, ', 'full = setup_ext(self, ', 1, 'setup_ext instead of setup_v4'),
    ('    install_actor_log(self, ', '    AG.install_actor_log(self, ', 1,
     'the pinned agent_v4 helper called through AG'),
)
# module-level names of a copy: the extension's own functions with a pinned helper's name, and the names that the
# substitutions introduce (removed pinned names are reached through RV4 / AG)
RUN_OWN = {'prepare', 'evaluator_command', 'run_config', 'code_dependencies', 'STAGE'}
RUN_NEW = {'RV4', 'AGX', 'freeze_ext_sources', 'extension_info'}
RUN_REMOVED = {'evaluator_env', 'freeze_v4_sources', 'CONFIG_NAME', 'FP_CONFIG_NAME', 'AG', 'actor_log_outcome'}
PREPARE_NEW = {'RV4', 'X', 'base_args'}
PREPARE_REMOVED = {'fast_prefix_config', 'AV', 'namespace', 'V4_CODE'}
SETUP_EXT_REMOVED = {'load_v4_config'}


def _node(tree, path):
    node = tree
    for name in path:
        found = [n for n in ast.iter_child_nodes(node)
                 if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name]
        if len(found) != 1:
            raise LookupError(f'{".".join(path)}: {len(found)} definitions of {name!r}')
        node = found[0]
    return node


def definition(rel, *path):
    """(ast node, dedented source without its docstring) of the definition rel:path[0].path[1]... (nested classes and
    functions), read from the file."""
    text = (H.ROOT / rel).read_text(encoding='utf-8')
    node = _node(ast.parse(text), path)
    lines = text.splitlines(True)
    skip = set()
    first = node.body[0] if node.body else None
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        skip = set(range(first.lineno, first.end_lineno + 1))
    src = ''.join(lines[i - 1] for i in range(node.lineno, node.end_lineno + 1) if i not in skip)
    return node, textwrap.dedent(src)


def apply(src, substitutions):
    """The pinned source with the substitutions applied in order; raises if one does not occur exactly as often as
    stated."""
    for old, new, count, what in substitutions:
        n = src.count(old)
        if n != count:
            raise AssertionError(f'substitution "{what}": {old!r} occurs {n} times in the pinned source, not {count}')
        src = src.replace(old, new)
    return src


def global_refs(fn):
    """{name: object} of the module-level names a function reads (its code and the nested code objects of its
    comprehensions and generator expressions). Dunder names are left out: co_names also holds attribute names, and
    an attribute such as type(x).__name__ would match the module's own __name__."""
    names, stack = set(), [fn.__code__]
    while stack:
        code = stack.pop()
        names.update(code.co_names)
        stack += [c for c in code.co_consts if isinstance(c, types.CodeType)]
    g = fn.__globals__
    return {n: g[n] for n in names if n in g and not (n.startswith('__') and n.endswith('__'))}


def same_binding(a, b):
    if a is b:
        return True
    return isinstance(a, (str, bytes, int, float, tuple, Path)) and type(a) is type(b) and a == b


def imports_of(node):
    """{alias: module or module.name} of the import statements directly in a function body."""
    out = {}
    for n in node.body:
        if isinstance(n, ast.ImportFrom):
            for a in n.names:
                out[a.asname or a.name] = f'{n.module}.{a.name}'
        elif isinstance(n, ast.Import):
            for a in n.names:
                out[a.asname or a.name] = a.name
    return out


class TextTest(unittest.TestCase):
    def assert_copy(self, pinned, copy, substitutions):
        _, src_p = definition(*pinned)
        _, src_c = definition(*copy)
        want = apply(src_p, substitutions)
        self.assertEqual(want.splitlines(), src_c.splitlines(), f'{copy} drifted from {pinned}')
        self.assertNotEqual(src_p, src_c)

    def test_run_is_the_pinned_run_with_the_documented_substitutions(self):
        self.assert_copy((PINNED_LAUNCHER, 'run'), (EXT_LAUNCHER, 'run'), RUN_SUBSTITUTIONS)

    def test_prepare_is_the_pinned_prepare_with_the_documented_substitutions(self):
        self.assert_copy((PINNED_LAUNCHER, 'prepare'), (EXT_LAUNCHER, 'prepare'), PREPARE_SUBSTITUTIONS)

    def test_setup_ext_is_setup_v4_with_the_documented_substitutions(self):
        self.assert_copy((PINNED_AGENT, 'setup_v4'), (EXT_AGENT, 'setup_ext'), SETUP_EXT_SUBSTITUTIONS)

    def test_agent_setup_is_the_pinned_agent_setup_with_setup_ext(self):
        self.assert_copy((PINNED_AGENT, 'build_agent_class', 'FrameLeaseV4Agent', 'setup'),
                         (EXT_AGENT, 'build_agent_class', 'FrameLeaseV4ExtAgent', 'setup'), AGENT_SETUP_SUBSTITUTIONS)

    def test_the_agent_class_overrides_setup_only(self):
        cls, _ = definition(EXT_AGENT, 'build_agent_class', 'FrameLeaseV4ExtAgent')
        self.assertEqual([b.id for b in cls.bases if isinstance(b, ast.Name)], ['Base'])
        body = [n for n in cls.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
        self.assertEqual([(type(n).__name__, getattr(n, 'name', None)) for n in body], [('FunctionDef', 'setup')])
        ext, _ = definition(EXT_AGENT, 'build_agent_class')
        pinned, _ = definition(PINNED_AGENT, 'build_agent_class')
        pinned_setup, _ = definition(PINNED_AGENT, 'build_agent_class', 'FrameLeaseV4Agent', 'setup')
        self.assertEqual(imports_of(ext), {**imports_of(pinned), **imports_of(pinned_setup),
                                           'AG': 'framelease_v4.arms.agent_v4'})
        self.assertEqual(imports_of(pinned_setup), {'AV': 'framelease_v4.arms.arms_v4'})
        base = [n for n in ext.body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', None) == 'Base']
        self.assertEqual(len(base), 1)
        self.assertEqual(ast.unparse(base[0].value), 'AG.build_agent_class(world_fn, backend_factory)')

    def test_a_drifted_copy_is_detected(self):
        _, src_p = definition(PINNED_LAUNCHER, 'run')
        _, src_c = definition(EXT_LAUNCHER, 'run')
        want = apply(src_p, RUN_SUBSTITUTIONS)
        self.assertEqual(want, src_c)
        # an edit of the copy
        self.assertNotEqual(want, src_c.replace("'FRAMELEASE_V4_ARMS']", "'FRAMELEASE_V4_ARMS', 'X']"))
        # an amended pinned source: a substitution whose pinned text is gone is reported
        with self.assertRaisesRegex(AssertionError, 'occurs 0 times'):
            apply(src_p.replace('raw / FP_CONFIG_NAME', 'raw / FP_NAME'), RUN_SUBSTITUTIONS)


class BindingTest(unittest.TestCase):
    def assert_bindings(self, pinned_fn, copy_fn, own=(), new=(), removed=()):
        refs_p, refs_c = global_refs(pinned_fn), global_refs(copy_fn)
        self.assertEqual(set(refs_p) - set(refs_c), set(removed))     # reached through RV4 / AG (TextTest)
        self.assertEqual(set(refs_c) - set(refs_p), set(new))
        for name in sorted(set(refs_c) & set(refs_p)):
            if name in own:
                self.assertIsNot(refs_c[name], refs_p[name], name)
                if callable(refs_c[name]):
                    self.assertEqual(refs_c[name].__module__, copy_fn.__module__, name)
            else:
                self.assertTrue(same_binding(refs_c[name], refs_p[name]), name)
        self.assertTrue(set(own) <= set(refs_c) & set(refs_p))

    def test_run(self):
        self.assert_bindings(RV4.run, RX.run, RUN_OWN, RUN_NEW, RUN_REMOVED)
        self.assertIs(RX.RV4, RV4)
        self.assertIs(RX.AGX, AGX)

    def test_prepare(self):
        self.assert_bindings(RV4.prepare, RX.prepare, (), PREPARE_NEW, PREPARE_REMOVED)

    def test_setup_ext(self):
        self.assert_bindings(AG.setup_v4, AGX.setup_ext, (), (), SETUP_EXT_REMOVED)


if __name__ == '__main__':
    unittest.main()
