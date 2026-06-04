#!/usr/bin/env bash
# Patch segment simworld attrs on demo_tencent_test.usd (no extra CLI args — Kit steals them).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/sim_defaults.sh"
cd "${PROJECT_ROOT}"
exec "${ISAAC_PYTHON}" "${SCRIPT_DIR}/patch_demo_tencent_usd_segments.py"
