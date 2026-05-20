#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/home/fangzhou/projects/LC_01}"
ISAAC_PYTHON="${ISAAC_PYTHON:-/home/fangzhou/Nvidia/isaacsim-git/isaacsim/_build/linux-x86_64/release/python.sh}"

SCENE_USD="${SCENE_USD:-${PROJECT_ROOT}/assets/blocks/test_field/test_simple_city.usd}"
ROBOT_NAME="${ROBOT_NAME:-spot_demo}"
WARMUP_FRAMES="${WARMUP_FRAMES:-30}"
CAMERA_PRIM_PATH="${CAMERA_PRIM_PATH:-/OmniverseKit_Persp}"

cd "${PROJECT_ROOT}"

"${ISAAC_PYTHON}" \
  src/simworld/main.py \
  --scene-usd "${SCENE_USD}" \
  --robot-name "${ROBOT_NAME}" \
  --warmup-frames "${WARMUP_FRAMES}" \
  --camera-prim-path "${CAMERA_PRIM_PATH}" \
  --/log/level=error \
  --/log/fileLogLevel=error \
  --/log/outputStreamLevel=error \
  "$@"
