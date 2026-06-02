# Project State

Operational snapshot for LC_01 SimWorld. Structured progress: `instances/lc01-simworld/dashboard.json`.

## Active Phase

- **Phase name**: Anyplan adoption and documentation consolidation (`phase-0-anyplan`)
- **Goal**: Instantiate Anyplan; keep existing `doc/` architecture; add `docs/` for AI collaboration; plan phased refactors
- **Status**: Active

## Current Priorities

1. Use `docs/AI-Entry.md` for all new AI sessions
2. Keep `doc/Architecture.md` and `doc/DynamicAgents.md` as architecture source of truth
3. Run unit tests before Isaac runtime changes when touching `engine/` or `isaac_agents/`
4. Execute [docs/refactoring/PHASED-REFACTORING.md](refactoring/PHASED-REFACTORING.md) only when scheduled—not in every task

## Do Not Reopen Casually

- Algorithm vs Isaac separation (`engine/` + `algorithm_lab` vs `isaac_env/`)
- Centralized Isaac imports through `isaac_adaptor/`
- English durable documentation
- `Input -> Contract -> Apply -> Runtime Update` integration pattern (see Architecture)

## Open Questions

- Whether to add `docs/WorkingContract.md` prose or keep `guidance.json` as sole contract
- CI workflow for `unittest` on push
- Whether to enable ActiveBugReports for Isaac debugging handoffs

## Validation (Current Phase)

```bash
cd /home/fangzhou/projects/LC_01
PYTHONPATH=src/simworld python3 -m unittest discover -s tests -v
```

Isaac runtime (owner machine):

```bash
ISAAC_PYTHON=/path/to/isaacsim/python.sh scripts/run_sim.sh
# Debug: scripts/run_sim_dbg.sh
```

Anyplan artifacts (from Anyplan framework repo):

```bash
ANYPLAN=/home/fangzhou/projects/Anygine/Anyplan
python3 "$ANYPLAN/scripts/build-doc-index.py" --project-id lc01-simworld --repo-root .
"$ANYPLAN/scripts/validate-guidance.sh" instances/lc01-simworld/guidance.json
"$ANYPLAN/scripts/validate-dashboard.sh" instances/lc01-simworld/dashboard.json
```

## Risks

- `doc/` vs `docs/` dual roots until Phase B refactor completes
- No CI yet—regressions rely on local unittest + manual Isaac runs
- Large gitignored `assets/`—AI must not assume assets are in version control

## Document Routing

| Need | Read first |
| --- | --- |
| Zero-context AI | `docs/AI-Entry.md` |
| Central rules | `instances/lc01-simworld/guidance.json` |
| Routing table | `docs/GuidanceManifest.md` |
| Run / install | `README.md` |
| Architecture | `doc/Architecture.md` |
| Dynamic agents | `doc/DynamicAgents.md` |
| Refactor plan | `docs/refactoring/PHASED-REFACTORING.md` |
| Decisions | `docs/adr/` |

Last updated: 2026-06-01
