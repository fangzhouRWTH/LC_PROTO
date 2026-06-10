#!/usr/bin/env bash
# Tencent simplified scene + fixed demo pedestrians + vehicle-line traffic.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"

# Reuse the pedestrian demo defaults, then opt vehicles into the same dynamic plan.
# Prefer the first locally validated sedan asset for demo stability; use 4w/remote as fallbacks.
export SCENE_USD="${SCENE_USD:-${PROJECT_ROOT}/assets/blocks/demo_tencent_test_simplified.usdc}"
export DEMO_PEOPLE_SCENARIO="${DEMO_PEOPLE_SCENARIO:-people_3}"
export DYNAMIC_MAX_VEHICLE_ACTORS="${DYNAMIC_MAX_VEHICLE_ACTORS:-6}"
export DYNAMIC_VEHICLES_PER_LINE="${DYNAMIC_VEHICLES_PER_LINE:-3}"
export DYNAMIC_VEHICLE_SPEED_MPS="${DYNAMIC_VEHICLE_SPEED_MPS:-9.0}"
export DYNAMIC_VEHICLE_SPAWN_INTERVAL_S="${DYNAMIC_VEHICLE_SPAWN_INTERVAL_S:-4.0}"
export DYNAMIC_VEHICLE_VISUAL="${DYNAMIC_VEHICLE_VISUAL:-asset}"

LEGACY_DEMO_VEHICLE_ASSET="${HOME}/LeapsCora/local_assets/dynamic_vehicles/lc_proto_sedan_vehicle_zup.usda"
DEFAULT_ISAAC_VEHICLE_ASSET="${HOME}/LeapsCora/local_assets/dynamic_vehicles/isaac_vehicle_4w/main.usda"
REMOTE_ISAAC_VEHICLE_ASSET="https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Environments/Outdoor/Rivermark/dsready_content/nv_core/common_tools/validation/golden_assets/vehicle/4w/main.usda"
if [[ -z "${DYNAMIC_VEHICLE_ASSET_PATH:-}" ]]; then
  if [[ -f "${LEGACY_DEMO_VEHICLE_ASSET}" ]]; then
    export DYNAMIC_VEHICLE_ASSET_PATH="${LEGACY_DEMO_VEHICLE_ASSET}"
  elif [[ -f "${DEFAULT_ISAAC_VEHICLE_ASSET}" ]]; then
    export DYNAMIC_VEHICLE_ASSET_PATH="${DEFAULT_ISAAC_VEHICLE_ASSET}"
  else
    export DYNAMIC_VEHICLE_ASSET_PATH="${REMOTE_ISAAC_VEHICLE_ASSET}"
    echo "[WARN] Local demo vehicle assets not found:" >&2
    echo "       ${LEGACY_DEMO_VEHICLE_ASSET}" >&2
    echo "       ${DEFAULT_ISAAC_VEHICLE_ASSET}" >&2
    echo "       Falling back to the official Isaac remote vehicle USD; first load requires network." >&2
  fi
fi

exec "${PROJECT_ROOT}/scripts/run_demo_tencent_dynamic_people.sh" "$@"
