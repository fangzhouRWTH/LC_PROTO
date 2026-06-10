#!/usr/bin/env python3
"""Build runnable people+vehicle preset JSON files for demo scenes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PEOPLE_CONFIG = REPO_ROOT / "configs" / "demo_people" / "tencent_dynamic_people_scenarios.json"
DEFAULT_AGENT_CONFIG = REPO_ROOT / "configs" / "demo_agents" / "tencent_dynamic_agent_scenarios.json"
DEFAULT_SCENARIOS = ("people_1", "people_2", "people_3", "people_4", "people_5", "people_6")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build dynamic-only runtime route JSONs and preset wrappers.",
    )
    parser.add_argument("--scene-usd", type=Path, required=True)
    parser.add_argument("--people-plan-dir", type=Path, required=True)
    parser.add_argument("--preset-prefix", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--people-config", type=Path, default=DEFAULT_PEOPLE_CONFIG)
    parser.add_argument("--agent-config", type=Path, default=DEFAULT_AGENT_CONFIG)
    parser.add_argument("--base-placement-plan-json", type=Path, default=None)
    parser.add_argument("--summary-json", type=Path, default=None)
    parser.add_argument("--scenario", action="append", dest="scenarios", default=[])
    parser.add_argument("--indent", type=int, default=2)
    return parser.parse_args(argv)


def _load_json(path: Path) -> dict[str, Any]:
    with path.expanduser().open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON must be an object: {path}")
    return value


def _repo_relative(path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _merge_settings(defaults: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(defaults)
    merged.update(override)
    return merged


def _people_actor_count(people_config: dict[str, Any], scenario: str) -> int:
    defaults = people_config.get("defaults") if isinstance(people_config.get("defaults"), dict) else {}
    scenarios = people_config.get("scenarios") if isinstance(people_config.get("scenarios"), dict) else {}
    raw = scenarios.get(scenario) if isinstance(scenarios.get(scenario), dict) else {}
    return int(raw.get("actor_count", defaults.get("actor_count", 0)) or 0)


def _runtime_env(settings: dict[str, Any], people_count: int) -> dict[str, str]:
    max_people = int(settings.get("pedestrian_max_actors", 40) or 40)
    max_people = max(max_people, people_count)
    return {
        "DYNAMIC_AGENT_BACKEND": str(settings.get("dynamic_agent_backend", "isaac_people_sumo")),
        "DYNAMIC_ROUTE_MODE": str(settings.get("route_mode", "once")),
        "DYNAMIC_MAX_PEDESTRIAN_ACTORS": str(max_people),
        "DYNAMIC_PEDESTRIAN_SPEED_MPS": str(settings.get("pedestrian_speed_mps", 0.8)),
        "DYNAMIC_MAX_VEHICLE_ACTORS": str(int(settings.get("max_vehicle_actors", 0) or 0)),
        "DYNAMIC_VEHICLES_PER_LINE": str(int(settings.get("vehicles_per_line", 1) or 1)),
        "DYNAMIC_VEHICLE_SPEED_MPS": str(settings.get("vehicle_speed_mps", 9.0)),
        "DYNAMIC_VEHICLE_SPAWN_INTERVAL_S": str(settings.get("vehicle_spawn_interval_s", 4.0)),
        "DYNAMIC_VEHICLE_VISUAL": str(settings.get("vehicle_visual", "asset")),
        "DYNAMIC_VEHICLE_ASSET_SCALE": str(settings.get("vehicle_asset_scale", 1.0)),
        "DYNAMIC_ISAAC_PEOPLE_IGNORE_SPAWN_TIME": str(settings.get("ignore_people_spawn_time", True)).lower(),
    }


def _build_preset(
    *,
    scenario: str,
    scene_usd: Path,
    people_plan: Path,
    dynamic_routes: Path,
    people_count: int,
    settings: dict[str, Any],
    base_plan: Path | None,
) -> dict[str, Any]:
    env = _runtime_env(settings, people_count)
    env["SCENE_USD"] = _repo_relative(scene_usd)
    env["DEMO_PEOPLE_SCENARIO"] = scenario
    env["DYNAMIC_ROUTES_JSON"] = _repo_relative(dynamic_routes)
    return {
        "schema_version": "simworld.demo_dynamic_agent_runtime_preset.v1",
        "scenario": scenario,
        "scene_usd": _repo_relative(scene_usd),
        "base_placement_plan_json": _repo_relative(base_plan) if base_plan else None,
        "placement_plan_json": _repo_relative(people_plan),
        "dynamic_routes_json": _repo_relative(dynamic_routes),
        "people": {
            "scenario": scenario,
            "visible_actor_count": people_count,
            "max_runtime_actors": int(env["DYNAMIC_MAX_PEDESTRIAN_ACTORS"]),
            "ignore_spawn_time": env["DYNAMIC_ISAAC_PEOPLE_IGNORE_SPAWN_TIME"] == "true",
        },
        "vehicles": {
            "max_vehicle_actors": int(env["DYNAMIC_MAX_VEHICLE_ACTORS"]),
            "vehicles_per_line": int(env["DYNAMIC_VEHICLES_PER_LINE"]),
            "speed_mps": float(env["DYNAMIC_VEHICLE_SPEED_MPS"]),
            "spawn_interval_s": float(env["DYNAMIC_VEHICLE_SPAWN_INTERVAL_S"]),
            "visual": env["DYNAMIC_VEHICLE_VISUAL"],
        },
        "environment": env,
        "run_command": "",
    }


def _dynamic_routes_payload(
    *,
    scenario: str,
    scene_usd: Path,
    people_plan_path: Path,
    people_plan: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "simworld.dynamic_routes.v1",
        "scenario": scenario,
        "scene_usd": _repo_relative(scene_usd),
        "source_placement_plan_json": _repo_relative(people_plan_path),
        "replace_existing": True,
        "pedestrian_routes": list(people_plan.get("pedestrian_routes") or []),
        "vehicle_routes": list(people_plan.get("vehicle_routes") or []),
        "vehicle_lanes": list(people_plan.get("vehicle_lanes") or []),
        "metadata": {
            "source": "demo_dynamic_agent_preset_builder",
            "note": "Dynamic-only route layer; does not include fixed asset placements.",
        },
    }


def _write_dynamic_routes_json(
    *,
    output_path: Path,
    scenario: str,
    scene_usd: Path,
    people_plan_path: Path,
    people_plan: dict[str, Any],
    indent: int,
) -> None:
    payload = _dynamic_routes_payload(
        scenario=scenario,
        scene_usd=scene_usd,
        people_plan_path=people_plan_path,
        people_plan=people_plan,
    )
    output_path.write_text(json.dumps(payload, indent=indent) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    people_config = _load_json(args.people_config)
    agent_config = _load_json(args.agent_config)
    defaults = agent_config.get("defaults") if isinstance(agent_config.get("defaults"), dict) else {}
    agent_scenarios = agent_config.get("scenarios") if isinstance(agent_config.get("scenarios"), dict) else {}
    scenarios = tuple(args.scenarios or DEFAULT_SCENARIOS)
    output_dir = args.output_dir.expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, Any]] = []
    for scenario in scenarios:
        people_plan = args.people_plan_dir.expanduser() / f"{args.preset_prefix}_{scenario}_placement_plan.json"
        if not people_plan.exists():
            raise FileNotFoundError(f"Missing generated people plan for {scenario}: {people_plan}")
        override = agent_scenarios.get(scenario) if isinstance(agent_scenarios.get(scenario), dict) else {}
        settings = _merge_settings(defaults, override)
        people_count = _people_actor_count(people_config, scenario)
        people_plan_payload = _load_json(people_plan)
        dynamic_routes_path = output_dir / f"{args.preset_prefix}_{scenario}_dynamic_routes.json"
        _write_dynamic_routes_json(
            output_path=dynamic_routes_path,
            scenario=scenario,
            scene_usd=args.scene_usd,
            people_plan_path=people_plan,
            people_plan=people_plan_payload,
            indent=args.indent,
        )
        preset = _build_preset(
            scenario=scenario,
            scene_usd=args.scene_usd,
            people_plan=people_plan,
            dynamic_routes=dynamic_routes_path,
            people_count=people_count,
            settings=settings,
            base_plan=args.base_placement_plan_json,
        )
        output_path = output_dir / f"{args.preset_prefix}_{scenario}_dynamic_agent_preset.json"
        preset["run_command"] = f"scripts/run_demo_dynamic_agent_preset.py --preset-json {_repo_relative(output_path)}"
        output_path.write_text(json.dumps(preset, indent=args.indent) + "\n", encoding="utf-8")
        summaries.append(
            {
                "scenario": scenario,
                "preset_json": _repo_relative(output_path),
                "placement_plan_json": _repo_relative(people_plan),
                "dynamic_routes_json": _repo_relative(dynamic_routes_path),
                "people_count": people_count,
                "max_vehicle_actors": preset["vehicles"]["max_vehicle_actors"],
                "vehicles_per_line": preset["vehicles"]["vehicles_per_line"],
                "vehicle_speed_mps": preset["vehicles"]["speed_mps"],
            }
        )
        print(
            f"{scenario}: people={people_count} vehicles={preset['vehicles']['max_vehicle_actors']} "
            f"per_line={preset['vehicles']['vehicles_per_line']} -> {output_path}"
        )

    if args.summary_json is not None:
        summary_path = args.summary_json.expanduser()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(
                {
                    "schema_version": "simworld.demo_dynamic_agent_runtime_summary.v1",
                    "scene_usd": _repo_relative(args.scene_usd),
                    "people_plan_dir": _repo_relative(args.people_plan_dir),
                    "output_dir": _repo_relative(output_dir),
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
