# Minimal Blender Test Scene for Area Placement

One public-space region you can export to USD and load in Isaac to see **3 dummy placement cubes** (`block_entrance` golden case).

---

## 1. Is everything encoded in names?

**No.** Naming only satisfies the parser **pattern** (`placeholder_area_publicspace_001`).  
**Semantic** fields come from **custom properties** (exported as USD `simworld:*` attributes) and **mesh geometry** (world-space vertices).

| Information | How you provide it |
| --- | --- |
| “This prim is a public-space region” | Object name `placeholder_area_publicspace_*` |
| Space type (`block_entrance`, …) | Custom prop → `simworld:public_space_type` |
| Dynamic/static ratio | Custom prop → `simworld:ratio_dynamic_static` |
| Boundary edge role | Custom prop → `simworld:boundary_type` on each segment |
| Segment index | Custom prop → `simworld:segment_id` |
| Region outline | **Mesh** vertices (quad) |
| Segment line | **Mesh** with 2 endpoints (child of region) |
| Optional columns / obstacles | Child `placeholder_assetset_line_*` + `simworld:asset_has_set_type` |

You do **not** need a separate JSON file if the USD is authored correctly.  
(JSON path `--region-input-json` is an alternative entry, not required together with USD.)

---

## 2. Minimal Blender hierarchy

```text
Scene
└─ Collection: PublicSpaceTest
   └─ placeholder_area_publicspace_001    ← Mesh, 10 m × 10 m quad, Z = 0
      ├─ placeholder_segment_edge_001      ← Mesh line, 2 verts
      ├─ placeholder_segment_edge_002
      ├─ placeholder_segment_edge_003
      └─ placeholder_segment_edge_004
```

Optional (visual context only, **not** used by area placement):

```text
└─ static_ground_plane_001                 ← any static ground mesh; no publicspace attrs
```

Optional (robot spawn, unrelated to layout):

```text
└─ placeholder_spot_spawn_001              ← if you run full sim with Spot
```

---

## 3. Geometry (apply scale before export)

Use **one flat quad** for the region and **four edge lines**. Suggested coordinates (meters, world = Blender global after apply transforms):

**Region** `placeholder_area_publicspace_001` — face corners (CCW when seen from +Z):

| Corner | X | Y | Z |
| --- | --- | --- | --- |
| A | 0 | 0 | 0 |
| B | 10 | 0 | 0 |
| C | 10 | 10 | 0 |
| D | 0 | 10 | 0 |

**Segments** (each object: one edge, mesh with only 2 vertices at endpoints):

| Object | Endpoint 1 | Endpoint 2 | `boundary_type` |
| --- | --- | --- | --- |
| `placeholder_segment_edge_001` | (0,0,0) | (0,10,0) | `block_boundary_primary` |
| `placeholder_segment_edge_002` | (0,10,0) | (10,10,0) | `street_boundary_primary` |
| `placeholder_segment_edge_003` | (10,10,0) | (10,0,0) | `street_boundary_primary` |
| `placeholder_segment_edge_004` | (10,0,0) | (0,0,0) | `block_boundary_other` |

Segment mesh can be a thin quad or a line with 2 verts; parser dedupes to a line.

---

## 4. Custom properties (Blender → USD)

On each object, add **Custom Properties** (must survive export as prim attributes):

### Region root

| Blender custom property | Type | Value |
| --- | --- | --- |
| `simworld:public_space_type` | string | `block_entrance` |
| `simworld:ratio_dynamic_static` | float | `0.7` |

### Each segment child

| Property | Type | Example on `edge_001` |
| --- | --- | --- |
| `simworld:segment_id` | int | `1` |
| `simworld:boundary_type` | string | `block_boundary_primary` |

Use `2` / `street_boundary_primary`, `3` / `street_boundary_primary`, `4` / `block_boundary_other` on the other three.

**Export note:** Your USD exporter must write these as prim attributes (e.g. `custom:simworld:public_space_type`). After export, confirm in UsdView/Isaac that attributes exist; naming alone is not enough.

---

## 5. Data format summary (concise)

```text
Per region instance
├── name:     placeholder_area_publicspace_<index>     [required, pattern]
├── attrs:    simworld:public_space_type               [required, enum string]
│             simworld:ratio_dynamic_static             [required, 0..1]
├── mesh:     ≥3 coplanar boundary vertices           [required, world space]
└── children[]
    └── per segment
        ├── name:   placeholder_segment_edge_<index>   [required, pattern]
        ├── attrs:  simworld:segment_id                [required, int]
        │           simworld:boundary_type              [required, enum string]
        ├── parent: under region root                   [required]
        └── mesh:   2 endpoints (line)                  [required, world space]

Optional per region
└── child placeholder_assetset_line_<index>
    ├── attrs: simworld:asset_has_set_id, simworld:asset_has_set_type
    └── mesh:  polyline (e.g. arcade_column row)
```

**Not in naming:** `public_space_type`, `boundary_type`, ratios — **attributes only**.  
**Not in attributes:** corner coordinates — **mesh geometry only**.

---

## 6. What you do not need for this minimal test

| Item | Needed? |
| --- | --- |
| Sidecar JSON in repo | No (USD carries data) |
| Real asset GLB/USD for placements | No (SimWorld uses Dummy cubes) |
| `placeholder_area_plaza_*` | No (legacy backend) |
| `asset_has_set` children | No for `block_entrance` golden |
| Materials / colors | No (algorithm ignores) |
| Segment semantics in material names | No (use attributes) |

---

## 7. Export and run

1. Blender: Apply all transforms (Ctrl+A → All Transforms).
2. Export USD (Z-up, meters).
3. Isaac:

```bash
scripts/run_sim.sh \
  --scene-usd /path/to/PublicSpaceTest.usd \
  --layout-backend area_placement_methods \
  --use-dummy-public-space-assets true \
  --layout-output-dir outputs/area_placement/blender_test \
  --skip-legacy-placeholder-areas true \
  --sensor-profile none
```

---

## 8. Expected result (compare here)

| Check | Expected |
| --- | --- |
| Log | `Public-space regions: 1` … `segments=4` |
| Log | `Built placement plan from 1 parsed public-space region(s)` |
| Log | `Applied 3 public-space placement(s)` |
| Viewport | **3 cubes** (~0.5 m) inside/near the 10×10 m quad |
| Stage | `/World/GeneratedAssets/PublicSpace/asset_*/DummyGeom` |
| Asset names in plan | `bollard`, `traffic_light_vehicle`, `traffic_light_pedestrian` |

If you see **0 regions** → names or attributes missing on export.  
If you see **regions but segments=0** → segments not parented or missing `boundary_type`.  
If you see **0 placements** → segment geometry invalid or wrong `public_space_type`.

---

## 9. `boundary_type` allowed values

`block_entrance`, `street_boundary_primary`, `street_boundary_secondary`, `block_boundary_primary`, `block_boundary_secondary`, `block_boundary_other`, `building_entrance_main`, `building_wall`, `building_other_type`, `yard_boundary`, `block_other_type`

See `proto/function definition.md` for semantics.
