"""USD metadata helpers for public-space parsing (no Isaac)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "simworld"))

from engine.public_space_metadata import (  # noqa: E402
    format_public_space_type_misexport_hint,
    is_known_public_space_type,
    looks_like_unset_simworld_property,
)


class PublicSpaceUsdMetadataTests(unittest.TestCase):
    def test_known_public_space_type(self):
        self.assertTrue(is_known_public_space_type("block_entrance"))
        self.assertFalse(is_known_public_space_type("simworld:public_space_type"))

    def test_property_key_like_values(self):
        self.assertTrue(
            looks_like_unset_simworld_property("simworld:public_space_type")
        )
        self.assertFalse(looks_like_unset_simworld_property("block_entrance"))

    def test_misexport_hint_mentions_block_entrance(self):
        hint = format_public_space_type_misexport_hint(
            "/root/placeholder_area_publicspace_001",
            "simworld:public_space_type",
        )
        self.assertIn("block_entrance", hint)


if __name__ == "__main__":
    unittest.main()
