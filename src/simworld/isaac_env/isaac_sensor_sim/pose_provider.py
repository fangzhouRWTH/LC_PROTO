from __future__ import annotations

from .frame import Pose3D


def get_world_pose(prim_path: str) -> Pose3D:
    from ..isaac_adaptor import isaac_context as iscctx

    context = iscctx.get_isaac_context()
    stage = context.omni_usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("Cannot read sensor pose without an open USD stage.")

    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        raise RuntimeError(f"Invalid sensor prim path: {prim_path}")

    matrix = context.omni_usd.get_world_transform_matrix(prim)
    position = matrix.ExtractTranslation()
    quat = matrix.ExtractRotation().GetQuat()
    imaginary = quat.GetImaginary()

    return Pose3D(
        position=(float(position[0]), float(position[1]), float(position[2])),
        orientation_wxyz=(
            float(quat.GetReal()),
            float(imaginary[0]),
            float(imaginary[1]),
            float(imaginary[2]),
        ),
    )
