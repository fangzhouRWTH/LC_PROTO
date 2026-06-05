"""Load area placement module from algorithm_lab (no Isaac imports)."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
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
    pedestrian_trip_min_length_m: float | None = None,
    pedestrian_trip_target_length_m: float | None = None,
    pedestrian_trip_max_length_m: float | None = None,
    pedestrian_node_merge_tolerance_m: float | None = None,
    max_pedestrian_trips_per_region: int | None = None,
) -> dict[str, Any]:
    plan_adapter = _load_adapters()
    kwargs = _pedestrian_trip_kwargs(
        pedestrian_trip_min_length_m=pedestrian_trip_min_length_m,
        pedestrian_trip_target_length_m=pedestrian_trip_target_length_m,
        pedestrian_trip_max_length_m=pedestrian_trip_max_length_m,
        pedestrian_node_merge_tolerance_m=pedestrian_node_merge_tolerance_m,
        max_pedestrian_trips_per_region=max_pedestrian_trips_per_region,
    )
    return plan_adapter.layout_result_to_placement_output(
        layout_result,
        region_id=region_id,
        layout_steps=layout_steps,
        **kwargs,
    )


def _pedestrian_trip_kwargs(
    *,
    pedestrian_trip_min_length_m: float | None = None,
    pedestrian_trip_target_length_m: float | None = None,
    pedestrian_trip_max_length_m: float | None = None,
    pedestrian_node_merge_tolerance_m: float | None = None,
    max_pedestrian_trips_per_region: int | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if pedestrian_trip_min_length_m is not None:
        kwargs["pedestrian_trip_min_length_m"] = pedestrian_trip_min_length_m
    if pedestrian_trip_target_length_m is not None:
        kwargs["pedestrian_trip_target_length_m"] = pedestrian_trip_target_length_m
    if pedestrian_trip_max_length_m is not None:
        kwargs["pedestrian_trip_max_length_m"] = pedestrian_trip_max_length_m
    if pedestrian_node_merge_tolerance_m is not None:
        kwargs["pedestrian_node_merge_tolerance_m"] = pedestrian_node_merge_tolerance_m
    if max_pedestrian_trips_per_region is not None:
        kwargs["max_pedestrian_trips_per_region"] = max_pedestrian_trips_per_region
    return kwargs


def _combined_pedestrian_route_debug(
    route_debugs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "walkable_line_count": sum(
            int(item.get("walkable_line_count") or 0) for item in route_debugs
        ),
        "generated_trip_count": sum(
            int(item.get("generated_trip_count") or 0) for item in route_debugs
        ),
        "graph_node_count": sum(
            int(item.get("graph_node_count") or 0) for item in route_debugs
        ),
        "graph_edge_count": sum(
            int(item.get("graph_edge_count") or 0) for item in route_debugs
        ),
        "component_count": sum(
            int(item.get("component_count") or 0) for item in route_debugs
        ),
        "skipped_short_component_count": sum(
            int(item.get("skipped_short_component_count") or 0)
            for item in route_debugs
        ),
        "regions": route_debugs,
    }


def _path_under_root(path: Path, root: Path) -> Path | None:
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return None


def _relocate_under_root(
    path: Path,
    *,
    old_root: Path | None,
    current_root: Path,
) -> Path | None:
    if old_root is None:
        return None
    relative = _path_under_root(path, old_root)
    if relative is None:
        return None
    return current_root / relative


def _resolve_existing_asset_path(
    candidate: Path,
    *,
    old_root: Path | None,
    current_root: Path,
    depth: int = 0,
) -> Path | None:
    if candidate.is_symlink() and depth < 4:
        target_text = os.readlink(candidate)
        target = Path(target_text).expanduser()
        if target.is_absolute():
            target = _relocate_under_root(
                target,
                old_root=old_root,
                current_root=current_root,
            ) or target
        else:
            target = candidate.parent / target
        resolved = _resolve_existing_asset_path(
            target,
            old_root=old_root,
            current_root=current_root,
            depth=depth + 1,
        )
        if resolved is not None:
            return resolved

    if candidate.exists():
        return candidate.resolve()
    return None


def _relocatable_asset_path(
    raw_value: Any,
    *,
    map_path: Path,
    old_library_root: Any,
) -> str:
    raw_text = str(raw_value)
    raw_path = Path(raw_text).expanduser()
    current_root = map_path.parent.resolve()
    old_root = None
    if isinstance(old_library_root, str) and old_library_root.strip():
        old_root = Path(old_library_root).expanduser()

    candidates: list[Path] = []
    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        candidates.append(current_root / raw_path)

    relocated = _relocate_under_root(
        raw_path,
        old_root=old_root,
        current_root=current_root,
    )
    if relocated is not None and relocated not in candidates:
        candidates.append(relocated)

    for candidate in candidates:
        resolved = _resolve_existing_asset_path(
            candidate,
            old_root=old_root,
            current_root=current_root,
        )
        if resolved is not None:
            return str(resolved)

    if relocated is not None:
        return str(relocated.resolve(strict=False))
    if raw_path.is_absolute():
        return raw_text
    return str((current_root / raw_path).resolve(strict=False))


def load_asset_name_map(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    path = path.expanduser().resolve()
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    assets = data.get("assets")
    if not isinstance(assets, dict):
        raise ValueError(f"asset name map must contain 'assets' object: {path}")
    library_root = data.get("library_root")
    return {
        str(key): _relocatable_asset_path(
            value,
            map_path=path,
            old_library_root=library_root,
        )
        for key, value in assets.items()
    }


def layout_subprocess_enabled() -> bool:
    return _layout_subprocess_enabled()


def _layout_subprocess_enabled() -> bool:
    """Subprocess layout is opt-in only (LC01_LAYOUT_IN_SUBPROCESS=1). Default: in-process."""
    flag = os.environ.get("LC01_LAYOUT_IN_SUBPROCESS", "0").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return False
    if flag in {"1", "true", "yes", "on"}:
        return True
    if flag == "auto":
        return _running_under_isaac_sim()
    return False


def _running_under_isaac_sim() -> bool:
    """True only when Kit/Omniverse modules are loaded in *this* interpreter."""
    return any(
        name.startswith("isaacsim")
        or name.startswith("omni.")
        or name == "carb"
        for name in sys.modules
    )


def _is_isaac_python_executable(path: str) -> bool:
    lowered = path.lower()
    markers = (
        "isaac",
        "omniverse",
        "omni.",
        "/kit/",
        "carb.sdk",
        "nvidia/isaac",
    )
    return any(marker in lowered for marker in markers)


def _layout_python_executable() -> str:
    override = os.environ.get("LC01_LAYOUT_PYTHON", "").strip()
    if override:
        return override
    for candidate in ("/usr/bin/python3", "/usr/local/bin/python3"):
        if Path(candidate).is_file() and not _is_isaac_python_executable(candidate):
            return candidate
    found = shutil.which("python3")
    if found and not _is_isaac_python_executable(found):
        return found
    return "/usr/bin/python3"


_KIT_ENV_PREFIXES = (
    "CARB_",
    "ISAAC",
    "OMNI_",
    "KIT_",
    "NV_",
)


def _layout_subprocess_env() -> dict[str, str]:
    """Child must not inherit Kit env vars (they re-trigger nested subprocess layout)."""
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(_KIT_ENV_PREFIXES)
    }
    env["LC01_LAYOUT_IN_SUBPROCESS"] = "0"
    return env


def _layout_subprocess_script() -> Path:
    return REPO_ROOT / "scripts" / "build_public_space_placement_plan.py"


def build_combined_placement_plan_from_region_inputs_isolated(
    region_inputs: list[dict[str, Any]],
    *,
    steps: list[int] | None = None,
    pedestrian_trip_min_length_m: float | None = None,
    pedestrian_trip_target_length_m: float | None = None,
    pedestrian_trip_max_length_m: float | None = None,
    pedestrian_node_merge_tolerance_m: float | None = None,
    max_pedestrian_trips_per_region: int | None = None,
) -> dict[str, Any]:
    """Run layout in a plain Python subprocess (avoids Kit segfaults during proto import)."""
    if not region_inputs:
        raise ValueError("region_inputs cannot be empty")

    script = _layout_subprocess_script()
    if not script.is_file():
        raise FileNotFoundError(f"Layout subprocess script not found: {script}")

    payload: dict[str, Any] = {"region_inputs": region_inputs}
    if steps is not None:
        payload["steps"] = [int(value) for value in steps]
    trip_kwargs = _pedestrian_trip_kwargs(
        pedestrian_trip_min_length_m=pedestrian_trip_min_length_m,
        pedestrian_trip_target_length_m=pedestrian_trip_target_length_m,
        pedestrian_trip_max_length_m=pedestrian_trip_max_length_m,
        pedestrian_node_merge_tolerance_m=pedestrian_node_merge_tolerance_m,
        max_pedestrian_trips_per_region=max_pedestrian_trips_per_region,
    )
    if trip_kwargs:
        payload["pedestrian_trip_config"] = trip_kwargs

    executable = _layout_python_executable()
    proc = subprocess.run(
        [executable, str(script)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=_layout_subprocess_env(),
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        if not detail:
            detail = (
                f"(no stderr; executable={executable!r}, "
                f"script={script!r})"
            )
        raise RuntimeError(
            f"Public-space layout subprocess failed (exit {proc.returncode}): {detail}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Public-space layout subprocess returned invalid JSON"
        ) from exc


def build_combined_placement_plan_from_region_inputs(
    region_inputs: list[dict[str, Any]],
    *,
    steps: list[int] | None = None,
    force_in_process: bool = False,
    pedestrian_trip_min_length_m: float | None = None,
    pedestrian_trip_target_length_m: float | None = None,
    pedestrian_trip_max_length_m: float | None = None,
    pedestrian_node_merge_tolerance_m: float | None = None,
    max_pedestrian_trips_per_region: int | None = None,
) -> dict[str, Any]:
    if not region_inputs:
        raise ValueError("region_inputs cannot be empty")

    if not force_in_process and _layout_subprocess_enabled():
        return build_combined_placement_plan_from_region_inputs_isolated(
            region_inputs,
            steps=steps,
            pedestrian_trip_min_length_m=pedestrian_trip_min_length_m,
            pedestrian_trip_target_length_m=pedestrian_trip_target_length_m,
            pedestrian_trip_max_length_m=pedestrian_trip_max_length_m,
            pedestrian_node_merge_tolerance_m=pedestrian_node_merge_tolerance_m,
            max_pedestrian_trips_per_region=max_pedestrian_trips_per_region,
        )

    _ensure_module_path()
    from adapters.public_space_region import public_space_region_to_region_input

    combined_placements: list[dict[str, Any]] = []
    combined_pedestrian_walkable_lines: list[dict[str, Any]] = []
    combined_pedestrian_routes: list[dict[str, Any]] = []
    combined_pedestrian_route_debugs: list[dict[str, Any]] = []
    combined_dynamic_zones: list[dict[str, Any]] = []
    combined_static_zones: list[dict[str, Any]] = []
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
            pedestrian_trip_min_length_m=pedestrian_trip_min_length_m,
            pedestrian_trip_target_length_m=pedestrian_trip_target_length_m,
            pedestrian_trip_max_length_m=pedestrian_trip_max_length_m,
            pedestrian_node_merge_tolerance_m=pedestrian_node_merge_tolerance_m,
            max_pedestrian_trips_per_region=max_pedestrian_trips_per_region,
        )
        public_space_type = plan.get("public_space_type") or public_space_type
        combined_placements.extend(plan.get("placements") or [])
        combined_pedestrian_walkable_lines.extend(
            plan.get("pedestrian_walkable_lines") or []
        )
        combined_pedestrian_routes.extend(plan.get("pedestrian_routes") or [])
        if isinstance(plan.get("pedestrian_route_debug"), dict):
            region_debug = dict(plan["pedestrian_route_debug"])
            region_debug["region_id"] = plan.get("region_id")
            combined_pedestrian_route_debugs.append(region_debug)
        combined_dynamic_zones.extend(plan.get("dynamic_zones") or [])
        combined_static_zones.extend(plan.get("static_zones") or [])
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
        "pedestrian_walkable_lines": combined_pedestrian_walkable_lines,
        "pedestrian_routes": combined_pedestrian_routes,
        "pedestrian_route_debug": _combined_pedestrian_route_debug(
            combined_pedestrian_route_debugs
        ),
        "dynamic_zones": combined_dynamic_zones,
        "static_zones": combined_static_zones,
        "warnings": warnings,
        "debug": {
            "source": "scene_stats.public_space_regions",
            "pedestrian_walkable_line_count": len(combined_pedestrian_walkable_lines),
            "pedestrian_route_count": len(combined_pedestrian_routes),
            "pedestrian_route_skipped_short_component_count": sum(
                int(item.get("skipped_short_component_count") or 0)
                for item in combined_pedestrian_route_debugs
            ),
            "dynamic_zone_count": len(combined_dynamic_zones),
            "static_zone_count": len(combined_static_zones),
            "used_fallback_placement": any(
                "asset_list was empty" in w for w in warnings
            ),
        },
    }


def build_combined_placement_plan(
    region_input_path: Path,
    *,
    steps: list[int] | None = None,
    pedestrian_trip_min_length_m: float | None = None,
    pedestrian_trip_target_length_m: float | None = None,
    pedestrian_trip_max_length_m: float | None = None,
    pedestrian_node_merge_tolerance_m: float | None = None,
    max_pedestrian_trips_per_region: int | None = None,
) -> dict[str, Any]:
    """Run layout for one file or merge all JSON files in a directory."""
    paths = collect_region_input_paths(region_input_path)
    if not paths:
        raise ValueError(f"No region input JSON files under {region_input_path}")

    combined_placements: list[dict[str, Any]] = []
    combined_pedestrian_walkable_lines: list[dict[str, Any]] = []
    combined_pedestrian_routes: list[dict[str, Any]] = []
    combined_pedestrian_route_debugs: list[dict[str, Any]] = []
    combined_dynamic_zones: list[dict[str, Any]] = []
    combined_static_zones: list[dict[str, Any]] = []
    warnings: list[str] = []
    public_space_type = ""
    layout_steps = steps or [1, 2, 3, 4, 5]

    for region_path in paths:
        layout = run_layout_from_region_file(region_path, steps=layout_steps)
        plan = layout_result_to_placement_output(
            layout,
            region_id=region_path.stem,
            layout_steps=layout_steps,
            pedestrian_trip_min_length_m=pedestrian_trip_min_length_m,
            pedestrian_trip_target_length_m=pedestrian_trip_target_length_m,
            pedestrian_trip_max_length_m=pedestrian_trip_max_length_m,
            pedestrian_node_merge_tolerance_m=pedestrian_node_merge_tolerance_m,
            max_pedestrian_trips_per_region=max_pedestrian_trips_per_region,
        )
        public_space_type = plan.get("public_space_type") or public_space_type
        combined_placements.extend(plan.get("placements") or [])
        combined_pedestrian_walkable_lines.extend(
            plan.get("pedestrian_walkable_lines") or []
        )
        combined_pedestrian_routes.extend(plan.get("pedestrian_routes") or [])
        if isinstance(plan.get("pedestrian_route_debug"), dict):
            region_debug = dict(plan["pedestrian_route_debug"])
            region_debug["region_id"] = plan.get("region_id")
            combined_pedestrian_route_debugs.append(region_debug)
        combined_dynamic_zones.extend(plan.get("dynamic_zones") or [])
        combined_static_zones.extend(plan.get("static_zones") or [])
        warnings.extend(plan.get("warnings") or [])

    return {
        "schema_version": "simworld.placement_output.v1",
        "region_id": region_input_path.stem,
        "public_space_type": public_space_type,
        "layout_steps": layout_steps,
        "placements": combined_placements,
        "pedestrian_walkable_lines": combined_pedestrian_walkable_lines,
        "pedestrian_routes": combined_pedestrian_routes,
        "pedestrian_route_debug": _combined_pedestrian_route_debug(
            combined_pedestrian_route_debugs
        ),
        "dynamic_zones": combined_dynamic_zones,
        "static_zones": combined_static_zones,
        "warnings": warnings,
        "debug": {
            "source_files": [str(p) for p in paths],
            "pedestrian_walkable_line_count": len(combined_pedestrian_walkable_lines),
            "pedestrian_route_count": len(combined_pedestrian_routes),
            "pedestrian_route_skipped_short_component_count": sum(
                int(item.get("skipped_short_component_count") or 0)
                for item in combined_pedestrian_route_debugs
            ),
            "dynamic_zone_count": len(combined_dynamic_zones),
            "static_zone_count": len(combined_static_zones),
        },
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
