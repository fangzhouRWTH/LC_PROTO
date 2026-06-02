# LC_01 SimWorld

LC_01 SimWorld is an NVIDIA Isaac Sim based simulation project for urban and campus-scale environments. The codebase has moved from early validation scripts into a modular runtime under `src/simworld`. The current pipeline can open USD scenes, parse scene semantics from naming rules, generate static asset layouts inside placeholder regions, import referenced USD assets, configure weather and lighting, spawn dynamic placeholder actors, attach pseudo sensors to the robot, and run an interactive Spot demo.

## Documentation

- [Architecture](doc/Architecture.md): describes the current module boundaries, runtime path, data contracts, and next integration steps.
- [Dynamic Agents](doc/DynamicAgents.md): describes dynamic pedestrian and vehicle placeholders, planning, runtime backends, and configuration.
- [Isaac Sensor Sim](src/simworld/isaac_env/isaac_sensor_sim/README.md): describes robot-decoupled pseudo sensors, sensor rigs, viewport switching, depth visualization, and future visual sensor modules.
- [Isaac VFX](src/simworld/isaac_env/isaac_vfx/README.md): describes weather lighting and camera-local particle effects.
- [Isaac Graph VFX](src/simworld/isaac_env/isaac_graph_vfx/README.md): describes the graph-backed VFX scaffold.

## Current Framework

The main runtime path is:

```text
scripts/run_sim.sh
  -> src/simworld/main.py
  -> isaac_env/simulation.py
  -> SimScene.prepare()
       -> scene_parser: parse USD prims by naming rules
       -> scene_generator + engine/placement.py: generate regional static layouts
       -> AssetPlacementPlanner: match assets and build import plans
       -> SceneAssetAllocator: reference assets into the USD stage and apply collision
       -> engine/dynamic.py: build optional DynamicScenePlan
  -> WeatherLightingManager: apply weather, sky, sun, fill light, and time variation
  -> RobotFactory: spawn the selected robot adapter
  -> isaac_agents: spawn optional dynamic actors from the dynamic plan
  -> isaac_sensor_sim: attach a sensor rig and select the active viewport sensor
  -> simulation loop: robot control, sensor updates, VFX updates, dynamic actors
```

Main modules:

- `src/simworld/main.py`: command-line entry point that builds `SimulationConfig`.
- `src/simworld/isaac_env/simulation.py`: runtime orchestration across Isaac context, scene, world, robot, dynamic agents, weather, VFX, and sensors.
- `src/simworld/isaac_env/isaac_adaptor/`: centralized boundary for Isaac Sim, Omniverse, and USD/PXR APIs.
- `src/simworld/isaac_env/isaac_scene/`: scene opening, naming-rule parsing, lighting cleanup, placeholder handling, and asset import.
- `src/simworld/engine/placement.py`: current geometry, regional layout, asset matching, and asset import planning logic.
- `src/simworld/engine/dynamic.py`: pure-Python dynamic actor plan generation from scene placeholders.
- `src/simworld/isaac_env/isaac_agents/`: runtime dynamic actor manager and kinematic P0 backend.
- `src/simworld/isaac_env/isaac_robots/`: robot adapters and lightweight robot factory. The default adapter is the Spot demo.
- `src/simworld/isaac_env/isaac_sensor_sim/`: pseudo-sensor runtime, sensor frame contracts, sensor rigs, mounted cameras, and depth visualization.
- `src/simworld/isaac_env/isaac_vfx/`: weather lighting plus particle rain, snow, and fog effects.
- `src/simworld/isaac_env/isaac_graph_vfx/`: graph-backed VFX scaffold for future OmniGraph/Warp implementations.
- `algorithm_lab/`: isolated workspace for lightweight experimental algorithms that should not depend on Isaac Sim.
- `scripts/`: helper scripts for asset pulling/conversion, simulation runs, and debug runs.

## Algorithm Lab

`algorithm_lab/` is reserved for independent algorithm experiments that may later feed the main Isaac Sim runtime. It is intended for regional layout, dynamic asset, and environment algorithm prototypes that need a lightweight development loop.

Code in this folder should keep dependencies minimal, avoid Isaac Sim imports, and exchange data through explicit JSON-compatible interfaces. See [algorithm_lab/guideline.md](algorithm_lab/guideline.md) before adding new experiments.

## Install And Run

### Prerequisites

- Linux environment.
- NVIDIA Isaac Sim with access to the Isaac Sim `python.sh` launcher.
- Project assets available under the repository `assets/` directory. See `scripts/collect_asset.py` if assets need to be pulled.

The run scripts search for Isaac Sim Python in this order:

1. `ISAAC_PYTHON=/path/to/isaacsim/python.sh`
2. `ISAACSIM_ROOT=/path/to/isaacsim`
3. `${HOME}/Nvidia/isaacsim-git/isaacsim/_build/linux-x86_64/release/python.sh`
4. `${HOME}/.local/share/ov/pkg/isaac-sim-*/python.sh`

If auto-detection fails, set `ISAAC_PYTHON` explicitly:

```bash
ISAAC_PYTHON=/path/to/isaacsim/python.sh scripts/run_sim.sh
```

### Normal Run

Run with Python defaults:

```bash
scripts/run_sim.sh
```

Run with environment-variable overrides:

```bash
SCENE_USD=/path/to/scene.usd ROBOT_TYPE=spot ROBOT_NAME=spot_test scripts/run_sim.sh
```

Run with CLI overrides:

```bash
scripts/run_sim.sh --scene-usd /path/to/scene.usd --robot-type spot --robot-name spot_test
```

Run with rain lighting and the Spot depth sensor active:

```bash
scripts/run_sim.sh --weather rain --sensor-profile spot_depth_camera --active-sensor spot_depth_view
```

Interactive Spot control uses the arrow keys:

```text
Arrow Up / Arrow Down: forward / backward
Arrow Left / Arrow Right: turn left / turn right
Space: stop
```

### Debug Run

Start Isaac Sim through `debugpy`:

```bash
scripts/run_sim_dbg.sh
```

By default, the debug script listens on `0.0.0.0:5678` and waits for a debugger client. Options can be overridden as follows:

```bash
DEBUG_PORT=5679 WAIT_FOR_CLIENT=0 scripts/run_sim_dbg.sh
```

## Runtime Parameters

Python defaults are defined in `src/simworld/isaac_env/simulation.py`:

- `scene_usd`: `assets/blocks/test_field/test_simple_city.usd`
- `robot_type`: `spot`
- `robot_name`: `spot_demo`
- `warmup_frames`: `30`
- `camera_prim_path`: `/OmniverseKit_Persp`
- `enable_dynamic_agents`: `true`
- `dynamic_agent_backend`: `kinematic`
- `weather`: random preset when omitted
- `daytime`: random compatible sky texture when omitted
- `sensor_profile`: `default`
- `active_sensor_id`: selected by the profile when omitted
- `fallback_spawn_position`: `(0.0, 0.0, 0.8)`

CLI arguments accepted by `src/simworld/main.py`:

- `--scene-usd`, `--scene_usd`: USD scene file to open.
- `--robot-type`: robot adapter type. Currently supported: `spot`.
- `--robot-name`: runtime robot name.
- `--warmup-frames`: number of Isaac Sim update frames before scene preparation.
- `--camera-prim-path`: fallback viewport camera prim path when sensor profiles are disabled.
- `--chase-camera`: legacy option. Follow view is now managed by `--sensor-profile`.
- `--enable-dynamic-agents`: enable or disable dynamic plan generation and runtime actors.
- `--dynamic-agent-backend`: dynamic actor backend. Currently supported: `kinematic`.
- `--dynamic-max-pedestrian-actors`, `--dynamic-max-vehicle-actors`: count limits for generated dynamic actors.
- `--dynamic-pedestrian-speed-mps`, `--dynamic-vehicle-speed-mps`: kinematic actor speeds.
- `--dynamic-spawn-time-s`: actor spawn delay.
- `--weather`: weather preset. Available presets are `sunny`, `rain`, `overcast`, `foggy`, and `storm`.
- `--daytime`: preferred sky time such as `morning`, `day`, `noon`, `sunset`, or `night`.
- `--sky-texture`: explicit lat-long sky texture or HDRI path.
- `--sun-intensity`, `--sky-intensity`, `--sky-exposure`: weather lighting overrides.
- `--weather-time-scale`, `--weather-start-time`: time-varying lighting controls.
- `--sensor-profile`: pseudo-sensor profile to attach to the robot.
- `--active-sensor`: initial active sensor id inside the selected rig.

Environment variables supported by `scripts/sim_defaults.sh`:

- `PROJECT_ROOT`
- `ISAAC_PYTHON`
- `ISAACSIM_ROOT`
- `SCENE_USD`
- `ROBOT_TYPE`
- `ROBOT_NAME`
- `WARMUP_FRAMES`
- `CAMERA_PRIM_PATH`
- `CHASE_CAMERA`
- `ENABLE_DYNAMIC_AGENTS`
- `DYNAMIC_AGENT_BACKEND`
- `DYNAMIC_MAX_PEDESTRIAN_ACTORS`
- `DYNAMIC_MAX_VEHICLE_ACTORS`
- `DYNAMIC_PEDESTRIAN_SPEED_MPS`
- `DYNAMIC_VEHICLE_SPEED_MPS`
- `DYNAMIC_SPAWN_TIME_S`
- `WEATHER`
- `DAYTIME`
- `SKY_TEXTURE`
- `SUN_INTENSITY`
- `SKY_INTENSITY`
- `SKY_EXPOSURE`
- `WEATHER_TIME_SCALE`
- `WEATHER_START_TIME`
- `KIT_LOG_LEVEL`
- `KIT_FILE_LOG_LEVEL`
- `KIT_OUTPUT_STREAM_LEVEL`
- `DEBUG_HOST`
- `DEBUG_PORT`
- `WAIT_FOR_CLIENT`

## Sensor Profiles

Pseudo sensors are managed by `isaac_sensor_sim.SensorRig`. Viewport cameras, follow cameras, and data-oriented sensors use the same activation path, so switching sensors can also switch the visible viewport renderer state.

Available profiles:

- `default` / `spot_camera_suite`: `follow_view`, `spot_front_view`, `spot_depth_view`, and `normal_view`; active sensor defaults to `follow_view`.
- `follow_camera` / `chase_camera`: sensor-owned follow camera only.
- `spot_front_camera`: forward-facing Spot preview camera.
- `spot_depth_camera` / `depth`: forward-facing Spot pseudo depth sensor and depth viewport visualization.
- `spot_normal_camera` / `pseudo_normal`: forward-facing Spot pseudo plane-normal sensor with normal render-var display and material-override fallback.
- `spot_isaac_depth_camera` / `isaac_depth`: forward-facing Spot camera with Isaac `distance_to_camera` annotator.
- `spot_isaac_normal_camera` / `normal` / `isaac_normal`: forward-facing Spot camera with Isaac `normals` annotator.
- `spot_isaac_camera_suite` / `isaac`: follow/front cameras plus Isaac depth and normal annotator sensors.
- `none` / `off`: no sensor rig; the simulation falls back to `--camera-prim-path`.

Examples:

```bash
scripts/run_sim.sh --sensor-profile default
scripts/run_sim.sh --sensor-profile default --active-sensor spot_depth_view
scripts/run_sim.sh --sensor-profile spot_depth_camera --active-sensor spot_depth_view
scripts/run_sim.sh --sensor-profile pseudo_normal --active-sensor normal_view
scripts/run_sim.sh --sensor-profile spot_isaac_depth_camera --active-sensor isaac_depth_view
scripts/run_sim.sh --sensor-profile normal --active-sensor isaac_normal_view
```

See [Isaac Sensor Sim](src/simworld/isaac_env/isaac_sensor_sim/README.md) for sensor frame contracts, renderer-control policy, external label formats, and recommended next visual sensors.

## Scene And Asset Conventions

Scene parsing currently relies on USD prim naming:

```text
<mobility>_<domain>_<category>_<index>
```

Current examples:

- `static_construction_building_001`: static building, with collision applied automatically.
- `static_ground_road_001`: static ground or road, with collision applied automatically.
- `placeholder_spot_spawn_001`: Spot spawn point.
- `placeholder_area_plaza_001`: public-space placeholder area for generated static asset layout.
- `placeholder_pedestrian_spawn_001` and `placeholder_pedestrian_goal_001`: dynamic pedestrian route endpoints.
- `placeholder_vehicle_spawn_001` and `placeholder_vehicle_goal_001`: dynamic vehicle route endpoints.
- `placeholder_vehicle_lane_001`: vehicle lane or future route geometry.
- `placeholder_area_sidewalk_001` and `placeholder_area_crosswalk_001`: future pedestrian navigation regions.

The current asset library convention is:

```text
assets/library/<category>/<asset>.usd
```

`AssetLibrary.scan_folder()` uses the parent directory as the asset category. `AssetMatcher` then matches generated footprints to assets by category. The next recommended step is to add sidecar metadata for each asset, including size, orientation, anchor point, tags, collision policy, and recommended usage context.

## Adding Another Robot Adapter

Robot adapters should implement the small runtime surface used by the simulation loop:

- `spawn(position)`
- `initialize()`
- `mark_reinit_required()`
- `forward(stepsize)`
- `step(command)`
- `initialized`
- `need_reinit`
- `prim_path` or another stable robot root prim path property for mounting sensors

Viewport and follow-camera behavior should live in `isaac_sensor_sim`, not inside the robot adapter.

Register the adapter in `src/simworld/isaac_env/isaac_robots/factory.py`:

```python
ROBOT_REGISTRY = {
    "spot": spot_demo.SpotDemo,
    "my_robot": my_robot.MyRobot,
}
```

Then run:

```bash
ROBOT_TYPE=my_robot ROBOT_NAME=my_robot_01 scripts/run_sim.sh
```

## Next Development Direction

The next phase should continue to split work into explicit contracts. Pure algorithm modules should generate structured plans or labels, and Isaac runtime modules should apply those outputs to USD stages, dynamic actors, renderers, or sensors.

- Asset import: stabilize `AssetSpec`, asset metadata, conversion scripts, category catalogs, size calibration, and anchor calibration.
- Regional layout algorithms: generate reproducible `Footprint3D` and `AssetImportPlan` outputs from plaza, sidewalk, road, and other placeholder regions.
- Dynamic asset algorithms: move from fixed spawn/goal playback toward route inference, behavior states, avoidance, and richer actor assets.
- Visual and environment algorithms: represent weather, time of day, sky, lighting, fog, particles, and material wetness as configurable outputs.
- Sensor simulation: extract shared render-var viewport sensors, then add semantic segmentation, instance segmentation, normal, detection, point cloud, BEV/occupancy, and optical-flow pseudo sensors.

See [doc/Architecture.md](doc/Architecture.md) for module boundaries, data contracts, integration plans, and optimization suggestions.
