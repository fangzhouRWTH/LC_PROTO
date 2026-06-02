# Guidance Manifest

Routes LC_01 SimWorld project memory for human and AI collaborators. Separates **authority** from **retrieval depth**.

## Default Startup Path

1. `instances/lc01-simworld/guidance.json`
2. `docs/AI-Entry.md`
3. `docs/ProjectState.md`
4. `README.md` (run/install sections as needed)
5. `doc/Architecture.md` (sections relevant to task)
6. Code and module READMEs for touched areas only

## Source of Truth by Question

| Question | Primary source |
| --- | --- |
| Central rules | `instances/lc01-simworld/guidance.json` |
| How should AI onboard? | `docs/AI-Entry.md` |
| Current phase and priorities? | `docs/ProjectState.md`, `dashboard.json` |
| How to run sim / debug? | `README.md`, `scripts/run_sim.sh` |
| Module boundaries and pipeline? | `doc/Architecture.md` |
| Dynamic pedestrians / vehicles? | `doc/DynamicAgents.md` |
| Sensors? | `src/simworld/isaac_env/isaac_sensor_sim/README.md` |
| Weather / particles? | `isaac_vfx/README.md` |
| Lab experiments (no Isaac)? | `algorithm_lab/guideline.md` |
| Binding decisions? | `docs/adr/` |
| Phased engineering refactor? | `docs/refactoring/PHASED-REFACTORING.md` |

## Document Map

| Document | Tier | Default read |
| --- | --- | --- |
| `guidance.json` | Task scope | Always |
| `docs/AI-Entry.md` | Task scope | Always (zero-context) |
| `docs/ProjectState.md` | Task scope | Always |
| `README.md` | Task scope | When running or configuring sim |
| `doc/Architecture.md` | Deep source | On demand (pipeline / boundary tasks) |
| `doc/DynamicAgents.md` | Deep source | Dynamic agent tasks |
| Module READMEs under `isaac_env/` | Deep source | Editing that module |
| `algorithm_lab/guideline.md` | Phase context | Lab work |
| `docs/adr/*` | Deep source | Decisions |
| `docs/refactoring/PHASED-REFACTORING.md` | Phase context | Refactor tasks only |
| `doc/weekly_reports/*` | Archive | Internal only |

## Context Expansion Triggers

Expand beyond startup when a task:

- Adds Isaac API usage outside `isaac_adaptor/`
- Changes data contracts (`SceneStats`, plans, sensor frames)
- Modifies default sim configuration or launch scripts
- Integrates new robot, sensor profile, or dynamic backend
- Contradicts ProjectState or Architecture
- Schedules a refactor phase from PHASED-REFACTORING.md

## Update Rules

- **ProjectState** — phase, priorities, validation commands change
- **dashboard.json** — task/phase status changes
- **guidance.json** — durable rules, document map, constraints
- **Architecture / DynamicAgents** — only when design or contracts change
- **README** — when run paths or CLI flags change
