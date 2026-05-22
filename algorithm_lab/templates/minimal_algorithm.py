from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


def _centroid(vertices: list[list[float]]) -> list[float]:
    if not vertices:
        return [0.0, 0.0, 0.0]

    dims = len(vertices[0])
    return [
        sum(float(vertex[i]) for vertex in vertices) / len(vertices)
        for i in range(dims)
    ]


def build_plan(payload: dict[str, Any], seed: int) -> dict[str, Any]:
    """Build a tiny deterministic plan without importing Isaac Sim."""
    rng = random.Random(seed)
    region = payload.get("region", {})
    vertices = region.get("vertices", [])

    center = _centroid(vertices)
    if len(center) == 2:
        center.append(0.0)

    return {
        "schema_version": "algorithm_lab.static_asset_plan.v1",
        "algorithm": "minimal_algorithm",
        "seed": seed,
        "asset_import_plans": [
            {
                "id": "example_0001",
                "category": "placeholder",
                "center": center[:3],
                "size_xy": [1.0, 1.0],
                "yaw": round(rng.uniform(-0.1, 0.1), 6),
                "metadata": {
                    "note": "Replace this placeholder with real algorithm output."
                },
            }
        ],
        "warnings": [],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Minimal standalone algorithm template."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    with args.input.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    plan = build_plan(payload, seed=args.seed)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)
        f.write("\n")

    print(
        f"Wrote {len(plan['asset_import_plans'])} plan item(s) "
        f"to {args.output}"
    )


if __name__ == "__main__":
    main()
