"""Viewport-local particle VFX.

The particle module is intentionally visual-only. It renders lightweight USD
point or curve primitives around the camera view and avoids physics, collision,
or global scene simulation.
"""

from .config import (
    CameraView,
    ParticleAppearance,
    ParticleEffectConfig,
    ParticlePartition,
    ParticleVolume,
    ParticleWindVariation,
)
from .effects import (
    FogParticleEffect,
    ParticleEffect,
    RainParticleEffect,
    SnowParticleEffect,
    with_overrides,
)
from .manager import ParticleEffectManager

__all__ = [
    "CameraView",
    "FogParticleEffect",
    "ParticleAppearance",
    "ParticleEffect",
    "ParticleEffectConfig",
    "ParticleEffectManager",
    "ParticlePartition",
    "ParticleVolume",
    "ParticleWindVariation",
    "RainParticleEffect",
    "SnowParticleEffect",
    "with_overrides",
]
