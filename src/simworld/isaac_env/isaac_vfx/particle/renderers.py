from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from ...assets import DEFAULT_FOG_BILLBOARD_SHADER, DEFAULT_FOG_BILLBOARD_TEXTURE
from ...isaac_adaptor import isaac_context as iscctx
from .config import ParticleAppearance
from .math_utils import normalize


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
    Gf = iscctx.get_isaac_context().pxr_gf
    return [
        Gf.Vec3f(
            float(appearance.color[0]),
            float(appearance.color[1]),
            float(appearance.color[2]),
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

        points = UsdGeom.Points.Define(stage, prim_path)
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

        curves = UsdGeom.BasisCurves.Define(stage, prim_path)
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
            camera_basis,
        )

        mesh = UsdGeom.Mesh.Define(stage, prim_path)
        mesh.GetPrim().SetActive(True)
        mesh.CreatePointsAttr().Set(_gf_vec3f_list(quad_points))
        mesh.CreateFaceVertexCountsAttr().Set([4] * len(positions_world))
        mesh.CreateFaceVertexIndicesAttr().Set(face_indices)
        mesh.CreateDoubleSidedAttr().Set(True)
        mesh.CreateDisplayColorAttr().Set(_display_color(appearance))

        display_opacity = mesh.CreateDisplayOpacityAttr()
        display_opacity.Set(
            self._quad_opacities(appearance, len(positions_world), opacities)
        )
        if opacities is not None:
            UsdGeom.Primvar(display_opacity).SetInterpolation(
                UsdGeom.Tokens.faceVarying
            )

        st = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar(
            "st",
            Sdf.ValueTypeNames.TexCoord2fArray,
            UsdGeom.Tokens.faceVarying,
        )
        st.Set(_gf_vec2f_list(quad_uvs))

        material_path = f"{prim_path.rsplit('/', 1)[0]}/BillboardMaterial"
        material = self._ensure_material(stage, material_path, appearance)
        self._bind_material(mesh.GetPrim(), material)
        return mesh.GetPrim()

    def _quad_mesh_data(
        self,
        positions_world: np.ndarray,
        appearance: ParticleAppearance,
        widths: np.ndarray | None,
        camera_basis: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, list[int]]:
        sizes = np.asarray(
            _particle_widths(appearance, len(positions_world), widths),
            dtype=np.float32,
        )
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

    def _quad_opacities(
        self,
        appearance: ParticleAppearance,
        particle_count: int,
        opacities: np.ndarray | None,
    ):
        values = _particle_opacities(appearance, particle_count, opacities)
        if opacities is None:
            return values
        return [float(v) for v in np.repeat(np.asarray(values, dtype=np.float32), 4)]

    def _ensure_material(
        self,
        stage,
        material_path: str,
        appearance: ParticleAppearance,
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
            Gf.Vec4f(1.0, 1.0, 1.0, float(appearance.opacity))
        )
        texture.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
        texture.CreateOutput("a", Sdf.ValueTypeNames.Float)

        preview = UsdShade.Shader.Define(stage, f"{material_path}/PreviewSurface")
        preview.CreateIdAttr("UsdPreviewSurface")
        preview.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
            Gf.Vec3f(
                float(appearance.color[0]),
                float(appearance.color[1]),
                float(appearance.color[2]),
            )
        )
        preview.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(1.0)
        preview.CreateInput("opacity", Sdf.ValueTypeNames.Float).ConnectToSource(
            texture.ConnectableAPI(),
            "a",
        )
        preview.CreateInput("opacityThreshold", Sdf.ValueTypeNames.Float).Set(0.0)
        preview.CreateOutput("surface", Sdf.ValueTypeNames.Token)
        material.CreateSurfaceOutput().ConnectToSource(
            preview.ConnectableAPI(),
            "surface",
        )

        self._try_add_mdl_output(
            material,
            material_path,
            appearance,
            texture_path,
            shader_path,
        )
        return material

    def _try_add_mdl_output(
        self,
        material,
        material_path: str,
        appearance: ParticleAppearance,
        texture_path: str,
        shader_path: str,
    ) -> None:
        try:
            from pxr import UsdShade

            context = iscctx.get_isaac_context()
            Gf = context.pxr_gf
            Sdf = context.pxr_Sdf
            shader = UsdShade.Shader.Define(
                material.GetPrim().GetStage(),
                f"{material_path}/MdlShader",
            )
            shader.CreateImplementationSourceAttr(UsdShade.Tokens.sourceAsset)
            shader.SetSourceAsset(Sdf.AssetPath(shader_path), "mdl")
            shader.SetSourceAssetSubIdentifier("fog_billboard", "mdl")
            shader.CreateInput("texture_path", Sdf.ValueTypeNames.Asset).Set(
                Sdf.AssetPath(texture_path)
            )
            shader.CreateInput("tint", Sdf.ValueTypeNames.Color3f).Set(
                Gf.Vec3f(
                    float(appearance.color[0]),
                    float(appearance.color[1]),
                    float(appearance.color[2]),
                )
            )
            shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(
                float(appearance.opacity)
            )
            shader.CreateOutput("out", Sdf.ValueTypeNames.Token)
            material.CreateSurfaceOutput("mdl").ConnectToSource(
                shader.ConnectableAPI(),
                "out",
            )
        except Exception:
            return

    def _bind_material(self, prim, material) -> None:
        from pxr import UsdShade

        UsdShade.MaterialBindingAPI(prim).Bind(material)
