from __future__ import annotations

from abc import ABC, abstractmethod

from .frame import SensorFrame


class PseudoSensor(ABC):
    sensor_id: str
    sensor_type: str
    frame_id: str

    @abstractmethod
    def initialize(self) -> None:
        pass

    @abstractmethod
    def update(self, timestamp: float, dt: float) -> SensorFrame | None:
        pass

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass
