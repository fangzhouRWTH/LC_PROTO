from ..isaac_adaptor import isaac_context as iscctx


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


def add_natural_light(stage, sky_texture_path=None):
    """Compatibility wrapper for the VFX weather lighting module."""

    from ..isaac_vfx.weather import WeatherLightingManager

    manager = WeatherLightingManager.from_weather(
        "sunny",
        sky_texture_path=sky_texture_path,
    )
    manager.apply(stage)
    return manager


def extract_prim_position(prim):
    if not prim.IsValid():
        raise RuntimeError("Invalid prim")
    omni_usd = iscctx.get_isaac_context().omni_usd
    world_mat = omni_usd.get_world_transform_matrix(prim)
    pos = world_mat.ExtractTranslation()

    return [float(pos[0]), float(pos[1]), float(pos[2])]


def normalize_dynamic_placeholder_visibility(value):
    normalized = str(value or "hidden").strip().lower()
    if normalized in {"hidden", "hide", "off", "false", "0"}:
        return "hidden"
    if normalized in {"visible", "show", "on", "true", "1"}:
        return "visible"
    raise ValueError(
        "dynamic_placeholder_visibility must be 'hidden' or 'visible', "
        f"got {value!r}"
    )


def apply_dynamic_placeholder_visibility(stage, stats, visibility="hidden"):
    normalized = normalize_dynamic_placeholder_visibility(visibility)
    visible = normalized == "visible"
    paths = _dynamic_placeholder_paths(stats)
    if not paths:
        return []

    UsdGeom = iscctx.get_isaac_context().pxr_usd_geom
    updated = []
    for prim_path in paths:
        prim = stage.GetPrimAtPath(prim_path)
        if not prim or not prim.IsValid():
            continue
        imageable = UsdGeom.Imageable(prim)
        if visible:
            imageable.MakeVisible()
        else:
            imageable.MakeInvisible()
        updated.append(str(prim_path))

    print(
        f"[INFO] Dynamic placeholders {normalized}: "
        f"{len(updated)} prim(s)."
    )
    return updated


def _dynamic_placeholder_paths(stats):
    paths = []
    field_names = (
        "pedestrian_spawn_points",
        "pedestrian_goal_points",
        "pedestrian_routes",
        "vehicle_spawn_points",
        "vehicle_goal_points",
        "vehicle_routes",
        "vehicle_lanes",
        "sidewalk_areas",
        "crosswalk_areas",
    )
    for field_name in field_names:
        for placeholder in getattr(stats, field_name, []) or []:
            prim_path = getattr(placeholder, "prim_path", "")
            if prim_path and prim_path not in paths:
                paths.append(prim_path)
    return paths
