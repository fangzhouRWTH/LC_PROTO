#!/usr/bin/env bash
# test_go.usd: robot spawn + path cameras. Static placement off by default (ENABLE_PUBLIC_SPACE_PLACEMENT=true to enable).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"

DEFAULT_SCENE_USD="${PROJECT_ROOT}/assets/blocks/test_go.usd"
LOCAL_ISAAC_ASSET_ROOT="${HOME}/isaacsim_assets/Assets/Isaac/5.1"

resolve_go2_usd_path() {
  local candidate
  for candidate in \
    "${GO2_USD_PATH:-}" \
    "${LOCAL_ISAAC_ASSET_ROOT}/Isaac/IsaacLab/Robots/Unitree/Go2/go2.usd" \
    "${LOCAL_ISAAC_ASSET_ROOT}/Isaac/Robots/Unitree/Go2/go2.usd"
  do
    if [[ -n "${candidate}" && -f "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  return 1
}

resolve_public_space_asset_name_map() {
  local candidate
  for candidate in \
    "${PUBLIC_SPACE_ASSET_NAME_MAP:-}" \
    "${PROJECT_ROOT}/assets/lcstd_assets_library/static/asset_name_map.json" \
    "${PROJECT_ROOT}/assets/lcstd_assets_library./lcstd_assets_library/static/asset_name_map.json"
  do
    if [[ -n "${candidate}" && -f "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  return 1
}

export SCENE_USD="${SCENE_USD:-${DEFAULT_SCENE_USD}}"
# Spot spawns at the first parsed placeholder_spot_spawn_* (see scene_parser spawn rule).
export ROBOT_TYPE="${ROBOT_TYPE:-spot}"
export ROBOT_NAME="${ROBOT_NAME:-spot_demo}"
export SENSOR_PROFILE="${SENSOR_PROFILE:-none}"
export CHASE_CAMERA="${CHASE_CAMERA:-false}"
export WEATHER="${WEATHER:-sunny}"
export DAYTIME="${DAYTIME:-day}"
export WARMUP_FRAMES="${WARMUP_FRAMES:-30}"
export AUTO_PLAY="${AUTO_PLAY:-true}"
export AUTO_PLAY_MIN_FRAMES="${AUTO_PLAY_MIN_FRAMES:-600}"
export ENABLE_PUBLIC_SPACE_PLACEMENT="${ENABLE_PUBLIC_SPACE_PLACEMENT:-false}"
export ENABLE_DYNAMIC_AGENTS="${ENABLE_DYNAMIC_AGENTS:-false}"
export ENABLE_PATH_CAMERAS="${ENABLE_PATH_CAMERAS:-false}"

if [[ "${ROBOT_TYPE}" == "go2" ]]; then
  GO2_USD_RESOLVED="$(resolve_go2_usd_path || true)"
  if [[ -z "${GO2_USD_RESOLVED}" ]]; then
    echo "[ERROR] Unitree Go2 USD not found." >&2
    echo "        Set GO2_USD_PATH=/path/to/go2.usd" >&2
    echo "        or install under ${LOCAL_ISAAC_ASSET_ROOT}/Isaac/IsaacLab/Robots/Unitree/Go2/." >&2
    exit 2
  fi
  export GO2_USD_PATH="${GO2_USD_RESOLVED}"
  echo "[INFO] Go2 USD: ${GO2_USD_PATH}"
fi

LAYOUT_OUTPUT_DIR="${LAYOUT_OUTPUT_DIR:-${PROJECT_ROOT}/outputs/area_placement/test_go}"
USE_DUMMY_PUBLIC_SPACE_ASSETS="${USE_DUMMY_PUBLIC_SPACE_ASSETS:-false}"
PUBLIC_SPACE_ASSET_NAME_MAP="$(resolve_public_space_asset_name_map || true)"

args=(
  --skip-legacy-placeholder-areas true
  --layout-backend legacy
)

if [[ "${ENABLE_PUBLIC_SPACE_PLACEMENT}" == "true" ]]; then
  args=(
    --skip-legacy-placeholder-areas true
  args+=(
    --layout-backend area_placement_methods
    --layout-output-dir "${LAYOUT_OUTPUT_DIR}"
    --use-dummy-public-space-assets "${USE_DUMMY_PUBLIC_SPACE_ASSETS}"
  )

  if [[ -n "${PUBLIC_SPACE_ASSET_NAME_MAP}" && -f "${PUBLIC_SPACE_ASSET_NAME_MAP}" ]]; then
    args+=(--public-space-asset-name-map "${PUBLIC_SPACE_ASSET_NAME_MAP}")
    echo "[INFO] Public-space asset map: ${PUBLIC_SPACE_ASSET_NAME_MAP}"
  elif [[ "${USE_DUMMY_PUBLIC_SPACE_ASSETS}" != "true" ]]; then
    echo "[WARN] Public-space asset map not found." >&2
    echo "       Expected: ${PROJECT_ROOT}/assets/lcstd_assets_library/static/asset_name_map.json" >&2
    echo "       Set PUBLIC_SPACE_ASSET_NAME_MAP=... or USE_DUMMY_PUBLIC_SPACE_ASSETS=true." >&2
  fi
else
  args+=(--layout-backend legacy)
  echo "[INFO] Public-space static placement disabled (ENABLE_PUBLIC_SPACE_PLACEMENT=false)."
fi

if [[ "${ENABLE_DYNAMIC_AGENTS}" != "true" ]]; then
  echo "[INFO] Dynamic agents disabled (ENABLE_DYNAMIC_AGENTS=false)."
fi

exec "${PROJECT_ROOT}/scripts/run_sim.sh" "${args[@]}" "$@"
