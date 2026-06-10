#!/usr/bin/env bash
# Download the official Isaac 5.1 4-wheel vehicle USD pack used by the Tencent demo.
set -euo pipefail

DEST_DIR="${DYNAMIC_VEHICLE_ASSET_DIR:-${HOME}/LeapsCora/local_assets/dynamic_vehicles/isaac_vehicle_4w}"
BASE_URL="https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Environments/Outdoor/Rivermark/dsready_content/nv_core/common_tools/validation/golden_assets/vehicle/4w"
FILES=(
  "main.usda"
  "main_with_physx.usda"
  "parts.usda"
  "instance/body.usda"
  "instance/door_0.usda"
  "instance/door_1.usda"
  "instance/door_2.usda"
  "instance/door_3.usda"
  "instance/lights.usda"
  "instance/main.usda"
  "instance/trunk.usda"
  "instance/wheel.usda"
)

for rel_path in "${FILES[@]}"; do
  target="${DEST_DIR}/${rel_path}"
  mkdir -p "$(dirname "${target}")"
  echo "[INFO] Downloading ${rel_path}"
  curl -L --fail --retry 3 --retry-delay 2 -o "${target}" "${BASE_URL}/${rel_path}"
done

echo "[OK] Isaac 4w vehicle asset installed: ${DEST_DIR}/main.usda"
