from dataclasses import dataclass, field
from typing import Any

Vec3 = tuple[float, float, float]


@dataclass
class DynamicPose:
    position: Vec3
    yaw_rad: float | None = None


@dataclass
class DynamicRoutePlan:
    route_id: str = ""
    route_type: str = "waypoints"
    route_mode: str = "loop"
    waypoints: list[Vec3] = field(default_factory=list)
    lane_ids: list[str] = field(default_factory=list)
    source_prim_paths: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DynamicLanePlan:
    lane_id: str = ""
    polygon: list[Vec3] = field(default_factory=list)
    centerline: list[Vec3] = field(default_factory=list)
    width_m: float | None = None
    source_prim_paths: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DynamicSpeedProfile:
    target_speed_mps: float = 0.0
    max_speed_mps: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DynamicActorShape:
    radius_m: float | None = None
    length_m: float | None = None
    width_m: float | None = None
    height_m: float | None = None


@dataclass
class DynamicPlanConfig:
    max_pedestrian_actors: int = 1
    max_vehicle_actors: int = 1
    pedestrian_speed_mps: float = 1.2
    vehicle_speed_mps: float = 4.0
    default_spawn_time_s: float = 0.0
    pedestrian_radius_m: float = 0.35
    pedestrian_height_m: float = 1.7
    vehicle_length_m: float = 4.5
    vehicle_width_m: float = 1.8
    vehicle_height_m: float = 1.6
    default_route_mode: str = "loop"


@dataclass
class DynamicActorPlan:
    actor_id: str
    actor_type: str
    route: list[Vec3] = field(default_factory=list)
    speed_mps: float = 0.0
    spawn_time_s: float = 0.0
    source_prim_paths: list[str] = field(default_factory=list)
    despawn_time_s: float | None = None
    spawn_pose: DynamicPose | None = None
    goal_pose: DynamicPose | None = None
    route_plan: DynamicRoutePlan | None = None
    route_id: str = ""
    speed_profile: DynamicSpeedProfile | None = None
    shape: DynamicActorShape = field(default_factory=DynamicActorShape)
    asset_category: str = ""
    behavior_profile: str = "route_follow"
    controller_profile: str = "kinematic"
    animation_profile: str = ""
    collision_policy: str = "kinematic"
    backend_hints: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DynamicScenePlan:
    actors: list[DynamicActorPlan] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    lanes: list[DynamicLanePlan] = field(default_factory=list)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value)


def _get_stats_list(scene_stats: Any, name: str) -> list[Any]:
    return _as_list(getattr(scene_stats, name, []))


def _to_vec3(value: Any) -> Vec3:
    if value is None:
        raise ValueError("Missing position")

    if hasattr(value, "position"):
        value = value.position

    if len(value) < 3:
        raise ValueError(f"Position must have 3 values, got {value}")

    return (float(value[0]), float(value[1]), float(value[2]))


def _source_prim_path(value: Any) -> str | None:
    prim_path = getattr(value, "prim_path", "")
    if not prim_path:
        return None
    return str(prim_path)


def _compact_source_paths(*values: Any) -> list[str]:
    paths = []
    for value in values:
        path = _source_prim_path(value)
        if path and path not in paths:
            paths.append(path)
    return paths


def _copy_actor_shape(shape: DynamicActorShape) -> DynamicActorShape:
    return DynamicActorShape(
        radius_m=shape.radius_m,
        length_m=shape.length_m,
        width_m=shape.width_m,
        height_m=shape.height_m,
    )


def _actor_shape_for_type(
    actor_type: str,
    config: DynamicPlanConfig,
) -> DynamicActorShape:
    if actor_type == "vehicle":
        return DynamicActorShape(
            length_m=float(config.vehicle_length_m),
            width_m=float(config.vehicle_width_m),
            height_m=float(config.vehicle_height_m),
        )

    return DynamicActorShape(
        radius_m=float(config.pedestrian_radius_m),
        height_m=float(config.pedestrian_height_m),
    )


def _make_waypoint_route_plan(
    route_id: str,
    route: list[Vec3],
    source_prim_paths: list[str],
    metadata: dict[str, Any] | None = None,
    lane_ids: list[str] | None = None,
    route_mode: str = "loop",
) -> DynamicRoutePlan:
    return DynamicRoutePlan(
        route_id=route_id,
        route_type="waypoints",
        route_mode=str(route_mode or "loop"),
        waypoints=list(route),
        lane_ids=list(lane_ids or []),
        source_prim_paths=list(source_prim_paths),
        metadata=metadata or {},
    )


def _make_speed_profile(speed_mps: float) -> DynamicSpeedProfile:
    speed = float(speed_mps)
    return DynamicSpeedProfile(target_speed_mps=speed, max_speed_mps=speed)


def _route_waypoints(value: Any) -> list[Vec3]:
    vertices = getattr(value, "vertices", value)
    return [_to_vec3(vertex) for vertex in vertices]


def _placeholder_index(value: Any) -> str:
    index = getattr(value, "index", "")
    return str(index) if index else ""


def _find_by_index(values: list[Any], index: str) -> Any | None:
    if not index:
        return None

    for value in values:
        if _placeholder_index(value) == index:
            return value
    return None


def _spawn_goal_pairs(
    spawns: list[Any],
    goals: list[Any],
) -> list[tuple[Any, Any, str]]:
    spawn_by_index: dict[str, Any] = {}
    goal_by_index: dict[str, Any] = {}
    unindexed_spawns: list[Any] = []
    unindexed_goals: list[Any] = []

    for spawn in spawns:
        index = _placeholder_index(spawn)
        if index:
            spawn_by_index[index] = spawn
        else:
            unindexed_spawns.append(spawn)

    for goal in goals:
        index = _placeholder_index(goal)
        if index:
            goal_by_index[index] = goal
        else:
            unindexed_goals.append(goal)

    pairs: list[tuple[Any, Any, str]] = []
    for index in sorted(set(spawn_by_index) & set(goal_by_index)):
        pairs.append((spawn_by_index[index], goal_by_index[index], index))

    unindexed_count = min(len(unindexed_spawns), len(unindexed_goals))
    for index in range(unindexed_count):
        pairs.append((unindexed_spawns[index], unindexed_goals[index], ""))

    return pairs


def _spawn_goal_metadata(placeholder_index: str) -> dict[str, Any]:
    metadata = {"source": "spawn_goal_pair"}
    if placeholder_index:
        metadata["placeholder_index"] = placeholder_index
    return metadata


def _route_id_for_spawn_goal(
    actor_id: str,
    actor_type: str,
    placeholder_index: str,
) -> str:
    if placeholder_index:
        return f"{actor_type}_route_{placeholder_index}"
    return f"{actor_id}_route"


def _route_id_for_placeholder(
    actor_id: str,
    actor_type: str,
    route_placeholder: Any,
) -> str:
    index = _placeholder_index(route_placeholder)
    if index:
        return f"{actor_type}_route_{index}"
    return f"{actor_id}_route"


def _route_metadata_for_placeholder(route_placeholder: Any) -> dict[str, Any]:
    metadata = {"source": "route_placeholder"}
    index = _placeholder_index(route_placeholder)
    if index:
        metadata["placeholder_index"] = index
    raw_name = getattr(route_placeholder, "raw_name", "")
    if raw_name:
        metadata["raw_name"] = str(raw_name)
    return metadata


def _distance_between(a: Vec3, b: Vec3) -> float:
    return (
        (b[0] - a[0]) ** 2
        + (b[1] - a[1]) ** 2
        + (b[2] - a[2]) ** 2
    ) ** 0.5


def _midpoint(a: Vec3, b: Vec3) -> Vec3:
    return (
        (a[0] + b[0]) * 0.5,
        (a[1] + b[1]) * 0.5,
        (a[2] + b[2]) * 0.5,
    )


def _lane_polygon(value: Any) -> list[Vec3]:
    vertices = getattr(value, "vertices", value)
    return [_to_vec3(vertex) for vertex in vertices]


def _lane_centerline(polygon: list[Vec3]) -> list[Vec3]:
    if len(polygon) == 4:
        return [_midpoint(polygon[0], polygon[3]), _midpoint(polygon[1], polygon[2])]
    return list(polygon)


def _lane_width(polygon: list[Vec3]) -> float | None:
    if len(polygon) == 4:
        return (
            _distance_between(polygon[0], polygon[3])
            + _distance_between(polygon[1], polygon[2])
        ) * 0.5
    return None


def _lane_id_for_placeholder(lane_placeholder: Any, fallback_index: int) -> str:
    index = _placeholder_index(lane_placeholder)
    if index:
        return f"vehicle_lane_{index}"
    return f"vehicle_lane_{fallback_index + 1:03d}"


def _lane_metadata_for_placeholder(lane_placeholder: Any) -> dict[str, Any]:
    metadata = {"source": "lane_placeholder"}
    index = _placeholder_index(lane_placeholder)
    if index:
        metadata["placeholder_index"] = index
    raw_name = getattr(lane_placeholder, "raw_name", "")
    if raw_name:
        metadata["raw_name"] = str(raw_name)
    return metadata


def _make_lane_plan(lane_placeholder: Any, fallback_index: int) -> DynamicLanePlan:
    polygon = _lane_polygon(lane_placeholder)
    lane_id = _lane_id_for_placeholder(lane_placeholder, fallback_index)
    return DynamicLanePlan(
        lane_id=lane_id,
        polygon=polygon,
        centerline=_lane_centerline(polygon),
        width_m=_lane_width(polygon),
        source_prim_paths=_compact_source_paths(lane_placeholder),
        metadata=_lane_metadata_for_placeholder(lane_placeholder),
    )


def _append_vehicle_lanes(plan: DynamicScenePlan, lane_placeholders: list[Any]) -> None:
    for index, lane_placeholder in enumerate(lane_placeholders):
        try:
            plan.lanes.append(_make_lane_plan(lane_placeholder, index))
        except Exception as exc:
            source = getattr(lane_placeholder, "prim_path", f"vehicle_lane_{index + 1:03d}")
            plan.warnings.append(f"Vehicle lane placeholder skipped: {source}: {exc}")


def _lane_id_by_placeholder_index(lane_plans: list[DynamicLanePlan]) -> dict[str, str]:
    lane_ids: dict[str, str] = {}
    for lane_plan in lane_plans:
        index = lane_plan.metadata.get("placeholder_index", "")
        if index:
            lane_ids[str(index)] = lane_plan.lane_id
    return lane_ids


def _lane_ids_for_placeholder(
    route_placeholder: Any,
    lane_plans: list[DynamicLanePlan],
) -> list[str]:
    if not lane_plans:
        return []

    placeholder_index = _placeholder_index(route_placeholder)
    lane_id_by_index = _lane_id_by_placeholder_index(lane_plans)
    if placeholder_index and placeholder_index in lane_id_by_index:
        return [lane_id_by_index[placeholder_index]]

    if len(lane_plans) == 1:
        return [lane_plans[0].lane_id]

    return []


def _append_spawn_goal_actor(
    plan: DynamicScenePlan,
    actor_id: str,
    actor_type: str,
    spawn: Any,
    goal: Any,
    speed_mps: float,
    spawn_time_s: float,
    shape: DynamicActorShape,
    placeholder_index: str = "",
    route_mode: str = "loop",
) -> None:
    spawn_position = _to_vec3(spawn)
    goal_position = _to_vec3(goal)
    route = [spawn_position, goal_position]
    source_prim_paths = _compact_source_paths(spawn, goal)
    route_id = _route_id_for_spawn_goal(actor_id, actor_type, placeholder_index)
    metadata = _spawn_goal_metadata(placeholder_index)

    plan.actors.append(
        DynamicActorPlan(
            actor_id=actor_id,
            actor_type=actor_type,
            route=route,
            speed_mps=float(speed_mps),
            spawn_time_s=float(spawn_time_s),
            source_prim_paths=source_prim_paths,
            despawn_time_s=None,
            spawn_pose=DynamicPose(position=spawn_position),
            goal_pose=DynamicPose(position=goal_position),
            route_plan=_make_waypoint_route_plan(
                route_id,
                route,
                source_prim_paths,
                metadata=metadata,
                route_mode=route_mode,
            ),
            route_id=route_id,
            speed_profile=_make_speed_profile(speed_mps),
            shape=_copy_actor_shape(shape),
            asset_category=actor_type,
            metadata=metadata,
        )
    )


def _append_spawn_goal_actors(
    plan: DynamicScenePlan,
    actor_type: str,
    spawns: list[Any],
    goals: list[Any],
    max_actors: int,
    speed_mps: float,
    spawn_time_s: float,
    shape: DynamicActorShape,
    route_mode: str = "loop",
) -> int:
    pairs = _spawn_goal_pairs(spawns, goals)
    actor_count = min(len(pairs), max(0, int(max_actors)))
    for seq, (spawn, goal, placeholder_index) in enumerate(pairs[:actor_count]):
        _append_spawn_goal_actor(
            plan=plan,
            actor_id=f"{actor_type}_{seq + 1:03d}",
            actor_type=actor_type,
            spawn=spawn,
            goal=goal,
            speed_mps=speed_mps,
            spawn_time_s=spawn_time_s,
            shape=shape,
            placeholder_index=placeholder_index,
            route_mode=route_mode,
        )
    return actor_count


def _warn_spawn_goal_pairing(
    plan: DynamicScenePlan,
    actor_type: str,
    spawns: list[Any],
    goals: list[Any],
    generated_count: int,
) -> None:
    if not spawns or not goals:
        return

    spawn_indices = {_placeholder_index(spawn) for spawn in spawns if _placeholder_index(spawn)}
    goal_indices = {_placeholder_index(goal) for goal in goals if _placeholder_index(goal)}

    for index in sorted(spawn_indices - goal_indices):
        plan.warnings.append(f"{actor_type} spawn index {index} has no matching goal.")
    for index in sorted(goal_indices - spawn_indices):
        plan.warnings.append(f"{actor_type} goal index {index} has no matching spawn.")

    unindexed_spawns = sum(1 for spawn in spawns if not _placeholder_index(spawn))
    unindexed_goals = sum(1 for goal in goals if not _placeholder_index(goal))
    if unindexed_spawns != unindexed_goals:
        plan.warnings.append(
            f"{actor_type} unindexed spawn/goal count mismatch; generated "
            f"{generated_count} paired actor(s)."
        )
    elif not spawn_indices and not goal_indices and len(spawns) != len(goals):
        plan.warnings.append(
            f"{actor_type} spawn/goal count mismatch; generated "
            f"{generated_count} paired actor(s)."
        )


def _append_route_actor(
    plan: DynamicScenePlan,
    actor_id: str,
    actor_type: str,
    route_placeholder: Any,
    matched_spawn: Any | None,
    matched_goal: Any | None,
    speed_mps: float,
    spawn_time_s: float,
    shape: DynamicActorShape,
    lane_ids: list[str] | None = None,
    route_mode: str = "loop",
) -> bool:
    route = _route_waypoints(route_placeholder)
    if len(route) < 2:
        plan.warnings.append(
            f"{actor_type} route placeholder has fewer than 2 waypoint(s): "
            f"{getattr(route_placeholder, 'prim_path', actor_id)}"
        )
        return False

    source_prim_paths = _compact_source_paths(
        route_placeholder,
        matched_spawn,
        matched_goal,
    )
    route_id = _route_id_for_placeholder(actor_id, actor_type, route_placeholder)
    metadata = _route_metadata_for_placeholder(route_placeholder)

    plan.actors.append(
        DynamicActorPlan(
            actor_id=actor_id,
            actor_type=actor_type,
            route=route,
            speed_mps=float(speed_mps),
            spawn_time_s=float(spawn_time_s),
            source_prim_paths=source_prim_paths,
            despawn_time_s=None,
            spawn_pose=DynamicPose(position=route[0]),
            goal_pose=DynamicPose(position=route[-1]),
            route_plan=_make_waypoint_route_plan(
                route_id,
                route,
                source_prim_paths,
                metadata=metadata,
                lane_ids=lane_ids,
                route_mode=route_mode,
            ),
            route_id=route_id,
            speed_profile=_make_speed_profile(speed_mps),
            shape=_copy_actor_shape(shape),
            asset_category=actor_type,
            metadata=metadata,
        )
    )
    return True


def _append_route_actors(
    plan: DynamicScenePlan,
    actor_type: str,
    routes: list[Any],
    spawns: list[Any],
    goals: list[Any],
    max_actors: int,
    speed_mps: float,
    spawn_time_s: float,
    shape: DynamicActorShape,
    lane_plans: list[DynamicLanePlan] | None = None,
    route_mode: str = "loop",
) -> int:
    actor_count = min(len(routes), max(0, int(max_actors)))
    appended_count = 0
    for index in range(actor_count):
        route_placeholder = routes[index]
        placeholder_index = _placeholder_index(route_placeholder)
        appended = _append_route_actor(
            plan=plan,
            actor_id=f"{actor_type}_{index + 1:03d}",
            actor_type=actor_type,
            route_placeholder=route_placeholder,
            matched_spawn=_find_by_index(spawns, placeholder_index),
            matched_goal=_find_by_index(goals, placeholder_index),
            speed_mps=speed_mps,
            spawn_time_s=spawn_time_s,
            shape=shape,
            lane_ids=_lane_ids_for_placeholder(route_placeholder, lane_plans or []),
            route_mode=route_mode,
        )
        if appended:
            appended_count += 1
    return appended_count


def _warn_incomplete_pair(
    plan: DynamicScenePlan,
    actor_type: str,
    spawns: list[Any],
    goals: list[Any],
) -> None:
    if spawns and not goals:
        plan.warnings.append(f"{actor_type} spawn exists but no goal was found.")
    elif goals and not spawns:
        plan.warnings.append(f"{actor_type} goal exists but no spawn was found.")


def build_dynamic_actor_plan(
    scene_stats: Any,
    config: DynamicPlanConfig | None = None,
) -> DynamicScenePlan:
    if config is None:
        config = DynamicPlanConfig()

    plan = DynamicScenePlan()

    pedestrian_spawns = _get_stats_list(scene_stats, "pedestrian_spawn_points")
    pedestrian_goals = _get_stats_list(scene_stats, "pedestrian_goal_points")
    pedestrian_routes = _get_stats_list(scene_stats, "pedestrian_routes")
    pedestrian_shape = _actor_shape_for_type("pedestrian", config)
    route_mode = config.default_route_mode

    if pedestrian_routes:
        pedestrian_count = _append_route_actors(
            plan=plan,
            actor_type="pedestrian",
            routes=pedestrian_routes,
            spawns=pedestrian_spawns,
            goals=pedestrian_goals,
            max_actors=config.max_pedestrian_actors,
            speed_mps=config.pedestrian_speed_mps,
            spawn_time_s=config.default_spawn_time_s,
            shape=pedestrian_shape,
            route_mode=route_mode,
        )
        if pedestrian_count == 0 and config.max_pedestrian_actors > 0:
            plan.warnings.append(
                "Pedestrian route placeholder exists but no actor was generated."
            )
    else:
        pedestrian_count = _append_spawn_goal_actors(
            plan=plan,
            actor_type="pedestrian",
            spawns=pedestrian_spawns,
            goals=pedestrian_goals,
            max_actors=config.max_pedestrian_actors,
            speed_mps=config.pedestrian_speed_mps,
            spawn_time_s=config.default_spawn_time_s,
            shape=pedestrian_shape,
            route_mode=route_mode,
        )
        if pedestrian_count == 0 and config.max_pedestrian_actors > 0:
            _warn_incomplete_pair(plan, "pedestrian", pedestrian_spawns, pedestrian_goals)
        _warn_spawn_goal_pairing(
            plan,
            "pedestrian",
            pedestrian_spawns,
            pedestrian_goals,
            pedestrian_count,
        )

    vehicle_spawns = _get_stats_list(scene_stats, "vehicle_spawn_points")
    vehicle_goals = _get_stats_list(scene_stats, "vehicle_goal_points")
    vehicle_routes = _get_stats_list(scene_stats, "vehicle_routes")
    vehicle_lanes = _get_stats_list(scene_stats, "vehicle_lanes")
    vehicle_shape = _actor_shape_for_type("vehicle", config)
    _append_vehicle_lanes(plan, vehicle_lanes)

    if vehicle_routes:
        vehicle_count = _append_route_actors(
            plan=plan,
            actor_type="vehicle",
            routes=vehicle_routes,
            spawns=vehicle_spawns,
            goals=vehicle_goals,
            max_actors=config.max_vehicle_actors,
            speed_mps=config.vehicle_speed_mps,
            spawn_time_s=config.default_spawn_time_s,
            shape=vehicle_shape,
            lane_plans=plan.lanes,
            route_mode=route_mode,
        )
        if vehicle_count == 0 and config.max_vehicle_actors > 0:
            plan.warnings.append(
                "Vehicle route placeholder exists but no actor was generated."
            )
    else:
        vehicle_count = _append_spawn_goal_actors(
            plan=plan,
            actor_type="vehicle",
            spawns=vehicle_spawns,
            goals=vehicle_goals,
            max_actors=config.max_vehicle_actors,
            speed_mps=config.vehicle_speed_mps,
            spawn_time_s=config.default_spawn_time_s,
            shape=vehicle_shape,
            route_mode=route_mode,
        )
        if vehicle_count == 0 and config.max_vehicle_actors > 0:
            _warn_incomplete_pair(plan, "vehicle", vehicle_spawns, vehicle_goals)
            if vehicle_lanes and not (vehicle_spawns and vehicle_goals):
                plan.warnings.append(
                    "Vehicle lane exists but no complete vehicle spawn/goal pair was found."
                )
        _warn_spawn_goal_pairing(
            plan,
            "vehicle",
            vehicle_spawns,
            vehicle_goals,
            vehicle_count,
        )

    return plan
