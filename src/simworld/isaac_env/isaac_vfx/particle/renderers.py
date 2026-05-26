from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

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
    ):
        raise NotImplementedError


def create_renderer(kind: str) -> ParticleRenderer:
    if kind == "points":
        return PointsParticleRenderer()
    if kind == "streaks":
        return StreakParticleRenderer()
    raise ValueError(f"Unsupported particle renderer: {kind}")


def _gf_vec3f_list(values: np.ndarray):
    Gf = iscctx.get_isaac_context().pxr_gf
    return [Gf.Vec3f(float(v[0]), float(v[1]), float(v[2])) for v in values]


def _display_color(appearance: ParticleAppearance):
    Gf = iscctx.get_isaac_context().pxr_gf
    return [
        Gf.Vec3f(
            float(appearance.color[0]),
            float(appearance.color[1]),
            float(appearance.color[2]),
        )
    ]


class PointsParticleRenderer(ParticleRenderer):
    """Render particles as USD points."""

    def render(
        self,
        stage,
        prim_path: str,
        positions_world: np.ndarray,
        appearance: ParticleAppearance,
        velocity_hint_world: np.ndarray,
    ):
        del velocity_hint_world
        UsdGeom = iscctx.get_isaac_context().pxr_usd_geom

        points = UsdGeom.Points.Define(stage, prim_path)
        points.GetPrim().SetActive(True)
        points.CreatePointsAttr().Set(_gf_vec3f_list(positions_world))
        points.CreateWidthsAttr().Set([float(appearance.point_width)] * len(positions_world))
        points.CreateDisplayColorAttr().Set(_display_color(appearance))
        points.CreateDisplayOpacityAttr().Set([float(appearance.opacity)])
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
    ):
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
        curves.CreateWidthsAttr().Set([float(appearance.streak_width)] * len(curve_points))
        curves.CreateDisplayColorAttr().Set(_display_color(appearance))
        curves.CreateDisplayOpacityAttr().Set([float(appearance.opacity)])
        return curves.GetPrim()

