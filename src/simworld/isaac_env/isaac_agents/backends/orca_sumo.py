from engine.dynamic import DynamicScenePlan

from .orca_pedestrian import OrcaPedestrianDynamicAgentBackend
from .sumo_vehicle import SumoVehicleDynamicAgentBackend
from .kinematic import DEFAULT_DYNAMIC_ROOT
from .visuals import DynamicVisualConfig


class OrcaSumoDynamicAgentBackend:
    """Composite backend: ORCA pedestrians + SUMO lane-following vehicles."""

    def __init__(
        self,
        root_prim_path: str = DEFAULT_DYNAMIC_ROOT,
        visual_config: DynamicVisualConfig | None = None,
    ):
        self.visual_config = visual_config or DynamicVisualConfig()
        self.pedestrian_backend = OrcaPedestrianDynamicAgentBackend(
            root_prim_path=root_prim_path,
            visual_config=self.visual_config,
        )
        self.vehicle_backend = SumoVehicleDynamicAgentBackend(
            root_prim_path=root_prim_path,
            visual_config=self.visual_config,
        )

    @property
    def actor_count(self) -> int:
        return (
            self.pedestrian_backend.actor_count
            + self.vehicle_backend.actor_count
        )

    def build_from_plan(self, plan: DynamicScenePlan | None):
        self.pedestrian_backend.build_from_plan(
            self._filtered_plan(plan, actor_type="pedestrian", include_lanes=False)
        )
        self.vehicle_backend.build_from_plan(
            self._filtered_plan(plan, actor_type="vehicle", include_lanes=True)
        )

    def _filtered_plan(
        self,
        plan: DynamicScenePlan | None,
        actor_type: str,
        include_lanes: bool,
    ) -> DynamicScenePlan:
        if plan is None:
            return DynamicScenePlan()

        return DynamicScenePlan(
            actors=[actor for actor in plan.actors if actor.actor_type == actor_type],
            warnings=list(plan.warnings),
            lanes=list(plan.lanes) if include_lanes else [],
        )

    def spawn(self, stage=None):
        self.pedestrian_backend.spawn(stage)
        self.vehicle_backend.spawn(stage)

    def reset(self):
        self.pedestrian_backend.reset()
        self.vehicle_backend.reset()

    def step(self, dt: float):
        self.pedestrian_backend.step(dt)
        self.vehicle_backend.step(dt)
