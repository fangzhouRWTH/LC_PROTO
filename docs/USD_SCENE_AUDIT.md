# USD scene audit tool

Standalone check for whether a scene USD can feed `scene_parser` and
`area_placement_methods`, without starting Isaac Sim.

## Run

```bash
scripts/audit_scene_usd.sh \
  --usd assets/blocks/placement_test/001.usd \
  -o assets/blocks/placement_test/001_audit.md
```

Uses Isaac Sim's `python.sh` with `--bootstrap-isaac` (headless Kit loads `pxr`).
Pure system Python works only if OpenUSD is already on `PYTHONPATH`.

Optional: print to terminal:

```bash
scripts/audit_scene_usd.sh --usd path/to/scene.usd --stdout
```

Exit code `0` = no issues; `3` = validation issues listed in the report.

## Module

Implementation: `src/simworld/engine/usd_scene_audit.py`

- Classifies each prim by **pipeline** (area placement, legacy placement, dynamic agents, spawn, static, unrelated).
- Marks attributes as **required / optional / geometry / unrelated** for layout.
- Validates public-space regions and segments the same way as `scene_parser` + `public_space_metadata`.
- Optional **region-input preview** via `algorithm_lab/.../public_space_region_to_region_input`.

## Report sections

| Section | Content |
| --- | --- |
| Summary | Counts, layout-ready regions, issue total |
| Prims by pipeline | What SimWorld subsystem would consume them |
| Global issues | Missing public-space region, etc. |
| Region-input preview | Adapter dry-run (segment count, geometry points) |
| Scene structure | Tree with ✓/✗ per prim |
| Area-placement detail | Attribute table with relevance |
| Unrelated prims | Lights, materials, etc. |

## Related docs

- `algorithm_lab/experiments/area_placement_methods/docs/SCENE_INPUT_AND_ASSET_LIBRARY_HANDBOOK.md` — full input + asset library guide
- `algorithm_lab/experiments/area_placement_methods/docs/USD_PLACEHOLDER_NAMING.md`
- `assets/blocks/placement_test/README.md`
