class NoOpRobot:
    """Robot placeholder for scene-only demos that do not need a controllable robot."""

    def __init__(self, name):
        self.name = name
        self.root_prim_path = "/World"
        self.initialized = True
        self.need_reinit = False

    def spawn(self, position):
        self.initialized = True
        self.need_reinit = False
        print("[INFO] No-op robot selected; skipping robot spawn.")

    def initialize(self):
        self.initialized = True
        self.need_reinit = False

    def mark_reinit_required(self):
        self.initialized = True
        self.need_reinit = False

    def forward(self, stepsize):
        return

    def step(self, command):
        return
