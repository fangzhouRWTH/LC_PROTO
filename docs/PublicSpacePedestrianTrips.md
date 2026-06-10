# Public-Space Pedestrian Trips

## Scope

This note records the current main-branch integration for pedestrian trips generated from public-space regions. The runtime source for pedestrians is now generated `pedestrian_routes`; raw `walking_lines` are kept as `pedestrian_walkable_lines` for debug and HTML preview only.

For the Tencent simplified test scene, use public-space regions parsed from the USD scene. Do not pass the external `asset_configuration/` directory for this test. That directory describes a separate set of region JSON inputs and can make fixed assets and pedestrian trips appear in the wrong parcel.

## Test Files To Share

These large/local assets are not tracked by git in this checkout, so teammates need a copy or an equivalent local install:

| Purpose | Local path |
| --- | --- |
| Tencent simplified scene | `/home/sstormw/LeapsCora/LC_PROTO/assets/blocks/demo_tencent_test_simplified.usdc` |
| LCSTD fixed asset library root | `/home/sstormw/LeapsCora/LC_PROTO/assets/lcstd_assets_library./lcstd_assets_library/static/` |
| LCSTD asset map | `/home/sstormw/LeapsCora/LC_PROTO/assets/lcstd_assets_library./lcstd_assets_library/static/asset_name_map.json` |
| Isaac People asset pack | `/home/sstormw/isaacsim_assets/Assets/Isaac/5.1/Isaac/People/` |
| Isaac 4w vehicle demo asset pack | `/home/sstormw/LeapsCora/local_assets/dynamic_vehicles/isaac_vehicle_4w/` |

The LCSTD directory name currently includes a trailing dot: `assets/lcstd_assets_library.`. Keep that spelling unless the command line is updated too.


## Scene-Specific People + Vehicle Preset Generation

For short-term demo scenes, use the two-step preset flow instead of manually wiring one-off environment variables. The default Tencent demo scene is:

```text
assets/blocks/demo_tencent_test_simplified.usdc
```

Generate six dynamic people/vehicle route presets from the current USD scene:

```bash
scripts/build_demo_dynamic_agent_presets.sh \
  --scene-usd assets/blocks/demo_tencent_test_simplified.usdc \
  --output-dir configs/demo_agents/generated/demo_tencent_test_simplified \
  --preset-prefix demo_tencent
```

The command writes:

- `demo_tencent_base_placement_plan.json`: clean scene-derived public-space placement plan
- `demo_tencent_base_summary.json`: parser summary, including `vehicle_route_count` and `vehicle_lane_count`
- `demo_tencent_people_1..6_placement_plan.json`: intermediate people-route plans used only by the generator
- `demo_tencent_people_1..6_dynamic_routes.json`: dynamic-only route layers loaded by runtime
- `demo_tencent_people_1..6_dynamic_agent_preset.json`: runtime environment presets for people + vehicles
- optional HTML previews under `outputs/public_space_routes/demo_tencent_test_simplified/`

The `*_dynamic_routes.json` files intentionally contain only `pedestrian_routes`, `vehicle_routes`, and `vehicle_lanes`. They do not contain fixed-asset `placements`, so loading one changes the dynamic layer without overriding the main static asset placement, weather, sensor, or camera flow.

Run one density with:

```bash
scripts/run_demo_dynamic_agent_preset.py \
  --preset-json configs/demo_agents/generated/demo_tencent_test_simplified/demo_tencent_people_3_dynamic_agent_preset.json
```

Change density by choosing `people_1` through `people_6` in the preset filename, or by setting `DEMO_PEOPLE_SCENARIO=people_4` when using the Tencent wrapper. The generated Tencent summary from this workstation confirms that `demo_tencent_test_simplified.usdc` currently parses `vehicle_route_count=2` and `vehicle_lane_count=2`. If vehicles do not appear at runtime, first check that the combined/preset runner is being used; the people-only wrapper intentionally defaults `DYNAMIC_MAX_VEHICLE_ACTORS=0`.

## Tencent Demo Vehicle Flow

Vehicle authoring for the short-term Tencent demo uses these USD placeholder names:

```text
placeholder_vehicle_lane_001  # drivable lane area / bounds
placeholder_vehicle_line_001  # explicit lane centerline; vertex order is driving direction
```

The runtime treats `placeholder_vehicle_line_*` as the authoritative driving line when it exists. A same-index `placeholder_vehicle_lane_*` is kept as lane context and validation metadata. If a future scene only provides `placeholder_vehicle_lane_*`, the dynamic plan falls back to a lane-derived centerline, but direction quality depends on the lane polygon ordering.

Run the combined people + vehicle demo with:

```bash
DEMO_PEOPLE_SCENARIO=people_3 \
DYNAMIC_MAX_VEHICLE_ACTORS=6 \
DYNAMIC_VEHICLES_PER_LINE=3 \
DYNAMIC_VEHICLE_SPEED_MPS=9.0 \
DYNAMIC_VEHICLE_SPAWN_INTERVAL_S=4.0 \
scripts/run_demo_tencent_dynamic_agents.sh
```

Useful knobs:

- `DEMO_PEOPLE_SCENARIO=people_1|people_2|people_3|people_4|people_5|people_6` changes pedestrian density.
- `DYNAMIC_MAX_VEHICLE_ACTORS` caps total visible/generated vehicle actors.
- `DYNAMIC_VEHICLES_PER_LINE` creates multiple staggered vehicles from each `vehicle_line`.
- `DYNAMIC_VEHICLE_SPAWN_INTERVAL_S` delays vehicles derived from the same line so they do not all appear at the start.
- `DYNAMIC_VEHICLE_SPEED_MPS` controls vehicle speed; the combined Tencent demo wrapper defaults to `9.0`.
- `DYNAMIC_ISAAC_PEOPLE_IGNORE_SPAWN_TIME=false` restores staggered pedestrian starts; the wrapper defaults to immediate starts.
- `DYNAMIC_VEHICLE_ASSET_PATH` points to the USD car asset; the combined wrapper now prefers the first locally validated sedan asset, then the local Isaac 4w asset pack, then the official remote Isaac USD. If the runtime cannot load the selected asset it falls back to proxy visuals.

On this workstation the default vehicle asset is:

```text
/home/sstormw/LeapsCora/local_assets/dynamic_vehicles/lc_proto_sedan_vehicle_zup.usda
```

The local Isaac 4w vehicle pack remains available as a fallback asset. Teammates can either copy this local folder, run the helper below, or rely on the wrapper remote fallback if their machine can access NVIDIA Omniverse content online:

```bash
scripts/download_isaac_vehicle_4w_asset.sh
```

```text
https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Environments/Outdoor/Rivermark/dsready_content/nv_core/common_tools/validation/golden_assets/vehicle/4w/main.usda
```

The generated preview and placement plan are local outputs and can be regenerated:

| Purpose | Local output |
| --- | --- |
| Correct USD-scene-derived plan | `outputs/area_placement/demo_tencent_scene_regions/placement_output.json` |
| Correct route preview HTML | `outputs/public_space_routes/demo_tencent_scene_region_trips.html` |

## Isaac People Runtime Requirements

Dynamic pedestrian animation is not fully self-contained in this repository. The demo uses Isaac Sim People runtime for character assets, animation graphs, and walk clips.

Each machine must have an Isaac Sim Python launcher available. Set one of these if the launcher is not in the script default search paths:

```bash
export ISAAC_PYTHON=/path/to/IsaacSim/_build/linux-x86_64/release/python.sh
# or
export ISAACSIM_ROOT=/path/to/IsaacSim/_build/linux-x86_64/release
```

Each machine must also have the Isaac People asset pack installed locally. Set `ISAAC_ASSET_ROOT` to the asset root, not to the `Isaac/People` subdirectory:

```bash
export ISAAC_ASSET_ROOT=/path/to/isaacsim_assets/Assets/Isaac/5.1
```

The following files are the minimum smoke-check targets:

```text
$ISAAC_ASSET_ROOT/Isaac/People/Characters/Biped_Setup.usd
$ISAAC_ASSET_ROOT/Isaac/People/Characters/F_Business_02/F_Business_02.usd
$ISAAC_ASSET_ROOT/Isaac/People/Animations/stand_walk_loop_in_place.skelanim.usd
```

On this workstation the working paths are:

```text
ISAAC_PYTHON=/home/sstormw/IsaacSim/_build/linux-x86_64/release/python.sh
ISAAC_ASSET_ROOT=/home/sstormw/isaacsim_assets/Assets/Isaac/5.1
```

The runtime enables Isaac People and animation extensions in code, including `omni.anim.people`, `omni.anim.graph.*`, `omni.anim.navigation.*`, and `isaacsim.replicator.agent.core`. If these extensions are missing from a coworker Isaac install, characters may fail to load even if the LC_PROTO Python code is present.

Expected successful log signs:

- `Isaac People asset root: .../isaacsim_assets/Assets/Isaac/5.1`
- `Isaac People control mode: route`
- `Isaac People navigation mode: direct route`
- `Spawned N Isaac People animated pedestrian actor(s).`
- With `DYNAMIC_ISAAC_PEOPLE_DEBUG=true`, route frame logs should show nonzero movement.

If the log says no character USD was found, or if `Spawned 0 Isaac People animated pedestrian actor(s).` appears, first check `ISAAC_ASSET_ROOT` and the files listed above. `dynamic_people_commands.txt` under `/tmp/lc_proto_dynamic_people/` is not the main dependency in route-control mode; it is intentionally empty for the current direct-route demo path.

## Correct Tencent Flow

The expected data flow is:

```text
demo_tencent_test_simplified.usdc
  -> scene_parser public_space_regions
  -> area_placement_methods
  -> pedestrian_walkable_lines
  -> deterministic trip generator
  -> pedestrian_routes
  -> DynamicScenePlan
  -> isaac_people_sumo runtime
```

Use `DYNAMIC_ROUTE_MODE=once` when the desired behavior is that a pedestrian disappears at the end of a trip. Use `loop` only for continuous route inspection.

## Tencent Demo People Scenarios

For the short-term Tencent pedestrian demo, use the explicit demo scenario config:

```text
configs/demo_people/tencent_dynamic_people_scenarios.json
```

The scenario names are literal visible-person counts:

| Scenario | Visible pedestrians | Notes |
| --- | ---: | --- |
| `people_1` | 6 | sparse, easiest visual sanity check |
| `people_2` | 10 | light foot traffic |
| `people_3` | 16 | default demo density |
| `people_4` | 22 | busy but still readable |
| `people_5` | 30 | dense demo crowd |
| `people_6` | 40 | maximum current crowd preset |

These presets are demo-only. The normal Tencent wrapper now builds fixed-asset placement from the current USD public-space labels, then applies the selected demo people scenario. This avoids loading one stale placement plan after the scene labels change.

The default runtime path applies the selected `*_dynamic_routes.json` after normal scene parsing and static placement. Density is selected with:

```bash
DEMO_PEOPLE_SCENARIO=people_1 scripts/run_demo_tencent_dynamic_people.sh
DEMO_PEOPLE_SCENARIO=people_6 scripts/run_demo_tencent_dynamic_agents.sh
```

You can also bypass the scenario naming and point at an exact dynamic layer:

```bash
DYNAMIC_ROUTES_JSON=configs/demo_agents/generated/demo_tencent_test_simplified/demo_tencent_people_4_dynamic_routes.json \
  scripts/run_demo_tencent_dynamic_agents.sh
```

Precomputed static plans may still be used explicitly for a locked legacy rehearsal by setting `DEMO_PEOPLE_USE_STATIC_PLAN=true` and `DEMO_PEOPLE_PLACEMENT_PLAN=...`. Static plans include fixed-asset placements plus final `pedestrian_routes`, so they must be regenerated whenever the scene USD labels change.

The offline generator that produced these plans keeps the main public-space output intact, then postprocesses `pedestrian_walkable_lines` into longer demo routes. Each actor has deterministic values for:

- `offset_m`: lateral route offset, using uneven left/right candidates instead of one fixed lane width
- `start_offset_m`: distance trimmed from the route start, so actors can spawn along the route body instead of only at graph endpoints
- `speed_mps`: per-actor walking speed
- `spawn_time_s`: staggered spawn time; the current Tencent demo wrapper ignores it by default so all people are visible and walking from frame 0
- `collision_rehearsal_detours`: optional local bend points inserted around near-collision locations

Run Isaac with the wrapper script:

```bash
DEMO_PEOPLE_SCENARIO=people_6 \
DYNAMIC_ISAAC_PEOPLE_DEBUG=true \
scripts/run_demo_tencent_dynamic_people.sh

# Restore staggered preset starts when desired:
DYNAMIC_ISAAC_PEOPLE_IGNORE_SPAWN_TIME=false scripts/run_demo_tencent_dynamic_people.sh
```

The wrapper defaults to `DEMO_PEOPLE_SCENARIO=people_3`, `DEMO_PEOPLE_USE_STATIC_PLAN=false`, `DYNAMIC_ROUTE_MODE=once`, `DYNAMIC_MAX_PEDESTRIAN_ACTORS=40`, and `DYNAMIC_ISAAC_PEOPLE_IGNORE_SPAWN_TIME=true`. It does not pass external `asset_configuration/`; fixed assets are generated from the current USD labels by default, then the selected dynamic-only JSON replaces only pedestrian/vehicle route fields. Set `DYNAMIC_ISAAC_PEOPLE_IGNORE_SPAWN_TIME=false` to restore the preset staggered starts.

Render an explicitly precomputed static plan without launching Isaac:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src/simworld \
scripts/visualize_public_space_routes.py \
  --placement-plan-json configs/demo_people/generated/tencent_people_6_placement_plan.json \
  --output outputs/public_space_routes/fixed/demo_tencent_people_6_static.html \
  --show-walkable-lines \
  --show-zones \
  --color-by status \
  --labels region
```

Latest fixed-plan previews generated all six requested counts with no scenario warnings: `6 / 10 / 16 / 22 / 30 / 40`. The fixed plans also record the offline collision-rehearsal summary in `demo_people_scenario_debug.collision_rehearsal`. The rehearsal inserts local bend points and small spawn delays where possible, but the current Tencent demo presets can still contain a few residual close passes in dense street segments.

To regenerate dynamic route layers for a different parcel, run the same scene-specific preset builder with the new scene USD:

```bash
scripts/build_demo_dynamic_agent_presets.sh \
  --scene-usd assets/blocks/<new_scene>.usdc \
  --output-dir configs/demo_agents/generated/<new_scene_name> \
  --preset-prefix <new_prefix>
```

The command writes six dynamic route JSONs and six preset wrappers. After that, runtime chooses by `DEMO_PEOPLE_SCENARIO` or `DYNAMIC_ROUTES_JSON`; it does not rerun the rehearsal while Isaac is starting. If the new parcel should keep both old and new presets, use a different `--preset-prefix` and point `DEMO_DYNAMIC_ROUTES_DIR` / `DEMO_DYNAMIC_ROUTES_PREFIX` or `DYNAMIC_ROUTES_JSON` at the desired set.

## HTML Preview

After the scene-derived `placement_output.json` exists, render the route-only preview:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src/simworld \
scripts/visualize_public_space_routes.py \
  --placement-plan-json outputs/area_placement/demo_tencent_scene_regions/placement_output.json \
  --output outputs/public_space_routes/demo_tencent_scene_region_trips.html \
  --show-walkable-lines \
  --show-zones \
  --color-by status
```

The correct preview from the current test run contained:

- 32 raw walkable lines
- 20 generated pedestrian trips
- trip length min/median/max about `20.93m / 24.92m / 30.09m`
- routes generated from 9 USD public-space placeholder regions

Open the HTML file directly in a browser. It shows generated trips as the main layer and raw walkable lines as dashed gray context.

## Full Isaac Smoke

Run the complete scene test without `--region-input-json`:

```bash
DYNAMIC_ISAAC_PEOPLE_DEBUG=true \
AUTO_PLAY=true \
AUTO_PLAY_MIN_FRAMES=2400 \
SCENE_USD=/home/sstormw/LeapsCora/LC_PROTO/assets/blocks/demo_tencent_test_simplified.usdc \
ROBOT_TYPE=none \
SENSOR_PROFILE=none \
ENABLE_DYNAMIC_AGENTS=true \
DYNAMIC_AGENT_BACKEND=isaac_people_sumo \
DYNAMIC_ROUTE_MODE=once \
DYNAMIC_PEDESTRIAN_SPEED_MPS=0.8 \
DYNAMIC_MAX_PEDESTRIAN_ACTORS=4 \
DYNAMIC_MAX_VEHICLE_ACTORS=0 \
scripts/run_sim.sh \
  --layout-backend area_placement_methods \
  --layout-output-dir outputs/area_placement/demo_tencent_scene_regions_people_once_slow \
  --use-dummy-public-space-assets false \
  --public-space-asset-name-map assets/lcstd_assets_library./lcstd_assets_library/static/asset_name_map.json \
  --skip-legacy-placeholder-areas true
```

Expected signs in the log:

- area placement consumes `scene_stats.public_space_regions`
- fixed placements are generated from the LCSTD library
- `Dynamic actor plan: pedestrians=4`
- Isaac People actors load successfully
- with `DYNAMIC_ROUTE_MODE=once`, actors are hidden at route end

The first four routes in the latest smoke were in the scene-derived public-space region around negative X. If the viewport camera starts elsewhere, move to that region or increase `DYNAMIC_MAX_PEDESTRIAN_ACTORS` after confirming the output plan.

## Debug Notes From This Integration

The main failure mode we hit was using `--region-input-json asset_configuration` while testing the main Tencent USD. That caused area placement to consume 17 external region JSON files instead of the USD scene's public-space regions. The result looked like a fixed-asset algorithm regression, but the underlying issue was the wrong input source: placements and pedestrian trips were generated in coordinates from the external configuration, not from `demo_tencent_test_simplified.usdc`.

After removing `--region-input-json`, `scene_area_placement` used `stats.public_space_regions` parsed from the USD. The corrected plan generated 87 fixed placements, 32 raw walkable lines, and 20 pedestrian trips in the expected scene regions.

The second issue was route semantics. Original `walking_lines` are walkable skeleton lines, not final pedestrian trips. Feeding them directly to runtime produced short routes and pedestrians that could stop in-place. The current generator keeps those lines as `pedestrian_walkable_lines`, splits and merges them into a deterministic graph, then emits 15-40m runtime trips through `pedestrian_routes`.

The third issue was route-end lifecycle. For Isaac People route mode, `once` and `stop_at_end` now hide the actor at the final waypoint instead of leaving it standing on the terminal point. Reset makes the actor visible again for another run.

LCSTD asset map loading also needed to tolerate local relocations. If `asset_name_map.json` or a `public_space/<name>/default.usd` symlink points at an old absolute path, the bridge resolves it relative to the current asset map directory and the current `static/usd/...` payload without rewriting the unpacked asset library.

## Troubleshooting Checklist

- If no pedestrians appear, confirm `ENABLE_DYNAMIC_AGENTS=true`, `DYNAMIC_AGENT_BACKEND=isaac_people_sumo`, and `DYNAMIC_MAX_PEDESTRIAN_ACTORS` is greater than zero.
- If pedestrians are loaded but not visible, check the route region in the HTML preview and move the Isaac camera to that parcel.
- If fixed assets look wrong, make sure the command does not include `--region-input-json asset_configuration`.
- If generated trips look too short, inspect `pedestrian_walkable_lines` versus `pedestrian_routes` in the HTML preview and tune trip parameters before re-entering Isaac.
- If Isaac People assets do not load, verify `/home/sstormw/isaacsim_assets/Assets/Isaac/5.1/Isaac/People/Characters/` and `/home/sstormw/isaacsim_assets/Assets/Isaac/5.1/Isaac/People/Animations/` exist, or set `ISAAC_ASSET_ROOT` to the local Isaac asset root.

## Validation

Checks used during the current integration:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src/simworld python3 -m unittest discover -s tests

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src/simworld \
python3 -m unittest \
  tests.test_isaac_people_backend \
  tests.test_dynamic_runtime_behaviors \
  tests.test_dynamic_contract

git diff --check
```
