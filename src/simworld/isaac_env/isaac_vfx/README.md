# Isaac VFX

`isaac_vfx` holds runtime-only visual effects for Isaac Sim. The first module is
`particle`, used for camera-local rain, snow, fog, and later particle-style
effects.

The particle effects only use USD visual primitives through `isaac_context`.
They do not create physics bodies, collision shapes, or full-scene particle
simulation state. Particle positions are stored in world coordinates, while each
update receives the camera pose and uses a small box in front of that viewport
only as a recycling range. Particles that leave the range are wrapped to the
opposite side of the box, so camera movement reads as motion through the effect
instead of dragging the particles with the camera.

Example:

```python
from isaac_env.isaac_vfx.particle import (
    CameraView,
    FogParticleEffect,
    ParticleEffectManager,
    RainParticleEffect,
    SnowParticleEffect,
)

vfx = ParticleEffectManager(
    [
        RainParticleEffect(seed=1),
        SnowParticleEffect(name="LightSnow", particle_count=300, seed=2),
        FogParticleEffect(name="DistantFog", mode="distant", seed=3),
    ]
)

# In the simulation loop:
camera = CameraView.from_look_at(
    position=eye,
    target=target,
    up=(0.0, 0.0, 1.0),
)
vfx.update_from_camera_view(dt, camera)
```

The Python particle backend can repeat one simulated tile across the viewport
box. For example, `partition_width_segments=4` and
`partition_height_segments=4` renders the requested particle count while only
simulating roughly one sixteenth of the particles:

```python
rain = RainParticleEffect(
    particle_count=1600,
    partition_width_segments=4,
    partition_height_segments=4,
)
print(rain.simulated_particle_count)  # 100
print(rain.rendered_particle_count)  # 1600
```

This reduces NumPy-side motion, turbulence, and wrapping work. It does not remove
the cost of expanding and writing all visible particles to USD each frame.

Wind can be modulated for visual weather dynamics. The main `wind_world` vector
sets the average direction and speed; the variation rotates that vector around
world Z within the configured angle range:

```python
rain = RainParticleEffect(
    wind_world=(0.3, 4.0, 0.0),
    wind_variation_angle_degrees=18.0,
    wind_variation_period_seconds=9.0,
    wind_variation_randomness=0.35,
)
```

The variation is low-frequency and deterministic for a fixed seed, so it adds
movement without per-frame hard jitter.

Fog has two built-in camera-space modes:

```python
distant_fog = FogParticleEffect(mode="distant", seed=3)
near_fog = FogParticleEffect(mode="near", density=0.8, seed=4)
textured_far_fog = FogParticleEffect(mode="distant", renderer="billboard", seed=5)
```

`mode="distant"` renders large, sparse, tiled point particles in the far camera
volume. It is the low-cost option for background haze and keeps NumPy-side work
small through the same partitioning strategy used by rain. `mode="near"` renders
more unique, smaller particles with per-particle width, opacity, height fade,
depth fade, and smooth swirl for closer camera views. Near fog defaults to the
`billboard` renderer; distant fog defaults to `points` but can opt into
`renderer="billboard"` when the added quad/texture cost is acceptable.

Billboard fog uses a camera-facing quad mesh and the default assets under
`isaac_env/default_asset` and `isaac_env/default_shader`:

```python
fog = FogParticleEffect(
    mode="near",
    renderer="billboard",
    billboard_texture_path="/path/to/custom_fog_alpha.png",
    billboard_shader_path="/path/to/custom_fog_billboard.mdl",
)
```

If no paths are supplied, the renderer uses
`default_asset/fog_billboard_alpha.png` and records
`default_shader/fog_billboard.mdl` on the generated material. The runtime USD
material also authors a portable `UsdPreviewSurface` texture network, so it can
render even when an MDL render context is unavailable.

For sensor work that must model true volumetric attenuation in depth, lidar, or
radar, use these billboard particles only as the visible RGB layer and pair them
with a depth/range-domain fog model, or move the effect to a graph-backed
volumetric implementation.

For custom effects, create a `ParticleEffectConfig` with `effect_type="particle"`
and pass it to `ParticleEffect`.
