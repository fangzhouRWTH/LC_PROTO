from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import math
import os

ISAAC_PEOPLE_YAW_OFFSET_DEG_ENV = "DYNAMIC_ISAAC_PEOPLE_YAW_OFFSET_DEG"
DEFAULT_ISAAC_PEOPLE_YAW_OFFSET_DEG = 90.0
PEOPLE_WALK_CLIP_RELATIVES = (
    "Isaac/People/Animations/stand_walk_loop_in_place.skelanim.usd",
    "Isaac/People/Animations/stand_walk_loop.skelanim.usd",
    "Isaac/People/Animations/stand_walk_1.skelanim.usd",
)


@dataclass(frozen=True)
class WalkClipBindingResult:
    skeleton_path: str = ""
    clip_path: str = ""
    animation_prim_path: str = ""

    @property
    def bound(self) -> bool:
        return bool(self.skeleton_path and self.clip_path and self.animation_prim_path)


@dataclass(frozen=True)
class RouteAnimGraphBindingResult:
    skelroot_paths: tuple[str, ...] = ()
    anim_graph_path: str = ""

    @property
    def bound(self) -> bool:
        return bool(self.skelroot_paths and self.anim_graph_path)


def resolve_isaac_people_yaw_offset_degrees(
    env_value: str | None = None,
    default: float = DEFAULT_ISAAC_PEOPLE_YAW_OFFSET_DEG,
) -> float:
    if env_value is None:
        env_value = os.environ.get(ISAAC_PEOPLE_YAW_OFFSET_DEG_ENV)
    if env_value is None or str(env_value).strip() == "":
        return float(default)
    try:
        return float(str(env_value).strip())
    except ValueError:
        return float(default)


def yaw_with_isaac_people_forward_offset(
    yaw_radians: float,
    yaw_offset_degrees: float = DEFAULT_ISAAC_PEOPLE_YAW_OFFSET_DEG,
) -> float:
    return float(yaw_radians) + math.radians(float(yaw_offset_degrees))


def set_orient_op_yaw(
    orient_op: Any,
    Gf: Any,
    yaw: float,
    yaw_offset_degrees: float = DEFAULT_ISAAC_PEOPLE_YAW_OFFSET_DEG,
):
    adjusted_yaw = yaw_with_isaac_people_forward_offset(yaw, yaw_offset_degrees)
    quat = Gf.Rotation(Gf.Vec3d(0.0, 0.0, 1.0), math.degrees(adjusted_yaw)).GetQuat()
    current = orient_op.Get()
    if isinstance(current, Gf.Quatf):
        orient_op.Set(Gf.Quatf(quat))
        return
    if isinstance(current, Gf.Quatd):
        orient_op.Set(Gf.Quatd(quat))
        return
    orient_op.Set(quat)


def resolve_isaac_people_walk_clip_path(
    asset_root: str | None,
    explicit_clip_path: str | None = None,
) -> str | None:
    explicit = str(explicit_clip_path or "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_file() and path.suffix.lower() in {".usd", ".usda", ".usdc"}:
            return str(path.resolve())
        return None

    if not asset_root:
        return None
    if _looks_like_remote_asset_root(asset_root):
        return _join_asset_root(asset_root, PEOPLE_WALK_CLIP_RELATIVES[0])

    root = Path(asset_root).expanduser()
    for relative in PEOPLE_WALK_CLIP_RELATIVES:
        path = root / relative
        if path.is_file():
            return str(path.resolve())
    return None


def bind_route_walk_clip(
    stage: Any,
    context: Any,
    actor: Any,
    asset_root: str | None,
    explicit_clip_path: str | None = None,
    debug_enabled: bool = False,
) -> WalkClipBindingResult:
    clip_path = resolve_isaac_people_walk_clip_path(
        asset_root,
        explicit_clip_path=explicit_clip_path,
    )
    if not clip_path:
        if debug_enabled:
            print("[WARN] No Isaac People walk skelanim clip found for route-control mode.")
        return WalkClipBindingResult()

    character_root = stage.GetPrimAtPath(actor.character_root_path)
    if not character_root or not character_root.IsValid():
        return WalkClipBindingResult()

    search_root_path = actor.skelroot_path or actor.character_root_path
    search_root = stage.GetPrimAtPath(search_root_path)
    if not search_root or not search_root.IsValid():
        search_root = character_root

    skeleton = first_descendant_prim_by_type(search_root, "Skeleton", context)
    if skeleton is None or not skeleton.IsValid():
        if debug_enabled:
            print(f"[WARN] No Skeleton found under {search_root_path} for walk clip binding.")
        return WalkClipBindingResult()

    animation_root_path = f"{actor.character_root_path}/LCProtoWalkAnimation"
    animation_root = stage.OverridePrim(animation_root_path)
    animation_root.GetReferences().AddReference(clip_path)
    context.update()

    animation = first_descendant_prim_by_type(animation_root, "SkelAnimation", context)
    if animation is None or not animation.IsValid():
        if debug_enabled:
            print(f"[WARN] No SkelAnimation found in walk clip: {clip_path}")
        return WalkClipBindingResult()

    try:
        from pxr import UsdSkel

        binding = UsdSkel.BindingAPI.Apply(skeleton)
        binding.CreateAnimationSourceRel().SetTargets([animation.GetPath()])
    except Exception as exc:  # pragma: no cover - Isaac runtime path
        if debug_enabled:
            print(f"[WARN] Isaac People walk clip binding failed: {exc}")
        return WalkClipBindingResult()

    return WalkClipBindingResult(
        skeleton_path=str(skeleton.GetPath()),
        clip_path=clip_path,
        animation_prim_path=str(animation.GetPath()),
    )


def first_descendant_prim_by_type(root_prim: Any, type_name: str, context: Any) -> Any | None:
    if root_prim.GetTypeName() == type_name:
        return root_prim
    for prim in context.pxr_usd.PrimRange(root_prim):
        if prim.GetTypeName() == type_name:
            return prim
    return None


def _looks_like_remote_asset_root(root: str) -> bool:
    return "://" in root or root.startswith("omniverse:")


def _join_asset_root(asset_root: str, relative_path: str) -> str:
    return f"{asset_root.rstrip('/')}/{relative_path.lstrip('/')}"


def setup_route_anim_graph(
    character_util: Any,
    context: Any,
    skelroots: list[Any],
    anim_graph_prim: Any,
    debug_enabled: bool = False,
) -> RouteAnimGraphBindingResult:
    """Attach Isaac People AnimGraph to route-controlled characters.

    LC_PROTO still owns root motion in route-control mode. The AnimGraph is
    only responsible for skeleton pose playback driven by per-frame variables.
    """
    valid_skelroots = [prim for prim in skelroots if _prim_is_valid(prim)]
    if not valid_skelroots:
        if debug_enabled:
            print("[WARN] Isaac People route AnimGraph setup skipped: no valid SkelRoot prims.")
        return RouteAnimGraphBindingResult()
    if not _prim_is_valid(anim_graph_prim):
        if debug_enabled:
            print("[WARN] Isaac People route AnimGraph setup skipped: missing AnimationGraph prim.")
        return RouteAnimGraphBindingResult()

    try:
        character_util.setup_animation_graph_to_character(valid_skelroots, anim_graph_prim)
        apply_route_anim_runtime_schemas(valid_skelroots, debug_enabled=debug_enabled)
        for _ in range(8):
            context.update()
    except Exception as exc:  # pragma: no cover - Isaac runtime path
        if debug_enabled:
            print(f"[WARN] Isaac People route AnimGraph setup failed: {exc}")
        return RouteAnimGraphBindingResult()

    return RouteAnimGraphBindingResult(
        skelroot_paths=tuple(str(prim.GetPath()) for prim in valid_skelroots),
        anim_graph_path=str(anim_graph_prim.GetPath()),
    )


def anim_graph_targets_for_skelroot(skelroot: Any) -> list[str]:
    if not _prim_is_valid(skelroot):
        return []
    try:
        import AnimGraphSchema

        relationship = AnimGraphSchema.AnimationGraphAPI(skelroot).GetAnimationGraphRel()
        return [str(target) for target in relationship.GetTargets()]
    except Exception:
        return []


def _prim_is_valid(prim: Any) -> bool:
    try:
        return prim is not None and prim.IsValid()
    except Exception:
        return False

def apply_route_anim_runtime_schemas(
    skelroots: list[Any],
    debug_enabled: bool = False,
) -> None:
    """Make route-controlled SkelRoots look like runnable AnimGraph characters.

    Isaac's own runnable test assets carry both AnimationGraphAPI and
    OmniGraphAPI. `ApplyAnimationGraphAPICommand` authors the former, so route
    mode defensively authors the latter when the schema is available.
    """
    for skelroot in skelroots:
        if not _prim_is_valid(skelroot):
            continue
        if _has_applied_schema(skelroot, "OmniGraphAPI"):
            continue
        if _apply_omnigraph_api_schema(skelroot):
            continue
        if debug_enabled:
            print(
                "[WARN] Isaac People route AnimGraph could not apply OmniGraphAPI "
                f"to {skelroot.GetPath()}. Runtime character handle may stay unavailable."
            )


def applied_schema_names(prim: Any) -> list[str]:
    if not _prim_is_valid(prim):
        return []
    try:
        return [str(schema) for schema in prim.GetAppliedSchemas()]
    except Exception:
        return []


def _has_applied_schema(prim: Any, schema_name: str) -> bool:
    return schema_name in applied_schema_names(prim)


def _apply_omnigraph_api_schema(prim: Any) -> bool:
    try:
        import OmniGraphSchema

        prim.ApplyAPI(OmniGraphSchema.OmniGraphAPI)
        return _has_applied_schema(prim, "OmniGraphAPI")
    except Exception:
        pass
    try:
        prim.AddAppliedSchema("OmniGraphAPI")
        return _has_applied_schema(prim, "OmniGraphAPI")
    except Exception:
        return False

