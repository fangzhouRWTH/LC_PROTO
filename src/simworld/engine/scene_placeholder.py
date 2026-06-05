"""Placeholder disposition helpers (no Isaac imports)."""

from __future__ import annotations


def normalize_placeholder_disposition(value) -> str:
    normalized = str(value or "hidden").strip().lower().replace("-", "_")
    if normalized in {"hidden", "hide", "off", "false", "0", "invisible"}:
        return "hidden"
    if normalized in {"visible", "show", "on", "true", "1"}:
        return "visible"
    if normalized in {"remove", "delete", "removed", "deleted"}:
        return "remove"
    raise ValueError(
        "placeholder_disposition must be 'hidden', 'visible', or 'remove', "
        f"got {value!r}"
    )


def collect_placeholder_prim_paths(stats) -> list[str]:
    """Collect every placeholder prim path recorded during scene parse."""
    paths: list[str] = []
    seen: set[str] = set()

    def add(path: str) -> None:
        if path and path not in seen:
            seen.add(path)
            paths.append(path)

    for path in getattr(stats, "placeholder_prim_paths", []) or []:
        add(str(path))

    for field_name in (
        "placeholder_areas",
        "pedestrian_spawn_points",
        "pedestrian_goal_points",
        "pedestrian_routes",
        "pedestrian_zones",
        "vehicle_spawn_points",
        "vehicle_goal_points",
        "vehicle_routes",
        "vehicle_lanes",
        "sidewalk_areas",
        "crosswalk_areas",
        "public_space_regions",
        "public_space_boundary_segments",
        "public_space_asset_has_sets",
    ):
        for item in getattr(stats, field_name, []) or []:
            add(str(getattr(item, "prim_path", "") or ""))

    return sorted(paths, key=lambda path: path.count("/"), reverse=True)
