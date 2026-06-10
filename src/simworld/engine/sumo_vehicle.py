from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .dynamic import DynamicActorPlan, DynamicLanePlan, DynamicScenePlan

Vec3 = tuple[float, float, float]


@dataclass
class TrafficConfig:
    stop_at_end: bool = True
    min_vehicle_center_gap_m: float = 5.0
    smooth_turns: bool = True
    turn_radius_m: float = 6.0
    arc_sample_spacing_m: float = 0.75


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
    travel_distance_m: float = 0.0
    last_sim_time_s: float | None = None
    spawn_time_s: float = 0.0
    target_speed_mps: float = 4.0
    max_speed_mps: float = 4.0
    finished: bool = False
    route_mode: str = "once"


@dataclass
class _VehicleStepCandidate:
    agent: VehicleAgentState
    active: bool
    position: Vec3
    yaw_rad: float
    velocity: Vec3
    distance_m: float
    travel_distance_m: float
    last_sim_time_s: float | None
    finished: bool


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
        if len(waypoints) < 2 and not lane_ids:
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
    if actor.route_plan is not None and len(actor.route_plan.waypoints) >= 2:
        return list(actor.route_plan.waypoints)
    if len(actor.route) >= 2:
        return list(actor.route)

    if actor.route_plan is not None and actor.route_plan.lane_ids:
        lane = lanes.get(actor.route_plan.lane_ids[0])
        if lane is not None and len(lane.centerline) >= 2:
            return list(lane.centerline)

    return []


def smooth_vehicle_path(
    path: list[Vec3],
    traffic_config: TrafficConfig | None = None,
) -> list[Vec3]:
    config = traffic_config or TrafficConfig()
    if (
        not config.smooth_turns
        or len(path) < 3
        or config.turn_radius_m <= 0.0
        or config.arc_sample_spacing_m <= 0.0
    ):
        return list(path)

    smoothed: list[Vec3] = [path[0]]
    for index in range(1, len(path) - 1):
        corner_arc = _corner_arc_points(
            path[index - 1],
            path[index],
            path[index + 1],
            radius_m=float(config.turn_radius_m),
            sample_spacing_m=float(config.arc_sample_spacing_m),
        )
        if corner_arc is None:
            _append_unique_point(smoothed, path[index])
            continue

        for point in corner_arc:
            _append_unique_point(smoothed, point)

    _append_unique_point(smoothed, path[-1])
    return smoothed


def _corner_arc_points(
    prev: Vec3,
    corner: Vec3,
    nxt: Vec3,
    radius_m: float,
    sample_spacing_m: float,
) -> list[Vec3] | None:
    incoming = (corner[0] - prev[0], corner[1] - prev[1])
    outgoing = (nxt[0] - corner[0], nxt[1] - corner[1])
    incoming_length = math.hypot(incoming[0], incoming[1])
    outgoing_length = math.hypot(outgoing[0], outgoing[1])
    if incoming_length < 1e-6 or outgoing_length < 1e-6:
        return None

    incoming_dir = (incoming[0] / incoming_length, incoming[1] / incoming_length)
    outgoing_dir = (outgoing[0] / outgoing_length, outgoing[1] / outgoing_length)
    dot = _clamp(
        incoming_dir[0] * outgoing_dir[0] + incoming_dir[1] * outgoing_dir[1],
        -1.0,
        1.0,
    )
    turn_angle = math.acos(dot)
    if turn_angle < math.radians(8.0) or turn_angle > math.radians(170.0):
        return None

    tangent_distance = radius_m * math.tan(turn_angle * 0.5)
    if tangent_distance >= min(incoming_length, outgoing_length):
        return None

    turn_sign = 1.0 if _cross_z(incoming_dir, outgoing_dir) > 0.0 else -1.0
    start = (
        corner[0] - incoming_dir[0] * tangent_distance,
        corner[1] - incoming_dir[1] * tangent_distance,
        _lerp_scalar(corner[2], prev[2], tangent_distance / incoming_length),
    )
    end = (
        corner[0] + outgoing_dir[0] * tangent_distance,
        corner[1] + outgoing_dir[1] * tangent_distance,
        _lerp_scalar(corner[2], nxt[2], tangent_distance / outgoing_length),
    )

    normal = (-incoming_dir[1] * turn_sign, incoming_dir[0] * turn_sign)
    center = (
        start[0] + normal[0] * radius_m,
        start[1] + normal[1] * radius_m,
    )
    start_angle = math.atan2(start[1] - center[1], start[0] - center[0])
    end_angle = math.atan2(end[1] - center[1], end[0] - center[0])
    if turn_sign > 0.0 and end_angle <= start_angle:
        end_angle += math.tau
    elif turn_sign < 0.0 and end_angle >= start_angle:
        end_angle -= math.tau

    arc_angle = abs(end_angle - start_angle)
    sample_count = max(2, int(math.ceil((arc_angle * radius_m) / sample_spacing_m)))
    points: list[Vec3] = []
    for sample_index in range(sample_count + 1):
        if sample_index == 0:
            points.append(start)
            continue
        if sample_index == sample_count:
            points.append(end)
            continue
        t = sample_index / sample_count
        angle = start_angle + (end_angle - start_angle) * t
        z = _lerp_scalar(start[2], end[2], t)
        points.append((
            center[0] + math.cos(angle) * radius_m,
            center[1] + math.sin(angle) * radius_m,
            z,
        ))
    return points


def _append_unique_point(points: list[Vec3], point: Vec3) -> None:
    if points and _distance(points[-1], point) < 1e-6:
        return
    points.append(point)


def _cross_z(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _lerp_scalar(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


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


def _route_mode_for_actor(actor: DynamicActorPlan) -> str:
    if actor.route_plan is not None and actor.route_plan.route_mode:
        return str(actor.route_plan.route_mode)
    return "once"


def build_vehicle_states_from_plan(
    plan: DynamicScenePlan,
    warnings: list[str] | None = None,
    traffic_config: TrafficConfig | None = None,
) -> list[VehicleAgentState]:
    if warnings is None:
        warnings = []
    traffic_config = traffic_config or TrafficConfig()

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

        source_path = _path_for_actor(actor, lanes)
        path = smooth_vehicle_path(source_path, traffic_config)
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
                route_mode=_route_mode_for_actor(actor),
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

    candidates = [
        _build_step_candidate(agent, traffic_config, float(dt_s), float(sim_time_s))
        for agent in agents
    ]
    placed: list[_VehicleStepCandidate] = []

    for candidate in candidates:
        if candidate.active and _candidate_conflicts(candidate, placed, traffic_config):
            candidate = _hold_vehicle_candidate(candidate, float(sim_time_s))

        _apply_step_candidate(candidate)
        if candidate.active and not candidate.finished:
            placed.append(candidate)


def _build_step_candidate(
    agent: VehicleAgentState,
    traffic_config: TrafficConfig,
    dt_s: float,
    sim_time_s: float,
) -> _VehicleStepCandidate:
    if sim_time_s < agent.spawn_time_s:
        return _VehicleStepCandidate(
            agent=agent,
            active=False,
            position=agent.path[0],
            yaw_rad=0.0,
            velocity=(0.0, 0.0, 0.0),
            distance_m=0.0,
            travel_distance_m=0.0,
            last_sim_time_s=None,
            finished=False,
        )

    if agent.finished:
        position, yaw = _pose_at_distance(agent.path, agent.distance_m)
        return _VehicleStepCandidate(
            agent=agent,
            active=False,
            position=position,
            yaw_rad=yaw,
            velocity=(0.0, 0.0, 0.0),
            distance_m=agent.distance_m,
            travel_distance_m=agent.travel_distance_m,
            last_sim_time_s=agent.last_sim_time_s,
            finished=True,
        )

    total_length = _path_length(agent.path)
    active_dt = _active_dt(agent, dt_s, sim_time_s)
    desired_travel_distance = agent.travel_distance_m + active_dt * agent.target_speed_mps
    distance_m = _distance_along_path(
        desired_travel_distance,
        total_length,
        agent.route_mode,
    )
    finished = (
        traffic_config.stop_at_end
        and _is_stop_at_end_mode(agent.route_mode)
        and desired_travel_distance >= total_length
    )
    if finished:
        distance_m = total_length
        desired_travel_distance = total_length

    position, yaw = _pose_at_distance(agent.path, distance_m)
    speed = 0.0 if finished else min(agent.max_speed_mps, agent.target_speed_mps)
    return _VehicleStepCandidate(
        agent=agent,
        active=True,
        position=position,
        yaw_rad=yaw,
        velocity=(speed * math.cos(yaw), speed * math.sin(yaw), 0.0),
        distance_m=distance_m,
        travel_distance_m=desired_travel_distance,
        last_sim_time_s=sim_time_s,
        finished=finished,
    )


def _active_dt(agent: VehicleAgentState, dt_s: float, sim_time_s: float) -> float:
    if agent.last_sim_time_s is None:
        return max(0.0, sim_time_s - agent.spawn_time_s)
    return max(0.0, min(dt_s, sim_time_s - agent.last_sim_time_s))


def _candidate_conflicts(
    candidate: _VehicleStepCandidate,
    placed: list[_VehicleStepCandidate],
    traffic_config: TrafficConfig,
) -> bool:
    for other in placed:
        if not _vehicles_should_yield(candidate, other, traffic_config):
            continue
        return True
    return False


def _vehicles_should_yield(
    candidate: _VehicleStepCandidate,
    other: _VehicleStepCandidate,
    traffic_config: TrafficConfig,
) -> bool:
    distance = _distance(candidate.position, other.position)
    if distance >= _vehicle_center_gap(candidate.agent, other.agent, traffic_config):
        return False

    if _share_lane(candidate.agent, other.agent):
        return True

    # Different lanes can pass side-by-side. Treat near vehicles on crossing or
    # merging headings as intersection conflicts that require one vehicle to wait.
    return abs(_angle_delta(candidate.yaw_rad, other.yaw_rad)) > math.radians(25.0)


def _vehicle_center_gap(
    a: VehicleAgentState,
    b: VehicleAgentState,
    traffic_config: TrafficConfig,
) -> float:
    half_lengths = (a.length_m + b.length_m) * 0.5
    return max(float(traffic_config.min_vehicle_center_gap_m), half_lengths)


def _share_lane(a: VehicleAgentState, b: VehicleAgentState) -> bool:
    if a.route_id and a.route_id == b.route_id:
        return True
    return bool(set(a.lane_ids) & set(b.lane_ids))


def _angle_delta(a: float, b: float) -> float:
    delta = (a - b + math.pi) % (math.tau) - math.pi
    return delta


def _hold_vehicle_candidate(
    candidate: _VehicleStepCandidate,
    sim_time_s: float,
) -> _VehicleStepCandidate:
    position, yaw = _pose_at_distance(
        candidate.agent.path,
        candidate.agent.distance_m,
    )
    return _VehicleStepCandidate(
        agent=candidate.agent,
        active=True,
        position=position,
        yaw_rad=yaw,
        velocity=(0.0, 0.0, 0.0),
        distance_m=candidate.agent.distance_m,
        travel_distance_m=candidate.agent.travel_distance_m,
        last_sim_time_s=sim_time_s,
        finished=False,
    )


def _apply_step_candidate(candidate: _VehicleStepCandidate) -> None:
    agent = candidate.agent
    agent.position = candidate.position
    agent.velocity = candidate.velocity
    agent.distance_m = candidate.distance_m
    agent.travel_distance_m = candidate.travel_distance_m
    agent.last_sim_time_s = candidate.last_sim_time_s
    agent.finished = candidate.finished


def _distance_along_path(
    raw_distance: float,
    total_length: float,
    route_mode: str,
) -> float:
    if total_length < 1e-8:
        return 0.0

    mode = str(route_mode or "once").lower()
    if _is_stop_at_end_mode(mode):
        return min(raw_distance, total_length)
    if mode == "loop":
        return raw_distance % total_length
    if mode == "ping_pong":
        period = total_length * 2.0
        phase = raw_distance % period
        return phase if phase <= total_length else period - phase
    return min(raw_distance, total_length)


def _is_stop_at_end_mode(route_mode: str) -> bool:
    return str(route_mode or "").lower() in {"once", "stop_at_end", "stop-at-end"}


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
