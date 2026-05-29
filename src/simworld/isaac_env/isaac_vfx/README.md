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

## Weather Lighting

Weather lighting is separate from scene import. `SimScene.prepare()` disables
stage-authored lights from imported USDs, then `WeatherLightingManager` owns the
runtime sun, dome sky, fill light, and slow time variation under
`/World/VFX/WeatherLighting`.

```python
from isaac_env.isaac_vfx import WeatherLightingManager

weather = WeatherLightingManager.from_weather(
    "rain",
    sky_texture_path="/path/to/latlong_sky.png",
    sun_intensity=180.0,
    sky_intensity=220.0,
    sky_exposure=0.25,
    time_scale=1.0,
)
weather.apply(stage)
weather.update(dt)
```

The app entrypoint exposes the same controls:

```bash
scripts/run_sim.sh
scripts/run_sim.sh --weather rain
scripts/run_sim.sh --weather sunny --daytime sunset
scripts/run_sim.sh --daytime night
scripts/run_sim.sh --weather sunny --sky-texture /path/to/custom_latlong_sky.png
```

Available presets are `sunny`, `rain`, `overcast`, `foggy`, and `storm`. If
`--weather` is omitted, the app randomly chooses a weather preset at startup. If
`--sky-texture` is omitted, the dome light randomly picks a texture from
`default_asset/sky/<weather>/`; `--daytime` narrows the pick when that weather
has a matching texture, otherwise it falls back to a random texture for the
selected weather. The random path uses system entropy rather than a fixed seed,
so repeated launches can choose different weather/sky combinations. `rain` and
`storm` also enable the rain particle effect in `simulation.py`; other presets
only apply lighting unless additional particle effects are configured.

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
    billboard_opacity_gain=10.0,
    billboard_texture_path="/path/to/custom_fog_alpha.png",
    billboard_shader_path="/path/to/custom_fog_billboard.mdl",
)
```

If no paths are supplied, the renderer uses
`default_asset/fog_billboard_alpha.png` and records
`default_shader/fog_billboard.mdl` on the generated material. The runtime USD
material uses a portable `UsdPreviewSurface` texture network by default, because
MDL texture-coordinate lookup can bypass the USD `st` primvar on generated
billboards in some Isaac/Hydra paths. Normal billboard rendering keeps
`displayOpacity` at 1.0 and lets the texture alpha be the only visible mask,
so the PNG alpha ramp stays continuous instead of turning into a binary cutout.
The material also forces `ior=1.0` and no specular/clearcoat response so RTX
does not treat the fog sheet like refractive glass. `billboard_opacity_gain`
multiplies the effect opacity before it is applied to the texture alpha; lower
it if the outer edge becomes visible, or raise it if the fog is too faint. Set
`billboard_use_mdl_shader=True` only when a tested MDL material is required.
Generated billboard meshes set `primvars:doNotCastShadows=true` and
`rtx:visibility:shadow=false`, and the default PreviewSurface uses emissive
color rather than diffuse lighting so fog does not cast or receive scene shadows.

To verify billboard placement separately from texture/material issues, enable
solid quad debug rendering:

```python
debug_fog = FogParticleEffect(
    mode="near",
    renderer="billboard",
    billboard_debug=True,
)
```

Debug mode skips material binding and renders orange camera-facing square panels,
which is useful for checking whether update/camera-space placement is working.

For sensor work that must model true volumetric attenuation in depth, lidar, or
radar, use these billboard particles only as the visible RGB layer and pair them
with a depth/range-domain fog model, or move the effect to a graph-backed
volumetric implementation.

For custom effects, create a `ParticleEffectConfig` with `effect_type="particle"`
and pass it to `ParticleEffect`.
