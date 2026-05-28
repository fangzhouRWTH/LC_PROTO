from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from ...assets import DEFAULT_FOG_BILLBOARD_SHADER, DEFAULT_FOG_BILLBOARD_TEXTURE
from ...isaac_adaptor import isaac_context as iscctx
from .config import ParticleAppearance
from .math_utils import normalize


_BILLBOARD_MATERIAL_VERSION = 8


class ParticleRenderer(ABC):
    """USD-backed renderer for visual particle geometry."""

    @abstractmethod
    def render(
        self,
        stage,
        prim_path: str,
        positions_world: np.ndarray,
        appearance: ParticleAppearance,
        velocity_hint_world: np.ndarray,
        widths: np.ndarray | None = None,
        opacities: np.ndarray | None = None,
        camera_basis: np.ndarray | None = None,
    ):
        raise NotImplementedError


def create_renderer(kind: str) -> ParticleRenderer:
    if kind == "points":
        return PointsParticleRenderer()
    if kind == "streaks":
        return StreakParticleRenderer()
    if kind == "billboard":
        return BillboardParticleRenderer()
    raise ValueError(f"Unsupported particle renderer: {kind}")


def _gf_vec3f_list(values: np.ndarray):
    Gf = iscctx.get_isaac_context().pxr_gf
    return [Gf.Vec3f(float(v[0]), float(v[1]), float(v[2])) for v in values]


def _gf_vec2f_list(values: np.ndarray):
    Gf = iscctx.get_isaac_context().pxr_gf
    return [Gf.Vec2f(float(v[0]), float(v[1])) for v in values]


def _display_color(appearance: ParticleAppearance):
    return _display_color_from(appearance.color)


def _display_color_from(color):
    Gf = iscctx.get_isaac_context().pxr_gf
    return [
        Gf.Vec3f(
            float(color[0]),
            float(color[1]),
            float(color[2]),
        )
    ]


def _particle_widths(
    appearance: ParticleAppearance,
    particle_count: int,
    widths: np.ndarray | None,
):
    if widths is None:
        return [float(appearance.point_width)] * particle_count

    values = np.asarray(widths, dtype=np.float32).reshape(-1)
    if len(values) != particle_count:
        raise ValueError(
            f"Particle width count {len(values)} does not match {particle_count}."
        )
    values = np.maximum(values, 1e-6)
    return [float(v) for v in values]


def _particle_opacities(
    appearance: ParticleAppearance,
    particle_count: int,
    opacities: np.ndarray | None,
):
    if opacities is None:
        return [float(appearance.opacity)]

    values = np.asarray(opacities, dtype=np.float32).reshape(-1)
    if len(values) != particle_count:
        raise ValueError(
            f"Particle opacity count {len(values)} does not match {particle_count}."
        )
    values = np.clip(values, 0.0, 1.0)
    return [float(v) for v in values]


def _resolve_asset_path(path: str | None, default_path: Path) -> str:
    if path is None:
        return str(default_path)
    expanded = Path(path).expanduser()
    if not expanded.is_absolute():
        expanded = Path.cwd() / expanded
    return str(expanded)


def _define_geometry(stage, prim_path: str, schema, type_name: str):
    prim = stage.GetPrimAtPath(prim_path)
    reset = not prim or not prim.IsValid()
    if prim and prim.IsValid() and prim.GetTypeName() != type_name:
        stage.RemovePrim(prim_path)
        reset = True
    return schema.Define(stage, prim_path), reset


class PointsParticleRenderer(ParticleRenderer):
    """Render particles as USD points."""

    def render(
        self,
        stage,
        prim_path: str,
        positions_world: np.ndarray,
        appearance: ParticleAppearance,
        velocity_hint_world: np.ndarray,
        widths: np.ndarray | None = None,
        opacities: np.ndarray | None = None,
        camera_basis: np.ndarray | None = None,
    ):
        del velocity_hint_world, camera_basis
        UsdGeom = iscctx.get_isaac_context().pxr_usd_geom

        points, _ = _define_geometry(stage, prim_path, UsdGeom.Points, "Points")
        points.GetPrim().SetActive(True)
        points.CreatePointsAttr().Set(_gf_vec3f_list(positions_world))
        points.CreateWidthsAttr().Set(
            _particle_widths(appearance, len(positions_world), widths)
        )
        points.CreateDisplayColorAttr().Set(_display_color(appearance))
        points.CreateDisplayOpacityAttr().Set(
            _particle_opacities(appearance, len(positions_world), opacities)
        )
        return points.GetPrim()


class StreakParticleRenderer(ParticleRenderer):
    """Render fast particles as short USD line curves."""

    def render(
        self,
        stage,
        prim_path: str,
        positions_world: np.ndarray,
        appearance: ParticleAppearance,
        velocity_hint_world: np.ndarray,
        widths: np.ndarray | None = None,
        opacities: np.ndarray | None = None,
        camera_basis: np.ndarray | None = None,
    ):
        del camera_basis
        UsdGeom = iscctx.get_isaac_context().pxr_usd_geom

        direction = normalize(
            velocity_hint_world,
            "velocity_hint_world",
            fallback=(0.0, 0.0, -1.0),
        )
        tails = positions_world - direction[None, :] * float(appearance.streak_length)
        curve_points = np.empty((len(positions_world) * 2, 3), dtype=np.float32)
        curve_points[0::2] = positions_world
        curve_points[1::2] = tails

        curves, _ = _define_geometry(
            stage,
            prim_path,
            UsdGeom.BasisCurves,
            "BasisCurves",
        )
        curves.GetPrim().SetActive(True)
        curves.CreateTypeAttr("linear")
        curves.CreateWrapAttr("nonperiodic")
        curves.CreateCurveVertexCountsAttr().Set([2] * len(positions_world))
        curves.CreatePointsAttr().Set(_gf_vec3f_list(curve_points))
        if widths is None:
            curve_widths = [float(appearance.streak_width)] * len(curve_points)
        else:
            curve_widths = np.repeat(
                _particle_widths(appearance, len(positions_world), widths),
                2,
            )
            curve_widths = [float(v) for v in np.maximum(curve_widths, 1e-6)]
        curves.CreateWidthsAttr().Set(curve_widths)
        curves.CreateDisplayColorAttr().Set(_display_color(appearance))
        if opacities is None:
            curve_opacities = None
        else:
            curve_opacities = np.repeat(
                np.asarray(opacities, dtype=np.float32).reshape(-1),
                2,
            )
        curves.CreateDisplayOpacityAttr().Set(
            _particle_opacities(appearance, len(curve_points), curve_opacities)
        )
        return curves.GetPrim()


class BillboardParticleRenderer(ParticleRenderer):
    """Render soft particles as camera-facing textured quads."""

    def __init__(self):
        self._topology_counts: dict[str, int] = {}

    def render(
        self,
        stage,
        prim_path: str,
        positions_world: np.ndarray,
        appearance: ParticleAppearance,
        velocity_hint_world: np.ndarray,
        widths: np.ndarray | None = None,
        opacities: np.ndarray | None = None,
        camera_basis: np.ndarray | None = None,
    ):
        del velocity_hint_world
        if camera_basis is None:
            raise ValueError("BillboardParticleRenderer requires camera_basis.")

        context = iscctx.get_isaac_context()
        UsdGeom = context.pxr_usd_geom
        Sdf = context.pxr_Sdf

        quad_points, quad_uvs, face_indices = self._quad_mesh_data(
            positions_world,
            appearance,
            widths,
            None if appearance.billboard_debug else opacities,
            camera_basis,
        )

        mesh, geometry_reset = _define_geometry(stage, prim_path, UsdGeom.Mesh, "Mesh")
        particle_count = len(positions_world)
        mesh.GetPrim().SetActive(True)
        self._disable_shadow_participation(mesh.GetPrim(), Sdf)
        mesh.CreatePointsAttr().Set(_gf_vec3f_list(quad_points))

        topology_key = f"{id(stage)}:{prim_path}"
        topology_count = self._topology_counts.get(topology_key)
        if geometry_reset or topology_count != particle_count:
            mesh.CreateFaceVertexCountsAttr().Set([4] * particle_count)
            mesh.CreateFaceVertexIndicesAttr().Set(face_indices)
            mesh.CreateDoubleSidedAttr().Set(True)
            st = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar(
                "st",
                Sdf.ValueTypeNames.TexCoord2fArray,
                UsdGeom.Tokens.faceVarying,
            )
            st.Set(_gf_vec2f_list(quad_uvs))
            self._topology_counts[topology_key] = particle_count

        display_opacity = mesh.CreateDisplayOpacityAttr()
        if appearance.billboard_debug:
            self._unbind_material(mesh.GetPrim())
            mesh.CreateDisplayColorAttr().Set(
                _display_color_from(appearance.billboard_debug_color)
            )
            display_opacity.Set([float(appearance.billboard_debug_opacity)])
            UsdGeom.Primvar(display_opacity).SetInterpolation(UsdGeom.Tokens.constant)
        else:
            mesh.CreateDisplayColorAttr().Set(_display_color(appearance))
            display_opacity.Set([1.0])
            UsdGeom.Primvar(display_opacity).SetInterpolation(
                UsdGeom.Tokens.constant
            )
            material_path = f"{prim_path.rsplit('/', 1)[0]}/BillboardMaterial"
            material_opacity = self._material_opacity(appearance, opacities)
            material = self._ensure_material(
                stage,
                material_path,
                appearance,
                material_opacity,
            )
            self._bind_material_if_needed(mesh.GetPrim(), material)
        return mesh.GetPrim()

    def _quad_mesh_data(
        self,
        positions_world: np.ndarray,
        appearance: ParticleAppearance,
        widths: np.ndarray | None,
        opacities: np.ndarray | None,
        camera_basis: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, list[int]]:
        sizes = np.asarray(
            _particle_widths(appearance, len(positions_world), widths),
            dtype=np.float32,
        )
        sizes *= self._quad_size_fade(appearance, len(positions_world), opacities)
        basis = np.asarray(camera_basis, dtype=np.float32)
        right = basis[0]
        up = basis[1]
        half_sizes = sizes[:, None] * 0.5
        right_offsets = right[None, :] * half_sizes
        up_offsets = up[None, :] * half_sizes

        quad_points = np.empty((len(positions_world) * 4, 3), dtype=np.float32)
        quad_points[0::4] = positions_world - right_offsets - up_offsets
        quad_points[1::4] = positions_world + right_offsets - up_offsets
        quad_points[2::4] = positions_world + right_offsets + up_offsets
        quad_points[3::4] = positions_world - right_offsets + up_offsets

        quad_uv = np.array(
            (
                (0.0, 0.0),
                (1.0, 0.0),
                (1.0, 1.0),
                (0.0, 1.0),
            ),
            dtype=np.float32,
        )
        quad_uvs = np.tile(quad_uv, (len(positions_world), 1))
        face_indices = list(range(len(positions_world) * 4))
        return quad_points, quad_uvs, face_indices

    def _quad_size_fade(
        self,
        appearance: ParticleAppearance,
        particle_count: int,
        opacities: np.ndarray | None,
    ) -> np.ndarray:
        if opacities is None:
            return np.ones(particle_count, dtype=np.float32)

        values = np.asarray(
            _particle_opacities(appearance, particle_count, opacities),
            dtype=np.float32,
        )
        base_opacity = max(float(appearance.opacity), 1e-6)
        return np.sqrt(np.clip(values / base_opacity, 0.0, 1.0)).astype(np.float32)

    def _ensure_material(
        self,
        stage,
        material_path: str,
        appearance: ParticleAppearance,
        material_opacity: float,
    ):
        from pxr import UsdShade

        context = iscctx.get_isaac_context()
        Gf = context.pxr_gf
        Sdf = context.pxr_Sdf
        texture_path = _resolve_asset_path(
            appearance.billboard_texture_path,
            DEFAULT_FOG_BILLBOARD_TEXTURE,
        )
        shader_path = _resolve_asset_path(
            appearance.billboard_shader_path,
            DEFAULT_FOG_BILLBOARD_SHADER,
        )

        material_prim = stage.GetPrimAtPath(material_path)
        if self._material_ready(material_prim, appearance, material_opacity):
            return UsdShade.Material(material_prim)
        if material_prim and material_prim.IsValid():
            stage.RemovePrim(material_path)

        material = UsdShade.Material.Define(stage, material_path)
        material_prim = material.GetPrim()
        material_prim.CreateAttribute(
            "simworld:billboardTexture",
            Sdf.ValueTypeNames.Asset,
        ).Set(Sdf.AssetPath(texture_path))
        material_prim.CreateAttribute(
            "simworld:billboardShader",
            Sdf.ValueTypeNames.Asset,
        ).Set(Sdf.AssetPath(shader_path))
        material_prim.CreateAttribute(
            "simworld:billboardUseMdlShader",
            Sdf.ValueTypeNames.Bool,
        ).Set(bool(appearance.billboard_use_mdl_shader))
        material_prim.CreateAttribute(
            "simworld:billboardOpacity",
            Sdf.ValueTypeNames.Float,
        ).Set(float(material_opacity))
        material_prim.CreateAttribute(
            "simworld:billboardOpacityGain",
            Sdf.ValueTypeNames.Float,
        ).Set(float(appearance.billboard_opacity_gain))

        st_reader = UsdShade.Shader.Define(stage, f"{material_path}/PrimvarReader_st")
        st_reader.CreateIdAttr("UsdPrimvarReader_float2")
        st_reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
        st_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)

        texture = UsdShade.Shader.Define(stage, f"{material_path}/Texture")
        texture.CreateIdAttr("UsdUVTexture")
        texture.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
            Sdf.AssetPath(texture_path)
        )
        texture.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")
        texture.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
            st_reader.ConnectableAPI(),
            "result",
        )
        texture.CreateInput("scale", Sdf.ValueTypeNames.Float4).Set(
            Gf.Vec4f(1.0, 1.0, 1.0, float(material_opacity))
        )
        texture.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
        texture.CreateOutput("a", Sdf.ValueTypeNames.Float)

        preview = UsdShade.Shader.Define(stage, f"{material_path}/PreviewSurface")
        preview.CreateIdAttr("UsdPreviewSurface")
        preview.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
            Gf.Vec3f(0.0, 0.0, 0.0)
        )
        preview.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(
            Gf.Vec3f(
                float(appearance.color[0]),
                float(appearance.color[1]),
                float(appearance.color[2]),
            )
        )
        preview.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(1.0)
        preview.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
        preview.CreateInput("clearcoat", Sdf.ValueTypeNames.Float).Set(0.0)
        preview.CreateInput("ior", Sdf.ValueTypeNames.Float).Set(1.0)
        preview.CreateInput("useSpecularWorkflow", Sdf.ValueTypeNames.Int).Set(1)
        preview.CreateInput("specularColor", Sdf.ValueTypeNames.Color3f).Set(
            Gf.Vec3f(0.0, 0.0, 0.0)
        )
        preview.CreateInput("opacity", Sdf.ValueTypeNames.Float).ConnectToSource(
            texture.ConnectableAPI(),
            "a",
        )
        preview.CreateOutput("surface", Sdf.ValueTypeNames.Token)
        material.CreateSurfaceOutput().ConnectToSource(
            preview.ConnectableAPI(),
            "surface",
        )

        if appearance.billboard_use_mdl_shader:
            self._try_add_mdl_output(
                material,
                material_path,
                appearance,
                material_opacity,
                shader_path,
            )
        material_prim.CreateAttribute(
            "simworld:materialReady",
            Sdf.ValueTypeNames.Bool,
        ).Set(True)
        material_prim.CreateAttribute(
            "simworld:materialVersion",
            Sdf.ValueTypeNames.Int,
        ).Set(_BILLBOARD_MATERIAL_VERSION)
        return material

    def _material_ready(
        self,
        material_prim,
        appearance: ParticleAppearance,
        material_opacity: float,
    ) -> bool:
        if not material_prim or not material_prim.IsValid():
            return False
        ready = material_prim.GetAttribute("simworld:materialReady")
        if not ready:
            return False
        version = material_prim.GetAttribute("simworld:materialVersion")
        if not version:
            return False
        use_mdl = material_prim.GetAttribute("simworld:billboardUseMdlShader")
        if not use_mdl:
            return False
        opacity = material_prim.GetAttribute("simworld:billboardOpacity")
        if not opacity:
            return False
        opacity_gain = material_prim.GetAttribute("simworld:billboardOpacityGain")
        if not opacity_gain:
            return False
        return (
            bool(ready.Get())
            and version.Get() == _BILLBOARD_MATERIAL_VERSION
            and bool(use_mdl.Get()) == bool(appearance.billboard_use_mdl_shader)
            and abs(float(opacity.Get()) - float(material_opacity)) < 1e-6
            and abs(
                float(opacity_gain.Get()) - float(appearance.billboard_opacity_gain)
            )
            < 1e-6
        )

    def _material_opacity(
        self,
        appearance: ParticleAppearance,
        opacities: np.ndarray | None,
    ) -> float:
        del opacities
        opacity = float(appearance.opacity) * float(appearance.billboard_opacity_gain)
        return float(np.clip(opacity, 0.0, 1.0))

    def _try_add_mdl_output(
        self,
        material,
        material_path: str,
        appearance: ParticleAppearance,
        material_opacity: float,
        shader_path: str,
    ) -> None:
        try:
            from pxr import UsdShade

            context = iscctx.get_isaac_context()
            Sdf = context.pxr_Sdf
            shader = UsdShade.Shader.Define(
                material.GetPrim().GetStage(),
                f"{material_path}/MdlShader",
            )
            shader.CreateImplementationSourceAttr(UsdShade.Tokens.sourceAsset)
            shader.SetSourceAsset(Sdf.AssetPath(shader_path), "mdl")
            shader.SetSourceAssetSubIdentifier("fog_billboard", "mdl")
            shader.CreateInput("tint", Sdf.ValueTypeNames.Color3f).Set(
                self._gf_color(appearance)
            )
            shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(
                float(material_opacity)
            )
            shader.CreateOutput("out", Sdf.ValueTypeNames.Token)
            material.CreateSurfaceOutput("mdl").ConnectToSource(
                shader.ConnectableAPI(),
                "out",
            )
        except Exception:
            return

    def _disable_shadow_participation(self, prim, Sdf) -> None:
        self._set_attr_if_needed(
            prim.CreateAttribute(
                "primvars:doNotCastShadows",
                Sdf.ValueTypeNames.Bool,
            ),
            True,
        )
        self._set_attr_if_needed(
            prim.CreateAttribute(
                "rtx:visibility:shadow",
                Sdf.ValueTypeNames.Bool,
            ),
            False,
        )

    def _set_attr_if_needed(self, attr, value) -> None:
        if attr.Get() != value:
            attr.Set(value)

    def _gf_color(self, appearance: ParticleAppearance):
        Gf = iscctx.get_isaac_context().pxr_gf
        return Gf.Vec3f(
            float(appearance.color[0]),
            float(appearance.color[1]),
            float(appearance.color[2]),
        )

    def _bind_material_if_needed(self, prim, material) -> None:
        from pxr import UsdShade

        material_path = material.GetPrim().GetPath()
        binding = prim.GetRelationship("material:binding")
        if binding and material_path in binding.GetTargets():
            return

        UsdShade.MaterialBindingAPI(prim).Bind(material)

    def _unbind_material(self, prim) -> None:
        try:
            for relationship in prim.GetRelationships():
                name = relationship.GetName()
                if name.startswith("material:binding"):
                    prim.RemoveProperty(name)
        except Exception:
            return
