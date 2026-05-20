#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/sim_defaults.sh"

build_sim_args
build_kit_log_args

DEBUG_HOST="${DEBUG_HOST:-0.0.0.0}"
DEBUG_PORT="${DEBUG_PORT:-5678}"
WAIT_FOR_CLIENT="${WAIT_FOR_CLIENT:-1}"

debug_args=(--listen "${DEBUG_HOST}:${DEBUG_PORT}")
if [[ "${WAIT_FOR_CLIENT}" == "1" || "${WAIT_FOR_CLIENT}" == "true" ]]; then
  debug_args+=(--wait-for-client)
fi

cd "${PROJECT_ROOT}"

"${ISAAC_PYTHON}" \
  -m debugpy \
  "${debug_args[@]}" \
  src/simworld/main.py \
  "${sim_args[@]}" \
  "${kit_log_args[@]}" \
  "$@"
