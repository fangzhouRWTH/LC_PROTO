from engine.scene_placeholder import (
    collect_placeholder_prim_paths,
    normalize_placeholder_disposition,
)

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
    """Backward-compatible alias for hidden/visible only."""
    disposition = normalize_placeholder_disposition(value)
    if disposition == "remove":
        raise ValueError(
            "dynamic_placeholder_visibility does not support 'remove'; "
            "use --placeholder-disposition remove"
        )
    return disposition


def _set_imageable_visibility(prim, *, visible: bool) -> None:
    UsdGeom = iscctx.get_isaac_context().pxr_usd_geom
    if not prim or not prim.IsValid():
        return
    if not prim.IsA(UsdGeom.Imageable):
        for child in prim.GetChildren():
            _set_imageable_visibility(child, visible=visible)
        return
    imageable = UsdGeom.Imageable(prim)
    if visible:
        imageable.MakeVisible()
    else:
        imageable.MakeInvisible()


def apply_placeholder_disposition(stage, stats, disposition="hidden"):
    """
    Hide, show, or remove all placeholder prims after parse/preprocess.

    ``hidden`` turns off rendering via UsdGeom.Imageable invisibility (incl. subtree).
    ``remove`` deletes placeholder prims from the stage (deepest paths first).
    """
    mode = normalize_placeholder_disposition(disposition)
    paths = collect_placeholder_prim_paths(stats)
    if not paths:
        print("[INFO] No placeholder prims to update.")
        return []

    updated: list[str] = []
    if mode == "remove":
        for prim_path in paths:
            prim = stage.GetPrimAtPath(prim_path)
            if not prim or not prim.IsValid():
                continue
            stage.RemovePrim(prim.GetPath())
            updated.append(str(prim_path))
        print(f"[INFO] Removed {len(updated)} placeholder prim(s) from stage.")
        return updated

    visible = mode == "visible"
    for prim_path in paths:
        prim = stage.GetPrimAtPath(prim_path)
        if not prim or not prim.IsValid():
            continue
        _set_imageable_visibility(prim, visible=visible)
        updated.append(str(prim_path))

    print(
        f"[INFO] Placeholder prims {mode}: {len(updated)} prim(s) "
        f"(rendering {'on' if visible else 'off'})."
    )
    return updated


def apply_dynamic_placeholder_visibility(stage, stats, visibility="hidden"):
    """Backward-compatible wrapper; prefer ``apply_placeholder_disposition``."""
    return apply_placeholder_disposition(stage, stats, disposition=visibility)
