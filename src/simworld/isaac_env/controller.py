import numpy as np
from .isaac_adaptor import isaac_context as iscctx
import carb
from carb.input import KeyboardEventType


class KeyboardVelocityController:
    def __init__(self, ctx: iscctx.IsaacContext, vx=0.6, vy=0.4, yaw=0.8):
        self.vx_speed = vx
        self.vy_speed = vy
        self.yaw_speed = yaw

        self.command = np.zeros(3, dtype=np.float32)

        self._pressed = set()

        self._app_window = omni.appwindow.get_default_app_window()
        self._keyboard = self._app_window.get_keyboard()
        self._input = carb.input.acquire_input_interface()

        self._sub_id = self._input.subscribe_to_keyboard_events(
            self._keyboard,
            self._on_keyboard_event,
        )

        print("[OK] Keyboard controller initialized.")
        print(
            "W/S: forward/backward, A/D: left/right, Q/E: turn left/right, Space: stop"
        )

    def _on_keyboard_event(self, event):
        key = event.input

        if event.type in (KeyboardEventType.KEY_PRESS, KeyboardEventType.KEY_REPEAT):
            self._pressed.add(key)

        elif event.type == KeyboardEventType.KEY_RELEASE:
            self._pressed.discard(key)

        self._update_command()
        return True

    def _update_command(self):
        self.command[:] = 0.0

        # forward / backward
        if carb.input.KeyboardInput.W in self._pressed:
            self.command[0] += self.vx_speed
        if carb.input.KeyboardInput.S in self._pressed:
            self.command[0] -= self.vx_speed

        # lateral movement
        if carb.input.KeyboardInput.A in self._pressed:
            self.command[1] += self.vy_speed
        if carb.input.KeyboardInput.D in self._pressed:
            self.command[1] -= self.vy_speed

        # yaw rotation
        if carb.input.KeyboardInput.Q in self._pressed:
            self.command[2] += self.yaw_speed
        if carb.input.KeyboardInput.E in self._pressed:
            self.command[2] -= self.yaw_speed

        # emergency stop
        if carb.input.KeyboardInput.SPACE in self._pressed:
            self.command[:] = 0.0
            self._pressed.clear()

    def get_command(self):
        return self.command.copy()

    def shutdown(self):
        if self._sub_id is not None:
            self._input.unsubscribe_to_keyboard_events(self._keyboard, self._sub_id)
            self._sub_id = None
