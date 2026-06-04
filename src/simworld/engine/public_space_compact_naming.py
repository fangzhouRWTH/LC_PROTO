"""Compact public-space prim naming (no underscores inside semantic tokens)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from engine.public_space_metadata import KNOWN_PUBLIC_SPACE_TYPES

PUBLIC_SPACE_REGION_PREFIX = "placeholder_area_publicspace_"
_INDEX_PATTERN = re.compile(r"^[0-9a-zA-Z]+$")

# Canonical public_space_type -> compact token (no underscores).
PUBLIC_SPACE_TYPE_TO_COMPACT: dict[str, str] = {
    "block_entrance": "blockentrance",
    "city_street_roof": "citystreetroof",
    "city_street_roofless": "citystreetroofless",
    "city_yard_roof": "cityyardroof",
    "city_yard_roofless": "cityyardroofless",
    "building_entrance": "buildingentrance",
}

PUBLIC_SPACE_TYPE_FROM_COMPACT: dict[str, str] = {
    compact: canonical for canonical, compact in PUBLIC_SPACE_TYPE_TO_COMPACT.items()
}

# boundary_type compact tokens (optional suffix on region prim name).
BOUNDARY_TYPE_TO_COMPACT: dict[str, str] = {
    "block_entrance": "blockentrance",
    "building_entrance_main": "buildingentrancemain",
    "street_boundary_primary": "streetboundaryprimary",
    "street_boundary_secondary": "streetboundarysecondary",
    "block_boundary_primary": "blockboundaryprimary",
    "block_boundary_secondary": "blockboundarysecondary",
    "block_boundary_other": "blockboundaryother",
    "yard_boundary": "yardboundary",
    "building_wall": "buildingwall",
    "building_other_type": "buildingothertype",
    "block_other_type": "blockothertype",
}

BOUNDARY_TYPE_FROM_COMPACT: dict[str, str] = {
    compact: canonical for canonical, compact in BOUNDARY_TYPE_TO_COMPACT.items()
}


@dataclass(frozen=True)
class PublicSpaceRegionNameInfo:
    raw_name: str
    index: str
    public_space_type: str = ""
    boundary_type_hint: str = ""


def _normalize_compact_token(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]", "", value).lower()


def decode_public_space_type_compact(token: str) -> str:
    return PUBLIC_SPACE_TYPE_FROM_COMPACT.get(_normalize_compact_token(token), "")


def decode_boundary_type_compact(token: str) -> str:
    return BOUNDARY_TYPE_FROM_COMPACT.get(_normalize_compact_token(token), "")


def encode_public_space_type_compact(public_space_type: str) -> str:
    return PUBLIC_SPACE_TYPE_TO_COMPACT.get(public_space_type, "")


def encode_boundary_type_compact(boundary_type: str) -> str:
    return BOUNDARY_TYPE_TO_COMPACT.get(boundary_type, "")


def _decode_legacy_public_space_type(remainder: str) -> str:
    for space_type in sorted(KNOWN_PUBLIC_SPACE_TYPES, key=len, reverse=True):
        suffix = f"_{space_type}"
        if remainder == space_type or remainder.endswith(suffix):
            return space_type
    return ""


def parse_public_space_region_name(name: str) -> Optional[PublicSpaceRegionNameInfo]:
    """
    Parse region prim names:

    - ``placeholder_area_publicspace_<index>``
    - ``placeholder_area_publicspace_<index>_<type_compact>``
    - ``placeholder_area_publicspace_<index>_<type_compact>_<boundary_compact>`` (optional)
    - legacy underscore types, e.g. ``..._001_city_yard_roofless``
    """
    if not name.startswith(PUBLIC_SPACE_REGION_PREFIX):
        return None

    rest = name[len(PUBLIC_SPACE_REGION_PREFIX) :]
    if not rest:
        return None

    parts = rest.split("_")
    index = parts[0]
    if not _INDEX_PATTERN.match(index):
        return None

    if len(parts) == 1:
        return PublicSpaceRegionNameInfo(raw_name=name, index=index)

    tail_parts = parts[1:]
    boundary_hint = ""
    if len(tail_parts) >= 2:
        decoded_boundary = decode_boundary_type_compact(tail_parts[-1])
        if decoded_boundary:
            boundary_hint = decoded_boundary
            tail_parts = tail_parts[:-1]

    if not tail_parts:
        return PublicSpaceRegionNameInfo(
            raw_name=name,
            index=index,
            boundary_type_hint=boundary_hint,
        )

    compact_type = decode_public_space_type_compact("".join(tail_parts))
    if compact_type:
        return PublicSpaceRegionNameInfo(
            raw_name=name,
            index=index,
            public_space_type=compact_type,
            boundary_type_hint=boundary_hint,
        )

    legacy_remainder = "_".join(tail_parts)
    legacy_type = _decode_legacy_public_space_type(legacy_remainder)
    if legacy_type:
        return PublicSpaceRegionNameInfo(
            raw_name=name,
            index=index,
            public_space_type=legacy_type,
            boundary_type_hint=boundary_hint,
        )

    return None


def format_public_space_region_name(
    index: str,
    public_space_type: str,
    *,
    boundary_type_hint: str = "",
) -> str:
    """Build a compact region prim name."""
    type_compact = encode_public_space_type_compact(public_space_type)
    if not type_compact:
        raise ValueError(f"unknown public_space_type: {public_space_type!r}")
    name = f"{PUBLIC_SPACE_REGION_PREFIX}{index}_{type_compact}"
    if boundary_type_hint:
        boundary_compact = encode_boundary_type_compact(boundary_type_hint)
        if not boundary_compact:
            raise ValueError(f"unknown boundary_type hint: {boundary_type_hint!r}")
        name = f"{name}_{boundary_compact}"
    return name
