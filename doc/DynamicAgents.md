# Dynamic Agents

## 1. Design Goal

Dynamic agents represent pedestrians, vehicles, and future moving scene actors in the urban simulation. The current implementation follows the same LC_PROTO integration pattern used by static scene generation and robots:

```text
USD placeholder naming
  -> scene_parser extracts semantic data
  -> engine.dynamic builds a pure Python DynamicScenePlan
  -> isaac_agents manager creates runtime actors through a backend
  -> simulation loop calls step(dt)
```

The important boundary is that scene parsing and planning do not depend on Isaac Sim APIs. Isaac-specific prim creation and transform updates stay inside `isaac_env/isaac_agents`.

## 2. Current P0 Capability

The P0 dynamic agent path supports lightweight kinematic actors:

- Pedestrians are represented by simple red cube visuals.
- Vehicles are represented by simple blue cube visuals.
- Each actor follows a route generated from a spawn point and a goal point.
- Actor movement is kinematic: each frame directly updates the USD transform from route progress and speed.
- Actor lifecycle supports reset, step, speed, count limit, and spawn delay.

This is intended to validate the architecture path before introducing ORCA, SUMO, animated humans, or richer vehicle models.

## 3. Scene Naming Contract

Dynamic placeholders use the same general naming style as the existing scene pipeline:

```text
<mobility>_<domain>_<category>_<index>
```

Currently supported dynamic names include:

| Prim name example | Meaning | Output field |
| --- | --- | --- |
| `placeholder_pedestrian_spawn_001` | Pedestrian spawn point | `SceneStats.pedestrian_spawn_points` |
| `placeholder_pedestrian_goal_001` | Pedestrian goal point | `SceneStats.pedestrian_goal_points` |
| `placeholder_vehicle_spawn_001` | Vehicle spawn point | `SceneStats.vehicle_spawn_points` |
| `placeholder_vehicle_goal_001` | Vehicle goal point | `SceneStats.vehicle_goal_points` |
| `placeholder_vehicle_lane_001` | Vehicle lane or route geometry | `SceneStats.vehicle_lanes` |
| `placeholder_area_sidewalk_001` | Sidewalk area for future pedestrian logic | `SceneStats.sidewalk_areas` |
| `placeholder_area_crosswalk_001` | Crosswalk area for future pedestrian logic | `SceneStats.crosswalk_areas` |

Dynamic placeholders are optional. A scene without dynamic agent placeholders should still prepare and run normally.

Malformed dynamic placeholders are skipped with warnings instead of failing `SimScene.prepare()`. For example, a route or area placeholder without a valid mesh should not terminate the simulation.

## 4. Data Flow

### SceneStats

`scene_parser.py` extracts dynamic placeholder data into dedicated `SceneStats` fields. Dynamic sidewalk, crosswalk, lane, and zone data are intentionally not mixed into the existing static `placeholder_areas` list, so they do not trigger static asset generation.

### DynamicScenePlan

`engine/dynamic.py` converts parsed dynamic scene semantics into `DynamicScenePlan`:

```text
DynamicScenePlan
  actors: list[DynamicActorPlan]
  warnings: list[str]

DynamicActorPlan
  actor_id
  actor_type          # pedestrian / vehicle
  route               # list[(x, y, z)]
  speed_mps
  spawn_time_s
  source_prim_paths
```

The current P0 planner pairs pedestrian spawn/goal points and vehicle spawn/goal points in deterministic order. The number of generated actors is limited by config.

### Runtime Backend

`isaac_agents` is split into a manager, factory, protocol, and backend:

```text
isaac_agents/
  protocol.py          # DynamicAgentBackend protocol
  factory.py           # backend registry and manager creation
  manager.py           # lifecycle wrapper
  backends/
    kinematic.py       # current P0 implementation
```

`simulation.py` only asks the factory for a manager and calls:

```text
build_from_plan(plan)
spawn(stage)
reset()
step(dt)
```

Backend-specific implementation details stay out of the main simulation loop.

## 5. Runtime Parameters

Dynamic agent runtime options can be passed through environment variables used by `scripts/run_sim.sh`:

| Environment variable | Default | Meaning |
| --- | --- | --- |
| `ENABLE_DYNAMIC_AGENTS` | `true` | Enable dynamic plan generation and runtime actors. |
| `DYNAMIC_AGENT_BACKEND` | `kinematic` | Runtime backend name. Currently only `kinematic` is registered. |
| `DYNAMIC_MAX_PEDESTRIAN_ACTORS` | `1` | Max number of pedestrian actors generated from spawn/goal pairs. |
| `DYNAMIC_MAX_VEHICLE_ACTORS` | `1` | Max number of vehicle actors generated from spawn/goal pairs. |
| `DYNAMIC_PEDESTRIAN_SPEED_MPS` | `1.2` | Pedestrian speed in meters per second. |
| `DYNAMIC_VEHICLE_SPEED_MPS` | `4.0` | Vehicle speed in meters per second. |
| `DYNAMIC_SPAWN_TIME_S` | `0.0` | Delay before actors begin moving. |

Example run:

```bash
WARMUP_FRAMES=0 SCENE_USD=assets/blocks/test_dynamic_agents/test_dynamic_agents.usda scripts/run_sim.sh
```

Disable dynamic agents:

```bash
ENABLE_DYNAMIC_AGENTS=false scripts/run_sim.sh
```

Adjust speeds:

```bash
DYNAMIC_PEDESTRIAN_SPEED_MPS=0.8 DYNAMIC_VEHICLE_SPEED_MPS=3.0 scripts/run_sim.sh
```

Select the current backend explicitly:

```bash
DYNAMIC_AGENT_BACKEND=kinematic scripts/run_sim.sh
```

## 6. P0 Limitations

The current backend is intentionally simple:

- It does not perform collision-aware avoidance.
- It does not run pedestrian social-force or ORCA behavior.
- It does not integrate SUMO traffic state.
- It does not use animated human or vehicle assets.
- It does not infer routes from lanes yet when spawn/goal pairs are missing.

These limitations are acceptable for P0 because the goal is to validate the LC_PROTO integration path.

## 7. Extension Path

Recommended next backend additions:

| Backend | Purpose | Integration point |
| --- | --- | --- |
| `orca` | Pedestrian local avoidance | Add `backends/orca.py` and register it in `factory.py`. |
| `sumo` | Traffic simulation and lane-level vehicle flow | Add `backends/sumo.py` and synchronize TraCI state to USD transforms. |
| `asset_visual` | Replace cube visuals with referenced USD assets | Keep motion backend stable and swap visual creation logic. |

The main rule for future work is: keep planning in `engine/`, keep Isaac runtime application in `isaac_env/`, and keep backend-specific behavior behind the `DynamicAgentBackend` protocol.
