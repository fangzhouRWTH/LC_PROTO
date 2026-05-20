from .isaac_adaptor import isaac_context as iscctx
from . import controller
from .isaac_scene import scene
from .isaac_scene import world
from .isaac_robots import spot_demo

from dataclasses import dataclass
import numpy as np
import pathlib


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_SCENE_USD = (
    PROJECT_ROOT / "assets" / "blocks" / "test_field" / "test_simple_city.usd"
)


@dataclass
class SimulationConfig:
    usd_path: pathlib.Path = DEFAULT_SCENE_USD
    robot_name: str = "spot_demo"
    callback_name: str = "simworld_callback"
    warmup_frames: int = 30
    camera_prim_path: str = "/OmniverseKit_Persp"
    fallback_spawn_position: tuple[float, float, float] = (0.0, 0.0, 0.8)


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

        for _ in range(config.warmup_frames):
            sim_scene.update()

        scene_stats = sim_scene.prepare()
        spawn_position = _select_spawn_position(
            scene_stats.spawn_points,
            config.fallback_spawn_position,
        )

        sim_world.reset()

        spot = spot_demo.SpotDemo(config.robot_name)
        spot.spawn(position=spawn_position)
        spot.set_chase_camera(chase=True, cam_prim_path=config.camera_prim_path)

        def simworld_callback(stepsize):
            if not spot.initialized:
                return

            try:
                spot.forward(stepsize)
            except Exception as e:
                print(f"[ERROR] spot.forward failed. Mark reinit required: {e}")

        sim_world.prepare(config.callback_name, simworld_callback)
        sim_world.stop()

        while context.is_running():
            state["base_command"] = _map_keyboard_command(ctrl.get_command())

            sim_scene.update()
            sim_world.update_state()

            if sim_world.is_stopped():
                spot.mark_reinit_required()
                continue

            world_reinitialized = sim_world.check_reinit()

            if spot.need_reinit:
                if not world_reinitialized:
                    sim_world.reset()
                spot.initialize_spot()

            if sim_world.is_playing() and spot.initialized:
                spot.step(state["base_command"])
                sim_world.step(render=True)

    finally:
        if ctrl is not None:
            ctrl.shutdown()

        print("Closing Isaac Sim.")
        context.close()
