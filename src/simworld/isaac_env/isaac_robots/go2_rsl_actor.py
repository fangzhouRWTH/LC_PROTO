"""RSL-RL actor loader for Unitree Go2 checkpoints."""

from __future__ import annotations

import pathlib

import torch
import torch.nn as nn

from .go2_config import ACTION_DIM, OBS_DIM

# Matches unitreego/agent.yaml policy.actor_hidden_dims / activation.
ACTOR_HIDDEN_DIMS = (512, 256, 128)


class Go2RslActor(nn.Module):
    def __init__(
        self,
        obs_dim: int = OBS_DIM,
        action_dim: int = ACTION_DIM,
        hidden_dims: tuple[int, ...] = ACTOR_HIDDEN_DIMS,
    ) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        layers.append(nn.Linear(obs_dim, hidden_dims[0]))
        layers.append(nn.ELU())
        for index in range(len(hidden_dims) - 1):
            layers.append(nn.Linear(hidden_dims[index], hidden_dims[index + 1]))
            layers.append(nn.ELU())
        layers.append(nn.Linear(hidden_dims[-1], action_dim))
        self.network = nn.Sequential(*layers)

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        return self.network(obs)


def _actor_state_dict(state_dict: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    network_state = {
        key[len("actor.network.") :]: value
        for key, value in state_dict.items()
        if key.startswith("actor.network.")
    }
    if network_state:
        return {f"network.{key}": value for key, value in network_state.items()}

    actor_state = {
        key[len("actor.") :]: value
        for key, value in state_dict.items()
        if key.startswith("actor.")
    }
    if actor_state:
        return {f"network.{key}": value for key, value in actor_state.items()}

    raise KeyError(
        "Go2 checkpoint does not contain actor weights "
        "(expected keys prefixed with 'actor.' or 'actor.network.')."
    )


def load_rsl_actor_checkpoint(path: str | pathlib.Path) -> Go2RslActor:
    checkpoint_path = pathlib.Path(path)
    checkpoint = torch.load(str(checkpoint_path), map_location="cpu", weights_only=False)
    if not isinstance(checkpoint, dict):
        raise TypeError(
            f"Unsupported Go2 checkpoint type: {type(checkpoint).__name__} ({checkpoint_path})"
        )

    state_dict = checkpoint.get("model_state_dict", checkpoint)
    if not isinstance(state_dict, dict):
        raise TypeError(
            "Go2 checkpoint must provide a model_state_dict mapping."
        )

    actor = Go2RslActor()
    actor.load_state_dict(_actor_state_dict(state_dict), strict=True)
    actor.eval()
    return actor
