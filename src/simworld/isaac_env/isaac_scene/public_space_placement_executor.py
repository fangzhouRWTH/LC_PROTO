"""Apply simworld.placement_output.v1 plans to a USD stage (Dummy or referenced assets)."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from engine.public_space_dummy_visual import dummy_visual_spec

from ..isaac_adaptor import isaac_context as iscctx

PLACEMENT_OUTPUT_SCHEMA = "simworld.placement_output.v1"
DEFAULT_PUBLIC_SPACE_ASSET_ROOT = "/World/GeneratedAssets/PublicSpace"
_DEBUG_GEOM_CHILD = "DebugGeom"
_REFERENCE_CHILD = "Asset"


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

        self.root_prim = self._resolve_root_prim(root_prim)
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

        self._ensure_xform_prim(self.root_prim)

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
        safe_name = self._usd_safe_prim_name(placement_id)
        prim_path = f"{self.root_prim}/{safe_name}"

        position = item.get("position") or [0.0, 0.0, 0.0]
        if len(position) < 3:
            return None

        yaw_deg = _yaw_degrees_from_orientation(item.get("orientation") or [])

        usd_path = self.asset_name_map.get(asset_name)
        use_reference = bool(usd_path) and not self.use_dummy_assets
        if use_reference:
            placed = self._place_reference(
                prim_path,
                Path(usd_path),
                position,
                yaw_deg,
                replace_existing=replace_existing,
                asset_name=asset_name,
                placement_id=placement_id,
            )
            if placed:
                return placed

        return self._place_dummy(
            prim_path,
            position,
            yaw_deg,
            replace_existing=replace_existing,
            asset_name=asset_name,
            placement_id=placement_id,
            missing_asset=not usd_path,
        )

    def _place_dummy(
        self,
        prim_path: str,
        position: Sequence[float],
        yaw_deg: float,
        *,
        replace_existing: bool,
        asset_name: str = "",
        placement_id: str = "",
        missing_asset: bool = False,
    ) -> str:
        UsdGeom = self.context.pxr_usd_geom
        Gf = self.context.pxr_gf

        spec = dummy_visual_spec(placement_id or prim_path, asset_name)
        size = float(spec.get("size") or self.dummy_size_m)

        wrapper = self._ensure_xform_prim(prim_path)
        if replace_existing:
            for child in list(wrapper.GetChildren()):
                self.stage.RemovePrim(child.GetPath())

        geom_path = f"{prim_path}/{_DEBUG_GEOM_CHILD}"
        self._define_debug_cube(UsdGeom, geom_path, size)

        self._set_world_pose(
            UsdGeom,
            Gf,
            wrapper,
            position,
            yaw_deg,
        )

        return prim_path

    def _define_debug_cube(self, UsdGeom, geom_path: str, size: float) -> None:
        """UsdGeom.Cube only — mixed Cone/Cylinder + displayColor can crash Kit."""
        parent_path = geom_path.rsplit("/", 1)[0]
        if parent_path:
            self._ensure_xform_prim(parent_path)
        existing = self.stage.GetPrimAtPath(geom_path)
        if existing.IsValid() and not existing.IsA(UsdGeom.Cube):
            self.stage.RemovePrim(existing.GetPath())
        cube = UsdGeom.Cube.Define(self.stage, geom_path)
        cube.CreateSizeAttr(max(0.2, min(float(size), 1.2)))

    def _set_world_pose(
        self,
        UsdGeom,
        Gf,
        prim,
        position: Sequence[float],
        yaw_deg: float,
    ) -> None:
        if not prim or not prim.IsValid() or not prim.IsA(UsdGeom.Xform):
            path = str(prim.GetPath()) if prim and prim.IsValid() else "<invalid>"
            raise RuntimeError(f"Cannot set world pose on non-Xform prim: {path}")
        xform = UsdGeom.Xformable(prim)
        xform.ClearXformOpOrder()
        xform.AddTranslateOp().Set(
            Gf.Vec3d(float(position[0]), float(position[1]), float(position[2]))
        )
        xform.AddRotateZOp().Set(float(yaw_deg))

    def _place_reference(
        self,
        prim_path: str,
        asset_path: Path,
        position: Sequence[float],
        yaw_deg: float,
        *,
        replace_existing: bool,
        asset_name: str = "",
        placement_id: str = "",
    ) -> str | None:
        if not asset_path.is_file():
            print(f"[WARN] Asset USD not found for reference: {asset_path}")
            return self._place_dummy(
                prim_path,
                position,
                yaw_deg,
                replace_existing=replace_existing,
                asset_name=asset_name,
                placement_id=placement_id,
                missing_asset=True,
            )

        UsdGeom = self.context.pxr_usd_geom
        Gf = self.context.pxr_gf

        wrapper = self._ensure_xform_prim(prim_path)
        if replace_existing:
            wrapper.GetReferences().ClearReferences()

        ref_path = f"{prim_path}/{_REFERENCE_CHILD}"
        ref_prim = self._ensure_xform_prim(ref_path)
        ref_prim.GetReferences().AddReference(str(asset_path.resolve()))

        self._set_world_pose(
            UsdGeom,
            Gf,
            wrapper,
            position,
            yaw_deg,
        )
        return prim_path


    @staticmethod
    def _usd_safe_prim_name(name: str) -> str:
        """Sanitize a single USD prim path element (no leading digit)."""
        safe = "".join(
            ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in (name or "")
        ).strip("_")
        if not safe:
            safe = "placement_unknown"
        if safe[0].isdigit():
            safe = f"ps_{safe}"
        return safe

    def _resolve_root_prim(self, root_prim: str) -> str:
        """Use /root/... when the opened stage has no /World (e.g. demo_tencent_test.usd)."""
        normalized = (root_prim or DEFAULT_PUBLIC_SPACE_ASSET_ROOT).rstrip("/") or "/"
        if normalized != DEFAULT_PUBLIC_SPACE_ASSET_ROOT:
            return normalized

        stage_root = self.stage.GetPrimAtPath("/root")
        world = self.stage.GetPrimAtPath("/World")
        if stage_root.IsValid() and not world.IsValid():
            return "/root/GeneratedAssets/PublicSpace"
        return DEFAULT_PUBLIC_SPACE_ASSET_ROOT

    def _normalize_prim_path(self, prim_path: str) -> str:
        normalized = prim_path.rstrip("/") or "/"
        if not normalized.startswith("/"):
            raise ValueError(f"Prim path must be absolute: {prim_path}")
        Sdf = self.context.pxr_Sdf
        sdf_path = Sdf.Path(normalized)
        if sdf_path.isEmpty or not sdf_path.IsAbsolutePath():
            raise ValueError(f"Invalid USD prim path: {prim_path}")
        return normalized

    def _ensure_parent_xforms(self, prim_path: str) -> None:
        parts = self._normalize_prim_path(prim_path).strip("/").split("/")[:-1]
        current = ""
        for part in parts:
            current = f"{current}/{part}"
            self._ensure_xform_prim(current)

    def _ensure_xform_prim(self, prim_path: str):
        """
        Ensure an Xform exists at ``prim_path``.

        Unlike the old ``_ensure_xform_chain``, parents are created first (Kit-safe),
        existing non-Xform prims are not passed to Xformable ops, and SetActive is
        not forced on arbitrary stage prims (avoids pick/viewport crashes).
        """
        prim_path = self._normalize_prim_path(prim_path)
        UsdGeom = self.context.pxr_usd_geom
        prim = self.stage.GetPrimAtPath(prim_path)
        if prim.IsValid():
            if prim.IsA(UsdGeom.Xform):
                return prim
            raise RuntimeError(
                f"Cannot place public-space asset at {prim_path}: "
                f"existing prim type is {prim.GetTypeName()} (expected Xform)"
            )

        parent_path = prim_path.rsplit("/", 1)[0] if prim_path.count("/") > 1 else ""
        if parent_path and parent_path != prim_path:
            self._ensure_xform_prim(parent_path)
        return UsdGeom.Xform.Define(self.stage, prim_path).GetPrim()