from dataclasses import dataclass, field
from types import SimpleNamespace
import unittest

from engine.dynamic import DynamicActorPlan, DynamicPlanConfig, build_dynamic_actor_plan


@dataclass
class Point:
    position: list[float]
    prim_path: str = ""
    index: str = ""


@dataclass
class PathPlaceholder:
    vertices: list[list[float]] = field(default_factory=list)
    prim_path: str = ""
    raw_name: str = ""
    index: str = ""


@dataclass
class AreaPlaceholder:
    vertices: list[list[float]] = field(default_factory=list)
    prim_path: str = ""
    raw_name: str = ""
    index: str = ""


class OrcaLikeMockBackend:
    def build_from_plan(self, plan):
        accepted = []
        for actor in plan.actors:
            if actor.actor_type != "pedestrian":
                continue

            missing = []
            if actor.spawn_pose is None:
                missing.append("spawn_pose")
            if actor.goal_pose is None:
                missing.append("goal_pose")
            if actor.speed_profile is None:
                missing.append("speed_profile")
            if actor.shape.radius_m is None:
                missing.append("shape.radius_m")
            if actor.route_plan is None:
                missing.append("route_plan")
            elif actor.route_plan.route_type != "waypoints":
                missing.append("route_plan.route_type=waypoints")

            if missing:
                raise AssertionError(f"ORCA-like plan missing: {missing}")
            accepted.append(actor.actor_id)
        return accepted


class SumoLikeMockBackend:
    def build_from_plan(self, plan):
        accepted = []
        known_lane_ids = {lane.lane_id for lane in getattr(plan, "lanes", [])}
        for actor in plan.actors:
            if actor.actor_type != "vehicle":
                continue

            missing = []
            if actor.route_plan is None:
                missing.append("route_plan")
            elif not actor.route_plan.route_id:
                missing.append("route_plan.route_id")
            elif any(
                lane_id not in known_lane_ids for lane_id in actor.route_plan.lane_ids
            ):
                missing.append("known route_plan.lane_ids")
            if not actor.route_id:
                missing.append("route_id")
            if actor.shape.length_m is None:
                missing.append("shape.length_m")
            if actor.shape.width_m is None:
                missing.append("shape.width_m")
            if actor.speed_profile is None:
                missing.append("speed_profile")

            if missing:
                raise AssertionError(f"SUMO-like plan missing: {missing}")
            accepted.append(actor.actor_id)
        return accepted


def make_stats(**values):
    return SimpleNamespace(**values)


class DynamicContractTest(unittest.TestCase):
    def test_legacy_route_fields_remain_available(self):
        stats = make_stats(
            pedestrian_spawn_points=[Point([0.0, 1.0, 0.0], "/World/ped_spawn")],
            pedestrian_goal_points=[Point([4.0, 1.0, 0.0], "/World/ped_goal")],
        )

        plan = build_dynamic_actor_plan(
            stats,
            DynamicPlanConfig(max_pedestrian_actors=1, max_vehicle_actors=0),
        )

        self.assertEqual(len(plan.actors), 1)
        actor = plan.actors[0]
        self.assertEqual(actor.route, [(0.0, 1.0, 0.0), (4.0, 1.0, 0.0)])
        self.assertEqual(actor.speed_mps, 1.2)
        self.assertEqual(actor.spawn_time_s, 0.0)

    def test_pedestrian_plan_has_orca_adapter_inputs(self):
        stats = make_stats(
            pedestrian_spawn_points=[Point([0.0, 0.0, 0.0], "/World/ped_spawn")],
            pedestrian_goal_points=[Point([2.0, 0.0, 0.0], "/World/ped_goal")],
        )
        config = DynamicPlanConfig(
            max_pedestrian_actors=1,
            max_vehicle_actors=0,
            pedestrian_speed_mps=1.4,
            default_spawn_time_s=2.5,
            pedestrian_radius_m=0.42,
        )

        plan = build_dynamic_actor_plan(stats, config)
        actor = plan.actors[0]

        self.assertEqual(OrcaLikeMockBackend().build_from_plan(plan), ["pedestrian_001"])
        self.assertEqual(actor.spawn_pose.position, (0.0, 0.0, 0.0))
        self.assertEqual(actor.goal_pose.position, (2.0, 0.0, 0.0))
        self.assertEqual(actor.shape.radius_m, 0.42)
        self.assertEqual(actor.speed_profile.target_speed_mps, 1.4)
        self.assertEqual(actor.speed_profile.max_speed_mps, 1.4)
        self.assertEqual(actor.route_plan.waypoints, actor.route)

    def test_vehicle_plan_has_sumo_adapter_inputs(self):
        stats = make_stats(
            vehicle_spawn_points=[Point([-1.0, 0.0, 0.0], "/World/vehicle_spawn")],
            vehicle_goal_points=[Point([5.0, 0.0, 0.0], "/World/vehicle_goal")],
        )
        config = DynamicPlanConfig(
            max_pedestrian_actors=0,
            max_vehicle_actors=1,
            vehicle_speed_mps=6.0,
            default_spawn_time_s=3.0,
            vehicle_length_m=4.8,
            vehicle_width_m=1.9,
        )

        plan = build_dynamic_actor_plan(stats, config)
        actor = plan.actors[0]

        self.assertEqual(SumoLikeMockBackend().build_from_plan(plan), ["vehicle_001"])
        self.assertEqual(actor.route_id, "vehicle_001_route")
        self.assertEqual(actor.route_plan.route_id, "vehicle_001_route")
        self.assertEqual(actor.route_plan.route_type, "waypoints")
        self.assertEqual(actor.spawn_time_s, 3.0)
        self.assertEqual(actor.shape.length_m, 4.8)
        self.assertEqual(actor.shape.width_m, 1.9)
        self.assertEqual(actor.speed_profile.target_speed_mps, 6.0)

    def test_pedestrian_route_placeholder_overrides_spawn_goal_fallback(self):
        stats = make_stats(
            pedestrian_spawn_points=[Point([0.0, 0.0, 0.0], "/World/ped_spawn", "007")],
            pedestrian_goal_points=[Point([9.0, 0.0, 0.0], "/World/ped_goal", "007")],
            pedestrian_routes=[
                PathPlaceholder(
                    vertices=[[1.0, 1.0, 0.0], [2.0, 2.0, 0.0], [3.0, 1.0, 0.0]],
                    prim_path="/World/ped_route",
                    raw_name="placeholder_pedestrian_route_007",
                    index="007",
                )
            ],
        )

        plan = build_dynamic_actor_plan(
            stats,
            DynamicPlanConfig(max_pedestrian_actors=1, max_vehicle_actors=0),
        )
        actor = plan.actors[0]

        self.assertEqual(
            actor.route,
            [(1.0, 1.0, 0.0), (2.0, 2.0, 0.0), (3.0, 1.0, 0.0)],
        )
        self.assertEqual(actor.spawn_pose.position, actor.route[0])
        self.assertEqual(actor.goal_pose.position, actor.route[-1])
        self.assertEqual(actor.route_id, "pedestrian_route_007")
        self.assertEqual(actor.route_plan.metadata["source"], "route_placeholder")
        self.assertEqual(actor.route_plan.metadata["placeholder_index"], "007")
        self.assertEqual(
            actor.source_prim_paths,
            ["/World/ped_route", "/World/ped_spawn", "/World/ped_goal"],
        )

    def test_public_space_generated_trip_dict_uses_explicit_id_and_metadata(self):
        stats = make_stats(
            pedestrian_routes=[
                {
                    "route_id": "pedestrian_trip_region_a_001",
                    "vertices": [[0.0, 0.0, 0.0], [15.0, 0.0, 0.0], [25.0, 0.0, 0.0]],
                    "raw_name": "pedestrian_trip_region_a_001",
                    "index": "001",
                    "metadata": {
                        "source": "public_space_trip_generator",
                        "source_region_id": "region_a",
                        "route_generation": "walkable_graph_trip",
                        "line_role": "trip",
                        "length": 25.0,
                    },
                }
            ],
        )

        plan = build_dynamic_actor_plan(
            stats,
            DynamicPlanConfig(max_pedestrian_actors=1, max_vehicle_actors=0),
        )
        actor = plan.actors[0]

        self.assertEqual(actor.route_id, "pedestrian_trip_region_a_001")
        self.assertEqual(actor.route_plan.route_id, "pedestrian_trip_region_a_001")
        self.assertEqual(actor.metadata["source"], "public_space_trip_generator")
        self.assertEqual(actor.route_plan.metadata["source_region_id"], "region_a")
        self.assertEqual(actor.route_plan.metadata["route_generation"], "walkable_graph_trip")
        self.assertEqual(actor.route_plan.metadata["line_role"], "trip")
        self.assertEqual(actor.route_plan.metadata["length"], 25.0)
        self.assertEqual(actor.route_plan.metadata["placeholder_index"], "001")

    def test_route_metadata_can_override_speed_spawn_and_mode(self):
        stats = make_stats(
            pedestrian_routes=[
                {
                    "route_id": "demo_people_busy_001",
                    "vertices": [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]],
                    "metadata": {
                        "source": "demo_people_scenario",
                        "speed_mps": 1.25,
                        "spawn_time_s": 0.75,
                        "route_mode": "once",
                    },
                }
            ],
        )

        plan = build_dynamic_actor_plan(
            stats,
            DynamicPlanConfig(
                max_pedestrian_actors=1,
                max_vehicle_actors=0,
                pedestrian_speed_mps=0.8,
                default_spawn_time_s=3.0,
                default_route_mode="loop",
            ),
        )
        actor = plan.actors[0]

        self.assertEqual(actor.speed_mps, 1.25)
        self.assertEqual(actor.spawn_time_s, 0.75)
        self.assertEqual(actor.speed_profile.target_speed_mps, 1.25)
        self.assertEqual(actor.route_plan.route_mode, "once")

    def test_spawn_goal_pairs_by_placeholder_index_not_traversal_order(self):
        stats = make_stats(
            pedestrian_spawn_points=[
                Point([0.0, 0.0, 0.0], "/World/spawn_002", "002"),
                Point([9.0, 0.0, 0.0], "/World/spawn_001", "001"),
            ],
            pedestrian_goal_points=[
                Point([1.0, 0.0, 0.0], "/World/goal_001", "001"),
                Point([10.0, 0.0, 0.0], "/World/goal_002", "002"),
            ],
        )

        plan = build_dynamic_actor_plan(
            stats,
            DynamicPlanConfig(max_pedestrian_actors=2, max_vehicle_actors=0),
        )

        self.assertEqual(len(plan.actors), 2)
        self.assertEqual(plan.actors[0].spawn_pose.position, (9.0, 0.0, 0.0))
        self.assertEqual(plan.actors[0].goal_pose.position, (1.0, 0.0, 0.0))
        self.assertEqual(plan.actors[1].spawn_pose.position, (0.0, 0.0, 0.0))
        self.assertEqual(plan.actors[1].goal_pose.position, (10.0, 0.0, 0.0))
        self.assertEqual(plan.actors[0].route_id, "pedestrian_route_001")

    def test_spawn_goal_warns_on_unmatched_index(self):
        stats = make_stats(
            pedestrian_spawn_points=[Point([0.0, 0.0, 0.0], "/World/spawn_001", "001")],
            pedestrian_goal_points=[Point([1.0, 0.0, 0.0], "/World/goal_002", "002")],
        )

        plan = build_dynamic_actor_plan(
            stats,
            DynamicPlanConfig(max_pedestrian_actors=2, max_vehicle_actors=0),
        )

        self.assertEqual(plan.actors, [])
        self.assertIn("spawn index 001 has no matching goal", plan.warnings[0])
        self.assertIn("goal index 002 has no matching spawn", plan.warnings[1])

    def test_route_mode_defaults_to_loop_and_can_be_overridden(self):
        stats = make_stats(
            pedestrian_spawn_points=[Point([0.0, 0.0, 0.0], "/World/ped_spawn")],
            pedestrian_goal_points=[Point([2.0, 0.0, 0.0], "/World/ped_goal")],
        )

        loop_plan = build_dynamic_actor_plan(stats, DynamicPlanConfig(max_vehicle_actors=0))
        once_plan = build_dynamic_actor_plan(
            stats,
            DynamicPlanConfig(max_vehicle_actors=0, default_route_mode="once"),
        )

        self.assertEqual(loop_plan.actors[0].route_plan.route_mode, "loop")
        self.assertEqual(once_plan.actors[0].route_plan.route_mode, "once")

    def test_vehicle_route_placeholder_does_not_require_spawn_goal_pair(self):
        stats = make_stats(
            vehicle_routes=[
                PathPlaceholder(
                    vertices=[[-5.0, -1.0, 0.0], [0.0, -1.0, 0.0], [5.0, -1.0, 0.0]],
                    prim_path="/World/vehicle_route",
                    raw_name="placeholder_vehicle_route_002",
                    index="002",
                )
            ],
        )

        plan = build_dynamic_actor_plan(
            stats,
            DynamicPlanConfig(max_pedestrian_actors=0, max_vehicle_actors=1),
        )
        actor = plan.actors[0]

        self.assertEqual(SumoLikeMockBackend().build_from_plan(plan), ["vehicle_001"])
        self.assertEqual(actor.route_id, "vehicle_route_002")
        self.assertEqual(actor.route_plan.waypoints, actor.route)
        self.assertEqual(plan.warnings, [])

    def test_vehicle_lane_placeholder_builds_lane_plan_and_route_reference(self):
        stats = make_stats(
            vehicle_routes=[
                PathPlaceholder(
                    vertices=[[-8.0, -1.0, 0.0], [8.0, -1.0, 0.0]],
                    prim_path="/World/vehicle_route_003",
                    raw_name="placeholder_vehicle_route_003",
                    index="003",
                )
            ],
            vehicle_lanes=[
                AreaPlaceholder(
                    vertices=[
                        [-8.0, -1.5, 0.0],
                        [8.0, -1.5, 0.0],
                        [8.0, -0.5, 0.0],
                        [-8.0, -0.5, 0.0],
                    ],
                    prim_path="/World/vehicle_lane_003",
                    raw_name="placeholder_vehicle_lane_003",
                    index="003",
                )
            ],
        )

        plan = build_dynamic_actor_plan(
            stats,
            DynamicPlanConfig(max_pedestrian_actors=0, max_vehicle_actors=1),
        )
        actor = plan.actors[0]
        lane = plan.lanes[0]

        self.assertEqual(SumoLikeMockBackend().build_from_plan(plan), ["vehicle_001"])
        self.assertEqual(lane.lane_id, "vehicle_lane_003")
        self.assertEqual(
            lane.centerline,
            [(-8.0, -1.0, 0.0), (8.0, -1.0, 0.0)],
        )
        self.assertEqual(lane.width_m, 1.0)
        self.assertEqual(lane.source_prim_paths, ["/World/vehicle_lane_003"])
        self.assertEqual(actor.route_plan.lane_ids, ["vehicle_lane_003"])

    def test_route_actor_count_respects_actor_limit(self):
        stats = make_stats(
            pedestrian_routes=[
                PathPlaceholder(
                    vertices=[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                    prim_path="/World/ped_route_001",
                    index="001",
                ),
                PathPlaceholder(
                    vertices=[[0.0, 1.0, 0.0], [1.0, 1.0, 0.0]],
                    prim_path="/World/ped_route_002",
                    index="002",
                ),
            ],
        )

        plan = build_dynamic_actor_plan(
            stats,
            DynamicPlanConfig(max_pedestrian_actors=1, max_vehicle_actors=0),
        )

        self.assertEqual([actor.actor_id for actor in plan.actors], ["pedestrian_001"])
        self.assertEqual(plan.actors[0].route_id, "pedestrian_route_001")

    def test_dynamic_actor_plan_can_still_be_constructed_minimally(self):
        actor = DynamicActorPlan(
            actor_id="legacy_actor",
            actor_type="pedestrian",
            route=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
        )

        self.assertEqual(actor.actor_id, "legacy_actor")
        self.assertEqual(actor.route_plan, None)
        self.assertEqual(actor.speed_profile, None)
        self.assertEqual(actor.shape.radius_m, None)


if __name__ == "__main__":
    unittest.main()
