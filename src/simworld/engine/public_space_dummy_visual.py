"""Deterministic dummy geometry specs for public-space layout debug (no Isaac)."""

from __future__ import annotations

import hashlib
import re
from typing import Any

SHAPE_NAMES = ("cube", "sphere", "cylinder", "cone")

# Rough semantic hints: asset name keyword -> preferred shape / scale / hue.
_ASSET_SHAPE_HINTS: tuple[tuple[str, str, float], ...] = (
    ("guard_rail", "cylinder", 0.35),
    ("street_light", "cylinder", 0.45),
    ("bollard", "cylinder", 0.3),
    ("tree", "sphere", 0.55),
    ("flower", "sphere", 0.4),
    ("bench", "cube", 0.6),
    ("seat", "cube", 0.45),
    ("sign", "cube", 0.35),
    ("metro", "cube", 0.4),
    ("traffic", "cube", 0.4),
    ("vending", "cube", 0.5),
    ("locker", "cube", 0.55),
    ("canopy", "cone", 0.65),
    ("bus_stop", "cube", 0.7),
    ("grass", "cube", 0.25),
    ("hydrant", "cylinder", 0.35),
    ("trash", "cylinder", 0.35),
    ("cart", "sphere", 0.4),
    ("placeholder", "cube", 0.5),
)


def _seed_bytes(*parts: str) -> bytes:
    payload = "|".join(str(part) for part in parts if part)
    return hashlib.sha256(payload.encode("utf-8")).digest()


def _unit_float(seed: bytes, salt: str) -> float:
    digest = hashlib.sha256(seed + salt.encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _asset_hint(asset_name: str) -> tuple[str | None, float | None]:
    key = re.sub(r"[^a-z0-9]+", "_", asset_name.lower()).strip("_")
    for prefix, shape, scale in _ASSET_SHAPE_HINTS:
        if prefix in key:
            return shape, scale
    return None, None


def dummy_visual_spec(
    placement_key: str,
    asset_name: str = "",
) -> dict[str, Any]:
    """
    Return a reproducible debug primitive description for one placement.

    Used when the asset library has no USD for ``asset_name``.
    """
    seed = _seed_bytes(placement_key, asset_name)
    hinted_shape, hinted_scale = _asset_hint(asset_name or placement_key)

    shape_index = int(_unit_float(seed, "shape") * len(SHAPE_NAMES))
    shape = hinted_shape or SHAPE_NAMES[shape_index % len(SHAPE_NAMES)]

    base = hinted_scale if hinted_scale is not None else 0.45
    size = base * (0.75 + 0.5 * _unit_float(seed, "size"))
    size = max(0.2, min(size, 1.2))

    hue = _unit_float(seed, "hue")
    # HSV -> RGB (simple piecewise, sufficient for debug)
    sat = 0.55 + 0.35 * _unit_float(seed, "sat")
    val = 0.65 + 0.3 * _unit_float(seed, "val")
    color = _hsv_to_rgb(hue, sat, val)

    return {
        "shape": shape,
        "size": float(size),
        "color": color,
        "asset_name": asset_name,
        "placement_key": placement_key,
    }


def _hsv_to_rgb(h: float, s: float, v: float) -> tuple[float, float, float]:
    i = int(h * 6.0)
    f = h * 6.0 - i
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    i %= 6
    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q
    return (float(r), float(g), float(b))
