#!/usr/bin/env bash
# Idempotent fixes to the independent dependency copy, never the pinned upstream.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"
cd "$FRAMELEASE_ROOT"
python - <<'PY'
from pathlib import Path
import shutil
base=Path('third_party/transformers-linux/src/transformers')
fixes=[
 ('onnx/config.py','from typing import TYPE_CHECKING, Any, Callable, Optional, Union','from typing import TYPE_CHECKING, Any, Callable, Optional, Union, List, Dict, Tuple'),
 ('models/bloom/configuration_bloom.py','from typing import TYPE_CHECKING, Any, Optional','from typing import TYPE_CHECKING, Any, Optional, List'),
 ('models/bloom/modeling_bloom.py','from typing import Optional, Union','from typing import Optional, Union, Tuple'),
]
for name,old,new in fixes:
    path=base/name
    lines=path.read_text().splitlines(keepends=True)
    if new+'\n' in lines:continue
    if lines.count(old+'\n')!=1:raise RuntimeError('Unexpected dependency source: '+str(path))
    lines[lines.index(old+'\n')]=new+'\n'
    path.write_text(''.join(lines))
benchmark=Path('third_party/bench2drive-linux')
if not benchmark.exists():
    shutil.copytree(Path('third_party/UniDriveVLA-linux/Bench2Drive/bench2drive'),benchmark,
                    ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for name in ('leaderboard/leaderboard/utils/route_parser.py',
             'scenario_runner/srunner/tools/route_parser.py',
             'scenario_runner/srunner/tools/scenario_parser.py'):
    path=benchmark/name;text=path.read_text()
    if 'scenario.getchildren()' not in text:
        if 'for elem in list(scenario):' not in text:raise RuntimeError('Unexpected XML parser: '+str(path))
        continue
    if text.count('scenario.getchildren()')!=1:raise RuntimeError('Unexpected XML parser: '+str(path))
    path.write_text(text.replace('scenario.getchildren()','list(scenario)'))
PY
python -c 'import peft; print("PEFT import passed:", peft.__version__)'
