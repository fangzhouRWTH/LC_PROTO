"""SimScene integration for area_placement_methods layout backend."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

from engine import area_placement_bridge, placement
from engine.area_placement_bridge import normalize_layout_backend

from . import scene_generator as generator
from . import scene_parser as parser
from .scene_public_space import build_placement_plan_from_parsed_regions
from .public_space_placement_executor import (
    PublicSpacePlacementExecutor,
    load_placement_output_json,
)


@dataclass
class AreaPlacementPrepareConfig:
    layout_backend: str = "legacy"
    region_input_path: pathlib.Path | None = None
    placement_plan_path: pathlib.Path | None = None
    layout_output_dir: pathlib.Path | None = None
    layout_steps: tuple[int, ...] = (1, 2, 3, 4, 5)
    use_dummy_assets: bool = True
    dummy_size_m: float = 0.5
    asset_name_map_path: pathlib.Path | None = None
    skip_legacy_placeholder_areas: bool = True


@dataclass
class AreaPlacementPrepareResult:
    placement_prim_paths: list[str] = field(default_factory=list)
    legacy_asset_prim_paths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def apply_area_placement_layout(
    *,
    stage,
    stats: parser.SceneStats,
    library: placement.AssetLibrary,
    asset_allocator,
    area_config: AreaPlacementPrepareConfig,
    verbose: bool = False,
) -> AreaPlacementPrepareResult:
    backend = normalize_layout_backend(area_config.layout_backend)
    if backend != "area_placement_methods":
        raise ValueError(f"apply_area_placement_layout called with backend={backend}")

    result = AreaPlacementPrepareResult()
    steps = [int(value) for value in area_config.layout_steps]

    if area_config.placement_plan_path is not None:
        plan = load_placement_output_json(area_config.placement_plan_path)
    elif area_config.region_input_path is not None:
        plan = area_placement_bridge.build_combined_placement_plan(
            area_config.region_input_path,
            steps=steps,
        )
        if area_config.layout_output_dir is not None:
            area_placement_bridge.write_json(
                area_config.layout_output_dir / "placement_output.json",
                plan,
            )
    elif stats.public_space_regions:
        try:
            plan = build_placement_plan_from_parsed_regions(stats, steps=steps)
        except ValueError as exc:
            result.warnings.append(str(exc))
            return result
        if area_config.layout_output_dir is not None:
            area_placement_bridge.write_json(
                area_config.layout_output_dir / "placement_output.json",
                plan,
            )
        if verbose:
            isolated = area_placement_bridge.layout_subprocess_enabled()
            mode = "subprocess" if isolated else "in-process"
            print(
                f"[INFO] Built placement plan from "
                f"{len(stats.public_space_regions)} parsed public-space region(s) "
                f"({mode})"
            )
    else:
        result.warnings.append(
            "area_placement_methods requires --region-input-json, "
            "--placement-plan-json, or USD public-space placeholders in the scene; "
            "skipping public-space placement."
        )
        return result

    asset_map = area_placement_bridge.load_asset_name_map(
        area_config.asset_name_map_path
    )
    executor = PublicSpacePlacementExecutor(
        stage=stage,
        use_dummy_assets=area_config.use_dummy_assets,
        dummy_size_m=area_config.dummy_size_m,
        asset_name_map=asset_map,
    )
    apply_result = executor.apply_plan(plan)
    result.placement_prim_paths.extend(apply_result.prim_paths)
    result.warnings.extend(apply_result.warnings)
    result.warnings.extend(plan.get("warnings") or [])

    if any("asset_list was empty" in warning for warning in plan.get("warnings") or []):
        print(
            "[WARN] Public-space layout used centroid fallback "
            "(asset_list was empty). A single debug primitive is placed at the "
            "region center; mapped assets use varied debug geoms when the library "
            "is not connected."
        )
    if stats.public_space_parse_warnings:
        print(
            f"[WARN] Public-space USD parse issues: "
            f"{len(stats.public_space_parse_warnings)} (see summary above)"
        )

    if verbose:
        print(
            f"[INFO] Area placement: {len(result.placement_prim_paths)} prim(s), "
            f"backend={backend}, dummy={area_config.use_dummy_assets}"
        )

    if not area_config.skip_legacy_placeholder_areas:
        result.legacy_asset_prim_paths.extend(
            _apply_legacy_placeholder_areas(
                stats=stats,
                library=library,
                asset_allocator=asset_allocator,
                verbose=verbose,
            )
        )

    return result


def _apply_legacy_placeholder_areas(
    *,
    stats: parser.SceneStats,
    library: placement.AssetLibrary,
    asset_allocator,
    verbose: bool,
) -> list[str]:
    footprints: list[placement.Footprint3D] = []
    for ply in stats.placeholder_areas:
        res = generator.generate_plane_polygon_layout(ply)
        footprints.extend(res.footprints)

    if not footprints:
        return []

    matcher = placement.AssetMatcher(library=library)
    planner = placement.AssetPlacementPlanner(matcher=matcher)
    import_plans = planner.build_plan_for_footprints(
        footprints=footprints,
        root_prim=asset_allocator.root_prim,
    )
    if verbose:
        for plan in import_plans:
            print(plan)

    allocation_result = asset_allocator.import_plans(import_plans)
    return list(allocation_result.prim_paths)
