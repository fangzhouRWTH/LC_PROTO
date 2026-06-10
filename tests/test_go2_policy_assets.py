import unittest

from isaac_env.isaac_robots.go2_config import (
    ACTION_DIM,
    DEFAULT_ENV_CONFIG,
    DEFAULT_POLICY_CHECKPOINT,
    OBS_DIM,
    Go2UsdNotFoundError,
    go2_articulation_root_path,
    is_torchscript_policy,
    local_go2_usd_candidates,
    resolve_local_go2_usd_path,
    unitreego_asset_dir,
)


class Go2PolicyAssetsTest(unittest.TestCase):
    def test_unitreego_assets_exist(self):
        asset_dir = unitreego_asset_dir()
        self.assertTrue(asset_dir.is_dir(), f"Missing unitreego dir: {asset_dir}")
        self.assertTrue((asset_dir / DEFAULT_ENV_CONFIG).is_file())
        self.assertTrue((asset_dir / DEFAULT_POLICY_CHECKPOINT).is_file())

    def test_policy_dimensions_match_blind_rough_config(self):
        # base_ang_vel(3) + projected_gravity(3) + velocity_commands(3)
        # + joint_pos(12) + joint_vel(12) + last_action(12)
        self.assertEqual(OBS_DIM, 45)
        self.assertEqual(ACTION_DIM, 12)

    def test_default_checkpoint_is_rsl_rl_not_torchscript(self):
        asset_dir = unitreego_asset_dir()
        checkpoint = asset_dir / DEFAULT_POLICY_CHECKPOINT
        self.assertTrue(checkpoint.is_file())
        self.assertFalse(
            is_torchscript_policy(checkpoint),
            "model_5300.pt must be loaded as RSL-RL state dict, not torch.jit.load",
        )

    def test_go2_articulation_root_path(self):
        self.assertEqual(
            go2_articulation_root_path("/World/Go2_demo"),
            "/World/Go2_demo/go2_description",
        )

    def test_local_go2_usd_resolution_prefers_existing_asset(self):
        candidates = local_go2_usd_candidates()
        self.assertGreater(len(candidates), 0)
        try:
            resolved = resolve_local_go2_usd_path()
        except Go2UsdNotFoundError:
            self.skipTest("Go2 USD not installed in this environment")
        self.assertTrue(resolved.is_file())
        self.assertEqual(resolved.name, "go2.usd")


if __name__ == "__main__":
    unittest.main()
