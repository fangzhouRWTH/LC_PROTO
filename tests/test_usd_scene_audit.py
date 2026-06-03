"""usd_scene_audit helpers (no pxr required)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "simworld"))

from engine.scene_naming import parse_prim_name
from engine.usd_scene_audit import (  # noqa: E402
    AUDIT_RULE_SPECS,
    Pipeline,
    PrimAuditRecord,
    _assign_layout_role,
    _classify_attribute,
    _matching_rules,
    _rule_matches,
    render_audit_markdown,
    AuditReport,
    FieldRelevance,
    PUBLIC_SPACE_REGION_ROLE,
)


class UsdSceneAuditLogicTests(unittest.TestCase):
    def test_public_space_region_name_matches_area_placement_rule(self):
        info = parse_prim_name("placeholder_area_publicspace_001")
        self.assertIsNotNone(info)
        matched = _matching_rules(info)
        self.assertTrue(any(spec.pipeline == Pipeline.AREA_PLACEMENT for spec in matched))
        self.assertEqual(_assign_layout_role(info, matched), PUBLIC_SPACE_REGION_ROLE)

    def test_segment_edge_matches_rule(self):
        info = parse_prim_name("placeholder_segment_edge_001")
        matched = _matching_rules(info)
        self.assertTrue(matched)
        self.assertEqual(_assign_layout_role(info, matched), "public_space_segment")

    def test_static_ground_is_unrelated_pipeline(self):
        info = parse_prim_name("static_ground_base_01")
        matched = _matching_rules(info)
        self.assertTrue(matched)
        self.assertEqual(matched[0].pipeline, Pipeline.STATIC_SCENE)

    def test_classify_simworld_attribute_required_on_region(self):
        rel = _classify_attribute("custom:simworld:public_space_type", PUBLIC_SPACE_REGION_ROLE)
        self.assertEqual(rel, FieldRelevance.REQUIRED_LAYOUT)

    def test_classify_material_unrelated(self):
        rel = _classify_attribute("inputs:diffuseColor", PUBLIC_SPACE_REGION_ROLE)
        self.assertEqual(rel, FieldRelevance.UNRELATED)

    def test_render_markdown_contains_pipeline_table(self):
        record = PrimAuditRecord(
            path="/root/placeholder_area_publicspace_001",
            name="placeholder_area_publicspace_001",
            type_name="Mesh",
            depth=1,
            parent_path="/root",
            name_info=parse_prim_name("placeholder_area_publicspace_001"),
            pipeline=Pipeline.AREA_PLACEMENT,
            layout_role=PUBLIC_SPACE_REGION_ROLE,
            issues=["test issue"],
        )
        report = AuditReport(
            usd_path="/tmp/test.usd",
            generated_at_utc="2026-06-03T00:00:00+00:00",
            default_prim="/root",
            up_axis="Z",
            meters_per_unit=1.0,
            prim_records=[record],
            summary={
                "prim_count": 1,
                "public_space_regions": 1,
                "public_space_segments": 0,
                "layout_ready_regions": 0,
                "total_issues": 1,
                "by_pipeline": {Pipeline.AREA_PLACEMENT.value: 1},
            },
        )
        md = render_audit_markdown(report)
        self.assertIn("area_placement_methods", md)
        self.assertIn("test issue", md)
        self.assertIn("placeholder_area_publicspace_001", md)

    def test_all_audit_rules_have_unique_names(self):
        names = [spec.name for spec in AUDIT_RULE_SPECS]
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
