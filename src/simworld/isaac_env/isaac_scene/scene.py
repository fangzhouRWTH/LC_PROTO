from ..isaac_adaptor import isaac_context as iscctx

import pathlib

from . import scene_tools as tools
from . import scene_parser as parser
from . import scene_generator as generator
from . import scene_asset_allocator as asset_allocator
from .scene_area_placement import (
    AreaPlacementPrepareConfig,
    apply_area_placement_layout,
)

from engine import placement
from engine import dynamic
from engine.area_placement_bridge import normalize_layout_backend


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[4]
DEFAULT_ASSET_LIBRARY_PATH = PROJECT_ROOT / "assets" / "library"


def print_dynamic_plan_summary(plan: dynamic.DynamicScenePlan):
    if not plan.actors and not plan.warnings:
        return

    print("\n========== Dynamic Actor Plan ==========")
    print(f"Actors:   {len(plan.actors)}")
    if plan.actors:
        counts: dict[str, int] = {}
        for actor in plan.actors:
            counts[actor.actor_type] = counts.get(actor.actor_type, 0) + 1
        for actor_type, count in counts.items():
            print(f"  {actor_type}: {count}")

    if plan.warnings:
        print(f"Warnings: {len(plan.warnings)}")
        for warning in plan.warnings:
            print(f"  [WARN] {warning}")
    print("========================================\n")


class SimScene:
    def __init__(
        self,
        path: pathlib.Path,
        rules=None,
        sky_texture_path=None,
        asset_library_path: pathlib.Path | None = None,
        generated_asset_root: str = asset_allocator.DEFAULT_GENERATED_ASSET_ROOT,
    ):
        self.path = pathlib.Path(path).expanduser()
        self.rules = rules
        self.sky_texture_path = sky_texture_path
        self.context = iscctx.get_isaac_context().omni_usd.get_context()
        self.stats = parser.SceneStats()
        self.dynamic_plan = dynamic.DynamicScenePlan()
        self.asset_import_plans: list[placement.AssetImportPlan] = []
        self.generated_asset_prim_paths: list[str] = []

        asset_root = pathlib.Path(asset_library_path or DEFAULT_ASSET_LIBRARY_PATH)

        self.library = placement.AssetLibrary()
        self.library.scan_folder(asset_root)
        self.library.print_summary()

        if not self.context.open_stage(str(self.path)):
            raise RuntimeError(f"Failed to open USD stage: {self.path}")
        self.stage = self.context.get_stage()
        # Imported USDs may contain DomeLights with fragile relative texture paths.
        # Silence stage-authored lights before the first render/update pass.
        tools.deactivate_all_lights(self.stage)
        self.asset_allocator = asset_allocator.SceneAssetAllocator(
            stage=self.stage,
            root_prim=generated_asset_root,
        )

    def prepare(
        self,
        verbose: bool = False,
        dynamic_plan_config: dynamic.DynamicPlanConfig | None = None,
        build_dynamic_plan: bool = True,
        dynamic_placeholder_visibility: str = "hidden",
        placeholder_disposition: str | None = None,
        area_placement: AreaPlacementPrepareConfig | None = None,
    ):
        self.stats = parser.SceneStats()
        tools.deactivate_all_lights(self.stage)

        par_res = parser.process_stage_by_naming_rules(
            self.stage,
            stats=self.stats,
            rules=self.rules,
            verbose=verbose,
        )

        area_placement = area_placement or AreaPlacementPrepareConfig()
        layout_backend = normalize_layout_backend(area_placement.layout_backend)
        self.generated_asset_prim_paths = []
        self.asset_import_plans = []

        if layout_backend == "area_placement_methods":
            ap_result = apply_area_placement_layout(
                stage=self.stage,
                stats=self.stats,
                library=self.library,
                asset_allocator=self.asset_allocator,
                area_config=area_placement,
                verbose=verbose,
            )
            self.generated_asset_prim_paths.extend(ap_result.placement_prim_paths)
            self.generated_asset_prim_paths.extend(ap_result.legacy_asset_prim_paths)
            for warning in ap_result.warnings:
                print(f"[WARN] {warning}")
        else:
            self.generated_asset_prim_paths.extend(
                self._prepare_legacy_placeholder_assets(verbose=verbose)
            )

        if build_dynamic_plan:
            self.dynamic_plan = dynamic.build_dynamic_actor_plan(
                self.stats,
                config=dynamic_plan_config,
            )
            print_dynamic_plan_summary(self.dynamic_plan)
        else:
            self.dynamic_plan = dynamic.DynamicScenePlan()

        # Generated/referenced assets can bring their own lights after the first
        # cleanup pass. Keep lighting controlled by isaac_vfx.weather.
        tools.deactivate_all_lights(self.stage)

        disposition = placeholder_disposition or dynamic_placeholder_visibility
        tools.apply_placeholder_disposition(
            self.stage,
            self.stats,
            disposition=disposition,
        )

        return par_res

    def _prepare_legacy_placeholder_assets(self, *, verbose: bool = False) -> list[str]:
        footprints: list[placement.Footprint3D] = []
        for ply in self.stats.placeholder_areas:
            res = generator.generate_plane_polygon_layout(ply)
            footprints.extend(res.footprints)

        asset_matcher = placement.AssetMatcher(library=self.library)
        planner = placement.AssetPlacementPlanner(matcher=asset_matcher)

        self.asset_import_plans = planner.build_plan_for_footprints(
            footprints=footprints,
            root_prim=self.asset_allocator.root_prim,
        )

        if verbose:
            for plan in self.asset_import_plans:
                print(plan)

        if not self.asset_import_plans:
            return []

        allocation_result = self.asset_allocator.import_plans(self.asset_import_plans)
        return list(allocation_result.prim_paths)

    def update(self):
        iscctx.get_isaac_context().simulation_app.update()
