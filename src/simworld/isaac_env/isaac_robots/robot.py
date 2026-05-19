from abc import ABC, abstractmethod
from isaac_env.isaac_adaptor import isaac_context as iscctx
import carb
import numpy as np


def _normalize_vec3(v):
    length = v.GetLength()
    if length > 1e-8:
        v /= length
    return v


def get_prim_world_pose(prim_path: str):
    """
    Get world position and orientation vectors of a USD prim.

    Args:
        prim_path:
            USD prim path, e.g. "/World/Robot/Spot".
        local_forward_axis:
            Which local axis should be treated as the prim's forward direction.
            Default assumes local +X is forward.
        local_right_axis:
            Which local axis should be treated as the prim's right direction.
        local_up_axis:
            Which local axis should be treated as the prim's up direction.

    Returns:
        dict with:
            position: [x, y, z]
            forward: [x, y, z]
            right: [x, y, z]
            up: [x, y, z]
            rotation: Gf.Rotation
            matrix: Gf.Matrix4d
    """
    import pxr.Gf as Gf

    omni_usd = iscctx.get_isaac_context().omni_usd

    local_forward_axis = Gf.Vec3d(1.0, 0.0, 0.0)
    local_right_axis = Gf.Vec3d(0.0, -1.0, 0.0)
    local_up_axis = Gf.Vec3d(0.0, 0.0, 1.0)

    stage = omni_usd.get_context().get_stage()

    prim = stage.GetPrimAtPath(prim_path)

    if not prim.IsValid():
        raise RuntimeError(f"Invalid prim path: {prim_path}")

    world_mat = omni_usd.get_world_transform_matrix(prim)

    pos = world_mat.ExtractTranslation()
    rot = world_mat.ExtractRotation()

    forward = _normalize_vec3(rot.TransformDir(local_forward_axis))
    right = _normalize_vec3(rot.TransformDir(local_right_axis))
    up = _normalize_vec3(rot.TransformDir(local_up_axis))

    return {
        "position": [float(pos[0]), float(pos[1]), float(pos[2])],
        "forward": [float(forward[0]), float(forward[1]), float(forward[2])],
        "right": [float(right[0]), float(right[1]), float(right[2])],
        "up": [float(up[0]), float(up[1]), float(up[2])],
        "rotation": rot,
        "matrix": world_mat,
    }


def set_camera_view(
    eye: np.array,
    target: np.array,
    camera_prim_path: str = "/OmniverseKit_Persp",
    viewport_api=None,
) -> None:
    """Set the location and target for a camera prim in the stage given its path

    Args:
        eye (np.ndarray): Location of camera.
        target (np.ndarray,): Location of camera target.
        camera_prim_path (str, optional): Path to camera prim being set. Defaults to "/OmniverseKit_Persp".
    """
    omni_kit = iscctx.get_isaac_context().omni_kit
    create = iscctx.get_isaac_context().omni_kit.commands.create
    Sdf = iscctx.get_isaac_context().pxr_Sdf
    Gf = iscctx.get_isaac_context().pxr_gf
    try:
        get_active_viewport = omni_kit.viewport.utility.get_active_viewport
        ViewportCameraState = omni_kit.viewport.utility.camera_state.ViewportCameraState
        # from omni_kit.viewport.utility import get_active_viewport
        # from omni_kit.viewport.utility.camera_state import ViewportCameraState

        if viewport_api is None:
            viewport_api = get_active_viewport()
    except ImportError:
        carb.log_warn(
            "omni.kit.viewport.utility needs to be enabled before using this function"
        )
        return

    if viewport_api is None:
        carb.log_warn("could not get active viewport, cannot set camera view")
        return

    # get all inputs
    camera_position = np.asarray(eye, dtype=np.double)
    camera_target = np.asarray(target, dtype=np.double)
    prim = viewport_api.stage.GetPrimAtPath(camera_prim_path)

    # check if center of interest property exists, create if not
    coi_prop = prim.GetProperty("omni:kit:centerOfInterest")
    if not coi_prop or not coi_prop.IsValid():
        prim.CreateAttribute(
            "omni:kit:centerOfInterest",
            Sdf.ValueTypeNames.Vector3d,
            True,
            Sdf.VariabilityUniform,
        ).Set(Gf.Vec3d(0, 0, -10))

    # set camera prim position
    camera_state = ViewportCameraState(camera_prim_path, viewport_api)
    camera_state.set_position_world(
        Gf.Vec3d(camera_position[0], camera_position[1], camera_position[2]), True
    )

    # if camera target is not directly above or below camera, set target using omni.kit.viewport.utility
    if (camera_target[0:2] != camera_position[0:2]).any():
        camera_state.set_target_world(
            Gf.Vec3d(camera_target[0], camera_target[1], camera_target[2]), True
        )
    else:
        # if camera has an orient property, set it to look at target
        if prim.GetAttribute("xformOp:orient"):
            rotate_prop = prim.GetAttribute("xformOp:orient")
            # set orientation quaternion based on if camera is looking up or down
            quat = [
                0 if camera_target[2] >= camera_position[2] else 1,
                0,
                1 if camera_target[2] >= camera_position[2] else 0,
                0,
            ]

            # save new rotate property as double or float quaternion based on original rotate property type
            if rotate_prop.GetTypeName() == Sdf.ValueTypeNames.Quatd:
                new_rotate = Gf.Quatd(*quat)
            elif rotate_prop.GetTypeName() == Sdf.ValueTypeNames.Quatf:
                new_rotate = Gf.Quatf(*quat)
            else:
                # if rotate property is not float or double quaternion, log warning and return
                carb.log_warn("unknown orient type")
                return
        else:
            # else, use rotate property to set camera orientation
            # use up_down to determine if camera is looking up or down
            up_down = 180 if camera_target[2] >= camera_position[2] else 0

            # set potential rotate properties based on which rotate property could be used
            xyz_zyx = [0, up_down, 0]
            xzy_zxy = [0, 0, up_down]
            yxz_yzx = [up_down, 0, 0]

            # check which rotate property is being used
            rot = (
                xyz_zyx
                if prim.GetAttribute("xformOp:rotateXYZ")
                or prim.GetAttribute("xformOp:rotateZYX")
                else (
                    xzy_zxy
                    if prim.GetAttribute("xformOp:rotateXZY")
                    or prim.GetAttribute("xformOp:rotateZXY")
                    else (
                        yxz_yzx
                        if prim.GetAttribute("xformOp:rotateYXZ")
                        or prim.GetAttribute("xformOp:rotateYZX")
                        else None
                    )
                )
            )

            # if no rotate property is found, log warning and return
            if rot is None:
                carb.log_warn("no orient or rotate attributes found")
                return

            # set new rotate property
            rotate_prop = (
                prim.GetAttribute("xformOp:rotateXYZ")
                or prim.GetAttribute("xformOp:rotateXZY")
                or prim.GetAttribute("xformOp:rotateZXY")
                or prim.GetAttribute("xformOp:rotateZYX")
                or prim.GetAttribute("xformOp:rotateYXZ")
                or prim.GetAttribute("xformOp:rotateYZX")
            )

            # save new rotate property as double or float vector based on original rotate property type
            if rotate_prop is None:
                # if no rotate property is found, log warning and return
                carb.log_warn("no orient or rotate attributes found")
                return
            elif rotate_prop.GetTypeName() == Sdf.ValueTypeNames.Double3:
                new_rotate = Gf.Vec3d(*rot)
            elif rotate_prop.GetTypeName() == Sdf.ValueTypeNames.Float3:
                new_rotate = Gf.Vec3f(*rot)
            else:
                # if rotate property is not float3 or double3, log warning and return
                carb.log_warn("unknown rotation type")
                return

        # set new rotate property
        # omni.kit.commands.create(
        create(
            "ChangePropertyCommand",
            prop_path=rotate_prop.GetPath(),
            value=new_rotate,
            prev=rotate_prop.Get(),
            timecode=Usd.TimeCode.Default(),
            type_to_create_if_not_exist=(rotate_prop.GetTypeName()),
        ).do()

        # set scale property to (1, 1, 1) to prevent weird near-infinite scale (scale doesn't affect anything)
        if prim.GetAttribute("xformOp:scale"):
            # omni.kit.commands.create(
            create(
                "ChangePropertyCommand",
                prop_path=prim.GetAttribute("xformOp:scale").GetPath(),
                value=Gf.Vec3d(1, 1, 1),
                prev=prim.GetAttribute("xformOp:scale").Get(),
                timecode=Usd.TimeCode.Default(),
                type_to_create_if_not_exist=(
                    prim.GetAttribute("xformOp:scale").GetTypeName()
                ),
            ).do()

    return


def update_chase_camera(
    target_prim_path: str,
    cam_prim_path: str,
    distance=5.0,
    height=2.5,
    target_height=0.8,
):
    pose = get_prim_world_pose(target_prim_path)

    pos = pose["position"]
    forward = pose["forward"]

    target = [
        pos[0],
        pos[1],
        pos[2] + target_height,
    ]

    eye = [
        target[0] - forward[0] * distance,
        target[1] - forward[1] * distance,
        pos[2] + height,
    ]

    set_camera_view(
        eye=eye,
        target=target,
        camera_prim_path=cam_prim_path,
    )


class Robot(ABC):
    @abstractmethod
    def prepare(self, name):
        pass

    @abstractmethod
    def reset(self):
        pass

    @abstractmethod
    def step(self):
        pass
