#!/usr/bin/env bash

SIM_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SIM_SCRIPT_DIR}/.." && pwd)}"

find_isaac_python() {
  local candidate

  if [[ -n "${ISAACSIM_ROOT:-}" ]]; then
    candidate="${ISAACSIM_ROOT}/python.sh"
    if [[ -x "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  fi

  candidate="${HOME}/Nvidia/isaacsim-git/isaacsim/_build/linux-x86_64/release/python.sh"
  if [[ -x "${candidate}" ]]; then
    printf '%s\n' "${candidate}"
    return 0
  fi

  shopt -s nullglob
  for candidate in "${HOME}"/.local/share/ov/pkg/isaac-sim-*/python.sh; do
    if [[ -x "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      shopt -u nullglob
      return 0
    fi
  done
  shopt -u nullglob

  return 1
}

ISAAC_PYTHON="${ISAAC_PYTHON:-$(find_isaac_python || true)}"
if [[ -z "${ISAAC_PYTHON}" || ! -x "${ISAAC_PYTHON}" ]]; then
  echo "[ERROR] Isaac Python launcher not found." >&2
  echo "        Set ISAAC_PYTHON=/path/to/isaacsim/python.sh or ISAACSIM_ROOT=/path/to/isaacsim." >&2
  exit 1
fi

# Leave these empty to use Python defaults from simworld.isaac_env.simulation.
SCENE_USD="${SCENE_USD:-}"
ROBOT_TYPE="${ROBOT_TYPE:-}"
ROBOT_NAME="${ROBOT_NAME:-}"
WARMUP_FRAMES="${WARMUP_FRAMES:-}"
CAMERA_PRIM_PATH="${CAMERA_PRIM_PATH:-}"

KIT_LOG_LEVEL="${KIT_LOG_LEVEL:-error}"
KIT_FILE_LOG_LEVEL="${KIT_FILE_LOG_LEVEL:-error}"
KIT_OUTPUT_STREAM_LEVEL="${KIT_OUTPUT_STREAM_LEVEL:-error}"

append_sim_arg_if_set() {
  local flag="$1"
  local value="${2:-}"

  if [[ -n "${value}" ]]; then
    sim_args+=("${flag}" "${value}")
  fi
}

build_sim_args() {
  sim_args=()
  append_sim_arg_if_set "--scene-usd" "${SCENE_USD}"
  append_sim_arg_if_set "--robot-type" "${ROBOT_TYPE}"
  append_sim_arg_if_set "--robot-name" "${ROBOT_NAME}"
  append_sim_arg_if_set "--warmup-frames" "${WARMUP_FRAMES}"
  append_sim_arg_if_set "--camera-prim-path" "${CAMERA_PRIM_PATH}"
}

build_kit_log_args() {
  kit_log_args=(
    "--/log/level=${KIT_LOG_LEVEL}"
    "--/log/fileLogLevel=${KIT_FILE_LOG_LEVEL}"
    "--/log/outputStreamLevel=${KIT_OUTPUT_STREAM_LEVEL}"
  )
}
