"""Core tool implementations shared across all provider profiles."""

from __future__ import annotations

from typing import Any

from attractor.agent.execution.base import ExecutionEnvironment, GrepOptions
from attractor.agent.tools.registry import RegisteredTool, ToolRegistry
from attractor.llm.models import ToolDefinition


async def read_file_exec(arguments: dict[str, Any], env: ExecutionEnvironment) -> str:
    path = arguments["file_path"]
    offset = arguments.get("offset")
    limit = arguments.get("limit", 2000)
    return await env.read_file(path, offset=offset, limit=limit)


async def write_file_exec(arguments: dict[str, Any], env: ExecutionEnvironment) -> str:
    path = arguments["file_path"]
    content = arguments["content"]
    await env.write_file(path, content)
    return f"Successfully wrote {len(content)} bytes to {path}"


async def edit_file_exec(arguments: dict[str, Any], env: ExecutionEnvironment) -> str:
    path = arguments["file_path"]
    old_string = arguments["old_string"]
    new_string = arguments["new_string"]
    replace_all = arguments.get("replace_all", False)

    content = await env.read_file(path)
    lines = []
    for line in content.split("\n"):
        parts = line.split(" | ", 1)
        lines.append(parts[1] if len(parts) == 2 else line)
    text = "\n".join(lines)

    if old_string not in text:
        return f"Error: old_string not found in {path}"

    if not replace_all and text.count(old_string) > 1:
        return (
            f"Error: old_string found {text.count(old_string)} times"
            f" in {path}. Provide more context to make it unique,"
            f" or use replace_all=true."
        )

    if replace_all:
        count = text.count(old_string)
        new_text = text.replace(old_string, new_string)
    else:
        new_text = text.replace(old_string, new_string, 1)
        count = 1

    await env.write_file(path, new_text)
    return f"Made {count} replacement(s) in {path}"


async def shell_exec(arguments: dict[str, Any], env: ExecutionEnvironment) -> str:
    command = arguments["command"]
    timeout_ms = arguments.get("timeout_ms", 10000)
    result = await env.exec_command(command, timeout_ms=timeout_ms)

    output = result.stdout
    if result.stderr:
        output += "\n" + result.stderr
    if result.timed_out:
        output += (
            f"\n[ERROR: Command timed out after {timeout_ms}ms."
            " Partial output is shown above."
            " You can retry with a longer timeout"
            " by setting the timeout_ms parameter.]"
        )

    return f"{output}\n\nExit code: {result.exit_code}"


async def grep_exec(arguments: dict[str, Any], env: ExecutionEnvironment) -> str:
    pattern = arguments["pattern"]
    path = arguments.get("path", env.working_directory())
    opts = GrepOptions(
        case_insensitive=arguments.get("case_insensitive", False),
        max_results=arguments.get("max_results", 100),
        glob_filter=arguments.get("glob_filter"),
    )
    return await env.grep(pattern, path, opts)


async def glob_exec(arguments: dict[str, Any], env: ExecutionEnvironment) -> str:
    pattern = arguments["pattern"]
    path = arguments.get("path")
    results = await env.glob(pattern, path)
    return "\n".join(results)


def register_core_tools(registry: ToolRegistry) -> None:
    registry.register(
        RegisteredTool(
            definition=ToolDefinition(
                name="read_file",
                description="Read a file from the filesystem. Returns line-numbered content.",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Absolute path to the file"},
                        "offset": {
                            "type": "integer",
                            "description": "1-based line number to start from",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max lines to read (default: 2000)",
                        },
                    },
                    "required": ["file_path"],
                },
            ),
            executor=read_file_exec,
        )
    )
    registry.register(
        RegisteredTool(
            definition=ToolDefinition(
                name="write_file",
                description=(
                    "Write content to a file."
                    " Creates the file and parent directories if needed."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Absolute path"},
                        "content": {"type": "string", "description": "The full file content"},
                    },
                    "required": ["file_path", "content"],
                },
            ),
            executor=write_file_exec,
        )
    )
    registry.register(
        RegisteredTool(
            definition=ToolDefinition(
                name="edit_file",
                description="Replace an exact string occurrence in a file.",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                        "old_string": {"type": "string", "description": "Exact text to find"},
                        "new_string": {"type": "string", "description": "Replacement text"},
                        "replace_all": {
                            "type": "boolean",
                            "description": "Replace all occurrences (default: false)",
                        },
                    },
                    "required": ["file_path", "old_string", "new_string"],
                },
            ),
            executor=edit_file_exec,
        )
    )
    registry.register(
        RegisteredTool(
            definition=ToolDefinition(
                name="shell",
                description="Execute a shell command. Returns stdout, stderr, and exit code.",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The command to run"},
                        "timeout_ms": {
                            "type": "integer",
                            "description": "Override default timeout",
                        },
                        "description": {
                            "type": "string",
                            "description": "Human-readable description",
                        },
                    },
                    "required": ["command"],
                },
            ),
            executor=shell_exec,
        )
    )
    registry.register(
        RegisteredTool(
            definition=ToolDefinition(
                name="grep",
                description="Search file contents using regex patterns.",
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "Regex pattern"},
                        "path": {"type": "string", "description": "Directory or file to search"},
                        "glob_filter": {
                            "type": "string",
                            "description": 'File pattern filter (e.g., "*.py")',
                        },
                        "case_insensitive": {"type": "boolean"},
                        "max_results": {"type": "integer"},
                    },
                    "required": ["pattern"],
                },
            ),
            executor=grep_exec,
        )
    )
    registry.register(
        RegisteredTool(
            definition=ToolDefinition(
                name="glob",
                description="Find files matching a glob pattern.",
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": 'Glob pattern (e.g., "**/*.ts")',
                        },
                        "path": {"type": "string", "description": "Base directory"},
                    },
                    "required": ["pattern"],
                },
            ),
            executor=glob_exec,
        )
    )
