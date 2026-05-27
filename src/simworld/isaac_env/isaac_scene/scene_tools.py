from ..isaac_adaptor import isaac_context as iscctx

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SKY_TEXTURE_PATH = PROJECT_ROOT / "assets" / "textures" / "sky" / "sky_01.png"


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
    UsdLux = iscctx.get_isaac_context().pxr_usd_lux
    Sdf = iscctx.get_isaac_context().pxr_Sdf
    lights = find_all_lights(stage, root_path=root_path)

    if not lights:
        print("[INFO] No lights found.")
        return []

    deactivated = []

    for light in lights:
        path = light.GetPath()
        print(f"[INFO] Deactivating light: {path}")
        if light.IsA(UsdLux.DomeLight):
            dome_light = UsdLux.DomeLight(light)
            texture_attr = dome_light.GetTextureFileAttr()
            if texture_attr and texture_attr.IsValid():
                texture_attr.Set(Sdf.AssetPath(""))
        light.SetActive(False)
        deactivated.append(str(path))

    print(f"[OK] Deactivated {len(deactivated)} light(s).")
    return deactivated


def add_natural_light(stage, sky_texture_path: str | Path = DEFAULT_SKY_TEXTURE_PATH):
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

    light_root = UsdGeom.Xform.Define(stage, "/World/Light")
    light_root.GetPrim().SetActive(True)

    # ------------------------------------------------------------
    # 1. Sun light: direct sunlight
    # ------------------------------------------------------------
    sun_path = "/World/Light/Sun"
    sun = UsdLux.DistantLight.Define(stage, sun_path)
    sun.GetPrim().SetActive(True)

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
    sky.GetPrim().SetActive(True)

    # Increase this first if shadow side is too dark.
    sky.CreateIntensityAttr(300.0)

    # Exposure is exponential: +1 roughly doubles brightness.
    sky.CreateExposureAttr(1.0)

    # Cool sky color.
    sky.CreateColorAttr(Gf.Vec3f(0.78, 0.86, 1.0))

    # Optional skybox / HDRI background
    sky_texture_path = Path(sky_texture_path).expanduser().resolve()

    if not sky_texture_path.exists():
        raise FileNotFoundError(f"Sky texture not found: {sky_texture_path}")

    # Use lat-long / equirectangular environment map.
    sky.CreateTextureFileAttr(Sdf.AssetPath(str(sky_texture_path)))
    sky.CreateTextureFormatAttr("latlong")

    print(f"[OK] Added skybox texture: {sky_texture_path}")

    # ------------------------------------------------------------
    # 3. Optional soft fill light
    # ------------------------------------------------------------
    fill_path = "/World/Light/Fill"
    fill = UsdLux.DistantLight.Define(stage, fill_path)
    fill.GetPrim().SetActive(True)

    # Much weaker than sun.
    fill.CreateIntensityAttr(120.0)
    fill.CreateAngleAttr(5.0)
    fill.CreateColorAttr(Gf.Vec3f(0.75, 0.82, 1.0))

    # Opposite-ish direction from sun to brighten shadow side.
    fill_xform = UsdGeom.Xformable(fill.GetPrim())
    fill_xform.ClearXformOpOrder()
    fill_xform.AddRotateXYZOp().Set(Gf.Vec3f(-25.0, 0.0, -145.0))

    print("[OK] Added natural light preset with stronger sky / indirect fill.")


def extract_prim_position(prim):
    if not prim.IsValid():
        raise RuntimeError("Invalid prim")
    omni_usd = iscctx.get_isaac_context().omni_usd
    world_mat = omni_usd.get_world_transform_matrix(prim)
    pos = world_mat.ExtractTranslation()

    return [float(pos[0]), float(pos[1]), float(pos[2])]
