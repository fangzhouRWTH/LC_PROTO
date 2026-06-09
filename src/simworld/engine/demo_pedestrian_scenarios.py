"""Demo-only pedestrian scenario postprocessing for the Tencent scene."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

Vec3 = tuple[float, float, float]
Vec2 = tuple[float, float]

DEFAULT_SCHEMA_VERSION = "simworld.demo_people_scenarios.v1"
DEFAULT_SCENARIO = "people_16"
DEFAULT_ZONE_SAMPLE_SPACING_M = 1.0
_EPS = 1e-6


def load_demo_people_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).expanduser()
    with config_path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Demo people config must be a JSON object: {config_path}")
    return config


def apply_demo_people_scenario_from_file(
    plan: dict[str, Any],
    config_path: str | Path,
    *,
    scenario_name: str | None = None,
) -> dict[str, Any]:
    config = load_demo_people_config(config_path)
    return apply_demo_people_scenario(
        plan,
        config,
        scenario_name=scenario_name,
        config_path=str(Path(config_path).expanduser()),
    )


def apply_demo_people_scenario(
    plan: dict[str, Any],
    config: dict[str, Any],
    *,
    scenario_name: str | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    """Return a placement plan with demo-selected pedestrian routes.

    This is intentionally not part of the long-term public-space route generator.
    It only runs when a demo config is explicitly supplied.
    """

    if not isinstance(plan, dict):
        raise ValueError("Placement plan must be a dict.")
    scenario_key = str(
        scenario_name or config.get("default_scenario") or DEFAULT_SCENARIO
    ).strip()
    scenarios = config.get("scenarios")
    if not isinstance(scenarios, dict) or scenario_key not in scenarios:
        available = ", ".join(sorted(str(key) for key in (scenarios or {}).keys()))
        raise ValueError(
            f"Unknown demo people scenario '{scenario_key}'. Available: {available}"
        )

    defaults = config.get("defaults") if isinstance(config.get("defaults"), dict) else {}
    scenario = dict(defaults)
    scenario.update(scenarios[scenario_key] or {})

    source_routes, source_debug = _demo_source_routes_for_plan(
        plan,
        scenario=scenario,
        scenario_name=scenario_key,
    )
    processed = copy.deepcopy(plan)
    selected, debug = select_demo_people_routes(
        source_routes,
        dynamic_zones=plan.get("dynamic_zones") or [],
        scenario=scenario,
        scenario_name=scenario_key,
    )
    debug["source_generation"] = source_debug

    processed["pedestrian_demo_source_routes"] = copy.deepcopy(source_routes)
    processed["pedestrian_routes"] = selected
    processed["demo_people_scenario_debug"] = {
        **debug,
        "schema_version": str(config.get("schema_version") or DEFAULT_SCHEMA_VERSION),
        "config_path": config_path or "",
    }
    debug_block = processed.setdefault("debug", {})
    if isinstance(debug_block, dict):
        debug_block["pedestrian_route_count"] = len(selected)
        debug_block["demo_people_source_route_count"] = len(source_routes)
        debug_block["demo_people_scenario"] = scenario_key
    if debug["warnings"]:
        processed.setdefault("warnings", [])
        if isinstance(processed["warnings"], list):
            processed["warnings"].extend(debug["warnings"])
    return processed


def _demo_source_routes_for_plan(
    plan: dict[str, Any],
    *,
    scenario: dict[str, Any],
    scenario_name: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    route_source = str(scenario.get("route_source") or "pedestrian_routes").strip().lower()
    target_count = max(0, int(scenario.get("actor_count") or 0))
    debug: dict[str, Any] = {
        "route_source": route_source,
        "used_walkable_graph": False,
        "fallback_used": False,
    }

    source_routes: list[dict[str, Any]] = []
    if route_source in {"walkable_lines", "pedestrian_walkable_lines", "walkable_graph"}:
        walkable_lines = [
            line
            for line in (plan.get("pedestrian_walkable_lines") or [])
            if isinstance(line, dict) and len(_route_vertices(line)) >= 2
        ]
        graph_routes, graph_debug = generate_demo_people_source_routes_from_walkable_lines(
            walkable_lines,
            scenario=scenario,
            scenario_name=scenario_name,
            target_count=target_count,
        )
        source_routes = graph_routes
        debug.update(graph_debug)
        debug["used_walkable_graph"] = bool(graph_routes)

    if not source_routes:
        raw_source_routes = (
            plan.get("pedestrian_demo_source_routes")
            or plan.get("pedestrian_routes")
            or []
        )
        source_routes = [
            route
            for route in raw_source_routes
            if isinstance(route, dict) and len(_route_vertices(route)) >= 2
        ]
        debug["fallback_used"] = route_source in {
            "walkable_lines",
            "pedestrian_walkable_lines",
            "walkable_graph",
        }
        debug["fallback_source_route_count"] = len(source_routes)

    debug["source_route_count"] = len(source_routes)
    return source_routes, debug


def generate_demo_people_source_routes_from_walkable_lines(
    walkable_lines: list[dict[str, Any]],
    *,
    scenario: dict[str, Any],
    scenario_name: str,
    target_count: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    min_length = max(0.0, float(scenario.get("min_route_length_m", 25.0)))
    max_length = max(min_length, float(scenario.get("max_route_length_m", 80.0)))
    target_length = max(
        min_length,
        min(max_length, float(scenario.get("target_route_length_m", max_length))),
    )
    node_tolerance = max(1e-6, float(scenario.get("node_merge_tolerance_m", 0.10)))
    max_sources = max(
        target_count,
        int(scenario.get("max_source_routes") or max(1, target_count * 4)),
    )
    per_region_limit = max(
        1,
        int(scenario.get("max_source_routes_per_region") or max_sources),
    )
    end_candidates_per_start = max(
        1,
        int(scenario.get("end_candidates_per_start") or 4),
    )

    grouped: dict[str, list[dict[str, Any]]] = {}
    region_order: list[str] = []
    for line in walkable_lines:
        region = _route_region(line)
        if region not in grouped:
            grouped[region] = []
            region_order.append(region)
        grouped[region].append(line)

    routes: list[dict[str, Any]] = []
    debug_regions: list[dict[str, Any]] = []
    seen: set[tuple[tuple[int, int, int], ...]] = set()
    for region in region_order:
        if len(routes) >= max_sources:
            break
        region_routes, region_debug = _generate_region_walkable_graph_routes(
            grouped[region],
            region_id=region,
            scenario_name=scenario_name,
            min_length_m=min_length,
            target_length_m=target_length,
            max_length_m=max_length,
            node_merge_tolerance_m=node_tolerance,
            max_routes=min(per_region_limit, max_sources - len(routes)),
            end_candidates_per_start=end_candidates_per_start,
            seen=seen,
        )
        routes.extend(region_routes)
        debug_regions.append(region_debug)

    return routes, {
        "walkable_line_count": len(walkable_lines),
        "generated_walkable_source_route_count": len(routes),
        "walkable_region_count": len(region_order),
        "walkable_regions": debug_regions,
        "walkable_source_config": {
            "min_route_length_m": min_length,
            "target_route_length_m": target_length,
            "max_route_length_m": max_length,
            "node_merge_tolerance_m": node_tolerance,
            "max_source_routes": max_sources,
            "max_source_routes_per_region": per_region_limit,
            "end_candidates_per_start": end_candidates_per_start,
        },
    }


def _generate_region_walkable_graph_routes(
    walkable_lines: list[dict[str, Any]],
    *,
    region_id: str,
    scenario_name: str,
    min_length_m: float,
    target_length_m: float,
    max_length_m: float,
    node_merge_tolerance_m: float,
    max_routes: int,
    end_candidates_per_start: int,
    seen: set[tuple[tuple[int, int, int], ...]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    graph = _graph_from_walkable_lines(
        walkable_lines,
        node_merge_tolerance_m=node_merge_tolerance_m,
    )
    nodes: list[Vec3] = graph["nodes"]
    edges: list[dict[str, Any]] = graph["edges"]
    adjacency: dict[int, dict[int, float]] = graph["adjacency"]
    components = _component_node_ids(adjacency)
    routes: list[dict[str, Any]] = []
    skipped_short_components: list[dict[str, Any]] = []
    slug = _safe_id(region_id).lower()
    seen_path_keys: set[tuple[tuple[int, int], ...]] = set()

    for component_index, component in enumerate(components, start=1):
        if len(routes) >= max_routes:
            break
        component_length = _component_edge_length(component, edges)
        if component_length + _EPS < min_length_m:
            skipped_short_components.append(
                {
                    "component_index": component_index,
                    "node_count": len(component),
                    "edge_length": component_length,
                    "reason": "component_shorter_than_min_route_length",
                }
            )
            continue

        leaf_nodes = [node for node in component if len(adjacency.get(node, {})) == 1]
        leaf_set = set(leaf_nodes)
        internal_nodes = [node for node in component if node not in leaf_set]
        start_nodes = sorted(
            leaf_nodes,
            key=lambda node: (nodes[node][0], nodes[node][1], node),
        ) + sorted(
            internal_nodes,
            key=lambda node: (nodes[node][0], nodes[node][1], node),
        )

        for start in start_nodes:
            if len(routes) >= max_routes:
                break
            distances, previous = _shortest_paths_from(start, component, adjacency)
            reachable = [
                node
                for node, distance in distances.items()
                if node != start
                and distance < float("inf")
                and distance + _EPS >= min_length_m
            ]
            candidates = sorted(
                reachable,
                key=lambda node: (
                    abs(min(distances[node], max_length_m) - target_length_m),
                    -min(distances[node], max_length_m),
                    nodes[node][0],
                    nodes[node][1],
                    node,
                ),
            )
            for end in candidates[:end_candidates_per_start]:
                if len(routes) >= max_routes:
                    break
                path = _reconstruct_path(previous, start, end)
                if len(path) < 2:
                    continue
                path_key = tuple(
                    sorted(
                        (min(path[index - 1], path[index]), max(path[index - 1], path[index]))
                        for index in range(1, len(path))
                    )
                )
                if path_key in seen_path_keys:
                    continue
                desired_length = min(distances[end], max_length_m)
                vertices = _truncate_path_vertices(path, nodes, adjacency, desired_length)
                if len(vertices) < 2:
                    continue
                length = _route_length(vertices)
                if length + _EPS < min_length_m:
                    continue
                key = _route_key(vertices)
                reverse_key = tuple(reversed(key))
                if key in seen or reverse_key in seen:
                    continue
                seen.add(key)
                seen_path_keys.add(path_key)
                route_token = f"{len(routes) + 1:03d}"
                route_id = _safe_id(
                    f"demo_source_trip_{scenario_name}_{slug}_{route_token}"
                )
                routes.append(
                    {
                        "route_id": route_id,
                        "vertices": [[x, y, z] for x, y, z in vertices],
                        "raw_name": route_id,
                        "category": "route",
                        "index": route_token,
                        "metadata": {
                            "source": "demo_people_walkable_graph",
                            "source_region_id": region_id,
                            "route_generation": "demo_walkable_graph_long_route",
                            "line_role": "demo_source_trip",
                            "length": length,
                            "component_index": component_index,
                            "target_length": target_length_m,
                            "min_length": min_length_m,
                            "max_length": max_length_m,
                            "source_walkable_line_count": len(walkable_lines),
                        },
                    }
                )

    return routes, {
        "region_id": region_id,
        "walkable_line_count": len(walkable_lines),
        "graph_node_count": len(nodes),
        "graph_edge_count": len(edges),
        "component_count": len(components),
        "generated_route_count": len(routes),
        "skipped_short_component_count": len(skipped_short_components),
        "skipped_short_components": skipped_short_components,
    }


def select_demo_people_routes(
    routes: list[dict[str, Any]],
    *,
    dynamic_zones: list[dict[str, Any]],
    scenario: dict[str, Any],
    scenario_name: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target_count = max(0, int(scenario.get("actor_count") or 0))
    offsets = _float_list(scenario.get("offset_candidates_m"), default=[0.0])
    if not offsets:
        offsets = [0.0]
    require_zero_offset = bool(scenario.get("require_zero_offset", True))
    if require_zero_offset and not any(abs(value) <= _EPS for value in offsets):
        offsets.insert(0, 0.0)
    offset_selection_mode = str(
        scenario.get("offset_selection_mode") or "zero_then_side"
    ).strip().lower()
    route_clearance_m = max(0.0, float(scenario.get("route_clearance_m", 1.5)))
    route_endpoint_ignore_m = max(0.0, float(scenario.get("route_endpoint_ignore_m", 1.5)))
    parallel_clearance_m = max(
        0.0,
        float(scenario.get("parallel_route_clearance_m", 0.65)),
    )
    zone_margin_m = max(0.0, float(scenario.get("zone_margin_m", 0.35)))
    sample_spacing_m = max(
        0.1,
        float(scenario.get("zone_sample_spacing_m", DEFAULT_ZONE_SAMPLE_SPACING_M)),
    )
    speed_mps = max(0.0, float(scenario.get("speed_mps", 1.2)))
    speed_range_mps = _float_range(scenario.get("speed_range_mps"))
    spawn_stagger_s = max(0.0, float(scenario.get("spawn_stagger_s", 0.0)))
    spawn_stagger_range_s = _float_range(scenario.get("spawn_stagger_range_s"))
    start_offset_range_m = _float_range(scenario.get("start_offset_range_m"))
    route_mode = str(scenario.get("route_mode") or "once")
    max_route_length_m = _optional_positive_float(scenario.get("max_route_length_m"))
    min_route_length_m = max(0.0, float(scenario.get("min_route_length_m", 1.0)))
    offset_jitter_m = max(0.0, float(scenario.get("offset_jitter_m", 0.0)))
    offset_range_m = _float_range(scenario.get("offset_range_m"))

    polygons = _zone_polygons(dynamic_zones)
    ordered_routes = _round_robin_routes_by_region(routes)
    rehearsal_settings = _collision_rehearsal_settings(scenario)
    pool_target_count = target_count
    if rehearsal_settings.get("enabled"):
        pool_multiplier = max(1.0, float(rehearsal_settings.get("candidate_pool_multiplier", 1.0)))
        pool_extra = max(0, int(rehearsal_settings.get("candidate_pool_extra", 0)))
        pool_target_count = max(
            target_count,
            int(math.ceil(target_count * pool_multiplier)) + pool_extra,
        )
    selected: list[dict[str, Any]] = []
    selected_geometries: list[tuple[str, list[Vec3]]] = []
    rejected: list[dict[str, Any]] = []
    seen_keys: set[tuple[tuple[int, int, int], ...]] = set()

    next_spawn_time_s = 0.0
    for route, offset_m, offset_index in _iter_route_offset_candidates(
        ordered_routes,
        offsets,
        mode=offset_selection_mode,
    ):
        if len(selected) >= pool_target_count:
            break
        sequence = len(selected) + 1
        candidate_offset_m = _jittered_offset(
            offset_m,
            route=route,
            scenario_name=scenario_name,
            sequence=sequence,
            offset_index=offset_index,
            jitter_m=offset_jitter_m,
            offset_range_m=offset_range_m,
        )
        base_vertices = _route_vertices(route)
        if max_route_length_m is not None:
            base_vertices = _truncate_route(base_vertices, max_route_length_m)
        if _route_length(base_vertices) + _EPS < min_route_length_m:
            rejected.append(
                _rejection(route, candidate_offset_m, "shorter_than_min_route_length")
            )
            continue
        start_offset_m = _route_start_offset(
            base_vertices,
            route=route,
            scenario_name=scenario_name,
            sequence=sequence,
            start_offset_range_m=start_offset_range_m,
            min_remaining_length_m=min_route_length_m,
        )
        if start_offset_m > _EPS:
            base_vertices = _trim_route_start(base_vertices, start_offset_m)
        vertices = _offset_route_vertices(base_vertices, candidate_offset_m)
        if not _route_within_zones(
            vertices,
            polygons,
            margin_m=zone_margin_m,
            sample_spacing_m=sample_spacing_m,
        ):
            rejected.append(_rejection(route, candidate_offset_m, "outside_dynamic_zone"))
            continue
        key = _route_key(vertices)
        if key in seen_keys:
            rejected.append(_rejection(route, candidate_offset_m, "duplicate_route"))
            continue
        parent_id = _route_id(route)
        if not _passes_route_spacing(
            vertices,
            parent_id=parent_id,
            selected_geometries=selected_geometries,
            route_clearance_m=route_clearance_m,
            route_endpoint_ignore_m=route_endpoint_ignore_m,
            parallel_clearance_m=parallel_clearance_m,
        ):
            rejected.append(_rejection(route, candidate_offset_m, "route_clearance"))
            continue
        actor_speed_mps = _range_value(
            speed_range_mps,
            default=speed_mps,
            parts=(scenario_name, parent_id, sequence, "speed"),
        )
        actor_spawn_time_s = next_spawn_time_s
        seen_keys.add(key)
        selected_geometries.append((parent_id, vertices))
        selected.append(
            _make_demo_route(
                route,
                vertices,
                sequence=sequence,
                scenario_name=scenario_name,
                offset_m=candidate_offset_m,
                start_offset_m=start_offset_m,
                speed_mps=actor_speed_mps,
                spawn_time_s=actor_spawn_time_s,
                route_mode=route_mode,
            )
        )
        next_spawn_time_s += _range_value(
            spawn_stagger_range_s,
            default=spawn_stagger_s,
            parts=(scenario_name, parent_id, sequence, "spawn"),
        )

    pool_rehearsal_debug: dict[str, Any] | None = None
    if pool_target_count > target_count and selected:
        rehearsed_pool, pool_rehearsal_debug = _rehearse_demo_route_collisions(
            selected,
            scenario=scenario,
            polygons=polygons,
            sample_spacing_m=sample_spacing_m,
        )
        selected = _prune_rehearsed_route_pool(
            rehearsed_pool,
            target_count=target_count,
            conflicts=pool_rehearsal_debug.get("unresolved_conflicts") or [],
        )
    elif len(selected) > target_count:
        selected = selected[:target_count]

    selected, rehearsal_debug = _rehearse_demo_route_collisions(
        selected,
        scenario=scenario,
        polygons=polygons,
        sample_spacing_m=sample_spacing_m,
    )
    if pool_rehearsal_debug is not None:
        rehearsal_debug["candidate_pool"] = {
            "pool_target_count": pool_target_count,
            "pool_selected_count": len(rehearsed_pool),
            "pool_unresolved_conflict_count": pool_rehearsal_debug.get("unresolved_conflict_count"),
        }

    warnings: list[str] = []
    if len(selected) < target_count:
        warnings.append(
            f"Demo people scenario '{scenario_name}' requested {target_count} "
            f"route(s) but generated {len(selected)} after zone/spacing validation."
        )

    return selected, {
        "scenario": scenario_name,
        "requested_actor_count": target_count,
        "selected_route_count": len(selected),
        "candidate_pool_target_count": pool_target_count,
        "source_route_count": len(routes),
        "dynamic_zone_count": len(polygons),
        "offset_candidates_m": offsets,
        "offset_selection_mode": offset_selection_mode,
        "require_zero_offset": require_zero_offset,
        "route_clearance_m": route_clearance_m,
        "parallel_route_clearance_m": parallel_clearance_m,
        "route_endpoint_ignore_m": route_endpoint_ignore_m,
        "zone_margin_m": zone_margin_m,
        "speed_mps": speed_mps,
        "speed_range_mps": list(speed_range_mps) if speed_range_mps is not None else None,
        "spawn_stagger_s": spawn_stagger_s,
        "spawn_stagger_range_s": list(spawn_stagger_range_s) if spawn_stagger_range_s is not None else None,
        "start_offset_range_m": list(start_offset_range_m) if start_offset_range_m is not None else None,
        "offset_jitter_m": offset_jitter_m,
        "offset_range_m": list(offset_range_m) if offset_range_m is not None else None,
        "route_mode": route_mode,
        "collision_rehearsal": rehearsal_debug,
        "max_route_length_m": max_route_length_m,
        "rejected_candidate_count": len(rejected),
        "rejected_candidates": rejected[:100],
        "warnings": warnings,
    }


def _make_demo_route(
    source_route: dict[str, Any],
    vertices: list[Vec3],
    *,
    sequence: int,
    scenario_name: str,
    offset_m: float,
    start_offset_m: float,
    speed_mps: float,
    spawn_time_s: float,
    route_mode: str,
) -> dict[str, Any]:
    parent_id = _route_id(source_route)
    region_id = _route_region(source_route)
    route_id = _safe_id(f"demo_people_{scenario_name}_{sequence:03d}_{parent_id}")
    metadata = dict(source_route.get("metadata") or {})
    metadata.update(
        {
            "source": "demo_people_scenario",
            "parent_source": (source_route.get("metadata") or {}).get("source", ""),
            "source_region_id": region_id,
            "demo_only": True,
            "scenario": scenario_name,
            "parent_route_id": parent_id,
            "offset_m": float(offset_m),
            "start_offset_m": float(start_offset_m),
            "line_role": "demo_trip",
            "route_generation": "demo_people_scenario_offset",
            "length": _route_length(vertices),
            "speed_mps": float(speed_mps),
            "spawn_time_s": float(spawn_time_s),
            "route_mode": str(route_mode or "once"),
        }
    )
    return {
        "route_id": route_id,
        "vertices": [[x, y, z] for x, y, z in vertices],
        "raw_name": route_id,
        "index": f"{sequence:03d}",
        "category": "route",
        "metadata": metadata,
    }


def _prune_rehearsed_route_pool(
    routes: list[dict[str, Any]],
    *,
    target_count: int,
    conflicts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(routes) <= target_count:
        return routes
    conflict_score: dict[str, float] = {}
    for conflict in conflicts:
        route_a = str(conflict.get("route_a") or "")
        route_b = str(conflict.get("route_b") or "")
        if route_a:
            conflict_score[route_a] = conflict_score.get(route_a, 0.0) + 1.0
        if route_b:
            conflict_score[route_b] = conflict_score.get(route_b, 0.0) + 1.35

    indexed = list(enumerate(routes))
    indexed.sort(
        key=lambda item: (
            conflict_score.get(_route_id(item[1]), 0.0),
            _metadata_float(
                item[1].get("metadata") if isinstance(item[1].get("metadata"), dict) else {},
                "collision_rehearsal_delay_s",
                0.0,
            ),
            item[0],
        )
    )
    kept_indices = {index for index, _route in indexed[:target_count]}
    return [route for index, route in enumerate(routes) if index in kept_indices]


def _rehearse_demo_route_collisions(
    routes: list[dict[str, Any]],
    *,
    scenario: dict[str, Any],
    polygons: list[list[Vec2]],
    sample_spacing_m: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    settings = _collision_rehearsal_settings(scenario)
    if not settings["enabled"] or len(routes) < 2:
        return routes, {"enabled": settings["enabled"], "route_count": len(routes)}

    min_separation_m = settings["min_separation_m"]
    time_step_s = settings["time_step_s"]
    delay_step_s = settings["spawn_delay_step_s"]
    max_delay_s = settings["max_spawn_delay_s"]
    detour_offsets_m = settings["detour_offsets_m"]
    detour_window_m = settings["detour_window_m"]
    max_detours_per_route = settings["max_detours_per_route"]
    max_delay_attempts = max(0, int(math.ceil(max_delay_s / max(delay_step_s, _EPS))))

    scheduled: list[dict[str, Any]] = []
    delayed_count = 0
    total_delay_s = 0.0
    max_applied_delay_s = 0.0
    detoured_route_count = 0
    inserted_detour_count = 0
    repaired_conflict_count = 0
    unresolved: list[dict[str, Any]] = []

    for route in routes:
        candidate = copy.deepcopy(route)
        metadata = candidate.setdefault("metadata", {})
        original_spawn_s = _metadata_float(metadata, "spawn_time_s", 0.0)
        applied_delay_s = 0.0
        route_detour_records: list[dict[str, Any]] = []
        attempts_used = 0

        for _detour_attempt in range(max_detours_per_route + 1):
            conflict = _first_rehearsal_conflict(
                candidate,
                scheduled,
                min_separation_m=min_separation_m,
                time_step_s=time_step_s,
            )
            attempts_used += 1
            if conflict is None:
                break
            repaired_conflict_count += 1
            if len(route_detour_records) >= max_detours_per_route:
                break
            detoured = _try_apply_collision_detour(
                candidate,
                conflict,
                scheduled=scheduled,
                min_separation_m=min_separation_m,
                time_step_s=time_step_s,
                detour_offsets_m=detour_offsets_m,
                detour_window_m=detour_window_m,
                polygons=polygons,
                sample_spacing_m=sample_spacing_m,
            )
            attempts_used += max(1, len(detour_offsets_m))
            if detoured is None:
                break
            candidate = detoured
            metadata = candidate.setdefault("metadata", {})
            route_detour_records.append(metadata.get("collision_rehearsal_detours", [])[-1])

        conflict = _first_rehearsal_conflict(
            candidate,
            scheduled,
            min_separation_m=min_separation_m,
            time_step_s=time_step_s,
        )
        if conflict is not None:
            for delay_attempt in range(1, max_delay_attempts + 1):
                delay_s = min(max_delay_s, delay_attempt * delay_step_s)
                metadata["spawn_time_s"] = original_spawn_s + delay_s
                conflict = _first_rehearsal_conflict(
                    candidate,
                    scheduled,
                    min_separation_m=min_separation_m,
                    time_step_s=time_step_s,
                )
                attempts_used += 1
                applied_delay_s = delay_s
                if conflict is None:
                    break
                repaired_conflict_count += 1

        if conflict is not None:
            unresolved.append(
                {
                    "route_id": _route_id(candidate),
                    "conflict": conflict,
                    "applied_delay_s": applied_delay_s,
                    "detour_count": len(route_detour_records),
                }
            )

        metadata["spawn_time_s"] = original_spawn_s + applied_delay_s
        metadata["collision_rehearsal_delay_s"] = applied_delay_s
        metadata["collision_rehearsal_attempts"] = attempts_used
        metadata["collision_rehearsal_detour_count"] = len(route_detour_records)
        if applied_delay_s > _EPS:
            metadata["spawn_time_s_original"] = original_spawn_s
            delayed_count += 1
            total_delay_s += applied_delay_s
            max_applied_delay_s = max(max_applied_delay_s, applied_delay_s)
        if route_detour_records:
            detoured_route_count += 1
            inserted_detour_count += len(route_detour_records)
        scheduled.append(candidate)

    final_conflicts = _collect_rehearsal_conflicts(
        scheduled,
        min_separation_m=min_separation_m,
        time_step_s=time_step_s,
        max_records=25,
    )
    return scheduled, {
        "enabled": True,
        "route_count": len(routes),
        "min_separation_m": min_separation_m,
        "time_step_s": time_step_s,
        "spawn_delay_step_s": delay_step_s,
        "max_spawn_delay_s": max_delay_s,
        "detour_offsets_m": detour_offsets_m,
        "detour_window_m": detour_window_m,
        "max_detours_per_route": max_detours_per_route,
        "detoured_route_count": detoured_route_count,
        "inserted_detour_count": inserted_detour_count,
        "delayed_route_count": delayed_count,
        "total_delay_s": total_delay_s,
        "max_applied_delay_s": max_applied_delay_s,
        "repaired_conflict_attempt_count": repaired_conflict_count,
        "unresolved_conflict_count": len(final_conflicts),
        "unresolved_conflicts": final_conflicts,
        "unresolved_candidates": unresolved[:25],
    }


def _collision_rehearsal_settings(scenario: dict[str, Any]) -> dict[str, Any]:
    raw = scenario.get("collision_rehearsal")
    if not isinstance(raw, dict):
        return {"enabled": False}
    detour_offsets = _float_list(
        raw.get("detour_offsets_m"),
        default=[0.55, -0.55, 0.8, -0.8],
    )
    if not detour_offsets:
        detour_offsets = [0.55, -0.55]
    return {
        "enabled": bool(raw.get("enabled", False)),
        "min_separation_m": max(0.0, float(raw.get("min_separation_m", 0.7))),
        "time_step_s": max(0.05, float(raw.get("time_step_s", 0.2))),
        "spawn_delay_step_s": max(0.05, float(raw.get("spawn_delay_step_s", 0.35))),
        "max_spawn_delay_s": max(0.0, float(raw.get("max_spawn_delay_s", 8.0))),
        "detour_offsets_m": detour_offsets,
        "detour_window_m": max(0.3, float(raw.get("detour_window_m", 2.2))),
        "max_detours_per_route": max(0, int(raw.get("max_detours_per_route", 2))),
        "candidate_pool_multiplier": max(1.0, float(raw.get("candidate_pool_multiplier", 1.0))),
        "candidate_pool_extra": max(0, int(raw.get("candidate_pool_extra", 0))),
    }


def _try_apply_collision_detour(
    route: dict[str, Any],
    conflict: dict[str, Any],
    *,
    scheduled: list[dict[str, Any]],
    min_separation_m: float,
    time_step_s: float,
    detour_offsets_m: list[float],
    detour_window_m: float,
    polygons: list[list[Vec2]],
    sample_spacing_m: float,
) -> dict[str, Any] | None:
    distance_m = conflict.get("route_a_distance_m")
    try:
        center_distance_m = float(distance_m)
    except (TypeError, ValueError):
        return None

    vertices = _route_vertices(route)
    route_length_m = _route_length(vertices)
    if route_length_m <= detour_window_m * 1.5 + _EPS:
        return None

    candidate_vertices: list[tuple[str, float, list[Vec3]]] = []
    if center_distance_m < detour_window_m:
        for trim_m in (detour_window_m, detour_window_m * 1.5, detour_window_m * 2.0):
            if trim_m < route_length_m - detour_window_m:
                candidate_vertices.append(("start_trim", trim_m, _trim_route_start(vertices, trim_m)))

    for offset_m in detour_offsets_m:
        candidate_vertices.append(
            (
                "local_detour",
                float(offset_m),
                _route_with_local_detour(
                    vertices,
                    center_distance_m=center_distance_m,
                    lateral_offset_m=float(offset_m),
                    window_m=detour_window_m,
                ),
            )
        )

    best_candidate: dict[str, Any] | None = None
    best_distance = float(conflict.get("distance_m") or -1.0)
    for action, value, detour_vertices in candidate_vertices:
        if len(detour_vertices) < 2:
            continue
        if not _route_within_zones(
            detour_vertices,
            polygons,
            margin_m=0.0,
            sample_spacing_m=sample_spacing_m,
        ):
            continue
        candidate = copy.deepcopy(route)
        candidate["vertices"] = [[x, y, z] for x, y, z in detour_vertices]
        metadata = candidate.setdefault("metadata", {})
        detours = list(metadata.get("collision_rehearsal_detours") or [])
        record: dict[str, Any] = {
            "action": action,
            "center_distance_m": center_distance_m,
            "window_m": detour_window_m,
            "conflict_time_s": conflict.get("time_s"),
            "conflict_route_id": conflict.get("route_b"),
        }
        if action == "start_trim":
            metadata["start_offset_m"] = _metadata_float(metadata, "start_offset_m", 0.0) + value
            record["trim_m"] = value
        else:
            record["lateral_offset_m"] = value
        detours.append(record)
        metadata["collision_rehearsal_detours"] = detours
        metadata["length"] = _route_length(detour_vertices)

        remaining_conflict = _first_rehearsal_conflict(
            candidate,
            scheduled,
            min_separation_m=min_separation_m,
            time_step_s=time_step_s,
        )
        if remaining_conflict is None:
            return candidate
        remaining_distance = float(remaining_conflict.get("distance_m") or 0.0)
        if remaining_distance > best_distance + _EPS:
            best_distance = remaining_distance
            best_candidate = candidate
    return best_candidate


def _route_with_local_detour(
    vertices: list[Vec3],
    *,
    center_distance_m: float,
    lateral_offset_m: float,
    window_m: float,
) -> list[Vec3]:
    total_length = _route_length(vertices)
    if len(vertices) < 2 or total_length <= _EPS:
        return list(vertices)
    start_distance = max(0.0, center_distance_m - window_m)
    end_distance = min(total_length, center_distance_m + window_m)
    if end_distance - start_distance <= _EPS:
        return list(vertices)

    p0 = _point_at_route_distance(vertices, start_distance)
    p1 = _point_at_route_distance(vertices, end_distance)
    c0 = _point_at_route_distance(vertices, center_distance_m)
    q0 = _point_at_route_distance(vertices, start_distance + (end_distance - start_distance) * 0.33)
    q1 = _point_at_route_distance(vertices, start_distance + (end_distance - start_distance) * 0.67)
    if p0 is None or p1 is None or c0 is None or q0 is None or q1 is None:
        return list(vertices)

    direction = _route_direction_at_distance(vertices, center_distance_m)
    normal = (-direction[1], direction[0])
    detour_points = [
        p0,
        (q0[0] + normal[0] * lateral_offset_m * 0.65, q0[1] + normal[1] * lateral_offset_m * 0.65, q0[2]),
        (c0[0] + normal[0] * lateral_offset_m, c0[1] + normal[1] * lateral_offset_m, c0[2]),
        (q1[0] + normal[0] * lateral_offset_m * 0.65, q1[1] + normal[1] * lateral_offset_m * 0.65, q1[2]),
        p1,
    ]

    result: list[Vec3] = []
    cumulative = 0.0
    if start_distance > _EPS:
        result.append(vertices[0])
    for index in range(len(vertices) - 1):
        seg_len = _distance_3d(vertices[index], vertices[index + 1])
        next_cumulative = cumulative + seg_len
        if _EPS < next_cumulative < start_distance - _EPS:
            result.append(vertices[index + 1])
        cumulative = next_cumulative
    result.extend(detour_points)
    cumulative = 0.0
    for index in range(len(vertices) - 1):
        seg_len = _distance_3d(vertices[index], vertices[index + 1])
        next_cumulative = cumulative + seg_len
        if next_cumulative > end_distance + _EPS:
            result.append(vertices[index + 1])
        cumulative = next_cumulative
    return _dedupe_consecutive_vertices(result)


def _route_direction_at_distance(vertices: list[Vec3], distance_m: float) -> Vec2:
    if len(vertices) < 2:
        return (1.0, 0.0)
    remaining = max(0.0, float(distance_m))
    for index in range(len(vertices) - 1):
        start = vertices[index]
        end = vertices[index + 1]
        segment_length = _distance_3d(start, end)
        if segment_length <= _EPS:
            continue
        if remaining <= segment_length + _EPS:
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            length = math.hypot(dx, dy)
            return (dx / length, dy / length) if length > _EPS else (1.0, 0.0)
        remaining -= segment_length
    start = vertices[-2]
    end = vertices[-1]
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    return (dx / length, dy / length) if length > _EPS else (1.0, 0.0)


def _dedupe_consecutive_vertices(vertices: list[Vec3]) -> list[Vec3]:
    result: list[Vec3] = []
    for vertex in vertices:
        if result and _distance_3d(result[-1], vertex) <= _EPS:
            continue
        result.append(vertex)
    return result


def _first_rehearsal_conflict(
    candidate: dict[str, Any],
    scheduled: list[dict[str, Any]],
    *,
    min_separation_m: float,
    time_step_s: float,
) -> dict[str, Any] | None:
    for other in scheduled:
        conflict = _pair_rehearsal_conflict(
            candidate,
            other,
            min_separation_m=min_separation_m,
            time_step_s=time_step_s,
        )
        if conflict is not None:
            return conflict
    return None


def _collect_rehearsal_conflicts(
    routes: list[dict[str, Any]],
    *,
    min_separation_m: float,
    time_step_s: float,
    max_records: int,
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for left_index, left in enumerate(routes):
        for right in routes[left_index + 1 :]:
            conflict = _pair_rehearsal_conflict(
                left,
                right,
                min_separation_m=min_separation_m,
                time_step_s=time_step_s,
            )
            if conflict is None:
                continue
            conflicts.append(conflict)
            if len(conflicts) >= max_records:
                return conflicts
    return conflicts


def _pair_rehearsal_conflict(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    min_separation_m: float,
    time_step_s: float,
) -> dict[str, Any] | None:
    left_start, left_end = _route_active_window(left)
    right_start, right_end = _route_active_window(right)
    start_s = max(left_start, right_start)
    end_s = min(left_end, right_end)
    if end_s + _EPS < start_s:
        return None

    steps = max(1, int(math.ceil((end_s - start_s) / time_step_s)))
    for step in range(steps + 1):
        t_s = min(end_s, start_s + step * time_step_s)
        left_distance = _route_distance_at_time(left, t_s)
        right_distance = _route_distance_at_time(right, t_s)
        if left_distance is None or right_distance is None:
            continue
        left_pos = _point_at_route_distance(_route_vertices(left), left_distance)
        right_pos = _point_at_route_distance(_route_vertices(right), right_distance)
        if left_pos is None or right_pos is None:
            continue
        distance_m = _distance_2d(_xy(left_pos), _xy(right_pos))
        if distance_m + _EPS < min_separation_m:
            return {
                "time_s": t_s,
                "distance_m": distance_m,
                "min_separation_m": min_separation_m,
                "route_a": _route_id(left),
                "route_b": _route_id(right),
                "route_a_distance_m": left_distance,
                "route_b_distance_m": right_distance,
            }
    return None


def _route_active_window(route: dict[str, Any]) -> tuple[float, float]:
    metadata = route.get("metadata") if isinstance(route.get("metadata"), dict) else {}
    spawn_s = _metadata_float(metadata, "spawn_time_s", 0.0)
    speed_mps = max(0.0, _metadata_float(metadata, "speed_mps", 1.0))
    length_m = _route_length(_route_vertices(route))
    if speed_mps <= _EPS or length_m <= _EPS:
        return (spawn_s, spawn_s)
    return (spawn_s, spawn_s + length_m / speed_mps)


def _route_distance_at_time(route: dict[str, Any], time_s: float) -> float | None:
    metadata = route.get("metadata") if isinstance(route.get("metadata"), dict) else {}
    spawn_s = _metadata_float(metadata, "spawn_time_s", 0.0)
    speed_mps = max(0.0, _metadata_float(metadata, "speed_mps", 1.0))
    vertices = _route_vertices(route)
    length_m = _route_length(vertices)
    if time_s + _EPS < spawn_s or speed_mps <= _EPS or length_m <= _EPS:
        return None
    raw_distance_m = (time_s - spawn_s) * speed_mps
    route_mode = str(metadata.get("route_mode") or "once").lower()
    if route_mode in {"loop", "repeat"}:
        return raw_distance_m % length_m
    if raw_distance_m >= length_m - _EPS:
        return None
    return raw_distance_m


def _route_position_at_time(route: dict[str, Any], time_s: float) -> Vec3 | None:
    distance_m = _route_distance_at_time(route, time_s)
    if distance_m is None:
        return None
    return _point_at_route_distance(_route_vertices(route), distance_m)


def _point_at_route_distance(vertices: list[Vec3], distance_m: float) -> Vec3 | None:
    if not vertices:
        return None
    if len(vertices) == 1 or distance_m <= _EPS:
        return vertices[0]
    remaining = float(distance_m)
    for index in range(len(vertices) - 1):
        start = vertices[index]
        end = vertices[index + 1]
        segment_length = _distance_3d(start, end)
        if segment_length <= _EPS:
            continue
        if remaining > segment_length:
            remaining -= segment_length
            continue
        t = max(0.0, min(1.0, remaining / segment_length))
        return (
            start[0] + (end[0] - start[0]) * t,
            start[1] + (end[1] - start[1]) * t,
            start[2] + (end[2] - start[2]) * t,
        )
    return vertices[-1]


def _dedupe_sorted_values(values: list[float]) -> list[float]:
    result: list[float] = []
    for value in sorted(max(0.0, min(1.0, float(item))) for item in values):
        if not result or abs(result[-1] - value) > 1e-6:
            result.append(value)
    return result


def _lerp3(a: Vec3, b: Vec3, t: float) -> Vec3:
    return (
        float(a[0]) + (float(b[0]) - float(a[0])) * t,
        float(a[1]) + (float(b[1]) - float(a[1])) * t,
        float(a[2]) + (float(b[2]) - float(a[2])) * t,
    )


def _segment_intersection_params(a: Vec3, b: Vec3, c: Vec3, d: Vec3) -> tuple[float, float] | None:
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


def _split_walkable_segments(walkable_lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for line_index, line in enumerate(walkable_lines):
        vertices = _route_vertices(line)
        for vertex_index in range(1, len(vertices)):
            start = vertices[vertex_index - 1]
            end = vertices[vertex_index]
            if _distance_3d(start, end) <= _EPS:
                continue
            segments.append(
                {
                    "start": start,
                    "end": end,
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


def _node_key(point: Vec3, tolerance: float) -> tuple[int, int, int]:
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
    nodes: list[Vec3] = []
    node_by_key: dict[tuple[int, int, int], int] = {}
    edges: dict[tuple[int, int], dict[str, Any]] = {}
    adjacency: dict[int, dict[int, float]] = {}

    def node_id(point: Vec3) -> int:
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
            length = _distance_3d(start, end)
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

    return {"nodes": nodes, "edges": list(edges.values()), "adjacency": adjacency}


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


def _component_edge_length(component: list[int], edges: list[dict[str, Any]]) -> float:
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
    nodes: list[Vec3],
    adjacency: dict[int, dict[int, float]],
    target_length: float,
) -> list[Vec3]:
    vertices = [nodes[path[0]]]
    remaining = float(target_length)
    for index in range(1, len(path)):
        start_id = path[index - 1]
        end_id = path[index]
        edge_length = float(adjacency[start_id][end_id])
        if remaining >= edge_length - 1e-6:
            vertices.append(nodes[end_id])
            remaining -= edge_length
            continue
        if remaining > 1e-6:
            t = remaining / edge_length
            vertices.append(_lerp3(nodes[start_id], nodes[end_id], t))
        break
    return vertices


def _round_robin_routes_by_region(routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    region_order: list[str] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for route in routes:
        region = _route_region(route)
        if region not in grouped:
            grouped[region] = []
            region_order.append(region)
        grouped[region].append(route)

    ordered: list[dict[str, Any]] = []
    index = 0
    while True:
        appended = False
        for region in region_order:
            bucket = grouped[region]
            if index < len(bucket):
                ordered.append(bucket[index])
                appended = True
        if not appended:
            break
        index += 1
    return ordered


def _iter_route_offset_candidates(
    routes: list[dict[str, Any]],
    offsets: list[float],
    *,
    mode: str,
):
    if mode in {"offset_round_robin", "offset-round-robin", "offset_first"}:
        if not offsets:
            return
        offset_count = len(offsets)
        for offset_round in range(offset_count):
            for route_index, route in enumerate(routes):
                offset_index = (route_index + offset_round) % offset_count
                yield route, offsets[offset_index], offset_index
        return

    if mode in {"route_round_robin", "route-round-robin", "route_first"}:
        for route in routes:
            for offset_index, offset_m in enumerate(offsets):
                yield route, offset_m, offset_index
        return

    zero_offsets = [(index, offset) for index, offset in enumerate(offsets) if abs(offset) <= _EPS]
    side_offsets = [(index, offset) for index, offset in enumerate(offsets) if abs(offset) > _EPS]
    for offset_pass in (zero_offsets, side_offsets):
        for route in routes:
            for offset_index, offset_m in offset_pass:
                yield route, offset_m, offset_index


def _passes_route_spacing(
    vertices: list[Vec3],
    *,
    parent_id: str,
    selected_geometries: list[tuple[str, list[Vec3]]],
    route_clearance_m: float,
    route_endpoint_ignore_m: float,
    parallel_clearance_m: float,
) -> bool:
    for selected_parent_id, selected_vertices in selected_geometries:
        if selected_parent_id == parent_id:
            required = parallel_clearance_m
            distance = _route_distance_2d(vertices, selected_vertices)
        else:
            required = route_clearance_m
            distance = _sampled_route_distance_2d(
                vertices,
                selected_vertices,
                endpoint_ignore_m=route_endpoint_ignore_m,
            )
        if distance + _EPS < required:
            return False
    return True


def _route_within_zones(
    vertices: list[Vec3],
    polygons: list[list[Vec2]],
    *,
    margin_m: float,
    sample_spacing_m: float,
) -> bool:
    if not polygons:
        return True
    samples = _route_samples(vertices, sample_spacing_m)
    last_index = len(samples) - 1
    for index, sample in enumerate(samples):
        # Entrances and street-corner terminals often lie on the dynamic-zone
        # boundary. Interior samples keep the pedestrian-radius margin.
        sample_margin = 0.0 if index in (0, last_index) else margin_m
        if not _point_in_zone_union(sample, polygons, margin_m=sample_margin):
            return False
    return True


def _point_in_zone_union(
    point: Vec3,
    polygons: list[list[Vec2]],
    *,
    margin_m: float,
) -> bool:
    point2 = (point[0], point[1])
    containing_count = 0
    best_clearance = -1.0
    for polygon in polygons:
        if _point_in_or_on_polygon(point2, polygon):
            containing_count += 1
            best_clearance = max(best_clearance, _point_polygon_clearance(point2, polygon))
    if containing_count == 0:
        return False
    if margin_m <= _EPS:
        return True
    # Adjacent dynamic strips meet at their shared boundary. Treat those
    # junctions as valid even though each individual rectangle has zero
    # boundary clearance at the exact shared edge.
    return best_clearance + _EPS >= margin_m or containing_count >= 2


def _route_samples(vertices: list[Vec3], spacing_m: float) -> list[Vec3]:
    samples: list[Vec3] = []
    for index in range(len(vertices) - 1):
        start = vertices[index]
        end = vertices[index + 1]
        if not samples:
            samples.append(start)
        length = _distance_3d(start, end)
        steps = max(1, int(math.ceil(length / spacing_m)))
        for step in range(1, steps + 1):
            t = step / steps
            samples.append(
                (
                    start[0] + (end[0] - start[0]) * t,
                    start[1] + (end[1] - start[1]) * t,
                    start[2] + (end[2] - start[2]) * t,
                )
            )
    return samples


def _route_start_offset(
    vertices: list[Vec3],
    *,
    route: dict[str, Any],
    scenario_name: str,
    sequence: int,
    start_offset_range_m: tuple[float, float] | None,
    min_remaining_length_m: float,
) -> float:
    if start_offset_range_m is None:
        return 0.0
    total_length = _route_length(vertices)
    max_allowed = max(0.0, total_length - max(0.0, min_remaining_length_m))
    if max_allowed <= _EPS:
        return 0.0
    requested = _range_value(
        start_offset_range_m,
        default=0.0,
        parts=(scenario_name, _route_id(route), sequence, "start_offset"),
    )
    return max(0.0, min(max_allowed, requested))


def _trim_route_start(vertices: list[Vec3], distance_m: float) -> list[Vec3]:
    if len(vertices) < 2 or distance_m <= _EPS:
        return list(vertices)
    remaining = float(distance_m)
    for index in range(len(vertices) - 1):
        start = vertices[index]
        end = vertices[index + 1]
        segment_length = _distance_3d(start, end)
        if segment_length <= _EPS:
            continue
        if remaining >= segment_length:
            remaining -= segment_length
            continue
        t = remaining / segment_length
        trimmed_start = (
            start[0] + (end[0] - start[0]) * t,
            start[1] + (end[1] - start[1]) * t,
            start[2] + (end[2] - start[2]) * t,
        )
        return [trimmed_start, *vertices[index + 1 :]]
    return list(vertices[-1:])


def _offset_route_vertices(vertices: list[Vec3], offset_m: float) -> list[Vec3]:
    if abs(offset_m) <= _EPS:
        return list(vertices)
    normals = _vertex_normals(vertices)
    return [
        (point[0] + normal[0] * offset_m, point[1] + normal[1] * offset_m, point[2])
        for point, normal in zip(vertices, normals)
    ]


def _vertex_normals(vertices: list[Vec3]) -> list[Vec2]:
    segment_normals: list[Vec2] = []
    for index in range(len(vertices) - 1):
        segment_normals.append(_segment_normal(vertices[index], vertices[index + 1]))
    if not segment_normals:
        return [(0.0, 0.0) for _ in vertices]
    normals: list[Vec2] = []
    for index in range(len(vertices)):
        if index == 0:
            normals.append(segment_normals[0])
        elif index == len(vertices) - 1:
            normals.append(segment_normals[-1])
        else:
            a = segment_normals[index - 1]
            b = segment_normals[index]
            nx = a[0] + b[0]
            ny = a[1] + b[1]
            length = math.hypot(nx, ny)
            normals.append((nx / length, ny / length) if length > _EPS else b)
    return normals


def _segment_normal(a: Vec3, b: Vec3) -> Vec2:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length = math.hypot(dx, dy)
    if length <= _EPS:
        return (0.0, 0.0)
    return (-dy / length, dx / length)


def _truncate_route(vertices: list[Vec3], max_length_m: float) -> list[Vec3]:
    if len(vertices) < 2 or max_length_m <= _EPS:
        return list(vertices[:1])
    truncated = [vertices[0]]
    remaining = float(max_length_m)
    for index in range(len(vertices) - 1):
        start = vertices[index]
        end = vertices[index + 1]
        segment_length = _distance_3d(start, end)
        if segment_length <= _EPS:
            continue
        if remaining >= segment_length:
            truncated.append(end)
            remaining -= segment_length
            continue
        t = remaining / segment_length
        truncated.append(
            (
                start[0] + (end[0] - start[0]) * t,
                start[1] + (end[1] - start[1]) * t,
                start[2] + (end[2] - start[2]) * t,
            )
        )
        break
    return truncated


def _zone_polygons(dynamic_zones: list[dict[str, Any]]) -> list[list[Vec2]]:
    polygons: list[list[Vec2]] = []
    for zone in dynamic_zones:
        geometry = zone.get("geometry") if isinstance(zone, dict) else None
        coords = geometry.get("coordinates") if isinstance(geometry, dict) else None
        points = [_point2(item) for item in (coords or [])]
        polygon = [point for point in points if point is not None]
        if len(polygon) > 1 and _distance_2d(polygon[0], polygon[-1]) <= _EPS:
            polygon = polygon[:-1]
        if len(polygon) >= 3:
            polygons.append(polygon)
    return polygons


def _route_vertices(route: dict[str, Any]) -> list[Vec3]:
    raw_vertices = route.get("vertices") or route.get("waypoints") or []
    vertices: list[Vec3] = []
    for item in raw_vertices:
        point = _point3(item)
        if point is not None:
            vertices.append(point)
    return vertices


def _route_length(vertices: list[Vec3]) -> float:
    return sum(_distance_3d(vertices[i], vertices[i + 1]) for i in range(len(vertices) - 1))


def _route_distance_2d(a: list[Vec3], b: list[Vec3]) -> float:
    if len(a) < 2 or len(b) < 2:
        return float("inf")
    best = float("inf")
    for i in range(len(a) - 1):
        for j in range(len(b) - 1):
            best = min(best, _segment_distance_2d(_xy(a[i]), _xy(a[i + 1]), _xy(b[j]), _xy(b[j + 1])))
    return best


def _sampled_route_distance_2d(
    a: list[Vec3],
    b: list[Vec3],
    *,
    endpoint_ignore_m: float,
) -> float:
    samples_a = _interior_route_samples(a, endpoint_ignore_m=endpoint_ignore_m)
    samples_b = _interior_route_samples(b, endpoint_ignore_m=endpoint_ignore_m)
    if not samples_a or not samples_b:
        return _route_distance_2d(a, b)
    best = float("inf")
    for point in samples_a:
        best = min(best, _point_route_distance_2d(point, b))
    for point in samples_b:
        best = min(best, _point_route_distance_2d(point, a))
    return best


def _interior_route_samples(
    vertices: list[Vec3],
    *,
    endpoint_ignore_m: float,
    spacing_m: float = 0.75,
) -> list[Vec2]:
    total_length = _route_length(vertices)
    if total_length <= endpoint_ignore_m * 2.0 + _EPS:
        return []
    samples: list[Vec2] = []
    distance_before = 0.0
    for index in range(len(vertices) - 1):
        start = vertices[index]
        end = vertices[index + 1]
        segment_length = _distance_3d(start, end)
        if segment_length <= _EPS:
            continue
        steps = max(1, int(math.ceil(segment_length / spacing_m)))
        for step in range(steps + 1):
            t = step / steps
            distance_along = distance_before + segment_length * t
            if (
                distance_along <= endpoint_ignore_m + _EPS
                or distance_along >= total_length - endpoint_ignore_m - _EPS
            ):
                continue
            samples.append(
                (
                    start[0] + (end[0] - start[0]) * t,
                    start[1] + (end[1] - start[1]) * t,
                )
            )
        distance_before += segment_length
    return samples


def _point_route_distance_2d(point: Vec2, vertices: list[Vec3]) -> float:
    if len(vertices) < 2:
        return float("inf")
    return min(
        _point_segment_distance(point, _xy(vertices[index]), _xy(vertices[index + 1]))
        for index in range(len(vertices) - 1)
    )


def _segment_distance_2d(a: Vec2, b: Vec2, c: Vec2, d: Vec2) -> float:
    if _segments_intersect(a, b, c, d):
        return 0.0
    return min(
        _point_segment_distance(a, c, d),
        _point_segment_distance(b, c, d),
        _point_segment_distance(c, a, b),
        _point_segment_distance(d, a, b),
    )


def _segments_intersect(a: Vec2, b: Vec2, c: Vec2, d: Vec2) -> bool:
    def orient(p: Vec2, q: Vec2, r: Vec2) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def on_segment(p: Vec2, q: Vec2, r: Vec2) -> bool:
        return (
            min(p[0], r[0]) - _EPS <= q[0] <= max(p[0], r[0]) + _EPS
            and min(p[1], r[1]) - _EPS <= q[1] <= max(p[1], r[1]) + _EPS
        )

    o1 = orient(a, b, c)
    o2 = orient(a, b, d)
    o3 = orient(c, d, a)
    o4 = orient(c, d, b)
    if o1 * o2 < -_EPS and o3 * o4 < -_EPS:
        return True
    return (
        abs(o1) <= _EPS and on_segment(a, c, b)
        or abs(o2) <= _EPS and on_segment(a, d, b)
        or abs(o3) <= _EPS and on_segment(c, a, d)
        or abs(o4) <= _EPS and on_segment(c, b, d)
    )


def _point_in_or_on_polygon(point: Vec2, polygon: list[Vec2]) -> bool:
    if _point_polygon_clearance(point, polygon) <= _EPS:
        return True
    inside = False
    x, y = point
    j = len(polygon) - 1
    for i, pi in enumerate(polygon):
        pj = polygon[j]
        if ((pi[1] > y) != (pj[1] > y)) and (
            x < (pj[0] - pi[0]) * (y - pi[1]) / (pj[1] - pi[1]) + pi[0]
        ):
            inside = not inside
        j = i
    return inside


def _point_polygon_clearance(point: Vec2, polygon: list[Vec2]) -> float:
    if len(polygon) < 2:
        return 0.0
    return min(
        _point_segment_distance(point, polygon[index], polygon[(index + 1) % len(polygon)])
        for index in range(len(polygon))
    )


def _point_segment_distance(point: Vec2, start: Vec2, end: Vec2) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_sq = dx * dx + dy * dy
    if length_sq <= _EPS:
        return _distance_2d(point, start)
    t = max(
        0.0,
        min(1.0, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_sq),
    )
    closest = (start[0] + t * dx, start[1] + t * dy)
    return _distance_2d(point, closest)


def _route_key(vertices: list[Vec3]) -> tuple[tuple[int, int, int], ...]:
    return tuple(
        (round(point[0] * 1000), round(point[1] * 1000), round(point[2] * 1000))
        for point in vertices
    )


def _route_id(route: dict[str, Any]) -> str:
    return str(route.get("route_id") or route.get("raw_name") or "route")


def _route_region(route: dict[str, Any]) -> str:
    metadata = route.get("metadata") if isinstance(route.get("metadata"), dict) else {}
    return str(metadata.get("source_region_id") or route.get("region_id") or "region")


def _rejection(route: dict[str, Any], offset_m: float, reason: str) -> dict[str, Any]:
    return {"route_id": _route_id(route), "offset_m": float(offset_m), "reason": reason}


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z_]+", "_", str(value)).strip("_")
    if not cleaned:
        cleaned = "demo_people_route"
    if cleaned[0].isdigit():
        cleaned = f"route_{cleaned}"
    return cleaned[:180]


def _float_list(value: Any, *, default: list[float]) -> list[float]:
    if value is None:
        return list(default)
    if not isinstance(value, (list, tuple)):
        return list(default)
    result: list[float] = []
    for item in value:
        try:
            result.append(float(item))
        except (TypeError, ValueError):
            continue
    return result


def _metadata_float(metadata: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(metadata.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def _float_range(value: Any) -> tuple[float, float] | None:
    values = _float_list(value, default=[])
    if len(values) < 2:
        return None
    low = min(values[0], values[1])
    high = max(values[0], values[1])
    return (float(low), float(high))


def _range_value(
    range_value: tuple[float, float] | None,
    *,
    default: float,
    parts: tuple[Any, ...],
) -> float:
    if range_value is None:
        return float(default)
    low, high = range_value
    if high <= low + _EPS:
        return float(low)
    return float(low + (high - low) * _stable_unit_float(*parts))


def _jittered_offset(
    offset_m: float,
    *,
    route: dict[str, Any],
    scenario_name: str,
    sequence: int,
    offset_index: int,
    jitter_m: float,
    offset_range_m: tuple[float, float] | None,
) -> float:
    value = float(offset_m)
    if jitter_m > _EPS:
        unit = _stable_unit_float(
            scenario_name,
            _route_id(route),
            sequence,
            offset_index,
            "offset",
        )
        value += (unit * 2.0 - 1.0) * jitter_m
    if offset_range_m is not None:
        value = max(offset_range_m[0], min(offset_range_m[1], value))
    return value


def _stable_unit_float(*parts: Any) -> float:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    integer = int.from_bytes(digest[:8], "big")
    return integer / float(2**64 - 1)


def _optional_positive_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0.0 else None


def _point2(value: Any) -> Vec2 | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None


def _point3(value: Any) -> Vec3 | None:
    if isinstance(value, dict):
        try:
            return (
                float(value["x"]),
                float(value["y"]),
                float(value.get("z", 0.0)),
            )
        except (KeyError, TypeError, ValueError):
            return None
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        z_value = value[2] if len(value) >= 3 else 0.0
        return (float(value[0]), float(value[1]), float(z_value))
    except (TypeError, ValueError):
        return None


def _xy(point: Vec3) -> Vec2:
    return (point[0], point[1])


def _distance_2d(a: Vec2, b: Vec2) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _distance_3d(a: Vec3, b: Vec3) -> float:
    return math.sqrt(
        (b[0] - a[0]) ** 2
        + (b[1] - a[1]) ** 2
        + (b[2] - a[2]) ** 2
    )
