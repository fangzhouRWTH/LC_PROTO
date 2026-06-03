# Agent / workspace handoff (2026-05-30)

Moved primary Cursor development from **UrbanSim** workspace to **LC_PROTO**.

## Open this project

- **Recommended**: `LC_PROTO-dev.code-workspace` (LC_PROTO + `prototypes/Development`)
- **Minimal**: open folder `/home/sstormw/LeapsCora/LC_PROTO`

## Keep the same Agent chat

In the **UrbanSim** window where the long dynamic-agents chat lives:

1. `Ctrl+Shift+P` → search **Move Agent** / **move agent to root**
2. Choose **multi-root** if offered, paths:
   - `/home/sstormw/LeapsCora/LC_PROTO`
   - `/home/sstormw/LeapsCora/prototypes/Development`
3. Or single root: `/home/sstormw/LeapsCora/LC_PROTO`

Alternatively open `LC_PROTO-dev.code-workspace` in a **new** window and paste a short summary; rules in `.cursor/rules/lc-proto-agent-handoff.mdc` carry most context.

## Branch state

- Current working branch: `dynamic-agents`
- `origin/dev-SSTORM` was removed after the dynamic agent PR was merged to `master`
- Local helper files currently remain untracked: `.cursor/`, `LC_PROTO-dev.code-workspace`, and `doc/AGENT_HANDOFF.md`
- Push/PR policy for `dynamic-agents`: decide before publishing the next round

## UrbanSim

Keep a separate Cursor window for UrbanSim-only work (`/home/sstormw/LeapsCora/UrbanSim`).
