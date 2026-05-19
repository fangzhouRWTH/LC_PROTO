from isaacsim import simulation_app
import os
import math
import numpy as np

import carb
from carb.input import KeyboardEventType

import math
import numpy as np
import re
from typing import Optional, Callable, List
from dataclasses import dataclass, field

from isaacsim.simulation_app import SimulationApp

simulation_app = SimulationApp(
    {
        "headless": False,
        "width": 1280,
        "height": 720,
    }
)

from isaacsim.core.api import World
from isaacsim.robot.policy.examples.robots import SpotFlatTerrainPolicy
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.viewports import set_camera_view
import omni.appwindow
import omni.timeline

import omni.usd

from pxr import UsdGeom, Gf, UsdLux, Sdf, UsdPhysics


class PlaceholderArea:
    def __init__(self, vertices):
        self.anchors = vertices


SPAWN_POS = np.array([0.0, 0.0, 0.8], dtype=np.float32)
PLACEHOLDER_AREA = list[PlaceholderArea]()


class ChaseViewportCamera:
    def __init__(
        self,
        distance=5.0,
        height=2.5,
        target_height=0.8,
        camera_prim_path="/OmniverseKit_Persp",
        smoothing=0.15,
    ):
        self.set_camera_view = set_camera_view
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


def yaw_from_quat_wxyz(q):
    """
    Convert quaternion [w, x, y, z] to yaw angle around Z axis.
    """
    w, x, y, z = q

    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)

    return math.atan2(siny_cosp, cosy_cosp)


class KeyboardVelocityController:
    def __init__(self, vx=0.6, vy=0.4, yaw=0.8):
        self.vx_speed = vx
        self.vy_speed = vy
        self.yaw_speed = yaw

        self.command = np.zeros(3, dtype=np.float32)

        self._pressed = set()

        self._app_window = omni.appwindow.get_default_app_window()
        self._keyboard = self._app_window.get_keyboard()
        self._input = carb.input.acquire_input_interface()

        self._sub_id = self._input.subscribe_to_keyboard_events(
            self._keyboard,
            self._on_keyboard_event,
        )

        print("[OK] Keyboard controller initialized.")
        print(
            "W/S: forward/backward, A/D: left/right, Q/E: turn left/right, Space: stop"
        )

    def _on_keyboard_event(self, event):
        key = event.input

        if event.type in (KeyboardEventType.KEY_PRESS, KeyboardEventType.KEY_REPEAT):
            self._pressed.add(key)

        elif event.type == KeyboardEventType.KEY_RELEASE:
            self._pressed.discard(key)

        self._update_command()
        return True

    def _update_command(self):
        self.command[:] = 0.0

        # forward / backward
        if carb.input.KeyboardInput.W in self._pressed:
            self.command[0] += self.vx_speed
        if carb.input.KeyboardInput.S in self._pressed:
            self.command[0] -= self.vx_speed

        # lateral movement
        if carb.input.KeyboardInput.A in self._pressed:
            self.command[1] += self.vy_speed
        if carb.input.KeyboardInput.D in self._pressed:
            self.command[1] -= self.vy_speed

        # yaw rotation
        if carb.input.KeyboardInput.Q in self._pressed:
            self.command[2] += self.yaw_speed
        if carb.input.KeyboardInput.E in self._pressed:
            self.command[2] -= self.yaw_speed

        # emergency stop
        if carb.input.KeyboardInput.SPACE in self._pressed:
            self.command[:] = 0.0
            self._pressed.clear()

    def get_command(self):
        return self.command.copy()

    def shutdown(self):
        if self._sub_id is not None:
            self._input.unsubscribe_to_keyboard_events(self._keyboard, self._sub_id)
            self._sub_id = None


def find_all_lights(stage, root_path="/"):
    """
    Find all USD light prims under root_path.

    root_path:
        "/" means search the whole stage.
        "/World/ImportedScene" means only search under that subtree.
    """

    light_schemas = (
        UsdLux.DistantLight,
        UsdLux.DomeLight,
        UsdLux.SphereLight,
        UsdLux.RectLight,
        UsdLux.DiskLight,
        UsdLux.CylinderLight,
    )

    light_type_names = {
        "DistantLight",
        "DomeLight",
        "SphereLight",
        "RectLight",
        "DiskLight",
        "CylinderLight",
        "PortalLight",
    }

    root = stage.GetPrimAtPath(root_path)
    if not root or not root.IsValid():
        raise RuntimeError(f"Invalid root path: {root_path}")

    lights = []

    for prim in stage.Traverse():
        prim_path = prim.GetPath()

        # Limit search scope
        if root_path != "/" and not prim_path.HasPrefix(Sdf.Path(root_path)):
            continue

        type_name = prim.GetTypeName()

        is_light = False

        # Standard typed USD lights
        for schema in light_schemas:
            if prim.IsA(schema):
                is_light = True
                break

        # Fallback for custom / extension light types
        if type_name in light_type_names:
            is_light = True

        if is_light:
            lights.append(prim)

    return lights


def deactivate_all_lights(stage, root_path="/"):
    """
    Deactivate all light prims under root_path.
    This is safer for referenced USD assets.
    """
    lights = find_all_lights(stage, root_path=root_path)

    if not lights:
        print("[INFO] No lights found.")
        return []

    deactivated = []

    for light in lights:
        path = light.GetPath()
        print(f"[INFO] Deactivating light: {path}")
        light.SetActive(False)
        deactivated.append(str(path))

    print(f"[OK] Deactivated {len(deactivated)} light(s).")
    return deactivated


def add_natural_light(stage):
    """
    Natural daylight preset:
    - Sun: strong direct light
    - Sky: stronger ambient / indirect-like dome light
    - Optional fill light: softens very dark shadow side
    """

    # Create light group
    UsdGeom.Xform.Define(stage, "/World/Light")

    # ------------------------------------------------------------
    # 1. Sun light: direct sunlight
    # ------------------------------------------------------------
    sun_path = "/World/Light/Sun"
    sun = UsdLux.DistantLight.Define(stage, sun_path)

    sun.CreateIntensityAttr(1200.0)
    sun.CreateAngleAttr(0.8)
    sun.CreateColorAttr(Gf.Vec3f(1.0, 0.96, 0.88))

    sun_xform = UsdGeom.Xformable(sun.GetPrim())
    sun_xform.ClearXformOpOrder()
    sun_xform.AddRotateXYZOp().Set(Gf.Vec3f(-45.0, 0.0, 35.0))

    # ------------------------------------------------------------
    # 2. Sky light: ambient/environment light
    # ------------------------------------------------------------
    sky_path = "/World/Light/Sky"
    sky = UsdLux.DomeLight.Define(stage, sky_path)

    # Increase this first if shadow side is too dark.
    sky.CreateIntensityAttr(300.0)

    # Exposure is exponential: +1 roughly doubles brightness.
    sky.CreateExposureAttr(1.0)

    # Cool sky color.
    sky.CreateColorAttr(Gf.Vec3f(0.78, 0.86, 1.0))

    # Optional skybox / HDRI background
    sky_texture = "/home/fangzhou/projects/LC_01/assets/textures/sky/sky_01.png"

    sky_texture_path = os.path.abspath(sky_texture)

    if not os.path.exists(sky_texture_path):
        raise FileNotFoundError(f"Sky texture not found: {sky_texture_path}")

    # Use lat-long / equirectangular environment map.
    sky.CreateTextureFileAttr(Sdf.AssetPath(sky_texture_path))
    sky.CreateTextureFormatAttr("latlong")

    print(f"[OK] Added skybox texture: {sky_texture_path}")

    # ------------------------------------------------------------
    # 3. Optional soft fill light
    # ------------------------------------------------------------
    fill_path = "/World/Light/Fill"
    fill = UsdLux.DistantLight.Define(stage, fill_path)

    # Much weaker than sun.
    fill.CreateIntensityAttr(120.0)
    fill.CreateAngleAttr(5.0)
    fill.CreateColorAttr(Gf.Vec3f(0.75, 0.82, 1.0))

    # Opposite-ish direction from sun to brighten shadow side.
    fill_xform = UsdGeom.Xformable(fill.GetPrim())
    fill_xform.ClearXformOpOrder()
    fill_xform.AddRotateXYZOp().Set(Gf.Vec3f(-25.0, 0.0, -145.0))

    print("[OK] Added natural light preset with stronger sky / indirect fill.")


def ensure_physics_scene(stage, scene_path="/World/PhysicsScene"):
    """
    Ensure the USD stage has a physics scene.
    Collision APIs can exist without this, but actual simulation needs a physics scene.
    """

    prim = stage.GetPrimAtPath(scene_path)
    if prim and prim.IsValid():
        return prim

    physics_scene = UsdPhysics.Scene.Define(stage, scene_path)

    # Optional gravity settings
    physics_scene.CreateGravityDirectionAttr(Gf.Vec3f(0.0, 0.0, -1.0))
    physics_scene.CreateGravityMagnitudeAttr(9.81)

    print(f"[OK] Created physics scene: {scene_path}")
    return physics_scene.GetPrim()


def is_supported_geometry_prim(prim):
    """
    Return True if the prim is a common geometry type that can reasonably receive collision.
    """

    return (
        prim.IsA(UsdGeom.Mesh)
        or prim.IsA(UsdGeom.Cube)
        or prim.IsA(UsdGeom.Sphere)
        or prim.IsA(UsdGeom.Capsule)
        or prim.IsA(UsdGeom.Cylinder)
        or prim.IsA(UsdGeom.Cone)
    )


def apply_collision_to_prim(prim, approximation="convexHull"):
    """
    Apply collision API to one geometry prim.

    For Mesh:
        Apply CollisionAPI + MeshCollisionAPI and set approximation.

    For primitive geometry:
        Apply CollisionAPI only.
    """

    if not prim or not prim.IsValid():
        return False

    if prim.IsInstanceProxy():
        print(f"[SKIP] Instance proxy cannot be edited directly: {prim.GetPath()}")
        return False

    if not is_supported_geometry_prim(prim):
        return False

    # Generic collision API
    if not prim.HasAPI(UsdPhysics.CollisionAPI):
        UsdPhysics.CollisionAPI.Apply(prim)

    # Mesh-specific collision approximation
    if prim.IsA(UsdGeom.Mesh):
        if not prim.HasAPI(UsdPhysics.MeshCollisionAPI):
            mesh_collision_api = UsdPhysics.MeshCollisionAPI.Apply(prim)
        else:
            mesh_collision_api = UsdPhysics.MeshCollisionAPI(prim)

        mesh_collision_api.CreateApproximationAttr().Set(approximation)

        print(f"[OK] Mesh collider: {prim.GetPath()} | approximation = {approximation}")
    else:
        print(f"[OK] Primitive collider: {prim.GetPath()}")

    return True


def add_collisions_to_stage(stage, root_path="/", approximation="convexHull"):
    """
    Traverse a subtree and add collision APIs to all supported geometry prims.
    """

    root = stage.GetPrimAtPath(root_path)
    if not root or not root.IsValid():
        raise RuntimeError(f"Invalid collision root path: {root_path}")

    ensure_physics_scene(stage)

    root_sdf_path = Sdf.Path(root_path)

    count = 0

    for prim in stage.Traverse():
        prim_path = prim.GetPath()

        if root_path != "/" and not prim_path.HasPrefix(root_sdf_path):
            continue

        if apply_collision_to_prim(prim, approximation=approximation):
            count += 1

    print(f"[OK] Added collision APIs to {count} prim(s) under {root_path}.")
    return count


def add_robot_reference(stage, robot_usd, robot_prim_path, robot_pos, robot_yaw_deg):
    if robot_usd is None:
        print("[INFO] No robot USD provided. Skipping robot placement.")
        return None

    # robot_usd = os.path.abspath(robot_usd)

    # if not os.path.exists(robot_usd):
    #     raise FileNotFoundError(f"Robot USD not found: {robot_usd}")

    # Create parent scope if needed
    UsdGeom.Xform.Define(stage, "/World/Robot")

    # Define robot root prim
    robot_xform = UsdGeom.Xform.Define(stage, robot_prim_path)
    robot_prim = robot_xform.GetPrim()

    # Add USD reference
    robot_prim.GetReferences().AddReference(robot_usd)

    # Set transform
    xformable = UsdGeom.Xformable(robot_prim)
    xformable.ClearXformOpOrder()

    xformable.AddTranslateOp().Set(Gf.Vec3d(*robot_pos))
    xformable.AddRotateXYZOp().Set(Gf.Vec3f(0.0, 0.0, robot_yaw_deg))

    scale_op = xformable.GetScaleOp()

    if scale_op:
        scale_op.Set(Gf.Vec3d(1.0, 1.0, 1.0))
    else:
        scale_op = xformable.AddScaleOp(precision=UsdGeom.XformOp.PrecisionDouble)
        scale_op.Set(Gf.Vec3d(1.0, 1.0, 1.0))

    print(f"[OK] Robot referenced:")
    print(f"     USD : {robot_usd}")
    print(f"     Prim: {robot_prim_path}")

    return robot_prim


def create_robot_articulation(robot_prim_path):
    robot = SingleArticulation(
        prim_path=robot_prim_path,
        name="spot_robot",
    )

    print(f"[OK] Created SingleArticulation wrapper for: {robot_prim_path}")
    return robot


def start_simulation():
    timeline = omni.timeline.get_timeline_interface()
    timeline.play()

    print("[OK] Simulation timeline started.")
    return timeline


def initialize_robot_after_sim_start(robot, simulation_app, warmup_frames=30):
    if robot is None:
        return

    # Let simulation start and physics initialize
    for _ in range(warmup_frames):
        simulation_app.update()

    robot.initialize()

    print("[OK] Robot articulation initialized.")

    try:
        joint_names = robot.dof_names
        print(f"[INFO] Robot DOF count: {len(joint_names)}")
        for i, name in enumerate(joint_names):
            print(f"  [{i}] {name}")
    except Exception as e:
        print(f"[WARN] Could not print joint names: {e}")


@dataclass
class PrimNameInfo:
    raw_name: str
    mobility: str
    domain: str
    category: str
    index: str


NAME_PATTERN = re.compile(
    r"^(?P<mobility>[a-zA-Z]+)_"
    r"(?P<domain>[a-zA-Z]+)_"
    r"(?P<category>[a-zA-Z]+)_"
    r"(?P<index>(?:\d+|[a-zA-Z]+))$"
)


def parse_prim_name(name: str) -> Optional[PrimNameInfo]:
    match = NAME_PATTERN.match(name)

    if not match:
        return None

    return PrimNameInfo(
        raw_name=name,
        mobility=match.group("mobility"),
        domain=match.group("domain"),
        category=match.group("category"),
        index=match.group("index"),
    )


@dataclass
class ProcessingRule:
    name: str
    mobility: str | None = None
    domain: str | None = None
    category: str | None = None
    prim_type: str | None = None
    actions: List[Callable] = field(default_factory=list)


def rule_matches(rule: ProcessingRule, info: PrimNameInfo, prim) -> bool:
    if rule.mobility is not None and rule.mobility != info.mobility:
        return False

    if rule.domain is not None and rule.domain != info.domain:
        return False

    if rule.category is not None and rule.category != info.category:
        return False

    if rule.prim_type is not None and rule.prim_type != prim.GetTypeName():
        return False

    return True


def apply_static_collision(prim, info: PrimNameInfo):
    """
    Apply static collision to a prim.
    If the prim is a Mesh, also apply MeshCollisionAPI.
    """
    if not prim.IsA(UsdGeom.Xformable):
        return

    UsdPhysics.CollisionAPI.Apply(prim)

    if prim.IsA(UsdGeom.Mesh):
        mesh_collision = UsdPhysics.MeshCollisionAPI.Apply(prim)
        mesh_collision.CreateApproximationAttr().Set("meshSimplification")

    print(f"[COLLISION] {prim.GetPath()} <- {info.raw_name}")


def process_placeholder_area(prim, info: PrimNameInfo):
    res = extract_mesh_world_vertices(prim.GetChildren()[0])
    vertices = res["world_vertices"]
    PLACEHOLDER_AREA.append(PlaceholderArea(vertices=vertices))


def set_spawn_point_from_prim(prim, info: PrimNameInfo):
    pos = extract_prim_position(prim)
    pos[2] += 0.8
    SPAWN_POS[:] = pos
    print(f"[SPAWN] {prim.GetPath()} <- {info.raw_name} | position = {pos}")


PROCESSING_RULES = [
    ProcessingRule(
        name="static construction buildings",
        mobility="static",
        domain="construction",
        category="building",
        actions=[
            apply_static_collision,
            # apply_semantic_label,
            # write_custom_metadata,
        ],
    ),
    ProcessingRule(
        name="static ground",
        mobility="static",
        domain="ground",
        actions=[
            apply_static_collision,
            # apply_semantic_label,
            # write_custom_metadata,
        ],
    ),
    ProcessingRule(
        name="placeholder spawn point",
        mobility="placeholder",
        domain="point",
        category="spawn",
        actions=[
            set_spawn_point_from_prim,
        ],
    ),
    ProcessingRule(
        name="placeholder plaza area",
        mobility="placeholder",
        domain="area",
        category="plaza",
        actions=[
            process_placeholder_area,
        ],
    ),
]


def process_stage_by_naming_rules(stage, rules):
    stats = {
        "visited": 0,
        "matched": 0,
        "unmatched_named": 0,
        "invalid_name": 0,
        "processed": {},
    }

    for prim in stage.Traverse():
        stats["visited"] += 1

        name = prim.GetName()
        print(name)
        info = parse_prim_name(name)

        print(info)

        if info is None:
            stats["invalid_name"] += 1
            continue

        matched_any = False

        for rule in rules:
            if not rule_matches(rule, info, prim):
                continue

            matched_any = True
            stats["matched"] += 1
            stats["processed"].setdefault(rule.name, 0)
            stats["processed"][rule.name] += 1

            for action in rule.actions:
                action(prim, info)

        if not matched_any:
            stats["unmatched_named"] += 1
            print(f"[WARN] Named prim matched pattern but no rule: {prim.GetPath()}")

    print_stage_processing_stats(stats)
    return stats


def print_stage_processing_stats(stats):
    print("\n========== Stage Processing Stats ==========")
    print(f"Visited prims:        {stats['visited']}")
    print(f"Matched rules:        {stats['matched']}")
    print(f"Invalid name format:  {stats['invalid_name']}")
    print(f"Unmatched named prim: {stats['unmatched_named']}")

    print("\nProcessed by rule:")
    for rule_name, count in stats["processed"].items():
        print(f"  {rule_name}: {count}")

    print("===========================================\n")


def transform_point(mat, p):
    p4 = mat.Transform(Gf.Vec3d(float(p[0]), float(p[1]), float(p[2])))
    return [float(p4[0]), float(p4[1]), float(p4[2])]


def extract_prim_position(prim):
    if not prim.IsValid():
        raise RuntimeError("Invalid prim")

    world_mat = omni.usd.get_world_transform_matrix(prim)
    pos = world_mat.ExtractTranslation()

    return [float(pos[0]), float(pos[1]), float(pos[2])]


def extract_mesh_world_vertices(prim):
    if not prim.IsValid():
        raise RuntimeError("Invalid prim")

    if not prim.IsA(UsdGeom.Mesh):
        raise RuntimeError("Prim is not a UsdGeom.Mesh")

    mesh = UsdGeom.Mesh(prim)

    points = mesh.GetPointsAttr().Get()
    face_counts = mesh.GetFaceVertexCountsAttr().Get()
    face_indices = mesh.GetFaceVertexIndicesAttr().Get()

    world_mat = omni.usd.get_world_transform_matrix(prim)

    world_vertices = [transform_point(world_mat, p) for p in points]

    return {
        "world_vertices": world_vertices,
        "face_vertex_counts": list(face_counts),
        "face_vertex_indices": list(face_indices),
        "world_matrix": world_mat,
    }


def extract_mesh_world_vertices_from_path(stage, mesh_prim_path: str):
    prim = stage.GetPrimAtPath(mesh_prim_path)

    return extract_mesh_world_vertices(prim)


def _normalize_vec3(v: Gf.Vec3d) -> Gf.Vec3d:
    length = v.GetLength()
    if length > 1e-8:
        v /= length
    return v


def get_prim_world_pose(
    prim_path: str,
    local_forward_axis=Gf.Vec3d(1.0, 0.0, 0.0),
    local_right_axis=Gf.Vec3d(0.0, -1.0, 0.0),
    local_up_axis=Gf.Vec3d(0.0, 0.0, 1.0),
):
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
    stage = omni.usd.get_context().get_stage()

    prim = stage.GetPrimAtPath(prim_path)

    if not prim.IsValid():
        raise RuntimeError(f"Invalid prim path: {prim_path}")

    world_mat = omni.usd.get_world_transform_matrix(prim)

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


def main():
    # usd_path = "/home/fangzhou/projects/LC_01/assets/blocks/usd_001/block_overall.usd"
    usd_path = (
        "/home/fangzhou/projects/LC_01/assets/blocks/test_field/test_simple_city.usd"
    )

    context = omni.usd.get_context()
    context.open_stage(usd_path)

    for _ in range(30):
        simulation_app.update()

    stage = context.get_stage()

    process_stage_by_naming_rules(stage, PROCESSING_RULES)

    for area in PLACEHOLDER_AREA:
        print(f"[PLACEHOLDER AREA] vertices = {area.anchors}")

    deactivate_all_lights(stage)

    add_natural_light(stage)

    camera_prim_path = "/OmniverseKit_Persp"

    spot_prim_path = "/World/Spot"
    spot = SpotFlatTerrainPolicy(
        prim_path=spot_prim_path,
        name="Spot",
        position=SPAWN_POS,
    )

    keyboard = KeyboardVelocityController()

    my_world = World(stage_units_in_meters=1.0, physics_dt=1 / 500, rendering_dt=1 / 50)

    state = {
        "spot_ready": False,
        "need_reinit": True,
        "was_stopped": False,
        "base_command": np.zeros(3, dtype=np.float32),
    }

    def initialize_spot():
        """
        Re-initialize Spot controller after world reset / timeline restart.
        """
        try:
            spot.initialize()
            state["spot_ready"] = True
            state["need_reinit"] = False
            print("[OK] Spot initialized.")
        except Exception as e:
            state["spot_ready"] = False
            state["need_reinit"] = True
            print(f"[ERROR] Spot initialize failed: {e}")

    def on_physics_step(step_size) -> None:
        """
        Physics callback should only send policy command.
        Do not reset world here.
        Do not initialize robot here unless absolutely necessary.
        """
        if not state["spot_ready"]:
            return

        try:
            spot.forward(step_size, state["base_command"])
        except Exception as e:
            state["spot_ready"] = False
            state["need_reinit"] = True
            print(f"[ERROR] spot.forward failed. Mark reinit required: {e}")

    my_world.reset()
    initialize_spot()

    CALLBACK_NAME = "spot_policy_step"

    my_world.add_physics_callback(CALLBACK_NAME, callback_fn=on_physics_step)

    while simulation_app.is_running():
        cmd = keyboard.get_command()

        f = cmd[0]
        l = cmd[1]
        y = cmd[2]

        state["base_command"] = np.array([2.0 * f + y, l, 2.0 * y], dtype=np.float32)

        if my_world.is_stopped():
            if not state["was_stopped"]:
                print("[INFO] World stopped. Spot controller invalidated.")

            state["was_stopped"] = True
            state["spot_ready"] = False
            state["need_reinit"] = True

            simulation_app.update()
            continue

        if my_world.is_playing() and state["need_reinit"]:
            print("[INFO] Reinitializing Spot after Play.")
            my_world.reset()
            initialize_spot()
            state["was_stopped"] = False

        my_world.step(render=True)

        if my_world.is_playing():
            try:
                update_chase_camera(
                    target_prim_path=(spot_prim_path + "/body"),
                    cam_prim_path=camera_prim_path,
                    height=1.2,
                )
            except Exception as e:
                print(f"[WARN] Chase camera update failed: {e}")

    print("[OK] Closing Isaac Sim.")

    simulation_app.close()


if __name__ == "__main__":
    main()
