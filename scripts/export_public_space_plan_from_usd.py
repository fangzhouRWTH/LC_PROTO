#!/usr/bin/env python3
"""Offline USD -> public-space placement plan exporter.

This script is intended to run under Isaac Python. It parses public-space
placeholders from a USD scene without launching the full LC_PROTO simulation,
then writes the clean/base placement_output JSON used by demo preset builders.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a clean public-space placement plan from a USD scene.",
    )
    parser.add_argument("--scene-usd", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path, default=None)
    parser.add_argument("--steps", default="1,2,3,4,5")
    parser.add_argument("--headless", default="true", choices=("true", "false"))
    parser.add_argument("--indent", type=int, default=2)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def _parse_steps(value: str) -> tuple[int, ...]:
    steps: list[int] = []
    for raw in str(value or "").split(","):
        raw = raw.strip()
        if raw:
            steps.append(int(raw))
    return tuple(steps or (1, 2, 3, 4, 5))


def _serialize_placeholder_path(item: Any) -> dict[str, Any]:
    return {
        "vertices": [list(vertex) for vertex in getattr(item, "vertices", []) or []],
        "prim_path": str(getattr(item, "prim_path", "") or ""),
        "raw_name": str(getattr(item, "raw_name", "") or ""),
        "category": str(getattr(item, "category", "") or ""),
        "index": str(getattr(item, "index", "") or ""),
    }


def _serialize_placeholder_area(item: Any) -> dict[str, Any]:
    return {
        "vertices": [list(vertex) for vertex in getattr(item, "vertices", []) or []],
        "prim_path": str(getattr(item, "prim_path", "") or ""),
        "raw_name": str(getattr(item, "raw_name", "") or ""),
        "category": str(getattr(item, "category", "") or ""),
        "index": str(getattr(item, "index", "") or ""),
    }


def _attach_dynamic_vehicle_records(plan: dict[str, Any], stats: Any) -> None:
    plan["vehicle_routes"] = [
        _serialize_placeholder_path(item)
        for item in getattr(stats, "vehicle_routes", []) or []
    ]
    plan["vehicle_lanes"] = [
        _serialize_placeholder_area(item)
        for item in getattr(stats, "vehicle_lanes", []) or []
    ]


class _OfflineOmniUsd:
    def __init__(self, usd_module: Any, usd_geom_module: Any):
        self._usd = usd_module
        self._usd_geom = usd_geom_module
        self._cache = usd_geom_module.XformCache(usd_module.TimeCode.Default())

    def get_world_transform_matrix(self, prim: Any) -> Any:
        return self._cache.GetLocalToWorldTransform(prim)


class _OfflineIsaacContext:
    def __init__(self) -> None:
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdPhysics

        self.pxr_gf = Gf
        self.pxr_Sdf = Sdf
        self.pxr_usd = Usd
        self.pxr_usd_geom = UsdGeom
        self.pxr_usd_lux = UsdLux
        self.pxr_usd_physics = UsdPhysics
        self.omni_usd = _OfflineOmniUsd(Usd, UsdGeom)


def _install_offline_context() -> None:
    from isaac_env.isaac_adaptor import isaac_context as iscctx

    iscctx._isaac_context = _OfflineIsaacContext()


def _summarize_stats(stats: Any, plan: dict[str, Any], scene_usd: Path) -> dict[str, Any]:
    return {
        "schema_version": "simworld.public_space_base_plan_summary.v1",
        "scene_usd": str(scene_usd),
        "visited_prims": int(getattr(stats, "visited", 0)),
        "matched_rules": int(getattr(stats, "matched", 0)),
        "public_space_region_count": len(getattr(stats, "public_space_regions", []) or []),
        "public_space_parse_warnings": list(getattr(stats, "public_space_parse_warnings", []) or []),
        "placement_count": len(plan.get("placements") or []),
        "pedestrian_walkable_line_count": len(plan.get("pedestrian_walkable_lines") or []),
        "pedestrian_route_count": len(plan.get("pedestrian_routes") or []),
        "dynamic_zone_count": len(plan.get("dynamic_zones") or []),
        "static_zone_count": len(plan.get("static_zones") or []),
        "vehicle_route_count": len(getattr(stats, "vehicle_routes", []) or []),
        "vehicle_lane_count": len(getattr(stats, "vehicle_lanes", []) or []),
        "vehicle_spawn_count": len(getattr(stats, "vehicle_spawn_points", []) or []),
        "vehicle_goal_count": len(getattr(stats, "vehicle_goal_points", []) or []),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    scene_usd = args.scene_usd.expanduser().resolve()
    if not scene_usd.exists():
        raise FileNotFoundError(scene_usd)

    sys.path.insert(0, str(REPO_ROOT / "src" / "simworld"))

    from isaacsim import SimulationApp

    app = SimulationApp({"headless": args.headless == "true"})
    try:
        _install_offline_context()
        from pxr import Usd
        from isaac_env.isaac_scene import scene_parser
        from isaac_env.isaac_scene.scene_public_space import (
            build_placement_plan_from_parsed_regions,
        )
        from engine import area_placement_bridge

        stage = Usd.Stage.Open(str(scene_usd))
        if stage is None:
            raise RuntimeError(f"Failed to open USD stage: {scene_usd}")

        stats = scene_parser.process_stage_by_naming_rules(
            stage,
            verbose=False,
            print_summary=not args.quiet,
        )
        plan = build_placement_plan_from_parsed_regions(
            stats,
            steps=_parse_steps(args.steps),
        )
        _attach_dynamic_vehicle_records(plan, stats)
        debug = plan.setdefault("debug", {})
        if isinstance(debug, dict):
            debug["source_scene_usd"] = str(scene_usd)
            debug["exported_by"] = "scripts/export_public_space_plan_from_usd.py"

        output = args.output.expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        area_placement_bridge.write_json(output, plan)

        summary = _summarize_stats(stats, plan, scene_usd)
        if args.summary_json is not None:
            summary_path = args.summary_json.expanduser()
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(
                json.dumps(summary, indent=args.indent) + "\n",
                encoding="utf-8",
            )
        print(
            f"[OK] Exported base placement plan: {output} "
            f"(regions={summary['public_space_region_count']}, "
            f"routes={summary['pedestrian_route_count']}, "
            f"vehicle_lines={summary['vehicle_route_count']})"
        )
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
