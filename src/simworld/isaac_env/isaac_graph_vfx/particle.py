from __future__ import annotations

from ..isaac_vfx.particle.config import ParticleAppearance, ParticleVolume
from .config import GraphParticleVFXConfig, GraphVFXRuntimeState
from .control_prim import GraphVFXControlPrim
from .graph_builder import GraphTemplate, GraphVFXBuilder
from .templates import make_graph_template


class GraphParticleEffect:
    """Script-level handle for graph-backed particle VFX."""

    def __init__(
        self,
        config: GraphParticleVFXConfig,
        graph_template: GraphTemplate | None = None,
        node_types: dict[str, str] | None = None,
        builder: GraphVFXBuilder | None = None,
    ):
        config.validate()
        self.config = config
        self.control_prim = GraphVFXControlPrim(config)
        self.graph_template = graph_template or make_graph_template(
            config,
            node_types=node_types,
        )
        self.builder = builder or GraphVFXBuilder()
        self._built = False

    @property
    def built(self) -> bool:
        return self._built

    def build(self, stage=None):
        self.control_prim.ensure(stage=stage)
        self.builder.build(self.graph_template)
        self._built = True
        return self

    def update_runtime_state(
        self,
        dt: float,
        camera_position,
        camera_forward,
        camera_up=(0.0, 0.0, 1.0),
        stage=None,
    ):
        state = GraphVFXRuntimeState(
            dt=float(dt),
            camera_position=tuple(float(v) for v in camera_position),
            camera_forward=tuple(float(v) for v in camera_forward),
            camera_up=tuple(float(v) for v in camera_up),
        )
        return self.control_prim.write_runtime_state(state, stage=stage)

    def update_from_camera_view(self, dt: float, camera_view, stage=None):
        return self.update_runtime_state(
            dt,
            camera_position=camera_view.position,
            camera_forward=camera_view.forward,
            camera_up=camera_view.up,
            stage=stage,
        )


class RainGraphParticleEffect(GraphParticleEffect):
    def __init__(
        self,
        camera_prim_path: str,
        name: str = "Rain",
        particle_count: int = 6000,
        backend="warp",
        seed: int = 1,
    ):
        super().__init__(
            GraphParticleVFXConfig(
                name=name,
                particle_count=particle_count,
                camera_prim_path=camera_prim_path,
                backend=backend,
                volume=ParticleVolume(
                    width=22.0,
                    height=13.0,
                    depth=34.0,
                    near_distance=1.0,
                ),
                appearance=ParticleAppearance(
                    color=(0.62, 0.76, 1.0),
                    opacity=0.55,
                    point_width=0.025,
                    streak_length=0.85,
                    streak_width=0.012,
                ),
                speed=10.0,
                speed_jitter=0.25,
                direction_world=(0.0, 0.0, -1.0),
                wind_world=(0.3, 0.0, 0.0),
                turbulence=0.06,
                seed=seed,
            )
        )


class SnowGraphParticleEffect(GraphParticleEffect):
    def __init__(
        self,
        camera_prim_path: str,
        name: str = "Snow",
        particle_count: int = 3500,
        backend="warp",
        seed: int = 2,
    ):
        super().__init__(
            GraphParticleVFXConfig(
                name=name,
                particle_count=particle_count,
                camera_prim_path=camera_prim_path,
                backend=backend,
                volume=ParticleVolume(
                    width=24.0,
                    height=14.0,
                    depth=28.0,
                    near_distance=0.8,
                ),
                appearance=ParticleAppearance(
                    color=(0.95, 0.98, 1.0),
                    opacity=0.8,
                    point_width=0.06,
                    streak_length=0.2,
                    streak_width=0.03,
                ),
                speed=1.6,
                speed_jitter=0.45,
                direction_world=(0.0, 0.0, -1.0),
                wind_world=(0.35, 0.1, 0.0),
                turbulence=0.55,
                seed=seed,
            )
        )


class FogGraphParticleEffect(GraphParticleEffect):
    def __init__(
        self,
        camera_prim_path: str,
        name: str = "Fog",
        particle_count: int = 1500,
        backend="warp",
        seed: int = 3,
    ):
        super().__init__(
            GraphParticleVFXConfig(
                name=name,
                particle_count=particle_count,
                camera_prim_path=camera_prim_path,
                backend=backend,
                volume=ParticleVolume(
                    width=26.0,
                    height=12.0,
                    depth=24.0,
                    near_distance=1.2,
                ),
                appearance=ParticleAppearance(
                    color=(0.78, 0.82, 0.84),
                    opacity=0.18,
                    point_width=0.7,
                    streak_length=0.4,
                    streak_width=0.15,
                ),
                speed=0.08,
                speed_jitter=0.8,
                direction_world=(0.0, 0.0, 0.0),
                wind_world=(0.08, 0.03, 0.0),
                turbulence=0.12,
                seed=seed,
            )
        )

