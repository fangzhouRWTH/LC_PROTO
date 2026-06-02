# ADR 0001: Anyplan Framework Adoption

## Status

Accepted

## Context

LC_01 SimWorld has strong technical documentation (`README.md`, `doc/Architecture.md`, `doc/DynamicAgents.md`, module READMEs) but no standardized **AI zero-context onboarding** or machine-readable collaboration contract.

The team adopted the [Anyplan](https://github.com/fangzhouRWTH/LC_PROTO) guidance framework (sibling project under Anygine) to:

- Give new AI sessions a single entry (`docs/AI-Entry.md`)
- Separate authority (`guidance.json`) from retrieval depth (`GuidanceManifest.md`)
- Track phase progress (`dashboard.json`)
- Support future extraction of SimWorld patterns back to Anyplan if they generalize

## Decision

1. **Project id:** `lc01-simworld` under `instances/lc01-simworld/`.
2. **Dual documentation roots (temporary):**
   - `docs/` — Anyplan collaboration artifacts (AI-Entry, ProjectState, adr, refactoring plans)
   - `doc/` — existing architecture prose (unchanged paths for now)
3. **Central contract:** `instances/lc01-simworld/guidance.json` outranks descriptive docs for AI collaboration rules.
4. **No Isaac-specific rules in Anyplan framework repo** — all SimWorld rules stay in this repository.
5. **Validation without Isaac:** `PYTHONPATH=src/simworld python3 -m unittest discover -s tests` is the default AI verification command for engine changes.
6. **Phased refactors** documented in `docs/refactoring/PHASED-REFACTORING.md`; not executed in the adoption commit.

## Consequences

Benefits:

- Owners can invoke AI with “Follow docs/AI-Entry.md”.
- Document index can be generated for the visual engine.
- Clear path to CI (Phase A) without blocking sim feature work.

Costs:

- `doc/` vs `docs/` until Phase B optional unify.
- Anyplan framework repo is external; validation scripts run from that path until vendored or scripted in LC_01.
- Maintainers must update dashboard + ProjectState when phase changes.

## Follow-up

- Phase A: CI for unit tests
- Phase B: `docs/architecture/` migration
- Consider submodule or `scripts/anyplan-validate.sh` wrapper in LC_01
