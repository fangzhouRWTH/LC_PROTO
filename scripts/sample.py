from isaacsim import simulation_app
import os


def find_all_lights(stage, root_path="/"):
    """
    Find all USD light prims under root_path.

    root_path:
        "/" means search the whole stage.
        "/World/ImportedScene" means only search under that subtree.
    """
    from pxr import UsdLux, Sdf

    light_schemas = (
        UsdLux.DistantLight,
        UsdLux.DomeLight,
        UsdLux.SphereLight,
        UsdLux.RectLight,
        UsdLux.DiskLight,
        UsdLux.CylinderLight,
    )

    light_type_names = {
        "DistantLight",
        "DomeLight",
        "SphereLight",
        "RectLight",
        "DiskLight",
        "CylinderLight",
        "PortalLight",
    }

    root = stage.GetPrimAtPath(root_path)
    if not root or not root.IsValid():
        raise RuntimeError(f"Invalid root path: {root_path}")

    lights = []

    for prim in stage.Traverse():
        prim_path = prim.GetPath()

        # Limit search scope
        if root_path != "/" and not prim_path.HasPrefix(Sdf.Path(root_path)):
            continue

        type_name = prim.GetTypeName()

        is_light = False

        # Standard typed USD lights
        for schema in light_schemas:
            if prim.IsA(schema):
                is_light = True
                break

        # Fallback for custom / extension light types
        if type_name in light_type_names:
            is_light = True

        if is_light:
            lights.append(prim)

    return lights


def deactivate_all_lights(stage, root_path="/"):
    """
    Deactivate all light prims under root_path.
    This is safer for referenced USD assets.
    """
    lights = find_all_lights(stage, root_path=root_path)

    if not lights:
        print("[INFO] No lights found.")
        return []

    deactivated = []

    for light in lights:
        path = light.GetPath()
        print(f"[INFO] Deactivating light: {path}")
        light.SetActive(False)
        deactivated.append(str(path))

    print(f"[OK] Deactivated {len(deactivated)} light(s).")
    return deactivated


def add_natural_light(stage):
    """
    Natural daylight preset:
    - Sun: strong direct light
    - Sky: stronger ambient / indirect-like dome light
    - Optional fill light: softens very dark shadow side
    """
    from pxr import UsdLux, UsdGeom, Gf, Sdf

    # Create light group
    UsdGeom.Xform.Define(stage, "/World/Light")

    # ------------------------------------------------------------
    # 1. Sun light: direct sunlight
    # ------------------------------------------------------------
    sun_path = "/World/Light/Sun"
    sun = UsdLux.DistantLight.Define(stage, sun_path)

    sun.CreateIntensityAttr(1200.0)
    sun.CreateAngleAttr(0.8)
    sun.CreateColorAttr(Gf.Vec3f(1.0, 0.96, 0.88))

    sun_xform = UsdGeom.Xformable(sun.GetPrim())
    sun_xform.ClearXformOpOrder()
    sun_xform.AddRotateXYZOp().Set(Gf.Vec3f(-45.0, 0.0, 35.0))

    # ------------------------------------------------------------
    # 2. Sky light: ambient/environment light
    # ------------------------------------------------------------
    sky_path = "/World/Light/Sky"
    sky = UsdLux.DomeLight.Define(stage, sky_path)

    # Increase this first if shadow side is too dark.
    sky.CreateIntensityAttr(300.0)

    # Exposure is exponential: +1 roughly doubles brightness.
    sky.CreateExposureAttr(1.0)

    # Cool sky color.
    sky.CreateColorAttr(Gf.Vec3f(0.78, 0.86, 1.0))

    # Optional skybox / HDRI background
    sky_texture = "/home/fangzhou/projects/LC_01/assets/textures/sky/sky_01.png"

    sky_texture_path = os.path.abspath(sky_texture)

    if not os.path.exists(sky_texture_path):
        raise FileNotFoundError(f"Sky texture not found: {sky_texture_path}")

    # Use lat-long / equirectangular environment map.
    sky.CreateTextureFileAttr(Sdf.AssetPath(sky_texture_path))
    sky.CreateTextureFormatAttr("latlong")

    print(f"[OK] Added skybox texture: {sky_texture_path}")

    # ------------------------------------------------------------
    # 3. Optional soft fill light
    # ------------------------------------------------------------
    fill_path = "/World/Light/Fill"
    fill = UsdLux.DistantLight.Define(stage, fill_path)

    # Much weaker than sun.
    fill.CreateIntensityAttr(120.0)
    fill.CreateAngleAttr(5.0)
    fill.CreateColorAttr(Gf.Vec3f(0.75, 0.82, 1.0))

    # Opposite-ish direction from sun to brighten shadow side.
    fill_xform = UsdGeom.Xformable(fill.GetPrim())
    fill_xform.ClearXformOpOrder()
    fill_xform.AddRotateXYZOp().Set(Gf.Vec3f(-25.0, 0.0, -145.0))

    print("[OK] Added natural light preset with stronger sky / indirect fill.")


def ensure_physics_scene(stage, scene_path="/World/PhysicsScene"):
    """
    Ensure the USD stage has a physics scene.
    Collision APIs can exist without this, but actual simulation needs a physics scene.
    """
    from pxr import UsdPhysics, Gf

    prim = stage.GetPrimAtPath(scene_path)
    if prim and prim.IsValid():
        return prim

    physics_scene = UsdPhysics.Scene.Define(stage, scene_path)

    # Optional gravity settings
    physics_scene.CreateGravityDirectionAttr(Gf.Vec3f(0.0, 0.0, -1.0))
    physics_scene.CreateGravityMagnitudeAttr(9.81)

    print(f"[OK] Created physics scene: {scene_path}")
    return physics_scene.GetPrim()


def is_supported_geometry_prim(prim):
    """
    Return True if the prim is a common geometry type that can reasonably receive collision.
    """
    from pxr import UsdGeom

    return (
        prim.IsA(UsdGeom.Mesh)
        or prim.IsA(UsdGeom.Cube)
        or prim.IsA(UsdGeom.Sphere)
        or prim.IsA(UsdGeom.Capsule)
        or prim.IsA(UsdGeom.Cylinder)
        or prim.IsA(UsdGeom.Cone)
    )


def apply_collision_to_prim(prim, approximation="convexHull"):
    """
    Apply collision API to one geometry prim.

    For Mesh:
        Apply CollisionAPI + MeshCollisionAPI and set approximation.

    For primitive geometry:
        Apply CollisionAPI only.
    """
    from pxr import UsdGeom, UsdPhysics

    if not prim or not prim.IsValid():
        return False

    if prim.IsInstanceProxy():
        print(f"[SKIP] Instance proxy cannot be edited directly: {prim.GetPath()}")
        return False

    if not is_supported_geometry_prim(prim):
        return False

    # Generic collision API
    if not prim.HasAPI(UsdPhysics.CollisionAPI):
        UsdPhysics.CollisionAPI.Apply(prim)

    # Mesh-specific collision approximation
    if prim.IsA(UsdGeom.Mesh):
        if not prim.HasAPI(UsdPhysics.MeshCollisionAPI):
            mesh_collision_api = UsdPhysics.MeshCollisionAPI.Apply(prim)
        else:
            mesh_collision_api = UsdPhysics.MeshCollisionAPI(prim)

        mesh_collision_api.CreateApproximationAttr().Set(approximation)

        print(f"[OK] Mesh collider: {prim.GetPath()} | approximation = {approximation}")
    else:
        print(f"[OK] Primitive collider: {prim.GetPath()}")

    return True


def add_collisions_to_stage(stage, root_path="/", approximation="convexHull"):
    """
    Traverse a subtree and add collision APIs to all supported geometry prims.
    """
    from pxr import Sdf

    root = stage.GetPrimAtPath(root_path)
    if not root or not root.IsValid():
        raise RuntimeError(f"Invalid collision root path: {root_path}")

    ensure_physics_scene(stage)

    root_sdf_path = Sdf.Path(root_path)

    count = 0

    for prim in stage.Traverse():
        prim_path = prim.GetPath()

        if root_path != "/" and not prim_path.HasPrefix(root_sdf_path):
            continue

        if apply_collision_to_prim(prim, approximation=approximation):
            count += 1

    print(f"[OK] Added collision APIs to {count} prim(s) under {root_path}.")
    return count


def add_robot_reference(stage, robot_usd, robot_prim_path, robot_pos, robot_yaw_deg):
    import os
    from pxr import UsdGeom, Gf

    if robot_usd is None:
        print("[INFO] No robot USD provided. Skipping robot placement.")
        return None

    # robot_usd = os.path.abspath(robot_usd)

    # if not os.path.exists(robot_usd):
    #     raise FileNotFoundError(f"Robot USD not found: {robot_usd}")

    # Create parent scope if needed
    UsdGeom.Xform.Define(stage, "/World/Robot")

    # Define robot root prim
    robot_xform = UsdGeom.Xform.Define(stage, robot_prim_path)
    robot_prim = robot_xform.GetPrim()

    # Add USD reference
    robot_prim.GetReferences().AddReference(robot_usd)

    # Set transform
    xformable = UsdGeom.Xformable(robot_prim)
    xformable.ClearXformOpOrder()

    xformable.AddTranslateOp().Set(Gf.Vec3d(*robot_pos))
    xformable.AddRotateXYZOp().Set(Gf.Vec3f(0.0, 0.0, robot_yaw_deg))

    scale_op = xformable.GetScaleOp()

    if scale_op:
        scale_op.Set(Gf.Vec3d(1.0, 1.0, 1.0))
    else:
        scale_op = xformable.AddScaleOp(precision=UsdGeom.XformOp.PrecisionDouble)
        scale_op.Set(Gf.Vec3d(1.0, 1.0, 1.0))

    print(f"[OK] Robot referenced:")
    print(f"     USD : {robot_usd}")
    print(f"     Prim: {robot_prim_path}")

    return robot_prim


def create_robot_articulation(robot_prim_path):
    try:
        from isaacsim.core.prims import SingleArticulation
    except ImportError:
        from omni.isaac.core.prims import SingleArticulation

    robot = SingleArticulation(
        prim_path=robot_prim_path,
        name="spot_robot",
    )

    print(f"[OK] Created SingleArticulation wrapper for: {robot_prim_path}")
    return robot


def start_simulation():
    import omni.timeline

    timeline = omni.timeline.get_timeline_interface()
    timeline.play()

    print("[OK] Simulation timeline started.")
    return timeline


def initialize_robot_after_sim_start(robot, simulation_app, warmup_frames=30):
    if robot is None:
        return

    # Let simulation start and physics initialize
    for _ in range(warmup_frames):
        simulation_app.update()

    robot.initialize()

    print("[OK] Robot articulation initialized.")

    try:
        joint_names = robot.dof_names
        print(f"[INFO] Robot DOF count: {len(joint_names)}")
        for i, name in enumerate(joint_names):
            print(f"  [{i}] {name}")
    except Exception as e:
        print(f"[WARN] Could not print joint names: {e}")


def set_robot_camera_view(robot_pos):
    try:
        from isaacsim.core.utils.viewports import set_camera_view
    except ImportError:
        from omni.isaac.core.utils.viewports import set_camera_view

    x, y, z = robot_pos

    eye = [x - 4.0, y - 4.0, z + 2.2]
    target = [x, y, z + 0.5]

    set_camera_view(
        eye=eye,
        target=target,
        camera_prim_path="/OmniverseKit_Persp",
    )

    print("[OK] Camera view set.")


def main():
    # Isaac Sim 5.x 推荐路径
    try:
        from isaacsim.simulation_app import SimulationApp
    except ImportError:
        # 兼容旧版本 Isaac Sim
        from omni.isaac.kit import SimulationApp

    # 启动 Isaac Sim / Omniverse Kit
    simulation_app = SimulationApp(
        {
            "headless": False,
            "width": 1280,
            "height": 720,
        }
    )

    print("[OK] Isaac Sim started.")

    import omni.usd
    from pxr import UsdGeom

    usd_path = "/home/fangzhou/projects/LC_01/assets/blocks/usd_001/block_overall.usd"

    context = omni.usd.get_context()
    context.open_stage(usd_path)

    for _ in range(30):
        simulation_app.update()

    stage = context.get_stage()

    deactivate_all_lights(stage)

    add_collisions_to_stage(
        stage,
        # root_path=args.collision_root,
        approximation="meshSimplification",
    )

    add_natural_light(stage)

    robot_usd_path = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Robots/BostonDynamics/spot/spot.usd"
    robot_prim_path = "/World/Robot/Spot"
    robot_yaw = 0.0
    robot_pos = [0.0, 0.0, 0.8]
    robot_prim = add_robot_reference(
        stage=stage,
        robot_usd=robot_usd_path,
        robot_prim_path=robot_prim_path,
        robot_pos=robot_pos,
        robot_yaw_deg=robot_yaw,
    )

    robot = None
    if robot_prim is not None:
        robot = create_robot_articulation(robot_prim_path)

    if robot_prim is not None:
        set_robot_camera_view(robot_pos)

    timeline = start_simulation()

    initialize_robot_after_sim_start(robot, simulation_app)

    while simulation_app.is_running():
        simulation_app.update()

    print("[OK] Closing Isaac Sim.")

    simulation_app.close()


if __name__ == "__main__":
    main()
