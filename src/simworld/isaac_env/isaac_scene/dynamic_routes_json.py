"""Load dynamic-only route JSON into parsed scene stats."""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from . import scene_parser as parser


@dataclass
class DynamicRoutesJsonResult:
    path: pathlib.Path
    replace_existing: bool = True
    pedestrian_route_count: int = 0
    vehicle_route_count: int = 0
    vehicle_lane_count: int = 0
    warnings: list[str] = field(default_factory=list)


def load_dynamic_routes_json(path: str | pathlib.Path) -> dict[str, Any]:
    route_path = pathlib.Path(path).expanduser()
    with route_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Dynamic routes JSON must be an object: {route_path}")
    return payload


def apply_dynamic_routes_json(
    stats: "parser.SceneStats",
    path: str | pathlib.Path,
) -> DynamicRoutesJsonResult:
    route_path = pathlib.Path(path).expanduser()
    payload = load_dynamic_routes_json(route_path)
    replace_existing = _bool_field(payload, "replace_existing", True)
    result = DynamicRoutesJsonResult(path=route_path, replace_existing=replace_existing)

    pedestrian_routes = _coerce_path_records(
        payload.get("pedestrian_routes") or [],
        default_category="route",
        fallback_raw_prefix="dynamic_pedestrian_route",
        warnings=result.warnings,
    )
    vehicle_routes = _coerce_path_records(
        payload.get("vehicle_routes") or [],
        default_category="line",
        fallback_raw_prefix="dynamic_vehicle_line",
        warnings=result.warnings,
    )
    vehicle_lanes = _coerce_area_records(
        payload.get("vehicle_lanes") or [],
        default_category="lane",
        fallback_raw_prefix="dynamic_vehicle_lane",
        warnings=result.warnings,
    )

    if replace_existing:
        stats.pedestrian_spawn_points.clear()
        stats.pedestrian_goal_points.clear()
        stats.pedestrian_routes.clear()
        stats.pedestrian_zones.clear()
        stats.vehicle_spawn_points.clear()
        stats.vehicle_goal_points.clear()
        stats.vehicle_routes.clear()
        stats.vehicle_lanes.clear()

    stats.pedestrian_routes.extend(pedestrian_routes)
    stats.vehicle_routes.extend(vehicle_routes)
    stats.vehicle_lanes.extend(vehicle_lanes)

    result.pedestrian_route_count = len(pedestrian_routes)
    result.vehicle_route_count = len(vehicle_routes)
    result.vehicle_lane_count = len(vehicle_lanes)
    return result


def _bool_field(payload: dict[str, Any], key: str, default: bool) -> bool:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _as_vertices(value: Any, *, allow_polygon: bool = False) -> list[list[float]]:
    if isinstance(value, dict):
        candidate_keys = (
            ("vertices", "waypoints", "route")
            if not allow_polygon
            else ("vertices", "polygon", "waypoints", "route")
        )
        for key in candidate_keys:
            raw = value.get(key)
            if raw is not None:
                value = raw
                break
    vertices: list[list[float]] = []
    for vertex in value or []:
        if isinstance(vertex, dict):
            vertex = [vertex.get("x"), vertex.get("y"), vertex.get("z", 0.0)]
        if len(vertex) < 3:
            raise ValueError(f"vertex must have at least 3 values, got {vertex!r}")
        vertices.append([float(vertex[0]), float(vertex[1]), float(vertex[2])])
    return vertices


def _coerce_path_records(
    raw_items: Any,
    *,
    default_category: str,
    fallback_raw_prefix: str,
    warnings: list[str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, item in enumerate(raw_items if isinstance(raw_items, list) else []):
        if not isinstance(item, dict):
            warnings.append(f"Skipping non-object dynamic route at index {index}")
            continue
        try:
            vertices = _as_vertices(item)
        except Exception as exc:
            warnings.append(f"Skipping dynamic route at index {index}: {exc}")
            continue
        if len(vertices) < 2:
            warnings.append(
                f"Skipping dynamic route at index {index}: needs at least 2 vertices"
            )
            continue
        record = dict(item)
        record["vertices"] = vertices
        record.setdefault("category", default_category)
        record.setdefault("index", f"{index + 1:03d}")
        record.setdefault("raw_name", f"{fallback_raw_prefix}_{index + 1:03d}")
        records.append(record)
    return records


def _coerce_area_records(
    raw_items: Any,
    *,
    default_category: str,
    fallback_raw_prefix: str,
    warnings: list[str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, item in enumerate(raw_items if isinstance(raw_items, list) else []):
        if not isinstance(item, dict):
            warnings.append(f"Skipping non-object dynamic area at index {index}")
            continue
        try:
            vertices = _as_vertices(item, allow_polygon=True)
        except Exception as exc:
            warnings.append(f"Skipping dynamic area at index {index}: {exc}")
            continue
        if len(vertices) < 3:
            warnings.append(
                f"Skipping dynamic area at index {index}: needs at least 3 vertices"
            )
            continue
        record = dict(item)
        record["vertices"] = vertices
        record.setdefault("category", default_category)
        record.setdefault("index", f"{index + 1:03d}")
        record.setdefault("raw_name", f"{fallback_raw_prefix}_{index + 1:03d}")
        records.append(record)
    return records
