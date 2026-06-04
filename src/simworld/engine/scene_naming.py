"""USD prim naming helpers (no Isaac imports)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from engine.public_space_compact_naming import parse_public_space_region_name

PUBLIC_SPACE_REGION_PREFIX = "placeholder_area_publicspace_"
_INDEX_PATTERN = re.compile(r"^[0-9a-zA-Z]+$")


@dataclass
class PrimNameInfo:
    raw_name: str
    mobility: str
    domain: str
    category: str
    index: str
    public_space_type: str = ""
    boundary_type_hint: str = ""


NAME_PATTERN = re.compile(
    r"^(?P<mobility>[a-zA-Z]+)_"
    r"(?P<domain>[a-zA-Z]+)_"
    r"(?P<category>[a-zA-Z]+)_"
    r"(?P<index>[0-9a-zA-Z]+)$"
)


def parse_prim_name(name: str) -> Optional[PrimNameInfo]:
    region = parse_public_space_region_name(name)
    if region is not None:
        return PrimNameInfo(
            raw_name=name,
            mobility="placeholder",
            domain="area",
            category="publicspace",
            index=region.index,
            public_space_type=region.public_space_type,
            boundary_type_hint=region.boundary_type_hint,
        )

    match = NAME_PATTERN.match(name)
    if not match:
        return None

    return PrimNameInfo(
        raw_name=name,
        mobility=match.group("mobility"),
        domain=match.group("domain"),
        category=match.group("category"),
        index=match.group("index"),
    )
