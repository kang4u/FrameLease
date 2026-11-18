#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"
cd "$FRAMELEASE_ROOT"
for asset in CARLA_0.9.15.tar.gz AdditionalMaps_0.9.15.tar.gz; do
    if [[ -f "downloads/linux/$asset" && ! -f "downloads/linux/$asset.aria2" ]]; then
        printf '%s\n' "$asset already present; verify archive integrity before extraction."
        continue
    fi
    "$FRAMELEASE_TOOLS_ENV/bin/aria2c" --continue=true --always-resume=true \
      --auto-file-renaming=false --allow-overwrite=false -x8 -s8 \
      --min-split-size=32M --max-tries=6 --retry-wait=5 --timeout=60 \
      --dir=downloads/linux --out="$asset" \
      "https://carla-releases.s3.us-east-005.backblazeb2.com/Linux/$asset"
done
