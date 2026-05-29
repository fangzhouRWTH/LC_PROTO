from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


OBJECT_LABEL_SCHEMA = "simworld.object_labels.v1"
RASTER_LABEL_SCHEMA = "simworld.raster_labels.v1"

Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]


@dataclass(frozen=True)
class BoundingBox3D:
    center: Vector3
    size: Vector3
    rotation_wxyz: Quaternion = (1.0, 0.0, 0.0, 0.0)

    def validate(self) -> None:
        if len(self.center) != 3:
            raise ValueError("BoundingBox3D.center must contain 3 values.")
        if len(self.size) != 3:
            raise ValueError("BoundingBox3D.size must contain 3 values.")
        if any(value < 0.0 for value in self.size):
            raise ValueError("BoundingBox3D.size values must be non-negative.")
        if len(self.rotation_wxyz) != 4:
            raise ValueError("BoundingBox3D.rotation_wxyz must contain 4 values.")


@dataclass(frozen=True)
class ObjectLabel:
    prim_path: str
    class_id: int
    class_name: str
    instance_id: int
    bbox3d_world: BoundingBox3D | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.prim_path.startswith("/"):
            raise ValueError("ObjectLabel.prim_path must be an absolute USD path.")
        if self.class_id < 0:
            raise ValueError("ObjectLabel.class_id must be non-negative.")
        if not self.class_name:
            raise ValueError("ObjectLabel.class_name cannot be empty.")
        if self.instance_id < 0:
            raise ValueError("ObjectLabel.instance_id must be non-negative.")
        if self.bbox3d_world is not None:
            self.bbox3d_world.validate()


@dataclass(frozen=True)
class ObjectLabelBundle:
    objects: tuple[ObjectLabel, ...]
    schema: str = OBJECT_LABEL_SCHEMA

    def validate(self) -> None:
        if self.schema != OBJECT_LABEL_SCHEMA:
            raise ValueError(f"Unsupported object label schema: {self.schema}")
        for item in self.objects:
            item.validate()


@dataclass(frozen=True)
class RasterLabelBundle:
    resolution: tuple[int, int]
    class_map: Any
    instance_map: Any | None = None
    palette: dict[int, tuple[int, int, int]] = field(default_factory=dict)
    camera_frame_id: str = ""
    timestamp: float = 0.0
    schema: str = RASTER_LABEL_SCHEMA

    def validate(self) -> None:
        if self.schema != RASTER_LABEL_SCHEMA:
            raise ValueError(f"Unsupported raster label schema: {self.schema}")
        if len(self.resolution) != 2:
            raise ValueError("RasterLabelBundle.resolution must contain 2 values.")
        if self.resolution[0] <= 0 or self.resolution[1] <= 0:
            raise ValueError("RasterLabelBundle.resolution values must be positive.")
        if not self.camera_frame_id:
            raise ValueError("RasterLabelBundle.camera_frame_id cannot be empty.")
        for class_id, color in self.palette.items():
            if class_id < 0:
                raise ValueError("RasterLabelBundle.palette class ids must be non-negative.")
            if len(color) != 3:
                raise ValueError("RasterLabelBundle.palette colors must contain 3 values.")
