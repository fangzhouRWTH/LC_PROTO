# Algorithm Lab Guideline

## Purpose

`algorithm_lab/` is a lightweight workspace for independent algorithm experiments. It exists so algorithm developers can prototype layout, dynamic asset, and environment ideas without touching the main Isaac Sim runtime framework in `src/simworld`.

This folder is intentionally separated from the production path. Experimental code may be rough, but every experiment should still expose clear inputs and outputs so it can later be reviewed, tested, and promoted into the main framework.

## Directory Layout

```text
algorithm_lab/
  guideline.rd
  templates/
    minimal_algorithm.py
  experiments/
    regional_layout/
    dynamic_assets/
    environment/
  sample_data/
    region_input.example.json
  outputs/
```

- `templates/`: small starter scripts that demonstrate the expected command-line and JSON interface style.
- `experiments/regional_layout/`: experiments for plaza, sidewalk, roadside, or other regional static asset placement.
- `experiments/dynamic_assets/`: experiments for pedestrians, vehicles, routes, schedules, and behavior profiles.
- `experiments/environment/`: experiments for weather, lighting, time of day, visibility, and material effects.
- `sample_data/`: small, commit-safe input examples only.
- `outputs/`: local generated files. This folder is ignored except for `.gitkeep`.

## Core Principles

1. Keep Isaac Sim isolated.
   Do not import `isaacsim`, `omni`, `pxr`, or project runtime modules under `src/simworld/isaac_env` from experimental scripts. Algorithms should generate data plans; the main Isaac layer will apply those plans later.

2. Minimize dependencies.
   Prefer the Python standard library. Use `numpy` only when it clearly simplifies numeric logic. Avoid adding heavy dependencies unless the team agrees and the experiment documents why they are needed.

3. Define the interface before the algorithm grows.
   Each experiment should document its input format, output format, units, coordinate convention, random seed behavior, and failure cases. If the interface is unclear, the result will be hard to integrate.

4. Exchange data through explicit files.
   Use JSON for structured plans, CSV for simple tables, and NPZ only for large numeric arrays. Avoid hidden global state, hardcoded absolute paths, and direct edits to USD files.

5. Return plans, not side effects.
   The preferred output is a plan such as `AssetImportPlan`, `DynamicActorPlan`, or `EnvironmentPlan`. The experiment should not create Isaac prims, modify USD stages, or launch Isaac Sim.

6. Keep experiments reproducible.
   Every stochastic algorithm should accept a `seed` field or CLI argument. Given the same input and seed, the output should be stable enough for review.

7. Keep generated data out of git.
   Do not commit large outputs, screenshots, cache files, generated assets, converted USD files, or local notebooks with bulky embedded results. Put generated files under `algorithm_lab/outputs/` or an experiment-local `outputs/` folder.

8. Make promotion easy.
   Once an experiment is useful, extract pure functions, add a small test case, document the schema, and propose the target production module under `src/simworld/engine`.

## Suggested Experiment Structure

For a new experiment, create a subfolder:

```text
algorithm_lab/experiments/regional_layout/my_layout_method/
  README.md
  run.py
  input.example.json
  output.example.json
```

The experiment README should include:

- Owner and status.
- Problem being explored.
- How to run it from the repository root.
- Input and output schema.
- Dependencies beyond the Python standard library.
- Known limitations.
- Suggested integration target, if known.

## Recommended CLI Pattern

Use this command style:

```bash
python algorithm_lab/experiments/regional_layout/my_layout_method/run.py \
  --input algorithm_lab/experiments/regional_layout/my_layout_method/input.example.json \
  --output algorithm_lab/outputs/my_layout_output.json \
  --seed 42
```

The script should:

- Read one explicit input file.
- Write one explicit output file.
- Accept a seed when randomness is used.
- Print a short summary, not a long debug stream.
- Exit with a non-zero status when input validation fails.

## Recommended Data Contracts

Regional layout experiments should aim to output:

```text
StaticAssetPlan
  schema_version
  algorithm
  seed
  footprints or asset_import_plans
  warnings
```

Dynamic asset experiments should aim to output:

```text
DynamicActorPlan
  actor_id
  actor_type
  spawn_time
  despawn_time
  spawn_pose
  route
  speed_profile
  behavior_profile
```

Environment experiments should aim to output:

```text
EnvironmentPlan
  time_of_day
  weather
  sun_rotation
  sun_intensity
  sky_texture
  fog_density
  precipitation
  wetness
```

These names do not need to be final, but experiments should make their output close to one of these plan shapes.

## Review Checklist

Before asking for review or integration, check:

- The script runs from the repository root.
- The script does not import Isaac Sim or modify the main runtime.
- Input and output examples are included and small.
- Units are documented, preferably meters and radians unless stated otherwise.
- Randomness is controlled by a seed.
- Dependencies are listed.
- Generated outputs are not committed unless they are tiny examples.
- The intended production integration point is described.
