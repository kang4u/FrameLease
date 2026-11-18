#!/usr/bin/env bash
# Run in a local terminal. sudo handles authentication; this script never reboots.
set -euo pipefail
sudo apt-get update
sudo apt-get install nvidia-driver-595-open vulkan-tools
printf '%s\n' 'Driver packages installed. Save your work and reboot when ready; then run nvidia-smi.'
