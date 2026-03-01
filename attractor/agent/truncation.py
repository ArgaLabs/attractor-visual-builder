"""Tool output truncation with head/tail split."""

from __future__ import annotations

DEFAULT_CHAR_LIMITS: dict[str, int] = {
    "read_file": 50000,
    "shell": 30000,
    "grep": 20000,
    "glob": 20000,
    "edit_file": 10000,
    "apply_patch": 10000,
    "write_file": 1000,
    "spawn_agent": 20000,
}

DEFAULT_TRUNCATION_MODES: dict[str, str] = {
    "read_file": "head_tail",
    "shell": "head_tail",
    "grep": "tail",
    "glob": "tail",
    "edit_file": "tail",
    "apply_patch": "tail",
    "write_file": "tail",
    "spawn_agent": "head_tail",
}

DEFAULT_LINE_LIMITS: dict[str, int | None] = {
    "shell": 256,
    "grep": 200,
    "glob": 500,
    "read_file": None,
    "edit_file": None,
}


def truncate_output(output: str, max_chars: int, mode: str = "head_tail") -> str:
    if len(output) <= max_chars:
        return output

    if mode == "head_tail":
        half = max_chars // 2
        removed = len(output) - max_chars
        return (
            output[:half] + f"\n\n[WARNING: Tool output was truncated. "
            f"{removed} characters were removed from the middle. "
            f"The full output is available in the event stream. "
            "If you need to see specific parts, re-run the tool"
            " with more targeted parameters.]\n\n"
            + output[-half:]
        )

    if mode == "tail":
        removed = len(output) - max_chars
        return (
            f"[WARNING: Tool output was truncated. First "
            f"{removed} characters were removed. "
            f"The full output is available in the event stream.]\n\n" + output[-max_chars:]
        )

    return output[:max_chars]


def truncate_lines(output: str, max_lines: int) -> str:
    lines = output.split("\n")
    if len(lines) <= max_lines:
        return output

    head_count = max_lines // 2
    tail_count = max_lines - head_count
    omitted = len(lines) - head_count - tail_count

    return (
        "\n".join(lines[:head_count])
        + f"\n[... {omitted} lines omitted ...]\n"
        + "\n".join(lines[-tail_count:])
    )


def truncate_tool_output(
    output: str,
    tool_name: str,
    char_limits: dict[str, int] | None = None,
    line_limits: dict[str, int | None] | None = None,
) -> str:
    limits = char_limits or DEFAULT_CHAR_LIMITS
    max_chars = limits.get(tool_name, 30000)
    mode = DEFAULT_TRUNCATION_MODES.get(tool_name, "head_tail")

    result = truncate_output(output, max_chars, mode)

    l_limits = line_limits or DEFAULT_LINE_LIMITS
    max_lines = l_limits.get(tool_name)
    if max_lines is not None:
        result = truncate_lines(result, max_lines)

    return result
