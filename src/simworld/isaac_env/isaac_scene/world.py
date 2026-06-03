from ..isaac_adaptor import isaac_context as iscctx


class SimWorld:
    def __init__(self):
        self.world = iscctx.get_isaac_context().isaac_core.api.World(
            stage_units_in_meters=1.0, physics_dt=1 / 500, rendering_dt=1 / 50
        )

        self.need_reinit = False
        self.was_stopped = False

    def prepare(self, func_name, func):
        self.world.add_physics_callback(func_name, callback_fn=func)
        # self.reset()

    def reset(self):
        print("[INFO] Resetting simulation world...")
        self.world.reset()
        self.need_reinit = False

    def is_stopped(self):
        return self.world.is_stopped()

    def is_playing(self):
        return self.world.is_playing()

    def update_state(self):
        if self.is_stopped() and not self.was_stopped:
            self.need_reinit = True
        self.was_stopped = self.is_stopped()

    def check_reinit(self):
        if self.is_playing() and self.need_reinit:
            self.need_reinit = False
            self.was_stopped = False
            self.reset()
            return True
        return False

    def step(self, render=False):
        self.world.step(render=render)

    def play(self):
        self.world.play()

    def stop(self):
        self.world.stop()
