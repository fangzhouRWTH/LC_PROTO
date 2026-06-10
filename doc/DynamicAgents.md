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
| `placeholder_vehicle_line_001` | Vehicle lane centerline; vertex order defines driving direction | `SceneStats.vehicle_routes` |
| `placeholder_vehicle_route_001` | Legacy vehicle waypoint route geometry | `SceneStats.vehicle_routes` |
| `placeholder_vehicle_lane_001` | Vehicle drivable lane area; fallback centerline source when no line exists | `SceneStats.vehicle_lanes` |
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

The planner uses explicit pedestrian route placeholders and explicit vehicle line/route placeholders first. Route placeholder mesh vertices are treated as waypoint order, and the first and last waypoints become the actor `spawn_pose` and `goal_pose`. If no route placeholder exists for an actor type, the planner falls back to pairing spawn/goal placeholders by matching `index` values; unindexed spawn/goal points are paired in list order after indexed pairs. Vehicle lane placeholders are converted into scene-level `DynamicLanePlan` entries; vehicle lines/routes with a matching placeholder index reference those lanes through `DynamicRoutePlan.lane_ids`. When no vehicle line/route exists, a lane-derived centerline is used as a fallback vehicle path. The number of generated actors is limited by config. P1.0 keeps the legacy `route`, `speed_mps`, and `spawn_time_s` fields so the kinematic backend stays compatible, while also filling richer optional fields that future adapters can consume.

For scene-specific demos, dynamic route data can also be loaded from a generated dynamic-only JSON before the `DynamicScenePlan` is built. Pass it with `--dynamic-routes-json` or `DYNAMIC_ROUTES_JSON`. This file replaces only pedestrian and vehicle route/lane fields by default (`replace_existing=true`) and does not affect fixed-asset placements, weather, sensors, or other mainline scene preparation.

### P1.3 Route Mode And Kinematic Behavior

`DynamicRoutePlan.route_mode` controls how the kinematic backend interprets route progress:

| `route_mode` | Behavior |
| --- | --- |
| `loop` | Default. Actor wraps along the full route length. |
| `once` / `stop_at_end` | Actor stops at the final waypoint. |
| `ping_pong` | Actor reverses direction at each route end. |

Set the default through `DynamicPlanConfig.default_route_mode`. The kinematic backend reads `route_plan.route_mode`; legacy plans without a route plan continue to loop.

Route mode support is currently backend-specific. The `kinematic` backend honors `loop`, `once`, and `ping_pong`. The mock ORCA/SUMO spikes primarily validate `once` / `stop_at_end` behavior; full `loop` and `ping_pong` parity for those mock backends is a later behavior-consistency task.

Reset and step ownership for dynamic backends:

```text
simulation loop
  -> agent_manager.step(dt)
    -> backend reads plan.route_plan.route_mode
    -> backend writes USD transform
```

`agent_manager.reset()` is called when the Isaac world stops; backends reset elapsed time, snap actors back to route start, and make previously hidden actors visible again. For `once` / `stop_at_end` routes, runtime backends hide the actor at the final waypoint instead of deleting the prim. The current demo places final waypoints outside the visible parcel, so leaving the parcel reads as an automatic despawn.

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
    orca_pedestrian.py # mock ORCA pedestrian backend (P2.1 spike)
    sumo_vehicle.py    # mock SUMO lane-following vehicle backend (P2.0 spike)
    orca_sumo.py       # composite: ORCA pedestrians + SUMO vehicles
```

`simulation.py` only asks the factory for a manager and calls:

```text
build_from_plan(plan)
spawn(stage)
reset()
step(dt)
```

Backend-specific implementation details stay out of the main simulation loop.

### Mock ORCA pedestrian tuning (P2.1.5)

`engine/orca_pedestrian.py` uses a lightweight mock (preferred velocity + local separation + static polygon repulsion), not a real ORCA library. When many pedestrians meet at a crossing, unconstrained separation can push agents off their polylines and into a shared heading.

P2.1.5 adds three stabilizers exposed via `OrcaPedestrianPlannerConfig`:

| Field | Default | Effect |
| --- | --- | --- |
| `route_attraction_gain` | `2.5` | Pull toward nearest point on the route polyline when off-route |
| `separation_max_ratio` | `0.55` | Cap repulsion relative to preferred velocity |
| `off_route_separation_decay_m` | `1.5` | Reduce separation strength while far from the route |

`tests/test_orca_pedestrian_planner.py` covers off-route recovery and heading diversity in clustered crossings.

### Mock SUMO vehicle spacing (P2.0.5)

`engine/sumo_vehicle.py` is still a lightweight mock, not real SUMO. For visual demos it applies two runtime-only helpers: sparse vehicle lanes/routes are expanded with circular fillet arcs at supported turns, and vehicles use a minimal spacing/yield rule. Vehicles sharing a lane keep a configurable center gap; vehicles on crossing or merging headings yield when their candidate poses would overlap. This avoids obvious sharp yaw jumps and cube interpenetration in the demo while keeping full junction priority, traffic lights, and car-following models as future real SUMO work.

## 5. Runtime Parameters

Dynamic agent runtime options can be passed through environment variables used by `scripts/run_sim.sh`:

| Environment variable | Default | Meaning |
| --- | --- | --- |
| `ENABLE_DYNAMIC_AGENTS` | `true` | Enable dynamic plan generation and runtime actors. |
| `DYNAMIC_AGENT_BACKEND` | `kinematic` | Runtime backend name. Supported: `kinematic`, `orca_pedestrian`, `sumo_vehicle`, `orca_sumo`, `isaac_people`, `isaac_people_sumo`. |
| `DYNAMIC_MAX_PEDESTRIAN_ACTORS` | `1` | Max number of pedestrian actors generated from route placeholders or spawn/goal pairs. |
| `DYNAMIC_MAX_VEHICLE_ACTORS` | `1` | Max number of vehicle actors generated from route placeholders or spawn/goal pairs. |
| `DYNAMIC_PEDESTRIAN_SPEED_MPS` | `1.2` | Pedestrian speed in meters per second. |
| `DYNAMIC_VEHICLE_SPEED_MPS` | `4.0` | Vehicle speed in meters per second. |
| `DYNAMIC_VEHICLES_PER_LINE` | `1` | Demo helper: number of vehicle actors derived from each vehicle line/lane. |
| `DYNAMIC_VEHICLE_SPAWN_INTERVAL_S` | `0.0` | Demo helper: spawn-time offset between vehicles derived from the same line/lane. |
| `DYNAMIC_SPAWN_TIME_S` | `0.0` | Delay before actors begin moving. |
| `DYNAMIC_ROUTE_MODE` | `loop` | Default route lifecycle. Use `once` for route-end hide/despawn demos. |
| `DYNAMIC_ROUTES_JSON` | unset | Optional dynamic-only JSON containing `pedestrian_routes`, `vehicle_routes`, and `vehicle_lanes` to apply before dynamic planning. |
| `DYNAMIC_PLACEHOLDER_VISIBILITY` | `hidden` | Show or hide dynamic authoring placeholders. Use `visible` for route debugging. |
| `DYNAMIC_PEDESTRIAN_VISUAL` | `proxy` | Pedestrian visual mode. Use `asset` to reference a real USD pedestrian asset. |
| `DYNAMIC_PEDESTRIAN_ASSET_PATH` | unset | Optional USD file or directory for pedestrian assets. Leave empty to try Isaac People defaults. |
| `DYNAMIC_PEDESTRIAN_ASSET_SCALE` | `1.0` | Extra multiplier after automatic pedestrian height fitting; use for artistic adjustment, not raw unit conversion. |
| `DYNAMIC_PEDESTRIAN_ANIMATION` | `none` | Pedestrian animation mode. Use `clip` to bind a USD Skel animation clip to the referenced pedestrian asset. |
| `DYNAMIC_PEDESTRIAN_ANIMATION_CLIP_PATH` | unset | Optional USD file or directory for pedestrian motion clips. If unset, the runtime searches nearby `Motion/` or `Motions/` folders. |
| `DYNAMIC_PEDESTRIAN_ANIMATION_TIME_SCALE` | `1.0` | Best-effort USD layer time scale for the referenced animation clip. |
| `DYNAMIC_VEHICLE_VISUAL` | `proxy` | Vehicle visual mode. Use `asset` to reference a USD vehicle asset. |
| `DYNAMIC_VEHICLE_ASSET_PATH` | unset | Optional USD file or directory for street-car assets. Explicit path is recommended; empty path falls back to proxy. |
| `DYNAMIC_VEHICLE_ASSET_SCALE` | `1.0` | Extra multiplier after automatic vehicle bounds fitting. |
| `SENSOR_PROFILE` | `default` | Sensor rig profile forwarded by `scripts/run_sim.sh`; use `none` for stage-authored demo cameras. |
| `ACTIVE_SENSOR` | unset | Initial active sensor id when a sensor rig is enabled. |

Example run (5 ORCA pedestrians + 2 SUMO vehicles on the multi-route test scene):

```bash
WARMUP_FRAMES=0 \
SCENE_USD=assets/blocks/test_dynamic_agents/test_dynamic_agents.usda \
SENSOR_PROFILE=none \
CAMERA_PRIM_PATH=/World/DemoCamera \
DYNAMIC_MAX_PEDESTRIAN_ACTORS=5 \
DYNAMIC_MAX_VEHICLE_ACTORS=2 \
DYNAMIC_AGENT_BACKEND=orca_sumo \
DYNAMIC_ROUTE_MODE=once \
scripts/run_sim.sh
```

ORCA pedestrians only:

```bash
WARMUP_FRAMES=0 \
SCENE_USD=assets/blocks/test_dynamic_agents/test_dynamic_agents.usda \
DYNAMIC_MAX_PEDESTRIAN_ACTORS=5 \
DYNAMIC_AGENT_BACKEND=orca_pedestrian \
scripts/run_sim.sh
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
DYNAMIC_AGENT_BACKEND=orca_pedestrian scripts/run_sim.sh
DYNAMIC_AGENT_BACKEND=sumo_vehicle scripts/run_sim.sh
DYNAMIC_AGENT_BACKEND=orca_sumo scripts/run_sim.sh
```

Vehicle-focused test on the dynamic agents scene:

```bash
WARMUP_FRAMES=0 \
SCENE_USD=assets/blocks/test_dynamic_agents/test_dynamic_agents.usda \
DYNAMIC_MAX_PEDESTRIAN_ACTORS=0 \
DYNAMIC_MAX_VEHICLE_ACTORS=1 \
DYNAMIC_AGENT_BACKEND=sumo_vehicle \
scripts/run_sim.sh
```

Export a `DynamicScenePlan` JSON from scene stats for offline adapter experiments:

```bash
PYTHONPATH=src/simworld python3 scripts/export_dynamic_plan.py \
  --input path/to/scene_stats.json \
  --output /tmp/dynamic_scene_plan.json
```


### Demo visual polish

The demo runtime hides dynamic authoring placeholders by default after parsing. Set `DYNAMIC_PLACEHOLDER_VISIBILITY=visible` to inspect route, lane, sidewalk, and crosswalk placeholders in the viewport. The runtime actors use lightweight proxy visuals shared by all current backends: a simple human-shaped pedestrian proxy and a simple vehicle proxy. These are placeholders for future real USD assets and USD Skel animation, not the final asset system.

### P1.4 Demo Parcel Behavior

The local `assets/blocks/test_dynamic_agents/test_dynamic_agents.usda` demo is intentionally a lightweight, ignored test asset. It now uses a larger street-block scale with a wider road intersection, sidewalks, crosswalks, denser ordered route points, and final pedestrian/vehicle waypoints outside the visible parcel. Running with `DYNAMIC_ROUTE_MODE=once` makes agents follow the route and disappear at the route end.

Curved corners do not require a spline engine in the current contract. Pedestrian paths can still use denser ordered route points when a visibly curved sidewalk path is needed. Vehicle lanes/routes should prefer sparse ordered control points around turns; the mock SUMO backend uses the matching `DynamicLanePlan.centerline` when `route_plan.lane_ids` is present and generates runtime circular fillets for smoother demo turns.

Recommended visual check:

```bash
WARMUP_FRAMES=0 \
SCENE_USD=assets/blocks/test_dynamic_agents/test_dynamic_agents.usda \
SENSOR_PROFILE=none \
CAMERA_PRIM_PATH=/World/DemoCamera \
DYNAMIC_MAX_PEDESTRIAN_ACTORS=5 \
DYNAMIC_MAX_VEHICLE_ACTORS=2 \
DYNAMIC_AGENT_BACKEND=orca_sumo \
DYNAMIC_ROUTE_MODE=once \
scripts/run_sim.sh
```


### Test Plot Authoring Guide

The current test plot is the authoring template for dynamic placeholders until formal parcels are introduced. Vehicle and pedestrian route mesh points are always ordered in travel direction. Route and lane placeholders with the same index should describe the same vehicle movement so the vehicle actor can reference the matching `DynamicLanePlan`.

For vehicle turns, author clean control points instead of dense zig-zag samples. A right turn should usually be authored as `entry straight -> corner control point -> exit straight`; the mock SUMO runtime generates a circular fillet for visual smoothness. Keep enough distance before and after the corner for the default `turn_radius_m=6.0`, and reduce the radius later only if the lane is genuinely narrow. Dense points are still accepted, but they can produce visible heading jitter.

Route endpoints used for `DYNAMIC_ROUTE_MODE=once` should sit outside the visible plot when the desired behavior is "leave the block and disappear". Use `DYNAMIC_PLACEHOLDER_VISIBILITY=visible` to debug route and lane authoring, then return to the default hidden mode for demos.

Next asset work should start with Isaac People pedestrian assets. This guide intentionally does not require real human, vehicle, SUMO, ORCA, or formal parcel assets.

### Pedestrian USD Asset Path

P1.6 adds an optional pedestrian asset visual layer. The default remains `DYNAMIC_PEDESTRIAN_VISUAL=proxy`; set `DYNAMIC_PEDESTRIAN_VISUAL=asset` to try a real USD pedestrian asset. If no usable USD is found, the runtime prints one warning and falls back to the lightweight proxy so the demo can still run. Referenced pedestrian assets are height-fitted to the actor shape by default, so centimeter-scale or character-pack USD files do not dwarf the test block. `DYNAMIC_PEDESTRIAN_ASSET_SCALE` is an extra multiplier after that fit.

Recommended sources:

- Isaac Sim official Local Assets Pack. The People assets are under `Isaac/People/Characters/` when the asset root is configured. The Replicator Agent configuration also uses `Isaac/People/Characters/` as the default character path and `Isaac/People/MotionLibrary/HumanMotionLibrary.usd` as the default motion library.
- External USD people assets from RenderPeople or Reallusion ActorCore / Character Creator. Prefer USD exports for this phase; FBX/GLB conversion and animation retargeting are later tasks.

Recommended local layout for purchased or downloaded people assets:

```bash
/home/sstormw/LeapsCora/local_assets/dynamic_people/
```

Current local test asset installed by P1.6:

```bash
/home/sstormw/LeapsCora/local_assets/omniverse_rigged_characters/Assets/Characters/Reallusion/ActorCore/Business_F_0002/Actor/business-f-0002/business-f-0002.usd
```

The broader extracted character directory is:

```bash
/home/sstormw/LeapsCora/local_assets/omniverse_rigged_characters/Assets/Characters/Reallusion/ActorCore
```

This directory intentionally lives outside `LC_PROTO/assets/library`, because that folder is scanned by the static `AssetLibrary` placement system and treats parent directories as placement categories. Dynamic pedestrians should stay as runtime references through `DYNAMIC_PEDESTRIAN_ASSET_PATH` until we introduce a dedicated dynamic asset catalog. The current Omniverse/Reallusion test character measured about 177.89 stage units high. Its rig/control bounds extend slightly below the visible foot/root area, so the runtime now treats that small negative Z as rig slack instead of lifting the character; this keeps the feet on the route ground while still fitting the visible height near the default 1.7 m pedestrian shape.

Run with an explicit asset directory:

```bash
WARMUP_FRAMES=0 \
SCENE_USD=assets/blocks/test_dynamic_agents/test_dynamic_agents.usda \
SENSOR_PROFILE=none \
CAMERA_PRIM_PATH=/World/DemoCamera \
DYNAMIC_MAX_PEDESTRIAN_ACTORS=5 \
DYNAMIC_MAX_VEHICLE_ACTORS=2 \
DYNAMIC_AGENT_BACKEND=orca_sumo \
DYNAMIC_ROUTE_MODE=once \
DYNAMIC_PEDESTRIAN_VISUAL=asset \
DYNAMIC_PEDESTRIAN_ASSET_PATH=/home/sstormw/LeapsCora/local_assets/omniverse_rigged_characters/Assets/Characters/Reallusion/ActorCore/Business_F_0002/Actor/business-f-0002/business-f-0002.usd \
scripts/run_sim.sh
```

A directory path also works; the resolver skips motion clips such as `Motions/Default.usd` when a character actor USD is available:

```bash
DYNAMIC_PEDESTRIAN_ASSET_PATH=/home/sstormw/LeapsCora/local_assets/omniverse_rigged_characters/Assets/Characters/Reallusion/ActorCore scripts/run_sim.sh
```

Run with Isaac People defaults after configuring the Isaac asset root:

```bash
DYNAMIC_PEDESTRIAN_VISUAL=asset scripts/run_sim.sh
```

P1.6 originally referenced static USD appearance only. The actor root transform still comes from the LC_PROTO motion backend. The referenced pedestrian asset child is rotated `+90` degrees around Z to match the common Isaac People / NVIDIA biped `-Y-forward` convention. Vehicle USD asset reference is supported as a static visual layer. The Tencent dynamic-agents wrapper now prefers the first locally validated sedan asset, then a local Isaac 4w vehicle pack under `/home/sstormw/LeapsCora/local_assets/dynamic_vehicles/isaac_vehicle_4w/`, then the official remote Isaac USD. If the selected vehicle USD cannot load, vehicles still fall back to the proxy visual.

### Pedestrian USD Clip Animation

P1.7 is now treated as an experimental fallback path. It adds a low-level pedestrian animation experiment: Set `DYNAMIC_PEDESTRIAN_ANIMATION=clip` while using `DYNAMIC_PEDESTRIAN_VISUAL=asset`; the runtime creates an `/Animation` child under each actor root, references a USD motion clip, finds the first `Skeleton` under `/Asset`, finds the first `SkelAnimation` under `/Animation`, and authors `skel:animationSource` on the skeleton. If the clip path is missing, not a USD file, contains no `SkelAnimation`, or cannot bind to the skeleton, the runtime prints one warning and keeps the static pedestrian asset alive. It does not fall back to proxy unless the visual asset itself failed.

Clip selection is explicit-first. `DYNAMIC_PEDESTRIAN_ANIMATION_CLIP_PATH` may point at a USD file or a directory. If it is unset, the resolver searches `Motion/` and `Motions/` directories near the character asset and its parent folders. It prefers names containing `walk`, `run`, `corridor`, `mobile`, `traffic`, `idle`, or `stand`, then falls back to deterministic path order. This lets Reallusion/ActorCore and Isaac-style asset layouts work without hard-coding one vendor.

Recommended animated demo command:

```bash
WARMUP_FRAMES=0 \
SCENE_USD=assets/blocks/test_dynamic_agents/test_dynamic_agents.usda \
SENSOR_PROFILE=none \
CAMERA_PRIM_PATH=/World/DemoCamera \
DYNAMIC_AGENT_BACKEND=orca_sumo \
DYNAMIC_ROUTE_MODE=once \
DYNAMIC_PEDESTRIAN_VISUAL=asset \
DYNAMIC_PEDESTRIAN_ASSET_PATH=/home/sstormw/LeapsCora/local_assets/omniverse_rigged_characters/Assets/Characters/Reallusion/ActorCore/Business_F_0002/Actor/business-f-0002/business-f-0002.usd \
DYNAMIC_PEDESTRIAN_ANIMATION=clip \
DYNAMIC_PEDESTRIAN_ANIMATION_CLIP_PATH=/home/sstormw/LeapsCora/local_assets/omniverse_rigged_characters/Assets/Characters/Reallusion/ActorCore/Business_F_0002/Motion/corridor_idle-b_f.usd \
DYNAMIC_VEHICLE_VISUAL=asset \
DYNAMIC_VEHICLE_ASSET_PATH=/home/sstormw/LeapsCora/local_assets/dynamic_vehicles/lc_proto_sedan_vehicle_zup.usda \
scripts/run_sim.sh
```

Implementation route judgment for future optimization:

- `USD clip` is the current path. It is minimally invasive because LC_PROTO still owns route following, ORCA/SUMO motion, visibility, and actor root transforms while USD Skel only animates the child asset.
- Isaac Replicator Agent / People Simulation is a richer future option for people behavior and motion libraries, but it would introduce a second system that wants to control agent movement. It should be evaluated after the LC_PROTO dynamic plan contract is stable.
- A pure interface-only pass is lower risk but does not satisfy visual demo requirements; keep it as the fallback strategy when a clip or skeleton cannot bind.

Current P1.7 limitations: there is no walk/idle blending, no automatic retargeting between mismatched skeletons, and no semantic animation selection from `DynamicActorPlan.animation_profile` yet. `DYNAMIC_PEDESTRIAN_ANIMATION_TIME_SCALE` is authored as a best-effort USD layer offset/custom attribute; verify clip playback speed in Isaac before depending on it for production timing.

### Isaac People Animated Pedestrian Backend

P1.9 is the current practical path for visible walking pedestrians in the local street-block demo. Use `DYNAMIC_AGENT_BACKEND=isaac_people_sumo`: pedestrians are spawned from Isaac People-compatible character USDs, vehicles continue to use the mock SUMO vehicle backend, and LC_PROTO still owns pedestrian route parsing.

The backend has two control modes:

| Env value | Use case | Behavior |
| --- | --- | --- |
| `DYNAMIC_ISAAC_PEOPLE_CONTROL=route` | Current default demo | LC_PROTO moves the character root along `placeholder_pedestrian_route_*` waypoints; the isolated `isaac_people_route_animation.py` helper binds an Isaac People in-place walk `*.skelanim.usd` clip to the character skeleton for visible leg motion. |
| `DYNAMIC_ISAAC_PEOPLE_CONTROL=command` | Future navmesh-backed formal parcels | LC_PROTO writes an OAP command file with `GoTo x y z angle` lines and lets `omni.anim.people` consume the command file. |

`DYNAMIC_ISAAC_PEOPLE_NAVMESH` only matters in `command` mode. The current test USD is not authored as a formal Omniverse navigation scene, so route mode is the reliable demo path. `once` / `stop_at_end` route modes hide the character at the route end and reset makes the character visible again. `DYNAMIC_ISAAC_PEOPLE_IGNORE_SPAWN_TIME=true` makes preset pedestrians start immediately even when their plan has staggered `spawn_time_s`; the Tencent demo wrapper enables this by default for clearer first-frame playback. Route mode is intentionally isolated from the existing kinematic / ORCA / SUMO runtime logic; only `isaac_people` and `isaac_people_sumo` call the Isaac People animation helper.

Isaac People/NVIDIA biped characters commonly use a `-Y-forward` convention while LC_PROTO route yaw treats +X as zero heading. Route mode therefore applies `DYNAMIC_ISAAC_PEOPLE_YAW_OFFSET_DEG=90` by default. If a character appears sideways or reversed, debug by running with `DYNAMIC_ISAAC_PEOPLE_YAW_OFFSET_DEG=0`, `-90`, or `180` without changing route data.

This backend requires Isaac People-compatible assets. The local Isaac Sim 5.1 asset pack layout used for this demo is:

```text
/home/sstormw/isaacsim_assets/Assets/Isaac/5.1/Isaac/People/Characters/Biped_Setup.usd
/home/sstormw/isaacsim_assets/Assets/Isaac/5.1/Isaac/People/Characters/<character>/<character>.usd
/home/sstormw/isaacsim_assets/Assets/Isaac/5.1/Isaac/People/Animations/*.skelanim.usd
```

Recommended animated people demo:

```bash
DYNAMIC_ISAAC_PEOPLE_DEBUG=true scripts/run_isaac_people_demo.sh
```

Equivalent expanded command:

```bash
WARMUP_FRAMES=0 SCENE_USD=assets/blocks/test_dynamic_agents/test_dynamic_agents.usda ROBOT_TYPE=none SENSOR_PROFILE=none CAMERA_PRIM_PATH=/World/DemoCamera AUTO_PLAY=true DYNAMIC_AGENT_BACKEND=isaac_people_sumo DYNAMIC_ROUTE_MODE=once DYNAMIC_ISAAC_PEOPLE_CONTROL=route DYNAMIC_ISAAC_PEOPLE_YAW_OFFSET_DEG=90 DYNAMIC_MAX_PEDESTRIAN_ACTORS=1 DYNAMIC_MAX_VEHICLE_ACTORS=2 DYNAMIC_VEHICLE_VISUAL=asset DYNAMIC_VEHICLE_ASSET_PATH=/home/sstormw/LeapsCora/local_assets/dynamic_vehicles/lc_proto_sedan_vehicle_zup.usda scripts/run_sim.sh
```

Debug mode prints the selected character asset, character root, SkelRoot, animation graph target, route start/end, walk clip binding result, and first/60th route-frame movement. In current route mode, successful animation setup logs `Isaac People route walk clip bound` and references an Isaac People `stand_walk_*.skelanim.usd` clip. If the character appears but has no leg animation, inspect that binding line first; the older `ag.get_character()` AnimGraph variable path is kept only as a fallback.

For future formal parcels, re-test `DYNAMIC_ISAAC_PEOPLE_CONTROL=command` after the parcel has a valid navmesh and reachable pedestrian route points. In that mode the generated command file remains:

```text
/tmp/lc_proto_dynamic_people/dynamic_people_commands.txt
```

Example command-mode lines:

```text
Character GoTo 12 3 0 0
Character GoTo 18 9 0 45
Character Idle 9999
```

Notes for authoring: route waypoints still come from LC_PROTO `placeholder_pedestrian_route_*`; in route mode they only need to be ordered and visually on the walkable surface. In command mode, keep them inside/reachable by the Isaac navmesh.

### Vehicle USD Asset Plan

Vehicle assets now follow the same runtime-reference pattern as pedestrians: `DYNAMIC_VEHICLE_VISUAL=proxy|asset`, `DYNAMIC_VEHICLE_ASSET_PATH`, and `DYNAMIC_VEHICLE_ASSET_SCALE`. The vehicle root keeps receiving motion/yaw from the backend; the referenced child is auto-fitted inside `DynamicActorShape.length_m`, `width_m`, and `height_m`. For this street-block demo, vehicle assets should be ordinary road cars, not delivery robots, carts, or sidewalk micro-mobility assets.

The current Tencent demo default is the first locally validated sedan wrapper. It is cached outside the repo so the USD payload is not committed:

```bash
/home/sstormw/LeapsCora/local_assets/dynamic_vehicles/lc_proto_sedan_vehicle_zup.usda
```

The Isaac 4w fallback folder to share with teammates is:

```bash
/home/sstormw/LeapsCora/local_assets/dynamic_vehicles/isaac_vehicle_4w/
```

It was downloaded from the Isaac official content bucket:

```text
https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Environments/Outdoor/Rivermark/dsready_content/nv_core/common_tools/validation/golden_assets/vehicle/4w/main.usda
```

`main.usda` references sibling files under `instance/`, so copy the whole `isaac_vehicle_4w/` folder instead of only the main file. Teammates can also install the same local pack with:

```bash
scripts/download_isaac_vehicle_4w_asset.sh
```

The combined Tencent wrapper resolves vehicle assets in this order: explicit `DYNAMIC_VEHICLE_ASSET_PATH`, local sedan wrapper, local Isaac 4w pack, official remote Isaac USD. The remote fallback is useful for a quick coworker smoke test, but reproducible demo machines should use a local folder/file.

Do not put downloaded vehicle packs under `LC_PROTO/assets/library` unless they are intended for the static placement planner. For shared dynamic demos, prefer a tracked manifest/download helper plus ignored payloads under a dynamic-asset folder or a repo-external path such as `/home/sstormw/LeapsCora/local_assets/dynamic_vehicles/`. If a source vehicle model is not `+X` forward, add a per-asset orientation override in a later pass rather than baking that assumption into route planning.

Run with an explicit vehicle asset path after downloading one:

```bash
DYNAMIC_VEHICLE_VISUAL=asset \
DYNAMIC_VEHICLE_ASSET_PATH=/home/sstormw/LeapsCora/local_assets/dynamic_vehicles/lc_proto_sedan_vehicle_zup.usda \
scripts/run_sim.sh
```

Reference links:

- Isaac Sim Local Assets Packs: <https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_faq.html>
- Isaac Sim Replicator Agent character path and motion library: <https://docs.isaacsim.omniverse.nvidia.com/latest/action_and_event_data_generation/ext_replicator-agent/ext_isaacsim_replicator_agent_configuration.html>
- Isaac asset root helper API: <https://docs.isaacsim.omniverse.nvidia.com/latest/py/source/extensions/isaacsim.storage.native/docs/index.html>
- Isaac Sim USD assets overview: <https://docs.isaacsim.omniverse.nvidia.com/latest/assets/usd_assets_overview.html>
- OpenUSD UsdSkel overview: <https://openusd.org/docs/api/usd_skel_page_front.html>
- Isaac Sim custom character / retargeting notes: <https://docs.isaacsim.omniverse.nvidia.com/latest/action_and_event_data_generation/ext_replicator-agent/customization.html>
- Omniverse downloadable asset packs: <https://docs-prod.omniverse.nvidia.com/usd/latest/usd_content_samples/downloadable_packs.html>
- RenderPeople 3D people: <https://renderpeople.com/3d-people/>
- RenderPeople animated people: <https://renderpeople.com/3d-animated-people/>
- Reallusion ActorCore: <https://actorcore.reallusion.com/>

## 6. P0 Limitations

The current backend is intentionally simple:

- It does not perform collision-aware avoidance.
- It does not run pedestrian social-force or ORCA behavior.
- It does not integrate SUMO traffic state.
- It does not provide production animation blending, retargeting, or real vehicle animation.
- It does not infer vehicle actors or full traffic routes from lanes yet when explicit route or spawn/goal data is missing.

These limitations are acceptable for P0 because the goal is to validate the LC_PROTO integration path.

## 7. Extension Path

Recommended next backend additions:

| Backend | Purpose | Integration point |
| --- | --- | --- |
| `orca` | Pedestrian local avoidance | Add `backends/orca.py` and register it in `factory.py`. |
| `orca_pedestrian` | Mock ORCA pedestrian spike for runtime validation | Already registered as `orca_pedestrian`; uses `engine/orca_pedestrian.py`. |
| `sumo` | Traffic simulation and lane-level vehicle flow | Add `backends/sumo.py` and synchronize TraCI state to USD transforms. |
| `sumo_vehicle` | Mock SUMO lane-following spike for runtime validation | Already registered as `sumo_vehicle`; uses `engine/sumo_vehicle.py`. |
| `orca_sumo` | Combined ORCA pedestrians + SUMO vehicles in one run | Already registered as `orca_sumo`; composes the two backends above. |
| `asset_visual` | Replace cube visuals with referenced USD assets | Keep motion backend stable and swap visual creation logic. |
| `isaac_people` | Animated pedestrians through Isaac `omni.anim.people` | Converts LC_PROTO pedestrian routes into OAP `GoTo` command files and lets Isaac People drive walking animation. |
| `isaac_people_sumo` | Animated pedestrians + current mock SUMO vehicles | Recommended demo backend once Isaac People assets are installed. |

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
