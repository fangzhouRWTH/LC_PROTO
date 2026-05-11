# scripts/scene_assembly_demo.py

import argparse
import math
import os
import random


def parse_args():
    parser = argparse.ArgumentParser("Minimal Isaac Sim scene assembly demo")

    parser.add_argument(
        "--scene_usd",
        type=str,
        required=True,
        help="Fixed USD scene to load.",
    )

    parser.add_argument(
        "--robot_usd",
        type=str,
        required=True,
        help="Robot USD file to reference into the scene.",
    )

    parser.add_argument(
        "--asset_usd",
        type=str,
        action="append",
        default=[],
        help="Small object USD asset. Can be passed multiple times.",
    )

    parser.add_argument(
        "--num_objects",
        type=int,
        default=10,
        help="Number of small objects to place.",
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run Isaac Sim in headless mode.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    parser.add_argument(
        "--save_as",
        type=str,
        default=None,
        help="Optional path to save the assembled stage.",
    )

    return parser.parse_args()


def launch_isaac_sim(headless: bool):
    """
    Important:
    Isaac Sim / Omniverse modules should be imported after SimulationApp starts.
    """
    try:
        # Newer Isaac Sim style
        from isaacsim.simulation_app import SimulationApp
    except ImportError:
        # Older Isaac Sim style
        from omni.isaac.kit import SimulationApp

    config = {
        "headless": headless,
        "width": 1280,
        "height": 720,
    }

    simulation_app = SimulationApp(config)
    return simulation_app


def open_usd_stage(scene_usd: str):
    import omni.usd

    if not os.path.exists(scene_usd):
        raise FileNotFoundError(f"Scene USD not found: {scene_usd}")

    context = omni.usd.get_context()
    context.open_stage(scene_usd)

    # Give Kit a few frames to finish loading the stage.
    return context


def get_stage():
    import omni.usd

    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("Failed to get current USD stage.")
    return stage


def ensure_xform(stage, prim_path: str):
    from pxr import UsdGeom

    prim = stage.GetPrimAtPath(prim_path)
    if prim and prim.IsValid():
        return prim

    xform = UsdGeom.Xform.Define(stage, prim_path)
    return xform.GetPrim()


def set_transform(prim, translation=(0, 0, 0), rotation_deg=(0, 0, 0), scale=(1, 1, 1)):
    """
    Set transform with raw USD xform ops.
    rotation_deg is XYZ Euler in degrees.
    """
    from pxr import UsdGeom, Gf

    xformable = UsdGeom.Xformable(prim)
    xformable.ClearXformOpOrder()

    translate_op = xformable.AddTranslateOp()
    rotate_op = xformable.AddRotateXYZOp()
    scale_op = xformable.AddScaleOp()

    translate_op.Set(Gf.Vec3d(*translation))
    rotate_op.Set(Gf.Vec3f(*rotation_deg))
    scale_op.Set(Gf.Vec3f(*scale))


def add_usd_reference(stage, prim_path: str, usd_path: str, translation=(0, 0, 0), rotation_deg=(0, 0, 0), scale=(1, 1, 1)):
    if not os.path.exists(usd_path):
        raise FileNotFoundError(f"USD asset not found: {usd_path}")

    prim = ensure_xform(stage, prim_path)
    prim.GetReferences().AddReference(usd_path)
    set_transform(prim, translation, rotation_deg, scale)
    return prim


def place_small_assets(stage, asset_usd_list, num_objects: int, seed: int):
    if not asset_usd_list:
        print("[Warning] No small asset USDs provided. Skipping object placement.")
        return []

    random.seed(seed)

    ensure_xform(stage, "/World/PlacedObjects")

    placed = []

    # A very simple placement area.
    # Later you can replace this with:
    # - road-aware placement
    # - obstacle-free sampling
    # - semantic zones
    # - collision checking
    x_min, x_max = -5.0, 5.0
    y_min, y_max = -5.0, 5.0

    for i in range(num_objects):
        asset_usd = random.choice(asset_usd_list)

        x = random.uniform(x_min, x_max)
        y = random.uniform(y_min, y_max)
        z = 0.0

        yaw = random.uniform(0.0, 360.0)

        # Keep small objects small.
        s = random.uniform(0.8, 1.2)

        prim_path = f"/World/PlacedObjects/Object_{i:03d}"

        prim = add_usd_reference(
            stage=stage,
            prim_path=prim_path,
            usd_path=asset_usd,
            translation=(x, y, z),
            rotation_deg=(0, 0, yaw),
            scale=(s, s, s),
        )

        placed.append(prim_path)

    print(f"Placed {len(placed)} small assets.")
    return placed


def place_robot(stage, robot_usd: str):
    ensure_xform(stage, "/World/Robot")

    robot_prim = add_usd_reference(
        stage=stage,
        prim_path="/World/Robot",
        usd_path=robot_usd,
        translation=(0.0, 0.0, 0.0),
        rotation_deg=(0.0, 0.0, 0.0),
        scale=(1.0, 1.0, 1.0),
    )

    print(f"Placed robot at /World/Robot from: {robot_usd}")
    return robot_prim


def save_stage_if_needed(stage, save_as: str | None):
    if save_as is None:
        return

    save_dir = os.path.dirname(os.path.abspath(save_as))
    os.makedirs(save_dir, exist_ok=True)

    stage.GetRootLayer().Export(save_as)
    print(f"Saved assembled stage to: {save_as}")


def main():
    args = parse_args()

    simulation_app = launch_isaac_sim(args.headless)

    try:
        # All Isaac / Omniverse imports and USD work happen after SimulationApp launch.
        open_usd_stage(args.scene_usd)

        # Let the app process the stage load.
        for _ in range(10):
            simulation_app.update()

        stage = get_stage()

        place_small_assets(
            stage=stage,
            asset_usd_list=args.asset_usd,
            num_objects=args.num_objects,
            seed=args.seed,
        )

        place_robot(stage, args.robot_usd)

        save_stage_if_needed(stage, args.save_as)

        # Keep GUI alive if not headless.
        if not args.headless:
            print("Scene assembled. Close the Isaac Sim window to exit.")
            while simulation_app.is_running():
                simulation_app.update()
        else:
            for _ in range(30):
                simulation_app.update()

    finally:
        simulation_app.close()


if __name__ == "__main__":
    main()