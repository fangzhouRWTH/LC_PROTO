from isaac_env.isaac_adaptor import isaac_context as iscctx

import pathlib

import isaac_env.isaac_scene.scene_tools as tools
import isaac_env.isaac_scene.scene_parser as parser


class SimScene:
    def __init__(self, path: pathlib.Path):
        self.path = path
        self.context = iscctx.get_isaac_context().omni_usd.get_context()

        if not self.context.open_stage(str(self.path)):
            raise RuntimeError(f"Failed to open USD stage: {self.path}")
        self.stage = self.context.get_stage()

    def prepare(self):
        tools.deactivate_all_lights(self.stage)
        tools.add_natural_light(self.stage)
        parser.process_stage_by_naming_rules(self.stage, parser.PROCESSING_RULES)

    def update(self):
        iscctx.get_isaac_context().simulation_app.update()
