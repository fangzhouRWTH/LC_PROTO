"""Apply simworld.placement_output.v1 plans to a USD stage (Dummy or referenced assets)."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from ..isaac_adaptor import isaac_context as iscctx

PLACEMENT_OUTPUT_SCHEMA = "simworld.placement_output.v1"
DEFAULT_PUBLIC_SPACE_ASSET_ROOT = "/World/GeneratedAssets/PublicSpace"


@dataclass
class PublicSpacePlacementApplyResult:
    prim_paths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def load_placement_output_json(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    version = data.get("schema_version")
    if version != PLACEMENT_OUTPUT_SCHEMA:
        raise ValueError(
            f"Unsupported placement output schema: {version} "
            f"(expected {PLACEMENT_OUTPUT_SCHEMA})"
        )
    if "placements" not in data:
        raise ValueError("placement output missing 'placements'")
    return data


def _yaw_degrees_from_orientation(orientation: Sequence[float]) -> float:
    if len(orientation) < 2:
        return 0.0
    x = float(orientation[0])
    y = float(orientation[1])
    if abs(x) < 1e-9 and abs(y) < 1e-9:
        return 0.0
    return math.degrees(math.atan2(y, x))


class PublicSpacePlacementExecutor:
    def __init__(
        self,
        stage=None,
        root_prim: str = DEFAULT_PUBLIC_SPACE_ASSET_ROOT,
        *,
        use_dummy_assets: bool = True,
        dummy_size_m: float = 0.5,
        asset_name_map: dict[str, str] | None = None,
        apply_collision: bool = False,
    ):
        self.context = iscctx.get_isaac_context()
        self.stage = stage or self.context.omni_usd.get_context().get_stage()
        if self.stage is None:
            raise RuntimeError(
                "Cannot apply public-space placements without an open USD stage."
            )

        self.root_prim = root_prim.rstrip("/") or "/"
        self.use_dummy_assets = use_dummy_assets
        self.dummy_size_m = float(dummy_size_m)
        self.asset_name_map = dict(asset_name_map or {})
        self.apply_collision = apply_collision

    def apply_plan(
        self,
        plan: dict[str, Any],
        *,
        replace_existing: bool = True,
    ) -> PublicSpacePlacementApplyResult:
        placements = plan.get("placements") or []
        result = PublicSpacePlacementApplyResult()

        if not placements:
            print("[INFO] Public-space placement plan is empty.")
            return result

        self._ensure_xform_chain(self.root_prim)

        for item in placements:
            if not isinstance(item, dict):
                continue
            prim_path = self._apply_one(item, replace_existing=replace_existing)
            if prim_path:
                result.prim_paths.append(prim_path)
            else:
                name = item.get("asset_name", "?")
                result.warnings.append(f"Skipped placement for asset_name={name}")

        print(
            f"[OK] Applied {len(result.prim_paths)} public-space placement(s) "
            f"under {self.root_prim}."
        )
        return result

    def apply_plan_file(
        self,
        path: str | Path,
        *,
        replace_existing: bool = True,
    ) -> PublicSpacePlacementApplyResult:
        return self.apply_plan(
            load_placement_output_json(path),
            replace_existing=replace_existing,
        )

    def _apply_one(self, item: dict[str, Any], *, replace_existing: bool) -> str | None:
        asset_name = str(item.get("asset_name") or "unknown").strip()
        placement_id = str(item.get("placement_id") or asset_name).strip()
        safe_name = "".join(
            ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in placement_id
        )
        prim_path = f"{self.root_prim}/{safe_name}"

        position = item.get("position") or [0.0, 0.0, 0.0]
        if len(position) < 3:
            return None

        yaw_deg = _yaw_degrees_from_orientation(item.get("orientation") or [])

        usd_path = self.asset_name_map.get(asset_name)
        if usd_path and not self.use_dummy_assets:
            return self._place_reference(
                prim_path,
                Path(usd_path),
                position,
                yaw_deg,
                replace_existing=replace_existing,
            )

        return self._place_dummy(
            prim_path,
            position,
            yaw_deg,
            replace_existing=replace_existing,
        )

    def _place_dummy(
        self,
        prim_path: str,
        position: Sequence[float],
        yaw_deg: float,
        *,
        replace_existing: bool,
    ) -> str:
        UsdGeom = self.context.pxr_usd_geom
        Gf = self.context.pxr_gf

        self._ensure_xform_chain(prim_path)
        wrapper = self.stage.GetPrimAtPath(prim_path)
        if replace_existing:
            for child in list(wrapper.GetChildren()):
                self.stage.RemovePrim(child.GetPath())

        cube_path = f"{prim_path}/DummyGeom"
        cube = UsdGeom.Cube.Define(self.stage, cube_path)
        size = self.dummy_size_m
        cube.CreateSizeAttr(size)

        xform = UsdGeom.Xformable(wrapper)
        xform.ClearXformOpOrder()
        xform.AddTranslateOp().Set(
            Gf.Vec3d(float(position[0]), float(position[1]), float(position[2]))
        )
        xform.AddRotateZOp().Set(float(yaw_deg))

        return prim_path

    def _place_reference(
        self,
        prim_path: str,
        asset_path: Path,
        position: Sequence[float],
        yaw_deg: float,
        *,
        replace_existing: bool,
    ) -> str | None:
        if not asset_path.is_file():
            print(f"[WARN] Asset USD not found for reference: {asset_path}")
            return self._place_dummy(
                prim_path,
                position,
                yaw_deg,
                replace_existing=replace_existing,
            )

        UsdGeom = self.context.pxr_usd_geom
        Gf = self.context.pxr_gf

        self._ensure_xform_chain(prim_path)
        wrapper = self.stage.GetPrimAtPath(prim_path)
        if replace_existing:
            wrapper.GetReferences().ClearReferences()

        ref_path = f"{prim_path}/Asset"
        ref_prim = self._ensure_xform_chain(ref_path)
        ref_prim.GetReferences().AddReference(str(asset_path.resolve()))

        xform = UsdGeom.Xformable(wrapper)
        xform.ClearXformOpOrder()
        xform.AddTranslateOp().Set(
            Gf.Vec3d(float(position[0]), float(position[1]), float(position[2]))
        )
        xform.AddRotateZOp().Set(float(yaw_deg))
        return prim_path

    def _ensure_xform_chain(self, prim_path: str):
        parts = prim_path.strip("/").split("/")
        UsdGeom = self.context.pxr_usd_geom
        current = ""
        last_prim = None
        for part in parts:
            current = f"{current}/{part}"
            prim = self.stage.GetPrimAtPath(current)
            if not prim.IsValid():
                last_prim = UsdGeom.Xform.Define(self.stage, current).GetPrim()
            else:
                prim.SetActive(True)
                last_prim = prim
        return last_prim
