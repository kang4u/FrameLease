#!/usr/bin/env bash
# Resume package installation after an interrupted session or reboot.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"
cd "$FRAMELEASE_ROOT"
py="$FRAMELEASE_MODEL_ENV/bin/python"
"$py" -m pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124
"$py" -m pip install -r configs/requirements_linux_b2d.txt --no-build-isolation --no-index --find-links downloads/linux/wheels
DS_BUILD_OPS=0 "$py" -m pip install deepspeed==0.14.4 --no-build-isolation
"$py" -m pip install --no-deps 'downloads/linux/wheels/flash_attn-2.7.4.post1+cu12torch2.5cxx11abiFALSE-cp310-cp310-linux_x86_64.whl'
"$py" -m pip install --no-deps --no-build-isolation -e third_party/mmdetection3d-linux
export FORCE_CUDA=1 MMCV_WITH_OPS=1 MMCV_NO_Compiler_CHECK=1
"$py" -m pip install --no-deps --no-build-isolation -v -e "$FRAMELEASE_UNIDRIVE_REPO/third_party/mmcv-1.7.2"
bash linux/build_official_ops.sh
bash linux/apply_dependency_fixes.sh
"$py" -m pip check
