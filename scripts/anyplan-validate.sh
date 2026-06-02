#!/usr/bin/env bash
# Validate Anyplan guidance artifacts for this repository.
set -euo pipefail

INSTANCE="${1:-lc01-simworld}"
ANYPLAN_ROOT="${ANYPLAN_ROOT:-/home/fangzhou/projects/Anygine/Anyplan}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -d "$ANYPLAN_ROOT/scripts" ]]; then
  echo "Set ANYPLAN_ROOT to your Anyplan framework checkout." >&2
  exit 1
fi

python3 "$ANYPLAN_ROOT/scripts/build-doc-index.py" --project-id "$INSTANCE" --repo-root "$REPO_ROOT"
"$ANYPLAN_ROOT/scripts/validate-guidance.sh" "$REPO_ROOT/instances/$INSTANCE/guidance.json"
"$ANYPLAN_ROOT/scripts/validate-dashboard.sh" "$REPO_ROOT/instances/$INSTANCE/dashboard.json"
echo "OK: instances/$INSTANCE"
