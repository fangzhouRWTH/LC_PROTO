from dataclasses import dataclass, field
from typing import Any

Vec3 = tuple[float, float, float]


@dataclass
class DynamicPlanConfig:
    max_pedestrian_actors: int = 1
    max_vehicle_actors: int = 1
    pedestrian_speed_mps: float = 1.2
    vehicle_speed_mps: float = 4.0
    default_spawn_time_s: float = 0.0


@dataclass
class DynamicActorPlan:
    actor_id: str
    actor_type: str
    route: list[Vec3] = field(default_factory=list)
    speed_mps: float = 0.0
    spawn_time_s: float = 0.0
    source_prim_paths: list[str] = field(default_factory=list)


@dataclass
class DynamicScenePlan:
    actors: list[DynamicActorPlan] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


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


def _append_spawn_goal_actor(
    plan: DynamicScenePlan,
    actor_id: str,
    actor_type: str,
    spawn: Any,
    goal: Any,
    speed_mps: float,
    spawn_time_s: float,
) -> None:
    plan.actors.append(
        DynamicActorPlan(
            actor_id=actor_id,
            actor_type=actor_type,
            route=[_to_vec3(spawn), _to_vec3(goal)],
            speed_mps=float(speed_mps),
            spawn_time_s=float(spawn_time_s),
            source_prim_paths=_compact_source_paths(spawn, goal),
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
) -> int:
    actor_count = min(len(spawns), len(goals), max(0, int(max_actors)))
    for index in range(actor_count):
        _append_spawn_goal_actor(
            plan=plan,
            actor_id=f"{actor_type}_{index + 1:03d}",
            actor_type=actor_type,
            spawn=spawns[index],
            goal=goals[index],
            speed_mps=speed_mps,
            spawn_time_s=spawn_time_s,
        )
    return actor_count


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

    pedestrian_count = _append_spawn_goal_actors(
        plan=plan,
        actor_type="pedestrian",
        spawns=pedestrian_spawns,
        goals=pedestrian_goals,
        max_actors=config.max_pedestrian_actors,
        speed_mps=config.pedestrian_speed_mps,
        spawn_time_s=config.default_spawn_time_s,
    )
    if pedestrian_count == 0 and config.max_pedestrian_actors > 0:
        _warn_incomplete_pair(plan, "pedestrian", pedestrian_spawns, pedestrian_goals)
    elif len(pedestrian_spawns) != len(pedestrian_goals):
        plan.warnings.append(
            "Pedestrian spawn/goal count mismatch; generated "
            f"{pedestrian_count} paired actor(s)."
        )

    vehicle_spawns = _get_stats_list(scene_stats, "vehicle_spawn_points")
    vehicle_goals = _get_stats_list(scene_stats, "vehicle_goal_points")
    vehicle_lanes = _get_stats_list(scene_stats, "vehicle_lanes")

    vehicle_count = _append_spawn_goal_actors(
        plan=plan,
        actor_type="vehicle",
        spawns=vehicle_spawns,
        goals=vehicle_goals,
        max_actors=config.max_vehicle_actors,
        speed_mps=config.vehicle_speed_mps,
        spawn_time_s=config.default_spawn_time_s,
    )
    if vehicle_count == 0 and config.max_vehicle_actors > 0:
        _warn_incomplete_pair(plan, "vehicle", vehicle_spawns, vehicle_goals)
        if vehicle_lanes and not (vehicle_spawns and vehicle_goals):
            plan.warnings.append(
                "Vehicle lane exists but no complete vehicle spawn/goal pair was found."
            )
    elif len(vehicle_spawns) != len(vehicle_goals):
        plan.warnings.append(
            "Vehicle spawn/goal count mismatch; generated "
            f"{vehicle_count} paired actor(s)."
        )

    return plan
