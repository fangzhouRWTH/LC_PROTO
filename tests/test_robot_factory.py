import unittest

from isaac_env.isaac_robots import factory


class RobotFactoryTest(unittest.TestCase):
    def test_noop_robot_is_available_for_scene_only_demos(self):
        self.assertIn("none", factory.available_robot_types())
        robot = factory.create_robot("none", "demo")

        robot.spawn((0.0, 0.0, 0.0))
        robot.forward(1.0)
        robot.step((0.0, 0.0, 0.0))

        self.assertTrue(robot.initialized)
        self.assertFalse(robot.need_reinit)
        self.assertEqual(robot.root_prim_path, "/World")

    def test_go2_robot_type_is_registered(self):
        available = factory.available_robot_types()
        self.assertIn("go2", available)
        self.assertIn("unitree_go2", available)


if __name__ == "__main__":
    unittest.main()
