import json
import unittest
from pathlib import Path

from engine.demo_pedestrian_scenarios import apply_demo_people_scenario


def route(route_id, y=0.0, region="region_a"):
    return {
        "route_id": route_id,
        "vertices": [[0.0, y, 0.0], [20.0, y, 0.0]],
        "metadata": {
            "source": "public_space_trip_generator",
            "source_region_id": region,
            "length": 20.0,
        },
    }


def walkable_line(line_id, vertices, region="region_a"):
    return {
        "line_id": line_id,
        "vertices": vertices,
        "metadata": {
            "source": "public_space_layout",
            "source_region_id": region,
            "line_role": "main",
        },
    }


def zone(x0, y0, x1, y1):
    return {
        "geometry": {
            "coordinates": [
                [x0, y0, 0.0],
                [x1, y0, 0.0],
                [x1, y1, 0.0],
                [x0, y1, 0.0],
                [x0, y0, 0.0],
            ]
        }
    }


class DemoPedestrianScenarioTests(unittest.TestCase):
    def test_busy_scenario_generates_offset_routes_inside_dynamic_zones(self):
        plan = {
            "pedestrian_routes": [
                route("r1", y=0.0, region="a"),
                route("r2", y=4.0, region="b"),
                route("r3", y=8.0, region="c"),
                route("r4", y=12.0, region="d"),
            ],
            "dynamic_zones": [
                zone(0.0, -1.5, 20.0, 1.5),
                zone(0.0, 2.5, 20.0, 5.5),
                zone(0.0, 6.5, 20.0, 9.5),
                zone(0.0, 10.5, 20.0, 13.5),
            ],
        }
        config = {
            "default_scenario": "busy",
            "defaults": {
                "offset_candidates_m": [0.0, -0.65, 0.65],
                "route_clearance_m": 1.5,
                "parallel_route_clearance_m": 0.5,
                "zone_margin_m": 0.35,
                "zone_sample_spacing_m": 1.0,
                "speed_mps": 1.25,
                "route_mode": "once",
            },
            "scenarios": {"busy": {"actor_count": 12}},
        }

        processed = apply_demo_people_scenario(plan, config)

        routes = processed["pedestrian_routes"]
        self.assertEqual(len(routes), 12)
        self.assertEqual(processed["demo_people_scenario_debug"]["scenario"], "busy")
        self.assertTrue(all(r["metadata"]["demo_only"] for r in routes))
        self.assertIn(-0.65, {r["metadata"]["offset_m"] for r in routes})
        self.assertIn(0.65, {r["metadata"]["offset_m"] for r in routes})
        self.assertTrue(all(r["metadata"]["route_mode"] == "once" for r in routes))
        self.assertTrue(all(r["metadata"]["speed_mps"] == 1.25 for r in routes))

    def test_reapplying_scenario_uses_saved_source_routes(self):
        plan = {
            "pedestrian_routes": [
                route("r1", y=0.0, region="a"),
                route("r2", y=4.0, region="b"),
            ],
            "dynamic_zones": [
                zone(0.0, -1.5, 20.0, 1.5),
                zone(0.0, 2.5, 20.0, 5.5),
            ],
        }
        config = {
            "default_scenario": "quiet",
            "defaults": {
                "offset_candidates_m": [0.0, -0.65, 0.65],
                "parallel_route_clearance_m": 0.5,
                "zone_margin_m": 0.35,
                "route_mode": "once",
            },
            "scenarios": {
                "quiet": {"actor_count": 2, "offset_candidates_m": [0.0]},
                "busy": {"actor_count": 6},
            },
        }

        quiet = apply_demo_people_scenario(plan, config, scenario_name="quiet")
        busy = apply_demo_people_scenario(quiet, config, scenario_name="busy")

        self.assertEqual(len(quiet["pedestrian_routes"]), 2)
        self.assertEqual(len(quiet["pedestrian_demo_source_routes"]), 2)
        self.assertEqual(len(busy["pedestrian_routes"]), 6)
        self.assertTrue(
            all(
                route["metadata"]["parent_route_id"] in {"r1", "r2"}
                for route in busy["pedestrian_routes"]
            )
        )


    def test_walkable_graph_source_generates_long_demo_routes(self):
        plan = {
            "pedestrian_routes": [route("short", y=0.0)],
            "pedestrian_walkable_lines": [
                walkable_line(
                    "long_block",
                    [[0.0, 0.0, 0.0], [120.0, 0.0, 0.0]],
                    region="block",
                )
            ],
            "dynamic_zones": [zone(-1.0, -2.0, 121.0, 2.0)],
        }
        config = {
            "default_scenario": "people_01",
            "defaults": {
                "route_source": "walkable_lines",
                "offset_candidates_m": [0.0],
                "zone_margin_m": 0.05,
                "min_route_length_m": 60.0,
                "target_route_length_m": 95.0,
                "max_route_length_m": 100.0,
                "route_clearance_m": 0.0,
                "route_mode": "once",
            },
            "scenarios": {"people_01": {"actor_count": 1}},
        }

        processed = apply_demo_people_scenario(plan, config)

        routes = processed["pedestrian_routes"]
        self.assertEqual(len(routes), 1)
        self.assertGreaterEqual(routes[0]["metadata"]["length"], 95.0)
        self.assertEqual(
            processed["pedestrian_demo_source_routes"][0]["metadata"]["source"],
            "demo_people_walkable_graph",
        )
        self.assertTrue(
            processed["demo_people_scenario_debug"]["source_generation"][
                "used_walkable_graph"
            ]
        )

    def test_walkable_graph_source_balances_regions_before_truncating(self):
        plan = {
            "pedestrian_walkable_lines": [
                walkable_line(
                    "a_east",
                    [[0.0, 0.0, 0.0], [120.0, 0.0, 0.0]],
                    region="region_a",
                ),
                walkable_line(
                    "a_north",
                    [[0.0, 0.0, 0.0], [0.0, 120.0, 0.0]],
                    region="region_a",
                ),
                walkable_line(
                    "a_west",
                    [[0.0, 0.0, 0.0], [-120.0, 0.0, 0.0]],
                    region="region_a",
                ),
                walkable_line(
                    "b_main",
                    [[0.0, 20.0, 0.0], [120.0, 20.0, 0.0]],
                    region="region_b",
                ),
            ],
            "dynamic_zones": [zone(-121.0, -2.0, 121.0, 122.0)],
        }
        config = {
            "default_scenario": "balanced",
            "defaults": {
                "route_source": "walkable_lines",
                "offset_candidates_m": [0.0],
                "zone_margin_m": 0.0,
                "min_route_length_m": 60.0,
                "target_route_length_m": 110.0,
                "max_route_length_m": 120.0,
                "max_source_routes": 2,
                "max_source_routes_per_region": 8,
                "route_clearance_m": 0.0,
                "parallel_route_clearance_m": 0.0,
                "collision_rehearsal": {"enabled": False},
            },
            "scenarios": {"balanced": {"actor_count": 2}},
        }

        processed = apply_demo_people_scenario(plan, config)

        selected_regions = {
            route["metadata"]["source_region_id"]
            for route in processed["pedestrian_routes"]
        }
        self.assertEqual(selected_regions, {"region_a", "region_b"})
        source_regions = {
            route["metadata"]["source_region_id"]
            for route in processed["pedestrian_demo_source_routes"]
        }
        self.assertEqual(source_regions, {"region_a", "region_b"})
        self.assertTrue(
            processed["demo_people_scenario_debug"]["source_generation"][
                "walkable_source_config"
            ]["balance_source_routes_by_region"]
        )

    def test_demo_routes_can_prefer_pedestrian_routes_near_vehicle_lines(self):
        plan = {
            "pedestrian_routes": [
                {
                    "route_id": "far",
                    "vertices": [[100.0, 0.0, 0.0], [120.0, 0.0, 0.0]],
                    "metadata": {"source_region_id": "far_region"},
                },
                {
                    "route_id": "near",
                    "vertices": [[0.0, 3.0, 0.0], [20.0, 3.0, 0.0]],
                    "metadata": {"source_region_id": "near_region"},
                },
            ],
            "vehicle_routes": [
                {
                    "route_id": "vehicle",
                    "vertices": [[0.0, 0.0, 0.0], [20.0, 0.0, 0.0]],
                }
            ],
            "dynamic_zones": [zone(-1.0, -1.0, 121.0, 5.0)],
        }
        config = {
            "default_scenario": "near_vehicle",
            "defaults": {
                "offset_candidates_m": [0.0],
                "prefer_routes_near_vehicle_routes": True,
                "zone_margin_m": 0.0,
                "route_clearance_m": 0.0,
                "parallel_route_clearance_m": 0.0,
            },
            "scenarios": {"near_vehicle": {"actor_count": 1}},
        }

        processed = apply_demo_people_scenario(plan, config)

        self.assertEqual(
            processed["pedestrian_routes"][0]["metadata"]["parent_route_id"],
            "near",
        )
        self.assertTrue(
            processed["demo_people_scenario_debug"][
                "prefer_routes_near_vehicle_routes"
            ]
        )

    def test_speed_and_spawn_are_deterministic_but_varied(self):
        plan = {
            "pedestrian_routes": [
                route("r1", y=0.0, region="a"),
                route("r2", y=4.0, region="b"),
                route("r3", y=8.0, region="c"),
                route("r4", y=12.0, region="d"),
            ],
            "dynamic_zones": [
                zone(0.0, -1.0, 20.0, 1.0),
                zone(0.0, 3.0, 20.0, 5.0),
                zone(0.0, 7.0, 20.0, 9.0),
                zone(0.0, 11.0, 20.0, 13.0),
            ],
        }
        config = {
            "default_scenario": "people_04",
            "defaults": {
                "offset_candidates_m": [0.0],
                "route_clearance_m": 0.0,
                "zone_margin_m": 0.05,
                "speed_range_mps": [0.8, 1.6],
                "spawn_stagger_range_s": [0.3, 0.9],
                "start_offset_range_m": [1.0, 5.0],
                "route_mode": "once",
            },
            "scenarios": {"people_04": {"actor_count": 4}},
        }

        first = apply_demo_people_scenario(plan, config)
        second = apply_demo_people_scenario(plan, config)

        first_metadata = [route["metadata"] for route in first["pedestrian_routes"]]
        second_metadata = [route["metadata"] for route in second["pedestrian_routes"]]
        self.assertEqual(
            [item["speed_mps"] for item in first_metadata],
            [item["speed_mps"] for item in second_metadata],
        )
        self.assertEqual(
            [item["start_offset_m"] for item in first_metadata],
            [item["start_offset_m"] for item in second_metadata],
        )
        speeds = [item["speed_mps"] for item in first_metadata]
        spawn_times = [item["spawn_time_s"] for item in first_metadata]
        start_offsets = [item["start_offset_m"] for item in first_metadata]
        self.assertEqual(len(set(round(value, 4) for value in speeds)), 4)
        self.assertTrue(all(0.8 <= value <= 1.6 for value in speeds))
        self.assertEqual(spawn_times[0], 0.0)
        self.assertEqual(spawn_times, sorted(spawn_times))
        self.assertGreater(spawn_times[-1], 0.0)
        self.assertTrue(all(1.0 <= value <= 5.0 for value in start_offsets))
        self.assertGreater(len(set(round(value, 4) for value in start_offsets)), 1)

    def test_tencent_people_count_config_exposes_six_scenarios(self):
        config_path = (
            Path(__file__).resolve().parents[1]
            / "configs"
            / "demo_people"
            / "tencent_dynamic_people_scenarios.json"
        )
        config = json.loads(config_path.read_text())

        expected_counts = {
            "people_1": 6,
            "people_2": 10,
            "people_3": 16,
            "people_4": 22,
            "people_5": 30,
            "people_6": 40,
        }
        self.assertEqual(config["default_scenario"], "people_3")
        self.assertEqual(
            {key: config["scenarios"][key]["actor_count"] for key in expected_counts},
            expected_counts,
        )
        self.assertEqual(config["defaults"]["route_source"], "walkable_lines")
        self.assertIn("start_offset_range_m", config["defaults"])

    def test_offset_candidate_outside_dynamic_zone_is_rejected(self):
        plan = {
            "pedestrian_routes": [route("narrow", y=0.0)],
            "dynamic_zones": [zone(0.0, -0.4, 20.0, 0.4)],
        }
        config = {
            "default_scenario": "normal",
            "defaults": {
                "offset_candidates_m": [0.0, -0.65, 0.65],
                "zone_margin_m": 0.35,
                "parallel_route_clearance_m": 0.5,
            },
            "scenarios": {"normal": {"actor_count": 3}},
        }

        processed = apply_demo_people_scenario(plan, config)

        routes = processed["pedestrian_routes"]
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0]["metadata"]["offset_m"], 0.0)
        reasons = {
            item["reason"]
            for item in processed["demo_people_scenario_debug"]["rejected_candidates"]
        }
        self.assertIn("outside_dynamic_zone", reasons)


if __name__ == "__main__":
    unittest.main()
