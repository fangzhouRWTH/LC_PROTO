import numpy as np

from .go2_config import Go2UsdNotFoundError
from .go2_policy import Go2RoughTerrainPolicy


class Go2Demo:
    def __init__(self, name: str):
        self.name = name
        self.go2_prim_path = "/World/Go2_" + name
        self.root_prim_path = self.go2_prim_path
        self.initialized = False
        self.need_reinit = True
        self.command_cache = np.zeros(3, dtype=np.float32)
        self.go2 = None

    def spawn(self, position):
        print(
            "[INFO] Spawning Unitree Go2 at "
            f"{self.go2_prim_path} position={position}"
        )
        try:
            self.go2 = Go2RoughTerrainPolicy(
                prim_path=self.go2_prim_path,
                name=self.name,
                position=position,
            )
        except Go2UsdNotFoundError as exc:
            self.mark_reinit_required()
            print(f"[ERROR] {exc}")
            return
        except Exception as exc:
            self.mark_reinit_required()
            print(f"[ERROR] Unitree Go2 spawn failed: {type(exc).__name__}: {exc}")
            raise

        self.initialize()

    def initialize(self):
        self.initialize_go2()

    def initialize_go2(self):
        try:
            self.go2.initialize()
            self.initialized = True
            self.need_reinit = False
            print("[INFO] Unitree Go2 initialized.")
        except Exception as exc:
            self.mark_reinit_required()
            print(f"[ERROR] Unitree Go2 initialize failed: {exc}")

    def mark_reinit_required(self):
        self.initialized = False
        self.need_reinit = True

    def reset(self):
        if self.go2 is not None:
            self.go2.reset()

    def forward(self, stepsize):
        if not self.initialized or self.go2 is None:
            return

        try:
            self.go2.forward(stepsize, self.command_cache)
        except Exception:
            self.mark_reinit_required()
            raise

    def step(self, command):
        command = np.asarray(command, dtype=np.float32).reshape(-1)
        if command.size != 3:
            raise ValueError(
                f"Go2 command must have 3 values, got shape {command.shape}"
            )

        self.command_cache = command.copy()
