"""Model stylesheet parser and applier."""

from __future__ import annotations

from pydantic import BaseModel, Field

from attractor.pipeline.graph import Graph, Node


class StyleRule(BaseModel):
    selector: str
    selector_type: str  # "universal", "class", "id"
    specificity: int = 0
    properties: dict[str, str] = Field(default_factory=dict)


class Stylesheet(BaseModel):
    rules: list[StyleRule] = Field(default_factory=list)


def parse_stylesheet(text: str) -> Stylesheet:
    text = text.strip()
    if not text:
        return Stylesheet()

    rules: list[StyleRule] = []
    remaining = text

    while remaining.strip():
        remaining = remaining.strip()
        if not remaining:
            break

        brace_start = remaining.find("{")
        if brace_start == -1:
            break

        selector = remaining[:brace_start].strip()
        remaining = remaining[brace_start + 1 :]

        brace_end = remaining.find("}")
        if brace_end == -1:
            raise ValueError("Unterminated style block")

        body = remaining[:brace_end].strip()
        remaining = remaining[brace_end + 1 :]

        properties: dict[str, str] = {}
        for prop in body.split(";"):
            prop = prop.strip()
            if not prop:
                continue
            if ":" not in prop:
                continue
            key, _, val = prop.partition(":")
            properties[key.strip()] = val.strip()

        if selector == "*":
            rules.append(
                StyleRule(
                    selector=selector,
                    selector_type="universal",
                    specificity=0,
                    properties=properties,
                )
            )
        elif selector.startswith("#"):
            rules.append(
                StyleRule(
                    selector=selector,
                    selector_type="id",
                    specificity=2,
                    properties=properties,
                )
            )
        elif selector.startswith("."):
            rules.append(
                StyleRule(
                    selector=selector,
                    selector_type="class",
                    specificity=1,
                    properties=properties,
                )
            )
        else:
            rules.append(
                StyleRule(
                    selector=selector,
                    selector_type="class",
                    specificity=1,
                    properties=properties,
                )
            )

    return Stylesheet(rules=rules)


def apply_stylesheet(graph: Graph, stylesheet: Stylesheet) -> None:
    sorted_rules = sorted(stylesheet.rules, key=lambda r: r.specificity)

    for node in graph.nodes.values():
        resolved: dict[str, str] = {}

        for rule in sorted_rules:
            if _matches(node, rule):
                resolved.update(rule.properties)

        for key, val in resolved.items():
            if key not in node.attrs:
                node.attrs[key] = val


def _matches(node: Node, rule: StyleRule) -> bool:
    if rule.selector_type == "universal":
        return True
    if rule.selector_type == "id":
        return f"#{node.id}" == rule.selector
    if rule.selector_type == "class":
        sel = rule.selector.lstrip(".")
        return node.css_class == sel or node.type == sel
    return False
