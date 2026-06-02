from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from .frame import SensorFrame


class SensorDataSource(str, Enum):
    PSEUDO = "pseudo"
    ISAAC_ANNOTATOR = "isaac_annotator"
    ISAAC_RTX = "isaac_rtx"


class BaseSensor(ABC):
    sensor_id: str
    sensor_type: str
    frame_id: str
    data_source: SensorDataSource | str = SensorDataSource.PSEUDO

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


class PseudoSensor(BaseSensor):
    data_source: SensorDataSource | str = SensorDataSource.PSEUDO


class IsaacSensor(BaseSensor):
    data_source: SensorDataSource | str = SensorDataSource.ISAAC_ANNOTATOR
