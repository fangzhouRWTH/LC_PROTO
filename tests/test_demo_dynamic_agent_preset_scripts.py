from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DemoDynamicAgentPresetScriptsTest(unittest.TestCase):
    def test_build_runtime_presets_writes_people_vehicle_env(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            people_dir = temp / "people"
            output_dir = temp / "runtime"
            people_dir.mkdir()
            for scenario in ("people_1", "people_2"):
                (people_dir / f"demo_{scenario}_placement_plan.json").write_text(
                    json.dumps({"pedestrian_routes": [{"vertices": [[0, 0, 0], [1, 0, 0]]}]}) + "\n",
                    encoding="utf-8",
                )
            people_config = temp / "people_config.json"
            people_config.write_text(
                json.dumps(
                    {
                        "schema_version": "simworld.demo_people_scenarios.v1",
                        "defaults": {"actor_count": 0},
                        "scenarios": {
                            "people_1": {"actor_count": 6},
                            "people_2": {"actor_count": 10},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            agent_config = temp / "agent_config.json"
            agent_config.write_text(
                json.dumps(
                    {
                        "schema_version": "simworld.demo_dynamic_agent_scenarios.v1",
                        "defaults": {
                            "max_vehicle_actors": 2,
                            "vehicles_per_line": 1,
                            "vehicle_speed_mps": 8.0,
                            "vehicle_spawn_interval_s": 6.0,
                            "ignore_people_spawn_time": True,
                        },
                        "scenarios": {
                            "people_2": {
                                "max_vehicle_actors": 5,
                                "vehicles_per_line": 3,
                                "vehicle_speed_mps": 9.5,
                            }
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            summary = temp / "summary.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "build_demo_agent_runtime_presets.py"),
                    "--scene-usd",
                    str(ROOT / "assets" / "blocks" / "demo_scene.usdc"),
                    "--people-plan-dir",
                    str(people_dir),
                    "--preset-prefix",
                    "demo",
                    "--output-dir",
                    str(output_dir),
                    "--people-config",
                    str(people_config),
                    "--agent-config",
                    str(agent_config),
                    "--summary-json",
                    str(summary),
                    "--scenario",
                    "people_1",
                    "--scenario",
                    "people_2",
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            people_2 = json.loads(
                (output_dir / "demo_people_2_dynamic_agent_preset.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(people_2["people"]["visible_actor_count"], 10)
            self.assertEqual(people_2["vehicles"]["max_vehicle_actors"], 5)
            self.assertEqual(people_2["vehicles"]["vehicles_per_line"], 3)
            self.assertEqual(people_2["environment"]["DYNAMIC_VEHICLE_SPEED_MPS"], "9.5")
            self.assertEqual(people_2["environment"]["DEMO_PEOPLE_SCENARIO"], "people_2")
            self.assertIn("dynamic_routes_json", people_2)
            self.assertIn("DYNAMIC_ROUTES_JSON", people_2["environment"])
            dynamic_routes = output_dir / "demo_people_2_dynamic_routes.json"
            self.assertTrue(dynamic_routes.exists())
            dynamic_payload = json.loads(dynamic_routes.read_text(encoding="utf-8"))
            self.assertEqual(dynamic_payload["schema_version"], "simworld.dynamic_routes.v1")
            self.assertNotIn("placements", dynamic_payload)
            self.assertEqual(len(dynamic_payload["pedestrian_routes"]), 1)
            self.assertTrue(summary.exists())

    def test_run_preset_builds_expected_environment(self):
        module_path = ROOT / "scripts" / "run_demo_dynamic_agent_preset.py"
        spec = importlib.util.spec_from_file_location("run_demo_dynamic_agent_preset", module_path)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)

        preset = {
            "scenario": "people_4",
            "scene_usd": "assets/blocks/demo_scene.usdc",
            "placement_plan_json": "configs/demo_agents/generated/demo/demo_people_4_placement_plan.json",
            "dynamic_routes_json": "configs/demo_agents/generated/demo/demo_people_4_dynamic_routes.json",
            "environment": {
                "DYNAMIC_MAX_VEHICLE_ACTORS": "5",
                "DYNAMIC_VEHICLES_PER_LINE": "2",
            },
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            preset_path = Path(temp_dir) / "preset.json"
            preset_path.write_text(json.dumps(preset), encoding="utf-8")
            env = module._build_env(preset, preset_path)

        self.assertEqual(env["DEMO_PEOPLE_SCENARIO"], "people_4")
        self.assertNotIn("DEMO_PEOPLE_USE_STATIC_PLAN", env)
        self.assertEqual(env["DYNAMIC_MAX_VEHICLE_ACTORS"], "5")
        self.assertTrue(
            env["DYNAMIC_ROUTES_JSON"].endswith(
                "configs/demo_agents/generated/demo/demo_people_4_dynamic_routes.json"
            )
        )
        self.assertTrue(env["SCENE_USD"].endswith("assets/blocks/demo_scene.usdc"))
        self.assertNotIn("DEMO_PEOPLE_PLACEMENT_PLAN", env)


if __name__ == "__main__":
    unittest.main()
