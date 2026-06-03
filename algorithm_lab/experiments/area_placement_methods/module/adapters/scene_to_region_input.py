"""Build simworld.region_input.v1 from scene-like data (no USD imports)."""

from __future__ import annotations

from typing import Any, Sequence

from generator import REGION_INPUT_SCHEMA

# Proto boundary types for block_entrance rectangle (sample_data.md first example).
_BLOCK_ENTRANCE_BOUNDARIES = (
    "block_boundary_primary",
    "street_boundary_primary",
    "street_boundary_primary",
    "block_boundary_other",
)


def _line_string_3d(points: Sequence[Sequence[float]]) -> dict[str, Any]:
    coords = [[float(p[0]), float(p[1]), float(p[2])] for p in points]
    return {"type": "LineString3D", "coordinates": coords}


def block_entrance_region_input_from_rectangle(
    *,
    min_xy: tuple[float, float],
    max_xy: tuple[float, float],
    z: float = 0.0,
    region_id: str = "placeholder_area_publicspace_001",
    ratio_dynamic_static: float = 0.7,
) -> dict[str, Any]:
    """
    Synthetic block_entrance region matching proto/01_block_entrance_01.json layout.

    Rectangle from (min_x, min_y) to (max_x, max_y) in world XY.
    """
    x0, y0 = float(min_xy[0]), float(min_xy[1])
    x1, y1 = float(max_xy[0]), float(max_xy[1])

    ring = [
        (x0, y0, z),
        (x1, y0, z),
        (x1, y1, z),
        (x0, y1, z),
        (x0, y0, z),
    ]
    edges = [
        (ring[0], ring[1]),
        (ring[1], ring[2]),
        (ring[2], ring[3]),
        (ring[3], ring[4]),
    ]

    segments = []
    for segment_id, (boundary_type, (p0, p1)) in enumerate(
        zip(_BLOCK_ENTRANCE_BOUNDARIES, edges),
        start=1,
    ):
        segments.append(
            {
                "segment_id": segment_id,
                "geometry": _line_string_3d([p0, p1]),
                "boundary_type": boundary_type,
            }
        )

    return {
        "schema_version": REGION_INPUT_SCHEMA,
        "region_id": region_id,
        "public_space_type": "block_entrance",
        "public_space_geometry": _line_string_3d(ring),
        "public_space_segments": segments,
        "ratio_dynamic_static": float(ratio_dynamic_static),
        "metadata": {
            "coordinate_frame": "world_xyz",
            "synthetic": True,
        },
    }


def placeholder_area_dict_to_region_input(
    area: dict[str, Any],
    *,
    public_space_type: str,
    ratio_dynamic_static: float = 0.36,
    segments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Minimal adapter from a dict resembling SceneStats PlaceholderArea.

    Requires ``vertices`` (world XYZ). ``segments`` must be supplied until
    Phase 5 mesh-edge inference exists.
    """
    vertices = area.get("vertices") or []
    if len(vertices) < 3:
        raise ValueError("placeholder area needs at least 3 vertices")

    ring = list(vertices)
    first = ring[0]
    last = ring[-1]
    if any(abs(float(first[i]) - float(last[i])) > 1e-6 for i in range(3)):
        ring.append(first)

    if segments is None:
        raise ValueError(
            "segments are required until USD segment prims are parsed (Phase 5)"
        )

    region_id = area.get("prim_path") or area.get("raw_name") or "unknown_region"

    return {
        "schema_version": REGION_INPUT_SCHEMA,
        "region_id": str(region_id),
        "public_space_type": public_space_type,
        "public_space_geometry": _line_string_3d(ring),
        "public_space_segments": segments,
        "ratio_dynamic_static": float(ratio_dynamic_static),
        "metadata": {
            "source_prim_path": area.get("prim_path"),
            "raw_name": area.get("raw_name"),
            "coordinate_frame": "world_xyz",
        },
    }
