from engine.dynamic import DynamicScenePlan

from .protocol import DynamicAgentBackend


class DynamicAgentManager:
    def __init__(self, backend: DynamicAgentBackend):
        self.backend = backend

    @property
    def actor_count(self) -> int:
        return self.backend.actor_count

    def build_from_plan(self, plan: DynamicScenePlan | None):
        self.backend.build_from_plan(plan)

    def spawn(self, stage=None):
        self.backend.spawn(stage)

    def reset(self):
        self.backend.reset()

    def step(self, dt: float):
        self.backend.step(dt)
