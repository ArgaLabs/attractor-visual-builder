"""Tests for attractor.llm.tools."""

from __future__ import annotations

from attractor.llm.models import ToolDefinition
from attractor.llm.tools import Tool


class TestToolToDefinition:
    def test_basic_tool(self):
        tool = Tool(
            name="search",
            description="Search the web",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        )
        defn = tool.to_definition()
        assert isinstance(defn, ToolDefinition)
        assert defn.name == "search"
        assert defn.description == "Search the web"
        assert defn.parameters["type"] == "object"
        assert "query" in defn.parameters["properties"]

    def test_empty_parameters(self):
        tool = Tool(name="noop", description="Does nothing")
        defn = tool.to_definition()
        assert defn.name == "noop"
        assert defn.description == "Does nothing"
        assert defn.parameters == {"type": "object", "properties": {}}

    def test_complex_parameters(self):
        params = {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "overwrite": {"type": "boolean", "default": False},
            },
            "required": ["path", "content"],
        }
        tool = Tool(name="write_file", description="Write a file", parameters=params)
        defn = tool.to_definition()
        assert defn.parameters == params

    def test_definition_fields_independent_of_execute(self):
        tool = Tool(
            name="calc",
            description="Calculator",
            parameters={"type": "object", "properties": {"expr": {"type": "string"}}},
            execute=lambda expr: eval(expr),
        )
        defn = tool.to_definition()
        assert defn.name == "calc"
        assert not hasattr(defn, "execute")

    def test_tool_with_no_description(self):
        tool = Tool(name="bare_tool")
        defn = tool.to_definition()
        assert defn.name == "bare_tool"
        assert defn.description == ""
