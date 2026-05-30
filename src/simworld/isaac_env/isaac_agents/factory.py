from .backends import (
    DEFAULT_DYNAMIC_ROOT,
    KinematicDynamicAgentBackend,
    OrcaPedestrianDynamicAgentBackend,
    OrcaSumoDynamicAgentBackend,
    SumoVehicleDynamicAgentBackend,
)
from .manager import DynamicAgentManager

DEFAULT_DYNAMIC_AGENT_BACKEND = "kinematic"

DYNAMIC_AGENT_BACKEND_REGISTRY = {
    DEFAULT_DYNAMIC_AGENT_BACKEND: KinematicDynamicAgentBackend,
    "orca_pedestrian": OrcaPedestrianDynamicAgentBackend,
    "sumo_vehicle": SumoVehicleDynamicAgentBackend,
    "orca_sumo": OrcaSumoDynamicAgentBackend,
}


def available_dynamic_agent_backends() -> tuple[str, ...]:
    return tuple(sorted(DYNAMIC_AGENT_BACKEND_REGISTRY))


def create_dynamic_agent_manager(
    backend_name: str = DEFAULT_DYNAMIC_AGENT_BACKEND,
    root_prim_path: str = DEFAULT_DYNAMIC_ROOT,
) -> DynamicAgentManager:
    try:
        backend_cls = DYNAMIC_AGENT_BACKEND_REGISTRY[backend_name]
    except KeyError as exc:
        available = ", ".join(available_dynamic_agent_backends())
        raise ValueError(
            "Unsupported dynamic agent backend: "
            f"{backend_name}. Available dynamic agent backends: {available}"
        ) from exc

    return DynamicAgentManager(backend_cls(root_prim_path=root_prim_path))
