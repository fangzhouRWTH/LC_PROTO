#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"

# Entertainment-only dynamic-agent demo. This script keeps the normal people,
# vehicle, and route behavior, but swaps pedestrian visuals to the grim reaper.
# It intentionally wraps scripts/run_sim.sh instead of changing the normal
# LC_PROTO demo entrypoint.
GRIM_REAPER_ASSET_PATH="${GRIM_REAPER_ASSET_PATH:-${HOME}/桌面/Untitled.usd}"
if [[ ! -f "${GRIM_REAPER_ASSET_PATH}" ]]; then
  echo "[ERROR] Grim reaper USD not found: ${GRIM_REAPER_ASSET_PATH}" >&2
  echo "        Set GRIM_REAPER_ASSET_PATH=/path/to/your/reaper.usd" >&2
  exit 1
fi

export WARMUP_FRAMES="${WARMUP_FRAMES:-0}"
export SCENE_USD="${SCENE_USD:-assets/blocks/test_dynamic_agents/test_dynamic_agents.usda}"
export SENSOR_PROFILE="${SENSOR_PROFILE:-none}"
export CAMERA_PRIM_PATH="${CAMERA_PRIM_PATH:-/World/DemoCamera}"
export DYNAMIC_AGENT_BACKEND="${DYNAMIC_AGENT_BACKEND:-orca_sumo}"
export DYNAMIC_MAX_PEDESTRIAN_ACTORS="${DYNAMIC_MAX_PEDESTRIAN_ACTORS:-5}"
export DYNAMIC_MAX_VEHICLE_ACTORS="${DYNAMIC_MAX_VEHICLE_ACTORS:-2}"
export DYNAMIC_ROUTE_MODE="${DYNAMIC_ROUTE_MODE:-once}"
export DYNAMIC_PLACEHOLDER_VISIBILITY="${DYNAMIC_PLACEHOLDER_VISIBILITY:-hidden}"
export DYNAMIC_PEDESTRIAN_VISUAL="asset"
export DYNAMIC_PEDESTRIAN_ASSET_PATH="${DYNAMIC_PEDESTRIAN_ASSET_PATH:-${GRIM_REAPER_ASSET_PATH}}"
export DYNAMIC_PEDESTRIAN_ASSET_SCALE="${DYNAMIC_PEDESTRIAN_ASSET_SCALE:-${GRIM_REAPER_SCALE:-5.0}}"
export DYNAMIC_VEHICLE_VISUAL="${DYNAMIC_VEHICLE_VISUAL:-asset}"
export DYNAMIC_VEHICLE_ASSET_PATH="${DYNAMIC_VEHICLE_ASSET_PATH:-${HOME}/LeapsCora/local_assets/dynamic_vehicles/lc_proto_sedan_vehicle_zup.usda}"

exec "${PROJECT_ROOT}/scripts/run_sim.sh"
