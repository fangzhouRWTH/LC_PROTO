# Isaac VFX

`isaac_vfx` holds runtime-only visual effects for Isaac Sim. The first module is
`particle`, used for camera-local rain, snow, fog, and later particle-style
effects.

The particle effects only use USD visual primitives through `isaac_context`.
They do not create physics bodies, collision shapes, or global particle
simulation state. Each update receives the camera pose and keeps particles inside
a small box in front of that viewport.

Example:

```python
from isaac_env.isaac_vfx.particle import (
    CameraView,
    ParticleEffectManager,
    RainParticleEffect,
    SnowParticleEffect,
)

vfx = ParticleEffectManager(
    [
        RainParticleEffect(seed=1),
        SnowParticleEffect(name="LightSnow", particle_count=300, seed=2),
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

For custom effects, create a `ParticleEffectConfig` with `effect_type="particle"`
and pass it to `ParticleEffect`.
