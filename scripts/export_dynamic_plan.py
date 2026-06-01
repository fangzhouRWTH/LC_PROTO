#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from engine.dynamic import DynamicPlanConfig, build_dynamic_actor_plan


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    return value


def _to_namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(
            **{str(key): _to_namespace(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return [_to_namespace(item) for item in value]
    return value


def _load_scene_stats(payload: dict[str, Any]) -> Any:
    raw_scene_stats = payload.get("scene_stats", payload)
    return _to_namespace(raw_scene_stats)


def _load_plan_config(payload: dict[str, Any]) -> DynamicPlanConfig:
    raw = payload.get("plan_config") or {}
    return DynamicPlanConfig(
        max_pedestrian_actors=int(raw.get("max_pedestrian_actors", 1)),
        max_vehicle_actors=int(raw.get("max_vehicle_actors", 1)),
        pedestrian_speed_mps=float(raw.get("pedestrian_speed_mps", 1.2)),
        vehicle_speed_mps=float(raw.get("vehicle_speed_mps", 4.0)),
        default_spawn_time_s=float(raw.get("default_spawn_time_s", 0.0)),
        pedestrian_radius_m=float(raw.get("pedestrian_radius_m", 0.35)),
        pedestrian_height_m=float(raw.get("pedestrian_height_m", 1.7)),
        vehicle_length_m=float(raw.get("vehicle_length_m", 4.5)),
        vehicle_width_m=float(raw.get("vehicle_width_m", 1.8)),
        vehicle_height_m=float(raw.get("vehicle_height_m", 1.6)),
        default_route_mode=str(raw.get("default_route_mode", "loop")),
    )


def build_export_payload(payload: dict[str, Any]) -> dict[str, Any]:
    scene_stats = _load_scene_stats(payload)
    plan_config = _load_plan_config(payload)
    plan = build_dynamic_actor_plan(scene_stats, plan_config)
    return {
        "schema_version": "dynamic_scene_plan.v0",
        **_to_jsonable(plan),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export DynamicScenePlan JSON from scene_stats input."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with args.input.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    export_payload = build_export_payload(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(export_payload, handle, indent=2)
        handle.write("\n")

    actor_count = len(export_payload.get("actors") or [])
    warning_count = len(export_payload.get("warnings") or [])
    print(
        f"Wrote DynamicScenePlan with {actor_count} actor(s) "
        f"and {warning_count} warning(s) to {args.output}"
    )


if __name__ == "__main__":
    main()
