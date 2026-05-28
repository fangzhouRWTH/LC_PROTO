from __future__ import annotations

from pathlib import Path


ISAAC_ENV_ROOT = Path(__file__).resolve().parent
DEFAULT_ASSET_DIR = ISAAC_ENV_ROOT / "default_asset"
DEFAULT_SHADER_DIR = ISAAC_ENV_ROOT / "default_shader"

DEFAULT_FOG_BILLBOARD_TEXTURE = DEFAULT_ASSET_DIR / "fog_billboard_alpha.png"
DEFAULT_FOG_BILLBOARD_SHADER = DEFAULT_SHADER_DIR / "fog_billboard.mdl"
