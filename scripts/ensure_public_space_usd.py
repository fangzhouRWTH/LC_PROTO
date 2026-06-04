#!/usr/bin/env python3
"""Complete public-space USD placeholders from compact region names + quad meshes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "simworld"))


def _bootstrap_openusd_via_isaac() -> None:
    from isaacsim import SimulationApp

    SimulationApp(
        {
            "headless": True,
            "width": 128,
            "height": 128,
            "hide_ui": True,
            "fast_shutdown": True,
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Ensure public-space USD regions have simworld attrs and four "
            "placeholder_segment_edge_* children synthesized from quad geometry. "
            "Region names: placeholder_area_publicspace_<index>_<typecompact> "
            "[_<boundarycompact>]. Requires pxr (use .sh wrapper on Isaac python)."
        )
    )
    parser.add_argument(
        "--usd",
        required=True,
        type=Path,
        help="Scene USD to patch in place",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without writing USD",
    )
    parser.add_argument(
        "--overwrite-segments",
        action="store_true",
        help="Replace existing segment child prims",
    )
    parser.add_argument(
        "--bootstrap-isaac",
        action="store_true",
        help="Start headless Isaac SimulationApp so pxr is available",
    )
    args = parser.parse_args(argv)

    if args.bootstrap_isaac:
        _bootstrap_openusd_via_isaac()

    from pxr import Usd

    from engine.usd_public_space_ensure import ensure_public_space_usd
    from engine.usd_scene_audit import (
        _find_first_mesh_prim,
        _transform_point,
        _world_transform,
    )

    usd_path = args.usd.expanduser().resolve()
    stage = Usd.Stage.Open(str(usd_path))
    if stage is None:
        print(f"[ERROR] cannot open {usd_path}", file=sys.stderr)
        return 1

    logs = ensure_public_space_usd(
        stage,
        mesh_helpers=(_find_first_mesh_prim, _world_transform, _transform_point),
        dry_run=args.dry_run,
        overwrite_existing_segments=args.overwrite_segments,
    )
    for line in logs:
        print(line)

    if not args.dry_run:
        stage.GetRootLayer().Save()
        print(f"[OK] saved {usd_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
