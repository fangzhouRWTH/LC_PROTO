from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ColorRGB = tuple[float, float, float]
Vec3 = tuple[float, float, float]
USD_SUFFIXES = {".usd", ".usda", ".usdc"}
DEFAULT_PEDESTRIAN_VISUAL = "proxy"
DEFAULT_PEDESTRIAN_ASSET_PATH = ""
DEFAULT_PEDESTRIAN_ASSET_SCALE = 1.0
DEFAULT_PEDESTRIAN_ASSET_FIT = "height"
DEFAULT_PEDESTRIAN_ANIMATION = "none"
DEFAULT_PEDESTRIAN_ANIMATION_CLIP_PATH = ""
DEFAULT_PEDESTRIAN_ANIMATION_TIME_SCALE = 1.0
DEFAULT_VEHICLE_VISUAL = "proxy"
DEFAULT_VEHICLE_ASSET_PATH = ""
DEFAULT_VEHICLE_ASSET_SCALE = 1.0
DEFAULT_VEHICLE_ASSET_FIT = "shape"
DEFAULT_ISAAC_PEOPLE_CHARACTERS_PATH = "Isaac/People/Characters/"
DEFAULT_ISAAC_VEHICLE_PATHS: tuple[str, ...] = ()
_ASSET_CHILD_NAME = "Asset"
_ANIMATION_CHILD_NAME = "Animation"
_KNOWN_VISUAL_CHILDREN = (
    _ASSET_CHILD_NAME,
    _ANIMATION_CHILD_NAME,
    "Legs",
    "Torso",
    "Head",
    "Body",
    "Cabin",
    "FrontMarker",
    "RearMarker",
)
_WARNED_MESSAGES: set[str] = set()
_ANIMATION_CLIP_KEYWORDS = (
    "walk",
    "walking",
    "run",
    "running",
    "corridor",
    "mobile",
    "traffic",
    "idle",
    "stand",
)


@dataclass(frozen=True)
class DynamicVisualConfig:
    pedestrian_visual: str = DEFAULT_PEDESTRIAN_VISUAL
    pedestrian_asset_path: str = DEFAULT_PEDESTRIAN_ASSET_PATH
    pedestrian_asset_scale: float = DEFAULT_PEDESTRIAN_ASSET_SCALE
    pedestrian_asset_fit: str = DEFAULT_PEDESTRIAN_ASSET_FIT
    pedestrian_animation: str = DEFAULT_PEDESTRIAN_ANIMATION
    pedestrian_animation_clip_path: str = DEFAULT_PEDESTRIAN_ANIMATION_CLIP_PATH
    pedestrian_animation_time_scale: float = DEFAULT_PEDESTRIAN_ANIMATION_TIME_SCALE
    vehicle_visual: str = DEFAULT_VEHICLE_VISUAL
    vehicle_asset_path: str = DEFAULT_VEHICLE_ASSET_PATH
    vehicle_asset_scale: float = DEFAULT_VEHICLE_ASSET_SCALE
    vehicle_asset_fit: str = DEFAULT_VEHICLE_ASSET_FIT


@dataclass(frozen=True)
class AssetBounds:
    min_xyz: Vec3
    max_xyz: Vec3

    @property
    def size_xyz(self) -> Vec3:
        return (
            max(0.0, self.max_xyz[0] - self.min_xyz[0]),
            max(0.0, self.max_xyz[1] - self.min_xyz[1]),
            max(0.0, self.max_xyz[2] - self.min_xyz[2]),
        )


@dataclass(frozen=True)
class AssetVisualTransform:
    scale: float
    translate_xyz: Vec3
    fit_applied: bool


@dataclass(frozen=True)
class ProxyPrimitiveSpec:
    name: str
    primitive_type: str
    translate_xyz: Vec3
    scale_xyz: Vec3
    color_rgb: ColorRGB


@dataclass(frozen=True)
class ProxyVisualSpec:
    actor_type: str
    bounds_xyz: Vec3
    parts: tuple[ProxyPrimitiveSpec, ...] = field(default_factory=tuple)


def proxy_visual_spec_for_actor(
    actor_type: str,
    shape: Any | None = None,
) -> ProxyVisualSpec:
    if actor_type == "vehicle":
        return _vehicle_proxy_visual_spec(shape)
    return _pedestrian_proxy_visual_spec(shape)


def actor_visual_source(
    actor_type: str,
    visual_config: DynamicVisualConfig | None = None,
    resolved_asset_path: str | None = None,
) -> str:
    config = _normalize_visual_config(visual_config)
    if actor_type == "pedestrian":
        if config.pedestrian_visual == "asset" and resolved_asset_path:
            return "asset"
        return "proxy"
    if actor_type == "vehicle":
        if config.vehicle_visual == "asset" and resolved_asset_path:
            return "asset"
        return "proxy"
    return "proxy"


def pedestrian_asset_transform_for_bounds(
    bounds: AssetBounds | None,
    shape: Any | None = None,
    asset_scale: float = DEFAULT_PEDESTRIAN_ASSET_SCALE,
    asset_fit: str = DEFAULT_PEDESTRIAN_ASSET_FIT,
) -> AssetVisualTransform:
    manual_scale = max(1e-6, float(asset_scale or DEFAULT_PEDESTRIAN_ASSET_SCALE))
    fit_mode = _normalize_asset_fit(asset_fit)
    if fit_mode != "height" or bounds is None:
        return AssetVisualTransform(
            scale=manual_scale,
            translate_xyz=(0.0, 0.0, 0.0),
            fit_applied=False,
        )

    source_height = _pedestrian_fit_height(bounds)
    if source_height <= 1e-6:
        return AssetVisualTransform(
            scale=manual_scale,
            translate_xyz=(0.0, 0.0, 0.0),
            fit_applied=False,
        )

    target_height = max(0.1, float(_field(shape, "height_m", 1.7) or 1.7))
    final_scale = manual_scale * target_height / source_height
    z_offset = _pedestrian_ground_z_offset(bounds, final_scale)
    return AssetVisualTransform(
        scale=final_scale,
        translate_xyz=(0.0, 0.0, z_offset),
        fit_applied=True,
    )


def vehicle_asset_transform_for_bounds(
    bounds: AssetBounds | None,
    shape: Any | None = None,
    asset_scale: float = DEFAULT_VEHICLE_ASSET_SCALE,
    asset_fit: str = DEFAULT_VEHICLE_ASSET_FIT,
) -> AssetVisualTransform:
    manual_scale = max(1e-6, float(asset_scale or DEFAULT_VEHICLE_ASSET_SCALE))
    fit_mode = _normalize_vehicle_asset_fit(asset_fit)
    if fit_mode != "shape" or bounds is None:
        return AssetVisualTransform(
            scale=manual_scale,
            translate_xyz=(0.0, 0.0, 0.0),
            fit_applied=False,
        )

    size_x, size_y, size_z = bounds.size_xyz
    target_dims = (
        max(0.1, float(_field(shape, "length_m", 4.5) or 4.5)),
        max(0.1, float(_field(shape, "width_m", 1.8) or 1.8)),
        max(0.1, float(_field(shape, "height_m", 1.6) or 1.6)),
    )
    candidates = [
        target / source
        for target, source in zip(target_dims, (size_x, size_y, size_z))
        if source > 1e-6
    ]
    if not candidates:
        return AssetVisualTransform(
            scale=manual_scale,
            translate_xyz=(0.0, 0.0, 0.0),
            fit_applied=False,
        )

    final_scale = manual_scale * min(candidates)
    z_offset = -bounds.min_xyz[2] * final_scale
    return AssetVisualTransform(
        scale=final_scale,
        translate_xyz=(0.0, 0.0, z_offset),
        fit_applied=True,
    )


def _pedestrian_fit_height(bounds: AssetBounds) -> float:
    min_z = bounds.min_xyz[2]
    max_z = bounds.max_xyz[2]
    full_height = bounds.size_xyz[2]
    if full_height <= 1e-6:
        return 0.0
    if min_z < 0.0 < max_z and abs(min_z) / full_height <= 0.15:
        return max_z
    return full_height


def _pedestrian_ground_z_offset(bounds: AssetBounds, final_scale: float) -> float:
    min_z = bounds.min_xyz[2]
    max_z = bounds.max_xyz[2]
    full_height = bounds.size_xyz[2]
    if full_height > 1e-6 and min_z < 0.0 < max_z and abs(min_z) / full_height <= 0.15:
        return 0.0
    return -min_z * final_scale


def resolve_pedestrian_asset_path(
    asset_path: str | None = None,
    context: Any | None = None,
) -> str | None:
    raw_path = str(asset_path or "").strip()
    if raw_path:
        return _resolve_asset_reference(raw_path, context)

    resolved_default = _resolve_with_isaac_storage(
        DEFAULT_ISAAC_PEOPLE_CHARACTERS_PATH,
        context,
    )
    if resolved_default:
        return _select_reference_from_resolved(resolved_default, context)
    return None


def resolve_vehicle_asset_path(
    asset_path: str | None = None,
    context: Any | None = None,
) -> str | None:
    raw_path = str(asset_path or "").strip()
    if raw_path:
        return _resolve_asset_reference(raw_path, context, asset_kind="vehicle")

    for default_path in DEFAULT_ISAAC_VEHICLE_PATHS:
        resolved_default = _resolve_with_isaac_storage(default_path, context)
        if not resolved_default:
            continue
        resolved_asset = _select_reference_from_resolved(
            resolved_default,
            context,
            asset_kind="vehicle",
        )
        if resolved_asset:
            return resolved_asset
    return None


def resolve_pedestrian_animation_clip_path(
    clip_path: str | None = None,
    asset_path: str | None = None,
    context: Any | None = None,
) -> str | None:
    raw_path = str(clip_path or "").strip()
    if raw_path:
        return _resolve_animation_clip_reference(raw_path, context)

    for candidate_dir in _candidate_animation_clip_dirs_for_asset(asset_path):
        candidate = _first_usd_in_dir(candidate_dir, asset_kind="animation")
        if candidate is not None:
            return str(candidate)
    return None


def spawn_actor_visual(
    stage: Any,
    context: Any,
    root_prim_path: str,
    actor_type: str,
    shape: Any | None = None,
    visual_config: DynamicVisualConfig | None = None,
) -> str:
    config = _normalize_visual_config(visual_config)
    _clear_known_visual_children(stage, context, root_prim_path)

    if actor_type == "pedestrian" and config.pedestrian_visual == "asset":
        asset_path = resolve_pedestrian_asset_path(
            config.pedestrian_asset_path,
            context,
        )
        if asset_path is not None:
            try:
                _spawn_referenced_asset_visual(
                    stage,
                    context,
                    root_prim_path,
                    asset_path,
                    config.pedestrian_asset_scale,
                    config.pedestrian_asset_fit,
                    shape,
                )
                _maybe_bind_pedestrian_animation_clip(
                    stage,
                    context,
                    root_prim_path,
                    asset_path,
                    config,
                )
                return "asset"
            except Exception as exc:  # pragma: no cover - Isaac/USD runtime path
                _warn_once(
                    "Pedestrian asset visual failed to load "
                    f"({asset_path}): {exc}. Falling back to proxy visual."
                )
        else:
            requested = config.pedestrian_asset_path or DEFAULT_ISAAC_PEOPLE_CHARACTERS_PATH
            _warn_once(
                "Pedestrian asset visual unavailable: "
                f"{requested}. Falling back to proxy visual."
            )

    if actor_type == "vehicle" and config.vehicle_visual == "asset":
        asset_path = resolve_vehicle_asset_path(config.vehicle_asset_path, context)
        if asset_path is not None:
            try:
                _spawn_referenced_asset_visual(
                    stage,
                    context,
                    root_prim_path,
                    asset_path,
                    config.vehicle_asset_scale,
                    config.vehicle_asset_fit,
                    shape,
                    actor_type="vehicle",
                )
                return "asset"
            except Exception as exc:  # pragma: no cover - Isaac/USD runtime path
                _warn_once(
                    "Vehicle asset visual failed to load "
                    f"({asset_path}): {exc}. Falling back to proxy visual."
                )
        else:
            requested = config.vehicle_asset_path or ", ".join(DEFAULT_ISAAC_VEHICLE_PATHS)
            _warn_once(
                "Vehicle asset visual unavailable: "
                f"{requested}. Falling back to proxy visual."
            )

    spec = proxy_visual_spec_for_actor(actor_type, shape)
    spawn_proxy_visual(stage, context, root_prim_path, spec)
    return "proxy"


def spawn_proxy_visual(stage: Any, context: Any, root_prim_path: str, spec: ProxyVisualSpec) -> None:
    for part in spec.parts:
        part_path = f"{root_prim_path}/{part.name}"
        prim = _define_primitive(stage, context, part_path, part.primitive_type)
        prim.CreateDisplayColorAttr().Set([context.pxr_gf.Vec3f(*part.color_rgb)])

        xformable = context.pxr_usd_geom.Xformable(prim.GetPrim())
        xformable.ClearXformOpOrder()
        xformable.AddTranslateOp().Set(context.pxr_gf.Vec3d(*part.translate_xyz))
        xformable.AddScaleOp().Set(context.pxr_gf.Vec3f(*part.scale_xyz))


def _normalize_visual_config(
    visual_config: DynamicVisualConfig | None,
) -> DynamicVisualConfig:
    config = visual_config or DynamicVisualConfig()
    pedestrian_visual = str(config.pedestrian_visual or DEFAULT_PEDESTRIAN_VISUAL).lower()
    if pedestrian_visual not in {"proxy", "asset"}:
        pedestrian_visual = DEFAULT_PEDESTRIAN_VISUAL
    return DynamicVisualConfig(
        pedestrian_visual=pedestrian_visual,
        pedestrian_asset_path=str(config.pedestrian_asset_path or "").strip(),
        pedestrian_asset_scale=max(1e-6, float(config.pedestrian_asset_scale or 1.0)),
        pedestrian_asset_fit=_normalize_asset_fit(
            getattr(config, "pedestrian_asset_fit", DEFAULT_PEDESTRIAN_ASSET_FIT)
        ),
        pedestrian_animation=_normalize_pedestrian_animation(
            getattr(config, "pedestrian_animation", DEFAULT_PEDESTRIAN_ANIMATION)
        ),
        pedestrian_animation_clip_path=str(
            getattr(
                config,
                "pedestrian_animation_clip_path",
                DEFAULT_PEDESTRIAN_ANIMATION_CLIP_PATH,
            )
            or ""
        ).strip(),
        pedestrian_animation_time_scale=max(
            1e-6,
            float(
                getattr(
                    config,
                    "pedestrian_animation_time_scale",
                    DEFAULT_PEDESTRIAN_ANIMATION_TIME_SCALE,
                )
                or DEFAULT_PEDESTRIAN_ANIMATION_TIME_SCALE
            ),
        ),
        vehicle_visual=_normalize_visual_mode(
            getattr(config, "vehicle_visual", DEFAULT_VEHICLE_VISUAL)
        ),
        vehicle_asset_path=str(
            getattr(config, "vehicle_asset_path", DEFAULT_VEHICLE_ASSET_PATH) or ""
        ).strip(),
        vehicle_asset_scale=max(
            1e-6,
            float(getattr(config, "vehicle_asset_scale", DEFAULT_VEHICLE_ASSET_SCALE) or 1.0),
        ),
        vehicle_asset_fit=_normalize_vehicle_asset_fit(
            getattr(config, "vehicle_asset_fit", DEFAULT_VEHICLE_ASSET_FIT)
        ),
    )


def _normalize_visual_mode(visual_mode: str | None) -> str:
    mode = str(visual_mode or "proxy").strip().lower()
    if mode in {"proxy", "asset"}:
        return mode
    return "proxy"


def _normalize_pedestrian_animation(animation_mode: str | None) -> str:
    mode = str(animation_mode or DEFAULT_PEDESTRIAN_ANIMATION).strip().lower()
    if mode in {"none", "clip"}:
        return mode
    return DEFAULT_PEDESTRIAN_ANIMATION


def _normalize_asset_fit(asset_fit: str | None) -> str:
    fit_mode = str(asset_fit or DEFAULT_PEDESTRIAN_ASSET_FIT).strip().lower()
    if fit_mode in {"height", "none"}:
        return fit_mode
    return DEFAULT_PEDESTRIAN_ASSET_FIT


def _normalize_vehicle_asset_fit(asset_fit: str | None) -> str:
    fit_mode = str(asset_fit or DEFAULT_VEHICLE_ASSET_FIT).strip().lower()
    if fit_mode in {"shape", "none"}:
        return fit_mode
    return DEFAULT_VEHICLE_ASSET_FIT


def _resolve_asset_reference(
    raw_path: str,
    context: Any | None,
    asset_kind: str = "pedestrian",
) -> str | None:
    local_asset = _select_local_usd(raw_path, asset_kind=asset_kind)
    if local_asset is not None:
        return str(local_asset)

    if _looks_like_url(raw_path):
        if _is_usd_file_reference(raw_path):
            return raw_path
        return _select_usd_from_remote_dir(raw_path, asset_kind=asset_kind)

    if Path(raw_path).expanduser().is_absolute():
        return None

    resolved = _resolve_with_isaac_storage(raw_path, context)
    if resolved is None or resolved == raw_path:
        return None
    return _select_reference_from_resolved(resolved, context, asset_kind=asset_kind)


def _select_reference_from_resolved(
    resolved_path: str,
    context: Any | None,
    asset_kind: str = "pedestrian",
) -> str | None:
    local_asset = _select_local_usd(resolved_path, asset_kind=asset_kind)
    if local_asset is not None:
        return str(local_asset)
    if _looks_like_url(resolved_path):
        if _is_usd_file_reference(resolved_path):
            return resolved_path
        return _select_usd_from_remote_dir(resolved_path, asset_kind=asset_kind)
    return None


def _resolve_with_isaac_storage(raw_path: str, context: Any | None) -> str | None:
    try:
        from isaacsim.storage.native import get_assets_root_path, get_full_asset_path
    except Exception:
        return _resolve_with_carb_asset_root(raw_path, context)

    try:
        full_path = get_full_asset_path(raw_path)
    except Exception:
        full_path = None
    if full_path:
        return str(full_path)

    try:
        root_path = get_assets_root_path(skip_check=True)
    except TypeError:
        try:
            root_path = get_assets_root_path()
        except Exception:
            root_path = None
    except Exception:
        root_path = None

    if root_path:
        return f"{str(root_path).rstrip('/')}/{raw_path.lstrip('/')}"
    return _resolve_with_carb_asset_root(raw_path, context)


def _resolve_with_carb_asset_root(raw_path: str, context: Any | None) -> str | None:
    try:
        import carb.settings

        root_path = carb.settings.get_settings().get(
            "/persistent/isaac/asset_root/default"
        )
    except Exception:
        root_path = None

    if root_path:
        return f"{str(root_path).rstrip('/')}/{raw_path.lstrip('/')}"
    return None


def _select_local_usd(path_text: str, asset_kind: str = "pedestrian") -> Path | None:
    path = Path(path_text).expanduser()
    if path.is_file() and path.suffix.lower() in USD_SUFFIXES:
        return path.resolve()
    if path.is_dir():
        return _first_usd_in_dir(path, asset_kind=asset_kind)
    return None


def _first_usd_in_dir(directory: Path, asset_kind: str = "pedestrian") -> Path | None:
    usd_files = sorted(
        candidate
        for candidate in directory.rglob("*")
        if candidate.is_file() and candidate.suffix.lower() in USD_SUFFIXES
    )
    if asset_kind == "animation":
        return (
            sorted(usd_files, key=_animation_clip_sort_key)[0].resolve()
            if usd_files
            else None
        )
    if asset_kind == "vehicle":
        for candidate in usd_files:
            if _is_preferred_street_vehicle_usd(candidate):
                return candidate.resolve()
    else:
        for candidate in usd_files:
            if _is_preferred_character_usd(candidate):
                return candidate.resolve()
    return usd_files[0].resolve() if usd_files else None


def _resolve_animation_clip_reference(
    raw_path: str,
    context: Any | None,
) -> str | None:
    local_asset = _select_local_usd(raw_path, asset_kind="animation")
    if local_asset is not None:
        return str(local_asset)

    if _looks_like_url(raw_path):
        if _is_usd_file_reference(raw_path):
            return raw_path
        return _select_usd_from_remote_dir(raw_path, asset_kind="animation")

    if Path(raw_path).expanduser().is_absolute():
        return None

    resolved = _resolve_with_isaac_storage(raw_path, context)
    if resolved is None or resolved == raw_path:
        return None
    return _select_reference_from_resolved(resolved, context, asset_kind="animation")


def _candidate_animation_clip_dirs_for_asset(asset_path: str | None) -> tuple[Path, ...]:
    if not asset_path or _looks_like_url(str(asset_path)):
        return ()

    path = Path(str(asset_path)).expanduser()
    start = path.parent if path.suffix.lower() in USD_SUFFIXES else path
    roots = [start]
    roots.extend(list(start.parents)[:6])

    candidates: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        for dirname in ("Motion", "Motions", "motion", "motions"):
            candidate = root / dirname
            if candidate.is_dir() and candidate not in seen:
                seen.add(candidate)
                candidates.append(candidate)
    return tuple(candidates)


def _animation_clip_sort_key(path: Path) -> tuple[int, int, str]:
    searchable = "/".join(part.lower() for part in path.parts)
    keyword_rank = len(_ANIMATION_CLIP_KEYWORDS)
    for index, keyword in enumerate(_ANIMATION_CLIP_KEYWORDS):
        if keyword in searchable:
            keyword_rank = index
            break

    parts = {part.lower() for part in path.parts}
    structural_penalty = 10 if parts & {"props", "bones", "materials"} else 0
    return (keyword_rank, structural_penalty, str(path).lower())


def _is_preferred_street_vehicle_usd(path: Path) -> bool:
    lower_parts = [part.lower() for part in path.parts]
    lower_name = path.name.lower()
    if any(part in {"materials", "textures", "wheels", "wheel"} for part in lower_parts):
        return False
    if "sedan" in lower_parts and lower_name.endswith(("fullasset.usda", "fullasset.usd")):
        return True
    if lower_name.endswith(("fullasset.usda", "fullasset.usd")):
        return True
    if any(kind in lower_parts for kind in ("sedan", "4wd", "van")) and path.suffix.lower() in USD_SUFFIXES:
        return True
    return False


def _is_preferred_character_usd(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    if parts & {"motion", "motions"}:
        return False
    if path.stem.lower() in {"default", "motion", "animation"}:
        return False
    return True


def _select_usd_from_remote_dir(path_text: str, asset_kind: str = "pedestrian") -> str | None:
    try:
        import omni.client
    except Exception:
        return None

    return _select_usd_from_remote_dir_recursive(
        omni.client,
        path_text.rstrip("/"),
        remaining_depth=3,
        visited=set(),
        asset_kind=asset_kind,
    )


def _select_usd_from_remote_dir_recursive(
    omni_client: Any,
    path_text: str,
    remaining_depth: int,
    visited: set[str],
    asset_kind: str = "pedestrian",
) -> str | None:
    if remaining_depth < 0 or path_text in visited:
        return None
    visited.add(path_text)

    try:
        result, entries = omni_client.list(path_text)
    except Exception:
        return None

    if "OK" not in str(result):
        return None

    child_dirs: list[str] = []
    usd_children: list[str] = []
    for entry in sorted(entries, key=lambda item: getattr(item, "relative_path", "")):
        relative_path = getattr(entry, "relative_path", "")
        if not relative_path:
            continue
        child_path = f"{path_text}/{relative_path}"
        if Path(relative_path).suffix.lower() in USD_SUFFIXES:
            usd_children.append(child_path)
            continue
        child_dirs.append(child_path)

    if asset_kind == "animation":
        if usd_children:
            return sorted(usd_children, key=lambda child: _animation_clip_sort_key(Path(child)))[0]
    elif asset_kind == "vehicle":
        for child_path in usd_children:
            if _is_preferred_street_vehicle_usd(Path(child_path)):
                return child_path
    else:
        for child_path in usd_children:
            if _is_preferred_character_usd(Path(child_path)):
                return child_path
    if usd_children:
        return usd_children[0]

    for child_path in child_dirs:
        resolved = _select_usd_from_remote_dir_recursive(
            omni_client,
            child_path,
            remaining_depth - 1,
            visited,
            asset_kind=asset_kind,
        )
        if resolved is not None:
            return resolved
    return None


def _looks_like_url(path_text: str) -> bool:
    return path_text.startswith(("omniverse://", "http://", "https://", "s3://"))


def _is_usd_file_reference(path_text: str) -> bool:
    return Path(path_text.split("?")[0]).suffix.lower() in USD_SUFFIXES


def _maybe_bind_pedestrian_animation_clip(
    stage: Any,
    context: Any,
    root_prim_path: str,
    asset_path: str,
    config: DynamicVisualConfig,
) -> None:
    if _normalize_pedestrian_animation(config.pedestrian_animation) != "clip":
        return

    clip_path = resolve_pedestrian_animation_clip_path(
        config.pedestrian_animation_clip_path,
        asset_path=asset_path,
        context=context,
    )
    if clip_path is None:
        requested = config.pedestrian_animation_clip_path or f"Motion/Motions near {asset_path}"
        _warn_once(
            "Pedestrian animation clip unavailable: "
            f"{requested}. Keeping static pedestrian asset."
        )
        return

    try:
        _spawn_animation_clip_reference_and_bind(
            stage,
            context,
            root_prim_path,
            clip_path,
            config.pedestrian_animation_time_scale,
        )
    except Exception as exc:  # pragma: no cover - Isaac/USD runtime path
        _warn_once(
            "Pedestrian animation clip failed to bind "
            f"({clip_path}): {exc}. Keeping static pedestrian asset."
        )


def _spawn_animation_clip_reference_and_bind(
    stage: Any,
    context: Any,
    root_prim_path: str,
    clip_path: str,
    time_scale: float,
) -> None:
    animation_prim_path = f"{root_prim_path}/{_ANIMATION_CHILD_NAME}"
    animation_prim = context.pxr_usd_geom.Xform.Define(
        stage,
        animation_prim_path,
    ).GetPrim()
    references = animation_prim.GetReferences()
    references.ClearReferences()
    _add_animation_reference(references, context, clip_path, time_scale)
    _set_animation_time_scale_attr(animation_prim, context, time_scale)

    asset_prim = stage.GetPrimAtPath(f"{root_prim_path}/{_ASSET_CHILD_NAME}")
    skeleton_prim = _find_first_prim_with_type(asset_prim, "Skeleton")
    animation_source_prim = _find_first_prim_with_type(animation_prim, "SkelAnimation")
    if skeleton_prim is None:
        raise RuntimeError("No Skeleton prim found under pedestrian Asset.")
    if animation_source_prim is None:
        raise RuntimeError("No SkelAnimation prim found under Animation clip.")

    _bind_skeleton_animation_source(skeleton_prim, animation_source_prim)
    print(
        "[OK] Bound pedestrian animation clip: "
        f"{clip_path} -> {skeleton_prim.GetPath()}"
    )


def _add_animation_reference(
    references: Any,
    context: Any,
    clip_path: str,
    time_scale: float,
) -> None:
    scale = max(1e-6, float(time_scale or DEFAULT_PEDESTRIAN_ANIMATION_TIME_SCALE))
    if abs(scale - 1.0) > 1e-9:
        try:
            layer_offset = context.pxr_Sdf.LayerOffset(0.0, scale)
            references.AddReference(
                clip_path,
                context.pxr_Sdf.Path.emptyPath,
                layer_offset,
            )
            return
        except Exception:
            pass
    references.AddReference(clip_path)


def _set_animation_time_scale_attr(prim: Any, context: Any, time_scale: float) -> None:
    try:
        attr = prim.CreateAttribute(
            "lc_proto:animationTimeScale",
            context.pxr_Sdf.ValueTypeNames.Double,
        )
        attr.Set(float(time_scale or DEFAULT_PEDESTRIAN_ANIMATION_TIME_SCALE))
    except Exception:
        return


def _find_first_prim_with_type(root_prim: Any, type_name: str) -> Any | None:
    try:
        if root_prim is None or not root_prim.IsValid():
            return None
    except Exception:
        return None

    stack = [root_prim]
    while stack:
        prim = stack.pop(0)
        try:
            if prim.GetTypeName() == type_name:
                return prim
            stack.extend(list(prim.GetChildren()))
        except Exception:
            continue
    return None


def _bind_skeleton_animation_source(skeleton_prim: Any, animation_source_prim: Any) -> None:
    try:
        from pxr import UsdSkel

        binding_api = UsdSkel.BindingAPI.Apply(skeleton_prim)
        relationship = binding_api.CreateAnimationSourceRel()
    except Exception:
        relationship = skeleton_prim.CreateRelationship("skel:animationSource")

    relationship.SetTargets([animation_source_prim.GetPath()])


def _spawn_referenced_asset_visual(
    stage: Any,
    context: Any,
    root_prim_path: str,
    asset_path: str,
    asset_scale: float,
    asset_fit: str,
    shape: Any | None,
    actor_type: str = "pedestrian",
) -> None:
    asset_prim_path = f"{root_prim_path}/{_ASSET_CHILD_NAME}"
    prim = context.pxr_usd_geom.Xform.Define(stage, asset_prim_path).GetPrim()
    references = prim.GetReferences()
    references.ClearReferences()
    references.AddReference(asset_path)

    bounds = _compute_stage_asset_bounds(stage, context, prim)
    if actor_type == "vehicle":
        transform = vehicle_asset_transform_for_bounds(
            bounds,
            shape,
            asset_scale=asset_scale,
            asset_fit=asset_fit,
        )
        if asset_fit == "shape" and not transform.fit_applied:
            _warn_once(
                "Vehicle asset shape fit unavailable for "
                f"{asset_path}; using manual scale {asset_scale}."
            )
        transform = _asset_transform_with_z_offset(
            transform,
            _asset_visual_z_offset_m(prim),
        )
        rotate_z_deg = 0.0
    else:
        transform = pedestrian_asset_transform_for_bounds(
            bounds,
            shape,
            asset_scale=asset_scale,
            asset_fit=asset_fit,
        )
        if asset_fit == "height" and not transform.fit_applied:
            _warn_once(
                "Pedestrian asset height fit unavailable for "
                f"{asset_path}; using manual scale {asset_scale}."
            )
        rotate_z_deg = 90.0

    xformable = context.pxr_usd_geom.Xformable(prim)
    xformable.ClearXformOpOrder()
    xformable.AddTranslateOp().Set(context.pxr_gf.Vec3d(*transform.translate_xyz))
    xformable.AddRotateXYZOp().Set(context.pxr_gf.Vec3f(0.0, 0.0, rotate_z_deg))
    xformable.AddScaleOp().Set(
        context.pxr_gf.Vec3f(transform.scale, transform.scale, transform.scale)
    )


def _asset_transform_with_z_offset(
    transform: AssetVisualTransform,
    z_offset_m: float,
) -> AssetVisualTransform:
    if abs(z_offset_m) < 1e-9:
        return transform
    return AssetVisualTransform(
        scale=transform.scale,
        translate_xyz=(
            transform.translate_xyz[0],
            transform.translate_xyz[1],
            transform.translate_xyz[2] + z_offset_m,
        ),
        fit_applied=transform.fit_applied,
    )


def _asset_visual_z_offset_m(prim: Any) -> float:
    for attr_name in ("lc_proto:visualZOffsetM", "lc_proto:assetZOffsetM"):
        try:
            attr = prim.GetAttribute(attr_name)
        except Exception:
            continue
        try:
            if attr and attr.HasAuthoredValueOpinion():
                return float(attr.Get() or 0.0)
        except Exception:
            continue
    return 0.0


def _compute_stage_asset_bounds(
    stage: Any,
    context: Any,
    prim: Any,
) -> AssetBounds | None:
    try:
        UsdGeom = context.pxr_usd_geom
        Usd = context.pxr_usd
        purposes = [UsdGeom.Tokens.default_, UsdGeom.Tokens.render]
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), purposes)
        bbox = cache.ComputeWorldBound(prim)
        aligned_range = bbox.ComputeAlignedRange()
        if aligned_range.IsEmpty():
            return None
        min_vec = aligned_range.GetMin()
        max_vec = aligned_range.GetMax()
    except Exception:
        return None

    return AssetBounds(
        min_xyz=(float(min_vec[0]), float(min_vec[1]), float(min_vec[2])),
        max_xyz=(float(max_vec[0]), float(max_vec[1]), float(max_vec[2])),
    )


def _clear_known_visual_children(stage: Any, context: Any, root_prim_path: str) -> None:
    for child_name in _KNOWN_VISUAL_CHILDREN:
        child_path = f"{root_prim_path}/{child_name}"
        prim = stage.GetPrimAtPath(child_path)
        if not prim.IsValid():
            continue
        try:
            stage.RemovePrim(child_path)
        except TypeError:
            stage.RemovePrim(context.pxr_Sdf.Path(child_path))


def _warn_once(message: str) -> None:
    if message in _WARNED_MESSAGES:
        return
    _WARNED_MESSAGES.add(message)
    print(f"[WARN] {message}")


def _define_primitive(stage: Any, context: Any, prim_path: str, primitive_type: str) -> Any:
    UsdGeom = context.pxr_usd_geom
    if primitive_type == "sphere":
        sphere = UsdGeom.Sphere.Define(stage, prim_path)
        sphere.CreateRadiusAttr(1.0)
        return sphere
    if primitive_type == "cylinder":
        cylinder = UsdGeom.Cylinder.Define(stage, prim_path)
        cylinder.CreateRadiusAttr(1.0)
        cylinder.CreateHeightAttr(1.0)
        return cylinder

    cube = UsdGeom.Cube.Define(stage, prim_path)
    cube.CreateSizeAttr(1.0)
    return cube


def _pedestrian_proxy_visual_spec(shape: Any | None) -> ProxyVisualSpec:
    height = max(1.2, float(_field(shape, "height_m", 1.7) or 1.7))
    radius = max(0.18, float(_field(shape, "radius_m", 0.35) or 0.35))
    leg_height = height * 0.32
    torso_height = height * 0.45
    head_radius = min(radius * 0.72, height * 0.13)
    torso_radius = radius * 0.78

    return ProxyVisualSpec(
        actor_type="pedestrian",
        bounds_xyz=(radius * 2.0, radius * 2.0, height),
        parts=(
            ProxyPrimitiveSpec(
                name="Legs",
                primitive_type="cylinder",
                translate_xyz=(0.0, 0.0, leg_height * 0.5),
                scale_xyz=(radius * 0.48, radius * 0.48, leg_height),
                color_rgb=(0.18, 0.22, 0.24),
            ),
            ProxyPrimitiveSpec(
                name="Torso",
                primitive_type="cylinder",
                translate_xyz=(0.0, 0.0, leg_height + torso_height * 0.5),
                scale_xyz=(torso_radius, torso_radius, torso_height),
                color_rgb=(0.88, 0.28, 0.16),
            ),
            ProxyPrimitiveSpec(
                name="Head",
                primitive_type="sphere",
                translate_xyz=(0.0, 0.0, leg_height + torso_height + head_radius),
                scale_xyz=(head_radius, head_radius, head_radius),
                color_rgb=(0.82, 0.62, 0.45),
            ),
        ),
    )


def _vehicle_proxy_visual_spec(shape: Any | None) -> ProxyVisualSpec:
    length = max(2.0, float(_field(shape, "length_m", 4.5) or 4.5))
    width = max(1.0, float(_field(shape, "width_m", 1.8) or 1.8))
    height = max(0.8, float(_field(shape, "height_m", 1.6) or 1.6))
    body_height = height * 0.55
    cabin_height = height * 0.32

    return ProxyVisualSpec(
        actor_type="vehicle",
        bounds_xyz=(length, width, height),
        parts=(
            ProxyPrimitiveSpec(
                name="Body",
                primitive_type="cube",
                translate_xyz=(0.0, 0.0, body_height * 0.5),
                scale_xyz=(length, width, body_height),
                color_rgb=(0.08, 0.30, 0.82),
            ),
            ProxyPrimitiveSpec(
                name="Cabin",
                primitive_type="cube",
                translate_xyz=(-length * 0.08, 0.0, body_height + cabin_height * 0.5),
                scale_xyz=(length * 0.42, width * 0.72, cabin_height),
                color_rgb=(0.08, 0.12, 0.16),
            ),
            ProxyPrimitiveSpec(
                name="FrontMarker",
                primitive_type="cube",
                translate_xyz=(length * 0.5 + 0.02, 0.0, body_height * 0.58),
                scale_xyz=(0.08, width * 0.62, body_height * 0.22),
                color_rgb=(0.95, 0.78, 0.18),
            ),
            ProxyPrimitiveSpec(
                name="RearMarker",
                primitive_type="cube",
                translate_xyz=(-length * 0.5 - 0.02, 0.0, body_height * 0.58),
                scale_xyz=(0.08, width * 0.62, body_height * 0.22),
                color_rgb=(0.70, 0.06, 0.05),
            ),
        ),
    )


def _field(value: Any | None, name: str, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)
