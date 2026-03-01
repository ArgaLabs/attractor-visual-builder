"""AST transforms: variable expansion, stylesheet application, custom transforms."""

from __future__ import annotations

from typing import Callable

from attractor.pipeline.graph import Graph
from attractor.pipeline.stylesheet import apply_stylesheet, parse_stylesheet

Transform = Callable[[Graph], None]


def variable_expansion(graph: Graph) -> None:
    goal = graph.goal
    vars: dict[str, str] = {"goal": goal}
    vars.update({k: str(v) for k, v in graph.attrs.items()})

    for node in graph.nodes.values():
        for key, val in list(node.attrs.items()):
            if isinstance(val, str):
                for var_name, var_val in vars.items():
                    val = val.replace(f"${var_name}", var_val)
                    val = val.replace(f"${{{var_name}}}", var_val)
                node.attrs[key] = val


def stylesheet_transform(graph: Graph) -> None:
    ss_text = graph.stylesheet
    if not ss_text:
        return
    stylesheet = parse_stylesheet(ss_text)
    apply_stylesheet(graph, stylesheet)


def apply_transforms(graph: Graph, custom: list[Transform] | None = None) -> None:
    variable_expansion(graph)
    stylesheet_transform(graph)
    if custom:
        for transform in custom:
            transform(graph)
