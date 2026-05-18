# from isaacsim.simulation_app import SimulationApp
from .isaac_adaptor import isaac_context as iscctx
from . import camera
from . import controller
from .isaac_scene import scene
from .isaac_scene import world

import pathlib


def run():
    context = iscctx.init_isaac_context()
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

    while context.is_running():
        context.update()
        continue

    print("[OK] Closing Isaac Sim.")

    context.close()
