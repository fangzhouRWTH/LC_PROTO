# SimWorld Architecture And Integration Plan

## 1. Design Goal

SimWorld should separate algorithm generation from Isaac Sim execution:

- The algorithm layer reads scene semantics, asset catalogs, and configuration, then outputs structured plans.
- The Isaac layer opens USD stages, applies plans, creates or updates prims, and controls the simulation loop.
- Asset import, static regional layout, dynamic assets, and visual/environment effects should all follow the same pattern: `Input -> Plan -> Apply -> Runtime Update`.

This keeps algorithms testable and reproducible, keeps Isaac-specific code centralized, and gives future modules a clear integration boundary.

## 2. Current Runtime Path

```text
main.py
  -> SimulationConfig
  -> IsaacContext
  -> SimScene
       -> open_stage()
       -> scene_tools.add_natural_light()
       -> scene_parser.process_stage_by_naming_rules()
       -> scene_generator.generate_plane_polygon_layout()
       -> placement.AssetPlacementPlanner.build_plan_for_footprints()
       -> SceneAssetAllocator.import_plans()
  -> SimWorld
  -> RobotFactory.create_robot()
  -> simulation loop
```

Current key data flow:

```text
USD stage
  -> SceneStats
       spawn_points: list[list[float]]
       placeholder_areas: list[PlaceholderArea]
  -> Footprint3D
  -> AssetImportPlan
  -> /World/GeneratedAssets/*
```

## 3. Module Boundaries

### 3.1 Runtime Orchestration Layer

Location:

- `src/simworld/main.py`
- `src/simworld/isaac_env/simulation.py`

Responsibilities:

- Read CLI parameters and defaults.
- Initialize Isaac Sim.
- Connect scene preparation, world reset, robot spawning, and the simulation loop.
- Avoid embedding concrete generation algorithms.

Recommendation:

- Add a `ScenePipelineConfig` later, so scene path, asset library, layout algorithm parameters, dynamic assets, and environment presets can be defined in a config file.

### 3.2 Isaac Adapter Layer

Location:

- `src/simworld/isaac_env/isaac_adaptor/isaac_context.py`

Responsibilities:

- Centralize Isaac, Omniverse, and PXR imports.
- Provide `SimulationApp`, USD context, PXR schemas, and Isaac Core helpers.
- Prevent algorithm modules from importing Isaac APIs directly.

Recommendation:

- Keep this layer thin. It should manage dependency access and lifecycle only.
- Put USD stage write operations in scene allocators or appliers, not in pure algorithm modules.

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
- Apply basic lighting.
- Call algorithm modules to generate plans.
- Apply plans to the USD stage.

Recommendation:

- Add plan-specific appliers as the project grows, such as `SceneDynamicAllocator` and `SceneEnvironmentApplier`.
- Let `SimScene.prepare()` evolve into a small configurable pipeline whose steps can be enabled or disabled by config.

### 3.4 Algorithm Layer

Current location:

- `src/simworld/engine/placement.py`
- `src/simworld/engine/calculate.py`

Current responsibilities:

- 3D and 2D geometry.
- Regional footprint generation.
- Asset library scanning, asset matching, and import-plan generation.

Recommended future split:

```text
src/simworld/engine/
  geometry.py          # Vec, polygon, projection, SAT, and frame utilities
  asset_catalog.py     # AssetSpec, AssetLibrary, and metadata loading
  layout.py            # Static regional footprint generation
  placement.py         # Footprint -> AssetImportPlan
  dynamic.py           # Pedestrian and vehicle DynamicActorPlan generation
  environment.py       # EnvironmentPlan generation
```

Short term, keeping `placement.py` intact is acceptable until the data contracts are stable.

### 3.5 Robot Layer

Location:

- `src/simworld/isaac_env/isaac_robots/factory.py`
- `src/simworld/isaac_env/isaac_robots/spot_demo.py`

Responsibilities:

- Create robots through a registry.
- Provide a stable interface used by the simulation loop.
- Isolate robot SDK or policy details inside adapters.

Recommendation:

- Define small protocols for mobile robots, vehicles, and sensor platforms as needed.
- Dynamic traffic vehicles do not necessarily need to use the robot factory. They may fit better under a dynamic actor allocator.

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

Suggested future examples:

- `placeholder_area_sidewalk_001`
- `placeholder_area_road_001`
- `placeholder_pedestrian_spawn_001`
- `placeholder_vehicle_lane_001`
- `placeholder_environment_zone_001`

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

Recommended new contract:

```text
DynamicActorPlan
  actor_id
  actor_type          # pedestrian / vehicle
  asset_category
  spawn_time
  despawn_time
  spawn_pose
  route               # list[waypoint]
  speed_profile
  behavior_profile
  animation_profile
  collision_policy
```

Dynamic algorithms should only generate plans. The Isaac layer should create actors, bind animation or controllers, update them over time, and release them when the plan ends.

### 4.4 Visual And Environment Contract

Recommended new contract:

```text
EnvironmentPlan
  time_of_day
  weather             # clear / cloudy / rain / fog ...
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

## 5. Integration Plan For The Four Next Modules

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
SceneDynamicAllocator -> create actors and controllers
simulation loop -> update actors by plan/controller
```

Focus:

- Pedestrians and vehicles can share the plan/apply pattern while using different controllers.
- Route generation and Isaac actor lifecycle management should stay separate.
- Collision, avoidance, and traffic rules can be added incrementally. Start with reproducible route playback.

### 5.4 Visual And Environment Algorithm Module

Inputs:

- Environment config, such as weather, time of day, season, and intensity
- Scene region metadata

Outputs:

- `EnvironmentPlan`

Integration path:

```text
environment_engine -> EnvironmentPlan
SceneEnvironmentApplier -> lights / sky / fog / material settings
simulation loop -> optional time-varying update
```

Focus:

- Current `scene_tools.add_natural_light()` can become the first `EnvironmentPlan(clear_day)` implementation.
- Start with discrete presets, then add continuous parameters.
- Wet materials, puddles, fog, rain, and snow should be coordinated with ground and asset material conventions.

## 6. Recommended Scene Preparation Pipeline

Short term, `SimScene.prepare()` can be organized as:

```text
1. open stage
2. clear/apply base environment
3. parse naming rules -> SceneStats
4. build asset catalog
5. generate static layout plans
6. apply static asset plans
7. generate dynamic actor plans
8. apply dynamic actor plans
9. apply environment plan
10. return SceneStats + generated plan summary
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
- Add a `configs/` directory for YAML or JSON scene, asset library, algorithm parameter, and environment preset files.
- Export every generated plan to JSON for reproduction and debugging.
- Add pure-Python tests for geometry, naming parsing, and asset matching.
- Add a stage validator to check naming rules, placeholder meshes, asset paths, and required textures before runtime.
- Keep USD stage writes centralized in allocators or appliers. Algorithm modules should not import Isaac APIs.
- Reserve a runtime manager for dynamic actors so pedestrian and vehicle update logic does not accumulate inside the main simulation loop.

## 8. Near-Term Implementation Order

Recommended priority:

1. Asset metadata: solve size and anchor information first, because layout quality depends on it.
2. Regional layout interface: stabilize `PlaceholderArea -> Footprint3D -> AssetImportPlan`.
3. Plan export and tests: make algorithm output reproducible.
4. Minimal dynamic asset loop: create pedestrians or vehicles from fixed routes in Isaac.
5. Environment preset: convert the current natural-light setup into a configurable clear-day preset.

This order lets each development track grow through the same interface pattern instead of coupling new work back to USD stage details.
