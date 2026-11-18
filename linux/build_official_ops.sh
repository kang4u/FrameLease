#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"
export FORCE_CUDA=1
cd "$WORK_DIR/projects/mmdet3d_plugin/ops"
"$FRAMELEASE_MODEL_ENV/bin/python" setup.py build_ext --inplace
