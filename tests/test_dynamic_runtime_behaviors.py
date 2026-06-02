from pathlib import Path
import importlib.util
import sys
import types
import unittest
from unittest.mock import patch

from engine.dynamic import (
    DynamicActorPlan,
    DynamicActorShape,
    DynamicPose,
    DynamicRoutePlan,
    DynamicScenePlan,
    DynamicSpeedProfile,
)
from engine.orca_pedestrian import (
    ObstacleContext,
    PedestrianAgentState,
    step_pedestrian_agents,
)
from engine.sumo_vehicle import (
    TrafficConfig,
    VehicleAgentState,
    step_vehicle_agents,
)
from isaac_env.isaac_agents.backends.kinematic import KinematicDynamicAgentBackend
from isaac_env.isaac_agents.backends.orca_pedestrian import (
    OrcaPedestrianDynamicAgentBackend,
)
from isaac_env.isaac_agents.backends.sumo_vehicle import SumoVehicleDynamicAgentBackend

ROOT = Path(__file__).resolve().parents[1]


class _Vec3(tuple):
    def __new__(cls, *values):
        return tuple.__new__(cls, values)


class _Gf:
    Vec3d = _Vec3
    Vec3f = _Vec3


class _Context:
    pxr_gf = _Gf()


class _Op:
    def __init__(self):
        self.values = []

    def Set(self, value):
        self.values.append(tuple(value))


def _actor(actor_type="pedestrian", route_mode="once", route=None, speed=1.0):
    route = route or [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
    shape = (
        DynamicActorShape(length_m=4.5, width_m=1.8, height_m=1.6)
        if actor_type == "vehicle"
        else DynamicActorShape(radius_m=0.35, height_m=1.7)
    )
    return DynamicActorPlan(
        actor_id=f"{actor_type}_001",
        actor_type=actor_type,
        route=route,
        speed_mps=speed,
        spawn_pose=DynamicPose(position=route[0]),
        goal_pose=DynamicPose(position=route[-1]),
        route_id=f"{actor_type}_route_001",
        route_plan=DynamicRoutePlan(
            route_id=f"{actor_type}_route_001",
            route_type="waypoints",
            route_mode=route_mode,
            waypoints=route,
        ),
        speed_profile=DynamicSpeedProfile(target_speed_mps=speed, max_speed_mps=speed),
        shape=shape,
    )


def _attach_fake_ops(backend):
    backend._get_context = lambda: _Context()
    for runtime in backend.actors:
        runtime.translate_op = _Op()
        runtime.rotate_op = _Op()


class DynamicRuntimeBehaviorTest(unittest.TestCase):
    def test_kinematic_once_actor_hides_at_route_end_and_reset_shows(self):
        backend = KinematicDynamicAgentBackend()
        backend.build_from_plan(DynamicScenePlan(actors=[_actor(route_mode="once")]))
        _attach_fake_ops(backend)

        runtime = backend.actors[0]
        backend.reset()
        self.assertFalse(runtime.hidden)

        backend.step(1.1)
        self.assertTrue(runtime.hidden)
        self.assertEqual(runtime.translate_op.values[-1], (1.0, 0.0, 0.0))

        backend.reset()
        self.assertFalse(runtime.hidden)

    def test_kinematic_loop_actor_does_not_hide_after_route_length(self):
        backend = KinematicDynamicAgentBackend()
        backend.build_from_plan(DynamicScenePlan(actors=[_actor(route_mode="loop")]))
        _attach_fake_ops(backend)

        runtime = backend.actors[0]
        backend.reset()
        backend.step(2.2)

        self.assertFalse(runtime.hidden)
        self.assertAlmostEqual(runtime.translate_op.values[-1][0], 0.2, places=6)

    def test_orca_finished_actor_hides_and_reset_shows(self):
        backend = OrcaPedestrianDynamicAgentBackend()
        backend.build_from_plan(DynamicScenePlan(actors=[_actor(speed=1.2, route_mode="once")]))
        _attach_fake_ops(backend)

        runtime = backend.actors[0]
        backend.reset()
        backend.step(1.0)

        self.assertTrue(runtime.planner_state.finished)
        self.assertTrue(runtime.hidden)

        backend.reset()
        self.assertFalse(runtime.hidden)
        self.assertFalse(runtime.planner_state.finished)

    def test_sumo_finished_actor_hides_and_reset_shows(self):
        backend = SumoVehicleDynamicAgentBackend()
        backend.build_from_plan(
            DynamicScenePlan(actors=[_actor(actor_type="vehicle", speed=4.0, route_mode="once")])
        )
        _attach_fake_ops(backend)

        runtime = backend.actors[0]
        backend.reset()
        backend.step(0.5)

        self.assertTrue(runtime.planner_state.finished)
        self.assertTrue(runtime.hidden)

        backend.reset()
        self.assertFalse(runtime.hidden)
        self.assertFalse(runtime.planner_state.finished)

    def test_orca_loop_state_does_not_finish_at_endpoint(self):
        agent = PedestrianAgentState(
            actor_id="pedestrian_001",
            radius_m=0.35,
            position=(0.0, 0.0, 0.0),
            waypoints=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
            target_speed_mps=1.2,
            max_speed_mps=1.2,
            route_mode="loop",
        )

        step_pedestrian_agents([agent], ObstacleContext(), dt_s=1.0, sim_time_s=1.0)
        step_pedestrian_agents([agent], ObstacleContext(), dt_s=1.0, sim_time_s=2.0)

        self.assertFalse(agent.finished)

    def test_sumo_loop_state_does_not_finish_and_wraps(self):
        agent = VehicleAgentState(
            actor_id="vehicle_001",
            route_id="vehicle_route_001",
            lane_ids=[],
            length_m=4.5,
            width_m=1.8,
            path=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
            position=(0.0, 0.0, 0.0),
            target_speed_mps=1.0,
            max_speed_mps=1.0,
            route_mode="loop",
        )

        step_vehicle_agents([agent], TrafficConfig(), dt_s=1.0, sim_time_s=2.25)

        self.assertFalse(agent.finished)
        self.assertAlmostEqual(agent.position[0], 0.25, places=6)

    def test_multi_waypoint_arc_route_progresses_monotonically_with_sane_yaw(self):
        agent = VehicleAgentState(
            actor_id="vehicle_arc",
            route_id="vehicle_route_arc",
            lane_ids=[],
            length_m=4.5,
            width_m=1.8,
            path=[
                (0.0, 0.0, 0.0),
                (1.0, 0.0, 0.0),
                (1.7, 0.3, 0.0),
                (2.0, 1.0, 0.0),
                (2.0, 2.0, 0.0),
            ],
            position=(0.0, 0.0, 0.0),
            target_speed_mps=0.5,
            max_speed_mps=0.5,
            route_mode="once",
        )
        samples = []
        for index in range(1, 7):
            step_vehicle_agents([agent], TrafficConfig(), dt_s=0.5, sim_time_s=index * 0.5)
            samples.append((agent.position, agent.velocity))

        xs = [position[0] for position, _ in samples]
        ys = [position[1] for position, _ in samples]
        self.assertEqual(xs, sorted(xs))
        self.assertGreater(max(ys), min(ys))
        for _, velocity in samples:
            self.assertLessEqual(abs(velocity[0]), agent.max_speed_mps + 1e-6)
            self.assertLessEqual(abs(velocity[1]), agent.max_speed_mps + 1e-6)

    def test_dynamic_route_mode_cli_argument_parses_with_stubbed_simulation(self):
        fake_simulation = types.SimpleNamespace(
            DEFAULT_SCENE_USD=Path("scene.usd"),
            DEFAULT_ROBOT_TYPE="spot",
            DEFAULT_ROBOT_NAME="spot_demo",
            DEFAULT_WARMUP_FRAMES=30,
            DEFAULT_CAMERA_PRIM_PATH="/OmniverseKit_Persp",
            DEFAULT_CHASE_CAMERA=False,
            DEFAULT_ENABLE_DYNAMIC_AGENTS=True,
            DEFAULT_DYNAMIC_AGENT_BACKEND="kinematic",
            DEFAULT_DYNAMIC_MAX_PEDESTRIAN_ACTORS=1,
            DEFAULT_DYNAMIC_MAX_VEHICLE_ACTORS=1,
            DEFAULT_DYNAMIC_PEDESTRIAN_SPEED_MPS=1.2,
            DEFAULT_DYNAMIC_VEHICLE_SPEED_MPS=4.0,
            DEFAULT_DYNAMIC_SPAWN_TIME_S=0.0,
            DEFAULT_DYNAMIC_ROUTE_MODE="loop",
            DEFAULT_DYNAMIC_PLACEHOLDER_VISIBILITY="hidden",
            DEFAULT_DYNAMIC_PEDESTRIAN_VISUAL="proxy",
            DEFAULT_DYNAMIC_PEDESTRIAN_ASSET_PATH="",
            DEFAULT_DYNAMIC_PEDESTRIAN_ASSET_SCALE=1.0,
            DEFAULT_DYNAMIC_PEDESTRIAN_ANIMATION="none",
            DEFAULT_DYNAMIC_PEDESTRIAN_ANIMATION_CLIP_PATH="",
            DEFAULT_DYNAMIC_PEDESTRIAN_ANIMATION_TIME_SCALE=1.0,
            DEFAULT_DYNAMIC_VEHICLE_VISUAL="proxy",
            DEFAULT_DYNAMIC_VEHICLE_ASSET_PATH="",
            DEFAULT_DYNAMIC_VEHICLE_ASSET_SCALE=1.0,
            DEFAULT_WEATHER=None,
            DEFAULT_DAYTIME=None,
            DEFAULT_WEATHER_TIME_SCALE=1.0,
            DEFAULT_SENSOR_PROFILE="default",
            DEFAULT_ACTIVE_SENSOR_ID=None,
            DEFAULT_SENSOR_DIAGNOSTICS=False,
            DEFAULT_SENSOR_DIAGNOSTICS_INTERVAL_S=1.0,
            DEFAULT_SENSOR_DEBUG_OUTPUT_DIR=None,
            DEFAULT_SENSOR_DEBUG_INTERVAL_S=1.0,
            available_robot_types=lambda: ("spot",),
            available_dynamic_agent_backends=lambda: ("kinematic",),
            available_weather_names=lambda: ("clear",),
            available_daytime_names=lambda: ("day",),
            available_sensor_profiles=lambda: ("default",),
        )
        fake_package = types.ModuleType("isaac_env")
        fake_package.simulation = fake_simulation
        module_name = "_lc_proto_main_route_mode_test"
        spec = importlib.util.spec_from_file_location(module_name, ROOT / "src/simworld/main.py")
        module = importlib.util.module_from_spec(spec)

        with patch.dict(
            sys.modules,
            {
                "isaac_env": fake_package,
                "isaac_env.simulation": fake_simulation,
            },
        ):
            assert spec.loader is not None
            spec.loader.exec_module(module)
            with patch.object(
                sys,
                "argv",
                [
                    "main.py",
                    "--dynamic-route-mode",
                    "once",
                    "--dynamic-placeholder-visibility",
                    "visible",
                    "--dynamic-pedestrian-visual",
                    "asset",
                    "--dynamic-pedestrian-asset-path",
                    "/tmp/people",
                    "--dynamic-pedestrian-asset-scale",
                    "1.25",
                    "--dynamic-pedestrian-animation",
                    "clip",
                    "--dynamic-pedestrian-animation-clip-path",
                    "/tmp/people/walk.usd",
                    "--dynamic-pedestrian-animation-time-scale",
                    "0.8",
                    "--dynamic-vehicle-visual",
                    "asset",
                    "--dynamic-vehicle-asset-path",
                    "/tmp/cars",
                    "--dynamic-vehicle-asset-scale",
                    "0.75",
                ],
            ):
                args = module.parse_args()

        self.assertEqual(args.dynamic_route_mode, "once")
        self.assertEqual(args.dynamic_placeholder_visibility, "visible")
        self.assertEqual(args.dynamic_pedestrian_visual, "asset")
        self.assertEqual(args.dynamic_pedestrian_asset_path, "/tmp/people")
        self.assertAlmostEqual(args.dynamic_pedestrian_asset_scale, 1.25)
        self.assertEqual(args.dynamic_pedestrian_animation, "clip")
        self.assertEqual(args.dynamic_pedestrian_animation_clip_path, "/tmp/people/walk.usd")
        self.assertAlmostEqual(args.dynamic_pedestrian_animation_time_scale, 0.8)
        self.assertEqual(args.dynamic_vehicle_visual, "asset")
        self.assertEqual(args.dynamic_vehicle_asset_path, "/tmp/cars")
        self.assertAlmostEqual(args.dynamic_vehicle_asset_scale, 0.75)

    def test_run_sim_env_wires_dynamic_demo_arguments(self):
        sim_defaults = (ROOT / "scripts/sim_defaults.sh").read_text()
        self.assertIn('DYNAMIC_ROUTE_MODE="${DYNAMIC_ROUTE_MODE:-}"', sim_defaults)
        self.assertIn('DYNAMIC_PLACEHOLDER_VISIBILITY="${DYNAMIC_PLACEHOLDER_VISIBILITY:-}"', sim_defaults)
        self.assertIn('DYNAMIC_PEDESTRIAN_VISUAL="${DYNAMIC_PEDESTRIAN_VISUAL:-}"', sim_defaults)
        self.assertIn('DYNAMIC_PEDESTRIAN_ASSET_PATH="${DYNAMIC_PEDESTRIAN_ASSET_PATH:-}"', sim_defaults)
        self.assertIn('DYNAMIC_PEDESTRIAN_ASSET_SCALE="${DYNAMIC_PEDESTRIAN_ASSET_SCALE:-}"', sim_defaults)
        self.assertIn('DYNAMIC_PEDESTRIAN_ANIMATION="${DYNAMIC_PEDESTRIAN_ANIMATION:-}"', sim_defaults)
        self.assertIn('DYNAMIC_PEDESTRIAN_ANIMATION_CLIP_PATH="${DYNAMIC_PEDESTRIAN_ANIMATION_CLIP_PATH:-}"', sim_defaults)
        self.assertIn('DYNAMIC_PEDESTRIAN_ANIMATION_TIME_SCALE="${DYNAMIC_PEDESTRIAN_ANIMATION_TIME_SCALE:-}"', sim_defaults)
        self.assertIn('DYNAMIC_VEHICLE_VISUAL="${DYNAMIC_VEHICLE_VISUAL:-}"', sim_defaults)
        self.assertIn('DYNAMIC_VEHICLE_ASSET_PATH="${DYNAMIC_VEHICLE_ASSET_PATH:-}"', sim_defaults)
        self.assertIn('DYNAMIC_VEHICLE_ASSET_SCALE="${DYNAMIC_VEHICLE_ASSET_SCALE:-}"', sim_defaults)
        self.assertIn('SENSOR_PROFILE="${SENSOR_PROFILE:-}"', sim_defaults)
        self.assertIn('ACTIVE_SENSOR="${ACTIVE_SENSOR:-}"', sim_defaults)
        self.assertIn(
            'append_sim_arg_if_set "--dynamic-route-mode" "${DYNAMIC_ROUTE_MODE}"',
            sim_defaults,
        )
        self.assertIn(
            'append_sim_arg_if_set "--dynamic-placeholder-visibility" "${DYNAMIC_PLACEHOLDER_VISIBILITY}"',
            sim_defaults,
        )
        self.assertIn(
            'append_sim_arg_if_set "--dynamic-pedestrian-visual" "${DYNAMIC_PEDESTRIAN_VISUAL}"',
            sim_defaults,
        )
        self.assertIn(
            'append_sim_arg_if_set "--dynamic-pedestrian-asset-path" "${DYNAMIC_PEDESTRIAN_ASSET_PATH}"',
            sim_defaults,
        )
        self.assertIn(
            'append_sim_arg_if_set "--dynamic-pedestrian-asset-scale" "${DYNAMIC_PEDESTRIAN_ASSET_SCALE}"',
            sim_defaults,
        )
        self.assertIn(
            'append_sim_arg_if_set "--dynamic-pedestrian-animation" "${DYNAMIC_PEDESTRIAN_ANIMATION}"',
            sim_defaults,
        )
        self.assertIn(
            'append_sim_arg_if_set "--dynamic-pedestrian-animation-clip-path" "${DYNAMIC_PEDESTRIAN_ANIMATION_CLIP_PATH}"',
            sim_defaults,
        )
        self.assertIn(
            'append_sim_arg_if_set "--dynamic-pedestrian-animation-time-scale" "${DYNAMIC_PEDESTRIAN_ANIMATION_TIME_SCALE}"',
            sim_defaults,
        )
        self.assertIn(
            'append_sim_arg_if_set "--dynamic-vehicle-visual" "${DYNAMIC_VEHICLE_VISUAL}"',
            sim_defaults,
        )
        self.assertIn(
            'append_sim_arg_if_set "--dynamic-vehicle-asset-path" "${DYNAMIC_VEHICLE_ASSET_PATH}"',
            sim_defaults,
        )
        self.assertIn(
            'append_sim_arg_if_set "--dynamic-vehicle-asset-scale" "${DYNAMIC_VEHICLE_ASSET_SCALE}"',
            sim_defaults,
        )
        self.assertIn(
            'append_sim_arg_if_set "--sensor-profile" "${SENSOR_PROFILE}"',
            sim_defaults,
        )
        self.assertIn(
            'append_sim_arg_if_set "--active-sensor" "${ACTIVE_SENSOR}"',
            sim_defaults,
        )


if __name__ == "__main__":
    unittest.main()
