from .isaac_adaptor import isaac_context as iscctx
from . import camera
from . import controller
from .isaac_scene import scene
from .isaac_scene import world
from .isaac_robots import spot_demo

import numpy as np
import pathlib


def run():
    context = iscctx.init_isaac_context()
    context.initialize_expansion()

    state = dict()
    state["base_command"] = np.zeros(3, dtype=np.float32)
    cam = camera.ChaseViewportCamera()
    ctrl = controller.KeyboardVelocityController()

    usd_path = pathlib.Path(
        "/home/fangzhou/projects/LC_01/assets/blocks/test_field/test_simple_city.usd"
    )

    simScene = scene.SimScene(usd_path)
    simWorld = world.SimWorld()

    for _ in range(30):
        context.update()

    simScene.prepare()
    simworld_callback_name = "simworld_callback"

    simWorld.reset()

    spot = spot_demo.SpotDemo("spot_demo")
    spot.spawn(position=np.array([0.0, 0.0, 1.2]))
    spot.set_chase_camera(chase=True, cam_prim_path="/OmniverseKit_Persp")

    def simworld_callback(stepsize):
        if not spot.initialized:
            return

        try:
            spot.forward(stepsize)
        except Exception as e:
            print(f"[ERROR] spot.forward failed. Mark reinit required: {e}")

    simWorld.prepare(simworld_callback_name, simworld_callback)
    simWorld.stop()

    while context.is_running():
        cmd = ctrl.get_command()

        f = cmd[0]
        l = cmd[1]
        y = cmd[2]

        state["base_command"] = np.array([2.0 * f + y, l, 2.0 * y], dtype=np.float32)

        simScene.update()
        simWorld.update_state()

        if simWorld.is_stopped():
            spot.mark_reinit_required()
            continue

        world_reinitialized = simWorld.check_reinit()

        if spot.need_reinit:
            if not world_reinitialized:
                simWorld.reset()
            spot.initialize_spot()

        if simWorld.is_playing() and spot.initialized:
            spot.step(state["base_command"])
            simWorld.step(render=True)

    print("Closing Isaac Sim.")

    context.close()
