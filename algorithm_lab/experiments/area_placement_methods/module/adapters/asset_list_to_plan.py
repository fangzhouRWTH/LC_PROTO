"""Convert proto layout result to simworld.placement_output.v1."""

from __future__ import annotations

import re
from typing import Any

PLACEMENT_OUTPUT_SCHEMA = "simworld.placement_output.v1"

# Resolved at runtime as UsdGeom.Cube when use_dummy_assets=True (no external USD).
DEFAULT_FALLBACK_ASSET_NAME = "isaac_builtin_placeholder"
# city_street_roof intentionally produces zero assets in proto step 5.
_TYPES_WITHOUT_FALLBACK = frozenset({"city_street_roof"})


def _region_slug(region_id: str) -> str:
    name = str(region_id or "region").rstrip("/").split("/")[-1]
    prefix = "placeholder_area_publicspace_"
    if name.startswith(prefix):
        name = name[len(prefix) :]
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_")
    return slug[:48] or "region"


def _usd_safe_placement_token(token: str) -> str:
    """USD prim path elements must not start with a digit."""
    cleaned = str(token or "").strip()
    if cleaned and cleaned[0].isdigit():
        return f"ps_{cleaned}"
    return cleaned or "placement"


def _placement_id(asset_id: Any, index: int, *, region_id: str = "") -> str:
    if asset_id is not None:
        base = f"asset_{asset_id:04d}" if isinstance(asset_id, int) else f"asset_{asset_id}"
    else:
        base = f"asset_{index:04d}"
    slug = _region_slug(region_id)
    if slug and slug != "region":
        return _usd_safe_placement_token(f"{slug}_{base}")
    return _usd_safe_placement_token(base)


def _centroid_from_geometry(geometry: dict[str, Any] | None) -> list[float]:
    """Average of polygon/line coordinates; used when asset_list is empty."""
    coords = (geometry or {}).get("coordinates") or []
    points: list[list[float]] = []
    for item in coords:
        if not isinstance(item, (list, tuple)):
            continue
        if len(item) >= 3:
            points.append([float(item[0]), float(item[1]), float(item[2])])
        elif len(item) >= 2:
            points.append([float(item[0]), float(item[1]), 0.0])
    if not points:
        return [0.0, 0.0, 0.0]
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    if not points:
        return [0.0, 0.0, 0.0]
    count = float(len(points))
    return [
        sum(p[0] for p in points) / count,
        sum(p[1] for p in points) / count,
        sum(p[2] for p in points) / count,
    ]


def _fallback_placement(layout_result: dict[str, Any], *, region_id: str = "") -> dict[str, Any]:
    position = _centroid_from_geometry(layout_result.get("public_space_geometry"))
    return {
        "placement_id": _placement_id(None, 0, region_id=region_id) if region_id else "fallback_0001",
        "asset_name": DEFAULT_FALLBACK_ASSET_NAME,
        "position": position,
        "orientation": [1.0, 0.0, 0.0],
        "zone_type": "fallback",
        "zone_id": None,
        "geometry": None,
        "asset_url": None,
    }


def layout_result_to_placement_output(
    layout_result: dict[str, Any],
    *,
    region_id: str,
    layout_steps: list[int] | None = None,
    inject_fallback_when_empty: bool = True,
) -> dict[str, Any]:
    asset_list = layout_result.get("asset_list") or []
    placements = []
    warnings = list(layout_result.get("warnings") or [])

    for index, item in enumerate(asset_list):
        if not isinstance(item, dict):
            continue
        placements.append(
            {
                "placement_id": _placement_id(
                    item.get("asset_id"),
                    index,
                    region_id=region_id,
                ),
                "asset_name": item.get("asset_candidates_name", ""),
                "position": list(item.get("asset_location") or []),
                "orientation": list(item.get("asset_orientation") or []),
                "zone_type": item.get("zone_type"),
                "zone_id": item.get("zone_id"),
                "geometry": item.get("geometry"),
                "asset_url": item.get("asset_URL") or item.get("asset_url"),
            }
        )

    public_space_type = str(layout_result.get("public_space_type") or "")
    used_fallback_placement = False
    if (
        not placements
        and inject_fallback_when_empty
        and public_space_type not in _TYPES_WITHOUT_FALLBACK
    ):
        placements.append(_fallback_placement(layout_result, region_id=region_id))
        used_fallback_placement = True
        warnings.append(
            "asset_list was empty; injected "
            f"{DEFAULT_FALLBACK_ASSET_NAME} at public_space_geometry centroid "
            "(executor renders varied debug geometry when assets are unmapped)."
        )

    return {
        "schema_version": PLACEMENT_OUTPUT_SCHEMA,
        "region_id": region_id,
        "public_space_type": public_space_type,
        "layout_steps": layout_steps or [1, 2, 3, 4, 5],
        "placements": placements,
        "warnings": warnings,
        "debug": {
            "flow_pattern": layout_result.get("flow_pattern"),
            "dynamic_zone_count": len(layout_result.get("dynamic_zones") or []),
            "static_zone_count": len(layout_result.get("static_zones") or []),
            "used_fallback_placement": used_fallback_placement,
        },
    }
