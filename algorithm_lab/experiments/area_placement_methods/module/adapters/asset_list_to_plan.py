"""Convert proto layout result to simworld.placement_output.v1."""

from __future__ import annotations

import re
from typing import Any

PLACEMENT_OUTPUT_SCHEMA = "simworld.placement_output.v1"
DEFAULT_PEDESTRIAN_TRIP_MIN_LENGTH_M = 15.0
DEFAULT_PEDESTRIAN_TRIP_TARGET_LENGTH_M = 25.0
DEFAULT_PEDESTRIAN_TRIP_MAX_LENGTH_M = 40.0
DEFAULT_PEDESTRIAN_NODE_MERGE_TOLERANCE_M = 0.10
DEFAULT_MAX_PEDESTRIAN_TRIPS_PER_REGION = 24
_EPS = 1e-6

# Resolved at runtime as UsdGeom.Cube when use_dummy_assets=True (no external USD).
DEFAULT_FALLBACK_ASSET_NAME = "isaac_builtin_placeholder"
# city_street_roof intentionally produces zero assets in proto step 5.
_TYPES_WITHOUT_FALLBACK = frozenset({"city_street_roof"})


def _region_slug(region_id: str) -> str:
    name = str(region_id or "region").rstrip("/").split("/")[-1]
    prefix = "placeholder_area_publicspace_"
    if name.startswith(prefix):
        name = name[len(prefix) :]
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_")
    return slug[:48] or "region"


def _usd_safe_placement_token(token: str) -> str:
    """USD prim path elements must not start with a digit."""
    cleaned = str(token or "").strip()
    if cleaned and cleaned[0].isdigit():
        return f"ps_{cleaned}"
    return cleaned or "placement"


def _placement_id(asset_id: Any, index: int, *, region_id: str = "") -> str:
    if asset_id is not None:
        base = f"asset_{asset_id:04d}" if isinstance(asset_id, int) else f"asset_{asset_id}"
    else:
        base = f"asset_{index:04d}"
    slug = _region_slug(region_id)
    if slug and slug != "region":
        return _usd_safe_placement_token(f"{slug}_{base}")
    return _usd_safe_placement_token(base)


def _centroid_from_geometry(geometry: dict[str, Any] | None) -> list[float]:
    """Average of polygon/line coordinates; used when asset_list is empty."""
    coords = (geometry or {}).get("coordinates") or []
    points: list[list[float]] = []
    for item in coords:
        if not isinstance(item, (list, tuple)):
            continue
        if len(item) >= 3:
            points.append([float(item[0]), float(item[1]), float(item[2])])
        elif len(item) >= 2:
            points.append([float(item[0]), float(item[1]), 0.0])
    if not points:
        return [0.0, 0.0, 0.0]
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    if not points:
        return [0.0, 0.0, 0.0]
    count = float(len(points))
    return [
        sum(p[0] for p in points) / count,
        sum(p[1] for p in points) / count,
        sum(p[2] for p in points) / count,
    ]


def _point3(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        z_value = value[2] if len(value) >= 3 else 0.0
        return [float(value[0]), float(value[1]), float(z_value)]
    except (TypeError, ValueError):
        return None


def _same_point(
    a: list[float] | tuple[float, float, float],
    b: list[float] | tuple[float, float, float],
) -> bool:
    return all(abs(float(a[i]) - float(b[i])) <= 1e-6 for i in range(3))


def _line_coordinates(line: Any) -> list[list[float]]:
    if isinstance(line, dict):
        geometry = line.get("geometry")
        if isinstance(geometry, dict):
            raw_coords = geometry.get("coordinates") or []
        else:
            raw_coords = line.get("coordinates") or []
    else:
        raw_coords = []

    coords: list[list[float]] = []
    for item in raw_coords:
        point = _point3(item)
        if point is None:
            continue
        if coords and _same_point(coords[-1], point):
            continue
        coords.append(point)
    return coords


def _route_length(vertices: list[list[float]]) -> float:
    length = 0.0
    for index in range(1, len(vertices)):
        a = vertices[index - 1]
        b = vertices[index]
        length += (
            (b[0] - a[0]) ** 2
            + (b[1] - a[1]) ** 2
            + (b[2] - a[2]) ** 2
        ) ** 0.5
    return length


def _distance(
    a: list[float] | tuple[float, float, float],
    b: list[float] | tuple[float, float, float],
) -> float:
    return (
        (float(b[0]) - float(a[0])) ** 2
        + (float(b[1]) - float(a[1])) ** 2
        + (float(b[2]) - float(a[2])) ** 2
    ) ** 0.5


def _lerp3(
    a: list[float] | tuple[float, float, float],
    b: list[float] | tuple[float, float, float],
    t: float,
) -> list[float]:
    return [
        float(a[0]) + (float(b[0]) - float(a[0])) * t,
        float(a[1]) + (float(b[1]) - float(a[1])) * t,
        float(a[2]) + (float(b[2]) - float(a[2])) * t,
    ]


def _dedupe_sorted_values(values: list[float]) -> list[float]:
    result: list[float] = []
    for value in sorted(max(0.0, min(1.0, float(item))) for item in values):
        if not result or abs(result[-1] - value) > 1e-6:
            result.append(value)
    return result


def _segment_intersection_params(
    a: list[float],
    b: list[float],
    c: list[float],
    d: list[float],
) -> tuple[float, float] | None:
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    cx, cy = float(c[0]), float(c[1])
    dx, dy = float(d[0]), float(d[1])
    rx, ry = bx - ax, by - ay
    sx, sy = dx - cx, dy - cy
    denominator = rx * sy - ry * sx
    if abs(denominator) <= 1e-9:
        return None
    qx, qy = cx - ax, cy - ay
    t = (qx * sy - qy * sx) / denominator
    u = (qx * ry - qy * rx) / denominator
    if -1e-6 <= t <= 1.0 + 1e-6 and -1e-6 <= u <= 1.0 + 1e-6:
        return (max(0.0, min(1.0, t)), max(0.0, min(1.0, u)))
    return None


def extract_pedestrian_walkable_lines_from_layout_result(
    layout_result: dict[str, Any],
    *,
    region_id: str,
) -> list[dict[str, Any]]:
    """Convert proto walking_lines into walkable line debug records."""
    walkable_lines: list[dict[str, Any]] = []
    slug = _region_slug(region_id)
    flow_pattern = layout_result.get("flow_pattern")

    for index, line in enumerate(layout_result.get("walking_lines") or [], start=1):
        if not isinstance(line, dict):
            continue
        vertices = _line_coordinates(line)
        if len(vertices) < 2:
            continue

        raw_line_id = line.get("line_id")
        line_token = str(raw_line_id or f"{index:03d}")
        length = line.get("length")
        try:
            length_value = float(length) if length is not None else _route_length(vertices)
        except (TypeError, ValueError):
            length_value = _route_length(vertices)

        metadata = {
            "source": "public_space_layout",
            "source_region_id": region_id,
            "flow_pattern": line.get("pattern") or flow_pattern,
            "line_id": raw_line_id,
            "line_role": line.get("line_role"),
            "length": length_value,
        }
        metadata = {
            key: value
            for key, value in metadata.items()
            if value not in (None, "")
        }
        line_record_id = _usd_safe_placement_token(
            f"walkable_line_{slug}_{line_token}"
        )
        walkable_lines.append(
            {
                "line_id": line_record_id,
                "vertices": vertices,
                "raw_name": line_record_id,
                "category": "walkable_line",
                "index": line_token,
                "metadata": metadata,
            }
        )

    return walkable_lines


def _split_walkable_segments(
    walkable_lines: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for line_index, line in enumerate(walkable_lines):
        vertices = line.get("vertices") or []
        for vertex_index in range(1, len(vertices)):
            start = vertices[vertex_index - 1]
            end = vertices[vertex_index]
            if _distance(start, end) <= _EPS:
                continue
            segments.append(
                {
                    "start": list(start),
                    "end": list(end),
                    "breaks": [0.0, 1.0],
                    "line_index": line_index,
                    "line_id": line.get("line_id") or line.get("raw_name") or "",
                }
            )

    for left_index, left in enumerate(segments):
        for right in segments[left_index + 1 :]:
            hit = _segment_intersection_params(
                left["start"],
                left["end"],
                right["start"],
                right["end"],
            )
            if hit is None:
                continue
            left["breaks"].append(hit[0])
            right["breaks"].append(hit[1])
    return segments


def _node_key(point: list[float], tolerance: float) -> tuple[int, int, int]:
    tolerance = max(1e-6, float(tolerance))
    return (
        round(float(point[0]) / tolerance),
        round(float(point[1]) / tolerance),
        round(float(point[2]) / tolerance),
    )


def _graph_from_walkable_lines(
    walkable_lines: list[dict[str, Any]],
    *,
    node_merge_tolerance_m: float,
) -> dict[str, Any]:
    segments = _split_walkable_segments(walkable_lines)
    nodes: list[list[float]] = []
    node_by_key: dict[tuple[int, int, int], int] = {}
    edges: dict[tuple[int, int], dict[str, Any]] = {}
    adjacency: dict[int, dict[int, float]] = {}

    def node_id(point: list[float]) -> int:
        key = _node_key(point, node_merge_tolerance_m)
        existing = node_by_key.get(key)
        if existing is not None:
            return existing
        new_id = len(nodes)
        nodes.append(point)
        node_by_key[key] = new_id
        adjacency[new_id] = {}
        return new_id

    for segment in segments:
        breaks = _dedupe_sorted_values(segment["breaks"])
        for index in range(1, len(breaks)):
            start_t = breaks[index - 1]
            end_t = breaks[index]
            if end_t - start_t <= 1e-6:
                continue
            start = _lerp3(segment["start"], segment["end"], start_t)
            end = _lerp3(segment["start"], segment["end"], end_t)
            length = _distance(start, end)
            if length <= _EPS:
                continue
            a = node_id(start)
            b = node_id(end)
            if a == b:
                continue
            edge_key = (min(a, b), max(a, b))
            if edge_key in edges and edges[edge_key]["length"] <= length:
                continue
            edges[edge_key] = {
                "a": edge_key[0],
                "b": edge_key[1],
                "length": length,
                "line_id": segment.get("line_id", ""),
            }
            adjacency[a][b] = length
            adjacency[b][a] = length

    return {
        "nodes": nodes,
        "edges": list(edges.values()),
        "adjacency": adjacency,
    }


def _component_node_ids(adjacency: dict[int, dict[int, float]]) -> list[list[int]]:
    remaining = set(adjacency)
    components: list[list[int]] = []
    while remaining:
        start = min(remaining)
        stack = [start]
        component: list[int] = []
        remaining.remove(start)
        while stack:
            node = stack.pop()
            component.append(node)
            for neighbor in sorted(adjacency[node]):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
        components.append(sorted(component))
    return components


def _component_edge_length(
    component: list[int],
    edges: list[dict[str, Any]],
) -> float:
    component_set = set(component)
    return sum(
        float(edge["length"])
        for edge in edges
        if edge["a"] in component_set and edge["b"] in component_set
    )


def _shortest_paths_from(
    start: int,
    component: list[int],
    adjacency: dict[int, dict[int, float]],
) -> tuple[dict[int, float], dict[int, int]]:
    component_set = set(component)
    distances = {node: float("inf") for node in component}
    previous: dict[int, int] = {}
    distances[start] = 0.0
    unvisited = set(component)
    while unvisited:
        current = min(unvisited, key=lambda node: (distances[node], node))
        unvisited.remove(current)
        if distances[current] == float("inf"):
            break
        for neighbor, weight in adjacency[current].items():
            if neighbor not in component_set or neighbor not in unvisited:
                continue
            candidate = distances[current] + float(weight)
            if candidate + 1e-9 < distances[neighbor]:
                distances[neighbor] = candidate
                previous[neighbor] = current
    return distances, previous


def _reconstruct_path(previous: dict[int, int], start: int, end: int) -> list[int]:
    path = [end]
    while path[-1] != start:
        parent = previous.get(path[-1])
        if parent is None:
            return []
        path.append(parent)
    return list(reversed(path))


def _truncate_path_vertices(
    path: list[int],
    nodes: list[list[float]],
    adjacency: dict[int, dict[int, float]],
    target_length: float,
) -> list[list[float]]:
    vertices = [list(nodes[path[0]])]
    remaining = float(target_length)
    for index in range(1, len(path)):
        start_id = path[index - 1]
        end_id = path[index]
        edge_length = float(adjacency[start_id][end_id])
        if remaining >= edge_length - 1e-6:
            vertices.append(list(nodes[end_id]))
            remaining -= edge_length
            continue
        if remaining > 1e-6:
            t = remaining / edge_length
            vertices.append(_lerp3(nodes[start_id], nodes[end_id], t))
        break
    return vertices


def _route_key(vertices: list[list[float]]) -> tuple[tuple[int, int, int], ...]:
    return tuple(_node_key(vertex, 0.01) for vertex in vertices)


def generate_pedestrian_trips_from_walkable_lines(
    walkable_lines: list[dict[str, Any]],
    *,
    region_id: str,
    min_trip_length_m: float = DEFAULT_PEDESTRIAN_TRIP_MIN_LENGTH_M,
    target_trip_length_m: float = DEFAULT_PEDESTRIAN_TRIP_TARGET_LENGTH_M,
    max_trip_length_m: float = DEFAULT_PEDESTRIAN_TRIP_MAX_LENGTH_M,
    node_merge_tolerance_m: float = DEFAULT_PEDESTRIAN_NODE_MERGE_TOLERANCE_M,
    max_trips_per_region: int = DEFAULT_MAX_PEDESTRIAN_TRIPS_PER_REGION,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Generate deterministic pedestrian trips from a walkable line graph."""
    min_trip_length_m = max(0.0, float(min_trip_length_m))
    max_trip_length_m = max(min_trip_length_m, float(max_trip_length_m))
    target_trip_length_m = max(
        min_trip_length_m,
        min(max_trip_length_m, float(target_trip_length_m)),
    )
    graph = _graph_from_walkable_lines(
        walkable_lines,
        node_merge_tolerance_m=node_merge_tolerance_m,
    )
    nodes = graph["nodes"]
    edges = graph["edges"]
    adjacency = graph["adjacency"]
    components = _component_node_ids(adjacency)
    trips: list[dict[str, Any]] = []
    skipped_short_components: list[dict[str, Any]] = []
    seen: set[tuple[tuple[int, int, int], ...]] = set()
    slug = _region_slug(region_id)

    for component_index, component in enumerate(components, start=1):
        component_length = _component_edge_length(component, edges)
        if component_length + 1e-6 < min_trip_length_m:
            skipped_short_components.append(
                {
                    "component_index": component_index,
                    "node_count": len(component),
                    "edge_length": component_length,
                    "reason": "component_shorter_than_min_trip_length",
                }
            )
            continue

        leaf_nodes = [
            node
            for node in component
            if len(adjacency.get(node, {})) == 1
        ]
        start_nodes = leaf_nodes or component
        start_nodes = sorted(
            start_nodes,
            key=lambda node: (nodes[node][0], nodes[node][1], node),
        )

        for start in start_nodes:
            if len(trips) >= max(0, int(max_trips_per_region)):
                break
            distances, previous = _shortest_paths_from(start, component, adjacency)
            reachable = [
                node
                for node, distance in distances.items()
                if node != start and distance < float("inf")
            ]
            in_range = [
                node
                for node in reachable
                if min_trip_length_m <= distances[node] <= max_trip_length_m
            ]
            if in_range:
                end = min(
                    in_range,
                    key=lambda node: (
                        abs(distances[node] - target_trip_length_m),
                        distances[node],
                        nodes[node][0],
                        nodes[node][1],
                        node,
                    ),
                )
                target_length = distances[end]
            else:
                farther = [node for node in reachable if distances[node] > max_trip_length_m]
                if not farther:
                    continue
                end = min(
                    farther,
                    key=lambda node: (
                        abs(distances[node] - target_trip_length_m),
                        distances[node],
                        nodes[node][0],
                        nodes[node][1],
                        node,
                    ),
                )
                target_length = target_trip_length_m
            path = _reconstruct_path(previous, start, end)
            if len(path) < 2:
                continue
            vertices = _truncate_path_vertices(path, nodes, adjacency, target_length)
            if len(vertices) < 2:
                continue
            length = _route_length(vertices)
            if length + 1e-6 < min_trip_length_m:
                continue
            if length > max_trip_length_m + 1e-6:
                vertices = _truncate_path_vertices(path, nodes, adjacency, max_trip_length_m)
                length = _route_length(vertices)
            key = _route_key(vertices)
            reverse_key = tuple(reversed(key))
            if key in seen or reverse_key in seen:
                continue
            seen.add(key)
            route_token = f"{len(trips) + 1:03d}"
            route_id = _usd_safe_placement_token(f"pedestrian_trip_{slug}_{route_token}")
            trips.append(
                {
                    "route_id": route_id,
                    "vertices": vertices,
                    "raw_name": route_id,
                    "category": "route",
                    "index": route_token,
                    "metadata": {
                        "source": "public_space_trip_generator",
                        "source_region_id": region_id,
                        "route_generation": "walkable_graph_trip",
                        "line_role": "trip",
                        "length": length,
                        "component_index": component_index,
                        "target_length": target_trip_length_m,
                        "min_length": min_trip_length_m,
                        "max_length": max_trip_length_m,
                        "source_walkable_line_count": len(walkable_lines),
                    },
                }
            )

    debug = {
        "walkable_line_count": len(walkable_lines),
        "generated_trip_count": len(trips),
        "graph_node_count": len(nodes),
        "graph_edge_count": len(edges),
        "component_count": len(components),
        "skipped_short_component_count": len(skipped_short_components),
        "skipped_short_components": skipped_short_components,
        "trip_config": {
            "min_trip_length_m": min_trip_length_m,
            "target_trip_length_m": target_trip_length_m,
            "max_trip_length_m": max_trip_length_m,
            "node_merge_tolerance_m": float(node_merge_tolerance_m),
            "max_trips_per_region": int(max_trips_per_region),
        },
    }
    return trips, debug


def extract_pedestrian_routes_from_layout_result(
    layout_result: dict[str, Any],
    *,
    region_id: str,
    min_trip_length_m: float = DEFAULT_PEDESTRIAN_TRIP_MIN_LENGTH_M,
    target_trip_length_m: float = DEFAULT_PEDESTRIAN_TRIP_TARGET_LENGTH_M,
    max_trip_length_m: float = DEFAULT_PEDESTRIAN_TRIP_MAX_LENGTH_M,
    node_merge_tolerance_m: float = DEFAULT_PEDESTRIAN_NODE_MERGE_TOLERANCE_M,
    max_trips_per_region: int = DEFAULT_MAX_PEDESTRIAN_TRIPS_PER_REGION,
) -> list[dict[str, Any]]:
    walkable_lines = extract_pedestrian_walkable_lines_from_layout_result(
        layout_result,
        region_id=region_id,
    )
    trips, _debug = generate_pedestrian_trips_from_walkable_lines(
        walkable_lines,
        region_id=region_id,
        min_trip_length_m=min_trip_length_m,
        target_trip_length_m=target_trip_length_m,
        max_trip_length_m=max_trip_length_m,
        node_merge_tolerance_m=node_merge_tolerance_m,
        max_trips_per_region=max_trips_per_region,
    )
    return trips


def _fallback_placement(layout_result: dict[str, Any], *, region_id: str = "") -> dict[str, Any]:
    position = _centroid_from_geometry(layout_result.get("public_space_geometry"))
    return {
        "placement_id": _placement_id(None, 0, region_id=region_id) if region_id else "fallback_0001",
        "asset_name": DEFAULT_FALLBACK_ASSET_NAME,
        "position": position,
        "orientation": [1.0, 0.0, 0.0],
        "zone_type": "fallback",
        "zone_id": None,
        "geometry": None,
        "asset_url": None,
    }


def layout_result_to_placement_output(
    layout_result: dict[str, Any],
    *,
    region_id: str,
    layout_steps: list[int] | None = None,
    inject_fallback_when_empty: bool = True,
    pedestrian_trip_min_length_m: float = DEFAULT_PEDESTRIAN_TRIP_MIN_LENGTH_M,
    pedestrian_trip_target_length_m: float = DEFAULT_PEDESTRIAN_TRIP_TARGET_LENGTH_M,
    pedestrian_trip_max_length_m: float = DEFAULT_PEDESTRIAN_TRIP_MAX_LENGTH_M,
    pedestrian_node_merge_tolerance_m: float = DEFAULT_PEDESTRIAN_NODE_MERGE_TOLERANCE_M,
    max_pedestrian_trips_per_region: int = DEFAULT_MAX_PEDESTRIAN_TRIPS_PER_REGION,
) -> dict[str, Any]:
    asset_list = layout_result.get("asset_list") or []
    placements = []
    warnings = list(layout_result.get("warnings") or [])
    pedestrian_walkable_lines = extract_pedestrian_walkable_lines_from_layout_result(
        layout_result,
        region_id=region_id,
    )
    pedestrian_routes, pedestrian_route_debug = generate_pedestrian_trips_from_walkable_lines(
        pedestrian_walkable_lines,
        region_id=region_id,
        min_trip_length_m=pedestrian_trip_min_length_m,
        target_trip_length_m=pedestrian_trip_target_length_m,
        max_trip_length_m=pedestrian_trip_max_length_m,
        node_merge_tolerance_m=pedestrian_node_merge_tolerance_m,
        max_trips_per_region=max_pedestrian_trips_per_region,
    )
    dynamic_zones = list(layout_result.get("dynamic_zones") or [])
    static_zones = list(layout_result.get("static_zones") or [])

    for index, item in enumerate(asset_list):
        if not isinstance(item, dict):
            continue
        placements.append(
            {
                "placement_id": _placement_id(
                    item.get("asset_id"),
                    index,
                    region_id=region_id,
                ),
                "asset_name": item.get("asset_candidates_name", ""),
                "position": list(item.get("asset_location") or []),
                "orientation": list(item.get("asset_orientation") or []),
                "zone_type": item.get("zone_type"),
                "zone_id": item.get("zone_id"),
                "geometry": item.get("geometry"),
                "asset_url": item.get("asset_URL") or item.get("asset_url"),
            }
        )

    public_space_type = str(layout_result.get("public_space_type") or "")
    used_fallback_placement = False
    if (
        not placements
        and inject_fallback_when_empty
        and public_space_type not in _TYPES_WITHOUT_FALLBACK
    ):
        placements.append(_fallback_placement(layout_result, region_id=region_id))
        used_fallback_placement = True
        warnings.append(
            "asset_list was empty; injected "
            f"{DEFAULT_FALLBACK_ASSET_NAME} at public_space_geometry centroid "
            "(executor renders varied debug geometry when assets are unmapped)."
        )

    return {
        "schema_version": PLACEMENT_OUTPUT_SCHEMA,
        "region_id": region_id,
        "public_space_type": public_space_type,
        "layout_steps": layout_steps or [1, 2, 3, 4, 5],
        "placements": placements,
        "pedestrian_walkable_lines": pedestrian_walkable_lines,
        "pedestrian_routes": pedestrian_routes,
        "pedestrian_route_debug": pedestrian_route_debug,
        "dynamic_zones": dynamic_zones,
        "static_zones": static_zones,
        "warnings": warnings,
        "debug": {
            "flow_pattern": layout_result.get("flow_pattern"),
            "pedestrian_walkable_line_count": len(pedestrian_walkable_lines),
            "pedestrian_route_count": len(pedestrian_routes),
            "pedestrian_route_skipped_short_component_count": pedestrian_route_debug.get(
                "skipped_short_component_count",
                0,
            ),
            "dynamic_zone_count": len(dynamic_zones),
            "static_zone_count": len(static_zones),
            "used_fallback_placement": used_fallback_placement,
        },
    }
