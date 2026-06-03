"""Load area placement module from algorithm_lab (no Isaac imports)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = (
    REPO_ROOT
    / "algorithm_lab"
    / "experiments"
    / "area_placement_methods"
    / "module"
)

_LAYOUT_BACKENDS = frozenset({"legacy", "area_placement_methods"})


def normalize_layout_backend(value: str | None) -> str:
    if value is None or str(value).strip() == "":
        return "legacy"
    key = str(value).strip().lower().replace("-", "_")
    aliases = {
        "area_placement": "area_placement_methods",
        "public_space": "area_placement_methods",
        "public_space_layout": "area_placement_methods",
    }
    normalized = aliases.get(key, key)
    if normalized not in _LAYOUT_BACKENDS:
        allowed = ", ".join(sorted(_LAYOUT_BACKENDS))
        raise ValueError(
            f"Unsupported layout_backend: {value}. Available: {allowed}"
        )
    return normalized


def available_layout_backends() -> tuple[str, ...]:
    return tuple(sorted(_LAYOUT_BACKENDS))


def _ensure_module_path() -> None:
    module_str = str(MODULE_DIR)
    if module_str not in sys.path:
        sys.path.insert(0, module_str)


def _load_generator_module():
    _ensure_module_path()
    import generator  # type: ignore import-not-found

    return generator


def _load_adapters():
    _ensure_module_path()
    import adapters.asset_list_to_plan as plan_adapter  # type: ignore

    return plan_adapter


def collect_region_input_paths(path: Path) -> list[Path]:
    path = path.expanduser().resolve()
    if path.is_file():
        return [path]
    if path.is_dir():
        files = sorted(path.glob("*.json"))
        return [f for f in files if f.name != "out_test.json"]
    raise FileNotFoundError(f"Region input path not found: {path}")


def run_public_space_layout(
    region_input: dict[str, Any],
    *,
    steps: list[int] | None = None,
) -> dict[str, Any]:
    generator = _load_generator_module()
    return generator.run_public_space_layout(
        region_input,
        steps=steps,
    )


def run_layout_from_region_file(
    region_path: Path,
    *,
    steps: list[int] | None = None,
) -> dict[str, Any]:
    generator = _load_generator_module()
    return generator.run_public_space_layout_from_file(
        region_path,
        steps=steps or [1, 2, 3, 4, 5],
    )


def layout_result_to_placement_output(
    layout_result: dict[str, Any],
    *,
    region_id: str,
    layout_steps: list[int] | None = None,
) -> dict[str, Any]:
    plan_adapter = _load_adapters()
    return plan_adapter.layout_result_to_placement_output(
        layout_result,
        region_id=region_id,
        layout_steps=layout_steps,
    )


def load_asset_name_map(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    path = path.expanduser().resolve()
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    assets = data.get("assets")
    if not isinstance(assets, dict):
        raise ValueError(f"asset name map must contain 'assets' object: {path}")
    return {str(key): str(value) for key, value in assets.items()}


def build_combined_placement_plan_from_region_inputs(
    region_inputs: list[dict[str, Any]],
    *,
    steps: list[int] | None = None,
) -> dict[str, Any]:
    if not region_inputs:
        raise ValueError("region_inputs cannot be empty")

    _ensure_module_path()
    from adapters.public_space_region import public_space_region_to_region_input

    combined_placements: list[dict[str, Any]] = []
    warnings: list[str] = []
    public_space_type = ""
    layout_steps = steps or [1, 2, 3, 4, 5]

    for raw in region_inputs:
        if raw.get("schema_version") == "simworld.region_input.v1":
            region_input = raw
        else:
            region_input = public_space_region_to_region_input(raw)
        layout = run_public_space_layout(region_input, steps=layout_steps)
        plan = layout_result_to_placement_output(
            layout,
            region_id=str(region_input.get("region_id", "region")),
            layout_steps=layout_steps,
        )
        public_space_type = plan.get("public_space_type") or public_space_type
        combined_placements.extend(plan.get("placements") or [])
        warnings.extend(plan.get("warnings") or [])
        if plan.get("debug", {}).get("used_fallback_placement"):
            region_id = region_input.get("region_id", "region")
            warnings.append(
                f"region {region_id}: layout produced no assets "
                f"(public_space_type={layout.get('public_space_type')!r})"
            )

    return {
        "schema_version": "simworld.placement_output.v1",
        "region_id": "parsed_public_space_regions",
        "public_space_type": public_space_type,
        "layout_steps": layout_steps,
        "placements": combined_placements,
        "warnings": warnings,
        "debug": {
            "source": "scene_stats.public_space_regions",
            "used_fallback_placement": any(
                "asset_list was empty" in w for w in warnings
            ),
        },
    }


def build_combined_placement_plan(
    region_input_path: Path,
    *,
    steps: list[int] | None = None,
) -> dict[str, Any]:
    """Run layout for one file or merge all JSON files in a directory."""
    paths = collect_region_input_paths(region_input_path)
    if not paths:
        raise ValueError(f"No region input JSON files under {region_input_path}")

    combined_placements: list[dict[str, Any]] = []
    warnings: list[str] = []
    public_space_type = ""
    layout_steps = steps or [1, 2, 3, 4, 5]

    for region_path in paths:
        layout = run_layout_from_region_file(region_path, steps=layout_steps)
        plan = layout_result_to_placement_output(
            layout,
            region_id=region_path.stem,
            layout_steps=layout_steps,
        )
        public_space_type = plan.get("public_space_type") or public_space_type
        combined_placements.extend(plan.get("placements") or [])
        warnings.extend(plan.get("warnings") or [])

    return {
        "schema_version": "simworld.placement_output.v1",
        "region_id": region_input_path.stem,
        "public_space_type": public_space_type,
        "layout_steps": layout_steps,
        "placements": combined_placements,
        "warnings": warnings,
        "debug": {"source_files": [str(p) for p in paths]},
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
