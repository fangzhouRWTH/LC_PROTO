from __future__ import annotations

from .manager import SensorRig
from .mount import SensorMountSpec, join_prim_path
from .sensors import (
    ChaseViewportCameraSensor,
    MountedIsaacDepthCameraSensor,
    MountedIsaacNormalCameraSensor,
    MountedPseudoDepthCameraSensor,
    MountedPseudoNormalCameraSensor,
    MountedViewportCameraSensor,
)


SENSOR_ROOT_PRIM_PATH = "/World/SimWorldSensors"
FOLLOW_SENSOR_ID = "follow_view"
SPOT_FRONT_SENSOR_ID = "spot_front_view"
SPOT_DEPTH_SENSOR_ID = "spot_depth_view"
NORMAL_SENSOR_ID = "normal_view"
ISAAC_DEPTH_SENSOR_ID = "isaac_depth_view"
ISAAC_NORMAL_SENSOR_ID = "isaac_normal_view"


_PROFILE_ALIASES = {
    None: "spot_camera_suite",
    "": "spot_camera_suite",
    "default": "spot_camera_suite",
    "spot-cameras": "spot_camera_suite",
    "spot_cameras": "spot_camera_suite",
    "spot-camera-suite": "spot_camera_suite",
    "spot_camera_suite": "spot_camera_suite",
    "isaac": "spot_isaac_camera_suite",
    "isaac-cameras": "spot_isaac_camera_suite",
    "isaac_cameras": "spot_isaac_camera_suite",
    "spot-isaac-camera-suite": "spot_isaac_camera_suite",
    "spot_isaac_camera_suite": "spot_isaac_camera_suite",
    "none": "none",
    "off": "none",
    "follow": "follow_camera",
    "follow-camera": "follow_camera",
    "follow_camera": "follow_camera",
    "chase": "follow_camera",
    "chase-camera": "follow_camera",
    "chase_camera": "follow_camera",
    "spot-front-camera": "spot_front_camera",
    "spot_front_camera": "spot_front_camera",
    "depth": "spot_depth_camera",
    "depth-camera": "spot_depth_camera",
    "depth_camera": "spot_depth_camera",
    "spot-depth-camera": "spot_depth_camera",
    "spot_depth_camera": "spot_depth_camera",
    "isaac-depth": "spot_isaac_depth_camera",
    "isaac_depth": "spot_isaac_depth_camera",
    "isaac-depth-camera": "spot_isaac_depth_camera",
    "isaac_depth_camera": "spot_isaac_depth_camera",
    "spot-isaac-depth-camera": "spot_isaac_depth_camera",
    "spot_isaac_depth_camera": "spot_isaac_depth_camera",
    "pseudo-normal": "spot_normal_camera",
    "pseudo_normal": "spot_normal_camera",
    "pseudo-normal-camera": "spot_normal_camera",
    "pseudo_normal_camera": "spot_normal_camera",
    "spot-normal-camera": "spot_normal_camera",
    "spot_normal_camera": "spot_normal_camera",
    "normal": "spot_isaac_normal_camera",
    "normal-view": "spot_isaac_normal_camera",
    "normal_view": "spot_isaac_normal_camera",
    "normal-camera": "spot_isaac_normal_camera",
    "normal_camera": "spot_isaac_normal_camera",
    "isaac-normal": "spot_isaac_normal_camera",
    "isaac_normal": "spot_isaac_normal_camera",
    "isaac-normal-camera": "spot_isaac_normal_camera",
    "isaac_normal_camera": "spot_isaac_normal_camera",
    "spot-isaac-normal-camera": "spot_isaac_normal_camera",
    "spot_isaac_normal_camera": "spot_isaac_normal_camera",
}


def normalize_sensor_profile(profile: str | None) -> str:
    key = profile.strip().lower() if isinstance(profile, str) else profile
    try:
        return _PROFILE_ALIASES[key]
    except KeyError as exc:
        available = ", ".join(available_sensor_profiles())
        raise ValueError(
            f"Unsupported sensor profile: {profile}. Available profiles: {available}"
        ) from exc


def available_sensor_profiles() -> tuple[str, ...]:
    return (
        "default",
        "spot_camera_suite",
        "spot-camera-suite",
        "spot_isaac_camera_suite",
        "spot-isaac-camera-suite",
        "isaac",
        "isaac-cameras",
        "follow_camera",
        "follow-camera",
        "chase_camera",
        "spot_front_camera",
        "spot-front-camera",
        "spot_depth_camera",
        "spot-depth-camera",
        "spot_isaac_depth_camera",
        "spot-isaac-depth-camera",
        "isaac_depth",
        "isaac-depth-camera",
        "spot_normal_camera",
        "spot-normal-camera",
        "pseudo_normal",
        "pseudo-normal-camera",
        "spot_isaac_normal_camera",
        "spot-isaac-normal-camera",
        "isaac_normal",
        "isaac-normal-camera",
        "normal",
        "normal-view",
        "normal_view",
        "normal-camera",
        "normal_camera",
        "depth",
        "depth-camera",
        "depth_camera",
        "none",
    )


def create_sensor_rig(
    profile: str | None,
    *,
    robot_type: str,
    robot_root_prim_path: str,
    active_sensor_id: str | None = None,
) -> SensorRig | None:
    normalized = normalize_sensor_profile(profile)
    if normalized == "none":
        return None

    if normalized == "follow_camera":
        target_prim_path = (
            join_prim_path(robot_root_prim_path, "body")
            if robot_type == "spot"
            else robot_root_prim_path
        )
        return _create_follow_camera_rig(
            robot_root_prim_path,
            target_prim_path=target_prim_path,
            active_sensor_id=active_sensor_id,
        )

    if normalized == "spot_camera_suite":
        if robot_type != "spot":
            raise ValueError(
                "The spot_camera_suite sensor profile currently requires robot_type='spot'."
            )
        return _create_spot_camera_suite_rig(
            robot_root_prim_path,
            active_sensor_id=active_sensor_id,
        )

    if normalized == "spot_isaac_camera_suite":
        if robot_type != "spot":
            raise ValueError(
                "The spot_isaac_camera_suite sensor profile currently requires robot_type='spot'."
            )
        return _create_spot_isaac_camera_suite_rig(
            robot_root_prim_path,
            active_sensor_id=active_sensor_id,
        )

    if normalized == "spot_front_camera":
        if robot_type != "spot":
            raise ValueError(
                "The spot_front_camera sensor profile currently requires robot_type='spot'."
            )
        return _create_spot_front_camera_rig(
            robot_root_prim_path,
            active_sensor_id=active_sensor_id,
        )

    if normalized == "spot_depth_camera":
        if robot_type != "spot":
            raise ValueError(
                "The spot_depth_camera sensor profile currently requires robot_type='spot'."
            )
        return _create_spot_depth_camera_rig(
            robot_root_prim_path,
            active_sensor_id=active_sensor_id,
        )

    if normalized == "spot_isaac_depth_camera":
        if robot_type != "spot":
            raise ValueError(
                "The spot_isaac_depth_camera sensor profile currently requires robot_type='spot'."
            )
        return _create_spot_isaac_depth_camera_rig(
            robot_root_prim_path,
            active_sensor_id=active_sensor_id,
        )

    if normalized == "spot_normal_camera":
        if robot_type != "spot":
            raise ValueError(
                "The spot_normal_camera sensor profile currently requires robot_type='spot'."
            )
        return _create_spot_normal_camera_rig(
            robot_root_prim_path,
            active_sensor_id=active_sensor_id,
        )

    if normalized == "spot_isaac_normal_camera":
        if robot_type != "spot":
            raise ValueError(
                "The spot_isaac_normal_camera sensor profile currently requires robot_type='spot'."
            )
        return _create_spot_isaac_normal_camera_rig(
            robot_root_prim_path,
            active_sensor_id=active_sensor_id,
        )

    raise ValueError(f"Unhandled sensor profile: {normalized}")


def _safe_prim_name(raw: str) -> str:
    return raw.strip("/").replace("/", "_") or "root"


def _sensor_namespace(robot_root_prim_path: str) -> str:
    return join_prim_path(SENSOR_ROOT_PRIM_PATH, _safe_prim_name(robot_root_prim_path))


def _create_follow_camera_sensor(
    robot_root_prim_path: str,
    *,
    target_prim_path: str | None = None,
) -> ChaseViewportCameraSensor:
    return ChaseViewportCameraSensor(
        sensor_id=FOLLOW_SENSOR_ID,
        target_prim_path=target_prim_path or robot_root_prim_path,
        camera_prim_path=join_prim_path(
            _sensor_namespace(robot_root_prim_path),
            "follow_view_camera",
        ),
        frame_id="world/follow_view_camera",
        activate_viewport_on_start=False,
    )


def _create_spot_front_camera_sensor(
    robot_root_prim_path: str,
) -> MountedViewportCameraSensor:
    parent_path = join_prim_path(robot_root_prim_path, "body")
    return MountedViewportCameraSensor(
        sensor_id=SPOT_FRONT_SENSOR_ID,
        mount=SensorMountSpec(
            parent_prim_path=parent_path,
            frame_id="spot/front_camera",
            translation=(0.44, 0.075, 0.01),
            # USD cameras look along local -Z; Spot's body frame uses +X as forward.
            rotation_rpy_deg=(90.0, 0.0, -90.0),
        ),
        child_name="front_view_camera",
        resolution=(960, 600),
        activate_viewport_on_start=False,
    )


def _create_spot_depth_camera_sensor(
    robot_root_prim_path: str,
) -> MountedPseudoDepthCameraSensor:
    parent_path = join_prim_path(robot_root_prim_path, "body")
    return MountedPseudoDepthCameraSensor(
        sensor_id=SPOT_DEPTH_SENSOR_ID,
        mount=SensorMountSpec(
            parent_prim_path=parent_path,
            frame_id="spot/depth_camera",
            translation=(0.46, 0.0, 0.03),
            # USD cameras look along local -Z; Spot's body frame uses +X as forward.
            rotation_rpy_deg=(90.0, 0.0, -90.0),
        ),
        child_name="depth_view_camera",
        resolution=(960, 600),
        depth_resolution=(320, 240),
        near_m=0.2,
        far_m=25.0,
        default_depth_m=8.0,
        noise_std_m=0.0,
        emit_depth_array=True,
        activate_viewport_on_start=False,
    )


def _create_spot_normal_camera_sensor(
    robot_root_prim_path: str,
) -> MountedPseudoNormalCameraSensor:
    parent_path = join_prim_path(robot_root_prim_path, "body")
    return MountedPseudoNormalCameraSensor(
        sensor_id=NORMAL_SENSOR_ID,
        mount=SensorMountSpec(
            parent_prim_path=parent_path,
            frame_id="spot/normal_camera",
            translation=(0.46, 0.0, 0.03),
            # USD cameras look along local -Z; Spot's body frame uses +X as forward.
            rotation_rpy_deg=(90.0, 0.0, -90.0),
        ),
        child_name="normal_view_camera",
        resolution=(960, 600),
        normal_resolution=(320, 240),
        plane_normal_camera=(0.0, 0.0, 1.0),
        emit_normal_array=True,
        emit_preview_rgb=True,
        activate_viewport_on_start=False,
    )


def _create_spot_isaac_depth_camera_sensor(
    robot_root_prim_path: str,
) -> MountedIsaacDepthCameraSensor:
    parent_path = join_prim_path(robot_root_prim_path, "body")
    return MountedIsaacDepthCameraSensor(
        sensor_id=ISAAC_DEPTH_SENSOR_ID,
        mount=SensorMountSpec(
            parent_prim_path=parent_path,
            frame_id="spot/isaac_depth_camera",
            translation=(0.46, 0.0, 0.03),
            # USD cameras look along local -Z; Spot's body frame uses +X as forward.
            rotation_rpy_deg=(90.0, 0.0, -90.0),
        ),
        child_name="isaac_depth_view_camera",
        resolution=(960, 600),
        near_m=0.2,
        far_m=25.0,
        activate_viewport_on_start=False,
    )


def _create_spot_isaac_normal_camera_sensor(
    robot_root_prim_path: str,
    *,
    enable_material_override: bool = False,
) -> MountedIsaacNormalCameraSensor:
    parent_path = join_prim_path(robot_root_prim_path, "body")
    return MountedIsaacNormalCameraSensor(
        sensor_id=ISAAC_NORMAL_SENSOR_ID,
        mount=SensorMountSpec(
            parent_prim_path=parent_path,
            frame_id="spot/isaac_normal_camera",
            translation=(0.46, 0.0, 0.03),
            # USD cameras look along local -Z; Spot's body frame uses +X as forward.
            rotation_rpy_deg=(90.0, 0.0, -90.0),
        ),
        child_name="isaac_normal_view_camera",
        resolution=(960, 600),
        enable_material_override=enable_material_override,
        activate_viewport_on_start=False,
    )


def _resolve_active_sensor_id(
    active_sensor_id: str | None,
    default_sensor_id: str,
) -> str:
    return active_sensor_id or default_sensor_id


def _create_follow_camera_rig(
    robot_root_prim_path: str,
    *,
    target_prim_path: str | None = None,
    active_sensor_id: str | None = None,
) -> SensorRig:
    camera = _create_follow_camera_sensor(
        robot_root_prim_path,
        target_prim_path=target_prim_path,
    )
    return SensorRig.from_sensors(
        rig_id="follow_camera_rig",
        sensors=[camera],
        active_sensor_id=_resolve_active_sensor_id(
            active_sensor_id,
            camera.sensor_id,
        ),
    )


def _create_spot_front_camera_rig(
    robot_root_prim_path: str,
    *,
    active_sensor_id: str | None = None,
) -> SensorRig:
    camera = _create_spot_front_camera_sensor(robot_root_prim_path)
    return SensorRig.from_sensors(
        rig_id="spot_front_camera_rig",
        sensors=[camera],
        active_sensor_id=_resolve_active_sensor_id(
            active_sensor_id,
            camera.sensor_id,
        ),
    )


def _create_spot_depth_camera_rig(
    robot_root_prim_path: str,
    *,
    active_sensor_id: str | None = None,
) -> SensorRig:
    camera = _create_spot_depth_camera_sensor(robot_root_prim_path)
    return SensorRig.from_sensors(
        rig_id="spot_depth_camera_rig",
        sensors=[camera],
        active_sensor_id=_resolve_active_sensor_id(
            active_sensor_id,
            camera.sensor_id,
        ),
    )


def _create_spot_normal_camera_rig(
    robot_root_prim_path: str,
    *,
    active_sensor_id: str | None = None,
) -> SensorRig:
    camera = _create_spot_normal_camera_sensor(robot_root_prim_path)
    return SensorRig.from_sensors(
        rig_id="spot_normal_camera_rig",
        sensors=[camera],
        active_sensor_id=_resolve_active_sensor_id(
            active_sensor_id,
            camera.sensor_id,
        ),
    )


def _create_spot_isaac_depth_camera_rig(
    robot_root_prim_path: str,
    *,
    active_sensor_id: str | None = None,
) -> SensorRig:
    camera = _create_spot_isaac_depth_camera_sensor(robot_root_prim_path)
    return SensorRig.from_sensors(
        rig_id="spot_isaac_depth_camera_rig",
        sensors=[camera],
        active_sensor_id=_resolve_active_sensor_id(
            active_sensor_id,
            camera.sensor_id,
        ),
    )


def _create_spot_isaac_normal_camera_rig(
    robot_root_prim_path: str,
    *,
    active_sensor_id: str | None = None,
) -> SensorRig:
    camera = _create_spot_isaac_normal_camera_sensor(robot_root_prim_path)
    return SensorRig.from_sensors(
        rig_id="spot_isaac_normal_camera_rig",
        sensors=[camera],
        active_sensor_id=_resolve_active_sensor_id(
            active_sensor_id,
            camera.sensor_id,
        ),
    )


def _create_spot_camera_suite_rig(
    robot_root_prim_path: str,
    *,
    active_sensor_id: str | None = None,
) -> SensorRig:
    follow_camera = _create_follow_camera_sensor(
        robot_root_prim_path,
        target_prim_path=join_prim_path(robot_root_prim_path, "body"),
    )
    front_camera = _create_spot_front_camera_sensor(robot_root_prim_path)
    depth_camera = _create_spot_depth_camera_sensor(robot_root_prim_path)
    normal_camera = _create_spot_normal_camera_sensor(robot_root_prim_path)
    return SensorRig.from_sensors(
        rig_id="spot_camera_suite_rig",
        sensors=[follow_camera, front_camera, depth_camera, normal_camera],
        active_sensor_id=_resolve_active_sensor_id(
            active_sensor_id,
            follow_camera.sensor_id,
        ),
    )


def _create_spot_isaac_camera_suite_rig(
    robot_root_prim_path: str,
    *,
    active_sensor_id: str | None = None,
) -> SensorRig:
    follow_camera = _create_follow_camera_sensor(
        robot_root_prim_path,
        target_prim_path=join_prim_path(robot_root_prim_path, "body"),
    )
    front_camera = _create_spot_front_camera_sensor(robot_root_prim_path)
    depth_camera = _create_spot_isaac_depth_camera_sensor(robot_root_prim_path)
    normal_camera = _create_spot_isaac_normal_camera_sensor(robot_root_prim_path)
    return SensorRig.from_sensors(
        rig_id="spot_isaac_camera_suite_rig",
        sensors=[follow_camera, front_camera, depth_camera, normal_camera],
        active_sensor_id=_resolve_active_sensor_id(
            active_sensor_id,
            follow_camera.sensor_id,
        ),
    )
