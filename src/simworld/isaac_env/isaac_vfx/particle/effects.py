from __future__ import annotations

from dataclasses import replace

import numpy as np

from ...isaac_adaptor import isaac_context as iscctx
from .config import (
    CameraView,
    ParticleAppearance,
    ParticleEffectConfig,
    ParticlePartition,
    ParticleVolume,
    ParticleWindVariation,
)
from .math_utils import (
    as_vec3,
    camera_basis,
    local_to_world,
    normalize,
    world_to_local,
)
from .renderers import create_renderer


class ParticleEffect:
    """Base visual particle effect stored in world space near the viewport."""

    def __init__(self, config: ParticleEffectConfig):
        config.validate()
        self.config = config
        self.prim_path = f"{config.root_path}/{config.name}"
        self.geometry_path = f"{self.prim_path}/Geometry"
        self._rng = np.random.default_rng(config.seed)
        self._renderer = create_renderer(config.renderer)
        self._positions_world: np.ndarray | None = None
        self._base_particle_count = config.partition.base_particle_count(
            config.particle_count
        )
        self._speed_scale = self._random_speed_scale(self._base_particle_count)
        self._time = 0.0
        self._wind_variation_phases = np.zeros(3, dtype=np.float32)
        self._reset_wind_variation_state()
        self._active = True
        self._created = False

    @property
    def active(self) -> bool:
        return self._active

    @property
    def simulated_particle_count(self) -> int:
        return self._base_particle_count

    @property
    def rendered_particle_count(self) -> int:
        return self.config.particle_count

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
        self._positions_world = None
        self._speed_scale = self._random_speed_scale(self._base_particle_count)
        self._time = 0.0
        self._reset_wind_variation_state()

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
        self._time += dt
        basis = camera_basis(camera_position, camera_forward, camera_up)
        velocity_world = self._velocity_world()

        self._ensure_world_positions(camera_position, basis)
        self._positions_world += velocity_world * dt
        self._apply_turbulence(dt)
        self._wrap_outside_particles(camera_position, basis)
        positions_world = self._render_positions_world(basis)
        widths, opacities = self._render_attributes(
            camera_position,
            basis,
            positions_world,
        )

        return self._renderer.render(
            stage,
            self.geometry_path,
            positions_world,
            self.config.appearance,
            self._mean_velocity_world(),
            widths=widths,
            opacities=opacities,
            camera_basis=basis,
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

    def _local_bounds(self) -> tuple[np.ndarray, np.ndarray]:
        volume = self.config.volume
        partition = self.config.partition
        mins = np.array(
            (
                -volume.width * 0.5,
                -volume.height * 0.5,
                volume.near_distance,
            ),
            dtype=np.float32,
        )
        spans = np.array(
            (
                volume.width / partition.width_segments,
                volume.height / partition.height_segments,
                volume.depth,
            ),
            dtype=np.float32,
        )
        return mins, spans

    def _random_local_positions(self, count: int) -> np.ndarray:
        mins, spans = self._local_bounds()
        positions = np.empty((count, 3), dtype=np.float32)
        positions[:, 0] = self._rng.uniform(mins[0], mins[0] + spans[0], count)
        positions[:, 1] = self._rng.uniform(mins[1], mins[1] + spans[1], count)
        positions[:, 2] = self._rng.uniform(mins[2], mins[2] + spans[2], count)
        return positions

    def _random_speed_scale(self, count: int) -> np.ndarray:
        if self.config.speed_jitter <= 0.0:
            return np.ones((count, 1), dtype=np.float32)

        low = max(0.0, 1.0 - self.config.speed_jitter)
        high = 1.0 + self.config.speed_jitter
        return self._rng.uniform(low, high, (count, 1)).astype(np.float32)

    def _reset_wind_variation_state(self) -> None:
        if not self.config.wind_variation.enabled:
            self._wind_variation_phases = np.zeros(3, dtype=np.float32)
            return

        self._wind_variation_phases = self._rng.uniform(
            0.0,
            2.0 * np.pi,
            3,
        ).astype(np.float32)

    def _direction_world(self) -> np.ndarray:
        direction = as_vec3(self.config.direction_world, "direction_world")
        if float(np.linalg.norm(direction)) <= 1e-6:
            return np.zeros(3, dtype=np.float32)
        return normalize(direction, "direction_world")

    def _velocity_world(self) -> np.ndarray:
        direction = self._direction_world()
        wind = self._wind_world()
        velocity = direction[None, :] * float(self.config.speed) * self._speed_scale
        return velocity + wind[None, :]

    def _mean_velocity_world(self) -> np.ndarray:
        return np.mean(self._velocity_world(), axis=0).astype(np.float32)

    def _wind_world(self) -> np.ndarray:
        wind = as_vec3(self.config.wind_world, "wind_world")
        variation = self.config.wind_variation
        if not variation.enabled:
            return wind

        horizontal = wind[:2]
        horizontal_speed = float(np.linalg.norm(horizontal))
        if horizontal_speed <= 1e-6:
            return wind

        phase = 2.0 * np.pi * self._time / variation.period_seconds
        random_strength = float(variation.randomness)
        periodic = np.sin(phase + float(self._wind_variation_phases[0]))
        random_wobble = 0.55 * np.sin(
            phase * 0.63 + float(self._wind_variation_phases[1])
        ) + 0.35 * np.sin(phase * 1.37 + float(self._wind_variation_phases[2]))
        normalized = periodic * (1.0 - min(random_strength, 1.0) * 0.35)
        normalized += random_wobble * random_strength * 0.45
        normalized = float(np.clip(normalized, -1.0, 1.0))

        angle = np.deg2rad(float(variation.angle_degrees) * normalized)
        cos_angle = float(np.cos(angle))
        sin_angle = float(np.sin(angle))
        rotated = np.array(
            (
                horizontal[0] * cos_angle - horizontal[1] * sin_angle,
                horizontal[0] * sin_angle + horizontal[1] * cos_angle,
            ),
            dtype=np.float32,
        )

        return np.array(
            (
                rotated[0],
                rotated[1],
                wind[2],
            ),
            dtype=np.float32,
        )

    def _ensure_world_positions(self, camera_position, basis) -> None:
        if self._positions_world is not None:
            return
        self._positions_world = local_to_world(
            self._random_local_positions(self._base_particle_count),
            camera_position,
            basis,
        ).astype(np.float32)

    def _apply_turbulence(self, dt: float) -> None:
        if self._positions_world is None or self.config.turbulence <= 0.0 or dt <= 0.0:
            return
        offsets = self._rng.normal(
            0.0,
            self.config.turbulence * dt,
            size=(self._base_particle_count, 2),
        ).astype(np.float32)
        self._positions_world[:, 0:2] += offsets

    def _wrap_outside_particles(self, camera_position, basis) -> None:
        if self._positions_world is None:
            return

        mins, spans = self._local_bounds()
        maxs = mins + spans
        positions_local = world_to_local(self._positions_world, camera_position, basis)

        outside = (
            (positions_local[:, 0] < mins[0])
            | (positions_local[:, 0] > maxs[0])
            | (positions_local[:, 1] < mins[1])
            | (positions_local[:, 1] > maxs[1])
            | (positions_local[:, 2] < mins[2])
            | (positions_local[:, 2] > maxs[2])
        )

        count = int(np.count_nonzero(outside))
        if count == 0:
            return

        positions_local[outside] = (
            (positions_local[outside] - mins[None, :]) % spans[None, :]
        ) + mins[None, :]
        self._positions_world[outside] = local_to_world(
            positions_local[outside],
            camera_position,
            basis,
        )
        self._speed_scale[outside] = self._random_speed_scale(count)
        self._on_particles_recycled(outside, count)

    def _on_particles_recycled(self, outside: np.ndarray, count: int) -> None:
        del outside, count

    def _tile_offsets_world(self, basis) -> np.ndarray:
        partition = self.config.partition
        if partition.tile_count == 1:
            return np.zeros((1, 3), dtype=np.float32)

        _, spans = self._local_bounds()
        x_offsets = np.arange(partition.width_segments, dtype=np.float32) * spans[0]
        y_offsets = np.arange(partition.height_segments, dtype=np.float32) * spans[1]
        xx, yy = np.meshgrid(x_offsets, y_offsets, indexing="xy")
        local_offsets = np.stack(
            (
                xx.reshape(-1),
                yy.reshape(-1),
                np.zeros(partition.tile_count, dtype=np.float32),
            ),
            axis=1,
        )
        return local_offsets @ basis

    def _render_positions_world(self, basis) -> np.ndarray:
        if self._positions_world is None:
            raise RuntimeError("Particle positions must be initialized before render.")

        if self.config.partition.tile_count == 1:
            return self._positions_world

        offsets_world = self._tile_offsets_world(basis)
        positions = (
            self._positions_world[:, None, :] + offsets_world[None, :, :]
        ).reshape(-1, 3)
        return positions[: self.config.particle_count].astype(np.float32, copy=False)

    def _render_attributes(
        self,
        camera_position,
        basis,
        positions_world: np.ndarray,
    ) -> tuple[np.ndarray | None, np.ndarray | None]:
        del camera_position, basis, positions_world
        return None, None


class RainParticleEffect(ParticleEffect):
    def __init__(
        self,
        name: str = "Rain",
        particle_count: int = 1000,
        root_path: str = "/World/VFX",
        wind_world=(0.3, 1.0, 0.0),
        seed: int | None = None,
        partition_width_segments: int = 1,
        partition_height_segments: int = 1,
        wind_variation_angle_degrees: float = 0.0,
        wind_variation_period_seconds: float = 8.0,
        wind_variation_randomness: float = 0.25,
    ):
        config = ParticleEffectConfig(
            name=name,
            particle_count=particle_count,
            root_path=root_path,
            partition=ParticlePartition(
                width_segments=partition_width_segments,
                height_segments=partition_height_segments,
            ),
            volume=ParticleVolume(
                width=20.0, height=12.0, depth=30.0, near_distance=1.0
            ),
            appearance=ParticleAppearance(
                color=(0.62, 0.76, 1.0),
                opacity=0.01,
                point_width=0.025,
                streak_length=0.45,
                streak_width=0.010,
            ),
            renderer="streaks",
            speed=8.1,
            speed_jitter=0.35,
            direction_world=(0.0, 0.0, -1.0),
            wind_world=wind_world,
            wind_variation=ParticleWindVariation(
                angle_degrees=wind_variation_angle_degrees,
                period_seconds=wind_variation_period_seconds,
                randomness=wind_variation_randomness,
            ),
            turbulence=0.10,
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
        partition_width_segments: int = 1,
        partition_height_segments: int = 1,
        wind_variation_angle_degrees: float = 0.0,
        wind_variation_period_seconds: float = 10.0,
        wind_variation_randomness: float = 0.35,
    ):
        config = ParticleEffectConfig(
            name=name,
            particle_count=particle_count,
            root_path=root_path,
            partition=ParticlePartition(
                width_segments=partition_width_segments,
                height_segments=partition_height_segments,
            ),
            volume=ParticleVolume(
                width=22.0, height=13.0, depth=26.0, near_distance=0.8
            ),
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
            wind_variation=ParticleWindVariation(
                angle_degrees=wind_variation_angle_degrees,
                period_seconds=wind_variation_period_seconds,
                randomness=wind_variation_randomness,
            ),
            turbulence=0.55,
            seed=seed,
        )
        super().__init__(config)


class FogParticleEffect(ParticleEffect):
    """Camera-local fog built from soft USD point particles.

    ``mode="distant"`` uses large, sparse particles tiled across the camera
    volume for low-cost background haze. ``mode="near"`` uses more unique,
    smaller particles with stronger per-particle variation for close inspection.
    """

    _MODE_ALIASES = {
        "distant": "distant",
        "far": "distant",
        "low": "distant",
        "near": "near",
        "fine": "near",
        "detailed": "near",
    }

    def __init__(
        self,
        name: str = "Fog",
        particle_count: int | None = None,
        root_path: str = "/World/VFX",
        wind_world=(0.08, 0.03, 0.0),
        seed: int | None = None,
        partition_width_segments: int | None = None,
        partition_height_segments: int | None = None,
        wind_variation_angle_degrees: float = 0.0,
        wind_variation_period_seconds: float | None = None,
        wind_variation_randomness: float | None = None,
        mode: str = "distant",
        density: float = 1.0,
        renderer: str | None = None,
        billboard_texture_path: str | None = None,
        billboard_shader_path: str | None = None,
    ):
        self.mode = self._normalize_mode(mode)
        self.density = float(density)
        if self.density <= 0.0:
            raise ValueError("FogParticleEffect.density must be positive.")

        preset = self._mode_preset(self.mode)
        if particle_count is None:
            particle_count = preset["particle_count"]
        if partition_width_segments is None:
            partition_width_segments = preset["partition_width_segments"]
        if partition_height_segments is None:
            partition_height_segments = preset["partition_height_segments"]
        if wind_variation_period_seconds is None:
            wind_variation_period_seconds = preset["wind_variation_period_seconds"]
        if wind_variation_randomness is None:
            wind_variation_randomness = preset["wind_variation_randomness"]
        if renderer is None:
            renderer = preset["renderer"]

        self._fog_near_fade_distance = preset["near_fade_distance"]
        self._fog_far_fade_distance = preset["far_fade_distance"]
        self._fog_depth_size_gain = preset["depth_size_gain"]
        self._fog_height_softness = preset["height_softness"]
        self._fog_max_opacity = preset["max_opacity"]

        config = ParticleEffectConfig(
            name=name,
            particle_count=particle_count,
            root_path=root_path,
            partition=ParticlePartition(
                width_segments=partition_width_segments,
                height_segments=partition_height_segments,
            ),
            volume=preset["volume"],
            appearance=replace(
                preset["appearance"],
                opacity=min(1.0, preset["appearance"].opacity * self.density),
                billboard_texture_path=billboard_texture_path,
                billboard_shader_path=billboard_shader_path,
            ),
            renderer=renderer,
            speed=preset["speed"],
            speed_jitter=preset["speed_jitter"],
            direction_world=(0.0, 0.0, 0.0),
            wind_world=wind_world,
            wind_variation=ParticleWindVariation(
                angle_degrees=wind_variation_angle_degrees,
                period_seconds=wind_variation_period_seconds,
                randomness=wind_variation_randomness,
            ),
            turbulence=preset["turbulence"],
            seed=seed,
        )
        super().__init__(config)
        self._reset_fog_particle_state()

    @classmethod
    def _normalize_mode(cls, mode: str) -> str:
        normalized = cls._MODE_ALIASES.get(mode.lower())
        if normalized is None:
            valid = ", ".join(sorted(cls._MODE_ALIASES))
            raise ValueError(
                f"Unsupported fog mode {mode!r}. Expected one of: {valid}."
            )
        return normalized

    @staticmethod
    def _mode_preset(mode: str) -> dict[str, object]:
        if mode == "distant":
            return {
                "particle_count": 720,
                "partition_width_segments": 4,
                "partition_height_segments": 2,
                "renderer": "points",
                "volume": ParticleVolume(
                    width=34.0,
                    height=12.0,
                    depth=58.0,
                    near_distance=7.5,
                ),
                "appearance": ParticleAppearance(
                    color=(0.76, 0.80, 0.82),
                    opacity=0.055,
                    point_width=1.9,
                    streak_length=0.4,
                    streak_width=0.15,
                ),
                "speed": 0.035,
                "speed_jitter": 0.55,
                "turbulence": 0.035,
                "wind_variation_period_seconds": 38.0,
                "wind_variation_randomness": 0.35,
                "near_fade_distance": 12.0,
                "far_fade_distance": 18.0,
                "depth_size_gain": 0.85,
                "height_softness": 0.42,
                "max_opacity": 0.12,
            }

        return {
            "particle_count": 1500,
            "partition_width_segments": 1,
            "partition_height_segments": 1,
            "renderer": "billboard",
            "volume": ParticleVolume(
                width=20.0,
                height=9.0,
                depth=24.0,
                near_distance=0.7,
            ),
            "appearance": ParticleAppearance(
                color=(0.80, 0.83, 0.84),
                opacity=0.075,
                point_width=0.42,
                streak_length=0.25,
                streak_width=0.08,
            ),
            "speed": 0.065,
            "speed_jitter": 0.85,
            "turbulence": 0.16,
            "wind_variation_period_seconds": 18.0,
            "wind_variation_randomness": 0.5,
            "near_fade_distance": 2.8,
            "far_fade_distance": 7.5,
            "depth_size_gain": 0.35,
            "height_softness": 0.52,
            "max_opacity": 0.16,
        }

    def reset(self, seed: int | None = None) -> None:
        super().reset(seed=seed)
        self._reset_fog_particle_state()

    def _reset_fog_particle_state(self) -> None:
        count = self._base_particle_count
        self._fog_size_scale = self._random_fog_size_scale(count)
        self._fog_opacity_scale = self._random_fog_opacity_scale(count)
        self._fog_swirl_phase = self._rng.uniform(
            0.0,
            2.0 * np.pi,
            (count, 3),
        ).astype(np.float32)
        self._fog_swirl_speed = self._rng.uniform(0.45, 1.25, (count, 1)).astype(
            np.float32
        )

    def _random_fog_size_scale(self, count: int) -> np.ndarray:
        if self.mode == "distant":
            return self._rng.uniform(0.72, 1.85, count).astype(np.float32)
        return self._rng.uniform(0.55, 1.35, count).astype(np.float32)

    def _random_fog_opacity_scale(self, count: int) -> np.ndarray:
        if self.mode == "distant":
            return self._rng.uniform(0.45, 1.15, count).astype(np.float32)
        return self._rng.uniform(0.35, 1.3, count).astype(np.float32)

    def _random_local_positions(self, count: int) -> np.ndarray:
        positions = super()._random_local_positions(count)
        mins, spans = self._local_bounds()
        height = self.config.volume.height

        if self.mode == "distant":
            y = self._rng.normal(-height * 0.04, height * 0.26, count)
            z01 = self._rng.power(1.85, count)
        else:
            y = self._rng.normal(-height * 0.12, height * 0.34, count)
            near_wisps = self._rng.random(count) < 0.38
            z01 = np.where(
                near_wisps,
                self._rng.power(0.75, count),
                self._rng.power(1.25, count),
            )

        positions[:, 1] = np.clip(y, mins[1], mins[1] + spans[1])
        positions[:, 2] = mins[2] + spans[2] * z01
        return positions.astype(np.float32, copy=False)

    def _apply_turbulence(self, dt: float) -> None:
        if (
            self._positions_world is None
            or self.config.turbulence <= 0.0
            or dt <= 0.0
        ):
            return

        if len(self._fog_swirl_phase) != self._base_particle_count:
            self._reset_fog_particle_state()

        phase = self._fog_swirl_phase
        t = self._time * self._fog_swirl_speed[:, 0]
        swirl = np.stack(
            (
                np.sin(t + phase[:, 0]),
                0.65 * np.cos(t * 0.73 + phase[:, 1]),
                0.22 * np.sin(t * 0.41 + phase[:, 2]),
            ),
            axis=1,
        ).astype(np.float32)
        self._positions_world += swirl * float(self.config.turbulence) * dt

    def _on_particles_recycled(self, outside: np.ndarray, count: int) -> None:
        self._fog_size_scale[outside] = self._random_fog_size_scale(count)
        self._fog_opacity_scale[outside] = self._random_fog_opacity_scale(count)
        self._fog_swirl_phase[outside] = self._rng.uniform(
            0.0,
            2.0 * np.pi,
            (count, 3),
        ).astype(np.float32)
        self._fog_swirl_speed[outside] = self._rng.uniform(
            0.45,
            1.25,
            (count, 1),
        ).astype(np.float32)

    def _expanded_fog_values(self, values: np.ndarray) -> np.ndarray:
        if self.config.partition.tile_count == 1:
            return values[: self.config.particle_count]

        expanded = np.repeat(values, self.config.partition.tile_count, axis=0)
        return expanded[: self.config.particle_count]

    def _render_attributes(
        self,
        camera_position,
        basis,
        positions_world: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        positions_local = world_to_local(positions_world, camera_position, basis)
        volume = self.config.volume
        near = float(volume.near_distance)
        far = near + float(volume.depth)
        z = np.clip(positions_local[:, 2], near, far)
        depth01 = (z - near) / max(float(volume.depth), 1e-6)

        near_fade = np.clip(
            (z - near) / max(float(self._fog_near_fade_distance), 1e-6),
            0.0,
            1.0,
        )
        far_fade = np.clip(
            (far - z) / max(float(self._fog_far_fade_distance), 1e-6),
            0.0,
            1.0,
        )
        vertical01 = np.abs(positions_local[:, 1]) / max(
            float(volume.height) * 0.5,
            1e-6,
        )
        height_fade = np.clip(
            1.08 - float(self._fog_height_softness) * np.power(vertical01, 1.35),
            0.18,
            1.08,
        )

        size_scale = self._expanded_fog_values(self._fog_size_scale)
        opacity_scale = self._expanded_fog_values(self._fog_opacity_scale)

        widths = (
            float(self.config.appearance.point_width)
            * size_scale
            * (1.0 + float(self._fog_depth_size_gain) * depth01)
        )
        opacities = (
            float(self.config.appearance.opacity)
            * opacity_scale
            * near_fade
            * far_fade
            * height_fade
        )
        opacities = np.clip(opacities, 0.0, float(self._fog_max_opacity))
        return widths.astype(np.float32), opacities.astype(np.float32)


def with_overrides(config: ParticleEffectConfig, **kwargs) -> ParticleEffect:
    """Create a custom particle effect from an existing config plus overrides."""

    return ParticleEffect(replace(config, **kwargs))
