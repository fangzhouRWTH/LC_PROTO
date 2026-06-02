from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..camera_utils import activate_viewport_depth_display, restore_viewport_display
from ..frame import SensorFrame
from .isaac_annotator_camera import MountedIsaacAnnotatorCameraSensor
from .viewport_camera import MountedViewportCameraSensor


@dataclass
class MountedPseudoDepthCameraSensor(MountedViewportCameraSensor):
    depth_resolution: tuple[int, int] = (320, 240)
    near_m: float = 0.2
    far_m: float = 25.0
    default_depth_m: float = 8.0
    noise_std_m: float = 0.0
    emit_depth_array: bool = True
    emit_inactive_depth_array: bool = False
    sensor_type: str = "mounted_pseudo_depth_camera"
    _depth_display_state: dict | None = field(default=None, init=False)

    def activate(self) -> None:
        super().activate()
        self._depth_display_state = activate_viewport_depth_display(
            near_m=self.near_m,
            far_m=self.far_m,
        )

    def deactivate(self) -> None:
        restore_viewport_display(self._depth_display_state)
        self._depth_display_state = None
        super().deactivate()

    def update(self, timestamp: float, dt: float) -> SensorFrame | None:
        frame = super().update(timestamp, dt)
        if frame is None:
            return None

        depth_m = (
            self._make_depth_array(timestamp)
            if self.emit_depth_array
            and (self._is_active or self.emit_inactive_depth_array)
            else None
        )
        depth_stats = self._make_depth_stats(depth_m)

        data = dict(frame.data or {})
        data.update(
            {
                "depth_m": depth_m,
                "depth_resolution": self.depth_resolution,
                "depth_encoding": "float32_meters",
                "near_m": float(self.near_m),
                "far_m": float(self.far_m),
                "invalid_value": 0.0,
                "statistics": depth_stats,
            }
        )

        meta = dict(frame.meta)
        meta.update(
            {
                "visualization_mode": "viewport_camera",
                "visual_output": (
                    "active_viewport_depth_display"
                    if self._is_active
                    else "depth_data_only"
                ),
                "requires_renderer_control": True,
                "requires_external_labels": False,
                "pseudo_model": "planar_gradient_depth",
                "viewport_display_render_var": "DistanceToCameraSDDisplay",
            }
        )

        return SensorFrame(
            sensor_id=frame.sensor_id,
            sensor_type=self.sensor_type,
            timestamp=frame.timestamp,
            frame_id=frame.frame_id,
            parent_frame_id=frame.parent_frame_id,
            world_pose=frame.world_pose,
            data=data,
            meta=meta,
        )

    def _make_depth_array(self, timestamp: float) -> np.ndarray:
        width, height = self.depth_resolution
        x = np.linspace(-1.0, 1.0, max(1, int(width)), dtype=np.float32)
        y = np.linspace(0.0, 1.0, max(1, int(height)), dtype=np.float32)
        xv, yv = np.meshgrid(x, y)

        depth = (
            float(self.default_depth_m)
            + 2.0 * yv
            + 0.35 * np.abs(xv)
            + 0.15 * np.sin(float(timestamp))
        )
        depth = np.clip(depth, float(self.near_m), float(self.far_m))

        if self.noise_std_m > 0.0:
            seed = int(float(timestamp) * 1000.0) & 0xFFFFFFFF
            rng = np.random.default_rng(seed)
            depth = depth + rng.normal(
                0.0,
                float(self.noise_std_m),
                size=depth.shape,
            ).astype(np.float32)
            depth = np.clip(depth, float(self.near_m), float(self.far_m))

        return depth.astype(np.float32, copy=False)

    def _make_depth_stats(self, depth_m: np.ndarray | None) -> dict[str, float | None]:
        if depth_m is None:
            return {
                "min_m": None,
                "max_m": None,
                "mean_m": None,
            }

        return {
            "min_m": float(depth_m.min()),
            "max_m": float(depth_m.max()),
            "mean_m": float(depth_m.mean()),
        }


@dataclass
class MountedIsaacDepthCameraSensor(MountedIsaacAnnotatorCameraSensor):
    depth_annotator_name: str = "distance_to_camera"
    near_m: float = 0.2
    far_m: float = 25.0
    sensor_type: str = "mounted_isaac_depth_camera"
    _depth_display_state: dict | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.annotator_names = (self.depth_annotator_name,)

    def activate(self) -> None:
        super().activate()
        self._depth_display_state = activate_viewport_depth_display(
            near_m=self.near_m,
            far_m=self.far_m,
        )

    def deactivate(self) -> None:
        restore_viewport_display(self._depth_display_state)
        self._depth_display_state = None
        super().deactivate()

    def process_annotator_data(self, raw_data: dict) -> dict:
        depth_m = raw_data.get(self.depth_annotator_name)
        return {
            "depth_m": depth_m,
            "depth_resolution": self.resolution,
            "depth_encoding": "float32_meters",
            "near_m": float(self.near_m),
            "far_m": float(self.far_m),
            "invalid_value": 0.0,
            "statistics": self._make_depth_stats(depth_m),
            "raw_depth_shape": _shape_of(depth_m),
            "raw_annotator_data": raw_data,
        }

    def update(self, timestamp: float, dt: float) -> SensorFrame | None:
        frame = super().update(timestamp, dt)
        if frame is None:
            return None

        meta = dict(frame.meta)
        meta.update(
            {
                "visualization_mode": "viewport_camera",
                "visual_output": (
                    "active_viewport_depth_display"
                    if self._is_active
                    else "depth_data_only"
                ),
                "viewport_display_render_var": "DistanceToCameraSDDisplay",
            }
        )

        return SensorFrame(
            sensor_id=frame.sensor_id,
            sensor_type=self.sensor_type,
            timestamp=frame.timestamp,
            frame_id=frame.frame_id,
            parent_frame_id=frame.parent_frame_id,
            world_pose=frame.world_pose,
            data=frame.data,
            meta=meta,
        )

    def _make_depth_stats(self, depth_m) -> dict[str, float | None]:
        if depth_m is None:
            return {
                "min_m": None,
                "max_m": None,
                "mean_m": None,
            }

        try:
            depth = np.asarray(depth_m, dtype=np.float32)
            return {
                "min_m": float(depth.min()),
                "max_m": float(depth.max()),
                "mean_m": float(depth.mean()),
            }
        except Exception:
            return {
                "min_m": None,
                "max_m": None,
                "mean_m": None,
            }


def _shape_of(value) -> tuple[int, ...] | None:
    if value is None:
        return None
    return tuple(getattr(value, "shape", ()) or ())
