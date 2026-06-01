from dataclasses import dataclass
from typing import Any
import math
import re

from engine.dynamic import DynamicActorPlan, DynamicScenePlan

from .visuals import DynamicVisualConfig, proxy_visual_spec_for_actor, spawn_actor_visual

DEFAULT_DYNAMIC_ROOT = "/World/DynamicActors"


@dataclass
class _ActorRuntime:
    plan: DynamicActorPlan
    prim_path: str
    route: list[tuple[float, float, float]]
    segment_lengths: list[float]
    total_length: float
    visual_height: float
    route_mode: str = "loop"
    elapsed_s: float = 0.0
    translate_op: Any = None
    rotate_op: Any = None
    hidden: bool = False


class KinematicDynamicAgentBackend:
    def __init__(
        self,
        root_prim_path: str = DEFAULT_DYNAMIC_ROOT,
        visual_config: DynamicVisualConfig | None = None,
    ):
        self.root_prim_path = root_prim_path
        self.visual_config = visual_config or DynamicVisualConfig()
        self.context = None
        self.stage = None
        self.plan = DynamicScenePlan()
        self.actors: list[_ActorRuntime] = []

    @property
    def actor_count(self) -> int:
        return len(self.actors)

    def build_from_plan(self, plan: DynamicScenePlan | None):
        self.plan = plan or DynamicScenePlan()
        self.actors = []

        for actor_plan in self.plan.actors:
            runtime = self._build_actor_runtime(actor_plan)
            if runtime is not None:
                self.actors.append(runtime)

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
        print(f"[OK] Spawned {len(self.actors)} dynamic actor(s).")

    def reset(self):
        for actor in self.actors:
            actor.elapsed_s = 0.0
            self._set_actor_visible(actor, True)
            position, yaw = self._pose_at_distance(actor, 0.0)
            self._apply_actor_pose(actor, position, yaw)

    def step(self, dt: float):
        if dt <= 0.0:
            return

        for actor in self.actors:
            if actor.translate_op is None or actor.rotate_op is None:
                continue

            actor.elapsed_s += float(dt)
            travel_time_s = max(0.0, actor.elapsed_s - actor.plan.spawn_time_s)
            raw_distance = travel_time_s * actor.plan.speed_mps
            distance = self._distance_along_route(
                raw_distance,
                actor.total_length,
                actor.route_mode,
            )
            position, yaw = self._pose_at_distance(actor, distance)
            self._apply_actor_pose(actor, position, yaw)
            self._set_actor_visible(
                actor,
                not self._should_hide_actor_at_distance(actor, raw_distance),
            )

    def _get_context(self):
        if self.context is None:
            from ...isaac_adaptor import isaac_context as iscctx

            self.context = iscctx.get_isaac_context()
        return self.context

    def _build_actor_runtime(self, plan: DynamicActorPlan):
        route = [self._as_vec3(point) for point in plan.route]
        if len(route) < 2:
            print(f"[WARN] Skip dynamic actor with short route: {plan.actor_id}")
            return None

        segment_lengths = [
            self._distance(route[i], route[i + 1]) for i in range(len(route) - 1)
        ]
        total_length = sum(segment_lengths)
        if total_length < 1e-6:
            print(f"[WARN] Skip dynamic actor with zero-length route: {plan.actor_id}")
            return None

        visual = proxy_visual_spec_for_actor(plan.actor_type, plan.shape)
        return _ActorRuntime(
            plan=plan,
            prim_path=f"{self.root_prim_path}/{self._safe_prim_name(plan.actor_id)}",
            route=route,
            segment_lengths=segment_lengths,
            total_length=total_length,
            visual_height=visual.bounds_xyz[2],
            route_mode=self._route_mode_for_plan(plan),
        )

    def _spawn_actor(self, actor: _ActorRuntime):
        context = self._get_context()
        prim = self._ensure_xform_prim(actor.prim_path)
        xformable = context.pxr_usd_geom.Xformable(prim)
        xformable.ClearXformOpOrder()
        actor.translate_op = xformable.AddTranslateOp()
        actor.rotate_op = xformable.AddRotateXYZOp()

        spawn_actor_visual(
            self.stage,
            context,
            actor.prim_path,
            actor.plan.actor_type,
            actor.plan.shape,
            self.visual_config,
        )

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

    def _pose_at_distance(self, actor: _ActorRuntime, distance: float):
        remaining = distance
        for index, segment_length in enumerate(actor.segment_lengths):
            start = actor.route[index]
            end = actor.route[index + 1]

            if remaining <= segment_length or index == len(actor.segment_lengths) - 1:
                t = 0.0 if segment_length < 1e-8 else remaining / segment_length
                position = self._lerp(start, end, t)
                yaw = math.atan2(end[1] - start[1], end[0] - start[0])
                return position, yaw

            remaining -= segment_length

        start = actor.route[0]
        end = actor.route[1]
        return start, math.atan2(end[1] - start[1], end[0] - start[0])

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

    def _set_actor_visible(self, actor: _ActorRuntime, visible: bool):
        actor.hidden = not visible
        if self.stage is None:
            return

        prim = self.stage.GetPrimAtPath(actor.prim_path)
        if not prim.IsValid():
            return

        imageable = self._get_context().pxr_usd_geom.Imageable(prim)
        if visible:
            imageable.MakeVisible()
        else:
            imageable.MakeInvisible()

    def _route_mode_for_plan(self, plan: DynamicActorPlan) -> str:
        route_plan = plan.route_plan
        if route_plan is not None and route_plan.route_mode:
            return str(route_plan.route_mode)
        return "loop"

    def _distance_along_route(
        self,
        raw_distance: float,
        total_length: float,
        route_mode: str,
    ) -> float:
        if total_length < 1e-8:
            return 0.0

        mode = str(route_mode or "loop").lower()
        if self._is_stop_at_end_mode(mode):
            return min(raw_distance, total_length)
        if mode == "ping_pong":
            period = total_length * 2.0
            phase = raw_distance % period
            return phase if phase <= total_length else period - phase
        return raw_distance % total_length

    def _should_hide_actor_at_distance(
        self,
        actor: _ActorRuntime,
        raw_distance: float,
    ) -> bool:
        return (
            self._is_stop_at_end_mode(actor.route_mode)
            and raw_distance >= actor.total_length
        )

    def _is_stop_at_end_mode(self, route_mode: str) -> bool:
        return str(route_mode or "").lower() in {"once", "stop_at_end", "stop-at-end"}

    def _safe_prim_name(self, value: str) -> str:
        name = re.sub(r"[^0-9a-zA-Z_]", "_", value.strip())
        return name or "dynamic_actor"

    def _as_vec3(self, value) -> tuple[float, float, float]:
        if len(value) < 3:
            raise ValueError(f"Expected 3D route point, got {value}")
        return (float(value[0]), float(value[1]), float(value[2]))

    def _distance(
        self,
        a: tuple[float, float, float],
        b: tuple[float, float, float],
    ) -> float:
        return math.sqrt(
            (b[0] - a[0]) ** 2
            + (b[1] - a[1]) ** 2
            + (b[2] - a[2]) ** 2
        )

    def _lerp(
        self,
        a: tuple[float, float, float],
        b: tuple[float, float, float],
        t: float,
    ) -> tuple[float, float, float]:
        return (
            a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t,
        )
