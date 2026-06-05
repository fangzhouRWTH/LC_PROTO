"""Area placement module tests (no Isaac)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ROOT = (
    REPO_ROOT / "algorithm_lab" / "experiments" / "area_placement_methods"
)
MODULE_DIR = EXPERIMENT_ROOT / "module"
PROTO_DIR = EXPERIMENT_ROOT / "proto"

sys.path.insert(0, str(MODULE_DIR))

from adapters.asset_list_to_plan import (  # noqa: E402
    DEFAULT_FALLBACK_ASSET_NAME,
    PLACEMENT_OUTPUT_SCHEMA,
    extract_pedestrian_routes_from_layout_result,
    extract_pedestrian_walkable_lines_from_layout_result,
    generate_pedestrian_trips_from_walkable_lines,
    layout_result_to_placement_output,
)
from adapters.scene_to_region_input import (  # noqa: E402
    block_entrance_region_input_from_rectangle,
)
from generator import (  # noqa: E402
    REGION_INPUT_SCHEMA,
    run_public_space_layout,
    run_public_space_layout_from_file,
)


def _proto_sample_paths() -> list[Path]:
    paths = sorted(PROTO_DIR.glob("*.json"))
    return [p for p in paths if p.name not in {"out_test.json"}]


class AreaPlacementModuleTests(unittest.TestCase):
    def test_block_entrance_synthetic_roundtrip(self):
        region = block_entrance_region_input_from_rectangle(
            min_xy=(0.0, 0.0),
            max_xy=(10.0, 10.0),
        )
        self.assertEqual(region["schema_version"], REGION_INPUT_SCHEMA)
        result = run_public_space_layout(region, steps=[1, 2, 3, 4, 5])
        self.assertIn("asset_list", result)
        self.assertGreater(len(result["asset_list"]), 0)

    def test_proto_sample_01_matches_file_pipeline(self):
        path = PROTO_DIR / "01_block_entrance_01.json"
        from_file = run_public_space_layout_from_file(path, steps=[1, 2, 3, 4, 5])
        with path.open(encoding="utf-8") as handle:
            raw = json.load(handle)
        from_dict = run_public_space_layout(raw, steps=[1, 2, 3, 4, 5])
        self.assertEqual(
            len(from_file.get("asset_list") or []),
            len(from_dict.get("asset_list") or []),
        )

    def test_all_proto_samples_run_steps_1_to_5(self):
        for path in _proto_sample_paths():
            with self.subTest(sample=path.name):
                result = run_public_space_layout_from_file(
                    path,
                    steps=[1, 2, 3, 4, 5],
                )
                self.assertEqual(
                    result.get("public_space_type"),
                    json.loads(path.read_text(encoding="utf-8"))["public_space_type"],
                )
                self.assertIn("walking_lines", result)
                self.assertIn("dynamic_zones", result)
                self.assertIn("static_zones", result)
                space_type = result.get("public_space_type")
                asset_list = result.get("asset_list") or []
                if space_type == "city_street_roof":
                    self.assertEqual(len(asset_list), 0)
                else:
                    self.assertGreater(len(asset_list), 0)

    def test_layout_result_to_placement_output(self):
        path = PROTO_DIR / "01_block_entrance_01.json"
        layout = run_public_space_layout_from_file(path, steps=[1, 2, 3, 4, 5])
        plan = layout_result_to_placement_output(
            layout,
            region_id="test_region",
        )
        self.assertEqual(plan["schema_version"], PLACEMENT_OUTPUT_SCHEMA)
        self.assertEqual(len(plan["placements"]), len(layout.get("asset_list") or []))
        self.assertEqual(
            len(plan["pedestrian_walkable_lines"]),
            len(layout.get("walking_lines") or []),
        )
        self.assertEqual(plan["dynamic_zones"], layout.get("dynamic_zones"))
        self.assertEqual(plan["static_zones"], layout.get("static_zones"))
        self.assertEqual(
            plan["debug"]["pedestrian_route_count"],
            len(plan["pedestrian_routes"]),
        )
        self.assertEqual(
            plan["debug"]["pedestrian_walkable_line_count"],
            len(plan["pedestrian_walkable_lines"]),
        )
        if plan["pedestrian_routes"]:
            route = plan["pedestrian_routes"][0]
            self.assertGreaterEqual(len(route["vertices"]), 2)
            self.assertEqual(route["metadata"]["source"], "public_space_trip_generator")
            self.assertEqual(route["metadata"]["source_region_id"], "test_region")
            self.assertGreaterEqual(route["metadata"]["length"], 15.0)
        if plan["placements"]:
            item = plan["placements"][0]
            self.assertIn("asset_name", item)
            self.assertIn("position", item)
            self.assertTrue(item["placement_id"].startswith("test_region_asset_"))

    def test_extract_walkable_lines_skips_invalid_walking_lines(self):
        layout = {
            "flow_pattern": "cross",
            "walking_lines": [
                {"line_id": 1, "geometry": {"coordinates": [[1.0, 2.0, 0.0]]}},
                {
                    "line_id": 2,
                    "line_role": "main",
                    "geometry": {
                        "coordinates": [
                            [0.0, 0.0, 0.0],
                            [3.0, 4.0, 0.0],
                        ]
                    },
                },
            ],
        }

        lines = extract_pedestrian_walkable_lines_from_layout_result(
            layout,
            region_id="/World/placeholder_area_publicspace_001_demo",
        )
        routes = extract_pedestrian_routes_from_layout_result(
            layout,
            region_id="/World/placeholder_area_publicspace_001_demo",
        )

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["line_id"], "walkable_line_001_demo_2")
        self.assertEqual(lines[0]["metadata"]["length"], 5.0)
        self.assertEqual(routes, [])

    def test_trip_generator_splits_intersections_into_graph_junctions(self):
        layout = {
            "flow_pattern": "cross",
            "walking_lines": [
                {
                    "line_id": 1,
                    "line_role": "main",
                    "geometry": {"coordinates": [[0.0, 0.0, 0.0], [20.0, 0.0, 0.0]]},
                },
                {
                    "line_id": 2,
                    "line_role": "cross",
                    "geometry": {"coordinates": [[10.0, -10.0, 0.0], [10.0, 10.0, 0.0]]},
                },
            ],
        }
        lines = extract_pedestrian_walkable_lines_from_layout_result(layout, region_id="cross")

        trips, debug = generate_pedestrian_trips_from_walkable_lines(
            lines,
            region_id="cross",
            min_trip_length_m=15.0,
            target_trip_length_m=25.0,
            max_trip_length_m=40.0,
        )

        self.assertGreater(len(trips), 0)
        self.assertGreaterEqual(debug["graph_node_count"], 5)
        self.assertTrue(
            any(
                any(abs(point[0] - 10.0) < 1e-6 and abs(point[1]) < 1e-6 for point in trip["vertices"])
                for trip in trips
            )
        )

    def test_trip_generator_merges_nearby_endpoints(self):
        lines = [
            {"line_id": "a", "vertices": [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]]},
            {"line_id": "b", "vertices": [[10.04, 0.0, 0.0], [25.0, 0.0, 0.0]]},
        ]

        trips, debug = generate_pedestrian_trips_from_walkable_lines(
            lines,
            region_id="merge",
            node_merge_tolerance_m=0.10,
        )

        self.assertGreater(len(trips), 0)
        self.assertLessEqual(debug["graph_node_count"], 3)
        self.assertGreaterEqual(trips[0]["metadata"]["length"], 15.0)

    def test_trip_generator_skips_short_components(self):
        lines = [{"line_id": "short", "vertices": [[0.0, 0.0, 0.0], [5.0, 0.0, 0.0]]}]

        trips, debug = generate_pedestrian_trips_from_walkable_lines(
            lines,
            region_id="short",
            min_trip_length_m=15.0,
        )

        self.assertEqual(trips, [])
        self.assertEqual(debug["skipped_short_component_count"], 1)

    def test_placement_ids_are_unique_per_region_slug(self):
        layout_a = {
            "public_space_type": "block_entrance",
            "asset_list": [
                {
                    "asset_id": 1,
                    "asset_candidates_name": "bollard",
                    "asset_location": [1.0, 1.0, 0.0],
                    "asset_orientation": [1.0, 0.0, 0.0],
                }
            ],
        }
        layout_b = {
            "public_space_type": "block_entrance",
            "asset_list": [
                {
                    "asset_id": 1,
                    "asset_candidates_name": "bollard",
                    "asset_location": [2.0, 2.0, 0.0],
                    "asset_orientation": [1.0, 0.0, 0.0],
                }
            ],
        }
        plan_a = layout_result_to_placement_output(
            layout_a,
            region_id="/World/placeholder_area_publicspace_009_blockentrance",
        )
        plan_b = layout_result_to_placement_output(
            layout_b,
            region_id="/World/placeholder_area_publicspace_008_blockentrance",
        )
        self.assertNotEqual(
            plan_a["placements"][0]["placement_id"],
            plan_b["placements"][0]["placement_id"],
        )
        self.assertTrue(
            plan_a["placements"][0]["placement_id"].startswith("ps_009_blockentrance_asset_")
        )

    def test_empty_asset_list_injects_builtin_placeholder(self):
        layout = {
            "public_space_type": "block_entrance",
            "public_space_geometry": {
                "type": "LineString3D",
                "coordinates": [
                    [0.0, 0.0, 0.0],
                    [10.0, 0.0, 0.0],
                    [10.0, 10.0, 0.0],
                    [0.0, 10.0, 0.0],
                    [0.0, 0.0, 0.0],
                ],
            },
            "asset_list": [],
        }
        plan = layout_result_to_placement_output(layout, region_id="debug_region")
        self.assertEqual(len(plan["placements"]), 1)
        self.assertEqual(
            plan["placements"][0]["asset_name"], DEFAULT_FALLBACK_ASSET_NAME
        )
        self.assertEqual(plan["placements"][0]["position"], [5.0, 5.0, 0.0])
        self.assertTrue(plan["debug"]["used_fallback_placement"])
        self.assertTrue(any("asset_list was empty" in w for w in plan["warnings"]))

    def test_city_street_roof_empty_list_has_no_fallback(self):
        layout = {
            "public_space_type": "city_street_roof",
            "public_space_geometry": {"coordinates": [[0, 0, 0], [1, 0, 0]]},
            "asset_list": [],
        }
        plan = layout_result_to_placement_output(layout, region_id="roof")
        self.assertEqual(plan["placements"], [])
        self.assertFalse(plan["debug"]["used_fallback_placement"])


if __name__ == "__main__":
    unittest.main()
