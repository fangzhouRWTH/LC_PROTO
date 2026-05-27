from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GraphNodeSpec:
    name: str
    type_name: str
    values: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphConnectionSpec:
    source_node: str
    source_attr: str
    target_node: str
    target_attr: str


@dataclass(frozen=True)
class GraphTemplate:
    graph_path: str
    nodes: tuple[GraphNodeSpec, ...] = ()
    connections: tuple[GraphConnectionSpec, ...] = ()
    values: dict[str, Any] = field(default_factory=dict)
    required_extensions: tuple[str, ...] = ()


class GraphBuildError(RuntimeError):
    pass


class GraphVFXBuilder:
    """Thin script wrapper around OmniGraph creation APIs."""

    def __init__(self, strict_extensions: bool = False):
        self.strict_extensions = strict_extensions

    def ensure_extensions(self, extension_names: tuple[str, ...]) -> None:
        if not extension_names:
            return

        try:
            import omni.kit.app
        except ImportError as exc:
            raise GraphBuildError(
                "Cannot enable OmniGraph extensions before Isaac/Kit is running."
            ) from exc

        manager = omni.kit.app.get_app().get_extension_manager()
        for extension_name in extension_names:
            try:
                manager.set_extension_enabled_immediate(extension_name, True)
            except Exception as exc:
                message = f"Failed to enable extension: {extension_name}"
                if self.strict_extensions:
                    raise GraphBuildError(message) from exc
                print(f"[WARN] {message}: {exc}")

    def build(self, template: GraphTemplate):
        self.ensure_extensions(template.required_extensions)

        try:
            import omni.graph.core as og
        except ImportError as exc:
            raise GraphBuildError(
                "Cannot import omni.graph.core before Isaac/Kit is running."
            ) from exc

        keys = og.Controller.Keys
        edit_data = {}
        if template.nodes:
            edit_data[keys.CREATE_NODES] = [
                (node.name, node.type_name) for node in template.nodes
            ]
        if template.connections:
            edit_data[keys.CONNECT] = [
                (
                    f"{conn.source_node}.{conn.source_attr}",
                    f"{conn.target_node}.{conn.target_attr}",
                )
                for conn in template.connections
            ]

        result = None
        if edit_data:
            result = og.Controller.edit(template.graph_path, edit_data)

        for node in template.nodes:
            self.set_node_values(template.graph_path, node.name, node.values)
        self.set_graph_values(template.graph_path, template.values)
        return result

    def set_graph_values(self, graph_path: str, values: dict[str, Any]) -> None:
        for attr_path, value in values.items():
            self.set_attribute(graph_path, attr_path, value)

    def set_node_values(
        self,
        graph_path: str,
        node_name: str,
        values: dict[str, Any],
    ) -> None:
        for attr_name, value in values.items():
            self.set_attribute(graph_path, f"{node_name}.{attr_name}", value)

    def set_attribute(self, graph_path: str, relative_attr_path: str, value: Any) -> None:
        import omni.graph.core as og

        attr = og.Controller.attribute(f"{graph_path}/{relative_attr_path}")
        attr.set(value)

