from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..base import PseudoSensor
from ..camera_utils import (
    ensure_xform_path,
    get_active_viewport,
    set_active_viewport_camera,
    set_camera_look_at,
)
from ..frame import SensorFrame
from ..pose_provider import get_world_pose


def _parent_prim_path(prim_path: str) -> str:
    parts = prim_path.strip("/").split("/")[:-1]
    return "/" + "/".join(parts) if parts else "/"


def _normalize_vec3(value, fallback):
    length = value.GetLength()
    if length > 1e-8:
        return value / length
    return fallback


@dataclass
class ChaseViewportCameraSensor(PseudoSensor):
    sensor_id: str
    target_prim_path: str
    camera_prim_path: str
    frame_id: str = "world/chase_camera"
    distance: float = 5.0
    height: float = 2.5
    target_height: float = 0.8
    smoothing: float = 0.15
    resolution: tuple[int, int] = (1280, 720)
    focal_length: float = 18.0
    horizontal_aperture: float = 20.0
    vertical_aperture: float = 12.5
    clipping_range: tuple[float, float] = (0.05, 1000.0)
    activate_viewport_on_start: bool = True
    sensor_type: str = "chase_viewport_camera"
    _initialized: bool = field(default=False, init=False)
    _is_active: bool = field(default=False, init=False)
    _previous_viewport_camera: str | None = field(default=None, init=False)
    _eye: np.ndarray | None = field(default=None, init=False)
    _target: np.ndarray | None = field(default=None, init=False)

    def initialize(self) -> None:
        from ...isaac_adaptor import isaac_context as iscctx

        context = iscctx.get_isaac_context()
        stage = context.omni_usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("Cannot initialize chase camera without an open USD stage.")

        target_prim = stage.GetPrimAtPath(self.target_prim_path)
        if not target_prim.IsValid():
            raise RuntimeError(f"Invalid chase camera target prim: {self.target_prim_path}")

        UsdGeom = context.pxr_usd_geom
        Gf = context.pxr_gf

        ensure_xform_path(stage, _parent_prim_path(self.camera_prim_path), UsdGeom)
        camera = UsdGeom.Camera.Define(stage, self.camera_prim_path)
        camera.CreateFocalLengthAttr().Set(float(self.focal_length))
        camera.CreateHorizontalApertureAttr().Set(float(self.horizontal_aperture))
        camera.CreateVerticalApertureAttr().Set(float(self.vertical_aperture))
        camera.CreateClippingRangeAttr().Set(
            Gf.Vec2f(float(self.clipping_range[0]), float(self.clipping_range[1]))
        )

        self._initialized = True
        self.update(timestamp=0.0, dt=0.0)
        if self.activate_viewport_on_start:
            self.activate()

    def activate(self) -> None:
        viewport = get_active_viewport()
        if viewport is not None and self._previous_viewport_camera is None:
            self._previous_viewport_camera = getattr(viewport, "camera_path", None)

        if set_active_viewport_camera(self.camera_prim_path):
            self._is_active = True
            print(f"[INFO] Activated chase sensor camera: {self.camera_prim_path}")
        else:
            print(
                "[WARNING] Could not activate chase sensor camera. "
                "The camera prim was still created."
            )

    def deactivate(self) -> None:
        if not self._is_active:
            return
        if self._previous_viewport_camera:
            set_active_viewport_camera(self._previous_viewport_camera)
        self._is_active = False

    def update(self, timestamp: float, dt: float) -> SensorFrame | None:
        if not self._initialized:
            return None

        eye, target = self._compute_camera_pose()
        pose_applied = set_camera_look_at(
            eye=eye,
            target=target,
            camera_prim_path=self.camera_prim_path,
        )

        return SensorFrame(
            sensor_id=self.sensor_id,
            sensor_type=self.sensor_type,
            timestamp=float(timestamp),
            frame_id=self.frame_id,
            parent_frame_id=self.target_prim_path,
            world_pose=get_world_pose(self.camera_prim_path),
            data={
                "camera_prim_path": self.camera_prim_path,
                "target_prim_path": self.target_prim_path,
                "eye": tuple(float(v) for v in eye),
                "target": tuple(float(v) for v in target),
                "resolution": self.resolution,
                "dt": float(dt),
                "camera_pose_applied": pose_applied,
            },
            meta={
                "visual_output": "active_viewport" if self._is_active else "usd_camera",
                "requires_renderer_control": False,
                "requires_external_labels": False,
                "visualization_mode": "viewport_camera",
            },
        )

    def _compute_camera_pose(self) -> tuple[np.ndarray, np.ndarray]:
        from ...isaac_adaptor import isaac_context as iscctx

        context = iscctx.get_isaac_context()
        stage = context.omni_usd.get_context().get_stage()
        prim = stage.GetPrimAtPath(self.target_prim_path)
        if not prim.IsValid():
            raise RuntimeError(f"Invalid chase camera target prim: {self.target_prim_path}")

        Gf = context.pxr_gf
        world_mat = context.omni_usd.get_world_transform_matrix(prim)
        pos = world_mat.ExtractTranslation()
        rot = world_mat.ExtractRotation()
        forward = _normalize_vec3(
            rot.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)),
            Gf.Vec3d(1.0, 0.0, 0.0),
        )

        target = np.array(
            [
                float(pos[0]),
                float(pos[1]),
                float(pos[2]) + float(self.target_height),
            ],
            dtype=np.double,
        )
        eye = np.array(
            [
                target[0] - float(forward[0]) * float(self.distance),
                target[1] - float(forward[1]) * float(self.distance),
                float(pos[2]) + float(self.height),
            ],
            dtype=np.double,
        )

        if self._eye is None or self._target is None or self.smoothing <= 0.0:
            self._eye = eye
            self._target = target
        else:
            alpha = max(0.0, min(1.0, float(self.smoothing)))
            self._eye = (1.0 - alpha) * self._eye + alpha * eye
            self._target = (1.0 - alpha) * self._target + alpha * target

        return self._eye.copy(), self._target.copy()
