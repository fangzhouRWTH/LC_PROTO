from __future__ import annotations

from dataclasses import replace

import numpy as np

from ...isaac_adaptor import isaac_context as iscctx
from .config import (
    CameraView,
    ParticleAppearance,
    ParticleEffectConfig,
    ParticleVolume,
)
from .math_utils import (
    as_vec3,
    camera_basis,
    local_to_world,
    normalize,
    world_vectors_to_local,
)
from .renderers import create_renderer


class ParticleEffect:
    """Base visual particle effect simulated in a camera-local volume."""

    def __init__(self, config: ParticleEffectConfig):
        config.validate()
        self.config = config
        self.prim_path = f"{config.root_path}/{config.name}"
        self.geometry_path = f"{self.prim_path}/Geometry"
        self._rng = np.random.default_rng(config.seed)
        self._renderer = create_renderer(config.renderer)
        self._positions_local = self._random_local_positions(config.particle_count)
        self._speed_scale = self._random_speed_scale(config.particle_count)
        self._active = True
        self._created = False

    @property
    def active(self) -> bool:
        return self._active

    def set_active(self, active: bool, stage=None) -> None:
        self._active = active
        if not self._created and stage is None:
            return
        stage = self._stage(stage)
        prim = stage.GetPrimAtPath(self.prim_path)
        if prim and prim.IsValid():
            prim.SetActive(active)

    def reset(self, seed: int | None = None) -> None:
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        self._positions_local = self._random_local_positions(self.config.particle_count)
        self._speed_scale = self._random_speed_scale(self.config.particle_count)

    def update(
        self,
        dt: float,
        camera_position,
        camera_forward,
        camera_up=(0.0, 0.0, 1.0),
        stage=None,
    ):
        """Advance and render the effect around the supplied camera pose."""

        if not self._active:
            return None

        stage = self._stage(stage)
        self._ensure_created(stage)

        dt = min(max(float(dt), 0.0), self.config.max_dt)
        basis = camera_basis(camera_position, camera_forward, camera_up)
        velocity_world = self._velocity_world()
        velocity_local = world_vectors_to_local(velocity_world, basis)

        self._positions_local += velocity_local * dt
        self._apply_turbulence(dt)
        self._recycle_outside_particles()

        positions_world = local_to_world(
            self._positions_local,
            camera_position,
            basis,
        )
        return self._renderer.render(
            stage,
            self.geometry_path,
            positions_world,
            self.config.appearance,
            self._mean_velocity_world(),
        )

    def update_from_camera_view(self, dt: float, camera_view: CameraView, stage=None):
        return self.update(
            dt,
            camera_position=camera_view.position,
            camera_forward=camera_view.forward,
            camera_up=camera_view.up,
            stage=stage,
        )

    def _stage(self, stage):
        if stage is not None:
            return stage
        stage = iscctx.get_isaac_context().omni_usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("Cannot update particle VFX without an open USD stage.")
        return stage

    def _ensure_created(self, stage) -> None:
        if self._created:
            return

        context = iscctx.get_isaac_context()
        UsdGeom = context.pxr_usd_geom
        Sdf = context.pxr_Sdf

        for path in (self.config.root_path, self.prim_path):
            if not Sdf.Path.IsValidPathString(path):
                raise ValueError(f"Invalid USD prim path: {path}")
            UsdGeom.Xform.Define(stage, path).GetPrim().SetActive(True)

        self._created = True

    def _random_local_positions(self, count: int) -> np.ndarray:
        volume = self.config.volume
        positions = np.empty((count, 3), dtype=np.float32)
        positions[:, 0] = self._rng.uniform(-volume.width * 0.5, volume.width * 0.5, count)
        positions[:, 1] = self._rng.uniform(-volume.height * 0.5, volume.height * 0.5, count)
        positions[:, 2] = self._rng.uniform(
            volume.near_distance,
            volume.near_distance + volume.depth,
            count,
        )
        return positions

    def _random_speed_scale(self, count: int) -> np.ndarray:
        if self.config.speed_jitter <= 0.0:
            return np.ones((count, 1), dtype=np.float32)

        low = max(0.0, 1.0 - self.config.speed_jitter)
        high = 1.0 + self.config.speed_jitter
        return self._rng.uniform(low, high, (count, 1)).astype(np.float32)

    def _direction_world(self) -> np.ndarray:
        direction = as_vec3(self.config.direction_world, "direction_world")
        if float(np.linalg.norm(direction)) <= 1e-6:
            return np.zeros(3, dtype=np.float32)
        return normalize(direction, "direction_world")

    def _velocity_world(self) -> np.ndarray:
        direction = self._direction_world()
        wind = as_vec3(self.config.wind_world, "wind_world")
        velocity = direction[None, :] * float(self.config.speed) * self._speed_scale
        return velocity + wind[None, :]

    def _mean_velocity_world(self) -> np.ndarray:
        return np.mean(self._velocity_world(), axis=0).astype(np.float32)

    def _apply_turbulence(self, dt: float) -> None:
        if self.config.turbulence <= 0.0 or dt <= 0.0:
            return
        offsets = self._rng.normal(
            0.0,
            self.config.turbulence * dt,
            size=(self.config.particle_count, 2),
        ).astype(np.float32)
        self._positions_local[:, 0:2] += offsets

    def _recycle_outside_particles(self) -> None:
        volume = self.config.volume
        x_limit = volume.width * 0.5
        y_limit = volume.height * 0.5
        z_min = volume.near_distance
        z_max = volume.near_distance + volume.depth

        outside = (
            (self._positions_local[:, 0] < -x_limit)
            | (self._positions_local[:, 0] > x_limit)
            | (self._positions_local[:, 1] < -y_limit)
            | (self._positions_local[:, 1] > y_limit)
            | (self._positions_local[:, 2] < z_min)
            | (self._positions_local[:, 2] > z_max)
        )

        count = int(np.count_nonzero(outside))
        if count == 0:
            return

        self._positions_local[outside] = self._random_local_positions(count)
        self._speed_scale[outside] = self._random_speed_scale(count)


class RainParticleEffect(ParticleEffect):
    def __init__(
        self,
        name: str = "Rain",
        particle_count: int = 1400,
        root_path: str = "/World/VFX",
        wind_world=(0.3, 0.0, 0.0),
        seed: int | None = None,
    ):
        config = ParticleEffectConfig(
            name=name,
            particle_count=particle_count,
            root_path=root_path,
            volume=ParticleVolume(width=20.0, height=12.0, depth=30.0, near_distance=1.0),
            appearance=ParticleAppearance(
                color=(0.62, 0.76, 1.0),
                opacity=0.55,
                point_width=0.025,
                streak_length=0.85,
                streak_width=0.012,
            ),
            renderer="streaks",
            speed=10.0,
            speed_jitter=0.25,
            direction_world=(0.0, 0.0, -1.0),
            wind_world=wind_world,
            turbulence=0.06,
            seed=seed,
        )
        super().__init__(config)


class SnowParticleEffect(ParticleEffect):
    def __init__(
        self,
        name: str = "Snow",
        particle_count: int = 900,
        root_path: str = "/World/VFX",
        wind_world=(0.35, 0.1, 0.0),
        seed: int | None = None,
    ):
        config = ParticleEffectConfig(
            name=name,
            particle_count=particle_count,
            root_path=root_path,
            volume=ParticleVolume(width=22.0, height=13.0, depth=26.0, near_distance=0.8),
            appearance=ParticleAppearance(
                color=(0.95, 0.98, 1.0),
                opacity=0.8,
                point_width=0.06,
                streak_length=0.2,
                streak_width=0.03,
            ),
            renderer="points",
            speed=1.6,
            speed_jitter=0.45,
            direction_world=(0.0, 0.0, -1.0),
            wind_world=wind_world,
            turbulence=0.55,
            seed=seed,
        )
        super().__init__(config)


class FogParticleEffect(ParticleEffect):
    def __init__(
        self,
        name: str = "Fog",
        particle_count: int = 520,
        root_path: str = "/World/VFX",
        wind_world=(0.08, 0.03, 0.0),
        seed: int | None = None,
    ):
        config = ParticleEffectConfig(
            name=name,
            particle_count=particle_count,
            root_path=root_path,
            volume=ParticleVolume(width=24.0, height=11.0, depth=22.0, near_distance=1.2),
            appearance=ParticleAppearance(
                color=(0.78, 0.82, 0.84),
                opacity=0.18,
                point_width=0.7,
                streak_length=0.4,
                streak_width=0.15,
            ),
            renderer="points",
            speed=0.08,
            speed_jitter=0.8,
            direction_world=(0.0, 0.0, 0.0),
            wind_world=wind_world,
            turbulence=0.12,
            seed=seed,
        )
        super().__init__(config)


def with_overrides(config: ParticleEffectConfig, **kwargs) -> ParticleEffect:
    """Create a custom particle effect from an existing config plus overrides."""

    return ParticleEffect(replace(config, **kwargs))
