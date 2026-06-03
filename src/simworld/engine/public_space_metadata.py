"""Public-space USD metadata validation (no Isaac imports)."""

from __future__ import annotations

KNOWN_PUBLIC_SPACE_TYPES = frozenset(
    {
        "block_entrance",
        "city_street_roof",
        "city_street_roofless",
        "city_yard_roof",
        "city_yard_roofless",
        "building_entrance",
    }
)

_ATTRIBUTE_KEY_LIKE_VALUES = frozenset(
    {
        "simworld:public_space_type",
        "custom:simworld:public_space_type",
        "simworld:boundary_type",
        "custom:simworld:boundary_type",
        "simworld:segment_id",
        "simworld:ratio_dynamic_static",
    }
)


def is_known_public_space_type(value: object) -> bool:
    return str(value).strip() in KNOWN_PUBLIC_SPACE_TYPES


def looks_like_unset_simworld_property(value: object) -> bool:
    """True when USD stores the property key instead of the semantic value."""
    return str(value).strip() in _ATTRIBUTE_KEY_LIKE_VALUES


def format_public_space_type_misexport_hint(prim_path: str, raw_value: object) -> str:
    return (
        f"{prim_path}: simworld:public_space_type={raw_value!r} is not a valid "
        "space type (expected e.g. block_entrance). In Blender, set the custom "
        "property **value** to block_entrance — not the property name."
    )
