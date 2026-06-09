from ..isaac_adaptor import isaac_context as iscctx

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence

from engine.scene_naming import PrimNameInfo, parse_prim_name


@dataclass
class PlaceholderPoint:
    position: list[float] = field(default_factory=list)
    prim_path: str = ""
    raw_name: str = ""
    index: str = ""


@dataclass
class PlaceholderArea:
    vertices: list[list[float]] = field(default_factory=list)
    prim_path: str = ""
    raw_name: str = ""
    category: str = ""
    index: str = ""


@dataclass
class PlaceholderBoundarySegment:
    vertices: list[list[float]] = field(default_factory=list)
    prim_path: str = ""
    raw_name: str = ""
    index: str = ""
    segment_id: int = 0
    boundary_type: str = ""
    parent_region_prim_path: str = ""


@dataclass
class PlaceholderAssetHasSet:
    vertices: list[list[float]] = field(default_factory=list)
    prim_path: str = ""
    raw_name: str = ""
    index: str = ""
    asset_has_set_id: int = 0
    asset_has_set_type: str = ""
    parent_region_prim_path: str = ""


@dataclass
class PlaceholderPublicSpaceRegion:
    boundary_vertices: list[list[float]] = field(default_factory=list)
    prim_path: str = ""
    raw_name: str = ""
    index: str = ""
    public_space_type: str = ""
    boundary_type_hint: str = ""
    ratio_dynamic_static: float = 0.36
    segments: list[PlaceholderBoundarySegment] = field(default_factory=list)
    asset_has_sets: list[PlaceholderAssetHasSet] = field(default_factory=list)


@dataclass
class PlaceholderPath:
    vertices: list[list[float]] = field(default_factory=list)
    prim_path: str = ""
    raw_name: str = ""
    category: str = ""
    index: str = ""


@dataclass
class SceneStats:
    spawn_points: list[list[float]] = field(default_factory=list)
    placeholder_areas: list[PlaceholderArea] = field(default_factory=list)

    pedestrian_spawn_points: list[PlaceholderPoint] = field(default_factory=list)
    pedestrian_goal_points: list[PlaceholderPoint] = field(default_factory=list)
    pedestrian_routes: list[PlaceholderPath] = field(default_factory=list)
    pedestrian_zones: list[PlaceholderArea] = field(default_factory=list)
    camera_paths: list[PlaceholderPath] = field(default_factory=list)

    vehicle_spawn_points: list[PlaceholderPoint] = field(default_factory=list)
    vehicle_goal_points: list[PlaceholderPoint] = field(default_factory=list)
    vehicle_routes: list[PlaceholderPath] = field(default_factory=list)
    vehicle_lanes: list[PlaceholderArea] = field(default_factory=list)

    sidewalk_areas: list[PlaceholderArea] = field(default_factory=list)
    crosswalk_areas: list[PlaceholderArea] = field(default_factory=list)
    public_space_regions: list[PlaceholderPublicSpaceRegion] = field(
        default_factory=list
    )
    public_space_boundary_segments: list[PlaceholderBoundarySegment] = field(
        default_factory=list
    )
    public_space_asset_has_sets: list[PlaceholderAssetHasSet] = field(
        default_factory=list
    )
    public_space_parse_warnings: list[str] = field(default_factory=list)
    skipped_dynamic_placeholders: list[str] = field(default_factory=list)
    placeholder_prim_paths: list[str] = field(default_factory=list)

    visited: int = 0
    matched: int = 0
    invalid_name: int = 0
    unmatched_named: int = 0
    processed: dict[str, int] = field(default_factory=dict)

    def record_match(self, rule_name: str) -> None:
        self.matched += 1
        self.processed[rule_name] = self.processed.get(rule_name, 0) + 1


def transform_point(mat, p):
    Gf = iscctx.get_isaac_context().pxr_gf
    p4 = mat.Transform(Gf.Vec3d(float(p[0]), float(p[1]), float(p[2])))
    return [float(p4[0]), float(p4[1]), float(p4[2])]


def extract_prim_position(prim):
    if not prim.IsValid():
        raise RuntimeError("Invalid prim")

    omni_usd = iscctx.get_isaac_context().omni_usd
    world_mat = omni_usd.get_world_transform_matrix(prim)
    pos = world_mat.ExtractTranslation()

    return [float(pos[0]), float(pos[1]), float(pos[2])]


def extract_mesh_world_vertices(prim):
    if not prim.IsValid():
        raise RuntimeError("Invalid prim")

    UsdGeom = iscctx.get_isaac_context().pxr_usd_geom
    omni_usd = iscctx.get_isaac_context().omni_usd
    if not prim.IsA(UsdGeom.Mesh):
        raise RuntimeError("Prim is not a UsdGeom.Mesh")

    mesh = UsdGeom.Mesh(prim)

    points = mesh.GetPointsAttr().Get()
    face_counts = mesh.GetFaceVertexCountsAttr().Get()
    face_indices = mesh.GetFaceVertexIndicesAttr().Get()

    world_mat = omni_usd.get_world_transform_matrix(prim)

    world_vertices = [transform_point(world_mat, p) for p in points]

    return {
        "world_vertices": world_vertices,
        "face_vertex_counts": list(face_counts),
        "face_vertex_indices": list(face_indices),
        "world_matrix": world_mat,
    }


def extract_mesh_world_vertices_from_path(stage, mesh_prim_path: str):
    prim = stage.GetPrimAtPath(mesh_prim_path)

    return extract_mesh_world_vertices(prim)


def find_first_mesh_prim(prim):
    UsdGeom = iscctx.get_isaac_context().pxr_usd_geom

    if prim.IsA(UsdGeom.Mesh):
        return prim

    for child in prim.GetChildren():
        mesh_prim = find_first_mesh_prim(child)
        if mesh_prim is not None:
            return mesh_prim

    return None


def extract_mesh_world_vertices_from_prim_or_child(prim):
    mesh_prim = find_first_mesh_prim(prim)
    if mesh_prim is None:
        raise RuntimeError(f"Placeholder prim has no mesh descendant: {prim.GetPath()}")

    return extract_mesh_world_vertices(mesh_prim)


def make_placeholder_point(prim, info: "PrimNameInfo", z_offset: float = 0.0):
    pos = extract_prim_position(prim)
    pos[2] += z_offset
    return PlaceholderPoint(
        position=pos,
        prim_path=str(prim.GetPath()),
        raw_name=info.raw_name,
        index=info.index,
    )


def make_placeholder_area(prim, info: "PrimNameInfo"):
    res = extract_mesh_world_vertices_from_prim_or_child(prim)
    return PlaceholderArea(
        vertices=res["world_vertices"],
        prim_path=str(prim.GetPath()),
        raw_name=info.raw_name,
        category=info.category,
        index=info.index,
    )


def make_placeholder_path(prim, info: "PrimNameInfo"):
    res = extract_mesh_world_vertices_from_prim_or_child(prim)
    return PlaceholderPath(
        vertices=res["world_vertices"],
        prim_path=str(prim.GetPath()),
        raw_name=info.raw_name,
        category=info.category,
        index=info.index,
    )


def record_placeholder_prim(stats: SceneStats, prim) -> None:
    prim_path = str(prim.GetPath())
    if prim_path and prim_path not in stats.placeholder_prim_paths:
        stats.placeholder_prim_paths.append(prim_path)


def record_dynamic_placeholder_skip(
    stats: "SceneStats",
    prim,
    info: "PrimNameInfo",
    reason: str,
):
    message = f"{prim.GetPath()} ({info.raw_name}): {reason}"
    stats.skipped_dynamic_placeholders.append(message)
    print(f"[WARN] Skipping dynamic placeholder {message}")


def try_make_placeholder_point(
    prim,
    info: "PrimNameInfo",
    stats: "SceneStats",
    z_offset: float = 0.0,
):
    try:
        return make_placeholder_point(prim, info, z_offset=z_offset)
    except Exception as exc:
        record_dynamic_placeholder_skip(stats, prim, info, str(exc))
        return None


def try_make_placeholder_area(prim, info: "PrimNameInfo", stats: "SceneStats"):
    try:
        area = make_placeholder_area(prim, info)
        if len(area.vertices) < 3:
            raise RuntimeError(
                f"Area placeholder needs at least 3 vertices, got {len(area.vertices)}"
            )
        return area
    except Exception as exc:
        record_dynamic_placeholder_skip(stats, prim, info, str(exc))
        return None


def try_make_placeholder_path(prim, info: "PrimNameInfo", stats: "SceneStats"):
    try:
        path = make_placeholder_path(prim, info)
        if len(path.vertices) < 2:
            raise RuntimeError(
                f"Path placeholder needs at least 2 vertices, got {len(path.vertices)}"
            )
        return path
    except Exception as exc:
        record_dynamic_placeholder_skip(stats, prim, info, str(exc))
        return None


# def _normalize_vec3(v: Gf.Vec3d) -> Gf.Vec3d:
#     v = Gf.Vec3d(v)
#     length = v.GetLength()
#     if length > 1e-8:
#         v /= length
#     return v


# def get_prim_world_pose(
#     prim_path: str,
#     local_forward_axis=Gf.Vec3d(1.0, 0.0, 0.0),
#     local_right_axis=Gf.Vec3d(0.0, -1.0, 0.0),
#     local_up_axis=Gf.Vec3d(0.0, 0.0, 1.0),
# ):
#     """
#     Get world position and orientation vectors of a USD prim.

#     Args:
#         prim_path:
#             USD prim path, e.g. "/World/Robot/Spot".
#         local_forward_axis:
#             Which local axis should be treated as the prim's forward direction.
#             Default assumes local +X is forward.
#         local_right_axis:
#             Which local axis should be treated as the prim's right direction.
#         local_up_axis:
#             Which local axis should be treated as the prim's up direction.

#     Returns:
#         dict with:
#             position: [x, y, z]
#             forward: [x, y, z]
#             right: [x, y, z]
#             up: [x, y, z]
#             rotation: Gf.Rotation
#             matrix: Gf.Matrix4d
#     """
#     stage = omni.usd.get_context().get_stage()

#     prim = stage.GetPrimAtPath(prim_path)

#     if not prim.IsValid():
#         raise RuntimeError(f"Invalid prim path: {prim_path}")

#     world_mat = omni.usd.get_world_transform_matrix(prim)

#     pos = world_mat.ExtractTranslation()
#     rot = world_mat.ExtractRotation()

#     forward = _normalize_vec3(rot.TransformDir(local_forward_axis))
#     right = _normalize_vec3(rot.TransformDir(local_right_axis))
#     up = _normalize_vec3(rot.TransformDir(local_up_axis))

#     return {
#         "position": [float(pos[0]), float(pos[1]), float(pos[2])],
#         "forward": [float(forward[0]), float(forward[1]), float(forward[2])],
#         "right": [float(right[0]), float(right[1]), float(right[2])],
#         "up": [float(up[0]), float(up[1]), float(up[2])],
#         "rotation": rot,
#         "matrix": world_mat,
#     }


SceneAction = Callable[[Any, PrimNameInfo, SceneStats], None]


@dataclass
class ProcessingRule:
    name: str
    mobility: str | None = None
    domain: str | None = None
    category: str | None = None
    prim_type: str | None = None
    actions: list[SceneAction] = field(default_factory=list)


def rule_matches(rule: ProcessingRule, info: PrimNameInfo, prim) -> bool:
    if rule.mobility is not None and rule.mobility != info.mobility:
        return False

    if rule.domain is not None and rule.domain != info.domain:
        return False

    if rule.category is not None and rule.category != info.category:
        return False

    if rule.prim_type is not None and rule.prim_type != prim.GetTypeName():
        return False

    return True


def apply_static_collision(prim, info: PrimNameInfo, stats: SceneStats):
    """
    Apply static collision to a prim.
    If the prim is a Mesh, also apply MeshCollisionAPI.
    """
    UsdGeom = iscctx.get_isaac_context().pxr_usd_geom
    UsdPhysics = iscctx.get_isaac_context().pxr_usd_physics

    if not prim.IsA(UsdGeom.Xformable):
        return

    if not prim.HasAPI(UsdPhysics.CollisionAPI):
        UsdPhysics.CollisionAPI.Apply(prim)

    if prim.IsA(UsdGeom.Mesh):
        if prim.HasAPI(UsdPhysics.MeshCollisionAPI):
            mesh_collision = UsdPhysics.MeshCollisionAPI(prim)
        else:
            mesh_collision = UsdPhysics.MeshCollisionAPI.Apply(prim)
        mesh_collision.CreateApproximationAttr().Set("meshSimplification")

    # print(f"[COLLISION] {prim.GetPath()} <- {info.raw_name}")


def process_placeholder_area(prim, info: PrimNameInfo, stats: SceneStats):
    stats.placeholder_areas.append(make_placeholder_area(prim, info))


def set_spawn_point_from_prim(prim, info: PrimNameInfo, stats: SceneStats):
    point = make_placeholder_point(prim, info, z_offset=0.8)
    stats.spawn_points.append(point.position)
    # print(f"[SPAWN] {prim.GetPath()} <- {info.raw_name} | position = {point.position}")


def record_pedestrian_spawn(prim, info: PrimNameInfo, stats: SceneStats):
    point = try_make_placeholder_point(prim, info, stats)
    if point is not None:
        stats.pedestrian_spawn_points.append(point)


def record_pedestrian_goal(prim, info: PrimNameInfo, stats: SceneStats):
    point = try_make_placeholder_point(prim, info, stats)
    if point is not None:
        stats.pedestrian_goal_points.append(point)


def record_pedestrian_route(prim, info: PrimNameInfo, stats: SceneStats):
    path = try_make_placeholder_path(prim, info, stats)
    if path is not None:
        stats.pedestrian_routes.append(path)


def record_camera_path(prim, info: PrimNameInfo, stats: SceneStats):
    path = try_make_placeholder_path(prim, info, stats)
    if path is not None:
        stats.camera_paths.append(path)


def record_pedestrian_zone(prim, info: PrimNameInfo, stats: SceneStats):
    area = try_make_placeholder_area(prim, info, stats)
    if area is not None:
        stats.pedestrian_zones.append(area)


def record_vehicle_spawn(prim, info: PrimNameInfo, stats: SceneStats):
    point = try_make_placeholder_point(prim, info, stats)
    if point is not None:
        stats.vehicle_spawn_points.append(point)


def record_vehicle_goal(prim, info: PrimNameInfo, stats: SceneStats):
    point = try_make_placeholder_point(prim, info, stats)
    if point is not None:
        stats.vehicle_goal_points.append(point)


def record_vehicle_route(prim, info: PrimNameInfo, stats: SceneStats):
    path = try_make_placeholder_path(prim, info, stats)
    if path is not None:
        stats.vehicle_routes.append(path)


def record_vehicle_lane(prim, info: PrimNameInfo, stats: SceneStats):
    area = try_make_placeholder_area(prim, info, stats)
    if area is not None:
        stats.vehicle_lanes.append(area)


def record_sidewalk_area(prim, info: PrimNameInfo, stats: SceneStats):
    area = try_make_placeholder_area(prim, info, stats)
    if area is not None:
        stats.sidewalk_areas.append(area)


def record_crosswalk_area(prim, info: PrimNameInfo, stats: SceneStats):
    area = try_make_placeholder_area(prim, info, stats)
    if area is not None:
        stats.crosswalk_areas.append(area)


def record_public_space_region(prim, info: PrimNameInfo, stats: SceneStats):
    from .scene_public_space import (
        DEFAULT_RATIO_DYNAMIC_STATIC,
        format_public_space_type_misexport_hint,
        is_known_public_space_type,
        looks_like_unset_simworld_property,
        read_simworld_attribute,
    )

    area = try_make_placeholder_area(prim, info, stats)
    if area is None:
        return

    public_space_type = read_simworld_attribute(prim, "public_space_type") or ""
    if not public_space_type and info.public_space_type:
        public_space_type = info.public_space_type
    if not public_space_type:
        stats.public_space_parse_warnings.append(
            f"{prim.GetPath()}: missing simworld:public_space_type "
            "(set attribute or use placeholder_area_publicspace_<index>_<typecompact>)"
        )
        return

    if looks_like_unset_simworld_property(public_space_type) or not is_known_public_space_type(
        public_space_type
    ):
        stats.public_space_parse_warnings.append(
            format_public_space_type_misexport_hint(prim.GetPath(), public_space_type)
        )
        return

    ratio = read_simworld_attribute(
        prim,
        "ratio_dynamic_static",
        DEFAULT_RATIO_DYNAMIC_STATIC,
    )
    try:
        ratio_value = float(ratio)
    except (TypeError, ValueError):
        ratio_value = DEFAULT_RATIO_DYNAMIC_STATIC

    region = PlaceholderPublicSpaceRegion(
        boundary_vertices=list(area.vertices),
        prim_path=area.prim_path,
        raw_name=area.raw_name,
        index=area.index,
        public_space_type=str(public_space_type),
        boundary_type_hint=getattr(info, "boundary_type_hint", "") or "",
        ratio_dynamic_static=ratio_value,
    )
    stats.public_space_regions.append(region)


def record_public_space_boundary_segment(prim, info: PrimNameInfo, stats: SceneStats):
    from .scene_public_space import (
        find_parent_public_space_prim_path,
        looks_like_unset_simworld_property,
        read_simworld_attribute,
    )

    try:
        mesh = extract_mesh_world_vertices_from_prim_or_child(prim)
        vertices = mesh["world_vertices"]
    except Exception as exc:
        stats.public_space_parse_warnings.append(
            f"{prim.GetPath()}: cannot read segment mesh ({exc})"
        )
        return

    boundary_type = read_simworld_attribute(prim, "boundary_type")
    if not boundary_type:
        stats.public_space_parse_warnings.append(
            f"{prim.GetPath()}: missing simworld:boundary_type"
        )
        return
    if looks_like_unset_simworld_property(boundary_type):
        stats.public_space_parse_warnings.append(
            f"{prim.GetPath()}: simworld:boundary_type={boundary_type!r} looks like an "
            "unset Blender custom property; set the value (e.g. block_boundary_primary)."
        )
        return

    segment_id = read_simworld_attribute(prim, "segment_id", info.index)
    try:
        segment_id_value = int(segment_id)
    except (TypeError, ValueError):
        segment_id_value = 0

    segment = PlaceholderBoundarySegment(
        vertices=vertices,
        prim_path=str(prim.GetPath()),
        raw_name=info.raw_name,
        index=info.index,
        segment_id=segment_id_value,
        boundary_type=str(boundary_type),
        parent_region_prim_path=find_parent_public_space_prim_path(prim) or "",
    )
    stats.public_space_boundary_segments.append(segment)


def record_public_space_asset_has_set(prim, info: PrimNameInfo, stats: SceneStats):
    from .scene_public_space import find_parent_public_space_prim_path, read_simworld_attribute

    try:
        mesh = extract_mesh_world_vertices_from_prim_or_child(prim)
        vertices = mesh["world_vertices"]
    except Exception as exc:
        stats.public_space_parse_warnings.append(
            f"{prim.GetPath()}: cannot read asset-has-set mesh ({exc})"
        )
        return

    asset_type = read_simworld_attribute(prim, "asset_has_set_type")
    if not asset_type:
        stats.public_space_parse_warnings.append(
            f"{prim.GetPath()}: missing simworld:asset_has_set_type"
        )
        return

    asset_id = read_simworld_attribute(prim, "asset_has_set_id", info.index)
    try:
        asset_id_value = int(asset_id)
    except (TypeError, ValueError):
        asset_id_value = 0

    item = PlaceholderAssetHasSet(
        vertices=vertices,
        prim_path=str(prim.GetPath()),
        raw_name=info.raw_name,
        index=info.index,
        asset_has_set_id=asset_id_value,
        asset_has_set_type=str(asset_type),
        parent_region_prim_path=find_parent_public_space_prim_path(prim) or "",
    )
    stats.public_space_asset_has_sets.append(item)


PROCESSING_RULES = [
    ProcessingRule(
        name="static construction buildings",
        mobility="static",
        domain="construction",
        category="building",
        actions=[
            apply_static_collision,
            # apply_semantic_label,
            # write_custom_metadata,
        ],
    ),
    ProcessingRule(
        name="static ground",
        mobility="static",
        domain="ground",
        actions=[
            apply_static_collision,
            # apply_semantic_label,
            # write_custom_metadata,
        ],
    ),
    ProcessingRule(
        name="static ground",
        mobility="static",
        domain="construction",
        actions=[
            apply_static_collision,
            # apply_semantic_label,
            # write_custom_metadata,
        ],
    ),
    ProcessingRule(
        name="placeholder spawn point",
        mobility="placeholder",
        domain="spot",
        category="spawn",
        actions=[
            set_spawn_point_from_prim,
        ],
    ),
    ProcessingRule(
        name="placeholder plaza area",
        mobility="placeholder",
        domain="area",
        category="plaza",
        actions=[
            process_placeholder_area,
        ],
    ),
    ProcessingRule(
        name="placeholder pedestrian spawn",
        mobility="placeholder",
        domain="pedestrian",
        category="spawn",
        actions=[record_pedestrian_spawn],
    ),
    ProcessingRule(
        name="placeholder pedestrian goal",
        mobility="placeholder",
        domain="pedestrian",
        category="goal",
        actions=[record_pedestrian_goal],
    ),
    ProcessingRule(
        name="placeholder pedestrian route",
        mobility="placeholder",
        domain="pedestrian",
        category="route",
        actions=[record_pedestrian_route],
    ),
    ProcessingRule(
        name="placeholder camera path",
        mobility="placeholder",
        domain="path",
        category="camera",
        actions=[record_camera_path],
    ),
    ProcessingRule(
        name="placeholder pedestrian zone",
        mobility="placeholder",
        domain="pedestrian",
        category="zone",
        actions=[record_pedestrian_zone],
    ),
    ProcessingRule(
        name="placeholder vehicle spawn",
        mobility="placeholder",
        domain="vehicle",
        category="spawn",
        actions=[record_vehicle_spawn],
    ),
    ProcessingRule(
        name="placeholder vehicle goal",
        mobility="placeholder",
        domain="vehicle",
        category="goal",
        actions=[record_vehicle_goal],
    ),
    ProcessingRule(
        name="placeholder vehicle route",
        mobility="placeholder",
        domain="vehicle",
        category="route",
        actions=[record_vehicle_route],
    ),
    ProcessingRule(
        name="placeholder vehicle lane",
        mobility="placeholder",
        domain="vehicle",
        category="lane",
        actions=[record_vehicle_lane],
    ),
    ProcessingRule(
        name="placeholder sidewalk area",
        mobility="placeholder",
        domain="area",
        category="sidewalk",
        actions=[record_sidewalk_area],
    ),
    ProcessingRule(
        name="placeholder crosswalk area",
        mobility="placeholder",
        domain="area",
        category="crosswalk",
        actions=[record_crosswalk_area],
    ),
    ProcessingRule(
        name="placeholder public space region",
        mobility="placeholder",
        domain="area",
        category="publicspace",
        actions=[record_public_space_region],
    ),
    ProcessingRule(
        name="placeholder public space boundary segment",
        mobility="placeholder",
        domain="segment",
        category="edge",
        actions=[record_public_space_boundary_segment],
    ),
    ProcessingRule(
        name="placeholder public space asset has set",
        mobility="placeholder",
        domain="assetset",
        category="line",
        actions=[record_public_space_asset_has_set],
    ),
]


def process_stage_by_naming_rules(
    stage,
    stats: SceneStats | None = None,
    rules: Sequence[ProcessingRule] | None = None,
    verbose: bool = False,
    print_summary: bool = True,
):
    if stats is None:
        stats = SceneStats()
    if rules is None:
        rules = PROCESSING_RULES

    for prim in stage.Traverse():
        stats.visited += 1

        name = prim.GetName()
        info = parse_prim_name(name)

        if verbose:
            print(f"[SCENE] {prim.GetPath()} | name={name} | info={info}")

        if info is None:
            stats.invalid_name += 1
            continue

        if info.mobility == "placeholder":
            record_placeholder_prim(stats, prim)

        matched_any = False

        for rule in rules:
            if not rule_matches(rule, info, prim):
                continue

            matched_any = True
            stats.record_match(rule.name)

            for action in rule.actions:
                action(prim, info, stats)

        if not matched_any:
            stats.unmatched_named += 1
            print(f"[WARN] Named prim matched pattern but no rule: {prim.GetPath()}")

    from .scene_public_space import attach_orphan_segments_to_regions

    attach_orphan_segments_to_regions(stats)

    if print_summary:
        print_stage_processing_stats(stats)

    return stats


def print_stage_processing_stats(stats: SceneStats):
    print("\n========== Stage Processing Stats ==========")
    print(f"Visited prims:        {stats.visited}")
    print(f"Matched rules:        {stats.matched}")
    print(f"Invalid name format:  {stats.invalid_name}")
    print(f"Unmatched named prim: {stats.unmatched_named}")
    print(f"Spawn points:         {len(stats.spawn_points)}")

    dynamic_counts = {
        "Pedestrian spawns": len(stats.pedestrian_spawn_points),
        "Pedestrian goals": len(stats.pedestrian_goal_points),
        "Pedestrian routes": len(stats.pedestrian_routes),
        "Pedestrian zones": len(stats.pedestrian_zones),
        "Camera paths": len(stats.camera_paths),
        "Vehicle spawns": len(stats.vehicle_spawn_points),
        "Vehicle goals": len(stats.vehicle_goal_points),
        "Vehicle routes": len(stats.vehicle_routes),
        "Vehicle lanes": len(stats.vehicle_lanes),
        "Sidewalk areas": len(stats.sidewalk_areas),
        "Crosswalk areas": len(stats.crosswalk_areas),
    }
    if any(dynamic_counts.values()) or stats.skipped_dynamic_placeholders:
        print("\nDynamic placeholders:")
        for label, count in dynamic_counts.items():
            if count:
                print(f"  {label}: {count}")
        if stats.skipped_dynamic_placeholders:
            print(f"  Skipped dynamic placeholders: {len(stats.skipped_dynamic_placeholders)}")

    if stats.public_space_regions:
        print(f"\nPublic-space regions: {len(stats.public_space_regions)}")
        for region in stats.public_space_regions:
            print(
                f"  {region.prim_path} type={region.public_space_type} "
                f"segments={len(region.segments)} "
                f"asset_has_set={len(region.asset_has_sets)}"
            )
    if stats.public_space_parse_warnings:
        print(f"\nPublic-space parse warnings: {len(stats.public_space_parse_warnings)}")
        for warning in stats.public_space_parse_warnings:
            print(f"  [WARN] {warning}")

    print("\nProcessed by rule:")
    for rule_name, count in stats.processed.items():
        print(f"  {rule_name}: {count}")

    print("===========================================\n")
