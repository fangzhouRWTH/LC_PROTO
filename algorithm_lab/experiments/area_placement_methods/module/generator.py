"""Stable API over proto/ps_asset_config.py (re-sync from proto/ when lab updates)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

PROTO_DIR = Path(__file__).resolve().parent.parent / "proto"
PROTO_MODULE_PATH = PROTO_DIR / "ps_asset_config.py"

REGION_INPUT_SCHEMA = "simworld.region_input.v1"
PLACEMENT_OUTPUT_SCHEMA = "simworld.placement_output.v1"

_REQUIRED_REGION_KEYS = (
    "public_space_type",
    "public_space_geometry",
    "public_space_segments",
    "ratio_dynamic_static",
)


def _load_proto_module():
    spec = importlib.util.spec_from_file_location(
        "area_placement_ps_asset_config",
        PROTO_MODULE_PATH,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load proto module from {PROTO_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_region_input(data: dict[str, Any]) -> list[str]:
    """Return validation error messages; empty list means OK."""
    errors: list[str] = []
    version = data.get("schema_version")
    if version is not None and version != REGION_INPUT_SCHEMA:
        errors.append(
            f"Unsupported schema_version: {version} (expected {REGION_INPUT_SCHEMA})"
        )

    for key in _REQUIRED_REGION_KEYS:
        if key not in data:
            errors.append(f"Missing required field: {key}")

    ratio = data.get("ratio_dynamic_static")
    if ratio is not None:
        try:
            r = float(ratio)
            if r < 0.0 or r > 1.0:
                errors.append("ratio_dynamic_static must be in [0, 1]")
        except (TypeError, ValueError):
            errors.append("ratio_dynamic_static must be a number")

    segments = data.get("public_space_segments")
    if segments is not None and not isinstance(segments, list):
        errors.append("public_space_segments must be a list")

    return errors


def load_region_input_json(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    errors = validate_region_input(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data


def region_input_to_proto_kwargs(data: dict[str, Any]) -> dict[str, Any]:
    """Map v1 region_input (or raw proto JSON) to generator keyword arguments."""
    asset_has_set = data.get("asset_has_set") or data.get("Asset_has_set")
    return {
        "public_space_type": data["public_space_type"],
        "public_space_geometry": data["public_space_geometry"],
        "public_space_segments": data["public_space_segments"],
        "ratio_dynamic_static": float(data["ratio_dynamic_static"]),
        "asset_candidates_list": data.get("asset_candidates_list"),
        "cover_geometry": data.get("cover_geometry"),
        "asset_has_set": asset_has_set,
    }


def run_public_space_layout(
    region_input: dict[str, Any],
    *,
    steps: list[int] | None = None,
    flow_pattern_override: str | None = None,
    output_json_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Run the public-space layout pipeline.

    Accepts proto-shaped JSON or ``simworld.region_input.v1`` (extra fields ignored).
    """
    errors = validate_region_input(region_input)
    if errors:
        raise ValueError("; ".join(errors))

    proto = _load_proto_module()
    kwargs = region_input_to_proto_kwargs(region_input)
    result = proto.public_space_asset_configuration(
        **kwargs,
        steps=steps,
        output_json_path=str(output_json_path) if output_json_path else None,
        flow_pattern_override=flow_pattern_override,
    )
    result.setdefault("metadata", {})
    if isinstance(result["metadata"], dict):
        result["metadata"]["region_id"] = region_input.get(
            "region_id",
            region_input.get("metadata", {}).get("source_prim_path"),
        )
    return result


def run_public_space_layout_from_file(
    input_path: str | Path,
    *,
    steps: list[int] | None = None,
    flow_pattern_override: str | None = None,
    output_json_path: str | Path | None = None,
) -> dict[str, Any]:
    data = load_region_input_json(input_path)
    return run_public_space_layout(
        data,
        steps=steps,
        flow_pattern_override=flow_pattern_override,
        output_json_path=output_json_path,
    )
