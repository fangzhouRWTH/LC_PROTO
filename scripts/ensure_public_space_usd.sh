#!/usr/bin/env bash
# Patch scene USD: simworld attrs + synthesized segment prims from compact region names.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/sim_defaults.sh"

cd "${PROJECT_ROOT}"

if [[ -z "${ISAAC_PYTHON:-}" || ! -x "${ISAAC_PYTHON}" ]]; then
  echo "[ERROR] Isaac python not found. Set ISAAC_PYTHON or ISAACSIM_ROOT." >&2
  exit 2
fi

exec "${ISAAC_PYTHON}" "${SCRIPT_DIR}/ensure_public_space_usd.py" --bootstrap-isaac "$@"
