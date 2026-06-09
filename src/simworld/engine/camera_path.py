"""Camera path planning from parsed scene placeholders (no Isaac imports)."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Sequence

from engine.public_space_quad import dedupe_points

Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class CameraPathPlan:
    path_id: str
    waypoints: tuple[Vec3, ...]
    source_prim_path: str = ""
    raw_name: str = ""
    index: str = ""
    route_mode: str = "loop"
    speed_mps: float = 2.0


@dataclass
class CameraPathScenePlan:
    paths: list[CameraPathPlan] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CameraPathPlanConfig:
    speed_mps: float = 2.0
    route_mode: str = "loop"
    max_paths: int = 16
    dedupe_epsilon_m: float = 0.05


def build_camera_path_plan(
    scene_stats: object,
    config: CameraPathPlanConfig | None = None,
) -> CameraPathScenePlan:
    if config is None:
        config = CameraPathPlanConfig()

    plan = CameraPathScenePlan()
    placeholders = list(getattr(scene_stats, "camera_paths", []) or [])
    if not placeholders:
        return plan

    limit = max(0, int(config.max_paths))
    for seq, placeholder in enumerate(placeholders[:limit]):
        waypoints = waypoints_from_placeholder(
            placeholder,
            dedupe_epsilon_m=float(config.dedupe_epsilon_m),
        )
        if len(waypoints) < 2:
            prim_path = str(getattr(placeholder, "prim_path", "") or "")
            plan.warnings.append(
                "Camera path placeholder has fewer than 2 waypoint(s): "
                f"{prim_path or seq + 1}"
            )
            continue

        index = str(getattr(placeholder, "index", "") or "")
        path_id = (
            f"camera_path_{index}"
            if index
            else f"camera_path_{seq + 1:03d}"
        )
        plan.paths.append(
            CameraPathPlan(
                path_id=path_id,
                waypoints=tuple(waypoints),
                source_prim_path=str(getattr(placeholder, "prim_path", "") or ""),
                raw_name=str(getattr(placeholder, "raw_name", "") or ""),
                index=index,
                route_mode=str(config.route_mode or "loop"),
                speed_mps=max(0.0, float(config.speed_mps)),
            )
        )

    if len(placeholders) > limit:
        plan.warnings.append(
            f"Camera path plan truncated to {limit} path(s) "
            f"from {len(placeholders)} placeholder(s)."
        )
    return plan


def waypoints_from_placeholder(
    placeholder: object,
    *,
    dedupe_epsilon_m: float = 0.05,
) -> list[Vec3]:
    raw_vertices = getattr(placeholder, "vertices", None) or []
    points = [_to_vec3(vertex) for vertex in raw_vertices]
    if not points:
        return []
    deduped = dedupe_points(points, tolerance=dedupe_epsilon_m)
    return [(float(p[0]), float(p[1]), float(p[2])) for p in deduped]


def position_along_path(
    waypoints: Sequence[Vec3],
    distance: float,
    *,
    route_mode: str = "loop",
) -> Vec3:
    """Return camera position on a polyline path (orientation not included)."""
    eye, _ = look_at_pose_along_path(
        waypoints,
        distance,
        route_mode=route_mode,
    )
    return eye


def look_at_pose_along_path(
    waypoints: Sequence[Vec3],
    distance: float,
    *,
    route_mode: str = "loop",
) -> tuple[Vec3, Vec3]:
    """Return camera eye position and look-at target on a polyline path."""
    if len(waypoints) < 2:
        point = waypoints[0] if waypoints else (0.0, 0.0, 0.0)
        return point, _offset_target(point, (1.0, 0.0, 0.0))

    segment_lengths = [
        _distance(waypoints[index], waypoints[index + 1])
        for index in range(len(waypoints) - 1)
    ]
    total_length = sum(segment_lengths)
    if total_length < 1e-8:
        return waypoints[0], waypoints[-1]

    travel = _distance_along_route(distance, total_length, route_mode)
    remaining = travel
    for index, segment_length in enumerate(segment_lengths):
        start = waypoints[index]
        end = waypoints[index + 1]
        if remaining <= segment_length or index == len(segment_lengths) - 1:
            t = 0.0 if segment_length < 1e-8 else remaining / segment_length
            eye = _lerp(start, end, t)
            return eye, end
        remaining -= segment_length

    return waypoints[-1], waypoints[-1]


def advance_path_distance(
    *,
    elapsed_s: float,
    speed_mps: float,
    dt: float,
) -> float:
    return max(0.0, float(elapsed_s) + max(0.0, float(dt))) * max(0.0, float(speed_mps))


def _distance_along_route(raw_distance: float, total_length: float, route_mode: str) -> float:
    if total_length < 1e-8:
        return 0.0
    mode = str(route_mode or "loop").strip().lower().replace("-", "_")
    if mode in {"once", "stop_at_end", "stopatend"}:
        return min(raw_distance, total_length)
    if mode == "ping_pong":
        period = total_length * 2.0
        phase = raw_distance % period
        return phase if phase <= total_length else period - phase
    return raw_distance % total_length


def _offset_target(eye: Vec3, direction: Vec3, distance_m: float = 1.0) -> Vec3:
    length = math.sqrt(direction[0] ** 2 + direction[1] ** 2 + direction[2] ** 2)
    if length < 1e-8:
        return (eye[0] + distance_m, eye[1], eye[2])
    scale = distance_m / length
    return (
        eye[0] + direction[0] * scale,
        eye[1] + direction[1] * scale,
        eye[2] + direction[2] * scale,
    )


def _lerp(a: Vec3, b: Vec3, t: float) -> Vec3:
    alpha = max(0.0, min(1.0, float(t)))
    return (
        a[0] + (b[0] - a[0]) * alpha,
        a[1] + (b[1] - a[1]) * alpha,
        a[2] + (b[2] - a[2]) * alpha,
    )


def _distance(a: Vec3, b: Vec3) -> float:
    return math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 + (b[2] - a[2]) ** 2)


def _to_vec3(value: object) -> Vec3:
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    position = getattr(value, "position", None)
    if isinstance(position, (list, tuple)) and len(position) >= 3:
        return (float(position[0]), float(position[1]), float(position[2]))
    raise TypeError(f"Cannot convert value to Vec3: {value!r}")
