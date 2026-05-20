#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/sim_defaults.sh"

build_sim_args
build_kit_log_args

cd "${PROJECT_ROOT}"

"${ISAAC_PYTHON}" \
  src/simworld/main.py \
  "${sim_args[@]}" \
  "${kit_log_args[@]}" \
  "$@"
