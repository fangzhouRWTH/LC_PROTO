#!/usr/bin/env python3
"""Reorganize lcstd static USD library for area_placement_methods name map."""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC = REPO_ROOT / "assets" / "lcstd_assets_library" / "static"

# LCSTD filename prefix -> usd/ subdirectory
_LCSTD_PREFIX_TO_DIR = {
    "asset_commercialandsignage_universal_": "commercial_and_signage",
    "asset_streetfurnitureandpublicfacility_universal_": "street_furniture",
    "asset_trafficinfrastructure_universal_": "traffic_infrastructure",
    "asset_vegetationandenvironment_universal_": "vegetation_and_environment",
}

# asset_candidates_name (ps_asset_config) -> (usd subdir, basename under that dir)
_PRIMARY_MAP: dict[str, tuple[str, str]] = {
    "guangzhou_bus_stop": ("traffic_infrastructure", "busstop_01.usd"),
    "tree_pool": ("vegetation_and_environment", "universaltree_01.usd"),
    "flower_box": ("vegetation_and_environment", "plantbox_01.usd"),
    "street_light": ("street_furniture", "standardstreetlight_01.usd"),
    "trash_bin": ("street_furniture", "standardbin_01.usd"),
    "fire_hydrant": ("street_furniture", "standardfirehydrant_01.usd"),
    "bollard": ("traffic_infrastructure", "trafficcone_01.usd"),
    "traffic_light_vehicle": (
        "traffic_infrastructure",
        "standardtrafficlightvehicle_01.usd",
    ),
    "traffic_light_pedestrian": (
        "traffic_infrastructure",
        "standardtrafficlightpedestrian_01.usd",
    ),
    "metro_sign": ("commercial_and_signage", "modernbusinesssignage_01.usd"),
    "vending_machine": ("street_furniture", "atm_01.usd"),
    "smart_locker": ("commercial_and_signage", "deliverylocker_01.usd"),
    "long_bench": ("street_furniture", "streetbench_01.usd"),
    "seat_group": ("street_furniture", "tablechair_01.usd"),
    "food_cart": ("commercial_and_signage", "foodtrailer_01.usd"),
}

# Extra LCSTD assets (no dedicated algorithm name yet)
_EXTRA_BY_DIR: dict[str, list[str]] = {
    "commercial_and_signage": ["modernbusinesssignage_02.usd"],
    "street_furniture": [
        "atm_02.usd",
        "dumpster_01.usd",
        "dumpster_02.usd",
        "standardbin_02.usd",
        "standardstreetlight_02.usd",
        "standardstreetlight_03.usd",
        "streetbench_02.usd",
        "streetbench_03.usd",
        "streetbench_04.usd",
        "streetbench_05.usd",
        "streetbench_06.usd",
        "tablechair_02.usd",
        "tablechair_03.usd",
        "tablechair_04.usd",
        "tablechair_05.usd",
    ],
    "traffic_infrastructure": ["crashbarrel_01.usd"],
    "vegetation_and_environment": [
        "plantbox_02.usd",
        "universaltree_02.usd",
        "universaltree_03.usd",
    ],
}

_ALGORITHM_NAMES_MISSING_USD = (
    "shared_bike_parking",
    "guard_rail",
    "entrance_canopy",
    "sculpture",
    "grass_patch",
)


def _short_usd_name(lcstd_filename: str) -> str:
    for prefix in _LCSTD_PREFIX_TO_DIR:
        if lcstd_filename.startswith(prefix) and lcstd_filename.endswith(".usd"):
            return lcstd_filename[len(prefix) :]
    return lcstd_filename


def _lcstd_dir_for_file(filename: str) -> str | None:
    for prefix, subdir in _LCSTD_PREFIX_TO_DIR.items():
        if filename.startswith(prefix):
            return subdir
    return None


def _move_root_assets() -> dict[str, Path]:
    """Move flat asset_*.usd / *.blend into usd/ and blend/ subtrees. Returns short->path."""
    usd_index: dict[str, Path] = {}
    for subdir in _LCSTD_PREFIX_TO_DIR.values():
        (STATIC / "usd" / subdir).mkdir(parents=True, exist_ok=True)
        (STATIC / "blend" / subdir).mkdir(parents=True, exist_ok=True)

    for path in sorted(STATIC.glob("asset_*.usd")):
        subdir = _lcstd_dir_for_file(path.name)
        if subdir is None:
            continue
        short = _short_usd_name(path.name)
        target = STATIC / "usd" / subdir / short
        if path.resolve() != target.resolve():
            if target.exists():
                target.unlink()
            shutil.move(str(path), str(target))
        usd_index[short] = target

    for path in sorted(STATIC.glob("asset_*.blend")):
        subdir = _lcstd_dir_for_file(path.name)
        if subdir is None:
            continue
        short = path.name
        for prefix in _LCSTD_PREFIX_TO_DIR:
            if short.startswith(prefix):
                short = short[len(prefix) :]
                break
        target = STATIC / "blend" / subdir / short
        if path.resolve() != target.resolve():
            if target.exists():
                target.unlink()
            shutil.move(str(path), str(target))

    return usd_index


def _link_public_space(usd_index: dict[str, Path]) -> dict[str, str]:
    public_space = STATIC / "public_space"
    if public_space.exists():
        shutil.rmtree(public_space)
    public_space.mkdir(parents=True)

    map_paths: dict[str, str] = {}
    for algo_name, (subdir, basename) in _PRIMARY_MAP.items():
        source = usd_index.get(basename) or (STATIC / "usd" / subdir / basename)
        if not source.is_file():
            raise FileNotFoundError(f"Missing USD for {algo_name}: {source}")
        dest_dir = public_space / algo_name
        dest_dir.mkdir(parents=True)
        dest = dest_dir / "default.usd"
        if dest.exists() or dest.is_symlink():
            dest.unlink()
        dest.symlink_to(source.resolve())
        map_paths[algo_name] = str(dest)

    extras_root = public_space / "_extras"
    extras_root.mkdir(parents=True)
    for subdir, names in _EXTRA_BY_DIR.items():
        extra_dir = extras_root / subdir
        extra_dir.mkdir(parents=True, exist_ok=True)
        for basename in names:
            source = usd_index.get(basename) or (STATIC / "usd" / subdir / basename)
            if not source.is_file():
                continue
            dest = extra_dir / basename
            if dest.exists() or dest.is_symlink():
                dest.unlink()
            dest.symlink_to(source.resolve())

    return map_paths


def _write_manifest(map_paths: dict[str, str]) -> None:
    payload = {
        "schema_version": "simworld.asset_name_map.v1",
        "library_root": str(STATIC.resolve()),
        "assets": map_paths,
        "notes": {
            "layout": "public_space/<asset_candidates_name>/default.usd",
            "source_usd": "usd/<lcstd_category>/<short_name>.usd",
            "textures": "textures/ (shared, do not move)",
            "algorithm_names_without_usd": list(_ALGORITHM_NAMES_MISSING_USD),
        },
    }
    map_path = STATIC / "asset_name_map.json"
    with map_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def _write_readme(map_paths: dict[str, str]) -> None:
    lines = [
        "# LCSTD static library (area placement)",
        "",
        "Aligned with `algorithm_lab/experiments/area_placement_methods/docs/SCENE_INPUT_AND_ASSET_LIBRARY_HANDBOOK.md`.",
        "",
        "## Layout",
        "",
        "```text",
        "static/",
        "  asset_name_map.json     # simworld.asset_name_map.v1 → Isaac --public-space-asset-name-map",
        "  textures/               # shared textures (keep path stable for USD references)",
        "  usd/<category>/         # canonical LCSTD exports (short filenames)",
        "  blend/<category>/       # Blender sources",
        "  public_space/<name>/    # one folder per asset_candidates_name",
        "    default.usd           # symlink → ../../usd/...",
        "    variants/             # optional extra symlinks",
        "  public_space/_extras/   # LCSTD assets not yet in EMBEDDED_ASSET_CANDIDATES",
        "```",
        "",
        "## Isaac",
        "",
        "```bash",
        "scripts/run_sim.sh \\",
        "  --layout-backend area_placement_methods \\",
        "  --use-dummy-public-space-assets false \\",
        f"  --public-space-asset-name-map {STATIC / 'asset_name_map.json'} \\",
        "  --scene-usd ...",
        "```",
        "",
        "## Mapped algorithm names",
        "",
        "| asset_candidates_name | default.usd |",
        "| --- | --- |",
    ]
    for name, path in sorted(map_paths.items()):
        rel = Path(path).relative_to(STATIC) if path.startswith(str(STATIC)) else path
        lines.append(f"| `{name}` | `{rel}` |")

    lines.extend(
        [
            "",
            "## Algorithm names without LCSTD USD yet",
            "",
        ]
    )
    for name in _ALGORITHM_NAMES_MISSING_USD:
        lines.append(f"- `{name}` (layout uses dummy cube until a USD is added)")

    lines.extend(
        [
            "",
            "## LCSTD → algorithm mapping notes",
            "",
            "| LCSTD asset | Maps to |",
            "| --- | --- |",
            "| `trafficcone_01` | `bollard` (placeholder) |",
            "| `crashbarrel_01` | `_extras` only |",
            "| `atm_*` | `vending_machine` |",
            "| `dumpster_*` | `_extras` only |",
            "",
            "Regenerate layout: `python3 scripts/organize_lcstd_static_library.py`",
            "",
            "Texture index (USD `textures/` relative paths + filename aliases):",
            "`python3 scripts/fix_lcstd_texture_index.py`",
        ]
    )
    (STATIC / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fix_texture_index() -> None:
    import subprocess

    script = REPO_ROOT / "scripts" / "fix_lcstd_texture_index.py"
    subprocess.run([sys.executable, str(script)], check=True)


def main() -> int:
    if not STATIC.is_dir():
        raise SystemExit(f"Not found: {STATIC}")

    usd_index = _move_root_assets()
    map_paths = _link_public_space(usd_index)
    _fix_texture_index()
    _write_manifest(map_paths)
    _write_readme(map_paths)
    print(f"[OK] Organized {len(map_paths)} public-space assets under {STATIC}")
    print(f"[OK] Wrote {STATIC / 'asset_name_map.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
