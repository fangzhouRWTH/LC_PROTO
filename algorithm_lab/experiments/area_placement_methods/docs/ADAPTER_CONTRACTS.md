# Adapter Contracts

Versioned JSON contracts between SimWorld scene parsing, the area placement algorithm, and USD placement.

**Schema IDs**

| ID | Direction | Owner module |
| --- | --- | --- |
| `simworld.region_input.v1` | Scene / parser → algorithm | `module/adapters/scene_to_region_input.py` |
| `simworld.placement_output.v1` | Algorithm → executor | `module/adapters/asset_list_to_plan.py` |

Native proto JSON (see `proto/README.md`) remains valid for lab runs; adapters may produce identical shapes for debugging.

---

## Coordinate conventions

| Field | Convention |
| --- | --- |
| Units | Meters |
| Axes | Right-handed **world** frame: X, Y horizontal; Z up (matches `scene_parser` world vertices) |
| `LineString3D` | Ordered vertices; first may repeat last for closed rings |
| `asset_location` | World position of asset anchor (proto step 5) |
| `asset_orientation` | Direction vector in world XY (proto); executor derives yaw from XY projection |

---

## `simworld.region_input.v1`

Logical input to `run_public_space_layout()`. Fields align with `public_space_asset_configuration()`.

### Required

| Field | Type | Description |
| --- | --- | --- |
| `schema_version` | string | Must be `simworld.region_input.v1` |
| `region_id` | string | Stable id (e.g. prim path or `placeholder_area_publicspace_001`) |
| `public_space_type` | enum string | See proto README (`block_entrance`, `city_street_roof`, …) |
| `public_space_geometry` | GeoJSON-like object | `type: LineString3D`, closed boundary |
| `public_space_segments` | array | Each: `segment_id`, `geometry`, `boundary_type` |
| `ratio_dynamic_static` | number | Target dynamic area ratio in `[0, 1]` |

### Optional

| Field | Type | Description |
| --- | --- | --- |
| `cover_geometry` | LineString3D | Roof / cover outline |
| `asset_has_set` | array | Pre-placed obstacles (`arcade_column`, …) |
| `seed` | int | Reserved; proto currently derives RNG from geometry strings |
| `metadata` | object | `source_prim_path`, `coordinate_frame`, parser version |

### Example

See `module/contracts/region_input.example.json`.

### Mapping from `SceneStats` (Phase 3)

| region_input field | Source |
| --- | --- |
| `region_id` | `PlaceholderArea.prim_path` or `raw_name` |
| `public_space_type` | USD custom attr `simworld:public_space_type` |
| `public_space_geometry` | Derived closed ring from area mesh boundary |
| `public_space_segments` | Child prims `placeholder_segment_*` or derived edges |
| `ratio_dynamic_static` | Attr `simworld:ratio_dynamic_static` or default `0.36` |
| `asset_has_set` | Child prims `placeholder_assetset_*` |

---

## `simworld.placement_output.v1`

Output of layout step 5, consumed by the placement executor (Isaac layer).

### Required

| Field | Type | Description |
| --- | --- | --- |
| `schema_version` | string | Must be `simworld.placement_output.v1` |
| `region_id` | string | Matches input `region_id` |
| `public_space_type` | string | Echo from input |
| `placements` | array | One entry per placed asset |

### Placement item

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `placement_id` | string | yes | e.g. `asset_0001` |
| `asset_name` | string | yes | `asset_candidates_name` from proto |
| `position` | `[x,y,z]` | yes | World meters |
| `orientation` | `[x,y,z]` | no | Proto direction vector |
| `zone_type` | string | no | `dynamic` / `static` / `fallback` |
| `zone_id` | int | no | Zone reference from step 4 |
| `geometry` | object | no | Footprint LineString3D for debug |
| `asset_url` | string | no | Proto placeholder URL; executor uses library map |

### Optional top-level

| Field | Type | Description |
| --- | --- | --- |
| `layout_steps` | int[] | Steps executed, e.g. `[1,2,3,4,5]` |
| `warnings` | string[] | Non-fatal issues |
| `debug` | object | Optional: `walking_lines`, zone counts |

### Example

See `module/contracts/placement_output.example.json`.

### Mapping from proto result

| placement_output | Proto source |
| --- | --- |
| `placements[].asset_name` | `asset_list[].asset_candidates_name` |
| `placements[].position` | `asset_list[].asset_location` |
| `placements[].orientation` | `asset_list[].asset_orientation` |
| `placements[].zone_type` | `asset_list[].zone_type` |
| `placements[].zone_id` | `asset_list[].zone_id` |
| `placements[].geometry` | `asset_list[].geometry` |
| `placements[].asset_url` | `asset_list[].asset_URL` |

---

## Executor mapping (Phase 2+)

| placement_output | Runtime |
| --- | --- |
| `asset_name` | Lookup in `asset_name_map.json` → `AssetSpec.usd_path` |
| Missing map entry | `DummyAssetFactory` (UsdGeom cube under generated root) |
| `position` + `orientation` | Xform translate + yaw from orientation XY |

---

## Validation rules

1. `public_space_segments` length ≥ 3 for rectangular regions (proto samples use 4).
2. Each segment `geometry.coordinates` has exactly 2 points (segment line).
3. `ratio_dynamic_static` in `[0.0, 1.0]`.
4. `placements` may be empty only when `public_space_type == city_street_roof` (by design).
5. For other types, if `asset_list` is empty, `layout_result_to_placement_output` injects one
   `isaac_builtin_placeholder` at `public_space_geometry` centroid (disable with
   `inject_fallback_when_empty=false`). Isaac applies it as `UsdGeom.Cube` when
   `use_dummy_public_space_assets=true`.

---

## Changelog

| Date | Change |
| --- | --- |
| 2026-06-03 | Initial v1 contracts |
