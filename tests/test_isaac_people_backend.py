import unittest

from engine.dynamic import (
    DynamicActorPlan,
    DynamicActorShape,
    DynamicPose,
    DynamicRoutePlan,
    DynamicScenePlan,
    DynamicSpeedProfile,
)
from isaac_env.isaac_agents import factory
from isaac_env.isaac_agents.backends.isaac_people import (
    IsaacPeopleDynamicAgentBackend,
    character_name_for_index,
    people_command_lines_for_route,
)
from isaac_env.isaac_agents.backends.isaac_people_sumo import (
    IsaacPeopleSumoDynamicAgentBackend,
)


def _actor(actor_id, actor_type, route):
    shape = (
        DynamicActorShape(length_m=4.5, width_m=1.8, height_m=1.6)
        if actor_type == "vehicle"
        else DynamicActorShape(radius_m=0.35, height_m=1.7)
    )
    return DynamicActorPlan(
        actor_id=actor_id,
        actor_type=actor_type,
        route=route,
        speed_mps=1.0,
        spawn_pose=DynamicPose(position=route[0]),
        goal_pose=DynamicPose(position=route[-1]),
        route_id=f"{actor_type}_route",
        route_plan=DynamicRoutePlan(
            route_id=f"{actor_type}_route",
            route_type="waypoints",
            route_mode="once",
            waypoints=route,
        ),
        speed_profile=DynamicSpeedProfile(target_speed_mps=1.0, max_speed_mps=1.0),
        shape=shape,
    )


class IsaacPeopleBackendTest(unittest.TestCase):
    def test_character_names_match_omni_anim_people_convention(self):
        self.assertEqual(character_name_for_index(0), "Character")
        self.assertEqual(character_name_for_index(1), "Character_01")
        self.assertEqual(character_name_for_index(9), "Character_09")
        self.assertEqual(character_name_for_index(10), "Character_10")

    def test_people_command_lines_follow_route_waypoints(self):
        lines = people_command_lines_for_route(
            "Character",
            [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0)],
            final_idle_s=3.0,
        )

        self.assertEqual(
            lines,
            [
                "Character GoTo 2 0 0 0",
                "Character GoTo 2 2 0 90",
                "Character Idle 3",
            ],
        )

    def test_isaac_people_backend_builds_only_pedestrian_commands(self):
        plan = DynamicScenePlan(
            actors=[
                _actor("pedestrian_001", "pedestrian", [(0, 0, 0), (1, 0, 0)]),
                _actor("vehicle_001", "vehicle", [(0, 0, 0), (2, 0, 0)]),
            ]
        )
        backend = IsaacPeopleDynamicAgentBackend()

        backend.build_from_plan(plan)

        self.assertEqual(backend.actor_count, 1)
        self.assertEqual(backend.actors[0].character_name, "Character")
        self.assertEqual(backend.actors[0].command_lines[0], "Character GoTo 1 0 0 0")

    def test_isaac_people_sumo_composite_splits_plan(self):
        plan = DynamicScenePlan(
            actors=[
                _actor("pedestrian_001", "pedestrian", [(0, 0, 0), (1, 0, 0)]),
                _actor("vehicle_001", "vehicle", [(0, 0, 0), (2, 0, 0)]),
            ]
        )
        backend = IsaacPeopleSumoDynamicAgentBackend()

        backend.build_from_plan(plan)

        self.assertEqual(backend.pedestrian_backend.actor_count, 1)
        self.assertEqual(backend.vehicle_backend.actor_count, 1)

    def test_factory_exposes_isaac_people_backends(self):
        self.assertIn("isaac_people", factory.available_dynamic_agent_backends())
        self.assertIn("isaac_people_sumo", factory.available_dynamic_agent_backends())


if __name__ == "__main__":
    unittest.main()
