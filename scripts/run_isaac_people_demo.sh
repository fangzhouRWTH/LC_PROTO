#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"

# Animated pedestrian demo. This uses Isaac omni.anim.people for pedestrians
# and the current LC_PROTO mock SUMO vehicle backend for cars. It requires
# Isaac People assets under the configured Isaac asset root:
#   Isaac/People/Characters/
#   Isaac/People/MotionLibrary/HumanMotionLibrary.usd

export WARMUP_FRAMES="${WARMUP_FRAMES:-0}"
export SCENE_USD="${SCENE_USD:-assets/blocks/test_dynamic_agents/test_dynamic_agents.usda}"
export SENSOR_PROFILE="${SENSOR_PROFILE:-none}"
export CAMERA_PRIM_PATH="${CAMERA_PRIM_PATH:-/World/DemoCamera}"
export DYNAMIC_AGENT_BACKEND="${DYNAMIC_AGENT_BACKEND:-isaac_people_sumo}"
export DYNAMIC_ROUTE_MODE="${DYNAMIC_ROUTE_MODE:-once}"
export DYNAMIC_MAX_PEDESTRIAN_ACTORS="${DYNAMIC_MAX_PEDESTRIAN_ACTORS:-1}"
export DYNAMIC_MAX_VEHICLE_ACTORS="${DYNAMIC_MAX_VEHICLE_ACTORS:-2}"
export DYNAMIC_PLACEHOLDER_VISIBILITY="${DYNAMIC_PLACEHOLDER_VISIBILITY:-hidden}"
export DYNAMIC_VEHICLE_VISUAL="${DYNAMIC_VEHICLE_VISUAL:-asset}"
export DYNAMIC_VEHICLE_ASSET_PATH="${DYNAMIC_VEHICLE_ASSET_PATH:-${HOME}/LeapsCora/local_assets/dynamic_vehicles/lc_proto_sedan_vehicle_zup.usda}"

exec "${PROJECT_ROOT}/scripts/run_sim.sh"
