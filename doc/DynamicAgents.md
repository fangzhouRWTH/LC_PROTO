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
| `placeholder_pedestrian_route_001` | Pedestrian waypoint route geometry | `SceneStats.pedestrian_routes` |
| `placeholder_vehicle_spawn_001` | Vehicle spawn point | `SceneStats.vehicle_spawn_points` |
| `placeholder_vehicle_goal_001` | Vehicle goal point | `SceneStats.vehicle_goal_points` |
| `placeholder_vehicle_route_001` | Vehicle waypoint route geometry | `SceneStats.vehicle_routes` |
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
  lanes: list[DynamicLanePlan]

DynamicActorPlan
  actor_id
  actor_type          # pedestrian / vehicle
  route               # legacy kinematic waypoint list
  speed_mps           # legacy kinematic target speed
  spawn_time_s
  source_prim_paths

  # P1.0 compatibility fields for future external backends
  despawn_time_s
  spawn_pose
  goal_pose
  route_plan
  route_id
  speed_profile
  shape               # radius for ORCA-like agents; dimensions for vehicles
  asset_category
  behavior_profile
  controller_profile
  animation_profile
  collision_policy
  backend_hints
  metadata

DynamicRoutePlan
  route_id
  route_type          # waypoints / lane_ids / external_network
  route_mode          # loop / once / ping_pong / stop_at_end
  waypoints
  lane_ids
  source_prim_paths
  metadata

DynamicLanePlan
  lane_id
  polygon             # parsed lane placeholder vertices
  centerline          # approximate centerline for adapter use
  width_m
  source_prim_paths
  metadata
```

The planner uses explicit pedestrian or vehicle route placeholders first. Route placeholder mesh vertices are treated as waypoint order, and the first and last waypoints become the actor `spawn_pose` and `goal_pose`. If no route placeholder exists for an actor type, the planner falls back to pairing spawn/goal placeholders by matching `index` values; unindexed spawn/goal points are paired in list order after indexed pairs. Vehicle lane placeholders are converted into scene-level `DynamicLanePlan` entries; vehicle routes with a matching placeholder index reference those lanes through `DynamicRoutePlan.lane_ids`. The number of generated actors is limited by config. P1.0 keeps the legacy `route`, `speed_mps`, and `spawn_time_s` fields so the kinematic backend stays compatible, while also filling richer optional fields that future adapters can consume.

### P1.3 Route Mode And Kinematic Behavior

`DynamicRoutePlan.route_mode` controls how the kinematic backend interprets route progress:

| `route_mode` | Behavior |
| --- | --- |
| `loop` | Default. Actor wraps along the full route length. |
| `once` / `stop_at_end` | Actor stops at the final waypoint. |
| `ping_pong` | Actor reverses direction at each route end. |

Set the default through `DynamicPlanConfig.default_route_mode`. The kinematic backend reads `route_plan.route_mode`; legacy plans without a route plan continue to loop.

Reset and step ownership for dynamic backends:

```text
simulation loop
  -> agent_manager.step(dt)
    -> backend reads plan.route_plan.route_mode
    -> backend writes USD transform
```

`agent_manager.reset()` is called when the Isaac world stops; backends reset elapsed time and snap actors back to route start.

### P1.0 Backend Compatibility

Dynamic placeholder names are an authoring contract only. Backends should consume `DynamicScenePlan` fields and should not depend on USD prim names such as `placeholder_pedestrian_spawn_001`. Future USD custom attributes can be parsed into the same plan fields without changing backend interfaces.

| Backend style | Minimum data it needs | P1.0 plan fields | Still not solved |
| --- | --- | --- | --- |
| `kinematic` | Waypoints, speed, spawn time | `route`, `speed_mps`, `spawn_time_s` | Real collision handling |
| ORCA-like pedestrian adapter | Spawn pose, goal pose, preferred/max speed, radius | `spawn_pose`, `goal_pose`, `speed_profile`, `shape.radius_m`, `route_plan` | Neighbor discovery, static obstacle extraction, actual ORCA integration |
| SUMO-like vehicle adapter | Departure time, route identity, lane references, vehicle dimensions, desired speed | `spawn_time_s`, `route_id`, `route_plan.lane_ids`, `lanes`, `shape.length_m`, `shape.width_m`, `speed_profile` | SUMO network generation, junction connectivity, TraCI synchronization |
| Asset/animation visual adapter | Actor type, asset category, animation hint | `actor_type`, `asset_category`, `animation_profile`, `metadata` | Real USD asset selection and animation binding |

`tests/test_dynamic_contract.py` contains pure Python mock backend checks for ORCA-like and SUMO-like inputs. These tests are not a substitute for real ORCA/SUMO integration, but they protect the LC_PROTO plan shape from drifting back into a kinematic-only contract. The SUMO-like checks verify that vehicle route lane references point at known scene-level lane plans.

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
| `DYNAMIC_MAX_PEDESTRIAN_ACTORS` | `1` | Max number of pedestrian actors generated from route placeholders or spawn/goal pairs. |
| `DYNAMIC_MAX_VEHICLE_ACTORS` | `1` | Max number of vehicle actors generated from route placeholders or spawn/goal pairs. |
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
- It does not infer vehicle actors or full traffic routes from lanes yet when explicit route or spawn/goal data is missing.

These limitations are acceptable for P0 because the goal is to validate the LC_PROTO integration path.

## 7. Extension Path

Recommended next backend additions:

| Backend | Purpose | Integration point |
| --- | --- | --- |
| `orca` | Pedestrian local avoidance | Add `backends/orca.py` and register it in `factory.py`. |
| `sumo` | Traffic simulation and lane-level vehicle flow | Add `backends/sumo.py` and synchronize TraCI state to USD transforms. |
| `asset_visual` | Replace cube visuals with referenced USD assets | Keep motion backend stable and swap visual creation logic. |

### Pedestrian Animation Roadmap

Pedestrian animation should be layered on top of motion behavior instead of being embedded inside ORCA, SUMO, or `engine.dynamic` planning. Motion backends compute pose, velocity, and heading; visual backends create USD assets, bind animation clips, and update animation state from runtime speed.

Recommended layering:

```text
motion / behavior backend
  kinematic / ORCA / social-force
  -> position, velocity, heading

visual / animation backend
  cube / referenced USD human / USD Skel animated human
  -> root transform, idle/walk/run animation state
```

Suggested rollout:

1. Replace cube pedestrians with referenced human USD assets while keeping kinematic motion unchanged.
2. Add `animation_profile` handling for idle and walk clips, driven by actor speed.
3. Add speed-based animation blending after the runtime backend exposes reliable velocity.
4. Combine ORCA-style pedestrian motion with the same animation layer, so avoidance and visual presentation remain independent.

The current `DynamicActorPlan` fields `asset_category`, `animation_profile`, `speed_profile`, and `shape` are intended to give this visual layer stable inputs without coupling the planner to Isaac-specific animation APIs.

The main rule for future work is: keep planning in `engine/`, keep Isaac runtime application in `isaac_env/`, and keep backend-specific behavior behind the `DynamicAgentBackend` protocol.
