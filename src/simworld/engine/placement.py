from dataclasses import dataclass
import math
import random
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Sequence

Vec2 = Tuple[float, float]
Vec3 = Tuple[float, float, float]
Polygon2D = List[Vec2]
Polygon3D = List[Vec3]


# ============================================================
# 3D vector utils
# ============================================================


def add3(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub3(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul3(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def dot3(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross3(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def length3(a: Vec3) -> float:
    return math.sqrt(dot3(a, a))


def normalize3(a: Vec3) -> Vec3:
    l = length3(a)
    if l < 1e-8:
        raise ValueError("Cannot normalize near-zero Vec3.")
    return (a[0] / l, a[1] / l, a[2] / l)


def project_vec_on_plane(v: Vec3, normal: Vec3) -> Vec3:
    """
    Remove normal component from v.
    """
    return sub3(v, mul3(normal, dot3(v, normal)))


def centroid3(points: List[Vec3]) -> Vec3:
    n = len(points)
    return (
        sum(p[0] for p in points) / n,
        sum(p[1] for p in points) / n,
        sum(p[2] for p in points) / n,
    )


def estimate_normal_from_unordered_points(points: List[Vec3]) -> Vec3:
    """
    从乱序点中估计一个平面法线。
    注意：这个法线方向本身是任意的。
    如果需要固定朝上，需要额外传入 reference_normal。
    """
    n = len(points)

    if n < 3:
        raise ValueError("At least 3 points are required.")

    # 找一组三点不共线
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                a = points[i]
                b = points[j]
                c = points[k]

                ab = sub3(b, a)
                ac = sub3(c, a)

                normal = cross3(ab, ac)

                if length3(normal) > 1e-8:
                    return normalize3(normal)

    raise ValueError("All points are collinear. Cannot estimate polygon normal.")


def sort_coplanar_points_3d(
    points: List[Vec3],
    clockwise: bool = False,
    reference_normal: Vec3 | None = None,
) -> Polygon3D:
    """
    对共面凸多边形顶点进行排序。

    Parameters:
        points:
            乱序 3D 顶点。

        clockwise:
            是否输出顺时针序列。
            默认 False，输出逆时针序列。

        reference_normal:
            可选参考法线。
            如果传入，则排序结果的法线会尽量与 reference_normal 同向。
            如果不传入，法线方向由估计结果决定，不具有全局稳定性。

    Returns:
        排序后的 3D 顶点序列。
    """

    if len(points) < 3:
        raise ValueError("At least 3 points are required.")

    center = centroid3(points)

    normal = estimate_normal_from_unordered_points(points)

    # 如果提供了参考法线，则让估计法线与参考法线同向
    if reference_normal is not None:
        ref = normalize3(reference_normal)
        if dot3(normal, ref) < 0:
            normal = mul3(normal, -1.0)

    # 构建局部坐标系
    # 选择一个远离中心的点作为 u 方向
    u_axis = None
    max_dist = -1.0

    for p in points:
        v = sub3(p, center)
        d = length3(v)
        if d > max_dist:
            max_dist = d
            u_axis = v

    if u_axis is None or max_dist < 1e-8:
        raise ValueError("Degenerate point set.")

    u_axis = normalize3(u_axis)

    # v = normal x u
    # 满足 u x v = normal
    v_axis = normalize3(cross3(normal, u_axis))

    def angle_of_point(p: Vec3) -> float:
        d = sub3(p, center)
        x = dot3(d, u_axis)
        y = dot3(d, v_axis)
        return math.atan2(y, x)

    sorted_points = sorted(points, key=angle_of_point)

    # sorted_points 默认是基于 normal 的逆时针
    if clockwise:
        sorted_points.reverse()

    return sorted_points


# ============================================================
# 2D vector utils
# ============================================================


def add2(a: Vec2, b: Vec2) -> Vec2:
    return (a[0] + b[0], a[1] + b[1])


def sub2(a: Vec2, b: Vec2) -> Vec2:
    return (a[0] - b[0], a[1] - b[1])


def mul2(a: Vec2, s: float) -> Vec2:
    return (a[0] * s, a[1] * s)


def dot2(a: Vec2, b: Vec2) -> float:
    return a[0] * b[0] + a[1] * b[1]


def cross2(a: Vec2, b: Vec2) -> float:
    return a[0] * b[1] - a[1] * b[0]


def length2(a: Vec2) -> float:
    return math.sqrt(dot2(a, a))


def normalize2(a: Vec2) -> Vec2:
    l = length2(a)
    if l < 1e-8:
        return (1.0, 0.0)
    return (a[0] / l, a[1] / l)


def perp2(a: Vec2) -> Vec2:
    return (-a[1], a[0])


# ============================================================
# Plane frame
# ============================================================


@dataclass
class PlaneFrame:
    origin: Vec3
    u_axis: Vec3
    v_axis: Vec3
    normal: Vec3


def compute_polygon_normal(vertices: Polygon3D) -> Vec3:
    """
    Compute oriented polygon normal using Newell's method.

    The normal direction is determined by input vertex order.
    Reverse the vertices, and the normal will be reversed.
    """
    nx, ny, nz = 0.0, 0.0, 0.0
    n = len(vertices)

    for i in range(n):
        x0, y0, z0 = vertices[i]
        x1, y1, z1 = vertices[(i + 1) % n]

        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)

    normal = (nx, ny, nz)

    if length3(normal) < 1e-8:
        raise ValueError("Degenerate polygon: cannot compute normal.")

    return normalize3(normal)


def compute_plane_frame(vertices: Polygon3D) -> PlaneFrame:
    """
    Build local 2D coordinate system on polygon plane.

    u_axis:
        chosen from the longest polygon edge projected onto the plane.

    v_axis:
        computed as normal x u_axis.

    This gives:
        u_axis x v_axis = normal
    """
    normal = compute_polygon_normal(vertices)

    best_len = -1.0
    best_u = None

    n = len(vertices)

    for i in range(n):
        e = sub3(vertices[(i + 1) % n], vertices[i])
        e = project_vec_on_plane(e, normal)
        l = length3(e)

        if l > best_len:
            best_len = l
            best_u = e

    if best_u is None or best_len < 1e-8:
        raise ValueError("Degenerate polygon: cannot build plane frame.")

    u_axis = normalize3(best_u)

    # Important:
    # v = normal x u, so u x v = normal.
    v_axis = normalize3(cross3(normal, u_axis))

    origin = vertices[0]

    return PlaneFrame(
        origin=origin,
        u_axis=u_axis,
        v_axis=v_axis,
        normal=normal,
    )


def world_to_plane_2d(p: Vec3, frame: PlaneFrame) -> Vec2:
    d = sub3(p, frame.origin)
    return (
        dot3(d, frame.u_axis),
        dot3(d, frame.v_axis),
    )


def plane_2d_to_world(p: Vec2, frame: PlaneFrame) -> Vec3:
    return add3(
        frame.origin,
        add3(
            mul3(frame.u_axis, p[0]),
            mul3(frame.v_axis, p[1]),
        ),
    )


# ============================================================
# 2D polygon utils
# ============================================================


def signed_area_2d(poly: Polygon2D) -> float:
    s = 0.0
    n = len(poly)

    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        s += x1 * y2 - x2 * y1

    return 0.5 * s


def area_2d(poly: Polygon2D) -> float:
    return abs(signed_area_2d(poly))


def edge_signed_distance_ccw(poly: Polygon2D, p: Vec2, edge_index: int) -> float:
    """
    For a CCW convex polygon, positive distance means inside this edge half-plane.
    """
    a = poly[edge_index]
    b = poly[(edge_index + 1) % len(poly)]

    e = sub2(b, a)

    return cross2(e, sub2(p, a)) / max(length2(e), 1e-8)


def point_inside_convex_with_margin(
    poly: Polygon2D, p: Vec2, margin: float = 0.0
) -> bool:
    for i in range(len(poly)):
        if edge_signed_distance_ccw(poly, p, i) < margin:
            return False

    return True


def polygon_inside_convex_with_margin(
    container: Polygon2D, inner: Polygon2D, margin: float = 0.0
) -> bool:
    return all(point_inside_convex_with_margin(container, p, margin) for p in inner)


def polygon_projection_range(poly: Polygon2D, axis: Vec2) -> Tuple[float, float]:
    values = [dot2(p, axis) for p in poly]
    return min(values), max(values)


def longest_edge_direction_2d(poly: Polygon2D) -> Vec2:
    best_len = -1.0
    best_dir = (1.0, 0.0)

    n = len(poly)

    for i in range(n):
        e = sub2(poly[(i + 1) % n], poly[i])
        l = length2(e)

        if l > best_len:
            best_len = l
            best_dir = normalize2(e)

    return best_dir


# ============================================================
# Footprint geometry
# ============================================================


def oriented_rectangle_2d(center: Vec2, size: Vec2, angle: float) -> Polygon2D:
    """
    size = (width, depth)
    angle in local 2D plane, radians.
    """
    w, d = size

    ux = (math.cos(angle), math.sin(angle))
    uy = (-math.sin(angle), math.cos(angle))

    hw = w * 0.5
    hd = d * 0.5

    return [
        add2(center, add2(mul2(ux, -hw), mul2(uy, -hd))),
        add2(center, add2(mul2(ux, hw), mul2(uy, -hd))),
        add2(center, add2(mul2(ux, hw), mul2(uy, hd))),
        add2(center, add2(mul2(ux, -hw), mul2(uy, hd))),
    ]


def project_polygon_2d(poly: Polygon2D, axis: Vec2) -> Tuple[float, float]:
    values = [dot2(p, axis) for p in poly]
    return min(values), max(values)


def polygons_overlap_sat_2d(a: Polygon2D, b: Polygon2D) -> bool:
    """
    SAT overlap test for convex polygons.
    """
    for poly in (a, b):
        n = len(poly)

        for i in range(n):
            edge = sub2(poly[(i + 1) % n], poly[i])
            axis = normalize2(perp2(edge))

            min_a, max_a = project_polygon_2d(a, axis)
            min_b, max_b = project_polygon_2d(b, axis)

            if max_a < min_b or max_b < min_a:
                return False

    return True


# ============================================================
# Shape and footprint data
# ============================================================


@dataclass
class ShapeInfo2D:
    area: float
    main_dir: Vec2
    side_dir: Vec2
    main_min: float
    main_max: float
    side_min: float
    side_max: float
    length: float
    width: float
    aspect: float


@dataclass
class Footprint2D:
    kind: str
    center: Vec2
    size: Vec2
    rotation: float
    polygon: Polygon2D


@dataclass
class Footprint3D:
    kind: str
    center: Vec3
    size: Vec2
    rotation_in_plane: float
    polygon: Polygon3D
    normal: Vec3


@dataclass
class AssetSpec:
    name: str
    usd_path: Path
    category: str

    # 资产自身推荐占地尺寸
    nominal_size_xy: Vec2 = (1.0, 1.0)

    min_scale: float = 0.5
    max_scale: float = 2.0

    allow_rotation: bool = True


@dataclass
class FootprintFrame:
    center: np.ndarray
    normal: np.ndarray
    tangent_x: np.ndarray
    tangent_y: np.ndarray
    size_xy: Vec2


@dataclass
class GenerationResult3D:
    normal: Vec3
    frame: PlaneFrame
    footprints: List[Footprint3D]


# ============================================================
# Shape analysis
# ============================================================


def analyze_shape_2d(poly: Polygon2D) -> ShapeInfo2D:
    main_dir = longest_edge_direction_2d(poly)
    side_dir = perp2(main_dir)

    main_min, main_max = polygon_projection_range(poly, main_dir)
    side_min, side_max = polygon_projection_range(poly, side_dir)

    main_len = max(main_max - main_min, 1e-6)
    side_len = max(side_max - side_min, 1e-6)

    if side_len > main_len:
        main_dir, side_dir = side_dir, main_dir

        main_min, main_max = polygon_projection_range(poly, main_dir)
        side_min, side_max = polygon_projection_range(poly, side_dir)

        main_len = max(main_max - main_min, 1e-6)
        side_len = max(side_max - side_min, 1e-6)

    aspect = main_len / max(side_len, 1e-6)

    return ShapeInfo2D(
        area=area_2d(poly),
        main_dir=main_dir,
        side_dir=side_dir,
        main_min=main_min,
        main_max=main_max,
        side_min=side_min,
        side_max=side_max,
        length=main_len,
        width=side_len,
        aspect=aspect,
    )


def uv_to_local_2d(info: ShapeInfo2D, u: float, v: float) -> Vec2:
    """
    Convert normalized template coordinate to local 2D plane coordinate.
    """
    s = info.main_min + u * info.length
    t = info.side_min + v * info.width

    return add2(
        mul2(info.main_dir, s),
        mul2(info.side_dir, t),
    )


def main_angle_2d(info: ShapeInfo2D) -> float:
    return math.atan2(info.main_dir[1], info.main_dir[0])


# ============================================================
# Template logic
# ============================================================


def choose_layout(info: ShapeInfo2D) -> str:
    if info.area < 80.0:
        return "pocket"

    if info.aspect > 3.0:
        return "linear"

    if info.aspect < 1.5:
        return "ring"

    return "mixed"


def sample_rule(layout: str, rng: random.Random):
    """
    Return:
        kind, min_size, max_size, zone, weight
    """
    if layout == "linear":
        rules = [
            ("bench", (1.6, 0.5), (2.8, 0.8), "side_band", 0.45),
            ("planter", (1.2, 1.2), (2.4, 2.4), "side_band", 0.35),
            ("tree_pit", (1.5, 1.5), (2.2, 2.2), "side_band", 0.20),
        ]

    elif layout == "ring":
        rules = [
            ("bench_group", (2.0, 0.8), (4.0, 1.4), "edge_ring", 0.35),
            ("planter", (1.5, 1.5), (3.0, 3.0), "edge_ring", 0.35),
            ("sculpture", (1.2, 1.2), (2.5, 2.5), "edge_ring", 0.30),
        ]

    elif layout == "mixed":
        rules = [
            ("bench_group", (2.0, 0.8), (4.0, 1.5), "cluster", 0.35),
            ("planter", (1.5, 1.0), (3.5, 2.5), "cluster", 0.40),
            ("kiosk", (2.5, 2.0), (4.0, 3.0), "cluster", 0.25),
        ]

    else:
        rules = [
            ("bench", (1.5, 0.5), (2.5, 0.8), "edge_ring", 0.55),
            ("planter", (1.0, 1.0), (2.0, 2.0), "edge_ring", 0.45),
        ]

    r = rng.random()
    acc = 0.0

    for rule in rules:
        acc += rule[4]
        if r <= acc:
            return rule

    return rules[-1]


def random_size(min_size: Vec2, max_size: Vec2, rng: random.Random) -> Vec2:
    return (
        rng.uniform(min_size[0], max_size[0]),
        rng.uniform(min_size[1], max_size[1]),
    )


def sample_uv_by_zone(zone: str, rng: random.Random):
    """
    Return:
        u, v, orientation_hint
    """
    if zone == "side_band":
        u = rng.uniform(0.08, 0.92)

        if rng.random() < 0.5:
            v = rng.uniform(0.12, 0.30)
        else:
            v = rng.uniform(0.70, 0.88)

        return u, v, "main"

    if zone == "edge_ring":
        side = rng.choice(["bottom", "top", "left", "right"])

        if side == "bottom":
            return rng.uniform(0.12, 0.88), rng.uniform(0.10, 0.24), "main"

        if side == "top":
            return rng.uniform(0.12, 0.88), rng.uniform(0.76, 0.90), "main"

        if side == "left":
            return rng.uniform(0.10, 0.24), rng.uniform(0.12, 0.88), "side"

        return rng.uniform(0.76, 0.90), rng.uniform(0.12, 0.88), "side"

    # cluster
    cx, cy = rng.choice(
        [
            (0.32, 0.35),
            (0.68, 0.65),
        ]
    )

    u = max(0.10, min(0.90, rng.gauss(cx, 0.12)))
    v = max(0.10, min(0.90, rng.gauss(cy, 0.12)))

    return u, v, "main"


def center_distance_ok(
    candidate: Footprint2D, placed: List[Footprint2D], min_gap: float
) -> bool:
    c1 = candidate.center
    r1 = 0.5 * math.sqrt(candidate.size[0] ** 2 + candidate.size[1] ** 2)

    for fp in placed:
        c2 = fp.center
        r2 = 0.5 * math.sqrt(fp.size[0] ** 2 + fp.size[1] ** 2)

        if length2(sub2(c1, c2)) < r1 + r2 + min_gap:
            return False

    return True


# ============================================================
# Main 2D generator
# ============================================================


def generate_footprints_on_2d_polygon(
    polygon_2d: Polygon2D,
    density: float = 0.25,
    seed: int = 0,
    boundary_margin: float = 0.8,
    min_gap: float = 0.6,
    max_attempts: int = 3000,
) -> List[Footprint2D]:

    if len(polygon_2d) != 4:
        raise ValueError("This minimal version expects exactly 4 vertices.")

    # In theory, projected polygon should already be CCW
    # because frame normal comes from the vertex order.
    # This check is kept for safety.
    if signed_area_2d(polygon_2d) < 0:
        polygon_2d = list(reversed(polygon_2d))

    info = analyze_shape_2d(polygon_2d)
    layout = choose_layout(info)

    density = max(0.02, min(density, 0.55))
    target_area = info.area * density

    rng = random.Random(seed)

    placed: List[Footprint2D] = []
    occupied_area = 0.0

    attempts = 0

    while occupied_area < target_area and attempts < max_attempts:
        attempts += 1

        kind, min_size, max_size, zone, _weight = sample_rule(layout, rng)

        size = random_size(min_size, max_size, rng)

        u, v, orient_hint = sample_uv_by_zone(zone, rng)
        center = uv_to_local_2d(info, u, v)

        base_angle = main_angle_2d(info)

        if orient_hint == "side":
            base_angle += math.pi * 0.5

        angle_jitter = math.radians(10.0)
        rotation = base_angle + rng.uniform(-angle_jitter, angle_jitter)

        rect = oriented_rectangle_2d(center, size, rotation)

        if not polygon_inside_convex_with_margin(polygon_2d, rect, boundary_margin):
            continue

        candidate = Footprint2D(
            kind=kind,
            center=center,
            size=size,
            rotation=rotation,
            polygon=rect,
        )

        if not center_distance_ok(candidate, placed, min_gap):
            continue

        has_overlap = any(
            polygons_overlap_sat_2d(candidate.polygon, fp.polygon) for fp in placed
        )

        if has_overlap:
            continue

        placed.append(candidate)
        occupied_area += size[0] * size[1]

    return placed


# ============================================================
# Main 3D generator
# ============================================================


def generate_public_space_footprints_3d(
    vertices_3d: Polygon3D,
    density: float = 0.25,
    seed: int = 0,
    boundary_margin: float = 0.8,
    min_gap: float = 0.6,
    max_attempts: int = 3000,
) -> GenerationResult3D:
    """
    Generate public-space footprints on a 3D coplanar convex quadrilateral.

    Parameters:
        vertices_3d:
            Four 3D vertices.
            The vertices must be ordered along polygon boundary.
            Clockwise / counter-clockwise both work, but they produce opposite normals.

        density:
            Approximate target occupied area ratio.

        boundary_margin:
            Minimum distance from polygon boundary, measured in plane units.

        min_gap:
            Approximate minimum gap between generated footprints.

    Returns:
        GenerationResult3D:
            normal:
                Polygon normal decided by input vertex order.

            frame:
                Local plane coordinate frame.

            footprints:
                Generated 3D footprints.
    """

    if len(vertices_3d) != 4:
        raise ValueError("This minimal version expects exactly 4 vertices.")

    vertices_3d = sort_coplanar_points_3d(vertices_3d, clockwise=False)

    frame = compute_plane_frame(vertices_3d)

    polygon_2d = [world_to_plane_2d(p, frame) for p in vertices_3d]

    footprints_2d = generate_footprints_on_2d_polygon(
        polygon_2d,
        density=density,
        seed=seed,
        boundary_margin=boundary_margin,
        min_gap=min_gap,
        max_attempts=max_attempts,
    )

    footprints_3d: List[Footprint3D] = []

    for fp in footprints_2d:
        center_3d = plane_2d_to_world(fp.center, frame)

        polygon_3d = [plane_2d_to_world(p, frame) for p in fp.polygon]

        footprints_3d.append(
            Footprint3D(
                kind=fp.kind,
                center=center_3d,
                size=fp.size,
                rotation_in_plane=fp.rotation,
                polygon=polygon_3d,
                normal=frame.normal,
            )
        )

    return GenerationResult3D(
        normal=frame.normal,
        frame=frame,
        footprints=footprints_3d,
    )


# ============================================================
# Debug print
# ============================================================


def print_footprints_3d(result: GenerationResult3D):
    print("Polygon normal:", result.normal)
    print("u_axis:", result.frame.u_axis)
    print("v_axis:", result.frame.v_axis)
    print()

    for i, fp in enumerate(result.footprints):
        cx, cy, cz = fp.center

        print(
            f"{i:02d} | {fp.kind:12s} "
            f"center=({cx:.2f}, {cy:.2f}, {cz:.2f}) "
            f"size=({fp.size[0]:.2f}, {fp.size[1]:.2f}) "
            f"rot_in_plane={math.degrees(fp.rotation_in_plane):.1f} deg"
        )


# ============================================================
# Analyzer
# ============================================================


class FootprintAnalyzer:
    @staticmethod
    def analyze(fp: Footprint3D) -> FootprintFrame:
        center = np.array(fp.center, dtype=np.float64)
        normal = FootprintAnalyzer._normalize(np.array(fp.normal, dtype=np.float64))

        # 根据 normal 构建一个稳定的平面参考轴
        ref_x = FootprintAnalyzer._make_reference_tangent(normal)

        # 在 footprint 平面内旋转
        tangent_x = FootprintAnalyzer._rotate_around_axis(
            ref_x,
            normal,
            fp.rotation_in_plane,
        )
        tangent_x = FootprintAnalyzer._normalize(tangent_x)

        # 构建局部 Y 轴
        tangent_y = np.cross(normal, tangent_x)
        tangent_y = FootprintAnalyzer._normalize(tangent_y)

        return FootprintFrame(
            center=center,
            normal=normal,
            tangent_x=tangent_x,
            tangent_y=tangent_y,
            size_xy=fp.size,
        )

    @staticmethod
    def _make_reference_tangent(normal: np.ndarray) -> np.ndarray:
        """
        给定法线，构建平面内一个稳定的参考 X 方向。
        默认使用 world X 投影到平面。
        如果 world X 与 normal 太接近，则改用 world Y。
        """
        world_x = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        world_y = np.array([0.0, 1.0, 0.0], dtype=np.float64)

        ref = world_x - normal * np.dot(world_x, normal)

        if np.linalg.norm(ref) < 1e-6:
            ref = world_y - normal * np.dot(world_y, normal)

        return FootprintAnalyzer._normalize(ref)

    @staticmethod
    def _rotate_around_axis(
        v: np.ndarray, axis: np.ndarray, angle: float
    ) -> np.ndarray:
        """
        Rodrigues rotation formula.
        angle 默认是 radians。
        """
        axis = FootprintAnalyzer._normalize(axis)

        return (
            v * math.cos(angle)
            + np.cross(axis, v) * math.sin(angle)
            + axis * np.dot(axis, v) * (1.0 - math.cos(angle))
        )

    @staticmethod
    def _normalize(v: np.ndarray) -> np.ndarray:
        l = np.linalg.norm(v)
        if l < 1e-8:
            raise ValueError("Cannot normalize zero vector.")
        return v / l


# Asset Matcher
class AssetMatcher:
    def __init__(self, library):
        self.library = library

    def choose_asset(
        self,
        fp: Footprint3D,
        frame: FootprintFrame,
        test_asset: Optional[AssetSpec] = None,
    ) -> AssetSpec:

        # 快速测试模式：强制使用单一资产
        if test_asset is not None:
            return test_asset

        # 根据 footprint.kind 匹配资产类别
        candidates = self.library.get_by_category(fp.kind)

        # 如果没有匹配类别，则退回到全部资产
        if not candidates:
            candidates = self.library.get_all_assets()

        if not candidates:
            raise RuntimeError("No asset available in AssetLibrary.")

        return random.choice(candidates)


class AssetLibrary:
    def __init__(self):
        self.assets: List[AssetSpec] = []
        self.assets_by_category: Dict[str, List[AssetSpec]] = {}

    def add_asset(self, asset: AssetSpec) -> None:
        self.assets.append(asset)

        if asset.category not in self.assets_by_category:
            self.assets_by_category[asset.category] = []

        self.assets_by_category[asset.category].append(asset)

    def get_all_assets(self) -> List[AssetSpec]:
        return self.assets

    def get_by_category(self, category: str) -> List[AssetSpec]:
        return self.assets_by_category.get(category, [])

    def scan_folder(
        self,
        root_dir: Path,
        recursive: bool = True,
    ) -> None:
        """
        假设资产目录结构为：

        root_dir/
        ├── bench/
        │   ├── bench_01.usd
        │   └── bench_02.usd
        ├── tree/
        │   └── tree_01.usd
        └── kiosk/
            └── kiosk_01.usd

        子文件夹名会被当作 category。
        """

        pattern = "**/*" if recursive else "*"

        for path in root_dir.glob(pattern):
            if not path.is_file():
                continue

            if path.suffix.lower() not in [".usd", ".usda", ".usdc"]:
                continue

            # 用父目录名作为类别
            category = path.parent.name

            asset = AssetSpec(
                name=path.stem,
                usd_path=path,
                category=category,
                nominal_size_xy=(1.0, 1.0),
            )

            self.add_asset(asset)

    def print_summary(self) -> None:
        print("AssetLibrary summary:")

        for category, assets in self.assets_by_category.items():
            print(f"  {category}: {len(assets)} assets")
            for asset in assets:
                print(f"    - {asset.name}: {asset.usd_path}")


# Placement Planner
@dataclass
class AssetImportPlan:
    asset: AssetSpec
    prim_path: str

    center: np.ndarray
    tangent_x: np.ndarray
    tangent_y: np.ndarray
    normal: np.ndarray

    scale_xyz: Tuple[float, float, float]


class AssetPlacementPlanner:
    def __init__(self, matcher: AssetMatcher):
        self.matcher = matcher

    def build_plan_for_footprints(
        self,
        footprints: Sequence[Footprint3D],
        root_prim: str = "/World/GeneratedAssets",
        test_asset: Optional[AssetSpec] = None,
    ) -> List[AssetImportPlan]:

        plans: List[AssetImportPlan] = []

        for i, fp in enumerate(footprints):
            frame = FootprintAnalyzer.analyze(fp)

            asset = self.matcher.choose_asset(
                fp=fp,
                frame=frame,
                test_asset=test_asset,
            )

            scale_xyz = self._compute_fit_scale(asset, frame)

            prim_path = f"{root_prim}/{fp.kind}_{i:04d}_{asset.name}"

            plan = AssetImportPlan(
                asset=asset,
                prim_path=prim_path,
                center=frame.center,
                tangent_x=frame.tangent_x,
                tangent_y=frame.tangent_y,
                normal=frame.normal,
                scale_xyz=scale_xyz,
            )

            plans.append(plan)

        return plans

    def _compute_fit_scale(
        self,
        asset: AssetSpec,
        frame: FootprintFrame,
        margin: float = 0.85,
    ) -> Tuple[float, float, float]:

        fp_w, fp_h = frame.size_xy
        # asset_w, asset_h = asset.nominal_size_xy
        asset_w = 1.0
        asset_h = 1.0

        if asset_w <= 1e-6 or asset_h <= 1e-6:
            return (1.0, 1.0, 1.0)

        sx = fp_w / asset_w * margin
        sy = fp_h / asset_h * margin

        # 推荐 uniform scale，避免公共空间资产被拉伸变形
        s = min(sx, sy)
        s = max(asset.min_scale, min(asset.max_scale, s))

        return (s, s, s)

# ============================================================
# Example
# ============================================================

if __name__ == "__main__":
    # Example 1:
    # A flat horizontal public space on XY plane.
    vertices = [
        (0.0, 0.0, 0.0),
        (30.0, 2.0, 0.0),
        (28.0, 14.0, 0.0),
        (2.0, 12.0, 0.0),
    ]

    result = generate_public_space_footprints_3d(
        vertices,
        density=0.28,
        seed=42,
        boundary_margin=0.8,
        min_gap=0.6,
    )

    print_footprints_3d(result)

    # Example 2:
    # Same kind of polygon, but tilted in 3D.
    tilted_vertices = [
        (0.0, 0.0, 0.0),
        (30.0, 2.0, 3.0),
        (28.0, 14.0, 5.0),
        (2.0, 12.0, 2.0),
    ]

    tilted_result = generate_public_space_footprints_3d(
        tilted_vertices,
        density=0.25,
        seed=7,
        boundary_margin=0.8,
        min_gap=0.6,
    )

    print()
    print("Tilted polygon result:")
    print_footprints_3d(tilted_result)
