#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"
cd "$FRAMELEASE_ROOT"
audit_dir="${1:-$FRAMELEASE_ROOT/audits/linux_setup_20261104/check_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$audit_dir"
export FRAMELEASE_CHECK_OUTPUT="$audit_dir"
"$FRAMELEASE_MODEL_ENV/bin/python" - <<'PY'
import importlib, importlib.metadata, json, os, platform, shutil, subprocess, sys
from pathlib import Path
result = {'platform': platform.platform(), 'python': sys.version,
          'executable': sys.executable, 'conda': (Path(sys.prefix)/'conda-meta').is_dir(),
          'project': os.environ['FRAMELEASE_ROOT'], 'checks': {},
          'model_inference': 'NOT_RUN', 'closed_loop': 'NOT_RUN',
          'research_gate_promoted': False}
for name, command in [('nvidia_smi', ['nvidia-smi']), ('nvcc', ['nvcc', '--version']),
                      ('pip_check', [sys.executable, '-m', 'pip', 'check'])]:
    try:
        p = subprocess.run(command, capture_output=True, text=True, timeout=40)
        result['checks'][name] = {'command': command, 'returncode': p.returncode,
                                 'stdout': p.stdout, 'stderr': p.stderr}
    except (OSError, subprocess.TimeoutExpired) as e:
        result['checks'][name] = {'command': command, 'error': repr(e), 'returncode': None}
for name in ('torch', 'torchvision', 'carla', 'mmcv.ops', 'mmdet', 'mmdet3d', 'transformers.models.qwen3_vl', 'flash_attn', 'peft'):
    try:
        m = importlib.import_module(name)
        result['checks']['import_'+name] = {'passed': True, 'path': getattr(m, '__file__', None)}
    except Exception as e:
        result['checks']['import_'+name] = {'passed': False, 'error': repr(e)}
try:
    import torch
    gpu = {'torch': torch.__version__, 'runtime_cuda': torch.version.cuda,
           'available': torch.cuda.is_available()}
    result['checks']['cuda_tensor'] = gpu
    if not gpu['available']:
        raise RuntimeError('CUDA driver/device unavailable')
    prop = torch.cuda.get_device_properties(0)
    gpu.update(name=prop.name, total_memory_bytes=prop.total_memory,
               free_memory_bytes=torch.cuda.mem_get_info()[0])
    x = torch.arange(16, device='cuda', dtype=torch.float32)
    y = (x*x).sum()
    torch.cuda.synchronize()
    gpu.update(passed=y.item()==1240.0, result=y.item())
except Exception as e:
    result['checks'].setdefault('cuda_tensor', {}).update(passed=False, error=repr(e))
result['carla_server'] = {'path': os.environ['CARLA_ROOT'],
                          'launcher_exists': (Path(os.environ['CARLA_ROOT'])/'CarlaUE4.sh').is_file()}
passed = all(v.get('passed', v.get('returncode') == 0) for v in result['checks'].values())
result['status'] = 'ENVIRONMENT_CHECKS_PASSED' if passed and result['carla_server']['launcher_exists'] else 'PARTIAL'
path = Path(os.environ['FRAMELEASE_CHECK_OUTPUT'])/'environment.json'
path.write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps({'status': result['status'], 'evidence': str(path), 'cuda': result['checks']['cuda_tensor']}))
sys.exit(0 if result['status']=='ENVIRONMENT_CHECKS_PASSED' else 2)
PY
