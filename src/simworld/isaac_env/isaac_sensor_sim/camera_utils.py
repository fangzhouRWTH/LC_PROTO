from __future__ import annotations

import numpy as np


DEPTH_DISPLAY_RENDER_VAR = "DistanceToCamera"
DEPTH_DISPLAY_RENDER_VAR_OUTPUT = "DistanceToCameraSDDisplay"


def get_active_viewport():
    try:
        from omni.kit.viewport.utility import get_active_viewport as _get_viewport

        return _get_viewport()
    except Exception:
        return None


def set_active_viewport_camera(camera_prim_path: str) -> bool:
    try:
        from isaacsim.core.utils.viewports import set_active_viewport_camera

        set_active_viewport_camera(camera_prim_path)
        return True
    except Exception:
        pass

    viewport = get_active_viewport()
    if viewport is None:
        return False

    try:
        viewport.camera_path = camera_prim_path
        return True
    except Exception:
        return False


def get_viewport_render_product_path(viewport) -> str | None:
    render_product_path = getattr(viewport, "render_product_path", None)
    if not render_product_path and hasattr(viewport, "get_render_product_path"):
        render_product_path = viewport.get_render_product_path()

    if not render_product_path:
        return None

    render_product_path = str(render_product_path)
    if not render_product_path.startswith("/"):
        render_product_path = f"/Render/RenderProduct_{render_product_path}"
    return render_product_path


def activate_viewport_depth_display(
    *,
    near_m: float,
    far_m: float,
    render_var: str = DEPTH_DISPLAY_RENDER_VAR,
) -> dict | None:
    viewport = get_active_viewport()
    if viewport is None:
        return None

    render_product_path = get_viewport_render_product_path(viewport)
    if render_product_path is None:
        return None

    previous_display_render_var = getattr(viewport, "display_render_var", None)
    display_template = f"{render_var}Display"
    post_template = f"{render_var}DisplayPost"
    combine_template = f"{render_var}DisplayPostCombine"
    display_render_var = f"{render_var}SDDisplay"
    activated_templates: list[str] = []

    try:
        from omni.syntheticdata import SyntheticData

        stage = getattr(viewport, "stage", None)
        synthetic_data = SyntheticData.Get()

        for template in (display_template, combine_template):
            try:
                synthetic_data.activate_node_template(
                    template,
                    0,
                    [render_product_path],
                    None,
                    stage,
                )
                activated_templates.append(template)
            except Exception as exc:
                print(f"[WARNING] Could not activate {template}: {exc}")

        synthetic_data.set_node_attributes(
            post_template,
            {"inputs:parameters": [float(near_m), float(far_m), 0.0, 0.0]},
            render_product_path,
        )
        if combine_template in activated_templates:
            synthetic_data.set_node_attributes(
                combine_template,
                {"inputs:parameters": [0.0, 0.0, -100.0]},
                render_product_path,
            )
        viewport.display_render_var = display_render_var
        return {
            "viewport": viewport,
            "render_product_path": render_product_path,
            "previous_display_render_var": previous_display_render_var,
            "display_templates": activated_templates,
        }
    except Exception as exc:
        print(f"[WARNING] Could not activate viewport depth display: {exc}")
        return None


def restore_viewport_display(display_state: dict | None) -> bool:
    if not display_state:
        return False

    viewport = display_state.get("viewport") or get_active_viewport()
    render_product_path = display_state.get("render_product_path")
    display_templates = display_state.get("display_templates") or []
    previous_display_render_var = display_state.get("previous_display_render_var")

    restored = False
    if viewport is not None and hasattr(viewport, "display_render_var"):
        try:
            viewport.display_render_var = previous_display_render_var or ""
            restored = True
        except Exception:
            pass

    if display_templates and render_product_path:
        try:
            from omni.syntheticdata import SyntheticData

            stage = getattr(viewport, "stage", None) if viewport is not None else None
            synthetic_data = SyntheticData.Get()
            for template in reversed(display_templates):
                synthetic_data.deactivate_node_template(
                    template,
                    0,
                    [render_product_path],
                    stage,
                )
            restored = True
        except Exception:
            pass

    return restored


def set_camera_look_at(
    *,
    eye: tuple[float, float, float] | list[float] | np.ndarray,
    target: tuple[float, float, float] | list[float] | np.ndarray,
    camera_prim_path: str,
) -> bool:
    viewport = get_active_viewport()
    if viewport is None:
        return False

    try:
        from isaacsim.core.utils.viewports import set_camera_view

        set_camera_view(
            eye=np.asarray(eye, dtype=np.double),
            target=np.asarray(target, dtype=np.double),
            camera_prim_path=camera_prim_path,
            viewport_api=viewport,
        )
        return True
    except Exception:
        return False


def ensure_xform_path(stage, prim_path: str, UsdGeom) -> None:
    cleaned = prim_path.strip("/")
    if not cleaned:
        return

    current = ""
    for part in cleaned.split("/"):
        current = f"{current}/{part}"
        prim = stage.GetPrimAtPath(current)
        if not prim.IsValid():
            UsdGeom.Xform.Define(stage, current)
