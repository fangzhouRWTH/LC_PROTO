import math

import numpy as np

from .isaac_adaptor import isaac_context as iscctx


class ChaseViewportCamera:
    def __init__(
        self,
        ctx: iscctx.IsaacContext,
        distance=5.0,
        height=2.5,
        target_height=0.8,
        camera_prim_path="/OmniverseKit_Persp",
        smoothing=0.15,
    ):
        self.set_camera_view = ctx.isaac_core_utils.viewports.set_camera_view
        self.distance = distance
        self.height = height
        self.target_height = target_height
        self.camera_prim_path = camera_prim_path
        self.smoothing = smoothing

        self._eye = None
        self._target = None

    def update(self, robot_pos, robot_yaw_rad):
        x, y, z = robot_pos

        forward = np.array(
            [
                math.cos(robot_yaw_rad),
                math.sin(robot_yaw_rad),
                0.0,
            ],
            dtype=np.float32,
        )

        target = np.array(
            [
                x,
                y,
                z + self.target_height,
            ],
            dtype=np.float32,
        )

        eye = target - forward * self.distance
        eye[2] = z + self.height

        if self._eye is None:
            self._eye = eye
            self._target = target
        else:
            a = self.smoothing
            self._eye = (1.0 - a) * self._eye + a * eye
            self._target = (1.0 - a) * self._target + a * target

        self.set_camera_view(
            eye=self._eye.tolist(),
            target=self._target.tolist(),
            camera_prim_path=self.camera_prim_path,
        )
