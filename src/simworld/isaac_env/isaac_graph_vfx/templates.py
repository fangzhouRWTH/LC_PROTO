from __future__ import annotations

from .config import GraphParticleVFXConfig
from .graph_builder import GraphNodeSpec, GraphTemplate


DEFAULT_CORE2_NODE_TYPES = {
    "particle_system": "omni.particle.system.core2.ParticleSystem",
    "emitter": "omni.particle.system.core2.Emitter",
    "display": "omni.particle.system.core2.SetDisplayAttributes",
    "to_points": "omni.particle.system.core2.ParticlesToPoints",
}


def make_warp_particle_template(
    config: GraphParticleVFXConfig,
    node_types: dict[str, str] | None = None,
) -> GraphTemplate:
    """Create the default Warp graph template for particle VFX.

    This default is intentionally control-only. It enables OmniGraph/Warp and
    creates the USD control prim through ``GraphParticleEffect.build()``, but it
    does not assume that the install has the optional Omniverse particle-system
    node library. Pass an explicit ``GraphTemplate`` for a version-specific Warp
    graph that connects kernels to renderable output.
    """

    del node_types
    return GraphTemplate(
        graph_path=config.graph_path,
        required_extensions=config.extension_names(),
    )


def make_particle_system_core2_template(
    config: GraphParticleVFXConfig,
    node_types: dict[str, str] | None = None,
) -> GraphTemplate:
    """Create a built-in particle-system graph skeleton."""

    types = {**DEFAULT_CORE2_NODE_TYPES, **(node_types or {})}
    return GraphTemplate(
        graph_path=config.graph_path,
        required_extensions=config.extension_names(),
        nodes=(
            GraphNodeSpec(
                "ParticleSystem",
                types["particle_system"],
                {
                    "inputs:active": config.active,
                    "inputs:maxparticles": int(config.particle_count),
                    "inputs:seed": int(config.seed),
                },
            ),
            GraphNodeSpec(
                "Emitter",
                types["emitter"],
                {
                    "inputs:rate": float(config.particle_count),
                    "inputs:speedMin": float(config.speed),
                    "inputs:speedMax": float(config.speed * (1.0 + config.speed_jitter)),
                },
            ),
            GraphNodeSpec(
                "Display",
                types["display"],
                {
                    "inputs:color": config.appearance.color,
                    "inputs:opacity": float(config.appearance.opacity),
                },
            ),
            GraphNodeSpec("ParticlesToPoints", types["to_points"]),
        ),
    )


def make_graph_template(
    config: GraphParticleVFXConfig,
    node_types: dict[str, str] | None = None,
) -> GraphTemplate:
    if config.backend == "warp":
        return make_warp_particle_template(config, node_types=node_types)
    if config.backend == "particle_system_core2":
        return make_particle_system_core2_template(config, node_types=node_types)
    return GraphTemplate(
        graph_path=config.graph_path,
        required_extensions=config.extension_names(),
    )
