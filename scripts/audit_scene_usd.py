#!/usr/bin/env python3
"""Audit a scene USD for SimWorld parser / area-placement structure; write Markdown."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "simworld"))

def _bootstrap_openusd_via_isaac() -> None:
    """Load ``pxr`` the same way ``run_sim`` does (headless Kit)."""
    try:
        from isaacsim import SimulationApp  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "Cannot import isaacsim for USD bootstrap. Run from Isaac Sim "
            "python.sh or install OpenUSD bindings."
        ) from exc

    SimulationApp(
        {
            "headless": True,
            "width": 128,
            "height": 128,
            "hide_ui": True,
            "fast_shutdown": True,
        }
    )


def _default_output_path(usd_path: Path) -> Path:
    return usd_path.with_name(f"{usd_path.stem}_audit.md")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Traverse a USD stage and emit a Markdown report: scene tree, "
            "which prims feed area_placement_methods vs unrelated data, and "
            "validation issues. Requires pxr (use scripts/audit_scene_usd.sh on Isaac)."
        )
    )
    parser.add_argument(
        "--usd",
        required=True,
        type=Path,
        help="Path to scene .usd / .usda / .usdc",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Markdown output path (default: <usd_stem>_audit.md beside the file)",
    )
    parser.add_argument(
        "--no-region-preview",
        action="store_true",
        help="Skip dry-run public_space_region_to_region_input conversion",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Also print the report to stdout",
    )
    parser.add_argument(
        "--bootstrap-isaac",
        action="store_true",
        help="Start headless Isaac SimulationApp so pxr is available (default via .sh)",
    )
    args = parser.parse_args(argv)

    if args.bootstrap_isaac:
        _bootstrap_openusd_via_isaac()

    from engine.usd_scene_audit import (  # noqa: E402
        render_audit_markdown,
        write_audit_markdown,
    )

    usd_path = args.usd.expanduser().resolve()
    output_path = args.output.expanduser().resolve() if args.output else _default_output_path(usd_path)

    try:
        report = write_audit_markdown(
            usd_path,
            output_path,
            include_region_input_preview=not args.no_region_preview,
        )
    except ImportError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    except (FileNotFoundError, RuntimeError, OSError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    summary = report.summary
    print(f"[OK] Wrote audit report: {output_path}")
    print(
        f"     regions={summary.get('public_space_regions', 0)} "
        f"layout-ready={summary.get('layout_ready_regions', 0)} "
        f"issues={summary.get('total_issues', 0)}"
    )
    if report.global_issues:
        for issue in report.global_issues:
            print(f"[WARN] {issue}")

    if args.stdout:
        print()
        print(render_audit_markdown(report))

    return 0 if summary.get("total_issues", 0) == 0 and not report.global_issues else 3


if __name__ == "__main__":
    raise SystemExit(main())
