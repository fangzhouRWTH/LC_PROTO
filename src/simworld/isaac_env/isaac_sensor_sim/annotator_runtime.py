from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReplicatorAnnotatorRuntime:
    camera_prim_path: str
    resolution: tuple[int, int]
    annotator_names: tuple[str, ...]
    render_product: Any = field(default=None, init=False)
    annotators: dict[str, Any] = field(default_factory=dict, init=False)
    render_product_path: str | None = field(default=None, init=False)
    initialized: bool = field(default=False, init=False)
    warning: str | None = field(default=None, init=False)

    def initialize(self) -> bool:
        try:
            import omni.replicator.core as rep

            self.render_product = rep.create.render_product(
                self.camera_prim_path,
                resolution=tuple(int(v) for v in self.resolution),
            )
            self.render_product_path = _render_product_path(self.render_product)

            for name in self.annotator_names:
                annotator = rep.AnnotatorRegistry.get_annotator(name)
                try:
                    annotator.attach([self.render_product])
                except Exception:
                    annotator.attach(self.render_product)
                self.annotators[name] = annotator

            self.initialized = True
            return True
        except Exception as exc:
            self.warning = str(exc)
            print(
                "[WARNING] Could not initialize Replicator annotator runtime "
                f"for {self.camera_prim_path}: {exc}"
            )
            self.initialized = False
            return False

    def get_data(self) -> dict[str, Any]:
        if not self.initialized:
            return {}

        data: dict[str, Any] = {}
        for name, annotator in self.annotators.items():
            try:
                data[name] = annotator.get_data()
            except Exception as exc:
                data[name] = None
                print(f"[WARNING] Could not read annotator {name}: {exc}")
        return data

    def detach(self) -> None:
        for annotator in self.annotators.values():
            try:
                annotator.detach([self.render_product])
            except Exception:
                try:
                    annotator.detach()
                except Exception:
                    pass
        self.annotators.clear()
        self.initialized = False


def _render_product_path(render_product: Any) -> str | None:
    for attr_name in ("path", "render_product_path"):
        value = getattr(render_product, attr_name, None)
        if value:
            return str(value)

    try:
        return str(render_product)
    except Exception:
        return None
