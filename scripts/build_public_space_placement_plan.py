#!/usr/bin/env python3
"""Build simworld.placement_output.v1 from region inputs (stdin JSON, stdout JSON).

Runs outside Isaac Sim so layout (algorithm_lab proto) does not share the Kit process.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "simworld"))

from engine import area_placement_bridge  # noqa: E402


def main() -> int:
    payload = json.load(sys.stdin)
    region_inputs = payload.get("region_inputs")
    if not isinstance(region_inputs, list) or not region_inputs:
        print(
            '{"error": "region_inputs must be a non-empty list"}',
            file=sys.stderr,
        )
        return 2
    steps = payload.get("steps")
    if steps is not None:
        steps = [int(value) for value in steps]
    plan = area_placement_bridge.build_combined_placement_plan_from_region_inputs(
        region_inputs,
        steps=steps,
        force_in_process=True,
    )
    json.dump(plan, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
