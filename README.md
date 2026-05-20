# LC_01 SimWorld

## 1. Project Introduction

LC_01 SimWorld is an early-stage simulation platform for building an automated pipeline that connects scene generation, training, and simulation workflows with NVIDIA Isaac Sim.

The current codebase is evolving from a fast prototyping script into a modular Python package under `src/simworld`. The immediate focus is to provide a reliable Isaac Sim runtime entry point, load generated USD scenes, parse scene semantics from naming conventions, prepare simulation assets, spawn controllable robots, and keep the runtime loop reusable for future training and evaluation tasks.

Current high-level modules:

- `src/simworld/main.py`: command-line entry point.
- `src/simworld/isaac_env/simulation.py`: simulation orchestration and runtime loop.
- `src/simworld/isaac_env/isaac_adaptor/`: Isaac Sim context and lazy integration boundary.
- `src/simworld/isaac_env/isaac_scene/`: USD scene loading, light setup, naming-rule parsing, spawn-point extraction, and simulation world wrapper.
- `src/simworld/isaac_env/isaac_robots/`: robot adapters and lightweight robot factory.
- `scripts/`: local run scripts for normal and debug execution.

The default robot implementation is currently a Spot demo adapter. The robot creation path is intentionally kept open through a lightweight registry so that other robot wrappers can be added later without rewriting the simulation loop.

## 2. Install & Run

### Prerequisites

- Linux environment with NVIDIA Isaac Sim available.
- Isaac Sim Python launcher, usually `python.sh`.
- Project assets available under the repository `assets/` directory.

The run scripts try to locate Isaac Sim in this order:

1. `ISAAC_PYTHON=/path/to/isaacsim/python.sh`
2. `ISAACSIM_ROOT=/path/to/isaacsim`
3. `${HOME}/Nvidia/isaacsim-git/isaacsim/_build/linux-x86_64/release/python.sh`
4. `${HOME}/.local/share/ov/pkg/isaac-sim-*/python.sh`

If auto-detection fails, set `ISAAC_PYTHON` explicitly:

```bash
ISAAC_PYTHON=/path/to/isaacsim/python.sh scripts/run_sim.sh
```

### Run Simulation

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

By default, the debug script listens on `0.0.0.0:5678` and waits for a debugger client.

Debug options:

```bash
DEBUG_PORT=5679 WAIT_FOR_CLIENT=0 scripts/run_sim_dbg.sh
```

### Runtime Parameters

Python defaults are defined in `src/simworld/isaac_env/simulation.py`:

- `scene_usd`: `assets/blocks/test_field/test_simple_city.usd`
- `robot_type`: `spot`
- `robot_name`: `spot_demo`
- `warmup_frames`: `30`
- `camera_prim_path`: `/OmniverseKit_Persp`
- `fallback_spawn_position`: `(0.0, 0.0, 0.8)`

CLI arguments accepted by `src/simworld/main.py`:

- `--scene-usd`, `--scene_usd`: USD scene file to open.
- `--robot-type`: robot adapter type. Currently available: `spot`.
- `--robot-name`: runtime robot name.
- `--warmup-frames`: number of Isaac Sim update frames before scene preparation.
- `--camera-prim-path`: viewport camera prim path for chase camera behavior.

Environment variables supported by `scripts/sim_defaults.sh`:

- `PROJECT_ROOT`: project root override. Normally inferred from the script location.
- `ISAAC_PYTHON`: explicit Isaac Sim Python launcher path.
- `ISAACSIM_ROOT`: Isaac Sim root directory. Used to find `${ISAACSIM_ROOT}/python.sh`.
- `SCENE_USD`: optional scene override.
- `ROBOT_TYPE`: optional robot type override.
- `ROBOT_NAME`: optional robot name override.
- `WARMUP_FRAMES`: optional warmup frame override.
- `CAMERA_PRIM_PATH`: optional camera prim path override.
- `KIT_LOG_LEVEL`: default `error`.
- `KIT_FILE_LOG_LEVEL`: default `error`.
- `KIT_OUTPUT_STREAM_LEVEL`: default `error`.
- `DEBUG_HOST`: debug listener host, default `0.0.0.0`.
- `DEBUG_PORT`: debug listener port, default `5678`.
- `WAIT_FOR_CLIENT`: set to `1` or `true` to wait for debugger attachment, default `1`.

### Adding Another Robot Adapter

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

## 3. Development Progression & Plan

### Current Progression

The project started from `scripts/sample.py`, a fast validation script used to test Isaac Sim scene loading, keyboard control, Spot policy execution, light setup, collision setup, and placeholder-based spawn extraction.

The current implementation moves those responsibilities into a more maintainable structure:

- Simulation runtime is centralized in `simulation.py`.
- Command-line parsing is isolated in `main.py`.
- Shell scripts are reduced to environment setup and execution wrappers.
- Scene preparation is handled through `SimScene` and naming-rule processing.
- `SimWorld` wraps Isaac Sim world state, reset, play/stop checks, and step execution.
- Robot creation now goes through a lightweight factory, with Spot as the first registered adapter.

### Near-Term Plan

- Stabilize USD naming conventions for generated scenes.
- Expand scene parsing beyond spawn points and static collision rules.
- Improve collision application for nested USD hierarchies and referenced assets.
- Add structured configuration files for repeatable scene and robot runs.
- Add basic runtime validation checks and focused tests for pure-Python parsing/config logic.
- Improve logging so simulation output can be filtered or redirected cleanly.

### Longer-Term Direction

The platform is expected to grow into an automated scene-generation, training, and simulation pipeline:

- Generate or import USD scenes from procedural tools or external asset sources.
- Annotate scenes with semantic placeholders, navigation regions, spawn points, and task metadata.
- Prepare Isaac Sim scenes automatically for physics, lighting, sensors, and robot placement.
- Run policy training or evaluation loops over generated scene batches.
- Collect simulation traces, observations, metrics, and failure cases.
- Support multiple robot adapters through the robot factory interface.

Some interfaces are intentionally open at this stage. The exact training backend, scene-generation interface, dataset format, and multi-robot abstractions will be refined as the project requirements become clearer.
