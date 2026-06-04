"""Public-space geometry helpers (re-export + segment synthesis entry points)."""

from __future__ import annotations

from typing import Sequence

from engine.public_space_quad import dedupe_points, extract_quad_corners, order_points_ccw_xy
from engine.public_space_segment_synthesis import (
    build_synthetic_boundary_segment_records,
    synthesize_boundary_segments_from_quad,
)

__all__ = [
    "dedupe_points",
    "order_points_ccw_xy",
    "extract_quad_corners",
    "infer_boundary_segments_from_quad_vertices",
    "build_inferred_boundary_segment_records",
]


def infer_boundary_segments_from_quad_vertices(
    vertices: Sequence[Sequence[float]],
    public_space_type: str = "block_entrance",
    *,
    boundary_type_hint: str = "",
    region_seed: str = "",
) -> list[dict[str, object]]:
    """Build four boundary segment records from a quad (placement-aware assignment)."""
    return synthesize_boundary_segments_from_quad(
        vertices,
        public_space_type,
        boundary_type_hint=boundary_type_hint,
        region_seed=region_seed,
    )


def build_inferred_boundary_segment_records(
    region_prim_path: str,
    boundary_vertices: Sequence[Sequence[float]],
    public_space_type: str = "block_entrance",
    *,
    boundary_type_hint: str = "",
) -> list[dict[str, object]]:
    """Segment dicts ready to become ``PlaceholderBoundarySegment``."""
    return build_synthetic_boundary_segment_records(
        region_prim_path,
        boundary_vertices,
        public_space_type,
        boundary_type_hint=boundary_type_hint,
    )
