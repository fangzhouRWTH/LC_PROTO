from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from engine.dynamic import DynamicActorShape
from isaac_env.isaac_agents.backends.visuals import (
    AssetBounds,
    DynamicVisualConfig,
    actor_visual_source,
    pedestrian_asset_transform_for_bounds,
    proxy_visual_spec_for_actor,
    resolve_pedestrian_asset_path,
    resolve_vehicle_asset_path,
    vehicle_asset_transform_for_bounds,
    _asset_transform_with_z_offset,
)


class DynamicProxyVisualTest(unittest.TestCase):
    def test_pedestrian_proxy_visual_spec_is_stable(self):
        spec = proxy_visual_spec_for_actor(
            "pedestrian",
            DynamicActorShape(radius_m=0.35, height_m=1.7),
        )

        self.assertEqual(spec.actor_type, "pedestrian")
        self.assertEqual([part.name for part in spec.parts], ["Legs", "Torso", "Head"])
        self.assertEqual(spec.parts[-1].primitive_type, "sphere")
        self.assertAlmostEqual(spec.bounds_xyz[2], 1.7)

    def test_vehicle_proxy_visual_spec_is_stable(self):
        spec = proxy_visual_spec_for_actor(
            "vehicle",
            DynamicActorShape(length_m=4.5, width_m=1.8, height_m=1.6),
        )

        self.assertEqual(spec.actor_type, "vehicle")
        self.assertEqual(
            [part.name for part in spec.parts],
            ["Body", "Cabin", "FrontMarker", "RearMarker"],
        )
        self.assertEqual(spec.parts[0].primitive_type, "cube")
        self.assertEqual(spec.bounds_xyz, (4.5, 1.8, 1.6))

    def test_resolve_pedestrian_asset_path_selects_first_usd_in_directory(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "z_character.usd").write_text("#usda 1.0")
            (root / "a_character.usda").write_text("#usda 1.0")

            resolved = resolve_pedestrian_asset_path(str(root))

        self.assertEqual(resolved, str((root / "a_character.usda").resolve()))

    def test_resolve_pedestrian_asset_path_prefers_character_over_motion_usd(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            motion_dir = root / "Actor" / "character" / "Motions"
            motion_dir.mkdir(parents=True)
            (motion_dir / "Default.usd").write_text("#usda 1.0")
            actor_usd = root / "Actor" / "character" / "character.usd"
            actor_usd.write_text("#usda 1.0")

            resolved = resolve_pedestrian_asset_path(str(root))

        self.assertEqual(resolved, str(actor_usd.resolve()))

    def test_resolve_pedestrian_asset_path_rejects_missing_and_non_usd_paths(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            non_usd = root / "notes.txt"
            non_usd.write_text("not a usd")

            self.assertIsNone(resolve_pedestrian_asset_path(str(root / "missing.usd")))
            self.assertIsNone(resolve_pedestrian_asset_path(str(non_usd)))


    def test_pedestrian_asset_transform_fits_root_based_humanoid_to_actor_height(self):
        bounds = AssetBounds(
            min_xyz=(-87.96276092529297, -18.808446884155273, -12.328277587890625),
            max_xyz=(88.11437225341797, 21.850399017333984, 165.56198120117188),
        )
        shape = DynamicActorShape(radius_m=0.35, height_m=1.7)

        transform = pedestrian_asset_transform_for_bounds(bounds, shape)

        expected_scale = 1.7 / bounds.max_xyz[2]
        self.assertTrue(transform.fit_applied)
        self.assertAlmostEqual(transform.scale, expected_scale, places=6)
        self.assertEqual(transform.translate_xyz, (0.0, 0.0, 0.0))

    def test_pedestrian_asset_transform_scale_is_multiplier_after_height_fit(self):
        bounds = AssetBounds(min_xyz=(0.0, 0.0, 0.0), max_xyz=(10.0, 4.0, 2.0))
        shape = DynamicActorShape(radius_m=0.35, height_m=1.6)

        transform = pedestrian_asset_transform_for_bounds(
            bounds,
            shape,
            asset_scale=0.5,
        )

        self.assertTrue(transform.fit_applied)
        self.assertAlmostEqual(transform.scale, 0.4)
        self.assertEqual(transform.translate_xyz, (0.0, 0.0, 0.0))

    def test_pedestrian_asset_transform_aligns_centered_assets_to_ground(self):
        bounds = AssetBounds(min_xyz=(-0.35, -0.35, -0.85), max_xyz=(0.35, 0.35, 0.85))

        transform = pedestrian_asset_transform_for_bounds(
            bounds,
            DynamicActorShape(radius_m=0.35, height_m=1.7),
        )

        self.assertTrue(transform.fit_applied)
        self.assertAlmostEqual(transform.scale, 1.0)
        self.assertEqual(transform.translate_xyz, (0.0, 0.0, 0.85))

    def test_pedestrian_asset_transform_can_disable_height_fit(self):
        bounds = AssetBounds(min_xyz=(0.0, 0.0, -5.0), max_xyz=(10.0, 4.0, 200.0))

        transform = pedestrian_asset_transform_for_bounds(
            bounds,
            DynamicActorShape(radius_m=0.35, height_m=1.7),
            asset_scale=2.0,
            asset_fit="none",
        )

        self.assertFalse(transform.fit_applied)
        self.assertEqual(transform.scale, 2.0)
        self.assertEqual(transform.translate_xyz, (0.0, 0.0, 0.0))


    def test_resolve_vehicle_asset_path_prefers_street_car_full_asset(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            material_dir = root / "materials"
            material_dir.mkdir()
            (material_dir / "backLight.usda").write_text("#usda 1.0")
            wheel_dir = root / "assets" / "wheels" / "wheelNormal" / "asset"
            wheel_dir.mkdir(parents=True)
            (wheel_dir / "wheelNormalAsset.usda").write_text("#usda 1.0")
            sedan_dir = root / "assets" / "vehicles" / "sedan" / "asset"
            sedan_dir.mkdir(parents=True)
            sedan_asset = sedan_dir / "sedanFullAsset.usda"
            sedan_asset.write_text("#usda 1.0")

            resolved = resolve_vehicle_asset_path(str(root))

        self.assertEqual(resolved, str(sedan_asset.resolve()))

    def test_resolve_vehicle_asset_path_accepts_explicit_usd_file(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vehicle_asset = root / "street_car.usda"
            vehicle_asset.write_text("#usda 1.0")

            resolved = resolve_vehicle_asset_path(str(vehicle_asset))

        self.assertEqual(resolved, str(vehicle_asset.resolve()))

    def test_vehicle_asset_transform_fits_within_actor_shape(self):
        bounds = AssetBounds(min_xyz=(-5.0, -2.0, -0.5), max_xyz=(5.0, 2.0, 2.5))
        shape = DynamicActorShape(length_m=4.5, width_m=1.8, height_m=1.6)

        transform = vehicle_asset_transform_for_bounds(bounds, shape)

        self.assertTrue(transform.fit_applied)
        self.assertAlmostEqual(transform.scale, 0.45)
        self.assertAlmostEqual(transform.translate_xyz[2], 0.225)


    def test_asset_transform_with_z_offset_applies_final_meter_offset(self):
        transform = vehicle_asset_transform_for_bounds(
            AssetBounds(min_xyz=(-5.0, -2.0, -0.5), max_xyz=(5.0, 2.0, 2.5)),
            DynamicActorShape(length_m=4.5, width_m=1.8, height_m=1.6),
        )

        adjusted = _asset_transform_with_z_offset(transform, -0.25)

        self.assertAlmostEqual(adjusted.scale, transform.scale)
        self.assertAlmostEqual(adjusted.translate_xyz[2], transform.translate_xyz[2] - 0.25)
        self.assertTrue(adjusted.fit_applied)

    def test_vehicle_asset_transform_can_disable_shape_fit(self):
        bounds = AssetBounds(min_xyz=(-5.0, -2.0, -0.5), max_xyz=(5.0, 2.0, 2.5))

        transform = vehicle_asset_transform_for_bounds(
            bounds,
            DynamicActorShape(length_m=4.5, width_m=1.8, height_m=1.6),
            asset_scale=2.0,
            asset_fit="none",
        )

        self.assertFalse(transform.fit_applied)
        self.assertEqual(transform.scale, 2.0)
        self.assertEqual(transform.translate_xyz, (0.0, 0.0, 0.0))

    def test_actor_visual_source_falls_back_without_resolved_asset(self):
        config = DynamicVisualConfig(pedestrian_visual="asset")

        self.assertEqual(actor_visual_source("pedestrian", config, None), "proxy")
        self.assertEqual(
            actor_visual_source("pedestrian", config, "/tmp/person.usd"),
            "asset",
        )
        self.assertEqual(
            actor_visual_source("vehicle", config, "/tmp/person.usd"),
            "proxy",
        )

        vehicle_config = DynamicVisualConfig(vehicle_visual="asset")
        self.assertEqual(
            actor_visual_source("vehicle", vehicle_config, "/tmp/car.usd"),
            "asset",
        )


if __name__ == "__main__":
    unittest.main()
