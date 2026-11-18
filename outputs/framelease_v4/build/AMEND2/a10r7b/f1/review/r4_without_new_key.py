"""Round-4 review of A11: run the round-2 and round-3 review tests against f1_class_report.py of fix pass 4 with the new
key differences_by_class['undefined_metric_pairing'] removed from every report (after checking that it is 0), so that
only behaviour other than the new key can fail. Synthetic data and fixture runs only (/tmp).

  taskset -c 12-15 nice -n 19 ionice -c 3 <wrapper> python -I -B r4_without_new_key.py
"""
import importlib.util
import os
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def patch(R):
    orig = R.report

    def report(out_dir):
        rep = orig(out_dir)
        n = rep['differences_by_class'].pop('undefined_metric_pairing')
        assert n == 0, n
        # class_undefined_metric_pairing stays: main() prints its runs per arm
        return rep
    R.report = report


suite = unittest.TestSuite()
for name in ('r2_test_adversarial', 'r3_test_new'):
    mod = _load(name + '_nk', os.path.join(HERE, name + '.py'))
    patch(mod.R)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(mod))
res = unittest.TextTestRunner(verbosity=2).run(suite)
print('FAILED/ERRORS:', sorted({str(t[0]).split()[0] for t in res.failures + res.errors}))
