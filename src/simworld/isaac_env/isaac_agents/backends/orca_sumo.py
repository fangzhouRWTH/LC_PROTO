from engine.dynamic import DynamicScenePlan

from .orca_pedestrian import OrcaPedestrianDynamicAgentBackend
from .sumo_vehicle import SumoVehicleDynamicAgentBackend
from .kinematic import DEFAULT_DYNAMIC_ROOT


class OrcaSumoDynamicAgentBackend:
    """Composite backend: ORCA pedestrians + SUMO lane-following vehicles."""

    def __init__(self, root_prim_path: str = DEFAULT_DYNAMIC_ROOT):
        self.pedestrian_backend = OrcaPedestrianDynamicAgentBackend(
            root_prim_path=root_prim_path
        )
        self.vehicle_backend = SumoVehicleDynamicAgentBackend(
            root_prim_path=root_prim_path
        )

    @property
    def actor_count(self) -> int:
        return (
            self.pedestrian_backend.actor_count
            + self.vehicle_backend.actor_count
        )

    def build_from_plan(self, plan: DynamicScenePlan | None):
        self.pedestrian_backend.build_from_plan(plan)
        self.vehicle_backend.build_from_plan(plan)

    def spawn(self, stage=None):
        self.pedestrian_backend.spawn(stage)
        self.vehicle_backend.spawn(stage)

    def reset(self):
        self.pedestrian_backend.reset()
        self.vehicle_backend.reset()

    def step(self, dt: float):
        self.pedestrian_backend.step(dt)
        self.vehicle_backend.step(dt)
