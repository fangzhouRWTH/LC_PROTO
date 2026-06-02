from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import math
import re
import tempfile

from engine.dynamic import DynamicActorPlan, DynamicScenePlan

from .kinematic import DEFAULT_DYNAMIC_ROOT
from .visuals import DynamicVisualConfig, resolve_pedestrian_asset_path

PEOPLE_CHARACTER_ROOT = "/World/Characters"
PEOPLE_COMMAND_DIR = Path(tempfile.gettempdir()) / "lc_proto_dynamic_people"
PEOPLE_COMMAND_FILE = PEOPLE_COMMAND_DIR / "dynamic_people_commands.txt"
PEOPLE_EXTENSIONS = (
    "omni.kit.scripting",
    "omni.anim.timeline",
    "omni.anim.graph.core",
    "omni.anim.retarget.core",
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
    command_lines: list[str] = field(default_factory=list)
    character_root_path: str = ""
    loaded: bool = False


class IsaacPeopleDynamicAgentBackend:
    """Isaac People / OAP animated pedestrian backend.

    LC_PROTO still authors pedestrian routes, but omni.anim.people owns runtime
    locomotion and walking animation. Vehicles should be handled by a composite
    backend such as isaac_people_sumo.
    """

    def __init__(
        self,
        root_prim_path: str = DEFAULT_DYNAMIC_ROOT,
        visual_config: DynamicVisualConfig | None = None,
        command_file_path: str | Path | None = None,
    ):
        self.root_prim_path = root_prim_path
        self.visual_config = visual_config or DynamicVisualConfig()
        self.command_file_path = Path(command_file_path or PEOPLE_COMMAND_FILE)
        self.context = None
        self.stage = None
        self.plan = DynamicScenePlan()
        self.actors: list[IsaacPeopleActorRuntime] = []
        self.available = False

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
            character_name = character_name_for_index(index)
            self.actors.append(
                IsaacPeopleActorRuntime(
                    plan=actor_plan,
                    character_name=character_name,
                    route=route,
                    command_lines=people_command_lines_for_route(
                        character_name,
                        route,
                    ),
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

        print(
            "[OK] Spawned "
            f"{sum(1 for actor in self.actors if actor.loaded)} "
            "Isaac People animated pedestrian actor(s)."
        )
        print(f"[INFO] Isaac People command file: {self.command_file_path}")

    def reset(self):
        if not self.actors:
            return
        try:
            self._write_command_file()
            self._reset_loaded_character_transforms()
        except Exception as exc:  # pragma: no cover - Isaac runtime path
            print(f"[WARN] Isaac People reset failed: {exc}")

    def step(self, dt: float):
        # omni.anim.people advances through Isaac's simulation/update loop.
        return

    def _get_context(self):
        if self.context is None:
            from ...isaac_adaptor import isaac_context as iscctx

            self.context = iscctx.get_isaac_context()
        return self.context

    def _enable_people_extensions(self, context):
        import omni.kit.app

        ext_manager = omni.kit.app.get_app().get_extension_manager()
        for extension_name in PEOPLE_EXTENSIONS:
            ext_manager.set_extension_enabled_immediate(extension_name, True)
        for _ in range(2):
            context.update()

    def _configure_people_settings(self):
        import carb
        from omni.anim.people.settings import PeopleSettings
        from isaacsim.replicator.agent.core.settings import PrimPaths

        settings = carb.settings.get_settings()
        settings.set(PeopleSettings.COMMAND_FILE_PATH, str(self.command_file_path))
        settings.set(PeopleSettings.NUMBER_OF_LOOP, "0")
        settings.set(PeopleSettings.NAVMESH_ENABLED, True)
        settings.set(PeopleSettings.DYNAMIC_AVOIDANCE_ENABLED, True)
        settings.set(PeopleSettings.CHARACTER_PRIM_PATH, PrimPaths.characters_parent_path())
        settings.set("/exts/omni.anim.people/navigation_settings/navmesh_enabled", True)
        settings.set("/persistent/exts/omni.anim.navigation.core/navMesh/viewNavMesh", False)
        settings.set("/app/omni.graph.scriptnode/enable_opt_in", False)
        settings.set("/rtx/raytracing/fractionalCutoutOpacity", True)

    def _write_command_file(self):
        self.command_file_path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for actor in self.actors:
            lines.extend(actor.command_lines)
        self.command_file_path.write_text("\n".join(lines) + "\n")

    def _spawn_people_characters(self):
        from isaacsim.replicator.agent.core.stage_util import CharacterUtil
        from isaacsim.replicator.agent.core.settings import BehaviorScriptPaths

        self._ensure_character_root()
        biped_prim = CharacterUtil.load_default_biped_to_stage()
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

            spawn = actor.route[0]
            yaw = _route_yaw_degrees(actor.route, 0)
            prim = CharacterUtil.load_character_usd_to_stage(
                asset_path,
                spawn,
                yaw,
                actor.character_name,
            )
            if prim is None or not prim.IsValid():
                print(f"[WARN] Failed to load Isaac People character: {asset_path}")
                continue

            actor.loaded = True
            actor.character_root_path = str(prim.GetPath())
            skelroot = CharacterUtil.get_character_skelroot_by_root(prim)
            if skelroot is not None:
                loaded_skelroots.append(skelroot)

        if loaded_skelroots:
            CharacterUtil.setup_animation_graph_to_character(
                loaded_skelroots,
                CharacterUtil.get_anim_graph_from_character(biped_prim),
            )
            CharacterUtil.setup_python_scripts_to_character(
                loaded_skelroots,
                BehaviorScriptPaths.behavior_script_path(),
            )
            self._apply_navmesh_exclusion_to_loaded_characters()

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

    def _reset_loaded_character_transforms(self):
        context = self._get_context()
        Gf = context.pxr_gf
        for actor in self.actors:
            if not actor.loaded:
                continue
            prim = self.stage.GetPrimAtPath(actor.character_root_path)
            if not prim.IsValid():
                continue
            xformable = context.pxr_usd_geom.Xformable(prim)
            translate_op = _find_or_add_xform_op(xformable, "xformOp:translate", "translate")
            orient_op = _find_or_add_xform_op(xformable, "xformOp:orient", "orient")
            spawn = actor.route[0]
            translate_op.Set(Gf.Vec3d(*spawn))
            orient_op.Set(
                Gf.Quatf(
                    Gf.Rotation(Gf.Vec3d(0.0, 0.0, 1.0), _route_yaw_degrees(actor.route, 0)).GetQuat()
                )
            )


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


def _safe_prim_name(value: str) -> str:
    name = re.sub(r"[^0-9a-zA-Z_]", "_", value.strip())
    return name or "dynamic_actor"
