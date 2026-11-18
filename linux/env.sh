#!/usr/bin/env bash
# Source this file; it changes only the current shell.
export FRAMELEASE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export FRAMELEASE_MODEL_ENV="$FRAMELEASE_ROOT/.conda-unidrive-linux"
export FRAMELEASE_TOOLS_ENV="$FRAMELEASE_ROOT/.conda-tools-linux"
export FRAMELEASE_UNIDRIVE_REPO="$FRAMELEASE_ROOT/third_party/UniDriveVLA-linux"
export CARLA_ROOT="${CARLA_ROOT:-/home/kang/opt/CARLA_0.9.15}"
export WORK_DIR="$FRAMELEASE_UNIDRIVE_REPO/Bench2Drive"
export PROJECT_DIR="$WORK_DIR"
export FRAMELEASE_BENCHMARK_ROOT="$FRAMELEASE_ROOT/third_party/bench2drive-linux"
export CHECKPOINT="$FRAMELEASE_ROOT/checkpoints/UniDriveVLA/b5ac33e9483f6f61633c53353a8b53fbd96e2bc5/UniDriveVLA_Stage3_Bench2drive_2B.pt"
export VLM_PRETRAINED_PATH="$FRAMELEASE_ROOT/checkpoints/Qwen3-VL-2B-Instruct/89644892e4d85e24eaac8bacfd4f463576704203"
export CUDA_HOME="$FRAMELEASE_TOOLS_ENV"
export CC="$FRAMELEASE_TOOLS_ENV/bin/x86_64-conda-linux-gnu-gcc"
export CXX="$FRAMELEASE_TOOLS_ENV/bin/x86_64-conda-linux-gnu-g++"
export CUDAHOSTCXX="$CXX"
export PATH="$FRAMELEASE_MODEL_ENV/bin:$FRAMELEASE_TOOLS_ENV/bin:$PATH"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-8.9}"
export MAX_JOBS="${MAX_JOBS:-4}"
export PYTHONNOUSERSITE=1
export PYTHONPATH="$WORK_DIR:$FRAMELEASE_BENCHMARK_ROOT:$FRAMELEASE_BENCHMARK_ROOT/leaderboard:$FRAMELEASE_BENCHMARK_ROOT/scenario_runner:$CARLA_ROOT/PythonAPI:$CARLA_ROOT/PythonAPI/carla${PYTHONPATH:+:$PYTHONPATH}"
export SCENARIO_RUNNER_ROOT="$FRAMELEASE_BENCHMARK_ROOT/scenario_runner"
export LEADERBOARD_ROOT="$FRAMELEASE_BENCHMARK_ROOT/leaderboard"
export IS_BENCH2DRIVE=1
export IS_VISUALIZE=0
export PLANNER_TYPE=traj
