"""Plan / apply public-space USD completions (region attrs + segment prims)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.public_space_compact_naming import (
    PublicSpaceRegionNameInfo,
    parse_public_space_region_name,
)
from engine.public_space_geometry import build_inferred_boundary_segment_records
from engine.public_space_metadata import is_known_public_space_type
from engine.scene_naming import parse_prim_name

DEFAULT_RATIO_DYNAMIC_STATIC = 0.36


@dataclass
class SegmentCompletionPlan:
    prim_path: str
    raw_name: str
    segment_id: int
    boundary_type: str
    vertices: list[list[float]]


@dataclass
class RegionCompletionPlan:
    region_path: str
    region_name: str
    public_space_type: str
    boundary_type_hint: str
    ratio_dynamic_static: float
    set_public_space_type: bool = False
    set_ratio_dynamic_static: bool = False
    segments: list[SegmentCompletionPlan] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _read_attr(prim, name: str, default=None):
    for key in (f"simworld:{name}", f"custom:simworld:{name}"):
        attr = prim.GetAttribute(key)
        if attr and attr.IsValid():
            value = attr.Get()
            if value is not None:
                return value
    return default


def _mesh_world_vertices(prim, *, mesh_helpers) -> list[list[float]]:
    find_first_mesh, world_transform, transform_point = mesh_helpers
    mesh = find_first_mesh(prim)
    if mesh is None:
        return []
    from pxr import UsdGeom

    points = UsdGeom.Mesh(mesh).GetPointsAttr().Get() or []
    world_mat = world_transform(mesh)
    return [transform_point(world_mat, point) for point in points]


def collect_region_completion_plans(
    stage,
    *,
    mesh_helpers,
    overwrite_existing_segments: bool = False,
) -> list[RegionCompletionPlan]:
    """
    Build completion plans for all ``placeholder_area_publicspace_*`` region prims.

    ``mesh_helpers`` is ``(find_first_mesh, world_transform, transform_point)``.
    """
    plans: list[RegionCompletionPlan] = []
    for prim in stage.Traverse():
        name_info = parse_public_space_region_name(prim.GetName())
        if name_info is None:
            continue

        plan = _plan_for_region(
            prim,
            name_info,
            mesh_helpers=mesh_helpers,
            overwrite_existing_segments=overwrite_existing_segments,
        )
        if plan is not None:
            plans.append(plan)
    return plans


def _plan_for_region(
    prim,
    name_info: PublicSpaceRegionNameInfo,
    *,
    mesh_helpers,
    overwrite_existing_segments: bool,
) -> RegionCompletionPlan | None:
    from pxr import UsdGeom

    find_first_mesh, world_transform, transform_point = mesh_helpers
    region_path = str(prim.GetPath())

    attr_type = _read_attr(prim, "public_space_type")
    public_space_type = str(attr_type) if attr_type else name_info.public_space_type
    if not public_space_type or not is_known_public_space_type(public_space_type):
        return None

    ratio_raw = _read_attr(prim, "ratio_dynamic_static")
    ratio = DEFAULT_RATIO_DYNAMIC_STATIC
    set_ratio = ratio_raw is None
    if ratio_raw is not None:
        try:
            ratio = float(ratio_raw)
        except (TypeError, ValueError):
            set_ratio = True

    plan = RegionCompletionPlan(
        region_path=region_path,
        region_name=prim.GetName(),
        public_space_type=public_space_type,
        boundary_type_hint=name_info.boundary_type_hint,
        ratio_dynamic_static=ratio,
        set_public_space_type=attr_type is None and bool(name_info.public_space_type),
        set_ratio_dynamic_static=set_ratio,
    )

    boundary_vertices = _mesh_world_vertices(prim, mesh_helpers=mesh_helpers)
    if len(boundary_vertices) < 3:
        plan.notes.append("region mesh missing or too few vertices")
        return plan

    existing_segments = []
    for child in prim.GetChildren():
        child_info = parse_prim_name(child.GetName())
        if child_info is None or child_info.domain != "segment":
            continue
        existing_segments.append(child)

    if existing_segments and not overwrite_existing_segments:
        plan.notes.append(f"skip segments: {len(existing_segments)} child edge prim(s) exist")
        return plan

    try:
        segment_records = build_inferred_boundary_segment_records(
            region_path,
            boundary_vertices,
            public_space_type,
            boundary_type_hint=name_info.boundary_type_hint,
        )
    except ValueError as exc:
        plan.notes.append(f"segment synthesis failed: {exc}")
        return plan

    region_xform = UsdGeom.Xformable(prim)
    region_world = world_transform(prim)
    region_inv = region_world.GetInverse()
    del region_xform

    for record in segment_records:
        world_p0 = record["vertices"][0]  # type: ignore[index]
        world_p1 = record["vertices"][1]  # type: ignore[index]
        plan.segments.append(
            SegmentCompletionPlan(
                prim_path=str(record["prim_path"]),
                raw_name=str(record["raw_name"]),
                segment_id=int(record["segment_id"]),
                boundary_type=str(record["boundary_type"]),
                vertices=[
                    transform_point(region_inv, world_p0),
                    transform_point(region_inv, world_p1),
                ],
            )
        )

    if existing_segments and overwrite_existing_segments:
        plan.notes.append(f"replace {len(existing_segments)} existing segment prim(s)")
    else:
        plan.notes.append(f"create {len(plan.segments)} segment prim(s)")
    return plan


def apply_region_completion_plan(
    stage,
    plan: RegionCompletionPlan,
    *,
    dry_run: bool = False,
) -> list[str]:
    """Create / update region attrs and segment prims. Returns log lines."""
    from pxr import Gf, Sdf, Usd, UsdGeom

    logs: list[str] = []
    region = stage.GetPrimAtPath(plan.region_path)
    if not region or not region.IsValid():
        logs.append(f"[SKIP] missing region prim {plan.region_path}")
        return logs

    if dry_run:
        logs.append(
            f"[DRY] {plan.region_name}: type={plan.public_space_type} "
            f"segments={len(plan.segments)} notes={plan.notes}"
        )
        return logs

    if plan.set_public_space_type:
        attr = region.GetAttribute("simworld:public_space_type")
        if not attr or not attr.IsValid():
            attr = region.CreateAttribute(
                "simworld:public_space_type",
                Sdf.ValueTypeNames.Token,
            )
        attr.Set(plan.public_space_type)
        logs.append(f"[OK] {plan.region_path} simworld:public_space_type={plan.public_space_type}")

    if plan.set_ratio_dynamic_static:
        attr = region.GetAttribute("simworld:ratio_dynamic_static")
        if not attr or not attr.IsValid():
            attr = region.CreateAttribute(
                "simworld:ratio_dynamic_static",
                Sdf.ValueTypeNames.Float,
            )
        attr.Set(float(plan.ratio_dynamic_static))
        logs.append(
            f"[OK] {plan.region_path} simworld:ratio_dynamic_static={plan.ratio_dynamic_static}"
        )

    for segment in plan.segments:
        seg_prim = region.GetChild(segment.raw_name)
        if not seg_prim or not seg_prim.IsValid():
            seg_prim = UsdGeom.Xform.Define(stage, segment.prim_path).GetPrim()

        for key, value, typ in (
            ("simworld:segment_id", segment.segment_id, Sdf.ValueTypeNames.Int),
            ("simworld:boundary_type", segment.boundary_type, Sdf.ValueTypeNames.Token),
        ):
            attr = seg_prim.GetAttribute(key)
            if not attr or not attr.IsValid():
                attr = seg_prim.CreateAttribute(key, typ)
            attr.Set(value)

        mesh_path = f"{segment.prim_path}/edge_mesh"
        mesh = UsdGeom.Mesh.Define(stage, mesh_path)
        mesh.CreatePointsAttr(
            [Gf.Vec3f(float(p[0]), float(p[1]), float(p[2])) for p in segment.vertices]
        )
        mesh.CreateFaceVertexCountsAttr([2])
        mesh.CreateFaceVertexIndicesAttr([0, 1])
        logs.append(
            f"[OK] {segment.prim_path} id={segment.segment_id} "
            f"boundary_type={segment.boundary_type}"
        )

    for note in plan.notes:
        logs.append(f"[NOTE] {plan.region_name}: {note}")
    return logs


def ensure_public_space_usd(
    stage,
    *,
    mesh_helpers,
    dry_run: bool = False,
    overwrite_existing_segments: bool = False,
) -> list[str]:
    """Top-level entry: plan and apply completions for all regions on ``stage``."""
    logs: list[str] = []
    plans = collect_region_completion_plans(
        stage,
        mesh_helpers=mesh_helpers,
        overwrite_existing_segments=overwrite_existing_segments,
    )
    logs.append(f"[INFO] found {len(plans)} public-space region(s)")
    for plan in plans:
        logs.extend(
            apply_region_completion_plan(stage, plan, dry_run=dry_run)
        )
    return logs
