import unittest

from scripts.export_dynamic_plan import build_export_payload


class ExportDynamicPlanTest(unittest.TestCase):
    def test_build_export_payload_accepts_json_dict_scene_stats(self):
        payload = {
            "plan_config": {
                "max_pedestrian_actors": 1,
                "max_vehicle_actors": 1,
                "default_route_mode": "once",
            },
            "scene_stats": {
                "pedestrian_spawn_points": [
                    {
                        "position": [0.0, 0.0, 0.0],
                        "prim_path": "/World/ped_spawn_001",
                        "index": "001",
                    }
                ],
                "pedestrian_goal_points": [
                    {
                        "position": [2.0, 0.0, 0.0],
                        "prim_path": "/World/ped_goal_001",
                        "index": "001",
                    }
                ],
                "vehicle_routes": [
                    {
                        "vertices": [
                            [-8.0, -1.0, 0.0],
                            [8.0, -1.0, 0.0],
                        ],
                        "prim_path": "/World/vehicle_route_001",
                        "raw_name": "placeholder_vehicle_route_001",
                        "index": "001",
                    }
                ],
                "vehicle_lanes": [
                    {
                        "vertices": [
                            [-8.0, -2.0, 0.0],
                            [8.0, -2.0, 0.0],
                            [8.0, 0.0, 0.0],
                            [-8.0, 0.0, 0.0],
                        ],
                        "prim_path": "/World/vehicle_lane_001",
                        "raw_name": "placeholder_vehicle_lane_001",
                        "index": "001",
                    }
                ],
            },
        }

        export_payload = build_export_payload(payload)

        self.assertEqual(export_payload["schema_version"], "dynamic_scene_plan.v0")
        self.assertEqual(len(export_payload["actors"]), 2)
        self.assertEqual(len(export_payload["lanes"]), 1)
        pedestrian, vehicle = export_payload["actors"]
        self.assertEqual(pedestrian["route_plan"]["route_mode"], "once")
        self.assertEqual(vehicle["route_plan"]["lane_ids"], ["vehicle_lane_001"])
        self.assertEqual(export_payload["warnings"], [])


if __name__ == "__main__":
    unittest.main()
