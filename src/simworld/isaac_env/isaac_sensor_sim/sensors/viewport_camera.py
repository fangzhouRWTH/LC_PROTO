from __future__ import annotations

from dataclasses import dataclass, field

from ..base import PseudoSensor
from ..camera_utils import (
    ensure_xform_path,
    get_active_viewport,
    set_active_viewport_camera,
)
from ..frame import SensorFrame
from ..mount import SensorMountSpec
from ..pose_provider import get_world_pose


@dataclass
class MountedViewportCameraSensor(PseudoSensor):
    sensor_id: str
    mount: SensorMountSpec
    child_name: str = "sensor_camera"
    resolution: tuple[int, int] = (960, 600)
    focal_length: float = 16.0
    horizontal_aperture: float = 20.0
    vertical_aperture: float = 12.5
    clipping_range: tuple[float, float] = (0.05, 1000.0)
    activate_viewport_on_start: bool = True
    sensor_type: str = "mounted_viewport_camera"
    _initialized: bool = field(default=False, init=False)
    _is_active: bool = field(default=False, init=False)
    _previous_viewport_camera: str | None = field(default=None, init=False)

    @property
    def frame_id(self) -> str:
        return self.mount.frame_id

    @property
    def camera_prim_path(self) -> str:
        return self.mount.child_path(self.child_name)

    def initialize(self) -> None:
        from ...isaac_adaptor import isaac_context as iscctx

        context = iscctx.get_isaac_context()
        stage = context.omni_usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("Cannot initialize sensor camera without an open USD stage.")

        parent_prim = stage.GetPrimAtPath(self.mount.parent_prim_path)
        if not parent_prim.IsValid():
            raise RuntimeError(
                f"Invalid sensor mount parent prim: {self.mount.parent_prim_path}"
            )

        UsdGeom = context.pxr_usd_geom
        Gf = context.pxr_gf

        ensure_xform_path(stage, self.mount.parent_prim_path, UsdGeom)
        camera = UsdGeom.Camera.Define(stage, self.camera_prim_path)
        camera.CreateFocalLengthAttr().Set(float(self.focal_length))
        camera.CreateHorizontalApertureAttr().Set(float(self.horizontal_aperture))
        camera.CreateVerticalApertureAttr().Set(float(self.vertical_aperture))
        camera.CreateClippingRangeAttr().Set(
            Gf.Vec2f(float(self.clipping_range[0]), float(self.clipping_range[1]))
        )

        xformable = UsdGeom.Xformable(camera.GetPrim())
        xformable.ClearXformOpOrder()
        xformable.AddTranslateOp().Set(Gf.Vec3d(*self.mount.translation))
        xformable.AddRotateXYZOp().Set(Gf.Vec3f(*self.mount.rotation_rpy_deg))

        self._initialized = True
        if self.activate_viewport_on_start:
            self.activate()

    def activate(self) -> None:
        viewport = get_active_viewport()
        if viewport is not None and self._previous_viewport_camera is None:
            self._previous_viewport_camera = getattr(viewport, "camera_path", None)

        if set_active_viewport_camera(self.camera_prim_path):
            self._is_active = True
            print(f"[INFO] Activated viewport sensor camera: {self.camera_prim_path}")
        else:
            print(
                "[WARNING] Could not activate viewport sensor camera. "
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

        return SensorFrame(
            sensor_id=self.sensor_id,
            sensor_type=self.sensor_type,
            timestamp=float(timestamp),
            frame_id=self.frame_id,
            parent_frame_id=self.mount.parent_prim_path,
            world_pose=get_world_pose(self.camera_prim_path),
            data={
                "camera_prim_path": self.camera_prim_path,
                "resolution": self.resolution,
                "dt": float(dt),
            },
            meta={
                "visual_output": "active_viewport" if self._is_active else "usd_camera",
                "requires_renderer_control": False,
                "requires_external_labels": False,
            },
        )
