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
CHASE_CAMERA="${CHASE_CAMERA:-}"
ENABLE_DYNAMIC_AGENTS="${ENABLE_DYNAMIC_AGENTS:-}"
DYNAMIC_AGENT_BACKEND="${DYNAMIC_AGENT_BACKEND:-}"
DYNAMIC_MAX_PEDESTRIAN_ACTORS="${DYNAMIC_MAX_PEDESTRIAN_ACTORS:-}"
DYNAMIC_MAX_VEHICLE_ACTORS="${DYNAMIC_MAX_VEHICLE_ACTORS:-}"
DYNAMIC_PEDESTRIAN_SPEED_MPS="${DYNAMIC_PEDESTRIAN_SPEED_MPS:-}"
DYNAMIC_VEHICLE_SPEED_MPS="${DYNAMIC_VEHICLE_SPEED_MPS:-}"
DYNAMIC_SPAWN_TIME_S="${DYNAMIC_SPAWN_TIME_S:-}"
WEATHER="${WEATHER:-}"
DAYTIME="${DAYTIME:-}"
SKY_TEXTURE="${SKY_TEXTURE:-}"
SUN_INTENSITY="${SUN_INTENSITY:-}"
SKY_INTENSITY="${SKY_INTENSITY:-}"
SKY_EXPOSURE="${SKY_EXPOSURE:-}"
WEATHER_TIME_SCALE="${WEATHER_TIME_SCALE:-}"
WEATHER_START_TIME="${WEATHER_START_TIME:-}"

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
  append_sim_arg_if_set "--chase-camera" "${CHASE_CAMERA}"
  append_sim_arg_if_set "--enable-dynamic-agents" "${ENABLE_DYNAMIC_AGENTS}"
  append_sim_arg_if_set "--dynamic-agent-backend" "${DYNAMIC_AGENT_BACKEND}"
  append_sim_arg_if_set "--dynamic-max-pedestrian-actors" "${DYNAMIC_MAX_PEDESTRIAN_ACTORS}"
  append_sim_arg_if_set "--dynamic-max-vehicle-actors" "${DYNAMIC_MAX_VEHICLE_ACTORS}"
  append_sim_arg_if_set "--dynamic-pedestrian-speed-mps" "${DYNAMIC_PEDESTRIAN_SPEED_MPS}"
  append_sim_arg_if_set "--dynamic-vehicle-speed-mps" "${DYNAMIC_VEHICLE_SPEED_MPS}"
  append_sim_arg_if_set "--dynamic-spawn-time-s" "${DYNAMIC_SPAWN_TIME_S}"
  append_sim_arg_if_set "--weather" "${WEATHER}"
  append_sim_arg_if_set "--daytime" "${DAYTIME}"
  append_sim_arg_if_set "--sky-texture" "${SKY_TEXTURE}"
  append_sim_arg_if_set "--sun-intensity" "${SUN_INTENSITY}"
  append_sim_arg_if_set "--sky-intensity" "${SKY_INTENSITY}"
  append_sim_arg_if_set "--sky-exposure" "${SKY_EXPOSURE}"
  append_sim_arg_if_set "--weather-time-scale" "${WEATHER_TIME_SCALE}"
  append_sim_arg_if_set "--weather-start-time" "${WEATHER_START_TIME}"
}

build_kit_log_args() {
  kit_log_args=(
    "--/log/level=${KIT_LOG_LEVEL}"
    "--/log/fileLogLevel=${KIT_FILE_LOG_LEVEL}"
    "--/log/outputStreamLevel=${KIT_OUTPUT_STREAM_LEVEL}"
  )
}
