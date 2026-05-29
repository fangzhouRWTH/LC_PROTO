from __future__ import annotations

from .manager import SensorRig
from .mount import SensorMountSpec, join_prim_path
from .sensors import MountedViewportCameraSensor


_PROFILE_ALIASES = {
    None: "none",
    "": "none",
    "none": "none",
    "off": "none",
    "spot-front-camera": "spot_front_camera",
    "spot_front_camera": "spot_front_camera",
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
    return ("none", "spot_front_camera", "spot-front-camera")


def create_sensor_rig(
    profile: str | None,
    *,
    robot_type: str,
    robot_root_prim_path: str,
) -> SensorRig | None:
    normalized = normalize_sensor_profile(profile)
    if normalized == "none":
        return None

    if normalized == "spot_front_camera":
        if robot_type != "spot":
            raise ValueError(
                "The spot_front_camera sensor profile currently requires robot_type='spot'."
            )
        return _create_spot_front_camera_rig(robot_root_prim_path)

    raise ValueError(f"Unhandled sensor profile: {normalized}")


def _create_spot_front_camera_rig(robot_root_prim_path: str) -> SensorRig:
    parent_path = join_prim_path(robot_root_prim_path, "body")
    camera = MountedViewportCameraSensor(
        sensor_id="spot_front_view",
        mount=SensorMountSpec(
            parent_prim_path=parent_path,
            frame_id="spot/front_camera",
            translation=(0.44, 0.075, 0.01),
            rotation_rpy_deg=(180.0, 180.0, 180.0),
        ),
        child_name="front_view_camera",
        resolution=(960, 600),
        activate_viewport_on_start=False,
    )
    return SensorRig.from_sensors(
        rig_id="spot_front_camera_rig",
        sensors=[camera],
        active_sensor_id=camera.sensor_id,
    )
