from ..isaac_adaptor import isaac_context as iscctx

from dataclasses import dataclass, field
import re
from typing import Any, Callable, Optional, Sequence


@dataclass
class PlaceholderArea:
    vertices: list[list[float]] = field(default_factory=list)


@dataclass
class SceneStats:
    spawn_points: list[list[float]] = field(default_factory=list)
    placeholder_areas: list[PlaceholderArea] = field(default_factory=list)

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


@dataclass
class PrimNameInfo:
    raw_name: str
    mobility: str
    domain: str
    category: str
    index: str


NAME_PATTERN = re.compile(
    r"^(?P<mobility>[a-zA-Z]+)_"
    r"(?P<domain>[a-zA-Z]+)_"
    r"(?P<category>[a-zA-Z]+)_"
    r"(?P<index>[0-9a-zA-Z]+)$"
)


def parse_prim_name(name: str) -> Optional[PrimNameInfo]:
    match = NAME_PATTERN.match(name)

    if not match:
        return None

    return PrimNameInfo(
        raw_name=name,
        mobility=match.group("mobility"),
        domain=match.group("domain"),
        category=match.group("category"),
        index=match.group("index"),
    )


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

    print(f"[COLLISION] {prim.GetPath()} <- {info.raw_name}")


def process_placeholder_area(prim, info: PrimNameInfo, stats: SceneStats):
    res = extract_mesh_world_vertices(prim.GetChildren()[0])
    vertices = res["world_vertices"]
    stats.placeholder_areas.append(PlaceholderArea(vertices=vertices))


def set_spawn_point_from_prim(prim, info: PrimNameInfo, stats: SceneStats):
    pos = extract_prim_position(prim)
    pos[2] += 0.8
    stats.spawn_points.append(pos)
    # print(f"[SPAWN] {prim.GetPath()} <- {info.raw_name} | position = {pos}")


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

    print("\nProcessed by rule:")
    for rule_name, count in stats.processed.items():
        print(f"  {rule_name}: {count}")

    print("===========================================\n")
