"""USD prim naming helpers (no Isaac imports)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class PrimNameInfo:
    raw_name: str
    mobility: str
    domain: str
    category: str
    index: str


NAME_PATTERN = re.compile(
    r"^(?P<mobility>[a-zA-Z]+)_"
    r"(?P<domain>[a-zA-Z]+)_"
    r"(?P<category>[a-zA-Z]+)_"
    r"(?P<index>[0-9a-zA-Z]+)$"
)


def parse_prim_name(name: str) -> Optional[PrimNameInfo]:
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
