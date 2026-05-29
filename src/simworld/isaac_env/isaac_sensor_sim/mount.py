from __future__ import annotations

from dataclasses import dataclass


Vector3 = tuple[float, float, float]


def join_prim_path(*parts: str) -> str:
    cleaned = [part.strip("/") for part in parts if part and part.strip("/")]
    return "/" + "/".join(cleaned)


@dataclass(frozen=True)
class SensorMountSpec:
    parent_prim_path: str
    frame_id: str
    translation: Vector3 = (0.0, 0.0, 0.0)
    rotation_rpy_deg: Vector3 = (0.0, 0.0, 0.0)

    def child_path(self, child_name: str) -> str:
        return join_prim_path(self.parent_prim_path, child_name)
