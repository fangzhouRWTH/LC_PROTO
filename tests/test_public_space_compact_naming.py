"""Compact naming and segment synthesis tests (no Isaac)."""

from __future__ import annotations

import unittest

from engine.public_space_compact_naming import (
    format_public_space_region_name,
    parse_public_space_region_name,
)
from engine.public_space_geometry import (
    build_inferred_boundary_segment_records,
    infer_boundary_segments_from_quad_vertices,
)
from engine.public_space_segment_synthesis import choose_quad_boundary_types
from engine.scene_naming import parse_prim_name


class PublicSpaceCompactNamingTests(unittest.TestCase):
    def test_compact_type_and_boundary_hint(self):
        info = parse_public_space_region_name(
            "placeholder_area_publicspace_009_blockentrance_streetboundaryprimary"
        )
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.index, "009")
        self.assertEqual(info.public_space_type, "block_entrance")
        self.assertEqual(info.boundary_type_hint, "street_boundary_primary")

    def test_legacy_underscore_type_still_works(self):
        info = parse_public_space_region_name(
            "placeholder_area_publicspace_001_city_yard_roofless"
        )
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.public_space_type, "city_yard_roofless")

    def test_parse_prim_name_compact(self):
        info = parse_prim_name("placeholder_area_publicspace_006_citystreetroofless")
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.public_space_type, "city_street_roofless")

    def test_format_roundtrip(self):
        name = format_public_space_region_name(
            "003",
            "building_entrance",
            boundary_type_hint="building_entrance_main",
        )
        self.assertEqual(
            name,
            "placeholder_area_publicspace_003_buildingentrance_buildingentrancemain",
        )
        parsed = parse_public_space_region_name(name)
        assert parsed is not None
        self.assertEqual(parsed.public_space_type, "building_entrance")
        self.assertEqual(parsed.boundary_type_hint, "building_entrance_main")


class PublicSpaceSegmentSynthesisTests(unittest.TestCase):
    _QUAD = [
        [0.0, 0.0, 0.0],
        [10.0, 0.0, 0.0],
        [10.0, 10.0, 0.0],
        [0.0, 10.0, 0.0],
    ]

    def test_synthesis_uses_type_template(self):
        segments = infer_boundary_segments_from_quad_vertices(
            self._QUAD,
            "block_entrance",
            region_seed="/World/region_a",
        )
        types = [str(item["boundary_type"]) for item in segments]
        self.assertEqual(len(types), 4)
        self.assertIn("street_boundary_primary", types)

    def test_boundary_hint_placed_on_edge(self):
        segments = infer_boundary_segments_from_quad_vertices(
            self._QUAD,
            "building_entrance",
            boundary_type_hint="building_entrance_main",
        )
        types = [str(item["boundary_type"]) for item in segments]
        self.assertEqual(types.count("building_entrance_main"), 1)

    def test_build_records_use_persistent_segment_paths(self):
        records = build_inferred_boundary_segment_records(
            "/World/placeholder_area_publicspace_009_blockentrance",
            self._QUAD,
            "block_entrance",
        )
        self.assertEqual(len(records), 4)
        self.assertTrue(
            records[0]["prim_path"].endswith("/placeholder_segment_edge_01")
        )

    def test_deterministic_rotation(self):
        corners = [
            [0.0, 0.0, 0.0],
            [10.0, 0.0, 0.0],
            [10.0, 10.0, 0.0],
            [0.0, 10.0, 0.0],
        ]
        a = choose_quad_boundary_types(
            corners, "city_street_roofless", region_seed="/a"
        )
        b = choose_quad_boundary_types(
            corners, "city_street_roofless", region_seed="/a"
        )
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
