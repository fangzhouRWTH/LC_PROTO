from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_SENSOR_MATERIAL_EXCLUDED_ROOTS = (
    "/World/SimWorldSensors",
    "/World/VFX",
)


@dataclass
class MaterialBindingSnapshot:
    prim_path: str
    relationships: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass
class MaterialOverrideState:
    stage: object
    material_path: str
    snapshots: list[MaterialBindingSnapshot] = field(default_factory=list)


def normal_to_rgb(
    normal_xyz: tuple[float, float, float],
) -> tuple[float, float, float]:
    return tuple(
        max(0.0, min(1.0, float(channel) * 0.5 + 0.5))
        for channel in normal_xyz
    )


def apply_flat_material_override(
    stage,
    *,
    color_rgb: tuple[float, float, float],
    material_path: str,
    excluded_roots: tuple[str, ...] = DEFAULT_SENSOR_MATERIAL_EXCLUDED_ROOTS,
) -> MaterialOverrideState | None:
    if stage is None:
        return None

    try:
        from pxr import UsdShade
    except Exception as exc:
        print(f"[WARNING] Could not import UsdShade for material override: {exc}")
        return None

    context = _get_isaac_context()
    UsdGeom = context.pxr_usd_geom
    material = _ensure_flat_preview_material(
        stage,
        material_path=material_path,
        color_rgb=color_rgb,
    )
    if material is None:
        return None

    snapshots: list[MaterialBindingSnapshot] = []
    for prim in stage.Traverse():
        if not prim.IsValid():
            continue
        if _is_excluded(str(prim.GetPath()), excluded_roots):
            continue
        if not prim.IsA(UsdGeom.Gprim):
            continue

        snapshots.append(_snapshot_material_bindings(prim))
        UsdShade.MaterialBindingAPI(prim).Bind(material)

    return MaterialOverrideState(
        stage=stage,
        material_path=material_path,
        snapshots=snapshots,
    )


def restore_material_override(state: MaterialOverrideState | None) -> bool:
    if state is None:
        return False

    restored = False
    context = _get_isaac_context()
    Sdf = context.pxr_Sdf

    for snapshot in state.snapshots:
        prim = state.stage.GetPrimAtPath(snapshot.prim_path)
        if not prim or not prim.IsValid():
            continue

        for relationship in list(prim.GetRelationships()):
            name = relationship.GetName()
            if name.startswith("material:binding"):
                prim.RemoveProperty(name)

        for name, targets in snapshot.relationships.items():
            relationship = prim.CreateRelationship(name)
            relationship.SetTargets([Sdf.Path(target) for target in targets])
        restored = True

    return restored


def apply_normal_mdl_material_override(
    stage,
    *,
    material_path: str,
    shader_path: str | Path,
    excluded_roots: tuple[str, ...] = DEFAULT_SENSOR_MATERIAL_EXCLUDED_ROOTS,
) -> MaterialOverrideState | None:
    if stage is None:
        return None

    try:
        from pxr import UsdShade
    except Exception as exc:
        print(f"[WARNING] Could not import UsdShade for normal MDL override: {exc}")
        return None

    context = _get_isaac_context()
    UsdGeom = context.pxr_usd_geom
    material = _ensure_normal_mdl_material(
        stage,
        material_path=material_path,
        shader_path=shader_path,
    )
    if material is None:
        return None

    snapshots: list[MaterialBindingSnapshot] = []
    for prim in stage.Traverse():
        if not prim.IsValid():
            continue
        if _is_excluded(str(prim.GetPath()), excluded_roots):
            continue
        if not prim.IsA(UsdGeom.Gprim):
            continue

        snapshots.append(_snapshot_material_bindings(prim))
        UsdShade.MaterialBindingAPI(prim).Bind(material)

    return MaterialOverrideState(
        stage=stage,
        material_path=material_path,
        snapshots=snapshots,
    )


def _get_isaac_context():
    from ..isaac_adaptor import isaac_context as iscctx

    return iscctx.get_isaac_context()


def _ensure_flat_preview_material(
    stage,
    *,
    material_path: str,
    color_rgb: tuple[float, float, float],
):
    try:
        from pxr import UsdShade
    except Exception as exc:
        print(f"[WARNING] Could not import UsdShade for material override: {exc}")
        return None

    context = _get_isaac_context()
    Gf = context.pxr_gf
    Sdf = context.pxr_Sdf
    UsdGeom = context.pxr_usd_geom

    from .camera_utils import ensure_xform_path

    parent_path = material_path.rsplit("/", 1)[0]
    ensure_xform_path(stage, parent_path, UsdGeom)

    material = UsdShade.Material.Define(stage, material_path)
    shader = UsdShade.Shader.Define(stage, f"{material_path}/PreviewSurface")
    shader.CreateIdAttr("UsdPreviewSurface")
    color = Gf.Vec3f(
        float(color_rgb[0]),
        float(color_rgb[1]),
        float(color_rgb[2]),
    )
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(color)
    shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(color)
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(1.0)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
    material.CreateSurfaceOutput().ConnectToSource(
        shader.ConnectableAPI(),
        "surface",
    )
    return material


def _ensure_normal_mdl_material(
    stage,
    *,
    material_path: str,
    shader_path: str | Path,
):
    try:
        from pxr import UsdShade
    except Exception as exc:
        print(f"[WARNING] Could not import UsdShade for normal MDL override: {exc}")
        return None

    context = _get_isaac_context()
    Sdf = context.pxr_Sdf
    UsdGeom = context.pxr_usd_geom

    from .camera_utils import ensure_xform_path

    parent_path = material_path.rsplit("/", 1)[0]
    ensure_xform_path(stage, parent_path, UsdGeom)

    material = UsdShade.Material.Define(stage, material_path)
    shader = UsdShade.Shader.Define(stage, f"{material_path}/NormalMdlShader")
    shader.CreateImplementationSourceAttr(UsdShade.Tokens.sourceAsset)
    shader.SetSourceAsset(Sdf.AssetPath(str(shader_path)), "mdl")
    shader.SetSourceAssetSubIdentifier("normal_view", "mdl")
    shader.CreateInput("normal_scale", Sdf.ValueTypeNames.Float).Set(0.5)
    shader.CreateInput("normal_bias", Sdf.ValueTypeNames.Float).Set(0.5)
    shader.CreateOutput("out", Sdf.ValueTypeNames.Token)
    material.CreateSurfaceOutput("mdl").ConnectToSource(
        shader.ConnectableAPI(),
        "out",
    )
    return material


def _snapshot_material_bindings(prim) -> MaterialBindingSnapshot:
    relationships: dict[str, tuple[str, ...]] = {}
    for relationship in prim.GetRelationships():
        name = relationship.GetName()
        if name.startswith("material:binding"):
            relationships[name] = tuple(
                str(target) for target in relationship.GetTargets()
            )
    return MaterialBindingSnapshot(
        prim_path=str(prim.GetPath()),
        relationships=relationships,
    )


def _is_excluded(path: str, excluded_roots: tuple[str, ...]) -> bool:
    for root in excluded_roots:
        root = root.rstrip("/")
        if path == root or path.startswith(f"{root}/"):
            return True
    return False
