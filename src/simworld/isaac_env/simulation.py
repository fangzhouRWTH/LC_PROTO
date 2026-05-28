from .isaac_adaptor import isaac_context as iscctx
from . import controller
from .isaac_scene import scene
from .isaac_scene import world
from .isaac_robots import factory as robot_factory

from .isaac_vfx.particle import (
    CameraView,
    ParticleEffectManager,
    RainParticleEffect,
    SnowParticleEffect,
    FogParticleEffect,
)

from .isaac_graph_vfx import GraphVFXManager, RainGraphParticleEffect
from .isaac_vfx import (
    WeatherLightingManager,
    available_daytime_names as _available_daytime_names,
    available_weather_names as _available_weather_names,
)

from dataclasses import dataclass
import numpy as np
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_SCENE_USD = (
    PROJECT_ROOT / "assets" / "blocks" / "test_field" / "test_simple_city.usd"
)
DEFAULT_ROBOT_TYPE = "spot"
DEFAULT_ROBOT_NAME = "spot_demo"
DEFAULT_CALLBACK_NAME = "simworld_callback"
DEFAULT_WARMUP_FRAMES = 30
DEFAULT_CAMERA_PRIM_PATH = "/OmniverseKit_Persp"
DEFAULT_FALLBACK_SPAWN_POSITION = (0.0, 0.0, 0.8)
DEFAULT_VFX_DT = 1.0 / 50.0
DEFAULT_FOG_BILLBOARD_DEBUG = False
DEFAULT_FOG_BILLBOARD_OPACITY_GAIN = 10.0
DEFAULT_WEATHER = None
DEFAULT_DAYTIME = None
DEFAULT_WEATHER_TIME_SCALE = 1.0


@dataclass
class SimulationConfig:
    usd_path: pathlib.Path = DEFAULT_SCENE_USD
    robot_type: str = DEFAULT_ROBOT_TYPE
    robot_name: str = DEFAULT_ROBOT_NAME
    callback_name: str = DEFAULT_CALLBACK_NAME
    warmup_frames: int = DEFAULT_WARMUP_FRAMES
    camera_prim_path: str = DEFAULT_CAMERA_PRIM_PATH
    fallback_spawn_position: tuple[float, float, float] = (
        DEFAULT_FALLBACK_SPAWN_POSITION
    )
    fog_billboard_debug: bool = DEFAULT_FOG_BILLBOARD_DEBUG
    fog_billboard_opacity_gain: float = DEFAULT_FOG_BILLBOARD_OPACITY_GAIN
    weather: str | None = DEFAULT_WEATHER
    daytime: str | None = DEFAULT_DAYTIME
    sky_texture_path: pathlib.Path | None = None
    sun_intensity: float | None = None
    sky_intensity: float | None = None
    sky_exposure: float | None = None
    weather_start_time: float = 0.0
    weather_time_scale: float = DEFAULT_WEATHER_TIME_SCALE


def available_robot_types() -> tuple[str, ...]:
    return robot_factory.available_robot_types()


def available_weather_names() -> tuple[str, ...]:
    return _available_weather_names()


def available_daytime_names() -> tuple[str, ...]:
    return _available_daytime_names()


def _is_rain_weather(weather_name: str) -> bool:
    return weather_name.lower() in {"rain", "storm"}


def _select_spawn_position(spawn_points, fallback_position):
    if spawn_points:
        return np.asarray(spawn_points[0], dtype=np.float32)
    return np.asarray(fallback_position, dtype=np.float32)


def _map_keyboard_command(command):
    forward, lateral, yaw = command
    return np.array(
        [2.0 * forward + yaw, lateral, 2.0 * yaw],
        dtype=np.float32,
    )


def _normalize_gf_vec3(value, fallback):
    length = value.GetLength()
    if length > 1e-8:
        return value / length
    return fallback


def _get_camera_look_at(camera_prim_path: str):
    context = iscctx.get_isaac_context()
    stage = context.omni_usd.get_context().get_stage()

    if stage is None:
        raise RuntimeError("Cannot read camera pose without an open USD stage.")

    prim = stage.GetPrimAtPath(camera_prim_path)
    if not prim.IsValid():
        raise RuntimeError(f"Invalid camera prim path: {camera_prim_path}")

    Gf = context.pxr_gf
    world_mat = context.omni_usd.get_world_transform_matrix(prim)
    eye = world_mat.ExtractTranslation()
    rotation = world_mat.ExtractRotation()

    forward = _normalize_gf_vec3(
        rotation.TransformDir(Gf.Vec3d(0.0, 0.0, -1.0)),
        Gf.Vec3d(0.0, 0.0, -1.0),
    )
    up = _normalize_gf_vec3(
        rotation.TransformDir(Gf.Vec3d(0.0, 1.0, 0.0)),
        Gf.Vec3d(0.0, 0.0, 1.0),
    )
    target = eye + forward

    return (
        [float(eye[0]), float(eye[1]), float(eye[2])],
        [float(target[0]), float(target[1]), float(target[2])],
        [float(up[0]), float(up[1]), float(up[2])],
    )


def run(config: SimulationConfig | None = None):
    if config is None:
        config = SimulationConfig()

    context = iscctx.init_isaac_context()
    ctrl = None

    try:
        context.initialize_expansion()

        state = {"base_command": np.zeros(3, dtype=np.float32)}
        ctrl = controller.KeyboardVelocityController()

        sim_scene = scene.SimScene(config.usd_path)
        sim_world = world.SimWorld()

        scene_stats = sim_scene.prepare()
        weather_lighting = WeatherLightingManager.from_weather(
            config.weather,
            daytime=config.daytime,
            sky_texture_path=config.sky_texture_path,
            sun_intensity=config.sun_intensity,
            sky_intensity=config.sky_intensity,
            sky_exposure=config.sky_exposure,
            time_scale=config.weather_time_scale,
            start_time_seconds=config.weather_start_time,
        )
        weather_lighting.apply(sim_scene.stage)

        for _ in range(config.warmup_frames):
            weather_lighting.update(DEFAULT_VFX_DT)
            sim_scene.update()

        spawn_position = _select_spawn_position(
            scene_stats.spawn_points,
            config.fallback_spawn_position,
        )

        sim_world.reset()

        robot = robot_factory.create_robot(config.robot_type, config.robot_name)
        robot.spawn(position=spawn_position)
        robot.set_chase_camera(chase=True, cam_prim_path=config.camera_prim_path)

        particle_effects = []
        if _is_rain_weather(weather_lighting.config.name):
            particle_effects.append(
                RainParticleEffect(
                    seed=1,
                    wind_world=(0.2, 0.2, 0.0),
                    particle_count=512,
                    partition_width_segments=2,
                    partition_height_segments=2,
                    wind_variation_angle_degrees=10.0,
                    wind_variation_period_seconds=32.0,
                    wind_variation_randomness=0.35,
                )
            )
        particle_effects.extend(
            [
                # SnowParticleEffect(name="LightSnow", particle_count=300, seed=2),
                # FogParticleEffect(
                #     name="DistantFogBillboard",
                #     mode="distant",
                #     density=0.65,
                #     renderer="billboard",
                #     particle_count=360,
                #     # billboard_debug=config.fog_billboard_debug,
                #     billboard_debug=True,
                #     seed=3,
                #     wind_world=(0.06, 0.02, 0.0),
                #     wind_variation_angle_degrees=8.0,
                #     wind_variation_period_seconds=36.0,
                #     wind_variation_randomness=0.30,
                # ),
                # FogParticleEffect(
                #     name="NearFogBillboard",
                #     mode="near",
                #     density=0.55,
                #     particle_count=200,
                #     # billboard_debug=config.fog_billboard_debug,
                #     billboard_debug=False,
                #     # billboard_use_mdl_shader=True,
                #     billboard_opacity_gain=config.fog_billboard_opacity_gain,
                #     seed=4,
                #     wind_world=(0.04, 0.02, 0.0),
                #     wind_variation_angle_degrees=12.0,
                #     wind_variation_period_seconds=22.0,
                #     wind_variation_randomness=0.45,
                # ),
            ]
        )
        vfx = ParticleEffectManager(particle_effects)

        def simworld_callback(stepsize):
            if not robot.initialized:
                return

            try:
                robot.forward(stepsize)
            except Exception as e:
                print(f"[ERROR] robot.forward failed. Mark reinit required: {e}")

        sim_world.prepare(config.callback_name, simworld_callback)
        sim_world.stop()

        while context.is_running():
            state["base_command"] = _map_keyboard_command(ctrl.get_command())

            sim_scene.update()
            sim_world.update_state()

            eye, target, camera_up = _get_camera_look_at(config.camera_prim_path)
            camera = CameraView.from_look_at(
                position=eye,
                target=target,
                up=camera_up,
            )

            vfx.update_from_camera_view(DEFAULT_VFX_DT, camera)
            # graph_vfx.update_from_camera_view(DEFAULT_VFX_DT, camera)
            weather_lighting.update(DEFAULT_VFX_DT)

            if sim_world.is_stopped():
                robot.mark_reinit_required()
                continue

            world_reinitialized = sim_world.check_reinit()

            if robot.need_reinit:
                if not world_reinitialized:
                    sim_world.reset()
                robot.initialize()

            if sim_world.is_playing() and robot.initialized:
                robot.step(state["base_command"])
                sim_world.step(render=True)

    finally:
        if ctrl is not None:
            ctrl.shutdown()

        print("Closing Isaac Sim.")
        context.close()
