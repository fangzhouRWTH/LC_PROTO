from __future__ import annotations

from collections.abc import Iterable

from .particle import GraphParticleEffect


class GraphVFXManager:
    def __init__(self, effects: Iterable[GraphParticleEffect] | None = None):
        self._effects: dict[str, GraphParticleEffect] = {}
        if effects is not None:
            for effect in effects:
                self.add(effect)

    def add(self, effect: GraphParticleEffect) -> GraphParticleEffect:
        self._effects[effect.config.name] = effect
        return effect

    def get(self, name: str) -> GraphParticleEffect | None:
        return self._effects.get(name)

    def remove(self, name: str) -> GraphParticleEffect | None:
        return self._effects.pop(name, None)

    def build_all(self, stage=None) -> None:
        for effect in self._effects.values():
            effect.build(stage=stage)

    def update_all(
        self,
        dt: float,
        camera_position,
        camera_forward,
        camera_up=(0.0, 0.0, 1.0),
        stage=None,
    ) -> None:
        for effect in self._effects.values():
            effect.update_runtime_state(
                dt,
                camera_position=camera_position,
                camera_forward=camera_forward,
                camera_up=camera_up,
                stage=stage,
            )

    def update_from_camera_view(self, dt: float, camera_view, stage=None) -> None:
        self.update_all(
            dt,
            camera_position=camera_view.position,
            camera_forward=camera_view.forward,
            camera_up=camera_view.up,
            stage=stage,
        )

    def names(self) -> tuple[str, ...]:
        return tuple(self._effects.keys())

