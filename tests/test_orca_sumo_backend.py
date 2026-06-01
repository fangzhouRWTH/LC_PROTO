from contextlib import redirect_stdout
from io import StringIO
import unittest

from engine.dynamic import (
    DynamicActorPlan,
    DynamicActorShape,
    DynamicLanePlan,
    DynamicPose,
    DynamicRoutePlan,
    DynamicScenePlan,
    DynamicSpeedProfile,
)
from isaac_env.isaac_agents.backends.orca_sumo import OrcaSumoDynamicAgentBackend


def _pedestrian_actor() -> DynamicActorPlan:
    return DynamicActorPlan(
        actor_id="pedestrian_001",
        actor_type="pedestrian",
        route=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
        speed_mps=1.2,
        spawn_pose=DynamicPose(position=(0.0, 0.0, 0.0)),
        goal_pose=DynamicPose(position=(2.0, 0.0, 0.0)),
        route_plan=DynamicRoutePlan(
            route_id="pedestrian_route_001",
            route_type="waypoints",
            route_mode="once",
            waypoints=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
        ),
        speed_profile=DynamicSpeedProfile(target_speed_mps=1.2, max_speed_mps=1.2),
        shape=DynamicActorShape(radius_m=0.35, height_m=1.7),
    )


def _vehicle_actor() -> DynamicActorPlan:
    return DynamicActorPlan(
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


class OrcaSumoBackendTest(unittest.TestCase):
    def test_composite_backend_filters_actor_types_without_skip_warnings(self):
        plan = DynamicScenePlan(
            actors=[_pedestrian_actor(), _vehicle_actor()],
            lanes=[
                DynamicLanePlan(
                    lane_id="vehicle_lane_001",
                    centerline=[(-8.0, -1.0, 0.0), (8.0, -1.0, 0.0)],
                    width_m=2.0,
                )
            ],
        )
        backend = OrcaSumoDynamicAgentBackend()
        stdout = StringIO()

        with redirect_stdout(stdout):
            backend.build_from_plan(plan)

        self.assertEqual(backend.actor_count, 2)
        self.assertNotIn("skips non-pedestrian actor", stdout.getvalue())
        self.assertNotIn("skips non-vehicle actor", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
