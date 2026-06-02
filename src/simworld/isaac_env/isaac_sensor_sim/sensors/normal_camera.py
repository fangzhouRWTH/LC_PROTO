from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..camera_utils import (
    NORMAL_DISPLAY_RENDER_VAR_OUTPUT,
    activate_viewport_normal_display,
    restore_viewport_display,
)
from ..frame import SensorFrame
from ..material_override import (
    DEFAULT_SENSOR_MATERIAL_EXCLUDED_ROOTS,
    MaterialOverrideState,
    apply_flat_material_override,
    apply_normal_mdl_material_override,
    normal_to_rgb,
    restore_material_override,
)
from .isaac_annotator_camera import MountedIsaacAnnotatorCameraSensor
from .viewport_camera import MountedViewportCameraSensor


@dataclass
class MountedPseudoNormalCameraSensor(MountedViewportCameraSensor):
    normal_resolution: tuple[int, int] = (320, 240)
    plane_normal_camera: tuple[float, float, float] = (0.0, 0.0, 1.0)
    emit_normal_array: bool = True
    emit_inactive_normal_array: bool = False
    emit_preview_rgb: bool = True
    enable_material_override: bool = True
    material_override_path: str = (
        "/World/SimWorldSensors/Materials/NormalViewMaterial"
    )
    material_override_excluded_roots: tuple[str, ...] = (
        DEFAULT_SENSOR_MATERIAL_EXCLUDED_ROOTS
    )
    sensor_type: str = "mounted_pseudo_normal_camera"
    _normal_display_state: dict | None = field(default=None, init=False)
    _material_override_state: MaterialOverrideState | None = field(
        default=None,
        init=False,
    )

    def activate(self) -> None:
        super().activate()
        self._normal_display_state = activate_viewport_normal_display()
        if self.enable_material_override and not _normal_display_looks_active(
            self._normal_display_state
        ):
            self._material_override_state = self._apply_material_override()

    def deactivate(self) -> None:
        restore_material_override(self._material_override_state)
        self._material_override_state = None
        restore_viewport_display(self._normal_display_state)
        self._normal_display_state = None
        super().deactivate()

    def update(self, timestamp: float, dt: float) -> SensorFrame | None:
        frame = super().update(timestamp, dt)
        if frame is None:
            return None

        normal_map = (
            self._make_normal_map()
            if self.emit_normal_array
            and (self._is_active or self.emit_inactive_normal_array)
            else None
        )
        normal_rgb = (
            self._make_preview_rgb(normal_map)
            if normal_map is not None and self.emit_preview_rgb
            else None
        )

        data = dict(frame.data or {})
        data.update(
            {
                "normal_map": normal_map,
                "normal_rgb_u8": normal_rgb,
                "normal_resolution": self.normal_resolution,
                "normal_encoding": "float32_xyz_unit",
                "normal_output_source": "pseudo_constant_plane",
                "normal_from_annotator": False,
                "coordinate_frame": "camera",
                "plane_normal_camera": self._normalized_plane_normal(),
                "invalid_value": (0.0, 0.0, 0.0),
                "statistics": self._make_normal_stats(normal_map),
            }
        )

        meta = dict(frame.meta)
        meta.update(
            {
                "visualization_mode": (
                    "material_override"
                    if self._material_override_state is not None
                    else "viewport_camera"
                ),
                "visual_output": (
                    "active_viewport_normal_display"
                    if self._is_active
                    else "normal_data_only"
                ),
                "requires_renderer_control": True,
                "requires_external_labels": False,
                "pseudo_model": "constant_plane_normal",
                "viewport_display_render_var": NORMAL_DISPLAY_RENDER_VAR_OUTPUT,
                "material_override_active": self._material_override_state is not None,
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

    def _normalized_plane_normal(self) -> tuple[float, float, float]:
        normal = np.asarray(self.plane_normal_camera, dtype=np.float32)
        length = float(np.linalg.norm(normal))
        if length <= 1e-6:
            return (0.0, 0.0, 1.0)
        normal = normal / length
        return (float(normal[0]), float(normal[1]), float(normal[2]))

    def _apply_material_override(self) -> MaterialOverrideState | None:
        from ...isaac_adaptor import isaac_context as iscctx

        stage = iscctx.get_isaac_context().omni_usd.get_context().get_stage()
        if stage is None:
            return None

        return apply_flat_material_override(
            stage,
            color_rgb=normal_to_rgb(self._normalized_plane_normal()),
            material_path=self.material_override_path,
            excluded_roots=self.material_override_excluded_roots,
        )

    def _make_normal_map(self) -> np.ndarray:
        width, height = self.normal_resolution
        width = max(1, int(width))
        height = max(1, int(height))
        normal = np.asarray(self._normalized_plane_normal(), dtype=np.float32)
        normal_map = np.empty((height, width, 3), dtype=np.float32)
        normal_map[:, :, :] = normal
        return normal_map

    def _make_preview_rgb(self, normal_map: np.ndarray) -> np.ndarray:
        encoded = np.clip((normal_map * 0.5 + 0.5) * 255.0, 0.0, 255.0)
        return encoded.astype(np.uint8)

    def _make_normal_stats(
        self,
        normal_map: np.ndarray | None,
    ) -> dict[str, float | tuple[float, float, float] | None]:
        if normal_map is None:
            return {
                "mean_xyz": None,
                "min_length": None,
                "max_length": None,
            }

        lengths = np.linalg.norm(normal_map, axis=2)
        mean_xyz = normal_map.reshape(-1, 3).mean(axis=0)
        return {
            "mean_xyz": (
                float(mean_xyz[0]),
                float(mean_xyz[1]),
                float(mean_xyz[2]),
            ),
            "min_length": float(lengths.min()),
            "max_length": float(lengths.max()),
        }


@dataclass
class MountedIsaacNormalCameraSensor(MountedIsaacAnnotatorCameraSensor):
    normal_annotator_name: str = "normals"
    route_viewport_to_render_product: bool = False
    enable_material_override: bool = False
    use_mdl_normal_visualizer: bool = False
    material_override_path: str = (
        "/World/SimWorldSensors/Materials/IsaacNormalViewMaterial"
    )
    material_override_excluded_roots: tuple[str, ...] = (
        DEFAULT_SENSOR_MATERIAL_EXCLUDED_ROOTS
    )
    sensor_type: str = "mounted_isaac_normal_camera"
    _normal_display_state: dict | None = field(default=None, init=False)
    _material_override_state: MaterialOverrideState | None = field(
        default=None,
        init=False,
    )

    def __post_init__(self) -> None:
        self.annotator_names = (self.normal_annotator_name,)

    def activate(self) -> None:
        super().activate()
        self._normal_display_state = activate_viewport_normal_display()
        if self.enable_material_override:
            self._material_override_state = self._apply_material_override()

    def deactivate(self) -> None:
        restore_material_override(self._material_override_state)
        self._material_override_state = None
        restore_viewport_display(self._normal_display_state)
        self._normal_display_state = None
        super().deactivate()

    def process_annotator_data(self, raw_data: dict) -> dict:
        annotator_output = raw_data.get(self.normal_annotator_name)
        normal_map = self._extract_normal_xyz(annotator_output)
        return {
            "normal_map": normal_map,
            "normal_rgb_u8": self._make_preview_rgb_safe(normal_map),
            "normal_resolution": self.resolution,
            "normal_encoding": "float32_xyz_unit",
            "normal_output_source": (
                f"isaac_annotator:{self.normal_annotator_name}"
                if normal_map is not None
                else "annotator_unavailable"
            ),
            "normal_from_annotator": normal_map is not None,
            "normal_annotator_name": self.normal_annotator_name,
            "coordinate_frame": "camera_or_renderer",
            "invalid_value": (0.0, 0.0, 0.0),
            "statistics": self._make_normal_stats_safe(normal_map),
            "raw_normal_shape": _shape_of(annotator_output),
            "raw_annotator_data": raw_data,
        }

    def update(self, timestamp: float, dt: float) -> SensorFrame | None:
        frame = super().update(timestamp, dt)
        if frame is None:
            return None

        meta = dict(frame.meta)
        meta.update(
            {
                "visualization_mode": (
                    "material_override"
                    if self._material_override_state is not None
                    else "viewport_camera"
                ),
                "visual_output": (
                    "active_viewport_normal_display"
                    if self._is_active
                    else "normal_data_only"
                ),
                "viewport_display_render_var": NORMAL_DISPLAY_RENDER_VAR_OUTPUT,
                "material_override_active": self._material_override_state is not None,
                "material_override_mode": (
                    "mdl_surface_normal"
                    if self._material_override_state is not None
                    and self.use_mdl_normal_visualizer
                    else None
                ),
                "normal_output_source": (
                    frame.data.get("normal_output_source")
                    if isinstance(frame.data, dict)
                    else None
                ),
                "normal_from_annotator": (
                    frame.data.get("normal_from_annotator")
                    if isinstance(frame.data, dict)
                    else False
                ),
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

    def _apply_material_override(self) -> MaterialOverrideState | None:
        from ...isaac_adaptor import isaac_context as iscctx

        stage = iscctx.get_isaac_context().omni_usd.get_context().get_stage()
        if stage is None:
            return None

        if self.use_mdl_normal_visualizer:
            from ...assets import DEFAULT_NORMAL_VIEW_SHADER

            return apply_normal_mdl_material_override(
                stage,
                material_path=self.material_override_path,
                shader_path=DEFAULT_NORMAL_VIEW_SHADER,
                excluded_roots=self.material_override_excluded_roots,
            )

        return apply_flat_material_override(
            stage,
            color_rgb=normal_to_rgb((0.0, 0.0, 1.0)),
            material_path=self.material_override_path,
            excluded_roots=self.material_override_excluded_roots,
        )

    def _make_preview_rgb_safe(self, normal_map) -> np.ndarray | None:
        if normal_map is None:
            return None
        try:
            normal = np.asarray(normal_map, dtype=np.float32)
            encoded = np.clip((normal * 0.5 + 0.5) * 255.0, 0.0, 255.0)
            return encoded.astype(np.uint8)
        except Exception:
            return None

    def _make_normal_stats_safe(self, normal_map) -> dict:
        if normal_map is None:
            return {
                "mean_xyz": None,
                "min_length": None,
                "max_length": None,
            }

        try:
            normal = np.asarray(normal_map, dtype=np.float32)
            normal = normal.reshape(-1, 3)
            lengths = np.linalg.norm(normal, axis=1)
            mean_xyz = normal.mean(axis=0)
            return {
                "mean_xyz": (
                    float(mean_xyz[0]),
                    float(mean_xyz[1]),
                    float(mean_xyz[2]),
                ),
                "min_length": float(lengths.min()),
                "max_length": float(lengths.max()),
            }
        except Exception:
            return {
                "mean_xyz": None,
                "min_length": None,
                "max_length": None,
            }

    def _extract_normal_xyz(self, annotator_output) -> np.ndarray | None:
        if annotator_output is None:
            return None

        try:
            normal = np.asarray(annotator_output, dtype=np.float32)
        except Exception:
            return None

        if normal.ndim < 3 or normal.shape[-1] < 3:
            return None
        return normal[..., :3]


def _shape_of(value) -> tuple[int, ...] | None:
    if value is None:
        return None
    return tuple(getattr(value, "shape", ()) or ())


def _normal_display_looks_active(display_state: dict | None) -> bool:
    if not display_state:
        return False
    templates = display_state.get("display_templates")
    if isinstance(templates, list) and templates:
        return True
    return bool(display_state.get("render_product_path"))
