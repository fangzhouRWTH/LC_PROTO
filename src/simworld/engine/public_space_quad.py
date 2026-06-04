"""Quad corner extraction for public-space regions (no Isaac imports)."""

from __future__ import annotations

import math
from typing import Sequence


def dedupe_points(
    points: Sequence[Sequence[float]],
    *,
    tolerance: float = 1e-3,
) -> list[list[float]]:
    unique: list[list[float]] = []
    for point in points:
        candidate = [float(point[0]), float(point[1]), float(point[2])]
        if any(math.dist(candidate, existing) <= tolerance for existing in unique):
            continue
        unique.append(candidate)
    return unique


def order_points_ccw_xy(points: list[list[float]]) -> list[list[float]]:
    if len(points) <= 1:
        return points

    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)

    def angle_key(point: list[float]) -> float:
        return math.atan2(point[1] - cy, point[0] - cx)

    return sorted(points, key=angle_key)


def extract_quad_corners(vertices: Sequence[Sequence[float]]) -> list[list[float]]:
    """Return four CCW-ordered corners from a quad region mesh."""
    unique = dedupe_points(vertices)
    if len(unique) == 4:
        return order_points_ccw_xy(unique)

    if len(unique) > 4:
        ordered = order_points_ccw_xy(unique)
        if len(ordered) >= 4:
            return ordered[:4]

    raise ValueError(
        f"expected a quad (4 unique corners), got {len(unique)} unique vertices"
    )
