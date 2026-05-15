from isaacsim.simulation_app import SimulationApp
from . import camera
from .isaac_adaptor import isaac_context as iscctx


def run():
    simulation_app = SimulationApp(
        {
            "headless": False,
            "width": 1280,
            "height": 720,
        }
    )

    context = iscctx.IsaacContext()
    cam = camera.ChaseViewportCamera(context)

    for _ in range(30):
        simulation_app.update()

        while simulation_app.is_running():

            simulation_app.update()
            continue

    print("[OK] Closing Isaac Sim.")

    simulation_app.close()
