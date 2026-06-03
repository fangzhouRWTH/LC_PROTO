# Area Placement Methods

Migrate the public-space layout pipeline from `proto/` into a production-callable module, wired to `scene_parser` and SimWorld asset placement.

## Quick links

| Document | Purpose |
| --- | --- |
| [MIGRATION_PLAN.md](MIGRATION_PLAN.md) | Phased roadmap, progress table, test plan, open issues |
| [docs/E2E_TEST_PLAN.md](docs/E2E_TEST_PLAN.md) | **Full-chain test plan**: inputs, commands, expected visuals, scoring rubric |
| [proto/README.md](proto/README.md) | Proto algorithm usage (steps 1–5, JSON I/O) |
| [proto/function definition.md](proto/function%20definition.md) | Functional specification |
| [proto/sample_data.md](proto/sample_data.md) | Sample geometry descriptions |

## Directory layout (target)

```text
area_placement_methods/
  README.md                 # this file
  MIGRATION_PLAN.md         # roadmap + tracking
  docs/                     # contracts and USD naming (Phase 0)
  proto/                    # reference implementation + golden JSON samples
  module/                   # migrated callable package (Phase 1+)
  outputs/                  # local generated plans (gitignored if large)
```

## Related production code

| Area | Path |
| --- | --- |
| Scene parsing | `src/simworld/isaac_env/isaac_scene/scene_parser.py` |
| Current grid layout | `src/simworld/isaac_env/isaac_scene/scene_generator.py` |
| Footprints / import plans | `src/simworld/engine/placement.py` |
| Scene prepare pipeline | `src/simworld/isaac_env/isaac_scene/scene.py` |
| Architecture | `doc/Architecture.md` §4.1, §5.2 |

## Status

| Phase | State |
| --- | --- |
| 0 Contracts | done |
| 1 Module + tests | done |
| 2 Placement apply | in progress (`isaac_scene/public_space_placement_executor.py`) |
| 3 Scene adapter | done |
| 4 SimScene flag | done |
| 5 USD parse + Blender checklist | done |

See [MIGRATION_PLAN.md](MIGRATION_PLAN.md) for details.

**Last updated:** 2026-06-03
