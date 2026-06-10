"""Unitree Go2 rough-terrain policy controller for Isaac Sim."""

from __future__ import annotations

import io
import pathlib
from typing import Optional

import numpy as np
import omni
import torch
from isaacsim.core.utils.rotations import quat_to_rot_matrix
from isaacsim.core.utils.types import ArticulationAction
from isaacsim.robot.policy.examples.controllers import PolicyController
from isaacsim.robot.policy.examples.controllers.config_loader import (
    get_physics_properties,
    parse_env_config,
)
from .go2_config import (
    ACTION_DIM,
    ACTION_SCALE,
    ANG_VEL_OBS_SCALE,
    DEFAULT_ENV_CONFIG,
    DEFAULT_POLICY_CHECKPOINT,
    JOINT_VEL_OBS_SCALE,
    OBS_DIM,
    go2_articulation_root_path,
    is_torchscript_policy,
    omniverse_readable_path,
    resolve_go2_usd_uri,
    unitreego_asset_dir,
)
from .go2_rsl_actor import load_rsl_actor_checkpoint


def _optional_isaac_assets_root() -> str | None:
    try:
        from isaacsim.storage.native import get_assets_root_path

        return get_assets_root_path()
    except RuntimeError as exc:
        print(f"[WARN] Isaac assets root unavailable, using local Go2 USD lookup: {exc}")
        return None


class Go2RoughTerrainPolicy(PolicyController):
    """Unitree Go2 locomotion policy exported from Isaac Lab / RSL-RL."""

    def __init__(
        self,
        prim_path: str,
        root_path: Optional[str] = None,
        name: str = "go2",
        usd_path: Optional[str] = None,
        position: Optional[np.ndarray] = None,
        orientation: Optional[np.ndarray] = None,
        policy_dir: str | pathlib.Path | None = None,
        policy_checkpoint: str = DEFAULT_POLICY_CHECKPOINT,
        env_config: str = DEFAULT_ENV_CONFIG,
    ) -> None:
        if usd_path is None:
            usd_path = resolve_go2_usd_uri(_optional_isaac_assets_root())
        if root_path is None:
            root_path = go2_articulation_root_path(prim_path)

        print(f"[INFO] Go2 USD reference: {usd_path}")
        print(f"[INFO] Go2 articulation root: {root_path}")

        super().__init__(name, prim_path, root_path, usd_path, position, orientation)

        asset_dir = pathlib.Path(policy_dir) if policy_dir is not None else unitreego_asset_dir()
        policy_path = asset_dir / policy_checkpoint
        env_path = asset_dir / env_config
        self._policy_mode = "rsl"
        self.load_go2_policy(str(policy_path), str(env_path))

        self._action_scale = ACTION_SCALE
        self._previous_action = np.zeros(ACTION_DIM, dtype=np.float32)
        self._policy_counter = 0
        if not hasattr(self, "action"):
            self.action = np.zeros(ACTION_DIM, dtype=np.float32)

    def load_go2_policy(self, policy_file_path: str, policy_env_path: str) -> None:
        env_uri = omniverse_readable_path(policy_env_path)
        self.policy_env_params = parse_env_config(env_uri)
        self._decimation, self._dt, self.render_interval = get_physics_properties(
            self.policy_env_params
        )

        policy_path = pathlib.Path(policy_file_path)
        if is_torchscript_policy(policy_path):
            file_content = omni.client.read_file(
                omniverse_readable_path(policy_path)
            )[2]
            file = io.BytesIO(memoryview(file_content).tobytes())
            self.policy = torch.jit.load(file)
            self._policy_mode = "jit"
            print(f"[INFO] Loaded Go2 TorchScript policy: {policy_path}")
            return

        self.policy = load_rsl_actor_checkpoint(policy_path)
        self._policy_mode = "rsl"
        print(f"[INFO] Loaded Go2 RSL-RL actor checkpoint: {policy_path}")

    def initialize(self, physics_sim_view=None) -> None:
        return super().initialize(
            physics_sim_view=physics_sim_view,
            set_articulation_props=False,
        )

    def _compute_action(self, obs: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            obs_tensor = torch.from_numpy(obs).view(1, -1).float()
            action = self.policy(obs_tensor)
            return action.detach().view(-1).numpy()

    def _compute_observation(self, command: np.ndarray) -> np.ndarray:
        ang_vel_I = self.robot.get_angular_velocity()
        _, q_IB = self.robot.get_world_pose()

        R_IB = quat_to_rot_matrix(q_IB)
        R_BI = R_IB.transpose()
        ang_vel_b = np.matmul(R_BI, ang_vel_I)
        gravity_b = np.matmul(R_BI, np.array([0.0, 0.0, -1.0], dtype=np.float32))

        current_joint_pos = self.robot.get_joint_positions()
        current_joint_vel = self.robot.get_joint_velocities()
        default_pos = np.asarray(self.default_pos, dtype=np.float32)

        obs = np.zeros(OBS_DIM, dtype=np.float32)
        obs[0:3] = ang_vel_b * ANG_VEL_OBS_SCALE
        obs[3:6] = gravity_b
        obs[6:9] = command
        obs[9:21] = current_joint_pos - default_pos
        obs[21:33] = current_joint_vel * JOINT_VEL_OBS_SCALE
        obs[33:45] = self._previous_action
        return obs

    def forward(self, dt: float, command: np.ndarray) -> None:
        del dt  # decimation is handled via policy_env_params.

        if self._policy_counter % self._decimation == 0:
            obs = self._compute_observation(command)
            self.action = self._compute_action(obs)
            self._previous_action = self.action.copy()

        default_pos = np.asarray(self.default_pos, dtype=np.float32)
        target_pos = default_pos + (self.action * self._action_scale)
        self.robot.apply_action(ArticulationAction(joint_positions=target_pos))
        self._policy_counter += 1
