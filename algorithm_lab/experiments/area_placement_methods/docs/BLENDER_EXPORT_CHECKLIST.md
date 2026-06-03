# Blender → USD Public-Space Export Checklist

Use with [USD_PLACEHOLDER_NAMING.md](USD_PLACEHOLDER_NAMING.md). Custom properties on Blender objects should export to USD as `custom:simworld:*` attributes (exporter-dependent; verify in UsdView).

## Region root

| Blender object name | USD prim example |
| --- | --- |
| `placeholder_area_publicspace_001` | `/World/.../placeholder_area_publicspace_001` |

Custom properties:

| Property | Example |
| --- | --- |
| `simworld:public_space_type` | `block_entrance` |
| `simworld:ratio_dynamic_static` | `0.7` |

Mesh: ordered boundary quad/ring in world space (Z-up).

## Boundary segment (child of region)

| Blender object name | USD prim example |
| --- | --- |
| `placeholder_segment_edge_001` | child under region |

Custom properties:

| Property | Example |
| --- | --- |
| `simworld:segment_id` | `1` |
| `simworld:boundary_type` | `street_boundary_primary` |

Mesh/curve: two endpoints of the segment line in world space.

## Asset has-set (optional child)

| Blender object name | USD prim example |
| --- | --- |
| `placeholder_assetset_line_001` | child under region |

Custom properties:

| Property | Example |
| --- | --- |
| `simworld:asset_has_set_id` | `1` |
| `simworld:asset_has_set_type` | `arcade_column` |

Geometry: polyline along column row (see proto `asset_has_set` samples).

## SimWorld run (no manual JSON)

When the exported USD is loaded:

```bash
scripts/run_sim.sh \
  --layout-backend area_placement_methods \
  --use-dummy-public-space-assets true \
  --sensor-profile none
```

Parser fills `SceneStats.public_space_regions` and layout runs automatically.

## Verify in log

After `SimScene.prepare`, expect:

```text
Public-space regions: N
  /World/.../placeholder_area_publicspace_001 type=block_entrance segments=4 ...
[INFO] Built placement plan from N parsed public-space region(s)
```
