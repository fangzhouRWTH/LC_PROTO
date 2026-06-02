from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .base import BaseSensor
from .frame import SensorFrame


@dataclass
class SensorRig:
    rig_id: str
    sensors: list[BaseSensor] = field(default_factory=list)
    active_sensor_id: str | None = None

    def initialize(self) -> None:
        for sensor in self.sensors:
            sensor.initialize()

        if self.active_sensor_id is not None:
            self.activate(self.active_sensor_id)

    def activate(self, sensor_id: str) -> None:
        target = self.get_sensor(sensor_id)
        if target is None:
            raise ValueError(f"Unknown sensor id for rig {self.rig_id}: {sensor_id}")

        for sensor in self.sensors:
            if sensor is not target:
                sensor.deactivate()

        target.activate()
        self.active_sensor_id = sensor_id

    def update(self, timestamp: float, dt: float) -> dict[str, SensorFrame]:
        frames: dict[str, SensorFrame] = {}
        for sensor in self.sensors:
            frame = sensor.update(timestamp, dt)
            if frame is not None:
                frames[sensor.sensor_id] = frame
        return frames

    @property
    def active_sensor(self) -> BaseSensor | None:
        if self.active_sensor_id is None:
            return None
        return self.get_sensor(self.active_sensor_id)

    def get_sensor(self, sensor_id: str) -> BaseSensor | None:
        return next(
            (sensor for sensor in self.sensors if sensor.sensor_id == sensor_id),
            None,
        )

    def sensor_ids(self) -> tuple[str, ...]:
        return tuple(sensor.sensor_id for sensor in self.sensors)

    def viewport_camera_sensor_ids(self) -> tuple[str, ...]:
        return tuple(
            sensor.sensor_id
            for sensor in self.sensors
            if isinstance(getattr(sensor, "camera_prim_path", None), str)
        )

    def activate_next_viewport_camera(self) -> str | None:
        camera_sensor_ids = self.viewport_camera_sensor_ids()
        if not camera_sensor_ids:
            return None

        if self.active_sensor_id not in camera_sensor_ids:
            next_sensor_id = camera_sensor_ids[0]
        else:
            index = camera_sensor_ids.index(self.active_sensor_id)
            next_sensor_id = camera_sensor_ids[(index + 1) % len(camera_sensor_ids)]

        self.activate(next_sensor_id)
        return next_sensor_id

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
        sensors: Iterable[BaseSensor],
        active_sensor_id: str | None = None,
    ) -> "SensorRig":
        return cls(
            rig_id=rig_id,
            sensors=list(sensors),
            active_sensor_id=active_sensor_id,
        )
