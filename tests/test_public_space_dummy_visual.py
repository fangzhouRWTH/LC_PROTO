"""Debug geometry specs when asset library is not mapped."""

from __future__ import annotations

import unittest

from engine.public_space_dummy_visual import dummy_visual_spec


class PublicSpaceDummyVisualTests(unittest.TestCase):
    def test_deterministic_for_same_key(self):
        a = dummy_visual_spec("asset_0001", "guard_rail")
        b = dummy_visual_spec("asset_0001", "guard_rail")
        self.assertEqual(a, b)

    def test_varies_by_asset_name(self):
        a = dummy_visual_spec("asset_0001", "guard_rail")
        b = dummy_visual_spec("asset_0001", "flower_box")
        self.assertNotEqual(a["shape"], b["shape"])

    def test_semantic_hint_for_street_light(self):
        spec = dummy_visual_spec("asset_0010", "street_light")
        self.assertEqual(spec["shape"], "cylinder")

    def test_size_in_reasonable_range(self):
        spec = dummy_visual_spec("asset_0020", "bollard")
        self.assertGreaterEqual(spec["size"], 0.2)
        self.assertLessEqual(spec["size"], 1.2)
        self.assertEqual(len(spec["color"]), 3)


if __name__ == "__main__":
    unittest.main()
