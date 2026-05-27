"""OmniGraph-backed visual effects scaffolding."""

from .config import (
    GraphBackend,
    GraphParticleVFXConfig,
    GraphVFXRuntimeState,
)
from .graph_builder import (
    GraphConnectionSpec,
    GraphNodeSpec,
    GraphTemplate,
    GraphVFXBuilder,
)
from .manager import GraphVFXManager
from .particle import (
    FogGraphParticleEffect,
    GraphParticleEffect,
    RainGraphParticleEffect,
    SnowGraphParticleEffect,
)

__all__ = [
    "FogGraphParticleEffect",
    "GraphBackend",
    "GraphConnectionSpec",
    "GraphNodeSpec",
    "GraphParticleEffect",
    "GraphParticleVFXConfig",
    "GraphTemplate",
    "GraphVFXBuilder",
    "GraphVFXManager",
    "GraphVFXRuntimeState",
    "RainGraphParticleEffect",
    "SnowGraphParticleEffect",
]
