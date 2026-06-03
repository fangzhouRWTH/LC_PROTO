#!/usr/bin/env bash
# Audit scene USD with OpenUSD (pxr). Uses Isaac Sim python when system python lacks pxr.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/sim_defaults.sh"

cd "${PROJECT_ROOT}"

if [[ -z "${ISAAC_PYTHON:-}" || ! -x "${ISAAC_PYTHON}" ]]; then
  echo "[ERROR] Isaac python not found. Set ISAAC_PYTHON or ISAACSIM_ROOT." >&2
  exit 2
fi

exec "${ISAAC_PYTHON}" "${SCRIPT_DIR}/audit_scene_usd.py" --bootstrap-isaac "$@"
