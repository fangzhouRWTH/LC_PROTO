from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .dynamic import DynamicActorPlan, DynamicScenePlan

Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]


@dataclass
class ObstacleContext:
    static_polygons_xy: list[list[Vec2]] = field(default_factory=list)
    agent_neighbor_radius_m: float = 4.0
    obstacle_influence_m: float = 0.8


@dataclass
class OrcaPedestrianPlannerConfig:
    separation_max_ratio: float = 0.55
    route_attraction_gain: float = 2.5
    route_attraction_max_mps: float = 1.0
    off_route_separation_decay_m: float = 1.5

DEFAULT_ORCA_PEDESTRIAN_PLANNER_CONFIG = OrcaPedestrianPlannerConfig()


@dataclass
class PedestrianAgentState:
    actor_id: str
    radius_m: float
    position: Vec3
    velocity: Vec3 = (0.0, 0.0, 0.0)
    waypoint_index: int = 0
    finished: bool = False
    spawn_time_s: float = 0.0
    target_speed_mps: float = 1.2
    max_speed_mps: float = 1.2
    waypoints: list[Vec3] = field(default_factory=list)
    route_mode: str = "once"


def validate_pedestrian_actor(actor: DynamicActorPlan) -> list[str]:
    missing: list[str] = []
    if actor.actor_type != "pedestrian":
        return ["actor_type!=pedestrian"]
    if actor.spawn_pose is None:
        missing.append("spawn_pose")
    if actor.goal_pose is None:
        missing.append("goal_pose")
    if actor.speed_profile is None:
        missing.append("speed_profile")
    if actor.shape.radius_m is None:
        missing.append("shape.radius_m")
    if actor.route_plan is None:
        missing.append("route_plan")
    elif actor.route_plan.route_type != "waypoints":
        missing.append("route_plan.route_type=waypoints")
    elif len(actor.route_plan.waypoints) < 2:
        missing.append("route_plan.waypoints")
    return missing


def _waypoints_for_actor(actor: DynamicActorPlan) -> list[Vec3]:
    if actor.route_plan is not None and actor.route_plan.waypoints:
        return list(actor.route_plan.waypoints)
    return list(actor.route)


def build_pedestrian_states_from_plan(
    plan: DynamicScenePlan,
    warnings: list[str] | None = None,
) -> list[PedestrianAgentState]:
    if warnings is None:
        warnings = []

    states: list[PedestrianAgentState] = []
    for actor in plan.actors:
        if actor.actor_type != "pedestrian":
            continue

        missing = validate_pedestrian_actor(actor)
        if missing:
            warnings.append(f"Skip actor {actor.actor_id}: missing {missing}")
            continue

        assert actor.spawn_pose is not None
        assert actor.speed_profile is not None
        assert actor.shape.radius_m is not None

        route_mode = "once"
        if actor.route_plan is not None and actor.route_plan.route_mode:
            route_mode = actor.route_plan.route_mode

        states.append(
            PedestrianAgentState(
                actor_id=actor.actor_id,
                radius_m=float(actor.shape.radius_m),
                position=tuple(actor.spawn_pose.position),
                spawn_time_s=float(actor.spawn_time_s),
                target_speed_mps=float(actor.speed_profile.target_speed_mps),
                max_speed_mps=float(
                    actor.speed_profile.max_speed_mps
                    if actor.speed_profile.max_speed_mps is not None
                    else actor.speed_profile.target_speed_mps
                ),
                waypoints=_waypoints_for_actor(actor),
                route_mode=route_mode,
            )
        )
    return states


def step_pedestrian_agents(
    agents: list[PedestrianAgentState],
    obstacle_context: ObstacleContext,
    dt_s: float,
    sim_time_s: float,
    planner_config: OrcaPedestrianPlannerConfig | None = None,
) -> None:
    if dt_s <= 0.0:
        return

    config = planner_config or DEFAULT_ORCA_PEDESTRIAN_PLANNER_CONFIG

    for agent in agents:
        if sim_time_s < agent.spawn_time_s:
            agent.position = agent.waypoints[0] if agent.waypoints else agent.position
            agent.velocity = (0.0, 0.0, 0.0)
            continue
        if agent.finished:
            continue

        pref_vx, pref_vy = _preferred_velocity(agent)
        _, off_route_m = _nearest_route_point(agent.waypoints, _vec2_xy(agent.position))
        sep_vx, sep_vy = _separation_velocity(
            agent,
            agents,
            obstacle_context.agent_neighbor_radius_m,
        )
        sep_vx, sep_vy = _scale_separation_by_off_route(
            sep_vx,
            sep_vy,
            off_route_m,
            config.off_route_separation_decay_m,
        )
        sep_vx, sep_vy = _cap_separation_velocity(
            sep_vx,
            sep_vy,
            pref_vx,
            pref_vy,
            config.separation_max_ratio,
        )
        route_vx, route_vy = _route_attraction_velocity(agent, config)
        obs_vx, obs_vy = _obstacle_repulsion(
            agent,
            obstacle_context.static_polygons_xy,
            obstacle_context.obstacle_influence_m,
        )
        vx, vy = _clamp_speed(
            pref_vx + sep_vx + route_vx + obs_vx,
            pref_vy + sep_vy + route_vy + obs_vy,
            agent.max_speed_mps,
        )
        agent.position = (
            agent.position[0] + vx * dt_s,
            agent.position[1] + vy * dt_s,
            agent.position[2],
        )
        agent.velocity = (vx, vy, 0.0)
        _advance_waypoint(agent)


def simulate_pedestrian_trajectory(
    agents: list[PedestrianAgentState],
    obstacle_context: ObstacleContext,
    dt_s: float,
    duration_s: float,
) -> dict[str, Any]:
    frames_by_actor: dict[str, list[dict[str, Any]]] = {
        agent.actor_id: [] for agent in agents
    }
    steps = max(1, int(math.ceil(duration_s / dt_s)))

    for step in range(steps + 1):
        t_s = min(duration_s, step * dt_s)
        if step > 0:
            step_pedestrian_agents(agents, obstacle_context, dt_s, t_s)

        for agent in agents:
            if t_s < agent.spawn_time_s:
                position = agent.waypoints[0] if agent.waypoints else agent.position
                frames_by_actor[agent.actor_id].append(
                    _frame_record(t_s, position, (0.0, 0.0, 0.0))
                )
            else:
                frames_by_actor[agent.actor_id].append(
                    _frame_record(t_s, agent.position, agent.velocity)
                )

    return {
        "actors": [
            {
                "actor_id": agent.actor_id,
                "radius_m": agent.radius_m,
                "frames": frames_by_actor[agent.actor_id],
            }
            for agent in agents
        ]
    }


def _vec2_xy(point: Vec3) -> Vec2:
    return (float(point[0]), float(point[1]))


def _distance_xy(a: Vec2, b: Vec2) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _normalize_xy(v: Vec2) -> Vec2:
    length = math.hypot(v[0], v[1])
    if length < 1e-8:
        return (0.0, 0.0)
    return (v[0] / length, v[1] / length)


def _clamp_speed(vx: float, vy: float, max_speed: float) -> tuple[float, float]:
    speed = math.hypot(vx, vy)
    if speed <= max_speed or speed < 1e-8:
        return vx, vy
    scale = max_speed / speed
    return vx * scale, vy * scale


def _preferred_velocity(agent: PedestrianAgentState) -> Vec2:
    if agent.finished or agent.waypoint_index >= len(agent.waypoints) - 1:
        return (0.0, 0.0)

    target = _vec2_xy(agent.waypoints[agent.waypoint_index + 1])
    current = _vec2_xy(agent.position)
    direction = _normalize_xy((target[0] - current[0], target[1] - current[1]))
    return (
        direction[0] * agent.target_speed_mps,
        direction[1] * agent.target_speed_mps,
    )


def _nearest_route_point(
    waypoints: list[Vec3],
    point: Vec2,
) -> tuple[Vec2, float]:
    if len(waypoints) < 2:
        return point, 0.0

    best_distance = float("inf")
    best_point = point
    for index in range(len(waypoints) - 1):
        start = _vec2_xy(waypoints[index])
        end = _vec2_xy(waypoints[index + 1])
        closest = _closest_point_on_segment(point, start, end)
        distance = _distance_xy(point, closest)
        if distance < best_distance:
            best_distance = distance
            best_point = closest
    return best_point, best_distance


def _route_attraction_velocity(
    agent: PedestrianAgentState,
    config: OrcaPedestrianPlannerConfig,
) -> Vec2:
    if len(agent.waypoints) < 2:
        return (0.0, 0.0)

    current = _vec2_xy(agent.position)
    nearest, off_route_m = _nearest_route_point(agent.waypoints, current)
    if off_route_m < 0.05:
        return (0.0, 0.0)

    direction = _normalize_xy((nearest[0] - current[0], nearest[1] - current[1]))
    speed = min(
        config.route_attraction_max_mps,
        config.route_attraction_gain * off_route_m,
    )
    return direction[0] * speed, direction[1] * speed


def _cap_separation_velocity(
    sep_vx: float,
    sep_vy: float,
    pref_vx: float,
    pref_vy: float,
    max_ratio: float,
) -> Vec2:
    pref_speed = math.hypot(pref_vx, pref_vy)
    max_sep_speed = max_ratio * max(pref_speed, 0.3)
    sep_speed = math.hypot(sep_vx, sep_vy)
    if sep_speed <= max_sep_speed or sep_speed < 1e-8:
        return sep_vx, sep_vy
    scale = max_sep_speed / sep_speed
    return sep_vx * scale, sep_vy * scale


def _scale_separation_by_off_route(
    sep_vx: float,
    sep_vy: float,
    off_route_m: float,
    decay_m: float,
) -> Vec2:
    if decay_m <= 1e-6:
        return sep_vx, sep_vy
    scale = 1.0 / (1.0 + off_route_m / decay_m)
    return sep_vx * scale, sep_vy * scale


def _separation_velocity(
    agent: PedestrianAgentState,
    others: list[PedestrianAgentState],
    neighbor_radius_m: float,
) -> Vec2:
    repulse_x = 0.0
    repulse_y = 0.0
    current = _vec2_xy(agent.position)

    for other in others:
        if other.actor_id == agent.actor_id or other.finished:
            continue

        other_xy = _vec2_xy(other.position)
        offset = (current[0] - other_xy[0], current[1] - other_xy[1])
        distance = math.hypot(offset[0], offset[1])
        min_sep = agent.radius_m + other.radius_m
        if distance < 1e-6 or distance > neighbor_radius_m:
            continue

        strength = (min_sep - distance) / max(min_sep, 1e-6)
        direction = _normalize_xy(offset)
        repulse_x += direction[0] * strength * agent.target_speed_mps
        repulse_y += direction[1] * strength * agent.target_speed_mps

    return repulse_x, repulse_y


def _obstacle_repulsion(
    agent: PedestrianAgentState,
    polygons: list[list[Vec2]],
    influence_m: float,
) -> Vec2:
    if not polygons:
        return (0.0, 0.0)

    current = _vec2_xy(agent.position)
    repulse_x = 0.0
    repulse_y = 0.0

    for polygon in polygons:
        if len(polygon) < 3:
            continue

        for index in range(len(polygon)):
            a = polygon[index]
            b = polygon[(index + 1) % len(polygon)]
            closest = _closest_point_on_segment(current, a, b)
            offset = (current[0] - closest[0], current[1] - closest[1])
            distance = math.hypot(offset[0], offset[1])
            clearance = agent.radius_m + influence_m
            if distance >= clearance or distance < 1e-6:
                continue

            strength = (clearance - distance) / clearance
            direction = _normalize_xy(offset)
            repulse_x += direction[0] * strength * agent.target_speed_mps
            repulse_y += direction[1] * strength * agent.target_speed_mps

    return repulse_x, repulse_y


def _closest_point_on_segment(point: Vec2, a: Vec2, b: Vec2) -> Vec2:
    ab = (b[0] - a[0], b[1] - a[1])
    ab_len_sq = ab[0] ** 2 + ab[1] ** 2
    if ab_len_sq < 1e-12:
        return a

    t = ((point[0] - a[0]) * ab[0] + (point[1] - a[1]) * ab[1]) / ab_len_sq
    t = max(0.0, min(1.0, t))
    return (a[0] + ab[0] * t, a[1] + ab[1] * t)


def _advance_waypoint(agent: PedestrianAgentState, waypoint_reach_m: float = 0.35) -> None:
    if agent.finished or agent.waypoint_index >= len(agent.waypoints) - 1:
        agent.finished = True
        return

    target = _vec2_xy(agent.waypoints[agent.waypoint_index + 1])
    current = _vec2_xy(agent.position)
    if _distance_xy(current, target) <= waypoint_reach_m:
        agent.waypoint_index += 1
        if agent.waypoint_index >= len(agent.waypoints) - 1:
            agent.position = agent.waypoints[-1]
            if agent.route_mode in {"once", "stop_at_end", "stop-at-end"}:
                agent.finished = True
                agent.velocity = (0.0, 0.0, 0.0)


def _frame_record(t_s: float, position: Vec3, velocity: Vec3) -> dict[str, Any]:
    yaw_rad = (
        math.atan2(velocity[1], velocity[0])
        if math.hypot(velocity[0], velocity[1]) > 1e-6
        else 0.0
    )
    return {
        "t_s": round(t_s, 6),
        "position": [round(position[0], 6), round(position[1], 6), round(position[2], 6)],
        "velocity": [round(velocity[0], 6), round(velocity[1], 6), round(velocity[2], 6)],
        "yaw_rad": round(yaw_rad, 6),
    }
