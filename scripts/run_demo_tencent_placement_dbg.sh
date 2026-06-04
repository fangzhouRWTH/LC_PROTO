#!/usr/bin/env bash
# Same as run_demo_tencent_placement.sh but with debugpy (WAIT_FOR_CLIENT=0 for no wait).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"

export SCENE_USD="${SCENE_USD:-${PROJECT_ROOT}/assets/blocks/demo/demo_tencent_test.usd}"
export WEATHER="${WEATHER:-sunny}"
export DAYTIME="${DAYTIME:-day}"
export SENSOR_PROFILE="${SENSOR_PROFILE:-none}"
export WARMUP_FRAMES="${WARMUP_FRAMES:-30}"
export ENABLE_DYNAMIC_AGENTS="${ENABLE_DYNAMIC_AGENTS:-false}"
export LAYOUT_OUTPUT_DIR="${LAYOUT_OUTPUT_DIR:-${PROJECT_ROOT}/outputs/area_placement/demo_tencent}"

exec "${PROJECT_ROOT}/scripts/run_sim_dbg.sh" \
  --layout-backend area_placement_methods \
  --use-dummy-public-space-assets true \
  --skip-legacy-placeholder-areas true \
  --layout-output-dir "${LAYOUT_OUTPUT_DIR}" \
  "$@"
