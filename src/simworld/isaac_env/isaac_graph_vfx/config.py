from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ..isaac_vfx.particle.config import ParticleAppearance, ParticleVolume, Vector3


GraphBackend = Literal["warp", "particle_system_core2", "custom"]


@dataclass(frozen=True)
class GraphVFXRuntimeState:
    """Small per-frame payload passed from Python into the graph."""

    dt: float
    camera_position: Vector3
    camera_forward: Vector3
    camera_up: Vector3 = (0.0, 0.0, 1.0)


@dataclass(frozen=True)
class GraphParticleVFXConfig:
    """Configuration for a graph-driven viewport-local particle effect."""

    name: str
    particle_count: int
    camera_prim_path: str
    backend: GraphBackend = "warp"
    root_path: str = "/World/GraphVFX"
    graph_root_path: str = "/World/GraphVFXGraphs"
    output_root_path: str = "/World/GraphVFXOutput"
    volume: ParticleVolume = field(default_factory=ParticleVolume)
    appearance: ParticleAppearance = field(default_factory=ParticleAppearance)
    speed: float = 1.0
    speed_jitter: float = 0.0
    direction_world: Vector3 = (0.0, 0.0, -1.0)
    wind_world: Vector3 = (0.0, 0.0, 0.0)
    turbulence: float = 0.0
    seed: int = 1
    active: bool = True

    @property
    def control_prim_path(self) -> str:
        return f"{self.root_path}/{self.name}"

    @property
    def graph_path(self) -> str:
        return f"{self.graph_root_path}/{self.name}Graph"

    @property
    def output_prim_path(self) -> str:
        return f"{self.output_root_path}/{self.name}"

    def validate(self) -> None:
        if not self.name:
            raise ValueError("GraphParticleVFXConfig.name cannot be empty.")
        if self.particle_count <= 0:
            raise ValueError("GraphParticleVFXConfig.particle_count must be positive.")
        if not self.camera_prim_path:
            raise ValueError("GraphParticleVFXConfig.camera_prim_path cannot be empty.")
        if self.backend not in ("warp", "particle_system_core2", "custom"):
            raise ValueError(f"Unsupported graph particle backend: {self.backend}")
        if self.speed < 0.0:
            raise ValueError("GraphParticleVFXConfig.speed must be non-negative.")
        if self.speed_jitter < 0.0:
            raise ValueError("GraphParticleVFXConfig.speed_jitter must be non-negative.")
        if self.turbulence < 0.0:
            raise ValueError("GraphParticleVFXConfig.turbulence must be non-negative.")

        self.volume.validate()
        self.appearance.validate()

    def extension_names(self) -> tuple[str, ...]:
        if self.backend == "warp":
            return (
                "omni.graph.core",
                "omni.graph.nodes",
                "omni.warp.core",
                "omni.warp",
            )
        if self.backend == "particle_system_core2":
            return (
                "omni.graph.core",
                "omni.graph.nodes",
                "omni.particle.system.core2",
            )
        return ("omni.graph.core", "omni.graph.nodes")
