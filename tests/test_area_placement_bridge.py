"""Engine bridge to area_placement_methods (no Isaac)."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest import mock

from engine import area_placement_bridge

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTO_SAMPLE = (
    REPO_ROOT
    / "algorithm_lab/experiments/area_placement_methods/proto/01_block_entrance_01.json"
)


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
        plan = area_placement_bridge.build_combined_placement_plan(PROTO_SAMPLE)
        self.assertEqual(plan["schema_version"], "simworld.placement_output.v1")
        self.assertGreater(len(plan["placements"]), 0)

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
        )
        self.assertEqual(len(plan["placements"]), 3)

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
        )
        self.assertEqual(plan["schema_version"], "simworld.placement_output.v1")
        self.assertEqual(len(plan["placements"]), 3)


if __name__ == "__main__":
    unittest.main()
