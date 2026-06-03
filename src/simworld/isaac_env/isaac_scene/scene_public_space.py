"""Parse helpers and region-input assembly for public-space USD placeholders."""

from __future__ import annotations

from typing import Any

from engine import area_placement_bridge
from engine.public_space_metadata import (
    format_public_space_type_misexport_hint,
    is_known_public_space_type,
    looks_like_unset_simworld_property,
)

from . import scene_parser as parser

SIMWORLD_NS = "simworld"
DEFAULT_RATIO_DYNAMIC_STATIC = 0.36


def read_simworld_attribute(prim, name: str, default=None):
    """Read custom:simworld:<name> or simworld:<name> USD attribute."""
    keys = (
        f"custom:{SIMWORLD_NS}:{name}",
        f"{SIMWORLD_NS}:{name}",
    )
    for key in keys:
        attr = prim.GetAttribute(key)
        if attr and attr.IsValid():
            value = attr.Get()
            if value is not None:
                return value

    try:
        custom = prim.GetCustomData()
    except Exception:
        custom = None
    if isinstance(custom, dict):
        for key in (name, f"{SIMWORLD_NS}:{name}"):
            if key in custom and custom[key] is not None:
                return custom[key]

    return default


def find_parent_public_space_prim_path(prim) -> str | None:
    parent = prim.GetParent()
    while parent and parent.IsValid():
        info = parser.parse_prim_name(parent.GetName())
        if (
            info is not None
            and info.mobility == "placeholder"
            and info.domain == "area"
            and info.category == "publicspace"
        ):
            return str(parent.GetPath())
        parent = parent.GetParent()
    return None


def public_space_region_record_to_dict(
    region: parser.PlaceholderPublicSpaceRegion,
) -> dict[str, Any]:
    segments = [
        {
            "segment_id": segment.segment_id,
            "boundary_type": segment.boundary_type,
            "vertices": segment.vertices,
        }
        for segment in region.segments
    ]
    asset_has_set = [
        {
            "asset_has_set_id": item.asset_has_set_id,
            "asset_has_set_type": item.asset_has_set_type,
            "vertices": item.vertices,
        }
        for item in region.asset_has_sets
    ]
    return {
        "region_id": region.prim_path or region.raw_name,
        "prim_path": region.prim_path,
        "raw_name": region.raw_name,
        "public_space_type": region.public_space_type,
        "ratio_dynamic_static": region.ratio_dynamic_static,
        "boundary_vertices": region.boundary_vertices,
        "segments": segments,
        "asset_has_set": asset_has_set,
    }


def build_region_inputs_from_stats(stats: parser.SceneStats) -> list[dict[str, Any]]:
    _ensure_public_space_adapter()
    from adapters.public_space_region import public_space_region_to_region_input

    inputs: list[dict[str, Any]] = []
    for region in stats.public_space_regions:
        try:
            payload = public_space_region_to_region_input(
                public_space_region_record_to_dict(region)
            )
        except ValueError as exc:
            print(f"[WARN] Skipping public-space region {region.prim_path}: {exc}")
            continue
        inputs.append(payload)
    return inputs


def build_placement_plan_from_parsed_regions(
    stats: parser.SceneStats,
    *,
    steps: list[int] | None = None,
) -> dict[str, Any]:
    region_inputs = build_region_inputs_from_stats(stats)
    if not region_inputs:
        raise ValueError("No valid public-space regions found in SceneStats")
    return area_placement_bridge.build_combined_placement_plan_from_region_inputs(
        region_inputs,
        steps=steps,
    )


def attach_orphan_segments_to_regions(stats: parser.SceneStats) -> None:
    """Bind segment records collected before their parent region was seen."""
    regions_by_path = {region.prim_path: region for region in stats.public_space_regions}

    for segment in stats.public_space_boundary_segments:
        parent_path = segment.parent_region_prim_path
        if not parent_path:
            continue
        region = regions_by_path.get(parent_path)
        if region is None:
            stats.public_space_parse_warnings.append(
                f"Segment {segment.prim_path} has unknown parent region {parent_path}"
            )
            continue
        region.segments.append(segment)

    for asset_set in stats.public_space_asset_has_sets:
        parent_path = asset_set.parent_region_prim_path
        if not parent_path:
            continue
        region = regions_by_path.get(parent_path)
        if region is None:
            stats.public_space_parse_warnings.append(
                f"Asset-has-set {asset_set.prim_path} has unknown parent {parent_path}"
            )
            continue
        region.asset_has_sets.append(asset_set)


def _ensure_public_space_adapter() -> None:
    area_placement_bridge._ensure_module_path()
