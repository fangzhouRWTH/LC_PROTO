# SimWorld Architecture And Integration Plan

## 1. Design Goal

SimWorld separates algorithm generation from Isaac Sim execution:

- The algorithm layer reads scene semantics, asset catalogs, label inputs, and configuration, then outputs structured plans or sensor-ready data.
- The Isaac layer opens USD stages, applies plans, creates or updates prims, controls renderer state, and runs the simulation loop.
- Static assets, dynamic agents, environment effects, and pseudo sensors should all follow the same pattern: `Input -> Contract -> Apply -> Runtime Update`.

This keeps algorithms testable and reproducible, keeps Isaac-specific code centralized, and gives future modules a clear integration boundary.

## 2. Current Runtime Path

```text
main.py
  -> SimulationConfig
  -> IsaacContext
  -> SimScene
       -> open_stage()
       -> deactivate stage-authored lights
       -> scene_parser.process_stage_by_naming_rules()
       -> scene_generator.generate_plane_polygon_layout()
       -> placement.AssetPlacementPlanner.build_plan_for_footprints()
       -> SceneAssetAllocator.import_plans()
       -> dynamic.build_dynamic_actor_plan()
  -> WeatherLightingManager.apply()
  -> SimWorld
  -> RobotFactory.create_robot()
  -> isaac_agents.create_dynamic_agent_manager()
  -> isaac_sensor_sim.create_sensor_rig()
  -> simulation loop
       -> robot.step(command)
       -> sensor_rig.update(timestamp, dt)
       -> particle VFX update from active sensor camera
       -> weather_lighting.update(dt)
       -> dynamic_agent_manager.step(dt)
```

Current key data flow:

```text
USD stage
  -> SceneStats
       spawn_points
       placeholder_areas
       pedestrian_spawn_points / pedestrian_goal_points
       vehicle_spawn_points / vehicle_goal_points
       vehicle_lanes
       sidewalk_areas / crosswalk_areas
  -> Footprint3D
  -> AssetImportPlan
  -> /World/GeneratedAssets/*
  -> DynamicScenePlan
  -> runtime dynamic actors
  -> SensorRig / SensorFrame
```

## 3. Module Boundaries

### 3.1 Runtime Orchestration Layer

Location:

- `src/simworld/main.py`
- `src/simworld/isaac_env/simulation.py`

Responsibilities:

- Read CLI parameters and defaults.
- Initialize Isaac Sim.
- Connect scene preparation, world reset, robot spawning, dynamic agents, weather, VFX, sensors, and the simulation loop.
- Avoid embedding concrete generation algorithms.

Recommendation:

- Add a `ScenePipelineConfig` later, so scene path, asset library, layout parameters, dynamic actors, environment presets, and sensor profiles can be defined in a config file.
- Keep interactive debug controls in runtime modules, while keeping algorithm configuration serializable.

### 3.2 Isaac Adapter Layer

Location:

- `src/simworld/isaac_env/isaac_adaptor/isaac_context.py`

Responsibilities:

- Centralize Isaac, Omniverse, and PXR imports.
- Provide `SimulationApp`, USD context, PXR schemas, and Isaac Core helpers.
- Prevent algorithm modules from importing Isaac APIs directly.

Recommendation:

- Keep this layer thin. It should manage dependency access and lifecycle only.
- Put USD stage writes in scene allocators, dynamic backends, VFX managers, or sensor modules, not in pure algorithm modules.

### 3.3 Scene Service Layer

Location:

- `src/simworld/isaac_env/isaac_scene/scene.py`
- `src/simworld/isaac_env/isaac_scene/scene_parser.py`
- `src/simworld/isaac_env/isaac_scene/scene_tools.py`
- `src/simworld/isaac_env/isaac_scene/scene_generator.py`
- `src/simworld/isaac_env/isaac_scene/scene_asset_allocator.py`

Responsibilities:

- Open the USD stage.
- Parse USD prim naming rules and semantic placeholders.
- Disable imported lights so environment lighting remains controlled.
- Call pure algorithm modules to generate static and dynamic plans.
- Apply static asset plans to the USD stage.

Recommendation:

- Let `SimScene.prepare()` evolve into a configurable pipeline whose steps can be enabled or disabled by config.
- Add plan-specific result summaries so generated assets, dynamic actors, and warnings can be exported for reproduction.

### 3.4 Algorithm Layer

Current location:

- `src/simworld/engine/placement.py`
- `src/simworld/engine/dynamic.py`
- `src/simworld/engine/calculate.py`

Current responsibilities:

- 3D and 2D geometry.
- Regional footprint generation.
- Asset library scanning, asset matching, and import-plan generation.
- Dynamic actor plan generation from parsed scene placeholders.

Recommended future split:

```text
src/simworld/engine/
  geometry.py          # Vec, polygon, projection, SAT, and frame utilities
  asset_catalog.py     # AssetSpec, AssetLibrary, and metadata loading
  layout.py            # Static regional footprint generation
  placement.py         # Footprint -> AssetImportPlan
  dynamic.py           # Pedestrian and vehicle DynamicActorPlan generation
  environment.py       # EnvironmentPlan generation
  labels.py            # Object/raster label preparation for pseudo sensors
```

Short term, keeping `placement.py` intact is acceptable until the data contracts are stable.

### 3.5 Robot Layer

Location:

- `src/simworld/isaac_env/isaac_robots/factory.py`
- `src/simworld/isaac_env/isaac_robots/spot_demo.py`
- `src/simworld/isaac_env/isaac_robots/robot.py`

Responsibilities:

- Create robots through a registry.
- Provide a stable interface used by the simulation loop.
- Isolate robot SDK or policy details inside adapters.
- Expose a stable root prim path that sensors can mount against.

Recommendation:

- Keep viewport cameras and perception sensors outside robot adapters. A robot adapter should not own follow-camera behavior.
- Define small protocols for mobile robots, vehicles, and sensor platforms as needed.
- Dynamic traffic vehicles do not necessarily need to use the robot factory. They fit better under the dynamic agent layer.

### 3.6 Dynamic Agent Layer

Location:

- `src/simworld/isaac_env/isaac_agents/`
- `src/simworld/engine/dynamic.py`

Responsibilities:

- Build `DynamicScenePlan` from parsed placeholder semantics.
- Create and update runtime dynamic actors through a backend.
- Keep backend-specific behavior behind `DynamicAgentBackend`.

Current state:

- The P0 backend is `kinematic`.
- Pedestrians and vehicles are represented by simple placeholder visuals.
- Actors follow deterministic spawn/goal routes with speed, count limit, and spawn delay controls.

Recommendation:

- Keep route planning and Isaac actor lifecycle management separate.
- Add richer visual assets, route inference, collision-aware avoidance, and traffic backends incrementally.

### 3.7 Visual And Environment Layer

Location:

- `src/simworld/isaac_env/isaac_vfx/`
- `src/simworld/isaac_env/isaac_graph_vfx/`

Responsibilities:

- Apply runtime weather lighting through sun, dome sky, fill light, and time variation.
- Provide camera-local particle effects for rain, snow, and fog.
- Keep graph-backed VFX scaffolding separate from Python particle effects.

Current state:

- Weather presets are `sunny`, `rain`, `overcast`, `foggy`, and `storm`.
- If `--weather` is omitted, startup chooses a weather preset randomly.
- `rain` and `storm` enable the rain particle effect in `simulation.py`.
- Graph VFX is scaffolded, but the main loop currently uses the Python particle manager.

Recommendation:

- Treat visual effects as runtime presentation modules unless their output is needed by sensors.
- For depth, lidar, radar, or perception sensors, pair visual fog/rain with explicit range-domain or label-domain models instead of relying only on visible particles.

### 3.8 Sensor Simulation Layer

Location:

- `src/simworld/isaac_env/isaac_sensor_sim/`

Responsibilities:

- Provide robot-decoupled pseudo sensors.
- Manage sensor lifecycle, sensor mounting, active sensor selection, and viewport camera switching.
- Emit structured `SensorFrame` outputs with pose, data, timestamp, and metadata.
- Own renderer-control behavior for sensors that need viewport display changes.
- Define external label contracts for pseudo sensors that cannot infer useful output from geometry alone.

Current state:

- `SensorRig` groups sensors and selects the active sensor.
- `follow_view` is a sensor-owned follow camera and replaces the old robot-owned chase camera path.
- `spot_front_view` is a mounted Spot preview camera.
- `spot_depth_view` is a mounted pseudo depth camera. It emits pseudo depth arrays and switches the active viewport to `DistanceToCameraSDDisplay`.
- Built-in profiles include `default`, `follow_camera`, `spot_front_camera`, `spot_depth_camera`, and `none`.

Recommendation:

- Extract a reusable `RenderVarViewportSensor` base for depth, normal, semantic, instance, and motion-style sensors.
- Require every pseudo sensor to declare `requires_renderer_control`, `requires_external_labels`, and `visualization_mode`.
- Keep semantic labels, object registries, and raster label maps as explicit inputs rather than hidden renderer side effects.

## 4. Recommended Data Contracts

### 4.1 Scene Input Contract

Continue using USD prim naming:

```text
<mobility>_<domain>_<category>_<index>
```

Current examples:

- `static_construction_building_001`
- `static_ground_road_001`
- `placeholder_spot_spawn_001`
- `placeholder_area_plaza_001`
- `placeholder_pedestrian_spawn_001`
- `placeholder_pedestrian_goal_001`
- `placeholder_vehicle_spawn_001`
- `placeholder_vehicle_goal_001`
- `placeholder_vehicle_lane_001`
- `placeholder_area_sidewalk_001`
- `placeholder_area_crosswalk_001`

Suggested future examples:

- `placeholder_environment_zone_001`
- `placeholder_sensor_target_001`
- `placeholder_traffic_signal_001`

### 4.2 Static Asset Contract

Already present:

- `AssetSpec`
- `Footprint3D`
- `AssetImportPlan`

Recommended future `AssetSpec` fields:

```text
name
usd_path
category
tags
nominal_size_xy
bounds_xyz
anchor_policy
forward_axis
up_axis
min_scale
max_scale
collision_policy
```

### 4.3 Dynamic Asset Contract

Current P0:

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

Recommended future fields:

```text
despawn_time_s
behavior_profile
animation_profile
collision_policy
asset_category
route_source
```

Dynamic algorithms should only generate plans. The Isaac layer should create actors, bind animation or controllers, update them over time, and release them when the plan ends.

### 4.4 Visual And Environment Contract

Current runtime weather controls:

```text
weather
daytime
sky_texture_path
sun_intensity
sky_intensity
sky_exposure
weather_time_scale
weather_start_time
```

Recommended future `EnvironmentPlan`:

```text
EnvironmentPlan
  time_of_day
  weather             # sunny / rain / overcast / foggy / storm ...
  sun_rotation
  sun_intensity
  sky_texture
  dome_intensity
  fog_density
  precipitation
  wetness
  exposure
```

Environment algorithms should only output parameters. The Isaac scene layer should apply those parameters to lights, materials, render settings, and optional effects.

### 4.5 Sensor Frame Contract

Current shared sensor output:

```text
SensorFrame
  sensor_id
  sensor_type
  timestamp
  frame_id
  parent_frame_id
  world_pose
  data
  meta
```

Recommended common metadata:

```text
visual_output
visualization_mode        # data_only / viewport_camera / material_override / render_product
requires_renderer_control
requires_external_labels
renderer_state_changed
```

Recommended label input contracts:

```text
ObjectLabelBundle
  schema
  objects[]
    prim_path
    class_id
    class_name
    instance_id
    bbox3d_world
    attributes

RasterLabelBundle
  schema
  resolution
  class_map
  instance_map
  palette
  camera_frame_id
  timestamp
```

This contract allows segmentation, detection, BEV, and planning-facing pseudo sensors to consume labels explicitly instead of depending on hidden material or renderer state.

## 5. Integration Plan For The Main Tracks

### 5.1 Asset Import Module

Inputs:

- `assets/library`
- Asset metadata
- Conversion script outputs

Outputs:

- `AssetLibrary`
- `AssetSpec`

Integration path:

```text
AssetLibrary.scan_folder()
  -> load metadata
  -> AssetMatcher.choose_asset()
  -> AssetPlacementPlanner.build_plan_for_footprints()
```

Focus:

- Stabilize the asset directory structure and metadata format first.
- Each asset needs real size and anchor information. Without that, regional layout cannot guarantee correct visual placement.

### 5.2 Regional Layout Algorithm Module

Inputs:

- `PlaceholderArea`
- Region type, such as plaza, sidewalk, or roadside
- Asset category constraints
- Density, boundary margin, clearance, and random seed

Outputs:

- `list[Footprint3D]`
- Or, after asset matching, `list[AssetImportPlan]`

Integration path:

```text
scene_parser -> PlaceholderArea
scene_generator/layout_engine -> Footprint3D
AssetPlacementPlanner -> AssetImportPlan
SceneAssetAllocator -> USD reference
```

Focus:

- Keep the algorithm layer independent from Isaac.
- Make generation reproducible by storing the seed in config.
- Let region type select layout strategy instead of hardcoding all behavior into one function.

### 5.3 Dynamic Asset Algorithm Module

Inputs:

- Pedestrian and vehicle spawn placeholders
- Lane, sidewalk, path, or navigation regions
- Density, speed, behavior rules, and time windows

Outputs:

- `list[DynamicActorPlan]`

Integration path:

```text
scene_parser -> dynamic placeholders / navigation regions
dynamic_engine -> DynamicActorPlan
isaac_agents manager -> create actors and controllers
simulation loop -> update actors by plan/controller
```

Focus:

- Pedestrians and vehicles can share the plan/apply pattern while using different controllers.
- Start with reproducible route playback, then add avoidance and traffic rules.

### 5.4 Visual And Environment Algorithm Module

Inputs:

- Environment config, such as weather, time of day, season, and intensity
- Scene region metadata

Outputs:

- `EnvironmentPlan`

Integration path:

```text
environment_engine -> EnvironmentPlan
WeatherLightingManager / SceneEnvironmentApplier -> lights / sky / fog / material settings
simulation loop -> optional time-varying update
```

Focus:

- Treat the current `WeatherLightingManager` as the runtime applier.
- Move toward serializable environment presets once configuration stabilizes.
- Coordinate wet materials, puddles, fog, rain, and snow with ground and asset material conventions.

### 5.5 Sensor Simulation Module

Inputs:

- Robot root prim path or scene prim path
- `SensorMountSpec`
- Optional renderer display mode
- Optional object labels or raster labels

Outputs:

- `SensorRig`
- `SensorFrame`
- Optional active viewport state

Integration path:

```text
RobotFactory -> robot root prim path
sensor presets -> SensorRig
SensorRig.activate(sensor_id)
simulation loop -> SensorRig.update(timestamp, dt)
downstream algorithm modules -> SensorFrame / label-aware outputs
```

Focus:

- Keep sensors reusable across robot platforms by depending on mount specs and prim paths, not robot classes.
- Use activation and deactivation as the only place where renderer state changes.
- Add shared bases for render-var sensors and label-driven sensors before adding many concrete sensors.

## 6. Recommended Scene Preparation And Runtime Pipeline

Short term, `SimScene.prepare()` can stay focused on scene-level preparation:

```text
1. open stage
2. clear imported lights
3. parse naming rules -> SceneStats
4. build asset catalog
5. generate static layout plans
6. apply static asset plans
7. generate dynamic actor plans
8. return SceneStats + generated plan summary
```

Runtime setup then attaches systems that need live simulation state:

```text
1. apply weather lighting
2. reset world
3. spawn robot
4. spawn dynamic actors
5. create sensor rig from robot root prim path
6. create VFX managers from weather and active camera
7. run robot, sensor, VFX, weather, and actor updates
```

Recommended result object:

```text
ScenePrepareResult
  stats
  asset_import_plans
  dynamic_actor_plans
  environment_plan
  generated_prim_paths
  warnings
```

## 7. Optimization Suggestions

- Split `placement.py` into geometry, asset catalog, layout, and plan generation modules when interfaces are stable.
- Add metadata files for `AssetSpec` to solve size, orientation, anchor, and category accuracy.
- Add a `configs/` directory for YAML or JSON scene, asset library, algorithm parameter, environment, and sensor profile files.
- Export every generated plan to JSON for reproduction and debugging.
- Add pure-Python tests for geometry, naming parsing, asset matching, dynamic plan generation, and sensor frame contracts.
- Add a stage validator to check naming rules, placeholder meshes, asset paths, textures, and required labels before runtime.
- Keep USD stage writes centralized in allocators, appliers, dynamic backends, VFX managers, or sensor modules. Algorithm modules should not import Isaac APIs.
- Reserve runtime managers for dynamic actors and sensors so update logic does not accumulate inside the main simulation loop.

## 8. Near-Term Implementation Order

Recommended priority:

1. Asset metadata: solve size and anchor information first, because layout quality depends on it.
2. Regional layout interface: stabilize `PlaceholderArea -> Footprint3D -> AssetImportPlan`.
3. Plan export and tests: make algorithm output reproducible.
4. Dynamic actor visual upgrade: keep the kinematic backend stable while replacing placeholder visuals with referenced assets.
5. Sensor base extraction: add a shared `RenderVarViewportSensor` and use it for depth, normal, semantic, instance, and motion display sensors.
6. Label-driven perception sensors: add semantic segmentation, instance segmentation, detection boxes, BEV/occupancy, and pseudo point-cloud contracts.
7. Environment presets: move weather and lighting parameters into serializable configs, then add material wetness and precipitation-domain sensor effects.

This order lets each development track grow through the same contract pattern instead of coupling new work back to USD stage details.
