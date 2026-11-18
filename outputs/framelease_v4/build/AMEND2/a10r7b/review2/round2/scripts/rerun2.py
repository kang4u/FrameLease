"""Run a10r7b/rerun_review2_sim.py (which loads review2/review2_sim.py unchanged) with its logs and its link directory
moved to /tmp/A10A11/recheck1/ (the item's own logs in review_rerun/review2_logs/ stay untouched). Trees under
/tmp/A10A11/applier/ (the harness accepts nothing else), removed by the harness at the end."""
import importlib.util
import sys
from pathlib import Path

P = Path('/home/kang/Desktop/DAC/outputs/framelease_v4/build/AMEND2/a10r7b/rerun_review2_sim.py')
s = importlib.util.spec_from_file_location('rerun_review2_sim', P)
R = importlib.util.module_from_spec(s)
s.loader.exec_module(R)
R.LOGS = Path('/tmp/A10A11/recheck1/review2_logs')
R.XHERE = Path('/tmp/A10A11/recheck1/xhere')
sys.argv = [str(P)] + sys.argv[1:]
sys.exit(R.main())
