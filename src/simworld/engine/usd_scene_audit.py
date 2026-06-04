"""
Audit a scene USD for SimWorld parser / area-placement consumable structure.

No Isaac Sim imports. Requires OpenUSD Python bindings (``pxr``), typically via
Isaac Sim's ``python.sh`` or a USD-enabled environment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Sequence

from engine.public_space_metadata import (
    format_public_space_type_misexport_hint,
    is_known_public_space_type,
    looks_like_unset_simworld_property,
)
from engine.scene_naming import PrimNameInfo, parse_prim_name

SIMWORLD_ATTR_PREFIXES = ("simworld:", "custom:simworld:")

KNOWN_BOUNDARY_TYPES = frozenset(
    {
        "block_boundary_primary",
        "block_boundary_other",
        "street_boundary_primary",
        "street_boundary_secondary",
        "building_entrance_main",
    }
)


class Pipeline(str, Enum):
    AREA_PLACEMENT = "area_placement_methods"
    LEGACY_PLACEMENT = "legacy_placeholder_placement"
    DYNAMIC_AGENTS = "dynamic_agents"
    SPAWN = "robot_spawn"
    STATIC_SCENE = "static_scene"
    UNMATCHED_NAMED = "unmatched_naming_pattern"
    UNRELATED = "unrelated_to_parser_or_placement"


class FieldRelevance(str, Enum):
    REQUIRED_LAYOUT = "required_for_layout"
    OPTIONAL_LAYOUT = "optional_for_layout"
    GEOMETRY_LAYOUT = "geometry_for_layout"
    UNRELATED = "unrelated_to_parser_or_placement"


@dataclass(frozen=True)
class AuditRuleSpec:
    name: str
    mobility: str | None = None
    domain: str | None = None
    category: str | None = None
    pipeline: Pipeline = Pipeline.UNRELATED


# Mirrors ``scene_parser.PROCESSING_RULES`` (metadata only; no Isaac actions).
AUDIT_RULE_SPECS: tuple[AuditRuleSpec, ...] = (
    AuditRuleSpec("static construction buildings", "static", "construction", "building", Pipeline.STATIC_SCENE),
    AuditRuleSpec("static ground (domain=ground)", "static", "ground", None, Pipeline.STATIC_SCENE),
    AuditRuleSpec("static construction (domain only)", "static", "construction", None, Pipeline.STATIC_SCENE),
    AuditRuleSpec("placeholder spawn point", "placeholder", "spot", "spawn", Pipeline.SPAWN),
    AuditRuleSpec("placeholder plaza area", "placeholder", "area", "plaza", Pipeline.LEGACY_PLACEMENT),
    AuditRuleSpec("placeholder pedestrian spawn", "placeholder", "pedestrian", "spawn", Pipeline.DYNAMIC_AGENTS),
    AuditRuleSpec("placeholder pedestrian goal", "placeholder", "pedestrian", "goal", Pipeline.DYNAMIC_AGENTS),
    AuditRuleSpec("placeholder pedestrian route", "placeholder", "pedestrian", "route", Pipeline.DYNAMIC_AGENTS),
    AuditRuleSpec("placeholder pedestrian zone", "placeholder", "pedestrian", "zone", Pipeline.DYNAMIC_AGENTS),
    AuditRuleSpec("placeholder vehicle spawn", "placeholder", "vehicle", "spawn", Pipeline.DYNAMIC_AGENTS),
    AuditRuleSpec("placeholder vehicle goal", "placeholder", "vehicle", "goal", Pipeline.DYNAMIC_AGENTS),
    AuditRuleSpec("placeholder vehicle route", "placeholder", "vehicle", "route", Pipeline.DYNAMIC_AGENTS),
    AuditRuleSpec("placeholder vehicle lane", "placeholder", "vehicle", "lane", Pipeline.DYNAMIC_AGENTS),
    AuditRuleSpec("placeholder sidewalk area", "placeholder", "area", "sidewalk", Pipeline.DYNAMIC_AGENTS),
    AuditRuleSpec("placeholder crosswalk area", "placeholder", "area", "crosswalk", Pipeline.DYNAMIC_AGENTS),
    AuditRuleSpec(
        "placeholder public space region",
        "placeholder",
        "area",
        "publicspace",
        Pipeline.AREA_PLACEMENT,
    ),
    AuditRuleSpec(
        "placeholder public space boundary segment",
        "placeholder",
        "segment",
        "edge",
        Pipeline.AREA_PLACEMENT,
    ),
    AuditRuleSpec(
        "placeholder public space asset has set",
        "placeholder",
        "assetset",
        "line",
        Pipeline.AREA_PLACEMENT,
    ),
)

PUBLIC_SPACE_REGION_ROLE = "public_space_region"
PUBLIC_SPACE_SEGMENT_ROLE = "public_space_segment"
PUBLIC_SPACE_ASSETSET_ROLE = "public_space_asset_has_set"


@dataclass
class AttributeRecord:
    name: str
    value: Any
    relevance: FieldRelevance
    note: str = ""


@dataclass
class PrimAuditRecord:
    path: str
    name: str
    type_name: str
    depth: int
    parent_path: str
    name_info: PrimNameInfo | None
    matched_rule_names: list[str] = field(default_factory=list)
    pipeline: Pipeline = Pipeline.UNRELATED
    layout_role: str = ""
    simworld_fields: dict[str, Any] = field(default_factory=dict)
    attributes: list[AttributeRecord] = field(default_factory=list)
    mesh_vertex_count: int | None = None
    mesh_world_vertices: list[list[float]] = field(default_factory=list)
    mesh_sample_vertices: list[list[float]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class AuditReport:
    usd_path: str
    generated_at_utc: str
    default_prim: str
    up_axis: str
    meters_per_unit: float | None
    prim_records: list[PrimAuditRecord]
    summary: dict[str, Any] = field(default_factory=dict)
    global_issues: list[str] = field(default_factory=list)
    region_input_preview: list[dict[str, Any]] = field(default_factory=list)


def open_usd_stage(usd_path: str | Path):
    try:
        from pxr import Usd
    except ImportError as exc:
        raise ImportError(
            "OpenUSD (pxr) is required to audit USD files. Run with Isaac Sim's "
            "python.sh, e.g. scripts/audit_scene_usd.sh, or set ISAAC_PYTHON."
        ) from exc

    path = Path(usd_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    stage = Usd.Stage.Open(str(path))
    if stage is None:
        raise RuntimeError(f"Failed to open USD stage: {path}")
    return stage, path


def _rule_matches(spec: AuditRuleSpec, info: PrimNameInfo) -> bool:
    if spec.mobility is not None and spec.mobility != info.mobility:
        return False
    if spec.domain is not None and spec.domain != info.domain:
        return False
    if spec.category is not None and spec.category != info.category:
        return False
    return True


def _matching_rules(info: PrimNameInfo) -> list[AuditRuleSpec]:
    return [spec for spec in AUDIT_RULE_SPECS if _rule_matches(spec, info)]


def _read_simworld_fields(prim) -> dict[str, Any]:
    """Same key order as ``scene_public_space.read_simworld_attribute``."""
    fields = (
        "public_space_type",
        "ratio_dynamic_static",
        "segment_id",
        "boundary_type",
        "asset_has_set_id",
        "asset_has_set_type",
        "region_id",
    )
    out: dict[str, Any] = {}
    keys_checked: list[str] = []

    for field_name in fields:
        for key in (f"custom:simworld:{field_name}", f"simworld:{field_name}"):
            keys_checked.append(key)
            attr = prim.GetAttribute(key)
            if attr and attr.IsValid():
                value = attr.Get()
                if value is not None:
                    out[field_name] = value
                    break

    try:
        custom = prim.GetCustomData()
    except Exception:
        custom = None
    if isinstance(custom, dict):
        for field_name in fields:
            if field_name in out:
                continue
            for key in (field_name, f"simworld:{field_name}"):
                if key in custom and custom[key] is not None:
                    out[field_name] = custom[key]
                    break

    out["_attribute_keys_found"] = _discover_simworld_attribute_names(prim)
    return out


def _discover_simworld_attribute_names(prim) -> list[str]:
    names: list[str] = []
    for attr in prim.GetAttributes():
        name = attr.GetName()
        if "simworld" in name.lower():
            names.append(name)
    return sorted(names)


def _classify_attribute(name: str, layout_role: str) -> FieldRelevance:
    lower = name.lower()
    if any(lower.startswith(prefix) for prefix in SIMWORLD_ATTR_PREFIXES):
        short = lower.split(":")[-1]
        if layout_role == PUBLIC_SPACE_REGION_ROLE:
            if short == "public_space_type":
                return FieldRelevance.REQUIRED_LAYOUT
            if short == "ratio_dynamic_static":
                return FieldRelevance.REQUIRED_LAYOUT
            if short == "region_id":
                return FieldRelevance.OPTIONAL_LAYOUT
        if layout_role == PUBLIC_SPACE_SEGMENT_ROLE:
            if short == "boundary_type":
                return FieldRelevance.REQUIRED_LAYOUT
            if short == "segment_id":
                return FieldRelevance.REQUIRED_LAYOUT
        if layout_role == PUBLIC_SPACE_ASSETSET_ROLE:
            if short in ("asset_has_set_id", "asset_has_set_type"):
                return FieldRelevance.OPTIONAL_LAYOUT
        return FieldRelevance.OPTIONAL_LAYOUT

    if lower in ("points", "facevertexcounts", "facevertexindices", "curvevertexcounts"):
        if layout_role:
            return FieldRelevance.GEOMETRY_LAYOUT
    if lower == "extent":
        if layout_role:
            return FieldRelevance.GEOMETRY_LAYOUT

    if lower.startswith("xformop:") or lower in ("xformoporder",):
        return FieldRelevance.UNRELATED
    if "preview" in lower or lower in ("inputs:surface", "outputs:surface"):
        return FieldRelevance.UNRELATED
    if lower.startswith("primvars:") or lower.startswith("userproperties:"):
        return FieldRelevance.UNRELATED

    return FieldRelevance.UNRELATED


def _collect_attribute_records(prim, layout_role: str) -> list[AttributeRecord]:
    records: list[AttributeRecord] = []
    for attr in prim.GetAttributes():
        if not attr.IsValid():
            continue
        name = attr.GetName()
        try:
            value = attr.Get()
        except Exception:
            value = "<unreadable>"
        relevance = _classify_attribute(name, layout_role)
        note = ""
        if relevance == FieldRelevance.UNRELATED and "simworld" in name.lower():
            note = "simworld-like name but not read by parser; check Blender export prefix"
        records.append(AttributeRecord(name=name, value=value, relevance=relevance, note=note))
    return records


def _world_transform(prim):
    from pxr import Usd, UsdGeom

    return UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())


def _transform_point(matrix, point) -> list[float]:
    from pxr import Gf

    world = matrix.Transform(Gf.Vec3d(float(point[0]), float(point[1]), float(point[2])))
    return [float(world[0]), float(world[1]), float(world[2])]


def _find_first_mesh_prim(prim):
    from pxr import UsdGeom

    if prim.IsA(UsdGeom.Mesh):
        return prim
    for child in prim.GetChildren():
        found = _find_first_mesh_prim(child)
        if found is not None:
            return found
    return None


def _mesh_summary(prim) -> tuple[int | None, list[list[float]]]:
    from pxr import UsdGeom

    mesh_prim = _find_first_mesh_prim(prim)
    if mesh_prim is None:
        return None, []

    mesh = UsdGeom.Mesh(mesh_prim)
    points = mesh.GetPointsAttr().Get() or []
    if not points:
        return 0, []

    world_mat = _world_transform(mesh_prim)
    world_vertices = [_transform_point(world_mat, p) for p in points]
    sample = world_vertices[:4]
    if len(world_vertices) > 4:
        sample.append(world_vertices[-1])
    return len(world_vertices), world_vertices, sample


def _assign_layout_role(info: PrimNameInfo | None, matched: Sequence[AuditRuleSpec]) -> str:
    if info is None:
        return ""
    if info.mobility == "placeholder" and info.domain == "area" and info.category == "publicspace":
        return PUBLIC_SPACE_REGION_ROLE
    if info.mobility == "placeholder" and info.domain == "segment" and info.category == "edge":
        return PUBLIC_SPACE_SEGMENT_ROLE
    if info.mobility == "placeholder" and info.domain == "assetset" and info.category == "line":
        return PUBLIC_SPACE_ASSETSET_ROLE
    if any(spec.pipeline == Pipeline.AREA_PLACEMENT for spec in matched):
        return matched[0].name
    if any(spec.pipeline == Pipeline.LEGACY_PLACEMENT for spec in matched):
        return "legacy_placeholder_area"
    return ""


def _validate_public_space_region(record: PrimAuditRecord) -> None:
    from engine.public_space_compact_naming import parse_public_space_region_name

    name_info = parse_public_space_region_name(record.name)
    ptype = record.simworld_fields.get("public_space_type")
    if ptype is None and name_info and name_info.public_space_type:
        ptype = name_info.public_space_type
        record.notes.append(
            f"public_space_type from prim name: {name_info.public_space_type}"
        )
    if name_info and name_info.boundary_type_hint:
        record.notes.append(
            f"boundary_type hint from prim name: {name_info.boundary_type_hint}"
        )
    if ptype is None:
        record.issues.append(
            "missing simworld:public_space_type (required for layout; "
            "or encode compact type in "
            "placeholder_area_publicspace_<index>_<typecompact>)"
        )
    elif looks_like_unset_simworld_property(ptype):
        record.issues.append(format_public_space_type_misexport_hint(record.path, ptype))
    elif not is_known_public_space_type(ptype):
        record.issues.append(
            f"unknown public_space_type={ptype!r}; expected one of "
            f"{sorted(KNOWN_PUBLIC_SPACE_TYPES)}"
        )

    ratio = record.simworld_fields.get("ratio_dynamic_static")
    if ratio is None:
        record.notes.append("ratio_dynamic_static missing; parser defaults to 0.36")
    else:
        try:
            rv = float(ratio)
            if not 0.0 <= rv <= 1.0:
                record.issues.append(f"ratio_dynamic_static={rv} outside [0, 1]")
        except (TypeError, ValueError):
            record.issues.append(f"ratio_dynamic_static not numeric: {ratio!r}")

    if record.mesh_vertex_count is None:
        record.issues.append("no UsdGeom.Mesh under region prim (boundary vertices required)")
    elif record.mesh_vertex_count < 3:
        record.issues.append(
            f"region mesh has {record.mesh_vertex_count} vertices; need at least 3"
        )


def _validate_public_space_segment(
    record: PrimAuditRecord,
    parent_region_path: str | None,
) -> None:
    if not parent_region_path:
        record.issues.append(
            "segment prim is not under a placeholder_area_publicspace_* ancestor"
        )

    boundary = record.simworld_fields.get("boundary_type")
    if boundary is None:
        record.issues.append("missing simworld:boundary_type")
    elif looks_like_unset_simworld_property(boundary):
        record.issues.append(
            f"boundary_type={boundary!r} looks like unset Blender custom property"
        )
    elif str(boundary) not in KNOWN_BOUNDARY_TYPES:
        record.notes.append(
            f"boundary_type={boundary!r} not in known enum sample; may still work in proto"
        )

    if record.mesh_vertex_count is None:
        record.issues.append("no mesh for segment line endpoints")
    elif record.mesh_vertex_count < 2:
        record.issues.append(
            f"segment mesh has {record.mesh_vertex_count} vertices; need at least 2"
        )


def _collect_prim_records(stage) -> list[PrimAuditRecord]:
    records: list[PrimAuditRecord] = []
    for prim in stage.Traverse():
        path = str(prim.GetPath())
        if path == "/":
            continue
        parent = prim.GetParent()
        parent_path = str(parent.GetPath()) if parent else ""
        depth = path.count("/") - 1
        name = prim.GetName()
        info = parse_prim_name(name)
        matched_specs = _matching_rules(info) if info else []
        matched_names = [spec.name for spec in matched_specs]

        if info and matched_specs:
            pipeline = matched_specs[0].pipeline
        elif info:
            pipeline = Pipeline.UNMATCHED_NAMED
        else:
            pipeline = Pipeline.UNRELATED

        layout_role = _assign_layout_role(info, matched_specs)
        simworld = _read_simworld_fields(prim) if layout_role else {}
        mesh_count, mesh_world, mesh_sample = (
            _mesh_summary(prim) if layout_role else (None, [], [])
        )

        record = PrimAuditRecord(
            path=path,
            name=name,
            type_name=prim.GetTypeName(),
            depth=depth,
            parent_path=parent_path,
            name_info=info,
            matched_rule_names=matched_names,
            pipeline=pipeline,
            layout_role=layout_role,
            simworld_fields=simworld,
            attributes=_collect_attribute_records(prim, layout_role),
            mesh_vertex_count=mesh_count,
            mesh_world_vertices=mesh_world,
            mesh_sample_vertices=mesh_sample,
        )

        if pipeline == Pipeline.UNMATCHED_NAMED:
            record.issues.append(
                "prim name matches mobility_domain_category_index but no parser rule"
            )

        records.append(record)

    regions = {
        r.path: r
        for r in records
        if r.layout_role == PUBLIC_SPACE_REGION_ROLE
    }

    def parent_public_space_path(prim_path: str) -> str | None:
        parts = prim_path.strip("/").split("/")
        for i in range(len(parts) - 1, 0, -1):
            candidate = "/" + "/".join(parts[:i])
            if candidate in regions:
                return candidate
        return None

    for record in records:
        if record.layout_role == PUBLIC_SPACE_REGION_ROLE:
            _validate_public_space_region(record)
        elif record.layout_role == PUBLIC_SPACE_SEGMENT_ROLE:
            _validate_public_space_segment(record, parent_public_space_path(record.path))
        elif record.layout_role == PUBLIC_SPACE_ASSETSET_ROLE:
            if not parent_public_space_path(record.path):
                record.issues.append("asset-has-set not under public-space region root")

    return records


def _build_summary(records: Sequence[PrimAuditRecord]) -> dict[str, Any]:
    by_pipeline: dict[str, int] = {}
    issue_count = 0
    layout_ready_regions = 0
    for record in records:
        key = record.pipeline.value
        by_pipeline[key] = by_pipeline.get(key, 0) + 1
        issue_count += len(record.issues)
        if (
            record.layout_role == PUBLIC_SPACE_REGION_ROLE
            and not record.issues
        ):
            layout_ready_regions += 1

    regions = [r for r in records if r.layout_role == PUBLIC_SPACE_REGION_ROLE]
    segments = [r for r in records if r.layout_role == PUBLIC_SPACE_SEGMENT_ROLE]

    return {
        "prim_count": len(records),
        "by_pipeline": by_pipeline,
        "public_space_regions": len(regions),
        "public_space_segments": len(segments),
        "layout_ready_regions": layout_ready_regions,
        "total_issues": issue_count,
    }


def _try_region_input_previews(records: Sequence[PrimAuditRecord]) -> list[dict[str, Any]]:
    """Optional adapter preview when algorithm_lab module is on PYTHONPATH."""
    regions = [r for r in records if r.layout_role == PUBLIC_SPACE_REGION_ROLE]
    if not regions:
        return []

    try:
        import sys
        from pathlib import Path as _Path

        module_dir = (
            _Path(__file__).resolve().parents[3]
            / "algorithm_lab"
            / "experiments"
            / "area_placement_methods"
            / "module"
        )
        if str(module_dir) not in sys.path:
            sys.path.insert(0, str(module_dir))
        from adapters.public_space_region import public_space_region_to_region_input
    except Exception as exc:
        return [{"error": f"region_input preview unavailable: {exc}"}]

    path_to_record = {r.path: r for r in records}
    region_paths = {r.path for r in regions}

    def region_ancestor(prim_path: str) -> str | None:
        current = path_to_record.get(prim_path)
        while current and current.path != "/":
            if current.path in region_paths:
                return current.path
            current = path_to_record.get(current.parent_path)
        return None

    segments_by_parent: dict[str, list[PrimAuditRecord]] = {}
    for record in records:
        if record.layout_role != PUBLIC_SPACE_SEGMENT_ROLE:
            continue
        parent = region_ancestor(record.path)
        if parent:
            segments_by_parent.setdefault(parent, []).append(record)

    previews: list[dict[str, Any]] = []
    for region in regions:
        seg_records = segments_by_parent.get(region.path, [])
        from engine.public_space_compact_naming import parse_public_space_region_name
        from engine.public_space_geometry import build_inferred_boundary_segment_records

        name_info = parse_public_space_region_name(region.name)
        public_space_type = region.simworld_fields.get("public_space_type")
        if not public_space_type and name_info is not None:
            public_space_type = name_info.public_space_type
        boundary_hint = name_info.boundary_type_hint if name_info else ""

        segment_payloads = [
            {
                "segment_id": seg.simworld_fields.get("segment_id"),
                "boundary_type": seg.simworld_fields.get("boundary_type"),
                "vertices": seg.mesh_world_vertices,
            }
            for seg in seg_records
        ]
        synthesized = False
        if len(segment_payloads) < 3 and region.mesh_world_vertices and public_space_type:
            try:
                synthetic = build_inferred_boundary_segment_records(
                    region.path,
                    region.mesh_world_vertices,
                    str(public_space_type),
                    boundary_type_hint=boundary_hint,
                )
                segment_payloads = [
                    {
                        "segment_id": item["segment_id"],
                        "boundary_type": item["boundary_type"],
                        "vertices": item["vertices"],
                    }
                    for item in synthetic
                ]
                synthesized = True
            except ValueError:
                pass

        payload = {
            "region_id": region.name,
            "prim_path": region.path,
            "raw_name": region.name,
            "public_space_type": public_space_type,
            "ratio_dynamic_static": region.simworld_fields.get("ratio_dynamic_static", 0.36),
            "boundary_vertices": region.mesh_world_vertices,
            "segments": segment_payloads,
            "asset_has_set": [],
        }
        try:
            converted = public_space_region_to_region_input(payload)
            previews.append(
                {
                    "region_id": region.path,
                    "status": "ok",
                    "public_space_type": converted.get("public_space_type"),
                    "segment_count": len(converted.get("public_space_segments") or []),
                    "geometry_point_count": len(
                        (converted.get("public_space_geometry") or {}).get("coordinates") or []
                    ),
                    "segments_synthesized": synthesized,
                }
            )
        except Exception as exc:
            previews.append(
                {"region_id": region.path, "status": "error", "error": str(exc)}
            )
    return previews


def audit_usd_file(usd_path: str | Path, *, include_region_input_preview: bool = True) -> AuditReport:
    stage, path = open_usd_stage(usd_path)
    records = _collect_prim_records(stage)

    up_axis = ""
    meters_per_unit = None
    try:
        from pxr import UsdGeom

        up_axis = str(UsdGeom.GetStageUpAxis(stage))
        meters_per_unit = float(UsdGeom.GetStageMetersPerUnit(stage))
    except Exception:
        pass

    default_prim = ""
    if stage.HasDefaultPrim():
        default_prim = str(stage.GetDefaultPrim().GetPath())

    global_issues: list[str] = []
    regions = [r for r in records if r.layout_role == PUBLIC_SPACE_REGION_ROLE]
    if not regions:
        global_issues.append(
            "No placeholder_area_publicspace_* region found; area_placement_methods "
            "will not run from USD alone."
        )

    preview: list[dict[str, Any]] = []
    if include_region_input_preview:
        preview = _try_region_input_previews(records)

    report = AuditReport(
        usd_path=str(path),
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        default_prim=default_prim,
        up_axis=up_axis,
        meters_per_unit=meters_per_unit,
        prim_records=records,
        summary=_build_summary(records),
        global_issues=global_issues,
        region_input_preview=preview,
    )
    return report


def _fmt_value(value: Any, max_len: int = 80) -> str:
    text = repr(value)
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def _relevance_label(rel: FieldRelevance) -> str:
    return {
        FieldRelevance.REQUIRED_LAYOUT: "required (layout)",
        FieldRelevance.OPTIONAL_LAYOUT: "optional (layout)",
        FieldRelevance.GEOMETRY_LAYOUT: "geometry (layout)",
        FieldRelevance.UNRELATED: "unrelated",
    }[rel]


def render_audit_markdown(report: AuditReport) -> str:
    lines: list[str] = []
    lines.append(f"# USD scene audit: `{report.usd_path}`")
    lines.append("")
    lines.append(f"- Generated (UTC): `{report.generated_at_utc}`")
    lines.append(f"- Default prim: `{report.default_prim or '(none)'}`")
    lines.append(f"- Up axis: `{report.up_axis}`")
    if report.meters_per_unit is not None:
        lines.append(f"- Meters per unit: `{report.meters_per_unit}`")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    summary = report.summary
    lines.append(f"| Metric | Value |")
    lines.append(f"| --- | --- |")
    lines.append(f"| Prims traversed | {summary.get('prim_count', 0)} |")
    lines.append(
        f"| Public-space regions | {summary.get('public_space_regions', 0)} "
        f"(layout-ready: {summary.get('layout_ready_regions', 0)}) |"
    )
    lines.append(f"| Public-space segments | {summary.get('public_space_segments', 0)} |")
    lines.append(f"| Issue count (prim-level) | {summary.get('total_issues', 0)} |")
    lines.append("")

    lines.append("### Prims by pipeline")
    lines.append("")
    lines.append("| Pipeline | Count | Meaning |")
    lines.append("| --- | --- | --- |")
    pipeline_help = {
        Pipeline.AREA_PLACEMENT.value: "Consumed by `area_placement_methods` (publicspace + segments)",
        Pipeline.LEGACY_PLACEMENT.value: "Legacy grid placement (`placeholder_area_plaza_*`, etc.)",
        Pipeline.DYNAMIC_AGENTS.value: "Pedestrian / vehicle placeholders",
        Pipeline.SPAWN.value: "Robot spawn spot",
        Pipeline.STATIC_SCENE.value: "Collision / visuals only",
        Pipeline.UNMATCHED_NAMED.value: "Matches naming pattern but no `scene_parser` rule",
        Pipeline.UNRELATED.value: "Lights, materials, root Xform, etc.",
    }
    for key, count in sorted((summary.get("by_pipeline") or {}).items()):
        lines.append(f"| `{key}` | {count} | {pipeline_help.get(key, '')} |")
    lines.append("")

    if report.global_issues:
        lines.append("## Global issues")
        lines.append("")
        for issue in report.global_issues:
            lines.append(f"- {issue}")
        lines.append("")

    if report.region_input_preview:
        lines.append("## Region-input conversion preview")
        lines.append("")
        lines.append(
            "Dry-run of `public_space_region_to_region_input` (same adapter as Isaac layout). "
            "Does not execute placement steps 1–5."
        )
        lines.append("")
        for item in report.region_input_preview:
            if item.get("status") == "ok":
                lines.append(
                    f"- `{item['region_id']}`: **ok** — type=`{item.get('public_space_type')}`, "
                    f"segments={item.get('segment_count')}, "
                    f"geometry points={item.get('geometry_point_count')}"
                )
            else:
                lines.append(f"- `{item.get('region_id')}`: **error** — {item.get('error')}")
        lines.append("")

    lines.append("## Scene structure (by prim path)")
    lines.append("")
    lines.append(
        "Legend: **role** = layout sub-role; **pipeline** = SimWorld consumer; "
        "✓ = no issues on this prim."
    )
    lines.append("")
    for record in report.prim_records:
        indent = "  " * record.depth
        flag = "✓" if not record.issues else "✗"
        role = record.layout_role or "—"
        lines.append(
            f"{indent}- {flag} `{record.path}` ({record.type_name}) "
            f"— pipeline=`{record.pipeline.value}`, role=`{role}`"
        )
        if record.matched_rule_names:
            lines.append(
                f"{indent}  - parser rules: {', '.join(record.matched_rule_names)}"
            )
        if record.simworld_fields:
            fields = {
                k: v
                for k, v in record.simworld_fields.items()
                if not k.startswith("_")
            }
            if fields:
                lines.append(f"{indent}  - simworld fields: `{fields}`")
            extra_keys = record.simworld_fields.get("_attribute_keys_found") or []
            if extra_keys:
                lines.append(
                    f"{indent}  - simworld attribute names on prim: `{extra_keys}`"
                )
        if record.mesh_vertex_count is not None:
            lines.append(
                f"{indent}  - mesh vertices (world): {record.mesh_vertex_count} "
                f"sample={record.mesh_sample_vertices}"
            )
        for issue in record.issues:
            lines.append(f"{indent}  - **issue:** {issue}")
        for note in record.notes:
            lines.append(f"{indent}  - note: {note}")
    lines.append("")

    layout_prims = [
        r
        for r in report.prim_records
        if r.pipeline == Pipeline.AREA_PLACEMENT or r.layout_role
    ]
    if layout_prims:
        lines.append("## Area-placement prim detail (attributes)")
        lines.append("")
        for record in layout_prims:
            lines.append(f"### `{record.path}`")
            lines.append("")
            if not record.attributes:
                lines.append("_No attributes._")
                lines.append("")
                continue
            lines.append("| Attribute | Value | Relevance |")
            lines.append("| --- | --- | --- |")
            for attr in sorted(
                record.attributes,
                key=lambda item: (item.relevance.value, item.name),
            ):
                note = f" — {attr.note}" if attr.note else ""
                lines.append(
                    f"| `{attr.name}` | `{_fmt_value(attr.value)}` | "
                    f"{_relevance_label(attr.relevance)}{note} |"
                )
            lines.append("")

    unrelated = [
        r
        for r in report.prim_records
        if r.pipeline == Pipeline.UNRELATED
        and r.type_name not in ("",)
    ]
    if unrelated:
        lines.append("## Unrelated prims (parser / placement ignore)")
        lines.append("")
        lines.append(
            "Typical scene authoring: lights, materials, shaders, anonymous scopes. "
            "Safe to ignore for `area_placement_methods`."
        )
        lines.append("")
        for record in unrelated[:40]:
            lines.append(f"- `{record.path}` ({record.type_name})")
        if len(unrelated) > 40:
            lines.append(f"- … and {len(unrelated) - 40} more")
        lines.append("")

    lines.append("## Reference")
    lines.append("")
    lines.append("- Naming: `algorithm_lab/experiments/area_placement_methods/docs/USD_PLACEHOLDER_NAMING.md`")
    lines.append("- Parser: `src/simworld/isaac_env/isaac_scene/scene_parser.py` (`PROCESSING_RULES`)")
    lines.append("- Re-run: `scripts/audit_scene_usd.sh --usd <file.usd> -o report.md`")
    lines.append("")

    return "\n".join(lines)


def write_audit_markdown(
    usd_path: str | Path,
    output_path: str | Path,
    *,
    include_region_input_preview: bool = True,
) -> AuditReport:
    report = audit_usd_file(usd_path, include_region_input_preview=include_region_input_preview)
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_audit_markdown(report), encoding="utf-8")
    return report
