"""Placeholder hide/remove helpers (no Isaac runtime)."""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field

from engine.scene_placeholder import (
    collect_placeholder_prim_paths,
    normalize_placeholder_disposition,
)


@dataclass
class _Area:
    prim_path: str = ""


@dataclass
class _Stats:
    placeholder_prim_paths: list[str] = field(default_factory=list)
    placeholder_areas: list[_Area] = field(default_factory=list)
    public_space_regions: list[_Area] = field(default_factory=list)


class ScenePlaceholderDispositionTests(unittest.TestCase):
    def test_normalize_placeholder_disposition_aliases(self):
        self.assertEqual(normalize_placeholder_disposition("hide"), "hidden")
        self.assertEqual(normalize_placeholder_disposition("remove"), "remove")
        self.assertEqual(normalize_placeholder_disposition("delete"), "remove")

    def test_collect_placeholder_prim_paths_deduplicates(self):
        stats = _Stats(
            placeholder_prim_paths=["/World/placeholder_area_publicspace_001"],
            public_space_regions=[
                _Area(prim_path="/World/placeholder_area_publicspace_001")
            ],
            placeholder_areas=[_Area(prim_path="/World/placeholder_area_plaza_001")],
        )
        paths = collect_placeholder_prim_paths(stats)
        self.assertEqual(
            paths,
            [
                "/World/placeholder_area_publicspace_001",
                "/World/placeholder_area_plaza_001",
            ],
        )


if __name__ == "__main__":
    unittest.main()
