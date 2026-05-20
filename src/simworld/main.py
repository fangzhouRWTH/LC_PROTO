import argparse
import pathlib

import isaac_env.simulation as simulation


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
        )
    )
