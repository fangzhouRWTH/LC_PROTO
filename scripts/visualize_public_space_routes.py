#!/usr/bin/env python3
"""Render generated pedestrian trips and raw walkable lines as standalone HTML/SVG."""

from __future__ import annotations

import argparse
import html
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "simworld"))

from engine import area_placement_bridge  # noqa: E402
from engine.demo_pedestrian_scenarios import apply_demo_people_scenario_from_file  # noqa: E402

DEFAULT_OUTPUT = REPO_ROOT / "outputs" / "public_space_routes" / "pedestrian_routes.html"
DEFAULT_STEPS = [1, 2, 3, 4, 5]
DEFAULT_MIN_TRIP_LENGTH_M = 15.0
DEFAULT_TARGET_TRIP_LENGTH_M = 25.0
DEFAULT_MAX_TRIP_LENGTH_M = 40.0
DEFAULT_NODE_MERGE_TOLERANCE_M = 0.10
DEFAULT_MAX_TRIPS_PER_REGION = 24
REGION_COLORS = (
    "#2563eb",
    "#dc2626",
    "#16a34a",
    "#9333ea",
    "#ea580c",
    "#0891b2",
    "#be123c",
    "#4f46e5",
    "#65a30d",
    "#c026d3",
)
ROLE_COLORS = {
    "main": "#e11d48",
    "cross": "#2563eb",
    "secondary": "#16a34a",
    "trip": "#4f46e5",
    "route": "#4f46e5",
}
STATUS_COLORS = {
    "ok": "#2563eb",
    "short": "#dc2626",
    "long": "#d97706",
}


@dataclass(frozen=True)
class RouteRecord:
    route_id: str
    region_id: str
    line_role: str
    flow_pattern: str
    line_id: str
    length_m: float
    vertices: list[tuple[float, float, float]]
    status: str
    offset_m: float | None = None
    scenario: str = ""


@dataclass(frozen=True)
class WalkableLineRecord:
    line_id: str
    region_id: str
    line_role: str
    flow_pattern: str
    length_m: float
    vertices: list[tuple[float, float, float]]


@dataclass(frozen=True)
class Bounds2D:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return max(1e-6, self.max_x - self.min_x)

    @property
    def height(self) -> float:
        return max(1e-6, self.max_y - self.min_y)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visualize generated pedestrian trips without launching Isaac Sim.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--region-input-json",
        type=Path,
        help="Region input JSON file or directory to run through area_placement_methods.",
    )
    source.add_argument(
        "--placement-plan-json",
        type=Path,
        help="Existing simworld.placement_output.v1 JSON containing pedestrian_routes.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"HTML output path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--write-plan-json",
        type=Path,
        default=None,
        help="Optional path to save the generated/loaded placement plan JSON.",
    )
    parser.add_argument(
        "--demo-people-config",
        type=Path,
        default=None,
        help="Optional demo-only people scenario config JSON to postprocess routes.",
    )
    parser.add_argument(
        "--demo-people-scenario",
        default=None,
        help="Scenario name from --demo-people-config, e.g. people_1, people_3, people_6.",
    )
    parser.add_argument(
        "--steps",
        default=",".join(str(value) for value in DEFAULT_STEPS),
        help="Comma-separated layout steps when using --region-input-json.",
    )
    parser.add_argument("--min-trip-length", type=float, default=DEFAULT_MIN_TRIP_LENGTH_M)
    parser.add_argument("--target-trip-length", type=float, default=DEFAULT_TARGET_TRIP_LENGTH_M)
    parser.add_argument("--max-trip-length", type=float, default=DEFAULT_MAX_TRIP_LENGTH_M)
    parser.add_argument(
        "--node-merge-tolerance",
        type=float,
        default=DEFAULT_NODE_MERGE_TOLERANCE_M,
    )
    parser.add_argument(
        "--max-trips-per-region",
        type=int,
        default=DEFAULT_MAX_TRIPS_PER_REGION,
    )
    parser.add_argument(
        "--max-routes",
        type=int,
        default=0,
        help="Limit rendered generated trips. 0 renders all trips.",
    )
    parser.add_argument(
        "--region",
        action="append",
        default=[],
        help="Only render records whose source_region_id contains this value. Repeatable.",
    )
    parser.add_argument(
        "--color-by",
        choices=("region", "role", "status"),
        default="region",
        help="Generated trip coloring mode.",
    )
    parser.add_argument(
        "--labels",
        choices=("none", "id", "region"),
        default="none",
        help="Generated trip label mode.",
    )
    parser.add_argument(
        "--show-walkable-lines",
        action="store_true",
        help="Draw raw walking_lines as dashed gray walkable-line context.",
    )
    parser.add_argument(
        "--show-zones",
        action="store_true",
        help="Draw dynamic/static zones as faint context layers.",
    )
    parser.add_argument("--width", type=int, default=1400)
    parser.add_argument("--height", type=int, default=900)
    return parser.parse_args(argv)


def load_plan_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.placement_plan_json is not None:
        with args.placement_plan_json.expanduser().open(encoding="utf-8") as handle:
            plan = json.load(handle)
    else:
        steps = parse_steps(args.steps)
        plan = area_placement_bridge.build_combined_placement_plan(
            args.region_input_json,
            steps=steps,
            pedestrian_trip_min_length_m=float(args.min_trip_length),
            pedestrian_trip_target_length_m=float(args.target_trip_length),
            pedestrian_trip_max_length_m=float(args.max_trip_length),
            pedestrian_node_merge_tolerance_m=float(args.node_merge_tolerance),
            max_pedestrian_trips_per_region=int(args.max_trips_per_region),
        )

    if args.demo_people_config is not None:
        plan = apply_demo_people_scenario_from_file(
            plan,
            args.demo_people_config.expanduser(),
            scenario_name=args.demo_people_scenario,
        )
    return plan


def parse_steps(value: str | None) -> list[int]:
    if value is None or str(value).strip() == "":
        return list(DEFAULT_STEPS)
    steps: list[int] = []
    for item in str(value).split(","):
        item = item.strip()
        if item:
            steps.append(int(item))
    return steps or list(DEFAULT_STEPS)


def _plan_trip_config(plan: dict[str, Any]) -> dict[str, float]:
    debug = plan.get("pedestrian_route_debug")
    if isinstance(debug, dict):
        regions = debug.get("regions")
        first_region = regions[0] if isinstance(regions, list) and regions else debug
        config = first_region.get("trip_config") if isinstance(first_region, dict) else None
        if isinstance(config, dict):
            return {
                "min": float(config.get("min_trip_length_m", DEFAULT_MIN_TRIP_LENGTH_M)),
                "target": float(config.get("target_trip_length_m", DEFAULT_TARGET_TRIP_LENGTH_M)),
                "max": float(config.get("max_trip_length_m", DEFAULT_MAX_TRIP_LENGTH_M)),
            }
    return {
        "min": DEFAULT_MIN_TRIP_LENGTH_M,
        "target": DEFAULT_TARGET_TRIP_LENGTH_M,
        "max": DEFAULT_MAX_TRIP_LENGTH_M,
    }


def route_records_from_plan(
    plan: dict[str, Any],
    *,
    max_routes: int = 0,
    region_filters: list[str] | None = None,
) -> list[RouteRecord]:
    filters = [item.lower() for item in region_filters or [] if item]
    config = _plan_trip_config(plan)
    records: list[RouteRecord] = []

    for item in plan.get("pedestrian_routes") or []:
        if not isinstance(item, dict):
            continue
        vertices = route_vertices(item)
        if len(vertices) < 2:
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        region_id = str(metadata.get("source_region_id") or plan.get("region_id") or "")
        if filters and not any(filter_value in region_id.lower() for filter_value in filters):
            continue
        length_m = record_length(item, vertices)
        route_id = str(item.get("route_id") or item.get("raw_name") or f"route_{len(records) + 1}")
        records.append(
            RouteRecord(
                route_id=route_id,
                region_id=region_id,
                line_role=str(metadata.get("line_role") or item.get("category") or "route"),
                flow_pattern=str(metadata.get("flow_pattern") or ""),
                line_id=str(metadata.get("line_id") or item.get("index") or ""),
                length_m=length_m,
                vertices=vertices,
                status=route_status(length_m, config),
                offset_m=_metadata_float_or_none(metadata.get("offset_m")),
                scenario=str(metadata.get("scenario") or ""),
            )
        )
        if max_routes > 0 and len(records) >= max_routes:
            break

    return records


def walkable_line_records_from_plan(
    plan: dict[str, Any],
    *,
    region_filters: list[str] | None = None,
) -> list[WalkableLineRecord]:
    filters = [item.lower() for item in region_filters or [] if item]
    records: list[WalkableLineRecord] = []
    for item in plan.get("pedestrian_walkable_lines") or []:
        if not isinstance(item, dict):
            continue
        vertices = route_vertices(item)
        if len(vertices) < 2:
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        region_id = str(metadata.get("source_region_id") or plan.get("region_id") or "")
        if filters and not any(filter_value in region_id.lower() for filter_value in filters):
            continue
        records.append(
            WalkableLineRecord(
                line_id=str(item.get("line_id") or item.get("raw_name") or "walkable_line"),
                region_id=region_id,
                line_role=str(metadata.get("line_role") or item.get("category") or ""),
                flow_pattern=str(metadata.get("flow_pattern") or ""),
                length_m=record_length(item, vertices),
                vertices=vertices,
            )
        )
    return records


def route_vertices(route: dict[str, Any]) -> list[tuple[float, float, float]]:
    raw_vertices = route.get("vertices") or route.get("waypoints") or []
    vertices: list[tuple[float, float, float]] = []
    for value in raw_vertices:
        point = point3(value)
        if point is None:
            continue
        if vertices and same_point(vertices[-1], point):
            continue
        vertices.append(point)
    return vertices


def point3(value: Any) -> tuple[float, float, float] | None:
    if isinstance(value, dict):
        if "position" in value:
            value = value.get("position")
        elif all(axis in value for axis in ("x", "y")):
            return (
                float(value["x"]),
                float(value["y"]),
                float(value.get("z", 0.0)),
            )
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        z_value = value[2] if len(value) >= 3 else 0.0
        return (float(value[0]), float(value[1]), float(z_value))
    except (TypeError, ValueError):
        return None


def same_point(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> bool:
    return all(abs(left[index] - right[index]) <= 1e-6 for index in range(3))


def record_length(item: dict[str, Any], vertices: list[tuple[float, float, float]]) -> float:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    try:
        return float(metadata.get("length"))
    except (TypeError, ValueError):
        return route_length(vertices)


def route_length(vertices: list[tuple[float, float, float]]) -> float:
    length = 0.0
    for index in range(1, len(vertices)):
        a = vertices[index - 1]
        b = vertices[index]
        length += math.sqrt(
            (b[0] - a[0]) ** 2
            + (b[1] - a[1]) ** 2
            + (b[2] - a[2]) ** 2
        )
    return length


def _metadata_float_or_none(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def route_status(length_m: float, config: dict[str, float]) -> str:
    if length_m < float(config["min"]) - 1e-6:
        return "short"
    if length_m > float(config["max"]) + 1e-6:
        return "long"
    return "ok"


def render_route_visualization_html(
    plan: dict[str, Any],
    *,
    width: int = 1400,
    height: int = 900,
    max_routes: int = 0,
    region_filters: list[str] | None = None,
    color_by: str = "region",
    labels: str = "none",
    show_walkable_lines: bool = False,
    show_zones: bool = False,
) -> str:
    routes = route_records_from_plan(
        plan,
        max_routes=max_routes,
        region_filters=region_filters,
    )
    walkable_lines = walkable_line_records_from_plan(
        plan,
        region_filters=region_filters,
    )
    bounds = bounds_for_records(
        routes,
        walkable_lines if show_walkable_lines else [],
        plan if show_zones else None,
    )
    region_color_map = color_map_for_regions(routes, walkable_lines)
    svg = render_svg(
        routes,
        walkable_lines=walkable_lines,
        plan=plan,
        bounds=bounds,
        width=width,
        height=height,
        region_color_map=region_color_map,
        color_by=color_by,
        labels=labels,
        show_walkable_lines=show_walkable_lines,
        show_zones=show_zones,
    )
    return build_html(
        svg,
        plan=plan,
        routes=routes,
        walkable_lines=walkable_lines,
        bounds=bounds,
        color_by=color_by,
        show_walkable_lines=show_walkable_lines,
        show_zones=show_zones,
    )


def bounds_for_records(
    routes: list[RouteRecord],
    walkable_lines: list[WalkableLineRecord],
    plan_for_zones: dict[str, Any] | None = None,
) -> Bounds2D:
    xs: list[float] = []
    ys: list[float] = []
    for record in list(routes) + list(walkable_lines):
        for x, y, _z in record.vertices:
            xs.append(x)
            ys.append(y)
    if plan_for_zones is not None:
        for zone in (plan_for_zones.get("dynamic_zones") or []) + (
            plan_for_zones.get("static_zones") or []
        ):
            for x, y, _z in geometry_points(zone):
                xs.append(x)
                ys.append(y)
    if not xs or not ys:
        return Bounds2D(-1.0, -1.0, 1.0, 1.0)
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    if abs(max_x - min_x) < 1e-6:
        min_x -= 1.0
        max_x += 1.0
    if abs(max_y - min_y) < 1e-6:
        min_y -= 1.0
        max_y += 1.0
    pad_x = max(0.5, (max_x - min_x) * 0.04)
    pad_y = max(0.5, (max_y - min_y) * 0.04)
    return Bounds2D(min_x - pad_x, min_y - pad_y, max_x + pad_x, max_y + pad_y)


def color_map_for_regions(
    routes: list[RouteRecord],
    walkable_lines: list[WalkableLineRecord],
) -> dict[str, str]:
    regions = sorted(
        {route.region_id for route in routes}
        | {line.region_id for line in walkable_lines}
    )
    return {
        region: REGION_COLORS[index % len(REGION_COLORS)]
        for index, region in enumerate(regions)
    }


def render_svg(
    routes: list[RouteRecord],
    *,
    walkable_lines: list[WalkableLineRecord],
    plan: dict[str, Any],
    bounds: Bounds2D,
    width: int,
    height: int,
    region_color_map: dict[str, str],
    color_by: str,
    labels: str,
    show_walkable_lines: bool,
    show_zones: bool,
) -> str:
    pieces = [
        f'<svg class="route-map" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" '
        'aria-label="Pedestrian trip preview">',
        "<defs>",
        '<filter id="routeGlow" x="-20%" y="-20%" width="140%" height="140%">',
        '<feGaussianBlur stdDeviation="2.2" result="blur"/>',
        '<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        "</filter>",
        "</defs>",
        render_grid(bounds, width, height),
    ]
    if show_zones:
        pieces.append(render_zones(plan, bounds, width, height))
    if show_walkable_lines:
        pieces.append(render_walkable_lines(walkable_lines, bounds, width, height))
    pieces.append('<g class="routes">')
    for index, route in enumerate(routes, start=1):
        color = route_color(route, region_color_map, color_by)
        points = [project(point, bounds, width, height) for point in route.vertices]
        pieces.append(render_route_group(index, route, points, color, labels))
    pieces.append("</g>")
    pieces.append("</svg>")
    return "\n".join(pieces)


def render_grid(bounds: Bounds2D, width: int, height: int) -> str:
    step = nice_grid_step(max(bounds.width, bounds.height) / 8.0)
    if step <= 0:
        return ""
    min_x = math.floor(bounds.min_x / step) * step
    max_x = math.ceil(bounds.max_x / step) * step
    min_y = math.floor(bounds.min_y / step) * step
    max_y = math.ceil(bounds.max_y / step) * step
    pieces = ['<g class="grid">']
    value = min_x
    while value <= max_x + 1e-6:
        x1, y1 = project((value, bounds.min_y, 0.0), bounds, width, height)
        x2, y2 = project((value, bounds.max_y, 0.0), bounds, width, height)
        pieces.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}"/>')
        pieces.append(f'<text x="{x1 + 4:.2f}" y="{height - 12:.2f}">{value:g}</text>')
        value += step
    value = min_y
    while value <= max_y + 1e-6:
        x1, y1 = project((bounds.min_x, value, 0.0), bounds, width, height)
        x2, y2 = project((bounds.max_x, value, 0.0), bounds, width, height)
        pieces.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}"/>')
        pieces.append(f'<text x="12" y="{y1 - 4:.2f}">{value:g}</text>')
        value += step
    pieces.append("</g>")
    return "\n".join(pieces)


def nice_grid_step(value: float) -> float:
    if value <= 0:
        return 1.0
    exponent = math.floor(math.log10(value))
    base = 10 ** exponent
    fraction = value / base
    if fraction <= 1.5:
        nice = 1.0
    elif fraction <= 3.0:
        nice = 2.0
    elif fraction <= 7.0:
        nice = 5.0
    else:
        nice = 10.0
    return nice * base


def render_zones(
    plan: dict[str, Any],
    bounds: Bounds2D,
    width: int,
    height: int,
) -> str:
    pieces = ['<g class="zones">']
    for class_name, zones in (
        ("dynamic-zone", plan.get("dynamic_zones") or []),
        ("static-zone", plan.get("static_zones") or []),
    ):
        for zone in zones:
            points = [project(point, bounds, width, height) for point in geometry_points(zone)]
            if len(points) < 2:
                continue
            point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
            tag = "polygon" if len(points) >= 3 else "polyline"
            pieces.append(f'<{tag} class="{class_name}" points="{point_text}"/>')
    pieces.append("</g>")
    return "\n".join(pieces)


def render_walkable_lines(
    walkable_lines: list[WalkableLineRecord],
    bounds: Bounds2D,
    width: int,
    height: int,
) -> str:
    pieces = ['<g class="walkable-lines">']
    for line in walkable_lines:
        points = [project(point, bounds, width, height) for point in line.vertices]
        point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        title = html.escape(
            f"{line.line_id}\nregion: {line.region_id}\nrole: {line.line_role}"
            f"\nlength: {line.length_m:.2f} m"
        )
        pieces.append(
            f'<polyline class="walkable-line" points="{point_text}"><title>{title}</title></polyline>'
        )
    pieces.append("</g>")
    return "\n".join(pieces)


def geometry_points(value: dict[str, Any]) -> list[tuple[float, float, float]]:
    geometry = value.get("geometry") if isinstance(value, dict) else None
    raw_points = geometry.get("coordinates") if isinstance(geometry, dict) else []
    points: list[tuple[float, float, float]] = []
    for item in raw_points or []:
        point = point3(item)
        if point is not None:
            points.append(point)
    return points


def render_route_group(
    index: int,
    route: RouteRecord,
    points: list[tuple[float, float]],
    color: str,
    labels: str,
) -> str:
    point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    safe_id = html.escape(route.route_id)
    safe_region = html.escape(route.region_id)
    title = html.escape(
        f"{route.route_id}\nregion: {route.region_id}\nstatus: {route.status}"
        f"\nrole: {route.line_role}\nlength: {route.length_m:.2f} m"
        f"\nscenario: {route.scenario or '-'}\noffset: {_format_offset(route.offset_m)}"
    )
    start = points[0]
    end = points[-1]
    arrow = arrowhead(points, color)
    label = ""
    if labels != "none":
        label_text = route.route_id if labels == "id" else route.region_id
        label = (
            f'<text class="route-label" x="{end[0] + 6:.2f}" y="{end[1] - 6:.2f}">'
            f"{html.escape(label_text)}</text>"
        )
    waypoint_dots = "\n".join(
        f'<circle class="waypoint" cx="{x:.2f}" cy="{y:.2f}" r="2.5"/>'
        for x, y in points[1:-1]
    )
    return f"""
<g class="route route-status-{route.status}" data-route-index="{index}" data-route-id="{safe_id}" data-region="{safe_region}">
  <title>{title}</title>
  <polyline class="route-line route-shadow" points="{point_text}" style="stroke:{color}"/>
  <polyline class="route-line" points="{point_text}" style="stroke:{color}"/>
  {arrow}
  <circle class="start-point" cx="{start[0]:.2f}" cy="{start[1]:.2f}" r="6"/>
  <circle class="end-point" cx="{end[0]:.2f}" cy="{end[1]:.2f}" r="6"/>
  {waypoint_dots}
  {label}
</g>
""".strip()


def arrowhead(points: list[tuple[float, float]], color: str) -> str:
    if len(points) < 2:
        return ""
    start = points[-2]
    end = points[-1]
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return ""
    ux = dx / length
    uy = dy / length
    size = 14.0
    back_x = end[0] - ux * size
    back_y = end[1] - uy * size
    perp_x = -uy * size * 0.45
    perp_y = ux * size * 0.45
    points_text = (
        f"{end[0]:.2f},{end[1]:.2f} "
        f"{back_x + perp_x:.2f},{back_y + perp_y:.2f} "
        f"{back_x - perp_x:.2f},{back_y - perp_y:.2f}"
    )
    return f'<polygon class="arrowhead" points="{points_text}" style="fill:{color}"/>'


def route_color(
    route: RouteRecord,
    region_color_map: dict[str, str],
    color_by: str,
) -> str:
    if color_by == "status":
        return STATUS_COLORS.get(route.status, STATUS_COLORS["ok"])
    if color_by == "role":
        return ROLE_COLORS.get(route.line_role, ROLE_COLORS["route"])
    return region_color_map.get(route.region_id, REGION_COLORS[0])


def project(
    point: tuple[float, float, float],
    bounds: Bounds2D,
    width: int,
    height: int,
) -> tuple[float, float]:
    padding = 40.0
    usable_w = max(1.0, width - padding * 2.0)
    usable_h = max(1.0, height - padding * 2.0)
    scale = min(usable_w / bounds.width, usable_h / bounds.height)
    content_w = bounds.width * scale
    content_h = bounds.height * scale
    offset_x = padding + (usable_w - content_w) * 0.5
    offset_y = padding + (usable_h - content_h) * 0.5
    x = offset_x + (point[0] - bounds.min_x) * scale
    y = height - offset_y - (point[1] - bounds.min_y) * scale
    return (x, y)


def _route_lengths(routes: list[RouteRecord]) -> list[float]:
    return sorted(route.length_m for route in routes)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return (values[middle - 1] + values[middle]) * 0.5


def _route_debug_counts(plan: dict[str, Any]) -> dict[str, int]:
    debug = plan.get("pedestrian_route_debug")
    if not isinstance(debug, dict):
        return {"skipped_short_component_count": 0}
    return {
        "skipped_short_component_count": int(
            debug.get("skipped_short_component_count") or 0
        ),
        "component_count": int(debug.get("component_count") or 0),
        "graph_node_count": int(debug.get("graph_node_count") or 0),
        "graph_edge_count": int(debug.get("graph_edge_count") or 0),
    }


def build_html(
    svg: str,
    *,
    plan: dict[str, Any],
    routes: list[RouteRecord],
    walkable_lines: list[WalkableLineRecord],
    bounds: Bounds2D,
    color_by: str,
    show_walkable_lines: bool,
    show_zones: bool,
) -> str:
    route_rows = "\n".join(render_route_row(index, route) for index, route in enumerate(routes, 1))
    region_count = len({route.region_id for route in routes} | {line.region_id for line in walkable_lines})
    lengths = _route_lengths(routes)
    total_length = sum(lengths)
    source_files = plan.get("debug", {}).get("source_files") if isinstance(plan.get("debug"), dict) else None
    source_text = ", ".join(source_files or [str(plan.get("region_id") or "unknown")])
    warning_count = sum(1 for route in routes if route.status != "ok")
    debug_counts = _route_debug_counts(plan)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pedestrian Trip Preview</title>
  <style>
    :root {{
      color-scheme: light;
      --panel: #f8fafc;
      --line: #cbd5e1;
      --text: #0f172a;
      --muted: #64748b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background: #ffffff;
    }}
    .shell {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 380px;
      min-height: 100vh;
    }}
    .map-pane {{ padding: 16px; background: #ffffff; overflow: auto; }}
    .side-pane {{
      border-left: 1px solid var(--line);
      background: var(--panel);
      padding: 18px;
      overflow: auto;
      max-height: 100vh;
    }}
    h1 {{ font-size: 20px; margin: 0 0 12px; letter-spacing: 0; }}
    .summary {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin: 12px 0 16px;
    }}
    .metric {{
      border: 1px solid var(--line);
      background: #ffffff;
      border-radius: 6px;
      padding: 10px;
    }}
    .metric b {{ display: block; font-size: 18px; }}
    .metric span {{ color: var(--muted); font-size: 12px; }}
    .source {{
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
      margin-bottom: 14px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 6px;
      overflow: hidden;
    }}
    th, td {{
      padding: 6px 7px;
      border-bottom: 1px solid #e2e8f0;
      vertical-align: top;
      text-align: left;
    }}
    th {{ position: sticky; top: 0; background: #e2e8f0; z-index: 1; }}
    td.route-id {{ overflow-wrap: anywhere; max-width: 150px; }}
    .status-short td, .status-long td {{ background: #fff7ed; }}
    .route-map {{
      width: 100%;
      height: auto;
      min-width: 760px;
      border: 1px solid var(--line);
      background: #fbfdff;
      border-radius: 8px;
    }}
    .grid line {{ stroke: #e2e8f0; stroke-width: 1; }}
    .grid text {{ fill: #94a3b8; font-size: 11px; }}
    .dynamic-zone {{ fill: rgba(14, 165, 233, 0.08); stroke: rgba(14, 165, 233, 0.22); stroke-width: 1; }}
    .static-zone {{ fill: rgba(148, 163, 184, 0.08); stroke: rgba(100, 116, 139, 0.18); stroke-width: 1; }}
    .walkable-line {{
      fill: none;
      stroke: #64748b;
      stroke-width: 2;
      stroke-dasharray: 6 6;
      opacity: 0.42;
      stroke-linecap: round;
    }}
    .route-line {{ fill: none; stroke-width: 4; stroke-linecap: round; stroke-linejoin: round; }}
    .route-shadow {{ opacity: 0.16; stroke-width: 10; filter: url(#routeGlow); }}
    .route:hover .route-line {{ stroke-width: 7; }}
    .route-status-short .route-line {{ stroke-dasharray: 9 5; }}
    .route-status-long .route-line {{ stroke-dasharray: 3 4; }}
    .start-point {{ fill: #22c55e; stroke: #ffffff; stroke-width: 2; }}
    .end-point {{ fill: #ef4444; stroke: #ffffff; stroke-width: 2; }}
    .waypoint {{ fill: #ffffff; stroke: #475569; stroke-width: 1.2; }}
    .route-label {{ fill: #0f172a; font-size: 12px; paint-order: stroke; stroke: #ffffff; stroke-width: 3; }}
    .arrowhead {{ stroke: #ffffff; stroke-width: 1; }}
    @media (max-width: 980px) {{
      .shell {{ grid-template-columns: 1fr; }}
      .side-pane {{ border-left: 0; border-top: 1px solid var(--line); max-height: none; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="map-pane">
      {svg}
    </section>
    <aside class="side-pane">
      <h1>Pedestrian Trip Preview</h1>
      <div class="source">source: {html.escape(source_text)}</div>
      <div class="summary">
        <div class="metric"><b>{len(routes)}</b><span>generated trips</span></div>
        <div class="metric"><b>{len(walkable_lines)}</b><span>raw walkable lines</span></div>
        <div class="metric"><b>{region_count}</b><span>regions</span></div>
        <div class="metric"><b>{debug_counts.get('skipped_short_component_count', 0)}</b><span>skipped short components</span></div>
        <div class="metric"><b>{min(lengths) if lengths else 0:.1f}</b><span>min trip m</span></div>
        <div class="metric"><b>{_median(lengths):.1f}</b><span>median trip m</span></div>
        <div class="metric"><b>{max(lengths) if lengths else 0:.1f}</b><span>max trip m</span></div>
        <div class="metric"><b>{warning_count}</b><span>warnings</span></div>
      </div>
      <div class="source">
        bounds: x {bounds.min_x:.2f} to {bounds.max_x:.2f}, y {bounds.min_y:.2f} to {bounds.max_y:.2f};
        total trip length: {total_length:.1f}m; color: {html.escape(color_by)};
        walkable lines: {"shown" if show_walkable_lines else "hidden"}; zones: {"shown" if show_zones else "hidden"}
      </div>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>trip</th>
            <th>region</th>
            <th>status</th>
            <th>m</th>
            <th>offset</th>
          </tr>
        </thead>
        <tbody>
          {route_rows}
        </tbody>
      </table>
    </aside>
  </main>
</body>
</html>
"""


def _format_offset(offset_m: float | None) -> str:
    if offset_m is None:
        return "-"
    return f"{offset_m:.2f}m"


def render_route_row(index: int, route: RouteRecord) -> str:
    return (
        f'<tr class="status-{html.escape(route.status)}">'
        f"<td>{index}</td>"
        f'<td class="route-id">{html.escape(route.route_id)}</td>'
        f"<td>{html.escape(route.region_id)}</td>"
        f"<td>{html.escape(route.status)}</td>"
        f"<td>{route.length_m:.1f}</td>"
        f"<td>{html.escape(_format_offset(route.offset_m))}</td>"
        "</tr>"
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan = load_plan_from_args(args)
    if args.write_plan_json is not None:
        write_json(args.write_plan_json.expanduser(), plan)
    html_text = render_route_visualization_html(
        plan,
        width=max(320, int(args.width)),
        height=max(240, int(args.height)),
        max_routes=max(0, int(args.max_routes)),
        region_filters=list(args.region or []),
        color_by=args.color_by,
        labels=args.labels,
        show_walkable_lines=bool(args.show_walkable_lines),
        show_zones=bool(args.show_zones),
    )
    output = args.output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_text, encoding="utf-8")
    route_count = len(
        route_records_from_plan(
            plan,
            max_routes=max(0, int(args.max_routes)),
            region_filters=list(args.region or []),
        )
    )
    walkable_count = len(
        walkable_line_records_from_plan(
            plan,
            region_filters=list(args.region or []),
        )
    )
    print(f"Wrote pedestrian trip preview: {output}")
    print(f"Rendered generated trips: {route_count}")
    print(f"Rendered raw walkable lines: {walkable_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
