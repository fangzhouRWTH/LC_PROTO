#!/usr/bin/env python3
"""Add simworld segment attrs to demo_tencent_test.usd (requires pxr / Isaac bootstrap)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_USD = REPO_ROOT / "assets/blocks/demo/demo_tencent_test.usd"
LOG_PATH = REPO_ROOT / "assets/blocks/demo/demo_tencent_patch.log"


def _log(msg: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(msg + "\n")
    print(msg, flush=True)


def main() -> int:
    LOG_PATH.write_text("", encoding="utf-8")
    _log("patch_demo_tencent_usd_segments: start")

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

    from pxr import Sdf, Usd

    usd_path = DEFAULT_USD.resolve()
    stage = Usd.Stage.Open(str(usd_path))
    if stage is None:
        _log(f"[ERROR] cannot open {usd_path}")
        return 1

    fixes = {
        "placeholder_segment_edge_01": (1, "street_boundary_primary"),
        "placeholder_segment_edge_02": (2, "block_boundary_other"),
        "placeholder_segment_edge_03": (3, "block_boundary_primary"),
        "placeholder_segment_edge_04": (4, "street_boundary_primary"),
    }

    fixed = 0
    for prim in stage.Traverse():
        if prim.GetName() not in fixes:
            continue
        seg_id, boundary = fixes[prim.GetName()]
        for key, value, typ in (
            ("simworld:segment_id", seg_id, Sdf.ValueTypeNames.Int),
            ("simworld:boundary_type", boundary, Sdf.ValueTypeNames.Token),
        ):
            attr = prim.GetAttribute(key)
            if not attr or not attr.IsValid():
                attr = prim.CreateAttribute(key, typ)
            attr.Set(value)
        for extra in ("simworld:public_space_type", "simworld:ratio_dynamic_static"):
            attr = prim.GetAttribute(extra)
            if attr and attr.IsValid():
                prim.RemoveProperty(extra)
        fixed += 1
        _log(f"[OK] {prim.GetPath()} id={seg_id} boundary_type={boundary}")

    if fixed != 4:
        _log(f"[WARN] fixed {fixed}/4 segment prims")
        return 2

    stage.GetRootLayer().Save()
    _log(f"[OK] saved {usd_path}")

    stage2 = Usd.Stage.Open(str(usd_path))
    verify = stage2.GetPrimAtPath(
        "/root/placeholder_area_publicspace_001/placeholder_segment_edge_01"
    )
    _log(
        f"[VERIFY] boundary_type={verify.GetAttribute('simworld:boundary_type').Get()} "
        f"segment_id={verify.GetAttribute('simworld:segment_id').Get()}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        _log(f"[ERROR] {exc}")
        raise
