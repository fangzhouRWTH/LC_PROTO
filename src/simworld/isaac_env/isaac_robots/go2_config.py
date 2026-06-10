"""Unitree Go2 policy asset paths and observation layout (Isaac-free)."""

from __future__ import annotations

import os
import pathlib
import zipfile

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[4]
DEFAULT_UNITREEGO_DIR = PROJECT_ROOT / "unitreego"
DEFAULT_POLICY_CHECKPOINT = "model_5300.pt"
DEFAULT_ENV_CONFIG = "env.yaml"
GO2_ARTICULATION_SUBPATH = "go2_description"

# Matches unitreego/env.yaml observations.policy (blind rough, no base_lin_vel).
OBS_DIM = 45
ACTION_DIM = 12
ANG_VEL_OBS_SCALE = 0.2
JOINT_VEL_OBS_SCALE = 0.05
ACTION_SCALE = 0.25


class Go2UsdNotFoundError(FileNotFoundError):
    """Raised when no local Go2 USD can be resolved."""


def unitreego_asset_dir() -> pathlib.Path:
    return DEFAULT_UNITREEGO_DIR


def go2_articulation_root_path(prim_path: str) -> str:
    return f"{prim_path.rstrip('/')}/{GO2_ARTICULATION_SUBPATH}"


def omniverse_readable_path(path: str | pathlib.Path) -> str:
    resolved = pathlib.Path(str(path).replace("file://", "")).expanduser().resolve()
    if resolved.is_file():
        return resolved.as_uri()
    return str(path)


def is_torchscript_policy(path: str | pathlib.Path) -> bool:
    policy_path = pathlib.Path(path)
    if not policy_path.is_file() or not zipfile.is_zipfile(policy_path):
        return False
    with zipfile.ZipFile(policy_path) as archive:
        return any(
            name.startswith("code/__torch__") or "_traced" in name
            for name in archive.namelist()
        )


def _strip_uri_prefix(path: str) -> str:
    return path.replace("file://", "").strip()


def local_go2_usd_candidates(assets_root_path: str | None = None) -> tuple[pathlib.Path, ...]:
    candidates: list[pathlib.Path] = []

    override = os.environ.get("GO2_USD_PATH", "").strip()
    if override:
        candidates.append(pathlib.Path(_strip_uri_prefix(override)))

    asset_root = os.environ.get("ISAAC_ASSET_ROOT", "").strip()
    if asset_root:
        root = pathlib.Path(_strip_uri_prefix(asset_root))
        candidates.extend(
            (
                root / "Isaac/IsaacLab/Robots/Unitree/Go2/go2.usd",
                root / "Isaac/Robots/Unitree/Go2/go2.usd",
            )
        )

    if assets_root_path:
        root_text = _strip_uri_prefix(assets_root_path)
        if not root_text.startswith(("omniverse:", "http://", "https://")):
            root = pathlib.Path(root_text)
            candidates.extend(
                (
                    root / "Isaac/IsaacLab/Robots/Unitree/Go2/go2.usd",
                    root / "Isaac/Robots/Unitree/Go2/go2.usd",
                )
            )

    candidates.append(
        pathlib.Path.home()
        / "isaacsim_assets/Assets/Isaac/5.1/Isaac/IsaacLab/Robots/Unitree/Go2/go2.usd"
    )
    return tuple(candidates)


def resolve_local_go2_usd_path(assets_root_path: str | None = None) -> pathlib.Path:
    seen: set[pathlib.Path] = set()
    for candidate in local_go2_usd_candidates(assets_root_path):
        resolved = candidate.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file():
            return resolved
    raise Go2UsdNotFoundError(
        "Unitree Go2 USD not found locally. Set GO2_USD_PATH or ISAAC_ASSET_ROOT, "
        "or install Isaac/IsaacLab/Robots/Unitree/Go2/go2.usd under your Isaac assets."
    )


def default_go2_usd_path(assets_root_path: str | None = None) -> str:
    return resolve_local_go2_usd_path(assets_root_path).as_uri()


def resolve_go2_usd_uri(assets_root_path: str | None = None) -> str:
    """Resolve Go2 USD without calling Isaac Sim get_assets_root_path()."""
    return default_go2_usd_path(assets_root_path)
