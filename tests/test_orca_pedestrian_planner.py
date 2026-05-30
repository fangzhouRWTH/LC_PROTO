from types import SimpleNamespace
import unittest

from engine.dynamic import DynamicActorPlan, DynamicPlanConfig, DynamicPose, DynamicRoutePlan, DynamicScenePlan, DynamicSpeedProfile, DynamicActorShape, build_dynamic_actor_plan
from engine.orca_pedestrian import (
    ObstacleContext,
    build_pedestrian_states_from_plan,
    step_pedestrian_agents,
    validate_pedestrian_actor,
)


def _pedestrian_actor(**overrides):
    base = DynamicActorPlan(
        actor_id="pedestrian_001",
        actor_type="pedestrian",
        route=[(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)],
        speed_mps=1.2,
        spawn_pose=DynamicPose(position=(0.0, 0.0, 0.0)),
        goal_pose=DynamicPose(position=(4.0, 0.0, 0.0)),
        route_plan=DynamicRoutePlan(
            route_id="pedestrian_route_001",
            route_type="waypoints",
            route_mode="once",
            waypoints=[(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)],
        ),
        speed_profile=DynamicSpeedProfile(target_speed_mps=1.2, max_speed_mps=1.2),
        shape=DynamicActorShape(radius_m=0.35, height_m=1.7),
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


class OrcaPedestrianPlannerTest(unittest.TestCase):
    def test_validate_pedestrian_actor_requires_orca_fields(self):
        actor = _pedestrian_actor()
        self.assertEqual(validate_pedestrian_actor(actor), [])

        invalid = _pedestrian_actor(route_plan=None)
        self.assertIn("route_plan", validate_pedestrian_actor(invalid))

    def test_build_states_from_dynamic_scene_plan(self):
        plan = DynamicScenePlan(actors=[_pedestrian_actor()])
        warnings: list[str] = []
        states = build_pedestrian_states_from_plan(plan, warnings)
        self.assertEqual(warnings, [])
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0].position, (0.0, 0.0, 0.0))

    def test_step_moves_pedestrian_toward_goal(self):
        plan = DynamicScenePlan(actors=[_pedestrian_actor()])
        states = build_pedestrian_states_from_plan(plan)
        step_pedestrian_agents(states, ObstacleContext(), dt_s=0.5, sim_time_s=0.5)
        self.assertGreater(states[0].position[0], 0.0)

    def test_build_dynamic_plan_feeds_orca_states(self):
        stats = SimpleNamespace(
            pedestrian_spawn_points=[
                SimpleNamespace(position=[0.0, 0.0, 0.0], prim_path="/World/spawn", index="001"),
            ],
            pedestrian_goal_points=[
                SimpleNamespace(position=[3.0, 0.0, 0.0], prim_path="/World/goal", index="001"),
            ],
        )
        plan = build_dynamic_actor_plan(
            stats,
            DynamicPlanConfig(max_pedestrian_actors=1, max_vehicle_actors=0),
        )
        states = build_pedestrian_states_from_plan(plan)
        self.assertEqual(len(states), 1)


if __name__ == "__main__":
    unittest.main()
