from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

from engine import placement
from ..isaac_adaptor import isaac_context as iscctx

DEFAULT_GENERATED_ASSET_ROOT = "/World/GeneratedAssets"


@dataclass
class AssetAllocationResult:
    prim_paths: list[str] = field(default_factory=list)


class SceneAssetAllocator:
    def __init__(
        self,
        stage=None,
        root_prim: str = DEFAULT_GENERATED_ASSET_ROOT,
        apply_collision: bool = True,
        reference_child_name: str = "Asset",
    ):
        self.context = iscctx.get_isaac_context()
        self.stage = stage or self.context.omni_usd.get_context().get_stage()
        if self.stage is None:
            raise RuntimeError(
                "Cannot allocate scene assets without an open USD stage."
            )

        self.root_prim = self._normalize_absolute_prim_path(root_prim)
        self.apply_collision = apply_collision
        self.reference_child_name = reference_child_name

    def import_plans(
        self,
        plans: Sequence[placement.AssetImportPlan],
        replace_existing: bool = True,
    ) -> AssetAllocationResult:
        if not plans:
            print("[INFO] No generated asset plans to import.")
            return AssetAllocationResult()

        self._ensure_xform_prim(self.root_prim)

        result = AssetAllocationResult()
        for plan in plans:
            prim = self.import_plan(plan, replace_existing=replace_existing)
            result.prim_paths.append(str(prim.GetPath()))

        print(
            f"[OK] Imported {len(result.prim_paths)} generated asset(s) "
            f"under {self.root_prim}."
        )
        return result

    def import_plan(
        self,
        plan: placement.AssetImportPlan,
        replace_existing: bool = True,
    ):
        prim_path = self._normalize_absolute_prim_path(plan.prim_path)
        asset_path = self._resolve_asset_path(plan.asset.usd_path)

        self._ensure_parent_xforms(prim_path)
        wrapper_prim = self._ensure_xform_prim(prim_path)
        if replace_existing:
            wrapper_prim.GetReferences().ClearReferences()

        self._define_reference_prim(
            prim_path=f"{prim_path}/{self.reference_child_name}",
            asset_path=asset_path,
            replace_existing=replace_existing,
        )
        self._apply_plan_transform(wrapper_prim, plan)

        if self.apply_collision:
            self._apply_static_collision_recursive(wrapper_prim)

        return wrapper_prim

    def _resolve_asset_path(self, asset_path: Path | str) -> Path:
        path = Path(asset_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Asset USD not found: {path}")
        if path.suffix.lower() not in {".usd", ".usda", ".usdc"}:
            raise ValueError(f"Asset path is not a USD file: {path}")
        return path

    def _normalize_absolute_prim_path(self, prim_path: str) -> str:
        if not prim_path:
            raise ValueError("Prim path cannot be empty.")

        normalized = prim_path.rstrip("/") or "/"
        if not normalized.startswith("/"):
            raise ValueError(f"Prim path must be absolute: {prim_path}")

        Sdf = self.context.pxr_Sdf
        sdf_path = Sdf.Path(normalized)
        if sdf_path.isEmpty or not sdf_path.IsAbsolutePath():
            raise ValueError(f"Invalid USD prim path: {prim_path}")

        return normalized

    def _ensure_parent_xforms(self, prim_path: str) -> None:
        parts = prim_path.strip("/").split("/")[:-1]
        current_path = ""

        for part in parts:
            current_path = f"{current_path}/{part}"
            self._ensure_xform_prim(current_path)

    def _ensure_xform_prim(self, prim_path: str):
        prim = self.stage.GetPrimAtPath(prim_path)
        if prim.IsValid():
            prim.SetActive(True)
            return prim

        UsdGeom = self.context.pxr_usd_geom
        return UsdGeom.Xform.Define(self.stage, prim_path).GetPrim()

    def _define_reference_prim(
        self,
        prim_path: str,
        asset_path: Path,
        replace_existing: bool,
    ):
        prim = self._ensure_xform_prim(prim_path)

        references = prim.GetReferences()
        if replace_existing:
            references.ClearReferences()
        references.AddReference(str(asset_path))

        return prim

    def _apply_plan_transform(self, prim, plan: placement.AssetImportPlan) -> None:
        UsdGeom = self.context.pxr_usd_geom

        xformable = UsdGeom.Xformable(prim)
        xformable.ClearXformOpOrder()
        xformable.AddTransformOp(precision=UsdGeom.XformOp.PrecisionDouble).Set(
            self._build_transform_matrix(plan)
        )

    def _build_transform_matrix(self, plan: placement.AssetImportPlan):
        Gf = self.context.pxr_gf

        sx, sy, sz = plan.scale_xyz

        x_axis = self._as_vec3(plan.tangent_x) * float(sx)
        y_axis = self._as_vec3(plan.tangent_y) * float(sy)
        z_axis = self._as_vec3(plan.normal) * float(sz)
        center = self._as_vec3(plan.center)

        return Gf.Matrix4d(
            float(x_axis[0]),
            float(x_axis[1]),
            float(x_axis[2]),
            0.0,
            float(y_axis[0]),
            float(y_axis[1]),
            float(y_axis[2]),
            0.0,
            float(z_axis[0]),
            float(z_axis[1]),
            float(z_axis[2]),
            0.0,
            float(center[0]),
            float(center[1]),
            float(center[2]),
            1.0,
        )

    def _as_vec3(self, value) -> np.ndarray:
        vec = np.asarray(value, dtype=np.float64)
        if vec.shape != (3,):
            raise ValueError(f"Expected 3D vector, got shape {vec.shape}.")
        return vec

    def _apply_static_collision_recursive(self, root_prim) -> None:
        UsdGeom = self.context.pxr_usd_geom
        UsdPhysics = self.context.pxr_usd_physics

        for prim in self._iter_prim_subtree(root_prim):
            if not prim.IsA(UsdGeom.Xformable):
                continue

            if not prim.HasAPI(UsdPhysics.CollisionAPI):
                UsdPhysics.CollisionAPI.Apply(prim)

            if prim.IsA(UsdGeom.Mesh):
                if prim.HasAPI(UsdPhysics.MeshCollisionAPI):
                    mesh_collision = UsdPhysics.MeshCollisionAPI(prim)
                else:
                    mesh_collision = UsdPhysics.MeshCollisionAPI.Apply(prim)
                mesh_collision.CreateApproximationAttr().Set("meshSimplification")

    def _iter_prim_subtree(self, prim):
        yield prim

        for child in prim.GetChildren():
            yield from self._iter_prim_subtree(child)
