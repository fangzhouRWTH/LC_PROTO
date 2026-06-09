#!/usr/bin/env python3
"""Build fixed demo pedestrian placement plans from a base placement plan.

This is an offline demo-prep tool. Runtime should load the generated
placement-plan JSONs directly instead of rerunning route generation/rehearsal.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "simworld"))

from engine.demo_pedestrian_scenarios import (  # noqa: E402
    apply_demo_people_scenario,
    load_demo_people_config,
)

DEFAULT_SCENARIOS = (
    "people_1",
    "people_2",
    "people_3",
    "people_4",
    "people_5",
    "people_6",
)
DEFAULT_CONFIG = REPO_ROOT / "configs" / "demo_people" / "tencent_dynamic_people_scenarios.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "configs" / "demo_people" / "generated"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate fixed demo people preset placement plans.",
    )
    parser.add_argument(
        "--base-placement-plan-json",
        type=Path,
        required=True,
        help="Clean/main placement_output.json for the target parcel or scene.",
    )
    parser.add_argument(
        "--demo-people-config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Demo people scenario config. Default: {DEFAULT_CONFIG}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for generated preset plans. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--preset-prefix",
        default="tencent",
        help="Filename prefix, e.g. tencent -> tencent_people_3_placement_plan.json.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        default=[],
        help="Scenario to generate. Repeatable. Defaults to all people_* presets.",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=None,
        help="Optional path to write a machine-readable generation summary.",
    )
    parser.add_argument("--indent", type=int, default=2)
    return parser.parse_args(argv)


def _load_json(path: Path) -> dict[str, Any]:
    with path.expanduser().open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON must be an object: {path}")
    return value


def _clean_base_plan(plan: dict[str, Any]) -> dict[str, Any]:
    cleaned = copy.deepcopy(plan)
    cleaned.pop("pedestrian_demo_source_routes", None)
    cleaned.pop("demo_people_scenario_debug", None)
    debug = cleaned.get("debug")
    if isinstance(debug, dict):
        for key in list(debug):
            if key.startswith("demo_people_"):
                debug.pop(key, None)
    return cleaned


def _scenario_summary(plan: dict[str, Any], scenario: str, output_path: Path) -> dict[str, Any]:
    debug = plan.get("demo_people_scenario_debug") if isinstance(plan, dict) else {}
    if not isinstance(debug, dict):
        debug = {}
    rehearsal = debug.get("collision_rehearsal") if isinstance(debug.get("collision_rehearsal"), dict) else {}
    return {
        "scenario": scenario,
        "output_path": str(output_path),
        "placement_count": len(plan.get("placements") or []),
        "pedestrian_route_count": len(plan.get("pedestrian_routes") or []),
        "walkable_line_count": len(plan.get("pedestrian_walkable_lines") or []),
        "collision_rehearsal": {
            "enabled": rehearsal.get("enabled"),
            "unresolved_conflict_count": rehearsal.get("unresolved_conflict_count"),
            "inserted_detour_count": rehearsal.get("inserted_detour_count"),
            "delayed_route_count": rehearsal.get("delayed_route_count"),
            "max_applied_delay_s": rehearsal.get("max_applied_delay_s"),
            "min_separation_m": rehearsal.get("min_separation_m"),
        },
        "warnings": debug.get("warnings") or plan.get("warnings") or [],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    base_path = args.base_placement_plan_json.expanduser()
    config_path = args.demo_people_config.expanduser()
    output_dir = args.output_dir.expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    base_plan = _clean_base_plan(_load_json(base_path))
    config = load_demo_people_config(config_path)
    scenarios = tuple(args.scenarios or DEFAULT_SCENARIOS)

    summaries: list[dict[str, Any]] = []
    for scenario in scenarios:
        plan = apply_demo_people_scenario(base_plan, config, scenario_name=scenario)
        debug = plan.setdefault("debug", {})
        if isinstance(debug, dict):
            debug["demo_people_static_preset"] = True
            debug["demo_people_static_preset_source"] = str(base_path)
            debug["demo_people_static_preset_config"] = str(config_path)
            debug["demo_people_static_preset_scenario"] = scenario
        output_path = output_dir / f"{args.preset_prefix}_{scenario}_placement_plan.json"
        output_path.write_text(json.dumps(plan, indent=args.indent) + "\n", encoding="utf-8")
        summary = _scenario_summary(plan, scenario, output_path)
        summaries.append(summary)
        rehearsal = summary["collision_rehearsal"]
        print(
            f"{scenario}: routes={summary['pedestrian_route_count']} "
            f"placements={summary['placement_count']} "
            f"unresolved={rehearsal.get('unresolved_conflict_count')} "
            f"detours={rehearsal.get('inserted_detour_count')} "
            f"delayed={rehearsal.get('delayed_route_count')} "
            f"-> {output_path}"
        )

    if args.summary_json is not None:
        summary_path = args.summary_json.expanduser()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(
                {
                    "base_placement_plan_json": str(base_path),
                    "demo_people_config": str(config_path),
                    "output_dir": str(output_dir),
                    "preset_prefix": args.preset_prefix,
                    "scenarios": summaries,
                },
                indent=args.indent,
            )
            + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
