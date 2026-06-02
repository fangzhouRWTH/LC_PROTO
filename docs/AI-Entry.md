---
anyplan.index: true
anyplan.role: task-scope
anyplan.title: AI Entry
anyplan.summary: Zero-context onboarding for LC_01 SimWorld. Read order, depth, and path bindings for Isaac Sim simulation development.
---

# AI Entry

Default onboarding for AI collaborators on **LC_01 SimWorld** with **no prior context**. This file is **meta navigation only**—not USD naming rules, Isaac APIs, or placement algorithms.

**Owner shortcut:** “Follow `docs/AI-Entry.md`, then do the task.”

## 1. Default Read Order

| Step | Memory type | Path |
| --- | --- | --- |
| 1 | Central contract (structured) | [instances/lc01-simworld/guidance.json](../instances/lc01-simworld/guidance.json) |
| 2 | AI entry | This file |
| 3 | Project state | [docs/ProjectState.md](ProjectState.md) |
| 4 | Routing manifest | [docs/GuidanceManifest.md](GuidanceManifest.md) |
| 5 | Operator README | [README.md](../README.md) — run commands, env vars, CLI flags |
| 6 | Architecture | [doc/Architecture.md](../doc/Architecture.md) — module boundaries, data flow |
| 7 | Dashboard (structured) | [instances/lc01-simworld/dashboard.json](../instances/lc01-simworld/dashboard.json) |
| 8 | Task-specific module doc | See §7 below |
| 9 | Code under `src/simworld/` | Only modules you will edit |

## 2. Read Depth

| Memory type | Depth | Expand when |
| --- | --- | --- |
| `guidance.json` | Full | Always for non-trivial work |
| `ProjectState.md` | Full | Always |
| `GuidanceManifest.md` | Full once; skim if unchanged | First session or doc changes |
| `README.md` | Sections needed (run, install, sensors) | Running or debugging sim |
| `doc/Architecture.md` | On-demand sections | Cross-module or pipeline changes |
| `doc/DynamicAgents.md` | Full | Any `isaac_agents` / `engine/dynamic.py` work |
| Module READMEs (`isaac_sensor_sim`, `isaac_vfx`, …) | Full for that module | Touching that package |
| `algorithm_lab/guideline.md` | Full | Adding or changing lab experiments |
| `docs/adr/` | Targeted ADR | Binding decision |
| `docs/refactoring/` | On-demand | Doc layout or engineering refactor tasks |
| `doc/weekly_reports/` | Archive | Internal history only |
| `instances/.../doc-index.json` | Do not read as narrative | Regenerate via Anyplan `build-doc-index.py` |

## 3. Do Not Read By Default

- Entire `assets/` tree (large binaries; use `asset_config.yaml` and scripts)
- All of `algorithm_lab/experiments/` unless task is lab-scoped
- `outputs/` runtime artifacts
- `doc/weekly_reports/` (gitignored internal reports)
- Isaac Sim kit sources outside this repo
- Full `tests/` suite when changing unrelated modules

## 4. Context Expansion Triggers

Read deep architecture or module docs when the task:

- Changes `isaac_adaptor` boundary or imports Isaac/Omniverse APIs outside adaptor
- Modifies `SceneStats`, `DynamicScenePlan`, asset import contracts, or sensor frame contracts
- Adds robots, sensors, VFX, or dynamic backends
- Touches `scripts/run_sim.sh` / `SimulationConfig` defaults
- Contradicts `ProjectState.md` or README run instructions
- Needs phased refactor context → [docs/refactoring/PHASED-REFACTORING.md](refactoring/PHASED-REFACTORING.md)

## 5. Optional Packs (This Instance)

| Pack | Enabled | Path |
| --- | --- | --- |
| Guidance manifest | Yes | [docs/GuidanceManifest.md](GuidanceManifest.md) |
| Phase context (prose) | No (use dashboard + ProjectState) | — |
| Active bug reports | No (enable in Phase 2 refactor) | — |
| Visual Anyplan dashboard | Yes | Anyplan `scripts/serve.sh lc01-simworld` from framework repo |

## 6. Module Quick Map (read on demand)

| Area | Path |
| --- | --- |
| CLI / config | `src/simworld/main.py`, `isaac_env/simulation.py` |
| Isaac API boundary | `isaac_env/isaac_adaptor/` |
| Scene / USD | `isaac_env/isaac_scene/` |
| Placement algorithms | `engine/placement.py` |
| Dynamic plans | `engine/dynamic.py`, `doc/DynamicAgents.md` |
| Dynamic runtime | `isaac_env/isaac_agents/` |
| Robots | `isaac_env/isaac_robots/` |
| Sensors | `isaac_env/isaac_sensor_sim/` |
| Weather / particles | `isaac_env/isaac_vfx/` |
| Algorithm lab | `algorithm_lab/` (no Isaac imports) |
| Unit tests (no Isaac) | `tests/`, `PYTHONPATH=src/simworld` |

## 7. Validation

```bash
# Engine / contract tests (no Isaac Sim required)
cd /home/fangzhou/projects/LC_01
PYTHONPATH=src/simworld python3 -m unittest discover -s tests -v

# After guidance/dashboard edits (from Anyplan repo)
/path/to/Anyplan/scripts/validate-guidance.sh instances/lc01-simworld/guidance.json
/path/to/Anyplan/scripts/validate-dashboard.sh instances/lc01-simworld/dashboard.json
python3 /path/to/Anyplan/scripts/build-doc-index.py --project-id lc01-simworld --repo-root .
```

Runtime sim (requires Isaac Sim `python.sh`):

```bash
scripts/run_sim.sh --help   # if supported; else see README
ISAAC_PYTHON=/path/to/isaacsim/python.sh scripts/run_sim.sh
```

## 8. After Context Recovery

1. **TaskBrief** — intent, scope, acceptance, unknowns  
2. **RetrievalScope** — files read and why  
3. Check **guidance.json** constraints (Isaac boundary, lab isolation, tests)  
4. Implement; prefer `engine/` + `tests/` when algorithms allow  
5. Update **ProjectState**, **dashboard.json**, **collaboration log**, ADR if durable  
