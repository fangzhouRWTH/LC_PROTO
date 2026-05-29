from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .base import PseudoSensor
from .frame import SensorFrame


@dataclass
class SensorRig:
    rig_id: str
    sensors: list[PseudoSensor] = field(default_factory=list)
    active_sensor_id: str | None = None

    def initialize(self) -> None:
        for sensor in self.sensors:
            sensor.initialize()

        if self.active_sensor_id is not None:
            self.activate(self.active_sensor_id)

    def activate(self, sensor_id: str) -> None:
        found = False
        for sensor in self.sensors:
            if sensor.sensor_id == sensor_id:
                sensor.activate()
                found = True
            else:
                sensor.deactivate()

        if not found:
            raise ValueError(f"Unknown sensor id for rig {self.rig_id}: {sensor_id}")

        self.active_sensor_id = sensor_id

    def update(self, timestamp: float, dt: float) -> dict[str, SensorFrame]:
        frames: dict[str, SensorFrame] = {}
        for sensor in self.sensors:
            frame = sensor.update(timestamp, dt)
            if frame is not None:
                frames[sensor.sensor_id] = frame
        return frames

    @property
    def active_sensor(self) -> PseudoSensor | None:
        if self.active_sensor_id is None:
            return None
        return next(
            (
                sensor
                for sensor in self.sensors
                if sensor.sensor_id == self.active_sensor_id
            ),
            None,
        )

    @property
    def active_viewport_camera_prim_path(self) -> str | None:
        sensor = self.active_sensor
        if sensor is None:
            return None
        camera_prim_path = getattr(sensor, "camera_prim_path", None)
        if isinstance(camera_prim_path, str) and camera_prim_path:
            return camera_prim_path
        return None

    @classmethod
    def from_sensors(
        cls,
        rig_id: str,
        sensors: Iterable[PseudoSensor],
        active_sensor_id: str | None = None,
    ) -> "SensorRig":
        return cls(
            rig_id=rig_id,
            sensors=list(sensors),
            active_sensor_id=active_sensor_id,
        )
