from dataclasses import dataclass, field
import unittest

from engine.camera_path import (
    CameraPathPlanConfig,
    build_camera_path_plan,
    look_at_pose_along_path,
    position_along_path,
)


@dataclass
class PathPlaceholder:
    vertices: list[list[float]] = field(default_factory=list)
    prim_path: str = ""
    raw_name: str = ""
    index: str = ""


@dataclass
class SceneStatsStub:
    camera_paths: list[PathPlaceholder] = field(default_factory=list)


class CameraPathPlanTests(unittest.TestCase):
    def test_build_camera_path_plan_from_placeholder(self):
        stats = SceneStatsStub(
            camera_paths=[
                PathPlaceholder(
                    vertices=[[0.0, 0.0, 2.0], [10.0, 0.0, 2.0], [10.0, 10.0, 2.0]],
                    prim_path="/World/placeholder_path_camera_001",
                    raw_name="placeholder_path_camera_001",
                    index="001",
                )
            ]
        )

        plan = build_camera_path_plan(stats, config=CameraPathPlanConfig(speed_mps=3.0))

        self.assertEqual(len(plan.paths), 1)
        self.assertEqual(plan.paths[0].path_id, "camera_path_001")
        self.assertEqual(len(plan.paths[0].waypoints), 3)
        self.assertEqual(plan.paths[0].speed_mps, 3.0)
        self.assertEqual(plan.paths[0].source_prim_path, "/World/placeholder_path_camera_001")

    def test_build_camera_path_plan_warns_on_short_path(self):
        stats = SceneStatsStub(
            camera_paths=[
                PathPlaceholder(
                    vertices=[[0.0, 0.0, 1.0]],
                    prim_path="/World/placeholder_path_camera_002",
                    index="002",
                )
            ]
        )

        plan = build_camera_path_plan(stats)

        self.assertEqual(plan.paths, [])
        self.assertEqual(len(plan.warnings), 1)

    def test_position_along_path_interpolates(self):
        waypoints = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0))

        position = position_along_path(waypoints, 5.0, route_mode="once")

        self.assertAlmostEqual(position[0], 5.0)
        self.assertAlmostEqual(position[1], 0.0)

    def test_look_at_pose_along_path_interpolates(self):
        waypoints = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0))

        eye, target = look_at_pose_along_path(waypoints, 5.0, route_mode="once")

        self.assertAlmostEqual(eye[0], 5.0)
        self.assertAlmostEqual(eye[1], 0.0)
        self.assertAlmostEqual(target[0], 10.0)
        self.assertAlmostEqual(target[1], 0.0)

    def test_look_at_pose_along_path_loops(self):
        waypoints = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0))

        eye, _ = look_at_pose_along_path(waypoints, 15.0, route_mode="loop")

        self.assertAlmostEqual(eye[0], 5.0)


    def test_build_camera_path_plan_supports_multiple_paths(self):
        stats = SceneStatsStub(
            camera_paths=[
                PathPlaceholder(
                    vertices=[[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]],
                    index="001",
                ),
                PathPlaceholder(
                    vertices=[[0.0, 10.0, 0.0], [10.0, 10.0, 0.0]],
                    index="002",
                ),
            ]
        )

        plan = build_camera_path_plan(stats)

        self.assertEqual(len(plan.paths), 2)
        self.assertEqual(plan.paths[0].path_id, "camera_path_001")
        self.assertEqual(plan.paths[1].path_id, "camera_path_002")


if __name__ == "__main__":
    unittest.main()
