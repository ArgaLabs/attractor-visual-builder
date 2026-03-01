"""System prompt construction and project document discovery."""

from __future__ import annotations

import os
import subprocess

from attractor.agent.execution.base import ExecutionEnvironment

PROVIDER_DOC_FILES: dict[str, list[str]] = {
    "openai": ["AGENTS.md", ".codex/instructions.md"],
    "anthropic": ["AGENTS.md", "CLAUDE.md"],
    "gemini": ["AGENTS.md", "GEMINI.md"],
}

MAX_PROJECT_DOCS_BYTES = 32768


def discover_project_docs(working_dir: str, provider: str = "anthropic") -> str:
    doc_names = PROVIDER_DOC_FILES.get(provider, ["AGENTS.md"])
    docs: list[str] = []
    total = 0

    git_root = _find_git_root(working_dir)
    search_dirs = []
    if git_root and git_root != working_dir:
        search_dirs.append(git_root)
    search_dirs.append(working_dir)

    for search_dir in search_dirs:
        for doc_name in doc_names:
            path = os.path.join(search_dir, doc_name)
            if os.path.isfile(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        content = f.read()
                    if total + len(content) > MAX_PROJECT_DOCS_BYTES:
                        remaining = MAX_PROJECT_DOCS_BYTES - total
                        content = content[:remaining] + "\n[Project instructions truncated at 32KB]"
                    docs.append(f"# {doc_name}\n\n{content}")
                    total += len(content)
                    if total >= MAX_PROJECT_DOCS_BYTES:
                        break
                except OSError:
                    continue
        if total >= MAX_PROJECT_DOCS_BYTES:
            break

    return "\n\n---\n\n".join(docs)


def build_environment_context(env: ExecutionEnvironment) -> str:
    import datetime

    lines = [
        "<environment>",
        f"Working directory: {env.working_directory()}",
    ]

    git_root = _find_git_root(env.working_directory())
    if git_root:
        lines.append("Is git repository: true")
        branch = _git_branch(env.working_directory())
        if branch:
            lines.append(f"Git branch: {branch}")
    else:
        lines.append("Is git repository: false")

    lines.extend(
        [
            f"Platform: {env.platform()}",
            f"OS version: {env.os_version()}",
            f"Today's date: {datetime.date.today().isoformat()}",
            "</environment>",
        ]
    )
    return "\n".join(lines)


def _find_git_root(path: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _git_branch(path: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None
