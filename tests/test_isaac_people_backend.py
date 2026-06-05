import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

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
    PEOPLE_EXTENSIONS,
    IsaacPeopleDynamicAgentBackend,
    resolve_isaac_people_asset_root,
    resolve_isaac_people_navmesh_enabled,
    resolve_isaac_people_control_mode,
    character_name_for_index,
    people_command_lines_for_route,
    route_walk_animation_state,
    _character_handle_lookup_paths,
    _route_walk_animation_should_move,
)
from isaac_env.isaac_agents.backends.isaac_people_route_animation import (
    DEFAULT_ISAAC_PEOPLE_YAW_OFFSET_DEG,
    resolve_isaac_people_walk_clip_path,
    resolve_isaac_people_yaw_offset_degrees,
    set_orient_op_yaw,
    yaw_with_isaac_people_forward_offset,
)
from isaac_env.isaac_agents.backends.isaac_people_sumo import (
    IsaacPeopleSumoDynamicAgentBackend,
)


ROOT = Path(__file__).resolve().parents[1]


class _FakeQuatf:
    def __init__(self, source=None):
        self.source = source


class _FakeQuatd:
    def __init__(self, source=None):
        self.source = source


class _FakeRotation:
    def __init__(self, axis, angle_degrees):
        self.axis = axis
        self.angle_degrees = angle_degrees

    def GetQuat(self):
        return _FakeQuatd((self.axis, self.angle_degrees))


class _FakeGf:
    Quatf = _FakeQuatf
    Quatd = _FakeQuatd
    Rotation = _FakeRotation

    @staticmethod
    def Vec3d(x, y, z):
        return (x, y, z)


class _FakeOrientOp:
    def __init__(self, current):
        self.current = current
        self.value = None

    def Get(self):
        return self.current

    def Set(self, value):
        self.value = value


class _FakeCharacterHandle:
    def __init__(self):
        self.variables = []

    def set_variable(self, name, value):
        self.variables.append((name, value))


def _actor(actor_id, actor_type, route, route_mode="once"):
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
            route_mode=route_mode,
            waypoints=route,
        ),
        speed_profile=DynamicSpeedProfile(target_speed_mps=1.0, max_speed_mps=1.0),
        shape=shape,
    )


class IsaacPeopleBackendTest(unittest.TestCase):
    def test_resolve_isaac_people_asset_root_prefers_explicit_env(self):
        self.assertEqual(
            resolve_isaac_people_asset_root(
                env_value="/tmp/custom_assets",
                default_root="/tmp/missing_assets",
            ),
            "/tmp/custom_assets",
        )

    def test_resolve_isaac_people_asset_root_detects_local_people_pack(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "Assets/Isaac/5.1"
            people = root / "Isaac/People/Characters"
            people.mkdir(parents=True)
            (people / "Biped_Setup.usd").write_text("#usda 1.0\n")

            self.assertEqual(
                resolve_isaac_people_asset_root(env_value="", default_root=root),
                str(root.resolve()),
            )

    def test_resolve_isaac_people_asset_root_rejects_missing_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertIsNone(
                resolve_isaac_people_asset_root(env_value="", default_root=tmpdir)
            )

    def test_resolve_isaac_people_walk_clip_path_prefers_explicit_clip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clip = Path(tmpdir) / "custom_walk.skelanim.usd"
            clip.write_text("#usda 1.0\n")

            self.assertEqual(
                resolve_isaac_people_walk_clip_path(
                    asset_root=None,
                    explicit_clip_path=str(clip),
                ),
                str(clip.resolve()),
            )

    def test_resolve_isaac_people_walk_clip_path_finds_default_clip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            clip = root / "Isaac/People/Animations/stand_walk_loop_in_place.skelanim.usd"
            clip.parent.mkdir(parents=True)
            clip.write_text("#usda 1.0\n")

            self.assertEqual(
                resolve_isaac_people_walk_clip_path(str(root)),
                str(clip.resolve()),
            )

    def test_isaac_people_navmesh_mode_defaults_to_direct_route(self):
        self.assertFalse(resolve_isaac_people_navmesh_enabled(env_value=None))
        self.assertFalse(resolve_isaac_people_navmesh_enabled(env_value=""))
        self.assertTrue(resolve_isaac_people_navmesh_enabled(env_value="true"))
        self.assertTrue(resolve_isaac_people_navmesh_enabled(env_value="navmesh"))
        self.assertFalse(resolve_isaac_people_navmesh_enabled(env_value="false"))
        self.assertFalse(resolve_isaac_people_navmesh_enabled(env_value="direct"))

    def test_isaac_people_control_mode_defaults_to_route(self):
        self.assertEqual(resolve_isaac_people_control_mode(env_value=None), "route")
        self.assertEqual(resolve_isaac_people_control_mode(env_value=""), "route")
        self.assertEqual(resolve_isaac_people_control_mode(env_value="route"), "route")
        self.assertEqual(resolve_isaac_people_control_mode(env_value="direct"), "route")
        self.assertEqual(resolve_isaac_people_control_mode(env_value="command"), "command")
        self.assertEqual(resolve_isaac_people_control_mode(env_value="oap"), "command")

    def test_isaac_people_backend_uses_route_control_by_default(self):
        backend = IsaacPeopleDynamicAgentBackend()

        self.assertEqual(backend.control_mode, "route")
        self.assertFalse(backend.navmesh_enabled)

    def test_people_extensions_include_animgraph_runtime_bundles(self):
        self.assertIn("omni.anim.graph.bundle", PEOPLE_EXTENSIONS)
        self.assertIn("omni.anim.retarget.bundle", PEOPLE_EXTENSIONS)
        self.assertIn("omni.anim.navigation.bundle", PEOPLE_EXTENSIONS)
        self.assertIn("omni.anim.people", PEOPLE_EXTENSIONS)
        self.assertIn("isaacsim.replicator.agent.core", PEOPLE_EXTENSIONS)

    def test_route_walk_animation_state_matches_people_animgraph_variables(self):
        walking = route_walk_animation_state(True)
        idle = route_walk_animation_state(False)

        self.assertEqual(walking.action, "Walk")
        self.assertEqual(walking.walk, 1.0)
        self.assertEqual(idle.action, "None")
        self.assertEqual(idle.walk, 0.0)

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

    def test_route_control_command_file_is_intentionally_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            command_file = Path(tmpdir) / "commands.txt"
            backend = IsaacPeopleDynamicAgentBackend(
                command_file_path=command_file,
                control_mode="route",
            )
            backend.build_from_plan(
                DynamicScenePlan(
                    actors=[
                        _actor("pedestrian_001", "pedestrian", [(0, 0, 0), (1, 0, 0)]),
                    ]
                )
            )

            backend._write_command_file()

            self.assertIn("route-control mode", command_file.read_text())
            self.assertNotIn("GoTo", command_file.read_text())

    def test_command_control_keeps_goto_command_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            command_file = Path(tmpdir) / "commands.txt"
            backend = IsaacPeopleDynamicAgentBackend(
                command_file_path=command_file,
                control_mode="command",
            )
            backend.build_from_plan(
                DynamicScenePlan(
                    actors=[
                        _actor("pedestrian_001", "pedestrian", [(0, 0, 0), (1, 0, 0)]),
                    ]
                )
            )

            backend._write_command_file()

            self.assertIn("Character GoTo 1 0 0 0", command_file.read_text())

    def test_route_control_progress_and_yaw_are_kinematic(self):
        backend = IsaacPeopleDynamicAgentBackend(control_mode="route")
        backend.build_from_plan(
            DynamicScenePlan(
                actors=[
                    _actor(
                        "pedestrian_001",
                        "pedestrian",
                        [(0, 0, 0), (2, 0, 0), (2, 2, 0)],
                    ),
                ]
            )
        )
        actor = backend.actors[0]

        position, yaw = backend._pose_at_distance(actor, 1.0)
        self.assertEqual(position, (1.0, 0.0, 0.0))
        self.assertAlmostEqual(yaw, 0.0)

        position, yaw = backend._pose_at_distance(actor, 3.0)
        self.assertEqual(position, (2.0, 1.0, 0.0))
        self.assertAlmostEqual(yaw, 1.5707963267948966)

    def test_route_control_once_hides_at_route_end(self):
        backend = IsaacPeopleDynamicAgentBackend(control_mode="route")
        backend.build_from_plan(
            DynamicScenePlan(
                actors=[
                    _actor("pedestrian_001", "pedestrian", [(0, 0, 0), (1, 0, 0)]),
                ]
            )
        )
        actor = backend.actors[0]

        self.assertFalse(backend._should_hide_actor_at_distance(actor, 0.99))
        self.assertTrue(backend._should_hide_actor_at_distance(actor, 1.0))

    def test_route_control_once_hide_transition_logs_once_in_debug_mode(self):
        backend = IsaacPeopleDynamicAgentBackend(control_mode="route", debug_enabled=True)
        backend.build_from_plan(
            DynamicScenePlan(
                actors=[
                    _actor("pedestrian_001", "pedestrian", [(0, 0, 0), (1, 0, 0)]),
                ]
            )
        )
        actor = backend.actors[0]

        output = io.StringIO()
        with redirect_stdout(output):
            backend._set_actor_visible(actor, False)
            backend._set_actor_visible(actor, False)

        self.assertTrue(actor.hidden)
        self.assertEqual(
            output.getvalue().count("Isaac People actor hidden at route end"),
            1,
        )

    def test_route_control_preserves_existing_orient_op_quat_type(self):
        double_op = _FakeOrientOp(_FakeGf.Quatd())
        float_op = _FakeOrientOp(_FakeGf.Quatf())

        set_orient_op_yaw(double_op, _FakeGf, 0.25, yaw_offset_degrees=0.0)
        set_orient_op_yaw(float_op, _FakeGf, 0.25, yaw_offset_degrees=0.0)

        self.assertIsInstance(double_op.value, _FakeGf.Quatd)
        self.assertIsInstance(float_op.value, _FakeGf.Quatf)

    def test_isaac_people_yaw_offset_defaults_for_minus_y_forward_assets(self):
        self.assertEqual(
            resolve_isaac_people_yaw_offset_degrees(env_value=None),
            DEFAULT_ISAAC_PEOPLE_YAW_OFFSET_DEG,
        )
        self.assertAlmostEqual(
            yaw_with_isaac_people_forward_offset(0.0),
            1.5707963267948966,
        )

    def test_isaac_people_yaw_offset_can_be_overridden(self):
        self.assertEqual(resolve_isaac_people_yaw_offset_degrees(env_value="-90"), -90.0)
        self.assertEqual(resolve_isaac_people_yaw_offset_degrees(env_value="bad", default=12.0), 12.0)

    def test_route_control_orient_op_applies_yaw_offset(self):
        op = _FakeOrientOp(_FakeGf.Quatd())

        set_orient_op_yaw(op, _FakeGf, 0.0, yaw_offset_degrees=90.0)

        self.assertEqual(op.value.source.source[1], 90.0)

    def test_character_handle_lookup_paths_try_official_names(self):
        backend = IsaacPeopleDynamicAgentBackend(control_mode="route")
        backend.build_from_plan(
            DynamicScenePlan(
                actors=[
                    _actor("pedestrian_001", "pedestrian", [(0, 0, 0), (1, 0, 0)]),
                ]
            )
        )
        actor = backend.actors[0]
        actor.skelroot_path = "/World/Characters/Character/SkelRoot"
        actor.character_root_path = "/World/Characters/Character"
        actor.character_name = "Character"

        self.assertEqual(
            _character_handle_lookup_paths(actor),
            [
                "/World/Characters/Character/SkelRoot",
                "/World/Characters/Character",
                "Character",
            ],
        )

    def test_route_walk_animation_keeps_loop_routes_walking_after_first_lap(self):
        backend = IsaacPeopleDynamicAgentBackend(control_mode="route")
        backend.build_from_plan(
            DynamicScenePlan(
                actors=[
                    _actor(
                        "pedestrian_001",
                        "pedestrian",
                        [(0, 0, 0), (1, 0, 0)],
                        route_mode="loop",
                    ),
                ]
            )
        )
        actor = backend.actors[0]

        self.assertTrue(
            _route_walk_animation_should_move(
                actor,
                raw_distance=2.5,
                travel_time_s=2.5,
                hidden=False,
            )
        )

    def test_route_walk_animation_stops_once_routes_at_endpoint(self):
        backend = IsaacPeopleDynamicAgentBackend(control_mode="route")
        backend.build_from_plan(
            DynamicScenePlan(
                actors=[
                    _actor(
                        "pedestrian_001",
                        "pedestrian",
                        [(0, 0, 0), (1, 0, 0)],
                        route_mode="once",
                    ),
                ]
            )
        )
        actor = backend.actors[0]

        self.assertFalse(
            _route_walk_animation_should_move(
                actor,
                raw_distance=1.0,
                travel_time_s=1.0,
                hidden=False,
            )
        )

    def test_route_walk_animation_sets_people_variables_in_runtime_order(self):
        backend = IsaacPeopleDynamicAgentBackend(control_mode="route")
        backend.build_from_plan(
            DynamicScenePlan(
                actors=[
                    _actor(
                        "pedestrian_001",
                        "pedestrian",
                        [(0, 0, 0), (1, 0, 0)],
                        route_mode="loop",
                    ),
                ]
            )
        )
        actor = backend.actors[0]
        handle = _FakeCharacterHandle()
        backend._get_character_handle = lambda _actor: handle

        backend._set_walk_animation(
            actor,
            moving=True,
            position=(0.0, 0.0, 0.0),
            distance=0.0,
        )

        self.assertEqual(
            [name for name, _value in handle.variables],
            ["Action", "PathPoints", "Walk"],
        )
        self.assertEqual(handle.variables[0], ("Action", "Walk"))
        self.assertEqual(handle.variables[2], ("Walk", 1.0))
        self.assertEqual(
            handle.variables[1][1],
            [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
        )

    def test_route_control_loop_does_not_hide_at_route_end(self):
        backend = IsaacPeopleDynamicAgentBackend(control_mode="route")
        backend.build_from_plan(
            DynamicScenePlan(
                actors=[
                    _actor(
                        "pedestrian_001",
                        "pedestrian",
                        [(0, 0, 0), (1, 0, 0)],
                        route_mode="loop",
                    ),
                ]
            )
        )
        actor = backend.actors[0]

        self.assertFalse(backend._should_hide_actor_at_distance(actor, 2.0))

    def test_isaac_people_demo_defaults_to_route_control(self):
        script = (ROOT / "scripts/run_isaac_people_demo.sh").read_text()

        self.assertIn('ROBOT_TYPE="${ROBOT_TYPE:-none}"', script)
        self.assertIn('AUTO_PLAY="${AUTO_PLAY:-true}"', script)
        self.assertIn(
            'DYNAMIC_ISAAC_PEOPLE_CONTROL="${DYNAMIC_ISAAC_PEOPLE_CONTROL:-route}"',
            script,
        )
        self.assertIn(
            'DYNAMIC_ISAAC_PEOPLE_YAW_OFFSET_DEG="${DYNAMIC_ISAAC_PEOPLE_YAW_OFFSET_DEG:-90}"',
            script,
        )

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
