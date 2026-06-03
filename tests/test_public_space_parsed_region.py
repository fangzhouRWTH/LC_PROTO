"""Public-space region parsing contracts (no Isaac)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = (
    REPO_ROOT / "algorithm_lab/experiments/area_placement_methods/module"
)
PROTO_SAMPLE = (
    REPO_ROOT
    / "algorithm_lab/experiments/area_placement_methods/proto/01_block_entrance_01.json"
)

sys.path.insert(0, str(MODULE_DIR))

from adapters.public_space_region import public_space_region_to_region_input  # noqa: E402
from generator import run_public_space_layout  # noqa: E402


class PublicSpaceParsedRegionTests(unittest.TestCase):
    def test_prim_name_pattern_publicspace(self):
        from engine.scene_naming import parse_prim_name

        info = parse_prim_name("placeholder_area_publicspace_001")
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.domain, "area")
        self.assertEqual(info.category, "publicspace")

        segment = parse_prim_name("placeholder_segment_edge_001")
        self.assertIsNotNone(segment)
        assert segment is not None
        self.assertEqual(segment.domain, "segment")
        self.assertEqual(segment.category, "edge")

    def test_parsed_region_dict_matches_proto_sample(self):
        with PROTO_SAMPLE.open(encoding="utf-8") as handle:
            proto = json.load(handle)

        parsed_region = {
            "region_id": "/World/Placeholders/placeholder_area_publicspace_001",
            "public_space_type": proto["public_space_type"],
            "ratio_dynamic_static": proto["ratio_dynamic_static"],
            "boundary_vertices": proto["public_space_geometry"]["coordinates"],
            "segments": [
                {
                    "segment_id": item["segment_id"],
                    "boundary_type": item["boundary_type"],
                    "coordinates": item["geometry"]["coordinates"],
                }
                for item in proto["public_space_segments"]
            ],
        }

        region_input = public_space_region_to_region_input(parsed_region)
        layout = run_public_space_layout(region_input, steps=[1, 2, 3, 4, 5])
        self.assertEqual(layout["public_space_type"], "block_entrance")
        self.assertGreater(len(layout.get("asset_list") or []), 0)


if __name__ == "__main__":
    unittest.main()
