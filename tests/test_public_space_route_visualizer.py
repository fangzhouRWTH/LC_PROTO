from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "visualize_public_space_routes.py"
PROTO_SAMPLE = (
    REPO_ROOT
    / "algorithm_lab/experiments/area_placement_methods/proto/01_block_entrance_01.json"
)

spec = importlib.util.spec_from_file_location("route_visualizer", SCRIPT_PATH)
route_visualizer = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = route_visualizer
spec.loader.exec_module(route_visualizer)


def sample_plan():
    return {
        "schema_version": "simworld.placement_output.v1",
        "region_id": "sample_regions",
        "pedestrian_walkable_lines": [
            {
                "line_id": "walkable_line_region_a_1",
                "vertices": [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]],
                "metadata": {
                    "source": "public_space_layout",
                    "source_region_id": "region_a",
                    "line_role": "main",
                    "flow_pattern": "cross",
                    "length": 10.0,
                },
            },
            {
                "line_id": "walkable_line_region_b_2",
                "vertices": [[1.0, 1.0, 0.0], [4.0, 1.0, 0.0]],
                "metadata": {
                    "source": "public_space_layout",
                    "source_region_id": "region_b",
                    "line_role": "secondary",
                    "length": 3.0,
                },
            },
        ],
        "pedestrian_routes": [
            {
                "route_id": "pedestrian_trip_region_a_001",
                "vertices": [
                    [0.0, 0.0, 0.0],
                    [15.0, 0.0, 0.0],
                    [25.0, 0.0, 0.0],
                ],
                "metadata": {
                    "source": "public_space_trip_generator",
                    "source_region_id": "region_a",
                    "line_role": "trip",
                    "flow_pattern": "cross",
                    "length": 25.0,
                },
            },
            {
                "route_id": "invalid_short_route",
                "vertices": [[1.0, 1.0, 0.0]],
                "metadata": {"source_region_id": "region_a"},
            },
            {
                "route_id": "pedestrian_trip_region_b_002",
                "vertices": [
                    {"x": 1.0, "y": 1.0, "z": 0.0},
                    {"x": 11.0, "y": 1.0, "z": 0.0},
                ],
                "metadata": {
                    "source": "public_space_trip_generator",
                    "source_region_id": "region_b",
                    "line_role": "trip",
                    "length": 10.0,
                },
            },
        ],
        "pedestrian_route_debug": {
            "walkable_line_count": 2,
            "generated_trip_count": 2,
            "skipped_short_component_count": 1,
            "trip_config": {
                "min_trip_length_m": 15.0,
                "target_trip_length_m": 25.0,
                "max_trip_length_m": 40.0,
                "node_merge_tolerance_m": 0.10,
                "max_trips_per_region": 24,
            },
        },
        "dynamic_zones": [
            {
                "geometry": {
                    "coordinates": [
                        [0.0, -0.5, 0.0],
                        [3.0, -0.5, 0.0],
                        [3.0, 0.5, 0.0],
                        [0.0, 0.5, 0.0],
                    ]
                }
            }
        ],
        "static_zones": [],
    }


class PublicSpaceRouteVisualizerTests(unittest.TestCase):
    def test_route_records_skip_invalid_routes_and_compute_status(self):
        routes = route_visualizer.route_records_from_plan(sample_plan())

        self.assertEqual(len(routes), 2)
        self.assertEqual(routes[0].route_id, "pedestrian_trip_region_a_001")
        self.assertEqual(routes[0].region_id, "region_a")
        self.assertEqual(routes[0].line_role, "trip")
        self.assertAlmostEqual(routes[0].length_m, 25.0)
        self.assertEqual(routes[0].status, "ok")
        self.assertEqual(routes[1].vertices, [(1.0, 1.0, 0.0), (11.0, 1.0, 0.0)])
        self.assertEqual(routes[1].status, "short")

    def test_walkable_line_records_are_separate_from_runtime_trips(self):
        lines = route_visualizer.walkable_line_records_from_plan(sample_plan())

        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].line_id, "walkable_line_region_a_1")
        self.assertEqual(lines[0].region_id, "region_a")
        self.assertEqual(lines[0].line_role, "main")
        self.assertAlmostEqual(lines[0].length_m, 10.0)

    def test_region_filter_limits_routes(self):
        routes = route_visualizer.route_records_from_plan(
            sample_plan(),
            region_filters=["region_b"],
        )

        self.assertEqual([route.route_id for route in routes], ["pedestrian_trip_region_b_002"])

    def test_render_route_visualization_html_contains_layers_and_warning_stats(self):
        html = route_visualizer.render_route_visualization_html(
            sample_plan(),
            labels="id",
            show_walkable_lines=True,
            show_zones=True,
            color_by="status",
        )

        self.assertIn("<svg", html)
        self.assertIn("pedestrian_trip_region_a_001", html)
        self.assertIn("pedestrian_trip_region_b_002", html)
        self.assertIn("walkable-line", html)
        self.assertIn("dynamic-zone", html)
        self.assertIn("generated trips", html)
        self.assertIn("skipped short components", html)
        self.assertIn("warnings", html)
        self.assertIn("status-short", html)
        self.assertIn("<table>", html)

    def test_cli_writes_html_from_placement_plan_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "placement_output.json"
            output_path = Path(tmpdir) / "routes.html"
            plan_path.write_text(json.dumps(sample_plan()), encoding="utf-8")

            exit_code = route_visualizer.main(
                [
                    "--placement-plan-json",
                    str(plan_path),
                    "--output",
                    str(output_path),
                    "--labels",
                    "id",
                    "--show-walkable-lines",
                    "--color-by",
                    "status",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(output_path.is_file())
            self.assertIn("Pedestrian Trip Preview", output_path.read_text(encoding="utf-8"))

    def test_cli_writes_html_from_region_input_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "routes.html"
            plan_path = Path(tmpdir) / "placement_output.json"

            exit_code = route_visualizer.main(
                [
                    "--region-input-json",
                    str(PROTO_SAMPLE),
                    "--output",
                    str(output_path),
                    "--write-plan-json",
                    str(plan_path),
                    "--min-trip-length",
                    "1",
                    "--target-trip-length",
                    "5",
                    "--max-trip-length",
                    "10",
                    "--show-walkable-lines",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(output_path.is_file())
            self.assertTrue(plan_path.is_file())
            generated_plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertGreater(len(generated_plan["pedestrian_walkable_lines"]), 0)
            self.assertGreater(len(generated_plan["pedestrian_routes"]), 0)
            self.assertIn("Pedestrian Trip Preview", output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
