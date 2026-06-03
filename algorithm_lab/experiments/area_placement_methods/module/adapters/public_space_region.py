"""Convert parsed public-space region records to simworld.region_input.v1."""

from __future__ import annotations

import math
from typing import Any, Sequence

from generator import REGION_INPUT_SCHEMA


def _line_string_3d(points: Sequence[Sequence[float]]) -> dict[str, Any]:
    coords = [[float(p[0]), float(p[1]), float(p[2])] for p in points]
    return {"type": "LineString3D", "coordinates": coords}


def _dedupe_points(
    points: Sequence[Sequence[float]],
    *,
    tolerance: float = 1e-3,
) -> list[list[float]]:
    unique: list[list[float]] = []
    for point in points:
        candidate = [float(point[0]), float(point[1]), float(point[2])]
        if any(
            math.dist(candidate, existing) <= tolerance for existing in unique
        ):
            continue
        unique.append(candidate)
    return unique


def _ring_from_boundary_vertices(vertices: Sequence[Sequence[float]]) -> list[list[float]]:
    unique = _dedupe_points(vertices)
    if len(unique) < 3:
        raise ValueError("public space region needs at least 3 unique boundary vertices")

    ordered = _order_points_ccw_xy(unique)
    if math.dist(ordered[0], ordered[-1]) > 1e-3:
        ordered.append(ordered[0])
    return ordered


def _order_points_ccw_xy(points: list[list[float]]) -> list[list[float]]:
    if len(points) <= 1:
        return points

    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)

    def angle_key(point: list[float]) -> float:
        return math.atan2(point[1] - cy, point[0] - cx)

    return sorted(points, key=angle_key)


def _segment_line_from_vertices(vertices: Sequence[Sequence[float]]) -> list[list[float]]:
    unique = _dedupe_points(vertices)
    if len(unique) < 2:
        raise ValueError("segment mesh needs at least 2 unique vertices")
    if len(unique) == 2:
        return unique

    # Thin quad segment meshes: use the two points farthest apart.
    best_pair = (unique[0], unique[1])
    best_dist = -1.0
    for i, p0 in enumerate(unique):
        for p1 in unique[i + 1 :]:
            dist = math.dist(p0, p1)
            if dist > best_dist:
                best_dist = dist
                best_pair = (p0, p1)
    return [best_pair[0], best_pair[1]]


def public_space_region_to_region_input(region: dict[str, Any]) -> dict[str, Any]:
    """
    Build ``simworld.region_input.v1`` from a plain dict (no USD / Isaac).

    Expected keys:
      region_id, public_space_type, ratio_dynamic_static,
      boundary_vertices, segments[], asset_has_set[] (optional)
    """
    public_space_type = str(region.get("public_space_type") or "").strip()
    if not public_space_type:
        raise ValueError("public_space_type is required")

    boundary_vertices = region.get("boundary_vertices") or []
    segments_in = region.get("segments") or []
    if not segments_in:
        raise ValueError(
            f"region {region.get('region_id')} has no boundary segments; "
            "author segment child prims in USD"
        )

    segments = []
    for item in segments_in:
        if not isinstance(item, dict):
            continue
        endpoints = item.get("coordinates")
        if endpoints is None:
            endpoints = _segment_line_from_vertices(item.get("vertices") or [])
        if len(endpoints) < 2:
            continue
        segments.append(
            {
                "segment_id": int(item.get("segment_id") or len(segments) + 1),
                "geometry": _line_string_3d(endpoints[:2]),
                "boundary_type": str(item.get("boundary_type") or "block_boundary_other"),
            }
        )

    if not segments:
        raise ValueError(f"region {region.get('region_id')} has no valid segments")

    asset_has_set = []
    for index, item in enumerate(region.get("asset_has_set") or [], start=1):
        if not isinstance(item, dict):
            continue
        coords = item.get("coordinates")
        if coords is None:
            line = _segment_line_from_vertices(item.get("vertices") or [])
            coords = line
        asset_has_set.append(
            {
                "asset_has_set_id": int(item.get("asset_has_set_id") or index),
                "asset_has_set_type": str(
                    item.get("asset_has_set_type") or "arcade_column"
                ),
                "geometry": _line_string_3d(coords),
            }
        )

    region_id = str(
        region.get("region_id")
        or region.get("prim_path")
        or region.get("raw_name")
        or "unknown_region"
    )

    payload: dict[str, Any] = {
        "schema_version": REGION_INPUT_SCHEMA,
        "region_id": region_id,
        "public_space_type": public_space_type,
        "public_space_geometry": _line_string_3d(_ring_from_boundary_vertices(boundary_vertices)),
        "public_space_segments": segments,
        "ratio_dynamic_static": float(region.get("ratio_dynamic_static", 0.36)),
        "metadata": {
            "source_prim_path": region.get("prim_path"),
            "raw_name": region.get("raw_name"),
            "coordinate_frame": "world_xyz",
            "parsed_from_usd": True,
        },
    }
    if asset_has_set:
        payload["asset_has_set"] = asset_has_set
    return payload
