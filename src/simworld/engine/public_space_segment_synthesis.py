"""Synthesize quad boundary segments for placement (no Isaac imports)."""

from __future__ import annotations

import hashlib
from typing import Sequence

from engine.public_space_quad import extract_quad_corners

# Four-edge templates derived from proto gold samples (steps 1–5 friendly).
QUAD_BOUNDARY_TEMPLATES: dict[str, list[str]] = {
    "block_entrance": [
        "block_boundary_primary",
        "street_boundary_primary",
        "street_boundary_primary",
        "block_boundary_other",
    ],
    "city_street_roofless": [
        # step5 `_street_boundary_zones` pairs static zones with *block* edges;
        # need two block_boundary_* sides + two street sides (not block_entrance).
        "block_boundary_primary",
        "street_boundary_primary",
        "street_boundary_primary",
        "block_boundary_other",
    ],
    "city_street_roof": [
        "street_boundary_secondary",
        "street_boundary_primary",
        "building_wall",
        "yard_boundary",
    ],
    "city_yard_roof": [
        "block_boundary_primary",
        "street_boundary_primary",
        "yard_boundary",
        "building_entrance_main",
    ],
    "city_yard_roofless": [
        "block_boundary_primary",
        "block_boundary_secondary",
        "block_entrance",
        "street_boundary_primary",
    ],
    "building_entrance": [
        "building_other_type",
        "building_entrance_main",
        "building_wall",
        "street_boundary_primary",
    ],
}

# Heuristic weights for choosing template rotation (proxy for placement yield).
_TEMPLATE_SCORE_WEIGHTS: dict[str, dict[str, int]] = {
    "block_entrance": {
        "street_boundary_primary": 3,
        "block_boundary_primary": 2,
        "block_boundary_other": 2,
        "block_entrance": 4,
    },
    "city_street_roofless": {
        "street_boundary_primary": 4,
        "street_boundary_secondary": 2,
        "block_boundary_primary": 6,
        "block_boundary_other": 6,
        "block_boundary_secondary": 4,
    },
    "city_street_roof": {
        "street_boundary_primary": 3,
        "street_boundary_secondary": 2,
        "yard_boundary": 2,
        "building_wall": 1,
    },
    "city_yard_roof": {
        "street_boundary_primary": 3,
        "yard_boundary": 3,
        "building_entrance_main": 3,
        "block_boundary_primary": 2,
    },
    "city_yard_roofless": {
        "street_boundary_primary": 3,
        "yard_boundary": 3,
        "block_entrance": 3,
        "block_boundary_primary": 2,
        "block_boundary_secondary": 2,
    },
    "building_entrance": {
        "building_entrance_main": 5,
        "building_wall": 3,
        "building_other_type": 2,
        "street_boundary_primary": 2,
    },
}

# Preferred compass edge for a boundary hint (max x, min x, max y, min y).
_HINT_EDGE_PICKER: dict[str, str] = {
    "street_boundary_primary": "max_x",
    "street_boundary_secondary": "max_y",
    "block_boundary_primary": "min_x",
    "block_boundary_other": "min_y",
    "block_boundary_secondary": "min_x",
    "block_entrance": "max_y",
    "building_entrance_main": "min_y",
    "building_wall": "min_y",
    "building_other_type": "min_x",
    "yard_boundary": "max_y",
    "block_other_type": "min_x",
}


def _edge_midpoints(corners: list[list[float]]) -> list[list[float]]:
    mids: list[list[float]] = []
    for index in range(4):
        p0 = corners[index]
        p1 = corners[(index + 1) % 4]
        mids.append(
            [
                (p0[0] + p1[0]) / 2.0,
                (p0[1] + p1[1]) / 2.0,
                (p0[2] + p1[2]) / 2.0,
            ]
        )
    return mids


def _pick_edge_index(midpoints: list[list[float]], picker: str) -> int:
    if picker == "max_x":
        return max(range(4), key=lambda i: midpoints[i][0])
    if picker == "min_x":
        return min(range(4), key=lambda i: midpoints[i][0])
    if picker == "max_y":
        return max(range(4), key=lambda i: midpoints[i][1])
    if picker == "min_y":
        return min(range(4), key=lambda i: midpoints[i][1])
    return 0


def _rotate_template(template: list[str], offset: int) -> list[str]:
    offset %= len(template)
    return template[offset:] + template[:offset]


def _score_template(public_space_type: str, boundary_types: list[str]) -> int:
    weights = _TEMPLATE_SCORE_WEIGHTS.get(public_space_type, {})
    score = sum(weights.get(item, 1) for item in boundary_types)
    if public_space_type == "city_street_roofless":
        block_edges = sum(
            1
            for item in boundary_types
            if item.startswith("block_boundary")
        )
        score += block_edges * 8
    return score


def _deterministic_rotation(region_seed: str, public_space_type: str, num_options: int) -> int:
    digest = hashlib.sha256(f"{region_seed}|{public_space_type}".encode()).hexdigest()
    return int(digest[:8], 16) % max(1, num_options)


def _assign_with_hint(
    template: list[str],
    *,
    boundary_type_hint: str,
    edge_index: int,
) -> list[str]:
    pool = list(template)
    if boundary_type_hint in pool:
        pool.remove(boundary_type_hint)
    assignment = [""] * 4
    assignment[edge_index] = boundary_type_hint
    pool_index = 0
    for index in range(4):
        if assignment[index]:
            continue
        assignment[index] = pool[pool_index % len(pool)]
        pool_index += 1
    return assignment


def choose_quad_boundary_types(
    corners: list[list[float]],
    public_space_type: str,
    *,
    boundary_type_hint: str = "",
    region_seed: str = "",
) -> list[str]:
    """Return four boundary_type values aligned CCW with quad edges."""
    template = list(
        QUAD_BOUNDARY_TEMPLATES.get(
            public_space_type,
            QUAD_BOUNDARY_TEMPLATES["block_entrance"],
        )
    )
    midpoints = _edge_midpoints(corners)

    if boundary_type_hint:
        picker = _HINT_EDGE_PICKER.get(boundary_type_hint, "min_y")
        edge_index = _pick_edge_index(midpoints, picker)
        return _assign_with_hint(
            template,
            boundary_type_hint=boundary_type_hint,
            edge_index=edge_index,
        )

    best_score = -1
    best_types: list[str] = template
    best_rotations: list[int] = []
    for rotation in range(4):
        candidate = _rotate_template(template, rotation)
        score = _score_template(public_space_type, candidate)
        if score > best_score:
            best_score = score
            best_rotations = [rotation]
        elif score == best_score:
            best_rotations.append(rotation)

    chosen = best_rotations[
        _deterministic_rotation(region_seed, public_space_type, len(best_rotations))
    ]
    return _rotate_template(template, chosen)


def synthesize_boundary_segments_from_quad(
    vertices: Sequence[Sequence[float]],
    public_space_type: str,
    *,
    boundary_type_hint: str = "",
    region_seed: str = "",
) -> list[dict[str, object]]:
    """Build four segment dicts with placement-friendly boundary_type assignment."""
    corners = extract_quad_corners(vertices)
    boundary_types = choose_quad_boundary_types(
        corners,
        public_space_type,
        boundary_type_hint=boundary_type_hint,
        region_seed=region_seed,
    )

    segments: list[dict[str, object]] = []
    for index in range(4):
        p0 = corners[index]
        p1 = corners[(index + 1) % 4]
        segments.append(
            {
                "segment_id": index + 1,
                "boundary_type": boundary_types[index],
                "vertices": [p0, p1],
            }
        )
    return segments


def build_synthetic_boundary_segment_records(
    region_prim_path: str,
    boundary_vertices: Sequence[Sequence[float]],
    public_space_type: str,
    *,
    boundary_type_hint: str = "",
) -> list[dict[str, object]]:
    """Segment dicts for parser / USD patch (runtime or persisted)."""
    inferred = synthesize_boundary_segments_from_quad(
        boundary_vertices,
        public_space_type,
        boundary_type_hint=boundary_type_hint,
        region_seed=region_prim_path,
    )
    records: list[dict[str, object]] = []
    for item in inferred:
        segment_id = int(item["segment_id"])
        records.append(
            {
                "vertices": item["vertices"],
                "prim_path": f"{region_prim_path}/placeholder_segment_edge_{segment_id:02d}",
                "raw_name": f"placeholder_segment_edge_{segment_id:02d}",
                "index": f"{segment_id:02d}",
                "segment_id": segment_id,
                "boundary_type": str(item["boundary_type"]),
                "parent_region_prim_path": region_prim_path,
            }
        )
    return records
