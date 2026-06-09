#!/usr/bin/env bash
# Tencent simplified scene + area_placement_methods + Isaac People pedestrians.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"

# Isaac People assets are searched below ISAAC_ASSET_ROOT/Isaac/People.
LOCAL_ISAAC_ASSET_ROOT="${HOME}/isaacsim_assets/Assets/Isaac/5.1"
if [[ -d "${LOCAL_ISAAC_ASSET_ROOT}/Isaac/People" ]]; then
  export ISAAC_ASSET_ROOT="${ISAAC_ASSET_ROOT:-${LOCAL_ISAAC_ASSET_ROOT}}"
fi

#DEFAULT_SCENE_USD="${PROJECT_ROOT}/assets/blocks/demo_tencent_test_simplified.usdc"
DEFAULT_SCENE_USD="${PROJECT_ROOT}/assets/blocks/demo_all_simplified.usd"

# LCSTD public-space USD library (see assets/lcstd_assets_library/static/).
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
export ROBOT_TYPE="${ROBOT_TYPE:-none}"
export SENSOR_PROFILE="${SENSOR_PROFILE:-none}"
export AUTO_PLAY="${AUTO_PLAY:-true}"
# Keep the Kit window alive for N frames; does not re-start play after the user stops.
export AUTO_PLAY_MIN_FRAMES="${AUTO_PLAY_MIN_FRAMES:-2400}"
export ENABLE_DYNAMIC_AGENTS="${ENABLE_DYNAMIC_AGENTS:-true}"
export DYNAMIC_AGENT_BACKEND="${DYNAMIC_AGENT_BACKEND:-isaac_people_sumo}"
export DYNAMIC_ROUTE_MODE="${DYNAMIC_ROUTE_MODE:-once}"
export DYNAMIC_PEDESTRIAN_SPEED_MPS="${DYNAMIC_PEDESTRIAN_SPEED_MPS:-0.8}"
export DYNAMIC_MAX_PEDESTRIAN_ACTORS="${DYNAMIC_MAX_PEDESTRIAN_ACTORS:-40}"
export DYNAMIC_MAX_VEHICLE_ACTORS="${DYNAMIC_MAX_VEHICLE_ACTORS:-0}"
export DYNAMIC_ISAAC_PEOPLE_CONTROL="${DYNAMIC_ISAAC_PEOPLE_CONTROL:-route}"
export DYNAMIC_ISAAC_PEOPLE_NAVMESH="${DYNAMIC_ISAAC_PEOPLE_NAVMESH:-false}"
export DYNAMIC_ISAAC_PEOPLE_YAW_OFFSET_DEG="${DYNAMIC_ISAAC_PEOPLE_YAW_OFFSET_DEG:-90}"
export DYNAMIC_ISAAC_PEOPLE_DEBUG="${DYNAMIC_ISAAC_PEOPLE_DEBUG:-false}"

LAYOUT_OUTPUT_DIR="${LAYOUT_OUTPUT_DIR:-${PROJECT_ROOT}/outputs/area_placement/demo_tencent_dynamic_people}"
USE_DUMMY_PUBLIC_SPACE_ASSETS="${USE_DUMMY_PUBLIC_SPACE_ASSETS:-false}"
PUBLIC_SPACE_ASSET_NAME_MAP="$(resolve_public_space_asset_name_map || true)"

args=(
  --layout-backend area_placement_methods
  --layout-output-dir "${LAYOUT_OUTPUT_DIR}"
  --use-dummy-public-space-assets "${USE_DUMMY_PUBLIC_SPACE_ASSETS}"
  --skip-legacy-placeholder-areas true
)

if [[ "${DEMO_PEOPLE_USE_STATIC_PLAN}" == "true" ]]; then
  if [[ -f "${DEMO_PEOPLE_PLACEMENT_PLAN}" ]]; then
    args+=(--placement-plan-json "${DEMO_PEOPLE_PLACEMENT_PLAN}")
  else
    echo "[ERROR] Demo people preset plan not found: ${DEMO_PEOPLE_PLACEMENT_PLAN}" >&2
    echo "        Set DEMO_PEOPLE_SCENARIO=people_1|people_2|people_3|people_4|people_5|people_6" >&2
    echo "        or set DEMO_PEOPLE_USE_STATIC_PLAN=false to regenerate from config." >&2
    exit 2
  fi
elif [[ -n "${DEMO_PEOPLE_CONFIG}" && -f "${DEMO_PEOPLE_CONFIG}" ]]; then
  args+=(--demo-people-config "${DEMO_PEOPLE_CONFIG}")
  args+=(--demo-people-scenario "${DEMO_PEOPLE_SCENARIO}")
elif [[ -n "${DEMO_PEOPLE_CONFIG}" ]]; then
  echo "[WARN] Demo people config not found: ${DEMO_PEOPLE_CONFIG}" >&2
fi

if [[ -n "${PUBLIC_SPACE_ASSET_NAME_MAP}" && -f "${PUBLIC_SPACE_ASSET_NAME_MAP}" ]]; then
  args+=(--public-space-asset-name-map "${PUBLIC_SPACE_ASSET_NAME_MAP}")
  echo "[INFO] Public-space asset map: ${PUBLIC_SPACE_ASSET_NAME_MAP}"
elif [[ "${USE_DUMMY_PUBLIC_SPACE_ASSETS}" != "true" ]]; then
  echo "[WARN] Public-space asset map not found." >&2
  echo "       Expected: ${PROJECT_ROOT}/assets/lcstd_assets_library/static/asset_name_map.json" >&2
  echo "       Set PUBLIC_SPACE_ASSET_NAME_MAP=... or USE_DUMMY_PUBLIC_SPACE_ASSETS=true." >&2
fi

exec "${PROJECT_ROOT}/scripts/run_sim.sh" "${args[@]}" "$@"
