#!/usr/bin/env python3
"""CLI entry for area placement layout (no Isaac)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from generator import run_public_space_layout_from_file


def _parse_steps(raw: list[str] | None) -> list[int] | None:
    if not raw:
        return [1, 2, 3, 4, 5]
    return [int(value) for value in raw]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run public-space area placement (proto pipeline)."
    )
    parser.add_argument("input_json", type=Path, help="Region input JSON path")
    parser.add_argument(
        "--steps",
        nargs="+",
        default=None,
        help="Pipeline steps (default: 1 2 3 4 5)",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_json",
        type=Path,
        help="Write augmented layout JSON here",
    )
    parser.add_argument(
        "--flow-pattern",
        choices=["cross", "fishbone", "ring", "orthogonal"],
        help="Override step-3 flow pattern",
    )
    parser.add_argument(
        "--to-placement-output",
        type=Path,
        help="Also write simworld.placement_output.v1 JSON",
    )
    args = parser.parse_args(argv)

    if not args.input_json.is_file():
        print(f"Input not found: {args.input_json}", file=sys.stderr)
        return 1

    try:
        result = run_public_space_layout_from_file(
            args.input_json,
            steps=_parse_steps(args.steps),
            flow_pattern_override=args.flow_pattern,
            output_json_path=args.output_json,
        )
    except (ValueError, OSError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    summary = {
        "public_space_type": result.get("public_space_type"),
        "asset_count": len(result.get("asset_list") or []),
        "walking_line_count": len(result.get("walking_lines") or []),
        "dynamic_zone_count": len(result.get("dynamic_zones") or []),
        "static_zone_count": len(result.get("static_zones") or []),
    }
    print(json.dumps(summary, indent=2))

    if args.to_placement_output:
        from adapters.asset_list_to_plan import layout_result_to_placement_output

        region_id = args.input_json.stem
        placement = layout_result_to_placement_output(result, region_id=region_id)
        args.to_placement_output.parent.mkdir(parents=True, exist_ok=True)
        with args.to_placement_output.open("w", encoding="utf-8") as handle:
            json.dump(placement, handle, indent=2, ensure_ascii=False)
        print(f"Wrote placement output: {args.to_placement_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
