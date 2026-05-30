from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .dynamic import DynamicActorPlan, DynamicLanePlan, DynamicScenePlan

Vec3 = tuple[float, float, float]


@dataclass
class TrafficConfig:
    stop_at_end: bool = True


@dataclass
class LaneRecord:
    lane_id: str
    centerline: list[Vec3]
    width_m: float | None = None


@dataclass
class VehicleAgentState:
    actor_id: str
    route_id: str
    lane_ids: list[str]
    length_m: float
    width_m: float
    path: list[Vec3]
    position: Vec3
    velocity: Vec3 = (0.0, 0.0, 0.0)
    distance_m: float = 0.0
    spawn_time_s: float = 0.0
    target_speed_mps: float = 4.0
    max_speed_mps: float = 4.0
    finished: bool = False


def validate_vehicle_actor(
    actor: DynamicActorPlan,
    known_lane_ids: set[str],
) -> list[str]:
    missing: list[str] = []
    if actor.actor_type != "vehicle":
        return ["actor_type!=vehicle"]

    if actor.route_plan is None:
        missing.append("route_plan")
    else:
        if not actor.route_plan.route_id:
            missing.append("route_plan.route_id")
        lane_ids = actor.route_plan.lane_ids
        if lane_ids and any(lane_id not in known_lane_ids for lane_id in lane_ids):
            missing.append("known route_plan.lane_ids")
        waypoints = actor.route_plan.waypoints or actor.route
        if len(waypoints) < 2:
            missing.append("route_plan.waypoints")

    if not actor.route_id:
        missing.append("route_id")
    if actor.shape.length_m is None:
        missing.append("shape.length_m")
    if actor.shape.width_m is None:
        missing.append("shape.width_m")
    if actor.speed_profile is None:
        missing.append("speed_profile")
    return missing


def _lane_records(lanes: list[DynamicLanePlan]) -> dict[str, LaneRecord]:
    records: dict[str, LaneRecord] = {}
    for lane in lanes:
        if not lane.lane_id:
            continue
        centerline = list(lane.centerline) if lane.centerline else list(lane.polygon)
        records[lane.lane_id] = LaneRecord(
            lane_id=lane.lane_id,
            centerline=centerline,
            width_m=lane.width_m,
        )
    return records


def _path_for_actor(actor: DynamicActorPlan, lanes: dict[str, LaneRecord]) -> list[Vec3]:
    if actor.route_plan is not None and actor.route_plan.lane_ids:
        lane = lanes.get(actor.route_plan.lane_ids[0])
        if lane is not None and len(lane.centerline) >= 2:
            return list(lane.centerline)

    if actor.route_plan is not None and actor.route_plan.waypoints:
        return list(actor.route_plan.waypoints)
    return list(actor.route)


def _path_length(path: list[Vec3]) -> float:
    total = 0.0
    for index in range(len(path) - 1):
        total += _distance(path[index], path[index + 1])
    return total


def _distance(a: Vec3, b: Vec3) -> float:
    return math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 + (b[2] - a[2]) ** 2)


def _pose_at_distance(path: list[Vec3], distance: float) -> tuple[Vec3, float]:
    if len(path) < 2:
        start = path[0] if path else (0.0, 0.0, 0.0)
        return start, 0.0

    remaining = max(0.0, distance)
    for index in range(len(path) - 1):
        start = path[index]
        end = path[index + 1]
        segment_length = _distance(start, end)
        if remaining <= segment_length or index == len(path) - 2:
            t = 0.0 if segment_length < 1e-8 else remaining / segment_length
            position = (
                start[0] + (end[0] - start[0]) * t,
                start[1] + (end[1] - start[1]) * t,
                start[2] + (end[2] - start[2]) * t,
            )
            yaw = math.atan2(end[1] - start[1], end[0] - start[0])
            return position, yaw
        remaining -= segment_length

    end = path[-1]
    prev = path[-2]
    yaw = math.atan2(end[1] - prev[1], end[0] - prev[0])
    return end, yaw


def build_vehicle_states_from_plan(
    plan: DynamicScenePlan,
    warnings: list[str] | None = None,
) -> list[VehicleAgentState]:
    if warnings is None:
        warnings = []

    lanes = _lane_records(plan.lanes)
    known_lane_ids = set(lanes)
    states: list[VehicleAgentState] = []

    for actor in plan.actors:
        if actor.actor_type != "vehicle":
            continue

        missing = validate_vehicle_actor(actor, known_lane_ids)
        if missing:
            warnings.append(f"Skip actor {actor.actor_id}: missing {missing}")
            continue

        assert actor.route_plan is not None
        assert actor.speed_profile is not None
        assert actor.shape.length_m is not None
        assert actor.shape.width_m is not None

        path = _path_for_actor(actor, lanes)
        if len(path) < 2:
            warnings.append(
                f"Skip actor {actor.actor_id}: path has fewer than 2 point(s)."
            )
            continue

        states.append(
            VehicleAgentState(
                actor_id=actor.actor_id,
                route_id=actor.route_id,
                lane_ids=list(actor.route_plan.lane_ids),
                length_m=float(actor.shape.length_m),
                width_m=float(actor.shape.width_m),
                path=path,
                position=path[0],
                spawn_time_s=float(actor.spawn_time_s),
                target_speed_mps=float(actor.speed_profile.target_speed_mps),
                max_speed_mps=float(
                    actor.speed_profile.max_speed_mps
                    if actor.speed_profile.max_speed_mps is not None
                    else actor.speed_profile.target_speed_mps
                ),
            )
        )
    return states


def step_vehicle_agents(
    agents: list[VehicleAgentState],
    traffic_config: TrafficConfig,
    dt_s: float,
    sim_time_s: float,
) -> None:
    if dt_s <= 0.0:
        return

    for agent in agents:
        total_length = _path_length(agent.path)
        if sim_time_s < agent.spawn_time_s:
            agent.position = agent.path[0]
            agent.velocity = (0.0, 0.0, 0.0)
            agent.distance_m = 0.0
            continue

        if agent.finished:
            continue

        travel_time = sim_time_s - agent.spawn_time_s
        agent.distance_m = travel_time * agent.target_speed_mps
        if traffic_config.stop_at_end and agent.distance_m >= total_length:
            agent.distance_m = total_length
            agent.finished = True

        position, yaw = _pose_at_distance(agent.path, agent.distance_m)
        agent.position = position
        if agent.finished:
            agent.velocity = (0.0, 0.0, 0.0)
        else:
            speed = min(agent.max_speed_mps, agent.target_speed_mps)
            agent.velocity = (speed * math.cos(yaw), speed * math.sin(yaw), 0.0)


def simulate_vehicle_trajectory(
    agents: list[VehicleAgentState],
    traffic_config: TrafficConfig,
    dt_s: float,
    duration_s: float,
) -> dict[str, Any]:
    frames_by_actor = {agent.actor_id: [] for agent in agents}
    steps = max(1, int(math.ceil(duration_s / dt_s)))

    for step in range(steps + 1):
        t_s = min(duration_s, step * dt_s)
        if step > 0:
            step_vehicle_agents(agents, traffic_config, dt_s, t_s)

        for agent in agents:
            if t_s < agent.spawn_time_s:
                frames_by_actor[agent.actor_id].append(
                    _frame_record(t_s, agent.path[0], (0.0, 0.0, 0.0))
                )
            else:
                yaw = (
                    math.atan2(agent.velocity[1], agent.velocity[0])
                    if math.hypot(agent.velocity[0], agent.velocity[1]) > 1e-6
                    else 0.0
                )
                frames_by_actor[agent.actor_id].append(
                    _frame_record(t_s, agent.position, agent.velocity, yaw)
                )

    return {
        "actors": [
            {
                "actor_id": agent.actor_id,
                "route_id": agent.route_id,
                "lane_ids": agent.lane_ids,
                "frames": frames_by_actor[agent.actor_id],
            }
            for agent in agents
        ]
    }


def _frame_record(
    t_s: float,
    position: Vec3,
    velocity: Vec3,
    yaw_rad: float | None = None,
) -> dict[str, Any]:
    if yaw_rad is None:
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
