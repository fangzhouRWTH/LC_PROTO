from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Sequence


Vector3 = tuple[float, float, float]
Color3 = tuple[float, float, float]
RendererKind = Literal["points", "streaks", "billboard"]


@dataclass(frozen=True)
class CameraView:
    """Camera pose inputs used to define the viewport recycling volume."""

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
class ParticlePartition:
    """Repeat one simulated particle tile across the viewport box."""

    width_segments: int = 1
    height_segments: int = 1

    @property
    def tile_count(self) -> int:
        return self.width_segments * self.height_segments

    def base_particle_count(self, particle_count: int) -> int:
        return max(1, (particle_count + self.tile_count - 1) // self.tile_count)

    def validate(self) -> None:
        if self.width_segments <= 0:
            raise ValueError("ParticlePartition.width_segments must be positive.")
        if self.height_segments <= 0:
            raise ValueError("ParticlePartition.height_segments must be positive.")


@dataclass(frozen=True)
class ParticleWindVariation:
    """Visual wind-direction modulation around the configured main wind."""

    angle_degrees: float = 0.0
    period_seconds: float = 8.0
    randomness: float = 0.25

    @property
    def enabled(self) -> bool:
        return self.angle_degrees > 0.0

    def validate(self) -> None:
        if self.angle_degrees < 0.0:
            raise ValueError("ParticleWindVariation.angle_degrees cannot be negative.")
        if self.angle_degrees > 180.0:
            raise ValueError("ParticleWindVariation.angle_degrees cannot exceed 180.")
        if self.period_seconds <= 0.0:
            raise ValueError("ParticleWindVariation.period_seconds must be positive.")
        if self.randomness < 0.0:
            raise ValueError("ParticleWindVariation.randomness cannot be negative.")
        if self.randomness > 1.0:
            raise ValueError("ParticleWindVariation.randomness cannot exceed 1.")


@dataclass(frozen=True)
class ParticleAppearance:
    """Simple USD display attributes for visual particles."""

    color: Color3 = (1.0, 1.0, 1.0)
    opacity: float = 0.75
    point_width: float = 0.035
    streak_length: float = 0.55
    streak_width: float = 0.018
    billboard_texture_path: str | None = None
    billboard_shader_path: str | None = None
    billboard_use_mdl_shader: bool = False
    billboard_opacity_gain: float = 10.0
    billboard_debug: bool = False
    billboard_debug_color: Color3 = (1.0, 0.45, 0.05)
    billboard_debug_opacity: float = 0.5

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
        if (
            self.billboard_texture_path is not None
            and not self.billboard_texture_path
        ):
            raise ValueError(
                "ParticleAppearance.billboard_texture_path cannot be empty."
            )
        if (
            self.billboard_shader_path is not None
            and not self.billboard_shader_path
        ):
            raise ValueError(
                "ParticleAppearance.billboard_shader_path cannot be empty."
            )
        if self.billboard_opacity_gain < 0.0:
            raise ValueError(
                "ParticleAppearance.billboard_opacity_gain cannot be negative."
            )
        if len(self.billboard_debug_color) != 3:
            raise ValueError(
                "ParticleAppearance.billboard_debug_color must contain 3 values."
            )
        if not 0.0 <= self.billboard_debug_opacity <= 1.0:
            raise ValueError(
                "ParticleAppearance.billboard_debug_opacity must be between 0 and 1."
            )


@dataclass(frozen=True)
class ParticleEffectConfig:
    """Configuration for viewport-local particle VFX."""

    name: str
    particle_count: int
    volume: ParticleVolume = field(default_factory=ParticleVolume)
    partition: ParticlePartition = field(default_factory=ParticlePartition)
    appearance: ParticleAppearance = field(default_factory=ParticleAppearance)
    renderer: RendererKind = "points"
    effect_type: str = "particle"
    root_path: str = "/World/VFX"
    speed: float = 1.0
    speed_jitter: float = 0.0
    direction_world: Vector3 = (0.0, 0.0, -1.0)
    wind_world: Vector3 = (0.0, 0.0, 0.0)
    wind_variation: ParticleWindVariation = field(
        default_factory=ParticleWindVariation
    )
    turbulence: float = 0.0
    max_dt: float = 1.0 / 15.0
    seed: int | None = None

    def validate(self) -> None:
        if not self.name:
            raise ValueError("ParticleEffectConfig.name cannot be empty.")
        if self.particle_count <= 0:
            raise ValueError("ParticleEffectConfig.particle_count must be positive.")
        if self.renderer not in ("points", "streaks", "billboard"):
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
        self.partition.validate()
        self.wind_variation.validate()
        self.appearance.validate()
