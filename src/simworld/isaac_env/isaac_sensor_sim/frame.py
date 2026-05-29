from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]


@dataclass(frozen=True)
class Pose3D:
    position: Vector3
    orientation_wxyz: Quaternion


@dataclass(frozen=True)
class SensorFrame:
    sensor_id: str
    sensor_type: str
    timestamp: float
    frame_id: str
    parent_frame_id: str
    world_pose: Pose3D
    data: Any = None
    meta: dict[str, Any] = field(default_factory=dict)
