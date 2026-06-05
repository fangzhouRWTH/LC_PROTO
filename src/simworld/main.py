import argparse
import pathlib

import isaac_env.simulation as simulation


def parse_bool(value):
    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    raise argparse.ArgumentTypeError(
        "Expected a boolean value: true/false, yes/no, on/off, or 1/0."
    )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scene_usd",
        "--scene-usd",
        dest="scene_usd",
        type=pathlib.Path,
        default=simulation.DEFAULT_SCENE_USD,
    )
    parser.add_argument(
        "--robot-type",
        default=simulation.DEFAULT_ROBOT_TYPE,
        choices=simulation.available_robot_types(),
    )
    parser.add_argument("--robot-name", default=simulation.DEFAULT_ROBOT_NAME)
    parser.add_argument(
        "--warmup-frames",
        type=int,
        default=simulation.DEFAULT_WARMUP_FRAMES,
    )
    parser.add_argument(
        "--camera-prim-path",
        default=simulation.DEFAULT_CAMERA_PRIM_PATH,
    )
    parser.add_argument(
        "--chase-camera",
        nargs="?",
        const=True,
        type=parse_bool,
        default=simulation.DEFAULT_CHASE_CAMERA,
        help="Legacy option. Follow view is now managed by --sensor-profile.",
    )
    parser.add_argument(
        "--auto-play",
        nargs="?",
        const=True,
        type=parse_bool,
        default=simulation.DEFAULT_AUTO_PLAY,
        help="Start the simulation timeline automatically after scene setup.",
    )
    parser.add_argument(
        "--auto-play-min-frames",
        type=int,
        default=simulation.DEFAULT_AUTO_PLAY_MIN_FRAMES,
        help="Keep auto-play demos alive for at least this many frames.",
    )
    parser.add_argument(
        "--enable-dynamic-agents",
        nargs="?",
        const=True,
        type=parse_bool,
        default=simulation.DEFAULT_ENABLE_DYNAMIC_AGENTS,
    )
    parser.add_argument(
        "--dynamic-agent-backend",
        default=simulation.DEFAULT_DYNAMIC_AGENT_BACKEND,
        choices=simulation.available_dynamic_agent_backends(),
    )
    parser.add_argument(
        "--dynamic-max-pedestrian-actors",
        type=int,
        default=simulation.DEFAULT_DYNAMIC_MAX_PEDESTRIAN_ACTORS,
    )
    parser.add_argument(
        "--dynamic-max-vehicle-actors",
        type=int,
        default=simulation.DEFAULT_DYNAMIC_MAX_VEHICLE_ACTORS,
    )
    parser.add_argument(
        "--dynamic-pedestrian-speed-mps",
        type=float,
        default=simulation.DEFAULT_DYNAMIC_PEDESTRIAN_SPEED_MPS,
    )
    parser.add_argument(
        "--dynamic-vehicle-speed-mps",
        type=float,
        default=simulation.DEFAULT_DYNAMIC_VEHICLE_SPEED_MPS,
    )
    parser.add_argument(
        "--dynamic-spawn-time-s",
        type=float,
        default=simulation.DEFAULT_DYNAMIC_SPAWN_TIME_S,
    )
    parser.add_argument(
        "--dynamic-route-mode",
        default=simulation.DEFAULT_DYNAMIC_ROUTE_MODE,
        choices=("loop", "once", "stop_at_end", "stop-at-end", "ping_pong"),
    )
    parser.add_argument(
        "--dynamic-placeholder-visibility",
        default=simulation.DEFAULT_DYNAMIC_PLACEHOLDER_VISIBILITY,
        choices=("hidden", "visible"),
        help="Legacy alias for --placeholder-disposition (hidden|visible only).",
    )
    parser.add_argument(
        "--placeholder-disposition",
        default=None,
        choices=("hidden", "visible", "remove"),
        help=(
            "After preprocess: hide all placeholder prims (default), keep visible, "
            "or remove them from the stage."
        ),
    )
    parser.add_argument(
        "--dynamic-pedestrian-visual",
        default=simulation.DEFAULT_DYNAMIC_PEDESTRIAN_VISUAL,
        choices=("proxy", "asset"),
    )
    parser.add_argument(
        "--dynamic-pedestrian-asset-path",
        default=simulation.DEFAULT_DYNAMIC_PEDESTRIAN_ASSET_PATH,
    )
    parser.add_argument(
        "--dynamic-pedestrian-asset-scale",
        type=float,
        default=simulation.DEFAULT_DYNAMIC_PEDESTRIAN_ASSET_SCALE,
    )
    parser.add_argument(
        "--dynamic-pedestrian-animation",
        default=simulation.DEFAULT_DYNAMIC_PEDESTRIAN_ANIMATION,
        choices=("none", "clip"),
    )
    parser.add_argument(
        "--dynamic-pedestrian-animation-clip-path",
        default=simulation.DEFAULT_DYNAMIC_PEDESTRIAN_ANIMATION_CLIP_PATH,
    )
    parser.add_argument(
        "--dynamic-pedestrian-animation-time-scale",
        type=float,
        default=simulation.DEFAULT_DYNAMIC_PEDESTRIAN_ANIMATION_TIME_SCALE,
    )
    parser.add_argument(
        "--dynamic-vehicle-visual",
        default=simulation.DEFAULT_DYNAMIC_VEHICLE_VISUAL,
        choices=("proxy", "asset"),
    )
    parser.add_argument(
        "--dynamic-vehicle-asset-path",
        default=simulation.DEFAULT_DYNAMIC_VEHICLE_ASSET_PATH,
    )
    parser.add_argument(
        "--dynamic-vehicle-asset-scale",
        type=float,
        default=simulation.DEFAULT_DYNAMIC_VEHICLE_ASSET_SCALE,
    )
    parser.add_argument(
        "--weather",
        default=simulation.DEFAULT_WEATHER,
        choices=simulation.available_weather_names(),
        help="Weather lighting preset. Omit to choose a random preset.",
    )
    parser.add_argument(
        "--daytime",
        default=simulation.DEFAULT_DAYTIME,
        help=(
            "Preferred default sky time, such as "
            f"{', '.join(simulation.available_daytime_names())}; "
            "falls back to a random sky when unavailable for the weather."
        ),
    )
    parser.add_argument(
        "--sky-texture",
        type=pathlib.Path,
        default=None,
        help="Optional lat-long sky texture/HDRI for the weather dome light.",
    )
    parser.add_argument(
        "--sun-intensity",
        type=float,
        default=None,
        help="Override the weather preset sun intensity.",
    )
    parser.add_argument(
        "--sky-intensity",
        type=float,
        default=None,
        help="Override the weather preset dome light intensity.",
    )
    parser.add_argument(
        "--sky-exposure",
        type=float,
        default=None,
        help="Override the weather preset dome light exposure.",
    )
    parser.add_argument(
        "--weather-time-scale",
        type=float,
        default=simulation.DEFAULT_WEATHER_TIME_SCALE,
        help="Multiplier for time-varying weather lighting.",
    )
    parser.add_argument(
        "--weather-start-time",
        type=float,
        default=0.0,
        help="Initial weather-lighting time in seconds.",
    )
    parser.add_argument(
        "--sensor-profile",
        default=simulation.DEFAULT_SENSOR_PROFILE,
        choices=simulation.available_sensor_profiles(),
        help="Optional pseudo sensor profile to attach to the robot.",
    )
    parser.add_argument(
        "--active-sensor",
        default=simulation.DEFAULT_ACTIVE_SENSOR_ID,
        help=(
            "Initial active sensor id inside the selected rig, "
            "for example follow_view or spot_front_view."
        ),
    )
    parser.add_argument(
        "--sensor-diagnostics",
        nargs="?",
        const=True,
        type=parse_bool,
        default=simulation.DEFAULT_SENSOR_DIAGNOSTICS,
        help="Print active sensor frame diagnostics periodically.",
    )
    parser.add_argument(
        "--sensor-diagnostics-interval-s",
        type=float,
        default=simulation.DEFAULT_SENSOR_DIAGNOSTICS_INTERVAL_S,
        help="Seconds between sensor diagnostic log lines.",
    )
    parser.add_argument(
        "--sensor-debug-output-dir",
        type=pathlib.Path,
        default=simulation.DEFAULT_SENSOR_DEBUG_OUTPUT_DIR,
        help="Optional directory for active sensor PNG preview frames.",
    )
    parser.add_argument(
        "--sensor-debug-interval-s",
        type=float,
        default=simulation.DEFAULT_SENSOR_DEBUG_INTERVAL_S,
        help="Seconds between active sensor PNG preview writes.",
    )
    parser.add_argument(
        "--layout-backend",
        default=simulation.DEFAULT_LAYOUT_BACKEND,
        choices=simulation.available_layout_backends_list(),
        help="Static layout backend: legacy grid footprints or area_placement_methods.",
    )
    parser.add_argument(
        "--region-input-json",
        type=pathlib.Path,
        default=simulation.DEFAULT_REGION_INPUT_JSON,
        help=(
            "Region input JSON file or directory (proto / simworld.region_input.v1) "
            "for area_placement_methods."
        ),
    )
    parser.add_argument(
        "--placement-plan-json",
        type=pathlib.Path,
        default=simulation.DEFAULT_PLACEMENT_PLAN_JSON,
        help="Precomputed simworld.placement_output.v1 JSON; skips layout generation.",
    )
    parser.add_argument(
        "--layout-output-dir",
        type=pathlib.Path,
        default=simulation.DEFAULT_LAYOUT_OUTPUT_DIR,
        help="Optional directory to write placement_output.json during prepare.",
    )
    parser.add_argument(
        "--use-dummy-public-space-assets",
        nargs="?",
        const=True,
        type=parse_bool,
        default=simulation.DEFAULT_USE_DUMMY_PUBLIC_SPACE_ASSETS,
        help="Use UsdGeom cubes for public-space placements (debug).",
    )
    parser.add_argument(
        "--public-space-dummy-size-m",
        type=float,
        default=simulation.DEFAULT_PUBLIC_SPACE_DUMMY_SIZE_M,
        help="Edge length for dummy public-space placeholder cubes.",
    )
    parser.add_argument(
        "--public-space-asset-name-map",
        type=pathlib.Path,
        default=simulation.DEFAULT_PUBLIC_SPACE_ASSET_NAME_MAP,
        help="JSON map from asset_candidates_name to USD paths.",
    )
    parser.add_argument(
        "--skip-legacy-placeholder-areas",
        nargs="?",
        const=True,
        type=parse_bool,
        default=simulation.DEFAULT_SKIP_LEGACY_PLACEHOLDER_AREAS,
        help=(
            "When using area_placement_methods, skip legacy plaza grid placement "
            "from placeholder_area_* prims."
        ),
    )
    args, _ = parser.parse_known_args()
    return args


if __name__ == "__main__":
    args = parse_args()
    simulation.run(
        simulation.SimulationConfig(
            usd_path=args.scene_usd,
            robot_type=args.robot_type,
            robot_name=args.robot_name,
            warmup_frames=args.warmup_frames,
            camera_prim_path=args.camera_prim_path,
            chase_camera=args.chase_camera,
            auto_play=args.auto_play,
            auto_play_min_frames=args.auto_play_min_frames,
            enable_dynamic_agents=args.enable_dynamic_agents,
            dynamic_agent_backend=args.dynamic_agent_backend,
            dynamic_max_pedestrian_actors=args.dynamic_max_pedestrian_actors,
            dynamic_max_vehicle_actors=args.dynamic_max_vehicle_actors,
            dynamic_pedestrian_speed_mps=args.dynamic_pedestrian_speed_mps,
            dynamic_vehicle_speed_mps=args.dynamic_vehicle_speed_mps,
            dynamic_spawn_time_s=args.dynamic_spawn_time_s,
            dynamic_route_mode=args.dynamic_route_mode,
            dynamic_placeholder_visibility=args.dynamic_placeholder_visibility,
            placeholder_disposition=args.placeholder_disposition,
            dynamic_pedestrian_visual=args.dynamic_pedestrian_visual,
            dynamic_pedestrian_asset_path=args.dynamic_pedestrian_asset_path,
            dynamic_pedestrian_asset_scale=args.dynamic_pedestrian_asset_scale,
            dynamic_pedestrian_animation=args.dynamic_pedestrian_animation,
            dynamic_pedestrian_animation_clip_path=args.dynamic_pedestrian_animation_clip_path,
            dynamic_pedestrian_animation_time_scale=args.dynamic_pedestrian_animation_time_scale,
            dynamic_vehicle_visual=args.dynamic_vehicle_visual,
            dynamic_vehicle_asset_path=args.dynamic_vehicle_asset_path,
            dynamic_vehicle_asset_scale=args.dynamic_vehicle_asset_scale,
            weather=args.weather,
            daytime=args.daytime,
            sky_texture_path=args.sky_texture,
            sun_intensity=args.sun_intensity,
            sky_intensity=args.sky_intensity,
            sky_exposure=args.sky_exposure,
            weather_time_scale=args.weather_time_scale,
            weather_start_time=args.weather_start_time,
            sensor_profile=args.sensor_profile,
            active_sensor_id=args.active_sensor,
            sensor_diagnostics=args.sensor_diagnostics,
            sensor_diagnostics_interval_s=args.sensor_diagnostics_interval_s,
            sensor_debug_output_dir=args.sensor_debug_output_dir,
            sensor_debug_interval_s=args.sensor_debug_interval_s,
            layout_backend=args.layout_backend,
            region_input_json=args.region_input_json,
            placement_plan_json=args.placement_plan_json,
            layout_output_dir=args.layout_output_dir,
            use_dummy_public_space_assets=args.use_dummy_public_space_assets,
            public_space_dummy_size_m=args.public_space_dummy_size_m,
            public_space_asset_name_map=args.public_space_asset_name_map,
            skip_legacy_placeholder_areas=args.skip_legacy_placeholder_areas,
        )
    )
