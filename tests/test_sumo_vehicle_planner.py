from types import SimpleNamespace
import unittest

from engine.dynamic import (
    DynamicActorPlan,
    DynamicLanePlan,
    DynamicPlanConfig,
    DynamicRoutePlan,
    DynamicScenePlan,
    DynamicSpeedProfile,
    DynamicActorShape,
    build_dynamic_actor_plan,
)
from engine.sumo_vehicle import (
    TrafficConfig,
    build_vehicle_states_from_plan,
    step_vehicle_agents,
    validate_vehicle_actor,
)


def _vehicle_actor(**overrides):
    base = DynamicActorPlan(
        actor_id="vehicle_001",
        actor_type="vehicle",
        route=[(-8.0, -1.0, 0.0), (8.0, -1.0, 0.0)],
        speed_mps=4.0,
        route_id="vehicle_route_001",
        route_plan=DynamicRoutePlan(
            route_id="vehicle_route_001",
            route_type="waypoints",
            route_mode="once",
            waypoints=[(-8.0, -1.0, 0.0), (8.0, -1.0, 0.0)],
            lane_ids=["vehicle_lane_001"],
        ),
        speed_profile=DynamicSpeedProfile(target_speed_mps=4.0, max_speed_mps=4.0),
        shape=DynamicActorShape(length_m=4.5, width_m=1.8, height_m=1.6),
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


class SumoVehiclePlannerTest(unittest.TestCase):
    def test_validate_vehicle_actor_requires_sumo_fields(self):
        lane_ids = {"vehicle_lane_001"}
        actor = _vehicle_actor()
        self.assertEqual(validate_vehicle_actor(actor, lane_ids), [])

        invalid = _vehicle_actor(route_plan=None)
        self.assertIn("route_plan", validate_vehicle_actor(invalid, lane_ids))

    def test_build_states_uses_lane_centerline(self):
        plan = DynamicScenePlan(
            lanes=[
                DynamicLanePlan(
                    lane_id="vehicle_lane_001",
                    polygon=[(-8.0, -2.0, 0.0), (8.0, -2.0, 0.0), (8.0, 0.0, 0.0), (-8.0, 0.0, 0.0)],
                    centerline=[(-8.0, -1.0, 0.0), (8.0, -1.0, 0.0)],
                    width_m=2.0,
                )
            ],
            actors=[_vehicle_actor()],
        )
        warnings: list[str] = []
        states = build_vehicle_states_from_plan(plan, warnings)
        self.assertEqual(warnings, [])
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0].path, [(-8.0, -1.0, 0.0), (8.0, -1.0, 0.0)])

    def test_step_moves_vehicle_along_path(self):
        plan = DynamicScenePlan(
            lanes=[
                DynamicLanePlan(
                    lane_id="vehicle_lane_001",
                    centerline=[(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)],
                )
            ],
            actors=[_vehicle_actor(route_plan=DynamicRoutePlan(
                route_id="vehicle_route_001",
                route_type="waypoints",
                waypoints=[(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)],
                lane_ids=["vehicle_lane_001"],
            ))],
        )
        states = build_vehicle_states_from_plan(plan)
        step_vehicle_agents(states, TrafficConfig(), dt_s=0.5, sim_time_s=1.0)
        self.assertGreater(states[0].position[0], 0.0)

    def test_build_dynamic_plan_feeds_sumo_states(self):
        stats = SimpleNamespace(
            vehicle_routes=[
                SimpleNamespace(
                    vertices=[[-8.0, -1.0, 0.0], [8.0, -1.0, 0.0]],
                    prim_path="/World/vehicle_route_001",
                    index="001",
                )
            ],
            vehicle_lanes=[
                SimpleNamespace(
                    vertices=[
                        [-8.0, -1.5, 0.0],
                        [8.0, -1.5, 0.0],
                        [8.0, -0.5, 0.0],
                        [-8.0, -0.5, 0.0],
                    ],
                    prim_path="/World/vehicle_lane_001",
                    index="001",
                )
            ],
        )
        plan = build_dynamic_actor_plan(
            stats,
            DynamicPlanConfig(max_pedestrian_actors=0, max_vehicle_actors=1),
        )
        states = build_vehicle_states_from_plan(plan)
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0].lane_ids, ["vehicle_lane_001"])


if __name__ == "__main__":
    unittest.main()
