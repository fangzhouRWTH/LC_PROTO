# Isaac Graph VFX

`isaac_graph_vfx` is the graph-backed VFX layer. It keeps Python at the
orchestration boundary: scripts create control prims, enable graph extensions,
build OmniGraph skeletons, and update only small runtime parameters such as
camera pose and frame `dt`.

Particle position updates should run inside OmniGraph/Warp or an available
Omniverse particle-system node library, not in Python. The package includes:

- `GraphParticleVFXConfig`: shared particle parameters and graph paths.
- `GraphVFXControlPrim`: USD attributes used as the script-to-graph bridge.
- `GraphVFXBuilder`: small wrapper around `omni.graph.core.Controller`.
- `GraphParticleEffect`: base handle for build/update lifecycle.
- Rain, snow, and fog presets.

Example:

```python
from isaac_env.isaac_graph_vfx import GraphVFXManager, RainGraphParticleEffect

graph_vfx = GraphVFXManager(
    [
        RainGraphParticleEffect(camera_prim_path="/OmniverseKit_Persp"),
    ]
)
graph_vfx.build_all()

# Per frame: only update camera parameters for the graph.
graph_vfx.update_from_camera_view(dt, camera_view)
```

The default `warp` backend is control-only: it creates the USD control prim and
enables OmniGraph/Warp, but it does not assume `omni.particle.system.core2` is
installed. Some Isaac/Kit builds do not ship that extension. Pass a custom
`GraphTemplate` when binding this framework to the specific graph nodes available
in the installed version.

Use `backend="particle_system_core2"` only in environments where the extension
manager can resolve `omni.particle.system.core2`.
