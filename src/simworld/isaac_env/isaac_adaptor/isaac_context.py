from functools import cache


@cache
def get_omni_usd():
    import omni.usd

    return omni.usd


@cache
def get_pxr_modules():
    from pxr import Usd, UsdGeom, UsdPhysics, PhysxSchema, Gf

    return Usd, UsdGeom, UsdPhysics, PhysxSchema, Gf


@cache
def get_isaac_core_utils():
    from omni.isaac.core.utils.prims import create_prim, get_prim_at_path
    from omni.isaac.core.utils.stage import add_reference_to_stage

    return create_prim, get_prim_at_path, add_reference_to_stage


class IsaacContext:
    def __init__(self):
        import isaacsim.core.utils as isaac_core_utils

        self.isaac_core_utils = isaac_core_utils
        # self.omni_app
        # import omni.usd
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
