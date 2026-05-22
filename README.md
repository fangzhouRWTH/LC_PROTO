# LC_01 SimWorld

LC_01 SimWorld is an NVIDIA Isaac Sim based simulation project for urban and campus-scale environments. The codebase has moved from early validation scripts into a modular framework under `src/simworld`. The current pipeline can open USD scenes, parse scene semantics from naming rules, extract spawn points and placeholder areas, generate static asset layouts inside regions, import referenced USD assets, configure lighting, spawn a controllable robot, and run the Isaac Sim loop.

## Documentation

- [Weekly Report](Doc/WeeklyReports/WeeklyReport_2026-05-15_2026-05-21.md): summarizes the main code updates, current outcome, and risks from 2026-05-15 to 2026-05-21.
- [Architecture](Doc/Architecture.md): describes the current framework boundaries and the integration plan for asset import, regional layout, dynamic assets, and visual/environment algorithms.

## Current Framework

The main runtime path is:

```text
scripts/run_sim.sh
  -> src/simworld/main.py
  -> isaac_env/simulation.py
  -> SimScene.prepare()
       -> scene_parser: parse USD prims by naming rules
       -> scene_generator + engine/placement.py: generate region asset footprints
       -> AssetPlacementPlanner: match assets and build import plans
       -> SceneAssetAllocator: reference assets into the USD stage and apply collision
  -> SimWorld + RobotFactory: reset the world, spawn the robot, and run the control loop
```

Main modules:

- `src/simworld/main.py`: command-line entry point that builds `SimulationConfig`.
- `src/simworld/isaac_env/simulation.py`: runtime orchestration across Isaac context, scene, world, and robot.
- `src/simworld/isaac_env/isaac_adaptor/`: centralized boundary for Isaac Sim, Omniverse, and USD/PXR APIs.
- `src/simworld/isaac_env/isaac_scene/`: scene opening, naming-rule parsing, lighting setup, placeholder handling, and asset import.
- `src/simworld/engine/placement.py`: current geometry, regional layout, asset matching, and asset import planning logic.
- `src/simworld/isaac_env/isaac_robots/`: robot adapters and lightweight robot factory. The default adapter is the Spot demo.
- `scripts/`: helper scripts for asset pulling/conversion, simulation runs, and debug runs.

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
- `fallback_spawn_position`: `(0.0, 0.0, 0.8)`

CLI arguments accepted by `src/simworld/main.py`:

- `--scene-usd`, `--scene_usd`: USD scene file to open.
- `--robot-type`: robot adapter type. Currently supported: `spot`.
- `--robot-name`: runtime robot name.
- `--warmup-frames`: number of Isaac Sim update frames before scene preparation.
- `--camera-prim-path`: viewport camera prim path for chase camera behavior.

Environment variables supported by `scripts/sim_defaults.sh`:

- `PROJECT_ROOT`
- `ISAAC_PYTHON`
- `ISAACSIM_ROOT`
- `SCENE_USD`
- `ROBOT_TYPE`
- `ROBOT_NAME`
- `WARMUP_FRAMES`
- `CAMERA_PRIM_PATH`
- `KIT_LOG_LEVEL`
- `KIT_FILE_LOG_LEVEL`
- `KIT_OUTPUT_STREAM_LEVEL`
- `DEBUG_HOST`
- `DEBUG_PORT`
- `WAIT_FOR_CLIENT`

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
- `set_chase_camera(chase, cam_prim_path=...)`
- `forward(stepsize)`
- `step(command)`
- `initialized`
- `need_reinit`

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

The next phase should be split into four development tracks. All of them should follow the same integration rule: the pure algorithm layer generates a structured plan, and the Isaac scene layer applies that plan to the USD stage or runtime.

- Asset import: stabilize `AssetSpec`, asset metadata, conversion scripts, category catalogs, size calibration, and anchor calibration.
- Regional layout algorithms: generate reproducible `Footprint3D` and `AssetImportPlan` outputs from plaza, sidewalk, road, and other placeholder regions.
- Dynamic asset algorithms: generate spawn points, routes, speed profiles, behavior states, and lifecycle plans for pedestrians and vehicles.
- Visual and environment algorithms: represent weather, time of day, sky, lighting, fog, and material wetness as configurable `EnvironmentPlan` outputs.

See [Doc/Architecture.md](Doc/Architecture.md) for module boundaries, data contracts, integration plans, and optimization suggestions.
