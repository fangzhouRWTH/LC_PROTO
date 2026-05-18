import isaac_env.isaac_adaptor.isaac_context as iscctx


class SimWorld:
    def __init__(self):
        self.world = iscctx.get_isaac_context().isaac_core.api.World(
            stage_units_in_meters=1.0, physics_dt=1 / 500, rendering_dt=1 / 50
        )
