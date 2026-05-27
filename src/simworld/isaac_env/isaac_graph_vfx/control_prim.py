from __future__ import annotations

from typing import Any

from ..isaac_adaptor import isaac_context as iscctx
from .config import GraphParticleVFXConfig, GraphVFXRuntimeState


def _stage(stage=None):
    if stage is not None:
        return stage
    stage = iscctx.get_isaac_context().omni_usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("Cannot create graph VFX prims without an open USD stage.")
    return stage


def _ensure_xform(stage, path: str):
    context = iscctx.get_isaac_context()
    Sdf = context.pxr_Sdf
    UsdGeom = context.pxr_usd_geom

    if not Sdf.Path.IsValidPathString(path):
        raise ValueError(f"Invalid USD prim path: {path}")
    return UsdGeom.Xform.Define(stage, path).GetPrim()


def _set_attr(prim, name: str, type_name, value: Any) -> None:
    attr = prim.GetAttribute(name)
    if not attr or not attr.IsValid():
        attr = prim.CreateAttribute(name, type_name, custom=True)
    attr.Set(value)


class GraphVFXControlPrim:
    """USD control prim used as the stable bridge between Python and a graph."""

    def __init__(self, config: GraphParticleVFXConfig):
        config.validate()
        self.config = config

    def ensure(self, stage=None):
        stage = _stage(stage)
        for path in (
            self.config.root_path,
            self.config.graph_root_path,
            self.config.output_root_path,
            self.config.control_prim_path,
        ):
            _ensure_xform(stage, path).SetActive(True)

        prim = stage.GetPrimAtPath(self.config.control_prim_path)
        self.write_static_attributes(prim)
        return prim

    def write_static_attributes(self, prim) -> None:
        Sdf = iscctx.get_isaac_context().pxr_Sdf
        volume = self.config.volume
        appearance = self.config.appearance

        _set_attr(prim, "vfx:name", Sdf.ValueTypeNames.String, self.config.name)
        _set_attr(prim, "vfx:backend", Sdf.ValueTypeNames.Token, self.config.backend)
        _set_attr(
            prim,
            "vfx:cameraPrimPath",
            Sdf.ValueTypeNames.String,
            self.config.camera_prim_path,
        )
        _set_attr(
            prim,
            "vfx:particleCount",
            Sdf.ValueTypeNames.Int,
            int(self.config.particle_count),
        )
        _set_attr(prim, "vfx:active", Sdf.ValueTypeNames.Bool, self.config.active)
        _set_attr(prim, "vfx:volumeWidth", Sdf.ValueTypeNames.Float, volume.width)
        _set_attr(prim, "vfx:volumeHeight", Sdf.ValueTypeNames.Float, volume.height)
        _set_attr(prim, "vfx:volumeDepth", Sdf.ValueTypeNames.Float, volume.depth)
        _set_attr(
            prim,
            "vfx:volumeNearDistance",
            Sdf.ValueTypeNames.Float,
            volume.near_distance,
        )
        _set_attr(prim, "vfx:speed", Sdf.ValueTypeNames.Float, self.config.speed)
        _set_attr(
            prim,
            "vfx:speedJitter",
            Sdf.ValueTypeNames.Float,
            self.config.speed_jitter,
        )
        _set_attr(
            prim,
            "vfx:turbulence",
            Sdf.ValueTypeNames.Float,
            self.config.turbulence,
        )
        _set_attr(prim, "vfx:seed", Sdf.ValueTypeNames.UInt, self.config.seed)
        _set_attr(
            prim,
            "vfx:directionWorld",
            Sdf.ValueTypeNames.Float3,
            self.config.direction_world,
        )
        _set_attr(
            prim,
            "vfx:windWorld",
            Sdf.ValueTypeNames.Float3,
            self.config.wind_world,
        )
        _set_attr(
            prim,
            "vfx:color",
            Sdf.ValueTypeNames.Color3f,
            appearance.color,
        )
        _set_attr(prim, "vfx:opacity", Sdf.ValueTypeNames.Float, appearance.opacity)
        _set_attr(
            prim,
            "vfx:pointWidth",
            Sdf.ValueTypeNames.Float,
            appearance.point_width,
        )
        _set_attr(
            prim,
            "vfx:streakLength",
            Sdf.ValueTypeNames.Float,
            appearance.streak_length,
        )
        _set_attr(
            prim,
            "vfx:streakWidth",
            Sdf.ValueTypeNames.Float,
            appearance.streak_width,
        )

    def write_runtime_state(self, runtime_state: GraphVFXRuntimeState, stage=None):
        prim = _stage(stage).GetPrimAtPath(self.config.control_prim_path)
        if not prim.IsValid():
            prim = self.ensure(stage=stage)

        Sdf = iscctx.get_isaac_context().pxr_Sdf
        _set_attr(prim, "vfx:dt", Sdf.ValueTypeNames.Float, runtime_state.dt)
        _set_attr(
            prim,
            "vfx:cameraPosition",
            Sdf.ValueTypeNames.Float3,
            runtime_state.camera_position,
        )
        _set_attr(
            prim,
            "vfx:cameraForward",
            Sdf.ValueTypeNames.Float3,
            runtime_state.camera_forward,
        )
        _set_attr(
            prim,
            "vfx:cameraUp",
            Sdf.ValueTypeNames.Float3,
            runtime_state.camera_up,
        )
        return prim

