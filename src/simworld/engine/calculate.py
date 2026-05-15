import math
import numpy as np


def yaw_from_quat_wxyz(q):
    """
    Convert quaternion [w, x, y, z] to yaw angle around Z axis.
    """
    w, x, y, z = q

    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)

    return math.atan2(siny_cosp, cosy_cosp)
