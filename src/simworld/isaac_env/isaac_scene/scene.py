from ..isaac_adaptor import isaac_context as iscctx

import pathlib

from . import scene_tools as tools
from . import scene_parser as parser


class SimScene:
    def __init__(self, path: pathlib.Path, rules=None, sky_texture_path=None):
        self.path = pathlib.Path(path).expanduser()
        self.rules = rules
        self.sky_texture_path = sky_texture_path
        self.context = iscctx.get_isaac_context().omni_usd.get_context()
        self.stats = parser.SceneStats()

        if not self.context.open_stage(str(self.path)):
            raise RuntimeError(f"Failed to open USD stage: {self.path}")
        self.stage = self.context.get_stage()

    def prepare(self, verbose: bool = False):
        self.stats = parser.SceneStats()
        tools.deactivate_all_lights(self.stage)
        if self.sky_texture_path is None:
            tools.add_natural_light(self.stage)
        else:
            tools.add_natural_light(self.stage, sky_texture_path=self.sky_texture_path)

        return parser.process_stage_by_naming_rules(
            self.stage,
            stats=self.stats,
            rules=self.rules,
            verbose=verbose,
        )

    def update(self):
        iscctx.get_isaac_context().simulation_app.update()
