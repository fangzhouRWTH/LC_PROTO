from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Sequence


Vector3 = tuple[float, float, float]
Color3 = tuple[float, float, float]
RendererKind = Literal["points", "streaks"]


@dataclass(frozen=True)
class CameraView:
    """Camera pose inputs used to keep particles local to the viewport."""

    position: Vector3
    forward: Vector3
    up: Vector3 = (0.0, 0.0, 1.0)

    @classmethod
    def from_look_at(
        cls,
        position: Sequence[float],
        target: Sequence[float],
        up: Sequence[float] = (0.0, 0.0, 1.0),
    ) -> "CameraView":
        forward = (
            float(target[0] - position[0]),
            float(target[1] - position[1]),
            float(target[2] - position[2]),
        )
        return cls(
            position=(float(position[0]), float(position[1]), float(position[2])),
            forward=forward,
            up=(float(up[0]), float(up[1]), float(up[2])),
        )


@dataclass(frozen=True)
class ParticleVolume:
    """Camera-local box used for visual particle simulation."""

    width: float = 18.0
    height: float = 10.0
    depth: float = 28.0
    near_distance: float = 1.0

    def validate(self) -> None:
        if self.width <= 0.0:
            raise ValueError("ParticleVolume.width must be positive.")
        if self.height <= 0.0:
            raise ValueError("ParticleVolume.height must be positive.")
        if self.depth <= 0.0:
            raise ValueError("ParticleVolume.depth must be positive.")
        if self.near_distance < 0.0:
            raise ValueError("ParticleVolume.near_distance must be non-negative.")


@dataclass(frozen=True)
class ParticleAppearance:
    """Simple USD display attributes for visual particles."""

    color: Color3 = (1.0, 1.0, 1.0)
    opacity: float = 0.75
    point_width: float = 0.035
    streak_length: float = 0.55
    streak_width: float = 0.018

    def validate(self) -> None:
        if not 0.0 <= self.opacity <= 1.0:
            raise ValueError("ParticleAppearance.opacity must be between 0 and 1.")
        if self.point_width <= 0.0:
            raise ValueError("ParticleAppearance.point_width must be positive.")
        if self.streak_length <= 0.0:
            raise ValueError("ParticleAppearance.streak_length must be positive.")
        if self.streak_width <= 0.0:
            raise ValueError("ParticleAppearance.streak_width must be positive.")
        if len(self.color) != 3:
            raise ValueError("ParticleAppearance.color must contain 3 values.")


@dataclass(frozen=True)
class ParticleEffectConfig:
    """Configuration for viewport-local particle VFX."""

    name: str
    particle_count: int
    volume: ParticleVolume = field(default_factory=ParticleVolume)
    appearance: ParticleAppearance = field(default_factory=ParticleAppearance)
    renderer: RendererKind = "points"
    effect_type: str = "particle"
    root_path: str = "/World/VFX"
    speed: float = 1.0
    speed_jitter: float = 0.0
    direction_world: Vector3 = (0.0, 0.0, -1.0)
    wind_world: Vector3 = (0.0, 0.0, 0.0)
    turbulence: float = 0.0
    max_dt: float = 1.0 / 15.0
    seed: int | None = None

    def validate(self) -> None:
        if not self.name:
            raise ValueError("ParticleEffectConfig.name cannot be empty.")
        if self.particle_count <= 0:
            raise ValueError("ParticleEffectConfig.particle_count must be positive.")
        if self.renderer not in ("points", "streaks"):
            raise ValueError(f"Unsupported particle renderer: {self.renderer}")
        if self.effect_type != "particle":
            raise ValueError("ParticleEffectConfig.effect_type must be 'particle'.")
        if self.speed < 0.0:
            raise ValueError("ParticleEffectConfig.speed must be non-negative.")
        if self.speed_jitter < 0.0:
            raise ValueError("ParticleEffectConfig.speed_jitter must be non-negative.")
        if self.turbulence < 0.0:
            raise ValueError("ParticleEffectConfig.turbulence must be non-negative.")
        if self.max_dt <= 0.0:
            raise ValueError("ParticleEffectConfig.max_dt must be positive.")

        self.volume.validate()
        self.appearance.validate()
