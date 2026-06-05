"""Engine bridge to area_placement_methods (no Isaac)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import area_placement_bridge

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTO_SAMPLE = (
    REPO_ROOT
    / "algorithm_lab/experiments/area_placement_methods/proto/01_block_entrance_01.json"
)
LOCAL_ASSET_CONFIGURATION = REPO_ROOT / "asset_configuration"


class AreaPlacementBridgeTests(unittest.TestCase):
    def test_normalize_layout_backend_aliases(self):
        self.assertEqual(
            area_placement_bridge.normalize_layout_backend("area_placement"),
            "area_placement_methods",
        )
        self.assertEqual(
            area_placement_bridge.normalize_layout_backend("legacy"),
            "legacy",
        )

    def test_build_combined_placement_plan_from_file(self):
        plan = area_placement_bridge.build_combined_placement_plan(
            PROTO_SAMPLE,
            pedestrian_trip_min_length_m=1.0,
            pedestrian_trip_target_length_m=5.0,
            pedestrian_trip_max_length_m=10.0,
        )
        self.assertEqual(plan["schema_version"], "simworld.placement_output.v1")
        self.assertGreater(len(plan["placements"]), 0)
        self.assertGreater(len(plan["pedestrian_walkable_lines"]), 0)
        self.assertGreater(len(plan["pedestrian_routes"]), 0)
        self.assertEqual(
            plan["debug"]["pedestrian_walkable_line_count"],
            len(plan["pedestrian_walkable_lines"]),
        )
        self.assertEqual(
            plan["debug"]["pedestrian_route_count"],
            len(plan["pedestrian_routes"]),
        )
        self.assertTrue(
            all(
                route["metadata"]["source"] == "public_space_trip_generator"
                for route in plan["pedestrian_routes"]
            )
        )
        self.assertTrue(
            all(
                route["metadata"]["length"] >= 1.0
                for route in plan["pedestrian_routes"]
            )
        )
        self.assertIn("dynamic_zones", plan)

    def test_run_layout_from_region_file(self):
        layout = area_placement_bridge.run_layout_from_region_file(
            PROTO_SAMPLE,
            steps=[1, 2, 3, 4, 5],
        )
        self.assertEqual(layout["public_space_type"], "block_entrance")
        self.assertIn("asset_list", layout)

    def test_build_combined_placement_plan_from_region_inputs(self):
        with PROTO_SAMPLE.open(encoding="utf-8") as handle:
            proto = json.load(handle)
        parsed = {
            "region_id": "test_region",
            "public_space_type": proto["public_space_type"],
            "ratio_dynamic_static": proto["ratio_dynamic_static"],
            "boundary_vertices": proto["public_space_geometry"]["coordinates"],
            "segments": [
                {
                    "segment_id": item["segment_id"],
                    "boundary_type": item["boundary_type"],
                    "coordinates": item["geometry"]["coordinates"],
                }
                for item in proto["public_space_segments"]
            ],
        }
        plan = area_placement_bridge.build_combined_placement_plan_from_region_inputs(
            [parsed],
            steps=[1, 2, 3, 4, 5],
            pedestrian_trip_min_length_m=1.0,
            pedestrian_trip_target_length_m=5.0,
            pedestrian_trip_max_length_m=10.0,
        )
        self.assertEqual(len(plan["placements"]), 3)
        self.assertGreater(len(plan["pedestrian_walkable_lines"]), 0)
        self.assertGreater(len(plan["pedestrian_routes"]), 0)
        self.assertGreater(plan["debug"]["pedestrian_route_count"], 0)
        self.assertEqual(
            plan["pedestrian_route_debug"]["generated_trip_count"],
            len(plan["pedestrian_routes"]),
        )
        self.assertTrue(
            all(
                route["metadata"]["length"] >= 1.0
                for route in plan["pedestrian_routes"]
            )
        )

    @unittest.skipUnless(
        LOCAL_ASSET_CONFIGURATION.is_dir(),
        "local asset_configuration directory is not available",
    )
    def test_local_asset_configuration_generates_default_runtime_trips(self):
        plan = area_placement_bridge.build_combined_placement_plan(
            LOCAL_ASSET_CONFIGURATION,
        )
        lengths = [
            float(route["metadata"]["length"])
            for route in plan["pedestrian_routes"]
        ]

        self.assertGreater(len(plan["placements"]), 0)
        self.assertGreater(len(plan["pedestrian_walkable_lines"]), 0)
        self.assertGreater(len(plan["pedestrian_routes"]), 0)
        self.assertTrue(all(length >= 15.0 for length in lengths))
        self.assertTrue(all(length <= 40.0 for length in lengths))
        self.assertEqual(
            plan["pedestrian_route_debug"]["generated_trip_count"],
            len(plan["pedestrian_routes"]),
        )

    def test_load_asset_name_map_relocates_old_root_and_public_space_symlink(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            current_root = Path(tmpdir) / "lcstd_assets_library" / "static"
            actual_usd = current_root / "usd" / "traffic_infrastructure" / "trafficcone_01.usd"
            public_space_dir = current_root / "public_space" / "trafficcone"
            actual_usd.parent.mkdir(parents=True)
            public_space_dir.mkdir(parents=True)
            actual_usd.write_text("#usda 1.0\n", encoding="utf-8")

            old_root = "/home/fangzhou/projects/LC_01/assets/lcstd_assets_library/static"
            symlink_path = public_space_dir / "default.usd"
            symlink_path.symlink_to(
                f"{old_root}/usd/traffic_infrastructure/trafficcone_01.usd"
            )
            map_path = current_root / "asset_name_map.json"
            map_path.write_text(
                json.dumps(
                    {
                        "schema_version": "lcstd.asset_name_map.v1",
                        "library_root": old_root,
                        "assets": {
                            "trafficcone": f"{old_root}/public_space/trafficcone/default.usd",
                        },
                    }
                ),
                encoding="utf-8",
            )

            loaded = area_placement_bridge.load_asset_name_map(map_path)

        self.assertEqual(loaded["trafficcone"], str(actual_usd.resolve()))

    def test_subprocess_layout_disabled_by_default(self):
        self.assertFalse(area_placement_bridge._layout_subprocess_enabled())

    def test_kit_env_vars_do_not_enable_subprocess_by_default(self):
        with mock.patch.dict(
            os.environ,
            {"CARB_APP_PATH": "/fake/kit", "ISAAC_PATH": "/fake"},
            clear=False,
        ):
            self.assertFalse(area_placement_bridge._running_under_isaac_sim())
            self.assertFalse(area_placement_bridge._layout_subprocess_enabled())

    def test_subprocess_layout_opt_in_via_env(self):
        with mock.patch.dict(
            os.environ,
            {"LC01_LAYOUT_IN_SUBPROCESS": "1"},
            clear=False,
        ):
            self.assertTrue(area_placement_bridge._layout_subprocess_enabled())

    def test_build_combined_placement_plan_isolated_subprocess(self):
        with PROTO_SAMPLE.open(encoding="utf-8") as handle:
            proto = json.load(handle)
        region_input = {
            "schema_version": "simworld.region_input.v1",
            "region_id": "isolated_test",
            "public_space_type": proto["public_space_type"],
            "ratio_dynamic_static": proto["ratio_dynamic_static"],
            "public_space_geometry": proto["public_space_geometry"],
            "public_space_segments": proto["public_space_segments"],
        }
        plan = area_placement_bridge.build_combined_placement_plan_from_region_inputs_isolated(
            [region_input],
            steps=[1, 2, 3, 4, 5],
            pedestrian_trip_min_length_m=1.0,
            pedestrian_trip_target_length_m=5.0,
            pedestrian_trip_max_length_m=10.0,
        )
        self.assertEqual(plan["schema_version"], "simworld.placement_output.v1")
        self.assertEqual(len(plan["placements"]), 3)
        self.assertGreater(len(plan["pedestrian_walkable_lines"]), 0)
        self.assertGreater(len(plan["pedestrian_routes"]), 0)
        self.assertGreater(plan["pedestrian_route_debug"]["generated_trip_count"], 0)


if __name__ == "__main__":
    unittest.main()
