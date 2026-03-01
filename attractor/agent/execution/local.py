"""Local execution environment implementation."""

from __future__ import annotations

import asyncio
import fnmatch
import os
import re
import signal
import time
from pathlib import Path

from attractor.agent.execution.base import (
    DirEntry,
    ExecResult,
    ExecutionEnvironment,
    GrepOptions,
)

_SENSITIVE_PATTERNS = [
    "*_API_KEY",
    "*_SECRET",
    "*_TOKEN",
    "*_PASSWORD",
    "*_CREDENTIAL",
]
_ALWAYS_INCLUDE = {
    "PATH",
    "HOME",
    "USER",
    "SHELL",
    "LANG",
    "TERM",
    "TMPDIR",
    "GOPATH",
    "CARGO_HOME",
    "NVM_DIR",
    "PYTHONPATH",
    "VIRTUAL_ENV",
    "CONDA_DEFAULT_ENV",
    "JAVA_HOME",
    "NODE_PATH",
}


def _filter_env() -> dict[str, str]:
    filtered: dict[str, str] = {}
    for key, val in os.environ.items():
        if key in _ALWAYS_INCLUDE:
            filtered[key] = val
            continue
        is_sensitive = False
        for pat in _SENSITIVE_PATTERNS:
            if fnmatch.fnmatch(key.upper(), pat.upper()):
                is_sensitive = True
                break
        if not is_sensitive:
            filtered[key] = val
    return filtered


class LocalExecutionEnvironment(ExecutionEnvironment):
    def __init__(self, working_dir: str | None = None):
        self._working_dir = working_dir or os.getcwd()

    def working_directory(self) -> str:
        return self._working_dir

    def _resolve(self, path: str) -> str:
        p = Path(path)
        if not p.is_absolute():
            p = Path(self._working_dir) / p
        return str(p)

    async def read_file(
        self, path: str, offset: int | None = None, limit: int | None = None
    ) -> str:
        resolved = self._resolve(path)
        with open(resolved, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        if offset is not None:
            start = max(0, offset - 1)
        else:
            start = 0

        if limit is not None:
            end = start + limit
        else:
            end = len(lines)

        selected = lines[start:end]
        numbered = []
        for i, line in enumerate(selected, start=start + 1):
            numbered.append(f"{i:6d} | {line.rstrip()}")
        return "\n".join(numbered)

    async def write_file(self, path: str, content: str) -> None:
        resolved = self._resolve(path)
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(content)

    async def file_exists(self, path: str) -> bool:
        return os.path.exists(self._resolve(path))

    async def list_directory(self, path: str, depth: int = 1) -> list[DirEntry]:
        resolved = self._resolve(path)
        entries: list[DirEntry] = []
        try:
            for item in sorted(os.listdir(resolved)):
                full = os.path.join(resolved, item)
                is_dir = os.path.isdir(full)
                size = os.path.getsize(full) if not is_dir else None
                entries.append(DirEntry(name=item, is_dir=is_dir, size=size))
        except OSError:
            pass
        return entries

    async def exec_command(
        self,
        command: str,
        timeout_ms: int = 10000,
        working_dir: str | None = None,
        env_vars: dict[str, str] | None = None,
    ) -> ExecResult:
        cwd = working_dir or self._working_dir
        env = _filter_env()
        if env_vars:
            env.update(env_vars)

        timeout_s = timeout_ms / 1000.0
        start = time.monotonic()

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
                start_new_session=True,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_s
                )
                elapsed = int((time.monotonic() - start) * 1000)
                return ExecResult(
                    stdout=stdout_bytes.decode(errors="replace"),
                    stderr=stderr_bytes.decode(errors="replace"),
                    exit_code=proc.returncode or 0,
                    timed_out=False,
                    duration_ms=elapsed,
                )
            except asyncio.TimeoutError:
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGTERM)
                try:
                    await asyncio.wait_for(proc.communicate(), timeout=2.0)
                except asyncio.TimeoutError:
                    os.killpg(pgid, signal.SIGKILL)
                    await proc.communicate()

                elapsed = int((time.monotonic() - start) * 1000)
                return ExecResult(
                    stdout="",
                    stderr=f"[ERROR: Command timed out after {timeout_ms}ms]",
                    exit_code=-1,
                    timed_out=True,
                    duration_ms=elapsed,
                )
        except OSError as e:
            elapsed = int((time.monotonic() - start) * 1000)
            return ExecResult(
                stdout="",
                stderr=str(e),
                exit_code=-1,
                duration_ms=elapsed,
            )

    async def grep(self, pattern: str, path: str, options: GrepOptions | None = None) -> str:
        opts = options or GrepOptions()
        resolved = self._resolve(path)

        cmd_parts = ["rg", "--line-number"]
        if opts.case_insensitive:
            cmd_parts.append("-i")
        cmd_parts.extend(["--max-count", str(opts.max_results)])
        if opts.glob_filter:
            cmd_parts.extend(["--glob", opts.glob_filter])
        cmd_parts.extend(["--", pattern, resolved])

        result = await self.exec_command(" ".join(cmd_parts), timeout_ms=30000)
        if result.exit_code == 0:
            return result.stdout
        # Fallback to Python regex if rg not available
        return await self._grep_fallback(pattern, resolved, opts)

    async def _grep_fallback(self, pattern: str, path: str, opts: GrepOptions) -> str:
        flags = re.IGNORECASE if opts.case_insensitive else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error:
            return f"Invalid regex: {pattern}"

        matches: list[str] = []
        target = Path(path)

        if target.is_file():
            files = [target]
        else:
            files = sorted(target.rglob("*"))

        for fp in files:
            if not fp.is_file():
                continue
            if opts.glob_filter and not fnmatch.fnmatch(fp.name, opts.glob_filter):
                continue
            try:
                for i, line in enumerate(fp.open(encoding="utf-8", errors="replace"), 1):
                    if regex.search(line):
                        matches.append(f"{fp}:{i}:{line.rstrip()}")
                        if len(matches) >= opts.max_results:
                            return "\n".join(matches)
            except (OSError, UnicodeDecodeError):
                continue

        return "\n".join(matches)

    async def glob(self, pattern: str, path: str | None = None) -> list[str]:
        import glob as _glob

        base = path or self._working_dir
        resolved = self._resolve(base)
        full_pattern = os.path.join(resolved, pattern)
        results = _glob.glob(full_pattern, recursive=True)
        results.sort(key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0, reverse=True)
        return results
