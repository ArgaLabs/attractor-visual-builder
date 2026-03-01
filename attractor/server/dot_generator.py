"""Generate DOT source from a visual graph definition."""

from __future__ import annotations

from typing import Any

SHAPE_MAP = {
    "start": "Mdiamond",
    "exit": "Msquare",
    "codergen": "box",
    "conditional": "diamond",
    "human": "house",
    "tool": "parallelogram",
    "parallel": "component",
    "fan_in": "tripleoctagon",
    "manager": "hexagon",
}


def generate_dot(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    graph_attrs: dict[str, Any] | None = None,
) -> str:
    lines: list[str] = []
    name = (graph_attrs or {}).get("name", "Pipeline")
    lines.append(f"digraph {_quote_id(name)} {{")

    g_attrs = dict(graph_attrs or {})
    g_attrs.pop("name", None)
    if g_attrs:
        attr_str = _format_attrs(g_attrs)
        lines.append(f"    graph {attr_str}")

    lines.append("")

    for node in nodes:
        node_id = node.get("id", "")
        if not node_id:
            continue

        attrs: dict[str, str] = {}
        node_type = node.get("type", "codergen")

        shape = SHAPE_MAP.get(node_type, node_type)
        attrs["shape"] = shape

        if node.get("label") and node["label"] != node_id:
            attrs["label"] = node["label"]
        if node.get("prompt"):
            attrs["prompt"] = node["prompt"]
        if node.get("goal_gate"):
            attrs["goal_gate"] = "true"
        if node.get("max_retries"):
            attrs["max_retries"] = str(node["max_retries"])
        if node.get("retry_target"):
            attrs["retry_target"] = node["retry_target"]
        if node.get("timeout"):
            attrs["timeout"] = node["timeout"]
        if node.get("command"):
            attrs["command"] = node["command"]
        if node.get("llm_model"):
            attrs["llm_model"] = node["llm_model"]
        if node.get("css_class"):
            attrs["class"] = node["css_class"]

        for k, v in node.get("extra_attrs", {}).items():
            attrs[k] = str(v)

        attr_str = _format_attrs(attrs) if attrs else ""
        lines.append(f"    {_quote_id(node_id)} {attr_str}")

    lines.append("")

    for edge in edges:
        source = edge.get("source", "")
        target = edge.get("target", "")
        if not source or not target:
            continue

        attrs: dict[str, str] = {}
        if edge.get("label"):
            attrs["label"] = edge["label"]
        if edge.get("condition"):
            attrs["condition"] = edge["condition"]
        if edge.get("weight"):
            attrs["weight"] = str(edge["weight"])
        if edge.get("fidelity"):
            attrs["fidelity"] = edge["fidelity"]
        if edge.get("loop_restart"):
            attrs["loop_restart"] = "true"

        for k, v in edge.get("extra_attrs", {}).items():
            attrs[k] = str(v)

        attr_str = f" {_format_attrs(attrs)}" if attrs else ""
        lines.append(
            f"    {_quote_id(source)} -> {_quote_id(target)}{attr_str}"
        )

    lines.append("}")
    return "\n".join(lines)


def _quote_id(name: str) -> str:
    if name.isidentifier() and name.isascii():
        return name
    return f'"{name}"'


def _format_attrs(attrs: dict[str, str]) -> str:
    parts: list[str] = []
    for k, v in attrs.items():
        parts.append(f'{k}="{_escape(v)}"')
    return "[" + ", ".join(parts) + "]"


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')
