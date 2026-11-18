#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"
if ! command -v nvidia-smi >/dev/null || ! nvidia-smi >/dev/null; then
    printf '%s\n' 'BLOCKED: NVIDIA driver is not ready; see linux/install_driver.sh.' >&2
    exit 2
fi
if [[ ! -x "$CARLA_ROOT/CarlaUE4.sh" ]]; then
    printf '%s\n' "BLOCKED: missing Linux CARLA launcher at $CARLA_ROOT/CarlaUE4.sh" >&2
    exit 2
fi
cd "$CARLA_ROOT"
exec ./CarlaUE4.sh -RenderOffScreen -nosound -quality-level=Low -carla-rpc-port=2199 "$@"
