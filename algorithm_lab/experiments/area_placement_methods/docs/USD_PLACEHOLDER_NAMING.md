# USD / Blender Placeholder Naming

Convention for exporting public-space regions from Blender into USD so `scene_parser` and area placement adapters can recover proto-shaped input.

**Decision:** Option A — parser-friendly prim names + **custom USD attributes** for types that do not fit `category` regex.

---

## Parser baseline

Existing pattern (`scene_parser.NAME_PATTERN`):

```text
<mobility>_<domain>_<category>_<index>
```

- `mobility`, `domain`, `category`: letters only `[a-zA-Z]+`
- `index`: alphanumeric `[0-9a-zA-Z]+`

Therefore `city_street_roof` **cannot** be a single `category` token. Use attributes (below).

---

## Region root prim

| Item | Value |
| --- | --- |
| **Prim name** | `placeholder_area_publicspace_<index>` |
| **Example** | `placeholder_area_publicspace_001` |
| **USD type** | `Mesh` (quad or n-gon) or Xform + child Mesh |
| **Parser rule** | `mobility=placeholder`, `domain=area`, `category=publicspace` |
| **Storage** | `SceneStats.public_space_regions` |

### Custom attributes (namespace `simworld:`)

| Attribute | Type | Required | Example |
| --- | --- | --- | --- |
| `simworld:public_space_type` | token/string | yes | `block_entrance` |
| `simworld:ratio_dynamic_static` | float | yes | `0.36` |
| `simworld:region_id` | string | no | Same as prim name |

Allowed `public_space_type` values (proto enum):

- `block_entrance`
- `city_street_roof`
- `city_street_roofless`
- `city_yard_roof`
- `city_yard_roofless`
- `building_entrance`

---

## Boundary segment prims

Each boundary edge is a **child** of the region root.

| Item | Value |
| --- | --- |
| **Prim name** | `placeholder_segment_edge_<index>` |
| **Example** | `placeholder_segment_edge_001` |
| **Geometry** | Open line: 2 vertices (world space) or `BasisCurves` |
| **Attributes** | |

| Attribute | Type | Required | Example |
| --- | --- | --- | --- |
| `simworld:segment_id` | int | yes | `1` |
| `simworld:boundary_type` | token | yes | `street_boundary_primary` |

`boundary_type` enum (proto): see `proto/function definition.md`.

### Segment ↔ proto mapping

| USD | Proto JSON |
| --- | --- |
| `simworld:segment_id` | `segment_id` |
| Line world coords (2 points) | `geometry.coordinates` |
| `simworld:boundary_type` | `boundary_type` |

---

## Asset has-set prims (optional)

Pre-placed columns, canopies, etc.

| Item | Value |
| --- | --- |
| **Prim name** | `placeholder_assetset_<index>` |
| **Example** | `placeholder_assetset_001` |
| **Attributes** | |

| Attribute | Type | Example |
| --- | --- | --- |
| `simworld:asset_has_set_id` | int | `1` |
| `simworld:asset_has_set_type` | token | `arcade_column` |

Geometry: mesh or line repeating along segment (see `proto/sample_data.md`).

---

## Outer boundary mesh

The region root mesh supplies `public_space_geometry`:

1. Export **ordered** boundary vertices in world space (CCW or CW consistent per file).
2. Close the ring (repeat first point at end) when writing `region_input`.
3. Adapter may simplify coplanar mesh to `LineString3D` on the dominant plane (Z or fitted normal).

---

## Blender export checklist

1. One collection per public space instance; collection name mirrors `region_id`.
2. Region mesh object name: `placeholder_area_publicspace_001`.
3. Set custom properties → exported as `simworld:*` USD attributes (script responsibility).
4. Segment objects: line meshes, two vertices, parented under region.
5. World coordinates; apply transforms before export.
6. Do not embed segment semantics only in material names — use `simworld:boundary_type`.

---

## Legacy placeholders

| Existing prim | Behavior |
| --- | --- |
| `placeholder_area_plaza_001` | Keeps current path: grid footprints via `scene_generator` |
| `placeholder_area_sidewalk_*` | Dynamic/pedestrian semantics only (no area placement) |

New public-space regions use `publicspace` category + attributes; they do not use `plaza` category.

---

## Parser implementation notes (Phase 5)

1. Add `PlaceholderPublicSpace` dataclass (extends area + typed fields).
2. Read `simworld:*` via `prim.GetAttribute()` in adaptor layer.
3. Fall back with warning if segments missing (adapter may infer from mesh edges — best-effort only).

---

## Changelog

| Date | Change |
| --- | --- |
| 2026-06-03 | Adopt Option A (attributes + `publicspace` category) |
