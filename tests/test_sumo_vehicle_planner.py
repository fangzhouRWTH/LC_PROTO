from types import SimpleNamespace
import math
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
    VehicleAgentState,
    build_vehicle_states_from_plan,
    smooth_vehicle_path,
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


def _max_yaw_delta(path):
    yaws = []
    for start, end in zip(path, path[1:]):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        if (dx * dx + dy * dy) ** 0.5 < 1e-8:
            continue
        yaws.append(math.atan2(dy, dx))
    if len(yaws) < 2:
        return 0.0
    return max(abs((b - a + math.pi) % math.tau - math.pi) for a, b in zip(yaws, yaws[1:]))


def _has_point_near(path, target, tolerance=1e-6):
    return any(
        math.dist(point, target) <= tolerance
        for point in path
    )


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


    def test_smooth_vehicle_path_adds_arc_samples_around_right_angle(self):
        path = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)]

        smoothed = smooth_vehicle_path(
            path,
            TrafficConfig(turn_radius_m=3.0, arc_sample_spacing_m=0.75),
        )

        self.assertEqual(smoothed[0], path[0])
        self.assertEqual(smoothed[-1], path[-1])
        self.assertGreater(len(smoothed), len(path))
        self.assertNotIn(path[1], smoothed)
        self.assertTrue(_has_point_near(smoothed, (7.0, 0.0, 0.0)))
        self.assertTrue(_has_point_near(smoothed, (10.0, 3.0, 0.0)))

    def test_smooth_vehicle_path_reduces_yaw_jumps(self):
        path = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)]
        smoothed = smooth_vehicle_path(
            path,
            TrafficConfig(turn_radius_m=3.0, arc_sample_spacing_m=0.75),
        )

        self.assertAlmostEqual(_max_yaw_delta(path), 1.57079632679, places=6)
        self.assertLess(_max_yaw_delta(smoothed), 0.5)

    def test_build_states_smooths_vehicle_lane_centerline(self):
        plan = DynamicScenePlan(
            lanes=[
                DynamicLanePlan(
                    lane_id="vehicle_lane_001",
                    centerline=[(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)],
                )
            ],
            actors=[_vehicle_actor(route_plan=DynamicRoutePlan(
                route_id="vehicle_route_001",
                route_type="waypoints",
                waypoints=[(0.0, 0.0, 0.0), (10.0, 10.0, 0.0)],
                lane_ids=["vehicle_lane_001"],
            ))],
        )

        states = build_vehicle_states_from_plan(
            plan,
            traffic_config=TrafficConfig(turn_radius_m=3.0, arc_sample_spacing_m=0.75),
        )

        self.assertGreater(len(states[0].path), 3)
        self.assertNotIn((10.0, 0.0, 0.0), states[0].path)

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

    def test_crossing_vehicles_yield_to_avoid_overlap(self):
        eastbound = VehicleAgentState(
            actor_id="vehicle_a",
            route_id="route_east",
            lane_ids=["lane_east"],
            length_m=4.5,
            width_m=1.8,
            path=[(-6.0, 0.0, 0.0), (6.0, 0.0, 0.0)],
            position=(-6.0, 0.0, 0.0),
            target_speed_mps=6.0,
            max_speed_mps=6.0,
            route_mode="once",
        )
        northbound = VehicleAgentState(
            actor_id="vehicle_b",
            route_id="route_north",
            lane_ids=["lane_north"],
            length_m=4.5,
            width_m=1.8,
            path=[(0.0, -6.0, 0.0), (0.0, 6.0, 0.0)],
            position=(0.0, -6.0, 0.0),
            target_speed_mps=6.0,
            max_speed_mps=6.0,
            route_mode="once",
        )

        agents = [eastbound, northbound]
        step_vehicle_agents(
            agents,
            TrafficConfig(min_vehicle_center_gap_m=5.0),
            dt_s=1.0,
            sim_time_s=1.0,
        )

        self.assertEqual(eastbound.position, (0.0, 0.0, 0.0))
        self.assertEqual(northbound.position, (0.0, -6.0, 0.0))
        self.assertEqual(northbound.velocity, (0.0, 0.0, 0.0))
        center_distance = (
            (eastbound.position[0] - northbound.position[0]) ** 2
            + (eastbound.position[1] - northbound.position[1]) ** 2
        ) ** 0.5
        self.assertGreaterEqual(center_distance, 5.0)

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
