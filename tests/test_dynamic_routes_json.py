from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dataclasses import dataclass, field

from isaac_env.isaac_scene.dynamic_routes_json import apply_dynamic_routes_json


@dataclass
class FakePath:
    vertices: list[list[float]] = field(default_factory=list)
    prim_path: str = ""


@dataclass
class FakeArea:
    vertices: list[list[float]] = field(default_factory=list)


@dataclass
class FakeStats:
    spawn_points: list[list[float]] = field(default_factory=list)
    placeholder_areas: list[FakeArea] = field(default_factory=list)
    pedestrian_spawn_points: list[object] = field(default_factory=list)
    pedestrian_goal_points: list[object] = field(default_factory=list)
    pedestrian_routes: list[object] = field(default_factory=list)
    pedestrian_zones: list[object] = field(default_factory=list)
    vehicle_spawn_points: list[object] = field(default_factory=list)
    vehicle_goal_points: list[object] = field(default_factory=list)
    vehicle_routes: list[object] = field(default_factory=list)
    vehicle_lanes: list[object] = field(default_factory=list)


class DynamicRoutesJsonTest(unittest.TestCase):
    def test_dynamic_routes_json_replaces_only_dynamic_route_fields(self):
        stats = FakeStats()
        stats.spawn_points.append([9.0, 9.0, 0.8])
        stats.placeholder_areas.append(
            FakeArea(vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0]])
        )
        stats.pedestrian_routes.append(
            FakePath(vertices=[[100, 0, 0], [101, 0, 0]], prim_path="/World/old_ped_route")
        )
        stats.vehicle_routes.append(
            FakePath(vertices=[[200, 0, 0], [201, 0, 0]], prim_path="/World/old_vehicle_line")
        )

        payload = {
            "schema_version": "simworld.dynamic_routes.v1",
            "replace_existing": True,
            "pedestrian_routes": [
                {"route_id": "ped_a", "waypoints": [[0, 0, 0], [2, 0, 0]]}
            ],
            "vehicle_routes": [
                {"route_id": "veh_a", "vertices": [[0, 1, 0], [3, 1, 0]], "index": "001"}
            ],
            "vehicle_lanes": [
                {
                    "vertices": [[0, 0, 0], [3, 0, 0], [3, 2, 0], [0, 2, 0]],
                    "index": "001",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "routes.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = apply_dynamic_routes_json(stats, path)

        self.assertEqual(result.pedestrian_route_count, 1)
        self.assertEqual(result.vehicle_route_count, 1)
        self.assertEqual(result.vehicle_lane_count, 1)
        self.assertEqual(stats.spawn_points, [[9.0, 9.0, 0.8]])
        self.assertEqual(len(stats.placeholder_areas), 1)
        self.assertEqual(stats.pedestrian_routes[0]["route_id"], "ped_a")
        self.assertEqual(stats.vehicle_routes[0]["route_id"], "veh_a")
        self.assertEqual(stats.vehicle_lanes[0]["index"], "001")

    def test_dynamic_routes_json_can_append_when_requested(self):
        stats = FakeStats()
        stats.pedestrian_routes.append(
            FakePath(vertices=[[0, 0, 0], [1, 0, 0]])
        )
        payload = {
            "replace_existing": False,
            "pedestrian_routes": [{"vertices": [[2, 0, 0], [3, 0, 0]]}],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "routes.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            apply_dynamic_routes_json(stats, path)

        self.assertEqual(len(stats.pedestrian_routes), 2)


if __name__ == "__main__":
    unittest.main()
