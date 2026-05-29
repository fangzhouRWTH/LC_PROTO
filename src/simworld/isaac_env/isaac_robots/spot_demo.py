from ..isaac_adaptor import isaac_context as iscctx
import numpy as np


class SpotDemo:
    def __init__(self, name):
        self.name = name
        self.spot_prim_path = "/World/Spot_" + name
        self.root_prim_path = self.spot_prim_path
        self.initialized = False
        self.need_reinit = True
        self.command_cache = np.zeros(3, dtype=np.float32)

    def spawn(self, position):
        self.spot = (
            iscctx.get_isaac_context().robot_policy_examples.SpotFlatTerrainPolicy(
                prim_path=self.spot_prim_path,
                name=self.name,
                position=position,
            )
        )

        self.initialize()

    def initialize(self):
        self.initialize_spot()

    def initialize_spot(self):
        try:
            self.spot.initialize()
            self.initialized = True
            self.need_reinit = False
            print("[INFO] Spot initialized.")
        except Exception as e:
            self.mark_reinit_required()
            print(f"[ERROR] Spot initialize failed: {e}")

    def mark_reinit_required(self):
        self.initialized = False
        self.need_reinit = True

    def reset(self):
        self.spot.reset()

    def forward(self, stepsize):
        if not self.initialized:
            return

        try:
            self.spot.forward(stepsize, self.command_cache)
        except Exception:
            self.mark_reinit_required()
            raise

    def step(self, command):
        command = np.asarray(command, dtype=np.float32).reshape(-1)
        if command.size != 3:
            raise ValueError(
                f"Spot command must have 3 values, got shape {command.shape}"
            )

        self.command_cache = command.copy()
