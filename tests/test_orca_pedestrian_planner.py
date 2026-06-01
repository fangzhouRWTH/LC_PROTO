from types import SimpleNamespace
import unittest

from engine.dynamic import DynamicActorPlan, DynamicPlanConfig, DynamicPose, DynamicRoutePlan, DynamicScenePlan, DynamicSpeedProfile, DynamicActorShape, build_dynamic_actor_plan
from engine.orca_pedestrian import (
    ObstacleContext,
    PedestrianAgentState,
    build_pedestrian_states_from_plan,
    step_pedestrian_agents,
    validate_pedestrian_actor,
)
import math


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

    def test_route_attraction_pulls_agent_back_toward_polyline(self):
        state = PedestrianAgentState(
            actor_id="pedestrian_off_route",
            radius_m=0.35,
            position=(1.0, 2.5, 0.0),
            waypoints=[(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)],
            target_speed_mps=1.2,
            max_speed_mps=1.2,
        )
        agents = [state]
        for step in range(30):
            step_pedestrian_agents(
                agents,
                ObstacleContext(),
                dt_s=0.1,
                sim_time_s=(step + 1) * 0.1,
            )
        self.assertLess(abs(state.position[1]), 1.5)

    def test_clustered_agents_keep_different_headings(self):
        agents = [
            PedestrianAgentState(
                actor_id="ped_a",
                radius_m=0.35,
                position=(0.0, 0.0, 0.0),
                waypoints=[(-5.0, 0.0, 0.0), (5.0, 0.0, 0.0)],
                target_speed_mps=1.2,
                max_speed_mps=1.2,
            ),
            PedestrianAgentState(
                actor_id="ped_b",
                radius_m=0.35,
                position=(0.1, 0.0, 0.0),
                waypoints=[(0.0, -5.0, 0.0), (0.0, 5.0, 0.0)],
                target_speed_mps=1.2,
                max_speed_mps=1.2,
            ),
            PedestrianAgentState(
                actor_id="ped_c",
                radius_m=0.35,
                position=(-0.1, 0.0, 0.0),
                waypoints=[(5.0, 0.0, 0.0), (-5.0, 0.0, 0.0)],
                target_speed_mps=1.2,
                max_speed_mps=1.2,
            ),
        ]
        for step in range(40):
            step_pedestrian_agents(
                agents,
                ObstacleContext(),
                dt_s=0.05,
                sim_time_s=(step + 1) * 0.05,
            )

        headings = [
            math.atan2(agent.velocity[1], agent.velocity[0])
            for agent in agents
            if math.hypot(agent.velocity[0], agent.velocity[1]) > 0.05
        ]
        self.assertGreaterEqual(len(headings), 2)
        spread = max(headings) - min(headings)
        self.assertGreater(abs(spread), 0.3)

    def test_neighbors_outside_min_separation_do_not_attract(self):
        agents = [
            PedestrianAgentState(
                actor_id="ped_a",
                radius_m=0.35,
                position=(0.0, 0.0, 0.0),
                target_speed_mps=1.2,
                max_speed_mps=1.2,
            ),
            PedestrianAgentState(
                actor_id="ped_b",
                radius_m=0.35,
                position=(1.0, 0.0, 0.0),
                target_speed_mps=1.2,
                max_speed_mps=1.2,
            ),
        ]
        initial_distance = math.hypot(
            agents[1].position[0] - agents[0].position[0],
            agents[1].position[1] - agents[0].position[1],
        )

        step_pedestrian_agents(
            agents,
            ObstacleContext(agent_neighbor_radius_m=4.0),
            dt_s=0.1,
            sim_time_s=0.1,
        )
        final_distance = math.hypot(
            agents[1].position[0] - agents[0].position[0],
            agents[1].position[1] - agents[0].position[1],
        )

        self.assertGreaterEqual(final_distance, initial_distance)


if __name__ == "__main__":
    unittest.main()
