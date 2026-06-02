#!/usr/bin/env bash
# Run SimWorld unit tests without Isaac Sim.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"
export PYTHONPATH="${PROJECT_ROOT}/src/simworld${PYTHONPATH:+:${PYTHONPATH}}"

exec python3 -m unittest discover -s tests -v "$@"
