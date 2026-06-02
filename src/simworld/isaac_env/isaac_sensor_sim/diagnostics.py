from __future__ import annotations

from dataclasses import dataclass, field
import pathlib
from typing import Any

import numpy as np

from .frame import SensorFrame


@dataclass
class SensorDiagnosticsPrinter:
    enabled: bool = False
    interval_s: float = 1.0
    active_only: bool = True
    _last_print_time_by_sensor: dict[str, float] = field(default_factory=dict)

    def maybe_print(
        self,
        *,
        timestamp: float,
        frames: dict[str, SensorFrame],
        active_sensor_id: str | None = None,
    ) -> None:
        if not self.enabled:
            return

        for sensor_id, frame in frames.items():
            if self.active_only and active_sensor_id and sensor_id != active_sensor_id:
                continue
            last_print_time = self._last_print_time_by_sensor.get(sensor_id)
            if (
                last_print_time is not None
                and float(timestamp) - last_print_time < max(0.0, self.interval_s)
            ):
                continue
            self._last_print_time_by_sensor[sensor_id] = float(timestamp)
            print(_format_sensor_diagnostic(frame))


@dataclass
class SensorDebugFrameWriter:
    output_dir: pathlib.Path | None = None
    interval_s: float = 1.0
    active_only: bool = True
    _last_write_time_by_sensor: dict[str, float] = field(default_factory=dict)
    _write_index_by_sensor: dict[str, int] = field(default_factory=dict)

    @property
    def enabled(self) -> bool:
        return self.output_dir is not None

    def maybe_write(
        self,
        *,
        timestamp: float,
        frames: dict[str, SensorFrame],
        active_sensor_id: str | None = None,
    ) -> None:
        if not self.enabled:
            return

        for sensor_id, frame in frames.items():
            if self.active_only and active_sensor_id and sensor_id != active_sensor_id:
                continue

            last_write_time = self._last_write_time_by_sensor.get(sensor_id)
            if (
                last_write_time is not None
                and float(timestamp) - last_write_time < max(0.0, self.interval_s)
            ):
                continue

            preview = _frame_preview_image_u8(frame)
            if preview is None:
                continue

            self._last_write_time_by_sensor[sensor_id] = float(timestamp)
            output_path = self._make_output_path(sensor_id, float(timestamp))
            _write_png(output_path, preview)
            print(f"[SENSOR] wrote debug preview: {output_path}")

    def _make_output_path(self, sensor_id: str, timestamp: float) -> pathlib.Path:
        assert self.output_dir is not None
        index = self._write_index_by_sensor.get(sensor_id, 0)
        self._write_index_by_sensor[sensor_id] = index + 1
        timestamp_ms = int(round(max(0.0, timestamp) * 1000.0))
        return (
            pathlib.Path(self.output_dir)
            / sensor_id
            / f"{index:06d}_{timestamp_ms:010d}ms.png"
        )


def _format_sensor_diagnostic(frame: SensorFrame) -> str:
    data = frame.data or {}
    meta = frame.meta or {}

    parts = [
        "[SENSOR]",
        f"id={frame.sensor_id}",
        f"type={frame.sensor_type}",
        f"source={meta.get('data_source')}",
        f"active_visual={meta.get('visual_output')}",
        f"ready={meta.get('annotator_runtime_ready')}",
    ]

    warning = meta.get("annotator_warning")
    if warning:
        parts.append(f"warning={warning}")

    render_product_path = meta.get("render_product_path")
    if render_product_path:
        parts.append(f"render_product={render_product_path}")

    for key in (
        "raw_normal_shape",
        "raw_depth_shape",
        "normal_resolution",
        "depth_resolution",
    ):
        if key in data:
            parts.append(f"{key}={data.get(key)}")

    stats = data.get("statistics")
    if isinstance(stats, dict):
        parts.append(f"stats={_compact_dict(stats)}")

    return " ".join(parts)


def _compact_dict(value: dict[str, Any]) -> str:
    entries = []
    for key, item in value.items():
        entries.append(f"{key}:{_compact_value(item)}")
    return "{" + ", ".join(entries) + "}"


def _compact_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, tuple):
        return "(" + ",".join(_compact_value(item) for item in value) + ")"
    return str(value)


def _frame_preview_image_u8(frame: SensorFrame) -> np.ndarray | None:
    data = frame.data or {}

    normal_rgb = data.get("normal_rgb_u8")
    if normal_rgb is not None:
        image = _as_rgb_u8(normal_rgb)
        if image is not None:
            return image

    depth_m = data.get("depth_m")
    if depth_m is not None:
        return _depth_preview_u8(depth_m)

    return None


def _as_rgb_u8(value: Any) -> np.ndarray | None:
    try:
        image = np.asarray(value)
    except Exception:
        return None

    if image.ndim == 2:
        image = np.repeat(image[:, :, None], 3, axis=2)
    if image.ndim != 3 or image.shape[2] < 3:
        return None

    image = image[:, :, :3]
    if image.dtype != np.uint8:
        image = np.clip(image, 0, 255).astype(np.uint8)
    return np.ascontiguousarray(image)


def _depth_preview_u8(value: Any) -> np.ndarray | None:
    try:
        depth = np.asarray(value, dtype=np.float32)
    except Exception:
        return None

    if depth.ndim == 3 and depth.shape[-1] == 1:
        depth = depth[:, :, 0]
    if depth.ndim != 2:
        return None

    valid = np.isfinite(depth) & (depth > 0.0)
    if not np.any(valid):
        return None

    valid_depth = depth[valid]
    near = float(np.percentile(valid_depth, 1.0))
    far = float(np.percentile(valid_depth, 99.0))
    if far <= near:
        far = near + 1.0

    normalized = np.clip((depth - near) / (far - near), 0.0, 1.0)
    normalized[~valid] = 0.0
    gray = (normalized * 255.0).astype(np.uint8)
    return np.repeat(gray[:, :, None], 3, axis=2)


def _write_png(path: pathlib.Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    from PIL import Image

    Image.fromarray(image).save(path)
