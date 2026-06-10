#!/usr/bin/env bash
# Build scene-specific people_1..people_6 pedestrian/vehicle demo preset JSONs.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
source "${SCRIPT_DIR}/sim_defaults.sh"

SCENE_USD_INPUT="${SCENE_USD:-}"
OUTPUT_DIR_INPUT=""
PRESET_PREFIX_INPUT=""
PEOPLE_CONFIG="${DEMO_PEOPLE_CONFIG:-${PROJECT_ROOT}/configs/demo_people/tencent_dynamic_people_scenarios.json}"
AGENT_CONFIG="${DEMO_AGENT_CONFIG:-${PROJECT_ROOT}/configs/demo_agents/tencent_dynamic_agent_scenarios.json}"
STEPS="${LAYOUT_STEPS:-1,2,3,4,5}"
GENERATE_HTML="${GENERATE_HTML:-true}"
SHOW_WALKABLE_LINES="${SHOW_WALKABLE_LINES:-true}"
SHOW_ZONES="${SHOW_ZONES:-true}"

usage() {
  cat <<USAGE
Usage: $0 --scene-usd path/to/scene.usd [options]

Options:
  --scene-usd PATH        USD/USDC scene containing public-space and vehicle labels.
  --output-dir DIR        Output directory for generated JSONs.
  --preset-prefix NAME    Prefix for generated files. Defaults to sanitized scene stem.
  --people-config PATH    Demo people scenario config JSON.
  --agent-config PATH     Demo people+vehicle runtime scenario config JSON.
  --steps LIST            Area placement steps, default: ${STEPS}
  --skip-html             Do not generate route preview HTML files.
  -h, --help              Show this help.

Environment overrides are also supported: SCENE_USD, DEMO_PEOPLE_CONFIG,
DEMO_AGENT_CONFIG, GENERATE_HTML, LAYOUT_STEPS, ISAAC_PYTHON, ISAACSIM_ROOT.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scene-usd)
      SCENE_USD_INPUT="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR_INPUT="$2"
      shift 2
      ;;
    --preset-prefix)
      PRESET_PREFIX_INPUT="$2"
      shift 2
      ;;
    --people-config)
      PEOPLE_CONFIG="$2"
      shift 2
      ;;
    --agent-config)
      AGENT_CONFIG="$2"
      shift 2
      ;;
    --steps)
      STEPS="$2"
      shift 2
      ;;
    --skip-html)
      GENERATE_HTML="false"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "${SCENE_USD_INPUT}" ]]; then
  echo "[ERROR] Missing --scene-usd or SCENE_USD." >&2
  usage >&2
  exit 2
fi

SCENE_USD_PATH="$(cd "$(dirname "${SCENE_USD_INPUT}")" && pwd)/$(basename "${SCENE_USD_INPUT}")"
if [[ ! -f "${SCENE_USD_PATH}" ]]; then
  echo "[ERROR] Scene USD not found: ${SCENE_USD_PATH}" >&2
  exit 2
fi

scene_stem="$(basename "${SCENE_USD_PATH}")"
scene_stem="${scene_stem%.*}"
scene_slug="$(printf %s "${scene_stem}" | tr -c A-Za-z0-9_ _)"
PRESET_PREFIX="${PRESET_PREFIX_INPUT:-${scene_slug}}"
OUTPUT_DIR="${OUTPUT_DIR_INPUT:-${PROJECT_ROOT}/configs/demo_agents/generated/${scene_slug}}"
HTML_DIR="${HTML_OUTPUT_DIR:-${PROJECT_ROOT}/outputs/public_space_routes/${scene_slug}}"
BASE_PLAN="${OUTPUT_DIR}/${PRESET_PREFIX}_base_placement_plan.json"
BASE_SUMMARY="${OUTPUT_DIR}/${PRESET_PREFIX}_base_summary.json"
PEOPLE_SUMMARY="${OUTPUT_DIR}/${PRESET_PREFIX}_people_preset_summary.json"
RUNTIME_SUMMARY="${OUTPUT_DIR}/${PRESET_PREFIX}_dynamic_agent_preset_summary.json"

mkdir -p "${OUTPUT_DIR}" "${HTML_DIR}"

echo "[INFO] Scene: ${SCENE_USD_PATH}"
echo "[INFO] Output dir: ${OUTPUT_DIR}"
echo "[INFO] Prefix: ${PRESET_PREFIX}"

"${ISAAC_PYTHON}" "${PROJECT_ROOT}/scripts/export_public_space_plan_from_usd.py" \
  --scene-usd "${SCENE_USD_PATH}" \
  --output "${BASE_PLAN}" \
  --summary-json "${BASE_SUMMARY}" \
  --steps "${STEPS}" \
  --quiet

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${PROJECT_ROOT}/src/simworld" \
python3 "${PROJECT_ROOT}/scripts/build_demo_people_static_presets.py" \
  --base-placement-plan-json "${BASE_PLAN}" \
  --demo-people-config "${PEOPLE_CONFIG}" \
  --output-dir "${OUTPUT_DIR}" \
  --preset-prefix "${PRESET_PREFIX}" \
  --summary-json "${PEOPLE_SUMMARY}"

PYTHONDONTWRITEBYTECODE=1 \
python3 "${PROJECT_ROOT}/scripts/build_demo_agent_runtime_presets.py" \
  --scene-usd "${SCENE_USD_PATH}" \
  --people-plan-dir "${OUTPUT_DIR}" \
  --preset-prefix "${PRESET_PREFIX}" \
  --output-dir "${OUTPUT_DIR}" \
  --people-config "${PEOPLE_CONFIG}" \
  --agent-config "${AGENT_CONFIG}" \
  --base-placement-plan-json "${BASE_PLAN}" \
  --summary-json "${RUNTIME_SUMMARY}"

if [[ "${GENERATE_HTML}" == "true" ]]; then
  for scenario in people_1 people_2 people_3 people_4 people_5 people_6; do
    html_args=(
      --placement-plan-json "${OUTPUT_DIR}/${PRESET_PREFIX}_${scenario}_placement_plan.json"
      --output "${HTML_DIR}/${PRESET_PREFIX}_${scenario}.html"
      --color-by status
      --labels region
    )
    if [[ "${SHOW_WALKABLE_LINES}" == "true" ]]; then
      html_args+=(--show-walkable-lines)
    fi
    if [[ "${SHOW_ZONES}" == "true" ]]; then
      html_args+=(--show-zones)
    fi
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${PROJECT_ROOT}/src/simworld" \
    python3 "${PROJECT_ROOT}/scripts/visualize_public_space_routes.py" "${html_args[@]}"
  done
fi

cat <<DONE
[OK] Generated demo dynamic agent presets.
Base plan: ${BASE_PLAN}
Runtime summary: ${RUNTIME_SUMMARY}

Run one preset with:
  scripts/run_demo_dynamic_agent_preset.py --preset-json ${OUTPUT_DIR}/${PRESET_PREFIX}_people_3_dynamic_agent_preset.json

Change density by choosing people_1..people_6 in that filename.
DONE
