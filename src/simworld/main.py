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
        )
    )
