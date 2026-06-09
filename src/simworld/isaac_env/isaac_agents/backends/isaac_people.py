from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import math
import os
import re
import tempfile

from engine.dynamic import DynamicActorPlan, DynamicScenePlan

from .isaac_people_route_animation import (
    anim_graph_targets_for_skelroot,
    applied_schema_names,
    bind_route_walk_clip,
    resolve_isaac_people_yaw_offset_degrees,
    set_orient_op_yaw,
    setup_route_anim_graph,
)
from .kinematic import DEFAULT_DYNAMIC_ROOT
from .visuals import DynamicVisualConfig, resolve_pedestrian_asset_path

PEOPLE_CHARACTER_ROOT = "/World/Characters"
DEFAULT_LOCAL_ISAAC_ASSET_ROOT = Path.home() / "isaacsim_assets/Assets/Isaac/5.1"
ISAAC_ASSET_ROOT_SETTING = "/persistent/isaac/asset_root/default"
ISAAC_ASSET_ROOT_TIMEOUT_SETTING = "/persistent/isaac/asset_root/timeout"
ISAAC_REPLICATOR_USE_ASSET_ROOT_SETTING = (
    "/exts/isaacsim.replicator.agent/asset_settings/use_isaac_sim_asset_root"
)
ISAAC_REPLICATOR_DEFAULT_BIPED_SETTING = (
    "/exts/isaacsim.replicator.agent/asset_settings/default_biped_assets_path"
)
ISAAC_REPLICATOR_DEFAULT_CHARACTER_SETTING = (
    "/exts/isaacsim.replicator.agent/asset_settings/default_character_asset_path"
)
PEOPLE_COMMAND_DIR = Path(tempfile.gettempdir()) / "lc_proto_dynamic_people"
PEOPLE_COMMAND_FILE = PEOPLE_COMMAND_DIR / "dynamic_people_commands.txt"
ISAAC_PEOPLE_NAVMESH_ENV = "DYNAMIC_ISAAC_PEOPLE_NAVMESH"
ISAAC_PEOPLE_CONTROL_ENV = "DYNAMIC_ISAAC_PEOPLE_CONTROL"
ISAAC_PEOPLE_DEBUG_ENV = "DYNAMIC_ISAAC_PEOPLE_DEBUG"
DEFAULT_ISAAC_PEOPLE_NAVMESH_ENABLED = False
DEFAULT_ISAAC_PEOPLE_CONTROL_MODE = "route"
DEFAULT_ROUTE_ANIM_HANDLE_WARMUP_FRAMES = 180
ROUTE_END_HIDE_EPSILON_M = 0.05
PEOPLE_EXTENSIONS = (
    "omni.kit.scripting",
    "omni.anim.timeline",
    "omni.anim.graph.bundle",
    "omni.anim.graph.core",
    "omni.anim.retarget.bundle",
    "omni.anim.retarget.core",
    "omni.anim.navigation.bundle",
    "omni.anim.navigation.core",
    "omni.anim.people",
    "isaacsim.replicator.agent.core",
    "omni.kit.mesh.raycast",
)


@dataclass
class IsaacPeopleActorRuntime:
    plan: DynamicActorPlan
    character_name: str
    route: list[tuple[float, float, float]]
    segment_lengths: list[float]
    total_length: float
    route_mode: str
    command_lines: list[str] = field(default_factory=list)
    character_root_path: str = ""
    skelroot_path: str = ""
    asset_path: str = ""
    anim_graph_path: str = ""
    behavior_script_path: str = ""
    skeleton_path: str = ""
    walk_clip_path: str = ""
    walk_animation_prim_path: str = ""
    walk_clip_bound: bool = False
    loaded: bool = False
    elapsed_s: float = 0.0
    translate_op: Any = None
    orient_op: Any = None
    character_handle: Any = None
    handle_attempts: int = 0
    animation_warning_printed: bool = False
    animation_update_printed: bool = False
    hidden_at_route_end_printed: bool = False
    debug_frame_count: int = 0
    debug_start_position: tuple[float, float, float] | None = None
    hidden: bool = False


def preload_isaac_people_runtime(
    context: Any,
    control_mode: str | None = None,
    debug_enabled: bool | None = None,
) -> bool:
    """Enable Isaac People runtime before a stage is opened.

    The People AnimGraph registry is sensitive to extension/stage init order.
    Preloading mirrors the standalone smoke test: enable People/AnimGraph
    extensions first, then let LC_PROTO open and populate the scene.
    """
    backend = IsaacPeopleDynamicAgentBackend(
        control_mode=control_mode,
        debug_enabled=debug_enabled,
    )
    backend.context = context
    try:
        backend._configure_people_asset_root()
        backend._enable_people_extensions(context)
        backend._configure_people_settings()
        return True
    except Exception as exc:  # pragma: no cover - Isaac runtime path
        print(f"[WARN] Isaac People runtime preload failed: {exc}")
        return False


class IsaacPeopleDynamicAgentBackend:
    """Isaac People animated pedestrian backend.

    `route` control mode is the current LC_PROTO demo path: LC_PROTO owns
    root motion along authored routes while Isaac People provides the Walk
    animation graph. `command` mode keeps the official omni.anim.people GoTo
    command-file path for future navmesh-backed scenes.
    """

    def __init__(
        self,
        root_prim_path: str = DEFAULT_DYNAMIC_ROOT,
        visual_config: DynamicVisualConfig | None = None,
        command_file_path: str | Path | None = None,
        navmesh_enabled: bool | None = None,
        control_mode: str | None = None,
        debug_enabled: bool | None = None,
    ):
        self.root_prim_path = root_prim_path
        self.visual_config = visual_config or DynamicVisualConfig()
        self.command_file_path = Path(command_file_path or PEOPLE_COMMAND_FILE)
        self.control_mode = resolve_isaac_people_control_mode(control_mode)
        self.navmesh_enabled = (
            resolve_isaac_people_navmesh_enabled()
            if navmesh_enabled is None
            else bool(navmesh_enabled)
        )
        self.debug_enabled = (
            resolve_bool_env(ISAAC_PEOPLE_DEBUG_ENV, False)
            if debug_enabled is None
            else bool(debug_enabled)
        )
        self.route_yaw_offset_degrees = resolve_isaac_people_yaw_offset_degrees()
        self.context = None
        self.stage = None
        self.plan = DynamicScenePlan()
        self.actors: list[IsaacPeopleActorRuntime] = []
        self.available = False
        self.timeline_started = False
        self.timeline_time_s = 0.0

    @property
    def actor_count(self) -> int:
        return len(self.actors)

    def build_from_plan(self, plan: DynamicScenePlan | None):
        self.plan = plan or DynamicScenePlan()
        self.actors = []

        pedestrian_actors = [
            actor for actor in self.plan.actors if actor.actor_type == "pedestrian"
        ]
        for index, actor_plan in enumerate(pedestrian_actors):
            route = [_as_vec3(point) for point in actor_plan.route]
            if len(route) < 2:
                print(
                    "[WARN] isaac_people backend skips pedestrian with short route: "
                    f"{actor_plan.actor_id}"
                )
                continue

            segment_lengths = [_distance(route[i], route[i + 1]) for i in range(len(route) - 1)]
            total_length = sum(segment_lengths)
            if total_length < 1e-6:
                print(
                    "[WARN] isaac_people backend skips pedestrian with zero-length route: "
                    f"{actor_plan.actor_id}"
                )
                continue

            character_name = character_name_for_index(index)
            self.actors.append(
                IsaacPeopleActorRuntime(
                    plan=actor_plan,
                    character_name=character_name,
                    route=route,
                    segment_lengths=segment_lengths,
                    total_length=total_length,
                    route_mode=_route_mode_for_plan(actor_plan),
                    command_lines=people_command_lines_for_route(character_name, route),
                    character_root_path=f"{PEOPLE_CHARACTER_ROOT}/{character_name}",
                )
            )

        skipped = len(self.plan.actors) - len(pedestrian_actors)
        if skipped:
            print(f"[INFO] isaac_people backend ignores {skipped} non-pedestrian actor(s).")

    def spawn(self, stage=None):
        if not self.actors:
            return

        context = self._get_context()
        self.stage = stage or context.omni_usd.get_context().get_stage()
        if self.stage is None:
            raise RuntimeError("Cannot spawn Isaac People without an open USD stage.")

        try:
            self._configure_people_asset_root()
            self._enable_people_extensions(context)
            self._configure_people_settings()
            self._write_command_file()
            self._spawn_people_characters()
            self.available = True
        except Exception as exc:  # pragma: no cover - Isaac runtime path
            self.available = False
            print(
                "[ERROR] Isaac People animated pedestrians unavailable: "
                f"{exc}. Pedestrians will not be spawned by this backend."
            )
            return

        loaded_count = sum(1 for actor in self.actors if actor.loaded)
        print(f"[OK] Spawned {loaded_count} Isaac People animated pedestrian actor(s).")
        print(f"[INFO] Isaac People command file: {self.command_file_path}")

    def reset(self):
        if not self.actors:
            return
        try:
            self._write_command_file()
            self.timeline_time_s = 0.0
            for actor in self.actors:
                actor.elapsed_s = 0.0
                actor.debug_frame_count = 0
                actor.debug_start_position = None
                actor.animation_update_printed = False
                self._set_actor_visible(actor, True)
                position, yaw = self._pose_at_distance(actor, 0.0)
                self._apply_actor_pose(actor, position, yaw)
                if not actor.walk_clip_bound:
                    self._set_walk_animation(actor, moving=False, position=position, distance=0.0)
        except Exception as exc:  # pragma: no cover - Isaac runtime path
            print(f"[WARN] Isaac People reset failed: {exc}")

    def step(self, dt: float):
        if self.control_mode == "command" or dt <= 0.0:
            return

        self._advance_people_timeline_frame(float(dt))

        for actor in self.actors:
            if not actor.loaded:
                continue
            self._ensure_actor_transform_ops(actor)
            if actor.translate_op is None or actor.orient_op is None:
                continue

            actor.elapsed_s += float(dt)
            travel_time_s = max(0.0, actor.elapsed_s - actor.plan.spawn_time_s)
            raw_distance = travel_time_s * max(0.0, float(actor.plan.speed_mps))
            distance = self._distance_along_route(raw_distance, actor.total_length, actor.route_mode)
            hidden = self._should_hide_actor_at_distance(actor, raw_distance)
            if hidden:
                self._set_actor_visible(actor, False)
                continue

            position, yaw = self._pose_at_distance(actor, distance)
            moving = _route_walk_animation_should_move(
                actor,
                raw_distance=raw_distance,
                travel_time_s=travel_time_s,
                hidden=False,
            )

            self._apply_actor_pose(actor, position, yaw)
            self._set_actor_visible(actor, True)
            self._debug_route_progress(actor, position)
            if not actor.walk_clip_bound:
                self._set_walk_animation(actor, moving=moving, position=position, distance=distance)

    def _get_context(self):
        if self.context is None:
            from ...isaac_adaptor import isaac_context as iscctx

            self.context = iscctx.get_isaac_context()
        return self.context

    def _ensure_people_timeline_playing(self, *, start_playback: bool = False):
        if self.timeline_started and not start_playback:
            return
        try:
            import omni.timeline

            timeline = omni.timeline.get_timeline_interface()
            try:
                import carb

                carb.settings.get_settings().set("/app/player/playSimulations", True)
            except Exception:
                pass
            if hasattr(timeline, "set_start_time"):
                timeline.set_start_time(0.0)
            if hasattr(timeline, "set_end_time"):
                timeline.set_end_time(3600.0)
            if hasattr(timeline, "set_auto_update"):
                timeline.set_auto_update(True)
            if self.timeline_time_s <= 0.0 and hasattr(timeline, "set_current_time"):
                timeline.set_current_time(0.0)
            if start_playback and not timeline.is_playing():
                timeline.play()
            if self.debug_enabled:
                current_time = _safe_call(timeline, "get_current_time")
                auto_update = _safe_call(timeline, "get_auto_update")
                print(
                    "[DEBUG] Isaac People timeline: "
                    f"playing={timeline.is_playing()} auto_update={auto_update} current_time={current_time}"
                )
            self.timeline_started = True
        except Exception as exc:  # pragma: no cover - Isaac runtime path
            if self.debug_enabled:
                print(f"[WARN] Isaac People timeline play failed: {exc}")

    def _advance_people_timeline_frame(self, dt: float):
        try:
            import omni.timeline

            timeline = omni.timeline.get_timeline_interface()
            if not timeline.is_playing():
                return
            self.timeline_time_s += max(0.0, float(dt))
            if hasattr(timeline, "set_current_time"):
                timeline.set_current_time(self.timeline_time_s)
            elif hasattr(timeline, "forward_one_frame"):
                timeline.forward_one_frame()
        except Exception as exc:  # pragma: no cover - Isaac runtime path
            if self.debug_enabled:
                print(f"[WARN] Isaac People timeline frame advance failed: {exc}")

    def _enable_people_extensions(self, context):
        import omni.kit.app

        ext_manager = omni.kit.app.get_app().get_extension_manager()
        for extension_name in PEOPLE_EXTENSIONS:
            ext_manager.set_extension_enabled_immediate(extension_name, True)
            context.update()
            if self.debug_enabled:
                print(f"[DEBUG] Isaac People extension enabled: {extension_name}")
        context.update()

    def _configure_people_asset_root(self) -> str | None:
        asset_root = resolve_isaac_people_asset_root()
        if not asset_root:
            return None

        import carb

        settings = carb.settings.get_settings()
        settings.set(ISAAC_ASSET_ROOT_SETTING, asset_root)
        settings.set(ISAAC_ASSET_ROOT_TIMEOUT_SETTING, 1.0)
        settings.set(ISAAC_REPLICATOR_USE_ASSET_ROOT_SETTING, True)
        settings.set(
            ISAAC_REPLICATOR_DEFAULT_BIPED_SETTING,
            _join_asset_root(asset_root, "Isaac/People/Characters/Biped_Setup.usd"),
        )
        settings.set(
            ISAAC_REPLICATOR_DEFAULT_CHARACTER_SETTING,
            _join_asset_root(asset_root, "Isaac/People/Characters/"),
        )
        print(f"[INFO] Isaac People asset root: {asset_root}")
        return asset_root

    def _configure_people_settings(self):
        import carb
        from omni.anim.people.settings import PeopleSettings
        from isaacsim.replicator.agent.core.settings import AssetPaths, PrimPaths

        settings = carb.settings.get_settings()
        asset_root = resolve_isaac_people_asset_root()
        if asset_root:
            AssetPaths.cached_isaac_sim_asset_root_path = asset_root
            settings.set(ISAAC_ASSET_ROOT_SETTING, asset_root)
            settings.set(ISAAC_REPLICATOR_USE_ASSET_ROOT_SETTING, True)
            settings.set(
                PeopleSettings.CHARACTER_ASSETS_PATH,
                _join_asset_root(asset_root, "Isaac/People/Characters/"),
            )
            settings.set(
                ISAAC_REPLICATOR_DEFAULT_BIPED_SETTING,
                _join_asset_root(asset_root, "Isaac/People/Characters/Biped_Setup.usd"),
            )
            settings.set(
                ISAAC_REPLICATOR_DEFAULT_CHARACTER_SETTING,
                _join_asset_root(asset_root, "Isaac/People/Characters/"),
            )

        effective_navmesh = self.control_mode == "command" and self.navmesh_enabled
        settings.set(PeopleSettings.COMMAND_FILE_PATH, str(self.command_file_path))
        settings.set(PeopleSettings.NUMBER_OF_LOOP, "0")
        settings.set(PeopleSettings.NAVMESH_ENABLED, effective_navmesh)
        settings.set(PeopleSettings.DYNAMIC_AVOIDANCE_ENABLED, self.control_mode == "command")
        settings.set(PeopleSettings.CHARACTER_PRIM_PATH, PrimPaths.characters_parent_path())
        settings.set(
            "/exts/omni.anim.people/navigation_settings/navmesh_enabled",
            effective_navmesh,
        )
        settings.set("/persistent/exts/omni.anim.navigation.core/navMesh/viewNavMesh", False)
        settings.set("/app/omni.graph.scriptnode/enable_opt_in", False)
        settings.set("/app/player/playSimulations", True)
        settings.set("/rtx/raytracing/fractionalCutoutOpacity", True)
        navigation_mode = "navmesh" if effective_navmesh else "direct route"
        print(f"[INFO] Isaac People control mode: {self.control_mode}")
        print(f"[INFO] Isaac People navigation mode: {navigation_mode}")

    def _write_command_file(self):
        self.command_file_path.parent.mkdir(parents=True, exist_ok=True)
        if self.control_mode != "command":
            lines = ["# LC_PROTO route-control mode: command file intentionally empty."]
        else:
            lines = []
            for actor in self.actors:
                lines.extend(actor.command_lines)
        self.command_file_path.write_text("\n".join(lines) + "\n")

    def _spawn_people_characters(self):
        from isaacsim.replicator.agent.core.stage_util import CharacterUtil
        from isaacsim.replicator.agent.core.settings import BehaviorScriptPaths

        self._ensure_character_root()
        biped_prim = CharacterUtil.load_default_biped_to_stage()
        self._update_people_runtime(frames=4)
        anim_graph_prim = CharacterUtil.get_anim_graph_from_character(biped_prim)
        behavior_script_path = BehaviorScriptPaths.behavior_script_path()
        loaded_skelroots = []

        for index, actor in enumerate(self.actors):
            asset_path = self._resolve_character_asset_path(index)
            if asset_path is None:
                print(
                    "[ERROR] No Isaac People character USD found. "
                    "Install Isaac Sim Assets Pack with Isaac/People/Characters "
                    "or set DYNAMIC_PEDESTRIAN_ASSET_PATH to a People-compatible character USD."
                )
                continue

            actor.asset_path = asset_path
            spawn = actor.route[0]
            yaw = _route_yaw_degrees(actor.route, 0)
            if self.control_mode == "route":
                yaw += self.route_yaw_offset_degrees
            prim = CharacterUtil.load_character_usd_to_stage(
                asset_path,
                spawn,
                yaw,
                actor.character_name,
            )
            self._update_people_runtime(frames=4)
            if prim is None or not prim.IsValid():
                print(f"[WARN] Failed to load Isaac People character: {asset_path}")
                continue

            actor.loaded = True
            actor.character_root_path = str(prim.GetPath())
            actor.anim_graph_path = str(anim_graph_prim.GetPath()) if anim_graph_prim and anim_graph_prim.IsValid() else ""
            actor.behavior_script_path = str(behavior_script_path)
            self._ensure_actor_transform_ops(actor)

            skelroot = CharacterUtil.get_character_skelroot_by_root(prim)
            if skelroot is not None and skelroot.IsValid():
                actor.skelroot_path = str(skelroot.GetPath())
                loaded_skelroots.append(skelroot)
            else:
                print(f"[WARN] No SkelRoot found for Isaac People character: {actor.character_name}")

            self._debug_actor_loaded(actor)

        if loaded_skelroots:
            if self.control_mode == "command":
                CharacterUtil.setup_animation_graph_to_character(loaded_skelroots, anim_graph_prim)
                CharacterUtil.setup_python_scripts_to_character(loaded_skelroots, behavior_script_path)
                self._apply_navmesh_exclusion_to_loaded_characters()
                self._debug_character_bindings(loaded_skelroots)
            else:
                self._setup_route_anim_graph(
                    CharacterUtil,
                    loaded_skelroots,
                    anim_graph_prim,
                    behavior_script_path,
                )

    def _ensure_character_root(self):
        from isaacsim.core.utils import prims
        from isaacsim.replicator.agent.core.settings import PrimPaths

        root_path = PrimPaths.characters_parent_path()
        prim = self.stage.GetPrimAtPath(root_path)
        if not prim.IsValid():
            prims.create_prim(root_path, "Xform")

    def _resolve_character_asset_path(self, index: int) -> str | None:
        explicit = str(self.visual_config.pedestrian_asset_path or "").strip()
        if explicit:
            resolved = resolve_pedestrian_asset_path(explicit, self._get_context())
            if resolved:
                return resolved
            return None
        return self._resolve_default_isaac_people_character(index)

    def _resolve_default_isaac_people_character(self, index: int) -> str | None:
        from isaacsim.replicator.agent.core.settings import AssetPaths
        import omni.client

        character_root = AssetPaths.default_character_path()
        if not character_root:
            return None
        return _select_people_character_usd(omni.client, character_root, index)

    def _apply_navmesh_exclusion_to_loaded_characters(self):
        try:
            import omni.kit.commands
            from pxr import NavSchema
        except Exception:
            return

        for actor in self.actors:
            if not actor.loaded:
                continue
            try:
                omni.kit.commands.execute(
                    "ApplyNavMeshAPICommand",
                    prim_path=actor.character_root_path,
                    api=NavSchema.NavMeshExcludeAPI,
                )
            except Exception:
                continue

    def _setup_route_anim_graph(
        self,
        CharacterUtil: Any,
        loaded_skelroots: list[Any],
        anim_graph_prim: Any,
        behavior_script_path: str,
    ):
        result = setup_route_anim_graph(
            character_util=CharacterUtil,
            context=self._get_context(),
            skelroots=loaded_skelroots,
            anim_graph_prim=anim_graph_prim,
            debug_enabled=self.debug_enabled,
        )
        if result.bound:
            if self.debug_enabled:
                print(
                    "[OK] Isaac People route AnimGraph attached: "
                    f"anim_graph={result.anim_graph_path} skelroots={list(result.skelroot_paths)}"
                )
            self._debug_character_bindings(loaded_skelroots)
            self._warmup_route_anim_graph_handles()
            return

        if str(self.visual_config.pedestrian_animation).strip().lower() == "clip":
            if self.debug_enabled:
                print(
                    "[WARN] Isaac People route AnimGraph unavailable; "
                    "trying experimental direct skelanim clip fallback."
                )
            self._bind_route_walk_clips()

    def _bind_route_walk_clips(self):
        for actor in self.actors:
            if not actor.loaded:
                continue
            if self._bind_route_walk_clip(actor) and self.debug_enabled:
                print(
                    "[OK] Isaac People route walk clip bound: "
                    f"character={actor.character_name} skeleton={actor.skeleton_path} "
                    f"clip={actor.walk_clip_path} animation={actor.walk_animation_prim_path}"
                )

    def _bind_route_walk_clip(self, actor: IsaacPeopleActorRuntime) -> bool:
        result = bind_route_walk_clip(
            stage=self.stage,
            context=self._get_context(),
            actor=actor,
            asset_root=resolve_isaac_people_asset_root(),
            explicit_clip_path=self.visual_config.pedestrian_animation_clip_path,
            debug_enabled=self.debug_enabled,
        )
        if not result.bound:
            return False
        actor.skeleton_path = result.skeleton_path
        actor.walk_clip_path = result.clip_path
        actor.walk_animation_prim_path = result.animation_prim_path
        actor.walk_clip_bound = True
        return True

    def _update_people_runtime(self, frames: int = 1):
        for _ in range(max(0, int(frames))):
            try:
                self._get_context().update()
            except Exception as exc:  # pragma: no cover - Isaac runtime path
                if self.debug_enabled:
                    print(f"[WARN] Isaac People runtime update failed: {exc}")
                break

    def _warmup_route_anim_graph_handles(self):
        pending = [
            actor
            for actor in self.actors
            if actor.loaded and actor.skelroot_path and not actor.walk_clip_bound
        ]
        if not pending:
            return

        self._ensure_people_timeline_playing(start_playback=True)
        report_frames = {1, 30, 60, 120, DEFAULT_ROUTE_ANIM_HANDLE_WARMUP_FRAMES}
        for frame in range(1, DEFAULT_ROUTE_ANIM_HANDLE_WARMUP_FRAMES + 1):
            self._update_people_runtime(frames=1)
            pending = [actor for actor in pending if self._get_character_handle(actor) is None]
            if not pending:
                if self.debug_enabled:
                    print(f"[OK] Isaac People route AnimGraph handles ready: warmup_frame={frame}")
                return
            if self.debug_enabled and frame in report_frames:
                print(
                    "[WAIT] Isaac People route AnimGraph handle warmup: "
                    f"frame={frame} pending={[actor.character_name for actor in pending]} "
                    f"runtime={_anim_graph_runtime_summary()}"
                )

        if self.debug_enabled:
            print(
                "[WARN] Isaac People route AnimGraph handles still unavailable after warmup: "
                f"pending={[actor.character_name for actor in pending]} "
                f"runtime={_anim_graph_runtime_summary()}"
            )

    def _ensure_actor_transform_ops(self, actor: IsaacPeopleActorRuntime):
        if self.stage is None or not actor.character_root_path:
            return
        prim = self.stage.GetPrimAtPath(actor.character_root_path)
        if not prim.IsValid():
            return
        xformable = self._get_context().pxr_usd_geom.Xformable(prim)
        actor.translate_op = _find_or_add_xform_op(xformable, "xformOp:translate", "translate")
        actor.orient_op = _find_or_add_xform_op(xformable, "xformOp:orient", "orient")

    def _apply_actor_pose(
        self,
        actor: IsaacPeopleActorRuntime,
        position: tuple[float, float, float],
        yaw: float,
    ):
        if actor.translate_op is None or actor.orient_op is None:
            return
        Gf = self._get_context().pxr_gf
        actor.translate_op.Set(Gf.Vec3d(position[0], position[1], position[2]))
        set_orient_op_yaw(actor.orient_op, Gf, yaw, self.route_yaw_offset_degrees)

    def _set_actor_visible(self, actor: IsaacPeopleActorRuntime, visible: bool):
        was_hidden = actor.hidden
        actor.hidden = not visible
        if (
            self.debug_enabled
            and actor.hidden
            and not was_hidden
            and not actor.hidden_at_route_end_printed
            and _is_stop_at_end_mode(actor.route_mode)
        ):
            actor.hidden_at_route_end_printed = True
            print(
                "[OK] Isaac People actor hidden at route end: "
                f"name={actor.character_name} route_mode={actor.route_mode} "
                f"total_length_m={actor.total_length:.3f}"
            )
        if self.stage is None or not actor.character_root_path:
            return
        prim = self.stage.GetPrimAtPath(actor.character_root_path)
        if not prim.IsValid():
            return
        imageable = self._get_context().pxr_usd_geom.Imageable(prim)
        if visible:
            imageable.MakeVisible()
        else:
            imageable.MakeInvisible()

    def _pose_at_distance(
        self,
        actor: IsaacPeopleActorRuntime,
        distance: float,
    ) -> tuple[tuple[float, float, float], float]:
        remaining = distance
        for index, segment_length in enumerate(actor.segment_lengths):
            start = actor.route[index]
            end = actor.route[index + 1]
            if remaining <= segment_length or index == len(actor.segment_lengths) - 1:
                t = 0.0 if segment_length < 1e-8 else remaining / segment_length
                position = _lerp(start, end, t)
                yaw = math.atan2(end[1] - start[1], end[0] - start[0])
                return position, yaw
            remaining -= segment_length
        start = actor.route[0]
        end = actor.route[1]
        return start, math.atan2(end[1] - start[1], end[0] - start[0])

    def _distance_along_route(self, raw_distance: float, total_length: float, route_mode: str) -> float:
        if total_length < 1e-8:
            return 0.0
        mode = str(route_mode or "loop").lower()
        if _is_stop_at_end_mode(mode):
            return min(raw_distance, total_length)
        if mode == "ping_pong":
            period = total_length * 2.0
            phase = raw_distance % period
            return phase if phase <= total_length else period - phase
        return raw_distance % total_length

    def _should_hide_actor_at_distance(self, actor: IsaacPeopleActorRuntime, raw_distance: float) -> bool:
        threshold = max(0.0, actor.total_length - ROUTE_END_HIDE_EPSILON_M)
        return _is_stop_at_end_mode(actor.route_mode) and raw_distance >= threshold

    def _set_walk_animation(
        self,
        actor: IsaacPeopleActorRuntime,
        moving: bool,
        position: tuple[float, float, float],
        distance: float,
    ):
        handle = self._get_character_handle(actor)
        if handle is None:
            return
        try:
            path_points = self._path_points_for_animation(actor, position, distance)
            animation_state = route_walk_animation_state(moving)
            handle.set_variable("Action", animation_state.action)
            handle.set_variable("PathPoints", path_points)
            handle.set_variable("Walk", animation_state.walk)
            if self.debug_enabled and moving and not actor.animation_update_printed:
                actor.animation_update_printed = True
                print(
                    "[OK] Isaac People route AnimGraph variables set: "
                    f"character={actor.character_name} action={animation_state.action} "
                    f"walk={animation_state.walk} "
                    f"path_points={path_points}"
                )
        except Exception as exc:  # pragma: no cover - Isaac runtime path
            if self.debug_enabled and not actor.animation_warning_printed:
                actor.animation_warning_printed = True
                print(
                    "[WARN] Isaac People animation variable update failed for "
                    f"{actor.character_name}: {exc}"
                )

    def _timeline_debug_state(self) -> str:
        try:
            import omni.timeline

            timeline = omni.timeline.get_timeline_interface()
            return (
                f"playing={timeline.is_playing()},"
                f"time={_safe_call(timeline, 'get_current_time')}"
            )
        except Exception as exc:  # pragma: no cover - Isaac runtime path
            return f"<error:{type(exc).__name__}>"

    def _get_character_handle(self, actor: IsaacPeopleActorRuntime):
        if actor.character_handle is not None:
            return actor.character_handle

        candidates = _character_handle_lookup_paths(actor)
        if not candidates:
            return None

        actor.handle_attempts += 1
        self._ensure_people_timeline_playing()
        handle = None
        failed_candidates = []
        try:
            import omni.anim.graph.core as ag

            for candidate in candidates:
                handle = ag.get_character(candidate)
                if handle is not None:
                    actor.character_handle = handle
                    if self.debug_enabled:
                        print(f"[OK] Isaac People character handle acquired: {candidate}")
                    return actor.character_handle
                failed_candidates.append(candidate)
        except Exception as exc:  # pragma: no cover - Isaac runtime path
            if self.debug_enabled and actor.handle_attempts in {1, 60}:
                print(
                    "[WARN] ag.get_character failed for "
                    f"{candidates}: {exc}"
                )

        if self.debug_enabled and actor.handle_attempts in {1, 60}:
            print(
                "[WARN] Isaac People character handle unavailable: "
                f"candidates={failed_candidates or candidates} "
                f"attempt={actor.handle_attempts} "
                f"timeline={self._timeline_debug_state()} "
                f"anim_graph_runtime={_anim_graph_runtime_summary()}"
            )
        return actor.character_handle

    def _path_points_for_animation(
        self,
        actor: IsaacPeopleActorRuntime,
        position: tuple[float, float, float],
        distance: float,
    ):
        next_point = actor.route[-1]
        remaining = distance
        for index, segment_length in enumerate(actor.segment_lengths):
            if remaining <= segment_length or index == len(actor.segment_lengths) - 1:
                next_point = actor.route[index + 1]
                break
            remaining -= segment_length
        try:
            import carb

            return [carb.Float3(*position), carb.Float3(*next_point)]
        except Exception:
            return [position, next_point]

    def _debug_actor_loaded(self, actor: IsaacPeopleActorRuntime):
        if not self.debug_enabled:
            return
        print(
            "[DEBUG] Isaac People actor loaded: "
            f"name={actor.character_name} asset={actor.asset_path} "
            f"root={actor.character_root_path} skelroot={actor.skelroot_path or '<missing>'} "
            f"anim_graph={actor.anim_graph_path or '<missing>'} "
            f"route_start={actor.route[0]} route_end={actor.route[-1]}"
        )

    def _debug_character_bindings(self, skelroots: list[Any]):
        if not self.debug_enabled:
            return
        for skelroot in skelroots:
            script_attr = skelroot.GetAttribute("omni:scripting:scripts")
            scripts = script_attr.Get() if script_attr and script_attr.IsValid() else None
            anim_graph_targets = anim_graph_targets_for_skelroot(skelroot)
            schemas = applied_schema_names(skelroot)
            print(
                "[DEBUG] Isaac People character binding: "
                f"skelroot={skelroot.GetPath()} scripts={scripts} "
                f"schemas={schemas} anim_graph_targets={anim_graph_targets}"
            )

    def _debug_route_progress(
        self,
        actor: IsaacPeopleActorRuntime,
        position: tuple[float, float, float],
    ):
        if not self.debug_enabled or actor.hidden:
            return
        actor.debug_frame_count += 1
        if actor.debug_frame_count == 1:
            actor.debug_start_position = position
            print(f"[DEBUG] Isaac People route frame 1: {actor.character_name} pos={position}")
        elif actor.debug_frame_count == 60 and actor.debug_start_position is not None:
            delta = _distance(actor.debug_start_position, position)
            print(
                "[DEBUG] Isaac People route frame 60: "
                f"{actor.character_name} pos={position} moved_m={delta:.3f}"
            )


def resolve_isaac_people_asset_root(
    env_value: str | None = None,
    default_root: Path | str | None = None,
) -> str | None:
    if env_value is None:
        env_value = os.environ.get("ISAAC_ASSET_ROOT")
    if env_value:
        return _normalize_asset_root(env_value, require_people_assets=False)

    candidate = Path(default_root) if default_root is not None else DEFAULT_LOCAL_ISAAC_ASSET_ROOT
    return _normalize_asset_root(str(candidate), require_people_assets=True)



def resolve_isaac_people_navmesh_enabled(
    env_value: str | None = None,
    default: bool = DEFAULT_ISAAC_PEOPLE_NAVMESH_ENABLED,
) -> bool:
    if env_value is None:
        env_value = os.environ.get(ISAAC_PEOPLE_NAVMESH_ENV)
    if env_value is None or str(env_value).strip() == "":
        return bool(default)
    value = str(env_value).strip().lower()
    if value in {"1", "true", "yes", "on", "navmesh"}:
        return True
    if value in {"0", "false", "no", "off", "direct", "route"}:
        return False
    return bool(default)


def resolve_isaac_people_control_mode(
    env_value: str | None = None,
    default: str = DEFAULT_ISAAC_PEOPLE_CONTROL_MODE,
) -> str:
    if env_value is None:
        env_value = os.environ.get(ISAAC_PEOPLE_CONTROL_ENV)
    value = str(env_value or default).strip().lower()
    if value in {"route", "direct", "direct_route", "direct-route"}:
        return "route"
    if value in {"command", "oap", "goto", "go_to", "go-to"}:
        return "command"
    return default


def resolve_bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or str(value).strip() == "":
        return bool(default)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def character_name_for_index(index: int) -> str:
    if index <= 0:
        return "Character"
    if index < 10:
        return f"Character_0{index}"
    return f"Character_{index}"


def people_command_lines_for_route(
    character_name: str,
    route: list[tuple[float, float, float]],
    final_idle_s: float = 9999.0,
) -> list[str]:
    if len(route) < 2:
        return []
    lines = []
    for index, point in enumerate(route[1:], start=1):
        yaw = _route_yaw_degrees(route, index - 1)
        lines.append(
            f"{character_name} GoTo "
            f"{_format_float(point[0])} {_format_float(point[1])} {_format_float(point[2])} "
            f"{_format_float(yaw)}"
        )
    if final_idle_s > 0.0:
        lines.append(f"{character_name} Idle {_format_float(final_idle_s)}")
    return lines


def _normalize_asset_root(raw_root: str, require_people_assets: bool) -> str | None:
    root = raw_root.strip().strip("'\"")
    if not root:
        return None
    if _looks_like_remote_asset_root(root):
        return root.rstrip("/")

    path = Path(root).expanduser()
    if require_people_assets and not _has_people_assets(path):
        return None
    return str(path.resolve() if path.exists() else path)


def _has_people_assets(root: Path) -> bool:
    characters = root / "Isaac/People/Characters"
    return characters.is_dir() and (characters / "Biped_Setup.usd").is_file()


def _looks_like_remote_asset_root(root: str) -> bool:
    return "://" in root or root.startswith("omniverse:")


def _join_asset_root(asset_root: str, relative_path: str) -> str:
    return f"{asset_root.rstrip('/')}/{relative_path.lstrip('/')}"


def _select_people_character_usd(omni_client: Any, character_root: str, index: int) -> str | None:
    root = character_root.rstrip("/")
    result, entries = omni_client.list(root)
    if "OK" not in str(result):
        return None

    folders = []
    direct_usds = []
    for entry in sorted(entries, key=lambda item: getattr(item, "relative_path", "")):
        relative = getattr(entry, "relative_path", "")
        if not relative:
            continue
        child_path = f"{root}/{relative}"
        if Path(relative).suffix.lower() in {".usd", ".usda", ".usdc"}:
            if "biped_setup" not in relative.lower():
                direct_usds.append(child_path)
            continue
        if relative.startswith(".") or relative.lower() == "biped_demo":
            continue
        folders.append(child_path)

    if direct_usds:
        return direct_usds[index % len(direct_usds)]
    if not folders:
        return None

    ordered_folders = folders[index % len(folders):] + folders[: index % len(folders)]
    for folder in ordered_folders:
        character_usd = _first_people_usd_in_folder(omni_client, folder)
        if character_usd:
            return character_usd
    return None


def _first_people_usd_in_folder(omni_client: Any, folder_path: str) -> str | None:
    result, entries = omni_client.list(folder_path.rstrip("/"))
    if "OK" not in str(result):
        return None
    usd_children = []
    for entry in sorted(entries, key=lambda item: getattr(item, "relative_path", "")):
        relative = getattr(entry, "relative_path", "")
        if not relative or Path(relative).suffix.lower() not in {".usd", ".usda", ".usdc"}:
            continue
        lower = relative.lower()
        if any(skip in lower for skip in ("motion", "animation", "biped_setup")):
            continue
        usd_children.append(f"{folder_path.rstrip('/')}/{relative}")
    return usd_children[0] if usd_children else None


def _find_or_add_xform_op(xformable: Any, op_name: str, op_type: str) -> Any:
    for op in xformable.GetOrderedXformOps():
        if op.GetOpName() == op_name:
            return op
    if op_type == "translate":
        return xformable.AddTranslateOp()
    if op_type == "orient":
        return xformable.AddOrientOp()
    raise ValueError(f"Unsupported xform op type: {op_type}")



@dataclass(frozen=True)
class RouteWalkAnimationState:
    action: str
    walk: float


def route_walk_animation_state(moving: bool) -> RouteWalkAnimationState:
    return RouteWalkAnimationState(
        action="Walk" if moving else "None",
        walk=1.0 if moving else 0.0,
    )


def _route_walk_animation_should_move(
    actor: IsaacPeopleActorRuntime,
    raw_distance: float,
    travel_time_s: float,
    hidden: bool = False,
) -> bool:
    if hidden or travel_time_s <= 0.0:
        return False
    if float(actor.plan.speed_mps) <= 0.0:
        return False
    if _is_stop_at_end_mode(actor.route_mode) and raw_distance >= actor.total_length:
        return False
    return True


def _character_handle_lookup_paths(actor: IsaacPeopleActorRuntime) -> list[str]:
    paths = []
    for candidate in (actor.skelroot_path, actor.character_root_path, actor.character_name):
        if candidate and candidate not in paths:
            paths.append(candidate)
    return paths



def _route_mode_for_plan(plan: DynamicActorPlan) -> str:
    route_plan = plan.route_plan
    if route_plan is not None and route_plan.route_mode:
        return str(route_plan.route_mode)
    return "loop"


def _is_stop_at_end_mode(route_mode: str) -> bool:
    return str(route_mode or "").lower() in {"once", "stop_at_end", "stop-at-end"}


def _route_yaw_degrees(route: list[tuple[float, float, float]], segment_index: int) -> float:
    start = route[max(0, min(segment_index, len(route) - 2))]
    end = route[max(1, min(segment_index + 1, len(route) - 1))]
    return math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))


def _format_float(value: float) -> str:
    text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return text if text and text != "-0" else "0"


def _as_vec3(value) -> tuple[float, float, float]:
    if len(value) < 3:
        raise ValueError(f"Expected 3D route point, got {value}")
    return (float(value[0]), float(value[1]), float(value[2]))


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 + (b[2] - a[2]) ** 2)


def _lerp(
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    t: float,
) -> tuple[float, float, float]:
    return (
        start[0] + (end[0] - start[0]) * t,
        start[1] + (end[1] - start[1]) * t,
        start[2] + (end[2] - start[2]) * t,
    )


def _safe_prim_name(value: str) -> str:
    name = re.sub(r"[^0-9a-zA-Z_]", "_", value.strip())
    return name or "dynamic_actor"

def _safe_call(obj: Any, method_name: str):
    try:
        method = getattr(obj, method_name)
    except Exception:
        return "<unavailable>"
    try:
        return method()
    except Exception:
        return "<error>"

def _anim_graph_runtime_summary() -> str:
    try:
        import omni.anim.graph.core as ag

        count = ag.get_character_count()
        return f"count={count}"
    except Exception as exc:
        return f"<error:{type(exc).__name__}>"

