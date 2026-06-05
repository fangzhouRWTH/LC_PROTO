#!/usr/bin/env python3
"""Fix LCSTD USD texture lookup: relative textures/ dir + filename aliases."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC = REPO_ROOT / "assets" / "lcstd_assets_library" / "static"
TEXTURES = STATIC / "textures"
USD_ROOT = STATIC / "usd"

_MAP_SUFFIXES = (
    "_diffuse",
    "_normal",
    "_glossiness",
    "_opacity",
    "_height",
    "_roughness",
    "_albedo",
    "_displacement",
)

# USD token suffix -> on-disk suffix variants (case-insensitive)
_SUFFIX_ALIASES: dict[str, tuple[str, ...]] = {
    "_diffuse": ("_diffuse", "_albedo"),
    "_albedo": ("_albedo", "_diffuse"),
    "_normal": ("_normal",),
    "_glossiness": ("_glossiness", "_roughness"),
    "_roughness": ("_roughness", "_glossiness"),
    "_opacity": ("_opacity",),
    "_height": ("_height",),
    "_displacement": ("_displacement",),
}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _em_cts_tokens(usd_path: Path) -> list[str]:
    data = usd_path.read_bytes().decode("latin-1", errors="ignore")
    tokens = set(re.findall(r"EM_CTS_[A-Za-z0-9_& -]{4,72}", data))
    return sorted(
        t.strip()
        for t in tokens
        if "?" not in t and "@" not in t and len(t) > 8
    )


def _split_texture_name(filename: str) -> tuple[str, str, str] | None:
    """Return (material_prefix, map_suffix_lower, extension)."""
    if "." not in filename:
        return None
    stem, ext = filename.rsplit(".", 1)
    lower = stem.lower()
    for suffix in _MAP_SUFFIXES:
        if lower.endswith(suffix):
            return stem[: len(stem) - len(suffix)], suffix, f".{ext}"
    return None


def _texture_files() -> list[Path]:
    return sorted(p for p in TEXTURES.iterdir() if p.is_file() and not p.is_symlink())


def _token_variants(token: str) -> list[str]:
    """USD material names often add numeric variant suffixes not present on disk."""
    variants = [token]
    current = token
    while True:
        stripped = re.sub(r"_\d+$", "", current)
        if stripped == current or not stripped:
            break
        if stripped not in variants:
            variants.append(stripped)
        current = stripped
    return variants


def _norm_material(value: str) -> str:
    return _norm(value.replace("&", "_").replace("-", "_"))


def _resolve_sources(token: str, files: list[Path]) -> list[Path]:
    hits: list[Path] = []
    token_norms = {_norm_material(v) for v in _token_variants(token)}
    for path in files:
        parsed = _split_texture_name(path.name)
        if parsed is None:
            continue
        prefix, _, _ = parsed
        n_pre = _norm_material(prefix)
        if n_pre in token_norms:
            hits.append(path)
            continue
        # Trees_FlowerBox_04_441 -> shared Trees_FlowerBox_* maps on disk
        for variant in token_norms:
            if variant.startswith("emctstreesflowerbox") and n_pre.startswith(
                "emctstreesflowerbox"
            ):
                hits.append(path)
                break
        # HotDog_Trailer (USD) vs HotDog-Trailer_Buddy (files)
        for variant in token_norms:
            if not variant.startswith("emctshotdogtrailer"):
                continue
            if n_pre.startswith(variant) and len(n_pre) > len(variant):
                hits.append(path)
                break
    return sorted(set(hits))


def _ensure_usd_textures_symlinks() -> int:
    count = 0
    for category_dir in sorted(USD_ROOT.iterdir()):
        if not category_dir.is_dir():
            continue
        link = category_dir / "textures"
        target = Path("../../textures")
        if link.is_symlink() and link.resolve() == TEXTURES.resolve():
            continue
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(target, target_is_directory=True)
        count += 1
    return count


def _ensure_texture_aliases(tokens: set[str], files: list[Path], *, dry_run: bool) -> int:
    created = 0
    for token in sorted(tokens):
        sources = _resolve_sources(token, files)
        if not sources:
            print(f"[WARN] No texture files matched USD token: {token}", file=sys.stderr)
            continue

        by_suffix: dict[str, list[Path]] = {}
        for src in sources:
            parsed = _split_texture_name(src.name)
            if parsed is None:
                continue
            _, suffix, _ = parsed
            by_suffix.setdefault(suffix, []).append(src)

        for canonical_suffix, aliases in _SUFFIX_ALIASES.items():
            src_list = []
            for alias in aliases:
                src_list.extend(by_suffix.get(alias, []))
            if not src_list:
                continue
            src = src_list[0]
            parsed = _split_texture_name(src.name)
            if parsed is None:
                continue
            src_prefix, _, ext = parsed
            for out_suffix in aliases:
                alias_name = f"{token}{out_suffix}{ext}"
                if _create_alias(alias_name, src.name, dry_run=dry_run):
                    created += 1

        # Multi-map materials (HotDog-Trailer_* -> HotDog_Trailer_*)
        if _norm_material(token).startswith("emctshotdogtrailer"):
            for src in sources:
                if "HotDog-Trailer" not in src.name:
                    continue
                alias_name = src.name.replace("HotDog-Trailer", "HotDog_Trailer")
                if _create_alias(alias_name, src.name, dry_run=dry_run):
                    created += 1
    return created


def _create_alias(alias_name: str, source_name: str, *, dry_run: bool) -> bool:
    alias_path = TEXTURES / alias_name
    if alias_path.exists() or alias_path.is_symlink():
        return False
    if dry_run:
        print(f"[dry-run] {alias_name} -> {source_name}")
    else:
        alias_path.symlink_to(source_name)
    return True


def _clear_texture_symlinks() -> int:
    removed = 0
    for path in TEXTURES.iterdir():
        if path.is_symlink():
            path.unlink()
            removed += 1
    return removed


def main() -> int:
    if not TEXTURES.is_dir():
        raise SystemExit(f"Missing textures dir: {TEXTURES}")

    removed = 0 if "--dry-run" in sys.argv else _clear_texture_symlinks()
    files = _texture_files()
    tokens: set[str] = set()
    for usd_path in sorted(USD_ROOT.rglob("*.usd")):
        tokens.update(_em_cts_tokens(usd_path))

    dry_run = "--dry-run" in sys.argv
    link_count = 0 if dry_run else _ensure_usd_textures_symlinks()
    alias_count = _ensure_texture_aliases(tokens, files, dry_run=dry_run)

    if removed:
        print(f"[OK] Cleared {removed} stale texture alias symlinks")
    print(
        f"[OK] USD texture dirs: {link_count} symlinks under usd/*/textures -> ../../textures"
    )
    print(f"[OK] Texture filename aliases: {alias_count} under {TEXTURES}")
    print(f"[OK] USD material tokens scanned: {len(tokens)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
