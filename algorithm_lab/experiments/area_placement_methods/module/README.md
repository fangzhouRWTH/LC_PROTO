# Area Placement Module

Isaac-free wrapper around `../proto/ps_asset_config.py`.

**Full authoring reference (scene input + asset library):**  
[../docs/SCENE_INPUT_AND_ASSET_LIBRARY_HANDBOOK.md](../docs/SCENE_INPUT_AND_ASSET_LIBRARY_HANDBOOK.md)

## Run from repository root

```bash
python3 algorithm_lab/experiments/area_placement_methods/module/run.py \
  algorithm_lab/experiments/area_placement_methods/proto/01_block_entrance_01.json \
  --steps 1 2 3 4 5 \
  -o algorithm_lab/outputs/area_placement_01.json \
  --to-placement-output algorithm_lab/outputs/area_placement_01.plan.json
```

## Python API

```python
from pathlib import Path
import sys

module_dir = Path("algorithm_lab/experiments/area_placement_methods/module")
sys.path.insert(0, str(module_dir))

from generator import run_public_space_layout_from_file
from adapters.asset_list_to_plan import layout_result_to_placement_output

layout = run_public_space_layout_from_file(".../01_block_entrance_01.json")
plan = layout_result_to_placement_output(layout, region_id="region_001")
```

## Re-sync from proto

When `proto/ps_asset_config.py` changes, re-run tests:

```bash
PYTHONPATH=src/simworld python3 -m unittest tests.test_area_placement_module -v
```

No copy step is required while the module loads proto via `importlib`.

## Isaac Sim (Phase 4)

From repository root:

```bash
scripts/run_sim.sh \
  --layout-backend area_placement_methods \
  --region-input-json algorithm_lab/experiments/area_placement_methods/proto/01_block_entrance_01.json \
  --use-dummy-public-space-assets true \
  --layout-output-dir outputs/area_placement \
  --sensor-profile none
```

Placements appear under `/World/GeneratedAssets/PublicSpace/` as dummy cubes unless
`--public-space-asset-name-map` provides real USD paths and dummy mode is off.

When the scene USD already contains `placeholder_area_publicspace_*` prims with
`simworld:*` attributes and child segment prims, omit `--region-input-json`:

```bash
scripts/run_sim.sh --layout-backend area_placement_methods --use-dummy-public-space-assets true
```

See `../docs/BLENDER_EXPORT_CHECKLIST.md` for export authoring.

## Empty `asset_list` and debug placeholder

If step 5 returns no assets (wrong `public_space_type`, missing segments, or steps
without `5`), the adapter injects one placement named `isaac_builtin_placeholder` at
the region polygon centroid. In Isaac this becomes a **UsdGeom.Cube** under
`/World/GeneratedAssets/PublicSpace/` when `--use-dummy-public-space-assets true`
(default). No instance asset or `assets/library` entry is required.

`city_street_roof` is excluded (proto intentionally places zero assets).

To trace the root cause instead of relying on the cube:

```bash
python3 algorithm_lab/experiments/area_placement_methods/module/run.py \
  your_region.json --steps 1 2 3 4 5 -o /tmp/layout.json
```

Check `asset_list`, `dynamic_zones`, `static_zones`, and `warnings` in the layout JSON.

## Real asset library (optional)

Two paths exist in SimWorld:

| Path | Used by | How to build |
| --- | --- | --- |
| **Public-space name map** | `area_placement_methods` executor | Copy `module/contracts/asset_name_map.example.json` → your map. Keys must match proto `asset_candidates_name` (e.g. `bollard`, `traffic_light_vehicle`). Values are absolute paths to `.usd` files. |
| **Legacy `AssetLibrary`** | `layout_backend=legacy` placeholder areas | Under repo `assets/library/`, one subfolder per category: `assets/library/bench/bench_01.usd`. `AssetLibrary.scan_folder()` uses the **parent folder name** as category. |

**Import in Isaac (public-space backend):**

```bash
scripts/run_sim.sh \
  --layout-backend area_placement_methods \
  --use-dummy-public-space-assets false \
  --public-space-asset-name-map /path/to/asset_name_map.json \
  ...
```

Unmapped names still fall back to a dummy cube. Prepare one USD per candidate you expect
from the algorithm; scale/anchor are not adjusted yet—place assets near origin in the
source USD or tune transforms later.

**Legacy import** uses `AssetPlacementPlanner` + `SceneAssetAllocator.import_plans()` after
`library.scan_folder(asset_root)` in `SimScene` (see `README.md` asset library section).
