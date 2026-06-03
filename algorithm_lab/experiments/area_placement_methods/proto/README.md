# Public Space Asset Configuration System

This project generates public-space analysis and layout results from JSON input geometry.

Implemented pipeline:
- `Step 1` segment priority + walkability
- `Step 2` people-point generation
- `Step 3` walking-flow generation
- `Step 4` dynamic/static zone generation
- `Step 5` asset selection + placement

## Files

- `ps_asset_config.py` – main generation pipeline
- `blender_importer.py` – Blender importer for raw input JSON
- `blender_exporter.py` – Blender visualizer for step `1 2 3 4 5` outputs
- `function definition.md` – functional specification

## Usage

Run the generator:

```bash
python ps_asset_config.py 01_block_entrance_01.json --steps 1 2 3 4 5 --output_json out.json
```

Parameters:
- `input_json` – source JSON path
- `--steps` – steps to execute
- `--output_json` – output JSON path
- `--flow_pattern` – optional step-3 override, for example `orthogonal`

Examples:

```bash
python ps_asset_config.py 01_block_entrance_01.json --steps 1 --output_json step1.json
python ps_asset_config.py 05_city_street_roof_01.json --steps 1 2 3 --output_json step3.json
python ps_asset_config.py 15_city_yard_roofless_01.json --steps 1 2 3 4 5 --output_json step5_15.json
```

Visualize raw input:

```bash
blender --python blender_importer.py -- 01_block_entrance_01.json
```

Visualize generated output:

```bash
blender --python blender_exporter.py -- out.json
```

## Input JSON

Input schema:

```json
{
  "public_space_type": "block_entrance | city_street_roof | city_street_roofless | city_yard_roof | city_yard_roofless | building_entrance",
  "public_space_geometry": {
    "type": "LineString3D",
    "coordinates": [[x, y, z], [x, y, z], "..."]
  },
  "public_space_segments": [
    {
      "segment_id": 1,
      "geometry": {
        "type": "LineString3D",
        "coordinates": [[x, y, z], [x, y, z]]
      },
      "boundary_type": "..."
    }
  ],
  "ratio_dynamic_static": 0.36,
  "cover_geometry": {},
  "asset_has_set": []
}
```

Notes:
- `asset_candidates_list` is no longer required in input JSON.
- Asset candidates are now embedded in `ps_asset_config.py`.
- `asset_has_set` is optional and is used by step 2 / step 3 for arcade columns and obstacle-aware flow fallback.

## Output JSON

The output keeps the original input fields and appends computed results.

Main appended fields:

```json
{
  "people_points": [],
  "flow_pattern": "cross | fishbone | ring | orthogonal",
  "walking_lines": [],
  "walking_main_line": {},
  "dynamic_zone_width": 0.0,
  "dynamic_area_target": 0.0,
  "dynamic_area_estimated": 0.0,
  "static_area_estimated": 0.0,
  "dynamic_zones": [],
  "static_zones": [],
  "asset_list": []
}
```

`asset_list` item shape:

```json
{
  "asset_id": 1,
  "asset_candidates_name": "seat_group",
  "asset_URL": "https://example.com/assets/seat_group/xxxx.glb",
  "geometry": { "type": "LineString3D", "coordinates": [] },
  "asset_location": [x, y, z],
  "asset_orientation": [x, y, z],
  "zone_type": "dynamic | static | fallback",
  "zone_id": 1
}
```

## Step Summary

### Step 1

- Maps `boundary_type` to `priority`
- Sets `walkable = false` only for `building_wall`

Priority mapping:
- `0`: `block_entrance`, `building_entrance_main`
- `2`: `street_boundary_primary`
- `4`: `yard_boundary`, `block_boundary_secondary`
- `6`: `block_boundary_primary`, `street_boundary_secondary`
- `8`: `building_other_type`, `block_boundary_other`
- `15`: `building_wall`

### Step 2

- Generates people points from segment length
- Special case: if nearby `arcade_column` exists, the segment is split by the column projections and the midpoint of each valid sub-segment is generated

Length-based fallback:
- `< 25m` → 1 midpoint
- `25m ~ 75m` → 2 points
- `> 75m` → 3 points

### Step 3

Implemented flow patterns:
- `cross`
- `fishbone`
- `ring`
- `orthogonal`

Notes:
- `block_entrance` uses `cross`
- `city_street_*` uses `fishbone`
- other space types choose among `fishbone`, `ring`, `orthogonal`
- non-ring flows fall back to `ring` if they cross non-arcade obstacles
- `orthogonal` now follows the implemented rule:
  - adjacent/opposite cases are separated
  - perpendicular direction must be perpendicular to the source segment
  - in adjacent case, the two unconnected directions are processed first
  - later points try perpendicular connection to all existing flows first, then fall back to bend connection

### Step 4

- Solves dynamic corridor width from step-3 walking lines
- Builds merged dynamic zones from corridor geometry
- Builds remaining static zones from uncovered rectangular cells

### Step 5

- Asset candidates are embedded in `ps_asset_config.py`
- Each placed asset gets:
  - fake test URL
  - placed geometry
  - location
  - orientation
  - zone reference

Implemented custom rules include:
- `city_street_roof` → no assets
- `city_street_roofless` → boundary greenery / rail / street-light logic
- `block_entrance` → static-zone allocation with block-boundary filtering
- `building_entrance` → `vending_machine` and `smart_locker` wall-offset placement
- `city_yard_roof` → static-zone fill, wall-side vending machine, dynamic food cart
- `city_yard_roofless` → exclusive static-zone filling, central sculpture, boundary greenery / rail / light / trash / hydrant

## Blender Output

`blender_exporter.py` currently renders:
- `public_space_segments`
- `people_points`
- `walking_lines`
- `dynamic_zones`
- `static_zones`
- `asset_list`

## Notes

- No third-party Python dependency is required
- Tested with local sample JSON files in this workspace
- Current geometry logic is rectangle / bbox based, not full polygon boolean modeling

**Last Updated**: June 3, 2026
