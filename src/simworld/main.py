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
            enable_dynamic_agents=args.enable_dynamic_agents,
            dynamic_agent_backend=args.dynamic_agent_backend,
            dynamic_max_pedestrian_actors=args.dynamic_max_pedestrian_actors,
            dynamic_max_vehicle_actors=args.dynamic_max_vehicle_actors,
            dynamic_pedestrian_speed_mps=args.dynamic_pedestrian_speed_mps,
            dynamic_vehicle_speed_mps=args.dynamic_vehicle_speed_mps,
            dynamic_spawn_time_s=args.dynamic_spawn_time_s,
            dynamic_route_mode=args.dynamic_route_mode,
            dynamic_placeholder_visibility=args.dynamic_placeholder_visibility,
            dynamic_pedestrian_visual=args.dynamic_pedestrian_visual,
            dynamic_pedestrian_asset_path=args.dynamic_pedestrian_asset_path,
            dynamic_pedestrian_asset_scale=args.dynamic_pedestrian_asset_scale,
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
        )
    )
