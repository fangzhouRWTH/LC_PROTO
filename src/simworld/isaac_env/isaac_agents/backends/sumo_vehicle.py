from dataclasses import dataclass
from typing import Any
import math
import re

from engine.dynamic import DynamicActorPlan, DynamicScenePlan
from engine.sumo_vehicle import (
    TrafficConfig,
    VehicleAgentState,
    build_vehicle_states_from_plan,
    step_vehicle_agents,
)

from .kinematic import DEFAULT_DYNAMIC_ROOT


@dataclass
class _ActorRuntime:
    actor_id: str
    prim_path: str
    planner_state: VehicleAgentState
    visual_scale: tuple[float, float, float]
    translate_op: Any = None
    rotate_op: Any = None


class SumoVehicleDynamicAgentBackend:
    """Mock SUMO vehicle backend for runtime validation."""

    def __init__(
        self,
        root_prim_path: str = DEFAULT_DYNAMIC_ROOT,
        traffic_config: TrafficConfig | None = None,
    ):
        self.root_prim_path = root_prim_path
        self.traffic_config = traffic_config or TrafficConfig()
        self.context = None
        self.stage = None
        self.plan = DynamicScenePlan()
        self.actors: list[_ActorRuntime] = []
        self.sim_time_s = 0.0

    @property
    def actor_count(self) -> int:
        return len(self.actors)

    def build_from_plan(self, plan: DynamicScenePlan | None):
        self.plan = plan or DynamicScenePlan()
        self.actors = []
        self.sim_time_s = 0.0

        warnings: list[str] = []
        planner_states = build_vehicle_states_from_plan(self.plan, warnings)
        for warning in warnings:
            print(f"[WARN] {warning}")

        for actor_plan in self.plan.actors:
            if actor_plan.actor_type != "vehicle":
                print(
                    f"[WARN] sumo_vehicle backend skips non-vehicle actor: "
                    f"{actor_plan.actor_id}"
                )
                continue

            planner_state = next(
                (state for state in planner_states if state.actor_id == actor_plan.actor_id),
                None,
            )
            if planner_state is None:
                continue

            self.actors.append(
                _ActorRuntime(
                    actor_id=actor_plan.actor_id,
                    prim_path=f"{self.root_prim_path}/{self._safe_prim_name(actor_plan.actor_id)}",
                    planner_state=planner_state,
                    visual_scale=self._visual_scale(actor_plan),
                )
            )

    def spawn(self, stage=None):
        if not self.actors:
            return

        context = self._get_context()
        self.stage = stage or context.omni_usd.get_context().get_stage()
        if self.stage is None:
            raise RuntimeError("Cannot spawn dynamic agents without an open USD stage.")

        self._ensure_xform_prim(self.root_prim_path)
        for actor in self.actors:
            self._spawn_actor(actor)

        self.reset()
        print(f"[OK] Spawned {len(self.actors)} SUMO vehicle actor(s).")

    def reset(self):
        self.sim_time_s = 0.0
        warnings: list[str] = []
        planner_states = build_vehicle_states_from_plan(self.plan, warnings)
        state_by_id = {state.actor_id: state for state in planner_states}

        for actor in self.actors:
            refreshed = state_by_id.get(actor.actor_id)
            if refreshed is not None:
                actor.planner_state = refreshed
            position = actor.planner_state.position
            yaw = self._yaw_from_velocity(actor.planner_state.velocity)
            self._apply_actor_pose(actor, position, yaw)

    def step(self, dt: float):
        if dt <= 0.0:
            return

        self.sim_time_s += float(dt)
        step_vehicle_agents(
            [actor.planner_state for actor in self.actors],
            self.traffic_config,
            float(dt),
            self.sim_time_s,
        )

        for actor in self.actors:
            if actor.translate_op is None or actor.rotate_op is None:
                continue
            position = actor.planner_state.position
            yaw = self._yaw_from_velocity(actor.planner_state.velocity)
            self._apply_actor_pose(actor, position, yaw)

    def _get_context(self):
        if self.context is None:
            from ...isaac_adaptor import isaac_context as iscctx

            self.context = iscctx.get_isaac_context()
        return self.context

    def _visual_scale(self, plan: DynamicActorPlan) -> tuple[float, float, float]:
        length_m = float(plan.shape.length_m or 4.5)
        width_m = float(plan.shape.width_m or 1.8)
        height_m = float(plan.shape.height_m or 1.6)
        return (length_m, width_m, height_m)

    def _spawn_actor(self, actor: _ActorRuntime):
        context = self._get_context()
        prim = self._ensure_xform_prim(actor.prim_path)
        xformable = context.pxr_usd_geom.Xformable(prim)
        xformable.ClearXformOpOrder()
        actor.translate_op = xformable.AddTranslateOp()
        actor.rotate_op = xformable.AddRotateXYZOp()

        body_path = f"{actor.prim_path}/Body"
        body = context.pxr_usd_geom.Cube.Define(self.stage, body_path)
        body.CreateSizeAttr(1.0)
        body.CreateDisplayColorAttr().Set([context.pxr_gf.Vec3f(0.1, 0.35, 0.9)])

        scale = actor.visual_scale
        body_xform = context.pxr_usd_geom.Xformable(body.GetPrim())
        body_xform.ClearXformOpOrder()
        body_xform.AddTranslateOp().Set(
            context.pxr_gf.Vec3d(0.0, 0.0, scale[2] * 0.5)
        )
        body_xform.AddScaleOp().Set(context.pxr_gf.Vec3f(*scale))

    def _ensure_xform_prim(self, prim_path: str):
        context = self._get_context()
        prim = self.stage.GetPrimAtPath(prim_path)
        if prim.IsValid():
            prim.SetActive(True)
            return prim

        parent_path = "/".join(prim_path.rstrip("/").split("/")[:-1])
        if parent_path and parent_path != prim_path:
            self._ensure_xform_prim(parent_path or "/")

        return context.pxr_usd_geom.Xform.Define(self.stage, prim_path).GetPrim()

    def _apply_actor_pose(
        self,
        actor: _ActorRuntime,
        position: tuple[float, float, float],
        yaw: float,
    ):
        if actor.translate_op is None or actor.rotate_op is None:
            return

        Gf = self._get_context().pxr_gf
        actor.translate_op.Set(Gf.Vec3d(position[0], position[1], position[2]))
        actor.rotate_op.Set(Gf.Vec3f(0.0, 0.0, math.degrees(yaw)))

    def _yaw_from_velocity(self, velocity: tuple[float, float, float]) -> float:
        if math.hypot(velocity[0], velocity[1]) < 1e-6:
            return 0.0
        return math.atan2(velocity[1], velocity[0])

    def _safe_prim_name(self, value: str) -> str:
        name = re.sub(r"[^0-9a-zA-Z_]", "_", value.strip())
        return name or "dynamic_actor"
