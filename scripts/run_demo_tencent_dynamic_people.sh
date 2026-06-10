#!/usr/bin/env bash
# Tencent simplified scene demo. Static placement and dynamic agents are off by default.
# Robot (optional): ROBOT_TYPE=none|spot|go2 spawns at placeholder_{spot,go2}_spawn_*.
# Path cameras: ENABLE_PATH_CAMERAS=true follows placeholder_path_camera_* in the scene.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"

# Local Isaac asset cache (Go2 USD, People, etc.).
LOCAL_ISAAC_ASSET_ROOT="${HOME}/isaacsim_assets/Assets/Isaac/5.1"

DEFAULT_SCENE_USD="${PROJECT_ROOT}/assets/blocks/demo_tencent_test_simplified.usdc"
DEMO_PEOPLE_SCENARIO="${DEMO_PEOPLE_SCENARIO:-people_3}"
DEMO_DYNAMIC_ROUTES_DIR="${DEMO_DYNAMIC_ROUTES_DIR:-${PROJECT_ROOT}/configs/demo_agents/generated/demo_tencent_test_simplified}"
DEMO_DYNAMIC_ROUTES_PREFIX="${DEMO_DYNAMIC_ROUTES_PREFIX:-demo_tencent}"
DEFAULT_DYNAMIC_ROUTES_JSON="${DEMO_DYNAMIC_ROUTES_DIR}/${DEMO_DYNAMIC_ROUTES_PREFIX}_${DEMO_PEOPLE_SCENARIO}_dynamic_routes.json"
export DYNAMIC_ROUTES_JSON="${DYNAMIC_ROUTES_JSON:-${DEFAULT_DYNAMIC_ROUTES_JSON}}"
DEMO_PEOPLE_USE_STATIC_PLAN="${DEMO_PEOPLE_USE_STATIC_PLAN:-false}"
DEMO_PEOPLE_PRESET_DIR="${DEMO_PEOPLE_PRESET_DIR:-${PROJECT_ROOT}/configs/demo_people/generated}"
DEMO_PEOPLE_PLACEMENT_PLAN="${DEMO_PEOPLE_PLACEMENT_PLAN:-}"

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

export SCENE_USD="${SCENE_USD:-${DEFAULT_SCENE_USD}}"
export ROBOT_TYPE="${ROBOT_TYPE:-none}"
export ROBOT_NAME="${ROBOT_NAME:-${ROBOT_TYPE}_demo}"
export SENSOR_PROFILE="${SENSOR_PROFILE:-none}"
export CHASE_CAMERA="${CHASE_CAMERA:-false}"
export ENABLE_PATH_CAMERAS="${ENABLE_PATH_CAMERAS:-false}"
export PATH_CAMERA_INDEX="${PATH_CAMERA_INDEX:-0}"
export PATH_CAMERA_SPEED_MPS="${PATH_CAMERA_SPEED_MPS:-}"
export PATH_CAMERA_ROUTE_MODE="${PATH_CAMERA_ROUTE_MODE:-}"
export WEATHER="${WEATHER:-sunny}"
export DAYTIME="${DAYTIME:-day}"
export WARMUP_FRAMES="${WARMUP_FRAMES:-30}"
export AUTO_PLAY="${AUTO_PLAY:-true}"
export AUTO_PLAY_MIN_FRAMES="${AUTO_PLAY_MIN_FRAMES:-2400}"
export ENABLE_PUBLIC_SPACE_PLACEMENT="${ENABLE_PUBLIC_SPACE_PLACEMENT:-false}"
export ENABLE_DYNAMIC_AGENTS="${ENABLE_DYNAMIC_AGENTS:-false}"
export DYNAMIC_AGENT_BACKEND="${DYNAMIC_AGENT_BACKEND:-isaac_people_sumo}"
export DYNAMIC_ROUTE_MODE="${DYNAMIC_ROUTE_MODE:-once}"
export DYNAMIC_PEDESTRIAN_SPEED_MPS="${DYNAMIC_PEDESTRIAN_SPEED_MPS:-0.8}"
export DYNAMIC_MAX_PEDESTRIAN_ACTORS="${DYNAMIC_MAX_PEDESTRIAN_ACTORS:-40}"
export DYNAMIC_MAX_VEHICLE_ACTORS="${DYNAMIC_MAX_VEHICLE_ACTORS:-0}"
export DYNAMIC_ISAAC_PEOPLE_CONTROL="${DYNAMIC_ISAAC_PEOPLE_CONTROL:-route}"
export DYNAMIC_ISAAC_PEOPLE_NAVMESH="${DYNAMIC_ISAAC_PEOPLE_NAVMESH:-false}"
export DYNAMIC_ISAAC_PEOPLE_YAW_OFFSET_DEG="${DYNAMIC_ISAAC_PEOPLE_YAW_OFFSET_DEG:-90}"
export DYNAMIC_ISAAC_PEOPLE_DEBUG="${DYNAMIC_ISAAC_PEOPLE_DEBUG:-false}"
export DYNAMIC_ISAAC_PEOPLE_IGNORE_SPAWN_TIME="${DYNAMIC_ISAAC_PEOPLE_IGNORE_SPAWN_TIME:-true}"

LAYOUT_OUTPUT_DIR="${LAYOUT_OUTPUT_DIR:-${PROJECT_ROOT}/outputs/area_placement/demo_tencent_dynamic_people}"
USE_DUMMY_PUBLIC_SPACE_ASSETS="${USE_DUMMY_PUBLIC_SPACE_ASSETS:-false}"
PUBLIC_SPACE_ASSET_NAME_MAP="$(resolve_public_space_asset_name_map || true)"

DEMO_PEOPLE_USE_STATIC_PLAN="${DEMO_PEOPLE_USE_STATIC_PLAN:-false}"
DEMO_PEOPLE_SCENARIO="${DEMO_PEOPLE_SCENARIO:-people_1}"
DEMO_PEOPLE_PRESET_DIR="${DEMO_PEOPLE_PRESET_DIR:-${PROJECT_ROOT}/configs/demo_people/generated}"
DEMO_PEOPLE_CONFIG="${DEMO_PEOPLE_CONFIG:-${PROJECT_ROOT}/configs/demo_people/tencent_dynamic_people_scenarios.json}"
if [[ -z "${DEMO_PEOPLE_PLACEMENT_PLAN:-}" ]]; then
  DEMO_PEOPLE_PLACEMENT_PLAN="${DEMO_PEOPLE_PRESET_DIR}/tencent_${DEMO_PEOPLE_SCENARIO}_placement_plan.json"
fi

args=(
  --skip-legacy-placeholder-areas true
  --layout-backend legacy
)

if [[ "${ENABLE_PUBLIC_SPACE_PLACEMENT}" == "true" ]]; then
  args=(
    --skip-legacy-placeholder-areas true
    --layout-backend area_placement_methods
    --layout-output-dir "${LAYOUT_OUTPUT_DIR}"
    --use-dummy-public-space-assets "${USE_DUMMY_PUBLIC_SPACE_ASSETS}"
  )

if [[ "${DEMO_PEOPLE_USE_STATIC_PLAN}" == "true" ]]; then
  if [[ -z "${DEMO_PEOPLE_PLACEMENT_PLAN}" ]]; then
    DEMO_PEOPLE_PLACEMENT_PLAN="${DEMO_PEOPLE_PRESET_DIR}/tencent_${DEMO_PEOPLE_SCENARIO}_placement_plan.json"
  fi
  if [[ -f "${DEMO_PEOPLE_PLACEMENT_PLAN}" ]]; then
    args+=(--placement-plan-json "${DEMO_PEOPLE_PLACEMENT_PLAN}")
    echo "[INFO] Legacy demo static placement plan: ${DEMO_PEOPLE_PLACEMENT_PLAN}"
  else
    echo "[ERROR] Demo people preset plan not found: ${DEMO_PEOPLE_PLACEMENT_PLAN}" >&2
    exit 2
  fi
elif [[ -n "${DYNAMIC_ROUTES_JSON}" ]]; then
  if [[ -f "${DYNAMIC_ROUTES_JSON}" ]]; then
    echo "[INFO] Dynamic routes JSON: ${DYNAMIC_ROUTES_JSON}"
  else
    echo "[ERROR] Dynamic routes JSON not found: ${DYNAMIC_ROUTES_JSON}" >&2
    echo "        Generate it first with scripts/build_demo_dynamic_agent_presets.sh" >&2
    echo "        or set DYNAMIC_ROUTES_JSON to a scene-specific dynamic-only routes file." >&2
    exit 2
  fi
fi

  if [[ -n "${PUBLIC_SPACE_ASSET_NAME_MAP}" && -f "${PUBLIC_SPACE_ASSET_NAME_MAP}" ]]; then
    args+=(--public-space-asset-name-map "${PUBLIC_SPACE_ASSET_NAME_MAP}")
    echo "[INFO] Public-space asset map: ${PUBLIC_SPACE_ASSET_NAME_MAP}"
  elif [[ "${USE_DUMMY_PUBLIC_SPACE_ASSETS}" != "true" ]]; then
    echo "[WARN] Public-space asset map not found." >&2
    echo "       Expected: ${PROJECT_ROOT}/assets/lcstd_assets_library/static/asset_name_map.json" >&2
    echo "       Set PUBLIC_SPACE_ASSET_NAME_MAP=... or USE_DUMMY_PUBLIC_SPACE_ASSETS=true." >&2
  fi
else
  echo "[INFO] Public-space static placement disabled (ENABLE_PUBLIC_SPACE_PLACEMENT=false)."
fi

if [[ "${ENABLE_DYNAMIC_AGENTS}" != "true" ]]; then
  echo "[INFO] Dynamic agents disabled (ENABLE_DYNAMIC_AGENTS=false)."
fi

if [[ "${ENABLE_PATH_CAMERAS}" != "true" ]]; then
  echo "[INFO] Path cameras disabled (ENABLE_PATH_CAMERAS=false)."
fi

exec "${PROJECT_ROOT}/scripts/run_sim.sh" "${args[@]}" "$@"
