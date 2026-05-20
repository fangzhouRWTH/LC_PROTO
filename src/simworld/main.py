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
    parser.add_argument("--robot-name", default="spot_demo")
    parser.add_argument("--warmup-frames", type=int, default=30)
    parser.add_argument("--camera-prim-path", default="/OmniverseKit_Persp")
    args, _ = parser.parse_known_args()
    return args


if __name__ == "__main__":
    args = parse_args()
    simulation.run(
        simulation.SimulationConfig(
            usd_path=args.scene_usd,
            robot_name=args.robot_name,
            warmup_frames=args.warmup_frames,
            camera_prim_path=args.camera_prim_path,
        )
    )
