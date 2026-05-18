from functools import cache

from isaacsim.simulation_app import SimulationApp

# @cache
# def get_omni_usd():
#     import omni.usd

#     return omni.usd


# @cache
# def get_pxr_modules():
#     from pxr import Usd, UsdLux, UsdGeom, UsdPhysics, PhysxSchema, Gf

#     return Usd, UsdLux, UsdGeom, UsdPhysics, PhysxSchema, Gf


# @cache
# def get_isaac_core_utils():
#     from omni.isaac.core.utils.prims import create_prim, get_prim_at_path
#     from omni.isaac.core.utils.stage import add_reference_to_stage

#     return create_prim, get_prim_at_path, add_reference_to_stage


class IsaacContext:
    def __init__(self):
        self.simulation_app = SimulationApp(
            {
                "headless": False,
                "width": 1280,
                "height": 720,
            }
        )

        import isaacsim.core as isaac_core

        self.isaac_core = isaac_core

        import isaacsim.core.utils as isaac_core_utils

        self.isaac_core_utils = isaac_core_utils

        import omni.usd as omni_usd

        self.omni_usd = omni_usd

        import omni.appwindow as omni_appwindow

        self.omni_appwindow = omni_appwindow

        import pxr.Usd as Usd

        self.pxr_usd = Usd

        import pxr.UsdLux as UsdLux

        self.pxr_usd_lux = UsdLux

        import pxr.UsdGeom as UsdGeom

        self.pxr_usd_geom = UsdGeom

        import pxr.Gf as Gf

        self.pxr_gf = Gf

        import pxr.Sdf as Sdf

        self.pxr_Sdf = Sdf

        # from pxr import Usd, UsdGeom, UsdPhysics, PhysxSchema, Gf
        # from omni.isaac.core.utils.prims import create_prim
        # from omni.isaac.core.utils.stage import add_reference_to_stage

        # self.omni_usd = omni.usd
        # self.Usd = Usd
        # self.UsdGeom = UsdGeom
        # self.UsdPhysics = UsdPhysics
        # self.PhysxSchema = PhysxSchema
        # self.Gf = Gf

        # self.create_prim = create_prim
        # self.add_reference_to_stage = add_reference_to_stage

    # @property
    # def stage(self):
    #     return self.omni_usd.get_context().get_stage()

    def update(self):
        self.simulation_app.update()

    def is_running(self):
        return self.simulation_app.is_running()

    def close(self):
        self.simulation_app.close()


_isaac_context: None | IsaacContext = None


def init_isaac_context() -> IsaacContext:
    global _isaac_context

    if _isaac_context is not None:
        print("[WARNING] IsaacContext already initialized.")
        return _isaac_context

    _isaac_context = IsaacContext()
    print("[OK] IsaacContext initialized.")
    return _isaac_context


def get_isaac_context() -> IsaacContext:
    global _isaac_context

    if _isaac_context is None:
        init_isaac_context()

    return _isaac_context
