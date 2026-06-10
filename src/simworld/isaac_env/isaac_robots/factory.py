from typing import Protocol

from . import noop


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
    "none": noop.NoOpRobot,
    "spot": "spot_demo.SpotDemo",
    "go2": "go2_demo.Go2Demo",
    "unitree_go2": "go2_demo.Go2Demo",
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

    if robot_cls == "spot_demo.SpotDemo":
        from . import spot_demo

        return spot_demo.SpotDemo(name)

    if robot_cls == "go2_demo.Go2Demo":
        from . import go2_demo

        return go2_demo.Go2Demo(name)

    return robot_cls(name)
