from typing import Protocol

from . import spot_demo


class SimRobot(Protocol):
    initialized: bool
    need_reinit: bool
    root_prim_path: str

    def spawn(self, position): ...

    def initialize(self): ...

    def mark_reinit_required(self): ...

    def forward(self, stepsize): ...

    def step(self, command): ...


ROBOT_REGISTRY = {
    "spot": spot_demo.SpotDemo,
}


def available_robot_types() -> tuple[str, ...]:
    return tuple(sorted(ROBOT_REGISTRY))


def create_robot(robot_type: str, name: str) -> SimRobot:
    try:
        robot_cls = ROBOT_REGISTRY[robot_type]
    except KeyError as exc:
        available = ", ".join(available_robot_types())
        raise ValueError(
            f"Unsupported robot type: {robot_type}. Available robot types: {available}"
        ) from exc

    return robot_cls(name)
