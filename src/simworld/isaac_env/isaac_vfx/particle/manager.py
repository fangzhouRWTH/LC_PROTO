from __future__ import annotations

from collections.abc import Iterable

from .config import CameraView
from .effects import ParticleEffect


class ParticleEffectManager:
    """Small registry for updating multiple particle effects together."""

    def __init__(self, effects: Iterable[ParticleEffect] | None = None):
        self._effects: dict[str, ParticleEffect] = {}
        if effects is not None:
            for effect in effects:
                self.add(effect)

    def add(self, effect: ParticleEffect) -> ParticleEffect:
        self._effects[effect.config.name] = effect
        return effect

    def remove(self, name: str) -> ParticleEffect | None:
        return self._effects.pop(name, None)

    def get(self, name: str) -> ParticleEffect | None:
        return self._effects.get(name)

    def set_active(self, name: str, active: bool, stage=None) -> None:
        effect = self._effects[name]
        effect.set_active(active, stage=stage)

    def update_all(
        self,
        dt: float,
        camera_position,
        camera_forward,
        camera_up=(0.0, 0.0, 1.0),
        stage=None,
    ) -> None:
        for effect in self._effects.values():
            effect.update(
                dt,
                camera_position=camera_position,
                camera_forward=camera_forward,
                camera_up=camera_up,
                stage=stage,
            )

    def update_from_camera_view(
        self,
        dt: float,
        camera_view: CameraView,
        stage=None,
    ) -> None:
        self.update_all(
            dt,
            camera_position=camera_view.position,
            camera_forward=camera_view.forward,
            camera_up=camera_view.up,
            stage=stage,
        )

    def names(self) -> tuple[str, ...]:
        return tuple(self._effects.keys())
