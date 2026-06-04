"""Public-space quad edge inference (no Isaac)."""

from __future__ import annotations

import unittest

from engine.public_space_geometry import (
    extract_quad_corners,
    infer_boundary_segments_from_quad_vertices,
)
from engine.scene_naming import parse_prim_name


class PublicSpaceGeometryTests(unittest.TestCase):
    def test_parse_region_name_with_embedded_type(self):
        info = parse_prim_name("placeholder_area_publicspace_001_block_entrance")
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.index, "001")
        self.assertEqual(info.public_space_type, "block_entrance")
        self.assertEqual(info.category, "publicspace")

    def test_parse_region_name_longest_type_suffix(self):
        info = parse_prim_name("placeholder_area_publicspace_02_city_street_roofless")
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.public_space_type, "city_street_roofless")

    def test_infer_four_edges_from_axis_aligned_quad(self):
        vertices = [
            [0.0, 0.0, 0.0],
            [10.0, 0.0, 0.0],
            [10.0, 10.0, 0.0],
            [0.0, 10.0, 0.0],
        ]
        corners = extract_quad_corners(vertices)
        self.assertEqual(len(corners), 4)

        segments = infer_boundary_segments_from_quad_vertices(
            vertices,
            "city_street_roofless",
        )
        self.assertEqual(len(segments), 4)
        ids = {int(item["segment_id"]) for item in segments}
        self.assertEqual(ids, {1, 2, 3, 4})
        for item in segments:
            verts = item["vertices"]
            self.assertEqual(len(verts), 2)

    def test_build_inferred_segment_records(self):
        from engine.public_space_geometry import build_inferred_boundary_segment_records

        records = build_inferred_boundary_segment_records(
            "/World/placeholder_area_publicspace_001_blockentrance",
            [
                [0.0, 0.0, 0.0],
                [10.0, 0.0, 0.0],
                [10.0, 10.0, 0.0],
                [0.0, 10.0, 0.0],
            ],
            "block_entrance",
        )
        self.assertEqual(len(records), 4)
        self.assertEqual(records[0]["raw_name"], "placeholder_segment_edge_01")
        self.assertIn("boundary_type", records[0])


if __name__ == "__main__":
    unittest.main()
