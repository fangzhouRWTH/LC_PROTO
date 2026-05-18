from ..isaac_adaptor import isaac_context as iscctx

import os


def find_all_lights(stage, root_path="/"):
    """
    Find all USD light prims under root_path.

    root_path:
        "/" means search the whole stage.
        "/World/ImportedScene" means only search under that subtree.
    """
    UsdLux = iscctx.get_isaac_context().pxr_usd_lux
    Sdf = iscctx.get_isaac_context().pxr_Sdf
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

    UsdGeom = iscctx.get_isaac_context().pxr_usd_geom
    UsdLux = iscctx.get_isaac_context().pxr_usd_lux
    Gf = iscctx.get_isaac_context().pxr_gf
    Sdf = iscctx.get_isaac_context().pxr_Sdf

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
