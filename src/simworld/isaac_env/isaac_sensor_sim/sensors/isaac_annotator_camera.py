from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..annotator_runtime import ReplicatorAnnotatorRuntime
from ..base import SensorDataSource
from ..camera_utils import (
    restore_viewport_render_product,
    set_active_viewport_render_product,
)
from ..frame import SensorFrame
from .viewport_camera import MountedViewportCameraSensor


@dataclass
class MountedIsaacAnnotatorCameraSensor(MountedViewportCameraSensor):
    annotator_names: tuple[str, ...] = field(default_factory=tuple)
    create_render_product: bool = True
    route_viewport_to_render_product: bool = False
    annotator_init_delay_updates: int = 3
    sensor_type: str = "mounted_isaac_annotator_camera"
    data_source: SensorDataSource | str = SensorDataSource.ISAAC_ANNOTATOR
    _annotator_runtime: ReplicatorAnnotatorRuntime | None = field(
        default=None,
        init=False,
    )
    _viewport_render_product_state: dict | None = field(default=None, init=False)
    _active_update_count: int = field(default=0, init=False)
    _annotator_init_attempted: bool = field(default=False, init=False)

    def initialize(self) -> None:
        super().initialize()

    def deactivate(self) -> None:
        restore_viewport_render_product(self._viewport_render_product_state)
        self._viewport_render_product_state = None
        self._active_update_count = 0
        super().deactivate()

    def activate(self) -> None:
        super().activate()
        self._active_update_count = 0
        runtime = self._annotator_runtime
        if (
            self.route_viewport_to_render_product
            and runtime is not None
            and runtime.render_product_path
        ):
            self._viewport_render_product_state = set_active_viewport_render_product(
                runtime.render_product_path
            )

    def update(self, timestamp: float, dt: float) -> SensorFrame | None:
        frame = super().update(timestamp, dt)
        if frame is None:
            return None

        if self._is_active:
            self._active_update_count += 1
            self._ensure_annotator_runtime()

        raw_annotator_data = (
            self._annotator_runtime.get_data()
            if self._annotator_runtime is not None
            else {}
        )
        annotator_data = self.process_annotator_data(raw_annotator_data)

        data = dict(frame.data or {})
        data.update(annotator_data)

        meta = dict(frame.meta)
        runtime = self._annotator_runtime
        meta.update(
            {
                "data_source": _data_source_value(self.data_source),
                "annotator_names": self.annotator_names,
                "annotator_runtime_ready": bool(runtime and runtime.initialized),
                "annotator_warning": runtime.warning if runtime else None,
                "render_product_path": (
                    runtime.render_product_path if runtime is not None else None
                ),
                "viewport_routed_to_render_product": (
                    self._viewport_render_product_state is not None
                ),
                "requires_renderer_control": True,
                "requires_external_labels": False,
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

    def process_annotator_data(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        return {"annotator_data": raw_data}

    def _ensure_annotator_runtime(self) -> None:
        if not self.create_render_product or not self.annotator_names:
            return
        if self._annotator_runtime is not None or self._annotator_init_attempted:
            return
        if self._active_update_count <= max(0, int(self.annotator_init_delay_updates)):
            return

        self._annotator_init_attempted = True
        self._annotator_runtime = ReplicatorAnnotatorRuntime(
            camera_prim_path=self.camera_prim_path,
            resolution=self.resolution,
            annotator_names=self.annotator_names,
        )
        self._annotator_runtime.initialize()

        runtime = self._annotator_runtime
        if (
            self.route_viewport_to_render_product
            and runtime is not None
            and runtime.render_product_path
        ):
            self._viewport_render_product_state = set_active_viewport_render_product(
                runtime.render_product_path
            )


def _data_source_value(value) -> str:
    return getattr(value, "value", str(value))
