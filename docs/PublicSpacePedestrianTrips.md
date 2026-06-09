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

The LCSTD directory name currently includes a trailing dot: `assets/lcstd_assets_library.`. Keep that spelling unless the command line is updated too.

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

These presets are demo-only. For the short-term demo, the six final route sets are precomputed and checked in under:

```text
configs/demo_people/generated/tencent_people_1_placement_plan.json
configs/demo_people/generated/tencent_people_2_placement_plan.json
configs/demo_people/generated/tencent_people_3_placement_plan.json
configs/demo_people/generated/tencent_people_4_placement_plan.json
configs/demo_people/generated/tencent_people_5_placement_plan.json
configs/demo_people/generated/tencent_people_6_placement_plan.json
```

The static plans include fixed-asset placements plus the final demo `pedestrian_routes`. Runtime does not rerun route generation, collision rehearsal, or local detour insertion when `scripts/run_demo_tencent_dynamic_people.sh` is used with its defaults. It only chooses the precomputed plan matching `DEMO_PEOPLE_SCENARIO`.

The offline generator that produced these plans keeps the main public-space output intact, then postprocesses `pedestrian_walkable_lines` into longer demo routes. Each actor has deterministic values for:

- `offset_m`: lateral route offset, using uneven left/right candidates instead of one fixed lane width
- `start_offset_m`: distance trimmed from the route start, so actors can spawn along the route body instead of only at graph endpoints
- `speed_mps`: per-actor walking speed
- `spawn_time_s`: staggered spawn time
- `collision_rehearsal_detours`: optional local bend points inserted around near-collision locations

Run Isaac with the wrapper script:

```bash
DEMO_PEOPLE_SCENARIO=people_6 \
DYNAMIC_ISAAC_PEOPLE_DEBUG=true \
scripts/run_demo_tencent_dynamic_people.sh
```

The wrapper defaults to `DEMO_PEOPLE_SCENARIO=people_3`, `DEMO_PEOPLE_USE_STATIC_PLAN=true`, `DYNAMIC_ROUTE_MODE=once`, and `DYNAMIC_MAX_PEDESTRIAN_ACTORS=40`. It does not pass external `asset_configuration/` and does not pass `--demo-people-config` unless `DEMO_PEOPLE_USE_STATIC_PLAN=false` is explicitly set.

Render the same demo-selected routes without launching Isaac:

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

To regenerate fixed presets for a different parcel, first produce a clean/main placement plan for that parcel. For USD-scene-derived regions this is typically the `placement_output.json` produced by area placement before applying demo people presets. Then run:

```bash
PYTHONDONTWRITEBYTECODE=1 \
scripts/build_demo_people_static_presets.py \
  --base-placement-plan-json outputs/area_placement/<new_parcel_base>/placement_output.json \
  --demo-people-config configs/demo_people/tencent_dynamic_people_scenarios.json \
  --output-dir configs/demo_people/generated \
  --preset-prefix tencent \
  --summary-json configs/demo_people/generated/tencent_static_preset_summary.json
```

The command writes six fixed placement plans. After that, runtime still only chooses by `DEMO_PEOPLE_SCENARIO`; it does not rerun the rehearsal. If the new parcel should keep both old and new presets, use a different `--preset-prefix` and set `DEMO_PEOPLE_PLACEMENT_PLAN` or `DEMO_PEOPLE_PRESET_DIR` in the wrapper script environment.

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
