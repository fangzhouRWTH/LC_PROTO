"""
Public space asset configuration generator.

Provides `public_space_asset_configuration(...)` which executes the
generation workflow described in `function definition.md`.

This module implements step 1 (set priority and walkable) fully.
Other steps are present as stubs (pass) so you can run and debug step 1
before implementing later steps.

Usage:
from ps_asset_config import public_space_asset_configuration

result = public_space_asset_configuration(
    public_space_type='block_entrance',
    public_space_geometry={...},
    public_space_segments=[...],
    ratio_dynamic_static=0.7,
    steps=[1]
)

The `steps` parameter controls which steps to run; provide a list of
integers (e.g. [1] or [1,2,3]) or None to run all steps.
"""
import random
from typing import List, Dict, Any, Optional, Set, Tuple


PRIORITY_MAPPING = {
    0: {'block_entrance', 'building_entrance_main'},
    2: {'street_boundary_primary'},
    4: {'yard_boundary', 'block_boundary_secondary'},
    6: {'block_boundary_primary', 'street_boundary_secondary'},
    8: {'building_other_type', 'block_boundary_other'},
    15: {'building_wall'},
}


def _local_asset_geometry(size: Tuple[float, float] = (0.5, 0.5)) -> Dict[str, Any]:
    half_x = size[0] * 0.5
    half_y = size[1] * 0.5
    return {
        'type': 'LineString3D',
        'coordinates': [
            [-half_x, -half_y, 0.0],
            [half_x, -half_y, 0.0],
            [half_x, half_y, 0.0],
            [-half_x, half_y, 0.0],
            [-half_x, -half_y, 0.0],
        ],
    }


EMBEDDED_ASSET_CANDIDATES = [
    {
        'asset_candidates_name': 'guangzhou_bus_stop',
        'asset_geometry_size': [0.5, 0.5],
        'geometry': _local_asset_geometry(),
        'applicable_types': ['city_street_roofless'],
        'preferred_zone': 'static',
        'probability': 0.20,
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'shared_bike_parking',
        'asset_geometry_size': [0.5, 0.5],
        'geometry': _local_asset_geometry(),
        'applicable_types': ['city_street_roofless'],
        'preferred_zone': 'static',
        'probability': 0.50,
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'tree_pool',
        'asset_geometry_size': [0.5, 0.5],
        'geometry': _local_asset_geometry((0.5, 0.5)),
        'applicable_types': ['city_street_roofless', 'city_yard_roofless'],
        'preferred_zone': 'static',
        'probability': 0.75,
        'probability_by_type': {
            'city_street_roofless': 0.50,
            'city_yard_roofless': 0.75,
        },
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'flower_box',
        'asset_geometry_size': [0.5, 0.5],
        'geometry': _local_asset_geometry((0.5, 0.5)),
        'applicable_types': ['city_street_roofless', 'city_yard_roofless'],
        'preferred_zone': 'static',
        'probability': 0.50,
        'probability_by_type': {
            'city_street_roofless': 0.50,
            'city_yard_roofless': 0.75,
        },
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'guard_rail',
        'asset_geometry_size': [5.0, 0.2],
        'geometry': _local_asset_geometry((5.0, 0.2)),
        'applicable_types': ['city_street_roofless', 'city_yard_roofless'],
        'preferred_zone': 'static',
        'probability': 1.00,
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'street_light',
        'asset_geometry_size': [0.2, 0.2],
        'geometry': _local_asset_geometry((0.2, 0.2)),
        'applicable_types': ['city_street_roofless', 'city_yard_roofless'],
        'preferred_zone': 'static',
        'probability': 1.00,
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'trash_bin',
        'asset_geometry_size': [0.5, 0.5],
        'geometry': _local_asset_geometry(),
        'applicable_types': ['city_street_roofless', 'city_yard_roofless'],
        'preferred_zone': 'static',
        'probability': 1.00,
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'fire_hydrant',
        'asset_geometry_size': [0.5, 0.5],
        'geometry': _local_asset_geometry(),
        'applicable_types': ['city_street_roofless', 'city_yard_roofless'],
        'preferred_zone': 'static',
        'probability': 1.00,
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'bollard',
        'asset_geometry_size': [0.5, 0.5],
        'geometry': _local_asset_geometry(),
        'applicable_types': ['block_entrance'],
        'preferred_zone': 'static',
        'probability': 1.00,
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'traffic_light_vehicle',
        'asset_geometry_size': [0.5, 0.5],
        'geometry': _local_asset_geometry(),
        'applicable_types': ['block_entrance'],
        'preferred_zone': 'static',
        'probability': 1.00,
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'traffic_light_pedestrian',
        'asset_geometry_size': [0.5, 0.5],
        'geometry': _local_asset_geometry(),
        'applicable_types': ['block_entrance'],
        'preferred_zone': 'static',
        'probability': 1.00,
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'metro_sign',
        'asset_geometry_size': [0.5, 0.5],
        'geometry': _local_asset_geometry(),
        'applicable_types': ['block_entrance'],
        'preferred_zone': 'static',
        'probability': 0.50,
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'vending_machine',
        'asset_geometry_size': [1.0, 1.0],
        'geometry': _local_asset_geometry((1.0, 1.0)),
        'applicable_types': ['building_entrance', 'city_yard_roof'],
        'preferred_zone': 'static',
        'probability': 0.50,
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'smart_locker',
        'asset_geometry_size': [0.5, 0.5],
        'geometry': _local_asset_geometry(),
        'applicable_types': ['building_entrance'],
        'preferred_zone': 'static',
        'probability': 1.00,
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'entrance_canopy',
        'asset_geometry_size': [0.5, 0.5],
        'geometry': _local_asset_geometry(),
        'applicable_types': ['building_entrance'],
        'preferred_zone': 'static',
        'probability': 1.00,
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'long_bench',
        'asset_geometry_size': [0.5, 0.5],
        'geometry': _local_asset_geometry(),
        'applicable_types': ['city_yard_roofless', 'city_yard_roof'],
        'preferred_zone': 'static',
        'probability': 0.25,
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'seat_group',
        'asset_geometry_size': [0.5, 0.5],
        'geometry': _local_asset_geometry(),
        'applicable_types': ['city_yard_roofless', 'city_yard_roof'],
        'preferred_zone': 'static',
        'probability': 0.75,
        'probability_by_type': {
            'city_yard_roofless': 0.75,
            'city_yard_roof': 0.25,
        },
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'food_cart',
        'asset_geometry_size': [0.5, 0.5],
        'geometry': _local_asset_geometry(),
        'applicable_types': ['city_yard_roofless', 'city_yard_roof'],
        'preferred_zone': 'dynamic',
        'probability': 0.50,
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'sculpture',
        'asset_geometry_size': [0.5, 0.5],
        'geometry': _local_asset_geometry(),
        'applicable_types': ['city_yard_roofless'],
        'preferred_zone': 'static',
        'probability': 1.00,
        'requires_central_static_zone': True,
        'max_count': 1,
    },
    {
        'asset_candidates_name': 'grass_patch',
        'asset_geometry_size': [0.5, 0.5],
        'geometry': _local_asset_geometry(),
        'applicable_types': ['city_yard_roofless'],
        'preferred_zone': 'static',
        'probability': 0.50,
        'max_count': 1,
    },
]


def _boundary_to_priority(boundary_type: str) -> int:
    for p, s in PRIORITY_MAPPING.items():
        if boundary_type in s:
            return p
    # default fallback
    return 10


def _is_walkable(boundary_type: str) -> bool:
    # building_wall is not walkable, others are walkable
    return boundary_type != 'building_wall'


def set_priority_and_walkable(public_space_segments: List[Dict[str, Any]]) -> None:
    """Append `priority` and `walkable` attributes to each segment dict.

    Modifies segments in-place.
    """
    for seg in public_space_segments:
        bt = seg.get('boundary_type', '')
        priority = _boundary_to_priority(bt)
        walkable = _is_walkable(bt)
        seg['priority'] = priority
        seg['walkable'] = walkable


def _point_to_xyz(point: List[float]) -> Tuple[float, float, float]:
    return (
        point[0],
        point[1],
        point[2] if len(point) > 2 else 0.0,
    )


def _vec_subtract(v1: Tuple[float, float, float], v2: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (v1[0] - v2[0], v1[1] - v2[1], v1[2] - v2[2])


def _vec_add(v1: Tuple[float, float, float], v2: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (v1[0] + v2[0], v1[1] + v2[1], v1[2] + v2[2])


def _vec_scale(v: Tuple[float, float, float], scale: float) -> Tuple[float, float, float]:
    return (v[0] * scale, v[1] * scale, v[2] * scale)


def _vec_dot(v1: Tuple[float, float, float], v2: Tuple[float, float, float]) -> float:
    return v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]


def _vec_length(v: Tuple[float, float, float]) -> float:
    return (v[0] ** 2 + v[1] ** 2 + v[2] ** 2) ** 0.5


def _segment_length(p0: Tuple[float, float, float], p1: Tuple[float, float, float]) -> float:
    return _vec_length(_vec_subtract(p1, p0))


def _point_to_segment_projection(
    point: Tuple[float, float, float],
    seg_p0: Tuple[float, float, float],
    seg_p1: Tuple[float, float, float],
) -> Tuple[Tuple[float, float, float], float]:
    seg_vec = _vec_subtract(seg_p1, seg_p0)
    point_vec = _vec_subtract(point, seg_p0)
    seg_len_sq = _vec_dot(seg_vec, seg_vec)
    if seg_len_sq == 0:
        return seg_p0, 0.0
    t = _vec_dot(point_vec, seg_vec) / seg_len_sq
    t = max(0.0, min(1.0, t))
    return _vec_add(seg_p0, _vec_scale(seg_vec, t)), t


def _polyline_length(coords: List[List[float]]) -> float:
    total = 0.0
    for start, end in zip(coords, coords[1:]):
        total += _segment_length(_point_to_xyz(start), _point_to_xyz(end))
    return total


def _line_string(coords: List[Tuple[float, float, float]]) -> Dict[str, Any]:
    return {
        'type': 'LineString3D',
        'coordinates': [[pt[0], pt[1], pt[2]] for pt in coords],
    }


def _polygon_string(coords: List[Tuple[float, float, float]]) -> Dict[str, Any]:
    closed = list(coords)
    if closed and closed[0] != closed[-1]:
        closed.append(closed[0])
    return {
        'type': 'LineString3D',
        'coordinates': [[pt[0], pt[1], pt[2]] for pt in closed],
    }


def _polygon_centroid(coords: List[List[float]]) -> Tuple[float, float, float]:
    if not coords:
        return (0.0, 0.0, 0.0)
    return (
        sum(c[0] for c in coords) / len(coords),
        sum(c[1] for c in coords) / len(coords),
        sum((c[2] if len(c) > 2 else 0.0) for c in coords) / len(coords),
    )


def _geometry_bbox(geometry: Dict[str, Any]) -> Tuple[float, float, float, float, float]:
    coords = geometry.get('coordinates', [])
    if not coords:
        return (0.0, 0.0, 0.0, 0.0, 0.0)
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    zs = [c[2] if len(c) > 2 else 0.0 for c in coords]
    return (min(xs), min(ys), max(xs), max(ys), sum(zs) / len(zs))


def _polygon_area_2d(coords: List[List[float]]) -> float:
    if len(coords) < 3:
        return 0.0
    area = 0.0
    points = coords[:-1] if coords[0] == coords[-1] else coords
    for current, nxt in zip(points, points[1:] + points[:1]):
        area += current[0] * nxt[1] - nxt[0] * current[1]
    return abs(area) * 0.5


def _bbox_from_coords(coords: List[List[float]]) -> Tuple[float, float, float, float]:
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return (min(xs), min(ys), max(xs), max(ys))


def _bbox_area(bbox: Tuple[float, float, float, float]) -> float:
    min_x, min_y, max_x, max_y = bbox
    return max(0.0, max_x - min_x) * max(0.0, max_y - min_y)


def _point_in_bbox(point: Tuple[float, float, float], bbox: Tuple[float, float, float, float], padding: float = 0.0) -> bool:
    min_x, min_y, max_x, max_y = bbox
    return (
        min_x - padding <= point[0] <= max_x + padding and
        min_y - padding <= point[1] <= max_y + padding
    )


def _segments_intersect_2d(
    p1: Tuple[float, float, float],
    p2: Tuple[float, float, float],
    q1: Tuple[float, float, float],
    q2: Tuple[float, float, float],
) -> bool:
    def orientation(a, b, c):
        value = (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1])
        if abs(value) < 1e-9:
            return 0
        return 1 if value > 0 else 2

    def on_segment(a, b, c):
        return (
            min(a[0], c[0]) - 1e-9 <= b[0] <= max(a[0], c[0]) + 1e-9 and
            min(a[1], c[1]) - 1e-9 <= b[1] <= max(a[1], c[1]) + 1e-9
        )

    o1 = orientation(p1, p2, q1)
    o2 = orientation(p1, p2, q2)
    o3 = orientation(q1, q2, p1)
    o4 = orientation(q1, q2, p2)

    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and on_segment(p1, q1, p2):
        return True
    if o2 == 0 and on_segment(p1, q2, p2):
        return True
    if o3 == 0 and on_segment(q1, p1, q2):
        return True
    if o4 == 0 and on_segment(q1, p2, q2):
        return True
    return False


def _segment_intersection_point_2d(
    p1: Tuple[float, float, float],
    p2: Tuple[float, float, float],
    q1: Tuple[float, float, float],
    q2: Tuple[float, float, float],
) -> Optional[Tuple[float, float]]:
    x1, y1 = p1[0], p1[1]
    x2, y2 = p2[0], p2[1]
    x3, y3 = q1[0], q1[1]
    x4, y4 = q2[0], q2[1]
    denominator = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denominator) < 1e-9:
        return None
    det1 = x1 * y2 - y1 * x2
    det2 = x3 * y4 - y3 * x4
    px = (det1 * (x3 - x4) - (x1 - x2) * det2) / denominator
    py = (det1 * (y3 - y4) - (y1 - y2) * det2) / denominator
    point = (px, py, 0.0)
    if _segments_intersect_2d(p1, p2, q1, q2):
        return (px, py)
    return None


def _segment_intersects_bbox(
    p0: Tuple[float, float, float],
    p1: Tuple[float, float, float],
    bbox: Tuple[float, float, float, float],
) -> bool:
    if _point_in_bbox(p0, bbox) or _point_in_bbox(p1, bbox):
        return True

    min_x, min_y, max_x, max_y = bbox
    corners = [
        (min_x, min_y, 0.0),
        (max_x, min_y, 0.0),
        (max_x, max_y, 0.0),
        (min_x, max_y, 0.0),
    ]
    bbox_edges = list(zip(corners, corners[1:] + corners[:1]))
    return any(_segments_intersect_2d(p0, p1, edge_start, edge_end) for edge_start, edge_end in bbox_edges)


def _polyline_intersects_any_bbox(coords: List[List[float]], bboxes: List[Tuple[float, float, float, float]]) -> bool:
    for start, end in zip(coords, coords[1:]):
        p0 = _point_to_xyz(start)
        p1 = _point_to_xyz(end)
        for bbox in bboxes:
            if _segment_intersects_bbox(p0, p1, bbox):
                return True
    return False


def _point_distance_2d(p0: Tuple[float, float, float], p1: Tuple[float, float, float]) -> float:
    return ((p0[0] - p1[0]) ** 2 + (p0[1] - p1[1]) ** 2) ** 0.5


def _normalize_2d(vec: Tuple[float, float, float]) -> Tuple[float, float, float]:
    length = (vec[0] ** 2 + vec[1] ** 2) ** 0.5
    if length <= 1e-9:
        return (1.0, 0.0, 0.0)
    return (vec[0] / length, vec[1] / length, 0.0)


def _nearest_point_on_polyline(
    point: Tuple[float, float, float],
    coords: List[List[float]],
) -> Tuple[Tuple[float, float, float], int]:
    best_point = _point_to_xyz(coords[0])
    best_index = 0
    best_distance = float('inf')

    for idx, (start, end) in enumerate(zip(coords, coords[1:])):
        projected, _ = _point_to_segment_projection(point, _point_to_xyz(start), _point_to_xyz(end))
        distance = _point_distance_2d(point, projected)
        if distance < best_distance:
            best_distance = distance
            best_point = projected
            best_index = idx
    return best_point, best_index


def _dedupe_path(points: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
    deduped: List[Tuple[float, float, float]] = []
    for point in points:
        if not deduped or _point_distance_2d(point, deduped[-1]) > 1e-6 or abs(point[2] - deduped[-1][2]) > 1e-6:
            deduped.append(point)
    return deduped


def _segment_meta_map(public_space_segments: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    meta = {}
    for index, seg in enumerate(public_space_segments):
        coords = seg.get('geometry', {}).get('coordinates', [])
        if len(coords) < 2:
            continue
        p0 = _point_to_xyz(coords[0])
        p1 = _point_to_xyz(coords[-1])
        meta[seg['segment_id']] = {
            'segment_id': seg['segment_id'],
            'index': index,
            'boundary_type': seg.get('boundary_type', ''),
            'priority': seg.get('priority', 10),
            'walkable': seg.get('walkable', True),
            'coords': coords,
            'p0': p0,
            'p1': p1,
            'length': _segment_length(p0, p1),
        }
    return meta


def _prepare_people_points(
    people_points: List[Dict[str, Any]],
    public_space_segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    segment_meta = _segment_meta_map(public_space_segments)
    prepared = []
    for index, point in enumerate(people_points):
        location = _point_to_xyz(point.get('location', [0.0, 0.0, 0.0]))
        segment_id = point.get('segment_id')
        meta = segment_meta.get(segment_id, {})
        if not meta.get('walkable', True):
            continue
        p0 = meta.get('p0')
        p1 = meta.get('p1')
        segment_axis = None
        perpendicular_axis = None
        if p0 and p1:
            if abs(p0[1] - p1[1]) <= 1e-9:
                segment_axis = 'horizontal'
                perpendicular_axis = 'vertical'
            elif abs(p0[0] - p1[0]) <= 1e-9:
                segment_axis = 'vertical'
                perpendicular_axis = 'horizontal'
        prepared.append({
            **point,
            'point_id': index,
            'xyz': location,
            'segment_index': meta.get('index', -1),
            'boundary_type': meta.get('boundary_type', ''),
            'segment_length': meta.get('length', 0.0),
            'segment_axis': segment_axis,
            'perpendicular_axis': perpendicular_axis,
        })
    return prepared


def _non_adjacent(point_a: Dict[str, Any], point_b: Dict[str, Any], segment_count: int) -> bool:
    idx_a = point_a.get('segment_index', -1)
    idx_b = point_b.get('segment_index', -1)
    if idx_a < 0 or idx_b < 0 or idx_a == idx_b:
        return False
    diff = abs(idx_a - idx_b)
    return diff not in {1, segment_count - 1}


def _adjacent(point_a: Dict[str, Any], point_b: Dict[str, Any], segment_count: int) -> bool:
    idx_a = point_a.get('segment_index', -1)
    idx_b = point_b.get('segment_index', -1)
    if idx_a < 0 or idx_b < 0 or idx_a == idx_b:
        return False
    diff = abs(idx_a - idx_b)
    return diff in {1, segment_count - 1}


def _bbox_side_for_point(
    point: Tuple[float, float, float],
    bbox: Tuple[float, float, float, float, float],
    tol: float = 1e-6,
) -> Optional[str]:
    x, y, _ = point
    min_x, min_y, max_x, max_y, _ = bbox
    distances = [
        ('left', abs(x - min_x)),
        ('right', abs(x - max_x)),
        ('bottom', abs(y - min_y)),
        ('top', abs(y - max_y)),
    ]
    side, distance = min(distances, key=lambda item: item[1])
    return side if distance <= tol else None


def _orthogonal_pair_relation(
    point_a: Dict[str, Any],
    point_b: Dict[str, Any],
    bbox: Tuple[float, float, float, float, float],
    segment_count: int,
) -> str:
    side_a = _bbox_side_for_point(point_a['xyz'], bbox)
    side_b = _bbox_side_for_point(point_b['xyz'], bbox)
    if side_a and side_b and side_a != side_b:
        opposite_pairs = {
            frozenset({'left', 'right'}),
            frozenset({'top', 'bottom'}),
        }
        return 'opposite' if frozenset({side_a, side_b}) in opposite_pairs else 'adjacent'
    if _adjacent(point_a, point_b, segment_count):
        return 'adjacent'
    if _non_adjacent(point_a, point_b, segment_count):
        return 'opposite'
    return 'same'


def _choose_main_pair(
    people_points: List[Dict[str, Any]],
    public_space_segments: List[Dict[str, Any]],
    public_space_type: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if len(people_points) < 2:
        return None, None

    segment_count = len(public_space_segments)
    segment_meta = _segment_meta_map(public_space_segments)
    sorted_points = sorted(
        people_points,
        key=lambda pt: (pt.get('priority', 10), pt.get('segment_index', 10**6), pt.get('point_id', 10**6)),
    )

    if public_space_type.startswith('city_street'):
        walkable_segments = [
            meta for meta in segment_meta.values()
            if meta.get('walkable', True)
        ]
        if walkable_segments:
            min_length = min(meta['length'] for meta in walkable_segments)
            short_segment_ids = {
                meta['segment_id']
                for meta in walkable_segments
                if abs(meta['length'] - min_length) < 1e-6
            }
            short_points = [pt for pt in sorted_points if pt.get('segment_id') in short_segment_ids]
            for point_a in short_points:
                for point_b in short_points:
                    if point_a['point_id'] >= point_b['point_id']:
                        continue
                    if _non_adjacent(point_a, point_b, segment_count):
                        return point_a, point_b

    best_pair = None
    best_key = None
    for point_a in sorted_points:
        for point_b in sorted_points:
            if point_a['point_id'] >= point_b['point_id']:
                continue
            if not _non_adjacent(point_a, point_b, segment_count):
                continue
            key = (
                max(point_a.get('priority', 10), point_b.get('priority', 10)),
                point_a.get('priority', 10) + point_b.get('priority', 10),
                -_point_distance_2d(point_a['xyz'], point_b['xyz']),
            )
            if best_key is None or key < best_key:
                best_key = key
                best_pair = (point_a, point_b)

    if best_pair:
        return best_pair
    return sorted_points[0], sorted_points[1]


def _choose_orthogonal_main_pair(
    people_points: List[Dict[str, Any]],
    public_space_segments: List[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if len(people_points) < 2:
        return None, None

    sorted_points = sorted(
        people_points,
        key=lambda pt: (pt.get('priority', 10), pt.get('segment_index', 10**6), pt.get('point_id', 10**6)),
    )

    best_pair = None
    best_key = None
    for point_a in sorted_points:
        for point_b in sorted_points:
            if point_a['point_id'] >= point_b['point_id']:
                continue
            key = (
                max(point_a.get('priority', 10), point_b.get('priority', 10)),
                point_a.get('priority', 10) + point_b.get('priority', 10),
                -_point_distance_2d(point_a['xyz'], point_b['xyz']),
            )
            if best_key is None or key < best_key:
                best_key = key
                best_pair = (point_a, point_b)

    if best_pair:
        return best_pair
    return sorted_points[0], sorted_points[1]


def _build_line_record(
    line_id: int,
    coords: List[Tuple[float, float, float]],
    role: str,
    pattern: str,
) -> Dict[str, Any]:
    clean_coords = _dedupe_path(coords)
    return {
        'line_id': line_id,
        'line_role': role,
        'pattern': pattern,
        'geometry': _line_string(clean_coords),
        'length': _polyline_length([[pt[0], pt[1], pt[2]] for pt in clean_coords]),
    }


def _choose_pattern(public_space_type: str, seed_value: str) -> str:
    if public_space_type == 'block_entrance':
        return 'cross'
    if public_space_type.startswith('city_street'):
        return 'fishbone'
    chooser = random.Random(seed_value)
    return chooser.choice(['fishbone', 'ring', 'orthogonal'])


def _build_cross_flow(geometry: Dict[str, Any]) -> Dict[str, Any]:
    min_x, min_y, max_x, max_y, avg_z = _geometry_bbox(geometry)
    center_x = (min_x + max_x) * 0.5
    center_y = (min_y + max_y) * 0.5
    horizontal = [(min_x, center_y, avg_z), (max_x, center_y, avg_z)]
    vertical = [(center_x, min_y, avg_z), (center_x, max_y, avg_z)]
    main_coords = horizontal if (max_x - min_x) >= (max_y - min_y) else vertical
    lines = [
        _build_line_record(1, main_coords, 'main', 'cross'),
        _build_line_record(2, vertical if main_coords == horizontal else horizontal, 'cross', 'cross'),
    ]
    return {
        'flow_pattern': 'cross',
        'walking_main_line': _line_string(main_coords),
        'walking_lines': lines,
    }


def _build_fishbone_flow(
    geometry: Dict[str, Any],
    people_points: List[Dict[str, Any]],
    public_space_segments: List[Dict[str, Any]],
    public_space_type: str,
) -> Dict[str, Any]:
    point_a, point_b = _choose_main_pair(people_points, public_space_segments, public_space_type)
    if not point_a or not point_b:
        return {
            'flow_pattern': 'fishbone',
            'walking_main_line': None,
            'walking_lines': [],
        }

    lines = [_build_line_record(1, [point_a['xyz'], point_b['xyz']], 'main', 'fishbone')]
    main_coords = lines[0]['geometry']['coordinates']

    line_id = 2
    for point in people_points:
        if point['point_id'] in {point_a['point_id'], point_b['point_id']}:
            continue
        projected, _ = _point_to_segment_projection(point['xyz'], point_a['xyz'], point_b['xyz'])
        if _point_distance_2d(point['xyz'], projected) <= 1e-6:
            continue
        lines.append(_build_line_record(line_id, [point['xyz'], projected], 'secondary', 'fishbone'))
        line_id += 1

    return {
        'flow_pattern': 'fishbone',
        'walking_main_line': _line_string([point_a['xyz'], point_b['xyz']]),
        'walking_lines': lines,
    }


def _build_ring_flow(
    geometry: Dict[str, Any],
    people_points: List[Dict[str, Any]],
    asset_has_set: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    min_x, min_y, max_x, max_y, avg_z = _geometry_bbox(geometry)
    obstacle_bboxes = []
    if asset_has_set:
        for asset in asset_has_set:
            if asset.get('asset_has_set_type') == 'arcade_column':
                continue
            coords = asset.get('geometry', {}).get('coordinates', [])
            if coords:
                obstacle_bboxes.append(_bbox_from_coords(coords))

    if obstacle_bboxes:
        ring_min_x = min(b[0] for b in obstacle_bboxes) - 1.0
        ring_min_y = min(b[1] for b in obstacle_bboxes) - 1.0
        ring_max_x = max(b[2] for b in obstacle_bboxes) + 1.0
        ring_max_y = max(b[3] for b in obstacle_bboxes) + 1.0
        ring_coords = [
            (ring_min_x, ring_min_y, avg_z),
            (ring_max_x, ring_min_y, avg_z),
            (ring_max_x, ring_max_y, avg_z),
            (ring_min_x, ring_max_y, avg_z),
            (ring_min_x, ring_min_y, avg_z),
        ]
    else:
        centroid = _polygon_centroid(geometry.get('coordinates', []))
        ring_coords = []
        for coord in geometry.get('coordinates', []):
            point = _point_to_xyz(coord)
            scaled = (
                centroid[0] + (point[0] - centroid[0]) * 0.4,
                centroid[1] + (point[1] - centroid[1]) * 0.4,
                avg_z,
            )
            ring_coords.append(scaled)
        if ring_coords and ring_coords[0] != ring_coords[-1]:
            ring_coords.append(ring_coords[0])

    lines = [_build_line_record(1, ring_coords, 'main', 'ring')]
    line_id = 2
    ring_polyline = lines[0]['geometry']['coordinates']
    for point in people_points:
        ring_point, _ = _nearest_point_on_polyline(point['xyz'], ring_polyline)
        if _point_distance_2d(point['xyz'], ring_point) <= 1e-6:
            continue
        lines.append(_build_line_record(line_id, [point['xyz'], ring_point], 'secondary', 'ring'))
        line_id += 1

    return {
        'flow_pattern': 'ring',
        'walking_main_line': _line_string(ring_coords),
        'walking_lines': lines,
    }


def _candidate_orthogonal_paths(
    start: Tuple[float, float, float],
    end: Tuple[float, float, float],
    bbox: Tuple[float, float, float, float, float],
) -> List[List[Tuple[float, float, float]]]:
    min_x, min_y, max_x, max_y, avg_z = bbox
    mid_x = (start[0] + end[0]) * 0.5
    mid_y = (start[1] + end[1]) * 0.5
    candidates = [
        [start, (end[0], start[1], avg_z), end],
        [start, (start[0], end[1], avg_z), end],
        [start, (mid_x, start[1], avg_z), (mid_x, end[1], avg_z), end],
        [start, (start[0], mid_y, avg_z), (end[0], mid_y, avg_z), end],
    ]
    filtered = []
    for candidate in candidates:
        if all(min_x - 1e-6 <= pt[0] <= max_x + 1e-6 and min_y - 1e-6 <= pt[1] <= max_y + 1e-6 for pt in candidate):
            filtered.append(_dedupe_path(candidate))
    return filtered or [[start, end]]


def _point_to_polyline_distance_2d(point: Tuple[float, float, float], coords: List[Tuple[float, float, float]]) -> float:
    if not coords:
        return float('inf')
    best = float('inf')
    for start, end in zip(coords, coords[1:]):
        projected, _ = _point_to_segment_projection(point, start, end)
        best = min(best, _point_distance_2d(point, projected))
    return best


def _nearest_bend_point(
    point: Tuple[float, float, float],
    bend_points: List[Tuple[float, float, float]],
) -> Optional[Tuple[float, float, float]]:
    if not bend_points:
        return None
    return min(bend_points, key=lambda bend: _point_distance_2d(point, bend))


def _orthogonal_path_to_point(
    start: Tuple[float, float, float],
    end: Tuple[float, float, float],
    centroid: Tuple[float, float, float],
) -> List[Tuple[float, float, float]]:
    if abs(start[0] - end[0]) <= 1e-9 or abs(start[1] - end[1]) <= 1e-9:
        return [start, end]

    options = [
        _dedupe_path([start, (end[0], start[1], end[2]), end]),
        _dedupe_path([start, (start[0], end[1], end[2]), end]),
    ]
    return min(
        options,
        key=lambda path: (
            _point_to_polyline_distance_2d(centroid, path),
            _polyline_length([[pt[0], pt[1], pt[2]] for pt in path]),
        ),
    )


def _perpendicular_connector_to_polyline(
    point: Dict[str, Any],
    polyline: List[Tuple[float, float, float]],
) -> Optional[List[Tuple[float, float, float]]]:
    point_xyz = point['xyz']
    perpendicular_axis = point.get('perpendicular_axis')
    best_projection = None
    best_distance = float('inf')

    for start, end in zip(polyline, polyline[1:]):
        if abs(start[1] - end[1]) <= 1e-9:
            if perpendicular_axis not in {None, 'vertical'}:
                continue
            min_x = min(start[0], end[0]) - 1e-9
            max_x = max(start[0], end[0]) + 1e-9
            if min_x <= point_xyz[0] <= max_x:
                projection = (point_xyz[0], start[1], start[2])
                distance = _point_distance_2d(point_xyz, projection)
                if distance < best_distance:
                    best_distance = distance
                    best_projection = projection
        elif abs(start[0] - end[0]) <= 1e-9:
            if perpendicular_axis not in {None, 'horizontal'}:
                continue
            min_y = min(start[1], end[1]) - 1e-9
            max_y = max(start[1], end[1]) + 1e-9
            if min_y <= point_xyz[1] <= max_y:
                projection = (start[0], point_xyz[1], start[2])
                distance = _point_distance_2d(point_xyz, projection)
                if distance < best_distance:
                    best_distance = distance
                    best_projection = projection

    if best_projection is None or _point_distance_2d(point_xyz, best_projection) <= 1e-9:
        return None
    return [point_xyz, best_projection]


def _best_perpendicular_connector_to_paths(
    point: Dict[str, Any],
    polylines: List[List[Tuple[float, float, float]]],
) -> Optional[List[Tuple[float, float, float]]]:
    best_connector = None
    best_distance = float('inf')

    for polyline in polylines:
        connector = _perpendicular_connector_to_polyline(point, polyline)
        if connector is None:
            continue
        distance = _point_distance_2d(connector[0], connector[-1])
        if distance < best_distance:
            best_distance = distance
            best_connector = connector

    return best_connector


def _orthogonal_mid_bend_paths(
    start: Tuple[float, float, float],
    end: Tuple[float, float, float],
    avg_z: float,
) -> List[List[Tuple[float, float, float]]]:
    if abs(start[0] - end[0]) <= 1e-9 or abs(start[1] - end[1]) <= 1e-9:
        return [[start, end]]

    mid_x = (start[0] + end[0]) * 0.5
    mid_y = (start[1] + end[1]) * 0.5
    return [
        _dedupe_path([start, (mid_x, start[1], avg_z), (mid_x, end[1], avg_z), end]),
        _dedupe_path([start, (start[0], mid_y, avg_z), (end[0], mid_y, avg_z), end]),
    ]


def _adjacent_orthogonal_paths(
    start: Tuple[float, float, float],
    end: Tuple[float, float, float],
    centroid: Tuple[float, float, float],
) -> List[List[Tuple[float, float, float]]]:
    corner_a = (start[0], end[1], centroid[2])
    corner_b = (end[0], start[1], centroid[2])
    candidate_a = _dedupe_path([start, corner_a, end])
    candidate_b = _dedupe_path([start, corner_b, end])
    return sorted(
        [candidate_a, candidate_b],
        key=lambda path: (
            _point_to_polyline_distance_2d(centroid, path),
            _polyline_length([[pt[0], pt[1], pt[2]] for pt in path]),
        ),
    )


def _build_orthogonal_flow(
    geometry: Dict[str, Any],
    people_points: List[Dict[str, Any]],
    public_space_segments: List[Dict[str, Any]],
    public_space_type: str,
) -> Dict[str, Any]:
    point_a, point_b = _choose_orthogonal_main_pair(people_points, public_space_segments)
    if not point_a or not point_b:
        return {
            'flow_pattern': 'orthogonal',
            'walking_main_line': None,
            'walking_lines': [],
        }

    bbox = _geometry_bbox(geometry)
    centroid = _polygon_centroid(geometry.get('coordinates', []))
    avg_z = bbox[4]
    segment_count = len(public_space_segments)
    pair_relation = _orthogonal_pair_relation(point_a, point_b, bbox, segment_count)
    is_adjacent_pair = pair_relation == 'adjacent'
    is_opposite_pair = pair_relation == 'opposite'

    if is_adjacent_pair:
        main_candidates = _adjacent_orthogonal_paths(point_a['xyz'], point_b['xyz'], centroid)
    elif is_opposite_pair:
        main_candidates = _orthogonal_mid_bend_paths(point_a['xyz'], point_b['xyz'], avg_z)
        if abs(point_a['xyz'][0] - point_b['xyz'][0]) <= 1e-9 or abs(point_a['xyz'][1] - point_b['xyz'][1]) <= 1e-9:
            main_candidates = [[point_a['xyz'], point_b['xyz']]] + main_candidates
    else:
        main_candidates = _candidate_orthogonal_paths(point_a['xyz'], point_b['xyz'], bbox)

    filtered_candidates = []
    for path in main_candidates:
        if all(
            bbox[0] - 1e-6 <= pt[0] <= bbox[2] + 1e-6 and
            bbox[1] - 1e-6 <= pt[1] <= bbox[3] + 1e-6
            for pt in path
        ):
            filtered_candidates.append(path)

    main_path = min(
        filtered_candidates or main_candidates or _candidate_orthogonal_paths(point_a['xyz'], point_b['xyz'], bbox),
        key=lambda path: (
            _point_to_polyline_distance_2d(centroid, path),
            _polyline_length([[pt[0], pt[1], pt[2]] for pt in path]),
        ),
    )

    lines = [_build_line_record(1, main_path, 'main', 'orthogonal')]
    line_id = 2
    main_path_xyz = lines[0]['geometry']['coordinates']
    main_path_tuples = [_point_to_xyz(coord) for coord in main_path_xyz]
    bend_points = main_path_tuples[1:-1]
    main_segment_ids = {point_a.get('segment_id'), point_b.get('segment_id')}
    main_sides = {
        side for side in (
            _bbox_side_for_point(point_a['xyz'], bbox),
            _bbox_side_for_point(point_b['xyz'], bbox),
        )
        if side is not None
    }

    remaining_points = [
        point for point in sorted(
            people_points,
            key=lambda pt: (pt.get('priority', 10), pt.get('segment_index', 10**6), pt.get('point_id', 10**6)),
        )
        if point['point_id'] not in {point_a['point_id'], point_b['point_id']}
    ]

    secondary_lines: List[List[Tuple[float, float, float]]] = []

    def add_connector(path: Optional[List[Tuple[float, float, float]]]) -> None:
        nonlocal line_id
        if not path:
            return
        clean = _dedupe_path(path)
        if len(clean) < 2 or _point_distance_2d(clean[0], clean[-1]) <= 1e-6:
            return
        lines.append(_build_line_record(line_id, clean, 'secondary', 'orthogonal'))
        secondary_lines.append(clean)
        line_id += 1

    if is_opposite_pair:
        off_direction_points = [pt for pt in remaining_points if pt.get('segment_id') not in main_segment_ids]
        same_direction_points = [pt for pt in remaining_points if pt.get('segment_id') in main_segment_ids]

        if len(bend_points) >= 1:
            for point in off_direction_points:
                bend = _nearest_bend_point(point['xyz'], bend_points)
                add_connector(_orthogonal_path_to_point(point['xyz'], bend, centroid) if bend else None)

            for point in same_direction_points:
                bend = _nearest_bend_point(point['xyz'], bend_points)
                add_connector(_orthogonal_path_to_point(point['xyz'], bend, centroid) if bend else None)
        else:
            for point in off_direction_points:
                add_connector(_perpendicular_connector_to_polyline(point, main_path_tuples))

            secondary_targets = secondary_lines[:]
            for point in same_direction_points:
                connector = None
                if secondary_targets:
                    best_target = min(
                        secondary_targets,
                        key=lambda target: _point_to_polyline_distance_2d(point['xyz'], target),
                    )
                    connector = _perpendicular_connector_to_polyline(point, best_target)
                if connector is None:
                    connector = _perpendicular_connector_to_polyline(point, main_path_tuples)
                add_connector(connector)
    else:
        off_direction_points = []
        same_direction_points = []
        for point in remaining_points:
            point_side = _bbox_side_for_point(point['xyz'], bbox)
            if point_side is not None and point_side in main_sides:
                same_direction_points.append(point)
            else:
                off_direction_points.append(point)

        for point in off_direction_points:
            connector = _best_perpendicular_connector_to_paths(
                point,
                [main_path_tuples] + secondary_lines,
            )
            if connector is None:
                bend = _nearest_bend_point(point['xyz'], bend_points)
                connector = _orthogonal_path_to_point(point['xyz'], bend, centroid) if bend else None
            add_connector(connector)

        for point in same_direction_points:
            connector = _best_perpendicular_connector_to_paths(
                point,
                [main_path_tuples] + secondary_lines,
            )
            if connector is None:
                bend = _nearest_bend_point(point['xyz'], bend_points)
                connector = _orthogonal_path_to_point(point['xyz'], bend, centroid) if bend else None
            add_connector(connector)

    return {
        'flow_pattern': 'orthogonal',
        'walking_main_line': _line_string(main_path),
        'walking_lines': lines,
    }


def _obstacle_bboxes(asset_has_set: Optional[List[Dict[str, Any]]]) -> List[Tuple[float, float, float, float]]:
    bboxes = []
    if not asset_has_set:
        return bboxes
    for asset in asset_has_set:
        if asset.get('asset_has_set_type') == 'arcade_column':
            continue
        coords = asset.get('geometry', {}).get('coordinates', [])
        if coords:
            bboxes.append(_bbox_from_coords(coords))
    return bboxes


def _clip_value(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _buffer_segment_polygon(
    p0: Tuple[float, float, float],
    p1: Tuple[float, float, float],
    width: float,
) -> Optional[List[Tuple[float, float, float]]]:
    segment = _vec_subtract(p1, p0)
    seg_length = _vec_length(segment)
    if seg_length <= 1e-9:
        return None
    half_width = width * 0.5
    perp = (-segment[1] / seg_length, segment[0] / seg_length, 0.0)
    offset = _vec_scale(perp, half_width)
    return [
        _vec_add(p0, offset),
        _vec_add(p1, offset),
        _vec_subtract(p1, offset),
        _vec_subtract(p0, offset),
    ]


def _count_flow_intersections(walking_lines: List[Dict[str, Any]]) -> int:
    intersections = set()
    for index, line_a in enumerate(walking_lines):
        coords_a = line_a.get('geometry', {}).get('coordinates', [])
        for line_b in walking_lines[index + 1:]:
            coords_b = line_b.get('geometry', {}).get('coordinates', [])
            for start_a, end_a in zip(coords_a, coords_a[1:]):
                p1 = _point_to_xyz(start_a)
                p2 = _point_to_xyz(end_a)
                for start_b, end_b in zip(coords_b, coords_b[1:]):
                    q1 = _point_to_xyz(start_b)
                    q2 = _point_to_xyz(end_b)
                    point = _segment_intersection_point_2d(p1, p2, q1, q2)
                    if point is not None:
                        intersections.add((round(point[0], 6), round(point[1], 6)))
    return len(intersections)


def _dynamic_rect_bboxes_for_width(
    public_space_geometry: Dict[str, Any],
    walking_lines: List[Dict[str, Any]],
    base_width: float,
) -> List[Tuple[float, float, float, float]]:
    if base_width <= 0.0:
        return []

    bbox_min_x, bbox_min_y, bbox_max_x, bbox_max_y, _ = _geometry_bbox(public_space_geometry)
    rect_bboxes: List[Tuple[float, float, float, float]] = []

    for line in walking_lines:
        line_role = line.get('line_role', 'secondary')
        line_width = base_width * (1.5 if line_role == 'main' else 1.0)
        if line_width <= 0.0:
            continue
        coords = line.get('geometry', {}).get('coordinates', [])
        for start, end in zip(coords, coords[1:]):
            p0 = _point_to_xyz(start)
            p1 = _point_to_xyz(end)
            polygon = _buffer_segment_polygon(p0, p1, line_width)
            if not polygon:
                continue
            polygon_geom = _polygon_string(polygon)
            polygon_bbox = _bbox_from_coords(polygon_geom['coordinates'])
            clipped_bbox = (
                _clip_value(polygon_bbox[0], bbox_min_x, bbox_max_x),
                _clip_value(polygon_bbox[1], bbox_min_y, bbox_max_y),
                _clip_value(polygon_bbox[2], bbox_min_x, bbox_max_x),
                _clip_value(polygon_bbox[3], bbox_min_y, bbox_max_y),
            )
            if clipped_bbox[2] - clipped_bbox[0] <= 1e-9 or clipped_bbox[3] - clipped_bbox[1] <= 1e-9:
                continue
            rect_bboxes.append(clipped_bbox)
    return rect_bboxes


def _partition_dynamic_static_rects(
    public_space_geometry: Dict[str, Any],
    dynamic_rect_bboxes: List[Tuple[float, float, float, float]],
) -> Tuple[List[Tuple[float, float, float, float]], List[Tuple[float, float, float, float]]]:
    bbox_min_x, bbox_min_y, bbox_max_x, bbox_max_y, _ = _geometry_bbox(public_space_geometry)
    split_x = sorted({bbox_min_x, bbox_max_x, *[rect[0] for rect in dynamic_rect_bboxes], *[rect[2] for rect in dynamic_rect_bboxes]})
    split_y = sorted({bbox_min_y, bbox_max_y, *[rect[1] for rect in dynamic_rect_bboxes], *[rect[3] for rect in dynamic_rect_bboxes]})

    dynamic_union_rects: List[Tuple[float, float, float, float]] = []
    static_rects: List[Tuple[float, float, float, float]] = []
    for x0, x1 in zip(split_x, split_x[1:]):
        for y0, y1 in zip(split_y, split_y[1:]):
            if x1 - x0 <= 1e-9 or y1 - y0 <= 1e-9:
                continue
            center_x, center_y = _cell_center((x0, y0, x1, y1))
            covered = any(
                rect[0] <= center_x <= rect[2] and rect[1] <= center_y <= rect[3]
                for rect in dynamic_rect_bboxes
            )
            if covered:
                dynamic_union_rects.append((x0, y0, x1, y1))
            else:
                static_rects.append((x0, y0, x1, y1))

    return _merge_rectangles(dynamic_union_rects), _merge_rectangles(static_rects)


def _solve_dynamic_width(
    public_space_geometry: Dict[str, Any],
    public_space_area: float,
    ratio_dynamic_static: float,
    walking_lines: List[Dict[str, Any]],
) -> float:
    target_area = public_space_area * ratio_dynamic_static
    if target_area <= 0.0 or not walking_lines:
        return 0.0

    bbox_min_x, bbox_min_y, bbox_max_x, bbox_max_y, _ = _geometry_bbox(public_space_geometry)
    max_width = min(bbox_max_x - bbox_min_x, bbox_max_y - bbox_min_y) * 0.45
    if max_width <= 1e-9:
        return 0.0

    def union_area_for_width(width: float) -> float:
        rects = _dynamic_rect_bboxes_for_width(public_space_geometry, walking_lines, width)
        if not rects:
            return 0.0
        dynamic_union_rects, _ = _partition_dynamic_static_rects(public_space_geometry, rects)
        return sum(_bbox_area(rect) for rect in dynamic_union_rects)

    if union_area_for_width(max_width) <= target_area:
        return max_width

    low = 0.0
    high = max_width
    for _ in range(48):
        mid = (low + high) * 0.5
        area = union_area_for_width(mid)
        if area < target_area:
            low = mid
        else:
            high = mid
    return high


def _rect_from_bbox(bbox: Tuple[float, float, float, float], z: float) -> List[Tuple[float, float, float]]:
    min_x, min_y, max_x, max_y = bbox
    return [
        (min_x, min_y, z),
        (max_x, min_y, z),
        (max_x, max_y, z),
        (min_x, max_y, z),
    ]


def _cell_center(bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
    min_x, min_y, max_x, max_y = bbox
    return ((min_x + max_x) * 0.5, (min_y + max_y) * 0.5)


def _merge_rectangles(rects: List[Tuple[float, float, float, float]]) -> List[Tuple[float, float, float, float]]:
    merged = list(rects)
    changed = True
    while changed:
        changed = False
        next_rects: List[Tuple[float, float, float, float]] = []
        while merged:
            current = merged.pop(0)
            did_merge = False
            for idx, other in enumerate(merged):
                if (
                    abs(current[1] - other[1]) < 1e-9 and
                    abs(current[3] - other[3]) < 1e-9 and
                    (abs(current[2] - other[0]) < 1e-9 or abs(other[2] - current[0]) < 1e-9)
                ):
                    current = (
                        min(current[0], other[0]),
                        current[1],
                        max(current[2], other[2]),
                        current[3],
                    )
                    merged.pop(idx)
                    changed = True
                    did_merge = True
                    break
                if (
                    abs(current[0] - other[0]) < 1e-9 and
                    abs(current[2] - other[2]) < 1e-9 and
                    (abs(current[3] - other[1]) < 1e-9 or abs(other[3] - current[1]) < 1e-9)
                ):
                    current = (
                        current[0],
                        min(current[1], other[1]),
                        current[2],
                        max(current[3], other[3]),
                    )
                    merged.pop(idx)
                    changed = True
                    did_merge = True
                    break
            next_rects.append(current)
            if did_merge:
                continue
        merged = next_rects
    return merged


def generate_people_points(
    public_space_geometry: Dict[str, Any],
    public_space_segments: List[Dict[str, Any]],
    asset_has_set: Optional[List[Dict[str, Any]]] = None,
    **kwargs
) -> List[Dict[str, Any]]:
    """Step 2: Generate people flow start/end points from segments.
    
    First checks for arcade columns within 1m. If found, splits the segment at
    each nearby column projection and uses the midpoint of every resulting
    sub-segment longer than 3m. Otherwise uses length-based generation.
    
    Returns a list of people point dictionaries with:
    - location: [x, y, z]
    - segment_id: int
    - priority: int (inherited from segment)
    - source: 'arcade_column' or 'length_based'
    """
    people_points = []
    
    # Vector math helpers
    def vec_subtract(v1, v2):
        return (v1[0] - v2[0], v1[1] - v2[1], v1[2] - v2[2])
    
    def vec_add(v1, v2):
        return (v1[0] + v2[0], v1[1] + v2[1], v1[2] + v2[2])
    
    def vec_scale(v, scale):
        return (v[0] * scale, v[1] * scale, v[2] * scale)
    
    def vec_length(v):
        return (v[0]**2 + v[1]**2 + v[2]**2) ** 0.5
    
    def vec_dot(v1, v2):
        return v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]
    
    def point_to_segment_projection(point, seg_p0, seg_p1):
        """Find closest point on segment to given point and its segment ratio."""
        seg_vec = vec_subtract(seg_p1, seg_p0)
        point_vec = vec_subtract(point, seg_p0)
        seg_len_sq = vec_dot(seg_vec, seg_vec)
        if seg_len_sq == 0:
            return seg_p0, 0.0
        t = vec_dot(point_vec, seg_vec) / seg_len_sq
        t = max(0, min(1, t))  # clamp to [0, 1]
        return vec_add(seg_p0, vec_scale(seg_vec, t)), t
    
    def polygon_centroid(coords):
        """Calculate centroid of polygon"""
        if not coords:
            return (0, 0, 0)
        cx = sum(c[0] for c in coords) / len(coords)
        cy = sum(c[1] for c in coords) / len(coords)
        cz = sum(c[2] if len(c) > 2 else 0 for c in coords) / len(coords)
        return (cx, cy, cz)
    
    # Extract arcade columns
    arcade_columns = []
    if asset_has_set:
        for asset in asset_has_set:
            asset_type = asset.get('asset_has_set_type')
            if asset_type == 'arcade_column':
                geom = asset.get('geometry', {})
                coords = geom.get('coordinates', [])
                if coords:
                    centroid = polygon_centroid(coords)
                    arcade_columns.append(centroid)
    
    for seg in public_space_segments:
        seg_id = seg.get('segment_id')
        priority = seg.get('priority', 10)
        seg_geom = seg.get('geometry', {})
        coords = seg_geom.get('coordinates', [])
        
        if len(coords) < 2:
            continue
        
        p0 = (coords[0][0], coords[0][1], coords[0][2] if len(coords[0]) > 2 else 0.0)
        p1 = (coords[-1][0], coords[-1][1], coords[-1][2] if len(coords[-1]) > 2 else 0.0)
        
        dir_vec = vec_subtract(p1, p0)
        seg_length = vec_length(dir_vec)
        
        # Check for nearby arcade columns (within 1m)
        arcade_split_ratios = [0.0, 1.0]
        for col_center in arcade_columns:
            # Find perpendicular foot from column to segment
            perp_foot, foot_ratio = point_to_segment_projection(col_center, p0, p1)
            
            # Distance from column center to perpendicular foot
            dist_to_seg = vec_length(vec_subtract(col_center, perp_foot))
            # Check if column is within 1m of segment
            if dist_to_seg <= 1.0:
                arcade_split_ratios.append(foot_ratio)

        arcade_split_ratios = sorted(set(round(ratio, 6) for ratio in arcade_split_ratios))
        arcade_point_added = False

        if len(arcade_split_ratios) > 2:
            for start_ratio, end_ratio in zip(arcade_split_ratios, arcade_split_ratios[1:]):
                sub_length = seg_length * (end_ratio - start_ratio)
                if sub_length <= 3.0:
                    continue

                mid_ratio = (start_ratio + end_ratio) * 0.5
                sub_mid = vec_add(p0, vec_scale(dir_vec, mid_ratio))
                people_points.append({
                    'location': list(sub_mid),
                    'segment_id': seg_id,
                    'priority': priority,
                    'source': 'arcade_column'
                })
                arcade_point_added = True
        
        # If arcade column logic applied, skip length-based generation
        if arcade_point_added:
            continue
        
        # Length-based generation (only if no arcade columns)
        ratios = []
        if seg_length < 25:
            ratios = [0.5]
        elif seg_length < 75:
            ratios = [1/3, 2/3]
        else:
            ratios = [1/4, 2/4, 3/4]
        
        for ratio in ratios:
            scaled_dir = vec_scale(dir_vec, ratio)
            pt = vec_add(p0, scaled_dir)
            
            people_points.append({
                'location': list(pt),
                'segment_id': seg_id,
                'priority': priority,
                'source': 'length_based'
            })
    
    return people_points


def generate_flow_lines(
    public_space_type: str,
    public_space_geometry: Dict[str, Any],
    public_space_segments: List[Dict[str, Any]],
    people_points: List[Dict[str, Any]],
    asset_has_set: Optional[List[Dict[str, Any]]] = None,
    flow_pattern_override: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Step 3: generate a walking flow network and main line."""
    prepared_points = _prepare_people_points(people_points, public_space_segments)
    if not prepared_points:
        return {
            'flow_pattern': None,
            'walking_main_line': None,
            'walking_lines': [],
        }

    seed_value = f"{public_space_type}|{public_space_geometry.get('coordinates', [])}|{len(prepared_points)}"
    pattern = flow_pattern_override or _choose_pattern(public_space_type, seed_value)

    if pattern == 'cross':
        flow = _build_cross_flow(public_space_geometry)
    elif pattern == 'ring':
        flow = _build_ring_flow(public_space_geometry, prepared_points, asset_has_set)
    elif pattern == 'orthogonal':
        flow = _build_orthogonal_flow(
            public_space_geometry,
            prepared_points,
            public_space_segments,
            public_space_type,
        )
    else:
        flow = _build_fishbone_flow(
            public_space_geometry,
            prepared_points,
            public_space_segments,
            public_space_type,
        )

    obstacle_bboxes = _obstacle_bboxes(asset_has_set)
    if obstacle_bboxes and pattern not in {'ring', 'cross'}:
        intersects = any(
            _polyline_intersects_any_bbox(line['geometry']['coordinates'], obstacle_bboxes)
            for line in flow['walking_lines']
        )
        if intersects:
            flow = _build_ring_flow(public_space_geometry, prepared_points, asset_has_set)

    return flow


def generate_dynamic_static_zones(*args, **kwargs):
    """Step 4: solve flow width and derive dynamic/static zones."""
    public_space_geometry = kwargs.get('public_space_geometry', {})
    ratio_dynamic_static = kwargs.get('ratio_dynamic_static', 0.5)
    walking_lines = kwargs.get('walking_lines', []) or []

    geometry_coords = public_space_geometry.get('coordinates', [])
    public_space_area = _polygon_area_2d(geometry_coords)
    bbox_min_x, bbox_min_y, bbox_max_x, bbox_max_y, avg_z = _geometry_bbox(public_space_geometry)
    bbox_area = max(0.0, (bbox_max_x - bbox_min_x) * (bbox_max_y - bbox_min_y))

    if public_space_area <= 0.0 or not walking_lines:
        return {
            'dynamic_zone_width': 0.0,
            'dynamic_area_target': public_space_area * ratio_dynamic_static,
            'dynamic_area_estimated': 0.0,
            'static_area_estimated': public_space_area,
            'dynamic_zones': [],
            'static_zones': [_polygon_string(_rect_from_bbox((bbox_min_x, bbox_min_y, bbox_max_x, bbox_max_y), avg_z))] if bbox_area > 0 else [],
        }

    solved_width = _solve_dynamic_width(public_space_geometry, public_space_area, ratio_dynamic_static, walking_lines)
    max_width = min(bbox_max_x - bbox_min_x, bbox_max_y - bbox_min_y) * 0.45 if bbox_area > 0 else solved_width
    dynamic_zone_width = _clip_value(solved_width, 0.0, max_width) if max_width > 0 else max(0.0, solved_width)

    dynamic_rect_bboxes = _dynamic_rect_bboxes_for_width(public_space_geometry, walking_lines, dynamic_zone_width)
    dynamic_union_rects, static_rects = _partition_dynamic_static_rects(public_space_geometry, dynamic_rect_bboxes)
    dynamic_area_estimated = sum(_bbox_area(rect) for rect in dynamic_union_rects)
    dynamic_zone_records = [
        {
            'zone_id': index + 1,
            'zone_type': 'dynamic',
            'width': dynamic_zone_width,
            'geometry': _polygon_string(_rect_from_bbox(rect, avg_z)),
            'area': _bbox_area(rect),
        }
        for index, rect in enumerate(dynamic_union_rects)
        if _bbox_area(rect) > 1e-9
    ]
    static_zone_records = [
        {
            'zone_id': index + 1,
            'zone_type': 'static',
            'geometry': _polygon_string(_rect_from_bbox(rect, avg_z)),
            'area': _bbox_area(rect),
        }
        for index, rect in enumerate(static_rects)
        if _bbox_area(rect) > 1e-9
    ]

    static_area_estimated = sum(zone['area'] for zone in static_zone_records)
    return {
        'dynamic_zone_width': dynamic_zone_width,
        'dynamic_area_target': public_space_area * ratio_dynamic_static,
        'dynamic_area_estimated': dynamic_area_estimated,
        'static_area_estimated': static_area_estimated,
        'dynamic_zones': dynamic_zone_records,
        'static_zones': static_zone_records,
    }


def _asset_dimensions(candidate: Dict[str, Any]) -> Tuple[float, float]:
    size = candidate.get('asset_geometry_size', [0.5, 0.5])
    if isinstance(size, (int, float)):
        value = float(size)
        return (value, value)
    if isinstance(size, (list, tuple)) and len(size) >= 2:
        return (float(size[0]), float(size[1]))
    return (0.5, 0.5)


def _asset_geometry_at(
    center: Tuple[float, float, float],
    size: Any = 0.5,
    orientation: Tuple[float, float, float] = (1.0, 0.0, 0.0),
) -> Dict[str, Any]:
    if isinstance(size, (list, tuple)) and len(size) >= 2:
        along_size = float(size[0])
        across_size = float(size[1])
    else:
        along_size = float(size)
        across_size = float(size)
    along = _normalize_2d(orientation)
    perp = (-along[1], along[0], 0.0)
    half_along = along_size * 0.5
    half_across = across_size * 0.5
    return _polygon_string([
        (
            center[0] - along[0] * half_along - perp[0] * half_across,
            center[1] - along[1] * half_along - perp[1] * half_across,
            center[2],
        ),
        (
            center[0] + along[0] * half_along - perp[0] * half_across,
            center[1] + along[1] * half_along - perp[1] * half_across,
            center[2],
        ),
        (
            center[0] + along[0] * half_along + perp[0] * half_across,
            center[1] + along[1] * half_along + perp[1] * half_across,
            center[2],
        ),
        (
            center[0] - along[0] * half_along + perp[0] * half_across,
            center[1] - along[1] * half_along + perp[1] * half_across,
            center[2],
        ),
    ])


def _asset_url(name: str, rng: random.Random) -> str:
    slug = name.lower().replace(' ', '_')
    return f"https://example.com/assets/{slug}/{rng.getrandbits(40):010x}.glb"


def _zone_center(zone: Dict[str, Any]) -> Tuple[float, float, float]:
    coords = zone.get('geometry', {}).get('coordinates', [])
    return _polygon_centroid(coords)


def _zone_key(zone: Dict[str, Any]) -> str:
    return f"{zone.get('zone_type', 'zone')}:{zone.get('zone_id', 0)}"


def _zone_candidate_centers(zone: Dict[str, Any], asset_size: float) -> List[Tuple[float, float, float]]:
    coords = zone.get('geometry', {}).get('coordinates', [])
    if not coords:
        return []
    min_x, min_y, max_x, max_y = _bbox_from_coords(coords)
    center = _zone_center(zone)
    margin = asset_size * 0.5
    usable_min_x = min_x + margin
    usable_max_x = max_x - margin
    usable_min_y = min_y + margin
    usable_max_y = max_y - margin
    if usable_min_x > usable_max_x or usable_min_y > usable_max_y:
        return [center]

    step = max(asset_size + 0.1, 0.6)
    x_values = []
    y_values = []

    x = usable_min_x
    while x <= usable_max_x + 1e-9:
        x_values.append(x)
        x += step
    if not x_values or abs(x_values[-1] - usable_max_x) > 1e-6:
        x_values.append(usable_max_x)

    y = usable_min_y
    while y <= usable_max_y + 1e-9:
        y_values.append(y)
        y += step
    if not y_values or abs(y_values[-1] - usable_max_y) > 1e-6:
        y_values.append(usable_max_y)

    candidates = [
        (xv, yv, center[2])
        for xv in x_values
        for yv in y_values
    ]
    if center not in candidates:
        candidates.append(center)
    unique_candidates = []
    for candidate in candidates:
        if not any(_point_distance_2d(candidate, existing) <= 1e-6 for existing in unique_candidates):
            unique_candidates.append(candidate)
    return sorted(unique_candidates, key=lambda pt: (_point_distance_2d(pt, center), pt[0], pt[1]))


def _center_is_available(
    center: Tuple[float, float, float],
    occupied_centers: List[Tuple[float, float, float]],
    asset_size: float,
) -> bool:
    min_distance = asset_size + 0.05
    return all(_point_distance_2d(center, occupied) >= min_distance for occupied in occupied_centers)


def _zone_bbox(zone: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    coords = zone.get('geometry', {}).get('coordinates', [])
    if not coords:
        return None
    return _bbox_from_coords(coords)


def _zone_touches_segment(zone: Dict[str, Any], segment: Dict[str, Any], tolerance: float = 1e-6) -> bool:
    zone_bbox = _zone_bbox(zone)
    segment_coords = segment.get('geometry', {}).get('coordinates', [])
    if zone_bbox is None or len(segment_coords) < 2:
        return False
    min_x, min_y, max_x, max_y = zone_bbox
    start = segment_coords[0]
    end = segment_coords[-1]
    x1, y1 = start[0], start[1]
    x2, y2 = end[0], end[1]
    if abs(x1 - x2) <= tolerance:
        if abs(x1 - min_x) > tolerance and abs(x1 - max_x) > tolerance:
            return False
        overlap = min(max_y, max(y1, y2)) - max(min_y, min(y1, y2))
        return overlap > tolerance
    if abs(y1 - y2) <= tolerance:
        if abs(y1 - min_y) > tolerance and abs(y1 - max_y) > tolerance:
            return False
        overlap = min(max_x, max(x1, x2)) - max(min_x, min(x1, x2))
        return overlap > tolerance
    return False


def _count_zone_boundary_type_contacts(
    zone: Dict[str, Any],
    public_space_segments: List[Dict[str, Any]],
    boundary_types: Set[str],
) -> int:
    count = 0
    for segment in public_space_segments:
        if segment.get('boundary_type') not in boundary_types:
            continue
        if _zone_touches_segment(zone, segment):
            count += 1
    return count


def _candidate_zone_pool(
    candidate: Dict[str, Any],
    public_space_type: str,
    dynamic_zones: List[Dict[str, Any]],
    static_zones: List[Dict[str, Any]],
    public_space_segments: List[Dict[str, Any]],
    zone_occupancy: Dict[str, List[Tuple[float, float, float]]],
) -> List[Dict[str, Any]]:
    preferred = candidate.get('preferred_zone', 'static')
    if preferred == 'dynamic':
        pool = list(dynamic_zones or static_zones)
    elif preferred == 'static':
        pool = list(static_zones or dynamic_zones)
    else:
        pool = list(static_zones or dynamic_zones)

    if public_space_type == 'block_entrance' and preferred == 'static':
        filtered = [
            zone for zone in pool
            if _count_zone_boundary_type_contacts(
                zone,
                public_space_segments,
                {'block_boundary_primary', 'block_boundary_secondary', 'block_boundary_other'},
            ) < 2
        ]
        if filtered:
            pool = filtered

    return sorted(
        pool,
        key=lambda zone: (
            len(zone_occupancy.get(_zone_key(zone), [])),
            zone.get('zone_id', 0),
        ),
    )


def _choose_zone_and_center_for_asset(
    candidate: Dict[str, Any],
    public_space_type: str,
    dynamic_zones: List[Dict[str, Any]],
    static_zones: List[Dict[str, Any]],
    public_space_segments: List[Dict[str, Any]],
    usage: Dict[str, int],
    zone_occupancy: Dict[str, List[Tuple[float, float, float]]],
) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[float, float, float]]]:
    preferred = candidate.get('preferred_zone', 'static')
    pool = _candidate_zone_pool(
        candidate,
        public_space_type,
        dynamic_zones,
        static_zones,
        public_space_segments,
        zone_occupancy,
    )
    if not pool:
        return None, None
    key = f"{candidate.get('asset_candidates_name', 'asset')}|{preferred}"
    start_index = usage.get(key, 0) % len(pool)
    usage[key] = usage.get(key, 0) + 1
    asset_size = max(_asset_dimensions(candidate))

    for offset in range(len(pool)):
        zone = pool[(start_index + offset) % len(pool)]
        zone_key = _zone_key(zone)
        occupied_centers = zone_occupancy.setdefault(zone_key, [])
        for center in _zone_candidate_centers(zone, asset_size):
            if _center_is_available(center, occupied_centers, asset_size):
                occupied_centers.append(center)
                return zone, center
    return None, None


def _fallback_center(public_space_geometry: Dict[str, Any]) -> Tuple[float, float, float]:
    coords = public_space_geometry.get('coordinates', [])
    return _polygon_centroid(coords) if coords else (0.0, 0.0, 0.0)


def _candidate_probability(candidate: Dict[str, Any], public_space_type: str) -> float:
    probability_by_type = candidate.get('probability_by_type', {})
    if isinstance(probability_by_type, dict) and public_space_type in probability_by_type:
        return float(probability_by_type[public_space_type])
    return float(candidate.get('probability', 1.0))


def _polygon_area_2d(coords: List[List[float]]) -> float:
    if len(coords) < 4:
        return 0.0
    area = 0.0
    for idx in range(len(coords) - 1):
        x1, y1 = coords[idx][0], coords[idx][1]
        x2, y2 = coords[idx + 1][0], coords[idx + 1][1]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def _is_central_static_zone(zone: Dict[str, Any], public_space_geometry: Dict[str, Any]) -> bool:
    zone_coords = zone.get('geometry', {}).get('coordinates', [])
    space_coords = public_space_geometry.get('coordinates', [])
    if not zone_coords or not space_coords:
        return False
    zone_center = _zone_center(zone)
    min_x, min_y, max_x, max_y = _bbox_from_coords(space_coords)
    space_center = ((min_x + max_x) * 0.5, (min_y + max_y) * 0.5)
    half_width = max((max_x - min_x) * 0.125, 0.5)
    half_height = max((max_y - min_y) * 0.125, 0.5)
    in_central_window = (
        abs(zone_center[0] - space_center[0]) <= half_width
        and abs(zone_center[1] - space_center[1]) <= half_height
    )
    if not in_central_window:
        return False
    space_area = _polygon_area_2d(space_coords)
    zone_area = float(zone.get('area', 0.0)) or _polygon_area_2d(zone_coords)
    return space_area > 0.0 and zone_area >= space_area * 0.25


def _candidate_allowed(
    candidate: Dict[str, Any],
    public_space_type: str,
    public_space_geometry: Dict[str, Any],
    static_zones: List[Dict[str, Any]],
) -> bool:
    if candidate.get('requires_central_static_zone'):
        return any(_is_central_static_zone(zone, public_space_geometry) for zone in static_zones)
    return True


def _make_asset_record(
    asset_id: int,
    candidate: Dict[str, Any],
    center: Tuple[float, float, float],
    rng: random.Random,
    zone: Optional[Dict[str, Any]] = None,
    orientation: Tuple[float, float, float] = (1.0, 0.0, 0.0),
) -> Dict[str, Any]:
    dimensions = _asset_dimensions(candidate)
    return {
        'asset_id': asset_id,
        'asset_candidates_name': candidate['asset_candidates_name'],
        'asset_URL': _asset_url(candidate['asset_candidates_name'], rng),
        'geometry': _asset_geometry_at(center, dimensions, orientation),
        'asset_location': [center[0], center[1], center[2]],
        'asset_orientation': [orientation[0], orientation[1], orientation[2]],
        'zone_type': zone.get('zone_type') if zone else 'fallback',
        'zone_id': zone.get('zone_id') if zone else None,
    }


def _segment_overlap_interval_with_zone(
    segment: Dict[str, Any],
    zone: Dict[str, Any],
) -> Optional[Tuple[str, float, float, Tuple[float, float, float], Tuple[float, float, float]]]:
    zone_bbox = _zone_bbox(zone)
    coords = segment.get('geometry', {}).get('coordinates', [])
    if zone_bbox is None or len(coords) < 2:
        return None
    min_x, min_y, max_x, max_y = zone_bbox
    p0 = _point_to_xyz(coords[0])
    p1 = _point_to_xyz(coords[-1])
    if abs(p0[0] - p1[0]) <= 1e-6:
        overlap_min = max(min(p0[1], p1[1]), min_y)
        overlap_max = min(max(p0[1], p1[1]), max_y)
        if overlap_max - overlap_min <= 1e-6:
            return None
        tangent = (0.0, 1.0 if p1[1] >= p0[1] else -1.0, 0.0)
        return ('vertical', overlap_min, overlap_max, p0, tangent)
    if abs(p0[1] - p1[1]) <= 1e-6:
        overlap_min = max(min(p0[0], p1[0]), min_x)
        overlap_max = min(max(p0[0], p1[0]), max_x)
        if overlap_max - overlap_min <= 1e-6:
            return None
        tangent = (1.0 if p1[0] >= p0[0] else -1.0, 0.0, 0.0)
        return ('horizontal', overlap_min, overlap_max, p0, tangent)
    return None


def _point_inside_zone_bbox(
    point: Tuple[float, float, float],
    zone: Dict[str, Any],
    margin: float = 0.0,
) -> bool:
    zone_bbox = _zone_bbox(zone)
    if zone_bbox is None:
        return False
    min_x, min_y, max_x, max_y = zone_bbox
    return (
        min_x + margin <= point[0] <= max_x - margin
        and min_y + margin <= point[1] <= max_y - margin
    )


def _zone_short_side(zone: Dict[str, Any]) -> float:
    zone_bbox = _zone_bbox(zone)
    if zone_bbox is None:
        return 0.0
    min_x, min_y, max_x, max_y = zone_bbox
    return min(max_x - min_x, max_y - min_y)


def _street_boundary_zones(
    static_zones: List[Dict[str, Any]],
    public_space_segments: List[Dict[str, Any]],
) -> Tuple[List[Tuple[Dict[str, Any], Dict[str, Any]]], List[Dict[str, Any]]]:
    block_segments = [
        segment
        for segment in public_space_segments
        if segment.get('boundary_type') in {'block_boundary_primary', 'block_boundary_secondary', 'block_boundary_other'}
    ]
    outer: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    inner: List[Dict[str, Any]] = []
    for zone in static_zones:
        best_segment = None
        best_length = -1.0
        for segment in block_segments:
            overlap = _segment_overlap_interval_with_zone(segment, zone)
            if overlap is None:
                continue
            overlap_length = overlap[2] - overlap[1]
            if overlap_length > best_length:
                best_length = overlap_length
                best_segment = segment
        if best_segment is not None:
            outer.append((zone, best_segment))
        else:
            inner.append(zone)
    return outer, inner


def _street_interval_centers(
    zone: Dict[str, Any],
    segment: Dict[str, Any],
    interval: float,
    inward_offset: float,
) -> List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
    overlap = _segment_overlap_interval_with_zone(segment, zone)
    if overlap is None:
        return []
    axis, start_value, end_value, line_point, tangent = overlap
    usable_length = end_value - start_value
    count = int(usable_length // interval)
    if count <= 0:
        return []
    zone_center = _zone_center(zone)
    step = usable_length / (count + 1)
    outward_candidates: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []
    for index in range(count):
        value = start_value + step * (index + 1)
        if axis == 'horizontal':
            base = (value, line_point[1], zone_center[2])
        else:
            base = (line_point[0], value, zone_center[2])
        perp_options = [(-tangent[1], tangent[0], 0.0), (tangent[1], -tangent[0], 0.0)]
        chosen_center = None
        chosen_perp = None
        for perp in perp_options:
            candidate_center = (
                base[0] + perp[0] * inward_offset,
                base[1] + perp[1] * inward_offset,
                base[2],
            )
            if _point_inside_zone_bbox(candidate_center, zone):
                chosen_center = candidate_center
                chosen_perp = perp
                break
        if chosen_center is not None and chosen_perp is not None:
            outward_candidates.append((chosen_center, tangent))
    return outward_candidates


def _street_inner_zone_centers(zone: Dict[str, Any], interval: float) -> List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
    zone_bbox = _zone_bbox(zone)
    if zone_bbox is None:
        return []
    min_x, min_y, max_x, max_y = zone_bbox
    width = max_x - min_x
    height = max_y - min_y
    zone_center = _zone_center(zone)
    if width >= height:
        count = int(width // interval)
        if count <= 0:
            return []
        step = width / (count + 1)
        y = zone_center[1]
        return [((min_x + step * (idx + 1), y, zone_center[2]), (1.0, 0.0, 0.0)) for idx in range(count)]
    count = int(height // interval)
    if count <= 0:
        return []
    step = height / (count + 1)
    x = zone_center[0]
    return [((x, min_y + step * (idx + 1), zone_center[2]), (0.0, 1.0, 0.0)) for idx in range(count)]


def _zones_touching_segments(
    zones: List[Dict[str, Any]],
    public_space_segments: List[Dict[str, Any]],
    boundary_types: Set[str],
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    touched: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for zone in zones:
        best_segment = None
        best_length = -1.0
        for segment in public_space_segments:
            if segment.get('boundary_type') not in boundary_types:
                continue
            overlap = _segment_overlap_interval_with_zone(segment, zone)
            if overlap is None:
                continue
            overlap_length = overlap[2] - overlap[1]
            if overlap_length > best_length:
                best_length = overlap_length
                best_segment = segment
        if best_segment is not None:
            touched.append((zone, best_segment))
    return touched


def _grid_fill_centers(
    zone: Dict[str, Any],
    min_spacing: float,
    margin: float,
) -> List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
    zone_bbox = _zone_bbox(zone)
    if zone_bbox is None:
        return []
    min_x, min_y, max_x, max_y = zone_bbox
    zone_center = _zone_center(zone)
    usable_min_x = min_x + margin
    usable_max_x = max_x - margin
    usable_min_y = min_y + margin
    usable_max_y = max_y - margin
    if usable_min_x > usable_max_x or usable_min_y > usable_max_y:
        return []
    width = usable_max_x - usable_min_x
    height = usable_max_y - usable_min_y
    centers: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []
    if width >= height:
        cols = max(1, int(width // min_spacing))
        rows = max(1, int(height // min_spacing))
        step_x = width / (cols + 1)
        step_y = height / (rows + 1)
        for row in range(rows):
            y = usable_min_y + step_y * (row + 1)
            for col in range(cols):
                x = usable_min_x + step_x * (col + 1)
                centers.append(((x, y, zone_center[2]), (1.0, 0.0, 0.0)))
    else:
        cols = max(1, int(width // min_spacing))
        rows = max(1, int(height // min_spacing))
        step_x = width / (cols + 1)
        step_y = height / (rows + 1)
        for col in range(cols):
            x = usable_min_x + step_x * (col + 1)
            for row in range(rows):
                y = usable_min_y + step_y * (row + 1)
                centers.append(((x, y, zone_center[2]), (0.0, 1.0, 0.0)))
    return centers


def _add_zone_fill_assets(
    asset_list: List[Dict[str, Any]],
    candidate: Dict[str, Any],
    zone: Dict[str, Any],
    rng: random.Random,
    min_spacing: float = 3.0,
) -> None:
    dimensions = _asset_dimensions(candidate)
    margin = max(dimensions) * 0.5
    for center, orientation in _grid_fill_centers(zone, min_spacing, margin):
        asset_list.append(_make_asset_record(len(asset_list) + 1, candidate, center, rng, zone, orientation))


def _add_zone_cover_asset(
    asset_list: List[Dict[str, Any]],
    candidate: Dict[str, Any],
    zone: Dict[str, Any],
    rng: random.Random,
) -> None:
    center = _zone_center(zone)
    asset_list.append({
        'asset_id': len(asset_list) + 1,
        'asset_candidates_name': candidate['asset_candidates_name'],
        'asset_URL': _asset_url(candidate['asset_candidates_name'], rng),
        'geometry': zone['geometry'],
        'asset_location': [center[0], center[1], center[2]],
        'asset_orientation': [1.0, 0.0, 0.0],
        'zone_type': zone.get('zone_type'),
        'zone_id': zone.get('zone_id'),
    })


def _choose_weighted_candidate(
    options: List[Tuple[Dict[str, Any], float]],
    rng: random.Random,
) -> Optional[Dict[str, Any]]:
    filtered = [(candidate, weight) for candidate, weight in options if candidate is not None and weight > 0.0]
    if not filtered:
        return None
    total = sum(weight for _, weight in filtered)
    draw = rng.random() * total
    cumulative = 0.0
    for candidate, weight in filtered:
        cumulative += weight
        if draw <= cumulative:
            return candidate
    return filtered[-1][0]


def _place_single_dynamic_asset(
    asset_list: List[Dict[str, Any]],
    candidate: Optional[Dict[str, Any]],
    dynamic_zones: List[Dict[str, Any]],
    rng: random.Random,
    probability: float,
) -> None:
    if candidate is None or not dynamic_zones or rng.random() > probability:
        return
    zone = max(dynamic_zones, key=lambda item: float(item.get('area', 0.0)))
    center = _zone_center(zone)
    asset_list.append(_make_asset_record(len(asset_list) + 1, candidate, center, rng, zone))


def _place_single_segment_side_asset(
    asset_list: List[Dict[str, Any]],
    candidate: Optional[Dict[str, Any]],
    zone_segment_pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]],
    rng: random.Random,
    probability: float,
    offset: float = 0.5,
) -> None:
    if candidate is None or not zone_segment_pairs or rng.random() > probability:
        return
    zone, segment = max(zone_segment_pairs, key=lambda pair: float(pair[0].get('area', 0.0)))
    positions = _street_interval_centers(zone, segment, 9999.0, offset)
    if positions:
        center, tangent = positions[0]
    else:
        center = _zone_center(zone)
        tangent = (1.0, 0.0, 0.0)
    asset_list.append(_make_asset_record(len(asset_list) + 1, candidate, center, rng, zone, tangent))


def _place_single_wall_offset_asset(
    asset_list: List[Dict[str, Any]],
    candidate: Optional[Dict[str, Any]],
    zone_segment_pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]],
    rng: random.Random,
    probability: float,
    offset: float = 0.5,
) -> None:
    if candidate is None or not zone_segment_pairs or rng.random() > probability:
        return

    zone, segment = max(zone_segment_pairs, key=lambda pair: float(pair[0].get('area', 0.0)))
    overlap = _segment_overlap_interval_with_zone(segment, zone)
    if overlap is None:
        center = _zone_center(zone)
        asset_list.append(_make_asset_record(len(asset_list) + 1, candidate, center, rng, zone))
        return

    axis, start_value, end_value, line_point, tangent = overlap
    along_size, _ = _asset_dimensions(candidate)
    half_along = along_size * 0.5
    usable_start = start_value + half_along
    usable_end = end_value - half_along
    if usable_end <= usable_start + 1e-9:
        value = (start_value + end_value) * 0.5
    else:
        value = rng.uniform(usable_start, usable_end)

    zone_center = _zone_center(zone)
    if axis == 'horizontal':
        base = (value, line_point[1], zone_center[2])
    else:
        base = (line_point[0], value, zone_center[2])

    perp_options = [(-tangent[1], tangent[0], 0.0), (tangent[1], -tangent[0], 0.0)]
    center = None
    for perp in perp_options:
        candidate_center = (
            base[0] + perp[0] * offset,
            base[1] + perp[1] * offset,
            base[2],
        )
        if _point_inside_zone_bbox(candidate_center, zone, margin=0.5):
            center = candidate_center
            break
    if center is None:
        for perp in perp_options:
            candidate_center = (
                base[0] + perp[0] * offset,
                base[1] + perp[1] * offset,
                base[2],
            )
            if _point_inside_zone_bbox(candidate_center, zone):
                center = candidate_center
                break
    if center is None:
        center = _zone_center(zone)

    asset_list.append(_make_asset_record(len(asset_list) + 1, candidate, center, rng, zone, tangent))


def _yard_roofless_central_zone(
    static_zones: List[Dict[str, Any]],
    public_space_geometry: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not static_zones:
        return None
    space_bbox = _bbox_from_coords(public_space_geometry.get('coordinates', []))
    space_center = ((space_bbox[0] + space_bbox[2]) * 0.5, (space_bbox[1] + space_bbox[3]) * 0.5)
    space_area = _polygon_area_2d(public_space_geometry.get('coordinates', []))
    candidates = []
    for zone in static_zones:
        center = _zone_center(zone)
        distance = ((center[0] - space_center[0]) ** 2 + (center[1] - space_center[1]) ** 2) ** 0.5
        area = float(zone.get('area', 0.0))
        if space_area > 0.0 and area >= space_area * 0.15:
            candidates.append((distance, -area, zone))
    return min(candidates, default=(0.0, 0.0, None))[2]


def _place_city_yard_roof_assets(
    public_space_geometry: Dict[str, Any],
    public_space_segments: List[Dict[str, Any]],
    dynamic_zones: List[Dict[str, Any]],
    static_zones: List[Dict[str, Any]],
    asset_candidates_list: List[Dict[str, Any]],
    rng: random.Random,
) -> List[Dict[str, Any]]:
    candidate_map = {candidate['asset_candidates_name']: candidate for candidate in asset_candidates_list}
    asset_list: List[Dict[str, Any]] = []
    for zone in static_zones:
        chosen = _choose_weighted_candidate([
            (candidate_map.get('long_bench'), 0.25),
            (candidate_map.get('seat_group'), 0.75),
        ], rng)
        if chosen is not None:
            spacing = 10.0 if chosen.get('asset_candidates_name') == 'seat_group' else 3.0
            _add_zone_fill_assets(asset_list, chosen, zone, rng, spacing)
    building_zones = _zones_touching_segments(
        static_zones,
        public_space_segments,
        {'building_wall', 'building_entrance_main', 'building_other_type'},
    )
    _place_single_wall_offset_asset(asset_list, candidate_map.get('vending_machine'), building_zones, rng, 0.50, 0.5)
    _place_single_dynamic_asset(asset_list, candidate_map.get('food_cart'), dynamic_zones, rng, 0.50)
    return asset_list


def _place_building_entrance_assets(
    public_space_segments: List[Dict[str, Any]],
    static_zones: List[Dict[str, Any]],
    asset_candidates_list: List[Dict[str, Any]],
    rng: random.Random,
) -> List[Dict[str, Any]]:
    candidate_map = {candidate['asset_candidates_name']: candidate for candidate in asset_candidates_list}
    asset_list: List[Dict[str, Any]] = []
    building_zones = _zones_touching_segments(
        static_zones,
        public_space_segments,
        {'building_wall', 'building_entrance_main', 'building_other_type'},
    )
    _place_single_wall_offset_asset(asset_list, candidate_map.get('vending_machine'), building_zones, rng, 0.50, 0.5)
    _place_single_wall_offset_asset(asset_list, candidate_map.get('smart_locker'), building_zones, rng, 1.00, 0.5)
    return asset_list


def _place_city_yard_roofless_assets(
    public_space_geometry: Dict[str, Any],
    public_space_segments: List[Dict[str, Any]],
    dynamic_zones: List[Dict[str, Any]],
    static_zones: List[Dict[str, Any]],
    asset_candidates_list: List[Dict[str, Any]],
    rng: random.Random,
) -> List[Dict[str, Any]]:
    candidate_map = {candidate['asset_candidates_name']: candidate for candidate in asset_candidates_list}
    asset_list: List[Dict[str, Any]] = []
    used_zone_ids: Set[int] = set()

    central_zone = _yard_roofless_central_zone(static_zones, public_space_geometry)
    if central_zone is not None and candidate_map.get('sculpture') is not None:
        asset_list.append(_make_asset_record(
            len(asset_list) + 1,
            candidate_map['sculpture'],
            _zone_center(central_zone),
            rng,
            central_zone,
        ))
        used_zone_ids.add(int(central_zone.get('zone_id', -1)))

    for zone in static_zones:
        zone_id = int(zone.get('zone_id', -1))
        if zone_id in used_zone_ids:
            continue
        chosen = _choose_weighted_candidate([
            (candidate_map.get('long_bench'), 0.25),
            (candidate_map.get('grass_patch'), 0.50),
            (candidate_map.get('seat_group'), 0.25),
        ], rng)
        if chosen is None:
            continue
        if chosen.get('asset_candidates_name') == 'grass_patch':
            _add_zone_cover_asset(asset_list, chosen, zone, rng)
        else:
            _add_zone_fill_assets(asset_list, chosen, zone, rng, 10.0)

    outer_zones = _zones_touching_segments(
        static_zones,
        public_space_segments,
        {'block_boundary_primary', 'block_boundary_secondary', 'block_boundary_other'},
    )
    branch_outer = rng.random() <= 0.75
    greenery_points: List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Dict[str, Any]]] = []
    guard_candidate = candidate_map.get('guard_rail')
    light_candidate = candidate_map.get('street_light')
    greenery_candidate_name = 'tree_pool' if rng.random() <= 0.5 else 'flower_box'
    greenery_candidate = candidate_map.get(greenery_candidate_name)
    inner_tree_candidate = candidate_map.get('tree_pool')

    for zone, segment in outer_zones:
        if guard_candidate is not None:
            for center, tangent in _street_interval_centers(zone, segment, 5.0, 0.0):
                asset_list.append(_make_asset_record(len(asset_list) + 1, guard_candidate, center, rng, zone, tangent))
        if branch_outer and greenery_candidate is not None:
            for center, tangent in _street_interval_centers(zone, segment, 5.0, 0.5):
                asset_list.append(_make_asset_record(len(asset_list) + 1, greenery_candidate, center, rng, zone, tangent))
                greenery_points.append((center, tangent, zone))
        elif (not branch_outer) and inner_tree_candidate is not None:
            for center, tangent in _street_interval_centers(zone, segment, 5.0, 3.0):
                asset_list.append(_make_asset_record(len(asset_list) + 1, inner_tree_candidate, center, rng, zone, tangent))
                greenery_points.append((center, tangent, zone))
        if light_candidate is not None:
            for center, tangent in _street_interval_centers(zone, segment, 5.0, 0.25):
                asset_list.append(_make_asset_record(len(asset_list) + 1, light_candidate, center, rng, zone, tangent))

    trash_candidate = candidate_map.get('trash_bin')
    hydrant_candidate = candidate_map.get('fire_hydrant')
    if greenery_points:
        first_center, first_tangent, first_zone = greenery_points[0]
        last_center, last_tangent, last_zone = greenery_points[-1]
        if trash_candidate is not None:
            trash_center = (
                first_center[0] + first_tangent[0] * 0.75,
                first_center[1] + first_tangent[1] * 0.75,
                first_center[2],
            )
            asset_list.append(_make_asset_record(len(asset_list) + 1, trash_candidate, trash_center, rng, first_zone, first_tangent))
        if hydrant_candidate is not None:
            hydrant_center = (
                last_center[0] - last_tangent[0] * 0.75,
                last_center[1] - last_tangent[1] * 0.75,
                last_center[2],
            )
            asset_list.append(_make_asset_record(len(asset_list) + 1, hydrant_candidate, hydrant_center, rng, last_zone, last_tangent))

    _place_single_dynamic_asset(asset_list, candidate_map.get('food_cart'), dynamic_zones, rng, 0.50)
    return asset_list


def _place_city_street_roofless_assets(
    public_space_geometry: Dict[str, Any],
    public_space_segments: List[Dict[str, Any]],
    static_zones: List[Dict[str, Any]],
    asset_candidates_list: List[Dict[str, Any]],
    rng: random.Random,
) -> List[Dict[str, Any]]:
    candidate_map = {candidate['asset_candidates_name']: candidate for candidate in asset_candidates_list}
    asset_list: List[Dict[str, Any]] = []
    outer_zones, inner_zones = _street_boundary_zones(static_zones, public_space_segments)

    guard_candidate = candidate_map.get('guard_rail')
    if guard_candidate is not None:
        for zone, segment in outer_zones:
            for center, tangent in _street_interval_centers(zone, segment, 5.0, 0.0):
                asset_list.append(_make_asset_record(len(asset_list) + 1, guard_candidate, center, rng, zone, tangent))

    branch_outer = rng.random() <= 0.5
    greenery_candidate_name = 'tree_pool' if rng.random() <= 0.5 else 'flower_box'
    greenery_candidate = candidate_map.get(greenery_candidate_name)
    tree_candidate = candidate_map.get('tree_pool')
    street_light_candidate = candidate_map.get('street_light')

    if branch_outer and greenery_candidate is not None:
        for zone, segment in outer_zones:
            greenery_points = _street_interval_centers(zone, segment, 5.0, 0.5)
            for center, tangent in greenery_points:
                asset_list.append(_make_asset_record(len(asset_list) + 1, greenery_candidate, center, rng, zone, tangent))
            if street_light_candidate is not None and len(greenery_points) >= 2:
                for (start_center, tangent), (end_center, _) in zip(greenery_points, greenery_points[1:]):
                    light_center = (
                        (start_center[0] + end_center[0]) * 0.5,
                        (start_center[1] + end_center[1]) * 0.5,
                        start_center[2],
                    )
                    min_margin = max(_asset_dimensions(street_light_candidate)) * 0.5
                    if _point_inside_zone_bbox(light_center, zone, min_margin):
                        asset_list.append(_make_asset_record(len(asset_list) + 1, street_light_candidate, light_center, rng, zone, tangent))
    elif tree_candidate is not None:
        for zone in inner_zones:
            if _zone_short_side(zone) <= 0.0:
                continue
            for center, tangent in _street_inner_zone_centers(zone, 5.0):
                asset_list.append(_make_asset_record(len(asset_list) + 1, tree_candidate, center, rng, zone, tangent))

    return asset_list


def place_assets(*args, **kwargs):
    """Step 5: asset selection and simple center-point placement."""
    public_space_type = kwargs.get('public_space_type', '')
    public_space_geometry = kwargs.get('public_space_geometry', {})
    public_space_segments = kwargs.get('public_space_segments', []) or []
    dynamic_zones = kwargs.get('dynamic_zones', []) or []
    static_zones = kwargs.get('static_zones', []) or []
    asset_candidates_list = kwargs.get('asset_candidates_list') or EMBEDDED_ASSET_CANDIDATES

    if public_space_type == 'city_street_roof':
        return []

    rng_seed = f"step5|{public_space_type}|{public_space_geometry.get('coordinates', [])}|{len(dynamic_zones)}|{len(static_zones)}"
    rng = random.Random(rng_seed)
    zone_usage: Dict[str, int] = {}
    zone_occupancy: Dict[str, List[Tuple[float, float, float]]] = {}
    asset_list: List[Dict[str, Any]] = []
    fallback_center = _fallback_center(public_space_geometry)
    excluded_names: Set[str] = set()

    if public_space_type == 'city_street_roofless':
        asset_list.extend(
            _place_city_street_roofless_assets(
                public_space_geometry,
                public_space_segments,
                static_zones,
                asset_candidates_list,
                rng,
            )
        )
        excluded_names.update({'guard_rail', 'tree_pool', 'flower_box', 'street_light'})
    elif public_space_type == 'city_yard_roof':
        asset_list.extend(
            _place_city_yard_roof_assets(
                public_space_geometry,
                public_space_segments,
                dynamic_zones,
                static_zones,
                asset_candidates_list,
                rng,
            )
        )
        excluded_names.update({'long_bench', 'seat_group', 'vending_machine', 'food_cart'})
    elif public_space_type == 'city_yard_roofless':
        asset_list.extend(
            _place_city_yard_roofless_assets(
                public_space_geometry,
                public_space_segments,
                dynamic_zones,
                static_zones,
                asset_candidates_list,
                rng,
            )
        )
        excluded_names.update({
            'sculpture',
            'long_bench',
            'grass_patch',
            'seat_group',
            'tree_pool',
            'flower_box',
            'guard_rail',
            'street_light',
            'food_cart',
            'trash_bin',
            'fire_hydrant',
        })
    elif public_space_type == 'building_entrance':
        asset_list.extend(
            _place_building_entrance_assets(
                public_space_segments,
                static_zones,
                asset_candidates_list,
                rng,
            )
        )
        excluded_names.update({'vending_machine', 'smart_locker'})

    for asset in asset_list:
        zone_type = asset.get('zone_type')
        zone_id = asset.get('zone_id')
        if zone_type is None or zone_id is None:
            continue
        zone_occupancy.setdefault(f"{zone_type}:{zone_id}", []).append(tuple(asset['asset_location']))

    applicable_candidates = [
        candidate
        for candidate in asset_candidates_list
        if public_space_type in candidate.get('applicable_types', [])
        and _candidate_allowed(candidate, public_space_type, public_space_geometry, static_zones)
        and candidate.get('asset_candidates_name') not in excluded_names
    ]

    for candidate in applicable_candidates:
        probability = _candidate_probability(candidate, public_space_type)
        max_count = max(0, int(candidate.get('max_count', 1)))
        for _ in range(max_count):
            if rng.random() > probability:
                continue
            zone, center = _choose_zone_and_center_for_asset(
                candidate,
                public_space_type,
                dynamic_zones,
                static_zones,
                public_space_segments,
                zone_usage,
                zone_occupancy,
            )
            center = center or fallback_center
            asset_list.append(_make_asset_record(len(asset_list) + 1, candidate, center, rng, zone))
    return asset_list


def save_json(data: Dict[str, Any], path: str) -> None:
    with open(path, 'w', encoding='utf-8') as fh:
        import json
        json.dump(data, fh, ensure_ascii=False, indent=2)


def public_space_asset_configuration(
    public_space_type: str,
    public_space_geometry: Dict[str, Any],
    public_space_segments: List[Dict[str, Any]],
    ratio_dynamic_static: float,
    asset_candidates_list: Optional[List[Dict[str, Any]]] = None,
    cover_geometry: Optional[Dict[str, Any]] = None,
    asset_has_set: Optional[List[Dict[str, Any]]] = None,
    steps: Optional[List[int]] = None,
    output_json_path: Optional[str] = None,
    flow_pattern_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main entry for public space asset configuration.

    Parameters:
    - steps: list of step numbers to execute. If None, runs all steps.
    - output_json_path: if provided, write the augmented result JSON to this file.

    Returns a dictionary with updated segments and placeholders for outputs.
    """
    run_steps: Optional[Set[int]] = set(steps) if steps is not None else None

    # Basic validation (lightweight)
    if not isinstance(public_space_segments, list):
        raise ValueError('public_space_segments must be a list')

    effective_asset_candidates = asset_candidates_list or EMBEDDED_ASSET_CANDIDATES

    # Step 1: priority and walkable
    if run_steps is None or 1 in run_steps:
        set_priority_and_walkable(public_space_segments)

    # Initialize step outputs before creating result dict
    people_points = []
    flow_pattern = None
    walking_main_line = None
    walking_lines = []
    dynamic_zone_width = 0.0
    dynamic_area_target = 0.0
    dynamic_area_estimated = 0.0
    static_area_estimated = 0.0
    dynamic_zones = []
    static_zones = []
    asset_list = []

    # Step 2 - execute before building result
    if run_steps is None or 2 in run_steps:
        people_points = generate_people_points(
            public_space_geometry=public_space_geometry,
            public_space_segments=public_space_segments,
            asset_has_set=asset_has_set,
            public_space_type=public_space_type,
        )

    # Step 3
    if run_steps is None or 3 in run_steps:
        flow_result = generate_flow_lines(
            public_space_type=public_space_type,
            public_space_geometry=public_space_geometry,
            public_space_segments=public_space_segments,
            people_points=people_points,
            asset_has_set=asset_has_set,
            flow_pattern_override=flow_pattern_override,
        )
        flow_pattern = flow_result.get('flow_pattern')
        walking_main_line = flow_result.get('walking_main_line')
        walking_lines = flow_result.get('walking_lines', [])

    # Step 4
    if run_steps is None or 4 in run_steps:
        zone_result = generate_dynamic_static_zones(
            public_space_geometry=public_space_geometry,
            ratio_dynamic_static=ratio_dynamic_static,
            walking_lines=walking_lines,
        )
        dynamic_zone_width = zone_result.get('dynamic_zone_width', 0.0)
        dynamic_area_target = zone_result.get('dynamic_area_target', 0.0)
        dynamic_area_estimated = zone_result.get('dynamic_area_estimated', 0.0)
        static_area_estimated = zone_result.get('static_area_estimated', 0.0)
        dynamic_zones = zone_result.get('dynamic_zones', [])
        static_zones = zone_result.get('static_zones', [])

    # Step 5
    if run_steps is None or 5 in run_steps:
        asset_list = place_assets(
            public_space_type=public_space_type,
            public_space_geometry=public_space_geometry,
            public_space_segments=public_space_segments,
            dynamic_zones=dynamic_zones,
            static_zones=static_zones,
            asset_candidates_list=effective_asset_candidates,
        )

    # Base augmented result structure (after all steps)
    result = {
        'public_space_type': public_space_type,
        'public_space_geometry': public_space_geometry,
        'public_space_segments': public_space_segments,
        'ratio_dynamic_static': ratio_dynamic_static,
        'asset_candidates_list': effective_asset_candidates,
        'cover_geometry': cover_geometry,
        'asset_has_set': asset_has_set,
        'people_points': people_points,
        'flow_pattern': flow_pattern,
        'walking_lines': walking_lines,
        'dynamic_zone_width': dynamic_zone_width,
        'dynamic_area_target': dynamic_area_target,
        'dynamic_area_estimated': dynamic_area_estimated,
        'static_area_estimated': static_area_estimated,
        'dynamic_zones': dynamic_zones,
        'static_zones': static_zones,
        'asset_list': asset_list,
        'walking_main_line': walking_main_line,
        'status': 'completed_partial' if run_steps is not None else 'completed_all',
    }

    if output_json_path:
        save_json(result, output_json_path)

    return result


if __name__ == '__main__':
    import argparse
    import json
    import os

    parser = argparse.ArgumentParser(description='Run public_space_asset_configuration on a JSON file.')
    parser.add_argument('input_json', help='Path to the input JSON file')
    parser.add_argument('--steps', nargs='+', type=int, default=[1],
                        help='Steps to run (default: 1)')
    parser.add_argument('--output_json', help='Path to write augmented output JSON')
    parser.add_argument('--flow_pattern', choices=['cross', 'fishbone', 'ring', 'orthogonal'],
                        help='Force a step-3 flow pattern for testing')
    args = parser.parse_args()

    if not os.path.exists(args.input_json):
        raise SystemExit(f'Input JSON not found: {args.input_json}')

    with open(args.input_json, 'r', encoding='utf-8') as fh:
        data = json.load(fh)

    # Support both 'asset_has_set' and 'Asset_has_set' keys
    asset_has_set = data.get('asset_has_set') or data.get('Asset_has_set')
    
    out = public_space_asset_configuration(
        public_space_type=data.get('public_space_type', ''),
        public_space_geometry=data.get('public_space_geometry', {}),
        public_space_segments=data.get('public_space_segments', []),
        ratio_dynamic_static=data.get('ratio_dynamic_static', 0.5),
        asset_candidates_list=data.get('asset_candidates_list'),
        cover_geometry=data.get('cover_geometry'),
        asset_has_set=asset_has_set,
        steps=args.steps,
        output_json_path=args.output_json,
        flow_pattern_override=args.flow_pattern,
    )

    print('Output:')
    print(json.dumps(out, indent=2, ensure_ascii=False))
    if args.output_json:
        print(f'Augmented JSON written to: {args.output_json}')
