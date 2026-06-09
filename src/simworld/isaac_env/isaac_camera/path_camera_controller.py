"""Isaac runtime for camera paths authored as scene placeholders."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from engine.camera_path import (
    CameraPathPlan,
    CameraPathScenePlan,
    advance_path_distance,
    position_along_path,
)
from ..isaac_sensor_sim.camera_utils import (
    ensure_xform_path,
    get_active_viewport_camera_prim_path,
    set_active_viewport_camera,
    set_camera_position_preserve_orientation,
    set_camera_position_world,
)

DEFAULT_CAMERA_PATH_ROOT = "/World/GeneratedAssets/CameraPaths"


def _parent_prim_path(prim_path: str) -> str:
    parts = prim_path.strip("/").split("/")[:-1]
    return "/" + "/".join(parts) if parts else "/"


def _set_camera_prim_translate(stage, context, prim_path: str, position) -> bool:
    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        return False

    UsdGeom = context.pxr_usd_geom
    Gf = context.pxr_gf
    xformable = UsdGeom.Xformable(prim)
    translate_op = None
    for op in xformable.GetOrderedXformOps():
        if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
            translate_op = op
            break
    if translate_op is None:
        translate_op = xformable.AddTranslateOp()
    translate_op.Set(
        Gf.Vec3d(float(position[0]), float(position[1]), float(position[2]))
    )
    return True


@dataclass
class PathCameraRuntime:
    plan: CameraPathPlan
    camera_prim_path: str
    elapsed_s: float = 0.0

    def position_at_elapsed(self) -> tuple[float, float, float]:
        distance = advance_path_distance(
            elapsed_s=self.elapsed_s,
            speed_mps=self.plan.speed_mps,
            dt=0.0,
        )
        return position_along_path(
            self.plan.waypoints,
            distance,
            route_mode=self.plan.route_mode,
        )

    def step(
        self,
        dt: float,
        *,
        stage,
        context,
        active: bool,
    ) -> None:
        if dt <= 0.0:
            return
        self.elapsed_s += float(dt)
        position = self.position_at_elapsed()
        if active:
            set_camera_position_preserve_orientation(
                position=position,
                camera_prim_path=self.camera_prim_path,
            )
            return
        _set_camera_prim_translate(stage, context, self.camera_prim_path, position)


@dataclass
class PathCameraController:
    runtimes: list[PathCameraRuntime] = field(default_factory=list)
    active_index: int = 0
    stage = None

    @classmethod
    def from_plan(
        cls,
        plan: CameraPathScenePlan,
        *,
        active_index: int = 0,
        root_prim_path: str = DEFAULT_CAMERA_PATH_ROOT,
    ) -> PathCameraController:
        controller = cls(active_index=max(0, int(active_index)))
        if not plan.paths:
            return controller

        root = root_prim_path.rstrip("/")
        for selected in plan.paths:
            camera_prim_path = f"{root}/{_safe_prim_name(selected.path_id)}"
            controller.runtimes.append(
                PathCameraRuntime(plan=selected, camera_prim_path=camera_prim_path)
            )
        return controller

    def camera_prim_paths(self) -> list[str]:
        return [runtime.camera_prim_path for runtime in self.runtimes]

    def active_viewport_camera_prim_path(self) -> str | None:
        if not self.runtimes:
            return None

        known = set(self.camera_prim_paths())
        viewport_camera = get_active_viewport_camera_prim_path()
        if viewport_camera in known:
            return viewport_camera

        index = min(self.active_index, len(self.runtimes) - 1)
        return self.runtimes[index].camera_prim_path

    def active_camera_prim_path(self) -> str | None:
        return self.active_viewport_camera_prim_path()

    def spawn(self, stage) -> list[str]:
        from ..isaac_adaptor import isaac_context as iscctx

        self.stage = stage
        context = iscctx.get_isaac_context()
        UsdGeom = context.pxr_usd_geom
        Gf = context.pxr_gf
        spawned: list[str] = []
        for runtime in self.runtimes:
            prim_path = runtime.camera_prim_path
            ensure_xform_path(stage, _parent_prim_path(prim_path), UsdGeom)
            camera = UsdGeom.Camera.Define(stage, prim_path)
            camera.CreateFocalLengthAttr().Set(24.0)
            camera.CreateFocusDistanceAttr().Set(400.0)
            camera.CreateHorizontalApertureAttr().Set(20.955)
            camera.CreateVerticalApertureAttr().Set(15.2908)
            camera.CreateClippingRangeAttr().Set(Gf.Vec2f(0.01, 1.0e6))

            start_position = runtime.position_at_elapsed()
            _set_camera_prim_translate(stage, context, prim_path, start_position)
            spawned.append(prim_path)
        return spawned

    def activate_viewport(self) -> str | None:
        if not self.runtimes:
            return None

        index = min(self.active_index, len(self.runtimes) - 1)
        runtime = self.runtimes[index]
        prim_path = runtime.camera_prim_path
        if not set_active_viewport_camera(prim_path):
            return None

        set_camera_position_world(
            position=runtime.position_at_elapsed(),
            camera_prim_path=prim_path,
        )
        return prim_path

    def step(self, dt: float) -> None:
        if self.stage is None or not self.runtimes:
            return

        from ..isaac_adaptor import isaac_context as iscctx

        context = iscctx.get_isaac_context()
        active_prim_path = self.active_viewport_camera_prim_path()
        for runtime in self.runtimes:
            runtime.step(
                dt,
                stage=self.stage,
                context=context,
                active=runtime.camera_prim_path == active_prim_path,
            )


def _safe_prim_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "camera_path"))
    return cleaned.strip("_") or "camera_path"
