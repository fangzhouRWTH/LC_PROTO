# Phased Refactoring Plan

This plan covers **optional** engineering and documentation improvements for LC_01 SimWorld. **Do not execute all phases in one task.** Schedule phases explicitly in `dashboard.json` and `ProjectState.md`.

Anyplan bootstrap (Phase 0) is complete enough for daily AI-assisted work without Phase A–C.

## Phase 0 — Anyplan instantiation (done / in progress)

**Goal:** AI can join with zero context via `docs/AI-Entry.md`.

**Deliverables:**

- [x] `instances/lc01-simworld/guidance.json`
- [x] `instances/lc01-simworld/dashboard.json`
- [x] `docs/AI-Entry.md`, `docs/ProjectState.md`, `docs/GuidanceManifest.md`
- [ ] `instances/lc01-simworld/doc-index.json` (build via Anyplan script)
- [ ] `docs/adr/0001-anyplan-adoption.md`
- [ ] README § AI collaboration

**Validation:**

```bash
PYTHONPATH=src/simworld python3 -m unittest discover -s tests -v
```

**No code moves required.**

---

## Phase A — CI and test gate (low complexity, high value)

**Goal:** Every PR runs engine unit tests without Isaac Sim.

**Tasks:**

1. Add `.github/workflows/tests.yml` (or GitLab equivalent) running:
   ```bash
   PYTHONPATH=src/simworld python3 -m unittest discover -s tests -v
   ```
2. Document command in `guidance.json` constraints and README.
3. Optional: `scripts/run_tests.sh` wrapper for local parity.

**Acceptance:** CI green on default branch; guidance references CI command.

**Estimated effort:** Small (1 session).

---

## Phase B — Documentation layout unify (medium complexity)

**Goal:** Single logical `docs/` root without breaking external links immediately.

**Problem:** Legacy `doc/` (Architecture, DynamicAgents) vs new `docs/` (Anyplan). Dual roots confuse AI and humans.

**Recommended approach (incremental):**

1. Create `docs/architecture/` and **copy or move**:
   - `doc/Architecture.md` → `docs/architecture/Architecture.md`
   - `doc/DynamicAgents.md` → `docs/architecture/DynamicAgents.md`
2. Leave **stub files** in `doc/` that only contain:
   ```markdown
   # Moved
   See [Architecture](../docs/architecture/Architecture.md).
   ```
3. Update README links to `docs/architecture/`.
4. Update `guidance.json` document paths and rebuild `doc-index.json`.
5. After one release cycle, remove `doc/` stubs if desired.

**Do not move** `doc/weekly_reports/` (gitignored internal).

**Acceptance:** AI-Entry and manifest point to canonical paths; README links work.

**Estimated effort:** Medium (1–2 sessions). **Defer** if no doc churn scheduled.

---

## Phase C — ScenePipelineConfig and contracts (higher complexity)

**Goal:** Implement Architecture §3.1 recommendation: serializable scene pipeline config.

**Tasks:**

1. Design `ScenePipelineConfig` (YAML or JSON) covering scene USD, assets, layout, dynamic agents, weather, sensors.
2. Wire `main.py` / `SimulationConfig` to load config file with CLI overrides.
3. Add contract tests for config round-trip and plan export.
4. Update README and Architecture with config examples.

**Acceptance:** `scripts/run_sim.sh --config path.yaml` (or equivalent) runs; tests cover config parsing.

**Estimated effort:** Large (multiple sessions). **Track as feature work**, not doc-only refactor.

---

## Phase D — Active bug reports (optional, low urgency)

**Goal:** Isaac debugging handoff per Anyplan [active-bug-reports spec](https://github.com/fangzhouRWTH/LC_PROTO) (see Anyplan `framework/spec/active-bug-reports.md` in framework repo).

**Tasks:**

1. Add `docs/active-bug-reports/README.md` + `_Template.md`.
2. Enable pack in `AI-Entry.md`.
3. Register in `guidance.json` documents.

**Acceptance:** Policy documented; directory empty unless threshold met.

**Estimated effort:** Small.

---

## Phase E — Algorithm lab promotion (as needed)

**Goal:** Promote stable `algorithm_lab` experiments into `engine/` with tests.

**Per-experiment** — not a single refactor. Use `algorithm_lab/guideline.md` for each promotion.

---

## Execution Rules for AI

1. Confirm which phase the owner requested in the **TaskBrief**.
2. Do not start Phase B or C while completing unrelated feature work unless explicitly combined.
3. Update `dashboard.json` phase status when a phase starts or completes.
4. Add ADR for Phase B or C when binding structure changes.

## Related

- [docs/adr/0001-anyplan-adoption.md](../adr/0001-anyplan-adoption.md)
- [doc/Architecture.md](../../doc/Architecture.md) §3.1 ScenePipelineConfig
